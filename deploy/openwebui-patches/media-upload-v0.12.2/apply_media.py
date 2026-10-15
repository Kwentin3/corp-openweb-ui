"""Apply the four accepted media integration changes to exact v0.12.2 sources.

No media preparation or transcription logic belongs in this overlay. Native
Files, storage, processing status, Events and the draft queue retain ownership.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f'Expected exactly one v0.12.2 anchor: {old[:100]!r}')
    return source.replace(old, new)


def transform(relative: str, source: str) -> str:
    if relative == 'backend/open_webui/storage/provider.py':
        source = replace_once(source, 'import logging\n', 'import hashlib\nimport logging\n')
        return replace_once(source, 'class LocalStorageProvider(StorageProvider):\n    @staticmethod\n', '''class LocalStorageProvider(StorageProvider):
    @staticmethod
    def upload_file_streaming(file: BinaryIO, filename: str, tags: Dict[str, str]) -> Tuple[int, str, str]:
        """Persist a native local upload without retaining the whole input."""
        path = os.path.join(UPLOAD_DIR, filename)
        digest = hashlib.sha256()
        size = 0
        created = False
        try:
            with open(path, 'xb') as output:
                created = True
                for chunk in iter(lambda: file.read(1024 * 1024), b''):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            if not size:
                raise ValueError(ERROR_MESSAGES.EMPTY_CONTENT)
        except Exception:
            if created and os.path.exists(path):
                os.remove(path)
            raise
        return size, digest.hexdigest(), path

    @staticmethod
''')

    if relative == 'backend/open_webui/routers/files.py':
        source = replace_once(source, 'from open_webui.storage.provider import Storage\n',
                              'from open_webui.storage.provider import LocalStorageProvider, Storage\n')
        source = replace_once(source, '\n\nasync def process_uploaded_file(\n', '''

async def _store_upload(file, filename, tags):
    if isinstance(Storage, LocalStorageProvider):
        return await asyncio.to_thread(Storage.upload_file_streaming, file, filename, tags)
    contents, path = await asyncio.to_thread(Storage.upload_file, file, filename, tags)
    return len(contents), hashlib.sha256(contents).hexdigest(), path


async def process_uploaded_file(
''')
        source = replace_once(source,
            '        # Prefer readable storage names for admins, but fall back if the filesystem rejects it.\n',
            '''        upload_hooks = []
        if process:
            from open_webui.models.functions import Functions
            from open_webui.utils.plugin import get_function_module_from_cache
            for function in await Functions.get_functions_by_type('event', active_only=True):
                module, _, _ = await get_function_module_from_cache(request, function.id, function=function)
                hook = getattr(module, 'accept_upload', None)
                if callable(hook):
                    upload_hooks.append(hook)

        # Prefer readable storage names for admins, but fall back if the filesystem rejects it.
''')
        first = '\n            contents, file_path = await asyncio.to_thread(Storage.upload_file, file.file, filename, tags)\n'
        source = replace_once(source, first,
                              '\n            size_bytes, computed_hash, file_path = await _store_upload(file.file, filename, tags)\n')
        second = '\n                contents, file_path = await asyncio.to_thread(Storage.upload_file, file.file, filename, tags)\n'
        source = replace_once(source, second,
                              '\n                size_bytes, computed_hash, file_path = await _store_upload(file.file, filename, tags)\n')
        source = replace_once(source, '        if max_size and len(contents) > int(max_size) * 1024 * 1024:\n',
                              '        if max_size and size_bytes > int(max_size) * 1024 * 1024:\n')
        source = replace_once(source, '''        file_hash = file_metadata.get('file_hash') or await asyncio.to_thread(
            lambda: hashlib.sha256(contents).hexdigest()
        )''', "        file_hash = file_metadata.get('file_hash') or computed_hash")
        source = replace_once(source, "                        'size': len(contents),\n",
                              "                        'size': size_bytes,\n")
        return replace_once(source, '        if process:\n            if background_tasks and process_in_background:\n', '''        if process:
            for hook in upload_hooks:
                if await hook(file_item.id, user.id):
                    # Native file.uploaded dispatch starts the registered Event function.
                    return {'status': True, **file_item.model_dump()}
            if background_tasks and process_in_background:
''')

    if relative == 'src/lib/apis/files/index.ts':
        return replace_once(source, '\treturn res;\n};\n\nexport const getFileProcessStatus', '''	if (res && stream && process !== false) {
		const current = await getFileById(token, res.id);
		if (current?.data?.stage2_video_intake?.state === 'failed') {
			throw current.data.error || 'Media preparation failed';
		}
		return { ...current, error: res.error };
	}
	return res;
};

export const getFileProcessStatus''')

    if relative == 'src/lib/components/chat/MessageInput.svelte':
        return replace_once(source, '''					fileItem.file = uploadedFile;
					fileItem.id = uploadedFile.id;''', '''					fileItem.file = uploadedFile;
					fileItem.name = uploadedFile.filename ?? fileItem.name;
					fileItem.size = uploadedFile.meta?.size ?? fileItem.size;
					fileItem.id = uploadedFile.id;''')
    raise ValueError(f'Unsupported media source: {relative}')


def apply(root: Path, *, check: bool = False, backend_only: bool = False) -> str:
    root = root.resolve(strict=True)
    manifest = json.loads((BUNDLE / 'manifest.json').read_text(encoding='utf-8'))
    selected = {p: h for p, h in manifest['files'].items()
                if not backend_only or p.startswith('backend/')}
    states = set()
    staged = {}
    for relative, expected in selected.items():
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root):
            raise RuntimeError(f'Media path leaves source root: {relative}')
        original = path.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        if digest == expected['candidate_sha256']:
            states.add('candidate')
            continue
        if digest != expected['upstream_sha256']:
            raise RuntimeError(f'Unexpected source: {relative}')
        states.add('upstream')
        candidate = transform(relative, original.decode('utf-8')).encode('utf-8')
        if hashlib.sha256(candidate).hexdigest() != expected['candidate_sha256']:
            raise RuntimeError(f'Installer differs from reviewed result: {relative}')
        if relative.endswith('.py'):
            ast.parse(candidate, filename=relative)
        staged[path] = candidate
    if len(states) != 1:
        raise RuntimeError('Mixed patch state; do not partially apply or guess')
    if states == {'candidate'}:
        return 'Exact media adaptation already present; no changes'
    if check:
        return 'Exact v0.12.2 source and media adaptation verified; no changes'
    for path, candidate in staged.items():
        path.write_bytes(candidate)
        if path.read_bytes() != candidate:
            raise RuntimeError(f'Could not verify media write: {path.name}')
    return 'Exact v0.12.2 media adaptation applied and verified'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source_root', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--backend-only', action='store_true',
                        help='Patch only backend files in an extracted/runtime /app root')
    args = parser.parse_args()
    print(apply(args.source_root, check=args.check, backend_only=args.backend_only))


if __name__ == '__main__':
    main()
