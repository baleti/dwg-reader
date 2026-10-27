import sys, os, time, json, hashlib
sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
from dwgviewer import build, flat as F
import fastflat, progressive
fastflat.install(F)
f = sys.argv[1]
def h(s): s = dict(s); s.pop('build_s', None); s.pop('tl', None); return hashlib.md5(json.dumps(s, sort_keys=True).encode()).hexdigest()
t0 = time.time(); d = build.Doc(f); d.meta(); tp = time.time() - t0
t = time.time(); got = {}; first = None
for i, tw, s in progressive.build_iter(f, d):
    if first is None: first = time.time() - t0
    got[(i, tw)] = h(s)
tall = time.time() - t0
d2 = build.Doc(f); d2.meta(); ref = {(l['i'], tw): h(d2.layout(l['i'], tw)) for l in d2.meta()['layouts'] for tw in ((True, False) if not l['ps'] else (True,))}
print(os.path.basename(f), 'parse %.2f first-scene %.2f all %.2f' % (tp, first, tall), 'IDENTICAL' if got == ref else 'DIFF')
