from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from .contracts import stable_digest


FACTORY_REQUIRED = (
    "PdfTextLayerParserFactory.create is the only production PDF text-layer parser entrypoint"
)
FORBIDDEN = (
    "Full-source builders, profilers, Gate 2 callers and smoke scripts must not instantiate PypdfParserAdapter directly"
)

PDF_TEXT_LAYER_PROJECTION_SCHEMA_VERSION = "pdf_text_layer_projection_v0"
PDF_TEXT_LAYER_COVERAGE_SCHEMA_VERSION = "pdf_text_layer_coverage_v0"
PDF_PARSER_POLICY_VERSION = "pypdf_page_text_policy_v0"
PYPDF_PINNED_VERSION = "6.7.5"
SUPPORTED_PDF_CAPABILITY = "page_text"
PDF_SOURCE_UNIT_TYPES = {"pdf_page_text_unit", "pdf_line_cluster_unit"}


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
    ) -> "PypdfParserAdapter":
        request = request or PdfParserCapabilityRequest()
        if request.capability != SUPPORTED_PDF_CAPABILITY:
            raise PdfTextLayerParserError(
                "pdf_parser_capability_unsupported",
                "Slice 1 supports page_text only and does not silently downgrade layout/table requests",
            )
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
    if (
        payload.get("page_rendering_used_for_extraction") is not False
        or projection.get("page_rendering_used_for_extraction") is not False
    ):
        errors.append(_error("pdf_projection_rendering_guard_failed", payload_ref))

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
        pdf_page_checksum_ref(page, str(payload.get("parser_ref") or "")) for page in pages
    ]
    actual_page_checksums = [str(page.get("page_text_checksum_ref") or "") for page in pages]
    if actual_page_checksums != expected_page_checksums:
        errors.append(_error("pdf_projection_page_checksum_mismatch", payload_ref))
    if list(projection.get("page_checksum_refs") or []) != actual_page_checksums:
        errors.append(_error("pdf_projection_page_checksum_inventory_mismatch", payload_ref))

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
        if projection.get("text_layer_projection_status") != "complete":
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
    if unit.get("ocr_vlm_used") is not False:
        errors.append(_error("pdf_source_unit_ocr_guard_failed", unit_ref))
    if unit.get("page_rendering_used_for_extraction") is not False:
        errors.append(_error("pdf_source_unit_rendering_guard_failed", unit_ref))
    if unit.get("parent_source_slice_truncated") is not False:
        errors.append(_error("pdf_source_unit_parent_truncated", unit_ref))
    if not list(unit.get("page_refs") or []):
        errors.append(_error("pdf_source_unit_page_ref_missing", unit_ref))
    if not list(unit.get("text_segment_refs") or []):
        errors.append(_error("pdf_source_unit_text_refs_missing", unit_ref))
    coverage = _object(unit.get("coverage"))
    if coverage.get("selected_total") != coverage.get("accounted_total"):
        errors.append(_error("pdf_source_unit_coverage_count_mismatch", unit_ref))
    if coverage.get("all_selected_refs_accounted") is not True:
        errors.append(_error("pdf_source_unit_coverage_incomplete", unit_ref))
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
    return errors


def resolve_pdf_payload_source_value(
    payload: dict[str, Any],
    entry: dict[str, Any],
) -> str:
    path = _object(entry.get("value_path"))
    if path.get("kind") != "pdf_page_text_span":
        raise ValueError("pdf_source_value_path_kind_invalid")
    page_number = int(path.get("page_number") or 0)
    pages = _dict_list(_object(payload.get("pdf_text_layer_projection")).get("page_inventory"))
    page = next((item for item in pages if int(item.get("page_number") or 0) == page_number), None)
    if page is None:
        raise ValueError("pdf_source_value_page_path_invalid")
    text = str(page.get("text") or "")
    start = int(path.get("character_start") or 0)
    end = int(path.get("character_end") or 0)
    if start < 0 or end < start or end > len(text):
        raise ValueError("pdf_source_value_span_path_invalid")
    return text[start:end]


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
