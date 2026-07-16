from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = ROOT / "scripts" / "pdf_dual_vlm_fact_evidence.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


EVIDENCE = _load_module("pdf_dual_vlm_fact_evidence_test", EVIDENCE_PATH)


class TestPdfDualVlmFactEvidence:
    def setup_method(self) -> None:
        self.verifier = EVIDENCE.PdfDualVlmFactEvidenceFactory().create()

    def test_unique_relation_projects_regions_and_preserves_source_refs(self) -> None:
        fact = _fact()
        before = copy.deepcopy(fact)

        result = self.verifier.verify(
            consensus_facts=[fact],
            word_inventory=_unique_words(),
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="text_layer",
        )

        source_map = result["source_maps"][0]
        relation = source_map["relation_candidates"][0]
        assert source_map["evidence_status"] == EVIDENCE.PARSER_VERIFIED
        assert source_map["relation_candidate_count"] == 1
        assert source_map["automatic_acceptance_eligible"] is True
        assert relation["row_label"]["exact_source_text"] == "Cash"
        assert relation["value"]["exact_source_text"] == "$ 1,000"
        assert relation["value"]["claimed_exact_text"] == "$ 1,000"
        assert relation["value"]["word_refs"] == ["word_3", "word_4"]
        assert relation["value"]["bbox_refs"] == ["bbox_3", "bbox_4"]
        assert relation["value"]["source_value_refs"] == ["src_3", "src_4"]
        assert relation["value"]["text_checksum_refs"] == ["txt_3", "txt_4"]
        assert source_map["source_identity"]["rendered_bbox"] == [
            20.0,
            10.0,
            120.0,
            110.0,
        ]
        assert source_map["evidence_requests"]["row_label"] == {
            "exact_visible_text": "Cash",
            "crop_normalized_bbox": [0.05, 0.35, 0.4, 0.55],
            "page_bbox": [25.0, 45.0, 60.0, 65.0],
        }
        assert result["summary"]["automatic_acceptance_eligible"] == 1
        assert EVIDENCE.validate_source_map(source_map) == []
        assert EVIDENCE.validate_evidence_result(result) == []
        assert fact == before

    def test_repeated_value_is_disambiguated_by_row_relation(self) -> None:
        words = _repeated_value_words(second_row_label="Bonds")
        fact = _simple_fact(
            row_label="Cash",
            value="$ 100",
            row_region=[0.0, 0.25, 0.5, 0.9],
            value_region=[0.55, 0.25, 1.0, 0.9],
            header="2024",
            header_region=[0.55, 0.0, 1.0, 0.25],
        )

        source_map = self.verifier.verify(
            consensus_facts=[fact],
            word_inventory=words,
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="text_layer",
        )["source_maps"][0]

        assert len(source_map["component_matches"]["value"]) == 2
        assert source_map["evidence_status"] == EVIDENCE.PARSER_VERIFIED
        assert source_map["relation_candidate_count"] == 1
        assert source_map["relation_candidates"][0]["value"]["parser_ordinals"] == [
            3,
            4,
        ]

    def test_repeated_row_and_value_relations_remain_ambiguous(self) -> None:
        words = _repeated_value_words(second_row_label="Cash")
        fact = _simple_fact(
            row_label="Cash",
            value="$ 100",
            row_region=[0.0, 0.25, 0.5, 0.9],
            value_region=[0.55, 0.25, 1.0, 0.9],
            header="2024",
            header_region=[0.55, 0.0, 1.0, 0.25],
        )

        source_map = self.verifier.verify(
            consensus_facts=[fact],
            word_inventory=words,
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="text_layer",
        )["source_maps"][0]

        assert source_map["evidence_status"] == EVIDENCE.AMBIGUOUS
        assert source_map["relation_candidate_count"] == 2
        assert source_map["automatic_acceptance_eligible"] is False
        assert source_map["reason_codes"] == ["multiple_complete_relation_tuples"]

    def test_period_header_must_be_above_and_column_compatible(self) -> None:
        words = [
            _word(1, "2023", [55, 20, 75, 30]),
            _word(2, "2024", [90, 20, 110, 30]),
            _word(3, "Cash", [30, 50, 50, 60]),
            _word(4, "$", [90, 50, 94, 60]),
            _word(5, "100", [96, 50, 110, 60]),
        ]
        correct = _simple_fact(
            row_label="Cash",
            value="$ 100",
            row_region=[0.0, 0.3, 0.5, 0.6],
            value_region=[0.65, 0.3, 1.0, 0.6],
            header="2024",
            header_region=[0.3, 0.0, 1.0, 0.3],
            period="2024",
        )
        wrong_column = copy.deepcopy(correct)
        wrong_column["header_path"] = ["2023"]
        wrong_column["period"] = "2023"

        maps = self.verifier.verify(
            consensus_facts=[correct, wrong_column],
            word_inventory=words,
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="text_layer",
        )["source_maps"]

        assert maps[0]["evidence_status"] == EVIDENCE.PARSER_VERIFIED
        assert maps[1]["evidence_status"] == EVIDENCE.NOT_FOUND
        assert maps[1]["relation_candidate_count"] == 0
        assert maps[1]["reason_codes"] == ["complete_relation_tuple_not_found"]

    def test_wrong_sign_is_not_normalized_into_a_match(self) -> None:
        words = [
            _word(1, "2024", [90, 20, 110, 30]),
            _word(2, "Loss", [30, 50, 50, 60]),
            _word(3, "-", [90, 50, 94, 60]),
            _word(4, "1,000", [96, 50, 110, 60]),
        ]
        fact = _simple_fact(
            row_label="Loss",
            value="+ 1,000",
            row_region=[0.0, 0.3, 0.5, 0.6],
            value_region=[0.65, 0.3, 1.0, 0.6],
            header="2024",
            header_region=[0.65, 0.0, 1.0, 0.3],
        )

        source_map = self.verifier.verify(
            consensus_facts=[fact],
            word_inventory=words,
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="text_layer",
        )["source_maps"][0]

        assert source_map["evidence_status"] == EVIDENCE.NOT_FOUND
        assert "exact_visible_value_evidence_not_found" in source_map["reason_codes"]
        assert source_map["value_normalization_performed"] is False

    def test_mixed_is_fact_scoped_but_raster_is_never_auto_accepted(self) -> None:
        mixed = self.verifier.verify(
            consensus_facts=[_fact()],
            word_inventory=_unique_words(),
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="mixed",
        )["source_maps"][0]
        raster = self.verifier.verify(
            consensus_facts=[_fact()],
            word_inventory=_unique_words(),
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="raster",
        )["source_maps"][0]

        assert mixed["evidence_status"] == EVIDENCE.PARSER_VERIFIED
        assert mixed["automatic_acceptance_eligible"] is True
        assert raster["evidence_status"] == EVIDENCE.OCR_UNAVAILABLE
        assert raster["strongest_consensus_evidence_status"] == EVIDENCE.VISION_ONLY
        assert raster["automatic_acceptance_eligible"] is False
        assert raster["ocr_performed"] is False

    def test_unrelated_page_words_do_not_verify_mixed_raster_table(self) -> None:
        unrelated = [
            _word(1, "2024", [150, 20, 170, 30]),
            _word(2, "Cash", [150, 50, 170, 60]),
            _word(3, "$", [175, 50, 179, 60]),
            _word(4, "1,000", [180, 50, 195, 60]),
        ]

        result = self.verifier.verify(
            consensus_facts=[_fact()],
            word_inventory=unrelated,
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="mixed",
        )
        source_map = result["source_maps"][0]

        assert result["table_scoped_words_total"] == 0
        assert source_map["evidence_status"] == EVIDENCE.OCR_UNAVAILABLE
        assert source_map["strongest_consensus_evidence_status"] == EVIDENCE.VISION_ONLY
        assert source_map["automatic_acceptance_eligible"] is False

        text_layer_no_words = self.verifier.verify(
            consensus_facts=[_fact()],
            word_inventory=[],
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="text_layer",
        )["source_maps"][0]
        assert text_layer_no_words["evidence_status"] == EVIDENCE.OCR_UNAVAILABLE
        assert text_layer_no_words["automatic_acceptance_eligible"] is False

    def test_checksum_tamper_is_rejected_and_factory_anchors_are_explicit(self) -> None:
        source_map = self.verifier.verify(
            consensus_facts=[_fact()],
            word_inventory=_unique_words(),
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="text_layer",
        )["source_maps"][0]
        tampered = copy.deepcopy(source_map)
        tampered["evidence_status"] = EVIDENCE.AMBIGUOUS

        assert EVIDENCE.validate_source_map(source_map) == []
        assert "fact_source_map_checksum_invalid" in EVIDENCE.validate_source_map(
            tampered
        )
        assert "PdfDualVlmFactEvidenceFactory.create" in EVIDENCE.FACTORY_REQUIRED
        assert "must not use a VLM answer as source evidence" in EVIDENCE.FORBIDDEN
        assert "auto-accept vision-only facts" in EVIDENCE.FORBIDDEN

    def test_versioned_consensus_entry_uses_intersected_provider_regions(self) -> None:
        source_map = self.verifier.verify(
            consensus_facts=[_versioned_consensus_entry()],
            word_inventory=_unique_words(),
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="text_layer",
        )["source_maps"][0]

        assert source_map["fact_id"] == "consensus_0001"
        assert source_map["consensus_status"] == "models_exactly_agree"
        assert source_map["evidence_status"] == EVIDENCE.PARSER_VERIFIED
        assert (
            source_map["evidence_requests"]["source_region_policy"]
            == "intersection_of_provider_regions"
        )
        assert source_map["evidence_requests"]["row_label"]["crop_normalized_bbox"] == [
            0.06,
            0.35,
            0.39,
            0.55,
        ]

    def test_material_qualifier_without_text_bbox_or_scope_fails_closed(self) -> None:
        missing_text = _versioned_consensus_entry()
        missing_text["canonical_fact"]["interpreted"]["entity"] = "Broker LLC"
        _reseal_canonical(missing_text)
        with pytest.raises(EVIDENCE.PdfDualVlmFactEvidenceError) as text_error:
            self.verifier.verify(
                consensus_facts=[missing_text],
                word_inventory=_unique_words(),
                crop_contract=_crop_contract(),
                page_width=200.0,
                page_height=150.0,
                medium="text_layer",
            )
        assert text_error.value.code == "fact_evidence_entity_source_text_missing"

        missing_bbox = _fact()
        missing_bbox["source_regions"]["qualifiers"]["entity"] = None
        with pytest.raises(EVIDENCE.PdfDualVlmFactEvidenceError) as bbox_error:
            self.verifier.verify(
                consensus_facts=[missing_bbox],
                word_inventory=_unique_words(),
                crop_contract=_crop_contract(),
                page_width=200.0,
                page_height=150.0,
                medium="text_layer",
            )
        assert bbox_error.value.code == "fact_evidence_entity_invalid"

        missing_scope = _fact()
        missing_scope["qualifier_scopes"].pop("entity")
        with pytest.raises(EVIDENCE.PdfDualVlmFactEvidenceError) as scope_error:
            self.verifier.verify(
                consensus_facts=[missing_scope],
                word_inventory=_unique_words(),
                crop_contract=_crop_contract(),
                page_width=200.0,
                page_height=150.0,
                medium="text_layer",
            )
        assert scope_error.value.code == "fact_evidence_entity_scope_invalid"

    def test_versioned_consensus_consumes_all_declared_qualifier_scopes(self) -> None:
        fact = _versioned_consensus_entry()
        canonical = fact["canonical_fact"]
        canonical["interpreted"].update(
            {
                "period": "2024",
                "currency_literal": "$",
                "unit": "USD",
                "scale": "thousands",
                "entity": "Broker LLC",
            }
        )
        request = canonical["evidence_request"]
        request["requested_text"].update(
            {
                "period_exact": "2024",
                "currency_exact": "$",
                "unit_exact": "USD",
                "scale_exact": "thousands",
                "entity_exact": "Broker LLC",
            }
        )
        for regions in (
            canonical["gemini_source_regions"],
            canonical["openai_source_regions"],
        ):
            regions["qualifier_bboxes"].update(
                {
                    "period": [0.65, 0.05, 0.95, 0.25],
                    "currency": [0.65, 0.35, 0.95, 0.55],
                    "unit": [0.65, 0.0, 0.8, 0.12],
                    "scale": [0.79, 0.0, 0.99, 0.12],
                    "entity": [0.05, 0.0, 0.6, 0.2],
                }
            )
        _reseal_canonical(fact)

        source_map = self.verifier.verify(
            consensus_facts=[fact],
            word_inventory=_unique_words(),
            crop_contract=_crop_contract(),
            page_width=200.0,
            page_height=150.0,
            medium="text_layer",
        )["source_maps"][0]

        assert source_map["evidence_status"] == EVIDENCE.PARSER_VERIFIED
        assert source_map["component_matches"]["qualifier_scopes"] == {
            "period": "header",
            "currency": "value",
            "unit": "header",
            "scale": "header",
            "entity": "table",
        }
        assert set(source_map["relation_candidates"][0]["qualifiers"]) == {
            "period",
            "currency",
            "unit",
            "scale",
            "entity",
        }


