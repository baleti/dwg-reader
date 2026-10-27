'use strict';

function csvEscape(v) {
  const s = v == null ? '' : String(v);
  return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function layersToCsv(layers, order, state) {
  const lines = ['Name,On,Frozen,Locked,Color,Linetype,Lineweight,Transparency,Plot,Used,Description'];
  const yesNo = v => v ? 'yes' : 'no';
  for (const i of order) {
    const l = layers[i];
    const color = (state.ovr && state.ovr[i]) || (l.c.length === 1
      ? 'ACI ' + l.c[0]
      : '#' + l.c.map(v => v.toString(16).padStart(2, '0')).join(''));
    lines.push([l.n, yesNo(state.on[i]), yesNo(state.frz[i]), yesNo(state.lock[i]),
      color, l.lt || 'Continuous', l.lw ? l.lw.toFixed(2) + ' mm' : 'Default',
      l.tr || 0, yesNo(l.plot), yesNo(l.used), l.desc || ''].map(csvEscape).join(','));
  }
  return lines.join('\r\n');
}

if (typeof module !== 'undefined') module.exports = {csvEscape, layersToCsv};
