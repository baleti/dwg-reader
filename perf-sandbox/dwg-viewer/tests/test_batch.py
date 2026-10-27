import os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import batch


def mk(root, rel, size=10):
    p = os.path.join(root, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(b'x' * size); return os.path.realpath(p)


class T(unittest.TestCase):
    def test_find(self):
        with tempfile.TemporaryDirectory() as d:
            a = mk(d, 'a.dwg'); b = mk(d, 'sub/B.DWG'); mk(d, 'sub/c.txt'); mk(d, '.hid/h.dwg'); mk(d, 'sub/deep/e.dwg')
            os.symlink(os.path.join(d, 'sub'), os.path.join(d, 'link'))
            got = batch.find_drawings([d, a, os.path.join(d, 'missing.dwg')])
            got = [os.path.realpath(p) for p in got]
            self.assertEqual(got, sorted(set([a, b, os.path.realpath(os.path.join(d, 'sub/deep/e.dwg'))])))
            self.assertEqual(len(batch.find_drawings([d, d])), 3)
            self.assertEqual(len(batch.find_drawings([os.path.join(d, 'sub')], exts=('.txt',))), 1)

    def test_plan(self):
        with tempfile.TemporaryDirectory() as d:
            big = mk(d, 'big.dwg', 500); small = mk(d, 'small.dwg', 5); mid = mk(d, 'mid.dwg', 50); cached = mk(d, 'cached.dwg', 20)
            todo, skipped = batch.plan([big, small, mid, cached], lambda p: p == cached)
            self.assertEqual(todo, [small, mid, big]); self.assertEqual(skipped, [(cached, 'cached')])
            todo, skipped = batch.plan([big, small, mid], lambda p: False, min_bytes=10, max_bytes=100)
            self.assertEqual(todo, [mid]); self.assertEqual(sorted(skipped), sorted([(big, 'size'), (small, 'size')]))
            todo, skipped = batch.plan([os.path.join(d, 'nope.dwg')], lambda p: False)
            self.assertEqual(skipped, [(os.path.join(d, 'nope.dwg'), 'unreadable')])

    def test_run(self):
        seen = []
        def worker(p):
            if p.endswith('bad'): raise RuntimeError('boom')
            if p.endswith('slow'): time.sleep(0.5)
            return {'n': len(p)}
        res = batch.run(['/a/one', '/a/bad', '/a/two'], worker, jobs=2, on_result=seen.append)
        self.assertEqual([r['path'] for r in res], ['/a/one', '/a/bad', '/a/two'])
        self.assertTrue(res[0]['ok'] and res[0]['result'] == {'n': 6}); self.assertFalse(res[1]['ok']); self.assertEqual(res[1]['error'], 'RuntimeError: boom')
        self.assertEqual(len(seen), 3); self.assertTrue(all('seconds' in r for r in res))
        res = batch.run(['/a/slow'], worker, jobs=0, timeout=0.05)
        self.assertEqual(res[0]['error'], 'timeout'); self.assertFalse(res[0]['ok'])

    def test_summary(self):
        res = [{'path': '/p/z.dwg', 'ok': False, 'error': 'E: x', 'seconds': 1.0}, {'path': '/p/a.dwg', 'ok': True, 'seconds': 2.25}, {'path': '/q/b.dwg', 'ok': False, 'error': 'timeout', 'seconds': 0.5}]
        self.assertEqual(batch.summary(res), '1 ok, 2 failed, 3.8 s\n  FAIL b.dwg: timeout\n  FAIL z.dwg: E: x')
        self.assertEqual(batch.summary([]), '0 ok, 0 failed, 0.0 s')


if __name__ == '__main__':
    unittest.main()
