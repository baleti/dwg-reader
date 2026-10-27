#!/usr/bin/env python3
"""pyrender.py FILE.dwg LAYOUT_INDEX [--out DIR] [--width 1600] : browser-free rendering of a layout (plot preview: ACI 7 black, non-plot layers hidden) with PIL,
then the same scoring as vcompare (ink precision/recall, aligned score) against the AutoCAD fixed plot. Needs no chromium, so it can run on host1.
Approximations: solid lines (no dash patterns), hatches only when solid, text with Liberation Sans (no SHX), no image placeholders."""
import sys, os, re, argparse, math
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'tools'))
from PIL import Image, ImageDraw, ImageFont, ImageChops
Image.MAX_IMAGE_PIXELS = None   # A0 oracle plots are large
import dwgscene
from dwgviewer import build

FONT = {}


def font(px):
    px = max(4, int(round(px)))
    if px not in FONT: FONT[px] = ImageFont.truetype(os.path.join(HERE, 'web', 'fonts', 'LiberationSans-Regular.ttf'), px)
    return FONT[px]


def rgb(c):
    if isinstance(c, (list, tuple)): return tuple(int(x) for x in c[:3])
    if c == 7: return (0, 0, 0)
    return tuple(dwgscene.ACI.get(c, (0, 0, 0)))


def plain(t):
    t = re.sub(r'\\[pP][^;]*;', '', t.replace('\\P', '\n'))
    t = re.sub(r'\\[A-Za-z][^;\\]*;', '', t)
    return re.sub(r'[{}]|\\[LlOoKk~]', '', t).replace('%%c', 'Ø').replace('%%d', '°').replace('%%p', '±')


def dashed(pts, pat):
    """split a pixel polyline into the 'on' pieces of the dash pattern (alternating on/off lengths in pixels)"""
    out = []; cur = []; i = 0; rem = max(pat[0], 0.5); on = True
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        L = math.hypot(x1 - x0, y1 - y0); t = 0.0
        if L == 0: continue
        if on and not cur: cur = [(x0, y0)]
        while L - t > rem:
            t += rem; pt = (x0 + (x1 - x0) * t / L, y0 + (y1 - y0) * t / L)
            if on: cur.append(pt); out.append(cur); cur = []
            else: cur = [pt]
            on = not on; i = (i + 1) % len(pat); rem = max(pat[i], 0.5)
        rem -= (L - t)
        if on: cur.append((x1, y1))
    if on and len(cur) > 1: out.append(cur)
    return [c for c in out if len(c) > 1]


