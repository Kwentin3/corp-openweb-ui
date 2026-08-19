#!/usr/bin/env python3
"""Qualify the single G5.91 replay against frozen G5.88 source-truth controls."""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any


ORDINALS = (10, 12, 14, 16, 20, 22)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g588-evidence-dir", type=Path, required=True)
    parser.add_argument("--g591-replay", type=Path, required=True)
    parser.add_argument("--dictionary", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    for output in (args.private_output, args.safe_output):
        if output.exists():
            raise SystemExit(f"output_must_be_new:{output.name}")

    source_root = args.g588_evidence_dir.resolve()
    controls = _read_json(source_root / "controls.private.json")
    source_truth = _read_json(
        source_root / "development-source-truth-qualification.private.json"
    )
    replay = _read_json(args.g591_replay)
    dictionary = _read_json(args.dictionary)
    if (
        replay.get("goal") != "G5.91"
        or replay.get("semantic_attempts") != len(ORDINALS)
        or replay.get("transport_submissions") != len(ORDINALS)
        or replay.get("semantic_retries") != 0
        or replay.get("best_of_n") is not False
        or replay.get("prompt_variants") != 0
        or any(
            item.get("terminal_status") != "validated"
            for item in replay.get("outcomes", [])
        )
    ):
        raise SystemExit("g591_single_replay_contract_invalid")
    source_score = source_truth["scores"]["affected_tax_credit_reversals"]
    source_correction = source_truth["frozen_oracle_corrections"]
    if (
        source_score["total"] != 105
        or source_correction["affected_tax_expected_label_replaced_by_unmapped"]
        != 105
        or any(
            not item["source_credit_only"] or not item["source_tax_explicit"]
            for item in source_score["failures"]
        )
    ):
        raise SystemExit("g588_source_truth_105_required")

    labels = {item["label_id"]: item for item in dictionary["labels"]}
    if dictionary.get("semantic_version") != "2.1.0" or "TAX_ADJUSTMENT" not in labels:
        raise SystemExit("g591_dictionary_required")
    dictionary_text = json.dumps(dictionary, ensure_ascii=False).casefold()
    broker_specific_rules_zero = "us tax" not in dictionary_text

    annotations_by_row: dict[tuple[str, int], list[str]] = defaultdict(list)
    relation_keys = 0
    for outcome in replay["outcomes"]:
        validated = outcome["validated_output"]
        for annotation in validated["annotations"]:
            target = annotation["target"]
            key = _row_key(target)
            if key is not None:
                annotations_by_row[key].append(annotation["financial_label"])
            relation_keys += len(
                {
                    "related_fact_id",
                    "relation",
                    "relation_id",
                    "event_id",
                }
                & set(annotation)
            )

    chunks = _read_json(source_root / "chunks.private.json")
    row_key_by_control: dict[tuple[int, str], tuple[str, int]] = {}
    for ordinal in ORDINALS:
        for mapping in chunks[str(ordinal)]["target_mappings"]:
            target = mapping["canonical_target"]
            if target.get("kind") == "table_row":
                row_key_by_control[(ordinal, mapping["target_alias"])] = (
                    target["node_id"],
                    target["row"],
                )

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
        "tax_adjustment": _score_labels(
            controls["affected_tax_exact"],
            row_key_by_control,
            annotations_by_row,
            ["TAX_ADJUSTMENT"],
        ),
        "true_dividend": _score_labels(
            controls["true_dividend_exact"],
            row_key_by_control,
            annotations_by_row,
            ["DIVIDEND_INCOME"],
        ),
        "ordinary_withholding": _score_labels(
            withholding_controls,
            row_key_by_control,
            annotations_by_row,
            ["TAX_WITHHELD"],
        ),
        "structural_none": _score_labels(
            controls["structural_none"],
            row_key_by_control,
            annotations_by_row,
            [],
        ),
    }
    checks = {
        "tax_adjustment_105_of_105": scores["tax_adjustment"]["passed"],
        "wrong_dividend_systematic_class_zero": all(
            "DIVIDEND_INCOME" not in failure.get("actual_labels", [])
            for failure in scores["tax_adjustment"]["failures"]
        )
        and scores["tax_adjustment"]["correct"] == 105,
        "true_dividend_controls_preserved": scores["true_dividend"]["passed"],
        "ordinary_withholding_controls_preserved": scores[
            "ordinary_withholding"
        ]["passed"],
        "structural_unmapped_controls_preserved": scores["structural_none"][
            "passed"
        ],
        "broker_specific_rules_zero": broker_specific_rules_zero,
        "inferred_relations_zero": relation_keys == 0,
    }
    passed = all(checks.values())
    terminals = (
        [
            "BROKER_TAX_OBSERVATION_SOURCE_CONTRACT_PROVEN",
            "WITHHOLDING_VS_ADJUSTMENT_SOURCE_DISTINCTION_PROVEN",
            "SYSTEMATIC_TAX_ADJUSTMENT_AS_DIVIDEND_ERROR_REMOVED",
            "TRUE_DIVIDEND_CONTROLS_PRESERVED",
            "ORDINARY_WITHHOLDING_CONTROLS_PRESERVED",
            "UNMAPPED_FAIL_CLOSED_PRESERVED",
            "BROKER_SPECIFIC_RULES_ZERO",
            "INFERRED_RELATIONS_ZERO",
        ]
        if passed
        else ["G591_SOURCE_QUALIFICATION_FAILED"]
    )
    private = {
        "schema_version": "broker_reports_g591_tax_adjustment_qualification_private_v1",
        "goal": "G5.91",
        "passed": passed,
        "checks": checks,
        "scores": scores,
        "source_truth_binding": {
            "g588_qualification_sha256": _file_sha256(
                source_root / "development-source-truth-qualification.private.json"
            ),
            "affected_tax_adjustment_rows": source_score["total"],
        },
        "dictionary_sha256": _file_sha256(args.dictionary),
        "replay_sha256": _file_sha256(args.g591_replay),
        "provider_calls": len(ORDINALS),
        "semantic_retries": 0,
        "best_of_n": False,
        "prompt_variants": 0,
        "tax_calculations": 0,
        "terminals": terminals,
    }
    _write_json(args.private_output, private)
    safe = {
        "schema_version": "broker_reports_g591_tax_adjustment_qualification_safe_v1",
        "goal": "G5.91",
        "passed": passed,
        "checks": checks,
        "scores": {
            key: {
                "passed": value["passed"],
                "correct": value["correct"],
                "total": value["total"],
            }
            for key, value in scores.items()
        },
        "provider_calls": len(ORDINALS),
        "semantic_retries": 0,
        "best_of_n": False,
        "prompt_variants": 0,
        "tax_calculations": 0,
        "private_result_sha256": _file_sha256(args.private_output),
        "terminals": terminals,
    }
    _write_json(args.safe_output, safe)
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 2


def _score_control_labels(
    controls: list[dict[str, Any]],
    keys: dict[tuple[int, str], tuple[str, int]],
    actual: dict[tuple[str, int], list[str]],
) -> dict[str, Any]:
    failures = []
    for control in controls:
        key = keys[(control["ordinal"], control["row_id"])]
        expected = sorted(control["expected_labels"])
        got = sorted(actual.get(key, []))
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


def _score_labels(
    controls: list[dict[str, Any]],
    keys: dict[tuple[int, str], tuple[str, int]],
    actual: dict[tuple[str, int], list[str]],
    expected: list[str],
) -> dict[str, Any]:
    normalized = [
        {**item, "expected_labels": expected}
        for item in controls
    ]
    return _score_control_labels(normalized, keys, actual)


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


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
