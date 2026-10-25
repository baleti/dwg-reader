#!/bin/bash
# sequential AutoCAD oracle (dump+plot+png) over the 100-file real sample; skips done files; retries once
cd ~/dwg-research
for f in $(cut -f1 ~/dwg-edit-tests/sample.tsv); do
  s=${f%.dwg}
  [ -f oracle-out/$s/plots/plot.log ] && continue
  for try in 1 2 3; do
    timeout 400 tools/oracle/dwgq run ~/dwg-edit-tests/src/$f --tasks dump,plot --png 80 --timeout 300 >> qa/oracle_batch.log 2>&1
    [ -f oracle-out/$s/plots/plot.log ] && break
    sleep 45
  done
  echo "$s $(ls oracle-out/$s/plots 2>/dev/null | grep -c fixed.pdf)" >> qa/oracle_batch.done
done
echo ALLDONE >> qa/oracle_batch.done
