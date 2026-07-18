from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from .contracts import stable_digest
from .pdf_layout import (
    PDF_LAYOUT_CAPABILITIES,
    PDF_LAYOUT_POLICY_VERSION,
    PDFMINER_PINNED_VERSION,
    PDFPLUMBER_PINNED_VERSION,
    PdfLayoutParserConfig,
    PdfPlumberLayoutAdapter,
)
from .pdf_layout_units import (
    PDF_LAYOUT_DOCUMENT_COVERAGE_SCHEMA_VERSION,
    PDF_LAYOUT_UNIT_COVERAGE_SCHEMA_VERSION,
    resolve_pdf_layout_unit_source_value,
)


FACTORY_REQUIRED = (
    "PdfTextLayerParserFactory.create is the only production PDF text-layer parser entrypoint"
)
FORBIDDEN = (
    "Full-source builders, profilers, Gate 2 callers and smoke scripts must not instantiate PypdfParserAdapter directly or PdfPlumberLayoutAdapter directly"
)

PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION = "pdf_text_layer_projection_v0"
PDF_TEXT_LAYER_COVERAGE_SCHEMA_VERSION = "pdf_text_layer_coverage_v0"
PDF_PARSER_POLICY_VERSION = "pypdf_page_text_policy_v0"
PYPDF_PINNED_VERSION = "6.7.5"
SUPPORTED_PDF_CAPABILITY = "page_text"
SUPPORTED_PDF_CAPABILITIES = frozenset(
    {SUPPORTED_PDF_CAPABILITY, *PDF_LAYOUT_CAPABILITIES}
)
PDF_SOURCE_UNIT_TYPES = {
    "pdf_page_text_unit",
    "pdf_line_cluster_unit",
    "pdf_table_candidate_unit",
    "pdf_visual_page_unit",
}


class PdfTextLayerParserError(RuntimeError):
    def __init__(self, code: str, message: str, *, status: str = "blocked") -> None:
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class PdfParserCapabilityRequest:
    capability: str = SUPPORTED_PDF_CAPABILITY


@dataclass(frozen=True)
class PdfTextLayerParserConfig:
    expected_pypdf_version: str = PYPDF_PINNED_VERSION
    max_document_bytes: int = 50_000_000
    max_pages: int = 2_000
    max_page_content_stream_bytes: int = 10_000_000
    max_page_text_characters: int = 200_000
    layout: PdfLayoutParserConfig = field(default_factory=PdfLayoutParserConfig)

    @property
    def config_ref(self) -> str:
        return _ref(
            "pdfparsercfg",
            PDF_PARSER_POLICY_VERSION,
            self.expected_pypdf_version,
            self.max_document_bytes,
            self.max_pages,
            self.max_page_content_stream_bytes,
            self.max_page_text_characters,
            length=20,
        )


@dataclass(frozen=True)
class PdfTextLayerParseResult:
    parser_engine: str
    parser_engine_version: str
    parser_config_ref: str
    parser_completeness_status: str
    parser_completeness_reason_codes: list[str]
    pdf_content_kind: str
    text_layer_projection_status: str
    visible_content_coverage_status: str
    semantic_reconstruction_status: str
    pages: list[dict[str, Any]]
    diagnostics: dict[str, Any]


class PdfTextLayerParserFactory:
    def __init__(self, config: PdfTextLayerParserConfig | None = None) -> None:
        self.config = config or PdfTextLayerParserConfig()

    def create(
        self,
        request: PdfParserCapabilityRequest | None = None,
    ) -> "PypdfParserAdapter | PdfPlumberLayoutAdapter":
        request = request or PdfParserCapabilityRequest()
        if request.capability not in SUPPORTED_PDF_CAPABILITIES:
            raise PdfTextLayerParserError(
                "pdf_parser_capability_unsupported",
                "Requested PDF parser capability is unsupported and will not be downgraded",
            )
        if request.capability in PDF_LAYOUT_CAPABILITIES:
            return self._create_layout_adapter(request)
        for value, code in (
            (self.config.max_document_bytes, "pdf_document_budget_invalid"),
            (self.config.max_pages, "pdf_page_budget_invalid"),
            (
                self.config.max_page_content_stream_bytes,
                "pdf_page_content_stream_budget_invalid",
            ),
            (self.config.max_page_text_characters, "pdf_page_text_budget_invalid"),
        ):
            if value <= 0:
                raise PdfTextLayerParserError(code, "PDF parser budgets must be positive")
        try:
            pypdf = importlib.import_module("pypdf")
        except ModuleNotFoundError as exc:
            raise PdfTextLayerParserError(
                "pdf_pypdf_runtime_unavailable",
                "Pinned pypdf runtime is unavailable",
            ) from exc
        version = str(getattr(pypdf, "__version__", "") or "")
        if version != self.config.expected_pypdf_version:
            raise PdfTextLayerParserError(
                "pdf_pypdf_runtime_version_mismatch",
                "Pinned pypdf runtime version does not match",
            )
        return PypdfParserAdapter(
            pypdf_module=pypdf,
            config=self.config,
            request=request,
        )

    def _create_layout_adapter(
        self,
        request: PdfParserCapabilityRequest,
    ) -> PdfPlumberLayoutAdapter:
        layout = self.config.layout
        for value, code in (
            (layout.max_document_bytes, "pdf_layout_document_budget_invalid"),
            (layout.max_pages, "pdf_layout_page_budget_invalid"),
            (layout.max_chars_per_page, "pdf_layout_char_budget_invalid"),
            (layout.max_words_per_page, "pdf_layout_word_budget_invalid"),
            (layout.max_lines_per_page, "pdf_layout_line_budget_invalid"),
            (
                layout.max_vector_objects_per_page,
                "pdf_layout_vector_object_budget_invalid",
            ),
            (
                layout.max_inventory_objects_per_document,
                "pdf_layout_document_inventory_budget_invalid",
            ),
            (
                layout.max_table_candidates_per_page,
                "pdf_layout_table_candidate_budget_invalid",
            ),
            (
                layout.max_table_detection_words_per_page,
                "pdf_layout_table_detection_word_budget_invalid",
            ),
            (
                layout.max_table_detection_vector_objects_per_page,
                "pdf_layout_table_detection_vector_budget_invalid",
            ),
            (layout.max_seconds_per_page, "pdf_layout_time_budget_invalid"),
        ):
            if value <= 0:
                raise PdfTextLayerParserError(
                    code, "PDF layout parser budgets must be positive"
                )
        try:
            pdfplumber = importlib.import_module("pdfplumber")
            pdfminer = importlib.import_module("pdfminer")
        except ModuleNotFoundError as exc:
            raise PdfTextLayerParserError(
                "pdf_layout_runtime_unavailable",
                "Pinned pdfplumber/pdfminer runtime is unavailable",
            ) from exc
        pdfplumber_version = str(getattr(pdfplumber, "__version__", "") or "")
        pdfminer_version = str(getattr(pdfminer, "__version__", "") or "")
        if pdfplumber_version != layout.expected_pdfplumber_version:
            raise PdfTextLayerParserError(
                "pdf_layout_pdfplumber_version_mismatch",
                "Pinned pdfplumber runtime version does not match",
            )
        if pdfminer_version != layout.expected_pdfminer_version:
            raise PdfTextLayerParserError(
                "pdf_layout_pdfminer_version_mismatch",
                "Pinned pdfminer.six runtime version does not match",
            )
        return PdfPlumberLayoutAdapter(
            pdfplumber_module=pdfplumber,
            pdfminer_module=pdfminer,
            config=layout,
            requested_capability=request.capability,
        )


