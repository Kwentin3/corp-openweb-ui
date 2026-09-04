from __future__ import annotations

import base64
import binascii
import hashlib
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


ARTIFACT_SCHEMA_VERSION = "broker_reports_artifact_v0"
PRIVATE_BINARY_ARTIFACT_TYPE = "private_binary_artifact_v1"
PRIVATE_BINARY_ARTIFACT_SCHEMA_VERSION = PRIVATE_BINARY_ARTIFACT_TYPE
ARTIFACT_LIFECYCLE_RESULT_SCHEMA_VERSION = "broker_reports_artifact_lifecycle_result_v1"
CANONICAL_VERSION_SCHEMA_VERSION = "broker_reports_canonical_version_v1"
CANONICAL_ACTIVATION_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_canonical_activation_receipt_v1"
)


class ArtifactStoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def new_artifact_id() -> str:
    return f"art_{secrets.token_urlsafe(24)}"


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

CANONICAL_RETENTION_CLASSES = {
    "SOURCE",
    "ACTIVE_CANONICAL",
    "SUPERSEDED_CANONICAL",
    "EVIDENCE",
    "RAW_PROVIDER",
    "TEMPORARY",
    "PROJECTION_CACHE",
    "RESEARCH",
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
    "broker_reports_gate1_supported_pilot_profile_v1",
    "broker_reports_gate1_supported_profile_assessment_v1",
    "broker_reports_gate1_archive_source_manifest_v1",
    "broker_reports_gate1_document_memory_manifest_v1",
    "document_inventory_v0",
    "technical_readability_profile_v0",
    "taxonomy_candidates_v0",
    "normalization_blockers_v0",
    "document_source_eligibility_v0",
    "llm_document_package_v0",
    "llm_prompt_snapshot_v0",
    "llm_passport_raw_output_v0",
    "llm_clarification_prompt_snapshot_v0",
    "llm_clarification_raw_output_v0",
    "document_metadata_passport_v0",
    "document_metadata_passport_validation_v0",
    "gate1_metadata_gap_report_v0",
    "gate1_clarification_request_v0",
    "gate1_clarification_resolution_v0",
    "gate1_issue_ledger_v0",
    "document_usage_classification_v0",
    "domain_context_packet_v0",
    "private_normalized_text_slice_v0",
    "private_normalized_table_slice_v0",
    "private_normalized_source_payload_v0",
    "private_normalized_source_unit_v0",
    PRIVATE_BINARY_ARTIFACT_TYPE,
    "broker_reports_normalized_table_projection_v0",
    "broker_reports_canonical_artifact_v1",
    "broker_reports_canonical_legacy_compare_receipt_v1",
    "broker_reports_canonical_build_failure_v1",
    "broker_reports_canonical_component_v1",
    "broker_reports_canonical_activation_receipt_v1",
    "broker_reports_file_processing_batch_v1",
    "chat_visible_normalization_report_v0",
    "validation_result_v0",
    "gate2_handoff_v0",
    "broker_reports_source_fact_extraction_run_v0",
    "broker_reports_source_fact_package_v0",
    "broker_reports_source_fact_raw_output_v0",
    "broker_reports_source_facts_v0",
    "broker_reports_source_fact_validation_v0",
    "broker_reports_source_fact_selection_validation_v1",
    "broker_reports_source_fact_selection_validation_v2",
    "broker_reports_source_fact_selection_validation_v3",
    "broker_reports_issue_fact_linkage_v0",
    "broker_reports_source_fact_extraction_summary_v0",
    "broker_reports_source_unit_domain_route_v0",
    "broker_reports_source_unit_segmentation_plan_v0",
    "broker_reports_derived_source_unit_v0",
    "broker_reports_domain_extraction_package_v0",
    "broker_reports_domain_source_facts_v0",
    "broker_reports_source_fact_stitch_result_v0",
    "broker_reports_domain_source_fact_extraction_run_v0",
    "broker_reports_domain_source_fact_extraction_summary_v0",
    "broker_reports_gate3_context_manifest_v0",
    "broker_reports_answer_context_v1",
    "broker_reports_answer_context_selection_receipt_v1",
    "broker_reports_document_extraction_packet_v0",
    "broker_reports_source_value_candidate_set_v0",
    "broker_reports_candidate_relation_set_v0",
    "broker_reports_candidate_binding_validation_v0",
    "broker_reports_financial_evidence_inputs_v1",
    "broker_reports_financial_evidence_inputs_v2",
    "broker_reports_gate2_financial_context_v1",
    "broker_reports_gate2_financial_context_v2",
    "broker_reports_gate2_financial_evidence_production_receipt_v1",
    "broker_reports_gate2_financial_evidence_production_run_v1",
    "broker_reports_financial_annotations_v1",
    "broker_reports_financial_annotations_v2",
    "broker_reports_ordinary_trade_runtime_projection_v1",
    "broker_reports_ordinary_trade_runtime_projection_v2",
    "broker_reports_ordinary_trade_runtime_projection_v3",
    "broker_reports_ordinary_trade_runtime_projection_v4",
    "broker_reports_ordinary_trade_runtime_projection_v5",
    "broker_reports_ordinary_trade_mapping_case_v1",
    "broker_reports_ordinary_trade_mapping_case_v2",
    "broker_reports_gate5_supplemental_fact_v0",
    "broker_reports_gate5_gap_request_v1",
    "broker_reports_gate5_gap_request_publication_v1",
    "broker_reports_gate5_user_case_fact_v1",
    "broker_reports_authenticated_case_taxpayer_binding_v1",
    "broker_reports_declaration_external_authority_v1",
    "broker_reports_ordinary_trade_declaration_mvp_receipt_v1",
    "broker_reports_ordinary_trade_declaration_xml_v1",
    "broker_reports_gate5_declaration_scope_assertion_v0",
    "broker_reports_gate5_openwebui_case_fact_submission_v0",
    "broker_reports_gate5_openwebui_xml_artifact_v0",
    "broker_reports_gate5_openwebui_xml_delivery_receipt_v0",
    "debug_diagnostic_v0",
}


