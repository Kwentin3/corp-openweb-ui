from __future__ import annotations

import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    FullSourceArtifactConfig,
    FullSourceArtifactFactory,
    Gate1Normalizer,
    Gate2InputReadinessFactory,
    Gate2SourceUnitRouterFactory,
    Gate2SourceUnitSegmenterFactory,
    PDFMINER_PINNED_VERSION,
    PDFPLUMBER_PINNED_VERSION,
    PdfLayoutParserConfig,
    PdfParserCapabilityRequest,
    PdfTextLayerParserConfig,
    PdfTextLayerParserError,
    PdfTextLayerParserFactory,
    build_retention_policy,
    persist_gate1_result,
    resolve_pdf_layout_unit_source_value,
    validate_full_source_unit,
    validate_pdf_text_layer_payload,
)
from broker_reports_gate1.pdf_text_layer import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    resolve_pdf_payload_source_value,
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


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _add_layout_page(
    writer: PdfWriter,
    *,
    texts: list[tuple[float, float, str]],
    vector_commands: list[str] | None = None,
) -> None:
    page = writer.add_blank_page(width=320, height=320)
    font_ref = _font_resource(writer)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    operators = []
    for x, y, text in texts:
        operators.append(
            f"BT /F1 10 Tf {x:g} {y:g} Td ({_escape(text)}) Tj ET"
        )
    operators.extend(vector_commands or [])
    stream = DecodedStreamObject()
    stream.set_data("\n".join(operators).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)


def _pdf_bytes(
    pages: list[dict],
) -> bytes:
    writer = PdfWriter()
    for page in pages:
        if page.get("blank"):
            writer.add_blank_page(width=320, height=320)
        else:
            _add_layout_page(
                writer,
                texts=list(page.get("texts") or []),
                vector_commands=list(page.get("vectors") or []),
            )
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _paragraph_pdf() -> bytes:
    return _pdf_bytes(
        [
            {
                "texts": [
                    (20, 290, "Synthetic Broker Report"),
                    (20, 270, "Account summary for period"),
                    (20, 250, "Amount 10.00 USD"),
                    (20, 20, "Synthetic Footer"),
                ]
            },
            {"blank": True},
        ]
    )


def _multi_column_pdf() -> bytes:
    return _pdf_bytes(
        [
            {
                "texts": [
                    (180, 250, "Right column note"),
                    (20, 250, "Left column note"),
                ]
            }
        ]
    )


def _duplicate_text_pdf() -> bytes:
    return _pdf_bytes(
        [
            {
                "texts": [
                    (20, 250, "DUPLICATE"),
                    (20, 250, "DUPLICATE"),
                    (20, 220, "Visible line"),
                ]
            }
        ]
    )


def _ruled_table_pdf() -> bytes:
    texts = [
        (30, 260, "Synthetic Table"),
        (30, 220, "Date"),
        (125, 220, "Amount"),
        (225, 220, "Currency"),
        (30, 195, "2026-01-01"),
        (125, 195, "10.00"),
        (225, 195, "USD"),
        (30, 170, "2026-01-02"),
        (125, 170, "20.00"),
        (225, 170, "EUR"),
        (30, 130, "Outside table note"),
    ]
    vectors = [
        "20 155 m 300 155 l S",
        "20 180 m 300 180 l S",
        "20 205 m 300 205 l S",
        "20 230 m 300 230 l S",
        "20 155 m 20 230 l S",
        "110 155 m 110 230 l S",
        "210 155 m 210 230 l S",
        "300 155 m 300 230 l S",
    ]
    return _pdf_bytes([{"texts": texts, "vectors": vectors}])


def _aligned_table_pdf(*, ambiguous: bool = False) -> bytes:
    rows = [
        (250, "Date", "Amount", "Currency"),
        (225, "2026-01-01", "10.00", "USD"),
    ]
    if not ambiguous:
        rows.extend(
            [
                (200, "2026-01-02", "20.00", "EUR"),
                (175, "2026-01-03", "30.00", "GBP"),
            ]
        )
    texts = [
        item
        for y, left, middle, right in rows
        for item in ((25, y, left), (130, y, middle), (235, y, right))
    ]
    return _pdf_bytes([{"texts": texts}])


