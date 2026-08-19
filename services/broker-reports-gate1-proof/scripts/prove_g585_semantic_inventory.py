#!/usr/bin/env python3
"""Inventory and structurally cluster the current G5.85 large-document facts."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalReaderFactory,
    Gate3FinancialAnnotationsPersistenceFactory,
)
from broker_reports_gate1.gate4_financial_case_cache import (  # noqa: E402
    CASE_COMPLETE_FOR_CURRENT_INPUT_SET,
    Gate4FinancialCaseRuntimeFactory,
)


LARGE_DOCUMENT_ID = "brdoc_001_7cfd297786cc"
LARGE_RUN_ID = "normrun_1f4f2d9e30c1a076"
BASE_CONTEXT = {
    "user_id": "g540e-private-user",
    "case_id": "g540e-real-source-contract",
    "chat_id": None,
    "workspace_model_id": "g540e-private-model",
}
REQUIRED_REVIEW_TYPES = frozenset(
    {
        "TAX_WITHHELD",
        "DIVIDEND_INCOME",
        "SECURITY_PURCHASE",
        "SECURITY_DISPOSAL",
        "TRANSACTION_CHARGE",
        "COMMISSION",
        "COMMISSION_TOTAL",
    }
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-root", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.private_output, args.safe_output):
        if path.exists():
            raise SystemExit(f"output_must_be_new:{path.name}")

    store = _store(args.store_root)
    context = _context()
    assembly = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().rebuild_case(context=context)
    if assembly.status != CASE_COMPLETE_FOR_CURRENT_INPUT_SET:
        raise RuntimeError("current_case_not_complete")
    source = next(
        item for item in assembly.sources if item.document_id == LARGE_DOCUMENT_ID
    )
    payload = Gate3FinancialAnnotationsPersistenceFactory(
        store=store,
        read_enabled=True,
    ).create().read(
        artifact_id=source.financial_annotations_artifact_id,
        context=context,
    )
    envelope = CanonicalReaderFactory(
        store=store,
        read_enabled=True,
    ).create().read_active_envelope(LARGE_DOCUMENT_ID, context)
    if envelope.canonical_version_id != source.canonical_version_id:
        raise RuntimeError("current_canonical_binding_drift")
    canonical = envelope.artifact
    facts = [
        fact
        for fact in assembly.facts
        if fact["gate3_binding"]["canonical_binding"]["document_id"]
        == LARGE_DOCUMENT_ID
    ]
    inventory = _inventory(
        canonical=canonical,
        facts=facts,
        annotations=payload["annotations"],
    )
    private = {
        "schema_version": "broker_reports_g585_semantic_inventory_private_v1",
        "goal": "G5.85",
        "document_id": LARGE_DOCUMENT_ID,
        "canonical_version_id": envelope.canonical_version_id,
        "financial_annotations_artifact_id": source.financial_annotations_artifact_id,
        **inventory,
        "provider_calls": 0,
        "ordinary_replay": 0,
        "vlm_calls": 0,
    }
    _write_json(args.private_output, private)
    safe = {
        "schema_version": "broker_reports_g585_semantic_inventory_safe_v1",
        "goal": "G5.85",
        "facts_total": inventory["facts_total"],
        "facts_accounted": inventory["facts_accounted"],
        "fact_type_counts": inventory["fact_type_counts"],
        "target_kind_counts": inventory["target_kind_counts"],
        "structural_clusters_total": len(inventory["structural_clusters"]),
        "structural_cluster_facts_accounted": sum(
            item["facts_total"] for item in inventory["structural_clusters"]
        ),
        "anomaly_clusters_total": len(inventory["anomaly_clusters"]),
        "anomaly_cluster_facts_total": sum(
            item["facts_total"] for item in inventory["anomaly_clusters"]
        ),
        "anomaly_reason_counts": inventory["anomaly_reason_counts"],
        "required_review_type_counts": inventory["required_review_type_counts"],
        "negative_control_families_total": len(
            inventory["negative_control_families"]
        ),
        "negative_control_rows_total": sum(
            item["rows_total"] for item in inventory["negative_control_families"]
        ),
        "required_roles_missing": inventory["required_roles_missing"],
        "role_targets_outside_accepted_row": inventory[
            "role_targets_outside_accepted_row"
        ],
        "same_type_duplicate_targets": inventory["same_type_duplicate_targets"],
        "multiple_types_same_target": inventory["multiple_types_same_target"],
        "facts_per_page": inventory["facts_per_page"],
        "review_manifest_items": len(inventory["review_manifest"]),
        "machine_coverage_percent": (
            100.0
            if inventory["facts_accounted"] == inventory["facts_total"] == 1489
            else 0.0
        ),
        "private_inventory_sha256": _sha256(args.private_output),
        "provider_calls": 0,
        "ordinary_replay": 0,
        "vlm_calls": 0,
    }
    _write_json(args.safe_output, safe)
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0 if safe["machine_coverage_percent"] == 100.0 else 2


def _inventory(
    *,
    canonical: dict[str, Any],
    facts: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
) -> dict[str, Any]:
    nodes = {node["node_id"]: node for node in canonical["nodes"]}
    provenance = {
        item["provenance_id"]: item for item in canonical["provenance"]
    }
    fact_by_annotation = {
        int(fact["gate3_binding"]["annotation_index"]): fact for fact in facts
    }
    if len(fact_by_annotation) != len(facts) or set(fact_by_annotation) != set(
        range(len(annotations))
    ):
        raise RuntimeError("gate3_gate4_fact_inventory_not_bijective")

    rows: list[dict[str, Any]] = []
    cluster_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    target_identities: Counter[str] = Counter()
    type_target_identities: Counter[str] = Counter()
    fact_rows_by_table: set[tuple[str, int]] = set()
    for annotation_index, annotation in enumerate(annotations):
        fact = fact_by_annotation[annotation_index]
        target = annotation["target"]
        node = nodes[target["node_id"]]
        page = _node_page(node, provenance)
        row_number = target.get("row")
        row_cells = _row_cells(node, row_number)
        row_identity = (
            (target["node_id"], int(row_number))
            if isinstance(row_number, int)
            else None
        )
        if row_identity is not None:
            fact_rows_by_table.add(row_identity)
        target_identity = _json_canonical(target)
        target_identities[target_identity] += 1
        type_target_identities[_json_canonical([annotation["financial_label"], target])] += 1
        role_geometry = _role_geometry(annotation, target)
        cluster_key = {
            "target_kind": target["kind"],
            "node_type": node["node_type"],
            "table_columns": _table_columns(node),
            "row_cell_columns": [cell["column"] for cell in row_cells],
            "row_cell_types": [cell["cell_type"] for cell in row_cells],
            "row_position": _row_position(node, row_number),
            "target_column": target.get("column"),
            "role_geometry": role_geometry,
        }
        cluster_id = "sc_" + _json_sha256(cluster_key)[:16]
        required_missing = sum(
            role.get("requirement") == "required" and role.get("status") != "bound"
            for role in fact["roles"]
        )
        outside_row = _outside_row_role_targets(annotation, target)
        row = {
            "annotation_index": annotation_index,
            "fact_id": fact["fact_id"],
            "financial_type": annotation["financial_label"],
            "page": page,
            "target": target,
            "target_identity_sha256": _json_sha256(target),
            "node_type": node["node_type"],
            "node_order": node["order"],
            "table_dimensions": _table_dimensions(node),
            "table_title_row": _row_literals(node, 1),
            "target_row_literals": _row_literals(node, row_number),
            "target_literal": _target_literal(node, target),
            "roles": annotation["roles"],
            "required_roles_missing": required_missing,
            "role_targets_outside_accepted_row": outside_row,
            "structural_cluster_id": cluster_id,
            "structural_cluster_key": cluster_key,
        }
        rows.append(row)
        cluster_rows[cluster_id].append(row)

    clusters = []
    anomaly_clusters = []
    anomaly_reason_counts: Counter[str] = Counter()
    for cluster_id, members in sorted(cluster_rows.items()):
        reason_set: set[str] = set()
        if len(members) <= 2:
            reason_set.add("rare_structural_cluster")
        if any(item["target"]["kind"] == "node" for item in members):
            reason_set.add("node_target")
        if any(item["required_roles_missing"] for item in members):
            reason_set.add("required_role_missing")
        if any(item["role_targets_outside_accepted_row"] for item in members):
            reason_set.add("role_target_outside_accepted_row")
        if any(target_identities[_json_canonical(item["target"])] > 1 for item in members):
            reason_set.add("multiple_facts_same_target")
        if len({item["financial_type"] for item in members}) > 1:
            reason_set.add("mixed_financial_types_in_structural_cluster")
        summary = {
            "cluster_id": cluster_id,
            "facts_total": len(members),
            "financial_type_counts": dict(
                sorted(Counter(item["financial_type"] for item in members).items())
            ),
            "page_counts": dict(
                sorted(
                    Counter(str(item["page"]) for item in members).items(),
                    key=lambda item: int(item[0]),
                )
            ),
            "anomaly_reasons": sorted(reason_set),
            "cluster_key": members[0]["structural_cluster_key"],
            "member_annotation_indices": [item["annotation_index"] for item in members],
            "representative_annotation_indices": _representatives(members),
        }
        clusters.append(summary)
        if reason_set:
            anomaly_clusters.append(summary)
            anomaly_reason_counts.update(reason_set)

    negative_families = _negative_control_families(
        nodes=nodes,
        provenance=provenance,
        fact_rows=fact_rows_by_table,
    )
    review_manifest = _review_manifest(
        rows=rows,
        anomaly_clusters=anomaly_clusters,
        negative_families=negative_families,
    )
    return {
        "facts_total": len(facts),
        "facts_accounted": len(rows),
        "fact_type_counts": dict(
            sorted(Counter(item["financial_type"] for item in rows).items())
        ),
        "target_kind_counts": dict(
            sorted(Counter(item["target"]["kind"] for item in rows).items())
        ),
        "facts_per_page": dict(
            sorted(
                Counter(str(item["page"]) for item in rows).items(),
                key=lambda item: int(item[0]),
            )
        ),
        "required_review_type_counts": {
            key: sum(item["financial_type"] == key for item in rows)
            for key in sorted(REQUIRED_REVIEW_TYPES)
        },
        "required_roles_missing": sum(item["required_roles_missing"] for item in rows),
        "role_targets_outside_accepted_row": sum(
            item["role_targets_outside_accepted_row"] for item in rows
        ),
        "same_type_duplicate_targets": sum(
            count - 1 for count in type_target_identities.values() if count > 1
        ),
        "multiple_types_same_target": sum(
            len(
                {
                    item["financial_type"]
                    for item in rows
                    if _json_canonical(item["target"]) == target_identity
                }
            )
            > 1
            for target_identity in target_identities
        ),
        "structural_clusters": clusters,
        "anomaly_clusters": anomaly_clusters,
        "anomaly_reason_counts": dict(sorted(anomaly_reason_counts.items())),
        "negative_control_families": negative_families,
        "review_manifest": review_manifest,
        "private_fact_rows": rows,
    }


def _review_manifest(
    *,
    rows: list[dict[str, Any]],
    anomaly_clusters: list[dict[str, Any]],
    negative_families: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_index = {item["annotation_index"]: item for item in rows}
    manifest: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for cluster in anomaly_clusters:
        for index in cluster["representative_annotation_indices"]:
            row = by_index[index]
            key = ("fact", str(index))
            if key in seen:
                continue
            seen.add(key)
            manifest.append(
                {
                    "review_kind": "anomaly_cluster_fact",
                    "coverage_ids": [cluster["cluster_id"]],
                    "annotation_index": index,
                    "page": row["page"],
                    "financial_type": row["financial_type"],
                    "target": row["target"],
                    "target_literal": row["target_literal"],
                    "target_row_literals": row["target_row_literals"],
                    "anomaly_reasons": cluster["anomaly_reasons"],
                }
            )
    for financial_type in sorted(REQUIRED_REVIEW_TYPES):
        members = [item for item in rows if item["financial_type"] == financial_type]
        for row in [members[0], members[len(members) // 2], members[-1]]:
            key = ("fact", str(row["annotation_index"]))
            if key in seen:
                continue
            seen.add(key)
            manifest.append(
                {
                    "review_kind": "required_type_fact",
                    "coverage_ids": [f"type:{financial_type}"],
                    "annotation_index": row["annotation_index"],
                    "page": row["page"],
                    "financial_type": financial_type,
                    "target": row["target"],
                    "target_literal": row["target_literal"],
                    "target_row_literals": row["target_row_literals"],
                    "anomaly_reasons": [],
                }
            )
    for family in negative_families:
        for sample in family["representatives"]:
            manifest.append(
                {
                    "review_kind": "negative_control_row",
                    "coverage_ids": [family["family_id"]],
                    **sample,
                }
            )
    return manifest


def _negative_control_families(
    *,
    nodes: dict[str, dict[str, Any]],
    provenance: dict[str, dict[str, Any]],
    fact_rows: set[tuple[str, int]],
) -> list[dict[str, Any]]:
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes.values():
        if node["node_type"] != "TABLE":
            continue
        rows = sorted({int(cell["row"]) for cell in node["content"]["cells"]})
        for row in rows:
            if (node["node_id"], row) in fact_rows:
                continue
            cells = _row_cells(node, row)
            key = {
                "table_columns": _table_columns(node),
                "row_cell_columns": [cell["column"] for cell in cells],
                "row_cell_types": [cell["cell_type"] for cell in cells],
                "row_position": _row_position(node, row),
            }
            family_id = "nc_" + _json_sha256(key)[:16]
            families[family_id].append(
                {
                    "page": _node_page(node, provenance),
                    "node_id": node["node_id"],
                    "row": row,
                    "row_literals": _row_literals(node, row),
                }
            )
    result = []
    for family_id, members in sorted(families.items()):
        result.append(
            {
                "family_id": family_id,
                "rows_total": len(members),
                "page_counts": dict(
                    sorted(
                        Counter(str(item["page"]) for item in members).items(),
                        key=lambda item: int(item[0]),
                    )
                ),
                "representatives": [members[0], members[len(members) // 2], members[-1]],
            }
        )
    return result


def _representatives(members: list[dict[str, Any]]) -> list[int]:
    ordered = sorted(members, key=lambda item: (item["page"], item["annotation_index"]))
    return sorted(
        {
            ordered[0]["annotation_index"],
            ordered[len(ordered) // 2]["annotation_index"],
            ordered[-1]["annotation_index"],
        }
    )


def _role_geometry(annotation: dict[str, Any], target: dict[str, Any]) -> list[list[Any]]:
    result = []
    for role in annotation["roles"]:
        role_target = role.get("target") or {}
        relation = "missing"
        if role.get("status") == "bound":
            if role_target == target:
                relation = "same_target"
            elif (
                role_target.get("node_id") == target.get("node_id")
                and role_target.get("row") == target.get("row")
            ):
                relation = "same_row"
            elif role_target.get("node_id") == target.get("node_id"):
                relation = "same_node"
            else:
                relation = "outside_node"
        result.append(
            [role["role"], role["status"], relation, role_target.get("column")]
        )
    return result


def _outside_row_role_targets(annotation: dict[str, Any], target: dict[str, Any]) -> int:
    if target["kind"] not in {"table_row", "table_cell"}:
        return 0
    return sum(
        role.get("status") == "bound"
        and (
            (role.get("target") or {}).get("node_id") != target.get("node_id")
            or (role.get("target") or {}).get("row") != target.get("row")
        )
        for role in annotation["roles"]
    )


def _node_page(
    node: dict[str, Any], provenance: dict[str, dict[str, Any]]
) -> int:
    pages = {
        (provenance[source_ref].get("source_locator") or {}).get("page")
        for source_ref in node.get("source_refs") or []
    }
    pages.discard(None)
    if len(pages) != 1:
        raise RuntimeError("canonical_node_page_not_unique")
    return int(next(iter(pages)))


def _table_columns(node: dict[str, Any]) -> list[int]:
    if node["node_type"] != "TABLE":
        return []
    return sorted({int(cell["column"]) for cell in node["content"]["cells"]})


def _table_dimensions(node: dict[str, Any]) -> dict[str, int] | None:
    if node["node_type"] != "TABLE":
        return None
    cells = node["content"]["cells"]
    return {
        "rows": max(int(cell["row"]) for cell in cells),
        "columns": max(int(cell["column"]) for cell in cells),
        "cells": len(cells),
    }


def _row_cells(node: dict[str, Any], row: Any) -> list[dict[str, Any]]:
    if node["node_type"] != "TABLE" or not isinstance(row, int):
        return []
    return sorted(
        [cell for cell in node["content"]["cells"] if cell["row"] == row],
        key=lambda cell: cell["column"],
    )


def _row_position(node: dict[str, Any], row: Any) -> str:
    if node["node_type"] != "TABLE" or not isinstance(row, int):
        return "not_table_row"
    maximum = max(int(cell["row"]) for cell in node["content"]["cells"])
    if row == 1:
        return "first"
    if row == maximum:
        return "last"
    return "interior"


def _row_literals(node: dict[str, Any], row: Any) -> list[str]:
    return [str(cell.get("displayed_value") or "") for cell in _row_cells(node, row)]


def _target_literal(node: dict[str, Any], target: dict[str, Any]) -> Any:
    if target["kind"] == "node":
        return (node.get("content") or {}).get("text")
    values = _row_literals(node, target.get("row"))
    if target["kind"] == "table_row":
        return values
    cell = next(
        item
        for item in _row_cells(node, target.get("row"))
        if item["column"] == target.get("column")
    )
    return str(cell.get("displayed_value") or "")


def _store(root: Path) -> Any:
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()


def _context() -> ArtifactAccessContext:
    return ArtifactAccessContext(
        **BASE_CONTEXT,
        normalization_run_id=LARGE_RUN_ID,
        allow_private=True,
    )


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(_json_canonical(value).encode("utf-8")).hexdigest()


def _json_canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
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
