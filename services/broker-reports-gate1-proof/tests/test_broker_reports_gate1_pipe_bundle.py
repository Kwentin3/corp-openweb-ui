from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BUNDLE = ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
GATE2_BUNDLE = (
    ROOT / "openwebui_actions" / "broker_reports_gate2_source_fact_pipe_bundled.py"
)
GATE2_DOMAIN_BUNDLE = (
    ROOT / "openwebui_actions" / "broker_reports_gate2_domain_source_fact_pipe_bundled.py"
)
GOAL391_LAB_BUNDLE = ROOT / "openwebui_actions" / "goal391_mapping_lab_pipe_bundled.py"
FIXTURES = REPO / "docs" / "stage2" / "testdata" / "broker_reports_gate1_normalization"
PUBLIC_PDF = (
    REPO
    / "docs"
    / "reports"
    / "2026-09-02"
    / "artifacts"
    / "mistral-public-pairs"
    / "drivewealth"
    / "source.pdf"
)


def run_pipe(pipe, body: dict, **kwargs) -> str:
    kwargs.setdefault("__user__", {"id": "bundle-test-user"})
    kwargs.setdefault(
        "__metadata__",
        {
            "chat_id": "bundle-test-chat",
            "model_id": "broker_reports_gate1_pipe_bundle_test",
        },
    )
    owned_files = {}
    for message in body.get("messages", []):
        for item in message.get("files", []):
            file_value = item.get("file", item)
            owned_files[str(file_value["id"])] = SimpleNamespace(
                filename=str(file_value.get("filename") or ""),
                content_type=str(file_value.get("mime_type") or ""),
                payload=file_value.get("content_bytes"),
            )

    class OwnedFileResolver:
        async def resolve(self, *, file_id: str, actor_user_id: str):
            if actor_user_id != "bundle-test-user" or file_id not in owned_files:
                raise AssertionError("unexpected owner-scoped file resolution")
            return owned_files[file_id]

    pipe._file_bytes_resolver = OwnedFileResolver()
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
        if (
            name == "broker_reports_gate1"
            or name.startswith("broker_reports_gate1.")
            or name.startswith("broker_reports_gate1__")
        )
    }


def _clear_broker_reports_modules() -> None:
    for name in list(sys.modules):
        if (
            name == "broker_reports_gate1"
            or name.startswith("broker_reports_gate1.")
            or name.startswith("broker_reports_gate1__")
        ):
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