_MEDIA_TYPE = re.compile(r"^[a-z0-9][a-z0-9!#$&^_.+-]*/[a-z0-9][a-z0-9!#$&^_.+-]*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def build_private_binary_payload(*, content: bytes, media_type: str) -> dict[str, str]:
    """Build the sole JSON-safe envelope for private binary ArtifactStore data."""

    if not isinstance(content, bytes) or not content:
        raise ArtifactStoreError(
            "artifact_binary_payload_invalid", "Private binary content is required"
        )
    if not isinstance(media_type, str):
        raise ArtifactStoreError(
            "artifact_binary_payload_invalid", "Private binary media type is invalid"
        )
    normalized_media_type = media_type.strip().lower()
    if _MEDIA_TYPE.fullmatch(normalized_media_type) is None:
        raise ArtifactStoreError(
            "artifact_binary_payload_invalid", "Private binary media type is invalid"
        )
    return {
        "schema_version": PRIVATE_BINARY_ARTIFACT_SCHEMA_VERSION,
        "media_type": normalized_media_type,
        "content_base64": base64.b64encode(content).decode("ascii"),
        "content_sha256": hashlib.sha256(content).hexdigest(),
    }


def decode_private_binary_payload(payload: Any) -> tuple[bytes, str, str]:
    """Validate and decode a private binary envelope without exposing its content."""

    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "media_type",
        "content_base64",
        "content_sha256",
    }:
        raise ArtifactStoreError(
            "artifact_binary_payload_invalid", "Private binary envelope is invalid"
        )
    media_type = payload.get("media_type")
    content_base64 = payload.get("content_base64")
    content_sha256 = payload.get("content_sha256")
    if (
        payload.get("schema_version") != PRIVATE_BINARY_ARTIFACT_SCHEMA_VERSION
        or not isinstance(media_type, str)
        or _MEDIA_TYPE.fullmatch(media_type) is None
        or not isinstance(content_base64, str)
        or not isinstance(content_sha256, str)
        or _SHA256.fullmatch(content_sha256) is None
    ):
        raise ArtifactStoreError(
            "artifact_binary_payload_invalid", "Private binary envelope is invalid"
        )
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise ArtifactStoreError(
            "artifact_binary_payload_invalid", "Private binary envelope is invalid"
        ) from None
    if not content or hashlib.sha256(content).hexdigest() != content_sha256:
        raise ArtifactStoreError(
            "artifact_binary_checksum_mismatch",
            "Private binary content does not match its checksum",
        )
    return content, media_type, content_sha256


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
    source_file_id: str | None = None


