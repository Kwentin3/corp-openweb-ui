from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
MANIFEST_PATH = ROOT / "benchmarks" / "pdf_dual_vlm_fact_v1" / "manifest.json"
RUNNER_PATH = SCRIPT_DIR / "local_pdf_dual_vlm_fact_benchmark.py"
SCORER_PATH = SCRIPT_DIR / "local_pdf_dual_vlm_fact_benchmark_score.py"

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPT_DIR))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


CONTRACTS = importlib.import_module("pdf_dual_vlm_fact_contracts")
RUNNER = _load_module("local_pdf_dual_vlm_fact_benchmark_test", RUNNER_PATH)
SCORER = _load_module("local_pdf_dual_vlm_fact_benchmark_score_test", SCORER_PATH)


def test_frozen_manifest_and_provider_views_preserve_closed_boundaries() -> None:
    manifest = _manifest()

    RUNNER._validate_manifest(manifest)

    assert manifest["schema_version"] == CONTRACTS.MANIFEST_SCHEMA_VERSION
    assert len(manifest["cases"]) == manifest["case_count"] == 8
    providers = manifest["provider_contracts"]
    extraction_providers = {
        providers["gemini_extraction"]["provider"],
        providers["openai_extraction"]["provider"],
    }
    assert extraction_providers == {"google", "openai"}
    assert (
        providers["gemini_extraction"]["model_id"]
        != providers["openai_extraction"]["model_id"]
    )
    assert manifest["execution_policy"] == {
        "count_or_preflight_calls_per_provider_operation": 1,
        "generate_calls_per_provider_operation": 1,
        "hidden_retry": False,
        "provider_failover": False,
        "third_llm_arbiter": False,
        "same_crop_bytes_for_extractors": True,
        "whole_document_prompt": False,
        "reference_available_to_runner": False,
    }
    assert manifest["reference_boundary"]["required_human_reviewed"] is True
    assert (
        manifest["reference_boundary"]["runner_may_accept_reference_argument"] is False
    )
    assert (
        manifest["reference_boundary"]["provider_may_receive_reference_data"] is False
    )

    detection_view = CONTRACTS.detection_model_view(
        document_id="case_1",
        page_number=2,
        page_image_sha256="1" * 64,
    )
    fact_view = CONTRACTS.fact_model_view(
        document_id="case_1",
        page_number=2,
        crop_id="crop_1",
        crop_sha256="2" * 64,
    )
    assert detection_view["rules"]["extract_cells_or_facts"] is False
    assert fact_view["rules"]["observed_interpreted_evidence_separated"] is True
    assert fact_view["rules"]["unknown_preferred_to_inference"] is True
    assert fact_view["rules"]["reference_or_other_provider_available"] is False
    assert RUNNER._find_forbidden_reference_key(detection_view) is None
    assert RUNNER._find_forbidden_reference_key(fact_view) is None
    leaked_view = copy.deepcopy(fact_view)
    leaked_view["answer_key"] = {"visible_value": "$1,000"}
    assert RUNNER._find_forbidden_reference_key(leaked_view) == "answer_key"

    schema = CONTRACTS.financial_fact_schema()
    fact_properties = schema["properties"]["facts"]["items"]["properties"]
    assert schema["additionalProperties"] is False
    assert set(fact_properties) == {
        "fact_id",
        "fact_type",
        "observed",
        "interpreted",
        "evidence_request",
        "uncertainty",
    }
    assert fact_properties["observed"]["additionalProperties"] is False
    assert fact_properties["interpreted"]["additionalProperties"] is False
    assert fact_properties["evidence_request"]["additionalProperties"] is False


