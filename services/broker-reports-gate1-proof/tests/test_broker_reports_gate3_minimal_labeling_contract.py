from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

from broker_reports_gate1.artifact_models import ARTIFACT_TYPES
from broker_reports_gate1.canonical_artifact import (
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    validate_canonical_artifact,
)


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
CONTRACTS = REPOSITORY_ROOT / "docs" / "stage2" / "contracts"
TARGET_SCHEMA_PATH = CONTRACTS / "BROKER_REPORTS_GATE3_TARGET.v1.schema.json"
PROJECTION_SCHEMA_PATH = (
    CONTRACTS / "BROKER_REPORTS_GATE3_PROJECTION.v1.schema.json"
)
RESPONSE_SCHEMA_PATH = (
    CONTRACTS / "BROKER_REPORTS_GATE3_LABELING_RESPONSE.v1.schema.json"
)
ANNOTATIONS_SCHEMA_PATH = (
    CONTRACTS / "BROKER_REPORTS_FINANCIAL_ANNOTATIONS.v1.schema.json"
)
MINIMAL_CONTRACT_PATH = (
    CONTRACTS / "BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md"
)
PIPELINE_GATES_PATH = CONTRACTS / "BROKER_REPORTS_PIPELINE_GATES.v1.md"
GATE3_HANDOFF_PATH = CONTRACTS / "BROKER_REPORTS_GATE3_HANDOFF.v1.md"
AUTHORITY_MAP_PATH = CONTRACTS / "BROKER_REPORTS_ARCHITECTURE_AUTHORITIES.md"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


TARGET_SCHEMA = _read_json(TARGET_SCHEMA_PATH)
PROJECTION_SCHEMA = _read_json(PROJECTION_SCHEMA_PATH)
RESPONSE_SCHEMA = _read_json(RESPONSE_SCHEMA_PATH)
ANNOTATIONS_SCHEMA = _read_json(ANNOTATIONS_SCHEMA_PATH)
TARGET_SCHEMA_ID = TARGET_SCHEMA["$id"]
SCHEMA_REGISTRY = Registry().with_resource(
    TARGET_SCHEMA_ID,
    Resource.from_contents(TARGET_SCHEMA),
)


def _validator(schema: dict) -> Draft202012Validator:
    return Draft202012Validator(schema, registry=SCHEMA_REGISTRY)


def _canonical_artifact() -> dict:
    return CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="gate3-contract-test-v1")
    ).create().build(
        tenant_id="gate3-contract-user",
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": "a" * 64,
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref="source-gate3-contract",
        source_payloads=[
            {
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "pdf_text_layer_projection": {
                    "page_inventory": [{"page_number": 1}],
                    "line_inventory": [],
                },
            }
        ],
        source_units=[
            {
                "unit_ref": "gate3-table-unit",
                "source_location": {"page": 1, "line_start": 1},
                "text": "Type Amount Brokerage fee 12.00",
            },
            {
                "unit_ref": "gate3-text-unit",
                "source_location": {"page": 1, "line_start": 2},
                "text": "Brokerage fee charged",
            },
        ],
        table_projections=[
            {
                "projection_status": "ready",
                "table_projection_id": "gate3-table",
                "source_unit_ref": "gate3-table-unit",
                "row_count": 2,
                "column_count": 2,
                "cells": [
                    {
                        "row_ordinal": row,
                        "column_ordinal": column,
                        "normalized_private_value_path": f"v-{row}-{column}",
                    }
                    for row in (1, 2)
                    for column in (1, 2)
                ],
                "private_values": [
                    {
                        "value_path_ref": f"v-{row}-{column}",
                        "normalized_value": value,
                    }
                    for row, values in (
                        (1, ("Type", "Amount")),
                        (2, ("Brokerage fee", "12.00")),
                    )
                    for column, value in enumerate(values, 1)
                ],
            }
        ],
    )


