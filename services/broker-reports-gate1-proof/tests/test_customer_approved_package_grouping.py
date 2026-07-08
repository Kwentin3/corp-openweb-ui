from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SCRIPT = ROOT / "scripts" / "customer_approved_package_grouping.py"
sys.path.insert(0, str(ROOT))


def load_script_module():
    spec = importlib.util.spec_from_file_location("customer_approved_package_grouping", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class CustomerApprovedPackageGroupingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_script_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_missing_explicit_customer_retention_fails_closed(self):
        args = argparse.Namespace(
            retention_mode="customer_approved_test",
            retention_explicit=False,
            private_registry="missing-private.json",
            safe_source_registry="missing-safe.json",
            safe_registry="unused-safe.json",
            case_groups="unused-groups.json",
            report="unused-report.md",
            artifact_root="unused-artifacts",
            expected_file_count=2,
            case_id="case-test",
            user_id="user-test",
            workspace_model_id="workspace-test",
            env_file=".env",
            check_openwebui_knowledge=False,
        )

        with self.assertRaises(self.module.CustomerGroupingError) as raised:
            self.module.run_grouping(args)

        self.assertEqual(raised.exception.code, "retention_policy_missing")

    def test_grouping_writes_safe_outputs_and_private_artifactstore_without_leaks(self):
        source_root = self.root / "customer-source"
        source_root.mkdir()
        report_file = source_root / "secret_customer_report_alpha.txt"
        ops_file = source_root / "secret_customer_operations_beta.csv"
        report_file.write_text(
            "Private Broker Report\nAccount PRIVATE-001\nDividend income marker\n",
            encoding="utf-8",
        )
        ops_file.write_text(
            "symbol,quantity,currency\nPRIVATE-A,1,USD\nPRIVATE-B,2,USD\n",
            encoding="utf-8",
        )
        safe_source = self.root / "safe-source.json"
        private_registry = self.root / "private-registry.json"
        safe_registry = self.root / "safe-registry.json"
        case_groups = self.root / "case-groups.json"
        report = self.root / "report.md"
        artifact_root = self.root / "artifactstore"

        report_hash = hashlib.sha256(report_file.read_bytes()).hexdigest()
        ops_hash = hashlib.sha256(ops_file.read_bytes()).hexdigest()
        safe_source.write_text(
            json.dumps(
                {
                    "schema_version": "broker_reports_customer_source_documents_index_v0_safe",
                    "source_root_public_label": "withheld_customer_local_folder",
                    "documents": [
                        self._safe_doc(
                            "brdoc_001_safe",
                            report_hash,
                            ".txt",
                            "txt",
                            "source_broker_report",
                            "yes",
                            "no",
                        ),
                        self._safe_doc(
                            "brdoc_002_safe",
                            ops_hash,
                            ".csv",
                            "csv",
                            "operations_table",
                            "yes",
                            "no",
                        ),
                    ],
                    "case_groups": [
                        {
                            "case_group_id": "case_group_001",
                            "probable_broker_or_role": "Synthetic Broker",
                            "probable_tax_years": ["unknown"],
                            "account_marker_hash": "acct_safe",
                            "document_ids": ["brdoc_001_safe", "brdoc_002_safe"],
                            "readiness": "needs_review",
                            "missing_or_blocking_items": ["customer-approved methodology"],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        private_registry.write_text(
            json.dumps(
                {
                    "schema_version": "broker_reports_customer_source_documents_index_v0_private",
                    "documents": [
                        {
                            "document_id": "brdoc_001_safe",
                            "absolute_path": str(report_file),
                            "relative_path": report_file.name,
                            "original_filename": report_file.name,
                            "sha256": report_hash,
                        },
                        {
                            "document_id": "brdoc_002_safe",
                            "absolute_path": str(ops_file),
                            "relative_path": ops_file.name,
                            "original_filename": ops_file.name,
                            "sha256": ops_hash,
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        args = argparse.Namespace(
            retention_mode="customer_approved_test",
            retention_explicit=True,
            private_registry=str(private_registry),
            safe_source_registry=str(safe_source),
            safe_registry=str(safe_registry),
            case_groups=str(case_groups),
            report=str(report),
            artifact_root=str(artifact_root),
            expected_file_count=2,
            case_id="case-test",
            user_id="user-test",
            workspace_model_id="workspace-test",
            env_file=".env",
            check_openwebui_knowledge=False,
        )

        summary = self.module.run_grouping(args)

        self.assertEqual(summary["status"], "passed")
        self.assertEqual(summary["files_processed"], 2)
        self.assertEqual(summary["retention_policy"]["mode"], "customer_approved_test")
        self.assertTrue(summary["retention_policy"]["explicit"])
        generated = "\n".join(
            [
                safe_registry.read_text(encoding="utf-8-sig"),
                case_groups.read_text(encoding="utf-8-sig"),
                report.read_text(encoding="utf-8-sig"),
            ]
        )
        self.assertNotIn(report_file.name, generated)
        self.assertNotIn(ops_file.name, generated)
        self.assertNotIn(str(report_file), generated)
        self.assertNotIn("PRIVATE-001", generated)
        self.assertNotIn("PRIVATE-A", generated)
        self.assertNotIn('"rows"', generated)
        self.assertNotIn('"text"', generated)

        safe_payload = json.loads(safe_registry.read_text(encoding="utf-8-sig"))
        group_payload = json.loads(case_groups.read_text(encoding="utf-8-sig"))
        self.assertEqual(safe_payload["summary"]["files_total"], 2)
        self.assertEqual(group_payload["recommended_first_package"]["case_group_id"], "case_group_001")
        self.assertTrue(group_payload["gate2_handoff"]["uses_opaque_refs"])
        self.assertFalse(group_payload["gate2_handoff"]["chat_json_used_as_handoff"])

        conn = sqlite3.connect(artifact_root / "artifacts.sqlite3")
        try:
            rows = conn.execute(
                "SELECT visibility, storage_backend, retention_policy_json FROM artifact_records"
            ).fetchall()
        finally:
            conn.close()
        self.assertTrue(any(row[0] == "private_case" and row[1] == "project_artifact_payload" for row in rows))
        self.assertFalse(any(row[1] == "openwebui_knowledge" for row in rows))
        self.assertTrue(all(json.loads(row[2])["mode"] == "customer_approved_test" for row in rows))

    def _safe_doc(
        self,
        document_id: str,
        sha256: str,
        extension: str,
        container: str,
        role: str,
        source: str,
        methodology: str,
    ) -> dict:
        return {
            "document_id": document_id,
            "extension": extension,
            "detected_mime_type": "text/csv" if container == "csv" else "text/plain",
            "file_size_bytes": 1,
            "sha256": sha256,
            "readable": "yes",
            "container_format": container,
            "document_taxonomy_class": role,
            "secondary_tags": [],
            "classification_confidence": "high",
            "can_be_source_evidence": source,
            "can_be_methodology": methodology,
            "can_be_loaded_to_knowledge": "after_review",
            "declaration_relevance": "source_fact",
            "technical_profile": {},
            "case_grouping_signals": {},
        }


if __name__ == "__main__":
    unittest.main()
