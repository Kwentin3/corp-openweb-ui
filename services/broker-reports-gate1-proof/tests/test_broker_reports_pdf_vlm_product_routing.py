from __future__ import annotations

import copy
import unittest

from broker_reports_gate1.pdf_vlm_product_routing import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PdfVlmProductRouter,
    PdfVlmProductRouterError,
    PdfVlmProductRouterFactory,
)


class BrokerReportsPdfVlmProductRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = PdfVlmProductRouterFactory().create()

    def test_factory_is_the_only_runtime_entrypoint(self) -> None:
        self.assertIn("PdfVlmProductRouterFactory.create", FACTORY_REQUIRED)
        self.assertIn("human labels", FORBIDDEN)
        with self.assertRaises(PdfVlmProductRouterError) as error:
            PdfVlmProductRouter()  # type: ignore[call-arg]
        self.assertEqual(
            "pdf_vlm_product_router_factory_required",
            error.exception.code,
        )

    def test_sparse_ruled_candidate_routes_to_candidate_crop(self) -> None:
        page, words, bboxes = _evidence(
            [
                ("Wrapped schedule label", 30.0, 80.0, 210.0),
                ("7,018", 260.0, 80.0, 310.0),
                ("Continuation", 30.0, 105.0, 130.0),
            ]
        )
        candidate = _candidate(
            words,
            strategy="ruled_lines_v0",
            rows=55,
            columns=10,
            populated_cells=3,
            cells=550,
        )

        result = self.router.route(
            page_evidence=page,
            candidate_evidence=candidate,
            page_words=words,
            bbox_inventory=bboxes,
        )

        self.assertEqual("candidate_crop", result["route"])
        self.assertEqual("plausible", result["detection"])
        self.assertTrue(result["provider_call_allowed"])
        self.assertIn("ruled_candidate_geometry_present", result["reason_codes"])
        self.assertTrue(result["observations"]["ruled_candidate"])
        self.router.validate_result(result)

    def test_genuinely_repeated_numeric_axis_routes_to_candidate_crop(self) -> None:
        rows = [(f"Line {index}", 30.0, 60.0 + index * 20.0, 150.0) for index in range(6)]
        rows += [
            (f"{(index + 1) * 100:,}", 260.0, 60.0 + index * 20.0, 310.0)
            for index in range(6)
        ]
        page, words, bboxes = _evidence(rows)
        candidate = _candidate(
            words,
            strategy="aligned_text_v0",
            rows=12,
            columns=3,
            populated_cells=12,
            cells=36,
        )

        result = self.router.route(
            page_evidence=page,
            candidate_evidence=candidate,
            page_words=words,
            bbox_inventory=bboxes,
        )

        self.assertEqual("candidate_crop", result["route"])
        self.assertEqual("plausible", result["detection"])
        self.assertTrue(result["observations"]["repeated_numeric_axis_present"])
        self.assertEqual(
            6,
            result["observations"]["maximum_repeated_numeric_axis_words"],
        )

    def test_broad_aligned_financial_schedule_routes_to_page_level(self) -> None:
        page, words, bboxes = _evidence(
            [
                ("The following table presents the changes in allowance for credit losses", 20, 60, 390),
                ("Opening balance", 30, 100, 150),
                ("1,200", 260, 100, 310),
                ("Charge offs", 30, 125, 130),
                ("(300)", 260, 125, 310),
                ("Closing balance", 30, 150, 150),
                ("900", 260, 150, 310),
            ]
        )
        candidate = _candidate(
            words,
            strategy="aligned_text_v0",
            rows=42,
            columns=8,
            populated_cells=80,
            cells=336,
            bbox=(10.0, 20.0, 390.0, 650.0),
        )

        result = self.router.route(
            page_evidence=page,
            candidate_evidence=candidate,
            page_words=words,
            bbox_inventory=bboxes,
        )

        self.assertEqual("page_level", result["route"])
        self.assertEqual("uncertain", result["detection"])
        self.assertIn(
            "broad_region_contains_objective_schedule_signal",
            result["reason_codes"],
        )
        self.assertTrue(result["observations"]["financial_schedule_signal_present"])

    def test_likely_missed_table_without_candidate_routes_to_page_level(self) -> None:
        page, words, bboxes = _evidence(
            [
                ("The following table presents fair value assets", 20, 60, 360),
                ("Level 1", 30, 100, 90),
                ("12,019", 260, 100, 310),
                ("Total", 30, 125, 80),
                ("12,019", 260, 125, 310),
            ]
        )

        result = self.router.route(
            page_evidence=page,
            candidate_evidence=None,
            page_words=words,
            bbox_inventory=bboxes,
        )

        self.assertEqual("page_level", result["route"])
        self.assertEqual("uncertain", result["detection"])
        self.assertFalse(result["observations"]["candidate_present"])
        self.assertTrue(result["provider_call_allowed"])

    def test_table_of_contents_is_an_obvious_zero_call_negative(self) -> None:
        page, words, bboxes = _evidence(
            [
                ("TABLE OF CONTENTS", 30, 50, 200),
                ("Statement of Financial Condition", 30, 90, 230),
                ("2", 300, 90, 310),
                ("Notes to the Statement", 30, 115, 200),
                ("3", 300, 115, 310),
            ]
        )
        candidate = _candidate(words, strategy="aligned_text_v0", rows=5, columns=4)

        result = self.router.route(
            page_evidence=page,
            candidate_evidence=candidate,
            page_words=words,
            bbox_inventory=bboxes,
        )

        self.assertEqual("skip_obvious_non_table", result["route"])
        self.assertEqual("implausible", result["detection"])
        self.assertFalse(result["provider_call_allowed"])
        self.assertEqual(
            ["table_of_contents_marker_present"],
            result["reason_codes"],
        )

    def test_plain_financial_prose_without_schedule_geometry_is_skipped(self) -> None:
        page, words, bboxes = _evidence(
            [
                ("The Company records financial assets at fair value.", 20, 60, 380),
                ("Management evaluates estimates and assumptions each period.", 20, 90, 390),
                ("ASC 820 defines three input tiers as follows.", 20, 120, 350),
                ("Level 1 uses observable market prices.", 20, 150, 330),
            ]
        )
        candidate = _candidate(
            words,
            strategy="aligned_text_v0",
            rows=54,
            columns=9,
            populated_cells=250,
            cells=486,
            bbox=(10.0, 20.0, 390.0, 650.0),
        )

        result = self.router.route(
            page_evidence=page,
            candidate_evidence=candidate,
            page_words=words,
            bbox_inventory=bboxes,
        )

        self.assertEqual("skip_obvious_non_table", result["route"])
        self.assertEqual("implausible", result["detection"])
        self.assertEqual(
            ["objective_table_signal_absent"],
            result["reason_codes"],
        )

    def test_upstream_failure_preserves_exact_closed_reasons(self) -> None:
        result = self.router.route(
            page_evidence=None,
            candidate_evidence=None,
            page_words=[],
            bbox_inventory=[],
            upstream_failure_reason_codes=[
                "pdf_layout_document_inventory_budget_exceeded",
                "pdf_layout_tail_not_processed_budget",
            ],
        )

        self.assertEqual("upstream_failure", result["route"])
        self.assertEqual("absent_due_to_upstream_failure", result["detection"])
        self.assertFalse(result["provider_call_allowed"])
        self.assertEqual(
            [
                "pdf_layout_document_inventory_budget_exceeded",
                "pdf_layout_tail_not_processed_budget",
            ],
            result["reason_codes"],
        )

    def test_damaged_projection_becomes_typed_upstream_failure(self) -> None:
        result = self.router.route(
            page_evidence={"layout_projection_status": "blocked"},
            candidate_evidence=None,
            page_words=[],
            bbox_inventory=[],
        )

        self.assertEqual("upstream_failure", result["route"])
        self.assertEqual("absent_due_to_upstream_failure", result["detection"])
        self.assertEqual(
            [
                "pdf_vlm_product_routing_page_evidence_unusable",
                "pdf_vlm_product_routing_page_geometry_missing",
                "pdf_vlm_product_routing_page_words_missing",
            ],
            result["reason_codes"],
        )

    def test_identity_labels_do_not_change_route_or_checksum(self) -> None:
        page, words, bboxes = _evidence(
            [
                ("The following table presents lease liabilities", 20, 60, 350),
                ("Assets", 30, 100, 90),
                ("387,349", 260, 100, 310),
            ]
        )
        candidate = _candidate(
            words,
            strategy="aligned_text_v0",
            rows=32,
            columns=8,
            bbox=(10.0, 20.0, 390.0, 650.0),
        )
        first = self.router.route(
            page_evidence={
                **page,
                "page_ref": "page_betterment_p4",
                "filename": "human-positive.pdf",
                "pdf_sha256": "a" * 64,
                "human_label": "positive",
            },
            candidate_evidence={
                **candidate,
                "page_ref": "page_betterment_p4",
                "human_label": "positive",
            },
            page_words=words,
            bbox_inventory=bboxes,
        )
        second = self.router.route(
            page_evidence={
                **page,
                "page_ref": "page_negative",
                "filename": "negative.pdf",
                "pdf_sha256": "b" * 64,
                "human_label": "negative",
            },
            candidate_evidence={
                **candidate,
                "page_ref": "page_negative",
                "human_label": "negative",
            },
            page_words=words,
            bbox_inventory=bboxes,
        )

        self.assertEqual(first, second)

    def test_checksum_validation_detects_observation_rewrite(self) -> None:
        page, words, bboxes = _evidence(
            [("Ordinary narrative paragraph without a schedule", 20, 60, 370)]
        )
        result = self.router.route(
            page_evidence=page,
            candidate_evidence=_candidate(words, strategy="aligned_text_v0"),
            page_words=words,
            bbox_inventory=bboxes,
        )
        forged = copy.deepcopy(result)
        forged["observations"]["ruled_candidate"] = True

        with self.assertRaises(PdfVlmProductRouterError) as error:
            self.router.validate_result(forged)
        self.assertEqual(
            "pdf_vlm_product_route_checksum_invalid",
            error.exception.code,
        )


