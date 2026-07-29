from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import jsonschema
import pytest

from broker_reports_gate1.gate2_financial_evidence_decision import (
    UNCLASSIFIED_REASON_CODES,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
CATALOG_V1_PATH = (
    SERVICE_ROOT
    / "managed_assets"
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v1.json"
)
CATALOG_V2_PATH = CATALOG_V1_PATH.with_name(
    "broker_reports_gate2_financial_decision_reason_catalog.v2.json"
)
CONTRACT_V1_PATH = (
    SERVICE_ROOT
    / "scripts"
    / "broker_reports_financial_decision_reason_catalog_contracts.py"
)
CONTRACT_V2_PATH = CONTRACT_V1_PATH.with_name(
    "broker_reports_financial_decision_reason_catalog_v2_contracts.py"
)
DECISION_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_decision.py"
)
ACTIVE_PROMPT_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v6_prompt.py"
)
FAMILY_V2_PATH = (
    SERVICE_ROOT
    / "managed_assets"
    / "broker_reports_financial_domain_assets.v2.manifest.json"
)
NEW_REASON = "single_registry_type_no_safe_record"
EXPECTED_IMMUTABLE_GIT_BLOBS = {
    CATALOG_V1_PATH: (
        "e5ca49c436113d5eebec189dae26d5a289287c214292eb32c80b547c29e56a0a"
    ),
    CONTRACT_V1_PATH: (
        "999b5d3869a9b08755bc6697c10aa725f92527a65d0d484515651420d5a8d375"
    ),
    DECISION_PATH: (
        "dc4fd160aeda35b2d0a3d063a871d4cc71f6efcefcc134d0d164722d5176f19f"
    ),
    ACTIVE_PROMPT_PATH: (
        "a6334ae2dd7e0f417e8ad629dbec9423ccc297b8fe20acac119d6b2caadfb8fc"
    ),
    FAMILY_V2_PATH: (
        "4ef70eba07bea24332a0909e4c9cb68c82854197a11fb2e78f47c3d88cf3d586"
    ),
}


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _load_contract() -> ModuleType:
    name = "broker_reports_financial_decision_reason_catalog_v2_contracts_test"
    spec = importlib.util.spec_from_file_location(name, CONTRACT_V2_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _factory(module: ModuleType, candidate: dict | None = None):
    return module.Gate2FinancialDecisionReasonCatalogV2ContractFactory(
        predecessor_catalog=_read_json(CATALOG_V1_PATH),
        candidate_catalog=candidate or _read_json(CATALOG_V2_PATH),
    )


def _reseal(value: dict) -> None:
    material = copy.deepcopy(value)
    material.pop("integrity_sha256", None)
    value["integrity_sha256"] = hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _git_blob(path: Path) -> bytes:
    relative = path.relative_to(REPO_ROOT).as_posix()
    return subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def test_catalog_v2_is_valid_inactive_and_gui_schema_ready() -> None:
    module = _load_contract()
    catalog = _read_json(CATALOG_V2_PATH)
    factory = _factory(module, catalog)
    schema = factory.schema()

    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(catalog)
    snapshot = factory.create(catalog=catalog)

    assert snapshot.schema_version == (
        "broker_reports_gate2_financial_decision_reason_catalog_v2"
    )
    assert snapshot.semantic_version == "2.0.0"
    assert snapshot.runtime_activation is False
    assert snapshot.response_profile_status == "not_implemented"
    assert snapshot.family_packaging_status == "not_packaged_until_goal7"
    assert snapshot.predecessor_reason_codes == UNCLASSIFIED_REASON_CODES[::-1]
    assert snapshot.added_reason_code == NEW_REASON
    assert snapshot.reason_codes == (
        "no_registry_type",
        NEW_REASON,
        "ambiguous_registry_type",
    )
    assert snapshot.integrity_sha256 == (
        "2510b57b51749a14f76b987cddaa3eea19f1bb975a97c6c089565253dc3593e9"
    )
    assert snapshot.canonical_semantic_bytes == 6393
    assert NEW_REASON not in UNCLASSIFIED_REASON_CODES


def test_catalog_v2_boundaries_are_total_and_existing_meanings_are_exact() -> None:
    v1 = _read_json(CATALOG_V1_PATH)
    v2 = _read_json(CATALOG_V2_PATH)
    v1_by_code = {item["code"]: item for item in v1["reasons"]}
    v2_by_code = {item["code"]: item for item in v2["reasons"]}

    assert set(v2_by_code) == {*UNCLASSIFIED_REASON_CODES, NEW_REASON}
    assert [
        (
            item["selection_boundary"][
                "plausible_distinct_available_financial_type_count"
            ]["minimum_inclusive"],
            item["selection_boundary"][
                "plausible_distinct_available_financial_type_count"
            ]["maximum_inclusive"],
            item["selection_boundary"][
                "uniquely_safe_prebound_choice_count"
            ]["minimum_inclusive"],
            item["selection_boundary"][
                "uniquely_safe_prebound_choice_count"
            ]["maximum_inclusive"],
        )
        for item in v2["reasons"]
    ] == [
        (0, 0, 0, 0),
        (1, 1, 0, 0),
        (2, "unbounded", 0, 0),
    ]
    for code in UNCLASSIFIED_REASON_CODES:
        for field in (
            "human_title",
            "meaning",
            "use_when",
            "do_not_use_when",
            "positive_example",
        ):
            assert v2_by_code[code][field] == v1_by_code[code][field]
    for code, reason in v2_by_code.items():
        assert {
            item["reason_code"]
            for item in reason["contrast_with_neighbouring_reasons"]
        } == set(v2_by_code) - {code}


def test_catalog_v2_validator_has_no_human_wording_or_active_route() -> None:
    source = CONTRACT_V2_PATH.read_text(encoding="utf-8")
    catalog = _read_json(CATALOG_V2_PATH)

    assert "provider" in source
    assert "runtime" in source
    assert "Gate2FinancialSemanticV6ChoiceContractFactory" not in source
    assert "gate2_financial_evidence_decision" not in source
    for reason in catalog["reasons"]:
        for field in (
            "human_title",
            "meaning",
            "use_when",
            "do_not_use_when",
            "positive_example",
        ):
            assert reason[field] not in source


def test_catalog_v2_validator_import_surface_is_closed() -> None:
    tree = ast.parse(CONTRACT_V2_PATH.read_text(encoding="utf-8"))
    imports = {
        node.module.split(".", maxsplit=1)[0]
        if isinstance(node, ast.ImportFrom) and node.module
        else alias.name.split(".", maxsplit=1)[0]
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
        "hashlib",
        "json",
        "re",
        "typing",
    }
    dynamic_calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert dynamic_calls.isdisjoint({"__import__", "eval", "exec"})


@pytest.mark.parametrize(
    ("mutate", "error_code"),
    [
        (
            lambda value: value.update(runtime_activation=True),
            "decision_reason_catalog_v2_identity_invalid",
        ),
        (
            lambda value: value["predecessor"].update(
                semantic_integrity_sha256="0" * 64
            ),
            "decision_reason_catalog_v2_predecessor_invalid",
        ),
        (
            lambda value: value["reasons"][0].update(
                meaning="Changed predecessor human meaning is forbidden."
            ),
            "decision_reason_catalog_v2_predecessor_meaning_drift",
        ),
        (
            lambda value: value["reasons"][1]["selection_boundary"][
                "plausible_distinct_available_financial_type_count"
            ].update(maximum_inclusive=2),
            "decision_reason_catalog_v2_boundaries_invalid",
        ),
        (
            lambda value: value["reasons"][1][
                "contrast_with_neighbouring_reasons"
            ].pop(),
            "decision_reason_catalog_v2_contrasts_invalid",
        ),
        (
            lambda value: value.update(integrity_sha256="0" * 64),
            "decision_reason_catalog_v2_integrity_invalid",
        ),
    ],
)
def test_catalog_v2_tampering_fails_closed(mutate, error_code) -> None:
    module = _load_contract()
    catalog = _read_json(CATALOG_V2_PATH)
    factory = _factory(module, catalog)
    invalid = copy.deepcopy(catalog)
    mutate(invalid)

    with pytest.raises(
        module.Gate2FinancialDecisionReasonCatalogV2ContractError,
        match=error_code,
    ):
        factory.create(catalog=invalid)


def test_catalog_v2_rejects_self_consistent_predecessor_substitution() -> None:
    module = _load_contract()
    predecessor = _read_json(CATALOG_V1_PATH)
    candidate = _read_json(CATALOG_V2_PATH)
    predecessor["reasons"][0]["meaning"] = (
        "A self-consistent replacement predecessor must still be rejected."
    )
    _reseal(predecessor)
    candidate["predecessor"]["semantic_integrity_sha256"] = predecessor[
        "integrity_sha256"
    ]
    candidate["reasons"][0]["meaning"] = predecessor["reasons"][0]["meaning"]
    _reseal(candidate)

    with pytest.raises(
        module.Gate2FinancialDecisionReasonCatalogV2ContractError,
        match="decision_reason_catalog_v2_predecessor_invalid",
    ):
        module.Gate2FinancialDecisionReasonCatalogV2ContractFactory(
            predecessor_catalog=predecessor,
            candidate_catalog=candidate,
        )


def test_catalog_v2_rejects_self_consistent_added_code_rename() -> None:
    module = _load_contract()
    candidate = _read_json(CATALOG_V2_PATH)
    replacement = "renamed_single_type_reason"
    candidate["reasons"][1]["code"] = replacement
    for reason in candidate["reasons"]:
        for contrast in reason["contrast_with_neighbouring_reasons"]:
            if contrast["reason_code"] == NEW_REASON:
                contrast["reason_code"] = replacement
    _reseal(candidate)

    with pytest.raises(
        module.Gate2FinancialDecisionReasonCatalogV2ContractError,
        match="decision_reason_catalog_v2_added_reason_code_invalid",
    ):
        _factory(module, candidate)


def test_historical_catalog_family_decision_and_prompt_blobs_are_unchanged() -> None:
    for path, expected in EXPECTED_IMMUTABLE_GIT_BLOBS.items():
        assert hashlib.sha256(_git_blob(path)).hexdigest() == expected

    family = _read_json(FAMILY_V2_PATH)
    dependencies = {
        item["dependency_id"]: item for item in family["dependencies"]
    }
    assert dependencies[
        "broker_reports_gate2_financial_decision_reason_catalog"
    ]["semantic_version"] == "1.0.0"
    assert dependencies["broker_reports_financial_decision_contract"][
        "contract_identity"
    ] == "broker_reports_gate2_financial_evidence_decision_v1"
