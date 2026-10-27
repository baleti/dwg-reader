import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import info


class Fake:
    def meta(self):
        return {'file': 'x.dwg', 'default': 1, 'layers': [{'n': 'A'}, {'n': 'B', 'off': True}, {'n': 'C', 'frozen': True, 'plot': False}, {'n': 'D', 'plot': False}],
                'layouts': [{'i': 0, 'name': 'Model', 'ps': False}, {'i': 1, 'name': 'Sheet1', 'ps': True}, {'i': 2, 'name': 'Bad', 'ps': True}]}

    def layout(self, i):
        if i == 0: return {'prims': [['l'], ['l'], ['h'], ['t'], ['p'], ['z']], 'mprims': [], 'vps': [], 'paper': None, 'bounds': [0, 0, 10, 5]}
        if i == 1: return {'prims': [['l']], 'mprims': [['l'], ['t']], 'vps': [{'id': 'F0D3', 'scale': 0.02, 'frozen': [1, 2]}, {'id': 9, 'scale': 1.0, 'frozen': []}], 'paper': [420, 297], 'bounds': [0, 0, 420, 297]}
        raise ValueError('boom')


class T(unittest.TestCase):
    def test_summary(self):
        s = info.summarize(Fake())
        self.assertEqual(s['file'], 'x.dwg'); self.assertEqual(s['default_layout'], 1)
        self.assertEqual(s['layers'], {'total': 4, 'off': 1, 'frozen': 1, 'nonplot': 2})
        m = s['layouts'][0]
        self.assertEqual(m['rows'], {'l': 2, 'h': 1, 't': 1, 'p': 1, 'total': 6}); self.assertFalse(m['paper_space']); self.assertIsNone(m['paper'])
        l1 = s['layouts'][1]
        self.assertTrue(l1['paper_space']); self.assertEqual(l1['paper'], [420, 297]); self.assertEqual(l1['model_rows_in_viewports'], 2)
        self.assertEqual(l1['viewports'], [{'id': 'F0D3', 'scale': 0.02, 'frozen_layers': 2}, {'id': 9, 'scale': 1.0, 'frozen_layers': 0}])
        self.assertEqual(s['layouts'][2]['error'], 'boom'); self.assertNotIn('rows', s['layouts'][2])

    def test_missing_keys(self):
        class Sparse:
            def meta(self): return {'file': 'y', 'layers': [], 'layouts': [{'i': 0, 'name': 'Model'}]}
            def layout(self, i): return {'prims': []}
        s = info.summarize(Sparse())
        self.assertEqual(s['layers']['total'], 0); self.assertEqual(s['layouts'][0]['rows']['total'], 0); self.assertEqual(s['default_layout'], 0)

    def test_text(self):
        t = info.render_text(info.summarize(Fake())).splitlines()
        self.assertEqual(t[0], 'x.dwg: 4 layers (1 off, 1 frozen), 3 layouts')
        self.assertEqual(t[1], '  [0] Model (model) rows=6 l=2 h=1 t=1 p=1 viewports=0')
        self.assertEqual(t[2], '  [1] Sheet1 (paper space) rows=1 l=1 h=0 t=0 p=0 viewports=2 *')
        self.assertEqual(t[3], '      viewport F0D3 scale=0.02 frozen=2')
        self.assertEqual(t[4], '      viewport 9 scale=1 frozen=0')
        self.assertEqual(t[5], '  [2] Bad ERROR boom')


if __name__ == '__main__':
    unittest.main()
