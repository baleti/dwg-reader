#!/usr/bin/env python3
"""smoke.py FILE.dwg : headless server smoke test (no browser): main page, meta, every layout JSON must load and be non-error."""
import sys, os, json, time, socket, subprocess, urllib.request, gzip
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
p = subprocess.Popen([sys.executable, '-m', 'dwgviewer', sys.argv[1], '--no-browser', '--port', str(port)], cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    base = 'http://127.0.0.1:%d' % port
    for _ in range(int(os.environ.get("SMOKE_WAIT", "120")) * 2):
        try:
            m = json.load(urllib.request.urlopen(base + '/api/meta'))
            if not m.get('loading'): break
        except Exception: pass
        time.sleep(0.5)
    assert "error" not in m, m   # (m is set once the server answered; SMOKE_WAIT seconds, default 120)
    assert b'<canvas' in urllib.request.urlopen(base + '/').read()
    for f in ('app.js', 'style.css', 'fonts/LiberationSans-Regular.ttf'): urllib.request.urlopen(base + '/' + f).read()
    for l in m['layouts']:
        resp = urllib.request.urlopen('%s/api/layout/%d' % (base, l['i'])); raw = resp.read()
        if resp.headers.get('Content-Encoding') == 'gzip': raw = gzip.decompress(raw)
        r = json.loads(raw)
        assert 'prims' in r, r
        assert r['errors'] == 0, 'entity errors: %d' % r['errors']
        print('layout %-14s prims=%d vps=%d errors=%d %.1fs' % (l['name'], r['n'], len(r['vps']), r['errors'], r['build_s']))
    print('SMOKE OK', m['file'])
finally:
    p.terminate()
