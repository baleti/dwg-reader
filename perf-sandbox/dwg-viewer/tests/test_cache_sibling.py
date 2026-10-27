import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import cache


class SiblingStampTests(unittest.TestCase):
    def test_key_changes_when_a_sibling_dwg_appears_or_changes(self):
        with tempfile.TemporaryDirectory() as td:
            me = os.path.join(td, 'host.dwg')
            with open(me, 'wb') as f: f.write(b'AC1018' + b'\0' * 200)
            k0 = cache.key(me)
            self.assertEqual(cache.key(me), k0)
            other = os.path.join(td, 'xref.dwg')
            with open(other, 'wb') as f: f.write(b'x' * 10)
            k1 = cache.key(me); self.assertNotEqual(k0, k1)
            with open(other, 'wb') as f: f.write(b'x' * 11)
            self.assertNotEqual(cache.key(me), k1)
            with open(os.path.join(td, 'notes.txt'), 'w') as f: f.write('x')
            k2 = cache.key(me)
            with open(os.path.join(td, 'more.txt'), 'w') as f: f.write('y')
            self.assertEqual(cache.key(me), k2)


if __name__ == '__main__':
    unittest.main()
