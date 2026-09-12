from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Protocol, runtime_checkable


PDF_DOCUMENT_EXTRACTION_SCHEMA_VERSION = "broker_reports_pdf_document_extraction_v5"
PDF_DOCUMENT_AI_POLICY_VERSION = "broker_reports_pdf_document_ai_v5"
PDF_DOCUMENT_AI_NOT_CONFIGURED = "PDF_DOCUMENT_AI_NOT_CONFIGURED"
PDF_DOCUMENT_AI_PAYMENT_REQUIRED = "PDF_DOCUMENT_AI_PAYMENT_REQUIRED"
_SAFE_TECHNICAL_SUMMARY_KEYS = {
    "document_bytes",
    "images_count",
    "markdown_bytes",
    "pages_count",
    "tables_count",
}


@dataclass(frozen=True)
class PdfDocumentImageRef:
    page_number: int
    markdown_target: str
    local_ref: str
    sha256: str
    media_type: str
    content_bytes: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.page_number) is not int or self.page_number < 1:
            raise ValueError("pdf_document_image_page_number_invalid")
        _require_closed_relative_ref(
            self.markdown_target,
            "pdf_document_image_markdown_target_must_be_closed_relative",
        )
        _require_closed_relative_ref(
            self.local_ref,
            "pdf_document_image_ref_must_be_closed_local",
        )
        _require_sha256(self.sha256, "pdf_document_image_sha256_invalid")
        if self.media_type not in {
            "image/png",
            "image/jpeg",
            "image/gif",
            "image/webp",
        }:
            raise ValueError("pdf_document_image_media_type_invalid")
        if type(self.content_bytes) is not bytes or not self.content_bytes:
            raise ValueError("pdf_document_image_bytes_required")
        if hashlib.sha256(self.content_bytes).hexdigest() != self.sha256:
            raise ValueError("pdf_document_image_sha256_mismatch")


@dataclass(frozen=True)
class PdfDocumentTableRef:
    """Opaque native table material owned by one document-extraction envelope."""

    page_number: int
    markdown_target: str
    local_ref: str
    sha256: str
    html_bytes: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.page_number) is not int or self.page_number < 1:
            raise ValueError("pdf_document_table_page_number_invalid")
        _require_closed_relative_ref(
            self.markdown_target,
            "pdf_document_table_markdown_target_must_be_closed_relative",
        )
        _require_closed_relative_ref(
            self.local_ref,
            "pdf_document_table_ref_must_be_closed_local",
        )
        _require_sha256(self.sha256, "pdf_document_table_sha256_invalid")
        if type(self.html_bytes) is not bytes or not self.html_bytes:
            raise ValueError("pdf_document_table_bytes_required")
        try:
            self.html_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("pdf_document_table_not_utf8") from exc
        if hashlib.sha256(self.html_bytes).hexdigest() != self.sha256:
            raise ValueError("pdf_document_table_sha256_mismatch")


PDF_DOCUMENT_TABLE_CONTINUATION_ASSESSMENT_SCHEMA_VERSION = (
    "broker_reports_pdf_document_table_continuation_assessment_v1"
)


@dataclass(frozen=True)
class PdfDocumentTableContinuationLink:
    """A relation between two opaque native table references in one extraction."""

    parent_table_ref: str
    child_table_ref: str

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str) and value.startswith("pdftable_")
            for value in (self.parent_table_ref, self.child_table_ref)
        ):
            raise ValueError("pdf_document_table_continuation_ref_invalid")
        if self.parent_table_ref == self.child_table_ref:
            raise ValueError("pdf_document_table_continuation_self_link")


@dataclass(frozen=True)
class PdfDocumentSelectedPageBinding:
    """Bind one local OCR page to the original zero-based PDF page."""

    local_page_number: int
    source_page_number: int

    def __post_init__(self) -> None:
        if type(self.local_page_number) is not int or self.local_page_number < 1:
            raise ValueError("pdf_document_annotation_local_page_invalid")
        if type(self.source_page_number) is not int or self.source_page_number < 0:
            raise ValueError("pdf_document_annotation_source_page_invalid")


