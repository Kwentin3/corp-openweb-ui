#!/usr/bin/env python3
"""Run the one-shot G5.103 table-instance separation prompt proof."""

from __future__ import annotations

import argparse
import base64
import copy
import json
from pathlib import Path
from typing import Any

from broker_reports_gate1.gemini_normalized_table_boxes import (
    GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA,
    GeminiNormalizedTableBoxError,
    GeminiNormalizedTableBoxProjectionFactory,
)
from broker_reports_gate1.pdf_table_raster import (
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from broker_reports_gate1.pdf_text_layer import (
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)
from scripts.local_gemini_table_boxes_g5102 import PROMPT as G5102_PROMPT
from scripts.local_minimal_native_pdfplumber_plan_g5100 import (
    DEFAULT_IMAGE_ROOT,
    DEFAULT_MANIFEST,
    DEFAULT_SOURCE_MAP,
    REPO_ROOT,
    _expected_table_counts,
    _provider,
    _read_object,
    _sha256,
    _sha256_json,
    _slice_page,
    _write_json,
)
from scripts.local_pdf_native_navigation_g5101 import (
    FROZEN_TRUTH_REGIONS,
    _region_evidence,
)


SCRIPT_PATH = Path(__file__).resolve()
G5102_SCRIPT_PATH = SCRIPT_PATH.with_name("local_gemini_table_boxes_g5102.py")
DEFAULT_PRIVATE_ROOT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_table_instance_separation_g5103_2026-08-19"
    / "private"
)
DEFAULT_PRIVATE_OUTPUT = DEFAULT_PRIVATE_ROOT / "development.private.json"
DEFAULT_SAFE_OUTPUT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-19"
    / "BROKER_REPORTS_G5103_TABLE_INSTANCE_SEPARATION_DEVELOPMENT.safe.json"
)
OFFICIAL_CONTRACT_URL = (
    "https://ai.google.dev/gemini-api/docs/generate-content/"
    "image-understanding#object-detection"
)
FACTORY_REQUIRED = (
    "PdfTableRasterFactory.create -> "
    "PdfGridExperimentProviderFactory.create_for_openwebui -> "
    "GeminiNormalizedTableBoxProjectionFactory.create"
)
FORBIDDEN = (
    "No broker/domain hint, navigation grid, PDF-point request, table "
    "extraction, vertical-line request, retry, best-of-N, semantic repair, "
    "or product routing"
)

G5102_INSTANCE_RULE = """Keep visually distinct tables separate. A table continuation without its
original header is still a table."""
G5103_INSTANCE_RULE = """Treat each visually independent data grid as a
separate table instance. The image may contain zero, one, or multiple table
instances. Return exactly one box per table instance. Never use one box that
encloses two distinct grids or titled table sections. A distinct table title
or column header together with a clear whitespace gap or a break in grid/row
continuity starts a new table instance. Do not split one continuous grid merely
because it contains internal section rows, repeated headers, or is a page
continuation. A table continuation without its original header is still one
table instance."""


def _derive_prompt() -> str:
    if G5102_PROMPT.count(G5102_INSTANCE_RULE) != 1:
        raise RuntimeError("g5103_g5102_prompt_anchor_invalid")
    return G5102_PROMPT.replace(G5102_INSTANCE_RULE, G5103_INSTANCE_RULE)


PROMPT = _derive_prompt()


