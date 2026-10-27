"""Disk cache of the scene JSON (meta + every layout) so re-opening a drawing does not re-parse it. Key = file size+mtime+head/tail hash + code stamp."""
import os, json, gzip, hashlib, glob, threading

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.environ.get('DWG_VIEW_CACHE', os.path.expanduser('~/.cache/dwg-viewer/scenes'))


def code_stamp():
    h = hashlib.sha1()
    for f in sorted(glob.glob(os.path.join(HERE, 'dwg*.py')) + glob.glob(os.path.join(HERE, 'dwgviewer', '*.py'))):
        st = os.stat(f); h.update(('%s:%d:%d' % (os.path.basename(f), st.st_size, int(st.st_mtime))).encode())
    return h.hexdigest()[:10]


def key(path):
    st = os.stat(path)
    h = hashlib.sha1()
    with open(path, 'rb') as f:
        h.update(f.read(1 << 16)); f.seek(max(0, st.st_size - (1 << 16))); h.update(f.read(1 << 16))
    return '%s_%d_%s_%s%s' % (os.path.splitext(os.path.basename(path))[0][:40], st.st_size, h.hexdigest()[:10], code_stamp(), _sibling_stamp(path))


def _sibling_stamp(path):
    """xrefs are drawn from DWG files next to the drawing, so the cache must notice when one of them appears or changes (first 400 siblings)"""
    try:
        d = os.path.dirname(os.path.abspath(path)); me = os.path.abspath(path); h = hashlib.sha1(); n = 0
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith('.dwg') or os.path.join(d, f) == me: continue
            st = os.stat(os.path.join(d, f)); h.update(('%s:%d:%d' % (f, st.st_size, int(st.st_mtime))).encode()); n += 1
            if n >= 400: break
        for x in [q for q in os.environ.get('DWG_XREF_PATH', '').split(os.pathsep) if q]:      # extra xref folders: part of the key too
            for f in sorted(os.listdir(x))[:400]:
                if f.lower().endswith('.dwg'): st = os.stat(os.path.join(x, f)); h.update(('%s:%s:%d:%d' % (x, f, st.st_size, int(st.st_mtime))).encode()); n += 1
        return '_x' + h.hexdigest()[:6] if n else ''
    except OSError:
        return ''


def dirfor(path):
    return os.path.join(ROOT, key(path))


def read_meta(path):
    p = os.path.join(dirfor(path), 'meta.json')
    if os.path.isfile(p):
        try: return json.load(open(p))
        except Exception: return None


def layout_path(path, i, twist):
    return os.path.join(dirfor(path), 'layout_%d_%d.json.gz' % (i, 1 if twist else 0))


def read_layout(path, i, twist):
    """Return cached gzip bytes, or remove a missing, short, or non-gzip entry and return None."""
    p = layout_path(path, i, twist)
    try:
        with open(p, 'rb') as f:
            body = f.read()
    except FileNotFoundError:
        body = b''
    if len(body) >= 18 and body.startswith(b'\x1f\x8b'):
        return body
    try:
        os.remove(p)
    except OSError:
        pass
    return None


def prune_stale(path):
    """remove cached scenes of this file written by older code stamps (every edit of the viewer changes the stamp)"""
    import shutil
    k = os.path.basename(dirfor(path)); pre = k.rsplit('_', 1)[0] + '_'
    try:
        for n in os.listdir(ROOT):
            if n.startswith(pre) and n != k and os.path.isdir(os.path.join(ROOT, n)): shutil.rmtree(os.path.join(ROOT, n), ignore_errors=True)
    except OSError:
        pass


def write_meta(path, meta):
    d = dirfor(path); os.makedirs(d, exist_ok=True)
    prune_stale(path)
    tmp = os.path.join(d, 'meta.json.%d.%d.tmp' % (os.getpid(), threading.get_ident())); json.dump(meta, open(tmp, 'w')); os.replace(tmp, os.path.join(d, 'meta.json'))


def write_layout(path, i, twist, data):
    p = layout_path(path, i, twist); os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = '%s.%d.%d.tmp' % (p, os.getpid(), threading.get_ident())   # prefetch and a request may write the same layout at once
    try:
        with gzip.open(tmp, 'wb', compresslevel=1) as f: f.write(json.dumps(data, separators=(',', ':')).encode())
        os.replace(tmp, p)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def prune(keep=12):
    """drop the oldest cache entries beyond `keep` (keeps the demo files warm without growing forever)"""
    try:
        ds = sorted((os.path.getmtime(d), d) for d in glob.glob(os.path.join(ROOT, '*')) if os.path.isdir(d))
        import shutil
        for _, d in ds[:-keep]: shutil.rmtree(d, ignore_errors=True)
    except Exception: pass
