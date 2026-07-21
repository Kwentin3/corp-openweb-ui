from __future__ import annotations

import ast
import base64
import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "local_pdf_table_strategy_benchmark.py"
CONTRACTS_PATH = ROOT / "scripts" / "pdf_table_strategy_benchmark_contracts.py"
SCORER_PATH = ROOT / "scripts" / "local_pdf_table_strategy_benchmark_score.py"
MANIFEST_PATH = ROOT / "benchmarks" / "pdf_table_strategy_v1" / "manifest.json"
REFERENCE_PATH = (
    ROOT / "benchmarks" / "pdf_table_strategy_v1" / "reference.private.json"
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTRACTS = _load_module("pdf_table_strategy_benchmark_contracts_test", CONTRACTS_PATH)
RUNNER = _load_module("local_pdf_table_strategy_benchmark_test", RUNNER_PATH)
SCORER = _load_module("local_pdf_table_strategy_benchmark_score_test", SCORER_PATH)


EXPECTED_CASES = {
    "betterment_p02": (
        "betterment",
        2,
        "betterment-financial-condition-2024.pdf",
        "fbe6a299b05615643a0f0264568c65a64bd857b6b77752163b8c2e52bbcbf71e",
        288909,
    ),
    "betterment_p04": (
        "betterment",
        4,
        "betterment-financial-condition-2024.pdf",
        "fbe6a299b05615643a0f0264568c65a64bd857b6b77752163b8c2e52bbcbf71e",
        288909,
    ),
    "drivewealth_p07": (
        "drivewealth",
        7,
        "drivewealth-institutional-financial-condition-2024.pdf",
        "738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57",
        1496464,
    ),
    "drivewealth_p09": (
        "drivewealth",
        9,
        "drivewealth-institutional-financial-condition-2024.pdf",
        "738a0279eba3020c9a6cf3a650df254d0a2a8a0800aae80b4889efcc0a8bec57",
        1496464,
    ),
    "moomoo_annual_p14": (
        "moomoo",
        14,
        "moomoo-financial-condition-2025.pdf",
        "bad1e5fa045f0735f02487aca14236d84037f82fd2b1230ee3c56ba3420aee67",
        1865552,
    ),
    "moomoo_midyear_p10": (
        "moomoo",
        10,
        "moomoo-financial-condition-midyear-2025.pdf",
        "766448b2bf8b9ebe9172e4a07b0392134787a3b642288a93fbe6c0f9999ed0d3",
        233753,
    ),
    "ibkr_annual_p11": (
        "ibkr",
        11,
        "ibkr-financial-condition-2025.pdf",
        "6486885e58867d382bd433228193e476a07b6cea2061ddbd74bef1dc6c65a118",
        1238967,
    ),
    "ibkr_midyear_p03": (
        "ibkr",
        3,
        "ibkr-financial-condition-midyear-2025.pdf",
        "d635df4866a040ce665bfde0da74dbf4dc8933931337a1b023377bf02cf60c2c",
        281480,
    ),
}


@unittest.skipUnless(
    REFERENCE_PATH.exists(),
    "offline private benchmark reference is required",
)
class BrokerReportsPdfTableStrategyBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))

    def test_run_help_exposes_no_reference_argument(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(RUNNER_PATH), "run", "--help"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        self.assertNotIn("--reference", completed.stdout)
        self.assertIn("--manifest", completed.stdout)
        self.assertIn("--corpus-root", completed.stdout)

    def test_frozen_manifest_and_reference_have_exact_scope_and_hash_binding(
        self,
    ) -> None:
        manifest_cases = self.manifest["cases"]
        reference_cases = self.reference["cases"]
        self.assertEqual(list(EXPECTED_CASES), [item["case_id"] for item in manifest_cases])
        self.assertEqual(list(EXPECTED_CASES), [item["case_id"] for item in reference_cases])
        self.assertEqual(8, self.manifest["case_count"])
        self.assertEqual(8, self.reference["case_count"])
        self.assertEqual(
            CONTRACTS.sha256_json(self.manifest),
            self.reference["manifest_sha256"],
        )
        self.assertEqual(
            {"betterment", "drivewealth", "moomoo", "ibkr"},
            {item["broker"] for item in manifest_cases},
        )
        self.assertEqual(
            set(self.manifest["required_categories"]),
            {
                "simple_ruled",
                "borderless",
                "sparse_financial",
                "multi_row_header",
                "currency_symbol",
                "compound_page",
                "without_text_layer",
                "raster_image",
            },
        )
        self.assertTrue(
            set(self.manifest["required_categories"])
            <= {
                tag
                for item in manifest_cases
                for tag in item["category_tags"]
            }
        )
        for case in manifest_cases:
            broker, page, filename, pdf_sha, pdf_bytes = EXPECTED_CASES[
                case["case_id"]
            ]
            self.assertEqual(broker, case["broker"])
            self.assertEqual(page, case["page_number"])
            self.assertEqual(filename, case["relative_pdf"])
            self.assertEqual(pdf_sha, case["pdf_sha256"])
            self.assertEqual(pdf_bytes, case["pdf_bytes"])
            self.assertEqual([0.0, 0.0, 612.0, 792.0], case["page_bbox_points"])
            self.assertEqual(150, case["render_dpi"])
            self.assertNotIn("expected_kind", case)
        self.assertEqual("negative", reference_cases[0]["expected_kind"])
        self.assertTrue(
            all("expected_kind" in item for item in reference_cases)
        )
        self.assertFalse(self.reference["provenance"]["human_reviewed"])
        self.assertNotIn("USD", REFERENCE_PATH.read_text(encoding="utf-8"))

    def test_manifest_validator_rejects_reference_leakage(self) -> None:
        RUNNER._validate_manifest(copy.deepcopy(self.manifest))
        for key, value in (
            ("expected_kind", "negative"),
            ("human_reference", {"tables": []}),
            ("ground_truth", {"bbox": [0.0, 0.0, 1.0, 1.0]}),
        ):
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.manifest)
                candidate["cases"][0][key] = value
                with self.assertRaises(RUNNER.BenchmarkError) as raised:
                    RUNNER._validate_manifest(candidate)
                self.assertEqual("benchmark_manifest_reference_leakage", raised.exception.code)

    def test_manifest_validator_rejects_retry_and_failover(self) -> None:
        for key, code in (
            ("hidden_retry", "benchmark_manifest_hidden_retry_invalid"),
            ("provider_failover", "benchmark_manifest_provider_failover_invalid"),
        ):
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.manifest)
                candidate["provider_contract"][key] = True
                with self.assertRaises(RUNNER.BenchmarkError) as raised:
                    RUNNER._validate_manifest(candidate)
                self.assertEqual(code, raised.exception.code)

    def test_detection_validator_is_closed_and_requires_explicit_uncertainty(
        self,
    ) -> None:
        valid = _detection_fixture()
        self.assertEqual([], CONTRACTS.validate_detection_output(valid))

        closed = copy.deepcopy(valid)
        closed["regions"][0]["cells"] = []
        self.assertIn(
            "benchmark_detection_region_keys_invalid",
            CONTRACTS.validate_detection_output(closed),
        )

        present_without_region = copy.deepcopy(valid)
        present_without_region["regions"] = []
        self.assertIn(
            "benchmark_detection_present_without_region",
            CONTRACTS.validate_detection_output(present_without_region),
        )

        uncertain_without_reason = copy.deepcopy(valid)
        uncertain_without_reason["presence"] = "uncertain"
        uncertain_without_reason["regions"] = []
        self.assertIn(
            "benchmark_detection_uncertain_without_reason",
            CONTRACTS.validate_detection_output(uncertain_without_reason),
        )

    def test_bbox_order_is_explicit_in_every_v2_prompt_and_schema(self) -> None:
        expected_order = ["x0", "y0", "x1", "y1"]
        views = (
            CONTRACTS.direct_page_model_view(case_id="case_1", page_number=1),
            CONTRACTS.detection_model_view(case_id="case_1", page_number=1),
            CONTRACTS.crop_extraction_model_view(
                case_id="case_1", page_number=1, region_index=1
            ),
        )
        for view in views:
            self.assertEqual(expected_order, view["rules"]["bbox_order"])
            self.assertEqual("top_left", view["rules"]["bbox_origin"])
            self.assertIn("[x0,y0,x1,y1]", view["task"])
            self.assertTrue(view["prompt_contract_version"].endswith("_v2"))

        bbox_schema = CONTRACTS.detection_schema()["properties"]["regions"][
            "items"
        ]["properties"]["bbox"]
        self.assertIn("[x0,y0,x1,y1]", bbox_schema["description"])

    def test_unified_validator_enforces_closed_rectangular_and_explicit_empty(
        self,
    ) -> None:
        valid = _resolved_extraction()
        self.assertEqual([], CONTRACTS.validate_unified_extraction(valid))

        closed = copy.deepcopy(valid)
        closed["tables"][0]["physical"]["inferred_grid"] = True
        self.assertIn(
            "benchmark_extraction_physical_keys_invalid",
            CONTRACTS.validate_unified_extraction(closed),
        )

        missing_cell = copy.deepcopy(valid)
        missing_cell["tables"][0]["physical"]["cells"].pop()
        errors = CONTRACTS.validate_unified_extraction(missing_cell)
        self.assertIn("benchmark_extraction_cell_count_mismatch", errors)
        self.assertIn("benchmark_extraction_rectangular_cell_coverage_invalid", errors)

        implicit_empty = copy.deepcopy(valid)
        implicit_empty["tables"][0]["physical"]["cells"][-1][
            "explicit_empty"
        ] = False
        self.assertIn(
            "benchmark_extraction_explicit_empty_mismatch",
            CONTRACTS.validate_unified_extraction(implicit_empty),
        )

    def test_unified_validator_preserves_explicit_ambiguity(self) -> None:
        missing = _resolved_extraction()
        missing["document_status"] = "ambiguous"
        missing["uncertainty_codes"] = ["multiple_physical_structures"]
        missing["tables"][0]["decision"] = "ambiguous"
        missing["tables"][0]["uncertainty_codes"] = [
            "multiple_physical_structures"
        ]
        self.assertIn(
            "benchmark_extraction_ambiguous_alternatives_missing",
            CONTRACTS.validate_unified_extraction(missing),
        )

        explicit = copy.deepcopy(missing)
        table = explicit["tables"][0]
        table["alternatives"] = [
            {
                "alternative_id": "alternative_1",
                "physical": copy.deepcopy(table["physical"]),
                "semantic": copy.deepcopy(table["semantic"]),
                "uncertainty_codes": ["multiple_physical_structures"],
            }
        ]
        self.assertEqual([], CONTRACTS.validate_unified_extraction(explicit))

    def test_currency_symbol_remains_unknown_and_usd_inference_is_detected(
        self,
    ) -> None:
        extraction = _resolved_extraction(bottom_right="$ 1", currency=True)
        self.assertEqual([], CONTRACTS.validate_unified_extraction(extraction))
        qualifier = extraction["tables"][0]["semantic"]["qualifiers"][0]
        self.assertEqual("currency", qualifier["kind"])
        self.assertIsNone(qualifier["normalized_code"])

        inferred = copy.deepcopy(extraction)
        inferred["tables"][0]["semantic"]["qualifiers"][0][
            "normalized_code"
        ] = "USD"
        self.assertEqual(
            {"USD"},
            SCORER._invented_currency_codes(inferred["tables"][0]),
        )

    def test_currency_column_split_is_structure_error_not_value_invention(
        self,
    ) -> None:
        reference = {"cells": [["$ 24,435,440"]]}
        predicted = {
            "cells": [
                {"cell_id": "c1", "text": "$"},
                {"cell_id": "c2", "text": "24,435,440"},
            ]
        }

        self.assertEqual(
            {"invented": 0, "mutated": 0, "omitted": 0},
            SCORER._visible_atom_differences(reference, predicted),
        )

    def test_operation_cost_prices_inferred_thinking_at_output_rate(self) -> None:
        terminal = {
            "target_manifest": {
                "provider_contract": {
                    "pricing": {
                        "currency": "USD",
                        "input_usd_per_1m_tokens": 1.5,
                        "output_usd_per_1m_tokens": 9.0,
                    }
                }
            }
        }
        operation = {
            "image_bytes": 1000,
            "model_view_bytes": 200,
            "schema_bytes": 300,
            "count_tokens": {"total_tokens": 90},
            "response_bytes": 500,
            "visible_output_bytes": 100,
            "attempt": {
                "duration_ms": 42,
                "provider": "google",
                "model_requested": "models/gemini-3.5-flash",
                "model_resolved": "models/gemini-3.5-flash",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 20,
                    "total_tokens": 130,
                },
                "hidden_retry": False,
                "provider_failover": False,
            },
        }

        metrics = SCORER._operation_metrics([operation], terminal=terminal)

        self.assertEqual(10, metrics["reasoning_tokens"])
        self.assertEqual(420.0, metrics["cost_microusd"])
        self.assertEqual(1500, metrics["input_bytes"])
        self.assertEqual(1, metrics["priced_operations"])

    def test_evidence_overlay_is_non_mutating_and_has_all_terminal_statuses(
        self,
    ) -> None:
        extraction = _single_cell_extraction("Cash")
        before = copy.deepcopy(extraction)
        inventories = {
            "traced": [
                {"parser_ordinal": 1, "text": "Cash", "bbox": [10, 10, 20, 20]}
            ],
            "ambiguous": [
                {"parser_ordinal": 1, "text": "Cash", "bbox": [10, 10, 20, 20]},
                {"parser_ordinal": 2, "text": "Cash", "bbox": [30, 10, 40, 20]},
            ],
            "not_found": [
                {"parser_ordinal": 1, "text": "Other", "bbox": [10, 10, 20, 20]}
            ],
            "unsupported": [],
        }

        for expected, words in inventories.items():
            with self.subTest(status=expected):
                overlay = CONTRACTS.validate_extraction_evidence(
                    extraction,
                    words,
                    page_width=100.0,
                    page_height=100.0,
                )
                self.assertEqual(expected, overlay["cells"][0]["status"])
                self.assertEqual(1, overlay["summary"]["status_counts"][expected])
                self.assertTrue(overlay["extraction_unchanged"])
                self.assertFalse(overlay["table_construction_performed"])
                self.assertFalse(overlay["value_mutation_performed"])
                self.assertEqual(before, extraction)

    def test_crop_bbox_projection_is_exact_and_does_not_mutate_input(self) -> None:
        extraction = _resolved_extraction()
        before = copy.deepcopy(extraction)

        projected = CONTRACTS.project_crop_bbox_to_page(
            extraction,
            [0.25, 0.2, 0.75, 0.8],
        )

        self.assertEqual(before, extraction)
        table = projected["tables"][0]
        self.assertEqual([0.25, 0.2, 0.75, 0.8], table["bbox"])
        self.assertEqual(CONTRACTS.PAGE_NORMALIZED, table["coordinate_space"])
        self.assertEqual(
            [0.25, 0.2, 0.5, 0.5],
            table["physical"]["cells"][0]["bbox"],
        )
        self.assertEqual([], CONTRACTS.validate_unified_extraction(projected))

    def test_provider_operation_calls_adapter_once_with_single_attempt_lineage(
        self,
    ) -> None:
        provider = _RecordingProvider()
        artifact_dir = self.root / "artifacts" / "case_1"
        artifact_dir.mkdir(parents=True)

        result = RUNNER._provider_operation(
            provider=provider,
            task_id="case_1_direct",
            kind="direct_page_extraction",
            model_view={"identity": {"package_id": "package_1"}},
            output_schema={"type": "object"},
            png_bytes=b"png-bytes",
            artifact_dir=artifact_dir,
            artifact_stem="direct",
        )

        self.assertEqual(1, provider.count_calls)
        self.assertEqual(1, provider.invoke_calls)
        self.assertEqual(1, provider.invoke_arguments["attempt_number"])
        self.assertEqual([], provider.invoke_arguments["attempt_lineage"])
        self.assertFalse(result["attempt"]["hidden_retry"])
        self.assertFalse(result["attempt"]["provider_failover"])
        self.assertTrue((artifact_dir / "direct.model_view.json").is_file())
        self.assertTrue((artifact_dir / "direct.extraction.private.json").is_file())

    def test_strategy_c_replays_b_extraction_without_provider_operation(self) -> None:
        provider = _SequencedProvider()
        result = RUNNER._run_case(
            case={
                "case_id": "synthetic_case",
                "broker": "synthetic",
                "category_tags": ["simple_ruled"],
                "page_number": 1,
                "page_bbox_points": [0.0, 0.0, 612.0, 792.0],
                "render_dpi": 150,
                "pdf_sha256": "a" * 64,
                "relative_pdf": "synthetic.pdf",
                "pdf_bytes": 4,
            },
            pdf_bytes=b"%PDF",
            parse_result=SimpleNamespace(
                pages=[
                    {
                        "width": 612.0,
                        "height": 792.0,
                        "word_inventory": [],
                    }
                ]
            ),
            renderer=_RasterBoundary(),
            provider=provider,
            output_dir=self.root,
        )

        strategy_b = result["strategies"]["B"]
        strategy_c = result["strategies"]["C"]
        self.assertEqual("completed", result["terminal_status"])
        self.assertEqual(strategy_b["extraction"], strategy_c["extraction"])
        self.assertEqual(
            CONTRACTS.sha256_json(strategy_b["extraction"]),
            strategy_c["extraction_sha256"],
        )
        self.assertEqual(
            strategy_c["extraction_sha256"],
            strategy_c["replayed_extraction_sha256"],
        )
        self.assertEqual("B", strategy_c["replayed_from_strategy"])
        self.assertEqual(0, strategy_c["provider_calls"])
        self.assertEqual([], strategy_c["operations"])
        self.assertEqual(3, provider.count_calls)
        self.assertEqual(3, provider.invoke_calls)

    def test_scorer_rejects_terminal_tamper_before_reference_access(self) -> None:
        terminal_path, seal_path = self._write_terminal_and_seal()
        terminal_path.write_bytes(terminal_path.read_bytes() + b"\n")
        missing_reference = self.root / "missing-reference.json"

        with self.assertRaises(SCORER.ScoreError) as raised:
            SCORER.score_paths(
                terminal_path=terminal_path,
                seal_path=seal_path,
                reference_path=missing_reference,
            )

        self.assertEqual(
            "benchmark_terminal_seal_checksum_mismatch",
            raised.exception.code,
        )
        self.assertFalse(raised.exception.terminal_verified)
        self.assertFalse(raised.exception.reference_accessed)

    def test_scorer_attempts_missing_reference_only_after_terminal_verification(
        self,
    ) -> None:
        terminal_path, seal_path = self._write_terminal_and_seal()

        with self.assertRaises(SCORER.ScoreError) as raised:
            SCORER.score_paths(
                terminal_path=terminal_path,
                seal_path=seal_path,
                reference_path=self.root / "missing-reference.json",
            )

        self.assertEqual("benchmark_reference_file_unavailable", raised.exception.code)
        self.assertTrue(raised.exception.terminal_verified)
        self.assertTrue(raised.exception.reference_accessed)

    def test_scorer_minimal_smoke_uses_tracked_reference_after_seal(self) -> None:
        terminal_path, seal_path = self._write_terminal_and_seal()

        result = SCORER.score_paths(
            terminal_path=terminal_path,
            seal_path=seal_path,
            reference_path=REFERENCE_PATH,
        )

        self.assertEqual("completed", result["scoring_status"])
        self.assertEqual("CURRENT_APPROACH_NOT_JUSTIFIED", result["conclusion"])
        self.assertTrue(result["terminal_verified_before_reference_access"])
        self.assertTrue(result["reference_accessed_after_terminal_verification"])
        self.assertTrue(result["terminal_unchanged_during_scoring"])
        self.assertTrue(result["provisional"])

    def test_two_step_detection_is_scored_when_crop_extraction_is_invalid(
        self,
    ) -> None:
        empty_extraction = {
            "schema_version": CONTRACTS.UNIFIED_EXTRACTION_SCHEMA_VERSION,
            "document_status": "no_tables",
            "tables": [],
            "uncertainty_codes": [],
        }
        terminal = {
            "target_manifest": {"provider_contract": {"pricing": {}}},
            "parser_accounting": {
                "unique_documents": [],
                "total_duration_ms": 0,
            },
            "cases": [
                {
                    "case_id": "case_1",
                    "page_bbox": [0.0, 0.0, 612.0, 792.0],
                    "strategies": {
                        "A": {
                            "status": "failed",
                            "extraction": None,
                            "operations": [],
                        },
                        "B": {
                            "status": "contract_invalid",
                            "detection": _detection_fixture(),
                            "extraction": empty_extraction,
                            "contract_errors": [
                                "benchmark_extraction_cell_count_mismatch"
                            ],
                            "operations": [],
                        },
                        "C": {
                            "status": "upstream_contract_invalid",
                            "extraction": copy.deepcopy(empty_extraction),
                            "replayed_from_strategy": "B",
                            "operations": [],
                            "provider_calls": 0,
                        },
                    },
                }
            ],
        }
        reference = {
            "cases": [
                {
                    "case_id": "case_1",
                    "regions": [
                        {
                            "bbox_normalized": [0.1, 0.1, 0.9, 0.9],
                            "rows": 1,
                            "columns": 1,
                            "cells": [["x"]],
                            "spans": [],
                            "header_rows": [],
                            "header_hierarchy": [],
                        }
                    ],
                }
            ]
        }
        failures: list[dict[str, Any]] = []

        result = SCORER._score_strategies(
            terminal=terminal,
            reference=reference,
            iou_threshold=0.5,
            failed_contracts=failures,
            strategy_contract_errors={},
        )

        self.assertEqual(0, result["A"]["detection"]["found_existing_tables"])
        self.assertEqual(1, result["B"]["detection"]["found_existing_tables"])
        self.assertEqual(1, result["C"]["detection"]["found_existing_tables"])
        self.assertEqual(1, result["B"]["safety"]["malformed_outputs"])
        self.assertEqual(
            "benchmark_extraction_cell_count_mismatch",
            failures[0]["reason_code"],
        )

    def test_runner_source_enforces_factory_route_and_has_no_retry_transport(
        self,
    ) -> None:
        source = RUNNER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        factories = {
            "PdfGridExperimentProviderFactory",
            "PdfTableRasterFactory",
            "PdfTextLayerParserFactory",
        }
        self.assertTrue(factories <= imports)
        instantiated = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(factories <= instantiated)
        self.assertIn(".create_for_openwebui(", source)
        self.assertIn(".create()", source)
        self.assertNotIn("generativelanguage.googleapis.com", source)
        self.assertNotIn(":generateContent", source)
        self.assertNotIn(":countTokens", source)
        self.assertFalse(any(isinstance(node, ast.While) for node in ast.walk(tree)))
        retry_loops = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.For)
            and "retry" in ast.unparse(node.target).casefold()
        ]
        self.assertEqual([], retry_loops)
        provider_calls = {
            node.func.attr: _enclosing_function_name(tree, node)
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"count_tokens", "invoke"}
        }
        self.assertEqual(
            {"count_tokens": "_provider_operation", "invoke": "_provider_operation"},
            provider_calls,
        )

    def _write_terminal_and_seal(self) -> tuple[Path, Path]:
        terminal = _minimal_terminal(self.manifest)
        terminal_bytes = _canonical_json_bytes(terminal)
        terminal_path = self.root / "terminal.private.json"
        seal_path = self.root / "terminal.private.sha256.json"
        terminal_path.write_bytes(terminal_bytes)
        seal_path.write_bytes(
            _canonical_json_bytes(
                {
                    "schema_version": SCORER.SEAL_SCHEMA,
                    "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
                    "terminal_size_bytes": len(terminal_bytes),
                }
            )
        )
        return terminal_path, seal_path


