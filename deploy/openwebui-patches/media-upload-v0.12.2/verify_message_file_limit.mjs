// Execute the real pinned handlers; only UI, upload and model transport boundaries use fixtures.
// Does not prove a Svelte build, browser behavior or provider context delivery.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const bundle = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(bundle, 'manifest.json'), 'utf8'));
const root = process.argv[2];
if (!root) throw new Error('Usage: node verify_message_file_limit.mjs PATCHED_SOURCE_ROOT');
function source(path) {
	const bytes = readFileSync(join(root, path));
	assert.equal(createHash('sha256').update(bytes).digest('hex'), manifest.files[path].candidate_sha256, path);
	return bytes.toString('utf8');
}
const chat = source('src/lib/components/chat/Chat.svelte');
const input = source('src/lib/components/chat/MessageInput.svelte');
const key = 'You can only chat with a maximum of {{maxCount}} file(s) at a time.';
const translations = Object.fromEntries(['en-US', 'ru-RU'].map((locale) => [
	locale, JSON.parse(source(`src/lib/i18n/locales/${locale}/translation.json`))[key]
]));
assert.equal(translations['en-US'], 'You can attach up to {{maxCount}} new files per message.');
assert.equal(translations['ru-RU'], 'К одному сообщению можно прикрепить не более {{maxCount}} новых файлов.');

