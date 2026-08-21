from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SERVICE_ROOT / "scripts"
REPO_ROOT = SERVICE_ROOT.parents[1]
SAFE_RECEIPT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-20"
    / "BROKER_REPORTS_GATE3_MINIMAL_CLASSIFIER_STAND.receipt.safe.json"
)
sys.path.insert(0, str(SCRIPT_DIR))

from qualify_gate3_minimal_classifier_stand import (  # noqa: E402
    MACHINE_CODE_TO_LABEL,
    RESPONSE_SCHEMA_VERSION,
    MinimalClassifierStandError,
    machine_code_catalog,
    _model_request,
    response_schema,
    validate_response,
    verdict,
)


def _valid_response() -> dict:
    return {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "decisions": [
            {"assertion_id": "o001", "machine_code": "F01"},
            {"assertion_id": "o002", "machine_code": "F00"},
        ],
    }


def test_catalog_is_only_machine_ids_for_the_current_dictionary() -> None:
    catalog = machine_code_catalog()

    assert catalog[0]["machine_code"] == "F00"
    assert catalog[0]["existing_financial_label"] is None
    assert {
        item["existing_financial_label"]
        for item in catalog[1:]
    } == set(MACHINE_CODE_TO_LABEL.values())
    assert len(catalog) == len(MACHINE_CODE_TO_LABEL) + 1


def test_response_schema_requires_one_closed_code_per_declared_object() -> None:
    schema = response_schema(["o001", "o002"])
    decisions = schema["properties"]["decisions"]

    assert decisions["minItems"] == 2
    assert decisions["maxItems"] == 2
    classification = schema["$defs"]["classification"]
    assert decisions["items"] == {"$ref": "#/$defs/classification"}
    assert classification["additionalProperties"] is False
    assert classification["properties"]["assertion_id"]["pattern"] == (
        "^o[0-9]{3}$"
    )
    assert set(
        classification["properties"]["machine_code"]["enum"]
    ) == {"F00", *MACHINE_CODE_TO_LABEL}


def test_model_request_uses_the_existing_three_part_gate3_transport_shape() -> None:
    schema = response_schema(["o001"])
    request = _model_request(
        batch={"schema_version": "test", "objects": [{"object_id": "o001"}]},
        schema=schema,
    )

    assert [item["role"] for item in request["messages"]] == [
        "system",
        "user",
        "user",
    ]
    assert all(item["content"] for item in request["messages"])
    assert request["response_format"]["json_schema"]["schema"] == schema


def test_validator_returns_terminal_exact_ordered_coverage() -> None:
    result = validate_response(_valid_response(), object_ids=["o001", "o002"])

    assert result["validation_status"] == "validated"
    assert result["explicit_coverage"] == 2
    assert result["decisions"] == [
        {"object_id": "o001", "machine_code": "F01"},
        {"object_id": "o002", "machine_code": "F00"},
    ]


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda value: value["decisions"].pop(),
            "classifier_response_coverage_invalid",
        ),
        (
            lambda value: value["decisions"].reverse(),
            "classifier_response_order_invalid",
        ),
        (
            lambda value: value["decisions"].__setitem__(
                1, {"assertion_id": "o001", "machine_code": "F00"}
            ),
            "classifier_response_object_duplicate",
        ),
        (
            lambda value: value["decisions"][0].__setitem__(
                "machine_code", "FREE_TEXT"
            ),
            "classifier_response_contract_invalid",
        ),
    ],
)
def test_validator_fails_closed_without_repair(mutate, error: str) -> None:
    value = copy.deepcopy(_valid_response())
    mutate(value)

    with pytest.raises(MinimalClassifierStandError, match=error):
        validate_response(value, object_ids=["o001", "o002"])


def test_verdict_requires_all_three_exact_and_fully_correct_runs() -> None:
    assert verdict(
        candidate_hashes=["same", "same", "same"],
        candidate_correct=[24, 24, 24],
        objects_total=24,
        baseline_correct=[21, 15, 18],
    ) == "CLOSED_MACHINE_CLASSIFIER_REPEATABILITY_PROVEN"
    assert verdict(
        candidate_hashes=["a", "b", "a"],
        candidate_correct=[24, 23, 24],
        objects_total=24,
        baseline_correct=[21, 15, 18],
    ) == "CLOSED_MACHINE_CLASSIFIER_PROMISING"


def test_research_script_cannot_become_a_production_or_retry_route() -> None:
    source = (SCRIPT_DIR / "qualify_gate3_minimal_classifier_stand.py").read_text(
        encoding="utf-8"
    )

    assert "Gate3FinancialAnnotationsPersistenceFactory" not in source
    assert "Gate4" not in source
    assert "Gate5" not in source
    assert "range(1, RUNS + 1)" in source
    assert '"retry_count": 0' in source
    assert '"repair_count": 0' in source
    assert '"best_of_n": False' in source
    assert '"production_changed": False' in source


def test_safe_receipt_records_the_honest_promising_terminal() -> None:
    receipt = json.loads(SAFE_RECEIPT.read_text(encoding="utf-8"))

    assert receipt["status"] == "CLOSED_MACHINE_CLASSIFIER_PROMISING"
    assert receipt["terminals"] == [
        "CURRENT_GATE3_CONTEXT_EXCESSIVE_FREEDOM_PROVEN",
        "CLOSED_MACHINE_CLASSIFIER_PROMISING",
    ]
    assert receipt["production_changed"] is False
    assert receipt["source_truth_objects"] == 24
    assert receipt["comparison"]["current_source_truth_correct"] == [21, 15, 18]
    assert receipt["comparison"]["candidate_source_truth_correct"] == [22, 22, 22]
    assert receipt["comparison"]["current_model_explicit_answer_counts"] == [
        17,
        9,
        14,
    ]
    assert receipt["comparison"]["candidate_explicit_answer_counts"] == [
        24,
        24,
        24,
    ]
    assert receipt["closed_classifier"]["exact_mapping_repeatability"] is True
    assert receipt["closed_classifier"]["explicit_coverage_each_run"] is True
    assert receipt["closed_classifier"]["omitted_objects"] == 0
    assert receipt["provider_submissions"] == 3
    assert receipt["retry_count"] == 0
    assert receipt["repair_count"] == 0
    assert receipt["best_of_n"] is False
