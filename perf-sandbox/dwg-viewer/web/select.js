'use strict';
// Selection: click / shift-click, window (left to right, solid blue) and crossing (right to left, dashed green) boxes, Ctrl+A, Esc,
// highlight with halo + dashed outline + grips, works through viewports. The selection unit is the top-level object (row top handle).
const S = new Set();            // selected top-level handles
let selItems = [];              // [{row, F, fz}] rows to highlight (rebuilt when the selection or the visible layers change)
let selBox = null;              // {x0, y0, x1, y1, crossing} in css px of the canvas while dragging
let curVp = -1;                 // viewport last clicked in a paper layout (target of VP freeze)
let handMode = false, spaceDown = false, panDrag = null, selDrag = null, cursorW = [0, 0];
const topOf = p => p[p.length - 1];
const HL = '#2f9bff';

function visibleRow(p, fz) { return on(p[1]) && !parentHidden(p, fz) && !lyLock[p[1]] && !(fz && p[1] >= 0 && fz.has(p[1])) && !rowOff(p); }
function toWorld(cx, cy) { const r = cv.getBoundingClientRect(); return [view.x + (cx - r.left) / view.s, view.y - (cy - r.top) / view.s]; }
function applyM(m, x, y) { return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]]; }
function pointInPoly(x, y, c) { let ins = false; for (let i = 0, j = c.length - 2; i < c.length; j = i, i += 2) { const xi = c[i], yi = c[i + 1], xj = c[j], yj = c[j + 1]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) ins = !ins; } return ins; }
function bbIn(b, R) { return b[0] >= R[0] && b[2] <= R[2] && b[1] >= R[1] && b[3] <= R[3]; }
function bbHit(b, R) { return !(b[2] < R[0] || b[0] > R[2] || b[3] < R[1] || b[1] > R[3]); }
function xformBB(m, b) {
  const c = [applyM(m, b[0], b[1]), applyM(m, b[2], b[1]), applyM(m, b[2], b[3]), applyM(m, b[0], b[3])];
  return [Math.min(c[0][0], c[1][0], c[2][0], c[3][0]), Math.min(c[0][1], c[1][1], c[2][1], c[3][1]), Math.max(c[0][0], c[1][0], c[2][0], c[3][0]), Math.max(c[0][1], c[1][1], c[2][1], c[3][1])];
}
function segHitsRect(ax, ay, bx, by, R) {   // Liang-Barsky
  let t0 = 0, t1 = 1; const dx = bx - ax, dy = by - ay;
  for (const [p, q] of [[-dx, ax - R[0]], [dx, R[2] - ax], [-dy, ay - R[1]], [dy, R[3] - ay]]) {
    if (p === 0) { if (q < 0) return false; } else { const t = q / p; if (p < 0) { if (t > t1) return false; if (t > t0) t0 = t; } else { if (t < t0) return false; if (t < t1) t1 = t; } }
  }
  return true;
}
function rowTouches(p, m, R) {
  if (p[0] === 'l') {
    const f = p[5];
    if (!m && f.length < 4) return false;
    let px = f[0], py = f[1]; if (m) [px, py] = applyM(m, px, py);
    for (let i = 2; i < f.length; i += 2) {
      let x = f[i], y = f[i + 1]; if (m) [x, y] = applyM(m, x, y);
      if (segHitsRect(px, py, x, y, R)) return true;
      px = x; py = y;
    }
    return false;
  }
  return true;   // text, hatch, points: bounding box (already tested)
}

