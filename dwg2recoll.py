#!/usr/bin/env python3
import sys, os, html, json, subprocess

here = os.path.dirname(os.path.abspath(__file__))
f = sys.argv[1]
MAXCH = 400000          # cap per drawing (a 600k-entity site plan can hold megabytes of labels)


def text_of(d):
    out = []
    add = out.append
    if d.get('version'): add('DWG version ' + str(d['version']))
    s = d.get('summary') or {}
    for k in ('title', 'subject', 'author', 'keywords', 'comments', 'last_saved_by', 'hyperlink_base'):
        if s.get(k): add('%s: %s' % (k, s[k]))
    if d.get('layouts'): add('Layouts: ' + ', '.join(str(l.get('name')) for l in d['layouts']))
    if d.get('layers'): add('Layers: ' + ', '.join(d['layers']))
    if d.get('blocks'): add('Blocks: ' + ', '.join(d['blocks']))
    for x in d.get('xrefs') or []: add('Xref: ' + (x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)))
    for x in d.get('images') or []: add('Image: ' + str(x.get('path') if isinstance(x, dict) else x))
    for a in d.get('attributes') or []:
        if a.get('value'): add('%s = %s' % (a.get('tag'), a['value']))
    seen = set()
    for i in d.get('items') or []:
        t = (i.get('text') or '').strip()
        if t and t not in seen: seen.add(t); add(t)
    return '\n'.join(out)[:MAXCH]


txt = ''
try:
    p = subprocess.run([sys.executable, os.path.join(here, 'dwg2text.py'), '--jsonl', f], capture_output=True, timeout=1100)
    line = p.stdout.decode('utf-8', 'replace').strip().splitlines()
    if line: txt = text_of(json.loads(line[0]))
except Exception:
    txt = ''
sys.stdout.write('<html><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><title>%s</title></head><body><pre>%s</pre></body></html>\n'
                 % (html.escape(os.path.basename(f)), html.escape(txt)))
