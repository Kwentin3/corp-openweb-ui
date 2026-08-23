#!/usr/bin/env python3
"""Run G5.41 on the frozen G5.40E evidence store without provider calls."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.gate5_declaration_preparation import (  # noqa: E402
    Gate5DeclarationPreparationRuntimeFactory,
)
from broker_reports_gate1.gate5_human_gap_closure import (  # noqa: E402
    gate5_case_taxpayer_scope_ref,
)
from broker_reports_gate1.gate5_declaration_scope_resolution import (  # noqa: E402
    GATE5_USER_INTENT_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_trusted_methodology import (  # noqa: E402
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)


FACTORY_REQUIRED = (
    "ArtifactStoreFactory.create and "
    "Gate5DeclarationPreparationRuntimeFactory.create are the only G5.41 proof path"
)
FORBIDDEN = (
    "provider, LLM, retry, repair, direct SQL, raw source file, synthetic "
    "supplement, reconciliation, relation graph, manual XML or product activation"
)

BASE_CONTEXT = {
    "user_id": "g540e-private-user",
    "case_id": "g540e-real-source-contract",
    "chat_id": None,
    "workspace_model_id": "g540e-private-model",
    "normalization_run_id": "normrun_25c3b0606ce86852",
    "allow_private": True,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--store-root",
        default=str(REPO_ROOT / "local" / "g540e_private_20260813" / "store"),
    )
    parser.add_argument(
        "--upstream-receipt",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-13"
            / "BROKER_REPORTS_GATE5_REAL_TAX_CASE_ASSEMBLY_G5_40F.receipt.safe.json"
        ),
    )
    parser.add_argument(
        "--private-evidence-dir",
        default=str(
            Path.home()
            / ".codex"
            / "private-evidence"
            / "broker-reports-g5.41-20260813-v1"
        ),
    )
    parser.add_argument(
        "--safe-receipt-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-13"
            / "BROKER_REPORTS_GATE5_DECLARATION_PREPARATION_G5_41.receipt.safe.json"
        ),
    )
    parser.add_argument(
        "--safe-actions-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-13"
            / "BROKER_REPORTS_GATE5_DECLARATION_PREPARATION_G5_41.actions.safe.json"
        ),
    )
    args = parser.parse_args()

    store_root = Path(args.store_root).resolve()
    upstream_path = Path(args.upstream_receipt).resolve()
    private_root = Path(args.private_evidence_dir).resolve()
    receipt_path = Path(args.safe_receipt_path).resolve()
    actions_path = Path(args.safe_actions_path).resolve()
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("frozen_store_unavailable")
    if not upstream_path.is_file():
        raise SystemExit("g540f_receipt_unavailable")
    if _is_within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if not _is_within(receipt_path, REPO_ROOT.resolve()) or not _is_within(
        actions_path, REPO_ROOT.resolve()
    ):
        raise SystemExit("safe_evidence_must_be_inside_repository")
    upstream_raw = upstream_path.read_bytes()
    upstream = json.loads(upstream_raw.decode("utf-8"))
    if (
        upstream.get("goal") != "G5.40F"
        or "REAL_CASE_ASSEMBLY_PROVEN" not in upstream.get("terminals", [])
        or upstream.get("provider_calls") != 0
        or upstream.get("invented_facts") != 0
        or upstream.get("invented_relations") != 0
    ):
        raise SystemExit("g540f_boundary_invalid")

    store_before = _store_snapshot(store_root)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(**BASE_CONTEXT)
    result = (
        Gate5DeclarationPreparationRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .prepare(
            source_fact_methodology_ref=_source_methodology_ref(),
            context=context,
            evidence_mode="REAL_EVIDENCE",
            user_intent={
                "schema_version": GATE5_USER_INTENT_SCHEMA_VERSION,
                "form": "3-NDFL",
                "tax_period": "2025",
                "task": "prepare_tax_declaration",
                "domains": ["broker_securities_income"],
            },
            taxpayer_scope_ref=gate5_case_taxpayer_scope_ref(context),
            user_case_facts=[],
        )
    )
    store_after = _store_snapshot(store_root)
    if store_before != store_after:
        raise SystemExit("read_only_g541_mutated_frozen_store")
    expected_terminals = {
        "EVIDENCE_INTAKE_CONTRACT_PROVEN",
        "CLIENT_EVIDENCE_REVIEW_PROVEN",
        "DECLARATION_SCOPE_ACTIVATION_PROVEN",
        "HUMAN_GAP_CLOSURE_LOOP_PROVEN",
        "DECLARATION_PREPARATION_WORKFLOW_PROVEN",
        "RESIDENCY_EVIDENCE_BOUNDARY_PROVEN",
        "REAL_EVIDENCE_GAPS_REMAIN",
    }
    if set(result["terminals"]) != expected_terminals:
        raise SystemExit("g541_terminals_invalid")

    private_root.mkdir(parents=True, exist_ok=True)
    private_result_path = private_root / "declaration_preparation.private.json"
    _atomic_write(private_result_path, _json_bytes(result))
    safe_actions = _safe_actions(result)
    actions_raw = _json_bytes(safe_actions)
    _atomic_write(actions_path, actions_raw)
    receipt = _safe_receipt(
        result=result,
        upstream_sha256=hashlib.sha256(upstream_raw).hexdigest(),
        private_sha256=hashlib.sha256(private_result_path.read_bytes()).hexdigest(),
        actions_sha256=hashlib.sha256(actions_raw).hexdigest(),
        store_sha256=store_before["tree_sha256"],
    )
    _atomic_write(receipt_path, _json_bytes(receipt))
    _atomic_write(
        private_root / "private_manifest.json",
        _json_bytes(_private_manifest(private_root)),
    )
    print(
        json.dumps(
            {
                "goal": "G5.41",
                "terminals": receipt["terminals"],
                "metadata_facts": receipt["intake"]["metadata_facts"],
                "active_demands": receipt["scope"]["active_demands"],
                "required_actions": receipt["closure"]["required_actions"],
                "advisory_actions": receipt["closure"]["advisory_actions"],
                "declaration_ready": receipt["readiness"]["ready"],
            },
            sort_keys=True,
        )
    )
    return 0


def _safe_receipt(
    *,
    result: dict[str, Any],
    upstream_sha256: str,
    private_sha256: str,
    actions_sha256: str,
    store_sha256: str,
) -> dict[str, Any]:
    intake = result["intake"]
    review = result["client_review"]
    scope = result["scope_activation"]
    closure = result["gap_closure"]
    fact_type_counts = Counter(item["fact_type"] for item in intake["metadata_facts"])
    closure_type_counts = Counter(
        item["closure_type"]
        for item in [
            *closure["required_actions"],
            *closure["advisory_actions"],
            *closure["deferred_actions"],
        ]
    )
    return {
        "schema_version": "broker_reports_gate5_declaration_preparation_receipt_v0",
        "goal": "G5.41",
        "terminals": list(result["terminals"]),
        "evidence_mode": result["evidence_mode"],
        "upstream_g540f_receipt_sha256": upstream_sha256,
        "private_result_sha256": private_sha256,
        "safe_actions_sha256": actions_sha256,
        "frozen_store_tree_sha256_before_after_equal": store_sha256,
        "provider_calls": 0,
        "provider_reruns": 0,
        "retry_count": 0,
        "repair_count": 0,
        "intake": {
            "documents": len(intake["documents"]),
            "metadata_facts": len(intake["metadata_facts"]),
            "metadata_fact_type_counts": dict(sorted(fact_type_counts.items())),
            "metadata_category_counts": intake["coverage"][
                "metadata_category_counts"
            ],
            "financial_category_counts": intake["coverage"][
                "financial_category_counts"
            ],
            "lost_upstream": intake["coverage"]["lost_upstream"],
            "provenance_complete": intake["coverage"]["provenance_complete"],
        },
        "review": {
            "coverage_groups": review["metrics"]["coverage_groups"],
            "required_blockers": review["metrics"]["required_blockers"],
            "advisory_findings": review["metrics"]["advisory_findings"],
            "commission_sanity": review["commission_sanity"],
            "withheld_tax_sanity": review["withheld_tax_sanity"],
        },
        "scope": dict(scope["metrics"]),
        "closure": {
            **dict(closure["metrics"]),
            "closure_type_counts": dict(sorted(closure_type_counts.items())),
        },
        "readiness": dict(result["declaration_readiness"]),
        "machine_readable_draft_calculations": result[
            "machine_readable_declaration_draft"
        ]["calculation_count"],
        "target_release_status": result["target_release"]["status"],
        "xml_emitted": result["target_release"]["xml_emitted"],
        "pdf_emitted": result["target_release"]["pdf_emitted"],
        "private_values_committed": False,
        "private_evidence_available": True,
        "private_evidence_location_committed": False,
        "invented_source_facts": result["metrics"]["invented_source_facts"],
        "invented_relations": result["metrics"]["invented_relations"],
        "reconciliation": result["reconciliation"],
        "new_persistence": False,
        "product_activation": False,
        "real_world_taxpayer_completeness_asserted": False,
    }


def _safe_actions(result: dict[str, Any]) -> dict[str, Any]:
    closure = result["gap_closure"]
    rows = []
    for kind, actions in (
        ("REQUIRED", closure["required_actions"]),
        ("ADVISORY", closure["advisory_actions"]),
        ("DEFERRED", closure["deferred_actions"]),
    ):
        for item in actions:
            rows.append(
                {
                    "kind": kind,
                    "priority": item["priority"],
                    "closure_type": item["closure_type"],
                    "fact_key": item["fact_key"],
                    "demand_count": len(item["demand_refs"]),
                    "evidence_ref_count": len(item["evidence_refs"]),
                    "subject_present": bool(item["subject"]),
                    "exact_private_action_available": True,
                    "client_benefit_present": bool(item["client_benefit"]),
                }
            )
    return {
        "schema_version": "broker_reports_gate5_declaration_actions_safe_v0",
        "goal": "G5.41",
        "terminals": list(result["terminals"]),
        "rows": rows,
        "private_values_committed": False,
        "raw_transactions_committed": False,
        "invented_facts": 0,
        "invented_relations": 0,
    }


def _source_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    }


def _store_snapshot(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        raw = path.read_bytes()
        files.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return {
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "tree_sha256": hashlib.sha256(_json_bytes(files)).hexdigest(),
    }


def _private_manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "private_manifest.json":
            continue
        raw = path.read_bytes()
        files.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return {
        "schema_version": "broker_reports_gate5_declaration_preparation_private_manifest_v0",
        "goal": "G5.41",
        "privacy": "PRIVATE_OUTSIDE_GIT",
        "files": files,
    }


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


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


def _is_within(candidate: Path, parent: Path) -> bool:
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
