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


def from_db():
    """text from the facts DB (cadfacts.py) when the file is there and unchanged: no second decode"""
    import sqlite3
    st = os.stat(f)
    db = sqlite3.connect('file:%s?mode=ro' % os.path.expanduser('~/.cache/indexes/cadfacts/facts.db'), uri=True, timeout=30)
    r = db.execute('SELECT id FROM files WHERE path=? AND size=? AND mtime=? AND kind="dwg" AND status IN ("ok","partial")', (f, st.st_size, int(st.st_mtime))).fetchone()
    if not r: return None
    q = lambda sql: [x[0] for x in db.execute(sql, (r[0],))]
    out = []
    lay = q('SELECT name FROM dwg_layouts WHERE fid=?')
    if lay: out.append('Layouts: ' + ', '.join(map(str, lay)))
    ly = q('SELECT name FROM dwg_layers WHERE fid=?')
    if ly: out.append('Layers: ' + ', '.join(ly))
    bl = q('SELECT name FROM dwg_blocks WHERE fid=?')
    if bl: out.append('Blocks: ' + ', '.join(bl))
    out += ['Xref: ' + x for x in q('SELECT path FROM dwg_xrefs WHERE fid=?')]
    out += q('SELECT text FROM dwg_text WHERE fid=?')
    return '\n'.join(out)[:MAXCH]


txt = ''
try:
    txt = from_db() or ''
except Exception:
    txt = ''
try:
  if not txt:
    p = subprocess.run([sys.executable, os.path.join(here, 'dwg2text.py'), '--jsonl', f], capture_output=True, timeout=1100)
    line = p.stdout.decode('utf-8', 'replace').strip().splitlines()
    if line: txt = text_of(json.loads(line[0]))
except Exception:
    txt = ''
sys.stdout.write('<html><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><title>%s</title></head><body><pre>%s</pre></body></html>\n'
                 % (html.escape(os.path.basename(f)), html.escape(txt)))
