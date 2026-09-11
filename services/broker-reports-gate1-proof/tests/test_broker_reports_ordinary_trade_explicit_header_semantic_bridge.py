from __future__ import annotations

import copy
import hashlib

import pytest

from broker_reports_gate1.ordinary_trade_explicit_header_source_response import (
    EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingError,
    OrdinaryTradeSemanticMappingFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_ordinary_trade_production_candidate as candidate_fixtures


def _physical_context(binding: dict[str, str], parent_id: str, child_id: str) -> dict:
    return {
        "schema_version": "broker_reports_physical_table_continuation_context_v1",
        "sidecar_artifact_ref": "art_physical_continuation",
        "sidecar_id": "ptc_bridge_test",
        "source_binding": {"normalization_run_id": "run_bridge", **binding},
        "links": [
            {
                "parent_table_node_id": parent_id,
                "child_table_node_id": child_id,
            }
        ],
    }


def _prepared_parent_outcome(tmp_path):
    _store, context, _document_id, canonical, binding = (
        case_fixtures._unknown_two_table_case(tmp_path)
    )
    table_nodes = [item for item in canonical["nodes"] if item["node_type"] == "TABLE"]
    parent, child = table_nodes
    child["content"]["header"] = []
    child.setdefault("content", {}).setdefault("metadata", {})[
        "physical_header_state"
    ] = "ABSENT"
    headers = tuple(
        cell["displayed_value"]
        for cell in sorted(
            (cell for cell in parent["content"]["cells"] if cell["row"] == 1),
            key=lambda cell: cell["column"],
        )
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()
    outcome = semantic.validate_mapping_response(
        response=case_fixtures._complete(
            parent, candidate_fixtures._mapping_from_headers(headers)
        ),
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=case_fixtures._metadata(),
        confirmed_understandings=[],
        user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
        target_table_node_ids=[parent["node_id"]],
    )
    return semantic, canonical, binding, context, parent, child, outcome


def _response(*, rows: list[int] | None = None) -> dict:
    return {
        "schema_version": EXPLICIT_HEADER_SOURCE_RESPONSE_SCHEMA_VERSION,
        "claims": [
            {
                "target_table_ref": "table_2",
                "header_source_table_ref": "table_1",
                "security_trade_rows": [2] if rows is None else rows,
            }
        ],
    }


def test_semantic_bridge_reuses_exact_qualified_parent_mapping_for_explicit_rows(tmp_path) -> None:
    semantic, canonical, binding, context, parent, child, outcome = _prepared_parent_outcome(tmp_path)

    continuations = semantic.build_explicit_header_source_continuations(
        response=_response(),
        canonical=canonical,
        canonical_binding=binding,
        user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
        qualified_mappings=outcome["qualified_mappings"],
        qualification_receipts=outcome["qualification_receipts"],
        physical_table_continuation_context=_physical_context(
            binding, parent["node_id"], child["node_id"]
        ),
    )

    assert continuations == [
        {
            "schema_version": "broker_reports_ordinary_trade_explicit_header_source_continuation_v1",
            "canonical_binding": binding,
            "target_table_node_id": child["node_id"],
            "header_source_table_node_id": parent["node_id"],
            "header_source_row": 1,
            "security_trade_rows": [2],
            "mapping": outcome["qualified_mappings"][0],
        }
    ]


def test_semantic_bridge_rejects_a_claim_outside_its_mapping_batch_scope(tmp_path) -> None:
    semantic, canonical, binding, context, parent, child, outcome = _prepared_parent_outcome(tmp_path)

    with pytest.raises(OrdinaryTradeSemanticMappingError) as error:
        semantic.build_explicit_header_source_continuations(
            response=_response(),
            canonical=canonical,
            canonical_binding=binding,
            user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
            qualified_mappings=outcome["qualified_mappings"],
            qualification_receipts=outcome["qualification_receipts"],
            physical_table_continuation_context=_physical_context(
                binding, parent["node_id"], child["node_id"]
            ),
            target_table_node_ids=[parent["node_id"]],
        )

    assert error.value.code == "ordinary_trade_explicit_header_source_invalid"


def test_semantic_bridge_uses_batch_local_table_refs_not_global_order(tmp_path) -> None:
    semantic, canonical, binding, context, parent, child, outcome = _prepared_parent_outcome(tmp_path)
    unrelated = copy.deepcopy(parent)
    unrelated["node_id"] = "node_unrelated_before_continuation"
    canonical["nodes"].insert(canonical["nodes"].index(parent), unrelated)

    continuations = semantic.build_explicit_header_source_continuations(
        response=_response(),
        canonical=canonical,
        canonical_binding=binding,
        user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
        qualified_mappings=outcome["qualified_mappings"],
        qualification_receipts=outcome["qualification_receipts"],
        physical_table_continuation_context=_physical_context(
            binding, parent["node_id"], child["node_id"]
        ),
        target_table_node_ids=[parent["node_id"], child["node_id"]],
    )

    assert continuations[0]["header_source_table_node_id"] == parent["node_id"]
    assert continuations[0]["target_table_node_id"] == child["node_id"]


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (
            lambda response, context: context["links"][0].update(
                {"parent_table_node_id": "forged-parent"}
            ),
            "ordinary_trade_explicit_header_source_context_invalid",
        ),
        (
            lambda response, context: response["claims"][0].update(
                {"security_trade_rows": [999]}
            ),
            "ordinary_trade_explicit_header_source_rows_invalid",
        ),
        (
            lambda response, context: None,
            "ordinary_trade_explicit_header_source_parent_mapping_invalid",
        ),
    ],
)
def test_semantic_bridge_fails_closed_for_unbound_rows_links_or_parent_authority(
    tmp_path, mutation, code
) -> None:
    semantic, canonical, binding, context, parent, child, outcome = _prepared_parent_outcome(tmp_path)
    response = _response()
    physical_context = _physical_context(binding, parent["node_id"], child["node_id"])
    mutation(response, physical_context)
    mappings = outcome["qualified_mappings"]
    if code == "ordinary_trade_explicit_header_source_parent_mapping_invalid":
        mappings = copy.deepcopy(mappings)
        mappings[0]["columns"][0]["semantic_role"] = "unmapped"

    with pytest.raises(OrdinaryTradeSemanticMappingError) as error:
        semantic.build_explicit_header_source_continuations(
            response=response,
            canonical=canonical,
            canonical_binding=binding,
            user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
            qualified_mappings=mappings,
            qualification_receipts=outcome["qualification_receipts"],
            physical_table_continuation_context=physical_context,
        )

    assert error.value.code == code
