from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.instructional_table_classification import (
    OUTPUT_SCHEMA_VERSION,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingError,
    OrdinaryTradeSemanticMappingFactory,
)

import test_broker_reports_issue312_mapping_case as mapping_case
import test_broker_reports_ordinary_trade_production_candidate as candidate


def _descriptor():
    canonical = {
        "nodes": [
            {
                "node_id": "heading_1",
                "container_ref": "page_1",
                "order": 0,
                "node_type": "HEADING",
                "content": {"text": "Reference example"},
            },
            {
                "node_id": "text_1",
                "container_ref": "page_1",
                "order": 1,
                "node_type": "TEXT",
                "content": {"text": "How to read this sample"},
            },
            {
                "node_id": "table_1",
                "container_ref": "page_1",
                "order": 2,
                "node_type": "TABLE",
                "content": {
                    "title": "Illustrative transactions",
                    "cells": [
                        {"row": 1, "column": 1, "displayed_value": "Date"},
                        {"row": 2, "column": 1, "displayed_value": "Example"},
                    ],
                },
            },
        ]
    }
    owner = OrdinaryTradeSemanticMappingFactory.create()
    return owner, canonical, owner.build_instructional_classification_descriptor(
        canonical=canonical, table_node_id="table_1"
    )


def _response(descriptor, *, classification: str):
    table = descriptor["case"]["table"]
    evidence = []
    if classification == "INSTRUCTIONAL_REFERENCE":
        context = table["source_context"]["entries"][0]
        evidence = [
            {"context_ref": context["context_ref"], "relation": context["relation"]}
        ]
    return {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "classification": classification,
        "header_row": table["header_row_choices"][0],
        "classification_evidence": evidence,
    }


def test_owner_admits_instructional_result_as_canonical_bound_resolution() -> None:
    owner, canonical, descriptor = _descriptor()

    admitted = owner.admit_instructional_classification(
        canonical=canonical,
        descriptor=descriptor,
        response=_response(descriptor, classification="INSTRUCTIONAL_REFERENCE"),
    )

    resolution = admitted["table_resolution"]
    assert admitted["classification"] == "INSTRUCTIONAL_REFERENCE"
    assert resolution["disposition"] == "NO_NAMED_CONSUMER"
    assert resolution["no_consumer_kind"] == "INSTRUCTIONAL_REFERENCE"
    assert resolution["classification_evidence"]
    assert all("literal" not in item for item in resolution["classification_evidence"])


def test_owner_rejects_stale_descriptor_and_does_not_create_non_instructional_resolution() -> None:
    owner, canonical, descriptor = _descriptor()
    stale = copy.deepcopy(descriptor)
    stale["case_sha256"] = "0" * 64

    with pytest.raises(OrdinaryTradeSemanticMappingError) as exc:
        owner.admit_instructional_classification(
            canonical=canonical,
            descriptor=stale,
            response=_response(descriptor, classification="INSTRUCTIONAL_REFERENCE"),
        )
    assert exc.value.code == "ordinary_trade_instructional_descriptor_stale"

    admitted = owner.admit_instructional_classification(
        canonical=canonical,
        descriptor=descriptor,
        response=_response(descriptor, classification="NOT_INSTRUCTIONAL"),
    )
    assert admitted["table_resolution"] is None


def test_owner_reports_missing_classifier_result_without_publishing_a_resolution() -> None:
    owner, canonical, descriptor = _descriptor()
    assert descriptor["table_node_id"] == "table_1"

    with pytest.raises(OrdinaryTradeSemanticMappingError) as exc:
        owner.rebind_instructional_classification_outcomes(
            canonical=canonical,
            target_table_node_ids=["table_1"],
            classifier_outcomes=[],
        )

    assert exc.value.code == "ordinary_trade_instructional_classifier_count_invalid"


