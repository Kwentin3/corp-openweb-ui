from __future__ import annotations

import asyncio
import copy
import hashlib

from broker_reports_gate1 import (
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.ordinary_trade_grouped_mapping_v17 import (
    ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeGroupedMappingV17AdapterFactory,
)
from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.ordinary_trade_mapping_runtime import (
    OrdinaryTradeAutomaticMappingRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
    OrdinaryTradeProjectionFactory,
)

import test_broker_reports_issue312_mapping_case as case_fixtures
import test_broker_reports_issue312_mapping_runtime as runtime_fixtures
import test_broker_reports_ordinary_trade_physical_continuation_context as continuation_fixtures


def _runtime(*, store, client):
    return OrdinaryTradeAutomaticMappingRuntimeFactory(
        store=store,
        read_enabled=True,
        model_client=client,
        mapping_response_adapter=OrdinaryTradeGroupedMappingV17AdapterFactory.create(),
        **runtime_fixtures._mapping_prompt_dependencies(),
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
    ).create()


def _v17_response(*, parent: dict, mapping: dict, child_ref: str = "table_2") -> dict:
    parent_decision = case_fixtures._complete(parent, mapping)["table_decisions"][0]
    del parent_decision["row_dispositions"]
    parent_decision["row_policy"] = {
        "default_disposition": "SECURITY_TRADES",
        "exception_rows": [],
    }
    return {
        "schema_version": ORDINARY_TRADE_GROUPED_MAPPING_V17_RESPONSE_SCHEMA_VERSION,
        "status": "COMPLETE",
        "table_decisions": [
            parent_decision,
            {
                "table_ref": "table_2",
                "header_row": None,
                "disposition": "HEADER_ABSENT",
                "columns": [],
                "amount_currency_bindings": [],
                "side_values": [],
                "row_dispositions": [],
            },
        ],
        "clarification": None,
        "message": "One strict response maps the parent and selected continuation rows.",
        "explicit_header_source_claims": {
            "schema_version": "broker_reports_ordinary_trade_explicit_header_source_response_v1",
            "claims": [
                {
                    "target_table_ref": child_ref,
                    "header_source_table_ref": "table_1",
                    "security_trade_rows": [2],
                }
            ],
        },
    }


def _case_with_source_bound_link(tmp_path):
    store, context = case_fixtures.candidate.gate4_fixtures._store_context(tmp_path)
    document_id = "v17-headerless-child-runtime-case"
    rows = []
    for suffix in ("parent", "child"):
        headers = list(case_fixtures.candidate._ROWS[0])
        if suffix == "child":
            headers[0] = f"{headers[0]} ({suffix})"
        rows.append((tuple(headers), *case_fixtures.candidate._ROWS[1:]))
    retention = build_retention_policy(mode="api_smoke")
    source_ref = "v17-headerless-child-source"
    store.put_record(
        ArtifactRecord(
            artifact_id=source_ref,
            artifact_type="source_file_ref_v0",
            case_id=context.case_id,
            chat_id=None,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref={"openwebui_file_id": "v17-headerless-child-file"},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload={"synthetic": True},
        )
    )
    source_units = []
    table_projections = []
    for table_index, table_rows in enumerate(rows, start=1):
        unit_ref = f"g4-test-table-unit-{table_index}"
        source_units.append(
            {
                "unit_ref": unit_ref,
                "source_location": {"page": table_index, "line_start": 1},
                "text": "\n".join(" ".join(row) for row in table_rows),
            }
        )
        values = [
            (row_index, column_index, value)
            for row_index, row in enumerate(table_rows, start=1)
            for column_index, value in enumerate(row, start=1)
        ]
        table_projections.append(
            {
                "projection_status": "ready",
                "reconstruction_strategy": "provider_native_table_html",
                "header_model": {"header_row_refs": ["header"] if table_index == 1 else []},
                "table_projection_id": f"v17-table-projection-{table_index}",
                "source_unit_ref": unit_ref,
                "row_count": len(table_rows),
                "column_count": max(len(row) for row in table_rows),
                "cells": [
                    {
                        "row_ordinal": row_index,
                        "column_ordinal": column_index,
                        "normalized_private_value_path": f"v-{table_index}-{row_index}-{column_index}",
                    }
                    for row_index, column_index, _value in values
                ],
                "private_values": [
                    {
                        "value_path_ref": f"v-{table_index}-{row_index}-{column_index}",
                        "normalized_value": value,
                    }
                    for row_index, column_index, value in values
                ],
            }
        )
    artifact = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="v17-headerless-child-test")
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=1,
        document={
            "container_format": "pdf",
            "sha256": hashlib.sha256(document_id.encode("utf-8")).hexdigest(),
            "declared_mime_type": "application/pdf",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "pdf_text_layer_projection": {
                    "page_inventory": [{"page_number": 1}, {"page_number": 2}],
                    "line_inventory": [],
                },
            }
        ],
        source_units=source_units,
        table_projections=table_projections,
    )
    candidate = CanonicalArtifactStoreFactory(
        store=store, config=CanonicalStorageConfig(capacity_check_enabled=False)
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=retention,
        compare_receipt=None,
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=candidate.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="v17-runtime-test",
        reason="genuine headerless child fixture",
    )
    canonical = CanonicalReaderFactory(store=store, read_enabled=True).create().read_active_envelope(
        document_id, context
    ).artifact
    tables = [node for node in canonical["nodes"] if node["node_type"] == "TABLE"]
    source_record = store.get_record_unchecked(canonical["source"]["source_artifact_ref"])
    assert source_record is not None
    assert tables[0]["content"]["metadata"]["physical_header_state"] == "PRESENT"
    assert tables[1]["content"]["metadata"]["physical_header_state"] == "ABSENT"
    assert tables[1]["content"]["header"] == []
    continuation_fixtures._persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        source_record=source_record,
        payload=continuation_fixtures._sidecar(
            context=context,
            document_id=document_id,
            source_sha=canonical["source"]["source_sha256"],
        ),
        artifact_id="v17-runtime-source-bound-link",
    )
    return store, context, document_id, tables


