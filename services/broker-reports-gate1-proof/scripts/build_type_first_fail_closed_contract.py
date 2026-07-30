from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
CONTRACT_ROOT = REPO_ROOT / "docs" / "stage2" / "contracts"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-07-30"

CONTRACT_PATH = (
    CONTRACT_ROOT / "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md"
)
MACHINE_PATH = (
    CONTRACT_ROOT / "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json"
)
OUTPUT_STEM = "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED_CONTRACT_GOAL16"
REPORT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.report.md"
RECEIPT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.receipt.safe.json"

BASE_COMMIT = "7ef38c2bba12e6773f2ded8542c256d603ca5aff"
GOAL_ID = "BROKER_REPORTS_GATE2_GOAL16_TYPE_FIRST_FAIL_CLOSED_CONTRACT"
CONTRACT_IDENTITIES = {
    "contract_identity": "broker_reports_gate2_type_first_fail_closed_v1",
    "context_profile": (
        "broker_reports_gate2_type_first_context_v1_candidate"
    ),
    "response_profile": (
        "broker_reports_gate2_type_first_plausible_types_response_v1"
    ),
    "decision_policy": (
        "broker_reports_gate2_type_first_fail_closed_policy_v1"
    ),
}
FIELD_ORDER = ("task", "source", "type_cards")
EXACT_SYSTEM_MESSAGE = (
    "Return exactly one JSON object that conforms to the supplied strict "
    "response schema. Use only the task and evidence in the user message."
)
EXACT_TASK = (
    "Return every type_key from type_cards whose financial meaning remains "
    "plausible for the visible source. Return all plausible types, not only "
    "the best one. Judge type plausibility independently of whether code can "
    "construct a complete record. Preserve type_cards order."
)
LOCAL_TYPE_KEY_ORDER = ("type_1", "type_2")
PRIVATE_TYPE_MAPPING = {
    "type_1": "cash_balance_snapshot_v1",
    "type_2": "printed_financial_metric_v1",
}
RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "plausible_types": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": list(LOCAL_TYPE_KEY_ORDER),
            },
            "minItems": 0,
            "maxItems": len(LOCAL_TYPE_KEY_ORDER),
            "uniqueItems": True,
        }
    },
    "required": ["plausible_types"],
}
STATUS = {
    "active": False,
    "transport_eligible": False,
    "runtime_activation": False,
    "provider_calls_total": 0,
    "fallback_allowed": False,
    "repair_allowed": False,
    "retry_allowed": False,
}
TOKEN_ESTIMATOR_ID = "compact_request_utf8_bytes_div_4_plus_64_v1"
TOKEN_ESTIMATOR_OVERHEAD = 64

GOAL15_TRANSPARENT_PATH = (
    REPORT_ROOT
    / "BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_"
    "ARCHITECTURE_AUDIT_GOAL15.transparent.json"
)

CASE_ORDER = (
    "syn_successor_v2_unique_cash",
    "syn_successor_v2_unique_printed_total",
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_no_registry_type",
    "syn_successor_v2_missing_discriminator",
    "syn_successor_v2_detail_vs_subtotal",
    "syn_successor_v2_adjacent_equal",
    "syn_successor_v2_adjacent_fx",
    "syn_successor_v2_optional_missing",
    "syn_successor_v2_forbidden_neighbour",
)
CASE_EXPECTATIONS = {
    "syn_successor_v2_unique_cash": {
        "plausible_local_types": ["type_1"],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "typed_option_identity": (
            "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
        ),
        "typed_option_pin_status": "historical_explicit",
    },
    "syn_successor_v2_unique_printed_total": {
        "plausible_local_types": ["type_2"],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "typed_option_identity": (
            "financial-typed-option:9c6b9a796d36dc2cde5b073c9d397622"
        ),
        "typed_option_pin_status": (
            "current_factory_observation_frozen_by_goal16"
        ),
    },
    "syn_successor_v2_multiple_compatible": {
        "plausible_local_types": ["type_1", "type_2"],
        "complete_option_counts_by_type": {"type_1": 0, "type_2": 0},
        "typed_option_identity": None,
        "typed_option_pin_status": "not_applicable",
    },
    "syn_successor_v2_no_registry_type": {
        "plausible_local_types": [],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "typed_option_identity": None,
        "typed_option_pin_status": "not_applicable",
    },
    "syn_successor_v2_missing_discriminator": {
        "plausible_local_types": ["type_1", "type_2"],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "typed_option_identity": None,
        "typed_option_pin_status": "not_applicable",
    },
    "syn_successor_v2_detail_vs_subtotal": {
        "plausible_local_types": ["type_2"],
        "complete_option_counts_by_type": {"type_1": 0, "type_2": 0},
        "typed_option_identity": None,
        "typed_option_pin_status": "not_applicable",
    },
    "syn_successor_v2_adjacent_equal": {
        "plausible_local_types": ["type_1"],
        "complete_option_counts_by_type": {"type_1": 0, "type_2": 0},
        "typed_option_identity": None,
        "typed_option_pin_status": "not_applicable",
    },
    "syn_successor_v2_adjacent_fx": {
        "plausible_local_types": ["type_1"],
        "complete_option_counts_by_type": {"type_1": 0, "type_2": 0},
        "typed_option_identity": None,
        "typed_option_pin_status": "not_applicable",
    },
    "syn_successor_v2_optional_missing": {
        "plausible_local_types": ["type_1"],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "typed_option_identity": (
            "financial-typed-option:2913ae6d06a3bc248adabfd7ff9ed411"
        ),
        "typed_option_pin_status": (
            "current_factory_observation_frozen_by_goal16"
        ),
    },
    "syn_successor_v2_forbidden_neighbour": {
        "plausible_local_types": ["type_1"],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "typed_option_identity": (
            "financial-typed-option:73ec7a290138fbd81b6bdc7f61d739ec"
        ),
        "typed_option_pin_status": (
            "current_factory_observation_frozen_by_goal16"
        ),
    },
}

MAPPING_RECEIPT_INTEGRITIES = {
    "syn_successor_v2_unique_cash": (
        "0a24f59049d314219e236ed68f3e27a862b5b2652ed0d668f0811ad32c630d91"
    ),
    "syn_successor_v2_unique_printed_total": (
        "22fa59c0bf217808b84798ad3365827063104f5c10fc0f881616bd08dd9e8d69"
    ),
    "syn_successor_v2_multiple_compatible": (
        "5819dc89a7b6c10813ffecc7a455234e56df3a1655cc2bc4ac5a6d7cfd626c99"
    ),
    "syn_successor_v2_no_registry_type": (
        "3a206c92816b7600cad18ca133b721c5fd0ead0aa37735750c90c98bf2ab78e6"
    ),
    "syn_successor_v2_missing_discriminator": (
        "fc37466094614eac1702705d8b8abb85d1de2c9990c8bb51a653bc8569dd76de"
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "6a09e2a18d4852c46cb6f6f19d914940be8a9e1aac7040f87ed0687431f767db"
    ),
    "syn_successor_v2_adjacent_equal": (
        "e2b02af18bf07092eb36d1ec73313ef72ae8963d582a9794470ddb9b13e10ec9"
    ),
    "syn_successor_v2_adjacent_fx": (
        "63e1ef039ec8835af6b65d3cb249e5e81e7e89786b2fba8162bbc13133ed80cc"
    ),
    "syn_successor_v2_optional_missing": (
        "f85954789da0d5e19e5d061f531a68d4b75235da6d8cce5280b6a434ade98b52"
    ),
    "syn_successor_v2_forbidden_neighbour": (
        "58751913997b84fde03a3cf897151dd1312e994d117020f45ec9ac964786fb33"
    ),
}
COMPILATION_INTEGRITIES = {
    "syn_successor_v2_unique_cash": (
        "0e37b4c78cf7e3e3e8260f07a4b7eb5476508df6c4ecb23eef3c45d8e60ff436"
    ),
    "syn_successor_v2_unique_printed_total": (
        "91821868dc7604d13ced0d053b5d2d628d5b25409e0444aeee00132cd86f6d4c"
    ),
    "syn_successor_v2_multiple_compatible": (
        "f75a29b5c37a4f29150709f0c338028ab43f176f3a8d0056c80b1def68df900c"
    ),
    "syn_successor_v2_no_registry_type": (
        "700951c097b69098337e43362f7c8df3c45abe06fe30c9d4e94c6517639c25d6"
    ),
    "syn_successor_v2_missing_discriminator": (
        "5a6cc4432b0a746205960f295627cefe140fe5f8d3ed31d5c41425175f46ef73"
    ),
    "syn_successor_v2_detail_vs_subtotal": (
        "f80c4f505b3b5b2df679cffd4c073b65009e91f718fbec603a3324f9115084ae"
    ),
    "syn_successor_v2_adjacent_equal": (
        "a4f7cf6bd633e613cc55e02bec9f6c37fd35594b490f4f2444624166ae243536"
    ),
    "syn_successor_v2_adjacent_fx": (
        "eb09e988d75656299774c7c3a0d316ec163f98694e57fa0c7b3c6e795541b1e8"
    ),
    "syn_successor_v2_optional_missing": (
        "a4d364651503c6e785cb2a8f1a63a8358b53d9a3b50357892c0c5e355390c633"
    ),
    "syn_successor_v2_forbidden_neighbour": (
        "9817d99d6d00571299105c0619153dbf70c3d40608e30f26cd9ece9b5dbab910"
    ),
}

