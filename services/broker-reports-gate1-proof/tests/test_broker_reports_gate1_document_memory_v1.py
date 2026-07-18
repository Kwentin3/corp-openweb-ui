from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    SUPPORTED_PROFILE_ID,
    build_retention_policy,
    persist_gate1_result,
    supported_pilot_profile_v1,
    validate_document_memory_manifest,
)
from tests.test_broker_reports_pdf_layout_slice2 import _ruled_table_pdf


def _mixed_inputs(*, include_xlsx: bool = True) -> list[FileInput]:
    inputs = [
        FileInput.from_bytes(
            private_ref="document-memory-csv",
            filename="representative.csv",
            content=b"Date,Amount\n2026-01-01,10\n",
            mime_type="text/csv",
        ),
        FileInput.from_bytes(
            private_ref="document-memory-html",
            filename="representative.html",
            content=(
                b"<p>Statement</p><table><tr><th>Date</th><th>Amount</th></tr>"
                b"<tr><td>2026-01-01</td><td>10</td></tr></table>"
            ),
            mime_type="text/html",
        ),
        FileInput.from_bytes(
            private_ref="document-memory-pdf",
            filename="representative.pdf",
            content=_ruled_table_pdf(),
            mime_type="application/pdf",
        ),
    ]
    if include_xlsx:
        from tests.test_broker_reports_gate1_backend_contract import (
            BrokerReportsGate1BackendContractTest,
        )

        inputs.append(
            FileInput.from_bytes(
                private_ref="document-memory-xlsx-outside-profile",
                filename="methodology.xlsx",
                content=BrokerReportsGate1BackendContractTest()._synthetic_xlsx_bytes(),
                mime_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            )
        )
    return inputs


