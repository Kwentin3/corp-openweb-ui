"""Contract tests for the closed-world Goal #391 private corpus exporter."""

from __future__ import annotations

import json
import hashlib
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord, ArtifactStoreError
from broker_reports_gate1.goal391_private_corpus_export import (
    Goal391PrivateCorpusExportCoordinator,
    Goal391PrivateCorpusExportError,
    PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION,
    parse_private_corpus_selection,
)
from broker_reports_gate1.goal391_private_corpus_export_cli import (
    export_private_corpus,
)


def test_exports_only_explicit_manifest_refs_through_canonical_reader() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = _store(root)
        first = _publish(store, context=_context("run-one"), document_id="document-one", amount="10")
        second = _publish(store, context=_context("run-two"), document_id="document-two", amount="20")
        reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
        recording_reader = _RecordingReader(reader)
        private_root = _private_root(root)
        selection = parse_private_corpus_selection(
            _selection("ordinary-trade-corpus", "trade-001", first.artifact_ref, "run-one")
        )

        receipt = Goal391PrivateCorpusExportCoordinator(
            reader=recording_reader, private_corpus_root=private_root
        ).export(selection=selection)

        pack_root = private_root / "ordinary-trade-corpus"
        pack = json.loads((pack_root / "corpus_manifest.private.json").read_text(encoding="utf-8"))
        exported = json.loads((pack_root / "canonical" / "trade-001.json").read_text(encoding="utf-8"))
        assert receipt["status"] == "EXPORTED"
        assert receipt["contains_private_payload"] is False
        assert receipt["selection_count"] == 1
        assert recording_reader.manifest_refs == [first.artifact_ref]
        assert recording_reader.expected_normalization_run_ids == ["run-one"]
        assert "Amount" not in json.dumps(receipt)
        assert "source-document-one" not in json.dumps(receipt)
        assert pack["entries"] == [
            {
                "slot_id": "trade-001",
                "canonical_binding": {
                    "document_id": "document-one",
                    "canonical_version_id": first.canonical_version_id,
                    "canonical_root_sha256": exported["canonical_root_hash"],
                    "source_artifact_ref": "source-document-one",
                    "source_sha256": exported["source"]["source_sha256"],
                },
                "canonical_file": "canonical/trade-001.json",
                "canonical_file_sha256": pack["entries"][0]["canonical_file_sha256"],
            }
        ]
        assert exported["source"]["source_artifact_ref"] == "source-document-one"
        assert exported["source"]["source_artifact_ref"] != second.artifact_ref
        assert not (pack_root / "canonical" / "trade-002.json").exists()


def test_scope_failure_leaves_no_partial_private_pack() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = _store(root)
        published = _publish(store, context=_context("run-one"), document_id="document-one", amount="10")
        reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
        private_root = _private_root(root)
        selection = parse_private_corpus_selection(
            _selection("ordinary-trade-corpus", "trade-001", published.artifact_ref, "run-one", user_id="other-user")
        )

        with pytest.raises(ArtifactStoreError) as denied:
            Goal391PrivateCorpusExportCoordinator(
                reader=reader, private_corpus_root=private_root
            ).export(selection=selection)

        assert denied.value.code == "artifact_access_denied"
        assert not (private_root / "ordinary-trade-corpus").exists()
        assert list(private_root.iterdir()) == []


def test_selected_normalization_run_mismatch_stops_before_private_payload_write() -> None:
    """The immutable selection run is checked by CanonicalReader before export."""

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = _store(root)
        published = _publish(
            store,
            context=_context("run-one"),
            document_id="document-one",
            amount="10",
        )
        private_root = _private_root(root)
        selection = parse_private_corpus_selection(
            _selection(
                "run-mismatch-corpus",
                "trade-001",
                published.artifact_ref,
                "run-two",
            )
        )

        with pytest.raises(ArtifactStoreError) as mismatch:
            Goal391PrivateCorpusExportCoordinator(
                reader=CanonicalReaderFactory(store=store, read_enabled=True).create(),
                private_corpus_root=private_root,
            ).export(selection=selection)

        assert mismatch.value.code == "canonical_normalization_run_mismatch"
        assert list(private_root.iterdir()) == []


