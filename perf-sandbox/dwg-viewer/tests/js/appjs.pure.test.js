'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const filename = path.resolve(__dirname, '../../web/app.js');
const source = fs.readFileSync(filename, 'utf8');

// Let the JS parser find the balanced function/statement end. Incomplete
// candidates (including braces or semicolons in strings) cannot compile.
// Compilation never executes the browser script or the extracted declaration.
function extract(name, kind = 'function') {
  const start = source.search(new RegExp(`^${kind} ${name}${kind === 'function' ? '\\(' : ' = '}`, 'm'));
  assert.notEqual(start, -1, `missing ${kind} ${name}`);
  const endChar = kind === 'function' ? '}' : ';';
  for (let end = source.indexOf(endChar, start); end !== -1; end = source.indexOf(endChar, end + 1)) {
    const declaration = source.slice(start, end + 1);
    try {
      new Function(`${declaration}\nreturn ${name};`);
      return declaration;
    } catch (error) {
      if (!(error instanceof SyntaxError)) throw error;
    }
  }
  assert.fail(`unterminated ${kind} ${name}`);
}

const names = ['fontCss', 'fontFlags', 'isShx', 'shxK', 'plainText', 'parseMtext',
  'dashArr', 'numMap', 'pointInPoly', 'css', 'modelBBox'];
function sandbox() {
  const ctx = vm.createContext({ CTB: null, colCache: new Map() });
  const declarations = ['ACI', 'FONT', 'FONTK'].map(name => extract(name, 'const'));
  vm.runInContext([...declarations, ...names.map(name => extract(name))].join('\n'), ctx, { filename });
  return { ctx, ...vm.runInContext(`({${names.join(',')}, ACI, FONT})`, ctx) };
}
const helpers = sandbox();
const { fontCss, fontFlags, isShx, shxK, plainText, parseMtext, dashArr,
  numMap, pointInPoly, modelBBox } = helpers;
// Normalize VM objects, while checking paragraph metadata separately below.
const local = value => JSON.parse(JSON.stringify(value));
const run = (t, extra = {}) => ({ t, h: 1, b: 0, i: 0, u: 0, o: 0, col: null, w: 1, ...extra });

