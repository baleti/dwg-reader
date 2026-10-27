"""Build the viewer scene JSON from a .dwg: layer table, layout list, per-layout primitive lists.
Scene format v2 (JSON). Per layout: {"paper":[w,h]|null,"bounds":[x0,y0,x1,y1],"prims":[...],"vps":[{"clip":[x,y,...],"prims":[...],"id":handle,"scale":s}]}
Rows (layer = index into meta.layers, -1 none; colour = ACI int (7 = foreground) or [r,g,b]):
 ["l", ly, col, lw_mm, dash|0, [x0,y0,x1,y1,...], handle]        polyline, dash = signed pattern in final units
 ["h", ly, col, [[x,y,...],...], info, handle]                    hatch (info: solid, pat, lines, grad)
 ["t", ly, col, x, y, height, rot_rad, text, opts, handle]        text/mtext (raw text, opts hj vj w font wf ob ...)
 ["p", ly, col, x, y, handle]                                     point
"""
import os, sys, math, time, struct
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import dwgscene, dwgmodel, dwgent
from . import vport as VP
from dwgscene import Mat
from . import flat as F
from .annoctx import AnnoContexts
from . import ole as OLE  # noqa: F401  (importing registers the OLE2FRAME decoder)
from . import fastbits
try:
    if os.environ.get('DWG_NO_FAST'): raise ImportError
    import dwgscene_fast as _R0, dwgbits as _B0
    _B0.Bits = _R0.Bits     # native bit reader (dwgscene-fast/tests/bits_parity.py)
except ImportError:
    fastbits.apply()    # bit-identical, about 1.5-2x faster object decoding (tools/chk_fastbits.py)


def fixname(n):
    """stop-gap for names the parser decoded as latin1 although the file codepage is a CJK ANSI page (NEEDS-FROM-PARSER 2)"""
    if not n or all(ord(c) < 128 for c in n) or any(ord(c) > 255 for c in n): return n
    try: raw = n.encode('latin1')
    except Exception: return n
    for cp in ('gbk', 'cp932', 'cp949', 'big5'):
        try: t = raw.decode(cp)
        except Exception: continue
        if all(ord(c) < 128 or 0x3000 <= ord(c) <= 0x9fff or 0xac00 <= ord(c) <= 0xd7af or 0xff00 <= ord(c) <= 0xffef for c in t): return t
    return n


def _round(f, n=3):
    return [round(v, n) for v in f]


try:
    import dwgscene_fast as _R
    if not os.environ.get('DWG_NO_FAST'): _round = _R.round_list
except Exception:
    pass


def _nobb(x, y, g=True): pass
_nobb.many = lambda xs, ys: None
_NOBB = _nobb


