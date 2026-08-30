from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

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
from broker_reports_gate1.ordinary_trade_document_role_receipt import (
    DECLARATION_METADATA_INPUT_ROLE,
    ORDINARY_TRADE_DECLARATION_WORKFLOW_ID,
    WORKFLOW_DOCUMENT_ROLE_RECEIPT_ARTIFACT_TYPE,
    WORKFLOW_DOCUMENT_ROLE_RECEIPT_SCHEMA_VERSION,
    WORKFLOW_DOCUMENT_ROLE_SOURCE,
    OrdinaryTradeDocumentRoleReceiptError,
    OrdinaryTradeDocumentRoleReceiptRuntimeFactory,
)

import test_broker_reports_gate4_sql_materialization as gate4_fixtures


def test_fixed_role_registration_is_deterministic_private_and_current(
    tmp_path: Path,
) -> None:
    store, context, canonical = _case(tmp_path)
    runtime = _runtime(store)

    first = runtime.register_declaration_metadata_input(
        canonical_artifact_ref=canonical.artifact_ref,
        context=context,
    )
    second = runtime.register_declaration_metadata_input(
        canonical_artifact_ref=canonical.artifact_ref,
        context=context,
    )
    validated = runtime.validate_current(receipt=first, context=context)
    record = store.get_record_unchecked(first["receipt_id"])
    active = store.get_active_canonical_version(
        context=context,
        document_id="workflow-metadata-document",
    )

    assert first == second == validated
    assert first["schema_version"] == (
        WORKFLOW_DOCUMENT_ROLE_RECEIPT_SCHEMA_VERSION
    )
    assert first["workflow_id"] == ORDINARY_TRADE_DECLARATION_WORKFLOW_ID
    assert first["role"] == DECLARATION_METADATA_INPUT_ROLE
    assert first["role_source"] == WORKFLOW_DOCUMENT_ROLE_SOURCE
    assert first["canonical_binding"] == {
        "document_id": "workflow-metadata-document",
        "canonical_version_id": canonical.canonical_version_id,
        "canonical_root_sha256": active.canonical_root_sha256,
        "manifest_ref": canonical.artifact_ref,
        "source_artifact_ref": "g4-runtime-source-workflow-metadata-document-1",
        "source_sha256": hashlib.sha256(
            b"g4-runtime-workflow-metadata-document-1"
        ).hexdigest(),
    }
    assert first["scope_binding"] == {
        "authenticated_user_ref": context.user_id,
        "case_id": context.case_id,
        "workspace_model_id": context.workspace_model_id,
        "normalization_run_id": context.normalization_run_id,
    }
    assert first["receipt_id"] == (
        "workflow_doc_role_" + first["receipt_sha256"][:32]
    )
    assert record is not None
    assert record.artifact_type == WORKFLOW_DOCUMENT_ROLE_RECEIPT_ARTIFACT_TYPE
    assert record.visibility == "private_case"
    assert record.storage_backend == "project_artifact_payload"
    assert record.document_id == "workflow-metadata-document"
    assert store.read_payload(record) == first
    assert record.access_policy["production_consumer_enabled"] is False
    assert sum(
        item.artifact_type == WORKFLOW_DOCUMENT_ROLE_RECEIPT_ARTIFACT_TYPE
        for item in store.list_by_case_context(context)
    ) == 1


def test_recomputed_hash_cannot_rebind_current_canonical(
    tmp_path: Path,
) -> None:
    store, context, canonical = _case(tmp_path)
    runtime = _runtime(store)
    receipt = runtime.register_declaration_metadata_input(
        canonical_artifact_ref=canonical.artifact_ref,
        context=context,
    )
    forged = copy.deepcopy(receipt)
    forged["canonical_binding"]["canonical_root_sha256"] = "f" * 64
    forged = _reseal(forged)
    _persist_forged(
        store=store,
        context=context,
        manifest_ref=canonical.artifact_ref,
        forged=forged,
    )

    with pytest.raises(OrdinaryTradeDocumentRoleReceiptError) as error:
        runtime.validate_current(receipt=forged, context=context)

    assert error.value.code == "workflow_document_role_stale"


