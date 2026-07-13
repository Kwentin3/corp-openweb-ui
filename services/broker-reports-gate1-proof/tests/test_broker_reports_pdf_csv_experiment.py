from __future__ import annotations

import hashlib
import json
import unittest

from broker_reports_gate1.gate2_provider_adapters import (
    Gate2OpenWebUIProviderConnection,
)
from broker_reports_gate1.pdf_csv_experiment import (
    PDF_CSV_ENVELOPE_PREFIX,
    PDF_CSV_ENVELOPE_SEPARATOR,
    PDF_CSV_ENVELOPE_SUFFIX,
    PDF_CSV_TOPOLOGY_SCHEMA,
    PdfCsvExperimentError,
    PdfCsvExperimentFactory,
)
from broker_reports_gate1.pdf_csv_experiment_provider import (
    PdfCsvExperimentProviderFactory,
    PdfCsvProviderConfig,
)


class PdfCsvDialectParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PdfCsvExperimentFactory().create()

    def test_free_csv_preserves_quotes_commas_line_break_and_empty_cell(self) -> None:
        parsed = self.runtime.parse_free_csv(
            '"a,b","say ""yes""",\n"line\nbreak",42,\n',
            expected_rows=2,
            expected_columns=3,
        )
        self.assertEqual(
            parsed["rows"],
            [["a,b", 'say "yes"', ""], ["line\nbreak", "42", ""]],
        )
        self.assertTrue(parsed["byte_complete_parse"])
        self.assertFalse(parsed["silent_repair_performed"])

    def test_parser_fails_closed_without_silent_repair(self) -> None:
        cases = (
            ('a,b\n1\n', "pdf_csv_column_count_mismatch"),
            ('a,b\n1,2\ncommentary\n', "pdf_csv_row_count_mismatch"),
            ('"a,b\n1,2\n', "pdf_csv_malformed_quoting"),
            ('\ufeffa,b\n1,2', "pdf_csv_bom_forbidden"),
            ('a,b\r\n1,2', "pdf_csv_newline_invalid"),
            ('a;b\n1;2', "pdf_csv_column_count_mismatch"),
            ('```csv\na,b\n1,2\n```', "pdf_csv_markdown_fence_forbidden"),
        )
        for text, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(
                PdfCsvExperimentError, code
            ):
                self.runtime.parse_free_csv(
                    text,
                    expected_rows=2,
                    expected_columns=2,
                )

    def test_candidate_csv_requires_known_exactly_once_ids(self) -> None:
        parsed = self.runtime.parse_candidate_csv(
            "0,1\n,2+3",
            expected_rows=2,
            expected_columns=2,
            candidate_ids=["0", "1", "2", "3"],
        )
        self.assertEqual(parsed["candidate_coverage"], 4)
        self.assertEqual(parsed["candidate_grid"][1][1], ["2", "3"])
        failures = (
            ("0,1\n,2+x", "pdf_csv_candidate_id_unknown"),
            ("0,1\n,1+2", "pdf_csv_candidate_ownership_duplicate"),
            ("0,1\n,,", "pdf_csv_column_count_mismatch"),
            ("0,1\n,2", "pdf_csv_candidate_ownership_incomplete"),
            ("0,1\n,3+2", "pdf_csv_candidate_source_order_invalid"),
        )
        for text, code in failures:
            with self.subTest(code=code), self.assertRaisesRegex(
                PdfCsvExperimentError, code
            ):
                self.runtime.parse_candidate_csv(
                    text,
                    expected_rows=2,
                    expected_columns=2,
                    candidate_ids=["0", "1", "2", "3"],
                )

    def test_candidate_topology_envelope_is_small_and_does_not_repeat_grid(self) -> None:
        topology = {
            "v": PDF_CSV_TOPOLOGY_SCHEMA,
            "d": "b",
            "r": 2,
            "c": 2,
            "h": 1,
            "m": [[1, 1, 1, 2, "h"]],
            "hh": [[1, 1, 1, 2]],
            "k": ["group", 1, 2],
            "rb": [],
            "cb": [0.0, 0.5, 1.0],
            "u": [],
        }
        text = (
            PDF_CSV_ENVELOPE_PREFIX
            + "0,1\n,2"
            + PDF_CSV_ENVELOPE_SEPARATOR
            + json.dumps(topology, separators=(",", ":"), sort_keys=True)
            + PDF_CSV_ENVELOPE_SUFFIX
        )
        parsed, sidecar = self.runtime.parse_candidate_topology_envelope(
            text,
            expected_rows=2,
            expected_columns=2,
            candidate_ids=["0", "1", "2"],
            expected_continuation=["group", 1, 2],
        )
        self.assertEqual(parsed["candidate_coverage_ratio"], 1.0)
        self.assertTrue(sidecar["independently_validated"])
        self.assertFalse(sidecar["grid_repeated"])
        self.assertLess(parsed["topology_bytes"], 4096)

        bad = dict(topology)
        bad["grid"] = [["0"]]
        bad_text = (
            PDF_CSV_ENVELOPE_PREFIX
            + "0,1\n,2"
            + PDF_CSV_ENVELOPE_SEPARATOR
            + json.dumps(bad, separators=(",", ":"), sort_keys=True)
            + PDF_CSV_ENVELOPE_SUFFIX
        )
        with self.assertRaisesRegex(
            PdfCsvExperimentError, "pdf_csv_topology_keys_invalid"
        ):
            self.runtime.parse_candidate_topology_envelope(
                bad_text,
                expected_rows=2,
                expected_columns=2,
                candidate_ids=["0", "1", "2"],
                expected_continuation=["group", 1, 2],
            )

    def test_topology_binding_routes_through_current_binding_contract(self) -> None:
        package = _package()
        topology = {
            "v": PDF_CSV_TOPOLOGY_SCHEMA,
            "d": "b",
            "r": 2,
            "c": 2,
            "h": 1,
            "m": [[1, 1, 1, 2, "h"]],
            "hh": [[1, 1, 1, 2]],
            "k": None,
            "rb": [],
            "cb": [],
            "u": [],
            "schema_version": PDF_CSV_TOPOLOGY_SCHEMA,
            "topology_hash": "x",
            "independently_validated": True,
            "grid_repeated": False,
            "candidate_dictionary_repeated": False,
        }
        parsed = self.runtime.parse_candidate_csv(
            "0,1\n,2",
            expected_rows=2,
            expected_columns=2,
            candidate_ids=["0", "1", "2"],
        )
        binding = self.runtime.binding_from_csv(
            evidence_package=package,
            parsed=parsed,
            topology=topology,
            global_header_depth=1,
        )
        self.assertEqual(binding["decision"], "bound")
        self.assertEqual(binding["rows"][1]["cells"], [[], ["2"]])
        self.assertEqual(binding["spans"][0]["relation"], "spanning_header")

    def test_comparison_is_position_sensitive(self) -> None:
        result = self.runtime.compare_views(
            free_grid=[["A", "1"], ["B", "2"]],
            candidate_grid=[["A", "2"], ["B", "1"]],
            parser_grid=[["A", "1"], ["B", "2"]],
            reference_grid=[["A", "1"], ["B", "2"]],
        )
        self.assertEqual(result["free_vs_reference"]["cells_exact"], 4)
        self.assertEqual(result["candidate_vs_reference"]["cells_exact"], 2)
        self.assertEqual(result["distinctions"]["candidate_value_wrong_cell"], 2)

    def test_repeatability_conflict_is_monotonic_after_later_agreement(self) -> None:
        result = self.runtime.assess_repeatability(
            [
                {"grid": "a", "placement": "x"},
                {"grid": "b", "placement": "y"},
                {"grid": "a", "placement": "x"},
            ],
            required_fields=("grid", "placement"),
        )
        self.assertTrue(result["ever_conflicted"])
        self.assertFalse(result["passed"])
        self.assertFalse(result["later_agreement_can_clear_conflict"])


