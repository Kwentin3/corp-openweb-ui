from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


ARTIFACT_SCHEMA_VERSION = "broker_reports_artifact_v0"

VISIBILITIES = {
    "chat_visible",
    "safe_internal",
    "private_case",
    "debug_ephemeral",
    "forbidden",
}

STORAGE_BACKENDS = {
    "openwebui_file",
    "openwebui_chat",
    "openwebui_knowledge",
    "project_artifact_store",
    "project_artifact_payload",
    "none_tombstone",
}

RETENTION_MODES = {
    "synthetic_dev",
    "api_smoke",
    "customer_approved_test",
    "production_case",
    "manual_purge_required",
    "expires_after_ttl",
}

LIFECYCLE_STATUSES = {
    "created",
    "validated",
    "visible_safe",
    "private_ready",
    "blocked",
    "expired",
    "purge_pending",
    "purged",
    "privacy_failed",
}

PURGE_STATUSES = {"active", "expired", "purge_pending", "purged", "blocked"}
VALIDATION_STATUSES = {"pending", "validated", "blocked", "privacy_failed"}

ARTIFACT_TYPES = {
    "source_file_ref_v0",
    "normalization_run_v0",
    "document_inventory_v0",
    "technical_readability_profile_v0",
    "taxonomy_candidates_v0",
    "normalization_blockers_v0",
    "private_normalized_text_slice_v0",
    "private_normalized_table_slice_v0",
    "chat_visible_normalization_report_v0",
    "validation_result_v0",
    "gate2_handoff_v0",
    "debug_diagnostic_v0",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RetentionPolicy:
    mode: str
    ttl_seconds: int | None
    expires_at: str | None
    source_delete_cascades: bool = True
    chat_delete_cascades: bool = True
    keep_redacted_tombstone: bool = True
    requires_manual_purge: bool = False
    explicit: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ttl_seconds": self.ttl_seconds,
            "expires_at": self.expires_at,
            "source_delete_cascades": self.source_delete_cascades,
            "chat_delete_cascades": self.chat_delete_cascades,
            "keep_redacted_tombstone": self.keep_redacted_tombstone,
            "requires_manual_purge": self.requires_manual_purge,
            "explicit": self.explicit,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RetentionPolicy":
        return cls(
            mode=str(value.get("mode") or ""),
            ttl_seconds=value.get("ttl_seconds"),
            expires_at=value.get("expires_at"),
            source_delete_cascades=bool(value.get("source_delete_cascades", True)),
            chat_delete_cascades=bool(value.get("chat_delete_cascades", True)),
            keep_redacted_tombstone=bool(value.get("keep_redacted_tombstone", True)),
            requires_manual_purge=bool(value.get("requires_manual_purge", False)),
            explicit=bool(value.get("explicit", False)),
        )


@dataclass(frozen=True)
class ArtifactAccessContext:
    user_id: str
    normalization_run_id: str
    case_id: str | None = None
    chat_id: str | None = None
    workspace_model_id: str | None = None
    allow_private: bool = False
    require_source_available: bool = False


@dataclass
class ArtifactRecord:
    artifact_id: str
    artifact_type: str
    case_id: str | None
    chat_id: str | None
    user_id: str
    normalization_run_id: str
    document_id: str | None
    source_file_ref: dict[str, Any] | None
    visibility: str
    storage_backend: str
    retention_policy: RetentionPolicy
    access_policy: dict[str, Any]
    validation_status: str
    lifecycle_status: str
    purge_status: str = "active"
    schema_version: str = ARTIFACT_SCHEMA_VERSION
    workspace_model_id: str | None = None
    message_id: str | None = None
    payload_kind: str = "inline_json"
    payload: Any = None
    payload_ref: str | None = None
    safe_metadata: dict[str, Any] = field(default_factory=dict)
    warning_codes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    expires_at: str | None = None
    deleted_at: str | None = None
    purged_at: str | None = None

    def __post_init__(self) -> None:
        if self.expires_at is None:
            self.expires_at = self.retention_policy.expires_at
