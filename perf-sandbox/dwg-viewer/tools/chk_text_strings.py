#!/usr/bin/env python3
"""chk_text_strings.py STEM... : TEXT/MTEXT strings of the scene versus the AutoCAD dump (matched by insertion point and block), plain text after removing MTEXT codes."""
import sys, os, re, json, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build


def plain(t):
    t = t.replace('\\P', '\n').replace('\r\n', '\n').replace('\r', '\n')
    t = re.sub(r'\\[pP][^;]*;', '', t)
    t = re.sub(r'\\[A-Za-z][^;\\]*;', '', t)
    t = re.sub(r'\\[LlOoKk~]|[{}]', '', t)
    return t.replace('%%c', 'Ø').replace('%%d', '°').replace('%%p', '±').strip()


for st in sys.argv[1:]:
    dump = json.load(open(os.path.expanduser('~/dwg-research/oracle-out/%s/dump.json' % st)))
    ora = collections.defaultdict(list)
    for b in dump['blocks']:
        for e in b.get('entities', []):
            if e['t'] in ('TEXT', 'MTEXT') and e.get('p'): ora[(e['t'], round(e['p'][0], 2), round(e['p'][1], 2))].append(plain(e.get('s') or ''))
    d = build.Doc(os.path.expanduser('~/dwg-research/corpus/%s.dwg' % st))
    n = ok = 0; ex = []
    for es in d.sc.by_block.values():
        for e in es:
            if e['kind'] not in ('TEXT', 'MTEXT'): continue
            pt = e.get('ins') if e['kind'] == 'MTEXT' else (e.get('ins') or e.get('align'))
            cand = ora.get((e['kind'], round(pt[0], 2), round(pt[1], 2)))
            if not cand: continue
            n += 1
            mine = plain(e.get('text') or '')
            if mine in cand: ok += 1
            elif len(ex) < 3: ex.append((mine[:30], cand[0][:30]))
    print('%s matched %d equal %d (%.1f%%) %s' % (st, n, ok, 100 * ok / max(n, 1), ex))
