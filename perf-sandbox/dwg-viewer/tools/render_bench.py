#!/usr/bin/env python3
"""render_bench.py FILE LAYOUT : times 5 full renderScene() calls in headless chromium (software canvas, so pessimistic) and prints the row count. Local use."""
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cdp import Session


async def run(p, layout):
    async with Session(p, 1600, 1000) as s:
        await s.open('', layout=layout)
        await asyncio.sleep(3)
        print(await s.js("""(()=>{const ts=[]; for(let i=0;i<5;i++){const t=performance.now(); renderScene(cv, view); ts.push(Math.round(performance.now()-t));}
          return JSON.stringify({file:meta.file, layout:lay.layout===undefined?%d:lay.layout, ms:ts, rows:lay.prims.length+lay.mprims.length*Math.max(1,lay.vps.length)})})()""" % layout))

asyncio.run(run(sys.argv[1], int(sys.argv[2])))
