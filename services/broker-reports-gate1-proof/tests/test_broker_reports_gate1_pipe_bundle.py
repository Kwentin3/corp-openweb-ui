from __future__ import annotations

import asyncio
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BUNDLE = ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py"
FIXTURES = REPO / "docs" / "stage2" / "testdata" / "broker_reports_gate1_normalization"


def run_pipe(pipe, body: dict, **kwargs) -> str:
    kwargs.setdefault("__user__", {"id": "bundle-test-user"})
    kwargs.setdefault(
        "__metadata__",
        {"chat_id": "bundle-test-chat", "model_id": "broker_reports_gate1_pipe_bundle_test"},
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


def load_bundle_module():
    for name in list(sys.modules):
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1."):
            del sys.modules[name]
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
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def tearDown(self) -> None:
        for name in list(sys.modules):
            if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1."):
                del sys.modules[name]

    def test_bundled_pipe_runs_backend_normalizer_without_repo_package_import(self):
        source = BUNDLE.read_text(encoding="utf-8")
        self.assertIn("_BUNDLED_MODULES", source)
        self.assertNotIn("pipe_stub", source)
        self.assertIn(
            "requirements: pydantic,pypdf==6.7.5,pdfplumber==0.11.10,pdfminer.six==20260107",
            source,
        )
        module = load_bundle_module()
        self.assertIn("pdf_layout", module._BUNDLED_MODULES)
        self.assertIn("pdf_layout_units", module._BUNDLED_MODULES)
        self.assertIn("pdf_text_layer", module._BUNDLED_MODULES)
        self.assertIn("source_provenance", module._BUNDLED_MODULES)
        self.assertIn("gate2_input_readiness", module._BUNDLED_MODULES)
        self.assertIn("gate2_source_fact_contracts", module._BUNDLED_MODULES)
        self.assertIn("gate2_model_contracts", module._BUNDLED_MODULES)
        self.assertIn("gate2_model_requests", module._BUNDLED_MODULES)
        self.assertIn("gate2_model_clients", module._BUNDLED_MODULES)
        self.assertIn("gate2_source_fact_validation", module._BUNDLED_MODULES)
        self.assertIn("gate2_source_fact_runtime", module._BUNDLED_MODULES)
        bundled_package = sys.modules["broker_reports_gate1"]
        self.assertTrue(hasattr(bundled_package, "NormalizedSliceProvenanceFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate2InputReadinessFactory"))
        self.assertTrue(hasattr(bundled_package, "Gate2SourceFactRuntimeFactory"))
        self.assertTrue(
            hasattr(bundled_package, "Gate2StructuredModelClientFactory")
        )
        self.assertTrue(hasattr(bundled_package, "PdfTextLayerParserFactory"))
        self.assertTrue(hasattr(bundled_package, "PdfLayoutUnitBuilder"))
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
        self.assertIn("unsupported_format", {item["code"] for item in report["blockers"]})
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


if __name__ == "__main__":
    unittest.main()
