"""Machine-readable Broker Reports architecture authority.

The normative prose authority is
``docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md``.  This module is
the runtime anchor imported by maintained entry points and inspected by
architecture regression tests.  Provider output is evidence, never canonical
authority.
"""

from __future__ import annotations

from .semantic_visual_table_contracts import (
    SEMANTIC_TABLE_TRANSCRIPTION_ROOT_FIELDS,
    SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION,
)

ARCHITECTURE_POLICY_VERSION = "broker_reports_architecture_policy_v2"
ARCHITECTURE_AUTHORITY = "docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md"
PIPELINE_ID = "broker_reports_controlled_source_processing"

NATIVE_OPENWEBUI_DOCUMENT_PROCESSING_ALLOWED = False
KNOWLEDGE_RAG_VECTORIZATION_ALLOWED = False

GATE_OWNERSHIP = {
    "gate1": "neutral_source_representation",
    "gate2": "source_local_financial_interpretation",
    "gate3": "outside_current_program",
    "gate4": "outside_current_program",
}

VISUAL_RECOVERY_PRODUCTION_PROVIDER_PROFILES = frozenset(
    {"google_gemini", "openai_gpt"}
)
VISUAL_RECOVERY_INPUT_SCOPES = frozenset({"declared_page", "table_crop"})
WHOLE_DOCUMENT_PROVIDER_UPLOAD_ALLOWED = False
LOCAL_OCR_PRODUCTION_ALLOWED = False
LOCAL_OCR_WORKER_POOL_ALLOWED = False
PROVIDER_OUTPUT_AUTHORITY = "semantic_transcription_only"
CANONICAL_PROMOTION_AUTHORITY = (
    "deterministic_validator_for_accepted_profile_else_review_or_fail_closed"
)
MODEL_CANONICAL_AUTHORITY = 0

VISUAL_TABLE_MODEL_FACING_CONTRACT = SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION
VISUAL_TABLE_MODEL_RESPONSE_FIELDS = SEMANTIC_TABLE_TRANSCRIPTION_ROOT_FIELDS
VISUAL_TABLE_MASTER_PROVIDER_PROFILE = "google_gemini"
VISUAL_TABLE_OPENAI_ROLE = "optional_control_or_explicit_fallback"
VISUAL_TABLE_PROVIDER_CONSENSUS_REQUIRED = False
VISUAL_TABLE_VLM_PHYSICAL_GEOMETRY_RESPONSIBILITY = 0
VISUAL_TABLE_MODEL_SYSTEM_METADATA_FIELDS = frozenset()
VISUAL_TABLE_MARKDOWN_RUNTIME_DEPENDENCY = False
VISUAL_TABLE_SYSTEM_ENVELOPE_OWNER = "deterministic_application_code"
VISUAL_TABLE_FINANCIAL_INTERPRETATION_OWNER = "gate2"
LEGACY_VISUAL_TABLE_MODEL_CONTRACT = "broker_reports_canonical_table_v1"
LEGACY_VISUAL_TABLE_CONTRACT_DISPOSITION = (
    "historical_evidence_and_immutable_artifacts_readable_not_default_model_facing"
)
GATE1_RUN_WIDE_PRIVATE_GRAPH_ALLOWED = False
GATE1_INTERMEDIATE_LIFETIME = "one_document_then_seal_persist_release"
GATE1_PRIVATE_REPRESENTATION_AUTHORITY = "artifactstore_resolver_only"
WORKLOAD_AUTHORITY = "sqlite_cross_process_single_authority"
WORKLOAD_ADMISSION = "capacity_queue_plus_worker_lease"
GATE1_HEAVY_CONCURRENCY = 1
GATE2_LOCAL_MAXIMUM_CONCURRENCY = 2
WORKLOAD_PRIMARY_WALL_TIMEOUT = None

COMPONENT_RUNTIME_STATUSES = {
    # Goal 5-qualified semantic numeric-table route. Fresh code objects remain
    # safe-off; the atomic release manifest owns the persisted default-on valve.
    "visual_table_vlm": "maintained_qualified_default_on",
    "visual_neutral_tables": "maintained_qualified_default_on",
    "visual_review_boundary": "maintained_default_off",
    "visual_recovery_handoff": "maintained_qualified_default_on",
    "gate1_bounded_graph": "maintained",
    "workload_authority": "maintained",
    # Preserved experiments and historical proof contours.
    "pdf_csv_experiment_provider": "proof_only",
    "pdf_grid_experiment_provider": "proof_only",
    "pdf_hybrid_provider": "proof_only",
    "pdf_dual_vlm_fact_providers": "maintained_qualified_default_on",
    "pdf_dual_vlm_canonical_table": "maintained_default_off",
    "pdf_dual_vlm_runtime": "maintained_qualified_default_on",
    "prove_visual_neutral_tables_actual_corpus": "offline_only",
}

NON_PRODUCTION_RUNTIME_STATUSES = frozenset(
    {
        "accepted_but_not_yet_deliverable",
        "proof_only",
        "offline_only",
        "unsupported_runtime",
    }
)

FACTORY_REQUIRED = (
    "Maintained Broker Reports entrypoints must route visual recovery through "
    "the production visual provider factory and deterministic semantic "
    "validator/materializer; "
    "heavy Gate 1 runs must route storage through Gate1BoundedGraphFactory.create; "
    "all production workloads must route through WorkloadAuthorityFactory.create"
)
FORBIDDEN = (
    "Native OpenWebUI processing, Knowledge/RAG/vectorization, whole-document "
    "visual upload, local OCR production dependencies, and model canonical "
    "authority are forbidden; retaining decoded private representations for "
    "the complete Gate 1 run, process-local workload queues and local OCR "
    "worker pools are forbidden; model-generated physical table geometry, "
    "model-generated system metadata, mandatory dual-provider consensus, and "
    "Markdown parser dependencies are forbidden in semantic visual extraction"
)


def component_runtime_status(component_id: str) -> str:
    """Return the maintained runtime classification or fail closed."""

    try:
        return COMPONENT_RUNTIME_STATUSES[component_id]
    except KeyError as exc:
        raise ValueError("broker_reports_component_runtime_status_unknown") from exc
