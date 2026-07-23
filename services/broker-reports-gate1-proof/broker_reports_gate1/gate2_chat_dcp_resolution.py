from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path


DCP_ARTIFACT_TYPE = "domain_context_packet_v0"


class Gate2ChatDcpResolutionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2ChatDcpResolverConfig:
    artifact_store_path: Path


class Gate2ChatDcpResolver:
    def __init__(self, config: Gate2ChatDcpResolverConfig) -> None:
        self.config = config

    def resolve(self, *, user_id: str, chat_id: str) -> str:
        owner = str(user_id or "").strip()
        chat = str(chat_id or "").strip()
        if not owner or not chat:
            raise Gate2ChatDcpResolutionError(
                "gate2_chat_dcp_scope_unverified"
            )
        with closing(sqlite3.connect(self.config.artifact_store_path)) as conn:
            rows = conn.execute(
                """
                SELECT artifact_id
                FROM artifact_records
                WHERE user_id = ?
                  AND chat_id = ?
                  AND artifact_type = ?
                  AND purge_status = 'active'
                  AND lifecycle_status NOT IN (
                      'expired', 'purge_pending', 'purged'
                  )
                ORDER BY created_at ASC, artifact_id ASC
                """,
                (owner, chat, DCP_ARTIFACT_TYPE),
            ).fetchall()
        if not rows:
            raise Gate2ChatDcpResolutionError("gate2_chat_dcp_not_found")
        if len(rows) != 1:
            raise Gate2ChatDcpResolutionError("gate2_chat_dcp_ambiguous")
        return str(rows[0][0])


class Gate2ChatDcpResolverFactory:
    def __init__(self, config: Gate2ChatDcpResolverConfig) -> None:
        self.config = config

    def create(self) -> Gate2ChatDcpResolver:
        return Gate2ChatDcpResolver(self.config)
