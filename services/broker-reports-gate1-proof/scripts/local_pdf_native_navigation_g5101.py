#!/usr/bin/env python3
"""Run the one-shot G5.101 native-coordinate navigation development test."""

from __future__ import annotations

import argparse
import base64
import copy
import json
from pathlib import Path
from typing import Any

from broker_reports_gate1.pdf_native_navigation_overlay import (
    NativePdfPointNavigationOverlayFactory,
)
from broker_reports_gate1.pdf_table_raster import (
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from broker_reports_gate1.pdf_text_layer import (
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)
from broker_reports_gate1.visual_pdfplumber_table_plan import (
    VisualPdfPlumberTableAdapterFactory,
    VisualPdfPlumberTablePlanError,
    validate_pdfplumber_table_plan,
)
from scripts.local_minimal_native_pdfplumber_plan_g5100 import (
    DEFAULT_IMAGE_ROOT,
    DEFAULT_MANIFEST,
    DEFAULT_SOURCE_MAP,
    REPO_ROOT,
    _compact_execution,
    _expected_table_counts,
    _provider,
    _read_object,
    _sha256,
    _sha256_json,
    _slice_page,
    _write_json,
)


SCRIPT_PATH = Path(__file__).resolve()
DEFAULT_PRIVATE_ROOT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_pdf_native_navigation_g5101_2026-08-18"
    / "private"
)
DEFAULT_PRIVATE_OUTPUT = DEFAULT_PRIVATE_ROOT / "development.private.json"
DEFAULT_SAFE_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-18"
    / "BROKER_REPORTS_G5101_PDF_NATIVE_NAVIGATION_DEVELOPMENT.safe.json"
)
FACTORY_REQUIRED = (
    "PdfTableRasterFactory.create -> "
    "NativePdfPointNavigationOverlayFactory.create -> "
    "PdfGridExperimentProviderFactory.create_for_openwebui -> "
    "VisualPdfPlumberTableAdapterFactory.create"
)
FORBIDDEN = (
    "No alternate renderer, image-pixel coordinate resolver, tolerance knob, "
    "retry, best-of-N, old breadcrumb repair, or product routing"
)

