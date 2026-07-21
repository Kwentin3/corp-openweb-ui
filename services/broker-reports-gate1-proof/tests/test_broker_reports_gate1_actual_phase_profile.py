from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.profile_gate1_actual_corpus import (
    MetricBook,
    _artifact_storage_summary,
    build_safe_report,
)


class BrokerReportsGate1ActualPhaseProfileTest(unittest.TestCase):
    def test_storage_summary_proves_projection_counts_and_digests_without_refs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / "artifacts.sqlite3"
            payload_root = root / "payloads"
            payload_root.mkdir()
            projection = {
                "source_format": "csv",
                "row_count": 2,
                "cell_count": 4,
                "source_value_refs": ["private-ref-1", "private-ref-2"],
                "table_projection_checksum_ref": "tableprojchk_example",
            }
            payload_bytes = json.dumps(
                projection,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            (payload_root / "projection.json").write_bytes(payload_bytes)
            conn = sqlite3.connect(database)
            try:
                conn.execute(
                    """
                    CREATE TABLE artifact_records(
                        artifact_id TEXT,
                        artifact_type TEXT,
                        payload_size_bytes INTEGER,
                        payload_ref TEXT,
                        payload_inline_json TEXT,
                        checksum_sha256 TEXT
                    )
                    """
                )
                conn.execute(
                    "INSERT INTO artifact_records VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "artifact-private",
                        "broker_reports_normalized_table_projection_v0",
                        len(payload_bytes),
                        "projection.json",
                        None,
                        hashlib.sha256(payload_bytes).hexdigest(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            summary = _artifact_storage_summary(database)

        csv = summary["table_projections"]["by_source_format"]["csv"]
        self.assertEqual(csv["projections_total"], 1)
        self.assertEqual(csv["rows_total"], 2)
        self.assertEqual(csv["cells_total"], 4)
        self.assertEqual(csv["source_value_refs_total"], 2)
        rendered = json.dumps(summary, sort_keys=True)
        self.assertNotIn("private-ref", rendered)
        self.assertNotIn("artifact-private", rendered)

    def test_safe_report_contains_only_aggregate_phase_and_storage_evidence(self):
        metrics = MetricBook()
        metrics.add("full_source_build.pdf", 12.5)
        metrics.add("full_source_build.pdf", 7.5)
        proof = {
            "proof_status": "passed",
            "actual_execution": {
                "top_level_inputs_total": 56,
                "document_sources_total": 104,
                "logical_documents_total": 80,
                "archive_containers_total": 24,
                "archive_promoted_members_total": 48,
                "zero_silent_loss_status": "passed",
                "terminal_status_counts": {"complete": 26, "review_required": 78},
            },
            "performance": {
                "gate1_normalization_wall_seconds": 100.0,
                "actual_proof_wall_seconds": 120.0,
            },
            "automated_checks": {"knowledge_rag_absent": True},
        }
        report = build_safe_report(
            revision="test-revision",
            proof=proof,
            metrics=metrics,
            total_wall_seconds=121.0,
            peak_rss_bytes=7000,
            storage={"records_total": 10, "payload_bytes_total": 1000},
        )

        self.assertEqual(report["status"], "passed")
        self.assertEqual(
            report["inclusive_phase_profile"]["full_source_build.pdf"]["calls"],
            2,
        )
        self.assertEqual(
            report["inclusive_phase_profile"]["full_source_build.pdf"][
                "inclusive_wall_seconds"
            ],
            20.0,
        )
        self.assertTrue(
            report["interpretation_guards"][
                "inclusive_nested_times_must_not_be_summed"
            ]
        )
        self.assertFalse(report["privacy"]["customer_values_in_output"])


if __name__ == "__main__":
    unittest.main()
