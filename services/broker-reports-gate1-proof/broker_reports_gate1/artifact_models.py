from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


ARTIFACT_SCHEMA_VERSION = "broker_reports_artifact_v0"
ARTIFACT_LIFECYCLE_RESULT_SCHEMA_VERSION = (
    "broker_reports_artifact_lifecycle_result_v1"
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
    "broker_reports_normalized_table_projection_v0",
    "broker_reports_gate1_visual_neutral_table_v1",
    "broker_reports_gate1_visual_recovery_manifest_v1",
    "broker_reports_pdf_compact_canonical_document_v1",
    "broker_reports_pdf_normalization_acceptance_v1",
    "broker_reports_pdf_compact_build_failure_v1",
    "broker_reports_pdf_table_classification_v1",
    "broker_reports_pdf_table_crop_v1",
    "broker_reports_pdf_table_candidate_v1",
    "broker_reports_pdf_table_detection_attempt_v1",
    "broker_reports_pdf_table_intake_run_v1",
    "broker_reports_pdf_hybrid_evidence_package_v1",
    "broker_reports_pdf_provider_attempt_v1",
    "broker_reports_pdf_hybrid_raw_response_v1",
    "broker_reports_pdf_hybrid_binding_output_v1",
    "broker_reports_pdf_table_materialization_result_v1",
    "broker_reports_pdf_table_validation_v1",
    "broker_reports_pdf_hybrid_shadow_decision_v1",
    "broker_reports_pdf_hybrid_proposed_compact_revision_v1",
    "broker_reports_pdf_hybrid_shadow_summary_v1",
    "broker_reports_pdf_hybrid_compact_ledger_v2",
    "broker_reports_pdf_hybrid_row_window_plan_v2",
    "broker_reports_pdf_hybrid_window_evidence_v2",
    "broker_reports_pdf_hybrid_provider_token_count_v2",
    "broker_reports_pdf_hybrid_structural_placement_validation_v2",
    "broker_reports_pdf_hybrid_continuation_contract_v2",
    "broker_reports_pdf_hybrid_continuation_validation_v2",
    "broker_reports_pdf_hybrid_repeatability_ledger_v2",
    "broker_reports_pdf_hybrid_shadow_arbitration_v2",
    "broker_reports_pdf_hybrid_reliability_summary_v2",
    "broker_reports_pdf_structural_repair_target_state_v1",
    "broker_reports_pdf_structural_repair_runtime_result_v1",
    "broker_reports_pdf_vlm_guided_intake_result_v1",
    "broker_reports_pdf_vlm_guided_candidate_intake_result_v1",
    "broker_reports_pdf_vlm_guided_page_intake_result_v1",
    "broker_reports_pdf_vlm_guided_upstream_terminal_v1",
    "broker_reports_pdf_vlm_guided_skip_terminal_v1",
    "broker_reports_pdf_semantic_header_projection_v1",
    "broker_reports_pdf_semantic_header_private_diagnostic_v1",
    "broker_reports_pdf_structural_repair_private_diagnostic_v1",
    "broker_reports_pdf_dual_oracle_repeat_history_v1",
    "broker_reports_pdf_structural_repair_shadow_summary_v1",
    "broker_reports_pdf_continuation_discovery_v1",
    "broker_reports_pdf_structural_repair_continuation_result_v1",
    "broker_reports_pdf_continuation_materialization_v1",
    "broker_reports_file_processing_batch_v1",
    "chat_visible_normalization_report_v0",
    "validation_result_v0",
    "gate2_handoff_v0",
    "broker_reports_source_fact_extraction_run_v0",
    "broker_reports_source_fact_package_v0",
    "broker_reports_source_fact_raw_output_v0",
    "broker_reports_source_facts_v0",
    "broker_reports_source_fact_validation_v0",
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
    "broker_reports_document_extraction_packet_v0",
    "broker_reports_source_value_candidate_set_v0",
    "broker_reports_candidate_relation_set_v0",
    "broker_reports_candidate_binding_validation_v0",
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

    def get_record_unchecked(self, artifact_id: str) -> ArtifactRecord | None: ...

    def list_by_run(self, normalization_run_id: str) -> list[ArtifactRecord]: ...

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
