"""Faster, bit-identical versions of the hot readers of dwgbits.Bits (RC, RS, RL, RD, H, DD): they decode a whole window with one integer operation instead of
8 single-byte reads. Applied on import by dwgviewer.build; tools/chk_fastbits.py compares the decoded entities with and without it."""
import struct
import dwgbits

_orig = {k: getattr(dwgbits.Bits, k) for k in ('RC', 'RS', 'RL', 'RD', 'H', 'DD')}
_unpack_d = struct.Struct('<d').unpack


def RC(self):
    i = self.p; d = self.d; a = i >> 3; s = i & 7
    if s == 0: v = d[a]
    else: v = (((d[a] << 8) | d[a + 1]) >> (8 - s)) & 255
    self.p = i + 8
    return v


def RS(self):
    v = self.bits(16)
    return ((v & 255) << 8) | (v >> 8)


def RL(self):
    return int.from_bytes(self.bits(32).to_bytes(4, 'big'), 'little')


def RD(self):
    return _unpack_d(self.bits(64).to_bytes(8, 'big'))[0]


def H(self):
    code = self.bits(4)
    n = self.bits(4)
    return code, (self.bits(8 * n) if n else 0)


def DD(self, default):
    c = self.bits(2)
    if c == 0: return default
    if c == 3: return RD(self)
    b = struct.pack('<d', default)
    if c == 1:
        nb = self.bits(32).to_bytes(4, 'big') + b[4:]
    else:
        x = self.bits(48).to_bytes(6, 'big')
        nb = x[2:6] + x[0:2] + b[6:]
    return _unpack_d(nb)[0]


def apply():
    for k, f in (('RC', RC), ('RS', RS), ('RL', RL), ('RD', RD), ('H', H), ('DD', DD)):
        setattr(dwgbits.Bits, k, f)


def restore():
    for k, f in _orig.items(): setattr(dwgbits.Bits, k, f)
