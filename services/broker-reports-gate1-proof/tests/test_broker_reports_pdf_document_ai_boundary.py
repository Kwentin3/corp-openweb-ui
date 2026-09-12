from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import io
import inspect
import json
import socket
import sys
import zipfile
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from broker_reports_gate1.artifact_models import (
    PRIVATE_BINARY_ARTIFACT_TYPE,
    ArtifactAccessContext,
    ArtifactStoreError,
    RetentionPolicy,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.bounded_graph import (
    Gate1BoundedGraphConfig,
    Gate1BoundedGraphFactory,
)
from broker_reports_gate1.gate2_handoff import persist_gate1_result
from broker_reports_gate1.inputs import FileInput
from broker_reports_gate1.normalizer import Gate1Normalizer
from broker_reports_gate1.ordinary_trade_production_runtime import (
    ORDINARY_TRADE_PRODUCTION_ROUTE_ID,
    OrdinaryTradeProductionRuntimeFactory,
)
from broker_reports_gate1.pdf_document_ai import (
    PDF_DOCUMENT_AI_NOT_CONFIGURED,
    PdfDocumentExtraction,
    PdfDocumentExtractionError,
    PdfDocumentExtractorFactory,
    PdfDocumentImageRef,
    PdfDocumentSelectedPageBinding,
    PdfDocumentTableContinuationAssessment,
    PdfDocumentTableContinuationLink,
    PdfDocumentTableContinuationRAndDResult,
    PdfDocumentTableRef,
    PdfSourceContext,
    UnconfiguredPdfDocumentExtractor,
    is_terminal_pdf_document_ai_request,
    pdf_document_selected_page_bindings_sha256,
    pdf_document_table_refs_sha256,
)
from broker_reports_gate1.pdfplumber_document_ai import (
    PDF_NATIVE_TEXT_UNUSABLE,
    PdfPlumberNativeTextExtractor,
)
from broker_reports_gate1.pdf_table_continuation_annotation_prompt import (
    PROMPT_COMMAND,
    PROMPT_CONTRACT_ID,
    PROMPT_REQUIRED_TAG,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND,
    PdfTableContinuationAnnotationExecution,
    PdfTableContinuationAnnotationManagedPrompt,
    execution_from_managed_prompt,
    pdf_table_continuation_annotation_prompt_hash,
)
from openwebui_actions.broker_reports_gate1_pipe import Pipe


REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_PDF = next(
    (REPO_ROOT / "docs" / "reports" / "2026-09-02" / "artifacts").glob(
        "*/fidelity/source.pdf"
    )
)
BUNDLED_PIPE_PATH = (
    REPO_ROOT
    / "services"
    / "broker-reports-gate1-proof"
    / "openwebui_actions"
    / "broker_reports_gate1_pipe_bundled.py"
)


def _input(pdf_bytes: bytes) -> FileInput:
    return FileInput.from_bytes(
        private_ref="public-pdf-boundary-test",
        filename="public-sample.pdf",
        content=pdf_bytes,
        mime_type="application/pdf",
        source_kind="synthetic",
    )


class _OfflineFixtureExtractor:
    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        page_markdown = b"# Exact offline fixture\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        page_markdown_bytes = tuple(
            page_markdown for _ in range(source_context.preflight_page_count)
        )
        markdown = b"\n\n".join(page_markdown_bytes)
        return PdfDocumentExtraction(
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            page_numbers=tuple(range(1, source_context.preflight_page_count + 1)),
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            image_refs=(),
            provider_id="offline_fixture_provider",
            requested_model_id="offline_fixture_model",
            model_id="offline_fixture_model",
            adapter_id="offline_fixture_adapter_v1",
            request_contract_version="offline_fixture_request_v1",
            request_parameters=(("include_image_base64", True),),
            request_parameters_sha256=hashlib.sha256(
                b'{"include_image_base64":true}'
            ).hexdigest(),
            page_markdown_sha256=tuple(
                hashlib.sha256(page).hexdigest() for page in page_markdown_bytes
            ),
            qualification_status="offline_fixture",
            usage_page_count=source_context.preflight_page_count,
            page_markdown_bytes=page_markdown_bytes,
            safe_technical_summary=(
                ("markdown_bytes", len(markdown)),
                ("pages_count", source_context.preflight_page_count),
            ),
        )


class _SecondOfflineFixtureExtractor(_OfflineFixtureExtractor):
    pass


class _AnnotatedOfflineFixtureExtractor(_OfflineFixtureExtractor):
    def __init__(self) -> None:
        self.annotation_calls: list[tuple[tuple[int, ...], str]] = []

    def extract(self, *_args, **_kwargs):
        raise AssertionError("annotation execution must use one annotated OCR call")

    def extract_with_table_continuation_assessment(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
        *,
        source_page_numbers: tuple[int, ...],
        document_annotation_prompt: str,
    ) -> PdfDocumentTableContinuationRAndDResult:
        self.annotation_calls.append((source_page_numbers, document_annotation_prompt))
        extraction = super().extract(pdf_bytes, source_context)
        table_one = b"<table><tr><th>date</th></tr><tr><td>1</td></tr></table>"
        table_two = b"<table><tr><td>2</td></tr></table>"
        pages = tuple(
            (
                b"# Exact offline fixture\n[first](table-1.html)"
                if page_number == 1
                else b"# Exact offline fixture\n[second](table-2.html)"
                if page_number == 2
                else b"# Exact offline fixture"
            )
            for page_number in extraction.page_numbers
        )
        markdown = b"\n\n".join(pages)
        extraction = replace(
            extraction,
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            page_markdown_bytes=pages,
            page_markdown_sha256=tuple(
                hashlib.sha256(page).hexdigest() for page in pages
            ),
            safe_technical_summary=(
                ("markdown_bytes", len(markdown)),
                ("pages_count", len(pages)),
            ),
            table_refs=(
                PdfDocumentTableRef(
                    page_number=1,
                    markdown_target="table-1.html",
                    local_ref="pdftable_normalizer_1",
                    sha256=hashlib.sha256(table_one).hexdigest(),
                    html_bytes=table_one,
                ),
                PdfDocumentTableRef(
                    page_number=2,
                    markdown_target="table-2.html",
                    local_ref="pdftable_normalizer_2",
                    sha256=hashlib.sha256(table_two).hexdigest(),
                    html_bytes=table_two,
                ),
            ),
        )
        bindings = tuple(
            PdfDocumentSelectedPageBinding(
                local_page_number=index + 1,
                source_page_number=page_number,
            )
            for index, page_number in enumerate(source_page_numbers)
        )
        assessment = PdfDocumentTableContinuationAssessment(
            source_pdf_sha256=extraction.source_pdf_sha256,
            table_refs_sha256=pdf_document_table_refs_sha256(extraction.table_refs),
            raw_annotation_sha256="a" * 64,
            request_parameters_sha256="b" * 64,
            annotation_prompt_sha256=hashlib.sha256(
                document_annotation_prompt.encode("utf-8")
            ).hexdigest(),
            annotation_schema_sha256="c" * 64,
            selected_page_bindings_sha256=pdf_document_selected_page_bindings_sha256(
                bindings
            ),
            source_page_numbers=source_page_numbers,
            selected_page_bindings=bindings,
            links=(
                PdfDocumentTableContinuationLink(
                    parent_table_ref="pdftable_normalizer_1",
                    child_table_ref="pdftable_normalizer_2",
                ),
            ),
        )
        return PdfDocumentTableContinuationRAndDResult(
            extraction=extraction,
            assessment=assessment,
            source_context=source_context,
        )


