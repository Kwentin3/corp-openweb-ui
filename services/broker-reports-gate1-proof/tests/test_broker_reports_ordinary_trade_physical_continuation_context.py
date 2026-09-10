from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import (
    PHYSICAL_TABLE_CONTINUATION_ARTIFACT_TYPE,
    ArtifactRecord,
)
from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseError,
    OrdinaryTradeMappingCaseFactory,
)
from broker_reports_gate1.physical_table_continuation import (
    build_physical_table_continuation_sidecar,
    validate_physical_table_continuation_sidecar,
)

import test_broker_reports_gate4_sql_materialization as gate4_fixtures
import test_broker_reports_issue312_mapping_runtime as runtime_fixtures
from test_broker_reports_physical_table_continuation import _annotation_receipt


_ROWS = (("Date", "Amount"), ("2026-01-10", "100.00"))
_SOURCE_SHA = "a" * 64


def _case(tmp_path):
    store, context = gate4_fixtures._store_context(tmp_path)
    document_id = "physical-continuation-mapping-case"
    gate4_fixtures._activate_canonical(
        store=store,
        context=context,
        document_id=document_id,
        artifact_version=1,
        expected_previous_version_id=None,
        table_row_sets=(_ROWS, _ROWS),
    )
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    envelope = reader.read_active_envelope(document_id, context)
    source_record = store.get_record_unchecked(
        envelope.artifact["source"]["source_artifact_ref"]
    )
    assert source_record is not None
    return store, context, document_id, envelope, source_record


def _sidecar(*, context, document_id: str, source_sha: str) -> dict:
    units = [
        {
            "unit_ref": "g4-test-table-unit-1",
            "normalization_run_id": context.normalization_run_id,
            "document_id": document_id,
            "source_checksum_sha256": source_sha,
            "document_ai_native_table_ref": "native-table-1",
            "document_ai_native_table_sha256": "b" * 64,
            "source_location": {"page": 1},
        },
        {
            "unit_ref": "g4-test-table-unit-2",
            "normalization_run_id": context.normalization_run_id,
            "document_id": document_id,
            "source_checksum_sha256": source_sha,
            "document_ai_native_table_ref": "native-table-2",
            "document_ai_native_table_sha256": "c" * 64,
            "source_location": {"page": 2},
        },
    ]
    return build_physical_table_continuation_sidecar(
        normalization_run_id=context.normalization_run_id,
        document_id=document_id,
        source_pdf_sha256=source_sha,
        source_units=units,
        proposed_links=[
            {
                "parent": {
                    "native_table_ref": "native-table-1",
                    "native_table_sha256": "b" * 64,
                    "page_number": 1,
                },
                "child": {
                    "native_table_ref": "native-table-2",
                    "native_table_sha256": "c" * 64,
                    "page_number": 2,
                },
            }
        ],
        annotation_receipt=_annotation_receipt(),
    )


def _persist_sidecar(
    *,
    store,
    context,
    document_id: str,
    source_record: ArtifactRecord,
    payload: dict,
    artifact_id: str,
    user_id: str | None = None,
    source_file_ref: dict | None = None,
    validate_payload: bool = True,
) -> ArtifactRecord:
    if validate_payload:
        validate_physical_table_continuation_sidecar(payload)
    record = ArtifactRecord(
        artifact_id=artifact_id,
        artifact_type=PHYSICAL_TABLE_CONTINUATION_ARTIFACT_TYPE,
        case_id=source_record.case_id,
        chat_id=source_record.chat_id,
        user_id=user_id or source_record.user_id,
        workspace_model_id=source_record.workspace_model_id,
        normalization_run_id=context.normalization_run_id,
        document_id=document_id,
        source_file_ref=copy.deepcopy(
            source_record.source_file_ref if source_file_ref is None else source_file_ref
        ),
        visibility="private_case",
        storage_backend="project_artifact_payload",
        retention_policy=source_record.retention_policy,
        access_policy={"requires_user_id": True},
        validation_status="validated",
        lifecycle_status=lifecycle_for_visibility(
            visibility="private_case", validation_status="validated"
        ),
        payload=copy.deepcopy(payload),
    )
    return store.put_record(record)


