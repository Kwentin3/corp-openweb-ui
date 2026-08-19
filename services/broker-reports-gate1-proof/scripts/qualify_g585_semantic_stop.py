#!/usr/bin/env python3
"""Localize the first G5.85 semantic divergence and emit the STOP evidence."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


EXPLICIT_TAX_MARKER = " - US Налог"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--ordinary-batch", type=Path, required=True)
    parser.add_argument("--frozen-batch", type=Path, required=True)
    parser.add_argument("--original-pdf", type=Path, required=True)
    parser.add_argument("--visual-receipt", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.private_output, args.safe_output):
        if path.exists():
            raise SystemExit(f"output_must_be_new:{path.name}")

    inventory = _read_json(args.inventory)
    batch = _read_json(args.ordinary_batch)
    frozen_batch = _read_json(args.frozen_batch)
    visual = _read_json(args.visual_receipt)
    conflicts = [
        row
        for row in inventory["private_fact_rows"]
        if row["financial_type"] == "DIVIDEND_INCOME"
        and EXPLICIT_TAX_MARKER in " ".join(row["target_row_literals"])
    ]
    if not conflicts:
        raise RuntimeError("systematic_semantic_conflict_not_found")
    conflict_bindings = [
        _provider_binding(
            batches=(
                ("ordinary_g583", batch),
                ("frozen_g580", frozen_batch),
            ),
            target=row["target"],
            financial_label=row["financial_type"],
        )
        for row in conflicts
    ]
    first = conflicts[0]
    first_binding = conflict_bindings[0]
    original_pdf_sha256 = _sha256(args.original_pdf)
    if (
        visual.get("original_pdf_sha256") != original_pdf_sha256
        or visual.get("vlm_calls") != 0
        or visual.get("verdict") != "SYSTEMATIC_SOURCE_LABEL_CONFLICT_CONFIRMED"
        or int(first["page"]) not in visual.get("pages_inspected", [])
    ):
        raise RuntimeError("development_visual_receipt_invalid")
    affected_pages = Counter(str(item["page"]) for item in conflicts)
    affected_clusters = Counter(item["structural_cluster_id"] for item in conflicts)
    affected_chunks = Counter(str(item["chunk_ordinal"]) for item in conflict_bindings)
    first_exact = (
        first["annotation_index"] == 22
        and first["page"] == 4
        and first["financial_type"] == "DIVIDEND_INCOME"
        and EXPLICIT_TAX_MARKER in " ".join(first["target_row_literals"])
        and first_binding["chunk_ordinal"] == 10
        and first_binding["fact_alias"] == "f005"
        and first_binding["target_alias"] == "t1241"
        and first_binding["pass1_label"] == "DIVIDEND_INCOME"
        and first_binding["role_label"] == "DIVIDEND_INCOME"
    )
    private = {
        "schema_version": "broker_reports_g585_semantic_stop_private_v1",
        "goal": "G5.85",
        "terminal": "SYSTEMATIC_SEMANTIC_ERROR_LOCALIZED",
        "inventory_sha256": _sha256(args.inventory),
        "ordinary_batch_sha256": _sha256(args.ordinary_batch),
        "frozen_batch_sha256": _sha256(args.frozen_batch),
        "original_pdf_sha256": original_pdf_sha256,
        "machine_inventory": {
            "facts_total": inventory["facts_total"],
            "facts_accounted": inventory["facts_accounted"],
            "structural_clusters_total": len(inventory["structural_clusters"]),
            "anomaly_clusters_total": len(inventory["anomaly_clusters"]),
            "negative_control_families_total": len(
                inventory["negative_control_families"]
            ),
        },
        "systematic_conflict": {
            "conflict_kind": (
                "DIVIDEND_INCOME_on_source_rows_explicitly_described_as_US_tax"
            ),
            "affected_facts": len(conflicts),
            "affected_pages": dict(
                sorted(affected_pages.items(), key=lambda item: int(item[0]))
            ),
            "affected_structural_clusters": dict(sorted(affected_clusters.items())),
            "affected_provider_chunks": dict(
                sorted(affected_chunks.items(), key=lambda item: int(item[0]))
            ),
            "all_amounts_bound": all(
                any(
                    role["role"] == "amount" and role["status"] == "bound"
                    for role in row["roles"]
                )
                for row in conflicts
            ),
            "all_source_rows_have_explicit_tax_marker": all(
                EXPLICIT_TAX_MARKER in " ".join(row["target_row_literals"])
                for row in conflicts
            ),
            "private_affected_facts": [
                {
                    "annotation_index": row["annotation_index"],
                    "fact_id": row["fact_id"],
                    "page": row["page"],
                    "target": row["target"],
                    "target_literal": row["target_literal"],
                    "target_row_literals": row["target_row_literals"],
                    "provider_binding": binding,
                }
                for row, binding in zip(conflicts, conflict_bindings)
            ],
        },
        "first_divergence": {
            "annotation_index": first["annotation_index"],
            "page": first["page"],
            "structural_cluster_id": first["structural_cluster_id"],
            "canonical_target": first["target"],
            "canonical_row_literals": first["target_row_literals"],
            "provider_binding": first_binding,
            "first_divergence_owner": "Gate3 pass-1 provider semantic proposal",
            "upstream_source_and_canonical_match_original_pdf": True,
            "downstream_role_persistence_and_gate4_preserve_proposed_label": True,
            "exact_localization_passed": first_exact,
        },
        "development_visual_audit": visual,
        "decision": {
            "section_a_operational_retry_policy": "QUALIFIED_SEPARATELY",
            "section_b_semantic_qualification": "FAILED_SYSTEMATIC_ERROR",
            "ordinary_replay_executed": False,
            "gate4_rebuild_after_ordinary_replay": False,
            "gate5_executed": False,
            "fix_applied": False,
        },
        "provider_calls": 0,
        "vlm_calls": 0,
    }
    _write_json(args.private_output, private)
    safe = {
        "schema_version": "broker_reports_g585_semantic_stop_safe_v1",
        "goal": "G5.85",
        "terminal": private["terminal"],
        "machine_inventory": private["machine_inventory"],
        "systematic_conflict": {
            "conflict_kind": private["systematic_conflict"]["conflict_kind"],
            "affected_facts": len(conflicts),
            "affected_pages": private["systematic_conflict"]["affected_pages"],
            "affected_structural_clusters_total": len(affected_clusters),
            "affected_provider_chunks": private["systematic_conflict"][
                "affected_provider_chunks"
            ],
            "all_amounts_bound": private["systematic_conflict"][
                "all_amounts_bound"
            ],
            "all_source_rows_have_explicit_tax_marker": private[
                "systematic_conflict"
            ]["all_source_rows_have_explicit_tax_marker"],
        },
        "first_divergence": {
            "annotation_index": first["annotation_index"],
            "page": first["page"],
            "structural_cluster_id": first["structural_cluster_id"],
            "provider_chunk_ordinal": first_binding["chunk_ordinal"],
            "provider_fact_alias": first_binding["fact_alias"],
            "provider_target_alias": first_binding["target_alias"],
            "first_divergence_owner": private["first_divergence"][
                "first_divergence_owner"
            ],
            "exact_localization_passed": first_exact,
        },
        "development_visual_audit": {
            "pages_inspected": visual["pages_inspected"],
            "verdict": visual["verdict"],
            "vlm_calls": visual["vlm_calls"],
            "render_sha256": visual["render_sha256"],
        },
        "decision": private["decision"],
        "original_pdf_sha256": original_pdf_sha256,
        "inventory_sha256": private["inventory_sha256"],
        "ordinary_batch_sha256": private["ordinary_batch_sha256"],
        "frozen_batch_sha256": private["frozen_batch_sha256"],
        "private_result_sha256": _sha256(args.private_output),
        "provider_calls": 0,
        "vlm_calls": 0,
    }
    _write_json(args.safe_output, safe)
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 2


def _provider_binding(
    *,
    batches: tuple[tuple[str, dict[str, Any]], ...],
    target: dict[str, Any],
    financial_label: str,
) -> dict[str, Any]:
    for replay_source, batch in batches:
        matches = []
        for outcome in batch["outcomes"]:
            role_attempt = outcome.get("role_attempt") or {}
            facts = role_attempt.get("facts") or []
            for fact in facts:
                if (
                    fact.get("target") != target
                    or fact.get("financial_label") != financial_label
                ):
                    continue
                mapping = next(
                    item
                    for item in outcome["chunk"]["target_mappings"]
                    if item["canonical_target"] == target
                )
                pass1 = _decoded(outcome["pass1_attempt"]["raw_model_output"])
                pass1_annotation = next(
                    item
                    for item in pass1["annotations"]
                    if item["target_alias"] == mapping["target_alias"]
                    and item["financial_label"] == fact["financial_label"]
                )
                role_raw = _decoded(role_attempt["raw_model_output"])
                role_fact = next(
                    item
                    for item in role_raw["facts"]
                    if item["fact_alias"] == fact["fact_alias"]
                )
                matches.append(
                    {
                        "replay_source": replay_source,
                        "chunk_ordinal": outcome["chunk"]["ordinal"],
                        "chunk_id": outcome["chunk"]["chunk_id"],
                        "fact_alias": fact["fact_alias"],
                        "target_alias": mapping["target_alias"],
                        "pass1_label": pass1_annotation["financial_label"],
                        "role_label": role_fact["financial_label"],
                        "model_visible_request_sha256": _json_sha256(
                            outcome["pass1_attempt"]["model_visible_request"]
                        ),
                        "pass1_raw_output_sha256": _json_sha256(pass1),
                        "role_raw_output_sha256": _json_sha256(role_raw),
                    }
                )
        if len(matches) > 1:
            raise RuntimeError("provider_fact_binding_not_unique")
        if matches:
            return matches[0]
    raise RuntimeError("provider_fact_binding_missing")


def _decoded(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        raise RuntimeError("provider_output_not_object")
    return decoded


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
