from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import replace

import fitz

from broker_reports_gate1.gate2_provider_adapters import Gate2OpenWebUIProviderConnection
from broker_reports_gate1.pdf_hybrid_contracts import (
    PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
    PDF_HYBRID_EVIDENCE_PACKAGE_SCHEMA,
    PDF_PROVIDER_ATTEMPT_SCHEMA,
    PDF_TABLE_MATERIALIZATION_SCHEMA,
    PDF_TABLE_VALIDATION_SCHEMA,
    hybrid_binding_output_schema,
    validate_binding_output_shape,
)
from broker_reports_gate1.pdf_hybrid_evidence import (
    PdfHybridEvidenceConfig,
    PdfHybridEvidenceError,
    PdfHybridEvidenceFactory,
)
from broker_reports_gate1.pdf_hybrid_materialization import (
    PdfHybridMaterializationError,
    PdfHybridMaterializationFactory,
)
from broker_reports_gate1.pdf_hybrid_provider import (
    PdfHybridProviderConfig,
    PdfHybridProviderFactory,
    _project_gemini_schema,
)
from broker_reports_gate1.pdf_table_classification import (
    PDF_TABLE_CLASSIFIER_POLICY_VERSION,
    PdfTableClassifierConfig,
    PdfTableClassifierFactory,
)
from broker_reports_gate1.pdf_table_raster import (
    PdfTableRasterConfig,
    PdfTableRasterError,
    PdfTableRasterFactory,
)
from broker_reports_gate1.pdf_table_validation import PdfTableValidationFactory


class PdfHybridGoal2ContractTests(unittest.TestCase):
    def test_binding_schema_forbids_free_values_and_has_exact_version(self) -> None:
        schema = hybrid_binding_output_schema()
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["schema_version"]["enum"],
            [PDF_HYBRID_BINDING_OUTPUT_SCHEMA],
        )
        self.assertNotIn("value", json.dumps(schema))
        value = _binding()
        value["value"] = "10"
        self.assertIn(
            "hybrid_binding_free_or_source_value_forbidden",
            validate_binding_output_shape(value),
        )

    def test_incomplete_rectangular_grid_and_missing_empty_cell_fail(self) -> None:
        value = _binding()
        value["rows"][0]["cells"].pop()
        errors = validate_binding_output_shape(value)
        self.assertIn("hybrid_binding_row_width_invalid", errors)
        self.assertIn("hybrid_binding_silent_missing_empty_cell", errors)

    def test_explicit_empty_cell_is_empty_candidate_array(self) -> None:
        value = _binding()
        self.assertEqual(value["rows"][0]["cells"][1], [])
        self.assertEqual(validate_binding_output_shape(value), [])

    def test_ambiguous_contract_is_terminal_without_grid(self) -> None:
        value = _binding(decision="ambiguous")
        value["row_count"] = 0
        value["column_count"] = 0
        value["rows"] = []
        value["uncertainty_codes"] = ["structure_unclear"]
        self.assertEqual(validate_binding_output_shape(value), [])


class PdfTableClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidate = _candidate(columns=3)
        self.projection = {
            "projection_status": "ready",
            "validator_status": "passed",
            "reconstruction_quality": "high",
            "reconstruction_reason_codes": [],
            "header_model": {},
        }

    def classify(self, **signals):
        return PdfTableClassifierFactory().create().classify(
            document_ref="doc",
            document_checksum="a" * 64,
            page_ref="page1",
            page_number=1,
            table_candidate=self.candidate,
            deterministic_projection=self.projection,
            signals=signals,
        )

    def test_simple_table_remains_deterministic(self) -> None:
        result = self.classify(deterministic_header_hierarchy_accepted=True)
        self.assertEqual(result["selected_path"], "deterministic_simple")
        self.assertEqual(result["policy_version"], PDF_TABLE_CLASSIFIER_POLICY_VERSION)
        self.assertFalse(result["authoritative_decision"])

    def test_wide_multirow_and_continuation_route_hybrid(self) -> None:
        self.candidate = _candidate(columns=16)
        wide = self.classify(multi_row_or_merged_header=True)
        self.assertEqual(wide["selected_path"], "hybrid_complex")
        self.assertIn("pdf_hybrid_wide_table", wide["reason_codes"])
        continuation = self.classify(continuation_signal=True)
        self.assertIn("pdf_hybrid_continuation", continuation["reason_codes"])

    def test_current_blocker_routes_hybrid_after_block(self) -> None:
        self.projection.update(
            projection_status="blocked",
            validator_status="blocked",
            reconstruction_reason_codes=[
                "pdf_table_geometry_column_structure_insufficient"
            ],
        )
        result = self.classify()
        self.assertEqual(result["selected_path"], "hybrid_after_deterministic_block")

    def test_missing_source_words_is_unsupported(self) -> None:
        self.candidate["contributing_word_refs"] = []
        result = self.classify(ordered_source_words_complete=False)
        self.assertEqual(result["selected_path"], "unsupported_image_or_text_layer")

    def test_idempotent_and_policy_hash_changes_with_config(self) -> None:
        first = self.classify(deterministic_header_hierarchy_accepted=True)
        second = self.classify(deterministic_header_hierarchy_accepted=True)
        self.assertEqual(first, second)
        other = PdfTableClassifierFactory(
            PdfTableClassifierConfig(wide_column_threshold=10)
        ).create().classify(
            document_ref="doc",
            document_checksum="a" * 64,
            page_ref="page1",
            page_number=1,
            table_candidate=self.candidate,
            deterministic_projection=self.projection,
            signals={"deterministic_header_hierarchy_accepted": True},
        )
        self.assertNotEqual(
            first["policy_configuration_hash"], other["policy_configuration_hash"]
        )


class PdfRasterAndEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        document = fitz.open()
        page = document.new_page(width=200, height=100)
        page.insert_text((12, 22), "A 10")
        cls.pdf_bytes = document.tobytes()
        cls.pdf_sha256 = hashlib.sha256(cls.pdf_bytes).hexdigest()
        document.close()

    def test_raster_hash_transform_dpi_and_budgets(self) -> None:
        renderer = PdfTableRasterFactory().create()
        first = renderer.render(
            pdf_bytes=self.pdf_bytes,
            pdf_sha256=self.pdf_sha256,
            document_ref="doc",
            page_number=1,
            table_ref="table1",
            table_bbox=[5, 5, 80, 35],
            dpi=150,
        )
        repeated = renderer.render(
            pdf_bytes=self.pdf_bytes,
            pdf_sha256=self.pdf_sha256,
            document_ref="doc",
            page_number=1,
            table_ref="table1",
            table_bbox=[5, 5, 80, 35],
            dpi=150,
        )
        self.assertEqual(first["manifest"]["png_sha256"], repeated["manifest"]["png_sha256"])
        self.assertEqual(first["private_png_base64"], repeated["private_png_base64"])
        transform = first["manifest"]["source_to_pixel_transform"]
        self.assertGreater(transform["scale_x"], 1)
        with self.assertRaisesRegex(PdfTableRasterError, "escalation_reason_missing"):
            renderer.render(
                pdf_bytes=self.pdf_bytes,
                pdf_sha256=self.pdf_sha256,
                document_ref="doc",
                page_number=1,
                table_ref="table1",
                table_bbox=[5, 5, 80, 35],
                dpi=200,
            )
        higher = renderer.render(
            pdf_bytes=self.pdf_bytes,
            pdf_sha256=self.pdf_sha256,
            document_ref="doc",
            page_number=1,
            table_ref="table1",
            table_bbox=[5, 5, 80, 35],
            dpi=200,
            escalation_reason="typed_readability_failure",
        )
        self.assertNotEqual(first["manifest"]["crop_id"], higher["manifest"]["crop_id"])
        tiny = PdfTableRasterFactory(
            PdfTableRasterConfig(maximum_width=10)
        ).create()
        with self.assertRaisesRegex(PdfTableRasterError, "dimension_budget"):
            tiny.render(
                pdf_bytes=self.pdf_bytes,
                pdf_sha256=self.pdf_sha256,
                document_ref="doc",
                page_number=1,
                table_ref="table1",
                table_bbox=[5, 5, 80, 35],
                dpi=150,
            )

    def test_evidence_is_reversible_scoped_and_accounted(self) -> None:
        crop = PdfTableRasterFactory().create().render(
            pdf_bytes=self.pdf_bytes,
            pdf_sha256=self.pdf_sha256,
            document_ref="doc",
            page_number=1,
            table_ref="table1",
            table_bbox=[5, 5, 80, 35],
            dpi=150,
        )["manifest"]
        package = PdfHybridEvidenceFactory().create().build(
            document_ref="doc",
            pdf_sha256=self.pdf_sha256,
            page_ref="page1",
            page_number=1,
            table_candidate=_candidate(columns=2),
            pdf_text_layer_projection=_projection(),
            crop_manifest=crop,
            private_crop_artifact_ref="art-crop",
            row_count_hint=1,
            column_count_hint=2,
        )
        self.assertEqual(package["schema_version"], PDF_HYBRID_EVIDENCE_PACKAGE_SCHEMA)
        self.assertEqual(list(package["private_candidate_dictionary"]), ["c0", "c1"])
        self.assertEqual(
            package["private_candidate_dictionary"]["c0"]["word_refs"], ["word1"]
        )
        model = json.dumps(package["model_facing"], ensure_ascii=False)
        self.assertNotIn("word1", model)
        self.assertNotIn("src1", model)
        self.assertTrue(package["component_accounting"]["pre_provider_budget_passed"])
        self.assertGreater(
            package["component_accounting"]["model_facing_text_amplification_ratio"], 0
        )

    def test_duplicate_text_keeps_distinct_ids_and_budget_fails_closed(self) -> None:
        projection = _projection()
        projection["word_inventory"][1]["text"] = "A"
        crop = PdfTableRasterFactory().create().render(
            pdf_bytes=self.pdf_bytes,
            pdf_sha256=self.pdf_sha256,
            document_ref="doc",
            page_number=1,
            table_ref="table1",
            table_bbox=[5, 5, 80, 35],
            dpi=150,
        )["manifest"]
        builder = PdfHybridEvidenceFactory(
            PdfHybridEvidenceConfig(maximum_candidates=1)
        ).create()
        with self.assertRaisesRegex(
            PdfHybridEvidenceError, "candidate_count_budget"
        ) as raised:
            builder.build(
                document_ref="doc",
                pdf_sha256=self.pdf_sha256,
                page_ref="page1",
                page_number=1,
                table_candidate=_candidate(columns=2),
                pdf_text_layer_projection=projection,
                crop_manifest=crop,
                private_crop_artifact_ref="art-crop",
                row_count_hint=1,
                column_count_hint=2,
            )
        self.assertEqual(raised.exception.component_accounting["candidate_count"], 2)
        self.assertFalse(
            raised.exception.component_accounting["pre_provider_budget_passed"]
        )

    def test_source_word_scope_mismatch_fails(self) -> None:
        candidate = _candidate(columns=2)
        candidate["contributing_word_refs"].append("missing")
        crop = {
            "table_ref": "table1",
            "pdf_sha256": self.pdf_sha256,
            "page_number": 1,
            "png_sha256": "b" * 64,
            "declared_table_bbox": [5, 5, 80, 35],
        }
        with self.assertRaisesRegex(PdfHybridEvidenceError, "scope_incomplete"):
            PdfHybridEvidenceFactory().create().build(
                document_ref="doc",
                pdf_sha256=self.pdf_sha256,
                page_ref="page1",
                page_number=1,
                table_candidate=candidate,
                pdf_text_layer_projection=_projection(),
                crop_manifest=crop,
                private_crop_artifact_ref="art-crop",
                row_count_hint=1,
                column_count_hint=2,
            )


class PdfMaterializationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.evidence = _evidence()
        self.binding = _binding()

    def test_valid_full_grid_and_repeatability(self) -> None:
        material = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=self.evidence,
            binding_output=self.binding,
        )
        self.assertEqual(material["schema_version"], PDF_TABLE_MATERIALIZATION_SCHEMA)
        self.assertEqual(len(material["placement_checksum"]), 64)
        self.assertEqual(len(material["cells"]), 2)
        self.assertEqual(material["explicit_empty_positions"], [[1, 2]])
        validation = PdfTableValidationFactory().create().validate(
            evidence_package=self.evidence,
            binding_output=self.binding,
            materialization=material,
            classification=_classification(),
            repeated_materialization_checksum=material["materialization_checksum"],
            require_repeatability=True,
        )
        self.assertEqual(validation["schema_version"], PDF_TABLE_VALIDATION_SCHEMA)
        self.assertEqual(validation["aggregate_result"], "accepted_shadow")

    def test_invalid_id_and_candidate_reuse_fail_closed(self) -> None:
        invalid = _binding()
        invalid["rows"][0]["cells"][0] = ["invented"]
        with self.assertRaisesRegex(PdfHybridMaterializationError, "unresolved"):
            PdfHybridMaterializationFactory().create().materialize(
                evidence_package=self.evidence,
                binding_output=invalid,
            )
        duplicate = _binding()
        duplicate["rows"][0]["cells"][1] = ["c0"]
        material = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=self.evidence,
            binding_output=duplicate,
        )
        validation = PdfTableValidationFactory().create().validate(
            evidence_package=self.evidence,
            binding_output=duplicate,
            materialization=material,
            classification=_classification(),
        )
        self.assertEqual(validation["aggregate_result"], "blocked")
        self.assertIn("pdf_hybrid_candidate_duplicate_use", validation["reason_codes"])

    def test_identity_and_nonrepeatability_fail(self) -> None:
        material = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=self.evidence,
            binding_output=self.binding,
        )
        mismatch = dict(self.binding, crop_sha256="bad")
        validation = PdfTableValidationFactory().create().validate(
            evidence_package=self.evidence,
            binding_output=mismatch,
            materialization=material,
            classification=_classification(),
            repeated_materialization_checksum="different",
            require_repeatability=True,
        )
        self.assertIn("pdf_hybrid_crop_identity_mismatch", validation["reason_codes"])
        self.assertIn("pdf_hybrid_non_repeatable_materialization", validation["reason_codes"])

    def test_materialization_checksum_tampering_fails(self) -> None:
        material = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=self.evidence,
            binding_output=self.binding,
        )
        material["cells"][0]["explicit_empty"] = True
        validation = PdfTableValidationFactory().create().validate(
            evidence_package=self.evidence,
            binding_output=self.binding,
            materialization=material,
            classification=_classification(),
        )
        self.assertIn(
            "pdf_hybrid_materialization_checksum_mismatch",
            validation["reason_codes"],
        )
        self.assertIn(
            "pdf_hybrid_placement_checksum_mismatch",
            validation["reason_codes"],
        )

    def test_wide_blocked_geometry_requires_human_review(self) -> None:
        material = PdfHybridMaterializationFactory().create().materialize(
            evidence_package=self.evidence,
            binding_output=self.binding,
        )
        classification = _classification()
        classification["measured_signals"].update(
            column_confidence="blocked",
            wide_table=True,
        )
        validation = PdfTableValidationFactory().create().validate(
            evidence_package=self.evidence,
            binding_output=self.binding,
            materialization=material,
            classification=classification,
        )
        self.assertEqual(validation["aggregate_result"], "human_review_required")
        self.assertFalse(validation["structural_placement_validated"])
        self.assertIn(
            "pdf_hybrid_wide_column_placement_not_independently_validated",
            validation["reason_codes"],
        )


