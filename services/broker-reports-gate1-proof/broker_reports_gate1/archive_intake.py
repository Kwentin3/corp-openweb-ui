from __future__ import annotations

import hashlib
import re
import stat
import unicodedata
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any
from zipfile import BadZipFile, LargeZipFile, ZipFile

from .contracts import stable_digest


ARCHIVE_SOURCE_MANIFEST_SCHEMA_VERSION = (
    "broker_reports_gate1_archive_source_manifest_v1"
)
ARCHIVE_SOURCE_PROFILE_ID = "broker_reports_bounded_zip_source_container_v1"
PROMOTED_MEMBER_EXTENSIONS = {"pdf", "xml"}
ACCOUNTED_SIDECAR_EXTENSIONS = {"p7s"}
NESTED_ARCHIVE_EXTENSIONS = {"7z", "gz", "rar", "tar", "tgz", "zip"}

FACTORY_REQUIRED = (
    "Gate1ArchiveIntakeFactory.create is the only production ZIP inspection "
    "and member-promotion entrypoint"
)
FORBIDDEN = (
    "Callers must not extract archive paths directly, recurse into nested archives, "
    "or silently omit unsupported members"
)


@dataclass(frozen=True)
class ArchiveIntakeConfig:
    max_archive_bytes: int = 10_000_000
    max_members: int = 100
    max_member_bytes: int = 20_000_000
    max_expanded_bytes: int = 50_000_000
    max_compression_ratio: float = 100.0
    max_member_path_characters: int = 240


@dataclass(frozen=True)
class ArchiveMemberExpansion:
    safe_member_ref: str
    member_index: int
    extension: str
    private_filename: str
    content_bytes: bytes
    content_sha256: str


@dataclass(frozen=True)
class ArchiveExpansionResult:
    manifest: dict[str, Any]
    promoted_members: tuple[ArchiveMemberExpansion, ...]


class Gate1ArchiveIntakeFactory:
    def __init__(self, config: ArchiveIntakeConfig | None = None) -> None:
        self.config = config or ArchiveIntakeConfig()

    def create(self) -> "Gate1ArchiveIntake":
        for value, code in (
            (self.config.max_archive_bytes, "archive_input_budget_invalid"),
            (self.config.max_members, "archive_member_count_budget_invalid"),
            (self.config.max_member_bytes, "archive_member_budget_invalid"),
            (self.config.max_expanded_bytes, "archive_expanded_budget_invalid"),
            (self.config.max_compression_ratio, "archive_ratio_budget_invalid"),
            (
                self.config.max_member_path_characters,
                "archive_member_path_budget_invalid",
            ),
        ):
            if value <= 0:
                raise ValueError(code)
        return Gate1ArchiveIntake(self.config)