TECHNICAL_RESPONSE_NEGATIVE_FIXTURES = (
    {
        "fixture_id": "malformed_json",
        "response_text": "{",
        "expected_error_code": "malformed_json",
    },
    {
        "fixture_id": "missing_plausible_types",
        "response_text": "{}",
        "expected_error_code": "missing_plausible_types",
    },
    {
        "fixture_id": "plausible_types_null",
        "response_text": '{"plausible_types":null}',
        "expected_error_code": "plausible_types_null",
    },
    {
        "fixture_id": "plausible_types_not_array",
        "response_text": '{"plausible_types":"type_1"}',
        "expected_error_code": "plausible_types_not_array",
    },
    {
        "fixture_id": "unknown_type_key",
        "response_text": '{"plausible_types":["type_3"]}',
        "expected_error_code": "unknown_type_key",
    },
    {
        "fixture_id": "duplicate_type_key",
        "response_text": '{"plausible_types":["type_1","type_1"]}',
        "expected_error_code": "duplicate_type_key",
    },
    {
        "fixture_id": "out_of_order_type_keys",
        "response_text": '{"plausible_types":["type_2","type_1"]}',
        "expected_error_code": "out_of_order_type_keys",
    },
    {
        "fixture_id": "extra_response_field",
        "response_text": '{"plausible_types":[],"reason":"no_registry_type"}',
        "expected_error_code": "extra_response_field",
    },
    {
        "fixture_id": "backend_type_id_forbidden",
        "response_text": (
            '{"plausible_types":["cash_balance_snapshot_v1"]}'
        ),
        "expected_error_code": "backend_type_id_forbidden",
    },
)
CONTRACT_INTEGRITY_NEGATIVE_FIXTURES = (
    {
        "fixture_id": "mapping_receipt_mismatch",
        "kind": "mapping_receipt",
        "expected": "mapping-receipt-expected",
        "observed": "mapping-receipt-resealed",
        "expected_error_code": "mapping_receipt_mismatch",
    },
    {
        "fixture_id": "context_profile_schema_hash_mismatch",
        "kind": "context_profile_schema",
        "expected": "context-profile-schema-expected",
        "observed": "context-profile-schema-drift",
        "expected_error_code": "context_profile_schema_hash_mismatch",
    },
    {
        "fixture_id": "pack_projection_drift",
        "kind": "pack_projection",
        "expected": "pack-projection-expected",
        "observed": "pack-projection-drift",
        "expected_error_code": "pack_projection_drift",
    },
    {
        "fixture_id": "evidence_bundle_scope_mismatch",
        "kind": "evidence_bundle_scope",
        "expected": "evidence-bundle-scope-expected",
        "observed": "evidence-bundle-scope-other",
        "expected_error_code": "evidence_bundle_scope_mismatch",
    },
    {
        "fixture_id": "candidate_compilation_scope_mismatch",
        "kind": "candidate_compilation_scope",
        "expected": "candidate-compilation-scope-expected",
        "observed": "candidate-compilation-scope-other",
        "expected_error_code": "candidate_compilation_scope_mismatch",
    },
)
BACKEND_RESTORATION_NEGATIVE_FIXTURES = (
    {
        "fixture_id": "missing_exact_code_owned_typed_option",
        "plausible_types": ["type_1"],
        "matching_option_ids": ["option_1"],
        "typed_option_id": None,
        "expected_error_code": "exact_code_owned_typed_option_mismatch",
    },
    {
        "fixture_id": "mismatched_exact_code_owned_typed_option",
        "plausible_types": ["type_1"],
        "matching_option_ids": ["option_1"],
        "typed_option_id": "option_2",
        "expected_error_code": "exact_code_owned_typed_option_mismatch",
    },
)
SEAL_ERROR_CODES = {
    fixture["kind"]: fixture["expected_error_code"]
    for fixture in CONTRACT_INTEGRITY_NEGATIVE_FIXTURES
}

QUALIFICATION_COUNTERS = (
    "plausible_type_set_exact_total",
    "false_empty_total",
    "false_singleton_total",
    "false_superset_total",
    "wrong_singleton_type_total",
    "false_singleton_typed_total",
    "unsafe_typed_total",
    "safe_under_typing_total",
    "invalid_response_total",
)
HARD_QUALIFICATION_GATES = {
    "unsafe_typed_total": 0,
    "false_singleton_typed_total": 0,
    "wrong_singleton_type_total": 0,
    "invalid_response_total": 0,
}

AUTHORITY_MAP = (
    {
        "concern": "packet_context_construction",
        "existing_owner": "Gate2FinancialSemanticV6PacketFactory.create",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_packet.py:218"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "additive_inactive_profile",
        "new_owner_required": False,
    },
    {
        "concern": "type_projection",
        "existing_owner": (
            "Gate2FinancialSemanticV5ProjectionFactory."
            "create_minimal_managed_projection"
        ),
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v5_projection.py:199"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "unchanged",
        "new_owner_required": False,
    },
    {
        "concern": "candidate_compilation",
        "existing_owner": "Gate2FinancialCandidateCompilerFactory.create",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_candidate_compiler.py:130"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "unchanged",
        "new_owner_required": False,
    },
    {
        "concern": "response_contract_parser",
        "existing_owner": (
            "Gate2FinancialSemanticV6ChoiceContractFactory.create"
        ),
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_choice.py:249"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "additive_inactive_profile",
        "new_owner_required": False,
    },
    {
        "concern": "context_validation_sealing",
        "existing_owner": (
            "Gate2FinancialSemanticV6ContextLinterFactory"
        ),
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_context_linter.py:362"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "additive_inactive_profile",
        "new_owner_required": False,
    },
    {
        "concern": "request_construction",
        "existing_owner": "Gate2OpenWebUIRequestBuilder",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_model_requests.py:210"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "additive_inactive_profile",
        "new_owner_required": False,
    },
    {
        "concern": "provider_adaptation",
        "existing_owner": "Gate2ProviderAdapterFactory.create",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_provider_adapters.py:663"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "unchanged_semantic_behavior",
        "new_owner_required": False,
    },
    {
        "concern": "decision_expansion",
        "existing_owner": (
            "Gate2FinancialSemanticV6DecisionExpansionFactory"
        ),
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_expansion.py:128"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "additive_type_first_profile",
        "new_owner_required": False,
    },
    {
        "concern": "validation",
        "existing_owner": (
            "Gate2FinancialEvidenceValidatedDecisionFactory.create"
        ),
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_evidence_materialization.py:89"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "unchanged",
        "new_owner_required": False,
    },
    {
        "concern": "materialization",
        "existing_owner": (
            "Gate2FinancialEvidenceMaterializerFactory.create"
        ),
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_evidence_materialization.py:145"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "unchanged",
        "new_owner_required": False,
    },
    {
        "concern": "decision_evidence_replay",
        "existing_owner": (
            "Gate2FinancialSemanticV6DecisionEvidenceFactory"
        ),
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_financial_semantic_v6_evidence.py:450"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "additive_single_stage_profile",
        "new_owner_required": False,
    },
    {
        "concern": "economy_accounting",
        "existing_owner": "Gate2EconomyBudgetSessionFactory",
        "authority_anchor": (
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
            "gate2_economy_budget.py:131"
        ),
        "goal16_change": "none_contract_only",
        "future_profile_change": "existing_one_call_limit_retained",
        "new_owner_required": False,
    },
)

HISTORICAL_SOURCE_PINS = (
    (
        "goal12_precall_plan",
        "docs/reports/2026-07-29/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
        ".precall.plan.safe.json",
        "2b3a25cd04f0fffc6532477a44b93f6ce78e7e32f76bc239cceb13a2f5abacfe",
    ),
    (
        "goal12_precall_transparent",
        "docs/reports/2026-07-29/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
        ".precall.transparent.json",
        "f64ef2e1daa92cc3eaa204ed34f1e753595ce0d4c7a4fd937492a6c145c58537",
    ),
    (
        "goal12_terminal_receipt",
        "docs/reports/2026-07-29/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
        ".receipt.safe.json",
        "b4e77203c7fdffd96ad09b4a7ef5364ccef09072c8fc645e38a36a142dfffc8b",
    ),
    (
        "goal12_terminal_report",
        "docs/reports/2026-07-29/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
        ".report.md",
        "fa5d4e6d5961124e59bcd4204291772476dc7afb6c41ee80b719b658b3d3664b",
    ),
    (
        "goal12_terminal_transparent",
        "docs/reports/2026-07-29/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
        ".transparent.json",
        "7f4718f13763c9963592326e8481072606219435495fb6fbd59655a881197281",
    ),
    (
        "goal13_forensic_receipt",
        "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_"
        "GOAL13.receipt.safe.json",
        "7c350ce0b24c8e252fc963cf9d9d7c05d3a895c169fb855dcb16afcfc9226735",
    ),
    (
        "goal13_forensic_report",
        "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_"
        "GOAL13.report.md",
        "7161542710ef9c33a45d3c16fb30f10ed97636e1d59d6c2e01bad88083a0379b",
    ),
    (
        "goal14_comparative_receipt",
        "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_EVIDENCE_FIRST_COMPARATIVE_"
        "REVIEW_GOAL14.receipt.safe.json",
        "360c8b23f713bd3981947de2c222da6e28b001d330809b4c6c1575245a86e63c",
    ),
    (
        "goal14_comparative_report",
        "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_EVIDENCE_FIRST_COMPARATIVE_"
        "REVIEW_GOAL14.report.md",
        "186eb0f7b9aa40f68bd672b2a9b2680eb029df3ec11a998a039caeec9a5051dd",
    ),
    (
        "goal14_comparative_transparent",
        "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_CONTEXT_V2_1_EVIDENCE_FIRST_COMPARATIVE_"
        "REVIEW_GOAL14.transparent.json",
        "c4956f26947ccff533ccd094ac734eb8cfdcf96bd9dbc183fe5940c3d165db96",
    ),
    (
        "goal15_architecture_receipt",
        "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_ARCHITECTURE_"
        "AUDIT_GOAL15.receipt.safe.json",
        "57c7d1c1b6ce7206fe9eb4d61a5505bc782c1f365c4e26db7743553b2d9c6288",
    ),
    (
        "goal15_architecture_report",
        "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_ARCHITECTURE_"
        "AUDIT_GOAL15.report.md",
        "eedd5b04ef79830b8fee0906629fbd202a10f914a29e9cad07b4da98d3ebbd27",
    ),
    (
        "goal15_architecture_transparent",
        "docs/reports/2026-07-30/"
        "BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_ARCHITECTURE_"
        "AUDIT_GOAL15.transparent.json",
        "d66ed03007b586bb861fb76e48297949e8e294b00142cf7bcc80dc95db9b7ed9",
    ),
)

