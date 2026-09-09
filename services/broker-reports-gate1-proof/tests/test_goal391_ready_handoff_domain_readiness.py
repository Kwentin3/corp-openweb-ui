from __future__ import annotations

import pytest

from broker_reports_gate1.domain_ingestion import (
    build_document_usage_classification,
    build_domain_context_packet,
)
from broker_reports_gate1.contracts import ready_gate2_handoff_document_ids


@pytest.mark.parametrize(
    ("status", "mode"),
    [
        ("ready_with_safe_refs", "full_package_ready_for_gate2"),
        ("ready_with_reduced_subset", "reduced_subset_ready_for_gate2"),
    ],
)
def test_ready_gate1_handoff_overrides_only_stale_readability_for_its_selected_document(
    status: str, mode: str
) -> None:
    """A ready Full/Reduced Source contract must not be contradicted downstream."""

    document_id = "doc_selected_by_gate1"
    package = {
        "normalization_run": {
            "run_id": "normrun_ready_handoff",
            "gate2_handoff_status": status,
            "gate2_handoff_mode": mode,
        },
        "gate2_handoff": {
            "gate2_handoff_status": status,
            "handoff_mode": mode,
            "included_document_ids": [document_id],
        },
        "document_inventory": {
            "documents": [
                {
                    "document_id": document_id,
                    "container_format": "pdf",
                    "bytes_status": "unavailable",
                    "readable": "no",
                    "read_error_class": "bytes_unavailable",
                }
            ]
        },
        "taxonomy_candidates": [
            {
                "document_id": document_id,
                "document_class_candidate": "source_broker_report",
            }
        ],
        "document_source_eligibility": {
            "entries": [
                {
                    "document_id": document_id,
                    "source_eligibility": "accepted_for_gate2",
                    "included_in_reduced_subset": True,
                }
            ]
        },
        "safe_artifact_refs": {},
    }
    ledger = {
        "schema_version": "gate1_issue_ledger_v0",
        "issue_ledger_id": "issueledger_stale_readability",
        "entries": [
            {
                "issue_id": "issue_stale_readability",
                "issue_type": "readability_blocker",
                "status": "unresolved",
                "target_document_refs": [document_id],
                "blocked_stages": ["source_fact_extraction"],
            }
        ],
    }

    usage = build_document_usage_classification(package, ledger)
    entry = usage["entries"][0]
    packet = build_domain_context_packet(package, ledger, usage)

    assert entry["readiness_by_stage"]["source_fact_extraction"] == "ready_with_issues"
    assert entry["private_payload_access"] == "resolver_required"
    assert entry["deterministic_basis"]["gate1_handoff_source_ready"] is True
    assert packet["stage_readiness"]["source_fact_extraction"] == "ready_with_issue_context"
    assert packet["next_stage_refs"]["source_fact_ready_refs"] == [document_id]


def test_conflicting_handoff_receipts_do_not_create_a_domain_ready_override() -> None:
    assert not ready_gate2_handoff_document_ids(
        normalization_run={
            "gate2_handoff_status": "ready_with_safe_refs",
            "gate2_handoff_mode": "full_package_ready_for_gate2",
        },
        handoff={
            "gate2_handoff_status": "ready_with_reduced_subset",
            "handoff_mode": "reduced_subset_ready_for_gate2",
            "included_document_ids": ["doc_foreign"],
        },
    )
