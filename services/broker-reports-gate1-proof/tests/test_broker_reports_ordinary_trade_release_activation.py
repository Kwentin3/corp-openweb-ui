from __future__ import annotations

import copy
import inspect
from pathlib import Path

from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.ordinary_trade_production_runtime import (
    FORBIDDEN,
    ORDINARY_TRADE_PRODUCTION_ROUTE_ID,
    OrdinaryTradeProductionRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)
from broker_reports_gate1.ordinary_trade_qualified_mappings import (
    OrdinaryTradeQualifiedMappingAuthorityFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    OrdinaryTradeSemanticCompilerFactory,
    compile_schema_mapping,
)

import test_broker_reports_gate4_sql_materialization as gate4_fixtures


_REPO_ROOT = Path(__file__).resolve().parents[3]
_PIPE_SOURCE = (
    _REPO_ROOT
    / "services"
    / "broker-reports-gate1-proof"
    / "openwebui_actions"
    / "broker_reports_gate1_pipe.py"
)


def test_release_route_uses_packaged_exact_mapping_and_reaches_gate5(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    rows = (
        tuple(item["header_literal"] for item in mapping["columns"]),
        tuple(_literal_for_role(item["semantic_role"]) for item in mapping["columns"]),
    )
    document_id = "qualified-ordinary-trade"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=rows,
    )
    version = next(
        item
        for item in store.list_canonical_versions(
            context=context,
            document_id=document_id,
        )
        if item.status == "ACTIVE"
    )
    assert version.manifest_ref
    runtime = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()

    first = runtime.run(
        canonical_artifact_refs=[version.manifest_ref],
        context=context,
    )
    second = runtime.run(canonical_artifact_refs=[], context=context)

    assert first["route_owner"] == ORDINARY_TRADE_PRODUCTION_ROUTE_ID
    assert first["provider_calls_total"] == 0
    assert first["semantic_fallback_used"] is False
    assert first["legacy_fallback_used"] is False
    assert first["documents"][0]["matched_qualified_tables"] == 1
    assert first["product"]["gate4"] == {
        "status": "candidate_projection_facts",
        "facts_total": 3,
        "security_facts_total": 1,
        "transaction_charge_facts_total": 2,
    }
    assert first["system_identity"] == second["system_identity"]


def test_unknown_schema_is_preserved_unmapped_without_semantic_fallback(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    document_id = "unknown-ordinary-trade-shape"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=(("Unknown", "Shape"), ("value", "1")),
    )
    version = next(
        item
        for item in store.list_canonical_versions(
            context=context,
            document_id=document_id,
        )
        if item.status == "ACTIVE"
    )
    result = (
        OrdinaryTradeProductionRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .run(
            canonical_artifact_refs=[str(version.manifest_ref)],
            context=context,
        )
    )
    projection = (
        OrdinaryTradeProjectionFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .current_case(context=context)[0][1]
    )

    assert result["product"]["gate4"]["facts_total"] == 0
    assert result["provider_calls_total"] == 0
    assert result["semantic_fallback_used"] is False
    assert projection["runtime_records"] == []
    assert {item["disposition"] for item in projection["source_observations"]} == {
        "RELEVANT_UNMAPPED"
    }


def test_missing_canonical_stops_without_old_semantic_fallback(tmp_path: Path) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    result = (
        OrdinaryTradeProductionRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .run(canonical_artifact_refs=[], context=context)
    )

    assert result["status"] == "blocked"
    assert result["provider_calls_total"] == 0
    assert result["semantic_fallback_used"] is False
    assert result["product"]["terminal"] == (
        "ordinary_trade_canonical_evidence_missing"
    )
    assert result["product"]["gate4"]["facts_total"] == 0


def test_supported_table_survives_unknown_table_in_same_canonical(tmp_path: Path) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    rows = (
        tuple(item["header_literal"] for item in mapping["columns"]),
        tuple(_literal_for_role(item["semantic_role"]) for item in mapping["columns"]),
    )
    document_id = "supported-with-unknown"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=rows,
    )
    envelope = (
        CanonicalReaderFactory(store=store, read_enabled=True)
        .create()
        .read_active_envelope(document_id, context)
    )
    canonical = copy.deepcopy(envelope.artifact)
    known = next(item for item in canonical["nodes"] if item["node_type"] == "TABLE")
    unknown = copy.deepcopy(known)
    unknown["node_id"] = "node_unknown_operation_table"
    unknown["content"]["cells"][0]["displayed_value"] = "Unknown operation"
    canonical["nodes"].append(unknown)
    projection = OrdinaryTradeSemanticCompilerFactory.create().compile(
        canonical=canonical,
        canonical_binding={
            "document_id": document_id,
            "canonical_version_id": envelope.canonical_version_id,
            "canonical_root_sha256": envelope.canonical_root_sha256,
            "source_artifact_ref": canonical["source"]["source_artifact_ref"],
            "source_sha256": canonical["source"]["source_sha256"],
        },
        mappings=[mapping],
    )

    assert sum(
        item["disposition"] == "RUNTIME_READY"
        for item in projection["source_observations"]
    ) == 1
    assert sum(
        item["disposition"] == "RELEVANT_UNMAPPED"
        for item in projection["source_observations"]
    ) == 2
    assert len(projection["runtime_records"]) == 3


