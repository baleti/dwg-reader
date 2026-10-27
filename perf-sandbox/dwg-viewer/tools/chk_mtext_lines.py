#!/usr/bin/env python3
"""chk_mtext_lines.py FILE... : MTEXT line layout versus AutoCAD's own result stored in the file (ext_w, ext_h). Simulates our word wrap with the fallback font
(PIL, Liberation Sans) and compares the number of lines and the widest line with AutoCAD's. Pure python, no browser: run on host1."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import ImageFont
import dwgscene
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
F = {(0, 0): ImageFont.truetype(os.path.join(HERE, 'web/fonts/LiberationSans-Regular.ttf'), 1000), (1, 0): ImageFont.truetype(os.path.join(HERE, 'web/fonts/LiberationSans-Bold.ttf'), 1000)}
CAP = 0.716


def bold(font):
    n = (font or '').lower()
    return 1 if re.search(r'bd|bold|black', n) else 0


def plain(s):
    s = re.sub(r'\\[fFHhCcWwQqTtAap][^;]*;', '', s)
    s = re.sub(r'\\S([^;^/#]*)[/^#]([^;]*);', r'\1/\2', s)
    s = s.replace('\\P', '\n').replace('\\~', ' ').replace('\\\\', '\\')
    s = re.sub(r'\\[LlOoKk]', '', s); s = re.sub(r'[{}]', '', s)
    s = re.sub(r'\\U\+([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), s)
    return s.replace('%%c', 'Ø').replace('%%d', '°').replace('%%p', '±')


def simulate(text, h, w, font, wf, calib=1.0):
    mh = re.search(r'\\H([0-9.]+)x;', text)
    if mh: h = h * float(mh.group(1))     # relative height code scales the whole run (the common case: one run)
    f = F[(bold(font), 0)]; em = h / CAP
    wid = lambda t: f.getlength(t) / 1000 * em * wf * calib
    lines = []
    for para in plain(text).split('\n'):
        if w <= 0: lines.append(para); continue
        cur = ''
        for tok in re.findall(r'\S+\s*|\s+', para):
            if cur and wid((cur + tok).rstrip()) > w + 1e-6: lines.append(cur); cur = tok
            else: cur += tok
        lines.append(cur)
    return lines, max([wid(l.rstrip()) for l in lines] or [0])


def main(files, calib=1.0):
    tot = agree = 0; ratios = []; worse = []; perfont = {}
    for fn in files:
        try: sc = dwgscene.Scene(open(fn, 'rb').read())
        except Exception as ex: print(os.path.basename(fn), 'skip', ex); continue
        m = sc.m; styles = m.styles(); byh = {st['handle']: st for st in styles.values()}
        for es in sc.by_block.values():
            for e in es:
                if e['kind'] != 'MTEXT' or not e.get('ext_h') or not e.get('ext_w') or not e['text_height']: continue
                h = e['text_height']; st = byh.get(e.get('style_handle')) or styles.get(e.get('style') or '') or {}
                font = st.get('font'); wf = st.get('width_factor') or 1.0
                mh = re.search(r'\\H([0-9.]+)x;', e['text']); hh = h * (float(mh.group(1)) if mh else 1.0)
                n_ac = max(1, round((e['ext_h'] / hh - 1.3333) / 1.6667) + 1)
                lines, wmax = simulate(e['text'], h, e.get('width') or 0, font, wf, calib)
                tot += 1; agree += (len(lines) == n_ac)
                ratios.append(e['ext_w'] / wmax if wmax else 1)
                if len(lines) == 1 and n_ac == 1 and wmax: perfont.setdefault((font or '').lower(), []).append(e['ext_w'] / wmax)
                if len(lines) != n_ac and len(worse) < 5: worse.append((os.path.basename(fn), e['handle'], n_ac, len(lines), round(e['width'] or 0, 1), round(e['ext_w'], 1), round(wmax, 1), font))
    ratios.sort()
    print('MTEXT checked', tot, 'line count agrees', agree, '(%.1f%%)' % (100 * agree / max(tot, 1)), 'ext_w/ours median %.3f p10 %.3f p90 %.3f' % (ratios[len(ratios) // 2], ratios[len(ratios) // 10], ratios[9 * len(ratios) // 10]) if ratios else '')
    for w in worse: print('  ', w)
    for fo, v in sorted(perfont.items(), key=lambda x: -len(x[1]))[:8]:
        v.sort(); print('  font %-14s n=%4d single-line ext_w/ours median %.3f p10 %.3f p90 %.3f' % (fo, len(v), v[len(v) // 2], v[len(v) // 10], v[9 * len(v) // 10]))
    return tot, agree


if __name__ == '__main__':
    main(sys.argv[1:])
