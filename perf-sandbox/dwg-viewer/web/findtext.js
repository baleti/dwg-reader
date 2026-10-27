'use strict';
// Find text: search the text rows of the layout (sheet rows and viewport content), jump to the next match and select it.
let fHits = [], fIdx = -1, fQuery = '', fLay = null;
function fCollect(q) {
  const out = [], ql = q.toLowerCase(), seen = new Set();
  const add = (p, x, y, vp) => { const t = topOf(p), key = t + ':' + (vp ? vp.id : -1); if (seen.has(key)) return; seen.add(key); out.push({x, y, top: t, vp, h: (p[5] || 1) * (vp ? Math.hypot(vp.M[0], vp.M[1]) : 1)}); };
  for (const p of lay.prims) if (p[0] === 't' && visibleRow(p, null) && String(p[7]).toLowerCase().includes(ql)) add(p, p[3], p[4], null);
  for (const vp of lay.vps) {
    const m = vp.M;
    for (const p of lay.mprims) {
      if (p[0] !== 't' || !visibleRow(p, vp.fzs) || !String(p[7]).toLowerCase().includes(ql)) continue;
      const x = m[0] * p[3] + m[2] * p[4] + m[4], y = m[1] * p[3] + m[3] * p[4] + m[5];
      if (pointInPoly(x, y, vp.clip)) add(p, x, y, vp);
    }
  }
  return out;
}
function fGo(dir) {
  const q = $('findBox').value.trim(); if (!q || !lay) { fHits = []; $('stat').textContent = ''; return; }
  if (q !== fQuery || fLay !== lay) { fQuery = q; fLay = lay; fHits = fCollect(q); fIdx = -1; }
  if (!fHits.length) { $('msg').style.display = 'block'; $('msg').textContent = 'no text matches "' + q + '"'; setTimeout(() => { if ($('msg').textContent.startsWith('no text')) $('msg').style.display = 'none'; }, 1800); return; }
  fIdx = (fIdx + dir + fHits.length) % fHits.length;
  const h = fHits[fIdx], r = cv.getBoundingClientRect();
  if (h.h > 0 && view.s * h.h < 14) view.s = 14 / h.h;      // zoom in when the text would be tiny
  view.x = h.x - r.width / 2 / view.s; view.y = h.y + r.height / 2 / view.s;
  setSelection([h.top], false); interact();
  const s = $('stat'); if (s) s.title = 'match ' + (fIdx + 1) + ' of ' + fHits.length;
  $('msg').style.display = 'block'; $('msg').textContent = 'match ' + (fIdx + 1) + ' of ' + fHits.length; setTimeout(() => { if ($('msg').textContent.startsWith('match')) $('msg').style.display = 'none'; }, 1200);
}
$('findBox').addEventListener('keydown', e => { e.stopPropagation(); if (e.key === 'Enter') { e.preventDefault(); fGo(e.shiftKey ? -1 : 1); } else if (e.key === 'Escape') { e.target.blur(); } });
$('findBox').addEventListener('input', () => { fQuery = ''; });
document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && (e.key === 'f' || e.key === 'F')) { e.preventDefault(); $('findBox').focus(); $('findBox').select(); } });