def _contract_examples() -> tuple[dict, dict, dict, dict]:
    canonical = _canonical_artifact()
    assert validate_canonical_artifact(canonical)["passed"]
    text_node = next(
        node for node in canonical["nodes"] if node["node_type"] == "TEXT"
    )
    table_node = next(
        node for node in canonical["nodes"] if node["node_type"] == "TABLE"
    )
    table_cell = next(
        cell
        for cell in table_node["content"]["cells"]
        if cell["row"] == 2 and cell["column"] == 1
    )
    node_target = {"kind": "node", "node_id": text_node["node_id"]}
    cell_target = {
        "kind": "table_cell",
        "node_id": table_node["node_id"],
        "row": table_cell["row"],
        "column": table_cell["column"],
    }
    projection = {
        "schema_version": "broker_reports_gate3_projection_v1",
        "canonical_binding": {
            "document_id": "document-gate3-contract",
            "canonical_version_id": "canonical-version-gate3-contract",
        },
        "model_view": {
            "media_type": "text/markdown",
            "content": "[t001] Brokerage fee charged\n\n[t002] Brokerage fee",
        },
        "target_mappings": [
            {"target_alias": "t001", "canonical_target": node_target},
            {"target_alias": "t002", "canonical_target": cell_target},
        ],
    }
    response = {
        "schema_version": "broker_reports_gate3_labeling_response_v1",
        "annotations": [
            {"target_alias": "t001", "financial_label": "BROKER_FEE"},
            {"target_alias": "t002", "financial_label": "BROKER_FEE"},
        ],
    }
    annotations = {
        "schema_version": "broker_reports_financial_annotations_v1",
        "canonical_binding": copy.deepcopy(projection["canonical_binding"]),
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": "1.0.0",
        },
        "instruction_identity": {
            "instruction_id": "broker-reports-bounded-semantic-labeling",
            "semantic_version": "1.0.1",
        },
        "model_identity": {"model_id": "model-exact-id"},
        "annotations": [
            {"target": node_target, "financial_label": "BROKER_FEE"},
            {"target": cell_target, "financial_label": "BROKER_FEE"},
        ],
        "validation_status": "validated",
    }
    return canonical, projection, response, annotations


def test_gate3_minimal_schemas_are_valid_and_share_one_target_grammar() -> None:
    for schema in (
        TARGET_SCHEMA,
        PROJECTION_SCHEMA,
        RESPONSE_SCHEMA,
        ANNOTATIONS_SCHEMA,
    ):
        Draft202012Validator.check_schema(schema)

    projection_ref = PROJECTION_SCHEMA["$defs"]["targetMapping"]["properties"][
        "canonical_target"
    ]["$ref"]
    annotations_ref = ANNOTATIONS_SCHEMA["$defs"]["annotation"]["properties"][
        "target"
    ]["$ref"]
    assert projection_ref == TARGET_SCHEMA_ID
    assert annotations_ref == TARGET_SCHEMA_ID


def test_gate3_contract_shapes_accept_canonical_backed_positive_examples() -> None:
    canonical, projection, response, annotations = _contract_examples()
    _validator(PROJECTION_SCHEMA).validate(projection)
    _validator(RESPONSE_SCHEMA).validate(response)
    _validator(ANNOTATIONS_SCHEMA).validate(annotations)

    canonical_node_ids = {node["node_id"] for node in canonical["nodes"]}
    for mapping in projection["target_mappings"]:
        target = mapping["canonical_target"]
        _validator(TARGET_SCHEMA).validate(target)
        assert target["node_id"] in canonical_node_ids

    table_node = next(
        node for node in canonical["nodes"] if node["node_type"] == "TABLE"
    )
    table_coordinates = {
        (cell["row"], cell["column"])
        for cell in table_node["content"]["cells"]
    }
    assert (2, 1) in table_coordinates


def test_gate3_response_is_sparse_and_empty_is_a_terminal_valid_shape() -> None:
    empty_response = {
        "schema_version": "broker_reports_gate3_labeling_response_v1",
        "annotations": [],
    }
    empty_annotations = {
        "schema_version": "broker_reports_financial_annotations_v1",
        "canonical_binding": {
            "document_id": "document-empty",
            "canonical_version_id": "canonical-version-empty",
        },
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": "1.0.0",
        },
        "instruction_identity": {
            "instruction_id": "broker-reports-bounded-semantic-labeling",
            "semantic_version": "1.0.1",
        },
        "model_identity": {"model_id": "model-exact-id"},
        "annotations": [],
        "validation_status": "validated",
    }
    _validator(RESPONSE_SCHEMA).validate(empty_response)
    _validator(ANNOTATIONS_SCHEMA).validate(empty_annotations)


@pytest.mark.parametrize(
    "mutation",
    (
        lambda value: value["annotations"][0].update({"confidence": 0.9}),
        lambda value: value["annotations"][0].update(
            {"node_id": "provider-invented-node"}
        ),
        lambda value: value.update({"reasoning": "not allowed"}),
    ),
)
def test_gate3_response_rejects_non_label_fields(mutation) -> None:
    _, _, response, _ = _contract_examples()
    mutation(response)
    with pytest.raises(ValidationError):
        _validator(RESPONSE_SCHEMA).validate(response)


