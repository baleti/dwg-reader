#!/usr/bin/env python3
"""chk_acis_ext.py STEM... : plan-view wireframes (parser dwgacis) of REGION/3DSOLID/BODY versus the AutoCAD dump: bounding box vs 'ext' (R2000 solids), edge length sum vs Perimeter (REGIONs)."""
import sys, os, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgacis
from dwgviewer import build
n = ok = 0
for stem in sys.argv[1:]:
    d = json.load(open(os.path.expanduser('~/dwg-research/oracle-out/%s/dump.json' % stem)))
    allr = {int(str(e['h']), 16): e for b in d['blocks'] for e in b.get('entities', []) if e['t'] in ('3DSOLID', 'REGION', 'BODY')}
    doc = build.Doc(os.path.expanduser('~/dwg-research/corpus/%s.dwg' % stem))
    for h, o in doc.m.objs.items():
        if o.type not in (37, 38, 39) or h not in allr: continue
        e = build.dwgmodel.ENT_DECODERS[o.type](o)
        pr = dwgacis.parse(e); w = dwgacis.wire(pr[1]) if pr else []
        pts = [q for pl in w for q in pl]; o_ = allr[h]
        if not pts: print('%s %X no edges' % (stem, h)); n += 1; continue
        if o_.get('Perimeter') and o.ver not in ('AC1015', 'AC1014', 'AC1012'):
            per = sum(math.dist(a, b) for pl in w for a, b in zip(pl, pl[1:])); n += 1; ok += abs(per / o_['Perimeter'] - 1) < 1e-3
            print('%s %X perimeter ratio %.4f' % (stem, h, per / o_['Perimeter']))
        elif o_.get('ext'):
            x = o_['ext']; mine = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
            err = max(abs(a - b) for a, b in zip(mine, (x[0], x[1], x[3], x[4]))); n += 1; ok += err < 0.5
            print('%s %X %s maxerr %.3f' % (stem, h, e['kind'], err))
print('ok: %d / %d' % (ok, n))
