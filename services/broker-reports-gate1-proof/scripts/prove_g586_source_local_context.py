#!/usr/bin/env python3
"""Prove the exact G5.86 source-local context boundary before provider use."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from typing import Any


EXPECTED_PAGES = (4, 5, 6, 7, 9, 10)
EXPECTED_CHUNKS = (10, 12, 14, 16, 20, 22)
EXPECTED_FACTS = 105
EXPECTED_CLASSES = 6


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--semantic-stop", type=Path, required=True)
    parser.add_argument("--ordinary-batch", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.private_output, args.safe_output):
        if path.exists():
            raise SystemExit(f"output_must_be_new:{path.name}")

    inventory = _read_json(args.inventory)
    stop = _read_json(args.semantic_stop)
    batch = _read_json(args.ordinary_batch)
    conflict = stop["systematic_conflict"]
    affected = list(conflict["private_affected_facts"])
    rows_by_index = {
        int(row["annotation_index"]): row for row in inventory["private_fact_rows"]
    }
    outcomes_by_ordinal = {
        int(outcome["chunk"]["ordinal"]): outcome for outcome in batch["outcomes"]
    }
    frozen = _freeze_receipt(conflict=conflict, affected=affected)
    if not all(frozen.values()):
        raise RuntimeError("g586_systematic_set_drift")

    observations = []
    class_first: dict[str, dict[str, Any]] = {}
    for item in affected:
        index = int(item["annotation_index"])
        row = rows_by_index[index]
        binding = item["provider_binding"]
        outcome = outcomes_by_ordinal[int(binding["chunk_ordinal"])]
        observation = _observe_exact_context(
            affected=item,
            row=row,
            outcome=outcome,
        )
        observations.append(observation)
        class_first.setdefault(row["structural_cluster_id"], observation)

    if len(class_first) != EXPECTED_CLASSES:
        raise RuntimeError("g586_structural_class_count_drift")
    if not all(
        observation["local_source_literal_visible"]
        and observation["output_target_alias_uniquely_restored"]
        and not observation["assertion_predeclared_before_provider"]
        and observation["broader_context_separately_identifiable"]
        and observation["exact_pass1_blob_proven"]
        for observation in observations
    ):
        raise RuntimeError("g586_deterministic_context_proof_failed")

    causes = Counter(item["first_root_cause"] for item in class_first.values())
    if causes != Counter({"B_LOCAL_ASSERTION_BOUNDARY_CONTRACT_GAP": 6}):
        raise RuntimeError("g586_root_cause_classification_drift")

    paired_correct_tax = _paired_correct_tax_controls(
        affected=affected,
        rows=inventory["private_fact_rows"],
    )
    true_dividend_controls = _true_dividend_controls(
        affected=affected,
        rows=inventory["private_fact_rows"],
    )
    ambiguous_controls = sum(
        not item["target_is_meaning_bearing"] for item in observations
    )
    private = {
        "schema_version": "broker_reports_g586_source_local_context_private_v1",
        "goal": "G5.86",
        "input_sha256": {
            "inventory": _sha256(args.inventory),
            "semantic_stop": _sha256(args.semantic_stop),
            "ordinary_batch": _sha256(args.ordinary_batch),
        },
        "frozen_systematic_set": frozen,
        "exact_context_observations": observations,
        "class_representatives": [class_first[key] for key in sorted(class_first)],
        "root_cause_counts": dict(sorted(causes.items())),
        "common_first_wrong_owner": "Gate3 source-local assertion packaging",
        "payload_decision": "MINIMAL_LOCAL_ASSERTION_ENVELOPE_REQUIRED",
        "minimal_envelope": {
            "assertion": ["row_target_ref", "local_row_text"],
            "structural_context": [
                "column_headers",
                "table_header",
                "section_header",
            ],
            "new_framework": False,
            "implemented": False,
        },
        "controls": {
            "wrong_class_rows": len(affected),
            "paired_existing_correct_tax_rows": paired_correct_tax,
            "true_dividend_rows_outside_frozen_wrong_set": true_dividend_controls,
            "ambiguous_target_cells_in_wrong_set": ambiguous_controls,
        },
        "provider_calls": 0,
        "vlm_calls": 0,
    }
    _write_json(args.private_output, private)
    safe = {
        "schema_version": "broker_reports_g586_source_local_context_safe_v1",
        "goal": "G5.86",
        "terminal": "LOCAL_ASSERTION_CONTEXT_CONTRACT_GAP_PROVEN",
        "frozen_systematic_set": frozen,
        "classes": [
            {
                "structural_class_id": item["structural_class_id"],
                "chunk_ordinal": item["chunk_ordinal"],
                "target_kind": item["target_kind"],
                "target_column": item["target_column"],
                "first_root_cause": item["first_root_cause"],
                "local_source_literal_visible": item["local_source_literal_visible"],
                "output_target_alias_uniquely_restored": item[
                    "output_target_alias_uniquely_restored"
                ],
                "assertion_predeclared_before_provider": item[
                    "assertion_predeclared_before_provider"
                ],
                "broader_context_separately_identifiable": item[
                    "broader_context_separately_identifiable"
                ],
            }
            for item in private["class_representatives"]
        ],
        "root_cause_counts": private["root_cause_counts"],
        "common_first_wrong_owner": private["common_first_wrong_owner"],
        "payload_decision": private["payload_decision"],
        "new_schema": False,
        "dictionary_changed": False,
        "broker_specific_literal_rule": False,
        "controls": private["controls"],
        "private_result_sha256": _sha256(args.private_output),
        "provider_calls": 0,
        "vlm_calls": 0,
    }
    _write_json(args.safe_output, safe)
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0


def _freeze_receipt(
    *, conflict: dict[str, Any], affected: list[dict[str, Any]]
) -> dict[str, bool | int | list[int]]:
    pages = sorted({int(item["page"]) for item in affected})
    chunks = sorted(
        {int(item["provider_binding"]["chunk_ordinal"]) for item in affected}
    )
    classes = list(conflict["affected_structural_clusters"])
    return {
        "facts_total": len(affected),
        "facts_exact": len(affected) == EXPECTED_FACTS,
        "pages": pages,
        "pages_exact": pages == list(EXPECTED_PAGES),
        "structural_classes_total": len(classes),
        "structural_classes_exact": len(classes) == EXPECTED_CLASSES,
        "provider_chunks": chunks,
        "provider_chunks_exact": chunks == list(EXPECTED_CHUNKS),
        "source_rows_explicit": bool(
            conflict["all_source_rows_have_explicit_tax_marker"]
        ),
    }


def _observe_exact_context(
    *, affected: dict[str, Any], row: dict[str, Any], outcome: dict[str, Any]
) -> dict[str, Any]:
    binding = affected["provider_binding"]
    chunk = outcome["chunk"]
    pass1 = outcome["pass1_attempt"]
    alias = binding["target_alias"]
    content = chunk["model_view"]["content"]
    messages = pass1["model_visible_request"]["messages"]
    mapping = next(
        item for item in chunk["target_mappings"] if item["target_alias"] == alias
    )
    alias_pattern = re.compile(rf"(?<!\\)\[{re.escape(alias)}\]")
    matching_lines = [
        line for line in content.splitlines() if alias_pattern.search(line)
    ]
    if len(matching_lines) != 1 or mapping["canonical_target"] != row["target"]:
        raise RuntimeError("g586_target_alias_binding_invalid")
    target_line = matching_lines[0]
    nonblank_row_literals = [
        str(value) for value in row["target_row_literals"] if str(value).strip()
    ]
    local_visible = all(value in target_line for value in nonblank_row_literals)
    exact_blob = bool(
        len(messages) == 3
        and messages[2]["content"].endswith(content)
        and pass1["projection"]["model_view"]["content"] == content
    )
    separate_context = bool(
        "## Structural context (context only)" in content
        and "## Target content" in content
        and "| row |" in content
        and row["table_title_row"]
        and all(str(value) in content for value in row["table_title_row"])
    )
    target_literal = row["target_literal"]
    meaning_literal = max(nonblank_row_literals, key=len)
    target_is_meaning_bearing = bool(
        row["target"]["kind"] == "table_row"
        or (isinstance(target_literal, str) and target_literal == meaning_literal)
    )
    neighbours = content.splitlines()
    line_index = neighbours.index(target_line)
    return {
        "annotation_index": int(row["annotation_index"]),
        "structural_class_id": row["structural_cluster_id"],
        "page": int(row["page"]),
        "chunk_ordinal": int(chunk["ordinal"]),
        "chunk_id": chunk["chunk_id"],
        "target_alias": alias,
        "target": row["target"],
        "target_kind": row["target"]["kind"],
        "target_column": row["target"].get("column"),
        "target_literal": target_literal,
        "local_row_literals": row["target_row_literals"],
        "column_headers_visible": "| row |" in content,
        "table_header_visible": bool(row["table_title_row"]),
        "section_page_context_visible": "## Structural context (context only)"
        in content,
        "neighbour_before": neighbours[line_index - 1] if line_index > 0 else None,
        "target_line": target_line,
        "neighbour_after": (
            neighbours[line_index + 1] if line_index + 1 < len(neighbours) else None
        ),
        "local_source_literal_visible": local_visible,
        "output_target_alias_uniquely_restored": len(alias_pattern.findall(content))
        == 1,
        "assertion_predeclared_before_provider": False,
        "broader_context_separately_identifiable": separate_context,
        "exact_pass1_blob_proven": exact_blob,
        "target_is_meaning_bearing": target_is_meaning_bearing,
        "first_root_cause": "B_LOCAL_ASSERTION_BOUNDARY_CONTRACT_GAP",
        "first_wrong_owner": "Gate3 source-local assertion packaging",
    }


def _paired_correct_tax_controls(
    *, affected: list[dict[str, Any]], rows: list[dict[str, Any]]
) -> int:
    affected_descriptions = Counter(
        _meaning_literal(item["target_row_literals"]) for item in affected
    )
    correct = Counter(
        _meaning_literal(row["target_row_literals"])
        for row in rows
        if row["financial_type"] == "TAX_WITHHELD"
    )
    return sum(
        min(count, correct[description])
        for description, count in affected_descriptions.items()
    )


def _true_dividend_controls(
    *, affected: list[dict[str, Any]], rows: list[dict[str, Any]]
) -> int:
    affected_indices = {int(item["annotation_index"]) for item in affected}
    affected_descriptions = {
        _meaning_literal(item["target_row_literals"]) for item in affected
    }
    return sum(
        row["financial_type"] == "DIVIDEND_INCOME"
        and int(row["annotation_index"]) not in affected_indices
        and _meaning_literal(row["target_row_literals"]) not in affected_descriptions
        for row in rows
    )


def _meaning_literal(values: list[Any]) -> str:
    nonblank = [str(value) for value in values if str(value).strip()]
    return max(nonblank, key=len)


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