def test_case_binding_exposes_exact_private_context_without_mutating_canonical(tmp_path) -> None:
    store, context, document_id, envelope, source_record = _case(tmp_path)
    source_sha = envelope.artifact["source"]["source_sha256"]
    _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        source_record=source_record,
        payload=_sidecar(context=context, document_id=document_id, source_sha=source_sha),
        artifact_id="physical-sidecar-exact",
    )
    before = copy.deepcopy(envelope.artifact)

    binding = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().case_binding(document_id=document_id, context=context)

    assert binding["canonical"] == before
    assert binding["physical_table_continuation_context"] == {
        "schema_version": "broker_reports_physical_table_continuation_context_v1",
        "sidecar_artifact_ref": "physical-sidecar-exact",
        "sidecar_id": binding["physical_table_continuation_context"]["sidecar_id"],
        "source_binding": {
            "normalization_run_id": context.normalization_run_id,
            "document_id": document_id,
            "source_artifact_ref": source_record.artifact_id,
            "source_sha256": source_sha,
            "canonical_version_id": binding["canonical_binding"]["canonical_version_id"],
            "canonical_root_sha256": binding["canonical_binding"]["canonical_root_sha256"],
        },
        "links": [
            {
                "parent_table_node_id": next(
                    node["node_id"]
                    for node in before["nodes"]
                    if node["node_type"] == "TABLE"
                    and any(
                        (item.get("source_locator") or {}).get("source_unit_ref")
                        == "g4-test-table-unit-1"
                        for item in before["provenance"]
                        if item["provenance_id"] in node["source_refs"]
                    )
                ),
                "child_table_node_id": next(
                    node["node_id"]
                    for node in before["nodes"]
                    if node["node_type"] == "TABLE"
                    and any(
                        (item.get("source_locator") or {}).get("source_unit_ref")
                        == "g4-test-table-unit-2"
                        for item in before["provenance"]
                        if item["provenance_id"] in node["source_refs"]
                    )
                ),
            }
        ],
    }


def test_mapping_case_receipt_binds_sidecar_identity_without_storing_links(tmp_path) -> None:
    store, context, document_id, envelope, source_record = _case(tmp_path)
    _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        source_record=source_record,
        payload=_sidecar(
            context=context,
            document_id=document_id,
            source_sha=envelope.artifact["source"]["source_sha256"],
        ),
        artifact_id="physical-sidecar-bound-receipt",
    )
    cases = OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create()
    binding = cases.case_binding(document_id=document_id, context=context)

    record, payload = cases.save_provider_terminal(
        document_id=document_id,
        context=context,
        status="PROVIDER_UNAVAILABLE",
        reason_code="test_terminal",
        message="No provider call was made.",
        provider_calls_total=0,
        mapping_prompt_snapshot=runtime_fixtures._test_mapping_prompt().snapshot(),
    )

    expected = binding["physical_table_continuation_binding"]
    assert record.artifact_type == "broker_reports_ordinary_trade_mapping_case_v6"
    assert payload["schema_version"] == "broker_reports_ordinary_trade_mapping_case_v6"
    assert payload["case_binding"]["physical_table_continuation_binding"] == expected
    assert "parent_table_node_id" not in str(payload["case_binding"])
    assert "physical-sidecar-bound-receipt" in str(payload["case_binding"])


def test_case_binding_rejects_tampered_private_sidecar_before_semantic_mapping(tmp_path) -> None:
    store, context, document_id, envelope, source_record = _case(tmp_path)
    payload = _sidecar(
        context=context,
        document_id=document_id,
        source_sha=envelope.artifact["source"]["source_sha256"],
    )
    payload["sidecar_id"] = "ptcont_tampered"
    _persist_sidecar(
        store=store, context=context, document_id=document_id,
        source_record=source_record, payload=payload, artifact_id="physical-sidecar-tampered",
        validate_payload=False,
    )

    with pytest.raises(OrdinaryTradeMappingCaseError, match="physical_table_continuation_context_sidecar_invalid"):
        OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create().case_binding(
            document_id=document_id, context=context
        )


def test_case_binding_rejects_stale_or_ambiguous_private_sidecar(tmp_path) -> None:
    store, context, document_id, envelope, source_record = _case(tmp_path)
    payload = _sidecar(context=context, document_id=document_id, source_sha=_SOURCE_SHA)
    _persist_sidecar(
        store=store, context=context, document_id=document_id,
        source_record=source_record, payload=payload, artifact_id="physical-sidecar-stale",
    )
    with pytest.raises(OrdinaryTradeMappingCaseError, match="physical_table_continuation_context_binding_stale"):
        OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create().case_binding(
            document_id=document_id, context=context
        )

    store, context, document_id, envelope, source_record = _case(tmp_path / "ambiguous")
    payload = _sidecar(
        context=context, document_id=document_id,
        source_sha=envelope.artifact["source"]["source_sha256"],
    )
    for artifact_id in ("physical-sidecar-one", "physical-sidecar-two"):
        _persist_sidecar(
            store=store, context=context, document_id=document_id,
            source_record=source_record, payload=payload, artifact_id=artifact_id,
        )
    with pytest.raises(OrdinaryTradeMappingCaseError, match="ordinary_trade_mapping_case_physical_continuation_ambiguous"):
        OrdinaryTradeMappingCaseFactory(store=store, read_enabled=True).create().case_binding(
            document_id=document_id, context=context
        )


def test_case_binding_does_not_read_foreign_sidecar(tmp_path) -> None:
    store, context, document_id, envelope, source_record = _case(tmp_path)
    _persist_sidecar(
        store=store,
        context=context,
        document_id=document_id,
        source_record=source_record,
        payload=_sidecar(
            context=context,
            document_id=document_id,
            source_sha=envelope.artifact["source"]["source_sha256"],
        ),
        artifact_id="physical-sidecar-foreign",
        user_id="another-user",
    )

    binding = OrdinaryTradeMappingCaseFactory(
        store=store, read_enabled=True
    ).create().case_binding(document_id=document_id, context=context)

    assert binding["physical_table_continuation_context"] is None
