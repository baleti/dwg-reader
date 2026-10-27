'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Only event registration runs at load time. Do not execute browser callbacks
// or stub globals that are referenced solely inside those callbacks.
const ctx = vm.createContext({
  cv: { addEventListener() {} },
  document: { addEventListener() {} },
  addEventListener() {},
});
const filename = path.resolve(__dirname, '../../web/select.js');
vm.runInContext(fs.readFileSync(filename, 'utf8'), ctx, { filename });
const { applyM, pointInPoly, bbIn, bbHit, xformBB, segHitsRect, rowTouches, segDist } =
  vm.runInContext('({ applyM, pointInPoly, bbIn, bbHit, xformBB, segHitsRect, rowTouches, segDist })', ctx);

// Convert VM arrays to this realm before strict comparison.
const assertArray = (actual, expected) => assert.deepEqual(Array.from(actual), expected);
const R = [0, 0, 10, 10];
const square = [0, 0, 10, 0, 10, 10, 0, 10];
const line = flat => ['l', 0, null, null, null, flat];

test('applyM: identity', () => {
  assertArray(applyM([1, 0, 0, 1, 0, 0], 3, -2), [3, -2]);
});
test('applyM: all six affine coefficients use the browser matrix order', () => {
  assertArray(applyM([2, 3, 4, 5, 6, 7], 8, 9), [58, 76]);
});
test('applyM: 90 degree rotation', () => {
  assertArray(applyM([0, 1, -1, 0, 0, 0], 3, 2), [-2, 3]);
});
test('applyM: nonuniform scaling, reflection and translation', () => {
  assertArray(applyM([-2, 0, 0, 3, 5, -1], 4, 2), [-3, 5]);
});
test('xformBB: 90 degree rotation reorders the extrema', () => {
  assertArray(xformBB([0, 1, -1, 0, 0, 0], [1, 2, 4, 6]), [-6, 1, -2, 4]);
});
test('xformBB: negative and nonuniform scaling with translation', () => {
  assertArray(xformBB([-2, 0, 0, 3, 5, -1], [1, 2, 4, 6]), [-3, 5, 3, 17]);
});
test('xformBB: shear requires extrema from all four corners', () => {
  assertArray(xformBB([1, 1, -1, 1, 0, 0], [1, 2, 4, 6]), [-5, 3, 2, 10]);
});

test('pointInPoly: convex polygon in a flat coordinate array', () => {
  assert.equal(pointInPoly(5, 5, square), true);
  assert.equal(pointInPoly(11, 5, square), false);
  assert.equal(pointInPoly(-1, 5, square), false);
});
test('pointInPoly: concave polygon includes both arms but excludes its notch', () => {
  const concave = [0, 0, 6, 0, 6, 2, 2, 2, 2, 6, 0, 6];
  assert.equal(pointInPoly(5, 1, concave), true);
  assert.equal(pointInPoly(1, 5, concave), true);
  assert.equal(pointInPoly(4, 4, concave), false);
});
test('pointInPoly: reversed winding and explicitly closed flat array', () => {
  assert.equal(pointInPoly(5, 5, [0, 10, 10, 10, 10, 0, 0, 0]), true);
  assert.equal(pointInPoly(5, 5, [...square, 0, 0]), true);
  assert.equal(pointInPoly(11, 5, [...square, 0, 0]), false);
});
test('pointInPoly boundary behavior: left/bottom edges included, right/top excluded', () => {
  for (const [x, y, expected] of [
    [0, 5, true], [5, 0, true], [10, 5, false], [5, 10, false],
    [0, 0, true], [10, 0, false], [10, 10, false], [0, 10, false],
  ]) {
    assert.equal(pointInPoly(x, y, square), expected, `boundary (${x}, ${y})`);
  }
});
test('pointInPoly: empty flat array has no interior', () => {
  assert.equal(pointInPoly(0, 0, []), false);
});

test('bbIn: contained, equal and edge-touching boxes are included', () => {
  for (const b of [[2, 3, 8, 9], R, [0, 2, 4, 10], [10, 10, 10, 10]]) {
    assert.equal(bbIn(b, R), true);
  }
});
test('bbIn: protruding beyond any side fails containment', () => {
  for (const b of [[-1, 2, 3, 4], [2, -1, 3, 4], [2, 3, 11, 4], [2, 3, 4, 11]]) {
    assert.equal(bbIn(b, R), false);
  }
  assert.equal(bbIn([-1, -1, 11, 11], R), false);
});
test('bbHit: overlapping and containing boxes intersect symmetrically', () => {
  for (const b of [[2, 2, 8, 8], [-1, -1, 11, 11], [8, 8, 12, 12], R]) {
    assert.equal(bbHit(b, R), true);
    assert.equal(bbHit(R, b), true);
  }
});
test('bbHit: touching edges and corners count as overlap', () => {
  for (const b of [[10, 2, 12, 8], [-2, 2, 0, 8], [2, 10, 8, 12], [2, -2, 8, 0], [10, 10, 12, 12]]) {
    assert.equal(bbHit(b, R), true);
  }
});
test('bbHit: separated boxes on every side do not overlap', () => {
  for (const b of [[11, 2, 12, 8], [-2, 2, -1, 8], [2, 11, 8, 12], [2, -2, 8, -1]]) {
    assert.equal(bbHit(b, R), false);
    assert.equal(bbHit(R, b), false);
  }
});

