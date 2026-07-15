from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1 import (  # noqa: E402
    FileInput,
    Gate1Normalizer,
    ManagedPrompt,
    build_llm_document_packages,
    render_chat_content,
)
from broker_reports_gate1.document_passport import prompt_hash  # noqa: E402
from broker_reports_gate1.file_processing_outcomes import (  # noqa: E402
    validate_file_processing_batch,
)


class BrokerReportsFileProcessingIntegrationTest(unittest.TestCase):
    def test_mixed_package_keeps_a_terminal_result_for_every_file(self) -> None:
        private_good_ref = "private-good-file-reference"
        private_missing_ref = "private-missing-file-reference"
        private_good_name = "customer-good-file.txt"
        private_missing_name = "customer-missing-file.csv"
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref=private_good_ref,
                    filename=private_good_name,
                    content=b"Synthetic broker statement\nPeriod: 2025\n",
                    mime_type="text/plain",
                ),
                FileInput(
                    private_ref=private_missing_ref,
                    original_filename_private=private_missing_name,
                    mime_type="text/csv",
                    bytes_provider=None,
                ),
            ]
        )

        batch = result.safe_report["file_processing_outcomes"]
        self.assertTrue(validate_file_processing_batch(batch)["passed"])
        self.assertEqual(batch["files_total"], 2)
        self.assertEqual(
            batch["status_counts"],
            {"success": 1, "partial": 0, "failed": 1},
        )
        self.assertTrue(all(item["terminal"] for item in batch["outcomes"]))
        self.assertEqual(
            {item["file_ref"] for item in batch["outcomes"]},
            {item["document_id"] for item in result.safe_report["documents"]},
        )
        failed = next(item for item in batch["outcomes"] if item["status"] == "failed")
        self.assertEqual(failed["stage"], "byte_access")
        self.assertEqual(failed["reason_code"], "bytes_unavailable")

        rendered = render_chat_content(result.safe_report)
        self.assertIn("Результат обработки файлов:", rendered)
        self.assertIn("успешно — 1", rendered)
        self.assertIn("с ошибкой — 1", rendered)
        for marker in (
            private_good_ref,
            private_missing_ref,
            private_good_name,
            private_missing_name,
        ):
            self.assertNotIn(marker, rendered)

    def test_llm_document_package_receives_only_the_matching_safe_outcome(self) -> None:
        private_marker = "PRIVATE-FILE-MARKER-7788"
        result = Gate1Normalizer().normalize(
            [
                FileInput(
                    private_ref=private_marker,
                    original_filename_private="private-customer-report.csv",
                    mime_type="text/csv",
                    bytes_provider=None,
                    privacy_markers=[private_marker],
                )
            ]
        )
        prompt_content = "Managed synthetic prompt"
        prompt = ManagedPrompt(
            prompt_ref="prompt-processing-outcome-test",
            command="broker_gate1_document_passport",
            version="test-v1",
            content=prompt_content,
            hash=prompt_hash(
                prompt_content,
                "broker_reports_document_metadata_passport_prompt_v0",
                "document_metadata_passport_v0",
            ),
            source="test",
            template_id="broker_reports.document_metadata_passport.v0",
            template_kind="document_metadata_passport",
            output_schema_version="document_metadata_passport_v0",
            tags=("test",),
            safe_metadata={},
        )

        llm_package = build_llm_document_packages(
            package=result.package,
            prompt=prompt,
            model_id="synthetic-model",
        )[0]
        outcome = llm_package["processing_outcome"]

        self.assertEqual(outcome["file_ref"], llm_package["document_id"])
        self.assertEqual(outcome["reason_code"], "bytes_unavailable")
        self.assertEqual(outcome["next_action"], "retry")
        rendered = json.dumps(llm_package, ensure_ascii=False, sort_keys=True)
        self.assertNotIn(private_marker, rendered)
        self.assertNotIn("private-customer-report.csv", rendered)
        self.assertNotIn("exception", rendered.lower())
        self.assertNotIn("provider_payload", rendered)

    def test_unknown_binary_is_reported_as_unsupported_format(self) -> None:
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="private-unsupported",
                    filename="customer-unsupported.bin",
                    content=b"\x00\x01\x02\x03",
                    mime_type="application/octet-stream",
                )
            ]
        )

        outcome = result.safe_report["file_processing_outcomes"]["outcomes"][0]
        self.assertEqual(outcome["status"], "failed")
        self.assertEqual(outcome["stage"], "container_detection")
        self.assertEqual(outcome["reason_code"], "unsupported_format")
        self.assertEqual(outcome["next_action"], "upload_supported_file")


if __name__ == "__main__":
    unittest.main()
