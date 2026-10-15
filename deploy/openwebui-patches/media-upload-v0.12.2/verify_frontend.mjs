// Build-input identity check; npm/Svelte build and browser acceptance are separate.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const bundle = dirname(fileURLToPath(import.meta.url));
const manifest = JSON.parse(readFileSync(join(bundle, 'manifest.json'), 'utf8'));
const root = process.argv[2];
if (!root) throw new Error('Usage: node verify_frontend.mjs SOURCE_ROOT');
if (Number(process.versions.node.split('.')[0]) !== 22) throw new Error('Build qualification requires Node 22');
const sha = (path) => createHash('sha256').update(readFileSync(join(root, path))).digest('hex');
for (const [path, hashes] of Object.entries(manifest.files)) {
	if (path.startsWith('src/') && sha(path) !== hashes.candidate_sha256) {
		throw new Error(`Unexpected patched frontend source: ${path}`);
	}
}
for (const path of ['package.json', 'package-lock.json']) {
	if (sha(path) !== manifest.build_identity[path]) throw new Error(`Unexpected upstream build input: ${path}`);
}
console.log(JSON.stringify({ node: process.version, upstream_commit: manifest.upstream_commit, frontend_inputs_verified: true }));
