#!/usr/bin/env python3
"""Run the frozen G5.94 deterministic-parser vs whole-page-VLM research trial.

Private PDF bytes, page renders, Variant A payloads and VLM responses stay under
the caller-selected local output directory.  The tracked manifest contains only
the frozen contract, source hashes and page ordinals.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fitz
import requests

from broker_reports_gate1 import FileInput, Gate1Normalizer
from broker_reports_gate1.pdf_grid_experiment_provider import (
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from broker_reports_gate1.pdf_table_raster import (
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)


SCRIPT_PATH = Path(__file__).resolve()
SERVICE_ROOT = SCRIPT_PATH.parent.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "pdf_ingestion_ab_g594" / "manifest.json"
)
MANIFEST_SCHEMA = "broker_reports_pdf_ingestion_ab_g594_manifest_v1"
PLAN_SCHEMA = "broker_reports_pdf_ingestion_ab_g594_plan_private_v1"
REVIEW_SCHEMA = "broker_reports_pdf_ingestion_ab_g594_review_private_v1"
REVIEW_DECISIONS_SCHEMA = (
    "broker_reports_pdf_ingestion_ab_g594_review_decisions_private_v1"
)
SAFE_SCHEMA = "broker_reports_pdf_ingestion_ab_g594_safe_v1"

ERROR_FIELDS = (
    "lost_text_segments",
    "invented_text_segments",
    "changed_literals",
    "lost_signs",
    "changed_decimal_separators",
    "distorted_dates",
    "changed_currency_symbols",
    "lost_rows",
    "invented_rows",
    "duplicated_rows",
    "merged_rows",
    "split_rows",
    "lost_column_relations",
    "incorrect_headers",
    "lost_tables",
    "false_tables",
    "broken_order",
)


class G594Error(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    _common_arguments(prepare)
    execute = subparsers.add_parser("execute")
    _common_arguments(execute)
    execute.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    score = subparsers.add_parser("score")
    _common_arguments(score)
    score.add_argument("--review-decisions")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = prepare_run(args)
        elif args.command == "execute":
            result = execute_run(args)
        else:
            result = score_run(args)
    except Exception as exc:
        code = exc.code if isinstance(exc, G594Error) else type(exc).__name__
        print(json.dumps({"status": "failed", "code": code}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--corpus-root", required=True)
    parser.add_argument("--output-dir", required=True)


def prepare_run(args: argparse.Namespace) -> dict[str, Any]:
    manifest_path = Path(args.manifest).resolve()
    corpus_root = Path(args.corpus_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise G594Error("g594_fresh_output_directory_required")
    output_dir.mkdir(parents=True, exist_ok=True)
    private_dir = output_dir / "private"
    private_dir.mkdir()

    manifest = _load_manifest(manifest_path)
    _verify_variant_a_hashes(manifest)
    sources = _find_sources(manifest, corpus_root)
    renderer = PdfTableRasterFactory(PdfTableRasterConfig(padding_points=0)).create()

    started = time.perf_counter()
    documents: list[dict[str, Any]] = []
    pages_total = 0
    ready_tables = 0
    blocked_tables = 0
    addressability = {
        "lines_total": 0,
        "lines_with_page_source_and_bbox_refs": 0,
        "cells_total": 0,
        "cells_with_source_paths": 0,
    }
    for declared in manifest["corpus"]["documents"]:
        document_id = str(declared["document_id"])
        source = sources[document_id]
        pdf_bytes = source.read_bytes()
        document_started = time.perf_counter()
        normalized = _normalize_document(document_id, source, pdf_bytes)
        normalization_ms = round((time.perf_counter() - document_started) * 1000)
        document_dir = private_dir / "documents" / document_id
        page_dir = document_dir / "pages"
        page_dir.mkdir(parents=True)
        page_records, table_counts, page_addressability = _persist_a_pages(
            document_id=document_id,
            declared=declared,
            normalized=normalized,
            pdf_bytes=pdf_bytes,
            renderer=renderer,
            page_dir=page_dir,
        )
        pages_total += len(page_records)
        ready_tables += table_counts["ready"]
        blocked_tables += table_counts["blocked"]
        for key, value in page_addressability.items():
            addressability[key] += value
        documents.append(
            {
                "document_id": document_id,
                "pdf_sha256": declared["pdf_sha256"],
                "pages": len(page_records),
                "normalization_duration_ms": normalization_ms,
                "page_records": page_records,
            }
        )

    if pages_total != int(manifest["corpus"]["pages_total"]):
        raise G594Error("g594_prepared_page_count_mismatch")
    slots = _build_slots(manifest)
    plan = {
        "schema_version": PLAN_SCHEMA,
        "manifest_sha256": _sha256_json(manifest),
        "variant_a_source_hashes": copy.deepcopy(
            manifest["variant_a"]["source_hashes"]
        ),
        "documents": documents,
        "slots": slots,
        "variant_a": {
            "duration_ms": round((time.perf_counter() - started) * 1000),
            "documents": len(documents),
            "pages": pages_total,
            "ready_tables": ready_tables,
            "blocked_tables": blocked_tables,
            "addressability": addressability,
        },
    }
    _write_json(private_dir / "plan.private.json", plan)
    review = _review_template(manifest)
    _write_json(private_dir / "review.private.json", review)
    safe = {
        "schema_version": SAFE_SCHEMA,
        "phase": "prepared",
        "manifest_sha256": plan["manifest_sha256"],
        "variant_a": plan["variant_a"],
        "variant_b": {
            "primary_slots": sum(item["run_ordinal"] == 1 for item in slots),
            "repeat_slots": sum(item["run_ordinal"] == 2 for item in slots),
            "provider_calls": 0,
        },
        "privacy": _privacy_statement(),
    }
    _write_json(output_dir / "prepare.safe.json", safe)
    return {
        "status": "prepared",
        "pages": pages_total,
        "slots": len(slots),
        "manifest_sha256": plan["manifest_sha256"],
    }


def execute_run(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _load_manifest(Path(args.manifest).resolve())
    output_dir = Path(args.output_dir).resolve()
    private_dir = output_dir / "private"
    plan = _read_object(private_dir / "plan.private.json")
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise G594Error("g594_plan_invalid")
    if plan.get("manifest_sha256") != _sha256_json(manifest):
        raise G594Error("g594_manifest_changed_after_prepare")
    _verify_variant_a_hashes(manifest)

    b_contract = manifest["variant_b"]
    provider = PdfGridExperimentProviderFactory(
        PdfGridProviderConfig(
            provider_profile=str(b_contract["provider_profile"]),
            model_id=str(b_contract["model_id"]),
            timeout_seconds=240,
            maximum_output_tokens=int(b_contract["maximum_output_tokens"]),
            maximum_counted_input_tokens=int(
                b_contract["maximum_counted_input_tokens"]
            ),
            thinking_level=str(b_contract["thinking_level"]),
        )
    ).create_for_openwebui(_openwebui_request(Path(args.env_file).resolve()))
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise G594Error("g594_provider_not_qualified")

    slot_dir = private_dir / "variant_b_slots"
    slot_dir.mkdir(exist_ok=True)
    started = time.perf_counter()
    submitted = 0
    skipped_terminal = 0
    interrupted_claims = 0
    for slot in plan["slots"]:
        slot_id = str(slot["slot_id"])
        file_stem = _slot_file_stem(slot_id)
        claim_path = slot_dir / f"{file_stem}.claim.private.json"
        private_path = slot_dir / f"{file_stem}.result.private.json"
        safe_path = slot_dir / f"{file_stem}.result.safe.json"
        if private_path.is_file() and safe_path.is_file():
            skipped_terminal += 1
            continue
        try:
            descriptor = os.open(
                claim_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            interrupted_claims += 1
            continue
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(
                {
                    "slot_id": slot_id,
                    "manifest_sha256": plan["manifest_sha256"],
                    "resubmission_forbidden": True,
                },
                handle,
                sort_keys=True,
            )
            handle.flush()
            os.fsync(handle.fileno())
        submitted += 1
        page_path = (
            private_dir
            / "documents"
            / str(slot["document_id"])
            / "pages"
            / f"p{int(slot['page_number']):03d}.private.png"
        )
        png_bytes = page_path.read_bytes()
        png_sha256 = hashlib.sha256(png_bytes).hexdigest()
        model_view = _variant_b_model_view(manifest)
        outcome = provider.invoke(
            task_id=slot_id,
            model_view=model_view,
            output_schema=copy.deepcopy(b_contract["response_schema"]),
            png_bytes=png_bytes,
            crop_sha256=png_sha256,
            attempt_number=1,
            attempt_lineage=[],
        )
        markdown, validation_error = _validated_markdown(outcome.get("json_output"))
        private_result = {
            "slot": slot,
            "page_png_sha256": png_sha256,
            "model_view": model_view,
            "attempt": outcome.get("attempt"),
            "markdown": markdown,
            "validation_error": validation_error,
            "raw_private_response": outcome.get("raw_private_response"),
            "response_hash": outcome.get("response_hash"),
        }
        _write_json(private_path, private_result)
        safe_result = _safe_slot_result(
            slot=slot,
            outcome=outcome,
            markdown=markdown,
            validation_error=validation_error,
        )
        _write_json(safe_path, safe_result)

    safe_results = [
        _read_object(path)
        for path in sorted(slot_dir.glob("*.result.safe.json"))
    ]
    terminal = _execution_summary(
        manifest=manifest,
        plan=plan,
        qualification=qualification,
        results=safe_results,
        duration_ms=round((time.perf_counter() - started) * 1000),
        submitted=submitted,
        skipped_terminal=skipped_terminal,
        interrupted_claims=interrupted_claims,
    )
    _write_json(output_dir / "execution.safe.json", terminal)
    return {
        "status": terminal["status"],
        "submitted": submitted,
        "terminal_slots": len(safe_results),
        "interrupted_claims": interrupted_claims,
    }


def score_run(args: argparse.Namespace) -> dict[str, Any]:
    manifest = _load_manifest(Path(args.manifest).resolve())
    output_dir = Path(args.output_dir).resolve()
    private_dir = output_dir / "private"
    plan = _read_object(private_dir / "plan.private.json")
    review = _read_object(private_dir / "review.private.json")
    if args.review_decisions:
        review = _materialize_review(
            review,
            _read_object(Path(args.review_decisions).resolve()),
        )
        _write_json(private_dir / "review.scored.private.json", review)
    if plan.get("manifest_sha256") != _sha256_json(manifest):
        raise G594Error("g594_score_manifest_mismatch")
    _validate_review(review, manifest)
    execution = _read_object(output_dir / "execution.safe.json")
    primary_economics = _primary_economics(
        plan=plan,
        private_dir=private_dir,
        pricing=manifest["variant_b"]["pricing"],
    )
    aggregates = {
        split: {
            arm: _aggregate_review(review, split, arm)
            for arm in ("A", "B")
        }
        for split in ("development", "holdout", "all")
    }
    recommendation = str(review.get("recommendation") or "")
    allowed = {
        "VARIANT_A_WINS",
        "VARIANT_B_WINS",
        "HYBRID_JUSTIFIED",
        "INCONCLUSIVE",
    }
    if recommendation not in allowed:
        raise G594Error("g594_recommendation_missing_or_invalid")
    safe = {
        "schema_version": SAFE_SCHEMA,
        "phase": "scored",
        "status": "complete",
        "goal": "G5.94",
        "manifest_sha256": plan["manifest_sha256"],
        "corpus": {
            "documents": 4,
            "pages_executed": 103,
            "pages_visually_scored": len(review["pages"]),
            "development_pages": aggregates["development"]["A"]["pages"],
            "holdout_pages": aggregates["holdout"]["A"]["pages"],
        },
        "variant_a": {
            **copy.deepcopy(plan["variant_a"]),
            "maintenance_complexity": {
                "table_strategies": 2,
                "rejection_classes": 11,
                "named_thresholds": 14,
                "local_numeric_or_ratio_decisions_approx": 23,
                "threshold_or_ratio_knobs_order_approx": 37,
                "direct_parser_tests": 25,
                "known_structural_debt_classes": 4,
            },
        },
        "variant_b": {
            "execution": execution,
            "primary_economics": primary_economics,
            "maintenance_complexity": {
                "new_product_runtime_modules": 0,
                "research_coordinator_scripts": 1,
                "prompt_contracts": 1,
                "response_fields": 1,
                "markdown_validation_rules": 4,
                "provider_specific_compatibility_owners_added": 0,
                "observed_failure_classes": 6,
            },
            "addressability": {
                "page_identity": True,
                "markdown_line_identity": True,
                "source_coordinate_identity": False,
                "source_cell_identity": False,
            },
        },
        "fidelity": aggregates,
        "recommendation": recommendation,
        "recommendation_basis": str(review.get("recommendation_basis") or ""),
        "scope": {
            "parser_changes": 0,
            "gate3_plus_changes": 0,
            "semantic_vlm_work": 0,
            "production_activation": False,
            "best_of_n": False,
            "retry": False,
            "ensemble": False,
        },
        "privacy": _privacy_statement(),
    }
    _write_json(output_dir / "comparison.safe.json", safe)
    return {
        "status": "scored",
        "recommendation": recommendation,
        "pages": len(review["pages"]),
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    manifest = _read_object(path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise G594Error("g594_manifest_schema_invalid")
    if manifest.get("goal") != "G5.94" or manifest.get("frozen") is not True:
        raise G594Error("g594_manifest_not_frozen")
    documents = manifest.get("corpus", {}).get("documents") or []
    if len(documents) != 4 or sum(int(item["pages"]) for item in documents) != 103:
        raise G594Error("g594_manifest_corpus_invalid")
    b_contract = manifest.get("variant_b") or {}
    if (
        b_contract.get("input") != "one_lossless_full_page_png_only"
        or b_contract.get("representation") != "neutral_markdown"
        or b_contract.get("hidden_retry") is not False
        or b_contract.get("provider_failover") is not False
        or b_contract.get("best_of_n") is not False
    ):
        raise G594Error("g594_variant_b_contract_invalid")
    prompt = str(b_contract.get("prompt") or "")
    forbidden = (
        "DIVIDEND_INCOME",
        "TAX_WITHHELD",
        "TAX_ADJUSTMENT",
        "canonical artifact",
        "parser output",
    )
    if not prompt or any(value.lower() in prompt.lower() for value in forbidden):
        raise G594Error("g594_prompt_semantic_leakage")
    split = manifest["corpus"]["scoring_split"]
    development = sum(len(value) for value in split["development"].values())
    holdout = sum(len(value) for value in split["holdout"].values())
    if development != 32 or holdout != 21:
        raise G594Error("g594_scoring_split_invalid")
    return manifest


def _verify_variant_a_hashes(manifest: dict[str, Any]) -> None:
    for relative, expected in manifest["variant_a"]["source_hashes"].items():
        path = SERVICE_ROOT / relative
        if not path.is_file():
            raise G594Error("g594_variant_a_source_missing")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise G594Error("g594_variant_a_source_hash_drift")


def _find_sources(manifest: dict[str, Any], root: Path) -> dict[str, Path]:
    if not root.is_dir():
        raise G594Error("g594_corpus_root_missing")
    by_hash: dict[str, list[Path]] = {}
    for path in root.rglob("*.pdf"):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        by_hash.setdefault(digest, []).append(path)
    result: dict[str, Path] = {}
    for item in manifest["corpus"]["documents"]:
        matches = by_hash.get(str(item["pdf_sha256"])) or []
        if len(matches) != 1:
            raise G594Error("g594_corpus_source_not_unique")
        path = matches[0]
        if path.stat().st_size != int(item["pdf_bytes"]):
            raise G594Error("g594_corpus_source_size_mismatch")
        with fitz.open(path) as document:
            if len(document) != int(item["pages"]):
                raise G594Error("g594_corpus_page_count_mismatch")
        result[str(item["document_id"])] = path
    return result


def _normalize_document(
    document_id: str,
    path: Path,
    pdf_bytes: bytes,
) -> dict[str, Any]:
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    file_input = FileInput(
        private_ref=f"g594-private-pdf:{digest}",
        original_filename_private=f"{document_id}.pdf",
        mime_type="application/pdf",
        source_kind="local_private_test",
        declared_size_bytes=len(pdf_bytes),
        bytes_provider=lambda payload=pdf_bytes: payload,
        provider_label="controlled_private_registry",
    )
    result = Gate1Normalizer().normalize(
        [file_input],
        input_context={
            "clarification_criticality_refinement_enabled": True,
            "pdf_layout_slice2_enabled": True,
        },
    )
    package = result.package
    payloads = package.get("private_normalized_source_payloads") or []
    if len(payloads) != 1:
        raise G594Error("g594_variant_a_payload_invalid")
    return {
        "source_payload": payloads[0],
        "source_units": package.get("private_normalized_source_units") or [],
        "table_projections": package.get("private_normalized_table_projections")
        or [],
    }


def _persist_a_pages(
    *,
    document_id: str,
    declared: dict[str, Any],
    normalized: dict[str, Any],
    pdf_bytes: bytes,
    renderer: Any,
    page_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    projection = normalized["source_payload"]["pdf_text_layer_projection"]
    pages = sorted(projection.get("page_inventory") or [], key=lambda item: item["page_number"])
    lines = projection.get("line_inventory") or []
    tables = normalized["table_projections"]
    records: list[dict[str, Any]] = []
    counts = {"ready": 0, "blocked": 0}
    addressability = {
        "lines_total": 0,
        "lines_with_page_source_and_bbox_refs": 0,
        "cells_total": 0,
        "cells_with_source_paths": 0,
    }
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        if len(pages) != len(document) or len(pages) != int(declared["pages"]):
            raise G594Error("g594_variant_a_page_inventory_mismatch")
        for page in pages:
            page_number = int(page["page_number"])
            page_ref = str(page["page_ref"])
            page_lines = [item for item in lines if item.get("page_ref") == page_ref]
            page_tables = [
                item for item in tables if page_ref in (item.get("page_refs") or [])
            ]
            for table in page_tables:
                status = "ready" if table.get("projection_status") == "ready" else "blocked"
                counts[status] += 1
                cells = table.get("cells") or []
                addressability["cells_total"] += len(cells)
                addressability["cells_with_source_paths"] += sum(
                    bool(cell.get("normalized_private_value_path")) for cell in cells
                )
            addressability["lines_total"] += len(page_lines)
            addressability["lines_with_page_source_and_bbox_refs"] += sum(
                bool(item.get("page_ref"))
                and bool(item.get("source_value_ref"))
                and bool(item.get("bbox_ref"))
                for item in page_lines
            )
            private_page = {
                "document_id": document_id,
                "page_number": page_number,
                "page_ref": page_ref,
                "page_text": page.get("text"),
                "lines": page_lines,
                "table_projections": page_tables,
                "source_units": [
                    unit
                    for unit in normalized["source_units"]
                    if page_ref in (unit.get("page_refs") or [])
                ],
            }
            json_path = page_dir / f"p{page_number:03d}.variant_a.private.json"
            _write_json(json_path, private_page)
            page_rect = [round(float(value), 6) for value in document[page_number - 1].rect]
            rendered = renderer.render_full_page(
                pdf_bytes=pdf_bytes,
                pdf_sha256=str(declared["pdf_sha256"]),
                document_ref=document_id,
                page_ref=f"{document_id}:p{page_number:03d}",
                page_number=page_number,
                expected_page_bbox=page_rect,
                dpi=150,
            )
            png = base64.b64decode(rendered["private_png_base64"])
            png_path = page_dir / f"p{page_number:03d}.private.png"
            png_path.write_bytes(png)
            records.append(
                {
                    "page_id": f"{document_id}:p{page_number:03d}",
                    "page_number": page_number,
                    "page_png_sha256": hashlib.sha256(png).hexdigest(),
                    "variant_a_page_sha256": hashlib.sha256(
                        json_path.read_bytes()
                    ).hexdigest(),
                }
            )
    return records, counts, addressability


def _build_slots(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    repeat = set(manifest["corpus"]["repeatability_pages"])
    slots: list[dict[str, Any]] = []
    for document in manifest["corpus"]["documents"]:
        document_id = str(document["document_id"])
        for page_number in range(1, int(document["pages"]) + 1):
            page_id = f"{document_id}:p{page_number:03d}"
            slots.append(_slot(page_id, document_id, page_number, 1))
            if page_id in repeat:
                slots.append(_slot(page_id, document_id, page_number, 2))
    if len(slots) != 111:
        raise G594Error("g594_slot_count_invalid")
    return slots


def _slot(
    page_id: str,
    document_id: str,
    page_number: int,
    run_ordinal: int,
) -> dict[str, Any]:
    return {
        "slot_id": f"{page_id.replace(':', '_')}:run{run_ordinal}",
        "page_id": page_id,
        "document_id": document_id,
        "page_number": page_number,
        "run_ordinal": run_ordinal,
        "response_selection_eligible": False,
    }


def _slot_file_stem(slot_id: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]", "_", slot_id)
    if not stem or stem in {".", ".."}:
        raise G594Error("g594_slot_filename_invalid")
    return stem


def _variant_b_model_view(manifest: dict[str, Any]) -> dict[str, Any]:
    return {"task": str(manifest["variant_b"]["prompt"])}


def _validated_markdown(value: Any) -> tuple[str | None, str | None]:
    if not isinstance(value, dict) or set(value) != {"markdown"}:
        return None, "markdown_response_shape_invalid"
    markdown = value.get("markdown")
    if not isinstance(markdown, str) or not markdown.strip():
        return None, "markdown_empty"
    if "\x00" in markdown:
        return None, "markdown_control_character_invalid"
    if len(markdown.encode("utf-8")) > 1024 * 1024:
        return None, "markdown_size_limit_exceeded"
    return markdown.replace("\r\n", "\n").replace("\r", "\n"), None


def _safe_slot_result(
    *,
    slot: dict[str, Any],
    outcome: dict[str, Any],
    markdown: str | None,
    validation_error: str | None,
) -> dict[str, Any]:
    attempt = copy.deepcopy(outcome.get("attempt") or {})
    terminal_error = validation_error or attempt.get("terminal_failure_class")
    return {
        "slot_id": slot["slot_id"],
        "page_id": slot["page_id"],
        "run_ordinal": slot["run_ordinal"],
        "status": "accepted" if terminal_error is None else "failed",
        "terminal_error": terminal_error,
        "duration_ms": attempt.get("duration_ms"),
        "usage": attempt.get("usage") or {},
        "finish_reason": attempt.get("finish_reason"),
        "model_requested": attempt.get("model_requested"),
        "model_resolved": attempt.get("model_resolved"),
        "markdown_sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest()
        if markdown is not None
        else None,
        "markdown_utf8_bytes": len(markdown.encode("utf-8"))
        if markdown is not None
        else 0,
        "structure_signature": _markdown_structure_signature(markdown)
        if markdown is not None
        else None,
        "hidden_retry": False,
        "provider_failover": False,
        "response_selection_eligible": False,
    }


def _markdown_structure_signature(markdown: str) -> dict[str, int]:
    lines = markdown.splitlines()
    return {
        "lines": len(lines),
        "headings": sum(bool(re.match(r"^#{1,6}\s", line)) for line in lines),
        "pipe_rows": sum(line.count("|") >= 2 for line in lines),
        "table_separators": sum(
            bool(re.match(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+", line))
            for line in lines
        ),
        "list_items": sum(
            bool(re.match(r"^\s*(?:[-*+] |\d+[.)] )", line)) for line in lines
        ),
        "blank_lines": sum(not line.strip() for line in lines),
    }


def _execution_summary(
    *,
    manifest: dict[str, Any],
    plan: dict[str, Any],
    qualification: dict[str, Any],
    results: list[dict[str, Any]],
    duration_ms: int,
    submitted: int,
    skipped_terminal: int,
    interrupted_claims: int,
) -> dict[str, Any]:
    primary = [item for item in results if item.get("run_ordinal") == 1]
    repeats = [item for item in results if item.get("run_ordinal") == 2]
    input_tokens = sum(int((item.get("usage") or {}).get("input_tokens") or 0) for item in results)
    output_tokens = sum(int((item.get("usage") or {}).get("output_tokens") or 0) for item in results)
    pricing = manifest["variant_b"]["pricing"]
    repeatability = _repeatability(results)
    complete = len(primary) == 103 and len(repeats) == 8 and interrupted_claims == 0
    return {
        "schema_version": SAFE_SCHEMA,
        "phase": "executed",
        "status": "complete" if complete else "incomplete",
        "manifest_sha256": plan["manifest_sha256"],
        "provider_qualification": qualification,
        "slots": {
            "planned": len(plan["slots"]),
            "terminal": len(results),
            "primary_terminal": len(primary),
            "repeat_terminal": len(repeats),
            "accepted": sum(item.get("status") == "accepted" for item in results),
            "failed": sum(item.get("status") != "accepted" for item in results),
            "submitted_this_process": submitted,
            "skipped_existing_terminal": skipped_terminal,
            "interrupted_claims": interrupted_claims,
        },
        "duration_ms_this_process": duration_ms,
        "provider_calls_total": len(results),
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        },
        "estimated_cost": {
            "currency": pricing["currency"],
            "input": round(input_tokens * float(pricing["input_usd_per_1m_tokens"]) / 1_000_000, 6),
            "output": round(output_tokens * float(pricing["output_usd_per_1m_tokens"]) / 1_000_000, 6),
            "total": round(
                input_tokens * float(pricing["input_usd_per_1m_tokens"]) / 1_000_000
                + output_tokens * float(pricing["output_usd_per_1m_tokens"]) / 1_000_000,
                6,
            ),
            "pricing_effective_date": pricing["effective_date"],
            "pricing_source_url": pricing["source_url"],
        },
        "repeatability": repeatability,
        "hidden_retry": False,
        "provider_failover": False,
        "best_of_n": False,
        "privacy": _privacy_statement(),
    }


def _repeatability(results: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        groups.setdefault(str(item["page_id"]), []).append(item)
    repeated = [items for items in groups.values() if len(items) == 2]
    both_accepted = [
        items for items in repeated if all(item.get("status") == "accepted" for item in items)
    ]
    exact = sum(
        items[0].get("markdown_sha256") == items[1].get("markdown_sha256")
        for items in both_accepted
    )
    structural = sum(
        items[0].get("structure_signature") == items[1].get("structure_signature")
        for items in both_accepted
    )
    return {
        "planned_pages": 8,
        "terminal_pairs": len(repeated),
        "both_accepted_pairs": len(both_accepted),
        "exact_match_pairs": exact,
        "structural_match_pairs": structural,
        "classification": "STABLE"
        if len(both_accepted) == 8 and structural == 8
        else "STOCHASTIC",
        "outputs_selected": 0,
    }


def _review_template(manifest: dict[str, Any]) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for split_name in ("development", "holdout"):
        split = manifest["corpus"]["scoring_split"][split_name]
        for document_id, numbers in split.items():
            for page_number in numbers:
                pages.append(
                    {
                        "page_id": f"{document_id}:p{int(page_number):03d}",
                        "split": split_name,
                        "source_truth_reviewed": False,
                        "A": {field: None for field in ERROR_FIELDS},
                        "B": {field: None for field in ERROR_FIELDS},
                        "disagreement_verdict": None,
                        "notes": None,
                    }
                )
    return {
        "schema_version": REVIEW_SCHEMA,
        "manifest_sha256": _sha256_json(manifest),
        "pages": pages,
        "recommendation": None,
        "recommendation_basis": None,
    }


def _materialize_review(
    template: dict[str, Any], decisions: dict[str, Any]
) -> dict[str, Any]:
    if decisions.get("schema_version") != REVIEW_DECISIONS_SCHEMA:
        raise G594Error("g594_review_decisions_schema_invalid")
    if decisions.get("manifest_sha256") != template.get("manifest_sha256"):
        raise G594Error("g594_review_decisions_manifest_mismatch")
    if decisions.get("unlisted_findings_confirmed_zero") is not True:
        raise G594Error("g594_review_decisions_not_fail_closed")

    review = copy.deepcopy(template)
    pages_by_id = {str(page["page_id"]): page for page in review["pages"]}
    for page in review["pages"]:
        page["source_truth_reviewed"] = True
        page["disagreement_verdict"] = "TIE"
        page["notes"] = "no_counted_difference"
        for arm in ("A", "B"):
            page[arm] = {field: 0 for field in ERROR_FIELDS}

    overrides = decisions.get("overrides") or {}
    if not isinstance(overrides, dict) or not set(overrides).issubset(pages_by_id):
        raise G594Error("g594_review_decisions_page_invalid")
    for page_id, page_override in overrides.items():
        if not isinstance(page_override, dict):
            raise G594Error("g594_review_decisions_shape_invalid")
        page = pages_by_id[page_id]
        for arm in ("A", "B"):
            arm_override = page_override.get(arm) or {}
            if not isinstance(arm_override, dict) or not set(arm_override).issubset(
                ERROR_FIELDS
            ):
                raise G594Error("g594_review_decisions_field_invalid")
            for field, value in arm_override.items():
                if not isinstance(value, int) or value < 0:
                    raise G594Error("g594_review_decisions_count_invalid")
                page[arm][field] = value
        for field in ("disagreement_verdict", "notes"):
            if field in page_override:
                page[field] = str(page_override[field])

    review["recommendation"] = decisions.get("recommendation")
    review["recommendation_basis"] = decisions.get("recommendation_basis")
    return review


def _validate_review(review: dict[str, Any], manifest: dict[str, Any]) -> None:
    if review.get("schema_version") != REVIEW_SCHEMA:
        raise G594Error("g594_review_schema_invalid")
    if review.get("manifest_sha256") != _sha256_json(manifest):
        raise G594Error("g594_review_manifest_mismatch")
    pages = review.get("pages") or []
    if len(pages) != 53 or len({item.get("page_id") for item in pages}) != 53:
        raise G594Error("g594_review_page_set_invalid")
    for page in pages:
        if page.get("source_truth_reviewed") is not True:
            raise G594Error("g594_review_not_complete")
        for arm in ("A", "B"):
            values = page.get(arm)
            if not isinstance(values, dict) or set(values) != set(ERROR_FIELDS):
                raise G594Error("g594_review_error_shape_invalid")
            if any(not isinstance(values[field], int) or values[field] < 0 for field in ERROR_FIELDS):
                raise G594Error("g594_review_error_count_invalid")


def _aggregate_review(
    review: dict[str, Any],
    split: str,
    arm: str,
) -> dict[str, Any]:
    pages = [
        item
        for item in review["pages"]
        if split == "all" or item.get("split") == split
    ]
    errors = {
        field: sum(int(item[arm][field]) for item in pages) for field in ERROR_FIELDS
    }
    literal_fields = ERROR_FIELDS[:7]
    structure_fields = ERROR_FIELDS[7:]
    return {
        "pages": len(pages),
        "literal_errors_total": sum(errors[field] for field in literal_fields),
        "structural_errors_total": sum(errors[field] for field in structure_fields),
        "errors": errors,
    }


def _primary_economics(
    *,
    plan: dict[str, Any],
    private_dir: Path,
    pricing: dict[str, Any],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for slot in plan["slots"]:
        if int(slot["run_ordinal"]) != 1:
            continue
        stem = _slot_file_stem(str(slot["slot_id"]))
        results.append(
            _read_object(
                private_dir / "variant_b_slots" / f"{stem}.result.safe.json"
            )
        )
    if len(results) != 103:
        raise G594Error("g594_primary_economics_page_count_invalid")
    return _economics_summary(results, pricing)


def _economics_summary(
    results: list[dict[str, Any]], pricing: dict[str, Any]
) -> dict[str, Any]:
    if not results:
        raise G594Error("g594_economics_results_missing")
    durations = sorted(int(item["duration_ms"]) for item in results)
    input_tokens = sum(int(item["usage"].get("input_tokens") or 0) for item in results)
    output_tokens = sum(int(item["usage"].get("output_tokens") or 0) for item in results)
    input_cost = input_tokens * float(pricing["input_usd_per_1m_tokens"]) / 1_000_000
    output_cost = output_tokens * float(pricing["output_usd_per_1m_tokens"]) / 1_000_000
    total_cost = input_cost + output_cost
    pages = len(results)
    accepted = sum(item.get("status") == "accepted" for item in results)
    duration_total_ms = sum(durations)
    return {
        "pages": pages,
        "accepted": accepted,
        "failed": pages - accepted,
        "availability_ratio": round(accepted / pages, 6),
        "duration_total_ms": duration_total_ms,
        "duration_mean_ms": round(duration_total_ms / pages, 1),
        "duration_median_ms": durations[pages // 2],
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
            "mean_per_page": round((input_tokens + output_tokens) / pages, 1),
        },
        "estimated_cost": {
            "currency": str(pricing["currency"]),
            "input": round(input_cost, 6),
            "output": round(output_cost, 6),
            "total": round(total_cost, 6),
            "projected_per_1000_pages_same_mix": round(total_cost * 1000 / pages, 4),
            "pricing_effective_date": str(pricing["effective_date"]),
            "pricing_source_url": str(pricing["source_url"]),
        },
    }


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(env.get("OPENWEBUI_HOST") or "").rstrip("/")
    email = str(env.get("WEBUI_ADMIN_EMAIL") or "")
    password = str(env.get("WEBUI_ADMIN_PASSWORD") or "")
    if not all((host, email, password)):
        raise G594Error("g594_openwebui_credentials_missing")
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
        raise G594Error("g594_openwebui_token_missing")
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
        raise G594Error("g594_env_file_missing")
    result: dict[str, str] = {}
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
        raise G594Error("g594_required_json_missing")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise G594Error("g594_json_object_required")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8") + b"\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
