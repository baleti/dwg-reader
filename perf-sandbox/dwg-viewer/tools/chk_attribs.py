#!/usr/bin/env python3
"""chk_attribs.py STEM... : block attributes: number of ATTRIBs per INSERT and their text/insertion points versus the AutoCAD dump (INSERT.attrs)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build
tot = cnt_ok = txt_ok = pos_ok = n_att = 0
for stem in sys.argv[1:]:
    d = json.load(open(os.path.expanduser('~/dwg-research/oracle-out/%s/dump.json' % stem)))
    orc = {}
    for b in d['blocks']:
        for e in b.get('entities', []):
            if e['t'] == 'INSERT' and e.get('attrs'):
                try: orc[int(str(e['h']), 16)] = e['attrs']
                except Exception: pass
    doc = build.Doc(os.path.expanduser('~/dwg-research/corpus/%s.dwg' % stem))
    fl = doc.fl
    for es in doc.sc.by_block.values():
        for e in es:
            if e['kind'] != 'INSERT' or e['handle'] not in orc: continue
            ours = fl.attribs.get(e['handle'], []); theirs = orc[e['handle']]
            tot += 1; cnt_ok += (len(ours) == len(theirs))
            tg = {a.get('tag'): a for a in theirs}
            for a in ours:
                o = tg.get(a.get('tag'))
                if not o: continue
                n_att += 1
                txt_ok += (str(o.get('s', '')) == str(a.get('text', '')))
                op = o.get('p'); ip = a.get('ins')    # the dump reports the first (insertion) point
                if op and ip and abs(op[0] - ip[0]) < 1e-3 * max(1, abs(op[0])) and abs(op[1] - ip[1]) < 1e-3 * max(1, abs(op[1])): pos_ok += 1
    print(stem, 'inserts with attributes', tot)
print('attribute count equal: %d/%d ; matched attributes %d: text equal %d, position equal %d' % (cnt_ok, tot, n_att, txt_ok, pos_ok))
