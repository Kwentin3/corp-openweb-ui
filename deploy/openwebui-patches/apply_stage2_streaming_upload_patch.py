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
            if video_type or (isinstance(file.content_type, str) and file.content_type.startswith('audio/')):
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

VIDEO_ROUTE_OLD = """            stt_supported = getattr(request.app.state.config, 'STT_SUPPORTED_CONTENT_TYPES', [])
"""
VIDEO_ROUTE_NEW = """            if content_type and content_type.startswith('video/'):
                # Prepare before Send. Keep native File/status ownership and
                # let its persistent reconciler finish an interrupted retry.
                from open_webui.services.stage2_video_intake import prepare_uploaded_video
                try:
                    await prepare_uploaded_video(file_item.id)
                except Exception:
                    log.exception('Video intake pending reconciliation for %s', file_item.id)
                return

            stt_supported = getattr(request.app.state.config, 'STT_SUPPORTED_CONTENT_TYPES', [])
"""

ROUTER_OLD = "router = APIRouter()\n"
ROUTER_NEW = """router = APIRouter()


_STAGE2_VIDEO_EXTENSIONS = {
    '.mp4': 'video/mp4', '.mov': 'video/quicktime',
    '.mkv': 'video/x-matroska', '.avi': 'video/x-msvideo',
    '.webm': 'video/webm', '.m4v': 'video/x-m4v',
    '.wmv': 'video/x-ms-wmv', '.mpeg': 'video/mpeg',
    '.mpg': 'video/mpeg',
}


def _stage2_video_type(content_type: str | None, filename: str | None) -> str | None:
    if isinstance(content_type, str) and content_type.startswith('audio/'):
        return None
    if isinstance(content_type, str) and content_type.startswith('video/'):
        return content_type
    return _STAGE2_VIDEO_EXTENSIONS.get(Path(filename or '').suffix.lower())


@router.on_event('startup')
async def start_stage2_video_intake() -> None:
    from open_webui.services.stage2_video_intake import start_video_intake_reconciler
    start_video_intake_reconciler()
"""

PROCESS_OLD = """    file_metadata = metadata if metadata else {}

    try:
"""
PROCESS_NEW = """    file_metadata = metadata if metadata else {}
    video_type = _stage2_video_type(file.content_type, file.filename)
    if video_type:
        process = True

    try:
"""

CONTENT_TYPE_OLD = """            content_type = file.content_type
"""
CONTENT_TYPE_NEW = """            content_type = (file_item.meta or {}).get('content_type') or file.content_type
"""

META_TYPE_OLD = """'content_type': (file.content_type if isinstance(file.content_type, str) else None),"""
META_TYPE_NEW = """'content_type': video_type or (file.content_type if isinstance(file.content_type, str) else None),"""


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
    files, video_status = _replace_exact(files, VIDEO_ROUTE_OLD, VIDEO_ROUTE_NEW, "video intake route")
    files, router_status = _replace_exact(files, ROUTER_OLD, ROUTER_NEW, "video intake startup")
    files, process_status = _replace_exact(files, PROCESS_OLD, PROCESS_NEW, "video intake process flag")
    files, content_type_status = _replace_exact(files, CONTENT_TYPE_OLD, CONTENT_TYPE_NEW, "video intake content type")
    files, meta_type_status = _replace_exact(files, META_TYPE_OLD, META_TYPE_NEW, "video intake metadata")
    if storage_status != method_status or files_import_status != files_status or files_status != size_status:
        raise RuntimeError("Incomplete streaming upload patch")
    if len({files_status, video_status, router_status, process_status, content_type_status, meta_type_status}) != 1:
        raise RuntimeError("Incomplete video intake patch")
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
