#!/usr/bin/env python3
"""ui_anno.py FILE [LAYOUT] : per-viewport annotation scale selector (headless chromium): select appears for a clicked viewport of a layout with annotative text,
lists several scales, and choosing another one changes what is drawn (screenshot differs) without JS errors. Use a file such as the AC1027_13 sheet layouts."""
import sys, os, asyncio, io, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cdp import Session
import numpy as np
from PIL import Image

FAILS = []
def check(name, cond, info=''):
    print(('PASS ' if cond else 'FAIL ') + name + ((' : ' + str(info)) if info != '' else ''))
    if not cond: FAILS.append(name)


async def main(path, layout):
    async with Session(path) as s:
        await s.open(layout=layout)
        check('select hidden before a viewport is chosen', await s.js("document.getElementById('vpAnno').style.display") == 'none')
        await s.js("curVp = 0; layerTableViewportChanged(); 1")
        vis = await s.js("document.getElementById('vpAnno').style.display")
        n = await s.js("document.getElementById('vpAnno').options.length")
        check('select shown with scales', vis != 'none' and n >= 2, n)
        a = Image.open(io.BytesIO(await s.shot())).convert('L')
        await s.js("(()=>{const e=document.getElementById('vpAnno'); e.selectedIndex = (e.selectedIndex + 1) % e.options.length; e.onchange(); return 1})()")
        await asyncio.sleep(0.5)
        b = Image.open(io.BytesIO(await s.shot())).convert('L')
        d = np.abs(np.asarray(a, int) - np.asarray(b, int)).sum()
        check('another scale redraws the viewport', d > 0, int(d))
        check('vp.an follows the selection', await s.js("Math.abs(lay.vps[0].an - Number(document.getElementById('vpAnno').value)) < 1e-9"))
        check('no JS errors', not (await s.js("(window.__errs||[]).length")))
    print(json.dumps({'fails': FAILS}))
    return 1 if FAILS else 0

sys.exit(asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)))
