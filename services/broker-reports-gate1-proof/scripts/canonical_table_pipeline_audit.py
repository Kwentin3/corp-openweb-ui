#!/usr/bin/env python3
"""Research-only audit of the PDF table path before financial mapping."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.pdf_table_locator_provider import (  # noqa: E402
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from local_pdf_vlm_guided_intake_development import (  # noqa: E402
    _openwebui_request,
)


SCHEMA_VERSION = "broker_reports_table_pipeline_visual_audit_v1"
FREEZE_VERSION = "broker_reports_table_pipeline_visual_freeze_v1"
RESULT_VERSION = "broker_reports_table_pipeline_visual_result_v1"
SAFE_RESULT_VERSION = "broker_reports_table_pipeline_visual_result_safe_v1"
STATIC_AUDIT_VERSION = "broker_reports_table_pipeline_static_audit_v1"
MODEL_ID = "models/gemini-3.5-flash"
PROVIDER_PROFILE = "google_gemini"

FACTORY_REQUIRED = (
    "PdfGridExperimentProviderFactory.create_for_openwebui owns the bounded "
    "research-only image call"
)
FORBIDDEN = (
    "product activation, Canonical mutation, financial fact publication, retry, "
    "repair, best-of-N, broker or filename routing, regex semantics"
)


class TablePipelineAuditError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def visual_response_schema() -> dict[str, Any]:
    """Return the closed visual-audit response contract."""

    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "document_purpose",
            "tax_data_scope",
            "table_purpose",
            "header_bands",
            "columns",
            "data_rows",
            "financial_rows",
            "explanation_markers",
            "summary",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "document_purpose": {
                "type": "string",
                "enum": [
                    "CUSTOMER_BROKER_REPORT",
                    "CLIENT_GUIDE_OR_SAMPLE",
                    "BROKER_CORPORATE_FINANCIAL_STATEMENT",
                    "INVESTMENT_PRODUCT_FACTSHEET",
                    "OTHER",
                    "UNCERTAIN",
                ],
            },
            "tax_data_scope": {
                "type": "string",
                "enum": [
                    "CUSTOMER_TRANSACTION_DATA",
                    "EXPLANATORY_ONLY",
                    "NOT_CUSTOMER_TAX_SOURCE",
                    "UNCERTAIN",
                ],
            },
            "table_purpose": {
                "type": "string",
                "enum": [
                    "TRANSACTION_DATA",
                    "EXPLANATORY_EXAMPLE",
                    "CORPORATE_OR_PRODUCT_DATA",
                    "OTHER",
                    "UNCERTAIN",
                ],
            },
            "header_bands": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                },
                "maxItems": 8,
            },
            "columns": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 128,
            },
            "data_rows": {"type": "integer", "minimum": 0},
            "financial_rows": {"type": "integer", "minimum": 0},
            "explanation_markers": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 32,
            },
            "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
        },
    }


def visual_model_view(case_id: str) -> dict[str, Any]:
    """Build a generic image-only task without source-specific hints."""

    if not case_id:
        raise TablePipelineAuditError("table_pipeline_case_id_required")
    return {
        "task_version": "table_pipeline_visual_understanding_v1",
        "case_ref": case_id,
        "input": "ONE_PNG_TABLE_REGION",
        "instruction": (
            "Inspect only the attached pixels. First decide whether the document "
            "is an actual customer broker report, a guide/sample explaining how to "
            "read a report, a broker corporate financial statement, an investment "
            "product factsheet, or something else. Then describe the visible table "
            "structure. Preserve the visible left-to-right column meaning, including "
            "multi-line or multi-band headers. Count visible data rows and financial "
            "transaction rows. Do not invent missing text, values, facts, or tax "
            "meaning. A numbered legend, explanatory callout, sample watermark, or "
            "surrounding how-to prose is evidence of an explanatory example, not a "
            "customer transaction. Return only the required JSON object."
        ),
    }


def validate_visual_output(value: Any) -> dict[str, Any]:
    errors = sorted(
        Draft202012Validator(visual_response_schema()).iter_errors(value),
        key=lambda item: list(item.path),
    )
    if errors:
        raise TablePipelineAuditError("table_pipeline_visual_response_invalid")
    return copy.deepcopy(value)


def load_canonical_payload(path: Path) -> dict[str, Any]:
    """Load either a single-payload or chunked Canonical physical payload."""

    value = _read_object(path)
    if isinstance(value.get("artifact"), dict):
        return copy.deepcopy(value["artifact"])
    if value.get("schema_version") != "canonical_physical_manifest_v1":
        raise TablePipelineAuditError("table_pipeline_canonical_payload_invalid")
    envelope = value.get("envelope")
    if not isinstance(envelope, dict) or not isinstance(envelope.get("chunks"), list):
        raise TablePipelineAuditError("table_pipeline_canonical_manifest_invalid")
    artifact = copy.deepcopy(envelope)
    artifact["containers"] = []
    artifact["nodes"] = []
    artifact["provenance"] = []
    artifact["issues"] = []
    for chunk in envelope["chunks"]:
        content_ref = str((chunk or {}).get("content_ref") or "")
        if not content_ref:
            continue
        payload = _read_object(path.parent / f"{content_ref}.json")
        for key in ("containers", "nodes", "provenance", "issues"):
            items = payload.get(key)
            if isinstance(items, list):
                artifact[key].extend(copy.deepcopy(items))
    return artifact


def static_canonical_audit(canonical: dict[str, Any]) -> dict[str, Any]:
    """Measure what Canonical preserves and what the naive continuation rule does."""

    containers = {
        str(item.get("container_id") or ""): item
        for item in canonical.get("containers") or []
        if isinstance(item, dict)
    }
    tables: list[dict[str, Any]] = []
    for node in canonical.get("nodes") or []:
        if not isinstance(node, dict) or node.get("node_type") != "TABLE":
            continue
        content = node.get("content") or {}
        metadata = content.get("metadata") or {}
        cells = content.get("cells") or []
        container = containers.get(str(node.get("container_ref") or ""), {})
        page = int(((container.get("metadata") or {}).get("page_number") or 0))
        tables.append(
            {
                "table_node_id": str(node.get("node_id") or ""),
                "page": page,
                "order": int(node.get("order") or 0),
                "columns": max(
                    (int(item.get("column") or 0) for item in cells if isinstance(item, dict)),
                    default=0,
                ),
                "rows": max(
                    (int(item.get("row") or 0) for item in cells if isinstance(item, dict)),
                    default=0,
                ),
                "canonical_header_present": bool(content.get("header")),
                "logical_table_id": metadata.get("logical_table_id"),
                "continuation": copy.deepcopy(metadata.get("continuation") or {}),
            }
        )
    tables.sort(key=lambda item: (item["page"], item["order"], item["table_node_id"]))
    naive = []
    for previous, current in zip(tables, tables[1:]):
        if not current["canonical_header_present"]:
            naive.append(
                {
                    "previous_table_node_id": previous["table_node_id"],
                    "following_table_node_id": current["table_node_id"],
                    "same_page": previous["page"] == current["page"],
                    "same_column_count": previous["columns"] == current["columns"],
                }
            )
    exact_groups: dict[str, list[str]] = {}
    for table in tables:
        logical_id = table.get("logical_table_id")
        if logical_id:
            exact_groups.setdefault(str(logical_id), []).append(table["table_node_id"])
    return {
        "schema_version": STATIC_AUDIT_VERSION,
        "tables_total": len(tables),
        "canonical_header_present": sum(
            item["canonical_header_present"] for item in tables
        ),
        "canonical_header_absent": sum(
            not item["canonical_header_present"] for item in tables
        ),
        "naive_headerless_continuation_candidates": len(naive),
        "naive_same_page_candidates": sum(item["same_page"] for item in naive),
        "naive_same_column_candidates": sum(
            item["same_column_count"] for item in naive
        ),
        "exact_mechanical_continuation_groups": len(exact_groups),
        "exact_mechanical_continuation_nodes": sum(map(len, exact_groups.values())),
        "tables": tables,
        "naive_candidates": naive,
        "exact_groups": exact_groups,
    }


def pdfplumber_variant_audit(
    *, pdf_path: Path, page_number: int, bbox: list[float]
) -> dict[str, Any]:
    """Compare only the relevant pdfplumber text-grid setting."""

    import pdfplumber  # noqa: PLC0415

    if page_number < 1 or len(bbox) != 4:
        raise TablePipelineAuditError("table_pipeline_pdf_crop_invalid")
    variants = []
    with pdfplumber.open(pdf_path) as document:
        page = document.pages[page_number - 1].crop(tuple(bbox), strict=False)
        for minimum in (3, 2, 1):
            settings = {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "min_words_vertical": minimum,
                "min_words_horizontal": 1,
                "text_x_tolerance": 3,
                "text_y_tolerance": 3,
                "snap_tolerance": 3,
                "join_tolerance": 3,
                "intersection_tolerance": 3,
            }
            found = page.find_tables(table_settings=settings)
            variants.append(
                {
                    "min_words_vertical": minimum,
                    "tables": len(found),
                    "row_counts": [len(table.rows) for table in found],
                    "column_counts": [len(table.columns) for table in found],
                }
            )
    return {
        "schema_version": "broker_reports_pdfplumber_parameter_audit_v1",
        "pdf_sha256": _sha256_file(pdf_path),
        "page_number": page_number,
        "bbox": bbox,
        "variants": variants,
        "source_values_included": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    static = commands.add_parser("static-canonical")
    static.add_argument("--canonical-payload", type=Path, required=True)
    static.add_argument("--output", type=Path, required=True)

    plumber = commands.add_parser("pdfplumber-variants")
    plumber.add_argument("--pdf", type=Path, required=True)
    plumber.add_argument("--page", type=int, required=True)
    plumber.add_argument("--bbox", type=float, nargs=4, required=True)
    plumber.add_argument("--output", type=Path, required=True)

    freeze = commands.add_parser("freeze-visual")
    freeze.add_argument("--image", action="append", required=True)
    freeze.add_argument("--output", type=Path, required=True)

    execute = commands.add_parser("execute-visual")
    execute.add_argument("--freeze", type=Path, required=True)
    execute.add_argument("--private-output-root", type=Path, required=True)
    execute.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")

    args = parser.parse_args()
    if args.command == "static-canonical":
        result = static_canonical_audit(load_canonical_payload(args.canonical_payload))
        _write_new_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "pdfplumber-variants":
        result = pdfplumber_variant_audit(
            pdf_path=args.pdf.resolve(), page_number=args.page, bbox=args.bbox
        )
        _write_new_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "freeze-visual":
        _freeze_visual(args)
        return 0
    return _execute_visual(args)


def _freeze_visual(args: argparse.Namespace) -> None:
    if _git_status():
        raise TablePipelineAuditError("table_pipeline_clean_head_required")
    cases = []
    for raw in args.image:
        case_id, separator, path_text = raw.partition("=")
        path = Path(path_text).resolve()
        if not separator or not case_id or not path.is_file():
            raise TablePipelineAuditError("table_pipeline_image_argument_invalid")
        cases.append(
            {
                "case_id": case_id,
                "image_path": str(path),
                "image_sha256": _sha256_file(path),
                "image_bytes": path.stat().st_size,
                "model_view": visual_model_view(case_id),
            }
        )
    if len({item["case_id"] for item in cases}) != len(cases):
        raise TablePipelineAuditError("table_pipeline_case_id_duplicate")
    freeze = {
        "schema_version": FREEZE_VERSION,
        "source_head": _git_head(),
        "source_worktree_clean": True,
        "provider_profile": PROVIDER_PROFILE,
        "model_id": MODEL_ID,
        "response_schema": visual_response_schema(),
        "cases": cases,
        "scheduled_model_calls": len(cases),
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "product_activation": False,
    }
    freeze["freeze_sha256"] = _sha256_json(freeze)
    _write_new_json(args.output.resolve(), freeze)
    print(json.dumps(freeze, ensure_ascii=False, indent=2))


def _execute_visual(args: argparse.Namespace) -> int:
    freeze = _read_object(args.freeze.resolve())
    if (
        freeze.get("schema_version") != FREEZE_VERSION
        or freeze.get("freeze_sha256")
        != _sha256_json({key: value for key, value in freeze.items() if key != "freeze_sha256"})
        or freeze.get("source_head") != _git_head()
        or _git_status()
        or freeze.get("model_id") != MODEL_ID
        or freeze.get("provider_profile") != PROVIDER_PROFILE
    ):
        raise TablePipelineAuditError("table_pipeline_freeze_invalid_or_drifted")
    output_root = args.private_output_root.resolve()
    if output_root.exists() or _is_within(output_root, REPO_ROOT.resolve()):
        raise TablePipelineAuditError("table_pipeline_private_output_invalid")
    request = _openwebui_request(args.env_file.resolve())
    provider = PdfGridExperimentProviderFactory(
        PdfGridProviderConfig(
            provider_profile=PROVIDER_PROFILE,
            model_id=MODEL_ID,
            timeout_seconds=300,
            maximum_output_tokens=4096,
            maximum_counted_input_tokens=24_000,
            thinking_level="minimal",
        )
    ).create_for_openwebui(request)
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise TablePipelineAuditError("table_pipeline_provider_not_qualified")
    output_root.mkdir(parents=True)
    private_runs = []
    safe_runs = []
    for case in freeze["cases"]:
        image_path = Path(case["image_path"])
        if _sha256_file(image_path) != case["image_sha256"]:
            raise TablePipelineAuditError("table_pipeline_image_drift")
        response = provider.invoke(
            task_id=f"table_pipeline_visual_{case['case_id']}",
            model_view=case["model_view"],
            output_schema=freeze["response_schema"],
            png_bytes=image_path.read_bytes(),
            crop_sha256=case["image_sha256"],
            attempt_number=1,
            attempt_lineage=[],
        )
        error = None
        output = response.get("json_output")
        try:
            validated = validate_visual_output(output)
        except TablePipelineAuditError as exc:
            validated = None
            error = exc.code
        private_run = {
            "case_id": case["case_id"],
            "image_sha256": case["image_sha256"],
            "attempt": response.get("attempt"),
            "validated_output": validated,
            "validation_error": error,
            "raw_private_response": response.get("raw_private_response"),
            "response_hash": response.get("response_hash"),
        }
        private_runs.append(private_run)
        safe_runs.append(
            {
                "case_id": case["case_id"],
                "image_sha256": case["image_sha256"],
                "terminal": "VALIDATED" if validated is not None else "FAILED",
                "document_purpose": (validated or {}).get("document_purpose"),
                "tax_data_scope": (validated or {}).get("tax_data_scope"),
                "table_purpose": (validated or {}).get("table_purpose"),
                "columns": len((validated or {}).get("columns") or []),
                "header_bands": len((validated or {}).get("header_bands") or []),
                "data_rows": (validated or {}).get("data_rows"),
                "financial_rows": (validated or {}).get("financial_rows"),
                "provider_submission": 1,
                "retry": False,
                "manual_output_edit": False,
            }
        )
    result = {
        "schema_version": RESULT_VERSION,
        "freeze_sha256": freeze["freeze_sha256"],
        "source_head": freeze["source_head"],
        "qualification": qualification,
        "provider_submissions": len(private_runs),
        "scheduled_model_calls": freeze["scheduled_model_calls"],
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "product_activation": False,
        "runs": private_runs,
    }
    safe = {
        "schema_version": SAFE_RESULT_VERSION,
        "freeze_sha256": freeze["freeze_sha256"],
        "source_head": freeze["source_head"],
        "provider_submissions": len(private_runs),
        "scheduled_model_calls": freeze["scheduled_model_calls"],
        "all_validated": all(item["terminal"] == "VALIDATED" for item in safe_runs),
        "retry": False,
        "repair": False,
        "best_of_n": False,
        "manual_output_edit": False,
        "private_values_committed": False,
        "product_activation": False,
        "runs": safe_runs,
    }
    safe["receipt_sha256"] = _sha256_json(safe)
    _write_new_json(output_root / "result.private.json", result)
    _write_new_json(output_root / "result.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if safe["all_validated"] else 2


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TablePipelineAuditError("table_pipeline_json_object_required")
    return value


def _write_new_json(path: Path, value: Any) -> None:
    if path.exists():
        raise TablePipelineAuditError("table_pipeline_output_exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def _git_status() -> str:
    return subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
    ).strip()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
