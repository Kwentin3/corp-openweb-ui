from __future__ import annotations

import copy
import unittest

from broker_reports_gate1.pdf_continuation_discovery import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PDF_CONTINUATION_DISCOVERY_POLICY_VERSION,
    PDF_CONTINUATION_DISCOVERY_SCHEMA,
    PdfContinuationDiscoveryConfig,
    PdfContinuationDiscoveryError,
    PdfContinuationDiscoveryFactory,
    PdfContinuationDiscoveryRuntime,
)


class PdfContinuationDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PdfContinuationDiscoveryFactory().create()

    def test_factory_anchors_and_factory_only_runtime(self) -> None:
        self.assertIn("PdfContinuationDiscoveryFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not infer continuation from text or values", FORBIDDEN)
        with self.assertRaisesRegex(
            PdfContinuationDiscoveryError,
            "pdf_continuation_discovery_factory_required",
        ):
            PdfContinuationDiscoveryRuntime(
                config=PdfContinuationDiscoveryConfig()
            )
        with self.assertRaisesRegex(
            PdfContinuationDiscoveryError,
            "pdf_continuation_discovery_config_invalid",
        ):
            PdfContinuationDiscoveryFactory(
                PdfContinuationDiscoveryConfig(bottom_edge_minimum=0.5)
            ).create()

    def test_exact_two_page_pair_is_grouped_deterministically(self) -> None:
        first = _descriptor(page_number=8, edge="bottom", table_ref="table_a")
        second = _descriptor(page_number=9, edge="top", table_ref="table_b")

        result = self.runtime.discover(descriptors=[second, first])
        repeated = self.runtime.discover(descriptors=[first, second])

        self.assertEqual(result, repeated)
        self.assertEqual(PDF_CONTINUATION_DISCOVERY_SCHEMA, result["schema_version"])
        self.assertEqual(
            PDF_CONTINUATION_DISCOVERY_POLICY_VERSION,
            result["policy_version"],
        )
        self.assertEqual("grouped", result["status"])
        self.assertFalse(result["manual_review_required"])
        self.assertEqual([], result["not_grouped"])
        self.assertEqual(1, len(result["continuation_groups"]))
        group = result["continuation_groups"][0]
        self.assertEqual(2, group["fragment_count"])
        self.assertEqual(4, group["shared_column_count"])
        self.assertEqual(1.0, group["horizontal_normalized_iou"])
        self.assertEqual([8, 9], [item["page_number"] for item in group["fragments"]])
        self.assertEqual(
            ["bottom_page_fragment", "top_page_fragment"],
            [item["edge_role"] for item in group["fragments"]],
        )
        self.assertTrue(result["deterministic_geometry_only"])
        self.assertFalse(result["text_or_values_used"])
        self.assertFalse(result["vlm_used"])
        self.assertFalse(result["authoritative"])
        self.assertEqual([], self.runtime.validate(result))

    def test_ambiguous_bottom_or_top_edge_is_not_grouped(self) -> None:
        cases = {
            "bottom": [
                _descriptor(page_number=1, edge="bottom", table_ref="bottom_a"),
                _descriptor(
                    page_number=1,
                    edge="bottom",
                    table_ref="bottom_b",
                    bbox=[12.0, 760.0, 588.0, 970.0],
                ),
                _descriptor(page_number=2, edge="top", table_ref="top_a"),
            ],
            "top": [
                _descriptor(page_number=1, edge="bottom", table_ref="bottom_a"),
                _descriptor(page_number=2, edge="top", table_ref="top_a"),
                _descriptor(
                    page_number=2,
                    edge="top",
                    table_ref="top_b",
                    bbox=[12.0, 20.0, 588.0, 300.0],
                ),
            ],
        }
        for edge, values in cases.items():
            with self.subTest(edge=edge):
                result = self.runtime.discover(descriptors=values)

                self._assert_manual_not_grouped(
                    result, "pdf_continuation_edge_candidate_ambiguous"
                )

    def test_missing_page_dimensions_is_not_grouped(self) -> None:
        first = _descriptor(page_number=1, edge="bottom", table_ref="bottom")
        first["page_width"] = None
        first["page_height"] = None

        result = self.runtime.discover(
            descriptors=[
                first,
                _descriptor(page_number=2, edge="top", table_ref="top"),
            ]
        )

        self._assert_manual_not_grouped(
            result, "pdf_continuation_page_dimensions_missing"
        )
        self.assertIn(
            "pdf_continuation_table_bbox_invalid", result["reason_codes"]
        )

    def test_nonadjacent_edge_candidates_are_not_grouped(self) -> None:
        result = self.runtime.discover(
            descriptors=[
                _descriptor(page_number=2, edge="bottom", table_ref="bottom"),
                _descriptor(page_number=4, edge="top", table_ref="top"),
            ]
        )

        self._assert_manual_not_grouped(
            result, "pdf_continuation_pages_nonadjacent"
        )

    def test_pair_mismatches_fail_closed(self) -> None:
        cases = {
            "sha": (
                {"pdf_sha256": "b" * 64},
                "pdf_continuation_document_or_sha_mismatch",
            ),
            "columns": (
                {"columns_total": 5},
                "pdf_continuation_column_model_mismatch",
            ),
            "minimum_columns": (
                {"columns_total": 1},
                "pdf_continuation_column_model_mismatch",
            ),
            "strategy": (
                {"table_strategy_ref": "other_strategy"},
                "pdf_continuation_strategy_mismatch",
            ),
            "confidence": (
                {"geometry_confidence": 0.79},
                "pdf_continuation_geometry_confidence_below_threshold",
            ),
            "horizontal_iou": (
                {"table_bbox": [100.0, 0.0, 600.0, 120.0]},
                "pdf_continuation_horizontal_overlap_insufficient",
            ),
        }
        for label, (changes, expected_reason) in cases.items():
            with self.subTest(label=label):
                first = _descriptor(
                    page_number=10, edge="bottom", table_ref="bottom"
                )
                second = _descriptor(
                    page_number=11, edge="top", table_ref="top"
                )
                second.update(changes)

                result = self.runtime.discover(descriptors=[first, second])

                self._assert_manual_not_grouped(result, expected_reason)

    def test_three_page_chain_is_never_split_into_two_pairs(self) -> None:
        middle = _descriptor(
            page_number=2,
            edge="both",
            table_ref="middle",
            bbox=[10.0, 0.0, 590.0, 1000.0],
        )
        result = self.runtime.discover(
            descriptors=[
                _descriptor(page_number=1, edge="bottom", table_ref="first"),
                middle,
                _descriptor(page_number=3, edge="top", table_ref="third"),
            ]
        )

        self._assert_manual_not_grouped(
            result, "pdf_continuation_three_page_chain_forbidden"
        )
        self.assertEqual(3, len(result["not_grouped"]))

    def test_non_edge_table_is_not_grouped_without_false_manual_review(self) -> None:
        value = _descriptor(page_number=1, edge="none", table_ref="ordinary")

        result = self.runtime.discover(descriptors=[value])

        self.assertEqual("not_grouped", result["status"])
        self.assertFalse(result["manual_review_required"])
        self.assertEqual(
            ["pdf_continuation_edge_signal_absent"],
            result["not_grouped"][0]["reason_codes"],
        )
        self.assertEqual([], self.runtime.validate(result))

    def test_tamper_and_open_input_contract_are_rejected(self) -> None:
        result = self.runtime.discover(
            descriptors=[
                _descriptor(page_number=1, edge="bottom", table_ref="bottom"),
                _descriptor(page_number=2, edge="top", table_ref="top"),
            ]
        )
        tampered = copy.deepcopy(result)
        tampered["continuation_groups"][0]["shared_column_count"] = 99

        errors = self.runtime.validate(tampered)

        self.assertIn("pdf_continuation_group_checksum_invalid", errors)
        self.assertIn("pdf_continuation_discovery_checksum_invalid", errors)
        malformed = copy.deepcopy(result)
        malformed["continuation_groups"][0]["fragments"][0][
            "normalized_edge_position"
        ] = "not-a-number"
        self.assertIn(
            "pdf_continuation_fragment_geometry_invalid",
            self.runtime.validate(malformed),
        )
        descriptor = _descriptor(
            page_number=1, edge="none", table_ref="open_contract"
        )
        descriptor["text"] = "forbidden free text"
        with self.assertRaisesRegex(
            PdfContinuationDiscoveryError,
            "pdf_continuation_descriptor_contract_invalid",
        ):
            self.runtime.discover(descriptors=[descriptor])

    def _assert_manual_not_grouped(
        self, result: dict, expected_reason: str
    ) -> None:
        self.assertEqual("not_grouped", result["status"])
        self.assertTrue(result["manual_review_required"])
        self.assertEqual([], result["continuation_groups"])
        self.assertIn(expected_reason, result["reason_codes"])
        self.assertEqual([], self.runtime.validate(result))


def _descriptor(
    *,
    page_number: int,
    edge: str,
    table_ref: str,
    bbox: list[float] | None = None,
) -> dict:
    if bbox is None:
        bbox = {
            "bottom": [10.0, 700.0, 590.0, 900.0],
            "top": [10.0, 100.0, 590.0, 400.0],
            "both": [10.0, 100.0, 590.0, 900.0],
            "none": [10.0, 300.0, 590.0, 700.0],
        }[edge]
    return {
        "document_ref": "doc_1",
        "pdf_sha256": "a" * 64,
        "page_ref": f"page_{page_number}",
        "page_number": page_number,
        "table_ref": table_ref,
        "page_width": 600.0,
        "page_height": 1000.0,
        "table_bbox": bbox,
        "columns_total": 4,
        "table_strategy_ref": "vector_grid_v1",
        "geometry_confidence": 0.91,
    }


if __name__ == "__main__":
    unittest.main()
