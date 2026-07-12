#!/usr/bin/env python3
"""Compare deterministic, raster-only and hybrid PDF table extraction safely."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import mimetypes
import re
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

import fitz
import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1 import FileInput, Gate1Normalizer  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


REFERENCE_SCHEMA = "broker_reports_pdf_table_visual_reference_v1"
SAFE_RESULT_SCHEMA = "broker_reports_pdf_table_approach_experiment_safe_v1"
PRIVATE_RESULT_SCHEMA = "broker_reports_pdf_table_approach_experiment_private_v1"
RASTER_OUTPUT_SCHEMA = "broker_reports_raster_table_output_v1"
HYBRID_OUTPUT_SCHEMA = "broker_reports_hybrid_table_binding_output_v1"

# page:table ordinals are one-based. The set was selected after visual inspection
# of the controlled six-page PDF and deliberately includes blocked production
# candidates and a cross-page continuation.
DEFAULT_TABLE_KEYS = (
    "1:1",
    "1:2",
    "1:3",
    "2:2",
    "3:2",
    "4:1",
    "4:2",
    "5:3",
    "5:4",
)
DEFAULT_SENSITIVITY_KEYS = ("1:3", "3:2", "4:1", "5:3")
DEFAULT_REPEAT_KEYS = ("1:2", "3:2")
REFERENCE_ROW_LIMITS = {
    "1:3": 8,
    "2:2": 12,
    "3:2": 12,
    "4:1": 10,
}

# This is a manual structural assertion derived from page-image inspection, not
# from the production table projection. Numbering rows are treated as headers.
MANUAL_HEADER_ROWS = {
    "1:1": 3,
    "1:2": 2,
    "1:3": 3,
    "2:2": 2,
    "3:2": 2,
    "4:1": 0,
    "4:2": 3,
    "5:3": 2,
    "5:4": 2,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--model-id", default="models/gemini-3.5-flash")
    parser.add_argument("--primary-dpi", type=int, default=150)
    parser.add_argument("--sensitivity-dpi", type=int, default=200)
    parser.add_argument("--repeat-count", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--skip-vlm", action="store_true")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    private_dir = output_dir / "private"
    crop_dir = private_dir / "crops"
    private_dir.mkdir(parents=True, exist_ok=True)
    crop_dir.mkdir(parents=True, exist_ok=True)

    pdf_bytes = pdf_path.read_bytes()
    pdf_sha256 = _sha256(pdf_bytes)
    document = fitz.open(pdf_path)
    references = _build_reference_set(document, pdf_sha256)
    selected = [references[key] for key in DEFAULT_TABLE_KEYS]
    _write_json(private_dir / "reference.private.json", {
        "schema_version": REFERENCE_SCHEMA,
        "pdf_sha256": pdf_sha256,
        "human_review_status": "agent_visual_reviewed_pending_human_signoff",
        "tables": selected,
    })

    normalization_started = time.perf_counter()
    normalization = _normalize(pdf_path, pdf_bytes, pdf_sha256)
    normalization_seconds = time.perf_counter() - normalization_started
    source_payload = normalization["source_payload"]
    table_projections = normalization["table_projections"]
    component_audit = _component_audit(
        source_payload=source_payload,
        source_units=normalization["source_units"],
        table_projections=table_projections,
    )

    deterministic = _run_deterministic_arm(
        references=references,
        source_payload=source_payload,
        projections=table_projections,
        pdf_sha256=pdf_sha256,
    )
    _write_json(private_dir / "deterministic.private.json", deterministic["private"])

    crops = _render_crops(
        document=document,
        references=selected,
        crop_dir=crop_dir,
        primary_dpi=args.primary_dpi,
        sensitivity_dpi=args.sensitivity_dpi,
    )
    words_by_table = {
        item["table_key"]: _word_candidates(document, source_payload, item)
        for item in selected
    }

    journal_path = private_dir / "vlm_journal.private.json"
    journal = _read_json_list(journal_path)
    journal = [
        _revalidate_checkpoint(item, references=references, candidates_by_table=words_by_table)
        for item in journal
    ]
    _write_json(journal_path, journal)
    vlm_private: list[dict[str, Any]] = [item["private"] for item in journal if isinstance(item.get("private"), dict)]
    vlm_safe: list[dict[str, Any]] = [item["safe"] for item in journal if isinstance(item.get("safe"), dict)]
    if not args.skip_vlm:
        env = _read_env(Path(args.env_file))
        base_url = _base_url(env)
        session = requests.Session()
        token = _signin(session, base_url, env)
        session.headers.update({"Authorization": f"Bearer {token}"})
        jobs = _vlm_jobs(
            selected,
            primary_dpi=args.primary_dpi,
            sensitivity_dpi=args.sensitivity_dpi,
            repeat_count=args.repeat_count,
        )
        completed_jobs = {
            (str(item.get("arm")), str(item.get("table_key")), int(item.get("dpi") or 0), int(item.get("run_ordinal") or 0))
            for item in vlm_safe
        }
        for job in jobs:
            job_key = (job["arm"], job["table_key"], job["dpi"], job["run_ordinal"])
            if job_key in completed_jobs:
                continue
            reference = references[job["table_key"]]
            crop = crops[(job["table_key"], job["dpi"])]
            try:
                if job["arm"] == "raster":
                    outcome = _run_raster_call(
                        session=session,
                        base_url=base_url,
                        model_id=args.model_id,
                        reference=reference,
                        crop=crop,
                        timeout=args.timeout,
                    )
                else:
                    outcome = _run_hybrid_call(
                        session=session,
                        base_url=base_url,
                        model_id=args.model_id,
                        reference=reference,
                        crop=crop,
                        candidates=words_by_table[job["table_key"]],
                        timeout=args.timeout,
                    )
            except Exception as exc:
                outcome = _failed_vlm_outcome(
                    job=job,
                    reference=reference,
                    crop=crop,
                    model_id=args.model_id,
                    exc=exc,
                )
            outcome["private"]["run_ordinal"] = job["run_ordinal"]
            outcome["safe"]["run_ordinal"] = job["run_ordinal"]
            vlm_private.append(outcome["private"])
            vlm_safe.append(outcome["safe"])
            journal.append(outcome)
            _write_json(journal_path, journal)

    raster_compact = _compact_vlm_artifact(
        arm="raster",
        pdf_sha256=pdf_sha256,
        model_id=args.model_id,
        runs=vlm_private,
        candidates_by_table=words_by_table,
    )
    hybrid_compact = _compact_vlm_artifact(
        arm="hybrid",
        pdf_sha256=pdf_sha256,
        model_id=args.model_id,
        runs=vlm_private,
        candidates_by_table=words_by_table,
    )
    _write_json(private_dir / "raster_compact.private.json", raster_compact)
    _write_json(private_dir / "hybrid_compact.private.json", hybrid_compact)

    private_result = {
        "schema_version": PRIVATE_RESULT_SCHEMA,
        "pdf_sha256": pdf_sha256,
        "references": selected,
        "deterministic": deterministic["private"],
        "vlm_runs": vlm_private,
    }
    _write_json(private_dir / "experiment.private.json", private_result)

    expected_vlm_jobs = len(_vlm_jobs(
        selected,
        primary_dpi=args.primary_dpi,
        sensitivity_dpi=args.sensitivity_dpi,
        repeat_count=args.repeat_count,
    ))
    experiment_status = _experiment_status(
        skip_vlm=args.skip_vlm,
        runs=vlm_safe,
        expected_jobs=expected_vlm_jobs,
    )
    safe_result = {
        "schema_version": SAFE_RESULT_SCHEMA,
        "status": experiment_status,
        "scope": {
            "pdf_pages": len(document),
            "reference_tables_total": len(references),
            "selected_tables_total": len(selected),
            "selected_table_keys": list(DEFAULT_TABLE_KEYS),
            "human_review_status": "agent_visual_reviewed_pending_human_signoff",
            "gridless_table_present": False,
        },
        "source": {
            "pdf_bytes": len(pdf_bytes),
            "pdf_sha256": pdf_sha256,
            "normalization_seconds": round(normalization_seconds, 3),
        },
        "normalization_component_audit": component_audit,
        "deterministic": deterministic["safe"],
        "crops": _safe_crop_summary(crops),
        "vlm_runs": vlm_safe,
        "vlm_aggregates": _aggregate_vlm(vlm_safe),
        "permanent_artifacts": {
            "deterministic_compact": _size_metrics(deterministic["private"]["compact_artifact"]),
            "raster_compact": _size_metrics(raster_compact),
            "hybrid_compact": _size_metrics(hybrid_compact),
            "optional_crop_png_bytes": sum(item["png_bytes"] for item in crops.values()),
        },
        "guards": {
            "production_runtime_changed": False,
            "validator_weakened": False,
            "knowledge_rag_vector_used": False,
            "openwebui_core_changed": False,
            "raw_customer_data_in_safe_output": False,
        },
    }
    _write_json(output_dir / "experiment.safe.json", safe_result)
    print(json.dumps(safe_result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if experiment_status in {"passed", "completed_with_failures", "deterministic_only"} else 2


def _build_reference_set(document: fitz.Document, pdf_sha256: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for page_index, page in enumerate(document):
        found = page.find_tables()
        for table_index, table in enumerate(found.tables):
            key = f"{page_index + 1}:{table_index + 1}"
            cells = [[str(value or "") for value in row] for row in table.extract()]
            columns = max((len(row) for row in cells), default=0)
            cells = [row + [""] * (columns - len(row)) for row in cells]
            source_rows = len(cells)
            row_limit = REFERENCE_ROW_LIMITS.get(key)
            if row_limit:
                cells = cells[:row_limit]
                row_boxes = [cell for row in table.rows[:row_limit] for cell in row.cells if cell]
                if row_boxes:
                    table_bbox = (
                        min(cell[0] for cell in row_boxes),
                        min(cell[1] for cell in row_boxes),
                        max(cell[2] for cell in row_boxes),
                        max(cell[3] for cell in row_boxes),
                    )
                else:
                    table_bbox = table.bbox
            else:
                table_bbox = table.bbox
            result[key] = {
                "table_key": key,
                "page": page_index + 1,
                "table_ordinal": table_index + 1,
                "bbox": [round(float(value), 4) for value in table_bbox],
                "bbox_norm": _normalize_bbox(table_bbox, page.rect),
                "rows": len(cells),
                "source_table_rows": source_rows,
                "row_limit": row_limit,
                "columns": columns,
                "header_rows": MANUAL_HEADER_ROWS.get(key, 0),
                "cells": cells,
                "cell_hashes": [[_sha256(_normalize_cell(value).encode()) for value in row] for row in cells],
                "content_hash": _sha256(_canonical_bytes(cells)),
                "pdf_sha256": pdf_sha256,
                "reference_engine": "pymupdf_table_finder_plus_agent_visual_structure_review",
            }
    return result


def _normalize(pdf_path: Path, pdf_bytes: bytes, pdf_sha256: str) -> dict[str, Any]:
    alias = "controlled.pdf"
    file_input = FileInput(
        private_ref=f"controlled-private-pdf:{pdf_sha256}",
        original_filename_private=alias,
        mime_type=mimetypes.guess_type(alias)[0] or "application/pdf",
        source_kind="local_private_test",
        declared_size_bytes=len(pdf_bytes),
        bytes_provider=lambda: pdf_path.read_bytes(),
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
    return {
        "source_payload": (package.get("private_normalized_source_payloads") or [])[0],
        "source_units": package.get("private_normalized_source_units") or [],
        "table_projections": package.get("private_normalized_table_projections") or [],
    }


def _component_audit(
    *, source_payload: dict[str, Any], source_units: list[dict[str, Any]], table_projections: list[dict[str, Any]]
) -> dict[str, Any]:
    pdf_projection = _object(source_payload.get("pdf_text_layer_projection"))
    components: dict[str, Any] = {}
    for name in (
        "char_inventory",
        "bbox_inventory",
        "word_inventory",
        "line_inventory",
        "text_fragment_inventory",
        "page_inventory",
        "vector_line_inventory",
        "rect_inventory",
        "table_candidate_inventory",
        "coverage",
        "layout_coverage",
        "parser_diagnostics",
        "layout_parser_diagnostics",
        "layout_unit_diagnostics",
    ):
        components[name] = _component_metrics(pdf_projection.get(name))
    components["source_value_index"] = _component_metrics(source_payload.get("source_value_index"))
    components["source_value_refs"] = _component_metrics(source_payload.get("source_value_refs"))
    components["source_units"] = _component_metrics(source_units)
    components["table_projections"] = _component_metrics(table_projections)
    components["accepted_table_rows"] = _component_metrics([
        row for item in table_projections if item.get("projection_status") == "ready" for row in item.get("rows") or []
    ])
    components["accepted_table_cells"] = _component_metrics([
        cell for item in table_projections if item.get("projection_status") == "ready" for cell in item.get("cells") or []
    ])
    components["header_models"] = _component_metrics([item.get("header_model") or {} for item in table_projections])
    components["rejected_table_hypotheses"] = _component_metrics([
        item for item in table_projections if item.get("projection_status") != "ready"
    ])
    full = _component_metrics(source_payload)
    return {
        "full_normalized_source_document": full,
        "components": components,
        "source_units": _size_metrics(source_units),
        "table_projections": _size_metrics(table_projections),
        "ready_tables": sum(item.get("projection_status") == "ready" for item in table_projections),
        "blocked_tables": sum(item.get("projection_status") != "ready" for item in table_projections),
    }


def _component_metrics(value: Any) -> dict[str, Any]:
    raw = _canonical_bytes(value)
    items = value if isinstance(value, list) else [value]
    hashes = [_sha256(_canonical_bytes(item)) for item in items]
    texts: list[str] = []
    _collect_visible_text(value, texts)
    unique_texts = list(dict.fromkeys(texts))
    return {
        "json_bytes": len(raw),
        "gzip_bytes": len(gzip.compress(raw, compresslevel=9)),
        "object_count": _node_counts(value)["objects"],
        "array_count": _node_counts(value)["arrays"],
        "item_count": len(items),
        "unique_object_count": len(set(hashes)),
        "duplicate_object_count": len(hashes) - len(set(hashes)),
        "text_occurrences": len(texts),
        "unique_text_count": len(unique_texts),
        "text_utf8_bytes": sum(len(item.encode()) for item in texts),
        "unique_text_utf8_bytes": sum(len(item.encode()) for item in unique_texts),
    }


def _run_deterministic_arm(
    *, references: dict[str, dict[str, Any]], source_payload: dict[str, Any], projections: list[dict[str, Any]], pdf_sha256: str
) -> dict[str, Any]:
    pdf_projection = _object(source_payload.get("pdf_text_layer_projection"))
    bboxes = {str(item.get("bbox_ref")): item.get("bbox") for item in pdf_projection.get("bbox_inventory") or []}
    page_order = {
        str(item.get("page_ref")): index + 1
        for index, item in enumerate(pdf_projection.get("page_inventory") or [])
    }
    results = []
    compact_tables = []
    matched_reference_keys: set[str] = set()
    for projection in projections:
        page_refs = [str(value) for value in projection.get("page_refs") or []]
        page = page_order.get(page_refs[0], 0) if page_refs else 0
        bbox = bboxes.get(str(projection.get("table_bbox_ref") or ""))
        reference = _best_reference(references, page, bbox)
        if reference is None:
            continue
        matched_reference_keys.add(reference["table_key"])
        predicted = _projection_grid(projection)
        if reference.get("row_limit"):
            predicted = predicted[: int(reference["row_limit"])]
        score = _score_table(reference, predicted, _projection_header_rows(projection))
        status = "accepted" if projection.get("projection_status") == "ready" else "blocked"
        results.append({
            "table_key": reference["table_key"],
            "status": status,
            "quality": projection.get("reconstruction_quality"),
            "reason_codes": list(projection.get("reconstruction_reason_codes") or []),
            "score": score,
            "projection_hash": _sha256(_canonical_bytes(projection)),
        })
        compact_tables.append(_compact_projection(projection, reference, predicted, pdf_sha256))
    all_reference_keys = set(references)
    ready = [item for item in results if item["status"] == "accepted"]
    safe = {
        "candidates_total": len(results),
        "reference_tables_total": len(references),
        "candidate_detection_recall": round(len(matched_reference_keys) / len(all_reference_keys), 6),
        "accepted_tables_total": len(ready),
        "accepted_reconstruction_recall": round(len(ready) / len(all_reference_keys), 6),
        "accepted_precision": 1.0 if ready else 0.0,
        "selected_results": [item for item in results if item["table_key"] in DEFAULT_TABLE_KEYS],
        "aggregate_score": _aggregate_scores([item["score"] for item in results if item["table_key"] in DEFAULT_TABLE_KEYS]),
        "compact_artifact_size": _size_metrics({"tables": compact_tables}),
    }
    return {
        "safe": safe,
        "private": {
            "pdf_sha256": pdf_sha256,
            "results": results,
            "compact_artifact": {
                "schema_version": "broker_reports_pdf_compact_canonical_document_v1",
                "pdf_sha256": pdf_sha256,
                "tables": compact_tables,
            },
        },
    }


def _projection_grid(projection: dict[str, Any]) -> list[list[str]]:
    if projection.get("projection_status") != "ready":
        return []
    rows = int(projection.get("row_count") or 0)
    columns = int(projection.get("column_count") or 0)
    grid = [[""] * columns for _ in range(rows)]
    values = {
        str(item.get("value_path_ref")): str(item.get("normalized_value") or "")
        for item in projection.get("private_values") or []
    }
    for cell in projection.get("cells") or []:
        row = int(cell.get("row_ordinal") or 0) - 1
        column = int(cell.get("column_ordinal") or 0) - 1
        if 0 <= row < rows and 0 <= column < columns:
            grid[row][column] = values.get(str(cell.get("normalized_private_value_path") or ""), "")
    return grid


def _projection_header_rows(projection: dict[str, Any]) -> int:
    rows = projection.get("rows") or []
    count = 0
    for row in rows:
        if row.get("row_role") == "header_row":
            count += 1
        else:
            break
    return count


def _compact_projection(
    projection: dict[str, Any], reference: dict[str, Any], grid: list[list[str]], pdf_sha256: str
) -> dict[str, Any]:
    cells_by_position = {
        (int(item.get("row_ordinal") or 0), int(item.get("column_ordinal") or 0)): item
        for item in projection.get("cells") or []
    }
    cells = []
    for row_index, row in enumerate(grid, start=1):
        for column_index, text in enumerate(row, start=1):
            source = cells_by_position.get((row_index, column_index), {})
            cells.append({
                "row": row_index,
                "column": column_index,
                "text": text,
                "text_hash": _sha256(_normalize_cell(text).encode()),
                "bbox_ref": source.get("bbox_ref"),
                "source_value_refs": list(source.get("source_value_refs") or []),
                "value_checksum_ref": source.get("value_checksum_ref"),
            })
    return {
        "table_key": reference["table_key"],
        "page": reference["page"],
        "bbox": reference["bbox"],
        "pdf_sha256": pdf_sha256,
        "projection_status": projection.get("projection_status"),
        "rows": int(projection.get("row_count") or 0),
        "columns": int(projection.get("column_count") or 0),
        "header_model": projection.get("header_model") or {},
        "cells": cells,
        "issues": list(projection.get("reconstruction_reason_codes") or []),
    }


def _render_crops(
    *, document: fitz.Document, references: list[dict[str, Any]], crop_dir: Path, primary_dpi: int, sensitivity_dpi: int
) -> dict[tuple[str, int], dict[str, Any]]:
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for reference in references:
        dpis = {primary_dpi}
        if reference["table_key"] in DEFAULT_SENSITIVITY_KEYS:
            dpis.add(sensitivity_dpi)
        for dpi in sorted(dpis):
            page = document[reference["page"] - 1]
            bbox = fitz.Rect(reference["bbox"])
            bbox = fitz.Rect(max(0, bbox.x0 - 2), max(0, bbox.y0 - 2), min(page.rect.x1, bbox.x1 + 2), min(page.rect.y1, bbox.y1 + 2))
            pix = page.get_pixmap(dpi=dpi, clip=bbox, alpha=False)
            path = crop_dir / f"table_{reference['table_key'].replace(':', '_')}_{dpi}dpi.png"
            pix.save(path)
            raw = path.read_bytes()
            result[(reference["table_key"], dpi)] = {
                "table_key": reference["table_key"],
                "page": reference["page"],
                "dpi": dpi,
                "path": str(path),
                "png_bytes": len(raw),
                "png_sha256": _sha256(raw),
                "width": pix.width,
                "height": pix.height,
                "bbox": [round(value, 4) for value in bbox],
            }
    return result


def _word_candidates(
    document: fitz.Document, source_payload: dict[str, Any], reference: dict[str, Any]
) -> list[dict[str, Any]]:
    page = document[reference["page"] - 1]
    table_rect = fitz.Rect(reference["bbox"])
    pdf_projection = _object(source_payload.get("pdf_text_layer_projection"))
    page_refs = {
        index + 1: str(item.get("page_ref") or "")
        for index, item in enumerate(pdf_projection.get("page_inventory") or [])
    }
    bboxes = {
        str(item.get("bbox_ref") or ""): item.get("bbox")
        for item in pdf_projection.get("bbox_inventory") or []
    }
    production_words = [
        {**item, "bbox": bboxes.get(str(item.get("bbox_ref") or ""))}
        for item in pdf_projection.get("word_inventory") or []
        if str(item.get("page_ref") or "") == page_refs.get(reference["page"])
    ]
    used_production_refs: set[str] = set()
    values = []
    for ordinal, word in enumerate(page.get_text("words", clip=table_rect, sort=True), start=1):
        x0, y0, x1, y1, text, *_ = word
        match = _best_production_word(
            text=str(text),
            bbox=(x0, y0, x1, y1),
            production_words=production_words,
            used_refs=used_production_refs,
        )
        if match:
            used_production_refs.add(str(match.get("word_ref") or ""))
        values.append({
            "candidate_id": f"w{ordinal:04d}",
            "text": str(text),
            "bbox_norm": _normalize_bbox((x0, y0, x1, y1), table_rect),
            "text_hash": _sha256(_normalize_cell(str(text)).encode()),
            "source_value_ref": match.get("source_value_ref") if match else None,
            "source_word_ref": match.get("word_ref") if match else None,
            "source_bbox_ref": match.get("bbox_ref") if match else None,
            "source_text_checksum_ref": match.get("text_checksum_ref") if match else None,
        })
    return values


def _best_production_word(
    *, text: str, bbox: Any, production_words: list[dict[str, Any]], used_refs: set[str]
) -> dict[str, Any] | None:
    expected = _normalize_cell(text)
    choices = [
        item for item in production_words
        if str(item.get("word_ref") or "") not in used_refs
        and _normalize_cell(item.get("text")) == expected
        and item.get("bbox")
    ]
    if not choices:
        return None
    source = fitz.Rect(bbox)
    return min(
        choices,
        key=lambda item: abs(fitz.Rect(item["bbox"]).x0 - source.x0) + abs(fitz.Rect(item["bbox"]).y0 - source.y0),
    )


def _vlm_jobs(
    references: list[dict[str, Any]], *, primary_dpi: int, sensitivity_dpi: int, repeat_count: int
) -> list[dict[str, Any]]:
    jobs = []
    for reference in references:
        key = reference["table_key"]
        for arm in ("raster", "hybrid"):
            jobs.append({"table_key": key, "arm": arm, "dpi": primary_dpi, "run_ordinal": 1})
            if key in DEFAULT_SENSITIVITY_KEYS:
                jobs.append({"table_key": key, "arm": arm, "dpi": sensitivity_dpi, "run_ordinal": 1})
            if key in DEFAULT_REPEAT_KEYS:
                for repeat in range(2, max(2, repeat_count) + 1):
                    jobs.append({"table_key": key, "arm": arm, "dpi": primary_dpi, "run_ordinal": repeat})
    return jobs


def _run_raster_call(
    *, session: requests.Session, base_url: str, model_id: str, reference: dict[str, Any], crop: dict[str, Any], timeout: int
) -> dict[str, Any]:
    schema = _raster_schema(reference["table_key"])
    prompt = (
        "Extract the complete visible table exactly. Detect its row and column structure. "
        "Preserve headers, numbering rows, totals, empty cells, digits, signs and decimal separators. "
        "Do not calculate, normalize or invent. Return only the required JSON."
    )
    parsed, safe_call, response = _call_vlm(
        session=session,
        base_url=base_url,
        model_id=model_id,
        prompt=prompt,
        schema=schema,
        schema_name="broker_reports_raster_table_output_v1",
        crop=crop,
        timeout=timeout,
    )
    validation_error = _validate_raster_output(parsed, reference["table_key"])
    if validation_error:
        safe_call["provider_status"] = "failed"
        safe_call["validation_error"] = validation_error
        scored_rows: list[dict[str, Any]] = []
    else:
        scored_rows = _dict_list(_object(parsed).get("rows"))
    predicted = [list(item.get("cells") or []) for item in scored_rows]
    header_rows = _leading_header_rows(scored_rows)
    score = _score_table(reference, predicted, header_rows)
    private = {
        "arm": "raster",
        "table_key": reference["table_key"],
        "dpi": crop["dpi"],
        "crop": crop,
        "parsed": parsed,
        "response": response,
        "score": score,
    }
    safe = {
        **safe_call,
        "arm": "raster",
        "table_key": reference["table_key"],
        "dpi": crop["dpi"],
        "score": score,
        "output_hash": _sha256(_canonical_bytes(parsed)),
        "provenance_level": "table_crop_only",
    }
    return {"private": private, "safe": safe}


def _run_hybrid_call(
    *, session: requests.Session, base_url: str, model_id: str, reference: dict[str, Any], crop: dict[str, Any], candidates: list[dict[str, Any]], timeout: int
) -> dict[str, Any]:
    schema = _hybrid_schema(reference["table_key"], [item["candidate_id"] for item in candidates])
    candidate_json = json.dumps(candidates, ensure_ascii=False, separators=(",", ":"))
    prompt = (
        "Interpret the table image, but construct every non-empty cell only by selecting candidate ids from the supplied "
        "ordered word list. Preserve empty cells as empty candidate-id arrays. Do not return or invent financial values. "
        "Return rows and cells in visual order using only the required JSON. Candidate list: " + candidate_json
    )
    parsed, safe_call, response = _call_vlm(
        session=session,
        base_url=base_url,
        model_id=model_id,
        prompt=prompt,
        schema=schema,
        schema_name="broker_reports_hybrid_table_binding_output_v1",
        crop=crop,
        timeout=timeout,
    )
    validation_error = _validate_hybrid_output(
        parsed,
        reference["table_key"],
        {item["candidate_id"] for item in candidates},
    )
    if validation_error:
        safe_call["provider_status"] = "failed"
        safe_call["validation_error"] = validation_error
    candidate_map = {item["candidate_id"]: item for item in candidates}
    invalid_ids = []
    predicted = []
    rows = [] if validation_error else _dict_list(_object(parsed).get("rows"))
    for row in rows:
        values = []
        for cell in _dict_list(row.get("cells")):
            ids = [str(value) for value in cell.get("candidate_ids") or []]
            invalid_ids.extend(value for value in ids if value not in candidate_map)
            values.append(" ".join(candidate_map[value]["text"] for value in ids if value in candidate_map))
        predicted.append(values)
    header_rows = _leading_header_rows(rows)
    score = _score_table(reference, predicted, header_rows)
    score["invalid_candidate_ids"] = len(invalid_ids)
    private = {
        "arm": "hybrid",
        "table_key": reference["table_key"],
        "dpi": crop["dpi"],
        "crop": crop,
        "parsed": parsed,
        "materialized_grid": predicted,
        "candidate_hash": _sha256(_canonical_bytes(candidates)),
        "response": response,
        "score": score,
    }
    safe = {
        **safe_call,
        "arm": "hybrid",
        "table_key": reference["table_key"],
        "dpi": crop["dpi"],
        "score": score,
        "output_hash": _sha256(_canonical_bytes(parsed)),
        "candidate_count": len(candidates),
        "candidate_bytes": len(candidate_json.encode()),
        "provenance_level": "candidate_bound_word_level",
    }
    return {"private": private, "safe": safe}


def _call_vlm(
    *, session: requests.Session, base_url: str, model_id: str, prompt: str, schema: dict[str, Any], schema_name: str, crop: dict[str, Any], timeout: int
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    image_bytes = Path(crop["path"]).read_bytes()
    body = {
        "model": model_id,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(image_bytes).decode(), "detail": "high"}},
            ],
        }],
        "stream": False,
        "temperature": 0,
        "max_tokens": 12000,
        "response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "strict": True, "schema": schema}},
    }
    started = time.perf_counter()
    response = session.post(_url(base_url, "/api/chat/completions"), json=body, timeout=timeout)
    duration = time.perf_counter() - started
    try:
        data = response.json()
    except Exception:
        data = {}
    parsed: Any = None
    parse_error = None
    if response.ok:
        content = _object((_dict_list(data.get("choices")) or [{}])[0].get("message")).get("content")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
        except Exception as exc:
            parse_error = type(exc).__name__
    usage = _object(data.get("usage"))
    safe = {
        "http_status": response.status_code,
        "provider_status": "passed" if response.ok and isinstance(parsed, dict) else "failed",
        "parse_error": parse_error,
        "duration_seconds": round(duration, 3),
        "model_id": model_id,
        "image_bytes": len(image_bytes),
        "image_width": crop["width"],
        "image_height": crop["height"],
        "prompt_bytes": len(prompt.encode()),
        "schema_bytes": len(_canonical_bytes(schema)),
        "request_json_bytes": len(_canonical_bytes(body)),
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "response_id_present": bool(data.get("id")),
    }
    if not response.ok:
        safe["error_class"] = "http_error"
    return parsed, safe, data


ROW_KINDS = {"header", "column_numbers", "data", "section", "subtotal", "total", "unknown"}


def _validate_raster_output(value: Any, table_key: str) -> str | None:
    data = _object(value)
    if not data:
        return "output_not_object"
    if data.get("schema_version") != RASTER_OUTPUT_SCHEMA or data.get("table_key") != table_key:
        return "output_identity_mismatch"
    if not isinstance(data.get("warnings"), list) or not all(isinstance(item, str) for item in data["warnings"]):
        return "warnings_not_string_array"
    rows = data.get("rows")
    if not isinstance(rows, list):
        return "rows_not_array"
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"cells", "row_kind", "uncertainty"}:
            return "row_shape_invalid"
        if row.get("row_kind") not in ROW_KINDS:
            return "row_kind_invalid"
        if not isinstance(row.get("cells"), list) or not all(isinstance(item, str) for item in row["cells"]):
            return "cells_not_string_array"
        if not isinstance(row.get("uncertainty"), list) or not all(isinstance(item, str) for item in row["uncertainty"]):
            return "uncertainty_not_string_array"
    return None


def _validate_hybrid_output(value: Any, table_key: str, candidate_ids: set[str]) -> str | None:
    data = _object(value)
    if not data:
        return "output_not_object"
    if data.get("schema_version") != HYBRID_OUTPUT_SCHEMA or data.get("table_key") != table_key:
        return "output_identity_mismatch"
    if not isinstance(data.get("warnings"), list) or not all(isinstance(item, str) for item in data["warnings"]):
        return "warnings_not_string_array"
    rows = data.get("rows")
    if not isinstance(rows, list):
        return "rows_not_array"
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"cells", "row_kind"}:
            return "row_shape_invalid"
        if row.get("row_kind") not in ROW_KINDS or not isinstance(row.get("cells"), list):
            return "row_kind_or_cells_invalid"
        for cell in row["cells"]:
            if not isinstance(cell, dict) or set(cell) != {"candidate_ids", "uncertainty"}:
                return "cell_shape_invalid"
            selected = cell.get("candidate_ids")
            uncertainty = cell.get("uncertainty")
            if not isinstance(selected, list) or not all(isinstance(item, str) for item in selected):
                return "candidate_ids_not_string_array"
            if any(item not in candidate_ids for item in selected):
                return "candidate_id_outside_enum"
            if not isinstance(uncertainty, list) or not all(isinstance(item, str) for item in uncertainty):
                return "uncertainty_not_string_array"
    return None


def _raster_schema(table_key: str) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "enum": [RASTER_OUTPUT_SCHEMA]},
            "table_key": {"type": "string", "enum": [table_key]},
            "rows": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "cells": {"type": "array", "items": {"type": "string"}},
                    "row_kind": {"type": "string", "enum": ["header", "column_numbers", "data", "section", "subtotal", "total", "unknown"]},
                    "uncertainty": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["cells", "row_kind", "uncertainty"],
            }},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["schema_version", "table_key", "rows", "warnings"],
    }


def _hybrid_schema(table_key: str, candidate_ids: list[str]) -> dict[str, Any]:
    candidate_item = {"type": "string", "enum": candidate_ids} if candidate_ids else {"type": "string", "enum": ["no_candidate_available"]}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "enum": [HYBRID_OUTPUT_SCHEMA]},
            "table_key": {"type": "string", "enum": [table_key]},
            "rows": {"type": "array", "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "cells": {"type": "array", "items": {
                        "type": "object", "additionalProperties": False,
                        "properties": {
                            "candidate_ids": {"type": "array", "items": candidate_item},
                            "uncertainty": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["candidate_ids", "uncertainty"],
                    }},
                    "row_kind": {"type": "string", "enum": ["header", "column_numbers", "data", "section", "subtotal", "total", "unknown"]},
                },
                "required": ["cells", "row_kind"],
            }},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["schema_version", "table_key", "rows", "warnings"],
    }


def _score_table(reference: dict[str, Any], predicted: list[list[str]], predicted_header_rows: int) -> dict[str, Any]:
    expected = reference["cells"]
    row_count = max(len(expected), len(predicted))
    column_count = max(
        max((len(row) for row in expected), default=0),
        max((len(row) for row in predicted), default=0),
    )
    pairs = []
    for row in range(row_count):
        for column in range(column_count):
            left = expected[row][column] if row < len(expected) and column < len(expected[row]) else ""
            right = predicted[row][column] if row < len(predicted) and column < len(predicted[row]) else ""
            pairs.append((_normalize_cell(left), _normalize_cell(right)))
    numeric = [pair for pair in pairs if _is_numeric(pair[0])]
    exact = sum(left == right for left, right in pairs)
    numeric_exact = sum(left == right for left, right in numeric)
    return {
        "rows_expected": len(expected),
        "rows_actual": len(predicted),
        "columns_expected": max((len(row) for row in expected), default=0),
        "columns_actual": max((len(row) for row in predicted), default=0),
        "structure_exact": len(expected) == len(predicted) and all(len(left) == len(right) for left, right in zip(expected, predicted)),
        "cells_exact": exact,
        "cells_total": len(pairs),
        "cell_accuracy": round(exact / len(pairs), 6) if pairs else 1.0,
        "numeric_exact": numeric_exact,
        "numeric_total": len(numeric),
        "numeric_accuracy": round(numeric_exact / len(numeric), 6) if numeric else 1.0,
        "header_rows_expected": int(reference.get("header_rows") or 0),
        "header_rows_actual": predicted_header_rows,
        "header_structure_exact": int(reference.get("header_rows") or 0) == predicted_header_rows,
        "hallucinated_nonempty_cells": sum(not left and bool(right) for left, right in pairs),
        "omitted_nonempty_cells": sum(bool(left) and not right for left, right in pairs),
    }


def _aggregate_scores(scores: list[dict[str, Any]]) -> dict[str, Any]:
    cells = sum(int(item.get("cells_total") or 0) for item in scores)
    numerics = sum(int(item.get("numeric_total") or 0) for item in scores)
    return {
        "tables_total": len(scores),
        "structure_exact_tables": sum(item.get("structure_exact") is True for item in scores),
        "header_exact_tables": sum(item.get("header_structure_exact") is True for item in scores),
        "cells_exact": sum(int(item.get("cells_exact") or 0) for item in scores),
        "cells_total": cells,
        "cell_accuracy": round(sum(int(item.get("cells_exact") or 0) for item in scores) / cells, 6) if cells else 0.0,
        "numeric_exact": sum(int(item.get("numeric_exact") or 0) for item in scores),
        "numeric_total": numerics,
        "numeric_accuracy": round(sum(int(item.get("numeric_exact") or 0) for item in scores) / numerics, 6) if numerics else 0.0,
        "hallucinated_nonempty_cells": sum(int(item.get("hallucinated_nonempty_cells") or 0) for item in scores),
        "omitted_nonempty_cells": sum(int(item.get("omitted_nonempty_cells") or 0) for item in scores),
    }


def _aggregate_vlm(runs: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for arm in ("raster", "hybrid"):
        values = [item for item in runs if item.get("arm") == arm]
        primary = [item for item in values if int(item.get("run_ordinal") or 0) == 1 and int(item.get("dpi") or 0) == 150]
        output_groups: dict[tuple[str, int], set[str]] = {}
        for item in values:
            key = (str(item.get("table_key")), int(item.get("dpi") or 0))
            output_groups.setdefault(key, set()).add(str(item.get("output_hash") or ""))
        result[arm] = {
            "calls_total": len(values),
            "passed_calls": sum(item.get("provider_status") == "passed" for item in values),
            "primary_score": _aggregate_scores([item["score"] for item in primary]),
            "input_tokens": sum(int(item.get("input_tokens") or 0) for item in values),
            "output_tokens": sum(int(item.get("output_tokens") or 0) for item in values),
            "model_input_image_bytes": sum(int(item.get("image_bytes") or 0) for item in values),
            "model_input_text_bytes": sum(int(item.get("prompt_bytes") or 0) for item in values),
            "model_input_schema_bytes": sum(int(item.get("schema_bytes") or 0) for item in values),
            "request_json_bytes": sum(int(item.get("request_json_bytes") or 0) for item in values),
            "repeat_groups_with_identical_hash": sum(len(hashes) == 1 for hashes in output_groups.values()),
            "repeat_groups_total": len(output_groups),
        }
    return result


def _experiment_status(*, skip_vlm: bool, runs: list[dict[str, Any]], expected_jobs: int) -> str:
    if len(runs) == expected_jobs:
        return "passed" if all(item.get("provider_status") == "passed" for item in runs) else "completed_with_failures"
    if skip_vlm and not runs:
        return "deterministic_only"
    return "partial_resume" if skip_vlm else "blocked"


def _failed_vlm_outcome(
    *, job: dict[str, Any], reference: dict[str, Any], crop: dict[str, Any], model_id: str, exc: Exception
) -> dict[str, Any]:
    score = _score_table(reference, [], 0)
    error_class = type(exc).__name__
    return {
        "private": {
            "arm": job["arm"],
            "table_key": job["table_key"],
            "dpi": job["dpi"],
            "crop": crop,
            "parsed": None,
            "response": None,
            "score": score,
            "error_class": error_class,
        },
        "safe": {
            "arm": job["arm"],
            "table_key": job["table_key"],
            "dpi": job["dpi"],
            "http_status": None,
            "provider_status": "failed",
            "error_class": error_class,
            "model_id": model_id,
            "image_bytes": int(crop.get("png_bytes") or 0),
            "image_width": int(crop.get("width") or 0),
            "image_height": int(crop.get("height") or 0),
            "prompt_bytes": 0,
            "schema_bytes": 0,
            "request_json_bytes": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "response_id_present": False,
            "score": score,
            "output_hash": _sha256(b"failed"),
            "provenance_level": "none_provider_failed",
        },
    }


def _revalidate_checkpoint(
    item: dict[str, Any],
    *,
    references: dict[str, dict[str, Any]],
    candidates_by_table: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    private = _object(item.get("private"))
    safe = _object(item.get("safe"))
    arm = str(private.get("arm") or safe.get("arm") or "")
    table_key = str(private.get("table_key") or safe.get("table_key") or "")
    reference = references.get(table_key)
    if reference is None or arm not in {"raster", "hybrid"}:
        safe["provider_status"] = "failed"
        safe["validation_error"] = "checkpoint_identity_invalid"
        return {"private": private, "safe": safe}

    parsed = private.get("parsed")
    if arm == "raster":
        validation_error = _validate_raster_output(parsed, table_key)
        rows = [] if validation_error else _dict_list(_object(parsed).get("rows"))
        predicted = [list(row.get("cells") or []) for row in rows]
    else:
        candidates = candidates_by_table.get(table_key, [])
        candidate_map = {item["candidate_id"]: item for item in candidates}
        validation_error = _validate_hybrid_output(parsed, table_key, set(candidate_map))
        rows = [] if validation_error else _dict_list(_object(parsed).get("rows"))
        predicted = [
            [
                " ".join(candidate_map[value]["text"] for value in cell.get("candidate_ids") or [])
                for cell in _dict_list(row.get("cells"))
            ]
            for row in rows
        ]

    score = _score_table(reference, predicted, _leading_header_rows(rows))
    if arm == "hybrid":
        score["invalid_candidate_ids"] = 0 if not validation_error else 1
    private["score"] = score
    safe["score"] = score
    http_status = safe.get("http_status")
    http_passed = isinstance(http_status, int) and 200 <= http_status < 300
    if validation_error:
        safe["provider_status"] = "failed"
        safe["validation_error"] = validation_error
    elif http_passed:
        safe["provider_status"] = "passed"
        safe.pop("validation_error", None)
    else:
        safe["provider_status"] = "failed"
    return {"private": private, "safe": safe}


def _compact_vlm_artifact(
    *, arm: str, pdf_sha256: str, model_id: str, runs: list[dict[str, Any]], candidates_by_table: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    selected = [item for item in runs if item.get("arm") == arm and item.get("run_ordinal") == 1 and item.get("dpi") == 150]
    tables = []
    for item in selected:
        value = {
            "table_key": item.get("table_key"),
            "page": _object(item.get("crop")).get("page"),
            "bbox": _object(item.get("crop")).get("bbox"),
            "crop_sha256": _object(item.get("crop")).get("png_sha256"),
            "model_id": model_id,
            "output_hash": _sha256(_canonical_bytes(item.get("parsed"))),
            "score": item.get("score"),
        }
        if arm == "raster":
            value["rows"] = _object(item.get("parsed")).get("rows") or []
            value["provenance"] = "document_page_table_crop"
        else:
            binding_rows = _object(item.get("parsed")).get("rows") or []
            used_ids = {
                str(candidate_id)
                for row in _dict_list(binding_rows)
                for cell in _dict_list(row.get("cells"))
                for candidate_id in cell.get("candidate_ids") or []
            }
            evidence = [
                candidate
                for candidate in candidates_by_table.get(str(item.get("table_key")), [])
                if candidate["candidate_id"] in used_ids
            ]
            value["binding_rows"] = binding_rows
            value["candidate_evidence"] = evidence
            value["model_candidate_projection_hash"] = item.get("candidate_hash")
            value["permanent_candidate_evidence_hash"] = _sha256(
                _canonical_bytes(candidates_by_table.get(str(item.get("table_key")), []))
            )
            value["provenance"] = "document_page_table_crop_and_word_candidate_ids"
        tables.append(value)
    return {
        "schema_version": f"broker_reports_pdf_{arm}_compact_experiment_v1",
        "pdf_sha256": pdf_sha256,
        "model_id": model_id,
        "tables": tables,
    }


def _safe_crop_summary(crops: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    values = list(crops.values())
    return {
        "crops_total": len(values),
        "png_bytes_total": sum(item["png_bytes"] for item in values),
        "by_dpi": dict(sorted(Counter(str(item["dpi"]) for item in values).items())),
        "max_crop_bytes": max((item["png_bytes"] for item in values), default=0),
        "max_dimensions": {
            "width": max((item["width"] for item in values), default=0),
            "height": max((item["height"] for item in values), default=0),
        },
    }


def _best_reference(references: dict[str, dict[str, Any]], page: int, bbox: Any) -> dict[str, Any] | None:
    if not bbox or not page:
        return None
    choices = [item for item in references.values() if item["page"] == page]
    return max(choices, key=lambda item: _bbox_iou(item["bbox"], bbox), default=None)


def _bbox_iou(left: Any, right: Any) -> float:
    a = fitz.Rect(left)
    b = fitz.Rect(right)
    intersection = a & b
    if intersection.is_empty:
        return 0.0
    intersection_area = max(0.0, intersection.width) * max(0.0, intersection.height)
    left_area = max(0.0, a.width) * max(0.0, a.height)
    right_area = max(0.0, b.width) * max(0.0, b.height)
    union = left_area + right_area - intersection_area
    return intersection_area / union if union else 0.0


def _normalize_bbox(value: Any, scope: fitz.Rect) -> list[float]:
    bbox = fitz.Rect(value)
    width = scope.width or 1.0
    height = scope.height or 1.0
    return [
        round((bbox.x0 - scope.x0) / width, 6),
        round((bbox.y0 - scope.y0) / height, 6),
        round((bbox.x1 - scope.x0) / width, 6),
        round((bbox.y1 - scope.y0) / height, 6),
    ]


def _leading_header_rows(rows: list[dict[str, Any]]) -> int:
    count = 0
    for row in rows:
        if row.get("row_kind") in {"header", "column_numbers"}:
            count += 1
        else:
            break
    return count


def _collect_visible_text(value: Any, output: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"text", "normalized_value"} and isinstance(item, str):
                output.append(item)
            else:
                _collect_visible_text(item, output)
    elif isinstance(value, list):
        for item in value:
            _collect_visible_text(item, output)


def _node_counts(value: Any) -> dict[str, int]:
    counts = {"objects": 0, "arrays": 0, "strings": 0}
    def walk(item: Any) -> None:
        if isinstance(item, dict):
            counts["objects"] += 1
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            counts["arrays"] += 1
            for child in item:
                walk(child)
        elif isinstance(item, str):
            counts["strings"] += 1
    walk(value)
    return counts


def _size_metrics(value: Any) -> dict[str, int]:
    raw = _canonical_bytes(value)
    nodes = _node_counts(value)
    return {
        "json_bytes": len(raw),
        "gzip_bytes": len(gzip.compress(raw, compresslevel=9)),
        **nodes,
    }


def _normalize_cell(value: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or ""))).strip()


def _is_numeric(value: str) -> bool:
    return bool(re.fullmatch(r"[+\-]?[\d\s]+(?:[.,]\d+)?", value))


def _aggregate(values: list[float]) -> float:
    return round(sum(values) / len(values), 6) if values else 0.0


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


if __name__ == "__main__":
    raise SystemExit(main())
