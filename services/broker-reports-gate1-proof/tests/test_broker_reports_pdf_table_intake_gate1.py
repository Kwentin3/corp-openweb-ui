from __future__ import annotations

import base64
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.gate2_handoff import persist_gate1_result
from broker_reports_gate1.inputs import FileInput
from broker_reports_gate1.normalizer import Gate1Normalizer
from broker_reports_gate1.pdf_table_intake_runtime import (
    PDF_TABLE_DETECTION_RESPONSE_SCHEMA,
    PdfTableIntakeConfig,
    PdfTableIntakeError,
    PdfTableIntakeRuntimeFactory,
    validate_table_detection_output,
)
from broker_reports_gate1.pdf_table_raster import (
    PdfTableRasterConfig,
    PdfTableRasterError,
    PdfTableRasterFactory,
)

def _single_page_pdf(*, width: float = 100, height: float = 200) -> bytes:
    document = fitz.open()
    page = document.new_page(width=width, height=height)
    page.draw_rect(fitz.Rect(20, 40, 80, 160), color=(0, 0, 0), width=1)
    page.insert_text((25, 60), "A  1  2")
    page.insert_text((25, 90), "B  3  4")
    data = document.tobytes(deflate=True)
    document.close()
    return data


class StaticDetectorProvider:
    def __init__(self, regions: list[list[float]], *, malformed: bool = False) -> None:
        self.regions = regions
        self.malformed = malformed

    def qualify(self):
        return {
            "status": "qualified",
            "provider_profile": "google_gemini",
            "provider_profile_revision": "test-profile-v1",
            "requested_model_id": "models/gemini-3.5-flash",
            "resolved_model_id": "models/gemini-3.5-flash",
            "exact_model_match": True,
            "image_input_supported": True,
            "structured_output_supported": True,
            "response_hash": "qualification-response-hash",
            "native_provider_transport": True,
            "credentials_from_openwebui_connection": True,
            "hidden_retry": False,
            "provider_failover": False,
        }

    def count_tokens(self, **kwargs):
        return {
            "total_tokens": 100,
            "request_hash": "token-request-hash",
            "response_hash": "token-response-hash",
            "within_hard_guard": True,
        }

    def invoke(self, **kwargs):
        request_id = kwargs["model_view"]["request_id"]
        value = {
            "schema_version": PDF_TABLE_DETECTION_RESPONSE_SCHEMA,
            "request_id": request_id,
            "table_presence": "present" if self.regions else "absent",
            "regions": [
                {"bbox_normalized": list(region)} for region in self.regions
            ],
        }
        if self.malformed:
            value["semantic_summary"] = "forbidden"
        return {
            "attempt": {
                "terminal_failure_class": None,
                "provider_profile": "google_gemini",
                "provider_profile_revision": "test-profile-v1",
                "model_requested": "models/gemini-3.5-flash",
                "model_resolved": "models/gemini-3.5-flash",
                "adapter_identity": "test-detector-adapter-v1",
                "request_hash": "provider-request-hash",
                "hidden_retry": False,
                "provider_failover": False,
            },
            "json_output": value,
            "raw_private_response": {"test": True},
            "response_hash": "provider-response-hash",
        }


class PdfTableDetectionContractTest(unittest.TestCase):
    def test_detector_output_is_strict_and_order_is_deterministic(self):
        value = {
            "schema_version": PDF_TABLE_DETECTION_RESPONSE_SCHEMA,
            "request_id": "request-1",
            "table_presence": "present",
            "regions": [
                {"bbox_normalized": [0.5, 0.6, 0.9, 0.9]},
                {"bbox_normalized": [0.1, 0.1, 0.4, 0.3]},
            ],
        }
        self.assertEqual(
            [[0.1, 0.1, 0.4, 0.3], [0.5, 0.6, 0.9, 0.9]],
            validate_table_detection_output(
                value, request_id="request-1", maximum_candidates=8
            ),
        )

    def test_detector_request_requires_outer_boundary_not_data_only_box(self):
        model_view = PdfTableIntakeRuntimeFactory(
            PdfTableIntakeConfig(enabled=True)
        ).create_with_provider(StaticDetectorProvider([]))._model_view(
            request_id="request-1", page_number=1
        )
        instructions = " ".join(model_view["instructions"])
        self.assertIn("OUTER boundary", instructions)
        self.assertIn("leftmost row label or first column", instructions)
        self.assertIn("complete visible continuation", instructions)
        self.assertIn("padding is only a safety margin", instructions)

    def test_detector_rejects_semantics_uncertainty_and_ambiguous_regions(self):
        base = {
            "schema_version": PDF_TABLE_DETECTION_RESPONSE_SCHEMA,
            "request_id": "request-1",
            "table_presence": "present",
            "regions": [{"bbox_normalized": [0.1, 0.1, 0.8, 0.8]}],
        }
        with self.assertRaisesRegex(
            PdfTableIntakeError, "pdf_table_detector_output_shape_invalid"
        ):
            validate_table_detection_output(
                {**base, "rows": []}, request_id="request-1", maximum_candidates=8
            )
        with self.assertRaisesRegex(
            PdfTableIntakeError, "pdf_table_detector_boundary_uncertain"
        ):
            validate_table_detection_output(
                {**base, "table_presence": "uncertain", "regions": []},
                request_id="request-1",
                maximum_candidates=8,
            )
        with self.assertRaisesRegex(
            PdfTableIntakeError, "pdf_table_detector_regions_ambiguous"
        ):
            validate_table_detection_output(
                {
                    **base,
                    "regions": [
                        {"bbox_normalized": [0.1, 0.1, 0.8, 0.8]},
                        {"bbox_normalized": [0.11, 0.11, 0.79, 0.79]},
                    ],
                },
                request_id="request-1",
                maximum_candidates=8,
            )