def test_manifest_is_closed_world_and_target_is_not_overwritten() -> None:
    malformed = {
        "schema_version": PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION,
        "corpus_id": "ordinary-trade-corpus",
        "selections": [],
    }
    with pytest.raises(Goal391PrivateCorpusExportError) as empty:
        parse_private_corpus_selection(malformed)
    assert empty.value.code == "goal391_private_corpus_selection_empty"

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        private_root = _private_root(root)
        (private_root / "ordinary-trade-corpus").mkdir()
        selection = parse_private_corpus_selection(
            _selection("ordinary-trade-corpus", "trade-001", "manifest-1", "run-one")
        )
        with pytest.raises(Goal391PrivateCorpusExportError) as exists:
            Goal391PrivateCorpusExportCoordinator(
                reader=_NeverRead(), private_corpus_root=private_root
            ).export(selection=selection)
        assert exists.value.code == "goal391_private_corpus_target_exists"


def test_cli_composes_read_only_store_reader_and_exporter_without_schema_or_probe() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = _store(root)
        published = _publish(store, context=_context("run-one"), document_id="document-one", amount="10")
        private_root = _private_root(root)
        manifest_path = root / "selection.private.json"
        manifest_path.write_text(
            json.dumps(_selection("cli-corpus", "trade-001", published.artifact_ref, "run-one")),
            encoding="utf-8",
        )
        actual_open = os.open

        def reject_payload_probe(path, *args, **kwargs):
            assert ".artifact-store-probe-" not in str(path)
            return actual_open(path, *args, **kwargs)

        with patch(
            "broker_reports_gate1.artifact_store.SqliteArtifactStoreAdapter._ensure_schema",
            side_effect=AssertionError("CLI must not initialize schema"),
        ), patch(
            "broker_reports_gate1.artifact_store.os.open",
            side_effect=reject_payload_probe,
        ):
            receipt = export_private_corpus(
                artifact_store_sqlite_path=root / "artifacts.sqlite3",
                artifact_payload_root=root / "payloads",
                selection_manifest=manifest_path,
                private_corpus_root=private_root,
            )

        assert receipt["status"] == "EXPORTED"
        assert (private_root / "cli-corpus" / "export_receipt.json").is_file()


def test_rejects_symlink_and_insecure_private_roots() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        actual = root / "actual-private"
        actual.mkdir(mode=0o700)
        link = root / "_private_test_corpora"
        try:
            os.symlink(actual, link, target_is_directory=True)
        except OSError:
            pytest.skip("symlink creation is unavailable in this environment")
        with pytest.raises(Goal391PrivateCorpusExportError) as linked:
            Goal391PrivateCorpusExportCoordinator(reader=_NeverRead(), private_corpus_root=link)
        assert linked.value.code == "goal391_private_corpus_root_unsafe"

    if os.name == "nt":
        return
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        private_root = _private_root(root)
        private_root.chmod(0o777)
        with pytest.raises(Goal391PrivateCorpusExportError) as insecure:
            Goal391PrivateCorpusExportCoordinator(
                reader=_NeverRead(), private_corpus_root=private_root
            )
        assert insecure.value.code == "goal391_private_corpus_root_unsafe"


def test_atomic_target_reservation_prevents_concurrent_overwrite() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = _store(root)
        published = _publish(store, context=_context("run-one"), document_id="document-one", amount="10")
        reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
        private_root = _private_root(root)
        selection = parse_private_corpus_selection(
            _selection("raced-corpus", "trade-001", published.artifact_ref, "run-one")
        )

        def export_once():
            return Goal391PrivateCorpusExportCoordinator(
                reader=reader, private_corpus_root=private_root
            ).export(selection=selection)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(export_once), pool.submit(export_once)]
            results = []
            failures = []
            for future in futures:
                try:
                    results.append(future.result())
                except Goal391PrivateCorpusExportError as exc:
                    failures.append(exc)

        assert len(results) == 1
        assert [failure.code for failure in failures] == [
            "goal391_private_corpus_target_exists"
        ]
        assert results[0]["status"] == "EXPORTED"
        assert (private_root / "raced-corpus" / "export_receipt.json").is_file()


