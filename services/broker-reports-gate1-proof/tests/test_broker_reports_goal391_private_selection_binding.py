"""Contract checks for explicit Goal #391 private selection issuance."""

from __future__ import annotations

from types import SimpleNamespace
import hashlib
import tempfile
from pathlib import Path

import pytest

from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_store import (
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)
from broker_reports_gate1.canonical_artifact import (
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
)
from broker_reports_gate1.canonical_store import (
    CanonicalReaderFactory,
    CanonicalArtifactStoreFactory,
    CanonicalStorageConfig,
)
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.goal391_private_selection_binding import (
    Goal391PrivateSelectionBindingError,
    Goal391PrivateSelectionBindingIssuer,
    Goal391PrivateSelectionRequest,
    Goal391PrivateSourceFileSelectionRequest,
)


def test_issues_exact_active_manifest_after_source_lifecycle_binding() -> None:
    store = _Store()
    reader = _Reader()
    resolver = _Resolver()
    selection = Goal391PrivateSelectionBindingIssuer(
        store=store, reader=reader, resolver=resolver
    ).issue(corpus_id="goal391-source-review", requests=(_request(),))

    assert selection.selections[0].manifest_ref == "manifest-1"
    assert selection.selections[0].case_id == "case-1"
    assert selection.selections[0].chat_id is None
    assert store.calls == [("active", "document-1", True)]
    assert reader.calls == [("exact", "manifest-1", "run-1", True)]
    assert resolver.calls == [("source-1", "run-1", True)]


def test_real_owners_issue_only_the_authenticated_active_canonical() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        context = _real_context(user_id="user-1")
        published = _publish_active(store, context=context)
        issuer = Goal391PrivateSelectionBindingIssuer(
            store=store,
            reader=CanonicalReaderFactory(store=store, read_enabled=True).create(),
            resolver=ArtifactResolver(store),
        )

        selection = issuer.issue(
            corpus_id="goal391-source-review",
            requests=(
                Goal391PrivateSelectionRequest(
                    slot_id="instructional-control",
                    document_id="document-1",
                    context=context,
                ),
            ),
        )

        assert selection.selections[0].manifest_ref == published.artifact_ref
        with pytest.raises(ArtifactStoreError) as foreign:
            issuer.issue(
                corpus_id="goal391-source-review",
                requests=(
                    Goal391PrivateSelectionRequest(
                        slot_id="instructional-control",
                        document_id="document-1",
                        context=_real_context(user_id="other-user"),
                    ),
                ),
            )
        assert foreign.value.code == "canonical_version_not_active"


def test_real_owners_issue_two_distinct_active_canonicals() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        context = _real_context(user_id="user-1")
        first = _publish_active(store, context=context, document_id="document-1")
        second = _publish_active(store, context=context, document_id="document-2")
        issuer = Goal391PrivateSelectionBindingIssuer(
            store=store,
            reader=CanonicalReaderFactory(store=store, read_enabled=True).create(),
            resolver=ArtifactResolver(store),
        )

        selection = issuer.issue(
            corpus_id="goal391-source-review",
            requests=(
                Goal391PrivateSelectionRequest(
                    slot_id="ordinary-context-1",
                    document_id="document-1",
                    context=context,
                ),
                Goal391PrivateSelectionRequest(
                    slot_id="ordinary-context-2",
                    document_id="document-2",
                    context=context,
                ),
            ),
        )

        assert [item.slot_id for item in selection.selections] == [
            "ordinary-context-1",
            "ordinary-context-2",
        ]
        assert [item.manifest_ref for item in selection.selections] == [
            first.artifact_ref,
            second.artifact_ref,
        ]


def test_real_owners_issue_exact_source_file_canonical_without_active_pointer() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        source_context = _real_context(user_id="user-1", run_id="original-run")
        published = _publish_active(store, context=source_context, activate=False)
        issuer = Goal391PrivateSelectionBindingIssuer(
            store=store,
            reader=CanonicalReaderFactory(store=store, read_enabled=True).create(),
            resolver=ArtifactResolver(store),
        )

        selection = issuer.issue_from_source_files(
            corpus_id="goal391-source-review",
            requests=(
                Goal391PrivateSourceFileSelectionRequest(
                    slot_id="instructional-control",
                    openwebui_file_id="file-document-1",
                    context=_real_context(user_id="user-1", run_id="caller-placeholder"),
                ),
            ),
        )

        item = selection.selections[0]
        assert item.manifest_ref == published.artifact_ref
        assert item.normalization_run_id == "original-run"