@dataclass(frozen=True)
class ArtifactLifecycleResult:
    operation: str
    status: str
    artifact_ids: tuple[str, ...]
    records_changed: int
    schema_version: str = ARTIFACT_LIFECYCLE_RESULT_SCHEMA_VERSION

    @classmethod
    def from_changed_ids(
        cls,
        *,
        operation: str,
        artifact_ids: list[str] | tuple[str, ...],
    ) -> "ArtifactLifecycleResult":
        ordered = tuple(sorted(set(artifact_ids)))
        return cls(
            operation=operation,
            status="changed" if ordered else "no_op",
            artifact_ids=ordered,
            records_changed=len(ordered),
        )


@dataclass(frozen=True)
class CanonicalVersionRecord:
    canonical_version_id: str
    document_id: str
    source_artifact_ref: str
    canonical_version_number: int
    schema_version: str
    normalizer_version: str
    source_sha256: str
    canonical_root_sha256: str
    previous_version_ref: str | None
    status: str
    created_at: str
    activated_at: str | None
    retention_class: str
    normalization_run_id: str
    manifest_ref: str | None = None


@dataclass(frozen=True)
class CanonicalActivationReceipt:
    receipt_id: str
    operation: str
    status: str
    document_id: str
    canonical_version_id: str
    previous_active_version_id: str | None
    activated_at: str
    actor: str
    reason: str
    context_fingerprint: str
    schema_version: str = CANONICAL_ACTIVATION_RECEIPT_SCHEMA_VERSION

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "operation": self.operation,
            "status": self.status,
            "document_id": self.document_id,
            "canonical_version_id": self.canonical_version_id,
            "previous_active_version_id": self.previous_active_version_id,
            "activated_at": self.activated_at,
            "actor": self.actor,
            "reason": self.reason,
            "context_fingerprint": self.context_fingerprint,
            "contains_private_payload": False,
        }


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


class ArtifactStorePort(Protocol):
    """Domain-neutral persistence port used by gate runtimes and resolvers."""

    def put_record(self, record: ArtifactRecord) -> ArtifactRecord: ...

    def put_records_atomic(
        self, records: list[ArtifactRecord]
    ) -> list[ArtifactRecord]: ...

    def get_record_unchecked(self, artifact_id: str) -> ArtifactRecord | None: ...

    def list_by_run(self, normalization_run_id: str) -> list[ArtifactRecord]: ...

    def list_by_case(self, case_id: str) -> list[ArtifactRecord]: ...

    def list_by_case_context(
        self, context: ArtifactAccessContext
    ) -> list[ArtifactRecord]: ...

    def read_payload(self, record: ArtifactRecord) -> Any: ...

    def expire_run(
        self,
        context: ArtifactAccessContext,
        now: datetime | None = None,
    ) -> ArtifactLifecycleResult: ...

    def purge_run(
        self,
        context: ArtifactAccessContext,
    ) -> ArtifactLifecycleResult: ...

    def purge_case(
        self,
        context: ArtifactAccessContext,
    ) -> ArtifactLifecycleResult: ...

    def purge_chat(
        self,
        context: ArtifactAccessContext,
    ) -> ArtifactLifecycleResult: ...

    def mark_source_file_deleted(
        self,
        context: ArtifactAccessContext,
    ) -> ArtifactLifecycleResult: ...
