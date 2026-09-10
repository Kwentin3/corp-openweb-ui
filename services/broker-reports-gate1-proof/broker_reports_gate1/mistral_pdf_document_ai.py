from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import socket
from collections.abc import Mapping, Sequence
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from .pdf_document_ai import (
    PdfDocumentExtraction,
    PdfDocumentAiExecutionContract,
    PdfDocumentExtractionError,
    PdfDocumentImageRef,
    PdfDocumentTableRef,
    PdfDocumentTableContinuationAssessment,
    PdfDocumentTableContinuationLink,
    PdfDocumentTableContinuationRAndDResult,
    PdfDocumentSelectedPageBinding,
    PdfSourceContext,
    new_pdf_document_image_ref,
    new_pdf_document_table_ref,
    pdf_document_selected_page_bindings_sha256,
    pdf_document_table_refs_sha256,
)


MISTRAL_OCR_MODEL = "mistral-ocr-4-1"
MISTRAL_OCR_ADAPTER_ID = "mistral_serverless_ocr_adapter_v3"
MISTRAL_OCR_PROVIDER_ID = "mistral"
MISTRAL_OCR_PROVIDER_REPORTED_MODEL_IDS = (
    "mistral-ocr-4-1",
    "mistral-ocr-4-1-completion",
)
MISTRAL_OCR_REQUEST_CONTRACT_VERSION = "mistral_ocr_request_v2"
MISTRAL_OCR_REQUEST_PARAMETERS = (
    ("document_type", "document_url"),
    ("document_url_media_type", "application/pdf"),
    ("include_image_base64", True),
    ("table_format", "html"),
)
_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
_MAX_IMAGES = 64
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_MAX_TOTAL_IMAGE_BYTES = 50 * 1024 * 1024
_PAGE_SEPARATOR = b"\n\n"
MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_CONTRACT_VERSION = (
    "mistral_ocr_table_continuation_annotation_v2"
)
MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "broker_reports_native_table_continuation_links_v2",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "continuation_links": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "parent": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "selected_page_position": {
                                        "type": "integer",
                                        "minimum": 0,
                                    },
                                    "table_ordinal": {
                                        "type": "integer",
                                        "minimum": 1,
                                    },
                                },
                                "required": [
                                    "selected_page_position",
                                    "table_ordinal",
                                ],
                            },
                            "child": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "selected_page_position": {
                                        "type": "integer",
                                        "minimum": 0,
                                    },
                                    "table_ordinal": {
                                        "type": "integer",
                                        "minimum": 1,
                                    },
                                },
                                "required": [
                                    "selected_page_position",
                                    "table_ordinal",
                                ],
                            },
                        },
                        "required": ["parent", "child"],
                    },
                }
            },
            "required": ["continuation_links"],
        },
    },
}
MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_REQUEST_PARAMETERS = tuple(
    sorted(
        (
            *MISTRAL_OCR_REQUEST_PARAMETERS,
            ("document_annotation_format", "json_schema"),
        )
    )
)


