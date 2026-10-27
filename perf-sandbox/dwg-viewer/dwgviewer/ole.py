"""OLE2FRAME: embedded OLE object (typically a pasted bitmap). Layout measured on AC1015_53 (3 frames, all bitmaps):
common entity data, BS flags, BS mode, BL byte count, then the bytes: a 128-byte frame header (u16 + four corner points TL, TR, BR, BL as 3 doubles each,
starting at byte 2) followed by an OLE2 compound file whose stream '\\x01Ole10Native' = u32 size + a BMP (or PNG/JPEG) file."""
import io, os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgent, dwgmodel

_cache = {}


def _bytes(o):
    r = dwgent.start_reader(o)
    e = dwgent.common_entity(r, o.ver)
    r.BS(); r.BS()
    n = r.BL()
    if n <= 0 or n > 64 << 20: raise ValueError('bad OLE length')
    return e, bytes(r.RC() for _ in range(n))


def decode_ole2frame(o):
    e, data = _bytes(o)
    pts = [struct.unpack_from('<3d', data, 2 + 24 * i) for i in range(4)]
    e.update(kind='OLE2FRAME', pts=pts, ext=(0.0, 0.0, 1.0), size=len(data))
    return e


def _emfplus_png(b):
    """first compressed bitmap (PNG/JPEG) of the EMF+ Image objects (record 0x4008, image type 1) inside the EMF of an OlePres stream; None if there is none"""
    import io
    from PIL import Image
    i = b.find(b' EMF')
    if i < 40: return None
    emf = b[i - 40:]
    p = 0
    while p + 8 <= len(emf):
        t, n = struct.unpack_from('<II', emf, p)
        if n < 8: break
        if t == 70 and emf[p + 12:p + 16] == b'EMF+':
            blob = emf[p + 12:p + 8 + struct.unpack_from('<I', emf, p + 8)[0] + 4]
            q = 4
            while q + 12 <= len(blob):
                rt, fl, sz, ds = struct.unpack_from('<HHII', blob, q)
                if sz < 12: break
                if rt == 0x4008 and (fl >> 8) & 0x7f == 5:
                    body = blob[q + 12:q + 12 + ds]
                    ver, typ = struct.unpack_from('<II', body, 0)
                    if typ == 1:
                        w, h, stride, pf, bt = struct.unpack_from('<iiiII', body, 8)
                        if bt == 1:
                            from PIL import ImageFile
                            ImageFile.LOAD_TRUNCATED_IMAGES = True      # the stored JPEG is short by a byte
                            im = Image.open(io.BytesIO(body[28:])); im.load()
                            buf = io.BytesIO(); im.convert('RGBA').save(buf, 'PNG'); return buf.getvalue()
                q += sz
        p += n
    return None


def image_png(o):
    """PNG bytes of the embedded picture, None when the frame holds no picture we can read"""
    if o.handle in _cache: return _cache[o.handle]
    out = None
    try:
        import olefile
        from PIL import Image
        e, data = _bytes(o)
        ole = olefile.OleFileIO(io.BytesIO(data[128:]))
        if ole.exists('\x01Ole10Native'):
            b = ole.openstream('\x01Ole10Native').read()
            for magic in (b'BM', b'\x89PNG', b'\xff\xd8\xff'):
                i = b.find(magic, 0, 600)
                if i >= 0:
                    im = Image.open(io.BytesIO(b[i:])); im.load()
                    buf = io.BytesIO(); im.convert('RGBA').save(buf, 'PNG'); out = buf.getvalue(); break
        if out is None:     # other servers (Word ...): a JPEG/PNG inside any stream, e.g. the Word 'Data' stream (the copy inside the EMF+ presentation is damaged)
            from PIL import ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True
            best = None
            for st in ole.listdir():
                nm = '/'.join(st)
                if 'OlePres' in nm: continue
                b = ole.openstream(st).read()
                for magic in (b'\xff\xd8\xff', b'\x89PNG'):
                    i = b.find(magic)
                    if i >= 0:
                        try:
                            im = Image.open(io.BytesIO(b[i:])); im.load()
                            if best is None or im.width * im.height > best.width * best.height: best = im
                        except Exception: pass
            if best is not None:
                buf = io.BytesIO(); best.convert('RGBA').save(buf, 'PNG'); out = buf.getvalue()
        if out is None and ole.exists('\x02OlePres000'):     # Word/other server: the cached presentation is an EMF whose EMF+ comment carries the picture (compressed bitmap object)
            out = _emfplus_png(ole.openstream('\x02OlePres000').read())
    except Exception:
        out = None
    _cache[o.handle] = out
    return out


dwgmodel.ENT_DECODERS[74] = decode_ole2frame