class G5103Error(RuntimeError):
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
        raise G5103Error("g5103_outputs_already_exist")
    manifest = _read_object(manifest_path)
    source_map = _read_object(source_map_path).get("documents") or {}
    cases = list(manifest.get("unseen_holdout") or [])
    expected_by_case = _expected_table_counts()
    case_ids = {str(item["case_id"]) for item in cases}
    if case_ids != set(expected_by_case) or case_ids != set(FROZEN_TRUTH_REGIONS):
        raise G5103Error("g5103_g599_case_set_invalid")

    raster = PdfTableRasterFactory(PdfTableRasterConfig(padding_points=0)).create()
    projection = GeminiNormalizedTableBoxProjectionFactory().create()
    parser = PdfTextLayerParserFactory().create(
        PdfParserCapabilityRequest(capability="table_candidates")
    )
    provider = _provider(env_path)
    qualification = provider.qualify()
    if qualification.get("status") != "qualified":
        raise G5103Error("g5103_provider_not_qualified")

    private_root.mkdir(parents=True, exist_ok=False)
    results = []
    for case in cases:
        case_id = str(case["case_id"])
        document_id = str(case["document_id"])
        page_number = int(case["page"])
        source = source_map.get(document_id) or {}
        source_bytes = Path(str(source.get("path") or "")).read_bytes()
        if _sha256(source_bytes) != source.get("sha256"):
            raise G5103Error("g5103_source_hash_drift")
        page_pdf, pypdf_width, pypdf_height = _slice_page(
            source_bytes, page_number
        )
        page_pdf_sha256 = _sha256(page_pdf)
        parsed = parser.parse(page_pdf)
        if parsed.layout_projection_status != "complete" or len(parsed.pages) != 1:
            raise G5103Error("g5103_parser_page_invalid")
        parser_page = parsed.pages[0]
        page_bbox = [
            0.0,
            0.0,
            float(parser_page["width"]),
            float(parser_page["height"]),
        ]
        if page_bbox[2:] != [pypdf_width, pypdf_height]:
            raise G5103Error("g5103_page_dimension_owner_mismatch")
        rendered = raster.render_full_page(
            pdf_bytes=page_pdf,
            pdf_sha256=page_pdf_sha256,
            document_ref=f"{document_id}_p{page_number:03d}",
            page_ref=f"g5103_{case_id}",
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
            raise G5103Error("g5103_frozen_baseline_render_drift")

        outcome = provider.invoke(
            task_id=f"g5103_{case_id}",
            model_view={"task": PROMPT},
            output_schema=copy.deepcopy(
                GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA
            ),
            png_bytes=page_png,
            crop_sha256=rendered["manifest"]["png_sha256"],
            attempt_number=1,
            attempt_lineage=[],
        )
        provider_value = outcome.get("json_output")
        projected = None
        projection_error = None
        try:
            projected = projection.project(
                provider_value=provider_value,
                raster_manifest=rendered["manifest"],
                expected_page_bbox=page_bbox,
            )
        except GeminiNormalizedTableBoxError as exc:
            projection_error = exc.code

        native_plan = {
            "tables": [
                {"bbox": list(item["bbox_pdf_points"])}
                for item in (projected or {}).get("tables") or []
            ]
        }
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
                "page_png_sha256": _sha256(page_png),
                "raster_manifest": rendered["manifest"],
                "provider_value": provider_value,
                "projection": projected,
                "projection_error": projection_error,
                "frozen_region_evidence": region_evidence,
                "attempt": outcome.get("attempt"),
                "response_hash": outcome.get("response_hash"),
                "raw_private_response": outcome.get("raw_private_response"),
            }
        )

    metrics = _metrics(results)
    terminals = _terminals(metrics)
    private = {
        "schema_version": (
            "broker_reports_table_instance_separation_g5103_"
            "development_private_v1"
        ),
        "goal": "G5.103",
        "phase": "development",
        "baseline": "g5102_same_open_g599_pages_and_contract",
        "hypothesis": "explicit_visual_table_instance_boundary_prevents_merge",
        "official_coordinate_contract": OFFICIAL_CONTRACT_URL,
        "baseline_prompt": G5102_PROMPT,
        "prompt": PROMPT,
        "response_schema": GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA,
        "baseline_prompt_sha256": _sha256_json(G5102_PROMPT),
        "prompt_sha256": _sha256_json(PROMPT),
        "response_schema_sha256": _sha256_json(
            GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA
        ),
        "baseline_harness_sha256": _sha256(G5102_SCRIPT_PATH.read_bytes()),
        "implementation_sha256": _sha256(SCRIPT_PATH.read_bytes()),
        "controlled_delta": {
            "changed": ["visual_table_instance_definition_in_prompt"],
            "unchanged": [
                "pages",
                "page_png_bytes",
                "model",
                "thinking_level",
                "response_schema",
                "coordinate_contract",
                "raster_factory",
                "provider_factory",
                "projection_factory",
                "attempts_per_page",
                "retry_policy",
                "evaluation",
            ],
            "broker_or_domain_hint_added": False,
        },
        "provider_policy": {
            "model": "models/gemini-3.5-flash",
            "calls": len(cases),
            "attempts_per_page": 1,
            "retry": False,
            "best_of_n": False,
            "model_change": False,
            "thinking_level": "minimal",
            "navigation_grid": False,
            "requested_pdf_points": False,
            "requested_vertical_lines": False,
            "body_values": 0,
        },
        "qualification": qualification,
        "results": results,
        "metrics": metrics,
        "terminals": terminals,
    }
    _write_json(private_output, private)
    safe = {
        "schema_version": (
            "broker_reports_table_instance_separation_g5103_"
            "development_safe_v1"
        ),
        "goal": "G5.103",
        "phase": "development",
        "hypothesis": private["hypothesis"],
        "controlled_delta": private["controlled_delta"],
        "provider_calls": len(cases),
        "metrics": metrics,
        "terminals": terminals,
        "freeze_permitted": False,
        "unseen_holdout_executed": False,
        "private_canonical_json_sha256": _sha256_json(private),
        "privacy": {
            "customer_bytes_in_git": False,
            "raw_provider_response_in_git": False,
            "normalized_coordinates_in_safe_report": False,
            "pdf_coordinates_in_safe_report": False,
            "cell_values_in_git": False,
        },
    }
    _write_json(safe_output, safe)
    return {"status": "complete", "metrics": metrics, "terminals": terminals}


