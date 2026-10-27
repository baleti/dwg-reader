const R = [];
const T = (name, fn) => { try { const d = fn(); R.push([name, d === true || d === undefined, d]); } catch (e) { R.push([name, false, String(e)]); } };
let copied;
const clipboard = value => Object.defineProperty(navigator, 'clipboard', {value, configurable: true});
clipboard({writeText: text => { copied = text; return Promise.resolve(); }});
const clickCsv = () => $('lbCsv').click();
const names = () => copied.split('\r\n').slice(1).map(row => row.split(',')[0]).join('|');
buildLayerTable();
T('filtered rows export in descending table order', () => {
  $('lfilter').value = 'A-WALL'; LSORT.dir = -1; buildLayerTable(); clickCsv();
  return names() === 'A-WALL-2|A-WALL-10|A-WALL';
});
T('selected visible rows export in table order using current state', () => {
  lSel.add(1); lSel.add(3); lSel.add(5);
  lyOn[3] = false; lyFrz[3] = true; lyLock[3] = true; OVR[3] = '#123abc';
  buildLayerTable(); clickCsv();
  return names() === 'A-WALL-2|A-WALL' && copied.includes('A-WALL-2,no,yes,yes,#123abc,');
});
T('repeated clicks preserve footer and replace suffix', () => {
  const base = $('lfoot').textContent.split(' | ')[0]; clickCsv(); clickCsv();
  return $('lfoot').textContent === base + ' | CSV copied (2 layers)';
});
T('empty filter results export only header', () => {
  lSel.clear(); $('lfilter').value = 'no-match'; buildLayerTable(); clickCsv();
  return copied === 'Name,On,Frozen,Locked,Color,Linetype,Lineweight,Transparency,Plot,Used,Description' && $('lfoot').textContent.endsWith(' | CSV copied (0 layers)');
});
T('missing clipboard still updates status', () => {
  clipboard(undefined); $('lfilter').value = ''; buildLayerTable(); clickCsv();
  return $('lfoot').textContent.endsWith(' | CSV copied (7 layers)');
});
let unhandled = false;
window.addEventListener('unhandledrejection', () => { unhandled = true; });
clipboard({writeText: () => Promise.reject(new Error('denied'))});
buildLayerTable(); clickCsv();
setTimeout(() => {
  T('clipboard rejection is caught and status still updates', () => !unhandled && $('lfoot').textContent.endsWith(' | CSV copied (7 layers)'));
  document.getElementById('out').textContent = JSON.stringify({results: R});
}, 0);
