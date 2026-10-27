'use strict';

function snapSegIntersect(ax, ay, bx, by, cx, cy, dx, dy) {
  const rx = bx - ax, ry = by - ay;
  const sx = dx - cx, sy = dy - cy;
  const rscale = Math.max(Math.abs(rx), Math.abs(ry));
  const sscale = Math.max(Math.abs(sx), Math.abs(sy));
  if (rscale === 0 || sscale === 0) return null;
  const ux = rx / rscale, uy = ry / rscale;
  const vx = sx / sscale, vy = sy / sscale;
  const cross = ux * vy - uy * vx;
  if (Math.abs(cross) <= 1e-9 * Math.hypot(ux, uy) * Math.hypot(vx, vy)) return null;
  const qx = cx - ax, qy = cy - ay;
  const t = ((qx / rscale) * vy - (qy / rscale) * vx) / cross;
  const u = ((qx / sscale) * uy - (qy / sscale) * ux) / cross;
  if (t < -1e-9 || t > 1 + 1e-9 || u < -1e-9 || u > 1 + 1e-9) return null;
  const clamped = Math.max(0, Math.min(1, t));
  return [ax + clamped * rx, ay + clamped * ry];
}

function snapNearestPointOnSegment(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay;
  const scale = Math.max(Math.abs(dx), Math.abs(dy));
  if (scale === 0) return [ax, ay, 0];
  const ux = dx / scale, uy = dy / scale;
  const t = Math.max(0, Math.min(1,
    ((px - ax) / scale * ux + (py - ay) / scale * uy) / (ux * ux + uy * uy)));
  return [ax + t * dx, ay + t * dy, t];
}

function snapClosed(poly, eps) {
  if (poly.length < 4) return false;
  if (eps === undefined) eps = 1e-6 * (1 + Math.abs(poly[0]));
  return Math.hypot(poly[poly.length - 2] - poly[0], poly[poly.length - 1] - poly[1]) <= eps;
}

function snapFind(polys, px, py, tol, kinds = ['end', 'mid', 'int']) {
  if (tol < 0) return null;
  const ends = kinds.includes('end'), mids = kinds.includes('mid');
  const ints = kinds.includes('int'), near = kinds.includes('near');
  const priority = {end: 0, int: 1, mid: 2, near: 3};
  const segments = [];
  let best = null;
  function snapConsider(x, y, kind) {
    const d = Math.hypot(x - px, y - py);
    if (d <= tol && (!best || d < best.d ||
        (d === best.d && priority[kind] < priority[best.kind]))) {
      best = {x, y, kind, d};
    }
  }
  for (let p = 0; p < polys.length; p++) {
    const poly = polys[p], count = poly.length / 2 - 1;
    const intersect = ints && count <= 2000;
    const closed = intersect && snapClosed(poly);
    for (let i = 0; i < count; i++) {
      const j = i * 2;
      const ax = poly[j], ay = poly[j + 1], bx = poly[j + 2], by = poly[j + 3];
      // Distance to the bounding box is a cheap rejection before geometry work.
      const gapX = Math.max(Math.min(ax, bx) - px, px - Math.max(ax, bx), 0);
      const gapY = Math.max(Math.min(ay, by) - py, py - Math.max(ay, by), 0);
      if (gapX <= tol && gapY <= tol) {
        if (ends) {
          snapConsider(ax, ay, 'end');
          snapConsider(bx, by, 'end');
        }
        if (mids) snapConsider(ax / 2 + bx / 2, ay / 2 + by / 2, 'mid');
        if (near) {
          const point = snapNearestPointOnSegment(px, py, ax, ay, bx, by);
          snapConsider(point[0], point[1], 'near');
        }
      }
      if (intersect) {
        const radius = tol + Math.hypot(bx - ax, by - ay);
        if (gapX > radius || gapY > radius) continue;
        const point = snapNearestPointOnSegment(px, py, ax, ay, bx, by);
        if (Math.hypot(point[0] - px, point[1] - py) <= radius) {
          segments.push({ax, ay, bx, by, p, i, count, closed});
        }
      }
    }
  }
  for (let i = 0; i < segments.length; i++) {
    const a = segments[i];
    for (let j = i + 1; j < segments.length; j++) {
      const b = segments[j];
      // The first and last segments of a closed polyline are adjacent too.
      if (a.p === b.p && (b.i - a.i === 1 ||
          (a.closed && a.i === 0 && b.i === a.count - 1))) continue;
      const point = snapSegIntersect(a.ax, a.ay, a.bx, a.by, b.ax, b.ay, b.bx, b.by);
      if (point) snapConsider(point[0], point[1], 'int');
    }
  }
  return best;
}

if (typeof module !== 'undefined') module.exports = {snapSegIntersect, snapNearestPointOnSegment, snapFind, snapClosed};