class PdfTableRasterCandidateTest(unittest.TestCase):
    def test_global_eight_percent_padding_is_exact_clamped_and_repeatable(self):
        pdf_bytes = _single_page_pdf()
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        renderer = PdfTableRasterFactory().create()
        kwargs = {
            "pdf_bytes": pdf_bytes,
            "pdf_sha256": pdf_sha256,
            "document_ref": "doc-1",
            "page_number": 1,
            "candidate_ref": "candidate-1",
            "detected_bbox_normalized": [0.2, 0.2, 0.8, 0.8],
            "detector_contract_version": PDF_TABLE_DETECTION_RESPONSE_SCHEMA,
            "detector_identity": {"model": "test"},
        }
        first = renderer.render_detected_region(**kwargs)
        second = renderer.render_detected_region(**kwargs)
        manifest = first["manifest"]
        self.assertEqual([20.0, 40.0, 80.0, 160.0], manifest["declared_table_bbox"])
        self.assertEqual([12.0, 24.0, 88.0, 176.0], manifest["rendered_bbox"])
        self.assertEqual(8.0, manifest["padding_x_points"])
        self.assertEqual(16.0, manifest["padding_y_points"])
        self.assertEqual(0.08, manifest["horizontal_padding_fraction"])
        self.assertEqual(0.08, manifest["vertical_padding_fraction"])
        self.assertEqual(first, second)
        self.assertEqual(
            manifest["png_sha256"],
            hashlib.sha256(base64.b64decode(first["private_png_base64"])).hexdigest(),
        )

        edge = renderer.render_detected_region(
            **{**kwargs, "detected_bbox_normalized": [0.01, 0.01, 0.4, 0.4]}
        )
        self.assertEqual([0.0, 0.0, 48.0, 96.0], edge["manifest"]["rendered_bbox"])

    def test_independent_padding_config_and_invalid_config_fail_closed(self):
        pdf_bytes = _single_page_pdf()
        renderer = PdfTableRasterFactory(
            PdfTableRasterConfig(
                horizontal_padding_fraction=0.08,
                vertical_padding_fraction=0.04,
            )
        ).create()
        rendered = renderer.render_detected_region(
            pdf_bytes=pdf_bytes,
            pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            document_ref="doc-1",
            page_number=1,
            candidate_ref="candidate-1",
            detected_bbox_normalized=[0.2, 0.2, 0.8, 0.8],
            detector_contract_version=PDF_TABLE_DETECTION_RESPONSE_SCHEMA,
            detector_identity={"model": "test"},
        )
        self.assertEqual([12.0, 32.0, 88.0, 168.0], rendered["manifest"]["rendered_bbox"])
        with self.assertRaisesRegex(
            PdfTableRasterError, "pdf_table_raster_padding_fraction_invalid"
        ):
            PdfTableRasterFactory(
                PdfTableRasterConfig(horizontal_padding_fraction=0.5)
            ).create()