// all objects that are inside (window) or touched by (crossing) the rectangle R given in the view (paper or model) space
function collectTops(R, crossing) {
  const out = new Set();
  const scanRows = (rows, m, fz, clipBB) => {
    const info = new Map();
    for (const p of rows) {
      if (p[0] === 't' ? !$('oText').checked : p[0] === 'h' ? !$('oHatch').checked : !$('oLines').checked) { if (p[0] !== 'p') continue; }
      if (!visibleRow(p, fz)) continue;
      let b = m ? xformBB(m, p.bb) : p.bb;
      if (clipBB) { if (!bbHit(b, clipBB)) continue; b = [Math.max(b[0], clipBB[0]), Math.max(b[1], clipBB[1]), Math.min(b[2], clipBB[2]), Math.min(b[3], clipBB[3])]; }
      const t = topOf(p); let o = info.get(t);
      if (!o) { o = {u: [1e300, 1e300, -1e300, -1e300], touch: false}; info.set(t, o); }
      const u = o.u; if (b[0] < u[0]) u[0] = b[0]; if (b[1] < u[1]) u[1] = b[1]; if (b[2] > u[2]) u[2] = b[2]; if (b[3] > u[3]) u[3] = b[3];
      if (crossing && !o.touch && bbHit(b, R) && rowTouches(p, m, R)) o.touch = true;
    }
    for (const [t, o] of info) if (crossing ? o.touch : bbIn(o.u, R)) out.add(t);
  };
  scanRows(lay.prims, null, null, null);
  for (const vp of lay.vps) {
    const cb = vp.clip; const cbb = [Math.min(...cb.filter((_, i) => i % 2 === 0)), Math.min(...cb.filter((_, i) => i % 2 === 1)), Math.max(...cb.filter((_, i) => i % 2 === 0)), Math.max(...cb.filter((_, i) => i % 2 === 1))];
    if (!bbHit(cbb, R)) continue;
    scanRows(lay.mprims, vp.M, vp.fzs, cbb);
  }
  return out;
}

function segDist(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
  let t = l2 ? ((px - ax) * dx + (py - ay) * dy) / l2 : 0; t = Math.max(0, Math.min(1, t));
  return Math.hypot(ax + t * dx - px, ay + t * dy - py);
}
function pickRow(wx, wy, tol) {
  let best = null, bd = tol;
  const test = (rows, x, y, t, fz, sc) => {
    for (const p of rows) {
      if (!visibleRow(p, fz)) continue;
      const b = p.bb; if (x < b[0] - t || x > b[2] + t || y < b[1] - t || y > b[3] + t) continue;
      let d = 1e300;
      if (p[0] === 'l') { const f = p[5]; for (let i = 0; i + 3 < f.length; i += 2) { const q = segDist(x, y, f[i], f[i + 1], f[i + 2], f[i + 3]); if (q < d) d = q; } }
      else if (p[0] === 't') d = Math.hypot(x - p[3], y - p[4]) < Math.max(p[5] * 3, t) ? 0 : 1e300;
      else if (p[0] === 'h') { if (p[4].wipe) continue; if (x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3]) d = t * 0.9; }
      else if (p[0] === 'p') d = Math.hypot(x - p[3], y - p[4]);
      d *= sc;
      if (d < bd) { bd = d; best = p; }
    }
  };
  test(lay.prims, wx, wy, tol, null, 1);
  for (const vp of lay.vps) {
    if (!pointInPoly(wx, wy, vp.clip)) continue;
    const m = vp.M, det = m[0] * m[3] - m[1] * m[2], s = Math.hypot(m[0], m[1]);
    const dx = wx - m[4], dy = wy - m[5];
    test(lay.mprims, (m[3] * dx - m[2] * dy) / det, (-m[1] * dx + m[0] * dy) / det, tol / s, vp.fzs, s);
  }
  return best;
}

