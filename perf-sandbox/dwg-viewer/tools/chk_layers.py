#!/usr/bin/env python3
"""chk_layers.py STEM... : layer table of the viewer (colour, on/off, frozen, locked, plot, lineweight, linetype) versus the AutoCAD dump."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build
tot = {}
for st in sys.argv[1:]:
    dump = json.load(open(os.path.expanduser('~/dwg-research/oracle-out/%s/dump.json' % st)))
    L = {l['name']: l for l in dump['layers']}
    d = build.Doc(os.path.expanduser('~/dwg-research/corpus/%s.dwg' % st))
    bad = {}; n = 0
    for l in d.meta()['layers']:
        o = L.get(l['n'])
        if not o: continue
        n += 1
        c = o.get('Color') or {}
        chk = {'off': bool(l['off']) == bool(o.get('IsOff')), 'frozen': bool(l['frz']) == bool(o.get('IsFrozen')), 'locked': bool(l['lock']) == bool(o.get('IsLocked')),
               'plot': bool(l['plot']) == bool(o.get('IsPlottable', True))}
        lw = str(o.get('LineWeight') or '')
        if lw.startswith('LineWeight') and lw[10:].isdigit(): chk['lineweight'] = abs((l['lw'] or 0) - int(lw[10:]) / 100) < 0.006
        ltn = (o.get('LinetypeObjectId') or {}).get('n')
        if ltn: chk['linetype'] = (l['lt'] or '').lower() == ltn.lower()
        if c.get('method') == 'ByAci': chk['aci'] = (l['c'] == c.get('index')) or isinstance(l['c'], list)
        for k, v in chk.items():
            if not v: bad.setdefault(k, []).append(l['n'])
    print('%s layers %d mismatches %s' % (st, n, {k: (len(v), v[:2]) for k, v in bad.items()}))
