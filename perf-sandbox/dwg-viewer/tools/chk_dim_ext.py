#!/usr/bin/env python3
"""chk_dim_ext.py STEM... : rows of each DIMENSION picture block versus the AutoCAD DIMENSION extents (dump): drawn box inside or equal to the AutoCAD box within 2 %."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build
for st in sys.argv[1:]:
    dump = json.load(open(os.path.expanduser('~/dwg-research/oracle-out/%s/dump.json' % st)))
    ext = {int(e['h'], 16): e['ext'] for b in dump['blocks'] for e in b.get('entities', []) if e['t'] == 'DIMENSION' and e.get('ext')}
    d = build.Doc(os.path.expanduser('~/dwg-research/corpus/%s.dwg' % st))
    ok = bad = 0; worst = []
    for es in d.sc.by_block.values():
        for e in es:
            if not (e['kind'].startswith('DIM') and e['handle'] in ext): continue
            out = []; d.fl._entity(dict(e), build.Mat(), frozenset(), build.F.Ctx(), 1.0, 0, out)
            xs = []; ys = []
            for p in out:
                if p[0] == 'l': xs += p[5][0::2]; ys += p[5][1::2]
                elif p[0] == 'h':
                    for l in p[3]: xs += l[0::2]; ys += l[1::2]
                elif p[0] == 't': xs.append(p[3]); ys.append(p[4])
            if not xs: bad += 1; continue
            x = ext[e['handle']]; t = (x[0], x[1], x[3], x[4]); m = (min(xs), min(ys), max(xs), max(ys)); tol = 0.02 * max(t[2] - t[0], t[3] - t[1], 1)
            good = m[0] >= t[0] - tol and m[1] >= t[1] - tol and m[2] <= t[2] + tol and m[3] <= t[3] + tol
            ok += good; bad += not good
            if not good and len(worst) < 3: worst.append((hex(e['handle']), [round(v, 1) for v in m], [round(v, 1) for v in t]))
    print('%s dimensions inside the AutoCAD extents: %d, outside/empty: %d %s' % (st, ok, bad, worst))
