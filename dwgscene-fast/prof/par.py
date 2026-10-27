"""prototype: serial vs fork-parallel layout build on one Doc (no viewer edits); outputs compared byte for byte"""
import sys, os, time, json, hashlib
sys.path.insert(0, os.path.expanduser('~/dwg-viewer'))
sys.path.insert(0, os.path.expanduser('~/dwg-research/dwgscene-fast'))
from dwgviewer import build, flat as F
import fastflat
if os.environ.get('FAST'): fastflat.install(F)
from dwgviewer import build
f = sys.argv[1]
def jobs(m): return [(l['i'], tw) for l in m['layouts'] for tw in ((True, False) if not l['ps'] else (True,))]
def enc(s):
    s = dict(s); s.pop('build_s', None); s.pop('tl', None)
    return json.dumps(s, separators=(',', ':')).encode()
t = time.time(); d = build.Doc(f); m = d.meta(); t_parse = time.time() - t
J = jobs(m)
t = time.time(); ser = {j: hashlib.md5(enc(d.layout(*j))).hexdigest() for j in J}; t_ser = time.time() - t
d2 = build.Doc(f); d2.meta()
t = time.time(); pipes = {}
for j in J:
    r, w = os.pipe(); pid = os.fork()
    if pid == 0:
        os.close(r); b = enc(d2.layout(*j))
        with os.fdopen(w, 'wb') as fh: fh.write(hashlib.md5(b).hexdigest().encode())
        os._exit(0)
    os.close(w); pipes[j] = (pid, r)
par = {}
for j, (pid, r) in pipes.items():
    with os.fdopen(r, 'rb') as fh: par[j] = fh.read().decode()
    os.waitpid(pid, 0)
t_par = time.time() - t
print(os.path.basename(f), 'jobs', len(J), 'parse+meta %.2f' % t_parse, 'serial %.2f' % t_ser, 'fork-parallel %.2f' % t_par, 'IDENTICAL' if ser == par else 'DIFF')
