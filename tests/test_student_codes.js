const assert = require('node:assert/strict');
const { webcrypto } = require('node:crypto');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const template = readFileSync(resolve(__dirname,
    '../my_flask_app/app/templates/students.html'), 'utf8');
const script = template.match(/<script>([\s\S]*?)<\/script>/)[1];

function loadGenerator(crypto) {
    const input = { value: 'existing-form-value' };
    const math = Object.create(Math);
    math.random = () => { throw new Error('Math.random must not generate access codes'); };
    const context = vm.createContext({
        crypto, Math: math,
        document: { getElementById(id) { assert.equal(id, 'token'); return input; } },
    });
    vm.runInContext(script, context);
    return { input, generate: () => context.generateToken() };
}

test('eight secure random bytes become sixteen zero-padded hexadecimal characters', () => {
    let calls = 0;
    const { input, generate } = loadGenerator({ getRandomValues(bytes) {
        calls++;
        assert.equal(bytes.constructor.name, 'Uint8Array');
        assert.equal(bytes.byteLength, 8);
        bytes.set([0, 1, 15, 16, 127, 128, 254, 255]);
        return bytes;
    } });
    generate();
    assert.equal(input.value, '00010f107f80feff');
    assert.equal(calls, 1);
});

test('each button action requests fresh random bytes and updates only the form field', () => {
    const arrays = [];
    const { input, generate } = loadGenerator({ getRandomValues(bytes) {
        arrays.push(bytes);
        bytes.fill(arrays.length);
        return bytes;
    } });
    generate();
    assert.equal(input.value, '0101010101010101');
    generate();
    assert.equal(input.value, '0202020202020202');
    assert.equal(arrays.length, 2);
    assert.notEqual(arrays[0], arrays[1]);
});

test('generator works with the real Web Crypto implementation', () => {
    const { input, generate } = loadGenerator(webcrypto);
    generate();
    assert.match(input.value, /^[0-9a-f]{16}$/);
});

test('secure random failure leaves the field intact without an insecure fallback', () => {
    const { input, generate } = loadGenerator({ getRandomValues() {
        throw new Error('Test-only random source failure');
    } });
    assert.throws(generate, /Test-only random source failure/);
    assert.equal(input.value, 'existing-form-value');
});