@dataclass(frozen=True)
class PdfDocumentTableContinuationAssessment:
    """R&D-only native annotation receipt; it carries no Canonical meaning."""

    source_pdf_sha256: str = field(repr=False)
    table_refs_sha256: str = field(repr=False)
    raw_annotation_sha256: str = field(repr=False)
    request_parameters_sha256: str = field(repr=False)
    annotation_prompt_sha256: str = field(repr=False)
    annotation_schema_sha256: str = field(repr=False)
    selected_page_bindings_sha256: str = field(repr=False)
    source_page_numbers: tuple[int, ...]
    selected_page_bindings: tuple[PdfDocumentSelectedPageBinding, ...]
    links: tuple[PdfDocumentTableContinuationLink, ...]
    schema_version: str = PDF_DOCUMENT_TABLE_CONTINUATION_ASSESSMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for value, code in (
            (self.source_pdf_sha256, "pdf_document_annotation_source_sha256_invalid"),
            (self.table_refs_sha256, "pdf_document_annotation_table_refs_sha256_invalid"),
            (self.raw_annotation_sha256, "pdf_document_annotation_raw_sha256_invalid"),
            (
                self.request_parameters_sha256,
                "pdf_document_annotation_request_parameters_sha256_invalid",
            ),
            (self.annotation_prompt_sha256, "pdf_document_annotation_prompt_sha256_invalid"),
            (self.annotation_schema_sha256, "pdf_document_annotation_schema_sha256_invalid"),
            (
                self.selected_page_bindings_sha256,
                "pdf_document_annotation_selected_page_bindings_sha256_invalid",
            ),
        ):
            _require_sha256(value, code)
        if self.schema_version != PDF_DOCUMENT_TABLE_CONTINUATION_ASSESSMENT_SCHEMA_VERSION:
            raise ValueError("pdf_document_annotation_schema_version_invalid")
        if (
            not self.source_page_numbers
            or any(
                type(page_number) is not int or page_number < 0
                for page_number in self.source_page_numbers
            )
            or self.source_page_numbers != tuple(sorted(set(self.source_page_numbers)))
        ):
            raise ValueError("pdf_document_annotation_source_page_numbers_invalid")
        if (
            not self.selected_page_bindings
            or len(self.selected_page_bindings) != len(self.source_page_numbers)
            or any(
                not isinstance(binding, PdfDocumentSelectedPageBinding)
                for binding in self.selected_page_bindings
            )
            or len(
                {
                    binding.local_page_number
                    for binding in self.selected_page_bindings
                }
            )
            != len(self.selected_page_bindings)
        ):
            raise ValueError("pdf_document_annotation_selected_page_bindings_invalid")
        if self.selected_page_bindings_sha256 != pdf_document_selected_page_bindings_sha256(
            self.selected_page_bindings
        ):
            raise ValueError(
                "pdf_document_annotation_selected_page_bindings_sha256_mismatch"
            )
        if any(
            not isinstance(link, PdfDocumentTableContinuationLink)
            for link in self.links
        ):
            raise ValueError("pdf_document_annotation_link_invalid")
        pairs = tuple(
            (link.parent_table_ref, link.child_table_ref) for link in self.links
        )
        if len(set(pairs)) != len(pairs):
            raise ValueError("pdf_document_annotation_duplicate_link")
        children = [link.child_table_ref for link in self.links]
        if len(set(children)) != len(children):
            raise ValueError("pdf_document_annotation_multiple_parent")
        parents = [link.parent_table_ref for link in self.links]
        if len(set(parents)) != len(parents):
            raise ValueError("pdf_document_annotation_multiple_child")


