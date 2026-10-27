#!/usr/bin/env python3
"""chk_curve_ext.py STEM... : bounding box of the polylines our flattener builds for LINE/ARC/CIRCLE/ELLIPSE/SPLINE/LWPOLYLINE/POLYLINE entities versus the AutoCAD dump 'ext' (block-space coordinates, matched by handle)."""
import sys, os, json
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build, flat

KINDS = ('INSERT', 'LINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE', 'LWPOLYLINE', 'POLYLINE2D', 'POLYLINE3D', 'SOLID')
tot = defaultdict(lambda: [0, 0]); worst = []
for stem in sys.argv[1:]:
    d = json.load(open(os.path.expanduser('~/dwg-research/oracle-out/%s/dump.json' % stem)))
    orc = {}
    for b in d['blocks']:
        for e in b.get('entities', []):
            if e.get('ext') and e['t'] in ('INSERT', 'LINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE', 'LWPOLYLINE', 'POLYLINE', 'SOLID'):
                try: orc[int(str(e['h']), 16)] = e['ext']
                except Exception: pass
    doc = build.Doc(os.path.join(os.environ['RWORLD_DIR'], stem + '.dwg') if os.environ.get('RWORLD_DIR') else os.path.expanduser('~/dwg-research/corpus/%s.dwg' % stem))
    TEXTY = ('TEXT', 'MTEXT', 'ATTRIB', 'IMAGE', 'ATTDEF')
    _memo = {}

    def has_text(owner, depth=0):    # AutoCAD's extents of an INSERT include its text and attribute extents, which this check does not model
        if owner in _memo: return _memo[owner]
        r = False
        if depth < 6:
            for x in doc.fl.by_owner.get(owner, []):
                if x['kind'] in TEXTY or x['kind'].startswith('DIM'): r = True; break
                if x['kind'] == 'INSERT':
                    bh = doc.fl.block_handle(x)
                    if bh is not None and has_text(bh, depth + 1): r = True; break
        _memo[owner] = r
        return r
    for es in doc.sc.by_block.values():
        for e in es:
            if e['kind'] not in KINDS or e['handle'] not in orc: continue
            if e['kind'] == 'INSERT':
                bh = doc.fl.block_handle(e)
                if bh is None or has_text(bh) or e.get('hasattribs'): continue
            out = []
            try: doc.fl._entity(dict(e, layer='0', invis=0), flat.Mat(), frozenset(), flat.Ctx(), 1.0, 0, out)
            except Exception: continue
            rows = [p for p in out if p[0] in 'lh' and not (p[0] == 'h' and p[4].get('wipe'))]
            if not rows: continue
            xs = []; ys = []
            for p in rows:
                if p[0] == 'l': xs += p[5][0::2]; ys += p[5][1::2]
                else:
                    for l in p[3]: xs += l[0::2]; ys += l[1::2]
            o = orc[e['handle']]; span = max(o[3] - o[0], o[4] - o[1], 1e-9)
            err = max(abs(min(xs) - o[0]), abs(min(ys) - o[1]), abs(max(xs) - o[3]), abs(max(ys) - o[4])) / span
            if e['kind'] == 'SPLINE' and err >= 0.01 and e.get('ctrl'):   # AutoCAD's extents of a spline are its control polygon hull
                hx = [c[0] for c in e['ctrl']]; hy = [c[1] for c in e['ctrl']]
                err = min(err, max(abs(min(hx) - o[0]), abs(min(hy) - o[1]), abs(max(hx) - o[3]), abs(max(hy) - o[4])) / span)
            t = tot[e['kind']]; t[0] += 1; t[1] += err < 0.01
            if err >= 0.01 and len(worst) < 8: worst.append((stem[:11], e['kind'], e['handle'], round(err, 3)))
for k, (n, g) in sorted(tot.items()): print('%-11s %6d within 1%% of AutoCAD extents: %6d (%.2f%%)' % (k, n, g, 100 * g / max(n, 1)))
for w in worst: print('  off', w)
