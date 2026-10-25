#!/bin/bash
cd ~/dwg-viewer
while true; do
  for s in $(grep -v ALLDONE ~/dwg-research/qa/oracle_batch.done | cut -d' ' -f1); do python3 tools/vqa.py $s >/dev/null 2>&1; done
  grep -q ALLDONE ~/dwg-research/qa/oracle_batch.done && break
  sleep 60
done
echo fin > ~/dwg-research/qa/vqa_loop.fin
