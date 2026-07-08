from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifact_lifecycle import assert_transition
from .artifact_models import (
    ARTIFACT_TYPES,
    PURGE_STATUSES,
    STORAGE_BACKENDS,
    VALIDATION_STATUSES,
    VISIBILITIES,
    ArtifactRecord,
    RetentionPolicy,
    utc_now_iso,
)


FACTORY_REQUIRED = "ArtifactStoreFactory.create is the only production store entrypoint"
FORBIDDEN = "Pipe and Gate 2 resolver must not instantiate SqliteArtifactStoreAdapter directly"


class ArtifactStoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ArtifactStoreConfig:
    mode: str
    sqlite_path: Path
    payload_root: Path


class ArtifactStoreFactory:
    def __init__(self, config: ArtifactStoreConfig) -> None:
        self.config = config

    def create(self) -> "SqliteArtifactStoreAdapter":
        if self.config.mode != "sqlite":
            raise ArtifactStoreError("artifact_store_unavailable", "Only sqlite ArtifactStore mode is enabled")
        return SqliteArtifactStoreAdapter(self.config.sqlite_path, self.config.payload_root)


class SqliteArtifactStoreAdapter:
    def __init__(self, sqlite_path: Path, payload_root: Path) -> None:
        self.sqlite_path = sqlite_path
        self.payload_root = payload_root
        self._ensure_schema()

    def put_record(self, record: ArtifactRecord) -> ArtifactRecord:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT lifecycle_status FROM artifact_records WHERE artifact_id = ?",
                (record.artifact_id,),
            ).fetchone()
        if existing is not None and str(existing["lifecycle_status"]) == "purged":
            raise ArtifactStoreError("artifact_purged", "Purged artifact ids cannot be restored")
        self._validate_record(record)
        payload_ref = record.payload_ref
        payload_inline = record.payload
        checksum = None
        size_bytes = None
        if record.payload is not None:
            payload_bytes = _json_bytes(record.payload)
            checksum = hashlib.sha256(payload_bytes).hexdigest()
            size_bytes = len(payload_bytes)
            if record.storage_backend == "project_artifact_payload":
                payload_ref = self._write_payload(record.artifact_id, payload_bytes)
                payload_inline = None

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO artifact_records(
                    artifact_id,
                    artifact_type,
                    schema_version,
                    case_id,
                    chat_id,
                    user_id,
                    workspace_model_id,
                    message_id,
                    normalization_run_id,
                    document_id,
                    source_file_ref_json,
                    visibility,
                    storage_backend,
                    retention_policy_json,
                    created_at,
                    updated_at,
                    expires_at,
                    purge_status,
                    lifecycle_status,
                    access_policy_json,
                    validation_status,
                    payload_kind,
                    payload_ref,
                    payload_inline_json,
                    checksum_sha256,
                    payload_size_bytes,
                    safe_metadata_json,
                    warning_codes_json,
                    deleted_at,
                    purged_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.artifact_id,
                    record.artifact_type,
                    record.schema_version,
                    record.case_id,
                    record.chat_id,
                    record.user_id,
                    record.workspace_model_id,
                    record.message_id,
                    record.normalization_run_id,
                    record.document_id,
                    _json_or_none(record.source_file_ref),
                    record.visibility,
                    record.storage_backend,
                    _json(record.retention_policy.to_dict()),
                    record.created_at,
                    record.updated_at,
                    record.expires_at,
                    record.purge_status,
                    record.lifecycle_status,
                    _json(record.access_policy),
                    record.validation_status,
                    record.payload_kind,
                    payload_ref,
                    _json_or_none(payload_inline),
                    checksum,
                    size_bytes,
                    _json(record.safe_metadata),
                    _json(record.warning_codes),
                    record.deleted_at,
                    record.purged_at,
                ),
            )
        stored = self.get_record_unchecked(record.artifact_id)
        if stored is None:
            raise ArtifactStoreError("artifact_not_found", "Artifact was not stored")
        return stored

    def get_record_unchecked(self, artifact_id: str) -> ArtifactRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM artifact_records WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    def list_by_run(self, normalization_run_id: str) -> list[ArtifactRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM artifact_records
                WHERE normalization_run_id = ?
                ORDER BY created_at ASC, artifact_type ASC
                """,
                (normalization_run_id,),
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def list_by_type(self, normalization_run_id: str, artifact_type: str) -> list[ArtifactRecord]:
        return [
            record
            for record in self.list_by_run(normalization_run_id)
            if record.artifact_type == artifact_type
        ]

    def read_payload(self, record: ArtifactRecord) -> Any:
        if record.purge_status == "purged" or record.lifecycle_status == "purged":
            raise ArtifactStoreError("artifact_purged", "Artifact payload was purged")
        if record.payload is not None:
            return record.payload
        if not record.payload_ref:
            return None
        payload_path = self._payload_path_from_ref(record.payload_ref)
        if not payload_path.exists():
            raise ArtifactStoreError("artifact_payload_unavailable", "Artifact payload file is missing")
        return json.loads(payload_path.read_text(encoding="utf-8"))

    def expire_artifacts(self, now: datetime | None = None) -> list[str]:
        current = now or datetime.now(timezone.utc)
        expired_ids: list[str] = []
        for record in self._active_records():
            if not record.expires_at:
                continue
            try:
                expires_at = datetime.fromisoformat(record.expires_at)
            except ValueError as exc:
                raise ArtifactStoreError("artifact_payload_unavailable", "Invalid artifact expires_at") from exc
            if expires_at > current:
                continue
            self._set_status(
                record.artifact_id,
                lifecycle_status="expired",
                purge_status="expired",
            )
            expired_ids.append(record.artifact_id)
        return expired_ids

    def purge_run(self, normalization_run_id: str) -> list[str]:
        purged_ids: list[str] = []
        for record in self.list_by_run(normalization_run_id):
            if record.lifecycle_status == "purged":
                continue
            self._transition_to_purge_pending(record)
            self._delete_payload(record)
            self._set_status(
                record.artifact_id,
                lifecycle_status="purged",
                purge_status="purged",
                storage_backend="none_tombstone",
                payload_ref=None,
                payload_inline=None,
                purged_at=utc_now_iso(),
            )
            purged_ids.append(record.artifact_id)
        return purged_ids

    def mark_source_file_deleted(self, *, openwebui_file_id: str) -> list[str]:
        affected: list[str] = []
        for record in self._active_records():
            source_ref = dict(record.source_file_ref or {})
            if source_ref.get("openwebui_file_id") != openwebui_file_id:
                continue
            source_ref["source_deleted"] = True
            source_ref["source_delete_observed_at"] = utc_now_iso()
            self._update_source_ref(record.artifact_id, source_ref)
            affected.append(record.artifact_id)
            if record.retention_policy.source_delete_cascades and record.visibility == "private_case":
                self._transition_to_purge_pending(record)
                self._delete_payload(record)
                self._set_status(
                    record.artifact_id,
                    lifecycle_status="purged",
                    purge_status="purged",
                    storage_backend="none_tombstone",
                    payload_ref=None,
                    payload_inline=None,
                    purged_at=utc_now_iso(),
                )
        return affected

    def purge_chat(self, *, chat_id: str) -> list[str]:
        purged: list[str] = []
        for record in self._active_records():
            if record.chat_id != chat_id or record.case_id:
                continue
            if not record.retention_policy.chat_delete_cascades:
                continue
            self._transition_to_purge_pending(record)
            self._delete_payload(record)
            self._set_status(
                record.artifact_id,
                lifecycle_status="purged",
                purge_status="purged",
                storage_backend="none_tombstone",
                payload_ref=None,
                payload_inline=None,
                purged_at=utc_now_iso(),
            )
            purged.append(record.artifact_id)
        return purged

    def purge_case(self, *, case_id: str) -> list[str]:
        purged: list[str] = []
        for record in self._active_records():
            if record.case_id != case_id:
                continue
            self._transition_to_purge_pending(record)
            self._delete_payload(record)
            self._set_status(
                record.artifact_id,
                lifecycle_status="purged",
                purge_status="purged",
                storage_backend="none_tombstone",
                payload_ref=None,
                payload_inline=None,
                purged_at=utc_now_iso(),
            )
            purged.append(record.artifact_id)
        return purged

    @contextmanager
    def _connect(self):
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.payload_root.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifact_records(
                    artifact_id TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    case_id TEXT NULL,
                    chat_id TEXT NULL,
                    user_id TEXT NOT NULL,
                    workspace_model_id TEXT NULL,
                    message_id TEXT NULL,
                    normalization_run_id TEXT NOT NULL,
                    document_id TEXT NULL,
                    source_file_ref_json TEXT NULL,
                    visibility TEXT NOT NULL,
                    storage_backend TEXT NOT NULL,
                    retention_policy_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NULL,
                    purge_status TEXT NOT NULL,
                    lifecycle_status TEXT NOT NULL,
                    access_policy_json TEXT NOT NULL,
                    validation_status TEXT NOT NULL,
                    payload_kind TEXT NOT NULL,
                    payload_ref TEXT NULL,
                    payload_inline_json TEXT NULL,
                    checksum_sha256 TEXT NULL,
                    payload_size_bytes INTEGER NULL,
                    safe_metadata_json TEXT NOT NULL,
                    warning_codes_json TEXT NOT NULL,
                    deleted_at TEXT NULL,
                    purged_at TEXT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_run ON artifact_records(normalization_run_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_scope ON artifact_records(user_id, case_id, chat_id)"
            )

    def _validate_record(self, record: ArtifactRecord) -> None:
        if record.artifact_type not in ARTIFACT_TYPES:
            raise ArtifactStoreError("artifact_blocked", f"Unsupported artifact type: {record.artifact_type}")
        if record.visibility not in VISIBILITIES:
            raise ArtifactStoreError("artifact_blocked", f"Unsupported visibility: {record.visibility}")
        if record.storage_backend not in STORAGE_BACKENDS:
            raise ArtifactStoreError("artifact_blocked", f"Unsupported storage backend: {record.storage_backend}")
        if record.purge_status not in PURGE_STATUSES:
            raise ArtifactStoreError("artifact_blocked", f"Unsupported purge status: {record.purge_status}")
        if record.validation_status not in VALIDATION_STATUSES:
            raise ArtifactStoreError("artifact_blocked", f"Unsupported validation status: {record.validation_status}")
        if not record.user_id:
            raise ArtifactStoreError("artifact_scope_unverified", "Artifact user_id is required")
        if record.storage_backend == "openwebui_knowledge" and (
            record.visibility == "private_case"
            or record.retention_policy.mode in {"customer_approved_test", "production_case"}
        ):
            raise ArtifactStoreError(
                "knowledge_storage_forbidden",
                "Knowledge is not allowed for private or customer case artifacts",
            )
        if record.visibility == "private_case" and record.storage_backend != "project_artifact_payload":
            raise ArtifactStoreError("artifact_blocked", "Private artifacts must use project_artifact_payload")

    def _write_payload(self, artifact_id: str, payload_bytes: bytes) -> str:
        if "/" in artifact_id or "\\" in artifact_id:
            raise ArtifactStoreError("artifact_not_found", "Artifact id is malformed")
        target = (self.payload_root / f"{artifact_id}.json").resolve()
        root = self.payload_root.resolve()
        if root not in target.parents:
            raise ArtifactStoreError("artifact_payload_unavailable", "Payload path escaped root")
        target.write_bytes(payload_bytes)
        return str(target.relative_to(root)).replace("\\", "/")

    def _payload_path_from_ref(self, payload_ref: str) -> Path:
        if payload_ref.startswith("/") or ".." in Path(payload_ref).parts:
            raise ArtifactStoreError("artifact_payload_unavailable", "Payload ref is malformed")
        target = (self.payload_root / payload_ref).resolve()
        root = self.payload_root.resolve()
        if root not in target.parents and target != root:
            raise ArtifactStoreError("artifact_payload_unavailable", "Payload ref escaped root")
        return target

    def _delete_payload(self, record: ArtifactRecord) -> None:
        if not record.payload_ref:
            return
        payload_path = self._payload_path_from_ref(record.payload_ref)
        if payload_path.exists():
            payload_path.unlink()

    def _active_records(self) -> list[ArtifactRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM artifact_records
                WHERE purge_status NOT IN ('purged') AND lifecycle_status NOT IN ('purged')
                ORDER BY created_at ASC
                """
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def _transition_to_purge_pending(self, record: ArtifactRecord) -> None:
        if record.lifecycle_status != "purge_pending":
            assert_transition(record.lifecycle_status, "purge_pending")
        self._set_status(record.artifact_id, lifecycle_status="purge_pending", purge_status="purge_pending")

    def _set_status(
        self,
        artifact_id: str,
        *,
        lifecycle_status: str,
        purge_status: str,
        storage_backend: str | None = None,
        payload_ref: str | None = None,
        payload_inline: Any = "__unchanged__",
        purged_at: str | None = None,
    ) -> None:
        assignments = [
            "lifecycle_status = ?",
            "purge_status = ?",
            "updated_at = ?",
        ]
        values: list[Any] = [lifecycle_status, purge_status, utc_now_iso()]
        if storage_backend is not None:
            assignments.append("storage_backend = ?")
            values.append(storage_backend)
        if payload_ref is not None or purge_status == "purged":
            assignments.append("payload_ref = ?")
            values.append(payload_ref)
        if payload_inline != "__unchanged__" or purge_status == "purged":
            assignments.append("payload_inline_json = ?")
            values.append(_json_or_none(None if payload_inline == "__unchanged__" else payload_inline))
        if purged_at is not None:
            assignments.append("purged_at = ?")
            values.append(purged_at)
        values.append(artifact_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE artifact_records SET {', '.join(assignments)} WHERE artifact_id = ?",
                values,
            )

    def _update_source_ref(self, artifact_id: str, source_ref: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE artifact_records
                SET source_file_ref_json = ?, updated_at = ?
                WHERE artifact_id = ?
                """,
                (_json(source_ref), utc_now_iso(), artifact_id),
            )


def new_artifact_id() -> str:
    return f"art_{secrets.token_urlsafe(24)}"


def _row_to_record(row: sqlite3.Row) -> ArtifactRecord:
    retention_policy = RetentionPolicy.from_dict(json.loads(str(row["retention_policy_json"])))
    return ArtifactRecord(
        artifact_id=str(row["artifact_id"]),
        artifact_type=str(row["artifact_type"]),
        schema_version=str(row["schema_version"]),
        case_id=row["case_id"],
        chat_id=row["chat_id"],
        user_id=str(row["user_id"]),
        workspace_model_id=row["workspace_model_id"],
        message_id=row["message_id"],
        normalization_run_id=str(row["normalization_run_id"]),
        document_id=row["document_id"],
        source_file_ref=json.loads(str(row["source_file_ref_json"])) if row["source_file_ref_json"] else None,
        visibility=str(row["visibility"]),
        storage_backend=str(row["storage_backend"]),
        retention_policy=retention_policy,
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
        expires_at=row["expires_at"],
        purge_status=str(row["purge_status"]),
        lifecycle_status=str(row["lifecycle_status"]),
        access_policy=json.loads(str(row["access_policy_json"])),
        validation_status=str(row["validation_status"]),
        payload_kind=str(row["payload_kind"]),
        payload_ref=row["payload_ref"],
        payload=json.loads(str(row["payload_inline_json"])) if row["payload_inline_json"] else None,
        safe_metadata=json.loads(str(row["safe_metadata_json"])),
        warning_codes=json.loads(str(row["warning_codes_json"])),
        deleted_at=row["deleted_at"],
        purged_at=row["purged_at"],
    )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return _json(value)


def _json_bytes(value: Any) -> bytes:
    return _json(value).encode("utf-8")