def test_charge_identity_is_bound_to_exact_commission_cell_and_trade_row(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    rows = (
        tuple(item["header_literal"] for item in mapping["columns"]),
        tuple(_literal_for_role(item["semantic_role"]) for item in mapping["columns"]),
    )
    document_id = "charge-binding"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=rows,
    )
    version = next(
        item
        for item in store.list_canonical_versions(
            context=context,
            document_id=document_id,
        )
        if item.status == "ACTIVE"
    )
    OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().run(
        canonical_artifact_refs=[str(version.manifest_ref)],
        context=context,
    )
    projection = (
        OrdinaryTradeProjectionFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .current_case(context=context)[0][1]
    )
    observation = projection["source_observations"][0]
    records = projection["runtime_records"]
    trade = next(
        item for item in records if item["record_type"].startswith("SECURITY_")
    )
    charges = [item for item in records if item["record_type"] == "TRANSACTION_CHARGE"]

    assert len(charges) == 2
    assert len({item["claim_refs"][0] for item in charges}) == 2
    for charge in charges:
        amount = next(item for item in charge["roles"] if item["role"] == "amount")
        source_ref = amount["source_binding"]["source_ref"]
        source_field = next(
            item for item in observation["fields"] if item["source_ref"] == source_ref
        )
        assert charge["claim_refs"] == [source_ref]
        assert amount["source_binding"]["source_literal"] == source_field["literal"]
        assert (
            amount["source_binding"]["canonical_cell"] == source_field["canonical_cell"]
        )
        assert charge["source_observation_id"] == trade["source_observation_id"]
        assert charge["annotation_target"] == trade["annotation_target"]


def test_semantic_decision_execution_order_does_not_change_mapping_identity() -> None:
    mapping = OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()[0]
    kwargs = {
        "title_literal": mapping["title_literal"],
        "headers": [
            {"column": item["column"], "literal": item["header_literal"]}
            for item in mapping["columns"]
        ],
        "model_columns": [
            {"column": item["column"], "semantic_role": item["semantic_role"]}
            for item in mapping["columns"]
        ],
        "amount_currency_bindings": mapping["amount_currency_bindings"],
        "side_values": mapping["side_values"],
    }
    reordered = compile_schema_mapping(
        **kwargs,
        semantic_decisions=list(reversed(mapping["semantic_decisions"])),
    )
    assert reordered == mapping


def test_production_factory_is_the_only_candidate_route_and_has_no_old_owner() -> None:
    source = inspect.getsource(OrdinaryTradeProductionRuntimeFactory)
    pipe = _PIPE_SOURCE.read_text(encoding="utf-8")
    assert "Gate3" not in source
    assert "FinancialAnnotationsV2" not in source
    assert "Gate4FinancialCaseRuntimeFactory" not in source
    assert "semantic fallback" in FORBIDDEN
    assert pipe.index("if candidate_enabled:") < pipe.index(
        "Gate2StructuredModelClientFactory("
    )


def test_qualified_mapping_authority_is_immutable_and_has_no_profile_keys() -> None:
    authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
    first = authority.list_mappings()
    second = authority.list_mappings()
    first[0]["columns"][0]["header_literal"] = "mutated"
    assert second == authority.list_mappings()
    assert all(
        not {"broker", "broker_id", "year", "filename", "profile"} & set(item)
        for item in second
    )


def _literal_for_role(role: str) -> str:
    return {
        "trade_date": "01.02.2026 10:00:00",
        "settlement_date": "03.02.2026",
        "trade_time": "10:00:00",
        "asset_name": "ACME",
        "security_code": "RU0000000000",
        "currency": "RUB",
        "side": "Продажа",
        "quantity": "2",
        "unit_price": "10.00",
        "gross_amount": "20.00",
        "accrued_interest": "0",
        "broker_commission": "1.00",
        "exchange_commission": "2.00",
        "trade_id": "trade-1",
        "comment": "",
        "status": "Исполнена",
        "unmapped": "",
        "venue": "MOEX",
    }[role]
