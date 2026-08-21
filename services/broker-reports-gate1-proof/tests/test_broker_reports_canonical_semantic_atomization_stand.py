from __future__ import annotations

import copy
from pathlib import Path
import sys
import json

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SERVICE_ROOT / "scripts"
REPO_ROOT = SERVICE_ROOT.parents[1]
SAFE_RECEIPT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-20"
    / "BROKER_REPORTS_CANONICAL_SEMANTIC_ATOMIZATION_STAND.receipt.safe.json"
)
sys.path.insert(0, str(SCRIPT_DIR))

from qualify_canonical_semantic_atomization_stand import (  # noqa: E402
    RESPONSE_SCHEMA_VERSION,
    SemanticAtomizationStandError,
    _canonical_boundaries,
    _score_run,
    model_request,
    response_schema,
    validate_response,
    verdict,
)


def _batch() -> dict:
    return {
        "schema_version": "broker_reports_semantic_atomization_batch_v1",
        "blocks": [
            {
                "block_id": "b001",
                "block_kind": "table_row",
                "elements": [
                    {"source_ref": "t001", "literal": "Alpha. Beta."},
                    {"source_ref": "t002", "literal": "100"},
                ],
                "header_context": [{"source_ref": "t003", "literal": "Description"}],
            }
        ],
    }


def _refs_response() -> dict:
    return {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "atoms": [
            {
                "assertion_id": "a001",
                "block_id": "b001",
                "claim_refs": ["t001", "t002"],
                "context_refs": ["t003"],
                "audit_description": "One source assertion.",
            }
        ],
    }


def _span_response() -> dict:
    return {
        "schema_version": RESPONSE_SCHEMA_VERSION,
        "atoms": [
            {
                "assertion_id": "a001",
                "block_id": "b001",
                "claim_slices": [
                    {"source_ref": "t001", "literal_fragment": "Alpha."},
                    {"source_ref": "t002", "literal_fragment": "100"},
                ],
                "context_refs": ["t003"],
                "audit_description": "One source assertion.",
            }
        ],
    }


@pytest.mark.parametrize("variant", ["refs_only", "ref_spans"])
def test_schema_preserves_gate3_transport_classification_seam(variant: str) -> None:
    schema = response_schema(
        variant=variant,
        block_ids=["b001"],
        allowed_refs=["t001", "t002", "t003"],
    )

    assert schema["properties"]["atoms"]["items"] == {"$ref": "#/$defs/classification"}
    classification = schema["$defs"]["classification"]
    assert classification["additionalProperties"] is False
    assert classification["properties"]["assertion_id"]["pattern"] == ("^a[0-9]{3}$")
    assert "machine_code" not in str(schema)
    assert "financial_label" not in str(schema)


@pytest.mark.parametrize("variant", ["refs_only", "ref_spans"])
def test_request_has_one_frozen_three_message_atomization_contract(
    variant: str,
) -> None:
    schema = response_schema(
        variant=variant,
        block_ids=["b001"],
        allowed_refs=["t001", "t002", "t003"],
    )
    request = model_request(variant=variant, batch=_batch(), schema=schema)

    assert [message["role"] for message in request["messages"]] == [
        "system",
        "user",
        "user",
    ]
    assert request["response_format"]["json_schema"]["schema"] == schema
    assert "PURCHASE" not in str(request)
    assert "SALE" not in str(request)
    assert "COMMISSION" not in str(request)


def test_refs_validator_returns_terminal_machine_boundaries() -> None:
    result = validate_response(
        _refs_response(),
        variant="refs_only",
        batch=_batch(),
    )

    assert result["validation_status"] == "validated"
    assert result["atoms"][0]["claim_refs"] == ["t001", "t002"]
    assert result["atoms"][0]["context_refs"] == ["t003"]


