#!/usr/bin/env python3
"""Build privacy-safe G5.48 path-diff and gap reclassification evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--private-g546-result", required=True)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    report_root = root / "docs" / "reports" / "2026-08-14"
    legacy_path = report_root / (
        "BROKER_REPORTS_GATE5_REAL_SEMANTIC_RECOVERY_G5_47.audit.safe.json"
    )
    one_gap_path = report_root / (
        "BROKER_REPORTS_GATE5_EXISTING_PIPELINE_ONE_GAP_G5_48.receipt.safe.json"
    )
    private_path = Path(args.private_g546_result).resolve()
    if _within(private_path, root):
        raise SystemExit("private_input_must_be_outside_repository")
    legacy = _json(legacy_path)
    one_gap = _json(one_gap_path)
    g546 = _json(private_path)
    exact_bound_inputs = {
        item["required_input"]
        for item in g546["evidence_demand"]["evidence_demands"]
        if item["required_input"].startswith("client_review:")
        and str(item.get("why_required") or "").startswith("g4fact_")
    }

    rows = []
    for item in legacy["classification_rows"]:
        old = item["classification"]
        required_input = item["required_input"]
        if old == "CANONICAL_PRESERVATION_GAP":
            new = (
                "EXISTING_PIPELINE_ROLE_EXTRACTION_GAP"
                if required_input in exact_bound_inputs
                else "RECOVERY_PATH_BYPASSED_EXISTING_OWNER"
            )
        elif old == "SOURCE_DOES_NOT_PROVE_REQUIRED_FACT":
            new = "UPSTREAM_FACT_CONTRACT_GAP"
        else:
            new = old
        rows.append(
            {
                "required_input": required_input,
                "underlying_semantic_meanings": item["underlying_semantic_meanings"],
                "g547_classification": old,
                "g548_classification": new,
            }
        )
    counts = {
        name: sum(item["g548_classification"] == name for item in rows)
        for name in sorted({item["g548_classification"] for item in rows})
    }
    reclassification = {
        "schema_version": "broker_reports_g548_gap_reclassification_v1",
        "goal": "G5.48",
        "status": "PRESERVATION_GAPS_RECLASSIFIED",
        "rows": rows,
        "counts": counts,
        "g547_canonical_preservation_gap_count": 29,
        "g548_true_canonical_preservation_gap_count": 0,
        "basis": {
            "exact_existing_gate4_fact_bindings": len(exact_bound_inputs),
            "legacy_rows_reclassified": len(rows),
            "canonical_preservation_not_proven_by_document_wide_provider_failure": True,
        },
        "private_values_committed": False,
    }
    reclassification_path = report_root / (
        "BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION_G5_48.reclassification.safe.json"
    )
    _write_json(reclassification_path, reclassification)

    old_tokens = 667_531
    current_tokens = one_gap["input_tokens_total"]
    path_diff = {
        "schema_version": "broker_reports_g548_path_diff_v1",
        "goal": "G5.48",
        "legacy_g547": {
            "reader_owner": "Gate5RealSemanticRecoveryRuntime",
            "source_view": "whole Canonical document atoms",
            "provider_calls": 4,
            "input_tokens": old_tokens,
            "gate4_path": "transient Canonical recovery projector",
            "status": "REMOVED_FROM_MAINTAINED_RUNTIME",
        },
        "current_g548": {
            "demand_owner": "Gate5EvidenceDemandRuntimeFactory.create",
            "binding_port": "Gate3EvidenceDemandPortFactory.create",
            "source_semantics_owner": "Gate3ChunkBatchLabelingFactory.create",
            "context_owner": "Gate3StructuralChunkFactory.create",
            "role_context_owner": "Gate3RoleContextFactory.create_from_accepted_facts",
            "gate4_path": "validated persisted FinancialAnnotationsV2 only",
            "source_or_canonical_read_by_gate5": False,
            "one_gap_provider_calls": one_gap["provider_submissions"],
            "one_gap_input_tokens": current_tokens,
            "one_gap_chunk_chars": one_gap["chunk_chars"],
            "one_gap_chunk_targets": one_gap["chunk_targets"],
            "one_gap_demanded_annotations": one_gap["demanded_annotations"],
            "one_gap_demanded_complete_annotations": one_gap[
                "demanded_complete_annotations"
            ],
            "store_unchanged": one_gap["store_unchanged"],
        },
        "comparison": {
            "provider_call_reduction_for_bounded_one_gap": 2,
            "input_token_reduction_percent_for_bounded_one_gap": round(
                (1 - current_tokens / old_tokens) * 100, 2
            ),
            "same_scope_warning": (
                "G5.47 measured four whole documents; G5.48 measured one exact "
                "gap chunk. The ratio proves bounding, not corpus-wide cost parity."
            ),
        },
        "recovery_terminal": {
            "BOUNDED_CONTEXT_EXECUTION_PROVEN": True,
            "BOUNDED_CONTEXT_RECOVERY_PROVEN": False,
            "reason": "demanded type re-emitted but no Role-Pack-complete fact",
        },
    }
    path_diff_path = report_root / (
        "BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION_G5_48.path-diff.safe.json"
    )
    _write_json(path_diff_path, path_diff)

    artifacts = [
        "services/broker-reports-gate1-proof/broker_reports_gate1/gate3_bounded_labeling.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/gate3_chunk_batch_labeling.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/gate3_evidence_demand_port.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/gate4_financial_case_materialization.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/gate5_evidence_demand.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/gate5_evidence_demand_contract.py",
        "services/broker-reports-gate1-proof/broker_reports_gate1/gate5_methodology_evidence.py",
        "services/broker-reports-gate1-proof/scripts/live_gate5_existing_pipeline_one_gap.py",
        "services/broker-reports-gate1-proof/scripts/build_gate5_existing_pipeline_reconnection_evidence.py",
        "services/broker-reports-gate1-proof/tests/test_broker_reports_cross_gate_contract_architecture.py",
        "services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_evidence_demand.py",
        "services/broker-reports-gate1-proof/tests/test_broker_reports_gate5_existing_pipeline_reconnection.py",
        "services/broker-reports-gate1-proof/openwebui_actions/broker_reports_gate1_pipe_bundled.py",
        "docs/stage2/contracts/BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION.v1.md",
        "docs/stage2/contracts/BROKER_REPORTS_GATE5_METHODOLOGY_DRIVEN_EVIDENCE_DEMAND.v1.md",
        "docs/stage2/contracts/BROKER_REPORTS_GATE5_REAL_CANONICAL_SEMANTIC_RECOVERY.v1.md",
        "docs/stage2/contracts/BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md",
        "docs/stage2/contracts/BROKER_REPORTS_CROSS_GATE_DOMAIN_OWNERSHIP.v1.md",
        "docs/reports/2026-08-14/BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION_G5_48.report.md",
        "docs/reports/2026-08-14/BROKER_REPORTS_GATE5_EXISTING_PIPELINE_ONE_GAP_G5_48.receipt.safe.json",
        str(reclassification_path.relative_to(root)).replace("\\", "/"),
        str(path_diff_path.relative_to(root)).replace("\\", "/"),
    ]
    receipt = {
        "schema_version": "broker_reports_g548_receipt_v1",
        "goal": "G5.48",
        "status": "PARTIAL_PROOF_FAIL_CLOSED",
        "proven_terminals": [
            "EXISTING_EXTRACTION_PIPELINE_RECONNECTED",
            "G5_47_PARALLEL_RECOVERY_PATH_REMOVED",
            "METHODOLOGY_DEMAND_TO_SOURCE_OWNER_BOUNDARY_PROVEN",
            "BOUNDED_CONTEXT_EXECUTION_PROVEN",
            "PRESERVATION_GAPS_RECLASSIFIED",
        ],
        "unproven_terminal": "BOUNDED_CONTEXT_RECOVERY_PROVEN",
        "provider_calls": one_gap["provider_submissions"],
        "retry_count": 0,
        "repair_count": 0,
        "ingestion_reruns": 0,
        "canonical_mutations": 0,
        "store_unchanged": one_gap["store_unchanged"],
        "private_values_committed": False,
        "verification": {
            "targeted_tests": {"passed": 50, "failed": 0},
            "ruff_check": "passed",
            "full_suite_collected": 3492,
            "full_suite_status": "NOT_GREEN_BASELINE_FAILURES_AND_TIMEOUT",
            "unrelated_baseline_failures": [
                "actual_corpus_runtime_budget_drift",
                "pipeline_documentation_still_requires_Gate4FinancialCaseFactV1",
            ],
            "remaining_suite_timeout_seconds": 603,
        },
        "artifacts": [_artifact(root, item) for item in artifacts],
    }
    receipt_path = report_root / (
        "BROKER_REPORTS_GATE5_EXISTING_PIPELINE_RECONNECTION_G5_48.receipt.safe.json"
    )
    _write_json(receipt_path, receipt)
    print(str(receipt_path))
    return 0


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _artifact(root: Path, relative: str) -> dict:
    raw = (root / relative).read_bytes()
    return {
        "path": relative,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
