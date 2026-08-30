from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_broker_reports_pdf_layout_slice2 import _ruled_table_pdf


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BUNDLE = ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
FIXTURES = REPO / "docs" / "stage2" / "testdata" / "broker_reports_gate1_normalization"


def run_pipe(pipe, body: dict, **kwargs) -> str:
    kwargs.setdefault("__user__", {"id": "bundle-test-user"})
    kwargs.setdefault(
        "__metadata__",
        {
            "chat_id": "bundle-test-chat",
            "model_id": "broker_reports_gate1_pipe_bundle_test",
        },
    )
    return asyncio.run(pipe.pipe(body, **kwargs))


def file_ref(file_id: str, filename: str, mime_type: str, content: bytes):
    return {
        "type": "file",
        "file": {
            "id": file_id,
            "filename": filename,
            "mime_type": mime_type,
            "content_bytes": content,
        },
    }


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _broker_reports_modules() -> dict[str, object]:
    return {
        name: module
        for name, module in sys.modules.items()
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1.")
    }


def _clear_broker_reports_modules() -> None:
    for name in list(sys.modules):
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1."):
            del sys.modules[name]


def load_bundle_module():
    _clear_broker_reports_modules()
    spec = importlib.util.spec_from_file_location(
        "broker_reports_gate1_pipe_bundled_under_test",
        BUNDLE,
    )
    if spec is None or spec.loader is None:
        raise AssertionError("could not create import spec for bundled pipe")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BrokerReportsGate1PipeBundleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._maintained_modules = _broker_reports_modules()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def tearDown(self) -> None:
        _clear_broker_reports_modules()
        sys.modules.update(self._maintained_modules)

    def test_bundled_pipe_runs_backend_normalizer_without_repo_package_import(self):
        source = BUNDLE.read_text(encoding="utf-8")
        self.assertIn("_BUNDLED_MODULES", source)
        self.assertNotIn("pipe_stub", source)
        self.assertIn(
            "requirements: pydantic,pypdf==6.7.5,pdfplumber==0.11.10,pdfminer.six==20260107",
            source,
        )
        module = load_bundle_module()
        self.assertEqual(
            "gate1_ordinary_trade_production_v9",
            module._BUNDLED_PACKAGE_VERSION,
        )
        self.assertIn("gate3_ndfl_workflow", module._BUNDLED_MODULES)
        self.assertIn("gate4_financial_case_materialization", module._BUNDLED_MODULES)
        self.assertIn("gate4_financial_case_cache", module._BUNDLED_MODULES)
        self.assertIn("gate5_real_tax_case_assembly", module._BUNDLED_MODULES)
        self.assertIn("gate5_declaration_scope_resolution", module._BUNDLED_MODULES)
        self.assertIn("ordinary_trade_production_runtime", module._BUNDLED_MODULES)
        self.assertIn("ordinary_trade_qualified_mappings", module._BUNDLED_MODULES)
        self.assertLess(
            module._BUNDLED_MODULE_ORDER.index("gate5_real_tax_case_assembly"),
            module._BUNDLED_MODULE_ORDER.index("gate5_declaration_scope_resolution"),
        )
        self.assertIn(
            "gate3_financial_label_dictionary.v1.json",
            module._BUNDLED_RESOURCES,
        )
        self.assertIn(
            "gate3_financial_label_dictionary.v2.json",
            module._BUNDLED_RESOURCES,
        )
        self.assertIn(
            "gate3_labeling_response.v1.schema.json",
            module._BUNDLED_RESOURCES,
        )
        self.assertIn(
            "gate3_financial_role_pack.v1.json",
            module._BUNDLED_RESOURCES,
        )
        self.assertIn(
            "gate3_financial_role_pack.v2.json",
            module._BUNDLED_RESOURCES,
        )
        self.assertIn(
            "gate3_financial_role_pack.v3.json",
            module._BUNDLED_RESOURCES,
        )
        self.assertIn(
            "gate3_role_labeling_response.v1.schema.json",
            module._BUNDLED_RESOURCES,
        )
        self.assertIn(
            "gate5_consumer_first_xml_projection.ru_3ndfl_2025.v0.json",
            module._BUNDLED_RESOURCES,
        )
        self.assertIn(
            "gate5_tax_methodology.ru_3ndfl_2025_declaration_input_contract.v3.json",
            module._BUNDLED_RESOURCES,
        )
        self.assertIn(
            "gate5_tax_methodology.ru_3ndfl_2025_income_group_settlement.v1.json",
            module._BUNDLED_RESOURCES,
        )
        bundled_methodology = sys.modules[
            "broker_reports_gate1.gate5_trusted_methodology"
        ]
        resolved = bundled_methodology.Gate5TrustedMethodologyAuthorityFactory.create().resolve(
            {
                "schema_version": (
                    bundled_methodology.GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION
                ),
                "methodology_id": (
                    bundled_methodology.GATE5_DECLARATION_INPUT_METHODOLOGY_ID
                ),
                "methodology_version": (
                    bundled_methodology.GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION
                ),
            }
        )
        self.assertEqual(
            "PUBLISHED_CURRENT_AUTHORITY",
            resolved["methodology"]["status"],
        )
        bundled_projection = sys.modules[
            "broker_reports_gate1.gate5_full_target_xml_projection"
        ]
        consumer_definition = bundled_projection.Gate5ConsumerFirstXmlProjectionDefinitionAuthorityFactory.create().resolve()
        self.assertEqual(
            "ru_3ndfl_2025_consumer_first_supplied_case",
            consumer_definition["projection_id"],
        )
        self.assertIn(
            "gate2_economy_model_policy",
            module._BUNDLED_MODULES,
        )
        self.assertIn("gate2_economy_budget", module._BUNDLED_MODULES)
        self.assertNotIn(
            "gate2_financial_evidence_registry",
            module._BUNDLED_MODULES,
        )
        self.assertIn("pdf_layout", module._BUNDLED_MODULES)
        self.assertIn("pdf_layout_units", module._BUNDLED_MODULES)
        self.assertIn("pdf_text_layer", module._BUNDLED_MODULES)
        self.assertIn("pdf_compact_canonical", module._BUNDLED_MODULES)
        self.assertIn("pdf_compact_gate2_adapter", module._BUNDLED_MODULES)
        self.assertIn("pdf_normalization_acceptance", module._BUNDLED_MODULES)
        self.assertNotIn("visual_table_review_contracts", module._BUNDLED_MODULES)
        self.assertIn("pdf_table_locator_provider", module._BUNDLED_MODULES)
        self.assertIn("pdf_table_intake_runtime", module._BUNDLED_MODULES)
        self.assertIn("gate3_metadata_source_facts", module._BUNDLED_MODULES)
        self.assertIn("gate5_evidence_intake", module._BUNDLED_MODULES)
        self.assertIn("gate5_client_evidence_review", module._BUNDLED_MODULES)
        self.assertIn("gate5_human_gap_closure", module._BUNDLED_MODULES)
        self.assertIn(
            "ordinary_trade_declaration_chat_adapter", module._BUNDLED_MODULES
        )
        self.assertIn("gate5_declaration_preparation", module._BUNDLED_MODULES)
        retired_product_modules = {
            "pdf_visual_table_review",
            "pdf_hybrid_budget",
            "pdf_hybrid_compaction",
            "pdf_hybrid_windows",
            "pdf_hybrid_structure",
            "pdf_hybrid_reliability",
            "pdf_hybrid_reliability_shadow",
            "pdf_dual_oracle_contracts",
            "pdf_dual_oracle_consensus",
            "pdf_parser_geometry",
            "pdf_structural_row_windows",
            "pdf_visual_topology",
            "pdf_topology_assembly",
            "pdf_vlm_product_routing",
            "pdf_vlm_region_binding",
            "pdf_grid_experiment_provider",
            "pdf_dual_vlm_canonical_table_contracts",
            "pdf_dual_vlm_fact_providers",
            "pdf_dual_vlm_runtime",
            "semantic_visual_table_materialization",
            "semantic_visual_table_migration",
            "pdf_continuation_discovery",
            "pdf_structural_repair_runtime",
            "pdf_semantic_header_contracts",
            "pdf_semantic_header_projection",
            "pdf_structural_repair_shadow",
            "pdf_hybrid_shadow",
            "gate5_end_to_end_full_target_xml",
            "gate5_openwebui_product",
        }
        self.assertFalse(retired_product_modules & set(module._BUNDLED_MODULES))
        bundled_order = module._BUNDLED_MODULE_ORDER
        self.assertLess(
            bundled_order.index("pdf_text_layer"),
            bundled_order.index("table_projection"),
        )
        self.assertLess(
            bundled_order.index("pdf_table_locator_provider"),
            bundled_order.index("pdf_table_intake_runtime"),
        )
        self.assertLess(
            bundled_order.index("gate3_metadata_source_facts"),
            bundled_order.index("gate5_evidence_intake"),
        )
        self.assertLess(
            bundled_order.index("gate5_evidence_intake"),
            bundled_order.index("gate5_declaration_preparation"),
        )
        self.assertIn("source_provenance", module._BUNDLED_MODULES)
        self.assertIn("document_memory", module._BUNDLED_MODULES)
        self.assertIn("gate2_input_readiness", module._BUNDLED_MODULES)
        self.assertIn("gate2_source_fact_contracts", module._BUNDLED_MODULES)
        self.assertIn("gate2_model_contracts", module._BUNDLED_MODULES)
        self.assertIn("gate2_model_requests", module._BUNDLED_MODULES)
        self.assertIn("gate2_model_clients", module._BUNDLED_MODULES)
        self.assertIn("gate2_source_fact_validation", module._BUNDLED_MODULES)
        self.assertIn("gate2_source_fact_runtime", module._BUNDLED_MODULES)
        self.assertIn(
            "gate5_deterministic_source_fact_consumption", module._BUNDLED_MODULES
        )
        bundled_package = sys.modules["broker_reports_gate1"]
        self.assertTrue(hasattr(bundled_package, "NormalizedSliceProvenanceFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate1DocumentMemoryFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate2InputReadinessFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate2SourceFactRuntimeFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate2StructuredModelClientFactory"))
        self.assertTrue(hasattr(bundled_package, "WorkloadAuthorityFactory"))
        self.assertTrue(hasattr(bundled_package, "PdfTextLayerParserFactory"))
        self.assertTrue(hasattr(bundled_package, "PdfTableIntakeRuntimeFactory"))
        self.assertFalse(hasattr(bundled_package, "PdfDualVlmRuntimeFactory"))
        self.assertFalse(hasattr(bundled_package, "SemanticVisualTableMigrationFactory"))
        self.assertTrue(hasattr(bundled_package, "PdfLayoutUnitBuilder"))

        text_layer = sys.modules["broker_reports_gate1.pdf_text_layer"]
        layout_units = sys.modules["broker_reports_gate1.pdf_layout_units"]
        unit = {
            "pdf_unit_type": "pdf_table_candidate_unit",
            "pdf_layout_coverage": {
                "selected_source_refs": ["word-1", "line-1"],
                "fallback_text_refs": [],
            },
            "table_candidate_ref": "candidate-1",
            "layout_parser_ref": "parser-1",
            "layout_parser_config_ref": "config-1",
            "text": "Title",
            "table_title_binding": {"value": "Title"},
            "bound_header_row_count": 1,
        }
        unit["pdf_layout_unit_checksum_ref"] = (
            layout_units.pdf_layout_unit_checksum_ref(unit)
        )
        unit["table_title_binding"] = {"value": "Changed"}
        checksum_errors = text_layer.validate_pdf_source_unit_structure(unit)
        self.assertIn(
            "pdf_layout_source_unit_checksum_mismatch",
            {item["code"] for item in checksum_errors},
        )
        self.assertFalse(hasattr(bundled_package, "PdfStructuralRowWindowFactory"))
        self.assertTrue(hasattr(bundled_package, "PdfCompactCanonicalFactory"))
        self.assertTrue(hasattr(bundled_package, "PdfNormalizationAcceptanceFactory"))
        self.assertTrue(hasattr(bundled_package, "PdfCompactGate2AdapterFactory"))
        self.assertTrue(
            hasattr(
                bundled_package,
                "Gate5DeterministicSourceFactConsumptionRuntimeFactory",
            )
        )
        self.assertEqual(bundled_package.PDFPLUMBER_PINNED_VERSION, "0.11.10")
        self.assertEqual(bundled_package.PDFMINER_PINNED_VERSION, "20260107")
        pipe = module.Pipe()
        root = Path(self._tmp.name)
        pipe.valves.artifact_store_path = str(root / "artifacts.sqlite3")
        pipe.valves.artifact_payload_root = str(root / "payloads")

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "нормализуй",
                        "files": [
                            file_ref(
                                "bundle-txt-1",
                                "synthetic_broker_report.txt",
                                "text/plain",
                                fixture_bytes("synthetic_broker_report.txt"),
                            ),
                            file_ref(
                                "bundle-html-1",
                                "synthetic_broker_report.html",
                                "text/html",
                                fixture_bytes("synthetic_broker_report.html"),
                            ),
                            file_ref(
                                "bundle-csv-1",
                                "synthetic_operations.csv",
                                "text/csv",
                                fixture_bytes("synthetic_operations.csv"),
                            ),
                            file_ref(
                                "bundle-csv-2",
                                "synthetic_operations_duplicate.csv",
                                "text/csv",
                                fixture_bytes("synthetic_operations_duplicate.csv"),
                            ),
                            file_ref(
                                "bundle-unknown-1",
                                "synthetic_unknown.bin",
                                "application/octet-stream",
                                fixture_bytes("synthetic_unknown.bin"),
                            ),
                        ],
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertNotIn("```json", content)
        self.assertIn("Нормализация завершена с предупреждениями.", content)
        self.assertIsNotNone(pipe.last_artifact_manifest)
        self.assertEqual(report["trigger_type"], "pipe_backend_normalizer")
        self.assertEqual(report["normalizer_version"], module.NORMALIZER_VERSION)
        self.assertEqual(report["file_ref_visibility"], "visible")
        self.assertEqual(report["files_total"], 5)
        self.assertEqual(
            report["container_counts"],
            {"csv": 2, "html_text": 1, "txt": 1, "unknown": 1},
        )
        self.assertEqual(report["duplicate_count"], 1)
        self.assertEqual(report["validation_result"]["status"], "passed")
        self.assertIn(
            "unsupported_format", {item["code"] for item in report["blockers"]}
        )
        self.assertIn("duplicate_review", {item["code"] for item in report["blockers"]})
        self.assertFalse(report["safety_flags"]["source_fact_extraction_performed"])
        self.assertFalse(report["safety_flags"]["tax_correctness_claimed"])
        self.assertFalse(report["safety_flags"]["declaration_generated"])
        self.assertFalse(report["safety_flags"]["xlsx_generated"])
        self.assertFalse(report["safety_flags"]["ocr_performed"])
        self.assertNotIn("bundle-csv-1", content)
        self.assertNotIn("synthetic_operations.csv", content)
        self.assertNotIn("SYNTH-ACCOUNT-001", content)
        self.assertNotIn("SYNTH-A,1,SYNTH-FCY", content)
        self.assertNotIn('"rows"', content)
        self.assertNotIn('"text"', content)

    def test_bundled_pipe_defaults_to_source_bound_table_intake(self):
        module = load_bundle_module()
        pipe = module.Pipe()
        root = Path(self._tmp.name)
        pipe.valves.artifact_store_path = str(root / "compact.sqlite3")
        pipe.valves.artifact_payload_root = str(root / "compact-payloads")
        self.assertFalse(pipe.valves.pdf_compact_canonical_dual_write)
        self.assertTrue(pipe.valves.pdf_table_intake_enabled)
        self.assertFalse(hasattr(pipe.valves, "pdf_dual_vlm_enabled"))
        self.assertFalse(
            hasattr(pipe.valves, "pdf_semantic_visual_table_downstream_enabled")
        )
        self.assertEqual(0.08, pipe.valves.pdf_table_intake_horizontal_padding_fraction)
        self.assertEqual(0.08, pipe.valves.pdf_table_intake_vertical_padding_fraction)
        self.assertFalse(hasattr(pipe.valves, "pdf_hybrid_shadow_enabled"))
        self.assertFalse(hasattr(pipe.valves, "pdf_structural_repair_shadow_enabled"))
        self.assertFalse(hasattr(pipe.valves, "pdf_vlm_guided_intake_shadow_enabled"))
        self.assertFalse(hasattr(pipe.valves, "pdf_semantic_header_shadow_enabled"))
        pipe.valves.pdf_compact_canonical_dual_write = True

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "normalize",
                        "files": [
                            file_ref(
                                "bundle-pdf-compact-1",
                                "synthetic-table.pdf",
                                "application/pdf",
                                _ruled_table_pdf(),
                            )
                        ],
                    }
                ]
            },
        )
        refs = pipe.last_artifact_manifest["artifact_refs_by_type"]
        self.assertEqual(
            len(refs["broker_reports_pdf_compact_canonical_document_v1"]), 1
        )
        self.assertEqual(len(refs["broker_reports_pdf_normalization_acceptance_v1"]), 1)
        self.assertNotIn("pdf_hybrid_shadow", pipe.last_artifact_manifest)
        self.assertNotIn("pdf_structural_repair_shadow", pipe.last_artifact_manifest)
        self.assertNotIn("pdf_semantic_header_shadow", pipe.last_artifact_manifest)
        self.assertFalse(any("pdf_hybrid" in artifact_type for artifact_type in refs))
        self.assertNotIn("Synthetic Table", content)


if __name__ == "__main__":
    unittest.main()
