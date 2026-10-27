#!/usr/bin/env python3
"""chk_hatch_ext.py STEM... : bounding box of every HATCH our flattener builds versus the AutoCAD dump 'ext' (matched by handle, block-space coordinates)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build, flat
tot = bad = 0
for stem in sys.argv[1:]:
    d = json.load(open(os.path.expanduser('~/dwg-research/oracle-out/%s/dump.json' % stem)))
    orc = {}
    for b in d['blocks']:
        for e in b.get('entities', []):
            if e['t'] == 'HATCH' and e.get('ext'):
                try: orc[int(str(e['h']), 16)] = e['ext']
                except Exception: pass
    doc = build.Doc(os.path.expanduser('~/dwg-research/corpus/%s.dwg' % stem))
    nb = 0
    for es in doc.sc.by_block.values():
        for e in es:
            if e['kind'] != 'HATCH' or e['handle'] not in orc: continue
            out = []
            try: doc.fl._entity(dict(e, layer='0', invis=0), flat.Mat(), frozenset(), flat.Ctx(), 1.0, 0, out)
            except Exception: pass
            hs = [p for p in out if p[0] == 'h']
            if not hs: nb += 1; tot += 1; bad += 1; continue
            xs = [v for l in hs[0][3] for v in l[0::2]]; ys = [v for l in hs[0][3] for v in l[1::2]]
            o = orc[e['handle']]; span = max(o[3] - o[0], o[4] - o[1], 1e-9)
            err = max(abs(min(xs) - o[0]), abs(min(ys) - o[1]), abs(max(xs) - o[3]), abs(max(ys) - o[4])) / span
            tot += 1
            if err > 0.01: nb += 1; bad += 1
    print('%s hatches off by >1%%: %d' % (stem, nb))
print('hatches checked', tot, 'bad', bad)
