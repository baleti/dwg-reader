"""Read the vector subset of MS-EMF into simple drawing primitives."""

import math
import struct


_IDENTITY = (1, 0, 0, 1, 0, 0)


def _compose(first, second):
    """Compose row-vector GDI transforms, applying first before second."""
    a, b, c, d, x, y = first
    e, f, g, h, u, v = second
    return (a*e + b*g, a*f + b*h, c*e + d*g, c*f + d*h,
            x*e + y*g + u, x*f + y*h + v)


def _rgb(color):
    return (color & 255, (color >> 8) & 255, (color >> 16) & 255)


def parse(data: bytes) -> dict | None:
    """Parse supported records; retain completed primitives on damaged input."""
    if len(data) < 88:
        return None
    kind, size = struct.unpack_from('<II', data)
    if kind != 1 or size < 88 or struct.unpack_from('<I', data, 40)[0] != 0x464D4520:
        return None
    result = {'bounds': struct.unpack_from('<4i', data, 8),
              'frame': struct.unpack_from('<4i', data, 24), 'prims': []}
    objects = {}
    pen, width, brush = (0, 0, 0), 1, None
    current = (0, 0)
    transform = _IDENTITY

    def emit(points, closed=False):
        a, b, c, d, x, y = transform
        prim = {'k': 'poly' if closed else 'line',
                'pts': [(px*a + py*c + x, px*b + py*d + y)
                        for px, py in points], 'rgb': pen, 'w': width}
        if closed:
            prim['fill'] = brush
        result['prims'].append(prim)

    offset = size
    if size % 4:
        return result
    while offset + 8 <= len(data):
        kind, size = struct.unpack_from('<II', data, offset)
        if size < 8 or size % 4 or size > len(data) - offset:
            break
        payload = memoryview(data)[offset + 8:offset + size]
        offset += size
        if kind == 14:
            break

        def read(fmt, pos=0):
            return struct.unpack_from('<' + fmt, payload, pos)

        def points(count, pos, short=True):
            stride = 4 if short else 8
            if count > (len(payload) - pos) // stride:
                raise struct.error('incomplete point array')
            return list(struct.iter_unpack('<hh' if short else '<ii',
                                          payload[pos:pos + count * stride]))

        try:
            if kind in (3, 4, 86, 87, 89):
                count, = read('I', 16)
                pts = points(count, 20, kind not in (3, 4))
                if kind == 89:
                    if pts:
                        emit([current] + pts)
                        current = pts[-1]
                else:
                    emit(pts, kind in (3, 86))
            elif kind in (90, 91):
                npolys, count = read('II', 16)
                if npolys > (len(payload) - 24) // 4:
                    continue
                counts = read(str(npolys) + 'I', 24)
                if sum(counts) != count:
                    continue
                pts = points(count, 24 + 4 * npolys)
                start = 0
                for n in counts:
                    emit(pts[start:start + n], kind == 91)
                    start += n
            elif kind in (27, 54):
                point = read('ii')
                if kind == 54:
                    emit([current, point])
                current = point
            elif kind in (42, 43):
                left, top, right, bottom = read('4i')
                if kind == 43:
                    pts = [(left, top), (right, top), (right, bottom), (left, bottom)]
                else:
                    cx, cy = (left + right) / 2, (top + bottom) / 2
                    rx, ry = (right - left) / 2, (bottom - top) / 2
                    pts = [(cx + rx * math.cos(i * math.tau / 48),
                            cy + ry * math.sin(i * math.tau / 48)) for i in range(48)]
                emit(pts, True)
            elif kind == 38:
                handle, style, w, unused_y, color = read('IIiiI')
                if handle:
                    objects[handle] = ('pen', None if style & 15 == 5 else _rgb(color), w)
            elif kind == 95:
                handle, = read('I')
                style, w, brushstyle, color, hatch, entries = read('6I', 20)
                if handle:
                    objects[handle] = ('pen', None if style & 15 == 5 else _rgb(color), w)
            elif kind == 39:
                handle, style, color, hatch = read('4I')
                if handle:
                    objects[handle] = ('brush', None if style == 1 else _rgb(color))
            elif kind == 37:
                handle, = read('I')
                obj = objects.get(handle)
                if handle & 0x80000000:
                    stock = handle & 0x7fffffff
                    if stock <= 5:
                        gray = (255, 192, 128, 64, 0, None)[stock]
                        obj = ('brush', None if gray is None else (gray,) * 3)
                    elif stock in (6, 7, 8):
                        obj = ('pen', {6: (255, 255, 255), 7: (0, 0, 0), 8: None}[stock], 1)
                    else:
                        obj = None
                if obj:
                    if obj[0] == 'pen':
                        pen, width = obj[1:]
                    else:
                        brush = obj[1]
            elif kind == 40:
                handle, = read('I')
                objects.pop(handle, None)
            elif kind == 35:
                transform = read('6f')
            elif kind == 36:
                values = read('6fI')
                xf, mode = values[:6], values[6]
                if mode == 1:
                    transform = _IDENTITY
                elif mode == 2:
                    transform = _compose(xf, transform)
                elif mode == 3:
                    transform = _compose(transform, xf)
                elif mode == 4:
                    transform = xf
        except struct.error:
            # A malformed payload cannot read into the following record.
            continue
    return result


def polylines(res, flip_y=True):
    """Return coloured outlines, optionally reflecting y about the bounds."""
    if res is None:
        return []
    out = []
    ysum = res['bounds'][1] + res['bounds'][3]
    for prim in res['prims']:
        if prim['k'] not in ('line', 'poly'):
            continue
        pts = list(prim['pts'])
        if prim['k'] == 'poly' and pts and pts[-1] != pts[0]:
            pts.append(pts[0])
        if flip_y:
            pts = [(x, ysum - y) for x, y in pts]
        out.append((prim['rgb'], pts))
    return out
