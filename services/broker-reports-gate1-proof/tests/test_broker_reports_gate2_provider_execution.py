from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    Gate2ProviderExecutionMetadata,
    Gate2SourceFactRuntimeError,
    gate2_model_execution_contract,
    gate2_provider_execution_safe_metadata,
    gate2_provider_execution_summary,
)


class BrokerReportsGate2ProviderExecutionTest(unittest.TestCase):
    def test_model_client_without_execution_contract_fails_closed(self):
        with self.assertRaises(Gate2SourceFactRuntimeError) as missing:
            gate2_model_execution_contract(object(), "model-under-test")

        self.assertEqual(
            missing.exception.code,
            "gate2_provider_execution_contract_missing",
        )

    def test_private_snapshot_and_safe_projection_have_explicit_response_id_boundary(self):
        metadata = self._metadata(
            provider_response_id="provider-response-private",
            resolved_model_id="models/gemini-3.5-flash-actual",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            duration_ms=0,
        )

        private = metadata.snapshot()
        safe = gate2_provider_execution_safe_metadata(metadata)

        self.assertEqual(
            private["schema_version"],
            "gate2_provider_execution_metadata_v1",
        )
        self.assertEqual(
            private["provider_response_id"],
            "provider-response-private",
        )
        self.assertNotIn("provider_response_id", safe)
        self.assertTrue(safe["provider_response_id_present"])
        self.assertEqual(
            safe["provider_response_id_sha256"],
            hashlib.sha256(b"provider-response-private").hexdigest(),
        )
        self.assertEqual(safe["requested_model_id"], "models/gemini-3.5-flash")
        self.assertEqual(
            safe["resolved_model_id"],
            "models/gemini-3.5-flash-actual",
        )
        self.assertEqual(safe["total_tokens"], 0)
        self.assertEqual(safe["duration_ms"], 0)

    def test_run_summary_distinguishes_zero_usage_from_unreported_usage(self):
        reported = self._metadata(
            provider_response_id="response-reported",
            resolved_model_id="models/gemini-3.5-flash",
            input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            duration_ms=0,
        ).snapshot()
        unreported = self._metadata(
            provider_response_id=None,
            resolved_model_id=None,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            duration_ms=None,
        ).snapshot()

        summary = gate2_provider_execution_summary(
            [
                {
                    "model_call_status": "passed",
                    "provider_execution": reported,
                },
                {
                    "model_call_status": "failed",
                    "error_code": "gate2_model_provider_rate_limited",
                    "provider_execution": unreported,
                },
            ]
        )

        self.assertEqual(summary["attempts_total"], 2)
        self.assertEqual(
            summary["call_status_counts"],
            {"failed": 1, "passed": 1},
        )
        self.assertEqual(summary["usage_reported_attempts"], 1)
        self.assertEqual(summary["usage_unreported_attempts"], 1)
        self.assertEqual(summary["input_tokens_total"], 0)
        self.assertEqual(summary["output_tokens_total"], 0)
        self.assertEqual(summary["total_tokens_total"], 0)
        self.assertEqual(summary["latency_observed_attempts"], 1)
        self.assertEqual(summary["latency_total_ms"], 0)
        self.assertEqual(summary["latency_max_ms"], 0)
        self.assertEqual(
            summary["provider_profile_counts"],
            {"google_gemini": 2},
        )
        self.assertEqual(
            summary["requested_model_counts"],
            {"models/gemini-3.5-flash": 2},
        )
        self.assertEqual(
            summary["resolved_model_counts"],
            {"models/gemini-3.5-flash": 1},
        )
        self.assertNotIn("provider_response_id", summary)
        self.assertNotIn("response-reported", str(summary))

    def test_safe_projection_rejects_malformed_provider_metadata(self):
        private_marker = "private_source_marker"
        metadata = Gate2ProviderExecutionMetadata(
            provider_id="google",
            provider_profile_id="google_gemini",
            provider_profile_revision="profile-revision",
            adapter_id="gemini_response_format",
            adapter_version="1.5.0",
            requested_model_id={"secret": private_marker},  # type: ignore[arg-type]
            resolved_model_id=private_marker,
            provider_response_id={"secret": private_marker},  # type: ignore[arg-type]
            structured_output_mode="openwebui_response_format_json_schema",
            response_format_type="json_schema",
            response_format_schema_mode="strict_json_schema",
            canonical_request_schema_hash=private_marker,
            adapted_request_schema_hash="f" * 65,
            schema_transform_count=-1,
            duration_ms=-1,
            input_tokens=-2,
            output_tokens=True,  # type: ignore[arg-type]
            total_tokens=-3,
            finish_reason="x" * 1024,
        )

        safe = gate2_provider_execution_safe_metadata(metadata)

        self.assertIsNone(safe["requested_model_id"])
        self.assertTrue(safe["requested_model_id_redacted"])
        self.assertIsNone(safe["resolved_model_id"])
        self.assertTrue(safe["resolved_model_id_redacted"])
        self.assertIsNone(safe["finish_reason"])
        self.assertIsNone(safe["canonical_request_schema_hash"])
        self.assertIsNone(safe["adapted_request_schema_hash"])
        self.assertIsNone(safe["schema_transform_count"])
        self.assertIsNone(safe["duration_ms"])
        self.assertIsNone(safe["input_tokens"])
        self.assertIsNone(safe["output_tokens"])
        self.assertIsNone(safe["total_tokens"])
        self.assertTrue(safe["provider_response_id_present"])
        self.assertNotIn(private_marker, str(safe))

    @staticmethod
    def _metadata(
        *,
        provider_response_id,
        resolved_model_id,
        input_tokens,
        output_tokens,
        total_tokens,
        duration_ms,
    ) -> Gate2ProviderExecutionMetadata:
        return Gate2ProviderExecutionMetadata(
            provider_id="google",
            provider_profile_id="google_gemini",
            provider_profile_revision="profile-revision",
            adapter_id="gemini_response_format",
            adapter_version="1.5.0",
            requested_model_id="models/gemini-3.5-flash",
            resolved_model_id=resolved_model_id,
            provider_response_id=provider_response_id,
            structured_output_mode="openwebui_response_format_json_schema",
            response_format_type="json_schema",
            response_format_schema_mode="strict_json_schema",
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            finish_reason="stop" if resolved_model_id else None,
        )


if __name__ == "__main__":
    unittest.main()
