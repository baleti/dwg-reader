#!/usr/bin/env python3
"""vqa_agg.py [vqa.jsonl] : aggregate scores (p5a/r5a) per version and per Model / paper layout, list the worst views. Aggregate output only."""
import sys, os, json, collections
f = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/dwg-research/qa/out/vqa.jsonl')
last = {}
for l in open(f):
    r = json.loads(l); last[(r['stem'], r['li'])] = r
rs = list(last.values())
ok = [r for r in rs if 'p5a' in r]; bad = [r for r in rs if 'p5a' not in r]
def stat(rows):
    if not rows: return '-'
    p = sorted(r['p5a'] for r in rows); q = sorted(r['r5a'] for r in rows)
    return 'n=%d meanP=%.3f meanR=%.3f P>=.95:%d%% R>=.95:%d%% bad(<.85 either):%d%%' % (len(rows), sum(p)/len(p), sum(q)/len(q), 100*sum(x>=.95 for x in p)//len(p), 100*sum(x>=.95 for x in q)//len(q), 100*sum(r['p5a']<.85 or r['r5a']<.85 for r in rows)//len(rows))
print('views: %d scored, %d errors' % (len(ok), len(bad)))
for k in ('model', 'paper'):
    rows = [r for r in ok if (r['model'] == (k == 'model'))]
    print(k, stat(rows))
    by = collections.defaultdict(list)
    for r in rows: by[r['version']].append(r)
    for v in sorted(by): print('  ', v, stat(by[v]))
print('errors:', dict(collections.Counter(r['err'][:50] for r in bad)))
print('worst:')
for r in sorted(ok, key=lambda r: r['p5a'] + r['r5a'])[:25]: print('  %s L%d p=%.3f r=%.3f' % (r['stem'], r['li'], r['p5a'], r['r5a']))