class PdfCsvProviderAdapterTests(unittest.TestCase):
    def test_count_and_invoke_have_explicit_terminal_and_no_retry(self) -> None:
        transport = _FakeUrlOpen()
        adapter = PdfCsvExperimentProviderFactory(
            PdfCsvProviderConfig(maximum_counted_input_tokens=1000),
            urlopen_fn=transport,
        ).create_with_connection(
            Gate2OpenWebUIProviderConnection(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key="secret",
            )
        )
        png = b"png"
        crop_hash = hashlib.sha256(png).hexdigest()
        counted = adapter.count_tokens(prompt="return csv", png_bytes=png, crop_sha256=crop_hash)
        result = adapter.invoke(
            task_id="csvtask",
            prompt="return csv",
            png_bytes=png,
            crop_sha256=crop_hash,
            attempt_number=1,
            attempt_lineage=[],
        )
        self.assertEqual(counted["total_tokens"], 123)
        self.assertTrue(counted["within_hard_guard"])
        self.assertEqual(result["text"], "a,b\n1,2")
        self.assertEqual(result["attempt"]["finish_reason"], "STOP")
        self.assertIsNone(result["attempt"]["terminal_failure_class"])
        self.assertFalse(result["attempt"]["hidden_retry"])
        self.assertFalse(result["attempt"]["provider_failover"])
        self.assertEqual(len(transport.requests), 2)
        request_body = json.loads(transport.requests[0].data.decode("utf-8"))
        self.assertIn("generateContentRequest", request_body)
        self.assertEqual(
            request_body["generateContentRequest"]["generationConfig"]["responseMimeType"],
            "text/plain",
        )


class _Response:
    def __init__(self, payload: dict) -> None:
        self.status = 200
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int) -> bytes:
        return self.payload


class _FakeUrlOpen:
    def __init__(self) -> None:
        self.requests = []

    def __call__(self, request, timeout: int):
        self.requests.append(request)
        if request.full_url.endswith(":countTokens"):
            return _Response(
                {
                    "totalTokens": 123,
                    "promptTokensDetails": [{"modality": "TEXT", "tokenCount": 10}],
                }
            )
        return _Response(
            {
                "modelVersion": "gemini-3.5-flash",
                "responseId": "response-1",
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": "a,b\n1,2"}]},
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 123,
                    "candidatesTokenCount": 8,
                    "totalTokenCount": 131,
                },
            }
        )


def _package() -> dict:
    dictionary = {
        "0": {"exact_source_span": "A"},
        "1": {"exact_source_span": "1"},
        "2": {"exact_source_span": "2"},
    }
    return {
        "package_id": "package",
        "crop_identity": {"crop_sha256": "a" * 64},
        "candidate_dictionary_hash": "b" * 64,
        "private_candidate_dictionary": dictionary,
        "window": {
            "row_start": 1,
            "row_end": 2,
            "row_count": 2,
            "column_count": 2,
        },
    }


if __name__ == "__main__":
    unittest.main()
