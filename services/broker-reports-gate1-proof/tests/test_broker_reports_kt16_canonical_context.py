from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
DOC_ROOT = REPO_ROOT / "docs" / "stage2"
CURRENT_STATE_PATH = DOC_ROOT / "BROKER_REPORTS_CURRENT_STATE.v1.json"
CURRENT_STATE_GUIDE_PATH = DOC_ROOT / "BROKER_REPORTS_CURRENT_STATE.v1.md"
DEBT_REGISTER_PATH = DOC_ROOT / "BROKER_REPORTS_DEBT_REGISTER.v1.json"
SKIP_AUDIT_PATH = DOC_ROOT / "BROKER_REPORTS_SKIP_AUDIT.v1.json"
EVIDENCE_INDEX_PATH = DOC_ROOT / "BROKER_REPORTS_EVIDENCE_INDEX.v1.md"
BENCHMARK_TEST_PATH = (
    SERVICE_ROOT / "tests" / "test_broker_reports_pdf_table_strategy_benchmark.py"
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_integrity(payload: dict[str, Any]) -> str:
    material = copy.deepcopy(payload)
    material.pop("integrity_sha256")
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_current_state_is_short_terminal_and_integrity_bound() -> None:
    state = _read_json(CURRENT_STATE_PATH)
    guide = CURRENT_STATE_GUIDE_PATH.read_text(encoding="utf-8")

    assert state["schema_version"] == "broker_reports_current_state_v1"
    assert state["integrity_sha256"] == _canonical_integrity(state)
    assert state["repository_debt"] == "CLOSED"
    assert state["live_parity_debt"] == "CLOSED"
    assert state["decision_gate_1"] == "CLOSED"
    assert state["kt2_status"] == "NOT_STARTED"
    assert state["kt2_ready"] is True
    assert state["open_blocking_debts"] == []
    assert len(guide.split()) <= 2500
    assert "KT2_READY = TRUE" in guide
    assert "KT2_STARTED = FALSE" in guide


def test_every_canonical_document_is_present() -> None:
    state = _read_json(CURRENT_STATE_PATH)

    missing = [
        path
        for path in state["canonical_documents"]
        if not (REPO_ROOT / path).is_file()
    ]
    assert missing == []


def test_debt_register_has_no_unknown_unowned_or_kt2_blocker() -> None:
    register = _read_json(DEBT_REGISTER_PATH)
    summary = register["summary"]
    debts = register["debts"]

    assert register["integrity_sha256"] == _canonical_integrity(register)
    assert summary == {
        "debts_total": len(debts),
        "unknown_debts_total": 0,
        "unowned_debts_total": 0,
        "kt2_blocking_debts_total": 0,
    }
    assert len({debt["debt_id"] for debt in debts}) == len(debts)
    required = {
        "debt_id",
        "title",
        "domain",
        "owner",
        "status",
        "severity",
        "blocks_kt2",
        "evidence",
        "reason_not_blocking_kt2",
        "resolution_or_trigger",
    }
    for debt in debts:
        assert required <= set(debt)
        assert debt["owner"]
        assert debt["blocks_kt2"] is False
        assert debt["reason_not_blocking_kt2"]
        assert debt["resolution_or_trigger"]
        assert "UNKNOWN" not in debt["status"]

    registered_ids = {debt["debt_id"] for debt in debts}
    state = _read_json(CURRENT_STATE_PATH)
    assert set(state["non_blocking_debts"]) <= registered_ids


def test_all_original_skips_are_classified_and_remove_now_is_fixed() -> None:
    audit = _read_json(SKIP_AUDIT_PATH)
    summary = audit["summary"]
    records = audit["records"]

    assert audit["integrity_sha256"] == _canonical_integrity(audit)
    assert len(records) == summary["original_skips_total"] == 23
    assert len({record["test"] for record in records}) == 23
    assert summary["remove_now_total"] == 18
    assert summary["remove_now_fixed_total"] == 18
    assert summary["final_skips_total"] == 5
    assert summary["new_skips_total"] == 0
    assert summary["unclassified_skips_total"] == 0
    assert summary["unjustified_kt2_blocking_skips_total"] == 0

    allowed = {
        "JUSTIFIED_CONDITIONAL_SKIP",
        "HISTORICAL_GUARD",
        "PLATFORM_UNAVAILABLE",
        "TEST_DEBT",
        "REMOVE_NOW",
    }
    for record in records:
        assert record["classification"] in allowed
        assert record["owner"]
        assert record["blocks_kt2"] is False
        test_path, *qualname = record["test"].split("::")
        source_path = SERVICE_ROOT / test_path
        assert source_path.is_file()
        assert qualname[-1] in source_path.read_text(encoding="utf-8")
        if record["classification"] == "REMOVE_NOW":
            assert record["final_state"] == "RUNS_UNCONDITIONALLY"


def test_private_reference_skip_is_narrowed_to_two_methods() -> None:
    tree = ast.parse(BENCHMARK_TEST_PATH.read_text(encoding="utf-8"))
    test_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "BrokerReportsPdfTableStrategyBenchmarkTests"
    )
    assert test_class.decorator_list == []

    skipped_methods = {
        node.name
        for node in test_class.body
        if isinstance(node, ast.FunctionDef)
        and any(
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr == "skipUnless"
            for decorator in node.decorator_list
        )
    }
    assert skipped_methods == {
        "test_frozen_manifest_and_reference_have_exact_scope_and_hash_binding",
        "test_scorer_minimal_smoke_uses_tracked_reference_after_seal",
    }


