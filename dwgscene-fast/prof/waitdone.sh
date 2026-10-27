until [ $(wc -l < $HOME/dwg-research/dwgscene-fast/prof/parity_corpus2.txt) -ge 56 ] || ! pgrep -f prof/fast.py >/dev/null; do sleep 30; done
