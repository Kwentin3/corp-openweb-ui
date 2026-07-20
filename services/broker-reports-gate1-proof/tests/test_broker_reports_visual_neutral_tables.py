from __future__ import annotations

import base64
import copy
import hashlib
import json
import unittest

from broker_reports_gate1.visual_neutral_tables import (
    VISUAL_OBSERVATION_SCHEMA_VERSION,
    VISUAL_RECOVERY_POLICY_VERSION,
    VISUAL_VALIDATOR_VERSION,
    Gate1VisualNeutralTableFactory,
    VisualNeutralTableError,
    build_visual_operator_review,
    render_visual_neutral_table_safe_report,
    seal_visual_ocr_observation,
    validate_visual_continuation_chain,
    validate_visual_neutral_table_result,
    validate_visual_ocr_observation,
)


def _ref(prefix: str, value: object) -> str:
    material = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(material).hexdigest()[:24]}"


def _source_unit(*, page_number: int = 1) -> dict:
    media = b"synthetic-private-image"
    return {
        "unit_ref": f"srcunit_visual_{page_number}",
        "unit_id": f"srcunit_visual_{page_number}",
        "document_id": "brdoc_synthetic_visual",
        "page_number": page_number,
        "pdf_unit_type": "pdf_visual_page_unit",
        "private_media_base64": base64.b64encode(media).decode("ascii"),
        "private_media_sha256": hashlib.sha256(media).hexdigest(),
        "access_scope_ref": "accessscope_synthetic_case",
    }


def _line(line_ref: str, text: str, bbox: list[int]) -> dict:
    checksum = _ref("visualtextchk", text)
    return {
        "line_ref": line_ref,
        "text": text,
        "bbox": bbox,
        "confidence": 0.99,
        "text_checksum_ref": checksum,
        "confirmation_text_checksum_ref": checksum,
    }


def _observation(source_unit: dict | None = None) -> dict:
    source_unit = source_unit or _source_unit()
    lines = [
        _line("line_header_a", "Column A", [10, 10, 80, 40]),
        _line("line_header_b", "Column B", [110, 10, 180, 40]),
        _line("line_value_a", "10,00", [10, 110, 80, 140]),
    ]
    cells = [
        {
            "row_index": 0,
            "column_index": 0,
            "row_span": 1,
            "column_span": 1,
            "bbox": [0, 0, 100, 100],
            "ocr_line_refs": ["line_header_a"],
            "source_text": "Column A",
            "content_state": "present",
        },
        {
            "row_index": 0,
            "column_index": 1,
            "row_span": 1,
            "column_span": 1,
            "bbox": [100, 0, 200, 100],
            "ocr_line_refs": ["line_header_b"],
            "source_text": "Column B",
            "content_state": "present",
        },
        {
            "row_index": 1,
            "column_index": 0,
            "row_span": 1,
            "column_span": 1,
            "bbox": [0, 100, 100, 200],
            "ocr_line_refs": ["line_value_a"],
            "source_text": "10,00",
            "content_state": "present",
        },
        {
            "row_index": 1,
            "column_index": 1,
            "row_span": 1,
            "column_span": 1,
            "bbox": [100, 100, 200, 200],
            "ocr_line_refs": [],
            "source_text": "",
            "content_state": "empty",
        },
    ]
    row_boundaries = [0, 100, 200]
    column_boundaries = [0, 100, 200]
    table = {
        "table_ref": "observed_table_001",
        "bbox": [0, 0, 200, 200],
        "row_count": 2,
        "column_count": 2,
        "row_boundaries": row_boundaries,
        "column_boundaries": column_boundaries,
        "cells": cells,
        "header_rows": [0],
        "header_hierarchy": [
            {
                "anchor": [0, 0],
                "parent_anchor": [],
                "level": 0,
                "source_text_checksum_ref": _ref("visualtextchk", "Column A"),
            },
            {
                "anchor": [0, 1],
                "parent_anchor": [],
                "level": 0,
                "source_text_checksum_ref": _ref("visualtextchk", "Column B"),
            },
        ],
        "row_roles": ["header", "body"],
        "merge_evidence": {
            "spanning_cell_anchors": [],
            "ambiguity_status": "not_present",
        },
        "geometry_evidence": {
            "expected_row_count": 2,
            "expected_column_count": 2,
            "raw_cell_boxes_total": 4,
            "raw_cell_boxes_checksum_ref": _ref(
                "visualcellboxchk", [cell["bbox"] for cell in cells]
            ),
            "row_boundaries_checksum_ref": _ref(
                "visualrowgridchk", row_boundaries
            ),
            "column_boundaries_checksum_ref": _ref(
                "visualcolgridchk", column_boundaries
            ),
            "independent_grid_consistency": "passed",
        },
    }
    observation = {
        "schema_version": VISUAL_OBSERVATION_SCHEMA_VERSION,
        "source_unit_ref": source_unit["unit_ref"],
        "document_ref": source_unit["document_id"],
        "page_number": source_unit["page_number"],
        "image_sha256": source_unit["private_media_sha256"],
        "access_scope_ref": source_unit["access_scope_ref"],
        "proposal_source": "local_ocr_geometry",
        "proposal_evidence": {
            "declared_region_only": True,
            "whole_document_provided_to_model": False,
            "model_canonical_authority": False,
            "financial_interpretation_performed": False,
        },
        "terminal_status": "completed",
        "reason_codes": [],
        "orientation_degrees": 0,
        "oriented_width_pixels": 200,
        "oriented_height_pixels": 200,
        "declared_region_bbox": [0, 0, 200, 200],
        "image_statistics": {
            "nonwhite_pixel_count": 1000,
            "pixel_stddev": 30.5,
        },
        "renderer_version": "synthetic_renderer_v1",
        "preprocessing_version": "synthetic_preprocessor_v1",
        "ocr_engine_id": "synthetic_local_ocr",
        "ocr_engine_version": "1.0",
        "ocr_model_set_ref": "synthetic_models_v1",
        "validator_version": VISUAL_VALIDATOR_VERSION,
        "recovery_policy_version": VISUAL_RECOVERY_POLICY_VERSION,
        "provider_accounting": {
            "calls": 0,
            "retries": 0,
            "tokens": 0,
            "cost": 0,
            "whole_document_uploads": 0,
        },
        "ocr_lines": lines,
        "ocr_consensus_status": "exact",
        "uncertainty_ledger": [],
        "tables": [table],
        "outside_table_line_refs": [],
        "continuation": {
            "relationship": "not_applicable",
            "group_ref": None,
            "previous_page_number": None,
            "next_page_number": None,
        },
    }
    return seal_visual_ocr_observation(observation)


