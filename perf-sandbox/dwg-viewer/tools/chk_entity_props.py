#!/usr/bin/env python3
"""chk_entity_props.py STEM... : colour index and layer of LINE/ARC/CIRCLE/LWPOLYLINE/INSERT/HATCH/SPLINE entities versus the AutoCAD dump, matched by handle."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build
KINDS = ('LINE', 'ARC', 'CIRCLE', 'LWPOLYLINE', 'INSERT', 'HATCH', 'SPLINE')
for st in sys.argv[1:]:
    dump = json.load(open(os.path.expanduser('~/dwg-research/oracle-out/%s/dump.json' % st)))
    ora = {int(e['h'], 16): (e.get('ci'), e['layer']) for b in dump['blocks'] for e in b.get('entities', []) if e['t'] in KINDS and isinstance(e.get('h'), str)}
    d = build.Doc(os.path.join(os.environ['RWORLD_DIR'], st + '.dwg') if os.environ.get('RWORLD_DIR') else os.path.expanduser('~/dwg-research/corpus/%s.dwg' % st))
    n = c = ly = 0; ex = []
    for es in d.sc.by_block.values():
        for e in es:
            o = ora.get(e['handle'])
            if not o or e['kind'] not in KINDS: continue
            n += 1; c += (e['color'][0] == o[0]) or o[0] is None; ly += e.get('layer') == o[1]
            if e['color'][0] != o[0] and len(ex) < 2: ex.append((e['kind'], e['color'], o[0]))
    print('%s entities %d colour equal %d layer equal %d %s' % (st, n, c, ly, ex))
