from __future__ import annotations

import hashlib
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord


class BrokerReportsCanonicalStorageLifecycleV1Test(unittest.TestCase):
    def test_cross_run_versions_atomic_activation_and_rollback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self._store(temp_dir)
            first = self._publish(
                store,
                context=self._context("run-1"),
                source_ref="source-1",
                amount="10",
                chunked=False,
            )
            reader = CanonicalReaderFactory(
                store=store, read_enabled=True
            ).create()
            activated = reader.activate(
                canonical_version_id=first.canonical_version_id,
                expected_previous_version_id=None,
                context=self._context("run-1"),
                actor="doc26-test",
                reason="initial shadow lifecycle proof",
            )
            self.assertEqual(activated.status, "changed")

            second = self._publish(
                store,
                context=self._context("run-2"),
                source_ref="source-2",
                amount="20",
                chunked=True,
            )
            history = reader.history("document-1", self._context("run-2"))
            self.assertEqual(
                [item.canonical_version_number for item in history], [1, 2]
            )
            self.assertEqual(
                second.previous_version_ref, first.canonical_version_id
            )
            self.assertEqual(
                reader.read_active("document-1", self._context("run-2"))[
                    "canonical_root_hash"
                ],
                reader.read(first.artifact_ref, self._context("run-2"))[
                    "canonical_root_hash"
                ],
            )
            with self.assertRaises(ArtifactStoreError) as conflict:
                reader.activate(
                    canonical_version_id=second.canonical_version_id,
                    expected_previous_version_id="stale-version",
                    context=self._context("run-2"),
                    actor="doc26-test",
                    reason="prove compare-and-set failure",
                )
            self.assertEqual(conflict.exception.code, "canonical_pointer_conflict")
            self.assertEqual(
                store.get_active_canonical_version(
                    context=self._context("run-2"), document_id="document-1"
                ).canonical_version_id,
                first.canonical_version_id,
            )
            promoted = reader.activate(
                canonical_version_id=second.canonical_version_id,
                expected_previous_version_id=first.canonical_version_id,
                context=self._context("run-2"),
                actor="doc26-test",
                reason="promote validated shadow version",
            )
            self.assertEqual(promoted.status, "changed")
            repeated = reader.activate(
                canonical_version_id=second.canonical_version_id,
                expected_previous_version_id=first.canonical_version_id,
                context=self._context("run-2"),
                actor="doc26-test",
                reason="idempotency proof",
            )
            self.assertEqual(repeated.status, "no_op")
            rolled_back = reader.rollback(
                target_version_id=first.canonical_version_id,
                expected_current_version_id=second.canonical_version_id,
                context=self._context("run-2"),
                actor="doc26-test",
                reason="bounded rollback proof",
            )
            self.assertEqual(rolled_back.operation, "ROLLBACK")
            self.assertEqual(rolled_back.status, "changed")
            final_history = reader.history("document-1", self._context("run-2"))
            self.assertEqual(
                [item.status for item in final_history], ["ACTIVE", "SUPERSEDED"]
            )
            self.assertEqual(
                [item.retention_class for item in final_history],
                ["ACTIVE_CANONICAL", "SUPERSEDED_CANONICAL"],
            )

    def test_chunked_and_single_payload_have_one_logical_reader_api(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self._store(temp_dir)
            small = self._publish(
                store,
                context=self._context("run-small"),
                source_ref="source-small",
                amount="10",
                chunked=False,
                document_id="document-small",
            )
            large = self._publish(
                store,
                context=self._context("run-large"),
                source_ref="source-large",
                amount="20",
                chunked=True,
                document_id="document-large",
            )
            reader = CanonicalReaderFactory(
                store=store, read_enabled=True
            ).create()
            small_artifact = reader.read(
                small.artifact_ref, self._context("run-small")
            )
            large_artifact = reader.read(
                large.artifact_ref, self._context("run-large")
            )
            self.assertEqual(small.physical_layout, "single_payload")
            self.assertEqual(large.physical_layout, "chunked")
            self.assertGreater(large.component_count, 1)
            for artifact, document_id, context in (
                (small_artifact, "document-small", self._context("run-small")),
                (large_artifact, "document-large", self._context("run-large")),
            ):
                root = artifact["root_container_ref"]
                table_id = next(
                    item["node_id"]
                    for item in artifact["nodes"]
                    if item["node_type"] == "TABLE"
                )
                container = reader.read_container(
                    document_id,
                    root,
                    context,
                    canonical_version_id=artifact["artifact_id"],
                )
                table = reader.read_table(
                    document_id,
                    table_id,
                    context,
                    canonical_version_id=artifact["artifact_id"],
                )
                self.assertEqual(container["container"]["container_id"], root)
                self.assertEqual(table["node_type"], "TABLE")

    def test_cross_tenant_and_guessed_version_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self._store(temp_dir)
            published = self._publish(
                store,
                context=self._context("run-access"),
                source_ref="source-access",
                amount="10",
                chunked=True,
            )
            reader = CanonicalReaderFactory(
                store=store, read_enabled=True
            ).create()
            other = ArtifactAccessContext(
                user_id="other-user",
                normalization_run_id="run-other",
                case_id="case-1",
                workspace_model_id="workspace-1",
                allow_private=True,
            )
            with self.assertRaises(ArtifactStoreError) as denied:
                reader.read(published.artifact_ref, other)
            self.assertEqual(denied.exception.code, "artifact_access_denied")
            with self.assertRaises(ArtifactStoreError) as missing:
                store.get_canonical_version(
                    context=self._context("run-access"),
                    canonical_version_id="canver_guessed",
                )
            self.assertEqual(missing.exception.code, "artifact_not_found")
            without_private = ArtifactAccessContext(
                user_id="user-1",
                normalization_run_id="run-access",
                case_id="case-1",
                workspace_model_id="workspace-1",
                allow_private=False,
            )
            with self.assertRaises(ArtifactStoreError) as private_denied:
                reader.read(published.artifact_ref, without_private)
            self.assertEqual(private_denied.exception.code, "artifact_access_denied")

    def test_purge_removes_every_physical_component_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self._store(temp_dir)
            context = self._context("run-purge")
            published = self._publish(
                store,
                context=context,
                source_ref="source-purge",
                amount="10",
                chunked=True,
            )
            self.assertGreater(published.component_count, 1)
            self.assertGreater(len(list(store.payload_root.glob("*.json"))), 1)
            result = store.purge_run(context)
            self.assertGreater(result.records_changed, 1)
            self.assertEqual(list(store.payload_root.glob("*.json")), [])
            with self.assertRaises(ArtifactStoreError) as purged:
                store.get_canonical_version(
                    context=context,
                    canonical_version_id=published.canonical_version_id,
                )
            self.assertEqual(purged.exception.code, "canonical_version_not_active")

    def test_failed_atomic_component_write_removes_new_payload_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self._store(temp_dir)
            context = self._context("run-atomic-failure")
            retention = build_retention_policy(mode="api_smoke")
            source = ArtifactRecord(
                artifact_id="atomic-source",
                artifact_type="source_file_ref_v0",
                case_id=context.case_id,
                chat_id=context.chat_id,
                user_id=context.user_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                document_id="atomic-document",
                source_file_ref={"openwebui_file_id": "file-atomic-document"},
                visibility="private_case",
                storage_backend="project_artifact_payload",
                retention_policy=retention,
                access_policy={"requires_user_id": True},
                validation_status="validated",
                lifecycle_status="private_ready",
                payload={"source": True},
            )
            store.put_record(source)
            before = sorted(path.name for path in store.payload_root.glob("*.json"))
            first = ArtifactRecord(
                **{
                    **source.__dict__,
                    "artifact_id": "atomic-component-1",
                    "artifact_type": "broker_reports_canonical_component_v1",
                    "payload": {"component": 1},
                }
            )
            second = ArtifactRecord(
                **{
                    **source.__dict__,
                    "artifact_id": "atomic-component-2",
                    "artifact_type": "broker_reports_canonical_component_v1",
                    "payload": {"component": 2},
                }
            )
            original = store._insert_record
            calls = 0

            def fail_second(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("synthetic atomic insert failure")
                return original(*args, **kwargs)

            with patch.object(store, "_insert_record", side_effect=fail_second):
                with self.assertRaisesRegex(RuntimeError, "synthetic atomic"):
                    store.put_records_atomic([first, second])
            after = sorted(path.name for path in store.payload_root.glob("*.json"))
            self.assertEqual(after, before)
            self.assertIsNone(store.get_record_unchecked("atomic-component-1"))
            self.assertIsNone(store.get_record_unchecked("atomic-component-2"))

    def test_direct_table_read_rejects_mutated_component_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self._store(temp_dir)
            context = self._context("run-component-file-mutation")
            published = self._publish(
                store,
                context=context,
                source_ref="source-component-file-mutation",
                amount="10",
                chunked=True,
                capacity_check_enabled=False,
            )
            component = next(
                item
                for item in store.list_canonical_components(
                    context=context,
                    canonical_version_id=published.canonical_version_id,
                )
                if item["component_kind"] == "table"
            )
            record = store.get_record_unchecked(str(component["artifact_ref"]))
            self.assertIsNotNone(record)
            assert record is not None and record.payload_ref
            (store.payload_root / record.payload_ref).write_text(
                '{"node":{"node_type":"TABLE","tampered":true}}',
                encoding="utf-8",
            )
            reader = CanonicalReaderFactory(store=store, read_enabled=True).create()

            with self.assertRaises(ArtifactStoreError) as blocked:
                reader.read_table(
                    "document-1",
                    str(component["component_key"]),
                    context,
                    canonical_version_id=published.canonical_version_id,
                )

            self.assertEqual(blocked.exception.code, "canonical_chunk_hash_mismatch")

    def test_canonical_descriptor_rejects_payload_resealed_in_artifact_row(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = self._store(temp_dir)
            context = self._context("run-component-resealed")
            published = self._publish(
                store,
                context=context,
                source_ref="source-component-resealed",
                amount="10",
                chunked=True,
                capacity_check_enabled=False,
            )
            component = next(
                item
                for item in store.list_canonical_components(
                    context=context,
                    canonical_version_id=published.canonical_version_id,
                )
                if item["component_kind"] == "table"
            )
            record = store.get_record_unchecked(str(component["artifact_ref"]))
            self.assertIsNotNone(record)
            assert record is not None and record.payload_ref
            tampered = b'{"node":{"node_type":"TABLE","resealed":true}}'
            (store.payload_root / record.payload_ref).write_bytes(tampered)
            with closing(sqlite3.connect(store.sqlite_path)) as conn:
                conn.execute(
                    """
                    UPDATE artifact_records
                    SET checksum_sha256 = ?, payload_size_bytes = ?
                    WHERE artifact_id = ?
                    """,
                    (
                        hashlib.sha256(tampered).hexdigest(),
                        len(tampered),
                        record.artifact_id,
                    ),
                )
                conn.commit()
            reader = CanonicalReaderFactory(store=store, read_enabled=True).create()

            with self.assertRaises(ArtifactStoreError) as blocked:
                reader.read_table(
                    "document-1",
                    str(component["component_key"]),
                    context,
                    canonical_version_id=published.canonical_version_id,
                )

            self.assertEqual(blocked.exception.code, "canonical_chunk_hash_mismatch")

    def _publish(
        self,
        store,
        *,
        context: ArtifactAccessContext,
        source_ref: str,
        amount: str,
        chunked: bool,
        document_id: str = "document-1",
        capacity_check_enabled: bool = True,
    ):
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
                lifecycle_status=lifecycle_for_visibility(
                    visibility="private_case", validation_status="validated"
                ),
                payload={"source_ref": source_ref},
            )
        )
        rows = [["Date", "Amount"], ["2026-01-01", amount]]
        artifact = CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="canonical-doc26-v1")
        ).create().build(
            tenant_id=context.user_id,
            artifact_version=1,
            document={
                "container_format": "csv",
                "sha256": ("a" if amount == "10" else "b") * 64,
                "declared_mime_type": "text/csv",
            },
            source_artifact_ref=source_ref,
            source_payloads=[
                {
                    "source_location": {"encoding": "utf-8", "delimiter": ","},
                    "canonical_projection": {
                        "rows": rows,
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
        config = CanonicalStorageConfig(
            small_payload_max_bytes=1 if chunked else 10_000_000,
            large_table_cell_threshold=1 if chunked else 10_000_000,
            capacity_check_enabled=capacity_check_enabled,
        )
        return CanonicalArtifactStoreFactory(
            store=store, config=config
        ).create().put_candidate(
            artifact=artifact,
            context=context,
            retention_policy=retention,
            compare_receipt=None,
        )

    @staticmethod
    def _context(run_id: str) -> ArtifactAccessContext:
        return ArtifactAccessContext(
            user_id="user-1",
            normalization_run_id=run_id,
            case_id="case-1",
            workspace_model_id="workspace-1",
            allow_private=True,
        )

    @staticmethod
    def _store(temp_dir: str):
        root = Path(temp_dir)
        return ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()


if __name__ == "__main__":
    unittest.main()