class _NoLinkAnnotatedOfflineFixtureExtractor(_AnnotatedOfflineFixtureExtractor):
    def extract_with_table_continuation_assessment(self, *args, **kwargs):
        result = super().extract_with_table_continuation_assessment(*args, **kwargs)
        return replace(result, assessment=replace(result.assessment, links=()))


def _annotation_execution() -> PdfTableContinuationAnnotationExecution:
    content = "Assess direct physical table continuation only."
    prompt = PdfTableContinuationAnnotationManagedPrompt(
        prompt_ref="test-prompt",
        command=PROMPT_COMMAND,
        version="test-history",
        content=content,
        hash=pdf_table_continuation_annotation_prompt_hash(content),
        source="test",
        template_id=PROMPT_TEMPLATE_ID,
        template_kind=PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PROMPT_CONTRACT_ID,
        input_schema_version="broker_reports_pdf_document_annotation_input_v1",
        output_schema_id="mistral_ocr_table_continuation_annotation_v4",
        output_schema_version="mistral_ocr_table_continuation_annotation_v4",
        tags=(PROMPT_REQUIRED_TAG,),
        safe_metadata={"name": "test"},
    )
    return execution_from_managed_prompt(prompt)


def test_pipe_leaves_annotation_unresolved_when_feature_is_disabled() -> None:
    pipe = Pipe()

    assert (
        asyncio.run(
            pipe._pdf_table_continuation_annotation_execution(
                user=None,
                metadata={},
            )
        )
        is None
    )


class _ProviderEmptyPageFixtureExtractor(_OfflineFixtureExtractor):
    """A successful provider envelope with one explicitly empty PDF page."""

    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        pages = tuple(
            b"# Exact offline fixture\n"
            if page != 2
            else b""
            for page in range(1, source_context.preflight_page_count + 1)
        )
        markdown = b"\n\n".join(pages)
        return PdfDocumentExtraction(
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            page_numbers=tuple(range(1, source_context.preflight_page_count + 1)),
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            image_refs=(),
            provider_id="offline_fixture_provider",
            requested_model_id="offline_fixture_model",
            model_id="offline_fixture_model",
            adapter_id="offline_fixture_adapter_v1",
            request_contract_version="offline_fixture_request_v1",
            request_parameters=(("include_image_base64", True),),
            request_parameters_sha256=hashlib.sha256(
                b'{"include_image_base64":true}'
            ).hexdigest(),
            page_markdown_sha256=tuple(
                hashlib.sha256(page).hexdigest() for page in pages
            ),
            qualification_status="offline_fixture",
            usage_page_count=source_context.preflight_page_count,
            page_markdown_bytes=pages,
            page_content_dispositions=tuple(
                "provider_empty_page" if not page else "markdown_materialized"
                for page in pages
            ),
        )


class _BrokerReportFixtureExtractor(_OfflineFixtureExtractor):
    """A source-bound Document AI representation with no local PDF parser."""

    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        base = super().extract(pdf_bytes, source_context)
        page_markdown = (
            b"# Broker Activity Statement\n\n"
            b"## Transactions\n\n"
            b"| Symbol | Quantity | Proceeds |\n|---|---:|---:|\n| SAFE | 1 | 10 |\n"
        )
        pages = tuple(page_markdown for _ in base.page_numbers)
        markdown = b"\n\n".join(pages)
        return replace(
            base,
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            page_markdown_bytes=pages,
            page_markdown_sha256=tuple(
                hashlib.sha256(page).hexdigest() for page in pages
            ),
            safe_technical_summary=(
                ("markdown_bytes", len(markdown)),
                ("pages_count", len(pages)),
            ),
        )


class _RussianBrokerReportFixtureExtractor(_BrokerReportFixtureExtractor):
    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        base = super().extract(pdf_bytes, source_context)
        page_markdown = (
            b"# \xd0\x9e\xd1\x82\xd1\x87\xd0\xb5\xd1\x82 \xd0\xb1\xd1\x80\xd0\xbe\xd0\xba\xd0\xb5\xd1\x80\xd0\xb0\n\n"
            b"## \xd0\xa1\xd0\xb4\xd0\xb5\xd0\xbb\xd0\xba\xd0\xb8\n\n"
            b"| \xd0\x94\xd0\xb0\xd1\x82\xd0\xb0 | \xd0\xa1\xd1\x83\xd0\xbc\xd0\xbc\xd0\xb0 | \xd0\x92\xd0\xb0\xd0\xbb\xd1\x8e\xd1\x82\xd0\xb0 |\n"
            b"|---|---:|---|\n| 2026-01-01 | 10 | USD |\n"
        )
        pages = tuple(page_markdown for _ in base.page_numbers)
        markdown = b"\n\n".join(pages)
        return replace(
            base,
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            page_markdown_bytes=pages,
            page_markdown_sha256=tuple(
                hashlib.sha256(page).hexdigest() for page in pages
            ),
            safe_technical_summary=(
                ("markdown_bytes", len(markdown)),
                ("pages_count", len(pages)),
            ),
        )