def test_source_file_selection_refuses_missing_exact_canonical() -> None:
    store, reader, resolver = _SourceFileStore(), _Reader(), _SourceFileResolver()
    with pytest.raises(Goal391PrivateSelectionBindingError) as rejected:
        Goal391PrivateSelectionBindingIssuer(
            store=store, reader=reader, resolver=resolver
        ).issue_from_source_files(
            corpus_id="goal391-source-review",
            requests=(_source_file_request(),),
        )
    assert rejected.value.code == "goal391_selection_binding_exact_canonical_missing"
    assert reader.calls == []


def test_source_file_selection_refuses_canonical_source_substitution() -> None:
    store = _SourceFileStore(
        versions=(
            SimpleNamespace(
                normalization_run_id="run-1",
                source_artifact_ref="source-1",
                source_sha256="a" * 64,
                manifest_ref="manifest-1",
                canonical_version_id="version-1",
                canonical_root_sha256="root-1",
            ),
        )
    )
    reader, resolver = _Reader(source_ref="source-other"), _SourceFileResolver()
    with pytest.raises(Goal391PrivateSelectionBindingError) as rejected:
        Goal391PrivateSelectionBindingIssuer(
            store=store, reader=reader, resolver=resolver
        ).issue_from_source_files(
            corpus_id="goal391-source-review",
            requests=(_source_file_request(),),
        )
    assert rejected.value.code == "goal391_selection_binding_canonical_invalid"
    assert reader.calls == [("exact", "manifest-1", "run-1", True)]


def test_real_source_lifecycle_refuses_deleted_source_before_selection() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        context = _real_context(user_id="user-1")
        _publish_active(store, context=context, source_deleted=True)
        issuer = Goal391PrivateSelectionBindingIssuer(
            store=store,
            reader=CanonicalReaderFactory(store=store, read_enabled=True).create(),
            resolver=ArtifactResolver(store),
        )

        with pytest.raises(ArtifactStoreError) as deleted:
            issuer.issue(
                corpus_id="goal391-source-review",
                requests=(
                    Goal391PrivateSelectionRequest(
                        slot_id="instructional-control",
                        document_id="document-1",
                        context=context,
                    ),
                ),
            )
        assert deleted.value.code == "source_file_unavailable"


def test_real_cross_run_active_canonical_stops_before_reader_or_resolver() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        active_context = _real_context(user_id="user-1", run_id="final-run")
        _publish_active(store, context=active_context)
        reader, resolver = _Reader(), _Resolver()
        issuer = Goal391PrivateSelectionBindingIssuer(
            store=store, reader=reader, resolver=resolver
        )

        with pytest.raises(Goal391PrivateSelectionBindingError) as cross_run:
            issuer.issue(
                corpus_id="goal391-source-review",
                requests=(
                    Goal391PrivateSelectionRequest(
                        slot_id="instructional-control",
                        document_id="document-1",
                        context=_real_context(user_id="user-1"),
                    ),
                ),
            )
        assert cross_run.value.code == "goal391_selection_binding_cross_run_unsupported"
        assert reader.calls == resolver.calls == []


def test_rejects_invalid_slot_before_any_owner_read() -> None:
    store, reader, resolver = _Store(), _Reader(), _Resolver()
    with pytest.raises(Goal391PrivateSelectionBindingError) as rejected:
        Goal391PrivateSelectionBindingIssuer(
            store=store, reader=reader, resolver=resolver
        ).issue(
            corpus_id="goal391-source-review",
            requests=(
                Goal391PrivateSelectionRequest(
                    slot_id="../escape", document_id="document-1", context=_context()
                ),
            ),
        )
    assert rejected.value.code == "goal391_selection_binding_request_invalid"
    assert store.calls == reader.calls == resolver.calls == []


