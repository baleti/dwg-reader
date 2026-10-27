'use strict';
// Measure tool: click points (snapping to polyline vertices), live length / area / bearing. Pure maths lives in measure.js.
// Points inside a paper-space viewport are converted to model units with the viewport's inverse transform (the viewport of the first point
// fixes the space); otherwise the space is the sheet itself (paper units, mm).
let measureMode = false, mPts = [], mVp = null, mDone = false, mCursor = null;
const M_UNITS = {1: 'in', 2: 'ft', 4: 'mm', 5: 'cm', 6: 'm'};

function mFromWorld(wx, wy) {
  if (!mVp) return [wx, wy];
  const m = mVp.M, det = m[0] * m[3] - m[1] * m[2], dx = wx - m[4], dy = wy - m[5];
  return [(m[3] * dx - m[2] * dy) / det, (-m[1] * dx + m[0] * dy) / det];
}
function mToWorld(p) { if (!mVp) return p; const m = mVp.M; return [m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5]]; }
function mUnit() { return mVp || !paper ? M_UNITS[meta && meta.insunits] : 'mm'; }
function mSnap(wx, wy) {
  const tol = 10 / view.s; let best = null, bd = tol;
  const scan = (rows, x, y, t, fz, sc, vp) => {      // x, y and t in the rows' own space; sc converts row distances to sheet distances
    const polys = [];
    for (const p of rows) {
      if (p[0] !== 'l' || !visibleRow(p, fz)) continue;
      const b = p.bb; if (x < b[0] - t || x > b[2] + t || y < b[1] - t || y > b[3] + t) continue;
      polys.push(p[5]);
    }
    if (!polys.length) return;
    const r = snapFind(polys, x, y, t, ['end', 'int', 'mid']);     // vertices, intersections, midpoints (snap.js)
    if (!r) return;
    const d = r.d * sc;
    if (d < bd) { bd = d; best = vp ? [vp.M[0] * r.x + vp.M[2] * r.y + vp.M[4], vp.M[1] * r.x + vp.M[3] * r.y + vp.M[5]] : [r.x, r.y]; }
  };
  scan(lay.prims, wx, wy, tol, null, 1, null);
  for (const vp of lay.vps) {
    if (!pointInPoly(wx, wy, vp.clip)) continue;
    const m = vp.M, det = m[0] * m[3] - m[1] * m[2], s = Math.hypot(m[0], m[1]), dx = wx - m[4], dy = wy - m[5];
    scan(lay.mprims, (m[3] * dx - m[2] * dy) / det, (-m[1] * dx + m[0] * dy) / det, tol / s, vp.fzs, s, vp);
  }
  return best;
}
function mPoint(e) {
  let [wx, wy] = toWorld(e.clientX, e.clientY);
  const sn = e.shiftKey ? null : mSnap(wx, wy); if (sn) { wx = sn[0]; wy = sn[1]; }
  return [wx, wy];
}
function mReport() {
  const pts = mPts.concat(mCursor && !mDone ? [mCursor] : []);
  if (!pts.length) return '';
  const u = mUnit(), L = pathLength(pts), out = ['length ' + fmtLength(L, u)];
  if (pts.length >= 2) {
    const a = pts[pts.length - 2], b = pts[pts.length - 1];
    out.push('last ' + fmtLength(dist(a, b), u), 'dx ' + fmtLength(b[0] - a[0], u) + '  dy ' + fmtLength(b[1] - a[1], u), 'bearing ' + bearingDeg(a, b).toFixed(2) + '°');
  }
  if (pts.length >= 3) out.push('area ' + fmtArea(polyArea(pts), u), 'perimeter ' + fmtLength(pathLength(pts, true), u), 'angle ' + angleDeg(pts[pts.length - 3], pts[pts.length - 2], pts[pts.length - 1]).toFixed(2) + '°');
  if (!u) out.push('(drawing units not set)');
  return out.join('\n');
}
function mUpdate() { const b = $('measOut'); if (!b) return; const t = measureMode ? (mReport() || 'click the first point') : ''; b.style.display = t ? 'block' : 'none'; b.textContent = t; draw(); }
function setMeasure(on) {
  measureMode = on; mPts = []; mVp = null; mDone = false; mCursor = null;
  $('measBtn').classList.toggle('on', on); cv.style.cursor = on ? 'crosshair' : (handMode ? 'grab' : 'crosshair'); mUpdate();
}
cv.addEventListener('mousedown', e => {
  if (!measureMode || e.button !== 0 || handMode || spaceDown) return;
  e.stopImmediatePropagation(); e.preventDefault();
  if (mDone) { mPts = []; mVp = null; mDone = false; }
  let [wx, wy] = mPoint(e);
  if (!mPts.length) { mVp = null; for (const vp of lay.vps) if (pointInPoly(wx, wy, vp.clip)) mVp = vp; }
  mPts.push(mFromWorld(wx, wy)); mUpdate();
}, true);
cv.addEventListener('dblclick', e => { if (!measureMode) return; e.stopImmediatePropagation(); if (mPts.length > 1) mPts.pop(); mDone = true; mCursor = null; mUpdate(); }, true);
cv.addEventListener('contextmenu', e => { if (measureMode && mPts.length && !mDone) { mPts.pop(); mUpdate(); } });
addEventListener('mousemove', e => { if (!measureMode || mDone || !mPts.length) return; const [wx, wy] = mPoint(e); mCursor = mFromWorld(wx, wy); mUpdate(); });
document.addEventListener('keydown', e => {
  const tag = (e.target && e.target.tagName) || ''; if (tag === 'INPUT' && e.target.type !== 'checkbox' && e.target.type !== 'range') return;
  if (e.key === 'm' || e.key === 'M') setMeasure(!measureMode);
  else if (measureMode && e.key === 'Escape') { if (mPts.length) { mPts = []; mDone = false; mCursor = null; mUpdate(); } else setMeasure(false); }
  else if (measureMode && e.key === 'Enter') { mDone = true; mCursor = null; mUpdate(); }
});
$('measBtn').onclick = () => setMeasure(!measureMode);
const _drawOverlayBase = drawOverlay;
drawOverlay = function () {
  _drawOverlayBase();
  if (!measureMode || !lay || !mPts.length) return;
  const pts = mPts.concat(mCursor && !mDone ? [mCursor] : []).map(mToWorld), k = view.s * devicePixelRatio, c = cv.getContext('2d');
  c.save(); c.setTransform(k, 0, 0, -k, -view.x * k, view.y * k);
  c.lineWidth = 1.6 / k; c.strokeStyle = '#ff7a00'; c.fillStyle = 'rgba(255,122,0,.15)'; c.setLineDash([]);
  c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (const p of pts.slice(1)) c.lineTo(p[0], p[1]);
  if (pts.length >= 3) { c.closePath(); c.fill(); } c.stroke();
  c.fillStyle = '#ff7a00'; for (const p of pts) { c.beginPath(); c.arc(p[0], p[1], 3.2 / k, 0, 6.2832); c.fill(); }
  c.restore();
};

// save the visible canvas as a PNG named after the drawing and layout
$('pngBtn').onclick = () => {
  draw(); requestAnimationFrame(() => cv.toBlob(b => {
    if (!b) return; const a = document.createElement('a'), nm = (meta.file || 'drawing').replace(/\.dwg$/i, '') + '_' + ((meta.layouts[layIdx] || {}).name || layIdx).replace(/[^\w.-]+/g, '_') + '.png';
    a.href = URL.createObjectURL(b); a.download = nm; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }, 'image/png'));
};