def _fact() -> dict[str, Any]:
    return {
        "fact_id": "cash_2024",
        "consensus_status": "models_exactly_agree",
        "exact_visible_row_label": "Cash",
        "header_path": ["2024"],
        "exact_visible_value": "$ 1,000",
        "period": "2024",
        "currency": "$",
        "unit": "USD",
        "scale": "thousands",
        "entity": "Broker LLC",
        "qualifier_scopes": {
            "period": "header",
            "currency": "value",
            "unit": "header",
            "scale": "header",
            "entity": "table",
        },
        "source_regions": {
            "row_label": [0.05, 0.35, 0.4, 0.55],
            "value": [0.65, 0.35, 0.95, 0.55],
            "headers": [[0.65, 0.05, 0.95, 0.25]],
            "qualifiers": {
                "period": [0.65, 0.05, 0.95, 0.25],
                "currency": [0.65, 0.35, 0.95, 0.55],
                "unit": [0.65, 0.0, 0.8, 0.12],
                "scale": [0.79, 0.0, 0.99, 0.12],
                "entity": [0.05, 0.0, 0.6, 0.2],
            },
        },
    }


def _simple_fact(
    *,
    row_label: str,
    value: str,
    row_region: list[float],
    value_region: list[float],
    header: str,
    header_region: list[float],
    period: str | None = None,
) -> dict[str, Any]:
    fact: dict[str, Any] = {
        "fact_id": f"{row_label}_{header}_{value}",
        "consensus_status": "models_exactly_agree",
        "exact_visible_row_label": row_label,
        "header_path": [header],
        "exact_visible_value": value,
        "qualifier_scopes": {},
        "source_regions": {
            "row_label": row_region,
            "value": value_region,
            "headers": [header_region],
            "qualifiers": {},
        },
    }
    if period is not None:
        fact["period"] = period
        fact["qualifier_scopes"]["period"] = "header"
        fact["source_regions"]["qualifiers"]["period"] = header_region
    return fact