class _GenericRussianFinancialFixtureExtractor(_BrokerReportFixtureExtractor):
    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        base = super().extract(pdf_bytes, source_context)
        page_markdown = (
            b"# \xd0\xa3\xd1\x87\xd0\xb5\xd0\xb1\xd0\xbd\xd0\xb0\xd1\x8f \xd1\x82\xd0\xb0\xd0\xb1\xd0\xbb\xd0\xb8\xd1\x86\xd0\xb0\n\n"
            b"| \xd0\x94\xd0\xb0\xd1\x82\xd0\xb0 \xd1\x81\xd0\xb4\xd0\xb5\xd0\xbb\xd0\xba\xd0\xb8 | \xd0\xa1\xd1\x83\xd0\xbc\xd0\xbc\xd0\xb0 | \xd0\x92\xd0\xb0\xd0\xbb\xd1\x8e\xd1\x82\xd0\xb0 |\n"
            b"|---|---:|---|\n| 2026-01-01 | 10 | USD |\n"
        )
        pages = tuple(page_markdown for _ in base.page_numbers)
        markdown = b"\n\n".join(pages)
        return replace(
            base,
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            page_markdown_bytes=pages,
            page_markdown_sha256=tuple(
                hashlib.sha256(page).hexdigest() for page in pages
            ),
            safe_technical_summary=(
                ("markdown_bytes", len(markdown)),
                ("pages_count", len(pages)),
            ),
        )


class _OfflineImageFixtureExtractor(_OfflineFixtureExtractor):
    def extract(
        self,
        pdf_bytes: bytes,
        source_context: PdfSourceContext,
    ) -> PdfDocumentExtraction:
        image_bytes = b"\x89PNG\r\n\x1a\nneutral-image"
        first_page = b"# Exact offline fixture\n\n![image](img-0.png)"
        other_page = b"# Exact offline fixture"
        page_markdown_bytes = (first_page,) + tuple(
            other_page for _ in range(source_context.preflight_page_count - 1)
        )
        markdown = b"\n\n".join(page_markdown_bytes)
        return PdfDocumentExtraction(
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            page_numbers=tuple(range(1, source_context.preflight_page_count + 1)),
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            image_refs=(
                PdfDocumentImageRef(
                    page_number=1,
                    markdown_target="img-0.png",
                    local_ref="pdfimg_normalizer_fixture",
                    sha256=hashlib.sha256(image_bytes).hexdigest(),
                    media_type="image/png",
                    content_bytes=image_bytes,
                ),
            ),
            provider_id="offline_fixture_provider",
            requested_model_id="offline_fixture_model",
            model_id="offline_fixture_model",
            adapter_id="offline_fixture_adapter_v1",
            request_contract_version="offline_fixture_request_v1",
            request_parameters=(("include_image_base64", True),),
            request_parameters_sha256=hashlib.sha256(
                b'{"include_image_base64":true}'
            ).hexdigest(),
            page_markdown_sha256=tuple(
                hashlib.sha256(page).hexdigest() for page in page_markdown_bytes
            ),
            qualification_status="offline_fixture",
            usage_page_count=source_context.preflight_page_count,
            page_markdown_bytes=page_markdown_bytes,
        )


def test_production_factory_is_sole_native_text_composition() -> None:
    extractor = PdfDocumentExtractorFactory.create()

    assert isinstance(extractor, PdfPlumberNativeTextExtractor)
    assert "_pdf_document_extractor" in inspect.signature(Gate1Normalizer).parameters
    assert "pdf_document_extractor" not in inspect.signature(Gate1Normalizer).parameters


def _unconfigured_normalizer(**kwargs: object) -> Gate1Normalizer:
    return Gate1Normalizer(
        _pdf_document_extractor=UnconfiguredPdfDocumentExtractor(),
        **kwargs,
    )


def test_native_text_factory_rejects_pdf_without_usable_text_layer() -> None:
    from pypdf import PdfWriter

    blank_pdf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(blank_pdf)
    pdf_bytes = blank_pdf.getvalue()

    with pytest.raises(PdfDocumentExtractionError) as exc_info:
        PdfDocumentExtractorFactory.create().extract(
            pdf_bytes,
            PdfSourceContext(
                document_ref="blank-native-text-pdf",
                expected_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
                preflight_page_count=1,
            ),
        )

    assert exc_info.value.code == PDF_NATIVE_TEXT_UNUSABLE


def test_unconfigured_pdf_is_terminal_before_network_and_creates_no_downstream() -> None:
    pdf_bytes = PUBLIC_PDF.read_bytes()

    with patch.object(socket, "create_connection", side_effect=AssertionError("network")), patch.object(
        socket.socket,
        "connect",
        side_effect=AssertionError("network"),
    ):
        result = _unconfigured_normalizer().normalize([_input(pdf_bytes)])

    blocker_codes = {
        item["code"] for item in result.package["normalization_blockers"]
    }
    assert PDF_DOCUMENT_AI_NOT_CONFIGURED in blocker_codes
    assert result.package["private_normalized_source_payloads"] == []
    assert result.package["private_normalized_source_units"] == []
    assert result.package["private_normalized_table_projections"] == []
    assert result.package["taxonomy_candidates"] == []
    assert "canonical_artifacts" not in result.package
    assert "source_facts" not in result.package
    assert "gate1_issue_ledger" not in result.package
    assert "document_usage_classification" not in result.package
    assert "domain_context_packet" not in result.package
    assert "domain_ingestion_summary" not in result.package


def test_archive_containing_only_pdf_is_terminal_before_domain_ingestion() -> None:
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("public-sample.pdf", PUBLIC_PDF.read_bytes())

    result = _unconfigured_normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="public-pdf-archive-boundary-test",
                filename="public-sample.zip",
                content=archive_buffer.getvalue(),
                mime_type="application/zip",
                source_kind="synthetic",
            )
        ]
    )

    assert PDF_DOCUMENT_AI_NOT_CONFIGURED in {
        item["code"] for item in result.package["normalization_blockers"]
    }
    assert result.package["normalization_run"]["run_status"] == "failed_safe"
    assert "gate1_issue_ledger" not in result.package
    assert "document_usage_classification" not in result.package
    assert "domain_context_packet" not in result.package
    assert "domain_ingestion_summary" not in result.package


def test_archive_with_two_duplicate_pdfs_is_terminal_and_valid_before_downstream() -> None:
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("first.pdf", PUBLIC_PDF.read_bytes())
        archive.writestr("second.pdf", PUBLIC_PDF.read_bytes())

    result = _unconfigured_normalizer().normalize(
        [
            FileInput.from_bytes(
                private_ref="public-multi-pdf-archive-boundary-test",
                filename="public-multi-pdf.zip",
                content=archive_buffer.getvalue(),
                mime_type="application/zip",
                source_kind="synthetic",
            )
        ]
    )

    pdf_documents = [
        item
        for item in result.package["document_inventory"]["documents"]
        if item["container_format"] == "pdf"
    ]
    pdf_blockers = [
        item
        for item in result.package["normalization_blockers"]
        if item["code"] == PDF_DOCUMENT_AI_NOT_CONFIGURED
    ]
    assert len(pdf_documents) == 2
    assert len(pdf_blockers) == 2
    assert pdf_documents[1]["duplicate_of_document_id"] == pdf_documents[0]["document_id"]
    assert result.package["normalization_run"]["run_status"] == "failed_safe"
    assert result.package["validation_result"]["status"] == "passed"
    for key in (
        "canonical_artifacts",
        "source_facts",
        "gate1_issue_ledger",
        "document_usage_classification",
        "domain_context_packet",
        "domain_ingestion_summary",
    ):
        assert key not in result.package