def test_rejects_finalized_cross_run_before_exact_or_source_read() -> None:
    store, reader, resolver = _Store(normalization_run_id="final-run"), _Reader(), _Resolver()
    with pytest.raises(Goal391PrivateSelectionBindingError) as rejected:
        Goal391PrivateSelectionBindingIssuer(
            store=store, reader=reader, resolver=resolver
        ).issue(corpus_id="goal391-source-review", requests=(_request(),))
    assert rejected.value.code == "goal391_selection_binding_cross_run_unsupported"
    assert store.calls == [("active", "document-1", True)]
    assert reader.calls == resolver.calls == []


def test_rejects_missing_source_lifecycle_binding() -> None:
    store, reader, resolver = _Store(), _Reader(), _Resolver(source_deleted=True)
    with pytest.raises(Goal391PrivateSelectionBindingError) as rejected:
        Goal391PrivateSelectionBindingIssuer(
            store=store, reader=reader, resolver=resolver
        ).issue(corpus_id="goal391-source-review", requests=(_request(),))
    assert rejected.value.code == "goal391_selection_binding_source_invalid"
    assert resolver.calls == [("source-1", "run-1", True)]


def test_rejects_non_private_context_before_owner_read() -> None:
    store, reader, resolver = _Store(), _Reader(), _Resolver()
    with pytest.raises(Goal391PrivateSelectionBindingError) as rejected:
        Goal391PrivateSelectionBindingIssuer(
            store=store, reader=reader, resolver=resolver
        ).issue(
            corpus_id="goal391-source-review",
            requests=(
                Goal391PrivateSelectionRequest(
                    slot_id="instructional-control",
                    document_id="document-1",
                    context=ArtifactAccessContext(
                        user_id="user-1",
                        normalization_run_id="run-1",
                        case_id="case-1",
                        chat_id=None,
                        workspace_model_id="workspace-1",
                        allow_private=False,
                    ),
                ),
            ),
        )
    assert rejected.value.code == "goal391_selection_binding_request_invalid"
    assert store.calls == reader.calls == resolver.calls == []


def test_rejects_malformed_effective_scope_before_owner_read() -> None:
    store, reader, resolver = _Store(), _Reader(), _Resolver()
    malformed = ArtifactAccessContext(
        user_id="user-1",
        normalization_run_id="run-1",
        case_id="",
        chat_id="chat-1",
        workspace_model_id="",
        allow_private=True,
    )
    with pytest.raises(Goal391PrivateSelectionBindingError) as rejected:
        Goal391PrivateSelectionBindingIssuer(
            store=store, reader=reader, resolver=resolver
        ).issue(
            corpus_id="goal391-source-review",
            requests=(
                Goal391PrivateSelectionRequest(
                    slot_id="instructional-control",
                    document_id="document-1",
                    context=malformed,
                ),
            ),
        )
    assert rejected.value.code == "goal391_selection_binding_request_invalid"
    assert store.calls == reader.calls == resolver.calls == []


def _context() -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="user-1",
        normalization_run_id="run-1",
        case_id="case-1",
        chat_id="chat-ignored-by-case-scope",
        workspace_model_id="workspace-1",
        allow_private=True,
    )


def _request() -> Goal391PrivateSelectionRequest:
    return Goal391PrivateSelectionRequest(
        slot_id="instructional-control", document_id="document-1", context=_context()
    )


class _Store:
    def __init__(self, *, normalization_run_id: str = "run-1") -> None:
        self.normalization_run_id = normalization_run_id
        self.calls: list[tuple[str, ...]] = []

    def get_active_canonical_version(self, *, context, document_id):
        self.calls.append(("active", document_id, context.require_source_available))
        return SimpleNamespace(
            document_id=document_id,
            canonical_version_id="version-1",
            canonical_root_sha256="root-1",
            source_artifact_ref="source-1",
            source_sha256="a" * 64,
            normalization_run_id=self.normalization_run_id,
            manifest_ref="manifest-1",
        )

    def list_canonical_versions(self, *, context, document_id):
        self.calls.append(("history", document_id, context.require_source_available))
        return []


class _Reader:
    def __init__(self, *, source_ref="source-1") -> None:
        self.source_ref = source_ref
        self.calls: list[tuple[str, ...]] = []

    def read_envelope(self, manifest_ref, context, *, expected_normalization_run_id):
        self.calls.append(
            (
                "exact",
                manifest_ref,
                expected_normalization_run_id,
                context.require_source_available,
            )
        )
        return SimpleNamespace(
            document_id="document-1",
            canonical_version_id="version-1",
            canonical_root_sha256="root-1",
            artifact={
                "source": {
                    "source_artifact_ref": self.source_ref,
                    "source_sha256": "a" * 64,
                }
            },
        )


