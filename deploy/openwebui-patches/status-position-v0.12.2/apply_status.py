"""Apply optional per-status after_content placement to exact OpenWebUI 0.12.2."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent
SOURCE = 'src/lib/components/chat/Messages/ResponseMessage.svelte'


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f'Expected exactly one v0.12.2 anchor: {old[:100]!r}')
    return source.replace(old, new)


def transform(source: str) -> str:
    source = replace_once(source, '\t\tstatusHistory?: {\n',
                          '\t\tstatusHistory?: {\n\t\t\tposition?: string;\n')
    source = replace_once(source, '\t$: hasVisibleStatus =\n', '''	$: beforeContentStatusHistory = (message?.statusHistory ?? []).filter(
		(status) => status?.position !== 'after_content'
	);
	$: afterContentStatusHistory = (message?.statusHistory ?? []).filter(
		(status) => status?.position === 'after_content'
	);
	$: hasVisibleStatus =
''')
    source = replace_once(source, '''		statusEntries.length > 0 &&
		!(statusEntries.at(-1)?.hidden ?? false);''', '''		(message?.statusHistory
			? [beforeContentStatusHistory.at(-1), afterContentStatusHistory.at(-1)].some(
					(status) => status && !(status.hidden ?? false)
				)
			: statusEntries.length > 0 && !(statusEntries.at(-1)?.hidden ?? false));''')
    source = replace_once(source,
                          '<StatusHistory statusHistory={message?.statusHistory} />',
                          '<StatusHistory statusHistory={beforeContentStatusHistory} />')
    return replace_once(source, '\n\t\t\t\t{#if compactPreview && message.timestamp}\n', '''
				{#if model?.info?.meta?.capabilities?.status_updates ?? true}
					<StatusHistory statusHistory={afterContentStatusHistory} />
				{/if}

				{#if compactPreview && message.timestamp}
''')


def apply(root: Path, *, check: bool = False) -> str:
    root = root.resolve(strict=True)
    manifest = json.loads((BUNDLE / 'manifest.json').read_text(encoding='utf-8'))
    for relative, expected in manifest['build_identity'].items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise RuntimeError(f'Unexpected v0.12.2 build identity: {relative}')
    if json.loads((root / 'package.json').read_text(encoding='utf-8'))['version'] != manifest['version']:
        raise RuntimeError('Unexpected OpenWebUI version')
    if hashlib.sha256((BUNDLE / 'status.patch').read_bytes()).hexdigest() != manifest['patch_sha256']:
        raise RuntimeError('Patch differs from reviewed manifest')
    expected = manifest['files'][SOURCE]
    path = (root / SOURCE).resolve(strict=True)
    if not path.is_relative_to(root):
        raise RuntimeError('Status source leaves source root')
    original = path.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    if digest == expected['candidate_sha256']:
        return 'Exact status placement adaptation already present; no changes'
    if digest != expected['upstream_sha256']:
        raise RuntimeError(f'Unexpected source: {SOURCE}')
    candidate = transform(original.decode('utf-8')).encode('utf-8')
    if hashlib.sha256(candidate).hexdigest() != expected['candidate_sha256']:
        raise RuntimeError('Installer differs from reviewed result')
    if check:
        return 'Exact v0.12.2 status placement adaptation verified; no changes'
    path.write_bytes(candidate)
    if path.read_bytes() != candidate:
        raise RuntimeError('Could not verify status placement write')
    return 'Exact v0.12.2 status placement adaptation applied and verified'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(apply(args.source_root, check=args.check))
