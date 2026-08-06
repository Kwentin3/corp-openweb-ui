from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
import sys

from jsonschema import Draft202012Validator

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    CanonicalArtifactError,
    CanonicalArtifactStoreFactory,
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
    CanonicalReaderFactory,
    CanonicalStorageConfig,
    build_retention_policy,
)
from broker_reports_gate1.artifact_lifecycle import lifecycle_for_visibility
from broker_reports_gate1.artifact_models import ArtifactRecord


REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = REPO_ROOT / "docs" / "stage2" / "contracts" / "BROKER_REPORTS_CANONICAL_ARTIFACT.v1.schema.json"
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
sys.path.insert(0, str(REPO_ROOT / "services" / "broker-reports-gate1-proof" / "scripts"))
import doc30_resource_bounded_backfill as doc30_runner  # noqa: E402


class BrokerReportsDoc31XlsxStreamingTest(unittest.TestCase):
    def test_duplicate_instance_scope_rewrites_only_exact_document_refs(self):
        package = {
            "document_id": "original-document",
            "refs": ["original-document", "prefix-original-document"],
            "nested": {"document_ref": "original-document", "content": "original-document report"},
        }
        doc30_runner._replace_exact_string(
            package, "original-document", "brdoc_011_fixture"
        )
        self.assertEqual(package["document_id"], "brdoc_011_fixture")
        self.assertEqual(package["refs"], ["brdoc_011_fixture", "prefix-original-document"])
        self.assertEqual(package["nested"]["document_ref"], "brdoc_011_fixture")
        self.assertEqual(package["nested"]["content"], "original-document report")

    def test_profile_preserves_structure_and_resumes_exactly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "fixture.xlsx"
            self._write_xlsx(source)
            stage = Path(temp_dir) / "stage"
            plan = self._plan(source, stage)
            repeated = self._plan(source, stage)

            self.assertEqual(plan.canonical_root_hash, repeated.canonical_root_hash)
            self.assertEqual(plan.node_entries, repeated.node_entries)
            self.assertEqual(plan.safe_metrics["formulas"], 2)
            self.assertEqual(plan.safe_metrics["missing_cached_values"], 1)
            self.assertEqual(plan.safe_metrics["blank_styled_cells"], 1)
            sheets = [item for item in plan.containers if item["container_type"] == "SHEET"]
            self.assertEqual([item["metadata"]["sheet_visibility"] for item in sheets], ["visible", "hidden"])
            self.assertEqual(plan.containers[0]["metadata"]["named_ranges"][0]["name"], "FixtureRange")
            self.assertEqual(plan.containers[0]["metadata"]["shared_strings"][0]["value"], "Shared Alpha")
            cells = [
                cell
                for node in plan.iter_nodes()
                for cell in (node.get("content") or {}).get("cells", [])
            ]
            shared = next(cell for cell in cells if cell["source_coordinate"] == "A1")
            cached = next(cell for cell in cells if cell["source_coordinate"] == "B1")
            missing = next(cell for cell in cells if cell["source_coordinate"] == "B2")
            self.assertEqual(shared["shared_string_ref"], "sst:0")
            self.assertEqual(cached["cached_value"], 20)
            self.assertIsNone(missing["cached_value"])
            first_table = next(node for node in plan.iter_nodes() if node["node_type"] == "TABLE")
            self.assertEqual(
                first_table["content"]["metadata"]["blank_style_runs"],
                [{"row": 1, "start_column": 3, "end_column": 3, "style_ref": "style:1"}],
            )
            summaries = {item["summary"] for item in plan.issues}
            self.assertIn("DIMENSION_METADATA_INCONSISTENT", summaries)
            self.assertIn("STALE_CALCULATION_POSSIBLE", summaries)
            self.assertIn("MISSING_CACHED_VALUE", summaries)

    def test_resume_rejects_tampered_chunk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "fixture.xlsx"
            self._write_xlsx(source)
            stage = Path(temp_dir) / "stage"
            plan = self._plan(source, stage)
            entry = next(item for item in plan.node_entries if item.get("relative_path"))
            (stage / entry["relative_path"]).write_text("{}", encoding="utf-8")
            with self.assertRaises(CanonicalArtifactError) as failure:
                self._plan(source, stage)
            self.assertEqual(failure.exception.code, "xlsx_streaming_resume_chunk_invalid")

    def test_bounded_publish_schema_reader_and_tenant_boundary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "fixture.xlsx"
            self._write_xlsx(source)
            context = self._context()
            store, retention = self._store_with_source(root, context)
            plan = self._plan(source, root / "stage")
            persisted = CanonicalArtifactStoreFactory(
                store=store,
                config=CanonicalStorageConfig(
                    capacity_check_enabled=False,
                    maximum_artifact_bytes=16 * 1024 * 1024,
                ),
            ).create().put_xlsx_streaming_candidate(
                plan=plan, context=context, retention_policy=retention
            )
            reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
            receipt = reader.validate_streaming_version(
                document_id="document-xlsx",
                canonical_version_id=persisted.canonical_version_id,
                context=context,
            )
            self.assertTrue(receipt["passed"])
            self.assertEqual(persisted.physical_layout, "xlsx_row_chunked_v1")
            artifact = reader.read(persisted.artifact_ref, context)
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            self.assertEqual(list(Draft202012Validator(schema).iter_errors(artifact)), [])
            table_id = next(node["node_id"] for node in artifact["nodes"] if node["node_type"] == "TABLE")
            self.assertEqual(
                reader.read_table(
                    "document-xlsx", table_id, context,
                    canonical_version_id=persisted.canonical_version_id,
                )["node_id"],
                table_id,
            )
            other = ArtifactAccessContext(
                user_id="other-user",
                normalization_run_id=context.normalization_run_id,
                case_id=context.case_id,
                chat_id=context.chat_id,
                workspace_model_id=context.workspace_model_id,
                allow_private=True,
                require_source_available=True,
            )
            with self.assertRaises(ArtifactStoreError) as denied:
                reader.validate_streaming_version(
                    document_id="document-xlsx",
                    canonical_version_id=persisted.canonical_version_id,
                    context=other,
                )
            self.assertEqual(denied.exception.code, "artifact_access_denied")

    def test_failed_stream_write_leaves_no_partial_candidate_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "fixture.xlsx"
            self._write_xlsx(source)
            context = self._context()
            store, retention = self._store_with_source(root, context)
            plan = self._plan(source, root / "stage")
            before = sorted(path.name for path in store.payload_root.glob("*.json"))
            original = store.put_record
            calls = 0

            def fail_third(record):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise RuntimeError("synthetic storage boundary failure")
                return original(record)

            canonical_store = CanonicalArtifactStoreFactory(
                store=store,
                config=CanonicalStorageConfig(capacity_check_enabled=False),
            ).create()
            with patch.object(store, "put_record", side_effect=fail_third):
                with self.assertRaisesRegex(RuntimeError, "synthetic storage"):
                    canonical_store.put_xlsx_streaming_candidate(
                        plan=plan, context=context, retention_policy=retention
                    )
            self.assertEqual(sorted(path.name for path in store.payload_root.glob("*.json")), before)
            with closing(sqlite3.connect(store.sqlite_path)) as connection:
                self.assertEqual(
                    connection.execute("SELECT status FROM canonical_versions").fetchone()[0],
                    "PURGED",
                )
                rows = connection.execute(
                    "SELECT lifecycle_status, storage_backend FROM artifact_records WHERE artifact_type = 'broker_reports_canonical_component_v1'"
                ).fetchall()
            self.assertTrue(rows)
            self.assertTrue(all(row == ("purged", "none_tombstone") for row in rows))

    @staticmethod
    def _context() -> ArtifactAccessContext:
        return ArtifactAccessContext(
            user_id="xlsx-user",
            normalization_run_id="xlsx-run",
            case_id="xlsx-case",
            chat_id="xlsx-chat",
            workspace_model_id="xlsx-workspace",
            allow_private=True,
            require_source_available=True,
        )

    @staticmethod
    def _plan(source: Path, stage: Path):
        return CanonicalNormalizerFactory(
            CanonicalNormalizerConfig(normalizer_version="canonical-doc31-v1")
        ).create().build_xlsx_streaming(
            source_path=source,
            staging_root=stage,
            tenant_id="xlsx-user",
            document_id="document-xlsx",
            source_artifact_ref="source-xlsx",
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            mime_type=MIME,
        )

    @staticmethod
    def _store_with_source(root: Path, context: ArtifactAccessContext):
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        retention = build_retention_policy(mode="api_smoke")
        store.put_record(
            ArtifactRecord(
                artifact_id="source-xlsx",
                artifact_type="source_file_ref_v0",
                case_id=context.case_id,
                chat_id=context.chat_id,
                user_id=context.user_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                document_id="document-xlsx",
                source_file_ref={"openwebui_file_id": "fixture-file"},
                visibility="private_case",
                storage_backend="project_artifact_payload",
                retention_policy=retention,
                access_policy={"requires_user_id": True},
                validation_status="validated",
                lifecycle_status=lifecycle_for_visibility(
                    visibility="private_case", validation_status="validated"
                ),
                payload={"source": True},
            )
        )
        return store, retention

    @staticmethod
    def _write_xlsx(path: Path) -> None:
        workbook = '''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Visible" sheetId="1" r:id="rId1"/><sheet name="Hidden" sheetId="2" state="hidden" r:id="rId2"/></sheets><definedNames><definedName name="FixtureRange">Visible!$A$1:$C$2</definedName></definedNames><calcPr calcId="1"/></workbook>'''
        relationships = '''<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>'''
        shared_strings = '''<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Shared Alpha</t></si></sst>'''
        styles = '''<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd"/></numFmts><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0"/></cellXfs></styleSheet>'''
        sheet1 = '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:XFD1048576"/><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><f>A2*2</f><v>20</v></c><c r="C1" s="1"/></row><row r="2"><c r="A2"><v>10</v></c><c r="B2"><f>A2+1</f></c></row></sheetData><mergeCells count="1"><mergeCell ref="A1:B1"/></mergeCells></worksheet>'''
        sheet2 = '''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1" hidden="1"><c r="A1" t="inlineStr"><is><t>hidden</t></is></c></row></sheetData></worksheet>'''
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, value in (
                ("xl/workbook.xml", workbook),
                ("xl/_rels/workbook.xml.rels", relationships),
                ("xl/sharedStrings.xml", shared_strings),
                ("xl/styles.xml", styles),
                ("xl/worksheets/sheet1.xml", sheet1),
                ("xl/worksheets/sheet2.xml", sheet2),
            ):
                archive.writestr(name, value)


if __name__ == "__main__":
    unittest.main()