def test_span_validator_accepts_only_exact_canonical_substrings() -> None:
    result = validate_response(
        _span_response(),
        variant="ref_spans",
        batch=_batch(),
    )
    assert result["validation_status"] == "validated"

    invalid = copy.deepcopy(_span_response())
    invalid["atoms"][0]["claim_slices"][0]["literal_fragment"] = "alpha"
    with pytest.raises(
        SemanticAtomizationStandError, match="atomization_claim_slice_invalid"
    ):
        validate_response(invalid, variant="ref_spans", batch=_batch())


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda value: value["atoms"][0].__setitem__("assertion_id", "a002"),
            "atomization_atom_id_sequence_invalid",
        ),
        (
            lambda value: value["atoms"][0]["claim_refs"].append("t003"),
            "atomization_claim_ref_invalid",
        ),
        (
            lambda value: value["atoms"][0]["context_refs"].append("t999"),
            "atomization_context_ref_invalid",
        ),
    ],
)
def test_refs_validator_fails_closed_without_repair(mutate, error: str) -> None:
    value = copy.deepcopy(_refs_response())
    mutate(value)

    with pytest.raises(SemanticAtomizationStandError, match=error):
        validate_response(value, variant="refs_only", batch=_batch())


def test_audit_description_does_not_change_machine_boundary() -> None:
    first = validate_response(_refs_response(), variant="refs_only", batch=_batch())[
        "atoms"
    ]
    changed = copy.deepcopy(_refs_response())
    changed["atoms"][0]["audit_description"] = "Different human wording."
    second = validate_response(changed, variant="refs_only", batch=_batch())["atoms"]

    assert _canonical_boundaries(first, variant="refs_only") == (
        _canonical_boundaries(second, variant="refs_only")
    )


def test_score_asserts_exact_atoms_and_claim_coverage_not_only_count() -> None:
    validated = validate_response(_refs_response(), variant="refs_only", batch=_batch())
    expected = _canonical_boundaries(validated["atoms"], variant="refs_only")

    score = _score_run(
        ordinal=1,
        variant="refs_only",
        validated=validated,
        expected=expected,
        execution_metadata={},
        provider_submissions=1,
    )

    assert score["atoms"] == 1
    assert score["exact_atoms_correct"] == 1
    assert score["missing_atoms"] == 0
    assert score["extra_atoms"] == 0
    assert score["claim_members_missing"] == 0
    assert score["claim_members_extra"] == 0
    assert score["provider_submissions"] == 1


def test_verdict_is_context_bound_even_when_local_spans_are_perfect() -> None:
    perfect = {
        "exact_boundary_repeatability": True,
        "source_fidelity_exact": True,
        "source_claim_coverage_complete": True,
    }
    imperfect = {
        "exact_boundary_repeatability": False,
        "source_fidelity_exact": False,
        "source_claim_coverage_complete": False,
    }

    assert verdict(variants={"refs_only": imperfect, "ref_spans": perfect}) == (
        "ATOMIZATION_PROMISING_BUT_CONTEXT_BOUND"
    )
    assert verdict(variants={"refs_only": imperfect, "ref_spans": imperfect}) == (
        "ATOM_BOUNDARIES_NOT_REPEATABLE"
    )


def test_research_stand_cannot_mutate_pipeline_or_retry_semantics() -> None:
    source = (SCRIPT_DIR / "qualify_canonical_semantic_atomization_stand.py").read_text(
        encoding="utf-8"
    )

    assert "Gate3FinancialAnnotationsPersistenceFactory" not in source
    assert "Gate4FinancialCase" not in source
    assert "Gate5" not in source
    assert '"retry_count": 0' in source
    assert '"repair_count": 0' in source
    assert '"best_of_n": False' in source
    assert '"production_changed": False' in source
    assert '"classification_passes": 0' in source
    assert "for ordinal in range(1, RUNS + 1)" in source


def test_safe_receipt_records_honest_negative_terminal() -> None:
    receipt = json.loads(SAFE_RECEIPT.read_text(encoding="utf-8"))

    assert receipt["status"] == ("SEMANTIC_ATOMIZATION_DOES_NOT_ADD_USEFUL_BOUNDARY")
    assert receipt["source_truth_blocks"] == 6
    assert receipt["source_truth_atoms"] == 9
    assert receipt["provider_submissions"] == 6
    assert receipt["retry_count"] == 0
    assert receipt["repair_count"] == 0
    assert receipt["best_of_n"] is False
    assert receipt["classification_passes"] == 0
    assert receipt["production_changed"] is False
    refs = receipt["variants"]["refs_only"]
    assert refs["validated_runs"] == 3
    assert refs["exact_boundary_repeatability"] is True
    assert refs["source_fidelity_exact"] is False
    assert [run["atoms"] for run in refs["runs"]] == [5, 5, 5]
    spans = receipt["variants"]["ref_spans"]
    assert spans["validated_runs"] == 1
    assert spans["exact_boundary_repeatability"] is False
