from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_catalog import (  # noqa: E402
    DEFERRED_CANDIDATE_IDS,
    EVIDENCE_KIND_IDS,
    FNS_SPECIALIZED_SCHEMA_FAMILIES,
    INITIAL_CATALOG_VERSION,
    INITIAL_FINANCIAL_EVIDENCE_DECLARATIONS,
    INITIAL_SEMANTIC_IDENTITY_PINS,
    LEGACY_BROAD_FINANCIAL_IDS,
    LEGACY_TECHNICAL_DISPOSITIONS,
    SUPPORTED_SOURCE_FAMILIES,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    REGISTRY_VERSION_V1,
    Gate2FinancialEvidenceRegistryFactory,
    financial_evidence_semantic_fingerprint,
)
from broker_reports_gate1.gate2_fns_2ndfl_contracts import (  # noqa: E402
    TYPED_FACTS_SCHEMA_VERSION,
)
from broker_reports_gate1.semantic_visual_table_contracts import (  # noqa: E402
    SEMANTIC_LOGICAL_TABLE_PROFILE_ID,
)
from broker_reports_gate1.table_projection import (  # noqa: E402
    TABLE_PROJECTION_SCHEMA_VERSION,
)


EXPECTED_REGISTRY_HASH = (
    "0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8"
)
EXPECTED_ACTIVE_TYPES = (
    "cash_balance_snapshot_v1",
    "printed_financial_metric_v1",
)


def test_initial_catalog_is_small_active_and_deterministic():
    first = Gate2FinancialEvidenceRegistryFactory().create()
    second = Gate2FinancialEvidenceRegistryFactory().create()

    assert INITIAL_CATALOG_VERSION == (
        "broker_reports_gate2_initial_financial_catalog_v1"
    )
    assert first.registry_version == REGISTRY_VERSION_V1
    assert first.registry_hash == EXPECTED_REGISTRY_HASH
    assert second.registry_hash == EXPECTED_REGISTRY_HASH
    assert first.provider_type_enum() == EXPECTED_ACTIVE_TYPES
    assert len(first.declarations) == 2
    assert all(item.lifecycle == "active" for item in first.declarations)


def test_every_active_type_has_safe_corpus_evidence_and_tests():
    for declaration in INITIAL_FINANCIAL_EVIDENCE_DECLARATIONS:
        assert declaration.evidence_refs
        assert declaration.test_refs
        assert any(
            ref.startswith("safe_receipt:")
            for ref in declaration.evidence_refs
        )
        assert any(
            ref.startswith("safe_report:")
            for ref in declaration.evidence_refs
        )
        assert declaration.examples
        assert declaration.counterexamples


def test_semantic_identity_pins_are_literals_and_exact():
    expected = dict(INITIAL_SEMANTIC_IDENTITY_PINS)

    assert set(expected) == set(EXPECTED_ACTIVE_TYPES)
    assert {
        declaration.input_type_id: (
            financial_evidence_semantic_fingerprint(declaration)
        )
        for declaration in INITIAL_FINANCIAL_EVIDENCE_DECLARATIONS
    } == expected


def test_catalog_source_families_are_existing_gate1_contract_ids():
    assert SUPPORTED_SOURCE_FAMILIES == (
        TABLE_PROJECTION_SCHEMA_VERSION,
        SEMANTIC_LOGICAL_TABLE_PROFILE_ID,
    )
    assert all(
        declaration.compatible_source_families
        == SUPPORTED_SOURCE_FAMILIES
        for declaration in INITIAL_FINANCIAL_EVIDENCE_DECLARATIONS
    )


def test_source_labels_router_statuses_and_legacy_ids_are_not_type_ids():
    canonical = set(EXPECTED_ACTIVE_TYPES)
    excluded_namespaces = (
        set(LEGACY_BROAD_FINANCIAL_IDS)
        | set(EVIDENCE_KIND_IDS)
        | set(LEGACY_TECHNICAL_DISPOSITIONS)
        | {
            "cash",
            "total",
            "summary",
            "position",
            "unknown",
            "no_fact",
            "unsupported",
        }
    )

    assert not canonical & excluded_namespaces
    assert set(DEFERRED_CANDIDATE_IDS).isdisjoint(canonical)
    assert all(type_id.endswith("_v1") for type_id in canonical)


def test_deferred_research_candidates_are_not_silently_experimental():
    snapshot = Gate2FinancialEvidenceRegistryFactory().create()
    declared = {
        declaration.input_type_id for declaration in snapshot.declarations
    }

    assert len(DEFERRED_CANDIDATE_IDS) == 10
    assert declared.isdisjoint(DEFERRED_CANDIDATE_IDS)
    assert snapshot.provider_type_enum(include_experimental=True) == (
        EXPECTED_ACTIVE_TYPES
    )


def test_fns_specialized_schema_family_remains_separate():
    snapshot = Gate2FinancialEvidenceRegistryFactory().create()
    declared = {
        declaration.input_type_id for declaration in snapshot.declarations
    }

    assert FNS_SPECIALIZED_SCHEMA_FAMILIES == (
        TYPED_FACTS_SCHEMA_VERSION,
    )
    assert declared.isdisjoint(FNS_SPECIALIZED_SCHEMA_FAMILIES)
    assert all(
        not type_id.startswith("fns_")
        for type_id in declared
    )


def test_printed_metric_is_explicitly_not_a_calculated_aggregate():
    snapshot = Gate2FinancialEvidenceRegistryFactory().create()
    printed = snapshot.get("printed_financial_metric_v1")

    assert "printed" in printed.definition.lower()
    assert "calculated by Gate 2" in printed.definition
    assert "printed_label_evidence_ref" in printed.required_roles
    assert "calculation_method" in printed.forbidden_roles
    assert any(
        "calculated by Gate 2" in item
        for item in printed.counterexamples
    )


def test_cash_balance_does_not_promote_restricted_assets_or_movements():
    snapshot = Gate2FinancialEvidenceRegistryFactory().create()
    cash = snapshot.get("cash_balance_snapshot_v1")

    assert cash.semantic_class == "state"
    assert cash.date_period_requirement == "as_of_date_required"
    assert "event_date" in cash.forbidden_roles
    assert any(
        "segregated" in item.lower()
        for item in cash.counterexamples
    )
    assert any(
        "movement" in item.lower()
        for item in cash.counterexamples
    )
