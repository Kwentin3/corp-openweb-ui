#!/usr/bin/env python3
"""Prepare and finalize the human-only reference for the dual-VLM benchmark."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
DEFAULT_REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = (
    SERVICE_ROOT / "benchmarks" / "pdf_dual_vlm_fact_v1" / "manifest.json"
)
DEFAULT_LEGACY_REFERENCE = (
    SERVICE_ROOT / "benchmarks" / "pdf_table_strategy_v1" / "reference.private.json"
)
DEFAULT_LEGACY_TERMINAL = (
    DEFAULT_REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_pdf_table_strategy_benchmark_2026-07-16"
    / "run2-gate"
    / "run"
    / "terminal.private.json"
)
DEFAULT_LEGACY_SEAL = DEFAULT_LEGACY_TERMINAL.with_name("terminal.private.sha256.json")
DEFAULT_CORPUS_ROOT = (
    DEFAULT_REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_pdf_structural_holdout_public_v5_2026-07-15"
    / "corpus"
)
EXPECTED_STRUCTURAL_LOCATOR_TEXT_MISMATCHES = frozenset(
    {"moomoo_annual_p14:r2:r2_row_10_col_3"}
)


sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.pdf_table_raster import (  # noqa: E402
    PdfTableRasterConfig,
    PdfTableRasterFactory,
)
from broker_reports_gate1.pdf_text_layer import (  # noqa: E402
    PdfParserCapabilityRequest,
    PdfTextLayerParserFactory,
)
from pdf_dual_vlm_fact_review import (  # noqa: E402
    PROPOSED_REFERENCE_SCHEMA,
    LOCATOR_CONFIRMATION_REQUIRED_PROPOSAL_SHA256,
    PdfDualVlmFactReviewDecisionFactory,
    _require_locator_confirmation_record,
    canonical_json_bytes,
    finalize_human_reference,
    generate_review_pack,
    sha256_json,
    validate_proposed_reference,
)


class ReferencePackError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="create a source-only review pack")
    prepare.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    prepare.add_argument("--legacy-reference", default=str(DEFAULT_LEGACY_REFERENCE))
    prepare.add_argument("--legacy-terminal", default=str(DEFAULT_LEGACY_TERMINAL))
    prepare.add_argument("--legacy-seal", default=str(DEFAULT_LEGACY_SEAL))
    prepare.add_argument("--corpus-root", default=str(DEFAULT_CORPUS_ROOT))
    prepare.add_argument("--output-dir", required=True)

    finalize = commands.add_parser(
        "finalize", help="validate exported human intent and seal the reference"
    )
    finalize.add_argument("--proposed-reference", required=True)
    finalize.add_argument("--review-index", required=True)
    finalize.add_argument("--review-intent", required=True)
    finalize.add_argument("--confirmation-record")
    finalize.add_argument("--prior-decisions")
    finalize.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        return _prepare(args)
    return _finalize(args)


def _prepare(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    _require_fresh_directory(output_dir)
    manifest_path = Path(args.manifest).resolve()
    legacy_reference_path = Path(args.legacy_reference).resolve()
    legacy_terminal_path = Path(args.legacy_terminal).resolve()
    legacy_seal_path = Path(args.legacy_seal).resolve()
    corpus_root = Path(args.corpus_root).resolve()

    manifest = _json_object(manifest_path)
    legacy_reference = _json_object(legacy_reference_path)
    legacy_terminal = _json_object(legacy_terminal_path)
    legacy_seal = _json_object(legacy_seal_path)
    manifest_sha = sha256_json(manifest)
    _verify_legacy_inputs(
        manifest=manifest,
        legacy_reference=legacy_reference,
        legacy_terminal=legacy_terminal,
        legacy_seal=legacy_seal,
        legacy_terminal_path=legacy_terminal_path,
    )

    renderer = PdfTableRasterFactory(PdfTableRasterConfig(padding_points=0)).create()
    parser = PdfTextLayerParserFactory().create(
        PdfParserCapabilityRequest(capability="layout_words")
    )
    artifacts_dir = output_dir / "artifacts"
    artifacts_dir.mkdir(parents=True)
    page_paths: dict[str, Path] = {}
    crop_paths: dict[str, Path] = {}
    proposal_cases: list[dict[str, Any]] = []
    reference_by_case = {
        str(case["case_id"]): case for case in legacy_reference["cases"]
    }
    terminal_by_case = {str(case["case_id"]): case for case in legacy_terminal["cases"]}
    parse_cache: dict[str, Any] = {}
    pdf_cache: dict[str, bytes] = {}

    for case in manifest["cases"]:
        case_id = str(case["case_id"])
        source = _source_path(corpus_root, str(case["relative_pdf"]))
        pdf_bytes = source.read_bytes()
        _require_hash_and_size(
            pdf_bytes, str(case["pdf_sha256"]), int(case["pdf_bytes"])
        )
        pdf_sha = str(case["pdf_sha256"])
        pdf_cache.setdefault(pdf_sha, pdf_bytes)
        if pdf_sha not in parse_cache:
            parse_cache[pdf_sha] = parser.parse(pdf_bytes)
        page_number = int(case["page_number"])
        page = parse_cache[pdf_sha].pages[page_number - 1]
        page_bbox = [float(item) for item in case["page_bbox_points"]]
        if [float(page["width"]), float(page["height"])] != page_bbox[2:]:
            raise ReferencePackError("reference_pack_page_identity_mismatch")

        full_page = renderer.render_full_page(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha,
            document_ref=case_id,
            page_ref=f"{case_id}_human_reference_source",
            page_number=page_number,
            expected_page_bbox=page_bbox,
            dpi=int(case["render_dpi"]),
        )
        page_png = base64.b64decode(full_page["private_png_base64"])
        page_path = artifacts_dir / case_id / "page.private.png"
        page_path.parent.mkdir(parents=True, exist_ok=True)
        page_path.write_bytes(page_png)
        page_sha = hashlib.sha256(page_png).hexdigest()
        page_paths[case_id] = page_path

        legacy_case = reference_by_case.get(case_id)
        prior_case = terminal_by_case.get(case_id)
        if not isinstance(legacy_case, dict) or not isinstance(prior_case, dict):
            raise ReferencePackError("reference_pack_case_lineage_missing")
        regions: list[dict[str, Any]] = []
        prior_tables = _prior_tables(prior_case)
        for legacy_region in legacy_case.get("regions") or []:
            region_id = str(legacy_region["region_id"])
            source_bbox = [float(item) for item in legacy_region["bbox_points"]]
            normalized_bbox = [float(item) for item in legacy_region["bbox_normalized"]]
            crop = renderer.render(
                pdf_bytes=pdf_bytes,
                pdf_sha256=pdf_sha,
                document_ref=case_id,
                page_number=page_number,
                table_ref=f"{case_id}_{region_id}_human_reference_candidate",
                table_bbox=source_bbox,
                dpi=int(case["render_dpi"]),
            )
            crop_png = base64.b64decode(crop["private_png_base64"])
            crop_sha = hashlib.sha256(crop_png).hexdigest()
            crop_path = page_path.parent / f"{region_id}.crop.private.png"
            crop_path.write_bytes(crop_png)
            crop_paths[f"{case_id}:{region_id}"] = crop_path
            scoped_words = _words_in_bbox(page.get("word_inventory") or [], source_bbox)
            regions.append(
                {
                    "region_id": region_id,
                    "bbox_normalized": normalized_bbox,
                    "crop_sha256": crop_sha,
                    "evidence_medium": _evidence_medium(
                        list(case.get("category_tags") or []), scoped_words
                    ),
                    "one_complete_table": True,
                    "cuts": {
                        "header": False,
                        "total": False,
                        "row": False,
                        "column": False,
                    },
                    "includes_neighboring_prose": False,
                    "includes_other_table": False,
                    "facts": _proposed_facts(
                        legacy_region=legacy_region,
                        prior_tables=prior_tables,
                        crop_bbox=normalized_bbox,
                        crop_sha256=crop_sha,
                    ),
                }
            )
        proposal_cases.append(
            {
                "case_id": case_id,
                "document_id": case_id,
                "pdf_sha256": pdf_sha,
                "page_number": page_number,
                "page_sha256": page_sha,
                "expected_kind": str(legacy_case["expected_kind"]),
                "regions": regions,
            }
        )

    _require_expected_structural_locator_text_mismatches(proposal_cases)

    proposed = {
        "schema_version": PROPOSED_REFERENCE_SCHEMA,
        "benchmark_id": str(manifest["benchmark_id"]),
        "manifest_sha256": manifest_sha,
        "cases": proposal_cases,
    }
    errors = validate_proposed_reference(proposed)
    if errors:
        raise ReferencePackError(f"reference_pack_proposal_invalid:{errors[0]}")
    proposal_path = output_dir / "proposed-reference.private.json"
    proposal_path.write_bytes(canonical_json_bytes(proposed))
    generated = generate_review_pack(
        proposed_reference=proposed,
        page_artifact_paths=page_paths,
        crop_artifact_paths=crop_paths,
        output_dir=output_dir / "review",
    )
    preparation = {
        "schema_version": "broker_reports_pdf_dual_vlm_fact_reference_preparation_v1",
        "human_reviewed": False,
        "may_be_used_for_scoring": False,
        "manifest_sha256": manifest_sha,
        "proposed_reference_sha256": sha256_json(proposed),
        "legacy_reference_sha256": _sha256_file(legacy_reference_path),
        "legacy_terminal_sha256": _sha256_file(legacy_terminal_path),
        "review_index_sha256": generated["review_index"]["index_sha256"],
        "review_html_sha256": generated["review_html_sha256"],
        "proposal_role": "unreviewed_source_only_candidate",
        "human_action_required": True,
    }
    preparation["preparation_sha256"] = sha256_json(preparation)
    preparation_path = output_dir / "preparation.safe.json"
    preparation_path.write_bytes(canonical_json_bytes(preparation))
    print(
        json.dumps(
            {
                "status": "human_review_required",
                "proposed_reference": str(proposal_path),
                "review_index": generated["review_index_path"],
                "review_html": generated["review_html_path"],
                "preparation": str(preparation_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _finalize(args: argparse.Namespace) -> int:
    proposed = _json_object(Path(args.proposed_reference).resolve())
    review_index = _json_object(Path(args.review_index).resolve())
    intent = _json_object(Path(args.review_intent).resolve())
    confirmation_record = (
        _json_object(Path(args.confirmation_record).resolve())
        if args.confirmation_record
        else None
    )
    prior = (
        _json_object(Path(args.prior_decisions).resolve())
        if args.prior_decisions
        else None
    )
    output_dir = Path(args.output_dir).resolve()
    _require_fresh_directory(output_dir)
    decisions = PdfDualVlmFactReviewDecisionFactory().create_from_intent(
        review_index=review_index,
        intent=intent,
        prior_decisions=prior,
    )
    _require_locator_confirmation_record(
        confirmation_record,
        review_decisions=decisions,
        review_intent=intent,
        required=(
            review_index["proposed_reference_sha256"]
            in LOCATOR_CONFIRMATION_REQUIRED_PROPOSAL_SHA256
        ),
    )
    decisions_path = output_dir / "review.decisions.private.json"
    decisions_path.write_bytes(canonical_json_bytes(decisions))
    copied_confirmation_path = None
    if confirmation_record is not None:
        copied_confirmation_path = output_dir / "locator-confirmation.private.json"
        copied_confirmation_path.write_bytes(canonical_json_bytes(confirmation_record))
    finalized = finalize_human_reference(
        proposed_reference=proposed,
        review_index=review_index,
        review_decisions=decisions,
        output_dir=output_dir,
        confirmation_record=confirmation_record,
    )
    print(
        json.dumps(
            {
                "status": "human_reference_sealed",
                "review_decisions": str(decisions_path),
                "confirmation_record": (
                    str(copied_confirmation_path)
                    if copied_confirmation_path is not None
                    else None
                ),
                "reference": finalized["reference_path"],
                "reference_seal": finalized["seal_path"],
                "reference_sha256": finalized["seal"]["reference_sha256"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _verify_legacy_inputs(
    *,
    manifest: dict[str, Any],
    legacy_reference: dict[str, Any],
    legacy_terminal: dict[str, Any],
    legacy_seal: dict[str, Any],
    legacy_terminal_path: Path,
) -> None:
    base = manifest.get("base_benchmark")
    if not isinstance(base, dict):
        raise ReferencePackError("reference_pack_base_benchmark_missing")
    terminal_sha = _sha256_file(legacy_terminal_path)
    if (
        terminal_sha != base.get("accepted_terminal_sha256")
        or legacy_seal.get("terminal_sha256") != terminal_sha
        or legacy_seal.get("terminal_size_bytes") != legacy_terminal_path.stat().st_size
    ):
        raise ReferencePackError("reference_pack_legacy_terminal_seal_mismatch")
    if legacy_terminal.get("reference_accessed") is not False:
        raise ReferencePackError("reference_pack_legacy_terminal_boundary_invalid")
    if legacy_reference.get("benchmark_id") != "pdf_table_strategy_v1":
        raise ReferencePackError("reference_pack_legacy_reference_invalid")
    provenance = legacy_reference.get("provenance")
    if (
        not isinstance(provenance, dict)
        or provenance.get("human_reviewed") is not False
    ):
        raise ReferencePackError("reference_pack_legacy_reference_truth_invalid")
    if legacy_reference.get("manifest_sha256") != base.get("manifest_semantic_sha256"):
        raise ReferencePackError("reference_pack_legacy_manifest_mismatch")


def _proposed_facts(
    *,
    legacy_region: dict[str, Any],
    prior_tables: list[dict[str, Any]],
    crop_bbox: list[float],
    crop_sha256: str,
) -> list[dict[str, Any]]:
    rows = legacy_region.get("cells") or []
    header_indices = {
        int(item) - 1
        for item in legacy_region.get("header_rows") or []
        if isinstance(item, int) and item > 0
    }
    facts: list[dict[str, Any]] = []
    region_id = str(legacy_region["region_id"])
    for row_index, row in enumerate(rows):
        if row_index in header_indices or not isinstance(row, list) or not row:
            continue
        row_label = str(row[0]).strip()
        if not row_label:
            continue
        for column_index, raw_value in enumerate(row[1:], start=1):
            visible_value = str(raw_value).strip()
            numeric = _numeric_value(visible_value)
            if numeric is None:
                continue
            header_path = _header_path(rows, header_indices, column_index)
            locators, locator_uncertainty = _fact_locators(
                prior_tables=prior_tables,
                row_label=row_label,
                visible_value=visible_value,
                header_path=header_path,
                value_column_index=column_index,
                total_value_columns=len(row) - 1,
                crop_bbox=crop_bbox,
                crop_sha256=crop_sha256,
            )
            uncertainty = ["proposed_from_unreviewed_legacy_grid"]
            uncertainty.extend(locator_uncertainty)
            if not header_path:
                uncertainty.append("header_not_present_in_source")
            if (
                locators["row_label"] is None
                or locators["value"] is None
                or (header_path and not locators["header"])
            ):
                uncertainty.append("source_locator_requires_human_correction")
            facts.append(
                {
                    "fact_id": (
                        f"{region_id}_row_{row_index + 1}_col_{column_index + 1}"
                    ),
                    "fact_type": "financial_numeric_fact",
                    "row_label": row_label,
                    "normalized_row_identity": None,
                    "header_path": header_path,
                    "visible_value": visible_value,
                    "numeric_value": numeric,
                    "sign": _sign(numeric),
                    "period": None,
                    "currency": None,
                    "unit": None,
                    "scale": None,
                    "entity": None,
                    "qualifiers": [],
                    "source_regions": locators,
                    "uncertainty": uncertainty,
                    "alternative_interpretation": None,
                }
            )
    return facts


def _require_expected_structural_locator_text_mismatches(
    proposal_cases: list[dict[str, Any]],
) -> None:
    actual = {
        f"{case['case_id']}:{region['region_id']}:{fact['fact_id']}"
        for case in proposal_cases
        for region in case["regions"]
        for fact in region["facts"]
        if "source_locator_text_mismatch_requires_human_confirmation"
        in fact["uncertainty"]
    }
    if actual != EXPECTED_STRUCTURAL_LOCATOR_TEXT_MISMATCHES:
        raise ReferencePackError("reference_pack_unexpected_locator_text_mismatch")


def _fact_locators(
    *,
    prior_tables: list[dict[str, Any]],
    row_label: str,
    visible_value: str,
    header_path: list[str],
    value_column_index: int,
    total_value_columns: int,
    crop_bbox: list[float],
    crop_sha256: str,
) -> tuple[dict[str, Any], list[str]]:
    row_match = _matching_prior_row(
        prior_tables,
        row_label,
        visible_value,
        value_column_index=value_column_index,
        total_value_columns=total_value_columns,
    )
    row_locator = None
    value_locator = None
    header_locators: list[dict[str, Any]] = []
    uncertainty: list[str] = []
    if row_match is not None:
        table, row_cells, value_cells, value_text_matched = row_match
        if not value_text_matched:
            uncertainty.append(
                "source_locator_text_mismatch_requires_human_confirmation"
            )
        if row_cells:
            row_locator = _locator(
                crop_sha256, row_label, _union_cell_bbox(row_cells), crop_bbox
            )
        if value_cells:
            value_locator = _locator(
                crop_sha256,
                visible_value,
                _union_cell_bbox(value_cells),
                crop_bbox,
            )
        all_cells = (table.get("physical") or {}).get("cells") or []
        target_column_ids = {
            cell.get("column_id")
            for cell in value_cells
            if isinstance(cell.get("column_id"), str)
        }
        target_column_cells = [
            cell for cell in all_cells if cell.get("column_id") in target_column_ids
        ]
        for header in header_path:
            candidates = _matching_text_cells(target_column_cells, header)
            if not candidates:
                candidates = _matching_text_cells(all_cells, header)
            if candidates:
                header_locators.append(
                    _locator(
                        crop_sha256,
                        header,
                        _union_cell_bbox(candidates),
                        crop_bbox,
                    )
                )
    return (
        {
            "row_label": row_locator,
            "header": header_locators,
            "value": value_locator,
            "context": [],
        },
        uncertainty,
    )


def _matching_prior_row(
    tables: list[dict[str, Any]],
    row_label: str,
    visible_value: str,
    *,
    value_column_index: int,
    total_value_columns: int,
) -> (
    tuple[
        dict[str, Any],
        list[dict[str, Any]],
        list[dict[str, Any]],
        bool,
    ]
    | None
):
    positional_fallback = None
    for table in tables:
        cells = (table.get("physical") or {}).get("cells") or []
        grouped: dict[str, list[dict[str, Any]]] = {}
        for cell in cells:
            if isinstance(cell, dict) and isinstance(cell.get("row_id"), str):
                grouped.setdefault(cell["row_id"], []).append(cell)
        for row_cells in grouped.values():
            label_cells = [
                cell for cell in row_cells if _same_visible(cell.get("text"), row_label)
            ]
            if not label_cells:
                continue
            value_candidates = [
                cell
                for cell in row_cells
                if cell not in label_cells and str(cell.get("text") or "").strip()
            ]
            target_value_cells = _positional_value_cells(
                value_candidates,
                value_column_index=value_column_index,
                total_value_columns=total_value_columns,
            )
            if not target_value_cells:
                continue
            matches = _matching_text_cell_groups(target_value_cells, visible_value)
            if matches:
                return table, label_cells, matches[0], True
            if positional_fallback is None:
                positional_fallback = (
                    table,
                    label_cells,
                    target_value_cells,
                    False,
                )
    return positional_fallback


def _positional_value_cells(
    cells: list[dict[str, Any]],
    *,
    value_column_index: int,
    total_value_columns: int,
) -> list[dict[str, Any]]:
    if total_value_columns == 1:
        return cells
    by_column: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        column_id = cell.get("column_id")
        if not isinstance(column_id, str):
            return []
        by_column.setdefault(column_id, []).append(cell)
    columns = sorted(
        by_column.values(),
        key=lambda items: min(_cell_horizontal_order(item) for item in items),
    )
    if len(columns) != total_value_columns or not 1 <= value_column_index <= len(
        columns
    ):
        return []
    return columns[value_column_index - 1]


def _matching_text_cells(cells: Any, visible_text: str) -> list[dict[str, Any]]:
    valid = [
        cell
        for cell in cells or []
        if isinstance(cell, dict)
        and isinstance(cell.get("bbox"), (list, tuple))
        and len(cell["bbox"]) == 4
        and str(cell.get("text") or "").strip()
    ]
    exact = [cell for cell in valid if _same_visible(cell.get("text"), visible_text)]
    if len(exact) == 1:
        return exact
    if len(exact) > 1:
        return []

    by_column: dict[str, list[dict[str, Any]]] = {}
    for cell in valid:
        column_id = cell.get("column_id")
        if isinstance(column_id, str):
            by_column.setdefault(column_id, []).append(cell)
    column_matches: list[list[dict[str, Any]]] = []
    for column_cells in by_column.values():
        matches = _matching_text_cell_groups(
            column_cells,
            visible_text,
            order_key=_cell_reading_order,
        )
        if len(matches) > 1:
            return []
        if matches:
            column_matches.append(matches[0])
    if len(column_matches) == 1:
        return column_matches[0]
    if len(column_matches) > 1:
        return []
    matches = _matching_text_cell_groups(
        valid,
        visible_text,
        order_key=_cell_reading_order,
    )
    return matches[0] if len(matches) == 1 else []


def _matching_text_cell_groups(
    cells: list[dict[str, Any]],
    visible_text: str,
    *,
    order_key: Any = None,
) -> list[list[dict[str, Any]]]:
    if order_key is None:
        order_key = _cell_horizontal_order
    ordered = sorted(cells, key=order_key)
    matches: list[list[dict[str, Any]]] = []
    for start in range(len(ordered)):
        for end in range(start + 1, len(ordered) + 1):
            candidate = ordered[start:end]
            rendered = " ".join(str(cell.get("text") or "") for cell in candidate)
            if _same_visible(rendered, visible_text):
                matches.append(candidate)
    return sorted(matches, key=lambda items: order_key(items[0]))


def _cell_horizontal_order(cell: dict[str, Any]) -> tuple[float, float]:
    bbox = [float(item) for item in cell["bbox"]]
    return (bbox[0], bbox[1])


def _cell_reading_order(cell: dict[str, Any]) -> tuple[float, float]:
    bbox = [float(item) for item in cell["bbox"]]
    return (bbox[1], bbox[0])


def _prior_tables(case: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    strategies = case.get("strategies")
    if not isinstance(strategies, dict):
        return result
    for name in ("B", "A"):
        strategy = strategies.get(name)
        if not isinstance(strategy, dict):
            continue
        extraction = strategy.get("extraction")
        if not isinstance(extraction, dict):
            continue
        for table in extraction.get("tables") or []:
            if not isinstance(table, dict):
                continue
            digest = sha256_json(table)
            if digest not in seen:
                result.append(table)
                seen.add(digest)
    return result


def _header_path(
    rows: list[Any], header_indices: set[int], column_index: int
) -> list[str]:
    result: list[str] = []
    for index in sorted(header_indices):
        if index >= len(rows) or not isinstance(rows[index], list):
            continue
        row = rows[index]
        value = str(row[column_index]).strip() if column_index < len(row) else ""
        if value and value not in result:
            result.append(value)
    return result


def _numeric_value(value: str) -> str | None:
    rendered = value.strip()
    if not rendered or not re.search(r"[0-9]", rendered):
        return None
    negative = rendered.startswith("(") and rendered.endswith(")")
    cleaned = rendered.replace("$", "").replace(",", "").strip()
    if negative:
        cleaned = cleaned[1:-1].strip()
    if cleaned.startswith("-"):
        negative = True
        cleaned = cleaned[1:].strip()
    if re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", cleaned) is None:
        return None
    normalized = cleaned.lstrip("0") or "0"
    if "." in cleaned:
        whole, fraction = cleaned.split(".", 1)
        normalized = (whole.lstrip("0") or "0") + "." + fraction
    return f"-{normalized}" if negative and normalized != "0" else normalized


def _sign(numeric: str) -> str:
    if numeric == "0" or re.fullmatch(r"0\.0+", numeric):
        return "zero"
    return "negative" if numeric.startswith("-") else "positive"


def _locator(
    artifact_sha256: str,
    visible_text: str,
    page_bbox: list[float],
    crop_bbox: list[float],
) -> dict[str, Any]:
    width = crop_bbox[2] - crop_bbox[0]
    height = crop_bbox[3] - crop_bbox[1]
    transformed = [
        (page_bbox[0] - crop_bbox[0]) / width,
        (page_bbox[1] - crop_bbox[1]) / height,
        (page_bbox[2] - crop_bbox[0]) / width,
        (page_bbox[3] - crop_bbox[1]) / height,
    ]
    return {
        "artifact_sha256": artifact_sha256,
        "bbox_normalized": [round(min(1.0, max(0.0, item)), 9) for item in transformed],
        "visible_text": visible_text,
    }


def _union_cell_bbox(cells: list[dict[str, Any]]) -> list[float]:
    boxes = [[float(item) for item in cell["bbox"]] for cell in cells]
    return [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]


def _words_in_bbox(
    words: list[dict[str, Any]], bbox: list[float]
) -> list[dict[str, Any]]:
    result = []
    for word in words:
        word_bbox = word.get("bbox") if isinstance(word, dict) else None
        if not isinstance(word_bbox, (list, tuple)) or len(word_bbox) != 4:
            continue
        center_x = (float(word_bbox[0]) + float(word_bbox[2])) / 2
        center_y = (float(word_bbox[1]) + float(word_bbox[3])) / 2
        if bbox[0] <= center_x <= bbox[2] and bbox[1] <= center_y <= bbox[3]:
            result.append(word)
    return result


def _evidence_medium(categories: list[str], words: list[dict[str, Any]]) -> str:
    raster_tagged = bool({"raster_image", "without_text_layer"} & set(categories))
    if raster_tagged:
        return "mixed" if words else "raster"
    return "text_layer"


def _same_visible(left: Any, right: Any) -> bool:
    def normalized(value: Any) -> str:
        return " ".join(str(value or "").split()).casefold()

    return normalized(left) == normalized(right)


def _source_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ReferencePackError("reference_pack_source_path_escape") from exc
    if not path.is_file():
        raise ReferencePackError("reference_pack_source_missing")
    return path


def _require_hash_and_size(payload: bytes, sha256: str, size: int) -> None:
    if len(payload) != size or hashlib.sha256(payload).hexdigest() != sha256:
        raise ReferencePackError("reference_pack_source_identity_mismatch")


def _require_fresh_directory(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ReferencePackError("reference_pack_fresh_output_required")
    path.mkdir(parents=True, exist_ok=True)


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ReferencePackError("reference_pack_json_invalid") from exc
    if not isinstance(value, dict):
        raise ReferencePackError("reference_pack_json_invalid")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
