from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from jsonschema import Draft202012Validator

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    FileInput,
    FullSourceArtifactConfig,
    FullSourceArtifactFactory,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = (
    REPO_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_CANONICAL_ARTIFACT.v1.schema.json"
)


class BrokerReportsCanonicalArtifactV1Test(unittest.TestCase):
    def test_flags_off_do_not_add_canonical_projection_or_artifacts(self):
        result = self._normalize_csv({})
        self.assertNotIn(
            "canonical_projection",
            result.package["private_normalized_source_payloads"][0],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store, context = self._store_context(temp_dir, result)
            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            self.assertNotIn(
                "broker_reports_canonical_artifact_v1",
                manifest.artifact_refs_by_type,
            )

    def test_shadow_write_validates_schema_and_fails_closed_across_tenants(self):
        result = self._normalize_csv(
            {
                "canonical_gate2_write_enabled": True,
                "canonical_gate2_read_enabled": False,
                "canonical_gate2_compare_enabled": True,
                "normalizer_version": "canonical-test-v1",
            }
        )
        self.assertIn(
            "canonical_projection",
            result.package["private_normalized_source_payloads"][0],
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            store, context = self._store_context(temp_dir, result)
            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            canonical_ref = manifest.artifact_refs_by_type[
                "broker_reports_canonical_artifact_v1"
            ][0]
            self.assertEqual(
                len(
                    manifest.artifact_refs_by_type[
                        "broker_reports_canonical_legacy_compare_receipt_v1"
                    ]
                ),
                1,
            )
            artifact = CanonicalReaderFactory(
                store=store, read_enabled=True
            ).create().read(canonical_ref, context)
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            errors = list(Draft202012Validator(schema).iter_errors(artifact))
            self.assertEqual(errors, [])
            self.assertEqual(
                artifact["source"]["source_format"], "csv"
            )
            self.assertEqual(artifact["nodes"][0]["node_type"], "TABLE")
            with self.assertRaises(ArtifactStoreError) as disabled:
                CanonicalReaderFactory(
                    store=store, read_enabled=False
                ).create().read(canonical_ref, context)
            self.assertEqual(disabled.exception.code, "canonical_read_disabled")
            other_tenant = ArtifactAccessContext(
                user_id="other-user",
                normalization_run_id=context.normalization_run_id,
                case_id=context.case_id,
                chat_id=context.chat_id,
                workspace_model_id=context.workspace_model_id,
                allow_private=True,
                require_source_available=True,
            )
            with self.assertRaises(ArtifactStoreError) as denied:
                CanonicalReaderFactory(
                    store=store, read_enabled=True
                ).create().read(canonical_ref, other_tenant)
            self.assertEqual(denied.exception.code, "artifact_access_denied")

    def test_three_rebuilds_have_identical_root_hashes(self):
        result = self._normalize_csv(
            {"canonical_gate2_write_enabled": True}
        )
        document = result.package["document_inventory"]["documents"][0]
        factory = CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="canonical-test-v1")
        )
        hashes = []
        for index in range(3):
            artifact = factory.create().build(
                tenant_id="tenant",
                artifact_version=1,
                document=document,
                source_artifact_ref=f"source-artifact-{index}",
                source_payloads=result.package[
                    "private_normalized_source_payloads"
                ],
                source_units=result.package["private_normalized_source_units"],
                table_projections=result.package[
                    "private_normalized_table_projections"
                ],
            )
            hashes.append(artifact["canonical_root_hash"])
        self.assertEqual(len(set(hashes)), 1)

    def test_html_semantics_share_the_full_source_parser_boundary(self):
        html = b"""
        <html><head><title>Report</title></head><body>
        <h2>Section</h2><p>Read <a href='https://example.invalid/a'>source</a>.</p>
        <ol><li>First</li><li>Second</li></ol>
        <table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>
        </body></html>
        """
        built = FullSourceArtifactFactory(
            FullSourceArtifactConfig(enable_canonical_artifact_v1_shadow=True)
        ).create().build(
            normalization_run_id="run-html",
            document_id="document-html",
            profile_id="profile-html",
            container_format="html_text",
            content_bytes=html,
            source_checksum_sha256="a" * 64,
        )
        artifact = CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="canonical-test-v1")
        ).create().build(
            tenant_id="tenant",
            artifact_version=1,
            document={
                "container_format": "html_text",
                "sha256": "a" * 64,
                "declared_mime_type": "text/html",
            },
            source_artifact_ref="source-html",
            source_payloads=built.payloads,
            source_units=built.units,
            table_projections=[],
        )
        node_types = [item["node_type"] for item in artifact["nodes"]]
        self.assertEqual(
            node_types,
            ["HEADING", "HEADING", "TEXT", "LIST", "TABLE"],
        )
        text_node = next(
            item for item in artifact["nodes"] if item["node_type"] == "TEXT"
        )
        self.assertEqual(
            text_node["content"]["links"],
            [{"text": "source", "target": "https://example.invalid/a"}],
        )

    def test_xlsx_preserves_sheet_formula_cached_value_and_visibility(self):
        built = FullSourceArtifactFactory(
            FullSourceArtifactConfig(enable_canonical_artifact_v1_shadow=True)
        ).create().build(
            normalization_run_id="run-xlsx",
            document_id="document-xlsx",
            profile_id="profile-xlsx",
            container_format="xlsx",
            content_bytes=self._xlsx_bytes(),
            source_checksum_sha256="b" * 64,
        )
        artifact = CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="canonical-test-v1")
        ).create().build(
            tenant_id="tenant",
            artifact_version=1,
            document={
                "container_format": "xlsx",
                "sha256": "b" * 64,
                "declared_mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
            source_artifact_ref="source-xlsx",
            source_payloads=built.payloads,
            source_units=built.units,
            table_projections=[],
        )
        sheets = [
            item
            for item in artifact["containers"]
            if item["container_type"] == "SHEET"
        ]
        self.assertEqual(
            [item["metadata"]["sheet_name"] for item in sheets],
            ["Visible", "Hidden"],
        )
        self.assertEqual(sheets[1]["metadata"]["sheet_visibility"], "hidden")
        formula = next(
            cell
            for node in artifact["nodes"]
            if node["node_type"] == "TABLE"
            for cell in node["content"]["cells"]
            if cell["formula"] is not None
        )
        self.assertEqual(formula["formula"], "A2*2")
        self.assertEqual(formula["raw_value"], "20")
        self.assertEqual(formula["displayed_value"], "20")
        self.assertEqual(formula["merged_range"], "A2:B2")

    def test_pdf_projection_replaces_its_source_unit_once_in_reading_order(self):
        units = [
            {
                "unit_ref": "table-unit",
                "source_location": {"page": 1, "line_start": 1},
                "text": "A B 1 2",
            },
            {
                "unit_ref": "line-unit",
                "source_location": {"page": 1, "line_start": 2},
                "text": "After table",
            },
        ]
        projection = {
            "projection_status": "ready",
            "table_projection_id": "projection-1",
            "source_unit_ref": "table-unit",
            "row_count": 2,
            "column_count": 2,
            "cells": [
                {"row_ordinal": 1, "column_ordinal": 1, "normalized_private_value_path": "v1"},
                {"row_ordinal": 1, "column_ordinal": 2, "normalized_private_value_path": "v2"},
                {"row_ordinal": 2, "column_ordinal": 1, "normalized_private_value_path": "v3"},
                {"row_ordinal": 2, "column_ordinal": 2, "normalized_private_value_path": "v4"},
            ],
            "private_values": [
                {"value_path_ref": "v1", "normalized_value": "A"},
                {"value_path_ref": "v2", "normalized_value": "B"},
                {"value_path_ref": "v3", "normalized_value": "1"},
                {"value_path_ref": "v4", "normalized_value": "2"},
            ],
        }
        artifact = CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="canonical-test-v1")
        ).create().build(
            tenant_id="tenant",
            artifact_version=1,
            document={
                "container_format": "pdf",
                "sha256": "c" * 64,
                "declared_mime_type": "application/pdf",
            },
            source_artifact_ref="source-pdf",
            source_payloads=[
                {
                    "parser_completeness_status": "complete",
                    "parser_completeness_reason_codes": [],
                    "pdf_text_layer_projection": {
                        "page_inventory": [{"page_number": 1}],
                        "line_inventory": [],
                    },
                }
            ],
            source_units=units,
            table_projections=[projection],
        )
        self.assertEqual(
            [item["node_type"] for item in artifact["nodes"]],
            ["TABLE", "TEXT"],
        )
        self.assertEqual(
            artifact["nodes"][0]["content"]["rows"],
            [["A", "B"], ["1", "2"]],
        )

    def test_csv_duplicate_headers_are_preserved_without_silent_repair(self):
        built = FullSourceArtifactFactory(
            FullSourceArtifactConfig(enable_canonical_artifact_v1_shadow=True)
        ).create().build(
            normalization_run_id="run-csv-duplicate",
            document_id="document-csv-duplicate",
            profile_id="profile-csv-duplicate",
            container_format="csv",
            content_bytes=b"Amount,Amount\n10,20\n",
            source_checksum_sha256="d" * 64,
        )
        canonical = built.payloads[0]["canonical_projection"]
        self.assertTrue(canonical["duplicate_headers"])
        self.assertEqual(canonical["rows"][0], ["Amount", "Amount"])

    @staticmethod
    def _xlsx_bytes() -> bytes:
        payload = BytesIO()
        workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <definedNames><definedName name="SyntheticRange">Visible!$A$1:$B$2</definedName></definedNames>
  <sheets><sheet name="Visible" sheetId="1" r:id="rId1"/><sheet name="Hidden" sheetId="2" state="hidden" r:id="rId2"/></sheets>
