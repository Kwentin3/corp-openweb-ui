from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1 import FileInput, Gate1Normalizer, NORMALIZER_VERSION, render_chat_content
from broker_reports_gate1.safe_report import render_safe_report
from broker_reports_gate1.validators import validate_safe_report


FIXTURES = REPO / "docs" / "stage2" / "testdata" / "broker_reports_gate1_normalization"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def normalize(inputs: list[FileInput]):
    return Gate1Normalizer().normalize(
        inputs,
        input_context={"test_case": "backend_contract"},
        entrypoint="backend_contract_test",
        trigger_type="backend_core",
    )


class BrokerReportsGate1BackendContractTest(unittest.TestCase):
    def test_no_files_fails_closed_with_no_files_blocker(self):
        result = normalize([])

        report = result.safe_report
        self.assertEqual(report["run_status"], "failed_safe")
        self.assertEqual(report["files_total"], 0)
        self.assertEqual(report["blockers"][0]["code"], "no_files")
        self.assertEqual(report["recommended_next_step"], "attach_synthetic_files_and_retry")

    def test_txt_csv_inventory_hashes_profiles_and_taxonomy_pass_validation(self):
        txt = fixture_bytes("synthetic_broker_report.txt")
        csv_content = fixture_bytes("synthetic_operations.csv")
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="local-txt-1",
                    filename="synthetic_broker_report.txt",
                    content=txt,
                    mime_type="text/plain",
                    source_kind="local_private_test",
                ),
                FileInput.from_bytes(
                    private_ref="local-csv-1",
                    filename="synthetic_operations.csv",
                    content=csv_content,
                    mime_type="text/csv",
                    source_kind="local_private_test",
                ),
            ]
        )

        package = result.package
        report = result.safe_report
        documents = package["document_inventory"]["documents"]
        self.assertEqual(report["run_status"], "completed")
        self.assertEqual(report["normalizer_version"], NORMALIZER_VERSION)
        self.assertEqual(report["normalization_run"]["normalizer_version"], NORMALIZER_VERSION)
        self.assertEqual(report["container_counts"], {"csv": 1, "txt": 1})
        self.assertEqual(report["validation_result"]["status"], "passed")
        self.assertEqual(documents[0]["sha256"], hashlib.sha256(txt).hexdigest())
        self.assertEqual(documents[1]["sha256"], hashlib.sha256(csv_content).hexdigest())
        self.assertEqual(
            {candidate["document_class_candidate"] for candidate in package["taxonomy_candidates"]},
            {"source_broker_report", "operations_table"},
        )
        self.assertFalse(report["safety_flags"]["tax_correctness_claimed"])
        self.assertFalse(report["safety_flags"]["source_fact_extraction_performed"])
        self.assertFalse(report["safety_flags"]["declaration_generated"])
        self.assertFalse(report["safety_flags"]["xlsx_generated"])

    def test_csv_profile_detects_delimiter_shape_and_private_bounded_slice(self):
        csv_content = fixture_bytes("synthetic_operations.csv")
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="csv-shape-1",
                    filename="synthetic_operations.csv",
                    content=csv_content,
                    mime_type="text/csv",
                )
            ]
        )

        profile = result.package["technical_readability_profiles"][0]
        private_slice = result.package["private_normalized_slices"][0]
        safe_content = render_chat_content(result.safe_report)
        self.assertEqual(profile["container_format"], "csv")
        self.assertEqual(profile["delimiter"], ",")
        self.assertEqual(profile["rows_count"], 3)
        self.assertEqual(profile["columns_count"], 4)
        self.assertTrue(profile["header_candidate"])
        self.assertEqual(private_slice["slice_type"], "table_rows")
        self.assertLessEqual(private_slice["rows_in_slice"], 5)
        self.assertEqual(private_slice["document_id"], profile["document_id"])
        self.assertIn("source_location", private_slice)
        self.assertNotIn("SYNTH-A,1,SYNTH-FCY", safe_content)
        self.assertNotIn("synthetic_operations.csv", safe_content)

    def test_txt_profile_counts_lines_sections_and_keeps_text_slice_private(self):
        txt = fixture_bytes("synthetic_broker_report.txt")
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="txt-profile-1",
                    filename="synthetic_broker_report.txt",
                    content=txt,
                    mime_type="text/plain",
                )
            ]
        )

        profile = result.package["technical_readability_profiles"][0]
        private_slice = result.package["private_normalized_slices"][0]
        safe_content = render_chat_content(result.safe_report)
        self.assertEqual(profile["container_format"], "txt")
        self.assertGreaterEqual(profile["line_count"], 5)
        self.assertGreaterEqual(profile["section_count"], 1)
        self.assertEqual(private_slice["slice_type"], "text_excerpt")
        self.assertEqual(private_slice["document_id"], profile["document_id"])
        self.assertIn("source_location", private_slice)
        self.assertLessEqual(private_slice["characters_in_slice"], 2000)
        self.assertNotIn("SYNTH-ACCOUNT-001", safe_content)
        self.assertNotIn("Synthetic Broker LLC", safe_content)

    def test_duplicate_content_sets_duplicate_group_and_warning_blocker(self):
        csv_content = fixture_bytes("synthetic_operations.csv")
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="dup-1",
                    filename="synthetic_operations.csv",
                    content=csv_content,
                    mime_type="text/csv",
                ),
                FileInput.from_bytes(
                    private_ref="dup-2",
                    filename="synthetic_operations_duplicate.csv",
                    content=csv_content,
                    mime_type="text/csv",
                ),
            ]
        )

        docs = result.package["document_inventory"]["documents"]
        self.assertEqual(result.safe_report["run_status"], "completed_with_blockers")
        self.assertEqual(result.safe_report["summary_counts"]["duplicate_count"], 1)
        self.assertEqual(result.safe_report["summary_counts"]["duplicate_hashes"], 1)
        self.assertEqual(docs[1]["duplicate_of_document_id"], docs[0]["document_id"])
        self.assertIn("duplicate_review", {item["code"] for item in result.package["normalization_blockers"]})

    def test_unknown_binary_gets_unsupported_and_unknown_role_blockers(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="unknown-bin-1",
                    filename="synthetic_unknown.bin",
                    content=fixture_bytes("synthetic_unknown.bin"),
                    mime_type="application/octet-stream",
                )
            ]
        )

        report = result.safe_report
        codes = {item["code"] for item in report["blockers"]}
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["container_counts"], {"unknown": 1})
        self.assertIn("unsupported_format", codes)
        self.assertNotIn("unknown_role", codes)
        self.assertEqual(
            report["taxonomy_candidates"][0]["document_class_candidate"],
            "unsupported",
        )

    def test_weak_supported_text_taxonomy_defaults_to_unknown_or_needs_review(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="weak-text-1",
                    filename="synthetic_note.txt",
                    content=b"Just a synthetic note without document role signals.",
                    mime_type="text/plain",
                )
            ]
        )

        report = result.safe_report
        self.assertEqual(
            report["taxonomy_candidates"][0]["document_class_candidate"],
            "unknown_or_needs_review",
        )
        self.assertIn("unknown_role", {item["code"] for item in report["blockers"]})

    def test_zip_inventory_counts_members_extensions_nested_and_requires_review(self):
        zip_bytes = self._synthetic_zip_bytes()
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="zip-1",
                    filename="synthetic_archive.zip",
                    content=zip_bytes,
                    mime_type="application/zip",
                )
            ]
        )

        profile = result.package["technical_readability_profiles"][0]
        report = result.safe_report
        safe_content = render_chat_content(report)
        self.assertEqual(report["container_counts"], {"zip": 1})
        self.assertEqual(profile["member_count"], 4)
        self.assertEqual(profile["extension_counts"]["pdf"], 1)
        self.assertEqual(profile["extension_counts"]["xml"], 1)
        self.assertEqual(profile["extension_counts"]["sig"], 1)
        self.assertEqual(profile["extension_counts"]["zip"], 1)
        self.assertEqual(profile["nested_archive_count"], 1)
        self.assertIn("zip_requires_review", {item["code"] for item in report["blockers"]})
        self.assertNotIn("broker_report.pdf", safe_content)
        self.assertNotIn("payload.xml", safe_content)

    def test_html_text_profile_detects_clean_text_and_table_candidate(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="html-1",
                    filename="synthetic_broker_report.html",
                    content=fixture_bytes("synthetic_broker_report.html"),
                    mime_type="text/html",
                )
            ]
        )

        profile = result.package["technical_readability_profiles"][0]
        private_slice = result.package["private_normalized_slices"][0]
        safe_content = render_chat_content(result.safe_report)
        self.assertEqual(profile["container_format"], "html_text")
        self.assertEqual(profile["text_subtype"], "html_text")
        self.assertTrue(profile["clean_text_available"])
        self.assertTrue(profile["table_candidate"])
        self.assertEqual(private_slice["profile_id"], profile["profile_id"])
        self.assertNotIn("SYNTH-ACCOUNT-HTML", safe_content)
        self.assertNotIn("synthetic_broker_report.html", safe_content)

    def test_xlsx_profile_detects_sheets_formulas_hidden_sheet_and_private_slice(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="xlsx-1",
                    filename="synthetic_workbook.xlsx",
                    content=self._synthetic_xlsx_bytes(),
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            ]
        )

        profile = result.package["technical_readability_profiles"][0]
        private_slices = result.package["private_normalized_slices"]
        safe_content = render_chat_content(result.safe_report)
        self.assertEqual(profile["container_format"], "xlsx")
        self.assertTrue(profile["workbook_readable"])
        self.assertEqual(profile["sheets_count"], 3)
        self.assertEqual(profile["hidden_sheets_count"], 1)
        self.assertTrue(profile["formulas_present"])
        self.assertGreaterEqual(len(profile["table_like_ranges"]), 1)
        self.assertGreaterEqual(len(private_slices), 1)
        self.assertEqual(private_slices[0]["profile_id"], profile["profile_id"])
        self.assertNotIn("OperationsRaw", safe_content)
        self.assertNotIn("HiddenPrivateSheet", safe_content)
        self.assertNotIn("SYNTH-X", safe_content)

    def test_text_layer_pdf_profile_detects_page_count_text_layer_and_private_text_slice(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="pdf-text-1",
                    filename="synthetic_text_layer.pdf",
                    content=self._synthetic_text_pdf_bytes(),
                    mime_type="application/pdf",
                )
            ]
        )

        profile = result.package["technical_readability_profiles"][0]
        private_slice = result.package["private_normalized_slices"][0]
        safe_content = render_chat_content(result.safe_report)
        self.assertEqual(profile["container_format"], "pdf")
        self.assertEqual(profile["pages_count"], 1)
        self.assertEqual(profile["text_layer"], "yes")
        self.assertTrue(profile["has_text_layer"])
        self.assertEqual(profile["raster_or_scan_likelihood"], "low")
        self.assertEqual(private_slice["profile_id"], profile["profile_id"])
        self.assertNotIn("Synthetic Broker PDF Report", safe_content)
        self.assertNotIn("synthetic_text_layer.pdf", safe_content)

    def test_raster_like_pdf_creates_ocr_review_blocker_without_ocr(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="pdf-raster-1",
                    filename="synthetic_raster.pdf",
                    content=self._synthetic_raster_pdf_bytes(),
                    mime_type="application/pdf",
                )
            ]
        )

        profile = result.package["technical_readability_profiles"][0]
        codes = {item["code"] for item in result.safe_report["blockers"]}
        self.assertEqual(profile["text_layer"], "no")
        self.assertEqual(profile["raster_or_scan_likelihood"], "high")
        self.assertFalse(profile["ocr_performed"])
        self.assertIn("raster_requires_ocr_or_review", codes)
        self.assertEqual(result.safe_report["gate2_handoff_status"], "blocked")

    def test_corrupt_pdf_creates_typed_corrupt_blocker(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="pdf-corrupt-1",
                    filename="synthetic_corrupt.pdf",
                    content=b"%PDF-1.4\n1 0 obj << /Type /Page >>\n",
                    mime_type="application/pdf",
                )
            ]
        )

        self.assertIn("corrupt_file", {item["code"] for item in result.safe_report["blockers"]})

    def test_encrypted_pdf_creates_typed_encrypted_blocker(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="pdf-encrypted-1",
                    filename="synthetic_encrypted.pdf",
                    content=b"%PDF-1.4\n1 0 obj << /Encrypt 2 0 R >> endobj\n%%EOF",
                    mime_type="application/pdf",
                )
            ]
        )

        self.assertIn("encrypted_file", {item["code"] for item in result.safe_report["blockers"]})

    def test_corrupt_zip_creates_typed_corrupt_blocker(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="zip-corrupt-1",
                    filename="synthetic_corrupt.zip",
                    content=b"PK\x03\x04not-a-complete-zip",
                    mime_type="application/zip",
                )
            ]
        )

        self.assertIn("corrupt_file", {item["code"] for item in result.safe_report["blockers"]})

    def test_docx_lightweight_profile_detects_paragraphs_headings_tables(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="docx-1",
                    filename="synthetic_report.docx",
                    content=self._synthetic_docx_bytes(),
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            ]
        )

        profile = result.package["technical_readability_profiles"][0]
        safe_content = render_chat_content(result.safe_report)
        self.assertEqual(profile["container_format"], "docx")
        self.assertTrue(profile["document_readable"])
        self.assertEqual(profile["paragraphs_count"], 3)
        self.assertEqual(profile["headings_count"], 1)
        self.assertEqual(profile["tables_count"], 1)
        self.assertEqual(result.safe_report["taxonomy_candidates"][0]["document_class_candidate"], "source_broker_report")
        self.assertNotIn("Synthetic Broker DOCX Report", safe_content)
        self.assertNotIn("synthetic_report.docx", safe_content)

    def test_image_profile_keeps_metadata_only_and_blocks_for_review(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="image-1",
                    filename="synthetic_scan.png",
                    content=self._synthetic_png_bytes(width=32, height=16),
                    mime_type="image/png",
                )
            ]
        )

        profile = result.package["technical_readability_profiles"][0]
        codes = {item["code"] for item in result.safe_report["blockers"]}
        self.assertEqual(profile["container_format"], "image")
        self.assertEqual(profile["width_px"], 32)
        self.assertEqual(profile["height_px"], 16)
        self.assertFalse(profile["ocr_performed"])
        self.assertIn("raster_requires_ocr_or_review", codes)

    def test_full_synthetic_package_validation_passes_with_profiles_and_typed_blockers(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="full-csv",
                    filename="synthetic_operations.csv",
                    content=fixture_bytes("synthetic_operations.csv"),
                    mime_type="text/csv",
                ),
                FileInput.from_bytes(
                    private_ref="full-txt",
                    filename="synthetic_broker_report.txt",
                    content=fixture_bytes("synthetic_broker_report.txt"),
                    mime_type="text/plain",
                ),
                FileInput.from_bytes(
                    private_ref="full-html",
                    filename="synthetic_broker_report.html",
                    content=fixture_bytes("synthetic_broker_report.html"),
                    mime_type="text/html",
                ),
                FileInput.from_bytes(
                    private_ref="full-xlsx",
                    filename="synthetic_workbook.xlsx",
                    content=self._synthetic_xlsx_bytes(),
                    mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                FileInput.from_bytes(
                    private_ref="full-pdf",
                    filename="synthetic_text_layer.pdf",
                    content=self._synthetic_text_pdf_bytes(),
                    mime_type="application/pdf",
                ),
                FileInput.from_bytes(
                    private_ref="full-zip",
                    filename="synthetic_archive.zip",
                    content=self._synthetic_zip_bytes(),
                    mime_type="application/zip",
                ),
                FileInput.from_bytes(
                    private_ref="full-docx",
                    filename="synthetic_report.docx",
                    content=self._synthetic_docx_bytes(),
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
                FileInput.from_bytes(
                    private_ref="full-image",
                    filename="synthetic_scan.png",
                    content=self._synthetic_png_bytes(width=4, height=4),
                    mime_type="image/png",
                ),
                FileInput.from_bytes(
                    private_ref="full-unknown",
                    filename="synthetic_unknown.bin",
                    content=fixture_bytes("synthetic_unknown.bin"),
                    mime_type="application/octet-stream",
                ),
            ]
        )

        report = result.safe_report
        self.assertEqual(report["validation_result"]["status"], "passed")
        self.assertEqual(report["container_counts"]["csv"], 1)
        self.assertEqual(report["container_counts"]["xlsx"], 1)
        self.assertEqual(report["container_counts"]["pdf"], 1)
        self.assertEqual(report["container_counts"]["zip"], 1)
        self.assertEqual(report["container_counts"]["docx"], 1)
        self.assertEqual(report["container_counts"]["image"], 1)
        self.assertEqual(report["gate2_handoff_status"], "blocked")
        self.assertFalse(report["safety_flags"]["source_fact_extraction_performed"])
        self.assertFalse(report["safety_flags"]["tax_correctness_claimed"])
        self.assertFalse(report["safety_flags"]["declaration_generated"])
        self.assertFalse(report["safety_flags"]["xlsx_generated"])
        self.assertFalse(report["safety_flags"]["ocr_performed"])

    def test_bytes_unavailable_is_typed_blocker_without_profile_requirement_failure(self):
        result = normalize(
            [
                FileInput(
                    private_ref="missing-bytes-1",
                    original_filename_private="synthetic_operations.csv",
                    mime_type="text/csv",
                    source_kind="local_private_test",
                    bytes_provider=None,
                )
            ]
        )

        report = result.safe_report
        self.assertEqual(report["run_status"], "completed_with_blockers")
        self.assertEqual(report["validation_result"]["status"], "passed")
        self.assertIn("bytes_unavailable", {item["code"] for item in report["blockers"]})
        self.assertEqual(report["documents"][0]["sha256"], None)
        self.assertEqual(report["documents"][0]["read_error_class"], "bytes_unavailable")

    def test_safe_report_excludes_private_slices_and_private_markers(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="privacy-csv-id",
                    filename="synthetic_operations.csv",
                    content=fixture_bytes("synthetic_operations.csv"),
                    mime_type="text/csv",
                )
            ]
        )

        safe_content = render_chat_content(result.safe_report)
        self.assertNotIn("private_normalized_slices", result.safe_report)
        self.assertIn("private_artifact_summary", result.safe_report)
        self.assertNotIn("privacy-csv-id", safe_content)
        self.assertNotIn("synthetic_operations.csv", safe_content)
        self.assertNotIn("SYNTH-B,2,SYNTH-FCY", safe_content)
        self.assertNotIn('"rows"', safe_content)
        self.assertNotIn('"text"', safe_content)

    def test_safe_report_validator_privacy_fails_closed_on_private_marker(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="private-marker-1",
                    filename="synthetic_operations.csv",
                    content=fixture_bytes("synthetic_operations.csv"),
                    mime_type="text/csv",
                )
            ]
        )
        unsafe_report = render_safe_report(result.package)
        unsafe_report["recommended_next_step"] = "private-marker-1"

        validation = validate_safe_report(
            safe_report=unsafe_report,
            private_markers=["private-marker-1"],
            run_id=result.package["normalization_run"]["run_id"],
        )

        self.assertEqual(validation["status"], "privacy_failed")
        self.assertEqual(validation["privacy_blocker"]["code"], "privacy_violation")

    def test_full_safe_report_is_json_serializable_and_has_contract_refs(self):
        result = normalize(
            [
                FileInput.from_bytes(
                    private_ref="contract-json-1",
                    filename="synthetic_broker_report.txt",
                    content=fixture_bytes("synthetic_broker_report.txt"),
                    mime_type="text/plain",
                )
            ]
        )

        serialized = json.dumps(result.safe_report, ensure_ascii=False, sort_keys=True)
        self.assertIn("normalization_run_v0", serialized)
        self.assertIn("document_inventory_v0", serialized)
        self.assertIn("technical_readability_profile_v0", serialized)
        self.assertIn("taxonomy_candidates_v0", serialized)
        self.assertIn("validation_result_v0", serialized)

    def test_local_file_fixture_paths_remain_outside_safe_report(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir) / "synthetic_operations.csv"
            temp_path.write_bytes(fixture_bytes("synthetic_operations.csv"))
            result = normalize(
                [
                    FileInput(
                        private_ref=str(temp_path),
                        original_filename_private=temp_path.name,
                        mime_type="text/csv",
                        source_kind="local_private_test",
                        declared_size_bytes=temp_path.stat().st_size,
                        bytes_provider=temp_path.read_bytes,
                        provider_label="local_private_test",
                    )
                ]
            )

        safe_content = render_chat_content(result.safe_report)
        self.assertNotIn(str(temp_path), safe_content)
        self.assertNotIn("synthetic_operations.csv", safe_content)
        self.assertEqual(result.safe_report["validation_result"]["status"], "passed")

    def _synthetic_zip_bytes(self) -> bytes:
        nested = BytesIO()
        with zipfile.ZipFile(nested, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("nested.txt", "synthetic nested content")

        payload = BytesIO()
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("broker_report.pdf", b"%PDF-1.4\n% synthetic pdf marker\n")
            archive.writestr("payload.xml", "<root>synthetic</root>")
            archive.writestr("signature.sig", "synthetic-signature")
            archive.writestr("nested_archive.zip", nested.getvalue())
        return payload.getvalue()

    def _synthetic_xlsx_bytes(self) -> bytes:
        payload = BytesIO()
        workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="OperationsRaw" sheetId="1" r:id="rId1"/>
    <sheet name="FormulaSheet" sheetId="2" r:id="rId2"/>
    <sheet name="HiddenPrivateSheet" sheetId="3" state="hidden" r:id="rId3"/>
  </sheets>
</workbook>"""
        rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="worksheet" Target="worksheets/sheet3.xml"/>
</Relationships>"""
        sheet1 = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:C3"/>
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>symbol</t></is></c><c r="B1" t="inlineStr"><is><t>quantity</t></is></c><c r="C1" t="inlineStr"><is><t>currency</t></is></c></row>
    <row r="2"><c r="A2" t="inlineStr"><is><t>SYNTH-X</t></is></c><c r="B2"><v>1</v></c><c r="C2" t="inlineStr"><is><t>SYNTH-FCY</t></is></c></row>
    <row r="3"><c r="A3" t="inlineStr"><is><t>SYNTH-Y</t></is></c><c r="B3"><v>2</v></c><c r="C3" t="inlineStr"><is><t>SYNTH-FCY</t></is></c></row>
  </sheetData>
</worksheet>"""
        sheet2 = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:B2"/>
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>base</t></is></c><c r="B1" t="inlineStr"><is><t>formula</t></is></c></row>
    <row r="2"><c r="A2"><v>10</v></c><c r="B2"><f>A2*2</f><v>20</v></c></row>
  </sheetData>
</worksheet>"""
        sheet3 = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:A1"/>
  <sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>hidden private marker</t></is></c></row></sheetData>
</worksheet>"""
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", workbook)
            archive.writestr("xl/_rels/workbook.xml.rels", rels)
            archive.writestr("xl/worksheets/sheet1.xml", sheet1)
            archive.writestr("xl/worksheets/sheet2.xml", sheet2)
            archive.writestr("xl/worksheets/sheet3.xml", sheet3)
        return payload.getvalue()

    def _synthetic_text_pdf_bytes(self) -> bytes:
        return (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Count 1 /Kids [3 0 R] >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
            b"4 0 obj << /Length 80 >> stream\n"
            b"BT /F1 12 Tf 72 720 Td (Synthetic Broker PDF Report) Tj ET\n"
            b"endstream endobj\n"
            b"%%EOF"
        )

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

    def _synthetic_docx_bytes(self) -> bytes:
        document = """<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Synthetic Broker DOCX Report</w:t></w:r></w:p>
    <w:p><w:r><w:t>Synthetic account DOCX-001 for Gate 1 only.</w:t></w:r></w:p>
    <w:tbl><w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
  </w:body>
</w:document>"""
        payload = BytesIO()
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", document)
        return payload.getvalue()

    def _synthetic_png_bytes(self, *, width: int, height: int) -> bytes:
        return (
            b"\x89PNG\r\n\x1a\n"
            + (13).to_bytes(4, "big")
            + b"IHDR"
            + width.to_bytes(4, "big")
            + height.to_bytes(4, "big")
            + b"\x08\x02\x00\x00\x00"
            + b"\x00\x00\x00\x00"
        )


if __name__ == "__main__":
    unittest.main()
