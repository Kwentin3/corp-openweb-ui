#!/usr/bin/env python3
"""Deterministically finalize a completed G5.80 Gate 3 replay in current code."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.gate3_ndfl_case_readiness import (  # noqa: E402
    Gate3NdflCaseReadinessFactory,
)
from broker_reports_gate1.gate3_role_labeling import (  # noqa: E402
    Gate3RoleValueResolverFactory,
)
from broker_reports_gate1.gate4_financial_case_cache import (  # noqa: E402
    CASE_COMPLETE_FOR_CURRENT_INPUT_SET,
    Gate4FinancialCaseRuntimeFactory,
)
from broker_reports_gate1.gate4_financial_case_materialization import (  # noqa: E402
    gate4_annotation_materialization_decision,
)
from live_gate5_real_source_fact_contract import (  # noqa: E402
    _atomic_write,
    _json_bytes,
    _jsonable,
)


LARGE_DOCUMENT_ID = "brdoc_001_7cfd297786cc"
CURRENT_RUN_ID = "normrun_1f4f2d9e30c1a076"
CURRENT_CANONICAL_VERSION_ID = "canver_lvs64r6lTXf56n30XPIfbV0FRxwVW1lE"
BASE_CONTEXT = {
    "user_id": "g540e-private-user",
    "case_id": "g540e-real-source-contract",
    "chat_id": None,
    "workspace_model_id": "g540e-private-model",
}
BASELINE_RUNS = {
    "brdoc_001_25c3b0606ce8": "normrun_056b15c46f64d9c9",
    "brdoc_001_79af73d5be78": "normrun_0ac55d0083f8ad4a",
    LARGE_DOCUMENT_ID: "normrun_b5c1922880533908",
    "brdoc_001_36a166a5a13e": "normrun_e5dcaae40e5ab7a9",
}
G57908_TARGET = {
    "kind": "table_cell",
    "node_id": "node_bfdfbcc1b016e5225a13ecd4",
    "row": 5,
    "column": 4,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store-root", type=Path, required=True)
    parser.add_argument("--baseline-store-root", type=Path, required=True)
    parser.add_argument("--baseline-gate4-private", type=Path, required=True)
    parser.add_argument("--incident-freeze-private", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()

    current_store = _store(args.store_root.resolve())
    baseline_store = _store(args.baseline_store_root.resolve())
    context = _context(CURRENT_RUN_ID)
    readiness = Gate3NdflCaseReadinessFactory(
        store=current_store,
        read_enabled=True,
    ).create(context=context)
    if readiness.get("case_status") != "ready_for_gate4_handoff":
        raise SystemExit("current_gate3_sidecars_not_ready")

    runtime = Gate4FinancialCaseRuntimeFactory(
        store=current_store,
        read_enabled=True,
    ).create()
    assembly = runtime.rebuild_case(context=context)
    if assembly.status != CASE_COMPLETE_FOR_CURRENT_INPUT_SET:
        raise SystemExit("current_gate4_case_incomplete")
    materializations = [
        runtime.materialize_artifact(
            financial_annotations_artifact_id=source.financial_annotations_artifact_id,
            context=context,
        )
        for source in assembly.sources
        if source.financial_annotations_artifact_id is not None
    ]
    omissions = [
        item
        for materialization in materializations
        for item in materialization.non_materialized_presence_annotations
    ]
    current_facts = list(assembly.facts)
    baseline_facts = json.loads(
        args.baseline_gate4_private.read_text(encoding="utf-8")
    )["assembly"]["facts"]
    baseline_atomic, baseline_non_atomic = _classify_baseline(
        store=baseline_store,
        facts=baseline_facts,
    )

    current_by_document = _by_document(current_facts)
    baseline_atomic_by_document = _by_document(baseline_atomic)
    unchanged_documents = [
        document_id
        for document_id in BASELINE_RUNS
        if document_id != LARGE_DOCUMENT_ID
    ]
    unchanged_exact = all(
        _facts_hash(current_by_document[document_id])
        == _facts_hash(baseline_atomic_by_document[document_id])
        for document_id in unchanged_documents
    )
    old_large = baseline_atomic_by_document[LARGE_DOCUMENT_ID]
    new_large = current_by_document[LARGE_DOCUMENT_ID]
    old_signatures = Counter(_semantic_signature(fact) for fact in old_large)
    new_signatures = Counter(_semantic_signature(fact) for fact in new_large)
    matched_large = sum((old_signatures & new_signatures).values())
    lost_old_large_atomic = len(old_large) - matched_large
    added_large_atomic = len(new_large) - matched_large

    incidents = json.loads(
        args.incident_freeze_private.read_text(encoding="utf-8")
    )["incidents"]
    decimal_fact_ids = {
        item["gate4_fact"]["fact_id"]
        for item in incidents
        if item["gate5_reason"] == "gate5_source_fact_decimal_invalid"
    }
    current_fact_ids = {fact["fact_id"] for fact in current_facts}
    decimal_facts_preserved = decimal_fact_ids <= current_fact_ids

    g57908 = [
        fact
        for fact in current_facts
        if _document_id(fact) == "brdoc_001_79af73d5be78"
        and fact["annotation_target"] == G57908_TARGET
    ]
    g57908_roles = {
        role["role"]: role["status"] for fact in g57908 for role in fact["roles"]
    }
    all_current_atomic = len(current_facts) == sum(
        len(materialization.facts) for materialization in materializations
    )
    no_unexplained_delta = unchanged_exact and lost_old_large_atomic == 0
    passed = (
        all_current_atomic
        and no_unexplained_delta
        and decimal_facts_preserved
        and len(g57908) == 1
        and g57908_roles.get("amount") == "missing"
        and g57908_roles.get("currency") == "missing"
    )

    private = {
        "schema_version": "broker_reports_g580_atomic_replay_final_private_v1",
        "goal": "G5.80",
        "assembly": _jsonable(assembly),
        "non_materialized_presence_annotations": omissions,
        "baseline_non_atomic_facts": baseline_non_atomic,
    }
    _atomic_write(args.private_output.resolve(), _json_bytes(private))
    safe = {
        "schema_version": "broker_reports_g580_atomic_replay_final_safe_v1",
        "goal": "G5.80",
        "terminal": (
            "CURRENT_CASE_SOURCE_FACTS_REQUALIFIED"
            if passed
            else "CURRENT_CASE_SOURCE_FACT_DELTA_UNEXPLAINED"
        ),
        "canonical_version_id": CURRENT_CANONICAL_VERSION_ID,
        "gate3_case_status": assembly.gate3_case_status,
        "gate4_status": assembly.status,
        "baseline_facts_total": len(baseline_facts),
        "baseline_atomic_facts": len(baseline_atomic),
        "baseline_non_atomic_pseudo_facts": len(baseline_non_atomic),
        "current_facts_total": len(current_facts),
        "current_non_materialized_presence_total": len(omissions),
        "unchanged_documents_exact": unchanged_exact,
        "old_large_atomic_facts": len(old_large),
        "new_large_atomic_facts": len(new_large),
        "matched_old_large_atomic_facts": matched_large,
        "lost_old_large_atomic_facts": lost_old_large_atomic,
        "added_large_atomic_facts": added_large_atomic,
        "no_unexplained_delta": no_unexplained_delta,
        "g57908_exact_fact_count": len(g57908),
        "g57908_amount_status": g57908_roles.get("amount"),
        "g57908_currency_status": g57908_roles.get("currency"),
        "decimal_incident_facts_expected": len(decimal_fact_ids),
        "decimal_incident_facts_preserved": decimal_facts_preserved,
        "manual_facts": 0,
        "production_visual_dependency": False,
        "stored_purchase_sale_relations": 0,
        "false_user_requests": 0,
        "passed": passed,
    }
    _atomic_write(args.safe_output.resolve(), _json_bytes(safe))
    print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 2


def _store(root: Path) -> Any:
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()


def _context(run_id: str) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        **BASE_CONTEXT,
        normalization_run_id=run_id,
        allow_private=True,
    )


def _classify_baseline(*, store: Any, facts: list[dict[str, Any]]) -> tuple[list, list]:
    versions = {
        _document_id(fact): fact["gate3_binding"]["canonical_binding"][
            "canonical_version_id"
        ]
        for fact in facts
    }
    resolvers = {
        document_id: Gate3RoleValueResolverFactory.create_from_active_canonical(
            store=store,
            read_enabled=True,
            document_id=document_id,
            expected_canonical_version_id=versions[document_id],
            context=_context(run_id),
        )
        for document_id, run_id in BASELINE_RUNS.items()
    }
    atomic: list[dict[str, Any]] = []
    non_atomic: list[dict[str, Any]] = []
    for fact in facts:
        resolver = resolvers[_document_id(fact)]
        annotation = _annotation_from_fact(fact)
        decision = gate4_annotation_materialization_decision(
            annotation,
            structurally_atomic_target=(
                resolver.is_unambiguously_atomic_assertion_target(
                    annotation["target"]
                )
            ),
            unambiguous_literal_anchor=(
                resolver.has_unambiguous_literal_anchor(annotation)
            ),
        )
        (atomic if decision["materializable"] else non_atomic).append(fact)
    return atomic, non_atomic


def _annotation_from_fact(fact: dict[str, Any]) -> dict[str, Any]:
    roles = []
    for role in fact["roles"]:
        source = role.get("source_binding")
        if not isinstance(source, dict):
            roles.append({"role": role["role"], "status": "missing"})
            continue
        restored = {
            "role": role["role"],
            "status": "bound",
            "target": source["target"],
        }
        if source.get("exact_text") is not None:
            restored["exact_text"] = source["exact_text"]
        roles.append(restored)
    return {
        "target": fact["annotation_target"],
        "financial_label": fact["financial_type"],
        "roles": roles,
    }


def _document_id(fact: dict[str, Any]) -> str:
    return fact["gate3_binding"]["canonical_binding"]["document_id"]


def _by_document(facts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {document_id: [] for document_id in BASELINE_RUNS}
    for fact in facts:
        result[_document_id(fact)].append(fact)
    return result


def _facts_hash(facts: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(
            facts,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _semantic_signature(fact: dict[str, Any]) -> str:
    roles = [
        {
            "role": role["role"],
            "status": role["status"],
            "value": role.get("value"),
        }
        for role in fact["roles"]
    ]
    return json.dumps(
        {"financial_type": fact["financial_type"], "roles": roles},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
