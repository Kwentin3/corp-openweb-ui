from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.gate4_ordinary_trade_candidate import (
    Gate4OrdinaryTradeCandidateRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_grouped_mapping_v18 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V18_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV18AdapterFactory,
)
from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    SOURCE_BOUND_OPEN_SHORT_MAPPING_CONTRACT,
    compile_schema_mapping,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingError,
    OrdinaryTradeSemanticMappingFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_ordinary_trade_production_candidate as candidate


def _v18_response(*, table: dict, mapping: dict) -> dict:
    response = case_fixtures._complete(table, mapping)
    response["schema_version"] = ORDINARY_TRADE_GROUPED_MAPPING_V18_RESPONSE_SCHEMA_VERSION
    decision = response["table_decisions"][0]
    del decision["row_dispositions"]
    decision["row_policy"] = {
        "default_disposition": "SECURITY_TRADES",
        "exception_rows": [],
    }
    response["explicit_header_source_claims"] = {
        "schema_version": (
            "broker_reports_ordinary_trade_explicit_header_source_response_v1"
        ),
        "claims": [],
    }
    return response


def _short_case(tmp_path, *, short_literal: str = "Open short sale"):
    headers = list(candidate._ROWS[0])
    # Keep this as an unknown schema so the fixture's frozen known mapping
    # cannot be a second authority for the V18 qualified candidate.
    headers[0] = headers[0] + " (v18 qualified source)"
    rows = (
        tuple(headers),
        candidate._source_row(
            side="Buy", quantity="10", unit_price="10.00", gross="100.00", broker="0", exchange="0"
        ),
        candidate._source_row(
            side=short_literal, quantity="4", unit_price="15.00", gross="60.00", broker="1.00", exchange="2.00"
        ),
    )
    store, context, document_id, _ignored_mapping = candidate._case(tmp_path, rows=rows)
    envelope = candidate.CanonicalReaderFactory(store=store, read_enabled=True).create().read_active_envelope(
        document_id, context
    )
    table = next(node for node in envelope.artifact["nodes"] if node["node_type"] == "TABLE")
    mapping = compile_schema_mapping(
        title_literal=None,
        headers=[
            {"column": index, "literal": literal}
            for index, literal in enumerate(rows[0], start=1)
        ],
        model_columns=[
            {"column": index, "semantic_role": role}
            for index, role in enumerate(candidate._ROLES, start=1)
        ],
        amount_currency_bindings=copy.deepcopy(candidate._QUALIFIED_MAPPING["amount_currency_bindings"]),
        side_values=[
            {"source_literal": "Buy", "normalized_value": "PURCHASE"},
            {
                "source_literal": short_literal,
                "normalized_value": "DISPOSAL",
                "position_effect": "OPEN_SHORT",
                "position_effect_evidence": {
                    "source_row": 3,
                    "source_column": 7,
                    "source_literal": short_literal,
                },
            },
        ],
        qualification_ref=copy.deepcopy(candidate._QUALIFIED_MAPPING["qualification_ref"]),
        position_effect_contract=SOURCE_BOUND_OPEN_SHORT_MAPPING_CONTRACT,
    )
    binding = {
        "document_id": envelope.document_id,
        "canonical_version_id": envelope.canonical_version_id,
        "canonical_root_sha256": envelope.canonical_root_sha256,
        "source_artifact_ref": envelope.artifact["source"]["source_artifact_ref"],
        "source_sha256": envelope.artifact["source"]["source_sha256"],
    }
    return store, context, document_id, envelope.artifact, binding, table, mapping


def _complete_and_save(tmp_path, *, mutation=None, short_literal: str = "Open short sale"):
    store, context, document_id, canonical, binding, table, mapping = _short_case(
        tmp_path, short_literal=short_literal
    )
    response = _v18_response(table=table, mapping=mapping)
    if mutation is not None:
        mutation(response)
    expanded = OrdinaryTradeGroupedMappingV18AdapterFactory.create().expand_to_v13(
        response=response,
        package=OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
            canonical=canonical, confirmed_understandings=[]
        ),
    )
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    outcome = OrdinaryTradeSemanticMappingFactory.create().validate_mapping_response(
        response=expanded,
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=case_fixtures._metadata(),
        confirmed_understandings=[],
        user_scope_sha256=cases.case_binding(document_id=document_id, context=context)[
            "user_scope_sha256"
        ],
        allow_source_bound_position_effect=True,
    )
    cases.save_mapping_outcome(
        document_id=document_id,
        context=context,
        outcome=outcome,
        provider_calls_total=1,
    )
    return store, context, document_id, outcome


