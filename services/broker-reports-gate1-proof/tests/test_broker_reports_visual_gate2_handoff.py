from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    Gate1VisualNeutralTableFactory,
    Gate1VisualRecoveryHandoffFactory,
    Gate2InputReadinessFactory,
    Gate2VisualTablePackageFactory,
    build_retention_policy,
    persist_gate1_result,
    validate_gate2_visual_table_package,
)
from broker_reports_gate1.gate2_visual_table_packages import (
    FACTORY_REQUIRED as GATE2_VISUAL_FACTORY_REQUIRED,
    FORBIDDEN as GATE2_VISUAL_FORBIDDEN,
)
from broker_reports_gate1.visual_recovery_handoff import (
    FACTORY_REQUIRED as HANDOFF_FACTORY_REQUIRED,
    FORBIDDEN as HANDOFF_FORBIDDEN,
    VisualRecoveryHandoffError,
)
from tests.test_broker_reports_pdf_text_layer_slice1 import _pdf_bytes
from tests.test_broker_reports_visual_neutral_tables import (
    _observation,
    _semantic_mutation,
)


class BrokerReportsVisualGate2HandoffTest(unittest.TestCase):
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
        self.result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="visual-gate2-source",
                    filename="broker_statement.pdf",
                    content=_pdf_bytes(
                        pages=[
                            (
                                "text",
                                [
                                    "Broker Statement",
                                    "Transactions Date Amount Currency",
                                    "2026-01-01 10.00 USD",
                                ],
                            ),
                            ("image", []),
                        ]
                    ),
                    mime_type="application/pdf",
                )
            ]
        )
        run_id = self.result.package["normalization_run"]["run_id"]
        self.context = ArtifactAccessContext(
            user_id="visual-handoff-user",
            normalization_run_id=run_id,
            case_id="visual-handoff-case",
            chat_id="visual-handoff-chat",
            workspace_model_id="visual-handoff-model",
            allow_private=True,
            require_source_available=True,
        )
        self.retention = build_retention_policy(mode="api_smoke")
        self.gate1_manifest = persist_gate1_result(
            store=self.store,
            result=self.result,
            context=self.context,
            retention_policy=self.retention,
        )
        resolver = ArtifactResolver(self.store)
        visual_source = None
        for artifact_ref in self.gate1_manifest.private_source_unit_refs:
            payload = resolver.resolve(artifact_ref, self.context)["payload"]
            if payload.get("pdf_unit_type") == "pdf_visual_page_unit":
                visual_source = copy.deepcopy(payload)
                break
        if visual_source is None:
            raise AssertionError("synthetic visual source unit missing")
        visual_source["access_scope_ref"] = "accessscope_visual_handoff_test"
        self.visual_source = visual_source
        self.visual_result = Gate1VisualNeutralTableFactory().create().recover(
            source_unit=visual_source,
            observation=_observation(visual_source),
        )

    def test_factory_persists_immutable_result_and_gate2_consumes_canonical_table(self):
        handoff = Gate1VisualRecoveryHandoffFactory(store=self.store).create().persist(
            results=[self.visual_result],
            context=self.context,
            retention_policy=self.retention,
        )
        records_before = [
            record.artifact_id
            for record in self.store.list_by_run(self.context.normalization_run_id)
        ]

        readiness = Gate2InputReadinessFactory(store=self.store).create().audit_and_build(
            domain_context_packet_ref=self.gate1_manifest.artifact_refs_by_type[
                "domain_context_packet_v0"
            ][0],
            context=self.context,
            visual_neutral_table_refs=handoff.accepted_result_refs,
        )
        records_after = [
            record.artifact_id
            for record in self.store.list_by_run(self.context.normalization_run_id)
        ]
        visual_packages = [
            package
            for package in readiness.packages
            if package["source_unit"].get("source_input_mode")
            == "visual_neutral_table"
        ]

        self.assertIn(
            "Gate1VisualRecoveryHandoffFactory.create", HANDOFF_FACTORY_REQUIRED
        )
        self.assertIn("must not inject visual tables", HANDOFF_FORBIDDEN)
        self.assertEqual(
            readiness.validation["validator_status"],
            "passed",
            readiness.validation["error_code_counts"],
        )
        self.assertTrue(visual_packages)
        self.assertEqual(records_before, records_after)
        self.assertTrue(readiness.validation["artifactstore_unchanged"])
        self.assertEqual(
            readiness.validation["visual_recovery_audit"][
                "accepted_canonical_results_total"
            ],
            1,
        )
        self.assertTrue(
            all(
                package["source_unit"]["unit_kind"] == "table_row_window"
                and package["document_context"]["selected_source_scope"]
                == "visual_neutral_table"
                and package["privacy_policy"]["local_ocr_used"] is True
                and package["privacy_policy"]["external_provider_used"] is False
                for package in visual_packages
            )
        )

    def test_package_factory_replays_and_tampering_fails_closed(self):
        builder = Gate2VisualTablePackageFactory().create()
        first = builder.build(
            visual_result=self.visual_result,
            visual_result_artifact_ref="art_visual_synthetic",
            normalization_run_id=self.context.normalization_run_id,
            case_id=self.context.case_id,
        )
        second = builder.build(
            visual_result=self.visual_result,
            visual_result_artifact_ref="art_visual_synthetic",
            normalization_run_id=self.context.normalization_run_id,
            case_id=self.context.case_id,
        )
        self.assertIn(
            "Gate2VisualTablePackageFactory.create",
            GATE2_VISUAL_FACTORY_REQUIRED,
        )
        self.assertIn("must not rebuild a table", GATE2_VISUAL_FORBIDDEN)
        self.assertEqual(first, second)
        package = copy.deepcopy(first[0])
        package["source_unit"]["private_values"][0]["normalized_value"] = "tampered"
        table = self.visual_result["canonical_tables"][0]
        with self.assertRaisesRegex(
            ValueError, "gate2_visual_cell_value_reproduction_failed"
        ):
            validate_gate2_visual_table_package(
                package=package,
                visual_result=self.visual_result,
                table=table,
            )

    def test_visual_canonical_input_supersedes_pre_recovery_unreadable_status(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="visual-only-unreadable-before-recovery",
                    filename="visual_statement.pdf",
                    content=_pdf_bytes(
                        pages=[
                            (
                                "text",
                                [
                                    "Broker Statement",
                                    "Transactions Date Amount Currency",
                                    "2026-01-01 10.00 USD",
                                ],
                            ),
                            ("image", []),
                        ]
                    ),
                    mime_type="application/pdf",
                )
            ]
        )
        usage = result.package["document_usage_classification"]["entries"][0]
        document_ref = usage["document_ref"]
        usage["readiness_by_stage"]["source_fact_extraction"] = (
            "blocked_unreadable"
        )
        usage["usage_modes"] = [
            mode
            for mode in usage["usage_modes"]
            if mode != "source_extraction_candidate"
        ]
        next_stage_refs = result.package["domain_context_packet"][
            "next_stage_refs"
        ]
        for key in (
            "source_fact_ready_refs",
            "primary_source_extraction_refs",
            "secondary_source_extraction_refs",
            "duplicate_or_non_primary_refs",
        ):
            next_stage_refs[key] = [
                ref for ref in next_stage_refs.get(key, []) if ref != document_ref
            ]
        self.assertEqual(
            usage["readiness_by_stage"]["source_fact_extraction"],
            "blocked_unreadable",
        )
        context = ArtifactAccessContext(
            user_id="visual-only-user",
            normalization_run_id=result.package["normalization_run"]["run_id"],
            case_id="visual-only-case",
            chat_id="visual-only-chat",
            workspace_model_id="visual-only-model",
            allow_private=True,
            require_source_available=True,
        )
        gate1_manifest = persist_gate1_result(
            store=self.store,
            result=result,
            context=context,
            retention_policy=self.retention,
        )
        resolver = ArtifactResolver(self.store)
        source_unit = next(
            copy.deepcopy(resolver.resolve(ref, context)["payload"])
            for ref in gate1_manifest.private_source_unit_refs
            if resolver.resolve(ref, context)["payload"].get("pdf_unit_type")
            == "pdf_visual_page_unit"
        )
        source_unit["access_scope_ref"] = "accessscope_visual_only_test"
        visual_result = Gate1VisualNeutralTableFactory().create().recover(
            source_unit=source_unit,
            observation=_observation(source_unit),
        )
        handoff = Gate1VisualRecoveryHandoffFactory(store=self.store).create().persist(
            results=[visual_result],
            context=context,
            retention_policy=self.retention,
        )

        readiness = Gate2InputReadinessFactory(store=self.store).create().audit_and_build(
            domain_context_packet_ref=gate1_manifest.artifact_refs_by_type[
                "domain_context_packet_v0"
            ][0],
            context=context,
            visual_neutral_table_refs=handoff.accepted_result_refs,
        )

        self.assertEqual(
            readiness.validation["validator_status"],
            "passed",
            readiness.validation["error_code_counts"],
        )
        self.assertEqual(
            [
                package["source_unit"]["source_input_mode"]
                for package in readiness.packages
            ],
            ["visual_neutral_table"],
        )

    def test_handoff_rejects_source_lineage_drift(self):
        drifted = copy.deepcopy(self.visual_result)
        drifted["image_sha256"] = "0" * 64
        with self.assertRaises(VisualRecoveryHandoffError) as raised:
            Gate1VisualRecoveryHandoffFactory(store=self.store).create().persist(
                results=[drifted],
                context=self.context,
                retention_policy=self.retention,
            )
        self.assertEqual(raised.exception.code, "visual_handoff_result_invalid")

    def test_confirmed_empty_scope_is_validated_accounting_not_gate2_input(self):
        def confirm_empty(item: dict) -> None:
            item["terminal_status"] = "confirmed_empty"
            item["reason_codes"] = ["visual_source_image_blank_or_uniform"]
            item["source_scope_decision"] = {
                "status": "confirmed_empty_source_scope",
                "authority": "authorized_source_owner",
                "canonical_table_count_expected": 0,
                "visual_recovery_required": False,
                "source_correction_required": False,
                "adjacent_page_inference_allowed": False,
                "model_content_invention_allowed": False,
            }
            item["image_statistics"] = {
                "nonwhite_pixel_count": 0,
                "pixel_stddev": 0.0,
            }
            item["ocr_lines"] = []
            item["ocr_consensus_status"] = "not_available"
            item["uncertainty_ledger"] = []
            item["tables"] = []
            item["outside_table_line_refs"] = []

        confirmed = Gate1VisualNeutralTableFactory().create().recover(
            source_unit=self.visual_source,
            observation=_semantic_mutation(
                _observation(self.visual_source), confirm_empty
            ),
        )
        handoff = Gate1VisualRecoveryHandoffFactory(
            store=self.store
        ).create().persist(
            results=[confirmed],
            context=self.context,
            retention_policy=self.retention,
        )
        resolver = ArtifactResolver(self.store)
        result_record = self.store.get_record_unchecked(handoff.result_refs[0])
        manifest = resolver.resolve(handoff.manifest_ref, self.context)["payload"]

        self.assertEqual(handoff.accepted_result_refs, [])
        self.assertEqual(len(handoff.confirmed_empty_result_refs), 1)
        self.assertEqual(handoff.blocked_result_refs, [])
        self.assertEqual(result_record.validation_status, "validated")
        self.assertEqual(manifest["confirmed_empty_results_total"], 1)
        self.assertTrue(manifest["all_results_terminally_accounted"])
        self.assertFalse(manifest["all_results_accepted"])


if __name__ == "__main__":
    unittest.main()
