// Executes the pinned upstream handlers with host stubs; not full WebUI acceptance.
// Usage: node scripts/prove-goal584-rich-ui.cjs <Open-WebUI-v0.12.2-source-directory>
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');

const commit = '6a18585ff4c2e5f6805f682222cfbc46dc669ef8';
assert(process.argv[2], 'Supply the pinned upstream source directory.');
const hashes = {
  'src/lib/components/common/FullHeightIframe.svelte': '678b144db4ca8bac132f4475536382b16d11bde2398ac53c981fbea91d70b909',
  'src/lib/components/chat/Chat.svelte': '2864642959fd5f6ffbbbb390dc7e27a3cd401e611ac96265265c03e6228d222e',
};
function readPinned(file) {
  const source = fs.readFileSync(path.join(process.argv[2], file), 'utf8').replace(/\r\n/g, '\n');
  assert.equal(crypto.createHash('sha256').update(source).digest('hex'), hashes[file], `Unexpected source: ${file}`);
  return source;
}
const frameSource = readPinned('src/lib/components/common/FullHeightIframe.svelte');
const chatSource = readPinned('src/lib/components/chat/Chat.svelte');
function between(source, start, end) {
  const a = source.indexOf(start);
  const b = source.indexOf(end, a);
  assert(a >= 0 && b > a, 'Pinned handler boundaries missing.');
  return source.slice(a, b);
}
const frameHandler = between(frameSource, '\tfunction onMessage(', '\n\t// When the iframe loads')
  .replace('e: MessageEvent', 'e');
const chatHandler = between(chatSource, '\tconst onMessageHandler = async (event:', '\n\tconst stopAudio')
  .replace(/\(event: \{[\s\S]*?\n\t\}\)/, '(event)')
  .replaceAll('(confirmed: boolean)', '(confirmed)');
const calls = { replies: [], submitted: [], filled: [], fetched: [] };
const ownWindow = { postMessage: data => calls.replies.push(data) };
const ctx = {
  console: { log() {}, debug() {} },
  window: { origin: 'http://example.test' },
  iframe: { contentWindow: ownWindow, style: {} }, payload: null,
  isEmbedWindow: source => source === ownWindow,
  $settings: { iframeSandboxAllowSameOrigin: false },
  prompt: '', $i18n: { t: x => x },
  document: { getElementById: () => ({}) },
  messageInput: { setText: x => calls.filled.push(x), focus() {} },
  tick: async () => {}, submitHandler: x => calls.submitted.push(x),
  fetch: (...args) => calls.fetched.push(args),
};
vm.createContext(ctx);
vm.runInContext(`${frameHandler}\n${chatHandler}\nglobalThis.chatHandler=onMessageHandler;`, ctx);
const own = data => ({ origin: 'null', source: ownWindow, data });

(async () => {
  ctx.onMessage(own({ type: 'pong' }));
  ctx.onMessage(own({ type: 'payload', requestId: 'snapshot' }));
  ctx.onMessage(own({ type: 'iframe:height', height: 234 }));
  assert.equal(calls.replies[0].type, 'pong:ack');
  assert.equal(calls.replies[1].payload, null);
  assert.equal(ctx.iframe.style.height, '234px');
  for (const data of [
    { type: 'tools/call', name: 'get_budget' },
    { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'get_budget' } },
    { type: 'action', action_id: 'set_budget' },
    { type: 'execute', data: { code: 'fetch("/api/budget")' } },
    { type: 'payload', requestId: 'fresh-read', endpoint: '/api/budget' },
  ]) {
    ctx.onMessage(own(data));
    await ctx.chatHandler(own(data));
  }
  assert.equal(calls.fetched.length, 0);
  assert.equal(calls.submitted.length, 0);
  assert.equal(calls.replies.find(x => x.requestId === 'fresh-read').payload, null);
  ctx.payload = { revision: 1 };
  ctx.onMessage(own({ type: 'payload', requestId: 'still-snapshot', endpoint: '/api/budget' }));
  assert.equal(calls.replies.find(x => x.requestId === 'still-snapshot').payload, ctx.payload);
  await ctx.chatHandler({ origin: 'null', source: {}, data: { type: 'input:prompt:submit', text: 'foreign' } });
  assert.equal(ctx.showEventConfirmation, undefined);
  await ctx.chatHandler(own({ type: 'input:prompt', text: 'Budget proposal' }));
  assert.equal(calls.filled[0], 'Budget proposal');
  await ctx.chatHandler(own({ type: 'input:prompt:submit', text: 'Read my fresh budget' }));
  assert.equal(ctx.showEventConfirmation, true);
  assert.equal(ctx.eventConfirmationTitle, 'Confirm Prompt from Embed');
  assert.equal(calls.submitted.length, 0);
  await ctx.eventCallback(false);
  assert.equal(calls.submitted.length, 0);
  await ctx.eventCallback(true);
  assert.deepEqual(calls.submitted, ['Read my fresh budget']);
  console.log(JSON.stringify({ passed: true, commit, source_hashes_lf: hashes,
    scope: 'Exact upstream handler replay with host stubs; no browser, auth server or budget mutation.',
    cases: ['height/pong', 'payload is configured snapshot', 'no direct tool/action/execute RPC',
      'foreign opaque window rejected', 'registered embed fills prompt', 'submission requires confirmation'],
  }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
