import sys, os, cProfile, pstats, io
sys.path.insert(0, os.path.expanduser('~/dwg-viewer'))
from dwgviewer import build
pr = cProfile.Profile(); pr.enable(); d = build.Doc(sys.argv[1]); d.meta(); pr.disable()
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats('tottime').print_stats(10); print('\n'.join(s.getvalue().splitlines()[6:20]))
