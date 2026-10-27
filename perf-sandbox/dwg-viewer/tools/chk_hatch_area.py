#!/usr/bin/env python3
"""chk_hatch_area.py STEM... : hatch boundary area of our flattened loops (largest loop minus the others, even-odd approximation) versus the AutoCAD dump 'area', per hatch."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build, flat


def poly_area(l):
    a = 0
    for i in range(0, len(l), 2):
        j = (i + 2) % len(l); a += l[i] * l[j + 1] - l[j] * l[i + 1]
    return a / 2


def inside(pt, l):
    x, y = pt; c = False
    n = len(l) // 2
    for i in range(n):
        x1, y1 = l[2 * i], l[2 * i + 1]; x2, y2 = l[2 * ((i + 1) % n)], l[2 * ((i + 1) % n) + 1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def evenodd_area(loops):
    areas = [abs(poly_area(l)) for l in loops]
    tot = 0.0
    for i, l in enumerate(loops):
        depth = sum(1 for j, m in enumerate(loops) if j != i and areas[j] > areas[i] and inside((l[0], l[1]), m))
        tot += areas[i] * (1 if depth % 2 == 0 else -1)
    return tot


tot = ok = 0
for stem in sys.argv[1:]:
    d = json.load(open(os.path.expanduser('~/dwg-research/oracle-out/%s/dump.json' % stem)))
    orc = {}
    for b in d['blocks']:
        for e in b.get('entities', []):
            if e['t'] == 'HATCH' and e.get('area') is not None:
                try: orc[int(str(e['h']), 16)] = e['area']
                except Exception: pass
    doc = build.Doc(os.path.join(os.environ['RWORLD_DIR'], stem + '.dwg') if os.environ.get('RWORLD_DIR') else os.path.expanduser('~/dwg-research/corpus/%s.dwg' % stem))
    n = g = 0; bad = []
    for es in doc.sc.by_block.values():
        for e in es:
            if e['kind'] == 'HATCH' and e['handle'] in orc and orc[e['handle']] > 0:
                out = []
                try: doc.fl._entity(dict(e, layer='0', invis=0), flat.Mat(), frozenset(), flat.Ctx(), 1.0, 0, out)
                except Exception: continue
                hs = [p for p in out if p[0] == 'h']
                if not hs: continue
                ar = hs[0][3]
                ours = evenodd_area(hs[0][3])
                n += 1; good = abs(orc[e['handle']] - ours) / orc[e['handle']] < 0.03; g += good
                if not good and len(bad) < 3: bad.append((e['handle'], round(orc[e['handle']], 1), round(ours, 1), len(ar)))
    print('%s hatches %d area within 3%%: %d %s' % (stem, n, g, bad)); tot += n; ok += g
print('total', tot, 'ok', ok)
