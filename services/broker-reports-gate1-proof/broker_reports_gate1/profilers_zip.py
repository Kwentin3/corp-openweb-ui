from __future__ import annotations

from typing import Any

from .archive_intake import Gate1ArchiveIntakeFactory
from .blockers import corrupt_file, zip_requires_review
from .contracts import profile_id


def profile_zip(
    run_id: str,
    document_id: str,
    content_bytes: bytes,
    *,
    archive_manifest: dict[str, Any] | None = None,
) -> tuple[dict, list[dict], list[dict]]:
    manifest = archive_manifest
    if manifest is None:
        manifest = Gate1ArchiveIntakeFactory().create().inspect_and_expand(
            normalization_run_id=run_id,
            parent_document_ref=document_id,
            content_bytes=content_bytes,
        ).manifest
    complete = (
        manifest.get("terminal_status") == "complete"
        and manifest.get("all_members_accounted") is True
        and int(manifest.get("blocked_members_total") or 0) == 0
    )
    blockers = []
    if not complete:
        if "zip_container_unreadable" in (manifest.get("reason_codes") or []):
            blockers.append(corrupt_file(run_id, document_id, "bad_zip_container"))
        blockers.append(zip_requires_review(run_id, document_id))
    extension_counts: dict[str, int] = {}
    for member in manifest.get("member_inventory") or []:
        if not isinstance(member, dict):
            continue
        extension = str(member.get("extension") or "none")
        extension_counts[extension] = extension_counts.get(extension, 0) + 1
    profile = {
        "profile_id": profile_id(document_id),
        "document_id": document_id,
        "container_format": "zip",
        "parser": "broker_reports_bounded_zip_source_container",
        "parser_version": "1",
        "profile_status": "profiled" if complete else "blocked",
        "machine_readable": "yes" if complete else "conditional",
        "machine_readable_table": False,
        "member_count": int(manifest.get("members_total") or 0),
        "members_count": int(manifest.get("members_total") or 0),
        "extension_counts": dict(sorted(extension_counts.items())),
        "member_extension_counts": dict(sorted(extension_counts.items())),
        "nested_archive_count": sum(
            count
            for extension, count in extension_counts.items()
            if extension in {"7z", "gz", "rar", "tar", "tgz", "zip"}
        ),
        "promoted_members_total": int(
            manifest.get("promoted_members_total") or 0
        ),
        "signature_sidecars_total": int(
            manifest.get("signature_sidecars_total") or 0
        ),
        "blocked_members_total": int(manifest.get("blocked_members_total") or 0),
        "policy_status": "accepted_source_container" if complete else "blocked",
        "archive_manifest_ref": manifest.get("archive_ref"),
        "all_members_accounted": manifest.get("all_members_accounted") is True,
        "member_inventory": manifest.get("member_inventory") or [],
        "normalized_slice_refs": [],
        "warnings": [] if complete else list(manifest.get("reason_codes") or []),
        "blocker_refs": [item["blocker_id"] for item in blockers],
    }
    return profile, [], blockers
