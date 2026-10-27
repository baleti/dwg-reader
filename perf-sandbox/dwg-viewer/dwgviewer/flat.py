"""Scene flattener for the viewer (own code). Walks a block's entities and emits display primitives in the final
space (model units, or paper units for viewport content), with ByLayer/ByBlock resolved, linetype dashes in final units,
text with everything the client needs to place it, hatches with their pattern lines, and entity handles for picking.

Primitive tuples (python); build.py turns them into JSON rows:
 ('l', layer, color, lw_mm, dash|None, flat_pts, handle)
 ('h', layer, color, loops, info, handle)       loops = list of flat point lists; info = dict(solid, pat, lines, grad)
 ('t', layer, color, x, y, h, rot, text, opts, handle)
color: ACI int (7 = foreground colour) or [r, g, b].
"""
import math, os, re
import dwgmodel
import dwgent
from dwgscene import Mat, arc_points, bulge_points, ocs_to_wcs, ocs_axes

DEFAULT_LW = 0.25


def _ell_pts(c, mj, r, a0, a1, mat):
    if a1 <= a0: a1 += 2 * math.pi
    n = max(24, int((a1 - a0) / (2 * math.pi) * 96))
    a, b = mj[0], mj[1]
    out = []
    for i in range(n + 1):
        t = a0 + (a1 - a0) * i / n
        out.append(mat.apply(c[0] + a * math.cos(t) - b * r * math.sin(t), c[1] + b * math.cos(t) + a * r * math.sin(t)))
    return out


def bspline_fast(deg, knots, ctrl, weights=None, n=None):
    """(rational) B-spline samples, Piegl-Tiller basis evaluation per span (replaces the recursive Cox-de Boor in dwgscene)"""
    m = len(ctrl)
    if m == 0 or len(knots) < m + deg + 1 or deg < 1: return [(c[0], c[1]) for c in ctrl]
    t0, t1 = knots[deg], knots[m]
    n = n or max(16, 6 * m)
    try:
        import numpy as np
    except ImportError:
        from bisect import bisect_right
        pts = []
        for s_ in range(n + 1):
            t = t0 + (t1 - t0) * s_ / n
            span = min(max(bisect_right(knots, t) - 1, deg), m - 1)
            N = [1.0] + [0.0] * deg
            left = [0.0] * (deg + 1); right = [0.0] * (deg + 1)
            for j in range(1, deg + 1):
                left[j] = t - knots[span + 1 - j]; right[j] = knots[span + j] - t
                saved = 0.0
                for r in range(j):
                    den = right[r + 1] + left[j - r]
                    tmp = N[r] / den if den else 0.0
                    N[r] = saved + right[r + 1] * tmp
                    saved = left[j - r] * tmp
                N[j] = saved
            x = y = w = 0.0
            for j in range(deg + 1):
                i = span - deg + j
                wi = N[j] * (weights[i] if weights else 1.0)
                x += wi * ctrl[i][0]; y += wi * ctrl[i][1]; w += wi
            if w: pts.append((x / w, y / w))
        return pts

    # Keep range's integer validation and its empty result for negative n.
    count = len(range(n + 1))
    if not count:
        return []
    knots = np.asarray(knots, dtype=float)
    # Match the scalar operation order, including the final parameter.
    t = t0 + (t1 - t0) * np.arange(count, dtype=float) / n
    span = np.minimum(np.maximum(np.searchsorted(knots, t, side='right') - 1,
                                 deg), m - 1)
    N = np.zeros((deg + 1, count))
    N[0] = 1.0
    left = np.zeros_like(N)
    right = np.zeros_like(N)
    for j in range(1, deg + 1):
        left[j] = t - knots[span + 1 - j]
        right[j] = knots[span + j] - t
        saved = np.zeros(count)
        for r in range(j):
            den = right[r + 1] + left[j - r]
            tmp = np.divide(N[r], den, out=np.zeros(count), where=den != 0)
            N[r] = saved + right[r + 1] * tmp
            saved = left[j - r] * tmp
        N[j] = saved

    xy = np.asarray([(c[0], c[1]) for c in ctrl], dtype=float)
    weighted = bool(weights)
    if weighted:
        weights = np.asarray(weights, dtype=float)
    x = np.zeros(count)
    y = np.zeros(count)
    w = np.zeros(count)
    # Accumulate in the same order as the scalar implementation.
    for j in range(deg + 1):
        i = span - deg + j
        wi = N[j] * weights[i] if weighted else N[j]
        x += wi * xy[i, 0]
        y += wi * xy[i, 1]
        w += wi
    valid = w != 0
    return list(zip((x[valid] / w[valid]).tolist(),
                    (y[valid] / w[valid]).tolist()))


def _flat(pts):
    f = []
    for x, y in pts:
        f.append(x); f.append(y)
    return f


class Ctx:
    """Inherited properties of an INSERT: ByBlock colour / lineweight / linetype and the layer for entities on layer 0."""
    __slots__ = ('color', 'lw', 'lt', 'layer', 'ltscale')

    def __init__(self, color=7, lw=DEFAULT_LW, lt=None, layer=None, ltscale=1.0):
        self.color, self.lw, self.lt, self.layer, self.ltscale = color, lw, lt, layer, ltscale


from .annoctx import AnnoContexts


def _sane(rows):
    """False if any row of an entity has a non-finite or absurd (> 1e12) coordinate"""
    for p in rows:
        k = p[0]
        if k == 'l': vals = p[5]
        elif k == 'h': vals = [v for lp in p[3] for v in lp]
        elif k in ('t', 'p'): vals = (p[3], p[4])
        else: continue
        if sum(map(abs, vals)) < 1e12: continue     # fast path (NaN/inf poison the sum); the exact per-value test only runs for suspicious rows
        for v in vals:
            if not abs(v) < 1e12: return False
    return True