def pdf_document_table_refs_sha256(
    table_refs: tuple[PdfDocumentTableRef, ...],
) -> str:
    """Hash the exact physical table set without exposing its HTML bytes."""

    material = [
        {
            "local_ref": item.local_ref,
            "markdown_target": item.markdown_target,
            "page_number": item.page_number,
            "sha256": item.sha256,
        }
        for item in table_refs
    ]
    return hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def validate_table_continuation_assessment(
    assessment: PdfDocumentTableContinuationAssessment,
    *,
    extraction: "PdfDocumentExtraction",
    source_context: "PdfSourceContext | None" = None,
) -> None:
    """Verify that an R&D annotation belongs to this exact OCR extraction."""

    if assessment.source_pdf_sha256 != extraction.source_pdf_sha256:
        raise ValueError("pdf_document_annotation_source_mismatch")
    if assessment.table_refs_sha256 != pdf_document_table_refs_sha256(
        extraction.table_refs
    ):
        raise ValueError("pdf_document_annotation_table_refs_mismatch")
    expected_local_page_numbers = extraction.page_numbers
    actual_local_page_numbers = tuple(
        binding.local_page_number for binding in assessment.selected_page_bindings
    )
    if actual_local_page_numbers != expected_local_page_numbers:
        raise ValueError("pdf_document_annotation_local_page_binding_mismatch")
    actual_source_page_numbers = tuple(
        binding.source_page_number for binding in assessment.selected_page_bindings
    )
    if actual_source_page_numbers != assessment.source_page_numbers:
        raise ValueError("pdf_document_annotation_source_page_binding_mismatch")
    if source_context is not None:
        if extraction.source_pdf_sha256 != source_context.expected_pdf_sha256:
            raise ValueError("pdf_document_annotation_source_context_mismatch")
        if any(
            source_page_number >= source_context.preflight_page_count
            for source_page_number in actual_source_page_numbers
        ):
            raise ValueError("pdf_document_annotation_source_page_out_of_range")
    tables_by_ref = {item.local_ref: item for item in extraction.table_refs}
    for link in assessment.links:
        parent = tables_by_ref.get(link.parent_table_ref)
        child = tables_by_ref.get(link.child_table_ref)
        if parent is None or child is None:
            raise ValueError("pdf_document_annotation_unknown_table_ref")
        if child.page_number <= parent.page_number:
            raise ValueError("pdf_document_annotation_child_page_order_invalid")
        if child.page_number != parent.page_number + 1:
            raise ValueError("pdf_document_annotation_nonadjacent_page_link")
    children_by_parent = {
        link.parent_table_ref: link.child_table_ref for link in assessment.links
    }
    for start in children_by_parent:
        seen: set[str] = set()
        cursor = start
        while cursor in children_by_parent:
            if cursor in seen:
                raise ValueError("pdf_document_annotation_cycle")
            seen.add(cursor)
            cursor = children_by_parent[cursor]


