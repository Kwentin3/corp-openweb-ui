from __future__ import annotations

import hashlib
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    FullSourceArtifactConfig,
    FullSourceArtifactFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord


class BrokerReportsDoc26MultiformatRegressionTest(unittest.TestCase):
    def test_html_complete_semantics_and_three_run_storage_determinism(self):
        html = b"""
        <html><head><title>Annual report</title><style>.x{display:none}</style></head>
        <body><h1>Overview</h1><h2>Details</h2>
        <p>Read <a href='https://example.invalid/report'>visible link</a>.</p>
        <ul><li>Outer<ol><li>Inner</li></ol></li></ul>
        <table><caption>First table</caption><tr><th>A</th><th>B</th></tr>
        <tr><td>1</td><td>2</td></tr></table>
        <aside>Visible note</aside>
        <table><caption>Second table</caption><tr><td>X</td></tr></table>
        <div hidden>HIDDEN-MARKER</div><script>SCRIPT-MARKER</script>
        <!-- COMMENT-MARKER --></body></html>
        """
        artifacts = self._three_runs(
            document_id="html-complete",
            container_format="html_text",
            mime_type="text/html",
            content=html,
        )
        artifact = artifacts[0]
        node_types = [item["node_type"] for item in artifact["nodes"]]
        self.assertEqual(node_types.count("TABLE"), 2)
        self.assertIn("NOTE", node_types)
        self.assertIn("LIST", node_types)
        titles = [
            item["content"]["title"]
            for item in artifact["nodes"]
            if item["node_type"] == "TABLE"
        ]
        self.assertEqual(titles, ["First table", "Second table"])
        serialized = str(artifact)
        self.assertNotIn("HIDDEN-MARKER", serialized)
        self.assertNotIn("SCRIPT-MARKER", serialized)
        self.assertNotIn("COMMENT-MARKER", serialized)
        link = next(
            link
            for item in artifact["nodes"]
            for link in (item.get("content") or {}).get("links") or []
        )
        self.assertEqual(link["target"], "https://example.invalid/report")

    def test_csv_dialects_codecs_edge_cases_and_large_rows(self):
        fixtures = {
            "csv-utf8-comma": (
                "text/csv",
                b'Amount,Amount,Note,Empty\n10,20,"line one\nline two",\n30,40,"a ""quote""",\n',
            ),
            "csv-cp1251-semicolon-headerless": (
                "text/csv",
                "1;Привет;\n2;Мир;\n".encode("cp1251"),
            ),
            "csv-large": (
                "text/csv",
                (
                    "row,value\n"
                    + "".join(f"{index},{index}.00\n" for index in range(1_501))
                ).encode("utf-8"),
            ),
        }
        outputs = {
            name: self._three_runs(
                document_id=name,
                container_format="csv",
                mime_type=mime,
                content=content,
            )[0]
            for name, (mime, content) in fixtures.items()
        }
        utf8 = self._table(outputs["csv-utf8-comma"])["content"]
        self.assertEqual(utf8["metadata"]["delimiter"], ",")
        self.assertTrue(utf8["metadata"]["duplicate_headers"])
        self.assertEqual(utf8["rows"][0][2], "line one\nline two")
        self.assertEqual(utf8["rows"][1][2], 'a "quote"')
        self.assertEqual(utf8["rows"][0][3], "")
        cp1251 = self._table(
            outputs["csv-cp1251-semicolon-headerless"]
        )["content"]
        self.assertEqual(cp1251["metadata"]["delimiter"], ";")
        self.assertFalse(cp1251["metadata"]["header_present"])
        self.assertIn(cp1251["metadata"]["encoding"], {"cp1251", "windows-1251"})
        large = self._table(outputs["csv-large"])["content"]
        self.assertEqual(len(large["rows"]), 1_501)
        self.assertTrue(all(cell["cell_type"] == "string" for cell in large["cells"]))

    def test_xlsx_workbook_semantics_and_three_run_storage_determinism(self):
        artifacts = self._three_runs(
            document_id="xlsx-complete",
            container_format="xlsx",
            mime_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            content=self._xlsx_bytes(),
        )
        artifact = artifacts[0]
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
        self.assertTrue(sheets[0]["metadata"]["named_ranges"])
        self.assertEqual(len(sheets[0]["metadata"]["table_definitions"]), 2)
        cells = [
            cell
            for node in artifact["nodes"]
            if node["node_type"] == "TABLE"
            for cell in node["content"]["cells"]
        ]
        formula = next(cell for cell in cells if cell["formula"] == "B2*2")
        self.assertEqual(formula["raw_value"], "20")
        self.assertEqual(formula["displayed_value"], "20")
        self.assertIsNone(formula["merged_range"])
        self.assertEqual(formula["number_format_ref"], "style:2")
        visible_table = next(
            node
            for node in artifact["nodes"]
            if node["node_type"] == "TABLE"
            and node["container_ref"] == sheets[0]["container_id"]
        )
        self.assertEqual(visible_table["content"]["rows"][2], [])
        self.assertTrue(any(cell["merged_range"] == "A4:B4" for cell in cells))
        self.assertTrue(any(cell["hidden"] for cell in cells))

    def test_pdf_adapter_and_storage_are_three_run_deterministic(self):
        units = [
            {
                "unit_ref": "intro",
                "source_location": {"page": 1, "line_start": 1},
                "text": "Introduction",
            },
            {
                "unit_ref": "table-source",
                "source_location": {"page": 1, "line_start": 2},
                "rows": [["A", "B"], ["1", "2"]],
            },
            {
                "unit_ref": "page-two",
                "source_location": {"page": 2, "line_start": 1},
                "text": "Continuation",
            },
        ]
        artifacts = self._three_runs(
            document_id="pdf-complete",
            container_format="pdf",
            mime_type="application/pdf",
            content=b"frozen-pdf-placeholder",
            source_units=units,
        )
        artifact = artifacts[0]
        self.assertEqual(
            [item["container_type"] for item in artifact["containers"]],
            ["DOCUMENT", "PAGE", "PAGE"],
        )
        self.assertEqual(
            [item["node_type"] for item in artifact["nodes"]],
            ["TEXT", "TABLE", "PAGE_BREAK", "TEXT"],
        )

    def _three_runs(
        self,
        *,
        document_id: str,
        container_format: str,
        mime_type: str,
        content: bytes,
        source_units: list[dict] | None = None,
    ) -> list[dict]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=root / "artifacts.sqlite3",
                    payload_root=root / "payloads",
                )
            ).create()
            source_sha256 = hashlib.sha256(content).hexdigest()
            if source_units is None:
                built = FullSourceArtifactFactory(
                    FullSourceArtifactConfig(
                        enable_canonical_artifact_v1_shadow=True
                    )
                ).create().build(
                    normalization_run_id="fixture-build",
                    document_id=document_id,
                    profile_id=f"profile-{document_id}",
                    container_format=container_format,
                    content_bytes=content,
                    source_checksum_sha256=source_sha256,
                )
                source_payloads = built.payloads
                units = built.units
            else:
                units = source_units
                pages = sorted(
                    {
                        int((unit.get("source_location") or {}).get("page") or 0)
                        for unit in units
                        if int((unit.get("source_location") or {}).get("page") or 0)
                        > 0
                    }
                )
                source_payloads = (
                    [
                        {
                            "parser_completeness_status": "complete",
                            "parser_completeness_reason_codes": [],
                            "pdf_text_layer_projection": {
                                "page_inventory": [
                                    {"page_number": page} for page in pages
                                ],
                                "line_inventory": [],
                            },
                        }
                    ]
                    if container_format == "pdf"
                    else []
                )
            hashes: list[str] = []
            issue_sets: list[list[dict]] = []
            ordered_content: list[list[tuple[str, str, int]]] = []
            resolved: list[dict] = []
            previous = None
            for index in range(3):
                context = ArtifactAccessContext(
                    user_id="doc26-user",
                    normalization_run_id=f"{document_id}-run-{index + 1}",
                    case_id="doc26-case",
                    workspace_model_id="doc26-workspace",
                    allow_private=True,
                )
                source_ref = f"source-{document_id}-{index + 1}"
                self._put_source(
                    store,
                    context=context,
                    source_ref=source_ref,
                    document_id=document_id,
                )
                artifact = CanonicalNormalizerFactory(
                    CanonicalNormalizerConfig(
                        normalizer_version="canonical-doc26-fixture-v1"
                    )
                ).create().build(
                    tenant_id=context.user_id,
                    artifact_version=1,
                    document={
                        "container_format": container_format,
                        "sha256": source_sha256,
                        "declared_mime_type": mime_type,
                    },
                    source_artifact_ref=source_ref,
                    source_payloads=source_payloads,
                    source_units=units,
                    table_projections=[],
                )
                persisted = CanonicalArtifactStoreFactory(
                    store=store,
                    config=CanonicalStorageConfig(
                        small_payload_max_bytes=2_048,
                        large_table_cell_threshold=100,
                    ),
                ).create().put_candidate(
                    artifact=artifact,
                    context=context,
                    retention_policy=build_retention_policy(mode="api_smoke"),
                    compare_receipt=None,
                )
                self.assertEqual(persisted.previous_version_ref, previous)
                previous = persisted.canonical_version_id
                logical = CanonicalReaderFactory(
                    store=store, read_enabled=True
                ).create().read(persisted.artifact_ref, context)
                hashes.append(logical["canonical_root_hash"])
                issue_sets.append(logical["issues"])
                ordered_content.append(
                    [
                        (
                            str(node["container_ref"]),
                            str(node["node_type"]),
                            int(node["order"]),
                        )
                        for node in logical["nodes"]
                    ]
                )
                resolved.append(logical)
            self.assertEqual(len(set(hashes)), 1)
            self.assertEqual(issue_sets[0], issue_sets[1])
            self.assertEqual(issue_sets[1], issue_sets[2])
            self.assertEqual(ordered_content[0], ordered_content[1])
            self.assertEqual(ordered_content[1], ordered_content[2])
            for artifact in resolved:
                provenance_ids = {
                    item["provenance_id"] for item in artifact["provenance"]
                }
                self.assertTrue(
                    all(
                        set(node["source_refs"]) <= provenance_ids
                        for node in artifact["nodes"]
                    )
                )
                self.assertNotIn("financial_fact", str(artifact).lower())
            return resolved

    @staticmethod
    def _put_source(store, *, context, source_ref, document_id):
        retention = build_retention_policy(mode="api_smoke")
        store.put_record(
            ArtifactRecord(
                artifact_id=source_ref,
                artifact_type="source_file_ref_v0",
                case_id=context.case_id,
                chat_id=context.chat_id,
                user_id=context.user_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                document_id=document_id,
                source_file_ref={"openwebui_file_id": f"file-{document_id}"},
                visibility="private_case",
                storage_backend="project_artifact_payload",
                retention_policy=retention,
                access_policy={"requires_user_id": True},
                validation_status="validated",
                lifecycle_status=lifecycle_for_visibility(
                    visibility="private_case", validation_status="validated"
                ),
                payload={"frozen_fixture": True},
            )
        )

    @staticmethod
    def _table(artifact: dict) -> dict:
        return next(
            item for item in artifact["nodes"] if item["node_type"] == "TABLE"
        )

    @staticmethod
    def _xlsx_bytes() -> bytes:
        payload = BytesIO()
        workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <definedNames><definedName name="ReportRange">Visible!$A$1:$C$4</definedName></definedNames>
  <sheets><sheet name="Visible" sheetId="1" r:id="rId1"/><sheet name="Hidden" sheetId="2" state="hidden" r:id="rId2"/></sheets>
