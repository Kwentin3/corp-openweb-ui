#!/usr/bin/env python3
"""Score a sealed literal terminal against a separately sealed human reference."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
sys.path.insert(0, str(SCRIPT_DIR))

from pdf_dual_vlm_literal_contracts import (  # noqa: E402
    REFERENCE_SEAL_SCHEMA_VERSION,
    SCORING_SCHEMA_VERSION,
    bbox_iou,
    canonical_json_bytes,
    canonicalize_entry,
    canonicalize_text,
    entry_regions_compatible,
    match_entries,
    parse_visible_numeric,
    project_entry_to_page_normalized,
    validate_reference,
)


SCORE_SEAL_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_literal_scores_seal_v1"


class LiteralReferenceScoreError(RuntimeError):
    pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--terminal-seal", required=True)
    parser.add_argument("--padding-experiment", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--reference-seal", required=True)
    parser.add_argument("--diffs", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--scored-diffs-output", required=True)
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    terminal_path = Path(args.terminal).resolve()
    terminal_seal_path = Path(args.terminal_seal).resolve()
    padding_path = Path(args.padding_experiment).resolve()
    reference_path = Path(args.reference).resolve()
    reference_seal_path = Path(args.reference_seal).resolve()
    diffs_path = Path(args.diffs).resolve()
    output_path = Path(args.output).resolve()
    scored_diffs_path = Path(args.scored_diffs_output).resolve()
    if output_path.exists() or scored_diffs_path.exists():
        raise LiteralReferenceScoreError("literal_reference_score_fresh_output_required")

    terminal = _json(terminal_path)
    terminal_seal = _json(terminal_seal_path)
    padding = _json(padding_path)
    reference = _json(reference_path)
    reference_seal = _json(reference_seal_path)
    diffs = _json(diffs_path)
    terminal_sha = _verify_seal(
        terminal_path,
        terminal_seal,
        digest_field="terminal_sha256",
        size_field="terminal_size_bytes",
        failure="literal_reference_score_terminal_seal_invalid",
    )
    reference_sha = _verify_seal(
        reference_path,
        reference_seal,
        digest_field="reference_sha256",
        size_field="reference_size_bytes",
        failure="literal_reference_score_reference_seal_invalid",
    )
    _verify_inputs(
        terminal=terminal,
        terminal_sha=terminal_sha,
        padding=padding,
        reference=reference,
        reference_seal=reference_seal,
        diffs=diffs,
    )

    reference_tables = {
        (str(case["case_id"]), str(table["table_identifier"])): table
        for case in reference["cases"]
        for table in case.get("tables") or []
    }
    crop_to_reference = _crop_reference_map(padding)
    table_scores: list[dict[str, Any]] = []
    score_lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for crop in terminal.get("crops") or []:
        case_id = str(crop["case_id"])
        candidate_id = str(crop["candidate_id"])
        region_id = crop_to_reference.get((case_id, candidate_id))
        table_identifier = f"{case_id}:{region_id}" if region_id else None
        reference_table = reference_tables.get((case_id, str(table_identifier)))
        if not reference_table:
            table_scores.append(
                {
                    "case_id": case_id,
                    "candidate_id": candidate_id,
                    "reference_table_identifier": table_identifier,
                    "score_status": "no_unique_reference_table_alignment",
                }
            )
            continue
        score = _score_table(crop, reference_table)
        table_scores.append(score)
        score_lookup[(case_id, candidate_id)] = score

    provider_metrics = {
        provider: _aggregate_provider_metrics(table_scores, provider)
        for provider in ("gemini", "openai")
    }
    dual_reference_outcomes = _aggregate_dual_outcomes(table_scores)
    scored_diffs = _score_diffs(
        diffs=diffs,
        score_lookup=score_lookup,
        reference_sha=reference_sha,
        invalid_upstream=terminal.get("diagnostic_invalid_upstream_crop_set") is True,
    )
    scored_diffs_path.parent.mkdir(parents=True, exist_ok=True)
    scored_diffs_path.write_bytes(canonical_json_bytes(scored_diffs))
    scored_diffs_sha = hashlib.sha256(scored_diffs_path.read_bytes()).hexdigest()

    score = {
        "schema_version": SCORING_SCHEMA_VERSION,
        "entrypoint": SCRIPT_PATH.name,
        "benchmark_id": terminal.get("benchmark_id"),
        "terminal_sha256": terminal_sha,
        "reference_sha256": reference_sha,
        "reference_human_reviewed": True,
        "reference_verified_before_scoring": True,
        "reference_available_to_provider_execution": False,
        "terminal_contract_verified_before_reference_access": True,
        "terminal_unchanged_during_scoring": (
            hashlib.sha256(terminal_path.read_bytes()).hexdigest() == terminal_sha
        ),
        "reference_unchanged_during_scoring": (
            hashlib.sha256(reference_path.read_bytes()).hexdigest() == reference_sha
        ),
        "diagnostic_invalid_upstream_crop_set": terminal.get(
            "diagnostic_invalid_upstream_crop_set"
        ),
        "financial_semantic_classification_scored": False,
        "scoring_denominator_policy": {
            "included_review_statuses": ["confirmed", "corrected"],
            "excluded_review_statuses": ["ambiguous", "excluded"],
            "misses_count_as_incorrect_for_accuracy": True,
            "ambiguous_entry_alignment_counts_as_unmatched": True,
            "literal_entry_correctness": (
                "canonical row label and header path plus exact visible value and cell state"
            ),
        },
        "provider_metrics": provider_metrics,
        "dual_reference_outcomes": dual_reference_outcomes,
        "table_scores": table_scores,
        "scored_diffs_sha256": scored_diffs_sha,
        "benchmark_disposition": (
            "diagnostic_scored_invalid_upstream"
            if terminal.get("diagnostic_invalid_upstream_crop_set") is True
            else "reference_scored"
        ),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_json_bytes(score))
    score_sha = hashlib.sha256(output_path.read_bytes()).hexdigest()
    seal_path = output_path.with_suffix(output_path.suffix + ".sha256.json")
    seal_path.write_bytes(
        canonical_json_bytes(
            {
                "schema_version": SCORE_SEAL_SCHEMA_VERSION,
                "scores_sha256": score_sha,
                "scores_size_bytes": output_path.stat().st_size,
                "reference_sha256": reference_sha,
                "terminal_sha256": terminal_sha,
            }
        )
    )
    print(
        json.dumps(
            {
                "scores": str(output_path),
                "scores_sha256": score_sha,
                "seal": str(seal_path),
                "scored_diffs": str(scored_diffs_path),
                "scored_diffs_sha256": scored_diffs_sha,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _score_table(
    crop: dict[str, Any], reference_table: dict[str, Any]
) -> dict[str, Any]:
    reference_entries_raw = [
        item
        for item in reference_table.get("entries") or []
        if item.get("review_status") in {"confirmed", "corrected"}
    ]
    reference_entries = [
        project_entry_to_page_normalized(
            _reference_as_provider(item), reference_table["complete_table_bbox"]
        )
        for item in reference_entries_raw
    ]
    providers: dict[str, Any] = {}
    for provider in ("gemini", "openai"):
        operation = crop.get(provider) or {}
        raw_entries = (
            (operation.get("json_output") or {}).get("entries") or []
            if operation.get("terminal_status") == "completed"
            else []
        )
        entries = [
            project_entry_to_page_normalized(item, crop["padded_crop_bbox"])
            for item in raw_entries
        ]
        providers[provider] = _score_provider(
            provider_entries=entries,
            reference_entries=reference_entries,
            terminal_status=str(operation.get("terminal_status") or "missing"),
        )
    dual_outcomes = _dual_outcomes_for_table(
        providers["gemini"], providers["openai"], reference_entries
    )
    return {
        "case_id": crop["case_id"],
        "candidate_id": crop["candidate_id"],
        "reference_table_identifier": reference_table["table_identifier"],
        "score_status": "scored",
        "diagnostic_only": crop.get("diagnostic_only"),
        "reference_entry_count": len(reference_entries),
        "reference_ambiguous_count": sum(
            item.get("review_status") == "ambiguous"
            for item in reference_table.get("entries") or []
        ),
        "reference_excluded_count": sum(
            item.get("review_status") == "excluded"
            for item in reference_table.get("entries") or []
        ),
        "reference_entries": copy.deepcopy(reference_entries_raw),
        "providers": providers,
        "dual_reference_outcomes": dual_outcomes,
    }


def _score_provider(
    *,
    provider_entries: list[dict[str, Any]],
    reference_entries: list[dict[str, Any]],
    terminal_status: str,
) -> dict[str, Any]:
    alignment = match_entries(provider_entries, reference_entries)
    provider_by_id = {str(item["entry_id"]): item for item in provider_entries}
    reference_by_id = {str(item["entry_id"]): item for item in reference_entries}
    results: list[dict[str, Any]] = []
    provider_to_reference: dict[str, str] = {}
    reference_to_provider: dict[str, str] = {}
    ambiguous_provider_ids: set[str] = set()
    ambiguous_reference_ids: set[str] = set()
    for match in alignment["matches"]:
        provider_id = str(match["gemini_entry_id"])
        reference_id = str(match["openai_entry_id"])
        if not match.get("match_unique"):
            ambiguous_provider_ids.add(provider_id)
            ambiguous_reference_ids.add(reference_id)
            continue
        provider_to_reference[provider_id] = reference_id
        reference_to_provider[reference_id] = provider_id
        results.append(
            _score_pair(provider_by_id[provider_id], reference_by_id[reference_id])
        )
    matched_reference_ids = set(reference_to_provider)
    matched_provider_ids = set(provider_to_reference)
    reference_count = len(reference_entries)
    provider_count = len(provider_entries)
    numeric_reference_count = sum(
        parse_visible_numeric(item["visible_value_text"]).parsed_numeric_value
        is not None
        for item in reference_entries
    )
    counts = {
        "literal_entry_correct": sum(item["literal_entry_correct"] for item in results),
        "exact_visible_value_correct": sum(
            item["exact_visible_value_correct"] for item in results
        ),
        "canonical_numeric_value_correct": sum(
            item["canonical_numeric_value_correct"] for item in results
        ),
        "sign_correct": sum(item["sign_correct"] for item in results),
        "row_label_correct": sum(item["row_label_correct"] for item in results),
        "header_path_correct": sum(item["header_path_correct"] for item in results),
        "row_value_binding_correct": sum(
            item["row_value_binding_correct"] for item in results
        ),
        "header_value_binding_correct": sum(
            item["header_value_binding_correct"] for item in results
        ),
        "source_region_covered": sum(
            item["source_region_covered"] for item in results
        ),
    }
    return {
        "terminal_status": terminal_status,
        "provider_entry_count": provider_count,
        "reference_entry_count": reference_count,
        "unique_aligned_entries": len(results),
        "ambiguous_alignments": len(ambiguous_provider_ids),
        "missed_reference_entries": reference_count - len(matched_reference_ids),
        "invented_provider_entries": provider_count - len(matched_provider_ids),
        "counts": counts,
        "metrics": {
            "literal_entry_precision": _rate(
                counts["literal_entry_correct"], provider_count
            ),
            "literal_entry_recall": _rate(
                counts["literal_entry_correct"], reference_count
            ),
            "exact_visible_value_accuracy": _rate(
                counts["exact_visible_value_correct"], reference_count
            ),
            "canonical_numeric_value_accuracy": _rate(
                counts["canonical_numeric_value_correct"], numeric_reference_count
            ),
            "sign_accuracy": _rate(counts["sign_correct"], numeric_reference_count),
            "row_label_accuracy": _rate(
                counts["row_label_correct"], reference_count
            ),
            "header_path_accuracy": _rate(
                counts["header_path_correct"], reference_count
            ),
            "row_value_binding_accuracy": _rate(
                counts["row_value_binding_correct"], reference_count
            ),
            "header_value_binding_accuracy": _rate(
                counts["header_value_binding_correct"], reference_count
            ),
            "source_region_coverage": _rate(
                counts["source_region_covered"], reference_count
            ),
        },
        "numeric_reference_entry_count": numeric_reference_count,
        "alignment": alignment,
        "provider_to_reference": provider_to_reference,
        "reference_to_provider": reference_to_provider,
        "entry_results": results,
    }


def _score_pair(
    provider_entry: dict[str, Any], reference_entry: dict[str, Any]
) -> dict[str, Any]:
    provider = canonicalize_entry(provider_entry)
    reference = canonicalize_entry(reference_entry)
    row_correct = (
        provider["row_label_text_canonical"]
        == reference["row_label_text_canonical"]
    )
    header_correct = (
        provider["column_header_path_canonical"]
        == reference["column_header_path_canonical"]
    )
    exact_value = (
        provider_entry["visible_value_text"] == reference_entry["visible_value_text"]
    )
    canonical_value = (
        provider["visible_value_text_canonical"]
        == reference["visible_value_text_canonical"]
    )
    numeric_reference = reference["parsed_numeric_value"] is not None
    numeric_correct = (
        numeric_reference
        and provider["parsed_numeric_value"] == reference["parsed_numeric_value"]
    )
    sign_correct = numeric_reference and provider["parsed_sign"] == reference["parsed_sign"]
    value_equivalent = canonical_value or numeric_correct
    row_region = _bbox_compatible(
        provider_entry["row_label_bbox"], reference_entry["row_label_bbox"]
    )
    value_region = _bbox_compatible(
        provider_entry["value_bbox"], reference_entry["value_bbox"]
    )
    header_region = _headers_compatible(
        provider_entry["header_bboxes"], reference_entry["header_bboxes"]
    )
    return {
        "provider_entry_id": provider_entry["entry_id"],
        "reference_entry_id": reference_entry["entry_id"],
        "literal_entry_correct": (
            row_correct
            and header_correct
            and exact_value
            and provider_entry["cell_state"] == reference_entry["cell_state"]
        ),
        "literal_entry_canonical_correct": (
            row_correct and header_correct and value_equivalent
        ),
        "exact_visible_value_correct": exact_value,
        "canonical_numeric_value_correct": numeric_correct,
        "sign_correct": sign_correct,
        "row_label_correct": row_correct,
        "header_path_correct": header_correct,
        "row_value_binding_correct": (
            row_correct and value_equivalent and row_region and value_region
        ),
        "header_value_binding_correct": (
            header_correct and value_equivalent and header_region and value_region
        ),
        "source_region_covered": entry_regions_compatible(
            provider_entry, reference_entry
        ),
        "raw_mapping": {
            "provider": _raw_mapping(provider_entry),
            "reference": _raw_mapping(reference_entry),
        },
        "provider_source_bboxes": {
            "row_label_bbox": copy.deepcopy(provider_entry["row_label_bbox"]),
            "header_bboxes": copy.deepcopy(provider_entry["header_bboxes"]),
            "value_bbox": copy.deepcopy(provider_entry["value_bbox"]),
        },
    }


def _dual_outcomes_for_table(
    gemini: dict[str, Any],
    openai: dict[str, Any],
    reference_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gemini_results = {
        str(item["reference_entry_id"]): item for item in gemini["entry_results"]
    }
    openai_results = {
        str(item["reference_entry_id"]): item for item in openai["entry_results"]
    }
    results: list[dict[str, Any]] = []
    for reference_entry in reference_entries:
        reference_id = str(reference_entry["entry_id"])
        left = gemini_results.get(reference_id)
        right = openai_results.get(reference_id)
        left_exact = bool(left and left["literal_entry_correct"])
        right_exact = bool(right and right["literal_entry_correct"])
        left_canonical = bool(left and left["literal_entry_canonical_correct"])
        right_canonical = bool(right and right["literal_entry_canonical_correct"])
        category = (
            "gemini_correct_openai_wrong"
            if left_exact and not right_exact
            else "openai_correct_gemini_wrong"
            if right_exact and not left_exact
            else "both_exact_correct"
            if left_exact and right_exact
            else "both_wrong"
        )
        both_correct_format_different = bool(
            left_canonical
            and right_canonical
            and left
            and right
            and left["raw_mapping"]["provider"]
            != right["raw_mapping"]["provider"]
        )
        both_wrong_same_way = bool(
            not left_canonical
            and not right_canonical
            and left
            and right
            and _canonical_mapping(left["raw_mapping"]["provider"])
            == _canonical_mapping(right["raw_mapping"]["provider"])
        )
        left_mapping = left["raw_mapping"]["provider"] if left else None
        right_mapping = right["raw_mapping"]["provider"] if right else None
        same_value = bool(
            left_mapping
            and right_mapping
            and _values_equivalent(
                str(left_mapping["visible_value_text"]),
                str(right_mapping["visible_value_text"]),
            )
        )
        same_value_different_headers = bool(
            same_value
            and left_mapping
            and right_mapping
            and tuple(
                canonicalize_text(item)
                for item in left_mapping["column_header_path"]
            )
            != tuple(
                canonicalize_text(item)
                for item in right_mapping["column_header_path"]
            )
        )
        different_values_same_region = bool(
            left
            and right
            and not same_value
            and _bbox_compatible(
                left["provider_source_bboxes"]["value_bbox"],
                right["provider_source_bboxes"]["value_bbox"],
            )
        )
        results.append(
            {
                "reference_entry_id": reference_id,
                "category": category,
                "gemini_provider_entry_id": (
                    left.get("provider_entry_id") if left else None
                ),
                "openai_provider_entry_id": (
                    right.get("provider_entry_id") if right else None
                ),
                "both_correct_format_different": both_correct_format_different,
                "both_wrong_same_way": both_wrong_same_way,
                "same_value_different_headers": same_value_different_headers,
                "different_values_same_region": different_values_same_region,
            }
        )
    return results


def _aggregate_provider_metrics(
    table_scores: list[dict[str, Any]], provider: str
) -> dict[str, Any]:
    scored = [item for item in table_scores if item.get("score_status") == "scored"]
    provider_scores = [item["providers"][provider] for item in scored]
    reference_count = sum(item["reference_entry_count"] for item in provider_scores)
    provider_count = sum(item["provider_entry_count"] for item in provider_scores)
    numeric_count = sum(
        item["numeric_reference_entry_count"] for item in provider_scores
    )
    count_names = next(iter(provider_scores), {"counts": {}})["counts"].keys()
    counts = {
        name: sum(item["counts"][name] for item in provider_scores)
        for name in count_names
    }
    return {
        "tables_scored": len(scored),
        "terminal_contract_failures": sum(
            item["terminal_status"] != "completed" for item in provider_scores
        ),
        "provider_entry_count": provider_count,
        "reference_entry_count": reference_count,
        "numeric_reference_entry_count": numeric_count,
        "missed_reference_entries": sum(
            item["missed_reference_entries"] for item in provider_scores
        ),
        "invented_provider_entries": sum(
            item["invented_provider_entries"] for item in provider_scores
        ),
        "ambiguous_alignments": sum(
            item["ambiguous_alignments"] for item in provider_scores
        ),
        "counts": counts,
        "metrics": {
            "literal_entry_precision": _rate(
                counts.get("literal_entry_correct", 0), provider_count
            ),
            "literal_entry_recall": _rate(
                counts.get("literal_entry_correct", 0), reference_count
            ),
            "exact_visible_value_accuracy": _rate(
                counts.get("exact_visible_value_correct", 0), reference_count
            ),
            "canonical_numeric_value_accuracy": _rate(
                counts.get("canonical_numeric_value_correct", 0), numeric_count
            ),
            "sign_accuracy": _rate(counts.get("sign_correct", 0), numeric_count),
            "row_label_accuracy": _rate(
                counts.get("row_label_correct", 0), reference_count
            ),
            "header_path_accuracy": _rate(
                counts.get("header_path_correct", 0), reference_count
            ),
            "row_value_binding_accuracy": _rate(
                counts.get("row_value_binding_correct", 0), reference_count
            ),
            "header_value_binding_accuracy": _rate(
                counts.get("header_value_binding_correct", 0), reference_count
            ),
            "source_region_coverage": _rate(
                counts.get("source_region_covered", 0), reference_count
            ),
        },
    }


def _aggregate_dual_outcomes(
    table_scores: list[dict[str, Any]],
) -> dict[str, Any]:
    outcomes = [
        outcome
        for table in table_scores
        if table.get("score_status") == "scored"
        for outcome in table["dual_reference_outcomes"]
    ]
    categories: dict[str, int] = {}
    for item in outcomes:
        categories[item["category"]] = categories.get(item["category"], 0) + 1
    return {
        "reference_entries_compared": len(outcomes),
        "categories": dict(sorted(categories.items())),
        "both_correct_format_different": sum(
            item["both_correct_format_different"] for item in outcomes
        ),
        "both_wrong_same_way": sum(item["both_wrong_same_way"] for item in outcomes),
        "same_value_different_headers": sum(
            item["same_value_different_headers"] for item in outcomes
        ),
        "different_values_same_region": sum(
            item["different_values_same_region"] for item in outcomes
        ),
        "entries": outcomes,
    }


def _score_diffs(
    *,
    diffs: dict[str, Any],
    score_lookup: dict[tuple[str, str], dict[str, Any]],
    reference_sha: str,
    invalid_upstream: bool,
) -> dict[str, Any]:
    output = copy.deepcopy(diffs)
    for item in output.get("disagreements") or []:
        table = score_lookup.get((str(item.get("case_id")), str(item.get("candidate_id"))))
        if not table:
            item["human_reference_answer"] = None
            item["final_benchmark_disposition"] = "no_unique_reference_table_alignment"
            continue
        reference_by_id = {
            str(entry["reference_entry_id"]): entry
            for entry in table["reference_entries"]
        }
        reference_ids: set[str] = set()
        for provider, field in (
            ("gemini", "exact_gemini_output"),
            ("openai", "exact_openai_output"),
        ):
            value = item.get(field)
            if not isinstance(value, dict):
                continue
            provider_id = str(value.get("entry_id"))
            reference_id = table["providers"][provider]["provider_to_reference"].get(
                provider_id
            )
            if reference_id:
                reference_ids.add(reference_id)
        item["human_reference_answer"] = [
            copy.deepcopy(reference_by_id[entry_id])
            for entry_id in sorted(reference_ids)
            if entry_id in reference_by_id
        ] or None
        outcome_by_reference = {
            str(outcome["reference_entry_id"]): outcome
            for outcome in table["dual_reference_outcomes"]
        }
        if len(reference_ids) == 1:
            outcome = outcome_by_reference.get(next(iter(reference_ids)))
            item["final_benchmark_disposition"] = (
                str(outcome["category"])
                if outcome
                else "human_reference_attached_without_dual_outcome"
            )
        elif reference_ids:
            item["final_benchmark_disposition"] = "multiple_human_reference_alignments"
        else:
            item["final_benchmark_disposition"] = (
                "no_unique_human_reference_alignment"
            )
    output["human_reference_added_during_scoring"] = True
    output["human_reference_status"] = "human_reviewed_sealed"
    output["human_reference_sha256"] = reference_sha
    output["final_benchmark_disposition"] = (
        "diagnostic_scored_invalid_upstream" if invalid_upstream else "reference_scored"
    )
    return output


def _crop_reference_map(padding: dict[str, Any]) -> dict[tuple[str, str], str]:
    result: dict[tuple[str, str], str] = {}
    for case in padding.get("cases") or []:
        case_id = str(case["case_id"])
        for match in case.get("matches") or []:
            key = (case_id, str(match["candidate_id"]))
            if key in result:
                raise LiteralReferenceScoreError(
                    "literal_reference_score_crop_reference_not_unique"
                )
            result[key] = str(match["reference_region_id"])
    return result


def _reference_as_provider(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_id": str(entry["reference_entry_id"]),
        "row_label_text": entry["row_label_text"],
        "column_header_path": copy.deepcopy(entry["column_header_path"]),
        "visible_value_text": entry["visible_value_text"],
        "row_label_bbox": copy.deepcopy(entry["row_label_bbox"]),
        "header_bboxes": copy.deepcopy(entry["header_bboxes"]),
        "value_bbox": copy.deepcopy(entry["value_bbox"]),
        "cell_state": entry["cell_state"],
        "uncertainty_codes": [],
    }


def _raw_mapping(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_label_text": entry["row_label_text"],
        "column_header_path": copy.deepcopy(entry["column_header_path"]),
        "visible_value_text": entry["visible_value_text"],
    }


def _canonical_mapping(value: dict[str, Any]) -> tuple[str, tuple[str, ...], str]:
    return (
        canonicalize_text(value.get("row_label_text")),
        tuple(canonicalize_text(item) for item in value.get("column_header_path") or []),
        canonicalize_text(value.get("visible_value_text")),
    )


def _values_equivalent(left: str, right: str) -> bool:
    if canonicalize_text(left) == canonicalize_text(right):
        return True
    left_numeric = parse_visible_numeric(left).parsed_numeric_value
    right_numeric = parse_visible_numeric(right).parsed_numeric_value
    return left_numeric is not None and left_numeric == right_numeric


def _bbox_compatible(left: list[float], right: list[float]) -> bool:
    if bbox_iou(left, right) >= 0.1:
        return True
    left_center = ((left[0] + left[2]) / 2, (left[1] + left[3]) / 2)
    right_center = ((right[0] + right[2]) / 2, (right[1] + right[3]) / 2)
    tolerance_x = max(left[2] - left[0], right[2] - right[0])
    tolerance_y = max(left[3] - left[1], right[3] - right[1])
    return (
        abs(left_center[0] - right_center[0]) <= tolerance_x
        and abs(left_center[1] - right_center[1]) <= tolerance_y
    )


def _headers_compatible(
    left: list[list[float]], right: list[list[float]]
) -> bool:
    if not left and not right:
        return True
    return bool(left and right and any(_bbox_compatible(a, b) for a in left for b in right))


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 9) if denominator else None


def _verify_inputs(
    *,
    terminal: dict[str, Any],
    terminal_sha: str,
    padding: dict[str, Any],
    reference: dict[str, Any],
    reference_seal: dict[str, Any],
    diffs: dict[str, Any],
) -> None:
    if reference_seal.get("schema_version") != REFERENCE_SEAL_SCHEMA_VERSION:
        raise LiteralReferenceScoreError("literal_reference_score_reference_seal_schema_invalid")
    if reference_seal.get("human_reviewed") is not True:
        raise LiteralReferenceScoreError("literal_reference_score_reference_not_human_reviewed")
    errors = validate_reference(reference, require_human_reviewed=True)
    if errors:
        raise LiteralReferenceScoreError(errors[0])
    if terminal.get("reference_accessed") is not False:
        raise LiteralReferenceScoreError("literal_reference_score_terminal_reference_boundary_invalid")
    if padding.get("detection_terminal_sha256") != terminal.get(
        "detection_terminal_sha256"
    ):
        raise LiteralReferenceScoreError("literal_reference_score_padding_lineage_invalid")
    if diffs.get("terminal_sha256") != terminal_sha:
        raise LiteralReferenceScoreError("literal_reference_score_diffs_lineage_invalid")
    if diffs.get("human_reference_added_during_scoring") is not False:
        raise LiteralReferenceScoreError("literal_reference_score_expected_unscored_diffs")


def _verify_seal(
    path: Path,
    seal: dict[str, Any],
    *,
    digest_field: str,
    size_field: str,
    failure: str,
) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if seal.get(digest_field) != digest or seal.get(size_field) != path.stat().st_size:
        raise LiteralReferenceScoreError(failure)
    return digest


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise LiteralReferenceScoreError("literal_reference_score_json_invalid") from exc
    if not isinstance(value, dict):
        raise LiteralReferenceScoreError("literal_reference_score_json_not_object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
