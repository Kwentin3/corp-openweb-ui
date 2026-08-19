#!/usr/bin/env python3
"""Assemble G5.40F from the frozen G5.40E store without provider execution."""

from __future__ import annotations

import argparse
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
from broker_reports_gate1.gate5_real_tax_case_assembly import (  # noqa: E402
    Gate5RealTaxCaseAssemblyRuntimeFactory,
)
from broker_reports_gate1.gate5_trusted_methodology import (  # noqa: E402
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)


FACTORY_REQUIRED = (
    "ArtifactStoreFactory.create and Gate5RealTaxCaseAssemblyRuntimeFactory.create "
    "are the only frozen deterministic proof path"
)
FORBIDDEN = (
    "provider, LLM, retry, repair, synthetic supplement, direct SQL, source "
    "document read, reconciliation, graph or persisted financial-event relation"
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
        "--g540e-receipt",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-13"
            / "BROKER_REPORTS_GATE5_REAL_SOURCE_FACT_CONTRACT_G5_40E.receipt.safe.json"
        ),
    )
    parser.add_argument(
        "--private-evidence-dir",
        default=str(
            Path.home()
            / ".codex"
            / "private-evidence"
            / "broker-reports-g5.40f-20260813-v1"
        ),
    )
    parser.add_argument(
        "--safe-receipt-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-13"
            / "BROKER_REPORTS_GATE5_REAL_TAX_CASE_ASSEMBLY_G5_40F.receipt.safe.json"
        ),
    )
    parser.add_argument(
        "--safe-matrix-path",
        default=str(
            REPO_ROOT
            / "docs"
            / "reports"
            / "2026-08-13"
            / "BROKER_REPORTS_GATE5_REAL_TAX_CASE_ASSEMBLY_G5_40F.matrix.safe.json"
        ),
    )
    args = parser.parse_args()

    store_root = Path(args.store_root).resolve()
    upstream_path = Path(args.g540e_receipt).resolve()
    private_root = Path(args.private_evidence_dir).resolve()
    safe_receipt_path = Path(args.safe_receipt_path).resolve()
    safe_matrix_path = Path(args.safe_matrix_path).resolve()
    if not (store_root / "artifacts.sqlite3").is_file():
        raise SystemExit("frozen_store_unavailable")
    if not upstream_path.is_file():
        raise SystemExit("g540e_safe_receipt_unavailable")
    if _is_within(private_root, REPO_ROOT.resolve()):
        raise SystemExit("private_evidence_must_be_outside_repository")
    if not _is_within(safe_receipt_path, REPO_ROOT.resolve()):
        raise SystemExit("safe_receipt_must_be_inside_repository")
    if not _is_within(safe_matrix_path, REPO_ROOT.resolve()):
        raise SystemExit("safe_matrix_must_be_inside_repository")

    upstream_raw = upstream_path.read_bytes()
    upstream = json.loads(upstream_raw.decode("utf-8"))
    if (
        upstream.get("goal") != "G5.40E"
        or upstream.get("all_documents_complete") is not True
        or upstream.get("provider_rerun_count") != 0
        or upstream.get("retry_count") != 0
        or upstream.get("repair_count") != 0
        or upstream.get("fallback_count") != 0
    ):
        raise SystemExit("g540e_frozen_boundary_invalid")

    store_before = _store_snapshot(store_root)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=store_root / "artifacts.sqlite3",
            payload_root=store_root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(**BASE_CONTEXT)
    assembled = Gate5RealTaxCaseAssemblyRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().assemble(
        source_fact_methodology_ref=_source_fact_methodology_ref(),
        context=context,
        evidence_mode="REAL_EVIDENCE",
    )
    store_after = _store_snapshot(store_root)
    if store_after != store_before:
        raise SystemExit("read_only_case_assembly_mutated_store")

    private_root.mkdir(parents=True, exist_ok=True)
    private_case_path = private_root / "case_assembly.private.json"
    _atomic_write(private_case_path, _json_bytes(assembled))
    safe_matrix_raw = _json_bytes(_safe_matrix(assembled))
    _atomic_write(safe_matrix_path, safe_matrix_raw)
    safe_receipt = _safe_receipt(
        assembled=assembled,
        upstream_sha256=hashlib.sha256(upstream_raw).hexdigest(),
        private_case_sha256=hashlib.sha256(private_case_path.read_bytes()).hexdigest(),
        safe_matrix_sha256=hashlib.sha256(safe_matrix_raw).hexdigest(),
        store_sha256=store_before["tree_sha256"],
    )
    _atomic_write(safe_receipt_path, _json_bytes(safe_receipt))
    _atomic_write(
        private_root / "private_manifest.json",
        _json_bytes(_private_manifest(private_root)),
    )
    print(
        json.dumps(
            {
                "goal": "G5.40F",
                "terminals": safe_receipt["terminals"],
                "demands": safe_receipt["metrics"]["declaration_demands_total"],
                "resolved": safe_receipt["metrics"]["RESOLVED"],
                "not_activated": safe_receipt["metrics"][
                    "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
                ],
                "missing": safe_receipt["metrics"]["MISSING_EVIDENCE"],
                "source_insufficient": safe_receipt["metrics"][
                    "SOURCE_EVIDENCE_INSUFFICIENT"
                ],
                "fifo_calculations": safe_receipt["metrics"][
                    "fifo_calculations"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


def _safe_receipt(
    *,
    assembled: dict[str, Any],
    upstream_sha256: str,
    private_case_sha256: str,
    safe_matrix_sha256: str,
    store_sha256: str,
) -> dict[str, Any]:
    source = assembled["source_fact_assembly"]
    demand_rows = [
        {
            "demand": item["demand"],
            "domain_id": item["domain_id"],
            "terminal": item["terminal"],
            "available_fact_count": len(item["available_evidence"]["fact_ids"]),
            "blocker_present": item["blocker"] is not None,
        }
        for item in assembled["declaration_demands"]
    ]
    return {
        "schema_version": "broker_reports_gate5_real_tax_case_assembly_receipt_v0",
        "goal": "G5.40F",
        "terminals": copy_list(assembled["terminals"]),
        "evidence_mode": assembled["evidence_mode"],
        "upstream_g540e_receipt_sha256": upstream_sha256,
        "private_case_sha256": private_case_sha256,
        "safe_matrix_sha256": safe_matrix_sha256,
        "private_evidence_available": True,
        "private_evidence_location_committed": False,
        "store_tree_sha256_before_after_equal": store_sha256,
        "provider_calls": 0,
        "provider_reruns": 0,
        "synthetic_supplemental_facts": 0,
        "knowledge_origins": [
            {
                "origin": item["origin"],
                "status": item["status"],
                "count": item["count"],
            }
            for item in assembled["knowledge_origins"]
        ],
        "metrics": dict(assembled["metrics"]),
        "declaration_demands": demand_rows,
        "source_fact_blocker_reason_counts": {
            reason: sum(item["reason_code"] == reason for item in source["blockers"])
            for reason in sorted({item["reason_code"] for item in source["blockers"]})
        },
        "multi_source_status": assembled["multi_source_assembly"]["status"],
        "source_documents": len(source["source_document_ids"]),
        "source_facts": source["facts_total"],
        "security_fact_counts": dict(source["security_fact_counts"]),
        "security_groups_total": len(source["security_groups"]),
        "security_group_status_counts": {
            status: sum(item["status"] == status for item in source["security_groups"])
            for status in sorted({item["status"] for item in source["security_groups"]})
        },
        "exact_source_fact_blockers": len(source["blockers"]),
        "reconciliation": assembled["reconciliation"],
        "invented_facts": assembled["invented_facts"],
        "invented_relations": assembled["invented_relations"],
        "stored_financial_event_relations": assembled[
            "stored_financial_event_relations"
        ],
        "new_persistence": False,
        "real_world_taxpayer_completeness_asserted": False,
    }


def _safe_matrix(assembled: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in assembled["declaration_demands"]:
        blocker = item["blocker"]
        rows.append(
            {
                "demand": item["demand"],
                "domain_id": item["domain_id"],
                "required_tax_rule": item["required_tax_rule"],
                "required_evidence": item["required_evidence"],
                "available_evidence": {
                    "knowledge_origin": item["available_evidence"][
                        "knowledge_origin"
                    ],
                    "fact_count": len(item["available_evidence"]["fact_ids"]),
                    "source_document_count": len(
                        item["available_evidence"]["source_document_ids"]
                    ),
                    "deterministic_calculation_count": item[
                        "available_evidence"
                    ]["deterministic_calculation_count"],
                },
                "terminal": item["terminal"],
                "blocker": (
                    None
                    if blocker is None
                    else {
                        "terminal": blocker["terminal"],
                        "why_supplied_evidence_is_insufficient": blocker[
                            "why_supplied_evidence_is_insufficient"
                        ],
                        "evidence_that_could_close": blocker[
                            "evidence_that_could_close"
                        ],
                        "source_fact_blocker_reason_codes": blocker[
                            "evidence_searched"
                        ]["source_fact_blocker_reason_codes"],
                        "exact_private_blocker_available": True,
                    }
                ),
            }
        )
    return {
        "schema_version": "broker_reports_gate5_real_tax_case_demand_matrix_v0",
        "goal": "G5.40F",
        "terminals": copy_list(assembled["terminals"]),
        "evidence_mode": assembled["evidence_mode"],
        "rows": rows,
        "metrics": dict(assembled["metrics"]),
        "private_values_committed": False,
        "synthetic_supplemental_facts": 0,
        "invented_facts": 0,
        "invented_relations": 0,
        "reconciliation": "not_performed",
    }


def _source_fact_methodology_ref() -> dict[str, str]:
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
        "schema_version": "broker_reports_gate5_real_tax_case_private_manifest_v0",
        "goal": "G5.40F",
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


def copy_list(value: list[Any]) -> list[Any]:
    return [item for item in value]


if __name__ == "__main__":
    raise SystemExit(main())