function handler(text, name, signature = null) {
	const start = text.indexOf(`\tconst ${name} = `);
	assert.notEqual(start, -1, name);
	const end = text.indexOf('\n\t};', start);
	assert.notEqual(end, -1, name);
	let code = text.slice(start, end + '\n\t};'.length);
	if (signature) {
		// Remove only the known TypeScript signature; preserve the complete executable body.
		const marker = name === 'submitHandler' ? '): Promise<BridgeSubmission> => {' : ') => {';
		const body = code.indexOf(marker);
		assert.notEqual(body, -1, `${name} signature`);
		code = `const ${name} = async (${signature}) => {` + code.slice(body + marker.length);
	}
	return code;
}
const handlers = [
	handler(chat, 'processNextInQueue', 'targetChatId'),
	handler(chat, 'submitPrompt', 'inputContent, inputFiles, bridgeRequest = null'),
	handler(chat, 'submitHandler', 'userPrompt, { _raw = false, bridge: bridgeRequest = null } = {}'),
	handler(input, 'inputFilesHandler')
].join('\n');
const files = (count, prefix = 'new', status = 'uploaded') => Array.from({ length: count }, (_, i) => ({
	id: `${prefix}-${i}`, name: `${prefix}-${i}.txt`, type: 'file', content_type: 'text/plain', size: 1, status
}));
function fixture({ old = 0, current = 0, queue = [], mode = 'normal', limit = 10 } = {}) {
	const sent = [], errors = [], uploads = [], context = {
		console: { log() {}, error(error) { errors.push(error.message ?? error); } },
		structuredClone, Set, Date,
		files: files(current), chatFiles: files(old, 'old'),
		$config: { file: { max_count: limit } }, $settings: {}, $chatId: 'chat-a',
		$chatRequestQueues: { 'chat-a': structuredClone(queue) },
		history: { currentId: 'previous', messages: {
			previous: { id: 'previous', role: 'assistant', done: true, childrenIds: [] },
			old: { id: 'old', role: 'user', files: files(old, 'old'), childrenIds: [] }
		} },
		selectedModelIds: ['model'], selectedModels: ['model'], $models: [{ id: 'model' }],
		pendingOAuthTools: [], chatVariables: {}, webSearchActive: false, webSearchConfirmed: false,
		$user: { id: 'user', name: 'User' }, $showCallOverlay: false,
		messageInput: { setText() {}, focus() {} }, prompt: '',
		emitTyping() {}, saveSessionSelectedModels() {},
		getChatVariablesForm: () => ({ conflicts: [], missing: false, empty: false }),
		equal: (a, b) => JSON.stringify(a) === JSON.stringify(b),
		isRasterImageContentType: () => false, isHeicImage: () => false,
		$i18n: { t: (text, values) => (translations['en-US'] && text === key ? translations['en-US'] : text)
			.replace('{{maxCount}}', values?.maxCount) },
		toast: { error: (text) => errors.push(text), warning: (text) => errors.push(text) }
	};
	let id = 0;
	context.uuidv4 = () => `id-${++id}`;
	context.chatRequestQueues = { update: (update) => { context.$chatRequestQueues = update(context.$chatRequestQueues); } };
	context.uploadFileHandler = (file) => { uploads.push(file); context.files.push(file); };
	context.sendMessage = async (history, userId) => {
		sent.push({ message: structuredClone(history.messages[userId]), history: structuredClone(history),
			chatFiles: structuredClone(context.chatFiles), locked: context.processingQueueChats.has('chat-a') });
		if (mode === 'throw') throw new Error('transport failure');
		const assistantId = `assistant-${userId}`;
		history.messages[userId].childrenIds.push(assistantId);
		history.messages[assistantId] = { id: assistantId, role: 'assistant', done: mode !== 'normal', childrenIds: [] };
		history.currentId = assistantId;
		if (mode === 'early') await context.handlers.processNextInQueue('chat-a');
		if (mode === 'navigate') context.$chatId = 'chat-b';
		return { status: 'submitted' };
	};
	vm.createContext(context);
	vm.runInContext(`const processingQueueChats = new Set();\n${handlers}\n` +
		'globalThis.handlers = { processNextInQueue, submitHandler, inputFilesHandler };' +
		'globalThis.processingQueueChats = processingQueueChats;', context);
	return { context, sent, errors, uploads, ...context.handlers };
}
const passed = [];
for (const [existing, added, accepted] of [[0, 10, true], [0, 11, false], [5, 5, true], [10, 1, false]]) {
	const f = fixture({ current: existing });
	await f.inputFilesHandler(files(added, 'input'));
	assert.equal(f.uploads.length, accepted ? added : 0);
	assert.equal(f.context.files.length, accepted ? existing + added : existing);
	assert.equal(f.errors.length, accepted ? 0 : 1);
}
passed.push('native upload handler accepts 10, rejects 11 and counts existing draft files');
for (const old of [0, 10, 20]) {
	const f = fixture({ old, current: 10 });
	assert.equal((await f.submitHandler('first')).status, 'submitted');
	assert.equal(f.sent.length, 1);
	assert.equal(f.sent[0].message.files.length, 10);
	assert.equal(f.sent[0].chatFiles.length, old + 10);
	assert.equal(f.sent[0].history.messages.old.files.length, old);
	assert.equal(f.errors.length, 0);
	f.context.history.messages[f.context.history.currentId].done = true;
	f.context.files = files(10, 'next');
	await f.submitHandler('next');
	assert.equal(f.sent[1].message.files.length, 10);
	assert.equal(f.sent[1].chatFiles.length, old + 20);
	assert.equal(f.sent[1].history.messages[f.sent[0].message.id].files.length, 10);
}
passed.push('native Send accepts fresh 10 after old 0/10/20, retains all history and chat sources for next turn');
for (const old of [0, 20]) {
	const f = fixture({ old, current: 11 });
	assert.equal((await f.submitHandler('too many')).status, 'rejected');
	assert.equal(f.sent.length, 0);
	assert.equal(f.context.files.length, 11);
	assert.equal(f.errors[0], 'You can attach up to 10 new files per message.');
}
passed.push('native Send rejects 11 new files with per-message feedback and preserves draft');
{
	const f = fixture({ old: 20, current: 11, limit: null });
	await f.submitHandler('native unlimited');
	assert.equal(f.sent[0].message.files.length, 11);
}
passed.push('native null configuration remains unlimited');
const two = () => [{ id: 'q1', prompt: 'first queued', files: files(10, 'q1') },
	{ id: 'q2', prompt: 'second queued', files: files(10, 'q2') }];
{
	const f = fixture({ old: 20, current: 10 });
	f.context.history.messages.previous.done = false;
	await f.submitHandler('first queued');
	f.context.files = files(10, 'next');
	await f.submitHandler('second queued');
	assert.equal(f.sent.length, 0);
	assert.deepEqual(Array.from(f.context.$chatRequestQueues['chat-a'], (m) => m.files.length), [10, 10]);
	f.context.history.messages.previous.done = true;
	await f.processNextInQueue('chat-a');
	f.context.history.messages[f.context.history.currentId].done = true;
	await f.processNextInQueue('chat-a');
	assert.deepEqual(f.sent.map((s) => s.message.content), ['first queued', 'second queued']);
	assert.deepEqual(f.sent.map((s) => s.message.files.length), [10, 10]);
	assert.equal(f.sent[1].chatFiles.length, 40);
}
passed.push('native Send enqueues two fresh ten-file messages during generation and drains them separately');
{
	const f = fixture({ old: 20, queue: two() });
	await f.processNextInQueue('chat-a');
	assert.equal(f.sent.length, 1);
	assert.equal(f.sent[0].message.content, 'first queued');
	assert.equal(f.sent[0].message.files.length, 10);
	assert.equal(f.context.$chatRequestQueues['chat-a'][0].id, 'q2');
	assert.equal(f.context.processingQueueChats.size, 0);
	f.context.history.messages[f.context.history.currentId].done = true;
	await f.processNextInQueue('chat-a');
	assert.deepEqual(f.sent.map((s) => s.message.content), ['first queued', 'second queued']);
	assert.deepEqual(f.sent.map((s) => s.message.files.length), [10, 10]);
	assert.equal(f.sent[1].chatFiles.length, 40);
	assert.equal(f.context.$chatRequestQueues['chat-a'].length, 0);
}
passed.push('native queue keeps 10+10 as separate messages and waits for active response completion');
{
	const f = fixture({ queue: two(), mode: 'early' });
	await f.processNextInQueue('chat-a');
	assert.deepEqual(f.sent.map((s) => s.message.content), ['first queued', 'second queued']);
	assert.deepEqual(f.sent.map((s) => s.message.files.length), [10, 10]);
	assert.equal(f.context.$chatRequestQueues['chat-a'].length, 0);
	assert.equal(f.context.processingQueueChats.size, 0);
}
passed.push('completion received before submit returns drains the remaining queue after unlock');
{
	const f = fixture({ queue: two(), mode: 'throw' });
	await f.processNextInQueue('chat-a');
	assert.equal(f.sent.length, 1);
	assert.equal(JSON.stringify(f.context.$chatRequestQueues['chat-a']), JSON.stringify(two()));
	assert.equal(f.context.processingQueueChats.size, 0);
	assert.deepEqual(f.errors, ['transport failure']);
}
passed.push('thrown submission restores the same item ahead of remaining queue without immediate retry');
{
	const f = fixture({ queue: two(), mode: 'navigate' });
	await f.processNextInQueue('chat-a');
	assert.equal(f.sent.length, 1);
	assert.equal(f.context.$chatRequestQueues['chat-a'][0].id, 'q2');
	assert.equal(f.context.processingQueueChats.size, 0);
}
passed.push('navigation during submission leaves remaining items queued in their original chat');
for (const status of ['uploading', 'error']) {
	const queue = two();
	queue[1].files[0].status = status;
	const f = fixture({ queue });
	await f.processNextInQueue('chat-a');
	assert.equal(f.sent.length, 0);
	assert.equal(f.context.$chatRequestQueues['chat-a'].length, 2);
}
passed.push('native readiness guard still checks every queued upload and error');
console.log(JSON.stringify({ passed, exact_candidate_handlers: true,
	boundaries: 'UI, upload and sendMessage transport fixtures; no browser/provider acceptance' }));
