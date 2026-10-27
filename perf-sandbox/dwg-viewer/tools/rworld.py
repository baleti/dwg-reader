#!/usr/bin/env python3
"""rworld.py ID... : numeric check of real-world drawings (campaign21 census / sample ids, AutoCAD dump in ~/dwg-research/oracle-out/<id>) against the viewer:
layer flags (on / frozen / locked / plot), paper-space viewport numbers (centre, size, view, frozen count) and model-space entity counts by kind.
One summary line per id (ids only, never paths); local use."""
import sys, os, json, csv, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build
ORA = os.path.expanduser('~/dwg-research/oracle-out')
cen = {}
for f in ('census.tsv', 'sample.tsv'):
    for r in csv.reader(open(os.path.expanduser('~/dwg-research/campaign21/' + f)), delimiter='\t'):
        if len(r) >= 5: cen.setdefault(r[0], r)
KIND = {'POLYLINE': 'LWPOLYLINE', 'DIMENSION': 'DIM'}
for id_ in sys.argv[1:]:
    try:
        dump = json.load(open('%s/%s/dump.json' % (ORA, id_))); d = build.Doc(os.path.join(os.environ['RWORLD_DIR'], id_ + '.dwg') if os.environ.get('RWORLD_DIR') else cen[id_][4]); res = [id_]
        L = {l['name']: l for l in dump['layers']}; n = bad = 0
        for l in d.meta()['layers']:
            o = L.get(l['n'])
            if not o: continue
            n += 1
            if bool(l['off']) != bool(o.get('IsOff')) or bool(l['frz']) != bool(o.get('IsFrozen')) or bool(l['lock']) != bool(o.get('IsLocked')) or bool(l['plot']) != bool(o.get('IsPlottable', True)): bad += 1
        res.append('layers %d/%d' % (n - bad, n))
        ov = [e for b in dump['blocks'] for e in b.get('entities', []) if e['t'] == 'VIEWPORT']
        tot = vb = 0
        for lay in d.lays:
            if lay['name'].lower() == 'model': continue
            for v, frozen in d._viewports(lay):
                tot += 1
                ok = any(abs(o['c'][0] - v['center'][0]) < 1e-3 and abs(o['c'][1] - v['center'][1]) < 1e-3 and abs(o['w'] - v['width']) < 1e-3 and abs(o['vh'] - v['view_height']) <= 1e-6 * max(1, o['vh'])
                         and abs(o['vc'][0] - v['view_center'][0]) < 1e-4 and abs(o['scale'] - v['height'] / v['view_height']) <= 1e-6 * max(1, o['scale']) for o in ov)    # layouts can share a rectangle: any dump viewport with all numbers equal
                if not ok: vb += 1
        res.append('viewports %d/%d' % (tot - vb, tot))
        mb = next((b for b in dump['blocks'] if (b.get('name') or '').lower() == '*model_space'), None)
        if mb:
            norm = lambda k: 'DIMENSION' if k.startswith('DIM_') else 'POLYLINE' if k in ('POLYLINE2D', 'POLYLINE3D') else k
            ours = collections.Counter(norm(e['kind']) for e in d.sc.block_content(d.model_name) if e['kind'] not in ('VERTEX2D', 'VERTEX3D', 'SEQEND', 'ATTRIB'))
            theirs = collections.Counter({k: v for k, v in mb['entity_counts'].items() if k not in ('ATTRIB',)})
            diff = {k: (ours.get(k, 0), theirs.get(k, 0)) for k in set(ours) | set(theirs) if ours.get(k, 0) != theirs.get(k, 0)}
            res.append('model kinds equal' if not diff else 'model diffs %s' % dict(list(diff.items())[:4]))
        print('\t'.join(res), flush=True)
    except BaseException as ex:
        print(id_, 'ERR', repr(ex)[:80], flush=True)