ACTIVE_SOURCE_PINS = (
    (
        "active_context_v2_1_packet_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_semantic_v6_packet.py",
        "175c450dbbd5ef3912bd160fa390cb85e1821f68321831ad8b58430c26d13e0e",
    ),
    (
        "active_choice_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_semantic_v6_choice.py",
        "e47e754f33032460edfd6ea25377bd2eeb75c181b307c64440965ab1e409d4d5",
    ),
    (
        "current_semantic_pack",
        "services/broker-reports-gate1-proof/semantic_packs/"
        "broker_reports_financial_semantic_pack.v1.json",
        "ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f",
    ),
    (
        "current_semantic_pack_schema",
        "services/broker-reports-gate1-proof/semantic_packs/"
        "broker_reports_financial_semantic_pack.v1.schema.json",
        "cea99c199ba6b20905fd988fed481e963a999d1a74464a0af055d38eb0c76b9e",
    ),
    (
        "current_minimal_projection_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_semantic_v5_projection.py",
        "a248cd93c3634b4d19b4da3c06e151c6e339e6e9ab33c6a69c4e2c0e1618deb7",
    ),
    (
        "current_model_asset_projection",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_semantic_model_assets.py",
        "53d91ef3386541bfb654d0e264c9f942a04ddeb7b21291c033a55f874314bc62",
    ),
    (
        "current_reason_catalog",
        "services/broker-reports-gate1-proof/managed_assets/decision_reasons/"
        "broker_reports_gate2_financial_decision_reason_catalog.v2.json",
        "cb784fe262c08297b9cd71c84e2bf36195d214f7aec82f3cc74f5707a24dde24",
    ),
    (
        "current_reason_catalog_schema",
        "services/broker-reports-gate1-proof/managed_assets/decision_reasons/"
        "broker_reports_gate2_financial_decision_reason_catalog.v2.schema.json",
        "d576e9368272f8bf6dd46250e9d798e7bf40c1dd56f98216262d770a12c2aa24",
    ),
    (
        "semantic_prompt_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_semantic_v6_prompt.py",
        "a6334ae2dd7e0f417e8ad629dbec9423ccc297b8fe20acac119d6b2caadfb8fc",
    ),
    (
        "provider_adapter_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_provider_adapters.py",
        "3e7cae769d023ef81cc052519507eceeeb3e5988abd7ed93194f4a8f5b36e2ac",
    ),
    (
        "active_context_linter_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_semantic_v6_context_linter.py",
        "99145aa603e1e42a7a9036a3d77e2cceedb82510734d25f0c1763c2933a875aa",
    ),
    (
        "active_request_builder_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_model_requests.py",
        "70142660c31adf2b595ee81aedf54afd35568eaed1713f5e5085f38d67725a73",
    ),
    (
        "candidate_compiler_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_semantic_v6_candidate_compiler.py",
        "c6b5a3baa33aae2ff0f39bd7d82e414bcb67a61a04e26d02dff824bf0fba936a",
    ),
    (
        "decision_expansion_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_semantic_v6_expansion.py",
        "d1b7856d7c3b08012f154778a05e76bb139e43078266151ae5cda69e7aa21e5c",
    ),
    (
        "validation_materialization_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_evidence_materialization.py",
        "bcadcf529bdade058b2facb6ee5bce1b1a57cae69f06a113f73a727dbd3e33ba",
    ),
    (
        "decision_evidence_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_semantic_v6_evidence.py",
        "a7f33a47fff6622e8d03c2311003cd7ff92fa1da564d6596bcaf1de64abae1ed",
    ),
    (
        "economy_accounting_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_economy_budget.py",
        "46efe45c2fd507e0e8e5efe729eec298aeade5cb2cf3d9b989316d077bdae942",
    ),
    (
        "economy_policy_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_economy_model_policy.py",
        "69a3835f690e441e3f3888e523521aea7eccf208ead9c2e074607620bc880d27",
    ),
    (
        "production_orchestration_owner",
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "gate2_financial_evidence_production_runtime.py",
        "b92537a5fbfe9ad0ff35fdbbb6812a97905b62a041ccea89705a712c1f3c24ec",
    ),
    (
        "active_context_v2_1_contract",
        "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE2_LLM_SEMANTIC_CONTEXT.v2.1.md",
        "c1b2a6376dd2c48d9e5303b49bc690b50965d387645a2dbc3bf177f70e003303",
    ),
    (
        "active_choice_contract",
        "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_CHOICE_V6.md",
        "797cdaee168263ace2d3ad9a6fb8c3c233cca75f76c9eb826b84ded82744d6ff",
    ),
    (
        "minimal_surface_contract",
        "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE2_MINIMAL_MODEL_SURFACE.v1.md",
        "cfa4e6f76aa817337b2c71ed3904ddaa774d15f0367ba7e98c94bff5e1b1668f",
    ),
    (
        "semantic_pack_model_input_contract",
        "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE2_SEMANTIC_PACK_MODEL_INPUT.v1.md",
        "8c33ea32cb769127c7a28285876b0ac17d55eac47a002555a0403127581f7d79",
    ),
)

EXPECTED_GOAL16_PATHS = {
    ".gitattributes",
    ".github/workflows/broker-reports-ci.yml",
    (
        "docs/reports/2026-07-30/"
        f"{OUTPUT_STEM}.receipt.safe.json"
    ),
    f"docs/reports/2026-07-30/{OUTPUT_STEM}.report.md",
    "docs/stage2/CONTEXT_INDEX.md",
    (
        "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_EXACT_EVIDENCE.md"
    ),
    (
        "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json"
    ),
    (
        "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md"
    ),
    (
        "services/broker-reports-gate1-proof/scripts/"
        "build_type_first_fail_closed_contract.py"
    ),
    (
        "services/broker-reports-gate1-proof/tests/"
        "test_build_type_first_fail_closed_contract.py"
    ),
}

_MODEL_VIEW_EXCLUDED_FIELDS = (
    "choices",
    "complete_options",
    "differentiators",
    "unclassified_reasons",
    "typed_option_ids",
    "canonical_type_ids",
    "compiler_option_counts",
    "bindings",
    "refs",
    "hashes",
    "materialization_metadata",
)
_MODEL_VIEW_FORBIDDEN_KEYS = frozenset(
    {
        "choices",
        "complete_options",
        "differentiators",
        "unclassified_reasons",
        "typed_option_id",
        "typed_option_ids",
        "choice_key",
        "input_type_id",
        "canonical_type_id",
        "canonical_type_ids",
        "compiler_option_counts",
        "bindings",
        "refs",
        "hashes",
        "materialization_metadata",
    }
)
_LOCAL_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/](?:Users|Documents|Desktop)[\\/]|"
    r"/(?:home|Users|private|tmp)/)"
)


class TypeFirstContractValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build or verify the inactive GOAL 16 type-first fail-closed "
            "contract evidence."
        )
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when generated contract evidence differs from repository.",
    )
    args = parser.parse_args(argv)

    contract_md, machine, report, receipt = build_artifacts()
    outputs = {
        CONTRACT_PATH: contract_md.encode("utf-8"),
        MACHINE_PATH: _json_bytes(machine),
        REPORT_PATH: report.encode("utf-8"),
        RECEIPT_PATH: _json_bytes(receipt),
    }
    write_or_check_outputs(outputs=outputs, check=args.check)
    print(
        _compact_json(
            {
                "contract_identity": CONTRACT_IDENTITIES[
                    "contract_identity"
                ],
                "mode": "check" if args.check else "write",
                "provider_calls_total": 0,
                "runtime_changes_total": 0,
                "status": "passed",
                "ten_case_count": len(machine["ten_case_matrix"]),
                "response_negative_fixture_count": len(
                    TECHNICAL_RESPONSE_NEGATIVE_FIXTURES
                ),
                "contract_integrity_negative_fixture_count": len(
                    CONTRACT_INTEGRITY_NEGATIVE_FIXTURES
                ),
                "backend_restoration_negative_fixture_count": len(
                    BACKEND_RESTORATION_NEGATIVE_FIXTURES
                ),
                "technical_negative_fixture_total": (
                    len(TECHNICAL_RESPONSE_NEGATIVE_FIXTURES)
                    + len(CONTRACT_INTEGRITY_NEGATIVE_FIXTURES)
                    + len(BACKEND_RESTORATION_NEGATIVE_FIXTURES)
                ),
            }
        )
    )
    return 0


def validate_response_text(
    response_text: str,
    visible_type_keys: tuple[str, ...] = LOCAL_TYPE_KEY_ORDER,
) -> tuple[str, ...]:
    try:
        value = json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        raise TypeFirstContractValidationError("malformed_json") from None
    return validate_response_object(
        value,
        visible_type_keys=visible_type_keys,
    )


def validate_response_object(
    value: Any,
    visible_type_keys: tuple[str, ...] = LOCAL_TYPE_KEY_ORDER,
) -> tuple[str, ...]:
    if not isinstance(value, dict):
        raise TypeFirstContractValidationError("response_root_not_object")
    if "plausible_types" not in value:
        raise TypeFirstContractValidationError("missing_plausible_types")
    if set(value) != {"plausible_types"}:
        raise TypeFirstContractValidationError("extra_response_field")

    plausible = value["plausible_types"]
    if plausible is None:
        raise TypeFirstContractValidationError("plausible_types_null")
    if not isinstance(plausible, list):
        raise TypeFirstContractValidationError("plausible_types_not_array")

    canonical_ids = frozenset(PRIVATE_TYPE_MAPPING.values())
    if any(
        isinstance(item, str) and item in canonical_ids
        for item in plausible
    ):
        raise TypeFirstContractValidationError(
            "backend_type_id_forbidden"
        )
    if any(
        not isinstance(item, str) or item not in visible_type_keys
        for item in plausible
    ):
        raise TypeFirstContractValidationError("unknown_type_key")
    if len(set(plausible)) != len(plausible):
        raise TypeFirstContractValidationError("duplicate_type_key")

    positions = [visible_type_keys.index(item) for item in plausible]
    if positions != sorted(positions):
        raise TypeFirstContractValidationError("out_of_order_type_keys")
    return tuple(plausible)


