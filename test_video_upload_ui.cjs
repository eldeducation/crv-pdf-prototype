// Browser upload behavior with mock responses; no network or AI calls.
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const {test} = require('node:test');
const source = readFileSync(__dirname + '/ui.js', 'utf8');
const start = source.indexOf('async function uploadVideo(');
const end = source.indexOf("$('generate').onclick", start);
assert(start >= 0 && end > start);
const chunkSize = 8 * 1024 ** 2;
const maximum = 200 * 1024 ** 2;

function fixture(responder) {
  const calls = [];
  const upload = vm.runInNewContext('(' + source.slice(start, end) + ')', {
    crypto: webcrypto, Uint8Array, message() {}, tr: (ja, en) => en,
    fetch: async (url, options) => {
      calls.push({url, ...options});
      const received = Number(options.headers['X-Upload-Offset']) + options.body.size;
      return responder ? responder(calls.length, received) : {
        ok: true, status: 200,
        json: async () => ({received, complete: received === Number(options.headers['X-Upload-Size']),
                           upload_id: options.headers['X-Upload-ID']})
      };
    }
  });
  return {calls, upload};
}

function file(size) {
  return {name: 'sample.mp4', size, slice: (start, end) => ({size: end - start, start, end})};
}

test('200 MiB uses 25 sequential requests with consistent identity and CSRF', async () => {
  const {calls, upload} = fixture();
  const identity = await upload(file(maximum), 'csrf-fixture', true);
  assert.equal(calls.length, 25);
  assert.match(identity, /^[a-f0-9]{24}$/);
  calls.forEach((request, i) => {
    assert.equal(request.url, 'upload');
    assert.equal(request.headers['X-CSRF-Token'], 'csrf-fixture');
    assert.equal(request.headers['X-Upload-ID'], identity);
    assert.equal(Number(request.headers['X-Upload-Offset']), i * chunkSize);
    assert.equal(Number(request.headers['X-Upload-Size']), maximum);
    assert.equal(request.body.size, chunkSize);
  });
});

test('final partial chunk and small files are transmitted exactly', async () => {
  for (const size of [1, chunkSize + 123]) {
    const {calls, upload} = fixture();
    await upload(file(size), 'csrf', true);
    assert.equal(calls.reduce((sum, call) => sum + call.body.size, 0), size);
    assert.equal(calls.at(-1).body.end, size);
  }
});

test('empty and oversized shared files fail before any network call', async () => {
  const {calls, upload} = fixture();
  for (const size of [0, maximum + 1]) await assert.rejects(upload(file(size), 'csrf', true));
  assert.equal(calls.length, 0);
});

test('local mode retains the 1 GiB allowance', async () => {
  const {calls, upload} = fixture();
  await upload(file(1024 ** 3), 'csrf', false);
  assert.equal(calls.length, 128);
  await assert.rejects(upload(file(1024 ** 3 + 1), 'csrf', false));
  assert.equal(calls.length, 128);
});

test('HTTP errors and non-JSON responses stop further chunks', async () => {
  for (const response of [
    {ok: false, status: 413, json: async () => ({error: 'Upload refused'})},
    {ok: false, status: 502, json: async () => {throw Error('HTML response');}}
  ]) {
    const {calls, upload} = fixture(() => response);
    await assert.rejects(upload(file(maximum), 'csrf', true));
    assert.equal(calls.length, 1);
  }
});

test('incorrect acknowledgement never reports a successful upload', async () => {
  const {calls, upload} = fixture(() => ({ok: true, status: 200,
    json: async () => ({received: 1, complete: false})}));
  await assert.rejects(upload(file(maximum), 'csrf', true));
  assert.equal(calls.length, 1);
});
