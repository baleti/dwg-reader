"""bit-exact parity of dwgscene_fast kernels vs the Python originals (random inputs). Usage: python3 tests/parity.py"""
import sys, os, math, random, struct
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..')); sys.path.insert(0, os.path.expanduser('~/dwg-viewer')); sys.path.insert(0, os.path.expanduser('~/dwg-viewer/dwgviewer'))
import dwgscene_fast as R
from dwgscene import Mat, arc_points, bulge_points, ocs_axes
import importlib.util
sp = importlib.util.spec_from_file_location('flat_', os.path.expanduser('~/dwg-viewer/dwgviewer/flat.py'))
rnd = random.Random(7); bad = 0; ulp = 0
def bits(v): return [struct.pack('<d', x) for x in v]
def chk(name, a, b):
    global bad, ulp
    if bits(a) != bits(b):
        if name == 'lwpoly' and max(abs(x - y) for x, y in zip(a, b)) < 1e-9: ulp += 1; return   # hypot: libm vs CPython's own

        bad += 1; print('DIFF', name, len(a), len(b)); return
# round
vals = [rnd.uniform(-1e5, 1e5) for _ in range(200000)] + [k / 2000 for k in range(-4000, 4000)] + [0.0005, -0.0005, 1.0005, 2.675, -0.0, -0.0001, 1e15, 1e-9, 123456789.1235, 0.1235, 0.0125]
for n in (3, 4, 5, 6, 2, 1):
    chk('round%d' % n, R.round_list(vals, n), [round(v, n) for v in vals])
# arc / circle
for _ in range(3000):
    M = Mat(*[rnd.uniform(-3, 3) for _ in range(6)]); m6 = (M.a, M.b, M.c, M.d, M.tx, M.ty)
    c = (rnd.uniform(-100, 100), rnd.uniform(-100, 100), rnd.uniform(-5, 5)); r = rnd.uniform(0.1, 50)
    a0 = rnd.uniform(-7, 7); a1 = rnd.choice([2 * math.pi, rnd.uniform(-7, 7)]); 
    if a1 == 2 * math.pi: a0 = 0
    ext = rnd.choice([(0.0, 0.0, 1.0), (0.3, -0.4, 0.8660254037844386)])
    if ext == (0.0, 0.0, 1.0): W = lambda x, y, z=0.0: M.apply(x, y); ax = None
    else:
        _ax, _ay, _az = ocs_axes(ext); ax = (_ax, _ay, _az)
        W = lambda x, y, z=0.0: M.apply(_ax[0]*x + _ay[0]*y + _az[0]*z, _ax[1]*x + _ay[1]*y + _az[1]*z)
    ref = [v for p in (W(x, y, c[2]) for x, y in arc_points(c[0], c[1], r, a0, a1)) for v in p]
    chk('arc', R.arc_flat(c, r, a0, a1, m6, ax), ref)
# ellipse
src = open(os.path.expanduser('~/dwg-viewer/dwgviewer/flat.py')).read()
ns = {}
exec(src[src.index('def _ell_pts'):src.index('def bspline_fast')], {'math': math, **ns}, ns)
ell = ns['_ell_pts']
for _ in range(3000):
    M = Mat(*[rnd.uniform(-3, 3) for _ in range(6)]); m6 = (M.a, M.b, M.c, M.d, M.tx, M.ty)
    c = (rnd.uniform(-100, 100), rnd.uniform(-100, 100), 0.0); mj = (rnd.uniform(-9, 9), rnd.uniform(-9, 9), 0.0)
    r = rnd.uniform(0.05, 1); a0 = rnd.uniform(0, 6.3); a1 = rnd.uniform(0, 6.3)
    chk('ell', R.ell_flat(c, mj, r, a0, a1, m6), [v for p in ell(c, mj, r, a0, a1, M) for v in p])
# lwpolyline path
for _ in range(3000):
    M = Mat(*[rnd.uniform(-3, 3) for _ in range(6)]); m6 = (M.a, M.b, M.c, M.d, M.tx, M.ty)
    n = rnd.randint(1, 12); pts = [(rnd.uniform(-50, 50), rnd.uniform(-50, 50)) for _ in range(n)]
    bul = [rnd.choice([0.0, 0.0, rnd.uniform(-2, 2), 1e-13]) for _ in range(rnd.randint(0, n))]
    closed = rnd.random() < .5; elev = rnd.uniform(-2, 2)
    W = lambda x, y, z=0.0: M.apply(x, y)
    path = [W(pts[0][0], pts[0][1], elev)]
    for i in range(1, n + (1 if closed else 0)):
        p0 = pts[i - 1]; p1 = pts[i % n]; b = bul[i - 1] if i - 1 < len(bul) else 0.0
        path.extend([W(q[0], q[1], elev) for q in bulge_points(p0, p1, b)])
    chk('lwpoly', R.lwpoly_path(pts, bul, closed, elev, m6, None), [v for p in path for v in p])
    chk('apply', R.apply_flat([v for p in pts for v in p], m6), [v for p in pts for v in M.apply(*p)])

import json
def pj(o): return json.dumps(o, separators=(',', ':')).encode()
fl = [rnd.uniform(-1, 1) * 10 ** rnd.randint(-12, 20) for _ in range(100000)] + [0.0, -0.0, 1.0, 1e16, 1e15, 9999999999999998.0, 1e-4, 1e-5, 0.0001234, 123456789012345678.0, 5e-324, 1.7976931348623157e308, float('inf'), float('-inf'), float('nan'), 100.0, 0.5, 12345.678]
for x in fl:
    a, b = R.dumps(x), pj(x)
    if a != b: bad += 1; print('DIFF float', repr(x), a, b); break
ob = {'a': [1, 2.5, None, True, False, 'é\u2028\U0001f600"\\\n\x01', (1, 2.0)], 3: {'k': -7, 'big': 123456789012345678901234567890}, 'e': [], 'd': {}}
if R.dumps(ob) != pj(ob): bad += 1; print('DIFF obj', R.dumps(ob), pj(ob))
try: R.dumps({1.5: 1}); bad += 1; print('no error for float key')
except TypeError: pass
print('lwpoly sub-1e-9 (hypot ulp) diffs:', ulp); print('PARITY', 'FAIL %d' % bad if bad else 'OK')
sys.exit(1 if bad else 0)
