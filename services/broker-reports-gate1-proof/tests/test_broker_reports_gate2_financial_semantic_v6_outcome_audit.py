from __future__ import annotations

import ast
import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import broker_reports_gate1.gate2_financial_semantic_v6_outcome_audit as audit_module
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from broker_reports_gate1.gate2_financial_semantic_v6_outcome_audit import (
    BASE_MANIFEST_SHA256,
    FORBIDDEN,
    HISTORICAL_BENCHMARK_SHA256,
    NEW_REASON_CODE,
    OUTCOME_AUDIT_INTEGRITY_SHA256,
    REASON_CATALOG_V2_INTEGRITY_SHA256,
    SEMANTIC_PACK_INTEGRITY_SHA256,
    Gate2FinancialSemanticV6OutcomeAuditError,
    validate_financial_semantic_v6_outcome_audit,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
AUDIT_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v6_outcome_audit_v1"
    / "manifest.json"
)
HISTORICAL_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v6"
    / "manifest.json"
)
BASE_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
PACK_PATH = (
    SERVICE_ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
CATALOG_V2_PATH = (
    SERVICE_ROOT
    / "managed_assets"
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v2.json"
)
MODULE_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v6_outcome_audit.py"
)
EXPECTED_HISTORICAL_GIT_BLOBS = {
    HISTORICAL_PATH: (
        "d69de0c4868c5561cacb0a31222cdaa2ac09400a7e2803d48d635aa981e0906c"
    ),
    BASE_PATH: (
        "448a3ea8622a6421c292e5daccef4c5ae65c38a7720a83e1cb8151daa4d2e1aa"
    ),
    PACK_PATH: (
        "ae07f1d378169e82792aa1f0ed6cebc346591e047656f14df0fcead1f5a18d1f"
    ),
}


def _read(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _inputs() -> dict:
    return {
        "manifest": _read(AUDIT_PATH),
        "historical_manifest": _read(HISTORICAL_PATH),
        "base_manifest": _read(BASE_PATH),
        "semantic_pack": _read(PACK_PATH),
        "reason_catalog_v2": _read(CATALOG_V2_PATH),
    }


def _canonical_without_integrity(value: dict) -> tuple[str, int]:
    material = copy.deepcopy(value)
    material.pop("integrity_sha256")
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), len(encoded)


def _reseal_manifest(monkeypatch, value: dict) -> None:
    digest, _ = _canonical_without_integrity(value)
    value["integrity_sha256"] = digest
    monkeypatch.setattr(
        audit_module,
        "OUTCOME_AUDIT_INTEGRITY_SHA256",
        digest,
    )


