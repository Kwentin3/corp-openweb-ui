"""G5.67 positive-role contract and single-holdout replay guards."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

from broker_reports_gate1.gate3_llm_metadata_adapter import (
    GATE3_LLM_METADATA_INSTRUCTION,
    GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION,
    validate_metadata_proposal,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "live_g567_single_holdout_replay.py"
QUALIFIER_PATH = SERVICE_ROOT / "scripts" / "qualify_g567_positive_role_evidence.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("g567_replay", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G567 = _load_script()


def _load_qualifier():
    spec = importlib.util.spec_from_file_location("g567_qualifier", QUALIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G567_QUALIFIER = _load_qualifier()


def test_positive_role_contract_is_one_versioned_boundary() -> None:
    assert GATE3_LLM_METADATA_PROPOSAL_SCHEMA_VERSION == (
        "broker_reports_llm_metadata_proposal_v2"
    )
    assert "positive source evidence for both its value and its semantic role" in (
        GATE3_LLM_METADATA_INSTRUCTION
    )
    assert "role_evidence_target_alias" in GATE3_LLM_METADATA_INSTRUCTION
    assert "trading code" not in GATE3_LLM_METADATA_INSTRUCTION.lower()
    assert "client code" not in GATE3_LLM_METADATA_INSTRUCTION.lower()


def test_validator_contains_no_human_language_semantic_branch() -> None:
    source = inspect.getsource(validate_metadata_proposal).lower()

    for forbidden_semantic_literal in (
        '"trading"',
        '"client"',
        '"broker"',
        '"agreement"',
        '"synonym"',
    ):
        assert forbidden_semantic_literal not in source


def test_single_holdout_harness_is_factory_routed_and_terminal() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "Gate3LlmMetadataAdapterFactory(" in source
    assert "Gate2StructuredModelClientFactory(" in source
    assert "exactly_one_g567_holdout_submission_required" in source
    assert '"retries": 0' in source
    assert '"best_of_n": False' in source
    assert '"manual_output_repair": False' in source


def test_single_holdout_harness_preserves_typed_provider_error() -> None:
    error = RuntimeError("typed provider error")
    error.code = "gate2_model_unavailable"  # type: ignore[attr-defined]
    error.failure_class = "provider_error_response"  # type: ignore[attr-defined]
    error.raw_output = {"detail": "Model not found", "status_code": 400}  # type: ignore[attr-defined]

    receipt = G567._error_receipt(error)

    assert receipt["code"] == "gate2_model_unavailable"
    assert receipt["failure_class"] == "provider_error_response"
    assert receipt["raw_output"] == {
        "detail": "Model not found",
        "status_code": 400,
    }


def test_qualifier_checks_role_binding_physical_identity() -> None:
    fact = {
        "source_binding": {
            "document_id": "doc-1",
            "canonical_version_id": "can-1",
            "role_evidence_binding": {
                "document_id": "doc-1",
                "canonical_version_id": "can-1",
                "source_target_alias": "m002",
                "source_refs": ["prov-1"],
            },
        }
    }
    registry = {
        "targets": {
            "m002": {
                "document_id": "doc-1",
                "canonical_version_id": "can-1",
            }
        }
    }

    assert G567_QUALIFIER._role_binding_failures(
        fact=fact, registry=registry
    ) == []

    registry["targets"]["m002"]["canonical_version_id"] = "can-other"
    assert G567_QUALIFIER._role_binding_failures(
        fact=fact, registry=registry
    ) == ["ROLE_EVIDENCE_CANONICAL_BINDING_MISMATCH"]
