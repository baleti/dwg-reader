'use strict';
const $ = id => document.getElementById(id);
const cv = $('cv'); let ctx = cv.getContext('2d');
let vpFz0 = {};
let meta = null, lay = null, layIdx = 0, vis = [], lyOn = [], lyFrz = [], lyLock = [], vpFz = {}, view = {x: 0, y: 0, s: 1}, paper = false, raf = 0, dark = false, fontsReady = false;

// ---------------------------------------------------------------- colours
const ACI = (() => {
  const p = {0: [0,0,0], 1: [255,0,0], 2: [255,255,0], 3: [0,255,0], 4: [0,255,255], 5: [0,0,255], 6: [255,0,255], 7: [255,255,255], 8: [65,65,65], 9: [128,128,128]};
  const vals = [[1,1],[.5,1],[1,.8],[.5,.8],[1,.6],[.5,.6],[1,.5],[.5,.5],[1,.3],[.5,.3]];
  for (let i = 10; i < 250; i++) {
    const h = Math.floor((i - 10) / 10) * 15 / 360, [s, v] = vals[(i - 10) % 10];
    const f = n => { const k = (n + h * 6) % 6; return v - v * s * Math.max(0, Math.min(k, 4 - k, 1)); };
    p[i] = [Math.round(f(5) * 255), Math.round(f(3) * 255), Math.round(f(1) * 255)];
  }
  [51, 91, 132, 173, 214, 255].forEach((g, k) => p[250 + k] = [g, g, g]);
  return p;
})();
const colCache = new Map(); let MONO = false;
let CTB = null; const OVR = {};   // layer index -> css colour override (control panel)
function rc(p, bgDark) { return OVR[p[1]] || css(p[2], bgDark); }
 const PLOTMODE = !!new URLSearchParams(location.search).get('plot');
function css(c, bgDark) {
  if (CTB && !Array.isArray(c)) { const e = CTB[c]; if (e && e[0]) { return 'rgb(' + e[0].join() + ')'; } }
  else if (CTB && Array.isArray(c) && CTB.mono) return '#000';
  const key = Array.isArray(c) ? c.join() : (c === 7 ? (bgDark ? 'w' : 'k') : c);
  let r = colCache.get(key);
  if (r) return r;
  let v = Array.isArray(c) ? c : (ACI[c] || [0, 0, 0]);
  if (!Array.isArray(c) && c === 7) v = bgDark ? [255, 255, 255] : [0, 0, 0];
  r = 'rgb(' + v[0] + ',' + v[1] + ',' + v[2] + ')'; colCache.set(key, r); return r;
}

