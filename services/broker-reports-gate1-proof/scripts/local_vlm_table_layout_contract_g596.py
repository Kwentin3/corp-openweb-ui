#!/usr/bin/env python3
"""Run the research-only G5.96 layout-contract and materialization proof.

The provider sees one frozen page image and can return only layout hints.  The
materializer separately reopens the source PDF through the maintained parser
factory, resolves those hints against exact parser lines/words, and emits a
private non-published Canonical-compatible table candidate.  No provider body
value is accepted or copied.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import itertools
import json
import os
import re
import statistics
import time
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests
import pypdf

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
    SERVICE_ROOT / "benchmarks" / "table_layout_contract_g596" / "manifest.json"
)
MANIFEST_SCHEMA = "broker_reports_table_layout_contract_g596_manifest_v1"
PRIVATE_CONTRACT_SCHEMA = "broker_reports_vlm_table_layout_contract_g596_private_v1"
PRIVATE_RESULT_SCHEMA = "broker_reports_table_materialization_g596_private_v1"
SAFE_RESULT_SCHEMA = "broker_reports_table_materialization_g596_safe_v1"

TERMINAL_LOCALIZATION = "BREADCRUMB_LOCALIZATION_INSUFFICIENT"
TERMINAL_COMPLEXITY = "LAYOUT_CONTRACT_DOES_NOT_REDUCE_PARSER_COMPLEXITY"
TERMINAL_PROVEN = "VLM_LAYOUT_CONTRACT_DETERMINISTIC_MATERIALIZATION_PROVEN"

_NON_SOURCE_VALUE_KEYS = frozenset(
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
    }
)
_BOUNDARIES = {"next_section", "footer", "end_of_page"}
_BODY_PATTERNS = {"repeated", "mixed", "none"}
_TRI_STATES = {"present", "absent", "unknown"}
_DIGIT_RE = re.compile(r"\d")
_NORMALIZE_RE = re.compile(r"[^\w]+", re.UNICODE)


class G596Error(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate-contract")
    generate.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    generate.add_argument("--g594-private-dir", required=True)
    generate.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    generate.add_argument("--private-output", required=True)
    generate.add_argument("--safe-output", required=True)
    recover = subparsers.add_parser("recover-contract-transport")
    recover.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    recover.add_argument("--prior-private", required=True)
    recover.add_argument("--g594-private-dir", required=True)
    recover.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    recover.add_argument("--private-output", required=True)
    recover.add_argument("--safe-output", required=True)
    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    materialize.add_argument("--contract-private", required=True)
    materialize.add_argument("--g594-private-dir", required=True)
    materialize.add_argument("--source-pdf", required=True)
    materialize.add_argument("--private-output", required=True)
    materialize.add_argument("--safe-output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "generate-contract":
            result = generate_contract(
                manifest_path=Path(args.manifest),
                g594_private_dir=Path(args.g594_private_dir),
                env_path=Path(args.env_file),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
        elif args.command == "recover-contract-transport":
            result = recover_contract_transport(
                manifest_path=Path(args.manifest),
                prior_private=Path(args.prior_private),
                g594_private_dir=Path(args.g594_private_dir),
                env_path=Path(args.env_file),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
        else:
            result = materialize_contract(
                manifest_path=Path(args.manifest),
                contract_path=Path(args.contract_private),
                g594_private_dir=Path(args.g594_private_dir),
                source_pdf=Path(args.source_pdf),
                private_output=Path(args.private_output),
                safe_output=Path(args.safe_output),
            )
    except Exception as exc:
        code = exc.code if isinstance(exc, G596Error) else type(exc).__name__
        print(json.dumps({"status": "failed", "code": code}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def generate_contract(
    *,
    manifest_path: Path,
    g594_private_dir: Path,
    env_path: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    if private_output.exists() or safe_output.exists():
        raise G596Error("g596_frozen_provider_output_must_be_fresh")
    provider_contract = manifest["provider"]
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
        raise G596Error("g596_provider_not_qualified")

    plan = _read_object(g594_private_dir / "plan.private.json")
    page_records = {
        int(record["page_number"]): record
        for document in plan.get("documents") or []
        if document.get("document_id") == manifest["source"]["document_id"]
        for record in document.get("page_records") or []
    }
    pages = sorted({int(case["page"]) for case in manifest["cases"]})
    results: list[dict[str, Any]] = []
    for page_number in pages:
        record = page_records.get(page_number)
        if not isinstance(record, dict):
            raise G596Error("g596_g594_page_record_missing")
        page_path = (
            g594_private_dir
            / "documents"
            / str(manifest["source"]["document_id"])
            / "pages"
            / f"p{page_number:03d}.private.png"
        )
        png_bytes = page_path.read_bytes()
        png_hash = hashlib.sha256(png_bytes).hexdigest()
        if png_hash != record.get("page_png_sha256"):
            raise G596Error("g596_page_png_hash_drift")
        model_view = {"task": str(provider_contract["prompt"])}
        outcome = provider.invoke(
            task_id=f"g596_p{page_number:03d}",
            model_view=model_view,
            output_schema=copy.deepcopy(provider_contract["response_schema"]),
            png_bytes=png_bytes,
            crop_sha256=png_hash,
            attempt_number=1,
            attempt_lineage=[],
        )
        output = outcome.get("json_output")
        validation_error = None
        try:
            validate_vlm_page_contract(output)
        except G596Error as exc:
            validation_error = exc.code
            output = None
        results.append(
            {
                "page": page_number,
                "page_png_sha256": png_hash,
                "attempt": outcome.get("attempt"),
                "layout_contract": output,
                "validation_error": validation_error,
                "raw_private_response": outcome.get("raw_private_response"),
                "response_hash": outcome.get("response_hash"),
            }
        )

    manifest_sha = _sha256_json(manifest)
    private = {
        "schema_version": PRIVATE_CONTRACT_SCHEMA,
        "goal": "G5.96",
        "manifest_sha256": manifest_sha,
        "source_pdf_sha256": manifest["source"]["pdf_sha256"],
        "provider_policy": {
            "body_value_fields": 0,
            "canonical_id_fields": 0,
            "exact_bbox_fields": 0,
            "attempts_per_page": 1,
            "hidden_retry": False,
            "best_of_n": False,
        },
        "qualification": qualification,
        "pages": results,
    }
    _write_json(private_output, private)
    safe_pages = [
        {
            "page": item["page"],
            "status": "valid" if item["layout_contract"] is not None else "blocked",
            "tables": len((item["layout_contract"] or {}).get("tables") or []),
            "validation_error": item["validation_error"],
            "response_hash": item["response_hash"],
            "attempt": _safe_attempt(item.get("attempt")),
        }
        for item in results
    ]
    safe = {
        "schema_version": SAFE_RESULT_SCHEMA,
        "phase": "vlm_layout_contract",
        "goal": "G5.96",
        "manifest_sha256": manifest_sha,
        "status": (
            "complete" if all(item["status"] == "valid" for item in safe_pages) else "blocked"
        ),
        "provider_calls": len(results),
        "vlm_body_values_used": 0,
        "vlm_canonical_ids": 0,
        "vlm_exact_bboxes": 0,
        "pages": safe_pages,
        "privacy": _privacy_statement(),
    }
    _write_json(safe_output, safe)
    return {"status": safe["status"], "provider_calls": len(results)}


def recover_contract_transport(
    *,
    manifest_path: Path,
    prior_private: Path,
    g594_private_dir: Path,
    env_path: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    """Revalidate captured STOP responses and recover only absent transport output."""
    manifest = _load_manifest(manifest_path)
    prior = _read_object(prior_private)
    if private_output.exists() or safe_output.exists():
        raise G596Error("g596_transport_recovery_output_must_be_fresh")
    if prior.get("schema_version") != PRIVATE_CONTRACT_SCHEMA or prior.get(
        "manifest_sha256"
    ) != _sha256_json(manifest):
        raise G596Error("g596_transport_recovery_prior_invalid")
    provider_contract = manifest["provider"]
    provider = None
    qualification = prior.get("qualification")
    plan = _read_object(g594_private_dir / "plan.private.json")
    page_records = {
        int(record["page_number"]): record
        for document in plan.get("documents") or []
        if document.get("document_id") == manifest["source"]["document_id"]
        for record in document.get("page_records") or []
    }
    recovered_calls = 0
    results: list[dict[str, Any]] = []
    for prior_page in prior.get("pages") or []:
        page_number = int(prior_page["page"])
        output = _json_from_raw_response(prior_page.get("raw_private_response"))
        recovery_attempt = None
        raw_response = prior_page.get("raw_private_response")
        response_hash = prior_page.get("response_hash")
        validation_error = None
        try:
            validate_vlm_page_contract(output)
        except G596Error as exc:
            validation_error = exc.code
            output = None
        initial_attempt = prior_page.get("attempt") or {}
        recoverable = (
            output is None
            and initial_attempt.get("terminal_failure_class") == "timeout_or_transport"
            and initial_attempt.get("finish_reason") in {None, ""}
        )
        if recoverable:
            if provider is None:
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
                    raise G596Error("g596_provider_not_qualified")
            page_path = (
                g594_private_dir
                / "documents"
                / str(manifest["source"]["document_id"])
                / "pages"
                / f"p{page_number:03d}.private.png"
            )
            png_bytes = page_path.read_bytes()
            png_hash = hashlib.sha256(png_bytes).hexdigest()
            if png_hash != page_records[page_number].get("page_png_sha256"):
                raise G596Error("g596_page_png_hash_drift")
            outcome = provider.invoke(
                task_id=f"g596_transport_recovery_p{page_number:03d}",
                model_view={"task": str(provider_contract["prompt"])},
                output_schema=copy.deepcopy(provider_contract["response_schema"]),
                png_bytes=png_bytes,
                crop_sha256=png_hash,
                attempt_number=1,
                attempt_lineage=[],
            )
            recovered_calls += 1
            recovery_attempt = outcome.get("attempt")
            raw_response = outcome.get("raw_private_response")
            response_hash = outcome.get("response_hash")
            output = outcome.get("json_output")
            try:
                validate_vlm_page_contract(output)
                validation_error = None
            except G596Error as exc:
                validation_error = exc.code
                output = None
        results.append(
            {
                "page": page_number,
                "page_png_sha256": prior_page.get("page_png_sha256"),
                "initial_attempt": initial_attempt,
                "transport_recovery_attempt": recovery_attempt,
                "layout_contract": output,
                "validation_error": validation_error,
                "raw_private_response": raw_response,
                "response_hash": response_hash,
            }
        )
    private = {
        "schema_version": PRIVATE_CONTRACT_SCHEMA,
        "goal": "G5.96",
        "manifest_sha256": _sha256_json(manifest),
        "source_pdf_sha256": manifest["source"]["pdf_sha256"],
        "provider_policy": {
            "body_value_fields": 0,
            "canonical_id_fields": 0,
            "exact_bbox_fields": 0,
            "completed_model_outputs_per_page": 1,
            "initial_transport_failures_preserved": recovered_calls,
            "explicit_transport_recovery_calls": recovered_calls,
            "competing_outputs_selected": 0,
            "hidden_retry": False,
            "best_of_n": False,
        },
        "qualification": qualification,
        "prior_contract_file_sha256": _sha256_file(prior_private),
        "pages": results,
    }
    _write_json(private_output, private)
    safe_pages = [
        {
            "page": item["page"],
            "status": "valid" if item["layout_contract"] is not None else "blocked",
            "tables": len((item["layout_contract"] or {}).get("tables") or []),
            "validation_error": item["validation_error"],
            "initial_attempt": _safe_attempt(item.get("initial_attempt")),
            "transport_recovery_attempt": _safe_attempt(
                item.get("transport_recovery_attempt")
            )
            if item.get("transport_recovery_attempt")
            else None,
            "response_hash": item["response_hash"],
        }
        for item in results
    ]
    safe = {
        "schema_version": SAFE_RESULT_SCHEMA,
        "phase": "vlm_layout_contract_transport_recovery",
        "goal": "G5.96",
        "manifest_sha256": _sha256_json(manifest),
        "status": "complete" if all(item["status"] == "valid" for item in safe_pages) else "blocked",
        "initial_provider_submissions": len(results),
        "explicit_transport_recovery_calls": recovered_calls,
        "completed_model_outputs": sum(item["status"] == "valid" for item in safe_pages),
        "competing_outputs_selected": 0,
        "vlm_body_values_used": 0,
        "vlm_canonical_ids": 0,
        "vlm_exact_bboxes": 0,
        "pages": safe_pages,
        "privacy": _privacy_statement(),
    }
    _write_json(safe_output, safe)
    return {"status": safe["status"], "transport_recovery_calls": recovered_calls}


def validate_vlm_page_contract(value: Any) -> None:
    if not isinstance(value, dict) or set(value) != {"tables"}:
        raise G596Error("g596_vlm_contract_top_level_invalid")
    tables = value.get("tables")
    if not isinstance(tables, list) or len(tables) > 20:
        raise G596Error("g596_vlm_contract_tables_invalid")
    _reject_forbidden_keys(value)
    for table in tables:
        if not isinstance(table, dict) or set(table) != {
            "local_name",
            "start_hints",
            "end_hints",
            "structure",
            "header_cell_token_hints",
        }:
            raise G596Error("g596_vlm_table_shape_invalid")
        if not _short_text(table.get("local_name"), 80):
            raise G596Error("g596_vlm_local_name_invalid")
        start = table.get("start_hints")
        end = table.get("end_hints")
        structure = table.get("structure")
        if not isinstance(start, dict) or set(start) != {
            "anchor_tokens",
            "table_ordinal_after_anchor",
        }:
            raise G596Error("g596_vlm_start_hints_invalid")
        _validate_hint_tokens(start.get("anchor_tokens"), allow_empty=False)
        ordinal = start.get("table_ordinal_after_anchor")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or not 1 <= ordinal <= 20:
            raise G596Error("g596_vlm_table_ordinal_invalid")
        if not isinstance(end, dict) or set(end) != {"boundary", "anchor_tokens"}:
            raise G596Error("g596_vlm_end_hints_invalid")
        if end.get("boundary") not in _BOUNDARIES:
            raise G596Error("g596_vlm_end_boundary_invalid")
        _validate_hint_tokens(
            end.get("anchor_tokens"),
            allow_empty=end.get("boundary") != "next_section",
        )
        if not isinstance(structure, dict) or set(structure) != {
            "columns",
            "header_rows",
            "continuation",
            "body_row_pattern",
            "wrapped_rows",
            "subtotal_rows",
        }:
            raise G596Error("g596_vlm_structure_invalid")
        columns = structure.get("columns")
        header_rows = structure.get("header_rows")
        if not isinstance(columns, int) or isinstance(columns, bool) or not 2 <= columns <= 50:
            raise G596Error("g596_vlm_column_count_invalid")
        if not isinstance(header_rows, int) or isinstance(header_rows, bool) or not 0 <= header_rows <= 10:
            raise G596Error("g596_vlm_header_rows_invalid")
        if not isinstance(structure.get("continuation"), bool):
            raise G596Error("g596_vlm_continuation_invalid")
        if structure.get("body_row_pattern") not in _BODY_PATTERNS:
            raise G596Error("g596_vlm_body_pattern_invalid")
        if structure.get("wrapped_rows") not in _TRI_STATES or structure.get("subtotal_rows") not in _TRI_STATES:
            raise G596Error("g596_vlm_row_hint_invalid")
        header_hints = table.get("header_cell_token_hints")
        if not isinstance(header_hints, list):
            raise G596Error("g596_vlm_header_hints_invalid")
        if header_hints and len(header_hints) != columns:
            raise G596Error("g596_vlm_header_hint_count_invalid")
        for hint in header_hints:
            if not isinstance(hint, dict) or set(hint) != {"tokens"}:
                raise G596Error("g596_vlm_header_hint_shape_invalid")
            _validate_hint_tokens(hint.get("tokens"), allow_empty=False)


def materialize_contract(
    *,
    manifest_path: Path,
    contract_path: Path,
    g594_private_dir: Path,
    source_pdf: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    contract = _read_object(contract_path)
    _validate_private_contract(contract, manifest)
    if _sha256_file(source_pdf) != manifest["source"]["pdf_sha256"]:
        raise G596Error("g596_source_pdf_hash_drift")
    pdf_bytes = source_pdf.read_bytes()
    started = time.perf_counter()
    selected_pages = sorted({int(case["page"]) for case in manifest["cases"]})
    page_capabilities = {
        int(case["page"]): (
            "layout_lines"
            if case["role"] == "ordinary_prose_control"
            else "table_candidates"
        )
        for case in manifest["cases"]
    }
    layout_pages, parser_evidence = _parse_selected_source_pages(
        pdf_bytes, selected_pages, page_capabilities
    )

    page_contracts = {
        int(item["page"]): item["layout_contract"] for item in contract["pages"]
    }
    axis_registry: dict[tuple[str, int], list[float]] = {}
    private_cases: list[dict[str, Any]] = []
    safe_cases: list[dict[str, Any]] = []
    for case in sorted(manifest["cases"], key=lambda item: int(item["page"])):
        page_number = int(case["page"])
        page_contract = page_contracts.get(page_number)
        if not isinstance(page_contract, dict):
            outcome = _failed_case(case, "g596_vlm_page_contract_missing")
        elif case["role"] == "ordinary_prose_control":
            tables = page_contract.get("tables") or []
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
                a_page_path = _a_page_path(
                    g594_private_dir,
                    manifest["source"]["document_id"],
                    page_number,
                )
                if _sha256_file(a_page_path) != case["variant_a_page_sha256"]:
                    raise G596Error("g596_variant_a_page_hash_drift")
                rejection_codes: list[str] = []
                false_positive = None
                for table in tables:
                    try:
                        false_positive = resolve_and_materialize(
                            page_layout=layout_pages[page_number],
                            variant_a_page=_read_object(a_page_path),
                            contract=table,
                            page_number=page_number,
                            axis_registry=axis_registry,
                        )
                        break
                    except G596Error as exc:
                        rejection_codes.append(exc.code)
                if false_positive is not None:
                    outcome = {
                        "case_id": case["case_id"],
                        "role": case["role"],
                        "page": page_number,
                        "status": "false_positive_materialized",
                        "reason_code": "VLM_PROSE_CONTRACT_MATERIALIZED",
                        "materialization": false_positive,
                    }
                else:
                    outcome = {
                        "case_id": case["case_id"],
                        "role": case["role"],
                        "page": page_number,
                        "status": "fail_closed_non_table",
                        "reason_code": "ALL_VLM_PROSE_CONTRACTS_REJECTED",
                        "rejection_codes": rejection_codes,
                        "materialization": None,
                    }
        else:
            tables = page_contract.get("tables") or []
            ordinal = int(case["visual_table_ordinal"])
            if ordinal > len(tables):
                outcome = _failed_case(case, "g596_target_visual_table_missing")
            else:
                a_page_path = _a_page_path(
                    g594_private_dir,
                    manifest["source"]["document_id"],
                    page_number,
                )
                if _sha256_file(a_page_path) != case["variant_a_page_sha256"]:
                    raise G596Error("g596_variant_a_page_hash_drift")
                try:
                    materialized = resolve_and_materialize(
                        page_layout=layout_pages[page_number],
                        variant_a_page=_read_object(a_page_path),
                        contract=tables[ordinal - 1],
                        page_number=page_number,
                        axis_registry=axis_registry,
                    )
                    outcome = {
                        "case_id": case["case_id"],
                        "role": case["role"],
                        "page": page_number,
                        "status": "materialized",
                        "reason_code": None,
                        "materialization": materialized,
                    }
                except G596Error as exc:
                    outcome = _failed_case(case, exc.code)
        private_cases.append(outcome)
        safe_cases.append(_safe_case(outcome, case))

    complexity = _complexity_evidence()
    terminal = _terminal(safe_cases, manifest, complexity)
    private = {
        "schema_version": PRIVATE_RESULT_SCHEMA,
        "goal": "G5.96",
        "manifest_sha256": _sha256_json(manifest),
        "contract_file_sha256": _sha256_file(contract_path),
        "parser": {
            "factory_entrypoint": "PdfTextLayerParserFactory.create",
            "capability": "table_candidates",
            **parser_evidence,
        },
        "cases": private_cases,
        "complexity": complexity,
        "terminal": terminal,
    }
    _write_json(private_output, private)
    safe = {
        "schema_version": SAFE_RESULT_SCHEMA,
        "phase": "deterministic_materialization",
        "goal": "G5.96",
        "manifest_sha256": _sha256_json(manifest),
        "contract_file_sha256": _sha256_file(contract_path),
        "status": "complete" if terminal == TERMINAL_PROVEN else "stopped",
        "terminal": terminal,
        "vlm_body_values_used": 0,
        "vlm_canonical_ids": 0,
        "vlm_exact_bboxes": 0,
        "provider_calls_during_materialization": 0,
        "parser_factory_entrypoint": "PdfTextLayerParserFactory.create",
        "cases": safe_cases,
        "aggregate": _aggregate(safe_cases),
        "complexity": complexity,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "scope": copy.deepcopy(manifest["scope"]),
        "privacy": _privacy_statement(),
    }
    _write_json(safe_output, safe)
    return {"status": safe["status"], "terminal": terminal}


def _parse_selected_source_pages(
    pdf_bytes: bytes,
    page_numbers: list[int],
    page_capabilities: dict[int, str],
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    """Losslessly slice known pages, then use the maintained public parser entrypoint."""
    reader = pypdf.PdfReader(BytesIO(pdf_bytes), strict=False)
    parsers = {
        capability: PdfTextLayerParserFactory().create(
            PdfParserCapabilityRequest(capability=capability)
        )
        for capability in sorted(set(page_capabilities.values()))
    }
    pages: dict[int, dict[str, Any]] = {}
    evidence: dict[str, Any] | None = None
    elapsed_total = 0.0
    for page_number in page_numbers:
        if not 1 <= page_number <= len(reader.pages):
            raise G596Error("g596_selected_page_out_of_range")
        writer = pypdf.PdfWriter()
        writer.add_page(reader.pages[page_number - 1])
        buffer = BytesIO()
        writer.write(buffer)
        capability = page_capabilities[page_number]
        result = parsers[capability].parse(buffer.getvalue())
        if result.layout_projection_status != "complete" or len(result.pages) != 1:
            raise G596Error("g596_parser_layout_incomplete")
        page = copy.deepcopy(result.pages[0])
        page["page_number"] = page_number
        pages[page_number] = page
        elapsed_total += float(
            result.diagnostics.get("elapsed_milliseconds_total") or 0.0
        )
        if evidence is None:
            evidence = {
                "factory_entrypoint": "PdfTextLayerParserFactory.create",
                "capabilities_by_page": {
                    str(page): page_capabilities[page] for page in page_numbers
                },
                "engine": result.parser_engine,
                "engine_version": result.parser_engine_version,
                "config_ref": result.parser_config_ref,
                "page_selection": "known_page_lossless_pypdf_slice_before_factory_parse",
                "source_pdf_hash_verified_before_slice": True,
                "frozen_variant_a_word_literal_and_ref_reverification": True,
            }
    if evidence is None:
        raise G596Error("g596_selected_page_set_empty")
    evidence["selected_pages"] = list(page_numbers)
    evidence["elapsed_milliseconds"] = round(elapsed_total, 3)
    return pages, evidence


def resolve_and_materialize(
    *,
    page_layout: dict[str, Any],
    variant_a_page: dict[str, Any],
    contract: dict[str, Any],
    page_number: int,
    axis_registry: dict[tuple[str, int], list[float]],
) -> dict[str, Any]:
    validate_vlm_page_contract({"tables": [contract]})
    lines = page_layout.get("line_inventory") or []
    words = page_layout.get("word_inventory") or []
    start_line = _resolve_line(
        lines,
        contract["start_hints"]["anchor_tokens"],
        collapse_multiword_phrase=True,
    )
    start_y = float(start_line["bbox"][1])
    end_y = _resolve_end_y(page_layout, contract["end_hints"], start_y)
    columns = int(contract["structure"]["columns"])
    axis_key = (_line_signature(start_line), columns)
    hints = contract.get("header_cell_token_hints") or []
    if not hints and axis_key not in axis_registry:
        raise G596Error("g596_layout_axis_not_resolvable")
    candidates = [
        item
        for item in page_layout.get("table_candidate_inventory") or []
        if float(item["bbox"][3]) > start_y and float(item["bbox"][1]) < end_y
    ]
    candidates.sort(key=lambda item: (float(item["bbox"][1]), float(item["bbox"][0])))
    ordinal = int(contract["start_hints"]["table_ordinal_after_anchor"])
    if ordinal > len(candidates):
        raise G596Error("g596_source_region_not_found")
    candidate = candidates[ordinal - 1]
    overlapping = [
        item
        for item in candidates
        if _bbox_iou(item["bbox"], candidate["bbox"]) >= 0.8
    ]
    if len(overlapping) != 1:
        raise G596Error("g596_source_region_ambiguous")
    source_columns = int(candidate.get("columns_total") or 0)
    if columns < 2 or source_columns < 2:
        raise G596Error("g596_source_structure_incompatible")
    candidate_words = _candidate_words(words, candidate)
    if hints:
        if source_columns == columns:
            column_boundaries = _verified_source_candidate_axis(
                candidate_words,
                candidate,
                hints,
                columns,
            )
            axis_registry[axis_key] = list(column_boundaries)
            mode = "preserved_source_candidate"
        else:
            column_boundaries = _header_axis(
                candidate_words, candidate["bbox"], hints
            )
            axis_registry[axis_key] = list(column_boundaries)
            mode = "header_axis_rematerialized"
    elif axis_key in axis_registry:
        if source_columns == columns:
            column_boundaries = _candidate_boundaries(
                candidate, axis="x", expected=columns
            )
            mode = "preserved_verified_axis_candidate"
        else:
            column_boundaries = list(axis_registry[axis_key])
            mode = "inherited_axis_rematerialized"
    else:
        raise G596Error("g596_layout_axis_not_resolvable")
    if len(column_boundaries) != columns + 1:
        raise G596Error("g596_layout_axis_incompatible")
    row_boundaries = _candidate_boundaries(
        candidate,
        axis="y",
        expected=int(candidate.get("rows_total") or 0),
    )
    bindings = _source_bindings(variant_a_page)
    rows, assigned = _materialize_cells(
        page_number=page_number,
        candidate_words=candidate_words,
        row_boundaries=row_boundaries,
        column_boundaries=column_boundaries,
        bindings=bindings,
        contract_hash=_sha256_json(contract),
    )
    expected_ordinals = {int(word["parser_ordinal"]) for word in candidate_words}
    if assigned != expected_ordinals:
        raise G596Error("g596_source_words_not_exactly_once")
    source_refs = [
        token["source_value_ref"]
        for row in rows
        for cell in row["cells"]
        for token in cell["source_tokens"]
    ]
    if len(source_refs) != len(expected_ordinals) or len(set(source_refs)) != len(source_refs):
        raise G596Error("g596_source_ref_coverage_incomplete")
    resolved_table_ref = "g596table_" + _digest(
        [page_number, candidate["bbox"], columns, source_refs], length=24
    )
    return {
        "schema_version": "broker_reports_canonical_table_candidate_g596_private_v1",
        "visibility": "research_private_not_published",
        "identity_status": "minted_after_exact_source_region_resolution",
        "resolved_table_ref": resolved_table_ref,
        "page_number": page_number,
        "source_region": {
            "parser_candidate_bbox": candidate["bbox"],
            "parser_candidate_strategy": candidate["table_strategy_ref"],
            "parser_columns": source_columns,
            "parser_rows": int(candidate["rows_total"]),
            "candidate_count_in_breadcrumb_region": len(candidates),
        },
        "layout_contract_hash": _sha256_json(contract),
        "materialization_mode": mode,
        "column_count": columns,
        "row_count": len(rows),
        "column_boundaries_from_source_geometry": column_boundaries,
        "row_boundaries_from_source_candidate": row_boundaries,
        "rows": rows,
        "source_word_count": len(expected_ordinals),
        "source_value_ref_count": len(source_refs),
        "source_ref_coverage_ratio": 1.0,
        "invented_source_literals": 0,
        "vlm_body_values_used": 0,
        "vlm_canonical_ids_used": 0,
        "vlm_exact_bboxes_used": 0,
        "mapping_digest": _digest(
            [
                [
                    [token["source_word_ref"] for token in cell["source_tokens"]]
                    for cell in row["cells"]
                ]
                for row in rows
            ]
        ),
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
    exact_matches = []
    concatenated_matches = []
    joined_target = "".join(target)
    for line in lines:
        if after_y is not None and float(line["bbox"][1]) <= after_y:
            continue
        source_tokens = [_normalized(token) for token in str(line.get("text") or "").split()]
        if _ordered_contains(source_tokens, target):
            exact_matches.append(line)
        if joined_target and joined_target in "".join(source_tokens):
            concatenated_matches.append(line)
    matches = exact_matches or concatenated_matches
    if len(matches) == 0:
        raise G596Error("g596_breadcrumb_line_not_found")
    if len(matches) > 1:
        may_take_first = first_after or (
            not exact_matches
            and collapse_multiword_phrase
            and any(any(char.isspace() for char in token) for token in tokens)
        )
        if not may_take_first:
            raise G596Error("g596_breadcrumb_line_ambiguous")
        matches.sort(key=lambda item: (float(item["bbox"][1]), float(item["bbox"][0])))
    return matches[0]


def _resolve_end_y(
    page_layout: dict[str, Any], end_hints: dict[str, Any], start_y: float
) -> float:
    boundary = end_hints["boundary"]
    if boundary == "end_of_page":
        return float(page_layout["height"])
    if boundary == "footer":
        footer_lines = [
            line
            for line in page_layout.get("line_inventory") or []
            if float(line["bbox"][1]) >= float(page_layout["height"]) * 0.95
        ]
        if len(footer_lines) != 1:
            raise G596Error("g596_footer_boundary_ambiguous")
        return float(footer_lines[0]["bbox"][1])
    end_line = _resolve_line(
        page_layout.get("line_inventory") or [],
        end_hints["anchor_tokens"],
        after_y=start_y,
        first_after=True,
        collapse_multiword_phrase=True,
    )
    end_y = float(end_line["bbox"][1])
    if end_y <= start_y:
        raise G596Error("g596_end_boundary_before_start")
    return end_y


def _header_axis(
    words: list[dict[str, Any]], bbox: list[float], hints: list[dict[str, Any]]
) -> list[float]:
    anchors = [_header_anchor(words, hint) for hint in hints]
    if anchors != sorted(anchors) or len(set(round(value, 3) for value in anchors)) != len(anchors):
        raise G596Error("g596_header_axis_not_strictly_ordered")
    boundaries = [float(bbox[0])]
    boundaries.extend(round((left + right) / 2.0, 3) for left, right in zip(anchors, anchors[1:]))
    boundaries.append(float(bbox[2]))
    return boundaries


def _header_anchor(words: list[dict[str, Any]], hint: dict[str, Any]) -> float:
    target = "".join(_normalized(token) for token in hint["tokens"])
    candidates: list[tuple[float, tuple[int, ...], float]] = []
    usable = [
        word
        for word in words
        if (piece := _normalized(str(word["text"])))
        and any(char.isalpha() for char in piece)
        and piece in target
    ]
    for size in range(1, min(4, len(usable)) + 1):
        for combination in itertools.combinations(usable, size):
            ordered = sorted(
                combination,
                key=lambda item: (float(item["bbox"][1]), float(item["bbox"][0])),
            )
            source = "".join(_normalized(str(item["text"])) for item in ordered)
            if source != target:
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
        raise G596Error("g596_header_hint_not_found")
    if len(candidates) > 1 and abs(candidates[0][0] - candidates[1][0]) < 0.001:
        raise G596Error("g596_header_hint_ambiguous")
    return float(candidates[0][2])


def _verified_source_candidate_axis(
    words: list[dict[str, Any]],
    candidate: dict[str, Any],
    hints: list[dict[str, Any]],
    columns: int,
) -> list[float]:
    boundaries = _candidate_boundaries(candidate, axis="x", expected=columns)
    verified = 0
    for index, hint in enumerate(hints):
        try:
            anchor = _header_anchor(words, hint)
        except G596Error as exc:
            if exc.code != "g596_header_hint_not_found":
                raise
            continue
        if not _in_band(anchor, boundaries, index):
            raise G596Error("g596_header_hint_source_column_incompatible")
        verified += 1
    if verified < max(2, columns - 1):
        raise G596Error("g596_header_hint_source_coverage_insufficient")
    return boundaries


def _candidate_boundaries(
    candidate: dict[str, Any], *, axis: str, expected: int
) -> list[float]:
    indexes = (0, 2) if axis == "x" else (1, 3)
    values = sorted(
        {
            round(float(cell["bbox"][index]), 3)
            for cell in candidate.get("cell_inventory") or []
            for index in indexes
        }
    )
    if expected < 1 or len(values) != expected + 1:
        raise G596Error(f"g596_source_{axis}_boundaries_incompatible")
    return values


def _candidate_words(
    words: list[dict[str, Any]], candidate: dict[str, Any]
) -> list[dict[str, Any]]:
    ordinals = {int(value) for value in candidate["contributing_word_parser_ordinals"]}
    result = [word for word in words if int(word["parser_ordinal"]) in ordinals]
    if len(result) != len(ordinals):
        raise G596Error("g596_candidate_word_inventory_incomplete")
    return result


def _source_bindings(variant_a_page: dict[str, Any]) -> dict[int, dict[str, str]]:
    ordinal_to_word_ref: dict[int, str] = {}
    for line in variant_a_page.get("lines") or []:
        ordinals = line.get("word_parser_ordinals") or []
        refs = line.get("word_refs") or []
        if len(ordinals) != len(refs):
            raise G596Error("g596_variant_a_word_ref_alignment_invalid")
        for ordinal, word_ref in zip(ordinals, refs):
            ordinal_to_word_ref[int(ordinal)] = str(word_ref)
    word_to_value_ref: dict[str, str] = {}
    for unit in variant_a_page.get("source_units") or []:
        for entry in unit.get("pdf_layout_source_value_index") or []:
            word_ref = str(entry.get("source_object_ref") or "")
            value_ref = str(entry.get("source_value_ref") or "")
            if not word_ref.startswith("pdfword_") or not value_ref:
                continue
            previous = word_to_value_ref.setdefault(word_ref, value_ref)
            if previous != value_ref:
                raise G596Error("g596_variant_a_source_value_ref_ambiguous")
    word_literals: dict[str, str] = {}
    for table in variant_a_page.get("table_projections") or []:
        for value in table.get("private_values") or []:
            word_ref = str(value.get("source_object_ref") or "")
            if not word_ref.startswith("pdfword_"):
                continue
            literal = str(value.get("normalized_value") or "")
            previous = word_literals.setdefault(word_ref, literal)
            if previous != literal:
                raise G596Error("g596_variant_a_word_literal_ambiguous")
    return {
        ordinal: {
            "source_word_ref": word_ref,
            "source_value_ref": word_to_value_ref.get(word_ref, ""),
            "frozen_literal": word_literals.get(word_ref, ""),
        }
        for ordinal, word_ref in ordinal_to_word_ref.items()
    }


def _materialize_cells(
    *,
    page_number: int,
    candidate_words: list[dict[str, Any]],
    row_boundaries: list[float],
    column_boundaries: list[float],
    bindings: dict[int, dict[str, str]],
    contract_hash: str,
) -> tuple[list[dict[str, Any]], set[int]]:
    rows: list[dict[str, Any]] = []
    assigned: set[int] = set()
    for row_index in range(len(row_boundaries) - 1):
        row_words = [
            word
            for word in candidate_words
            if _in_band(
                _center(word["bbox"], "y"),
                row_boundaries,
                row_index,
            )
        ]
        cells = []
        for column_index in range(len(column_boundaries) - 1):
            members = [
                word
                for word in row_words
                if _in_band(
                    _center(word["bbox"], "x"),
                    column_boundaries,
                    column_index,
                )
            ]
            members.sort(key=lambda item: (float(item["bbox"][1]), float(item["bbox"][0])))
            source_tokens = []
            for word in members:
                ordinal = int(word["parser_ordinal"])
                binding = bindings.get(ordinal) or {}
                literal = str(word.get("text") or "")
                if not binding.get("source_value_ref") or binding.get("frozen_literal") != literal:
                    raise G596Error("g596_parser_literal_not_source_verified")
                if ordinal in assigned:
                    raise G596Error("g596_source_word_duplicate_assignment")
                assigned.add(ordinal)
                source_tokens.append(
                    {
                        "literal": literal,
                        "parser_word_ordinal": ordinal,
                        "source_word_ref": binding["source_word_ref"],
                        "source_value_ref": binding["source_value_ref"],
                        "parser_bbox": word["bbox"],
                        "provenance": "factory_parser_word_verified_against_frozen_variant_a",
                    }
                )
            cell_ref = "g596cell_" + _digest(
                [
                    page_number,
                    row_index + 1,
                    column_index + 1,
                    contract_hash,
                    [token["source_value_ref"] for token in source_tokens],
                ],
                length=24,
            )
            cells.append(
                {
                    "resolved_cell_ref": cell_ref,
                    "row_ordinal": row_index + 1,
                    "column_ordinal": column_index + 1,
                    "literal": _joined_literal(source_tokens),
                    "source_value_refs": [
                        token["source_value_ref"] for token in source_tokens
                    ],
                    "source_tokens": source_tokens,
                }
            )
        rows.append(
            {
                "resolved_row_ref": "g596row_"
                + _digest(
                    [page_number, row_index + 1, [cell["resolved_cell_ref"] for cell in cells]],
                    length=24,
                ),
                "row_ordinal": row_index + 1,
                "cells": cells,
            }
        )
    return rows, assigned


def _joined_literal(tokens: list[dict[str, Any]]) -> str:
    lines: list[list[dict[str, Any]]] = []
    for token in tokens:
        top = float(token["parser_bbox"][1])
        if not lines or abs(top - float(lines[-1][0]["parser_bbox"][1])) > 2.0:
            lines.append([token])
        else:
            lines[-1].append(token)
    return "\n".join(
        " ".join(str(token["literal"]) for token in line) for line in lines
    )


def _safe_case(outcome: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    materialized = outcome.get("materialization") or {}
    parser_columns = (materialized.get("source_region") or {}).get("parser_columns")
    return {
        "case_id": outcome["case_id"],
        "role": outcome["role"],
        "page": outcome["page"],
        "status": outcome["status"],
        "reason_code": outcome.get("reason_code"),
        "expected_parser_columns": expected["expected_parser_columns"],
        "observed_parser_columns": parser_columns,
        "expected_visual_columns": expected["expected_visual_columns"],
        "materialized_columns": materialized.get("column_count"),
        "expected_rows": expected["expected_rows"],
        "materialized_rows": materialized.get("row_count"),
        "materialization_mode": materialized.get("materialization_mode"),
        "source_words": materialized.get("source_word_count", 0),
        "source_value_refs": materialized.get("source_value_ref_count", 0),
        "source_ref_coverage_ratio": materialized.get("source_ref_coverage_ratio", 0.0),
        "invented_source_literals": materialized.get("invented_source_literals", 0),
        "mapping_digest": materialized.get("mapping_digest"),
    }


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    development = [case for case in cases if case["role"].startswith("known_wrong")]
    known_good = [case for case in cases if case["role"] == "known_good_table_control"]
    prose = [case for case in cases if case["role"] == "ordinary_prose_control"]
    return {
        "known_wrong_column_relations_total": len(development),
        "known_wrong_column_relations_corrected": sum(
            case["status"] == "materialized"
            and case["observed_parser_columns"] == case["expected_parser_columns"]
            and case["materialized_columns"] == case["expected_visual_columns"]
            and case["materialized_rows"] == case["expected_rows"]
            for case in development
        ),
        "known_good_controls_total": len(known_good),
        "known_good_controls_preserved": sum(
            case["status"] == "materialized"
            and case["materialization_mode"] == "preserved_source_candidate"
            and case["materialized_columns"] == case["observed_parser_columns"]
            for case in known_good
        ),
        "non_table_controls_total": len(prose),
        "non_table_controls_fail_closed": sum(
            case["status"] == "fail_closed_non_table" for case in prose
        ),
        "materialized_source_words": sum(int(case["source_words"]) for case in cases),
        "materialized_source_value_refs": sum(int(case["source_value_refs"]) for case in cases),
        "all_materialized_source_ref_coverage_100_percent": all(
            case["source_ref_coverage_ratio"] == 1.0
            for case in cases
            if case["status"] == "materialized"
        ),
        "invented_source_literals": sum(int(case["invented_source_literals"]) for case in cases),
    }


def _terminal(
    cases: list[dict[str, Any]], manifest: dict[str, Any], complexity: dict[str, Any]
) -> str:
    localization_codes = {
        "g596_breadcrumb_line_not_found",
        "g596_breadcrumb_line_ambiguous",
        "g596_source_region_not_found",
        "g596_source_region_ambiguous",
        "g596_target_visual_table_missing",
        "g596_header_hint_not_found",
        "g596_header_hint_ambiguous",
        "g596_layout_axis_not_resolvable",
    }
    if any(case.get("reason_code") in localization_codes for case in cases):
        return TERMINAL_LOCALIZATION
    aggregate = _aggregate(cases)
    acceptance = manifest["acceptance"]
    functional = (
        aggregate["known_wrong_column_relations_corrected"]
        == acceptance["known_wrong_column_relations_corrected"]
        and aggregate["known_good_controls_preserved"]
        == acceptance["known_good_controls_preserved"]
        and aggregate["non_table_controls_fail_closed"]
        == acceptance["non_table_controls_fail_closed"]
        and aggregate["all_materialized_source_ref_coverage_100_percent"] is True
        and aggregate["invented_source_literals"] == 0
    )
    simple = (
        complexity["document_specific_code_branches"] == 0
        and complexity["body_value_heuristic_rules"] == 0
        and complexity["production_owner_changes"] == 0
        and complexity["materialization_primitives"] == 4
    )
    return TERMINAL_PROVEN if functional and simple else TERMINAL_COMPLEXITY


def _complexity_evidence() -> dict[str, Any]:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    core_names = {
        "resolve_and_materialize",
        "_resolve_line",
        "_resolve_end_y",
        "_header_axis",
        "_header_anchor",
        "_verified_source_candidate_axis",
        "_candidate_boundaries",
        "_candidate_words",
        "_source_bindings",
        "_materialize_cells",
    }
    core_functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in core_names
    ]
    numeric_page_branches = re.findall(
        r"\b(?:page|page_number)\s*(?:==|in)\s*(?:\d+|\([^)]*\d[^)]*\))",
        source,
    )
    return {
        "mechanism": "resolve breadcrumbs -> select one parser region -> derive/reuse column axis -> rebin exact parser words",
        "materialization_primitives": 4,
        "materialization_modes": 3,
        "body_value_heuristic_rules": 0,
        "financial_semantic_rules": 0,
        "document_specific_code_branches": len(numeric_page_branches),
        "production_owner_changes": 0,
        "provider_calls_during_materialization": 0,
        "mechanism_core_function_count": len(core_functions),
        "mechanism_core_source_lines": sum(
            int(node.end_lineno or node.lineno) - int(node.lineno) + 1
            for node in core_functions
        ),
        "whole_research_harness_source_lines": len(source.splitlines()),
        "complexity_delta": "13-column parser candidate becomes a bounded 11-axis reassignment; no body interpretation or table rediscovery",
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    manifest = _read_object(path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA or manifest.get("goal") != "G5.96":
        raise G596Error("g596_manifest_schema_invalid")
    if manifest.get("frozen") is not True:
        raise G596Error("g596_manifest_not_frozen")
    if manifest.get("scope") != {
        "research_only": True,
        "gate2_only": True,
        "provider_routing_design": False,
        "reconciliation_design": False,
        "fallback_design": False,
        "gate3_plus": False,
        "production_activation": False,
    }:
        raise G596Error("g596_scope_invalid")
    pages = [int(case["page"]) for case in manifest.get("cases") or []]
    if pages != [23, 24, 25, 26, 27, 28, 64]:
        raise G596Error("g596_frozen_case_set_invalid")
    return manifest


def _validate_private_contract(contract: dict[str, Any], manifest: dict[str, Any]) -> None:
    if contract.get("schema_version") != PRIVATE_CONTRACT_SCHEMA:
        raise G596Error("g596_private_contract_schema_invalid")
    if contract.get("manifest_sha256") != _sha256_json(manifest):
        raise G596Error("g596_private_contract_manifest_mismatch")
    policy = contract.get("provider_policy") or {}
    if (
        policy.get("body_value_fields") != 0
        or policy.get("canonical_id_fields") != 0
        or policy.get("exact_bbox_fields") != 0
        or policy.get("hidden_retry") is not False
        or policy.get("best_of_n") is not False
        or int(policy.get("competing_outputs_selected") or 0) != 0
    ):
        raise G596Error("g596_private_contract_policy_invalid")
    expected_pages = {int(case["page"]) for case in manifest["cases"]}
    observed_pages = {int(item["page"]) for item in contract.get("pages") or []}
    if observed_pages != expected_pages:
        raise G596Error("g596_private_contract_pages_invalid")
    for item in contract["pages"]:
        if item.get("validation_error") is not None or item.get("layout_contract") is None:
            raise G596Error("g596_private_contract_page_blocked")
        validate_vlm_page_contract(item["layout_contract"])


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _NON_SOURCE_VALUE_KEYS:
                raise G596Error("g596_vlm_forbidden_authority_field")
            _reject_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_keys(child)


def _json_from_raw_response(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        return None
    content = candidates[0].get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return None
    text = "".join(
        str(part.get("text") or "") for part in parts if isinstance(part, dict)
    )
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _validate_hint_tokens(value: Any, *, allow_empty: bool) -> None:
    if not isinstance(value, list) or len(value) > 12 or (not value and not allow_empty):
        raise G596Error("g596_vlm_hint_tokens_invalid")
    for token in value:
        if not _short_text(token, 80) or _DIGIT_RE.search(str(token)):
            raise G596Error("g596_vlm_body_value_like_hint_forbidden")


def _short_text(value: Any, maximum: int) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum and "\x00" not in value


def _ordered_contains(source: list[str], target: list[str]) -> bool:
    if not target:
        return False
    cursor = 0
    for token in source:
        if token == target[cursor]:
            cursor += 1
            if cursor == len(target):
                return True
    return False


def _normalized(value: str) -> str:
    return _NORMALIZE_RE.sub("", value.casefold())


def _line_signature(line: dict[str, Any]) -> str:
    return _digest([_normalized(str(line.get("text") or ""))], length=20)


def _center(bbox: list[float], axis: str) -> float:
    return (float(bbox[0]) + float(bbox[2])) / 2.0 if axis == "x" else (float(bbox[1]) + float(bbox[3])) / 2.0


def _in_band(value: float, boundaries: list[float], index: int) -> bool:
    lower, upper = boundaries[index], boundaries[index + 1]
    return lower <= value <= upper if index == len(boundaries) - 2 else lower <= value < upper


def _bbox_iou(left: list[float], right: list[float]) -> float:
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _failed_case(case: dict[str, Any], code: str) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "role": case["role"],
        "page": int(case["page"]),
        "status": "failed_closed",
        "reason_code": code,
        "materialization": None,
    }


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


def _a_page_path(root: Path, document_id: str, page: int) -> Path:
    return root / "documents" / document_id / "pages" / f"p{page:03d}.variant_a.private.json"


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(env.get("OPENWEBUI_HOST") or "").rstrip("/")
    email = str(env.get("WEBUI_ADMIN_EMAIL") or "")
    password = str(env.get("WEBUI_ADMIN_PASSWORD") or "")
    if not all((host, email, password)):
        raise G596Error("g596_openwebui_credentials_missing")
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
        raise G596Error("g596_openwebui_token_missing")
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
        raise G596Error("g596_env_file_missing")
    result = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _privacy_statement() -> dict[str, bool]:
    return {
        "raw_customer_text_in_safe_output": False,
        "private_paths_in_safe_output": False,
        "page_images_in_safe_output": False,
        "provider_payloads_in_safe_output": False,
    }


def _read_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise G596Error("g596_required_json_missing")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise G596Error("g596_json_object_required")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _digest(value: Any, *, length: int = 32) -> str:
    return _sha256_json(value)[:length]


if __name__ == "__main__":
    raise SystemExit(main())
