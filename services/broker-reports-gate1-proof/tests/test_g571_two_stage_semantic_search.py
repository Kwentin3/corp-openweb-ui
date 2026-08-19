"""G5.71 two-stage semantic architecture-search guard tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image
import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "live_g571_two_stage_semantic_search.py"
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SERVICE_ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("live_g571_two_stage", SCRIPT_PATH)
assert spec and spec.loader
two_stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(two_stage)


def test_stage1_is_visual_source_only_and_cannot_see_metadata_contract() -> None:
    view = two_stage.assertion_model_view()

    assert view["domain"] == "VISUAL_SOURCE_ASSERTION_TRANSCRIPTION"
    assert view["metadata_contract_visible"] is False
    assert view["broker_hints"] == []
    assert view["input"]["flattened_canonical_text"] is False
    assert "allowed_fact_types" not in json.dumps(view)


def test_stage2_owns_only_semantic_mapping_to_frozen_fact_types() -> None:
    view = two_stage.classifier_model_view_template()

    assert view["domain"] == "METADATA_SEMANTIC_ADAPTER"
    assert tuple(view["contract"]["allowed_fact_types"]) == tuple(
        two_stage.g570.GATE3_MINIMAL_METADATA_FACT_TYPES
    )
    assert view["contract"]["contract_version"] == "1.0.0"
    assert view["broker_hints"] == []


def test_factory_first_route_has_no_direct_provider_transport() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "PdfGridExperimentProviderFactory(" in source
    assert "PdfDualVlmFactProviderFactory(" in source
    assert ").create_for_openwebui(request)" in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
    assert "requests." not in source
    assert "urlopen(" not in source
    assert "x-goog-api-key" not in source
    assert "authorization" not in source.lower()


def test_assertion_validator_accepts_source_literals_without_machine_roles() -> None:
    value = {
        "schema_version": two_stage.ASSERTION_SCHEMA_VERSION,
        "assertions": [
            {
                "role_label_literal": "Метка",
                "value_literal": "SYNTHETIC-1",
                "period_start_literal": None,
                "period_end_literal": None,
            }
        ],
    }

    assert two_stage.validate_assertions(value) == []
    assert "fact_type" not in json.dumps(value)


def test_assertion_validator_rejects_partial_period_and_duplicate() -> None:
    assertion = {
        "role_label_literal": "Период",
        "value_literal": "2025",
        "period_start_literal": "01.01.2025",
        "period_end_literal": None,
    }
    partial = {
        "schema_version": two_stage.ASSERTION_SCHEMA_VERSION,
        "assertions": [assertion],
    }
    duplicate = {
        "schema_version": two_stage.ASSERTION_SCHEMA_VERSION,
        "assertions": [assertion, dict(assertion)],
    }

    partial_errors = two_stage.validate_assertions(partial)
    duplicate_errors = two_stage.validate_assertions(duplicate)

    assert "assertion_0_partial_period_boundary" in partial_errors
    assert any("non-unique elements" in item for item in duplicate_errors)


def test_run_evaluator_preserves_wrong_role_terminal() -> None:
    case = {
        "truth": [],
        "non_contract_observations": [
            {
                "observation_id": "outside",
                "semantic_role": "OUTSIDE_CONTRACT",
                "source_literal": "SYNTHETIC-1",
            }
        ],
        "human_transcription": "Метка SYNTHETIC-1",
        "crop_sha256": "a" * 64,
    }
    proposal = {
        "schema_version": "broker_reports_llm_metadata_proposal_v2",
        "facts": [
            {
                "fact_type": "ACCOUNT_IDENTIFIER",
                "source_target_alias": "m001",
                "role_evidence_target_alias": "m001",
                "source_literal": "SYNTHETIC-1",
                "period_start_literal": None,
                "period_end_literal": None,
            }
        ],
    }
    run = two_stage._build_run(
        scheduled={"run_id": "r1", "case_id": "case", "purpose": "development"},
        case=case,
        assertions={"schema_version": two_stage.ASSERTION_SCHEMA_VERSION, "assertions": []},
        stage1_response={"attempt": {}, "json_output": {}},
        stage1_errors=[],
        stage2_response={"attempt": {}, "json_output": proposal},
    )

    assert run["metrics"]["wrong_role"] == 1
    assert run["semantic_exact"] is False


def test_freeze_binds_two_calls_and_domain_contracts(tmp_path: Path) -> None:
    crop = tmp_path / "case.png"
    Image.new("RGB", (20, 12), "white").save(crop)
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n%%EOF\n")
    freeze = _freeze(
        [
            {
                "case_id": "case_c",
                "role": "CLEAN_SUCCESS_CONTROL",
                "crop_path": "case.png",
                "crop_sha256": two_stage.g570._sha256_file(crop),
                "crop_width": 20,
                "crop_height": 12,
                "source_pdf_path": "source.pdf",
                "source_pdf_sha256": two_stage.g570._sha256_file(source),
                "truth_authority": "VISUAL_HUMAN_TRUTH",
                "human_transcription": "Клиент Иван Иванов",
                "truth": [
                    {
                        "fact_id": "party",
                        "fact_type": "PARTY_NAME",
                        "source_literal": "Иван Иванов",
                        "period_start_literal": None,
                        "period_end_literal": None,
                    }
                ],
                "non_contract_observations": [],
            }
        ]
    )
    path = tmp_path / "freeze.json"
    path.write_text(json.dumps(freeze, ensure_ascii=False), encoding="utf-8")

    cases = two_stage.validate_freeze(freeze, freeze_path=path)

    assert list(cases) == ["case_c"]
    assert freeze["provider_calls_per_document"] == 2


def test_freeze_rejects_broker_hints(tmp_path: Path) -> None:
    freeze = _freeze([])
    freeze["broker_hints"] = ["forbidden"]

    with pytest.raises(two_stage.G571TwoStageError) as captured:
        two_stage.validate_freeze(freeze, freeze_path=tmp_path / "freeze.json")

    assert captured.value.code == "g571_two_stage_freeze_contract_invalid"


def _freeze(cases: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema_version": two_stage.FREEZE_SCHEMA_VERSION,
        "goal": "G5.71",
        "phase": "development",
        "hypothesis_id": "H5_JOINT_EXTRACTION_CLASSIFICATION_OVERLOAD",
        "candidate_id": "VISUAL_ASSERTIONS_THEN_SEMANTIC_CLASSIFICATION",
        "solution_frozen": False,
        "contract_version": "1.0.0",
        "assertion_instruction_version": two_stage.ASSERTION_INSTRUCTION_VERSION,
        "classifier_instruction_version": two_stage.CLASSIFIER_INSTRUCTION_VERSION,
        "assertion_model_view_sha256": two_stage.g570._sha256_json(
            two_stage.assertion_model_view()
        ),
        "assertion_response_schema_sha256": two_stage.g570._sha256_json(
            two_stage.assertion_response_schema()
        ),
        "classifier_model_view_template_sha256": two_stage.g570._sha256_json(
            two_stage.classifier_model_view_template()
        ),
        "published_response_schema_sha256": two_stage.g570._sha256_json(
            two_stage.metadata_proposal_response_schema()
        ),
        "stage1_provider_profile": "google_gemini",
        "stage1_model_id": "models/gemini-3.5-flash",
        "stage2_provider_profile": "openai_gpt",
        "stage2_model_id": "gpt-5.6-sol",
        "maximum_output_tokens": 4096,
        "maximum_counted_input_tokens": 8000,
        "provider_calls_per_document": 2,
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
