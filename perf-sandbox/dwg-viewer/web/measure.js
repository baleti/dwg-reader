'use strict';

function validPoint(p) {
  return Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1]);
}

function validPoints(pts) {
  if (!Array.isArray(pts)) return false;
  for (const p of pts) if (!validPoint(p)) return false;
  return true;
}

function dist(a, b) {
  if (!validPoint(a) || !validPoint(b)) return NaN;
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

function pathLength(pts, closed = false) {
  if (!validPoints(pts)) return NaN;
  if (pts.length < 2) return 0;
  let length = 0;
  for (let i = 1; i < pts.length; i++) length += dist(pts[i - 1], pts[i]);
  if (closed) length += dist(pts[pts.length - 1], pts[0]);
  return length;
}

function signedArea(pts) {
  if (!validPoints(pts)) return NaN;
  if (pts.length < 3) return 0;
  let twiceArea = 0;
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    twiceArea += a[0] * b[1] - b[0] * a[1];
  }
  return twiceArea / 2;
}

function polyArea(pts) {
  return Math.abs(signedArea(pts));
}

function centroid(pts) {
  if (!validPoints(pts)) return NaN;
  if (!pts.length) return null;
  const area = signedArea(pts);
  let x = 0, y = 0;
  if (area === 0) {
    for (const p of pts) {
      x += p[0] / pts.length;
      y += p[1] / pts.length;
    }
    return [x, y];
  }
  for (let i = 0; i < pts.length; i++) {
    const a = pts[i], b = pts[(i + 1) % pts.length];
    const cross = a[0] * b[1] - b[0] * a[1];
    x += (a[0] + b[0]) * cross;
    y += (a[1] + b[1]) * cross;
  }
  return [x / (6 * area), y / (6 * area)];
}

function angleDeg(a, vertex, b) {
  if (!validPoint(a) || !validPoint(vertex) || !validPoint(b)) return NaN;
  const ax = a[0] - vertex[0], ay = a[1] - vertex[1];
  const bx = b[0] - vertex[0], by = b[1] - vertex[1];
  const al = Math.hypot(ax, ay), bl = Math.hypot(bx, by);
  if (al === 0 || bl === 0) return 0;
  const dot = (ax / al) * (bx / bl) + (ay / al) * (by / bl);
  return Math.acos(Math.max(-1, Math.min(1, dot))) * 180 / Math.PI;
}

function bearingDeg(a, b) {
  if (!validPoint(a) || !validPoint(b)) return NaN;
  if (a[0] === b[0] && a[1] === b[1]) return 0;
  return (Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI + 360) % 360;
}

function plainNumber(v) {
  return String(Number(v.toFixed(3)));
}

function fmtLength(v, unit) {
  if (!Number.isFinite(v)) return '';
  switch (unit) {
    case 'mm': return Math.abs(v) < 1000 ? v.toFixed(1) + ' mm' : (v / 1000).toFixed(3) + ' m';
    case 'cm': return v.toFixed(2) + ' cm';
    case 'm': return v.toFixed(3) + ' m';
    case 'in': return v.toFixed(2) + ' in';
    case 'ft': {
      let feet = Math.floor(Math.abs(v));
      let inches = Number(((Math.abs(v) - feet) * 12).toFixed(2));
      if (inches >= 12) {
        feet++;
        inches = 0;
      }
      return (v < 0 ? '-' : '') + feet + "'-" + inches.toFixed(2) + '"';
    }
    default: return plainNumber(v);
  }
}

function fmtArea(v, unit) {
  if (!Number.isFinite(v)) return '';
  switch (unit) {
    case 'mm': return v >= 1e6 ? (v / 1e6).toFixed(2) + ' m2' : v.toFixed(0) + ' mm2';
    case 'm': return v.toFixed(2) + ' m2';
    case 'cm':
    case 'in':
    case 'ft': return v.toFixed(2) + ' ' + unit + '2';
    default: return plainNumber(v);
  }
}

if (typeof module !== 'undefined') module.exports = {dist, pathLength, polyArea, signedArea, centroid, angleDeg, bearingDeg, fmtLength, fmtArea};
