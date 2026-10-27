const test = require('node:test');
const assert = require('node:assert/strict');
const S = require('../../web/snap.js');
const close = (a, b, e = 1e-9) => assert.ok(Math.abs(a - b) < e, a + ' vs ' + b);

test('segment intersection', () => {
  const p = S.snapSegIntersect(0, 0, 10, 10, 0, 10, 10, 0); close(p[0], 5); close(p[1], 5);
  assert.equal(S.snapSegIntersect(0, 0, 1, 0, 0, 1, 1, 1), null);
  assert.equal(S.snapSegIntersect(0, 0, 1, 0, 2, 0, 3, 0), null);
  assert.equal(S.snapSegIntersect(0, 0, 1, 1, 2, 2, 3, 3), null);
  assert.equal(S.snapSegIntersect(0, 0, 1, 0, 2, -1, 2, 1), null);
  const t = S.snapSegIntersect(0, 0, 4, 0, 4, 0, 4, 5); close(t[0], 4); close(t[1], 0);
});

test('nearest point on segment', () => {
  let r = S.snapNearestPointOnSegment(5, 3, 0, 0, 10, 0); close(r[0], 5); close(r[1], 0); close(r[2], 0.5);
  r = S.snapNearestPointOnSegment(-4, 3, 0, 0, 10, 0); close(r[0], 0); close(r[2], 0);
  r = S.snapNearestPointOnSegment(14, 3, 0, 0, 10, 0); close(r[0], 10); close(r[2], 1);
  r = S.snapNearestPointOnSegment(1, 1, 2, 2, 2, 2); close(r[0], 2); close(r[2], 0);
});

test('snapFind kinds and priority', () => {
  const polys = [[0, 0, 10, 0, 10, 10], [0, 10, 10, 0]];
  let r = S.snapFind(polys, 0.3, 0.2, 1);
  assert.deepEqual([r.kind, r.x, r.y], ['end', 0, 0]);
  r = S.snapFind([[0, 0, 10, 10], [0, 10, 10, 0]], 5.2, 4.9, 1);
  assert.equal(r.kind, 'int'); close(r.x, 5); close(r.y, 5);
  r = S.snapFind([[0, 0, 10, 0]], 4.8, 0.3, 1);
  assert.equal(r.kind, 'mid'); close(r.x, 5);
  r = S.snapFind([[0, 0, 10, 0]], 3, 0.2, 1);
  assert.equal(r, null);
  r = S.snapFind([[0, 0, 10, 0]], 3, 0.2, 1, ['near']);
  assert.equal(r.kind, 'near'); close(r.x, 3); close(r.y, 0);
  assert.equal(S.snapFind([], 0, 0, 5), null);
  assert.equal(S.snapFind([[0, 0, 1, 1]], 100, 100, 5), null);
});

test('self intersection of a bow tie and adjacent segments', () => {
  const bow = [[0, 0, 10, 10, 10, 0, 0, 10]];
  const r = S.snapFind(bow, 5.1, 5.1, 1, ['int']);
  assert.equal(r.kind, 'int'); close(r.x, 5); close(r.y, 5);
  const l = [[0, 0, 10, 0, 10, 10]];
  assert.equal(S.snapFind(l, 10.2, 0.1, 1, ['int']), null);
});

test('snapClosed', () => {
  assert.equal(S.snapClosed([0, 0, 1, 0, 1, 1, 0, 0]), true);
  assert.equal(S.snapClosed([0, 0, 1, 0, 1, 1]), false);
  assert.equal(S.snapClosed([1e6, 0, 5, 5, 1e6 + 1e-7, 0]), true);
});

test('performance on 5000 polylines', () => {
  const polys = [];
  let seed = 12345; const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
  for (let i = 0; i < 5000; i++) { const p = []; let x = rnd() * 1e6, y = rnd() * 1e6; for (let k = 0; k < 11; k++) { p.push(x, y); x += (rnd() - 0.5) * 200; y += (rnd() - 0.5) * 200; } polys.push(p); }
  const t = process.hrtime.bigint();
  for (let i = 0; i < 5; i++) S.snapFind(polys, polys[100 + i][0] + 1, polys[100 + i][1] + 1, 20);
  const ms = Number(process.hrtime.bigint() - t) / 1e6 / 5;
  assert.ok(ms < 50, 'too slow: ' + ms + ' ms per query');
});
