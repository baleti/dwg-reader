"""parity + time: stock Python build vs fastflat-patched build, per layout, canonical JSON compare (sort_keys, no build_s)"""
import sys, os, time, json, hashlib
sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
from dwgviewer import build, flat as F
import fastflat
f = sys.argv[1]
def run():
    d = build.Doc(f); m = d.meta(); t = time.time(); out = {}
    for l in m['layouts']:
        for tw in ((True, False) if not l['ps'] else (True,)):
            s = d.layout(l['i'], tw); s.pop('build_s', None); out[(l['i'], tw)] = hashlib.md5(json.dumps(s, sort_keys=True).encode()).hexdigest()
    return time.time() - t, out
ta, a = run()
orig = fastflat.install(F)
tb, b = run()
print(os.path.basename(f), 'python %.2f' % ta, 'rust-flatten %.2f' % tb, '%.2fx' % (ta / tb), 'IDENTICAL' if a == b else 'DIFF %s' % [k for k in a if a[k] != b.get(k)])
