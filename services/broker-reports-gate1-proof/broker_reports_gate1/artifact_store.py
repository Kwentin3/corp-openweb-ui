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

from .artifact_models import (
    ARTIFACT_TYPES,
    PURGE_STATUSES,
    STORAGE_BACKENDS,
    VALIDATION_STATUSES,
    VISIBILITIES,
    ArtifactAccessContext,
    ArtifactLifecycleResult,
    ArtifactRecord,
    ArtifactStoreError,
    RetentionPolicy,
    new_artifact_id as new_artifact_id,
    utc_now_iso,
)


FACTORY_REQUIRED = "ArtifactStoreFactory.create is the only production store entrypoint"
FORBIDDEN = "Pipe and Gate 2 resolver must not instantiate SqliteArtifactStoreAdapter directly"


@dataclass(frozen=True)
class ArtifactStoreConfig:
    mode: str
    sqlite_path: Path
    payload_root: Path


@dataclass(frozen=True)
class _LifecycleScope:
    predicate: str
    parameters: tuple[Any, ...]


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
                "SELECT * FROM artifact_records WHERE artifact_id = ?",
                (record.artifact_id,),
            ).fetchone()
        if existing is not None:
            stored = _row_to_record(existing)
            if stored.lifecycle_status == "purged":
                raise ArtifactStoreError(
                    "artifact_purged", "Purged artifact ids cannot be restored"
                )
            existing_payload = self.read_payload(stored)
            incoming_payload = record.payload
            if incoming_payload is None and record.payload_ref == stored.payload_ref:
                incoming_payload = existing_payload
            if _immutable_record_material(stored, existing_payload) == _immutable_record_material(
                record, incoming_payload
            ):
                return stored
            raise ArtifactStoreError(
                "artifact_immutable",
                "Existing artifact ids cannot be overwritten with different content",
            )
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
                INSERT INTO artifact_records(
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

    def list_by_case(self, case_id: str) -> list[ArtifactRecord]:
        if not case_id:
            raise ArtifactStoreError("artifact_scope_unverified", "Artifact case context is required")
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM artifact_records
                WHERE case_id = ?
                ORDER BY created_at ASC, artifact_type ASC
                """,
                (case_id,),
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
        if (
            record.purge_status == "purge_pending"
            or record.lifecycle_status == "purge_pending"
        ):
            raise ArtifactStoreError(
                "artifact_purge_pending",
                "Artifact payload purge is pending",
            )
        if record.purge_status == "expired" or record.lifecycle_status == "expired":
            raise ArtifactStoreError("artifact_expired", "Artifact payload expired")
        if record.payload is not None:
            return record.payload
        if not record.payload_ref:
            return None
        payload_path = self._payload_path_from_ref(record.payload_ref)
        if not payload_path.exists():
            raise ArtifactStoreError("artifact_payload_unavailable", "Artifact payload file is missing")
        return json.loads(payload_path.read_text(encoding="utf-8"))

    def expire_run(
        self,
        context: ArtifactAccessContext,
        now: datetime | None = None,
    ) -> ArtifactLifecycleResult:
        scope = self._lifecycle_scope(context, required_scope="run")
        transition_at = utc_now_iso()
        current = _normalized_utc_iso(now or datetime.now(timezone.utc))
        with self._connect(immediate=True) as conn:
            self._authorize_lifecycle_scope(conn, scope)
            rows = conn.execute(
                f"""
                UPDATE artifact_records
                SET lifecycle_status = 'expired',
                    purge_status = 'expired',
                    updated_at = ?
                WHERE {scope.predicate}
                  AND expires_at IS NOT NULL
                  AND expires_at <= ?
                  AND lifecycle_status IN (
                      'validated', 'visible_safe', 'private_ready'
                  )
                  AND purge_status = 'active'
                RETURNING artifact_id
                """,
                (transition_at, *scope.parameters, current),
            ).fetchall()
        return ArtifactLifecycleResult.from_changed_ids(
            operation="expire_run",
            artifact_ids=[str(row["artifact_id"]) for row in rows],
        )

    def purge_run(
        self,
        context: ArtifactAccessContext,
    ) -> ArtifactLifecycleResult:
        return self._purge_scope(
            context=context,
            operation="purge_run",
            required_scope="run",
        )

    def purge_case(
        self,
        context: ArtifactAccessContext,
    ) -> ArtifactLifecycleResult:
        return self._purge_scope(
            context=context,
            operation="purge_case",
            required_scope="case",
        )

    def purge_chat(
        self,
        context: ArtifactAccessContext,
    ) -> ArtifactLifecycleResult:
        return self._purge_scope(
            context=context,
            operation="purge_chat",
            required_scope="chat",
            extra_predicate=(
                "COALESCE(json_extract(retention_policy_json, "
                "'$.chat_delete_cascades'), 1) = 1"
            ),
        )

    def mark_source_file_deleted(
        self,
        context: ArtifactAccessContext,
    ) -> ArtifactLifecycleResult:
        scope = self._lifecycle_scope(context, required_scope="source")
        source_file_id = str(context.source_file_id or "").strip()
        source_predicate = (
            "json_extract(source_file_ref_json, '$.openwebui_file_id') = ?"
        )
        claim_id = f"claim_{secrets.token_urlsafe(24)}"
        transition_at = utc_now_iso()
        claimed_records: list[ArtifactRecord] = []
        changed_ids: list[str] = []
        with self._connect(immediate=True) as conn:
            self._authorize_lifecycle_scope(
                conn,
                scope,
                extra_predicate=source_predicate,
                extra_parameters=(source_file_id,),
            )
            retry_rows = conn.execute(
                f"""
                UPDATE artifact_records
                SET lifecycle_claim_id = ?,
                    lifecycle_claimed_at = ?,
                    updated_at = ?
                WHERE {scope.predicate}
                  AND {source_predicate}
                  AND visibility = 'private_case'
                  AND COALESCE(
                      json_extract(
                          retention_policy_json,
                          '$.source_delete_cascades'
                      ),
                      1
                  ) = 1
                  AND lifecycle_status = 'purge_pending'
                  AND purge_status = 'purge_pending'
                  AND lifecycle_claim_id IS NULL
                RETURNING *
                """,
                (
                    claim_id,
                    transition_at,
                    transition_at,
                    *scope.parameters,
                    source_file_id,
                ),
            ).fetchall()
            claimed_rows = conn.execute(
                f"""
                UPDATE artifact_records
                SET source_file_ref_json = json_set(
                        source_file_ref_json,
                        '$.source_deleted', json('true'),
                        '$.source_delete_observed_at', ?
                    ),
                    lifecycle_status = 'purge_pending',
                    purge_status = 'purge_pending',
                    lifecycle_claim_id = ?,
                    lifecycle_claimed_at = ?,
                    updated_at = ?
                WHERE {scope.predicate}
                  AND {source_predicate}
                  AND COALESCE(
                      json_extract(source_file_ref_json, '$.source_deleted'),
                      0
                  ) != 1
                  AND visibility = 'private_case'
                  AND COALESCE(
                      json_extract(
                          retention_policy_json,
                          '$.source_delete_cascades'
                      ),
                      1
                  ) = 1
                  AND lifecycle_status IN (
                      'validated', 'visible_safe', 'private_ready', 'blocked',
                      'expired', 'privacy_failed'
                  )
                  AND purge_status NOT IN ('purged', 'purge_pending')
                RETURNING *
                """,
                (
                    transition_at,
                    claim_id,
                    transition_at,
                    transition_at,
                    *scope.parameters,
                    source_file_id,
                ),
            ).fetchall()
            claimed_records = [
                _row_to_record(row) for row in (*retry_rows, *claimed_rows)
            ]
            changed_ids.extend(record.artifact_id for record in claimed_records)
            marked_rows = conn.execute(
                f"""
                UPDATE artifact_records
                SET source_file_ref_json = json_set(
                        source_file_ref_json,
                        '$.source_deleted', json('true'),
                        '$.source_delete_observed_at', ?
                    ),
                    updated_at = ?
                WHERE {scope.predicate}
                  AND {source_predicate}
                  AND COALESCE(
                      json_extract(source_file_ref_json, '$.source_deleted'),
                      0
                  ) != 1
                  AND lifecycle_status != 'purged'
                  AND purge_status != 'purged'
                RETURNING artifact_id
                """,
                (
                    transition_at,
                    transition_at,
                    *scope.parameters,
                    source_file_id,
                ),
            ).fetchall()
            changed_ids.extend(str(row["artifact_id"]) for row in marked_rows)

        try:
            finalized = self._delete_and_finalize_claim(
                records=claimed_records,
                claim_id=claim_id,
            )
        except Exception:
            self._release_failed_claim(
                records=claimed_records,
                claim_id=claim_id,
            )
            raise
        changed_ids.extend(finalized)
        return ArtifactLifecycleResult.from_changed_ids(
            operation="mark_source_file_deleted",
            artifact_ids=changed_ids,
        )

    def _purge_scope(
        self,
        *,
        context: ArtifactAccessContext,
        operation: str,
        required_scope: str,
        extra_predicate: str | None = None,
    ) -> ArtifactLifecycleResult:
        scope = self._lifecycle_scope(context, required_scope=required_scope)
        claim_id = f"claim_{secrets.token_urlsafe(24)}"
        transition_at = utc_now_iso()
        predicates = [scope.predicate]
        if extra_predicate:
            predicates.append(extra_predicate)
        with self._connect(immediate=True) as conn:
            self._authorize_lifecycle_scope(conn, scope)
            rows = conn.execute(
                f"""
                UPDATE artifact_records
                SET lifecycle_status = 'purge_pending',
                    purge_status = 'purge_pending',
                    lifecycle_claim_id = ?,
                    lifecycle_claimed_at = ?,
                    updated_at = ?
                WHERE {' AND '.join(predicates)}
                  AND (
                      (
                          lifecycle_status IN (
                              'validated', 'visible_safe', 'private_ready',
                              'blocked', 'expired', 'privacy_failed'
                          )
                          AND purge_status NOT IN ('purged', 'purge_pending')
                      )
                      OR (
                          lifecycle_status = 'purge_pending'
                          AND purge_status = 'purge_pending'
                          AND lifecycle_claim_id IS NULL
                      )
                  )
                RETURNING *
                """,
                (
                    claim_id,
                    transition_at,
                    transition_at,
                    *scope.parameters,
                ),
            ).fetchall()
        records = [_row_to_record(row) for row in rows]
        try:
            purged_ids = self._delete_and_finalize_claim(
                records=records,
                claim_id=claim_id,
            )
        except Exception:
            self._release_failed_claim(
                records=records,
                claim_id=claim_id,
            )
            raise
        return ArtifactLifecycleResult.from_changed_ids(
            operation=operation,
            artifact_ids=purged_ids,
        )

    def _release_failed_claim(
        self,
        *,
        records: list[ArtifactRecord],
        claim_id: str,
    ) -> None:
        """Make only this failed operation's pending rows available for retry."""

        transition_at = utc_now_iso()
        with self._connect(immediate=True) as conn:
            for record in records:
                conn.execute(
                    """
                    UPDATE artifact_records
                    SET lifecycle_claim_id = NULL,
                        lifecycle_claimed_at = NULL,
                        updated_at = ?
                    WHERE artifact_id = ?
                      AND lifecycle_status = 'purge_pending'
                      AND purge_status = 'purge_pending'
                      AND lifecycle_claim_id = ?
                    """,
                    (transition_at, record.artifact_id, claim_id),
                )

    def _delete_and_finalize_claim(
        self,
        *,
        records: list[ArtifactRecord],
        claim_id: str,
    ) -> list[str]:
        purged_ids: list[str] = []
        for record in records:
            self._delete_payload(record)
            transition_at = utc_now_iso()
            with self._connect(immediate=True) as conn:
                row = conn.execute(
                    """
                    UPDATE artifact_records
                    SET lifecycle_status = 'purged',
                        purge_status = 'purged',
                        storage_backend = 'none_tombstone',
                        payload_ref = NULL,
                        payload_inline_json = NULL,
                        lifecycle_claim_id = NULL,
                        lifecycle_claimed_at = NULL,
                        purged_at = ?,
                        updated_at = ?
                    WHERE artifact_id = ?
                      AND lifecycle_status = 'purge_pending'
                      AND purge_status = 'purge_pending'
                      AND lifecycle_claim_id = ?
                    RETURNING artifact_id
                    """,
                    (
                        transition_at,
                        transition_at,
                        record.artifact_id,
                        claim_id,
                    ),
                ).fetchone()
            if row is None:
                raise ArtifactStoreError(
                    "artifact_lifecycle_claim_lost",
                    "Artifact purge claim was not owned by this operation",
                )
            purged_ids.append(str(row["artifact_id"]))
        return purged_ids

    def _lifecycle_scope(
        self,
        context: ArtifactAccessContext,
        *,
        required_scope: str,
    ) -> _LifecycleScope:
        if not isinstance(context, ArtifactAccessContext):
            raise ArtifactStoreError(
                "artifact_scope_unverified",
                "Trusted ArtifactAccessContext is required",
            )
        user_id = str(context.user_id or "").strip()
        run_id = str(context.normalization_run_id or "").strip()
        case_id = str(context.case_id or "").strip()
        chat_id = str(context.chat_id or "").strip()
        if not user_id or not run_id:
            raise ArtifactStoreError(
                "artifact_scope_unverified",
                "Artifact user and normalization run context are required",
            )
        if required_scope == "case":
            if not case_id:
                raise ArtifactStoreError(
                    "artifact_scope_unverified",
                    "Artifact case context is required",
                )
            return _LifecycleScope(
                predicate=(
                    "user_id = ? AND case_id = ? "
                    "AND workspace_model_id IS ? AND normalization_run_id = ?"
                ),
                parameters=(
                    user_id,
                    case_id,
                    context.workspace_model_id,
                    run_id,
                ),
            )
        if required_scope == "chat":
            if case_id or not chat_id:
                raise ArtifactStoreError(
                    "artifact_scope_unverified",
                    "Case-free artifact chat context is required",
                )
            return _LifecycleScope(
                predicate=(
                    "user_id = ? AND case_id IS NULL AND chat_id = ? "
                    "AND workspace_model_id IS ? AND normalization_run_id = ?"
                ),
                parameters=(
                    user_id,
                    chat_id,
                    context.workspace_model_id,
                    run_id,
                ),
            )
        if required_scope not in {"run", "source"}:
            raise ArtifactStoreError(
                "artifact_scope_unverified",
                "Artifact lifecycle scope is unsupported",
            )
        if required_scope == "source" and not str(
            context.source_file_id or ""
        ).strip():
            raise ArtifactStoreError(
                "artifact_scope_unverified",
                "Artifact source identity is required",
            )
        if case_id:
            return _LifecycleScope(
                predicate=(
                    "user_id = ? AND case_id = ? "
                    "AND workspace_model_id IS ? AND normalization_run_id = ?"
                ),
                parameters=(
                    user_id,
                    case_id,
                    context.workspace_model_id,
                    run_id,
                ),
            )
        if chat_id:
            return _LifecycleScope(
                predicate=(
                    "user_id = ? AND case_id IS NULL AND chat_id = ? "
                    "AND workspace_model_id IS ? AND normalization_run_id = ?"
                ),
                parameters=(
                    user_id,
                    chat_id,
                    context.workspace_model_id,
                    run_id,
                ),
            )
        raise ArtifactStoreError(
            "artifact_scope_unverified",
            "Artifact case or chat context is required",
        )

    @staticmethod
    def _authorize_lifecycle_scope(
        conn: sqlite3.Connection,
        scope: _LifecycleScope,
        *,
        extra_predicate: str | None = None,
        extra_parameters: tuple[Any, ...] = (),
    ) -> None:
        predicates = [scope.predicate]
        if extra_predicate:
            predicates.append(extra_predicate)
        row = conn.execute(
            f"""
            SELECT artifact_id
            FROM artifact_records
            WHERE {' AND '.join(predicates)}
            LIMIT 1
            """,
            (*scope.parameters, *extra_parameters),
        ).fetchone()
        if row is None:
            raise ArtifactStoreError(
                "artifact_access_denied",
                "Artifact lifecycle context does not own the requested scope",
            )

    @contextmanager
    def _connect(self, *, immediate: bool = False):
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.sqlite_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            if immediate:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
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
                    purged_at TEXT NULL,
                    lifecycle_claim_id TEXT NULL,
                    lifecycle_claimed_at TEXT NULL
                )
                """
            )
            existing_columns = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(artifact_records)")
            }
            if "lifecycle_claim_id" not in existing_columns:
                conn.execute(
                    "ALTER TABLE artifact_records "
                    "ADD COLUMN lifecycle_claim_id TEXT NULL"
                )
            if "lifecycle_claimed_at" not in existing_columns:
                conn.execute(
                    "ALTER TABLE artifact_records "
                    "ADD COLUMN lifecycle_claimed_at TEXT NULL"
                )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_run ON artifact_records(normalization_run_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_artifact_scope ON artifact_records(user_id, case_id, chat_id)"
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifact_lifecycle_case_run
                ON artifact_records(
                    user_id,
                    case_id,
                    workspace_model_id,
                    normalization_run_id,
                    lifecycle_status,
                    purge_status,
                    expires_at
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifact_lifecycle_chat_run
                ON artifact_records(
                    user_id,
                    chat_id,
                    workspace_model_id,
                    normalization_run_id,
                    lifecycle_status,
                    purge_status,
                    expires_at
                )
                WHERE case_id IS NULL
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifact_lifecycle_source_run
                ON artifact_records(
                    user_id,
                    case_id,
                    workspace_model_id,
                    normalization_run_id,
                    json_extract(
                        source_file_ref_json,
                        '$.openwebui_file_id'
                    )
                )
                WHERE source_file_ref_json IS NOT NULL
                """
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
        try:
            with target.open("xb") as stream:
                stream.write(payload_bytes)
        except FileExistsError as exc:
            raise ArtifactStoreError(
                "artifact_immutable",
                "Existing artifact payloads cannot be overwritten",
            ) from exc
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


