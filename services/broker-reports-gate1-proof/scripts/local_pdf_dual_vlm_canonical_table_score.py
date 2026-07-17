#!/usr/bin/env python3
"""Score a sealed canonical-table terminal without reference leakage."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_PATH.parent
SERVICE_ROOT = SCRIPT_DIR.parent
DEFAULT_REFERENCE = (
    SERVICE_ROOT
    / "benchmarks"
    / "pdf_dual_vlm_canonical_table_v1"
    / "controlled_reference.json"
)
DEFAULT_HISTORICAL_REFERENCE = (
    SERVICE_ROOT / "benchmarks" / "pdf_table_strategy_v1" / "reference.private.json"
)

sys.path.insert(0, str(SCRIPT_DIR))

from pdf_dual_vlm_canonical_table_contracts import (  # noqa: E402
    GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE,
    REFERENCE_SCHEMA_VERSION,
    SCORE_SCHEMA_VERSION,
    TERMINAL_SCHEMA_VERSION,
    canonical_json_bytes,
    compare_tables,
    table_accuracy,
    validate_table_output,
)


DIFF_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_canonical_table_diffs_v1"
SCORE_SEAL_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_canonical_table_scores_seal_v1"


class CanonicalTableScoreError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--terminal-seal", required=True)
    parser.add_argument("--previous-terminal")
    parser.add_argument("--previous-terminal-seal")
    parser.add_argument("--controlled-reference", default=str(DEFAULT_REFERENCE))
    parser.add_argument(
        "--historical-real-reference", default=str(DEFAULT_HISTORICAL_REFERENCE)
    )
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    return run(args)


def run(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise CanonicalTableScoreError("canonical_table_score_fresh_output_required")
    output_dir.mkdir(parents=True, exist_ok=True)
    terminal_path = Path(args.terminal).resolve()
    terminal_root = terminal_path.parent
    terminal = _json(terminal_path)
    terminal_sha = _verify_terminal(
        terminal_path, terminal, _json(Path(args.terminal_seal).resolve())
    )
    previous: tuple[Path, dict[str, Any], str] | None = None
    if bool(args.previous_terminal) != bool(args.previous_terminal_seal):
        raise CanonicalTableScoreError(
            "canonical_table_previous_terminal_pair_required"
        )
    if args.previous_terminal:
        previous_path = Path(args.previous_terminal).resolve()
        previous_terminal = _json(previous_path)
        previous_sha = _verify_terminal(
            previous_path,
            previous_terminal,
            _json(Path(args.previous_terminal_seal).resolve()),
        )
        previous = (previous_path, previous_terminal, previous_sha)
    reference = _json(Path(args.controlled_reference).resolve())
    _validate_reference(reference)
    historical = _json(Path(args.historical_real_reference).resolve())
    if (historical.get("provenance") or {}).get("human_reviewed") is not False:
        raise CanonicalTableScoreError(
            "canonical_table_real_reference_review_state_unexpected"
        )

    reference_by_id = {case["case_id"]: case for case in reference["cases"]}
    controlled_results: list[dict[str, Any]] = []
    real_results: list[dict[str, Any]] = []
    for crop in terminal.get("crops") or []:
        providers = {
            provider: _load_provider_output(
                terminal_root=terminal_root,
                operation=crop[provider],
                provider=provider,
                table_id=crop["table_id"],
            )
            for provider in ("gemini", "openai")
        }
        result = _score_crop(
            crop=crop, providers=providers, reference_by_id=reference_by_id
        )
        if crop["corpus"] == "controlled_exact_ground_truth":
            controlled_results.append(result)
        elif crop["corpus"] == "real_pdf_unreviewed":
            real_results.append(result)
        else:
            raise CanonicalTableScoreError("canonical_table_score_unknown_corpus")

    controlled_aggregate = _controlled_aggregate(controlled_results)
    real_aggregate = _real_aggregate(real_results)
    crop_diagnostic = _historical_crop_diagnostic(
        real_results=real_results,
        historical=historical,
    )
    repeatability = (
        _repeatability(
            current_terminal=terminal,
            current_root=terminal_root,
            previous_terminal=previous[1],
            previous_root=previous[0].parent,
            previous_sha=previous[2],
        )
        if previous is not None
        else None
    )
    examples = _representative_examples(controlled_results + real_results)
    scores = {
        "schema_version": SCORE_SCHEMA_VERSION,
        "benchmark_id": terminal["benchmark_id"],
        "terminal_sha256": terminal_sha,
        "terminal_verified_before_reference_access": True,
        "terminal_unchanged_during_scoring": (
            hashlib.sha256(terminal_path.read_bytes()).hexdigest() == terminal_sha
        ),
        "comparison_unit": "model + provider API + schema adapter",
        "causality_established": False,
        "controlled_truth": {
            "authority": reference["authority"],
            "accuracy_scoring_allowed": True,
            "case_count": len(controlled_results),
        },
        "real_pdf_truth": {
            "human_reviewed": False,
            "accuracy_scoring_allowed": False,
            "accuracy_metrics": None,
            "reason": "historical reference is explicitly unreviewed",
        },
        "crop_policy": {
            "padding_fraction_per_page_side": GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE,
            "all_crops_byte_reproducible": all(
                item["byte_identical_reproduction"] is True
                for item in controlled_results + real_results
            ),
            "historical_unreviewed_bbox_containment_diagnostic": crop_diagnostic,
        },
        "controlled_metrics": controlled_aggregate,
        "real_pdf_consensus_diagnostics": real_aggregate,
        "repeatability": repeatability,
        "representative_examples": examples,
        "verdict": _verdict(controlled_aggregate),
        "production_readiness": False,
    }
    diffs = {
        "schema_version": DIFF_SCHEMA_VERSION,
        "terminal_sha256": terminal_sha,
        "controlled": controlled_results,
        "real_pdf_unreviewed": real_results,
    }
    score_bytes = canonical_json_bytes(scores)
    score_path = output_dir / "canonical_table_scores.json"
    score_path.write_bytes(score_bytes)
    diff_path = output_dir / "canonical_table_diffs.json"
    diff_path.write_bytes(canonical_json_bytes(diffs))
    seal = {
        "schema_version": SCORE_SEAL_SCHEMA_VERSION,
        "scores_sha256": hashlib.sha256(score_bytes).hexdigest(),
        "scores_size_bytes": len(score_bytes),
        "terminal_sha256": terminal_sha,
    }
    seal_path = output_dir / "canonical_table_scores.sha256.json"
    seal_path.write_bytes(canonical_json_bytes(seal))
    review_path = _write_review(
        results=controlled_results + real_results,
        terminal_root=terminal_root,
        output_dir=output_dir / "review",
    )
    print(
        json.dumps(
            {
                "scores": str(score_path),
                "scores_sha256": seal["scores_sha256"],
                "diffs": str(diff_path),
                "review": str(review_path),
                "verdict": scores["verdict"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _score_crop(
    *,
    crop: dict[str, Any],
    providers: dict[str, dict[str, Any]],
    reference_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    valid = {
        provider: value["terminal_status"] == "completed"
        for provider, value in providers.items()
    }
    if all(valid.values()):
        consensus = compare_tables(
            providers["gemini"]["json_output"],
            providers["openai"]["json_output"],
        )
    else:
        consensus = {
            "STRUCTURAL_CONSENSUS": False,
            "CONTENT_CONSENSUS": False,
            "FULL_TABLE_CONSENSUS": False,
            "raw_format_only_difference": False,
            "smallest_difference": {
                "class": "provider_contract_failure",
                "cell": None,
                "left": providers["gemini"]["terminal_status"],
                "right": providers["openai"]["terminal_status"],
            },
            "differences": [],
        }
    result: dict[str, Any] = {
        "case_id": crop["case_id"],
        "table_id": crop["table_id"],
        "corpus": crop["corpus"],
        "category_tags": crop.get("category_tags") or [],
        "crop_path": crop["crop_path"],
        "crop_sha256": crop["crop_sha256"],
        "detected_bbox_normalized": crop.get("detected_bbox_normalized"),
        "padded_crop_bbox_normalized": crop["padded_crop_bbox_normalized"],
        "padding_fraction_per_page_side": crop["padding_fraction_per_page_side"],
        "byte_identical_reproduction": crop["byte_identical_reproduction"],
        "provider_contract_valid": valid,
        "provider_failures": {
            provider: value.get("failure_code") for provider, value in providers.items()
        },
        "provider_canonical_outputs": {
            provider: value.get("json_output") for provider, value in providers.items()
        },
        "consensus": consensus,
        "accuracy_scored": False,
        "provider_accuracy": None,
        "outcome": "unreviewed_real_pdf_diagnostic",
    }
    if crop["corpus"] != "controlled_exact_ground_truth":
        return result
    reference_case = reference_by_id.get(crop["case_id"])
    if reference_case is None:
        raise CanonicalTableScoreError("canonical_table_controlled_reference_missing")
    reference_table = reference_case["table"]
    accuracy = {
        provider: (
            table_accuracy(value["json_output"], reference_table)
            if valid[provider]
            else None
        )
        for provider, value in providers.items()
    }
    result["accuracy_scored"] = True
    result["provider_accuracy"] = accuracy
    gemini_correct = bool(accuracy["gemini"] and accuracy["gemini"]["exact_full_table"])
    openai_correct = bool(accuracy["openai"] and accuracy["openai"]["exact_full_table"])
    full = consensus["FULL_TABLE_CONSENSUS"]
    if not all(valid.values()):
        outcome = "provider_contract_failure"
    elif full and gemini_correct and openai_correct:
        outcome = "correct_consensus"
    elif full:
        outcome = "false_consensus"
    elif gemini_correct and not openai_correct:
        outcome = "gemini_correct_openai_wrong"
    elif openai_correct and not gemini_correct:
        outcome = "openai_correct_gemini_wrong"
    else:
        outcome = "both_wrong_disagreement"
    result["outcome"] = outcome
    return result


def _controlled_aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    providers: dict[str, Any] = {}
    for provider in ("gemini", "openai"):
        valid = sum(item["provider_contract_valid"][provider] for item in results)
        exact = sum(
            bool(
                (item["provider_accuracy"] or {}).get(provider)
                and item["provider_accuracy"][provider]["exact_full_table"]
            )
            for item in results
        )
        structure = sum(
            bool(
                (item["provider_accuracy"] or {}).get(provider)
                and item["provider_accuracy"][provider]["exact_structure"]
            )
            for item in results
        )
        correct_cells = sum(
            ((item["provider_accuracy"] or {}).get(provider) or {}).get(
                "correct_content_cell_count", 0
            )
            for item in results
        )
        reference_cells = sum(
            ((item["provider_accuracy"] or {}).get(provider) or {}).get(
                "reference_cell_count", 0
            )
            for item in results
            if (item["provider_accuracy"] or {}).get(provider)
        )
        providers[provider] = {
            "contract_valid_tables": valid,
            "contract_valid_rate": _ratio(valid, total),
            "exact_full_tables": exact,
            "exact_full_table_accuracy": _ratio(exact, total),
            "exact_structure_tables": structure,
            "structural_accuracy": _ratio(structure, total),
            "correct_content_cells": correct_cells,
            "reference_cells_scored": reference_cells,
            "cell_content_accuracy": _ratio(correct_cells, reference_cells),
            "missing_cells": sum(
                ((item["provider_accuracy"] or {}).get(provider) or {}).get(
                    "missing_cell_count", 0
                )
                for item in results
            ),
            "extra_cells": sum(
                ((item["provider_accuracy"] or {}).get(provider) or {}).get(
                    "extra_cell_count", 0
                )
                for item in results
            ),
        }
    structural = sum(item["consensus"]["STRUCTURAL_CONSENSUS"] for item in results)
    content = sum(item["consensus"]["CONTENT_CONSENSUS"] for item in results)
    full = sum(item["consensus"]["FULL_TABLE_CONSENSUS"] for item in results)
    correct_consensus = sum(item["outcome"] == "correct_consensus" for item in results)
    false_consensus = sum(item["outcome"] == "false_consensus" for item in results)
    return {
        "table_count": total,
        "providers": providers,
        "dual_provider": {
            "structural_consensus_tables": structural,
            "structural_consensus_rate": _ratio(structural, total),
            "content_consensus_tables": content,
            "content_consensus_rate": _ratio(content, total),
            "full_table_consensus_tables": full,
            "full_table_consensus_rate": _ratio(full, total),
            "correct_full_consensus_tables": correct_consensus,
            "correctness_given_full_consensus": _ratio(correct_consensus, full),
            "false_consensus_count": false_consensus,
            "false_consensus_rate": _ratio(false_consensus, full),
            "automatic_acceptance_coverage": _ratio(correct_consensus, total),
            "coverage_lost_by_full_consensus": _ratio(total - full, total),
            "outcome_distribution": {
                outcome: sum(item["outcome"] == outcome for item in results)
                for outcome in (
                    "correct_consensus",
                    "false_consensus",
                    "gemini_correct_openai_wrong",
                    "openai_correct_gemini_wrong",
                    "both_wrong_disagreement",
                    "provider_contract_failure",
                )
            },
            "correlated_error_cases": [
                item["case_id"]
                for item in results
                if item["outcome"] == "false_consensus"
            ],
        },
    }


def _real_aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    return {
        "table_count": total,
        "accuracy_scored": False,
        "gemini_contract_valid_tables": sum(
            item["provider_contract_valid"]["gemini"] for item in results
        ),
        "openai_contract_valid_tables": sum(
            item["provider_contract_valid"]["openai"] for item in results
        ),
        "contract_failure_tables": {
            provider: [
                item["table_id"]
                for item in results
                if not item["provider_contract_valid"][provider]
            ]
            for provider in ("gemini", "openai")
        },
        "structural_consensus_tables": sum(
            item["consensus"]["STRUCTURAL_CONSENSUS"] for item in results
        ),
        "structural_consensus_rate": _ratio(
            sum(item["consensus"]["STRUCTURAL_CONSENSUS"] for item in results), total
        ),
        "content_consensus_tables": sum(
            item["consensus"]["CONTENT_CONSENSUS"] for item in results
        ),
        "content_consensus_rate": _ratio(
            sum(item["consensus"]["CONTENT_CONSENSUS"] for item in results), total
        ),
        "full_table_consensus_tables": sum(
            item["consensus"]["FULL_TABLE_CONSENSUS"] for item in results
        ),
        "full_table_consensus_rate": _ratio(
            sum(item["consensus"]["FULL_TABLE_CONSENSUS"] for item in results), total
        ),
        "disagreement_classes": _histogram(
            (item["consensus"].get("smallest_difference") or {}).get("class")
            for item in results
            if not item["consensus"]["FULL_TABLE_CONSENSUS"]
        ),
    }


def _historical_crop_diagnostic(
    *, real_results: list[dict[str, Any]], historical: dict[str, Any]
) -> dict[str, Any]:
    reference_by_case = {
        case["case_id"]: case for case in historical.get("cases") or []
    }
    records: list[dict[str, Any]] = []
    used: dict[str, set[int]] = {}
    for item in real_results:
        case = reference_by_case.get(item["case_id"])
        detected = item.get("detected_bbox_normalized")
        if not case or not detected:
            continue
        candidates = [region["bbox_normalized"] for region in case.get("regions") or []]
        occupied = used.setdefault(item["case_id"], set())
        ranked = sorted(
            (
                (_bbox_iou(detected, bbox), index, bbox)
                for index, bbox in enumerate(candidates)
                if index not in occupied
            ),
            reverse=True,
        )
        if not ranked:
            continue
        iou, index, reference_bbox = ranked[0]
        occupied.add(index)
        records.append(
            {
                "case_id": item["case_id"],
                "table_id": item["table_id"],
                "matched_unreviewed_region_index": index,
                "detected_bbox_iou": round(iou, 6),
                "padded_crop_contains_unreviewed_bbox": _bbox_contains(
                    item["padded_crop_bbox_normalized"], reference_bbox
                ),
            }
        )
    return {
        "authoritative": False,
        "accuracy_metric": False,
        "historical_reference_human_reviewed": False,
        "record_count": len(records),
        "all_matched_draft_bboxes_contained": bool(records)
        and all(item["padded_crop_contains_unreviewed_bbox"] for item in records),
        "records": records,
    }


def _representative_examples(results: list[dict[str, Any]]) -> dict[str, Any]:
    selectors = {
        "perfect_full_table_consensus": lambda item: item["consensus"][
            "FULL_TABLE_CONSENSUS"
        ],
        "structural_disagreement": lambda item: all(
            item["provider_contract_valid"].values()
        )
        and not item["consensus"]["STRUCTURAL_CONSENSUS"],
        "content_disagreement": lambda item: item["consensus"]["STRUCTURAL_CONSENSUS"]
        and not item["consensus"]["CONTENT_CONSENSUS"],
        "one_provider_omission": lambda item: any(
            difference.get("class") == "one_provider_omitted_cell"
            for difference in item["consensus"].get("differences") or []
        ),
        "provider_contract_failure": lambda item: not all(
            item["provider_contract_valid"].values()
        ),
        "correct_consensus": lambda item: item["outcome"] == "correct_consensus",
        "false_consensus": lambda item: item["outcome"] == "false_consensus",
        "both_providers_same_error": lambda item: item["outcome"] == "false_consensus",
    }
    examples: dict[str, Any] = {}
    for name, predicate in selectors.items():
        selected = next((item for item in results if predicate(item)), None)
        if selected is None:
            examples[name] = None
            continue
        selected_difference = selected["consensus"].get("smallest_difference")
        if name == "one_provider_omission":
            selected_difference = next(
                difference
                for difference in selected["consensus"].get("differences") or []
                if difference.get("class") == "one_provider_omitted_cell"
            )
        examples[name] = {
            "case_id": selected["case_id"],
            "table_id": selected["table_id"],
            "corpus": selected["corpus"],
            "smallest_difference": selected["consensus"].get("smallest_difference"),
            "selected_difference": selected_difference,
        }
    return examples


def _repeatability(
    *,
    current_terminal: dict[str, Any],
    current_root: Path,
    previous_terminal: dict[str, Any],
    previous_root: Path,
    previous_sha: str,
) -> dict[str, Any]:
    current_by_id = {crop["table_id"]: crop for crop in current_terminal["crops"]}
    previous_by_id = {crop["table_id"]: crop for crop in previous_terminal["crops"]}
    if set(current_by_id) != set(previous_by_id):
        raise CanonicalTableScoreError(
            "canonical_table_repeatability_case_set_mismatch"
        )
    records: list[dict[str, Any]] = []
    for table_id in sorted(current_by_id):
        current_crop = current_by_id[table_id]
        previous_crop = previous_by_id[table_id]
        input_checks = {
            "crop_sha256": current_crop["crop_sha256"] == previous_crop["crop_sha256"],
            "model_view": current_crop["model_view"] == previous_crop["model_view"],
            "padding": current_crop["padding_fraction_per_page_side"]
            == previous_crop["padding_fraction_per_page_side"],
        }
        if not all(input_checks.values()):
            raise CanonicalTableScoreError(
                "canonical_table_repeatability_input_mismatch"
            )
        provider_records: dict[str, Any] = {}
        for provider in ("gemini", "openai"):
            current_output = _load_provider_output(
                terminal_root=current_root,
                operation=current_crop[provider],
                provider=provider,
                table_id=table_id,
            )
            previous_output = _load_provider_output(
                terminal_root=previous_root,
                operation=previous_crop[provider],
                provider=provider,
                table_id=table_id,
            )
            current_status = current_output["terminal_status"]
            previous_status = previous_output["terminal_status"]
            comparison = None
            if current_status == "completed" and previous_status == "completed":
                comparison = compare_tables(
                    previous_output["json_output"], current_output["json_output"]
                )
            provider_records[provider] = {
                "previous_status": previous_status,
                "current_status": current_status,
                "status_stable": previous_status == current_status,
                "canonical_output_repeatable": (
                    comparison["FULL_TABLE_CONSENSUS"]
                    if comparison is not None
                    else False
                ),
                "smallest_difference": (
                    comparison["smallest_difference"]
                    if comparison is not None
                    else {
                        "class": "provider_contract_status_changed",
                        "left": previous_status,
                        "right": current_status,
                        "cell": None,
                    }
                ),
            }
        records.append(
            {
                "table_id": table_id,
                "corpus": current_crop["corpus"],
                "input_checks": input_checks,
                "providers": provider_records,
            }
        )

    return {
        "previous_terminal_sha256": previous_sha,
        "identical_inputs_for_every_table": all(
            all(record["input_checks"].values()) for record in records
        ),
        "providers": {
            provider: {
                corpus: _repeatability_aggregate(
                    records, provider=provider, corpus=corpus
                )
                for corpus in (
                    "controlled_exact_ground_truth",
                    "real_pdf_unreviewed",
                )
            }
            for provider in ("gemini", "openai")
        },
        "records": records,
    }


def _repeatability_aggregate(
    records: list[dict[str, Any]], *, provider: str, corpus: str
) -> dict[str, Any]:
    selected = [record for record in records if record["corpus"] == corpus]
    both_valid = [
        record
        for record in selected
        if record["providers"][provider]["previous_status"] == "completed"
        and record["providers"][provider]["current_status"] == "completed"
    ]
    repeatable = sum(
        record["providers"][provider]["canonical_output_repeatable"]
        for record in both_valid
    )
    return {
        "table_count": len(selected),
        "contract_status_stable_tables": sum(
            record["providers"][provider]["status_stable"] for record in selected
        ),
        "both_runs_contract_valid_tables": len(both_valid),
        "canonical_output_repeatable_tables": repeatable,
        "canonical_output_repeatability_rate": _ratio(repeatable, len(both_valid)),
        "changed_tables": [
            record["table_id"]
            for record in selected
            if not record["providers"][provider]["status_stable"]
            or (
                record in both_valid
                and not record["providers"][provider]["canonical_output_repeatable"]
            )
        ],
    }


def _verdict(metrics: dict[str, Any]) -> str:
    dual = metrics["dual_provider"]
    total = metrics["table_count"]
    if (
        total >= 20
        and dual["false_consensus_count"] == 0
        and dual["correctness_given_full_consensus"] == 1.0
    ):
        return "DUAL_VLM_CANONICAL_TABLE_CONSENSUS_VALIDATED"
    if dual["false_consensus_count"] == 0 and (
        dual["correct_full_consensus_tables"] > 0
    ):
        return "DUAL_VLM_CANONICAL_TABLE_CONSENSUS_PROMISING_BUT_NOT_PROVEN"
    return "DUAL_VLM_CANONICAL_TABLE_CONSENSUS_NOT_JUSTIFIED"


def _load_provider_output(
    *,
    terminal_root: Path,
    operation: dict[str, Any],
    provider: str,
    table_id: str,
) -> dict[str, Any]:
    raw_path = (terminal_root / operation["raw_artifact_path"]).resolve()
    if terminal_root not in raw_path.parents:
        raise CanonicalTableScoreError("canonical_table_raw_artifact_outside_terminal")
    if (
        hashlib.sha256(raw_path.read_bytes()).hexdigest()
        != operation["raw_artifact_sha256"]
    ):
        raise CanonicalTableScoreError("canonical_table_raw_artifact_sha_invalid")
    raw = _json(raw_path)
    if raw.get("provider") != provider or raw.get("terminal_status") != operation.get(
        "terminal_status"
    ):
        raise CanonicalTableScoreError("canonical_table_raw_artifact_identity_invalid")
    if raw.get("terminal_status") == "completed":
        errors = validate_table_output(raw.get("json_output"), table_id=table_id)
        if errors:
            raise CanonicalTableScoreError(
                "canonical_table_completed_raw_output_invalid"
            )
    return raw


def _verify_terminal(path: Path, terminal: dict[str, Any], seal: dict[str, Any]) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if (
        terminal.get("schema_version") != TERMINAL_SCHEMA_VERSION
        or seal.get("terminal_sha256") != digest
        or seal.get("terminal_size_bytes") != path.stat().st_size
    ):
        raise CanonicalTableScoreError("canonical_table_terminal_seal_invalid")
    if terminal.get("scoring_reference_accessed") is not False:
        raise CanonicalTableScoreError(
            "canonical_table_terminal_reference_boundary_invalid"
        )
    if (
        terminal.get("global_padding_fraction_per_page_side")
        != GLOBAL_PADDING_FRACTION_PER_PAGE_SIDE
    ):
        raise CanonicalTableScoreError("canonical_table_terminal_padding_invalid")
    return digest


def _validate_reference(reference: dict[str, Any]) -> None:
    if reference.get("schema_version") != REFERENCE_SCHEMA_VERSION:
        raise CanonicalTableScoreError("canonical_table_reference_schema_invalid")
    authority = reference.get("authority") or {}
    if (
        authority.get("kind") != "controlled_source_exact_ground_truth"
        or authority.get("accuracy_scoring_allowed") is not True
        or authority.get("provider_or_consensus_used_as_truth") is not False
    ):
        raise CanonicalTableScoreError("canonical_table_reference_authority_invalid")
    for case in reference.get("cases") or []:
        if validate_table_output(case.get("table"), table_id=case.get("case_id")):
            raise CanonicalTableScoreError("canonical_table_reference_table_invalid")


def _write_review(
    *, results: list[dict[str, Any]], terminal_root: Path, output_dir: Path
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = output_dir / "assets"
    assets.mkdir()
    cards: list[str] = []
    for index, item in enumerate(results):
        if item["consensus"]["FULL_TABLE_CONSENSUS"]:
            continue
        source = (terminal_root / item["crop_path"]).resolve()
        destination = assets / f"{index:03d}_{source.name}"
        shutil.copyfile(source, destination)
        difference = item["consensus"].get("smallest_difference")
        cards.append(
            "<section><h2>"
            + html.escape(item["table_id"])
            + "</h2><p>Corpus: "
            + html.escape(item["corpus"])
            + '</p><img src="assets/'
            + html.escape(destination.name)
            + '" alt="table crop"><h3>Smallest difference</h3><pre>'
            + html.escape(
                json.dumps(difference, ensure_ascii=False, indent=2, sort_keys=True)
            )
            + "</pre><h3>Gemini canonical output</h3><pre>"
            + html.escape(
                json.dumps(
                    item["provider_canonical_outputs"]["gemini"],
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            + "</pre><h3>OpenAI canonical output</h3><pre>"
            + html.escape(
                json.dumps(
                    item["provider_canonical_outputs"]["openai"],
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            + "</pre></section>"
        )
    body = "".join(cards) or "<p>No provider disagreement was observed.</p>"
    document = (
        '<!doctype html><html><head><meta charset="utf-8"><title>Canonical table disagreements</title>'
        "<style>body{font:14px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem}"
        "section{border:1px solid #bbb;padding:1rem;margin:1rem 0}img{max-width:100%;border:1px solid #ddd}"
        "pre{white-space:pre-wrap;background:#f5f5f5;padding:.75rem;overflow:auto}</style></head>"
        "<body><h1>Canonical table disagreement review</h1>" + body + "</body></html>"
    )
    path = output_dir / "index.html"
    path.write_text(document, encoding="utf-8")
    return path


def _bbox_iou(left: list[float], right: list[float]) -> float:
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(left[2], right[2])
    y1 = min(left[3], right[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _bbox_contains(outer: list[float], inner: list[float]) -> bool:
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def _histogram(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value or "none")
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))


def _ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise CanonicalTableScoreError("canonical_table_score_json_not_object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
