#!/usr/bin/env python3
"""chk_vports.py STEM... : compare our decoded paper-space viewports (centre, size, view centre/height, twist, frozen layer set size) with the AutoCAD dump. Matches by centre+width."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build
ORA = os.path.expanduser('~/dwg-research/oracle-out'); COR = os.path.expanduser('~/dwg-research/corpus')
tot = bad = 0
for stem in sys.argv[1:]:
    d = json.load(open('%s/%s/dump.json' % (ORA, stem)))
    ov = []
    for b in d['blocks']:
        for e in b.get('entities', []):
            if e['t'] == 'VIEWPORT': ov.append(e)
    doc = build.Doc('%s/%s.dwg' % (COR, stem))
    for lay in doc.lays:
        if lay['name'].lower() == 'model': continue
        for v, frozen in doc._viewports(lay):
            m = next((o for o in ov if abs(o['c'][0] - v['center'][0]) < 1e-3 and abs(o['c'][1] - v['center'][1]) < 1e-3 and abs(o['w'] - v['width']) < 1e-3), None)
            tot += 1
            if not m: bad += 1; print(stem, lay['name'], 'NO MATCH', v['center'][:2], v['width']); continue
            errs = []
            if abs(m['vh'] - v['view_height']) > 1e-6 * max(1, m['vh']): errs.append('vh %s vs %s' % (m['vh'], v['view_height']))
            if abs(m['vc'][0] - v['view_center'][0]) > 1e-4 or abs(m['vc'][1] - v['view_center'][1]) > 1e-4: errs.append('vc %s vs %s' % (m['vc'], v['view_center']))
            if abs(m.get('twist', 0) - v['twist']) > 1e-6: errs.append('twist')
            if len(m['frozen']) != len(frozen): errs.append('frozen %d vs %d' % (len(m['frozen']), len(frozen)))
            if abs(m['scale'] - v['height'] / v['view_height']) > 1e-6 * max(1, m['scale']): errs.append('scale %s vs %s' % (m['scale'], v['height'] / v['view_height']))
            if m.get('nonrect') and not v.get('clip_poly'): errs.append('NONRECT clip missing')
            if errs: bad += 1; print(stem, lay['name'], errs)
print('viewports', tot, 'with differences', bad)
