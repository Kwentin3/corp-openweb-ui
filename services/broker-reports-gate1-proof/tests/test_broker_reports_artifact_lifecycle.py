from __future__ import annotations

import inspect
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.artifact_store import (
    SqliteArtifactStoreAdapter,
    new_artifact_id,
)


class BrokerReportsArtifactLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.sqlite_path = root / "artifacts.sqlite3"
        self.payload_root = root / "payloads"
        self.store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=self.sqlite_path,
                payload_root=self.payload_root,
            )
        ).create()
        self.context = ArtifactAccessContext(
            user_id="user-lifecycle",
            case_id="case-lifecycle",
            chat_id="chat-lifecycle",
            workspace_model_id="broker_reports_gate1_pipe",
            normalization_run_id="run-lifecycle",
            allow_private=True,
        )

    def test_repeated_expiry_is_strict_no_op_and_preserves_timestamp(self) -> None:
        record = self._put_record(expires_in=timedelta(minutes=1))
        lifecycle_now = datetime.now(timezone.utc) + timedelta(minutes=2)

        first = self.store.expire_run(self.context, now=lifecycle_now)
        after_first = self.store.get_record_unchecked(record.artifact_id)
        second = self.store.expire_run(self.context, now=lifecycle_now)
        after_second = self.store.get_record_unchecked(record.artifact_id)

        self.assertEqual(first.status, "changed")
        self.assertEqual(first.records_changed, 1)
        self.assertEqual(first.artifact_ids, (record.artifact_id,))
        self.assertEqual(second.status, "no_op")
        self.assertEqual(second.records_changed, 0)
        self.assertEqual(after_first.lifecycle_status, "expired")
        self.assertEqual(after_first.updated_at, after_second.updated_at)

    def test_two_concurrent_expiry_callers_have_one_winner(self) -> None:
        record = self._put_record(expires_in=timedelta(minutes=1))
        lifecycle_now = datetime.now(timezone.utc) + timedelta(minutes=2)
        start = threading.Barrier(2)

        def expire():
            start.wait()
            return self.store.expire_run(self.context, now=lifecycle_now)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: expire(), range(2)))

        self.assertEqual(
            sorted(result.status for result in results),
            ["changed", "no_op"],
        )
        self.assertEqual(sum(result.records_changed for result in results), 1)
        self.assertEqual(
            self.store.get_record_unchecked(record.artifact_id).lifecycle_status,
            "expired",
        )

    def test_cross_user_case_and_workspace_contexts_are_denied(self) -> None:
        record = self._put_record(expires_in=timedelta(minutes=1))
        lifecycle_now = datetime.now(timezone.utc) + timedelta(minutes=2)
        wrong_contexts = (
            replace(self.context, user_id="other-user"),
            replace(self.context, case_id="other-case"),
            replace(self.context, workspace_model_id="other-workspace"),
        )

        for context in wrong_contexts:
            with self.subTest(context=context):
                with self.assertRaises(ArtifactStoreError) as denied:
                    self.store.expire_run(context, now=lifecycle_now)
                self.assertEqual(denied.exception.code, "artifact_access_denied")

        unchanged = self.store.get_record_unchecked(record.artifact_id)
        self.assertEqual(unchanged.lifecycle_status, "visible_safe")
        self.assertEqual(unchanged.purge_status, "active")

    def test_two_concurrent_purge_callers_and_replay_have_one_winner(self) -> None:
        record = self._put_record(private=True)
        start = threading.Barrier(2)

        def purge():
            start.wait()
            return self.store.purge_run(self.context)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: purge(), range(2)))

        self.assertEqual(
            sorted(result.status for result in results),
            ["changed", "no_op"],
        )
        self.assertEqual(sum(result.records_changed for result in results), 1)
        purged = self.store.get_record_unchecked(record.artifact_id)
        purged_at = purged.purged_at

        replay = self.store.purge_run(self.context)
        after_replay = self.store.get_record_unchecked(record.artifact_id)

        self.assertEqual(replay.status, "no_op")
        self.assertEqual(after_replay.purged_at, purged_at)
        self.assertEqual(after_replay.storage_backend, "none_tombstone")
        self.assertIsNone(after_replay.payload_ref)
        with self.assertRaises(ArtifactStoreError) as unavailable:
            ArtifactResolver(self.store).resolve(record.artifact_id, self.context)
        self.assertEqual(unavailable.exception.code, "artifact_purged")

    def test_filesystem_failure_retains_pending_then_concurrent_retry_purges(self) -> None:
        record = self._put_record(private=True)
        stored = self.store.get_record_unchecked(record.artifact_id)
        payload_path = self.payload_root / str(stored.payload_ref)
        self.assertTrue(payload_path.exists())

        with mock.patch.object(
            Path,
            "unlink",
            side_effect=PermissionError("synthetic deletion denied"),
        ):
            with self.assertRaises(PermissionError):
                self.store.purge_run(self.context)

        pending = self.store.get_record_unchecked(record.artifact_id)
        self.assertEqual(pending.lifecycle_status, "purge_pending")
        self.assertEqual(pending.purge_status, "purge_pending")
        self.assertTrue(payload_path.exists())
        with self.assertRaises(ArtifactStoreError) as unresolved:
            ArtifactResolver(self.store).resolve(record.artifact_id, self.context)
        self.assertEqual(unresolved.exception.code, "artifact_purge_pending")
        with self.assertRaises(ArtifactStoreError) as direct_read:
            self.store.read_payload(pending)
        self.assertEqual(direct_read.exception.code, "artifact_purge_pending")

        with closing(sqlite3.connect(self.sqlite_path)) as conn:
            claim = conn.execute(
                """
                SELECT lifecycle_claim_id
                FROM artifact_records
                WHERE artifact_id = ?
                """,
                (record.artifact_id,),
            ).fetchone()
        self.assertIsNone(claim[0])

        retry_start = threading.Barrier(2)

        def retry_purge():
            retry_start.wait()
            return self.store.purge_run(self.context)

        with ThreadPoolExecutor(max_workers=2) as pool:
            retry_results = list(
                pool.map(lambda _index: retry_purge(), range(2))
            )

        self.assertEqual(
            sorted(result.status for result in retry_results),
            ["changed", "no_op"],
        )
        self.assertEqual(
            sum(result.records_changed for result in retry_results),
            1,
        )
        purged = self.store.get_record_unchecked(record.artifact_id)
        self.assertEqual(purged.lifecycle_status, "purged")
        self.assertEqual(purged.purge_status, "purged")
        self.assertFalse(payload_path.exists())

        replay = self.store.purge_run(self.context)
        self.assertEqual(replay.status, "no_op")

    def test_source_cleanup_is_exact_scoped_and_idempotent(self) -> None:
        selected = self._put_record(private=True, source_file_id="source-a")
        unrelated = self._put_record(private=True, source_file_id="source-b")
        source_context = replace(self.context, source_file_id="source-a")

        first = self.store.mark_source_file_deleted(source_context)
        replay = self.store.mark_source_file_deleted(source_context)

        self.assertEqual(first.status, "changed")
        self.assertEqual(first.artifact_ids, (selected.artifact_id,))
        self.assertEqual(replay.status, "no_op")
        self.assertEqual(
            self.store.get_record_unchecked(selected.artifact_id).purge_status,
            "purged",
        )
        self.assertEqual(
            self.store.get_record_unchecked(unrelated.artifact_id).purge_status,
            "active",
        )
        with self.assertRaises(ArtifactStoreError) as wrong_source:
            self.store.mark_source_file_deleted(
                replace(self.context, source_file_id="source-missing")
            )
        self.assertEqual(wrong_source.exception.code, "artifact_access_denied")

    def test_case_and_chat_cleanup_remain_run_bound(self) -> None:
        selected = self._put_record(private=True)
        other_context = replace(
            self.context,
            normalization_run_id="run-other",
        )
        unrelated = self._put_record(private=True, context=other_context)

        result = self.store.purge_case(self.context)

        self.assertEqual(result.artifact_ids, (selected.artifact_id,))
        self.assertEqual(
            self.store.get_record_unchecked(unrelated.artifact_id).purge_status,
            "active",
        )

        chat_context = ArtifactAccessContext(
            user_id="user-chat",
            case_id=None,
            chat_id="chat-only",
            workspace_model_id="broker_reports_gate1_pipe",
            normalization_run_id="run-chat",
            allow_private=True,
        )
        chat_record = self._put_record(private=True, context=chat_context)
        chat_result = self.store.purge_chat(chat_context)
        self.assertEqual(chat_result.artifact_ids, (chat_record.artifact_id,))
        with self.assertRaises(ArtifactStoreError) as missing_case:
            self.store.purge_case(chat_context)
        self.assertEqual(missing_case.exception.code, "artifact_scope_unverified")

    def test_maintained_cleanup_has_composite_indexes_and_no_global_fallback(
        self,
    ) -> None:
        source = inspect.getsource(SqliteArtifactStoreAdapter)
        self.assertNotIn("def expire_artifacts", source)
        self.assertNotIn("def _active_records", source)

        with closing(sqlite3.connect(self.sqlite_path)) as conn:
            indexes = {
                str(row[1])
                for row in conn.execute("PRAGMA index_list(artifact_records)")
            }
            plan = conn.execute(
                """
                EXPLAIN QUERY PLAN
                SELECT artifact_id
                FROM artifact_records
                WHERE user_id = ?
                  AND case_id = ?
                  AND workspace_model_id IS ?
                  AND normalization_run_id = ?
                  AND lifecycle_status = ?
                  AND purge_status = ?
                  AND expires_at <= ?
                """,
                (
                    self.context.user_id,
                    self.context.case_id,
                    self.context.workspace_model_id,
                    self.context.normalization_run_id,
                    "visible_safe",
                    "active",
                    datetime.now(timezone.utc).isoformat(),
                ),
            ).fetchall()

        self.assertTrue(
            {
                "idx_artifact_lifecycle_case_run",
                "idx_artifact_lifecycle_chat_run",
                "idx_artifact_lifecycle_source_run",
            }
            <= indexes
        )
        self.assertIn(
            "idx_artifact_lifecycle_case_run",
            " ".join(str(row[3]) for row in plan),
        )

    def _put_record(
        self,
        *,
        private: bool = False,
        expires_in: timedelta = timedelta(days=1),
        source_file_id: str = "source-default",
        context: ArtifactAccessContext | None = None,
    ) -> ArtifactRecord:
        selected_context = context or self.context
        lifecycle = "private_ready" if private else "visible_safe"
        visibility = "private_case" if private else "safe_internal"
        storage = (
            "project_artifact_payload"
            if private
            else "project_artifact_store"
        )
        record = ArtifactRecord(
            artifact_id=new_artifact_id(),
            artifact_type=(
                "private_normalized_text_slice_v0"
                if private
                else "validation_result_v0"
            ),
            case_id=selected_context.case_id,
            chat_id=selected_context.chat_id,
            user_id=selected_context.user_id,
            workspace_model_id=selected_context.workspace_model_id,
            normalization_run_id=selected_context.normalization_run_id,
            document_id="document-lifecycle",
            source_file_ref={
                "provider": "openwebui",
                "openwebui_file_id": source_file_id,
                "source_deleted": False,
            },
            visibility=visibility,
            storage_backend=storage,
            retention_policy=build_retention_policy(
                mode="api_smoke",
                ttl_seconds=24 * 60 * 60,
            ),
            access_policy={"scope": "case_private" if private else "safe"},
            validation_status="validated",
            lifecycle_status=lifecycle,
            expires_at=(datetime.now(timezone.utc) + expires_in).isoformat(),
            payload={"synthetic": True, "private": private},
        )
        return self.store.put_record(record)


if __name__ == "__main__":
    unittest.main()
