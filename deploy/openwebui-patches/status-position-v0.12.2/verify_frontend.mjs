// Focused source behavior/identity check; native build and browser acceptance remain separate.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const bundle = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(bundle, 'manifest.json'), 'utf8'));
const root = process.argv[2];
if (!root) throw new Error('Usage: node verify_frontend.mjs PATCHED_SOURCE_ROOT');
const sha = (path) => createHash('sha256').update(readFileSync(join(root, path))).digest('hex');
for (const [path, hashes] of Object.entries(manifest.files)) {
	assert.equal(sha(path), hashes.candidate_sha256, `Unexpected patched source: ${path}`);
}
for (const [path, hash] of Object.entries(manifest.build_identity)) {
	assert.equal(sha(path), hash, `Unexpected upstream build input: ${path}`);
}
const source = readFileSync(join(root, Object.keys(manifest.files)[0]), 'utf8');
// Evaluate the actual component's reactive projection, not a test-side copy.
const begin = source.indexOf('\t$: statusEntries =');
const end = source.indexOf('\t$: visibleResponseContent =', begin);
assert(begin > 0 && end > begin);
const project = new Function('message', 'model', `let statusEntries, beforeContentStatusHistory,
 afterContentStatusHistory, hasVisibleStatus; ${source.slice(begin, end).replaceAll('$:', '')}
 return { before: beforeContentStatusHistory, after: afterContentStatusHistory, visible: hasVisibleStatus };`);
const progress = Object.freeze({ description: 'Working', done: false });
const cost = Object.freeze({ description: 'Response $0.01 / Chat $0.02', done: true, position: 'after_content' });
const unknown = Object.freeze({ description: 'Future status', done: true, position: 'future_value' });
const hidden = (status) => Object.freeze({ ...status, hidden: true });
const history = Object.freeze([progress, cost, unknown]);
const message = Object.freeze({ content: 'Long answer\n'.repeat(500), statusHistory: history });
const beforeMessage = JSON.stringify(message);
assert.deepEqual(project(message, null), { before: [progress, unknown], after: [cost], visible: true });
assert.equal(JSON.stringify(message), beforeMessage, 'Projection mutated answer/history');
assert.deepEqual(project({ statusHistory: [progress] }, null), { before: [progress], after: [], visible: true });
assert.deepEqual(project({}, null), { before: [], after: [], visible: false });
assert.equal(project({ status: progress }, null).visible, true, 'Legacy cursor visibility changed');
assert.equal(project({ status: hidden(progress) }, null).visible, false);
assert.equal(project({ statusHistory: [progress, hidden(cost)] }, null).visible, true);
assert.equal(project({ statusHistory: [hidden(progress), cost] }, null).visible, true);
assert.equal(project({ statusHistory: [hidden(progress), hidden(cost)] }, null).visible, false);
assert.equal(project({ statusHistory: [progress, hidden(progress)] }, null).visible, false);
assert.equal(project(message, { info: { meta: { capabilities: { status_updates: false } } } }).visible, false);
// Supplementary hunk checks bind the evaluated projection to its actual render sites.
const above = source.indexOf('<StatusHistory statusHistory={beforeContentStatusHistory} />');
const answer = source.indexOf('<ContentRenderer');
const below = source.indexOf('<StatusHistory statusHistory={afterContentStatusHistory} />');
const controls = source.indexOf('bind:this={buttonsContainerElement}');
assert(above < answer && answer < below && below < controls);
assert(source.includes("{#if model?.info?.meta?.capabilities?.status_updates ?? true}\n\t\t\t\t\t<StatusHistory statusHistory={afterContentStatusHistory} />\n\t\t\t\t{/if}"));
console.log(JSON.stringify({ upstream_commit: manifest.upstream_commit, source_identity_verified: true,
 actual_status_projection_verified: true, placement_hunks_verified: true, browser_acceptance: 'not performed' }));
