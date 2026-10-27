#!/usr/bin/env python3
"""vsweep.py OUTDIR FILE... : vcompare layout 1 (first paper layout) of each file; TSV of ink precision/recall."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import vcompare
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
for f in sys.argv[2:]:
    for li in [int(x) for x in os.environ.get('LAYOUTS', '1').split(',')]:
        try:
            r = vcompare.run(f, li, out=out)
            print('%s\t%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s' % (os.path.basename(f), li, r['ink_precision'], r['ink_recall'], r['p5'], r['r5'], r.get('p5a'), r.get('r5a'), round(r['aspect_ours'] / r['aspect_oracle'], 3)), flush=True)
        except BaseException as ex:
            print('%s\t%d\tERR %s' % (os.path.basename(f), li, str(ex)[:100]), flush=True)
