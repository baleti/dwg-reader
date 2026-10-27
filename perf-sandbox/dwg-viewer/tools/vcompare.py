#!/usr/bin/env python3
"""vcompare.py FILE.dwg LAYOUT_INDEX [--oracle DIR] [--out DIR] : render our layout (headless chromium, clean mode) and the AutoCAD oracle plot
(fixed.pdf), crop both to their ink bbox, report ink precision/recall after 2px dilation, write side-by-side + diff PNG. Local use only."""
import sys, os, re, subprocess, json, socket, argparse
import numpy as np
from PIL import Image, ImageFilter
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORA = os.path.expanduser('~/dwg-research/oracle-out')


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


def ink_bbox(im, thr=235):
    a = np.asarray(im.convert('RGB')).min(axis=2)
    ys, xs = np.where(a < thr)
    if len(xs) == 0: return None
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def run(path, li, oracle_name=None, out='/tmp', width=1600, height=1130, port=None, kind='fixed'):
    stem = os.path.splitext(os.path.basename(path))[0]
    odir = os.path.join(ORA, stem)
    dump = json.load(open(os.path.join(odir, 'dump.json')))
    lname = None
    import asyncio
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cdp import Session
    png = os.path.join(out, '%s_L%d_ours.png' % (stem, li))
    info = {}
    async def shoot():
        async with Session(path, width, height) as s:
            await s.open('clean=1&' + ('fit=full' if os.environ.get('VC_FIT', 'full') == 'full' else 'fit=bounds') + '' + ('' if os.environ.get('VC_NOPLOT') else '&plot=1') + ('&noclip=1' if kind == 'fixed' and not os.environ.get('VC_CLIP') else ''), layout=li)
            for _ in range(2000):     # wait until the layout is loaded and the first full render finished
                if await s.js("document.body.classList.contains('clean') && typeof STAT!=='undefined' && !raf && typeof lay!=='undefined' && lay!==null && document.getElementById('msg').style.display==='none'"): break
                await asyncio.sleep(0.3)
            await asyncio.sleep(1.0)
            info['name'] = await s.js("meta.layouts[%d].name" % li)
            if os.environ.get('VC_LWK', '0') != '0':
                try:    # the fixed plot shrinks the sheet to A3 but keeps physical lineweights: scale ours to the same relative thickness
                    import fitz
                    pdf = os.path.join(odir, 'plots', '%s.%s.pdf' % (info['name'].replace(' ', '_'), kind))
                    pg = fitz.open(pdf)[0]
                    xs = [v for d in pg.get_drawings() for v in (d['rect'].x0, d['rect'].x1)]
                    full = await s.js("JSON.stringify(lay.full)"); full = json.loads(full)
                    k = (full[2] - full[0]) / ((max(xs) - min(xs)) / 2.8346)
                    k = min(max(k, 0.5), 8)
                    await s.js("(()=>{const e=document.getElementById('lwK'); e.max=8; e.value=%f; e.oninput({target:e});})()" % k)
                    info['lwk'] = round(k, 2)
                    await asyncio.sleep(1.5)
                except Exception as ex:
                    info['lwk'] = str(ex)[:60]
            await s.shot(png)
    asyncio.run(shoot())
    return compare(stem, li, info['name'], png, out, kind)