class PypdfParserAdapter:
    def __init__(
        self,
        *,
        pypdf_module: Any,
        config: PdfTextLayerParserConfig,
        request: PdfParserCapabilityRequest,
    ) -> None:
        self._pypdf = pypdf_module
        self.config = config
        self.request = request

    def parse(self, content_bytes: bytes) -> PdfTextLayerParseResult:
        if not content_bytes.startswith(b"%PDF-"):
            return self._terminal_result("blocked", ["pdf_header_missing"])
        if len(content_bytes) > self.config.max_document_bytes:
            return self._terminal_result(
                "partial",
                ["pdf_document_budget_exceeded"],
            )
        try:
            reader = self._pypdf.PdfReader(BytesIO(content_bytes), strict=False)
        except Exception:
            return self._terminal_result(
                "blocked",
                ["pdf_corrupt_or_unreadable"],
            )
        if bool(getattr(reader, "is_encrypted", False)):
            return self._terminal_result(
                "blocked",
                ["pdf_encrypted_without_key"],
            )
        try:
            pages_total = len(reader.pages)
        except Exception:
            return self._terminal_result(
                "blocked",
                ["pdf_page_inventory_unavailable"],
            )
        if pages_total <= 0:
            return self._terminal_result("partial", ["pdf_page_inventory_empty"])
        if pages_total > self.config.max_pages:
            return self._terminal_result("partial", ["pdf_page_budget_exceeded"])

        pages: list[dict[str, Any]] = []
        document_reasons: list[str] = []
        try:
            embedded_attachments_total = sum(1 for _ in reader.attachment_list)
        except Exception:
            embedded_attachments_total = 0
            document_reasons.append("pdf_attachment_inventory_unavailable")
        if embedded_attachments_total:
            document_reasons.append("pdf_embedded_attachments_not_supported")
        for page_index, page in enumerate(reader.pages, start=1):
            page_result = self._parse_page(page=page, page_number=page_index)
            pages.append(page_result)
            document_reasons.extend(page_result["reason_codes"])

        text_pages = sum(1 for page in pages if page.get("text", "").strip())
        image_pages = sum(1 for page in pages if int(page.get("image_objects_total") or 0) > 0)
        mixed_pages = sum(
            1
            for page in pages
            if page.get("text", "").strip()
            and int(page.get("image_objects_total") or 0) > 0
        )
        if text_pages == 0:
            document_reasons.append("pdf_no_text_layer")
        reasons = sorted(set(document_reasons))
        status = "complete" if not reasons else "partial"
        if text_pages and image_pages:
            content_kind = "mixed_pdf_with_text"
        elif text_pages:
            content_kind = "text_layer_pdf"
        elif image_pages:
            content_kind = "raster_pdf_or_image_only"
        else:
            content_kind = "parser_partial_pdf"
        return PdfTextLayerParseResult(
            parser_engine="pypdf",
            parser_engine_version=self.config.expected_pypdf_version,
            parser_config_ref=self.config.config_ref,
            parser_completeness_status=status,
            parser_completeness_reason_codes=reasons,
            pdf_content_kind=content_kind,
            text_layer_projection_status=status,
            visible_content_coverage_status=(
                "partial_out_of_scope" if image_pages else "complete_text_only"
            ),
            semantic_reconstruction_status="not_claimed",
            pages=pages,
            diagnostics={
                "pages_total": pages_total,
                "pages_with_text": text_pages,
                "pages_without_text": pages_total - text_pages,
                "pages_with_images": image_pages,
                "mixed_text_image_pages": mixed_pages,
                "page_parse_errors": sum(
                    1 for page in pages if page.get("page_projection_status") != "complete"
                ),
                "text_fragments_total": sum(
                    len(page.get("parser_fragments") or []) for page in pages
                ),
                "text_characters_total": sum(len(str(page.get("text") or "")) for page in pages),
                "replacement_characters_total": sum(
                    int(page.get("replacement_characters_total") or 0) for page in pages
                ),
                "unknown_font_fragments_total": sum(
                    int(page.get("unknown_font_fragments_total") or 0) for page in pages
                ),
                "embedded_attachments_total": embedded_attachments_total,
            },
        )

    def _parse_page(self, *, page: Any, page_number: int) -> dict[str, Any]:
        reasons: list[str] = []
        try:
            contents = page.get_contents()
            content_data = contents.get_data() if contents is not None else b""
        except Exception:
            return self._page_failure(page_number, "pdf_page_content_stream_unavailable")
        content_stream_bytes = len(content_data)
        if content_stream_bytes > self.config.max_page_content_stream_bytes:
            return self._page_failure(page_number, "pdf_content_stream_budget_exceeded")

        parser_fragments: list[dict[str, Any]] = []
        unknown_font_fragments = 0

        def visitor_text(
            text: str,
            user_matrix: Any,
            text_matrix: Any,
            font_dictionary: Any,
            font_size: Any,
        ) -> None:
            nonlocal unknown_font_fragments
            if not text:
                return
            if text.strip() and font_dictionary is None:
                unknown_font_fragments += 1
            parser_fragments.append(
                {
                    "parser_ordinal": len(parser_fragments) + 1,
                    "text": text,
                    "raw_text_checksum_ref": _checksum_ref("pdfrawtxtchk", text),
                    "user_matrix": _numeric_matrix(user_matrix),
                    "text_matrix": _numeric_matrix(text_matrix),
                    "font_known": font_dictionary is not None,
                    "font_size": _finite_number(font_size),
                    "coordinate_confidence": "parser_reported_unverified",
                }
            )

        try:
            extracted_text = page.extract_text(visitor_text=visitor_text) or ""
        except Exception:
            return self._page_failure(page_number, "pdf_page_parse_failed")

        visitor_text_projection = "".join(
            str(fragment.get("text") or "") for fragment in parser_fragments
        )
        if visitor_text_projection != extracted_text:
            reasons.append("pdf_page_projection_reconciliation_failed")
        if len(extracted_text) > self.config.max_page_text_characters:
            reasons.append("pdf_page_text_budget_exceeded")
        replacement_characters = extracted_text.count("\ufffd")
        if replacement_characters:
            reasons.append("pdf_text_operator_decode_incomplete")
        if unknown_font_fragments:
            reasons.append("pdf_unknown_font_mapping")

        text_operator_count = _text_showing_operator_count(contents)
        image_objects_total = _count_image_objects(page)
        has_text = bool(extracted_text.strip())
        if not has_text and image_objects_total:
            reasons.append("pdf_image_only_no_text_layer")
            page_kind = "image_only"
        elif not has_text and text_operator_count:
            reasons.append("pdf_text_operator_decode_incomplete")
            page_kind = "partial"
        elif not has_text:
            page_kind = "blank"
        elif image_objects_total:
            page_kind = "mixed"
        else:
            page_kind = "text"

        return {
            "page_number": page_number,
            "page_content_kind": page_kind,
            "page_projection_status": "complete" if not reasons else "partial",
            "reason_codes": sorted(set(reasons)),
            "text": extracted_text,
            "parser_fragments": parser_fragments,
            "content_stream_bytes": content_stream_bytes,
            "text_showing_operators_total": text_operator_count,
            "image_objects_total": image_objects_total,
            "replacement_characters_total": replacement_characters,
            "unknown_font_fragments_total": unknown_font_fragments,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
        }

    def _page_failure(self, page_number: int, reason: str) -> dict[str, Any]:
        return {
            "page_number": page_number,
            "page_content_kind": "partial",
            "page_projection_status": "partial",
            "reason_codes": [reason],
            "text": "",
            "parser_fragments": [],
            "content_stream_bytes": 0,
            "text_showing_operators_total": 0,
            "image_objects_total": 0,
            "replacement_characters_total": 0,
            "unknown_font_fragments_total": 0,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
        }

    def _terminal_result(
        self,
        status: str,
        reasons: list[str],
    ) -> PdfTextLayerParseResult:
        return PdfTextLayerParseResult(
            parser_engine="pypdf",
            parser_engine_version=self.config.expected_pypdf_version,
            parser_config_ref=self.config.config_ref,
            parser_completeness_status=status,
            parser_completeness_reason_codes=sorted(set(reasons)),
            pdf_content_kind=(
                "encrypted_or_corrupt" if status == "blocked" else "parser_partial_pdf"
            ),
            text_layer_projection_status=status,
            visible_content_coverage_status="unknown",
            semantic_reconstruction_status="not_claimed",
            pages=[],
            diagnostics={
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
                "embedded_attachments_total": 0,
            },
        )


