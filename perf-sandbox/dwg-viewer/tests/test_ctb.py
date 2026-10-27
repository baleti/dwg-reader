"""Synthetic plot-style fixtures; run with python3 -m unittest tests.test_ctb -v."""
import os
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import ctb


HEADER = b'PIAFILEVERSION_2.0,CTBVER1,compress\npmzlibcodec' + b'\x00' * 4


def style_text(blocks, weights=((0, 0.0), (1, 0.25), (2, 0.5))):
    lines = ['custom_lineweight_table{']
    lines.extend(f'{index}={mm:.4f}' for index, mm in weights)
    lines.extend(['}', 'plot_style{'])
    for number, fields in blocks:
        lines.append(f'{number}{{')
        lines.extend(f'{key}={value}' for key, value in fields.items())
        lines.append('}')
    lines.append('}')
    return '\n'.join(lines) + '\n'


class CTBTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = directory.name
        search = patch.object(ctb, 'SEARCH', [self.directory])
        search.start()
        self.addCleanup(search.stop)

    def write_ctb(self, text, compressed=True, name='x.ctb'):
        path = os.path.join(self.directory, name)
        payload = text.encode('latin1')
        if compressed:
            payload = HEADER + zlib.compress(payload)
        with open(path, 'wb') as stream:
            stream.write(payload)
        return path

    def read_table(self, blocks, **kwargs):
        return ctb.table(self.write_ctb(style_text(blocks, **kwargs)))

    def test_find_empty_names(self):
        for name in ('', None):
            with self.subTest(name=name):
                self.assertIsNone(ctb.find(name))

    def test_find_without_extension(self):
        path = self.write_ctb('')
        self.assertEqual(ctb.find('x'), path)

    def test_find_with_extension(self):
        path = self.write_ctb('')
        self.assertEqual(ctb.find('x.ctb'), path)

    def test_find_windows_path_case_insensitive(self):
        path = self.write_ctb('')
        self.assertEqual(ctb.find(r'C:\styles\X.CTB'), path)

    def test_find_missing(self):
        self.write_ctb('')
        self.assertIsNone(ctb.find('missing'))

    def test_parse_compressed_round_trip(self):
        text = style_text([(0, {'name': 'Café', 'color': -1})])
        self.assertEqual(ctb.parse(self.write_ctb(text)), text)

    def test_parse_plain_latin1_fallback(self):
        text = style_text([(0, {'name': 'Café', 'color': -1})])
        self.assertEqual(ctb.parse(self.write_ctb(text, compressed=False)), text)

    def test_parse_marker_without_valid_stream(self):
        # Cover both no candidate byte and a candidate that fails decompression.
        for suffix in (b'', b'\x78not a zlib stream'):
            with self.subTest(suffix=suffix):
                path = os.path.join(self.directory, 'invalid.ctb')
                with open(path, 'wb') as stream:
                    stream.write(HEADER + suffix)
                with self.assertRaisesRegex(ValueError, 'no zlib stream'):
                    ctb.parse(path)

    def test_table_aci_is_block_number_plus_one(self):
        result = self.read_table([
            (0, {'name': 'first'}),
            (7, {'name': 'eighth'}),
        ])
        self.assertEqual(set(result['aci']), {1, 8})

    def test_table_object_colour_sentinels_and_missing_colour(self):
        for fields in ({'color': -1}, {'color': 0xFFFFFFFF}, {'name': 'object'}):
            with self.subTest(fields=fields):
                result = self.read_table([(0, fields)])
                self.assertIsNone(result['aci'][1]['rgb'])

    def test_table_colour_packing_is_rgb(self):
        result = self.read_table([
            (0, {'color': 0xFF0000}),
            (1, {'color': 0x123456}),
        ])
        self.assertEqual(result['aci'][1]['rgb'], (255, 0, 0))
        self.assertEqual(result['aci'][2]['rgb'], (18, 52, 86))

    def test_table_zero_lineweight_uses_object(self):
        result = self.read_table([(0, {'name': 'object', 'lineweight': 0})])
        self.assertIsNone(result['aci'][1]['lw'])

    def test_table_valid_lineweight_indices(self):
        result = self.read_table([
            (0, {'name': 'thin', 'lineweight': 1}),
            (1, {'name': 'thick', 'lineweight': 2}),
        ])
        self.assertEqual(result['aci'][1]['lw'], 0.25)
        self.assertEqual(result['aci'][2]['lw'], 0.5)

    def test_table_out_of_range_lineweight(self):
        for index in (3, 99):
            with self.subTest(index=index):
                result = self.read_table([(0, {'name': 'outside', 'lineweight': index})])
                self.assertIsNone(result['aci'][1]['lw'])

    def test_table_screen_defaults_to_100(self):
        result = self.read_table([(0, {'name': 'default'})])
        self.assertEqual(result['aci'][1]['screen'], 100)

    def test_table_explicit_screens(self):
        for screen in (0, 42, 100):
            with self.subTest(screen=screen):
                result = self.read_table([(0, {'name': 'screened', 'screen': screen})])
                self.assertEqual(result['aci'][1]['screen'], screen)

    def test_table_skips_blocks_without_name_and_colour(self):
        result = self.read_table([
            (0, {'lineweight': 1, 'screen': 50}),
            (1, {}),
            (2, {'name': 'name only'}),
            (3, {'color': 0}),
        ])
        self.assertEqual(set(result['aci']), {3, 4})
        self.assertEqual(result['aci'][4]['rgb'], (0, 0, 0))

    def test_table_lineweights_follow_text_order(self):
        result = self.read_table([], weights=((0, 0.0), (2, 0.5), (1, 0.25)))
        # The parser appends values in encounter order, ignoring numeric labels.
        self.assertEqual(result['lwtable'], [0.0, 0.5, 0.25])


if __name__ == '__main__':
    unittest.main()
