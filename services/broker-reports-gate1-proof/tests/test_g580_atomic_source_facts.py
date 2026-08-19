from __future__ import annotations

from pathlib import Path

from broker_reports_gate1.gate4_financial_case_materialization import (
    gate4_annotation_materialization_decision,
)
from broker_reports_gate1.gate3_role_labeling import Gate3RoleValueResolverFactory


REPO_ROOT = Path(__file__).resolve().parents[3]


def _annotation(*, target: dict, status: str) -> dict:
    return {
        "target": target,
        "financial_label": "SECURITY_PURCHASE",
        "roles": [
            {"role": "date", "status": status},
            {"role": "asset", "status": status},
        ],
    }


def test_coarse_roleless_presence_does_not_materialize_as_transaction() -> None:
    decision = gate4_annotation_materialization_decision(
        _annotation(target={"kind": "node", "node_id": "coarse-page"}, status="missing")
    )

    assert decision == {
        "materializable": False,
        "reason_code": "non_atomic_region_presence_only",
    }


def test_exact_incomplete_row_remains_a_legitimate_source_fact() -> None:
    decision = gate4_annotation_materialization_decision(
        _annotation(
            target={
                "kind": "table_cell",
                "node_id": "redemption-table",
                "row": 5,
                "column": 4,
            },
            status="missing",
        )
    )

    assert decision == {
        "materializable": True,
        "reason_code": "atomic_source_assertion",
    }


def test_bound_literal_does_not_make_a_coarse_region_atomic() -> None:
    decision = gate4_annotation_materialization_decision(
        _annotation(target={"kind": "node", "node_id": "exact-line"}, status="bound")
    )

    assert decision["materializable"] is False


def test_structurally_qualified_single_line_node_remains_materializable() -> None:
    decision = gate4_annotation_materialization_decision(
        _annotation(target={"kind": "node", "node_id": "exact-line"}, status="missing"),
        structurally_atomic_target=True,
    )

    assert decision == {
        "materializable": True,
        "reason_code": "atomic_source_assertion",
    }


def test_unique_bound_literal_can_anchor_a_multiline_region() -> None:
    decision = gate4_annotation_materialization_decision(
        _annotation(target={"kind": "node", "node_id": "region"}, status="bound"),
        structurally_atomic_target=False,
        unambiguous_literal_anchor=True,
    )

    assert decision == {
        "materializable": True,
        "reason_code": "atomic_source_assertion",
    }


def test_literal_anchor_must_be_unique_inside_its_canonical_target() -> None:
    resolver = Gate3RoleValueResolverFactory.create(
        canonical_artifact={
            "nodes": [
                {
                    "node_id": "region",
                    "node_type": "TEXT",
                    "content": {"text": "same\nsame\nunique-amount"},
                }
            ],
            "provenance": [],
        }
    )
    repeated = {
        "roles": [
            {
                "role": "asset",
                "status": "bound",
                "target": {"kind": "node", "node_id": "region"},
                "exact_text": "same",
            }
        ]
    }
    unique = {
        "roles": [
            *repeated["roles"],
            {
                "role": "amount",
                "status": "bound",
                "target": {"kind": "node", "node_id": "region"},
                "exact_text": "unique-amount",
            },
        ]
    }

    assert resolver.has_unambiguous_literal_anchor(repeated) is False
    assert resolver.has_unambiguous_literal_anchor(unique) is True


def test_contracts_freeze_atomicity_and_development_only_visual_oracle() -> None:
    gate3 = (
        REPO_ROOT
        / "docs/stage2/contracts/BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md"
    ).read_text(encoding="utf-8")
    gate4 = (
        REPO_ROOT
        / "docs/stage2/contracts/BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.md"
    ).read_text(encoding="utf-8")
    architecture = (
        REPO_ROOT
        / "docs/stage2/contracts/BROKER_REPORTS_PIPELINE_GATES.v1.md"
    ).read_text(encoding="utf-8")

    assert "Atomic annotation boundary" in gate3
    assert "one source assertion whose occurrence is" in gate3
    assert "non_atomic_region_presence_only" in gate4
    compact_architecture = " ".join(architecture.split())
    assert "Development visual qualification" in compact_architecture
    assert "development/test oracle only" in compact_architecture
    assert "must never be copied into production facts" in compact_architecture
