from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.ordinary_trade_explicit_header_source_response import (
    EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION,
)
from broker_reports_gate1.ordinary_trade_grouped_mapping_v17 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV17AdapterFactory,
    OrdinaryTradeGroupedMappingV17Error,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MAPPING_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures


def _v17_response(*, table: dict, mapping: dict) -> dict:
    response = case_fixtures._complete(table, mapping)
    response["schema_version"] = ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION
    decision = response["table_decisions"][0]
    del decision["row_dispositions"]
    decision["row_policy"] = {
        "default_disposition": "SECURITY_TRADES",
        "exception_rows": [],
    }
    response["explicit_header_source_claims"] = {
        "schema_version": EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION,
        "claims": [
            {
                "target_table_ref": "table_2",
                "header_source_table_ref": "table_1",
                "security_trade_rows": [2],
            }
        ],
    }
    return response


def test_v17_schema_is_distinct_strict_and_requires_validator_owned_claim_envelope() -> None:
    adapter = OrdinaryTradeGroupedMappingV17AdapterFactory.create()
    response_format = adapter.mapping_response_format(
        v13_response_format=OrdinaryTradeSemanticMappingFactory.create().mapping_response_format()
    )

    assert response_format["json_schema"]["name"].endswith("_v17")
    assert response_format["json_schema"]["strict"] is True
    root = response_format["json_schema"]["schema"]
    assert root["additionalProperties"] is False
    assert root["properties"]["schema_version"]["const"] == (
        ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION
    )
    assert "explicit_header_source_claims" in root["required"]
    claim_root = root["properties"]["explicit_header_source_claims"]
    assert claim_root["required"] == ["schema_version", "claims"]
    claim = claim_root["properties"]["claims"]["items"]
    assert claim["required"] == [
        "target_table_ref",
        "header_source_table_ref",
        "security_trade_rows",
    ]
    assert claim["additionalProperties"] is False


def test_v17_expands_grouped_mapping_through_v15_and_preserves_validated_claims(tmp_path) -> None:
    _store, _context, _document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    adapter = OrdinaryTradeGroupedMappingV17AdapterFactory.create()
    response = _v17_response(table=table, mapping=mapping)
    package = OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
        canonical=_canonical,
        confirmed_understandings=[],
    )

    expanded = adapter.expand_to_v13(response=response, package=package)

    assert expanded["schema_version"] == MAPPING_RESPONSE_SCHEMA_VERSION
    assert expanded["table_decisions"][0]["row_dispositions"] == [
        {"row": 2, "disposition": "SECURITY_TRADES"},
        {"row": 3, "disposition": "SECURITY_TRADES"},
    ]
    assert adapter.explicit_header_source_claims(response=response) == {
        "schema_version": EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION,
        "claims": response["explicit_header_source_claims"]["claims"],
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda response: response.pop("explicit_header_source_claims"),
        lambda response: response["explicit_header_source_claims"]["claims"][0].update(
            {"unexpected": True}
        ),
    ],
)
def test_v17_rejects_missing_or_non_strict_claim_envelope(tmp_path, mutation) -> None:
    _store, _context, _document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _v17_response(table=table, mapping=mapping)
    mutation(response)

    with pytest.raises(OrdinaryTradeGroupedMappingV17Error):
        OrdinaryTradeGroupedMappingV17AdapterFactory.create().explicit_header_source_claims(
            response=copy.deepcopy(response)
        )


def test_v17_rejects_v18_only_position_effect(tmp_path) -> None:
    _store, _context, _document_id, _canonical, _binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = _v17_response(table=table, mapping=mapping)
    response["table_decisions"][0]["side_values"][0]["position_effect"] = "OPEN_SHORT"

    with pytest.raises(OrdinaryTradeGroupedMappingV17Error):
        OrdinaryTradeGroupedMappingV17AdapterFactory.create().expand_to_v13(
            response=response,
            package=OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
                canonical=_canonical, confirmed_understandings=[]
            ),
        )
