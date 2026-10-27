"""Convex clipping of flattened rows (INSERT spatial filters = XCLIP). Pure functions: polygons are lists of (x, y), rows are the flat.py row tuples."""


def ccw(poly):
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    return list(poly) if a >= 0 else list(reversed(poly))


def inside(poly, x, y, eps=1e-9):
    """point in a convex counter-clockwise polygon (edges included)"""
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]; bx, by = poly[(i + 1) % n]
        if (bx - ax) * (y - ay) - (by - ay) * (x - ax) < -eps: return False
    return True


def clip_segment(poly, x0, y0, x1, y1):
    """(t0, t1) part of the segment inside the convex CCW polygon (Cyrus-Beck) or None"""
    t0, t1 = 0.0, 1.0; dx, dy = x1 - x0, y1 - y0
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]; bx, by = poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        num = ex * (y0 - ay) - ey * (x0 - ax)       # >= 0 means inside for the start point
        den = ex * dy - ey * dx                       # change of that value along the segment
        if abs(den) < 1e-15:
            if num < 0: return None
            continue
        t = -num / den
        if den > 0:
            if t > t0: t0 = t
        else:
            if t < t1: t1 = t
        if t0 > t1: return None
    return t0, t1


def clip_polyline(poly, f):
    """flat [x0, y0, x1, y1, ...] -> list of flat pieces inside the polygon"""
    out = []; cur = None
    for i in range(0, len(f) - 3, 2):
        x0, y0, x1, y1 = f[i], f[i + 1], f[i + 2], f[i + 3]
        r = clip_segment(poly, x0, y0, x1, y1)
        if r is None:
            cur = None; continue
        t0, t1 = r
        a = (x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0)
        b = (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)
        if cur is not None and t0 == 0.0 and abs(cur[-2] - a[0]) < 1e-9 and abs(cur[-1] - a[1]) < 1e-9:
            cur.extend(b)
        else:
            cur = [a[0], a[1], b[0], b[1]]; out.append(cur)
        if t1 < 1.0: cur = None
    return out


def clip_loop(poly, pts):
    """Sutherland-Hodgman: polygon loop [(x, y)...] clipped by the convex CCW polygon"""
    out = list(pts); n = len(poly)
    for i in range(n):
        if not out: break
        ax, ay = poly[i]; bx, by = poly[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        side = lambda p: ex * (p[1] - ay) - ey * (p[0] - ax)
        inp, out = out, []
        for j in range(len(inp)):
            p, q = inp[j], inp[(j + 1) % len(inp)]
            sp, sq = side(p), side(q)
            if sp >= 0: out.append(p)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq); out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def clip_rows(rows, poly):
    """rows clipped to the convex polygon (any orientation): lines are cut, hatch loops intersected, text / points kept when their anchor is inside"""
    poly = ccw(poly); out = []
    for r in rows:
        k = r[0]
        if k == 'l':
            for piece in clip_polyline(poly, r[5]):
                out.append(r[:5] + (piece,) + r[6:])
        elif k == 'h':
            loops = []
            for lp in r[3]:
                pts = [(lp[i], lp[i + 1]) for i in range(0, len(lp) - 1, 2)]
                c = clip_loop(poly, pts)
                if len(c) >= 3: loops.append([v for p in c for v in p])
            if loops: out.append(r[:3] + (loops,) + r[4:])
        elif k in ('t', 'p'):
            if inside(poly, r[3], r[4]): out.append(r)
        else:
            out.append(r)
    return out
