"""prototype: memoise Flattener.resolve (no viewer edits); compares scene content + time"""
import sys, os, time, json
sys.path.insert(0, os.path.expanduser('~/dwg-viewer'))
from dwgviewer import build, flat as F
f = sys.argv[1]
def run(patch):
    orig = F.Flattener.resolve
    if patch:
        def resolve(self, e, ctx):
            c = e['color']
            if e.get('ltflags') == 3: return orig(self, e, ctx)
            k = (e.get('layer'), tuple(c), e.get('lweight'), e.get('ltflags'), ctx.color if not isinstance(ctx.color, list) else tuple(ctx.color), ctx.lw, ctx.lt, ctx.layer)
            m = self.__dict__.setdefault('_rmemo', {})
            r = m.get(k)
            if r is None:
                r = m[k] = orig(self, e, ctx)
            return (r[0], list(r[1]) if isinstance(r[1], list) else r[1], r[2], r[3])
        F.Flattener.resolve = resolve
    try:
        d = build.Doc(f); m = d.meta(); t = time.time(); out = []
        for l in m['layouts']:
            for tw in ((True, False) if not l['ps'] else (True,)):
                s = d.layout(l['i'], tw); s.pop('build_s', None); out.append(json.dumps(s, sort_keys=True))
        return time.time() - t, out
    finally: F.Flattener.resolve = orig
ta, a = run(False); tb, b = run(True)
print(os.path.basename(f), 'baseline %.2f' % ta, 'memo %.2f' % tb, 'IDENTICAL' if a == b else 'DIFF')
