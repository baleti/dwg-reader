#!/usr/bin/env python3
"""review_index.py [DIR] : write DIR/INDEX.md (and index.html with the side-by-side images) from the *_side.png files and DIR/sweep.tsv scores. Local only."""
import sys, os, glob, json, html
d = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else '~/review-compare-dwg')
scores = {}
for ln in open(os.path.join(d, 'sweep.tsv')):
    if ln.startswith('{'):
        try: j = json.loads(ln)
        except Exception: continue
        scores[os.path.basename(j['side'])] = j
rows = sorted(glob.glob(os.path.join(d, '*_side.png')))
md = ['# DWG viewer vs AutoCAD plots (left: AutoCAD, middle: dwg-viewer, right: diff, red = only AutoCAD, blue = only ours)', '', 'ink precision/recall after 2 px and 5 px dilation (p5/r5); local files only.', '', '| file | layout | prec | rec | p5 | r5 |', '|---|---|---|---|---|---|']
hh = ['<meta charset="utf-8"><title>dwg-viewer vs AutoCAD</title><body style="font:13px sans-serif;background:#222;color:#ddd"><h2>dwg-viewer vs AutoCAD plots</h2><p>left AutoCAD, middle dwg-viewer, right diff (red only AutoCAD, blue only ours)</p>']
for f in rows:
    b = os.path.basename(f); j = scores.get(b, {})
    md.append('| %s | %s | %s | %s | %s | %s |' % (j.get('file', b), j.get('layout', ''), j.get('ink_precision', ''), j.get('ink_recall', ''), j.get('p5', ''), j.get('r5', '')))
    hh.append('<h4>%s / %s &nbsp; p=%s r=%s p5=%s r5=%s</h4><img src="%s" style="max-width:100%%">' % (html.escape(str(j.get('file', b))), html.escape(str(j.get('layout', ''))), j.get('ink_precision'), j.get('ink_recall'), j.get('p5'), j.get('r5'), html.escape(b)))
open(os.path.join(d, 'INDEX.md'), 'w').write('\n'.join(md) + '\n')
open(os.path.join(d, 'index.html'), 'w').write('\n'.join(hh))
print(len(rows), 'pairs indexed in', d)