class PdfProviderAdapterTests(unittest.TestCase):
    def test_schema_projection_preserves_property_names(self) -> None:
        projected, count = _project_gemini_schema(
            {
                "type": "object",
                "properties": {"candidate_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["candidate_ids"],
                "const": "removed",
            }
        )
        self.assertIn("candidate_ids", projected["properties"])
        self.assertNotIn("const", projected)
        self.assertEqual(count, 1)

    def test_exact_model_qualification(self) -> None:
        fake = _FakeUrlOpen(
            [
                (
                    200,
                    {
                        "name": "models/gemini-3.5-flash",
                        "supportedGenerationMethods": ["generateContent"],
                        "outputTokenLimit": 65536,
                    },
                )
            ]
        )
        adapter = PdfHybridProviderFactory(urlopen_fn=fake).create_with_connection(
            Gate2OpenWebUIProviderConnection(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key="secret",
            )
        )
        result = adapter.qualify()
        self.assertEqual(result["status"], "qualified")
        self.assertTrue(result["exact_model_match"])

    def test_http_200_invalid_json_and_resolved_model_mismatch_are_failures(self) -> None:
        for payload, expected in (
            ({"candidates": [{"content": {"parts": [{"text": "not-json"}]}}]}, "parse_failure"),
            (
                _provider_payload(_binding(), model="models/other"),
                "resolved_model_mismatch",
            ),
        ):
            fake = _FakeUrlOpen([(200, payload)])
            adapter = PdfHybridProviderFactory(urlopen_fn=fake).create_with_connection(
                Gate2OpenWebUIProviderConnection(
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                    api_key="secret",
                )
            )
            result = adapter.invoke(
                evidence_package=_provider_evidence(),
                png_bytes=b"png",
                attempt_number=1,
                attempt_lineage=[],
            )
            self.assertEqual(result["attempt"]["schema_version"], PDF_PROVIDER_ATTEMPT_SCHEMA)
            self.assertEqual(result["attempt"]["terminal_failure_class"], expected)
            self.assertFalse(result["attempt"]["hidden_retry"])
            self.assertFalse(result["attempt"]["provider_failover"])

    def test_same_evidence_attempt_lineage_is_explicit(self) -> None:
        fake = _FakeUrlOpen([(200, _provider_payload(_binding()))])
        adapter = PdfHybridProviderFactory(urlopen_fn=fake).create_with_connection(
            Gate2OpenWebUIProviderConnection(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key="secret",
            )
        )
        result = adapter.invoke(
            evidence_package=_provider_evidence(),
            png_bytes=b"png",
            attempt_number=2,
            attempt_lineage=["pdfhybridtask_x_a1"],
        )
        self.assertEqual(result["attempt"]["attempt_number"], 2)
        self.assertEqual(result["attempt"]["attempt_lineage"], ["pdfhybridtask_x_a1"])

    def test_count_tokens_uses_exact_generate_request_with_inline_image(self) -> None:
        fake = _FakeUrlOpen(
            [
                (
                    200,
                    {
                        "totalTokens": 1234,
                        "promptTokensDetails": [
                            {"modality": "IMAGE", "tokenCount": 258}
                        ],
                    },
                )
            ]
        )
        adapter = PdfHybridProviderFactory(urlopen_fn=fake).create_with_connection(
            Gate2OpenWebUIProviderConnection(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key="secret",
            )
        )
        result = adapter.count_tokens(
            evidence_package=_provider_evidence(),
            png_bytes=b"png",
        )
        self.assertEqual(result["total_tokens"], 1234)
        self.assertTrue(fake.requests[0].full_url.endswith(":countTokens"))
        body = json.loads(fake.requests[0].data.decode("utf-8"))
        generated = body["generateContentRequest"]
        self.assertEqual(generated["model"], "models/gemini-3.5-flash")
        self.assertEqual(
            generated["contents"][0]["parts"][1]["inlineData"]["mimeType"],
            "image/png",
        )
        self.assertIn(
            "responseJsonSchema", generated["generationConfig"]
        )

    def test_rate_limit_timeout_and_response_budgets_are_terminal(self) -> None:
        cases = (
            (_FakeUrlOpen([(429, {"error": {"code": 429}})]), "rate_limit"),
            (_TimeoutUrlOpen(), "timeout_or_transport"),
            (
                _FakeUrlOpen([(200, {"oversized": "x" * (2 * 1024 * 1024)})]),
                "response_budget",
            ),
            (
                _FakeUrlOpen(
                    [(200, _provider_payload(_binding(), finish_reason="MAX_TOKENS"))]
                ),
                "response_budget",
            ),
        )
        for transport, expected in cases:
            adapter = PdfHybridProviderFactory(
                urlopen_fn=transport
            ).create_with_connection(
                Gate2OpenWebUIProviderConnection(
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                    api_key="secret",
                )
            )
            result = adapter.invoke(
                evidence_package=_provider_evidence(),
                png_bytes=b"png",
                attempt_number=1,
                attempt_lineage=[],
            )
            self.assertEqual(result["attempt"]["terminal_failure_class"], expected)
            self.assertIsNone(result["binding_output"])
            self.assertFalse(result["attempt"]["hidden_retry"])


def _candidate(columns: int) -> dict:
    return {
        "table_candidate_ref": "table1",
        "bbox_ref": "bbox_table",
        "page_ref": "page1",
        "rows_total": 1,
        "geometry_confidence": 0.9,
        "table_strategy_ref": "ruled_lines_v0",
        "contributing_word_refs": ["word1", "word2"],
        "cell_inventory": [
            {
                "row_ordinal": 1,
                "column_ordinal": index,
                "word_refs": [f"word{min(index, 2)}"],
            }
            for index in range(1, columns + 1)
        ],
    }


def _projection() -> dict:
    return {
        "bbox_inventory": [
            {"bbox_ref": "bbox_table", "bbox": [5, 5, 80, 35]},
            {"bbox_ref": "bbox1", "bbox": [10, 10, 20, 20]},
            {"bbox_ref": "bbox2", "bbox": [25, 10, 40, 20]},
        ],
        "word_inventory": [
            {
                "word_ref": "word1",
                "page_ref": "page1",
                "bbox_ref": "bbox1",
                "source_value_ref": "src1",
                "text": "A",
                "text_checksum_ref": "chk1",
                "geometry_reading_order": 1,
                "parser_ordinal": 1,
            },
            {
                "word_ref": "word2",
                "page_ref": "page1",
                "bbox_ref": "bbox2",
                "source_value_ref": "src2",
                "text": "10",
                "text_checksum_ref": "chk2",
                "geometry_reading_order": 2,
                "parser_ordinal": 2,
            },
        ],
    }


def _binding(decision: str = "bound") -> dict:
    return {
        "schema_version": PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
        "package_id": "pkg",
        "crop_sha256": "crop",
        "candidate_dictionary_hash": "dict",
        "decision": decision,
        "row_count": 1,
        "column_count": 2,
        "header_rows": [1],
        "header_hierarchy": [],
        "rows": [
            {
                "row_ordinal": 1,
                "row_kind": "header",
                "cells": [
                    ["c0"],
                    [],
                ],
            }
        ],
        "spans": [],
        "uncertainty_codes": [],
    }


def _evidence() -> dict:
    return {
        "package_id": "pkg",
        "crop_identity": {"crop_sha256": "crop"},
        "candidate_dictionary_hash": "dict",
        "private_candidate_dictionary": {
            "c0": {
                "exact_source_span": "A",
                "source_value_refs": ["src1"],
                "word_refs": ["word1"],
            }
        },
    }


def _classification() -> dict:
    return {"measured_signals": {"row_count_hint": 1, "column_count_hint": 2}}


def _provider_evidence() -> dict:
    value = _evidence()
    value.update(
        package_hash="package-hash",
        output_schema=hybrid_binding_output_schema(),
        model_facing={"task": "bind", "identity": {"package_id": "pkg"}},
    )
    value["crop_identity"]["crop_sha256"] = hashlib.sha256(b"png").hexdigest()
    binding = _binding()
    binding["crop_sha256"] = value["crop_identity"]["crop_sha256"]
    return value


def _provider_payload(
    binding: dict,
    model: str = "models/gemini-3.5-flash",
    finish_reason: str = "STOP",
) -> dict:
    adjusted = dict(binding)
    adjusted["crop_sha256"] = hashlib.sha256(b"png").hexdigest()
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": json.dumps(adjusted)}]},
                "finishReason": finish_reason,
            }
        ],
        "modelVersion": model,
        "responseId": "response-1",
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 20,
            "totalTokenCount": 30,
        },
    }


class _FakeResponse:
    def __init__(self, status: int, payload: dict) -> None:
        self.status = status
        self.body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class _FakeUrlOpen:
    def __init__(self, responses: list[tuple[int, dict]]) -> None:
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        status, payload = self.responses.pop(0)
        return _FakeResponse(status, payload)


class _TimeoutUrlOpen:
    def __call__(self, request, timeout):
        raise TimeoutError("synthetic timeout")


if __name__ == "__main__":
    unittest.main()
