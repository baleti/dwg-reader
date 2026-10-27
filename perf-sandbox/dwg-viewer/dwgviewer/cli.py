import argparse, os, sys, socket, subprocess, json
from aiohttp import web
from . import server


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


def open_browser(url, workspace=None):
    prof = os.path.expanduser('~/.cache/dwg-viewer/chromium-profile')
    cmd = ['chromium', '--app=' + url, '--user-data-dir=' + prof, '--no-first-run', '--window-size=1500,950']
    if workspace:
        import shlex
        code = 'hl.dispatch(hl.dsp.exec_cmd(%s))' % json.dumps('[workspace %s silent] %s' % (workspace, ' '.join(shlex.quote(c) for c in cmd)))
        subprocess.run(['hyprctl', 'eval', code])
    else:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main(argv=None):
    ap = argparse.ArgumentParser(prog='dwg-viewer')
    ap.add_argument('file', nargs='+')
    ap.add_argument('--prepare', action='store_true', help='parse and cache every layout, print READY with the demo command, do not serve')
    ap.add_argument('--port', type=int, default=0)
    ap.add_argument('--no-browser', action='store_true')
    ap.add_argument('--workspace')
    ap.add_argument('--layout', help='layout name or index to open first')
    ap.add_argument('--model', action='store_true', help='open model space first')
    ap.add_argument('--sheets', action='store_true', help='open the first paper layout with content (the default)')
    ap.add_argument('--hide', default='', help='comma list of layer names hidden at start')
    a = ap.parse_args(argv)
    if a.prepare:
        from . import build, cache
        import time
        for f in a.file:
            f = os.path.abspath(f); t = time.time()
            if cache.read_meta(f) and all(os.path.isfile(cache.layout_path(f, l['i'], True)) for l in cache.read_meta(f)['layouts']):
                print('cached already: %s' % f); continue
            d = build.Doc(f); m = d.meta(); cache.write_meta(f, m)
            for l in m['layouts']:
                for tw in ((True, False) if not l['ps'] else (True,)): cache.write_layout(f, l['i'], tw, d.layout(l['i'], tw))
            cache.prune()
            print('READY (%.0fs, %d layouts): %s' % (time.time() - t, len(m['layouts']), '%s %s' % (os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'bin', 'dwg-viewer')), f)))
        return
    path = os.path.abspath(a.file[0])
    if not os.path.isfile(path):
        sys.exit('dwg-viewer: no such file: %s' % path)
    port = a.port or free_port()
    url = 'http://127.0.0.1:%d/' % port
    if a.hide:
        import urllib.parse
        url += '?hide=' + urllib.parse.quote(a.hide)
    print('serving', path, url, flush=True)
    if not a.no_browser: open_browser(url, a.workspace)
    web.run_app(server.make_app(path, '0' if a.model else a.layout), host='127.0.0.1', port=port, print=None)
