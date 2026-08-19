#!/usr/bin/env python3
"""Run the research-only G5.100 development experiment once per page."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import struct
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pypdf
import requests

from broker_reports_gate1.pdf_grid_experiment_provider import (
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
)
from broker_reports_gate1.visual_pdfplumber_table_plan import (
    VisualPdfPlumberTableAdapterFactory,
    VisualPdfPlumberTablePlanError,
    validate_pdfplumber_table_plan,
)


SCRIPT_PATH = Path(__file__).resolve()
SERVICE_ROOT = SCRIPT_PATH.parent.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = (
    SERVICE_ROOT
    / "benchmarks"
    / "frozen_cross_document_breadcrumb_g599"
    / "manifest.json"
)
DEFAULT_SOURCE_MAP = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_frozen_cross_document_g599_2026-08-18"
    / "private"
    / "sources.private.json"
)
DEFAULT_IMAGE_ROOT = DEFAULT_SOURCE_MAP.parent
DEFAULT_PRIVATE_OUTPUT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_minimal_native_pdfplumber_g5100_2026-08-18"
    / "private"
    / "development.private.json"
)
DEFAULT_SAFE_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-18"
    / "BROKER_REPORTS_G5100_MINIMAL_NATIVE_PDFPLUMBER_DEVELOPMENT.safe.json"
)

PROMPT_TEMPLATE = """Inspect this one rendered PDF page. Return a strictly valid
configuration for pdfplumber 0.11.10 table extraction, not table content.

Image coordinates use a top-left origin: x grows right and y grows down. The image
is {image_width} by {image_height} pixels. The source PDF page is {pdf_width:.3f} by
{pdf_height:.3f} points. All coordinates you return are absolute image pixels; the
caller performs only independent x/y scaling into pdfplumber's (x0, top, x1,
bottom) coordinates.

For every visible data table or table continuation, in top-to-bottom order:
- bbox is a tight [x0, top, x1, bottom] crop containing that table only;
- vertical_strategy is always explicit;
- explicit_vertical_lines contains every column boundary from the left outer table
  content boundary through the right outer table content boundary, in increasing x;
- horizontal_strategy is lines when visible horizontal rules define rows, otherwise
  text for a borderless table.

Do not return cell values, body rows, text, labels, amounts, dates, financial roles,
summaries, tolerances, or any field outside the schema. Do not treat prose, lists,
aligned page furniture, or covers as tables. A continuation is still a table. Keep
multiple tables separate. If no visible data table exists, return {{"tables": []}}.
"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tables"],
    "properties": {
        "tables": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "bbox",
                    "vertical_strategy",
                    "explicit_vertical_lines",
                    "horizontal_strategy",
                ],
                "properties": {
                    "bbox": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {"type": "number"},
                    },
                    "vertical_strategy": {
                        "type": "string",
                        "enum": ["explicit"],
                    },
                    "explicit_vertical_lines": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 40,
                        "items": {"type": "number"},
                    },
                    "horizontal_strategy": {
                        "type": "string",
                        "enum": ["lines", "text"],
                    },
                },
            },
        }
    },
}


