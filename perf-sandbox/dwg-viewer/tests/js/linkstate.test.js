'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const LS = require('../../web/linkstate.js');

test('encode order and omission', () => {
  assert.equal(LS.encode({}), '');
  assert.equal(LS.encode({ layout: 2 }), 'l=2');
  assert.equal(LS.encode({ layout: 0, z: [0, 1, 2.5, 3] }), 'l=0&z=0%2C1%2C2.5%2C3');
  assert.equal(LS.encode({ layout: 1, hide: ['A', 'B'] }), 'l=1&hide=A%2CB');
});
test('z precision', () => {
  const s = LS.encode({ z: [1 / 3, 2 / 3, 1e-7, 123456789.123456] });
  const d = LS.decode(s).z;
  assert.deepEqual(d, [0.3333333333, 0.6666666667, 1e-7, 123456789.1]);
});
test('old links decode', () => {
  const d = LS.decode('?l=3&z=1,2,3,4&hide=WALL,A-DOOR');
  assert.equal(d.layout, 3); assert.deepEqual(d.z, [1, 2, 3, 4]); assert.deepEqual(d.hide, ['WALL', 'A-DOOR']);
  assert.deepEqual(d.vpFrozen, {}); assert.deepEqual(d.anno, {});
});
test('defaults', () => {
  const d = LS.decode('');
  assert.deepEqual(d, { layout: null, z: null, hide: [], vpFrozen: {}, anno: {} });
});
test('layer names with commas and percents round trip', () => {
  const s = { layout: 1, hide: ['A,B', '50%', 'x%2Cy', 'quote"s', 'ünï cödé 図面', 'plain'], vpFrozen: { '1:F0D3': ['L,1', 'L2'] }, anno: { '1:F0D3': 0.02 } };
  const d = LS.decode(LS.encode(s));
  assert.deepEqual(d.hide, s.hide); assert.deepEqual(d.vpFrozen, s.vpFrozen); assert.deepEqual(d.anno, s.anno); assert.equal(d.layout, 1);
});
test('empty freeze lists are dropped', () => {
  assert.equal(LS.encode({ vpFrozen: { '1:A': [] } }), '');
  assert.equal(LS.encode({ anno: {} }), '');
});
test('tolerant decoding', () => {
  assert.equal(LS.decode('z=1,2,3').z, null);
  assert.equal(LS.decode('z=1,2,x,4').z, null);
  assert.equal(LS.decode('l=abc').layout, null);
  assert.equal(LS.decode('l=2.5').layout, null);
  assert.deepEqual(LS.decode('vf=%7Bnot json').vpFrozen, {});
  assert.deepEqual(LS.decode('vf=' + encodeURIComponent(JSON.stringify({ a: ['x'], b: 'no', c: [1] }))).vpFrozen, { a: ['x'] });
  assert.deepEqual(LS.decode('an=' + encodeURIComponent(JSON.stringify({ a: 0.5, b: -1, c: 'x', d: 0 }))).anno, { a: 0.5 });
});
test('leading question mark optional', () => {
  assert.deepEqual(LS.decode('?l=4'), LS.decode('l=4'));
});
