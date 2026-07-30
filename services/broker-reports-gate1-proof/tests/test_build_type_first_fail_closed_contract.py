from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
BUILD_SCRIPT = (
    SERVICE_ROOT / "scripts" / "build_type_first_fail_closed_contract.py"
)

EXACT_BASE_COMMIT = "7ef38c2bba12e6773f2ded8542c256d603ca5aff"
EXACT_FIELD_ORDER = ["task", "source", "type_cards"]
EXACT_TASK = (
    "Return every type_key from type_cards whose financial meaning remains "
    "plausible for the visible source. Return all plausible types, not only "
    "the best one. Judge type plausibility independently of whether code can "
    "construct a complete record. Preserve type_cards order."
)
EXACT_TASK_SHA256 = (
    "2dc44b6475e1bd1c753cc1ba91074fd4d1da2f0c660abb4446371aa437a80c68"
)
EXACT_SCHEMA_SHA256 = (
    "8897f4fc91b0dd52e92e366d5f36f24a8af37a8ae7edaab2cb8a9c79bd245b3a"
)
EXACT_IDENTITIES = {
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
EXACT_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "plausible_types": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["type_1", "type_2"],
            },
            "minItems": 0,
            "maxItems": 2,
            "uniqueItems": True,
        }
    },
    "required": ["plausible_types"],
}

RESPONSE_NEGATIVE_FIXTURE_IDS = [
    "malformed_json",
    "missing_plausible_types",
    "plausible_types_null",
    "plausible_types_not_array",
    "unknown_type_key",
    "duplicate_type_key",
    "out_of_order_type_keys",
    "extra_response_field",
    "backend_type_id_forbidden",
]
CONTRACT_INTEGRITY_NEGATIVE_FIXTURE_IDS = [
    "mapping_receipt_mismatch",
    "context_profile_schema_hash_mismatch",
    "pack_projection_drift",
    "evidence_bundle_scope_mismatch",
    "candidate_compilation_scope_mismatch",
]
BACKEND_RESTORATION_NEGATIVE_FIXTURE_IDS = [
    "missing_exact_code_owned_typed_option",
    "mismatched_exact_code_owned_typed_option",
]
QUALIFICATION_COUNTERS = [
    "plausible_type_set_exact_total",
    "false_empty_total",
    "false_singleton_total",
    "false_superset_total",
    "wrong_singleton_type_total",
    "false_singleton_typed_total",
    "unsafe_typed_total",
    "safe_under_typing_total",
    "invalid_response_total",
]
HARD_QUALIFICATION_GATES = {
    "unsafe_typed_total": 0,
    "false_singleton_typed_total": 0,
    "wrong_singleton_type_total": 0,
    "invalid_response_total": 0,
}
EXACT_MARKDOWN_HEADINGS = [
    "## 1. Purpose",
    "## 2. Semantic responsibility boundary",
    "## 3. Exact model-visible context",
    "## 4. Exact response schema",
    "## 5. Private mapping",
    "## 6. Deterministic decision table",
    "## 7. Technical failures",
    "## 8. False singleton risk",
    "## 9. Retention and ownership",
    "## 10. Qualification counters and hard gates",
    "## 11. Ten-case matrix",
    "## 12. Authority map",
    "## 13. Byte budget",
    "## 14. Variant C reservation",
    "## 15. Activation boundary",
]

OUTPUT_STEM = "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED_CONTRACT_GOAL16"
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

