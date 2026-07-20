from __future__ import annotations

import copy
import base64
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1ArchiveIntakeFactory,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    build_retention_policy,
    persist_gate1_result,
    validate_document_memory_manifest,
)
from broker_reports_gate1.validators import validate_artifacts
from broker_reports_gate1.archive_intake import (
    FACTORY_REQUIRED as ARCHIVE_FACTORY_REQUIRED,
    FORBIDDEN as ARCHIVE_FORBIDDEN,
)
from broker_reports_gate1.domain_ingestion import _next_stage_refs, _usage_entry
from tests.test_broker_reports_pdf_text_layer_slice1 import _pdf_bytes
from tests.test_broker_reports_gate2_fns_2ndfl_adapter import _xml as _fns_2ndfl_xml
from scripts.prove_gate1_actual_customer_corpus import (
    _full_gate2_validator_passed,
    _opaque_run_ref,
)
from scripts.prove_visual_neutral_tables_actual_corpus import PROVIDER_ZERO


def _zip_bytes(entries: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return output.getvalue()


class BrokerReportsGate1ArchiveXmlVisualV1Test(unittest.TestCase):
    def test_html_data_images_become_visual_memory_with_review_restrictions(self):
        tiny_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
            "AAMAASsJTYQAAAAASUVORK5CYII="
        )
        encoded = base64.b64encode(tiny_png).decode("ascii")
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="html-visual-memory",
                    filename="statement.html",
                    content=(
                        "<p>Statement</p><img src='data:image/png;base64,"
                        + encoded
                        + "'><table><tr><th>Date</th></tr>"
                        "<tr><td>2026-01-01</td></tr></table><p>End</p>"
                    ).encode("utf-8"),
                    mime_type="text/html",
                )
            ]
        )

        assessment = result.package["gate1_supported_profile_assessment"][
            "entries"
        ][0]
        visual_units = [
            item
            for item in result.package["private_normalized_source_units"]
            if item.get("slice_type") == "visual_media"
        ]
        content_units = [
            item
            for item in result.package["private_normalized_source_units"]
            if item.get("slice_type") != "visual_media"
        ]
        scope = result.package["document_memory_manifest"]["documents"][0][
            "source_scope"
        ]

        self.assertEqual(result.package["validation_result"]["status"], "passed")
        self.assertEqual(assessment["terminal_status"], "review_required")
        self.assertEqual(assessment["zero_silent_loss"], "passed")
        self.assertEqual(len(visual_units), 1)
        self.assertEqual(
            [item["slice_type"] for item in content_units],
            ["text_excerpt", "table_rows", "text_excerpt"],
        )
        self.assertEqual(content_units[0]["text"], "Statement")
        self.assertEqual(content_units[2]["text"], "End")
        self.assertEqual(visual_units[0]["media_type"], "image/png")
        self.assertEqual(visual_units[0]["coverage"]["unit_kind"], "visual_media")
        self.assertEqual(scope["declared"]["visual_media"], 1)
        self.assertEqual(scope["scope_readiness"]["visual_scope"], "ready")
        self.assertIn(
            "visual_units_require_visual_consumer",
            scope["scope_readiness"]["restrictions"],
        )

    def test_zip_promotes_pdf_and_xml_and_accounts_signature_sidecar(self):
        content = _zip_bytes(
            [
                ("payload.xml", _fns_2ndfl_xml()),
                (
                    "statement.pdf",
                    _pdf_bytes(
                        pages=[
                            (
                                "text",
                                ["Synthetic Broker Report", "Amount 10.00 USD"],
                            )
                        ]
                    ),
                ),
                ("signature.p7s", b"synthetic-signature"),
            ]
        )
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="archive-source",
                    filename="source.zip",
                    content=content,
                    mime_type="application/zip",
                )
            ]
        )

        manifest = result.package["archive_source_manifests"][0]
        assessments = result.package["gate1_supported_profile_assessment"][
            "entries"
        ]
        document_memory = result.package["document_memory_manifest"]
        dcp = result.package["domain_context_packet"]
        usage_by_format = {
            next(
                document["container_format"]
                for document in result.package["document_inventory"]["documents"]
                if document["document_id"] == item["document_ref"]
            ): item
            for item in result.package["document_usage_classification"]["entries"]
        }
        by_format = {item["container_format"]: item for item in assessments}
        memory_by_format = {
            item["container_format"]: item
            for item in document_memory["documents"]
        }
        container_ref = memory_by_format["zip"]["source_file_ref"]
        member_refs = {
            item["source_file_ref"]
            for item in document_memory["documents"]
            if item["container_format"] in {"pdf", "xml"}
        }

        self.assertEqual(result.package["validation_result"]["status"], "passed")
        self.assertEqual(manifest["terminal_status"], "complete")
        self.assertTrue(manifest["all_members_accounted"])
        self.assertEqual(manifest["members_total"], 3)
        self.assertEqual(manifest["promoted_members_total"], 2)
        self.assertEqual(manifest["signature_sidecars_total"], 1)
        self.assertEqual(manifest["blocked_members_total"], 0)
        self.assertEqual(by_format["zip"]["profile_acceptance"], "container_accepted")
        self.assertEqual(by_format["xml"]["terminal_status"], "review_required")
        self.assertEqual(
            by_format["xml"]["gate2_memory_status"], "ready_with_restrictions"
        )
        self.assertEqual(by_format["pdf"]["terminal_status"], "complete")
        self.assertEqual(
            usage_by_format["zip"]["readiness_by_stage"][
                "source_fact_extraction"
            ],
            "not_applicable_lineage_only",
        )
        self.assertIn("archive_lineage", usage_by_format["zip"]["usage_modes"])
        self.assertIn("audit_reference", usage_by_format["zip"]["usage_modes"])
        self.assertNotIn(
            container_ref,
            dcp["next_stage_refs"]["source_fact_ready_refs"],
        )
        self.assertEqual(
            dcp["next_stage_refs"]["archive_lineage_refs"],
            [container_ref],
        )
        self.assertTrue(
            member_refs
            <= set(dcp["next_stage_refs"]["source_fact_ready_refs"])
        )
        self.assertEqual(document_memory["summary"]["logical_documents_total"], 2)
        self.assertEqual(
            document_memory["summary"]["accepted_archive_containers_total"], 1
        )
        self.assertEqual(
            validate_document_memory_manifest(document_memory)["validator_status"],
            "passed",
        )
        safe_text = str(result.safe_report)
        self.assertNotIn("payload.xml", safe_text)
        self.assertNotIn("statement.pdf", safe_text)
        self.assertNotIn("synthetic-signature", safe_text)

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=root / "artifacts.sqlite3",
                    payload_root=root / "payloads",
                )
            ).create()
            run_id = result.package["normalization_run"]["run_id"]
            context = ArtifactAccessContext(
                user_id="archive-lineage-user",
                normalization_run_id=run_id,
                case_id="archive-lineage-case",
                chat_id="archive-lineage-chat",
                workspace_model_id="archive-lineage-test",
                allow_private=True,
                require_source_available=True,
            )
            persisted = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            records_before = [
                (
                    record.artifact_id,
                    record.payload_ref,
                    record.validation_status,
                    record.lifecycle_status,
                    record.updated_at,
                )
                for record in store.list_by_run(run_id)
            ]
            readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
                domain_context_packet_ref=persisted.artifact_refs_by_type[
                    "domain_context_packet_v0"
                ][0],
                context=context,
            )
            records_after = [
                (
                    record.artifact_id,
                    record.payload_ref,
                    record.validation_status,
                    record.lifecycle_status,
                    record.updated_at,
                )
                for record in store.list_by_run(run_id)
            ]
            packaged_documents = {
                item["source_unit"]["document_ref"]
                for item in readiness.packages
            }

            self.assertEqual(
                readiness.validation["validator_status"], "passed"
            )
            self.assertNotIn(container_ref, packaged_documents)
            self.assertTrue(member_refs <= packaged_documents)
            self.assertEqual(records_before, records_after)
            self.assertNotIn(
                "gate2_source_ready_document_memory_blocked",
                {item["code"] for item in readiness.validation["errors"]},
            )

        tampered = copy.deepcopy(result.package)
        zip_usage = next(
            item
            for item in tampered["document_usage_classification"]["entries"]
            if item["document_ref"] == container_ref
        )
        zip_usage["readiness_by_stage"]["source_fact_extraction"] = "ready"
        zip_usage["usage_modes"].append("source_extraction_candidate")
        tampered["domain_context_packet"]["next_stage_refs"][
            "source_fact_ready_refs"
        ].append(container_ref)
        tampered["domain_context_packet"]["next_stage_refs"][
            "secondary_source_extraction_refs"
        ].append(container_ref)
        tamper_validation = validate_artifacts(tampered)
        tamper_codes = {item["code"] for item in tamper_validation["errors"]}
        self.assertEqual(tamper_validation["status"], "failed")
        self.assertIn(
            "usage_archive_lineage_source_fact_status_invalid", tamper_codes
        )
        self.assertIn(
            "domain_packet_archive_lineage_declared_source_ready", tamper_codes
        )

    def test_single_member_zip_keeps_container_lineage_only_and_member_ready(self):
        member_cases = (
            ("only.xml", b"<root><item>10</item></root>", "application/zip"),
            (
                "only.pdf",
                _pdf_bytes(pages=[("text", ["Synthetic Broker Report"])]),
                "application/zip",
            ),
        )
        for member_name, member_content, mime_type in member_cases:
            with self.subTest(member_name=member_name):
                result = Gate1Normalizer().normalize(
                    [
                        FileInput.from_bytes(
                            private_ref=f"single-member-{member_name}",
                            filename="single-member.zip",
                            content=_zip_bytes([(member_name, member_content)]),
                            mime_type=mime_type,
                        )
                    ]
                )
                memory = result.package["document_memory_manifest"]
                dcp = result.package["domain_context_packet"]
                container = next(
                    item
                    for item in memory["documents"]
                    if item["container_format"] == "zip"
                )
                member = next(
                    item
                    for item in memory["documents"]
                    if item["container_format"] != "zip"
                )

                self.assertEqual(result.package["validation_result"]["status"], "passed")
                self.assertEqual(memory["summary"]["source_files_total"], 2)
                self.assertEqual(memory["summary"]["logical_documents_total"], 1)
                self.assertEqual(container["gate2_memory_status"], "lineage_only")
                self.assertEqual(container["logical_document_refs"], [])
                self.assertEqual(len(member["logical_document_refs"]), 1)
                self.assertEqual(
                    dcp["next_stage_refs"]["archive_lineage_refs"],
                    [container["source_file_ref"]],
                )
                self.assertNotIn(
                    container["source_file_ref"],
                    dcp["next_stage_refs"]["source_fact_ready_refs"],
                )
                self.assertIn(
                    member["source_file_ref"],
                    dcp["next_stage_refs"]["source_fact_ready_refs"],
                )

    def test_archive_policy_fails_closed_for_traversal_and_nested_archive(self):
        self.assertIn("Gate1ArchiveIntakeFactory.create", ARCHIVE_FACTORY_REQUIRED)
        self.assertIn("must not extract archive paths directly", ARCHIVE_FORBIDDEN)
        service = Gate1ArchiveIntakeFactory().create()
        result = service.inspect_and_expand(
            normalization_run_id="normrun_synthetic",
            parent_document_ref="brdoc_synthetic",
            content_bytes=_zip_bytes(
                [
                    ("../escape.xml", b"<root/>") ,
                    ("nested.zip", _zip_bytes([("inside.xml", b"<inside/>")])) ,
                ]
            ),
        )

        self.assertEqual(result.manifest["terminal_status"], "blocked")
        self.assertEqual(result.promoted_members, ())
        self.assertFalse(result.manifest["nested_archive_recursion_performed"])
        self.assertIn(
            "zip_member_path_traversal_forbidden",
            result.manifest["reason_codes"],
        )
        self.assertIn(
            "zip_nested_archive_forbidden",
            result.manifest["reason_codes"],
        )

    def test_image_only_pdf_becomes_visual_memory_with_explicit_restrictions(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="visual-pdf",
                    filename="scan.pdf",
                    content=_pdf_bytes(pages=[("image", [])]),
                    mime_type="application/pdf",
                )
            ]
        )

        assessment = result.package["gate1_supported_profile_assessment"][
            "entries"
        ][0]
        units = result.package["private_normalized_source_units"]
        scope = result.package["document_memory_manifest"]["documents"][0][
            "source_scope"
        ]["scope_readiness"]

        self.assertEqual(result.package["validation_result"]["status"], "passed")
        self.assertEqual(assessment["terminal_status"], "review_required")
        self.assertEqual(assessment["zero_silent_loss"], "passed")
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["slice_type"], "visual_page")
        self.assertEqual(units[0]["pdf_unit_type"], "pdf_visual_page_unit")
        self.assertFalse(units[0]["ocr_vlm_used"])
        self.assertTrue(units[0]["page_rendering_used_for_extraction"])
        self.assertEqual(units[0]["canonical_table_scope"], "unavailable")
        self.assertEqual(scope["visual_scope"], "ready")
        self.assertEqual(scope["text_scope"], "unavailable_visual_scope_only")
        self.assertIn("visual_units_require_visual_consumer", scope["restrictions"])
        usage = result.package["document_usage_classification"]["entries"][0]
        self.assertEqual(
            usage["readiness_by_stage"]["source_fact_extraction"],
            "blocked_unreadable",
        )
        self.assertFalse(
            usage["deterministic_basis"]["gate2_consumable_source_scope"]
        )
        self.assertEqual(
            result.package["domain_context_packet"]["next_stage_refs"][
                "source_fact_ready_refs"
            ],
            [],
        )

    def test_visual_only_source_candidate_is_not_advertised_without_consumer(self):
        document = {
            "document_id": "brdoc_visual_candidate",
            "bytes_status": "available",
            "readable": "yes",
            "container_format": "pdf",
            "machine_readable": "unknown",
        }
        eligibility = {
            "document_id": "brdoc_visual_candidate",
            "source_eligibility": "accepted_for_gate2",
            "included_in_reduced_subset": True,
            "reason_codes": [],
        }
        usage = _usage_entry(
            document,
            {"document_class_candidate": "tax_source_document"},
            eligibility,
            [],
            memory_entry={
                "gate2_memory_status": "ready_with_restrictions",
                "source_scope": {
                    "scope_readiness": {
                        "text_scope": "unavailable_visual_scope_only",
                        "visual_scope": "ready",
                        "canonical_table_scope": "unavailable",
                        "neutral_structure_scope": "not_applicable",
                    }
                },
            },
        )

        self.assertEqual(
            usage["readiness_by_stage"]["source_fact_extraction"],
            "blocked_no_gate2_consumer",
        )
        self.assertIn("audit_reference", usage["usage_modes"])
        refs = _next_stage_refs(
            {
                "document_source_eligibility": {"entries": [eligibility]},
                "gate2_handoff": {
                    "included_document_ids": ["brdoc_visual_candidate"]
                },
            },
            [usage],
        )
        self.assertEqual(refs["source_fact_ready_refs"], [])
        self.assertEqual(refs["audit_reference_refs"], ["brdoc_visual_candidate"])

    def test_requested_full_gate2_validation_is_a_proof_gate(self):
        self.assertTrue(
            _full_gate2_validator_passed(requested=False, evidence=None)
        )
        self.assertFalse(
            _full_gate2_validator_passed(
                requested=True,
                evidence={"status": "completed", "validator_status": "failed"},
            )
        )
        opaque = _opaque_run_ref("normrun_private_internal_identifier")
        self.assertEqual(len(opaque), 24)
        self.assertNotIn("normrun", opaque)
        self.assertEqual(
            PROVIDER_ZERO,
            {
                "calls": 0,
                "retries": 0,
                "tokens": 0,
                "cost": 0,
                "whole_document_uploads": 0,
            },
        )
        self.assertTrue(
            _full_gate2_validator_passed(
                requested=True,
                evidence={"status": "completed", "validator_status": "passed"},
            )
        )

    def test_scope_readiness_tamper_is_rejected(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="scope-pdf",
                    filename="scan.pdf",
                    content=_pdf_bytes(pages=[("image", [])]),
                    mime_type="application/pdf",
                )
            ]
        )
        manifest = copy.deepcopy(result.package["document_memory_manifest"])
        manifest["documents"][0]["source_scope"]["scope_readiness"][
            "canonical_table_scope"
        ] = "ready"

        validation = validate_document_memory_manifest(manifest)

        self.assertEqual(validation["validator_status"], "failed")
        self.assertIn(
            "document_memory_integrity_mismatch",
            {item["code"] for item in validation["errors"]},
        )


if __name__ == "__main__":
    unittest.main()
