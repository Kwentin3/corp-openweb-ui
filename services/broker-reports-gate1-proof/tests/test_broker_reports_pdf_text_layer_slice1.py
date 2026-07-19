from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    FullSourceArtifactConfig,
    FullSourceArtifactFactory,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    PdfParserCapabilityRequest,
    PdfTextLayerParserConfig,
    PdfTextLayerParserError,
    PdfTextLayerParserFactory,
    build_retention_policy,
    persist_gate1_result,
    resolve_source_value,
    validate_full_source_unit,
    validate_pdf_source_unit,
    validate_pdf_source_unit_parent_linkage,
    validate_pdf_source_unit_structure,
    validate_pdf_text_layer_payload,
)
from broker_reports_gate1.pdf_text_layer import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PYPDF_PINNED_VERSION,
)


def _font_resource(writer: PdfWriter):
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    return writer._add_object(font)


def _add_text_page(writer: PdfWriter, lines: list[str]) -> None:
    page = writer.add_blank_page(width=300, height=300)
    font_ref = _font_resource(writer)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): font_ref}
            )
        }
    )
    operators = [b"BT /F1 12 Tf 20 260 Td"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            operators.append(b"0 -20 Td")
        operators.append(f"({escaped}) Tj".encode("latin-1"))
    operators.append(b"ET")
    stream = DecodedStreamObject()
    stream.set_data(b"\n".join(operators))
    page[NameObject("/Contents")] = writer._add_object(stream)


def _add_image_only_page(writer: PdfWriter) -> None:
    page = writer.add_blank_page(width=300, height=300)
    image = DecodedStreamObject()
    image.set_data(b"\x00")
    image.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Image"),
            NameObject("/Width"): NumberObject(1),
            NameObject("/Height"): NumberObject(1),
            NameObject("/ColorSpace"): NameObject("/DeviceGray"),
            NameObject("/BitsPerComponent"): NumberObject(8),
        }
    )
    image_ref = writer._add_object(image)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/XObject"): DictionaryObject(
                {NameObject("/Im1"): image_ref}
            )
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"q 10 0 0 10 20 20 cm /Im1 Do Q")
    page[NameObject("/Contents")] = writer._add_object(stream)


def _pdf_bytes(
    *,
    pages: list[tuple[str, list[str]]],
    encrypted: bool = False,
) -> bytes:
    writer = PdfWriter()
    for kind, lines in pages:
        if kind == "text":
            _add_text_page(writer, lines)
        elif kind == "blank":
            writer.add_blank_page(width=300, height=300)
        elif kind == "image":
            _add_image_only_page(writer)
        else:
            raise AssertionError(f"unsupported synthetic page kind: {kind}")
    if encrypted:
        writer.encrypt("synthetic-secret")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


