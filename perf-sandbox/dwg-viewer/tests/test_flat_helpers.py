"""Tests for pure flat helpers, using only synthetic in-memory inputs."""
import importlib.util
import math
import os
import struct
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The source-only checkout omits these drawing-reader dependencies. None of
# the helpers tested here uses them. Supply only missing imports, temporarily,
# leaving real modules available when running in a complete checkout.
_missing = {}
for _name in ('dwgmodel', 'dwgent', 'dwgviewer.annoctx'):
    if _name not in sys.modules and importlib.util.find_spec(_name) is None:
        _missing[_name] = types.ModuleType(_name)
if 'dwgviewer.annoctx' in _missing:
    _missing['dwgviewer.annoctx'].AnnoContexts = object
with patch.dict(sys.modules, _missing):
    from dwgviewer import flat


class SaneTests(unittest.TestCase):
    @staticmethod
    def rows_with(value):
        return [
            ('l', None, None, None, None, [0.0, value]),
            ('h', None, None, [[0.0, 1.0], [2.0, value]]),
            ('t', None, None, value, 0.0),
            ('t', None, None, 0.0, value),
            ('p', None, None, value, 0.0),
            ('p', None, None, 0.0, value),
        ]

    def test_empty_rows_and_empty_coordinate_lists(self):
        for rows in ([], [('l', None, None, None, None, [])],
                     [('h', None, None, [])], [('h', None, None, [[]])]):
            with self.subTest(rows=rows):
                self.assertTrue(flat._sane(rows))

    def test_nonfinite_and_limit_coordinates_are_rejected(self):
        for value in (math.nan, math.inf, -math.inf, 1e12, -1e12, 2e12):
            for row in self.rows_with(value):
                with self.subTest(value=value, row=row):
                    self.assertFalse(flat._sane([row]))

    def test_coordinates_just_inside_limit_are_accepted(self):
        for value in (999999999999.0, -999999999999.0):
            for row in self.rows_with(value):
                with self.subTest(value=value, row=row):
                    self.assertTrue(flat._sane([row]))

    def test_large_sum_of_valid_coordinates_is_accepted(self):
        values = [2e11, -2e11] * 10
        self.assertGreater(sum(map(abs, values)), 1e12)
        rows = [
            ('l', None, None, None, None, values),
            ('h', None, None, [values[:10], values[10:]]),
            ('t', None, None, 6e11, -6e11),
            ('p', None, None, -6e11, 6e11),
        ]
        self.assertTrue(flat._sane(rows))

    def test_unknown_kinds_are_ignored(self):
        self.assertTrue(flat._sane([
            ('unknown', None, None, math.nan, math.inf, [1e12]),
            ('unknown',),
        ]))

    def test_bad_coordinate_in_later_row_is_not_missed(self):
        rows = [('l', None, None, None, None, [1.0, 2.0]),
                ('h', None, None, [[3.0, 4.0], [5.0, math.nan]])]
        self.assertFalse(flat._sane(rows))


class FlatTests(unittest.TestCase):
    def test_empty_points(self):
        self.assertEqual(flat._flat([]), [])

    def test_one_point(self):
        self.assertEqual(flat._flat([(3, -4)]), [3, -4])

    def test_several_points_preserve_order(self):
        self.assertEqual(flat._flat([(1, 2), (-3, 4), (5, -6)]),
                         [1, 2, -3, 4, 5, -6])

    def test_coordinates_are_not_rounded(self):
        self.assertEqual(flat._flat([(1.123456789012345, -0.000000123456789)]),
                         [1.123456789012345, -0.000000123456789])


