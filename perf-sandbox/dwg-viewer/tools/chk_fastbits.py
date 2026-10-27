#!/usr/bin/env python3
"""chk_fastbits.py FILE : decode every entity with the original and with the fast Bits readers; report timing and any difference."""
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgscene
from dwgviewer import fastbits


def decode(path):
    t = time.time()
    sc = dwgscene.Scene(open(path, 'rb').read())
    ents = {k: sorted(((e['handle'], json.dumps({a: b for a, b in e.items() if a != 'eed'}, sort_keys=True, default=str)) for e in es)) for k, es in sc.by_block.items()}
    return time.time() - t, ents


fastbits.restore(); t0, a = decode(sys.argv[1])
fastbits.apply(); t1, b = decode(sys.argv[1])
print('original %.1fs  fast %.1fs  identical %s  entities %d' % (t0, t1, a == b, sum(len(v) for v in a.values())))
