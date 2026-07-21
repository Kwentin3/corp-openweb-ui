"""Machine-readable Broker Reports architecture authority.

The normative prose authority is
``docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md``.  This module is
the runtime anchor imported by maintained entry points and inspected by
architecture regression tests.  Provider output is evidence, never canonical
authority.
"""

from __future__ import annotations


ARCHITECTURE_POLICY_VERSION = "broker_reports_architecture_policy_v1"
ARCHITECTURE_AUTHORITY = (
    "docs/stage2/blueprints/BROKER_REPORTS_GATE_ARCHITECTURE.md"
)
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
PROVIDER_OUTPUT_AUTHORITY = "typed_proposal_only"
CANONICAL_PROMOTION_AUTHORITY = "deterministic_validator_only"
MODEL_CANONICAL_AUTHORITY = 0

COMPONENT_RUNTIME_STATUSES = {
    # Accepted production design; Goal 2 promotes this only after runtime tests.
    "visual_table_vlm": "implementation_pending",
    "visual_neutral_tables": "production",
    "visual_recovery_handoff": "production",
    # Preserved experiments and historical proof contours.
    "pdf_csv_experiment_provider": "proof_only",
    "pdf_grid_experiment_provider": "proof_only",
    "pdf_hybrid_provider": "proof_only",
    "pdf_dual_vlm_fact_providers": "proof_only",
    "pdf_dual_vlm_canonical_table": "proof_only",
    "prove_visual_neutral_tables_actual_corpus": "offline_only",
}

NON_PRODUCTION_RUNTIME_STATUSES = frozenset(
    {"proof_only", "offline_only", "unsupported_runtime"}
)

FACTORY_REQUIRED = (
    "Maintained Broker Reports entrypoints must route visual recovery through "
    "the production visual provider factory and deterministic promotion validator"
)
FORBIDDEN = (
    "Native OpenWebUI processing, Knowledge/RAG/vectorization, whole-document "
    "visual upload, local OCR production dependencies, and model canonical "
    "authority are forbidden"
)


def component_runtime_status(component_id: str) -> str:
    """Return the maintained runtime classification or fail closed."""

    try:
        return COMPONENT_RUNTIME_STATUSES[component_id]
    except KeyError as exc:
        raise ValueError("broker_reports_component_runtime_status_unknown") from exc