class BrokerReportsPdfTextLayerSlice1Test(unittest.TestCase):
    def test_factory_is_pinned_and_rejects_capability_downgrade(self):
        self.assertIn("PdfTextLayerParserFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not instantiate PypdfParserAdapter directly", FORBIDDEN)
        parser = PdfTextLayerParserFactory().create()
        self.assertEqual(parser.config.expected_pypdf_version, PYPDF_PINNED_VERSION)
        layout_parser = PdfTextLayerParserFactory().create(
            PdfParserCapabilityRequest(capability="table_candidates")
        )
        self.assertEqual(layout_parser.requested_capability, "table_candidates")

        with self.assertRaises(PdfTextLayerParserError) as capability_error:
            PdfTextLayerParserFactory().create(
                PdfParserCapabilityRequest(capability="semantic_tables")
            )
        self.assertEqual(
            capability_error.exception.code,
            "pdf_parser_capability_unsupported",
        )

        with self.assertRaises(PdfTextLayerParserError) as version_error:
            PdfTextLayerParserFactory(
                PdfTextLayerParserConfig(expected_pypdf_version="0.0.0")
            ).create()
        self.assertEqual(
            version_error.exception.code,
            "pdf_pypdf_runtime_version_mismatch",
        )

    def test_complete_page_text_payload_refs_checksums_and_values_are_stable(self):
        content = _pdf_bytes(
            pages=[
                ("text", ["Synthetic Broker Report", "Amount 10.00 USD"]),
                ("blank", []),
            ]
        )
        first = self._build(content)
        second = self._build(content)

        self.assertEqual(first.summary["parser_completeness_status"], "complete")
        self.assertEqual(first.summary["pdf_pages_total"], 2)
        self.assertEqual(first.summary["pdf_pages_with_text"], 1)
        self.assertEqual(first.summary["pdf_pages_without_text"], 1)
        self.assertEqual(len(first.units), 2)
        payload = first.payloads[0]
        unit = next(
            item for item in first.units if item["pdf_unit_type"] == "pdf_page_text_unit"
        )
        visual_unit = next(
            item for item in first.units if item["pdf_unit_type"] == "pdf_visual_page_unit"
        )
        second_payload = second.payloads[0]
        second_unit = next(
            item for item in second.units if item["pdf_unit_type"] == "pdf_page_text_unit"
        )
        second_visual_unit = next(
            item for item in second.units if item["pdf_unit_type"] == "pdf_visual_page_unit"
        )

        self.assertEqual(
            payload["pdf_text_layer_projection"]["schema_version"],
            "pdf_text_layer_projection_v0",
        )
        self.assertEqual(payload["text_layer_projection_status"], "complete")
        self.assertEqual(payload["semantic_reconstruction_status"], "not_claimed")
        self.assertFalse(payload["ocr_vlm_used"])
        self.assertTrue(payload["page_rendering_used_for_extraction"])
        self.assertEqual(
            payload["pdf_text_layer_projection"]["page_checksum_refs"],
            second_payload["pdf_text_layer_projection"]["page_checksum_refs"],
        )
        self.assertEqual(payload["page_refs"], second_payload["page_refs"])
        self.assertEqual(payload["payload_checksum_ref"], second_payload["payload_checksum_ref"])
        self.assertEqual(unit["text_segment_refs"], second_unit["text_segment_refs"])
        self.assertEqual(unit["character_span_refs"], second_unit["character_span_refs"])
        self.assertEqual(unit["source_value_refs"], second_unit["source_value_refs"])
        self.assertEqual(
            visual_unit["source_unit_checksum_ref"],
            second_visual_unit["source_unit_checksum_ref"],
        )
        self.assertEqual(unit["pdf_unit_type"], "pdf_page_text_unit")
        self.assertTrue(unit["declared_range_complete"])
        self.assertFalse(unit["source_slice_truncated"])
        self.assertFalse(unit["parent_source_slice_truncated"])
        self.assertEqual(unit["parent_remainder_status"], "not_applicable_parent_complete")
        self.assertEqual(unit["coverage"]["selected_total"], unit["coverage"]["accounted_total"])
        self.assertTrue(unit["coverage"]["all_selected_refs_accounted"])

        payload_validation = validate_pdf_text_layer_payload(payload)
        self.assertEqual(payload_validation["validator_status"], "passed")
        unit_validation = validate_full_source_unit(
            unit=unit,
            normalization_run_id="normrun_pdf_slice1",
            document_id="brdoc_pdf_slice1",
            source_checksum_sha256="a" * 64,
        )
        self.assertEqual(unit_validation["validator_status"], "passed")
        missing_parent_errors = validate_pdf_source_unit(
            unit,
            require_parent_payload=True,
        )
        self.assertIn(
            "pdf_source_unit_parent_payload_missing",
            {item["code"] for item in missing_parent_errors},
        )
        structural_errors = validate_pdf_source_unit_structure(unit)
        linkage_errors = validate_pdf_source_unit_parent_linkage(
            unit,
            parent_payload=payload,
            parent_validation=payload_validation,
            require_parent_payload=True,
        )
        self.assertEqual(structural_errors, [])
        self.assertEqual(linkage_errors, [])
        self.assertEqual(
            validate_pdf_source_unit(
                unit,
                parent_payload=payload,
                parent_validation=payload_validation,
                require_parent_payload=True,
            ),
            [*structural_errors, *linkage_errors],
        )
        wrong_parent_errors = validate_pdf_source_unit_parent_linkage(
            {**unit, "parent_payload_ref": "pdfpayload_foreign"},
            parent_payload=payload,
            parent_validation=payload_validation,
            require_parent_payload=True,
        )
        self.assertIn(
            "pdf_source_unit_parent_ref_mismatch",
            {item["code"] for item in wrong_parent_errors},
        )
        wrong_checksum_errors = validate_pdf_source_unit_parent_linkage(
            {**unit, "payload_checksum_ref": "pdfpayloadchk_foreign"},
            parent_payload=payload,
            parent_validation=payload_validation,
            require_parent_payload=True,
        )
        self.assertIn(
            "pdf_source_unit_payload_checksum_mismatch",
            {item["code"] for item in wrong_checksum_errors},
        )
        values = [resolve_source_value(unit, ref) for ref in unit["source_value_refs"]]
        self.assertIn("Synthetic Broker Report\n", values)
        self.assertIn("Amount 10.00 USD", values)

        page_inventory = payload["pdf_text_layer_projection"]["page_inventory"]
        self.assertEqual(page_inventory[1]["page_content_kind"], "blank")
        self.assertEqual(page_inventory[1]["page_projection_status"], "complete")
        self.assertIn(
            page_inventory[1]["page_ref"],
            payload["pdf_text_layer_projection"]["coverage"]["blank_or_layout_refs"],
        )

    def test_budget_image_only_encrypted_and_corrupt_inputs_fail_closed(self):
        text_pdf = _pdf_bytes(pages=[("text", ["Synthetic text for budget"] * 4)])
        budget = FullSourceArtifactFactory(
            FullSourceArtifactConfig(max_pdf_page_content_stream_bytes=16)
        ).create().build(
            normalization_run_id="normrun_pdf_budget",
            document_id="brdoc_pdf_budget",
            profile_id="techprof_pdf_budget",
            container_format="pdf",
            content_bytes=text_pdf,
            source_checksum_sha256="b" * 64,
        )
        self.assertEqual(budget.summary["parser_completeness_status"], "partial")
        self.assertEqual(budget.units, [])
        self.assertIn(
            "pdf_content_stream_budget_exceeded",
            budget.summary["parser_completeness_reason_codes"],
        )

        image_only = self._build(_pdf_bytes(pages=[("image", [])]))
        self.assertEqual(image_only.summary["parser_completeness_status"], "complete")
        self.assertEqual(
            [unit["pdf_unit_type"] for unit in image_only.units],
            ["pdf_visual_page_unit"],
        )
        self.assertEqual(image_only.summary["parser_completeness_reason_codes"], [])
        self.assertEqual(
            image_only.payloads[0]["visible_content_coverage_status"],
            "complete_with_visual_fallback",
        )

        encrypted = self._build(
            _pdf_bytes(
                pages=[("text", ["Encrypted synthetic text"])],
                encrypted=True,
            )
        )
        self.assertEqual(encrypted.summary["parser_completeness_status"], "blocked")
        self.assertEqual(encrypted.units, [])
        self.assertIn(
            "pdf_encrypted_without_key",
            encrypted.summary["parser_completeness_reason_codes"],
        )

        corrupt = self._build(b"%PDF-1.7\nnot-a-valid-object-graph\n%%EOF")
        self.assertEqual(corrupt.summary["parser_completeness_status"], "blocked")
        self.assertEqual(corrupt.units, [])
        self.assertIn(
            "pdf_corrupt_or_unreadable",
            corrupt.summary["parser_completeness_reason_codes"],
        )

    def test_artifactstore_and_gate2_no_model_dry_run_use_complete_pdf_unit(self):
        content = _pdf_bytes(
            pages=[("text", ["Synthetic Broker Report", "Amount 10.00 USD"])]
        )
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="pdf-text-layer-slice1",
                    filename="synthetic_text_layer.pdf",
                    content=content,
                    mime_type="application/pdf",
                )
            ],
            input_context={
                "clarification_criticality_refinement_enabled": True,
                "pdf_layout_slice2_enabled": False,
            },
        )
        self.assertEqual(result.package["validation_result"]["status"], "passed")
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
                user_id="pdf-slice1-user",
                normalization_run_id=run_id,
                case_id="pdf-slice1-case",
                chat_id="pdf-slice1-chat",
                workspace_model_id="pdf-slice1-model",
                allow_private=True,
                require_source_available=True,
            )
            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            records = store.list_by_run(run_id)
            pdf_payload_record = next(
                record
                for record in records
                if record.artifact_type == "private_normalized_source_payload_v0"
            )
            pdf_unit_record = next(
                record
                for record in records
                if record.artifact_type == "private_normalized_source_unit_v0"
            )
            self.assertEqual(pdf_payload_record.visibility, "private_case")
            self.assertEqual(pdf_payload_record.storage_backend, "project_artifact_payload")
            self.assertTrue(pdf_payload_record.access_policy["requires_gate2_resolver"])
            self.assertEqual(pdf_unit_record.visibility, "private_case")
            self.assertEqual(pdf_unit_record.storage_backend, "project_artifact_payload")
            self.assertTrue(pdf_unit_record.access_policy["requires_gate2_resolver"])
            self.assertFalse(
                any(record.storage_backend == "openwebui_knowledge" for record in records)
            )

            dcp_ref = manifest.artifact_refs_by_type["domain_context_packet_v0"][0]
            readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
                domain_context_packet_ref=dcp_ref,
                context=context,
            )
            self.assertEqual(readiness.validation["validator_status"], "passed")
            self.assertTrue(readiness.validation["artifactstore_unchanged"])
            self.assertEqual(readiness.validation["knowledge_records"], 0)
            self.assertEqual(len(readiness.packages), 1)
            package = readiness.packages[0]
            self.assertEqual(package["source_unit"]["source_input_mode"], "full_source_unit")
            self.assertEqual(package["source_unit"]["pdf_unit_type"], "pdf_page_text_unit")
            self.assertFalse(package["source_unit"]["ocr_vlm_used"])
            self.assertFalse(package["source_unit"]["page_rendering_used_for_extraction"])
            self.assertFalse(package["prompt_contract"]["model_call_performed"])
            self.assertFalse(package["privacy_policy"]["knowledge_rag_used"])
            self.assertFalse(package["privacy_policy"]["vectorization_performed"])

    def test_gate2_validates_shared_pdf_parent_once_per_audit_run(self):
        content = _pdf_bytes(
            pages=[
                ("text", ["Synthetic Broker Report", "Page one amount 10.00 USD"]),
                ("text", ["Synthetic Broker Report", "Page two amount 20.00 USD"]),
            ]
        )
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="pdf-parent-validation-cache",
                    filename="synthetic_parent_fanout.pdf",
                    content=content,
                    mime_type="application/pdf",
                )
            ],
            input_context={
                "clarification_criticality_refinement_enabled": True,
                "pdf_layout_slice2_enabled": False,
            },
        )
        self.assertEqual(result.package["validation_result"]["status"], "passed")
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
                user_id="pdf-parent-cache-user",
                normalization_run_id=run_id,
                case_id="pdf-parent-cache-case",
                chat_id="pdf-parent-cache-chat",
                workspace_model_id="pdf-parent-cache-model",
                allow_private=True,
                require_source_available=True,
            )
            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            records_before = [record.artifact_id for record in store.list_by_run(run_id)]
            service = Gate2InputReadinessFactory(store=store).create()
            dcp_ref = manifest.artifact_refs_by_type["domain_context_packet_v0"][0]

            first = service.audit_and_build(
                domain_context_packet_ref=dcp_ref,
                context=context,
            )
            second = service.audit_and_build(
                domain_context_packet_ref=dcp_ref,
                context=context,
            )

            for readiness in (first, second):
                audit = readiness.validation["slice_audit"]
                self.assertEqual(readiness.validation["validator_status"], "passed")
                self.assertEqual(audit["pdf_parent_payloads_resolved_total"], 1)
                self.assertEqual(audit["pdf_parent_full_validation_total"], 1)
                self.assertEqual(audit["pdf_parent_validation_cache_entries_total"], 1)
                self.assertEqual(audit["pdf_unit_parent_linkage_validation_total"], 2)
                self.assertEqual(audit["pdf_parent_validation_cache_hit_total"], 1)
                self.assertEqual(len(readiness.packages), 2)
                self.assertFalse(
                    readiness.safe_report["safety_flags"][
                        "source_fact_llm_call_performed"
                    ]
                )
            self.assertEqual(
                records_before,
                [record.artifact_id for record in store.list_by_run(run_id)],
            )

    @staticmethod
    def _build(content: bytes):
        return FullSourceArtifactFactory(
            FullSourceArtifactConfig(enable_pdf_layout_slice2=False)
        ).create().build(
            normalization_run_id="normrun_pdf_slice1",
            document_id="brdoc_pdf_slice1",
            profile_id="techprof_pdf_slice1",
            container_format="pdf",
            content_bytes=content,
            source_checksum_sha256="a" * 64,
        )


if __name__ == "__main__":
    unittest.main()