def _proposal_count(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    tables = value.get("tables")
    return len(tables) if isinstance(tables, list) else 0


def _metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = [
        item
        for result in results
        for item in result["frozen_region_evidence"]
        if item.get("truth_region_expressible") is True
    ]
    coverages = [float(item["truth_coverage_percent"]) for item in evidence]
    return {
        "pages": len(results),
        "positive_pages": sum(
            result["expected_visual_tables"] > 0 for result in results
        ),
        "negative_pages": sum(
            result["expected_visual_tables"] == 0 for result in results
        ),
        "expected_visual_tables": sum(
            result["expected_visual_tables"] for result in results
        ),
        "proposed_tables": sum(
            _proposal_count(result["provider_value"]) for result in results
        ),
        "projected_boxes": sum(
            len((result.get("projection") or {}).get("tables") or [])
            for result in results
        ),
        "pages_with_exact_table_count": sum(
            _proposal_count(result["provider_value"])
            == result["expected_visual_tables"]
            for result in results
        ),
        "false_boxes_on_negative_pages": sum(
            _proposal_count(result["provider_value"])
            for result in results
            if result["expected_visual_tables"] == 0
        ),
        "invalid_responses": sum(
            result.get("projection_error") is not None for result in results
        ),
        "provider_non_success_terminals": sum(
            (result.get("attempt") or {}).get("finish_reason") != "STOP"
            or (result.get("attempt") or {}).get("terminal_failure_class")
            is not None
            for result in results
        ),
        "expressible_truth_regions": len(evidence),
        "exact_truth_regions": sum(
            item.get("exact_region_match") is True for item in evidence
        ),
        "truth_regions_with_full_coverage": sum(
            item.get("truth_coverage_percent") == 100.0 for item in evidence
        ),
        "truth_region_minimum_coverage_percent": min(coverages)
        if coverages
        else None,
        "truth_region_mean_coverage_percent": round(
            sum(coverages) / len(coverages), 1
        )
        if coverages
        else None,
        "extraneous_parser_lines_total": sum(
            int(item["extraneous_lines_total"]) for item in evidence
        ),
        "nonexpressible_embedded_truth_regions": sum(
            item.get("truth_region_expressible") is False
            for result in results
            for item in result["frozen_region_evidence"]
        ),
        "vlm_body_values_used": 0,
        "invented_source_literals": 0,
    }


def _terminals(metrics: dict[str, Any]) -> list[str]:
    if metrics["provider_non_success_terminals"] or metrics["invalid_responses"]:
        return ["TABLE_INSTANCE_SEPARATION_CONTRACT_FAILED"]
    if (
        metrics["pages_with_exact_table_count"] != metrics["pages"]
        or metrics["false_boxes_on_negative_pages"] != 0
    ):
        return ["TABLE_INSTANCE_SEPARATION_COUNT_INSUFFICIENT"]
    if metrics["exact_truth_regions"] != metrics["expressible_truth_regions"]:
        return ["TABLE_INSTANCE_SEPARATION_LOCALIZATION_INSUFFICIENT"]
    return ["TABLE_INSTANCE_SEPARATION_MACHINE_CHECKS_PASSED"]


if __name__ == "__main__":
    raise SystemExit(main())
