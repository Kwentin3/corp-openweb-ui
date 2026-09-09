from __future__ import annotations

import copy

from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingFactory,
)

import test_broker_reports_issue312_mapping_case as mapping_case


def _no_named_consumer_response(*, schema_version: str, evidence=None) -> dict:
    decision = {
        "table_ref": "table_1",
        "header_row": 1,
        "disposition": "NO_NAMED_CONSUMER",
        "columns": [],
        "amount_currency_bindings": [],
        "side_values": [],
        "row_dispositions": [],
        "no_consumer_kind": "OTHER_NO_NAMED_CONSUMER",
    }
    if evidence is not None:
        decision["classification_evidence"] = evidence
    return {
        "schema_version": schema_version,
        "status": "COMPLETE",
        "table_decisions": [decision],
        "clarification": None,
        "message": "No named consumer for this auxiliary table.",
    }


def _validate(*, store, owner, response, canonical, binding, document_id, context) -> dict:
    scope = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True)
    return owner.validate_mapping_response(
        response=response,
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=mapping_case._metadata(),
        confirmed_understandings=[],
        user_scope_sha256=scope.create().case_binding(
            document_id=document_id, context=context
        )["user_scope_sha256"],
    )


def test_v12_omits_model_evidence_and_owner_binds_the_full_canonical_envelope(
    tmp_path,
) -> None:
    store, context, document_id, canonical, binding, table, _mapping = (
        mapping_case._unknown_case(tmp_path)
    )
    canonical = copy.deepcopy(canonical)
    next(node for node in canonical["nodes"] if node["node_id"] == table["node_id"])[
        "content"
    ]["title"] = "Auxiliary source context"
    owner = OrdinaryTradeSemanticMappingFactory.create()
    expected_envelope = owner.build_classification_evidence_envelopes(
        canonical=canonical,
        target_table_node_ids=[table["node_id"]],
    )[table["node_id"]]

    outcome = _validate(
        store=store,
        owner=owner,
        response=_no_named_consumer_response(
            schema_version=owner.mapping_response_format()["json_schema"]["schema"][
                "properties"
            ]["schema_version"]["const"]
        ),
        canonical=canonical,
        binding=binding,
        document_id=document_id,
        context=context,
    )

    assert outcome["status"] == "COMPLETE"
    resolution = outcome["table_resolutions"][0]
    assert resolution["classification_evidence"] == expected_envelope
    schema = owner.mapping_response_format()["json_schema"]["schema"]
    no_consumer_variant = schema["properties"]["table_decisions"]["items"][
        "anyOf"
    ][2]
    assert "classification_evidence" not in no_consumer_variant["required"]
    assert "classification_evidence" not in no_consumer_variant["properties"]


def test_v11_replay_keeps_its_model_selected_evidence_subset(tmp_path) -> None:
    store, context, document_id, canonical, binding, table, _mapping = (
        mapping_case._unknown_case(tmp_path)
    )
    canonical = copy.deepcopy(canonical)
    next(node for node in canonical["nodes"] if node["node_id"] == table["node_id"])[
        "content"
    ]["title"] = "Auxiliary source context"
    owner = OrdinaryTradeSemanticMappingFactory.create()
    envelope = owner.build_classification_evidence_envelopes(
        canonical=canonical,
        target_table_node_ids=[table["node_id"]],
    )[table["node_id"]]
    selected = [
        {
            "context_ref": envelope[0]["context_ref"],
            "relation": envelope[0]["relation"],
        }
    ]

    outcome = _validate(
        store=store,
        owner=owner,
        response=_no_named_consumer_response(
            schema_version="broker_reports_ordinary_trade_semantic_mapping_response_v11",
            evidence=copy.deepcopy(selected),
        ),
        canonical=canonical,
        binding=binding,
        document_id=document_id,
        context=context,
    )

    assert outcome["status"] == "COMPLETE"
    assert outcome["table_resolutions"][0]["classification_evidence"] == [
        {**selected[0], **{key: envelope[0][key] for key in ("canonical_node_id", "literal_sha256")}}
    ]
