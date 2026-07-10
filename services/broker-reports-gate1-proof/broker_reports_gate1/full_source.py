from __future__ import annotations

import copy
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO, StringIO
from pathlib import PurePosixPath
from typing import Any
from zipfile import BadZipFile, ZipFile

from .contracts import stable_digest
from .pdf_text_layer import (
    PDF_TEXT_LAYER_COVERAGE_SCHEMA_VERSION,
    PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION,
    PDF_PARSER_POLICY_VERSION,
    PYPDF_PINNED_VERSION,
    PdfParserCapabilityRequest,
    PdfTextLayerParserConfig,
    PdfTextLayerParserError,
    PdfTextLayerParserFactory,
    pdf_page_checksum_ref,
    pdf_payload_checksum_ref,
    validate_pdf_source_unit,
    validate_pdf_text_layer_payload,
)
from .profilers_csv_txt import decode_text_bytes
from .source_provenance import NormalizedSliceProvenanceFactory


FACTORY_REQUIRED = (
    "FullSourceArtifactFactory.create is the only production full-source payload and unit entrypoint"
)
FORBIDDEN = (
    "Profilers, Gate 2 callers and smoke scripts must not mint extraction-grade full-source refs directly"
)

SOURCE_PAYLOAD_SCHEMA_VERSION = "private_normalized_source_payload_v0"
SOURCE_UNIT_SCHEMA_VERSION = "private_normalized_source_unit_v0"
PARSER_COMPLETENESS_STATUSES = {"complete", "partial", "blocked"}


@dataclass(frozen=True)
class FullSourceArtifactConfig:
    max_rows_per_logical_unit: int = 10_000
    max_cells_per_logical_unit: int = 100_000
    max_text_characters_per_logical_unit: int = 200_000
    max_zip_member_bytes: int = 5_000_000
    max_pdf_document_bytes: int = 50_000_000
    max_pdf_pages: int = 2_000
    max_pdf_page_content_stream_bytes: int = 10_000_000
    expected_pypdf_version: str = PYPDF_PINNED_VERSION


@dataclass(frozen=True)
class FullSourceBuildResult:
    payloads: list[dict[str, Any]]
    units: list[dict[str, Any]]
    summary: dict[str, Any]


class FullSourceArtifactFactory:
    def __init__(self, config: FullSourceArtifactConfig | None = None) -> None:
        self.config = config or FullSourceArtifactConfig()

    def create(self) -> "FullSourceArtifactBuilder":
        if self.config.max_rows_per_logical_unit <= 0:
            raise ValueError("full_source_row_budget_invalid")
        if self.config.max_cells_per_logical_unit <= 0:
            raise ValueError("full_source_cell_budget_invalid")
        if self.config.max_text_characters_per_logical_unit <= 0:
            raise ValueError("full_source_text_budget_invalid")
        if self.config.max_zip_member_bytes <= 0:
            raise ValueError("full_source_zip_member_budget_invalid")
        if self.config.max_pdf_document_bytes <= 0:
            raise ValueError("full_source_pdf_document_budget_invalid")
        if self.config.max_pdf_pages <= 0:
            raise ValueError("full_source_pdf_page_budget_invalid")
        if self.config.max_pdf_page_content_stream_bytes <= 0:
            raise ValueError("full_source_pdf_page_stream_budget_invalid")
        if not self.config.expected_pypdf_version:
            raise ValueError("full_source_pypdf_version_required")
        return FullSourceArtifactBuilder(self.config)