def test_recomputed_hash_cannot_rebind_source_artifact(
    tmp_path: Path,
) -> None:
    store, context, canonical = _case(tmp_path)
    other = _activate_canonical(
        store=store,
        context=context,
        document_id="foreign-source-document",
        artifact_version=1,
        expected_previous_version_id=None,
        source_rows=("Broker: Other",),
    )
    assert other.artifact_ref
    runtime = _runtime(store)
    receipt = runtime.register_declaration_metadata_input(
        canonical_artifact_ref=canonical.artifact_ref,
        context=context,
    )
    forged = copy.deepcopy(receipt)
    forged["canonical_binding"]["source_artifact_ref"] = (
        "g4-runtime-source-foreign-source-document-1"
    )
    forged = _reseal(forged)
    _persist_forged(
        store=store,
        context=context,
        manifest_ref=canonical.artifact_ref,
        forged=forged,
    )

    with pytest.raises(OrdinaryTradeDocumentRoleReceiptError) as error:
        runtime.validate_current(receipt=forged, context=context)

    assert error.value.code == "workflow_document_role_binding_mismatch"


@pytest.mark.parametrize(
    ("changed", "expected"),
    (
        ({"user_id": "foreign-user"}, "workflow_document_role_scope_mismatch"),
        ({"case_id": "foreign-case"}, "workflow_document_role_scope_mismatch"),
        (
            {"workspace_model_id": "foreign-workspace"},
            "workflow_document_role_scope_mismatch",
        ),
    ),
)
def test_foreign_scope_cannot_validate_role_receipt(
    tmp_path: Path,
    changed: dict[str, str],
    expected: str,
) -> None:
    store, context, canonical = _case(tmp_path)
    runtime = _runtime(store)
    receipt = runtime.register_declaration_metadata_input(
        canonical_artifact_ref=canonical.artifact_ref,
        context=context,
    )

    with pytest.raises(OrdinaryTradeDocumentRoleReceiptError) as error:
        runtime.validate_current(
            receipt=receipt,
            context=replace(context, **changed),
        )

    assert error.value.code == expected


def test_successor_canonical_makes_old_receipt_stale(
    tmp_path: Path,
) -> None:
    store, context, canonical = _case(tmp_path)
    runtime = _runtime(store)
    old = runtime.register_declaration_metadata_input(
        canonical_artifact_ref=canonical.artifact_ref,
        context=context,
    )
    successor_context = replace(
        context,
        normalization_run_id="workflow-role-successor-run",
    )
    successor = _activate_canonical(
        store=store,
        context=successor_context,
        document_id="workflow-metadata-document",
        artifact_version=2,
        expected_previous_version_id=canonical.canonical_version_id,
        source_rows=("Broker: Example", "Account number: SECOND"),
    )

    with pytest.raises(OrdinaryTradeDocumentRoleReceiptError) as error:
        runtime.validate_current(receipt=old, context=successor_context)

    assert error.value.code == "workflow_document_role_stale"
    current = runtime.register_declaration_metadata_input(
        canonical_artifact_ref=successor.artifact_ref,
        context=successor_context,
    )
    assert current["receipt_id"] != old["receipt_id"]
    assert (
        runtime.validate_current(receipt=current, context=successor_context)
        == current
    )


def test_conflicting_receipt_for_same_canonical_fails_closed(
    tmp_path: Path,
) -> None:
    store, context, canonical = _case(tmp_path)
    runtime = _runtime(store)
    receipt = runtime.register_declaration_metadata_input(
        canonical_artifact_ref=canonical.artifact_ref,
        context=context,
    )
    conflicting = copy.deepcopy(receipt)
    conflicting["scope_binding"]["normalization_run_id"] = "conflicting-run"
    conflicting = _reseal(conflicting)
    _persist_forged(
        store=store,
        context=replace(context, normalization_run_id="conflicting-run"),
        manifest_ref=canonical.artifact_ref,
        forged=conflicting,
    )

    with pytest.raises(OrdinaryTradeDocumentRoleReceiptError) as error:
        runtime.validate_current(receipt=receipt, context=context)

    assert error.value.code == "workflow_document_role_conflict"


