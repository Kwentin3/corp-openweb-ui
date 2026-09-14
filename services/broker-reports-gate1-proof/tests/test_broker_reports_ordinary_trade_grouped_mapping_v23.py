from __future__ import annotations

import pytest

from broker_reports_gate1.ordinary_trade_grouped_mapping_v23 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V23_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV23AdapterFactory,
    OrdinaryTradeGroupedMappingV23Error,
)
from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    OrdinaryTradeProjectionFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_issue312_mapping_runtime as runtime_fixtures
from test_broker_reports_ordinary_trade_grouped_mapping_v17_runtime import (
    _case_with_source_bound_link,
    _v20_response,
)


def _v23_response(*, parent: dict, mapping: dict, headerless: str, claim: bool) -> dict:
    response = _v20_response(parent=parent, mapping=mapping)
    response["schema_version"] = ORDINARY_TRADE_GROUPED_MAPPING_V23_RESPONSE_SCHEMA_VERSION
    response["table_decisions"][1]["headerless_disposition"] = headerless
    if not claim:
        response["explicit_header_source_claims"]["claims"] = []
    return response


def _parent_mapping(tables: list[dict]) -> dict:
    return case_fixtures.candidate._mapping_from_headers(
        tuple(
            cell["displayed_value"]
            for cell in sorted(
                (cell for cell in tables[0]["content"]["cells"] if cell["row"] == 1),
                key=lambda cell: cell["column"],
            )
        )
    )


def test_v23_response_schema_requires_one_closed_headerless_disposition() -> None:
    adapter = OrdinaryTradeGroupedMappingV23AdapterFactory.create()
    response_format = adapter.mapping_response_format(
        v13_response_format=case_fixtures.OrdinaryTradeSemanticMappingFactory.create().mapping_response_format()
    )
    matches: list[dict] = []

    def visit(value) -> None:
        if isinstance(value, dict):
            properties = value.get("properties")
            if (
                isinstance(properties, dict)
                and properties.get("disposition") == {"const": "HEADER_ABSENT"}
            ):
                matches.append(value)
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(response_format["json_schema"]["schema"])
    assert len(matches) == 1
    assert matches[0]["properties"]["headerless_disposition"] == {
        "enum": ["CONTINUATION", "STANDALONE"]
    }
    assert "headerless_disposition" in matches[0]["required"]


def test_v23_rejects_headerless_decision_without_its_required_discriminator(tmp_path) -> None:
    _store, _context, _document_id, tables = _case_with_source_bound_link(
        tmp_path, persist_sidecar=False
    )
    response = _v23_response(
        parent=tables[0], mapping=_parent_mapping(tables),
        headerless="CONTINUATION", claim=True,
    )
    del response["table_decisions"][1]["headerless_disposition"]

    with pytest.raises(OrdinaryTradeGroupedMappingV23Error) as error:
        OrdinaryTradeGroupedMappingV23AdapterFactory.create().headerless_dispositions(
            response=response
        )

    assert error.value.code == "ordinary_trade_grouped_mapping_v23_response_invalid"


def _admit(*, store, context, document_id: str, tables: list[dict], response: dict) -> tuple[dict, dict]:
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    binding = cases.case_binding(document_id=document_id, context=context)
    semantic = case_fixtures.OrdinaryTradeSemanticMappingFactory.create()
    target_table_node_ids = [table["node_id"] for table in tables]
    package = semantic.build_mapping_package(
        canonical=binding["canonical"],
        confirmed_understandings=[],
        target_table_node_ids=target_table_node_ids,
        physical_table_continuation_context=None,
    )
    adapter = OrdinaryTradeGroupedMappingV23AdapterFactory.create()
    expanded = semantic.bind_source_owned_headers(
        response=adapter.expand_to_v13(response=response, package=package),
        package=package,
    )
    return cases, semantic.validate_mapping_response(
        response=expanded,
        canonical=binding["canonical"],
        canonical_binding=binding["canonical_binding"],
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=case_fixtures._metadata(),
        confirmed_understandings=[],
        user_scope_sha256=binding["user_scope_sha256"],
        target_table_node_ids=target_table_node_ids,
        explicit_header_source_response=adapter.explicit_header_source_claims(
            response=response
        ),
        headerless_disposition_response=adapter.headerless_dispositions(
            response=response
        ),
        physical_table_continuation_context=None,
        allow_source_bound_position_effect=True,
        allow_model_selected_header=True,
        require_headerless_dispositions=True,
    )


def test_v23_continuation_claim_qualifies_and_projects_headerless_child(tmp_path) -> None:
    store, context, document_id, tables = _case_with_source_bound_link(
        tmp_path, persist_sidecar=False
    )
    cases, outcome = _admit(
        store=store,
        context=context,
        document_id=document_id,
        tables=tables,
        response=_v23_response(
            parent=tables[0], mapping=_parent_mapping(tables),
            headerless="CONTINUATION", claim=True,
        ),
    )

    assert outcome["status"] == "COMPLETE"
    _record, saved = cases.save_mapping_outcome(
        document_id=document_id,
        context=context,
        outcome=outcome,
        provider_calls_total=1,
        mapping_prompt_snapshot=runtime_fixtures._test_mapping_prompt().snapshot(),
    )
    assert saved["explicit_header_source_continuations"]
    projection = OrdinaryTradeProjectionFactory(store=store, read_enabled=True).create().compile_and_save(
        document_id=document_id, context=context
    )
    assert projection.artifact_type == ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE
    payload = OrdinaryTradeProjectionFactory(store=store, read_enabled=True).create().read(
        artifact_id=projection.artifact_id, context=context
    )
    child_rows = {
        record["annotation_target"]["row"]
        for record in payload["runtime_records"]
        if record["annotation_target"]["node_id"] == tables[1]["node_id"]
    }
    assert child_rows == {2}


def test_v23_continuation_without_claim_is_rejected_at_mapping_boundary(tmp_path) -> None:
    store, context, document_id, tables = _case_with_source_bound_link(
        tmp_path, persist_sidecar=False
    )
    with pytest.raises(case_fixtures.OrdinaryTradeSemanticMappingError) as error:
        _admit(
            store=store,
            context=context,
            document_id=document_id,
            tables=tables,
            response=_v23_response(
                parent=tables[0], mapping=_parent_mapping(tables),
                headerless="CONTINUATION", claim=False,
            ),
        )

    assert error.value.code == (
        "ordinary_trade_semantic_mapping_headerless_continuation_claim_required"
    )


def test_v23_standalone_headerless_segment_requires_no_claim(tmp_path) -> None:
    store, context, document_id, tables = _case_with_source_bound_link(
        tmp_path, persist_sidecar=False
    )
    _cases, outcome = _admit(
        store=store,
        context=context,
        document_id=document_id,
        tables=tables,
        response=_v23_response(
            parent=tables[0], mapping=_parent_mapping(tables),
            headerless="STANDALONE", claim=False,
        ),
    )

    assert outcome["status"] == "COMPLETE"
    assert outcome["explicit_header_source_continuations"] == []
