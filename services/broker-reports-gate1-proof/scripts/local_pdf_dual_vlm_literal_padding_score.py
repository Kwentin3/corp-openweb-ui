#!/usr/bin/env python3
"""Score sealed reference-free detections and select one frozen padding variant."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = SERVICE_ROOT / "benchmarks" / "pdf_dual_vlm_literal_v1" / "manifest.json"

sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from pdf_dual_vlm_literal_contracts import (  # noqa: E402
    PADDING_EXPERIMENT_SCHEMA_VERSION,
    PADDING_VARIANTS,
    bbox_area,
    bbox_contains,
    bbox_iou,
    canonical_json_bytes,
    sha256_json,
)


class LiteralPaddingScoreError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--seal", required=True)
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    terminal_path = Path(args.terminal).resolve()
    seal_path = Path(args.seal).resolve()
    manifest_path = Path(args.manifest).resolve()
    output_path = Path(args.output).resolve()
    if output_path.exists():
        raise LiteralPaddingScoreError("literal_padding_output_must_not_exist")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    terminal = _json(terminal_path)
    seal = _json(seal_path)
    manifest = _json(manifest_path)
    _verify_terminal(terminal_path, terminal, seal)
    if terminal.get("manifest_sha256") != sha256_json(manifest):
        raise LiteralPaddingScoreError("literal_padding_manifest_mismatch")
    context = manifest.get("historical_context") or {}
    reference_path = _repo_path(context.get("structural_reference"))
    if hashlib.sha256(reference_path.read_bytes()).hexdigest() != context.get(
        "structural_reference_file_sha256"
    ):
        raise LiteralPaddingScoreError("literal_padding_reference_sha_mismatch")
    reference = _json(reference_path)
    reference_cases = {str(case["case_id"]): case for case in reference["cases"]}
    case_results: list[dict[str, Any]] = []
    total_reference = 0
    total_candidates = 0
    total_invalid = 0
    total_matched = 0

    for case in terminal.get("cases") or []:
        case_id = str(case["case_id"])
        reference_case = reference_cases[case_id]
        regions = [
            {
                "region_id": str(region["region_id"]),
                "bbox": [float(item) for item in region["bbox_normalized"]],
            }
            for region in reference_case.get("regions") or []
        ]
        candidates = [
            item
            for item in case.get("candidates") or []
            if isinstance(item, dict) and item.get("decision") == "present"
        ]
        total_reference += len(regions)
        total_candidates += len(candidates)
        total_invalid += sum(item.get("bbox_contract_valid") is not True for item in candidates)
        valid_candidates = [item for item in candidates if item.get("bbox_contract_valid") is True]
        matches = _region_matches(valid_candidates, regions)
        total_matched += len(matches)
        case_results.append(
            {
                "case_id": case_id,
                "page_number": case.get("page_number"),
                "reference_table_count": len(regions),
                "detected_candidate_count": len(candidates),
                "invalid_bbox_count": sum(
                    item.get("bbox_contract_valid") is not True for item in candidates
                ),
                "matches": matches,
                "missed_reference_region_ids": [
                    region["region_id"]
                    for index, region in enumerate(regions)
                    if index not in {item["reference_index"] for item in matches}
                ],
                "false_candidate_ids": [
                    str(candidate.get("candidate_id"))
                    for index, candidate in enumerate(candidates)
                    if candidate.get("bbox_contract_valid") is not True
                    or index
                    not in {
                        _candidate_original_index(candidates, valid_candidates, item["candidate_index"])
                        for item in matches
                    }
                ],
                "candidates": candidates,
                "reference_regions": regions,
            }
        )

    precision = total_matched / total_candidates if total_candidates else None
    recall = total_matched / total_reference if total_reference else None
    variant_results = [
        _score_variant(
            padding=padding,
            cases=case_results,
            total_reference=total_reference,
            total_candidates=total_candidates,
            total_invalid=total_invalid,
            total_matched=total_matched,
        )
        for padding in PADDING_VARIANTS
    ]
    selected = next((item for item in variant_results if item["selection_conditions_passed"]), None)
    thresholds = manifest.get("gate_thresholds") or {}
    detection_gate_passed = bool(
        recall is not None
        and recall >= float(thresholds["detection_recall_minimum"])
        and precision is not None
        and precision >= float(thresholds["detection_precision_minimum"])
        and total_invalid <= int(thresholds["invalid_bboxes_maximum"])
        and selected is not None
        and selected["cut_reference_tables"] <= int(thresholds["cut_tables_maximum"])
        and selected["merged_reference_tables"]
        <= int(thresholds["merged_tables_maximum"])
        and selected["split_reference_tables"] <= int(thresholds["split_tables_maximum"])
        and selected["adjacent_table_inclusion"]
        <= int(thresholds["adjacent_table_inclusion_maximum"])
        and selected["crop_reproducibility_failures"]
        <= int(thresholds["crop_reproducibility_failures_maximum"])
    )
    result = {
        "schema_version": PADDING_EXPERIMENT_SCHEMA_VERSION,
        "benchmark_id": manifest["benchmark_id"],
        "detection_terminal_sha256": seal["terminal_sha256"],
        "reference_role": "development_table_region_reference_only",
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "reference_available_to_detection_runner": False,
        "reference_available_to_crop_generation": False,
        "padding_variants_predeclared_before_detection": list(PADDING_VARIANTS),
        "detected_bboxes_mutated": False,
        "detection_metrics": {
            "reference_tables": total_reference,
            "present_candidates": total_candidates,
            "matched_tables": total_matched,
            "recall": recall,
            "precision": precision,
            "invalid_bboxes": total_invalid,
        },
        "variant_results": variant_results,
        "selected_padding_fraction_per_page_side": (
            selected["padding_fraction_per_page_side"] if selected else None
        ),
        "selected_padding_percent_per_page_side": (
            selected["padding_fraction_per_page_side"] * 100 if selected else None
        ),
        "selected_padding_global_and_frozen": selected is not None,
        "no_declared_padding_variant_passed": selected is None,
        "extraction_benchmark_allowed": detection_gate_passed,
        "diagnostic_extraction_upstream_crop_set_valid": detection_gate_passed,
        "gate_a_passed": detection_gate_passed,
        "cases": [
            {key: value for key, value in case.items() if key != "candidates"}
            for case in case_results
        ],
        "regression_checks": _regression_checks(manifest, case_results, variant_results),
    }
    output_path.write_bytes(canonical_json_bytes(result))
    print(
        json.dumps(
            {
                "output": str(output_path),
                "output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
                "gate_a_passed": detection_gate_passed,
                "selected_padding": result["selected_padding_fraction_per_page_side"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if detection_gate_passed else 1


def _region_matches(
    candidates: list[dict[str, Any]], regions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    edges = sorted(
        (
            (
                bbox_iou(candidate["detected_bbox"], region["bbox"]),
                candidate_index,
                reference_index,
            )
            for candidate_index, candidate in enumerate(candidates)
            for reference_index, region in enumerate(regions)
        ),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    matched_candidates: set[int] = set()
    matched_regions: set[int] = set()
    result: list[dict[str, Any]] = []
    for iou, candidate_index, reference_index in edges:
        if iou < 0.5:
            continue
        if candidate_index in matched_candidates or reference_index in matched_regions:
            continue
        matched_candidates.add(candidate_index)
        matched_regions.add(reference_index)
        result.append(
            {
                "candidate_index": candidate_index,
                "candidate_id": candidates[candidate_index]["candidate_id"],
                "reference_index": reference_index,
                "reference_region_id": regions[reference_index]["region_id"],
                "detected_bbox_iou": round(iou, 9),
            }
        )
    return sorted(result, key=lambda item: (item["reference_index"], item["candidate_index"]))


def _score_variant(
    *,
    padding: float,
    cases: list[dict[str, Any]],
    total_reference: int,
    total_candidates: int,
    total_invalid: int,
    total_matched: int,
) -> dict[str, Any]:
    cut = 0
    merged = 0
    split = 0
    adjacent = 0
    reproducibility = 0
    attributed = 0
    crops: list[dict[str, Any]] = []
    missed = total_reference - total_matched
    false_candidates = total_candidates - total_matched
    for case in cases:
        candidates = case["candidates"]
        valid_candidates = [item for item in candidates if item.get("bbox_contract_valid") is True]
        regions = case["reference_regions"]
        region_candidate_counts = [0] * len(regions)
        for candidate_index, candidate in enumerate(valid_candidates):
            compatible = [
                index
                for index, region in enumerate(regions)
                if bbox_iou(candidate["detected_bbox"], region["bbox"]) >= 0.5
            ]
            for index in compatible:
                region_candidate_counts[index] += 1
        split += sum(count > 1 for count in region_candidate_counts)
        for match in case["matches"]:
            candidate = valid_candidates[match["candidate_index"]]
            reference = regions[match["reference_index"]]
            variant = next(
                (
                    item
                    for item in candidate.get("padding_variants") or []
                    if float(item.get("padding_fraction_per_page_side", -1)) == padding
                ),
                None,
            )
            if variant is None:
                reproducibility += 1
                continue
            crop_bbox = variant["padded_crop_bbox"]
            complete = bbox_contains(crop_bbox, reference["bbox"])
            if not complete:
                cut += 1
            other_regions = [
                item for index, item in enumerate(regions) if index != match["reference_index"]
            ]
            included_other = [
                item["region_id"]
                for item in other_regions
                if _material_intersection(crop_bbox, item["bbox"])
            ]
            if included_other:
                adjacent += 1
                merged += 1
            if variant.get("byte_identical_reproduction") is not True:
                reproducibility += 1
            if complete and not included_other:
                attributed += 1
            extra_area = max(0.0, bbox_area(crop_bbox) - bbox_area(reference["bbox"]))
            crops.append(
                {
                    "case_id": case["case_id"],
                    "page_number": case["page_number"],
                    "candidate_id": candidate["candidate_id"],
                    "reference_region_id": reference["region_id"],
                    "detected_bbox": candidate["detected_bbox"],
                    "padded_crop_bbox": crop_bbox,
                    "reference_bbox": reference["bbox"],
                    "complete_reference_table_contained": complete,
                    "adjacent_reference_table_ids_included": included_other,
                    "extra_crop_area_page_fraction": round(extra_area, 9),
                    "extra_crop_area_vs_reference_ratio": round(
                        extra_area / bbox_area(reference["bbox"]), 9
                    )
                    if bbox_area(reference["bbox"]) > 0
                    else None,
                    "neighbouring_prose_included": (
                        "possible_in_extra_area_not_yet_parser_counted"
                        if extra_area > 0
                        else "none_by_geometry"
                    ),
                    "added_content_downstream_effect": "pending_extraction_or_not_run",
                    "crop_sha256": variant["crop_sha256"],
                    "crop_bytes": variant["crop_bytes"],
                    "crop_width": variant["crop_width"],
                    "crop_height": variant["crop_height"],
                    "byte_identical_reproduction": variant[
                        "byte_identical_reproduction"
                    ],
                }
            )
    exactly_one = attributed == total_reference and false_candidates == 0
    selection_passed = bool(
        missed == 0
        and false_candidates == 0
        and total_invalid == 0
        and cut == 0
        and merged == 0
        and split == 0
        and adjacent == 0
        and reproducibility == 0
        and exactly_one
    )
    return {
        "padding_fraction_per_page_side": padding,
        "padding_percent_per_page_side": padding * 100,
        "cut_reference_tables": cut,
        "merged_reference_tables": merged,
        "split_reference_tables": split,
        "adjacent_table_inclusion": adjacent,
        "missed_reference_tables": missed,
        "false_candidates": false_candidates,
        "invalid_bboxes": total_invalid,
        "crop_reproducibility_failures": reproducibility,
        "crops_attributable_to_exactly_one_reference_table": attributed,
        "every_crop_attributable_to_exactly_one_reference_table": exactly_one,
        "selection_conditions_passed": selection_passed,
        "crops": crops,
    }


def _material_intersection(left: list[float], right: list[float]) -> bool:
    x = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    y = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    return x * y > 1e-8


def _candidate_original_index(
    all_candidates: list[dict[str, Any]],
    valid_candidates: list[dict[str, Any]],
    valid_index: int,
) -> int:
    target = valid_candidates[valid_index]
    return next(index for index, item in enumerate(all_candidates) if item is target)


def _regression_checks(
    manifest: dict[str, Any],
    cases: list[dict[str, Any]],
    variants: list[dict[str, Any]],
) -> dict[str, Any]:
    policy = manifest.get("detection_regressions") or {}
    by_case = {str(case["case_id"]): case for case in cases}
    false_case_results = {
        case_id: not bool(by_case[case_id]["false_candidate_ids"])
        for case_id in policy.get("false_candidate_case_ids") or []
    }
    missed_case_results = {
        case_id: not bool(by_case[case_id]["missed_reference_region_ids"])
        for case_id in policy.get("missed_reference_table_case_ids") or []
    }
    invalid_case_results = {
        case_id: by_case[case_id]["invalid_bbox_count"] == 0
        for case_id in policy.get("invalid_bbox_case_ids") or []
    }
    cut_by_variant = {
        str(item["padding_fraction_per_page_side"]): [
            f"{crop['case_id']}:{crop['reference_region_id']}"
            for crop in item["crops"]
            if not crop["complete_reference_table_contained"]
        ]
        for item in variants
    }
    return {
        "false_candidate_regressions_passed": false_case_results,
        "missed_table_regressions_passed": missed_case_results,
        "invalid_bbox_regressions_passed": invalid_case_results,
        "previously_cut_reference_tables": policy.get(
            "previously_cut_reference_tables"
        ),
        "cut_reference_tables_by_padding": cut_by_variant,
        "all_reference_tables_checked": sum(
            case["reference_table_count"] for case in cases
        )
        == manifest.get("expected_reference_tables"),
    }


def _verify_terminal(
    path: Path, terminal: dict[str, Any], seal: dict[str, Any]
) -> None:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if (
        seal.get("terminal_sha256") != digest
        or seal.get("terminal_size_bytes") != path.stat().st_size
    ):
        raise LiteralPaddingScoreError("literal_padding_terminal_seal_mismatch")
    if terminal.get("reference_accessed") is not False:
        raise LiteralPaddingScoreError("literal_padding_detection_reference_boundary_invalid")


def _repo_path(value: Any) -> Path:
    if not isinstance(value, str):
        raise LiteralPaddingScoreError("literal_padding_repo_path_invalid")
    path = (REPO_ROOT / value).resolve()
    try:
        path.relative_to(REPO_ROOT)
    except ValueError as exc:
        raise LiteralPaddingScoreError("literal_padding_repo_path_escape") from exc
    return path


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise LiteralPaddingScoreError("literal_padding_json_invalid") from exc
    if not isinstance(value, dict):
        raise LiteralPaddingScoreError("literal_padding_json_not_object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