def test_crop_contract_checksum_detects_immutable_crop_tamper() -> None:
    png = b"\x89PNG\r\n\x1a\nfixed-crop"
    raster_manifest = {
        "crop_id": "crop_1",
        "pdf_sha256": "a" * 64,
        "page_number": 4,
        "declared_table_bbox": [10.0, 20.0, 110.0, 120.0],
        "rendered_bbox": [10.0, 20.0, 110.0, 120.0],
        "source_to_pixel_transform": {
            "x_scale": 2.0,
            "y_scale": 2.0,
            "x_offset": -20.0,
            "y_offset": -40.0,
        },
        "dpi": 150,
        "width": 208,
        "height": 208,
        "png_bytes": len(png),
        "png_sha256": hashlib.sha256(png).hexdigest(),
        "renderer": "fixture_renderer",
        "renderer_version": "1",
        "padding_points": 0,
        "lossless": True,
        "silent_resize_performed": False,
        "manifest_hash": "b" * 64,
    }
    contract = CONTRACTS.build_crop_contract(
        document_id="case_1",
        page_image_sha256="c" * 64,
        normalized_bbox=[0.1, 0.2, 0.8, 0.9],
        raster_manifest=raster_manifest,
    )

    assert CONTRACTS.validate_crop_contract(contract) == []
    assert contract["rendered_image_sha256"] == hashlib.sha256(png).hexdigest()
    assert contract["padding_points"] == 0
    assert contract["silent_resize_performed"] is False

    tampered = copy.deepcopy(contract)
    tampered["rendered_image_bytes"] += 1
    assert "dual_vlm_crop_contract_checksum_invalid" in (
        CONTRACTS.validate_crop_contract(tampered)
    )

    moved = copy.deepcopy(contract)
    moved["normalized_bbox"][0] = 0.11
    assert "dual_vlm_crop_contract_checksum_invalid" in (
        CONTRACTS.validate_crop_contract(moved)
    )


@pytest.mark.parametrize(
    ("openai_changes", "expected_status"),
    [
        ({}, "models_exactly_agree"),
        (
            {"physical_value_bbox": [0.62, 0.4, 0.9, 0.6]},
            "models_semantically_agree_physical_layout_differs",
        ),
        ({"period": "2023"}, "models_partially_agree"),
        ({"sign": "negative", "numeric_value": "-1000"}, "model_conflict"),
        ({"missing": True}, "one_model_missing_fact"),
    ],
)
def test_consensus_has_terminal_non_voting_dispositions(
    openai_changes: dict[str, Any], expected_status: str
) -> None:
    gemini = _fact_output(fact_id="gemini_fact")
    openai = _fact_output(fact_id="openai_fact", **openai_changes)
    assert CONTRACTS.validate_fact_extraction_output(gemini) == []
    assert CONTRACTS.validate_fact_extraction_output(openai) == []

    consensus = CONTRACTS.compare_provider_facts(gemini, openai)

    assert CONTRACTS.validate_consensus(consensus) == []
    assert [entry["status"] for entry in consensus["entries"]] == [expected_status]
    entry = consensus["entries"][0]
    agreement = expected_status in CONTRACTS.AGREEMENT_STATUSES
    assert entry["runtime_disposition"] == (
        "evidence_eligible" if agreement else "human_review_required"
    )
    assert (entry["canonical_fact"] is not None) is agreement
    assert consensus["human_reference_used"] is False
    assert consensus["voting_used"] is False
    assert consensus["confidence_averaging_used"] is False
    assert consensus["third_llm_arbiter_used"] is False


def test_consensus_authority_and_checksum_tamper_fail_closed() -> None:
    consensus = CONTRACTS.compare_provider_facts(
        _fact_output(fact_id="gemini_fact"),
        _fact_output(fact_id="openai_fact"),
    )

    authority_tamper = copy.deepcopy(consensus)
    authority_tamper["human_reference_used"] = True
    unsigned = copy.deepcopy(authority_tamper)
    unsigned.pop("consensus_checksum")
    authority_tamper["consensus_checksum"] = CONTRACTS.sha256_json(unsigned)
    assert "dual_vlm_consensus_authority_boundary_invalid" in (
        CONTRACTS.validate_consensus(authority_tamper)
    )

    content_tamper = copy.deepcopy(consensus)
    content_tamper["entries"][0]["runtime_disposition"] = "human_review_required"
    assert "dual_vlm_consensus_checksum_invalid" in (
        CONTRACTS.validate_consensus(content_tamper)
    )


