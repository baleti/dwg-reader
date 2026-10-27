import sys, os, collections
sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
from dwgviewer import build, flat as F
import fastflat; fastflat.install(F)
C = collections.Counter(); o1 = F.Flattener._one
def one(self, e, *a): C[e['kind']] += 1; return o1(self, e, *a)
F.Flattener._one = one
d = build.Doc(sys.argv[1]); m = d.meta()
for l in m['layouts']:
    for tw in ((True, False) if not l['ps'] else (True,)): d.layout(l['i'], tw)
print(os.path.basename(sys.argv[1]), C.most_common(8))