def _unique_words() -> list[dict[str, Any]]:
    return [
        _word(1, "2024", [90, 20, 110, 30]),
        _word(2, "Cash", [30, 50, 50, 60]),
        _word(3, "$", [90, 50, 94, 60]),
        _word(4, "1,000", [96, 50, 110, 60]),
        _word(5, "USD", [90, 12, 98, 18]),
        _word(6, "thousands", [100, 12, 118, 18]),
        _word(7, "Broker", [30, 12, 48, 18]),
        _word(8, "LLC", [50, 12, 60, 18]),
    ]


def _repeated_value_words(*, second_row_label: str) -> list[dict[str, Any]]:
    return [
        _word(1, "2024", [90, 20, 110, 30]),
        _word(2, "Cash", [30, 50, 50, 60]),
        _word(3, "$", [90, 50, 94, 60]),
        _word(4, "100", [96, 50, 110, 60]),
        _word(5, second_row_label, [30, 80, 55, 90]),
        _word(6, "$", [90, 80, 94, 90]),
        _word(7, "100", [96, 80, 110, 90]),
    ]


def _word(ordinal: int, text: str, bbox: list[float]) -> dict[str, Any]:
    return {
        "parser_ordinal": ordinal,
        "geometry_reading_order": ordinal,
        "text": text,
        "bbox": bbox,
        "word_ref": f"word_{ordinal}",
        "bbox_ref": f"bbox_{ordinal}",
        "source_value_ref": f"src_{ordinal}",
        "text_checksum_ref": f"txt_{ordinal}",
    }


