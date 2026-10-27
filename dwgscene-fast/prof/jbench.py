import sys, os, time, json
sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
from dwgviewer import build
import dwgscene_fast as R
d = build.Doc(sys.argv[1]); m = d.meta()
for l in m['layouts']:
    s = d.layout(l['i'], True)
    t = time.time(); a = json.dumps(s, separators=(',', ':')).encode(); tp = time.time() - t
    t = time.time(); b = R.dumps(s); tr = time.time() - t
    print(os.path.basename(sys.argv[1]), 'layout', l['i'], '%.1f MB' % (len(a) / 1e6), 'py %.2fs rust %.2fs' % (tp, tr), 'IDENTICAL' if a == b else 'DIFF')
