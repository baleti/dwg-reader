const test = require('node:test');
const assert = require('node:assert/strict');
const {csvEscape, layersToCsv} = require('../../web/layercsv.js');

test('CSV escaping preserves CR/LF, quotes, and scalar values', () => {
  for (const [input, expected] of [[undefined, ''], [null, ''], [false, 'false'],
    [0, '0'], ['', ''], ['a\rb', '"a\rb"'], ['a\r\nb,"c"', '"a\r\nb,""c"""']]) {
    assert.equal(csvEscape(input), expected);
  }
});

test('export follows indices, formats defaults, and does not mutate inputs', () => {
  const layers = Object.freeze([
    Object.freeze({n: 'first', c: Object.freeze([0, 15, 255]), lw: 1, tr: 75, plot: true}),
    Object.freeze({n: 'last, "quoted"', c: Object.freeze([256]), desc: 'one\r\ntwo', used: true})
  ]);
  const order = Object.freeze([1, 0]);
  const state = Object.freeze({on: {0: true}, frz: {1: true}, lock: {0: true}, ovr: {1: 'rgb(1, 2, 3)'}});
  const header = 'Name,On,Frozen,Locked,Color,Linetype,Lineweight,Transparency,Plot,Used,Description';
  assert.equal(layersToCsv(layers, order, state), header + '\r\n' +
    '"last, ""quoted""",no,yes,no,"rgb(1, 2, 3)",Continuous,Default,0,no,yes,"one\r\ntwo"\r\n' +
    'first,yes,no,yes,#000fff,Continuous,1.00 mm,75,yes,no,');
  assert.equal(layersToCsv(layers, [], state), header);
});