def test_v17_one_call_persists_continuation_and_projects_only_claimed_child_rows(tmp_path) -> None:
    """Target seam: strict V17 remains one call through case and projection owners."""

    store, context, document_id, tables = _case_with_source_bound_link(tmp_path)
    mapping = case_fixtures.candidate._mapping_from_headers(
        tuple(
            cell["displayed_value"]
            for cell in sorted(
                (cell for cell in tables[0]["content"]["cells"] if cell["row"] == 1),
                key=lambda cell: cell["column"],
            )
        )
    )
    client = runtime_fixtures.BoundaryModelClient(
        [_v17_response(parent=tables[0], mapping=mapping)]
    )

    result = asyncio.run(
        _runtime(store=store, client=client).resolve(
            document_id=document_id, context=context
        )
    )

    assert result["status"] == "COMPLETE"
    assert result["provider_calls_this_turn"] == 1
    assert len(client.calls) == 1
    assert [table["table_ref"] for table in client.calls[0]["package"]["case"]["tables"]] == [
        "table_1",
        "table_2",
    ]
    saved = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create().current(
        document_id=document_id, context=context
    )[1]
    assert saved["explicit_header_source_continuations"]
    projections = OrdinaryTradeProjectionFactory(store=store, read_enabled=True).create()
    projection = projections.compile_and_save(
        document_id=document_id, context=context
    )
    assert projection.artifact_type == ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE
    projection_payload = projections.read(
        artifact_id=projection.artifact_id, context=context
    )
    child_records = [
        record
        for record in projection_payload["runtime_records"]
        if record["annotation_target"]["node_id"] == tables[1]["node_id"]
    ]
    assert {record["annotation_target"]["row"] for record in child_records} == {2}


def test_v17_forged_child_link_is_terminal_and_never_projects(tmp_path) -> None:
    store, context, document_id, tables = _case_with_source_bound_link(tmp_path)
    mapping = case_fixtures.candidate._mapping_from_headers(
        tuple(cell["displayed_value"] for cell in sorted(
            (cell for cell in tables[0]["content"]["cells"] if cell["row"] == 1),
            key=lambda cell: cell["column"],
        ))
    )
    response = _v17_response(parent=tables[0], mapping=mapping, child_ref="table_3")
    client = runtime_fixtures.BoundaryModelClient([copy.deepcopy(response)])

    result = asyncio.run(
        _runtime(store=store, client=client).resolve(
            document_id=document_id, context=context
        )
    )

    assert result["status"] == "MAPPING_OUTPUT_INVALID"
    assert result["provider_calls_this_turn"] == 1
    assert len(client.calls) == 1
    saved = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create().current(
        document_id=document_id, context=context
    )[1]
    assert saved["reason_code"] == "ordinary_trade_explicit_header_source_invalid"
    assert store.list_by_type(
        context.normalization_run_id, ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE
    ) == []
