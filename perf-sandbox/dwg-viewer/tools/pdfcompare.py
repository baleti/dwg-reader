#!/usr/bin/env python3
"""pdfcompare.py FILE.dwg LAYOUT_INDEX REFERENCE.pdf [--out DIR] : score our rendering of a layout against any plotted PDF (e.g. the PDFs delivered with a drawing set)
with the same ink precision / recall as vcompare.py (colour independent: plot style tables are not applied to ours). Local use only."""
import sys, os, asyncio, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vcompare
from cdp import Session

ap = argparse.ArgumentParser()
ap.add_argument('file'); ap.add_argument('layout', type=int); ap.add_argument('pdf')
ap.add_argument('--out', default='/tmp'); ap.add_argument('--fit', default='full')
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
stem = os.path.splitext(os.path.basename(a.file))[0] + '_' + os.path.splitext(os.path.basename(a.pdf))[0][-10:]
png = os.path.join(a.out, '%s_ours.png' % stem)


async def shoot():
    async with Session(a.file, 1600, 1130) as s:
        await s.open('clean=1&fit=%s&plot=1' % a.fit, layout=a.layout)
        await asyncio.sleep(6)
        name = await s.js("meta.layouts[%d].name" % a.layout)
        # whole sheet: frame the sheet bounds exactly and report its pixel rectangle so the screenshot can be cropped to the page
        r = await s.js("""(()=>{const b=lay.bounds, w=cv.width/devicePixelRatio, h=cv.height/devicePixelRatio, k=Math.min(w/(b[2]-b[0]), h/(b[3]-b[1]));
          view.s=k; view.x=(b[0]+b[2])/2-w/2/k; view.y=(b[1]+b[3])/2+h/2/k; draw(); const dpr=devicePixelRatio;
          return JSON.stringify([(b[0]-view.x)*k*dpr, (view.y-b[3])*k*dpr, (b[2]-view.x)*k*dpr, (view.y-b[1])*k*dpr])})()""")
        await asyncio.sleep(2.5)
        import json
        from PIL import Image
        import io
        im = Image.open(io.BytesIO(await s.shot())).convert('RGB'); x0, y0, x1, y1 = [round(v) for v in json.loads(r)]
        im.crop((x0, y0, x1, y1)).save(png)
        return name

name = asyncio.run(shoot())
os.environ['VC_PDF'] = a.pdf; os.environ['VC_FULLPAGE'] = '1'
vcompare.compare(stem, a.layout, name, png, a.out)
