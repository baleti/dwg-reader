#!/usr/bin/env python3
"""chk_vp_off.py FILE... : per file, how many VIEWPORT objects have status bit 0x20000 (turned off) and how many in total (parser only, no scene build)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgmodel, dwgent
for f in sys.argv[1:]:
    try:
        m = dwgmodel.Model(open(f, 'rb').read())
        tot = off = 0
        for h, o in m.objs.items():
            if o.type == 34:
                try: v = dwgent.decode_viewport(o)
                except Exception: continue
                tot += 1; off += bool(v['status'] & 0x20000)
        print('%s\t%d\t%d' % (os.path.basename(f), tot, off), flush=True)
    except Exception as ex:
        print('%s\tERR %s' % (os.path.basename(f), str(ex)[:60]), flush=True)
