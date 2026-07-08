from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
    render_chat_content,
)
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.artifact_retention import RetentionPolicyError
from broker_reports_gate1.artifact_store import FACTORY_REQUIRED, FORBIDDEN, new_artifact_id


FIXTURES = REPO / "docs" / "stage2" / "testdata" / "broker_reports_gate1_normalization"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class BrokerReportsGate1ArtifactStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()

    def test_factory_anchors_prevent_artifact_store_drift(self):
        self.assertIn("ArtifactStoreFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not instantiate SqliteArtifactStoreAdapter directly", FORBIDDEN)

    def test_gate1_run_persists_safe_private_and_handoff_artifacts(self):
        result, context, manifest = self._persist_clean_run()
        records = self.store.list_by_run(context.normalization_run_id)
        types = {record.artifact_type for record in records}

        self.assertIn("normalization_run_v0", types)
        self.assertIn("document_inventory_v0", types)
        self.assertIn("technical_readability_profile_v0", types)
        self.assertIn("taxonomy_candidates_v0", types)
        self.assertIn("normalization_blockers_v0", types)
        self.assertIn("validation_result_v0", types)
        self.assertIn("chat_visible_normalization_report_v0", types)
        self.assertIn("private_normalized_text_slice_v0", types)
        self.assertIn("private_normalized_table_slice_v0", types)
        self.assertIn("gate2_handoff_v0", types)
        self.assertIn("source_file_ref_v0", types)
        self.assertTrue(manifest.private_slice_refs)
        self.assertTrue(manifest.safe_refs)
        for record in records:
            self.assertEqual(record.user_id, context.user_id)
            self.assertEqual(record.case_id, context.case_id)
            self.assertEqual(record.normalization_run_id, context.normalization_run_id)
            self.assertEqual(record.purge_status, "active")
            self.assertEqual(record.validation_status, "validated")
            self.assertIsNotNone(record.retention_policy.expires_at)
        private_records = [record for record in records if record.visibility == "private_case"]
        self.assertTrue(private_records)
        for record in private_records:
            self.assertEqual(record.storage_backend, "project_artifact_payload")
            self.assertTrue(record.payload_ref)
            self.assertIsNone(record.payload)
        self.assertFalse(result.safe_report["safety_flags"]["customer_docs_loaded_to_knowledge"])

    def test_compact_chat_report_is_not_full_json_and_has_safe_run_ref(self):
        result, _context, _manifest = self._persist_clean_run()

        content = render_chat_content(result.safe_report)

        self.assertIn("Нормализация завершена.", content)
        self.assertIn("Обработано файлов: 2", content)
        self.assertIn("Техническая ссылка: run normrun_", content)
        self.assertNotIn("```json", content)
        self.assertNotIn("private_normalized_slices", content)
        self.assertNotIn("openwebui-file-csv-1", content)
        self.assertNotIn("synthetic_operations.csv", content)
        self.assertNotIn("SYNTH-ACCOUNT-001", content)
        self.assertNotIn("SYNTH-A,1,SYNTH-FCY", content)

    def test_resolver_allows_same_context_safe_and_private_refs(self):
        _result, context, manifest = self._persist_clean_run()
        resolver = ArtifactResolver(self.store)

        safe = resolver.resolve(manifest.safe_refs[0], context)
        private = resolver.resolve(
            manifest.private_slice_refs[0],
            ArtifactAccessContext(**{**context.__dict__, "allow_private": True}),
        )

        self.assertIsNotNone(safe["payload"])
        self.assertIn(private["record"].artifact_type, {"private_normalized_text_slice_v0", "private_normalized_table_slice_v0"})
        self.assertIsNotNone(private["payload"])

    def test_resolver_denies_wrong_user_case_chat_expired_purged_blocked_and_privacy_failed(self):
        _result, context, manifest = self._persist_clean_run()
        resolver = ArtifactResolver(self.store)

        self._assert_resolve_error(
            resolver,
            manifest.safe_refs[0],
            ArtifactAccessContext(**{**context.__dict__, "user_id": "wrong-user"}),
            "artifact_access_denied",
        )
        self._assert_resolve_error(
            resolver,
            manifest.safe_refs[0],
            ArtifactAccessContext(**{**context.__dict__, "case_id": "wrong-case"}),
            "artifact_access_denied",
        )
        self._assert_resolve_error(
            resolver,
            manifest.safe_refs[0],
            ArtifactAccessContext(**{**context.__dict__, "workspace_model_id": None}),
            "artifact_scope_unverified",
        )

        _chat_result, chat_context, chat_manifest = self._persist_clean_run(case_id=None, chat_id="chat-only-1")
        self._assert_resolve_error(
            resolver,
            chat_manifest.safe_refs[0],
            ArtifactAccessContext(**{**chat_context.__dict__, "chat_id": "wrong-chat"}),
            "artifact_access_denied",
        )

        self.store.expire_artifacts(now=datetime.now(timezone.utc) + timedelta(days=8))
        self._assert_resolve_error(resolver, manifest.safe_refs[0], context, "artifact_expired")

        result2, context2, manifest2 = self._persist_clean_run(case_id="case-purge")
        private_ref = manifest2.private_slice_refs[0]
        private_record = self.store.get_record_unchecked(private_ref)
        self.assertIsNotNone(private_record)
        payload_path = Path(self._tmp.name) / "payloads" / str(private_record.payload_ref)
        self.assertTrue(payload_path.exists())
        self.store.purge_run(context2.normalization_run_id)
        self.assertFalse(payload_path.exists())
        self._assert_resolve_error(resolver, private_ref, context2, "artifact_purged")
        purged_record = self.store.get_record_unchecked(private_ref)
        self.assertEqual(purged_record.storage_backend, "none_tombstone")
        self.assertIsNone(purged_record.payload)
        self.assertIsNone(purged_record.payload_ref)
        with self.assertRaises(ArtifactStoreError) as restore:
            self.store.put_record(purged_record)
        self.assertEqual(restore.exception.code, "artifact_purged")
        self.assertEqual(result2.safe_report["validation_result"]["status"], "passed")

        blocked_result, blocked_context, blocked_manifest = self._persist_blocked_run()
        handoff_ref = blocked_manifest.gate2_handoff_ref
        self._assert_resolve_error(resolver, handoff_ref, blocked_context, "artifact_blocked")
        self.assertEqual(blocked_result.safe_report["gate2_handoff_status"], "blocked")

        privacy_result, privacy_context, privacy_manifest = self._persist_privacy_failed_run()
        self._assert_resolve_error(
            resolver,
            privacy_manifest.safe_refs[0],
            privacy_context,
            "artifact_privacy_failed",
        )
        self.assertEqual(privacy_result.safe_report["run_status"], "privacy_failed")

    def test_retention_modes_and_purge_triggers(self):
        retention = build_retention_policy(mode="api_smoke", ttl_seconds=24 * 60 * 60)
        self.assertEqual(retention.mode, "api_smoke")
        self.assertEqual(retention.ttl_seconds, 24 * 60 * 60)
        with self.assertRaises(RetentionPolicyError) as missing_customer:
            build_retention_policy(mode="customer_approved_test", explicit=False)
        self.assertEqual(missing_customer.exception.code, "retention_policy_missing")
        explicit_customer = build_retention_policy(mode="customer_approved_test", explicit=True)
        self.assertEqual(explicit_customer.ttl_seconds, 14 * 24 * 60 * 60)

        _result, context, manifest = self._persist_clean_run(case_id="case-delete")
        source_file_id = "openwebui-file-csv-1"
        affected = self.store.mark_source_file_deleted(openwebui_file_id=source_file_id)
        self.assertTrue(affected)
        for private_ref in manifest.private_slice_refs:
            record = self.store.get_record_unchecked(private_ref)
            if (record.source_file_ref or {}).get("openwebui_file_id") == source_file_id:
                self.assertEqual(record.purge_status, "purged")

        _chat_result, chat_context, _chat_manifest = self._persist_clean_run(case_id=None, chat_id="chat-delete-1")
        purged_chat = self.store.purge_chat(chat_id="chat-delete-1")
        self.assertTrue(purged_chat)
        for record in self.store.list_by_run(chat_context.normalization_run_id):
            self.assertEqual(record.purge_status, "purged")

        _case_result, case_context, _case_manifest = self._persist_clean_run(case_id="case-delete-2")
        purged_case = self.store.purge_case(case_id="case-delete-2")
        self.assertTrue(purged_case)
        for record in self.store.list_by_run(case_context.normalization_run_id):
            self.assertEqual(record.purge_status, "purged")

    def test_knowledge_backend_is_rejected_for_private_or_customer_artifacts(self):
        result, context, _manifest = self._persist_clean_run(case_id="knowledge-guard")
        record = ArtifactRecord(
            artifact_id=new_artifact_id(),
            artifact_type="private_normalized_text_slice_v0",
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            normalization_run_id=context.normalization_run_id,
            document_id="brdoc_001_test",
            source_file_ref=None,
            visibility="private_case",
            storage_backend="openwebui_knowledge",
            retention_policy=build_retention_policy(mode="api_smoke"),
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status="private_ready",
            payload={"private": "synthetic"},
        )

        with self.assertRaises(ArtifactStoreError) as forbidden:
            self.store.put_record(record)

        self.assertEqual(forbidden.exception.code, "knowledge_storage_forbidden")
        self.assertFalse(result.safe_report["safety_flags"]["customer_docs_loaded_to_knowledge"])
        self.assertFalse(any(r.storage_backend == "openwebui_knowledge" for r in self.store.list_by_run(context.normalization_run_id)))

    def test_gate2_handoff_contains_opaque_refs_not_chat_json(self):
        _result, context, manifest = self._persist_clean_run()
        resolver = ArtifactResolver(self.store)

        resolved = resolver.resolve(manifest.gate2_handoff_ref, context)
        payload = resolved["payload"]
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)

        self.assertEqual(payload["artifact_type"], "gate2_handoff_v0")
        self.assertEqual(payload["validation_status"], "validated")
        self.assertEqual(payload["handoff_status"], "ready_with_safe_refs")
        self.assertEqual(payload["private_slice_refs"], manifest.private_slice_refs)
        self.assertNotIn("```json", rendered)
        self.assertNotIn("SYNTH-ACCOUNT-001", rendered)
        self.assertNotIn("synthetic_operations.csv", rendered)

    def _persist_clean_run(self, *, case_id: str | None = "case-1", chat_id: str = "chat-1"):
        run_suffix = case_id or chat_id
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref=f"openwebui-file-csv-1-{run_suffix}",
                    filename="synthetic_operations.csv",
                    content=fixture_bytes("synthetic_operations.csv"),
                    mime_type="text/csv",
                    source_kind="openwebui_pipe",
                ),
                FileInput.from_bytes(
                    private_ref=f"openwebui-file-txt-1-{run_suffix}",
                    filename="synthetic_broker_report.txt",
                    content=fixture_bytes("synthetic_broker_report.txt"),
                    mime_type="text/plain",
                    source_kind="openwebui_pipe",
                ),
            ],
            input_context={"test_case": "artifact_store"},
            entrypoint="artifact_store_test",
            trigger_type="backend_core",
        )
        context = ArtifactAccessContext(
            user_id="user-1",
            case_id=case_id,
            chat_id=chat_id,
            workspace_model_id="broker_reports_gate1_pipe",
            normalization_run_id=result.package["normalization_run"]["run_id"],
            allow_private=True,
        )
        manifest = persist_gate1_result(
            store=self.store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
            source_file_refs=[
                {
                    "provider": "openwebui",
                    "openwebui_file_id": "openwebui-file-csv-1",
                    "content_type": "text/csv",
                    "size_bytes": len(fixture_bytes("synthetic_operations.csv")),
                    "source_deleted": False,
                },
                {
                    "provider": "openwebui",
                    "openwebui_file_id": "openwebui-file-txt-1",
                    "content_type": "text/plain",
                    "size_bytes": len(fixture_bytes("synthetic_broker_report.txt")),
                    "source_deleted": False,
                },
            ],
        )
        return result, context, manifest

    def _persist_blocked_run(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="openwebui-file-unknown-1",
                    filename="synthetic_unknown.bin",
                    content=fixture_bytes("synthetic_unknown.bin"),
                    mime_type="application/octet-stream",
                    source_kind="openwebui_pipe",
                )
            ],
            input_context={"test_case": "blocked_artifact_store"},
        )
        context = ArtifactAccessContext(
            user_id="user-blocked",
            case_id="case-blocked",
            chat_id="chat-blocked",
            normalization_run_id=result.package["normalization_run"]["run_id"],
            allow_private=True,
        )
        manifest = persist_gate1_result(
            store=self.store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
            source_file_refs=[
                {
                    "provider": "openwebui",
                    "openwebui_file_id": "openwebui-file-unknown-1",
                    "content_type": "application/octet-stream",
                    "size_bytes": len(fixture_bytes("synthetic_unknown.bin")),
                    "source_deleted": False,
                }
            ],
        )
        return result, context, manifest

    def _persist_privacy_failed_run(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="privacy-file-1",
                    filename="synthetic_operations.csv",
                    content=fixture_bytes("synthetic_operations.csv"),
                    mime_type="text/csv",
                )
            ],
            input_context={"test_case": "privacy_failed"},
            entrypoint="privacy_marker_entrypoint",
            extra_private_markers=["privacy_marker_entrypoint"],
        )
        context = ArtifactAccessContext(
            user_id="user-privacy",
            case_id="case-privacy",
            chat_id="chat-privacy",
            normalization_run_id=result.package["normalization_run"]["run_id"],
            allow_private=True,
        )
        manifest = persist_gate1_result(
            store=self.store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
        )
        return result, context, manifest

    def _assert_resolve_error(self, resolver: ArtifactResolver, artifact_id: str, context: ArtifactAccessContext, code: str) -> None:
        with self.assertRaises(ArtifactStoreError) as raised:
            resolver.resolve(artifact_id, context)
        self.assertEqual(raised.exception.code, code)


if __name__ == "__main__":
    unittest.main()