def pdf_document_selected_page_bindings_sha256(
    selected_page_bindings: tuple[PdfDocumentSelectedPageBinding, ...],
) -> str:
    """Hash the local-to-original page mapping carried by an R&D receipt."""

    material = [
        {
            "local_page_number": binding.local_page_number,
            "source_page_number": binding.source_page_number,
        }
        for binding in selected_page_bindings
    ]
    return hashlib.sha256(
        json.dumps(
            material,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def new_pdf_document_image_ref() -> str:
    """Mint an opaque, unpublished ref without choosing a storage backend."""

    return f"pdfimg_{secrets.token_urlsafe(24)}"


def new_pdf_document_table_ref() -> str:
    """Mint an opaque, unpublished table ref without choosing persistence."""

    return f"pdftable_{secrets.token_urlsafe(24)}"


def _require_closed_relative_ref(value: str, code: str) -> None:
    if not isinstance(value, str):
        raise ValueError(code)
    windows_path = PureWindowsPath(value)
    posix_path = PurePosixPath(value)
    if (
        not value
        or value == "."
        or "\x00" in value
        or "://" in value
        or windows_path.drive
        or windows_path.root
        or windows_path.is_absolute()
        or posix_path.is_absolute()
        or ".." in windows_path.parts
        or ".." in posix_path.parts
    ):
        raise ValueError(code)


@dataclass(frozen=True)
class PdfDocumentExtraction:
    source_pdf_sha256: str = field(repr=False)
    page_numbers: tuple[int, ...]
    markdown_bytes: bytes = field(repr=False)
    markdown_sha256: str = field(repr=False)
    image_refs: tuple[PdfDocumentImageRef, ...] = field(repr=False)
    provider_id: str
    requested_model_id: str
    model_id: str
    adapter_id: str
    request_contract_version: str
    request_parameters: tuple[tuple[str, bool | int | str], ...]
    request_parameters_sha256: str = field(repr=False)
    page_markdown_sha256: tuple[str, ...] = field(repr=False)
    qualification_status: str
    usage_page_count: int
    page_markdown_bytes: tuple[bytes, ...] = field(repr=False, default=())
    table_refs: tuple[PdfDocumentTableRef, ...] = field(repr=False, default=())
    page_content_dispositions: tuple[str, ...] = ()
    safe_technical_summary: tuple[tuple[str, int], ...] = ()
    schema_version: str = PDF_DOCUMENT_EXTRACTION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_sha256(self.source_pdf_sha256, "pdf_document_source_sha256_invalid")
        _require_sha256(self.markdown_sha256, "pdf_document_markdown_sha256_invalid")
        if hashlib.sha256(self.markdown_bytes).hexdigest() != self.markdown_sha256:
            raise ValueError("pdf_document_markdown_sha256_mismatch")
        try:
            self.markdown_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ValueError("pdf_document_markdown_not_utf8") from exc
        if not self.page_numbers or self.page_numbers != tuple(
            range(1, len(self.page_numbers) + 1)
        ):
            raise ValueError("pdf_document_page_order_invalid")
        if self.page_numbers[0] < 1 or self.usage_page_count != len(self.page_numbers):
            raise ValueError("pdf_document_page_count_invalid")
        if not all(
            (
                self.provider_id,
                self.requested_model_id,
                self.model_id,
                self.adapter_id,
                self.request_contract_version,
            )
        ):
            raise ValueError("pdf_document_provenance_incomplete")
        parameter_keys = tuple(key for key, _value in self.request_parameters)
        if parameter_keys != tuple(sorted(parameter_keys)) or len(
            set(parameter_keys)
        ) != len(parameter_keys):
            raise ValueError("pdf_document_request_parameters_invalid")
        _require_sha256(
            self.request_parameters_sha256,
            "pdf_document_request_parameters_sha256_invalid",
        )
        parameter_material = json.dumps(
            dict(self.request_parameters),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if (
            hashlib.sha256(parameter_material).hexdigest()
            != self.request_parameters_sha256
        ):
            raise ValueError("pdf_document_request_parameters_sha256_mismatch")
        if len(self.page_markdown_sha256) != len(self.page_numbers):
            raise ValueError("pdf_document_page_markdown_digest_count_mismatch")
        for digest in self.page_markdown_sha256:
            _require_sha256(digest, "pdf_document_page_markdown_sha256_invalid")
        if self.page_markdown_bytes:
            if len(self.page_markdown_bytes) != len(self.page_numbers):
                raise ValueError("pdf_document_page_markdown_bytes_count_invalid")
            if any(type(page) is not bytes for page in self.page_markdown_bytes):
                raise ValueError("pdf_document_page_markdown_bytes_invalid")
            if tuple(
                hashlib.sha256(page).hexdigest()
                for page in self.page_markdown_bytes
            ) != self.page_markdown_sha256:
                raise ValueError("pdf_document_page_markdown_bytes_hash_mismatch")
            if b"\n\n".join(self.page_markdown_bytes) != self.markdown_bytes:
                raise ValueError("pdf_document_page_markdown_aggregate_mismatch")
        if self.page_content_dispositions:
            if len(self.page_content_dispositions) != len(self.page_numbers):
                raise ValueError("pdf_document_page_content_disposition_count_invalid")
            if any(
                disposition not in {"markdown_materialized", "provider_empty_page"}
                for disposition in self.page_content_dispositions
            ):
                raise ValueError("pdf_document_page_content_disposition_invalid")
            if not self.page_markdown_bytes:
                raise ValueError("pdf_document_page_content_disposition_without_pages")
            for page, disposition in zip(
                self.page_markdown_bytes,
                self.page_content_dispositions,
                strict=True,
            ):
                if bool(page) != (disposition == "markdown_materialized"):
                    raise ValueError("pdf_document_page_content_disposition_mismatch")
        if self.schema_version not in {
            "broker_reports_pdf_document_extraction_v4",
            PDF_DOCUMENT_EXTRACTION_SCHEMA_VERSION,
        }:
            raise ValueError("pdf_document_extraction_schema_version_invalid")
        if self.table_refs and self.schema_version != PDF_DOCUMENT_EXTRACTION_SCHEMA_VERSION:
            raise ValueError("pdf_document_table_refs_require_v5")
        if len({item.local_ref for item in self.table_refs}) != len(self.table_refs):
            raise ValueError("pdf_document_table_ref_duplicate")
        if any(item.page_number not in self.page_numbers for item in self.table_refs):
            raise ValueError("pdf_document_table_page_not_in_document")
        table_associations = {
            (item.page_number, item.markdown_target) for item in self.table_refs
        }
        if len(table_associations) != len(self.table_refs):
            raise ValueError("pdf_document_table_association_duplicate")
        table_pages = tuple(item.page_number for item in self.table_refs)
        if table_pages != tuple(sorted(table_pages)):
            raise ValueError("pdf_document_table_page_order_invalid")
        if self.qualification_status not in {
            "offline_fixture",
            "qualified",
        }:
            raise ValueError("pdf_document_qualification_status_invalid")
        if len({item.local_ref for item in self.image_refs}) != len(self.image_refs):
            raise ValueError("pdf_document_image_ref_duplicate")
        if any(item.page_number not in self.page_numbers for item in self.image_refs):
            raise ValueError("pdf_document_image_page_not_in_document")
        image_pages = tuple(item.page_number for item in self.image_refs)
        if image_pages != tuple(sorted(image_pages)):
            raise ValueError("pdf_document_image_page_order_invalid")
        associations = {
            (item.page_number, item.markdown_target) for item in self.image_refs
        }
        if len(associations) != len(self.image_refs):
            raise ValueError("pdf_document_image_association_duplicate")
        summary_keys = [key for key, _value in self.safe_technical_summary]
        if len(set(summary_keys)) != len(summary_keys):
            raise ValueError("pdf_document_safe_summary_key_duplicate")
        if not set(summary_keys).issubset(_SAFE_TECHNICAL_SUMMARY_KEYS):
            raise ValueError("pdf_document_safe_summary_key_forbidden")
        summary = dict(self.safe_technical_summary)
        if any(type(value) is not int or value < 0 for value in summary.values()):
            raise ValueError("pdf_document_safe_summary_count_invalid")
        expected_counts = {
            "images_count": len(self.image_refs),
            "markdown_bytes": len(self.markdown_bytes),
            "pages_count": self.usage_page_count,
            "tables_count": len(self.table_refs),
        }
        if any(
            key in summary and summary[key] != expected
            for key, expected in expected_counts.items()
        ):
            raise ValueError("pdf_document_safe_summary_count_mismatch")


@dataclass(frozen=True)
class PdfDocumentTableContinuationRAndDResult:
    """One OCR response plus its native table-continuation assessment.

    This is intentionally an R&D result.  It is not a Full Source or
    Canonical input, and it has no production factory or runtime consumer.
    """

    extraction: PdfDocumentExtraction = field(repr=False)
    assessment: PdfDocumentTableContinuationAssessment = field(repr=False)
    source_context: "PdfSourceContext" = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.extraction, PdfDocumentExtraction):
            raise ValueError("pdf_document_annotation_extraction_invalid")
        if not isinstance(self.assessment, PdfDocumentTableContinuationAssessment):
            raise ValueError("pdf_document_annotation_assessment_invalid")
        if not isinstance(self.source_context, PdfSourceContext):
            raise ValueError("pdf_document_annotation_source_context_invalid")
        if len(self.assessment.source_page_numbers) != self.extraction.usage_page_count:
            raise ValueError("pdf_document_annotation_source_page_count_mismatch")
        validate_table_continuation_assessment(
            self.assessment,
            extraction=self.extraction,
            source_context=self.source_context,
        )


@dataclass(frozen=True)
class PdfSourceContext:
    document_ref: str
    expected_pdf_sha256: str
    preflight_page_count: int

    def __post_init__(self) -> None:
        if not self.document_ref:
            raise ValueError("pdf_document_source_ref_required")
        _require_sha256(
            self.expected_pdf_sha256,
            "pdf_document_expected_source_sha256_invalid",
        )
        if self.preflight_page_count < 1:
            raise ValueError("pdf_document_preflight_page_count_invalid")


class PdfDocumentExtractionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfDocumentAiExecutionContract:
    provider_id: str
    requested_model_id: str
    adapter_id: str
    request_contract_version: str
    request_parameters: tuple[tuple[str, bool | int | str], ...]
    request_parameters_sha256: str
    accepted_provider_reported_model_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(
            (
                self.provider_id,
                self.requested_model_id,
                self.adapter_id,
                self.request_contract_version,
                *self.accepted_provider_reported_model_ids,
            )
        ):
            raise ValueError("pdf_document_execution_contract_incomplete")
        keys = tuple(key for key, _value in self.request_parameters)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("pdf_document_execution_contract_parameters_invalid")
        _require_sha256(
            self.request_parameters_sha256,
            "pdf_document_execution_contract_parameters_sha256_invalid",
        )
        material = json.dumps(
            dict(self.request_parameters),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if hashlib.sha256(material).hexdigest() != self.request_parameters_sha256:
            raise ValueError(
                "pdf_document_execution_contract_parameters_sha256_mismatch"
            )

    def safe_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "requested_model_id": self.requested_model_id,
            "adapter_id": self.adapter_id,
            "request_contract_version": self.request_contract_version,
            "request_parameters": dict(self.request_parameters),
            "request_parameters_sha256": self.request_parameters_sha256,
            "accepted_provider_reported_model_ids": list(
                self.accepted_provider_reported_model_ids
            ),
        }


@runtime_checkable
class PdfDocumentExtractor(Protocol):
    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction: ...


@runtime_checkable
class PdfDocumentTableContinuationAssessor(Protocol):
    """Optional native annotation capability of the existing PDF owner."""

    def extract_with_table_continuation_assessment(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
        *,
        source_page_numbers: tuple[int, ...],
        document_annotation_prompt: str,
    ) -> PdfDocumentTableContinuationRAndDResult: ...


@runtime_checkable
class PdfDocumentTableContinuationAnnotationExecution(Protocol):
    """Frozen instruction supplied by the native OpenWebUI composition root."""

    content: str
    prompt_snapshot: dict[str, object]

    @property
    def content_sha256(self) -> str: ...


class UnconfiguredPdfDocumentExtractor:
    adapter_id = "unconfigured_pdf_document_extractor_v1"

    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        del pdf_bytes, source_context
        raise PdfDocumentExtractionError(PDF_DOCUMENT_AI_NOT_CONFIGURED)


class RejectedPdfDocumentExtractor:
    """Keep a static configuration failure inside the normal PDF boundary."""

    def __init__(self, code: str) -> None:
        self._code = code

    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        del pdf_bytes, source_context
        raise PdfDocumentExtractionError(self._code)


class PdfDocumentExtractorFactory:
    """The sole production composition point for PDF understanding.

    Goal #391 admits only deterministic extraction of a usable embedded text
    layer.  The factory intentionally does not inspect OpenWebUI's Mistral
    configuration and never falls through to a provider after local failure.
    """

    FACTORY_REQUIRED = "PdfDocumentExtractorFactory.create is the only production PDF Document AI composition point"
    FORBIDDEN = "Automatic provider selection, retry and fallback are forbidden"

    @staticmethod
    def create(
        *,
        server_request: Any = None,
        image_root: Path | None = None,
    ) -> PdfDocumentExtractor:
        del server_request, image_root
        from .pdfplumber_document_ai import PdfPlumberNativeTextExtractor

        return PdfPlumberNativeTextExtractor()


def is_terminal_pdf_document_ai_request(
    documents: Iterable[Mapping[str, object]],
    blockers: Iterable[Mapping[str, object]],
) -> bool:
    """Return whether every processable document stopped at the PDF boundary."""

    document_list = tuple(documents)
    pdf_document_refs = {
        str(document.get("document_id") or "")
        for document in document_list
        if document.get("container_format") == "pdf" and document.get("document_id")
    }
    blocked_document_refs = {
        str(blocker.get("document_id") or "")
        for blocker in blockers
        if (
            blocker.get("code")
            in {
                PDF_DOCUMENT_AI_NOT_CONFIGURED,
                PDF_DOCUMENT_AI_PAYMENT_REQUIRED,
            }
            or (
                blocker.get("code") == "parser_failed"
                and str(
                    blocker.get("reason_code") or blocker.get("reason") or ""
                ).startswith(("PDF_DOCUMENT_", "PDF_NATIVE_TEXT_"))
            )
        )
        and str(blocker.get("document_id") or "") in pdf_document_refs
    }
    if not blocked_document_refs:
        return False
    processable_document_refs = {
        str(document.get("document_id") or "")
        for document in document_list
        if document.get("container_format") != "zip" and document.get("document_id")
    }
    return bool(processable_document_refs) and processable_document_refs.issubset(
        blocked_document_refs
    )


def validate_extraction_source(
    extraction: PdfDocumentExtraction,
    *,
    pdf_bytes: bytes,
    source_context: PdfSourceContext,
) -> None:
    actual_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    if actual_sha256 != source_context.expected_pdf_sha256:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_SOURCE_CUSTODY_MISMATCH")
    if extraction.source_pdf_sha256 != actual_sha256:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_EXTRACTION_SOURCE_MISMATCH")
    if extraction.usage_page_count != source_context.preflight_page_count:
        raise PdfDocumentExtractionError("PDF_DOCUMENT_EXTRACTION_PAGE_COUNT_MISMATCH")


def _require_sha256(value: str, code: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(code)
