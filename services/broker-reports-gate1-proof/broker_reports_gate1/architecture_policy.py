"""Machine-readable anchors for the current Broker Reports architecture.

Pipeline Gates v1 is the sole current gate-placement authority. Document AI
output crosses one provider-neutral source-normalization boundary and is never
itself canonical, financial, or tax authority.
"""

from __future__ import annotations

# Semantic snapshot identity, not merely the Python/dictionary shape. Bump when
# route ownership, active contracts, allowed behavior or forbidden behavior
# changes; comments and behavior-preserving refactors do not require a bump.
ARCHITECTURE_POLICY_VERSION = "broker_reports_architecture_policy_v28"
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
    "presentation_adapter": "public_dialogue_wording_and_non_authoritative_answer_proposal",
}

# Gate names describe stable responsibilities. This separate closed map records
# which implementation currently performs those responsibilities for a product
# route, so the generic Gate 3 label cannot reactivate its historical runtime.
ACTIVE_PRODUCT_ROUTES = {
    "ordinary_security_trades": {
        "route_id": "ordinary_trade_automatic_semantic_mapping_v1",
        "composition_root": "OrdinaryTradeProductionRuntimeFactory.create",
        "source_semantics_owner": (
            "OrdinaryTradeSemanticMappingFactory.create"
            "+OrdinaryTradeMappingCaseFactory.create"
            "+OrdinaryTradeQualifiedMappingAuthorityFactory.create"
            "+OrdinaryTradeSemanticCompilerFactory.create"
        ),
        "mapping_contract": "broker_reports_ordinary_trade_schema_mapping_v3",
        "qualification_contract": (
            "broker_reports_ordinary_trade_mapping_qualification_v2"
            "|broker_reports_ordinary_trade_case_mapping_qualification_v1"
        ),
        "normalized_fact_contract": "Gate4FinancialCaseFactV2",
        "canonical_completeness_owner": (
            "OrdinaryTradeProjectionRuntime.current_case_coverage"
        ),
        "human_fact_owner": "Gate5HumanGapClosureRuntime",
        "public_dialogue_owner": "ordinary_trade_declaration_chat_adapter",
        "presentation_transport_owner": (
            "Pipe._call_openwebui_presentation_completion"
        ),
        "presentation_model_boundary": "PRESENTATION_ADAPTER",
        "mapping_presentation_verification": (
            "safe_brief_draft_then_bound_semantic_accept_or_fallback"
        ),
        "presentation_business_authority": False,
        "case_metadata_source_owner": "Gate3MetadataSourceFactRuntime",
        "declaration_contract": (
            "BROKER_REPORTS_ORDINARY_TRADE_DECLARATION_MVP.v1"
        ),
        "declaration_status": "active_bounded_fail_closed",
        "taxpayer_identity_contract": (
            "broker_reports_gate5_user_case_fact_v1:taxpayer_identity"
        ),
        "taxpayer_scope_contract": "primary_user_attested_taxpayer_slot_v1",
        "tax_period_selection_contract": (
            "broker_reports_gate5_user_case_fact_v1:selected_tax_period"
        ),
        "operation_period_owner": (
            "Gate5DeterministicSourceFactConsumptionRuntime.assemble_available"
        ),
        "position_scope_contract": "broker_reports_gate5_security_position_scope_v0",
        "profile_owners": [
            "Gate5TrustedMethodologyAuthorityFactory.create",
            "Gate5FullTargetXmlProjectionDefinitionAuthorityFactory.create",
        ],
        "product_states": [
            "INPUT_REQUIRED",
            "DRAFT_READY",
            "DECLARATION_XML_READY",
            "OPEN_POSITION_RETAINED",
            "ANALYSIS_READY_WITH_OPEN_ITEMS",
            "ANALYSIS_ONLY_READY",
            "NON_FILING_SURROGATE_READY",
            "STOPPED_RESUMABLE",
        ],
        "gate3_runtime_status": "financial_llm_deployment_rollback_only",
        "case_metadata_source_status": "current_exact_canonical_supporting_owner",
        "semantic_fallback_allowed": False,
    }
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
    {
        "SOURCE_ADAPTER",
        "METHODOLOGY_ADAPTER",
        "HUMAN_ADAPTER",
        "PRESENTATION_ADAPTER",
        "RESEARCH_ONLY",
    }
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
    "ordinary_trade_public_dialogue": (
        "PRESENTATION_ADAPTER",
        "plain_language_dialogue_wording_and_answer_proposal",
        (
            "broker_reports_ordinary_trade_public_dialogue_message_v5"
            "|broker_reports_ordinary_trade_public_mapping_verification_v1"
            "|broker_reports_ordinary_trade_public_interpretation_v1"
        ),
    ),
    "ordinary_trade_semantic_mapping": (
        "SOURCE_ADAPTER",
        "external_table_semantics_and_column_roles",
        "broker_reports_ordinary_trade_semantic_mapping_response_v2",
    ),
    "ordinary_trade_mapping_answer": (
        "HUMAN_ADAPTER",
        "natural_language_mapping_clarification_answer",
        "broker_reports_ordinary_trade_mapping_answer_response_v1",
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

PDF_DOCUMENT_EXTRACTION_PORT = "PdfDocumentExtractor"
PDF_DOCUMENT_EXTRACTION_ENVELOPE = "PdfDocumentExtraction"
PDF_DOCUMENT_EXTRACTION_COMPOSITION_ROOT = "PdfDocumentExtractorFactory.create"
PDF_DOCUMENT_EXTRACTION_DEFAULT = "UnconfiguredPdfDocumentExtractor"
PDF_DOCUMENT_EXTRACTION_UNCONFIGURED_CODE = "PDF_DOCUMENT_AI_NOT_CONFIGURED"
PDF_DOCUMENT_EXTRACTION_SELECTED_UNQUALIFIED_CODE = (
    "PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED"
)
PDF_DOCUMENT_EXTRACTION_SELECTED_ENGINE = "mistral_ocr"
PDF_DOCUMENT_EXTRACTION_SELECTED_ADAPTER = "mistral_serverless_ocr_adapter_v2"
PDF_DOCUMENT_EXTRACTION_STATIC_READY = True
PDF_DOCUMENT_EXTRACTION_LIVE_QUALIFIED = False
PDF_DOCUMENT_EXTRACTION_QUALIFICATION_ALLOWLIST_SIZE = 2
PDF_DOCUMENT_EXTRACTION_IMAGE_LIFECYCLE = (
    "existing_artifact_store_atomic_private_graph"
)
PDF_DOCUMENT_EXTRACTION_QUALIFICATION_REVIEW = (
    "same_pipe_same_user_digest_bound_temporary_review_then_purge"
)
PDF_DOCUMENT_EXTRACTION_AUTOMATIC_FALLBACK_ALLOWED = False
PDF_DOCUMENT_EXTRACTION_PRODUCTION_CONFIGURED = False
LOCAL_OCR_PRODUCTION_ALLOWED = False
LOCAL_OCR_WORKER_POOL_ALLOWED = False
PROVIDER_OUTPUT_AUTHORITY = "document_ai_representation_only"
CANONICAL_PROMOTION_AUTHORITY = "existing_canonical_downstream_only"
MODEL_CANONICAL_AUTHORITY = 0
GATE1_RUN_WIDE_PRIVATE_GRAPH_ALLOWED = False
GATE1_INTERMEDIATE_LIFETIME = "one_document_then_seal_persist_release"
GATE1_PRIVATE_REPRESENTATION_AUTHORITY = "artifactstore_resolver_only"
WORKLOAD_AUTHORITY = "sqlite_cross_process_single_authority"
WORKLOAD_ADMISSION = "capacity_queue_plus_worker_lease"
GATE1_HEAVY_CONCURRENCY = 1
GATE2_LOCAL_MAXIMUM_CONCURRENCY = 2
WORKLOAD_PRIMARY_WALL_TIMEOUT = None

COMPONENT_RUNTIME_STATUSES = {
    "pdf_document_ai": "live_qualification_ready_activation_blocked",
    "gate1_bounded_graph": "maintained",
    "workload_authority": "maintained",
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
    "Maintained Broker Reports entrypoints must route PDF understanding through "
    "PdfDocumentExtractorFactory.create; "
    "heavy Gate 1 runs must route storage through Gate1BoundedGraphFactory.create; "
    "all production workloads must route through WorkloadAuthorityFactory.create; "
    "consumer evidence demand must route through Gate3EvidenceDemandPortFactory.create"
)
FORBIDDEN = (
    "Native OpenWebUI processing, Knowledge/RAG/vectorization, local content "
    "extraction, local OCR production dependencies, and model canonical "
    "authority are forbidden; retaining decoded private representations for "
    "the complete Gate 1 run, process-local workload queues and local OCR "
    "worker pools are forbidden; automatic provider fallback and Markdown "
    "semantic parsing are forbidden at the Document AI boundary; "
    "Gate 5 Canonical/source reads and document-provider calls, Gate 3 tax "
    "methodology, Gate 4 tax calculation, and projection business decisions are forbidden"
)


def component_runtime_status(component_id: str) -> str:
    """Return the maintained runtime classification or fail closed."""

    try:
        return COMPONENT_RUNTIME_STATUSES[component_id]
    except KeyError as exc:
        raise ValueError("broker_reports_component_runtime_status_unknown") from exc