// ---- selection state ----
function setSelection(tops, add) {
  if (!add) S.clear();
  for (const t of tops) S.add(t);
  rebuildSelItems(); selectionChanged();
}
function toggleSelection(tops) { for (const t of tops) { if (S.has(t)) S.delete(t); else S.add(t); } rebuildSelItems(); selectionChanged(); }
function clearSelection(silent) { S.clear(); selItems = []; if (!silent) selectionChanged(); else updateSelStatus(); }
function rebuildSelItems() {
  selItems = [];
  if (!lay || !S.size) return;
  for (const p of lay.prims) if (S.has(topOf(p)) && visibleRow(p, null)) selItems.push({row: p, F: null});
  for (const vp of lay.vps) { const F = vpFrame(vp); for (const p of lay.mprims) if (S.has(topOf(p)) && visibleRow(p, vp.fzs)) selItems.push({row: p, F, vp}); }
}
function selectionChanged() { updateSelStatus(); if (typeof layerTableSelectionChanged === 'function') layerTableSelectionChanged(); showInfo(); draw(); }
function updateSelStatus() { const e = $('sel'); if (e) e.textContent = S.size ? S.size + ' selected' : 'nothing selected'; }
function selectAll() { setSelection(collectTops([-1e300, -1e300, 1e300, 1e300], true), false); }
function layersOfSelection() { const r = new Set(); for (const it of selItems) if (it.row[1] >= 0) r.add(it.row[1]); return r; }
function selectOnLayers(set) {
  const tops = new Set();
  for (const p of lay.prims) if (set.has(p[1]) && visibleRow(p, null)) tops.add(topOf(p));
  for (const vp of lay.vps) for (const p of lay.mprims) if (set.has(p[1]) && visibleRow(p, vp.fzs)) tops.add(topOf(p));
  setSelection(tops, false);
}
// total length of the selected polylines and area of closed polylines / hatches (row units: model units inside viewports, sheet units elsewhere)
function selMeasures() {
  if (typeof pathLength !== 'function') return '';
  const acc = {sheet: {len: 0, area: 0, nl: 0, na: 0}, model: {len: 0, area: 0, nl: 0, na: 0}};
  const pts = f => { const o = []; for (let i = 0; i + 1 < f.length; i += 2) o.push([f[i], f[i + 1]]); return o; };
  for (const {row: p, F} of selItems) {
    const a = F ? acc.model : acc.sheet;     // viewport rows are in model units, the others in sheet units (mm on a layout)
    if (p[0] === 'l') {
      const q = pts(p[5]); a.len += pathLength(q); a.nl++;
      if (q.length > 3 && Math.hypot(q[0][0] - q[q.length - 1][0], q[0][1] - q[q.length - 1][1]) < 1e-6 * (1 + Math.abs(q[0][0]))) { a.area += polyArea(q.slice(0, -1)); a.na++; }
    } else if (p[0] === 'h' && !p[4].wipe && p[3].length) {
      const ar = p[3].map(l => polyArea(pts(l))).sort((x, y) => y - x); a.area += ar[0] - ar.slice(1).reduce((x, y) => x + y, 0); a.na++;
    }
  }
  const mu = meta && {1: 'in', 2: 'ft', 4: 'mm', 5: 'cm', 6: 'm'}[meta.insunits], su = paper || lay.vps.length ? 'mm' : mu;
  const two = acc.sheet.nl + acc.sheet.na && acc.model.nl + acc.model.na;
  let out = '';
  for (const [k, a, u] of [['sheet', acc.sheet, su], ['model', acc.model, mu]]) {
    const tag = two ? ' (' + k + ')' : '';
    if (a.nl) out += '\nlength' + tag + ' ' + fmtLength(a.len, u);
    if (a.na) out += '\narea' + tag + ' ' + fmtArea(a.area, u) + ' (closed polylines + hatches, islands subtracted)';
  }
  return out;
}
async function showInfo() {
  const box = $('info');
  if (!S.size) { box.style.display = 'none'; return; }
  const names = {l: 'polyline', h: 'hatch', t: 'text', p: 'point'};
  const byLayer = new Map(), kinds = new Map();
  for (const it of selItems) { const n = it.row[1] >= 0 ? meta.layers[it.row[1]].n : '-'; byLayer.set(n, (byLayer.get(n) || 0) + 1); kinds.set(names[it.row[0]], (kinds.get(names[it.row[0]]) || 0) + 1); }
  let txt = S.size + ' object' + (S.size > 1 ? 's' : '') + ' selected\nlayers: ' + [...byLayer].sort((a, b) => b[1] - a[1]).slice(0, 6).map(x => x[0] + ' (' + x[1] + ')').join(', ');
  txt += selMeasures();
  box.style.display = 'block'; box.textContent = txt;
  if (S.size === 1) {
    const h = [...S][0];
    try { const d = await (await fetch('/api/entity/' + h)).json(); if (d && d.kind && S.size === 1 && S.has(h)) box.textContent = d.kind + '  handle ' + h.toString(16).toUpperCase() + '\n' + txt + '\n' + (d.summary || ''); } catch (_) {}
  }
}