def test_second_selected_read_failure_removes_first_private_payload() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        store = _store(root)
        first = _publish(store, context=_context("run-one"), document_id="document-one", amount="10")
        second = _publish(store, context=_context("run-two"), document_id="document-two", amount="20")
        reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
        private_root = _private_root(root)
        manifest = _selection("partial-corpus", "trade-001", first.artifact_ref, "run-one")
        manifest["selections"].append(
            {
                **manifest["selections"][0],
                "slot_id": "trade-002",
                "manifest_ref": second.artifact_ref,
                "normalization_run_id": "run-two",
                "user_id": "other-user",
            }
        )
        selection = parse_private_corpus_selection(manifest)

        with pytest.raises(ArtifactStoreError) as denied:
            Goal391PrivateCorpusExportCoordinator(
                reader=reader, private_corpus_root=private_root
            ).export(selection=selection)

        assert denied.value.code == "artifact_access_denied"
        assert list(private_root.iterdir()) == []


def _selection(
    corpus_id: str,
    slot_id: str,
    manifest_ref: str,
    run_id: str,
    *,
    user_id: str = "user-1",
) -> dict:
    return {
        "schema_version": PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION,
        "corpus_id": corpus_id,
        "selections": [
            {
                "slot_id": slot_id,
                "manifest_ref": manifest_ref,
                "user_id": user_id,
                "normalization_run_id": run_id,
                "case_id": "case-1",
                "chat_id": None,
                "workspace_model_id": "workspace-1",
            }
        ],
    }


def _context(run_id: str) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="user-1",
        normalization_run_id=run_id,
        case_id="case-1",
        workspace_model_id="workspace-1",
        allow_private=True,
    )


def _private_root(root: Path) -> Path:
    private_root = root / "_private_test_corpora"
    private_root.mkdir(mode=0o700)
    if os.name != "nt":
        private_root.chmod(0o700)
    return private_root


def _store(root: Path):
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite", sqlite_path=root / "artifacts.sqlite3", payload_root=root / "payloads"
        )
    ).create()


def _publish(store, *, context: ArtifactAccessContext, document_id: str, amount: str):
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
            source_file_ref={"openwebui_file_id": f"file-{document_id}"},
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(visibility="private_case", validation_status="validated"),
            payload={"source_ref": source_ref},
        )
    )
    artifact = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="goal391-private-corpus-test")
    ).create().build(
        tenant_id=context.user_id,
        artifact_version=1,
        document={
            "container_format": "csv",
            "sha256": hashlib.sha256(amount.encode("utf-8")).hexdigest(),
            "declared_mime_type": "text/csv",
        },
        source_artifact_ref=source_ref,
        source_payloads=[
            {
                "source_location": {"encoding": "utf-8", "delimiter": ","},
                "canonical_projection": {
                    "rows": [["Date", "Amount"], ["2026-01-01", amount]],
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
    return CanonicalArtifactStoreFactory(
        store=store,
        config=CanonicalStorageConfig(capacity_check_enabled=False),
    ).create().put_candidate(
        artifact=artifact, context=context, retention_policy=retention, compare_receipt=None
    )


class _NeverRead:
    def read_envelope(self, *_args, **_kwargs):
        raise AssertionError("existing target must stop before any Canonical read")


class _RecordingReader:
    def __init__(self, reader) -> None:
        self._reader = reader
        self.manifest_refs: list[str] = []
        self.expected_normalization_run_ids: list[str | None] = []

    def read_envelope(self, manifest_ref, context, *, expected_normalization_run_id=None):
        self.manifest_refs.append(manifest_ref)
        self.expected_normalization_run_ids.append(expected_normalization_run_id)
        return self._reader.read_envelope(
            manifest_ref,
            context,
            expected_normalization_run_id=expected_normalization_run_id,
        )
