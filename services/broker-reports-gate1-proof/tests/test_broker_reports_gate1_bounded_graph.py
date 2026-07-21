from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreBackedList,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1BoundedGraphConfig,
    Gate1BoundedGraphError,
    Gate1BoundedGraphFactory,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    build_retention_policy,
    persist_gate1_result,
)
from scripts.profile_gate1_bounded_graph import (
    _VOLATILE_PAYLOAD_KEYS,
    _baseline_repository_revision,
    _baseline_resource_profile,
    _baseline_terminal_status_counts,
    _normalize_payload,
    _record_contract,
    _store_signature,
)
from broker_reports_gate1.validators import validate_artifacts


def _input(name: str, mime_type: str, content: bytes) -> FileInput:
    return FileInput(
        private_ref=f"private-{name}",
        original_filename_private=name,
        mime_type=mime_type,
        source_kind="upload",
        declared_size_bytes=len(content),
        bytes_provider=lambda value=content: value,
        provider_label="bounded_graph_test",
    )


def _inputs() -> list[FileInput]:
    return [
        _input("operations.csv", "text/csv", b"date,amount\n2026-01-01,12\n"),
        _input(
            "evidence.xml",
            "application/xml",
            b"<report><amount currency='USD'>12</amount></report>",
        ),
    ]


def _source_refs(inputs: list[FileInput]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "provider": "bounded_graph_test",
            "openwebui_file_id": f"file-{index}",
            "content_type": item.mime_type,
            "size_bytes": item.declared_size_bytes,
            "source_deleted": False,
        }
        for index, item in enumerate(inputs, start=1)
    )


def _plain(value: Any) -> Any:
    if isinstance(value, ArtifactStoreBackedList):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