def _immutable_record_material(record: ArtifactRecord, payload: Any) -> dict[str, Any]:
    """Exclude audit timestamps; lifecycle methods own the only allowed mutations."""

    return {
        "artifact_id": record.artifact_id,
        "artifact_type": record.artifact_type,
        "schema_version": record.schema_version,
        "case_id": record.case_id,
        "chat_id": record.chat_id,
        "user_id": record.user_id,
        "workspace_model_id": record.workspace_model_id,
        "message_id": record.message_id,
        "normalization_run_id": record.normalization_run_id,
        "document_id": record.document_id,
        "source_file_ref": record.source_file_ref,
        "visibility": record.visibility,
        "storage_backend": record.storage_backend,
        "retention_policy": record.retention_policy.to_dict(),
        "expires_at": record.expires_at,
        "purge_status": record.purge_status,
        "lifecycle_status": record.lifecycle_status,
        "access_policy": record.access_policy,
        "validation_status": record.validation_status,
        "payload_kind": record.payload_kind,
        "payload": payload,
        "safe_metadata": record.safe_metadata,
        "warning_codes": record.warning_codes,
        "deleted_at": record.deleted_at,
        "purged_at": record.purged_at,
    }


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_or_none(value: Any) -> str | None:
    if value is None:
        return None
    return _json(value)


def _json_bytes(value: Any) -> bytes:
    return _json(value).encode("utf-8")


def _normalized_utc_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ArtifactStoreError(
            "artifact_scope_unverified",
            "Artifact lifecycle time must be timezone-aware",
        )
    return value.astimezone(timezone.utc).isoformat()