</workbook>"""
        relationships = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>"""
        sheet1 = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>base</t></is></c><c r="B1" t="inlineStr"><is><t>formula</t></is></c></row><row r="2"><c r="A2"><v>10</v></c><c r="B2"><f>A2*2</f><v>20</v></c></row></sheetData>
  <mergeCells count="1"><mergeCell ref="A2:B2"/></mergeCells>
</worksheet>"""
        sheet2 = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1" hidden="1"><c r="A1" t="inlineStr"><is><t>hidden</t></is></c></row></sheetData></worksheet>"""
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", workbook)
            archive.writestr("xl/_rels/workbook.xml.rels", relationships)
            archive.writestr("xl/worksheets/sheet1.xml", sheet1)
            archive.writestr("xl/worksheets/sheet2.xml", sheet2)
        return payload.getvalue()

    @staticmethod
    def _normalize_csv(input_context):
        return Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="canonical-synthetic-csv",
                    filename="canonical.csv",
                    content=b"Date,Amount\n2026-01-01,10.00\n",
                    mime_type="text/csv",
                )
            ],
            input_context=input_context,
        )

    @staticmethod
    def _store_context(temp_dir, result):
        root = Path(temp_dir)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        context = ArtifactAccessContext(
            user_id="canonical-user",
            normalization_run_id=result.package["normalization_run"]["run_id"],
            case_id="canonical-case",
            chat_id="canonical-chat",
            workspace_model_id="canonical-workspace",
            allow_private=True,
            require_source_available=True,
        )
        return store, context


if __name__ == "__main__":
    unittest.main()