class BSplineFastTests(unittest.TestCase):
    def setUp(self):
        self.ctrl = [(0, 0), (1, 2), (2, 0)]
        self.knots = [0, 0, 0, 1, 1, 1]

    def test_quadratic_bezier_endpoints_and_midpoint(self):
        points = flat.bspline_fast(2, self.knots, self.ctrl, n=10)
        self.assertEqual(points[0], (0, 0))
        self.assertEqual(points[-1], (2, 0))
        self.assertAlmostEqual(points[5][0], 1.0)
        self.assertAlmostEqual(points[5][1], 1.0)
        for i, (x, y) in enumerate(points):
            t = i / 10
            self.assertAlmostEqual(x, 2 * t)
            self.assertAlmostEqual(y, 4 * t * (1 - t))

    def test_unit_weights_match_unweighted_samples(self):
        plain = flat.bspline_fast(2, self.knots, self.ctrl, n=20)
        weighted = flat.bspline_fast(
            2, self.knots, self.ctrl, weights=[1.0] * 3, n=20)
        self.assertEqual(weighted, plain)

    def test_degree_one_samples_lie_on_polyline(self):
        ctrl = [(0, 0), (2, 3), (2, -1), (-1, -1)]
        points = flat.bspline_fast(1, [0, 0, 1, 2, 3, 3], ctrl, n=30)
        self.assertEqual(len(points), 31)
        self.assertEqual(points[0], ctrl[0])
        self.assertEqual(points[-1], ctrl[-1])
        for point in points:
            distances = []
            for a, b in zip(ctrl, ctrl[1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                t = ((point[0] - a[0]) * dx +
                     (point[1] - a[1]) * dy) / (dx * dx + dy * dy)
                t = max(0.0, min(1.0, t))
                distances.append(math.hypot(
                    point[0] - (a[0] + t * dx),
                    point[1] - (a[1] + t * dy)))
            self.assertLessEqual(min(distances), 1e-9)

    def test_too_few_knots_returns_control_xy_pairs(self):
        ctrl = [(0, 1, 9), (2, 3, 8), (4, 5, 7)]
        for knots in ([], [0, 0, 0, 1, 1]):
            with self.subTest(knots=knots):
                self.assertEqual(flat.bspline_fast(2, knots, ctrl),
                                 [(0, 1), (2, 3), (4, 5)])

    def test_empty_controls_return_empty_list(self):
        self.assertEqual(flat.bspline_fast(2, self.knots, []), [])

    def test_n_controls_sample_count(self):
        for n in (1, 2, 7, 24):
            with self.subTest(n=n):
                self.assertEqual(
                    len(flat.bspline_fast(2, self.knots, self.ctrl, n=n)),
                    n + 1)


class DStyleOverridesTests(unittest.TestCase):
    @staticmethod
    def stream(label='DSTYLE'):
        # Type 0, uint16 character count, UTF-16LE string, opening brace.
        return (b'\x00' + struct.pack('<H', len(label)) +
                label.encode('utf-16le') + b'\x02\x00')

    @staticmethod
    def int16(value):
        return b'\x46' + struct.pack('<h', value)

    def test_empty_and_none_inputs(self):
        for eed in (None, []):
            with self.subTest(eed=eed):
                self.assertEqual(flat.dstyle_overrides(eed), {})

    def test_int16_and_double_pairs_are_decoded(self):
        stream = (self.stream() + self.int16(77) + self.int16(-2) +
                  self.int16(40) + b'\x28' + struct.pack('<d', 2.5) +
                  b'\x02\x01')
        self.assertEqual(flat.dstyle_overrides([('ACAD', stream)]),
                         {77: -2, 40: 2.5})

    def test_entries_without_dstyle_are_ignored(self):
        unrelated = self.stream('OTHER') + self.int16(77) + self.int16(9)
        valid = self.stream() + self.int16(77) + self.int16(3)
        self.assertEqual(flat.dstyle_overrides([('ACAD', unrelated)]), {})
        self.assertEqual(flat.dstyle_overrides([
            ('ACAD', valid), ('ACAD', unrelated), ('OTHER', b'garbage')]),
            {77: 3})

    def test_truncated_double_preserves_completed_pairs(self):
        prefix = self.stream() + self.int16(77) + self.int16(4)
        double = struct.pack('<d', 2.5)
        for size in range(8):
            with self.subTest(size=size):
                stream = prefix + self.int16(40) + b'\x28' + double[:size]
                self.assertEqual(flat.dstyle_overrides([('ACAD', stream)]),
                                 {77: 4})

    def test_unpaired_code_at_end_does_not_raise(self):
        stream = self.stream() + self.int16(40)
        self.assertEqual(flat.dstyle_overrides([('ACAD', stream)]), {})


if __name__ == '__main__':
    unittest.main()


class DstyleHandleTest(unittest.TestCase):
    def test_handle_value_does_not_stop_parsing(self):
        from dwgviewer import flat
        b = b'\x00\x06\x00D\x00S\x00T\x00Y\x00L\x00E\x00\x02\x00FM\x00F\x00\x00FT\x01\x05\x00\x00\x00\x00\x00\x00c\xa0F(\x00(\x00\x00\x00\x00\x00\x00\xf0?\x02\x01'
        self.assertEqual(flat.dstyle_overrides([(5, b)]), {77: 0, 340: 25504, 40: 1.0})