@pytest.mark.parametrize(
    "target_alias",
    ("[t001]", "`t001`", "target=t001", "alias: t001", "<t001>"),
)
def test_gate3_response_schema_requires_the_bare_alias_value(
    target_alias: str,
) -> None:
    _, _, response, _ = _contract_examples()
    response["annotations"][0]["target_alias"] = target_alias
    with pytest.raises(ValidationError):
        _validator(RESPONSE_SCHEMA).validate(response)

    alias_schema = RESPONSE_SCHEMA["$defs"]["annotation"]["properties"][
        "target_alias"
    ]
    assert alias_schema["pattern"] == "^t[0-9]{3,}$"
    assert "for [t123], return t123" in alias_schema["description"]
    assert "enum" not in alias_schema


def test_gate3_projection_keeps_backend_mapping_outside_model_view() -> None:
    _, projection, _, _ = _contract_examples()
    projection["model_view"]["canonical_target"] = copy.deepcopy(
        projection["target_mappings"][0]["canonical_target"]
    )
    with pytest.raises(ValidationError):
        _validator(PROJECTION_SCHEMA).validate(projection)


def test_financial_annotations_reject_unvalidated_or_enriched_payloads() -> None:
    _, _, _, annotations = _contract_examples()
    pending = copy.deepcopy(annotations)
    pending["validation_status"] = "pending"
    with pytest.raises(ValidationError):
        _validator(ANNOTATIONS_SCHEMA).validate(pending)

    enriched = copy.deepcopy(annotations)
    enriched["annotations"][0]["confidence"] = 0.9
    with pytest.raises(ValidationError):
        _validator(ANNOTATIONS_SCHEMA).validate(enriched)


def test_gate3_target_coordinates_follow_canonical_coordinate_bases() -> None:
    valid_targets = (
        {"kind": "node", "node_id": "node-1"},
        {"kind": "list_item", "node_id": "node-list", "item_index": 0},
        {"kind": "table_row", "node_id": "node-table", "row": 1},
        {
            "kind": "table_cell",
            "node_id": "node-table",
            "row": 1,
            "column": 1,
        },
    )
    for target in valid_targets:
        _validator(TARGET_SCHEMA).validate(target)

    invalid = {
        "kind": "table_cell",
        "node_id": "node-table",
        "row": 0,
        "column": 1,
    }
    with pytest.raises(ValidationError):
        _validator(TARGET_SCHEMA).validate(invalid)


def test_gate3_product_closeout_is_ndfl_scoped_with_one_sidecar_type() -> None:
    contract = MINIMAL_CONTRACT_PATH.read_text(encoding="utf-8")
    pipeline = PIPELINE_GATES_PATH.read_text(encoding="utf-8")
    handoff = GATE3_HANDOFF_PATH.read_text(encoding="utf-8")
    authority = AUTHORITY_MAP_PATH.read_text(encoding="utf-8")

    assert (
        "Status: `CURRENT_ACTIVE_IN_NDFL_G3_C5_CLOSED`"
        in contract
    )
    assert "Implementation status: `G3.2_ACTIVE_IN_NDFL`" in contract
    assert "Dictionary implementation status: `G3.3M_ACTIVE_IN_NDFL`" in contract
    assert "Managed dictionary GUI binding: `active`" in contract
    assert "NDFL product-path activation: `true`" in contract
    assert "Chunk batch status: `G3.4C_ACTIVE_IN_NDFL`" in contract
    assert "Strict alias output status: `G3.4D_ACTIVE_IN_NDFL`" in contract
    assert "Persistence implementation status: `G3.5_ACTIVE_IN_NDFL`" in contract
    assert "Terminal proof status: `G3.C5_CLOSED`" in contract
    assert "ACTIVE_IN_NDFL" in pipeline
    assert "G3.C5_CLOSED" in pipeline
    assert "Gate3FinancialAnnotationsPersistenceFactory.create" in handoff
    assert "broker-reports-financial-labels" in handoff
    assert "broker_reports_financial_label_dictionary" in handoff
    assert "NdflWorkflowFactory.create" in handoff
    assert "broker-reports-ndfl" in handoff
    assert "actual `broker-reports-ndfl` product route end to end" in handoff
    assert "BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md" in pipeline
    assert "BROKER_REPORTS_GATE3_MINIMAL_LABELING.v1.md" in handoff
    assert "Gate 3 Minimal Labeling Contract" in authority
    assert "Gate3ProjectionFactory.create" in authority
    assert "Gate3FinancialLabelDictionaryFactory.create" in authority
    assert "Gate3FinancialAnnotationsPersistenceFactory.create" in authority
    assert "broker_reports_financial_annotations_v1" in ARTIFACT_TYPES
    assert "broker_reports_gate3_projection_v1" not in ARTIFACT_TYPES
