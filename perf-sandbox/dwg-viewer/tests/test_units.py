import math
import unittest
from dwgviewer import units


class UnitsTests(unittest.TestCase):
    def test_tables(self):
        self.assertEqual(units.name(4), 'mm'); self.assertEqual(units.name(6), 'm'); self.assertEqual(units.name(2), 'ft')
        self.assertEqual(units.name(None), 'unitless'); self.assertEqual(units.name(99), 'unitless'); self.assertEqual(units.name(0), 'unitless')
        self.assertEqual(set(units.UNIT_NAMES), set(range(25)))
        self.assertEqual(set(units.METRES), set(range(1, 25)))
        self.assertAlmostEqual(units.METRES[21], 1200 / 3937)
        self.assertAlmostEqual(units.METRES[24], 5280 * 1200 / 3937)
        self.assertEqual(units.METRES[4], 0.001)

    def test_factor_and_convert(self):
        self.assertAlmostEqual(units.factor(4, 6), 0.001)
        self.assertAlmostEqual(units.factor(6, 4), 1000)
        self.assertAlmostEqual(units.factor(1, 5), 2.54)
        self.assertAlmostEqual(units.factor(2, 1), 12)
        self.assertIsNone(units.factor(0, 6)); self.assertIsNone(units.factor(6, None)); self.assertIsNone(units.factor(6, 99))
        self.assertAlmostEqual(units.convert(2500, 4, 6), 2.5)
        self.assertEqual(units.convert(7, 0, 6), 7)

    def test_guess(self):
        self.assertEqual(units.guess(12, 8), 6)
        self.assertEqual(units.guess(0.5, 0.2), 6)
        self.assertEqual(units.guess(25000, 18000), 4)
        self.assertEqual(units.guess(2e6, 1e6), 4)
        self.assertEqual(units.guess(0, 0), 0)
        self.assertEqual(units.guess(-1, -5), 0)
        self.assertEqual(units.guess(float('nan'), 3), 0)
        self.assertEqual(units.guess(float('inf'), 3), 0)

    def test_fmt(self):
        self.assertEqual(units.fmt(12.3456, 6), '12.35 m')
        self.assertEqual(units.fmt(1234.5678, 4), '1235 mm')
        self.assertEqual(units.fmt(-0.5, 2), '-0.5 ft')
        self.assertEqual(units.fmt(1.23456, 0), '1.235')
        self.assertEqual(units.fmt(2.0, 0), '2')
        self.assertEqual(units.fmt(float('nan'), 6), '')
        self.assertEqual(units.fmt(None, 6), '')


if __name__ == '__main__':
    unittest.main()
