"""Optional Rust fast path for flat.Flattener.flatten: install(F) patches the class in place. Entities of simple kinds are built in
dwgscene_fast.flatten_block; everything else (and anything unusual) goes through the unchanged Python per-entity code, in the original order."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
try:
    import dwgscene_fast as R
except ImportError:
    from . import dwgscene_fast as R


def install(F):
    orig_flatten = F.Flattener.flatten
    import dwgmodel

    def miss_for(self, ctx):
        def miss(e):
            try:
                ly, col, lw, lt = self.resolve(e, ctx)
                ltn = self.lts.get(lt) if lt else None
                ds = None
                if ltn:
                    d = [x['length'] for x in ltn['dashes'] if not x.get('shape') and not (x.get('flags', 0) & 6)]
                    if d and not all(abs(x) < 1e-12 for x in d): ds = d
                return (ly, col, lw, ds, self.ltscale)
            except Exception:
                return None
        return miss

    def flatten(self, block_name, mat=None, hide=frozenset(), ctx=None, dscale=1.0, depth=0, out=None):
        if os.environ.get('DWG_NO_FAST') or getattr(self, '_cull', None) is not None and not os.environ.get('DWG_NO_CULL'):
            return orig_flatten(self, block_name, mat, hide, ctx, dscale, depth, out)
        mat = mat or F.Mat(); ctx = ctx or F.Ctx(); out = [] if out is None else out
        if depth > 8: return out
        content = self.by_owner.get(block_name, []) if isinstance(block_name, int) else self.sc.block_content(block_name)
        if not isinstance(content, list): content = list(content)
        ck = (tuple(ctx.color) if isinstance(ctx.color, list) else ctx.color, ctx.lw, ctx.lt, ctx.layer)
        fc = self.__dict__.setdefault('_fcache', {})
        ent = fc.get(ck)
        if ent is None:
            ent = fc[ck] = ({}, miss_for(self, ctx))
        res = R.flatten_block(content, (mat.a, mat.b, mat.c, mat.d, mat.tx, mat.ty), set(hide), dscale, depth == 0, ent[0], ent[1])
        for it in res:
            if type(it) is int:
                self._one(content[it], mat, hide, ctx, dscale, depth, out)
            else:
                out.append(it)
        return out

    def _one(self, e, mat, hide, ctx, dscale, depth, out):
        """the per-entity body of Flattener.flatten, unchanged"""
        n0 = len(out)
        try:
            self._entity(e, mat, hide, ctx, dscale, depth, out)
            if len(out) > n0:
                a_ = e.get('color') and len(e['color']) > 2 and e['color'][2]
                if a_ and (a_ >> 24) == 2 and (a_ & 255) < 255:
                    al_ = round((a_ & 255) / 255, 3)
                    if depth == 0:
                        if not hasattr(self, 'ealpha'): self.ealpha = {}
                        self.ealpha[e['handle']] = al_
                    for i in range(n0, len(out)):
                        r_ = out[i]
                        if r_[0] == 'h' and isinstance(r_[4], dict): out[i] = r_[:4] + (dict(r_[4], a=al_),) + r_[5:]
            if len(out) > n0 and not F._sane(out[n0:]): del out[n0:]
            if depth == 0 and e['kind'] in ('INSERT', 'MINSERT') and len(out) > n0:
                ly0 = e.get('layer')
                if ly0 and any(r_[1] != ly0 for r_ in out[n0:]):
                    if not hasattr(self, 'toplayer'): self.toplayer = {}
                    self.toplayer[e['handle']] = ly0
            if depth == 0:
                for i in range(n0, len(out)): out[i] = out[i] + (e['handle'],)
        except TypeError as ex:
            if 'NoneType' not in str(ex): self.errors = getattr(self, 'errors', 0) + 1
        except Exception:
            self.errors = getattr(self, 'errors', 0) + 1

    try:
        from dwgviewer import build as _b
        _b._round = R.round_list
    except Exception: pass
    F.Flattener.flatten = flatten
    F.Flattener._one = _one
    return orig_flatten
