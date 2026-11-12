// node vendor/deepmerge/test.cjs
const assert = require('node:assert/strict');
const merge = require('./cjs.js');

// normal behaviour
assert.deepEqual(merge({a: 1, n: {x: 1}}, {b: 2, n: {y: 2}}), {a: 1, b: 2, n: {x: 1, y: 2}});
assert.deepEqual(merge([1], [2]), [1, 2]);
assert.deepEqual(merge.all([{a: 1}, {b: 2}, {a: 3}]), {a: 3, b: 2});
assert.deepEqual(merge({plugins: ['a']}, {plugins: ['b']}), {plugins: ['a', 'b']});

// CVE-2026-93753: "__proto__" from JSON must not become the prototype
const evil = JSON.parse('{"__proto__": {"polluted": true}, "ok": 1}');
const out = merge({}, evil);
assert.equal(Object.getPrototypeOf(out), Object.prototype);
assert.equal(out.polluted, undefined);
assert.equal(out.ok, 1);
assert.equal({}.polluted, undefined);
const nested = merge({a: {}}, JSON.parse('{"a": {"__proto__": {"polluted": true}}}'));
assert.equal(nested.a.polluted, undefined);
assert.equal(Object.getPrototypeOf(nested.a), Object.prototype);
// the path upstream 4.3.1 actually gets wrong: "__proto__" on the *target*
const fromTarget = merge(JSON.parse('{"__proto__": {"polluted": true}}'), {b: 1});
assert.equal(fromTarget.polluted, undefined);
assert.equal(Object.getPrototypeOf(fromTarget), Object.prototype);
assert.equal(fromTarget.b, 1);
console.log('deepmerge vendor copy: all checks passed');