class BrokerReportsGate1DocumentMemoryV1Test(unittest.TestCase):
    def test_supported_profile_is_explicit_and_bounded(self):
        profile = supported_pilot_profile_v1()

        self.assertEqual(profile["profile_id"], SUPPORTED_PROFILE_ID)
        self.assertEqual(
            set(profile["formats"]), {"csv", "html_text", "pdf", "xml", "zip"}
        )
        self.assertEqual(profile["formats"]["csv"]["max_rows"], 10_000)
        self.assertEqual(profile["formats"]["pdf"]["max_pages"], 2_000)
        self.assertEqual(
            profile["formats"]["pdf"]["image_only_pages"],
            "bounded_visual_page_memory_review_required",
        )
        self.assertEqual(
            profile["formats"]["zip"]["promoted_member_formats"],
            ["pdf", "xml"],
        )
        self.assertIn("xlsx", profile["explicitly_outside_profile"])
        self.assertFalse(profile["silent_omission_allowed"])
        self.assertFalse(profile["financial_semantics_allowed"])

    def test_mixed_case_builds_one_cohesive_zero_loss_root(self):
        result = Gate1Normalizer().normalize(
            _mixed_inputs(),
            input_context={"clarification_criticality_refinement_enabled": True},
        )
        package = result.package
        assessment = package["gate1_supported_profile_assessment"]
        manifest = package["document_memory_manifest"]
        by_format = {
            item["container_format"]: item for item in assessment["entries"]
        }

        self.assertEqual(package["validation_result"]["status"], "passed")
        for container in ("csv", "html_text", "pdf"):
            self.assertEqual(by_format[container]["profile_acceptance"], "accepted")
            self.assertEqual(by_format[container]["accounting_status"], "passed")
            self.assertEqual(by_format[container]["zero_silent_loss"], "passed")
        self.assertEqual(by_format["xlsx"]["terminal_status"], "unsupported")
        self.assertEqual(by_format["xlsx"]["gate2_memory_status"], "blocked")
        self.assertEqual(manifest["summary"]["accepted_documents_total"], 3)
        self.assertEqual(
            manifest["summary"]["zero_silent_loss_status"],
            "passed_for_all_profile_accepted_documents",
        )
        self.assertEqual(
            manifest["summary"]["duplicate_normalized_artifact_refs_total"], 0
        )
        for document in manifest["documents"]:
            self.assertEqual(len(document["logical_document_refs"]), 1)
            self.assertTrue(document["source_scope"]["scope_ref"])
            self.assertEqual(document["normalization_run_id"], manifest["normalization_run_id"])
            self.assertFalse(document["private_values_copied_to_manifest"])
        self.assertEqual(
            validate_document_memory_manifest(manifest)["validator_status"],
            "passed",
        )

    def test_html_executable_content_is_explicitly_partial(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="document-memory-html-script",
                    filename="dynamic.html",
                    content=(
                        b"<p>Visible</p><script>window.rows=[['hidden',10]]</script>"
                    ),
                    mime_type="text/html",
                )
            ]
        )
        assessment = result.package["gate1_supported_profile_assessment"]["entries"][0]

        self.assertEqual(result.package["validation_result"]["status"], "passed")
        self.assertEqual(assessment["terminal_status"], "partial")
        self.assertEqual(assessment["gate2_memory_status"], "blocked")
        self.assertIn(
            "html_script_content_outside_supported_profile",
            assessment["reason_codes"],
        )
        self.assertEqual(result.package["private_normalized_source_units"], [])

    def test_manifest_tamper_is_rejected(self):
        result = Gate1Normalizer().normalize(_mixed_inputs(include_xlsx=False))
        tampered = copy.deepcopy(result.package["document_memory_manifest"])
        tampered["documents"][0]["logical_document_refs"] = []

        validation = validate_document_memory_manifest(tampered)

        self.assertEqual(validation["validator_status"], "failed")
        self.assertIn(
            "document_memory_integrity_mismatch",
            {item["code"] for item in validation["errors"]},
        )
        self.assertIn(
            "document_memory_logical_document_identity_invalid",
            {item["code"] for item in validation["errors"]},
        )

    def test_persist_resolve_gate2_wrong_context_and_purge(self):
        result = Gate1Normalizer().normalize(
            _mixed_inputs(include_xlsx=False),
            input_context={"clarification_criticality_refinement_enabled": True},
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=Path(temp_dir) / "artifacts.sqlite3",
                    payload_root=Path(temp_dir) / "payloads",
                )
            ).create()
            context = ArtifactAccessContext(
                user_id="document-memory-user",
                case_id="document-memory-case",
                chat_id="document-memory-chat",
                workspace_model_id="broker_reports_gate1_pipe",
                normalization_run_id=result.package["normalization_run"]["run_id"],
                allow_private=True,
            )
            persisted = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            manifest_ref = persisted.artifact_refs_by_type[
                "broker_reports_gate1_document_memory_manifest_v1"
            ][0]
            resolver = ArtifactResolver(store)
            resolved = resolver.resolve(manifest_ref, context)
            records_before = [
                item.artifact_id for item in store.list_by_run(context.normalization_run_id)
            ]
            readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
                domain_context_packet_ref=persisted.artifact_refs_by_type[
                    "domain_context_packet_v0"
                ][0],
                context=context,
            )
            records_after = [
                item.artifact_id for item in store.list_by_run(context.normalization_run_id)
            ]

            self.assertEqual(
                resolved["payload"]["schema_version"],
                "broker_reports_gate1_document_memory_manifest_v1",
            )
            self.assertEqual(readiness.validation["validator_status"], "passed")
            self.assertEqual(
                readiness.validation["document_memory_audit"]["validator_status"],
                "passed",
            )
            self.assertFalse(
                readiness.validation["document_memory_audit"][
                    "format_specific_parser_required"
                ]
            )
            self.assertEqual(records_before, records_after)
            wrong_context = ArtifactAccessContext(
                user_id="foreign-user",
                case_id=context.case_id,
                chat_id=context.chat_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                allow_private=True,
            )
            with self.assertRaises(ArtifactStoreError):
                resolver.resolve(manifest_ref, wrong_context)

            purged = store.purge_case(case_id=str(context.case_id))
            self.assertTrue(purged)
            with self.assertRaises(ArtifactStoreError):
                resolver.resolve(manifest_ref, context)


if __name__ == "__main__":
    unittest.main()