class _Resolver:
    def __init__(self, *, source_deleted: bool = False) -> None:
        self.source_deleted = source_deleted
        self.calls: list[tuple[str, str, bool]] = []

    def resolve_record(self, artifact_id, context):
        self.calls.append(
            (artifact_id, context.normalization_run_id, context.require_source_available)
        )
        return SimpleNamespace(
            artifact_type="source_file_ref_v0",
            document_id="document-1",
            normalization_run_id="run-1",
            source_file_ref={
                "file_hash_sha256": "a" * 64,
                "source_deleted": self.source_deleted,
            },
        )

    def resolve_authenticated_source_file_binding(self, *, context, openwebui_file_id):
        return SimpleNamespace(
            document_id="document-1",
            normalization_run_id="run-1",
            source_artifact_id="source-1",
            file_hash_sha256="a" * 64,
        )


class _SourceFileStore:
    def __init__(self, *, versions=()):
        self.versions = versions

    def get_active_canonical_version(self, *, context, document_id):
        raise AssertionError("source-file selection must not use active pointer")

    def list_canonical_versions(self, *, context, document_id):
        assert context.normalization_run_id == "run-1"
        assert document_id == "document-1"
        return list(self.versions)


class _SourceFileResolver:
    def __init__(self, *, source_ref="source-1"):
        self.source_ref = source_ref

    def resolve_record(self, artifact_id, context):
        raise AssertionError("source-file selection resolves binding before Canonical history")

    def resolve_authenticated_source_file_binding(self, *, context, openwebui_file_id):
        assert context.require_source_available is True
        assert openwebui_file_id == "file-1"
        return SimpleNamespace(
            document_id="document-1",
            normalization_run_id="run-1",
            source_artifact_id=self.source_ref,
            file_hash_sha256="a" * 64,
        )


def _source_file_request() -> Goal391PrivateSourceFileSelectionRequest:
    return Goal391PrivateSourceFileSelectionRequest(
        slot_id="instructional-control",
        openwebui_file_id="file-1",
        context=_real_context(user_id="user-1", run_id="caller-placeholder"),
    )


def _real_context(*, user_id: str, run_id: str = "run-1") -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id=user_id,
        normalization_run_id=run_id,
        case_id="case-1",
        chat_id=None,
        workspace_model_id="workspace-1",
        allow_private=True,
    )


def _publish_active(
    store,
    *,
    context: ArtifactAccessContext,
    source_deleted: bool = False,
    document_id: str = "document-1",
    activate: bool = True,
):
    source_bytes = f"goal391 source {document_id}".encode("utf-8")
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    source_ref = f"source-{document_id}"
    retention = build_retention_policy(mode="api_smoke")
    store.put_record(
        ArtifactRecord(
            artifact_id=source_ref,
            artifact_type="source_file_ref_v0",
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
            source_file_ref={
                "openwebui_file_id": f"file-{document_id}",
                "file_hash_sha256": source_sha256,
                "source_deleted": source_deleted,
            },
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload={"source_ref": source_ref},
        )
    )
    artifact = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="goal391-selection-binding-test")
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=1,
        document={
            "container_format": "csv",
            "sha256": source_sha256,
            "declared_mime_type": "text/csv",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "source_location": {"encoding": "utf-8", "delimiter": ","},
                "canonical_projection": {
                    "rows": [["Date", "Amount"], ["2026-01-01", "10"]],
                    "encoding": "utf-8",
                    "delimiter": ",",
                    "quotechar": '"',
                    "header_present": True,
                    "duplicate_headers": False,
                },
            }
        ],
        source_units=[],
        table_projections=[],
    )
    candidate = CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(capacity_check_enabled=False),
    ).create().put_candidate(
        artifact=artifact,
        context=context,
        retention_policy=retention,
        compare_receipt=None,
    )
    if activate:
        store.activate_canonical_version(
            context=context,
            canonical_version_id=candidate.canonical_version_id,
            expected_previous_version_id=None,
            actor="test",
            reason="goal391 selection binding test",
        )
    return candidate