def validate_seal_match(kind: str, observed: str, expected: str) -> None:
    code = SEAL_ERROR_CODES.get(kind)
    if code is None:
        raise TypeFirstContractValidationError("unknown_seal_kind")
    if observed != expected:
        raise TypeFirstContractValidationError(code)


def derive_backend_decision(
    plausible_types: list[str] | tuple[str, ...],
    matching_option_ids: list[str] | tuple[str, ...],
    *,
    typed_option_id: str | None = None,
) -> dict[str, str]:
    validated = validate_response_object(
        {"plausible_types": list(plausible_types)}
    )
    if len(validated) == 0:
        return {
            "disposition": "unclassified_financial_input",
            "reason_code": "no_registry_type",
        }
    if len(validated) >= 2:
        return {
            "disposition": "unclassified_financial_input",
            "reason_code": "ambiguous_registry_type",
        }
    if len(matching_option_ids) != 1:
        return {
            "disposition": "unclassified_financial_input",
            "reason_code": "single_registry_type_no_safe_record",
        }
    selected = matching_option_ids[0]
    if typed_option_id is None or selected != typed_option_id:
        raise TypeFirstContractValidationError(
            "exact_code_owned_typed_option_mismatch"
        )
    return {
        "disposition": "typed_input",
        "typed_option_id": selected,
    }


def build_artifacts() -> tuple[
    str,
    dict[str, Any],
    str,
    dict[str, Any],
]:
    source_authority_pins = _validate_source_authorities()
    goal15 = _read_json(GOAL15_TRANSPARENT_PATH)
    _validate_embedded_integrity(goal15, "integrity_sha256")

    case_matrix, logical_contexts, goal16_metrics, goal15_metrics = (
        _build_case_matrix(goal15)
    )
    representative_context = copy.deepcopy(
        logical_contexts["syn_successor_v2_unique_cash"]
    )
    type_cards_hash = _sha256_json(representative_context["type_cards"])
    source_projection_hashes = {
        case_id: _sha256_json(context["source"])
        for case_id, context in logical_contexts.items()
    }

    machine_material = {
        "schema_version": (
            "broker_reports_gate2_type_first_fail_closed_machine_contract_v1"
        ),
        "goal_identity": GOAL_ID,
        "base_commit": BASE_COMMIT,
        "contract_identities": copy.deepcopy(CONTRACT_IDENTITIES),
        "status": copy.deepcopy(STATUS),
        "model_visible_contract": {
            "field_order": list(FIELD_ORDER),
            "root_fields_total": len(FIELD_ORDER),
            "exact_system_message": EXACT_SYSTEM_MESSAGE,
            "exact_task": EXACT_TASK,
            "local_type_key_order": list(LOCAL_TYPE_KEY_ORDER),
            "model_output_semantics": (
                "ordered_unique_exact_subsequence_of_type_cards"
            ),
            "serialized_user_context_order": list(FIELD_ORDER),
            "serialized_user_context_canonicalization": (
                "utf8_minified_json_preserve_insertion_order"
            ),
            "representative_user_context": representative_context,
            "type_cards_sha256": type_cards_hash,
            "source_projection_sha256_by_case": source_projection_hashes,
            "source_requirement": (
                "byte_equivalent_current_context_v2_1_semantic_projection"
            ),
            "type_cards_requirement": (
                "exact_current_managed_minimal_type_cards_in_current_order"
            ),
            "type_card_wording_copied_into_python_total": 0,
            "excluded_fields": list(_MODEL_VIEW_EXCLUDED_FIELDS),
        },
        "response_contract": {
            "logical_schema": copy.deepcopy(RESPONSE_SCHEMA),
            "schema_sha256": _sha256_json(RESPONSE_SCHEMA),
            "task_sha256": _sha256_bytes(EXACT_TASK.encode("utf-8")),
            "field_order_sha256": _sha256_json(list(FIELD_ORDER)),
            "real_profile_enum_binding": (
                "exact_visible_type_cards[*].type_key"
            ),
            "real_profile_max_items_binding": (
                "count(exact_visible_type_cards)"
            ),
            "valid_examples": [
                {"plausible_types": []},
                {"plausible_types": ["type_1"]},
                {"plausible_types": ["type_1", "type_2"]},
            ],
            "null_allowed": False,
            "reason_allowed": False,
            "selected_choice_allowed": False,
            "free_text_allowed": False,
            "canonical_backend_ids_allowed": False,
            "repair_sort_dedupe_allowed": False,
        },
        "private_mapping_contract": {
            "model_visible": False,
            "baseline_local_to_canonical": copy.deepcopy(
                PRIVATE_TYPE_MAPPING
            ),
            "future_profile_receipt_exists": False,
            "future_profile_receipt_hash": None,
            "required_bindings": [
                "context_profile",
                "visible_type_card_order",
                "semantic_pack_identity",
                "managed_projection_identity",
                "evidence_bundle_scope",
                "candidate_compilation_scope",
                "integrity_sha256",
            ],
            "unknown_removed_reordered_or_resealed_mapping": (
                "technical_contract_failure"
            ),
        },
        "single_variable_experiment_boundary": {
            "reused_without_semantic_change": [
                "current_context_v2_1_source",
                "current_context_v2_1_type_cards",
                "current_managed_minimal_projection",
                "current_semantic_pack",
                "current_source_hierarchy",
                "current_exact_source_literals",
            ],
            "changed_only": [
                "semantic_task",
                "response_schema",
                "absence_of_record_construction_signals",
            ],
            "forbidden_concurrent_changes": [
                "type_card_wording",
                "source_grouping",
                "type_boundaries",
                "semantic_pack",
                "expected_answers",
            ],
        },
        "decision_table": _build_decision_table(),
        "technical_failures": {
            "response_negative_fixtures": [
                {
                    "fixture_id": item["fixture_id"],
                    "expected_error_code": item["expected_error_code"],
                }
                for item in TECHNICAL_RESPONSE_NEGATIVE_FIXTURES
            ],
            "contract_integrity_negative_fixtures": [
                {
                    "fixture_id": item["fixture_id"],
                    "expected_error_code": item["expected_error_code"],
                }
                for item in CONTRACT_INTEGRITY_NEGATIVE_FIXTURES
            ],
            "backend_restoration_negative_fixtures": [
                {
                    "fixture_id": item["fixture_id"],
                    "expected_error_code": item["expected_error_code"],
                }
                for item in BACKEND_RESTORATION_NEGATIVE_FIXTURES
            ],
            "response_root_not_object_code": "response_root_not_object",
            "terminal_behavior": {
                "semantic_reason_assigned": False,
                "unclassified_financial_input_written": False,
                "typed_record_materialized": False,
                "terminal_financial_domain_result_written": False,
                "technical_evidence_retained": True,
                "retry_total": 0,
                "repair_total": 0,
                "fallback_total": 0,
            },
        },
        "retention_rules": {
            "unclassified_routes": [
                "full_evidence_bundle_retained",
                "all_source_literals_retained",
                "all_provenance_retained",
                "all_source_ownership_retained",
                "no_cross_scope_movement",
                "no_duplicate_binding",
                "no_source_value_loss",
                "no_raw_provider_payload_in_product_paths",
            ],
            "typed_route": [
                "exact_code_owned_option_only",
                "model_returns_no_values_refs_or_bindings",
                "existing_validator_remains_authority",
                "existing_materializer_remains_authority",
                "model_output_is_not_a_financial_record",
                "existing_typed_evidence_path_unchanged",
            ],
        },
        "qualification": {
            "primary_risk": "FALSE_SINGLETON_TYPED_RISK",
            "risk_example": {
                "true_plausible_types": ["type_1", "type_2"],
                "incorrect_model_output": ["type_1"],
                "unsafe_path": (
                    "one_matching_complete_option_can_materialize_a_wrong_"
                    "typed_record"
                ),
            },
            "counters": list(QUALIFICATION_COUNTERS),
            "counter_definitions": {
                "plausible_type_set_exact_total": (
                    "responses whose ordered plausible type set exactly "
                    "equals the audited ordered set"
                ),
                "false_empty_total": (
                    "empty model sets when the audited set is non-empty"
                ),
                "false_singleton_total": (
                    "singleton model sets when the audited set cardinality "
                    "is not one"
                ),
                "false_superset_total": (
                    "model sets that are strict supersets of the audited set"
                ),
                "wrong_singleton_type_total": (
                    "singleton model and audited sets whose sole type keys "
                    "differ"
                ),
                "false_singleton_typed_total": (
                    "false singleton responses that reach a typed outcome"
                ),
                "unsafe_typed_total": (
                    "typed outcomes that do not equal the audited exact safe "
                    "code-owned option"
                ),
                "safe_under_typing_total": (
                    "unclassified outcomes where the audited singleton type "
                    "had exactly one complete validly prebound option"
                ),
                "invalid_response_total": (
                    "responses rejected as technical contract failures"
                ),
            },
            "hard_gates": copy.deepcopy(HARD_QUALIFICATION_GATES),
            "provider_qualification_performed": False,
            "model_quality_proven": False,
        },
        "ten_case_matrix": case_matrix,
        "authority_map": {
            "rows": copy.deepcopy(list(AUTHORITY_MAP)),
            "rows_total": len(AUTHORITY_MAP),
            "new_owner_required_total": 0,
            "semantic_prompt_asset": {
                "existing_owner": (
                    "V6_SEMANTIC_SYSTEM_PROMPT and "
                    "financial_semantic_v6_prompt"
                ),
                "goal16_change": "none_contract_only",
                "future_profile_change": "existing_prompt_owner",
                "new_owner_required": False,
            },
        },
        "byte_budget": _build_byte_budget(
            goal15_metrics=goal15_metrics,
            goal16_metrics=goal16_metrics,
        ),
        "variant_c_reservation": {
            "implemented": False,
            "stage2_exists_in_variant_b": False,
            "second_provider_call_allowed": False,
            "selected_choice_present": False,
            "same_type_multiple_option_outcome": (
                "single_registry_type_no_safe_record"
            ),
            "economy_policy": "one_call_existing_limit_retained",
            "multi_stage_replay_introduced": False,
            "future_reopen_requirements": [
                "accepted_real_same_type_multiple_option_evidence",
                "proof_of_one_mutually_exclusive_record_choice",
                "proven_frequency",
                "separate_stage2_safety_qualification",
                "measurable_net_completeness_gain",
            ],
        },
        "activation_boundary": {
            "contract_status": "inactive_normative_candidate",
            "runtime_implementation_performed": False,
            "runtime_activation": False,
            "provider_smoke_allowed": False,
            "next_goal": "NON_ACTIVE_TYPE_FIRST_CONTRACT_IMPLEMENTATION",
            "provider_smoke_prerequisites": [
                "non_active_implementation",
                "sealed_request_and_linter_proof",
                "three_provider_local_end_to_end_proof",
            ],
        },
        "change_accounting": {
            "provider_calls_total": 0,
            "runtime_changes_total": 0,
            "product_logic_changes_total": 0,
            "prompt_runtime_changes_total": 0,
            "pack_wording_changes_total": 0,
            "source_projection_changes_total": 0,
            "provider_adapter_changes_total": 0,
            "active_context_v2_1_changes_total": 0,
            "historical_files_modified_total": 0,
            "new_owners_total": 0,
        },
        "source_authority_pins": source_authority_pins,
        "evidence_lineage": {
            "goal15_recommendation": (
                "SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C"
            ),
            "goal15_transparent_integrity_sha256": goal15[
                "integrity_sha256"
            ],
            "matrix_is_mechanical_contract_evidence": True,
            "matrix_is_model_qualification": False,
            "goal16_private_mapping_receipt_created": False,
            "typed_option_identity_evidence": {
                "historical_explicit_total": 1,
                "current_factory_observation_frozen_by_goal16_total": 3,
                "builder_runtime_rederivation_performed": False,
                "current_factory_cross_check_required_by_test": True,
                "current_factory_cross_check_provider_calls_total": 0,
            },
        },
    }
    machine = _with_integrity(machine_material)
    _validate_machine_contract(machine)
    _validate_repository_safe_output(machine)

    contract_md = _render_contract(machine)
    report = _render_report(machine)
    _validate_repository_safe_text(contract_md)
    _validate_repository_safe_text(report)

    receipt_material = {
        "schema_version": (
            "broker_reports_gate2_type_first_fail_closed_contract_"
            "receipt_v1"
        ),
        "goal_identity": GOAL_ID,
        "base_commit": BASE_COMMIT,
        "contract_identity": CONTRACT_IDENTITIES["contract_identity"],
        "contract_version": "v1",
        "field_order": list(FIELD_ORDER),
        "schema_sha256": _sha256_json(RESPONSE_SCHEMA),
        "task_sha256": _sha256_bytes(EXACT_TASK.encode("utf-8")),
        "ten_case_count": len(case_matrix),
        "technical_negative_fixture_count": len(
            TECHNICAL_RESPONSE_NEGATIVE_FIXTURES
        ),
        "contract_integrity_negative_fixture_count": len(
            CONTRACT_INTEGRITY_NEGATIVE_FIXTURES
        ),
        "backend_restoration_negative_fixture_count": len(
            BACKEND_RESTORATION_NEGATIVE_FIXTURES
        ),
        "technical_negative_fixture_total": (
            len(TECHNICAL_RESPONSE_NEGATIVE_FIXTURES)
            + len(CONTRACT_INTEGRITY_NEGATIVE_FIXTURES)
            + len(BACKEND_RESTORATION_NEGATIVE_FIXTURES)
        ),
        "provider_calls_total": 0,
        "runtime_changes_total": 0,
        "product_logic_changes_total": 0,
        "historical_files_modified_total": 0,
        "new_owners_total": 0,
        "active": False,
        "transport_eligible": False,
        "runtime_activation": False,
        "contract_file_sha256": _sha256_bytes(
            contract_md.encode("utf-8")
        ),
        "artifact_file_sha256": _sha256_bytes(_json_bytes(machine)),
        "report_file_sha256": _sha256_bytes(report.encode("utf-8")),
        "integrity_canonicalization": (
            "utf8_minified_json_sort_keys_true_without_integrity_sha256"
        ),
    }
    receipt = _with_integrity(receipt_material)
    _validate_repository_safe_output(receipt)
    return contract_md, machine, report, receipt


