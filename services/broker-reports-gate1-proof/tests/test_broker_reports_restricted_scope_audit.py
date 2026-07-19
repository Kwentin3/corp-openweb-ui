from __future__ import annotations

import sys
import unittest
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = SERVICE_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from audit_restricted_source_scopes import (  # noqa: E402
    FACTORY_REQUIRED,
    FORBIDDEN,
    assert_safe_output,
    bbox_relationship,
    classify_table_candidate,
    classify_visual_unit,
    xml_value_coverage,
)


class BrokerReportsRestrictedScopeAuditTest(unittest.TestCase):
    def test_table_taxonomy_keeps_projection_form_and_table_classes_distinct(self):
        self.assertEqual(
            classify_table_candidate(
                inferred_role="source_broker_report",
                projection_validation_status="validated",
                cell_count=40,
                word_count=80,
            )[0],
            "canonical_projection_already_exists",
        )
        self.assertEqual(
            classify_table_candidate(
                inferred_role="withholding_report",
                projection_validation_status="blocked",
                cell_count=24,
                word_count=36,
            )[0],
            "false_positive_table_candidate",
        )
        self.assertEqual(
            classify_table_candidate(
                inferred_role="withholding_report",
                projection_validation_status="blocked",
                cell_count=42,
                word_count=53,
            )[0],
            "text_layout_complete_topology_unresolved",
        )

    def test_visual_taxonomy_requires_bounded_recovery_only_without_text(self):
        self.assertEqual(
            classify_visual_unit(
                unit_type="visual_media",
                inferred_role="source_broker_report",
                page_number=None,
                sibling_text_characters=0,
            )[0],
            "non_material_visual_content",
        )
        self.assertEqual(
            classify_visual_unit(
                unit_type="pdf_visual_page_unit",
                inferred_role="operations_table",
                page_number=1,
                sibling_text_characters=120,
            )[0],
            "visual_fallback_with_text_layout",
        )
        self.assertEqual(
            classify_visual_unit(
                unit_type="pdf_visual_page_unit",
                inferred_role="tax_source_document",
                page_number=1,
                sibling_text_characters=0,
            )[0],
            "visual_only_material_table",
        )
        self.assertEqual(
            classify_visual_unit(
                unit_type="pdf_visual_page_unit",
                inferred_role="dividends_report",
                page_number=12,
                sibling_text_characters=0,
            )[0],
            "non_material_visual_content",
        )

    def test_geometry_metrics_detect_overlap_without_exposing_coordinates(self):
        exact = bbox_relationship([0, 0, 10, 10], [0, 0, 10, 10])
        separate = bbox_relationship([0, 0, 10, 10], [11, 0, 20, 10])
        contained = bbox_relationship([0, 0, 10, 10], [2, 2, 4, 4])
        self.assertEqual(exact["iou"], 1.0)
        self.assertEqual(separate["iou"], 0.0)
        self.assertEqual(contained["containment"], 1.0)

    def test_xml_coverage_separates_metadata_from_financial_values(self):
        rows = [
            ["event_ordinal", "depth", "event_type", "node_path", "name", "attribute_name", "value"],
            [1, 1, "attribute", "/x", "x", "СумДоход", "10.50"],
            [2, 1, "attribute", "/x", "x", "НомСпр", "ABC-7"],
        ]
        result = xml_value_coverage(xml_rows=rows, pdf_text="amount 10.50")
        self.assertEqual(result["values_total"], 2)
        self.assertEqual(result["values_matched_in_pdf_layout"], 1)
        self.assertEqual(result["unmatched_metadata_values"], 1)
        self.assertEqual(result["unmatched_financial_values"], 0)

    def test_safe_output_guard_rejects_private_identity_and_paths(self):
        assert_safe_output({"opaque_document_id": "document_123", "count": 1})
        with self.assertRaisesRegex(RuntimeError, "unsafe_safe_output"):
            assert_safe_output({"document": "brdoc_001_private"})
        with self.assertRaisesRegex(RuntimeError, "unsafe_safe_output"):
            assert_safe_output({"location": "C:\\private\\source.pdf"})

    def test_audit_retains_factory_and_non_promotion_anchors(self):
        self.assertIn("ArtifactStoreFactory.create", FACTORY_REQUIRED)
        self.assertIn("Gate2InputReadinessFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not", FORBIDDEN)
        self.assertIn("provider", FORBIDDEN)
        self.assertIn("promote", FORBIDDEN)


if __name__ == "__main__":
    unittest.main()