class Canvas:
    def __init__(self, doc, i, width):
        self.doc, self.i = doc, i
        meta = doc.meta()
        self.meta = meta
        self.lay = doc.layout(i)
        r = self.lay
        x0, y0, x1, y1 = r['paper'] and [0, 0, r['paper'][0], r['paper'][1]] or r['full']
        if r['paper']:   # fit=full draws the sheet and anything beyond it: use the drawn extents when they exceed the sheet
            f = r['full']; x0, y0, x1, y1 = min(x0, f[0]), min(y0, f[1]), max(x1, f[2]), max(y1, f[3])
        self.k = min(width / max(x1 - x0, 1e-9), 1130 / max(y1 - y0, 1e-9))    # fit inside width x 1130 like the browser capture
        self.W = max(1, int(math.ceil((x1 - x0) * self.k))); self.H = max(1, int(math.ceil((y1 - y0) * self.k)))
        self.x0, self.y1 = x0, y1
        self.img = Image.new('RGB', (self.W, self.H), (255, 255, 255))
        self.layers = meta['layers']

    def px(self, x, y): return ((x - self.x0) * self.k, (self.y1 - y) * self.k)

    def lay_ok(self, li, frozen=()):
        if li < 0: return True
        L = self.layers[li]
        return not (L['off'] or L['frz'] or L.get('plot') is False or li in frozen)

    def draw_rows(self, rows, im, tf, frozen=(), scale=1.0, dk=None):
        """rows in their own units drawn on image im through tf(x, y) -> pixel"""
        d = ImageDraw.Draw(im)
        dk = self.k if dk is None else dk
        for p in rows:
            k = p[0]
            if not self.lay_ok(p[1], frozen): continue
            if k == 'l':
                if p[3] is not None and p[3] < 0: continue
                f = p[5]
                if len(f) < 4: continue
                lw = p[3] if p[3] else 0.25
                w = max(1, int(round(lw * self.k)))
                pts = [tf(f[j], f[j + 1]) for j in range(0, len(f) - 1, 2)]
                dash = p[4]
                if dash and len(dash) >= 2:
                    for seg in dashed(pts, [abs(v) * dk for v in dash]): d.line(seg, fill=rgb(p[2]), width=w)
                else:
                    d.line(pts, fill=rgb(p[2]), width=w, joint='curve' if w > 2 else None)
            elif k == 'h':
                info = p[4]
                if info.get('img') or info.get('wipe'):
                    if info.get('wipe'):
                        for lp in p[3]: d.polygon([tf(lp[j], lp[j + 1]) for j in range(0, len(lp) - 1, 2)], fill=(255, 255, 255))
                    continue
                if not info.get('solid') and info.get('lines'):
                    self.pattern(im, p, tf)
                    continue
                if info.get('solid'):
                    for lp in p[3]:
                        if len(lp) >= 6: d.polygon([tf(lp[j], lp[j + 1]) for j in range(0, len(lp) - 1, 2)], fill=rgb(p[2]))
            elif k == 't':
                self.text(d, im, p, tf, scale)
            elif k == 'p':
                x, y = tf(p[3], p[4]); d.point((x, y), fill=rgb(p[2]))

    def pattern(self, im, p, tf):
        """hatch pattern lines (angle, origin, family offset; dash arrays drawn solid) clipped to the hatch loops; too dense on screen -> 35 % tint like the browser"""
        loops = [lp for lp in p[3] if len(lp) >= 6]
        if not loops: return
        xs = [v for lp in loops for v in lp[0::2]]; ys = [v for lp in loops for v in lp[1::2]]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        mask = Image.new('L', im.size, 0)
        md = ImageDraw.Draw(mask)
        for lp in loops: md.polygon([tf(lp[j], lp[j + 1]) for j in range(0, len(lp) - 1, 2)], fill=255)
        col = rgb(p[2]); layer = Image.new('RGB', im.size, (255, 255, 255)); ld = ImageDraw.Draw(layer)
        ux = abs(tf(1, 0)[0] - tf(0, 0)[0]) + abs(tf(1, 0)[1] - tf(0, 0)[1])      # pixels per data unit (uniform transforms)
        dense = False
        for ang, ox, oy, fx, fy, *_ in p[4]['lines']:
            dx, dy = math.cos(ang), math.sin(ang); nx, ny = -dy, dx
            perp = fx * nx + fy * ny
            if abs(perp) < 1e-9: continue
            if abs(perp) * ux < 2.2: dense = True; break
        if dense:
            tint = tuple(int(255 - (255 - c) * 0.35) for c in col); ImageDraw.Draw(layer).rectangle([0, 0, im.size[0], im.size[1]], fill=tint)
        else:
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            for ang, ox, oy, fx, fy, *_ in p[4]['lines']:
                dx, dy = math.cos(ang), math.sin(ang); nx, ny = -dy, dx
                perp = fx * nx + fy * ny
                if abs(perp) < 1e-9: continue
                pn = [((cx - ox) * nx + (cy - oy) * ny) / perp for cx, cy in corners]
                n0, n1 = int(math.floor(min(pn))) - 1, int(math.ceil(max(pn))) + 1
                if n1 - n0 > 3000: continue
                for n in range(n0, n1 + 1):
                    px, py = ox + n * fx, oy + n * fy
                    ts = [(cx - px) * dx + (cy - py) * dy for cx, cy in corners]
                    ld.line([tf(px + dx * min(ts), py + dy * min(ts)), tf(px + dx * max(ts), py + dy * max(ts))], fill=col, width=1)
        im.paste(layer, (0, 0), mask)

    def text(self, d, im, p, tf, scale):
        h = p[5] * scale * self.k
        txt = plain(str(p[7]))
        if not txt.strip() or h < 0.6: return
        o = p[8]
        x, y = tf(p[3], p[4])
        col = rgb(p[2])
        if h < 2.2:     # faint bar like the browser
            w = len(txt) * 0.5 * h * (o.get('wf', 1.0)); d.rectangle([x, y - h, x + w, y], fill=tuple(int(255 - (255 - c) * 0.55) for c in col)); return
        lines = txt.split('\n')
        f = font(h / 0.716)
        ls = 1.6667 * h; n = len(lines); total = h + (n - 1) * ls
        vj = o.get('vj', 0); hj = o.get('hj', 0)
        if o.get('mt'): y0 = {3: 0.0, 2: total / 2, 1: total}.get(vj, total) - h
        else: y0 = {3: -h, 2: -h / 2}.get(vj, 0.0)
        for li, ln in enumerate(lines):
            w = d.textlength(ln, font=f)
            xx = x - (w / 2 if hj == 1 else w if hj == 2 else 0)
            d.text((xx, y - y0 + li * ls), ln, font=f, fill=col, anchor='ls')

    def render(self):
        r = self.lay
        d = ImageDraw.Draw(self.img)
        if r['paper']:
            d.rectangle([self.px(0, r['paper'][1]), self.px(r['paper'][0], 0)], outline=(200, 200, 200))
        self.draw_rows(r['prims'], self.img, self.px)
        for vp in r['vps']:
            a, b, c, dd, e, f = vp['M']
            layer = Image.new('RGB', (self.W, self.H), (255, 255, 255))
            tf = lambda x, y, a=a, b=b, c=c, dd=dd, e=e, f=f: self.px(a * x + c * y + e, b * x + dd * y + f)
            self.draw_rows(r['mprims'], layer, tf, frozen=set(vp['frozen']), scale=vp['scale'], dk=self.k * (1.0 if vp.get('psl') else vp['scale']))
            mask = Image.new('L', (self.W, self.H), 0)
            cl = vp['clip']
            ImageDraw.Draw(mask).polygon([self.px(cl[j], cl[j + 1]) for j in range(0, len(cl) - 1, 2)], fill=255)
            ink = layer.convert('L').point(lambda v: 255 if v < 255 else 0)      # only what the viewport actually drew (overlapping viewports must not blank each other)
            self.img.paste(layer, (0, 0), ImageChops.multiply(mask, ink))
        return self.img


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('file'); ap.add_argument('layout', type=int)
    ap.add_argument('--out', default=os.path.expanduser('~/review-compare-dwg')); ap.add_argument('--width', type=int, default=1600)
    ap.add_argument('--kind', default='fixed'); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.file))[0]
    doc = build.Doc(a.file)
    cv = Canvas(doc, a.layout, a.width)
    img = cv.render()
    png = os.path.join(a.out, '%s_L%d_ours.png' % (stem, a.layout)); img.save(png)
    import vcompare
    name = doc.meta()['layouts'][a.layout]['name']
    vcompare.compare(stem, a.layout, name, png, a.out, a.kind)


if __name__ == '__main__':
    main()
