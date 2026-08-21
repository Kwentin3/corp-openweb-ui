from __future__ import annotations

import copy
import inspect
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from broker_reports_gate1.gate4_ordinary_trade_candidate import (
    FORBIDDEN as GATE4_FORBIDDEN,
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_candidate_runtime import (
    OrdinaryTradeCandidateRuntimeFactory,
)
from broker_reports_gate1.gate5_trusted_methodology import (
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    OrdinaryTradeSemanticCompilerError,
    OrdinaryTradeSemanticCompilerFactory,
    compile_schema_mapping,
)
from broker_reports_gate1.canonical_store import CanonicalReaderFactory

import test_broker_reports_gate4_sql_materialization as gate4_fixtures


_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONTRACTS = _REPO_ROOT / "docs" / "stage2" / "contracts"
_FACT_SCHEMA = json.loads(
    (_CONTRACTS / "BROKER_REPORTS_GATE4_FINANCIAL_CASE_FACT.v2.schema.json")
    .read_text(encoding="utf-8")
)
_TARGET_SCHEMA = json.loads(
    (_CONTRACTS / "BROKER_REPORTS_GATE3_TARGET.v1.schema.json").read_text(
        encoding="utf-8"
    )
)
_FACT_VALIDATOR = Draft202012Validator(
    _FACT_SCHEMA,
    registry=Registry().with_resource(
        _TARGET_SCHEMA["$id"], Resource.from_contents(_TARGET_SCHEMA)
    ),
)


_ROWS = (
    (
        "Asset",
        "Trade date",
        "Side",
        "Quantity",
        "Price",
        "Currency",
        "Gross",
        "Broker commission",
        "Settlement commission",
    ),
    ("ACME", "01.01.2026 10:00:00", "Buy", "10", "10.00", "RUB", "100.00", "0", "0"),
    ("ACME", "02.02.2026 11:00:00", "Sell", "4", "15.00", "RUB", "60.00", "1.00", "2.00"),
)
_ROLES = (
    "asset_name",
    "trade_date",
    "side",
    "quantity",
    "unit_price",
    "currency",
    "gross_amount",
    "broker_commission",
    "broker_commission",
)


def test_candidate_reaches_unchanged_gate5_and_is_exactly_repeatable(
    tmp_path: Path,
) -> None:
    store, context, document_id, mapping = _case(tmp_path)
    projections = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create()

    first = projections.compile_and_save(
        document_id=document_id, mappings=[mapping], context=context
    )
    second = projections.compile_and_save(
        document_id=document_id, mappings=[copy.deepcopy(mapping)], context=context
    )

    assert second.artifact_id == first.artifact_id
    projection = projections.read(artifact_id=first.artifact_id, context=context)
    assert projection["mapping_matches"] == [
        {"mapping_id": mapping["mapping_id"], "matched_tables": 1}
    ]
    assert [item["disposition"] for item in projection["source_observations"]] == [
        "RUNTIME_READY",
        "RUNTIME_READY",
    ]
    assert len(projection["runtime_records"]) == 4
    assert all(
        role["source_binding"]["source_literal"]
        for record in projection["runtime_records"]
        for role in record["roles"]
    )

    gate4 = Gate4OrdinaryTradeCandidateRuntimeFactory(
        store=store, read_enabled=True
    ).create()
    facts_first = gate4.list_facts(context=context)
    facts_second = gate4.list_facts(context=context)
    assert json.dumps(facts_first, sort_keys=True) == json.dumps(
        facts_second, sort_keys=True
    )
    assert len({item["fact_id"] for item in facts_first}) == 4
    for fact in facts_first:
        _FACT_VALIDATOR.validate(fact)
    assert [item["financial_type"] for item in facts_first] == [
        "SECURITY_PURCHASE",
        "SECURITY_DISPOSAL",
        "TRANSACTION_CHARGE",
        "TRANSACTION_CHARGE",
    ]
    assert all(
        item["gate3_binding"]["financial_annotations_artifact_id"]
        == first.artifact_id
        for item in facts_first
    )

    consumed = OrdinaryTradeCandidateRuntimeFactory(
        store=store, read_enabled=True
    ).create().run(methodology_ref=_methodology_ref(), context=context)
    disposal = consumed["securities"][0]
    assert disposal["gross_income"]["value"] == {
        "kind": "money",
        "amount": "60.00",
        "currency": "RUB",
    }
    assert disposal["recognized_acquisition_cost"]["value"]["amount"] == "40.00"
    assert disposal["direct_transaction_expense"]["value"]["amount"] == "3.00"


def test_equal_source_values_remain_distinct_observations(tmp_path: Path) -> None:
    store, context, document_id, mapping = _case(
        tmp_path,
        rows=(*_ROWS, _ROWS[-1]),
    )
    projection = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().compile_and_save(
        document_id=document_id, mappings=[mapping], context=context
    )
    payload = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().read(artifact_id=projection.artifact_id, context=context)

    ready = [
        item
        for item in payload["source_observations"]
        if item["disposition"] == "RUNTIME_READY"
    ]
    assert len(ready) == 3
    assert len({item["observation_id"] for item in ready}) == 3
    assert ready[1]["fields"] != ready[2]["fields"]


def test_changed_or_unknown_schema_fails_closed_without_blocking_known_table(
    tmp_path: Path,
) -> None:
    changed = tuple(
        ("Different asset header", *row[1:]) if index == 0 else row
        for index, row in enumerate(_ROWS)
    )
    store, context, document_id, _changed_mapping = _case(tmp_path, rows=changed)
    mapping = _mapping_from_headers(_ROWS[0])
    runtime = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create()

    record = runtime.compile_and_save(
        document_id=document_id, mappings=[mapping], context=context
    )
    projection = runtime.read(artifact_id=record.artifact_id, context=context)
    assert projection["runtime_records"] == []
    assert projection["source_observations"]
    assert {
        item["disposition"] for item in projection["source_observations"]
    } == {"RELEVANT_UNMAPPED"}
    assert {
        item["reason_code"] for item in projection["source_observations"]
    } == {"UNKNOWN_STRUCTURAL_FINGERPRINT"}


def test_table_local_numeric_convention_handles_grouped_integer_quantity(
    tmp_path: Path,
) -> None:
    rows = (
        _ROWS[0],
        (
            "ACME",
            "01.01.2026 10:00:00",
            "Buy",
            "1,160,000",
            "1.00",
            "RUB",
            "1,160,000.00",
            "0",
            "0",
        ),
    )
    store, context, document_id, mapping = _case(tmp_path, rows=rows)
    runtime = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create()
    record = runtime.compile_and_save(
        document_id=document_id, mappings=[mapping], context=context
    )
    projection = runtime.read(artifact_id=record.artifact_id, context=context)
    security = projection["runtime_records"][0]
    quantity = next(item for item in security["roles"] if item["role"] == "quantity")
    assert quantity["value"] == "1160000"
    assert quantity["source_binding"]["source_literal"] == "1,160,000"
    assert quantity["source_binding"]["deterministic_transform"] == (
        "SOURCE_DECIMAL_TO_CANONICAL_DECIMAL"
    )


def test_mapping_contract_rejects_profile_keys_and_header_reorder() -> None:
    mapping = _mapping_from_headers(_ROWS[0])
    with pytest.raises(OrdinaryTradeSemanticCompilerError) as reordered:
        compile_schema_mapping(
            title_literal=None,
            headers=[
                {"column": index, "literal": literal}
                for index, literal in enumerate(_ROWS[0], start=1)
            ],
            model_columns=list(
                reversed(
                    [
                        {"column": index, "semantic_role": role}
                        for index, role in enumerate(_ROLES, start=1)
                    ]
                )
            ),
            side_values=mapping["side_values"],
            semantic_decisions=mapping["semantic_decisions"],
        )
    assert reordered.value.code == "ordinary_trade_mapping_header_order"

    profile = copy.deepcopy(mapping)
    profile["broker"] = "synthetic"
    canonical = {
        "canonical_root_hash": "a" * 64,
        "source": {"source_artifact_ref": "source", "source_sha256": "b" * 64},
        "nodes": [],
    }
    with pytest.raises(OrdinaryTradeSemanticCompilerError) as forbidden:
        OrdinaryTradeSemanticCompilerFactory.create().compile(
            canonical=canonical,
            canonical_binding={
                "document_id": "document",
                "canonical_version_id": "version",
                "canonical_root_sha256": "a" * 64,
                "source_artifact_ref": "source",
                "source_sha256": "b" * 64,
            },
            mappings=[profile],
        )
    assert forbidden.value.code == "ordinary_trade_mapping_contract_invalid"


def test_candidate_fact_adapter_has_no_forbidden_owners() -> None:
    source = inspect.getsource(Gate4OrdinaryTradeCandidateRuntimeFactory)
    composition = inspect.getsource(OrdinaryTradeCandidateRuntimeFactory)
    assert "CanonicalReader" not in source
    assert "sqlite3" not in source
    assert "LLM" not in source
    assert "CanonicalReader" not in composition
    assert "LLM" not in composition
    assert "second SQL cache" in GATE4_FORBIDDEN


def _case(tmp_path: Path, *, rows: tuple = _ROWS):
    store, context = gate4_fixtures._store_context(tmp_path)
    document_id = "ordinary-trade-candidate-document"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_rows=rows,
    )
    envelope = CanonicalReaderFactory(
        store=store, read_enabled=True
    ).create().read_active_envelope(document_id, context)
    table = next(
        item for item in envelope.artifact["nodes"] if item["node_type"] == "TABLE"
    )
    header_cells = sorted(
        (
            item
            for item in table["content"]["cells"]
            if item["row"] == 1
        ),
        key=lambda item: item["column"],
    )
    mapping = _mapping_from_headers(
        tuple(item["displayed_value"] for item in header_cells)
    )
    return store, context, document_id, mapping


def _mapping_from_headers(headers: tuple[str, ...]) -> dict:
    return compile_schema_mapping(
        title_literal=None,
        headers=[
            {"column": index, "literal": literal}
            for index, literal in enumerate(headers, start=1)
        ],
        model_columns=[
            {"column": index, "semantic_role": role}
            for index, role in enumerate(_ROLES, start=1)
        ],
        side_values=[
            {"source_literal": "Buy", "normalized_value": "PURCHASE"},
            {"source_literal": "Sell", "normalized_value": "DISPOSAL"},
        ],
        semantic_decisions=[
            {
                "decision_id": "decision-schema",
                "decision_kind": "SCHEMA_MAPPING",
                "model_id": "model-test",
                "response_sha256": "a" * 64,
            },
            {
                "decision_id": "decision-side",
                "decision_kind": "SIDE_ENUM",
                "model_id": "model-test",
                "response_sha256": "b" * 64,
            },
        ],
    )


def _methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
        "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    }