PROMPT_TEMPLATE = """Inspect this one rendered PDF page and return only a native
pdfplumber 0.11.10 table extraction plan.

The blue grid and the rulers outside the page show pdfplumber's own top-left PDF
point coordinates. X grows right from {x0:g} to {x1:g}; TOP grows down from
{top:g} to {bottom:g}. Read coordinates from these visible rulers. Do not use
outer-image pixels. The grid and rulers are navigation aids only: they are not
PDF content, table borders, rows, columns, or evidence, and pdfplumber will not
receive them.

For every visible data table or table continuation, in top-to-bottom order:
- bbox is exactly [x0, top, x1, bottom] in the visible PDF-point coordinates and
  tightly encloses the complete table;
- explicit_vertical_lines contains every column boundary from the left outer
  table boundary through the right outer table boundary, in increasing native
  X coordinates;
- horizontal_strategy is lines only when original PDF rules define rows;
  otherwise use text for a borderless table.

Do not return cell values, body rows, text, labels, amounts, dates, financial
roles, summaries, tolerances, or fields outside the schema. Do not treat prose,
lists, page furniture, the blue navigation grid, or covers as tables. A table
continuation is still a table. Keep multiple tables separate. If no visible data
table exists, return {{"tables": []}}.
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

FROZEN_TRUTH_REGIONS: dict[str, list[tuple[int, int] | None]] = {
    "g599_holdout_01": [],
    "g599_holdout_02": [],
    "g599_holdout_03": [(18, 24), (25, 31)],
    "g599_holdout_04": [(2, 8), (9, 73)],
    "g599_holdout_05": [(2, 9), (10, 50), (51, 52)],
    "g599_holdout_06": [None, None],
    "g599_holdout_07": [],
    "g599_holdout_08": [],
    "g599_holdout_09": [],
}


class G5101Error(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--source-map", default=str(DEFAULT_SOURCE_MAP))
    parser.add_argument("--baseline-image-root", default=str(DEFAULT_IMAGE_ROOT))
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--private-root", default=str(DEFAULT_PRIVATE_ROOT))
    parser.add_argument("--private-output", default=str(DEFAULT_PRIVATE_OUTPUT))
    parser.add_argument("--safe-output", default=str(DEFAULT_SAFE_OUTPUT))
    args = parser.parse_args(argv)
    result = run_development(
        manifest_path=Path(args.manifest),
        source_map_path=Path(args.source_map),
        baseline_image_root=Path(args.baseline_image_root),
        env_path=Path(args.env_file),
        private_root=Path(args.private_root),
        private_output=Path(args.private_output),
        safe_output=Path(args.safe_output),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def run_development(
    *,
    manifest_path: Path,
    source_map_path: Path,
    baseline_image_root: Path,
    env_path: Path,
    private_root: Path,
    private_output: Path,
    safe_output: Path,
) -> dict[str, Any]:
    if private_output.exists() or safe_output.exists():
        raise G5101Error("g5101_outputs_already_exist")
    manifest = _read_object(manifest_path)
    source_map = _read_object(source_map_path).get("documents") or {}
    cases = list(manifest.get("unseen_holdout") or [])
    expected_by_case = _expected_table_counts()
    case_ids = {str(item["case_id"]) for item in cases}
    if case_ids != set(expected_by_case) or case_ids != set(FROZEN_TRUTH_REGIONS):
        raise G5101Error("g5101_g599_case_set_invalid")

    raster = PdfTableRasterFactory(
        PdfTableRasterConfig(padding_points=0)
    ).create()
    overlay = NativePdfPointNavigationOverlayFactory().create()
    adapter = VisualPdfPlumberTableAdapterFactory().create()
    provider = _provider(env_path)
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise G5101Error("g5101_provider_not_qualified")

    results = []
    overlay_dir = private_root / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=False)
    for case in cases:
        case_id = str(case["case_id"])
        document_id = str(case["document_id"])
        page_number = int(case["page"])
        source = source_map.get(document_id) or {}
        source_bytes = Path(str(source.get("path") or "")).read_bytes()
        if _sha256(source_bytes) != source.get("sha256"):
            raise G5101Error("g5101_source_hash_drift")
        page_pdf, pypdf_width, pypdf_height = _slice_page(
            source_bytes, page_number
        )
        page_pdf_sha256 = _sha256(page_pdf)
        parsed = PdfTextLayerParserFactory().create(
            PdfParserCapabilityRequest(capability="table_candidates")
        ).parse(page_pdf)
        if parsed.layout_projection_status != "complete" or len(parsed.pages) != 1:
            raise G5101Error("g5101_parser_page_invalid")
        parser_page = parsed.pages[0]
        page_bbox = [
            0.0,
            0.0,
            float(parser_page["width"]),
            float(parser_page["height"]),
        ]
        if page_bbox[2:] != [pypdf_width, pypdf_height]:
            raise G5101Error("g5101_page_dimension_owner_mismatch")
        rendered = raster.render_full_page(
            pdf_bytes=page_pdf,
            pdf_sha256=page_pdf_sha256,
            document_ref=f"{document_id}_p{page_number:03d}",
            page_ref=f"g5101_{case_id}",
            page_number=1,
            expected_page_bbox=page_bbox,
            dpi=150,
        )
        page_png = base64.b64decode(rendered["private_png_base64"])
        baseline_image = (
            baseline_image_root
            / "documents"
            / document_id
            / "pages"
            / f"p{page_number:03d}.private.png"
        ).read_bytes()
        if (
            page_png != baseline_image
            or _sha256(page_png) != case.get("page_png_sha256")
        ):
            raise G5101Error("g5101_frozen_baseline_render_drift")
        navigated = overlay.apply(
            page_png_bytes=page_png,
            raster_manifest=rendered["manifest"],
            expected_page_bbox=page_bbox,
        )
        navigated_png = base64.b64decode(navigated["private_png_base64"])
        overlay_path = overlay_dir / f"{case_id}.private.png"
        overlay_path.write_bytes(navigated_png)
        prompt = PROMPT_TEMPLATE.format(
            x0=page_bbox[0],
            top=page_bbox[1],
            x1=page_bbox[2],
            bottom=page_bbox[3],
        )
        outcome = provider.invoke(
            task_id=f"g5101_{case_id}",
            model_view={"task": prompt},
            output_schema=copy.deepcopy(RESPONSE_SCHEMA),
            png_bytes=navigated_png,
            crop_sha256=navigated["manifest"]["output_png_sha256"],
            attempt_number=1,
            attempt_lineage=[],
        )
        native_plan = outcome.get("json_output")
        execution_plan = None
        validation_error = None
        try:
            execution_plan = _execution_plan(
                native_plan,
                page_width=page_bbox[2],
                page_height=page_bbox[3],
            )
        except VisualPdfPlumberTablePlanError as exc:
            validation_error = exc.code
        execution = None
        execution_error = None
        if execution_plan is not None:
            try:
                execution = adapter.execute_single_page(
                    pdf_bytes=page_pdf,
                    image_width_pixels=page_bbox[2],
                    image_height_pixels=page_bbox[3],
                    plan=execution_plan,
                    document_id=f"{document_id}_p{page_number:03d}",
                )
            except VisualPdfPlumberTablePlanError as exc:
                execution_error = exc.code
        region_evidence = _region_evidence(
            parser_page=parser_page,
            native_plan=native_plan,
            expected_regions=FROZEN_TRUTH_REGIONS[case_id],
        )
        results.append(
            {
                "case_id": case_id,
                "document_id": document_id,
                "page": page_number,
                "expected_visual_tables": expected_by_case[case_id],
                "page_bbox": page_bbox,
                "baseline_page_png_sha256": _sha256(page_png),
                "navigation_overlay_manifest": navigated["manifest"],
                "native_plan": native_plan,
                "plan_validation_error": validation_error,
                "execution_error": execution_error,
                "execution": _compact_execution(execution),
                "frozen_region_evidence": region_evidence,
                "attempt": outcome.get("attempt"),
                "response_hash": outcome.get("response_hash"),
                "raw_private_response": outcome.get("raw_private_response"),
            }
        )

    metrics = _metrics(results)
    terminals = _terminals(metrics)
    private = {
        "schema_version": "broker_reports_pdf_native_navigation_g5101_development_private_v1",
        "goal": "G5.101",
        "phase": "development",
        "baseline": "G5.100_frozen_no_repair",
        "prompt_template": PROMPT_TEMPLATE,
        "response_schema": RESPONSE_SCHEMA,
        "prompt_sha256": _sha256_json(PROMPT_TEMPLATE),
        "response_schema_sha256": _sha256_json(RESPONSE_SCHEMA),
        "implementation_sha256": _sha256(SCRIPT_PATH.read_bytes()),
        "provider_policy": {
            "model": "models/gemini-3.5-flash",
            "calls": len(cases),
            "attempts_per_page": 1,
            "retry": False,
            "best_of_n": False,
            "model_change": False,
            "tolerance_knobs": 0,
            "body_values": 0,
        },
        "qualification": qualification,
        "results": results,
        "metrics": metrics,
        "terminals": terminals,
    }
    _write_json(private_output, private)
    safe = {
        "schema_version": "broker_reports_pdf_native_navigation_g5101_development_safe_v1",
        "goal": "G5.101",
        "phase": "development",
        "changed_variable": "visible_pdfplumber_point_navigation_overlay_only",
        "native_plan_fields": [
            "bbox",
            "explicit_vertical_lines",
            "horizontal_strategy",
        ],
        "plan_to_pdfplumber_transform": "identity",
        "tolerance_knobs": 0,
        "provider_calls": len(cases),
        "metrics": metrics,
        "terminals": terminals,
        "freeze_permitted": False,
        "unseen_holdout_executed": False,
        "private_file_sha256": _sha256_json(private),
        "privacy": {
            "customer_bytes_in_git": False,
            "raw_provider_response_in_git": False,
            "coordinates_in_safe_report": False,
            "cell_values_in_git": False,
        },
    }
    _write_json(safe_output, safe)
    return {"status": "complete", "metrics": metrics, "terminals": terminals}


def _execution_plan(
    value: Any, *, page_width: float, page_height: float
) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"tables"}:
        raise VisualPdfPlumberTablePlanError("g5101_plan_shape_invalid")
    tables = value.get("tables")
    if not isinstance(tables, list):
        raise VisualPdfPlumberTablePlanError("g5101_tables_invalid")
    expanded = {"tables": []}
    expected_keys = {
        "bbox",
        "explicit_vertical_lines",
        "horizontal_strategy",
    }
    for table in tables:
        if not isinstance(table, dict) or set(table) != expected_keys:
            raise VisualPdfPlumberTablePlanError(
                "g5101_table_plan_shape_invalid"
            )
        expanded["tables"].append(
            {
                "bbox": copy.deepcopy(table["bbox"]),
                "vertical_strategy": "explicit",
                "explicit_vertical_lines": copy.deepcopy(
                    table["explicit_vertical_lines"]
                ),
                "horizontal_strategy": table["horizontal_strategy"],
            }
        )
    validate_pdfplumber_table_plan(
        expanded,
        image_width_pixels=page_width,
        image_height_pixels=page_height,
    )
    return expanded


def _region_evidence(
    *,
    parser_page: dict[str, Any],
    native_plan: Any,
    expected_regions: list[tuple[int, int] | None],
) -> list[dict[str, Any]]:
    tables = (
        list(native_plan.get("tables") or [])
        if isinstance(native_plan, dict)
        else []
    )
    lines = list(parser_page.get("line_inventory") or [])
    evidence = []
    for ordinal, expected in enumerate(expected_regions, 1):
        table = tables[ordinal - 1] if ordinal <= len(tables) else None
        if expected is None:
            evidence.append(
                {
                    "plan_ordinal": ordinal,
                    "truth_region_expressible": False,
                    "exact_region_match": None,
                }
            )
            continue
        inside = []
        if isinstance(table, dict):
            bbox = table.get("bbox")
            if (
                isinstance(bbox, list)
                and len(bbox) == 4
                and all(
                    isinstance(item, (int, float))
                    and not isinstance(item, bool)
                    for item in bbox
                )
            ):
                x0, top, x1, bottom = [float(item) for item in bbox]
                for line in lines:
                    line_bbox = line.get("bbox") or []
                    if len(line_bbox) != 4:
                        continue
                    center_x = (float(line_bbox[0]) + float(line_bbox[2])) / 2
                    center_y = (float(line_bbox[1]) + float(line_bbox[3])) / 2
                    if x0 <= center_x < x1 and top <= center_y < bottom:
                        inside.append(int(line["parser_ordinal"]))
        truth = set(range(expected[0], expected[1] + 1))
        selected = set(inside)
        evidence.append(
            {
                "plan_ordinal": ordinal,
                "truth_region_expressible": True,
                "expected_line_ordinal_range": list(expected),
                "selected_line_ordinals": inside,
                "truth_coverage_percent": round(
                    100.0 * len(truth & selected) / len(truth), 1
                ),
                "extraneous_lines_total": len(selected - truth),
                "exact_region_match": selected == truth,
            }
        )
    return evidence


def _metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    expected_total = sum(item["expected_visual_tables"] for item in results)
    proposed_total = sum(
        len((item.get("native_plan") or {}).get("tables") or [])
        for item in results
    )
    extracted_total = sum(
        len((item.get("execution") or {}).get("native_table_shapes") or [])
        for item in results
    )
    negatives = [item for item in results if item["expected_visual_tables"] == 0]
    canonical = [
        (item.get("execution") or {}).get("canonical_metrics") or {}
        for item in results
    ]
    region_rows = [
        region
        for item in results
        for region in item["frozen_region_evidence"]
        if region["truth_region_expressible"] is True
    ]
    return {
        "pages": len(results),
        "expected_visual_tables": expected_total,
        "proposed_tables": proposed_total,
        "native_tables_reaching_canonical": extracted_total,
        "pages_with_exact_plan_count": sum(
            len((item.get("native_plan") or {}).get("tables") or [])
            == item["expected_visual_tables"]
            for item in results
        ),
        "pages_with_exact_native_count": sum(
            len((item.get("execution") or {}).get("native_table_shapes") or [])
            == item["expected_visual_tables"]
            for item in results
        ),
        "false_table_plans_on_negative_pages": sum(
            len((item.get("native_plan") or {}).get("tables") or [])
            for item in negatives
        ),
        "invalid_plans": sum(
            item.get("plan_validation_error") is not None for item in results
        ),
        "execution_errors": sum(
            item.get("execution_error") is not None for item in results
        ),
        "non_success_terminals": sum(
            (item.get("execution") or {}).get("terminal")
            not in {"NATIVE_TABLE_EXTRACTED", "NO_TABLE_PLAN"}
            for item in results
        ),
        "expressible_truth_regions": len(region_rows),
        "exact_truth_regions": sum(
            item.get("exact_region_match") is True for item in region_rows
        ),
        "canonical_pages_valid": sum(
            item.get("canonical_valid") is True for item in canonical
        ),
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
            int(
                (item.get("execution") or {}).get("invented_source_literals")
                or 0
            )
            for item in results
        ),
    }


def _terminals(metrics: dict[str, Any]) -> list[str]:
    if (
        metrics["pages_with_exact_plan_count"] == metrics["pages"]
        and metrics["false_table_plans_on_negative_pages"] == 0
        and metrics["invalid_plans"] == 0
        and metrics["exact_truth_regions"]
        == metrics["expressible_truth_regions"]
        and metrics["pages_with_exact_native_count"] == metrics["pages"]
        and metrics["canonical_pages_exactly_accounted"] == metrics["pages"]
        and metrics["vlm_body_values_used"] == 0
        and metrics["invented_source_literals"] == 0
    ):
        return ["NATIVE_PDF_POINT_NAVIGATION_DEVELOPMENT_PASSED"]
    if metrics["native_tables_reaching_canonical"] > 0:
        return ["NATIVE_PDF_POINT_NAVIGATION_PROMISING_BUT_INCOMPLETE"]
    return ["NATIVE_PDF_POINT_NAVIGATION_INSUFFICIENT"]


if __name__ == "__main__":
    raise SystemExit(main())