def _git_blob(path: Path) -> bytes:
    relative = path.relative_to(REPO_ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def test_outcome_audit_validates_total_taxonomy_and_three_corrections() -> None:
    snapshot = validate_financial_semantic_v6_outcome_audit(**_inputs())

    assert snapshot.schema_version == (
        "broker_reports_gate2_financial_semantic_v6_outcome_audit_v1"
    )
    assert snapshot.cases_total == 12
    assert snapshot.corrected_expected_answers_total == 3
    assert snapshot.zero_choice_plausible_type_counts == (2, 1, 1, 1)
    assert snapshot.semantic_pack_integrity_sha256 == (
        SEMANTIC_PACK_INTEGRITY_SHA256
    )
    assert snapshot.reason_catalog_integrity_sha256 == (
        REASON_CATALOG_V2_INTEGRITY_SHA256
    )
    assert snapshot.integrity_sha256 == OUTCOME_AUDIT_INTEGRITY_SHA256
    assert snapshot.safe_summary()["zero_choice_plausible_type_counts"] == [
        2,
        1,
        1,
        1,
    ]


def test_outcome_audit_is_self_sealed_and_not_executed() -> None:
    manifest = _read(AUDIT_PATH)
    digest, canonical_bytes = _canonical_without_integrity(manifest)

    assert digest == OUTCOME_AUDIT_INTEGRITY_SHA256
    assert canonical_bytes == 10866
    assert manifest["execution_policy"] == {
        "provider_calls": 0,
        "full_benchmark_run": False,
        "hidden_retry": False,
        "repair": False,
        "fallback": False,
        "fixture_decisions_are_provider_outputs": False,
        "runtime_activation": False,
        "active_v6_consumer": False,
    }
    assert manifest["reason_catalog"]["response_profile_status"] == (
        "not_implemented"
    )


def test_historical_benchmark_base_and_pack_are_exactly_unchanged() -> None:
    historical = _read(HISTORICAL_PATH)
    base = _read(BASE_PATH)

    assert sha256_json(historical) == HISTORICAL_BENCHMARK_SHA256
    assert sha256_json(base) == BASE_MANIFEST_SHA256
    for path, expected in EXPECTED_HISTORICAL_GIT_BLOBS.items():
        assert hashlib.sha256(_git_blob(path)).hexdigest() == expected


def test_only_three_expected_reasons_change_from_historical_manifest() -> None:
    audit = _read(AUDIT_PATH)
    historical = _read(HISTORICAL_PATH)
    historical_by_id = {
        item["case_id"]: item for item in historical["cases"]
    }
    changed = {
        item["case_id"]
        for item in audit["cases"]
        if item["expected_reason_code"]
        != historical_by_id[item["case_id"]]["expected_reason_code"]
    }

    assert changed == {
        "syn_successor_v2_detail_vs_subtotal",
        "syn_successor_v2_adjacent_equal",
        "syn_successor_v2_adjacent_fx",
    }
    assert {
        item["expected_reason_code"]
        for item in audit["cases"]
        if item["case_id"] in changed
    } == {NEW_REASON_CODE}


def test_audit_validator_contains_no_execution_or_semantic_inference_route() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")

    assert "Gate2StructuredModelClientFactory" not in source
    assert "qualify_financial_semantic_v6" not in source
    assert "_fixture_model_choice" not in source
    assert "literal_value" not in source
    assert "must not mutate" in FORBIDDEN


def test_audit_validator_imports_and_runtime_consumers_are_closed() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module
        if isinstance(node, ast.ImportFrom)
        else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (
            node.names if isinstance(node, ast.Import) else [node.names[0]]
        )
    }
    assert imports == {
        "__future__",
        "copy",
        "dataclasses",
        "gate2_financial_evidence_materialization_contracts",
        "gate2_financial_semantic_v6_benchmark",
        "hashlib",
        "json",
        "typing",
    }
    dynamic_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert dynamic_calls.isdisjoint({"__import__", "eval", "exec"})

    inactive_model_assets_path = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "gate2_financial_semantic_model_assets.py"
    )
    inactive_choice_profile_path = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "gate2_financial_semantic_v6_choice.py"
    )
    candidate_canonical_path = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "gate2_financial_semantic_v6_canonical.py"
    )
    candidate_smoke_report_path = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "gate2_financial_semantic_v6_smoke_report.py"
    )
    candidate_smoke_evidence_path = (
        SERVICE_ROOT
        / "broker_reports_gate1"
        / "gate2_financial_semantic_v6_evidence.py"
    )
    for path in (SERVICE_ROOT / "broker_reports_gate1").glob("*.py"):
        if path == MODULE_PATH:
            continue
        active_source = path.read_text(encoding="utf-8")
        assert MODULE_PATH.stem not in active_source
        if path not in {
            inactive_model_assets_path,
            inactive_choice_profile_path,
            candidate_canonical_path,
            candidate_smoke_report_path,
            candidate_smoke_evidence_path,
        }:
            assert NEW_REASON_CODE not in active_source
    choice_source = inactive_choice_profile_path.read_text(encoding="utf-8")
    assert choice_source.count(NEW_REASON_CODE) == 1
    assert "CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES" in choice_source

    canonical_tree = ast.parse(
        candidate_canonical_path.read_text(encoding="utf-8")
    )
    reason_literal_owners = set()
    for node in canonical_tree.body:
        candidates = (
            [(node.name, node)]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            else (
                [
                    (f"{node.name}.{method.name}", method)
                    for method in node.body
                    if isinstance(
                        method,
                        (ast.FunctionDef, ast.AsyncFunctionDef),
                    )
                ]
                if isinstance(node, ast.ClassDef)
                else []
            )
        )
        for owner, candidate in candidates:
            if any(
                isinstance(item, ast.Constant)
                and item.value == NEW_REASON_CODE
                for item in ast.walk(candidate)
            ):
                reason_literal_owners.add(owner)
    assert reason_literal_owners == {
        (
            "_Gate2FinancialSemanticV6ContextV21DecisionContract."
            "_parse_unclassified"
        ),
        "_context_v2_1_candidate_contract",
    }
    canonical_factory = next(
        node
        for node in canonical_tree.body
        if isinstance(node, ast.ClassDef)
        and node.name
        == "Gate2FinancialSemanticV6CanonicalDecisionContractFactory"
    )
    active_create = next(
        node
        for node in canonical_factory.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "create"
    )
    assert all(
        not isinstance(item, ast.Constant)
        or item.value != NEW_REASON_CODE
        for item in ast.walk(active_create)
    )
    active_context_flags = [
        keyword.value
        for item in ast.walk(active_create)
        if isinstance(item, ast.Call)
        for keyword in item.keywords
        if keyword.arg == "context_v2_1_candidate"
    ]
    assert len(active_context_flags) == 1
    assert isinstance(active_context_flags[0], ast.Constant)
    assert active_context_flags[0].value is False

    smoke_report_tree = ast.parse(
        candidate_smoke_report_path.read_text(encoding="utf-8")
    )
    literal_assignments = {
        target.id
        for node in smoke_report_tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
        )
        if isinstance(target, ast.Name)
        and any(
            isinstance(item, ast.Constant)
            and item.value == NEW_REASON_CODE
            for item in ast.walk(node.value)
        )
    }
    assert literal_assignments == {
        "CONTEXT_V2_1_PROVIDER_PROOF_EXPECTED_ANSWERS",
        "CONTEXT_V2_1_PROVIDER_PROOF_EXTRACTED_OUTPUTS",
    }
    governed_constants = literal_assignments
    governed_constant_consumers = set()
    for node in smoke_report_tree.body:
        candidates = (
            [(node.name, node)]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            else (
                [
                    (f"{node.name}.{method.name}", method)
                    for method in node.body
                    if isinstance(
                        method,
                        (ast.FunctionDef, ast.AsyncFunctionDef),
                    )
                ]
                if isinstance(node, ast.ClassDef)
                else []
            )
        )
        for owner, candidate in candidates:
            if {
                item.id
                for item in ast.walk(candidate)
                if isinstance(item, ast.Name)
            } & governed_constants:
                governed_constant_consumers.add(owner)
    assert governed_constant_consumers == {
        (
            "Gate2FinancialSemanticV6TransparentSmokeReportFactory."
            "create_context_v2_1_provider_case"
        ),
        "_context_v2_1_case_projection_is_valid",
        "_context_v2_1_extracted_output_is_exact",
    }