def dstyle_overrides(eed):
    """{dimension variable group code: value} from the ACAD/DSTYLE extended data of an entity (pairs of 70 code + value; 40 DIMSCALE, 41 DIMASZ ...).
    EED stream: type byte (0 string = u16 length + UTF-16, 2 brace, 70 int16, 71 int32, 40 double, 1070.. as 70/71, 10 handle 8 bytes)."""
    out = {}
    for app, b in eed or []:
        if 'DSTYLE'.encode('utf-16le') not in b: continue
        i = 0; code = None
        try:
            while i < len(b):
                t = b[i]; i += 1
                if t == 0: n = int.from_bytes(b[i:i + 2], 'little'); i += 2 + 2 * n
                elif t == 2: i += 1
                elif t == 70:
                    v = int.from_bytes(b[i:i + 2], 'little', signed=True); i += 2
                    if code is None: code = v
                    else: out[code] = v; code = None
                elif t == 71:
                    v = int.from_bytes(b[i:i + 4], 'little', signed=True); i += 4
                    if code is None: code = v
                    else: out[code] = v; code = None
                elif t in (40, 41, 42):
                    import struct as _st
                    out[code] = _st.unpack_from('<d', b, i)[0]; i += 8; code = None
                elif t == 5:      # 1005 handle (e.g. the text style / arrow block override): value of the pending code
                    if code is not None: out[code] = int.from_bytes(b[i:i + 8], 'big')
                    i += 8; code = None
                elif t in (10, 11, 12, 13): i += 24      # 3D point / position / displacement / direction
                elif t == 3: i += 8
                elif t == 4: i += 1 + b[i]
                else: break
        except Exception: pass
    return out