def load_additional_bundle_module(bundle_path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, bundle_path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not create secondary bundled pipe import spec")
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

    def test_gate1_pdf_factory_survives_loading_another_bundled_function(self):
        gate1_bundle = load_bundle_module()
        gate1_package = sys.modules[gate1_bundle._BUNDLED_PACKAGE_NAME]

        additional_bundles = tuple(
            load_additional_bundle_module(path, module_name)
            for path, module_name in (
                (
                    GATE2_BUNDLE,
                    "broker_reports_gate2_source_fact_pipe_bundled_after_gate1_under_test",
                ),
                (
                    GATE2_DOMAIN_BUNDLE,
                    "broker_reports_gate2_domain_source_fact_pipe_bundled_after_gate1_under_test",
                ),
                (
                    GOAL391_LAB_BUNDLE,
                    "goal391_mapping_lab_pipe_bundled_after_gate1_under_test",
                ),
            )
        )

        self.assertEqual(
            3,
            len({bundle._BUNDLED_PACKAGE_NAME for bundle in additional_bundles}),
        )
        self.assertNotIn(
            gate1_bundle._BUNDLED_PACKAGE_NAME,
            {bundle._BUNDLED_PACKAGE_NAME for bundle in additional_bundles},
        )
        self.assertIs(
            gate1_package,
            sys.modules[gate1_bundle._BUNDLED_PACKAGE_NAME],
        )
        extractor = gate1_package.PdfDocumentExtractorFactory.create()
        self.assertEqual(
            "broker_reports_gate1__gate1_pipe.pdfplumber_document_ai",
            type(extractor).__module__,
        )

    def test_bundled_pipe_runs_backend_normalizer_without_repo_package_import(self):
        source = BUNDLE.read_text(encoding="utf-8")
        self.assertIn("_BUNDLED_MODULES", source)
        self.assertNotIn("pipe_stub", source)
        self.assertIn(
            "requirements: pydantic,pypdf==6.7.5,pdfplumber==0.11.10,lxml==6.1.1",
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
        self.assertIn("gate5_operation_set_demand_derivation", module._BUNDLED_MODULES)
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
            module._BUNDLED_PACKAGE_NAME + ".gate5_trusted_methodology"
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
            module._BUNDLED_PACKAGE_NAME + ".gate5_full_target_xml_projection"
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
        self.assertIn("pdf_document_ai", module._BUNDLED_MODULES)
        self.assertIn("pdfplumber_document_ai", module._BUNDLED_MODULES)
        self.assertNotIn("mistral_pdf_document_ai", module._BUNDLED_MODULES)
        self.assertNotIn("visual_table_review_contracts", module._BUNDLED_MODULES)
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
            bundled_order.index("pdf_document_ai"),
            bundled_order.index("full_source"),
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
        bundled_package = sys.modules[module._BUNDLED_PACKAGE_NAME]
        self.assertTrue(hasattr(bundled_package, "NormalizedSliceProvenanceFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate1DocumentMemoryFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate2InputReadinessFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate2SourceFactRuntimeFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate2StructuredModelClientFactory"))
        self.assertTrue(hasattr(bundled_package, "WorkloadAuthorityFactory"))
        self.assertTrue(hasattr(bundled_package, "PdfDocumentExtractorFactory"))
        self.assertTrue(hasattr(bundled_package, "PdfDocumentExtraction"))
        self.assertFalse(hasattr(bundled_package, "PdfDualVlmRuntimeFactory"))
        self.assertFalse(hasattr(bundled_package, "SemanticVisualTableMigrationFactory"))
        self.assertFalse(hasattr(bundled_package, "PdfStructuralRowWindowFactory"))
        self.assertTrue(
            hasattr(
                bundled_package,
                "Gate5DeterministicSourceFactConsumptionRuntimeFactory",
            )
        )
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

    def test_bundled_pipe_projects_pdf_full_source_through_private_file_boundary(self):
        module = load_bundle_module()
        pipe = module.Pipe()
        root = Path(self._tmp.name)
        pipe.valves.artifact_store_path = str(root / "compact.sqlite3")
        pipe.valves.artifact_payload_root = str(root / "compact-payloads")
        self.assertFalse(hasattr(pipe.valves, "pdf_dual_vlm_enabled"))
        self.assertFalse(
            hasattr(pipe.valves, "pdf_semantic_visual_table_downstream_enabled")
        )
        self.assertFalse(hasattr(pipe.valves, "pdf_hybrid_shadow_enabled"))
        self.assertFalse(hasattr(pipe.valves, "pdf_structural_repair_shadow_enabled"))
        self.assertFalse(hasattr(pipe.valves, "pdf_vlm_guided_intake_shadow_enabled"))
        self.assertFalse(hasattr(pipe.valves, "pdf_semantic_header_shadow_enabled"))
        publication: dict[str, object] = {}

        async def publish_private_file(**kwargs):
            publication.update(kwargs)
            self.assertEqual({"id": "bundle-test-user"}, kwargs["user"])
            self.assertEqual("bundle-test-user", kwargs["context"].user_id)
            self.assertEqual("bundle-test-chat", kwargs["context"].chat_id)
            self.assertEqual(module.FULL_SOURCE_ZIP_FILENAME, kwargs["filename"])
            self.assertEqual("application/zip", kwargs["content_type"])
            self.assertEqual(
                hashlib.sha256(kwargs["content"]).hexdigest(),
                kwargs["content_sha256"],
            )
            self.assertEqual(
                module.FULL_SOURCE_PROJECTION_SCHEMA_VERSION,
                kwargs["purpose"],
            )
            self.assertEqual(1, kwargs["projection_metadata"]["documents_total"])
            return "bundle-full-source-private-file"

        original_publisher = module.Pipe._publish_owner_scoped_private_file
        module.Pipe._publish_owner_scoped_private_file = staticmethod(publish_private_file)
        self.addCleanup(
            setattr,
            module.Pipe,
            "_publish_owner_scoped_private_file",
            original_publisher,
        )
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
                                PUBLIC_PDF.read_bytes(),
                            )
                        ],
                    }
                ]
            },
        )
        self.assertIn("full_package_ready_for_gate2", content)
        self.assertNotIn("gate2_blocked_no_eligible_sources", content)
        self.assertNotIn("PDF_DOCUMENT_AI_NOT_CONFIGURED", content)
        self.assertIn("Full Source:", content)
        self.assertIn(
            "/api/v1/files/bundle-full-source-private-file/content?attachment=true",
            content,
        )
        self.assertEqual(b"PK", publication["content"][:2])
        self.assertIsNotNone(pipe.last_artifact_manifest)
        self.assertEqual(
            "bundle-full-source-private-file",
            pipe.last_artifact_manifest["full_source_delivery"]["file_id"],
        )


if __name__ == "__main__":
    unittest.main()
