"""xref resolution: a host drawing whose xref DWG sits next to it draws the xref's model space (needs two local corpus drawings, skipped without them)."""
import glob, os, shutil, sys, tempfile, unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
CORPUS = os.path.expanduser('~/dwg-research/corpus')


@unittest.skipUnless(glob.glob(os.path.join(CORPUS, 'AC1018_42*.dwg')) and glob.glob(os.path.join(CORPUS, 'AC1015_56*.dwg')), 'corpus missing')
class XrefTests(unittest.TestCase):
    def test_xref_found_adds_rows(self):
        from dwgviewer import build
        host = glob.glob(os.path.join(CORPUS, 'AC1018_42*.dwg'))[0]; child = glob.glob(os.path.join(CORPUS, 'AC1015_56*.dwg'))[0]
        with tempfile.TemporaryDirectory() as td:
            h = os.path.join(td, 'host.dwg'); shutil.copy(host, h)
            d0 = build.Doc(h); x0 = d0.meta()['xrefs']
            self.assertEqual(len(x0), 1); self.assertFalse(x0[0]['found'])
            n0 = d0.layout(0)['n']
            shutil.copy(child, os.path.join(td, os.path.basename(x0[0]['path'].replace('\\', '/'))))
            d1 = build.Doc(h); x1 = d1.meta()['xrefs']
            self.assertTrue(x1[0]['found'])
            self.assertGreater(d1.layout(0)['n'], n0)
            self.assertEqual(d1.layout(0)['errors'], 0)


if __name__ == '__main__':
    unittest.main()
