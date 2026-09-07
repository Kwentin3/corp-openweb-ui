from __future__ import annotations

import asyncio
import copy
import hashlib
import json

import pytest

from broker_reports_gate1.gate2_model_contracts import Gate2StructuredModelResult
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MAPPING_PROMPT_VERSION,
    OrdinaryTradeSemanticMappingError,
    OrdinaryTradeSemanticMappingFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping_qualification import (
    OrdinaryTradeSemanticMappingQualificationError,
    OrdinaryTradeSemanticMappingQualificationFactory,
    load_frozen_fixture,
    safe_role_map_sha256,
)

import test_broker_reports_issue312_mapping_case as case_fixtures


class InjectedClient:
    def __init__(self, response):
        self._response = response
        self.calls = []

    async def extract(self, **kwargs):
        self.calls.append(kwargs)
        return Gate2StructuredModelResult(
            content=self._response,
            execution_metadata=case_fixtures._metadata(),
        )


def _fixture(tmp_path):
    _store, context, _document_id, canonical, binding, table, mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    response = case_fixtures._complete(table, mapping)
    user_scope_sha256 = hashlib.sha256(context.user_id.encode()).hexdigest()
    return {
        "canonical": canonical,
        "canonical_binding": binding,
        "user_scope_sha256": user_scope_sha256,
        "expected_verdict": {
            "status": "COMPLETE",
            "qualified_mapping_count": 1,
            "qualification_receipt_count": 1,
            "table_resolution_count": 1,
            "currency_table_count": 0,
            "role_map_sha256": safe_role_map_sha256(response),
        },
        "confirmed_understandings": [],
        "target_table_node_ids": None,
        "frozen_mappings": [],
        "fixture_identity": {"fixture_id": "public-test-ordinary-trade-v1"},
    }, response


def test_local_qualification_uses_production_contract_once_and_returns_safe_receipt(tmp_path):
    fixture, response = _fixture(tmp_path)
    client = InjectedClient(response)

    receipt = asyncio.run(
        OrdinaryTradeSemanticMappingQualificationFactory(model_client=client)
        .create()
        .run(
            fixture=fixture,
            model_id="models/gemini-3.5-flash",
            provider_profile_id="google_gemini",
        )
    )

    assert len(client.calls) == 1
    assert client.calls[0]["prompt"].version == MAPPING_PROMPT_VERSION
    assert MAPPING_PROMPT_VERSION == "ordinary_trade_semantic_mapping_prompt_v21"
    assert client.calls[0]["response_format"]["json_schema"]["strict"] is True
    assert receipt["status"] == "PASSED"
    assert receipt["provider_calls_total"] == 1
    assert receipt["verdict"] == fixture["expected_verdict"]
    assert "Mapping" not in str(receipt)
    assert "displayed_value" not in str(receipt)


def test_local_qualification_fails_closed_when_validator_verdict_disagrees(tmp_path):
    fixture, response = _fixture(tmp_path)
    fixture = copy.deepcopy(fixture)
    fixture["expected_verdict"]["qualified_mapping_count"] = 0

    with pytest.raises(OrdinaryTradeSemanticMappingQualificationError) as exc:
        asyncio.run(
            OrdinaryTradeSemanticMappingQualificationFactory(
                model_client=InjectedClient(response)
            )
            .create()
            .run(
                fixture=fixture,
                model_id="models/gemini-3.5-flash",
                provider_profile_id="google_gemini",
            )
        )

    assert exc.value.code == "ordinary_trade_mapping_qualification_verdict_mismatch"


def test_local_qualification_reads_only_a_frozen_fixture_json(tmp_path):
    fixture, _response = _fixture(tmp_path)
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(fixture), encoding="utf-8")

    loaded = load_frozen_fixture(path)

    assert loaded["fixture_identity"] == fixture["fixture_identity"]
    assert loaded["expected_verdict"] == fixture["expected_verdict"]


