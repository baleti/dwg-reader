"""Tiny Chrome DevTools Protocol client on aiohttp (no playwright here): start server + headless chromium, evaluate JS, mouse/keyboard events, screenshots, console errors."""
import sys, os, json, time, socket, subprocess, asyncio, urllib.request, base64
import aiohttp
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


class Session:
    def __init__(self, path, width=1500, height=950):
        self.path, self.w, self.h = os.path.abspath(path), width, height
        self.errors = []; self._id = 0

    async def __aenter__(self):
        self.sp, cp = free_port(), free_port()
        env = dict(os.environ)
        self.srv = subprocess.Popen([sys.executable, '-m', 'dwgviewer', self.path, '--no-browser', '--port', str(self.sp)], cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        prof = '/tmp/claude-1000/cdp-prof-%d' % cp
        self.ch = subprocess.Popen(['systemd-run', '--user', '--scope', '-q', '-p', 'CPUQuota=300%', 'nice', '-n', '19', 'chromium', '--headless=new', '--no-sandbox', '--disable-gpu', '--user-data-dir=' + prof,
                                    '--remote-debugging-port=%d' % cp, '--window-size=%d,%d' % (self.w, self.h), 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            try: tabs = json.load(urllib.request.urlopen('http://127.0.0.1:%d/json' % cp)); break
            except Exception: await asyncio.sleep(0.3)
        ws_url = next(t['webSocketDebuggerUrl'] for t in tabs if t['type'] == 'page')
        self.sess = aiohttp.ClientSession(); self.ws = await self.sess.ws_connect(ws_url, max_msg_size=0)
        self.reader = asyncio.ensure_future(self._read()); self.pending = {}
        await self.call('Runtime.enable'); await self.call('Page.enable')
        return self

    async def _read(self):
        async for m in self.ws:
            d = json.loads(m.data)
            if 'id' in d and d['id'] in self.pending: self.pending.pop(d['id']).set_result(d)
            elif d.get('method') == 'Runtime.exceptionThrown': self.errors.append(d['params']['exceptionDetails'].get('exception', {}).get('description', str(d['params']['exceptionDetails']))[:300])
            elif d.get('method') == 'Runtime.consoleAPICalled' and d['params']['type'] == 'error': self.errors.append(' '.join(str(a.get('value', a.get('description', ''))) for a in d['params']['args'])[:300])

    async def call(self, method, **params):
        self._id += 1; i = self._id
        fut = asyncio.get_running_loop().create_future(); self.pending[i] = fut
        await self.ws.send_json({'id': i, 'method': method, 'params': params})
        return await fut

    async def js(self, expr):
        r = await self.call('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=True)
        res = r.get('result', {})
        if 'exceptionDetails' in res: self.errors.append(str(res['exceptionDetails'].get('exception', {}).get('description', res['exceptionDetails']))[:400])
        return res.get('result', {}).get('value')

    async def open(self, query='', layout=None, wait_paths=True):
        for _ in range(240):
            try:
                if not json.load(urllib.request.urlopen('http://127.0.0.1:%d/api/meta' % self.sp)).get('loading'): break
            except Exception: pass
            await asyncio.sleep(0.5)
        if layout is not None: urllib.request.urlopen('http://127.0.0.1:%d/api/layout/%d' % (self.sp, layout), timeout=600).read()
        await self.call('Page.navigate', url='http://127.0.0.1:%d/?%s%s' % (self.sp, ('l=%d&' % layout) if layout is not None else '', query))
        for _ in range(2400):
            v = await self.js("(window.lay ? 1 : 0) + '|' + (document.getElementById('msg')||{style:{}}).style.display")
            if v and v.startswith('1') or (await self.js("typeof lay!=='undefined' && lay!==null && (document.getElementById('msg')||{style:{}}).style.display==='none'")): break
            await asyncio.sleep(0.4)
        await asyncio.sleep(0.5)

    async def mouse(self, typ, x, y, button='left', buttons=1, mods=0, count=1):
        await self.call('Input.dispatchMouseEvent', type=typ, x=x, y=y, button=button, buttons=buttons, modifiers=mods, clickCount=count)

    async def drag(self, x0, y0, x1, y1, steps=8, button='left', mods=0):
        b = {'left': 1, 'middle': 4, 'right': 2}[button]
        await self.mouse('mouseMoved', x0, y0, 'none', 0, mods)
        await self.mouse('mousePressed', x0, y0, button, b, mods)
        for i in range(1, steps + 1): await self.mouse('mouseMoved', x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps, button, b, mods)
        await self.mouse('mouseReleased', x1, y1, button, 0, mods)

    async def click(self, x, y, mods=0):
        await self.mouse('mouseMoved', x, y, 'none', 0, mods); await self.mouse('mousePressed', x, y, 'left', 1, mods); await self.mouse('mouseReleased', x, y, 'left', 0, mods)

    async def key(self, key, mods=0, code=None):
        await self.call('Input.dispatchKeyEvent', type='keyDown', key=key, code=code or key, modifiers=mods, windowsVirtualKeyCode=ord(key.upper()) if len(key) == 1 else 27 if key == 'Escape' else 0)
        await self.call('Input.dispatchKeyEvent', type='keyUp', key=key, code=code or key, modifiers=mods)

    async def wheel(self, x, y, dy):
        await self.call('Input.dispatchMouseEvent', type='mouseWheel', x=x, y=y, deltaX=0, deltaY=dy)

    async def shot(self, path=None):
        r = await self.call('Page.captureScreenshot', format='png')
        data = base64.b64decode(r['result']['data'])
        if path: open(path, 'wb').write(data)
        return data

    async def __aexit__(self, *a):
        try: await self.sess.close()
        except Exception: pass
        self.ch.terminate(); self.srv.terminate()