class FullSourceArtifactBuilder:
    def __init__(self, config: FullSourceArtifactConfig) -> None:
        self.config = config
        self.provenance = NormalizedSliceProvenanceFactory().create()
        self.pdf_parser_factory = PdfTextLayerParserFactory(
            PdfTextLayerParserConfig(
                expected_pypdf_version=config.expected_pypdf_version,
                max_document_bytes=config.max_pdf_document_bytes,
                max_pages=config.max_pdf_pages,
                max_page_content_stream_bytes=config.max_pdf_page_content_stream_bytes,
                max_page_text_characters=config.max_text_characters_per_logical_unit,
            )
        )

    def build(
        self,
        *,
        normalization_run_id: str,
        document_id: str,
        profile_id: str,
        container_format: str,
        content_bytes: bytes,
        source_checksum_sha256: str,
    ) -> FullSourceBuildResult:
        if not normalization_run_id or not document_id or not source_checksum_sha256:
            raise ValueError("full_source_scope_required")
        if container_format == "pdf":
            return self._build_pdf_document(
                normalization_run_id=normalization_run_id,
                document_id=document_id,
                profile_id=profile_id,
                content_bytes=content_bytes,
                source_checksum_sha256=source_checksum_sha256,
            )
        descriptors, document_reasons = self._extract(
            container_format=container_format,
            content_bytes=content_bytes,
            document_id=document_id,
        )
        payloads: list[dict[str, Any]] = []
        units: list[dict[str, Any]] = []
        for ordinal, descriptor in enumerate(descriptors, start=1):
            payload, unit = self._build_descriptor(
                normalization_run_id=normalization_run_id,
                document_id=document_id,
                profile_id=profile_id,
                source_checksum_sha256=source_checksum_sha256,
                container_format=container_format,
                ordinal=ordinal,
                descriptor=descriptor,
            )
            payloads.append(payload)
            if unit is not None:
                units.append(unit)

        unit_refs = [str(item["unit_ref"]) for item in units]
        for index, unit in enumerate(units):
            unit["remaining_unit_refs"] = unit_refs[index + 1 :]
            unit["next_unit_refs"] = unit_refs[index + 1 : index + 2]
        units_by_payload = {str(item["parent_payload_ref"]): item for item in units}
        for payload in payloads:
            unit = units_by_payload.get(str(payload["source_payload_ref"]))
            payload["extraction_unit_refs"] = [unit["unit_ref"]] if unit else []
            if unit:
                payload["row_inventory"] = copy.deepcopy(unit.get("row_provenance") or [])
                payload["cell_inventory"] = copy.deepcopy(unit.get("cell_provenance") or [])
                payload["text_segment_inventory"] = copy.deepcopy(
                    unit.get("segment_provenance") or []
                )
                payload["source_value_index"] = copy.deepcopy(
                    unit.get("source_value_index") or []
                )
                payload["coverage_index"] = copy.deepcopy(unit.get("coverage") or {})

        statuses = [str(item.get("parser_completeness_status") or "blocked") for item in payloads]
        if payloads and statuses and all(status == "complete" for status in statuses):
            document_status = "complete"
        elif payloads and any(status in {"complete", "partial"} for status in statuses):
            document_status = "partial"
        else:
            document_status = "blocked"
        reasons = sorted(
            {
                *document_reasons,
                *(
                    reason
                    for payload in payloads
                    for reason in payload.get("parser_completeness_reason_codes") or []
                ),
            }
        )
        summary = {
            "schema_version": "full_source_coverage_summary_v0",
            "document_ref": document_id,
            "container_format": container_format,
            "parser_completeness_status": document_status,
            "parser_completeness_reason_codes": reasons,
            "payloads_total": len(payloads),
            "extraction_units_total": len(units),
            "rows_total": sum(int(item.get("rows_total") or 0) for item in payloads),
            "cells_total": sum(int(item.get("cells_total") or 0) for item in payloads),
            "text_characters_total": sum(
                int(item.get("text_characters_total") or 0) for item in payloads
            ),
            "text_segments_total": sum(
                len(item.get("text_segment_inventory") or []) for item in payloads
            ),
            "full_coverage_available": document_status == "complete" and bool(units),
            "preview_artifacts_are_coverage_authority": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        }
        return FullSourceBuildResult(payloads=payloads, units=units, summary=summary)

    def _extract(
        self, *, container_format: str, content_bytes: bytes, document_id: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if container_format == "csv":
            return self._extract_csv(content_bytes), []
        if container_format == "txt":
            return self._extract_text(content_bytes), []
        if container_format == "html_text":
            return self._extract_html(content_bytes), []
        if container_format == "xlsx":
            return self._extract_xlsx(content_bytes, document_id)
        if container_format == "docx":
            return self._extract_docx(content_bytes)
        if container_format == "pdf":
            return self._extract_pdf(content_bytes)
        return [], ["format_not_supported_for_full_source"]

    def _extract_csv(self, content_bytes: bytes) -> list[dict[str, Any]]:
        decoded, encoding, error = decode_text_bytes(content_bytes)
        if decoded is None:
            return [self._blocked_descriptor("table_rows", "python_stdlib_csv", error or "decode_failed")]
        try:
            delimiter = _detect_delimiter(decoded)
            rows = list(csv.reader(StringIO(decoded), delimiter=delimiter))
        except csv.Error:
            return [self._blocked_descriptor("table_rows", "python_stdlib_csv", "csv_parse_failed")]
        return [
            {
                "logical_identity": "csv_table_001",
                "slice_type": "table_rows",
                "parser": "python_stdlib_csv",
                "parser_version": "1",
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "source_location": {
                    "kind": "csv_rows",
                    "start_row": 1 if rows else 0,
                    "end_row": len(rows),
                    "encoding": encoding,
                },
                "cells": rows,
            }
        ]

    def _extract_text(self, content_bytes: bytes) -> list[dict[str, Any]]:
        decoded, encoding, error = decode_text_bytes(content_bytes)
        if decoded is None:
            return [self._blocked_descriptor("text_excerpt", "python_text_decode", error or "decode_failed")]
        return [
            {
                "logical_identity": "plain_text_001",
                "slice_type": "text_excerpt",
                "parser": "python_text_decode",
                "parser_version": "1",
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "source_location": {
                    "kind": "text_characters",
                    "character_start": 0,
                    "character_end": len(decoded),
                    "encoding": encoding,
                },
                "text": decoded,
            }
        ]

    def _extract_html(self, content_bytes: bytes) -> list[dict[str, Any]]:
        decoded, encoding, error = decode_text_bytes(content_bytes)
        if decoded is None:
            return [self._blocked_descriptor("text_excerpt", "python_html_text_decode", error or "decode_failed")]
        parser = _FullHtmlExtractor()
        try:
            parser.feed(decoded)
            parser.close()
        except Exception:
            return [self._blocked_descriptor("text_excerpt", "python_html_text_decode", "html_parse_failed")]
        descriptors: list[dict[str, Any]] = []
        outside_text = parser.outside_text()
        if outside_text:
            descriptors.append(
                {
                    "logical_identity": "html_outside_table_text_001",
                    "slice_type": "text_excerpt",
                    "parser": "python_html_text_decode",
                    "parser_version": "1",
                    "parser_completeness_status": "complete",
                    "parser_completeness_reason_codes": [],
                    "source_location": {
                        "kind": "html_outside_table_text",
                        "character_start": 0,
                        "character_end": len(outside_text),
                        "encoding": encoding,
                    },
                    "text": outside_text,
                }
            )
        for table_index, rows in enumerate(parser.tables, start=1):
            descriptors.append(
                {
                    "logical_identity": f"html_table_{table_index:03d}",
                    "slice_type": "table_rows",
                    "parser": "python_html_table_decode",
                    "parser_version": "1",
                    "parser_completeness_status": "complete",
                    "parser_completeness_reason_codes": [],
                    "source_location": {
                        "kind": "html_table_rows",
                        "table_ordinal": table_index,
                        "start_row": 1 if rows else 0,
                        "end_row": len(rows),
                        "encoding": encoding,
                    },
                    "cells": rows,
                }
            )
        if not descriptors:
            descriptors.append(
                {
                    "logical_identity": "html_text_001",
                    "slice_type": "text_excerpt",
                    "parser": "python_html_text_decode",
                    "parser_version": "1",
                    "parser_completeness_status": "complete",
                    "parser_completeness_reason_codes": [],
                    "source_location": {
                        "kind": "html_text",
                        "character_start": 0,
                        "character_end": 0,
                        "encoding": encoding,
                    },
                    "text": "",
                }
            )
        return descriptors

    def _extract_xlsx(
        self, content_bytes: bytes, document_id: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        try:
            archive = ZipFile(BytesIO(content_bytes))
        except BadZipFile:
            return [self._blocked_descriptor("table_rows", "python_stdlib_xlsx_zip_xml", "bad_xlsx_zip")], []
        with archive:
            oversized = {
                info.filename
                for info in archive.infolist()
                if info.file_size > self.config.max_zip_member_bytes
            }
            if "xl/workbook.xml" in oversized:
                return [self._blocked_descriptor("table_rows", "python_stdlib_xlsx_zip_xml", "xlsx_workbook_member_too_large")], []
            try:
                workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
                relationships = _xlsx_relationships(archive)
                shared_strings = _xlsx_shared_strings(
                    archive,
                    max_member_bytes=self.config.max_zip_member_bytes,
                )
            except (KeyError, ET.ParseError, ValueError):
                return [self._blocked_descriptor("table_rows", "python_stdlib_xlsx_zip_xml", "xlsx_structure_invalid")], []
            descriptors: list[dict[str, Any]] = []
            document_reasons: list[str] = []
            for sheet_index, sheet in enumerate(_iter_local(workbook_root, "sheet"), start=1):
                rel_id = sheet.attrib.get(_rel_attr("id"))
                target = relationships.get(rel_id or "")
                path = _sheet_target_path(target)
                safe_sheet_id = f"xlsheet_{stable_digest([document_id, sheet_index, sheet.attrib.get('name')], length=12)}"
                if not path or path not in archive.namelist():
                    descriptors.append(
                        self._blocked_descriptor(
                            "table_rows",
                            "python_stdlib_xlsx_zip_xml",
                            "xlsx_sheet_missing",
                            logical_identity=f"xlsx_sheet_{sheet_index:03d}",
                        )
                    )
                    document_reasons.append("xlsx_sheet_missing")
                    continue
                if path in oversized:
                    descriptors.append(
                        self._blocked_descriptor(
                            "table_rows",
                            "python_stdlib_xlsx_zip_xml",
                            "xlsx_sheet_member_too_large",
                            logical_identity=f"xlsx_sheet_{sheet_index:03d}",
                        )
                    )
                    document_reasons.append("xlsx_sheet_member_too_large")
                    continue
                try:
                    root = ET.fromstring(archive.read(path))
                except ET.ParseError:
                    descriptors.append(
                        self._blocked_descriptor(
                            "table_rows",
                            "python_stdlib_xlsx_zip_xml",
                            "xlsx_sheet_xml_invalid",
                            logical_identity=f"xlsx_sheet_{sheet_index:03d}",
                        )
                    )
                    document_reasons.append("xlsx_sheet_xml_invalid")
                    continue
                rows, formulas_count = _xlsx_rows_with_coordinates(root, shared_strings)
                status = "partial" if formulas_count else "complete"
                reasons = ["xlsx_formulas_not_extraction_complete"] if formulas_count else []
                descriptors.append(
                    {
                        "logical_identity": f"xlsx_sheet_{sheet_index:03d}",
                        "slice_type": "table_rows",
                        "parser": "python_stdlib_xlsx_zip_xml",
                        "parser_version": "1",
                        "parser_completeness_status": status,
                        "parser_completeness_reason_codes": reasons,
                        "source_location": {
                            "kind": "xlsx_sheet_rows",
                            "safe_sheet_id": safe_sheet_id,
                            "sheet_index": sheet_index,
                            "sheet_visibility": sheet.attrib.get("state", "visible"),
                            "row_start": 1 if rows else 0,
                            "row_end": len(rows),
                            "column_start": 1 if rows else 0,
                            "column_end": max((len(row) for row in rows), default=0),
                        },
                        "cells": rows,
                    }
                )
                document_reasons.extend(reasons)
            return descriptors, document_reasons

    def _extract_docx(self, content_bytes: bytes) -> tuple[list[dict[str, Any]], list[str]]:
        try:
            with ZipFile(BytesIO(content_bytes)) as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
                extra_parts = [
                    name
                    for name in archive.namelist()
                    if re.fullmatch(r"word/(?:header|footer)\d+\.xml", name)
                    or name in {"word/footnotes.xml", "word/endnotes.xml", "word/comments.xml"}
                ]
        except (BadZipFile, KeyError, ET.ParseError):
            return [self._blocked_descriptor("text_excerpt", "python_stdlib_docx_zip_xml", "docx_structure_invalid")], []
        paragraphs = []
        for paragraph in _iter_local(root, "p"):
            text = "".join(node.text or "" for node in _iter_local(paragraph, "t")).strip()
            if text:
                paragraphs.append(text)
        tables_count = sum(1 for _ in _iter_local(root, "tbl"))
        reasons = ["docx_structure_projection_not_complete"]
        if tables_count:
            reasons.append("docx_tables_not_structurally_extracted")
        if extra_parts:
            reasons.append("docx_auxiliary_parts_not_extracted")
        descriptor = {
            "logical_identity": "docx_body_text_001",
            "slice_type": "text_excerpt",
            "parser": "python_stdlib_docx_zip_xml",
            "parser_version": "1",
            "parser_completeness_status": "partial",
            "parser_completeness_reason_codes": sorted(set(reasons)),
            "source_location": {
                "kind": "docx_body_paragraph_projection",
                "paragraph_start": 1 if paragraphs else 0,
                "paragraph_end": len(paragraphs),
            },
            "text": "\n".join(paragraphs),
        }
        return [descriptor], sorted(set(reasons))

    def _build_pdf_document(
        self,
        *,
        normalization_run_id: str,
        document_id: str,
        profile_id: str,
        content_bytes: bytes,
        source_checksum_sha256: str,
    ) -> FullSourceBuildResult:
        logical_identity = "pdf_text_layer_001"
        source_checksum_ref = (
            f"srcsum_{stable_digest([document_id, source_checksum_sha256], length=24)}"
        )
        payload_ref = (
            "srcpayload_"
            + stable_digest(
                [
                    normalization_run_id,
                    document_id,
                    logical_identity,
                    source_checksum_sha256,
                ],
                length=24,
            )
        )
        try:
            parser = self.pdf_parser_factory.create(
                PdfParserCapabilityRequest(capability="page_text")
            )
            parsed = parser.parse(content_bytes)
            parser_engine = parsed.parser_engine
            parser_version = parsed.parser_engine_version
            parser_config_ref = parsed.parser_config_ref
            status = parsed.parser_completeness_status
            reasons = list(parsed.parser_completeness_reason_codes)
            pdf_content_kind = parsed.pdf_content_kind
            text_layer_status = parsed.text_layer_projection_status
            visible_content_status = parsed.visible_content_coverage_status
            semantic_status = parsed.semantic_reconstruction_status
            parsed_pages = copy.deepcopy(parsed.pages)
            parser_diagnostics = copy.deepcopy(parsed.diagnostics)
        except PdfTextLayerParserError as exc:
            parser_engine = "pypdf"
            parser_version = self.config.expected_pypdf_version
            parser_config_ref = self.pdf_parser_factory.config.config_ref
            status = exc.status
            reasons = [exc.code]
            pdf_content_kind = "parser_partial_pdf"
            text_layer_status = exc.status
            visible_content_status = "unknown"
            semantic_status = "not_claimed"
            parsed_pages = []
            parser_diagnostics = {
                "pages_total": 0,
                "pages_with_text": 0,
                "pages_without_text": 0,
                "pages_with_images": 0,
                "mixed_text_image_pages": 0,
                "page_parse_errors": 0,
                "text_fragments_total": 0,
                "text_characters_total": 0,
                "replacement_characters_total": 0,
                "unknown_font_fragments_total": 0,
            }

        parser_label = f"pypdf_page_text_{parser_version.replace('.', '_')}"
        parser_ref = f"parser_{stable_digest([parser_label, profile_id], length=20)}"
        page_inventory: list[dict[str, Any]] = []
        provisional_units: list[dict[str, Any]] = []
        text_segment_inventory: list[dict[str, Any]] = []
        text_fragment_inventory: list[dict[str, Any]] = []
        payload_source_value_refs: list[str] = []
        payload_source_value_index: list[dict[str, Any]] = []

        for parsed_page in parsed_pages:
            page_number = int(parsed_page.get("page_number") or 0)
            page_ref = f"page_{stable_digest((source_checksum_ref, page_number), length=20)}"
            page = copy.deepcopy(parsed_page)
            page["page_ref"] = page_ref
            page["parser_stream_order_refs"] = []
            page["geometry_reading_order_refs"] = []
            for fragment in page.get("parser_fragments") or []:
                fragment_ref = f"pdftextfrag_{stable_digest([page_ref, fragment.get('parser_ordinal'), fragment.get('raw_text_checksum_ref')], length=24)}"
                fragment["text_fragment_ref"] = fragment_ref
                fragment["page_ref"] = page_ref
                page["parser_stream_order_refs"].append(fragment_ref)
                text_fragment_inventory.append(copy.deepcopy(fragment))
            page["text_fragment_refs"] = list(page["parser_stream_order_refs"])

            text = str(page.get("text") or "")
            if text:
                source_location = {
                    "kind": "pdf_page_text",
                    "page": page_number,
                    "page_start": page_number,
                    "page_end": page_number,
                    "character_start": 0,
                    "character_end": len(text),
                }
                slice_id = f"fullsrc_{stable_digest([payload_ref, page_ref], length=24)}"
                private_slice = {
                    "slice_id": slice_id,
                    "document_id": document_id,
                    "profile_id": profile_id,
                    "slice_type": "text_excerpt",
                    "source_location": source_location,
                    "location": copy.deepcopy(source_location),
                    "bounded": True,
                    "truncated": False,
                    "parser": parser_label,
                    "created_for_gate": "gate1_pdf_text_layer_slice1",
                    "characters_in_slice": len(text),
                    "chars_count": len(text),
                    "text": text,
                }
                unit = self.provenance.enrich_slice(
                    normalization_run_id=normalization_run_id,
                    document_id=document_id,
                    source_checksum_sha256=source_checksum_sha256,
                    private_slice=private_slice,
                )
                page["text_segment_refs"] = list(unit.get("text_segment_refs") or [])
                page["section_refs"] = list(unit.get("section_refs") or [])
                page["character_span_refs"] = list(
                    unit.get("character_span_refs") or []
                )
                page["source_value_refs"] = list(unit.get("source_value_refs") or [])
                page["segment_provenance"] = copy.deepcopy(
                    unit.get("segment_provenance") or []
                )
                text_segment_inventory.extend(
                    copy.deepcopy(unit.get("segment_provenance") or [])
                )
                payload_source_value_refs.extend(page["source_value_refs"])
                for entry in unit.get("source_value_index") or []:
                    rebased = copy.deepcopy(entry)
                    span = rebased.get("value_path") or {}
                    rebased["value_path"] = {
                        "kind": "pdf_page_text_span",
                        "page_number": page_number,
                        "character_start": int(span.get("character_start") or 0),
                        "character_end": int(span.get("character_end") or 0),
                    }
                    payload_source_value_index.append(rebased)

                unit_ref = f"srcunit_{stable_digest([payload_ref, unit.get('slice_payload_checksum_ref'), unit.get('coverage', {}).get('coverage_ref')], length=24)}"
                unit.update(
                    {
                        "schema_version": SOURCE_UNIT_SCHEMA_VERSION,
                        "unit_ref": unit_ref,
                        "unit_id": unit_ref,
                        "parent_payload_ref": payload_ref,
                        "payload_checksum_ref": None,
                        "source_unit_checksum_ref": None,
                        "parser_completeness_status": "complete",
                        "declared_range_complete": True,
                        "coverage_scope": "complete_pdf_page_text_projection",
                        "source_slice_truncated": False,
                        "parent_source_slice_truncated": False,
                        "parent_remainder_status": "not_applicable_parent_complete",
                        "remaining_unit_refs": [],
                        "next_unit_refs": [],
                        "visibility": "private_case",
                        "knowledge_rag_used": False,
                        "vectorization_performed": False,
                        "pdf_unit_type": "pdf_page_text_unit",
                        "pdf_projection_schema_version": PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION,
                        "declared_page_refs": [page_ref],
                        "pdf_text_fragment_refs": list(page["text_fragment_refs"]),
                        "text_layer_projection_status": "complete",
                        "visible_content_coverage_status": visible_content_status,
                        "semantic_reconstruction_status": "not_claimed",
                        "ocr_vlm_used": False,
                        "page_rendering_used_for_extraction": False,
                    }
                )
                provisional_units.append(unit)
            else:
                page["text_segment_refs"] = []
                page["section_refs"] = []
                page["character_span_refs"] = []
                page["source_value_refs"] = []
                page["segment_provenance"] = []
            page["page_text_checksum_ref"] = pdf_page_checksum_ref(page, parser_ref)
            page_inventory.append(page)

        selected_refs: list[str] = []
        text_candidate_refs: list[str] = []
        blank_or_layout_refs: list[str] = []
        non_text_page_refs: list[str] = []
        partial_or_rejected_refs: list[str] = []
        for page in page_inventory:
            segment_refs = list(page.get("text_segment_refs") or [])
            if page.get("page_projection_status") != "complete" and segment_refs:
                selected_refs.extend(segment_refs)
                partial_or_rejected_refs.extend(segment_refs)
            elif segment_refs:
                selected_refs.extend(segment_refs)
                text_candidate_refs.extend(segment_refs)
            elif page.get("page_content_kind") == "blank":
                selected_refs.append(str(page["page_ref"]))
                blank_or_layout_refs.append(str(page["page_ref"]))
            elif page.get("page_content_kind") == "image_only":
                selected_refs.append(str(page["page_ref"]))
                non_text_page_refs.append(str(page["page_ref"]))
            else:
                selected_refs.append(str(page["page_ref"]))
                partial_or_rejected_refs.append(str(page["page_ref"]))
        accounted_refs = [
            *text_candidate_refs,
            *blank_or_layout_refs,
            *non_text_page_refs,
            *partial_or_rejected_refs,
        ]
        page_refs = [str(page.get("page_ref") or "") for page in page_inventory]
        coverage = {
            "schema_version": PDF_TEXT_LAYER_COVERAGE_SCHEMA_VERSION,
            "coverage_ref": f"pdfcoverage_{stable_digest([source_checksum_ref, *selected_refs], length=24)}",
            "declared_page_refs": page_refs,
            "accounted_page_refs": list(page_refs),
            "selected_text_refs": selected_refs,
            "text_candidate_refs": text_candidate_refs,
            "blank_or_layout_refs": blank_or_layout_refs,
            "non_text_page_refs": non_text_page_refs,
            "table_candidate_refs": [],
            "table_fallback_text_refs": [],
            "partial_or_rejected_refs": partial_or_rejected_refs,
            "selected_total": len(selected_refs),
            "accounted_total": len(accounted_refs),
            "all_declared_pages_accounted": len(page_refs) == len(set(page_refs)),
            "all_selected_refs_accounted": (
                sorted(selected_refs) == sorted(accounted_refs)
                and len(accounted_refs) == len(set(accounted_refs))
            ),
            "duplicate_accounted_refs": sorted(
                {ref for ref in accounted_refs if accounted_refs.count(ref) > 1}
            ),
            "unaccounted_refs": sorted(set(selected_refs) - set(accounted_refs)),
        }
        if status == "complete" and not provisional_units:
            status = "partial"
            text_layer_status = "partial"
            reasons.append("pdf_no_text_layer")
        reasons = sorted(set(reasons))
        extraction_units = provisional_units if status == "complete" else []
        projection = {
            "schema_version": PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION,
            "projection_policy_ref": PDF_PARSER_POLICY_VERSION,
            "parser_engine": parser_engine,
            "parser_engine_version": parser_version,
            "parser_config_ref": parser_config_ref,
            "requested_capability": "page_text",
            "provided_capabilities": ["page_text"] if page_inventory else [],
            "pdf_content_kind": pdf_content_kind,
            "declared_page_range": {
                "page_start": 1 if page_inventory else 0,
                "page_end": len(page_inventory),
                "pages_total": len(page_inventory),
            },
            "page_inventory": page_inventory,
            "text_fragment_inventory": text_fragment_inventory,
            "block_inventory": [],
            "line_inventory": copy.deepcopy(text_segment_inventory),
            "word_inventory": [],
            "table_candidate_inventory": [],
            "page_checksum_refs": [
                str(page.get("page_text_checksum_ref") or "") for page in page_inventory
            ],
            "coverage": coverage,
            "completeness": {
                "text_layer_projection_status": text_layer_status,
                "visible_content_coverage_status": visible_content_status,
                "semantic_reconstruction_status": semantic_status,
                "reason_codes": reasons,
            },
            "text_layer_projection_status": text_layer_status,
            "visible_content_coverage_status": visible_content_status,
            "semantic_reconstruction_status": semantic_status,
            "parser_diagnostics": parser_diagnostics,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
        }
        budget_omitted = not page_inventory and any(
            reason.endswith("_budget_exceeded") for reason in reasons
        )
        payload = {
            "schema_version": SOURCE_PAYLOAD_SCHEMA_VERSION,
            "source_payload_ref": payload_ref,
            "normalization_run_id": normalization_run_id,
            "document_ref": document_id,
            "profile_ref": profile_id,
            "container_format": "pdf",
            "logical_identity": logical_identity,
            "parser": parser_label,
            "parser_version": parser_version,
            "parser_ref": parser_ref,
            "source_checksum_ref": source_checksum_ref,
            "payload_checksum_ref": None,
            "parser_completeness_status": status,
            "parser_completeness_reason_codes": reasons,
            "normalized_projection": {
                "kind": "pdf_text_layer_projection",
                "projection_schema_version": PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION,
            }
            if not budget_omitted
            else {},
            "normalized_projection_status": (
                "omitted_budget_exceeded" if budget_omitted else "materialized"
            ),
            "source_location": {
                "kind": "pdf_text_layer_pages",
                "page_start": 1 if page_inventory else 0,
                "page_end": len(page_inventory),
            },
            "rows_total": 0,
            "cells_total": 0,
            "text_characters_total": sum(
                len(str(page.get("text") or "")) for page in page_inventory
            ),
            "row_inventory": [],
            "cell_inventory": [],
            "text_segment_inventory": text_segment_inventory,
            "text_fragment_refs": [
                str(item.get("text_fragment_ref") or "")
                for item in text_fragment_inventory
            ],
            "page_refs": page_refs,
            "source_value_refs": payload_source_value_refs,
            "source_value_index": payload_source_value_index,
            "coverage_index": {
                **copy.deepcopy(coverage),
                "full_source_coverage_available": status == "complete"
                and bool(extraction_units),
                "coverage_scope": "complete_pdf_text_layer_projection"
                if status == "complete"
                else "partial_pdf_text_layer_projection",
                "reason_codes": reasons,
            },
            "extraction_unit_refs": [
                str(unit.get("unit_ref") or "") for unit in extraction_units
            ],
            "pdf_text_layer_projection": projection,
            "text_layer_projection_status": text_layer_status,
            "visible_content_coverage_status": visible_content_status,
            "semantic_reconstruction_status": semantic_status,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
            "visibility": "private_case",
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        }
        payload["payload_checksum_ref"] = pdf_payload_checksum_ref(payload)
        unit_refs = [str(unit.get("unit_ref") or "") for unit in extraction_units]
        for index, unit in enumerate(extraction_units):
            unit["payload_checksum_ref"] = payload["payload_checksum_ref"]
            unit["source_unit_checksum_ref"] = _checksum_ref(
                "srcunitchk",
                {
                    "unit_ref": unit.get("unit_ref"),
                    "payload_checksum_ref": unit.get("payload_checksum_ref"),
                    "slice_payload_checksum_ref": unit.get(
                        "slice_payload_checksum_ref"
                    ),
                    "coverage_ref": (unit.get("coverage") or {}).get("coverage_ref"),
                },
            )
            unit["remaining_unit_refs"] = unit_refs[index + 1 :]
            unit["next_unit_refs"] = unit_refs[index + 1 : index + 2]

        payload_validation = validate_pdf_text_layer_payload(payload)
        if status == "complete" and payload_validation.get("validator_status") != "passed":
            status = "partial"
            text_layer_status = "partial"
            reasons = sorted(
                {
                    *reasons,
                    *(
                        str(error.get("code") or "pdf_projection_validation_failed")
                        for error in payload_validation.get("errors") or []
                    ),
                }
            )
            extraction_units = []
            payload["parser_completeness_status"] = status
            payload["parser_completeness_reason_codes"] = reasons
            payload["text_layer_projection_status"] = text_layer_status
            projection["text_layer_projection_status"] = text_layer_status
            projection["completeness"]["text_layer_projection_status"] = text_layer_status
            projection["completeness"]["reason_codes"] = reasons
            payload["extraction_unit_refs"] = []
            payload["coverage_index"]["full_source_coverage_available"] = False
            payload["coverage_index"]["coverage_scope"] = (
                "partial_pdf_text_layer_projection"
            )
            payload["coverage_index"]["reason_codes"] = reasons
            payload["payload_checksum_ref"] = pdf_payload_checksum_ref(payload)

        summary = {
            "schema_version": "full_source_coverage_summary_v0",
            "document_ref": document_id,
            "container_format": "pdf",
            "parser_completeness_status": status,
            "parser_completeness_reason_codes": reasons,
            "payloads_total": 1,
            "extraction_units_total": len(extraction_units),
            "rows_total": 0,
            "cells_total": 0,
            "text_characters_total": int(payload.get("text_characters_total") or 0),
            "text_segments_total": len(text_segment_inventory),
            "full_coverage_available": status == "complete" and bool(extraction_units),
            "preview_artifacts_are_coverage_authority": False,
            "pdf_pages_total": len(page_inventory),
            "pdf_pages_with_text": sum(
                1 for page in page_inventory if str(page.get("text") or "").strip()
            ),
            "pdf_pages_without_text": sum(
                1 for page in page_inventory if not str(page.get("text") or "").strip()
            ),
            "pdf_source_value_refs_total": len(payload_source_value_refs),
            "pdf_text_layer_projection_status": text_layer_status,
            "pdf_visible_content_coverage_status": visible_content_status,
            "pdf_semantic_reconstruction_status": semantic_status,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        }
        return FullSourceBuildResult(
            payloads=[payload],
            units=extraction_units,
            summary=summary,
        )

    def _extract_pdf(self, content_bytes: bytes) -> tuple[list[dict[str, Any]], list[str]]:
        if not content_bytes.startswith(b"%PDF-"):
            return [self._blocked_descriptor("text_excerpt", "python_stdlib_pdf_heuristic", "pdf_header_missing")], []
        # Compatibility fallback only. Production PDF builds are routed above
        # through PdfTextLayerParserFactory and never reach this heuristic.
        # The legacy profiler remains a bounded preview and cannot mint units.
        text = ""
        reasons = [
            "pdf_heuristic_parser_not_full_coverage",
            "pdf_full_text_not_reparsed_for_partial_payload",
        ]
        descriptor = {
            "logical_identity": "pdf_heuristic_text_001",
            "slice_type": "text_excerpt",
            "parser": "python_stdlib_pdf_heuristic",
            "parser_version": "1",
            "parser_completeness_status": "partial",
            "parser_completeness_reason_codes": reasons,
            "source_location": {
                "kind": "pdf_heuristic_text_projection",
                "page_start": 1,
                "page_end": max(1, len(re.findall(rb"/Type\s*/Page(?!s)", content_bytes))),
            },
            "text": text,
        }
        return [descriptor], reasons

    def _build_descriptor(
        self,
        *,
        normalization_run_id: str,
        document_id: str,
        profile_id: str,
        source_checksum_sha256: str,
        container_format: str,
        ordinal: int,
        descriptor: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        logical_identity = str(descriptor.get("logical_identity") or f"logical_{ordinal:03d}")
        projection = (
            {"cells": copy.deepcopy(descriptor.get("cells") or [])}
            if descriptor.get("slice_type") == "table_rows"
            else {"text": str(descriptor.get("text") or "")}
        )
        rows = projection.get("cells") if isinstance(projection.get("cells"), list) else []
        text = str(projection.get("text") or "")
        rows_total = len(rows)
        cells_total = sum(len(row) for row in rows if isinstance(row, list))
        reasons = list(descriptor.get("parser_completeness_reason_codes") or [])
        status = str(descriptor.get("parser_completeness_status") or "blocked")
        if rows_total > self.config.max_rows_per_logical_unit:
            status = "partial"
            reasons.append("full_source_row_budget_exceeded")
        if cells_total > self.config.max_cells_per_logical_unit:
            status = "partial"
            reasons.append("full_source_cell_budget_exceeded")
        if len(text) > self.config.max_text_characters_per_logical_unit:
            status = "partial"
            reasons.append("full_source_text_budget_exceeded")
        if status not in PARSER_COMPLETENESS_STATUSES:
            raise ValueError("full_source_parser_completeness_status_invalid")

        budget_exceeded = any(reason.endswith("_budget_exceeded") for reason in reasons)
        stored_projection = {} if budget_exceeded else projection
        payload_ref = f"srcpayload_{stable_digest([normalization_run_id, document_id, logical_identity, source_checksum_sha256], length=24)}"
        payload_checksum_ref = _checksum_ref(
            "srcpayloadchk",
            {
                "container_format": container_format,
                "logical_identity": logical_identity,
                "source_location": descriptor.get("source_location") or {},
                "projection": stored_projection,
                "projection_status": (
                    "omitted_budget_exceeded" if budget_exceeded else "materialized"
                ),
                "parser": descriptor.get("parser"),
                "parser_version": descriptor.get("parser_version"),
            },
        )
        source_checksum_ref = f"srcsum_{stable_digest([document_id, source_checksum_sha256], length=24)}"
        payload = {
            "schema_version": SOURCE_PAYLOAD_SCHEMA_VERSION,
            "source_payload_ref": payload_ref,
            "normalization_run_id": normalization_run_id,
            "document_ref": document_id,
            "profile_ref": profile_id,
            "container_format": container_format,
            "logical_identity": logical_identity,
            "parser": descriptor.get("parser"),
            "parser_version": descriptor.get("parser_version"),
            "parser_ref": f"parser_{stable_digest([descriptor.get('parser'), profile_id], length=20)}",
            "source_checksum_ref": source_checksum_ref,
            "payload_checksum_ref": payload_checksum_ref,
            "parser_completeness_status": status,
            "parser_completeness_reason_codes": sorted(set(reasons)),
            "normalized_projection": stored_projection,
            "normalized_projection_status": (
                "omitted_budget_exceeded" if budget_exceeded else "materialized"
            ),
            "source_location": copy.deepcopy(descriptor.get("source_location") or {}),
            "rows_total": rows_total,
            "cells_total": cells_total,
            "text_characters_total": len(text),
            "row_inventory": [],
            "cell_inventory": [],
            "text_segment_inventory": [],
            "source_value_index": [],
            "coverage_index": {
                "full_source_coverage_available": False,
                "reason_codes": sorted(set(reasons)),
            },
            "extraction_unit_refs": [],
            "visibility": "private_case",
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        }
        if status != "complete":
            return payload, None

        slice_id = f"fullsrc_{stable_digest([payload_ref, logical_identity], length=24)}"
        private_slice = {
            "slice_id": slice_id,
            "document_id": document_id,
            "profile_id": profile_id,
            "slice_type": descriptor.get("slice_type"),
            "source_location": copy.deepcopy(descriptor.get("source_location") or {}),
            "location": copy.deepcopy(descriptor.get("source_location") or {}),
            "bounded": True,
            "truncated": False,
            "parser": descriptor.get("parser"),
            "created_for_gate": "gate1_full_source_reslice",
        }
        if descriptor.get("slice_type") == "table_rows":
            private_slice.update(
                {
                    "rows_in_slice": rows_total,
                    "rows_count": rows_total,
                    "columns_count": max((len(row) for row in rows if isinstance(row, list)), default=0),
                    "row_range": [1, rows_total] if rows_total else [0, 0],
                    "column_policy": "complete_parser_logical_unit",
                    "cells": copy.deepcopy(rows),
                    "rows": copy.deepcopy(rows),
                }
            )
        else:
            private_slice.update(
                {
                    "characters_in_slice": len(text),
                    "chars_count": len(text),
                    "text": text,
                }
            )
        unit = self.provenance.enrich_slice(
            normalization_run_id=normalization_run_id,
            document_id=document_id,
            source_checksum_sha256=source_checksum_sha256,
            private_slice=private_slice,
        )
        unit_ref = f"srcunit_{stable_digest([payload_ref, unit.get('slice_payload_checksum_ref'), unit.get('coverage', {}).get('coverage_ref')], length=24)}"
        unit.update(
            {
                "schema_version": SOURCE_UNIT_SCHEMA_VERSION,
                "unit_ref": unit_ref,
                "unit_id": unit_ref,
                "parent_payload_ref": payload_ref,
                "payload_checksum_ref": payload_checksum_ref,
                "source_unit_checksum_ref": _checksum_ref(
                    "srcunitchk",
                    {
                        "unit_ref": unit_ref,
                        "payload_checksum_ref": payload_checksum_ref,
                        "slice_payload_checksum_ref": unit.get("slice_payload_checksum_ref"),
                        "coverage_ref": (unit.get("coverage") or {}).get("coverage_ref"),
                    },
                ),
                "parser_completeness_status": "complete",
                "declared_range_complete": True,
                "coverage_scope": "complete_parser_logical_unit",
                "source_slice_truncated": False,
                "parent_source_slice_truncated": False,
                "parent_remainder_status": "not_applicable_parent_complete",
                "remaining_unit_refs": [],
                "next_unit_refs": [],
                "visibility": "private_case",
                "knowledge_rag_used": False,
                "vectorization_performed": False,
            }
        )
        payload["coverage_index"] = copy.deepcopy(unit.get("coverage") or {})
        payload["coverage_index"].update(
            {
                "full_source_coverage_available": True,
                "coverage_scope": "complete_parser_logical_unit",
            }
        )
        return payload, unit

    @staticmethod
    def _blocked_descriptor(
        slice_type: str,
        parser: str,
        reason: str,
        *,
        logical_identity: str = "blocked_projection_001",
    ) -> dict[str, Any]:
        return {
            "logical_identity": logical_identity,
            "slice_type": slice_type,
            "parser": parser,
            "parser_version": "1",
            "parser_completeness_status": "blocked",
            "parser_completeness_reason_codes": [reason],
            "source_location": {"kind": "blocked_projection"},
            "cells": [] if slice_type == "table_rows" else None,
            "text": "" if slice_type != "table_rows" else None,
        }


def validate_full_source_unit(
    *,
    unit: dict[str, Any],
    normalization_run_id: str,
    document_id: str,
    source_checksum_sha256: str,
) -> dict[str, Any]:
    from .source_provenance import validate_normalized_slice_provenance

    errors: list[dict[str, str]] = []
    if unit.get("schema_version") != SOURCE_UNIT_SCHEMA_VERSION:
        errors.append({"code": "full_source_unit_schema_mismatch", "subject": str(unit.get("unit_ref") or "")})
    if unit.get("parser_completeness_status") != "complete":
        errors.append({"code": "full_source_unit_parser_not_complete", "subject": str(unit.get("unit_ref") or "")})
    if unit.get("declared_range_complete") is not True:
        errors.append({"code": "full_source_unit_declared_range_incomplete", "subject": str(unit.get("unit_ref") or "")})
    if unit.get("source_slice_truncated") is not False:
        errors.append({"code": "full_source_unit_truncated", "subject": str(unit.get("unit_ref") or "")})
    if unit.get("parent_source_slice_truncated") is not False:
        errors.append({"code": "full_source_unit_parent_truncated", "subject": str(unit.get("unit_ref") or "")})
    if unit.get("parent_remainder_status") != "not_applicable_parent_complete":
        errors.append({"code": "full_source_unit_parent_remainder_pending", "subject": str(unit.get("unit_ref") or "")})
    expected_unit_checksum = _checksum_ref(
        "srcunitchk",
        {
            "unit_ref": unit.get("unit_ref"),
            "payload_checksum_ref": unit.get("payload_checksum_ref"),
            "slice_payload_checksum_ref": unit.get("slice_payload_checksum_ref"),
            "coverage_ref": (unit.get("coverage") or {}).get("coverage_ref"),
        },
    )
    if unit.get("source_unit_checksum_ref") != expected_unit_checksum:
        errors.append({"code": "full_source_unit_checksum_mismatch", "subject": str(unit.get("unit_ref") or "")})
    if unit.get("pdf_unit_type"):
        errors.extend(validate_pdf_source_unit(unit))
    provenance = validate_normalized_slice_provenance(
        private_slice=unit,
        normalization_run_id=normalization_run_id,
        document_id=document_id,
        source_checksum_sha256=source_checksum_sha256,
    )
    errors.extend(copy.deepcopy(provenance.get("errors") or []))
    return {
        "schema_version": "private_normalized_source_unit_validation_v0",
        "unit_ref": unit.get("unit_ref"),
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "errors_count": len(errors),
        "errors": errors,
    }


class _FullHtmlExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._table_depth = 0
        self._outside_parts: list[str] = []
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self.tables: list[list[list[str]]] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_table = []
            return
        if tag == "tr" and self._table_depth == 1:
            self._current_row = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []
        elif not self._table_depth and tag in {"br", "p", "div", "li", "section", "h1", "h2", "h3"}:
            self._outside_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
            self._current_row.append(" ".join(" ".join(self._current_cell).split()))
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            if any(cell for cell in self._current_row):
                assert self._current_table is not None
                self._current_table.append(self._current_row)
            self._current_row = None
            self._current_cell = None
        elif tag == "table" and self._table_depth:
            if self._table_depth == 1 and self._current_table is not None:
                self.tables.append(self._current_table)
                self._current_table = None
            self._table_depth -= 1
        elif not self._table_depth and tag in {"p", "div", "li", "section", "h1", "h2", "h3"}:
            self._outside_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._current_cell is not None:
            self._current_cell.append(text)
        elif not self._table_depth:
            self._outside_parts.append(text)

    def outside_text(self) -> str:
        lines = []
        for line in "\n".join(self._outside_parts).splitlines():
            clean = " ".join(line.split())
            if clean:
                lines.append(clean)
        return "\n".join(lines)


def _detect_delimiter(decoded: str) -> str:
    sample = decoded[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return max((",", ";", "\t", "|"), key=sample.count)


def _xlsx_relationships(archive: ZipFile) -> dict[str, str]:
    try:
        root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        return {}
    return {
        str(node.attrib["Id"]): str(node.attrib["Target"])
        for node in _iter_local(root, "Relationship")
        if node.attrib.get("Id") and node.attrib.get("Target")
    }


def _xlsx_shared_strings(archive: ZipFile, *, max_member_bytes: int) -> list[str]:
    try:
        info = archive.getinfo("xl/sharedStrings.xml")
    except KeyError:
        return []
    if info.file_size > max_member_bytes:
        raise ValueError("xlsx_shared_strings_member_too_large")
    root = ET.fromstring(archive.read(info.filename))
    return ["".join(node.text or "" for node in _iter_local(item, "t")) for item in _iter_local(root, "si")]


def _xlsx_rows_with_coordinates(
    root: ET.Element, shared_strings: list[str]
) -> tuple[list[list[str | None]], int]:
    rows: list[list[str | None]] = []
    formulas_count = 0
    expected_row = 1
    for row_node in _iter_local(root, "row"):
        try:
            row_ordinal = int(row_node.attrib.get("r") or expected_row)
        except ValueError:
            row_ordinal = expected_row
        while expected_row < row_ordinal:
            rows.append([])
            expected_row += 1
        cells: list[str | None] = []
        expected_column = 1
        for cell_node in _iter_local(row_node, "c"):
            cell_ref = str(cell_node.attrib.get("r") or "")
            column = _xlsx_column_ordinal(cell_ref) or expected_column
            while expected_column < column:
                cells.append(None)
                expected_column += 1
            if next(_iter_local(cell_node, "f"), None) is not None:
                formulas_count += 1
            cells.append(_xlsx_cell_value(cell_node, shared_strings))
            expected_column += 1
        rows.append(cells)
        expected_row = row_ordinal + 1
    return rows, formulas_count


def _xlsx_cell_value(cell_node: ET.Element, shared_strings: list[str]) -> str | None:
    cell_type = cell_node.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in _iter_local(cell_node, "t")) or None
    value_node = next(_iter_local(cell_node, "v"), None)
    if value_node is None or value_node.text is None:
        return None
    if cell_type == "s":
        try:
            return shared_strings[int(value_node.text)]
        except (ValueError, IndexError):
            return None
    return value_node.text


def _xlsx_column_ordinal(cell_ref: str) -> int | None:
    match = re.match(r"([A-Za-z]+)", cell_ref)
    if not match:
        return None
    value = 0
    for character in match.group(1).upper():
        value = value * 26 + ord(character) - ord("A") + 1
    return value


def _sheet_target_path(target: str | None) -> str | None:
    if not target:
        return None
    normalized = str(PurePosixPath(target.lstrip("/")))
    return normalized if normalized.startswith("xl/") else f"xl/{normalized}"


def _iter_local(root: ET.Element, local_name: str):
    return (node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == local_name)


def _rel_attr(local_name: str) -> str:
    return f"{{http://schemas.openxmlformats.org/officeDocument/2006/relationships}}{local_name}"


def _checksum_ref(prefix: str, value: Any) -> str:
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:24]}"
