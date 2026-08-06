from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    CANONICAL_OK,
    CanonicalArtifactStoreFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    FileInput,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
)
from broker_reports_gate1.canonical_wave2_shadow import (
    WAVE2_SHADOW_CONTRACTS,
    CanonicalWave2ShadowFactory,
)


def _published(root: Path):
    result = Gate1Normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="doc29-test-source",
                filename="source.html",
                content=b"<html><body><h1>Statement</h1><p>Value 1</p></body></html>",
                mime_type="text/html",
            )
        ],
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_compare_enabled": True,
            "canonical_gate2_read_enabled": False,
        },
    )
    run_id = result.package["normalization_run"]["run_id"]
    context = ArtifactAccessContext(
        user_id="doc29-user",
        normalization_run_id=run_id,
        case_id="doc29-case",
        workspace_model_id="doc29-workspace",
        allow_private=True,
        require_source_available=True,
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    manifest = persist_gate1_result(
        store=store,
        result=result,
        context=context,
        retention_policy=build_retention_policy(
            mode="manual_purge_required", explicit=True
        ),
        source_file_refs=[
            {
                "provider": "doc29-test",
                "openwebui_file_id": "doc29-test-file",
                "file_hash_sha256": "a" * 64,
                "content_type": "text/html",
                "size_bytes": 61,
            }
        ],
    )
    manifest_ref = manifest.artifact_refs_by_type[
        "broker_reports_canonical_artifact_v1"
    ][0]
    version = store.get_canonical_version_by_manifest(
        context=context, manifest_ref=manifest_ref
    )
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    reader.activate(
        canonical_version_id=version.canonical_version_id,
        expected_previous_version_id=None,
        context=context,
        actor="doc29-test",
        reason="terminal shadow fixture",
    )
    return store, context, version.document_id


def test_wave2_shadow_contracts_are_terminal_stable_and_side_effect_free() -> None:
    assert len(WAVE2_SHADOW_CONTRACTS) == 6
    assert len({item.consumer_id for item in WAVE2_SHADOW_CONTRACTS}) == 6
    with tempfile.TemporaryDirectory() as temp_dir:
        store, context, document_id = _published(Path(temp_dir))
        for contract in WAVE2_SHADOW_CONTRACTS:
            outputs = []
            for _ in range(3):
                result = CanonicalWave2ShadowFactory(
                    store=store, contract=contract, enabled=True
                ).create().read_active(document_id=document_id, context=context)
                assert result.compatibility_status == CANONICAL_OK
                assert result.output is not None
                assert result.output["provider_requests"] == 0
                assert result.output["product_writes"] == 0
                assert result.output["notifications"] == 0
                assert result.output["financial_facts_created"] == 0
                assert result.output["legacy_fallback"] is False
                outputs.append(result.output)
            assert outputs[0] == outputs[1] == outputs[2]


def test_wave2_shadow_flag_and_cross_tenant_access_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        store, context, document_id = _published(Path(temp_dir))
        contract = WAVE2_SHADOW_CONTRACTS[0]
        disabled = CanonicalWave2ShadowFactory(
            store=store, contract=contract, enabled=False
        ).create().read_active(document_id=document_id, context=context)
        assert disabled.compatibility_status == "CANONICAL_INCOMPLETE"
        assert disabled.error_code == "canonical_read_disabled"
        assert disabled.output is None

        other = ArtifactAccessContext(
            user_id="doc29-other-user",
            normalization_run_id=context.normalization_run_id,
            case_id=context.case_id,
            workspace_model_id=context.workspace_model_id,
            allow_private=True,
            require_source_available=True,
        )
        denied = CanonicalWave2ShadowFactory(
            store=store, contract=contract, enabled=True
        ).create().read_active(document_id=document_id, context=other)
        assert denied.compatibility_status in {
            "CANONICAL_ACCESS_DENIED",
            "CANONICAL_INCOMPLETE",
        }
        assert denied.error_code in {
            "artifact_access_denied",
            "canonical_version_not_active",
        }
        assert denied.output is None


def test_capacity_policy_rejects_before_any_version_reservation() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        context = ArtifactAccessContext(
            user_id="doc29-user",
            normalization_run_id="doc29-capacity-run",
            case_id="doc29-case",
            allow_private=True,
        )
        with pytest.raises(ArtifactStoreError) as blocked:
            CanonicalArtifactStoreFactory(
                store=store,
                config=CanonicalStorageConfig(maximum_artifact_bytes=1),
            ).create().put_candidate(
                artifact={"tenant_id": context.user_id},
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
                compare_receipt=None,
            )
        assert blocked.value.code == "canonical_artifact_too_large"
        assert store.list_canonical_versions(
            context=ArtifactAccessContext(
                user_id=context.user_id,
                normalization_run_id=context.normalization_run_id,
                case_id=context.case_id,
                allow_private=True,
            ),
            document_id="missing",
        ) == []
