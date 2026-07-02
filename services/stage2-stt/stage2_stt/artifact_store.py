from __future__ import annotations

import json
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from stage2_stt.config import ArtifactStoreMode, SttConfig
from stage2_stt.contracts import (
    ArtifactAccessContextV1,
    ArtifactChainEdgeV1,
    ArtifactChainV1,
    ArtifactRecordV1,
    ArtifactRefV1,
)


FACTORY_REQUIRED = "ArtifactStoreFactory.create is the only production store entrypoint"
FORBIDDEN = "Route handlers must not instantiate SqliteArtifactStoreAdapter directly"


class ArtifactStoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ArtifactStoreAdapter(Protocol):
    def put_artifact(self, record: ArtifactRecordV1) -> ArtifactRefV1:
        ...

    def get_artifact(
        self,
        artifact_ref: str,
        user_context: ArtifactAccessContextV1,
    ) -> ArtifactRecordV1:
        ...

    def link_artifacts(self, from_ref: str, to_ref: str, transform: str) -> ArtifactChainV1:
        ...

    def list_chain(
        self,
        root_or_ref: str,
        user_context: ArtifactAccessContextV1,
    ) -> ArtifactChainV1:
        ...

    def expire_artifact(self, artifact_ref: str, reason: str) -> None:
        ...

    def delete_scope(self, scope_id: str, reason: str) -> None:
        ...

    def index_transcript(
        self,
        *,
        transcript_ref: str,
        transcript_hash: str,
        chain_id: str,
        artifact_ref: str,
        created_at: str,
        expires_at: str | None,
    ) -> None:
        ...


@dataclass(frozen=True)
class ArtifactStoreDecision:
    mode: str
    available: bool
    warnings: list[str]


def resolve_artifact_store_decision(config: SttConfig) -> ArtifactStoreDecision:
    if config.artifact_store_mode is ArtifactStoreMode.DISABLED:
        return ArtifactStoreDecision(
            mode="disabled",
            available=False,
            warnings=["artifact_store_unavailable"],
        )
    if config.artifact_store_mode is ArtifactStoreMode.SQLITE:
        return ArtifactStoreDecision(mode="sqlite", available=True, warnings=[])
    return ArtifactStoreDecision(
        mode="memory_test",
        available=True,
        warnings=["artifact_store_memory_test_only"],
    )


class ArtifactStoreFactory:
    def __init__(self, config: SttConfig) -> None:
        self.config = config

    def create(self) -> ArtifactStoreAdapter:
        if self.config.artifact_store_mode is ArtifactStoreMode.DISABLED:
            return DisabledArtifactStoreAdapter()
        if self.config.artifact_store_mode is ArtifactStoreMode.SQLITE:
            if not self.config.artifact_store_path:
                raise ArtifactStoreError(
                    "artifact_store_unavailable",
                    "SQLite artifact store path is not configured",
                )
            try:
                return SqliteArtifactStoreAdapter(Path(self.config.artifact_store_path))
            except (OSError, sqlite3.Error) as exc:
                raise ArtifactStoreError(
                    "artifact_store_unavailable",
                    "SQLite artifact store is unavailable",
                ) from exc
        raise ArtifactStoreError(
            "artifact_store_unavailable",
            "memory_test artifact store is not allowed in runtime config",
        )


class DisabledArtifactStoreAdapter:
    def put_artifact(self, record: ArtifactRecordV1) -> ArtifactRefV1:
        raise ArtifactStoreError("artifact_store_unavailable", "Artifact store is disabled")

    def get_artifact(
        self,
        artifact_ref: str,
        user_context: ArtifactAccessContextV1,
    ) -> ArtifactRecordV1:
        raise ArtifactStoreError("artifact_store_unavailable", "Artifact store is disabled")

    def link_artifacts(self, from_ref: str, to_ref: str, transform: str) -> ArtifactChainV1:
        raise ArtifactStoreError("artifact_store_unavailable", "Artifact store is disabled")

    def list_chain(
        self,
        root_or_ref: str,
        user_context: ArtifactAccessContextV1,
    ) -> ArtifactChainV1:
        raise ArtifactStoreError("artifact_store_unavailable", "Artifact store is disabled")

    def expire_artifact(self, artifact_ref: str, reason: str) -> None:
        raise ArtifactStoreError("artifact_store_unavailable", "Artifact store is disabled")

    def delete_scope(self, scope_id: str, reason: str) -> None:
        raise ArtifactStoreError("artifact_store_unavailable", "Artifact store is disabled")

    def index_transcript(
        self,
        *,
        transcript_ref: str,
        transcript_hash: str,
        chain_id: str,
        artifact_ref: str,
        created_at: str,
        expires_at: str | None,
    ) -> None:
        raise ArtifactStoreError("artifact_store_unavailable", "Artifact store is disabled")


