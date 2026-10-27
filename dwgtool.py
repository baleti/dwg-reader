#!/usr/bin/env python3
"""dwgtool.py - small command line editor on dwgdoc (own code). Writes a new file, never modifies the input.
  dwgtool.py info IN.dwg
  dwgtool.py layers IN.dwg
  dwgtool.py edit IN.dwg OUT.dwg [--rename-layer OLD NEW]... [--layer-color NAME ACI]... [--layer-off NAME]... [--layer-freeze NAME]...
                                  [--move-layer NAME DX DY]... [--erase-layer NAME]... [--replace-text OLD NEW]...
"""
import sys, collections
import dwgdoc, dwgxform


def ents(doc):
    for bn, bh in doc.blocks().items():
        if bn.startswith('*d') or bn.startswith('*u'): continue
        for h in doc.chain(bh):
            yield bn, h


def main(a):
    if len(a) < 2: print(__doc__); return 2
    cmd, src = a[0], a[1]
    doc = dwgdoc.Doc(open(src, 'rb').read())
    if cmd == 'info':
        print(doc.ver, 'objects', len(doc.objs), 'layers', len(doc.layers()), 'blocks', len(doc.blocks()), 'layouts', list(doc.layouts()))
        c = collections.Counter(doc.otype(h) for _, h in ents(doc)); print('entities by type', dict(c))
    elif cmd == 'layers':
        for n, h in sorted(doc.layers().items()):
            d = doc.get(h); print('%-40s flags=%#x color=%s' % (d['name'], d['flags'], d['color'][0] or hex(d['color'][1] or 0)))
    elif cmd == 'edit':
        out = a[2]; i = 3
        lay = lambda n: doc.layer_handle(n)
        while i < len(a):
            o = a[i]
            if o == '--rename-layer': doc.set_layer(a[i + 1], new_name=a[i + 2]); i += 3
            elif o == '--layer-color': doc.set_layer(a[i + 1], color=int(a[i + 2])); i += 3
            elif o == '--layer-off': doc.set_layer(a[i + 1], off=True); i += 2
            elif o == '--layer-freeze': doc.set_layer(a[i + 1], frozen=True); i += 2
            elif o == '--replace-text': print(o, a[i + 1], '->', a[i + 2], doc.replace_text(a[i + 1], a[i + 2]), 'objects'); i += 3
            elif o in ('--move-layer', '--erase-layer'):
                lh = lay(a[i + 1]); n = 0; skipped = 0
                for bn, h in list(ents(doc)):
                    if doc.get(h)['layer'] != lh: continue
                    if o == '--erase-layer': doc.erase(h)
                    else:
                        try: doc.transform(h, dwgxform.Transform.translate(float(a[i + 2]), float(a[i + 3])))
                        except NotImplementedError: skipped += 1; continue      # e.g. ACIS solids
                    n += 1
                print(o, a[i + 1], n, 'entities' + (', %d not movable (skipped)' % skipped if skipped else ''))
                i += 2 if o == '--erase-layer' else 4
            else: print('unknown option', o); return 2
        import dwgio; dwgio.safe_save(out, doc.save(), keep_backup=False); print('wrote', out)   # atomic: a crash or a locked target never leaves a torn .dwg
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