def execution_contract() -> PdfDocumentAiExecutionContract:
    parameters_sha256 = hashlib.sha256(
        json.dumps(
            dict(MISTRAL_OCR_REQUEST_PARAMETERS),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return PdfDocumentAiExecutionContract(
        provider_id=MISTRAL_OCR_PROVIDER_ID,
        requested_model_id=MISTRAL_OCR_MODEL,
        adapter_id=MISTRAL_OCR_ADAPTER_ID,
        request_contract_version=MISTRAL_OCR_REQUEST_CONTRACT_VERSION,
        request_parameters=MISTRAL_OCR_REQUEST_PARAMETERS,
        request_parameters_sha256=parameters_sha256,
        accepted_provider_reported_model_ids=MISTRAL_OCR_PROVIDER_REPORTED_MODEL_IDS,
    )


class _HttpOpener(Protocol):
    def open(self, request: Request, *, timeout: float) -> Any: ...


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class BoundedImageDecoder:
    """Decode one response batch without choosing or touching storage."""

    def decode(
        self, encoded_images: Sequence[tuple[int, str, str]]
    ) -> tuple[PdfDocumentImageRef, ...]:
        if len(encoded_images) > _MAX_IMAGES:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_IMAGE_LIMIT_EXCEEDED")
        if not encoded_images:
            return ()

        refs: list[PdfDocumentImageRef] = []
        total_bytes = 0
        for page_number, markdown_target, encoded in encoded_images:
            image_bytes, extension = _decode_image(encoded)
            total_bytes += len(image_bytes)
            if total_bytes > _MAX_TOTAL_IMAGE_BYTES:
                raise PdfDocumentExtractionError(
                    "PDF_DOCUMENT_AI_IMAGE_LIMIT_EXCEEDED"
                )
            refs.append(
                PdfDocumentImageRef(
                    page_number=page_number,
                    markdown_target=markdown_target,
                    local_ref=new_pdf_document_image_ref(),
                    sha256=hashlib.sha256(image_bytes).hexdigest(),
                    media_type=f"image/{extension}",
                    content_bytes=image_bytes,
                )
            )
        return tuple(refs)


class MistralPdfDocumentExtractor:
    """One-call Mistral OCR transport and representation adapter."""

    def __init__(
        self,
        *,
        api_base_url: str,
        api_key: str,
        image_decoder: BoundedImageDecoder,
        qualification_status: str,
        timeout_seconds: float = 180.0,
        opener: _HttpOpener | None = None,
    ) -> None:
        if not isinstance(api_key, str) or not api_key.strip():
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_CONFIG_MISSING")
        self._ocr_url = _ocr_url(api_base_url)
        self._api_key = api_key
        self._images = image_decoder
        if qualification_status not in {
            "offline_fixture",
            "qualified",
        }:
            raise PdfDocumentExtractionError(
                "PDF_DOCUMENT_AI_QUALIFICATION_STATUS_INVALID"
            )
        self._qualification_status = qualification_status
        self._timeout_seconds = timeout_seconds
        self._opener = opener or build_opener(ProxyHandler({}), _NoRedirectHandler())

    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        response = self._post_once(pdf_bytes)
        return self._extraction_from_response(
            response=response,
            pdf_bytes=pdf_bytes,
            source_context=source_context,
            expected_response_page_indices=None,
        )

    def extract_with_table_continuation_assessment(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
        *,
        source_page_numbers: tuple[int, ...],
        document_annotation_prompt: str,
    ) -> PdfDocumentTableContinuationRAndDResult:
        """Run the native, non-product annotation experiment in one OCR call."""

        source_page_numbers = _validated_annotation_source_page_numbers(
            source_page_numbers,
            source_context=source_context,
        )
        if (
            not isinstance(document_annotation_prompt, str)
            or not document_annotation_prompt.strip()
        ):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_PROMPT_INVALID")
        response = self._post_once(
            pdf_bytes,
            document_annotation_prompt=document_annotation_prompt,
            source_page_numbers=source_page_numbers,
        )
        response_page_indices = _bound_annotation_response_page_indices(
            response,
            source_page_numbers=source_page_numbers,
        )
        extraction = self._extraction_from_response(
            response=response,
            pdf_bytes=pdf_bytes,
            source_context=source_context,
            expected_response_page_indices=response_page_indices,
        )
        assessment = _parse_table_continuation_assessment(
            response=response,
            extraction=extraction,
            document_annotation_prompt=document_annotation_prompt,
            source_page_numbers=source_page_numbers,
        )
        try:
            return PdfDocumentTableContinuationRAndDResult(
                extraction=extraction,
                assessment=assessment,
                source_context=source_context,
            )
        except ValueError as exc:
            raise PdfDocumentExtractionError(
                "PDF_DOCUMENT_AI_ANNOTATION_INVALID"
            ) from exc

    def _extraction_from_response(
        self,
        *,
        response: Mapping[str, Any],
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
        expected_response_page_indices: tuple[int, ...] | None,
    ) -> PdfDocumentExtraction:
        pages = response.get("pages")
        expected_page_count = (
            source_context.preflight_page_count
            if expected_response_page_indices is None
            else len(expected_response_page_indices)
        )
        if not isinstance(pages, list) or len(pages) != expected_page_count:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_PAGE_COUNT_MISMATCH")

        markdown_parts: list[bytes] = []
        page_content_dispositions: list[str] = []
        encoded_images: list[tuple[int, str, str]] = []
        table_refs: list[PdfDocumentTableRef] = []
        for expected_index, page in enumerate(pages):
            if not isinstance(page, Mapping):
                raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
            expected_response_index = (
                expected_index
                if expected_response_page_indices is None
                else expected_response_page_indices[expected_index]
            )
            if (
                type(page.get("index")) is not int
                or page.get("index") != expected_response_index
            ):
                raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_PAGE_ORDER_INVALID")
            markdown = page.get("markdown")
            if not isinstance(markdown, str):
                raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
            if any(
                line.startswith("Error during processing:")
                for line in markdown.splitlines()
            ):
                raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
            markdown_parts.append(markdown.encode("utf-8", errors="strict"))
            page_content_dispositions.append(
                "markdown_materialized" if markdown else "provider_empty_page"
            )
            images = page.get("images", [])
            if not isinstance(images, list):
                raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
            page_image_ids: list[str] = []
            for image in images:
                if not isinstance(image, Mapping) or not isinstance(
                    image.get("image_base64"), str
                ):
                    raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_IMAGE_INVALID")
                image_id = image.get("id")
                if (
                    not isinstance(image_id, str)
                    or not re.fullmatch(r"[A-Za-z0-9._-]{1,255}", image_id)
                    or image_id in page_image_ids
                ):
                    raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_IMAGE_INVALID")
                page_image_ids.append(image_id)
                encoded_images.append(
                    (expected_index + 1, image_id, image["image_base64"])
                )
            markdown_image_targets = re.findall(
                r"!\[[^\]\r\n]*\]\(([^\s)]+)", markdown
            )
            if markdown_image_targets != page_image_ids:
                raise PdfDocumentExtractionError(
                    "PDF_DOCUMENT_AI_IMAGE_ASSOCIATION_INVALID"
                )
            tables = page.get("tables", [])
            if not isinstance(tables, list):
                raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_TABLE_INVALID")
            page_table_ids: list[str] = []
            markdown_link_targets = re.findall(
                r"\[[^\]\r\n]*\]\(([^\s)]+)\)", markdown
            )
            for table in tables:
                if not isinstance(table, Mapping):
                    raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_TABLE_INVALID")
                table_id = table.get("id")
                html = table.get("content")
                if (
                    not isinstance(table_id, str)
                    or not re.fullmatch(r"[A-Za-z0-9._-]{1,255}", table_id)
                    or table_id in page_table_ids
                    or table_id in page_image_ids
                    or not isinstance(html, str)
                ):
                    raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_TABLE_INVALID")
                html_bytes = html.encode("utf-8", errors="strict")
                if not html_bytes or markdown_link_targets.count(table_id) != 1:
                    raise PdfDocumentExtractionError(
                        "PDF_DOCUMENT_AI_TABLE_ASSOCIATION_INVALID"
                    )
                page_table_ids.append(table_id)
                table_refs.append(
                    PdfDocumentTableRef(
                        page_number=expected_index + 1,
                        markdown_target=table_id,
                        local_ref=new_pdf_document_table_ref(),
                        sha256=hashlib.sha256(html_bytes).hexdigest(),
                        html_bytes=html_bytes,
                    )
                )

        usage = response.get("usage_info")
        if not isinstance(usage, Mapping) or type(usage.get("pages_processed")) is not int:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
        usage_page_count = int(usage["pages_processed"])
        if usage_page_count != len(pages):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_PAGE_COUNT_MISMATCH")
        model = response.get("model")
        if not isinstance(model, str) or not re.fullmatch(
            r"[A-Za-z0-9._:-]{1,128}", model
        ):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
        if model not in MISTRAL_OCR_PROVIDER_REPORTED_MODEL_IDS:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_MODEL_MISMATCH")

        markdown_bytes = _PAGE_SEPARATOR.join(markdown_parts)
        contract = execution_contract()
        image_refs = self._images.decode(encoded_images)
        return PdfDocumentExtraction(
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            page_numbers=tuple(range(1, len(pages) + 1)),
            markdown_bytes=markdown_bytes,
            markdown_sha256=hashlib.sha256(markdown_bytes).hexdigest(),
            image_refs=image_refs,
            provider_id=MISTRAL_OCR_PROVIDER_ID,
            requested_model_id=MISTRAL_OCR_MODEL,
            model_id=model,
            adapter_id=MISTRAL_OCR_ADAPTER_ID,
            request_contract_version=MISTRAL_OCR_REQUEST_CONTRACT_VERSION,
            request_parameters=MISTRAL_OCR_REQUEST_PARAMETERS,
            request_parameters_sha256=contract.request_parameters_sha256,
            page_markdown_sha256=tuple(
                hashlib.sha256(part).hexdigest() for part in markdown_parts
            ),
            qualification_status=self._qualification_status,
            usage_page_count=usage_page_count,
            page_markdown_bytes=tuple(markdown_parts),
            table_refs=tuple(table_refs),
            page_content_dispositions=tuple(page_content_dispositions),
            safe_technical_summary=(
                ("document_bytes", len(pdf_bytes)),
                ("images_count", len(image_refs)),
                ("markdown_bytes", len(markdown_bytes)),
                ("pages_count", usage_page_count),
                ("tables_count", len(table_refs)),
            ),
        )

    def _post_once(
        self,
        pdf_bytes: bytes,
        *,
        document_annotation_prompt: str | None = None,
        source_page_numbers: tuple[int, ...] | None = None,
    ) -> Mapping[str, Any]:
        parameters = dict(MISTRAL_OCR_REQUEST_PARAMETERS)
        payload_object: dict[str, object] = {
            "model": MISTRAL_OCR_MODEL,
            "document": {
                "type": parameters["document_type"],
                "document_url": (
                    f"data:{parameters['document_url_media_type']};base64,"
                    + base64.b64encode(pdf_bytes).decode("ascii")
                ),
            },
            "include_image_base64": parameters["include_image_base64"],
            "table_format": parameters["table_format"],
        }
        if document_annotation_prompt is not None:
            payload_object["document_annotation_format"] = (
                MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_SCHEMA
            )
            payload_object["document_annotation_prompt"] = document_annotation_prompt
            if source_page_numbers is None:
                raise PdfDocumentExtractionError(
                    "PDF_DOCUMENT_AI_ANNOTATION_SOURCE_PAGES_INVALID"
                )
            payload_object["pages"] = list(source_page_numbers)
        payload = json.dumps(
            payload_object,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            self._ocr_url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self._timeout_seconds) as response:
                status = int(getattr(response, "status", 200))
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                code = "PDF_DOCUMENT_AI_AUTH_FAILED"
            elif exc.code == 402:
                code = "PDF_DOCUMENT_AI_PAYMENT_REQUIRED"
            elif exc.code == 429:
                code = "PDF_DOCUMENT_AI_RATE_LIMITED"
            elif 500 <= exc.code <= 599:
                code = "PDF_DOCUMENT_AI_PROVIDER_UNAVAILABLE"
            else:
                code = "PDF_DOCUMENT_AI_HTTP_REJECTED"
            raise PdfDocumentExtractionError(code) from None
        except (TimeoutError, socket.timeout):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_TIMEOUT") from None
        except (URLError, OSError):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_TRANSPORT_FAILED") from None
        if status != 200:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_HTTP_REJECTED")
        if not isinstance(raw, bytes):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
        if len(raw) > _MAX_RESPONSE_BYTES:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_TOO_LARGE")
        try:
            value = json.loads(raw.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID") from None
        if not isinstance(value, Mapping):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
        return value


def _validated_annotation_source_page_numbers(
    source_page_numbers: tuple[int, ...],
    *,
    source_context: PdfSourceContext,
) -> tuple[int, ...]:
    if (
        type(source_page_numbers) is not tuple
        or not source_page_numbers
        or any(
            type(page_number) is not int
            or page_number < 0
            or page_number >= source_context.preflight_page_count
            for page_number in source_page_numbers
        )
        or source_page_numbers != tuple(sorted(set(source_page_numbers)))
    ):
        raise PdfDocumentExtractionError(
            "PDF_DOCUMENT_AI_ANNOTATION_SOURCE_PAGES_INVALID"
        )
    return source_page_numbers


def _bound_annotation_response_page_indices(
    response: Mapping[str, Any],
    *,
    source_page_numbers: tuple[int, ...],
) -> tuple[int, ...]:
    pages = response.get("pages")
    if not isinstance(pages, list) or len(pages) != len(source_page_numbers):
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_PAGE_COUNT_MISMATCH")
    response_page_indices = tuple(
        page.get("index") if isinstance(page, Mapping) else None for page in pages
    )
    if any(type(page_index) is not int for page_index in response_page_indices):
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
    zero_based_subset_indices = tuple(range(len(source_page_numbers)))
    if response_page_indices not in {
        source_page_numbers,
        zero_based_subset_indices,
    }:
        raise PdfDocumentExtractionError(
            "PDF_DOCUMENT_AI_ANNOTATION_RESPONSE_PAGE_BINDING_INVALID"
        )
    return tuple(int(page_index) for page_index in response_page_indices)


def _parse_table_continuation_assessment(
    *,
    response: Mapping[str, Any],
    extraction: PdfDocumentExtraction,
    document_annotation_prompt: str,
    source_page_numbers: tuple[int, ...],
) -> PdfDocumentTableContinuationAssessment:
    raw_annotation = response.get("document_annotation")
    if not isinstance(raw_annotation, str):
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_INVALID")
    try:
        annotation = json.loads(raw_annotation)
    except json.JSONDecodeError:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_INVALID") from None
    if not isinstance(annotation, Mapping) or set(annotation) != {"continuation_links"}:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_INVALID")
    raw_links = annotation["continuation_links"]
    if not isinstance(raw_links, list):
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_INVALID")

    table_by_selected_position_and_ordinal = _tables_by_selected_position_and_ordinal(
        extraction.table_refs
    )
    selected_page_bindings = tuple(
        PdfDocumentSelectedPageBinding(
            local_page_number=local_page_number,
            source_page_number=source_page_number,
        )
        for local_page_number, source_page_number in zip(
            extraction.page_numbers, source_page_numbers, strict=True
        )
    )
    source_page_number_by_local_page = {
        binding.local_page_number: binding.source_page_number
        for binding in selected_page_bindings
    }
    links: list[PdfDocumentTableContinuationLink] = []
    pairs: set[tuple[str, str]] = set()
    parent_refs: set[str] = set()
    child_refs: set[str] = set()
    for raw_link in raw_links:
        if not isinstance(raw_link, Mapping) or set(raw_link) != {"parent", "child"}:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_INVALID")
        parent = _annotation_table_ref(
            raw_link["parent"],
            table_by_selected_position_and_ordinal=(
                table_by_selected_position_and_ordinal
            ),
        )
        child = _annotation_table_ref(
            raw_link["child"],
            table_by_selected_position_and_ordinal=(
                table_by_selected_position_and_ordinal
            ),
        )
        if parent.local_ref == child.local_ref:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_SELF_LINK")
        parent_source_page_number = source_page_number_by_local_page[parent.page_number]
        child_source_page_number = source_page_number_by_local_page[child.page_number]
        if child_source_page_number <= parent_source_page_number:
            raise PdfDocumentExtractionError(
                "PDF_DOCUMENT_AI_ANNOTATION_CHILD_PAGE_ORDER_INVALID"
            )
        if child_source_page_number != parent_source_page_number + 1:
            raise PdfDocumentExtractionError(
                "PDF_DOCUMENT_AI_ANNOTATION_NONADJACENT_PAGE_LINK"
            )
        pair = (parent.local_ref, child.local_ref)
        if pair in pairs:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_DUPLICATE_LINK")
        if child.local_ref in child_refs:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_MULTIPLE_PARENT")
        if parent.local_ref in parent_refs:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_MULTIPLE_CHILD")
        pairs.add(pair)
        parent_refs.add(parent.local_ref)
        child_refs.add(child.local_ref)
        links.append(
            PdfDocumentTableContinuationLink(
                parent_table_ref=parent.local_ref,
                child_table_ref=child.local_ref,
            )
        )
    if _has_table_continuation_cycle(tuple(links)):
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_CYCLE")
    try:
        return PdfDocumentTableContinuationAssessment(
            source_pdf_sha256=extraction.source_pdf_sha256,
            table_refs_sha256=pdf_document_table_refs_sha256(extraction.table_refs),
            raw_annotation_sha256=hashlib.sha256(
                raw_annotation.encode("utf-8", errors="strict")
            ).hexdigest(),
            request_parameters_sha256=_json_sha256(
                {
                    **dict(MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_REQUEST_PARAMETERS),
                    "source_page_numbers": list(source_page_numbers),
                }
            ),
            annotation_prompt_sha256=hashlib.sha256(
                document_annotation_prompt.encode("utf-8", errors="strict")
            ).hexdigest(),
            annotation_schema_sha256=_json_sha256(
                MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_SCHEMA
            ),
            selected_page_bindings_sha256=pdf_document_selected_page_bindings_sha256(
                selected_page_bindings
            ),
            source_page_numbers=source_page_numbers,
            selected_page_bindings=selected_page_bindings,
            links=tuple(links),
        )
    except (TypeError, UnicodeEncodeError, ValueError):
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_INVALID") from None


def _annotation_table_ref(
    value: object,
    *,
    table_by_selected_position_and_ordinal: Mapping[
        tuple[int, int], PdfDocumentTableRef
    ],
) -> PdfDocumentTableRef:
    if not isinstance(value, Mapping) or set(value) != {
        "selected_page_position",
        "table_ordinal",
    }:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_INVALID")
    selected_page_position = value["selected_page_position"]
    table_ordinal = value["table_ordinal"]
    if (
        type(selected_page_position) is not int
        or selected_page_position < 0
        or type(table_ordinal) is not int
        or table_ordinal < 1
    ):
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_INVALID")
    table = table_by_selected_position_and_ordinal.get(
        (selected_page_position, table_ordinal)
    )
    if table is None:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_UNKNOWN_TABLE")
    return table


def _tables_by_selected_position_and_ordinal(
    table_refs: tuple[PdfDocumentTableRef, ...],
) -> dict[tuple[int, int], PdfDocumentTableRef]:
    """Bind R&D annotation positions to this exact response table ordering.

    The provider's opaque table ids remain inside the extraction only.  The
    annotation contract can name a table solely by its zero-based selected-page
    position and one-based ordinal in the already validated response order.
    """

    table_by_position_and_ordinal: dict[tuple[int, int], PdfDocumentTableRef] = {}
    ordinal_by_local_page: dict[int, int] = {}
    for table in table_refs:
        local_page_number = table.page_number
        ordinal = ordinal_by_local_page.get(local_page_number, 0) + 1
        ordinal_by_local_page[local_page_number] = ordinal
        key = (local_page_number - 1, ordinal)
        if key in table_by_position_and_ordinal:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_ANNOTATION_INVALID")
        table_by_position_and_ordinal[key] = table
    return table_by_position_and_ordinal


def _has_table_continuation_cycle(
    links: tuple[PdfDocumentTableContinuationLink, ...],
) -> bool:
    children_by_parent = {
        link.parent_table_ref: link.child_table_ref for link in links
    }
    for start in children_by_parent:
        seen: set[str] = set()
        cursor = start
        while cursor in children_by_parent:
            if cursor in seen:
                return True
            seen.add(cursor)
            cursor = children_by_parent[cursor]
    return False


def _json_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def create_from_openwebui_request(
    *,
    server_request: Any,
) -> MistralPdfDocumentExtractor | None:
    """Read the sole live OpenWebUI config owner without copying persistence."""

    try:
        config = server_request.app.state.config
        engine = str(config.CONTENT_EXTRACTION_ENGINE or "").lower()
    except (AttributeError, TypeError):
        return None
    if engine != "mistral_ocr":
        return None
    try:
        api_base_url = str(config.MISTRAL_OCR_API_BASE_URL or "")
        api_key = str(config.MISTRAL_OCR_API_KEY or "")
    except (AttributeError, TypeError):
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_CONFIG_MISSING") from None
    if not api_base_url or not api_key.strip():
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_CONFIG_MISSING")
    return MistralPdfDocumentExtractor(
        api_base_url=api_base_url,
        api_key=api_key,
        image_decoder=BoundedImageDecoder(),
        qualification_status="qualified",
    )


def _ocr_url(api_base_url: str) -> str:
    parsed = urlsplit(api_base_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.mistral.ai"
        or parsed.netloc != "api.mistral.ai"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path.rstrip("/") != "/v1"
        or parsed.query
        or parsed.fragment
    ):
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_CONFIG_INVALID")
    path = parsed.path.rstrip("/") + "/ocr"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _decode_image(encoded: str) -> tuple[bytes, str]:
    payload = encoded
    if encoded.startswith("data:"):
        header, separator, payload = encoded.partition(",")
        if not separator or not header.endswith(";base64"):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_IMAGE_INVALID")
    try:
        image_bytes = base64.b64decode(payload, validate=True)
    except (ValueError, binascii.Error):
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_IMAGE_INVALID") from None
    if not image_bytes or len(image_bytes) > _MAX_IMAGE_BYTES:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_IMAGE_LIMIT_EXCEEDED")
    signatures = (
        (b"\x89PNG\r\n\x1a\n", "png"),
        (b"\xff\xd8\xff", "jpeg"),
        (b"GIF87a", "gif"),
        (b"GIF89a", "gif"),
    )
    for signature, extension in signatures:
        if image_bytes.startswith(signature):
            return image_bytes, extension
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return image_bytes, "webp"
    raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_IMAGE_INVALID")
