import sys, os, cProfile, pstats, io
sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
from dwgviewer import build, flat as F
import fastflat; fastflat.install(F)
d = build.Doc(sys.argv[1]); m = d.meta()
pr = cProfile.Profile(); pr.enable()
for l in m['layouts']:
    for tw in ((True, False) if not l['ps'] else (True,)): d.layout(l['i'], tw)
pr.disable(); s = io.StringIO(); ps = pstats.Stats(pr, stream=s); ps.sort_stats('cumulative').print_stats('flat.py|dwgmodel|dwgent|dwgscene|fastflat'); print('\n'.join(s.getvalue().splitlines()[6:30]))