def pdf_page_checksum_ref(page: dict[str, Any], parser_ref: str) -> str:
    return _checksum_ref(
        "pdfpagechk",
        {
            "parser_ref": parser_ref,
            "page_ref": page.get("page_ref"),
            "page_number": page.get("page_number"),
            "page_content_kind": page.get("page_content_kind"),
            "page_projection_status": page.get("page_projection_status"),
            "reason_codes": list(page.get("reason_codes") or []),
            "text": str(page.get("text") or ""),
            "parser_fragments": list(page.get("parser_fragments") or []),
            "text_segment_refs": list(page.get("text_segment_refs") or []),
            "character_span_refs": list(page.get("character_span_refs") or []),
            "source_value_refs": list(page.get("source_value_refs") or []),
            "content_stream_bytes": int(page.get("content_stream_bytes") or 0),
            "text_showing_operators_total": int(
                page.get("text_showing_operators_total") or 0
            ),
            "image_objects_total": int(page.get("image_objects_total") or 0),
            "visual_page_ref": page.get("visual_page_ref"),
            "visual_media_ref": page.get("visual_media_ref"),
            "visual_media_checksum_ref": page.get("visual_media_checksum_ref"),
            "visual_width_pixels": page.get("visual_width_pixels"),
            "visual_height_pixels": page.get("visual_height_pixels"),
            "page_rendering_used_for_extraction": bool(
                page.get("page_rendering_used_for_extraction")
            ),
        },
    )