class _RecordingProvider:
    """External provider boundary; benchmark orchestration remains real."""

    def __init__(self) -> None:
        self.count_calls = 0
        self.invoke_calls = 0
        self.invoke_arguments: dict[str, Any] = {}

    def count_tokens(self, **_: Any) -> dict[str, Any]:
        self.count_calls += 1
        return {"total_tokens": 12}

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.invoke_calls += 1
        self.invoke_arguments = dict(kwargs)
        return {
            "attempt": {
                "attempt_number": kwargs["attempt_number"],
                "attempt_lineage": list(kwargs["attempt_lineage"]),
                "hidden_retry": False,
                "provider_failover": False,
            },
            "raw_private_response": {"ok": True},
            "json_output": {"ok": True},
            "response_bytes": 2,
            "response_hash": hashlib.sha256(b"{}").hexdigest(),
            "visible_output_bytes": 2,
            "visible_output_hash": hashlib.sha256(b"{}").hexdigest(),
        }


class _SequencedProvider(_RecordingProvider):
    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        result = super().invoke(**kwargs)
        result["json_output"] = (
            _detection_fixture()
            if str(kwargs["task_id"]).endswith("_detect")
            else _resolved_extraction(bottom_right="$ 1", currency=True)
        )
        return result


class _RasterBoundary:
    """External raster boundary; crop orchestration remains real."""

    @staticmethod
    def render_full_page(**_: Any) -> dict[str, Any]:
        return {
            "private_png_base64": base64.b64encode(b"page-image").decode("ascii"),
            "manifest": {"scope": "page"},
        }

    @staticmethod
    def render(**_: Any) -> dict[str, Any]:
        return {
            "private_png_base64": base64.b64encode(b"crop-image").decode("ascii"),
            "manifest": {"scope": "crop"},
        }


