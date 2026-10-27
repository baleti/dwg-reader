"""Annotative object-context data (one MTEXT layout per annotation scale), read from the object's extension dictionary.

Layout of ACDB_MTEXTOBJECTCONTEXTDATA (measured against the AutoCAD dump on AC1027_13): class version BS, is-default B, attachment BL, x axis 3BD,
insertion point 3BD, rectangle width BD, rectangle height BD, extents width BD, extents height BD; the SCALE object is the first hard pointer
(code 5) of the handle stream. SCALE: name (string stream), paper units BD, drawing units BD (scale = paper / drawing)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgent, dwgmodel

MTEXT_CLASS = 'ACDB_MTEXTOBJECTCONTEXTDATA_CLASS'


class AnnoContexts:
    def __init__(self, m):
        self.m = m
        self._cls = {c['num']: c['dxf'] for c in m.classes()}
        self._scale = {}

    def scale_of(self, h):
        if h in self._scale: return self._scale[h]
        v = None
        o = self.m.objs.get(h)
        try:
            r = dwgent.start_reader(o)
            while True:
                n = r.BS()
                if n == 0: break
                r.H(); r.p += 8 * n
            r.BL(); r.B(); r.B(); r.BS()
            paper, draw = r.BD(), r.BD()
            if draw: v = paper / draw
        except Exception: pass
        self._scale[h] = v
        return v

    def _ctx_objects(self, o):
        """context-data objects reachable from the object's extension dictionary (dictionary -> dictionary -> objects)"""
        seen, found, todo = set(), [], [(x, 0) for c, x in dwgmodel.resolve_handles(o) if c == 3]
        while todo:
            h, d = todo.pop()
            if h in seen or h not in self.m.objs or d > 3: continue
            seen.add(h)
            ob = self.m.objs[h]
            if self._cls.get(ob.type) == MTEXT_CLASS: found.append(ob)
            elif ob.type == 42:
                todo.extend((x, d + 1) for c, x in dwgmodel.resolve_handles(ob) if c == 2)
        return found

    def mtext(self, h):
        """[{'s', 'default', 'attach', 'xdir', 'ins', 'w', 'ew', 'eh'}] for the annotative MTEXT with handle h, [] if none"""
        o = self.m.objs.get(h)
        if o is None: return []
        res = []
        for ob in self._ctx_objects(o):
            try:
                r = dwgent.start_reader(ob)
                while True:
                    n = r.BS()
                    if n == 0: break
                    r.H(); r.p += 8 * n
                r.BL(); r.B()
                if ob.ver in ('AC1027', 'AC1032'): r.B()
                r.BS(); dflt = r.B()
                att = r.BL(); xd = (r.BD(), r.BD(), r.BD()); ins = (r.BD(), r.BD(), r.BD())
                w = r.BD(); r.BD(); ew = r.BD(); eh = r.BD()
                sh = next((x for c, x in dwgmodel.resolve_handles(ob) if c == 5 and x in self.m.objs and self._cls.get(self.m.objs[x].type) == 'SCALE'), None)
                s = self.scale_of(sh) if sh else None
                if s: res.append({'s': s, 'default': bool(dflt), 'attach': att, 'xdir': xd, 'ins': ins, 'w': w, 'ew': ew, 'eh': eh})
            except Exception: continue
        return res
