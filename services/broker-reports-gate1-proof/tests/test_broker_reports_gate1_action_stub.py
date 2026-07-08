from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openwebui_actions.broker_reports_gate1_normalizer_action import Action


def run_action(action: Action, body: dict, **kwargs):
    return asyncio.run(action.action(body, **kwargs))


class BrokerReportsGate1ActionStubTest(unittest.TestCase):
    def test_action_collects_body_files_and_returns_safe_report_without_raw_names(self):
        action = Action()

        response = run_action(
            action,
            {
                "files": [
                    {
                        "file": {
                            "id": "file-pdf-1",
                            "filename": "synthetic_gate1_text_pdf_or_txt.txt",
                            "mime_type": "text/plain",
                            "size": 120,
                        }
                    },
                    {
                        "file": {
                            "id": "file-csv-1",
                            "filename": "synthetic_gate1_operations.csv",
                            "mime_type": "text/csv",
                            "size": 240,
                        }
                    },
                    {
                        "file": {
                            "id": "file-xlsx-1",
                            "filename": "synthetic_gate1_workbook.xlsx",
                            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "size": 360,
                        }
                    },
                ]
            },
            __user__={"id": "synthetic-user"},
        )

        report = response["broker_reports_gate1_report"]
        content = response["content"]
        self.assertEqual(
            report["schema_version"],
            "broker_reports_chat_visible_normalization_report_v0",
        )
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["file_ref_visibility"], "visible")
        self.assertEqual(report["summary_counts"]["files_total"], 3)
        self.assertEqual(
            report["summary_counts"]["container_counts"],
            {"txt": 1, "csv": 1, "xlsx": 1},
        )
        self.assertIn("Select case_group_synthetic_001", content)
        self.assertNotIn("synthetic_gate1_operations.csv", content)
        self.assertNotIn("file-csv-1", content)
        self.assertNotIn("SYNTH-ACCOUNT-001", content)

    def test_action_supports_metadata_files_and_files_arg_shapes(self):
        action = Action()

        response = run_action(
            action,
            {},
            __metadata__={
                "files": [
                    {
                        "file": {
                            "id": "file-metadata-1",
                            "filename": "synthetic.txt",
                            "mime_type": "text/plain",
                        }
                    }
                ]
            },
            __files__=[
                {
                    "file": {
                        "id": "file-arg-1",
                        "filename": "synthetic.csv",
                        "mime_type": "text/csv",
                    }
                }
            ],
        )

        report = response["broker_reports_gate1_report"]
        self.assertEqual(report["summary_counts"]["files_total"], 2)
        self.assertEqual(report["summary_counts"]["container_counts"], {"txt": 1, "csv": 1})

    def test_action_collects_file_refs_from_nested_message_files(self):
        action = Action()

        response = run_action(
            action,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Synthetic visible message text",
                        "files": [
                            {
                                "type": "file",
                                "id": "message-file-csv-1",
                                "name": "synthetic_gate1_operations.csv",
                                "mime_type": "text/csv",
                                "size": 136,
                            }
                        ],
                    }
                ]
            },
        )

        report = response["broker_reports_gate1_report"]
        content = response["content"]
        self.assertEqual(report["file_ref_visibility"], "visible")
        self.assertEqual(report["summary_counts"]["files_total"], 1)
        self.assertEqual(report["summary_counts"]["container_counts"], {"csv": 1})
        self.assertEqual(report["input_context"]["messages_count"], 1)
        self.assertEqual(report["input_context"]["messages_with_files_count"], 1)
        self.assertNotIn("message-file-csv-1", content)
        self.assertNotIn("synthetic_gate1_operations.csv", content)
        self.assertNotIn("Synthetic visible message text", content)

    def test_action_can_prove_original_bytes_under_upload_root(self):
        action = Action()
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            action.valves.upload_root = str(tmp_path)
            action.valves.prove_original_bytes_access = True
            (tmp_path / "file-csv-1_synthetic_gate1_operations.csv").write_bytes(
                b"symbol,quantity,price\nSYNTH-A,1,10\n"
            )

            response = run_action(
                action,
                {
                    "files": [
                        {
                            "file": {
                                "id": "file-csv-1",
                                "filename": "synthetic_gate1_operations.csv",
                                "mime_type": "text/csv",
                            }
                        }
                    ]
                },
            )

        report = response["broker_reports_gate1_report"]
        self.assertEqual(report["original_bytes_access"]["status"], "proven")
        self.assertEqual(report["original_bytes_access"]["files_with_bytes"], 1)
        self.assertNotIn("SYNTH-A,1,10", response["content"])

    def test_action_fails_closed_when_no_file_refs_are_visible(self):
        action = Action()

        response = run_action(
            action,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "PRIVATE NAME AND TAX ID SHOULD NOT APPEAR",
                    }
                ]
            },
        )

        report = response["broker_reports_gate1_report"]
        self.assertEqual(report["run_status"], "failed_safe")
        self.assertEqual(report["file_ref_visibility"], "not_visible")
        self.assertEqual(report["summary_counts"]["blockers_total"], 1)
        self.assertEqual(report["input_context"]["messages_count"], 1)
        self.assertIn("Select case_group_synthetic_001", response["content"])
        self.assertNotIn("PRIVATE NAME", response["content"])


if __name__ == "__main__":
    unittest.main()