def pdf_layout_page_checksum_ref(page: dict[str, Any], layout_parser_ref: str) -> str:
    return _checksum_ref(
        "pdflayoutpagechk",
        {
            "layout_parser_ref": layout_parser_ref,
            "page_ref": page.get("page_ref"),
            "page_number": page.get("page_number"),
            "layout_projection_status": page.get("layout_projection_status"),
            "layout_reason_codes": list(page.get("layout_reason_codes") or []),
            "layout_char_refs": list(page.get("layout_char_refs") or []),
            "layout_word_refs": list(page.get("layout_word_refs") or []),
            "layout_line_refs": list(page.get("layout_line_refs") or []),
            "layout_block_refs": list(page.get("layout_block_refs") or []),
            "table_candidate_refs": list(page.get("table_candidate_refs") or []),
            "parser_order_word_refs": list(page.get("parser_order_word_refs") or []),
            "geometry_reading_order_refs": list(
                page.get("geometry_reading_order_refs") or []
            ),
            "duplicate_chars_total": int(page.get("duplicate_chars_total") or 0),
            "rotated_chars_total": int(page.get("rotated_chars_total") or 0),
            "layout_page_width": page.get("layout_page_width"),
            "layout_page_height": page.get("layout_page_height"),
            "layout_page_rotation": page.get("layout_page_rotation"),
        },
    )


def pdf_payload_checksum_ref(payload: dict[str, Any]) -> str:
    projection = _object(payload.get("pdf_text_layer_projection"))
    return _checksum_ref(
        "srcpayloadchk",
        {
            "source_payload_ref": payload.get("source_payload_ref"),
            "source_checksum_ref": payload.get("source_checksum_ref"),
            "parser_ref": payload.get("parser_ref"),
            "parser_engine": projection.get("parser_engine"),
            "parser_engine_version": projection.get("parser_engine_version"),
            "parser_config_ref": projection.get("parser_config_ref"),
            "projection_policy_ref": projection.get("projection_policy_ref"),
            "parser_completeness_status": payload.get("parser_completeness_status"),
            "parser_completeness_reason_codes": list(
                payload.get("parser_completeness_reason_codes") or []
            ),
            "text_layer_projection_status": projection.get(
                "text_layer_projection_status"
            ),
            "visible_content_coverage_status": projection.get(
                "visible_content_coverage_status"
            ),
            "semantic_reconstruction_status": projection.get(
                "semantic_reconstruction_status"
            ),
            "declared_page_range": projection.get("declared_page_range"),
            "page_checksum_refs": list(projection.get("page_checksum_refs") or []),
            "coverage_ref": _object(projection.get("coverage")).get("coverage_ref"),
            "layout_parser_ref": projection.get("layout_parser_ref"),
            "layout_parser_engine": projection.get("layout_parser_engine"),
            "layout_parser_engine_version": projection.get(
                "layout_parser_engine_version"
            ),
            "layout_underlying_engine": projection.get("layout_underlying_engine"),
            "layout_underlying_engine_version": projection.get(
                "layout_underlying_engine_version"
            ),
            "layout_parser_config_ref": projection.get("layout_parser_config_ref"),
            "layout_projection_status": projection.get("layout_projection_status"),
            "table_candidate_status": projection.get("table_candidate_status"),
            "layout_page_checksum_refs": list(
                projection.get("layout_page_checksum_refs") or []
            ),
            "layout_coverage_ref": _object(
                projection.get("layout_coverage")
            ).get("coverage_ref"),
            "layout_unit_config_ref": projection.get("layout_unit_config_ref"),
            "visual_fallback_status": projection.get("visual_fallback_status"),
            "visual_page_refs": [
                str(item.get("visual_page_ref") or "")
                for item in _dict_list(projection.get("visual_page_inventory"))
            ],
        },
    )


