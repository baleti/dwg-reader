import sys, os, json
sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
from dwgviewer import build, flat as F
import fastflat
f = sys.argv[1]
d = build.Doc(f); m = d.meta(); a = d.layout(0, True)
fastflat.install(F)
d2 = build.Doc(f); d2.meta(); b = d2.layout(0, True)
for k in a:
    if k != 'build_s' and json.dumps(a[k], sort_keys=True) != json.dumps(b[k], sort_keys=True): print('key', k)
for i, (x, y) in enumerate(zip(a['prims'], b['prims'])):
    if x != y: print(i, str(x)[:300]); print(i, str(y)[:300]); break
print(len(a['prims']), len(b['prims']))