def test_classifier_rebind_keeps_the_canonical_node_order_not_container_id_order() -> None:
    canonical = {
        "nodes": [
            {
                "node_id": "table_z_first",
                "container_ref": "container_z",
                "order": 0,
                "node_type": "TABLE",
                "content": {
                    "cells": [
                        {"row": 1, "column": 1, "displayed_value": "Date"},
                        {"row": 2, "column": 1, "displayed_value": "Value"},
                    ]
                },
            },
            {
                "node_id": "table_a_second",
                "container_ref": "container_a",
                "order": 0,
                "node_type": "TABLE",
                "content": {
                    "cells": [
                        {"row": 1, "column": 1, "displayed_value": "Date"},
                        {"row": 2, "column": 1, "displayed_value": "Value"},
                    ]
                },
            },
        ]
    }
    owner = OrdinaryTradeSemanticMappingFactory.create()
    target_ids = ["table_z_first", "table_a_second"]
    descriptors = [
        owner.build_instructional_classification_descriptor(
            canonical=canonical, table_node_id=table_node_id
        )
        for table_node_id in target_ids
    ]

    rebound = owner.rebind_instructional_classification_outcomes(
        canonical=canonical,
        target_table_node_ids=target_ids,
        classifier_outcomes=[
            {
                "table_node_id": descriptor["table_node_id"],
                "response": _response(
                    descriptor, classification="NOT_INSTRUCTIONAL"
                ),
            }
            for descriptor in descriptors
        ],
    )

    assert rebound["target_table_node_ids"] == target_ids
    assert rebound["mapping_target_table_node_ids"] == target_ids


def test_all_instructional_scope_completes_without_a_role_mapping(tmp_path) -> None:
    store, context, document_id, canonical, binding, table, _mapping = (
        mapping_case._unknown_case(tmp_path)
    )
    table["content"]["title"] = "Reference example"
    owner = OrdinaryTradeSemanticMappingFactory.create()
    descriptor = owner.build_instructional_classification_descriptor(
        canonical=canonical, table_node_id=table["node_id"]
    )
    outcome = owner.finalize_instructional_preclassification(
        canonical=canonical,
        canonical_binding=binding,
        user_scope_sha256=(
            mapping_case.OrdinaryTradeMappingCaseFactory(
                store=store, read_enabled=True
            )
            .create()
            .case_binding(document_id=document_id, context=context)["user_scope_sha256"]
        ),
        target_table_node_ids=[table["node_id"]],
        classifier_outcomes=[
            {
                "table_node_id": table["node_id"],
                "response": _response(
                    descriptor, classification="INSTRUCTIONAL_REFERENCE"
                ),
            }
        ],
        mapping_outcome=None,
    )

    assert outcome["status"] == "COMPLETE"
    assert outcome["qualified_mappings"] == []
    assert outcome["qualification_receipts"] == []
    assert outcome["table_resolutions"][0]["no_consumer_kind"] == (
        "INSTRUCTIONAL_REFERENCE"
    )


def test_mixed_instructional_and_mapped_scope_is_merged_in_canonical_order(
    tmp_path,
) -> None:
    store, context, document_id, canonical, binding = mapping_case._unknown_two_table_case(
        tmp_path
    )
    tables = [item for item in canonical["nodes"] if item["node_type"] == "TABLE"]
    instructional, mapped = tables
    instructional["content"]["title"] = "Reference example"
    owner = OrdinaryTradeSemanticMappingFactory.create()
    instructional_descriptor = owner.build_instructional_classification_descriptor(
        canonical=canonical, table_node_id=instructional["node_id"]
    )
    mapped_descriptor = owner.build_instructional_classification_descriptor(
        canonical=canonical, table_node_id=mapped["node_id"]
    )
    cases = mapping_case.OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create()
    scope = cases.case_binding(document_id=document_id, context=context)[
        "user_scope_sha256"
    ]
    mapping_outcome = owner.validate_mapping_response(
        response=mapping_case._complete(
            mapped,
            candidate._mapping_from_headers(tuple(candidate._ROWS[0])),
        ),
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata=mapping_case._metadata(),
        confirmed_understandings=[],
        user_scope_sha256=scope,
        target_table_node_ids=[mapped["node_id"]],
    )

    outcome = owner.finalize_instructional_preclassification(
        canonical=canonical,
        canonical_binding=binding,
        user_scope_sha256=scope,
        target_table_node_ids=[item["node_id"] for item in tables],
        classifier_outcomes=[
            {
                "table_node_id": instructional["node_id"],
                "response": _response(
                    instructional_descriptor,
                    classification="INSTRUCTIONAL_REFERENCE",
                ),
            },
            {
                "table_node_id": mapped["node_id"],
                "response": _response(
                    mapped_descriptor, classification="NOT_INSTRUCTIONAL"
                ),
            },
        ],
        mapping_outcome=mapping_outcome,
    )

    assert outcome["status"] == "COMPLETE"
    assert [item["table_node_id"] for item in outcome["table_resolutions"]] == [
        item["node_id"] for item in tables
    ]
    assert outcome["table_resolutions"][0]["no_consumer_kind"] == (
        "INSTRUCTIONAL_REFERENCE"
    )