def _crop_contract() -> dict[str, Any]:
    contract = {
        "pdf_sha256": "a" * 64,
        "page_number": 1,
        "crop_id": "crop_0001",
        "source_bbox_points": [20.0, 10.0, 120.0, 110.0],
        "rendered_bbox_points": [20.0, 10.0, 120.0, 110.0],
        "rendered_image_sha256": "b" * 64,
        "render_dpi": 150,
        "dimensions": {"width": 200, "height": 200},
        "source_to_pixel_transform": {
            "scale_x": 2.0,
            "scale_y": 2.0,
            "translate_source_x": -20.0,
            "translate_source_y": -10.0,
        },
    }
    contract["contract_checksum"] = EVIDENCE.sha256_json(contract)
    return contract


def _versioned_consensus_entry() -> dict[str, Any]:
    gemini_regions = {
        "row_label_bbox": [0.05, 0.35, 0.4, 0.55],
        "value_bbox": [0.65, 0.35, 0.95, 0.55],
        "header_bboxes": [[0.65, 0.05, 0.95, 0.25]],
        "qualifier_bboxes": {
            "period": None,
            "currency": None,
            "unit": None,
            "scale": None,
            "entity": None,
        },
    }
    openai_regions = copy.deepcopy(gemini_regions)
    openai_regions["row_label_bbox"] = [0.06, 0.34, 0.39, 0.56]
    result = {
        "consensus_id": "consensus_0001",
        "status": "models_exactly_agree",
        "canonical_fact": {
            "fact_type": "financial_statement_line_item",
            "row_label_exact": "Cash",
            "header_path_exact": ["2024"],
            "value_exact": "$ 1,000",
            "interpreted": {
                "period": None,
                "currency_literal": None,
                "unit": None,
                "scale": None,
            },
            "evidence_request": {
                "requested_text": {
                    "row_label_exact": "Cash",
                    "header_path_exact": ["2024"],
                    "value_exact": "$ 1,000",
                    "period_exact": None,
                    "currency_exact": None,
                    "unit_exact": None,
                    "scale_exact": None,
                    "entity_exact": None,
                },
                "qualifier_scopes": {
                    "period": "header",
                    "currency": "value",
                    "unit": "header",
                    "scale": "header",
                    "entity": "table",
                },
                "required_relations": [
                    "row_value_spatial",
                    "header_value_spatial",
                ],
            },
            "gemini_source_regions": gemini_regions,
            "openai_source_regions": openai_regions,
        },
    }
    _reseal_canonical(result)
    return result


def _reseal_canonical(entry: dict[str, Any]) -> None:
    canonical = entry["canonical_fact"]
    canonical.pop("fact_checksum", None)
    canonical["fact_checksum"] = EVIDENCE.sha256_json(canonical)
