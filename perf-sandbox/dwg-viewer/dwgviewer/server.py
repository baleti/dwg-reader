"""aiohttp server: /api/meta, /api/layout/<i>, static web/."""
import struct, os, json, asyncio
from aiohttp import web
from . import build, cache
from . import ole as OLE

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(HERE, 'web')


def make_app(path, start_layout=None, prefetch=True):
    app = web.Application()
    state = {'doc': None, 'err': None, 'meta': None}
    import threading
    locks = {}

    def klock(i, tw):
        return locks.setdefault((i, bool(tw)), threading.Lock())    # one build per layout at a time: a request waits for the prefetch of the same layout instead of duplicating it

    def parse():
        """build the Doc (slow); writes meta + all layouts to the disk cache in the background"""
        d = build.Doc(path)
        state['doc'] = d
        return d

    async def load(app):
        loop = asyncio.get_running_loop()
        m = cache.read_meta(path)
        if m:
            state['meta'] = m
            loop.run_in_executor(None, lambda: _safe(parse))        # the Doc is still needed for the entity inspector
            return
        try:
            d = await loop.run_in_executor(None, parse)
            state['meta'] = d.meta()
            cache.write_meta(path, state['meta'])
            if prefetch: loop.run_in_executor(None, lambda: _safe(lambda: prefetch_all(d)))
        except Exception as ex:
            import traceback; traceback.print_exc()
            names = {'AC1012': 'R13', 'AC1014': 'R14', 'AC1009': 'R12'}
            v = str(ex).strip("'\" ")
            import re as _re
            state['err'] = ('This drawing is %s (%s), a file version the parser cannot read yet.' % (names.get(v, v), v)) if isinstance(ex, NotImplementedError) and _re.fullmatch(r'AC10\d\d', v) else ('This file is not a readable DWG (%s).' % (str(ex) or type(ex).__name__)) if isinstance(ex, NotImplementedError) else ('This drawing could not be read: the file looks damaged, truncated or uses data this parser does not decode (%s).' % (str(ex)[:120] or type(ex).__name__)) if isinstance(ex, (struct.error, ValueError, IndexError, EOFError, KeyError, OverflowError, MemoryError)) else '%s: %s' % (type(ex).__name__, ex)

    def _safe(fn):
        try: return fn()
        except Exception:
            import traceback; traceback.print_exc()

    def prefetch_all(d):
        """default layout first (in this process), the others in forked workers that write the cache themselves (POSIX); serial elsewhere"""
        m = state['meta']
        order = [m['default']] + [l['i'] for l in m['layouts'] if l['i'] != m['default']]
        jobs = [(i, tw) for i in order for tw in ((True, False) if not m['layouts'][i]['ps'] else (True,))]
        todo = [j for j in jobs if not os.path.exists(cache.layout_path(path, *j))]
        first = [j for j in todo if j[0] == m['default']]; rest = [j for j in todo if j[0] != m['default']]
        for j in first:
            with klock(*j):
                if not os.path.exists(cache.layout_path(path, *j)): cache.write_layout(path, j[0], j[1], d.layout(*j))
        if hasattr(os, 'fork') and len(rest) > 1 and not os.environ.get('DWG_NO_FORK'):
            nw = max(1, min(len(rest), (os.cpu_count() or 2) - 1, 3)); running = {}
            for j in rest:
                while len(running) >= nw:
                    pid, _ = os.wait(); running.pop(pid, None)
                pid = os.fork()
                if pid == 0:
                    code = 0
                    try: cache.write_layout(path, j[0], j[1], d.layout(*j))
                    except BaseException: code = 1
                    os._exit(code)
                running[pid] = j
            while running:
                pid, _ = os.wait(); running.pop(pid, None)
        else:
            for j in rest: cache.write_layout(path, j[0], j[1], d.layout(*j))
        cache.prune()
    app.on_startup.append(lambda a: asyncio.ensure_future(load(a)))

    async def meta(req):
        if state['err']: return web.json_response({'error': state['err']})
        if not state['meta']: return web.json_response({'loading': True})
        m = dict(state['meta']); m['start'] = start_layout if start_layout is not None else m['default']
        return web.json_response(m)

    async def layout(req):
        if not state['meta']: return web.json_response({'loading': True}, status=503)
        i = int(req.match_info['i'])
        loop = asyncio.get_running_loop()
        tw = req.query.get('twist', '1') != '0'
        body = cache.read_layout(path, i, tw)
        if body is not None:
            return web.Response(body=body, content_type='application/json', headers={'Content-Encoding': 'gzip'})
        d = state['doc']
        if d is None: d = await loop.run_in_executor(None, parse)
        def build_one():
            with klock(i, tw):
                if cache.read_layout(path, i, tw) is None:
                    r_ = d.layout(i, tw); _safe(lambda: cache.write_layout(path, i, tw, r_)); return r_
            return None
        r = await loop.run_in_executor(None, build_one)
        body = cache.read_layout(path, i, tw)
        if r is None and body is None: r = await loop.run_in_executor(None, d.layout, i, tw)
        if body is not None:
            return web.Response(body=body, content_type='application/json', headers={'Content-Encoding': 'gzip'})
        resp = web.json_response(r); resp.enable_compression(); return resp

    async def olepic(req):
        d = state['doc']; h = int(req.match_info['h'])
        o = d.m.objs.get(h) if d else None
        png = OLE.image_png(o) if o is not None and o.type == 74 else None
        if not png: return web.Response(status=404)
        return web.Response(body=png, content_type='image/png', headers={'Cache-Control': 'max-age=3600'})

    async def entity(req):
        d = state['doc']; h = int(req.match_info['h'])
        if not d: return web.json_response({'kind': 'loading'})
        for es in d.sc.by_block.values():
            for e in es:
                if e['handle'] == h:
                    keep = {k: v for k, v in e.items() if k not in ('eed', 'paths', 'pts', 'verts', 'knots', 'ctrl', 'pattern_lines', 'gradient')}
                    return web.json_response({'kind': e['kind'], 'summary': ', '.join('%s=%s' % (k, (round(v, 3) if isinstance(v, float) else v)) for k, v in keep.items() if k in ('block_ref', 'text', 'height', 'text_height', 'radius', 'pattern_name', 'lweight', 'ltscale', 'rot')), 'props': keep}, dumps=lambda o: json.dumps(o, default=str))
        return web.json_response({})

    async def ctbapi(req):
        from . import ctb
        n = req.query.get('name', '')
        p = ctb.find(n)
        if not p: return web.json_response({'name': n, 'found': False})
        t = ctb.table(p)
        return web.json_response({'name': os.path.basename(p), 'found': True, 'aci': {k: [v['rgb'], v['lw'], v['screen']] for k, v in t['aci'].items()}})

    async def ctbupload(req):
        """a plot style table (.ctb) picked in the browser: parsed from the request body, nothing is stored"""
        from . import ctb
        raw = await req.read()
        try:
            t = ctb.table_bytes(raw)
        except Exception as ex:
            return web.json_response({'found': False, 'error': str(ex)[:120]})
        return web.json_response({'found': True, 'aci': {k: [v['rgb'], v['lw'], v['screen']] for k, v in t['aci'].items()}})

    async def ctblist(req):
        from . import ctb
        out = []
        for d in ctb.SEARCH:
            if d and os.path.isdir(d): out += sorted(f for f in os.listdir(d) if f.lower().endswith('.ctb'))
        return web.json_response(sorted(set(out)))

    async def index(req):
        return web.FileResponse(os.path.join(WEB, 'index.html'))
    app.router.add_get('/', index)
    app.router.add_get('/api/meta', meta)
    app.router.add_get('/api/layout/{i}', layout)
    app.router.add_get('/api/ctb', ctbapi)
    app.router.add_get('/api/ctblist', ctblist)
    app.router.add_post('/api/ctbupload', ctbupload)
    app.router.add_get('/api/entity/{h}', entity)
    app.router.add_get('/api/ole/{h}', olepic)
    app.router.add_static('/', WEB)
    return app
