import sys, os, time
sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
from dwgviewer import build, flat as F
import fastflat, dwgscene_fast as R
fastflat.install(F)
d = build.Doc(sys.argv[1]); m = d.meta()
prims = d.fl.flatten(d.model_name)
bxs = []; bys = []
def bb(x, y, g=True): bxs.append(x); bys.append(y)
bb.many = lambda xs, ys: (bxs.extend(xs), bys.extend(ys))
t = time.time(); ref = [d._row(p, bb) for p in prims]; tp = time.time() - t
t = time.time(); items, xs, ys = R.rows_batch(prims, d.lidx); tr = time.time() - t
fb = [i for i, it in enumerate(items) if isinstance(it, int)]
t = time.time()
bx2 = []; by2 = []
def bbb(x, y, g=True): bx2.append(x); by2.append(y)
bbb.many = lambda a, b: (bx2.extend(a), by2.extend(b))
for i in fb: items[i] = d._row(prims[i], bbb)
tf = time.time() - t
ok = items == ref and sorted(bxs) == sorted(bx2 + xs) and sorted(bys) == sorted(by2 + ys)
import json
ok = ok and json.dumps(items) == json.dumps(ref)
print(os.path.basename(sys.argv[1]), len(prims), 'prims; python _row %.3fs, rust %.3fs + %d python fallbacks %.3fs' % (tp, tr, len(fb), tf), 'IDENTICAL' if ok else 'DIFF')