for (const [name, coords, expected] of [
  ['inside', [2, 3, 8, 9], true],
  ['diagonal crossing with both endpoints outside', [-5, -5, 15, 15], true],
  ['outside despite overlapping bounding boxes', [-2, 9, 9, 20], false],
  ['touching just a corner', [-2, 2, 2, -2], true],
  ['vertical crossing', [5, -2, 5, 12], true],
  ['vertical outside', [-1, -2, -1, 12], false],
  ['horizontal crossing', [-2, 5, 12, 5], true],
  ['horizontal outside', [-2, 11, 12, 11], false],
  ['along an edge', [-2, 0, 12, 0], true],
  ['ending on an edge', [-2, 5, 0, 5], true],
  ['degenerate inside', [5, 5, 5, 5], true],
  ['degenerate on a corner', [10, 10, 10, 10], true],
  ['degenerate outside', [11, 5, 11, 5], false],
]) {
  test(`segHitsRect: ${name} (both endpoint orders)`, () => {
    assert.equal(segHitsRect(...coords, R), expected);
    assert.equal(segHitsRect(coords[2], coords[3], coords[0], coords[1], R), expected);
  });
}

test('rowTouches: line coordinates are at index 5 and crossing counts', () => {
  assert.equal(rowTouches(line([-2, 5, 12, 5]), null, R), true);
});
test('rowTouches: checks later segments of an open polyline', () => {
  assert.equal(rowTouches(line([-5, -5, -5, 5, 5, 5]), null, R), true);
});
test('rowTouches: bbox overlap alone does not imply a segment hit', () => {
  assert.equal(rowTouches(line([-2, 9, 9, 20]), null, R), false);
});
test('rowTouches: does not implicitly close a line row', () => {
  assert.equal(rowTouches(line([-5, 5, -5, 15, 15, 15]), null, R), false);
});
test('rowTouches: translation can move a line into or out of the rectangle', () => {
  const row = line([-5, 2, -5, 8]);
  assert.equal(rowTouches(row, null, R), false);
  assert.equal(rowTouches(row, [1, 0, 0, 1, 10, 0], R), true);
  assert.equal(rowTouches(line([5, 2, 5, 8]), [1, 0, 0, 1, 10, 0], R), false);
});
test('rowTouches: rotation and scaling transform both endpoints', () => {
  assert.equal(rowTouches(line([1, -3, 4, -3]), [0, 2, -2, 0, 0, 0], R), true);
  assert.equal(rowTouches(line([1, -6, 4, -6]), [0, 2, -2, 0, 0, 0], R), false);
});
test('rowTouches: empty and single-point rows have no segments, even with a matrix', () => {
  for (const flat of [[], [5, 5]]) {
    for (const matrix of [null, [1, 0, 0, 1, 0, 0]]) {
      assert.equal(rowTouches(line(flat), matrix, R), false);
    }
  }
});
test('rowTouches: repeated coordinates form a degenerate segment that can hit', () => {
  assert.equal(rowTouches(line([5, 5, 5, 5]), null, R), true);
  assert.equal(rowTouches(line([11, 5, 11, 5]), null, R), false);
});

for (const [name, coords, expected] of [
  ['perpendicular projection inside horizontal segment', [4, 3, 0, 0, 10, 0], 3],
  ['perpendicular projection inside vertical segment', [3, 4, 0, 0, 0, 10], 3],
  ['projection before first endpoint', [-3, 4, 0, 0, 10, 0], 5],
  ['projection beyond last endpoint', [13, 4, 0, 0, 10, 0], 5],
  ['point on segment', [4, 0, 0, 0, 10, 0], 0],
  ['point at endpoint', [10, 0, 0, 0, 10, 0], 0],
  ['diagonal segment', [0, 2, 0, 0, 2, 2], Math.SQRT2],
  ['degenerate segment', [4, 6, 1, 2, 1, 2], 5],
  ['point coincides with degenerate segment', [1, 2, 1, 2, 1, 2], 0],
]) {
  test(`segDist: ${name}`, () => {
    assert.ok(Math.abs(segDist(...coords) - expected) < 1e-12);
    const [px, py, ax, ay, bx, by] = coords;
    assert.ok(Math.abs(segDist(px, py, bx, by, ax, ay) - expected) < 1e-12);
  });
}
