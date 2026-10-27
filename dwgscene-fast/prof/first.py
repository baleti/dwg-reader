import sys, os, time
sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
from dwgviewer import build, flat as F
import fastflat
if os.environ.get('FAST'): fastflat.install(F)
t = time.time(); d = build.Doc(sys.argv[1]); m = d.meta(); t1 = time.time() - t
dl = m['default']; 
t = time.time(); d.layout(dl if isinstance(dl, int) else 0, True); print(os.environ.get('FAST', 'py'), 'default layout', dl, 'parse+meta %.2f' % t1, 'first layout %.2f' % (time.time() - t), 'cold-first %.2f' % (t1 + time.time() - t))