def _build_case_matrix(
    goal15: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    source_cases = goal15.get("per_case_simulations")
    if not isinstance(source_cases, list):
        raise ValueError("goal15_case_matrix_missing")
    by_id = {
        item.get("case_id"): item
        for item in source_cases
        if isinstance(item, dict)
    }
    if list(by_id) != list(CASE_ORDER):
        raise ValueError("goal15_case_order_invalid")

    matrix: list[dict[str, Any]] = []
    contexts: dict[str, dict[str, Any]] = {}
    goal16_metrics: list[dict[str, Any]] = []
    goal15_metrics: list[dict[str, Any]] = []
    shared_type_cards_hash: str | None = None

    for case_id in CASE_ORDER:
        source_case = by_id[case_id]
        expected = CASE_EXPECTATIONS[case_id]
        plausible = source_case.get("audited_plausible_types")
        counts = source_case.get(
            "available_complete_option_counts_by_type"
        )
        if plausible != expected["plausible_local_types"]:
            raise ValueError(f"goal15_plausible_types_drift:{case_id}")
        if counts != expected["complete_option_counts_by_type"]:
            raise ValueError(f"goal15_option_counts_drift:{case_id}")

        variant_b = _find_variant_b(source_case)
        stage1 = variant_b.get("stage1_request", {})
        user_context = stage1.get("user_context", {})
        source = user_context.get("source_summary")
        type_cards = user_context.get("plausible_type_cards")
        if not isinstance(source, dict) or not isinstance(type_cards, list):
            raise ValueError(f"goal15_type_first_context_missing:{case_id}")
        local_order = [item.get("type_key") for item in type_cards]
        if local_order != list(LOCAL_TYPE_KEY_ORDER):
            raise ValueError(f"goal15_type_card_order_invalid:{case_id}")
        type_cards_hash = _sha256_json(type_cards)
        if shared_type_cards_hash is None:
            shared_type_cards_hash = type_cards_hash
        elif type_cards_hash != shared_type_cards_hash:
            raise ValueError(f"goal15_type_cards_drift:{case_id}")

        logical_context = {
            "task": EXACT_TASK,
            "source": copy.deepcopy(source),
            "type_cards": copy.deepcopy(type_cards),
        }
        if list(logical_context) != list(FIELD_ORDER):
            raise ValueError("goal16_field_order_invalid")
        forbidden = _recursive_keys(logical_context).intersection(
            _MODEL_VIEW_FORBIDDEN_KEYS
        )
        if forbidden:
            raise ValueError(
                "goal16_model_visible_forbidden_keys:"
                + ",".join(sorted(forbidden))
            )
        contexts[case_id] = logical_context

        logical_request = {
            "response_schema": copy.deepcopy(RESPONSE_SCHEMA),
            "user_context": copy.deepcopy(logical_context),
        }
        request_bytes = _ordered_compact_json_bytes(logical_request)
        metric = {
            "case_id": case_id,
            "request_utf8_bytes": len(request_bytes),
            "estimated_input_tokens": (
                math.ceil(len(request_bytes) / 4)
                + TOKEN_ESTIMATOR_OVERHEAD
            ),
            "request_sha256": _sha256_bytes(request_bytes),
        }
        if metric["request_utf8_bytes"] > 2500:
            raise ValueError(f"goal16_logical_request_budget:{case_id}")
        goal16_metrics.append(metric)

        baseline = variant_b.get("stage1_request_metrics")
        if not isinstance(baseline, dict):
            raise ValueError(f"goal15_request_metrics_missing:{case_id}")
        goal15_metrics.append(
            {
                "case_id": case_id,
                "request_utf8_bytes": baseline["request_utf8_bytes"],
                "estimated_input_tokens": baseline[
                    "estimated_input_tokens"
                ],
                "request_sha256": baseline["request_sha256"],
            }
        )

        selected_type = plausible[0] if len(plausible) == 1 else None
        matching_count = counts[selected_type] if selected_type else 0
        typed_identity = expected["typed_option_identity"]
        matching_ids = (
            [typed_identity]
            if selected_type is not None
            and matching_count == 1
            and typed_identity is not None
            else [f"complete-option-{index + 1}" for index in range(
                matching_count
            )]
        )
        result = derive_backend_decision(
            plausible,
            matching_ids,
            typed_option_id=typed_identity,
        )
        canonical_types = [
            PRIVATE_TYPE_MAPPING[item] for item in plausible
        ]
        route = _case_route(plausible, matching_count)
        expected_disposition = result["disposition"]
        unclassified_reason = result.get("reason_code")
        if expected_disposition == "typed_input":
            retention = "existing_typed_evidence_path_unchanged"
        else:
            retention = "full_evidence_bundle_retained"

        matrix.append(
            {
                "case_id": case_id,
                "plausible_local_types": copy.deepcopy(plausible),
                "plausible_canonical_types": canonical_types,
                "complete_option_counts_by_type": copy.deepcopy(counts),
                "route": route,
                "expected_disposition": expected_disposition,
                "typed_option_identity": typed_identity,
                "typed_option_pin_status": expected[
                    "typed_option_pin_status"
                ],
                "unclassified_reason": unclassified_reason,
                "source_retention_expectation": retention,
                "source_projection_sha256": _sha256_json(source),
                "mapping_receipt_integrity": (
                    MAPPING_RECEIPT_INTEGRITIES[case_id]
                ),
                "candidate_compilation_integrity": (
                    COMPILATION_INTEGRITIES[case_id]
                ),
                "logical_stage1_calls": 1,
                "stage2_calls": 0,
                "mechanical_contract_evidence_only": True,
            }
        )
    return matrix, contexts, goal16_metrics, goal15_metrics


def _find_variant_b(source_case: dict[str, Any]) -> dict[str, Any]:
    variants = source_case.get("variant_results")
    if not isinstance(variants, list):
        raise ValueError("goal15_variant_results_missing")
    matches = [
        item
        for item in variants
        if isinstance(item, dict)
        and item.get("variant_id") == "ONE_CALL_TYPE_FIRST_FAIL_CLOSED"
    ]
    if len(matches) != 1:
        raise ValueError("goal15_variant_b_not_unique")
    return matches[0]


def _case_route(plausible: list[str], matching_count: int) -> str:
    if len(plausible) == 0:
        return "zero_plausible_types"
    if len(plausible) >= 2:
        return "multiple_plausible_types"
    if matching_count == 1:
        return "singleton_type_one_complete_option"
    return "singleton_type_no_safe_record"


def _build_decision_table() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    samples = {
        "zero": [],
        "one": ["type_1"],
        "two_or_more": ["type_1", "type_2"],
    }
    options = {
        "zero": [],
        "one": ["option_1"],
        "two_or_more": ["option_1", "option_2"],
    }
    for plausible_label, plausible in samples.items():
        for options_label, option_ids in options.items():
            typed_option_id = (
                "option_1"
                if plausible_label == "one" and options_label == "one"
                else None
            )
            result = derive_backend_decision(
                plausible,
                option_ids,
                typed_option_id=typed_option_id,
            )
            rows.append(
                {
                    "plausible_type_cardinality": plausible_label,
                    "matching_complete_option_cardinality": options_label,
                    "disposition": result["disposition"],
                    "reason_code": result.get("reason_code"),
                    "restoration": (
                        "exact_code_owned_typed_option"
                        if result["disposition"] == "typed_input"
                        else None
                    ),
                    "complete_validly_prebound_options_only": True,
                    "option_counts_are_semantic_evidence": False,
                }
            )
    return rows


def _build_byte_budget(
    *,
    goal15_metrics: list[dict[str, Any]],
    goal16_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    goal15_bytes = [
        item["request_utf8_bytes"] for item in goal15_metrics
    ]
    goal15_tokens = [
        item["estimated_input_tokens"] for item in goal15_metrics
    ]
    goal16_bytes = [
        item["request_utf8_bytes"] for item in goal16_metrics
    ]
    goal16_tokens = [
        item["estimated_input_tokens"] for item in goal16_metrics
    ]
    return {
        "goal15_design_baseline_only": True,
        "goal15_logical_request_utf8_bytes": {
            "minimum": min(goal15_bytes),
            "maximum": max(goal15_bytes),
        },
        "goal15_estimated_planning_tokens": {
            "minimum": min(goal15_tokens),
            "maximum": max(goal15_tokens),
        },
        "goal15_aggregate_utf8_bytes": sum(goal15_bytes),
        "goal15_aggregate_estimated_planning_tokens": sum(
            goal15_tokens
        ),
        "goal15_per_case_metrics": copy.deepcopy(goal15_metrics),
        "goal16_provider_neutral_logical_request_utf8_bytes": {
            "minimum": min(goal16_bytes),
            "maximum": max(goal16_bytes),
        },
        "goal16_estimated_planning_tokens": {
            "minimum": min(goal16_tokens),
            "maximum": max(goal16_tokens),
        },
        "goal16_aggregate_utf8_bytes": sum(goal16_bytes),
        "goal16_aggregate_estimated_planning_tokens": sum(
            goal16_tokens
        ),
        "goal16_per_case_metrics": copy.deepcopy(goal16_metrics),
        "logical_request_basis": (
            "provider_neutral_response_schema_plus_exact_user_context"
        ),
        "goal16_request_serialization": (
            "utf8_minified_json_preserve_insertion_order"
        ),
        "goal16_user_context_field_order": list(FIELD_ORDER),
        "token_estimator_id": TOKEN_ESTIMATOR_ID,
        "provider_tokenizer_measurement": False,
        "future_provider_neutral_max_utf8_bytes": 2500,
        "increase_above_target_requires_stop_and_review": True,
        "sealed_request_proof_deferred": True,
        "future_stage1_calls_for_ten_cases": 10,
        "future_stage2_calls_for_ten_cases": 0,
        "future_worst_case_calls_per_operation": 1,
        "provider_calls_executed": 0,
    }


def _render_contract(machine: dict[str, Any]) -> str:
    model_view = machine["model_visible_contract"]
    response = machine["response_contract"]
    qualification = machine["qualification"]
    lines = [
        "# Broker Reports Gate 2 Type-First Fail-Closed Contract v1",
        "",
        (
            "Status: normative inactive candidate. Contract identity: "
            f"`{CONTRACT_IDENTITIES['contract_identity']}`."
        ),
        "",
        (
            "Context profile: "
            f"`{CONTRACT_IDENTITIES['context_profile']}`. Response profile: "
            f"`{CONTRACT_IDENTITIES['response_profile']}`. Decision policy: "
            f"`{CONTRACT_IDENTITIES['decision_policy']}`."
        ),
        "",
        (
            "For every profile: `active = false`, "
            "`transport_eligible = false`, `runtime_activation = false`, "
            "`provider_calls_total = 0`, `fallback_allowed = false`, "
            "`repair_allowed = false`, and `retry_allowed = false`."
        ),
        "",
        (
            "Machine-readable contract: "
            "[BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json]"
            "(BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json)."
        ),
        "",
        (
            "GOAL 16 evidence: "
            f"[report](../../reports/2026-07-30/{REPORT_PATH.name}) and "
            f"[safe receipt](../../reports/2026-07-30/{RECEIPT_PATH.name})."
        ),
        "",
        "## 1. Purpose",
        "",
        (
            "This contract normatively fixes Variant B, "
            "`ONE_CALL_TYPE_FIRST_FAIL_CLOSED`, as the MVP contract. It "
            "defines one model decision and a closed backend policy. It does "
            "not implement or activate runtime behavior and does not qualify "
            "a model."
        ),
        "",
        "## 2. Semantic responsibility boundary",
        "",
        (
            "The model returns only the ordered set of plausible local "
            "financial type keys. It never sees constructible choices and "
            "never chooses a reason, record, value, ref or binding."
        ),
        "",
        (
            "Code validates the response without repair, restores the private "
            "local-to-canonical mapping, derives the reason from cardinality, "
            "filters complete validly prebound options for a singleton type, "
            "and permits typed materialization only for exactly one matching "
            "code-owned option. Constructibility is not semantic evidence."
        ),
        "",
        "## 3. Exact model-visible context",
        "",
        "The system message remains exactly:",
        "",
        f"> {EXACT_SYSTEM_MESSAGE}",
        "",
        "The user message has exactly three ordered root fields:",
        "",
        "1. `task`",
        "2. `source`",
        "3. `type_cards`",
        "",
        "The semantic task is exactly:",
        "",
        f"> {EXACT_TASK}",
        "",
        "Representative governed logical context:",
        "",
        "```json",
        _pretty_json(model_view["representative_user_context"]),
        "```",
        "",
        (
            "`source` is the byte-equivalent semantic projection of current "
            "Context V2.1: every governed source literal is retained exactly, "
            "the real hierarchy is retained, no association is invented, and "
            "no backend ref or option-construction signal is visible. "
            "`type_cards` are the exact current managed minimal cards in "
            "current order, with local keys only and no Python copy of their "
            "wording."
        ),
        "",
        (
            "The future candidate reuses without semantic change the current "
            "Context V2.1 `source` and `type_cards`, managed minimal "
            "projection, Semantic Pack, source hierarchy, and exact source "
            "literals. Only the semantic task, response schema, and absence "
            "of record-construction signals change."
        ),
        "",
        (
            "Concurrent changes to type-card wording, source grouping, type "
            "boundaries, the Semantic Pack, or expected answers are "
            "forbidden. Choices, complete options, differentiators, "
            "unclassified reasons, Typed Option IDs, canonical IDs, compiler "
            "counts, bindings, refs, hashes, and materialization metadata are "
            "absent from the model-visible scope."
        ),
        "",
        "## 4. Exact response schema",
        "",
        "```json",
        _pretty_json(response["logical_schema"]),
        "```",
        "",
        "A valid singleton response is:",
        "",
        "```json",
        _pretty_json({"plausible_types": ["type_1"]}),
        "```",
        "",
            (
                "The array is an ordered set and must be an exact subsequence of "
                "`type_cards`. Empty is valid. Null, duplicates, unknown keys, "
                "extra fields, free text and backend IDs are invalid. Out-of-order "
                "keys fail technically; code must not sort, deduplicate or retry."
            ),
            "",
            (
                "For every real inactive profile instance, `enum` is derived "
                "from the exact visible `type_cards[*].type_key` sequence and "
                "`maxItems` equals the number of visible cards. The two-card "
                "schema above is the exact governed v1 baseline."
            ),
            "",
        "## 5. Private mapping",
        "",
        (
            "The backend-only baseline mapping used by the ten-case contract "
            "matrix is:"
        ),
        "",
        "```json",
        _pretty_json(PRIVATE_TYPE_MAPPING),
        "```",
        "",
        (
            "The future profile must create its own sealed private mapping "
            "receipt bound to Context profile, visible card order, Semantic "
            "Pack, managed projection, Evidence Bundle and Candidate "
            "Compilation scopes, plus its `integrity_sha256`. Unknown, "
            "removed, reordered, or resealed mappings fail closed as a "
            "technical contract failure. GOAL 16 does not create that "
            "receipt. The model sees neither the mapping nor canonical IDs."
        ),
        "",
        "## 6. Deterministic decision table",
        "",
        (
            "Only complete, validly prebound options of the mapped singleton "
            "type count. Option counts do not modify the plausible type set."
        ),
        "",
        (
            "| Plausible types | Matching complete options | Result | "
            "Reason/restoration |"
        ),
        "|---|---|---|---|",
    ]
    for row in machine["decision_table"]:
        detail = (
            row["reason_code"]
            if row["reason_code"] is not None
            else row["restoration"]
        )
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` |".format(
                row["plausible_type_cardinality"],
                row["matching_complete_option_cardinality"],
                row["disposition"],
                detail,
            )
        )
    lines.extend(
        [
            "",
            (
                "Zero types always yields `no_registry_type`. Two or more "
                "types always yields `ambiguous_registry_type`. A singleton "
                "with zero or multiple matching options yields "
                "`single_registry_type_no_safe_record`. Only singleton plus "
                "one matching option restores the unchanged V6 typed Choice; "
                "the typed result contains no reason code."
            ),
            "",
            "## 7. Technical failures",
            "",
            (
                "Technical failures are not semantic answers. They write no "
                "terminal Financial Domain result, materialize no record, "
                "retain technical evidence and perform no retry, repair or "
                "fallback."
            ),
            "",
            "| Failure class | Exact error code |",
            "|---|---|",
        ]
    )
    for item in machine["technical_failures"][
        "response_negative_fixtures"
    ]:
        lines.append(
            f"| `{item['fixture_id']}` | `{item['expected_error_code']}` |"
        )
    for item in machine["technical_failures"][
        "contract_integrity_negative_fixtures"
    ]:
        lines.append(
            f"| `{item['fixture_id']}` | `{item['expected_error_code']}` |"
        )
    for item in machine["technical_failures"][
        "backend_restoration_negative_fixtures"
    ]:
        lines.append(
            f"| `{item['fixture_id']}` | `{item['expected_error_code']}` |"
        )
    lines.extend(
        [
            "",
            "## 8. False singleton risk",
            "",
            (
                "`FALSE_SINGLETON_TYPED_RISK` is the primary safety risk. If "
                "the true set is `[\"type_1\", \"type_2\"]`, but the model "
                "incorrectly returns `[\"type_1\"]`, one complete option for "
                "`type_1` can produce a semantically wrong typed record. "
                "Backend cardinality checks cannot detect this model error."
            ),
            "",
            "```json",
            _pretty_json(qualification["risk_example"]),
            "```",
            "",
            "## 9. Retention and ownership",
            "",
            (
                "Every unclassified route retains the full Evidence Bundle, "
                "all source literals, provenance and ownership. It performs "
                "no cross-scope movement, duplicate binding or source-value "
                "loss. The typed route restores only an exact code-owned "
                "option; existing validation and materialization remain the "
                "authorities. Raw provider payloads never enter product paths."
            ),
            "",
            "## 10. Qualification counters and hard gates",
            "",
            "Future qualification must count:",
            "",
        ]
    )
    lines.extend(
        (
            f"- `{item}` — "
            f"{qualification['counter_definitions'][item]}."
        )
        for item in qualification["counters"]
    )
    lines.extend(
        [
            "",
            "Hard gates:",
            "",
            "```json",
            _pretty_json(qualification["hard_gates"]),
            "```",
            "",
            (
                "GOAL 16 defines these counters and gates only. It performs "
                "no provider qualification and proves no model quality."
            ),
            "",
            "## 11. Ten-case matrix",
            "",
            (
                "| Case | Local plausible set | Canonical set | Options "
                "type_1/type_2 | Route | Outcome | Retention |"
            ),
            "|---|---|---|---:|---|---|---|",
        ]
    )
    for row in machine["ten_case_matrix"]:
        counts = row["complete_option_counts_by_type"]
        outcome = (
            row["typed_option_identity"]
            if row["typed_option_identity"] is not None
            else row["unclassified_reason"]
        )
        lines.append(
            "| `{}` | `{}` | `{}` | `{}/{}` | `{}` | `{}` | `{}` |".format(
                row["case_id"],
                _compact_json(row["plausible_local_types"]),
                _compact_json(row["plausible_canonical_types"]),
                counts["type_1"],
                counts["type_2"],
                row["route"],
                outcome,
                row["source_retention_expectation"],
            )
        )
    lines.extend(
        [
            "",
            (
                "This matrix is frozen mechanical contract evidence copied "
                "from pinned GOAL 15 inputs. It is not model qualification. "
                "One typed-option ID was explicit in historical evidence. "
                "Three additional IDs are current-factory observations frozen "
                "normatively by GOAL 16 and independently cross-checked by "
                "the GOAL 16 repository test. The stdlib-only builder does not "
                "import runtime or claim to rederive those three IDs."
            ),
            "",
            "## 12. Authority map",
            "",
            "| Concern | Existing owner | Future change | New owner |",
            "|---|---|---|---:|",
        ]
    )
    for row in machine["authority_map"]["rows"]:
        lines.append(
            "| `{}` | `{}` | `{}` | `{}` |".format(
                row["concern"],
                row["existing_owner"],
                row["future_profile_change"],
                str(row["new_owner_required"]).lower(),
            )
        )
    lines.extend(
        [
            "",
            (
                "The exact existing Prompt owner remains "
                "`V6_SEMANTIC_SYSTEM_PROMPT` / "
                "`financial_semantic_v6_prompt` in "
                "`services/broker-reports-gate1-proof/broker_reports_gate1/"
                "gate2_financial_semantic_v6_prompt.py`. It is not a new "
                "routing authority. Total new owners required: `0`."
            ),
            "",
            "## 13. Byte budget",
            "",
            (
                "GOAL 15 Variant B was a design baseline of 2,050–2,208 "
                "provider-neutral logical request bytes and 577–616 planning "
                "tokens. GOAL 16 changes field names, task text and schema, so "
                "its request hashes are newly calculated rather than reused."
            ),
            "",
            "```json",
            _pretty_json(
                {
                    "goal16_logical_request_utf8_bytes": machine[
                        "byte_budget"
                    ][
                        "goal16_provider_neutral_logical_request_utf8_bytes"
                    ],
                    "goal16_estimated_planning_tokens": machine[
                        "byte_budget"
                    ]["goal16_estimated_planning_tokens"],
                    "target_max_utf8_bytes": 2500,
                    "provider_tokenizer_measurement": False,
                }
            ),
            "```",
            "",
            (
                "The estimator is planning-only. Full provider-specific "
                "sealed request cost is deferred. Any governed logical request "
                "above 2,500 bytes requires STOP and a separate review."
            ),
            "",
            "## 14. Variant C reservation",
            "",
            (
                "Variant C is not implemented. Variant B has no Stage 2, no "
                "second call, no `selected_choice`, no multi-stage replay and "
                "no same-type record selection. Multiple complete options of "
                "one type fail closed as "
                "`single_registry_type_no_safe_record`. Economy Policy stays "
                "one-call."
            ),
            "",
            (
                "Variant C may be reconsidered only with accepted real "
                "same-type/multiple-option evidence, proof that the options "
                "are one mutually exclusive record choice, proven frequency, "
                "separate Stage 2 safety qualification and measurable net "
                "completeness gain."
            ),
            "",
            "## 15. Activation boundary",
            "",
            (
                "All GOAL 16 profiles remain inactive and transport "
                "ineligible. Runtime, active Context V2.1, active Choice, "
                "Prompt runtime, Pack, projection, adapters and product logic "
                "are unchanged. Provider calls are zero."
            ),
            "",
            (
                "The next separate GOAL is "
                "`NON-ACTIVE TYPE-FIRST CONTRACT IMPLEMENTATION`. Provider "
                "smoke remains forbidden until non-active implementation, "
                "sealed request/linter proof and three-provider local "
                "end-to-end proof all exist."
            ),
            "",
            "**STOP AFTER GOAL 16.**",
            "",
        ]
    )
    return "\n".join(lines)


