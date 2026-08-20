"""Machine-readable anchors for the current Broker Reports architecture.

Pipeline Gates v1 is the sole current gate-placement authority. Provider
output only locates table regions at an external-variability boundary; it is
never source-literal, canonical, financial, or tax authority.
"""

from __future__ import annotations

from .pdf_table_locator import (
    PDF_TABLE_LOCATOR_RESPONSE_SCHEMA,
)

ARCHITECTURE_POLICY_VERSION = "broker_reports_architecture_policy_v4"
ARCHITECTURE_AUTHORITY = "docs/stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md"
VISUAL_TABLE_CONTRACT_AUTHORITY = (
    "docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md"
)
PIPELINE_ID = "broker_reports_controlled_source_processing"

NATIVE_OPENWEBUI_DOCUMENT_PROCESSING_ALLOWED = False
KNOWLEDGE_RAG_VECTORIZATION_ALLOWED = False

GATE_OWNERSHIP = {
    "gate1": "authenticated_source_intake_and_custody",
    "gate2": "canonical_source_preservation",
    "adaptive_context": "structure_preserving_context_packaging",
    "gate3": "source_financial_labeling_and_role_binding",
    "gate4": "normalized_source_facts_and_case_query",
    "gate5": "deterministic_tax_methodology_and_calculation",
    "human_adapter": "typed_factual_human_evidence",
    "external_reference_facts": "typed_authoritative_external_evidence",
    "methodology_adapter": "reviewed_methodology_proposals_only",
    "declaration_semantics": "target_independent_declaration_meaning",
    "release": "evidence_completeness_and_release_decision",
    "projection": "representation_only",
}

DOMAIN_BOUNDARY_SEQUENCE = (
    "gate1",
    "gate2",
    "adaptive_context",
    "gate3",
    "gate4",
    "gate5",
    "declaration_semantics",
    "release",
    "projection",
)
LLM_BOUNDARY_CLASSES = frozenset(
    {"SOURCE_ADAPTER", "METHODOLOGY_ADAPTER", "HUMAN_ADAPTER", "RESEARCH_ONLY"}
)
DETERMINISTIC_RUNTIME_PREFIXES = (
    "gate4_",
    "gate5_",
)

# Every direct structured-model call site is closed-world classified.  Adding
# one without declaring both the uncertainty removed and strict output contract
# fails the architecture suite before it can become an accidental owner.
PROVIDER_CALL_SITE_CLASSIFICATIONS = {
    "gate2_domain_runtime": (
        "SOURCE_ADAPTER",
        "external_broker_vocabulary",
        "gate2_domain_source_facts_strict_schema",
    ),
    "gate2_financial_context_checksum": (
        "RESEARCH_ONLY",
        "qualification_context_ambiguity",
        "gate2_financial_context_checksum_choice_schema",
    ),
    "gate2_financial_evidence_production_runtime": (
        "SOURCE_ADAPTER",
        "source_financial_wording",
        "validated_financial_evidence_decision",
    ),
    "gate2_financial_evidence_shadow_qualification": (
        "RESEARCH_ONLY",
        "candidate_model_quality",
        "shadow_qualification_decision_schema",
    ),
    "gate2_financial_evidence_successor": (
        "RESEARCH_ONLY",
        "successor_semantic_selection_quality",
        "successor_choice_schema",
    ),
    "gate2_financial_semantic_v5_qualification_run": (
        "RESEARCH_ONLY",
        "v5_model_quality",
        "v5_qualification_choice_schema",
    ),
    "gate2_financial_semantic_v6_model_diagnostic": (
        "RESEARCH_ONLY",
        "v6_model_contract_diagnostics",
        "v6_diagnostic_choice_schema",
    ),
    "gate2_financial_semantic_v6_qualification_run": (
        "RESEARCH_ONLY",
        "v6_model_quality",
        "v6_qualification_choice_schema",
    ),
    "gate2_source_fact_runtime": (
        "SOURCE_ADAPTER",
        "external_source_wording",
        "gate2_source_fact_strict_schema",
    ),
    "gate3_bounded_labeling": (
        "SOURCE_ADAPTER",
        "financial_label_wording",
        "gate3_sparse_label_response_schema",
    ),
    "gate3_llm_metadata_adapter": (
        "SOURCE_ADAPTER",
        "minimal_person_document_metadata_wording",
        "broker_reports_llm_metadata_proposal_v2",
    ),
    "gate3_role_labeling": (
        "SOURCE_ADAPTER",
        "financial_role_wording",
        "gate3_role_labeling_response_schema",
    ),
    "gate5_single_input_human_loop": (
        "HUMAN_ADAPTER",
        "natural_language_factual_answer",
        "gate5_single_input_factual_proposal_schema",
    ),
}

