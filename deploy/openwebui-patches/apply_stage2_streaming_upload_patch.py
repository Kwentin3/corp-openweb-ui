#!/usr/bin/env python3
"""Fail-fast OpenWebUI v0.9.6 overlay for bounded-memory local file upload.

The native LocalStorageProvider still owns the file path and bytes on disk.
All local uploads use its new streaming method. The deployed storage provider
is local. Other providers retain the upstream route for non-media files and
fail closed for media until they offer the same streaming contract.
"""

from __future__ import annotations

import argparse
from pathlib import Path


STORAGE_OLD = "class LocalStorageProvider(StorageProvider):\n    @staticmethod\n    def upload_file("
STORAGE_NEW = '''class LocalStorageProvider(StorageProvider):
    @staticmethod
    def upload_file_streaming(file: BinaryIO, filename: str, tags: Dict[str, str]) -> Tuple[int, str, str]:
        """Write and hash a local upload in bounded chunks."""
        file_path = os.path.join(UPLOAD_DIR, filename)
        digest = hashlib.sha256()
        size = 0
        try:
            with open(file_path, "xb") as destination:
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    destination.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
            if not size:
                raise ValueError(ERROR_MESSAGES.EMPTY_CONTENT)
        except Exception:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise
        return size, digest.hexdigest(), file_path

    @staticmethod
    def upload_file('''

IMPORT_OLD = "from open_webui.storage.provider import Storage\n"
IMPORT_NEW = "from open_webui.storage.provider import LocalStorageProvider, Storage\n"

UPLOAD_OLD = '''        contents, file_path = await asyncio.to_thread(
            Storage.upload_file,
            file.file,
            filename,
            {
                'OpenWebUI-User-Email': user.email,
                'OpenWebUI-User-Id': user.id,
                'OpenWebUI-User-Name': user.name,
                'OpenWebUI-File-Id': id,
            },
        )

        # SHA-256 of raw uploaded bytes for incremental sync diffing.
        # If the client pre-computed and sent file_hash, use that.
        file_hash = file_metadata.get('file_hash') or hashlib.sha256(contents).hexdigest()
'''
UPLOAD_NEW = '''        storage_tags = {
            'OpenWebUI-User-Email': user.email,
            'OpenWebUI-User-Id': user.id,
            'OpenWebUI-User-Name': user.name,
            'OpenWebUI-File-Id': id,
        }
        if isinstance(Storage, LocalStorageProvider):
            # Native local storage streams every file and computes its hash.
            size, computed_hash, file_path = await asyncio.to_thread(
                Storage.upload_file_streaming, file.file, filename, storage_tags
            )
        else:
            if isinstance(file.content_type, str) and file.content_type.startswith(('audio/', 'video/')):
                raise ValueError('Streaming media upload requires local storage')
            contents, file_path = await asyncio.to_thread(
                Storage.upload_file, file.file, filename, storage_tags
            )
            size = len(contents)
            computed_hash = hashlib.sha256(contents).hexdigest()

        # SHA-256 of raw uploaded bytes for incremental sync diffing.
        # If the client pre-computed and sent file_hash, use that.
        file_hash = file_metadata.get('file_hash') or computed_hash
'''


def _replace_exact(source: str, old: str, new: str, label: str) -> tuple[str, str]:
    if source.count(new) == 1:
        return source, "already_patched"
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: expected exactly one pinned v0.9.6 signature")
    return source.replace(old, new), "patched"


def patch(storage_path: Path, files_path: Path, *, dry_run: bool = False) -> tuple[str, str]:
    storage = storage_path.read_text(encoding="utf-8")
    files = files_path.read_text(encoding="utf-8")
    storage, storage_status = _replace_exact(storage, "import json\n", "import hashlib\nimport json\n", "storage import")
    storage, method_status = _replace_exact(storage, STORAGE_OLD, STORAGE_NEW, "storage method")
    files, files_import_status = _replace_exact(files, IMPORT_OLD, IMPORT_NEW, "upload route import")
    files, files_status = _replace_exact(files, UPLOAD_OLD, UPLOAD_NEW, "upload route")
    files, size_status = _replace_exact(files, "'size': len(contents),", "'size': size,", "upload size")
    if storage_status != method_status or files_import_status != files_status or files_status != size_status:
        raise RuntimeError("Incomplete streaming upload patch")
    if not dry_run:
        storage_path.write_text(storage, encoding="utf-8")
        files_path.write_text(files, encoding="utf-8")
    return storage_status, files_status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-root", default="/app/backend/open_webui")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.backend_root)
    statuses = patch(root / "storage/provider.py", root / "routers/files.py", dry_run=args.dry_run)
    print(f"stage2-streaming-upload-v1: storage={statuses[0]} files={statuses[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
