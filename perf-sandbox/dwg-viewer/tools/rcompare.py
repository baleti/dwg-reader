#!/usr/bin/env python3
"""rcompare.py OUT.tsv [MAXMB] [LIMIT] [SKIP] : vcompare of every real-world drawing that has AutoCAD plots in ~/dwg-research/oracle-out/<id>/plots (id = census id,
campaign21/census.tsv gives the path). One TSV line per scored layout: id, layout index, version, size MB, aspect ours / oracle, p5, r5 (5 px ink precision / recall).
Ids only, never paths; local use. Each file runs in a subprocess with a time cap."""
import sys, os, csv, glob, json, subprocess
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORA = os.path.expanduser('~/dwg-research/oracle-out')
out_tsv = sys.argv[1]; mx = float(sys.argv[2]) if len(sys.argv) > 2 else 8; limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10 ** 9; skip = int(sys.argv[4]) if len(sys.argv) > 4 else 0
cen = {}
for r in csv.reader(open(os.path.expanduser('~/dwg-research/campaign21/census.tsv')), delimiter='\t'):
    if len(r) >= 5: cen[r[0]] = (r[1], int(r[2]) if r[2].isdigit() else 0, r[4])
ids = sorted(os.path.basename(d.rstrip('/')) for d in glob.glob(os.path.join(ORA, '*/')) if glob.glob(os.path.join(d, 'plots', '*.fixed.pdf')))
ids = [i for i in ids if i in cen and os.path.isfile(cen[i][2]) and cen[i][1] <= mx * 1e6 and cen[i][0].startswith('AC10') and cen[i][0] >= 'AC1009'][skip:skip + limit]
WORK = r'''
import sys, os, json, glob
sys.path.insert(0, %r); sys.path.insert(0, %r)
import vcompare
from dwgviewer import build
path, id_ = sys.argv[1], sys.argv[2]
d = build.Doc(path)
names = {os.path.basename(p)[:-len('.fixed.pdf')] for p in glob.glob(os.path.join(%r, id_, 'plots', '*.fixed.pdf'))}
done = 0
for li, l in enumerate(d.layout_list()):
    if l['name'].replace(' ', '_') in names and done < 2:
        os.environ['VC_FIT'] = 'bounds' if li == 0 else 'full'
        try:
            r = vcompare.run(path, li, out=sys.argv[3])
            print('ROW', json.dumps([id_, li, r['aspect_ours'], r['aspect_oracle'], r['p5'], r['r5']]), flush=True)
        except BaseException as ex:
            print('ROW', json.dumps([id_, li, 'ERR', str(ex)[:60]]), flush=True)
        done += 1
''' % (os.path.join(HERE, 'tools'), HERE, ORA)
os.makedirs('/tmp/rcompare', exist_ok=True)
with open(out_tsv, 'a') as fo:
    for i in ids:
        mag, size, path = cen[i]
        try:
            p = subprocess.run([sys.executable, '-c', WORK, path, i, '/tmp/rcompare'], capture_output=True, text=True, timeout=900)
            rows = [l[4:] for l in p.stdout.splitlines() if l.startswith('ROW ')]
        except subprocess.TimeoutExpired:
            rows = [json.dumps([i, -1, 'TIMEOUT'])]
        for r in rows:
            v = json.loads(r); fo.write('\t'.join(str(x) for x in [v[0], v[1], mag, round(size / 1e6, 1)] + v[2:]) + '\n'); fo.flush()
        if not rows: fo.write('%s\t-\t%s\t%.1f\tnorow\n' % (i, mag, size / 1e6)); fo.flush()