// ---------------------------------------------------------------- text
const FONT = 'LibSans, Liberation Sans, Arial, Noto Sans CJK SC, sans-serif';
const CAP = 0.716;       // cap height / em of the fallback font
function fontCss(px, bold, ital) { return (ital ? 'italic ' : '') + (bold ? 'bold ' : '') + px.toFixed(2) + 'px ' + FONT; }
function fontFlags(name) {
  const n = String(name || '').toLowerCase().replace(/\.(ttf|ttc|otf|shx)$/, '');
  const bold = /(^|[^a-z])bold|bd$|bold$|^(arialbd|arialbi|calibrib|calibriz|verdanab|verdanaz|tahomabd|timesbd|timesbi|trebucbd|trebucbi|gothicb|gothicbi)$|black$/.test(n) || /bi$|z$/.test(n) && n.length > 4;
  const ital = /italic|(^|[^a-z])ital|bi$|^(ariali|arialbi|calibrii|calibriz|timesi|timesbi|trebucit|trebucbi|verdanai|verdanaz|gothici|gothicbi)$/.test(n);
  return [bold ? 1 : 0, ital ? 1 : 0];
}
// Width factors of the fallback font (Liberation Sans) versus the real fonts, measured as AutoCAD's ext_w / our natural width on 6635 MTEXT of the corpus
const FONTK = {romans: 1.10, romand: 1.10, romanc: 1.10, romant: 1.10, calibri: 0.936, calibrib: 0.934, calibril: 0.93, tahoma: 0.908, tahomabd: 0.92, verdana: 0.969, txt: 0.967, gothic: 0.99};
function isShx(name) { return /\.shx$/i.test(String(name || '')) || /^(txt|simplex|romans|romand|romanc|romant|isocp|isocpeur|monotxt|gothice|italic|italicc|italict|scriptc|scripts|iso3098|gbenor|gbcbig|complex|greekc|greeks)$/i.test(String(name || '')); }
function shxK(name) { const n = String(name || '').toLowerCase().replace(/\.(shx|ttf|ttc|otf)$/, ''); return FONTK[n] || 1.0; }
function plainText(s) {
  return String(s).replace(/%%[cC]/g, 'Ø').replace(/%%[dD]/g, '°').replace(/%%[pP]/g, '±').replace(/%%[uUoO]/g, '').replace(/%%(\d{1,3})/g, (m, n) => String.fromCharCode(+n));
}
// MTEXT -> {lines:[[run...]]} ; run = {t, h (rel height), b, i, u, o, col, stack:[a,b]}
function parseMtext(src) {
  const lines = [[]]; let curAl = 'l', curEx = false; lines[0].al = 'l';
  let st = {h: 1, b: 0, i: 0, u: 0, o: 0, col: null, w: 1};
  const stack = [];
  let buf = '';
  const flush = () => { if (buf) { lines[lines.length - 1].push(Object.assign({t: plainText(buf)}, st)); buf = ''; } };
  const s = String(src);
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (ch === '{') { flush(); stack.push(Object.assign({}, st)); }
    else if (ch === '}') { flush(); if (stack.length) st = stack.pop(); }
    else if (ch === '\\') {
      const n = s[++i];
      if (n === 'P' || n === 'X') { flush(); lines.push([]); lines[lines.length - 1].al = curAl; lines[lines.length - 1].ex = curEx; }
      else if (n === '~') buf += ' ';
      else if (n === '\\' || n === '{' || n === '}') buf += n;
      else if (n === 'L') { flush(); st.u = 1; } else if (n === 'l') { flush(); st.u = 0; }
      else if (n === 'O') { flush(); st.o = 1; } else if (n === 'o') { flush(); st.o = 0; }
      else if (n === 'K' || n === 'k') { /* strike */ }
      else if (n === 'U' && s[i + 1] === '+') { buf += String.fromCharCode(parseInt(s.substr(i + 2, 4), 16)); i += 5; }
      else if (n === 'S') {
        const e = s.indexOf(';', i); if (e < 0) continue;
        const body = s.slice(i + 1, e), m = body.match(/^(.*?)([\/#^])(.*)$/);
        flush();
        lines[lines.length - 1].push(Object.assign({t: '', stack: m ? [plainText(m[1]), plainText(m[3])] : [plainText(body), ''], sl: m ? m[2] : '/'}, st));
        i = e;
      } else if ('fFHhCcWwQqTtAap'.includes(n)) {
        const e = s.indexOf(';', i); if (e < 0) continue;
        const body = s.slice(i + 1, e); flush();
        if (n === 'p') { const m = body.match(/q([lcrjd])/); if (m) { curAl = m[1]; curEx = true; lines[lines.length - 1].al = curAl; lines[lines.length - 1].ex = true; } }
        else if (n === 'f' || n === 'F') { const parts = body.split('|'); st.font = parts[0]; st.b = parts.some(x => x === 'b1') ? 1 : st.b; st.i = parts.some(x => x === 'i1') ? 1 : st.i; }
        else if (n === 'H' || n === 'h') { st.h = body.endsWith('x') ? parseFloat(body) : parseFloat(body) / (st.baseH || 1); st.hAbs = body.endsWith('x') ? 0 : parseFloat(body); }
        else if (n === 'C') st.col = +body; else if (n === 'c') { const v = +body; st.col = [v & 255, (v >> 8) & 255, (v >> 16) & 255]; }
        else if (n === 'W' || n === 'w') st.w = parseFloat(body);
        i = e;
      } else buf += n || '';
    } else buf += ch;
  }
  flush();
  return lines;
}
function layoutText(p) {
  // p = row t: [t, ly, col, x, y, h, rot, text, opts, handle]; cache on the row
  if (p._lt) return p._lt;
  const o = p[8], h = p[5];
  let lines;
  const [fb, fi] = fontFlags(o.font);
  if (o.mt) { lines = parseMtext(p[7]); for (const ln of lines) for (const r of ln) { if (r.b === 0 && fb) r.b = 1; if (r.i === 0 && fi) r.i = 1; } }
  else lines = [[{t: plainText(p[7]), h: 1, b: fb, i: fi, u: 0, o: 0, col: null, w: 1}]];
  p._lt = lines; return lines;
}
const measCtx = document.createElement('canvas').getContext('2d');
function runWidth(r, px) {
  measCtx.font = fontCss(px * r.h, r.b, r.i);
  if (r.stack) return Math.max(measCtx.measureText(r.stack[0]).width, measCtx.measureText(r.stack[1]).width) * 0.7;
  return measCtx.measureText(r.t).width * r.w;
}
function drawText(p, k, bgDark, F) {
  let o = p[8];
  let X0 = p[3], Y0 = p[4], H0 = p[5], R0 = p[6];
  let src = p;
  if (o.ac && F) {   // annotative text: the layout stored for this viewport's annotation scale (ac = [scale, x, y, rot, h, w, ew, eh, hj, vj])
    const as = F.an || 1, a = o.ac.find(c => Math.abs(c[0] - as) <= 1e-3 * as);   // F.an: the viewport's annotation scale (default 1:1)
    if (a) { o = Object.assign({}, o, {w: a[5], ew: a[6], eh: a[7], hj: a[8], vj: a[9]}); delete o.ac; src = [p[0], p[1], p[2], a[1], a[2], a[4], a[3]]; }
  }
  if (F) { const m = F.m; X0 = m[0] * src[3] + m[2] * src[4] + m[4]; Y0 = m[1] * src[3] + m[3] * src[4] + m[5]; H0 = src[5] * F.s; R0 = src[6] + F.rot; }
  const h = H0 * TXK;
  const SHXB = isShx(o.font);   // SHX fonts are stroke fonts: thicken the fallback glyphs a little
  const SS = F ? F.s : 1, oW = (o.w || 0) * SS, oEW = (o.ew || 0) * SS, oEH = (o.eh || 0) * SS, oFW = (o.fw || 0) * SS;   // widths in o are in the row's own units: bring them to paper units like h
  const px = h / CAP;                // font size in drawing units
  const hpx = h * k;
  if (hpx < 2.2) {                   // too small for glyphs: a faint bar of about the right length
    if (hpx < 0.6) return;
    const n = Math.min(String(p[7]).replace(/\\[A-Za-z][^;]*;|[{}]/g, '').length, 200), wbar = n * 0.5 * h * (o.wf || 1);
    const hj = o.hj || 0, x0 = hj === 0 ? 0 : hj === 1 ? -wbar / 2 : -wbar;
    ctx.save(); ctx.translate((X0 - view.x) * k, (view.y - Y0) * k); ctx.rotate(-R0);
    ctx.globalAlpha = 0.55; ctx.fillStyle = css(p[2], bgDark);
    ctx.fillRect(x0 * k, -(o.vj === 3 ? 0 : o.vj === 2 ? h * 0.5 : h) * k * -1 - h * 0.7 * k, wbar * k, Math.max(h * 0.45 * k, 1));
    ctx.restore(); return;
  }
  STAT.text++;
  const lines = layoutText(p);
  let wf = (o.wf || 1) * shxK(o.font);
  // AutoCAD's own extents (ew, eh) tell how many lines it laid out: a single line must not wrap with our wider fallback font; scale it to AutoCAD's width instead
  let single = false;
  if (o.mt && oEW && oEH && lines.length === 1) {
    const nac = Math.max(1, Math.round((oEH / h - 1.3333) / 1.6667) + 1);
    if (nac === 1) {
      single = true;
      let nat = 0; for (const r of lines[0]) nat += runWidth(r, px);
      if (nat > 0) wf *= Math.min(1.4, Math.max(0.6, oEW / nat));
    }
  }
  const ls = (o.ls || 1) * 1.6667 * h;
  // measure
  let maxW = 0; const lw = [];
  const wrapW = o.mt && oW > 0 && !single ? oW : 0;
  let L = lines;
  if (wrapW) {   // word wrap
    const out = [];
    for (const ln of lines) {
      let cur = [], cw = 0;
      for (const r of ln) {
        if (r.stack || !r.t) { const w = runWidth(r, px) * wf; if (cw + w > wrapW && cur.length) { cur.al = ln.al; out.push(cur); cur = []; cw = 0; } cur.push(r); cw += w; continue; }
        const words = r.t.split(/(?<=\s)|(?<=[\u2e80-\u9fff\uff00-\uffef])/);   // AutoCAD wraps at spaces (not at hyphens: 'No. 21639-FR-C-..' breaks before the number); CJK breaks anywhere
        for (const wd of words) {
          const rr = Object.assign({}, r, {t: wd}); const w = runWidth(rr, px) * wf;
          if (cw + w > wrapW + 1e-6 && cur.length && wd.trim()) { cur.al = ln.al; out.push(cur); cur = []; cw = 0; }
          cur.push(rr); cw += w;
        }
      }
      cur.al = ln.al; out.push(cur);
    }
    L = out;
  }
  if (window.__dbg && String(p[7]).includes(window.__dbg)) window.__dbgout = {nL: L.length, nlines0: lines.length, wrapW, wf, px, h, single, o};
  for (const ln of L) { let w = 0; for (const r of ln) w += runWidth(r, px) * wf; lw.push(w); if (w > maxW) maxW = w; }
  const nL = L.length;
  const totalH = h + (nL - 1) * ls;
  // anchor: (x,y) with hj/vj. y offset of first baseline relative to anchor (y up)
  let y0;                           // baseline of first line relative to anchor, y up
  const vj = o.vj || 0;
  if (o.mt) { y0 = vj === 3 ? -h : vj === 2 ? -(totalH / 2) + (totalH - h) - (totalH - h) + 0 : 0; }
  if (o.mt) {
    // top of block = anchor for vj 3; first baseline = top - h ; middle: centre ; bottom: last baseline at anchor
    const top = vj === 3 ? 0 : vj === 2 ? totalH / 2 : totalH;
    y0 = top - h;
  } else {
    y0 = vj === 3 ? -h : vj === 2 ? -h / 2 : 0;   // TEXT: baseline(0), bottom(1: descender ignored), middle(2), top(3)
  }
  const bx = o.mt && wrapW && (o.hj || 0) !== 0 ? 0 : 0;
  ctx.save();
  ctx.translate((X0 - view.x) * k, (view.y - Y0) * k);
  ctx.rotate(-R0);
  ctx.scale(k, -k);                 // now drawing units, y up
  ctx.scale(1, -1);                 // flip for text (y down)
  ctx.fillStyle = rc(p, bgDark);
  ctx.textBaseline = 'alphabetic';
  if (o.mx) ctx.scale(-1, 1);
  if (o.my) ctx.scale(1, -1);
  const ob = o.ob ? Math.tan(o.ob) : 0;
  for (let li = 0; li < nL; li++) {
    const ln = L[li], w = lw[li];
    let x = 0;
    const fs_ = o.fit && oFW && w > 0 ? oFW / w : 1;   // aligned (3): scale both axes; fit (5): width only
    if (fs_ !== 1) ctx.save(), ctx.scale(fs_, o.fit === 3 ? fs_ : 1);
    const hj = o.hj || 0;
    const boxW = o.mt ? (wrapW || (ln.ex && oW > 0 ? oW : maxW)) : 0;   // an explicit paragraph alignment (\\pxql) lays the text out in the box width (measured on AC1027_13: 'PLOT 2xx' starts at ins - width/2, not centred)
    if (o.mt) { // block anchored by hj: left: x0 = 0 ; center: block centred; right: right edge
      const blockLeft = hj === 0 ? 0 : hj === 1 ? -boxW / 2 : -boxW;
      x = blockLeft + (ln.al === 'r' ? boxW - w : ln.al === 'c' ? (boxW - w) / 2 : 0);
    } else x = hj === 0 ? 0 : hj === 1 ? -w / 2 : -w;
    const yb = -(y0 - li * ls);     // y down
    let cx = x;
    for (const r of ln) {
      const rpx = px * r.h;
      ctx.font = fontCss(rpx, r.b, r.i);
      if (r.col != null) ctx.fillStyle = css(r.col, bgDark); else ctx.fillStyle = rc(p, bgDark);
      const rw = runWidth(r, px) * wf;
      ctx.save();
      ctx.translate(cx, yb);
      if (ob) ctx.transform(1, 0, -ob, 1, 0, 0);
      if (wf !== 1 || r.w !== 1) ctx.scale(wf * (r.stack ? 1 : r.w), 1);
      if (r.stack) {
        ctx.font = fontCss(rpx * 0.7);
        ctx.fillText(r.stack[0], 0, -h * 0.35); ctx.fillText(r.stack[1], 0, h * 0.45);
        ctx.fillRect(0, -h * 0.05, rw / wf, h * 0.04 * 0.5);
      } else { ctx.fillText(r.t, 0, 0); if (SHXB) { ctx.strokeStyle = ctx.fillStyle; ctx.lineWidth = rpx * 0.05; ctx.lineJoin = 'round'; ctx.strokeText(r.t, 0, 0); } }
      if (r.u) ctx.fillRect(0, h * 0.15, rw / (wf * r.w), h * 0.06);
      if (r.o) ctx.fillRect(0, -h * 1.1, rw / (wf * r.w), h * 0.06);
      ctx.restore();
      cx += rw;
    }
    if (fs_ !== 1) ctx.restore();
  }
  ctx.restore();
}

// ---------------------------------------------------------------- dashes
function dashArr(d) {
  if (!d) return null;
  const cache = d._c; if (cache) return cache;
  const out = []; let on = true, cur = 0, have = false;
  let tot = 0; for (const v of d) tot += Math.abs(v);
  const dot = Math.max(tot * 0.003, 1e-9);
  const arr = []; // alternate on/off
  let state = null, acc = 0;
  const push = (isOn, len) => {
    if (state === isOn) { arr[arr.length - 1] += len; return; }
    if (state === null && !isOn) arr.push(0);
    arr.push(len); state = isOn;
  };
  for (const v of d) { if (v > 0) push(true, v); else if (v < 0) push(false, -v); else push(true, dot); }
  if (arr.length % 2) arr.push(0);
  d._c = {a: arr, period: tot}; return d._c;
}

// ---------------------------------------------------------------- scene prep
function prepRows(rows) {
  for (const p of rows) {
    let x0 = 1e300, y0 = 1e300, x1 = -1e300, y1 = -1e300;
    if (p[0] === 'l') { const f = p[5]; for (let i = 0; i < f.length; i += 2) { const x = f[i], y = f[i + 1]; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; } }
    else if (p[0] === 'h') { for (const f of p[3]) for (let i = 0; i < f.length; i += 2) { const x = f[i], y = f[i + 1]; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; } }
    else if (p[0] === 't') { const r = p[5] * 40; x0 = p[3] - r; x1 = p[3] + r; y0 = p[4] - r; y1 = p[4] + r; }
    else { x0 = x1 = p[3]; y0 = y1 = p[4]; }
    p.bb = [x0, y0, x1, y1];
  }
}
function applyLayerState() { vis = meta.layers.map((l, i) => !!lyOn[i] && !lyFrz[i]); vis[-1] = true; sceneVer++; draw(); }
function on(i) { return i < 0 || (vis[i] && !((CTB || PLOTMODE) && meta.layers[i].plot === false)); }
function fit() {
  if (!lay) return;
  const zq = new URLSearchParams(location.search).get('z');
  const b = zq ? zq.split(',').map(Number) : (new URLSearchParams(location.search).get('fit') === 'full' && lay.full ? lay.full : lay.bounds), w = cv.width / devicePixelRatio, h = cv.height / devicePixelRatio;
  const bw = Math.max(b[2] - b[0], 1e-9), bh = Math.max(b[3] - b[1], 1e-9);
  view.s = Math.min(w / bw, h / bh) * (zq ? 1.0 : 0.95);
  view.x = (b[0] + b[2]) / 2 - w / 2 / view.s; view.y = (b[1] + b[3]) / 2 + h / 2 / view.s;
  draw();
}
function resize() { cv.width = cv.clientWidth * devicePixelRatio; cv.height = cv.clientHeight * devicePixelRatio; sceneVer++; draw(); }
addEventListener('resize', resize);

// ---------------------------------------------------------------- hatch patterns
function hatchPath(loops) {
  ctx.beginPath();
  for (const l of loops) { ctx.moveTo(l[0], l[1]); for (let i = 2; i < l.length; i += 2) ctx.lineTo(l[i], l[i + 1]); ctx.closePath(); }
}
function lwOnNow() { return $('lwOn').checked; }
const OLEI = {};
function olePic(h) { let i = OLEI[h]; if (!i) { i = new Image(); i.onload = () => invalidate(); i.src = '/api/ole/' + h; OLEI[h] = i; } return i; }
function drawHatch(p, k, bgDark, vb, sc = 1) {
  const info = p[4];
  if (info.img) {   // embedded OLE picture: quad TL, TR, BR, BL
    const im = olePic(info.img), f = p[3][0];
    if (im.complete && im.naturalWidth) {
      const w = im.naturalWidth, h = im.naturalHeight;
      ctx.save(); ctx.transform((f[2] - f[0]) / w, (f[3] - f[1]) / w, (f[6] - f[0]) / h, (f[7] - f[1]) / h, f[0], f[1]);
      ctx.drawImage(im, 0, 0); ctx.restore();
    }
    return;
  }
  ctx.fillStyle = rc(p, bgDark);
  if (info.solid) { hatchPath(p[3]); const ga = ctx.globalAlpha; if (info.a != null) ctx.globalAlpha = ga * info.a; ctx.fill(info.nz ? 'nonzero' : 'evenodd'); ctx.globalAlpha = ga; return; }
  if (info.grad && info.grad.colors && info.grad.colors.length) { hatchPath(p[3]); ctx.globalAlpha = 0.5; ctx.fill('evenodd'); ctx.globalAlpha = 1; return; }
  const lines = info.lines;
  if (!lines || !lines.length) { hatchPath(p[3]); ctx.globalAlpha = 0.2; ctx.fill('evenodd'); ctx.globalAlpha = 1; return; }
  // visible region = hatch bbox ∩ view
  const x0 = Math.max(p.bb[0], vb[0]), y0 = Math.max(p.bb[1], vb[1]), x1 = Math.min(p.bb[2], vb[2]), y1 = Math.min(p.bb[3], vb[3]);
  if (x0 >= x1 || y0 >= y1) return;
  // too dense on screen -> average tint
  let dense = false;
  for (const ln of lines) { const d = Math.abs(ln[3] * Math.sin(ln[0]) * -1 + ln[4] * Math.cos(ln[0])); if (d * k < 2.2) { dense = true; break; } }
  if (dense) { hatchPath(p[3]); ctx.globalAlpha = 0.35; ctx.fill('evenodd'); ctx.globalAlpha = 1; return; }
  ctx.save();
  hatchPath(p[3]); ctx.clip('evenodd');
  ctx.strokeStyle = rc(p, bgDark);
  ctx.lineWidth = Math.max(1 / k, (paper || sc !== 1) && lwOnNow() && info.w ? info.w * +$('lwK').value / sc : 0);   // pattern lines take the hatch lineweight (paper mm) on sheets
  const corners = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  ctx.beginPath();
  let budget = 6000;
  for (const [ang, ox, oy, fx, fy, dsh] of lines) {
    const dx = Math.cos(ang), dy = Math.sin(ang), nx = -dy, ny = dx;
    const perp = fx * nx + fy * ny;          // perpendicular spacing (signed)
    const along = fx * dx + fy * dy;         // shift along the line per row
    if (Math.abs(perp) < 1e-9) continue;
    let nmin = 1e300, nmax = -1e300, tmin = 1e300, tmax = -1e300;
    for (const [cx, cy] of corners) {
      const pn = ((cx - ox) * nx + (cy - oy) * ny) / perp; if (pn < nmin) nmin = pn; if (pn > nmax) nmax = pn;
    }
    const n0 = Math.floor(nmin) - 1, n1 = Math.ceil(nmax) + 1;
    if (n1 - n0 > 4000) continue;
    const pat = dsh && dsh.length ? dashArr(dsh) : null;
    for (let n = n0; n <= n1 && budget > 0; n++) {
      const px = ox + n * fx, py = oy + n * fy;
      let ta = 1e300, tb = -1e300;
      for (const [cx, cy] of corners) { const t = (cx - px) * dx + (cy - py) * dy; if (t < ta) ta = t; if (t > tb) tb = t; }
      if (pat && pat.period > 0) {
        ta = Math.floor(ta / pat.period) * pat.period;
        if ((tb - ta) / pat.period * pat.a.length > 4000) continue;
        // explicit dash segments
        let t = ta; budget--;
        while (t < tb) {
          for (let i = 0; i < pat.a.length; i += 2) {
            const a = t, b = t + pat.a[i];
            if (b >= ta && a <= tb) { ctx.moveTo(px + dx * a, py + dy * a); ctx.lineTo(px + dx * b, py + dy * b); }
            t += pat.a[i] + pat.a[i + 1];
          }
          if (pat.period <= 0) break;
        }
      } else { ctx.moveTo(px + dx * ta, py + dy * ta); ctx.lineTo(px + dx * tb, py + dy * tb); budget--; }
    }
  }
  ctx.stroke();
  ctx.restore();
}

// ---------------------------------------------------------------- render
function drawRows(rows, k, vb, bgDark, lwOn, F, frozen) {
  // wipeouts mask everything before them in the list: draw the list in chunks split at the wipeouts
  let start = 0, drawn = 0;
  for (let i = 0; i < rows.length; i++) {
    const p = rows[i];
    if (p[0] === 'h' && p[4].wipe) {
      if (i > start) drawn += drawChunk(rows, start, i, k, vb, bgDark, lwOn, F, frozen);
      if (!(!on(p[1]) || (frozen && p[1] >= 0 && frozen.has(p[1])) || parentHidden(p, frozen))) {
        const b = p.bb;
        if (!(b[2] < vb[0] || b[0] > vb[2] || b[3] < vb[1] || b[1] > vb[3]) && $('oHatch').checked) { ctx.fillStyle = bgDark ? '#111' : '#fff'; hatchPath(p[3]); ctx.fill('evenodd'); }
      }
      start = i + 1;
    }
  }
  if (rows.length > start) drawn += drawChunk(rows, start, rows.length, k, vb, bgDark, lwOn, F, frozen);
  return drawn;
}
// layer alpha: locked layers are dimmed, layer transparency (percent from the LAYER data) lowers opacity further
// handle-keyed maps: JSON keys are exact strings but row handles are parsed as doubles (R14 handles exceed 2^53), so key by Number(key)
function numMap(o) { return new Map(Object.entries(o).map(([k, v]) => [Number(k), v])); }
function entAlpha(p) { if (!lay || !lay.ea) return 1; const m = lay._ea || (lay._ea = numMap(lay.ea)); const v = m.get(p[p.length - 1]); return v == null ? 1 : v; }
// content of an INSERT whose own layer is off / frozen (here or in the viewport) is hidden although its entities sit on other layers
function parentHidden(p, frozen) { if (!lay || !lay.tl) return false; const m = lay._tl || (lay._tl = numMap(lay.tl)); const i = m.get(p[p.length - 1]); return i != null && (!on(i) || !!(frozen && frozen.has(i))); }
function lyAlpha(i) { const t = i >= 0 && meta && meta.layers[i] ? (meta.layers[i].tr || 0) : 0; return (lyLock[i] ? 0.4 : 1) * (1 - t / 100); }
function drawChunk(all, from, to, k, vb, bgDark, lwOn, F, frozen) {
  const rows = (from === 0 && to === all.length) ? all : all.slice(from, to);
  // F: null (final space) or {m, s, psl}: rows are in model units drawn under the canvas transform m (model -> paper), s = uniform scale
  const sc = F ? F.s : 1, kk = k * sc, px = 1 / kk;
  const dk = F ? (F.psl ? 1 / sc : 1) : 1;           // dash pattern units -> model units (PSLTSCALE keeps paper length)
  let drawn = 0;
  const skip = p => !on(p[1]) || (frozen && p[1] >= 0 && frozen.has(p[1])) || rowOff(p) || parentHidden(p, frozen);
  for (const p of rows) {
    if (p[0] !== 'h' || p[4].wipe || skip(p) || !$('oHatch').checked) continue;
    const b = p.bb; if (b[2] < vb[0] || b[0] > vb[2] || b[3] < vb[1] || b[1] > vb[3]) continue;
    ctx.globalAlpha = lyAlpha(p[1]);
    drawHatch(p, kk, bgDark, vb, sc);
    ctx.globalAlpha = 1;
  }
  ctx.lineJoin = 'round'; ctx.lineCap = 'butt';
  const K = +$('lwK').value;
  for (const p of rows) {
    if (p[0] !== 'l' || skip(p) || !$('oLines').checked) continue;
    const b = p.bb; if (b[2] < vb[0] || b[0] > vb[2] || b[3] < vb[1] || b[1] > vb[3]) continue;
    if ((b[2] - b[0] + b[3] - b[1]) * kk < 0.3) continue;   // sub-pixel paths
    if (p[3] < 0 && (PLOTMODE || CTB)) continue;   // image placeholder
    const f = p[5];
    ctx.globalAlpha = lyAlpha(p[1]) * entAlpha(p);
    ctx.strokeStyle = rc(p, bgDark);
    let mm = lwOn ? Math.max(p[3], 0.18) * K : 0;
    if (CTB && lwOn && !Array.isArray(p[2]) && CTB[p[2]] && CTB[p[2]][1] != null) mm = CTB[p[2]][1] * K;
    // paper space and viewport content: lineweight in paper mm; model space: display-only pixel width
    ctx.lineWidth = (paper || F) ? Math.max((mm || 0) / sc, px) : Math.max((mm ? mm * 3.78 * 0.5 : 1) * px, px);
    if (p[7]) ctx.lineWidth = Math.max(ctx.lineWidth, p[7]);   // polyline constant width (drawing units)
    const da = p[4] ? dashArr(p[4]) : null;
    if (da && da.period * dk * kk > 3) { STAT.dash++; ctx.setLineDash(dk === 1 ? da.a : da.a.map(v => v * dk)); } else ctx.setLineDash([]);
    ctx.beginPath(); ctx.moveTo(f[0], f[1]);
    for (let i = 2; i < f.length; i += 2) ctx.lineTo(f[i], f[i + 1]);
    ctx.stroke(); drawn++;
  }
  ctx.globalAlpha = 1;
  ctx.setLineDash([]);
  for (const p of rows) {
    if (p[0] !== 'p' || skip(p)) continue;
    ctx.fillStyle = rc(p, bgDark); ctx.fillRect(p[3] - 1.5 * px, p[4] - 1.5 * px, 3 * px, 3 * px);
  }
  return drawn;
}
function drawTexts(rows, k, vb, bgDark, F, frozen) {
  for (const p of rows) {
    if (p[0] !== 't' || !on(p[1]) || (frozen && p[1] >= 0 && frozen.has(p[1])) || !$('oText').checked || rowOff(p) || parentHidden(p, frozen)) continue;
    const b = p.bb; if (b[2] < vb[0] || b[0] > vb[2] || b[3] < vb[1] || b[1] > vb[3]) continue;
    ctx.globalAlpha = lyAlpha(p[1]) * entAlpha(p);
    drawText(p, k, bgDark, F);
    ctx.globalAlpha = 1;
  }
}
// ---------------------------------------------------------------- frame pipeline
// A full render draws everything. When it is slow (big drawing) the last full render is cached in an offscreen canvas with a margin;
// while the user pans/zooms that bitmap is transformed (text, dashes and hatches are in it, so nothing flickers) and one full render
// follows when the gesture settles. Fast drawings are simply redrawn in full on every frame.
let catOff = new Set(), TXK = 1; const ctbNames = new Set();
function rowOff(p) { if (!catOff.size && !(PLOTMODE || CTB)) return false; const k = lay.kinds && lay.kinds[p[p.length - 1]]; if (k === 'image' && (PLOTMODE || CTB)) return true; return catOff.has(k || (p[0] === 'h' ? 'hatch' : p[0] === 't' ? 'text' : p[0] === 'p' ? 'point' : 'curve')); }
const STAT = {text: 0, dash: 0, rows: 0};
const SLOW_MS = 28, MARGIN = 0.22;
let cache = null, interacting = false, settleTimer = 0, lastFullMs = 0, frameLog = [];
function interact() { interacting = true; clearTimeout(settleTimer); settleTimer = setTimeout(() => { interacting = false; draw(); }, 140); draw(); }
function draw() { if (!raf) raf = requestAnimationFrame(frame); }
function bgColor() { return document.body.classList.contains('clean') ? '#fff' : paper ? (dark ? '#333' : '#8a8a8a') : (dark ? '#111' : '#fff'); }
function renderScene(target, v) {
  // draws the whole scene for view v (css-pixel units; y up) into the canvas `target`
  const sctx = ctx, sview = view;
  ctx = target.getContext('2d'); view = v;
  STAT.text = 0; STAT.dash = 0;
  try {
    const W = target.width, H = target.height, dpr = devicePixelRatio;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = bgColor(); ctx.fillRect(0, 0, W, H);
    if (!lay) return 0;
    const bgDark = dark && !paper;
    const k = v.s * dpr;
    if (paper) {
      ctx.fillStyle = dark ? '#1a1a1a' : '#fff'; const b = lay.bounds;
      ctx.fillRect((b[0] - v.x) * k, (v.y - b[3]) * k, (b[2] - b[0]) * k, (b[3] - b[1]) * k);
    }
    const clipPage = PLOTMODE && paper && !new URLSearchParams(location.search).get('noclip');      // plot preview: only the sheet is plotted, items outside the paper edge are cut
    if (clipPage) { const b = lay.bounds; ctx.save(); ctx.beginPath(); ctx.rect((b[0] - v.x) * k, (v.y - b[3]) * k, (b[2] - b[0]) * k, (b[3] - b[1]) * k); ctx.clip(); }
    const fg = paper ? dark : bgDark;
    const base = [k, 0, 0, -k, -v.x * k, v.y * k];
    ctx.setTransform(...base);
    const lwOn = $('lwOn').checked;
    const vb = [v.x, v.y - H / k, v.x + W / k, v.y];
    let drawn = drawRows(lay.prims, k, vb, fg, lwOn, null, null);
    const vpInfo = lay.vps.map(vp => ({vp, F: vpFrame(vp), fz: vp.fzs}));
    const clipBB = vp => { const cb = vp.clip; return vp.cbb || (vp.cbb = [Math.min(...cb.filter((_, i) => i % 2 === 0)), Math.min(...cb.filter((_, i) => i % 2 === 1)), Math.max(...cb.filter((_, i) => i % 2 === 0)), Math.max(...cb.filter((_, i) => i % 2 === 1))]); };
    for (const {vp, F, fz} of vpInfo) {
      ctx.save(); clipPath(vp.clip); ctx.clip(); ctx.transform(...F.m);
      const cbb = clipBB(vp), pb = [Math.max(vb[0], cbb[0]), Math.max(vb[1], cbb[1]), Math.min(vb[2], cbb[2]), Math.min(vb[3], cbb[3])];
      if (pb[0] < pb[2] && pb[1] < pb[3]) drawn += drawRows(lay.mprims, k, modelBBox(F, pb), fg, lwOn, F, fz);
      ctx.restore();
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    drawTexts(lay.prims, k, vb, fg, null, null);
    for (const {vp, F, fz} of vpInfo) {
      ctx.save(); ctx.setTransform(...base); clipPath(vp.clip); ctx.clip(); ctx.setTransform(1, 0, 0, 1, 0, 0);
      const cbb = clipBB(vp), pb = [Math.max(vb[0], cbb[0]), Math.max(vb[1], cbb[1]), Math.min(vb[2], cbb[2]), Math.min(vb[3], cbb[3])];
      if (pb[0] < pb[2] && pb[1] < pb[3]) drawTexts(lay.mprims, k, modelBBox(F, pb), fg, F, fz);
      ctx.restore();
    }
    if (clipPage) ctx.restore();
    return drawn;
  } finally { ctx = sctx; view = sview; }
}
function frame() {
  raf = 0;
  const t0 = performance.now();
  const W = cv.width, H = cv.height, dpr = devicePixelRatio;
  let mode = 'full', drawn = 0;
  const useCache = lastFullMs > SLOW_MS;
  if (!lay) { const c = cv.getContext('2d'); c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = bgColor(); c.fillRect(0, 0, W, H); }
  else if (!useCache) {
    cache = null; drawn = renderScene(cv, view); lastFullMs = performance.now() - t0;
  } else {
    const valid = cache && cache.ver === sceneVer && cache.W === W && cache.H === H;
    if (!(interacting && valid)) {
      // full render into the margin cache, then show it
      const mw = Math.round(W * (1 + 2 * MARGIN)), mh = Math.round(H * (1 + 2 * MARGIN));
      if (!cache || cache.canvas.width !== mw || cache.canvas.height !== mh) { cache = {canvas: document.createElement('canvas')}; cache.canvas.width = mw; cache.canvas.height = mh; }
      const mx = W * MARGIN, my = H * MARGIN;
      cache.view = {x: view.x - mx / dpr / view.s, y: view.y + my / dpr / view.s, s: view.s};
      cache.W = W; cache.H = H; cache.ver = sceneVer;
      const t1 = performance.now(); drawn = renderScene(cache.canvas, cache.view); lastFullMs = performance.now() - t1;
    } else mode = 'bitmap';
    const c = cv.getContext('2d'); c.setTransform(1, 0, 0, 1, 0, 0);
    c.fillStyle = bgColor(); c.fillRect(0, 0, W, H);
    const r = view.s / cache.view.s;
    c.drawImage(cache.canvas, (cache.view.x - view.x) * view.s * dpr, (view.y - cache.view.y) * view.s * dpr, cache.canvas.width * r, cache.canvas.height * r);
  }
  if (typeof drawOverlay === 'function') drawOverlay();
  const ms = Math.round(performance.now() - t0);
  frameLog.push({mode, ms, text: STAT.text, dash: STAT.dash, vx: view.x, vs: view.s}); if (frameLog.length > 400) frameLog.shift();
  if (mode === 'full') $('stat').textContent = drawn + ' paths ' + Math.round(lastFullMs) + ' ms';
  if (!useCache) interacting = interacting;   // fast path: every frame is a full render
}
let sceneVer = 0;   // bump whenever what is drawn changes (layers, toggles, colours, layout)
function invalidate() { sceneVer++; draw(); }
function vpFrame(vp) {
  const m = vp.M;   // [a, b, c, d, tx, ty] canvas order, model -> paper
  const s = Math.hypot(m[0], m[1]);
  return {m, s, rot: Math.atan2(m[1], m[0]), psl: vp.psl, an: vp.an};
}
function modelBBox(F, pb) {   // paper-space bbox -> model-space bbox through the inverse of F.m
  const m = F.m, det = m[0] * m[3] - m[1] * m[2];
  const inv = (X, Y) => { const dx = X - m[4], dy = Y - m[5]; return [(m[3] * dx - m[2] * dy) / det, (-m[1] * dx + m[0] * dy) / det]; };
  const cs = [inv(pb[0], pb[1]), inv(pb[2], pb[1]), inv(pb[2], pb[3]), inv(pb[0], pb[3])];
  return [Math.min(...cs.map(c => c[0])), Math.min(...cs.map(c => c[1])), Math.max(...cs.map(c => c[0])), Math.max(...cs.map(c => c[1]))];
}
function clipPath(c) { ctx.beginPath(); ctx.moveTo(c[0], c[1]); for (let i = 2; i < c.length; i += 2) ctx.lineTo(c[i], c[i + 1]); ctx.closePath(); }

cv.addEventListener('wheel', e => {
  e.preventDefault();
  const r = cv.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
  const wx = view.x + mx / view.s, wy = view.y - my / view.s;
  view.s *= Math.exp(-e.deltaY * 0.0015);
  view.x = wx - mx / view.s; view.y = wy + my / view.s; interact();
}, {passive: false});
$('ctb').onchange = async e => {
  const n = e.target.value; CTB = null; colCache.clear();
  if (n && n[0] === '\u2191') { CTB = ctbUploads[n] || null; invalidate(); return; }
  if (n) { const r = await (await fetch('/api/ctb?name=' + encodeURIComponent(n))).json(); if (r.found) { CTB = r.aci; CTB.mono = /mono/i.test(n); } }
  invalidate();
};
const ctbUploads = {};
$('ctbFile').onchange = async e => {      // a plot style table picked from disk (kept in the browser session only)
  const f = e.target.files[0]; if (!f) return;
  const r = await (await fetch('/api/ctbupload', {method: 'POST', body: await f.arrayBuffer()})).json();
  if (!r.found) { alert('could not read ' + f.name + (r.error ? ': ' + r.error : '')); return; }
  CTB = r.aci; CTB.mono = /mono/i.test(f.name); colCache.clear(); ctbUploads['\u2191 ' + f.name] = CTB;
  let o = [...$('ctb').options].find(x => x.value === '\u2191 ' + f.name); if (!o) { o = document.createElement('option'); o.value = '\u2191 ' + f.name; o.textContent = f.name + ' (from disk)'; $('ctb').append(o); }
  $('ctb').value = o.value; invalidate(); e.target.value = '';
};
for (const id of ['oLines', 'oHatch', 'oText', 'lwK']) $(id).oninput = invalidate;
$('txK').oninput = e => { TXK = +e.target.value; for (const p of lay ? [...lay.prims, ...lay.mprims] : []) if (p[0] === 't') delete p._lt; invalidate(); };
$('twist').onchange = () => openLayout(layIdx);
$('linkBtn').onclick = async () => {
  const w = cv.width / devicePixelRatio, h = cv.height / devicePixelRatio;
  const hide = meta.layers.filter((l, i) => !lyOn[i] || lyFrz[i]).map(l => l.n);
  const same = (a, b) => a.size === b.size && [...a].every(x => b.has(x));
  const vpFrozen = {}, anno = {};
  for (const [k, set] of Object.entries(vpFz)) { if (vpFz0[k] && same(set, vpFz0[k])) continue; vpFrozen[k] = [...set].map(j => meta.layers[j].n); }
  if (lay) for (const v of lay.vps) if (v.an0 !== undefined && v.an !== v.an0) anno[layIdx + ':' + v.id] = v.an;
  const u = new URL(location.href); u.search = LinkState.encode({layout: layIdx, z: [view.x, view.y - h / view.s, view.x + w / view.s, view.y], hide, vpFrozen, anno});
  if ($('ctb').value) u.searchParams.set('ctb', $('ctb').value);
  try { await navigator.clipboard.writeText(u.href); $('linkBtn').textContent = 'Copied'; } catch (e) { prompt('Link:', u.href); }
  setTimeout(() => $('linkBtn').textContent = 'Link', 1500);
};
$('fit').onclick = fit; $('lwOn').onchange = invalidate; $('dark').onchange = e => { dark = e.target.checked; invalidate(); };
async function openLayout(i, win) {
  layIdx = i;
  [...$('tabs').children].forEach((b, j) => b.className = j === i ? 'on' : '');
  $('msg').style.display = 'block'; $('msg').textContent = 'loading layout...';
  const r = await fetch('/api/layout/' + i + (new URLSearchParams(location.search).get('twist') === '0' || !$('twist').checked ? '?twist=0' : '')); lay = await r.json();
  paper = !!lay.paper;
  prepRows(lay.prims); prepRows(lay.mprims);
  const LKS = (typeof LinkState !== 'undefined') ? LinkState.decode(location.search) : {vpFrozen: {}, anno: {}};
  const lidx = new Map(meta.layers.map((l, j) => [l.n, j]));
  for (const v of lay.vps) {
    const k = layIdx + ':' + v.id; v.fz0 = vpFz0[k] || (vpFz0[k] = new Set(v.frozen));
    if (!vpFz[k] && LKS.vpFrozen[k]) vpFz[k] = new Set(LKS.vpFrozen[k].map(n => lidx.get(n)).filter(j => j !== undefined));
    v.fzs = vpFz[k] || (vpFz[k] = new Set(v.frozen));
    if (LKS.anno[k] && !v.annoSet) { v.an0 = v.an || 1; v.an = LKS.anno[k]; v.annoSet = true; }
  }
  clearSelection(true);
  $('msg').style.display = 'none';
  if (win) { lay.bounds = win; }
  const st = meta.layouts[i].style;
  $('ctb').title = st ? 'layout plot style: ' + st + (ctbNames.has(st.toLowerCase()) ? ' (available: select it to preview)' : ' (file not available locally)') : 'no plot style table on this layout';
  sceneVer++; buildLayerTable(); if (window.lsReady) { window.lsReady(); window.lsReady = null; } fit();
}
// external references: their content is not in the file, so the viewer lists them (missing ones are not drawn)
function showXrefs(m) {
  const b = $('xrefBadge'), x = m.xrefs || []; if (!b) return;
  if (!x.length) { b.style.display = 'none'; return; }
  const miss = x.filter(r => !r.found).length;
  b.style.display = 'inline'; b.textContent = x.length + ' xref' + (x.length > 1 ? 's' : '') + (miss ? ' (' + miss + ' not drawn)' : '');
  b.style.color = miss ? '#e8a33a' : '#7c7';
  b.title = 'external references (drawn when the DWG is found next to this drawing):\n' + x.map(r => (r.found ? '[drawn] ' : '[not found] ') + (r.overlay ? '[overlay] ' : '') + r.name + '  <-  ' + r.path).join('\n');
}
async function init() {
  try { await Promise.all([new FontFace('LibSans', 'url(fonts/LiberationSans-Regular.ttf)').load().then(f => document.fonts.add(f)),
    new FontFace('LibSans', 'url(fonts/LiberationSans-Bold.ttf)', {weight: 'bold'}).load().then(f => document.fonts.add(f)),
    new FontFace('LibSans', 'url(fonts/LiberationSans-Italic.ttf)', {style: 'italic'}).load().then(f => document.fonts.add(f)),
    new FontFace('LibSans', 'url(fonts/LiberationSans-BoldItalic.ttf)', {weight: 'bold', style: 'italic'}).load().then(f => document.fonts.add(f))]); } catch (e) { console.log(e); }
  for (;;) {
    const m = await (await fetch('/api/meta')).json();
    if (m.error) { $('msg').style.display = 'block'; $('msg').textContent = m.error; return; }
    if (!m.loading) { meta = m; showXrefs(m); break; }
    $('msg').style.display = 'block'; $('msg').textContent = 'parsing...';
    await new Promise(r => setTimeout(r, 500));
  }
  $('fname').textContent = meta.file;
  lyOn = meta.layers.map(l => !l.off); lyFrz = meta.layers.map(l => !!l.frz); lyLock = meta.layers.map(l => !!l.lock); applyLayerState();
  const qh = (typeof LinkState !== 'undefined' ? LinkState.decode(location.search).hide : (new URLSearchParams(location.search).get('hide') || '').split(',').filter(Boolean)); if (qh.length) { const hs = new Set(qh); meta.layers.forEach((l, i) => { if (hs.has(l.n)) lyOn[i] = false; }); applyLayerState(); }
  meta.layouts.forEach((l, i) => { const b = document.createElement('button'); b.textContent = l.name; b.onclick = () => openLayout(i); $('tabs').append(b); });
  let st = 0;
  if (meta.start != null) { const n = meta.layouts.findIndex(l => l.name === meta.start); st = n >= 0 ? n : (parseInt(meta.start) || 0); }
  if (typeof meta.start === 'number') st = meta.start;
  const ql = new URLSearchParams(location.search).get('l'); if (ql != null) st = parseInt(ql) || 0;
  if (new URLSearchParams(location.search).get('clean')) { document.body.classList.add('clean'); }
  try { const l = await (await fetch('/api/ctblist')).json(); for (const n of l) { ctbNames.add(n.toLowerCase()); const o = document.createElement('option'); o.value = n; o.textContent = n; $('ctb').append(o); } } catch (_) {}
  const qc = new URLSearchParams(location.search).get('ctb'); if (qc) { $('ctb').value = qc; await $('ctb').onchange({target: $('ctb')}); }
  resize(); await openLayout(st);
  const qd = new URLSearchParams(location.search).get('dbl'); if (qd) { const [a, b] = qd.split(',').map(Number); await dblAt(a, b); }
}
init();

// double click inside a viewport: open Model space framed to what that viewport shows, with its frozen layers off
function pointInPoly(x, y, c) { let ins = false; for (let i = 0, j = c.length - 2; i < c.length; j = i, i += 2) { const xi = c[i], yi = c[i + 1], xj = c[j], yj = c[j + 1]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) ins = !ins; } return ins; }
cv.addEventListener('dblclick', e => dblAt(e.clientX, e.clientY));
async function dblAt(cx, cy) {
  if (!lay || !lay.vps.length) return;
  const r = cv.getBoundingClientRect(), wx = view.x + (cx - r.left) / view.s, wy = view.y - (cy - r.top) / view.s;
  const vp = [...lay.vps].reverse().find(v => pointInPoly(wx, wy, v.clip));
  if (new URLSearchParams(location.search).get('dbl')) { $('msg').style.display = 'block'; $('msg').textContent = 'dbl ' + wx.toFixed(1) + ',' + wy.toFixed(1) + ' vp=' + (vp ? vp.id : 'none') + ' n=' + lay.vps.length; }
  if (!vp) return;
  const mi = meta.layouts.findIndex(l => !l.ps);
  if (mi < 0) return;
  lyOn = meta.layers.map(l => !l.off); lyFrz = meta.layers.map((l, i) => !!l.frz || vp.frozen.includes(i)); applyLayerState();
  await openLayout(mi, vp.mwin);
}
