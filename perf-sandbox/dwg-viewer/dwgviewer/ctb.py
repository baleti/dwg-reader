"""Plot style tables: ACAD .ctb (colour-dependent) reader. Own code; format = text header, 'pmzlibcodec', length words, zlib stream of key=value text."""
import re, zlib, os

SEARCH = [os.environ.get('DWG_PLOTSTYLE_DIR', ''), os.path.expanduser('~/dwg-research/oracle-out/_ref')]


def find(name):
    if not name: return None
    b = os.path.basename(name.replace('\\', '/'))
    for d in SEARCH:
        if not d: continue
        for cand in (b, b + '.ctb'):
            p = os.path.join(d, cand)
            if os.path.isfile(p): return p
        try:
            for f in os.listdir(d):
                if f.lower() in (b.lower(), b.lower() + '.ctb'): return os.path.join(d, f)
        except OSError: pass
    return None


def parse(path):
    return parse_bytes(open(path, 'rb').read())


def parse_bytes(raw):
    i = raw.find(b'pmzlibcodec')
    if i < 0: txt = raw.decode('latin1')
    else:
        j = raw.find(b'\x78', i + 11)
        while j >= 0:
            try:
                txt = zlib.decompress(raw[j:]).decode('latin1'); break
            except Exception:
                j = raw.find(b'\x78', j + 1)
        else: raise ValueError('no zlib stream')
    return txt


def table(path):
    return table_from_text(parse(path))


def table_bytes(raw):
    return table_from_text(parse_bytes(raw))


def table_from_text(txt):
    """-> {'aci': {n: {'rgb': (r,g,b)|None, 'lw': mm|None, 'screen': 0..100}}, 'lwtable': [...]} ; rgb None = use object colour"""
    m = re.search(r'custom_lineweight_table\{(.*?)\}', txt, re.S)
    lwt = []
    if m:
        for ln in m.group(1).split('\n'):
            mm = re.match(r'\s*\d+=([0-9.]+)', ln)
            if mm: lwt.append(float(mm.group(1)))
    acis = {}
    m = re.search(r'plot_style\{(.*)\}\s*$', txt, re.S)
    body = m.group(1) if m else txt
    for blk in re.finditer(r'(\d+)\{(.*?)\n\s*\}', body, re.S):
        n = int(blk.group(1)); d = dict(re.findall(r'\s*(\w+)=(.*)', blk.group(2)))
        if 'color' not in d and 'name' not in d: continue
        rgb = None
        c = d.get('color')
        if c and c.strip().lstrip('-').isdigit():
            v = int(c) & 0xFFFFFFFF
            if v != 0xFFFFFFFF: rgb = ((v >> 16) & 255, (v >> 8) & 255, v & 255)
        lw = d.get('lineweight')
        lwmm = lwt[int(lw)] if lw and lw.isdigit() and int(lw) > 0 and int(lw) < len(lwt) else None   # 0 = use object lineweight
        acis[n + 1] = {'rgb': rgb, 'lw': lwmm, 'screen': int(d.get('screen', 100))}
    return {'aci': acis, 'lwtable': lwt}