def test_matching_uncertain_provider_facts_require_human_review() -> None:
    gemini = _fact_output(fact_id="gemini_fact")
    openai = _fact_output(fact_id="openai_fact")
    for output in (gemini, openai):
        output["status"] = "uncertain"
        output["uncertainty_codes"] = ["ambiguous_period"]
        output["facts"][0]["uncertainty"] = {
            "status": "uncertain",
            "reason_codes": ["ambiguous_period"],
            "alternative_interpretations": [],
        }
        assert CONTRACTS.validate_fact_extraction_output(output) == []

    consensus = CONTRACTS.compare_provider_facts(gemini, openai)

    assert consensus["entries"][0]["status"] == "human_review_required"
    assert consensus["entries"][0]["runtime_disposition"] == "human_review_required"
    assert consensus["entries"][0]["canonical_fact"] is None
    assert "provider_fact_uncertain" in consensus["entries"][0]["material_differences"]


def test_runner_cli_provider_operation_and_factory_route_are_reference_free(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as raised:
        RUNNER.main(["--help"])
    assert raised.value.code == 0
    help_text = capsys.readouterr().out
    assert "--output-dir" in help_text
    assert "--reference" not in help_text

    artifact_dir = tmp_path / "run" / "artifacts" / "case_1"
    artifact_dir.mkdir(parents=True)
    provider = _RecordingProvider()
    png = b"\x89PNG\r\n\x1a\nimmutable-provider-input"
    operation = RUNNER._provider_operation(
        provider=provider,
        task_id="case_1_crop_1",
        kind="test_financial_fact_extraction",
        model_view={
            "task": "financial_fact",
            "crop_sha256": hashlib.sha256(png).hexdigest(),
        },
        output_schema={"type": "object", "additionalProperties": False},
        png_bytes=png,
        artifact_dir=artifact_dir,
        artifact_stem="provider",
    )

    assert [name for name, _kwargs in provider.calls] == ["count_tokens", "invoke"]
    count_kwargs = provider.calls[0][1]
    invoke_kwargs = provider.calls[1][1]
    assert count_kwargs["png_bytes"] == invoke_kwargs["png_bytes"] == png
    assert count_kwargs["crop_sha256"] == invoke_kwargs["crop_sha256"]
    assert invoke_kwargs["attempt_number"] == 1
    assert invoke_kwargs["attempt_lineage"] == []
    assert operation["attempt"]["hidden_retry"] is False
    assert operation["attempt"]["provider_failover"] is False

    with pytest.raises(RUNNER.BenchmarkError) as reference_leak:
        RUNNER._provider_operation(
            provider=_RecordingProvider(),
            task_id="leaked",
            kind="test",
            model_view={"expected_value": "1"},
            output_schema={"type": "object"},
            png_bytes=png,
            artifact_dir=artifact_dir,
            artifact_stem="leaked",
        )
    assert reference_leak.value.code == "dual_vlm_model_view_reference_leak"

    source = RUNNER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    called_names = {
        _qualified_name(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    assert {
        "PdfDualVlmFactProviderFactory",
        "PdfTableRasterFactory",
        "PdfTextLayerParserFactory",
        "PdfDualVlmFactEvidenceFactory",
    }.issubset(called_names)
    assert "OpenAIResponsesVisionAdapter" not in source
    assert "PdfGridExperimentProviderFactory" not in source

    operation_node = _function_node(tree, "_provider_operation")
    operation_calls = [
        _qualified_name(node.func)
        for node in ast.walk(operation_node)
        if isinstance(node, ast.Call)
    ]
    assert operation_calls.count("provider.count_tokens") == 1
    assert operation_calls.count("provider.invoke") == 1
    assert not any(
        isinstance(node, (ast.For, ast.While)) for node in ast.walk(operation_node)
    )


def test_scorer_seal_precedes_reference_and_missing_human_review_is_typed(
    tmp_path: Path,
) -> None:
    terminal_path, seal_path = _write_reference_free_terminal(tmp_path)
    reference_path = tmp_path / "missing-human-reference.json"
    reference_seal_path = tmp_path / "missing-human-reference.seal.json"

    with pytest.raises(SCORER.ScoreError) as invalid_terminal:
        SCORER.score_run(
            terminal_path=terminal_path,
            seal_path=seal_path,
            reference_path=reference_path,
            reference_seal_path=reference_seal_path,
        )
    assert invalid_terminal.value.code == "dual_vlm_terminal_authority_boundary_invalid"

    output_path = tmp_path / "blocked-score.json"
    exit_code = SCORER.main(
        [
            "--terminal",
            str(terminal_path),
            "--seal",
            str(seal_path),
            "--reference",
            str(reference_path),
            "--reference-seal",
            str(reference_seal_path),
            "--output",
            str(output_path),
        ]
    )
    persisted = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert persisted["scoring_status"] == "failed"
    assert persisted["failure_code"] == "dual_vlm_terminal_authority_boundary_invalid"

    reference_path.write_bytes(
        CONTRACTS.canonical_json_bytes(
            {
                "schema_version": SCORER.FINAL_REFERENCE_SCHEMA,
                "human_reviewed": False,
            }
        )
    )
    reference_seal_path.write_text("{}", encoding="utf-8")
    with pytest.raises(SCORER.ScoreError) as non_human:
        SCORER.score_run(
            terminal_path=terminal_path,
            seal_path=seal_path,
            reference_path=reference_path,
            reference_seal_path=reference_seal_path,
        )
    # Once a reference exists, the scorer must finish the full terminal-contract
    # audit before opening or classifying that reference.
    assert non_human.value.code == "dual_vlm_terminal_authority_boundary_invalid"


def test_scorer_rejects_terminal_tamper_before_opening_reference(
    tmp_path: Path,
) -> None:
    terminal_path, seal_path = _write_reference_free_terminal(tmp_path)
    terminal_path.write_bytes(terminal_path.read_bytes() + b" ")
    reference_path = tmp_path / "reference.json"
    reference_path.write_text("not valid json", encoding="utf-8")
    reference_seal_path = tmp_path / "reference.seal.json"
    reference_seal_path.write_text("not valid json", encoding="utf-8")

    with pytest.raises(SCORER.ScoreError) as raised:
        SCORER.score_run(
            terminal_path=terminal_path,
            seal_path=seal_path,
            reference_path=reference_path,
            reference_seal_path=reference_seal_path,
        )

    assert raised.value.code == "dual_vlm_terminal_seal_mismatch"
    scorer_tree = ast.parse(SCORER_PATH.read_text(encoding="utf-8"))
    score_node = _function_node(scorer_tree, "score_run")
    terminal_read_lines = [
        node.lineno
        for node in ast.walk(score_node)
        if isinstance(node, ast.Call)
        and _qualified_name(node.func) == "terminal_path.read_bytes"
    ]
    reference_read_lines = [
        node.lineno
        for node in ast.walk(score_node)
        if isinstance(node, ast.Call)
        and _qualified_name(node.func) == "reference_path.read_bytes"
    ]
    assert min(terminal_read_lines) < min(reference_read_lines)


class _RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def count_tokens(self, **kwargs: Any) -> dict[str, int]:
        self.calls.append(("count_tokens", kwargs))
        return {"total_tokens": 10}

    def invoke(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("invoke", kwargs))
        return {
            "attempt": {
                "crop_sha256": kwargs["crop_sha256"],
                "hidden_retry": False,
                "provider_failover": False,
                "terminal_failure_class": None,
            },
            "raw_private_response": {"fixture": True},
            "json_output": {"schema_version": "fixture"},
            "response_bytes": 2,
            "response_hash": "d" * 64,
            "visible_output_bytes": 2,
            "visible_output_hash": "e" * 64,
        }


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _fact_output(
    *,
    fact_id: str,
    period: str = "2024",
    sign: str = "positive",
    numeric_value: str = "1000",
    physical_value_bbox: list[float] | None = None,
    missing: bool = False,
) -> dict[str, Any]:
    identity = {
        "document_id": "case_1",
        "page_number": 4,
        "crop_id": "crop_1",
        "crop_sha256": "f" * 64,
    }
    context = {
        "table_title_exact": "Statement of Financial Condition",
        "period_context_exact": period,
        "currency_context_exact": "$",
        "unit_scale_context_exact": "USD",
        "entity_context_exact": "Broker LLC",
        "uncertainty_codes": [],
    }
    if missing:
        return {
            "schema_version": CONTRACTS.FACT_SCHEMA_VERSION,
            **identity,
            "status": "no_financial_facts",
            "table_context": context,
            "physical_cells": [],
            "facts": [],
            "uncertainty_codes": [],
        }
    row_bbox = [0.05, 0.4, 0.5, 0.6]
    header_bbox = [0.6, 0.1, 0.9, 0.25]
    value_bbox = [0.6, 0.4, 0.9, 0.6]
    physical_value_bbox = physical_value_bbox or value_bbox
    physical_cells = [
        {
            "cell_id": "row_cell",
            "text_exact": "Cash",
            "bbox": row_bbox,
            "role": "row_label",
            "row_hint": "Cash",
            "column_hint": None,
        },
        {
            "cell_id": "header_cell",
            "text_exact": period,
            "bbox": header_bbox,
            "role": "header",
            "row_hint": None,
            "column_hint": period,
        },
        {
            "cell_id": "value_cell",
            "text_exact": "$1,000",
            "bbox": physical_value_bbox,
            "role": "value",
            "row_hint": "Cash",
            "column_hint": period,
        },
    ]
    observed = {
        "row_label_exact": "Cash",
        "header_path_exact": [period],
        "value_exact": "$1,000",
        "source_cell_ids": ["row_cell", "header_cell", "value_cell"],
        "source_regions": {
            "row_label_bbox": row_bbox,
            "value_bbox": value_bbox,
            "header_bboxes": [header_bbox],
            "qualifier_bboxes": {
                "period": header_bbox,
                "currency": value_bbox,
                "unit": header_bbox,
                "scale": header_bbox,
                "entity": header_bbox,
            },
        },
    }
    fact = {
        "fact_id": fact_id,
        "fact_type": "financial_statement_line_item",
        "observed": observed,
        "interpreted": {
            "normalized_row_identity": "cash",
            "numeric_value": numeric_value,
            "sign": sign,
            "period": period,
            "currency_literal": "$",
            "currency_code": "USD",
            "unit": "USD",
            "scale": None,
            "entity": "Broker LLC",
            "qualifiers": [],
        },
        "evidence_request": {
            "requested_text": {
                "row_label_exact": "Cash",
                "header_path_exact": [period],
                "value_exact": "$1,000",
                "period_exact": period,
                "currency_exact": "$",
                "unit_exact": "USD",
                "scale_exact": None,
                "entity_exact": "Broker LLC",
            },
            "qualifier_scopes": {
                "period": "header",
                "currency": "value",
                "unit": "table",
                "scale": "table",
                "entity": "table",
            },
            "required_relations": [
                "row_value_spatial",
                "header_value_spatial",
                "period_scope",
                "currency_scope",
                "unit_scale_scope",
                "entity_scope",
            ],
        },
        "uncertainty": {
            "status": "certain",
            "reason_codes": [],
            "alternative_interpretations": [],
        },
    }
    return {
        "schema_version": CONTRACTS.FACT_SCHEMA_VERSION,
        **identity,
        "status": "completed",
        "table_context": context,
        "physical_cells": physical_cells,
        "facts": [fact],
        "uncertainty_codes": [],
    }


def _write_reference_free_terminal(tmp_path: Path) -> tuple[Path, Path]:
    manifest = _manifest()
    terminal = {
        "schema_version": SCORER.TERMINAL_SCHEMA_VERSION,
        "runner": {"reference_argument_supported": False},
        "reference_accessed": False,
        "human_reference_available_to_runner": False,
        "manifest_sha256": CONTRACTS.sha256_json(manifest),
        "target_manifest": manifest,
        "cases": [],
        # Deliberately not represented as a successful run fixture.
        "run_status": "failed_before_case_completion",
    }
    terminal_bytes = CONTRACTS.canonical_json_bytes(terminal)
    terminal_path = tmp_path / "terminal.private.json"
    terminal_path.write_bytes(terminal_bytes)
    seal = {
        "schema_version": SCORER.SEAL_SCHEMA_VERSION,
        "terminal_sha256": hashlib.sha256(terminal_bytes).hexdigest(),
        "terminal_size_bytes": len(terminal_bytes),
        "reference_accessed": False,
    }
    seal_path = tmp_path / "terminal.private.sha256.json"
    seal_path.write_bytes(CONTRACTS.canonical_json_bytes(seal))
    return terminal_path, seal_path


def _qualified_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _qualified_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _function_node(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    assert len(matches) == 1
    return matches[0]
