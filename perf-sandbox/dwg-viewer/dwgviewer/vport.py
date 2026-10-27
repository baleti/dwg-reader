"""VPORT table entry (the saved model-space view, *ACTIVE): view height, aspect, centre, target, direction, twist. Own decoder; layout validated against the AutoCAD dump."""
import dwgent
from dwgmodel import noent_common
import dwgtab


def decode_vport(o):
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = dwgtab._rd(o, r)
    name = rd()
    dwgtab.xref_part(r, o)
    d = dict(name=name)
    d['view_height'] = r.BD(); d['width'] = r.BD()   # stored as 'aspect' but equals the view width in the dump
    d['center'] = r.RD2(); d['target'] = r.BD3(); d['direction'] = r.BD3()
    d['twist'] = r.BD(); d['lens'] = r.BD(); d['front'] = r.BD(); d['back'] = r.BD()
    return d


def active(model):
    out = []
    for h, o in model.objs.items():
        if o.type != 65: continue
        try: out.append(decode_vport(o))
        except Exception: pass
    return out
