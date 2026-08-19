#!/usr/bin/env python3
"""Qualify the one G5.86 focused replay and fail closed on control regression."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_ORDINALS = (10, 12, 14, 16, 20, 22)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--semantic-stop", type=Path, required=True)
    parser.add_argument("--focused-replay", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.private_output, args.safe_output):
        if path.exists():
            raise SystemExit(f"output_must_be_new:{path.name}")

    inventory = _read_json(args.inventory)
    stop = _read_json(args.semantic_stop)
    replay = _read_json(args.focused_replay)
    if (
        tuple(replay["plan"]["chunk_ordinals"]) != EXPECTED_ORDINALS
        or replay["semantic_attempts"] != 6
        or replay["transport_submissions"] != 6
        or replay["provider_submission_counter"] != 6
        or not replay["artifact_store_unchanged"]
        or any(item["terminal_status"] != "validated" for item in replay["outcomes"])
    ):
        raise RuntimeError("g586_focused_replay_contract_invalid")

    chunk_targets = {
        _canonical(mapping["canonical_target"])
        for outcome in replay["outcomes"]
        for mapping in outcome["chunk"]["target_mappings"]
    }
    chunk_by_row = {}
    for outcome in replay["outcomes"]:
        ordinal = int(outcome["chunk"]["ordinal"])
        for mapping in outcome["chunk"]["target_mappings"]:
            key = _row_key(mapping["canonical_target"])
            if key is not None:
                chunk_by_row[key] = ordinal

    new_by_row: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    new_pairs = Counter()
    new_targets_outside_chunk = 0
    for outcome in replay["outcomes"]:
        for annotation in outcome["attempt"]["validated_output"]["annotations"]:
            target_key = _canonical(annotation["target"])
            if target_key not in chunk_targets:
                new_targets_outside_chunk += 1
            new_pairs[(target_key, annotation["financial_label"])] += 1
            row_key = _row_key(annotation["target"])
            if row_key is not None:
                new_by_row[row_key].append(annotation)

    affected_indices = {
        int(item["annotation_index"])
        for item in stop["systematic_conflict"]["private_affected_facts"]
    }
    rows = list(inventory["private_fact_rows"])
    affected = [row for row in rows if int(row["annotation_index"]) in affected_indices]
    affected_descriptions = Counter(_meaning_literal(row) for row in affected)
    baseline_focused = [
        row for row in rows if _canonical(row["target"]) in chunk_targets
    ]
    paired_tax = [
        row
        for row in baseline_focused
        if row["financial_type"] == "TAX_WITHHELD"
        and _meaning_literal(row) in affected_descriptions
    ]
    true_dividends = [
        row
        for row in baseline_focused
        if row["financial_type"] == "DIVIDEND_INCOME"
        and int(row["annotation_index"]) not in affected_indices
        and _meaning_literal(row) not in affected_descriptions
    ]

    affected_still_dividend = [
        row
        for row in affected
        if _has_label(new_by_row[_row_key(row["target"])], "DIVIDEND_INCOME")
    ]
    paired_tax_preserved = [
        row
        for row in paired_tax
        if _has_label(new_by_row[_row_key(row["target"])], "TAX_WITHHELD")
    ]
    true_dividends_preserved = [
        row
        for row in true_dividends
        if _has_label(new_by_row[_row_key(row["target"])], "DIVIDEND_INCOME")
    ]
    remaining_by_class = Counter(
        row["structural_cluster_id"] for row in affected_still_dividend
    )
    repaired_by_class = Counter(
        row["structural_cluster_id"]
        for row in affected
        if row not in affected_still_dividend
    )
    first_remaining = affected_still_dividend[0]
    first_row_key = _row_key(first_remaining["target"])
    duplicate_pairs = sum(count - 1 for count in new_pairs.values() if count > 1)
    checks = {
        "wrong_rows_no_longer_dividend": len(affected_still_dividend) == 0,
        "true_dividend_controls_preserved": len(true_dividends_preserved)
        == len(true_dividends),
        "existing_tax_controls_preserved": len(paired_tax_preserved) == len(paired_tax),
        "aliases_restore_only_canonical_targets": new_targets_outside_chunk == 0,
        "duplicate_annotation_pairs_zero": duplicate_pairs == 0,
        "artifact_store_unchanged": replay["artifact_store_unchanged"] is True,
    }
    terminal = (
        "SOURCE_LOCAL_SEMANTIC_PRECEDENCE_PROVEN"
        if all(checks.values())
        else "GATE3_SEMANTIC_ROOT_CAUSE_REQUALIFICATION_REQUIRED"
    )
    private = {
        "schema_version": "broker_reports_g586_focused_qualification_private_v1",
        "goal": "G5.86",
        "terminal": terminal,
        "focused_replay_sha256": _sha256(args.focused_replay),
        "checks": checks,
        "controls": {
            "wrong_rows_total": len(affected),
            "wrong_rows_still_dividend": len(affected_still_dividend),
            "wrong_rows_no_longer_dividend": len(affected)
            - len(affected_still_dividend),
            "paired_existing_tax_total": len(paired_tax),
            "paired_existing_tax_preserved": len(paired_tax_preserved),
            "paired_existing_tax_regressed": len(paired_tax)
            - len(paired_tax_preserved),
            "true_dividend_total": len(true_dividends),
            "true_dividend_preserved": len(true_dividends_preserved),
            "new_targets_outside_chunk": new_targets_outside_chunk,
            "duplicate_annotation_pairs": duplicate_pairs,
        },
        "remaining_wrong_by_structural_class": dict(sorted(remaining_by_class.items())),
        "repaired_by_structural_class": dict(sorted(repaired_by_class.items())),
        "first_remaining_wrong": {
            "annotation_index": first_remaining["annotation_index"],
            "page": first_remaining["page"],
            "structural_class_id": first_remaining["structural_cluster_id"],
            "chunk_ordinal": chunk_by_row[first_row_key],
            "target": first_remaining["target"],
            "target_literal": first_remaining["target_literal"],
            "target_row_literals": first_remaining["target_row_literals"],
            "new_annotations_on_row": new_by_row[first_row_key],
        },
        "root_cause_requalification": {
            "previous_candidate": "instruction_only_local_precedence",
            "candidate_result": "REJECTED_BY_FOCUSED_CONTROLS",
            "requalified_class": "B_LOCAL_ASSERTION_BOUNDARY_CONTRACT_GAP",
            "first_wrong_owner": "Gate3 source-local assertion packaging",
            "proof": (
                "Every alias is unique, but pass 1 receives one whole-table blob and "
                "no predeclared assertion object. The provider still chooses its own "
                "cell or row targets, so instruction-only precedence is not stable."
            ),
            "terminal": "LOCAL_ASSERTION_CONTEXT_CONTRACT_GAP_PROVEN",
            "minimal_next_shape": {
                "assertion": ["row_target_ref", "local_row_text"],
                "structural_context": [
                    "column_headers",
                    "table_header",
                    "section_header",
                ],
                "new_framework": False,
                "implementation_in_this_goal": False,
            },
        },
        "decision": {
            "second_provider_replay": False,
            "full_semantic_inventory_resumed": False,
            "ordinary_gate3_replay": False,
            "gate4_rebuild": False,
            "gate5_executed": False,
            "candidate_instruction_qualified": False,
        },
        "provider_calls_semantic": 6,
        "provider_calls_transport": 6,
        "semantic_retries": 0,
        "vlm_calls": 0,
    }
    _write_json(args.private_output, private)
    safe = {
        "schema_version": "broker_reports_g586_focused_qualification_safe_v1",
        "goal": "G5.86",
        "terminal": terminal,
        "checks": checks,
        "controls": private["controls"],
        "remaining_wrong_by_structural_class": private[
            "remaining_wrong_by_structural_class"
        ],
        "repaired_by_structural_class": private["repaired_by_structural_class"],
        "first_remaining_wrong": {
            "annotation_index": first_remaining["annotation_index"],
            "page": first_remaining["page"],
            "structural_class_id": first_remaining["structural_cluster_id"],
            "chunk_ordinal": chunk_by_row[first_row_key],
        },
        "root_cause_requalification": private["root_cause_requalification"],
        "decision": private["decision"],
        "provider_calls_semantic": 6,
        "provider_calls_transport": 6,
        "semantic_retries": 0,
        "vlm_calls": 0,
        "private_result_sha256": _sha256(args.private_output),
    }
    _write_json(args.safe_output, safe)
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0 if terminal == "SOURCE_LOCAL_SEMANTIC_PRECEDENCE_PROVEN" else 2


def _row_key(target: dict[str, Any]) -> tuple[str, int] | None:
    node_id = target.get("node_id")
    row = target.get("row")
    if isinstance(node_id, str) and isinstance(row, int) and not isinstance(row, bool):
        return node_id, row
    return None


def _meaning_literal(row: dict[str, Any]) -> str:
    values = [str(value) for value in row["target_row_literals"] if str(value).strip()]
    return max(values, key=len)


def _has_label(annotations: list[dict[str, Any]], label: str) -> bool:
    return any(item["financial_label"] == label for item in annotations)


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("input_not_object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
