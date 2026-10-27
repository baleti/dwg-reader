cd /home/user1/dwg-research/dwgscene-fast
for f in AC1024_21_3d823834 AC1014_18_d634d535 AC1014_49_60a9d12f AC1032_27_50a84483 AC1018_34_c9245e16 AC1018_39_c30462c3; do timeout 900 python3 prof/fast.py /home/user1/dwg-research/corpus/$f.dwg 2>&1 | tail -1; done > prof/parity_big.txt