def validate_pdf_text_layer_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    payload_ref = str(payload.get("source_payload_ref") or "")
    projection = _object(payload.get("pdf_text_layer_projection"))
    if projection.get("schema_version") != PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION:
        errors.append(_error("pdf_projection_schema_mismatch", payload_ref))
    if projection.get("requested_capability") != SUPPORTED_PDF_CAPABILITY:
        errors.append(_error("pdf_projection_capability_mismatch", payload_ref))
    if projection.get("parser_engine") != "pypdf":
        errors.append(_error("pdf_projection_engine_mismatch", payload_ref))
    if projection.get("parser_engine_version") != PYPDF_PINNED_VERSION:
        errors.append(_error("pdf_projection_engine_version_mismatch", payload_ref))
    if payload.get("ocr_vlm_used") is not False or projection.get("ocr_vlm_used") is not False:
        errors.append(_error("pdf_projection_ocr_guard_failed", payload_ref))
    visual_status = str(projection.get("visual_fallback_status") or "not_required")
    rendering_used = bool(projection.get("page_rendering_used_for_extraction"))
    if bool(payload.get("page_rendering_used_for_extraction")) != rendering_used:
        errors.append(_error("pdf_projection_rendering_status_mismatch", payload_ref))
    if rendering_used != (visual_status == "complete"):
        errors.append(_error("pdf_projection_visual_fallback_status_invalid", payload_ref))

    pages = _dict_list(projection.get("page_inventory"))
    declared = _object(projection.get("declared_page_range"))
    pages_total = int(declared.get("pages_total") or 0)
    if pages_total != len(pages):
        errors.append(_error("pdf_projection_page_count_mismatch", payload_ref))
    expected_ordinals = list(range(1, len(pages) + 1))
    actual_ordinals = [int(page.get("page_number") or 0) for page in pages]
    if actual_ordinals != expected_ordinals:
        errors.append(_error("pdf_projection_page_order_mismatch", payload_ref))
    page_refs = [str(page.get("page_ref") or "") for page in pages]
    if not all(page_refs) or len(page_refs) != len(set(page_refs)):
        errors.append(_error("pdf_projection_page_ref_invalid", payload_ref))
    expected_page_checksums = [
        pdf_page_checksum_ref(
            page,
            str(
                projection.get("page_text_parser_ref")
                or payload.get("parser_ref")
                or ""
            ),
        )
        for page in pages
    ]
    actual_page_checksums = [str(page.get("page_text_checksum_ref") or "") for page in pages]
    if actual_page_checksums != expected_page_checksums:
        errors.append(_error("pdf_projection_page_checksum_mismatch", payload_ref))
    if list(projection.get("page_checksum_refs") or []) != actual_page_checksums:
        errors.append(_error("pdf_projection_page_checksum_inventory_mismatch", payload_ref))
    visual_inventory = _dict_list(projection.get("visual_page_inventory"))
    visual_page_refs = [str(item.get("visual_page_ref") or "") for item in visual_inventory]
    visual_media_refs = [str(item.get("media_ref") or "") for item in visual_inventory]
    if visual_status == "complete":
        if not visual_inventory:
            errors.append(_error("pdf_visual_inventory_empty", payload_ref))
        if not all(visual_page_refs) or len(visual_page_refs) != len(set(visual_page_refs)):
            errors.append(_error("pdf_visual_page_ref_invalid", payload_ref))
        if not all(visual_media_refs) or len(visual_media_refs) != len(set(visual_media_refs)):
            errors.append(_error("pdf_visual_media_ref_invalid", payload_ref))
        inventory_by_page = {
            int(item.get("page_number") or 0): item for item in visual_inventory
        }
        for page in pages:
            page_number = int(page.get("page_number") or 0)
            visual = inventory_by_page.get(page_number)
            needs_visual = (
                not str(page.get("text") or "").strip()
                or int(page.get("image_objects_total") or 0) > 0
            )
            if needs_visual and visual is None:
                errors.append(_error("pdf_visual_page_coverage_incomplete", page_number))
            if visual is not None and (
                page.get("visual_page_ref") != visual.get("visual_page_ref")
                or page.get("visual_media_ref") != visual.get("media_ref")
                or page.get("visual_media_checksum_ref")
                != visual.get("media_checksum_ref")
            ):
                errors.append(_error("pdf_visual_page_inventory_mismatch", page_number))

    layout_requested = projection.get("layout_requested_capability")
    if layout_requested is not None:
        if layout_requested not in PDF_LAYOUT_CAPABILITIES:
            errors.append(_error("pdf_layout_capability_mismatch", payload_ref))
        if projection.get("layout_parser_engine") != "pdfplumber":
            errors.append(_error("pdf_layout_engine_mismatch", payload_ref))
        if projection.get("layout_parser_engine_version") != PDFPLUMBER_PINNED_VERSION:
            errors.append(_error("pdf_layout_engine_version_mismatch", payload_ref))
        if projection.get("layout_underlying_engine") != "pdfminer.six":
            errors.append(_error("pdf_layout_underlying_engine_mismatch", payload_ref))
        if (
            projection.get("layout_underlying_engine_version")
            != PDFMINER_PINNED_VERSION
        ):
            errors.append(
                _error("pdf_layout_underlying_engine_version_mismatch", payload_ref)
            )
        layout_parser_ref = str(projection.get("layout_parser_ref") or "")
        if not layout_parser_ref or not projection.get("layout_parser_config_ref"):
            errors.append(_error("pdf_layout_parser_ref_missing", payload_ref))
        expected_layout_checksums = [
            pdf_layout_page_checksum_ref(page, layout_parser_ref) for page in pages
        ]
        actual_layout_checksums = [
            str(page.get("page_layout_checksum_ref") or "") for page in pages
        ]
        if actual_layout_checksums != expected_layout_checksums:
            errors.append(_error("pdf_layout_page_checksum_mismatch", payload_ref))
        if (
            list(projection.get("layout_page_checksum_refs") or [])
            != actual_layout_checksums
        ):
            errors.append(
                _error("pdf_layout_page_checksum_inventory_mismatch", payload_ref)
            )
        word_inventory = _dict_list(projection.get("word_inventory"))
        line_inventory = _dict_list(projection.get("line_inventory"))
        char_inventory = _dict_list(projection.get("char_inventory"))
        block_inventory = _dict_list(projection.get("block_inventory"))
        table_inventory = _dict_list(projection.get("table_candidate_inventory"))
        for inventory, ref_name, code in (
            (char_inventory, "char_ref", "pdf_layout_char_ref_invalid"),
            (word_inventory, "word_ref", "pdf_layout_word_ref_invalid"),
            (line_inventory, "line_ref", "pdf_layout_line_ref_invalid"),
            (block_inventory, "block_ref", "pdf_layout_block_ref_invalid"),
            (
                table_inventory,
                "table_candidate_ref",
                "pdf_layout_table_candidate_ref_invalid",
            ),
        ):
            refs = [str(item.get(ref_name) or "") for item in inventory]
            if not all(refs) or len(refs) != len(set(refs)):
                errors.append(_error(code, payload_ref))
            if any(str(item.get("page_ref") or "") not in set(page_refs) for item in inventory):
                errors.append(_error(f"{code}_page_scope", payload_ref))
        word_refs = {str(item.get("word_ref") or "") for item in word_inventory}
        line_refs = {str(item.get("line_ref") or "") for item in line_inventory}
        for line in line_inventory:
            if not set(str(ref) for ref in line.get("word_refs") or []) <= word_refs:
                errors.append(_error("pdf_layout_line_word_ref_out_of_scope", payload_ref))
        for candidate in table_inventory:
            if candidate.get("table_reconstruction_status") != "candidate":
                errors.append(_error("pdf_table_candidate_status_invalid", payload_ref))
            if candidate.get("semantic_table_truth_claimed") is not False:
                errors.append(_error("pdf_table_candidate_semantic_truth_claimed", payload_ref))
            if not set(
                str(ref) for ref in candidate.get("contributing_word_refs") or []
            ) <= word_refs:
                errors.append(
                    _error("pdf_table_candidate_word_ref_out_of_scope", payload_ref)
                )
            if not set(
                str(ref) for ref in candidate.get("fallback_text_refs") or []
            ) <= line_refs:
                errors.append(
                    _error("pdf_table_candidate_fallback_ref_out_of_scope", payload_ref)
                )
        layout_coverage = _object(projection.get("layout_coverage"))
        if (
            layout_coverage.get("schema_version")
            != PDF_LAYOUT_DOCUMENT_COVERAGE_SCHEMA_VERSION
        ):
            errors.append(_error("pdf_layout_coverage_schema_mismatch", payload_ref))
        layout_selected = list(layout_coverage.get("selected_source_refs") or [])
        layout_accounted = list(layout_coverage.get("accounted_source_refs") or [])
        expected_layout_selected = [
            *[str(item.get("word_ref") or "") for item in word_inventory],
            *[str(item.get("line_ref") or "") for item in line_inventory],
        ]
        if layout_selected != expected_layout_selected:
            errors.append(_error("pdf_layout_selected_refs_mismatch", payload_ref))
        layout_status = projection.get("layout_projection_status")
        if len(layout_accounted) != len(set(layout_accounted)):
            errors.append(_error("pdf_layout_coverage_duplicate_ref", payload_ref))
        if layout_status == "complete":
            if sorted(layout_selected) != sorted(layout_accounted):
                errors.append(_error("pdf_layout_selected_accounted_mismatch", payload_ref))
            if layout_coverage.get("all_selected_refs_accounted") is not True:
                errors.append(_error("pdf_layout_coverage_incomplete", payload_ref))
            if any(
                page.get("layout_projection_status") != "complete" for page in pages
            ):
                errors.append(_error("pdf_layout_complete_page_status_mismatch", payload_ref))
        else:
            if not set(layout_accounted) <= set(layout_selected):
                errors.append(_error("pdf_layout_partial_accounted_ref_out_of_scope", payload_ref))
            if sorted(layout_coverage.get("unaccounted_refs") or []) != sorted(
                set(layout_selected) - set(layout_accounted)
            ):
                errors.append(_error("pdf_layout_partial_unaccounted_refs_mismatch", payload_ref))
        if projection.get("table_candidate_status") == "candidate":
            if not table_inventory:
                errors.append(_error("pdf_table_candidate_inventory_empty", payload_ref))
            if projection.get("semantic_reconstruction_status") != "candidate":
                errors.append(_error("pdf_table_semantic_candidate_status_mismatch", payload_ref))

    coverage = _object(projection.get("coverage"))
    if coverage.get("schema_version") != PDF_TEXT_LAYER_COVERAGE_SCHEMA_VERSION:
        errors.append(_error("pdf_projection_coverage_schema_mismatch", payload_ref))
    if list(coverage.get("declared_page_refs") or []) != page_refs:
        errors.append(_error("pdf_projection_declared_page_refs_mismatch", payload_ref))
    if list(coverage.get("accounted_page_refs") or []) != page_refs:
        errors.append(_error("pdf_projection_accounted_page_refs_mismatch", payload_ref))
    if coverage.get("all_declared_pages_accounted") is not True:
        errors.append(_error("pdf_projection_page_coverage_incomplete", payload_ref))
    selected_refs = list(coverage.get("selected_text_refs") or [])
    accounted_refs = [
        *list(coverage.get("text_candidate_refs") or []),
        *list(coverage.get("blank_or_layout_refs") or []),
        *list(coverage.get("non_text_page_refs") or []),
        *list(coverage.get("partial_or_rejected_refs") or []),
    ]
    if len(accounted_refs) != len(set(accounted_refs)):
        errors.append(_error("pdf_projection_coverage_duplicate_ref", payload_ref))
    if sorted(selected_refs) != sorted(accounted_refs):
        errors.append(_error("pdf_projection_selected_accounted_mismatch", payload_ref))
    if coverage.get("all_selected_refs_accounted") is not True:
        errors.append(_error("pdf_projection_selected_coverage_incomplete", payload_ref))

    source_value_refs = list(payload.get("source_value_refs") or [])
    source_value_index = _dict_list(payload.get("source_value_index"))
    if len(source_value_refs) != len(set(source_value_refs)):
        errors.append(_error("pdf_projection_source_value_ref_duplicate", payload_ref))
    index_by_ref: dict[str, list[dict[str, Any]]] = {}
    for entry in source_value_index:
        index_by_ref.setdefault(str(entry.get("source_value_ref") or ""), []).append(entry)
    for source_value_ref in source_value_refs:
        entries = index_by_ref.get(str(source_value_ref), [])
        if len(entries) != 1:
            errors.append(_error("pdf_source_value_ref_not_unique_or_missing", source_value_ref))
            continue
        try:
            value = resolve_pdf_payload_source_value(payload, entries[0])
        except ValueError as exc:
            errors.append(_error(str(exc), source_value_ref))
            continue
        if entries[0].get("value_checksum_ref") != _checksum_ref("valuechk", value):
            errors.append(_error("pdf_source_value_checksum_mismatch", source_value_ref))

    expected_payload_checksum = pdf_payload_checksum_ref(payload)
    if payload.get("payload_checksum_ref") != expected_payload_checksum:
        errors.append(_error("pdf_projection_payload_checksum_mismatch", payload_ref))
    if payload.get("parser_completeness_status") == "complete":
        if (
            projection.get("text_layer_projection_status") != "complete"
            and visual_status != "complete"
        ):
            errors.append(_error("pdf_projection_complete_status_mismatch", payload_ref))
        if payload.get("parser_completeness_reason_codes"):
            errors.append(_error("pdf_projection_complete_has_reasons", payload_ref))
        if not payload.get("extraction_unit_refs"):
            errors.append(_error("pdf_projection_complete_without_units", payload_ref))
    return {
        "schema_version": "pdf_text_layer_payload_validation_v0",
        "source_payload_ref": payload_ref,
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "errors_count": len(errors),
        "errors": errors,
    }


