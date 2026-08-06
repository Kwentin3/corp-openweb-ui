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
    CANONICAL_RETENTION_CLASSES,
    PURGE_STATUSES,
    STORAGE_BACKENDS,
    VALIDATION_STATUSES,
    VISIBILITIES,
    ArtifactAccessContext,
    CanonicalActivationReceipt,
    CanonicalVersionRecord,
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

    def put_records_atomic(
        self, records: list[ArtifactRecord]
    ) -> list[ArtifactRecord]:
        """Persist one physical artifact graph or none of it.

        Payload files are removed when the SQLite transaction fails. Existing
        immutable records may participate only when their bytes are identical.
        """

        if not records:
            return []
        artifact_ids = [record.artifact_id for record in records]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ArtifactStoreError(
                "artifact_immutable", "Atomic artifact ids must be unique"
            )
        prepared: list[tuple[ArtifactRecord, str | None, Any, str | None, int | None]] = []
        created_payloads: list[Path] = []
        with self._connect() as conn:
            existing_rows = {
                str(row["artifact_id"]): row
                for row in conn.execute(
                    f"SELECT * FROM artifact_records WHERE artifact_id IN ({','.join('?' for _ in artifact_ids)})",
                    tuple(artifact_ids),
                ).fetchall()
            }
        for record in records:
            self._validate_record(record)
            existing = existing_rows.get(record.artifact_id)
            if existing is not None:
                stored = _row_to_record(existing)
                if stored.lifecycle_status == "purged":
                    raise ArtifactStoreError(
                        "artifact_purged", "Purged artifact ids cannot be restored"
                    )
                incoming_payload = record.payload
                existing_payload = self.read_payload(stored)
                if incoming_payload is None and record.payload_ref == stored.payload_ref:
                    incoming_payload = existing_payload
                if _immutable_record_material(
                    stored, existing_payload
                ) != _immutable_record_material(record, incoming_payload):
                    raise ArtifactStoreError(
                        "artifact_immutable",
                        "Existing artifact ids cannot be overwritten with different content",
                    )
                prepared.append(
                    (
                        stored,
                        stored.payload_ref,
                        stored.payload,
                        str(existing["checksum_sha256"] or "") or None,
                        existing["payload_size_bytes"],
                    )
                )
                continue
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
                    created_payloads.append(self._payload_path_from_ref(payload_ref))
                    payload_inline = None
            prepared.append(
                (record, payload_ref, payload_inline, checksum, size_bytes)
            )
        try:
            with self._connect(immediate=True) as conn:
                for record, payload_ref, payload_inline, checksum, size_bytes in prepared:
                    if record.artifact_id in existing_rows:
                        continue
                    self._insert_record(
                        conn,
                        record=record,
                        payload_ref=payload_ref,
                        payload_inline=payload_inline,
                        checksum=checksum,
                        size_bytes=size_bytes,
                    )
        except Exception:
            for payload_path in created_payloads:
                if payload_path.exists():
                    payload_path.unlink()
            raise
        stored_records: list[ArtifactRecord] = []
        for artifact_id in artifact_ids:
            stored = self.get_record_unchecked(artifact_id)
            if stored is None:
                raise ArtifactStoreError(
                    "artifact_not_found", "Atomic artifact graph was not stored"
                )
            stored_records.append(stored)
        return stored_records

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

    def reserve_canonical_version(
        self,
        *,
        context: ArtifactAccessContext,
        document_id: str,
        source_artifact_ref: str,
        schema_version: str,
        normalizer_version: str,
        source_sha256: str,
        canonical_root_sha256: str,
        retention_class: str,
    ) -> CanonicalVersionRecord:
        """Reserve one immutable cross-run version in authenticated document scope."""

        self._validate_canonical_context(context, require_private=False)
        if retention_class not in CANONICAL_RETENTION_CLASSES:
            raise ArtifactStoreError(
                "canonical_retention_class_invalid",
                "Canonical retention class is not configured",
            )
        if not document_id or not source_artifact_ref:
            raise ArtifactStoreError(
                "canonical_source_scope_mismatch",
                "Canonical document and source refs are required",
            )
        created_at = utc_now_iso()
        with self._connect(immediate=True) as conn:
            source_row = conn.execute(
                "SELECT * FROM artifact_records WHERE artifact_id = ?",
                (source_artifact_ref,),
            ).fetchone()
            if source_row is None:
                raise ArtifactStoreError(
                    "artifact_not_found", "Canonical source artifact was not found"
                )
            source_record = _row_to_record(source_row)
            self._validate_record_context(
                source_record, context, require_run=True, require_private=False
            )
            if source_record.document_id != document_id:
                raise ArtifactStoreError(
                    "canonical_source_scope_mismatch",
                    "Canonical document does not match its source artifact",
                )
            scope_key = self._canonical_document_scope_key(context, document_id)
            existing = conn.execute(
                """
                SELECT * FROM canonical_versions
                WHERE document_scope_key = ? AND normalization_run_id = ?
                """,
                (scope_key, context.normalization_run_id),
            ).fetchone()
            if existing is not None:
                version = _row_to_canonical_version(existing)
                if (
                    version.canonical_root_sha256 == canonical_root_sha256
                    and version.source_artifact_ref == source_artifact_ref
                    and version.schema_version == schema_version
                    and version.normalizer_version == normalizer_version
                ):
                    return version
                raise ArtifactStoreError(
                    "artifact_immutable",
                    "A processing run cannot publish two canonical versions",
                )
            latest_number = conn.execute(
                """
                SELECT MAX(canonical_version_number) AS maximum_version_number
                FROM canonical_versions
                WHERE document_scope_key = ?
                """,
                (scope_key,),
            ).fetchone()
            previous = conn.execute(
                """
                SELECT * FROM canonical_versions
                WHERE document_scope_key = ? AND status != 'PURGED'
                ORDER BY canonical_version_number DESC LIMIT 1
                """,
                (scope_key,),
            ).fetchone()
            maximum_version_number = (
                int(latest_number["maximum_version_number"])
                if latest_number is not None
                and latest_number["maximum_version_number"] is not None
                else 0
            )
            version_number = maximum_version_number + 1
            previous_ref = (
                str(previous["canonical_version_id"])
                if previous is not None
                else None
            )
            version_id = f"canver_{secrets.token_urlsafe(24)}"
            conn.execute(
                """
                INSERT INTO canonical_versions(
                    canonical_version_id, document_scope_key, document_id,
                    source_artifact_ref, canonical_version_number,
                    schema_version, normalizer_version, source_sha256,
                    canonical_root_sha256, previous_version_ref, status,
                    created_at, activated_at, retention_class,
                    normalization_run_id, manifest_ref, user_id, case_id,
                    chat_id, workspace_model_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CANDIDATE', ?, NULL,
                          ?, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    scope_key,
                    document_id,
                    source_artifact_ref,
                    version_number,
                    schema_version,
                    normalizer_version,
                    source_sha256,
                    canonical_root_sha256,
                    previous_ref,
                    created_at,
                    retention_class,
                    context.normalization_run_id,
                    context.user_id,
                    context.case_id,
                    context.chat_id,
                    context.workspace_model_id,
                ),
            )
            row = conn.execute(
                "SELECT * FROM canonical_versions WHERE canonical_version_id = ?",
                (version_id,),
            ).fetchone()
        if row is None:
            raise ArtifactStoreError(
                "artifact_not_found", "Canonical version reservation failed"
            )
        return _row_to_canonical_version(row)

    def finalize_canonical_version(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_version_id: str,
        manifest_ref: str,
        components: list[dict[str, Any]],
    ) -> CanonicalVersionRecord:
        """Bind an immutable physical graph and promote CANDIDATE to VALIDATED."""

        self._validate_canonical_context(context, require_private=False)
        if not components:
            raise ArtifactStoreError(
                "canonical_chunk_missing", "Canonical physical graph is empty"
            )
        with self._connect(immediate=True) as conn:
            version_row = conn.execute(
                "SELECT * FROM canonical_versions WHERE canonical_version_id = ?",
                (canonical_version_id,),
            ).fetchone()
            if version_row is None:
                raise ArtifactStoreError(
                    "artifact_not_found", "Canonical version was not found"
                )
            self._validate_canonical_version_scope(
                version_row, context, require_run=True, require_private=False
            )
            if version_row["status"] not in {"CANDIDATE", "VALIDATED"}:
                raise ArtifactStoreError(
                    "artifact_immutable",
                    "Only a candidate canonical version can be finalized",
                )
            existing_components = conn.execute(
                """
                SELECT component_kind, component_key, artifact_ref,
                       content_sha256, ordinal
                FROM canonical_version_components
                WHERE canonical_version_id = ?
                ORDER BY ordinal, component_kind, component_key
                """,
                (canonical_version_id,),
            ).fetchall()
            normalized = sorted(
                [
                    (
                        str(item["component_kind"]),
                        str(item["component_key"]),
                        str(item["artifact_ref"]),
                        str(item["content_sha256"]),
                        int(item["ordinal"]),
                    )
                    for item in components
                ],
                key=lambda item: (item[4], item[0], item[1]),
            )
            if existing_components:
                stored = [
                    (
                        str(item["component_kind"]),
                        str(item["component_key"]),
                        str(item["artifact_ref"]),
                        str(item["content_sha256"]),
                        int(item["ordinal"]),
                    )
                    for item in existing_components
                ]
                if stored != normalized or str(version_row["manifest_ref"]) != manifest_ref:
                    raise ArtifactStoreError(
                        "artifact_immutable",
                        "Finalized canonical component graph is immutable",
                    )
                return _row_to_canonical_version(version_row)
            for kind, key, artifact_ref, expected_sha256, ordinal in normalized:
                artifact_row = conn.execute(
                    "SELECT * FROM artifact_records WHERE artifact_id = ?",
                    (artifact_ref,),
                ).fetchone()
                if artifact_row is None:
                    raise ArtifactStoreError(
                        "canonical_chunk_missing",
                        "Canonical component artifact is missing",
                    )
                artifact_record = _row_to_record(artifact_row)
                self._validate_record_context(
                    artifact_record,
                    context,
                    require_run=True,
                    require_private=False,
                )
                if str(artifact_row["checksum_sha256"] or "") != expected_sha256:
                    raise ArtifactStoreError(
                        "canonical_chunk_hash_mismatch",
                        "Canonical component checksum does not match",
                    )
                conn.execute(
                    """
                    INSERT INTO canonical_version_components(
                        canonical_version_id, component_kind, component_key,
                        artifact_ref, content_sha256, ordinal
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        canonical_version_id,
                        kind,
                        key,
                        artifact_ref,
                        expected_sha256,
                        ordinal,
                    ),
                )
            if not any(item[2] == manifest_ref for item in normalized):
                raise ArtifactStoreError(
                    "canonical_chunk_missing",
                    "Canonical manifest is not part of its physical graph",
                )
            conn.execute(
                """
                UPDATE canonical_versions
                SET status = 'VALIDATED', manifest_ref = ?
                WHERE canonical_version_id = ?
                """,
                (manifest_ref, canonical_version_id),
            )
            row = conn.execute(
                "SELECT * FROM canonical_versions WHERE canonical_version_id = ?",
                (canonical_version_id,),
            ).fetchone()
        if row is None:
            raise ArtifactStoreError(
                "artifact_not_found", "Canonical version finalization failed"
            )
        return _row_to_canonical_version(row)

    def abort_canonical_candidate(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_version_id: str,
        component_artifact_ids: list[str],
    ) -> None:
        """Terminally purge only an unlinked candidate's streamed components."""

        self._validate_canonical_context(context, require_private=False)
        artifact_ids = sorted(set(component_artifact_ids))
        records: list[ArtifactRecord] = []
        transition_at = utc_now_iso()
        with self._connect(immediate=True) as conn:
            version_row = conn.execute(
                "SELECT * FROM canonical_versions WHERE canonical_version_id = ?",
                (canonical_version_id,),
            ).fetchone()
            if version_row is None:
                raise ArtifactStoreError(
                    "artifact_not_found", "Canonical candidate was not found"
                )
            self._validate_canonical_version_scope(
                version_row, context, require_run=True, require_private=False
            )
            if str(version_row["status"]) != "CANDIDATE":
                raise ArtifactStoreError(
                    "artifact_immutable", "Only an unfinalized candidate can be aborted"
                )
            linked = conn.execute(
                "SELECT 1 FROM canonical_version_components WHERE canonical_version_id = ? LIMIT 1",
                (canonical_version_id,),
            ).fetchone()
            active = conn.execute(
                "SELECT 1 FROM canonical_active_pointers WHERE active_version_id = ? LIMIT 1",
                (canonical_version_id,),
            ).fetchone()
            if linked is not None or active is not None:
                raise ArtifactStoreError(
                    "artifact_immutable", "Linked or active canonical state cannot be aborted"
                )
            for artifact_id in artifact_ids:
                row = conn.execute(
                    "SELECT * FROM artifact_records WHERE artifact_id = ?",
                    (artifact_id,),
                ).fetchone()
                if row is None:
                    continue
                record = _row_to_record(row)
                self._validate_record_context(
                    record, context, require_run=True, require_private=False
                )
                referenced = conn.execute(
                    "SELECT 1 FROM canonical_version_components WHERE artifact_ref = ? LIMIT 1",
                    (artifact_id,),
                ).fetchone()
                if referenced is not None:
                    raise ArtifactStoreError(
                        "artifact_immutable", "A linked canonical component cannot be aborted"
                    )
                conn.execute(
                    """
                    UPDATE artifact_records
                    SET lifecycle_status = 'purge_pending',
                        purge_status = 'purge_pending', updated_at = ?
                    WHERE artifact_id = ?
                    """,
                    (transition_at, artifact_id),
                )
                records.append(record)
        for record in records:
            self._delete_payload(record)
        with self._connect(immediate=True) as conn:
            for record in records:
                conn.execute(
                    """
                    UPDATE artifact_records
                    SET lifecycle_status = 'purged', purge_status = 'purged',
                        storage_backend = 'none_tombstone', payload_ref = NULL,
                        payload_inline_json = NULL, purged_at = ?, updated_at = ?
                    WHERE artifact_id = ?
                      AND lifecycle_status = 'purge_pending'
                    """,
                    (transition_at, transition_at, record.artifact_id),
                )
            conn.execute(
                """
                UPDATE canonical_versions
                SET status = 'PURGED', manifest_ref = NULL
                WHERE canonical_version_id = ? AND status = 'CANDIDATE'
                """,
                (canonical_version_id,),
            )

    def list_canonical_versions(
        self, *, context: ArtifactAccessContext, document_id: str
    ) -> list[CanonicalVersionRecord]:
        self._validate_canonical_context(context, require_private=True)
        scope = self._canonical_scope(context, document_id)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM canonical_versions
                WHERE {scope.predicate} AND status != 'PURGED'
                ORDER BY canonical_version_number ASC
                """,
                scope.parameters,
            ).fetchall()
        return [_row_to_canonical_version(row) for row in rows]

    def get_canonical_version(
        self, *, context: ArtifactAccessContext, canonical_version_id: str
    ) -> CanonicalVersionRecord:
        self._validate_canonical_context(context, require_private=True)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM canonical_versions WHERE canonical_version_id = ?",
                (canonical_version_id,),
            ).fetchone()
        if row is None:
            raise ArtifactStoreError(
                "artifact_not_found", "Canonical version was not found"
            )
        self._validate_canonical_version_scope(
            row, context, require_run=False, require_private=True
        )
        if str(row["status"]) in {"CANDIDATE", "PURGED"}:
            raise ArtifactStoreError(
                "canonical_version_not_active",
                "Canonical version is not readable",
            )
        return _row_to_canonical_version(row)

    def get_canonical_version_by_manifest(
        self, *, context: ArtifactAccessContext, manifest_ref: str
    ) -> CanonicalVersionRecord:
        self._validate_canonical_context(context, require_private=True)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM canonical_versions WHERE manifest_ref = ?",
                (manifest_ref,),
            ).fetchone()
        if row is None:
            raise ArtifactStoreError(
                "artifact_not_found", "Canonical manifest was not registered"
            )
        self._validate_canonical_version_scope(
            row, context, require_run=False, require_private=True
        )
        if str(row["status"]) in {"CANDIDATE", "PURGED"}:
            raise ArtifactStoreError(
                "canonical_version_not_active", "Canonical manifest is not readable"
            )
        return _row_to_canonical_version(row)

    def get_active_canonical_version(
        self, *, context: ArtifactAccessContext, document_id: str
    ) -> CanonicalVersionRecord:
        self._validate_canonical_context(context, require_private=True)
        scope = self._canonical_scope(context, document_id)
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT v.*
                FROM canonical_active_pointers p
                JOIN canonical_versions v
                  ON v.canonical_version_id = p.active_version_id
                WHERE {scope.predicate.replace('document_id', 'v.document_id')}
                  AND p.document_scope_key = v.document_scope_key
                """,
                scope.parameters,
            ).fetchone()
        if row is None:
            raise ArtifactStoreError(
                "canonical_version_not_active", "No active canonical version exists"
            )
        self._validate_canonical_version_scope(
            row, context, require_run=False, require_private=True
        )
        if str(row["status"]) != "ACTIVE":
            raise ArtifactStoreError(
                "canonical_version_not_active", "Canonical pointer is not active"
            )
        return _row_to_canonical_version(row)

    def activate_canonical_version(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_version_id: str,
        expected_previous_version_id: str | None,
        actor: str,
        reason: str,
        operation: str = "ACTIVATE",
    ) -> CanonicalActivationReceipt:
        self._validate_canonical_context(context, require_private=True)
        if operation not in {"ACTIVATE", "ROLLBACK"} or not actor or not reason:
            raise ArtifactStoreError(
                "canonical_pointer_conflict",
                "Activation operation, actor and reason are required",
            )
        transition_at = utc_now_iso()
        with self._connect(immediate=True) as conn:
            target = conn.execute(
                "SELECT * FROM canonical_versions WHERE canonical_version_id = ?",
                (canonical_version_id,),
            ).fetchone()
            if target is None:
                raise ArtifactStoreError(
                    "artifact_not_found", "Canonical activation target was not found"
                )
            self._validate_canonical_version_scope(
                target, context, require_run=False, require_private=True
            )
            if str(target["status"]) not in {"VALIDATED", "ACTIVE", "SUPERSEDED"}:
                raise ArtifactStoreError(
                    "canonical_version_not_active",
                    "Only a validated canonical version can be activated",
                )
            component_row = conn.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN a.artifact_id IS NULL
                                 OR a.lifecycle_status IN ('expired','purge_pending','purged','blocked','privacy_failed')
                                 OR a.validation_status != 'validated'
                                THEN 1 ELSE 0 END) AS invalid
                FROM canonical_version_components c
                LEFT JOIN artifact_records a ON a.artifact_id = c.artifact_ref
                WHERE c.canonical_version_id = ?
                """,
                (canonical_version_id,),
            ).fetchone()
            if (
                component_row is None
                or int(component_row["total"] or 0) == 0
                or int(component_row["invalid"] or 0) != 0
            ):
                raise ArtifactStoreError(
                    "canonical_chunk_missing",
                    "Canonical activation target has an incomplete physical graph",
                )
            scope_key = str(target["document_scope_key"])
            pointer = conn.execute(
                "SELECT active_version_id FROM canonical_active_pointers WHERE document_scope_key = ?",
                (scope_key,),
            ).fetchone()
            current = str(pointer["active_version_id"]) if pointer is not None else None
            if current == canonical_version_id:
                status = "no_op"
            else:
                if current != expected_previous_version_id:
                    raise ArtifactStoreError(
                        "canonical_pointer_conflict",
                        "Canonical active pointer changed before activation",
                    )
                if current is not None:
                    conn.execute(
                        """
                        UPDATE canonical_versions
                        SET status = 'SUPERSEDED', retention_class = 'SUPERSEDED_CANONICAL'
                        WHERE canonical_version_id = ? AND status = 'ACTIVE'
                        """,
                        (current,),
                    )
                conn.execute(
                    """
                    UPDATE canonical_versions
                    SET status = 'ACTIVE', activated_at = ?,
                        retention_class = 'ACTIVE_CANONICAL'
                    WHERE canonical_version_id = ?
                    """,
                    (transition_at, canonical_version_id),
                )
                conn.execute(
                    """
                    INSERT INTO canonical_active_pointers(
                        document_scope_key, active_version_id, updated_at
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(document_scope_key) DO UPDATE SET
                        active_version_id = excluded.active_version_id,
                        updated_at = excluded.updated_at
                    """,
                    (scope_key, canonical_version_id, transition_at),
                )
                status = "changed"
            receipt_id = f"canreceipt_{secrets.token_urlsafe(24)}"
            context_fingerprint = self._canonical_context_fingerprint(context)
            conn.execute(
                """
                INSERT INTO canonical_activation_receipts(
                    receipt_id, operation, status, document_scope_key,
                    document_id, canonical_version_id,
                    previous_active_version_id, activated_at, actor, reason,
                    context_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    receipt_id,
                    operation,
                    status,
                    scope_key,
                    str(target["document_id"]),
                    canonical_version_id,
                    current,
                    transition_at,
                    actor,
                    reason,
                    context_fingerprint,
                ),
            )
        return CanonicalActivationReceipt(
            receipt_id=receipt_id,
            operation=operation,
            status=status,
            document_id=str(target["document_id"]),
            canonical_version_id=canonical_version_id,
            previous_active_version_id=current,
            activated_at=transition_at,
            actor=actor,
            reason=reason,
            context_fingerprint=context_fingerprint,
        )

    def rollback_canonical_version(
        self,
        *,
        context: ArtifactAccessContext,
        target_version_id: str,
        expected_current_version_id: str,
        actor: str,
        reason: str,
    ) -> CanonicalActivationReceipt:
        return self.activate_canonical_version(
            context=context,
            canonical_version_id=target_version_id,
            expected_previous_version_id=expected_current_version_id,
            actor=actor,
            reason=reason,
            operation="ROLLBACK",
        )

    def list_canonical_components(
        self, *, context: ArtifactAccessContext, canonical_version_id: str
    ) -> list[dict[str, Any]]:
        self.get_canonical_version(
            context=context, canonical_version_id=canonical_version_id
        )
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT component_kind, component_key, artifact_ref,
                       content_sha256, ordinal
                FROM canonical_version_components
                WHERE canonical_version_id = ?
                ORDER BY ordinal, component_kind, component_key
                """,
                (canonical_version_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def read_canonical_component(
        self,
        *,
        context: ArtifactAccessContext,
        canonical_version_id: str,
        component_kind: str,
        component_key: str,
    ) -> Any:
        self.get_canonical_version(
            context=context, canonical_version_id=canonical_version_id
        )
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT a.*, c.content_sha256
                FROM canonical_version_components c
                JOIN artifact_records a ON a.artifact_id = c.artifact_ref
                WHERE c.canonical_version_id = ?
                  AND c.component_kind = ? AND c.component_key = ?
                """,
                (canonical_version_id, component_kind, component_key),
            ).fetchone()
        if row is None:
            raise ArtifactStoreError(
                "canonical_chunk_missing", "Canonical component was not found"
            )
        record = _row_to_record(row)
        self._validate_record_context(
            record, context, require_run=False, require_private=True
        )
        if str(row["checksum_sha256"] or "") != str(row["content_sha256"]):
            raise ArtifactStoreError(
                "canonical_chunk_hash_mismatch",
                "Canonical component checksum changed",
            )
        return self.read_payload(record)

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
                component_versions = conn.execute(
                    """
                    SELECT canonical_version_id
                    FROM canonical_version_components
                    WHERE artifact_ref = ?
                    """,
                    (record.artifact_id,),
                ).fetchall()
                conn.execute(
                    "DELETE FROM canonical_version_components WHERE artifact_ref = ?",
                    (record.artifact_id,),
                )
                for component_version in component_versions:
                    version_id = str(component_version["canonical_version_id"])
                    remaining = conn.execute(
                        """
                        SELECT 1 FROM canonical_version_components
                        WHERE canonical_version_id = ? LIMIT 1
                        """,
                        (version_id,),
                    ).fetchone()
                    if remaining is None:
                        conn.execute(
                            """
                            DELETE FROM canonical_active_pointers
                            WHERE active_version_id = ?
                            """,
                            (version_id,),
                        )
                        conn.execute(
                            """
                            UPDATE canonical_versions
                            SET status = 'PURGED', manifest_ref = NULL
                            WHERE canonical_version_id = ?
                            """,
                            (version_id,),
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
    def _validate_canonical_context(
        context: ArtifactAccessContext, *, require_private: bool
    ) -> None:
        if not isinstance(context, ArtifactAccessContext):
            raise ArtifactStoreError(
                "artifact_scope_unverified", "Trusted ArtifactAccessContext is required"
            )
        if not str(context.user_id or "").strip() or not str(
            context.normalization_run_id or ""
        ).strip():
            raise ArtifactStoreError(
                "artifact_scope_unverified",
                "Canonical user and processing-run context are required",
            )
        if not context.case_id and not context.chat_id:
            raise ArtifactStoreError(
                "artifact_scope_unverified",
                "Canonical case or chat context is required",
            )
        if require_private and not context.allow_private:
            raise ArtifactStoreError(
                "artifact_access_denied", "Private canonical access was not requested"
            )

    @classmethod
    def _canonical_scope(
        cls, context: ArtifactAccessContext, document_id: str
    ) -> _LifecycleScope:
        cls._validate_canonical_context(context, require_private=True)
        if not document_id:
            raise ArtifactStoreError(
                "artifact_scope_unverified", "Canonical document context is required"
            )
        if context.case_id:
            return _LifecycleScope(
                predicate=(
                    "user_id = ? AND case_id = ? AND workspace_model_id IS ? "
                    "AND document_id = ?"
                ),
                parameters=(
                    context.user_id,
                    context.case_id,
                    context.workspace_model_id,
                    document_id,
                ),
            )
        return _LifecycleScope(
            predicate=(
                "user_id = ? AND case_id IS NULL AND chat_id = ? "
                "AND workspace_model_id IS ? AND document_id = ?"
            ),
            parameters=(
                context.user_id,
                context.chat_id,
                context.workspace_model_id,
                document_id,
            ),
        )

    @classmethod
    def _canonical_document_scope_key(
        cls, context: ArtifactAccessContext, document_id: str
    ) -> str:
        cls._validate_canonical_context(context, require_private=False)
        scope = {
            "user_id": context.user_id,
            "case_id": context.case_id,
            "chat_id": None if context.case_id else context.chat_id,
            "workspace_model_id": context.workspace_model_id,
            "document_id": document_id,
        }
        return hashlib.sha256(_json_bytes(scope)).hexdigest()

    @staticmethod
    def _canonical_context_fingerprint(context: ArtifactAccessContext) -> str:
        return hashlib.sha256(
            _json_bytes(
                {
                    "user_id": context.user_id,
                    "case_id": context.case_id,
                    "chat_id": None if context.case_id else context.chat_id,
                    "workspace_model_id": context.workspace_model_id,
                    "normalization_run_id": context.normalization_run_id,
                }
            )
        ).hexdigest()

    @classmethod
    def _validate_canonical_version_scope(
        cls,
        row: sqlite3.Row,
        context: ArtifactAccessContext,
        *,
        require_run: bool,
        require_private: bool,
    ) -> None:
        cls._validate_canonical_context(context, require_private=require_private)
        if str(row["user_id"]) != context.user_id:
            raise ArtifactStoreError(
                "artifact_access_denied", "Canonical user context mismatch"
            )
        if row["case_id"]:
            if not context.case_id:
                raise ArtifactStoreError(
                    "artifact_scope_unverified", "Canonical case context is missing"
                )
            if str(row["case_id"]) != context.case_id:
                raise ArtifactStoreError(
                    "artifact_access_denied", "Canonical case context mismatch"
                )
        elif str(row["chat_id"] or "") != str(context.chat_id or ""):
            raise ArtifactStoreError(
                "artifact_access_denied", "Canonical chat context mismatch"
            )
        if row["workspace_model_id"] != context.workspace_model_id:
            raise ArtifactStoreError(
                "artifact_access_denied", "Canonical workspace context mismatch"
            )
        if require_run and str(row["normalization_run_id"]) != context.normalization_run_id:
            raise ArtifactStoreError(
                "artifact_access_denied", "Canonical processing-run context mismatch"
            )

    @classmethod
    def _validate_record_context(
        cls,
        record: ArtifactRecord,
        context: ArtifactAccessContext,
        *,
        require_run: bool,
        require_private: bool,
    ) -> None:
        cls._validate_canonical_context(context, require_private=require_private)
        if record.user_id != context.user_id:
            raise ArtifactStoreError(
                "artifact_access_denied", "Artifact user context mismatch"
            )
        if record.case_id:
            if record.case_id != context.case_id:
                raise ArtifactStoreError(
                    "artifact_access_denied", "Artifact case context mismatch"
                )
        elif record.chat_id != context.chat_id:
            raise ArtifactStoreError(
                "artifact_access_denied", "Artifact chat context mismatch"
            )
        if record.workspace_model_id != context.workspace_model_id:
            raise ArtifactStoreError(
                "artifact_access_denied", "Artifact workspace context mismatch"
            )
        if require_run and record.normalization_run_id != context.normalization_run_id:
            raise ArtifactStoreError(
                "artifact_access_denied", "Artifact processing-run context mismatch"
            )
        if record.lifecycle_status in {
            "expired",
            "purge_pending",
            "purged",
            "blocked",
            "privacy_failed",
        } or record.validation_status != "validated":
            raise ArtifactStoreError(
                "artifact_blocked", "Artifact lifecycle does not permit canonical access"
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
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical_versions(
                    canonical_version_id TEXT PRIMARY KEY,
                    document_scope_key TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source_artifact_ref TEXT NOT NULL,
                    canonical_version_number INTEGER NOT NULL,
                    schema_version TEXT NOT NULL,
                    normalizer_version TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    canonical_root_sha256 TEXT NOT NULL,
                    previous_version_ref TEXT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    activated_at TEXT NULL,
                    retention_class TEXT NOT NULL,
                    normalization_run_id TEXT NOT NULL,
                    manifest_ref TEXT NULL UNIQUE,
                    user_id TEXT NOT NULL,
                    case_id TEXT NULL,
                    chat_id TEXT NULL,
                    workspace_model_id TEXT NULL,
                    UNIQUE(document_scope_key, canonical_version_number),
                    UNIQUE(document_scope_key, normalization_run_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical_version_components(
                    canonical_version_id TEXT NOT NULL,
                    component_kind TEXT NOT NULL,
                    component_key TEXT NOT NULL,
                    artifact_ref TEXT NOT NULL UNIQUE,
                    content_sha256 TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    PRIMARY KEY(
                        canonical_version_id, component_kind, component_key
                    ),
                    FOREIGN KEY(canonical_version_id)
                        REFERENCES canonical_versions(canonical_version_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical_active_pointers(
                    document_scope_key TEXT PRIMARY KEY,
                    active_version_id TEXT NOT NULL UNIQUE,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(active_version_id)
                        REFERENCES canonical_versions(canonical_version_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS canonical_activation_receipts(
                    receipt_id TEXT PRIMARY KEY,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    document_scope_key TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    canonical_version_id TEXT NOT NULL,
                    previous_active_version_id TEXT NULL,
                    activated_at TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    context_fingerprint TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_canonical_one_active
                ON canonical_versions(document_scope_key)
                WHERE status = 'ACTIVE'
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_canonical_scope_document
                ON canonical_versions(
                    user_id, case_id, chat_id, workspace_model_id,
                    document_id, canonical_version_number
                )
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

    @staticmethod
    def _insert_record(
        conn: sqlite3.Connection,
        *,
        record: ArtifactRecord,
        payload_ref: str | None,
        payload_inline: Any,
        checksum: str | None,
        size_bytes: int | None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO artifact_records(
                artifact_id, artifact_type, schema_version, case_id, chat_id,
                user_id, workspace_model_id, message_id, normalization_run_id,
                document_id, source_file_ref_json, visibility, storage_backend,
                retention_policy_json, created_at, updated_at, expires_at,
                purge_status, lifecycle_status, access_policy_json,
                validation_status, payload_kind, payload_ref,
                payload_inline_json, checksum_sha256, payload_size_bytes,
                safe_metadata_json, warning_codes_json, deleted_at, purged_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


def _row_to_canonical_version(row: sqlite3.Row) -> CanonicalVersionRecord:
    return CanonicalVersionRecord(
        canonical_version_id=str(row["canonical_version_id"]),
        document_id=str(row["document_id"]),
        source_artifact_ref=str(row["source_artifact_ref"]),
        canonical_version_number=int(row["canonical_version_number"]),
        schema_version=str(row["schema_version"]),
        normalizer_version=str(row["normalizer_version"]),
        source_sha256=str(row["source_sha256"]),
        canonical_root_sha256=str(row["canonical_root_sha256"]),
        previous_version_ref=(
            str(row["previous_version_ref"])
            if row["previous_version_ref"] is not None
            else None
        ),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        activated_at=(
            str(row["activated_at"]) if row["activated_at"] is not None else None
        ),
        retention_class=str(row["retention_class"]),
        normalization_run_id=str(row["normalization_run_id"]),
        manifest_ref=(str(row["manifest_ref"]) if row["manifest_ref"] else None),
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
