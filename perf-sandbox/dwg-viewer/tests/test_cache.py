import os, sys, gzip, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DWG_VIEW_CACHE'] = tempfile.mkdtemp()
from dwgviewer import cache


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.f = os.path.join(self.d, 'x.dwg'); open(self.f, 'wb').write(b'AC1015' + b'\0' * 100)

    def test_missing(self):
        self.assertIsNone(cache.read_layout(self.f, 0, True))

    def test_roundtrip(self):
        cache.write_layout(self.f, 1, True, {'a': 1})
        b = cache.read_layout(self.f, 1, True)
        self.assertEqual(gzip.decompress(b), b'{"a":1}')

    def test_corrupt_removed(self):
        for payload in (b'', b'\x00' * 64, b'  ' * 20, b'\x1f\x8b'):
            p = cache.layout_path(self.f, 2, False); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(payload)
            self.assertIsNone(cache.read_layout(self.f, 2, False))
            self.assertFalse(os.path.exists(p))

    def test_twist_flag_separate(self):
        cache.write_layout(self.f, 3, True, {'t': 1})
        self.assertIsNone(cache.read_layout(self.f, 3, False))

    def test_no_tmp_left(self):
        cache.write_layout(self.f, 4, True, {'a': 1})
        names = os.listdir(os.path.dirname(cache.layout_path(self.f, 4, True)))
        self.assertFalse([n for n in names if n.endswith('.tmp')])


if __name__ == '__main__':
    unittest.main()