// ---- overlay drawing (on the main canvas, after the scene) ----
function drawOverlay() {
  if (!lay) return;
  const dpr = devicePixelRatio, k = view.s * dpr, c = cv.getContext('2d');
  if (curVp >= 0 && lay.vps[curVp] && lay.vps.length > 1) {
    c.save(); c.setTransform(k, 0, 0, -k, -view.x * k, view.y * k); c.strokeStyle = 'rgba(47,155,255,.5)'; c.lineWidth = 2 / k; c.setLineDash([8 / k, 5 / k]);
    const cl = lay.vps[curVp].clip; c.beginPath(); c.moveTo(cl[0], cl[1]); for (let i = 2; i < cl.length; i += 2) c.lineTo(cl[i], cl[i + 1]); c.closePath(); c.stroke(); c.restore();
  }
  if (selItems.length) {
    const dash = performance.now() / 60 % 20;
    let grips = 0; const gp = [];
    for (const {row: p, F, vp} of selItems) {
      c.save();
      c.setTransform(k, 0, 0, -k, -view.x * k, view.y * k);
      if (vp) { const cl = vp.clip; c.beginPath(); c.moveTo(cl[0], cl[1]); for (let i = 2; i < cl.length; i += 2) c.lineTo(cl[i], cl[i + 1]); c.closePath(); c.clip(); c.transform(...F.m); }
      const kk = k * (F ? F.s : 1), px = 1 / kk;
      c.lineJoin = 'round'; c.lineCap = 'round';
      if (p[0] === 'l') {
        const f = p[5]; c.beginPath(); c.moveTo(f[0], f[1]); for (let i = 2; i < f.length; i += 2) c.lineTo(f[i], f[i + 1]);
        c.strokeStyle = 'rgba(47,155,255,.38)'; c.lineWidth = 7 * px; c.stroke();
        c.strokeStyle = '#d6ecff'; c.lineWidth = 1.6 * px; c.setLineDash([6 * px, 4 * px]); c.stroke();
        if (grips < 400) { grips++; const n = f.length / 2; for (const i of [0, Math.floor((n - 1) / 2), n - 1]) gp.push(F ? applyM(F.m, f[2 * i], f[2 * i + 1]) : [f[2 * i], f[2 * i + 1]]); }
      } else if (p[0] === 'h') {
        c.beginPath(); for (const l of p[3]) { c.moveTo(l[0], l[1]); for (let i = 2; i < l.length; i += 2) c.lineTo(l[i], l[i + 1]); c.closePath(); }
        c.fillStyle = 'rgba(47,155,255,.22)'; c.fill('evenodd');
        c.strokeStyle = '#d6ecff'; c.lineWidth = 1.5 * px; c.setLineDash([6 * px, 4 * px]); c.stroke();
      } else if (p[0] === 't') {
        const o = p[8], h = p[5], w = o.ew || Math.min(String(p[7]).length, 200) * 0.5 * h * (o.wf || 1), hj = o.hj || 0;
        c.translate(p[3], p[4]); c.rotate(p[6]);
        const x0 = hj === 1 ? -w / 2 : hj === 2 ? -w : 0, vj = o.vj || 0, y0 = vj === 3 ? -h * 1.2 : vj === 2 ? -h * 0.6 : -h * 0.2;
        c.strokeStyle = HL; c.lineWidth = 1.8 * px; c.setLineDash([5 * px, 3 * px]); c.strokeRect(x0 - h * 0.1, y0, w + h * 0.2, h * 1.4);
      } else if (p[0] === 'p') {
        c.fillStyle = HL; c.fillRect(p[3] - 4 * px, p[4] - 4 * px, 8 * px, 8 * px);
      }
      c.restore();
    }
    c.save(); c.setTransform(1, 0, 0, 1, 0, 0);
    for (const [x, y] of gp) {
      const sx = (x - view.x) * k, sy = (view.y - y) * k;
      if (sx < -10 || sy < -10 || sx > cv.width + 10 || sy > cv.height + 10) continue;
      c.fillStyle = '#1b6fd8'; c.strokeStyle = '#fff'; c.lineWidth = 1; c.fillRect(sx - 3.5 * dpr, sy - 3.5 * dpr, 7 * dpr, 7 * dpr); c.strokeRect(sx - 3.5 * dpr, sy - 3.5 * dpr, 7 * dpr, 7 * dpr);
    }
    c.restore();
  }
  if (selBox) {
    const b = selBox, x = Math.min(b.x0, b.x1) * dpr, y = Math.min(b.y0, b.y1) * dpr, w = Math.abs(b.x1 - b.x0) * dpr, h = Math.abs(b.y1 - b.y0) * dpr;
    c.save(); c.setTransform(1, 0, 0, 1, 0, 0);
    c.fillStyle = b.crossing ? 'rgba(40,190,80,.16)' : 'rgba(47,155,255,.18)'; c.fillRect(x, y, w, h);
    c.strokeStyle = b.crossing ? '#2dbd55' : '#2f9bff'; c.lineWidth = 1.4 * dpr; c.setLineDash(b.crossing ? [7 * dpr, 4 * dpr] : []); c.strokeRect(x, y, w, h);
    c.restore();
  }
}

