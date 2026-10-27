'use strict';
// Layer Properties Manager: sortable/filterable table, multi-select (click, shift-range, ctrl-toggle, select all), bulk On / Freeze / Lock /
// isolate / VP freeze, colour override, links with the object selection.
const LSORT = {col: 'name', dir: 1};
let lOrder = [], lSel = new Set(), lAnchor = -1;
const LCOLS = [
  ['sts', 'Sts', 'w-sts'], ['name', 'Name', 'w-name'], ['on', 'On', 'w-chk'], ['frz', 'Frz', 'w-chk'], ['lock', 'Lck', 'w-chk'], ['color', 'Color', 'w-col'],
  ['lt', 'Linetype', 'w-lt'], ['lw', 'Lineweight', 'w-lw'], ['tr', 'Transp', 'w-tr'], ['plot', 'Plot', 'w-chk'], ['vp', 'VP Frz', 'w-chk'], ['desc', 'Description', 'w-desc']];
function wildRe(q) {
  q = q.trim(); if (!q) return null;
  if (/[*?]/.test(q)) return new RegExp('^' + q.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*/g, '.*').replace(/\?/g, '.') + '$', 'i');
  const lq = q.toLowerCase(); return {test: s => s.toLowerCase().includes(lq)};
}
function lwText(l) { return l.lw ? l.lw.toFixed(2) + ' mm' : 'Default'; }
function layerFiltered() {
  const re = wildRe($('lfilter').value || ''), f = $('lfsel').value, sel = f === 'sel' ? layersOfSelection() : null;
  const out = [];
  meta.layers.forEach((l, i) => {
    if (re && !re.test(l.n)) return;
    if (f === 'used' && !l.used) return; if (f === 'unused' && l.used) return;
    if (f === 'off' && lyOn[i]) return; if (f === 'frz' && !lyFrz[i]) return; if (f === 'lock' && !lyLock[i]) return;
    if (f === 'sel' && !sel.has(i)) return;
    out.push(i);
  });
  const key = i => { const l = meta.layers[i]; switch (LSORT.col) {
    case 'name': return l.n.toLowerCase(); case 'on': return lyOn[i] ? 1 : 0; case 'frz': return lyFrz[i] ? 1 : 0; case 'lock': return lyLock[i] ? 1 : 0;
    case 'color': return JSON.stringify(l.c); case 'lt': return (l.lt || '').toLowerCase(); case 'lw': return l.lw || 0; case 'tr': return l.tr || 0;
    case 'plot': return l.plot ? 1 : 0; case 'sts': return l.used ? 1 : 0; case 'vp': return curVp >= 0 && lay.vps[curVp].fzs.has(i) ? 1 : 0; case 'desc': return (l.desc || '').toLowerCase(); } return 0; };
  out.sort((a, b) => { const x = key(a), y = key(b); return (x < y ? -1 : x > y ? 1 : a - b) * LSORT.dir; });
  return out;
}
function hexOf(l, i) { if (OVR[i]) return OVR[i]; const m = css(l.c, false).match(/\d+/g).map(Number); return '#' + m.map(v => v.toString(16).padStart(2, '0')).join(''); }
function buildLayerTable() {
  if (!meta) return;
  const box = $('ltable'); const sy = box.scrollTop;
  lOrder = layerFiltered();
  const frag = document.createDocumentFragment();
  const head = document.createElement('div'); head.className = 'lrow lhead';
  for (const [c, t, w] of LCOLS) {
    const d = document.createElement('div'); d.className = 'lc ' + w + (LSORT.col === c ? ' sorted' : ''); d.textContent = t + (LSORT.col === c ? (LSORT.dir > 0 ? ' ▲' : ' ▼') : '');
    d.onclick = () => { if (LSORT.col === c) LSORT.dir = -LSORT.dir; else { LSORT.col = c; LSORT.dir = 1; } buildLayerTable(); };
    if (c === 'vp') d.title = curVp >= 0 ? 'freeze in the current viewport (click a viewport frame on the sheet)' : 'click inside a viewport on the sheet first';
    head.append(d);
  }
  frag.append(head);
  const cur = meta.layers.findIndex(l => l.n === (meta.current || '0'));
  const vpOk = lay && curVp >= 0 && lay.vps[curVp];
  for (const i of lOrder) {
    const l = meta.layers[i], r = document.createElement('div');
    r.className = 'lrow' + (lSel.has(i) ? ' sel' : '') + (!lyOn[i] || lyFrz[i] ? ' dim' : ''); r.dataset.i = i;
    const mk = (w, content) => { const d = document.createElement('div'); d.className = 'lc ' + w; if (content != null) { if (content instanceof Node) d.append(content); else d.textContent = content; } r.append(d); return d; };
    const st = mk('w-sts', i === cur ? '▶' : l.used ? '●' : '○'); st.title = i === cur ? 'current layer' : l.used ? 'layer in use' : 'layer not used'; st.className += l.used ? ' used' : '';
    mk('w-name', l.n).title = l.n;
    const chk = (v, onchange, dis) => { const c = document.createElement('input'); c.type = 'checkbox'; c.checked = v; c.disabled = !!dis; c.onclick = e => e.stopPropagation(); c.onchange = () => onchange(c.checked); return c; };
    mk('w-chk', chk(!!lyOn[i], v => applyToLayers(i, 'on', v)));
    mk('w-chk', chk(!!lyFrz[i], v => applyToLayers(i, 'frz', v)));
    mk('w-chk', chk(!!lyLock[i], v => applyToLayers(i, 'lock', v)));
    const sw = document.createElement('input'); sw.type = 'color'; sw.className = 'sw' + (OVR[i] ? ' ovr' : ''); sw.value = hexOf(l, i); sw.title = 'colour (' + JSON.stringify(l.c) + '); change = override, double click = reset';
    sw.onclick = e => e.stopPropagation(); sw.oninput = () => { OVR[i] = sw.value; invalidate(); };
    sw.ondblclick = () => { delete OVR[i]; buildLayerTable(); invalidate(); };
    mk('w-col', sw);
    mk('w-lt', l.lt || 'Continuous').title = l.lt || '';
    mk('w-lw', lwText(l)); mk('w-tr', String(l.tr || 0));
    mk('w-chk', chk(!!l.plot, v => { for (const j of (lSel.has(i) ? lSel : [i])) meta.layers[j].plot = v; buildLayerTable(); invalidate(); }));
    mk('w-chk', chk(vpOk ? lay.vps[curVp].fzs.has(i) : false, v => applyToLayers(i, 'vp', v), !vpOk));
    mk('w-desc', l.desc || '');
    r.onclick = e => {
      if (e.shiftKey && lAnchor >= 0) { const a = lOrder.indexOf(lAnchor), b = lOrder.indexOf(i); const [lo, hi] = a < b ? [a, b] : [b, a]; if (!e.ctrlKey) lSel.clear(); for (let k = lo; k <= hi; k++) lSel.add(lOrder[k]); }
      else if (e.ctrlKey || e.metaKey) { if (lSel.has(i)) lSel.delete(i); else lSel.add(i); lAnchor = i; }
      else { lSel.clear(); lSel.add(i); lAnchor = i; }
      buildLayerTable();
    };
    r.ondblclick = () => { lSel.clear(); lSel.add(i); isolateLayers(); };
    frag.append(r);
  }
  box.replaceChildren(frag); box.scrollTop = sy;
  refreshAnno();
  const f = $('lfoot'); if (f) f.textContent = meta.layers.length + ' layers, ' + lOrder.length + ' shown, ' + meta.layers.filter(l => l.used).length + ' in use, ' + lSel.size + ' selected';
}
function targets(i) { return lSel.has(i) ? [...lSel] : [i]; }
function applyToLayers(i, what, v) {
  for (const j of targets(i)) {
    if (what === 'on') lyOn[j] = v; else if (what === 'frz') lyFrz[j] = v; else if (what === 'lock') lyLock[j] = v;
    else if (what === 'vp' && lay && curVp >= 0) { const fz = lay.vps[curVp].fzs; if (v) fz.add(j); else fz.delete(j); }
  }
  rebuildAfterLayerChange();
}
function rebuildAfterLayerChange() { applyLayerState(); rebuildSelItems(); buildLayerTable(); invalidate(); }
function selIdx() { return [...lSel]; }
function isolateLayers() { const s = lSel; if (!s.size) return; meta.layers.forEach((l, i) => { if (s.has(i)) { lyOn[i] = true; lyFrz[i] = false; } else lyOn[i] = false; }); rebuildAfterLayerChange(); }
function layerSelClear() { lSel.clear(); lAnchor = -1; buildLayerTable(); }
function layerSelectAll() { for (const i of lOrder) lSel.add(i); buildLayerTable(); }
function layerTableSelectionChanged() { if ($('lfsel').value === 'sel') buildLayerTable(); }
function annoScales() {   // annotation scales that annotative text of the model carries
  const S = new Set();
  if (lay && lay.mprims) for (const p of lay.mprims) { const ac = p[0] === 't' && p[8] && p[8].ac; if (ac) for (const c of ac) S.add(c[0]); }
  return [...S].sort((a, b) => b - a);
}
function refreshAnno() {
  const sel = $('vpAnno'); if (!sel) return;
  const vp = lay && curVp >= 0 && lay.vps && lay.vps[curVp], sc = vp ? annoScales() : [];
  if (!vp || !sc.length) { sel.style.display = 'none'; return; }
  if (vp.an0 === undefined) vp.an0 = vp.an || 1;
  const fmt = a => a >= 1 ? (+a.toFixed(3)) + ':1' : '1:' + (+(1 / a).toFixed(3));
  sel.innerHTML = ''; for (const a of sc) { const o = document.createElement('option'); o.value = a; o.textContent = 'anno ' + fmt(a) + (Math.abs(a - vp.an0) <= 1e-3 * a ? ' (file)' : ''); sel.append(o); }
  const cur = sc.find(a => Math.abs(a - (vp.an || 1)) <= 1e-3 * a); sel.value = cur !== undefined ? cur : sc[0];
  sel.style.display = '';
  sel.onchange = () => { vp.an = +sel.value; invalidate(); };
}
function layerTableViewportChanged() { buildLayerTable(); }
function bulk(fn) { if (!lSel.size) return; fn(selIdx()); rebuildAfterLayerChange(); }
function initCats() {
  const box = $('cats'); box.innerHTML = '';
  for (const [k, t] of [['dim', 'Dims'], ['leader', 'Leaders'], ['block', 'Blocks'], ['curve', 'Curves'], ['wipeout', 'Masks'], ['image', 'Images'], ['solid', 'Solids']]) {
    const l = document.createElement('label'), c = document.createElement('input'); c.type = 'checkbox'; c.checked = true;
    c.onchange = () => { if (c.checked) catOff.delete(k); else catOff.add(k); rebuildSelItems(); invalidate(); };
    l.append(c, ' ' + t); box.append(l);
  }
}
// named layer states (like AutoCAD's Layer States Manager), kept per drawing in the browser's localStorage
function lsKey() { return 'dwgviewer.layerstates.' + (meta ? meta.file : ''); }
function lsLoad() { try { return JSON.parse(localStorage.getItem(lsKey()) || '{}'); } catch (e) { return {}; } }
function lsStore(o) { try { localStorage.setItem(lsKey(), JSON.stringify(o)); } catch (e) {} }
function lsRefresh(sel) {
  const o = lsLoad(), box = $('lstates'); box.innerHTML = '<option value="">layer states...</option>';
  for (const n of Object.keys((meta && meta.fstates) || {})) { const op = document.createElement('option'); op.value = '\u25c6' + n; op.textContent = '\u25c6 ' + n + ' (in file)'; box.append(op); }
  for (const n of Object.keys(o)) { const op = document.createElement('option'); op.value = n; op.textContent = n; box.append(op); }
  if (sel) box.value = sel;
}
function lsCapture() {
  const vp = {}; if (lay) lay.vps.forEach((v, i) => { vp[layIdx + ':' + v.id] = [...v.fzs].map(j => meta.layers[j].n); });
  return {on: meta.layers.filter((l, i) => lyOn[i]).map(l => l.n), frz: meta.layers.filter((l, i) => lyFrz[i]).map(l => l.n), lock: meta.layers.filter((l, i) => lyLock[i]).map(l => l.n),
          ovr: Object.fromEntries(Object.entries(OVR).map(([i, c]) => [meta.layers[i].n, c])), vp, cats: [...catOff]};
}
function lsApply(st) {
  const idx = new Map(meta.layers.map((l, i) => [l.n, i]));
  const on = new Set(st.on), fr = new Set(st.frz), lk = new Set(st.lock);
  meta.layers.forEach((l, i) => { lyOn[i] = on.has(l.n); lyFrz[i] = fr.has(l.n); lyLock[i] = lk.has(l.n); });
  for (const k in OVR) delete OVR[k];
  for (const [n, c] of Object.entries(st.ovr || {})) if (idx.has(n)) OVR[idx.get(n)] = c;
  if (lay) for (const v of lay.vps) { const names = (st.vp || {})[layIdx + ':' + v.id]; if (names) v.fzs = new Set(names.filter(n => idx.has(n)).map(n => idx.get(n))); }
  catOff.clear(); for (const c of st.cats || []) catOff.add(c);
  document.querySelectorAll('#cats input').forEach((c, i) => { c.checked = !catOff.has(['dim', 'leader', 'block', 'curve', 'wipeout', 'image', 'solid'][i]); });
  rebuildAfterLayerChange();
}
function initLayerStates() {
  lsRefresh();
  $('lsSave').onclick = () => { const n = (prompt('Name of the layer state:') || '').trim(); if (!n) return; const o = lsLoad(); o[n] = lsCapture(); lsStore(o); lsRefresh(n); };
  $('lsRestore').onclick = () => { const n = $('lstates').value; if (!n) return; 
    if (n[0] === '\u25c6') {   // a layer state saved in the drawing: layers it lists follow its on/off, all others stay as they are now
      const fs = meta.fstates[n.slice(1)]; if (!fs) return;
      const st = lsCapture(), off = new Set(fs.off), on = new Set(fs.on);
      st.on = meta.layers.filter((l, i) => off.has(l.n) ? false : on.has(l.n) ? true : lyOn[i]).map(l => l.n); return lsApply(st);
    }
    const st = lsLoad()[n]; if (st) lsApply(st); };
  $('lsDel').onclick = () => { const n = $('lstates').value; if (!n || n[0] === '\u25c6') return; const o = lsLoad(); delete o[n]; lsStore(o); lsRefresh(); };
}
function initLayerPanel() {
  initCats();
  $('lfilter').oninput = buildLayerTable; $('lfsel').onchange = buildLayerTable;
  const B = (id, fn) => { $(id).onclick = fn; };
  B('lbCsv', () => {
    const order = lSel.size ? lOrder.filter(i => lSel.has(i)) : lOrder;
    const csv = layersToCsv(meta.layers, order, {on: lyOn, frz: lyFrz, lock: lyLock, ovr: OVR});
    const foot = $('lfoot');
    foot.textContent = foot.textContent.replace(/ \| CSV copied \(\d+ layers\)$/, '') + ' | CSV copied (' + order.length + ' layers)';
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        Promise.resolve(navigator.clipboard.writeText(csv)).catch(() => {});
      }
    } catch (e) {}
  });
  B('lbOn', () => bulk(ix => { const to = !ix.every(i => lyOn[i]); ix.forEach(i => lyOn[i] = to); }));
  B('lbFrz', () => bulk(ix => { const to = !ix.every(i => lyFrz[i]); ix.forEach(i => lyFrz[i] = to); }));
  B('lbLock', () => bulk(ix => { const to = !ix.every(i => lyLock[i]); ix.forEach(i => lyLock[i] = to); }));
  B('lbIso', () => { if (lSel.size) isolateLayers(); });
  B('lbOff', () => bulk(ix => ix.forEach(i => lyOn[i] = false)));
  B('lbAllOn', () => { meta.layers.forEach((l, i) => { lyOn[i] = true; lyFrz[i] = false; }); rebuildAfterLayerChange(); });
  B('lbVp', () => { if (!(lay && curVp >= 0 && lSel.size)) return; const fz = lay.vps[curVp].fzs, ix = selIdx(), to = !ix.every(i => fz.has(i)); ix.forEach(i => to ? fz.add(i) : fz.delete(i)); rebuildAfterLayerChange(); });
  B('lbSelObj', () => { if (lSel.size) selectOnLayers(lSel); });
  B('lbOfSel', () => { const s = layersOfSelection(); lSel = new Set(s); lAnchor = [...s][0] ?? -1; buildLayerTable(); });
  B('lbInvert', () => { const n = new Set(); meta.layers.forEach((l, i) => { if (!lSel.has(i)) n.add(i); }); lSel = n; buildLayerTable(); });
  B('lbReset', () => { lyOn = meta.layers.map(l => !l.off); lyFrz = meta.layers.map(l => !!l.frz); lyLock = meta.layers.map(l => !!l.lock); for (const k in OVR) delete OVR[k]; if (lay) lay.vps.forEach(v => v.fzs = new Set(v.frozen)); rebuildAfterLayerChange(); });
  window.lsReady = initLayerStates;
  B('lpToggle', () => { const p = $('layerpanel'); p.classList.toggle('collapsed'); setTimeout(() => { resize(); }, 30); });
  $('handBtn').onclick = () => { handMode = !handMode; $('handBtn').classList.toggle('on', handMode); cv.style.cursor = handMode ? 'grab' : 'crosshair'; };
}

initLayerPanel();
