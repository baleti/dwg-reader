import sys, os, json
sys.path.insert(0, os.path.expanduser('~/dwg-viewer'))
from dwgviewer import build
f = sys.argv[1]
d = build.Doc(f); m = d.meta()
J = [(l['i'], tw) for l in m['layouts'] for tw in ((True, False) if not l['ps'] else (True,))]
ser = {j: d.layout(*j) for j in J}
for j in J:
    e = build.Doc(f); e.meta(); s = e.layout(*j)   # fresh Doc per job (what a forked child sees)
    bad = [k for k in set(s) | set(ser[j]) if k != 'build_s' and json.dumps(s.get(k)) != json.dumps(ser[j].get(k))]
    print(j, 'differs in', bad, 'tl subset of serial' if all(ser[j]['tl'].get(k) == v for k, v in s['tl'].items()) else 'tl CONFLICT', len(s['tl']), len(ser[j]['tl']))
