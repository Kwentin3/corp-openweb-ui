from __future__ import annotations

import hashlib
import json
import unittest

from broker_reports_gate1.gate2_provider_adapters import (
    Gate2OpenWebUIProviderConnection,
)
from broker_reports_gate1.pdf_csv_experiment import (
    PDF_CSV_TOPOLOGY_SCHEMA,
    PdfCsvExperimentFactory,
)
from broker_reports_gate1.pdf_grid_experiment import (
    PDF_COMPACT_GRID_SCHEMA,
    PdfGridExperimentError,
    PdfGridExperimentFactory,
)
from broker_reports_gate1.pdf_grid_experiment_provider import (
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)


class PdfGridExperimentContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = PdfGridExperimentFactory().create()

    def test_free_csv_dialect_and_natural_shape_are_separate(self) -> None:
        parsed = PdfCsvExperimentFactory().create().inspect_free_csv("a,b\n1,2,3")
        self.assertEqual(parsed["row_widths"], [2, 3])
        self.assertFalse(parsed["rectangular"])
        self.assertTrue(parsed["byte_complete_parse"])
        self.assertIsNone(parsed["column_count"])

    def test_compact_grid_is_schema_constrained_and_routes_to_binding_contract(self) -> None:
        package = _package()
        schema = self.runtime.compact_output_schema(
            expected_rows=2, expected_columns=2
        )
        self.assertEqual(schema["$id"], PDF_COMPACT_GRID_SCHEMA)
        self.assertFalse(schema["additionalProperties"])
        parsed = self.runtime.parse_compact_output(
            {"g": [["0", "1"], ["", "2+3"]]},
            expected_rows=2,
            expected_columns=2,
            candidate_ids=["0", "1", "2", "3"],
        )
        binding = self.runtime.binding_from_compact_grid(
            evidence_package=package,
            parsed=parsed,
            global_header_depth=1,
        )
        self.assertEqual(parsed["candidate_coverage_ratio"], 1.0)
        self.assertEqual(binding["rows"][1]["cells"], [[], ["2", "3"]])
        self.assertNotIn("topology", parsed)

    def test_compact_grid_fails_closed_on_shape_ownership_and_extra_keys(self) -> None:
        cases = (
            (
                {"g": [["0", "1"]]},
                "pdf_grid_row_count_mismatch",
            ),
            (
                {"g": [["0", "1"], ["", "2"]]},
                "pdf_grid_candidate_ownership_incomplete",
            ),
            (
                {"g": [["0", "1"], ["", "2+3"]], "x": 1},
                "pdf_grid_root_contract_invalid",
            ),
        )
        for value, code in cases:
            with self.subTest(code=code), self.assertRaisesRegex(
                PdfGridExperimentError, code
            ):
                self.runtime.parse_compact_output(
                    value,
                    expected_rows=2,
                    expected_columns=2,
                    candidate_ids=["0", "1", "2", "3"],
                )

    def test_topology_is_validated_without_repeating_or_owning_grid(self) -> None:
        topology = PdfCsvExperimentFactory().create().parse_topology_json(
            {
                "v": PDF_CSV_TOPOLOGY_SCHEMA,
                "d": "a",
                "r": 2,
                "c": 2,
                "h": 1,
                "m": [],
                "hh": [],
                "k": None,
                "rb": [],
                "cb": [],
                "u": ["header_ambiguous"],
            },
            expected_rows=2,
            expected_columns=2,
            expected_continuation=None,
        )
        self.assertTrue(topology["independently_validated"])
        self.assertFalse(topology["grid_repeated"])
        self.assertEqual(topology["d"], "a")


class PdfGridExperimentProviderTests(unittest.TestCase):
    def test_provider_uses_json_schema_and_has_terminal_no_retry_attempt(self) -> None:
        transport = _FakeUrlOpen()
        adapter = PdfGridExperimentProviderFactory(
            PdfGridProviderConfig(maximum_counted_input_tokens=1000),
            urlopen_fn=transport,
        ).create_with_connection(
            Gate2OpenWebUIProviderConnection(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key="secret",
            )
        )
        png = b"png"
        crop_hash = hashlib.sha256(png).hexdigest()
        model_view = {"i": "place ids", "c": [["0", "A"]]}
        schema = PdfGridExperimentFactory().create().compact_output_schema(
            expected_rows=1,
            expected_columns=1,
        )
        counted = adapter.count_tokens(
            model_view=model_view,
            output_schema=schema,
            png_bytes=png,
            crop_sha256=crop_hash,
        )
        result = adapter.invoke(
            task_id="gridtask",
            model_view=model_view,
            output_schema=schema,
            png_bytes=png,
            crop_sha256=crop_hash,
            attempt_number=1,
            attempt_lineage=[],
        )
        self.assertEqual(counted["total_tokens"], 123)
        self.assertEqual(result["json_output"], {"g": [["0"]]})
        self.assertEqual(result["attempt"]["finish_reason"], "STOP")
        self.assertFalse(result["attempt"]["hidden_retry"])
        self.assertFalse(result["attempt"]["provider_failover"])
        request_body = json.loads(transport.requests[0].data.decode("utf-8"))
        generation = request_body["generateContentRequest"]["generationConfig"]
        self.assertEqual(generation["responseMimeType"], "application/json")
        self.assertIn("responseJsonSchema", generation)


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
            return _Response({"totalTokens": 123})
        return _Response(
            {
                "modelVersion": "gemini-3.5-flash",
                "responseId": "response-1",
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": '{"g":[["0"]]}'}]},
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
    return {
        "package_id": "package",
        "crop_identity": {"crop_sha256": "a" * 64},
        "candidate_dictionary_hash": "b" * 64,
        "window": {
            "row_start": 1,
            "row_end": 2,
            "row_count": 2,
            "column_count": 2,
        },
        "model_facing": {
            "h": ["header", 1],
            "c": [
                ["0", "A", "t", 0.0, 0.0, 0.4, 0.4],
                ["1", "B", "t", 0.5, 0.0, 1.0, 0.4],
                ["2", "C", "t", 0.5, 0.5, 0.7, 1.0],
                ["3", "D", "t", 0.7, 0.5, 1.0, 1.0],
            ],
        },
    }


if __name__ == "__main__":
    unittest.main()