</workbook>"""
        relationships = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>"""
        sheet1 = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>Date</t></is></c><c r="B1" t="inlineStr"><is><t>Amount</t></is></c><c r="C1" t="inlineStr"><is><t>Total</t></is></c></row>
    <row r="2"><c r="A2" s="1"><v>46023</v></c><c r="B2" s="2"><v>10</v></c><c r="C2" s="2"><f>B2*2</f><v>20</v></c></row>
    <row r="3"></row><row r="4"><c r="A4" t="inlineStr"><is><t>Merged</t></is></c></row>
  </sheetData><mergeCells count="1"><mergeCell ref="A4:B4"/></mergeCells>
  <tableParts count="2"><tablePart r:id="rTable1"/><tablePart r:id="rTable2"/></tableParts>
</worksheet>"""
        sheet2 = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1" hidden="1"><c r="A1" t="inlineStr"><is><t>Hidden row</t></is></c></row></sheetData></worksheet>"""
        with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("xl/workbook.xml", workbook)
            archive.writestr("xl/_rels/workbook.xml.rels", relationships)
            archive.writestr("xl/worksheets/sheet1.xml", sheet1)
            archive.writestr("xl/worksheets/sheet2.xml", sheet2)
        return payload.getvalue()


if __name__ == "__main__":
    unittest.main()