def _render_report(machine: dict[str, Any]) -> str:
    budget = machine["byte_budget"]
    lines = [
        "# Broker Reports Gate 2 GOAL 16 Contract Report",
        "",
        "Status: `COMPLETED_OFFLINE_INACTIVE_CONTRACT_EVIDENCE`.",
        "",
        "## Outcome",
        "",
        (
            "Program decision `SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C` is now "
            "expressed as one normative versioned inactive contract: "
            f"`{CONTRACT_IDENTITIES['contract_identity']}`."
        ),
        "",
        (
            "Canonical contract: "
            "[BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md]"
            "(../../stage2/contracts/"
            "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md)."
        ),
        "",
        (
            "Machine artifact: "
            "[BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json]"
            "(../../stage2/contracts/"
            "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json)."
        ),
        "",
        "## Contract surface",
        "",
        "```json",
        _pretty_json(
            {
                "contract_identities": machine["contract_identities"],
                "field_order": machine["model_visible_contract"][
                    "field_order"
                ],
                "status": machine["status"],
            }
        ),
        "```",
        "",
        (
            "The model sees only `task`, `source`, and `type_cards`, in that "
            "order, and returns only `plausible_types`. Code owns mapping, "
            "reason derivation, exact option restoration, validation and "
            "materialization."
        ),
        "",
        "## Safety result",
        "",
        (
            "The nine-cell decision policy is total. Zero plausible types "
            "always gives `no_registry_type`; two or more always gives "
            "`ambiguous_registry_type`; a singleton types only when exactly "
            "one complete validly prebound option exists. Zero or multiple "
            "matching options fail closed."
        ),
        "",
        (
            "The principal unresolved safety risk is "
            "`FALSE_SINGLETON_TYPED_RISK`. Model quality has not been "
            "qualified; all four future hard gates therefore remain "
            "requirements, not results."
        ),
        "",
        "## Evidence and verification",
        "",
        "```json",
        _pretty_json(
            {
                "governed_cases": len(machine["ten_case_matrix"]),
                "response_negative_fixtures": len(
                    machine["technical_failures"][
                        "response_negative_fixtures"
                    ]
                ),
                "contract_integrity_negative_fixtures": len(
                    machine["technical_failures"][
                        "contract_integrity_negative_fixtures"
                    ]
                ),
                "backend_restoration_negative_fixtures": len(
                    machine["technical_failures"][
                        "backend_restoration_negative_fixtures"
                    ]
                ),
                "historical_pins": sum(
                    item["category"] == "historical"
                    for item in machine["source_authority_pins"]
                ),
                "active_pins": sum(
                    item["category"] == "active"
                    for item in machine["source_authority_pins"]
                ),
                "new_owners": 0,
            }
        ),
        "```",
        "",
        (
            "All ten governed cases reproduce the GOAL 15 Variant B matrix. "
            "Historical GOAL 12–15 outputs and active Context/Choice/Pack/"
            "projection/Prompt/adapter authorities are hash-pinned. The "
            "offline validator is standard-library-only and is not imported "
            "by runtime. A separate repository test rebuilds current local "
            "factory outputs to cross-check source/type-card parity and the "
            "four typed-option identities without provider calls."
        ),
        "",
        "## Byte and call boundary",
        "",
        "```json",
        _pretty_json(
            {
                "goal15_baseline_bytes": budget[
                    "goal15_logical_request_utf8_bytes"
                ],
                "goal16_logical_bytes": budget[
                    "goal16_provider_neutral_logical_request_utf8_bytes"
                ],
                "future_max_bytes": budget[
                    "future_provider_neutral_max_utf8_bytes"
                ],
                "future_worst_case_calls_per_operation": 1,
                "provider_calls_executed": 0,
            }
        ),
        "```",
        "",
        (
            "GOAL 16 request hashes are newly derived because its exact task, "
            "root field names and schema differ from GOAL 15. The planning "
            "serializer preserves the normative `task`, `source`, "
            "`type_cards` order. The estimator is not a provider tokenizer. "
            "Full sealed-request proof is deferred."
        ),
        "",
        "## Remaining work and STOP",
        "",
        (
            "Variant C remains reserved and unimplemented. The type-first "
            "model has not been qualified. The future private mapping receipt "
            "does not yet exist."
        ),
        "",
        (
            "Next: a separate non-active implementation GOAL, then sealed "
            "request/linter proof, then three-provider local end-to-end proof. "
            "No runtime implementation or provider smoke is authorized here."
        ),
        "",
        "**STOP AFTER GOAL 16.**",
        "",
    ]
    return "\n".join(lines)


