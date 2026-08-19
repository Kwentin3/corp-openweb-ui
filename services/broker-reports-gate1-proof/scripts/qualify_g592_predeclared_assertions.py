#!/usr/bin/env python3
"""Qualify frozen G5.92 development or untouched holdout against source truth."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any


DEVELOPMENT_ORDINALS = (10, 12, 14, 16, 20, 22, 52)
HOLDOUT_ORDINALS = (128,)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("development", "holdout"), required=True)
    parser.add_argument("--g588-evidence-dir", type=Path, required=True)
    parser.add_argument("--g591-evidence-dir", type=Path)
    parser.add_argument("--private-plan-dir", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()

    source_root = args.g588_evidence_dir.resolve()
    root = args.private_plan_dir.resolve()
    safe_path = args.safe_output.resolve()
    private_path = root / f"{args.phase}-qualification.private.json"
    for output in (private_path, safe_path):
        if output.exists():
            raise SystemExit(f"output_must_be_new:{output.name}")

    plan = _read_json(root / "frozen-plan.private.json")
    replay = _read_json(root / f"{args.phase}-replay.private.json")
    controls = _read_json(source_root / "controls.private.json")
    chunks = _read_json(root / "chunks.private.json")
    ordinals = DEVELOPMENT_ORDINALS if args.phase == "development" else HOLDOUT_ORDINALS
    if (
        plan.get("goal") != "G5.92"
        or replay.get("goal") != "G5.92"
        or replay.get("phase") != args.phase
        or tuple(plan[f"{args.phase}_ordinals"]) != ordinals
        or replay.get("semantic_attempts") != len(ordinals)
        or replay.get("transport_submissions") != len(ordinals)
        or replay.get("semantic_retries") != 0
        or replay.get("best_of_n") is not False
        or replay.get("prompt_variants") != 1
        or replay.get("model_variants") != 1
        or len(replay.get("outcomes", [])) != len(ordinals)
        or any(
            item.get("terminal_status") != "validated"
            for item in replay.get("outcomes", [])
        )
    ):
        raise SystemExit("g592_frozen_replay_contract_invalid")

    actual_by_row: dict[tuple[str, int], list[str]] = defaultdict(list)
    unknown_ids = duplicate_ids = invented_objects = 0
    relation_keys = 0
    for outcome in replay["outcomes"]:
        metrics = outcome["metrics"]
        unknown_ids += int(metrics["unknown_assertion_ids"])
        duplicate_ids += int(metrics["duplicate_assertion_ids"])
        invented_objects += int(metrics["invented_source_objects"])
        for classification in outcome["validated_output"]["classifications"]:
            target = classification["source_target"]
            key = _row_key(target)
            if key is None:
                raise SystemExit("non_row_assertion_reached_qualification")
            actual_by_row[key].extend(
                item
                for item in classification["financial_types"]
                if item != "UNMAPPED"
            )
            relation_keys += len(
                {"related_fact_id", "relation", "relation_id", "event_id"}
                & set(classification)
            )

    row_key_by_control: dict[tuple[int, str], tuple[str, int]] = {}
    for ordinal in ordinals:
        for mapping in chunks[str(ordinal)]["target_mappings"]:
            target = mapping["canonical_target"]
            if target.get("kind") == "table_row":
                row_key_by_control[(ordinal, mapping["target_alias"])] = (
                    target["node_id"],
                    target["row"],
                )

    if args.phase == "development":
        dividend_controls = {
            (item["ordinal"], item["row_id"])
            for item in controls["true_dividend_exact"]
        }
        withholding_controls = [
            item
            for item in controls["existing_tax_exact"]
            if (item["ordinal"], item["row_id"]) not in dividend_controls
        ]
        scores = {
            "tax_adjustment": _score_fixed(
                controls["affected_tax_exact"],
                row_key_by_control,
                actual_by_row,
                ["TAX_ADJUSTMENT"],
            ),
            "ordinary_withholding": _score_fixed(
                withholding_controls,
                row_key_by_control,
                actual_by_row,
                ["TAX_WITHHELD"],
            ),
            "true_dividend": _score_fixed(
                controls["true_dividend_exact"],
                row_key_by_control,
                actual_by_row,
                ["DIVIDEND_INCOME"],
            ),
            "structural_unmapped": _score_fixed(
                controls["structural_none"],
                row_key_by_control,
                actual_by_row,
                [],
            ),
            "cross_type": _score_source_expected(
                controls["cross_type"], row_key_by_control, actual_by_row
            ),
        }
        checks = {
            "tax_adjustment_105_of_105": scores["tax_adjustment"]["passed"],
            "wrong_tax_adjustment_as_dividend_zero": all(
                "DIVIDEND_INCOME" not in item["actual_labels"]
                for item in scores["tax_adjustment"]["failures"]
            )
            and scores["tax_adjustment"]["correct"] == 105,
            "ordinary_withholding_113_of_113": scores["ordinary_withholding"][
                "passed"
            ],
            "true_dividend_25_of_25": scores["true_dividend"]["passed"],
            "structural_unmapped_12_of_12": scores["structural_unmapped"][
                "passed"
            ],
            "cross_type_4_of_4": scores["cross_type"]["passed"],
            "unknown_assertion_ids_zero": unknown_ids == 0,
            "duplicate_assertion_ids_zero": duplicate_ids == 0,
            "invented_source_objects_zero": invented_objects == 0,
            "inferred_relations_zero": relation_keys == 0,
        }
        passed = all(checks.values())
        development_proven_for_holdout = passed
    else:
        scores = {
            "untouched_holdout": _score_source_expected(
                controls["holdout"], row_key_by_control, actual_by_row
            )
        }
        checks = {
            "untouched_holdout_7_of_7": scores["untouched_holdout"]["passed"],
            "unknown_assertion_ids_zero": unknown_ids == 0,
            "duplicate_assertion_ids_zero": duplicate_ids == 0,
            "invented_source_objects_zero": invented_objects == 0,
            "inferred_relations_zero": relation_keys == 0,
        }
        passed = all(checks.values())
        development_proven_for_holdout = None

    usage = _usage_summary(replay)
    baseline = (
        _baseline_summary(args.g591_evidence_dir.resolve())
        if args.phase == "development" and args.g591_evidence_dir
        else None
    )
    private = {
        "schema_version": "broker_reports_g592_qualification_private_v1",
        "goal": "G5.92",
        "phase": args.phase,
        "passed": passed,
        "development_proven_for_holdout": development_proven_for_holdout,
        "checks": checks,
        "scores": scores,
        "usage": usage,
        "whole_table_baseline": baseline,
        "plan_sha256": _file_sha256(root / "frozen-plan.private.json"),
        "replay_sha256": _file_sha256(root / f"{args.phase}-replay.private.json"),
        "source_truth_sha256": _file_sha256(source_root / "controls.private.json"),
        "semantic_retries": 0,
        "best_of_n": False,
        "prompt_variants": 1,
        "model_variants": 1,
        "broker_specific_rules": 0,
        "literal_specific_rules": 0,
        "tax_calculations": 0,
        "role_binding": False,
        "production_activation": False,
    }
    _write_json(private_path, private)
    safe = {
        "schema_version": "broker_reports_g592_qualification_safe_v1",
        "goal": "G5.92",
        "phase": args.phase,
        "passed": passed,
        "development_proven_for_holdout": development_proven_for_holdout,
        "checks": checks,
        "scores": {
            key: {
                "passed": value["passed"],
                "correct": value["correct"],
                "total": value["total"],
            }
            for key, value in scores.items()
        },
        "usage": usage,
        "whole_table_baseline": baseline,
        "semantic_retries": 0,
        "best_of_n": False,
        "prompt_variants": 1,
        "model_variants": 1,
        "broker_specific_rules": 0,
        "literal_specific_rules": 0,
        "tax_calculations": 0,
        "role_binding": False,
        "production_activation": False,
        "private_result_sha256": _file_sha256(private_path),
    }
    _write_json(safe_path, safe)
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 2


def _score_fixed(
    controls: list[dict[str, Any]],
    keys: dict[tuple[int, str], tuple[str, int]],
    actual: dict[tuple[str, int], list[str]],
    expected: list[str],
) -> dict[str, Any]:
    return _score(
        [{**item, "expected_labels": expected} for item in controls], keys, actual
    )


def _score_source_expected(
    controls: list[dict[str, Any]],
    keys: dict[tuple[int, str], tuple[str, int]],
    actual: dict[tuple[str, int], list[str]],
) -> dict[str, Any]:
    return _score(controls, keys, actual)


def _score(
    controls: list[dict[str, Any]],
    keys: dict[tuple[int, str], tuple[str, int]],
    actual: dict[tuple[str, int], list[str]],
) -> dict[str, Any]:
    failures = []
    for control in controls:
        key = keys[(control["ordinal"], control["row_id"])]
        expected = sorted(control["expected_labels"])
        got = sorted(set(actual.get(key, [])))
        if got != expected:
            failures.append(
                {
                    "ordinal": control["ordinal"],
                    "row_id": control["row_id"],
                    "expected_labels": expected,
                    "actual_labels": got,
                }
            )
    return {
        "passed": not failures,
        "correct": len(controls) - len(failures),
        "total": len(controls),
        "failures": failures,
    }


def _usage_summary(replay: dict[str, Any]) -> dict[str, Any]:
    metrics = [item["metrics"] for item in replay["outcomes"]]
    return {
        "provider_calls": replay["transport_submissions"],
        "assertions": sum(item["assertions_predeclared"] for item in metrics),
        "input_tokens": sum(item["input_tokens"] or 0 for item in metrics),
        "output_tokens": sum(item["output_tokens"] or 0 for item in metrics),
        "total_tokens": sum(item["total_tokens"] or 0 for item in metrics),
        "latency_ms": sum(item["duration_ms"] or 0 for item in metrics),
        "peak_input_chars": max(item["final_model_input_chars"] for item in metrics),
    }


def _baseline_summary(root: Path) -> dict[str, Any]:
    qualification = _read_json(root / "qualification.private.json")
    replay = _read_json(root / "replay.private.json")
    return {
        "tax_adjustment_correct": qualification["scores"]["tax_adjustment"][
            "correct"
        ],
        "tax_adjustment_total": qualification["scores"]["tax_adjustment"]["total"],
        "wrong_tax_adjustment_as_dividend": sum(
            "DIVIDEND_INCOME" in item.get("actual_labels", [])
            for item in qualification["scores"]["tax_adjustment"]["failures"]
        ),
        "provider_calls": replay["transport_submissions"],
        "input_tokens": sum(
            (item.get("metrics") or {}).get("input_tokens") or 0
            for item in replay["outcomes"]
        ),
        "output_tokens": sum(
            (item.get("metrics") or {}).get("output_tokens") or 0
            for item in replay["outcomes"]
        ),
        "total_tokens": sum(
            (item.get("metrics") or {}).get("total_tokens") or 0
            for item in replay["outcomes"]
        ),
        "latency_ms": sum(
            (item.get("metrics") or {}).get("duration_ms") or 0
            for item in replay["outcomes"]
        ),
        "qualification_sha256": _file_sha256(root / "qualification.private.json"),
        "replay_sha256": _file_sha256(root / "replay.private.json"),
    }


def _row_key(target: dict[str, Any]) -> tuple[str, int] | None:
    node_id = target.get("node_id")
    row = target.get("row")
    if isinstance(node_id, str) and isinstance(row, int) and not isinstance(row, bool):
        return node_id, row
    return None


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"json_object_required:{path.name}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
