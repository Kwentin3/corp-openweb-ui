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
    PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED,
    PDF_DOCUMENT_AI_LIVE_QUALIFIED,
    PdfDocumentExtraction,
    PdfDocumentExtractionError,
    PdfDocumentImageRef,
    PdfSourceContext,
    new_pdf_document_image_ref,
)


MISTRAL_OCR_MODEL = "mistral-ocr-latest"
MISTRAL_OCR_ADAPTER_ID = "mistral_serverless_ocr_adapter_v1"
MISTRAL_OCR_PROVIDER_ID = "mistral"
_MAX_RESPONSE_BYTES = 64 * 1024 * 1024
_MAX_IMAGES = 64
_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_MAX_TOTAL_IMAGE_BYTES = 50 * 1024 * 1024
_PAGE_SEPARATOR = b"\n\n"


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
            "qualification_attempt",
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
        pages = response.get("pages")
        if not isinstance(pages, list) or len(pages) != source_context.preflight_page_count:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_PAGE_COUNT_MISMATCH")

        markdown_parts: list[bytes] = []
        encoded_images: list[tuple[int, str, str]] = []
        for expected_index, page in enumerate(pages):
            if not isinstance(page, Mapping):
                raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
            if type(page.get("index")) is not int or page.get("index") != expected_index:
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

        usage = response.get("usage_info")
        if not isinstance(usage, Mapping) or type(usage.get("pages_processed")) is not int:
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")
        usage_page_count = int(usage["pages_processed"])
        if usage_page_count != len(pages):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_PAGE_COUNT_MISMATCH")
        model = response.get("model")
        if (
            not isinstance(model, str)
            or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", model)
        ):
            raise PdfDocumentExtractionError("PDF_DOCUMENT_AI_RESPONSE_INVALID")

        markdown_bytes = _PAGE_SEPARATOR.join(markdown_parts)
        image_refs = self._images.decode(encoded_images)
        return PdfDocumentExtraction(
                source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
                page_numbers=tuple(range(1, len(pages) + 1)),
                markdown_bytes=markdown_bytes,
                markdown_sha256=hashlib.sha256(markdown_bytes).hexdigest(),
                image_refs=image_refs,
                provider_id=MISTRAL_OCR_PROVIDER_ID,
                model_id=model,
                adapter_id=MISTRAL_OCR_ADAPTER_ID,
                qualification_status=self._qualification_status,
                usage_page_count=usage_page_count,
                safe_technical_summary=(
                    ("document_bytes", len(pdf_bytes)),
                    ("images_count", len(image_refs)),
                    ("markdown_bytes", len(markdown_bytes)),
                    ("pages_count", usage_page_count),
                ),
            )

    def _post_once(self, pdf_bytes: bytes) -> Mapping[str, Any]:
        payload = json.dumps(
            {
                "model": MISTRAL_OCR_MODEL,
                "document": {
                    "type": "document_url",
                    "document_url": (
                        "data:application/pdf;base64,"
                        + base64.b64encode(pdf_bytes).decode("ascii")
                    ),
                },
                "include_image_base64": True,
            },
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


def create_from_openwebui_request(
    *,
    server_request: Any,
    qualification_status: str = "qualified",
) -> MistralPdfDocumentExtractor | None:
    """Read the sole live OpenWebUI config owner without copying persistence."""

    try:
        config = server_request.app.state.config
        engine = str(config.CONTENT_EXTRACTION_ENGINE or "").lower()
    except (AttributeError, TypeError):
        return None
    if engine != "mistral_ocr":
        return None
    if (
        not PDF_DOCUMENT_AI_LIVE_QUALIFIED
        and qualification_status != "qualification_attempt"
    ):
        raise PdfDocumentExtractionError(
            PDF_DOCUMENT_AI_LIVE_QUALIFICATION_REQUIRED
        )
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
        qualification_status=qualification_status,
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
