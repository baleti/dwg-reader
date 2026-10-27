#!/usr/bin/env python3
"""Apply the scene fast path to a dwg viewer/ballet source tree (idempotent). Usage: apply_to_viewer.py TREE PKG   (PKG = dwgballet or dwgviewer)
Copies fastflat.py + dwgscene_fast.abi3.so, patches PKG/flat.py (hook), PKG/build.py (_round, native Bits), PKG/cache.py (gzip level 1), PKG/server.py
(per-layout locks, default layout first, forked prefetch workers). Without the .so everything runs in pure Python; DWG_NO_FAST=1 / DWG_NO_FORK=1 switch parts off."""
import sys, os, shutil
tree, pkg = sys.argv[1], sys.argv[2]; here = os.path.dirname(os.path.abspath(__file__))
P = lambda f: os.path.join(tree, pkg, f)
def sub(path, old, new, marker):
    s = open(path).read()
    if marker in s: return
    assert old in s, (path, old[:50])
    open(path, 'w').write(s.replace(old, new, 1))
ff = open(os.path.join(here, 'fastflat.py')).read()
ff = ff.replace("sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\nimport dwgscene_fast as R", "sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))\nimport dwgscene_fast as R")
ff = ff.replace("        if os.environ.get('DWG_NO_FAST') or getattr(self, '_cull', None) is not None and not os.environ.get('DWG_NO_CULL'):",
                "        if os.environ.get('DWG_NO_FAST') or getattr(self, '_cull', None) is not None and not os.environ.get('DWG_NO_CULL') or (depth == 0 and getattr(self, 'anno_cur', None) is not None):")
ff = ff.replace("    try:\n        from dwgviewer import build as _b\n        _b._round = R.round_list\n    except Exception: pass\n", "")
open(os.path.join(tree, pkg, 'fastflat.py'), 'w').write(ff)
shutil.copy(os.path.join(here, 'dwgscene_fast.abi3.so'), os.path.join(tree, 'dwgscene_fast.abi3.so'))
s = open(P('flat.py')).read()
if '_ff.install' not in s:
    open(P('flat.py'), 'a').write('''

try:    # optional Rust fast path (dwgscene_fast.abi3.so next to dwgfast); DWG_NO_FAST=1 disables it
    if not os.environ.get('DWG_NO_FAST'):
        import sys as _sys
        from . import fastflat as _ff
        _ff.install(_sys.modules[__name__])
except Exception:
    pass
''')
sub(P('build.py'), "def _nobb(x, y, g=True): pass", """try:
    import dwgscene_fast as _R
    if not os.environ.get('DWG_NO_FAST'): _round = _R.round_list
except Exception:
    pass


def _nobb(x, y, g=True): pass""", '_R.round_list')
sub(P('build.py'), "fastbits.apply()    # bit-identical", """try:
    if os.environ.get('DWG_NO_FAST'): raise ImportError
    import dwgscene_fast as _R0, dwgbits as _B0
    _B0.Bits = _R0.Bits     # native bit reader (dwgscene-fast/tests/bits_parity.py)
except ImportError:
    fastbits.apply()    # bit-identical""", '_B0.Bits')
sub(P('cache.py'), "compresslevel=3)", "compresslevel=1)", 'compresslevel=1')
s = open(P('server.py')).read()
if 'klock' not in s:
    a = s.index('    def prefetch_all(d, path):'); b = s.index("    app.on_startup.append(lambda a: asyncio.ensure_future(load(a)))")
    s = s[:a] + '''    import threading
    locks = {}

    def klock(path, i, tw):
        return locks.setdefault((path, i, bool(tw)), threading.Lock())    # one build per layout at a time: a request waits for the prefetch of the same layout

    def prefetch_all(d, path):
        """default layout first (in this process), the others in forked workers that write the cache themselves (POSIX); serial elsewhere"""
        m = state['meta']
        order = [m['default']] + [l['i'] for l in m['layouts'] if l['i'] != m['default']]
        jobs = [(i, tw) for i in order for tw in ((True, False) if not m['layouts'][i]['ps'] else (True,))]
        todo = [j for j in jobs if not os.path.exists(cache.layout_path(path, *j))]
        first = [j for j in todo if j[0] == m['default']]; rest = [j for j in todo if j[0] != m['default']]
        for j in first:
            with klock(path, *j):
                if not os.path.exists(cache.layout_path(path, *j)): cache.write_layout(path, j[0], j[1], d.layout(*j))
        if hasattr(os, 'fork') and len(rest) > 1 and not os.environ.get('DWG_NO_FORK'):
            nw = max(1, min(len(rest), (os.cpu_count() or 2) - 1, 3)); running = {}
            for j in rest:
                while len(running) >= nw:
                    pid, _ = os.wait(); running.pop(pid, None)
                pid = os.fork()
                if pid == 0:
                    code = 0
                    try: cache.write_layout(path, j[0], j[1], d.layout(*j))
                    except BaseException: code = 1
                    os._exit(code)
                running[pid] = j
            while running:
                pid, _ = os.wait(); running.pop(pid, None)
        else:
            for j in rest: cache.write_layout(path, j[0], j[1], d.layout(*j))
        cache.prune()
''' + s[b:]
    old = """        r = await loop.run_in_executor(None, d.layout, i, tw)
        await loop.run_in_executor(None, lambda: _safe(lambda: cache.write_layout(path, i, tw, r)))
        body = cache.read_layout(path, i, tw)"""
    assert old in s
    s = s.replace(old, """        def build_one():
            with klock(path, i, tw):
                if not os.path.exists(cache.layout_path(path, i, tw)):
                    r_ = d.layout(i, tw); _safe(lambda: cache.write_layout(path, i, tw, r_)); return r_
            return None
        r = await loop.run_in_executor(None, build_one)
        body = cache.read_layout(path, i, tw)
        if r is None and body is None: r = await loop.run_in_executor(None, d.layout, i, tw)""", 1)
    open(P('server.py'), 'w').write(s)
print('applied to', tree, pkg)
