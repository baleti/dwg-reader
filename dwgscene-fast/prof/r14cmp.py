import sys, os, time, json
sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
import dwgbits
from dwgviewer import build
f = sys.argv[1]
def run():
    t = time.time(); d = build.Doc(f); m = d.meta(); t1 = time.time() - t
    ents = json.dumps({str(k): v for k, v in d.sc.by_block.items()}, default=repr, sort_keys=True)
    return t1, hash(ents), len(ents)
a = run()
import dwgscene_fast as R
dwgbits.Bits = R.Bits
b = run()
print(os.path.basename(f), 'python parse+meta %.2f' % a[0], 'rust Bits %.2f' % b[0], '%.2fx' % (a[0] / b[0]), 'IDENTICAL' if a[1:] == b[1:] else 'DIFF')