class BrokerReportsGate1BoundedGraphTest(unittest.TestCase):
    def test_profile_output_can_be_the_next_deterministic_baseline(self):
        profile = {
            "schema_version": "broker_reports_gate1_bounded_graph_profile_safe_v1",
            "baseline": {"repository_revision": "revision-a"},
            "candidate": {
                "proof_wall_seconds": 10.0,
                "normalization_wall_seconds": 8.0,
                "process_peak_rss_bytes": 123,
            },
            "terminal": {"terminal_status_counts": {"complete": 2}},
        }

        self.assertEqual(
            _baseline_resource_profile(profile), profile["candidate"]
        )
        self.assertEqual(
            _baseline_terminal_status_counts(profile), {"complete": 2}
        )
        self.assertEqual(_baseline_repository_revision(profile), "revision-a")

    def _bounded_result(self, root: Path):
        inputs = _inputs()
        normalizer = Gate1Normalizer()
        run_id = normalizer.plan_run_id(inputs)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        context = ArtifactAccessContext(
            user_id="user-1",
            case_id="case-1",
            chat_id="chat-1",
            workspace_model_id="broker-reports",
            normalization_run_id=run_id,
            allow_private=True,
            require_source_available=True,
        )
        retention = build_retention_policy(
            mode="customer_approved_test",
            explicit=True,
        )
        source_refs = _source_refs(inputs)
        graph = Gate1BoundedGraphFactory(
            Gate1BoundedGraphConfig(
                store=store,
                context=context,
                retention_policy=retention,
                source_file_refs=source_refs,
            )
        ).create(normalization_run_id=run_id)
        result = normalizer.normalize(inputs, bounded_graph=graph)
        return result, graph, store, context, retention, source_refs

    def test_bounded_path_is_output_equivalent_and_retains_only_refs(self):
        legacy = Gate1Normalizer().normalize(_inputs())
        with tempfile.TemporaryDirectory() as temp:
            result, graph, store, *_ = self._bounded_result(Path(temp))

            self.assertEqual(_plain(result.package), legacy.package)
            self.assertEqual(result.safe_report, legacy.safe_report)
            receipt = graph.compact_receipt()
            self.assertTrue(receipt["sealed"])
            self.assertEqual(receipt["retained_payload_objects"], 0)
            self.assertTrue(receipt["retained_compact_refs_only"])
            self.assertEqual(receipt["source_records_total"], 2)

            for collection in graph.collections.values():
                self.assertEqual(list.__len__(collection), 0)
                self.assertGreater(len(collection), 0)
                self.assertIs(copy.deepcopy(collection), collection)
                for artifact_id in collection.artifact_ids:
                    record = store.get_record_unchecked(artifact_id)
                    self.assertIsNotNone(record)
                    self.assertIsNone(record.payload)
                    self.assertTrue(record.payload_ref)

    def test_persistence_reuses_sealed_records_and_gate2_remains_compatible(self):
        with tempfile.TemporaryDirectory() as temp:
            (
                result,
                graph,
                store,
                context,
                retention,
                source_refs,
            ) = self._bounded_result(Path(temp))
            records_before = store.list_by_run(context.normalization_run_id)

            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=retention,
                source_file_refs=list(source_refs),
            )

            for name, collection in graph.collections.items():
                artifact_type_refs = {
                    ref
                    for refs in manifest.artifact_refs_by_type.values()
                    for ref in refs
                }
                self.assertTrue(
                    set(collection.artifact_ids) <= artifact_type_refs, name
                )
            self.assertEqual(
                len(manifest.artifact_refs_by_type["source_file_ref_v0"]),
                2,
            )
            self.assertGreater(
                len(store.list_by_run(context.normalization_run_id)),
                len(records_before),
            )

            readiness = (
                Gate2InputReadinessFactory(store=store)
                .create()
                .audit_and_build(
                    domain_context_packet_ref=manifest.artifact_refs_by_type[
                        "domain_context_packet_v0"
                    ][0],
                    context=context,
                )
            )
            self.assertEqual(readiness.validation["validator_status"], "passed")
            self.assertTrue(readiness.validation["artifactstore_unchanged"])

    def test_legacy_and_bounded_artifactstore_contracts_are_equivalent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (
                result,
                _graph,
                bounded_store,
                context,
                retention,
                source_refs,
            ) = self._bounded_result(root / "bounded")
            persist_gate1_result(
                store=bounded_store,
                result=result,
                context=context,
                retention_policy=retention,
                source_file_refs=list(source_refs),
            )

            legacy_store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=root / "legacy" / "artifacts.sqlite3",
                    payload_root=root / "legacy" / "payloads",
                )
            ).create()
            legacy = Gate1Normalizer().normalize(_inputs())
            persist_gate1_result(
                store=legacy_store,
                result=legacy,
                context=context,
                retention_policy=retention,
                source_file_refs=list(source_refs),
            )

            bounded_signature = _store_signature(bounded_store.sqlite_path)
            legacy_signature = _store_signature(legacy_store.sqlite_path)
            for key in (
                "records_total",
                "payload_bytes_total",
                "records_by_type",
                "payload_bytes_by_type",
                "representation_checksum_set_digests",
                "representation_semantic_checksum_set_digests",
                "semantic_checksum_set_digests",
                "record_contract_set_digests",
            ):
                self.assertEqual(
                    bounded_signature[key],
                    legacy_signature[key],
                    key,
                )

    def test_factory_scope_and_seal_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            inputs = _inputs()
            normalizer = Gate1Normalizer()
            run_id = normalizer.plan_run_id(inputs)
            root = Path(temp)
            store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=root / "artifacts.sqlite3",
                    payload_root=root / "payloads",
                )
            ).create()
            context = ArtifactAccessContext(
                user_id="user-1",
                case_id="case-1",
                chat_id="chat-1",
                workspace_model_id="broker-reports",
                normalization_run_id=run_id,
                allow_private=True,
            )
            retention = build_retention_policy(
                mode="customer_approved_test",
                explicit=True,
            )
            graph = Gate1BoundedGraphFactory(
                Gate1BoundedGraphConfig(
                    store=store,
                    context=context,
                    retention_policy=retention,
                    source_file_refs=_source_refs(inputs),
                )
            ).create(normalization_run_id=run_id)

            with self.assertRaisesRegex(
                Gate1BoundedGraphError,
                "bounded_collection_copy_before_seal",
            ):
                copy.deepcopy(graph.collection("private_normalized_source_payloads"))
            with self.assertRaisesRegex(
                Gate1BoundedGraphError,
                "bounded_graph_context_run_mismatch",
            ):
                Gate1BoundedGraphFactory(
                    Gate1BoundedGraphConfig(
                        store=store,
                        context=context,
                        retention_policy=retention,
                        source_file_refs=(),
                    )
                ).create(normalization_run_id="different-run")

    def test_equivalence_oracle_excludes_only_declared_runtime_diagnostics(self):
        self.assertEqual(
            _VOLATILE_PAYLOAD_KEYS,
            {
                "created_at",
                "elapsed_milliseconds_total",
                "layout_elapsed_milliseconds",
            },
        )
        baseline = {
            "created_at": "first-run",
            "layout_elapsed_milliseconds": 10.25,
            "nested": {
                "elapsed_milliseconds_total": 20.5,
                "source_text": "same evidence",
            },
        }
        candidate = copy.deepcopy(baseline)
        candidate["created_at"] = "second-run"
        candidate["layout_elapsed_milliseconds"] = 11.75
        candidate["nested"]["elapsed_milliseconds_total"] = 22.0
        self.assertEqual(
            _normalize_payload(baseline, {}),
            _normalize_payload(candidate, {}),
        )

        candidate["nested"]["source_text"] = "changed evidence"
        self.assertNotEqual(
            _normalize_payload(baseline, {}),
            _normalize_payload(candidate, {}),
        )

    def test_record_contract_compares_retention_semantics_not_calendar_time(self):
        def row(expires_at: str) -> dict[str, Any]:
            return {
                "artifact_type": "private_normalized_source_payload_v0",
                "document_id": "document-1",
                "source_file_ref_json": None,
                "visibility": "private",
                "storage_backend": "sqlite_external_payload",
                "retention_policy_json": json.dumps(
                    {
                        "mode": "customer_approved_test",
                        "ttl_seconds": 1209600,
                        "expires_at": expires_at,
                        "source_delete_cascades": True,
                        "chat_delete_cascades": True,
                        "keep_redacted_tombstone": True,
                        "requires_manual_purge": False,
                        "explicit": True,
                    }
                ),
                "expires_at": expires_at,
                "purge_status": "active",
                "lifecycle_status": "active",
                "access_policy_json": json.dumps({"allow_private": True}),
                "validation_status": "passed",
                "payload_kind": "external_json",
                "safe_metadata_json": json.dumps({"created_at": expires_at}),
                "warning_codes_json": "[]",
            }

        self.assertEqual(
            _record_contract(row("2026-07-21T00:00:00+00:00"), {}),
            _record_contract(row("2026-07-22T00:00:00+00:00"), {}),
        )
        invalid = row("2026-07-22T00:00:00+00:00")
        invalid["expires_at"] = "2026-07-23T00:00:00+00:00"
        self.assertNotEqual(
            _record_contract(row("2026-07-21T00:00:00+00:00"), {}),
            _record_contract(invalid, {}),
        )

    def test_sealed_validator_uses_compact_receipts_without_payload_rereads(self):
        with tempfile.TemporaryDirectory() as temp:
            result, graph, store, *_ = self._bounded_result(Path(temp))
            compact_entries = [
                item
                for collection in graph.collections.values()
                for item in collection.iter_compact()
            ]
            self.assertTrue(compact_entries)
            serialized = json.dumps(compact_entries, sort_keys=True)
            for forbidden in (
                '"content"',
                '"raw_rows"',
                '"raw_text"',
                '"rows"',
                '"text"',
            ):
                self.assertNotIn(forbidden, serialized)

            def unexpected_read(_record):
                raise AssertionError("sealed validator reread a persisted payload")

            store.read_payload = unexpected_read
            validation = validate_artifacts(result.package)
            self.assertEqual(validation["status"], "passed")
            self.assertEqual(validation["errors"], [])


if __name__ == "__main__":
    unittest.main()