class PdfTableIntakeRuntimeTest(unittest.TestCase):
    def test_runtime_produces_deterministic_gate2_raster_candidate(self):
        pdf_bytes = _single_page_pdf()
        config = PdfTableIntakeConfig(enabled=True)
        runtime = PdfTableIntakeRuntimeFactory(config).create_with_provider(
            StaticDetectorProvider([[0.2, 0.2, 0.8, 0.8]])
        )
        documents = [
            {
                "document_ref": "doc-1",
                "pdf_bytes": pdf_bytes,
                "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            }
        ]
        first = runtime.run(documents)
        second = runtime.run(documents)
        self.assertEqual("completed", first.safe_summary["status"])
        self.assertTrue(first.safe_summary["gate2_boundary_ready"])
        self.assertEqual(1, first.safe_summary["candidates_total"])
        self.assertFalse(first.safe_summary["rows_columns_cells_inferred"])
        self.assertFalse(first.safe_summary["financial_semantics_inferred"])
        self.assertEqual(first.private_candidates, second.private_candidates)
        self.assertEqual(
            "gate2_raster_candidate",
            first.private_candidates[0]["manifest"]["downstream_contract"],
        )

    def test_invalid_detector_terminal_has_no_success_candidate(self):
        pdf_bytes = _single_page_pdf()
        runtime = PdfTableIntakeRuntimeFactory(
            PdfTableIntakeConfig(enabled=True)
        ).create_with_provider(
            StaticDetectorProvider([[0.2, 0.2, 0.8, 0.8]], malformed=True)
        )
        result = runtime.run(
            [
                {
                    "document_ref": "doc-1",
                    "pdf_bytes": pdf_bytes,
                    "pdf_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                }
            ]
        )
        self.assertEqual("failed", result.safe_summary["status"])
        self.assertFalse(result.safe_summary["gate2_boundary_ready"])
        self.assertEqual([], result.private_candidates)
        self.assertEqual([], result.private_detection_attempts)
        self.assertEqual(
            "pdf_table_detector_output_shape_invalid",
            result.safe_summary["failed_pages"][0]["failure_code"],
        )

    def test_candidate_is_persisted_and_exposed_in_gate2_handoff(self):
        pdf_bytes = _single_page_pdf()
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        result = Gate1Normalizer().normalize(
            [
                FileInput(
                    private_ref="file-1",
                    original_filename_private="table.pdf",
                    mime_type="application/pdf",
                    source_kind="unit_test",
                    declared_size_bytes=len(pdf_bytes),
                    bytes_provider=lambda: pdf_bytes,
                    provider_label="unit_test",
                )
            ],
            entrypoint="unit_test",
            trigger_type="unit_test",
        )
        intake = PdfTableIntakeRuntimeFactory(
            PdfTableIntakeConfig(enabled=True)
        ).create_with_provider(
            StaticDetectorProvider([[0.2, 0.2, 0.8, 0.8]])
        ).run(
            [
                {
                    "document_ref": result.package["document_inventory"]["documents"][0][
                        "document_id"
                    ],
                    "pdf_bytes": pdf_bytes,
                    "pdf_sha256": pdf_sha256,
                }
            ]
        )
        result.package["pdf_table_intake"] = intake.safe_summary
        result.package["private_pdf_table_candidates"] = intake.private_candidates
        result.package["private_pdf_table_detection_attempts"] = (
            intake.private_detection_attempts
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=root / "artifacts.sqlite3",
                    payload_root=root / "payloads",
                )
            ).create()
            context = ArtifactAccessContext(
                user_id="user-1",
                normalization_run_id=result.package["normalization_run"]["run_id"],
                case_id="case-1",
                chat_id="chat-1",
                workspace_model_id="broker_reports_gate1_pipe",
                allow_private=True,
            )
            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(
                    mode="api_smoke", explicit=True, ttl_seconds=3600
                ),
                source_file_refs=[
                    {
                        "provider": "unit_test",
                        "openwebui_file_id": "file-1",
                        "content_type": "application/pdf",
                        "size_bytes": len(pdf_bytes),
                    }
                ],
            )
            self.assertEqual(1, len(manifest.pdf_table_candidate_refs))
            self.assertEqual(1, len(manifest.pdf_table_detection_attempt_refs))
            candidate_record = store.get_record_unchecked(
                manifest.pdf_table_candidate_refs[0]
            )
            self.assertIsNotNone(candidate_record)
            candidate = store.read_payload(candidate_record)
            self.assertEqual(
                candidate["manifest"]["png_sha256"],
                hashlib.sha256(
                    base64.b64decode(candidate["private_png_base64"])
                ).hexdigest(),
            )
            handoff_record = store.get_record_unchecked(manifest.gate2_handoff_ref)
            self.assertIsNotNone(handoff_record)
            handoff = store.read_payload(handoff_record)
            self.assertTrue(handoff["pdf_table_intake_contract"]["gate2_boundary_ready"])
            self.assertEqual(
                manifest.pdf_table_candidate_refs,
                handoff["pdf_table_candidate_refs"],
            )


class PdfTableIntakeFactoryBoundaryTest(unittest.TestCase):
    def test_pipe_and_bundle_builder_use_maintained_factory_path(self):
        pipe_source = (
            ROOT / "openwebui_actions" / "broker_reports_gate1_pipe.py"
        ).read_text(encoding="utf-8")
        runtime_source = (
            ROOT / "broker_reports_gate1" / "pdf_table_intake_runtime.py"
        ).read_text(encoding="utf-8")
        bundle_builder = (
            ROOT / "scripts" / "build_openwebui_pipe_bundle.py"
        ).read_text(encoding="utf-8")
        self.assertIn("PdfTableIntakeRuntimeFactory(config)", pipe_source)
        self.assertNotIn("GeminiGridExperimentAdapter(", pipe_source)
        self.assertIn("FACTORY_REQUIRED", runtime_source)
        self.assertIn("FORBIDDEN", runtime_source)
        self.assertIn('"pdf_table_intake_runtime"', bundle_builder)


if __name__ == "__main__":
    unittest.main()
