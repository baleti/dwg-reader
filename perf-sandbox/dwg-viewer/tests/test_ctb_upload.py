import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dwgviewer import ctb

SAMPLE = b"""description="test"
aci_table{
}
custom_lineweight_table{
 0=0.0000
 1=0.2500
}
plot_style{
0{
 name="Color_1"
 color=-1
 mode_color=-1
 screen=100
 lineweight=1
}
1{
 name="Color_2"
 color=16711680
 screen=50
 lineweight=0
}
}
"""


class CtbBytesTests(unittest.TestCase):
    def test_table_bytes_matches_file_parser(self):
        t = ctb.table_bytes(SAMPLE)
        self.assertEqual(sorted(t['aci']), [1, 2])
        self.assertEqual(t['aci'][1]['lw'], 0.25); self.assertIsNone(t['aci'][1]['rgb'])
        self.assertEqual(t['aci'][2]['rgb'], (255, 0, 0)); self.assertEqual(t['aci'][2]['screen'], 50)


if __name__ == '__main__':
    unittest.main()