class SqliteArtifactStoreAdapter:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._ensure_schema()

    def put_artifact(self, record: ArtifactRecordV1) -> ArtifactRefV1:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO artifact_records(
                    artifact_ref,
                    artifact_type,
                    version,
                    scope_id,
                    workspace_id,
                    user_id,
                    chat_id,
                    message_id,
                    openwebui_file_id,
                    stage2_job_id,
                    client_label,
                    project_label,
                    external_context_id,
                    tenant_id,
                    access_context_hash,
                    scope_json,
                    parent_refs_json,
                    payload_kind,
                    payload_ref,
                    payload_inline_json,
                    checksum_sha256,
                    size_bytes,
                    safe_metadata_json,
                    warnings_json,
                    retention_class,
                    created_by,
                    created_at,
                    expires_at,
                    deleted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                _record_row(record),
            )
        return record.artifact_ref

    def get_artifact(
        self,
        artifact_ref: str,
        user_context: ArtifactAccessContextV1,
    ) -> ArtifactRecordV1:
        row = self._get_record_row(artifact_ref)
        if row is None:
            raise ArtifactStoreError("artifact_not_found", "Artifact ref was not found")
        record = _row_to_record(row)
        _raise_if_expired(record.artifact_ref)
        _validate_access(record.artifact_ref.artifact_scope, user_context)
        return record

    def link_artifacts(self, from_ref: str, to_ref: str, transform: str) -> ArtifactChainV1:
        now = utc_now_iso()
        chain_id = self._chain_id_for_ref(from_ref) or self._chain_id_for_ref(to_ref)
        if chain_id is None:
            chain_id = f"chain_{secrets.token_urlsafe(24)}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO artifact_edges(chain_id, from_ref, to_ref, transform, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (chain_id, from_ref, to_ref, transform, now),
            )
        return self._list_chain_without_access(chain_id)

    def list_chain(
        self,
        root_or_ref: str,
        user_context: ArtifactAccessContextV1,
    ) -> ArtifactChainV1:
        chain_id = self._chain_id_for_ref(root_or_ref)
        if chain_id is None:
            root = self.get_artifact(root_or_ref, user_context)
            return ArtifactChainV1(
                chain_id=f"chain_unlinked_{root.artifact_ref.artifact_ref}",
                root_ref=root.artifact_ref.artifact_ref,
                latest_refs=[root.artifact_ref.artifact_ref],
                edges=[],
            )
        chain = self._list_chain_without_access(chain_id)
        self.get_artifact(chain.root_ref, user_context)
        for edge in chain.edges:
            self.get_artifact(edge.to_ref, user_context)
        return chain

    def expire_artifact(self, artifact_ref: str, reason: str) -> None:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE artifact_records SET expires_at = ? WHERE artifact_ref = ?",
                (utc_now_iso(), artifact_ref),
            )
        if cursor.rowcount == 0:
            raise ArtifactStoreError("artifact_not_found", "Artifact ref was not found")

    def delete_scope(self, scope_id: str, reason: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE artifact_records
                SET deleted_at = ?
                WHERE scope_id = ? AND deleted_at IS NULL
                """,
                (utc_now_iso(), scope_id),
            )

    def index_transcript(
        self,
        *,
        transcript_ref: str,
        transcript_hash: str,
        chain_id: str,
        artifact_ref: str,
        created_at: str,
        expires_at: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO transcript_index(
                    transcript_ref,
                    transcript_hash,
                    chain_id,
                    artifact_ref,
                    created_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (transcript_ref, transcript_hash, chain_id, artifact_ref, created_at, expires_at),
            )

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS artifact_records(
                    artifact_ref TEXT PRIMARY KEY,
                    artifact_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    scope_id TEXT NOT NULL,
                    workspace_id TEXT NULL,
                    user_id TEXT NULL,
                    chat_id TEXT NULL,
                    message_id TEXT NULL,
                    openwebui_file_id TEXT NULL,
                    stage2_job_id TEXT NULL,
                    client_label TEXT NULL,
                    project_label TEXT NULL,
                    external_context_id TEXT NULL,
                    tenant_id TEXT NULL,
                    access_context_hash TEXT NULL,
                    scope_json TEXT NOT NULL,
                    parent_refs_json TEXT NOT NULL,
                    payload_kind TEXT NOT NULL,
                    payload_ref TEXT NULL,
                    payload_inline_json TEXT NULL,
                    checksum_sha256 TEXT NULL,
                    size_bytes INTEGER NULL,
                    safe_metadata_json TEXT NOT NULL,
                    warnings_json TEXT NOT NULL,
                    retention_class TEXT NOT NULL,
                    created_by TEXT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NULL,
                    deleted_at TEXT NULL
                );

                CREATE TABLE IF NOT EXISTS artifact_edges(
                    chain_id TEXT NOT NULL,
                    from_ref TEXT NOT NULL,
                    to_ref TEXT NOT NULL,
                    transform TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS transcript_index(
                    transcript_ref TEXT PRIMARY KEY,
                    transcript_hash TEXT NOT NULL,
                    chain_id TEXT NOT NULL,
                    artifact_ref TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NULL
                );
                """
            )

    def _get_record_row(self, artifact_ref: str) -> sqlite3.Row | None:
        if not artifact_ref.startswith("art_"):
            raise ArtifactStoreError("artifact_not_found", "Artifact ref is malformed")
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT *
                FROM artifact_records
                WHERE artifact_ref = ? AND deleted_at IS NULL
                """,
                (artifact_ref,),
            ).fetchone()

    def _chain_id_for_ref(self, artifact_ref: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT chain_id
                FROM artifact_edges
                WHERE from_ref = ? OR to_ref = ?
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (artifact_ref, artifact_ref),
            ).fetchone()
        return str(row["chain_id"]) if row is not None else None

    def _list_chain_without_access(self, chain_id: str) -> ArtifactChainV1:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT from_ref, to_ref, transform, created_at
                FROM artifact_edges
                WHERE chain_id = ?
                ORDER BY created_at ASC
                """,
                (chain_id,),
            ).fetchall()
        edges = [
            ArtifactChainEdgeV1(
                from_ref=str(row["from_ref"]),
                to_ref=str(row["to_ref"]),
                transform=str(row["transform"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]
        if not edges:
            raise ArtifactStoreError("artifact_not_found", "Artifact chain was not found")
        return ArtifactChainV1(
            chain_id=chain_id,
            root_ref=edges[0].from_ref,
            latest_refs=[edges[-1].to_ref],
            edges=edges,
        )


def new_artifact_ref(
    *,
    artifact_type: str,
    artifact_scope,
    expires_at: str | None,
) -> ArtifactRefV1:
    return ArtifactRefV1(
        artifact_ref=f"art_{secrets.token_urlsafe(32)}",
        artifact_type=artifact_type,
        artifact_scope=artifact_scope,
        created_at=utc_now_iso(),
        expires_at=expires_at,
    )


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_row(record: ArtifactRecordV1) -> tuple:
    ref = record.artifact_ref
    scope = ref.artifact_scope
    return (
        ref.artifact_ref,
        ref.artifact_type,
        ref.version,
        scope.scope_id,
        scope.workspace_id,
        scope.user_id,
        scope.chat_id,
        scope.message_id,
        scope.openwebui_file_id,
        scope.stage2_job_id,
        scope.client_label,
        scope.project_label,
        scope.external_context_id,
        scope.tenant_id,
        scope.access_context_hash,
        ref.artifact_scope.model_dump_json(),
        json.dumps(record.parent_refs, sort_keys=True),
        record.payload_kind,
        record.payload_ref,
        json.dumps(record.payload_inline, sort_keys=True) if record.payload_inline is not None else None,
        record.checksum_sha256,
        record.size_bytes,
        json.dumps(record.safe_metadata, sort_keys=True),
        json.dumps(record.warnings, sort_keys=True),
        record.retention_class,
        record.created_by,
        ref.created_at,
        ref.expires_at,
    )


def _row_to_record(row: sqlite3.Row) -> ArtifactRecordV1:
    ref = ArtifactRefV1(
        artifact_ref=str(row["artifact_ref"]),
        artifact_type=str(row["artifact_type"]),
        version=str(row["version"]),
        artifact_scope=json.loads(str(row["scope_json"])),
        created_at=str(row["created_at"]),
        expires_at=row["expires_at"],
    )
    payload_inline = None
    if row["payload_inline_json"] is not None:
        payload_inline = json.loads(str(row["payload_inline_json"]))
    return ArtifactRecordV1(
        artifact_ref=ref,
        parent_refs=json.loads(str(row["parent_refs_json"])),
        payload_kind=str(row["payload_kind"]),
        payload_ref=row["payload_ref"],
        payload_inline=payload_inline,
        checksum_sha256=row["checksum_sha256"],
        size_bytes=row["size_bytes"],
        safe_metadata=json.loads(str(row["safe_metadata_json"])),
        warnings=json.loads(str(row["warnings_json"])),
        retention_class=str(row["retention_class"]),
        created_by=row["created_by"],
    )


def _raise_if_expired(ref: ArtifactRefV1) -> None:
    if ref.expires_at is None:
        return
    try:
        expires_at = datetime.fromisoformat(ref.expires_at)
    except ValueError as exc:
        raise ArtifactStoreError(
            "artifact_payload_unavailable",
            "Artifact expiry timestamp is invalid",
        ) from exc
    if expires_at <= datetime.now(timezone.utc):
        raise ArtifactStoreError("artifact_expired", "Artifact ref is expired")


def _validate_access(scope, context: ArtifactAccessContextV1) -> None:
    access_fields = (
        "user_id",
        "workspace_id",
        "chat_id",
        "message_id",
        "openwebui_file_id",
        "tenant_id",
    )
    checked = False
    for field_name in access_fields:
        stored = getattr(scope, field_name)
        if stored is None:
            continue
        checked = True
        supplied = getattr(context, field_name)
        if supplied is None:
            raise ArtifactStoreError(
                "artifact_scope_unverified",
                f"Artifact access context is missing {field_name}",
            )
        if supplied != stored:
            raise ArtifactStoreError(
                "artifact_access_denied",
                f"Artifact access context mismatch for {field_name}",
            )
    if not checked:
        raise ArtifactStoreError(
            "artifact_scope_unverified",
            "Artifact has no verifiable access context",
        )
