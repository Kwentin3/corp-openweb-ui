"""Build the offline GOAL 14 Context V2.1 comparative evidence pack."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-07-30"
OUTPUT_STEM = (
    "BROKER_REPORTS_GATE2_CONTEXT_V2_1_"
    "EVIDENCE_FIRST_COMPARATIVE_REVIEW_GOAL14"
)
REPORT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.report.md"
TRANSPARENT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.transparent.json"
RECEIPT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.receipt.safe.json"

GOAL12_ROOT = REPO_ROOT / "docs" / "reports" / "2026-07-29"
GOAL13_ROOT = REPO_ROOT / "docs" / "reports" / "2026-07-30"
GOAL12_PRECALL_PLAN_PATH = (
    GOAL12_ROOT
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
    ".precall.plan.safe.json"
)
GOAL12_PRECALL_TRANSPARENT_PATH = (
    GOAL12_ROOT
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
    ".precall.transparent.json"
)
GOAL12_REPORT_PATH = (
    GOAL12_ROOT
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
    ".report.md"
)
GOAL12_TRANSPARENT_PATH = (
    GOAL12_ROOT
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
    ".transparent.json"
)
GOAL12_RECEIPT_PATH = (
    GOAL12_ROOT
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_BUDGET_MODEL_SMOKE_GOAL12"
    ".receipt.safe.json"
)
GOAL13_REPORT_PATH = (
    GOAL13_ROOT
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_GOAL13"
    ".report.md"
)
GOAL13_RECEIPT_PATH = (
    GOAL13_ROOT
    / "BROKER_REPORTS_GATE2_CONTEXT_V2_1_POST_SMOKE_FORENSIC_AUDIT_GOAL13"
    ".receipt.safe.json"
)
SUCCESSOR_MANIFEST_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
OUTCOME_AUDIT_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v6_outcome_audit_v1"
    / "manifest.json"
)
SEMANTIC_PACK_PATH = (
    SERVICE_ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
REASON_CATALOG_PATH = (
    SERVICE_ROOT
    / "managed_assets"
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v2.json"
)

SOURCE_AUTHORITIES = (
    (
        "goal12_precall_plan",
        GOAL12_PRECALL_PLAN_PATH,
        "2b3a25cd04f0fffc6532477a44b93f6ce78e7e32f76bc239cceb13a2f5abacfe",
    ),
    (
        "goal12_precall_transparent",
        GOAL12_PRECALL_TRANSPARENT_PATH,
        "f64ef2e1daa92cc3eaa204ed34f1e753595ce0d4c7a4fd937492a6c145c58537",
    ),
    (
        "goal12_terminal_report",
        GOAL12_REPORT_PATH,
        "fa5d4e6d5961124e59bcd4204291772476dc7afb6c41ee80b719b658b3d3664b",
    ),
    (
        "goal12_terminal_transparent",
        GOAL12_TRANSPARENT_PATH,
        "7f4718f13763c9963592326e8481072606219435495fb6fbd59655a881197281",
    ),
    (
        "goal12_terminal_receipt",
        GOAL12_RECEIPT_PATH,
        "b4e77203c7fdffd96ad09b4a7ef5364ccef09072c8fc645e38a36a142dfffc8b",
    ),
    (
        "goal13_forensic_report",
        GOAL13_REPORT_PATH,
        "7161542710ef9c33a45d3c16fb30f10ed97636e1d59d6c2e01bad88083a0379b",
    ),
    (
        "goal13_forensic_receipt",
        GOAL13_RECEIPT_PATH,
        "7c350ce0b24c8e252fc963cf9d9d7c05d3a895c169fb855dcb16afcfc9226735",
    ),
    (
        "successor_v2_fixture_manifest",
        SUCCESSOR_MANIFEST_PATH,
        "448a3ea8622a6421c292e5daccef4c5ae65c38a7720a83e1cb8151daa4d2e1aa",
    ),
    (
        "corrected_outcome_audit",
        OUTCOME_AUDIT_PATH,
        "9d99e32d80a38a3621821d0e1918584a82615cca1cf1212e481f5e52811b8249",
    ),
    (
        "unchanged_semantic_pack",
        SEMANTIC_PACK_PATH,
        "ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f",
    ),
    (
        "managed_reason_catalog_v2",
        REASON_CATALOG_PATH,
        "cb784fe262c08297b9cd71c84e2bf36195d214f7aec82f3cc74f5707a24dde24",
    ),
)

CASE_ORDER = (
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_detail_vs_subtotal",
    "syn_successor_v2_no_registry_type",
)
PROVIDER_ORDER = ("openai_gpt", "anthropic_claude")
EXPECTED_MODEL_IDS = {
    "openai_gpt": "gpt-5.4-nano-2026-03-17",
    "anthropic_claude": "claude-haiku-4-5-20251001",
}
MODEL_LABELS = {
    "openai_gpt": "Nano",
    "anthropic_claude": "Haiku",
}
EXPECTED_REASON_CODES = (
    "no_registry_type",
    "single_registry_type_no_safe_record",
    "ambiguous_registry_type",
)
ASSOCIATION_FINDINGS = {
    "syn_successor_v2_multiple_compatible": {
        "visibility": "partial",
        "basis": (
            "One row groups all six values, but the exact source contains no "
            "amount-to-description pair links."
        ),
    },
    "syn_successor_v2_detail_vs_subtotal": {
        "visibility": "partial",
        "basis": (
            "The exact meanings distinguish detail amount from subtotal "
            "amount, but the flat row contains no explicit pair or "
            "relationship binding."
        ),
    },
    "syn_successor_v2_no_registry_type": {
        "visibility": "yes",
        "basis": (
            "One amount, currency, date and description are grouped in one "
            "row with no competing value pair."
        ),
    },
}
INTERPRETATION_NOTES = {
    "syn_successor_v2_multiple_compatible": {
        "source_projection": (
            "Every literal survives, but amount-to-description pairing is "
            "absent. Causation is not established."
        ),
        "type_glossary": (
            "Both relevant cards and their reciprocal distinction are "
            "visible; no causal glossary defect is proven."
        ),
        "choices_presentation": (
            "Zero choices and an unclassified-only schema are directly "
            "present."
        ),
        "reason_contract": (
            "The proven mismatch locus is plausible-type cardinality 2+ to "
            "1; that does not prove the contract caused it."
        ),
        "model_capability": (
            "One exact response cannot isolate capability from presentation."
        ),
        "expected_answer_defect": (
            "Independent revalidation reproduces the expected answer and "
            "records expected_answer_defect_supported=false."
        ),
    },
    "syn_successor_v2_detail_vs_subtotal": {
        "source_projection": (
            "No literal or amount role is lost; the flat row remains an "
            "unproved contributor."
        ),
        "type_glossary": (
            "The visible printed-metric card covers a labelled source total; "
            "no concrete glossary defect is shown."
        ),
        "choices_presentation": (
            "choices=[] establishes zero safe prebound records, not zero "
            "plausible types."
        ),
        "reason_contract": (
            "The proven mismatch locus is plausible-type cardinality 1 to 0; "
            "causal responsibility is not proven."
        ),
        "model_capability": (
            "The exact response cannot isolate model capability."
        ),
        "expected_answer_defect": (
            "Independent revalidation reproduces the corrected expected "
            "answer and records expected_answer_defect_supported=false."
        ),
    },
    "syn_successor_v2_no_registry_type": {
        "source_projection": (
            "All four values survive in one simple row; no projection defect "
            "creating two meanings is shown."
        ),
        "type_glossary": (
            "The full Pack detail-row exclusion is absent from the minimal "
            "visible card; its causal effect is unobserved."
        ),
        "choices_presentation": (
            "Two structural choices are visible while the audited plausible "
            "type set is empty."
        ),
        "reason_contract": (
            "The proven mismatch locus is plausible-type cardinality 0 to "
            "2+; the contract is not thereby proven causal."
        ),
        "model_capability": (
            "Capability cannot be separated from the supported presentation "
            "risks."
        ),
        "expected_answer_defect": (
            "Pack, reason catalog and corrected audit reproduce zero "
            "plausible types; expected_answer_defect_supported=false."
        ),
    },
}

_FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "authorization_headers",
        "credential",
        "credentials",
        "filesystem_path",
        "hidden_reasoning",
        "managed_to_local_type_mapping",
        "password",
        "private_backend_mapping",
        "private_mapping",
        "raw_provider_envelope",
        "raw_provider_response",
        "reasoning_trace",
        "repository_path",
        "response_id",
        "secret",
        "source_path",
        "type_mappings",
    }
)
_LOCAL_PATH_RE = re.compile(
    r"(?i)(?:^|[\"'`\s(])(?:[a-z]:[\\/]+users[\\/]+|/home/|/users/)"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail unless all committed GOAL 14 artifacts match generated bytes.",
    )
    arguments = parser.parse_args(argv)
    report, transparent, receipt = build_artifacts()
    outputs = {
        REPORT_PATH: report.encode("utf-8"),
        TRANSPARENT_PATH: _json_bytes(transparent),
        RECEIPT_PATH: _json_bytes(receipt),
    }
    write_or_check_outputs(outputs=outputs, check=arguments.check)
    print(
        json.dumps(
            {
                "status": "passed",
                "mode": "check" if arguments.check else "write",
                "case_count": len(transparent["cases"]),
                "provider_calls_total": 0,
                "runtime_changes_total": 0,
                "historical_files_modified_total": 0,
                "report_file_sha256": _sha256_bytes(outputs[REPORT_PATH]),
                "transparent_file_sha256": _sha256_bytes(
                    outputs[TRANSPARENT_PATH]
                ),
                "receipt_file_sha256": _sha256_bytes(outputs[RECEIPT_PATH]),
            },
            sort_keys=True,
        )
    )
    return 0


def build_artifacts() -> tuple[str, dict[str, Any], dict[str, Any]]:
    authority_hashes = _validate_source_authorities()
    goal12_plan = _read_json(GOAL12_PRECALL_PLAN_PATH)
    goal12_precall = _read_json(GOAL12_PRECALL_TRANSPARENT_PATH)
    goal12_terminal = _read_json(GOAL12_TRANSPARENT_PATH)
    goal13_receipt = _read_json(GOAL13_RECEIPT_PATH)
    successor_manifest = _read_json(SUCCESSOR_MANIFEST_PATH)
    outcome_audit = _read_json(OUTCOME_AUDIT_PATH)
    semantic_pack = _read_json(SEMANTIC_PACK_PATH)
    reason_catalog = _read_json(REASON_CATALOG_PATH)

    _validate_embedded_integrity(goal12_plan, "integrity_hash")
    _validate_embedded_integrity(goal12_precall, "integrity_sha256")
    _validate_embedded_integrity(goal12_terminal, "integrity_hash")
    _validate_embedded_integrity(goal13_receipt, "integrity_hash")
    _validate_embedded_integrity(outcome_audit, "integrity_sha256")
    _validate_embedded_integrity(semantic_pack, "integrity_sha256")
    _validate_embedded_integrity(reason_catalog, "integrity_sha256")

    cases = _build_cases(
        goal12_plan=goal12_plan,
        goal12_precall=goal12_precall,
        goal12_terminal=goal12_terminal,
        goal13_receipt=goal13_receipt,
        successor_manifest=successor_manifest,
        outcome_audit=outcome_audit,
        semantic_pack=semantic_pack,
        reason_catalog=reason_catalog,
    )
    parity_totals = _sum_parity(cases)
    transparent_material = {
        "schema_version": (
            "broker_reports_gate2_context_v2_1_comparative_evidence_v1"
        ),
        "status": "completed_offline_comparative_review",
        "active": False,
        "synthetic_evidence_only": True,
        "case_count": len(cases),
        "model_ids": [
            EXPECTED_MODEL_IDS[provider] for provider in PROVIDER_ORDER
        ],
        "source_evidence": [
            {
                "identity": identity,
                "repository_lf_sha256": authority_hashes[identity],
            }
            for identity, _path, _expected in SOURCE_AUTHORITIES
        ],
        "cases": cases,
        "verification": {
            "report_scope_case_ids": list(CASE_ORDER),
            "table_json_parity": parity_totals,
            "context_matches_goal12": True,
            "nano_outputs_match_goal12": True,
            "haiku_outputs_match_goal12": True,
            "expected_answers_match_corrected_audit": True,
            "historical_goal12_goal13_repository_lf_hashes_match": True,
            "source_authority_repository_lf_hashes_match": True,
            "privacy_validation": "passed",
        },
        "execution_accounting": {
            "provider_calls_total": 0,
            "provider_submissions_total": 0,
            "provider_responses_total": 0,
            "retry_total": 0,
            "repair_total": 0,
            "fallback_total": 0,
        },
        "change_accounting": {
            "corrective_implementation_changes_total": 0,
            "runtime_changes_total": 0,
            "product_logic_changes_total": 0,
            "prompt_changes_total": 0,
            "context_changes_total": 0,
            "semantic_pack_changes_total": 0,
            "choice_changes_total": 0,
            "source_projection_changes_total": 0,
            "expected_answer_changes_total": 0,
            "historical_files_modified_total": 0,
        },
        "production_admissions": [],
        "final_refactor_choice": "not_selected",
    }
    transparent = _with_integrity(transparent_material)
    _validate_repository_safe_output(transparent)

    report = _render_report(cases)
    receipt_material = {
        "schema_version": (
            "broker_reports_gate2_context_v2_1_comparative_receipt_v1"
        ),
        "source_evidence": [
            {
                "identity": identity,
                "repository_lf_sha256": authority_hashes[identity],
            }
            for identity, _path, _expected in SOURCE_AUTHORITIES
        ],
        "case_count": len(cases),
        "model_ids": [
            EXPECTED_MODEL_IDS[provider] for provider in PROVIDER_ORDER
        ],
        "case_hashes": [
            {
                "case_id": case["case_id"],
                "context_sha256": case["context"]["hashes"][
                    "exact_user_content_utf8_sha256"
                ],
                "nano_exact_output_sha256": case["providers"][0][
                    "exact_adapter_output"
                ]["exact_output_sha256"],
                "haiku_exact_output_sha256": case["providers"][1][
                    "exact_adapter_output"
                ]["exact_output_sha256"],
                "source_sha256": case["source"]["exact_source_sha256"],
            }
            for case in cases
        ],
        "table_json_parity": parity_totals,
        "provider_calls_total": 0,
        "runtime_changes_total": 0,
        "historical_files_modified_total": 0,
    }
    receipt = _with_integrity(receipt_material)
    _validate_repository_safe_output(receipt)
    return report, transparent, receipt


def _build_cases(
    *,
    goal12_plan: dict[str, Any],
    goal12_precall: dict[str, Any],
    goal12_terminal: dict[str, Any],
    goal13_receipt: dict[str, Any],
    successor_manifest: dict[str, Any],
    outcome_audit: dict[str, Any],
    semantic_pack: dict[str, Any],
    reason_catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    if goal12_plan.get("integrity_hash") != goal12_precall.get(
        "plan_integrity_hash"
    ):
        raise ValueError("goal12_plan_identity_mismatch")
    if goal12_terminal.get("plan_integrity_hash") != goal12_precall.get(
        "plan_integrity_hash"
    ):
        raise ValueError("goal12_terminal_plan_identity_mismatch")

    precall_by_slot = _unique_by(
        goal12_precall.get("slots"), "slot_id", "goal12_precall_slots"
    )
    terminal_by_slot = _unique_by(
        goal12_terminal.get("cases"), "slot_id", "goal12_terminal_cases"
    )
    plan_by_slot = _unique_by(
        goal12_plan.get("slots"), "slot_id", "goal12_plan_slots"
    )
    goal13_by_case = _unique_by(
        goal13_receipt.get("case_findings"),
        "case_id",
        "goal13_case_findings",
    )
    fixture_by_case = _unique_by(
        successor_manifest.get("cases"),
        "case_id",
        "successor_fixture_cases",
    )
    audit_by_case = _unique_by(
        outcome_audit.get("cases"), "case_id", "outcome_audit_cases"
    )
    pack_by_id = _unique_by(
        semantic_pack.get("full_compact_snapshot"),
        "input_type_id",
        "semantic_pack_types",
    )

    reason_codes = tuple(
        item["code"] for item in reason_catalog.get("reasons", ())
    )
    if reason_codes != EXPECTED_REASON_CODES:
        raise ValueError("managed_reason_catalog_order_or_content_drift")
    if outcome_audit.get("reason_catalog", {}).get(
        "semantic_integrity_sha256"
    ) != reason_catalog.get("integrity_sha256"):
        raise ValueError("outcome_audit_reason_catalog_binding_invalid")
    if outcome_audit.get("semantic_pack", {}).get(
        "semantic_integrity_sha256"
    ) != semantic_pack.get("integrity_sha256"):
        raise ValueError("outcome_audit_semantic_pack_binding_invalid")

    cases: list[dict[str, Any]] = []
    for ordinal, case_id in enumerate(CASE_ORDER, start=1):
        audit_case = _required(audit_by_case, case_id, "audit_case")
        fixture_case = _required(fixture_by_case, case_id, "fixture_case")
        forensic_case = _required(goal13_by_case, case_id, "forensic_case")
        provider_material: list[dict[str, Any]] = []
        provider_slots: dict[str, dict[str, Any]] = {}

        for provider_id in PROVIDER_ORDER:
            slot_id = f"{provider_id}:{case_id}"
            precall_slot = _required(precall_by_slot, slot_id, "precall_slot")
            terminal_case = _required(
                terminal_by_slot, slot_id, "terminal_case"
            )
            plan_slot = _required(plan_by_slot, slot_id, "plan_slot")
            _validate_slot_binding(
                precall_slot=precall_slot,
                terminal_case=terminal_case,
                plan_slot=plan_slot,
                provider_id=provider_id,
                case_id=case_id,
            )
            provider_slots[provider_id] = precall_slot
            provider_material.append(
                _build_provider_material(
                    precall_slot=precall_slot,
                    terminal_case=terminal_case,
                    provider_id=provider_id,
                )
            )

        openai_slot = provider_slots["openai_gpt"]
        anthropic_slot = provider_slots["anthropic_claude"]
        openai_visible = openai_slot["exact_model_visible_request"]
        anthropic_visible = anthropic_slot["exact_model_visible_request"]
        if openai_visible != anthropic_visible:
            raise ValueError(f"semantic_context_provider_drift:{case_id}")
        if (
            openai_slot["hashes"]["model_visible_request_hash"]
            != anthropic_slot["hashes"]["model_visible_request_hash"]
        ):
            raise ValueError(f"model_visible_request_hash_drift:{case_id}")

        messages = openai_visible.get("messages")
        if (
            not isinstance(messages, list)
            or len(messages) != 2
            or [item.get("role") for item in messages] != ["system", "user"]
        ):
            raise ValueError(f"canonical_messages_invalid:{case_id}")
        system_message = messages[0].get("content")
        exact_user_content = messages[1].get("content")
        if not isinstance(system_message, str) or not system_message:
            raise ValueError(f"exact_system_message_invalid:{case_id}")
        if not isinstance(exact_user_content, str) or not exact_user_content:
            raise ValueError(f"exact_user_content_invalid:{case_id}")
        semantic_context = json.loads(exact_user_content)
        if list(semantic_context) != [
            "task",
            "source",
            "type_cards",
            "choices",
            "unclassified_reasons",
        ]:
            raise ValueError(f"semantic_context_shape_invalid:{case_id}")

        canonical_schema = copy.deepcopy(
            openai_visible["response_format"]["json_schema"]["schema"]
        )
        canonical_schema_hash = _sha256_json(canonical_schema)
        expected_schema_hash = openai_slot["hashes"][
            "canonical_schema_hash"
        ]
        if (
            canonical_schema_hash != expected_schema_hash
            or expected_schema_hash
            != anthropic_slot["hashes"]["canonical_schema_hash"]
        ):
            raise ValueError(f"canonical_schema_hash_invalid:{case_id}")
        schema_features = _schema_features(canonical_schema)
        context_reason_codes = tuple(
            item.get("code")
            for item in semantic_context.get("unclassified_reasons", ())
        )
        if (
            context_reason_codes != EXPECTED_REASON_CODES
            or tuple(schema_features["allowed_reason_codes"])
            != EXPECTED_REASON_CODES
        ):
            raise ValueError(f"context_reason_codes_invalid:{case_id}")

        choices = semantic_context.get("choices")
        if not isinstance(choices, list):
            raise ValueError(f"context_choices_invalid:{case_id}")
        if (
            schema_features["typed_branch_present"] != bool(choices)
            or schema_features["unclassified_branch_present"] is not True
            or len(choices) != audit_case.get("expected_typed_options")
        ):
            raise ValueError(f"choice_schema_availability_invalid:{case_id}")

        source = copy.deepcopy(semantic_context["source"])
        table_rows = _flatten_source(source)
        _validate_source_against_fixture(
            table_rows=table_rows,
            fixture_case=fixture_case,
            case_id=case_id,
        )
        parity = {
            "table_rows_total": len(table_rows),
            "source_values_total": len(table_rows),
            "exact_matches_total": len(table_rows),
            "missing_total": 0,
            "duplicate_mappings_total": 0,
            "literal_mismatches_total": 0,
        }

        expected_answer = {
            "disposition": audit_case["expected_disposition"],
            "reason_code": audit_case["expected_reason_code"],
        }
        if audit_case.get("expected_input_type_id") is not None:
            expected_answer["input_type_id"] = audit_case[
                "expected_input_type_id"
            ]
        for provider_item, provider_id in zip(
            provider_material, PROVIDER_ORDER, strict=True
        ):
            terminal_case = terminal_by_slot[f"{provider_id}:{case_id}"]
            if (
                terminal_case.get("audited_expected_answer")
                != expected_answer
            ):
                raise ValueError(
                    f"goal12_expected_answer_audit_mismatch:{case_id}:"
                    f"{provider_id}"
                )
            recalculated_diff = _mechanical_diff(
                expected_answer,
                provider_item["normalized_canonical_answer"],
            )
            if recalculated_diff != terminal_case.get("mechanical_diff"):
                raise ValueError(
                    f"goal12_mechanical_diff_mismatch:{case_id}:"
                    f"{provider_id}"
                )
            provider_item["field_level_diff"] = recalculated_diff

        local_type_mapping = _local_type_mapping(
            semantic_context=semantic_context,
            semantic_pack=pack_by_id,
        )
        plausible_managed_types = list(
            audit_case.get("plausible_type_ids", ())
        )
        plausible_local_types = [
            local_type_mapping[item] for item in plausible_managed_types
        ]
        if forensic_case.get("plausible_type_ids") != plausible_managed_types:
            raise ValueError(f"goal13_plausible_types_mismatch:{case_id}")
        if (
            forensic_case.get("expected_answer_independently_revalidated")
            is not True
            or forensic_case.get("expected_answer_defect_supported") is not False
            or forensic_case.get("expected_reason_code")
            != expected_answer["reason_code"]
        ):
            raise ValueError(f"goal13_expected_revalidation_invalid:{case_id}")

        interpretation = _build_interpretation(
            case_id=case_id,
            forensic_case=forensic_case,
        )
        case_material = {
            "ordinal": ordinal,
            "case_id": case_id,
            "source": {
                "table_rows": table_rows,
                "exact_source_json": source,
                "association_visible": ASSOCIATION_FINDINGS[case_id][
                    "visibility"
                ],
                "association_basis": ASSOCIATION_FINDINGS[case_id]["basis"],
                "table_json_parity": parity,
                "exact_source_sha256": _sha256_json(source),
                "fixture_case_sha256": _sha256_json(fixture_case),
            },
            "context": {
                "exact_system_message": system_message,
                "exact_semantic_context_serialized": exact_user_content,
                "exact_semantic_context": semantic_context,
                "exact_canonical_response_schema": canonical_schema,
                "choices_count": len(choices),
                "typed_branch_present": schema_features[
                    "typed_branch_present"
                ],
                "unclassified_branch_present": schema_features[
                    "unclassified_branch_present"
                ],
                "allowed_reason_codes": list(EXPECTED_REASON_CODES),
                "provider_semantic_context_byte_identical": True,
                "hashes": {
                    "exact_system_message_utf8_sha256": _sha256_text(
                        system_message
                    ),
                    "exact_user_content_utf8_sha256": _sha256_text(
                        exact_user_content
                    ),
                    "semantic_context_canonical_sha256": _sha256_json(
                        semantic_context
                    ),
                    "canonical_schema_sha256": canonical_schema_hash,
                    "model_visible_request_sha256": openai_slot["hashes"][
                        "model_visible_request_hash"
                    ],
                },
            },
            "providers": provider_material,
            "comparison": {
                "independently_audited_expected_answer": expected_answer,
                "plausible_local_type_set": plausible_local_types,
            },
            "facts_before_interpretation": _facts_for_case(
                case_id=case_id,
                table_rows=table_rows,
                choices_count=len(choices),
                typed_branch_present=schema_features[
                    "typed_branch_present"
                ],
                plausible_local_types=plausible_local_types,
                expected_answer=expected_answer,
                providers=provider_material,
            ),
            "bounded_interpretation": interpretation,
        }
        _validate_case_material(case_material)
        cases.append(case_material)

    if len(cases) != 3:
        raise ValueError("comparative_case_count_invalid")
    return cases


def _validate_slot_binding(
    *,
    precall_slot: dict[str, Any],
    terminal_case: dict[str, Any],
    plan_slot: dict[str, Any],
    provider_id: str,
    case_id: str,
) -> None:
    provider = precall_slot.get("provider", {})
    terminal_provider = terminal_case.get("provider", {})
    if (
        precall_slot.get("case", {}).get("case_id") != case_id
        or terminal_case.get("case_id") != case_id
        or provider.get("provider_profile_id") != provider_id
        or terminal_provider.get("provider_profile_id") != provider_id
    ):
        raise ValueError(f"slot_case_provider_binding_invalid:{case_id}")
    exact_model_id = EXPECTED_MODEL_IDS[provider_id]
    if (
        precall_slot.get("model_identity", {}).get(
            "requested_model_selector"
        )
        != exact_model_id
        or terminal_provider.get("exact_model_id") != exact_model_id
    ):
        raise ValueError(f"exact_model_identity_invalid:{case_id}:{provider_id}")

    hashes = precall_slot.get("hashes", {})
    for precall_key, plan_key in (
        ("sealed_request_hash", "sealed_request_hash"),
        (
            "sealed_request_receipt_integrity_hash",
            "sealed_request_receipt_integrity_hash",
        ),
        ("model_visible_request_hash", "model_visible_request_hash"),
        ("canonical_schema_hash", "canonical_schema_hash"),
        ("prepared_request_hash", "prepared_request_hash"),
        ("provider_visible_schema_hash", "provider_visible_schema_hash"),
        ("expected_answer_hash", "expected_answer_hash"),
        ("slot_integrity_hash", "integrity_hash"),
    ):
        if hashes.get(precall_key) != plan_slot.get(plan_key):
            raise ValueError(
                f"precall_plan_hash_binding_invalid:{case_id}:{provider_id}:"
                f"{precall_key}"
            )
    if terminal_case.get("slot_integrity_hash") != hashes.get(
        "slot_integrity_hash"
    ):
        raise ValueError(
            f"terminal_slot_integrity_binding_invalid:{case_id}:{provider_id}"
        )
    _validate_embedded_integrity(terminal_case, "integrity_hash")

    prepared = precall_slot.get("exact_final_prepared_request", {})
    if (
        prepared.get("form_data")
        != terminal_case.get("exact_synthetic_final_provider_request")
        or precall_slot.get("exact_provider_visible_schema")
        != terminal_case.get("exact_provider_visible_response_schema")
        or prepared.get("provider_visible_schema")
        != precall_slot.get("exact_provider_visible_schema")
        or _sha256_json(prepared) != hashes.get("prepared_request_hash")
        or _sha256_json(prepared.get("provider_visible_schema"))
        != hashes.get("provider_visible_schema_hash")
        or _sha256_json(terminal_case.get("audited_expected_answer"))
        != hashes.get("expected_answer_hash")
    ):
        raise ValueError(
            f"precall_terminal_exact_material_mismatch:{case_id}:{provider_id}"
        )

    model_visible = precall_slot.get("exact_model_visible_request", {})
    messages = model_visible.get("messages", ())
    if (
        len(messages) != 2
        or messages[0].get("content")
        != terminal_case.get("exact_system_message")
        or messages[1].get("content")
        != terminal_case.get("exact_user_content")
    ):
        raise ValueError(
            f"precall_terminal_context_mismatch:{case_id}:{provider_id}"
        )


def _build_provider_material(
    *,
    precall_slot: dict[str, Any],
    terminal_case: dict[str, Any],
    provider_id: str,
) -> dict[str, Any]:
    prepared = precall_slot["exact_final_prepared_request"]
    form_data = prepared["form_data"]
    provider = precall_slot["provider"]
    model_visible = precall_slot["exact_model_visible_request"]
    system_message = model_visible["messages"][0]["content"]
    user_content = model_visible["messages"][1]["content"]
    canonical_schema = model_visible["response_format"]["json_schema"]["schema"]
    provider_schema = prepared["provider_visible_schema"]

    if provider_id == "openai_gpt":
        expected_keys = {
            "max_completion_tokens",
            "messages",
            "model",
            "response_format",
            "stream",
        }
        if set(form_data) != expected_keys:
            raise ValueError("openai_wrapper_fields_invalid")
        if (
            form_data["messages"]
            != [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_content},
            ]
            or form_data["response_format"]["json_schema"]["schema"]
            != provider_schema
            or provider_schema.get("properties", {}).get(
                "broker_reports_gate2_choice"
            )
            != canonical_schema
            or prepared.get("schema_transform_count") != 1
            or form_data.get("max_completion_tokens") != 640
            or form_data.get("stream") is not False
        ):
            raise ValueError("openai_wrapper_binding_invalid")
        wrapper_delta = {
            "top_level_fields": list(form_data),
            "provider_request_wrapper": "openai_response_format",
            "system_message_location": "messages[0].content",
            "user_content_location": "messages[1].content",
            "token_limit": {
                "field": "max_completion_tokens",
                "value": 640,
            },
            "provider_visible_schema_location": (
                "response_format.json_schema.schema"
            ),
            "provider_visible_schema_wrapper": {
                "type": form_data["response_format"]["type"],
                "name": form_data["response_format"]["json_schema"]["name"],
                "strict": form_data["response_format"]["json_schema"][
                    "strict"
                ],
                "canonical_schema_nested_under": (
                    "properties.broker_reports_gate2_choice"
                ),
            },
            "exact_provider_visible_schema": copy.deepcopy(provider_schema),
            "schema_transformation_count": 1,
            "stream_field": {"present": True, "value": False},
        }
    elif provider_id == "anthropic_claude":
        expected_keys = {
            "max_tokens",
            "messages",
            "model",
            "output_config",
            "system",
        }
        if set(form_data) != expected_keys:
            raise ValueError("anthropic_wrapper_fields_invalid")
        if (
            form_data["system"] != system_message
            or form_data["messages"]
            != [{"role": "user", "content": user_content}]
            or form_data["output_config"]["format"]["schema"]
            != provider_schema
            or provider_schema != canonical_schema
            or prepared.get("schema_transform_count") != 0
            or form_data.get("max_tokens") != 640
        ):
            raise ValueError("anthropic_wrapper_binding_invalid")
        wrapper_delta = {
            "top_level_fields": list(form_data),
            "provider_request_wrapper": "anthropic_native_messages",
            "system_message_location": "system",
            "user_content_location": "messages[0].content",
            "token_limit": {"field": "max_tokens", "value": 640},
            "provider_visible_schema_location": (
                "output_config.format.schema"
            ),
            "provider_visible_schema_wrapper": {
                "type": form_data["output_config"]["format"]["type"],
                "canonical_schema_nested_under": None,
            },
            "exact_provider_visible_schema": copy.deepcopy(provider_schema),
            "schema_transformation_count": 0,
            "stream_field": {"present": False},
        }
    else:
        raise ValueError(f"unexpected_provider:{provider_id}")

    exact_output = copy.deepcopy(
        terminal_case["exact_adapter_extracted_output"]
    )
    if provider_id == "openai_gpt":
        if not isinstance(exact_output, dict):
            raise ValueError("nano_exact_output_storage_type_invalid")
        exact_output_hash = _sha256_json(exact_output)
        hash_basis = "canonical_json_value"
        parsed_output = exact_output
        storage_type = "object"
    else:
        if not isinstance(exact_output, str):
            raise ValueError("haiku_exact_output_storage_type_invalid")
        exact_output_hash = _sha256_text(exact_output)
        hash_basis = "exact_utf8_string"
        parsed_output = json.loads(exact_output)
        storage_type = "string"
    if not isinstance(parsed_output, dict):
        raise ValueError(f"adapter_output_shape_invalid:{provider_id}")
    normalized = _normalize_adapter_output(parsed_output)
    if normalized != terminal_case.get("normalized_canonical_answer"):
        raise ValueError(f"normalized_output_mismatch:{provider_id}")

    return {
        "provider_profile_id": provider_id,
        "provider_id": provider["provider_id"],
        "model_label": MODEL_LABELS[provider_id],
        "exact_model_id": EXPECTED_MODEL_IDS[provider_id],
        "adapter": {
            "id": provider["provider_adapter_id"],
            "version": provider["provider_adapter_version"],
        },
        "wrapper_delta": wrapper_delta,
        "exact_adapter_output": {
            "storage_type": storage_type,
            "value": exact_output,
            "exact_output_sha256": exact_output_hash,
            "hash_basis": hash_basis,
        },
        "normalized_canonical_answer": normalized,
    }


def _schema_features(schema: dict[str, Any]) -> dict[str, Any]:
    branches = schema.get("anyOf")
    if not isinstance(branches, list) or not branches:
        raise ValueError("canonical_schema_any_of_invalid")
    typed_branches = []
    unclassified_branches = []
    for branch in branches:
        properties = branch.get("properties", {})
        choice = properties.get("choice", {})
        if choice.get("enum") == ["unclassified"]:
            unclassified_branches.append(branch)
        else:
            typed_branches.append(branch)
    if len(unclassified_branches) != 1 or len(typed_branches) > 1:
        raise ValueError("canonical_schema_branch_count_invalid")
    reason_codes = (
        unclassified_branches[0]
        .get("properties", {})
        .get("reason", {})
        .get("enum")
    )
    if not isinstance(reason_codes, list):
        raise ValueError("canonical_schema_reason_enum_invalid")
    return {
        "typed_branch_present": bool(typed_branches),
        "unclassified_branch_present": True,
        "allowed_reason_codes": reason_codes,
    }


def _flatten_source(source: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if "values" in node:
                values = node["values"]
                if not isinstance(values, list):
                    raise ValueError("source_values_not_list")
                for value in values:
                    if (
                        not isinstance(value, dict)
                        or list(value) != ["meaning", "literal"]
                        or not isinstance(value.get("meaning"), str)
                        or not isinstance(value.get("literal"), str)
                    ):
                        raise ValueError("source_value_shape_invalid")
                    meaning = value["meaning"]
                    literal = value["literal"]
                    if any(mark in meaning or mark in literal for mark in ("\n", "\r", "|")):
                        raise ValueError("source_value_not_markdown_table_safe")
                    rows.append(
                        {"meaning": meaning, "literal": literal}
                    )
            children = node.get("children")
            if children is not None:
                if not isinstance(children, list):
                    raise ValueError("source_children_not_list")
                for child in children:
                    visit(child)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(source)
    if not rows:
        raise ValueError("source_contains_no_values")
    return rows


def _validate_source_against_fixture(
    *,
    table_rows: list[dict[str, str]],
    fixture_case: dict[str, Any],
    case_id: str,
) -> None:
    fixture_pairs = Counter(
        (
            item["header"].replace("_", " "),
            item["literal"],
        )
        for item in fixture_case.get("cells", ())
    )
    projected_pairs = Counter(
        (item["meaning"], item["literal"]) for item in table_rows
    )
    if fixture_pairs != projected_pairs:
        raise ValueError(f"source_fixture_exact_value_mismatch:{case_id}")


def _local_type_mapping(
    *,
    semantic_context: dict[str, Any],
    semantic_pack: dict[str, dict[str, Any]],
) -> dict[str, str]:
    cards = semantic_context.get("type_cards")
    if not isinstance(cards, list):
        raise ValueError("context_type_cards_invalid")
    cards_by_title = _unique_by(cards, "title", "context_type_cards")
    mapping: dict[str, str] = {}
    for input_type_id, pack_type in semantic_pack.items():
        title = pack_type.get("title")
        card = cards_by_title.get(title)
        if card is not None:
            if card.get("definition") != pack_type.get("definition"):
                raise ValueError(
                    f"type_card_pack_definition_drift:{input_type_id}"
                )
            mapping[input_type_id] = card["type_key"]
    if set(mapping) != {
        "cash_balance_snapshot_v1",
        "printed_financial_metric_v1",
    }:
        raise ValueError("managed_to_local_type_mapping_incomplete")
    return mapping


def _normalize_adapter_output(output: dict[str, Any]) -> dict[str, Any]:
    if output.get("choice") != "unclassified" or set(output) != {
        "choice",
        "reason",
    }:
        raise ValueError("comparative_output_not_unclassified")
    reason = output.get("reason")
    if reason not in EXPECTED_REASON_CODES:
        raise ValueError("comparative_output_reason_invalid")
    return {
        "disposition": "unclassified_financial_input",
        "reason_code": reason,
    }


def _mechanical_diff(
    expected: dict[str, Any], actual: dict[str, Any]
) -> dict[str, Any]:
    fields: list[dict[str, Any]] = []
    ordered_fields = list(expected)
    ordered_fields.extend(key for key in actual if key not in expected)
    for field in ordered_fields:
        expected_present = field in expected
        actual_present = field in actual
        expected_value = expected.get(field)
        actual_value = actual.get(field)
        fields.append(
            {
                "field": field,
                "expected_present": expected_present,
                "expected_value": expected_value,
                "actual_present": actual_present,
                "actual_value": actual_value,
                "exact_match": (
                    expected_present
                    and actual_present
                    and expected_value == actual_value
                ),
            }
        )
    return {
        "all_fields_match": all(item["exact_match"] for item in fields),
        "fields": fields,
    }


def _build_interpretation(
    *, case_id: str, forensic_case: dict[str, Any]
) -> list[dict[str, Any]]:
    historical = forensic_case.get("layer_evidence_strength", {})
    mapping = (
        ("source_projection", "source_projection"),
        ("type_glossary", "type_glossary"),
        ("choices_presentation", "choices_presentation"),
        ("reason_contract", "reason_contract_error_locus"),
        ("model_capability", "model_capability"),
    )
    rows = []
    for layer, historical_key in mapping:
        strength = historical.get(historical_key)
        if strength not in {"proven", "supported", "hypothesis"}:
            raise ValueError(
                f"goal13_layer_strength_invalid:{case_id}:{layer}"
            )
        rows.append(
            {
                "layer": layer,
                "evidence_strength": strength,
                "bounded_finding": INTERPRETATION_NOTES[case_id][layer],
            }
        )
    if historical.get("expected_answer_defect") != "hypothesis":
        raise ValueError(
            f"goal13_expected_defect_strength_invalid:{case_id}"
        )
    rows.append(
        {
            "layer": "expected_answer_defect",
            "evidence_strength": "not supported",
            "historical_exploratory_label": "hypothesis",
            "bounded_finding": INTERPRETATION_NOTES[case_id][
                "expected_answer_defect"
            ],
        }
    )
    return rows


def _facts_for_case(
    *,
    case_id: str,
    table_rows: list[dict[str, str]],
    choices_count: int,
    typed_branch_present: bool,
    plausible_local_types: list[str],
    expected_answer: dict[str, Any],
    providers: list[dict[str, Any]],
) -> list[str]:
    nano_reason = providers[0]["normalized_canonical_answer"]["reason_code"]
    haiku_reason = providers[1]["normalized_canonical_answer"]["reason_code"]
    expected_reason = expected_answer["reason_code"]
    common = [
        f"The exact source contains {len(table_rows)} values in one row.",
        (
            "The exact visible source literals, in model order, are "
            f"{_compact_json([item['literal'] for item in table_rows])}."
        ),
        (
            f"Association visibility is "
            f"{ASSOCIATION_FINDINGS[case_id]['visibility']}: "
            f"{ASSOCIATION_FINDINGS[case_id]['basis']}"
        ),
        f"The exact choices array contains {choices_count} entries.",
        (
            "The canonical schema contains a typed branch."
            if typed_branch_present
            else "The canonical schema contains no typed branch."
        ),
        "The canonical schema contains the unclassified branch.",
        "Both exact outputs contain choice=unclassified.",
        (
            "The independently audited plausible local type set is "
            f"{_inline_list(plausible_local_types)}."
        ),
        (
            "The independently audited plausible type count is "
            f"{len(plausible_local_types)}."
        ),
        (
            "The independently audited expected canonical answer is "
            f"{_compact_json(expected_answer)}."
        ),
        (
            f"The exact expected reason is {expected_reason}; Nano returned "
            f"{nano_reason}; Haiku returned {haiku_reason}."
        ),
    ]
    return common


def _validate_case_material(case: dict[str, Any]) -> None:
    source = case["source"]
    rebuilt_rows = _flatten_source(source["exact_source_json"])
    if rebuilt_rows != source["table_rows"]:
        raise ValueError(f"table_json_parity_invalid:{case['case_id']}")
    parity = source["table_json_parity"]
    if parity != {
        "table_rows_total": len(rebuilt_rows),
        "source_values_total": len(rebuilt_rows),
        "exact_matches_total": len(rebuilt_rows),
        "missing_total": 0,
        "duplicate_mappings_total": 0,
        "literal_mismatches_total": 0,
    }:
        raise ValueError(f"table_json_counters_invalid:{case['case_id']}")
    forbidden_fact_terms = (
        "likely",
        "probably",
        "model understood",
        "model was confused",
    )
    facts_text = "\n".join(case["facts_before_interpretation"]).lower()
    if any(term in facts_text for term in forbidden_fact_terms):
        raise ValueError(f"facts_language_invalid:{case['case_id']}")
    if case["context"]["choices_count"] == 0 and case["context"][
        "typed_branch_present"
    ]:
        raise ValueError(f"zero_choice_typed_branch_invalid:{case['case_id']}")
    if {
        item["evidence_strength"]
        for item in case["bounded_interpretation"]
    } - {"proven", "supported", "hypothesis", "not supported"}:
        raise ValueError(
            f"interpretation_strength_vocabulary_invalid:{case['case_id']}"
        )


def _sum_parity(cases: list[dict[str, Any]]) -> dict[str, int]:
    keys = (
        "table_rows_total",
        "source_values_total",
        "exact_matches_total",
        "missing_total",
        "duplicate_mappings_total",
        "literal_mismatches_total",
    )
    return {
        key: sum(
            case["source"]["table_json_parity"][key] for case in cases
        )
        for key in keys
    }


def _render_report(cases: list[dict[str, Any]]) -> str:
    lines = [
        "# Broker Reports Gate 2 Context V2.1 evidence-first comparative review",
        "",
        "Status: completed offline analytical review for exactly three synthetic "
        "cases.",
        "",
        "This report mechanically rebuilds primary facts from immutable GOAL 12 "
        "requests and outputs, then applies the bounded GOAL 13 classifications. "
        "It makes no Prompt, Context, Semantic Pack, Choice, source-projection, "
        "expected-answer, runtime or product change. Provider calls, retries, "
        "repairs and fallbacks are `0/0/0/0`. No final refactor is selected.",
        "",
        "Association rubric: `yes` means the exact row/value structure uniquely "
        "identifies the relevant role associations; `partial` means row grouping "
        "is visible but at least one relevant pairwise association is absent; "
        "`no` means neither is visible.",
        "",
    ]
    for case in cases:
        lines.extend(_render_case(case))
    lines.extend(
        [
            "## Review boundary",
            "",
            "The comparison proves exact inputs, outputs, expected answers, "
            "mechanical differences and bounded evidence strengths. It does not "
            "prove a causal root, qualify either model, authorize activation or "
            "select a corrective implementation.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_case(case: dict[str, Any]) -> list[str]:
    case_id = case["case_id"]
    source = case["source"]
    context = case["context"]
    providers = case["providers"]
    expected = case["comparison"]["independently_audited_expected_answer"]
    nano = providers[0]
    haiku = providers[1]
    lines = [
        f"## Case {case['ordinal']} — `{case_id}`",
        "",
        "### A — Original source as a table",
        "",
        "| Source field | Exact literal |",
        "| --- | --- |",
    ]
    lines.extend(
        f"| `{row['meaning']}` | `{row['literal']}` |"
        for row in source["table_rows"]
    )
    parity = source["table_json_parity"]
    lines.extend(
        [
            "",
            f"`association visible: {source['association_visible']}` — "
            f"{source['association_basis']}",
            "",
            "Mechanical parity: "
            f"rows `{parity['table_rows_total']}`; source values "
            f"`{parity['source_values_total']}`; exact matches "
            f"`{parity['exact_matches_total']}`; missing "
            f"`{parity['missing_total']}`; duplicate mappings "
            f"`{parity['duplicate_mappings_total']}`; literal mismatches "
            f"`{parity['literal_mismatches_total']}`.",
            "",
            "### B — Exact source JSON",
            "",
            "The block is the pretty-printed exact parsed `source` value; no "
            "field or literal is normalized.",
            "",
            "```json",
            _pretty_json(source["exact_source_json"]).rstrip(),
            "```",
            "",
            "### C — Exact model task and context",
            "",
            "Exact system message:",
            "",
            "```text",
            context["exact_system_message"],
            "```",
            "",
            "Exact user semantic context (pretty-printed parsed value; the "
            "transparent artifact also preserves the exact compact serialized "
            "bytes):",
            "",
            "```json",
            _pretty_json(context["exact_semantic_context"]).rstrip(),
            "```",
            "",
            "Exact canonical response schema:",
            "",
            "```json",
            _pretty_json(
                context["exact_canonical_response_schema"]
            ).rstrip(),
            "```",
            "",
            "| Property | Exact value |",
            "| --- | --- |",
            f"| `choices` count | `{context['choices_count']}` |",
            "| typed response branch present | "
            f"`{_yes_no(context['typed_branch_present'])}` |",
            "| unclassified branch present | "
            f"`{_yes_no(context['unclassified_branch_present'])}` |",
            "| allowed reason codes | "
            f"`{_compact_json(context['allowed_reason_codes'])}` |",
            "",
        ]
    )
    if context["choices_count"] == 0:
        lines.extend(
            [
                "> **Typed output was unavailable:** `choices=[]`, and the "
                "canonical schema permits only the unclassified branch.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "> Typed output was available: the exact choices and both typed "
                "and unclassified schema branches were visible.",
                "",
            ]
        )

    openai_delta = nano["wrapper_delta"]
    anthropic_delta = haiku["wrapper_delta"]
    lines.extend(
        [
            "### D — Provider differences",
            "",
            "The system message, complete user semantic context and canonical "
            "response schema are byte/structurally identical across providers. "
            "Exact user-content UTF-8 SHA-256: "
            f"`{context['hashes']['exact_user_content_utf8_sha256']}`. "
            "Sealed model-visible request SHA-256: "
            f"`{context['hashes']['model_visible_request_sha256']}`.",
            "",
            "| Wrapper fact | OpenAI Nano | Anthropic Haiku |",
            "| --- | --- | --- |",
            "| top-level fields | "
            f"`{_compact_json(openai_delta['top_level_fields'])}` | "
            f"`{_compact_json(anthropic_delta['top_level_fields'])}` |",
            "| model | "
            f"`{nano['exact_model_id']}` | `{haiku['exact_model_id']}` |",
            "| provider request wrapper | "
            f"`{openai_delta['provider_request_wrapper']}` | "
            f"`{anthropic_delta['provider_request_wrapper']}` |",
            "| system location | "
            f"`{openai_delta['system_message_location']}` | "
            f"`{anthropic_delta['system_message_location']}` |",
            "| user location | "
            f"`{openai_delta['user_content_location']}` | "
            f"`{anthropic_delta['user_content_location']}` |",
            "| token cap | "
            f"`{openai_delta['token_limit']['field']}=640` | "
            f"`{anthropic_delta['token_limit']['field']}=640` |",
            "| schema location | "
            f"`{openai_delta['provider_visible_schema_location']}` | "
            f"`{anthropic_delta['provider_visible_schema_location']}` |",
            "| provider-visible schema shape | canonical schema under "
            "`properties.broker_reports_gate2_choice` | direct canonical "
            "schema |",
            "| schema metadata | `name=broker_reports_gate2_choice`, "
            "`strict=true` | absent |",
            "| schema transformation count | "
            f"`{openai_delta['schema_transformation_count']}` | "
            f"`{anthropic_delta['schema_transformation_count']}` |",
            "| stream field | `stream=false` | absent |",
            "",
            "No other semantic-context field delta exists in the stored exact "
            "requests.",
            "",
            "### E — Exact model outputs",
            "",
            "| Model | Stored adapter value type | Exact adapter-extracted value |",
            "| --- | --- | --- |",
            f"| Nano | `{nano['exact_adapter_output']['storage_type']}` | "
            f"`{_exact_output_text(nano)}` |",
            f"| Haiku | `{haiku['exact_adapter_output']['storage_type']}` | "
            f"`{_exact_output_text(haiku)}` |",
            "",
            "### F — Expected answer and mechanical diff",
            "",
            "| Field | Expected | Nano | Haiku |",
            "| --- | --- | --- | --- |",
        ]
    )
    field_order = list(expected)
    field_order.extend(
        key
        for provider in providers
        for key in provider["normalized_canonical_answer"]
        if key not in field_order
    )
    for field in field_order:
        lines.append(
            f"| `{field}` | `{_display_value(expected.get(field))}` | "
            f"`{_display_value(nano['normalized_canonical_answer'].get(field))}` "
            f"| `{_display_value(haiku['normalized_canonical_answer'].get(field))}` |"
        )
    lines.extend(
        [
            "",
            "Independently audited plausible local type set: "
            f"`{_inline_list(case['comparison']['plausible_local_type_set'])}`.",
            "",
            f"- Nano field-level diff: {_render_diff(nano['field_level_diff'])}",
            f"- Haiku field-level diff: {_render_diff(haiku['field_level_diff'])}",
            "",
            "### G — Facts before interpretation",
            "",
        ]
    )
    lines.extend(f"- {fact}" for fact in case["facts_before_interpretation"])
    lines.extend(
        [
            "",
            "### H — Bounded interpretation",
            "",
            "| Layer | Evidence strength | Bounded finding |",
            "| --- | --- | --- |",
        ]
    )
    lines.extend(
        f"| `{item['layer']}` | `{item['evidence_strength']}` | "
        f"{item['bounded_finding']} |"
        for item in case["bounded_interpretation"]
    )
    lines.extend(
        [
            "",
            "No row above establishes a causal root.",
            "",
        ]
    )
    return lines


def write_or_check_outputs(
    *, outputs: dict[Path, bytes], check: bool
) -> None:
    for path, expected in outputs.items():
        if check:
            actual = path.read_bytes() if path.is_file() else None
            if actual != expected:
                raise SystemExit(
                    f"context_v2_1_comparative_evidence_drift:{path.name}"
                )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)


def _validate_source_authorities() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for identity, path, expected_hash in SOURCE_AUTHORITIES:
        if not path.is_file():
            raise ValueError(f"source_authority_missing:{identity}")
        actual_hash = _sha256_bytes(
            _repository_lf_bytes(path.read_bytes())
        )
        if actual_hash != expected_hash:
            raise ValueError(
                f"source_authority_repository_lf_hash_drift:{identity}"
            )
        hashes[identity] = actual_hash
    return hashes


def _repository_lf_bytes(value: bytes) -> bytes:
    without_crlf = value.replace(b"\r\n", b"")
    if b"\r" in without_crlf:
        raise ValueError("source_authority_lone_carriage_return")
    return value.replace(b"\r\n", b"\n")


def _validate_embedded_integrity(
    value: dict[str, Any], field: str
) -> None:
    material = copy.deepcopy(value)
    supplied = material.pop(field, None)
    if not isinstance(supplied, str) or supplied != _sha256_json(material):
        raise ValueError(f"embedded_integrity_invalid:{field}")


def _validate_repository_safe_output(value: dict[str, Any]) -> None:
    keys = _recursive_keys(value)
    forbidden = keys.intersection(_FORBIDDEN_OUTPUT_KEYS)
    if forbidden:
        raise ValueError(
            "repository_safe_output_forbidden_keys:"
            + ",".join(sorted(forbidden))
        )
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if _LOCAL_PATH_RE.search(rendered):
        raise ValueError("repository_safe_output_local_path_detected")
    for forbidden_text in (
        "Bearer ",
        "api.openai.com",
        "api.anthropic.com",
        "raw provider envelope",
    ):
        if forbidden_text.lower() in rendered.lower():
            raise ValueError(
                "repository_safe_output_forbidden_text:"
                + forbidden_text
            )


def _recursive_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key).lower())
            keys.update(_recursive_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_recursive_keys(item))
    return keys


def _with_integrity(material: dict[str, Any]) -> dict[str, Any]:
    return {
        **copy.deepcopy(material),
        "integrity_sha256": _sha256_json(material),
    }


def _unique_by(
    values: Any, key: str, label: str
) -> dict[str, dict[str, Any]]:
    if not isinstance(values, list):
        raise ValueError(f"{label}_not_list")
    result: dict[str, dict[str, Any]] = {}
    for item in values:
        if not isinstance(item, dict) or not isinstance(item.get(key), str):
            raise ValueError(f"{label}_item_invalid")
        item_key = item[key]
        if item_key in result:
            raise ValueError(f"{label}_duplicate:{item_key}")
        result[item_key] = item
    return result


def _required(
    values: dict[str, dict[str, Any]], key: str, label: str
) -> dict[str, Any]:
    try:
        return values[key]
    except KeyError as error:
        raise ValueError(f"{label}_missing:{key}") from error


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_root_not_object:{path.name}")
    return value


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _pretty_json(value: Any) -> str:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
            allow_nan=False,
        )
        + "\n"
    )


def _compact_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_json(value: Any) -> str:
    return _sha256_text(_compact_json(value))


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _inline_list(values: list[str]) -> str:
    return "[" + ", ".join(values) + "]"


def _display_value(value: Any) -> str:
    if value is None:
        return "absent"
    if isinstance(value, str):
        return value
    return _compact_json(value)


def _exact_output_text(provider: dict[str, Any]) -> str:
    output = provider["exact_adapter_output"]
    if output["storage_type"] == "string":
        return output["value"]
    return _compact_json(output["value"])


def _render_diff(diff: dict[str, Any]) -> str:
    mismatches = [
        item for item in diff["fields"] if item["exact_match"] is not True
    ]
    if not mismatches:
        return "`none`."
    return "; ".join(
        f"`$.{item['field']}` expected "
        f"`{_display_value(item['expected_value'])}`, actual "
        f"`{_display_value(item['actual_value'])}`"
        for item in mismatches
    ) + "."


if __name__ == "__main__":
    raise SystemExit(main())