test('fontCss: rounds size and uses the source font fallback list', () => {
  assert.equal(fontCss(12.345, false, false), `12.35px ${helpers.FONT}`);
  assert.equal(fontCss(10, true, true), `italic bold 10.00px ${helpers.FONT}`);
});
for (const [name, flags] of [[null, [0, 0]], ['Arial.TTF', [0, 0]],
  ['ARIALBD.ttf', [1, 0]], ['calibriz.otf', [1, 1]], ['TimesI.ttc', [0, 1]],
  ['Example Black', [1, 0]]]) {
  test(`fontFlags: ${name}`, () => assert.deepEqual(local(fontFlags(name)), flags));
}
test('isShx: suffixes and built-in names are case insensitive', () => {
  for (const name of ['custom.SHX', 'ROMANS', 'simplex', 'txt']) assert.equal(isShx(name), true);
  for (const name of [null, '', 'Arial.ttf', 'romans.ttf', 'custom']) assert.equal(isShx(name), false);
});
test('shxK: normalizes known extensions and defaults to one', () => {
  assert.equal(shxK('ROMANS.SHX'), 1.1);
  assert.equal(shxK('Calibri.TTF'), 0.936);
  assert.equal(shxK('tahomabd.otf'), 0.92);
  assert.equal(shxK('unknown'), 1);
  assert.equal(shxK(null), 1);
});
test('plainText: replaces CAD symbols and removes underline/overline toggles', () => {
  assert.equal(plainText('%%c %%C %%d %%D %%p %%P %%uA%%U %%oB%%O'), 'Ø Ø ° ° ± ± A B');
});
test('plainText: numeric escapes consume up to three digits and coerce input', () => {
  assert.equal(plainText('%%65 %%065 %%1234 %%q'), 'A A {4 %%q');
  assert.equal(plainText(null), 'null');
});
test('parseMtext: plain text and empty input', () => {
  assert.deepEqual(local(parseMtext('hello %%d')), [[run('hello °')]]);
  assert.deepEqual(local(parseMtext('')), [[]]);
  assert.equal(parseMtext('hello')[0].al, 'l');
});
test('parseMtext: paragraph breaks preserve empty paragraphs', () => {
  const lines = parseMtext(String.raw`one\P\Ptwo\Xthree`);
  assert.deepEqual(local(lines), [[run('one')], [], [run('two')], [run('three')]]);
  assert.equal(lines[1].al, 'l');
  assert.equal(lines[1].ex, false);
});
test('parseMtext: font style groups restore the surrounding state', () => {
  assert.deepEqual(local(parseMtext(String.raw`a{\fArial|b1;bold}z`)),
    [[run('a'), run('bold', { font: 'Arial', b: 1 }), run('z')]]);
});
test('parseMtext: nested styles and b0 retain current bold until group closes', () => {
  assert.deepEqual(local(parseMtext(String.raw`{\fArial|b1;a{\fOther|b0|i1;b}c}d`)),
    [[run('a', { font: 'Arial', b: 1 }), run('b', { font: 'Other', b: 1, i: 1 }),
      run('c', { font: 'Arial', b: 1 }), run('d')]]);
});
test('parseMtext: indexed and packed RGB colours', () => {
  assert.deepEqual(local(parseMtext(String.raw`\C3;green{\c197121;rgb}back`)),
    [[run('green', { col: 3 }), run('rgb', { col: [1, 2, 3] }), run('back', { col: 3 })]]);
});
test('parseMtext: relative heights replace rather than multiply; absolute heights retained', () => {
  assert.deepEqual(local(parseMtext(String.raw`\H2x;a\H3x;b\H4;c`)),
    [[run('a', { h: 2, hAbs: 0 }), run('b', { h: 3, hAbs: 0 }), run('c', { h: 4, hAbs: 4 })]]);
});
for (const separator of ['/', '#', '^']) {
  test(`parseMtext: stacked fraction ${separator}`, () => {
    assert.deepEqual(local(parseMtext(`\\S%%65${separator}2;`)),
      [[run('', { stack: ['A', '2'], sl: separator })]]);
  });
}
test('parseMtext: stack without separator has an empty denominator', () => {
  assert.deepEqual(local(parseMtext(String.raw`\Sabc;`)), [[run('', { stack: ['abc', ''], sl: '/' })]]);
});
test('parseMtext: unicode escapes consume four hexadecimal digits', () => {
  assert.deepEqual(local(parseMtext(String.raw`\U+0041\U+03A9!`)), [[run('AΩ!')]]);
});
test('parseMtext: unbalanced opening and closing braces are tolerated', () => {
  assert.deepEqual(local(parseMtext(String.raw`{\fArial|b1;open`)), [[run('open', { font: 'Arial', b: 1 })]]);
  assert.deepEqual(local(parseMtext('a}b}}c')), [[run('a'), run('b'), run('c')]]);
});
test('parseMtext: escaped braces, backslash and nonbreaking space', () => {
  assert.deepEqual(local(parseMtext(String.raw`\{x\}\\\~y`)), [[run('{x}\\\u00a0y')]]);
});
test('dashArr: absent and empty patterns', () => {
  assert.equal(dashArr(null), null);
  assert.deepEqual(local(dashArr([])), { a: [], period: 0 });
});
test('dashArr: merges equal signs, pads leading gaps and trailing strokes', () => {
  assert.deepEqual(local(dashArr([-2, -3, 4, 1])), { a: [0, 5, 5, 0], period: 10 });
  assert.deepEqual(local(dashArr([2, -1, 3, -4])), { a: [2, 1, 3, 4], period: 10 });
});
test('dashArr: dots use total length with a minimum length', () => {
  assert.deepEqual(local(dashArr([0, -10])), { a: [0.03, 10], period: 10 });
  assert.deepEqual(local(dashArr([0])), { a: [1e-9, 0], period: 0 });
});
test('dashArr: caches the result on the input array', () => {
  const pattern = [2, -1];
  const result = dashArr(pattern);
  assert.equal(pattern._c, result);
  assert.equal(dashArr(pattern), result);
});
test('numMap: converts keys to numbers and preserves values', () => {
  const value = { synthetic: true };
  const result = numMap({ '2': value, '-1.5': 'fraction', invalid: 'nan' });
  assert.equal(result.size, 3);
  assert.equal(result.get(2), value);
  assert.equal(result.get(-1.5), 'fraction');
  assert.equal(result.get(NaN), 'nan');
  assert.equal(numMap({}).size, 0);
});
test('pointInPoly: inside, outside and empty polygon', () => {
  const square = [0, 0, 10, 0, 10, 10, 0, 10];
  assert.equal(pointInPoly(5, 5, square), true);
  assert.equal(pointInPoly(11, 5, square), false);
  assert.equal(pointInPoly(0, 0, []), false);
});
test('pointInPoly: concave arms and notch, in either winding', () => {
  for (const polygon of [[0, 0, 6, 0, 6, 2, 2, 2, 2, 6, 0, 6],
    [0, 6, 2, 6, 2, 2, 6, 2, 6, 0, 0, 0]]) {
    assert.equal(pointInPoly(5, 1, polygon), true);
    assert.equal(pointInPoly(1, 5, polygon), true);
    assert.equal(pointInPoly(4, 4, polygon), false);
    assert.equal(pointInPoly(2, 4, polygon), false);
    assert.equal(pointInPoly(0, 4, polygon), true);
  }
});
test('ACI: primary colours, generated shades and grayscale endpoints', () => {
  for (const [index, expected] of [[1, [255, 0, 0]], [5, [0, 0, 255]],
    [10, [255, 0, 0]], [11, [255, 128, 128]], [250, [51, 51, 51]], [255, [255, 255, 255]]]) {
    assert.deepEqual(local(helpers.ACI[index]), expected);
  }
});
test('css: ACI, explicit RGB and unknown colour fallback', () => {
  const { css } = sandbox();
  assert.equal(css(3, false), 'rgb(0,255,0)');
  assert.equal(css([12, 34, 56], true), 'rgb(12,34,56)');
  assert.equal(css(999, true), 'rgb(0,0,0)');
});
test('css: index seven flips with background even after caching', () => {
  const { css } = sandbox();
  for (const dark of [false, true, false, true]) {
    assert.equal(css(7, dark), dark ? 'rgb(255,255,255)' : 'rgb(0,0,0)');
    assert.equal(css([255, 255, 255], dark), 'rgb(255,255,255)');
    assert.equal(css(0, dark), 'rgb(0,0,0)');
  }
});
test('css: CTB overrides indexed colour and monochrome truecolour', () => {
  const { ctx, css } = sandbox();
  css(7, true);
  ctx.CTB = { 7: [[10, 20, 30]], mono: true };
  assert.equal(css(7, true), 'rgb(10,20,30)');
  assert.equal(css([50, 60, 70], true), '#000');
  assert.equal(css(1, false), 'rgb(255,0,0)');
});
test('modelBBox: identity and inverse translation/scaling', () => {
  assert.deepEqual(local(modelBBox({ m: [1, 0, 0, 1, 0, 0] }, [1, 2, 4, 6])), [1, 2, 4, 6]);
  assert.deepEqual(local(modelBBox({ m: [2, 0, 0, 3, 10, -6] }, [12, 0, 18, 12])), [1, 2, 4, 6]);
});
test('modelBBox: rotation, reflection and shear reorder corner extrema', () => {
  assert.deepEqual(local(modelBBox({ m: [0, 1, -1, 0, 0, 0] }, [-6, 1, -2, 4])), [1, 2, 4, 6]);
  assert.deepEqual(local(modelBBox({ m: [-1, 0, 0, 1, 0, 0] }, [1, 2, 4, 6])), [-4, 2, -1, 6]);
  assert.deepEqual(local(modelBBox({ m: [1, 0, 1, 1, 0, 0] }, [0, 0, 4, 2])), [-2, 0, 4, 2]);
});
