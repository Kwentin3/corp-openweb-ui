"""Real-store contract tests for exact authenticated source-file bindings."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import sqlite3

import pytest

from broker_reports_gate1.artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.artifact_store import (
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)


def test_resolves_one_payload_free_binding_in_its_authenticated_scope() -> None:
    with _store() as store:
        context = _context()
        source = _put_source(store, context=context, artifact_id="source-1")

        binding = ArtifactResolver(store).resolve_authenticated_source_file_binding(
            context=context,
            openwebui_file_id="file-1",
        )

        assert binding.document_id == "document-1"
        assert binding.normalization_run_id == "run-1"
        assert binding.source_artifact_id == source.artifact_id
        assert binding.file_hash_sha256 == "a" * 64
        stored = store.find_source_file_records_by_authenticated_scope(
            context=context,
            openwebui_file_id="file-1",
        )
        assert len(stored) == 1
        assert stored[0].payload is None
        assert stored[0].payload_ref is None


def test_binding_lookup_does_not_read_private_payload_columns(monkeypatch) -> None:
    with _store() as store:
        context = _context()
        _put_source(store, context=context, artifact_id="source-1")
        connect = store._connect

        @contextmanager
        def payload_denied_connection(*, immediate: bool = False):
            with connect(immediate=immediate) as connection:

                def deny_payload_reads(action, _arg1, column, _db, _trigger):
                    if action == sqlite3.SQLITE_READ and column in {
                        "payload_ref",
                        "payload_inline_json",
                    }:
                        return sqlite3.SQLITE_DENY
                    return sqlite3.SQLITE_OK

                connection.set_authorizer(deny_payload_reads)
                yield connection

        monkeypatch.setattr(store, "_connect", payload_denied_connection)

        binding = ArtifactResolver(store).resolve_authenticated_source_file_binding(
            context=context,
            openwebui_file_id="file-1",
        )

        assert binding.source_artifact_id == "source-1"


def test_refuses_foreign_user_case_or_workspace_without_disclosure() -> None:
    with _store() as store:
        _put_source(store, context=_context(), artifact_id="source-1")
        for foreign_context in (
            _context(user_id="other-user"),
            _context(case_id="other-case"),
            _context(workspace_model_id="other-workspace"),
        ):
            with pytest.raises(ArtifactStoreError) as missing:
                ArtifactResolver(store).resolve_authenticated_source_file_binding(
                    context=foreign_context,
                    openwebui_file_id="file-1",
                )
            assert missing.value.code == "source_file_binding_not_found"


def test_refuses_foreign_chat_scope_without_disclosure() -> None:
    with _store() as store:
        owner_context = _context(case_id=None, chat_id="chat-1")
        _put_source(store, context=owner_context, artifact_id="source-1")

        with pytest.raises(ArtifactStoreError) as missing:
            ArtifactResolver(store).resolve_authenticated_source_file_binding(
                context=replace(owner_context, chat_id="other-chat"),
                openwebui_file_id="file-1",
            )

        assert missing.value.code == "source_file_binding_not_found"


@pytest.mark.parametrize(
    "source_deleted,lifecycle_status,purge_status,expected_code",
    (
        (True, "private_ready", "active", "source_file_unavailable"),
        (False, "purged", "purged", "artifact_purged"),
    ),
)
def test_refuses_deleted_or_unavailable_source(
    source_deleted: bool,
    lifecycle_status: str,
    purge_status: str,
    expected_code: str,
) -> None:
    with _store() as store:
        _put_source(
            store,
            context=_context(),
            artifact_id="source-1",
            source_deleted=source_deleted,
            lifecycle_status=lifecycle_status,
            purge_status=purge_status,
        )

        with pytest.raises(ArtifactStoreError) as unavailable:
            ArtifactResolver(store).resolve_authenticated_source_file_binding(
                context=_context(),
                openwebui_file_id="file-1",
            )

        assert unavailable.value.code == expected_code


def test_refuses_source_binding_with_an_invalid_checksum() -> None:
    with _store() as store:
        _put_source(
            store,
            context=_context(),
            artifact_id="source-1",
            file_hash_sha256="not-a-sha256",
        )

        with pytest.raises(ArtifactStoreError) as invalid:
            ArtifactResolver(store).resolve_authenticated_source_file_binding(
                context=_context(),
                openwebui_file_id="file-1",
            )

        assert invalid.value.code == "source_file_binding_invalid"


def test_rejects_malformed_context_or_file_id() -> None:
    with _store() as store:
        _put_source(store, context=_context(), artifact_id="source-1")
        for context, file_id, expected_code in (
            (_context(user_id=""), "file-1", "artifact_scope_unverified"),
            (_context(allow_private=False), "file-1", "artifact_access_denied"),
            (_context(), " ", "source_file_binding_invalid"),
        ):
            with pytest.raises(ArtifactStoreError) as rejected:
                ArtifactResolver(store).resolve_authenticated_source_file_binding(
                    context=context,
                    openwebui_file_id=file_id,
                )
            assert rejected.value.code == expected_code


def test_fails_closed_when_multiple_records_bind_the_exact_same_file() -> None:
    with _store() as store:
        context = _context()
        _put_source(store, context=context, artifact_id="source-1")
        _put_source(
            store,
            context=replace(context, normalization_run_id="run-2"),
            artifact_id="source-2",
            document_id="document-2",
        )

        with pytest.raises(ArtifactStoreError) as ambiguous:
            ArtifactResolver(store).resolve_authenticated_source_file_binding(
                context=context,
                openwebui_file_id="file-1",
            )

        assert ambiguous.value.code == "source_file_binding_ambiguous"


class _StoreContext:
    def __enter__(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        root = Path(self._temp_dir.name)
        return ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()

    def __exit__(self, exc_type, exc_value, traceback):
        self._temp_dir.cleanup()


def _store() -> _StoreContext:
    return _StoreContext()


def _context(
    *,
    user_id: str = "user-1",
    case_id: str | None = "case-1",
    chat_id: str | None = None,
    workspace_model_id: str = "workspace-1",
    allow_private: bool = True,
) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id=user_id,
        normalization_run_id="caller-run-is-not-source-authority",
        case_id=case_id,
        chat_id=chat_id,
        workspace_model_id=workspace_model_id,
        allow_private=allow_private,
    )


def _put_source(
    store,
    *,
    context: ArtifactAccessContext,
    artifact_id: str,
    document_id: str = "document-1",
    source_deleted: bool = False,
    lifecycle_status: str = "private_ready",
    purge_status: str = "active",
    file_hash_sha256: str = "a" * 64,
) -> ArtifactRecord:
    return store.put_record(
        ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type="source_file_ref_v0",
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=(
                "run-1" if artifact_id == "source-1" else "run-2"
            ),
            document_id=document_id,
            source_file_ref={
                "openwebui_file_id": "file-1",
                "file_hash_sha256": file_hash_sha256,
                "source_deleted": source_deleted,
            },
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=build_retention_policy(mode="api_smoke"),
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_status,
            purge_status=purge_status,
            payload={"must_not_be_exposed_by_binding": True},
        )
    )
