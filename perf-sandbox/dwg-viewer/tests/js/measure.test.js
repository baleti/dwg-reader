const test = require('node:test');
const assert = require('node:assert/strict');
const M = require('../../web/measure.js');
const close = (a, b, e = 1e-9) => assert.ok(Math.abs(a - b) < e, a + ' vs ' + b);

test('dist and pathLength', () => {
  close(M.dist([0, 0], [3, 4]), 5);
  close(M.pathLength([[0, 0], [3, 4], [3, 10]]), 11);
  close(M.pathLength([[0, 0], [4, 0], [4, 3]], true), 12);
  assert.equal(M.pathLength([[1, 1]]), 0);
  assert.equal(M.pathLength([]), 0);
});

test('areas and centroid', () => {
  const sq = [[0, 0], [4, 0], [4, 3], [0, 3]];
  close(M.polyArea(sq), 12); close(M.signedArea(sq), 12); close(M.signedArea(sq.slice().reverse()), -12);
  close(M.polyArea(sq.slice().reverse()), 12);
  assert.equal(M.polyArea([[0, 0], [1, 1]]), 0);
  assert.deepEqual(M.centroid(sq).map(v => +v.toFixed(9)), [2, 1.5]);
  assert.deepEqual(M.centroid([[0, 0], [2, 2], [4, 4]]), [2, 2]);
  assert.equal(M.centroid([]), null);
});

test('angles and bearings', () => {
  close(M.angleDeg([1, 0], [0, 0], [0, 1]), 90);
  close(M.angleDeg([1, 0], [0, 0], [-1, 0]), 180);
  close(M.angleDeg([1, 0], [0, 0], [1, 0]), 0);
  assert.equal(M.angleDeg([0, 0], [0, 0], [1, 0]), 0);
  close(M.bearingDeg([0, 0], [1, 0]), 0);
  close(M.bearingDeg([0, 0], [0, 1]), 90);
  close(M.bearingDeg([0, 0], [-1, 0]), 180);
  close(M.bearingDeg([0, 0], [0, -1]), 270);
  assert.equal(M.bearingDeg([2, 2], [2, 2]), 0);
});

test('fmtLength', () => {
  assert.equal(M.fmtLength(12.5, 'mm'), '12.5 mm');
  assert.equal(M.fmtLength(1234, 'mm'), '1.234 m');
  assert.equal(M.fmtLength(12.5, 'cm'), '12.50 cm');
  assert.equal(M.fmtLength(1.23456, 'm'), '1.235 m');
  assert.equal(M.fmtLength(3.5, 'in'), '3.50 in');
  assert.equal(M.fmtLength(40.5, 'ft'), '40\'-6.00"');
  assert.equal(M.fmtLength(-3.375, 'ft'), '-3\'-4.50"');
  assert.equal(M.fmtLength(2.99999, 'ft'), '3\'-0.00"');
  assert.equal(M.fmtLength(-1.5, 'mm'), '-1.5 mm');
  assert.equal(M.fmtLength(1.25, undefined), '1.25');
  assert.equal(M.fmtLength(2, 'zz'), '2');
  assert.equal(M.fmtLength(NaN, 'mm'), '');
  assert.equal(M.fmtLength(undefined, 'm'), '');
});

test('fmtArea', () => {
  assert.equal(M.fmtArea(500, 'mm'), '500 mm2');
  assert.equal(M.fmtArea(12500000, 'mm'), '12.50 m2');
  assert.equal(M.fmtArea(12.5, 'm'), '12.50 m2');
  assert.equal(M.fmtArea(7.5, undefined), '7.5');
  assert.equal(M.fmtArea(NaN, 'm'), '');
});

test('NaN input never throws', () => {
  assert.ok(Number.isNaN(M.dist([NaN, 0], [1, 1])));
  assert.ok(Number.isNaN(M.polyArea([[NaN, 0], [1, 1], [2, 0]])));
  assert.doesNotThrow(() => M.centroid(undefined));
});
