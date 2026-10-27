import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import clip

SQ = [(0, 0), (10, 0), (10, 10), (0, 10)]


class ClipTests(unittest.TestCase):
    def test_ccw_orientation(self):
        self.assertEqual(clip.ccw(SQ), SQ)
        self.assertEqual(clip.ccw(list(reversed(SQ))), SQ)

    def test_inside(self):
        self.assertTrue(clip.inside(SQ, 5, 5)); self.assertTrue(clip.inside(SQ, 10, 10)); self.assertFalse(clip.inside(SQ, 10.1, 5))

    def test_segment_and_polyline(self):
        self.assertEqual(clip.clip_segment(SQ, -5, 5, 15, 5), (0.25, 0.75))
        self.assertIsNone(clip.clip_segment(SQ, -5, 20, 15, 20))
        self.assertIsNone(clip.clip_segment(SQ, 11, 0, 11, 10))
        self.assertEqual(clip.clip_polyline(SQ, [-5, 5, 15, 5]), [[0.0, 5.0, 10.0, 5.0]])
        self.assertEqual(clip.clip_polyline(SQ, [-5, -5, 5, 5, 5, 15]), [[0.0, 0.0, 5.0, 5.0, 5.0, 10.0]])
        two = clip.clip_polyline(SQ, [2, 5, 20, 5, 20, 8, 3, 8])        # leaves and re-enters: two pieces
        self.assertEqual(len(two), 2)

    def test_loop(self):
        c = clip.clip_loop(SQ, [(5, 5), (15, 5), (15, 15), (5, 15)])
        self.assertEqual(sorted(c), sorted([(5, 5), (10.0, 5.0), (10.0, 10.0), (5.0, 10.0)]))
        self.assertEqual(clip.clip_loop(SQ, [(20, 20), (30, 20), (30, 30)]), [])

    def test_rows(self):
        rows = [('t', 'a', 7, 5, 5, 1), ('t', 'a', 7, 50, 5, 1), ('p', 'a', 7, 1, 1, 9), ('p', 'a', 7, 11, 1, 9),
                ('l', 'a', 7, 0.25, None, [-5, 5, 15, 5], 1, 0.0), ('h', 'a', 7, [[5, 5, 15, 5, 15, 15, 5, 15], [30, 30, 40, 30, 40, 40]], {'solid': 1}, 3)]
        out = clip.clip_rows(rows, list(reversed(SQ)))      # orientation of the polygon does not matter
        kinds = [r[0] for r in out]
        self.assertEqual(kinds, ['t', 'p', 'l', 'h'])
        self.assertEqual(out[2][5], [0.0, 5.0, 10.0, 5.0]); self.assertEqual(len(out[3][3]), 1)


if __name__ == '__main__':
    unittest.main()