@pytest.mark.parametrize(
    ("mutate", "error_code"),
    [
        (
            lambda value: value["execution_policy"].update(
                active_v6_consumer=True
            ),
            "financial_semantic_v6_outcome_audit_identity_invalid",
        ),
        (
            lambda value: value["truth_table"][3].update(
                semantic_reason_code="ambiguous_registry_type"
            ),
            "financial_semantic_v6_outcome_audit_truth_table_invalid",
        ),
        (
            lambda value: value["truth_table"][0].update(
                unallowlisted_field="forbidden"
            ),
            "financial_semantic_v6_outcome_audit_truth_table_invalid",
        ),
        (
            lambda value: value["cases"][6].update(
                expected_reason_code="ambiguous_registry_type"
            ),
            "financial_semantic_v6_outcome_audit_correction_invalid",
        ),
        (
            lambda value: value["zero_choice_audit"][2][
                "primary_evidence"
            ]["source_manifest_pointers"].__setitem__(
                0,
                "/cases/7/cells/99",
            ),
            "financial_semantic_v6_outcome_audit_evidence_invalid",
        ),
        (
            lambda value: value["zero_choice_audit"][1].update(
                plausible_type_ids=[
                    "cash_balance_snapshot_v1",
                    "printed_financial_metric_v1",
                ]
            ),
            "financial_semantic_v6_outcome_audit_zero_choice_invalid",
        ),
    ],
)
def test_outcome_audit_tampering_fails_closed(
    monkeypatch,
    mutate,
    error_code,
) -> None:
    inputs = _inputs()
    invalid = copy.deepcopy(inputs["manifest"])
    mutate(invalid)
    _reseal_manifest(monkeypatch, invalid)
    inputs["manifest"] = invalid

    with pytest.raises(Gate2FinancialSemanticV6OutcomeAuditError, match=error_code):
        validate_financial_semantic_v6_outcome_audit(**inputs)


def test_same_count_plausible_type_substitution_fails_closed(
    monkeypatch,
) -> None:
    inputs = _inputs()
    invalid = copy.deepcopy(inputs["manifest"])
    replacement = ["cash_balance_snapshot_v1"]
    invalid["cases"][6]["plausible_type_ids"] = replacement
    invalid["zero_choice_audit"][1]["plausible_type_ids"] = replacement
    _reseal_manifest(monkeypatch, invalid)
    inputs["manifest"] = invalid

    with pytest.raises(
        Gate2FinancialSemanticV6OutcomeAuditError,
        match="financial_semantic_v6_outcome_audit_types_invalid",
    ):
        validate_financial_semantic_v6_outcome_audit(**inputs)


def test_reordered_exact_evidence_pointers_fail_closed(monkeypatch) -> None:
    inputs = _inputs()
    invalid = copy.deepcopy(inputs["manifest"])
    invalid["zero_choice_audit"][0]["primary_evidence"][
        "semantic_pack_pointers"
    ].reverse()
    _reseal_manifest(monkeypatch, invalid)
    inputs["manifest"] = invalid

    with pytest.raises(
        Gate2FinancialSemanticV6OutcomeAuditError,
        match="financial_semantic_v6_outcome_audit_evidence_invalid",
    ):
        validate_financial_semantic_v6_outcome_audit(**inputs)


def test_historical_benchmark_tamper_still_fails_before_audit() -> None:
    inputs = _inputs()
    inputs["historical_manifest"]["cases"][0]["expected_typed_options"] = 0

    with pytest.raises(ValueError, match="financial_semantic_v6_benchmark"):
        validate_financial_semantic_v6_outcome_audit(**inputs)
