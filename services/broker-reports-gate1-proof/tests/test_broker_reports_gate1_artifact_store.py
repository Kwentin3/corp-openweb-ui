from __future__ import annotations

import copy
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

    def test_document_extraction_packet_is_private_payload_artifact(self):
        retention = build_retention_policy(mode="customer_approved_test", explicit=True)
        record = ArtifactRecord(
            artifact_id=new_artifact_id(),
            artifact_type="broker_reports_document_extraction_packet_v0",
            case_id="case_packet",
            chat_id="chat_packet",
            user_id="user_packet",
            workspace_model_id="broker_reports_gate2_domain_source_fact_pipe",
            normalization_run_id="norm_packet",
            document_id="doc_packet",
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=retention,
            access_policy={"scope": "case_private"},
            validation_status="validated",
            lifecycle_status="private_ready",
            payload={"schema_version": "broker_reports_document_extraction_packet_v0"},
            safe_metadata={"coverage_uncovered_total": 0},
        )

        stored = self.store.put_record(record)
        payload = self.store.read_payload(stored)

        self.assertEqual(stored.artifact_type, "broker_reports_document_extraction_packet_v0")
        self.assertEqual(stored.visibility, "private_case")
        self.assertEqual(stored.storage_backend, "project_artifact_payload")
        self.assertTrue(stored.payload_ref)
        self.assertEqual(payload["schema_version"], "broker_reports_document_extraction_packet_v0")

    def test_put_record_is_idempotent_but_rejects_semantic_overwrite(self):
        retention = build_retention_policy(mode="api_smoke")
        record = ArtifactRecord(
            artifact_id=new_artifact_id(),
            artifact_type="validation_result_v0",
            case_id="case-immutable",
            chat_id="chat-immutable",
            user_id="user-immutable",
            normalization_run_id="norm-immutable",
            document_id=None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            retention_policy=retention,
            access_policy={"requires_user_id": True},
            validation_status="validated",
            lifecycle_status="visible_safe",
            payload={"schema_version": "validation_result_v0", "status": "passed"},
            safe_metadata={"status": "passed"},
        )

        first = self.store.put_record(record)
        replay = self.store.put_record(copy.deepcopy(record))
        changed = copy.deepcopy(record)
        changed.payload["status"] = "failed"
        changed.safe_metadata["status"] = "failed"

        with self.assertRaises(ArtifactStoreError) as overwritten:
            self.store.put_record(changed)

        self.assertEqual(replay.artifact_id, first.artifact_id)
        self.assertEqual(overwritten.exception.code, "artifact_immutable")
        self.assertEqual(self.store.read_payload(first)["status"], "passed")

    def test_gate1_run_persists_safe_private_and_handoff_artifacts(self):
        result, context, manifest = self._persist_clean_run()
        records = self.store.list_by_run(context.normalization_run_id)
        case_records = self.store.list_by_case(str(context.case_id))
        types = {record.artifact_type for record in records}

        self.assertEqual(
            {record.artifact_id for record in records},
            {record.artifact_id for record in case_records},
        )

        self.assertIn("normalization_run_v0", types)
        self.assertIn("document_inventory_v0", types)
        self.assertIn("technical_readability_profile_v0", types)
        self.assertIn("taxonomy_candidates_v0", types)
        self.assertIn("normalization_blockers_v0", types)
        self.assertIn("broker_reports_file_processing_batch_v1", types)
        self.assertIn("document_source_eligibility_v0", types)
        self.assertIn("gate1_issue_ledger_v0", types)
        self.assertIn("document_usage_classification_v0", types)
        self.assertIn("domain_context_packet_v0", types)
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
            if record.artifact_type in {
                "private_normalized_text_slice_v0",
                "private_normalized_table_slice_v0",
            }:
                self.assertEqual(
                    record.safe_metadata["source_unit_schema_version"],
                    "source_unit_provenance_v0",
                )
                self.assertTrue(record.safe_metadata["source_checksum_ref"])
                self.assertTrue(record.safe_metadata["parser_ref"])
                self.assertTrue(record.safe_metadata["coverage_ref"])
                self.assertTrue(record.safe_metadata["coverage_complete"])
        handoff_record = next(record for record in records if record.artifact_type == "gate2_handoff_v0")
        self.assertEqual(
            handoff_record.safe_metadata["source_fact_input_manifest_status"],
            "resolver_ready",
        )
        self.assertFalse(result.safe_report["safety_flags"]["customer_docs_loaded_to_knowledge"])

    def test_compact_chat_report_is_not_full_json_and_has_safe_run_ref(self):
        result, _context, _manifest = self._persist_clean_run()

        content = render_chat_content(result.safe_report)

        self.assertIn("Нормализация завершена.", content)
        self.assertIn("Получено документов: 2", content)
        self.assertIn("Итог Gate 1: пакет поглощен", content)
        self.assertIn("Контекст домена:", content)
        self.assertIn("Техническая ссылка: run normrun_", content)
        self.assertNotIn("```json", content)
        self.assertNotIn("private_normalized_slices", content)
        self.assertNotIn("openwebui-file-csv-1", content)
        self.assertNotIn("synthetic_operations.csv", content)
        self.assertNotIn("SYNTH-ACCOUNT-001", content)
        self.assertNotIn("SYNTH-A,1,SYNTH-FCY", content)

    def test_compact_chat_report_explains_cross_page_continuation_outcome(self):
        result, _context, _manifest = self._persist_clean_run()
        report = dict(result.safe_report)
        report["pdf_structural_repair_shadow"] = {
            "summary": {
                "enabled": True,
                "tables_selected": 2,
                "accepted_supplied_consensus_tables": 2,
                "continuation_groups_discovered": 1,
                "continuation_groups_accepted": 1,
                "continuation_groups_failed": 0,
                "semantic_header_shadow_enabled": True,
                "semantic_projection_status_counts": {"projected": 2},
                "private_semantic_projections_persisted": 2,
            }
        }

        content = render_chat_content(report)

        self.assertIn(
            "Продолжения таблиц на соседней странице: найдено 1; "
            "аккуратно объединено 1; требует проверки 0.",
            content,
        )
        self.assertIn("основной результат Gate 2 не изменён", content)
        self.assertIn(
            "Семантические заголовки: сохранено приватных проекций 2; "
            "статусы: projected: 2.",
            content,
        )

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

        self.store.expire_run(
            context,
            now=datetime.now(timezone.utc) + timedelta(days=8),
        )
        self._assert_resolve_error(resolver, manifest.safe_refs[0], context, "artifact_expired")

        result2, context2, manifest2 = self._persist_clean_run(case_id="case-purge")
        private_ref = manifest2.private_slice_refs[0]
        private_record = self.store.get_record_unchecked(private_ref)
        self.assertIsNotNone(private_record)
        payload_path = Path(self._tmp.name) / "payloads" / str(private_record.payload_ref)
        self.assertTrue(payload_path.exists())
        self.store.purge_run(context2)
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
        affected = self.store.mark_source_file_deleted(
            ArtifactAccessContext(
                **{**context.__dict__, "source_file_id": source_file_id}
            )
        )
        self.assertEqual(affected.status, "changed")
        for private_ref in manifest.private_slice_refs:
            record = self.store.get_record_unchecked(private_ref)
            if (record.source_file_ref or {}).get("openwebui_file_id") == source_file_id:
                self.assertEqual(record.purge_status, "purged")

        _chat_result, chat_context, _chat_manifest = self._persist_clean_run(case_id=None, chat_id="chat-delete-1")
        purged_chat = self.store.purge_chat(chat_context)
        self.assertEqual(purged_chat.status, "changed")
        for record in self.store.list_by_run(chat_context.normalization_run_id):
            self.assertEqual(record.purge_status, "purged")

        _case_result, case_context, _case_manifest = self._persist_clean_run(case_id="case-delete-2")
        purged_case = self.store.purge_case(case_context)
        self.assertEqual(purged_case.status, "changed")
        for record in self.store.list_by_run(case_context.normalization_run_id):
            self.assertEqual(record.purge_status, "purged")

    def test_expire_run_is_index_scoped_and_does_not_scan_other_runs(self):
        _first_result, first_context, _first_manifest = self._persist_clean_run(
            case_id="case-expire-run-first"
        )
        _second_result, second_context, _second_manifest = self._persist_clean_run(
            case_id="case-expire-run-second"
        )

        self.assertFalse(hasattr(self.store, "_active_records"))
        expired = self.store.expire_run(
            first_context,
            now=datetime.now(timezone.utc) + timedelta(days=8),
        )

        first_records = self.store.list_by_run(first_context.normalization_run_id)
        second_records = self.store.list_by_run(second_context.normalization_run_id)
        self.assertEqual(expired.records_changed, len(first_records))
        self.assertEqual(expired.status, "changed")
        self.assertTrue(all(record.lifecycle_status == "expired" for record in first_records))
        self.assertTrue(all(record.purge_status == "expired" for record in first_records))
        self.assertTrue(all(record.lifecycle_status != "expired" for record in second_records))
        self.assertTrue(all(record.purge_status == "active" for record in second_records))

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
        self.assertEqual(payload["handoff_mode"], "full_package_ready_for_gate2")
        self.assertTrue(payload["eligibility_ref"])
        self.assertTrue(payload["issue_ledger_ref"])
        self.assertTrue(payload["document_usage_classification_ref"])
        self.assertTrue(payload["domain_context_packet_ref"])
        self.assertTrue(payload["document_memory_manifest_ref"])
        self.assertEqual(
            payload["domain_stage_readiness"]["source_fact_extraction"],
            "ready_with_issue_context",
        )
        self.assertEqual(len(payload["included_document_refs"]), 2)
        self.assertEqual(payload["excluded_document_refs"], [])
        self.assertEqual(payload["pending_review_refs"], [])
        self.assertEqual(payload["source_policy_review_refs"], [])
        self.assertEqual(payload["ocr_required_refs"], [])
        self.assertEqual(payload["private_slice_refs"], manifest.private_slice_refs)
        self.assertNotIn("```json", rendered)
        self.assertNotIn("SYNTH-ACCOUNT-001", rendered)
        self.assertNotIn("synthetic_operations.csv", rendered)

    def test_gate2_handoff_carries_next_stage_refs_for_source_ready_non_primary_docs(self):
        csv_content = fixture_bytes("synthetic_operations.csv")
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="handoff-primary-csv",
                    filename="synthetic_operations.csv",
                    content=csv_content,
                    mime_type="text/csv",
                    source_kind="openwebui_pipe",
                ),
                FileInput.from_bytes(
                    private_ref="handoff-duplicate-csv",
                    filename="synthetic_operations_duplicate.csv",
                    content=csv_content,
                    mime_type="text/csv",
                    source_kind="openwebui_pipe",
                ),
            ],
            input_context={"test_case": "artifact_store_next_stage_refs"},
        )
        context = ArtifactAccessContext(
            user_id="user-next-stage",
            case_id="case-next-stage",
            chat_id="chat-next-stage",
            workspace_model_id="broker_reports_gate1_pipe",
            normalization_run_id=result.package["normalization_run"]["run_id"],
            allow_private=True,
        )
        manifest = persist_gate1_result(
            store=self.store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
        )

        handoff = ArtifactResolver(self.store).resolve(manifest.gate2_handoff_ref, context)["payload"]
        next_stage_refs = handoff["next_stage_refs"]

        self.assertEqual(handoff["next_stage_ref_summary"]["dropped_source_ready_total"], 0)
        self.assertEqual(len(next_stage_refs["source_fact_ready_refs"]), 2)
        self.assertEqual(len(next_stage_refs["primary_source_extraction_refs"]), 1)
        self.assertEqual(len(next_stage_refs["duplicate_or_non_primary_refs"]), 1)
        self.assertEqual(set(next_stage_refs["source_ready_not_primary_refs"]), set(next_stage_refs["duplicate_or_non_primary_refs"]))
        self.assertTrue(handoff["private_slice_refs_by_next_stage_bucket"]["primary_source_extraction_refs"])
        self.assertTrue(handoff["private_slice_refs_by_next_stage_bucket"]["duplicate_or_non_primary_refs"])
        self.assertNotEqual(
            set(handoff["private_slice_refs_by_next_stage_bucket"]["primary_source_extraction_refs"]),
            set(handoff["private_slice_refs_by_next_stage_bucket"]["duplicate_or_non_primary_refs"]),
        )

    def test_reduced_handoff_contains_eligibility_refs_and_only_included_private_refs(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="reduced-csv-1",
                    filename="synthetic_operations.csv",
                    content=fixture_bytes("synthetic_operations.csv"),
                    mime_type="text/csv",
                    source_kind="openwebui_pipe",
                ),
                FileInput.from_bytes(
                    private_ref="reduced-unknown-role-1",
                    filename="synthetic_note.txt",
                    content=b"Just a synthetic note without document role signals.",
                    mime_type="text/plain",
                    source_kind="openwebui_pipe",
                ),
                FileInput.from_bytes(
                    private_ref="reduced-raster-1",
                    filename="synthetic_raster.pdf",
                    content=self._synthetic_raster_pdf_bytes(),
                    mime_type="application/pdf",
                    source_kind="openwebui_pipe",
                ),
                FileInput.from_bytes(
                    private_ref="reduced-unsupported-1",
                    filename="synthetic_unknown.bin",
                    content=fixture_bytes("synthetic_unknown.bin"),
                    mime_type="application/octet-stream",
                    source_kind="openwebui_pipe",
                ),
            ],
            input_context={"test_case": "artifact_store_reduced_handoff"},
        )
        context = ArtifactAccessContext(
            user_id="user-reduced",
            case_id="case-reduced",
            chat_id="chat-reduced",
            workspace_model_id="broker_reports_gate1_pipe",
            normalization_run_id=result.package["normalization_run"]["run_id"],
            allow_private=True,
        )
        manifest = persist_gate1_result(
            store=self.store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
        )
        resolver = ArtifactResolver(self.store)
        handoff = resolver.resolve(manifest.gate2_handoff_ref, context)["payload"]
        eligibility = resolver.resolve(handoff["eligibility_ref"], context)["payload"]
        records = self.store.list_by_run(context.normalization_run_id)
        types = {record.artifact_type for record in records}

        self.assertIn("document_source_eligibility_v0", types)
        self.assertIn("gate1_issue_ledger_v0", types)
        self.assertIn("document_usage_classification_v0", types)
        self.assertIn("domain_context_packet_v0", types)
        self.assertEqual(handoff["handoff_status"], "ready_with_reduced_subset")
        self.assertEqual(handoff["handoff_mode"], "reduced_subset_ready_for_gate2")
        self.assertTrue(handoff["reduced_subset_validated"])
        self.assertEqual(len(handoff["included_document_refs"]), 1)
        self.assertEqual(len(handoff["pending_review_refs"]), 1)
        self.assertEqual(len(handoff["source_policy_review_refs"]), 0)
        self.assertEqual(len(handoff["ocr_required_refs"]), 1)
        self.assertEqual(len(handoff["excluded_document_refs"]), 1)
        self.assertEqual(eligibility["schema_version"], "document_source_eligibility_v0")
        self.assertEqual(len(eligibility["entries"]), 4)
        self.assertTrue(handoff["issue_ledger_ref"])
        self.assertTrue(handoff["document_usage_classification_ref"])
        self.assertTrue(handoff["domain_context_packet_ref"])
        self.assertIn("source_fact_extraction", handoff["domain_stage_readiness"])
        self.assertTrue(handoff["unresolved_issue_refs"])
        self.assertLess(len(handoff["private_slice_refs"]), len(manifest.private_slice_refs))
        included_doc_ids = set(result.safe_report["gate2_handoff"]["included_document_ids"])
        for private_ref in handoff["private_slice_refs"]:
            private_record = self.store.get_record_unchecked(private_ref)
            self.assertIsNotNone(private_record)
            self.assertIn(private_record.document_id, included_doc_ids)
        rendered = json.dumps(handoff, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("```json", rendered)
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

    def _synthetic_raster_pdf_bytes(self) -> bytes:
        return (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /Resources << /XObject << /Im1 5 0 R >> >> /Contents 4 0 R >> endobj\n"
            b"4 0 obj << /Length 0 >> stream\nendstream endobj\n"
            b"5 0 obj << /Type /XObject /Subtype /Image /Width 10 /Height 10 >> endobj\n"
            b"%%EOF"
        )

    def _assert_resolve_error(self, resolver: ArtifactResolver, artifact_id: str, context: ArtifactAccessContext, code: str) -> None:
        with self.assertRaises(ArtifactStoreError) as raised:
            resolver.resolve(artifact_id, context)
        self.assertEqual(raised.exception.code, code)


if __name__ == "__main__":
    unittest.main()
