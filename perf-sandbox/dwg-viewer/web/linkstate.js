/* Pure serialization of the viewer's shareable state. */
var LinkState = (function () {
  'use strict';

  function encode(state) {
    state = state || {};
    var params = new URLSearchParams();
    if (state.layout !== undefined && state.layout !== null) {
      params.set('l', state.layout);
    }
    if (state.z != null) {
      params.set('z', state.z.map(function (v) {
        return Number(v.toPrecision(10));
      }).join(','));
    }
    if (state.hide && state.hide.length) {
      params.set('hide', state.hide.map(function (name) {
        return name.replace(/%/g, '%25').replace(/,/g, '%2C');
      }).join(','));
    }
    var frozen = Object.fromEntries(Object.entries(state.vpFrozen || {})
      .filter(function (entry) { return entry[1].length > 0; }));
    if (Object.keys(frozen).length) params.set('vf', JSON.stringify(frozen));
    if (state.anno && Object.keys(state.anno).length) {
      params.set('an', JSON.stringify(state.anno));
    }
    return params.toString();
  }

  function readMap(text, valid) {
    try {
      var value = JSON.parse(text);
      if (value === null || typeof value !== 'object' || Array.isArray(value)) {
        return {};
      }
      return Object.fromEntries(Object.entries(value).filter(function (entry) {
        return valid(entry[1]);
      }));
    } catch (error) {
      return {};
    }
  }

  function decode(search) {
    var params = new URLSearchParams(search);
    var layoutText = params.get('l');
    var layout = layoutText !== null && layoutText.trim() !== ''
      ? Number(layoutText) : NaN;
    var z = null;
    if (params.has('z')) {
      var parts = params.get('z').split(',');
      var numbers = parts.map(Number);
      if (parts.length === 4 && parts.every(function (part) {
        return part.trim() !== '';
      }) && numbers.every(Number.isFinite)) {
        z = numbers;
      }
    }
    return {
      layout: Number.isInteger(layout) ? layout : null,
      z: z,
      hide: params.has('hide') ? params.get('hide').split(',').map(function (name) {
        // One pass preserves literal escape-looking text such as "%2C".
        return name.replace(/%2C|%25/gi, function (escape) {
          return escape.toUpperCase() === '%2C' ? ',' : '%';
        });
      }) : [],
      vpFrozen: readMap(params.get('vf'), function (value) {
        return Array.isArray(value) && value.every(function (name) {
          return typeof name === 'string';
        });
      }),
      anno: readMap(params.get('an'), function (value) {
        return typeof value === 'number' && Number.isFinite(value) && value > 0;
      })
    };
  }

  return { encode: encode, decode: decode };
}());

if (typeof module !== 'undefined') {
  module.exports = LinkState;
}
