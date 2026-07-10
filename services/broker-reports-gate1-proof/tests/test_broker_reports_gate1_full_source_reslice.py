from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    FullSourceArtifactFactory,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    Gate2SourceUnitRouterFactory,
    Gate2SourceUnitSegmenterFactory,
    build_retention_policy,
    persist_gate1_result,
    resolve_source_value,
    validate_full_source_unit,
)
from broker_reports_gate1.full_source import FACTORY_REQUIRED, FORBIDDEN


def _full_csv() -> bytes:
    header = "Date,Operation,Amount,Currency,Identifier\n"
    rows = "".join(
        f"2026-01-{index:02d},position_snapshot,{index}.00,USD,SYNTH-{index:02d}\n"
        for index in range(1, 13)
    )
    return (header + rows).encode("utf-8")


class BrokerReportsGate1FullSourceResliceTest(unittest.TestCase):
    def test_full_source_unit_covers_rows_beyond_legacy_preview_with_stable_refs(self):
        first = self._normalize()
        second = self._normalize()
        preview = first.package["private_normalized_slices"][0]
        payload = first.package["private_normalized_source_payloads"][0]
        unit = first.package["private_normalized_source_units"][0]
        second_unit = second.package["private_normalized_source_units"][0]
        document = first.package["document_inventory"]["documents"][0]

        self.assertIn("FullSourceArtifactFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not mint extraction-grade full-source refs", FORBIDDEN)
        self.assertEqual(len(preview["cells"]), 5)
        self.assertTrue(preview["truncated"])
        self.assertEqual(payload["schema_version"], "private_normalized_source_payload_v0")
        self.assertEqual(payload["parser_completeness_status"], "complete")
        self.assertEqual(payload["rows_total"], 13)
        self.assertEqual(unit["schema_version"], "private_normalized_source_unit_v0")
        self.assertEqual(len(unit["cells"]), 13)
        self.assertFalse(unit["source_slice_truncated"])
        self.assertFalse(unit["parent_source_slice_truncated"])
        self.assertEqual(unit["parent_remainder_status"], "not_applicable_parent_complete")
        self.assertEqual(unit["coverage"]["selected_total"], 13)
        self.assertEqual(unit["row_refs"], second_unit["row_refs"])
        self.assertEqual(unit["source_value_refs"], second_unit["source_value_refs"])
        twelfth_amount_ref = next(
            item["source_value_ref"]
            for item in unit["cell_provenance"]
            if item["row_ordinal"] == 12 and item["column_ordinal"] == 3
        )
        self.assertEqual(resolve_source_value(unit, twelfth_amount_ref), "11.00")
        validation = validate_full_source_unit(
            unit=unit,
            normalization_run_id=first.package["normalization_run"]["run_id"],
            document_id=document["document_id"],
            source_checksum_sha256=document["sha256"],
        )
        self.assertEqual(validation["validator_status"], "passed")

    def test_artifactstore_and_gate2_prefer_complete_unit_without_parent_remainder(self):
        result = self._normalize()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            store = ArtifactStoreFactory(
                ArtifactStoreConfig(
                    mode="sqlite",
                    sqlite_path=root / "artifacts.sqlite3",
                    payload_root=root / "payloads",
                )
            ).create()
            run_id = result.package["normalization_run"]["run_id"]
            context = ArtifactAccessContext(
                user_id="full-source-test-user",
                normalization_run_id=run_id,
                case_id="full-source-test-case",
                chat_id="full-source-test-chat",
                workspace_model_id="full-source-test-model",
                allow_private=True,
                require_source_available=True,
            )
            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            self.assertEqual(len(manifest.private_source_payload_refs), 1)
            self.assertEqual(len(manifest.private_source_unit_refs), 1)
            records = store.list_by_run(run_id)
            unit_record = next(
                item
                for item in records
                if item.artifact_type == "private_normalized_source_unit_v0"
            )
            self.assertEqual(unit_record.visibility, "private_case")
            self.assertEqual(unit_record.storage_backend, "project_artifact_payload")
            self.assertTrue(unit_record.access_policy["requires_gate2_resolver"])
            self.assertTrue(
                all(item.storage_backend != "openwebui_knowledge" for item in records)
            )

            dcp_ref = manifest.artifact_refs_by_type["domain_context_packet_v0"][0]
            readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
                domain_context_packet_ref=dcp_ref,
                context=context,
            )
            self.assertEqual(readiness.validation["validator_status"], "passed")
            package = readiness.packages[0]
            self.assertEqual(
                package["source_unit"]["source_input_mode"], "full_source_unit"
            )
            self.assertTrue(
                package["expansion_readiness"]["limited_primary_expansion_ready"]
            )
            route = Gate2SourceUnitRouterFactory().create().route(package)
            segmented = Gate2SourceUnitSegmenterFactory().create().segment(
                base_package=package,
                parent_route=route,
            )
            self.assertEqual(
                segmented.plan["coverage"]["parent_remainder_status"],
                "not_applicable_parent_complete",
            )
            self.assertFalse(segmented.plan["parent_source_slice_truncated"])
            self.assertTrue(
                all(
                    item["source_unit"]["parent_remainder_status"]
                    == "not_applicable_parent_complete"
                    for item in segmented.derived_packages
                )
            )

    def test_invalid_pdf_full_source_projection_fails_closed_without_ocr(self):
        result = FullSourceArtifactFactory().create().build(
            normalization_run_id="normrun_pdf_partial",
            document_id="brdoc_001_pdfpartial",
            profile_id="techprof_pdfpartial",
            container_format="pdf",
            content_bytes=b"%PDF-1.4\n1 0 obj <<>> stream\nBT (Visible text) Tj ET\nendstream\n%%EOF",
            source_checksum_sha256="a" * 64,
        )
        self.assertIn(result.summary["parser_completeness_status"], {"partial", "blocked"})
        self.assertFalse(result.summary["full_coverage_available"])
        self.assertEqual(result.units, [])
        self.assertIn(
            "pdf_corrupt_or_unreadable",
            result.summary["parser_completeness_reason_codes"],
        )

    @staticmethod
    def _normalize():
        return Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="full-source-reslice-synthetic",
                    filename="synthetic_full_source.csv",
                    content=_full_csv(),
                    mime_type="text/csv",
                )
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
        )


if __name__ == "__main__":
    unittest.main()