def _pipe_file(
    file_id: str,
    filename: str,
    mime_type: str,
    content_bytes: bytes,
) -> dict:
    return {
        "type": "file",
        "file": {
            "id": file_id,
            "filename": filename,
            "mime_type": mime_type,
            "content_bytes": content_bytes,
        },
    }


def _run_mixed_pipe(
    pipe_variant: str,
    tmp_path: Path,
    files: list[dict],
    *,
    unconfigured_pdf: bool = False,
) -> tuple[object, str, int]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    maintained_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1.")
    }
    try:
        if pipe_variant == "bundled":
            for name in maintained_modules:
                del sys.modules[name]
            spec = importlib.util.spec_from_file_location(
                "broker_reports_gate1_pdf_boundary_bundle_test",
                BUNDLED_PIPE_PATH,
            )
            if spec is None or spec.loader is None:
                raise AssertionError("could not load bundled Gate 1 Pipe")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            pipe_type = module.Pipe
            pipe_module = module
        else:
            pipe_type = Pipe
            pipe_module = sys.modules[pipe_type.__module__]
        pipe = pipe_type()
        normalizer_type = pipe_module.Gate1Normalizer
        unconfigured_type = sys.modules[
            "broker_reports_gate1.pdf_document_ai"
        ].UnconfiguredPdfDocumentExtractor

        def unconfigured_pipe_normalizer(**kwargs: object) -> Gate1Normalizer:
            return normalizer_type(
                _pdf_document_extractor=unconfigured_type(),
                **kwargs,
            )

        pipe.valves.artifact_store_path = str(tmp_path / "artifacts.sqlite3")
        pipe.valves.artifact_payload_root = str(tmp_path / "payloads")
        owned_files = {
            item["file"]["id"]: SimpleNamespace(
                filename=item["file"]["filename"],
                content_type=item["file"]["mime_type"],
                payload=item["file"]["content_bytes"],
            )
            for item in files
        }

        class OwnedFileResolver:
            async def resolve(self, *, file_id: str, actor_user_id: str) -> object:
                assert actor_user_id == "mixed-pdf-boundary-user"
                return owned_files[file_id]

        pipe._openwebui_file_bytes_resolver = lambda: OwnedFileResolver()

        def forbidden(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("mixed PDF route must not call the network")

        async def run() -> tuple[str, int]:
            with (
                (
                    patch.object(
                        pipe_module,
                        "Gate1Normalizer",
                        side_effect=unconfigured_pipe_normalizer,
                    )
                    if unconfigured_pdf
                    else nullcontext()
                ),
                patch.object(
                    pipe,
                    "_maybe_run_passport_stage",
                    wraps=pipe._maybe_run_passport_stage,
                ) as passport_stage,
                patch.object(socket, "create_connection", side_effect=forbidden),
                patch.object(socket.socket, "connect", side_effect=forbidden),
            ):
                content = await pipe.pipe(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": "Gate 1 mixed normalization",
                                "files": files,
                            }
                        ]
                    },
                    __user__={"id": "mixed-pdf-boundary-user"},
                    __metadata__={
                        "chat_id": "mixed-pdf-boundary-chat",
                        "model_id": "broker_reports_gate1_pipe_test",
                    },
                )
                return content, passport_stage.await_count

        content, passport_await_count = asyncio.run(run())
        return pipe, content, passport_await_count
    finally:
        if pipe_variant == "bundled":
            for name in list(sys.modules):
                if name == "broker_reports_gate1" or name.startswith(
                    "broker_reports_gate1."
                ):
                    del sys.modules[name]
            sys.modules.update(maintained_modules)


@pytest.mark.parametrize("pipe_variant", ("maintained", "bundled"))
def test_mixed_csv_and_pdf_continues_reduced_subset_in_production_pipe(
    pipe_variant: str,
    tmp_path: Path,
) -> None:
    pipe, content, passport_await_count = _run_mixed_pipe(
        pipe_variant,
        tmp_path,
        [
            _pipe_file(
                "mixed-csv",
                "operations.csv",
                "text/csv",
                b"symbol,quantity\nSYNTH-A,1\n",
            ),
            _pipe_file(
                "mixed-pdf",
                "statement.pdf",
                "application/pdf",
                PUBLIC_PDF.read_bytes(),
            ),
        ],
        unconfigured_pdf=True,
    )

    report = pipe.last_safe_report
    assert report is not None
    documents = {item["container_format"]: item for item in report["documents"]}
    included = set(report["gate2_handoff"]["included_document_ids"])
    assert report["run_status"] == "completed_with_blockers"
    assert report["validation_result"]["status"] == "passed"
    assert report["gate2_handoff_status"] == "ready_with_reduced_subset"
    assert documents["csv"]["document_id"] in included
    assert documents["pdf"]["document_id"] not in included
    assert report["private_artifact_summary"]["private_normalized_source_units_count"] > 0
    assert report["domain_context_packet"] is not None
    assert passport_await_count == 1
    assert pipe.last_workload_snapshot["state"] == "completed"
    assert pipe.last_workload_snapshot["cleanup_status"] == "cleaned"
    assert "Gate 1 stopped at the PDF Document AI boundary" not in content


