#!/bin/sh
# psweep.sh OUTDIR : browser-free pyrender score of the first paper layout (or Model) of every corpus file; TSV on stdout. Run on host1 (h1run).
OUT=$1; mkdir -p "$OUT"; exec > "$OUT/scores.tsv"
for f in $HOME/dwg-research/corpus/*.dwg; do
  for L in 1 0; do
    r=$(timeout 600 python3 tools/pyrender.py "$f" $L --out "$OUT" 2>/dev/null | tail -1)
    case "$r" in \{*) echo "$(basename $f)	$L	$r" | python3 -c "
import sys,json
a=sys.stdin.read().split('\t',2); r=json.loads(a[2]); print(a[0],a[1],r.get('p5a'),r.get('r5a'),sep='\t')"; break;; esac
  done
done
