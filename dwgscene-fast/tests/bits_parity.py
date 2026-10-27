"""differential test: dwgscene_fast.Bits vs dwgbits.Bits (random streams, random op sequences, exceptions must match in type)"""
import sys, os, random, struct, math
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, '..')); sys.path.insert(0, os.path.expanduser('~/dwg-viewer'))
import dwgbits, dwgscene_fast as R
rnd = random.Random(11)
OPS = ['bit', 'B', 'BB', 'BS', 'BL', 'BD', 'RC', 'RS', 'RL', 'RD', 'H', 'BD3', 'RD2', 'BT', 'BE', 'BLL', 'TV', 'TU', 'bits', 'DD', 'cnt', 'rcs', '_raw']
def call(o, op, arg):
    f = getattr(o, op)
    if op == 'bits': return f(arg % 70)
    if op == 'DD': return f(rnd_default[0])
    if op == 'cnt': return f(arg % 50, 8)
    if op in ('rcs', '_raw'): return f(arg % 20)
    return f()
def same(a, b):
    if isinstance(a, float) and isinstance(b, float): return struct.pack('<d', a) == struct.pack('<d', b)
    if isinstance(a, tuple) and isinstance(b, tuple): return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return bytes(a) == bytes(b) if isinstance(a, (bytes, bytearray, memoryview)) else (a == b and type(a) == type(b))
bad = 0; n = 0
rnd_default = [1.5]
for trial in range(4000):
    data = bytes(rnd.getrandbits(8) for _ in range(rnd.randint(0, 80)))
    pos = rnd.randint(0, 40)
    py = dwgbits.Bits(data, pos); rs = R.Bits(data, pos)
    rnd_default[0] = rnd.choice([1.5, 0.0, -3.25, 1e10])
    for _ in range(30):
        op = rnd.choice(OPS); arg = rnd.randint(0, 200); n += 1
        try: a = ('ok', call(py, op, arg))
        except Exception as e: a = ('err', type(e).__name__)
        try: b = ('ok', call(rs, op, arg))
        except Exception as e: b = ('err', type(e).__name__)
        if a[0] != b[0] or (a[0] == 'err' and a[1] != b[1]) or (a[0] == 'ok' and not same(a[1], b[1])) or py.p != rs.p:
            if not (a[0] == 'err' and b[0] == 'err'):
                bad += 1; print('DIFF', op, arg, a, b, py.p, rs.p)
                if bad > 10: sys.exit(1)
            break
        if a[0] == 'err': break
print('BITS PARITY', 'FAIL %d' % bad if bad else 'OK', n, 'ops')
sys.exit(1 if bad else 0)