class Gate1ArchiveIntake:
    def __init__(self, config: ArchiveIntakeConfig) -> None:
        self.config = config

    def inspect_and_expand(
        self,
        *,
        normalization_run_id: str,
        parent_document_ref: str,
        content_bytes: bytes,
    ) -> ArchiveExpansionResult:
        if not normalization_run_id or not parent_document_ref:
            raise ValueError("archive_scope_required")
        archive_ref = "archive_" + stable_digest(
            [normalization_run_id, parent_document_ref], length=24
        )
        if len(content_bytes) > self.config.max_archive_bytes:
            return self._blocked(
                archive_ref=archive_ref,
                normalization_run_id=normalization_run_id,
                parent_document_ref=parent_document_ref,
                reasons=["zip_archive_byte_budget_exceeded"],
            )

        try:
            archive = ZipFile(BytesIO(content_bytes))
            infos = archive.infolist()
        except (BadZipFile, LargeZipFile):
            return self._blocked(
                archive_ref=archive_ref,
                normalization_run_id=normalization_run_id,
                parent_document_ref=parent_document_ref,
                reasons=["zip_container_unreadable"],
            )

        reasons: list[str] = []
        if len(infos) > self.config.max_members:
            reasons.append("zip_member_count_budget_exceeded")
        expanded_total = sum(int(info.file_size) for info in infos)
        if expanded_total > self.config.max_expanded_bytes:
            reasons.append("zip_expanded_byte_budget_exceeded")

        normalized_names: set[str] = set()
        private_records: list[dict[str, Any]] = []
        safe_records: list[dict[str, Any]] = []
        promoted: list[ArchiveMemberExpansion] = []
        try:
            for member_index, info in enumerate(infos, start=1):
                safe_member_ref = "zipmem_" + stable_digest(
                    [archive_ref, member_index, int(info.CRC)], length=24
                )
                normalized_name, name_reasons = _normalized_member_name(
                    info.filename,
                    max_characters=self.config.max_member_path_characters,
                )
                reasons.extend(name_reasons)
                collision_key = unicodedata.normalize("NFC", normalized_name).casefold()
                if collision_key in normalized_names:
                    reasons.append("zip_member_name_collision")
                normalized_names.add(collision_key)

                extension = (
                    PurePosixPath(normalized_name).suffix.lower().lstrip(".")
                    or "none"
                )
                member_reasons: list[str] = []
                if info.flag_bits & 0x1:
                    member_reasons.append("zip_encrypted_member_forbidden")
                if info.file_size > self.config.max_member_bytes:
                    member_reasons.append("zip_member_byte_budget_exceeded")
                ratio = (
                    float(info.file_size) / float(max(int(info.compress_size), 1))
                    if info.file_size
                    else 0.0
                )
                if ratio > self.config.max_compression_ratio:
                    member_reasons.append("zip_compression_ratio_exceeded")
                file_type = _member_file_type(info)
                if file_type in {"symlink", "special"}:
                    member_reasons.append(f"zip_{file_type}_member_forbidden")
                if extension in NESTED_ARCHIVE_EXTENSIONS:
                    member_reasons.append("zip_nested_archive_forbidden")
                if (
                    not info.is_dir()
                    and extension not in PROMOTED_MEMBER_EXTENSIONS
                    and extension not in ACCOUNTED_SIDECAR_EXTENSIONS
                ):
                    member_reasons.append("zip_member_format_unsupported")

                member_bytes = b""
                if not info.is_dir() and not member_reasons and not name_reasons:
                    try:
                        member_bytes = archive.read(info)
                    except (BadZipFile, RuntimeError, OSError):
                        member_reasons.append("zip_member_crc_or_read_failed")
                    if len(member_bytes) != int(info.file_size):
                        member_reasons.append("zip_member_size_mismatch")
                reasons.extend(member_reasons)

                content_sha256 = (
                    hashlib.sha256(member_bytes).hexdigest() if member_bytes else ""
                )
                checksum_ref = (
                    "srcsum_"
                    + stable_digest(
                        [parent_document_ref, safe_member_ref, content_sha256],
                        length=24,
                    )
                    if content_sha256
                    else None
                )
                if info.is_dir():
                    disposition = "accounted_directory"
                elif member_reasons or name_reasons:
                    disposition = "blocked_member"
                elif extension in ACCOUNTED_SIDECAR_EXTENSIONS:
                    disposition = "accounted_signature_sidecar"
                else:
                    disposition = "promoted_source_document"

                safe_records.append(
                    {
                        "safe_member_ref": safe_member_ref,
                        "member_index": member_index,
                        "extension": extension,
                        "compressed_size": int(info.compress_size),
                        "expanded_size": int(info.file_size),
                        "compression_ratio": round(ratio, 6),
                        "disposition": disposition,
                        "content_checksum_ref": checksum_ref,
                        "promoted_document_ref": None,
                        "reason_codes": sorted(set(name_reasons + member_reasons)),
                        "raw_member_name_included": False,
                    }
                )
                private_records.append(
                    {
                        "safe_member_ref": safe_member_ref,
                        "member_index": member_index,
                        "extension": extension,
                        "private_filename": info.filename,
                        "content_bytes": member_bytes,
                        "content_sha256": content_sha256,
                        "disposition": disposition,
                    }
                )
        finally:
            archive.close()

        reasons = sorted(set(reasons))
        if reasons:
            for record in safe_records:
                if record["disposition"] == "promoted_source_document":
                    record["disposition"] = "blocked_due_archive_policy"
                    record["reason_codes"] = sorted(
                        set(record["reason_codes"] + ["archive_fail_closed"])
                    )
            promoted = []
            status = "blocked"
        else:
            for record in private_records:
                if record["disposition"] != "promoted_source_document":
                    continue
                promoted.append(
                    ArchiveMemberExpansion(
                        safe_member_ref=str(record["safe_member_ref"]),
                        member_index=int(record["member_index"]),
                        extension=str(record["extension"]),
                        private_filename=str(record["private_filename"]),
                        content_bytes=bytes(record["content_bytes"]),
                        content_sha256=str(record["content_sha256"]),
                    )
                )
            status = "complete"

        manifest = {
            "schema_version": ARCHIVE_SOURCE_MANIFEST_SCHEMA_VERSION,
            "profile_id": ARCHIVE_SOURCE_PROFILE_ID,
            "archive_ref": archive_ref,
            "normalization_run_id": normalization_run_id,
            "parent_document_ref": parent_document_ref,
            "terminal_status": status,
            "reason_codes": reasons,
            "members_total": len(safe_records),
            "promoted_members_total": sum(
                item["disposition"] == "promoted_source_document"
                for item in safe_records
            ),
            "signature_sidecars_total": sum(
                item["disposition"] == "accounted_signature_sidecar"
                for item in safe_records
            ),
            "blocked_members_total": sum(
                item["disposition"]
                in {"blocked_member", "blocked_due_archive_policy"}
                for item in safe_records
            ),
            "expanded_bytes_total": expanded_total,
            "member_inventory": safe_records,
            "all_members_accounted": len(safe_records) == len(infos),
            "silent_member_omission_allowed": False,
            "nested_archive_recursion_performed": False,
            "private_member_names_included": False,
            "private_values_included": False,
        }
        return ArchiveExpansionResult(
            manifest=manifest,
            promoted_members=tuple(promoted),
        )

    @staticmethod
    def _blocked(
        *,
        archive_ref: str,
        normalization_run_id: str,
        parent_document_ref: str,
        reasons: list[str],
    ) -> ArchiveExpansionResult:
        return ArchiveExpansionResult(
            manifest={
                "schema_version": ARCHIVE_SOURCE_MANIFEST_SCHEMA_VERSION,
                "profile_id": ARCHIVE_SOURCE_PROFILE_ID,
                "archive_ref": archive_ref,
                "normalization_run_id": normalization_run_id,
                "parent_document_ref": parent_document_ref,
                "terminal_status": "blocked",
                "reason_codes": sorted(set(reasons)),
                "members_total": 0,
                "promoted_members_total": 0,
                "signature_sidecars_total": 0,
                "blocked_members_total": 0,
                "expanded_bytes_total": 0,
                "member_inventory": [],
                "all_members_accounted": False,
                "silent_member_omission_allowed": False,
                "nested_archive_recursion_performed": False,
                "private_member_names_included": False,
                "private_values_included": False,
            },
            promoted_members=(),
        )


def _normalized_member_name(
    value: str, *, max_characters: int
) -> tuple[str, list[str]]:
    rendered = str(value or "").replace("\\", "/")
    reasons: list[str] = []
    if not rendered or "\x00" in rendered:
        reasons.append("zip_member_name_invalid")
    if len(rendered) > max_characters:
        reasons.append("zip_member_path_budget_exceeded")
    if rendered.startswith("/") or rendered.startswith("//"):
        reasons.append("zip_absolute_member_path_forbidden")
    if re.match(r"^[A-Za-z]:", rendered):
        reasons.append("zip_drive_member_path_forbidden")
    path = PurePosixPath(rendered)
    if any(part in {"", ".", ".."} for part in path.parts):
        reasons.append("zip_member_path_traversal_forbidden")
    return str(path), sorted(set(reasons))


def _member_file_type(info: Any) -> str:
    if info.is_dir():
        return "directory"
    mode = int(info.external_attr) >> 16
    if not mode:
        return "regular"
    kind = stat.S_IFMT(mode)
    if kind in {0, stat.S_IFREG}:
        return "regular"
    if kind == stat.S_IFLNK:
        return "symlink"
    if kind == stat.S_IFDIR:
        return "directory"
    return "special"