class Flattener:
    def __init__(self, scene, header=None):
        self.sc = scene
        self.m = scene.m
        self.h = header or {}
        self.ltscale = float(self.h.get('ltscale', 1.0))
        self.layers = self.m.layer_table()
        self.lts = self.m.ltypes()
        self.styles = self.m.styles()
        self._style_by_handle = {st['handle']: st for st in self.styles.values() if 'handle' in st}
        self._ent_style = {}
        self.by_owner = {}                      # BLOCK_HEADER handle -> entities (anonymous blocks share the name '*U')
        base_ps = None
        try:    # BLOCK_CONTROL ends with the *Model_Space and *Paper_Space handles
            for h_, o_ in scene.m.objs.items():
                if o_.type == 48:
                    hs_ = [v for c, v in dwgmodel.resolve_handles(o_) if v in scene.m.objs and scene.m.objs[v].type == 49]
                    if hs_: base_ps = hs_[-1]
                    break
        except Exception: pass
        if base_ps is None: base_ps = next((h for h, n in scene.m.blocks.items() if n.lower() == '*paper_space'), None)
        polys = {e['handle']: e for es in scene.by_block.values() for e in es if e['kind'].startswith('POLYLINE')}
        for es in scene.by_block.values():     # vertices that the parser could not chain by handle order (owned by the polyline, entmode 0: AC1018_39 has 142,595 such polylines)
            for e in es:
                p_ = polys.get(e.get('owner'))
                if p_ is not None and e['kind'].startswith('VERTEX') and not p_.get('verts'):
                    p_.setdefault('_v', []).append(e)
        for p_ in polys.values():
            if p_.get('_v') and not p_.get('verts'):
                p_['_v'].sort(key=lambda v: v['handle'])
                p_['verts'] = [v for v in p_['_v'] if v['kind'] != 'VERTEX_PFACE_FACE']
                p_['faces'] = [v for v in p_['_v'] if v['kind'] == 'VERTEX_PFACE_FACE']
            p_.pop('_v', None)
        for es in scene.by_block.values():
            for e in es:
                # entmode 1 = the base *Paper_Space block (the parser assigns the 'active' paper space instead, which can be another layout)
                o = base_ps if (e.get('entmode') == 1 and base_ps is not None) else e['owner']
                self.by_owner.setdefault(o, []).append(e)
        self._blk_of = {}
        self._base_h = {}
        self.attribs = {}
        for e in scene.by_block.get(None, []):
            if e['kind'] == 'ATTRIB': self.attribs.setdefault(e['owner'], []).append(e)

    # ---- property resolution -------------------------------------------------
    def layer_color(self, name):
        d = self.layers.get(name)
        if not d: return 7
        if d.get('true_color'): return list(d['true_color'])
        c = d['color']
        return abs(c) if c else 7

    def layer_lw(self, name):
        d = self.layers.get(name)
        return (d.get('lineweight_mm') if d else None) or None

    def resolve(self, e, ctx):
        """-> (layer_for_visibility, color, lw_mm, ltype name)"""
        ly = e.get('layer')
        if ly == '0' and ctx.layer is not None: ly = ctx.layer
        ef = self.m.effective(dict(e, layer=ly))
        raw = e['color'][0]
        if ef['rgb'] is not None: col = list(ef['rgb'])
        elif raw == 0 and not (len(e['color']) > 1 and e['color'][1] is not None): col = ctx.color
        else: col = ef['color'] or 7
        lw = e.get('lweight')
        if lw is not None and lw < 24: lw_mm = dwgmodel.LWEIGHT_MM.get(lw)
        elif lw == 30: lw_mm = ctx.lw
        elif lw == 31: lw_mm = DEFAULT_LW
        else: lw_mm = ef['lineweight_mm'] or DEFAULT_LW
        lt = 'Continuous' if e.get('ltflags') == 2 else ef['ltype']
        if lt == 'ByBlock': lt = ctx.lt
        return ly, col, lw_mm, lt

    def dash(self, ltname, e, mat, dscale):
        """signed dash list in final-space units (positive = pen down) or None for continuous."""
        lt = self.lts.get(ltname) if ltname else None
        if not lt: return None
        ds = [d['length'] for d in lt['dashes'] if not d.get('shape') and not (d.get('flags', 0) & 6)]
        if not ds or all(abs(x) < 1e-12 for x in ds): return None
        k = self.ltscale * e.get('ltscale', 1.0) * dscale
        return [round(x * k, 6) for x in ds]

    # ---- text ----------------------------------------------------------------
    def style_of(self, e):
        h = e['handle']
        if h in self._ent_style: return self._ent_style[h]
        st = None
        o = self.m.objs.get(h)
        if o is not None:
            try:
                for c, v in dwgmodel.resolve_handles(o):
                    if v in self._style_by_handle: st = self._style_by_handle[v]; break
            except Exception:
                pass
        self._ent_style[h] = st
        return st

    # ---- main walk -----------------------------------------------------------
    def flatten(self, block_name, mat=None, hide=frozenset(), ctx=None, dscale=1.0, depth=0, out=None):
        mat = mat or Mat()
        ctx = ctx or Ctx()
        out = [] if out is None else out
        if depth > 8: return out
        content = self.by_owner.get(block_name, []) if isinstance(block_name, int) else self.sc.block_content(block_name)
        cull = None if os.environ.get('DWG_NO_CULL') else getattr(self, '_cull', None)
        for e in content:
            n0 = len(out)
            if cull is not None and self._culled(e, mat, cull): continue
            try:
                self._entity(e, mat, hide, ctx, dscale, depth, out)
                if len(out) > n0:
                    a_ = e.get('color') and len(e['color']) > 2 and e['color'][2]
                    if a_ and (a_ >> 24) == 2 and (a_ & 255) < 255:    # entity transparency (colour alpha word 0x02000000 | 0..255, 255 = opaque)
                        al_ = round((a_ & 255) / 255, 3)
                        if depth == 0:
                            if not hasattr(self, 'ealpha'): self.ealpha = {}
                            self.ealpha[e['handle']] = al_    # line / text rows have no info dict: the client looks the alpha up by top-level handle
                        for i in range(n0, len(out)):
                            r_ = out[i]
                            if r_[0] == 'h' and isinstance(r_[4], dict): out[i] = r_[:4] + (dict(r_[4], a=al_),) + r_[5:]
                if len(out) > n0 and not _sane(out[n0:]): del out[n0:]    # garbage coordinates (1e206 from a misdecoded record) would blow up the drawn extents
                if depth == 0 and e['kind'] in ('INSERT', 'MINSERT') and len(out) > n0:    # content on other layers is still hidden when the INSERT's own layer is off / frozen
                    ly0 = e.get('layer')
                    if ly0 and any(r_[1] != ly0 for r_ in out[n0:]):
                        if not hasattr(self, 'toplayer'): self.toplayer = {}
                        self.toplayer[e['handle']] = ly0
                if depth == 0:   # rows remember the top-level object they belong to (an INSERT owns everything nested in it): the selection unit
                    for i in range(n0, len(out)): out[i] = out[i] + (e['handle'],)
            except TypeError as ex:  # a field the parser could not decode (None) is a skipped entity, not a viewer error
                if 'NoneType' not in str(ex): self.errors = getattr(self, 'errors', 0) + 1
            except Exception:  # one bad entity must not kill the drawing
                self.errors = getattr(self, 'errors', 0) + 1
        return out

    def _entity(self, e, mat, hide, ctx, dscale, depth, out):
        k = e['kind']
        if k in ('ATTDEF', 'VERTEX2D', 'VERTEX3D', 'SEQEND', 'VIEWPORT'): return
        ly, col, lw, lt = self.resolve(e, ctx)
        if ly in hide or e.get('invis'): return
        hd = e['handle']
        for key_ in ('p1', 'p2', 'center', 'ins', 'p'):     # a misdecoded entity (R13/R14 reader: a BD code 3 gives None) carries None coordinates: skip it instead of failing
            v_ = e.get(key_)
            if isinstance(v_, (tuple, list)) and any(c is None or not abs(c) < 1e12 for c in v_[:2]): return     # None, NaN or absurd (1e270) values are decoding garbage
        for key_ in ('radius', 'height', 'text_height'):
            v_ = e.get(key_)
            if isinstance(v_, float) and not abs(v_) < 1e12: return
        ext = tuple(e.get('ext', (0.0, 0.0, 1.0)))
        L = out.append

        if ext == (0.0, 0.0, 1.0):
            def W(x, y, z=0.0):
                return mat.apply(x, y)
        else:
            _ax, _ay, _az = ocs_axes(ext)       # axes once per entity, not once per point

            def W(x, y, z=0.0):
                return mat.apply(_ax[0] * x + _ay[0] * y + _az[0] * z, _ax[1] * x + _ay[1] * y + _az[1] * z)

        def line(pts, wd=0.0):
            if len(pts) > 1: L(('l', ly, col, lw, self.dash(lt, e, mat, dscale), _flat(pts), hd, wd))
        if k == 'LINE':
            line([mat.apply(e['p1'][0], e['p1'][1]), mat.apply(e['p2'][0], e['p2'][1])])
        elif k == 'CIRCLE':
            c = e['center']
            line([W(x, y, c[2]) for x, y in arc_points(c[0], c[1], e['radius'], 0, 2 * math.pi)])
        elif k == 'ARC':
            c = e['center']
            line([W(x, y, c[2]) for x, y in arc_points(c[0], c[1], e['radius'], e['a0'], e['a1'])])
        elif k == 'ELLIPSE':
            line(_ell_pts(e['center'], e['major'], e['ratio'], e['a0'], e['a1'], mat))
        elif k == 'LWPOLYLINE':
            pts = e['pts']; bul = e['bulges']
            if not pts: return
            n = len(pts)
            cw = e.get('constwidth') or 0.0
            wl = e.get('widths') or []
            has_w = cw > 0 or any((a_ or 0) > 0 or (b_ or 0) > 0 for a_, b_ in wl)
            path = [W(pts[0][0], pts[0][1], e['elev'])]
            quads = []; sc_ = mat.scale_x()
            for i in range(1, n + (1 if e['closed'] else 0)):
                p0 = pts[i - 1]; p1 = pts[i % n]
                b = bul[i - 1] if i - 1 < len(bul) else 0.0
                sub = [W(p0[0], p0[1], e['elev'])] + [W(q[0], q[1], e['elev']) for q in bulge_points(p0, p1, b)]
                path.extend(sub[1:])
                if has_w:
                    w0, w1 = (wl[i - 1] if i - 1 < len(wl) else (0.0, 0.0))
                    if not (w0 or w1): w0 = w1 = cw
                    if w0 > 0 or w1 > 0:
                        tot = sum(math.hypot(sub[j + 1][0] - sub[j][0], sub[j + 1][1] - sub[j][1]) for j in range(len(sub) - 1)) or 1.0
                        acc = 0.0
                        for j in range(len(sub) - 1):
                            (ax_, ay_), (bx_, by_) = sub[j], sub[j + 1]
                            dl = math.hypot(bx_ - ax_, by_ - ay_)
                            if dl < 1e-12: continue
                            wa = (w0 + (w1 - w0) * acc / tot) * sc_ / 2; acc += dl; wb = (w0 + (w1 - w0) * acc / tot) * sc_ / 2
                            nx, ny = -(by_ - ay_) / dl, (bx_ - ax_) / dl
                            quads.append(_flat([(ax_ + nx * wa, ay_ + ny * wa), (bx_ + nx * wb, by_ + ny * wb), (bx_ - nx * wb, by_ - ny * wb), (ax_ - nx * wa, ay_ - ny * wa)]))
            line(path)
            if quads: L(('h', ly, col, quads, {'solid': 1, 'nz': 1}, hd))
        elif k == 'POLYLINE2D' and e.get('verts'):
            vs = [(v['p'][0], v['p'][1], v['bulge']) for v in e['verts'] if not (v['flags'] & 16)]
            if vs:
                path = [W(vs[0][0], vs[0][1])]
                n = len(vs)
                for i in range(1, n + (1 if e['closed'] else 0)):
                    p0 = vs[i - 1]; p1 = vs[i % n]
                    for q in bulge_points(p0[:2], p1[:2], p0[2]): path.append(W(q[0], q[1]))
                line(path)
        elif k == 'POLYLINE3D' and e.get('verts'):
            vs = [v['p'] for v in e['verts'] if not (v['flags'] & 16)]
            if e['closed'] and vs: vs = vs + [vs[0]]
            line([mat.apply(p[0], p[1]) for p in vs])
        elif k == 'LEADER':
            pts_ = [mat.apply(p[0], p[1]) for p in e['pts']]
            line(pts_)
            if e.get('arrowhead') and len(pts_) > 1:
                size = self.leader_arrow(e) * mat.scale_x()
                (x0, y0), (x1, y1) = pts_[0], pts_[1]
                dl = math.hypot(x1 - x0, y1 - y0)
                if size > 0 and dl > 1e-12:
                    ux, uy = (x1 - x0) / dl, (y1 - y0) / dl
                    bx, by = x0 + ux * size, y0 + uy * size
                    L(('h', ly, col, [_flat([(x0, y0), (bx - uy * size / 6, by + ux * size / 6), (bx + uy * size / 6, by - ux * size / 6)])], {'solid': 1}, hd))
        elif k == 'ACAD_TABLE':    # the table draws as its anonymous *T block, placed so that the block's top-left sits at the insertion point (flow-up tables have the block above the origin)
            o_ = self.m.objs.get(e['handle'])
            bh = next((v for c, v in dwgmodel.resolve_handles(o_)[1:] if v in self.by_owner and v in self.m.objs and self.m.objs[v].type == 49), None) if o_ is not None else None
            if bh is not None:
                r_ = dwgent.start_reader(o_); dwgent.common_entity(r_, o_.ver); ins = r_.BD3()
                ys = [q for e2 in self.by_owner[bh] if e2['kind'] == 'LINE' for q in (e2['p1'][1], e2['p2'][1])]
                top = max(max(ys), 0.0) if ys else 0.0
                self.flatten(bh, mat.mul(Mat(1, 0, 0, 1, ins[0], ins[1] - top)), hide, Ctx(col, lw, lt, ly, ctx.ltscale), dscale, depth + 1, out)
        elif k == 'MULTILEADER':
            asz = (e.get('arrow_size') or 0.0) * mat.scale_x()
            for pts in e.get('leader_lines') or []:
                poly = [mat.apply(q[0], q[1]) for q in pts] + [mat.apply(e['leader_conn'][0], e['leader_conn'][1]), mat.apply(e['leader_end'][0], e['leader_end'][1])]
                line(poly)
                (x0, y0), (x1, y1) = poly[0], poly[1]
                dl = math.hypot(x1 - x0, y1 - y0)
                if asz > 0 and dl > 1e-12:
                    ux, uy = (x1 - x0) / dl, (y1 - y0) / dl
                    bx, by = x0 + ux * asz, y0 + uy * asz
                    L(('h', ly, col, [_flat([(x0, y0), (bx - uy * asz / 6, by + ux * asz / 6), (bx + uy * asz / 6, by - ux * asz / 6)])], {'solid': 1}, hd))
            if e.get('text_loc') and e.get('strings'):
                txt = '\\P'.join(x for x in (re.sub(r'\\[pP][^;]*;', '', t).strip() for t in e['strings']) if x)
                if txt:
                    x, y = mat.apply(e['text_loc'][0], e['text_loc'][1])
                    opts = {'mt': 1, 'hj': 0, 'vj': 3}
                    st = self.style_of(e)
                    if st: opts['font'] = st['font']
                    L(('t', ly, col, x, y, e['text_height'] * mat.scale_x(), mat.rot(), txt, opts, hd))
        elif k in ('REGION', '3DSOLID', 'BODY'):   # ACIS wireframe in plan view (parser: dwgacis)
            w = e.get('_wire')
            if w is None:
                try:
                    import dwgacis
                    pr = dwgacis.parse(e); w = e['_wire'] = dwgacis.wire(pr[1]) if pr else []
                except Exception:
                    w = e['_wire'] = []
            for sg in w: line([mat.apply(q[0], q[1]) for q in sg])
        elif k == 'OLE2FRAME':    # embedded picture: a filled quad that carries the picture id (drawn by the client from /api/ole/<handle>)
            q = [mat.apply(p[0], p[1]) for p in e['pts']]
            L(('h', ly, col, [_flat(q)], {'solid': 1, 'img': hd}, hd))
        elif k == 'SPLINE':
            if e['ctrl']: pts = bspline_fast(e['degree'], e['knots'], e['ctrl'], e['weights'] or None)
            else: pts = [(p[0], p[1]) for p in e['fit']]
            line([mat.apply(x, y) for x, y in pts])
        elif k in ('SOLID', 'TRACE'):
            p = e['pts']
            loop = [W(x, y, e['elev']) for x, y in (p[0], p[1], p[3], p[2])]
            L(('h', ly, col, [_flat(loop)], {'solid': 1}, hd))
        elif k == '3DFACE':
            p = e['pts']
            line([mat.apply(q[0], q[1]) for q in (p[0], p[1], p[2], p[3], p[0])])
        elif k == 'POINT':
            x, y = mat.apply(e['p'][0], e['p'][1])
            L(('p', ly, col, x, y, hd))
        elif k in ('TEXT', 'ATTRIB'):
            self._text(e, mat, ly, col, W, out)
        elif k == 'WIPEOUT':
            self._wipeout(e, mat, ly, col, out)
        elif k == 'MLINE':
            for ln in e.get('lines') or []:
                pts = [mat.apply(q[0], q[1]) for q in ln]
                if e.get('closed') and len(pts) > 2: pts.append(pts[0])
                if len(pts) > 1: L(('l', ly, col, lw, self.dash(lt, e, mat, dscale), _flat(pts), hd, 0.0))
        elif k.endswith('UNDERLAY'):   # the PDF / DGN / DWF itself is external: draw the clip frame (or a cross) as placeholder, hidden in plot preview like IMAGE
            ix, iy = e['ins'][0], e['ins'][1]; sx, sy = e['scale'][0], e['scale'][1]; c_, s_ = math.cos(e['rot']), math.sin(e['rot'])
            cl = e.get('clip') or []
            loc = cl + [cl[0]] if len(cl) > 2 else [(-5, -5), (5, -5), (5, 5), (-5, 5), (-5, -5)]
            pts = [mat.apply(ix + sx * x * c_ - sy * y * s_, iy + sx * x * s_ + sy * y * c_) for x, y in loc]
            L(('l', ly, col, -1, None, _flat(pts), hd, 0.0))
        elif k == 'IMAGE':   # raster file is external: draw the frame with a cross as placeholder
            o_, u_, v_ = e['pt0'], e['uvec'], e['vvec']; sz = e.get('size') or (1, 1)
            cl = e.get('clip') or []
            if e.get('clip_type') == 1 and len(cl) == 2: (x0, y0), (x1, y1) = cl
            else: x0, y0, x1, y1 = -0.5, -0.5, sz[0] - 0.5, sz[1] - 0.5
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            pts = [mat.apply(o_[0] + (cx + 0.5) * u_[0] + (cy + 0.5) * v_[0], o_[1] + (cx + 0.5) * u_[1] + (cy + 0.5) * v_[1]) for cx, cy in corners]
            for seg in (pts + [pts[0]], [pts[0], pts[2]], [pts[1], pts[3]]):   # lineweight -1 marks an image placeholder (hidden in plot preview)
                L(('l', ly, col, -1, None, _flat(seg), hd, 0.0))
        elif k == 'MTEXT':
            self._mtext(e, mat, ly, col, out)
        elif k == 'HATCH':
            self._hatch(e, mat, W, ly, col, out, lw)
        elif k in ('INSERT', 'MINSERT'):
            self._insert(e, mat, hide, ctx, dscale, depth, ly, col, lw, lt, ext, out)
        elif k.startswith('DIM_'):
            bname = e.get('block_ref')
            bh = self.block_handle(e)
            if bh is not None and bh in self.by_owner: bname = bh
            if bname:
                self.flatten(bname, mat, hide, Ctx(col, lw, lt, ly if ly != '0' else ctx.layer, ctx.ltscale), dscale, depth + 1, out)

    def leader_arrow(self, e):
        """arrowhead length = DIMASZ * DIMSCALE of the leader's dimstyle (handle stream type 69)"""
        try:
            if not hasattr(self, '_dimst'):
                self._dimst = {v['handle']: v for v in self.m.dimstyles().values()}
            o = self.m.objs.get(e['handle'])
            for c, v in dwgmodel.resolve_handles(o):
                if v in self._dimst:
                    d = self._dimst[v]; ov = dstyle_overrides(e.get('eed'))
                    return float(ov.get(41, d.get('DIMASZ', 0.18))) * float(ov.get(40, d.get('DIMSCALE', 1.0)) or 1.0)
        except Exception: pass
        return 0.0

    def block_handle(self, e):
        h = e['handle']
        if h in self._blk_of: return self._blk_of[h]
        r = None
        o = self.m.objs.get(h)
        if o is not None:
            try:
                for c, v in dwgmodel.resolve_handles(o)[1:]:   # [0] is the owner block (entmode 0) or the layer
                    if v in self.m.objs and self.m.objs[v].type == 49: r = v; break
            except Exception: pass
        self._blk_of[h] = r
        return r

    def base_of(self, bh):
        if bh not in self._base_h:
            import dwgtab
            try: self._base_h[bh] = dwgtab.decode_block_header(self.m.objs[bh])['base']
            except Exception: self._base_h[bh] = None
        return self._base_h[bh]

    def _culled(self, e, mat, cull):
        """True when the entity's bounding box (plain LINE / LWPOLYLINE without bulges / CIRCLE / ARC in the default plane) lies completely outside the cull box (final space):
        used while an INSERT with a spatial filter is flattened, so content that the clip removes anyway is not built"""
        k = e['kind']
        try:
            if k == 'LINE': pts = [e['p1'], e['p2']]
            elif k == 'LWPOLYLINE':
                if e.get('bulges') and any(e['bulges']): return False
                pts = e['pts']
            elif k in ('CIRCLE', 'ARC'):
                c, r = e['center'], e['radius']
                pts = [(c[0] - r, c[1] - r), (c[0] + r, c[1] - r), (c[0] + r, c[1] + r), (c[0] - r, c[1] + r)]
            else: return False
            if tuple(e.get('ext', (0.0, 0.0, 1.0))) != (0.0, 0.0, 1.0) or not pts: return False
            xs = []; ys = []
            for p in pts:
                x, y = mat.apply(p[0], p[1]); xs.append(x); ys.append(y)
            return max(xs) < cull[0] or min(xs) > cull[2] or max(ys) < cull[1] or min(ys) > cull[3]
        except Exception:
            return False

    def spatial_clip(self, e):
        """clip polygon of an INSERT's spatial filter (XCLIP) in block space, or None. Chain: INSERT xdictionary -> ACAD_FILTER dictionary -> SPATIAL object.
        SPATIAL object (own decoding, checked on a real drawing against the AutoCAD plot): BS count, count x 2RD clip points (2 points = rectangle corners),
        3BD normal, 3BD origin, BS display flag, BS front on [BD], BS back on [BD], 12 BD matrix (3 x 4 rows, translation last): block point = M * clip point."""
        h = e['handle']
        if os.environ.get('DWG_NO_XCLIP'): return None
        if not hasattr(self, '_sclip'): self._sclip = {}
        if h in self._sclip: return self._sclip[h]
        res = None
        try:
            o = self.m.objs.get(h)
            xd = next((v for c, v in dwgmodel.resolve_handles(o) if c == 3), None) if o is not None else None
            if xd:
                ds = self.m.dictionaries()
                flt = ds.get(xd, {}).get('ACAD_FILTER'); sp = ds.get(flt, {}).get('SPATIAL') if flt else None
                if sp and sp in self.m.objs:
                    import dwgent, dwgtab
                    r = dwgent.start_reader(self.m.objs[sp]); dwgtab.noent_common(r, self.m.objs[sp].ver)
                    n = r.BS(); pts = [r.RD2() for _ in range(n)] if 0 < n <= 256 else []
                    r.BD3(); r.BD3(); r.BS()
                    if r.BS(): r.BD()
                    if r.BS(): r.BD()
                    mx = [r.BD() for _ in range(12)]
                    if len(pts) == 2: (x0, y0), (x1, y1) = pts; pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                    if len(pts) >= 3:
                        res = [(mx[0] * x + mx[1] * y + mx[3], mx[4] * x + mx[5] * y + mx[7]) for x, y in pts]
        except Exception:
            res = None
        self._sclip[h] = res
        return res

    def _insert(self, e, mat, hide, ctx, dscale, depth, ly, col, lw, lt, ext, out):
        bname = e.get('block_ref') or e.get('block_name') or '*MINSERT'
        bh = self.block_handle(e)
        xr = getattr(self, 'xref_resolver', None)
        if xr is not None and bh is not None and bh not in self.by_owner and depth < 4:     # external reference whose DWG is next to the drawing: draw its model space
            r_ = xr(bh)
            if r_:
                child, prefix = r_
                sx, sy, sz = e['scale']; ins = ocs_to_wcs(e['ins'], ext); c, s = math.cos(e['rot']), math.sin(e['rot'])
                ib = child.fl.h.get('insbase') or (0.0, 0.0, 0.0)
                mx_ = Mat(c * sx, -s * sy, s * sx, c * sy, ins[0], ins[1]).mul(Mat(1, 0, 0, 1, -ib[0], -ib[1]))
                n0 = len(out)
                child.fl.flatten(child.model_name, mat.mul(mx_), frozenset(), Ctx(7, DEFAULT_LW, None, None, ctx.ltscale), dscale, depth + 1, out)
                for i_ in range(n0, len(out)):       # xref layers are listed in the host as 'xrefname|layer'
                    r2 = out[i_]
                    if r2[1]: out[i_] = (r2[0], prefix + r2[1]) + tuple(r2[2:])
                return
        bh = self.block_handle(e)
        if bh is not None and bh in self.by_owner:
            bname = bh
            base = self.base_of(bh) or self.sc.blk_base.get(e.get('block_ref'), (0.0, 0.0, 0.0))
        else:
            base = self.sc.blk_base.get(bname, (0.0, 0.0, 0.0))
        sx, sy, sz = e['scale']
        ins = ocs_to_wcs(e['ins'], ext)
        c, s = math.cos(e['rot']), math.sin(e['rot'])
        m2 = Mat(c * sx, -s * sy, s * sx, c * sy, ins[0], ins[1])
        if ext != (0.0, 0.0, 1.0):      # block axes follow the OCS of the INSERT (mirrored inserts have extrusion (0,0,-1))
            from dwgscene import ocs_axes
            ax, ay, _ = ocs_axes(ext)
            m2 = Mat(ax[0], ay[0], ax[1], ay[1], ins[0], ins[1]).mul(Mat(c * sx, -s * sy, s * sx, c * sy, 0, 0))
        m2 = m2.mul(Mat(1, 0, 0, 1, -base[0], -base[1]))
        nctx = Ctx(col, lw, lt, ly, ctx.ltscale)
        offs = [(0.0, 0.0)]
        if e['kind'] == 'MINSERT':     # array: instance (r, c) sits at ins + R(rot) * (c * column spacing, r * row spacing)
            nc, nr = max(int(e.get('cols') or 1), 1), max(int(e.get('rows') or 1), 1)
            cs, rs = e.get('col_spacing') or 0.0, e.get('row_spacing') or 0.0
            if nc * nr > 1 and nc * nr <= 20000:
                offs = []
                for r_ in range(nr):
                    for c_ in range(nc):
                        dx, dy = c_ * cs, r_ * rs
                        offs.append((c * dx - s * dy, s * dx + c * dy))
        n_in = len(out)
        cp = self.spatial_clip(e)
        saved_cull = getattr(self, '_cull', None)
        if cp and len(offs) == 1:      # entities outside the clip box are not built at all
            mf_ = mat.mul(m2); fp = [mf_.apply(x, y) for x, y in cp]
            bx = (min(p[0] for p in fp), min(p[1] for p in fp), max(p[0] for p in fp), max(p[1] for p in fp))
            if saved_cull: bx = (max(bx[0], saved_cull[0]), max(bx[1], saved_cull[1]), min(bx[2], saved_cull[2]), min(bx[3], saved_cull[3]))
            self._cull = bx
        try:
            for ox_, oy_ in offs:
                mi = Mat(1, 0, 0, 1, ox_, oy_).mul(m2) if (ox_ or oy_) else m2
                self.flatten(bname, mat.mul(mi), hide, nctx, dscale, depth + 1, out)
        finally:
            self._cull = saved_cull
        if len(out) <= n_in: cp = None
        if cp:         # XCLIP: the block content is cut to the clip polygon (block space -> final space with the same matrix as the content)
            from . import clip as _clip
            mfin = mat.mul(m2)
            out[n_in:] = _clip.clip_rows(out[n_in:], [mfin.apply(x, y) for x, y in cp])
        for a in self.attribs.get(e['handle'], ()):   # attributes are owned by the INSERT and live in the parent space
            try: self._entity(a, mat, hide, ctx, dscale, depth, out)
            except Exception: self.errors = getattr(self, 'errors', 0) + 1

    def _wipeout(self, e, mat, ly, col, out):
        """mask polygon from the image frame: clip points are in image space (-0.5..0.5 per axis, origin at the image centre of a 1x1 pixel grid)"""
        if not e.get('display', 7) & 1 and False: return
        o, u, v = e['pt0'], e['uvec'], e['vvec']
        clip = e.get('clip')
        if isinstance(clip, str): return
        if not clip: clip = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
        elif e.get('clip_type') == 1 and len(clip) == 2:
            (x0, y0), (x1, y1) = clip
            clip = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        pts = []
        for cx, cy in clip:
            wx = o[0] + (cx + 0.5) * u[0] + (cy + 0.5) * v[0]; wy = o[1] + (cx + 0.5) * u[1] + (cy + 0.5) * v[1]
            pts.append(mat.apply(wx, wy))
        if len(pts) > 2: out.append(('h', ly, col, [_flat(pts)], {'wipe': 1, 'solid': 1}, e['handle']))

    def _text(self, e, mat, ly, col, W, out):
        if not e.get('text'): return
        al = e.get('halign', 0) or 0; va = e.get('valign', 0) or 0
        fitw = None; rot_ = e['rot']
        if al in (3, 5):    # aligned / fit: first point = ins, second = align; the two points set rotation and width
            x, y = W(e['ins'][0], e['ins'][1], e['elev']); x2, y2 = W(e['align'][0], e['align'][1], e['elev'])
            fitw = math.hypot(x2 - x, y2 - y); rot_ = math.atan2(y2 - y, x2 - x) - mat.rot()
        elif al or va: x, y = W(e['align'][0], e['align'][1], e['elev'])
        else: x, y = W(e['ins'][0], e['ins'][1], e['elev'])
        st = self.style_of(e)
        sc_ = mat.scale_x()
        opts = {'hj': {0: 0, 1: 1, 2: 2, 3: 0, 4: 1, 5: 0}.get(al, 0), 'vj': va}
        if al == 4: opts['vj'] = 2
        if fitw: opts['fit'] = al; opts['fw'] = fitw
        if e.get('widthf') not in (None, 1.0): opts['wf'] = e['widthf']
        if e.get('oblique'): opts['ob'] = e['oblique']
        if e.get('mirror_x'): opts['mx'] = 1
        if e.get('mirror_y'): opts['my'] = 1
        if st:
            opts['font'] = st['font']
            if st.get('width_factor') not in (None, 1.0) and 'wf' not in opts: opts['wf'] = st['width_factor']
            if st.get('oblique') and 'ob' not in opts: opts['ob'] = st['oblique']
        if e['kind'] == 'ATTRIB' and re.search(r'\\[WwFfHhCcQqTtAaLlOoKkSsPp~]', e['text']): opts['mt'] = 1    # R2018 multiline attribute carries MTEXT codes
        out.append(('t', ly, col, x, y, e['height'] * sc_, rot_ + mat.rot(), e['text'], opts, e['handle']))

    def _mtext(self, e, mat, ly, col, out):
        x, y = mat.apply(e['ins'][0], e['ins'][1])
        ang = math.atan2(e['xdir'][1], e['xdir'][0]) + mat.rot()
        a = e['attachment']
        sc_ = mat.scale_x()
        opts = {'mt': 1, 'hj': (a - 1) % 3, 'vj': {0: 3, 1: 2, 2: 1}[(a - 1) // 3], 'w': (e.get('width') or 0) * sc_}
        if e.get('ext_w'): opts['ew'] = e['ext_w'] * sc_
        if e.get('ext_h'): opts['eh'] = e['ext_h'] * sc_
        if e.get('ls_factor') not in (None, 1.0): opts['ls'] = e['ls_factor']
        if e.get('drawdir') not in (None, 1, 5): opts['dd'] = e['drawdir']
        st = self.style_of(e)
        if st:
            opts['font'] = st['font']
            if st.get('width_factor') not in (None, 1.0): opts['wf'] = st['width_factor']
        bgf = e.get('bgflags') or 0
        if bgf and e.get('ext_w') and e.get('ext_h'):   # background mask / fill behind the text block
            h_ = e['text_height'] * sc_; mg = ((e.get('bg_scale') or 1.5) - 1.0) * h_
            ew, eh = e['ext_w'] * sc_ + 2 * mg, e['ext_h'] * sc_ + 2 * mg
            x0 = {0: -mg, 1: -ew / 2, 2: -ew + mg}[opts['hj']]; y0 = {3: -eh + mg, 2: -eh / 2, 1: -mg}[opts['vj']]
            ca, sa = math.cos(ang), math.sin(ang)
            quad = [(x + ca * px - sa * py, y + sa * px + ca * py) for px, py in ((x0, y0), (x0 + ew, y0), (x0 + ew, y0 + eh), (x0, y0 + eh))]
            bgc = (e.get('bg_color') or (0, None, 0))[1]
            info = {'solid': 1}
            fillc = col
            if (bgf & 2) or bgc is None: info['wipe'] = 1
            elif (bgc >> 24) == 0xC2: fillc = [(bgc >> 16) & 255, (bgc >> 8) & 255, bgc & 255]
            else: info['wipe'] = 1
            out.append(('h', ly, fillc, [_flat(quad)], info, e['handle']))
        if len(e.get('eed') or []) and any('AnnotativeData'.encode('utf-16le') in b or b'AnnotativeData' in b for a_, b in e['eed']):     # annotative: one layout per annotation scale, chosen by the viewport scale on the client
            if getattr(self, '_ac', None) is None: self._ac = AnnoContexts(self.m)
            cs = self._ac.mtext(e['handle'])
            if len(cs) > 1:
                d_ = next((c for c in cs if c['default']), cs[0])
                opts['ac'] = [[c['s'], *mat.apply(c['ins'][0], c['ins'][1]), math.atan2(c['xdir'][1], c['xdir'][0]) + mat.rot(), e['text_height'] * sc_ * d_['s'] / c['s'],
                               (c['w'] or 0) * sc_, c['ew'] * sc_, c['eh'] * sc_, (c['attach'] - 1) % 3, {0: 3, 1: 2, 2: 1}[(c['attach'] - 1) // 3]] for c in cs]
        txt_ = e['text']
        if 'ac' in opts and '\\pxq' not in txt_: txt_ = '\\pxql;' + txt_     # AutoCAD reports annotative MTEXT with an explicit left paragraph (390 of 521 in AC1027_13) and lays it out from the box's left edge (PDF strokes start at ins - width/2)
        out.append(('t', ly, col, x, y, e['text_height'] * sc_, ang, txt_, opts, e['handle']))

    def _hatch(self, e, mat, W, ly, col, out, lw=None):
        loops = []
        for p in e['paths']:
            pts = []
            if p['segs'] and all(sg[0] == 'P' for sg in p['segs']):    # polyline loop with bulges (closed)
                vs = [(sg[1], sg[2] if len(sg) > 2 else 0.0) for sg in p['segs']]
                n_ = len(vs)
                pts.append(vs[0][0])
                for i_ in range(n_):
                    pts.extend(bulge_points(vs[i_][0], vs[(i_ + 1) % n_][0], vs[i_][1]))
                if len(pts) > 1 and pts[-1] == pts[0]: pts.pop()
                if len(pts) > 2: loops.append(_flat([W(x, y, e['elev']) for x, y in pts]))
                continue
            for sg in p['segs']:
                if sg[0] == 'P': pts.append(sg[1])
                elif sg[0] == 'L': pts.extend([sg[1], sg[2]])
                elif sg[0] == 'A':
                    a0, a1 = sg[3], sg[4]
                    if not sg[5]: a0, a1 = 2 * math.pi - sg[4], 2 * math.pi - sg[3]    # clockwise edges store mirrored angles (matches the AutoCAD hatch extents)
                    ap = arc_points(sg[1][0], sg[1][1], sg[2], a0, a1, True)
                    if not sg[5]: ap.reverse()          # clockwise edges are traversed from the high-angle end: keep the chain order of the loop
                    pts.extend(ap)
                elif sg[0] == 'E':
                    c = sg[1]; mj = sg[2]; r = sg[3]; a0, a1 = sg[4], sg[5]
                    if len(sg) > 6 and not sg[6]: a0, a1 = 2 * math.pi - a1, 2 * math.pi - a0
                    if a1 <= a0: a1 += 2 * math.pi
                    ep = []
                    for i in range(33):
                        t = a0 + (a1 - a0) * i / 32
                        ep.append((c[0] + mj[0] * math.cos(t) - mj[1] * r * math.sin(t), c[1] + mj[1] * math.cos(t) + mj[0] * r * math.sin(t)))
                    if len(sg) > 6 and not sg[6]: ep.reverse()
                    pts.extend(ep)
                elif sg[0] == 'S':
                    cp = [c[0] for c in sg[5]]
                    wt = [c[1] for c in sg[5]] if sg[2] else None
                    try: pts.extend(bspline_fast(sg[1], sg[4], cp, wt))
                    except Exception: pts.extend(cp)
            if len(pts) > 2: loops.append(_flat([W(x, y, e['elev']) for x, y in pts]))
        if not loops: return
        info = {'solid': 1 if e['solid'] else 0}
        if not e['solid'] and e.get('pattern_lines'):
            lines = []
            for ang, org, off, dsh in e['pattern_lines']:
                ox, oy = mat.apply(org[0], org[1])
                # direction and offset vectors under the matrix (linear part only)
                dx, dy = math.cos(ang), math.sin(ang)
                ax = mat.a * dx + mat.b * dy; ay = mat.c * dx + mat.d * dy
                fx = mat.a * off[0] + mat.b * off[1]; fy = mat.c * off[0] + mat.d * off[1]
                k = mat.scale_x()
                lines.append([math.atan2(ay, ax), ox, oy, fx, fy, [d * k for d in dsh]])
            info['lines'] = lines
            info['pat'] = e.get('pattern_name')
            if lw: info['w'] = lw      # lineweight (mm) of the pattern lines
        g = e.get('gradient') or {}
        if g.get('is_gradient'): info['grad'] = {'name': g.get('name'), 'angle': g.get('angle'), 'colors': g.get('colors')}
        out.append(('h', ly, col, loops, info, e['handle']))


try:    # optional Rust fast path (dwgscene_fast.abi3.so next to dwgfast); DWG_NO_FAST=1 disables it
    if not os.environ.get('DWG_NO_FAST'):
        import sys as _sys
        from . import fastflat as _ff
        _ff.install(_sys.modules[__name__])
except Exception:
    pass
