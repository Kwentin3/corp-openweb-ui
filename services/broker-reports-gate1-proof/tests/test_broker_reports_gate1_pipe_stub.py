from __future__ import annotations

import asyncio
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openwebui_actions.broker_reports_gate1_pipe import NORMALIZER_VERSION, SAFETY_STATEMENT, Pipe


def run_pipe(pipe: Pipe, body: dict, **kwargs) -> str:
    kwargs.setdefault("__user__", {"id": "pipe-test-user"})
    kwargs.setdefault(
        "__metadata__",
        {"chat_id": "pipe-test-chat", "model_id": "broker_reports_gate1_pipe_test"},
    )
    return asyncio.run(pipe.pipe(body, **kwargs))


def file_ref(file_id: str, filename: str, mime_type: str, **extra):
    payload = {
        "id": file_id,
        "filename": filename,
        "mime_type": mime_type,
    }
    payload.update(extra)
    return {"type": "file", "file": payload}


class BrokerReportsGate1PipeSlice1Test(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _pipe(self) -> Pipe:
        pipe = Pipe()
        root = Path(self._tmp.name)
        pipe.valves.artifact_store_path = str(root / "artifacts.sqlite3")
        pipe.valves.artifact_payload_root = str(root / "payloads")
        return pipe

    def test_pipe_collects_files_and_returns_contract_safe_inventory(self):
        pipe = self._pipe()
        txt = (
            "Synthetic Person Alpha\n"
            "Synthetic Broker LLC\n"
            "SYNTH-ACCOUNT-001\n"
            "SYNTH-A\n"
            "SYNTH-FCY\n"
        )
        csv = (
            "synthetic_symbol,synthetic_quantity,synthetic_currency,synthetic_note\n"
            "SYNTH-A,1,SYNTH-FCY,synthetic operation row for Gate 1 only\n"
        )

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization with private prompt text",
                        "files": [
                            file_ref(
                                "pipe-file-txt-1",
                                "synthetic_gate1_text_pdf_or_txt.txt",
                                "text/plain",
                                content=txt,
                            ),
                            file_ref(
                                "pipe-file-csv-1",
                                "synthetic_gate1_operations.csv",
                                "text/csv",
                                content=csv,
                            ),
                        ],
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertNotIn("```json", content)
        self.assertIn("Нормализация завершена.", content)
        self.assertIn("Техническая ссылка: run", content)
        self.assertIsNotNone(pipe.last_artifact_manifest)
        self.assertEqual(report["trigger_type"], "pipe_backend_normalizer")
        self.assertEqual(report["entrypoint"], "broker_reports_gate1_pipe")
        self.assertEqual(report["normalizer_version"], NORMALIZER_VERSION)
        self.assertEqual(report["input_context"]["normalizer_version"], NORMALIZER_VERSION)
        self.assertEqual(report["run_status"], "completed")
        self.assertEqual(report["file_ref_visibility"], "visible")
        self.assertEqual(report["files_total"], 2)
        self.assertEqual(report["summary_counts"]["files_total"], 2)
        self.assertEqual(report["container_counts"], {"txt": 1, "csv": 1})
        self.assertEqual(report["summary_counts"]["container_counts"], {"txt": 1, "csv": 1})
        self.assertEqual(report["duplicate_count"], 0)
        self.assertEqual(report["blockers_total"], 0)
        self.assertEqual(len(report["documents"]), 2)
        self.assertEqual(
            report["documents"][0]["sha256"],
            hashlib.sha256(txt.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(
            report["documents"][1]["sha256"],
            hashlib.sha256(csv.encode("utf-8")).hexdigest(),
        )
        self.assertEqual(report["normalization_run"]["schema_version"], "normalization_run_v0")
        self.assertEqual(report["normalization_run"]["gate2_handoff_status"], "ready_with_safe_refs")
        self.assertEqual(report["safety_statement"], SAFETY_STATEMENT)
        self.assertFalse(report["safety_flags"]["tax_correctness_claimed"])
        self.assertFalse(report["safety_flags"]["source_fact_extraction_performed"])
        self.assertFalse(report["safety_flags"]["declaration_generated"])
        self.assertFalse(report["safety_flags"]["xlsx_generated"])
        self.assertFalse(report["safety_flags"]["ocr_performed"])
        self.assertNotIn("pipe-file-csv-1", content)
        self.assertNotIn("synthetic_gate1_operations.csv", content)
        self.assertNotIn("private prompt text", content)
        self.assertNotIn("SYNTH-ACCOUNT-001", content)
        self.assertNotIn("SYNTH-A,1,SYNTH-FCY", content)
        self.assertNotIn(csv, content)

    def test_pipe_live_artifactstore_smoke_proves_retention_without_private_leaks(self):
        pipe = self._pipe()
        txt = (
            "Synthetic Person Alpha\n"
            "Synthetic Broker LLC\n"
            "SYNTH-ACCOUNT-001\n"
            "SYNTH-A\n"
            "SYNTH-FCY\n"
        )
        csv = (
            "synthetic_symbol,synthetic_quantity,synthetic_currency,synthetic_note\n"
            "SYNTH-A,1,SYNTH-FCY,synthetic operation row for Gate 1 only\n"
        )

        content = run_pipe(
            pipe,
            {
                "metadata": {"case_id": "case-live-smoke"},
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization\nartifactstore retention smoke",
                        "files": [
                            file_ref(
                                "pipe-file-txt-1",
                                "synthetic_gate1_text_pdf_or_txt.txt",
                                "text/plain",
                                content=txt,
                            ),
                            file_ref(
                                "pipe-file-csv-1",
                                "synthetic_gate1_operations.csv",
                                "text/csv",
                                content=csv,
                            ),
                        ],
                    }
                ],
            },
        )

        self.assertIn("Проверка ArtifactStore:", content)
        self.assertIn("хранилище доступно для записи: да", content)
        self.assertIn("retention policy: mode=api_smoke, explicit=True, ttl_seconds=86400", content)
        self.assertIn("normalization_run_v0", content)
        self.assertIn("private_normalized_text_slice_v0", content)
        self.assertIn("private_normalized_table_slice_v0", content)
        self.assertIn("private slices в chat: нет", content)
        self.assertIn("private slices в Knowledge: нет", content)
        self.assertIn("customer_docs_loaded_to_knowledge=false", content)
        self.assertIn("Gate 2 handoff использует opaque refs, не chat JSON", content)
        self.assertIn("resolver same-context: allow", content)
        self.assertIn("resolver denies wrong-user/wrong-case/expired/purged: ok", content)
        self.assertIn("purge удалил private payloads и оставил tombstones", content)
        self.assertIn("source facts/tax/declaration/xlsx/ocr flags=false", content)
        self.assertNotIn("```json", content)
        self.assertNotIn("pipe-file-csv-1", content)
        self.assertNotIn("synthetic_gate1_operations.csv", content)
        self.assertNotIn("SYNTH-ACCOUNT-001", content)
        self.assertNotIn("SYNTH-A,1,SYNTH-FCY", content)
        self.assertNotIn(csv, content)

    def test_pipe_fails_closed_without_files(self):
        pipe = self._pipe()

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization PRIVATE NAME",
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertNotIn("```json", content)
        self.assertIn("Нормализация остановлена.", content)
        self.assertEqual(report["run_status"], "failed_safe")
        self.assertEqual(report["file_ref_visibility"], "not_visible")
        self.assertEqual(report["summary_counts"]["blockers_total"], 1)
        self.assertEqual(report["blockers"][0]["code"], "no_files")
        self.assertEqual(report["recommended_next_step"], "attach_synthetic_files_and_retry")
        self.assertNotIn("PRIVATE NAME", content)

    def test_pipe_can_require_trigger_phrase(self):
        pipe = self._pipe()
        pipe.valves.require_trigger_phrase = True

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "hello",
                        "files": [
                            file_ref(
                                "pipe-file-csv-1",
                                "synthetic_gate1_operations.csv",
                                "text/csv",
                                content="synthetic_symbol\nSYNTH-A\n",
                            )
                        ],
                    }
                ],
            },
        )

        self.assertIn("Gate 1 normalization is available", content)
        self.assertNotIn("pipe-file-csv-1", content)

    def test_pipe_reports_bytes_unavailable_without_failing(self):
        pipe = self._pipe()
        pipe.valves.allow_upload_path_access = False

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization",
                        "files": [
                            file_ref(
                                "pipe-file-csv-1",
                                "synthetic_gate1_operations.csv",
                                "text/csv",
                            )
                        ],
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["container_counts"], {"csv": 1})
        self.assertEqual(report["blockers_total"], 1)
        self.assertEqual(report["blockers"][0]["code"], "bytes_unavailable")
        self.assertEqual(report["blockers"][0]["reason_code"], "upload_path_access_disabled")
        self.assertEqual(report["documents"][0]["sha256"], None)
        self.assertEqual(report["documents"][0]["read_error_class"], "bytes_unavailable")
        self.assertEqual(report["recommended_next_step"], "verify_pipe_byte_access_boundary")

    def test_pipe_hashes_uploaded_bytes_from_guarded_upload_root(self):
        pipe = self._pipe()
        csv_bytes = b"synthetic_symbol,synthetic_quantity\nSYNTH-A,1\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            pipe.valves.upload_root = str(tmp_path)
            (tmp_path / "pipe-file-csv-1_synthetic_gate1_operations.csv").write_bytes(csv_bytes)

            content = run_pipe(
                pipe,
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Gate 1 normalization",
                            "files": [
                                file_ref(
                                    "pipe-file-csv-1",
                                    "synthetic_gate1_operations.csv",
                                    "text/csv",
                                )
                            ],
                        }
                    ],
                },
            )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "completed")
        self.assertEqual(report["documents"][0]["sha256"], hashlib.sha256(csv_bytes).hexdigest())
        self.assertEqual(report["documents"][0]["size_bytes"], len(csv_bytes))
        self.assertNotIn("SYNTH-A,1", content)
        self.assertNotIn("synthetic_gate1_operations.csv", content)

    def test_pipe_detects_duplicate_file_bytes(self):
        pipe = self._pipe()
        duplicate = "synthetic duplicate content\nSYNTH-FCY\n"

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization",
                        "files": [
                            file_ref("pipe-file-1", "first.txt", "text/plain", content=duplicate),
                            file_ref("pipe-file-2", "second.txt", "text/plain", content=duplicate),
                        ],
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["duplicate_count"], 1)
        self.assertEqual(report["summary_counts"]["duplicate_hashes"], 1)
        self.assertIn("duplicate_review", {blocker["code"] for blocker in report["blockers"]})
        self.assertEqual(report["documents"][1]["duplicate_of_document_id"], report["documents"][0]["document_id"])
        self.assertNotIn("pipe-file-1", content)
        self.assertNotIn("first.txt", content)
        self.assertNotIn(duplicate, content)

    def test_pipe_marks_unknown_container_with_typed_blocker(self):
        pipe = self._pipe()

        content = run_pipe(
            pipe,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Gate 1 normalization",
                        "files": [
                            file_ref(
                                "pipe-file-unknown-1",
                                "synthetic_unknown_payload.bin",
                                "application/octet-stream",
                                content_bytes=b"\x00\x01unknown synthetic bytes",
                            )
                        ],
                    }
                ],
            },
        )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["container_counts"], {"unknown": 1})
        self.assertIn("unsupported_format", {blocker["code"] for blocker in report["blockers"]})
        self.assertNotIn("pipe-file-unknown-1", content)
        self.assertNotIn("synthetic_unknown_payload.bin", content)

    def test_pipe_blocks_upload_path_escape_without_printing_private_path(self):
        pipe = self._pipe()
        with tempfile.TemporaryDirectory() as tmp_dir:
            pipe.valves.upload_root = tmp_dir
            content = run_pipe(
                pipe,
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Gate 1 normalization",
                            "files": [
                                file_ref(
                                    "..\\escape-file",
                                    "synthetic_gate1_operations.csv",
                                    "text/csv",
                                )
                            ],
                        }
                    ],
                },
            )

        report = pipe.last_safe_report
        self.assertIsNotNone(report)
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["blockers"][0]["code"], "bytes_unavailable")
        self.assertEqual(report["blockers"][0]["reason_code"], "upload_path_escape_detected")
        self.assertNotIn("escape-file", content)
        self.assertNotIn("synthetic_gate1_operations.csv", content)


if __name__ == "__main__":
    unittest.main()
