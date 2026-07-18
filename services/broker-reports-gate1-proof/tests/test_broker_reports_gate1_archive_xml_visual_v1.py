from __future__ import annotations

import copy
import base64
import io
import unittest
import zipfile

from broker_reports_gate1 import (
    FileInput,
    Gate1ArchiveIntakeFactory,
    Gate1Normalizer,
    validate_document_memory_manifest,
)
from tests.test_broker_reports_pdf_layout_slice2 import _ruled_table_pdf
from tests.test_broker_reports_pdf_text_layer_slice1 import _pdf_bytes


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
                ("payload.xml", b"<root><item code='a'>10</item></root>"),
                ("statement.pdf", _ruled_table_pdf()),
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
        by_format = {item["container_format"]: item for item in assessments}

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

    def test_archive_policy_fails_closed_for_traversal_and_nested_archive(self):
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