def compare(stem, li, lname, png, out, kind='fixed'):
    """score our rendering png against the oracle plot of layout lname (pdf pages are rasterised at 110 dpi)"""
    odir = os.path.join(ORA, stem)
    pdf = os.environ.get('VC_PDF') or os.path.join(odir, 'plots', '%s.%s.pdf' % (re.sub(r'[^\w.\-]', '_', lname), kind))     # VC_PDF: any plotted PDF as the reference
    if not os.path.exists(pdf):
        import glob
        c = glob.glob(os.path.join(odir, 'plots', '*.%s.pdf' % kind))
        raise SystemExit('no oracle pdf for %r; have %s' % (lname, [os.path.basename(x) for x in c]))
    base = os.path.join(out, '%s_L%d_ora' % (stem, li))
    subprocess.run(['pdftoppm', '-r', '110', '-png', '-singlefile', pdf, base], check=True)
    a = Image.open(png).convert('RGB'); b = Image.open(base + '.png').convert('RGB')
    ba, bb = ink_bbox(a), ink_bbox(b)
    if os.environ.get('VC_FULLPAGE'): ba, bb = (0, 0, a.width, a.height), (0, 0, b.width, b.height)     # both images are the whole sheet (pdfcompare.py): no ink-box framing
    if not ba or not bb: raise SystemExit('empty render: ours=%s oracle=%s' % (ba, bb))
    ca, cb = a.crop(ba), b.crop(bb)
    # fit ours into oracle crop size, preserving nothing: report aspect mismatch
    asp_a, asp_b = ca.width / ca.height, cb.width / cb.height
    ca = ca.resize(cb.size, Image.LANCZOS)
    ka = np.asarray(ca).min(axis=2) < 195
    kb = np.asarray(cb).min(axis=2) < 195
    def dil(m, r=2):
        im = Image.fromarray((m * 255).astype('uint8')).filter(ImageFilter.MaxFilter(2 * r + 1))
        return np.asarray(im) > 0
    da, db = dil(ka), dil(kb)
    prec = (ka & db).sum() / max(ka.sum(), 1)
    rec = (kb & da).sum() / max(kb.sum(), 1)
    da5, db5 = dil(ka, 5), dil(kb, 5)
    prec5 = (ka & db5).sum() / max(ka.sum(), 1); rec5 = (kb & da5).sum() / max(kb.sum(), 1)
    # aligned score: the two crops are framed by their ink bounding boxes, which differ when one side has extra far-away items; search scale (+-4 %) and shift
    # on 1/4 size masks (FFT cross-correlation) and rescore the full-size masks with the best transform
    def small(m): return np.asarray(Image.fromarray((m * 255).astype('uint8')).resize((m.shape[1] // 4, m.shape[0] // 4), Image.BOX)) > 40
    sa, sb = dil(small(ka) , 1), dil(small(kb), 1)
    H, W = sb.shape; FB = np.fft.rfft2(sb.astype(float))
    best = (-1, 1.0, 0, 0)
    for sc in np.arange(0.90, 1.1001, 0.005):
        M = Image.fromarray((sa * 255).astype('uint8')).transform((W, H), Image.AFFINE, (1 / sc, 0, W / 2 * (1 - 1 / sc), 0, 1 / sc, H / 2 * (1 - 1 / sc)), Image.BILINEAR)
        A = np.asarray(M) > 100
        cc = np.fft.irfft2(np.fft.rfft2(A.astype(float)) * np.conj(FB), s=(H, W))
        k = int(np.argmax(cc)); dy, dx = divmod(k, W)
        if dy > H // 2: dy -= H
        if dx > W // 2: dx -= W
        if cc.flat[k] > best[0]: best = (cc.flat[k], sc, dx, dy)
    _, bs, bdx, bdy = best
    # cc peak at (dy, dx) means A shifted by (dy, dx) matches B... our mask must move by -(dx, dy) of the correlation convention: try both signs
    def apply(sc, dx, dy):
        im = ca.transform(ca.size, Image.AFFINE, (1 / sc, 0, ca.width / 2 * (1 - 1 / sc) - dx * 4, 0, 1 / sc, ca.height / 2 * (1 - 1 / sc) - dy * 4), Image.BILINEAR, fillcolor=(255, 255, 255))
        k2 = np.asarray(im).min(axis=2) < 195
        d2, d2b = dil(k2, 5), db5
        return (k2 & d2b).sum() / max(k2.sum(), 1), (kb & d2).sum() / max(kb.sum(), 1)
    cand = [apply(bs, bdx, bdy), apply(bs, -bdx, -bdy)]
    pa5, ra5 = max(cand, key=lambda t: t[0] + t[1])
    diff = np.full(kb.shape + (3,), 255, 'uint8')
    diff[kb & ~da] = (220, 0, 0)      # only oracle (missing in ours)
    diff[ka & ~db] = (0, 0, 220)      # only ours (extra)
    diff[ka & kb] = (0, 0, 0)
    side = Image.new('RGB', (cb.width * 3 + 20, cb.height), 'white')
    side.paste(cb, (0, 0)); side.paste(ca, (cb.width + 10, 0)); side.paste(Image.fromarray(diff), (2 * cb.width + 20, 0))
    sp = os.path.join(out, '%s_L%d_side.png' % (stem, li)); side.save(sp)
    res = dict(file=stem, layout=lname, aspect_ours=round(asp_a, 3), aspect_oracle=round(asp_b, 3), ink_precision=round(float(prec), 3), ink_recall=round(float(rec), 3), p5=round(float(prec5), 3), r5=round(float(rec5), 3), p5a=round(float(pa5), 3), r5a=round(float(ra5), 3), align=[round(float(bs), 3), int(bdx) * 4, int(bdy) * 4], side=sp)
    print(json.dumps(res))
    return res



if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('file'); ap.add_argument('layout', type=int)
    ap.add_argument('--out', default=os.path.expanduser('~/review-compare-dwg'))
    ap.add_argument('--kind', default='fixed'); ap.add_argument('--port', type=int)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    run(a.file, a.layout, out=a.out, kind=a.kind, port=a.port)