def _validate_machine_contract(machine: dict[str, Any]) -> None:
    if machine["contract_identities"] != CONTRACT_IDENTITIES:
        raise ValueError("contract_identities_invalid")
    if machine["status"] != STATUS:
        raise ValueError("contract_status_invalid")
    model_view = machine["model_visible_contract"]
    if model_view["field_order"] != list(FIELD_ORDER):
        raise ValueError("model_visible_field_order_invalid")
    if list(model_view["representative_user_context"]) != list(FIELD_ORDER):
        raise ValueError("model_visible_context_order_invalid")
    serialized_context = _ordered_compact_json_bytes(
        model_view["representative_user_context"]
    )
    if list(json.loads(serialized_context)) != list(FIELD_ORDER):
        raise ValueError("model_visible_serialized_context_order_invalid")
    if model_view["serialized_user_context_order"] != list(FIELD_ORDER):
        raise ValueError("model_visible_serialized_order_metadata_invalid")
    if model_view["exact_task"] != EXACT_TASK:
        raise ValueError("model_visible_task_invalid")
    if (
        _recursive_keys(model_view["representative_user_context"])
        .intersection(_MODEL_VIEW_FORBIDDEN_KEYS)
    ):
        raise ValueError("model_visible_forbidden_surface")
    if machine["response_contract"]["logical_schema"] != RESPONSE_SCHEMA:
        raise ValueError("response_schema_invalid")

    for example in machine["response_contract"]["valid_examples"]:
        validate_response_object(example)
    for fixture in TECHNICAL_RESPONSE_NEGATIVE_FIXTURES:
        try:
            validate_response_text(fixture["response_text"])
        except TypeFirstContractValidationError as error:
            if error.code != fixture["expected_error_code"]:
                raise ValueError(
                    "response_negative_fixture_error_code_invalid:"
                    f"{fixture['fixture_id']}"
                ) from error
        else:
            raise ValueError(
                f"response_negative_fixture_accepted:{fixture['fixture_id']}"
            )
    for fixture in CONTRACT_INTEGRITY_NEGATIVE_FIXTURES:
        try:
            validate_seal_match(
                fixture["kind"],
                fixture["observed"],
                fixture["expected"],
            )
        except TypeFirstContractValidationError as error:
            if error.code != fixture["expected_error_code"]:
                raise ValueError(
                    "integrity_negative_fixture_error_code_invalid:"
                    f"{fixture['fixture_id']}"
                ) from error
        else:
            raise ValueError(
                f"integrity_negative_fixture_accepted:{fixture['fixture_id']}"
            )
    for fixture in BACKEND_RESTORATION_NEGATIVE_FIXTURES:
        try:
            derive_backend_decision(
                fixture["plausible_types"],
                fixture["matching_option_ids"],
                typed_option_id=fixture["typed_option_id"],
            )
        except TypeFirstContractValidationError as error:
            if error.code != fixture["expected_error_code"]:
                raise ValueError(
                    "backend_restoration_negative_fixture_error_code_invalid:"
                    f"{fixture['fixture_id']}"
                ) from error
        else:
            raise ValueError(
                "backend_restoration_negative_fixture_accepted:"
                f"{fixture['fixture_id']}"
            )
    if len(machine["decision_table"]) != 9:
        raise ValueError("decision_table_not_total")
    if [item["case_id"] for item in machine["ten_case_matrix"]] != list(
        CASE_ORDER
    ):
        raise ValueError("ten_case_matrix_invalid")
    if machine["authority_map"]["rows_total"] != 12:
        raise ValueError("authority_rows_invalid")
    if machine["authority_map"]["new_owner_required_total"] != 0:
        raise ValueError("new_owner_required")
    if machine["qualification"]["counters"] != list(
        QUALIFICATION_COUNTERS
    ):
        raise ValueError("qualification_counters_invalid")
    if machine["qualification"]["hard_gates"] != HARD_QUALIFICATION_GATES:
        raise ValueError("qualification_hard_gates_invalid")
    if any(machine["change_accounting"].values()):
        raise ValueError("goal16_change_accounting_nonzero")
    _validate_embedded_integrity(machine, "integrity_sha256")