def _detection_fixture() -> dict[str, Any]:
    return {
        "schema_version": CONTRACTS.DETECTION_SCHEMA_VERSION,
        "presence": "present",
        "regions": [
            {
                "region_id": "region_1",
                "bbox": [0.1, 0.1, 0.9, 0.9],
                "coordinate_space": CONTRACTS.INPUT_IMAGE_NORMALIZED,
                "confidence": 0.9,
                "possible_table_type": "simple_ruled",
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _resolved_extraction(
    *,
    bottom_right: str = "",
    currency: bool = False,
) -> dict[str, Any]:
    cells = [
        _cell("cell_r1_c1", "row_1", "column_1", [0.0, 0.0, 0.5, 0.5], "Description"),
        _cell("cell_r1_c2", "row_1", "column_2", [0.5, 0.0, 1.0, 0.5], "Amount"),
        _cell("cell_r2_c1", "row_2", "column_1", [0.0, 0.5, 0.5, 1.0], "Cash"),
        _cell("cell_r2_c2", "row_2", "column_2", [0.5, 0.5, 1.0, 1.0], bottom_right),
    ]
    amount_qualifiers = ["currency_qualifier"] if currency else []
    qualifiers = (
        [
            {
                "qualifier_id": "currency_qualifier",
                "kind": "currency",
                "target_field_id": "amount_field",
                "physical_column_ids": ["column_2"],
                "evidence_cell_ids": ["cell_r2_c2"],
                "normalized_code": None,
                "uncertainty_codes": [],
            }
        ]
        if currency
        else []
    )
    return {
        "schema_version": CONTRACTS.UNIFIED_EXTRACTION_SCHEMA_VERSION,
        "document_status": "completed",
        "tables": [
            {
                "table_id": "table_1",
                "bbox": [0.0, 0.0, 1.0, 1.0],
                "coordinate_space": CONTRACTS.INPUT_IMAGE_NORMALIZED,
                "decision": "resolved",
                "physical": {
                    "row_count": 2,
                    "column_count": 2,
                    "rows": [
                        {"row_id": "row_1", "ordinal": 1, "bbox": [0.0, 0.0, 1.0, 0.5]},
                        {"row_id": "row_2", "ordinal": 2, "bbox": [0.0, 0.5, 1.0, 1.0]},
                    ],
                    "columns": [
                        {"column_id": "column_1", "ordinal": 1, "bbox": [0.0, 0.0, 0.5, 1.0]},
                        {"column_id": "column_2", "ordinal": 2, "bbox": [0.5, 0.0, 1.0, 1.0]},
                    ],
                    "cells": cells,
                    "merged_regions": [],
                },
                "semantic": {
                    "fields": [
                        {
                            "field_id": "description_field",
                            "role": "description",
                            "logical_type": "text",
                            "physical_column_ids": ["column_1"],
                            "header_cell_ids": ["cell_r1_c1"],
                            "qualifier_ids": [],
                            "uncertainty_codes": [],
                        },
                        {
                            "field_id": "amount_field",
                            "role": "amount",
                            "logical_type": "monetary_amount",
                            "physical_column_ids": ["column_2"],
                            "header_cell_ids": ["cell_r1_c2"],
                            "qualifier_ids": amount_qualifiers,
                            "uncertainty_codes": [],
                        },
                    ],
                    "qualifiers": qualifiers,
                },
                "alternatives": [],
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _single_cell_extraction(text: str) -> dict[str, Any]:
    return {
        "schema_version": CONTRACTS.UNIFIED_EXTRACTION_SCHEMA_VERSION,
        "document_status": "completed",
        "tables": [
            {
                "table_id": "table_1",
                "bbox": [0.0, 0.0, 1.0, 1.0],
                "coordinate_space": CONTRACTS.PAGE_NORMALIZED,
                "decision": "resolved",
                "physical": {
                    "row_count": 1,
                    "column_count": 1,
                    "rows": [
                        {"row_id": "row_1", "ordinal": 1, "bbox": [0.0, 0.0, 1.0, 1.0]}
                    ],
                    "columns": [
                        {"column_id": "column_1", "ordinal": 1, "bbox": [0.0, 0.0, 1.0, 1.0]}
                    ],
                    "cells": [
                        _cell(
                            "cell_1",
                            "row_1",
                            "column_1",
                            [0.0, 0.0, 1.0, 1.0],
                            text,
                        )
                    ],
                    "merged_regions": [],
                },
                "semantic": {
                    "fields": [
                        {
                            "field_id": "field_1",
                            "role": "description",
                            "logical_type": "text",
                            "physical_column_ids": ["column_1"],
                            "header_cell_ids": [],
                            "qualifier_ids": [],
                            "uncertainty_codes": [],
                        }
                    ],
                    "qualifiers": [],
                },
                "alternatives": [],
                "uncertainty_codes": [],
            }
        ],
        "uncertainty_codes": [],
    }


def _cell(
    cell_id: str,
    row_id: str,
    column_id: str,
    bbox: list[float],
    text: str,
) -> dict[str, Any]:
    return {
        "cell_id": cell_id,
        "row_id": row_id,
        "column_id": column_id,
        "bbox": bbox,
        "text": text,
        "explicit_empty": text == "",
        "uncertainty_codes": [],
    }


def _minimal_terminal(manifest: dict[str, Any]) -> dict[str, Any]:
    empty_a = {"status": "failed", "extraction": None, "operations": []}
    empty_b = {
        "status": "failed",
        "detection": None,
        "extraction": None,
        "operations": [],
    }
    empty_c = {
        "status": "failed",
        "extraction": None,
        "operations": [],
        "evidence_validation": None,
        "replayed_from_strategy": "B",
        "provider_calls": 0,
    }
    return {
        "schema_version": SCORER.TERMINAL_SCHEMA,
        "reference_accessed": False,
        "production_authority": False,
        "production_pipeline_changed": False,
        "production_gate2_selection_changed": False,
        "ocr_performed": False,
        "hidden_retry": False,
        "provider_failover": False,
        "manifest_sha256": CONTRACTS.sha256_json(manifest),
        "target_manifest": copy.deepcopy(manifest),
        "prompt_contracts": RUNNER._prompt_contracts(manifest),
        "provider_qualification": {"status": "qualified"},
        "cases": [
            {
                "case_id": case["case_id"],
                "page_bbox": case["page_bbox_points"],
                "strategies": {
                    "A": copy.deepcopy(empty_a),
                    "B": copy.deepcopy(empty_b),
                    "C": copy.deepcopy(empty_c),
                },
            }
            for case in manifest["cases"]
        ],
    }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _enclosing_function_name(tree: ast.AST, target: ast.AST) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and target in set(
            ast.walk(node)
        ):
            return node.name
    return None


if __name__ == "__main__":
    unittest.main()