class Doc:
    def __init__(self, path, header=None, _stack=()):
        self.path = path
        self._stack = tuple(_stack) + (os.path.realpath(path),)    # xref cycle guard
        t = time.time()
        self.sc = dwgscene.Scene(open(path, 'rb').read())
        self.parse_s = time.time() - t
        self.m = self.sc.m
        self.lays = self.m.layouts()
        self.ltab = self.m.layer_table()
        self.lnames = list(self.ltab)
        self.lidx = {n: i for i, n in enumerate(self.lnames)}
        try: hv = {k.lower(): v for k, v in self.m.header().items()}
        except Exception: hv = {}
        hv.update(header or {})
        self.fl = F.Flattener(self.sc, hv)
        self.fl.xref_resolver = self._xref_child
        self.model_name = next((n for n in self.m.blocks.values() if n.lower() == '*model_space'), None)
        self._cache = {}
        try: self.vport = next((v for v in VP.active(self.m) if v['name'].lower() == '*active'), None)
        except Exception: self.vport = None

    # ---- meta ----
    def used_layers(self):
        if getattr(self, '_used', None) is None:
            u = set()
            for es in self.sc.by_block.values():
                for e in es:
                    if e.get('layer') is not None: u.add(e['layer'])
            self._used = u
        return self._used

    def layer_eed(self, h):
        """(description, transparency percent) of a LAYER from its extended data (apps AcAecLayerStandard / AcCmTransparency), own decoding checked against the dump"""
        desc, tr = '', 0
        try:
            o = self.m.objs[h]; r = dwgent.start_reader(o)
            while True:
                n = r.BS()
                if n == 0: break
                app = r.H(); data = bytes(r.RC() for _ in range(n))
                nm = dwgmodel.table_entry_name(self.m.objs[app[1]]) if app[1] in self.m.objs else ''
                if nm == 'AcAecLayerStandard' and len(data) >= 6:
                    if self.m.version in ('AC1015', 'AC1018'):    # 8-bit text in the file code page, big-endian length at 4
                        ln = int.from_bytes(data[4:6], 'big')
                        desc = dwgmodel.decode_tv(data[8:8 + ln].decode('latin1'), self.m.codepage)
                    else:                                          # groups of [00][len16][UTF-16 chars]: style name, then description
                        i, strs = 0, []
                        while i + 3 <= len(data) and data[i] == 0:
                            ln = int.from_bytes(data[i + 1:i + 3], 'little'); strs.append(data[i + 3:i + 3 + 2 * ln].decode('utf-16le', 'ignore')); i += 3 + 2 * ln
                        desc = strs[-1] if strs else ''
                elif nm == 'AcCmTransparency' and len(data) >= 5 and data[0] == 0x47:
                    v = int.from_bytes(data[1:5], 'little')
                    if (v >> 24) == 2: tr = round((255 - (v & 255)) / 255 * 100)
        except Exception:
            pass
        return desc, tr

    def layers(self):
        out = []
        used = self.used_layers()
        for n in self.lnames:
            d = self.ltab[n]
            out.append({'n': n, 'c': self.fl.layer_color(n), 'lw': d.get('lineweight_mm'), 'lt': d.get('ltype'),
                        'off': bool(d.get('off')), 'frz': bool(d.get('frozen')), 'lock': bool(d.get('locked')), 'plot': bool(d.get('plot', True)), 'used': n in used, 'tr': self.layer_eed(d.get('handle'))[1], 'desc': self.layer_eed(d.get('handle'))[0]})
        return out

    def layout_list(self):
        res = []
        for i, l in enumerate(self.lays):
            ps = l['name'].lower() != 'model'
            ok = ps and self.paper(l)[0] > 0 and self.paper(l)[1] > 0
            res.append({'i': i, 'name': l['name'], 'paper': list(self.paper(l)) if ok else None, 'ps': ps, 'style': l.get('style_sheet') or ''})
        return res

    @staticmethod
    def paper(lay):
        """paper size as plotted: PlotRotation 1 or 3 (90 / 270 degrees) swaps width and height"""
        w, h = lay['paper']
        return (h, w) if lay.get('rotation') in (1, 3) else (w, h)

    def layout_entities(self, lay):
        if lay['block'] is not None: return self.fl.by_owner.get(lay['block'], [])
        return self.sc.block_content(lay['block_name'])

    def default_layout(self):
        """first paper layout that has content (own entities or a viewport), else 0 (Model)"""
        for i, l in enumerate(self.lays):
            if l['name'].lower() == 'model': continue
            if len(self.layout_entities(l)) > 1 or len(l['viewports']) > 1: return i
        return 0

    def _xref_headers(self):
        """{BLOCK_HEADER handle: dict(name, path, found, overlay, file)} of the xref blocks; file = the DWG that exists next to the drawing or at the stored path"""
        if getattr(self, '_xh', None) is not None: return self._xh
        out = {}
        try:
            import dwgtab
            here = os.path.dirname(os.path.abspath(self.path))
            for h, o in self.m.objs.items():
                if o.type != 49: continue
                d = dwgtab.decode_block_header(o)
                if not d.get('is_xref'): continue
                p = dwgmodel.decode_tv(d['xref_path'], self.m.codepage) if isinstance(d['xref_path'], str) else d['xref_path']
                p = str(p or '').replace('\\', '/')
                base = os.path.basename(p)
                cands = [os.path.join(here, p), os.path.join(here, base), p] + [os.path.join(x, base) for x in os.environ.get('DWG_XREF_PATH', '').split(os.pathsep) if x] if base else []
                fn = next((c for c in cands if os.path.isfile(c)), None)
                out[h] = {'name': (self.m.blocks.get(h) or d.get('name') or '').split('~')[0], 'path': p, 'found': bool(fn), 'overlay': bool(d.get('overlaid')), 'file': fn}
        except Exception:
            pass
        self._xh = out
        return out

    def xref_list(self):
        """external references for the toolbar: [{name, path, found, overlay}]"""
        return [{k: v for k, v in x.items() if k != 'file'} for x in self._xref_headers().values()]

    def _xref_child(self, bh):
        """(child Doc, layer prefix) of the xref block with BLOCK_HEADER handle bh when its DWG exists next to the drawing, else None; children are cached"""
        x = self._xref_headers().get(bh)
        if not x or not x['file']: return None
        cache = self.__dict__.setdefault('_xchild', {})
        if bh not in cache:
            rp = os.path.realpath(x['file'])
            try:
                cache[bh] = None if rp in self._stack or len(self._stack) > 4 else Doc(x['file'], _stack=self._stack)
            except Exception:
                cache[bh] = None
        c = cache[bh]
        return (c, x['name'] + '|') if c else None

    def file_layer_states(self):
        """named layer states stored in the drawing (ACAD_LAYERSTATES): {name: {desc, cur, on: [layer names saved on], off: [saved off]}}; negative colour = layer off, other flag bits are not calibrated"""
        try:
            out = {}
            for nm, st in self.m.layer_states().items():
                rows = [r for r in st['layers'] if r.get('name') in self.ltab]
                out[nm] = {'desc': st.get('description') or '', 'cur': st.get('current'),
                           'on': [r['name'] for r in rows if (r.get('color') or 0) >= 0], 'off': [r['name'] for r in rows if (r.get('color') or 0) < 0]}
            return out
        except Exception:
            return {}

    def meta(self):
        return {'v': 3, 'current': self.fl.h.get('clayer'), 'file': os.path.basename(self.path), 'insunits': (self.fl.h or {}).get('insunits') or 0, 'xrefs': self.xref_list(), 'layers': self.layers(), 'fstates': self.file_layer_states(), 'layouts': self.layout_list(), 'parse_s': round(self.parse_s, 2), 'default': self.default_layout(),
                'ltypes': {n: [d['length'] for d in l['dashes']] for n, l in self.m.ltypes().items() if l['dashes']}}

    # ---- rows ----
    def _row(self, p, bb):
        k = p[0]
        li = self.lidx.get(p[1], -1) if p[1] else -1
        if k == 'l':
            f = p[5]
            bb.many(f[0::2], f[1::2])
            return ['l', li, p[2], p[3], p[4] or 0, _round(f), p[6], round(p[7], 4) if p[7] else 0, p[8]]
        if k == 'h':
            for l in p[3]:
                bb.many(l[0::2], l[1::2])
            return ['h', li, p[2], [_round(l) for l in p[3]], p[4], p[5], p[6]]
        if k == 't':
            o = p[8]; h = p[5]
            w = o.get('ew') or (min(len(p[7]), 200) * 0.5 * h * o.get('wf', 1.0))
            hj = o.get('hj', 0); x0 = p[3] - (w / 2 if hj == 1 else w if hj == 2 else 0)
            for dx, dy in ((0, 0), (w, h)):   # text extent box (rotation ignored): counts for the drawn extents like AutoCAD's zoom extents
                bb(x0 + dx, p[4] + dy, bool(o.get('ew')))
            return ['t', li, p[2], round(p[3], 3), round(p[4], 3), round(p[5], 4), round(p[6], 5), p[7], p[8], p[9], p[10]]
        if k == 'p':
            bb(p[3], p[4], False)
            return ['p', li, p[2], round(p[3], 3), round(p[4], 3), p[5], p[6]]

    def _viewports(self, lay):
        """[(vp dict, frozen layer set)] for the non-overall viewports of a paper layout"""
        m = self.m
        res = []
        vhs = list(dict.fromkeys(lay['viewports']))
        for e in self.layout_entities(lay):
            if e['kind'] == 'VIEWPORT' and e['handle'] not in vhs and e.get('owner') == lay['block'] and (self.m.version in ('AC1015', 'AC1021') or len(vhs) < 2): vhs.append(e['handle'])   # R2000 layouts list none; some R2007 layouts list only the active one
        for vh in vhs:
            o = m.objs[vh]
            try:
                v = m.decode_viewport(o) if hasattr(m, 'decode_viewport') else dwgent.decode_viewport(o)    # R13/R14 reader: viewport data lives in the MVIEW xdata
            except Exception:
                continue
            if hasattr(m, 'decode_viewport'):
                v.setdefault('status', 0)
                v['handle'] = vh; v['anno'] = None; v['clip_poly'] = None
                if v['width'] <= 0 or v['height'] <= 0 or v['view_height'] <= 0: continue
                pc = v['center']
                if abs(v['view_center'][0] - pc[0]) < 1e-6 and abs(v['view_center'][1] - pc[1]) < 1e-6 and abs(v['view_target'][0]) < 1e-6 and abs(v['view_target'][1]) < 1e-6: continue
                try: frozen = set(m.viewport_frozen(o))
                except Exception: frozen = set()
                res.append((v, frozen)); continue
            if v['width'] <= 0 or v['height'] <= 0 or v['view_height'] <= 0: continue
            if v['status'] & 0x20000: continue    # status bit 17: the viewport is turned off (AC1018_34: 2 of 4 viewports; the dump reports on=False / number -1)
            pc = v['center']
            if abs(v['view_center'][0] - pc[0]) < 1e-6 and abs(v['view_center'][1] - pc[1]) < 1e-6 and abs(v['view_target'][0]) < 1e-6 and abs(v['view_target'][1]) < 1e-6:
                continue   # the paper-space overall viewport (view centre = viewport centre, target at origin)
            hs = dwgmodel.resolve_handles(o)
            first_layer = next((x for c, x in hs if c == 5), None)
            frozen = set()
            c4 = [x for c, x in hs if c == 4 and x in m.objs and m.objs[x].type == 51]   # frozen layer handles are hard pointers (code 4); the viewport's own layer can be among them
            if c4:
                frozen = {m.layers.get(x) for x in c4[:v['nfrozen']]}
            else:
                for c, x in hs:
                    if x in m.objs and m.objs[x].type == 51 and x != first_layer and len(frozen) < v['nfrozen']:
                        frozen.add(m.layers.get(x))
            if os.environ.get('DWGVIEW_NOFREEZE'): frozen = set()
            v['handle'] = vh
            v['anno'] = self._vp_anno(o)
            v['clip_poly'] = None
            if v['status'] & 0x10000:
                ent = next((x for c, x in hs if c == 5 and x in m.objs and m.objs[x].type != 51 and x != first_layer and x != 0 and m.objs[x].type in (77, 19, 18, 35, 15, 16)), None)
                v['clip_poly'] = self._clip_polygon(ent)
            res.append((v, frozen))
        return res

    def _clip_polygon(self, h):
        """flat polygon of a clipping entity (LWPOLYLINE, CIRCLE, ELLIPSE, POLYLINE) in paper space, or None"""
        if h is None: return None
        if not hasattr(self, '_by_handle'):
            self._by_handle = {e['handle']: e for es in self.sc.by_block.values() for e in es}
        e = self._by_handle.get(h)
        if e is None: return None
        out = []
        try: self.fl._entity(dict(e, layer='0', invis=0), Mat(), frozenset(), F.Ctx(), 1.0, 0, out)
        except Exception: return None
        for p in out:
            if p[0] == 'l' and len(p[5]) >= 6: return list(p[5])
        return None

    def _vp_anno(self, o):
        """annotation scale (paper/drawing) of a viewport: its extension dictionary holds the xrecord ASDK_XREC_ANNOTATION_SCALE_INFO = [90 version, 340 SCALE handle]; None when absent"""
        try:
            if getattr(self, '_actx', None) is None: self._actx = AnnoContexts(self.m)
            for c, x in dwgmodel.resolve_handles(o):
                if c != 3 or x not in self.m.objs: continue
                for c2, xr in dwgmodel.resolve_handles(self.m.objs[x]):
                    if c2 != 2 or xr not in self.m.objs or self.m.objs[xr].type != 79: continue
                    r = dwgent.start_reader(self.m.objs[xr])
                    while True:
                        n = r.BS()
                        if n == 0: break
                        r.H(); r.p += 8 * n
                    r.BL(); r.B(); r.B()
                    data = bytes(r.RC() for _ in range(r.BL()))
                    i = 0
                    while i + 2 <= len(data):
                        code = struct.unpack_from('<h', data, i)[0]; i += 2
                        if 90 <= code <= 99: i += 4
                        elif 320 <= code <= 369:
                            return self._actx.scale_of(struct.unpack_from('<q', data, i)[0])
                        else: break
        except Exception: pass
        return None

    def origin(self):
        """model-space shift: canvas paths are float32, so georeferenced coordinates (1e8) must be moved near zero; header EXTMIN/EXTMAX centre, else drawn-extents centre"""
        if getattr(self, '_org', None) is not None: return self._org
        o = (0.0, 0.0)
        lo, hi = self.fl.h.get('extmin'), self.fl.h.get('extmax')
        try:
            if lo and hi and abs(hi[0]) < 1e15 and abs(lo[0]) < 1e15 and hi[0] >= lo[0]:
                o = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
        except Exception: pass
        if abs(o[0]) < 1e5 and abs(o[1]) < 1e5:
            o = (0.0, 0.0)
        self._org = o
        return o

    def kinds_of(self, *row_lists):
        """{top handle: category} for the objects of these rows: dim, leader, block, text, hatch, image, point, curve"""
        if not hasattr(self, '_by_handle'):
            self._by_handle = {e['handle']: e for es in self.sc.by_block.values() for e in es}
        cat = {'INSERT': 'block', 'LEADER': 'leader', 'MTEXT': 'text', 'TEXT': 'text', 'ATTRIB': 'text', 'HATCH': 'hatch', 'IMAGE': 'image', 'WIPEOUT': 'wipeout', 'POINT': 'point', 'OLE2FRAME': 'ole', 'REGION': 'solid', '3DSOLID': 'solid', 'BODY': 'solid'}
        out = {}
        for rows in row_lists:
            for p in rows:
                t = p[-1]
                if t in out: continue
                e = self._by_handle.get(t)
                k = e['kind'] if e else ''
                out[t] = 'dim' if k.startswith('DIM') else cat.get(k, 'curve')
        return out

    def model_rows(self):
        """model-space primitives in model units, shared by every viewport of every paper layout"""
        if getattr(self, '_mrows', None) is None:
            ox, oy = self.origin()
            self._mrows = [self._row(p, _NOBB) for p in self.fl.flatten(self.model_name, Mat(1, 0, 0, 1, -ox, -oy) if (ox or oy) else None)]
        return self._mrows

    def layout(self, i, twist=True):
        key = (i, bool(twist))
        if key in self._cache: return self._cache[key]
        t = time.time()
        lay = self.lays[i]
        ps = lay['name'].lower() != 'model'
        bxs = []; bys = []; gxs = []; gys = []

        def bb(x, y, geo=True):
            bxs.append(x); bys.append(y)
            if geo: gxs.append(x); gys.append(y)

        def bb_many(xs, ys):
            bxs.extend(xs); bys.extend(ys); gxs.extend(xs); gys.extend(ys)
        bb.many = bb_many
        blk = self.model_name if not ps else (lay['block_name'] if lay['block'] is None else lay['block'])   # by BLOCK_HEADER handle: several layouts can share a block name
        M0 = None
        tw0 = self.vport['twist'] if (self.vport and not ps and twist) else 0.0
        ox, oy = self.origin()
        if not ps and (ox or oy): M0 = Mat(1, 0, 0, 1, -ox, -oy)
        if abs(tw0) > 1e-9:
            c_, s_ = math.cos(tw0), math.sin(tw0); M0 = Mat(c_, -s_, s_, c_, 0, 0).mul(M0 or Mat())
        prims = [self._row(p, bb) for p in self.fl.flatten(blk, M0)]
        vps = []
        if ps:
            vlist = self._viewports(lay)
            if True:    # viewport borders are plotted as hairlines on the viewport's layer (oversized/switched-off viewports are not; with an unknown paper size (R2007 plot settings) no size test)
                W_, H_ = self.paper(lay)
                if not (W_ > 0 and H_ > 0): W_ = H_ = float('inf')
                ents = {e['handle']: e for e in self.layout_entities(lay) if e['kind'] == 'VIEWPORT'}
                for v, frozen in vlist:
                    e = ents.get(v['handle'])
                    if not e or v['width'] > 1.05 * W_ or v['height'] > 1.05 * H_: continue
                    cx, cy = v['center'][0], v['center'][1]; hw, hh = v['width'] / 2, v['height'] / 2
                    pts = v.get('clip_poly') or [cx - hw, cy - hh, cx + hw, cy - hh, cx + hw, cy + hh, cx - hw, cy + hh]
                    pts = list(pts) + pts[:2]
                    prims.append(['l', self.lidx.get(e.get('layer'), -1), self.fl.layer_color(e.get('layer')), 0.0, 0, _round(pts), v['handle'], 0, v['handle']])
                    for x_, y_ in zip(pts[0::2], pts[1::2]): bb(x_, y_)
            for v, frozen in vlist:
                pc = v['center']
                s = v['height'] / v['view_height']
                tx, ty = v['view_target'][0], v['view_target'][1]
                tw = v['twist']
                ct, st = math.cos(tw), math.sin(tw)    # DCS = R(+twist) * (P - target): checked against the dump view centre
                vcx, vcy = v['view_center']
                M = Mat(1, 0, 0, 1, pc[0] - s * vcx, pc[1] - s * vcy).mul(Mat(s * ct, -s * st, s * st, s * ct, 0, 0)).mul(Mat(1, 0, 0, 1, -tx, -ty)).mul(Mat(1, 0, 0, 1, ox, oy))
                psl = 1 if self.fl.h.get('psltscale', 1) else 0
                xmin, xmax = pc[0] - v['width'] / 2, pc[0] + v['width'] / 2
                ymin, ymax = pc[1] - v['height'] / 2, pc[1] + v['height'] / 2
                mw, mh = v['width'] / s, v['height'] / s
                cwx = tx + math.cos(tw) * vcx + math.sin(tw) * vcy; cwy = ty - math.sin(tw) * vcx + math.cos(tw) * vcy   # model-space point shown at the viewport centre
                vps.append({'id': v['handle'], 'scale': s, 'mwin': [cwx - mw / 2 - ox, cwy - mh / 2 - oy, cwx + mw / 2 - ox, cwy + mh / 2 - oy], 'twist': tw,
                            'frozen': sorted(self.lidx[n] for n in frozen if n in self.lidx), 'clip': v.get('clip_poly') or [xmin, ymin, xmax, ymin, xmax, ymax, xmin, ymax],
                            'M': [M.a, M.c, M.b, M.d, M.tx, M.ty], 'psl': psl, 'an': v.get('anno')})
                bb(xmin, ymin); bb(xmax, ymax)
        paper_ok = ps and self.paper(lay)[0] > 0 and self.paper(lay)[1] > 0
        if paper_ok and gxs and (max(gxs) - min(gxs) > 3 * self.paper(lay)[0] or max(gys) - min(gys) > 3 * self.paper(lay)[1]):
            paper_ok = False    # the stored paper size does not describe where the sheet is drawn (e.g. an A4 default with a metre-scaled layout)
        porg = (0.0, 0.0)       # the sheet sits at the plot window's corner when the layout is plotted by window and that window holds the content
        w_ = lay.get('window')
        if paper_ok and lay.get('plot_type') == 4 and w_ and gxs and (w_[0] or w_[1]):
            pw, ph = self.paper(lay)
            ix = min(max(gxs), w_[0] + pw) - max(min(gxs), w_[0]); iy = min(max(gys), w_[1] + ph) - max(min(gys), w_[1])
            ox0, oy0 = min(max(gxs), 0 + pw) - max(min(gxs), 0), min(max(gys), 0 + ph) - max(min(gys), 0)
            if ix > 0 and iy > 0 and (ix * iy > 2 * max(ox0, 0) * max(oy0, 0) if ox0 > 0 and oy0 > 0 else True): porg = (w_[0], w_[1])
        if paper_ok and lay.get('plot_type') == 1 and lay.get('scale_type') == 0 and gxs and not os.environ.get('DWG_NO_EXTFIT'):
            # plotted by Extents, scaled to fit: the sheet is the content extents scaled onto the paper (centred), not the paper rectangle at 1:1
            pw, ph = self.paper(lay)
            x0, y0, x1, y1 = min(gxs), min(gys), max(gxs), max(gys)
            cw, ch = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
            k = max(cw / pw, ch / ph)
            if k > 1.02 or k < 0.98:
                bw, bh = pw * k, ph * k
                bounds = [(x0 + x1) / 2 - bw / 2, (y0 + y1) / 2 - bh / 2, (x0 + x1) / 2 + bw / 2, (y0 + y1) / 2 + bh / 2]
            else:
                bounds = [porg[0], porg[1], porg[0] + pw, porg[1] + ph]
        elif paper_ok:
            bounds = [porg[0], porg[1], porg[0] + self.paper(lay)[0], porg[1] + self.paper(lay)[1]]
        elif bxs:
            xs = sorted(bxs); ys = sorted(bys); n = len(xs)
            lo, hi = int(n * 0.004), max(int(n * 0.996) - 1, 0)
            bounds = [xs[lo], ys[lo], xs[hi], ys[hi]] if ps is False else [xs[0], ys[0], xs[-1], ys[-1]]
        else:
            bounds = [0, 0, 100, 100]
        full = [min(gxs), min(gys), max(gxs), max(gys)] if gxs else bounds
        r = {'full': full, 'paper': list(self.paper(lay)) if paper_ok else None, 'bounds': bounds, 'prims': prims, 'vps': vps, 'mprims': self.model_rows() if vps else [], 'kinds': self.kinds_of(prims, self.model_rows() if vps else []),
             'n': len(prims) + (len(self.model_rows()) * len(vps) if vps else 0), 'build_s': round(time.time() - t, 2), 'twist': tw0, 'errors': getattr(self.fl, 'errors', 0), 'ea': dict(getattr(self.fl, 'ealpha', {})), 'tl': {h: self.lidx[n] for h, n in getattr(self.fl, 'toplayer', {}).items() if n in self.lidx}}
        self._cache[key] = r
        return r