def _validate_source_authorities() -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for category, pins in (
        ("historical", HISTORICAL_SOURCE_PINS),
        ("active", ACTIVE_SOURCE_PINS),
    ):
        for identity, repository_path, expected_hash in pins:
            path = REPO_ROOT / repository_path
            if not path.is_file():
                raise ValueError(f"source_authority_missing:{identity}")
            actual = _sha256_bytes(
                _repository_lf_bytes(path.read_bytes())
            )
            if actual != expected_hash:
                raise ValueError(
                    f"source_authority_hash_invalid:{identity}:{actual}"
                )
            result.append(
                {
                    "identity": identity,
                    "repository_path": repository_path,
                    "sha256": actual,
                    "category": category,
                }
            )
    return result


def write_or_check_outputs(
    *,
    outputs: dict[Path, bytes],
    check: bool,
) -> None:
    for path, expected in outputs.items():
        if check:
            if not path.is_file() or path.read_bytes() != expected:
                raise SystemExit(
                    f"type_first_fail_closed_contract_drift:{path.name}"
                )
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)


def _validate_repository_safe_output(value: dict[str, Any]) -> None:
    forbidden_keys = {
        "api_key",
        "authorization",
        "credential",
        "customer_data",
        "filesystem_path",
        "hidden_reasoning",
        "managed_to_local_type_mapping",
        "private_ref",
        "provider_envelope",
        "raw_provider_envelope",
        "raw_provider_payload",
        "secret",
    }
    forbidden = _recursive_keys(value).intersection(forbidden_keys)
    if forbidden:
        raise ValueError(
            "repository_safe_output_forbidden_keys:"
            + ",".join(sorted(forbidden))
        )
    _validate_repository_safe_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    )


def _validate_repository_safe_text(value: str) -> None:
    if _LOCAL_PATH_RE.search(value):
        raise ValueError("repository_safe_output_local_path")
    lowered = value.lower()
    for marker in ("bearer ", "x-api-key", "api-key"):
        if marker in lowered:
            raise ValueError(f"repository_safe_output_marker:{marker}")


def _validate_embedded_integrity(
    value: dict[str, Any],
    field: str,
) -> None:
    material = copy.deepcopy(value)
    supplied = material.pop(field, None)
    if supplied != _sha256_json(material):
        raise ValueError(f"embedded_integrity_invalid:{field}")


def _with_integrity(material: dict[str, Any]) -> dict[str, Any]:
    return {
        **copy.deepcopy(material),
        "integrity_sha256": _sha256_json(material),
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_not_object:{path.name}")
    return value


def _repository_lf_bytes(value: bytes) -> bytes:
    if b"\r" in value.replace(b"\r\n", b""):
        raise ValueError("source_authority_lone_carriage_return")
    return value.replace(b"\r\n", b"\n")


def _recursive_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(_recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_recursive_keys(item))
    return keys


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _ordered_compact_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pretty_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=False,
        indent=2,
        allow_nan=False,
    )


def _compact_json(value: Any) -> str:
    return _canonical_json_bytes(value).decode("utf-8")


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
