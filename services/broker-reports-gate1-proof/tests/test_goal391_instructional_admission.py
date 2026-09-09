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
