"""G5.70 VLM-first metadata microstand guard tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from PIL import Image
import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "live_g570_vlm_metadata_microstand.py"
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SERVICE_ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("live_g570", SCRIPT_PATH)
assert spec and spec.loader
g570 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g570)


def _fact(
    fact_type: str,
    literal: str,
    *,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, object]:
    return {
        "fact_type": fact_type,
        "source_target_alias": "m001",
        "role_evidence_target_alias": "m001",
        "source_literal": literal,
        "period_start_literal": start,
        "period_end_literal": end,
    }


def _truth(
    fact_id: str,
    fact_type: str,
    literal: str,
    *,
    start: str | None = None,
    end: str | None = None,
) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "fact_type": fact_type,
        "source_literal": literal,
        "period_start_literal": start,
        "period_end_literal": end,
    }


def test_model_view_is_one_visual_contract_without_case_or_broker_hints() -> None:
    view = g570.visual_metadata_model_view()

    assert view["input"] == {
        "kind": "VISUAL_CROP",
        "region_alias": "m001",
        "flattened_canonical_text": False,
        "ocr_dump": False,
        "parser_reconstruction": False,
    }
    assert view["broker_hints"] == []
    assert set(view["contract"]["allowed_fact_types"]) == set(
        g570.GATE3_MINIMAL_METADATA_FACT_TYPES
    )
    serialized = json.dumps(view, ensure_ascii=False).lower()
    assert "case_b" not in serialized
    assert "case_f" not in serialized
    assert "bcs" not in serialized
    assert "client code" not in serialized


def test_existing_image_provider_factory_is_required_and_direct_transport_forbidden() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "PdfGridExperimentProviderFactory(" in source
    assert ").create_for_openwebui(request)" in source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
    assert "requests." not in source
    assert "urlopen(" not in source
    assert "generateContent" not in source
    assert "x-goog-api-key" not in source
    assert "retry" not in source.lower().split("def main", 1)[1].split(
        "def visual_metadata_model_view", 1
    )[0]


def test_visual_proposal_validator_accepts_terminal_exact_contract() -> None:
    value = {
        "schema_version": "broker_reports_llm_metadata_proposal_v2",
        "facts": [
            _fact("PARTY_NAME", "Anna Kurpitko"),
            _fact(
                "STATEMENT_PERIOD",
                "с 01.01.2025 по 31.12.2025",
                start="01.01.2025",
                end="31.12.2025",
            ),
        ],
    }

    assert g570.validate_visual_proposal(value) == []


def test_visual_proposal_validator_rejects_non_crop_alias_and_period_shape() -> None:
    value = {
        "schema_version": "broker_reports_llm_metadata_proposal_v2",
        "facts": [
            {
                **_fact("ACCOUNT_IDENTIFIER", "TF1467223"),
                "source_target_alias": "m002",
                "period_start_literal": "2025-01-01",
            }
        ],
    }

    errors = g570.validate_visual_proposal(value)

    assert "fact_0_source_alias_not_crop" in errors
    assert "fact_0_non_period_boundaries_present" in errors


def test_evaluator_counts_correct_missed_and_wrong_role_without_repair() -> None:
    value = {
        "schema_version": "broker_reports_llm_metadata_proposal_v2",
        "facts": [
            _fact("PARTY_NAME", "Anna Kurpitko"),
            _fact("ACCOUNT_IDENTIFIER", "TF1467223"),
        ],
    }
    truth = [_truth("party", "PARTY_NAME", "Anna Kurpitko")]
    observations = [
        {
            "observation_id": "client-code",
            "semantic_role": "CLIENT_CODE_OUTSIDE_CONTRACT",
            "source_literal": "TF1467223",
        }
    ]

    metrics, details = g570.evaluate_visual_proposal(
        value,
        truth=truth,
        non_contract_observations=observations,
        human_transcription="Клиент Anna Kurpitko Код клиента TF1467223",
    )

    assert metrics == {
        "correct": 1,
        "missed": 0,
        "wrong_role": 1,
        "extra_fact": 0,
        "wrong_value_boundary": 0,
        "invented_value": 0,
    }
    assert details["wrong_role"] == [
        {
            "proposal_index": 1,
            "proposed_fact_type": "ACCOUNT_IDENTIFIER",
            "visible_semantic_role": "CLIENT_CODE_OUTSIDE_CONTRACT",
        }
    ]


def test_evaluator_separates_wrong_boundary_extra_and_invented() -> None:
    value = {
        "schema_version": "broker_reports_llm_metadata_proposal_v2",
        "facts": [
            _fact("PARTY_NAME", "Клиент: Иван Иванов"),
            _fact("DOCUMENT_DATE", "2024-03-07"),
            _fact("ACCOUNT_IDENTIFIER", "INVENTED-42"),
        ],
    }
    truth = [_truth("party", "PARTY_NAME", "Иван Иванов")]

    metrics, _details = g570.evaluate_visual_proposal(
        value,
        truth=truth,
        non_contract_observations=[],
        human_transcription="Клиент: Иван Иванов Дата заключения договора 2024-03-07",
    )

    assert metrics == {
        "correct": 0,
        "missed": 1,
        "wrong_role": 0,
        "extra_fact": 1,
        "wrong_value_boundary": 1,
        "invented_value": 1,
    }


def test_freeze_binds_crop_truth_prompt_schema_and_single_shot_schedule(
    tmp_path: Path,
) -> None:
    crop = tmp_path / "case.png"
    Image.new("RGB", (12, 8), "white").save(crop)
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
    freeze = {
        "schema_version": g570.FREEZE_SCHEMA_VERSION,
        "goal": "G5.70",
        "phase": "development_initial",
        "contract_version": g570.GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "instruction_version": g570.INSTRUCTION_VERSION,
        "model_view_sha256": g570._sha256_json(g570.visual_metadata_model_view()),
        "response_schema_sha256": g570._sha256_json(
            g570.metadata_proposal_response_schema()
        ),
        "provider_profile": "google_gemini",
        "model_id": "models/gemini-3.5-flash",
        "maximum_output_tokens": 2048,
        "maximum_counted_input_tokens": 8000,
        "thinking_level": "minimal",
        "broker_hints": [],
        "prompt_tuning_after_freeze": False,
        "product_activation": False,
        "cases": [
            {
                "case_id": "case_c",
                "role": "CLEAN_SUCCESS_CONTROL",
                "crop_path": "case.png",
                "crop_sha256": g570._sha256_file(crop),
                "crop_width": 12,
                "crop_height": 8,
                "source_pdf_path": "source.pdf",
                "source_pdf_sha256": g570._sha256_file(source_pdf),
                "truth_authority": "VISUAL_HUMAN_TRUTH",
                "human_transcription": "Клиент Иван Иванов",
                "truth": [_truth("party", "PARTY_NAME", "Иван Иванов")],
                "non_contract_observations": [],
            }
        ],
        "runs": [
            {"run_id": "case_c_initial", "case_id": "case_c", "purpose": "initial"}
        ],
    }
    freeze_path = tmp_path / "freeze.json"
    freeze_path.write_text(json.dumps(freeze, ensure_ascii=False), encoding="utf-8")

    cases = g570.validate_freeze(freeze, freeze_path=freeze_path)

    assert list(cases) == ["case_c"]
    assert cases["case_c"]["crop_path"] == crop.resolve()
    assert cases["case_c"]["source_evidence_path"] == source_pdf.resolve()
    assert cases["case_c"]["source_evidence_kind"] == "SOURCE_PDF"


def test_freeze_rejects_broker_hints(tmp_path: Path) -> None:
    freeze = {
        "schema_version": g570.FREEZE_SCHEMA_VERSION,
        "goal": "G5.70",
        "phase": "development_initial",
        "contract_version": g570.GATE3_MINIMAL_METADATA_CONTRACT_VERSION,
        "instruction_version": g570.INSTRUCTION_VERSION,
        "model_view_sha256": g570._sha256_json(g570.visual_metadata_model_view()),
        "response_schema_sha256": g570._sha256_json(
            g570.metadata_proposal_response_schema()
        ),
        "provider_profile": "google_gemini",
        "model_id": "models/gemini-3.5-flash",
        "maximum_output_tokens": 2048,
        "maximum_counted_input_tokens": 8000,
        "thinking_level": "minimal",
        "broker_hints": ["forbidden"],
        "prompt_tuning_after_freeze": False,
        "product_activation": False,
        "cases": [],
        "runs": [],
    }

    with pytest.raises(g570.G570MicrostandError) as captured:
        g570.validate_freeze(freeze, freeze_path=tmp_path / "freeze.json")

    assert captured.value.code == "g570_freeze_contract_invalid"
