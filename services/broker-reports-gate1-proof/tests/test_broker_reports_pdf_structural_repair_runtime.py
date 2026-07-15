from __future__ import annotations

import copy
import hashlib
import unittest

from broker_reports_gate1.pdf_dual_oracle_contracts import (
    PdfDualOracleContractFactory,
)
from broker_reports_gate1.pdf_hybrid_contracts import sha256_json
from broker_reports_gate1.pdf_grid_experiment_provider import PdfGridProviderError
from broker_reports_gate1.pdf_parser_geometry import PdfParserGeometryFactory
from broker_reports_gate1.pdf_structural_repair_runtime import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PdfStructuralRepairRuntime,
    PdfStructuralRepairRuntimeConfig,
    PdfStructuralRepairRuntimeError,
    PdfStructuralRepairRuntimeFactory,
)
from broker_reports_gate1.pdf_visual_topology import (
    PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
    PdfVisualTopologyFactory,
)


class _Provider:
    def __init__(self, *, counted_tokens: int = 100) -> None:
        self.counted_tokens = counted_tokens
        self.count_calls = 0
        self.generate_calls = 0
        self.package_id = ""

    def qualify(self) -> dict:
        return {
            "status": "qualified",
            "provider_profile": "google_gemini",
            "requested_model_id": "models/gemini-3.5-flash",
            "resolved_model_id": "models/gemini-3.5-flash",
            "exact_model_match": True,
            "image_input_supported": True,
            "structured_output_supported": True,
            "maximum_input_tokens": 1_000_000,
            "maximum_output_tokens": 65_536,
            "hidden_retry": False,
            "provider_failover": False,
        }

    def count_tokens(self, **kwargs) -> dict:
        self.count_calls += 1
        return {
            "total_tokens": self.counted_tokens,
            "model_requested": "models/gemini-3.5-flash",
            "within_hard_guard": True,
        }

    def invoke(
        self,
        *,
        task_id: str,
        attempt_number: int,
        attempt_lineage: list[str],
        **kwargs,
    ) -> dict:
        self.generate_calls += 1
        attempt_id = f"{task_id}_a{attempt_number}"
        return {
            "attempt": {
                "task_id": task_id,
                "attempt_id": attempt_id,
                "attempt_number": attempt_number,
                "attempt_lineage": list(attempt_lineage),
                "model_requested": "models/gemini-3.5-flash",
                "model_resolved": "models/gemini-3.5-flash",
                "started_at": f"2026-07-14T00:00:0{attempt_number}Z",
                "usage": {
                    "input_tokens": self.counted_tokens,
                    "output_tokens": 20,
                    "total_tokens": self.counted_tokens + 20,
                },
                "finish_reason": "STOP",
                "terminal_failure_class": None,
                "hidden_retry": False,
                "provider_failover": False,
            },
            "json_output": _topology_response(self.package_id),
            "raw_private_response": {"private": "provider-boundary"},
            "visible_output_bytes": 100,
            "response_bytes": 200,
        }


class _BudgetErrorProvider(_Provider):
    def count_tokens(self, **kwargs) -> dict:
        self.count_calls += 1
        raise PdfGridProviderError(
            "pdf_grid_provider_counted_input_budget_exceeded",
            "context_budget",
            safe_details={
                "observed_total_tokens": 21_337,
                "maximum_counted_input_tokens": 20_000,
            },
        )


class PdfStructuralRepairRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        contracts = PdfDualOracleContractFactory().create()
        self.projection = _projection()
        self.observation = contracts.build_parser_observation_from_word_atoms(
            document_ref="document-1",
            pdf_sha256="pdf-sha",
            page_ref="page-1",
            page_number=1,
            table_ref="table-1",
            table_bbox=[0.0, 0.0, 200.0, 100.0],
            pdf_text_layer_projection=self.projection,
        )
        self.geometry = PdfParserGeometryFactory().create().build_observation(
            document_ref="document-1",
            pdf_sha256="pdf-sha",
            page_ref="page-1",
            page_number=1,
            table_ref="table-1",
            table_bbox=[0.0, 0.0, 200.0, 100.0],
            pdf_text_layer_projection=self.projection,
        )
        self.png_bytes = b"lossless-test-png"
        self.crop = _crop_manifest(self.png_bytes)
        self.package = PdfVisualTopologyFactory().create().build_package(
            parser_observation=self.observation,
            crop_manifest=self.crop,
        )

    def test_factory_runtime_executes_exact_two_attempt_terminal(self) -> None:
        provider = _Provider()
        provider.package_id = self.package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        qualification = runtime.qualify_provider()

        result = runtime.run_target(
            target_id="regression_001",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=qualification,
        )

        self.assertEqual("accepted_unique_consensus", result["runtime_terminal_status"])
        self.assertEqual(2, provider.count_calls)
        self.assertEqual(2, provider.generate_calls)
        self.assertEqual(2, result["new_provider_count_token_calls"])
        self.assertEqual(2, result["new_provider_generate_calls"])
        self.assertEqual(2, len(result["journal"]))
        self.assertIsNotNone(result["accepted_binding"])
        self.assertEqual(2, result["materialization"]["row_count"])
        self.assertEqual(2, result["materialization"]["column_count"])
        self.assertEqual(0, result["materialization"]["model_invented_values_total"])
        self.assertTrue(result["safe_summary"]["all_candidates_accounted"])
        self.assertFalse(result["safe_summary"]["production_authority"])
        self.assertEqual([], runtime.validate_result(result))

    def test_counted_input_budget_blocks_before_generate(self) -> None:
        provider = _Provider(counted_tokens=20_001)
        provider.package_id = self.package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_target(
            target_id="regression_oversized",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual("preflight_blocked", result["runtime_terminal_status"])
        self.assertEqual(1, provider.count_calls)
        self.assertEqual(0, provider.generate_calls)
        self.assertEqual(
            ["pdf_structural_repair_counted_input_budget_exceeded"],
            result["safe_summary"]["reason_codes"],
        )

    def test_provider_budget_error_preserves_safe_observed_count(self) -> None:
        provider = _BudgetErrorProvider()
        provider.package_id = self.package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)

        result = runtime.run_target(
            target_id="provider_budget_detail",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertEqual("preflight_blocked", result["runtime_terminal_status"])
        self.assertEqual(0, provider.generate_calls)
        self.assertEqual(
            [21_337], result["safe_summary"]["counted_input_tokens"]
        )
        self.assertEqual(
            21_337,
            result["journal"][0]["count_tokens"]["total_tokens"],
        )
        self.assertFalse(
            result["journal"][0]["count_tokens"]["within_hard_guard"]
        )

    def test_private_provider_response_is_not_copied_to_safe_summary(self) -> None:
        provider = _Provider()
        provider.package_id = self.package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        result = runtime.run_target(
            target_id="regression_private_boundary",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        self.assertIn("provider-boundary", repr(result["journal"]))
        self.assertNotIn("provider-boundary", repr(result["safe_summary"]))
        self.assertNotIn("alpha-private", repr(result["safe_summary"]))

    def test_result_checksum_and_safe_ref_fail_closed(self) -> None:
        provider = _Provider()
        provider.package_id = self.package["package_id"]
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        result = runtime.run_target(
            target_id="regression_checksum",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )
        tampered = copy.deepcopy(result)
        tampered["safe_summary"]["generate_calls"] = 99

        self.assertIn(
            "pdf_structural_repair_result_checksum_invalid",
            runtime.validate_result(tampered),
        )

    def test_runtime_constructor_requires_factory(self) -> None:
        self.assertIn("PdfStructuralRepairRuntimeFactory.create", FACTORY_REQUIRED)
        self.assertIn("continuation groups must not trigger new provider calls", FORBIDDEN)
        with self.assertRaisesRegex(
            PdfStructuralRepairRuntimeError,
            "pdf_structural_repair_runtime_factory_required",
        ):
            PdfStructuralRepairRuntime(
                PdfStructuralRepairRuntimeConfig(),
                provider=_Provider(),
            )

    def test_continuation_group_joins_two_accepted_fragments_without_provider_calls(
        self,
    ) -> None:
        provider = _Provider()
        runtime = PdfStructuralRepairRuntimeFactory().create(provider=provider)
        provider.package_id = self.package["package_id"]
        first = runtime.run_target(
            target_id="continuation_fragment_1",
            parser_observation=self.observation,
            parser_geometry_observation=self.geometry,
            visual_package=self.package,
            png_bytes=self.png_bytes,
            provider_qualification=runtime.qualify_provider(),
        )

        second_projection = _projection(
            page_ref="page-2",
            values=(
                ("epsilon-private", [10.0, 10.0, 90.0, 40.0]),
                ("zeta-private", [110.0, 10.0, 190.0, 40.0]),
                ("eta-private", [10.0, 60.0, 90.0, 90.0]),
                ("theta-private", [110.0, 60.0, 190.0, 90.0]),
            ),
        )
        contracts = PdfDualOracleContractFactory().create()
        second_observation = contracts.build_parser_observation_from_word_atoms(
            document_ref="document-1",
            pdf_sha256="pdf-sha",
            page_ref="page-2",
            page_number=2,
            table_ref="table-2",
            table_bbox=[0.0, 0.0, 200.0, 100.0],
            pdf_text_layer_projection=second_projection,
        )
        second_geometry = PdfParserGeometryFactory().create().build_observation(
            document_ref="document-1",
            pdf_sha256="pdf-sha",
            page_ref="page-2",
            page_number=2,
            table_ref="table-2",
            table_bbox=[0.0, 0.0, 200.0, 100.0],
            pdf_text_layer_projection=second_projection,
        )
        second_png = b"lossless-test-png-page-2"
        second_package = PdfVisualTopologyFactory().create().build_package(
            parser_observation=second_observation,
            crop_manifest=_crop_manifest(
                second_png,
                crop_id="crop-2",
                page_number=2,
                table_ref="table-2",
            ),
        )
        provider.package_id = second_package["package_id"]
        second = runtime.run_target(
            target_id="continuation_fragment_2",
            parser_observation=second_observation,
            parser_geometry_observation=second_geometry,
            visual_package=second_package,
            png_bytes=second_png,
            provider_qualification=runtime.qualify_provider(),
        )
        calls_before_join = (provider.count_calls, provider.generate_calls)

        joined = runtime.run_continuation_group(
            continuation_group_id="continuation_group_1_2",
            fragments=[
                {
                    "target_id": "continuation_fragment_1",
                    "parser_observation": self.observation,
                    "visual_package": self.package,
                    "runtime_result": first,
                    "repeat_history_ever_conflicted": False,
                },
                {
                    "target_id": "continuation_fragment_2",
                    "parser_observation": second_observation,
                    "visual_package": second_package,
                    "runtime_result": second,
                    "repeat_history_ever_conflicted": False,
                },
            ],
        )

        self.assertEqual((4, 4), calls_before_join)
        self.assertEqual(calls_before_join, (provider.count_calls, provider.generate_calls))
        self.assertEqual("accepted_unique_consensus", joined["runtime_terminal_status"])
        self.assertEqual(0, joined["new_provider_count_token_calls"])
        self.assertEqual(0, joined["new_provider_generate_calls"])
        self.assertEqual(2, len(joined["fragment_evidence"]))
        self.assertEqual(
            "broker_reports_pdf_dual_oracle_continuation_consensus_v2",
            joined["continuation_consensus_result"]["schema_version"],
        )
        self.assertEqual(4, joined["materialization"]["row_count"])
        self.assertEqual(2, joined["materialization"]["column_count"])
        self.assertTrue(joined["materialization"]["candidate_ownership_exact"])
        self.assertEqual(0, joined["materialization"]["model_invented_values_total"])
        self.assertTrue(joined["safe_summary"]["all_candidates_accounted"])
        self.assertNotIn("alpha-private", repr(joined["safe_summary"]))
        self.assertNotIn("epsilon-private", repr(joined["safe_summary"]))
        self.assertEqual([], runtime.validate_continuation_group_result(joined))


def _topology_response(package_id: str) -> dict:
    return {
        "schema_version": PDF_VISUAL_TOPOLOGY_RESPONSE_SCHEMA,
        "package_id": package_id,
        "decision": "bound",
        "alternatives_complete": True,
        "hypotheses": [
            {
                "hypothesis_key": "primary",
                "row_boundaries": [0.0, 0.5, 1.0],
                "column_boundaries": [0.0, 0.5, 1.0],
                "header_row_count": 1,
                "spans": [],
                "header_hierarchy": [],
                "continuation_required": False,
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _projection(
    *,
    page_ref: str = "page-1",
    values: tuple[tuple[str, list[float]], ...] = (
        ("alpha-private", [10.0, 10.0, 90.0, 40.0]),
        ("beta-private", [110.0, 10.0, 190.0, 40.0]),
        ("gamma-private", [10.0, 60.0, 90.0, 90.0]),
        ("delta-private", [110.0, 60.0, 190.0, 90.0]),
    ),
) -> dict:
    bboxes = []
    words = []
    for ordinal, (text, bbox) in enumerate(values, start=1):
        bbox_ref = f"bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        words.append(
            {
                "parser_ordinal": ordinal,
                "word_ref": f"word-{ordinal}",
                "page_ref": page_ref,
                "bbox_ref": bbox_ref,
                "text": text,
                "geometry_reading_order": ordinal,
                "text_checksum_ref": f"text-checksum-{ordinal}",
                "source_value_ref": f"source-{ordinal}",
            }
        )
    vector_specs = (
        [0.0, 0.0, 0.0, 100.0],
        [100.0, 0.0, 100.0, 100.0],
        [200.0, 0.0, 200.0, 100.0],
        [0.0, 0.0, 200.0, 0.0],
        [0.0, 50.0, 200.0, 50.0],
        [0.0, 100.0, 200.0, 100.0],
    )
    vectors = []
    for ordinal, bbox in enumerate(vector_specs, start=1):
        bbox_ref = f"vector-bbox-{ordinal}"
        bboxes.append({"bbox_ref": bbox_ref, "bbox": list(bbox)})
        vectors.append(
            {
                "parser_ordinal": ordinal,
                "object_ref": f"vector-{ordinal}",
                "page_ref": page_ref,
                "bbox_ref": bbox_ref,
                "linewidth": 0.5,
            }
        )
    return {
        "bbox_inventory": bboxes,
        "word_inventory": words,
        "line_inventory": [],
        "vector_line_inventory": vectors,
        "rect_inventory": [],
    }


def _crop_manifest(
    png_bytes: bytes,
    *,
    crop_id: str = "crop-1",
    page_number: int = 1,
    table_ref: str = "table-1",
) -> dict:
    value = {
        "schema_version": "broker_reports_pdf_table_crop_v1",
        "policy_version": "pdf_table_raster_policy_v1",
        "crop_id": crop_id,
        "document_ref": "document-1",
        "pdf_sha256": "pdf-sha",
        "page_number": page_number,
        "table_ref": table_ref,
        "declared_table_bbox": [0.0, 0.0, 200.0, 100.0],
        "rendered_bbox": [0.0, 0.0, 200.0, 100.0],
        "source_coordinate_space": "pdf_top_left_points",
        "pixel_coordinate_space": "crop_top_left_pixels",
        "source_to_pixel_transform": {
            "scale_x": 2.0,
            "scale_y": 2.0,
            "translate_source_x": 0.0,
            "translate_source_y": 0.0,
        },
        "renderer": "pymupdf",
        "renderer_version": "1.26.5",
        "page_rotation": 0,
        "applied_rotation": 0,
        "padding_points": 0.0,
        "dpi": 150,
        "dpi_revision_reason": "primary_150_dpi",
        "width": 400,
        "height": 200,
        "pixels": 80_000,
        "png_bytes": len(png_bytes),
        "png_sha256": hashlib.sha256(png_bytes).hexdigest(),
        "lossless": True,
        "silent_resize_performed": False,
    }
    value["manifest_hash"] = sha256_json(value)
    return value


if __name__ == "__main__":
    unittest.main()