def test_local_qualification_rejects_a_stale_canonical_binding_before_model_call(tmp_path):
    fixture, response = _fixture(tmp_path)
    fixture = copy.deepcopy(fixture)
    fixture["canonical_binding"]["canonical_root_sha256"] = "0" * 64
    client = InjectedClient(response)

    with pytest.raises(OrdinaryTradeSemanticMappingQualificationError) as exc:
        asyncio.run(
            OrdinaryTradeSemanticMappingQualificationFactory(model_client=client)
            .create()
            .run(
                fixture=fixture,
                model_id="models/gemini-3.5-flash",
                provider_profile_id="google_gemini",
            )
        )

    assert exc.value.code == "ordinary_trade_mapping_qualification_canonical_binding_invalid"
    assert client.calls == []


def test_local_qualification_rejects_count_equivalent_wrong_role_map(tmp_path):
    fixture, response = _fixture(tmp_path)
    wrong_response = copy.deepcopy(response)
    column = next(
        item
        for item in wrong_response["table_decisions"][0]["columns"]
        if item["semantic_role"] == "comment"
    )
    column["semantic_role"] = "unmapped"

    with pytest.raises(OrdinaryTradeSemanticMappingQualificationError) as exc:
        asyncio.run(
            OrdinaryTradeSemanticMappingQualificationFactory(
                model_client=InjectedClient(wrong_response)
            )
            .create()
            .run(
                fixture=fixture,
                model_id="models/gemini-3.5-flash",
                provider_profile_id="google_gemini",
            )
        )

    assert exc.value.code == "ordinary_trade_mapping_qualification_verdict_mismatch"


def test_scoped_mapping_does_not_claim_to_cover_tables_not_sent_to_model(tmp_path):
    _store, context, document_id, canonical, binding = (
        case_fixtures._unknown_two_table_case(tmp_path)
    )
    table = next(
        node for node in canonical["nodes"] if node["node_type"] == "TABLE"
    )
    header_cells = sorted(
        (cell for cell in table["content"]["cells"] if cell["row"] == 1),
        key=lambda cell: cell["column"],
    )
    mapping = case_fixtures.candidate._mapping_from_headers(
        tuple(cell["displayed_value"] for cell in header_cells)
    )
    semantic = OrdinaryTradeSemanticMappingFactory.create()

    outcome = semantic.validate_mapping_response(
        response=case_fixtures._complete(table, mapping),
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=case_fixtures._metadata(),
        confirmed_understandings=[],
        user_scope_sha256=hashlib.sha256(context.user_id.encode()).hexdigest(),
        target_table_node_ids=[table["node_id"]],
    )

    assert outcome["status"] == "COMPLETE"
    assert [item["table_node_id"] for item in outcome["table_resolutions"]] == [
        table["node_id"]
    ]


def test_scoped_mapping_applies_context_limits_after_structural_scope_selection(tmp_path):
    _store, _context, _document_id, canonical, _binding = (
        case_fixtures._unknown_two_table_case(tmp_path)
    )
    canonical = copy.deepcopy(canonical)
    target = next(node for node in canonical["nodes"] if node["node_type"] == "TABLE")
    for index in range(65):
        unrelated = copy.deepcopy(target)
        unrelated["node_id"] = f"unrelated-table-{index}"
        unrelated["order"] = 1000 + index
        canonical["nodes"].append(unrelated)

    package = OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
        canonical=canonical,
        confirmed_understandings=[],
        target_table_node_ids=[target["node_id"]],
    )

    # The full Canonical is still intact; only the explicit structural scope is
    # sent to the model, so unrelated tables cannot consume this call's budget.
    assert len(package["case"]["tables"]) == 1
    assert package["case"]["tables"][0]["table_ref"] == "table_1"