// ---- mouse / keyboard ----
function evPos(e) { const r = cv.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; }
cv.addEventListener('contextmenu', e => e.preventDefault());
cv.addEventListener('mousedown', e => {
  cv.focus && cv.focus();
  const [mx, my] = evPos(e);
  if (e.button === 1 || e.button === 2 || handMode || spaceDown) { panDrag = [e.clientX, e.clientY]; e.preventDefault(); return; }
  if (e.button === 0) selDrag = {x0: mx, y0: my, x1: mx, y1: my, shift: e.shiftKey, moved: false};
});
addEventListener('mousemove', e => {
  const [mx, my] = evPos(e); cursorW = toWorld(e.clientX, e.clientY);
  const cs = $('coord'); if (cs && lay) cs.textContent = cursorW[0].toFixed(2) + ', ' + cursorW[1].toFixed(2);
  if (panDrag) { view.x -= (e.clientX - panDrag[0]) / view.s; view.y += (e.clientY - panDrag[1]) / view.s; panDrag = [e.clientX, e.clientY]; interact(); return; }
  if (selDrag) {
    selDrag.x1 = mx; selDrag.y1 = my;
    if (Math.hypot(mx - selDrag.x0, my - selDrag.y0) > 4) selDrag.moved = true;
    if (selDrag.moved) { selBox = {x0: selDrag.x0, y0: selDrag.y0, x1: mx, y1: my, crossing: mx < selDrag.x0}; draw(); }
  }
});
addEventListener('mouseup', e => {
  if (panDrag) { panDrag = null; return; }
  if (!selDrag) return;
  const d = selDrag; selDrag = null; selBox = null;
  if (!lay) return;
  if (d.moved) {
    const [ax, ay] = toWorld(d.x0 + cv.getBoundingClientRect().left, d.y0 + cv.getBoundingClientRect().top);
    const [bx, by] = toWorld(d.x1 + cv.getBoundingClientRect().left, d.y1 + cv.getBoundingClientRect().top);
    const R = [Math.min(ax, bx), Math.min(ay, by), Math.max(ax, bx), Math.max(ay, by)];
    const tops = collectTops(R, d.x1 < d.x0);
    if (d.shift) toggleSelection(tops); else setSelection(tops, false);
    return;
  }
  const [wx, wy] = toWorld(d.x0 + cv.getBoundingClientRect().left, d.y0 + cv.getBoundingClientRect().top);
  const row = pickRow(wx, wy, 6 / view.s);
  if (row) { const t = topOf(row); if (d.shift) toggleSelection([t]); else setSelection([t], false); }
  else {
    // click on empty space: choose the viewport (for VP freeze), clear the selection unless shift is held
    let vi = -1; lay.vps.forEach((v, i) => { if (pointInPoly(wx, wy, v.clip)) vi = i; });
    if (vi !== curVp) { curVp = vi; if (typeof layerTableViewportChanged === 'function') layerTableViewportChanged(); }
    if (!d.shift) clearSelection(false); else draw();
  }
});
document.addEventListener('keydown', e => {
  const tag = (e.target && e.target.tagName) || '';
  if (tag === 'INPUT' && e.target.type !== 'checkbox' && e.target.type !== 'range') return;
  if (e.key === 'Escape') { clearSelection(false); if (typeof layerSelClear === 'function') layerSelClear(); }
  else if ((e.ctrlKey || e.metaKey) && (e.key === 'a' || e.key === 'A')) {
    e.preventDefault();
    if (document.activeElement && document.activeElement.closest && document.activeElement.closest('#layerpanel') && typeof layerSelectAll === 'function') layerSelectAll(); else selectAll();
  } else if (e.key === ' ' && !spaceDown) { spaceDown = true; cv.style.cursor = 'grab'; e.preventDefault(); }
  else if (e.key === 'h' || e.key === 'H') { handMode = !handMode; cv.style.cursor = handMode ? 'grab' : 'crosshair'; const b = $('handBtn'); if (b) b.classList.toggle('on', handMode); }
  else if (e.key === 'f' || e.key === 'F') fit();
  else if (e.key === '?' || e.key === 'F1') { const h = $('help'); h.style.display = h.style.display === 'block' ? 'none' : 'block'; e.preventDefault(); }
});
document.addEventListener('keyup', e => { if (e.key === ' ') { spaceDown = false; cv.style.cursor = handMode ? 'grab' : 'crosshair'; } });