CASE_ORDER = [
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
]
EXPECTED_CASE_MATRIX = {
    "syn_successor_v2_unique_cash": {
        "plausible_local_types": ["type_1"],
        "plausible_canonical_types": ["cash_balance_snapshot_v1"],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "route": "singleton_type_one_complete_option",
        "expected_disposition": "typed_input",
        "typed_option_identity": (
            "financial-typed-option:ddcf7fde28240dc392c4f143abb40d3f"
        ),
        "unclassified_reason": None,
        "source_retention_expectation": (
            "existing_typed_evidence_path_unchanged"
        ),
    },
    "syn_successor_v2_unique_printed_total": {
        "plausible_local_types": ["type_2"],
        "plausible_canonical_types": ["printed_financial_metric_v1"],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "route": "singleton_type_one_complete_option",
        "expected_disposition": "typed_input",
        "typed_option_identity": (
            "financial-typed-option:9c6b9a796d36dc2cde5b073c9d397622"
        ),
        "unclassified_reason": None,
        "source_retention_expectation": (
            "existing_typed_evidence_path_unchanged"
        ),
    },
    "syn_successor_v2_multiple_compatible": {
        "plausible_local_types": ["type_1", "type_2"],
        "plausible_canonical_types": [
            "cash_balance_snapshot_v1",
            "printed_financial_metric_v1",
        ],
        "complete_option_counts_by_type": {"type_1": 0, "type_2": 0},
        "route": "multiple_plausible_types",
        "expected_disposition": "unclassified_financial_input",
        "typed_option_identity": None,
        "unclassified_reason": "ambiguous_registry_type",
        "source_retention_expectation": "full_evidence_bundle_retained",
    },
    "syn_successor_v2_no_registry_type": {
        "plausible_local_types": [],
        "plausible_canonical_types": [],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "route": "zero_plausible_types",
        "expected_disposition": "unclassified_financial_input",
        "typed_option_identity": None,
        "unclassified_reason": "no_registry_type",
        "source_retention_expectation": "full_evidence_bundle_retained",
    },
    "syn_successor_v2_missing_discriminator": {
        "plausible_local_types": ["type_1", "type_2"],
        "plausible_canonical_types": [
            "cash_balance_snapshot_v1",
            "printed_financial_metric_v1",
        ],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "route": "multiple_plausible_types",
        "expected_disposition": "unclassified_financial_input",
        "typed_option_identity": None,
        "unclassified_reason": "ambiguous_registry_type",
        "source_retention_expectation": "full_evidence_bundle_retained",
    },
    "syn_successor_v2_detail_vs_subtotal": {
        "plausible_local_types": ["type_2"],
        "plausible_canonical_types": ["printed_financial_metric_v1"],
        "complete_option_counts_by_type": {"type_1": 0, "type_2": 0},
        "route": "singleton_type_no_safe_record",
        "expected_disposition": "unclassified_financial_input",
        "typed_option_identity": None,
        "unclassified_reason": "single_registry_type_no_safe_record",
        "source_retention_expectation": "full_evidence_bundle_retained",
    },
    "syn_successor_v2_adjacent_equal": {
        "plausible_local_types": ["type_1"],
        "plausible_canonical_types": ["cash_balance_snapshot_v1"],
        "complete_option_counts_by_type": {"type_1": 0, "type_2": 0},
        "route": "singleton_type_no_safe_record",
        "expected_disposition": "unclassified_financial_input",
        "typed_option_identity": None,
        "unclassified_reason": "single_registry_type_no_safe_record",
        "source_retention_expectation": "full_evidence_bundle_retained",
    },
    "syn_successor_v2_adjacent_fx": {
        "plausible_local_types": ["type_1"],
        "plausible_canonical_types": ["cash_balance_snapshot_v1"],
        "complete_option_counts_by_type": {"type_1": 0, "type_2": 0},
        "route": "singleton_type_no_safe_record",
        "expected_disposition": "unclassified_financial_input",
        "typed_option_identity": None,
        "unclassified_reason": "single_registry_type_no_safe_record",
        "source_retention_expectation": "full_evidence_bundle_retained",
    },
    "syn_successor_v2_optional_missing": {
        "plausible_local_types": ["type_1"],
        "plausible_canonical_types": ["cash_balance_snapshot_v1"],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "route": "singleton_type_one_complete_option",
        "expected_disposition": "typed_input",
        "typed_option_identity": (
            "financial-typed-option:2913ae6d06a3bc248adabfd7ff9ed411"
        ),
        "unclassified_reason": None,
        "source_retention_expectation": (
            "existing_typed_evidence_path_unchanged"
        ),
    },
    "syn_successor_v2_forbidden_neighbour": {
        "plausible_local_types": ["type_1"],
        "plausible_canonical_types": ["cash_balance_snapshot_v1"],
        "complete_option_counts_by_type": {"type_1": 1, "type_2": 1},
        "route": "singleton_type_one_complete_option",
        "expected_disposition": "typed_input",
        "typed_option_identity": (
            "financial-typed-option:73ec7a290138fbd81b6bdc7f61d739ec"
        ),
        "unclassified_reason": None,
        "source_retention_expectation": (
            "existing_typed_evidence_path_unchanged"
        ),
    },
}


