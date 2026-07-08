from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from .blockers import corrupt_file, encrypted_file, zip_requires_review
from .contracts import profile_id, stable_digest

OVERSIZED_ZIP_MEMBER_SIZE = 20_000_000


def profile_zip(run_id: str, document_id: str, content_bytes: bytes) -> tuple[dict, list[dict], list[dict]]:
    blockers = []
    try:
        with ZipFile(BytesIO(content_bytes)) as archive:
            infos = archive.infolist()
            corrupt_member = archive.testzip()
    except BadZipFile:
        blocker = corrupt_file(run_id, document_id, "bad_zip_file")
        return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]

    extension_counts: Counter[str] = Counter()
    encrypted_count = 0
    nested_archive_count = 0
    oversized_member_count = 0
    member_summaries = []
    for index, info in enumerate(infos, start=1):
        suffix = PurePosixPath(info.filename).suffix.lower().lstrip(".") or "none"
        extension_counts[suffix] += 1
        is_encrypted = bool(info.flag_bits & 0x1)
        if is_encrypted:
            encrypted_count += 1
        if suffix in {"zip", "7z", "rar"}:
            nested_archive_count += 1
        if info.file_size > OVERSIZED_ZIP_MEMBER_SIZE:
            oversized_member_count += 1
        member_summaries.append(
            {
                "member_index": index,
                "safe_member_id": f"zipmem_{stable_digest([document_id, info.filename], length=12)}",
                "extension": suffix,
                "compressed_size": int(info.compress_size),
                "file_size": int(info.file_size),
                "is_dir": info.is_dir(),
                "encrypted": is_encrypted,
            }
        )

    review_blocker = zip_requires_review(run_id, document_id)
    blockers.append(review_blocker)
    if encrypted_count:
        blockers.append(encrypted_file(run_id, document_id))
    if corrupt_member:
        blockers.append(corrupt_file(run_id, document_id, "zip_member_failed_crc"))

    profile = {
        "profile_id": profile_id(document_id),
        "document_id": document_id,
        "container_format": "zip",
        "parser": "python_stdlib_zipfile",
        "parser_version": "1",
        "profile_status": "profiled_with_review",
        "machine_readable": "conditional",
        "machine_readable_table": False,
        "member_count": len(infos),
        "members_count": len(infos),
        "extension_counts": dict(sorted(extension_counts.items())),
        "member_extension_counts": dict(sorted(extension_counts.items())),
        "nested_archive_count": nested_archive_count,
        "encrypted_count": encrypted_count,
        "encrypted_member_count": encrypted_count,
        "oversized_member_count": oversized_member_count,
        "corrupt_member_detected": bool(corrupt_member),
        "policy_status": "requires_review",
        "member_inventory": member_summaries,
        "normalized_slice_refs": [],
        "warnings": ["zip_requires_review"],
        "blocker_refs": [blocker["blocker_id"] for blocker in blockers],
    }
    return profile, [], blockers


def _blocked_profile(document_id: str, blocker_refs: list[str]) -> dict:
    return {
        "profile_id": profile_id(document_id),
        "document_id": document_id,
        "container_format": "zip",
        "parser": "python_stdlib_zipfile",
        "parser_version": "1",
        "profile_status": "blocked",
        "machine_readable": "unknown",
        "machine_readable_table": False,
        "member_count": 0,
        "members_count": 0,
        "extension_counts": {},
        "member_extension_counts": {},
        "nested_archive_count": 0,
        "encrypted_count": 0,
        "encrypted_member_count": 0,
        "oversized_member_count": 0,
        "corrupt_member_detected": True,
        "policy_status": "blocked",
        "member_inventory": [],
        "normalized_slice_refs": [],
        "warnings": ["corrupt_file"],
        "blocker_refs": blocker_refs,
    }
