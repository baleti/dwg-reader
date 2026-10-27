import sys, os, time, collections
sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
from dwgviewer import build, flat as F
import fastflat; fastflat.install(F)
T = collections.Counter(); N = collections.Counter()
oe = F.Flattener._entity
def ent(self, e, *a):
    t = time.perf_counter()
    try: return oe(self, e, *a)
    finally: T[e['kind']] += time.perf_counter() - t; N[e['kind']] += 1
F.Flattener._entity = ent
d = build.Doc(sys.argv[1]); m = d.meta()
for l in m['layouts']:
    for tw in ((True, False) if not l['ps'] else (True,)): d.layout(l['i'], tw)
for k, v in T.most_common(8): print(k, N[k], '%.2fs (inclusive of nested INSERT content)' % v)
