"""Requalify the frozen G5.88 development result against source truth.

This is deliberately offline. It preserves the original frozen-oracle score,
checks the discovered oracle conflicts from immutable source rows and the
published dictionary, and emits a separate private receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


_ALIAS_PREFIX = re.compile(r"^\[t\d+\]\s*")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--dictionary", required=True)
    args = parser.parse_args()

    evidence_dir = Path(args.evidence_dir).resolve()
    dictionary_path = Path(args.dictionary).resolve()
    output_path = evidence_dir / "development-source-truth-qualification.private.json"
    if output_path.exists():
        raise SystemExit("qualification_output_already_exists")

    plan = _read_json(evidence_dir / "frozen-plan.private.json")
    controls = _read_json(evidence_dir / "controls.private.json")
    chunks = _read_json(evidence_dir / "chunks.private.json")
    development = _read_json(evidence_dir / "development.private.json")
    dictionary = _read_json(dictionary_path)

    if plan.get("goal") != "G5.88" or development.get("goal") != "G5.88":
        raise SystemExit("g588_evidence_required")
    if not isinstance(development.get("terminal"), str) or not development["terminal"]:
        raise SystemExit("terminal_development_required")
    if development.get("semantic_retries") != 0:
        raise SystemExit("semantic_retry_forbidden")
    if development.get("semantic_responses_received") != len(
        plan["development_ordinals"]
    ):
        raise SystemExit("complete_development_responses_required")

    actual = _actual_by_row_alias(development=development, chunks=chunks)
    source_rows = _source_rows(chunks)

    tax_label = next(
        item for item in dictionary["labels"] if item.get("label_id") == "TAX_WITHHELD"
    )
    refund_excluded = any(
        "refund" in item.casefold() for item in tax_label["do_not_apply_when"]
    )
    if not refund_excluded:
        raise SystemExit("published_tax_dictionary_refund_exclusion_required")

    affected_checks = []
    for control in controls["affected_tax_exact"]:
        row_id = control["row_id"]
        cells = source_rows[row_id]
        if len(cells) != 7:
            raise SystemExit(f"unexpected_cash_row_shape:{row_id}")
        debit = _cell_text(cells[4])
        credit = _cell_text(cells[5])
        description = _cell_text(cells[3])
        source_credit_only = not debit and bool(credit)
        tax_explicit = "налог" in description.casefold() or "tax" in description.casefold()
        labels = actual[row_id]["labels"]
        status = actual[row_id]["status"]
        affected_checks.append(
            {
                "ordinal": control["ordinal"],
                "row_id": row_id,
                "source_credit_only": source_credit_only,
                "source_tax_explicit": tax_explicit,
                "corrected_expected_status": "UNMAPPED",
                "actual_status": status,
                "actual_labels": labels,
                "passed": source_credit_only
                and tax_explicit
                and status == "UNMAPPED"
                and labels == [],
            }
        )

    dividend_keys = {
        (item["ordinal"], item["row_id"])
        for item in controls["true_dividend_exact"]
    }
    baseline_false_positives = [
        item
        for item in controls["existing_tax_exact"]
        if (item["ordinal"], item["row_id"]) in dividend_keys
    ]
    corrected_existing_tax = [
        item
        for item in controls["existing_tax_exact"]
        if (item["ordinal"], item["row_id"]) not in dividend_keys
    ]

    score_groups = {
        "affected_tax_credit_reversals": _score_affected(affected_checks),
        "true_dividend": _score_exact(controls["true_dividend_exact"], actual),
        "existing_tax_withholding": _score_exact(corrected_existing_tax, actual),
        "structural_none": _score_status(controls["structural_none"], actual, "NONE"),
        "cross_type": _score_exact(controls["cross_type"], actual),
    }
    real_failures = score_groups["existing_tax_withholding"]["failures"]
    payload = {
        "schema_version": "broker_reports_g588_source_truth_qualification_v1",
        "goal": "G5.88",
        "mode": "offline_deterministic_requalification",
        "provider_calls": 0,
        "semantic_retries": 0,
        "semantic_instruction_changed": False,
        "frozen_automatic_qualification": development["qualification"],
        "source_truth_basis": {
            "controls_sha256": _sha256(evidence_dir / "controls.private.json"),
            "development_sha256": _sha256(evidence_dir / "development.private.json"),
            "dictionary_sha256": _sha256(dictionary_path),
            "dictionary_identity": {
                "dictionary_id": dictionary["dictionary_id"],
                "semantic_version": dictionary["semantic_version"],
            },
            "tax_refund_explicitly_excluded": refund_excluded,
        },
        "frozen_oracle_corrections": {
            "affected_tax_expected_label_replaced_by_unmapped": len(affected_checks),
            "reason": "all source rows are tax-explicit credit-only reversals/refunds",
            "baseline_false_positive_controls": [
                {
                    **item,
                    "classification": "FROZEN_ORACLE_BASELINE_FALSE_POSITIVE",
                }
                for item in baseline_false_positives
            ],
        },
        "scores": score_groups,
        "remaining_semantic_failures": real_failures,
        "development_semantics_proven": not real_failures
        and all(group["passed"] for group in score_groups.values()),
    }
    _atomic_write(output_path, _json_bytes(payload))
    print(
        json.dumps(
            {
                "status": "REQUALIFIED",
                "output": str(output_path),
                "affected_credit_reversals": score_groups[
                    "affected_tax_credit_reversals"
                ],
                "existing_tax_withholding": score_groups[
                    "existing_tax_withholding"
                ],
                "baseline_false_positive_controls": len(baseline_false_positives),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _actual_by_row_alias(
    *, development: dict[str, Any], chunks: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for outcome in development["outcomes"]:
        if outcome.get("status") != "validated":
            raise SystemExit("all_development_outcomes_must_be_validated")
        ordinal = str(outcome["ordinal"])
        chunk = chunks[ordinal]
        target_to_alias = {
            _canonical_json(item["canonical_target"]): item["target_alias"]
            for item in chunk["target_mappings"]
            if item["canonical_target"].get("kind") == "table_row"
        }
        labels_by_alias: dict[str, list[str]] = {alias: [] for alias in target_to_alias.values()}
        for annotation in outcome["validated"]["mapped_financial_annotations_v2"][
            "annotations"
        ]:
            alias = target_to_alias[_canonical_json(annotation["target"])]
            labels_by_alias[alias].append(annotation["financial_label"])
        for alias, status in outcome["validated"]["row_statuses"].items():
            result[alias] = {
                "status": status,
                "labels": sorted(labels_by_alias.get(alias, [])),
            }
    return result


def _source_rows(chunks: dict[str, Any]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for chunk in chunks.values():
        for line in chunk["model_view"]["content"].splitlines():
            if not line.startswith("| [t"):
                continue
            cells = [item.strip() for item in line.strip().strip("|").split("|")]
            match = re.match(r"\[(t\d+)\]", cells[0])
            if match is not None:
                result[match.group(1)] = cells
    return result


def _score_affected(checks: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [item for item in checks if not item["passed"]]
    return {
        "passed": not failures,
        "correct": len(checks) - len(failures),
        "total": len(checks),
        "failures": failures,
    }


def _score_exact(
    controls: list[dict[str, Any]], actual: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    failures = []
    for control in controls:
        row = actual[control["row_id"]]
        expected = sorted(control["expected_labels"])
        if row["labels"] != expected:
            failures.append(
                {
                    "ordinal": control["ordinal"],
                    "row_id": control["row_id"],
                    "expected_labels": expected,
                    "actual_labels": row["labels"],
                    "actual_status": row["status"],
                }
            )
    return {
        "passed": not failures,
        "correct": len(controls) - len(failures),
        "total": len(controls),
        "failures": failures,
    }


def _score_status(
    controls: list[dict[str, Any]],
    actual: dict[str, dict[str, Any]],
    expected_status: str,
) -> dict[str, Any]:
    failures = [
        {
            "ordinal": item["ordinal"],
            "row_id": item["row_id"],
            "expected_status": expected_status,
            "actual_status": actual[item["row_id"]]["status"],
            "actual_labels": actual[item["row_id"]]["labels"],
        }
        for item in controls
        if actual[item["row_id"]]["status"] != expected_status
        or actual[item["row_id"]]["labels"]
    ]
    return {
        "passed": not failures,
        "correct": len(controls) - len(failures),
        "total": len(controls),
        "failures": failures,
    }


def _cell_text(value: str) -> str:
    return _ALIAS_PREFIX.sub("", value).strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit(f"json_object_required:{path.name}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
