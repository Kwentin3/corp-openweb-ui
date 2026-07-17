#!/usr/bin/env python3
"""Render and seal exact-ground-truth controlled table crops."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import fitz


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
DEFAULT_REFERENCE = (
    SERVICE_ROOT
    / "benchmarks"
    / "pdf_dual_vlm_canonical_table_v1"
    / "controlled_reference.json"
)

sys.path.insert(0, str(SCRIPT_DIR))

from pdf_dual_vlm_canonical_table_contracts import (  # noqa: E402
    GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE,
    REFERENCE_SCHEMA_VERSION,
    canonical_json_bytes,
    canonicalize_table,
    validate_table_output,
)


CROP_PACK_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_controlled_crop_pack_v1"
CROP_PACK_SEAL_SCHEMA_VERSION = (
    "broker_reports_pdf_dual_vlm_controlled_crop_pack_seal_v1"
)


class ControlledCorpusError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", default=str(DEFAULT_REFERENCE))
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    reference_path = Path(args.reference).resolve()
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ControlledCorpusError("controlled_corpus_fresh_output_required")
    output_dir.mkdir(parents=True, exist_ok=True)
    crop_dir = output_dir / "crops"
    crop_dir.mkdir()

    reference = _json(reference_path)
    _validate_reference(reference)
    rendering = reference["rendering"]
    if fitz.VersionBind != rendering["renderer_version"]:
        raise ControlledCorpusError("controlled_corpus_renderer_version_mismatch")
    if (
        float(rendering["padding_fraction_per_page_side"])
        != GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE
    ):
        raise ControlledCorpusError("controlled_corpus_padding_policy_mismatch")

    crops: list[dict[str, Any]] = []
    for case in reference["cases"]:
        crop = _render_case(case=case, rendering=rendering)
        crop_path = crop_dir / f"{case['case_id']}.png"
        crop_path.write_bytes(crop.pop("png_bytes"))
        crop["crop_path"] = str(crop_path.relative_to(output_dir)).replace("\\", "/")
        crops.append(crop)

    pack = {
        "schema_version": CROP_PACK_SCHEMA_VERSION,
        "benchmark_id": reference["benchmark_id"],
        "entrypoint": SCRIPT_PATH.name,
        "reference_accessed_for_controlled_rendering": True,
        "reference_available_to_providers": False,
        "provider_calls": 0,
        "authority": reference["authority"],
        "rendering": rendering,
        "case_count": len(crops),
        "crops": crops,
        "run_status": "completed",
    }
    pack_bytes = canonical_json_bytes(pack)
    pack_path = output_dir / "controlled_crop_pack.json"
    pack_path.write_bytes(pack_bytes)
    seal = {
        "schema_version": CROP_PACK_SEAL_SCHEMA_VERSION,
        "crop_pack_sha256": hashlib.sha256(pack_bytes).hexdigest(),
        "crop_pack_size_bytes": len(pack_bytes),
    }
    seal_path = output_dir / "controlled_crop_pack.sha256.json"
    seal_path.write_bytes(canonical_json_bytes(seal))
    print(
        json.dumps(
            {
                "crop_pack": str(pack_path),
                "seal": str(seal_path),
                "crop_pack_sha256": seal["crop_pack_sha256"],
                "case_count": len(crops),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _render_case(*, case: dict[str, Any], rendering: dict[str, Any]) -> dict[str, Any]:
    page_width = float(rendering["page_width_points"])
    page_height = float(rendering["page_height_points"])
    detected = [float(item) for item in rendering["detected_table_bbox_normalized"]]
    padded = _apply_padding(detected, GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE)
    if padded != [float(item) for item in rendering["padded_crop_bbox_normalized"]]:
        raise ControlledCorpusError("controlled_corpus_declared_padding_bbox_mismatch")

    document = fitz.open()
    try:
        page = document.new_page(width=page_width, height=page_height)
        table_rect = _normalized_rect(detected, page_width, page_height)
        _draw_table(
            page=page,
            table=case["table"],
            table_rect=table_rect,
            style=case["visual_style"],
        )
        pdf_bytes = document.tobytes(garbage=4, deflate=True)
    finally:
        document.close()

    crop_rect = _normalized_rect(padded, page_width, page_height)
    first = _render_pdf_crop(pdf_bytes, crop_rect, int(rendering["render_dpi"]))
    second = _render_pdf_crop(pdf_bytes, crop_rect, int(rendering["render_dpi"]))
    if first != second:
        raise ControlledCorpusError("controlled_corpus_crop_not_reproducible")
    pixmap = _pixmap_for_dimensions(pdf_bytes, crop_rect, int(rendering["render_dpi"]))
    return {
        "case_id": case["case_id"],
        "table_id": case["table"]["table_id"],
        "corpus": "controlled_exact_ground_truth",
        "category_tags": case["category_tags"],
        "detected_bbox_normalized": detected,
        "padding_fraction_per_page_side": GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE,
        "padded_crop_bbox_normalized": padded,
        "crop_sha256": hashlib.sha256(first).hexdigest(),
        "crop_bytes": len(first),
        "crop_width": int(pixmap.width),
        "crop_height": int(pixmap.height),
        "byte_identical_reproduction": True,
        "png_bytes": first,
    }


def _draw_table(
    *,
    page: fitz.Page,
    table: dict[str, Any],
    table_rect: fitz.Rect,
    style: str,
) -> None:
    canonical = canonicalize_table(table, table_id=table["table_id"])
    row_height = table_rect.height / canonical["row_count"]
    column_width = table_rect.width / canonical["column_count"]
    for cell in canonical["cells"]:
        rect = fitz.Rect(
            table_rect.x0 + cell["column_index"] * column_width,
            table_rect.y0 + cell["row_index"] * row_height,
            table_rect.x0 + (cell["column_index"] + cell["column_span"]) * column_width,
            table_rect.y0 + (cell["row_index"] + cell["row_span"]) * row_height,
        )
        if style == "ruled":
            page.draw_rect(rect, color=(0, 0, 0), width=1)
        elif style != "borderless":
            raise ControlledCorpusError("controlled_corpus_visual_style_invalid")
        if cell["content_state"] == "unreadable":
            obscured = fitz.Rect(rect.x0 + 18, rect.y0 + 24, rect.x1 - 18, rect.y1 - 24)
            page.draw_rect(obscured, color=(0, 0, 0), fill=(0, 0, 0), width=0)
            continue
        if cell["content_state"] == "empty":
            continue
        inset = fitz.Rect(rect.x0 + 8, rect.y0 + 10, rect.x1 - 8, rect.y1 - 8)
        result = page.insert_textbox(
            inset,
            cell["source_text"],
            fontname="helv",
            fontsize=13,
            align=1 if style == "ruled" else 0,
            color=(0, 0, 0),
        )
        if result < 0:
            raise ControlledCorpusError("controlled_corpus_text_did_not_fit")


def _render_pdf_crop(pdf_bytes: bytes, crop_rect: fitz.Rect, dpi: int) -> bytes:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pixmap = document[0].get_pixmap(dpi=dpi, clip=crop_rect, alpha=False)
        return pixmap.tobytes("png")
    finally:
        document.close()


def _pixmap_for_dimensions(
    pdf_bytes: bytes, crop_rect: fitz.Rect, dpi: int
) -> fitz.Pixmap:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return document[0].get_pixmap(dpi=dpi, clip=crop_rect, alpha=False)
    finally:
        document.close()


def _apply_padding(bbox: list[float], padding: float) -> list[float]:
    return [
        round(max(0.0, bbox[0] - padding), 9),
        round(max(0.0, bbox[1] - padding), 9),
        round(min(1.0, bbox[2] + padding), 9),
        round(min(1.0, bbox[3] + padding), 9),
    ]


def _normalized_rect(
    bbox: list[float], page_width: float, page_height: float
) -> fitz.Rect:
    return fitz.Rect(
        bbox[0] * page_width,
        bbox[1] * page_height,
        bbox[2] * page_width,
        bbox[3] * page_height,
    )


def _validate_reference(reference: dict[str, Any]) -> None:
    if reference.get("schema_version") != REFERENCE_SCHEMA_VERSION:
        raise ControlledCorpusError("controlled_corpus_reference_schema_invalid")
    authority = reference.get("authority") or {}
    if (
        authority.get("kind") != "controlled_source_exact_ground_truth"
        or authority.get("accuracy_scoring_allowed") is not True
        or authority.get("provider_or_consensus_used_as_truth") is not False
    ):
        raise ControlledCorpusError("controlled_corpus_reference_authority_invalid")
    cases = reference.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ControlledCorpusError("controlled_corpus_reference_cases_invalid")
    identifiers: set[str] = set()
    for case in cases:
        case_id = case.get("case_id") if isinstance(case, dict) else None
        if not isinstance(case_id, str) or case_id in identifiers:
            raise ControlledCorpusError("controlled_corpus_case_id_invalid")
        identifiers.add(case_id)
        if case.get("table", {}).get("table_id") != case_id:
            raise ControlledCorpusError("controlled_corpus_table_id_invalid")
        if validate_table_output(case.get("table"), table_id=case_id):
            raise ControlledCorpusError("controlled_corpus_table_contract_invalid")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ControlledCorpusError("controlled_corpus_json_not_object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
