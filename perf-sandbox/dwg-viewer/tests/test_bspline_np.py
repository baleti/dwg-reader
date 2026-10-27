import importlib.util, os, random, sys, time, types, unittest
from bisect import bisect_right

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    pkg = types.ModuleType('dwgviewer'); pkg.__path__ = [os.path.join(ROOT, 'dwgviewer')]
    sys.modules.setdefault('dwgviewer', pkg)
    for name in ('dwgscene', 'dwgmodel', 'dwgent'):
        sys.modules.setdefault(name, types.ModuleType(name))
    spec = importlib.util.spec_from_file_location('dwgviewer.flat_np_test', os.path.join(ROOT, 'dwgviewer', 'flat.py'))
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        # flat.py imports parser modules; give it permissive stubs
        class _Any(types.ModuleType):
            def __getattr__(self, k): return lambda *a, **kw: None
        for name in ('dwgscene', 'dwgmodel', 'dwgent', 'dwgtab', 'dwgload'):
            sys.modules[name] = _Any(name)
        spec.loader.exec_module(mod)
    return mod


def ref(deg, knots, ctrl, weights=None, n=None):
    m = len(ctrl)
    if m == 0 or len(knots) < m + deg + 1 or deg < 1: return [(c[0], c[1]) for c in ctrl]
    t0, t1 = knots[deg], knots[m]
    n = n or max(16, 6 * m)
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


def knots_for(m, deg, rng, clamped):
    if clamped:
        inner = sorted(rng.uniform(0, 1) for _ in range(m - deg - 1)) if m > deg + 1 else []
        return [0.0] * (deg + 1) + inner + [1.0] * (deg + 1)
    return sorted(rng.uniform(0, 10) for _ in range(m + deg + 1))


class BSplineNumpyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = staticmethod(_load().bspline_fast)

    def test_matches_reference(self):
        rng = random.Random(7)
        for case in range(300):
            deg = rng.randint(1, 5); m = rng.randint(max(2, deg + 1), 40)
            clamped = case % 2 == 0
            kn = knots_for(m, deg, rng, clamped)
            ctrl = [(rng.uniform(-50, 50), rng.uniform(-50, 50), 0.0) for _ in range(m)]
            w = [rng.uniform(0.2, 3) for _ in range(m)] if case % 3 == 0 else None
            n = rng.choice([None, 5, 33])
            a = self.f(deg, kn, ctrl, w, n); b = ref(deg, kn, ctrl, w, n)
            self.assertEqual(len(a), len(b), (case, deg, m))
            for p, q in zip(a, b):
                self.assertAlmostEqual(p[0], q[0], delta=1e-9); self.assertAlmostEqual(p[1], q[1], delta=1e-9)

    def test_edge_cases(self):
        self.assertEqual(self.f(3, [0, 0, 0, 0, 1, 1, 1, 1], []), [])
        c = [(1.0, 2.0, 0.0), (3.0, 4.0, 0.0)]
        self.assertEqual(self.f(3, [0, 1], c), [(1.0, 2.0), (3.0, 4.0)])
        self.assertEqual(self.f(0, [0, 0, 1, 1], c), [(1.0, 2.0), (3.0, 4.0)])

    def test_faster(self):
        rng = random.Random(3); m, deg = 60, 3
        kn = knots_for(m, deg, rng, True)
        ctrl = [(rng.uniform(0, 100), rng.uniform(0, 100), 0.0) for _ in range(m)]
        def clock(fn):
            best = 1e9
            for _ in range(7):
                t = time.perf_counter()
                for _ in range(200): fn(deg, kn, ctrl)
                best = min(best, time.perf_counter() - t)
            return best
        self.assertLess(clock(self.f) * 3, clock(ref))


if __name__ == '__main__':
    unittest.main()
