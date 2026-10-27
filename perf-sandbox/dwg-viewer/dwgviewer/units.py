"""AutoCAD INSUNITS names, length conversions, and display helpers."""

import math


UNIT_NAMES = {
    0: 'unitless', 1: 'in', 2: 'ft', 3: 'mi', 4: 'mm', 5: 'cm',
    6: 'm', 7: 'km', 8: 'uin', 9: 'mil', 10: 'yd', 11: 'A',
    12: 'nm', 13: 'um', 14: 'dm', 15: 'dam', 16: 'hm', 17: 'Gm',
    18: 'au', 19: 'ly', 20: 'pc', 21: 'USft', 22: 'USin',
    23: 'USyd', 24: 'USmi',
}

METRES = {
    1: 0.0254,
    2: 0.3048,
    3: 1609.344,
    4: 0.001,
    5: 0.01,
    6: 1,
    7: 1000,
    8: 2.54e-8,
    9: 2.54e-5,
    10: 0.9144,
    11: 1e-10,
    12: 1e-9,
    13: 1e-6,
    14: 0.1,
    15: 10,
    16: 100,
    17: 1e9,
    18: 149597870700,
    19: 9460730472580800,
    20: 30856775814913673,
    21: 1200 / 3937,
    22: 1200 / 3937 / 12,
    23: 3600 / 3937,
    24: 5280 * 1200 / 3937,
}


def name(code):
    """Return the short unit name, defaulting to unitless."""
    return UNIT_NAMES.get(code, 'unitless')


def factor(from_code, to_code):
    """Return a length multiplier, or None for unspecified units."""
    if from_code not in METRES or to_code not in METRES:
        return None
    return METRES[from_code] / METRES[to_code]


def convert(value, from_code, to_code):
    """Convert a length, preserving its value when units are unspecified."""
    multiplier = factor(from_code, to_code)
    return value if multiplier is None else value * multiplier


def guess(extents_w, extents_h):
    """Guess metres below 1000 drawing units, otherwise millimetres."""
    if not math.isfinite(extents_w) or not math.isfinite(extents_h):
        return 0
    dimension = max(extents_w, extents_h)
    if dimension <= 0:
        return 0
    return 6 if dimension < 1000 else 4


def fmt(value, code):
    """Format unitless lengths to three decimals, named units to four digits."""
    if value is None or math.isnan(value):
        return ''
    unit_name = name(code)
    if unit_name == 'unitless':
        return ('%.3f' % value).rstrip('0').rstrip('.')
    return '%.4g' % value + ' ' + unit_name