def _semantic_mutation(observation: dict, mutation) -> dict:
    changed = copy.deepcopy(observation)
    mutation(changed)
    return seal_visual_ocr_observation(changed)


def _codes(observation: dict, source_unit: dict | None = None) -> set[str]:
    source_unit = source_unit or _source_unit()
    return {
        item["code"]
        for item in validate_visual_ocr_observation(
            observation,
            source_unit=source_unit,
        )
    }


class BrokerReportsVisualNeutralTableTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source_unit = _source_unit()
        self.observation = _observation(self.source_unit)
        self.service = Gate1VisualNeutralTableFactory().create()

    def test_deterministic_promotion_replay_and_safe_projection(self):
        first = self.service.recover(
            source_unit=self.source_unit,
            observation=self.observation,
        )
        second = self.service.recover(
            source_unit=self.source_unit,
            observation=self.observation,
        )
        safe = render_visual_neutral_table_safe_report(first)

        self.assertEqual(first, second)
        self.assertEqual(
            first["promotion_state"],
            "canonical_table_accepted_deterministic",
        )
        self.assertEqual(first["source_to_table_accounting"]["ocr_lines_total"], 3)
        self.assertEqual(first["source_to_table_accounting"]["cells_total"], 4)
        self.assertEqual(validate_visual_neutral_table_result(first), [])
        self.assertEqual(safe["validator_status"], "passed")
        self.assertFalse(safe["customer_values_in_report"])
        self.assertFalse(safe["source_identities_in_report"])
        self.assertNotIn("10,00", json.dumps(safe, ensure_ascii=False))

    def test_reviewed_visual_promotion_requires_scoped_operator_review(self):
        def make_uncertain(item: dict) -> None:
            line = item["ocr_lines"][2]
            line["confidence"] = 0.5
            line["confirmation_text_checksum_ref"] = _ref(
                "visualtextchk", "10.00"
            )
            item["ocr_consensus_status"] = "differences_resolved_by_review"
            item["uncertainty_ledger"] = [
                {
                    "uncertainty_ref": "uncertainty_decimal_separator",
                    "scope_ref": line["line_ref"],
                    "resolution": "operator_resolved",
                }
            ]

        observation = _semantic_mutation(self.observation, make_uncertain)
        without_review = self.service.recover(
            source_unit=self.source_unit,
            observation=observation,
        )
        review = build_visual_operator_review(
            observation=observation,
            resolved_uncertainty_refs=["uncertainty_decimal_separator"],
        )
        accepted = self.service.recover(
            source_unit=self.source_unit,
            observation=observation,
            operator_review=review,
        )

        self.assertEqual(
            without_review["promotion_state"],
            "unresolved_visual_requires_review",
        )
        self.assertEqual(
            accepted["promotion_state"],
            "canonical_table_accepted_reviewed_visual",
        )

    def test_blank_material_scope_stays_explicitly_unresolved(self):
        def make_blank(item: dict) -> None:
            item["terminal_status"] = "unresolved"
            item["reason_codes"] = ["visual_source_image_blank_or_uniform"]
            item["image_statistics"] = {
                "nonwhite_pixel_count": 0,
                "pixel_stddev": 0.0,
            }
            item["ocr_lines"] = []
            item["ocr_consensus_status"] = "not_available"
            item["tables"] = []

        observation = _semantic_mutation(self.observation, make_blank)
        result = self.service.recover(
            source_unit=self.source_unit,
            observation=observation,
        )

        self.assertEqual(
            result["promotion_state"], "unresolved_visual_requires_review"
        )
        self.assertEqual(result["canonical_tables"], [])
        self.assertEqual(result["reason_codes"], ["visual_source_image_blank_or_uniform"])

    def test_provider_proposal_is_not_used_without_approval(self):
        observation = _semantic_mutation(
            self.observation,
            lambda item: item.update(proposal_source="bounded_vl_proposal"),
        )
        result = self.service.recover(
            source_unit=self.source_unit,
            observation=observation,
        )
        self.assertEqual(
            result["promotion_state"], "unresolved_visual_requires_review"
        )
        self.assertEqual(result["provider_accounting"]["calls"], 0)

    def test_grid_coverage_duplicate_and_omission_fail_closed(self):
        cases = [
            (
                "missing_cell",
                lambda item: item["tables"][0]["cells"].pop(),
                "visual_table_grid_coverage_invalid",
            ),
            (
                "duplicate_ocr_ref",
                lambda item: item["tables"][0]["cells"][3].update(
                    ocr_line_refs=["line_value_a"],
                    source_text="10,00",
                    content_state="present",
                ),
                "visual_ocr_line_assigned_multiple_times",
            ),
            (
                "omitted_line_accounting",
                lambda item: item["tables"][0]["cells"][2].update(
                    ocr_line_refs=[], source_text="", content_state="empty"
                ),
                "visual_ocr_line_accounting_incomplete",
            ),
        ]
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                changed = _semantic_mutation(self.observation, mutate)
                self.assertIn(expected, _codes(changed))

    def test_ocr_substitution_and_decimal_separator_drift_fail_closed(self):
        for replacement in ("99,99", "10.00"):
            with self.subTest(replacement=replacement):
                def mutate(item: dict) -> None:
                    line = item["ocr_lines"][2]
                    line["text"] = replacement
                    line["text_checksum_ref"] = _ref("visualtextchk", replacement)
                    line["confirmation_text_checksum_ref"] = line[
                        "text_checksum_ref"
                    ]

                changed = _semantic_mutation(self.observation, mutate)
                self.assertIn(
                    "visual_cell_source_text_unreproducible", _codes(changed)
                )

    def test_geometry_column_order_header_total_and_merge_fail_closed(self):
        cases = [
            (
                "column_reorder",
                lambda item: (
                    item["tables"][0]["cells"][0].update(
                        ocr_line_refs=["line_header_b"], source_text="Column B"
                    ),
                    item["tables"][0]["cells"][1].update(
                        ocr_line_refs=["line_header_a"], source_text="Column A"
                    ),
                ),
                "visual_cell_ocr_geometry_mismatch",
            ),
            (
                "header_hierarchy",
                lambda item: item["tables"][0].update(header_hierarchy=[]),
                "visual_table_header_hierarchy_incomplete",
            ),
            (
                "false_merge",
                lambda item: item["tables"][0]["merge_evidence"].update(
                    ambiguity_status="confirmed"
                ),
                "visual_table_merge_evidence_invalid",
            ),
            (
                "false_boundary",
                lambda item: item["tables"][0].update(
                    column_boundaries=[0, 70, 200]
                ),
                "visual_cell_geometry_mismatch",
            ),
        ]
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                changed = _semantic_mutation(self.observation, mutate)
                self.assertIn(expected, _codes(changed))

        def make_unmarked_total(item: dict) -> None:
            line = item["ocr_lines"][2]
            line["text"] = "Total: 10,00"
            line["text_checksum_ref"] = _ref("visualtextchk", line["text"])
            line["confirmation_text_checksum_ref"] = line["text_checksum_ref"]
            item["tables"][0]["cells"][2]["source_text"] = line["text"]

        total = _semantic_mutation(self.observation, make_unmarked_total)
        self.assertIn("visual_table_total_role_missing", _codes(total))

    def test_wrong_scope_access_image_and_continuation_fail_closed(self):
        cases = [
            (
                lambda item: item.update(page_number=2),
                "visual_observation_scope_mismatch",
            ),
            (
                lambda item: item.update(access_scope_ref="another_case"),
                "visual_observation_scope_mismatch",
            ),
            (
                lambda item: item["continuation"].update(
                    relationship="declared_page_sequence",
                    group_ref="group_1",
                    next_page_number=4,
                ),
                "visual_continuation_next_page_invalid",
            ),
        ]
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                self.assertIn(
                    expected,
                    _codes(_semantic_mutation(self.observation, mutate)),
                )

        drifted_source = copy.deepcopy(self.source_unit)
        drifted_source["private_media_base64"] = base64.b64encode(b"drift").decode(
            "ascii"
        )
        self.assertIn(
            "visual_source_image_checksum_drift",
            _codes(self.observation, drifted_source),
        )

    def test_malformed_authority_boundaries_and_cells_return_errors_not_crashes(self):
        cases = [
            (
                lambda item: item["proposal_evidence"].update(
                    model_canonical_authority=True
                ),
                "visual_proposal_authority_contract_invalid",
            ),
            (
                lambda item: item["tables"][0].update(row_boundaries=[]),
                "visual_table_row_boundaries_invalid",
            ),
            (
                lambda item: item["tables"][0]["cells"][0].update(
                    row_index="zero"
                ),
                "visual_cell_span_invalid",
            ),
        ]
        for mutate, expected in cases:
            with self.subTest(expected=expected):
                changed = _semantic_mutation(self.observation, mutate)
                self.assertIn(expected, _codes(changed))

    def test_tampered_result_and_unsupported_state_with_tables_are_rejected(self):
        result = self.service.recover(
            source_unit=self.source_unit,
            observation=self.observation,
        )
        tampered = copy.deepcopy(result)
        tampered["canonical_tables"][0]["cells"][2]["source_text"] = "99,99"
        self.assertIn(
            "visual_result_table_integrity_mismatch",
            {item["code"] for item in validate_visual_neutral_table_result(tampered)},
        )
        unsupported = copy.deepcopy(result)
        unsupported["promotion_state"] = "unsupported_visual_layout"
        self.assertIn(
            "visual_result_canonical_table_state_mismatch",
            {
                item["code"]
                for item in validate_visual_neutral_table_result(unsupported)
            },
        )

    def test_continuation_chain_requires_complete_links(self):
        results = []
        for page in (1, 2, 3):
            source = _source_unit(page_number=page)
            observation = _observation(source)
            observation = _semantic_mutation(
                observation,
                lambda item, current=page: item.update(
                    continuation={
                        "relationship": "declared_page_sequence",
                        "group_ref": "restricted_sequence_1",
                        "previous_page_number": current - 1 if current > 1 else None,
                        "next_page_number": current + 1 if current < 3 else None,
                    }
                ),
            )
            results.append(
                self.service.recover(source_unit=source, observation=observation)
            )
        self.assertEqual(validate_visual_continuation_chain(results), [])
        results.pop(1)
        self.assertIn(
            "visual_continuation_chain_invalid",
            {item["code"] for item in validate_visual_continuation_chain(results)},
        )

    def test_invalid_observation_is_never_promoted(self):
        changed = copy.deepcopy(self.observation)
        changed["tables"][0]["cells"].pop()
        with self.assertRaises(VisualNeutralTableError):
            self.service.recover(
                source_unit=self.source_unit,
                observation=changed,
            )


if __name__ == "__main__":
    unittest.main()