def test_mapping_package_projects_only_the_immediate_preceding_sibling_context(
    tmp_path,
):
    _store, _context, _document_id, canonical, _binding, table, _mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    canonical = copy.deepcopy(canonical)
    table = next(
        item for item in canonical["nodes"] if item["node_id"] == table["node_id"]
    )
    root = canonical["root_container_ref"]
    target_container = next(
        item
        for item in canonical["containers"]
        if item["container_id"] == table["container_ref"]
    )
    target_container["order"] = 1
    preceding_container = {
        "container_id": "container_preceding",
        "parent_container_ref": root,
        "order": 0,
    }
    next_container = {
        "container_id": "container_next",
        "parent_container_ref": root,
        "order": 2,
    }
    other_parent_container = {
        "container_id": "container_other_parent",
        "parent_container_ref": "container_preceding",
        "order": 0,
    }
    canonical["containers"].extend(
        [preceding_container, next_container, other_parent_container]
    )
    table["order"] = 5
    preceding_literals = [
            {
                "node_id": f"preceding-text-{index}",
                "container_ref": "container_preceding",
                "order": index,
                "node_type": "TEXT",
                "content": {"text": f"sibling-{index}"},
            }
            for index in range(6)
    ]
    local_literals = [
        {
            "node_id": f"local-text-{index}",
            "container_ref": table["container_ref"],
            "order": index,
            "node_type": "NOTE",
            "content": {"text": f"local-{index}"},
        }
        for index in range(5)
    ]
    canonical["nodes"].extend(
        preceding_literals
        + [
            {
                "node_id": "preceding-table",
                "container_ref": "container_preceding",
                "order": 6,
                "node_type": "TABLE",
                "content": {"cells": [{"displayed_value": "table-leak"}]},
            },
        ]
        + local_literals
        + [
            {
                "node_id": "local-after-table",
                "container_ref": table["container_ref"],
                "order": 6,
                "node_type": "HEADING",
                "content": {"text": "next-node-leak"},
            },
            {
                "node_id": "next-sibling-text",
                "container_ref": "container_next",
                "order": 0,
                "node_type": "TEXT",
                "content": {"text": "next-sibling-leak"},
            },
            {
                "node_id": "other-parent-text",
                "container_ref": "container_other_parent",
                "order": 0,
                "node_type": "TEXT",
                "content": {"text": "other-parent-leak"},
            },
        ]
    )

    package = OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
        canonical=canonical,
        confirmed_understandings=[],
        target_table_node_ids=[table["node_id"]],
    )

    source_context = package["case"]["tables"][0]["source_context"]
    assert [item["literal"] for item in source_context["entries"]] == [
        "sibling-3",
        "sibling-4",
        "sibling-5",
        "local-0",
        "local-1",
        "local-2",
        "local-3",
        "local-4",
    ]
    assert [item["relation"] for item in source_context["entries"]] == [
        "PRECEDING_SIBLING_CONTAINER",
        "PRECEDING_SIBLING_CONTAINER",
        "PRECEDING_SIBLING_CONTAINER",
        "PRECEDING_SAME_CONTAINER",
        "PRECEDING_SAME_CONTAINER",
        "PRECEDING_SAME_CONTAINER",
        "PRECEDING_SAME_CONTAINER",
        "PRECEDING_SAME_CONTAINER",
    ]
    assert "leak" not in str(source_context)


def test_mapping_package_fails_closed_for_ambiguous_sibling_container_order(tmp_path):
    _store, _context, _document_id, canonical, _binding, table, _mapping = (
        case_fixtures._unknown_case(tmp_path)
    )
    canonical = copy.deepcopy(canonical)
    root = canonical["root_container_ref"]
    canonical["containers"].append(
        {
            "container_id": "container_duplicate_sibling_order",
            "parent_container_ref": root,
            "order": 0,
        }
    )

    with pytest.raises(OrdinaryTradeSemanticMappingError) as exc:
        OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
            canonical=canonical,
            confirmed_understandings=[],
            target_table_node_ids=[table["node_id"]],
        )

    assert exc.value.code == "ordinary_trade_semantic_mapping_canonical_invalid"


def test_safe_role_map_hash_covers_amount_currency_and_side_choices(tmp_path):
    _fixture_value, response = _fixture(tmp_path)
    changed = copy.deepcopy(response)
    decision = changed["table_decisions"][0]
    decision["amount_currency_bindings"][0]["currency_column"] = -1
    decision["side_values"][0]["normalized_value"] = (
        "PURCHASE"
        if decision["side_values"][0]["normalized_value"] == "DISPOSAL"
        else "DISPOSAL"
    )

    assert safe_role_map_sha256(changed) != safe_role_map_sha256(response)