def _load_builder():
    name = "build_type_first_fail_closed_contract_under_test"
    spec = importlib.util.spec_from_file_location(name, BUILD_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BUILDER = _load_builder()


@pytest.fixture(scope="module")
def built_artifacts():
    return BUILDER.build_artifacts()


def test_exact_identities_model_view_and_inactive_boundary(
    built_artifacts,
) -> None:
    _contract_md, machine, _report, receipt = built_artifacts

    assert list(BUILDER.FIELD_ORDER) == EXACT_FIELD_ORDER
    assert BUILDER.EXACT_TASK == EXACT_TASK
    assert BUILDER.CONTRACT_IDENTITIES == EXACT_IDENTITIES
    assert BUILDER.RESPONSE_SCHEMA == EXACT_RESPONSE_SCHEMA

    assert machine["contract_identities"] == EXACT_IDENTITIES
    model_view = machine["model_visible_contract"]
    assert model_view["field_order"] == EXACT_FIELD_ORDER
    assert model_view["exact_task"] == EXACT_TASK
    assert model_view["local_type_key_order"] == ["type_1", "type_2"]
    assert model_view["root_fields_total"] == 3
    assert set(model_view["excluded_fields"]) >= {
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
    }

    exact_status = {
        "active": False,
        "transport_eligible": False,
        "runtime_activation": False,
        "provider_calls_total": 0,
        "fallback_allowed": False,
        "repair_allowed": False,
        "retry_allowed": False,
    }
    assert machine["status"] == exact_status
    assert receipt["contract_identity"] == EXACT_IDENTITIES["contract_identity"]
    assert receipt["contract_version"] == "v1"


def test_canonical_markdown_has_exact_normative_surface(
    built_artifacts,
) -> None:
    contract_md, _machine, _report, _receipt = built_artifacts
    headings = [
        line for line in contract_md.splitlines() if line.startswith("## ")
    ]
    assert headings == EXACT_MARKDOWN_HEADINGS

    for identity in EXACT_IDENTITIES.values():
        assert f"`{identity}`" in contract_md
    for clause in (
        "`active = false`",
        "`transport_eligible = false`",
        "`runtime_activation = false`",
        "`provider_calls_total = 0`",
        "`fallback_allowed = false`",
        "`repair_allowed = false`",
        "`retry_allowed = false`",
        "every governed source literal is retained exactly",
        "the real hierarchy is retained",
        "no association is invented",
        "Only the semantic task, response schema, and absence",
        "Concurrent changes to type-card wording",
        "`integrity_sha256`",
        "Unknown, removed, reordered, or resealed mappings fail closed",
        "`V6_SEMANTIC_SYSTEM_PROMPT`",
        "`financial_semantic_v6_prompt`",
    ):
        assert clause in contract_md


def test_persisted_machine_context_preserves_exact_root_order(
    built_artifacts,
) -> None:
    _contract_md, machine, _report, _receipt = built_artifacts
    serialized_machine = _json_bytes(machine)
    persisted = json.loads(serialized_machine)
    model_view = persisted["model_visible_contract"]

    assert list(model_view["representative_user_context"]) == (
        EXACT_FIELD_ORDER
    )
    assert model_view["serialized_user_context_order"] == EXACT_FIELD_ORDER
    assert model_view["serialized_user_context_canonicalization"] == (
        "utf8_minified_json_preserve_insertion_order"
    )
    assert machine["byte_budget"]["goal16_user_context_field_order"] == (
        EXACT_FIELD_ORDER
    )
    assert machine["byte_budget"]["goal16_request_serialization"] == (
        "utf8_minified_json_preserve_insertion_order"
    )


def test_goal16_request_hashes_cover_ordered_user_context_bytes(
    built_artifacts,
) -> None:
    _contract_md, machine, _report, _receipt = built_artifacts
    goal15 = BUILDER._read_json(BUILDER.GOAL15_TRANSPARENT_PATH)
    _matrix, contexts, _metrics, _goal15_metrics = (
        BUILDER._build_case_matrix(goal15)
    )
    metrics = {
        item["case_id"]: item
        for item in machine["byte_budget"]["goal16_per_case_metrics"]
    }

    for case_id, context in contexts.items():
        request_bytes = _ordered_compact_json_bytes(
            {
                "response_schema": copy.deepcopy(EXACT_RESPONSE_SCHEMA),
                "user_context": copy.deepcopy(context),
            }
        )
        decoded = json.loads(request_bytes)
        assert list(decoded["user_context"]) == EXACT_FIELD_ORDER
        assert metrics[case_id]["request_utf8_bytes"] == len(request_bytes)
        assert metrics[case_id]["request_sha256"] == _sha256_bytes(
            request_bytes
        )


def test_markdown_json_blocks_parse_and_match_machine_contract(
    built_artifacts,
) -> None:
    contract_md, machine, report, _receipt = built_artifacts
    contract_blocks = _parse_json_fences(contract_md)
    report_blocks = _parse_json_fences(report)

    assert len(contract_blocks) >= 3
    assert any(block == EXACT_RESPONSE_SCHEMA for block in contract_blocks)
    assert any(
        block == {"plausible_types": ["type_1"]}
        for block in contract_blocks
    )
    assert machine["response_contract"]["logical_schema"] == (
        EXACT_RESPONSE_SCHEMA
    )
    assert all(isinstance(block, (dict, list)) for block in report_blocks)


def test_json_schema_and_manual_ordered_subsequence_validation() -> None:
    Draft202012Validator.check_schema(BUILDER.RESPONSE_SCHEMA)
    schema_validator = Draft202012Validator(BUILDER.RESPONSE_SCHEMA)

    positive_objects = [
        {"plausible_types": []},
        {"plausible_types": ["type_1"]},
        {"plausible_types": ["type_1", "type_2"]},
    ]
    for value in positive_objects:
        before = copy.deepcopy(value)
        schema_validator.validate(value)
        result = BUILDER.validate_response_object(value)
        assert list(result) == value["plausible_types"]
        assert value == before
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        assert list(BUILDER.validate_response_text(encoded)) == (
            value["plausible_types"]
        )

    out_of_order = {"plausible_types": ["type_2", "type_1"]}
    assert list(schema_validator.iter_errors(out_of_order)) == []
    with pytest.raises(
        BUILDER.TypeFirstContractValidationError,
        match="out_of_order_type_keys",
    ):
        BUILDER.validate_response_object(out_of_order)
    assert out_of_order == {
        "plausible_types": ["type_2", "type_1"]
    }


def test_exact_nine_response_negative_fixtures_fail_closed() -> None:
    fixtures = BUILDER.TECHNICAL_RESPONSE_NEGATIVE_FIXTURES
    assert len(fixtures) == 9
    assert [item["fixture_id"] for item in fixtures] == (
        RESPONSE_NEGATIVE_FIXTURE_IDS
    )

    for fixture in fixtures:
        with pytest.raises(
            BUILDER.TypeFirstContractValidationError
        ) as caught:
            BUILDER.validate_response_text(fixture["response_text"])
        assert _error_code(caught.value) == fixture["expected_error_code"]

    backend_fixture = fixtures[-1]
    assert "cash_balance_snapshot_v1" in backend_fixture["response_text"]
    assert backend_fixture["expected_error_code"] == (
        "backend_type_id_forbidden"
    )


def test_schema_rejects_schema_level_negative_examples() -> None:
    validator = Draft202012Validator(BUILDER.RESPONSE_SCHEMA)
    fixtures = {
        item["fixture_id"]: item
        for item in BUILDER.TECHNICAL_RESPONSE_NEGATIVE_FIXTURES
    }
    schema_negative_ids = {
        "missing_plausible_types",
        "plausible_types_null",
        "plausible_types_not_array",
        "unknown_type_key",
        "duplicate_type_key",
        "extra_response_field",
        "backend_type_id_forbidden",
    }

    for fixture_id in schema_negative_ids:
        value = json.loads(fixtures[fixture_id]["response_text"])
        assert list(validator.iter_errors(value)), fixture_id

    out_of_order = json.loads(
        fixtures["out_of_order_type_keys"]["response_text"]
    )
    assert list(validator.iter_errors(out_of_order)) == []


def test_exact_five_contract_integrity_negatives_fail_closed() -> None:
    fixtures = BUILDER.CONTRACT_INTEGRITY_NEGATIVE_FIXTURES
    assert len(fixtures) == 5
    assert [item["fixture_id"] for item in fixtures] == (
        CONTRACT_INTEGRITY_NEGATIVE_FIXTURE_IDS
    )

    for fixture in fixtures:
        BUILDER.validate_seal_match(
            fixture["kind"],
            fixture["expected"],
            fixture["expected"],
        )
        with pytest.raises(
            BUILDER.TypeFirstContractValidationError
        ) as caught:
            BUILDER.validate_seal_match(
                fixture["kind"],
                fixture["observed"],
                fixture["expected"],
            )
        assert _error_code(caught.value) == fixture["expected_error_code"]


def test_exact_two_backend_restoration_negatives_fail_closed() -> None:
    fixtures = BUILDER.BACKEND_RESTORATION_NEGATIVE_FIXTURES
    assert len(fixtures) == 2
    assert [item["fixture_id"] for item in fixtures] == (
        BACKEND_RESTORATION_NEGATIVE_FIXTURE_IDS
    )

    for fixture in fixtures:
        with pytest.raises(
            BUILDER.TypeFirstContractValidationError
        ) as caught:
            BUILDER.derive_backend_decision(
                fixture["plausible_types"],
                fixture["matching_option_ids"],
                typed_option_id=fixture["typed_option_id"],
            )
        assert _error_code(caught.value) == fixture["expected_error_code"]


@pytest.mark.parametrize(
    (
        "plausible_types",
        "matching_option_ids",
        "typed_option_id",
        "expected",
    ),
    [
        (
            [],
            [],
            None,
            {
                "disposition": "unclassified_financial_input",
                "reason_code": "no_registry_type",
            },
        ),
        (
            [],
            ["option_1"],
            None,
            {
                "disposition": "unclassified_financial_input",
                "reason_code": "no_registry_type",
            },
        ),
        (
            [],
            ["option_1", "option_2"],
            None,
            {
                "disposition": "unclassified_financial_input",
                "reason_code": "no_registry_type",
            },
        ),
        (
            ["type_1"],
            [],
            None,
            {
                "disposition": "unclassified_financial_input",
                "reason_code": "single_registry_type_no_safe_record",
            },
        ),
        (
            ["type_1"],
            ["option_1"],
            "option_1",
            {
                "disposition": "typed_input",
                "typed_option_id": "option_1",
            },
        ),
        (
            ["type_1"],
            ["option_1", "option_2"],
            None,
            {
                "disposition": "unclassified_financial_input",
                "reason_code": "single_registry_type_no_safe_record",
            },
        ),
        (
            ["type_1", "type_2"],
            [],
            None,
            {
                "disposition": "unclassified_financial_input",
                "reason_code": "ambiguous_registry_type",
            },
        ),
        (
            ["type_1", "type_2"],
            ["option_1"],
            "option_1",
            {
                "disposition": "unclassified_financial_input",
                "reason_code": "ambiguous_registry_type",
            },
        ),
        (
            ["type_1", "type_2"],
            ["option_1", "option_2"],
            None,
            {
                "disposition": "unclassified_financial_input",
                "reason_code": "ambiguous_registry_type",
            },
        ),
    ],
)
def test_decision_policy_is_total_over_nine_safety_cells(
    plausible_types,
    matching_option_ids,
    typed_option_id,
    expected,
) -> None:
    actual = BUILDER.derive_backend_decision(
        plausible_types,
        matching_option_ids,
        typed_option_id=typed_option_id,
    )
    assert actual == expected
    if actual["disposition"] == "typed_input":
        assert "reason_code" not in actual
    else:
        assert "typed_option_id" not in actual


def test_machine_decision_table_covers_the_same_nine_cells(
    built_artifacts,
) -> None:
    _contract_md, machine, _report, _receipt = built_artifacts
    table = machine["decision_table"]
    assert len(table) == 9

    observed_cells = {
        (
            row["plausible_type_cardinality"],
            row["matching_complete_option_cardinality"],
        )
        for row in table
    }
    assert observed_cells == {
        (plausible, options)
        for plausible in ("zero", "one", "two_or_more")
        for options in ("zero", "one", "two_or_more")
    }

    for row in table:
        plausible = row["plausible_type_cardinality"]
        options = row["matching_complete_option_cardinality"]
        if plausible == "zero":
            assert row["reason_code"] == "no_registry_type"
            assert row["disposition"] == "unclassified_financial_input"
        elif plausible == "two_or_more":
            assert row["reason_code"] == "ambiguous_registry_type"
            assert row["disposition"] == "unclassified_financial_input"
        elif options == "one":
            assert row["disposition"] == "typed_input"
            assert row["reason_code"] is None
            assert row["restoration"] == "exact_code_owned_typed_option"
        else:
            assert row["reason_code"] == (
                "single_registry_type_no_safe_record"
            )
            assert row["disposition"] == "unclassified_financial_input"


def test_ten_case_matrix_is_exact_and_mechanical(
    built_artifacts,
) -> None:
    _contract_md, machine, _report, receipt = built_artifacts
    matrix = machine["ten_case_matrix"]
    assert [row["case_id"] for row in matrix] == CASE_ORDER
    assert receipt["ten_case_count"] == 10

    observed = {row["case_id"]: row for row in matrix}
    for case_id, expected in EXPECTED_CASE_MATRIX.items():
        row = observed[case_id]
        for key, value in expected.items():
            assert row[key] == value, f"{case_id}:{key}"
        if row["expected_disposition"] == "typed_input":
            assert row["unclassified_reason"] is None
            assert row["typed_option_identity"].startswith(
                "financial-typed-option:"
            )
        else:
            assert row["typed_option_identity"] is None
            assert row["source_retention_expectation"] == (
                "full_evidence_bundle_retained"
            )
    assert observed["syn_successor_v2_unique_cash"][
        "typed_option_pin_status"
    ] == "historical_explicit"
    for case_id in (
        "syn_successor_v2_unique_printed_total",
        "syn_successor_v2_optional_missing",
        "syn_successor_v2_forbidden_neighbour",
    ):
        assert observed[case_id]["typed_option_pin_status"] == (
            "current_factory_observation_frozen_by_goal16"
        )


def test_current_local_factories_cross_check_context_and_typed_identities(
    built_artifacts,
    monkeypatch,
) -> None:
    monkeypatch.syspath_prepend(str(SERVICE_ROOT))
    from broker_reports_gate1.gate2_financial_evidence_registry import (
        Gate2FinancialEvidenceRegistryFactory,
    )
    from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (
        Gate2FinancialSemanticV6QualificationFixtureFactory,
    )

    manifest = json.loads(
        (
            SERVICE_ROOT
            / "benchmarks"
            / "gate2_financial_semantic_v6"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    base_manifest = json.loads(
        (
            SERVICE_ROOT
            / "benchmarks"
            / "gate2_financial_successor_v2"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    fixture = Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=Gate2FinancialEvidenceRegistryFactory().create(),
        snapshot_authority_key=b"goal16-current-factory-cross-check",
        continuation_key=b"goal16-current-factory-continuation",
    ).create(manifest=manifest, base_manifest=base_manifest)

    _contract_md, machine, _report, _receipt = built_artifacts
    rows = {row["case_id"]: row for row in machine["ten_case_matrix"]}
    goal15 = BUILDER._read_json(BUILDER.GOAL15_TRANSPARENT_PATH)
    _matrix, contexts, _goal16_metrics, _goal15_metrics = (
        BUILDER._build_case_matrix(goal15)
    )
    assert [case.case_id for case in fixture.semantic_cases] == CASE_ORDER

    for case in fixture.semantic_cases:
        row = rows[case.case_id]
        candidate = case.packet.context_v2_candidate
        assert candidate.provider_calls_total == 0
        assert candidate.payload["source"] == contexts[case.case_id]["source"]
        assert candidate.payload["type_cards"] == (
            contexts[case.case_id]["type_cards"]
        )

        counts = {
            type_key: sum(
                option.input_type_id == canonical_type
                for option in case.compilation.typed_options
            )
            for type_key, canonical_type in (
                BUILDER.PRIVATE_TYPE_MAPPING.items()
            )
        }
        assert counts == row["complete_option_counts_by_type"]

        if row["typed_option_identity"] is not None:
            canonical_type = row["plausible_canonical_types"][0]
            matching = [
                option
                for option in case.compilation.typed_options
                if option.input_type_id == canonical_type
            ]
            assert len(matching) == 1
            assert matching[0].typed_option_id == row[
                "typed_option_identity"
            ]


def test_false_singleton_counters_and_hard_gates_are_exact(
    built_artifacts,
) -> None:
    _contract_md, machine, _report, _receipt = built_artifacts
    qualification = machine["qualification"]

    assert qualification["primary_risk"] == "FALSE_SINGLETON_TYPED_RISK"
    assert qualification["counters"] == QUALIFICATION_COUNTERS
    assert qualification["hard_gates"] == HARD_QUALIFICATION_GATES
    assert qualification["provider_qualification_performed"] is False


def test_byte_budget_is_goal15_derived_and_not_provider_tokenization(
    built_artifacts,
) -> None:
    _contract_md, machine, _report, _receipt = built_artifacts
    budget = machine["byte_budget"]

    assert budget["goal15_logical_request_utf8_bytes"] == {
        "minimum": 2050,
        "maximum": 2208,
    }
    assert budget["goal15_estimated_planning_tokens"] == {
        "minimum": 577,
        "maximum": 616,
    }
    assert budget["future_provider_neutral_max_utf8_bytes"] == 2500
    assert budget["provider_tokenizer_measurement"] is False
    assert budget["sealed_request_proof_deferred"] is True


def test_artifact_receipt_hash_chain_and_zero_change_accounting(
    built_artifacts,
) -> None:
    contract_md, machine, report, receipt = built_artifacts
    machine_material = copy.deepcopy(machine)
    machine_integrity = machine_material.pop("integrity_sha256")
    receipt_material = copy.deepcopy(receipt)
    receipt_integrity = receipt_material.pop("integrity_sha256")

    assert machine_integrity == _sha256_json(machine_material)
    assert receipt_integrity == _sha256_json(receipt_material)
    assert receipt["base_commit"] == EXACT_BASE_COMMIT
    assert receipt["field_order"] == EXACT_FIELD_ORDER
    assert receipt["schema_sha256"] == EXACT_SCHEMA_SHA256
    assert receipt["task_sha256"] == EXACT_TASK_SHA256
    assert receipt["technical_negative_fixture_count"] == 9
    assert receipt["contract_integrity_negative_fixture_count"] == 5
    assert receipt["backend_restoration_negative_fixture_count"] == 2
    assert receipt["technical_negative_fixture_total"] == 16
    assert receipt["provider_calls_total"] == 0
    assert receipt["runtime_changes_total"] == 0
    assert receipt["product_logic_changes_total"] == 0
    assert receipt["historical_files_modified_total"] == 0
    assert receipt["new_owners_total"] == 0
    assert receipt["contract_file_sha256"] == _sha256_bytes(
        contract_md.encode("utf-8")
    )
    assert receipt["artifact_file_sha256"] == _sha256_bytes(
        _json_bytes(machine)
    )
    assert receipt["report_file_sha256"] == _sha256_bytes(
        report.encode("utf-8")
    )


def test_historical_and_active_authority_pins_match_git_blobs(
    built_artifacts,
) -> None:
    _contract_md, machine, _report, _receipt = built_artifacts
    pins = machine["source_authority_pins"]
    historical = [pin for pin in pins if pin["category"] == "historical"]
    active = [pin for pin in pins if pin["category"] == "active"]

    assert len(historical) == 13
    historical_paths = {pin["repository_path"] for pin in historical}
    assert sum("GOAL12" in path for path in historical_paths) == 5
    assert sum("GOAL13" in path for path in historical_paths) == 2
    assert sum("GOAL14" in path for path in historical_paths) == 3
    assert sum("GOAL15" in path for path in historical_paths) == 3

    active_identities = {pin["identity"] for pin in active}
    assert {
        "active_context_v2_1_packet_owner",
        "active_choice_owner",
        "current_semantic_pack",
        "current_minimal_projection_owner",
        "semantic_prompt_owner",
        "provider_adapter_owner",
    } <= active_identities

    assert BUILDER.BASE_COMMIT == EXACT_BASE_COMMIT
    for pin in pins:
        repository_path = pin["repository_path"]
        assert not Path(repository_path).is_absolute()
        working_path = REPO_ROOT / repository_path
        assert working_path.is_file(), pin["identity"]
        repository_bytes = _git_bytes(
            "cat-file",
            "blob",
            f"{EXACT_BASE_COMMIT}:{repository_path}",
        )
        assert b"\r" not in repository_bytes, pin["identity"]
        assert _sha256_bytes(repository_bytes) == pin["sha256"]


def test_builder_is_stdlib_only_offline_support_code() -> None:
    source = BUILD_SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        (node.module or "").split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    assert imported_roots <= {
        "__future__",
        "argparse",
        "copy",
        "hashlib",
        "json",
        "math",
        "pathlib",
        "re",
        "subprocess",
        "typing",
    }

    for forbidden in (
        "sys.path",
        "import requests",
        "import httpx",
        "urllib.request",
        "execute_slot(",
        "extract_context_v2_1_once(",
        "Gate2StructuredModelClientFactory",
        "provider_client",
    ):
        assert forbidden not in source

    module_name = BUILD_SCRIPT.stem
    runtime_root = SERVICE_ROOT / "broker_reports_gate1"
    runtime_references = [
        path
        for path in runtime_root.rglob("*.py")
        if module_name in path.read_text(encoding="utf-8")
    ]
    assert runtime_references == []


def test_repository_safe_outputs_and_model_visibility_scope(
    built_artifacts,
) -> None:
    contract_md, machine, report, receipt = built_artifacts
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
    for value in (machine, receipt):
        assert _recursive_keys(value).isdisjoint(forbidden_keys)

    all_text = "\n".join(
        (
            contract_md,
            json.dumps(machine, ensure_ascii=False, sort_keys=True),
            report,
            json.dumps(receipt, ensure_ascii=False, sort_keys=True),
        )
    )
    assert not re.search(
        r"(?:[A-Za-z]:[\\/](?:Users|Documents|Desktop)[\\/]|"
        r"/(?:home|Users|private|tmp)/)",
        all_text,
    )
    lowered = all_text.lower()
    for marker in ("bearer ", "x-api-key", "api-key"):
        assert marker not in lowered

    model_view_text = json.dumps(
        machine["model_visible_contract"],
        ensure_ascii=False,
        sort_keys=True,
    )
    for backend_value in (
        "cash_balance_snapshot_v1",
        "printed_financial_metric_v1",
        "financial-typed-option:",
    ):
        assert backend_value not in model_view_text


def test_generated_files_and_builder_check_are_byte_exact(
    built_artifacts,
) -> None:
    contract_md, machine, report, receipt = built_artifacts
    expected_outputs = {
        BUILDER.CONTRACT_PATH: contract_md.encode("utf-8"),
        BUILDER.MACHINE_PATH: _json_bytes(machine),
        BUILDER.REPORT_PATH: report.encode("utf-8"),
        BUILDER.RECEIPT_PATH: _json_bytes(receipt),
    }
    for path, expected_bytes in expected_outputs.items():
        assert path.is_file()
        assert path.read_bytes() == expected_bytes

    rebuilt = BUILDER.build_artifacts()
    assert rebuilt == built_artifacts

    completed = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--check"],
        cwd=SERVICE_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    terminal = json.loads(completed.stdout.strip().splitlines()[-1])
    assert terminal["status"] == "passed"
    assert terminal["mode"] == "check"
    assert terminal["provider_calls_total"] == 0
    assert terminal["runtime_changes_total"] == 0


def test_documentation_links_cover_all_goal16_outputs() -> None:
    context_index = (
        REPO_ROOT / "docs" / "stage2" / "CONTEXT_INDEX.md"
    ).read_text(encoding="utf-8")
    exact_evidence = (
        REPO_ROOT
        / "docs"
        / "stage2"
        / "contracts"
        / "BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_EXACT_EVIDENCE.md"
    ).read_text(encoding="utf-8")
    names = {
        "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.md",
        "BROKER_REPORTS_GATE2_TYPE_FIRST_FAIL_CLOSED.v1.json",
        f"{OUTPUT_STEM}.report.md",
        f"{OUTPUT_STEM}.receipt.safe.json",
    }

    for name in names:
        assert name in context_index
        assert name in exact_evidence


def test_goal16_diff_is_exactly_docs_offline_support_and_ci() -> None:
    assert set(BUILDER.EXPECTED_GOAL16_PATHS) == EXPECTED_GOAL16_PATHS
    changed = _goal16_changed_paths()
    report_path = BUILDER.REPORT_PATH.relative_to(REPO_ROOT).as_posix()
    if report_path not in changed:
        pytest.skip("not executing in the complete GOAL 16 change set")

    assert changed == EXPECTED_GOAL16_PATHS
    assert not any(
        path.startswith(
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
        )
        for path in changed
    )
    assert not any(
        path.startswith(
            "services/broker-reports-gate1-proof/managed_assets/"
        )
        or path.startswith(
            "services/broker-reports-gate1-proof/semantic_packs/"
        )
        or path.startswith(
            "services/broker-reports-gate1-proof/benchmarks/"
        )
        for path in changed
    )
    assert not any(
        "GOAL12" in path
        or "GOAL13" in path
        or "GOAL14" in path
        or "GOAL15" in path
        for path in changed
    )


def _parse_json_fences(value: str) -> list[Any]:
    blocks = re.findall(r"```json[ \t]*\n(.*?)\n```", value, flags=re.DOTALL)
    return [json.loads(block) for block in blocks]


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    return str(code if code is not None else error)


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


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json_bytes(value))


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _repository_lf_bytes(value: bytes) -> bytes:
    if b"\r" in value.replace(b"\r\n", b""):
        raise AssertionError("source authority contains lone carriage return")
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


def _goal16_changed_paths() -> set[str]:
    changed: set[str] = set()
    if os.environ.get("GITHUB_ACTIONS") == "true":
        parents = _git("rev-list", "--parents", "-n", "1", "HEAD").split()
        if len(parents) == 3:
            changed.update(
                _git("diff", "--name-only", parents[1], "HEAD").splitlines()
            )
        else:
            changed.update(
                _git("diff", "--name-only", "origin/main...HEAD").splitlines()
            )
    else:
        changed.update(
            _git("diff", "--name-only", "origin/main...HEAD").splitlines()
        )
        changed.update(_git("diff", "--cached", "--name-only").splitlines())
        changed.update(_git("diff", "--name-only").splitlines())
        changed.update(
            _git("ls-files", "--others", "--exclude-standard").splitlines()
        )
    return {path.replace("\\", "/") for path in changed if path}


def _git(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _git_bytes(*arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return completed.stdout
