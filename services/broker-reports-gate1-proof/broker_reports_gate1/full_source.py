from __future__ import annotations

import copy
import base64
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
from .csv_profile import CsvSupportedProfileError, CsvSupportedProfileFactory
from .pdf_document_ai import PdfDocumentExtraction
from .profilers_csv_txt import decode_text_bytes
from .source_provenance import NormalizedSliceProvenanceFactory
from .xml_source import XmlNeutralMemoryError, XmlNeutralMemoryFactory


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
    max_html_embedded_media_items: int = 16
    max_html_embedded_media_bytes_per_item: int = 2_000_000
    max_html_embedded_media_bytes_per_document: int = 10_000_000
    enable_canonical_artifact_v1_shadow: bool = False


@dataclass(frozen=True)
class FullSourceBuildResult:
    payloads: list[dict[str, Any]]
    units: list[dict[str, Any]]
    summary: dict[str, Any]


class FullSourceArtifactFactory:
    """Sole bounded extractor factory for private Full Evidence material.

    Its output feeds canonical normalization but is not itself the public Gate
    2 contract. Callers must keep source bytes and detailed parser evidence in
    the authenticated private contour.
    """

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
        if self.config.max_html_embedded_media_items <= 0:
            raise ValueError("full_source_html_media_count_budget_invalid")
        if self.config.max_html_embedded_media_bytes_per_item <= 0:
            raise ValueError("full_source_html_media_item_budget_invalid")
        if self.config.max_html_embedded_media_bytes_per_document <= 0:
            raise ValueError("full_source_html_media_document_budget_invalid")
        return FullSourceArtifactBuilder(self.config)


