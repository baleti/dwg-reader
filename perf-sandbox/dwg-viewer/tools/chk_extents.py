#!/usr/bin/env python3
"""chk_extents.py STEM... : model-space drawn extents (no twist) versus the AutoCAD header EXTMIN/EXTMAX (stale or unset values show as large differences)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build
for stem in sys.argv[1:]:
    d = json.load(open(os.path.expanduser('~/dwg-research/oracle-out/%s/dump.json' % stem)))
    lo, hi = d['header'].get('Extmin'), d['header'].get('Extmax')
    doc = build.Doc(os.path.join(os.environ['RWORLD_DIR'], stem + '.dwg') if os.environ.get('RWORLD_DIR') else os.path.expanduser('~/dwg-research/corpus/%s.dwg' % stem))
    r = doc.layout(0, twist=False)
    ox, oy = doc.origin(); f = [r['full'][0] + ox, r['full'][1] + oy, r['full'][2] + ox, r['full'][3] + oy]
    span = max(hi[0] - lo[0], hi[1] - lo[1], 1e-9)
    err = max(abs(f[0] - lo[0]), abs(f[1] - lo[1]), abs(f[2] - hi[0]), abs(f[3] - hi[1])) / span
    print('%s\tours=%s\tacad=%s\trel_err=%.4f' % (stem, [round(v, 1) for v in f], [round(v, 1) for v in (lo[0], lo[1], hi[0], hi[1])], err))
