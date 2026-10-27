#!/usr/bin/env python3
"""rsweep.py CENSUS.tsv N [SEED] [MAXMB] : build every layout (no browser) of N random drawings of the census (id, magic, size, source, path) and print
one TSV line per file with the id only (never the path): id, magic, MB, status, layouts, prims, errors, max layout s. Each file runs in a subprocess with a time and memory cap."""
import sys, os, random, subprocess, json, resource
census, n = sys.argv[1], int(sys.argv[2]); seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1; mx = float(sys.argv[4]) if len(sys.argv) > 4 else 6
rows = [l.rstrip('\n').split('\t') for l in open(census)][1:]
rows = [r for r in rows if r[1].startswith('AC10') and r[1] >= 'AC1015' and int(r[2]) <= mx * 1e6 and os.path.isfile(r[4])]
random.Random(seed).shuffle(rows)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE = r'''
import sys, time, json
sys.path.insert(0, %r)
from dwgviewer import build
t = time.time(); d = build.Doc(sys.argv[1]); pt = time.time() - t
tot = er = 0; mxs = 0
for i in range(len(d.lays)):
    t = time.time(); r = d.layout(i); mxs = max(mxs, time.time() - t); tot += len(r['prims']) + len(r['mprims']); er += r.get('errors', 0)
print(json.dumps({'layouts': len(d.lays), 'prims': tot, 'errors': er, 'max_s': round(mxs, 1), 'parse_s': round(pt, 1)}))
''' % HERE
print('id\tmagic\tMB\tstatus\tlayouts\tprims\terrors\tmax_layout_s\tparse_s', flush=True)
for r in rows[:n]:
    try:
        p = subprocess.run([sys.executable, '-c', CODE, r[4]], capture_output=True, text=True, timeout=300,
                           preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_AS, (3 << 30, 3 << 30)))
        if p.returncode == 0:
            j = json.loads(p.stdout.strip().splitlines()[-1]); print('\t'.join(map(str, [r[0], r[1], round(int(r[2]) / 1e6, 1), 'ok', j['layouts'], j['prims'], j['errors'], j['max_s'], j['parse_s']])), flush=True)
        else:
            e = (p.stderr.strip().splitlines() or ['?'])[-1][:90]; print('\t'.join([r[0], r[1], str(round(int(r[2]) / 1e6, 1)), 'FAIL ' + e]), flush=True)
    except subprocess.TimeoutExpired:
        print('\t'.join([r[0], r[1], str(round(int(r[2]) / 1e6, 1)), 'TIMEOUT']), flush=True)
