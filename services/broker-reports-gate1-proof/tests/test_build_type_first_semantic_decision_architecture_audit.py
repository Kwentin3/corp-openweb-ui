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

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
BUILD_SCRIPT = (
    SERVICE_ROOT
    / "scripts"
    / "build_type_first_semantic_decision_architecture_audit.py"
)
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-07-30"
OUTPUT_STEM = (
    "BROKER_REPORTS_GATE2_TYPE_FIRST_SEMANTIC_DECISION_"
    "ARCHITECTURE_AUDIT_GOAL15"
)
REPORT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.report.md"
TRANSPARENT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.transparent.json"
RECEIPT_PATH = REPORT_ROOT / f"{OUTPUT_STEM}.receipt.safe.json"

VARIANT_IDS = [
    "ONE_CALL_CHOICES_AND_PLAUSIBLE_TYPES",
    "ONE_CALL_TYPE_FIRST_FAIL_CLOSED",
    "TYPE_FIRST_THEN_RECORD_SELECTION",
]
DETAILED_CASE_IDS = [
    "syn_successor_v2_unique_cash",
    "syn_successor_v2_no_registry_type",
    "syn_successor_v2_multiple_compatible",
    "syn_successor_v2_detail_vs_subtotal",
]
CASE_IDS = [
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
EXPECTED_GOAL15_PATHS = {
    ".gitattributes",
    ".github/workflows/broker-reports-ci.yml",
    f"docs/reports/2026-07-30/{OUTPUT_STEM}.receipt.safe.json",
    f"docs/reports/2026-07-30/{OUTPUT_STEM}.report.md",
    f"docs/reports/2026-07-30/{OUTPUT_STEM}.transparent.json",
    "docs/stage2/CONTEXT_INDEX.md",
    (
        "docs/stage2/contracts/"
        "BROKER_REPORTS_GATE2_FINANCIAL_SEMANTIC_V6_EXACT_EVIDENCE.md"
    ),
    (
        "services/broker-reports-gate1-proof/scripts/"
        "build_type_first_semantic_decision_architecture_audit.py"
    ),
    (
        "services/broker-reports-gate1-proof/tests/"
        "test_build_type_first_semantic_decision_architecture_audit.py"
    ),
}


def _load_builder():
    name = "build_type_first_semantic_decision_architecture_audit_under_test"
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


def test_exactly_three_variants_four_detailed_and_ten_governed_cases(
    built_artifacts,
) -> None:
    _report, transparent, receipt = built_artifacts

    assert [item["variant_id"] for item in transparent["variants"]] == (
        VARIANT_IDS
    )
    assert transparent["detailed_case_ids"] == DETAILED_CASE_IDS
    assert [
        item["case_id"] for item in transparent["per_case_simulations"]
    ] == CASE_IDS
    assert receipt["variant_ids"] == VARIANT_IDS
    assert receipt["detailed_cases_simulated"] == DETAILED_CASE_IDS
    assert receipt["cases_simulated"] == CASE_IDS


def test_report_has_exact_fourteen_sections_and_parseable_json_blocks(
    built_artifacts,
) -> None:
    report, _transparent, _receipt = built_artifacts
    headings = re.findall(r"^## (.+)$", report, flags=re.MULTILINE)
    assert headings == [
        "1. Problem statement",
        "2. Facts established by GOAL 14",
        "3. Variant A",
        "4. Variant B",
        "5. Variant C",
        "6. Four-case simulation",
        "7. Ten-case mechanical simulation",
        "8. Same-type multi-option scenario",
        "9. Authority/change-surface matrix",
        "10. Byte/call estimates",
        "11. Comparison matrix",
        "12. Recommendation",
        "13. Unresolved questions",
        "14. Decision boundary",
    ]
    blocks = re.findall(r"```json\n(.*?)\n```", report, flags=re.DOTALL)
    assert len(blocks) >= 16
    assert all(json.loads(block) is not None for block in blocks)


def test_logical_contracts_are_provider_neutral_and_closed(
    built_artifacts,
) -> None:
    _report, transparent, _receipt = built_artifacts
    variants = {
        item["variant_id"]: item for item in transparent["variants"]
    }
    a = variants[VARIANT_IDS[0]]
    b = variants[VARIANT_IDS[1]]
    c = variants[VARIANT_IDS[2]]

    assert list(a["logical_stage1_request_sketch"]) == [
        "response_schema",
        "user_context",
    ]
    assert set(a["logical_stage1_request_sketch"]["user_context"]) == {
        "task",
        "source_summary",
        "plausible_type_cards",
        "complete_options",
        "differentiators",
    }
    a_task = a["logical_stage1_request_sketch"]["user_context"]["task"]
    assert "Return every plausible type_key" in a_task
    assert "independently of whether complete_options" in a_task
    assert "otherwise set selected_choice to null" in a_task
    for item in (b, c):
        assert set(item["logical_stage1_request_sketch"]["user_context"]) == {
            "task",
            "source_summary",
            "plausible_type_cards",
        }
        task = item["logical_stage1_request_sketch"]["user_context"]["task"]
        assert "Return every plausible type_key" in task
        assert "Return all plausible types, not only the best one" in task
        assert "independently of whether any complete record" in task
    assert a["logical_stage2_request_sketch"] is None
    assert b["logical_stage2_request_sketch"] is None
    stage2 = c["logical_stage2_request_sketch"]
    assert set(stage2["user_context"]) == {
        "task",
        "source_summary",
        "selected_type_card",
        "complete_options",
        "differentiators",
    }
    assert "plausible_types" not in stage2["response_schema"]["properties"]
    assert set(stage2["response_schema"]["properties"]) == {
        "selected_choice"
    }
    stage2_task = stage2["user_context"]["task"]
    assert "financial type is fixed by Stage 1" in stage2_task
    assert "Do not reconsider or return a type" in stage2_task
    assert "otherwise return selected_choice as null" in stage2_task
    assert all(
        item["provider_specific_wrapper_required"] is False
        for item in variants.values()
    )


def test_ten_case_simulation_is_mechanical_and_matches_corrected_answers(
    built_artifacts,
) -> None:
    _report, transparent, _receipt = built_artifacts
    expected_states = {
        "syn_successor_v2_unique_cash": "typed_safe_1",
        "syn_successor_v2_unique_printed_total": "typed_safe_1",
        "syn_successor_v2_multiple_compatible": "ambiguous_type_2plus",
        "syn_successor_v2_no_registry_type": "no_type_0",
        "syn_successor_v2_missing_discriminator": "ambiguous_type_2plus",
        "syn_successor_v2_detail_vs_subtotal": (
            "single_type_no_safe_record"
        ),
        "syn_successor_v2_adjacent_equal": "single_type_no_safe_record",
        "syn_successor_v2_adjacent_fx": "single_type_no_safe_record",
        "syn_successor_v2_optional_missing": "typed_safe_1",
        "syn_successor_v2_forbidden_neighbour": "typed_safe_1",
    }

    for case in transparent["per_case_simulations"]:
        assert case["expected_semantic_state"] == expected_states[
            case["case_id"]
        ]
        assert case["semantic_audit_status"] == "authority_pinned"
        assert case["plausible_type_count"] == len(
            case["audited_plausible_types"]
        )
        assert sum(
            case["available_complete_option_counts_by_type"].values()
        ) == len(case["complete_options"])
        assert len(case["variant_results"]) == 3
        for result in case["variant_results"]:
            assert result["final_canonical_disposition"] == (
                case["expected_final_answer"]["disposition"]
            )
            if result["final_canonical_disposition"] != "typed_input":
                assert result["final_reason_or_typed_option"][
                    "reason_code"
                ] == case["expected_final_answer"]["reason_code"]
            assert result["llm_call_count"] == 1
            assert result["stage2_required"] is False
            assert result["stage2_request"] is None
            assert result["possible_completeness_loss"] == (
                "none_observed_in_governed_fixture"
            )
            assert (
                "proposed_stage1_returns_frozen_audited_plausible_set"
                in result["unproven_semantic_assumptions"]
            )


def test_variant_c_stage2_is_zero_for_governed_cases_and_b_equals_c(
    built_artifacts,
) -> None:
    _report, transparent, _receipt = built_artifacts
    budget = transparent["byte_and_call_budget"]["variants"]
    b = budget[VARIANT_IDS[1]]
    c = budget[VARIANT_IDS[2]]

    assert b["governed_stage1_request_utf8_bytes_total"] == 21343
    assert b["governed_stage1_estimated_input_tokens_total"] == 5979
    assert c["governed_stage1_request_utf8_bytes_total"] == 21343
    assert c["governed_stage1_estimated_input_tokens_total"] == 5979
    assert c["governed_stage1_calls_total"] == 10
    assert c["governed_stage2_calls_total"] == 0
    assert c["governed_aggregate_calls_total"] == 10
    assert c["architectural_worst_calls_per_operation"] == 2
    assert c["ten_operation_architectural_upper_bound_calls"] == 20

    for case in transparent["per_case_simulations"]:
        results = {
            item["variant_id"]: item for item in case["variant_results"]
        }
        assert results[VARIANT_IDS[1]]["final_canonical_disposition"] == (
            results[VARIANT_IDS[2]]["final_canonical_disposition"]
        )
        assert results[VARIANT_IDS[1]][
            "final_reason_or_typed_option"
        ] == results[VARIANT_IDS[2]]["final_reason_or_typed_option"]


def test_same_type_scenario_exposes_b_c_difference_without_evidence_claim(
    built_artifacts,
) -> None:
    _report, transparent, _receipt = built_artifacts
    scenario = transparent["same_type_multiple_option_scenario"]

    assert scenario["evidence_class"] == (
        "documentation_only_thought_experiment"
    )
    assert scenario["benchmark_fixture"] is False
    assert scenario["product_case"] is False
    assert scenario["frequency_evidence"] is False
    assert scenario["stipulated_plausible_types"] == ["type_1"]
    assert scenario["complete_option_counts_by_type"] == {
        "type_1": 2,
        "type_2": 0,
    }
    assert scenario["variant_b"]["final"] == {
        "disposition": "unclassified_financial_input",
        "reason_code": "single_registry_type_no_safe_record",
    }
    assert scenario["variant_c"]["calls"] == 2
    assert scenario["variant_c"]["stage2_request_metrics"][
        "request_utf8_bytes"
    ] == 2073
    assert scenario["variant_c"]["stage2_request_metrics"][
        "estimated_input_tokens"
    ] == 583
    assert scenario["variant_c"]["stage2_request"]["user_context"][
        "selected_type_card"
    ]["type_key"] == "type_1"
    assert all(
        item["type_key"] == "type_1"
        for item in scenario["variant_c"]["stage2_request"]["user_context"][
            "complete_options"
        ]
    )


def test_authority_matrix_has_twelve_existing_owners_and_no_new_owner(
    built_artifacts,
) -> None:
    _report, transparent, _receipt = built_artifacts
    surface = transparent["authority_change_surface"]
    assert len(surface["rows"]) == 12
    assert surface["new_owner_required_total"] == 0
    for row in surface["rows"]:
        assert row["existing_owner"]
        assert set(row["changes"]) == set(VARIANT_IDS)
        assert set(row["new_owner_required"]) == set(VARIANT_IDS)
        assert not any(row["new_owner_required"].values())
        assert set(row["changes"].values()) <= {
            "unchanged",
            "additive_profile",
            "behavior_change_later_required",
        }
    economy = next(
        row
        for row in surface["rows"]
        if row["concern"] == "operation/economy accounting"
    )
    assert economy["changes"][VARIANT_IDS[2]] == (
        "behavior_change_later_required"
    )


def test_comparison_has_twenty_equal_criteria_and_selected_recommendation(
    built_artifacts,
) -> None:
    _report, transparent, receipt = built_artifacts
    comparison = transparent["comparison"]
    assert len(comparison["criteria"]) == 20
    assert comparison["maximum_weighted_score"] == 160
    assert comparison["weighted_totals"] == {
        VARIANT_IDS[0]: {
            "score": 101,
            "maximum": 160,
            "percentage": 63.1,
        },
        VARIANT_IDS[1]: {
            "score": 142,
            "maximum": 160,
            "percentage": 88.8,
        },
        VARIANT_IDS[2]: {
            "score": 130,
            "maximum": 160,
            "percentage": 81.2,
        },
    }
    assert transparent["recommendation"]["recommendation_id"] == (
        "SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C"
    )
    assert transparent["recommendation"]["confidence"] == "medium"
    assert receipt["recommendation_id"] == (
        "SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C"
    )
    assert receipt["confidence"] == "medium"
    assert receipt["unresolved_assumptions_count"] == 7


def test_receipt_integrity_file_hashes_and_zero_change_accounting(
    built_artifacts,
) -> None:
    report, transparent, receipt = built_artifacts
    material = copy.deepcopy(receipt)
    supplied = material.pop("integrity_sha256")
    assert supplied == BUILDER._sha256_json(material)
    assert receipt["report_file_sha256"] == hashlib.sha256(
        report.encode("utf-8")
    ).hexdigest()
    assert receipt["transparent_file_sha256"] == hashlib.sha256(
        BUILDER._json_bytes(transparent)
    ).hexdigest()
    assert receipt["provider_calls_total"] == 0
    assert receipt["runtime_changes_total"] == 0
    assert receipt["product_logic_changes_total"] == 0
    assert receipt["historical_files_modified_total"] == 0
    assert set(transparent["execution_accounting"].values()) == {0}
    assert set(transparent["change_accounting"].values()) == {0}


def test_historical_goal12_to_goal14_authorities_are_immutable_and_safe(
    built_artifacts,
) -> None:
    _report, transparent, receipt = built_artifacts
    actual = BUILDER._validate_source_authorities()
    assert len(BUILDER.HISTORICAL_AUTHORITIES) == 10
    for identity, path, expected_hash in BUILDER.HISTORICAL_AUTHORITIES:
        repository_path = path.relative_to(REPO_ROOT).as_posix()
        repository_bytes = _git_bytes(
            "cat-file",
            "blob",
            f"HEAD:{repository_path}",
        )
        assert b"\r" not in repository_bytes, identity
        assert hashlib.sha256(repository_bytes).hexdigest() == expected_hash
        assert actual[identity] == expected_hash

    for artifact in (transparent, receipt):
        BUILDER._validate_repository_safe_output(artifact)
        assert BUILDER._recursive_keys(artifact).isdisjoint(
            BUILDER._FORBIDDEN_OUTPUT_KEYS
        )
    assert BUILDER._repository_lf_bytes(b"a\r\nb\n") == b"a\nb\n"
    with pytest.raises(
        ValueError,
        match="source_authority_lone_carriage_return",
    ):
        BUILDER._repository_lf_bytes(b"a\rb\n")


def test_builder_is_closed_world_offline_support_code() -> None:
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
        "pathlib",
        "re",
        "typing",
    }
    for forbidden in (
        "sys.path",
        "import requests",
        "requests.get(",
        "requests.post(",
        "import httpx",
        "httpx.Client(",
        "urllib.request",
        "execute_slot(",
        "extract_context_v2_1_once(",
        "Gate2StructuredModelClientFactory",
    ):
        assert forbidden not in source