class FullSourceArtifactBuilder:
    """Extract format-specific source units under explicit resource budgets."""

    def __init__(self, config: FullSourceArtifactConfig) -> None:
        self.config = config
        self.provenance = NormalizedSliceProvenanceFactory().create()

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

    def build_document_extraction(
        self,
        *,
        normalization_run_id: str,
        document_id: str,
        profile_id: str,
        extraction: PdfDocumentExtraction,
    ) -> FullSourceBuildResult:
        """Carry exact extraction output as one private representation-only unit."""
        text = extraction.markdown_bytes.decode("utf-8", errors="strict")
        provenance = {
            "provider_id": extraction.provider_id,
            "model_id": extraction.model_id,
            "adapter_id": extraction.adapter_id,
            "qualification_status": extraction.qualification_status,
        }
        image_refs = [
            {
                "page_number": item.page_number,
                "markdown_target": item.markdown_target,
                "local_ref": item.local_ref,
                "sha256": item.sha256,
            }
            for item in extraction.image_refs
        ]
        descriptor = {
            "logical_identity": "document_ai_markdown_001",
            "slice_type": "text_excerpt",
            "parser": "document_ai_extraction_envelope",
            "parser_version": extraction.schema_version,
            "parser_completeness_status": "complete",
            "parser_completeness_reason_codes": [],
            "format_reason_codes": ["document_ai_content_not_semantically_parsed"],
            "format_structural_inventory": {
                "pages_count": extraction.usage_page_count,
                "images_count": len(extraction.image_refs),
                "markdown_bytes": len(extraction.markdown_bytes),
            },
            "source_location": {
                "kind": "document_ai_extraction",
                "page_numbers": list(extraction.page_numbers),
            },
            "text": text,
            "document_ai_provenance": provenance,
            "document_ai_markdown_sha256": extraction.markdown_sha256,
            "document_ai_image_refs": image_refs,
        }
        payload, unit = self._build_descriptor(
            normalization_run_id=normalization_run_id,
            document_id=document_id,
            profile_id=profile_id,
            source_checksum_sha256=extraction.source_pdf_sha256,
            container_format="pdf",
            ordinal=1,
            descriptor=descriptor,
        )
        units = [unit] if unit is not None else []
        return FullSourceBuildResult(
            payloads=[payload],
            units=units,
            summary={
                "schema_version": "full_source_coverage_summary_v0",
                "document_ref": document_id,
                "container_format": "pdf",
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "payloads_total": 1,
                "extraction_units_total": len(units),
                "rows_total": 0,
                "cells_total": 0,
                "text_characters_total": len(text),
                "text_segments_total": 0,
                "full_coverage_available": bool(units),
                "preview_artifacts_are_coverage_authority": False,
                "knowledge_rag_used": False,
                "vectorization_performed": False,
            },
        )

    def _extract(
        self, *, container_format: str, content_bytes: bytes, document_id: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if container_format == "csv":
            return self._extract_csv(content_bytes), []
        if container_format == "txt":
            return self._extract_text(content_bytes), []
        if container_format == "html_text":
            return self._extract_html(content_bytes), []
        if container_format == "xml":
            return self._extract_xml(content_bytes)
        if container_format == "xlsx":
            return self._extract_xlsx(content_bytes, document_id)
        if container_format == "docx":
            return self._extract_docx(content_bytes)
        return [], ["format_not_supported_for_full_source"]

    def _extract_xml(
        self, content_bytes: bytes
    ) -> tuple[list[dict[str, Any]], list[str]]:
        try:
            parsed = XmlNeutralMemoryFactory().create().parse(content_bytes)
        except XmlNeutralMemoryError as exc:
            return [
                self._blocked_descriptor(
                    "table_rows",
                    "python_expat_neutral_events",
                    exc.code,
                    logical_identity="xml_neutral_events_001",
                )
            ], [exc.code]
        return [
            {
                "logical_identity": "xml_neutral_events_001",
                "slice_type": "table_rows",
                "parser": "python_expat_neutral_events",
                "parser_version": "stdlib",
                "parser_completeness_status": "complete",
                "parser_completeness_reason_codes": [],
                "format_reason_codes": [
                    "xml_financial_semantics_not_claimed",
                    "xml_canonical_table_topology_not_claimed",
                ],
                "format_structural_inventory": parsed.safe_inventory,
                "source_location": {
                    "kind": "xml_neutral_event_rows",
                    "start_row": 1,
                    "end_row": len(parsed.rows),
                    "profile_id": "broker_reports_xml_neutral_event_memory_v1",
                },
                "cells": parsed.rows,
            }
        ], []

    def _extract_csv(self, content_bytes: bytes) -> list[dict[str, Any]]:
        try:
            parsed = CsvSupportedProfileFactory().create().parse(content_bytes)
        except CsvSupportedProfileError as exc:
            if self.config.enable_canonical_artifact_v1_shadow:
                canonical = _canonical_csv_projection(content_bytes)
                if canonical is not None:
                    descriptor = self._blocked_descriptor(
                        "table_rows", "python_stdlib_csv", exc.code
                    )
                    descriptor["canonical_projection"] = canonical
                    return [descriptor]
            return [
                self._blocked_descriptor(
                    "table_rows", "python_stdlib_csv", exc.code
                )
            ]
        rows = parsed.rows
        descriptor = {
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
                    "encoding": parsed.encoding,
                    "delimiter": parsed.delimiter,
                    "supported_csv_profile_id": "broker_reports_csv_supported_profile_v1",
                },
                "cells": rows,
            }
        if self.config.enable_canonical_artifact_v1_shadow:
            descriptor["canonical_projection"] = {
                "rows": copy.deepcopy(rows),
                "encoding": parsed.encoding,
                "delimiter": parsed.delimiter,
                "quotechar": '"',
                "header_present": True,
                "duplicate_headers": len(rows[0]) != len(set(rows[0])) if rows else False,
            }
        return [descriptor]

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
        parser = _FullHtmlExtractor(
            max_media_items=self.config.max_html_embedded_media_items,
            max_media_bytes_per_item=(
                self.config.max_html_embedded_media_bytes_per_item
            ),
            max_media_bytes_per_document=(
                self.config.max_html_embedded_media_bytes_per_document
            ),
            capture_canonical_semantics=(
                self.config.enable_canonical_artifact_v1_shadow
            ),
        )
        try:
            parser.feed(decoded)
            parser.close()
        except Exception:
            return [self._blocked_descriptor("text_excerpt", "python_html_text_decode", "html_parse_failed")]
        format_reason_codes = parser.format_reason_codes()
        blocking_reason_codes = parser.blocking_reason_codes()
        format_structural_inventory = parser.safe_structural_inventory()
        descriptors: list[dict[str, Any]] = []
        text_index = 0
        for block_index, block in enumerate(
            parser.ordered_content_blocks(), start=1
        ):
            if block["kind"] == "text":
                text_index += 1
                outside_text = str(block["text"])
                descriptors.append(
                    {
                        "logical_identity": (
                            f"html_outside_table_text_{text_index:03d}"
                        ),
                        "slice_type": "text_excerpt",
                        "parser": "python_html_text_decode",
                        "parser_version": "1",
                        "parser_completeness_status": (
                            "partial" if blocking_reason_codes else "complete"
                        ),
                        "parser_completeness_reason_codes": blocking_reason_codes,
                        "format_reason_codes": format_reason_codes,
                        "format_structural_inventory": format_structural_inventory,
                        "source_location": {
                            "kind": "html_outside_table_text",
                            "content_block_ordinal": block_index,
                            "character_start": 0,
                            "character_end": len(outside_text),
                            "encoding": encoding,
                        },
                        "text": outside_text,
                    }
                )
                continue
            rows = copy.deepcopy(block["rows"])
            table_index = int(block["table_ordinal"])
            descriptors.append(
                {
                    "logical_identity": f"html_table_{table_index:03d}",
                    "slice_type": "table_rows",
                    "parser": "python_html_table_decode",
                    "parser_version": "1",
                    "parser_completeness_status": (
                        "partial" if blocking_reason_codes else "complete"
                    ),
                    "parser_completeness_reason_codes": blocking_reason_codes,
                    "format_reason_codes": format_reason_codes,
                    "format_structural_inventory": format_structural_inventory,
                    "source_location": {
                        "kind": "html_table_rows",
                        "content_block_ordinal": block_index,
                        "table_ordinal": table_index,
                        "start_row": 1 if rows else 0,
                        "end_row": len(rows),
                        "encoding": encoding,
                    },
                    "cells": rows,
                }
            )
        for media_index, media in enumerate(parser.embedded_media, start=1):
            descriptors.append(
                {
                    "logical_identity": f"html_embedded_media_{media_index:03d}",
                    "slice_type": "visual_media",
                    "parser": "python_html_data_media_decode",
                    "parser_version": "1",
                    "parser_completeness_status": (
                        "partial" if blocking_reason_codes else "complete"
                    ),
                    "parser_completeness_reason_codes": blocking_reason_codes,
                    "format_reason_codes": format_reason_codes,
                    "format_structural_inventory": format_structural_inventory,
                    "source_location": {
                        "kind": "html_embedded_data_media",
                        "media_ordinal": media_index,
                        "encoding": encoding,
                    },
                    "media_type": media["media_type"],
                    "private_media_base64": media["private_media_base64"],
                    "private_media_sha256": media["private_media_sha256"],
                }
            )
        if not descriptors:
            descriptors.append(
                {
                    "logical_identity": "html_text_001",
                    "slice_type": "text_excerpt",
                    "parser": "python_html_text_decode",
                    "parser_version": "1",
                    "parser_completeness_status": (
                        "partial" if blocking_reason_codes else "complete"
                    ),
                    "parser_completeness_reason_codes": blocking_reason_codes,
                    "format_reason_codes": format_reason_codes,
                    "format_structural_inventory": format_structural_inventory,
                    "source_location": {
                        "kind": "html_text",
                        "character_start": 0,
                        "character_end": 0,
                        "encoding": encoding,
                    },
                    "text": "",
                }
            )
        if self.config.enable_canonical_artifact_v1_shadow and descriptors:
            descriptors[0]["canonical_projection"] = {
                "blocks": parser.semantic_content_blocks()
            }
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
                descriptor = {
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
                if self.config.enable_canonical_artifact_v1_shadow:
                    descriptor["canonical_projection"] = _canonical_xlsx_projection(
                        workbook_root=workbook_root,
                        sheet=sheet,
                        sheet_root=root,
                        sheet_index=sheet_index,
                        rows=rows,
                        shared_strings=shared_strings,
                    )
                descriptors.append(descriptor)
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
        if descriptor.get("slice_type") == "table_rows":
            projection = {"cells": copy.deepcopy(descriptor.get("cells") or [])}
        elif descriptor.get("slice_type") == "visual_media":
            projection = {
                "media_type": descriptor.get("media_type"),
                "private_media_base64": descriptor.get("private_media_base64"),
                "private_media_sha256": descriptor.get("private_media_sha256"),
            }
        else:
            projection = {"text": str(descriptor.get("text") or "")}
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
        checksum_material = {
            "container_format": container_format,
            "logical_identity": logical_identity,
            "source_location": descriptor.get("source_location") or {},
            "projection": stored_projection,
            "projection_status": (
                "omitted_budget_exceeded" if budget_exceeded else "materialized"
            ),
            "parser": descriptor.get("parser"),
            "parser_version": descriptor.get("parser_version"),
            "format_structural_inventory": descriptor.get(
                "format_structural_inventory"
            )
            or {},
            "format_reason_codes": descriptor.get("format_reason_codes") or [],
        }
        for key in (
            "document_ai_provenance",
            "document_ai_markdown_sha256",
            "document_ai_image_refs",
        ):
            if key in descriptor:
                checksum_material[key] = copy.deepcopy(descriptor[key])
        payload_checksum_ref = _checksum_ref("srcpayloadchk", checksum_material)
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
            "format_reason_codes": sorted(
                set(descriptor.get("format_reason_codes") or [])
            ),
            "format_structural_inventory": copy.deepcopy(
                descriptor.get("format_structural_inventory") or {}
            ),
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
        for key in (
            "document_ai_provenance",
            "document_ai_markdown_sha256",
            "document_ai_image_refs",
        ):
            if key in descriptor:
                payload[key] = copy.deepcopy(descriptor[key])
        if self.config.enable_canonical_artifact_v1_shadow and isinstance(
            descriptor.get("canonical_projection"), dict
        ):
            payload["canonical_projection"] = copy.deepcopy(
                descriptor["canonical_projection"]
            )
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
        elif descriptor.get("slice_type") == "visual_media":
            private_slice.update(
                {
                    "media_type": descriptor.get("media_type"),
                    "private_media_base64": descriptor.get(
                        "private_media_base64"
                    ),
                    "private_media_sha256": descriptor.get(
                        "private_media_sha256"
                    ),
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
    def __init__(
        self,
        *,
        max_media_items: int,
        max_media_bytes_per_item: int,
        max_media_bytes_per_document: int,
        capture_canonical_semantics: bool = False,
    ) -> None:
        super().__init__()
        self.max_media_items = max_media_items
        self.max_media_bytes_per_item = max_media_bytes_per_item
        self.max_media_bytes_per_document = max_media_bytes_per_document
        self.capture_canonical_semantics = capture_canonical_semantics
        self._skip_depth = 0
        self._skip_tags: list[str] = []
        self._table_depth = 0
        self._outside_parts: list[str] = []
        self._ordered_content_blocks: list[dict[str, Any]] = []
        self._current_table: list[list[str]] | None = None
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._current_caption: list[str] | None = None
        self.tables: list[list[list[str]]] = []
        self.script_elements_total = 0
        self.script_characters_total = 0
        self.style_elements_total = 0
        self.comment_elements_total = 0
        self.embedded_media_elements_total = 0
        self.embedded_media: list[dict[str, str]] = []
        self.embedded_media_bytes_total = 0
        self.embedded_media_reason_codes: list[str] = []
        self.nested_tables_total = 0
        self.link_elements_total = 0
        self._semantic_blocks: list[dict[str, Any]] = []
        self._semantic_stack: list[dict[str, Any]] = []
        self._list_tags: list[str] = []
        self._active_link: dict[str, Any] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        hidden = (
            "hidden" in attributes
            or str(attributes.get("aria-hidden") or "").lower() == "true"
            or "display:none"
            in str(attributes.get("style") or "").lower().replace(" ", "")
        )
        if self._skip_depth:
            self._skip_depth += 1
            self._skip_tags.append(tag)
            return
        if tag in {"script", "style"} or hidden:
            if tag == "script":
                self.script_elements_total += 1
            elif tag == "style":
                self.style_elements_total += 1
            self._skip_depth += 1
            self._skip_tags.append(tag)
            return
        if tag in {"img", "picture", "object", "embed", "iframe", "canvas", "svg", "video", "audio"}:
            self.embedded_media_elements_total += 1
            if tag == "img":
                self._capture_data_image(dict(attrs).get("src"))
        if tag == "a":
            self.link_elements_total += 1
            if self.capture_canonical_semantics and not self._table_depth:
                self._active_link = {
                    "target": str(dict(attrs).get("href") or ""),
                    "parts": [],
                }
        if self.capture_canonical_semantics and not self._table_depth:
            if tag in {"ul", "ol"}:
                self._list_tags.append(tag)
            if tag in {
                "title",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
                "p",
                "li",
                "aside",
                "blockquote",
            }:
                self._semantic_stack.append(
                    {
                        "tag": tag,
                        "parts": [],
                        "links": [],
                        "list_level": max(0, len(self._list_tags) - 1),
                        "ordered": bool(self._list_tags and self._list_tags[-1] == "ol"),
                    }
                )
        if tag == "table":
            if not self._table_depth:
                self._flush_outside_block()
            if self._table_depth:
                self.nested_tables_total += 1
            self._table_depth += 1
            if self._table_depth == 1:
                self._current_table = []
            return
        if tag == "tr" and self._table_depth == 1:
            self._current_row = []
        elif tag == "caption" and self._table_depth == 1:
            self._current_caption = []
        elif tag in {"td", "th"} and self._current_row is not None:
            self._current_cell = []
        elif not self._table_depth and tag in {"br", "p", "div", "li", "section", "h1", "h2", "h3"}:
            self._outside_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            if self._skip_tags and self._skip_tags[-1] == tag:
                self._skip_depth -= 1
                self._skip_tags.pop()
            return
        if tag == "a" and self.capture_canonical_semantics and self._active_link is not None:
            link = {
                "text": " ".join(" ".join(self._active_link["parts"]).split()),
                "target": self._active_link["target"],
            }
            if self._semantic_stack and (link["text"] or link["target"]):
                self._semantic_stack[-1]["links"].append(link)
            self._active_link = None
        if tag == "caption" and self._current_caption is not None:
            self._current_caption = [
                " ".join(" ".join(self._current_caption).split())
            ]
        elif tag in {"td", "th"} and self._current_cell is not None and self._current_row is not None:
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
                self._ordered_content_blocks.append(
                    {
                        "kind": "table",
                        "table_ordinal": len(self.tables),
                        "rows": copy.deepcopy(self._current_table),
                    }
                )
                if self.capture_canonical_semantics:
                    block = {
                        "kind": "table",
                        "rows": copy.deepcopy(self._current_table),
                        "source_location": {
                            "kind": "html_table_rows",
                            "table_ordinal": len(self.tables),
                        },
                    }
                    caption = "".join(self._current_caption or [])
                    if caption:
                        block["caption"] = caption
                    self._semantic_blocks.append(block)
                self._current_table = None
                self._current_caption = None
            self._table_depth -= 1
        elif not self._table_depth and tag in {"p", "div", "li", "section", "h1", "h2", "h3"}:
            self._outside_parts.append("\n")
        if self.capture_canonical_semantics and tag in {
            "title",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "p",
            "li",
            "aside",
            "blockquote",
        }:
            self._finish_semantic_tag(tag)
        if self.capture_canonical_semantics and tag in {"ul", "ol"} and self._list_tags:
            self._list_tags.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            if self._skip_tags and self._skip_tags[-1] == "script":
                self.script_characters_total += len(data.strip())
            return
        text = " ".join(data.split())
        if not text:
            return
        if self._current_cell is not None:
            self._current_cell.append(text)
        elif self._current_caption is not None:
            self._current_caption.append(text)
        elif not self._table_depth:
            self._outside_parts.append(text)
            if self.capture_canonical_semantics and self._semantic_stack:
                self._semantic_stack[-1]["parts"].append(text)
            if self.capture_canonical_semantics and self._active_link is not None:
                self._active_link["parts"].append(text)

    def handle_comment(self, data: str) -> None:
        self.comment_elements_total += 1

    def format_reason_codes(self) -> list[str]:
        reasons = list(self.blocking_reason_codes())
        if self.embedded_media_elements_total and not self.embedded_media_reason_codes:
            reasons.append("html_embedded_media_visual_memory_review_required")
        reasons.extend(self.embedded_media_reason_codes)
        return sorted(set(reasons))

    def blocking_reason_codes(self) -> list[str]:
        reasons = list(self.embedded_media_reason_codes)
        if self.script_characters_total:
            reasons.append("html_script_content_outside_supported_profile")
        if self.nested_tables_total:
            reasons.append("html_nested_tables_outside_supported_profile")
        if self._skip_depth or self._table_depth or self._current_row is not None:
            reasons.append("html_structure_not_closed")
        return sorted(set(reasons))

    def _capture_data_image(self, source: str | None) -> None:
        if len(self.embedded_media) >= self.max_media_items:
            self.embedded_media_reason_codes.append(
                "html_embedded_media_count_budget_exceeded"
            )
            return
        match = re.fullmatch(
            r"data:(image/(?:png|jpeg|jpg|gif|webp));base64,([A-Za-z0-9+/=\s]+)",
            str(source or ""),
            flags=re.IGNORECASE,
        )
        if not match:
            self.embedded_media_reason_codes.append(
                "html_embedded_media_not_bounded_data_image"
            )
            return
        try:
            encoded_media = "".join(match.group(2).split())
            media_bytes = base64.b64decode(encoded_media, validate=True)
        except (ValueError, TypeError):
            self.embedded_media_reason_codes.append(
                "html_embedded_media_base64_invalid"
            )
            return
        if not media_bytes:
            self.embedded_media_reason_codes.append(
                "html_embedded_media_bytes_missing"
            )
            return
        if len(media_bytes) > self.max_media_bytes_per_item:
            self.embedded_media_reason_codes.append(
                "html_embedded_media_item_budget_exceeded"
            )
            return
        if (
            self.embedded_media_bytes_total + len(media_bytes)
            > self.max_media_bytes_per_document
        ):
            self.embedded_media_reason_codes.append(
                "html_embedded_media_document_budget_exceeded"
            )
            return
        self.embedded_media_bytes_total += len(media_bytes)
        media_type = match.group(1).lower().replace("image/jpg", "image/jpeg")
        self.embedded_media.append(
            {
                "media_type": media_type,
                "private_media_base64": base64.b64encode(media_bytes).decode("ascii"),
                "private_media_sha256": hashlib.sha256(media_bytes).hexdigest(),
            }
        )

    def safe_structural_inventory(self) -> dict[str, int | bool]:
        return {
            "tables_total": len(self.tables),
            "script_elements_total": self.script_elements_total,
            "script_characters_total": self.script_characters_total,
            "style_elements_total": self.style_elements_total,
            "comment_elements_total": self.comment_elements_total,
            "embedded_media_elements_total": self.embedded_media_elements_total,
            "embedded_media_captured_total": len(self.embedded_media),
            "embedded_media_bytes_total": self.embedded_media_bytes_total,
            "nested_tables_total": self.nested_tables_total,
            "link_elements_total": self.link_elements_total,
            "ordered_content_blocks_total": len(self.ordered_content_blocks()),
            "private_values_in_inventory": False,
        }

    def outside_text(self) -> str:
        return "\n".join(
            str(block["text"])
            for block in self.ordered_content_blocks()
            if block["kind"] == "text"
        )

    def ordered_content_blocks(self) -> list[dict[str, Any]]:
        self._flush_outside_block()
        return copy.deepcopy(self._ordered_content_blocks)

    def semantic_content_blocks(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self._semantic_blocks)

    def _finish_semantic_tag(self, tag: str) -> None:
        index = next(
            (
                position
                for position in range(len(self._semantic_stack) - 1, -1, -1)
                if self._semantic_stack[position]["tag"] == tag
            ),
            None,
        )
        if index is None:
            return
        item = self._semantic_stack.pop(index)
        text = " ".join(" ".join(item["parts"]).split())
        if not text:
            return
        if tag == "li":
            list_item = {
                "text": text,
                "level": int(item["list_level"]),
                "ordered": bool(item["ordered"]),
            }
            if (
                self._semantic_blocks
                and self._semantic_blocks[-1].get("kind") == "list"
            ):
                self._semantic_blocks[-1]["items"].append(list_item)
            else:
                self._semantic_blocks.append(
                    {
                        "kind": "list",
                        "items": [list_item],
                        "source_location": {"kind": "html_list"},
                    }
                )
            return
        if tag == "title" or tag.startswith("h"):
            level = 1 if tag == "title" else int(tag[1])
            kind = "heading"
        elif tag in {"aside", "blockquote"}:
            level = None
            kind = "note"
        else:
            level = None
            kind = "text"
        block = {
            "kind": kind,
            "text": text,
            "links": copy.deepcopy(item["links"]),
            "source_location": {"kind": f"html_{tag}"},
        }
        if level is not None:
            block["level"] = level
        self._semantic_blocks.append(block)

    def _flush_outside_block(self) -> None:
        lines = []
        for line in "\n".join(self._outside_parts).splitlines():
            clean = " ".join(line.split())
            if clean:
                lines.append(clean)
        self._outside_parts = []
        text = "\n".join(lines)
        if text:
            self._ordered_content_blocks.append({"kind": "text", "text": text})


def _canonical_csv_projection(content_bytes: bytes) -> dict[str, Any] | None:
    decoded, encoding, _error = decode_text_bytes(content_bytes)
    if decoded is None:
        return None
    sample = decoded[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    try:
        rows = [list(row) for row in csv.reader(StringIO(decoded, newline=""), dialect)]
    except csv.Error:
        return None
    try:
        header_present = bool(rows and csv.Sniffer().has_header(sample))
    except csv.Error:
        header_present = False
    header = rows[0] if header_present and rows else []
    return {
        "rows": rows,
        "encoding": encoding,
        "delimiter": str(dialect.delimiter),
        "quotechar": str(dialect.quotechar or '"'),
        "header_present": header_present,
        "duplicate_headers": len(header) != len(set(header)),
    }


def _canonical_xlsx_projection(
    *,
    workbook_root: ET.Element,
    sheet: ET.Element,
    sheet_root: ET.Element,
    sheet_index: int,
    rows: list[list[str | None]],
    shared_strings: list[str],
) -> dict[str, Any]:
    merged_ranges = [
        str(node.attrib.get("ref") or "")
        for node in _iter_local(sheet_root, "mergeCell")
        if node.attrib.get("ref")
    ]
    hidden_columns: set[int] = set()
    for column in _iter_local(sheet_root, "col"):
        if str(column.attrib.get("hidden") or "0") not in {"1", "true", "True"}:
            continue
        start = int(column.attrib.get("min") or 0)
        end = int(column.attrib.get("max") or start)
        hidden_columns.update(range(start, end + 1))
    cells: list[dict[str, Any]] = []
    for row_node in _iter_local(sheet_root, "row"):
        row_number = int(row_node.attrib.get("r") or 0)
        row_hidden = str(row_node.attrib.get("hidden") or "0") in {"1", "true", "True"}
        expected_column = 1
        for cell_node in _iter_local(row_node, "c"):
            cell_ref = str(cell_node.attrib.get("r") or "")
            column = _xlsx_column_ordinal(cell_ref) or expected_column
            expected_column = column + 1
            value_node = next(iter(_iter_local(cell_node, "v")), None)
            formula_node = next(iter(_iter_local(cell_node, "f")), None)
            raw_value = value_node.text if value_node is not None else None
            displayed_value = _xlsx_cell_value(cell_node, shared_strings)
            cell_type_code = str(cell_node.attrib.get("t") or "")
            if formula_node is not None:
                cell_type = "formula"
            elif cell_type_code == "b":
                cell_type = "boolean"
            elif cell_type_code == "e":
                cell_type = "error"
            elif cell_type_code in {"s", "str", "inlineStr"}:
                cell_type = "string"
            elif raw_value in {None, ""}:
                cell_type = "blank"
            else:
                try:
                    float(str(raw_value))
                    cell_type = "number"
                except ValueError:
                    cell_type = "string"
            merged_range = next(
                (item for item in merged_ranges if _cell_in_a1_range(cell_ref, item)),
                None,
            )
            cells.append(
                {
                    "row": row_number or 1,
                    "column": column,
                    "value": displayed_value,
                    "raw_value": raw_value,
                    "displayed_value": displayed_value,
                    "cell_type": cell_type,
                    "formula": formula_node.text if formula_node is not None else None,
                    "merged_range": merged_range,
                    "source_coordinate": cell_ref or f"R{row_number}C{column}",
                    "hidden": row_hidden or column in hidden_columns,
                    "number_format_ref": (
                        f"style:{cell_node.attrib['s']}"
                        if cell_node.attrib.get("s") is not None
                        else None
                    ),
                    "source_refs": [],
                }
            )
    named_ranges = [
        {
            "name": str(node.attrib.get("name") or ""),
            "formula": str(node.text or ""),
            "local_sheet_id": node.attrib.get("localSheetId"),
        }
        for node in _iter_local(workbook_root, "definedName")
        if node.attrib.get("name")
    ]
    table_definitions = [
        {"relationship_ref": str(node.attrib.get(_rel_attr("id")) or "")}
        for node in _iter_local(sheet_root, "tablePart")
        if node.attrib.get(_rel_attr("id"))
    ]
    return {
        "sheet_index": sheet_index,
        "sheet_name": str(sheet.attrib.get("name") or ""),
        "sheet_visibility": str(sheet.attrib.get("state") or "visible"),
        "rows": copy.deepcopy(rows),
        "cells": cells,
        "merged_ranges": merged_ranges,
        "named_ranges": named_ranges,
        "table_definitions": table_definitions,
    }


def _cell_in_a1_range(cell_ref: str, range_ref: str) -> bool:
    match = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", range_ref.upper())
    cell = re.fullmatch(r"([A-Z]+)(\d+)", cell_ref.upper())
    if match is None or cell is None:
        return cell_ref.upper() == range_ref.upper()
    column = _xlsx_column_ordinal(cell_ref) or 0
    start_column = _xlsx_column_ordinal(match.group(1)) or 0
    end_column = _xlsx_column_ordinal(match.group(3)) or 0
    row = int(cell.group(2))
    return start_column <= column <= end_column and int(match.group(2)) <= row <= int(match.group(4))


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
