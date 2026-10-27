#!/usr/bin/env python3
"""bsweep.py CORPUS_DIR : build every layout of every .dwg (no browser) and report timing/size/errors as TSV. Heavy: run on host1."""
import sys, os, time, json, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import build
print('file\tver\tMB\tparse_s\tlayouts\tprims_total\tmax_layout_s\tjson_MB\terrors\tstatus', flush=True)
for f in sorted(glob.glob(os.path.join(sys.argv[1], '*.dwg'))):
    ver = open(f, 'rb').read(6).decode('latin1')
    if ver == 'AC1021' or ver < 'AC1015':
        print('%s\t%s\t%.1f\t\t\t\t\t\t\tskip (unsupported version)' % (os.path.basename(f), ver, os.path.getsize(f) / 1e6), flush=True); continue
    try:
        t = time.time()
        doc = build.Doc(f)
        n = 0; mx = 0; js = 0; er = 0
        for i in range(len(doc.lays)):
            t1 = time.time(); r = doc.layout(i); mx = max(mx, time.time() - t1); n += r['n']; er += r['errors']
            js += len(json.dumps(r))
        print('%s\t%s\t%.1f\t%.1f\t%d\t%d\t%.1f\t%.1f\t%d\tok' % (os.path.basename(f), ver, os.path.getsize(f) / 1e6, doc.parse_s, len(doc.lays), n, mx, js / 1e6, er), flush=True)
    except BaseException as ex:
        print('%s\t%s\t%.1f\t\t\t\t\t\t\tERR %s' % (os.path.basename(f), ver, os.path.getsize(f) / 1e6, repr(ex)[:120]), flush=True)