def test_v18_schema_has_closed_optional_effect_only_on_side_values() -> None:
    adapter = OrdinaryTradeGroupedMappingV18AdapterFactory.create()
    schema = adapter.mapping_response_format(
        v13_response_format=OrdinaryTradeSemanticMappingFactory.create().mapping_response_format()
    )

    assert schema["json_schema"]["name"].endswith("_v18")
    assert schema["json_schema"]["strict"] is True
    side_schemas = []

    def walk(value):
        if isinstance(value, dict):
            properties = value.get("properties")
            if (
                isinstance(properties, dict)
                and isinstance(properties.get("side_values"), dict)
                and isinstance(properties["side_values"].get("items"), dict)
            ):
                side_schemas.append(properties["side_values"]["items"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(schema["json_schema"]["schema"])
    assert len(side_schemas) == 2
    assert all(item["properties"]["position_effect"] == {"const": "OPEN_SHORT"} for item in side_schemas)
    assert all(item["required"] == ["source_literal", "normalized_value"] for item in side_schemas)
    assert all(
        item["properties"]["position_effect_evidence"]["required"]
        == ["source_row", "source_column", "source_literal"]
        for item in side_schemas
    )


def test_v18_emits_source_bound_optional_open_short_to_active_candidate(tmp_path) -> None:
    store, context, document_id, _outcome = _complete_and_save(tmp_path)
    projection_record = OrdinaryTradeProjectionFactory(
        store=store, read_enabled=True
    ).create().compile_and_save(document_id=document_id, context=context)
    projection = OrdinaryTradeProjectionFactory(store=store, read_enabled=True).create().read(
        artifact_id=projection_record.artifact_id, context=context
    )
    disposal = next(
        item for item in projection["runtime_records"] if item["record_type"] == "SECURITY_DISPOSAL"
    )
    effect = next(item for item in disposal["roles"] if item["role"] == "position_effect")
    side = next(
        item for item in disposal["roles"] if item["role"] == "date"
    )
    assert effect["value"] == "OPEN_SHORT"
    assert effect["source_binding"]["source_literal"] == "Open short sale"
    assert effect["source_binding"]["semantic_mapping"]["position_effect"] == "OPEN_SHORT"
    assert disposal["record_type"] == "SECURITY_DISPOSAL"
    assert side["role"] == "date"

    facts = Gate4OrdinaryTradeCandidateRuntimeFactory(
        store=store, read_enabled=True
    ).create().list_facts(context=context)
    fact = next(item for item in facts if item["financial_type"] == "SECURITY_DISPOSAL")
    fact_effect = next(item for item in fact["roles"] if item["role"] == "position_effect")
    assert fact_effect["requirement"] == "optional"
    assert fact_effect["value"] == "OPEN_SHORT"
    assert fact_effect["source_binding"]["source_literal"] == "Open short sale"


def test_v18_accepts_an_ordinary_mapping_without_position_effect(tmp_path) -> None:
    def remove_effect(response: dict) -> None:
        side_value = response["table_decisions"][0]["side_values"][1]
        side_value.pop("position_effect")
        side_value.pop("position_effect_evidence")

    _store, _context, _document_id, outcome = _complete_and_save(
        tmp_path,
        mutation=remove_effect,
    )
    mapping = outcome["qualified_mappings"][0]
    assert "position_effect_contract" not in mapping
    assert all("position_effect" not in item for item in mapping["side_values"])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda response: response["table_decisions"][0]["side_values"][1].update(
            {"position_effect": "CLOSE_SHORT"}
        ),
        lambda response: response["table_decisions"][0]["side_values"][1].update(
            {"source_literal": "invented opening short", "position_effect": "OPEN_SHORT"}
        ),
        lambda response: response["table_decisions"][0]["side_values"][1].pop(
            "position_effect_evidence"
        ),
    ],
)
def test_v18_rejects_unknown_or_non_source_bound_effect(tmp_path, mutation) -> None:
    with pytest.raises(OrdinaryTradeSemanticMappingError):
        _complete_and_save(tmp_path, mutation=mutation)


def test_v18_generic_sale_requires_an_exact_source_cell_evidence(tmp_path) -> None:
    with pytest.raises(OrdinaryTradeSemanticMappingError):
        _complete_and_save(
            tmp_path,
            short_literal="Sale",
            mutation=lambda response: response["table_decisions"][0]["side_values"][1].pop(
                "position_effect_evidence"
            ),
        )