@pytest.mark.parametrize("pipe_variant", ("maintained", "bundled"))
def test_archive_pdf_and_xml_continues_xml_in_production_pipe(
    pipe_variant: str,
    tmp_path: Path,
) -> None:
    mixed_archive_buffer = io.BytesIO()
    with zipfile.ZipFile(mixed_archive_buffer, "w") as archive:
        archive.writestr("statement.pdf", PUBLIC_PDF.read_bytes())
        archive.writestr(
            "operations.xml",
            b"<operations><quantity>1</quantity></operations>",
        )
    control_archive_buffer = io.BytesIO()
    with zipfile.ZipFile(control_archive_buffer, "w") as archive:
        archive.writestr(
            "operations.xml",
            b"<operations><quantity>1</quantity></operations>",
        )

    pipe, content, passport_await_count = _run_mixed_pipe(
        pipe_variant,
        tmp_path / "mixed",
        [
            _pipe_file(
                "mixed-archive",
                "mixed.zip",
                "application/zip",
                mixed_archive_buffer.getvalue(),
            )
        ],
        unconfigured_pdf=True,
    )
    control_pipe, _control_content, control_passport_await_count = _run_mixed_pipe(
        pipe_variant,
        tmp_path / "control",
        [
            _pipe_file(
                "xml-only-archive",
                "xml-only.zip",
                "application/zip",
                control_archive_buffer.getvalue(),
            )
        ],
        unconfigured_pdf=True,
    )

    report = pipe.last_safe_report
    control_report = control_pipe.last_safe_report
    assert report is not None
    assert control_report is not None
    documents = {item["container_format"]: item for item in report["documents"]}
    eligibility = {
        item["document_id"]: item
        for item in report["document_source_eligibility"]["entries"]
    }
    control_xml_document = next(
        item
        for item in control_report["documents"]
        if item["container_format"] == "xml"
    )
    control_xml_eligibility = next(
        item
        for item in control_report["document_source_eligibility"]["entries"]
        if item["document_id"] == control_xml_document["document_id"]
    )
    xml_eligibility = eligibility[documents["xml"]["document_id"]]
    pdf_eligibility = eligibility[documents["pdf"]["document_id"]]
    assert report["run_status"] == "completed_with_blockers"
    assert report["validation_result"]["status"] == "passed"
    assert report["gate2_handoff_status"] == control_report["gate2_handoff_status"]
    assert report["gate2_handoff_mode"] == control_report["gate2_handoff_mode"]
    assert {
        key: xml_eligibility[key]
        for key in (
            "source_eligibility",
            "can_enter_gate2",
            "reason_codes",
            "review_action",
        )
    } == {
        key: control_xml_eligibility[key]
        for key in (
            "source_eligibility",
            "can_enter_gate2",
            "reason_codes",
            "review_action",
        )
    }
    assert pdf_eligibility["source_eligibility"] == "excluded_from_gate2"
    assert pdf_eligibility["reason_codes"] == [PDF_DOCUMENT_AI_NOT_CONFIGURED]
    private_summary = report["private_artifact_summary"]
    control_private_summary = control_report["private_artifact_summary"]
    for key in (
        "private_normalized_slices_count",
        "private_normalized_source_payloads_count",
        "private_normalized_source_units_count",
        "private_normalized_table_projections_count",
        "full_source_raw_content_chat_visible",
        "chat_visible_raw_slice_content",
    ):
        assert private_summary[key] == control_private_summary[key]
    assert private_summary["private_normalized_source_units_count"] > 0
    assert report["domain_context_packet"] is not None
    assert passport_await_count == 1
    assert control_passport_await_count == 1
    assert pipe.last_workload_snapshot["state"] == "completed"
    assert pipe.last_workload_snapshot["cleanup_status"] == "cleaned"
    assert "Gate 1 stopped at the PDF Document AI boundary" not in content


def test_pipe_returns_unconfigured_pdf_before_any_provider_or_semantic_artifact(
    tmp_path: Path,
) -> None:
    pdf_bytes = PUBLIC_PDF.read_bytes()
    pipe = Pipe()
    pipe.valves.artifact_store_path = str(tmp_path / "artifacts.sqlite3")
    pipe.valves.artifact_payload_root = str(tmp_path / "payloads")
    pipe.valves.passport_enabled = True
    pipe.valves.passport_model_id = "must-not-run"
    pipe.valves.clarification_enabled = True
    pipe.valves.clarification_model_id = "must-not-run"

    class OwnedFileResolver:
        async def resolve(self, *, file_id: str, actor_user_id: str) -> object:
            assert file_id == "pdf-document-ai-boundary"
            assert actor_user_id == "pdf-boundary-user"
            return SimpleNamespace(
                filename="boundary.pdf",
                content_type="application/pdf",
                payload=pdf_bytes,
            )

    pipe._openwebui_file_bytes_resolver = lambda: OwnedFileResolver()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("downstream stage must not run")

    body = {
        "messages": [
            {
                "role": "user",
                "content": "Gate 1 normalization",
                "files": [
                    {
                        "type": "file",
                        "file": {
                            "id": "pdf-document-ai-boundary",
                            "filename": "boundary.pdf",
                            "mime_type": "application/pdf",
                            "content_bytes": pdf_bytes,
                        },
                    }
                ],
            }
        ]
    }

    async def run() -> str:
        with (
            patch.object(
                sys.modules[Pipe.__module__],
                "Gate1Normalizer",
                side_effect=_unconfigured_normalizer,
            ),
            patch.object(pipe, "_maybe_run_passport_stage", side_effect=forbidden),
            patch.object(pipe, "_maybe_run_clarification_stage", side_effect=forbidden),
            patch.object(pipe, "_maybe_run_ndfl_gate3", side_effect=forbidden),
            patch.object(
                pipe, "_openwebui_completion_dependencies", side_effect=forbidden
            ),
            patch.object(socket, "create_connection", side_effect=forbidden),
            patch.object(socket.socket, "connect", side_effect=forbidden),
        ):
            return await pipe.pipe(
                body,
                __user__={"id": "pdf-boundary-user"},
                __metadata__={
                    "chat_id": "pdf-boundary-chat",
                    "model_id": "broker_reports_gate1_pipe_test",
                },
            )

    content = asyncio.run(run())

    assert content
    assert pipe.last_artifact_manifest is not None
    artifact_types = set(pipe.last_artifact_manifest["artifact_refs_by_type"])
    assert artifact_types.isdisjoint(
        {
            "full_source_v0",
            "canonical_artifact_v1",
            "normalized_source_facts_v0",
            "gate1_issue_ledger_v0",
            "document_usage_classification_v0",
            "domain_context_packet_v0",
            "domain_ingestion_summary_v0",
        }
    )
    assert pipe.last_safe_report is not None
    assert {item["code"] for item in pipe.last_safe_report["blockers"]} >= {
        PDF_DOCUMENT_AI_NOT_CONFIGURED
    }
    assert PDF_DOCUMENT_AI_NOT_CONFIGURED in content
    assert "PDF Document AI is not configured" in content
    assert "successfully processed" not in content.lower()


