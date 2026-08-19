"""G5.71 semantic-adaptation architecture-search guard tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image
import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "live_g571_metadata_semantic_search.py"
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SERVICE_ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("live_g571", SCRIPT_PATH)
assert spec and spec.loader
g571 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g571)


def _decision(
    decision: str,
    literal: str,
    *,
    fact_type: str | None,
    label: str | None,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, object]:
    return {
        "decision": decision,
        "fact_type": fact_type,
        "source_target_alias": "m001",
        "role_evidence_target_alias": "m001",
        "role_label_literal": label,
        "source_literal": literal,
        "period_start_literal": start,
        "period_end_literal": end,
    }


def _truth(fact_id: str, fact_type: str, literal: str) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "fact_type": fact_type,
        "source_literal": literal,
        "period_start_literal": None,
        "period_end_literal": None,
    }


def _output(*decisions: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": g571.DECISION_SCHEMA_VERSION,
        "decisions": list(decisions),
    }


def test_model_view_preserves_visual_input_and_frozen_fact_types() -> None:
    view = g571.semantic_model_view()

    assert view["input"] == {
        "kind": "VISUAL_CROP",
        "region_alias": "m001",
        "flattened_canonical_text": False,
        "ocr_dump": False,
        "parser_reconstruction": False,
    }
    assert view["broker_hints"] == []
    assert tuple(view["contract"]["allowed_fact_types"]) == tuple(
        g571.g570.GATE3_MINIMAL_METADATA_FACT_TYPES
    )
    assert view["contract"]["contract_version"] == "1.0.0"
    serialized = json.dumps(view, ensure_ascii=False).lower()
    assert "case_b" not in serialized
    assert "case_f" not in serialized


def test_existing_factory_is_required_and_direct_transport_is_forbidden() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "PdfGridExperimentProviderFactory(" in source
    assert "PdfDualVlmFactProviderFactory(" in source
    assert ").create_for_openwebui(request)" in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
    assert "requests." not in source
    assert "urlopen(" not in source
    assert "generateContent" not in source
    assert "x-goog-api-key" not in source


def test_existing_openai_candidate_reuses_g570_contract_without_prompt_change() -> None:
    candidate = "EXISTING_OPENAI_VLM_BASELINE_CONTRACT"

    assert g571.candidate_model_view(candidate) == g571.g570.visual_metadata_model_view()
    assert g571.candidate_response_schema(candidate) == (
        g571.metadata_proposal_response_schema()
    )


def test_decision_schema_adds_no_published_metadata_fact_type() -> None:
    schema = g571.semantic_decision_response_schema()
    fact_type = schema["properties"]["decisions"]["items"]["properties"][
        "fact_type"
    ]
    allowed = fact_type["anyOf"][0]["enum"]

    assert tuple(allowed) == tuple(g571.g570.GATE3_MINIMAL_METADATA_FACT_TYPES)
    assert "NO_CONTRACT_MATCH" not in allowed


def test_validator_accepts_explicit_contract_and_no_match_terminals() -> None:
    value = _output(
        _decision(
            "CONTRACT_FACT",
            "Иван Иванов",
            fact_type="PARTY_NAME",
            label="Клиент",
        ),
        _decision(
            "NO_CONTRACT_MATCH",
            "SYNTHETIC-7",
            fact_type=None,
            label="Внутренняя метка",
        ),
    )

    assert g571.validate_semantic_decisions(value) == []


def test_projection_discards_no_match_without_repairing_typed_facts() -> None:
    value = _output(
        _decision(
            "CONTRACT_FACT",
            "Иван Иванов",
            fact_type="PARTY_NAME",
            label="Клиент",
        ),
        _decision(
            "NO_CONTRACT_MATCH",
            "SYNTHETIC-7",
            fact_type=None,
            label="Внутренняя метка",
        ),
    )

    proposal = g571.project_contract_proposal(value)

    assert proposal == {
        "schema_version": "broker_reports_llm_metadata_proposal_v2",
        "facts": [
            {
                "fact_type": "PARTY_NAME",
                "source_target_alias": "m001",
                "role_evidence_target_alias": "m001",
                "source_literal": "Иван Иванов",
                "period_start_literal": None,
                "period_end_literal": None,
            }
        ],
    }


def test_evaluator_requires_contract_truth_and_known_no_match_observation() -> None:
    value = _output(
        _decision(
            "CONTRACT_FACT",
            "Иван Иванов",
            fact_type="PARTY_NAME",
            label="Клиент",
        ),
        _decision(
            "NO_CONTRACT_MATCH",
            "SYNTHETIC-7",
            fact_type=None,
            label="Внутренняя метка",
        ),
    )
    metrics, _details = g571.evaluate_semantic_decisions(
        value,
        truth=[_truth("party", "PARTY_NAME", "Иван Иванов")],
        non_contract_observations=[
            {
                "observation_id": "outside-contract",
                "semantic_role": "OUTSIDE_CONTRACT",
                "source_literal": "SYNTHETIC-7",
            }
        ],
        human_transcription=(
            "Клиент Иван Иванов Внутренняя метка SYNTHETIC-7"
        ),
    )

    assert metrics == {
        "correct": 1,
        "missed": 0,
        "wrong_role": 0,
        "extra_fact": 0,
        "wrong_value_boundary": 0,
        "invented_value": 0,
        "no_match_correct": 1,
        "no_match_missed": 0,
        "no_match_wrong": 0,
        "no_match_extra": 0,
        "no_match_invented": 0,
    }


def test_evaluator_preserves_wrong_role_failure_instead_of_hiding_it() -> None:
    value = _output(
        _decision(
            "CONTRACT_FACT",
            "SYNTHETIC-7",
            fact_type="ACCOUNT_IDENTIFIER",
            label="Внутренняя метка",
        )
    )
    metrics, _details = g571.evaluate_semantic_decisions(
        value,
        truth=[],
        non_contract_observations=[
            {
                "observation_id": "outside-contract",
                "semantic_role": "OUTSIDE_CONTRACT",
                "source_literal": "SYNTHETIC-7",
            }
        ],
        human_transcription="Внутренняя метка SYNTHETIC-7",
    )

    assert metrics["wrong_role"] == 1
    assert metrics["no_match_missed"] == 1


def test_freeze_binds_candidate_visual_truth_and_single_call(tmp_path: Path) -> None:
    crop = tmp_path / "case.png"
    Image.new("RGB", (16, 10), "white").save(crop)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")
    case = {
        "case_id": "case_c",
        "role": "CLEAN_SUCCESS_CONTROL",
        "crop_path": "case.png",
        "crop_sha256": g571.g570._sha256_file(crop),
        "crop_width": 16,
        "crop_height": 10,
        "source_pdf_path": "source.pdf",
        "source_pdf_sha256": g571.g570._sha256_file(source),
        "truth_authority": "VISUAL_HUMAN_TRUTH",
        "human_transcription": "Клиент Иван Иванов",
        "truth": [_truth("party", "PARTY_NAME", "Иван Иванов")],
        "non_contract_observations": [],
    }
    freeze = _freeze([case])
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(freeze, ensure_ascii=False), encoding="utf-8")

    cases = g571.validate_freeze(freeze, freeze_path=freeze_path)

    assert list(cases) == ["case_c"]
    assert cases["case_c"]["crop_path"] == crop.resolve()
    assert freeze["provider_calls_per_document"] == 1


def test_freeze_rejects_semantic_magic(tmp_path: Path) -> None:
    freeze = _freeze([])
    freeze["broker_hints"] = ["forbidden"]

    with pytest.raises(g571.G571SearchError) as captured:
        g571.validate_freeze(freeze, freeze_path=tmp_path / "freeze.json")

    assert captured.value.code == "g571_freeze_contract_invalid"


def test_freeze_accepts_existing_openai_visual_owner_candidate(tmp_path: Path) -> None:
    crop = tmp_path / "case.png"
    Image.new("RGB", (16, 10), "white").save(crop)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")
    case = {
        "case_id": "case_c",
        "role": "CLEAN_SUCCESS_CONTROL",
        "crop_path": "case.png",
        "crop_sha256": g571.g570._sha256_file(crop),
        "crop_width": 16,
        "crop_height": 10,
        "source_pdf_path": "source.pdf",
        "source_pdf_sha256": g571.g570._sha256_file(source),
        "truth_authority": "VISUAL_HUMAN_TRUTH",
        "human_transcription": "Клиент Иван Иванов",
        "truth": [_truth("party", "PARTY_NAME", "Иван Иванов")],
        "non_contract_observations": [],
    }
    freeze = _freeze([case])
    candidate = "EXISTING_OPENAI_VLM_BASELINE_CONTRACT"
    freeze.update(
        {
            "hypothesis_id": "H4_MODEL_CAPABILITY_FLOOR",
            "candidate_id": candidate,
            "instruction_version": g571.g570.INSTRUCTION_VERSION,
            "model_view_sha256": g571.g570._sha256_json(
                g571.candidate_model_view(candidate)
            ),
            "response_schema_sha256": g571.g570._sha256_json(
                g571.candidate_response_schema(candidate)
            ),
            "provider_profile": "openai_gpt",
            "model_id": "gpt-5.6-sol",
        }
    )
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(freeze, ensure_ascii=False), encoding="utf-8")

    cases = g571.validate_freeze(freeze, freeze_path=freeze_path)

    assert list(cases) == ["case_c"]


def _freeze(cases: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": g571.FREEZE_SCHEMA_VERSION,
        "goal": "G5.71",
        "phase": "development",
        "hypothesis_id": "H3_POSITIVE_ONLY_SCHEMA_COERCION",
        "candidate_id": "EXPLICIT_NO_CONTRACT_MATCH_ONE_CALL",
        "solution_frozen": False,
        "contract_version": "1.0.0",
        "instruction_version": g571.INSTRUCTION_VERSION,
        "model_view_sha256": g571.g570._sha256_json(g571.semantic_model_view()),
        "response_schema_sha256": g571.g570._sha256_json(
            g571.semantic_decision_response_schema()
        ),
        "provider_profile": "google_gemini",
        "model_id": "models/gemini-3.5-flash",
        "maximum_output_tokens": 2048,
        "maximum_counted_input_tokens": 8000,
        "thinking_level": "minimal",
        "provider_calls_per_document": 1,
        "broker_hints": [],
        "regex_semantics": False,
        "prompt_blacklist": False,
        "fixed_layout_semantics": False,
        "prompt_tuning_after_freeze": False,
        "product_activation": False,
        "cases": cases,
        "runs": [
            {"run_id": "case_c_r1", "case_id": "case_c", "purpose": "development"}
        ]
        if cases
        else [],
    }