def test_historical_evidence_is_present_and_receipts_are_intact() -> None:
    goal18_root = REPO_ROOT / "docs" / "reports" / "2026-07-30"
    goal18_files = [
        "BROKER_REPORTS_GATE2_PIPELINE_RECONCILIATION_AUDIT_GOAL18.report.md",
        "BROKER_REPORTS_GATE2_PIPELINE_RECONCILIATION_AUDIT_GOAL18.receipt.safe.json",
        "BROKER_REPORTS_GATE2_PIPELINE_RECONCILIATION_DECISION_BRIEF.md",
    ]
    assert all((goal18_root / name).is_file() for name in goal18_files)
    goal18_receipt = _read_json(goal18_root / goal18_files[1])
    assert goal18_receipt["integrity_sha256"] == _canonical_integrity(
        goal18_receipt
    )

    kt15_receipt = _read_json(
        REPO_ROOT
        / "docs"
        / "reports"
        / "2026-07-31"
        / "BROKER_REPORTS_KT15_FINAL_AUTHORITY_CLOSURE.receipt.safe.json"
    )
    assert kt15_receipt["integrity_sha256"] == _canonical_integrity(kt15_receipt)
    assert kt15_receipt["live_parity_status"] == "CLOSED"

    pr77_root = REPO_ROOT / "docs" / "reports" / "2026-07-23"
    pr77_names = [
        "BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_FINAL_DECISION.report.md",
        "BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL0_ARCHAEOLOGY.report.md",
        "BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL1_ACTUAL_CORPUS_CONCEPT_INVENTORY.report.md",
        "BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL2_LAYER_MODEL.report.md",
        "BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL3_FACT_REGISTRY_BLUEPRINT.report.md",
        "BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL4_DECISION_CONTRACT_BLUEPRINT.report.md",
        "BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL5_INITIAL_REGISTRY_CANDIDATES.report.md",
        "BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL6_REGISTER_ACCOUNTING_AUDIT.report.md",
        "BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_GOAL7_MIGRATION_ROADMAP.report.md",
        "BROKER_REPORTS_GATE2_CANONICAL_DOMAIN_RESEARCH.receipt.safe.json",
    ]
    assert all((pr77_root / name).is_file() for name in pr77_names)
    assert not (
        pr77_root
        / "BROKER_REPORTS_GATE2_CANONICAL_FACT_REGISTRY_DRAFT.safe.json"
    ).exists()

    evidence_index = EVIDENCE_INDEX_PATH.read_text(encoding="utf-8")
    assert "GOAL18 = HISTORICAL_AUDIT_EVIDENCE" in evidence_index
    assert "current_live_parity = CLOSED_BY_KT1_5" in evidence_index
    assert "HISTORICAL_RESEARCH_SUPERSEDED" in evidence_index
    assert "`REJECT`" in evidence_index


def test_current_route_and_live_status_are_consistent() -> None:
    route = (
        DOC_ROOT
        / "architecture"
        / "BROKER_REPORTS_GATE2_ROUTE_STATUS.v1.md"
    ).read_text(encoding="utf-8")
    owner_context = _read_json(
        DOC_ROOT / "architecture" / "BROKER_REPORTS_OWNER_CONTEXT.v1.json"
    )
    owners = {owner["owner_id"]: owner for owner in owner_context["owners"]}

    assert "route_id=release_live_bundle_state;status=VERIFIED_LIVE" in route
    assert "Debt: `CLOSED_BY_KT1_5`." in route
    assert owners["release_live_parity_verifier"]["runtime_status"] == (
        "VERIFIED_LIVE"
    )
    assert owner_context["program_owner_decisions"]["kt2_authorized"] is True
    subordinate = owners["current_source_fact_orchestration"][
        "inactive_subordinate_capabilities"
    ]
    assert subordinate == [
        {
            "capability_id": "kt2_same_source_type_first_proof",
            "module": (
                "services/broker-reports-gate1-proof/broker_reports_gate1/"
                "gate2_same_source_type_first_proof.py"
            ),
            "symbol": "Gate2SameSourceTypeFirstProof",
            "runtime_status": "PROOF_ONLY",
            "product_reachability": "FORBIDDEN",
            "provider_reachability": "FORBIDDEN",
            "canonical_owner_delta": 0,
            "contract": (
                "docs/stage2/contracts/"
                "BROKER_REPORTS_GATE2_SAME_SOURCE_TYPE_FIRST_PROOF.v1.md"
            ),
        }
    ]