def _inventory_overflow_pdf() -> bytes:
    table_rows = [
        (250, "Date", "Amount", "Currency"),
        (225, "2026-01-01", "10.00", "USD"),
        (200, "2026-01-02", "20.00", "EUR"),
        (175, "2026-01-03", "30.00", "GBP"),
    ]
    table_texts = [
        item
        for y, left, middle, right in table_rows
        for item in ((25, y, left), (130, y, middle), (235, y, right))
    ]
    tail_texts = [
        (20, 300 - (index * 12), f"Tail inventory line {index:02d}")
        for index in range(1, 20)
    ]
    return _pdf_bytes([{"texts": table_texts}, {"texts": tail_texts}])


def _layout_inventory_objects(page: dict) -> int:
    return sum(
        len(page.get(key) or [])
        for key in (
            "char_inventory",
            "word_inventory",
            "line_inventory",
            "block_inventory",
            "vector_line_inventory",
            "rect_inventory",
            "table_candidate_inventory",
        )
    )


class BrokerReportsPdfLayoutSlice2Test(unittest.TestCase):
    def test_document_inventory_cap_default_remains_75000(self) -> None:
        self.assertEqual(
            75_000,
            PdfLayoutParserConfig().max_inventory_objects_per_document,
        )

    def test_factory_pins_layout_backend_and_never_downgrades(self):
        self.assertIn("PdfTextLayerParserFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not instantiate PypdfParserAdapter directly", FORBIDDEN)
        self.assertIn("PdfPlumberLayoutAdapter directly", FORBIDDEN)
        parser = PdfTextLayerParserFactory().create(
            PdfParserCapabilityRequest(capability="table_candidates")
        )
        self.assertEqual(parser.config.expected_pdfplumber_version, PDFPLUMBER_PINNED_VERSION)
        self.assertEqual(parser.config.expected_pdfminer_version, PDFMINER_PINNED_VERSION)
        with self.assertRaises(PdfTextLayerParserError) as version_error:
            PdfTextLayerParserFactory(
                PdfTextLayerParserConfig(
                    layout=PdfLayoutParserConfig(
                        expected_pdfplumber_version="0.0.0"
                    )
                )
            ).create(PdfParserCapabilityRequest(capability="layout_words"))
        self.assertEqual(
            version_error.exception.code,
            "pdf_layout_pdfplumber_version_mismatch",
        )

    def test_duplicate_chars_are_explicit_and_coverage_stays_exact(self):
        result = self._build(_duplicate_text_pdf())
        payload = result.payloads[0]
        projection = payload["pdf_text_layer_projection"]
        self.assertEqual(payload["layout_projection_status"], "partial")
        self.assertGreater(
            sum(page.get("duplicate_chars_total", 0) for page in projection["page_inventory"]),
            0,
        )
        self.assertTrue(
            any(item.get("duplicate_of_char_ref") for item in projection["char_inventory"])
        )
        self.assertFalse(projection["layout_coverage"]["all_selected_refs_accounted"])
        self.assertEqual(
            set(projection["layout_coverage"]["selected_source_refs"]),
            set(projection["layout_coverage"]["unaccounted_refs"]),
        )
        self.assertIn(
            "pdf_layout_word_page_text_mismatch",
            projection["page_inventory"][0]["layout_reason_codes"],
        )
        self.assertEqual(
            validate_pdf_text_layer_payload(payload)["validator_status"], "passed"
        )

    def test_words_lines_geometry_refs_checksums_and_coverage_are_stable(self):
        first = self._build(_paragraph_pdf())
        second = self._build(_paragraph_pdf())
        self.assertEqual(first.summary["parser_completeness_status"], "complete")
        self.assertEqual(first.summary["pdf_layout_projection_status"], "complete")
        self.assertEqual(first.summary["pdf_layout_complete_pages"], 2)
        self.assertGreater(first.summary["pdf_layout_words_total"], 0)
        self.assertGreater(first.summary["pdf_layout_lines_total"], 0)
        self.assertTrue(first.units)
        self.assertEqual(
            {unit["pdf_unit_type"] for unit in first.units},
            {"pdf_line_cluster_unit", "pdf_visual_page_unit"},
        )

        payload = first.payloads[0]
        second_payload = second.payloads[0]
        projection = payload["pdf_text_layer_projection"]
        self.assertEqual(projection["layout_parser_engine"], "pdfplumber")
        self.assertEqual(
            projection["layout_parser_engine_version"], PDFPLUMBER_PINNED_VERSION
        )
        self.assertEqual(
            projection["layout_underlying_engine_version"], PDFMINER_PINNED_VERSION
        )
        self.assertEqual(
            projection["layout_page_checksum_refs"],
            second_payload["pdf_text_layer_projection"]["layout_page_checksum_refs"],
        )
        self.assertEqual(payload["payload_checksum_ref"], second_payload["payload_checksum_ref"])
        self.assertEqual(
            [item["word_ref"] for item in projection["word_inventory"]],
            [
                item["word_ref"]
                for item in second_payload["pdf_text_layer_projection"]["word_inventory"]
            ],
        )
        self.assertEqual(
            projection["layout_coverage"]["selected_source_refs"],
            projection["layout_coverage"]["accounted_source_refs"],
        )
        self.assertTrue(projection["layout_coverage"]["all_selected_refs_accounted"])
        self.assertEqual(
            validate_pdf_text_layer_payload(payload)["validator_status"], "passed"
        )
        for entry in payload["source_value_index"]:
            if (entry.get("value_path") or {}).get("kind") in {
                "pdf_layout_word_text",
                "pdf_layout_line_text",
            }:
                self.assertIsInstance(resolve_pdf_payload_source_value(payload, entry), str)
        for unit in first.units:
            self.assertEqual(
                validate_full_source_unit(
                    unit=unit,
                    normalization_run_id="normrun_pdf_layout_slice2",
                    document_id="brdoc_pdf_layout_slice2",
                    source_checksum_sha256="d" * 64,
                )["validator_status"],
                "passed",
            )
            for ref in unit.get("pdf_layout_source_value_refs", []):
                self.assertIsInstance(resolve_pdf_layout_unit_source_value(unit, ref), str)
            self.assertFalse(unit["ocr_vlm_used"])
            self.assertEqual(
                unit["page_rendering_used_for_extraction"],
                unit["pdf_unit_type"] == "pdf_visual_page_unit",
            )

    def test_ruled_and_aligned_candidates_are_non_semantic_and_ambiguous_falls_back(self):
        ruled = self._build(_ruled_table_pdf())
        ruled_payload = ruled.payloads[0]
        table_units = [
            unit
            for unit in ruled.units
            if unit.get("pdf_unit_type") == "pdf_table_candidate_unit"
        ]
        self.assertTrue(table_units)
        self.assertEqual(ruled.summary["pdf_table_candidate_status"], "candidate")
        self.assertTrue(
            any(
                item.get("table_strategy_ref") == "ruled_lines_v0"
                for item in ruled_payload["pdf_text_layer_projection"][
                    "table_candidate_inventory"
                ]
            )
        )
        for unit in table_units:
            self.assertEqual(unit["table_reconstruction_status"], "candidate")
            self.assertFalse(unit["semantic_table_truth_claimed"])
            self.assertTrue(unit["table_fallback_text_refs"])
            self.assertTrue(unit["table_contributing_word_refs"])
            self.assertEqual(
                len(unit["pdf_layout_coverage"]["accounted_source_refs"]),
                len(set(unit["pdf_layout_coverage"]["accounted_source_refs"])),
            )

        aligned = self._build(_aligned_table_pdf())
        self.assertTrue(
            any(
                item.get("table_strategy_ref") == "aligned_text_v0"
                for item in aligned.payloads[0]["pdf_text_layer_projection"][
                    "table_candidate_inventory"
                ]
            )
        )
        ambiguous = self._build(_aligned_table_pdf(ambiguous=True))
        self.assertFalse(
            any(
                unit.get("pdf_unit_type") == "pdf_table_candidate_unit"
                for unit in ambiguous.units
            )
        )
        self.assertTrue(
            all(
                unit.get("pdf_unit_type") == "pdf_line_cluster_unit"
                for unit in ambiguous.units
            )
        )

    def test_layout_and_unit_budgets_fail_partial_without_weakening_page_text(self):
        content = _paragraph_pdf()
        word_budget = FullSourceArtifactFactory(
            FullSourceArtifactConfig(max_pdf_layout_words_per_page=1)
        ).create().build(
            normalization_run_id="normrun_pdf_layout_budget",
            document_id="brdoc_pdf_layout_budget",
            profile_id="techprof_pdf_layout_budget",
            container_format="pdf",
            content_bytes=content,
            source_checksum_sha256="e" * 64,
        )
        self.assertEqual(word_budget.summary["parser_completeness_status"], "complete")
        self.assertEqual(word_budget.summary["pdf_text_layer_projection_status"], "complete")
        self.assertEqual(word_budget.summary["pdf_layout_projection_status"], "partial")
        self.assertEqual(
            {unit["pdf_unit_type"] for unit in word_budget.units},
            {"pdf_page_text_unit", "pdf_visual_page_unit"},
        )
        self.assertIn(
            "pdf_layout_word_budget_exceeded",
            word_budget.payloads[0]["pdf_text_layer_projection"]["layout_reason_codes"],
        )
        self.assertEqual(
            validate_pdf_text_layer_payload(word_budget.payloads[0])["validator_status"],
            "passed",
        )

        cluster_budget = FullSourceArtifactFactory(
            FullSourceArtifactConfig(max_pdf_layout_characters_per_cluster=5)
        ).create().build(
            normalization_run_id="normrun_pdf_layout_cluster_budget",
            document_id="brdoc_pdf_layout_cluster_budget",
            profile_id="techprof_pdf_layout_cluster_budget",
            container_format="pdf",
            content_bytes=content,
            source_checksum_sha256="f" * 64,
        )
        self.assertEqual(cluster_budget.summary["parser_completeness_status"], "complete")
        self.assertEqual(cluster_budget.summary["pdf_layout_projection_status"], "partial")
        self.assertIn(
            "pdf_line_cluster_single_line_budget_exceeded",
            cluster_budget.payloads[0]["pdf_text_layer_projection"]["layout_reason_codes"],
        )
        self.assertEqual(
            {unit["pdf_unit_type"] for unit in cluster_budget.units},
            {"pdf_page_text_unit", "pdf_visual_page_unit"},
        )

    def test_document_inventory_overflow_preserves_completed_prefix_and_accounts_tail(self):
        content = _inventory_overflow_pdf()
        request = PdfParserCapabilityRequest(capability="table_candidates")
        baseline = PdfTextLayerParserFactory().create(request).parse(content)
        first_page_objects = _layout_inventory_objects(baseline.pages[0])
        second_page_objects = _layout_inventory_objects(baseline.pages[1])
        first_page_candidates = baseline.pages[0]["table_candidate_inventory"]
        self.assertGreater(first_page_objects, 0)
        self.assertGreater(second_page_objects, 0)
        self.assertTrue(first_page_candidates)

        limited_parser = PdfTextLayerParserFactory(
            PdfTextLayerParserConfig(
                layout=PdfLayoutParserConfig(
                    max_inventory_objects_per_document=first_page_objects
                )
            )
        ).create(request)
        limited = limited_parser.parse(content)

        self.assertEqual("partial", limited.layout_projection_status)
        self.assertIn(
            "pdf_layout_document_inventory_budget_exceeded",
            limited.layout_reason_codes,
        )
        self.assertEqual(2, len(limited.pages))
        self.assertEqual(
            first_page_candidates,
            limited.pages[0]["table_candidate_inventory"],
        )
        self.assertEqual([], limited.pages[1]["table_candidate_inventory"])
        self.assertIn(
            "pdf_layout_page_not_processed_document_inventory_budget",
            limited.pages[1]["layout_reason_codes"],
        )
        self.assertEqual(
            {
                "source_pages_total": 2,
                "completed_pages_total": 1,
                "missing_tail_pages_total": 1,
                "first_missing_page_number": 2,
                "inventory_objects_retained_total": first_page_objects,
                "inventory_objects_would_be_total": first_page_objects + second_page_objects,
                "inventory_objects_limit": first_page_objects,
            },
            {
                key: limited.diagnostics[key]
                for key in (
                    "source_pages_total",
                    "completed_pages_total",
                    "missing_tail_pages_total",
                    "first_missing_page_number",
                    "inventory_objects_retained_total",
                    "inventory_objects_would_be_total",
                    "inventory_objects_limit",
                )
            },
        )

        result = FullSourceArtifactFactory(
            FullSourceArtifactConfig(
                max_pdf_layout_inventory_objects_per_document=first_page_objects
            )
        ).create().build(
            normalization_run_id="normrun_pdf_layout_inventory_overflow",
            document_id="brdoc_pdf_layout_inventory_overflow",
            profile_id="techprof_pdf_layout_inventory_overflow",
            container_format="pdf",
            content_bytes=content,
            source_checksum_sha256="a" * 64,
        )
        payload = result.payloads[0]
        projection = payload["pdf_text_layer_projection"]
        retained_candidates = projection["table_candidate_inventory"]
        retained_word_refs = {
            item["word_ref"] for item in projection["word_inventory"]
        }
        self.assertEqual("partial", projection["layout_projection_status"])
        self.assertTrue(retained_candidates)
        self.assertTrue(
            all(
                set(candidate["contributing_word_refs"]) <= retained_word_refs
                for candidate in retained_candidates
            )
        )
        self.assertIn(
            "pdf_layout_page_not_processed_document_inventory_budget",
            projection["page_inventory"][1]["layout_reason_codes"],
        )
        self.assertEqual(
            1,
            projection["layout_parser_diagnostics"]["completed_pages_total"],
        )
        self.assertEqual(
            1,
            projection["layout_parser_diagnostics"]["missing_tail_pages_total"],
        )
        self.assertEqual(
            {"pdf_page_text_unit"},
            {unit["pdf_unit_type"] for unit in result.units},
        )
        self.assertFalse(projection["ocr_vlm_used"])
        self.assertFalse(projection["page_rendering_used_for_extraction"])
        self.assertEqual(
            "passed", validate_pdf_text_layer_payload(payload)["validator_status"]
        )

    def test_multi_column_geometry_order_reconciles_through_page_local_word_refs(self):
        result = self._build(_multi_column_pdf())
        self.assertEqual(result.summary["parser_completeness_status"], "complete")
        self.assertEqual(result.summary["pdf_layout_projection_status"], "complete")
        projection = result.payloads[0]["pdf_text_layer_projection"]
        self.assertTrue(
            any(
                line.get("canonical_page_text_match_status")
                == "resolved_via_word_refs"
                for line in projection["line_inventory"]
            )
        )
        self.assertEqual(
            {unit["pdf_unit_type"] for unit in result.units},
            {"pdf_line_cluster_unit"},
        )

    def test_artifactstore_gate2_router_and_segmenter_accept_bounded_layout_unit(self):
        result = Gate1Normalizer().normalize(
            [
                FileInput.from_bytes(
                    private_ref="pdf-layout-slice2",
                    filename="synthetic_layout.pdf",
                    content=_paragraph_pdf(),
                    mime_type="application/pdf",
                )
            ],
            input_context={"clarification_criticality_refinement_enabled": True},
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
                user_id="pdf-layout-user",
                normalization_run_id=run_id,
                case_id="pdf-layout-case",
                chat_id="pdf-layout-chat",
                workspace_model_id="pdf-layout-model",
                allow_private=True,
                require_source_available=True,
            )
            manifest = persist_gate1_result(
                store=store,
                result=result,
                context=context,
                retention_policy=build_retention_policy(mode="api_smoke"),
            )
            before = [record.artifact_id for record in store.list_by_run(run_id)]
            readiness = Gate2InputReadinessFactory(store=store).create().audit_and_build(
                domain_context_packet_ref=manifest.artifact_refs_by_type[
                    "domain_context_packet_v0"
                ][0],
                context=context,
            )
            after = [record.artifact_id for record in store.list_by_run(run_id)]
            self.assertEqual(readiness.validation["validator_status"], "passed")
            self.assertEqual(before, after)
            self.assertEqual(readiness.validation["knowledge_records"], 0)
            self.assertTrue(readiness.packages)
            package = readiness.packages[0]
            source_unit = package["source_unit"]
            self.assertEqual(source_unit["unit_kind"], "pdf_line_cluster")
            self.assertEqual(source_unit["pdf_unit_type"], "pdf_line_cluster_unit")
            self.assertTrue(source_unit["pdf_layout_source_value_refs"])
            self.assertTrue(source_unit["pdf_layout_coverage"])
            self.assertFalse(package["prompt_contract"]["model_call_performed"])
            self.assertFalse(package["privacy_policy"]["knowledge_rag_used"])
            self.assertFalse(package["privacy_policy"]["vectorization_performed"])
            route = Gate2SourceUnitRouterFactory().create().route(package)
            self.assertTrue(route["coverage"]["all_selected_refs_routed"])
            segmentation = Gate2SourceUnitSegmenterFactory().create().segment(
                base_package=package,
                parent_route=route,
            )
            self.assertTrue(
                segmentation.plan["coverage"]["all_parent_selected_refs_partitioned"]
            )
            self.assertTrue(segmentation.derived_packages)
            self.assertTrue(
                all(
                    derived["source_unit"]["unit_kind"] == "pdf_line_cluster"
                    for derived in segmentation.derived_packages
                )
            )
            self.assertFalse(
                any(
                    record.storage_backend == "openwebui_knowledge"
                    for record in store.list_by_run(run_id)
                )
            )

    @staticmethod
    def _build(content: bytes):
        return FullSourceArtifactFactory().create().build(
            normalization_run_id="normrun_pdf_layout_slice2",
            document_id="brdoc_pdf_layout_slice2",
            profile_id="techprof_pdf_layout_slice2",
            container_format="pdf",
            content_bytes=content,
            source_checksum_sha256="d" * 64,
        )


if __name__ == "__main__":
    unittest.main()