def test_offline_adapters_with_same_envelope_have_identical_representation_handoff() -> None:
    pdf_bytes = PUBLIC_PDF.read_bytes()
    first = Gate1Normalizer(
        _pdf_document_extractor=_OfflineFixtureExtractor()
    ).normalize([_input(pdf_bytes)])
    second = Gate1Normalizer(
        _pdf_document_extractor=_SecondOfflineFixtureExtractor()
    ).normalize([_input(pdf_bytes)])

    assert first.package["private_normalized_source_payloads"] == second.package[
        "private_normalized_source_payloads"
    ]
    assert first.package["private_normalized_source_units"] == second.package[
        "private_normalized_source_units"
    ]
    assert first.package["private_normalized_table_projections"] == []
    payload = first.package["private_normalized_source_payloads"][0]
    assert payload["normalized_projection"]["text"].startswith(
        "# Exact offline fixture"
    )
    assert payload["format_reason_codes"] == [
        "document_ai_content_not_semantically_parsed"
    ]


def test_document_ai_pdf_representation_reaches_existing_taxonomy_owner() -> None:
    """A successful OCR representation must not be hidden behind the PDF profile."""

    result = Gate1Normalizer(
        _pdf_document_extractor=_BrokerReportFixtureExtractor()
    ).normalize(
        [_input(PUBLIC_PDF.read_bytes())],
        input_context={
            "source_policy": {
                "mode": "native_ndfl_workspace_model",
                "explicit": True,
                "accept_pdf_html_source_roles": True,
            }
        },
    )

    candidate = result.package["taxonomy_candidates"][0]
    eligibility = result.package["document_source_eligibility"]["entries"][0]
    assert candidate["document_class_candidate"] == "source_broker_report"
    assert candidate["source_role_policy_status"] == "approved"
    assert eligibility["source_eligibility"] == "accepted_for_gate2"
    assert "unknown_role" not in {
        item["code"] for item in result.package["normalization_blockers"]
    }


def test_russian_broker_report_heading_is_admitted_without_a_second_llm_stage() -> None:
    result = Gate1Normalizer(
        _pdf_document_extractor=_RussianBrokerReportFixtureExtractor()
    ).normalize(
        [_input(PUBLIC_PDF.read_bytes())],
        input_context={
            "source_policy": {
                "mode": "native_ndfl_workspace_model",
                "explicit": True,
                "accept_pdf_html_source_roles": True,
            }
        },
    )

    candidate = result.package["taxonomy_candidates"][0]
    eligibility = result.package["document_source_eligibility"]["entries"][0]
    assert candidate["document_class_candidate"] == "source_broker_report"
    assert eligibility["source_eligibility"] == "accepted_for_gate2"
    assert result.package["gate2_handoff"]["handoff_mode"] != "gate2_blocked_no_eligible_sources"


def test_generic_russian_financial_words_do_not_admit_an_instructional_table() -> None:
    result = Gate1Normalizer(
        _pdf_document_extractor=_GenericRussianFinancialFixtureExtractor()
    ).normalize(
        [_input(PUBLIC_PDF.read_bytes())],
        input_context={
            "source_policy": {
                "mode": "native_ndfl_workspace_model",
                "explicit": True,
                "accept_pdf_html_source_roles": True,
            }
        },
    )

    candidate = result.package["taxonomy_candidates"][0]
    eligibility = result.package["document_source_eligibility"]["entries"][0]
    assert candidate["document_class_candidate"] == "unknown_or_needs_review"
    assert eligibility["source_eligibility"] == "metadata_review_required"
    assert result.package["gate2_handoff"]["handoff_mode"] == "gate2_blocked_requires_metadata_review"