def test_generated_files_and_check_mode_are_byte_exact(
    built_artifacts,
    tmp_path,
) -> None:
    report, transparent, receipt = built_artifacts
    assert REPORT_PATH.read_bytes() == report.encode("utf-8")
    assert TRANSPARENT_PATH.read_bytes() == BUILDER._json_bytes(transparent)
    assert RECEIPT_PATH.read_bytes() == BUILDER._json_bytes(receipt)

    completed = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--check"],
        cwd=SERVICE_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    summary = json.loads(completed.stdout)
    assert summary == {
        "detailed_cases_total": 4,
        "governed_cases_total": 10,
        "historical_files_modified_total": 0,
        "mode": "check",
        "product_logic_changes_total": 0,
        "provider_calls_total": 0,
        "recommendation_id": (
            "SELECT_VARIANT_B_AS_MVP_AND_RESERVE_C"
        ),
        "runtime_changes_total": 0,
        "status": "passed",
        "variants_total": 3,
    }

    isolated = tmp_path / "artifact.json"
    expected = b'{\n  "status": "completed"\n}\n'
    outputs = {isolated: expected}
    BUILDER.write_or_check_outputs(outputs=outputs, check=False)
    BUILDER.write_or_check_outputs(outputs=outputs, check=True)
    isolated.write_bytes(expected + b"\r\n")
    with pytest.raises(
        SystemExit,
        match="type_first_semantic_decision_audit_drift:artifact.json",
    ):
        BUILDER.write_or_check_outputs(outputs=outputs, check=True)


def test_documentation_links_point_to_generated_artifacts() -> None:
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
    for name in (REPORT_PATH.name, TRANSPARENT_PATH.name, RECEIPT_PATH.name):
        assert name in context_index
        assert name in exact_evidence


def test_goal15_diff_is_docs_offline_support_and_ci_only() -> None:
    changed = _goal15_changed_paths()
    report_path = REPORT_PATH.relative_to(REPO_ROOT).as_posix()
    if report_path not in changed:
        pytest.skip("not executing in the GOAL 15 change set")
    assert changed == EXPECTED_GOAL15_PATHS
    assert not any(
        path.startswith(
            "services/broker-reports-gate1-proof/broker_reports_gate1/"
        )
        for path in changed
    )
    assert not any(
        "GOAL12" in path or "GOAL13" in path or "GOAL14" in path
        for path in changed
    )


def _goal15_changed_paths() -> set[str]:
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
