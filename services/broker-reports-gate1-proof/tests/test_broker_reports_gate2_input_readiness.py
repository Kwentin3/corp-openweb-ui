from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
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
    Gate2InputReadinessFactory,
    NormalizedSliceProvenanceFactory,
    apply_domain_ingestion_artifacts,
    build_retention_policy,
    persist_gate1_result,
    reproduce_normalized_value,
    resolve_source_value,
    validate_dry_run_source_fact_package,
    validate_normalized_slice_provenance,
)
from broker_reports_gate1.gate2_input_readiness import (
    FACTORY_REQUIRED as GATE2_FACTORY_REQUIRED,
    FORBIDDEN as GATE2_FORBIDDEN,
    _table_row_fact_type_hint,
)
from broker_reports_gate1.normalizer import NormalizationResult
from broker_reports_gate1.safe_report import render_safe_report
from broker_reports_gate1.source_provenance import (
    FACTORY_REQUIRED as PROVENANCE_FACTORY_REQUIRED,
    FORBIDDEN as PROVENANCE_FORBIDDEN,
)
from broker_reports_gate1.validators import validate_artifacts


FIXTURES = REPO / "docs" / "stage2" / "testdata" / "broker_reports_gate1_normalization"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class BrokerReportsGate2InputReadinessTest(unittest.TestCase):
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

    def test_source_unit_provenance_factory_builds_stable_table_and_text_value_refs(self):
        first = self._normalize_value_ref_fixtures()
        second = self._normalize_value_ref_fixtures()
        first_slices = first.package["private_normalized_slices"]
        second_slices = second.package["private_normalized_slices"]
        table = next(item for item in first_slices if item["slice_type"] == "table_rows")
        text = next(item for item in first_slices if item["slice_type"] == "text_excerpt")
        second_table = next(item for item in second_slices if item["slice_type"] == "table_rows")
        second_text = next(item for item in second_slices if item["slice_type"] == "text_excerpt")

        self.assertIn("NormalizedSliceProvenanceFactory.create", PROVENANCE_FACTORY_REQUIRED)
        self.assertIn("must not mint row, cell or source-value refs directly", PROVENANCE_FORBIDDEN)
        self.assertEqual(table["schema_version"], "private_normalized_table_slice_v0")
        self.assertEqual(table["source_unit_schema_version"], "source_unit_provenance_v0")
        self.assertEqual(table["row_refs"], second_table["row_refs"])
        self.assertEqual(table["source_value_refs"], second_table["source_value_refs"])
        self.assertEqual(text["text_segment_refs"], second_text["text_segment_refs"])
        self.assertEqual(text["source_value_refs"], second_text["source_value_refs"])
        self.assertTrue(table["coverage"]["all_selected_refs_accounted"])
        self.assertEqual(table["coverage"]["selected_total"], 5)
        self.assertEqual(len(table["coverage"]["header_candidate_refs"]), 1)
        self.assertEqual(len(table["coverage"]["blank_refs"]), 1)
        self.assertEqual(len(table["coverage"]["layout_candidate_refs"]), 1)
        self.assertEqual(len(table["coverage"]["fact_candidate_refs"]), 2)
        self.assertEqual(
            [item["normalized_label"] for item in table["normalized_header_descriptors"]],
            ["date", "operation", "amount", "currency"],
        )
        amount_ref = next(
            item["source_value_ref"]
            for item in table["cell_provenance"]
            if item["row_ordinal"] == 2 and item["column_ordinal"] == 3
        )
        self.assertEqual(resolve_source_value(table, amount_ref), "100.00")
        self.assertEqual(reproduce_normalized_value(table, amount_ref, "decimal_dot"), "100.00")
        self.assertTrue(text["text_segment_refs"])
        self.assertTrue(text["section_refs"])
        self.assertTrue(text["character_span_refs"])
        self.assertTrue(text["coverage"]["all_selected_refs_accounted"])

    def test_identifier_header_is_a_safe_instrument_signal(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="private-identifier-header-signal",
                    filename="identifier_header.csv",
                    content=b"Date,Operation,Amount,Currency,Identifier\n2026-01-01,position_snapshot,1.00,USD,SYNTH-ID\n",
                    mime_type="text/csv",
                )
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
        )
        table = next(
            item
            for item in result.package["private_normalized_slices"]
            if item["slice_type"] == "table_rows"
        )
        self.assertEqual(
            [
                item["normalized_label"]
                for item in table["normalized_header_descriptors"]
            ],
            ["date", "operation", "amount", "currency", "instrument"],
        )

    def test_slice_provenance_validator_fails_closed_on_missing_or_foreign_value_refs(self):
        result = self._normalize_value_ref_fixtures()
        package = result.package
        table = next(
            item for item in package["private_normalized_slices"] if item["slice_type"] == "table_rows"
        )
        document = next(
            item
            for item in package["document_inventory"]["documents"]
            if item["document_id"] == table["document_id"]
        )
        tampered = copy.deepcopy(table)
        tampered["source_value_index"][0]["source_value_ref"] = "srcval_foreign"

        validation = validate_normalized_slice_provenance(
            private_slice=tampered,
            normalization_run_id=package["normalization_run"]["run_id"],
            document_id=table["document_id"],
            source_checksum_sha256=document["sha256"],
        )

        self.assertEqual(validation["validator_status"], "failed")
        error_codes = {item["code"] for item in validation["errors"]}
        self.assertIn("slice_provenance_field_mismatch", error_codes)
        self.assertIn("source_value_ref_not_unique_or_missing", error_codes)

    def test_factory_backed_dry_run_builds_primary_secondary_and_duplicate_packages(self):
        result = self._normalization_with_secondary_and_unit_issue()
        context, manifest = self._persist(result)
        dcp_ref = manifest.artifact_refs_by_type["domain_context_packet_v0"][0]
        records_before = [
            record.artifact_id for record in self.store.list_by_run(context.normalization_run_id)
        ]

        service = Gate2InputReadinessFactory(store=self.store).create()
        dry_run = service.audit_and_build(
            domain_context_packet_ref=dcp_ref,
            context=context,
        )

        records_after = [
            record.artifact_id for record in self.store.list_by_run(context.normalization_run_id)
        ]
        self.assertIn("Gate2InputReadinessFactory.create", GATE2_FACTORY_REQUIRED)
        self.assertIn("must not read ArtifactStore payloads", GATE2_FORBIDDEN)
        self.assertEqual(dry_run.validation["validator_status"], "passed")
        self.assertEqual(dry_run.safe_report["status"], "passed")
        self.assertEqual(
            dry_run.safe_report["source_ready_documents_total"],
            dry_run.safe_report["packageable_documents_total"],
        )
        self.assertTrue(dry_run.safe_report["no_source_ready_document_loss"])
        self.assertTrue(dry_run.safe_report["row_segment_coverage_ready"])
        self.assertGreater(dry_run.safe_report["source_value_refs_total"], 0)
        self.assertGreater(dry_run.safe_report["issue_scope_counts"].get("source_unit", 0), 0)
        self.assertEqual(
            _table_row_fact_type_hint(
                [
                    {"header_label": "operation", "value": "sell"},
                    {"header_label": "amount", "value": "100.00"},
                ]
            ),
            "trade_operation",
        )
        self.assertGreater(
            dry_run.safe_report["bucket_counts"]["primary_source_extraction_refs"],
            0,
        )
        self.assertGreater(
            dry_run.safe_report["bucket_counts"]["secondary_source_extraction_refs"],
            0,
        )
        self.assertGreater(
            dry_run.safe_report["bucket_counts"]["duplicate_or_non_primary_refs"],
            0,
        )
        self.assertEqual(records_before, records_after)
        self.assertFalse(dry_run.safe_report["safety_flags"]["source_fact_llm_call_performed"])
        self.assertFalse(dry_run.safe_report["safety_flags"]["tax_calculation_performed"])
        safe_rendered = json.dumps(dry_run.safe_report, ensure_ascii=False, sort_keys=True)
        self.assertNotIn("synthetic_gate2_value_refs.csv", safe_rendered)
        self.assertNotIn("100.00", safe_rendered)
        self.assertTrue(
            all(record.storage_backend != "openwebui_knowledge" for record in self.store.list_by_run(context.normalization_run_id))
        )

    def test_dry_run_rejects_cross_scope_context_and_foreign_package_refs(self):
        result = self._normalization_with_secondary_and_unit_issue()
        context, manifest = self._persist(result)
        dcp_ref = manifest.artifact_refs_by_type["domain_context_packet_v0"][0]
        service = Gate2InputReadinessFactory(store=self.store).create()

        with self.assertRaises(ArtifactStoreError) as wrong_user:
            service.audit_and_build(
                domain_context_packet_ref=dcp_ref,
                context=ArtifactAccessContext(
                    **{**context.__dict__, "user_id": "foreign-user"}
                ),
            )
        self.assertEqual(wrong_user.exception.code, "artifact_access_denied")

        dry_run = service.audit_and_build(
            domain_context_packet_ref=dcp_ref,
            context=context,
        )
        package = copy.deepcopy(dry_run.packages[0])
        package["allowed_source_value_refs"].append("srcval_foreign")
        slice_record = self.store.get_record_unchecked(
            package["source_unit"]["private_slice_artifact_ref"]
        )
        private_slice = self.store.read_payload(slice_record)
        if private_slice.get("source_unit_schema_version") != "source_unit_provenance_v0":
            private_slice = NormalizedSliceProvenanceFactory().create().enrich_slice(
                normalization_run_id=context.normalization_run_id,
                document_id=str(slice_record.document_id),
                source_checksum_sha256=str(slice_record.source_file_ref["file_hash_sha256"]),
                private_slice=private_slice,
            )
        validation = validate_dry_run_source_fact_package(
            package=package,
            private_slice=private_slice,
            allowed_document_issue_refs=package["allowed_issue_refs"],
        )

        self.assertEqual(validation["validator_status"], "failed")
        self.assertIn(
            "gate2_package_source_value_refs_mismatch",
            {item["code"] for item in validation["errors"]},
        )

    def test_source_fact_ready_dcp_keeps_handoff_manifest_resolver_readable_when_compatibility_is_blocked(self):
        result = self._normalization_with_secondary_and_unit_issue()
        package = copy.deepcopy(result.package)
        package["normalization_run"]["gate2_handoff_status"] = "blocked"
        package["normalization_run"]["gate2_handoff_mode"] = "gate2_blocked_requires_metadata_review"
        package["gate2_handoff"]["gate2_handoff_status"] = "blocked"
        package["gate2_handoff"]["handoff_mode"] = "gate2_blocked_requires_metadata_review"
        package["validation_result"] = validate_artifacts(package)
        self.assertEqual(package["validation_result"]["status"], "passed")
        blocked_compat_result = NormalizationResult(
            package=package,
            safe_report=render_safe_report(package),
            private_markers=result.private_markers,
        )

        context, manifest = self._persist(blocked_compat_result)
        handoff_record = self.store.get_record_unchecked(manifest.gate2_handoff_ref)
        resolved = ArtifactResolver(self.store).resolve(manifest.gate2_handoff_ref, context)

        self.assertEqual(handoff_record.validation_status, "validated")
        self.assertEqual(
            handoff_record.safe_metadata["source_fact_input_manifest_status"],
            "resolver_ready",
        )
        self.assertEqual(resolved["payload"]["handoff_status"], "blocked")
        self.assertIn(
            package["domain_context_packet"]["stage_readiness"]["source_fact_extraction"],
            {"ready", "ready_with_issue_context"},
        )

    def _normalize_value_ref_fixtures(self) -> NormalizationResult:
        return Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="gate2-value-refs-csv",
                    filename="synthetic_gate2_value_refs.csv",
                    content=fixture_bytes("synthetic_gate2_value_refs.csv"),
                    mime_type="text/csv",
                ),
                FileInput.from_bytes(
                    private_ref="gate2-value-refs-text",
                    filename="synthetic_broker_report.txt",
                    content=fixture_bytes("synthetic_broker_report.txt"),
                    mime_type="text/plain",
                ),
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
        )

    def _normalization_with_secondary_and_unit_issue(self) -> NormalizationResult:
        normalizer = Gate1Normalizer()
        result = normalizer.normalize(
            [
                FileInput.from_bytes(
                    private_ref="gate2-primary-csv",
                    filename="synthetic_operations.csv",
                    content=fixture_bytes("synthetic_operations.csv"),
                    mime_type="text/csv",
                ),
                FileInput.from_bytes(
                    private_ref="gate2-secondary-text",
                    filename="synthetic_broker_report.txt",
                    content=fixture_bytes("synthetic_broker_report.txt"),
                    mime_type="text/plain",
                ),
                FileInput.from_bytes(
                    private_ref="gate2-duplicate-csv",
                    filename="synthetic_operations_duplicate.csv",
                    content=fixture_bytes("synthetic_operations_duplicate.csv"),
                    mime_type="text/csv",
                ),
                FileInput.from_bytes(
                    private_ref="gate2-primary-html",
                    filename="synthetic_broker_report.html",
                    content=fixture_bytes("synthetic_broker_report.html"),
                    mime_type="text/html",
                ),
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
        )
        package = copy.deepcopy(result.package)
        source_ready_refs = package["domain_context_packet"]["next_stage_refs"]["source_fact_ready_refs"]
        duplicate_refs = set(
            package["domain_context_packet"]["next_stage_refs"]["duplicate_or_non_primary_refs"]
        )
        secondary_ref = next(ref for ref in source_ready_refs if ref not in duplicate_refs)
        package["gate2_handoff"]["included_document_ids"] = [
            ref
            for ref in package["gate2_handoff"]["included_document_ids"]
            if ref != secondary_ref
        ]
        package = apply_domain_ingestion_artifacts(package)
        issue_ref = package["domain_context_packet"]["document_issue_refs"].get(secondary_ref, [None])[0]
        if issue_ref:
            slice_ref = next(
                item["slice_id"]
                for item in package["private_normalized_slices"]
                if item["document_id"] == secondary_ref
            )
            issue = next(
                item for item in package["gate1_issue_ledger"]["entries"] if item["issue_id"] == issue_ref
            )
            issue["evidence_refs"] = sorted(set(issue.get("evidence_refs") or []) | {slice_ref})
        package["validation_result"] = validate_artifacts(package)
        self.assertEqual(package["validation_result"]["status"], "passed")
        return NormalizationResult(
            package=package,
            safe_report=render_safe_report(package),
            private_markers=result.private_markers,
        )

    def _persist(self, result: NormalizationResult):
        run_id = result.package["normalization_run"]["run_id"]
        context = ArtifactAccessContext(
            user_id="gate2-readiness-user",
            normalization_run_id=run_id,
            case_id="synthetic-gate2-readiness-case",
            chat_id="synthetic-gate2-readiness-chat",
            workspace_model_id="broker-reports-gate2-readiness-test",
            allow_private=True,
            require_source_available=True,
        )
        manifest = persist_gate1_result(
            store=self.store,
            result=result,
            context=context,
            retention_policy=build_retention_policy(mode="api_smoke"),
        )
        return context, manifest


if __name__ == "__main__":
    unittest.main()
