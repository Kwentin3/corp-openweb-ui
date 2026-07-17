from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

import pdf_dual_vlm_literal_contracts as CONTRACTS  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "local_pdf_dual_vlm_literal_extract_test",
    SCRIPT_DIR / "local_pdf_dual_vlm_literal_extract.py",
)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

PADDING_SPEC = importlib.util.spec_from_file_location(
    "local_pdf_dual_vlm_literal_padding_score_test",
    SCRIPT_DIR / "local_pdf_dual_vlm_literal_padding_score.py",
)
assert PADDING_SPEC and PADDING_SPEC.loader
PADDING = importlib.util.module_from_spec(PADDING_SPEC)
PADDING_SPEC.loader.exec_module(PADDING)


class BoundaryProvider:
    def __init__(self, output: dict[str, object]) -> None:
        self.output = output
        self.count_calls = 0
        self.invoke_calls = 0

    def count_tokens(self, **kwargs: object) -> dict[str, object]:
        self.count_calls += 1
        schema = kwargs["output_schema"]
        return {
            "total_tokens": 100,
            "canonical_schema_hash": CONTRACTS.sha256_json(schema),
            "adapted_schema_hash": CONTRACTS.sha256_json(schema),
            "schema_transform_count": 0,
        }

    def invoke(self, **kwargs: object) -> dict[str, object]:
        self.invoke_calls += 1
        crop_sha = str(kwargs["crop_sha256"])
        model_view = kwargs["model_view"]
        return {
            "attempt": {
                "attempt_number": kwargs["attempt_number"],
                "attempt_lineage": kwargs["attempt_lineage"],
                "hidden_retry": False,
                "provider_failover": False,
                "crop_sha256": crop_sha,
                "model_view_hash": CONTRACTS.sha256_json(model_view),
                "terminal_failure_class": None,
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
            "text": CONTRACTS.canonical_json_bytes(self.output).decode("utf-8"),
            "json_output": self.output,
            "response_bytes": 500,
        }


def _output(crop_sha: str) -> dict[str, object]:
    return {
        "schema_version": CONTRACTS.LITERAL_SCHEMA_VERSION,
        "crop_sha256": crop_sha,
        "table_identifier": "case_1:table_0",
        "entries": [
            {
                "entry_id": "p1",
                "row_label_text": "Total assets",
                "column_header_path": ["2025"],
                "visible_value_text": "10,500",
                "row_label_bbox": [0.1, 0.2, 0.4, 0.25],
                "header_bboxes": [[0.7, 0.1, 0.9, 0.15]],
                "value_bbox": [0.7, 0.2, 0.9, 0.25],
                "cell_state": "value",
                "uncertainty_codes": [],
            }
        ],
    }


def test_provider_operation_has_one_preflight_one_generate_and_terminal_output() -> None:
    png = b"immutable-crop"
    crop_sha = RUNNER.hashlib.sha256(png).hexdigest()
    provider = BoundaryProvider(_output(crop_sha))
    view = CONTRACTS.literal_model_view(
        crop_sha256=crop_sha,
        table_identifier="case_1:table_0",
        image_width=100,
        image_height=50,
    )

    operation = RUNNER._provider_operation(
        provider=provider,
        provider_name="gemini",
        task_id="task_1",
        model_view=view,
        output_schema=CONTRACTS.literal_observation_schema(),
        png_bytes=png,
        table_identifier="case_1:table_0",
    )

    assert provider.count_calls == 1
    assert provider.invoke_calls == 1
    assert operation["count_or_preflight_calls_completed"] == 1
    assert operation["generate_calls_completed"] == 1
    assert operation["attempt"]["attempt_number"] == 1
    assert operation["attempt"]["attempt_lineage"] == []
    assert operation["hidden_retry"] is False
    assert operation["provider_failover"] is False
    assert operation["terminal_status"] == "completed"


def test_malformed_provider_output_is_terminal_and_not_repaired() -> None:
    png = b"immutable-crop"
    crop_sha = RUNNER.hashlib.sha256(png).hexdigest()
    malformed = _output(crop_sha)
    del malformed["entries"][0]["value_bbox"]
    provider = BoundaryProvider(malformed)
    view = CONTRACTS.literal_model_view(
        crop_sha256=crop_sha,
        table_identifier="case_1:table_0",
        image_width=100,
        image_height=50,
    )

    operation = RUNNER._provider_operation(
        provider=provider,
        provider_name="openai",
        task_id="task_1",
        model_view=view,
        output_schema=CONTRACTS.literal_observation_schema(),
        png_bytes=png,
        table_identifier="case_1:table_0",
    )

    assert operation["terminal_status"] == "terminal_contract_failure"
    assert operation["failure_code"] == "literal_entry_0_fields_invalid"
    assert "value_bbox" not in operation["json_output"]["entries"][0]


def test_raster_parser_evidence_never_treats_one_vlm_as_independent_evidence() -> None:
    evidence = RUNNER._parser_evidence(
        entries=_output("a" * 64)["entries"],
        crop_bbox=[0.1, 0.1, 0.9, 0.9],
        page_bbox_points=[0.0, 0.0, 612.0, 792.0],
        words=[],
        evidence_medium="raster",
    )

    assert evidence == [
        {
            "entry_id": "p1",
            "status": "parser_not_applicable_raster",
            "independent_text_evidence": "vision_only_no_independent_text_evidence",
            "parser_atom_ids": [],
            "binding_unique": False,
        }
    ]


def test_schema_fixture_roundtrip_is_canonical_for_both_adapters() -> None:
    result = RUNNER._schema_fixture_roundtrip()

    assert result["canonical_validation_errors"] == []
    assert result["canonical_equivalence"] is True
    assert result["gemini_adapter_roundtrip_sha256"] == result[
        "openai_adapter_roundtrip_sha256"
    ]


def test_padding_selection_fails_when_detection_missed_reference_table() -> None:
    variant = PADDING._score_variant(
        padding=0.01,
        cases=[
            {
                "case_id": "case_1",
                "page_number": 1,
                "candidates": [],
                "reference_regions": [
                    {"region_id": "r1", "bbox": [0.1, 0.1, 0.9, 0.9]}
                ],
                "matches": [],
            }
        ],
        total_reference=1,
        total_candidates=0,
        total_invalid=0,
        total_matched=0,
    )

    assert variant["missed_reference_tables"] == 1
    assert variant["selection_conditions_passed"] is False


def test_padding_variant_records_complete_reproducible_attributable_crop() -> None:
    reference_bbox = [0.1, 0.1, 0.9, 0.9]
    candidate = {
        "candidate_id": "table_0",
        "decision": "present",
        "bbox_contract_valid": True,
        "detected_bbox": [0.105, 0.105, 0.895, 0.895],
        "padding_variants": [
            {
                "padding_fraction_per_page_side": 0.01,
                "padded_crop_bbox": [0.095, 0.095, 0.905, 0.905],
                "crop_sha256": "a" * 64,
                "crop_bytes": 100,
                "crop_width": 200,
                "crop_height": 300,
                "byte_identical_reproduction": True,
            }
        ],
    }
    variant = PADDING._score_variant(
        padding=0.01,
        cases=[
            {
                "case_id": "case_1",
                "page_number": 1,
                "candidates": [candidate],
                "reference_regions": [{"region_id": "r1", "bbox": reference_bbox}],
                "matches": [
                    {
                        "candidate_index": 0,
                        "candidate_id": "table_0",
                        "reference_index": 0,
                        "reference_region_id": "r1",
                        "detected_bbox_iou": 0.9,
                    }
                ],
            }
        ],
        total_reference=1,
        total_candidates=1,
        total_invalid=0,
        total_matched=1,
    )

    assert variant["cut_reference_tables"] == 0
    assert variant["adjacent_table_inclusion"] == 0
    assert variant["crop_reproducibility_failures"] == 0
    assert variant["every_crop_attributable_to_exactly_one_reference_table"] is True
    assert variant["selection_conditions_passed"] is True