def _evidence(
    rows: list[tuple[str, float, float, float]],
) -> tuple[dict, list[dict], list[dict]]:
    page = {
        "layout_page_width": 400.0,
        "layout_page_height": 700.0,
        "layout_projection_status": "complete",
    }
    words = []
    bboxes = [
        {
            "bbox_ref": "candidate_bbox",
            "coordinate_space": "pdfplumber_top_origin_points",
            "bbox": [10.0, 20.0, 390.0, 650.0],
        }
    ]
    for ordinal, (text, x0, top, x1) in enumerate(rows, start=1):
        word_ref = f"word_{ordinal:03d}"
        bbox_ref = f"bbox_{ordinal:03d}"
        words.append(
            {
                "word_ref": word_ref,
                "bbox_ref": bbox_ref,
                "text": text,
                "geometry_reading_order": ordinal,
            }
        )
        bboxes.append(
            {
                "bbox_ref": bbox_ref,
                "coordinate_space": "pdfplumber_top_origin_points",
                "bbox": [float(x0), float(top), float(x1), float(top + 10.0)],
            }
        )
    return page, words, bboxes


def _candidate(
    words: list[dict],
    *,
    strategy: str,
    rows: int = 8,
    columns: int = 4,
    populated_cells: int | None = None,
    cells: int | None = None,
    bbox: tuple[float, float, float, float] = (10.0, 20.0, 390.0, 650.0),
) -> dict:
    total_cells = cells if cells is not None else rows * columns
    populated = populated_cells if populated_cells is not None else len(words)
    return {
        "bbox_ref": "candidate_bbox",
        "table_strategy_ref": strategy,
        "table_reconstruction_status": "candidate",
        "rows_total": rows,
        "columns_total": columns,
        "cells_total": total_cells,
        "contributing_word_refs": [word["word_ref"] for word in words],
        "cell_inventory": [
            {"word_refs": [f"owned_{index}"] if index < populated else []}
            for index in range(total_cells)
        ],
        "diagnostic_bbox": list(bbox),
    }


if __name__ == "__main__":
    unittest.main()