def _bounded_pdf_normalization(tmp_path: Path):
    pdf_input = _input(PUBLIC_PDF.read_bytes())
    normalizer = Gate1Normalizer(
        _pdf_document_extractor=_OfflineImageFixtureExtractor()
    )
    run_id = normalizer.plan_run_id([pdf_input])
    context = ArtifactAccessContext(
        user_id="pdf-normalizer-user",
        normalization_run_id=run_id,
        case_id="pdf-normalizer-case",
        chat_id="pdf-normalizer-chat",
        workspace_model_id="pdf-normalizer-workspace",
        allow_private=True,
    )
    retention = RetentionPolicy(
        mode="synthetic_dev",
        ttl_seconds=None,
        expires_at=None,
        explicit=True,
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    graph = Gate1BoundedGraphFactory(
        Gate1BoundedGraphConfig(
            store=store,
            context=context,
            retention_policy=retention,
            source_file_refs=(
                {
                    "provider": "openwebui",
                    "openwebui_file_id": "pdf-normalizer-upload",
                    "content_type": "application/pdf",
                    "source_deleted": False,
                },
            ),
        )
    ).create(normalization_run_id=run_id)
    return normalizer, pdf_input, store, graph, context, retention


def test_normalizer_routes_pdf_markdown_unit_and_image_through_atomic_graph(
    tmp_path: Path,
) -> None:
    normalizer, pdf_input, store, graph, context, _retention = (
        _bounded_pdf_normalization(tmp_path)
    )

    result = normalizer.normalize([pdf_input], bounded_graph=graph)

    payload = result.package["private_normalized_source_payloads"][0]
    association = payload["document_ai_image_refs"][0]
    assert graph.refs_by_type[PRIVATE_BINARY_ARTIFACT_TYPE] == [
        association["local_ref"]
    ]
    resolved = ArtifactResolver(store).resolve_private_binary(
        association["local_ref"],
        context,
        expected_sha256=association["sha256"],
    )
    assert resolved["content"].startswith(b"\x89PNG")


def test_normalizer_binds_one_annotated_ocr_response_to_private_sidecar(
    tmp_path: Path,
) -> None:
    _normalizer, pdf_input, store, graph, _context, _retention = (
        _bounded_pdf_normalization(tmp_path)
    )
    extractor = _AnnotatedOfflineFixtureExtractor()
    normalizer = Gate1Normalizer(_pdf_document_extractor=extractor)
    execution = _annotation_execution()

    result = normalizer.normalize(
        [pdf_input],
        bounded_graph=graph,
        pdf_table_continuation_annotation_execution=execution,
    )

    observed_pages, observed_prompt = extractor.annotation_calls[0]
    assert observed_pages == tuple(range(len(observed_pages)))
    assert len(observed_pages) > 1
    assert observed_prompt == execution.content
    assert not any(
        item["code"] == "parser_failed"
        for item in result.package["normalization_blockers"]
    )
    sidecar_refs = graph.physical_table_continuation_refs_by_doc
    assert len(sidecar_refs) == 1
    artifact_id = next(iter(sidecar_refs.values()))[0]
    stored = store.get_record_unchecked(artifact_id)
    payload = store.read_payload(stored)
    assert payload["annotation_receipt"]["prompt_snapshot"] == execution.prompt_snapshot
    # A body digest is deliberate provenance; the instruction body itself is
    # never persisted in the private sidecar receipt.
    assert "content" not in payload["annotation_receipt"]["prompt_snapshot"]
    assert result.package["private_normalized_source_units"]
    assert "private_physical_table_continuations" not in result.package


def test_normalizer_rejects_forged_annotation_execution_before_provider_call(
    tmp_path: Path,
) -> None:
    class ForgedExecution:
        content = "send this unapproved instruction"
        content_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        prompt_snapshot = {"prompt_hash": content_sha256}

    _normalizer, pdf_input, _store, graph, _context, _retention = (
        _bounded_pdf_normalization(tmp_path)
    )
    extractor = _AnnotatedOfflineFixtureExtractor()
    result = Gate1Normalizer(_pdf_document_extractor=extractor).normalize(
        [pdf_input],
        bounded_graph=graph,
        pdf_table_continuation_annotation_execution=ForgedExecution(),
    )

    assert extractor.annotation_calls == []
    assert graph.physical_table_continuation_refs_by_doc == {}
    assert any(
        item["code"] == "parser_failed"
        and item["reason_code"] == "PDF_DOCUMENT_AI_ANNOTATION_EXECUTION_INVALID"
        for item in result.package["normalization_blockers"]
    )


@pytest.mark.parametrize("tamper", ("content", "snapshot"))
def test_normalizer_rejects_tampered_sealed_annotation_before_provider_call(
    tmp_path: Path, tamper: str
) -> None:
    _normalizer, pdf_input, _store, graph, _context, _retention = (
        _bounded_pdf_normalization(tmp_path)
    )
    execution = _annotation_execution()
    if tamper == "content":
        object.__setattr__(execution, "content", "tampered instruction")
    else:
        snapshot = execution.prompt_snapshot
        snapshot["safe_metadata"] = {"body": "must not persist"}
        object.__setattr__(execution, "_prompt_snapshot", snapshot)

    extractor = _AnnotatedOfflineFixtureExtractor()
    result = Gate1Normalizer(_pdf_document_extractor=extractor).normalize(
        [pdf_input],
        bounded_graph=graph,
        pdf_table_continuation_annotation_execution=execution,
    )

    assert extractor.annotation_calls == []
    assert graph.physical_table_continuation_refs_by_doc == {}
    assert any(
        item["code"] == "parser_failed"
        and item["reason_code"] == "PDF_DOCUMENT_AI_ANNOTATION_EXECUTION_INVALID"
        for item in result.package["normalization_blockers"]
    )


def test_normalizer_omits_empty_annotation_sidecar_without_changing_full_source(
    tmp_path: Path,
) -> None:
    _normalizer, pdf_input, _store, graph, _context, _retention = (
        _bounded_pdf_normalization(tmp_path)
    )
    extractor = _NoLinkAnnotatedOfflineFixtureExtractor()
    result = Gate1Normalizer(_pdf_document_extractor=extractor).normalize(
        [pdf_input],
        bounded_graph=graph,
        pdf_table_continuation_annotation_execution=_annotation_execution(),
    )

    assert extractor.annotation_calls
    assert graph.physical_table_continuation_refs_by_doc == {}
    assert result.package["private_normalized_source_units"]
    assert not any(
        item["code"] == "parser_failed"
        for item in result.package["normalization_blockers"]
    )


def test_persisted_pdf_canonical_exact_ref_reaches_existing_right_bank(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The configured PDF route must not stop at private Full Source.

    This exercises the real Gate 1 persistence seam: the existing neutral
    Canonical owner consumes the source-bound PDF units, and the resulting
    artifact remains readable only in the exact authenticated scope.
    """

    # This is a synthetic persistence test.  The capacity policy itself has
    # dedicated tests; pin a healthy filesystem boundary here so the asserted
    # PDF-to-right-bank route is independent of the developer machine's disk.
    import broker_reports_gate1.canonical_store as canonical_store

    monkeypatch.setattr(
        canonical_store.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(
            total=20 * 1024 * 1024 * 1024,
            free=10 * 1024 * 1024 * 1024,
        ),
    )

    normalizer, pdf_input, store, graph, context, retention = (
        _bounded_pdf_normalization(tmp_path)
    )
    normalizer = Gate1Normalizer(_pdf_document_extractor=_OfflineFixtureExtractor())
    result = normalizer.normalize(
        [pdf_input],
        bounded_graph=graph,
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_read_enabled": True,
            "normalizer_version": "issue-391-pdf-canonical-v1",
        },
    )

    manifest = persist_gate1_result(
        store=store,
        result=result,
        context=context,
        retention_policy=retention,
        source_file_refs=[
            {
                "provider": "openwebui",
                "openwebui_file_id": "pdf-normalizer-upload",
                "content_type": "application/pdf",
                "source_deleted": False,
            }
        ],
    )
    canonical_refs = manifest.artifact_refs_by_type.get(
        "broker_reports_canonical_artifact_v1", []
    )
    failures = manifest.artifact_refs_by_type.get(
        "broker_reports_canonical_build_failure_v1", []
    )
    failure_payloads = [
        store.read_payload(store.get_record_unchecked(ref)) for ref in failures
    ]
    assert canonical_refs, [item["failure_code"] for item in failure_payloads]
    assert len(canonical_refs) == 1

    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    envelope = reader.read_envelope(canonical_refs[0], context)
    artifact = envelope.artifact
    assert artifact["source"]["source_format"] == "pdf"
    assert artifact["source"]["source_sha256"] == hashlib.sha256(
        PUBLIC_PDF.read_bytes()
    ).hexdigest()
    assert any(node["node_type"] == "TABLE" for node in artifact["nodes"])

    right_bank = OrdinaryTradeProductionRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().run(
        canonical_artifact_refs=canonical_refs,
        context=context,
    )

    assert right_bank["route_owner"] == ORDINARY_TRADE_PRODUCTION_ROUTE_ID
    assert right_bank["canonical_version_ids"] == [envelope.canonical_version_id]
    assert right_bank["canonical_root_sha256"] == [
        envelope.canonical_root_sha256
    ]
    assert len(right_bank["documents"]) == 1
    document = right_bank["documents"][0]
    assert document["document_id"] == envelope.document_id
    assert document["canonical_version_id"] == envelope.canonical_version_id
    assert document["projection_artifact_id"] == right_bank[
        "projection_artifact_ids"
    ][0]
    assert document["runtime_ready_observations"] == 0
    assert document["relevant_unmapped_observations"] == sum(
        node["node_type"] != "PAGE_BREAK" for node in artifact["nodes"]
    )
    assert document["matched_qualified_tables"] == 0
    assert document["activation_receipt"]["actor"] == (
        ORDINARY_TRADE_PRODUCTION_ROUTE_ID
    )
    assert document["activation_receipt"][
        "canonical_version_id"
    ] == envelope.canonical_version_id
    assert right_bank["product"]["terminal"] == (
        "ordinary_trade_declaration_canonical_relevant_unmapped"
    )
    assert right_bank["product"]["declaration_ready"] is False
    assert right_bank["provider_calls_total"] == 0
    assert right_bank["semantic_fallback_used"] is False
    assert "user_case_fact" not in json.dumps(artifact, sort_keys=True)


def test_persisted_provider_empty_pdf_page_is_evidence_only_not_a_fact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import broker_reports_gate1.canonical_store as canonical_store

    monkeypatch.setattr(
        canonical_store.shutil,
        "disk_usage",
        lambda _path: SimpleNamespace(
            total=20 * 1024 * 1024 * 1024,
            free=10 * 1024 * 1024 * 1024,
        ),
    )
    normalizer, pdf_input, store, graph, context, retention = (
        _bounded_pdf_normalization(tmp_path)
    )
    normalizer = Gate1Normalizer(
        _pdf_document_extractor=_ProviderEmptyPageFixtureExtractor()
    )
    result = normalizer.normalize(
        [pdf_input],
        bounded_graph=graph,
        input_context={
            "canonical_gate2_write_enabled": True,
            "canonical_gate2_read_enabled": True,
            "normalizer_version": "provider-empty-page-boundary-v1",
        },
    )

    manifest = persist_gate1_result(
        store=store,
        result=result,
        context=context,
        retention_policy=retention,
        source_file_refs=[
            {
                "provider": "openwebui",
                "openwebui_file_id": "pdf-normalizer-upload",
                "content_type": "application/pdf",
                "source_deleted": False,
            }
        ],
    )
    canonical_refs = manifest.artifact_refs_by_type.get(
        "broker_reports_canonical_artifact_v1", []
    )
    assert len(canonical_refs) == 1
    assert not manifest.artifact_refs_by_type.get(
        "broker_reports_canonical_build_failure_v1", []
    )
    artifact = CanonicalReaderFactory(store=store, read_enabled=True).create().read_envelope(
        canonical_refs[0], context
    ).artifact
    receipt = next(
        item
        for item in artifact["containers"]
        if item["container_type"] == "DOCUMENT"
    )["metadata"]["pdf_completeness"]
    assert receipt["source_atom_accounting_percent"] == 100.0
    assert receipt["unresolved_source_atoms_total"] == 0
    assert receipt["categories"]["EVIDENCE_ONLY"] == 1
    provenance = {
        item["provenance_id"]: item["source_locator"]
        for item in artifact["provenance"]
    }
    assert all(
        not (
            node["node_type"] in {"TEXT", "TABLE"}
            and any(
                provenance[ref].get("page") == 2
                for ref in node.get("source_refs") or []
            )
        )
        for node in artifact["nodes"]
    )


def test_normalizer_turns_atomic_pdf_publication_failure_into_blocker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    normalizer, pdf_input, store, graph, _context, _retention = (
        _bounded_pdf_normalization(tmp_path)
    )

    def fail_atomic(_records: object) -> None:
        raise ArtifactStoreError("artifact_atomic_write_failed", "synthetic")

    monkeypatch.setattr(store, "put_records_atomic", fail_atomic)
    result = normalizer.normalize([pdf_input], bounded_graph=graph)

    assert {
        item["reason_code"]
        for item in result.package["normalization_blockers"]
        if item["reason_code"] == "PDF_DOCUMENT_ARTIFACT_PUBLICATION_FAILED"
    } == {"PDF_DOCUMENT_ARTIFACT_PUBLICATION_FAILED"}
    assert result.package["private_normalized_source_payloads"] == []
    assert result.package["private_normalized_source_units"] == []
    assert PRIVATE_BINARY_ARTIFACT_TYPE not in graph.refs_by_type

    assert is_terminal_pdf_document_ai_request(
        result.package["document_inventory"]["documents"],
        result.package["normalization_blockers"],
    )


@pytest.mark.parametrize(
    "local_ref",
    (
        "../image.png",
        "images/../../image.png",
        r"images\..\image.png",
        r"C:\images\image.png",
        r"C:images\image.png",
        r"\\server\share\image.png",
        r"\images\image.png",
        "/images/image.png",
    ),
)
def test_image_ref_rejects_escape_and_absolute_path_mutations(local_ref: str) -> None:
    with pytest.raises(ValueError, match="pdf_document_image_ref_must_be_closed_local"):
        PdfDocumentImageRef(
            page_number=1,
            markdown_target="image.png",
            local_ref=local_ref,
            sha256=hashlib.sha256(b"image").hexdigest(),
            media_type="image/png",
            content_bytes=b"image",
        )


@pytest.mark.parametrize(
    ("summary", "error"),
    (
        ((("pages_count", "one"),), "pdf_document_safe_summary_count_invalid"),
        ((("pages_count", True),), "pdf_document_safe_summary_count_invalid"),
        ((("pages_count", -1),), "pdf_document_safe_summary_count_invalid"),
        ((("pages_count", 2),), "pdf_document_safe_summary_count_mismatch"),
        ((("markdown_bytes", 0),), "pdf_document_safe_summary_count_mismatch"),
    ),
)
def test_safe_summary_rejects_text_boolean_negative_and_mismatched_counts(
    summary: tuple[tuple[str, object], ...],
    error: str,
) -> None:
    markdown = b"fixture"
    with pytest.raises(ValueError, match=error):
        PdfDocumentExtraction(
            source_pdf_sha256="0" * 64,
            page_numbers=(1,),
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            image_refs=(),
            provider_id="offline_fixture_provider",
            requested_model_id="offline_fixture_model",
            model_id="offline_fixture_model",
            adapter_id="offline_fixture_adapter_v1",
            request_contract_version="offline_fixture_request_v1",
            request_parameters=(("include_image_base64", True),),
            request_parameters_sha256=hashlib.sha256(
                b'{"include_image_base64":true}'
            ).hexdigest(),
            page_markdown_sha256=(hashlib.sha256(markdown).hexdigest(),),
            qualification_status="offline_fixture",
            usage_page_count=1,
            safe_technical_summary=summary,  # type: ignore[arg-type]
        )