def test_recomputed_run_binding_cannot_replace_owner_run(
    tmp_path: Path,
) -> None:
    store, context, canonical = _case(tmp_path)
    runtime = _runtime(store)
    forged = _receipt_for_current(
        store=store,
        context=context,
        canonical=canonical,
        normalization_run_id="forged-owner-run",
    )
    _persist_forged(
        store=store,
        context=replace(context, normalization_run_id="forged-owner-run"),
        manifest_ref=canonical.artifact_ref,
        forged=forged,
    )

    with pytest.raises(OrdinaryTradeDocumentRoleReceiptError) as error:
        runtime.validate_current(receipt=forged, context=context)

    assert error.value.code == "workflow_document_role_binding_mismatch"


def test_registration_rejects_source_owner_with_wrong_byte_hash(
    tmp_path: Path,
) -> None:
    store, context = gate4_fixtures._store_context(tmp_path)
    canonical = _activate_canonical(
        store=store,
        context=context,
        document_id="wrong-source-hash-document",
        artifact_version=1,
        expected_previous_version_id=None,
        source_rows=("Broker: Example",),
        source_file_hash_override="e" * 64,
    )

    with pytest.raises(OrdinaryTradeDocumentRoleReceiptError) as error:
        _runtime(store).register_declaration_metadata_input(
            canonical_artifact_ref=canonical.artifact_ref,
            context=context,
        )

    assert error.value.code == "workflow_document_role_source_invalid"


def test_deleted_source_owner_cannot_register_or_revalidate(
    tmp_path: Path,
) -> None:
    store, context, canonical = _case(tmp_path)
    runtime = _runtime(store)
    receipt = runtime.register_declaration_metadata_input(
        canonical_artifact_ref=canonical.artifact_ref,
        context=context,
    )
    source_artifact_ref = receipt["canonical_binding"]["source_artifact_ref"]
    source_record = store.get_record_unchecked(source_artifact_ref)
    assert source_record is not None
    deleted_source_ref = {**source_record.source_file_ref, "source_deleted": True}
    with sqlite3.connect(store.sqlite_path) as connection:
        changed = connection.execute(
            "UPDATE artifact_records SET source_file_ref_json = ? "
            "WHERE artifact_id = ?",
            (
                json.dumps(deleted_source_ref, sort_keys=True),
                source_artifact_ref,
            ),
        ).rowcount
    assert changed == 1

    with pytest.raises(OrdinaryTradeDocumentRoleReceiptError) as error:
        runtime.validate_current(receipt=receipt, context=context)

    assert error.value.code == "workflow_document_role_binding_unavailable"


def test_registration_requires_private_case_and_active_canonical(
    tmp_path: Path,
) -> None:
    store, context, canonical = _case(tmp_path)
    runtime = _runtime(store)

    with pytest.raises(OrdinaryTradeDocumentRoleReceiptError) as private_error:
        runtime.register_declaration_metadata_input(
            canonical_artifact_ref=canonical.artifact_ref,
            context=replace(context, allow_private=False),
        )
    assert private_error.value.code == "workflow_document_role_private_case_required"

    candidate = _activate_canonical(
        store=store,
        context=context,
        document_id="other-active-document",
        artifact_version=1,
        expected_previous_version_id=None,
        source_rows=("Broker: Other",),
    )
    assert candidate.artifact_ref
    with pytest.raises(OrdinaryTradeDocumentRoleReceiptError) as foreign_error:
        runtime.register_declaration_metadata_input(
            canonical_artifact_ref=candidate.artifact_ref,
            context=replace(context, user_id="foreign-user"),
        )
    assert foreign_error.value.code == "workflow_document_role_canonical_invalid"


def _case(tmp_path: Path):
    store, context = gate4_fixtures._store_context(tmp_path)
    canonical = _activate_canonical(
        store=store,
        context=context,
        document_id="workflow-metadata-document",
        artifact_version=1,
        expected_previous_version_id=None,
        source_rows=("Broker: Example", "Account number: PRIMARY"),
    )
    assert canonical.artifact_ref
    return store, context, canonical