class G5100Error(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--source-map", default=str(DEFAULT_SOURCE_MAP))
    parser.add_argument("--image-root", default=str(DEFAULT_IMAGE_ROOT))
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--private-output", default=str(DEFAULT_PRIVATE_OUTPUT))
    parser.add_argument("--safe-output", default=str(DEFAULT_SAFE_OUTPUT))
    args = parser.parse_args(argv)
    result = run_development(
        manifest_path=Path(args.manifest),
        source_map_path=Path(args.source_map),
        image_root=Path(args.image_root),
        env_path=Path(args.env_file),
        private_output=Path(args.private_output),
        safe_output=Path(args.safe_output),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_development(
    *,
    manifest_path: Path,
    source_map_path: Path,
    image_root: Path,
    env_path: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    if private_output.exists() or safe_output.exists():
        raise G5100Error("g5100_outputs_already_exist")
    manifest = _read_object(manifest_path)
    source_map = _read_object(source_map_path).get("documents") or {}
    cases = list(manifest.get("unseen_holdout") or [])
    expected_by_case = _expected_table_counts()
    if {item["case_id"] for item in cases} != set(expected_by_case):
        raise G5100Error("g5100_g599_case_set_invalid")

    provider = _provider(env_path)
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise G5100Error("g5100_provider_not_qualified")
    adapter = VisualPdfPlumberTableAdapterFactory().create()
    results = []
    for case in cases:
        case_id = str(case["case_id"])
        document_id = str(case["document_id"])
        page_number = int(case["page"])
        source = source_map.get(document_id) or {}
        source_path = Path(str(source.get("path") or ""))
        source_bytes = source_path.read_bytes()
        if _sha256(source_bytes) != source.get("sha256"):
            raise G5100Error("g5100_source_hash_drift")
        image_path = (
            image_root
            / "documents"
            / document_id
            / "pages"
            / f"p{page_number:03d}.private.png"
        )
        png = image_path.read_bytes()
        if _sha256(png) != case.get("page_png_sha256"):
            raise G5100Error("g5100_page_image_hash_drift")
        image_width, image_height = _png_dimensions(png)
        page_pdf, pdf_width, pdf_height = _slice_page(source_bytes, page_number)
        prompt = PROMPT_TEMPLATE.format(
            image_width=image_width,
            image_height=image_height,
            pdf_width=pdf_width,
            pdf_height=pdf_height,
        )
        outcome = provider.invoke(
            task_id=f"g5100_{case_id}",
            model_view={"task": prompt},
            output_schema=copy.deepcopy(RESPONSE_SCHEMA),
            png_bytes=png,
            crop_sha256=case["page_png_sha256"],
            attempt_number=1,
            attempt_lineage=[],
        )
        plan = outcome.get("json_output")
        validation_error = None
        try:
            validate_pdfplumber_table_plan(
                plan,
                image_width_pixels=image_width,
                image_height_pixels=image_height,
            )
        except VisualPdfPlumberTablePlanError as exc:
            validation_error = exc.code
        execution = None
        execution_error = None
        if validation_error is None:
            try:
                execution = adapter.execute_single_page(
                    pdf_bytes=page_pdf,
                    image_width_pixels=image_width,
                    image_height_pixels=image_height,
                    plan=plan,
                    document_id=f"{document_id}_p{page_number:03d}",
                )
            except VisualPdfPlumberTablePlanError as exc:
                execution_error = exc.code
        results.append(
            {
                "case_id": case_id,
                "document_id": document_id,
                "page": page_number,
                "expected_visual_tables": expected_by_case[case_id],
                "image_dimensions": [image_width, image_height],
                "pdf_dimensions": [pdf_width, pdf_height],
                "page_png_sha256": case["page_png_sha256"],
                "page_pdf_sha256": _sha256(page_pdf),
                "plan": plan,
                "plan_validation_error": validation_error,
                "execution_error": execution_error,
                "execution": _compact_execution(execution),
                "attempt": outcome.get("attempt"),
                "response_hash": outcome.get("response_hash"),
                "raw_private_response": outcome.get("raw_private_response"),
            }
        )

    metrics = _metrics(results)
    terminals = _terminals(metrics)
    private = {
        "schema_version": "broker_reports_minimal_native_pdfplumber_g5100_development_private_v1",
        "goal": "G5.100",
        "phase": "development",
        "prompt_template": PROMPT_TEMPLATE,
        "response_schema": RESPONSE_SCHEMA,
        "prompt_sha256": _sha256_json(PROMPT_TEMPLATE),
        "response_schema_sha256": _sha256_json(RESPONSE_SCHEMA),
        "implementation_sha256": _sha256(SCRIPT_PATH.read_bytes()),
        "provider_policy": {
            "calls": len(cases),
            "attempts_per_page": 1,
            "retry": False,
            "best_of_n": False,
            "model_change": False,
            "body_values": 0,
        },
        "qualification": qualification,
        "results": results,
        "metrics": metrics,
        "terminals": terminals,
    }
    _write_json(private_output, private)
    safe = {
        "schema_version": "broker_reports_minimal_native_pdfplumber_g5100_development_safe_v1",
        "goal": "G5.100",
        "phase": "development",
        "pdfplumber_version": "0.11.10",
        "whitelist": [
            "crop/bbox",
            "vertical_strategy=explicit",
            "explicit_vertical_lines",
            "horizontal_strategy=lines|text",
        ],
        "tolerance_knobs": 0,
        "provider_calls": len(cases),
        "metrics": metrics,
        "terminals": terminals,
        "freeze_permitted": terminals == [
            "MINIMAL_NATIVE_PDFPLUMBER_VLM_CONTRACT_PROVEN",
            "VLM_DIRECTLY_CONFIGURES_NATIVE_TABLE_EXTRACTION",
            "SOURCE_LITERAL_AUTHORITY_PRESERVED",
            "WHOLE_PAGE_CANONICAL_ASSEMBLY_PROVEN",
            "CUSTOM_TABLE_RESOLVER_COMPLEXITY_REDUCED",
        ],
        "private_file_sha256": _sha256_json(private),
        "privacy": {
            "customer_bytes_in_git": False,
            "raw_provider_response_in_git": False,
            "cell_values_in_git": False,
        },
    }
    _write_json(safe_output, safe)
    return {"status": "complete", "metrics": metrics, "terminals": terminals}


def _compact_execution(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "terminal": value.get("terminal"),
        "reason": value.get("reason"),
        "tables": value.get("tables"),
        "native_table_shapes": [
            {
                "rows": item.get("rows_total"),
                "columns": item.get("columns_total"),
                "cells": item.get("cells_total"),
                "source_words": len(item.get("contributing_word_parser_ordinals") or []),
            }
            for item in value.get("native_tables") or []
        ],
        "canonical_metrics": value.get("canonical_metrics"),
        "vlm_body_values_used": value.get("vlm_body_values_used", 0),
        "invented_source_literals": value.get("invented_source_literals", 0),
        "parser": value.get("parser"),
    }


def _metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    expected_total = sum(item["expected_visual_tables"] for item in results)
    proposed_total = sum(len((item.get("plan") or {}).get("tables") or []) for item in results)
    extracted_total = sum(
        len((item.get("execution") or {}).get("native_table_shapes") or []) for item in results
    )
    negatives = [item for item in results if item["expected_visual_tables"] == 0]
    canonical = [
        (item.get("execution") or {}).get("canonical_metrics") or {} for item in results
    ]
    return {
        "pages": len(results),
        "expected_visual_tables": expected_total,
        "proposed_tables": proposed_total,
        "native_tables_extracted": extracted_total,
        "pages_with_exact_plan_count": sum(
            len((item.get("plan") or {}).get("tables") or [])
            == item["expected_visual_tables"]
            for item in results
        ),
        "pages_with_exact_native_count": sum(
            len((item.get("execution") or {}).get("native_table_shapes") or [])
            == item["expected_visual_tables"]
            for item in results
        ),
        "false_table_plans_on_negative_pages": sum(
            len((item.get("plan") or {}).get("tables") or []) for item in negatives
        ),
        "invalid_plans": sum(item.get("plan_validation_error") is not None for item in results),
        "execution_errors": sum(item.get("execution_error") is not None for item in results),
        "non_success_terminals": sum(
            (item.get("execution") or {}).get("terminal")
            not in {"NATIVE_TABLE_EXTRACTED", "NO_TABLE_PLAN"}
            for item in results
        ),
        "canonical_pages_valid": sum(item.get("canonical_valid") is True for item in canonical),
        "canonical_pages_exactly_accounted": sum(
            item.get("source_atom_accounting_percent") == 100.0
            and item.get("unresolved_source_atoms_total") == 0
            and item.get("layout_duplicate_refs") == 0
            and item.get("layout_unaccounted_refs") == 0
            for item in canonical
        ),
        "vlm_body_values_used": sum(
            int((item.get("execution") or {}).get("vlm_body_values_used") or 0)
            for item in results
        ),
        "invented_source_literals": sum(
            int((item.get("execution") or {}).get("invented_source_literals") or 0)
            for item in results
        ),
    }


def _terminals(metrics: dict[str, Any]) -> list[str]:
    exact = (
        metrics["expected_visual_tables"] == metrics["native_tables_extracted"]
        and metrics["pages_with_exact_native_count"] == metrics["pages"]
        and metrics["false_table_plans_on_negative_pages"] == 0
        and metrics["invalid_plans"] == 0
        and metrics["execution_errors"] == 0
        and metrics["non_success_terminals"] == 0
        and metrics["canonical_pages_exactly_accounted"] == metrics["pages"]
        and metrics["vlm_body_values_used"] == 0
        and metrics["invented_source_literals"] == 0
    )
    if exact:
        return [
            "MINIMAL_NATIVE_PDFPLUMBER_VLM_CONTRACT_PROVEN",
            "VLM_DIRECTLY_CONFIGURES_NATIVE_TABLE_EXTRACTION",
            "SOURCE_LITERAL_AUTHORITY_PRESERVED",
            "WHOLE_PAGE_CANONICAL_ASSEMBLY_PROVEN",
            "CUSTOM_TABLE_RESOLVER_COMPLEXITY_REDUCED",
        ]
    if metrics["native_tables_extracted"] > 0:
        return ["NATIVE_PDFPLUMBER_PLAN_PROMISING_BUT_INCOMPLETE"]
    return ["MINIMAL_NATIVE_CONTRACT_INSUFFICIENT"]


def _expected_table_counts() -> dict[str, int]:
    return {
        "g599_holdout_01": 0,
        "g599_holdout_02": 0,
        "g599_holdout_03": 2,
        "g599_holdout_04": 2,
        "g599_holdout_05": 3,
        "g599_holdout_06": 2,
        "g599_holdout_07": 0,
        "g599_holdout_08": 0,
        "g599_holdout_09": 0,
    }


def _slice_page(pdf_bytes: bytes, page_number: int) -> tuple[bytes, float, float]:
    reader = pypdf.PdfReader(BytesIO(pdf_bytes), strict=False)
    page = reader.pages[page_number - 1]
    writer = pypdf.PdfWriter()
    writer.add_page(page)
    output = BytesIO()
    writer.write(output)
    return output.getvalue(), float(page.mediabox.width), float(page.mediabox.height)


def _png_dimensions(value: bytes) -> tuple[int, int]:
    if value[:8] != b"\x89PNG\r\n\x1a\n" or value[12:16] != b"IHDR":
        raise G5100Error("g5100_png_invalid")
    return struct.unpack(">II", value[16:24])


def _provider(env_path: Path) -> Any:
    return PdfGridExperimentProviderFactory(
        PdfGridProviderConfig(
            provider_profile="google_gemini",
            model_id="models/gemini-3.5-flash",
            timeout_seconds=240,
            maximum_output_tokens=4096,
            maximum_counted_input_tokens=24000,
            thinking_level="minimal",
        )
    ).create_for_openwebui(_openwebui_request(env_path.resolve()))


def _openwebui_request(env_path: Path) -> Any:
    env = _read_env(env_path)
    host = str(env.get("OPENWEBUI_HOST") or "").rstrip("/")
    email = str(env.get("WEBUI_ADMIN_EMAIL") or "")
    password = str(env.get("WEBUI_ADMIN_PASSWORD") or "")
    if not all((host, email, password)):
        raise G5100Error("g5100_openwebui_credentials_missing")
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
        raise G5100Error("g5100_openwebui_token_missing")
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
    values = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise G5100Error("g5100_json_object_required")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    )


if __name__ == "__main__":
    raise SystemExit(main())
