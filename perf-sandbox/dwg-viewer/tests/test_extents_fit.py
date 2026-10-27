"""A layout plotted by Extents, scaled to fit, shows the whole content scaled onto the paper (the sheet is not the paper rectangle at 1:1).
Synthetic: A4 layout with a 3x larger paper-space line frame (needs the writer's blank template; skipped without it)."""
import os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
TPL = os.path.join(HERE, 'templates', 'blank_2000.dwg')
if not os.path.exists(TPL): TPL = os.path.expanduser('~/dwg-write/templates/blank_2000.dwg')


@unittest.skipUnless(os.path.exists(TPL), 'blank template missing')
class ExtentsFitTests(unittest.TestCase):
    def build(self, plot_type, scale_type):
        import dwgdoc
        from dwgviewer import build
        d = dwgdoc.Doc(open(TPL, 'rb').read())
        lh = d.add_layout('A4', paper=(297, 210), plot_type=plot_type)
        L = d.get(lh); L['scale_type'] = scale_type; L['scale_factor'] = 0.34; d.put(L)
        blk = d.get(L['block'])['name']
        for a, b in (((0, 0), (840, 0)), ((840, 0), (840, 594)), ((840, 594), (0, 594)), ((0, 594), (0, 0))): d.add_line(a, b, block=blk)
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, 't.dwg'); open(p, 'wb').write(d.save())
            doc = build.Doc(p)
            i = next(i for i, l in enumerate(doc.lays) if l['name'] == 'A4')
            return doc.layout(i)

    def test_extents_fit_covers_content(self):
        b = self.build(1, 0)['bounds']
        self.assertGreaterEqual(b[2] - b[0], 840 - 1e-6); self.assertGreaterEqual(b[3] - b[1], 594 - 1e-6)
        self.assertAlmostEqual((b[2] - b[0]) / (b[3] - b[1]), 297 / 210, places=3)

    def test_other_plot_types_keep_paper(self):
        b = self.build(5, 16)['bounds']
        self.assertEqual([round(x, 3) for x in b], [0, 0, 297, 210])


if __name__ == '__main__':
    unittest.main()