def _activate_canonical(
    *,
    store,
    context,
    document_id: str,
    artifact_version: int,
    expected_previous_version_id: str | None,
    source_rows: tuple[str, ...],
    source_file_hash_override: str | None = None,
):
    retention = build_retention_policy(mode="api_smoke")
    source_ref = f"g4-runtime-source-{document_id}-{artifact_version}"
    source_bytes = f"g4-runtime-{document_id}-{artifact_version}".encode()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    source_file_ref = {
        "provider": "synthetic_test",
        "openwebui_file_id": f"synthetic-g4-file-{document_id}-{artifact_version}",
        "file_hash_sha256": source_file_hash_override or source_sha256,
        "content_type": "text/html",
        "size_bytes": len(source_bytes),
        "source_deleted": False,
        "source_delete_observed_at": None,
    }
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
            source_file_ref=copy.deepcopy(source_file_ref),
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload=copy.deepcopy(source_file_ref),
        )
    )
    artifact = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(
            normalizer_version=f"workflow-role-test-v{artifact_version}"
        )
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=artifact_version,
        document={
            "container_format": "html_text",
            "sha256": source_sha256,
            "declared_mime_type": "text/html",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "canonical_projection": {
                    "blocks": [
                        {
                            "kind": "text",
                            "text": text,
                            "source_location": {"block_index": index},
                        }
                        for index, text in enumerate(source_rows, start=1)
                    ]
                }
            }
        ],
        source_units=[],
        table_projections=[],
    )
    canonical = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(capacity_check_enabled=False),
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=retention,
        compare_receipt=None,
    )
    CanonicalReaderFactory(store=store, read_enabled=True).create().activate(
        canonical_version_id=canonical.canonical_version_id,
        expected_previous_version_id=expected_previous_version_id,
        context=context,
        actor="workflow-document-role-test",
        reason="workflow document role receipt test",
    )
    return canonical


def _runtime(store):
    return OrdinaryTradeDocumentRoleReceiptRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()


def _reseal(receipt: dict) -> dict:
    material = copy.deepcopy(receipt)
    material.pop("receipt_id", None)
    material.pop("receipt_sha256", None)
    digest = _sha(material)
    return {
        **material,
        "receipt_id": "workflow_doc_role_" + digest[:32],
        "receipt_sha256": digest,
    }


def _receipt_for_current(
    *,
    store,
    context,
    canonical,
    normalization_run_id: str,
) -> dict:
    manifest = store.get_record_unchecked(canonical.artifact_ref)
    assert manifest is not None
    active = store.get_active_canonical_version(
        context=context,
        document_id=manifest.document_id,
    )
    source_ref = manifest.source_file_ref
    source_record = store.get_record_unchecked(active.source_artifact_ref)
    assert source_record is not None
    material = {
        "schema_version": WORKFLOW_DOCUMENT_ROLE_RECEIPT_SCHEMA_VERSION,
        "workflow_id": ORDINARY_TRADE_DECLARATION_WORKFLOW_ID,
        "role": DECLARATION_METADATA_INPUT_ROLE,
        "role_source": WORKFLOW_DOCUMENT_ROLE_SOURCE,
        "canonical_binding": {
            "document_id": manifest.document_id,
            "canonical_version_id": canonical.canonical_version_id,
            "canonical_root_sha256": active.canonical_root_sha256,
            "manifest_ref": canonical.artifact_ref,
            "source_artifact_ref": active.source_artifact_ref,
            "source_sha256": active.source_sha256,
        },
        "scope_binding": {
            "authenticated_user_ref": context.user_id,
            "case_id": context.case_id,
            "workspace_model_id": context.workspace_model_id,
            "normalization_run_id": normalization_run_id,
        },
        "source_file_ref_sha256": _sha(source_ref),
    }
    return _reseal(material)


def _persist_forged(
    *,
    store,
    context,
    manifest_ref: str,
    forged: dict,
) -> None:
    manifest_record = store.get_record_unchecked(manifest_ref)
    assert manifest_record is not None
    store.put_record(
        ArtifactRecord(
            artifact_id=forged["receipt_id"],
            artifact_type=WORKFLOW_DOCUMENT_ROLE_RECEIPT_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=forged["scope_binding"]["normalization_run_id"],
            document_id=forged["canonical_binding"]["document_id"],
            source_file_ref=copy.deepcopy(manifest_record.source_file_ref),
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=manifest_record.retention_policy,
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": bool(
                    context.workspace_model_id
                ),
                "workflow_document_role_receipt_only": True,
                "production_consumer_enabled": False,
            },
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload_kind="json_file",
            payload=copy.deepcopy(forged),
            safe_metadata={"forged_test_artifact": True},
        )
    )


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