def validate_pdf_source_unit(
    unit: dict[str, Any],
    *,
    parent_payload: dict[str, Any] | None = None,
    require_parent_payload: bool = False,
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    unit_ref = str(unit.get("unit_ref") or "")
    if unit.get("pdf_unit_type") not in PDF_SOURCE_UNIT_TYPES:
        errors.append(_error("pdf_source_unit_type_invalid", unit_ref))
    if unit.get("pdf_projection_schema_version") != PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION:
        errors.append(_error("pdf_source_unit_projection_schema_mismatch", unit_ref))
    visual_unit = unit.get("pdf_unit_type") == "pdf_visual_page_unit"
    if unit.get("ocr_vlm_used") is not False:
        errors.append(_error("pdf_source_unit_ocr_guard_failed", unit_ref))
    if visual_unit:
        if unit.get("page_rendering_used_for_extraction") is not True:
            errors.append(_error("pdf_visual_source_unit_rendering_missing", unit_ref))
        if unit.get("media_type") != "image/png":
            errors.append(_error("pdf_visual_source_unit_media_type_invalid", unit_ref))
        if not unit.get("media_ref") or not unit.get("media_checksum_ref"):
            errors.append(_error("pdf_visual_source_unit_media_ref_missing", unit_ref))
        if unit.get("financial_interpretation_restricted") is not True:
            errors.append(_error("pdf_visual_source_unit_scope_not_restricted", unit_ref))
    elif unit.get("page_rendering_used_for_extraction") is not False:
        errors.append(_error("pdf_source_unit_rendering_guard_failed", unit_ref))
    if unit.get("parent_source_slice_truncated") is not False:
        errors.append(_error("pdf_source_unit_parent_truncated", unit_ref))
    if not list(unit.get("page_refs") or []):
        errors.append(_error("pdf_source_unit_page_ref_missing", unit_ref))
    if not visual_unit and not list(unit.get("text_segment_refs") or []):
        errors.append(_error("pdf_source_unit_text_refs_missing", unit_ref))
    coverage = _object(unit.get("coverage"))
    if coverage.get("selected_total") != coverage.get("accounted_total"):
        errors.append(_error("pdf_source_unit_coverage_count_mismatch", unit_ref))
    if coverage.get("all_selected_refs_accounted") is not True:
        errors.append(_error("pdf_source_unit_coverage_incomplete", unit_ref))
    unit_type = unit.get("pdf_unit_type")
    if unit_type in {"pdf_line_cluster_unit", "pdf_table_candidate_unit"}:
        if unit.get("layout_projection_status") != "complete":
            errors.append(_error("pdf_layout_source_unit_projection_not_complete", unit_ref))
        layout_coverage = _object(unit.get("pdf_layout_coverage"))
        if (
            layout_coverage.get("schema_version")
            != PDF_LAYOUT_UNIT_COVERAGE_SCHEMA_VERSION
        ):
            errors.append(_error("pdf_layout_source_unit_coverage_schema_mismatch", unit_ref))
        selected = list(layout_coverage.get("selected_source_refs") or [])
        accounted = list(layout_coverage.get("accounted_source_refs") or [])
        if not selected or sorted(selected) != sorted(accounted):
            errors.append(_error("pdf_layout_source_unit_coverage_refs_mismatch", unit_ref))
        if len(accounted) != len(set(accounted)):
            errors.append(_error("pdf_layout_source_unit_coverage_duplicate_ref", unit_ref))
        if layout_coverage.get("all_selected_refs_accounted") is not True:
            errors.append(_error("pdf_layout_source_unit_coverage_incomplete", unit_ref))
        supplemental_refs = list(unit.get("pdf_layout_source_value_refs") or [])
        if not supplemental_refs or len(supplemental_refs) != len(set(supplemental_refs)):
            errors.append(_error("pdf_layout_source_unit_value_refs_invalid", unit_ref))
        for source_value_ref in supplemental_refs:
            try:
                resolve_pdf_layout_unit_source_value(unit, str(source_value_ref))
            except ValueError as exc:
                errors.append(_error(str(exc), source_value_ref))
        if unit.get("semantic_table_truth_claimed") is not False:
            errors.append(_error("pdf_layout_source_unit_semantic_truth_claimed", unit_ref))
        if unit_type == "pdf_table_candidate_unit":
            if unit.get("table_reconstruction_status") != "candidate":
                errors.append(_error("pdf_table_source_unit_status_invalid", unit_ref))
            for field in (
                "table_candidate_ref",
                "table_strategy_ref",
                "geometry_confidence",
                "table_bbox_ref",
            ):
                if unit.get(field) in {None, ""}:
                    errors.append(_error("pdf_table_source_unit_field_missing", f"{unit_ref}:{field}"))
            if not list(unit.get("table_contributing_word_refs") or []):
                errors.append(_error("pdf_table_source_unit_words_missing", unit_ref))
            if not list(unit.get("table_fallback_text_refs") or []):
                errors.append(_error("pdf_table_source_unit_fallback_missing", unit_ref))
        elif unit.get("table_reconstruction_status") != "not_claimed":
            errors.append(_error("pdf_line_cluster_claims_table_reconstruction", unit_ref))
    if require_parent_payload and parent_payload is None:
        errors.append(_error("pdf_source_unit_parent_payload_missing", unit_ref))
    if parent_payload is not None:
        validation = validate_pdf_text_layer_payload(parent_payload)
        if validation.get("validator_status") != "passed":
            errors.append(_error("pdf_source_unit_parent_payload_invalid", unit_ref))
        if parent_payload.get("parser_completeness_status") != "complete":
            errors.append(_error("pdf_source_unit_parent_payload_not_complete", unit_ref))
        if unit.get("parent_payload_ref") != parent_payload.get("source_payload_ref"):
            errors.append(_error("pdf_source_unit_parent_ref_mismatch", unit_ref))
        if unit.get("payload_checksum_ref") != parent_payload.get("payload_checksum_ref"):
            errors.append(_error("pdf_source_unit_payload_checksum_mismatch", unit_ref))
        if unit_type in {"pdf_line_cluster_unit", "pdf_table_candidate_unit"}:
            parent_projection = _object(parent_payload.get("pdf_text_layer_projection"))
            if parent_projection.get("layout_projection_status") != "complete":
                errors.append(_error("pdf_layout_source_unit_parent_not_complete", unit_ref))
            parent_layout_refs = set(parent_payload.get("source_value_refs") or [])
            for source_value_ref in unit.get("pdf_layout_source_value_refs") or []:
                if source_value_ref not in parent_layout_refs:
                    errors.append(
                        _error("pdf_layout_source_unit_value_ref_out_of_parent", source_value_ref)
                    )
                    continue
                unit_value = resolve_pdf_layout_unit_source_value(
                    unit, str(source_value_ref)
                )
                parent_entries = [
                    item
                    for item in _dict_list(parent_payload.get("source_value_index"))
                    if item.get("source_value_ref") == source_value_ref
                ]
                if len(parent_entries) != 1:
                    errors.append(
                        _error("pdf_layout_parent_value_ref_not_unique", source_value_ref)
                    )
                    continue
                try:
                    parent_value = resolve_pdf_payload_source_value(
                        parent_payload, parent_entries[0]
                    )
                except ValueError as exc:
                    errors.append(_error(str(exc), source_value_ref))
                    continue
                if unit_value != parent_value:
                    errors.append(
                        _error("pdf_layout_source_unit_parent_value_mismatch", source_value_ref)
                    )
    return errors


def resolve_pdf_payload_source_value(
    payload: dict[str, Any],
    entry: dict[str, Any],
) -> str:
    path = _object(entry.get("value_path"))
    kind = path.get("kind")
    projection = _object(payload.get("pdf_text_layer_projection"))
    if kind == "pdf_page_text_span":
        page_number = int(path.get("page_number") or 0)
        pages = _dict_list(projection.get("page_inventory"))
        page = next(
            (
                item
                for item in pages
                if int(item.get("page_number") or 0) == page_number
            ),
            None,
        )
        if page is None:
            raise ValueError("pdf_source_value_page_path_invalid")
        text = str(page.get("text") or "")
        start = int(path.get("character_start") or 0)
        end = int(path.get("character_end") or 0)
        if start < 0 or end < start or end > len(text):
            raise ValueError("pdf_source_value_span_path_invalid")
        return text[start:end]
    if kind == "pdf_layout_word_text":
        ref = str(path.get("word_ref") or "")
        matches = [
            item
            for item in _dict_list(projection.get("word_inventory"))
            if item.get("word_ref") == ref
        ]
        if len(matches) != 1:
            raise ValueError("pdf_layout_word_value_path_invalid")
        return str(matches[0].get("text") or "")
    if kind == "pdf_layout_line_text":
        ref = str(path.get("line_ref") or "")
        matches = [
            item
            for item in _dict_list(projection.get("line_inventory"))
            if item.get("line_ref") == ref
        ]
        if len(matches) != 1:
            raise ValueError("pdf_layout_line_value_path_invalid")
        return str(matches[0].get("text") or "")
    raise ValueError("pdf_source_value_path_kind_invalid")


def _text_showing_operator_count(contents: Any) -> int:
    if contents is None:
        return 0
    try:
        operations = list(getattr(contents, "operations", []) or [])
    except Exception:
        return 0
    operators = {b"Tj", b"TJ", b"'", b'"'}
    return sum(1 for _operands, operator in operations if operator in operators)


def _count_image_objects(page: Any) -> int:
    try:
        resources = _resolve_pdf_object(page.get("/Resources"))
    except Exception:
        return 0
    return _count_images_in_resources(resources, seen=set())


def _count_images_in_resources(resources: Any, *, seen: set[tuple[int, int] | int]) -> int:
    if not hasattr(resources, "get"):
        return 0
    try:
        xobjects = _resolve_pdf_object(resources.get("/XObject"))
    except Exception:
        return 0
    if not hasattr(xobjects, "values"):
        return 0
    count = 0
    for value in xobjects.values():
        key = _pdf_object_identity(value)
        if key in seen:
            continue
        seen.add(key)
        try:
            current = _resolve_pdf_object(value)
            subtype = str(current.get("/Subtype") or "") if hasattr(current, "get") else ""
            if subtype == "/Image":
                count += 1
            elif subtype == "/Form" and hasattr(current, "get"):
                count += _count_images_in_resources(
                    _resolve_pdf_object(current.get("/Resources")),
                    seen=seen,
                )
        except Exception:
            continue
    return count


def _resolve_pdf_object(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def _pdf_object_identity(value: Any) -> tuple[int, int] | int:
    if hasattr(value, "idnum"):
        return (int(getattr(value, "idnum", 0)), int(getattr(value, "generation", 0)))
    return id(value)


def _numeric_matrix(value: Any) -> list[float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 6:
        return None
    try:
        return [round(float(value[index]), 6) for index in range(6)]
    except (TypeError, ValueError):
        return None


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 6) if number == number and abs(number) != float("inf") else None


def _checksum_ref(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _ref(prefix: str, *parts: Any, length: int) -> str:
    return f"{prefix}_{stable_digest(parts, length=length)}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}
