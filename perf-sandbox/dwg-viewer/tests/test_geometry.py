"""Pure-geometry unit tests for the viewer's flattener helpers (no drawing needed): python3 -m unittest discover -s tests"""
import math, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgscene
from dwgviewer import flat


class Splines(unittest.TestCase):
    def test_fast_matches_reference(self):
        k = [0, 0, 0, 0, 1, 2, 3, 4, 4, 4, 4]; c = [(0, 0), (1, 2), (3, 3), (4, 1), (6, 2), (7, 0), (8, 3)]
        a = dwgscene.bspline_points(3, k, c); b = flat.bspline_fast(3, k, c, n=len(a) - 1)
        self.assertEqual(len(a), len(b))
        self.assertLess(max(abs(x[0] - y[0]) + abs(x[1] - y[1]) for x, y in zip(a, b)), 1e-9)

    def test_curve_stays_in_hull(self):
        k = [0, 0, 0, 0, 1, 1, 1, 2, 2, 2, 2]; c = [(0, 0), (1, 5), (2, -5), (3, 0), (4, 5), (5, -5), (6, 0)]
        pts = flat.bspline_fast(3, k, c)
        self.assertTrue(all(min(p[0] for p in c) - 1e-9 <= x <= max(p[0] for p in c) + 1e-9 and min(p[1] for p in c) - 1e-9 <= y <= max(p[1] for p in c) + 1e-9 for x, y in pts))


class Bulges(unittest.TestCase):
    def test_semicircle(self):
        pts = dwgscene.bulge_points((0, 0), (2, 0), 1.0)    # bulge 1 = half circle, centre (1, 0), radius 1
        self.assertTrue(all(abs(math.hypot(x - 1, y) - 1) < 1e-9 for x, y in pts))
        self.assertAlmostEqual(min(y for x, y in pts), -1, places=2)    # counter-clockwise: the arc bulges to the right of the direction of travel

    def test_zero_bulge_is_straight(self):
        self.assertEqual(dwgscene.bulge_points((0, 0), (5, 0), 0.0), [(5, 0)])


class Matrices(unittest.TestCase):
    def test_mat_compose(self):
        m = dwgscene.Mat(1, 0, 0, 1, 10, 0).mul(dwgscene.Mat(0, -1, 1, 0, 0, 0))    # rotate 90 deg, then translate
        x, y = m.apply(1, 0); self.assertAlmostEqual(x, 10); self.assertAlmostEqual(y, 1)

    def test_ocs_mirror(self):
        ax, ay, az = dwgscene.ocs_axes((0, 0, -1))
        self.assertAlmostEqual(ax[0], -1); self.assertAlmostEqual(ay[1], 1)    # extrusion (0,0,-1): x axis mirrored

    def test_minsert_offsets(self):
        c, s = math.cos(math.pi / 2), math.sin(math.pi / 2)
        offs = [(c * (cc * 10) - s * (rr * 20), s * (cc * 10) + c * (rr * 20)) for rr in range(2) for cc in range(2)]
        self.assertEqual([(round(a, 6), round(b, 6)) for a, b in offs], [(0, 0), (0, 10), (-20, 0), (-20, 10)])


class Annotation(unittest.TestCase):
    def test_dstyle_overrides(self):
        from dwgviewer import flat
        b = (b'\x00\x06\x00D\x00S\x00T\x00Y\x00L\x00E\x00\x02\x00F(\x00(\x00\x00\x00\x00\x00\x004@F\x93\x00(\x00\x00\x00\x00\x00\x00\xf0?FM\x00F\x00\x00\x02\x01')
        self.assertEqual(flat.dstyle_overrides([((5, 84), b)]), {40: 20.0, 147: 1.0, 77: 0})
        self.assertEqual(flat.dstyle_overrides([]), {})
        self.assertEqual(flat.dstyle_overrides([((5, 1), b'garbage')]), {})


if __name__ == '__main__':
    unittest.main()
