from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.file_processing_outcomes import (  # noqa: E402
    BATCH_OUTCOME_FALLBACK_MESSAGE,
    FACTORY_REQUIRED,
    FILE_OUTCOME_FALLBACK_MESSAGE,
    FILE_PROCESSING_BATCH_SCHEMA_VERSION,
    FILE_PROCESSING_OUTCOME_SCHEMA_VERSION,
    FORBIDDEN,
    PRIVATE_PROCESSING_DIAGNOSTIC_SCHEMA_VERSION,
    FileProcessingOutcomeConfig,
    FileProcessingOutcomeError,
    FileProcessingOutcomeFactory,
    FileProcessingOutcomeRecord,
    render_file_processing_batch,
    render_file_processing_outcome,
    validate_file_processing_batch,
    validate_file_processing_outcome,
    validate_private_processing_diagnostic,
)


class BrokerReportsFileProcessingOutcomesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FileProcessingOutcomeFactory().create()

    def test_factory_anchors_and_direct_record_construction_is_blocked(self) -> None:
        self.assertIn("FileProcessingOutcomeFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not construct model-facing outcomes", FORBIDDEN)

        with self.assertRaises(TypeError):
            FileProcessingOutcomeRecord({}, None)  # type: ignore[call-arg]

    def test_success_is_a_closed_terminal_safe_contract(self) -> None:
        record = self.service.success(file_ref="file_report_001")
        outcome = record.safe_snapshot()

        self.assertEqual(
            set(outcome),
            {
                "schema_version",
                "policy_version",
                "outcome_id",
                "outcome_checksum_ref",
                "file_ref",
                "status",
                "stage",
                "reason_code",
                "retryable",
                "next_action",
                "user_message",
                "terminal",
            },
        )
        self.assertEqual(outcome["schema_version"], FILE_PROCESSING_OUTCOME_SCHEMA_VERSION)
        self.assertEqual(outcome["status"], "success")
        self.assertEqual(outcome["stage"], "completed")
        self.assertEqual(outcome["reason_code"], "completed")
        self.assertFalse(outcome["retryable"])
        self.assertEqual(outcome["next_action"], "none")
        self.assertTrue(outcome["terminal"])
        self.assertTrue(validate_file_processing_outcome(outcome)["passed"])
        self.assertEqual(record.model_context(), outcome)
        self.assertIsNone(record.private_snapshot())
        self.assertEqual(
            render_file_processing_outcome(record),
            "file_report_001: Файл успешно обработан.",
        )

    def test_partial_and_failed_terminal_outcomes_derive_safe_policy_fields(self) -> None:
        partial = self.service.partial(
            file_ref="document_pdf_002",
            stage="oracle_consensus",
            reason_code="consensus_not_reached",
        ).safe_snapshot()
        failed = self.service.failed(
            file_ref="upload_pdf_003",
            stage="provider_call",
            reason_code="provider_rate_limited",
        ).safe_snapshot()

        self.assertEqual(partial["status"], "partial")
        self.assertTrue(partial["terminal"])
        self.assertTrue(partial["retryable"])
        self.assertEqual(partial["next_action"], "manual_review")
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(failed["terminal"])
        self.assertTrue(failed["retryable"])
        self.assertEqual(failed["next_action"], "retry_later")
        self.assertTrue(validate_file_processing_outcome(partial)["passed"])
        self.assertTrue(validate_file_processing_outcome(failed)["passed"])

    def test_private_diagnostic_is_separate_and_never_model_facing(self) -> None:
        private_marker = "PRIVATE-ACCOUNT-778899"
        secret_marker = "sk-secret-do-not-publish"
        path_marker = r"C:\customer\private\statement.pdf"
        diagnostic = self.service.private_diagnostic(
            file_ref="file_report_004",
            stage="provider_call",
            exception=RuntimeError(f"provider failed for {private_marker}"),
            source_path=path_marker,
            provider_payload={"raw": private_marker},
            private_context={"api_key": secret_marker},
        )
        record = self.service.failed(
            file_ref="file_report_004",
            stage="provider_call",
            reason_code="provider_temporarily_unavailable",
            private_diagnostic=diagnostic,
        )

        private = record.private_snapshot()
        safe = record.safe_snapshot()
        model_context = record.model_context()
        self.assertIsNotNone(private)
        self.assertEqual(
            private["schema_version"],  # type: ignore[index]
            PRIVATE_PROCESSING_DIAGNOSTIC_SCHEMA_VERSION,
        )
        self.assertTrue(validate_private_processing_diagnostic(private)["passed"])
        self.assertTrue(record.has_private_diagnostic)
        self.assertIn(private_marker, json.dumps(private, ensure_ascii=False))
        self.assertIn(secret_marker, json.dumps(private, ensure_ascii=False))
        self.assertEqual(private["source_path"], path_marker)
        for public_value in (safe, model_context, repr(record), repr(diagnostic)):
            rendered = (
                json.dumps(public_value, ensure_ascii=False)
                if isinstance(public_value, dict)
                else public_value
            )
            self.assertNotIn(private_marker, rendered)
            self.assertNotIn(secret_marker, rendered)
            self.assertNotIn(path_marker, rendered)
        self.assertNotIn("diagnostic", json.dumps(model_context, ensure_ascii=False))

    def test_private_diagnostic_lineage_must_match_safe_outcome(self) -> None:
        diagnostic = self.service.private_diagnostic(
            file_ref="file_report_005",
            stage="provider_call",
            exception=RuntimeError("private"),
        )

        with self.assertRaises(FileProcessingOutcomeError) as mismatch:
            self.service.failed(
                file_ref="file_report_006",
                stage="provider_call",
                reason_code="provider_temporarily_unavailable",
                private_diagnostic=diagnostic,
            )

        self.assertEqual(
            mismatch.exception.code,
            "file_outcome_private_diagnostic_mismatch",
        )

    def test_unknown_reason_wrong_stage_and_path_like_ref_fail_closed(self) -> None:
        cases = (
            (
                {"file_ref": "file_report_007", "stage": "provider_call", "reason_code": "raw_500"},
                "file_outcome_reason_code_invalid",
            ),
            (
                {"file_ref": "file_report_007", "stage": "parsing", "reason_code": "provider_rate_limited"},
                "file_outcome_reason_stage_invalid",
            ),
            (
                {"file_ref": r"C:\private\report.pdf", "stage": "provider_call", "reason_code": "provider_rate_limited"},
                "file_outcome_file_ref_invalid",
            ),
        )
        for kwargs, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(FileProcessingOutcomeError) as raised:
                    self.service.failed(**kwargs)
                self.assertEqual(raised.exception.code, code)

    def test_tampering_breaks_checksum_and_uses_non_interpolating_fallback(self) -> None:
        marker = "RAW-EXCEPTION-MUST-NOT-LEAK"
        tampered = self.service.failed(
            file_ref="file_report_008",
            stage="processing",
            reason_code="internal_processing_failed",
        ).safe_snapshot()
        tampered["user_message"] = marker
        tampered["raw_exception"] = marker

        validation = validate_file_processing_outcome(tampered)

        self.assertFalse(validation["passed"])
        self.assertIn(
            "file_outcome_shape_invalid",
            {item["code"] for item in validation["errors"]},
        )
        self.assertIn(
            "file_outcome_checksum_mismatch",
            {item["code"] for item in validation["errors"]},
        )
        rendered = render_file_processing_outcome(tampered)
        self.assertEqual(rendered, FILE_OUTCOME_FALLBACK_MESSAGE)
        self.assertNotIn(marker, rendered)

        malformed = {"user_message": {marker}}
        self.assertFalse(validate_file_processing_outcome(malformed)["passed"])
        self.assertEqual(
            render_file_processing_outcome(malformed),
            FILE_OUTCOME_FALLBACK_MESSAGE,
        )

    def test_batch_is_deterministic_closed_and_keeps_per_file_results(self) -> None:
        records = [
            self.service.failed(
                file_ref="file_c",
                stage="parsing",
                reason_code="corrupt_file",
            ),
            self.service.success(file_ref="file_a"),
            self.service.partial(
                file_ref="file_b",
                stage="output_validation",
                reason_code="table_validation_failed",
            ),
        ]

        first = self.service.batch(records)
        second = self.service.batch(reversed(records))
        batch = first.safe_snapshot()

        self.assertEqual(first.safe_snapshot(), second.safe_snapshot())
        self.assertEqual(batch["schema_version"], FILE_PROCESSING_BATCH_SCHEMA_VERSION)
        self.assertEqual(batch["overall_status"], "partial")
        self.assertEqual(batch["files_total"], 3)
        self.assertEqual(
            batch["status_counts"],
            {"success": 1, "partial": 1, "failed": 1},
        )
        self.assertEqual(
            [item["file_ref"] for item in batch["outcomes"]],
            ["file_a", "file_b", "file_c"],
        )
        self.assertTrue(batch["terminal"])
        self.assertTrue(all(item["terminal"] for item in batch["outcomes"]))
        self.assertTrue(validate_file_processing_batch(batch)["passed"])
        self.assertEqual(first.model_context(), batch)
        rendered = render_file_processing_batch(first)
        self.assertEqual(len(rendered.splitlines()), 4)
        for file_ref in ("file_a", "file_b", "file_c"):
            self.assertIn(f"{file_ref}:", rendered)

    def test_batch_never_contains_child_private_diagnostics(self) -> None:
        marker = "PRIVATE-PROVIDER-RESPONSE"
        diagnostic = self.service.private_diagnostic(
            file_ref="file_private_009",
            stage="provider_call",
            provider_payload={"raw": marker},
        )
        record = self.service.failed(
            file_ref="file_private_009",
            stage="provider_call",
            reason_code="provider_response_invalid",
            private_diagnostic=diagnostic,
        )

        batch = self.service.batch([record]).model_context()

        self.assertEqual(batch["overall_status"], "failed")
        self.assertNotIn(marker, json.dumps(batch, ensure_ascii=False))
        self.assertNotIn("diagnostic", json.dumps(batch, ensure_ascii=False))

    def test_batch_tamper_uses_deterministic_fallback(self) -> None:
        marker = "PRIVATE-BATCH-MARKER"
        batch = self.service.batch(
            [self.service.success(file_ref="file_report_010")]
        ).safe_snapshot()
        batch["outcomes"][0]["user_message"] = marker

        validation = validate_file_processing_batch(batch)

        self.assertFalse(validation["passed"])
        rendered = render_file_processing_batch(batch)
        self.assertEqual(rendered, BATCH_OUTCOME_FALLBACK_MESSAGE)
        self.assertNotIn(marker, rendered)

    def test_closed_private_shape_and_checksum_detect_tampering(self) -> None:
        diagnostic = self.service.private_diagnostic(
            file_ref="file_report_011",
            stage="processing",
            exception=RuntimeError("private"),
        ).snapshot()
        tampered = copy.deepcopy(diagnostic)
        tampered["source_path"] = r"C:\changed\path.pdf"

        validation = validate_private_processing_diagnostic(tampered)

        self.assertFalse(validation["passed"])
        self.assertIn(
            "file_outcome_private_diagnostic_checksum_mismatch",
            {item["code"] for item in validation["errors"]},
        )

    def test_policy_and_batch_limits_are_fail_closed(self) -> None:
        with self.assertRaises(FileProcessingOutcomeError) as policy:
            FileProcessingOutcomeFactory(
                FileProcessingOutcomeConfig(policy_version="unknown")
            ).create()
        self.assertEqual(policy.exception.code, "file_outcome_policy_version_invalid")

        limited = FileProcessingOutcomeFactory(
            FileProcessingOutcomeConfig(maximum_batch_files=1)
        ).create()
        with self.assertRaises(FileProcessingOutcomeError) as too_many:
            limited.batch(
                [
                    limited.success(file_ref="file_one"),
                    limited.success(file_ref="file_two"),
                ]
            )
        self.assertEqual(
            too_many.exception.code,
            "file_outcome_batch_limit_exceeded",
        )


if __name__ == "__main__":
    unittest.main()
