const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const loaderPath = path.resolve(
  __dirname,
  '../../../deploy/openwebui-static/loader.js'
);
const loaderSource = fs.readFileSync(loaderPath, 'utf8');

function loaderRuntime(pathname) {
  const calls = [];
  const originalFetch = async (input, init) => {
    calls.push({ input, init });
    return new Response('{}', {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };
  const window = {
    __stage2SttFetchPatched: false,
    crypto: { randomUUID: () => '00000000-0000-4000-8000-000000000000' },
    fetch: originalFetch,
    location: {
      origin: 'https://openwebui.test',
      pathname,
    },
    requestAnimationFrame: () => 0,
    sessionStorage: {
      getItem: () => null,
      key: () => null,
      length: 0,
      removeItem: () => {},
      setItem: () => {},
    },
    localStorage: {
      getItem: () => null,
      key: () => null,
      length: 0,
      removeItem: () => {},
      setItem: () => {},
    },
  };
  const document = {
    addEventListener: () => {},
    readyState: 'loading',
  };
  const context = {
    Blob,
    File: class File {},
    FormData,
    Headers,
    InputEvent: class InputEvent {},
    MutationObserver: class MutationObserver {},
    Request,
    Response,
    URL,
    clearTimeout,
    console,
    document,
    navigator: {},
    setTimeout,
    window,
  };
  Object.defineProperty(context, 'fetch', {
    configurable: true,
    get: () => window.fetch,
    set: (value) => {
      window.fetch = value;
    },
  });
  vm.runInNewContext(loaderSource, context, { filename: loaderPath });
  return { calls, window };
}

function completionCall(calls) {
  return calls.find(({ input }) =>
    String(input && input.url ? input.url : input).includes('/api/chat/completions')
  );
}

test('Gate 2 completion is bound to the active persistent chat', async () => {
  const activeChatId = '11111111-2222-4333-8444-555555555555';
  const { calls, window } = loaderRuntime(`/c/${activeChatId}`);

  await window.fetch('/api/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'broker_reports_gate2_source_fact_pipe',
      chat_id: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
      metadata: {
        chat_id: 'aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee',
        retained: true,
      },
      user_message: { content: 'safe test prompt' },
    }),
  });

  const call = completionCall(calls);
  assert.ok(call);
  const body = JSON.parse(call.init.body);
  assert.equal(body.chat_id, activeChatId);
  assert.equal(body.metadata.chat_id, activeChatId);
  assert.equal(body.metadata.retained, true);
  assert.equal(body.model, 'broker_reports_gate2_source_fact_pipe');
});

test('Gate 2 domain completion is bound to the active persistent chat', async () => {
  const activeChatId = '11111111-2222-4333-8444-555555555555';
  const { calls, window } = loaderRuntime(`/c/${activeChatId}`);

  await window.fetch('/api/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: 'broker_reports_gate2_domain_source_fact_pipe',
      user_message: { content: 'safe test prompt' },
    }),
  });

  const call = completionCall(calls);
  assert.ok(call);
  const body = JSON.parse(call.init.body);
  assert.equal(body.chat_id, activeChatId);
  assert.equal(body.metadata.chat_id, activeChatId);
  assert.equal(body.model, 'broker_reports_gate2_domain_source_fact_pipe');
});

test('non-Gate 2 completion remains unchanged', async () => {
  const { calls, window } = loaderRuntime(
    '/c/11111111-2222-4333-8444-555555555555'
  );
  const original = {
    model: 'broker_reports_gate1_pipe',
    user_message: { content: 'safe test prompt' },
  };

  await window.fetch('/api/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(original),
  });

  const call = completionCall(calls);
  assert.ok(call);
  assert.deepEqual(JSON.parse(call.init.body), original);
});

test('Gate 2 completion without a persistent chat remains fail closed', async () => {
  const { calls, window } = loaderRuntime('/');
  const original = {
    model: 'broker_reports_gate2_source_fact_pipe',
    user_message: { content: 'safe test prompt' },
  };

  await window.fetch('/api/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(original),
  });

  const call = completionCall(calls);
  assert.ok(call);
  assert.deepEqual(JSON.parse(call.init.body), original);
});

test('Gate 2 Request input preserves request transport while binding chat', async () => {
  const activeChatId = '11111111-2222-4333-8444-555555555555';
  const { calls, window } = loaderRuntime(`/c/${activeChatId}`);
  const request = new Request(
    'https://openwebui.test/api/chat/completions',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'broker_reports_gate2_source_fact_pipe',
        user_message: { content: 'safe test prompt' },
      }),
    }
  );

  await window.fetch(request);

  const call = completionCall(calls);
  assert.ok(call);
  assert.ok(call.input instanceof Request);
  const body = await call.input.clone().json();
  assert.equal(body.chat_id, activeChatId);
  assert.equal(body.metadata.chat_id, activeChatId);
});