# This historical end-to-end composition module is misnamed under gate5_.  It
# is not a Gate 5 domain owner, is inactive, and is the one bounded physical
# package debt retained until its replay consumers can migrate safely.
COMPATIBILITY_ONLY_CROSS_DOMAIN_MODULES = {
    "gate5_end_to_end_full_target_xml": (
        "inactive_full_pipeline_proof_orchestrator",
        "move_to_product_composition_after_replay_consumer_migration",
    )
}

VISUAL_RECOVERY_PRODUCTION_PROVIDER_PROFILES = frozenset({"google_gemini"})
VISUAL_RECOVERY_INPUT_SCOPES = frozenset({"declared_page", "table_crop"})
WHOLE_DOCUMENT_PROVIDER_UPLOAD_ALLOWED = False
LOCAL_OCR_PRODUCTION_ALLOWED = False
LOCAL_OCR_WORKER_POOL_ALLOWED = False
PROVIDER_OUTPUT_AUTHORITY = "table_region_location_only"
CANONICAL_PROMOTION_AUTHORITY = (
    "deterministic_pdfplumber_source_projection_else_fail_closed"
)
MODEL_CANONICAL_AUTHORITY = 0

VISUAL_TABLE_MODEL_FACING_CONTRACT = PDF_TABLE_LOCATOR_RESPONSE_SCHEMA
VISUAL_TABLE_MODEL_RESPONSE_FIELDS = frozenset({"tables"})
VISUAL_TABLE_MASTER_PROVIDER_PROFILE = "google_gemini"
VISUAL_TABLE_OPENAI_ROLE = "none_in_current_pipeline"
VISUAL_TABLE_PROVIDER_CONSENSUS_REQUIRED = False
VISUAL_TABLE_VLM_PHYSICAL_GEOMETRY_RESPONSIBILITY = 0
VISUAL_TABLE_MODEL_SYSTEM_METADATA_FIELDS = frozenset()
VISUAL_TABLE_MARKDOWN_RUNTIME_DEPENDENCY = False
VISUAL_TABLE_SYSTEM_ENVELOPE_OWNER = "deterministic_application_code"
VISUAL_TABLE_FINANCIAL_INTERPRETATION_OWNER = "gate3"
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
    "visual_table_vlm": "research_only",
    "visual_neutral_tables": "maintained_qualified_default_on",
    "visual_review_boundary": "research_only",
    "visual_recovery_handoff": "research_only",
    "gate1_bounded_graph": "maintained",
    "workload_authority": "maintained",
    # One current locator transport plus isolated historical research contours.
    "pdf_table_locator_provider": "maintained_current",
    "pdf_csv_experiment_provider": "proof_only",
    "pdf_grid_experiment_provider": "compatibility_only",
    "pdf_hybrid_provider": "research_only",
    "pdf_dual_vlm_fact_providers": "research_only",
    "pdf_dual_vlm_canonical_table": "research_only",
    "pdf_dual_vlm_runtime": "research_only",
    "prove_visual_neutral_tables_actual_corpus": "offline_only",
}

NON_PRODUCTION_RUNTIME_STATUSES = frozenset(
    {
        "accepted_but_not_yet_deliverable",
        "proof_only",
        "research_only",
        "compatibility_only",
        "offline_only",
        "unsupported_runtime",
    }
)

FACTORY_REQUIRED = (
    "Maintained Broker Reports entrypoints must route PDF table location through "
    "PdfTableIntakeRuntimeFactory and deterministic pdfplumber projection; "
    "heavy Gate 1 runs must route storage through Gate1BoundedGraphFactory.create; "
    "all production workloads must route through WorkloadAuthorityFactory.create; "
    "consumer evidence demand must route through Gate3EvidenceDemandPortFactory.create"
)
FORBIDDEN = (
    "Native OpenWebUI processing, Knowledge/RAG/vectorization, whole-document "
    "visual upload, local OCR production dependencies, and model canonical "
    "authority are forbidden; retaining decoded private representations for "
    "the complete Gate 1 run, process-local workload queues and local OCR "
    "worker pools are forbidden; model-generated physical table geometry, "
    "model-generated system metadata, mandatory dual-provider consensus, and "
    "Markdown parser dependencies are forbidden in semantic visual extraction; "
    "Gate 5 Canonical/source reads and document-provider calls, Gate 3 tax "
    "methodology, Gate 4 tax calculation, and projection business decisions are forbidden"
)


def component_runtime_status(component_id: str) -> str:
    """Return the maintained runtime classification or fail closed."""

    try:
        return COMPONENT_RUNTIME_STATUSES[component_id]
    except KeyError as exc:
        raise ValueError("broker_reports_component_runtime_status_unknown") from exc
