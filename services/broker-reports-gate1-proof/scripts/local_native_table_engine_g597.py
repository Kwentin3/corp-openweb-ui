#!/usr/bin/env python3
"""Research-only G5.97 adapter proof for a native PDF table engine.

The VLM contract stays engine-neutral.  Deterministic code resolves one source
region and visual column axis, pdfplumber constructs the row/cell geometry, and
only maintained-parser words that bind back to frozen source refs may populate
the private result.  Engine-returned strings are never source authority.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.metadata
import itertools
import json
import re
import statistics
import time
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pdfplumber
import pypdf
import requests

from broker_reports_gate1.pdf_grid_experiment_provider import (
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from broker_reports_gate1.pdf_text_layer import (
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)


SCRIPT_PATH = Path(__file__).resolve()
SERVICE_ROOT = SCRIPT_PATH.parent.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "table_layout_native_engine_g597" / "manifest.json"
)
DEFAULT_G596_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "table_layout_contract_g596" / "manifest.json"
)
MANIFEST_SCHEMA = "broker_reports_table_layout_native_engine_g597_manifest_v1"
PRIVATE_DEVELOPMENT_SCHEMA = "broker_reports_native_table_engine_g597_development_private_v1"
SAFE_DEVELOPMENT_SCHEMA = "broker_reports_native_table_engine_g597_development_safe_v1"
PRIVATE_HOLDOUT_CONTRACT_SCHEMA = (
    "broker_reports_native_table_engine_g597_holdout_contract_private_v1"
)
SAFE_HOLDOUT_CONTRACT_SCHEMA = (
    "broker_reports_native_table_engine_g597_holdout_contract_safe_v1"
)
PRIVATE_HOLDOUT_SCHEMA = "broker_reports_native_table_engine_g597_holdout_private_v1"
SAFE_HOLDOUT_SCHEMA = "broker_reports_native_table_engine_g597_holdout_safe_v1"

DEVELOPMENT_PROVEN = "NATIVE_ENGINE_DEVELOPMENT_CONTROLS_PROVEN"
DEVELOPMENT_FAILED = "NATIVE_ENGINE_DEVELOPMENT_CONTROLS_FAILED"
HOLDOUT_EXECUTED = "FROZEN_UNSEEN_HOLDOUT_EXECUTED"
HOLDOUT_FAILED = "FROZEN_UNSEEN_HOLDOUT_FAILED"

_NORMALIZE_RE = re.compile(r"[^\w]+", re.UNICODE)
_DIGIT_RE = re.compile(r"\d")
_FORBIDDEN_CONTRACT_KEYS = frozenset(
    {
        "body_values",
        "body_rows",
        "cell_values",
        "rows",
        "cells",
        "canonical_id",
        "canonical_ids",
        "bbox",
        "bboxes",
        "amount",
        "quantity",
        "security",
        "date",
        "financial_semantics",
        "vertical_strategy",
        "horizontal_strategy",
        "explicit_vertical_lines",
        "explicit_horizontal_lines",
        "snap_tolerance",
        "join_tolerance",
        "intersection_tolerance",
    }
)


class G597Error(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PdfplumberTableExtractorAdapter:
    """The only G5.97 component allowed to know the pdfplumber table API."""

    def __init__(self, pdf_bytes: bytes, *, expected_version: str) -> None:
        if importlib.metadata.version("pdfplumber") != expected_version:
            raise G597Error("g597_native_engine_version_mismatch")
        self._pdf = pdfplumber.open(
            BytesIO(pdf_bytes),
            laparams={
                "line_overlap": 0.5,
                "char_margin": 2.0,
                "line_margin": 0.5,
                "word_margin": 0.1,
                "boxes_flow": None,
                "detect_vertical": True,
                "all_texts": True,
            },
            unicode_norm="NFC",
            strict_metadata=False,
        )

    def close(self) -> None:
        self._pdf.close()

    def extract_geometry(
        self,
        *,
        page_number: int,
        source_region: list[float],
        visual_column_boundaries: list[float],
        expected_columns: int,
    ) -> dict[str, Any]:
        """Translate engine-neutral region/axis facts into one native grid."""
        if len(visual_column_boundaries) != expected_columns + 1:
            raise G597Error("g597_visual_axis_incompatible")
        page = self._pdf.pages[page_number - 1]
        cropped = page.crop(tuple(source_region))
        native_configuration = {
            "vertical_strategy": "explicit",
            "explicit_vertical_lines": list(visual_column_boundaries),
            "horizontal_strategy": "lines",
        }
        tables = cropped.find_tables(table_settings=native_configuration)
        if len(tables) != 1:
            raise G597Error(
                "g597_native_table_not_found"
                if not tables
                else "g597_native_table_ambiguous"
            )
        table = tables[0]
        rows = []
        for row in list(table.rows or []):
            cells = [list(cell) if cell is not None else None for cell in row.cells]
            if len(cells) != expected_columns or any(cell is None for cell in cells):
                raise G597Error("g597_native_grid_incompatible")
            rows.append(cells)
        if not rows or len(table.columns or []) != expected_columns:
            raise G597Error("g597_native_grid_incompatible")
        return {
            "engine": "pdfplumber",
            "engine_version": importlib.metadata.version("pdfplumber"),
            "configuration": native_configuration,
            "table_bbox": list(table.bbox),
            "rows": rows,
            "row_count": len(rows),
            "column_count": expected_columns,
            "engine_strings_used": 0,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    development = commands.add_parser("development")
    _add_common_input_arguments(development)
    development.add_argument("--g596-contract-private", required=True)
    development.add_argument("--g596-materialization-private", required=True)
    development.add_argument("--private-output", required=True)
    development.add_argument("--safe-output", required=True)

    generate = commands.add_parser("generate-holdout-contract")
    generate.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    generate.add_argument("--g596-manifest", default=str(DEFAULT_G596_MANIFEST))
    generate.add_argument("--frozen-development-private", required=True)
    generate.add_argument("--frozen-development-safe", required=True)
    generate.add_argument("--g594-private-dir", required=True)
    generate.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    generate.add_argument("--private-output", required=True)
    generate.add_argument("--safe-output", required=True)

    holdout = commands.add_parser("holdout")
    _add_common_input_arguments(holdout)
    holdout.add_argument("--frozen-development-private", required=True)
    holdout.add_argument("--frozen-development-safe", required=True)
    holdout.add_argument("--holdout-contract-private", required=True)
    holdout.add_argument("--private-output", required=True)
    holdout.add_argument("--safe-output", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "development":
            result = run_development(
                manifest_path=Path(args.manifest),
                g596_manifest_path=Path(args.g596_manifest),
                g596_contract_path=Path(args.g596_contract_private),
                g596_materialization_path=Path(args.g596_materialization_private),
                g594_private_dir=Path(args.g594_private_dir),
                source_pdf=Path(args.source_pdf),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
        elif args.command == "generate-holdout-contract":
            result = generate_holdout_contract(
                manifest_path=Path(args.manifest),
                g596_manifest_path=Path(args.g596_manifest),
                development_private=Path(args.frozen_development_private),
                development_safe=Path(args.frozen_development_safe),
                g594_private_dir=Path(args.g594_private_dir),
                env_path=Path(args.env_file),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
        else:
            result = run_holdout(
                manifest_path=Path(args.manifest),
                g596_manifest_path=Path(args.g596_manifest),
                development_private=Path(args.frozen_development_private),
                development_safe=Path(args.frozen_development_safe),
                holdout_contract=Path(args.holdout_contract_private),
                g594_private_dir=Path(args.g594_private_dir),
                source_pdf=Path(args.source_pdf),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
    except Exception as exc:
        code = exc.code if isinstance(exc, G597Error) else type(exc).__name__
        print(json.dumps({"status": "failed", "code": code}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _add_common_input_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--g596-manifest", default=str(DEFAULT_G596_MANIFEST))
    parser.add_argument("--g594-private-dir", required=True)
    parser.add_argument("--source-pdf", required=True)


def run_development(
    *,
    manifest_path: Path,
    g596_manifest_path: Path,
    g596_contract_path: Path,
    g596_materialization_path: Path,
    g594_private_dir: Path,
    source_pdf: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    manifest, g596_manifest = _load_frozen_inputs(
        manifest_path,
        g596_manifest_path,
        g596_contract_path,
        g596_materialization_path,
    )
    _require_fresh_outputs(private_output, safe_output)
    pdf_bytes = _verified_source_bytes(source_pdf, manifest)
    contract_receipt = _read_object(g596_contract_path)
    baseline_receipt = _read_object(g596_materialization_path)
    contracts_by_page = {
        int(item["page"]): item["layout_contract"]
        for item in contract_receipt.get("pages") or []
    }
    baseline_by_case = {
        str(item["case_id"]): item for item in baseline_receipt.get("cases") or []
    }
    cases = [
        item
        for item in g596_manifest["cases"]
        if item["case_id"] in manifest["development"]["g596_cases"]
    ]
    pages = sorted({int(item["page"]) for item in cases})
    capabilities = {
        int(item["page"]): (
            "layout_lines"
            if item["role"] == "ordinary_prose_control"
            else "table_candidates"
        )
        for item in cases
    }
    started = time.perf_counter()
    layouts, parser_evidence = _parse_selected_source_pages(
        pdf_bytes, pages, capabilities
    )
    axis_registry: dict[tuple[str, int], list[float]] = {}
    private_cases: list[dict[str, Any]] = []
    adapter = PdfplumberTableExtractorAdapter(
        pdf_bytes, expected_version=manifest["candidate"]["version"]
    )
    try:
        for case in sorted(cases, key=lambda item: int(item["page"])):
            page_number = int(case["page"])
            page_contract = contracts_by_page.get(page_number)
            if not isinstance(page_contract, dict):
                private_cases.append(_failed_case(case, "g597_layout_contract_missing"))
                continue
            tables = page_contract.get("tables") or []
            if case["role"] == "ordinary_prose_control":
                rejection_codes = []
                false_positive = None
                for table_contract in tables:
                    try:
                        false_positive = _extract_one_table(
                            case=case,
                            page_layout=layouts[page_number],
                            variant_a_page=_load_variant_a_page(
                                g594_private_dir, g596_manifest, case
                            ),
                            contract=table_contract,
                            axis_registry=axis_registry,
                            adapter=adapter,
                            baseline=None,
                        )
                        break
                    except G597Error as exc:
                        rejection_codes.append(exc.code)
                private_cases.append(
                    {
                        "case_id": case["case_id"],
                        "role": case["role"],
                        "page": page_number,
                        "status": (
                            "false_positive_materialized"
                            if false_positive is not None
                            else "fail_closed_non_table"
                        ),
                        "reason_code": (
                            "G597_PROSE_CONTRACT_MATERIALIZED"
                            if false_positive is not None
                            else "ALL_PROSE_CONTRACTS_REJECTED"
                        ),
                        "rejection_codes": rejection_codes,
                        "materialization": false_positive,
                    }
                )
                continue
            ordinal = int(case["visual_table_ordinal"])
            if ordinal < 1 or ordinal > len(tables):
                private_cases.append(_failed_case(case, "g597_target_table_missing"))
                continue
            try:
                private_cases.append(
                    {
                        "case_id": case["case_id"],
                        "role": case["role"],
                        "page": page_number,
                        "status": "materialized",
                        "reason_code": None,
                        "materialization": _extract_one_table(
                            case=case,
                            page_layout=layouts[page_number],
                            variant_a_page=_load_variant_a_page(
                                g594_private_dir, g596_manifest, case
                            ),
                            contract=tables[ordinal - 1],
                            axis_registry=axis_registry,
                            adapter=adapter,
                            baseline=baseline_by_case.get(str(case["case_id"])),
                        ),
                    }
                )
            except G597Error as exc:
                private_cases.append(_failed_case(case, exc.code))
    finally:
        adapter.close()

    safe_cases = [_safe_development_case(item, case) for item, case in zip(private_cases, cases)]
    aggregate = _development_aggregate(safe_cases)
    complexity = _complexity_evidence()
    terminal = _development_terminal(aggregate, manifest)
    implementation_hash = _sha256_file(SCRIPT_PATH)
    private = {
        "schema_version": PRIVATE_DEVELOPMENT_SCHEMA,
        "goal": "G5.97",
        "manifest_file_sha256": _sha256_file(manifest_path),
        "implementation_sha256": implementation_hash,
        "g596_contract_file_sha256": _sha256_file(g596_contract_path),
        "g596_materialization_file_sha256": _sha256_file(g596_materialization_path),
        "parser": parser_evidence,
        "engine": {
            "name": "pdfplumber",
            "version": manifest["candidate"]["version"],
            "engine_strings_used": 0,
        },
        "axis_registry": [
            {"anchor_signature": key[0], "columns": key[1], "boundaries": value}
            for key, value in sorted(axis_registry.items())
        ],
        "cases": private_cases,
        "aggregate": aggregate,
        "complexity": complexity,
        "terminal": terminal,
    }
    _write_json(private_output, private)
    safe = {
        "schema_version": SAFE_DEVELOPMENT_SCHEMA,
        "goal": "G5.97",
        "phase": "development_native_engine_comparison",
        "status": "complete" if terminal == DEVELOPMENT_PROVEN else "stopped",
        "terminal": terminal,
        "manifest_file_sha256": _sha256_file(manifest_path),
        "implementation_sha256": implementation_hash,
        "development_private_file_sha256": _sha256_file(private_output),
        "provider_calls": 0,
        "vlm_body_values_used": 0,
        "engine_strings_used": 0,
        "invented_source_literals": aggregate["invented_source_literals"],
        "cases": safe_cases,
        "aggregate": aggregate,
        "complexity": complexity,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "scope": copy.deepcopy(manifest["scope"]),
        "privacy": _privacy_statement(),
    }
    _write_json(safe_output, safe)
    return {"status": safe["status"], "terminal": terminal}


def _load_frozen_inputs(
    manifest_path: Path,
    g596_manifest_path: Path,
    g596_contract_path: Path | None = None,
    g596_materialization_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _read_object(manifest_path)
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("goal") != "G5.97"
        or manifest.get("frozen") is not True
    ):
        raise G597Error("g597_manifest_invalid")
    expected = manifest["frozen_inputs"]
    if _sha256_file(g596_manifest_path) != expected["g596_manifest_file_sha256"]:
        raise G597Error("g597_g596_manifest_hash_drift")
    if g596_contract_path is not None and (
        _sha256_file(g596_contract_path)
        != expected["g596_contract_private_file_sha256"]
    ):
        raise G597Error("g597_g596_contract_hash_drift")
    if g596_materialization_path is not None and (
        _sha256_file(g596_materialization_path)
        != expected["g596_materialization_private_file_sha256"]
    ):
        raise G597Error("g597_g596_materialization_hash_drift")
    g596_manifest = _read_object(g596_manifest_path)
    if g596_manifest.get("goal") != "G5.96" or g596_manifest.get("frozen") is not True:
        raise G597Error("g597_g596_manifest_invalid")
    return manifest, g596_manifest


def _verified_source_bytes(source_pdf: Path, manifest: dict[str, Any]) -> bytes:
    if _sha256_file(source_pdf) != manifest["source"]["pdf_sha256"]:
        raise G597Error("g597_source_pdf_hash_drift")
    return source_pdf.read_bytes()


def _parse_selected_source_pages(
    pdf_bytes: bytes,
    page_numbers: list[int],
    capabilities: dict[int, str],
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    reader = pypdf.PdfReader(BytesIO(pdf_bytes), strict=False)
    parsers = {
        capability: PdfTextLayerParserFactory().create(
            PdfParserCapabilityRequest(capability=capability)
        )
        for capability in sorted(set(capabilities.values()))
    }
    pages: dict[int, dict[str, Any]] = {}
    evidence: dict[str, Any] | None = None
    elapsed = 0.0
    for page_number in page_numbers:
        if not 1 <= page_number <= len(reader.pages):
            raise G597Error("g597_page_out_of_range")
        writer = pypdf.PdfWriter()
        writer.add_page(reader.pages[page_number - 1])
        buffer = BytesIO()
        writer.write(buffer)
        result = parsers[capabilities[page_number]].parse(buffer.getvalue())
        if result.layout_projection_status != "complete" or len(result.pages) != 1:
            raise G597Error("g597_parser_layout_incomplete")
        page = copy.deepcopy(result.pages[0])
        page["page_number"] = page_number
        pages[page_number] = page
        elapsed += float(result.diagnostics.get("elapsed_milliseconds_total") or 0)
        if evidence is None:
            evidence = {
                "factory_entrypoint": "PdfTextLayerParserFactory.create",
                "engine": result.parser_engine,
                "engine_version": result.parser_engine_version,
                "config_ref": result.parser_config_ref,
                "source_pdf_hash_verified_before_lossless_slice": True,
            }
    if evidence is None:
        raise G597Error("g597_page_set_empty")
    evidence["selected_pages"] = page_numbers
    evidence["elapsed_milliseconds"] = round(elapsed, 3)
    return pages, evidence


def _extract_one_table(
    *,
    case: dict[str, Any],
    page_layout: dict[str, Any],
    variant_a_page: dict[str, Any],
    contract: dict[str, Any],
    axis_registry: dict[tuple[str, int], list[float]],
    adapter: PdfplumberTableExtractorAdapter,
    baseline: dict[str, Any] | None,
) -> dict[str, Any]:
    resolved = _resolve_contract(
        page_layout=page_layout,
        contract=contract,
        axis_registry=axis_registry,
    )
    geometry = adapter.extract_geometry(
        page_number=int(case["page"]),
        source_region=resolved["source_region"],
        visual_column_boundaries=resolved["column_boundaries"],
        expected_columns=resolved["visual_columns"],
    )
    bindings = _source_bindings(variant_a_page)
    rows, assigned = _bind_source_words(
        page_layout=page_layout,
        candidate_words=resolved["candidate_words"],
        native_rows=geometry["rows"],
        bindings=bindings,
    )
    expected_ordinals = {
        int(item["parser_ordinal"]) for item in resolved["candidate_words"]
    }
    if assigned != expected_ordinals:
        raise G597Error("g597_source_word_coverage_incomplete")
    source_refs = [
        token["source_value_ref"]
        for row in rows
        for cell in row["cells"]
        for token in cell["source_tokens"]
    ]
    if len(source_refs) != len(expected_ordinals) or len(set(source_refs)) != len(source_refs):
        raise G597Error("g597_source_ref_coverage_incomplete")
    mapping_digest = _mapping_digest(rows)
    baseline_materialization = (
        baseline.get("materialization") if isinstance(baseline, dict) else None
    )
    baseline_digest = (
        baseline_materialization.get("mapping_digest")
        if isinstance(baseline_materialization, dict)
        else None
    )
    return {
        "schema_version": "broker_reports_native_extracted_source_table_g597_private_v1",
        "visibility": "research_private_not_published",
        "page_number": int(case["page"]),
        "layout_contract_sha256": _sha256_json(contract),
        "resolved_source_region": {
            "bbox": resolved["source_region"],
            "parser_columns": resolved["parser_columns"],
            "visual_columns": resolved["visual_columns"],
            "mode": resolved["mode"],
            "candidate_count": resolved["candidate_count"],
        },
        "native_engine_configuration": geometry["configuration"],
        "native_engine_table_bbox": geometry["table_bbox"],
        "rows": rows,
        "row_count": len(rows),
        "column_count": resolved["visual_columns"],
        "source_word_count": len(expected_ordinals),
        "source_value_ref_count": len(source_refs),
        "source_ref_coverage_ratio": 1.0,
        "invented_source_literals": 0,
        "vlm_body_values_used": 0,
        "engine_strings_used": 0,
        "mapping_digest": mapping_digest,
        "g596_mapping_digest": baseline_digest,
        "mapping_matches_g596": baseline_digest == mapping_digest if baseline_digest else None,
    }


def _resolve_contract(
    *,
    page_layout: dict[str, Any],
    contract: dict[str, Any],
    axis_registry: dict[tuple[str, int], list[float]],
) -> dict[str, Any]:
    _validate_layout_contract({"tables": [contract]})
    lines = page_layout.get("line_inventory") or []
    words = page_layout.get("word_inventory") or []
    start_line = _resolve_line(
        lines,
        contract["start_hints"]["anchor_tokens"],
        collapse_multiword_phrase=True,
    )
    start_y = float(start_line["bbox"][1])
    end_hints = contract["end_hints"]
    if end_hints["boundary"] == "end_of_page":
        end_y = float(page_layout["height"])
    elif end_hints["boundary"] == "footer":
        footers = [
            line
            for line in lines
            if float(line["bbox"][1]) >= float(page_layout["height"]) * 0.95
        ]
        if len(footers) != 1:
            raise G597Error("g597_footer_boundary_ambiguous")
        end_y = float(footers[0]["bbox"][1])
    else:
        end_y = float(
            _resolve_line(
                lines,
                end_hints["anchor_tokens"],
                after_y=start_y,
                first_after=True,
                collapse_multiword_phrase=True,
            )["bbox"][1]
        )
    if end_y <= start_y:
        raise G597Error("g597_end_boundary_before_start")
    visual_columns = int(contract["structure"]["columns"])
    axis_key = (_line_signature(start_line), visual_columns)
    hints = contract.get("header_cell_token_hints") or []
    if not hints and axis_key not in axis_registry:
        raise G597Error("g597_layout_axis_not_resolvable")
    candidates = [
        item
        for item in page_layout.get("table_candidate_inventory") or []
        if float(item["bbox"][3]) > start_y and float(item["bbox"][1]) < end_y
    ]
    candidates.sort(key=lambda item: (float(item["bbox"][1]), float(item["bbox"][0])))
    ordinal = int(contract["start_hints"]["table_ordinal_after_anchor"])
    if ordinal > len(candidates):
        raise G597Error("g597_source_region_not_found")
    candidate = candidates[ordinal - 1]
    if sum(_bbox_iou(item["bbox"], candidate["bbox"]) >= 0.8 for item in candidates) != 1:
        raise G597Error("g597_source_region_ambiguous")
    parser_columns = int(candidate.get("columns_total") or 0)
    if parser_columns < 2 or visual_columns < 2:
        raise G597Error("g597_source_structure_incompatible")
    ordinals = {int(value) for value in candidate["contributing_word_parser_ordinals"]}
    candidate_words = [
        item for item in words if int(item["parser_ordinal"]) in ordinals
    ]
    if len(candidate_words) != len(ordinals):
        raise G597Error("g597_candidate_word_inventory_incomplete")
    if hints and parser_columns == visual_columns:
        boundaries = _candidate_axis(candidate, expected=visual_columns)
        verified = 0
        for index, hint in enumerate(hints):
            try:
                anchor = _header_anchor(candidate_words, hint)
            except G597Error as exc:
                if exc.code != "g597_header_hint_not_found":
                    raise
                continue
            if not _in_band(anchor, boundaries, index):
                raise G597Error("g597_header_hint_source_column_incompatible")
            verified += 1
        if verified < max(2, visual_columns - 1):
            raise G597Error("g597_header_hint_source_coverage_insufficient")
        mode = "preserved_source_candidate_axis"
        axis_registry[axis_key] = list(boundaries)
    elif hints:
        boundaries = _header_axis(candidate_words, candidate["bbox"], hints)
        mode = "header_resolved_axis"
        axis_registry[axis_key] = list(boundaries)
    else:
        boundaries = list(axis_registry[axis_key])
        mode = "inherited_resolved_axis"
    return {
        "source_region": list(candidate["bbox"]),
        "column_boundaries": boundaries,
        "parser_columns": parser_columns,
        "visual_columns": visual_columns,
        "candidate_count": len(candidates),
        "candidate_words": candidate_words,
        "axis_key": axis_key,
        "mode": mode,
    }


def _resolve_line(
    lines: list[dict[str, Any]],
    tokens: list[str],
    *,
    after_y: float | None = None,
    first_after: bool = False,
    collapse_multiword_phrase: bool = False,
) -> dict[str, Any]:
    target = [_normalized(token) for token in tokens]
    exact = []
    concatenated = []
    joined_target = "".join(target)
    for line in lines:
        if after_y is not None and float(line["bbox"][1]) <= after_y:
            continue
        source = [_normalized(token) for token in str(line.get("text") or "").split()]
        if _ordered_contains(source, target):
            exact.append(line)
        if joined_target and joined_target in "".join(source):
            concatenated.append(line)
    matches = exact or concatenated
    if not matches:
        raise G597Error("g597_breadcrumb_line_not_found")
    if len(matches) > 1:
        may_take_first = first_after or (
            not exact
            and collapse_multiword_phrase
            and any(any(char.isspace() for char in token) for token in tokens)
        )
        if not may_take_first:
            raise G597Error("g597_breadcrumb_line_ambiguous")
        matches.sort(key=lambda item: (float(item["bbox"][1]), float(item["bbox"][0])))
    return matches[0]


def _header_axis(
    words: list[dict[str, Any]], bbox: list[float], hints: list[dict[str, Any]]
) -> list[float]:
    anchors = [_header_anchor(words, hint) for hint in hints]
    if anchors != sorted(anchors) or len(set(round(value, 3) for value in anchors)) != len(anchors):
        raise G597Error("g597_header_axis_not_strictly_ordered")
    return [
        float(bbox[0]),
        *(round((left + right) / 2.0, 3) for left, right in zip(anchors, anchors[1:])),
        float(bbox[2]),
    ]


def _header_anchor(words: list[dict[str, Any]], hint: dict[str, Any]) -> float:
    target = "".join(_normalized(token) for token in hint["tokens"])
    usable = [
        word
        for word in words
        if (piece := _normalized(str(word["text"])))
        and any(char.isalpha() for char in piece)
        and piece in target
    ]
    candidates = []
    for size in range(1, min(4, len(usable)) + 1):
        for combination in itertools.combinations(usable, size):
            ordered = sorted(
                combination,
                key=lambda item: (float(item["bbox"][1]), float(item["bbox"][0])),
            )
            if "".join(_normalized(str(item["text"])) for item in ordered) != target:
                continue
            centers = [_center(item["bbox"], "x") for item in ordered]
            candidates.append(
                (
                    max(centers) - min(centers),
                    tuple(int(item["parser_ordinal"]) for item in ordered),
                    statistics.median(centers),
                )
            )
    candidates.sort()
    if not candidates:
        raise G597Error("g597_header_hint_not_found")
    if len(candidates) > 1 and abs(candidates[0][0] - candidates[1][0]) < 0.001:
        raise G597Error("g597_header_hint_ambiguous")
    return float(candidates[0][2])


def _candidate_axis(candidate: dict[str, Any], *, expected: int) -> list[float]:
    boundaries = sorted(
        {
            round(float(cell["bbox"][index]), 3)
            for cell in candidate.get("cell_inventory") or []
            for index in (0, 2)
        }
    )
    if len(boundaries) != expected + 1:
        raise G597Error("g597_source_x_boundaries_incompatible")
    return boundaries


def _source_bindings(variant_a_page: dict[str, Any]) -> dict[int, dict[str, str]]:
    ordinal_to_word_ref: dict[int, str] = {}
    for line in variant_a_page.get("lines") or []:
        ordinals = line.get("word_parser_ordinals") or []
        refs = line.get("word_refs") or []
        if len(ordinals) != len(refs):
            raise G597Error("g597_variant_a_word_ref_alignment_invalid")
        for ordinal, word_ref in zip(ordinals, refs):
            ordinal_to_word_ref[int(ordinal)] = str(word_ref)
    word_to_value_ref: dict[str, str] = {}
    for unit in variant_a_page.get("source_units") or []:
        for entry in unit.get("pdf_layout_source_value_index") or []:
            word_ref = str(entry.get("source_object_ref") or "")
            value_ref = str(entry.get("source_value_ref") or "")
            if word_ref.startswith("pdfword_") and value_ref:
                previous = word_to_value_ref.setdefault(word_ref, value_ref)
                if previous != value_ref:
                    raise G597Error("g597_variant_a_source_value_ref_ambiguous")
    literals: dict[str, str] = {}
    for table in variant_a_page.get("table_projections") or []:
        for value in table.get("private_values") or []:
            word_ref = str(value.get("source_object_ref") or "")
            if word_ref.startswith("pdfword_"):
                literal = str(value.get("normalized_value") or "")
                previous = literals.setdefault(word_ref, literal)
                if previous != literal:
                    raise G597Error("g597_variant_a_word_literal_ambiguous")
    return {
        ordinal: {
            "source_word_ref": word_ref,
            "source_value_ref": word_to_value_ref.get(word_ref, ""),
            "frozen_literal": literals.get(word_ref, ""),
        }
        for ordinal, word_ref in ordinal_to_word_ref.items()
    }


def _bind_source_words(
    *,
    page_layout: dict[str, Any],
    candidate_words: list[dict[str, Any]],
    native_rows: list[list[list[float]]],
    bindings: dict[int, dict[str, str]],
) -> tuple[list[dict[str, Any]], set[int]]:
    word_to_line = {
        int(ordinal): int(line["parser_ordinal"])
        for line in page_layout.get("line_inventory") or []
        for ordinal in line.get("word_parser_ordinals") or []
    }
    assigned: set[int] = set()
    rows = []
    for row_index, native_cells in enumerate(native_rows, 1):
        cells = []
        for column_index, bbox in enumerate(native_cells, 1):
            members = [
                word
                for word in candidate_words
                if _bbox_center_inside(word["bbox"], bbox)
            ]
            members.sort(
                key=lambda item: (
                    word_to_line.get(int(item["parser_ordinal"]), 0),
                    float(item["bbox"][0]),
                )
            )
            tokens = []
            for word in members:
                ordinal = int(word["parser_ordinal"])
                binding = bindings.get(ordinal) or {}
                literal = str(word.get("text") or "")
                if (
                    not binding.get("source_value_ref")
                    or binding.get("frozen_literal") != literal
                ):
                    raise G597Error("g597_parser_literal_not_source_verified")
                if ordinal in assigned:
                    raise G597Error("g597_source_word_duplicate_assignment")
                assigned.add(ordinal)
                tokens.append(
                    {
                        "literal": literal,
                        "parser_word_ordinal": ordinal,
                        "parser_line_ordinal": word_to_line.get(ordinal),
                        "source_word_ref": binding["source_word_ref"],
                        "source_value_ref": binding["source_value_ref"],
                        "parser_bbox": word["bbox"],
                    }
                )
            line_groups: list[list[dict[str, Any]]] = []
            for token in tokens:
                if (
                    not line_groups
                    or line_groups[-1][0]["parser_line_ordinal"]
                    != token["parser_line_ordinal"]
                ):
                    line_groups.append([token])
                else:
                    line_groups[-1].append(token)
            cells.append(
                {
                    "row_ordinal": row_index,
                    "column_ordinal": column_index,
                    "native_cell_bbox": bbox,
                    "literal": "\n".join(
                        " ".join(str(token["literal"]) for token in line)
                        for line in line_groups
                    ),
                    "source_value_refs": [
                        token["source_value_ref"] for token in tokens
                    ],
                    "source_tokens": tokens,
                }
            )
        rows.append({"row_ordinal": row_index, "cells": cells})
    return rows, assigned


def _mapping_digest(rows: list[dict[str, Any]]) -> str:
    return _digest(
        [
            [
                [token["source_word_ref"] for token in cell["source_tokens"]]
                for cell in row["cells"]
            ]
            for row in rows
        ]
    )


def _safe_development_case(
    outcome: dict[str, Any], expected: dict[str, Any]
) -> dict[str, Any]:
    materialized = outcome.get("materialization") or {}
    return {
        "case_id": outcome["case_id"],
        "role": outcome["role"],
        "page": outcome["page"],
        "status": outcome["status"],
        "reason_code": outcome.get("reason_code"),
        "rejection_codes": outcome.get("rejection_codes") or [],
        "expected_parser_columns": int(expected.get("expected_parser_columns") or 0),
        "expected_visual_columns": int(expected.get("expected_visual_columns") or 0),
        "expected_rows": int(expected.get("expected_rows") or 0),
        "observed_parser_columns": int(
            (materialized.get("resolved_source_region") or {}).get("parser_columns") or 0
        ),
        "materialized_columns": int(materialized.get("column_count") or 0),
        "materialized_rows": int(materialized.get("row_count") or 0),
        "source_words": int(materialized.get("source_word_count") or 0),
        "source_value_refs": int(materialized.get("source_value_ref_count") or 0),
        "source_ref_coverage_ratio": float(
            materialized.get("source_ref_coverage_ratio") or 0
        ),
        "invented_source_literals": int(
            materialized.get("invented_source_literals") or 0
        ),
        "mapping_matches_g596": materialized.get("mapping_matches_g596"),
        "materialization_mode": (
            materialized.get("resolved_source_region") or {}
        ).get("mode"),
    }


def _development_aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    development = [item for item in cases if item["role"].startswith("known_wrong")]
    known_good = [item for item in cases if item["role"] == "known_good_table_control"]
    prose = [item for item in cases if item["role"] == "ordinary_prose_control"]
    materialized = [item for item in cases if item["status"] == "materialized"]
    return {
        "known_wrong_column_relations_corrected": sum(
            item["observed_parser_columns"] == item["expected_parser_columns"]
            and item["materialized_columns"] == item["expected_visual_columns"]
            and item["materialized_rows"] == item["expected_rows"]
            for item in development
        ),
        "known_good_controls_preserved": sum(
            item["materialized_columns"] == item["expected_visual_columns"]
            and item["materialized_rows"] == item["expected_rows"]
            for item in known_good
        ),
        "non_table_controls_fail_closed": sum(
            item["status"] == "fail_closed_non_table" for item in prose
        ),
        "materialized_source_words": sum(item["source_words"] for item in materialized),
        "materialized_source_value_refs": sum(
            item["source_value_refs"] for item in materialized
        ),
        "source_ref_coverage_ratio": (
            1.0
            if materialized
            and all(item["source_ref_coverage_ratio"] == 1.0 for item in materialized)
            else 0.0
        ),
        "invented_source_literals": sum(
            item["invented_source_literals"] for item in materialized
        ),
        "native_mapping_matches_g596": sum(
            item["mapping_matches_g596"] is True for item in materialized
        ),
        "engine_strings_used": 0,
    }


def _development_terminal(
    aggregate: dict[str, Any], manifest: dict[str, Any]
) -> str:
    expected = manifest["development"]["acceptance"]
    keys = (
        "known_wrong_column_relations_corrected",
        "known_good_controls_preserved",
        "non_table_controls_fail_closed",
        "materialized_source_words",
        "source_ref_coverage_ratio",
        "invented_source_literals",
        "native_mapping_matches_g596",
    )
    return (
        DEVELOPMENT_PROVEN
        if all(aggregate[key] == expected[key] for key in keys)
        else DEVELOPMENT_FAILED
    )


def _complexity_evidence() -> dict[str, Any]:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    core_names = {
        "_resolve_contract",
        "_resolve_line",
        "_header_axis",
        "_header_anchor",
        "_candidate_axis",
        "_source_bindings",
        "_bind_source_words",
        "extract_geometry",
    }
    nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in core_names
    ]
    adapter = next(node for node in nodes if node.name == "extract_geometry")
    failures = sorted(set(re.findall(r'"(g597_[a-z0-9_]+)"', source)))
    page_branches = re.findall(
        r"\b(?:page|page_number)\s*(?:==|in)\s*(?:\d+|\([^)]*\d[^)]*\))",
        source,
    )
    return {
        "g596_custom_core_source_lines": 407,
        "g596_custom_core_functions": 10,
        "native_path_custom_core_source_lines": sum(
            int(node.end_lineno or node.lineno) - int(node.lineno) + 1
            for node in nodes
        ),
        "native_path_custom_core_functions": len(nodes),
        "engine_specific_adapter_source_lines": int(adapter.end_lineno or adapter.lineno)
        - int(adapter.lineno)
        + 1,
        "engine_specific_adapter_functions": 1,
        "custom_numeric_thresholds": 3,
        "vendor_strategy_choices": 2,
        "vendor_numeric_overrides": 0,
        "failure_classes_whole_harness": len(failures),
        "document_specific_code_branches": len(page_branches),
        "body_value_heuristic_rules": 0,
        "financial_semantic_rules": 0,
        "production_owner_changes": 0,
        "new_dependencies": 0,
        "whole_research_harness_source_lines": len(source.splitlines()),
        "native_engine_replaces": [
            "row_boundary_detection",
            "cell_rectangle_construction",
            "row_cell_grid_assembly",
        ],
        "custom_code_retained": [
            "breadcrumb_and_region_resolution",
            "visual_column_axis_resolution_or_inheritance",
            "exact_parser_word_and_source_ref_binding",
            "fail_closed_validation",
        ],
    }


def generate_holdout_contract(
    *,
    manifest_path: Path,
    g596_manifest_path: Path,
    development_private: Path,
    development_safe: Path,
    g594_private_dir: Path,
    env_path: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    manifest, g596_manifest = _load_frozen_inputs(manifest_path, g596_manifest_path)
    _require_fresh_outputs(private_output, safe_output)
    frozen_private, frozen_safe = _validate_frozen_development(
        development_private, development_safe
    )
    provider_contract = g596_manifest["provider"]
    provider = PdfGridExperimentProviderFactory(
        PdfGridProviderConfig(
            provider_profile=str(provider_contract["provider_profile"]),
            model_id=str(provider_contract["model_id"]),
            timeout_seconds=240,
            maximum_output_tokens=int(provider_contract["maximum_output_tokens"]),
            maximum_counted_input_tokens=int(
                provider_contract["maximum_counted_input_tokens"]
            ),
            thinking_level=str(provider_contract["thinking_level"]),
        )
    ).create_for_openwebui(_openwebui_request(env_path.resolve()))
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise G597Error("g597_provider_not_qualified")
    holdout = manifest["unseen_holdout"]
    page_number = int(holdout["page"])
    page_path = (
        g594_private_dir
        / "documents"
        / str(holdout["document_id"])
        / "pages"
        / f"p{page_number:03d}.private.png"
    )
    png_bytes = page_path.read_bytes()
    if hashlib.sha256(png_bytes).hexdigest() != holdout["page_png_sha256"]:
        raise G597Error("g597_holdout_png_hash_drift")
    outcome = provider.invoke(
        task_id="g597_frozen_unseen_holdout",
        model_view={"task": str(provider_contract["prompt"])},
        output_schema=copy.deepcopy(provider_contract["response_schema"]),
        png_bytes=png_bytes,
        crop_sha256=holdout["page_png_sha256"],
        attempt_number=1,
        attempt_lineage=[],
    )
    contract = outcome.get("json_output")
    validation_error = None
    try:
        _validate_layout_contract(contract)
    except G597Error as exc:
        validation_error = exc.code
        contract = None
    private = {
        "schema_version": PRIVATE_HOLDOUT_CONTRACT_SCHEMA,
        "goal": "G5.97",
        "manifest_file_sha256": _sha256_file(manifest_path),
        "implementation_sha256": frozen_private["implementation_sha256"],
        "development_private_file_sha256": _sha256_file(development_private),
        "development_safe_file_sha256": _sha256_file(development_safe),
        "page": page_number,
        "page_png_sha256": holdout["page_png_sha256"],
        "layout_contract": contract,
        "validation_error": validation_error,
        "attempt": outcome.get("attempt"),
        "raw_private_response": outcome.get("raw_private_response"),
        "response_hash": outcome.get("response_hash"),
        "qualification": qualification,
        "provider_policy": {
            "attempts": 1,
            "retry": False,
            "best_of_n": False,
            "post_open_tuning": False,
            "vlm_body_values": 0,
        },
    }
    _write_json(private_output, private)
    safe = {
        "schema_version": SAFE_HOLDOUT_CONTRACT_SCHEMA,
        "goal": "G5.97",
        "phase": "frozen_unseen_holdout_contract",
        "status": "complete" if contract is not None else "blocked",
        "page": page_number,
        "provider_calls": 1,
        "tables": len((contract or {}).get("tables") or []),
        "validation_error": validation_error,
        "response_hash": outcome.get("response_hash"),
        "attempt": _safe_attempt(outcome.get("attempt")),
        "implementation_sha256": frozen_safe["implementation_sha256"],
        "holdout_contract_private_file_sha256": _sha256_file(private_output),
        "vlm_body_values_used": 0,
        "privacy": _privacy_statement(),
    }
    _write_json(safe_output, safe)
    return {"status": safe["status"], "provider_calls": 1}


def run_holdout(
    *,
    manifest_path: Path,
    g596_manifest_path: Path,
    development_private: Path,
    development_safe: Path,
    holdout_contract: Path,
    g594_private_dir: Path,
    source_pdf: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    manifest, g596_manifest = _load_frozen_inputs(manifest_path, g596_manifest_path)
    _require_fresh_outputs(private_output, safe_output)
    frozen_private, frozen_safe = _validate_frozen_development(
        development_private, development_safe
    )
    contract_receipt = _read_object(holdout_contract)
    if (
        contract_receipt.get("schema_version") != PRIVATE_HOLDOUT_CONTRACT_SCHEMA
        or contract_receipt.get("implementation_sha256")
        != frozen_private["implementation_sha256"]
    ):
        raise G597Error("g597_holdout_contract_receipt_invalid")
    contract = contract_receipt.get("layout_contract")
    _validate_layout_contract(contract)
    holdout = manifest["unseen_holdout"]
    page_number = int(holdout["page"])
    pdf_bytes = _verified_source_bytes(source_pdf, manifest)
    layouts, parser_evidence = _parse_selected_source_pages(
        pdf_bytes, [page_number], {page_number: "table_candidates"}
    )
    case = {
        "case_id": "unseen_holdout_01",
        "role": "unseen_holdout",
        "page": page_number,
        "variant_a_page_sha256": holdout["variant_a_page_sha256"],
    }
    variant_a = _load_variant_a_page(g594_private_dir, g596_manifest, case)
    axis_registry = {
        (str(item["anchor_signature"]), int(item["columns"])): list(
            item["boundaries"]
        )
        for item in frozen_private.get("axis_registry") or []
    }
    tables = contract.get("tables") or []
    started = time.perf_counter()
    if not tables:
        outcome = {
            "case_id": case["case_id"],
            "role": case["role"],
            "page": page_number,
            "status": "fail_closed_non_table",
            "reason_code": "NO_TABLE_LAYOUT_CONTRACT",
            "materialization": None,
        }
    else:
        ordinal = int(holdout["visual_table_ordinal"])
        if ordinal > len(tables):
            outcome = _failed_case(case, "g597_holdout_target_table_missing")
        else:
            adapter = PdfplumberTableExtractorAdapter(
                pdf_bytes, expected_version=manifest["candidate"]["version"]
            )
            try:
                materialized = _extract_one_table(
                    case=case,
                    page_layout=layouts[page_number],
                    variant_a_page=variant_a,
                    contract=tables[ordinal - 1],
                    axis_registry=axis_registry,
                    adapter=adapter,
                    baseline=None,
                )
                outcome = {
                    "case_id": case["case_id"],
                    "role": case["role"],
                    "page": page_number,
                    "status": "materialized",
                    "reason_code": None,
                    "materialization": materialized,
                }
            except G597Error as exc:
                outcome = _failed_case(case, exc.code)
            finally:
                adapter.close()
    materialized = outcome.get("materialization") or {}
    accepted = outcome["status"] in {"materialized", "fail_closed_non_table"}
    terminal = HOLDOUT_EXECUTED if accepted else HOLDOUT_FAILED
    private = {
        "schema_version": PRIVATE_HOLDOUT_SCHEMA,
        "goal": "G5.97",
        "manifest_file_sha256": _sha256_file(manifest_path),
        "implementation_sha256": frozen_private["implementation_sha256"],
        "development_private_file_sha256": _sha256_file(development_private),
        "development_safe_file_sha256": _sha256_file(development_safe),
        "holdout_contract_file_sha256": _sha256_file(holdout_contract),
        "parser": parser_evidence,
        "case": outcome,
        "terminal": terminal,
    }
    _write_json(private_output, private)
    safe = {
        "schema_version": SAFE_HOLDOUT_SCHEMA,
        "goal": "G5.97",
        "phase": "frozen_unseen_holdout_materialization",
        "status": "complete" if accepted else "stopped",
        "terminal": terminal,
        "page": page_number,
        "case_status": outcome["status"],
        "reason_code": outcome.get("reason_code"),
        "materialized_columns": int(materialized.get("column_count") or 0),
        "materialized_rows": int(materialized.get("row_count") or 0),
        "source_words": int(materialized.get("source_word_count") or 0),
        "source_value_refs": int(materialized.get("source_value_ref_count") or 0),
        "source_ref_coverage_ratio": float(
            materialized.get("source_ref_coverage_ratio") or 0
        ),
        "invented_source_literals": int(
            materialized.get("invented_source_literals") or 0
        ),
        "provider_calls_during_materialization": 0,
        "engine_strings_used": 0,
        "post_open_tuning": False,
        "implementation_sha256": frozen_safe["implementation_sha256"],
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "scope": copy.deepcopy(manifest["scope"]),
        "privacy": _privacy_statement(),
    }
    _write_json(safe_output, safe)
    return {"status": safe["status"], "terminal": terminal}


def _validate_frozen_development(
    private_path: Path, safe_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    private = _read_object(private_path)
    safe = _read_object(safe_path)
    if (
        private.get("schema_version") != PRIVATE_DEVELOPMENT_SCHEMA
        or safe.get("schema_version") != SAFE_DEVELOPMENT_SCHEMA
        or private.get("terminal") != DEVELOPMENT_PROVEN
        or safe.get("terminal") != DEVELOPMENT_PROVEN
        or safe.get("development_private_file_sha256") != _sha256_file(private_path)
        or private.get("implementation_sha256") != _sha256_file(SCRIPT_PATH)
        or safe.get("implementation_sha256") != _sha256_file(SCRIPT_PATH)
    ):
        raise G597Error("g597_development_freeze_invalid")
    return private, safe


def _validate_layout_contract(value: Any) -> None:
    _reject_forbidden_keys(value)
    if not isinstance(value, dict) or set(value) != {"tables"}:
        raise G597Error("g597_layout_contract_shape_invalid")
    tables = value.get("tables")
    if not isinstance(tables, list) or len(tables) > 20:
        raise G597Error("g597_layout_contract_tables_invalid")
    for table in tables:
        if not isinstance(table, dict) or set(table) != {
            "local_name",
            "start_hints",
            "end_hints",
            "structure",
            "header_cell_token_hints",
        }:
            raise G597Error("g597_layout_table_shape_invalid")
        start = table["start_hints"]
        end = table["end_hints"]
        structure = table["structure"]
        if not isinstance(start, dict) or set(start) != {
            "anchor_tokens",
            "table_ordinal_after_anchor",
        }:
            raise G597Error("g597_start_hints_invalid")
        if not isinstance(end, dict) or set(end) != {"boundary", "anchor_tokens"}:
            raise G597Error("g597_end_hints_invalid")
        if end["boundary"] not in {"next_section", "footer", "end_of_page"}:
            raise G597Error("g597_end_boundary_invalid")
        if not isinstance(structure, dict) or set(structure) != {
            "columns",
            "header_rows",
            "continuation",
            "body_row_pattern",
            "wrapped_rows",
            "subtotal_rows",
        }:
            raise G597Error("g597_structure_invalid")
        columns = structure["columns"]
        if not isinstance(columns, int) or isinstance(columns, bool) or not 2 <= columns <= 100:
            raise G597Error("g597_columns_invalid")
        _validate_hint_tokens(start["anchor_tokens"], allow_empty=False)
        _validate_hint_tokens(end["anchor_tokens"], allow_empty=end["boundary"] != "next_section")
        hints = table["header_cell_token_hints"]
        if not isinstance(hints, list) or (hints and len(hints) != columns):
            raise G597Error("g597_header_hints_invalid")
        for hint in hints:
            if not isinstance(hint, dict) or set(hint) != {"tokens"}:
                raise G597Error("g597_header_hint_shape_invalid")
            _validate_hint_tokens(hint["tokens"], allow_empty=False)


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold() in _FORBIDDEN_CONTRACT_KEYS:
                raise G597Error("g597_contract_domain_leakage")
            _reject_forbidden_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_keys(nested)


def _validate_hint_tokens(value: Any, *, allow_empty: bool) -> None:
    if not isinstance(value, list) or (not value and not allow_empty) or len(value) > 12:
        raise G597Error("g597_hint_tokens_invalid")
    for token in value:
        if not isinstance(token, str) or not token.strip() or len(token) > 80 or _DIGIT_RE.search(token):
            raise G597Error("g597_hint_token_invalid")


def _load_variant_a_page(
    g594_private_dir: Path,
    g596_manifest: dict[str, Any],
    case: dict[str, Any],
) -> dict[str, Any]:
    page = int(case["page"])
    path = (
        g594_private_dir
        / "documents"
        / str(g596_manifest["source"]["document_id"])
        / "pages"
        / f"p{page:03d}.variant_a.private.json"
    )
    if _sha256_file(path) != case["variant_a_page_sha256"]:
        raise G597Error("g597_variant_a_page_hash_drift")
    return _read_object(path)


def _failed_case(case: dict[str, Any], code: str) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "role": case["role"],
        "page": int(case["page"]),
        "status": "failed",
        "reason_code": code,
        "materialization": None,
    }


def _normalized(value: str) -> str:
    return _NORMALIZE_RE.sub("", value.casefold())


def _ordered_contains(source: list[str], target: list[str]) -> bool:
    if not target:
        return False
    iterator = iter(source)
    return all(any(item == wanted for item in iterator) for wanted in target)


def _line_signature(line: dict[str, Any]) -> str:
    return _digest([_normalized(str(line.get("text") or ""))], length=20)


def _center(bbox: list[float], axis: str) -> float:
    indexes = (0, 2) if axis == "x" else (1, 3)
    return (float(bbox[indexes[0]]) + float(bbox[indexes[1]])) / 2.0


def _in_band(value: float, boundaries: list[float], index: int) -> bool:
    lower, upper = boundaries[index], boundaries[index + 1]
    return lower <= value <= upper if index == len(boundaries) - 2 else lower <= value < upper


def _bbox_center_inside(inner: list[float], outer: list[float]) -> bool:
    return _in_band(_center(inner, "x"), [outer[0], outer[2]], 0) and _in_band(
        _center(inner, "y"), [outer[1], outer[3]], 0
    )


def _bbox_iou(left: list[float], right: list[float]) -> float:
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _safe_attempt(attempt: Any) -> dict[str, Any]:
    attempt = attempt if isinstance(attempt, dict) else {}
    return {
        key: attempt.get(key)
        for key in (
            "attempt_number",
            "provider",
            "provider_profile",
            "model_requested",
            "model_resolved",
            "duration_ms",
            "http_status",
            "usage",
            "finish_reason",
            "parse_result",
            "terminal_failure_class",
            "hidden_retry",
            "provider_failover",
        )
    }


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(env.get("OPENWEBUI_HOST") or "").rstrip("/")
    email = str(env.get("WEBUI_ADMIN_EMAIL") or "")
    password = str(env.get("WEBUI_ADMIN_PASSWORD") or "")
    if not all((host, email, password)):
        raise G597Error("g597_openwebui_credentials_missing")
    base_url = host if host.startswith(("http://", "https://")) else f"https://{host}"
    session = requests.Session()
    response = session.post(
        base_url + "/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    token = str((response.json() or {}).get("token") or "")
    if not token:
        raise G597Error("g597_openwebui_token_missing")
    session.headers.update({"Authorization": f"Bearer {token}"})
    config_response = session.get(base_url + "/openai/config", timeout=30)
    config_response.raise_for_status()
    config = config_response.json() or {}
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                config=SimpleNamespace(
                    OPENAI_API_BASE_URLS=config.get("OPENAI_API_BASE_URLS"),
                    OPENAI_API_KEYS=config.get("OPENAI_API_KEYS"),
                    OPENAI_API_CONFIGS=config.get("OPENAI_API_CONFIGS"),
                )
            )
        )
    )


def _read_env(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise G597Error("g597_env_file_missing")
    result = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _require_fresh_outputs(*paths: Path) -> None:
    if any(path.exists() for path in paths):
        raise G597Error("g597_frozen_output_must_be_fresh")


def _privacy_statement() -> dict[str, bool]:
    return {
        "customer_literals_in_safe_output": False,
        "customer_paths_in_safe_output": False,
        "source_coordinates_in_safe_output": False,
        "provider_payloads_in_safe_output": False,
        "private_evidence_outside_git": True,
    }


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise G597Error("g597_json_object_required")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _digest(value: Any, *, length: int = 32) -> str:
    return _sha256_json(value)[:length]


if __name__ == "__main__":
    raise SystemExit(main())
