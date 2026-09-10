from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import io
import json
import re
import traceback
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from broker_reports_gate1.artifact_models import (
    PRIVATE_BINARY_ARTIFACT_TYPE,
    PHYSICAL_TABLE_CONTINUATION_ARTIFACT_TYPE,
    ArtifactAccessContext,
    ArtifactStoreError,
    RetentionPolicy,
)
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.bounded_graph import (
    Gate1BoundedGraphConfig,
    Gate1BoundedGraphFactory,
)
from broker_reports_gate1.mistral_pdf_document_ai import (
    BoundedImageDecoder,
    MISTRAL_OCR_ADAPTER_ID,
    MISTRAL_OCR_MODEL,
    MISTRAL_OCR_PROVIDER_ID,
    MISTRAL_OCR_PROVIDER_REPORTED_MODEL_IDS,
    MISTRAL_OCR_REQUEST_CONTRACT_VERSION,
    MISTRAL_OCR_REQUEST_PARAMETERS,
    MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_CONTRACT_VERSION,
    MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_REQUEST_PARAMETERS,
    MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_SCHEMA,
    MistralPdfDocumentExtractor,
)
from broker_reports_gate1.full_source import FullSourceArtifactFactory
from broker_reports_gate1.canonical_artifact import (
    CanonicalNormalizerConfig,
    CanonicalNormalizerFactory,
)
from broker_reports_gate1.table_projection import NormalizedTableProjectionFactory
from broker_reports_gate1.pdf_document_ai import (
    PdfDocumentExtraction,
    PdfDocumentExtractionError,
    PdfDocumentExtractorFactory,
    PdfDocumentImageRef,
    PdfDocumentTableRef,
    PdfDocumentSelectedPageBinding,
    PdfDocumentTableContinuationRAndDResult,
    PdfSourceContext,
    RejectedPdfDocumentExtractor,
    UnconfiguredPdfDocumentExtractor,
    pdf_document_selected_page_bindings_sha256,
    pdf_document_table_refs_sha256,
)
from broker_reports_gate1.physical_table_continuation import (
    PHYSICAL_TABLE_CONTINUATION_SCHEMA_VERSION,
    build_physical_table_continuation_sidecar,
)
from broker_reports_gate1.pdf_table_continuation_annotation_prompt import (
    INPUT_SCHEMA_VERSION as TABLE_ANNOTATION_INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_ID as TABLE_ANNOTATION_OUTPUT_SCHEMA_ID,
    OUTPUT_SCHEMA_VERSION as TABLE_ANNOTATION_OUTPUT_SCHEMA_VERSION,
    PROMPT_COMMAND as TABLE_ANNOTATION_PROMPT_COMMAND,
    PROMPT_CONTRACT_ID as TABLE_ANNOTATION_PROMPT_CONTRACT_ID,
    PROMPT_REQUIRED_TAG as TABLE_ANNOTATION_PROMPT_REQUIRED_TAG,
    PROMPT_TEMPLATE_ID as TABLE_ANNOTATION_PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND as TABLE_ANNOTATION_PROMPT_TEMPLATE_KIND,
    PdfTableContinuationAnnotationManagedPrompt,
    execution_from_managed_prompt,
    pdf_table_continuation_annotation_prompt_hash,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MAPPING_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    OrdinaryTradeSemanticCompilerFactory,
)
from openwebui_actions.broker_reports_gate1_pipe import Pipe


PDF_BYTES = b"%PDF-1.7\nclosed-http-boundary-fixture\n%%EOF"
PDF_BASE64 = base64.b64encode(PDF_BYTES).decode("ascii")
API_KEY = "mistral-test-secret-must-not-leak"
RAW_PROVIDER_SECRET = "raw-provider-body-must-not-leak"
PNG_BYTES = b"\x89PNG\r\n\x1a\nfixture-image"
PNG_BASE64 = base64.b64encode(PNG_BYTES).decode("ascii")
REPO_ROOT = Path(__file__).resolve().parents[3]
PUBLIC_PDF = next(
    (REPO_ROOT / "docs" / "reports" / "2026-09-02" / "artifacts").glob(
        "*/fidelity/source.pdf"
    )
)
FIDELITY_FIXTURE_ROOT = PUBLIC_PDF.parent
FIDELITY_IMAGE_ASSOCIATIONS = (
    (1, "img-0.jpeg", "1b669fc6f1d25f31511b3de2b69a2e16359340f0509115be59f07499b6b08f9b"),
    (3, "img-1.jpeg", "471d69e259ed61018654fb9f4e46a55a70bff2019a10d901b5be913ac778bf83"),
    (4, "img-2.jpeg", "20038d0abdbd9377a33961f8d3cca668ec9548d49c3986bece2446d2891fedf9"),
    (8, "img-3.jpeg", "d3f4c9f2871cb6d82e2a9ff96044a4d2a3a16760b073d4ab0d3bafbeb6e95878"),
    (19, "img-4.jpeg", "7f3c2dc4bfb5573915d32ab011c6325df9bcc1aac7331de66a3b0ed249ae5723"),
    (20, "img-5.jpeg", "a8470376c926d1e6141718ad9a429cc75319ecb20a4f6588dc211af1a05fc44b"),
    (24, "img-6.jpeg", "a8470376c926d1e6141718ad9a429cc75319ecb20a4f6588dc211af1a05fc44b"),
    (25, "img-7.jpeg", "a8470376c926d1e6141718ad9a429cc75319ecb20a4f6588dc211af1a05fc44b"),
)


class _FakeResponse:
    def __init__(self, payload: object = None, *, status: int = 200, raw: bytes | None = None) -> None:
        self.status = status
        self._raw = (
            raw
            if raw is not None
            else json.dumps(payload, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        )
        self.read_limits: list[int] = []

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        self.read_limits.append(limit)
        return self._raw


class _OversizedResponse(_FakeResponse):
    def __init__(self) -> None:
        super().__init__(raw=b"")

    def read(self, limit: int) -> bytes:
        self.read_limits.append(limit)
        return b"x" * limit


class _FakeOpener:
    def __init__(self, outcome: _FakeResponse | BaseException) -> None:
        self._outcome = outcome
        self.calls: list[tuple[Request, float]] = []

    def open(self, request: Request, *, timeout: float) -> _FakeResponse:
        self.calls.append((request, timeout))
        if len(self.calls) != 1:
            raise AssertionError("Mistral adapter retried the HTTP request")
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


def _source_context(page_count: int) -> PdfSourceContext:
    return PdfSourceContext(
        document_ref="closed-http-boundary-pdf",
        expected_pdf_sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
        preflight_page_count=page_count,
    )


def _response(
    pages: list[Mapping[str, object]],
    *,
    pages_processed: int | None = None,
    model: object = MISTRAL_OCR_MODEL,
) -> dict[str, object]:
    return {
        "pages": pages,
        "usage_info": {
            "pages_processed": len(pages) if pages_processed is None else pages_processed
        },
        "model": model,
    }


def _extractor(
    tmp_path: Path, opener: _FakeOpener
) -> MistralPdfDocumentExtractor:
    return MistralPdfDocumentExtractor(
        api_base_url="https://api.mistral.ai/v1",
        api_key=API_KEY,
        image_decoder=BoundedImageDecoder(),
        qualification_status="offline_fixture",
        timeout_seconds=17.0,
        opener=opener,
    )


def _assert_one_post(
    opener: _FakeOpener,
    *,
    expected_pdf_bytes: bytes = PDF_BYTES,
    expected_annotation_prompt: str | None = None,
    expected_source_page_numbers: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    assert len(opener.calls) == 1
    request, timeout = opener.calls[0]
    assert request.get_method() == "POST"
    assert request.full_url == "https://api.mistral.ai/v1/ocr"
    assert timeout == 17.0
    assert request.get_header("Authorization") == f"Bearer {API_KEY}"
    assert request.get_header("Content-type") == "application/json"
    assert request.data is not None
    payload = json.loads(request.data.decode("utf-8"))
    expected_payload: dict[str, object] = {
        "model": MISTRAL_OCR_MODEL,
        "document": {
            "type": "document_url",
            "document_url": (
                "data:application/pdf;base64,"
                + base64.b64encode(expected_pdf_bytes).decode("ascii")
            ),
        },
        "include_image_base64": True,
        "table_format": "html",
    }
    if expected_annotation_prompt is not None:
        assert expected_source_page_numbers is not None
        expected_payload["document_annotation_format"] = (
            MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_SCHEMA
        )
        expected_payload["document_annotation_prompt"] = expected_annotation_prompt
        expected_payload["pages"] = list(expected_source_page_numbers)
    assert payload == expected_payload
    return payload


def _assert_typed_failure_without_leak(
    caught: pytest.ExceptionInfo[PdfDocumentExtractionError],
    *,
    expected_code: str,
) -> None:
    error = caught.value
    assert error.code == expected_code
    assert str(error) == expected_code
    rendered = "".join(traceback.format_exception(error))
    for forbidden in (API_KEY, PDF_BASE64, RAW_PROVIDER_SECRET, PDF_BYTES.decode("ascii")):
        assert forbidden not in rendered


def test_success_maps_ordered_multi_page_empty_page_and_image_once(tmp_path: Path) -> None:
    first_page_markdown = "# First page\n\n![chart](img-0.png)"
    response = _FakeResponse(
        _response(
            [
                {
                    "index": 0,
                    "markdown": first_page_markdown,
                    "images": [
                        {
                            "id": "img-0.png",
                            "image_base64": f"data:image/png;base64,{PNG_BASE64}",
                        }
                    ],
                },
                {"index": 1, "markdown": "", "images": []},
            ]
        )
    )
    opener = _FakeOpener(response)

    result = _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(2))

    _assert_one_post(opener)
    assert MISTRAL_OCR_MODEL == "mistral-ocr-4-1"
    assert result.page_numbers == (1, 2)
    assert result.markdown_bytes == first_page_markdown.encode("utf-8") + b"\n\n"
    assert result.usage_page_count == 2
    assert result.provider_id == MISTRAL_OCR_PROVIDER_ID
    assert result.requested_model_id == "mistral-ocr-4-1"
    assert result.model_id == MISTRAL_OCR_MODEL
    assert result.adapter_id == MISTRAL_OCR_ADAPTER_ID
    assert result.request_contract_version == "mistral_ocr_request_v2"
    assert result.request_parameters == MISTRAL_OCR_REQUEST_PARAMETERS
    assert (
        result.request_parameters_sha256
        == hashlib.sha256(
            json.dumps(
                dict(MISTRAL_OCR_REQUEST_PARAMETERS),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
    )
    assert result.page_markdown_sha256 == (
        hashlib.sha256(first_page_markdown.encode("utf-8")).hexdigest(),
        hashlib.sha256(b"").hexdigest(),
    )
    assert result.page_content_dispositions == (
        "markdown_materialized",
        "provider_empty_page",
    )
    assert result.qualification_status == "offline_fixture"
    assert result.source_pdf_sha256 == hashlib.sha256(PDF_BYTES).hexdigest()
    assert result.markdown_sha256 == hashlib.sha256(result.markdown_bytes).hexdigest()
    assert len(result.image_refs) == 1
    image_ref = result.image_refs[0]
    assert image_ref.page_number == 1
    assert image_ref.markdown_target == "img-0.png"
    assert image_ref.sha256 == hashlib.sha256(PNG_BYTES).hexdigest()
    assert image_ref.content_bytes == PNG_BYTES
    assert image_ref.media_type == "image/png"
    result_text = repr(result)
    assert first_page_markdown not in result_text
    assert API_KEY not in result_text
    assert PDF_BASE64 not in result_text
    assert PDF_BYTES.decode("ascii") not in result_text
    assert RAW_PROVIDER_SECRET not in result_text


def test_native_table_continuation_annotation_is_bound_to_one_selected_source_slice(
    tmp_path: Path,
) -> None:
    raw_annotation = json.dumps(
        {
            "continuation_links": [
                {
                    "parent": {
                        "source_page_number": 2,
                        "markdown_table_target": "page-2-table.html",
                    },
                    "child": {
                        "source_page_number": 3,
                        "markdown_table_target": "page-3-table.html",
                    },
                }
            ]
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    response = _response(
        [
            {
                "index": 2,
                "markdown": "[first](page-2-table.html)",
                "images": [],
                "tables": [
                    {
                        "id": "page-2-table.html",
                        "content": "<table><tr><td>first</td></tr></table>",
                    }
                ],
            },
            {
                "index": 3,
                "markdown": "[second](page-3-table.html)",
                "images": [],
                "tables": [
                    {
                        "id": "page-3-table.html",
                        "content": "<table><tr><td>second</td></tr></table>",
                    }
                ],
            },
        ]
    )
    response["document_annotation"] = raw_annotation
    opener = _FakeOpener(_FakeResponse(response))
    prompt = "Link only physical table continuations in this selected source slice."

    result = _extractor(tmp_path, opener).extract_with_table_continuation_assessment(
        PDF_BYTES,
        _source_context(8),
        source_page_numbers=(2, 3),
        document_annotation_prompt=prompt,
    )

    _assert_one_post(
        opener,
        expected_annotation_prompt=prompt,
        expected_source_page_numbers=(2, 3),
    )
    assert (
        MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_CONTRACT_VERSION
        == "mistral_ocr_table_continuation_annotation_v4"
    )
    serialized_schema = json.dumps(
        MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_SCHEMA,
        ensure_ascii=True,
        sort_keys=True,
    )
    assert '"source_page_number"' in serialized_schema
    assert '"markdown_table_target"' in serialized_schema
    assert '"table_ordinal"' not in serialized_schema
    assert result.extraction.source_pdf_sha256 == hashlib.sha256(PDF_BYTES).hexdigest()
    assert result.extraction.page_numbers == (1, 2)
    assert result.assessment.source_page_numbers == (2, 3)
    assert [
        (binding.local_page_number, binding.source_page_number)
        for binding in result.assessment.selected_page_bindings
    ] == [(1, 2), (2, 3)]
    assert result.assessment.selected_page_bindings_sha256 == (
        pdf_document_selected_page_bindings_sha256(
            result.assessment.selected_page_bindings
        )
    )
    assert result.assessment.table_refs_sha256 == pdf_document_table_refs_sha256(
        result.extraction.table_refs
    )
    assert result.assessment.raw_annotation_sha256 == hashlib.sha256(
        raw_annotation.encode("utf-8")
    ).hexdigest()
    assert result.assessment.request_parameters_sha256 == hashlib.sha256(
        json.dumps(
            {
                **dict(MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_REQUEST_PARAMETERS),
                "source_page_numbers": [2, 3],
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert result.assessment.annotation_prompt_sha256 == hashlib.sha256(
        prompt.encode("utf-8")
    ).hexdigest()
    assert result.assessment.annotation_schema_sha256 == hashlib.sha256(
        json.dumps(
            MISTRAL_OCR_TABLE_CONTINUATION_ANNOTATION_SCHEMA,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    assert len(result.assessment.links) == 1
    link = result.assessment.links[0]
    assert link.parent_table_ref == result.extraction.table_refs[0].local_ref
    assert link.child_table_ref == result.extraction.table_refs[1].local_ref
    assert all(
        not hasattr(result.assessment, field)
        for field in ("raw_annotation", "document_annotation_prompt", "schema")
    )
    assert prompt not in repr(result)
    assert raw_annotation not in repr(result)
    assert list(tmp_path.iterdir()) == []


def test_native_table_continuation_annotation_rejects_native_table_id_mutation(
    tmp_path: Path,
) -> None:
    response = _response(
        [
            {
                "index": 0,
                "markdown": "[first](first.html)",
                "images": [],
                "tables": [
                    {
                        "id": "first.html",
                        "content": "<table><tr><td>first</td></tr></table>",
                    }
                ],
            },
            {
                "index": 1,
                "markdown": "[second](second.html)",
                "images": [],
                "tables": [
                    {
                        "id": "second.html",
                        "content": "<table><tr><td>second</td></tr></table>",
                    }
                ],
            },
        ]
    )
    response["document_annotation"] = (
        '{"continuation_links":[{"parent":{"source_page_number":0,"markdown_table_target":"first.html"},'
        '"child":{"source_page_number":1,"markdown_table_target":"second.html"}}]}'
    )
    result = _extractor(tmp_path, _FakeOpener(_FakeResponse(response))).extract_with_table_continuation_assessment(
        PDF_BYTES,
        _source_context(2),
        source_page_numbers=(0, 1),
        document_annotation_prompt="Link physical table continuations.",
    )
    mutated_table = replace(
        result.extraction.table_refs[0], markdown_target="renamed-first.html"
    )
    mutated_extraction = replace(
        result.extraction,
        table_refs=(mutated_table, *result.extraction.table_refs[1:]),
    )

    assert pdf_document_table_refs_sha256(mutated_extraction.table_refs) != (
        result.assessment.table_refs_sha256
    )
    with pytest.raises(ValueError) as caught:
        PdfDocumentTableContinuationRAndDResult(
            extraction=mutated_extraction,
            assessment=result.assessment,
            source_context=result.source_context,
        )

    assert str(caught.value) == "pdf_document_annotation_table_refs_mismatch"


def test_native_table_continuation_annotation_rejects_rebound_original_pages(
    tmp_path: Path,
) -> None:
    response = _response(
        [
            {
                "index": 4,
                "markdown": "[first](first.html)",
                "images": [],
                "tables": [
                    {
                        "id": "first.html",
                        "content": "<table><tr><td>first</td></tr></table>",
                    }
                ],
            },
            {
                "index": 5,
                "markdown": "[second](second.html)",
                "images": [],
                "tables": [
                    {
                        "id": "second.html",
                        "content": "<table><tr><td>second</td></tr></table>",
                    }
                ],
            },
        ]
    )
    response["document_annotation"] = (
        '{"continuation_links":[{"parent":{"source_page_number":4,"markdown_table_target":"first.html"},'
        '"child":{"source_page_number":5,"markdown_table_target":"second.html"}}]}'
    )
    result = _extractor(tmp_path, _FakeOpener(_FakeResponse(response))).extract_with_table_continuation_assessment(
        PDF_BYTES,
        _source_context(8),
        source_page_numbers=(4, 5),
        document_annotation_prompt="Link physical table continuations.",
    )
    rebound_bindings = (
        PdfDocumentSelectedPageBinding(local_page_number=1, source_page_number=5),
        PdfDocumentSelectedPageBinding(local_page_number=2, source_page_number=4),
    )
    rebound_assessment = replace(
        result.assessment,
        selected_page_bindings=rebound_bindings,
        selected_page_bindings_sha256=pdf_document_selected_page_bindings_sha256(
            rebound_bindings
        ),
    )

    with pytest.raises(ValueError) as caught:
        PdfDocumentTableContinuationRAndDResult(
            extraction=result.extraction,
            assessment=rebound_assessment,
            source_context=result.source_context,
        )

    assert str(caught.value) == "pdf_document_annotation_source_page_binding_mismatch"


def test_native_table_continuation_annotation_accepts_full_document_page_scope(
    tmp_path: Path,
) -> None:
    from broker_reports_gate1.mistral_pdf_document_ai import (
        _validated_annotation_source_page_numbers,
    )

    assert _validated_annotation_source_page_numbers(
        tuple(range(9)), source_context=_source_context(9)
    ) == tuple(range(9))


@pytest.mark.parametrize(
    ("annotation", "source_page_numbers", "expected_code"),
    (
        (
            {
                "continuation_links": [
                    {
                        "parent": {
                            "source_page_number": 0,
                            "markdown_table_target": "first.html",
                        },
                        "child": {
                            "source_page_number": 1,
                            "markdown_table_target": "second.html",
                        },
                    }
                ]
            },
            (2, 3),
            "PDF_DOCUMENT_AI_ANNOTATION_UNKNOWN_TABLE",
        ),
        (
            {
                "continuation_links": [
                    {
                        "parent": {
                            "source_page_number": 0,
                            "markdown_table_target": "missing.html",
                        },
                        "child": {
                            "source_page_number": 1,
                            "markdown_table_target": "second.html",
                        },
                    }
                ]
            },
            (0, 1),
            "PDF_DOCUMENT_AI_ANNOTATION_UNKNOWN_TABLE",
        ),
        (
            {
                "continuation_links": [
                    {
                        "parent": {
                            "source_page_number": 1,
                            "markdown_table_target": "first.html",
                        },
                        "child": {
                            "source_page_number": 1,
                            "markdown_table_target": "second.html",
                        },
                    }
                ]
            },
            (0, 1),
            "PDF_DOCUMENT_AI_ANNOTATION_UNKNOWN_TABLE",
        ),
        (
            {
                "continuation_links": [
                    {
                        "parent": {
                            "source_page_number": 0,
                            "markdown_table_target": "first.html",
                        },
                        "child": {
                            "source_page_number": 2,
                            "markdown_table_target": "second.html",
                        },
                    }
                ]
            },
            (0, 2),
            "PDF_DOCUMENT_AI_ANNOTATION_NONADJACENT_PAGE_LINK",
        ),
        (
            {
                "continuation_links": [
                    {
                        "parent": {
                            "source_page_number": 0,
                            "markdown_table_target": "first.html",
                        },
                        "child": {
                            "source_page_number": 1,
                            "markdown_table_target": "second.html",
                        },
                    },
                    {
                        "parent": {
                            "source_page_number": 0,
                            "markdown_table_target": "other-first.html",
                        },
                        "child": {
                            "source_page_number": 1,
                            "markdown_table_target": "second.html",
                        },
                    },
                ]
            },
            (0, 1),
            "PDF_DOCUMENT_AI_ANNOTATION_MULTIPLE_PARENT",
        ),
    ),
    ids=(
        "selected_slice_positions_are_not_source_page_numbers",
        "unknown_target",
        "target_from_another_page",
        "nonadjacent_source_pages",
        "multiple_parent",
    ),
)
def test_native_table_continuation_annotation_rejects_unbound_or_ambiguous_links(
    tmp_path: Path,
    annotation: dict[str, object],
    source_page_numbers: tuple[int, ...],
    expected_code: str,
) -> None:
    response = _response(
        [
            {
                "index": 0,
                "markdown": "[first](first.html)\n[other](other-first.html)",
                "images": [],
                "tables": [
                    {
                        "id": "first.html",
                        "content": "<table><tr><td>first</td></tr></table>",
                    },
                    {
                        "id": "other-first.html",
                        "content": "<table><tr><td>other</td></tr></table>",
                    },
                ],
            },
            {
                "index": 1,
                "markdown": "[second](second.html)",
                "images": [],
                "tables": [
                    {
                        "id": "second.html",
                        "content": "<table><tr><td>second</td></tr></table>",
                    }
                ],
            },
        ]
    )
    response["document_annotation"] = json.dumps(annotation, separators=(",", ":"))
    opener = _FakeOpener(_FakeResponse(response))

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract_with_table_continuation_assessment(
            PDF_BYTES,
            _source_context(4),
            source_page_numbers=source_page_numbers,
            document_annotation_prompt="Link physical table continuations.",
        )

    _assert_one_post(
        opener,
        expected_annotation_prompt="Link physical table continuations.",
        expected_source_page_numbers=source_page_numbers,
    )
    _assert_typed_failure_without_leak(caught, expected_code=expected_code)


def test_native_table_continuation_annotation_rejects_v1_native_table_id_shape(
    tmp_path: Path,
) -> None:
    response = _response(
        [
            {
                "index": 0,
                "markdown": "[first](first.html)",
                "images": [],
                "tables": [
                    {
                        "id": "first.html",
                        "content": "<table><tr><td>first</td></tr></table>",
                    }
                ],
            },
            {
                "index": 1,
                "markdown": "[second](second.html)",
                "images": [],
                "tables": [
                    {
                        "id": "second.html",
                        "content": "<table><tr><td>second</td></tr></table>",
                    }
                ],
            },
        ]
    )
    response["document_annotation"] = (
        '{"continuation_links":[{"parent":{"page_index":0,"table_id":"first.html"},'
        '"child":{"page_index":1,"table_id":"second.html"}}]}'
    )
    opener = _FakeOpener(_FakeResponse(response))

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract_with_table_continuation_assessment(
            PDF_BYTES,
            _source_context(2),
            source_page_numbers=(0, 1),
            document_annotation_prompt="Link physical table continuations.",
        )

    _assert_one_post(
        opener,
        expected_annotation_prompt="Link physical table continuations.",
        expected_source_page_numbers=(0, 1),
    )
    _assert_typed_failure_without_leak(
        caught,
        expected_code="PDF_DOCUMENT_AI_ANNOTATION_INVALID",
    )


def test_native_table_continuation_annotation_rejects_legacy_v2_ordinal_shape(
    tmp_path: Path,
) -> None:
    response = _response(
        [
            {
                "index": 0,
                "markdown": "[first](first.html)",
                "images": [],
                "tables": [{"id": "first.html", "content": "<table><tr><td>first</td></tr></table>"}],
            },
            {
                "index": 1,
                "markdown": "[second](second.html)",
                "images": [],
                "tables": [{"id": "second.html", "content": "<table><tr><td>second</td></tr></table>"}],
            },
        ]
    )
    response["document_annotation"] = (
        '{"continuation_links":[{"parent":{"selected_page_position":0,"table_ordinal":1},'
        '"child":{"selected_page_position":1,"table_ordinal":1}}]}'
    )
    opener = _FakeOpener(_FakeResponse(response))

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract_with_table_continuation_assessment(
            PDF_BYTES,
            _source_context(2),
            source_page_numbers=(0, 1),
            document_annotation_prompt="Link physical table continuations.",
        )

    _assert_one_post(
        opener,
        expected_annotation_prompt="Link physical table continuations.",
        expected_source_page_numbers=(0, 1),
    )
    _assert_typed_failure_without_leak(
        caught,
        expected_code="PDF_DOCUMENT_AI_ANNOTATION_INVALID",
    )


def test_native_table_continuation_annotation_rejects_legacy_v3_selected_position_shape(
    tmp_path: Path,
) -> None:
    response = _response(
        [
            {
                "index": 2,
                "markdown": "[first](first.html)",
                "images": [],
                "tables": [
                    {
                        "id": "first.html",
                        "content": "<table><tr><td>first</td></tr></table>",
                    }
                ],
            },
            {
                "index": 3,
                "markdown": "[second](second.html)",
                "images": [],
                "tables": [
                    {
                        "id": "second.html",
                        "content": "<table><tr><td>second</td></tr></table>",
                    }
                ],
            },
        ]
    )
    response["document_annotation"] = (
        '{"continuation_links":[{"parent":{"selected_page_position":0,'
        '"markdown_table_target":"first.html"},"child":'
        '{"selected_page_position":1,"markdown_table_target":"second.html"}}]}'
    )
    opener = _FakeOpener(_FakeResponse(response))

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract_with_table_continuation_assessment(
            PDF_BYTES,
            _source_context(4),
            source_page_numbers=(2, 3),
            document_annotation_prompt="Link physical table continuations.",
        )

    _assert_one_post(
        opener,
        expected_annotation_prompt="Link physical table continuations.",
        expected_source_page_numbers=(2, 3),
    )
    _assert_typed_failure_without_leak(
        caught,
        expected_code="PDF_DOCUMENT_AI_ANNOTATION_INVALID",
    )


def test_native_table_continuation_annotation_scopes_identical_targets_by_page(
    tmp_path: Path,
) -> None:
    response = _response(
        [
            {
                "index": 0,
                "markdown": "[first](tbl-0.html)",
                "images": [],
                "tables": [{"id": "tbl-0.html", "content": "<table><tr><td>first</td></tr></table>"}],
            },
            {
                "index": 1,
                "markdown": "[second](tbl-0.html)",
                "images": [],
                "tables": [{"id": "tbl-0.html", "content": "<table><tr><td>second</td></tr></table>"}],
            },
        ]
    )
    response["document_annotation"] = (
        '{"continuation_links":[{"parent":{"source_page_number":0,"markdown_table_target":"tbl-0.html"},'
        '"child":{"source_page_number":1,"markdown_table_target":"tbl-0.html"}}]}'
    )

    result = _extractor(
        tmp_path, _FakeOpener(_FakeResponse(response))
    ).extract_with_table_continuation_assessment(
        PDF_BYTES,
        _source_context(2),
        source_page_numbers=(0, 1),
        document_annotation_prompt="Link physical table continuations.",
    )

    assert [(link.parent_table_ref, link.child_table_ref) for link in result.assessment.links] == [
        (result.extraction.table_refs[0].local_ref, result.extraction.table_refs[1].local_ref)
    ]


def test_native_table_continuation_annotation_rejects_ambiguous_provider_page_binding(
    tmp_path: Path,
) -> None:
    response = _response(
        [
            {"index": 2, "markdown": "", "images": []},
            {"index": 3, "markdown": "", "images": []},
        ]
    )
    response["document_annotation"] = '{"continuation_links":[]}'
    opener = _FakeOpener(_FakeResponse(response))

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract_with_table_continuation_assessment(
            PDF_BYTES,
            _source_context(8),
            source_page_numbers=(4, 5),
            document_annotation_prompt="Link physical table continuations.",
        )

    _assert_one_post(
        opener,
        expected_annotation_prompt="Link physical table continuations.",
        expected_source_page_numbers=(4, 5),
    )
    _assert_typed_failure_without_leak(
        caught,
        expected_code="PDF_DOCUMENT_AI_ANNOTATION_RESPONSE_PAGE_BINDING_INVALID",
    )


def test_native_html_table_is_preserved_as_physical_header_and_headerless_units(
    tmp_path: Path,
) -> None:
    first_html = (
        "<table><thead><tr><th>Date</th><th>Amount</th></tr></thead>"
        "<tbody><tr><td>2026-01-01</td><td>10</td></tr></tbody></table>"
    )
    continuation_html = "<table><tbody><tr><td>2026-01-02</td><td>11</td></tr></tbody></table>"
    response = _FakeResponse(
        _response(
            [
                {
                    "index": 0,
                    "markdown": "Opening\n[t0](tbl-0.html)\nClosing",
                    "images": [],
                    "tables": [{"id": "tbl-0.html", "content": first_html}],
                },
                {
                    "index": 1,
                    "markdown": "[t1](tbl-1.html)",
                    "images": [],
                    "tables": [{"id": "tbl-1.html", "content": continuation_html}],
                },
            ]
        )
    )
    extraction = _extractor(tmp_path, _FakeOpener(response)).extract(
        PDF_BYTES, _source_context(2)
    )

    assert len(extraction.table_refs) == 2
    assert all(item.markdown_target.startswith("tbl-") for item in extraction.table_refs)
    assert all(item.local_ref.startswith("pdftable_") for item in extraction.table_refs)
    built = FullSourceArtifactFactory().create().build_document_extraction(
        normalization_run_id="native-table-run",
        document_id="native-table-document",
        profile_id="native-table-profile",
        extraction=extraction,
    )
    table_units = [
        unit
        for unit in built.units
        if (unit.get("source_location") or {}).get("kind")
        == "document_ai_native_table_html"
    ]
    assert len(table_units) == 2
    assert [
        (unit["source_location"]["page"], unit["source_location"]["structural_header_row_ordinals"])
        for unit in table_units
    ] == [(1, [1]), (2, [])]
    assert [
        (unit["document_ai_native_table_ref"], unit["document_ai_native_table_sha256"])
        for unit in table_units
    ] == [
        (item.local_ref, item.sha256)
        for item in extraction.table_refs
    ]
    assert {unit["source_checksum_sha256"] for unit in table_units} == {
        extraction.source_pdf_sha256
    }
    assert all("tbl-" not in str(unit.get("text") or "") for unit in built.units)

    projected = NormalizedTableProjectionFactory().create().build_for_document(
        source_format="pdf", payloads=built.payloads, source_units=built.units
    ).projections
    assert len(projected) == 2
    assert projected[0]["header_model"]["header_row_refs"]
    assert not projected[1]["header_model"]["header_row_refs"]
    assert [row["row_role"] for row in projected[1]["rows"]] == ["data_row"]
    assert all(item["page_refs"] in (["page_1"], ["page_2"]) for item in projected)
    canonical = CanonicalNormalizerFactory(
        CanonicalNormalizerConfig(normalizer_version="native-table-test-v1")
    ).create().build(
        tenant_id="native-table-tenant",
        artifact_version=1,
        document={"container_format": "pdf", "sha256": hashlib.sha256(PDF_BYTES).hexdigest()},
        source_artifact_ref="native-table-source",
        source_payloads=built.payloads,
        source_units=built.units,
        table_projections=projected,
    )
    canonical_tables = [node for node in canonical["nodes"] if node["node_type"] == "TABLE"]
    assert len(canonical_tables) == 2
    assert canonical_tables[0]["content"]["header"] == ["Date", "Amount"]
    assert canonical_tables[1]["content"]["header"] == []
    assert [
        table["content"]["metadata"].get("physical_header_state")
        for table in canonical_tables
    ] == ["PRESENT", "ABSENT"]
    mapping_package = OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
        canonical=canonical,
        confirmed_understandings=[],
    )
    mapping_tables = mapping_package["case"]["tables"]
    assert [table["physical_header_row"] for table in mapping_tables] == [1, None]
    assert mapping_tables[1]["header_row_choices"] == []
    assert mapping_tables[1]["rows"] == [
        {
            "row": 1,
            "cells": [
                {"column": 1, "literal": "2026-01-02"},
                {"column": 2, "literal": "11"},
            ],
        }
    ]
    headerless_table = canonical_tables[1]
    binding = {
        "document_id": "native-table-document",
        "canonical_version_id": "native-table-version",
        "canonical_root_sha256": canonical["canonical_root_hash"],
        "source_artifact_ref": canonical["source"]["source_artifact_ref"],
        "source_sha256": canonical["source"]["source_sha256"],
    }
    mapping_result = OrdinaryTradeSemanticMappingFactory.create().validate_mapping_response(
        response={
            "schema_version": MAPPING_RESPONSE_SCHEMA_VERSION,
            "status": "COMPLETE",
            "table_decisions": [
                {
                    "table_ref": "table_1",
                    "header_row": None,
                    "disposition": "HEADER_ABSENT",
                    "columns": [],
                    "amount_currency_bindings": [],
                    "side_values": [],
                    "row_dispositions": [],
                }
            ],
            "clarification": None,
            "message": "The physical continuation has no header.",
        },
        canonical=canonical,
        canonical_binding=binding,
        model_id="models/gemini-3.5-flash",
        provider_profile_id="google_gemini",
        execution_metadata={"fixture": "native-mistral-headerless"},
        confirmed_understandings=[],
        user_scope_sha256=hashlib.sha256(b"native-table-user").hexdigest(),
        target_table_node_ids=[headerless_table["node_id"]],
    )
    projection = OrdinaryTradeSemanticCompilerFactory.create().compile(
        canonical=canonical,
        canonical_binding=binding,
        mappings=mapping_result["qualified_mappings"],
        table_resolutions=mapping_result["table_resolutions"],
    )
    continuation_observations = [
        item
        for item in projection["source_observations"]
        if item["table_node_id"] == headerless_table["node_id"]
    ]
    assert mapping_result["qualified_mappings"] == []
    assert projection["runtime_records"] == []
    assert [(item["row"], item["reason_code"]) for item in continuation_observations] == [
        (1, "ORDINARY_TRADE_SOURCE_HEADER_ABSENT")
    ]
    assert [
        field["literal"] for field in continuation_observations[0]["fields"]
    ] == ["2026-01-02", "11"]
    assert all(
        "document_ai_continuation" not in table["content"].get("metadata", {})
        for table in canonical_tables
    )


def test_native_table_missing_exact_markdown_anchor_fails_closed(tmp_path: Path) -> None:
    opener = _FakeOpener(
        _FakeResponse(
            _response(
                [
                    {
                        "index": 0,
                        "markdown": "no matching native table anchor",
                        "images": [],
                        "tables": [{"id": "tbl-0.html", "content": "<table><tr><td>x</td></tr></table>"}],
                    }
                ]
            )
        )
    )
    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))
    _assert_one_post(opener)
    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_TABLE_ASSOCIATION_INVALID"
    )


def test_native_table_cannot_reuse_an_image_markdown_target(tmp_path: Path) -> None:
    opener = _FakeOpener(
        _FakeResponse(
            _response(
                [
                    {
                        "index": 0,
                        "markdown": "![image](shared.html)",
                        "images": [{"id": "shared.html", "image_base64": PNG_BASE64}],
                        "tables": [{"id": "shared.html", "content": "<table><tr><td>x</td></tr></table>"}],
                    }
                ]
            )
        )
    )
    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))
    _assert_one_post(opener)
    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_TABLE_INVALID"
    )


def test_full_source_carries_only_declared_provider_empty_page_as_evidence() -> None:
    pages = (b"# Materialized\n", b"")
    markdown = b"\n\n".join(pages)
    extraction = PdfDocumentExtraction(
        source_pdf_sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
        page_numbers=(1, 2),
        markdown_bytes=markdown,
        markdown_sha256=hashlib.sha256(markdown).hexdigest(),
        image_refs=(),
        provider_id="offline_fixture_provider",
        requested_model_id=MISTRAL_OCR_MODEL,
        model_id="offline_fixture_model",
        adapter_id="offline_fixture_adapter_v1",
        request_contract_version=MISTRAL_OCR_REQUEST_CONTRACT_VERSION,
        request_parameters=MISTRAL_OCR_REQUEST_PARAMETERS,
        request_parameters_sha256=hashlib.sha256(
            json.dumps(
                dict(MISTRAL_OCR_REQUEST_PARAMETERS),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest(),
        page_markdown_sha256=tuple(hashlib.sha256(page).hexdigest() for page in pages),
        qualification_status="offline_fixture",
        usage_page_count=2,
        page_markdown_bytes=pages,
        page_content_dispositions=(
            "markdown_materialized",
            "provider_empty_page",
        ),
    )

    built = FullSourceArtifactFactory().create().build_document_extraction(
        normalization_run_id="run-provider-empty-page",
        document_id="document-provider-empty-page",
        profile_id="technical_pdf_profile_v0",
        extraction=extraction,
    )

    assert [
        unit["source_location"].get("page_content_disposition")
        for unit in built.units
    ] == ["markdown_materialized", "provider_empty_page"]
    assert built.units[1].get("text") == ""


@pytest.mark.parametrize(
    ("dispositions", "error"),
    (
        (("markdown_materialized",), "pdf_document_page_content_disposition_count_invalid"),
        (("provider_empty_page", "markdown_materialized"), "pdf_document_page_content_disposition_mismatch"),
    ),
)
def test_page_content_disposition_is_sealed_to_its_page_markdown(
    dispositions: tuple[str, ...], error: str
) -> None:
    pages = (b"text", b"")
    markdown = b"\n\n".join(pages)
    with pytest.raises(ValueError, match=error):
        PdfDocumentExtraction(
            source_pdf_sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
            page_numbers=(1, 2),
            markdown_bytes=markdown,
            markdown_sha256=hashlib.sha256(markdown).hexdigest(),
            image_refs=(),
            provider_id="offline_fixture_provider",
            requested_model_id=MISTRAL_OCR_MODEL,
            model_id="offline_fixture_model",
            adapter_id="offline_fixture_adapter_v1",
            request_contract_version=MISTRAL_OCR_REQUEST_CONTRACT_VERSION,
            request_parameters=MISTRAL_OCR_REQUEST_PARAMETERS,
            request_parameters_sha256=hashlib.sha256(
                json.dumps(
                    dict(MISTRAL_OCR_REQUEST_PARAMETERS),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
            page_markdown_sha256=tuple(hashlib.sha256(page).hexdigest() for page in pages),
            qualification_status="offline_fixture",
            usage_page_count=2,
            page_markdown_bytes=pages,
            page_content_dispositions=dispositions,
        )
def test_success_preserves_multiple_same_page_and_page_scoped_targets(
    tmp_path: Path,
) -> None:
    pages = [
        {
            "index": 0,
            "markdown": "![first](a.png)\n![second](b.png)",
            "images": [
                {"id": "a.png", "image_base64": PNG_BASE64},
                {"id": "b.png", "image_base64": PNG_BASE64},
            ],
        },
        {
            "index": 1,
            "markdown": "![shared](shared.png)",
            "images": [{"id": "shared.png", "image_base64": PNG_BASE64}],
        },
        {
            "index": 2,
            "markdown": "![shared-again](shared.png)",
            "images": [{"id": "shared.png", "image_base64": PNG_BASE64}],
        },
    ]
    opener = _FakeOpener(_FakeResponse(_response(pages)))

    result = _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(3))

    _assert_one_post(opener)
    assert tuple(
        (ref.page_number, ref.markdown_target) for ref in result.image_refs
    ) == (
        (1, "a.png"),
        (1, "b.png"),
        (2, "shared.png"),
        (3, "shared.png"),
    )
    assert len({ref.local_ref for ref in result.image_refs}) == 4


def test_provider_reported_model_outside_pinned_family_is_terminal(
    tmp_path: Path,
) -> None:
    opener = _FakeOpener(
        _FakeResponse(
            _response(
                [{"index": 0, "markdown": "page", "images": []}],
                model="mistral-ocr-other",
            )
        )
    )

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))

    assert caught.value.code == "PDF_DOCUMENT_AI_MODEL_MISMATCH"
    assert len(opener.calls) == 1
    assert MISTRAL_OCR_PROVIDER_REPORTED_MODEL_IDS == (
        "mistral-ocr-4-1",
        "mistral-ocr-4-1-completion",
    )


def _fidelity_offline_pages() -> tuple[str, list[dict[str, object]]]:
    markdown = (FIDELITY_FIXTURE_ROOT / "mistral-markdown.md").read_text(
        encoding="utf-8"
    )
    by_page = {
        page_number: target
        for page_number, target, _sha256 in FIDELITY_IMAGE_ASSOCIATIONS
    }
    pages: list[dict[str, object]] = []
    cursor = 0
    footers = tuple(re.finditer(r"(?m)^(\d+) of 28$", markdown))
    assert tuple(int(match.group(1)) for match in footers) == tuple(range(1, 29))
    for page_number, footer in enumerate(footers, start=1):
        page_markdown = markdown[cursor : footer.end()]
        cursor = footer.end()
        if page_number < 28:
            assert markdown[cursor : cursor + 2] == "\n\n"
            cursor += 2
        target = by_page.get(page_number)
        images: list[dict[str, str]] = []
        if target is not None:
            assert f"]({target})" in page_markdown
            encoded = base64.b64encode(
                (FIDELITY_FIXTURE_ROOT / target).read_bytes()
            ).decode("ascii")
            images.append(
                {
                    "id": target,
                    "image_base64": f"data:image/jpeg;base64,{encoded}",
                }
            )
        pages.append(
            {"index": page_number - 1, "markdown": page_markdown, "images": images}
        )
    assert cursor == len(markdown)
    return markdown, pages


def test_fidelity_offline_fixture_preserves_all_eight_image_associations(
    tmp_path: Path,
) -> None:
    markdown, pages = _fidelity_offline_pages()
    pdf_bytes = PUBLIC_PDF.read_bytes()
    opener = _FakeOpener(_FakeResponse(_response(pages)))
    source_context = PdfSourceContext(
        document_ref="fidelity-public-offline-fixture",
        expected_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        preflight_page_count=28,
    )

    result = _extractor(tmp_path, opener).extract(pdf_bytes, source_context)

    _assert_one_post(opener, expected_pdf_bytes=pdf_bytes)
    assert result.markdown_bytes == markdown.encode("utf-8")
    assert tuple(
        (ref.page_number, ref.markdown_target, ref.sha256)
        for ref in result.image_refs
    ) == FIDELITY_IMAGE_ASSOCIATIONS
    assert len(result.image_refs) == 8
    for ref in result.image_refs:
        assert ref.content_bytes == (
            FIDELITY_FIXTURE_ROOT / ref.markdown_target
        ).read_bytes()
        assert hashlib.sha256(ref.content_bytes).hexdigest() == ref.sha256
    repeated_hash_refs = [
        ref
        for ref in result.image_refs
        if ref.sha256 == FIDELITY_IMAGE_ASSOCIATIONS[-1][2]
    ]
    assert [(ref.page_number, ref.markdown_target) for ref in repeated_hash_refs] == [
        (20, "img-5.jpeg"),
        (24, "img-6.jpeg"),
        (25, "img-7.jpeg"),
    ]


@pytest.mark.parametrize(
    ("page_number", "markdown_target", "expected_error"),
    (
        (0, "img.png", "pdf_document_image_page_number_invalid"),
        (True, "img.png", "pdf_document_image_page_number_invalid"),
        (1, "../img.png", "pdf_document_image_markdown_target_must_be_closed_relative"),
        (1, "https://example.invalid/img.png", "pdf_document_image_markdown_target_must_be_closed_relative"),
    ),
)
def test_neutral_image_ref_rejects_invalid_page_or_escaping_target(
    page_number: object, markdown_target: str, expected_error: str
) -> None:
    with pytest.raises(ValueError, match=expected_error):
        PdfDocumentImageRef(
            page_number=page_number,  # type: ignore[arg-type]
            markdown_target=markdown_target,
            local_ref="pdf_document_images/batch/image.png",
            sha256=hashlib.sha256(PNG_BYTES).hexdigest(),
            media_type="image/png",
            content_bytes=PNG_BYTES,
        )


def _neutral_extraction(
    image_refs: tuple[PdfDocumentImageRef, ...],
) -> PdfDocumentExtraction:
    markdown = b"page one\n\npage two"
    parameters_sha = hashlib.sha256(
        json.dumps(
            dict(MISTRAL_OCR_REQUEST_PARAMETERS),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return PdfDocumentExtraction(
        source_pdf_sha256="0" * 64,
        page_numbers=(1, 2),
        markdown_bytes=markdown,
        markdown_sha256=hashlib.sha256(markdown).hexdigest(),
        image_refs=image_refs,
        provider_id="offline_fixture_provider",
        requested_model_id=MISTRAL_OCR_MODEL,
        model_id="offline_fixture_model",
        adapter_id="offline_fixture_adapter_v1",
        request_contract_version=MISTRAL_OCR_REQUEST_CONTRACT_VERSION,
        request_parameters=MISTRAL_OCR_REQUEST_PARAMETERS,
        request_parameters_sha256=parameters_sha,
        page_markdown_sha256=tuple(
            hashlib.sha256(part).hexdigest() for part in (b"page one", b"page two")
        ),
        qualification_status="offline_fixture",
        usage_page_count=2,
    )


def _neutral_image_ref(
    page_number: int, markdown_target: str, local_ref: str
) -> PdfDocumentImageRef:
    return PdfDocumentImageRef(
        page_number=page_number,
        markdown_target=markdown_target,
        local_ref=local_ref,
        sha256=hashlib.sha256(PNG_BYTES).hexdigest(),
        media_type="image/png",
        content_bytes=PNG_BYTES,
    )


@pytest.mark.parametrize(
    ("image_refs", "expected_error"),
    (
        (
            (
                _neutral_image_ref(3, "img.png", "images/a.png"),
            ),
            "pdf_document_image_page_not_in_document",
        ),
        (
            (
                _neutral_image_ref(2, "b.png", "images/b.png"),
                _neutral_image_ref(1, "a.png", "images/a.png"),
            ),
            "pdf_document_image_page_order_invalid",
        ),
        (
            (
                _neutral_image_ref(1, "same.png", "images/a.png"),
                _neutral_image_ref(1, "same.png", "images/b.png"),
            ),
            "pdf_document_image_association_duplicate",
        ),
        (
            (
                _neutral_image_ref(1, "a.png", "images/same.png"),
                _neutral_image_ref(2, "b.png", "images/same.png"),
            ),
            "pdf_document_image_ref_duplicate",
        ),
    ),
    ids=("foreign_page", "page_regression", "duplicate_association", "duplicate_local_ref"),
)
def test_neutral_extraction_rejects_ambiguous_image_associations(
    image_refs: tuple[PdfDocumentImageRef, ...], expected_error: str
) -> None:
    with pytest.raises(ValueError, match=expected_error):
        _neutral_extraction(image_refs)


def test_same_markdown_target_on_distinct_pages_remains_unambiguous() -> None:
    extraction = _neutral_extraction(
        (
            _neutral_image_ref(1, "same.png", "images/a.png"),
            _neutral_image_ref(2, "same.png", "images/b.png"),
        )
    )

    assert tuple(
        (ref.page_number, ref.markdown_target) for ref in extraction.image_refs
    ) == ((1, "same.png"), (2, "same.png"))


@pytest.mark.parametrize(
    "indexes",
    (
        (0, 0),
        (0, 2),
        (1, 0),
    ),
    ids=("duplicate", "gap", "out_of_order"),
)
def test_page_index_mutations_fail_typed_without_retry(
    tmp_path: Path, indexes: tuple[int, int]
) -> None:
    opener = _FakeOpener(
        _FakeResponse(
            _response(
                [
                    {"index": indexes[0], "markdown": "first", "images": []},
                    {"index": indexes[1], "markdown": "second", "images": []},
                ]
            )
        )
    )

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(2))

    _assert_one_post(opener)
    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_PAGE_ORDER_INVALID"
    )


@pytest.mark.parametrize(
    ("response", "expected_code"),
    (
        (_FakeResponse(raw=b"not-json"), "PDF_DOCUMENT_AI_RESPONSE_INVALID"),
        (_FakeResponse([], status=200), "PDF_DOCUMENT_AI_RESPONSE_INVALID"),
        (_FakeResponse({"model": "m", "usage_info": {}}), "PDF_DOCUMENT_AI_PAGE_COUNT_MISMATCH"),
        (
            _FakeResponse(_response([{"index": 0, "markdown": 1, "images": []}])),
            "PDF_DOCUMENT_AI_RESPONSE_INVALID",
        ),
        (
            _FakeResponse(_response([{"index": 0, "markdown": "ok", "images": []}], model="")),
            "PDF_DOCUMENT_AI_RESPONSE_INVALID",
        ),
        (
            _FakeResponse(
                _response(
                    [{"index": 0, "markdown": "ok", "images": []}],
                    pages_processed=2,
                )
            ),
            "PDF_DOCUMENT_AI_PAGE_COUNT_MISMATCH",
        ),
    ),
    ids=(
        "malformed_json",
        "non_object",
        "missing_pages",
        "non_text_markdown",
        "missing_model",
        "usage_mismatch",
    ),
)
def test_malformed_responses_fail_typed_once(
    tmp_path: Path, response: _FakeResponse, expected_code: str
) -> None:
    opener = _FakeOpener(response)

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))

    _assert_one_post(opener)
    _assert_typed_failure_without_leak(caught, expected_code=expected_code)


@pytest.mark.parametrize(
    ("markdown", "image_ids"),
    (
        ("page", ("img-0.png",)),
        ("page\n\n![chart](other.png)", ("img-0.png",)),
        (
            "page\n\n![second](img-1.png)\n![first](img-0.png)",
            ("img-0.png", "img-1.png"),
        ),
    ),
    ids=("missing_target", "mismatched_target", "reversed_targets"),
)
def test_markdown_image_association_must_exactly_match_ids_in_order(
    tmp_path: Path, markdown: str, image_ids: tuple[str, ...]
) -> None:
    images = [
        {
            "id": image_id,
            "image_base64": f"data:image/png;base64,{PNG_BASE64}",
        }
        for image_id in image_ids
    ]
    opener = _FakeOpener(
        _FakeResponse(
            _response([{"index": 0, "markdown": markdown, "images": images}])
        )
    )

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))

    _assert_one_post(opener)
    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_IMAGE_ASSOCIATION_INVALID"
    )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "image",
    (
        {},
        {"id": "img-0.png", "image_base64": "%%%not-base64%%%"},
        {
            "id": "img-0.png",
            "image_base64": base64.b64encode(b"not-an-image").decode("ascii"),
        },
    ),
    ids=("missing_payload", "broken_base64", "unsupported_signature"),
)
def test_missing_or_broken_image_fails_and_leaves_no_batch(
    tmp_path: Path, image: Mapping[str, object]
) -> None:
    image_id = image.get("id")
    markdown = (
        f"page\n\n![image]({image_id})" if isinstance(image_id, str) else "page"
    )
    opener = _FakeOpener(
        _FakeResponse(
            _response([{"index": 0, "markdown": markdown, "images": [image]}])
        )
    )

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))

    _assert_one_post(opener)
    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_IMAGE_INVALID"
    )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("status", "expected_code"),
    (
        (401, "PDF_DOCUMENT_AI_AUTH_FAILED"),
        (403, "PDF_DOCUMENT_AI_AUTH_FAILED"),
        (402, "PDF_DOCUMENT_AI_PAYMENT_REQUIRED"),
        (429, "PDF_DOCUMENT_AI_RATE_LIMITED"),
        (500, "PDF_DOCUMENT_AI_PROVIDER_UNAVAILABLE"),
        (503, "PDF_DOCUMENT_AI_PROVIDER_UNAVAILABLE"),
    ),
)
def test_http_failures_are_typed_sanitized_and_never_retried(
    tmp_path: Path, status: int, expected_code: str
) -> None:
    error = HTTPError(
        "https://api.mistral.ai/v1/ocr",
        status,
        RAW_PROVIDER_SECRET,
        hdrs=None,
        fp=io.BytesIO(RAW_PROVIDER_SECRET.encode("utf-8")),
    )
    opener = _FakeOpener(error)

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))

    _assert_one_post(opener)
    _assert_typed_failure_without_leak(caught, expected_code=expected_code)


@pytest.mark.parametrize(
    ("error", "expected_code"),
    (
        (TimeoutError(RAW_PROVIDER_SECRET), "PDF_DOCUMENT_AI_TIMEOUT"),
        (URLError(RAW_PROVIDER_SECRET), "PDF_DOCUMENT_AI_TRANSPORT_FAILED"),
    ),
    ids=("timeout", "transport"),
)
def test_transport_failures_are_typed_sanitized_and_never_retried(
    tmp_path: Path, error: BaseException, expected_code: str
) -> None:
    opener = _FakeOpener(error)

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))

    _assert_one_post(opener)
    _assert_typed_failure_without_leak(caught, expected_code=expected_code)


def test_non_200_response_without_http_error_is_rejected_once(tmp_path: Path) -> None:
    opener = _FakeOpener(
        _FakeResponse({"raw": RAW_PROVIDER_SECRET}, status=400)
    )

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))

    _assert_one_post(opener)
    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_HTTP_REJECTED"
    )


def test_oversized_response_is_rejected_before_json_parsing(tmp_path: Path) -> None:
    response = _OversizedResponse()
    opener = _FakeOpener(response)

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))

    _assert_one_post(opener)
    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_RESPONSE_TOO_LARGE"
    )
    assert len(response.read_limits) == 1


def test_private_rnd_capture_returns_exact_bounded_annotation_response_once(
    tmp_path: Path,
) -> None:
    raw_response = (
        b'{"document_annotation":"private provider response",'
        b'"pages":[{"index":0,"markdown":"[t](tbl-0.html)","tables":[]}]}'
    )
    opener = _FakeOpener(_FakeResponse(raw=raw_response))
    prompt = "Capture one physical table annotation response."

    captured = _extractor(
        tmp_path, opener
    ).capture_unvalidated_table_annotation_response_once(
        PDF_BYTES,
        _source_context(1),
        source_page_numbers=(0,),
        document_annotation_prompt=prompt,
    )

    assert captured == raw_response
    _assert_one_post(
        opener,
        expected_annotation_prompt=prompt,
        expected_source_page_numbers=(0,),
    )
    assert list(tmp_path.iterdir()) == []


def test_partial_image_decode_failure_never_touches_filesystem(tmp_path: Path) -> None:
    opener = _FakeOpener(
        _FakeResponse(
            _response(
                [
                    {
                        "index": 0,
                        "markdown": (
                            "page\n\n![first](img-0.png)\n![second](img-1.png)"
                        ),
                        "images": [
                            {
                                "id": "img-0.png",
                                "image_base64": f"data:image/png;base64,{PNG_BASE64}",
                            },
                            {
                                "id": "img-1.png",
                                "image_base64": "%%%broken-second-image%%%",
                            },
                        ],
                    }
                ]
            )
        )
    )

    with pytest.raises(PdfDocumentExtractionError) as caught:
        _extractor(tmp_path, opener).extract(PDF_BYTES, _source_context(1))

    _assert_one_post(opener)
    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_IMAGE_INVALID"
    )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "api_base_url",
    (
        "https://mistral.invalid/v1",
        "https://api.mistral.ai:443/v1",
        "https://api.mistral.ai/v2",
        "https://api.mistral.ai/v1/arbitrary",
    ),
    ids=("foreign_host", "explicit_port", "wrong_api_version", "arbitrary_path"),
)
def test_arbitrary_host_port_or_path_is_rejected_before_http(
    tmp_path: Path, api_base_url: str
) -> None:
    opener = _FakeOpener(_FakeResponse({}))

    with pytest.raises(PdfDocumentExtractionError) as caught:
        MistralPdfDocumentExtractor(
            api_base_url=api_base_url,
            api_key=API_KEY,
            image_decoder=BoundedImageDecoder(),
            qualification_status="offline_fixture",
            opener=opener,
        )

    assert opener.calls == []
    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_CONFIG_INVALID"
    )


def test_direct_adapter_rejects_missing_key_before_http(tmp_path: Path) -> None:
    opener = _FakeOpener(
        _FakeResponse(_response([{"index": 0, "markdown": "ok", "images": []}]))
    )

    with pytest.raises(PdfDocumentExtractionError) as caught:
        MistralPdfDocumentExtractor(
            api_base_url="https://api.mistral.ai/v1",
            api_key="   ",
            image_decoder=BoundedImageDecoder(),
            qualification_status="offline_fixture",
            opener=opener,
        )

    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_CONFIG_MISSING"
    )
    assert opener.calls == []


def _server_request(
    *,
    engine: str = "mistral_ocr",
    api_base_url: str = "https://api.mistral.ai/v1",
    api_key: str = API_KEY,
) -> SimpleNamespace:
    config = SimpleNamespace(
        CONTENT_EXTRACTION_ENGINE=engine,
        MISTRAL_OCR_API_BASE_URL=api_base_url,
        MISTRAL_OCR_API_KEY=api_key,
    )
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(config=config)))


def test_factory_exposes_configured_native_mistral_to_product_flow(
    tmp_path: Path,
) -> None:
    configured = PdfDocumentExtractorFactory.create(
        server_request=_server_request(), image_root=tmp_path
    )
    other_engine = PdfDocumentExtractorFactory.create(
        server_request=_server_request(engine="tika"), image_root=tmp_path
    )
    no_request = PdfDocumentExtractorFactory.create()

    assert isinstance(configured, MistralPdfDocumentExtractor)
    assert isinstance(other_engine, UnconfiguredPdfDocumentExtractor)
    assert isinstance(no_request, UnconfiguredPdfDocumentExtractor)


def test_factory_missing_native_key_is_terminal_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request = _server_request(api_key="")
    monkeypatch.setattr(
        "broker_reports_gate1.mistral_pdf_document_ai.build_opener",
        lambda *_handlers: (_ for _ in ()).throw(
            AssertionError("static admission must not construct HTTP transport")
        ),
    )
    extractor = PdfDocumentExtractorFactory.create(
        server_request=request,
        image_root=tmp_path,
    )
    assert isinstance(extractor, RejectedPdfDocumentExtractor)
    with pytest.raises(PdfDocumentExtractionError) as caught:
        extractor.extract(PDF_BYTES, _source_context(1))
    _assert_typed_failure_without_leak(
        caught, expected_code="PDF_DOCUMENT_AI_CONFIG_MISSING"
    )


def _full_source_checksum(
    *,
    page_number: int,
    markdown_target: str,
    local_ref: str,
    image_bytes: bytes,
) -> tuple[str, list[dict[str, object]]]:
    markdown = b"# Provider-neutral extraction"
    parameters_sha = hashlib.sha256(
        json.dumps(
            dict(MISTRAL_OCR_REQUEST_PARAMETERS), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    extraction = PdfDocumentExtraction(
        source_pdf_sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
        page_numbers=(1, 2),
        markdown_bytes=markdown,
        markdown_sha256=hashlib.sha256(markdown).hexdigest(),
        image_refs=(
            PdfDocumentImageRef(
                page_number=page_number,
                markdown_target=markdown_target,
                local_ref=local_ref,
                sha256=hashlib.sha256(image_bytes).hexdigest(),
                media_type="image/png",
                content_bytes=image_bytes,
            ),
        ),
        provider_id=MISTRAL_OCR_PROVIDER_ID,
        requested_model_id=MISTRAL_OCR_MODEL,
        model_id="mistral-ocr-versioned",
        adapter_id=MISTRAL_OCR_ADAPTER_ID,
        request_contract_version=MISTRAL_OCR_REQUEST_CONTRACT_VERSION,
        request_parameters=MISTRAL_OCR_REQUEST_PARAMETERS,
        request_parameters_sha256=parameters_sha,
        page_markdown_sha256=(
            hashlib.sha256(markdown).hexdigest(),
            hashlib.sha256(b"").hexdigest(),
        ),
        qualification_status="offline_fixture",
        usage_page_count=2,
    )
    built = FullSourceArtifactFactory().create().build_document_extraction(
        normalization_run_id="pdf-document-ai-checksum-run",
        document_id="pdf-document-ai-checksum-document",
        profile_id="technical_pdf_profile_v0",
        extraction=extraction,
    )
    assert len(built.payloads) == 1
    payload = built.payloads[0]
    return (
        str(payload["payload_checksum_ref"]),
        list(payload["document_ai_image_refs"]),
    )


@pytest.mark.parametrize(
    ("mutated_page", "mutated_target", "mutated_ref", "mutated_bytes"),
    (
        (2, "img-0.png", "pdfimg_a", PNG_BYTES),
        (1, "img-other.png", "pdfimg_a", PNG_BYTES),
        (1, "img-0.png", "pdfimg_b", PNG_BYTES),
        (1, "img-0.png", "pdfimg_a", PNG_BYTES + b"-changed"),
    ),
    ids=("page_number", "markdown_target", "image_ref", "image_hash"),
)
def test_full_source_payload_checksum_binds_every_image_association_field(
    mutated_page: int,
    mutated_target: str,
    mutated_ref: str,
    mutated_bytes: bytes,
) -> None:
    baseline_checksum, baseline_refs = _full_source_checksum(
        page_number=1,
        markdown_target="img-0.png",
        local_ref="pdfimg_a",
        image_bytes=PNG_BYTES,
    )

    mutated_checksum, _mutated_refs = _full_source_checksum(
        page_number=mutated_page,
        markdown_target=mutated_target,
        local_ref=mutated_ref,
        image_bytes=mutated_bytes,
    )

    assert baseline_refs == [
        {
            "page_number": 1,
            "markdown_target": "img-0.png",
            "local_ref": "pdfimg_a",
            "sha256": hashlib.sha256(PNG_BYTES).hexdigest(),
        }
    ]
    assert mutated_checksum != baseline_checksum


def _pdf_graph_fixture(tmp_path: Path):
    run_id = "pdf-atomic-publication-run"
    document_id = "pdf-atomic-publication-document"
    context = ArtifactAccessContext(
        user_id="pdf-user",
        normalization_run_id=run_id,
        case_id="pdf-case",
        chat_id="pdf-chat",
        workspace_model_id="pdf-workspace",
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
                    "openwebui_file_id": "pdf-upload",
                    "content_type": "application/pdf",
                    "source_deleted": False,
                },
            ),
        )
    ).create(normalization_run_id=run_id)
    graph.register_document(
        {
            "document_id": document_id,
            "root_input_ordinal": 1,
            "source_kind": "openwebui_pipe",
            "container_format": "pdf",
            "declared_mime_type": "application/pdf",
            "sha256": hashlib.sha256(PDF_BYTES).hexdigest(),
            "size_bytes": len(PDF_BYTES),
        }
    )
    image = _neutral_image_ref(1, "img-0.png", "pdfimg_atomic_fixture")
    markdown = b"page\n\n![image](img-0.png)"
    parameters_sha = hashlib.sha256(
        json.dumps(
            dict(MISTRAL_OCR_REQUEST_PARAMETERS), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    extraction = PdfDocumentExtraction(
        source_pdf_sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
        page_numbers=(1,),
        markdown_bytes=markdown,
        markdown_sha256=hashlib.sha256(markdown).hexdigest(),
        image_refs=(image,),
        provider_id="offline_fixture_provider",
        requested_model_id=MISTRAL_OCR_MODEL,
        model_id="offline_fixture_model",
        adapter_id="offline_fixture_adapter_v1",
        request_contract_version=MISTRAL_OCR_REQUEST_CONTRACT_VERSION,
        request_parameters=MISTRAL_OCR_REQUEST_PARAMETERS,
        request_parameters_sha256=parameters_sha,
        page_markdown_sha256=(hashlib.sha256(markdown).hexdigest(),),
        qualification_status="offline_fixture",
        usage_page_count=1,
    )
    result = FullSourceArtifactFactory().create().build_document_extraction(
        normalization_run_id=run_id,
        document_id=document_id,
        profile_id="technical_pdf_profile_v0",
        extraction=extraction,
    )
    return store, graph, context, result, image


def _native_table_annotation_receipt() -> dict[str, str | dict[str, object]]:
    content = "Assess physical table continuations only."
    execution = execution_from_managed_prompt(
        PdfTableContinuationAnnotationManagedPrompt(
            prompt_ref="test-prompt",
            command=TABLE_ANNOTATION_PROMPT_COMMAND,
            version="test-history",
            content=content,
            hash=pdf_table_continuation_annotation_prompt_hash(content),
            source="test",
            template_id=TABLE_ANNOTATION_PROMPT_TEMPLATE_ID,
            template_kind=TABLE_ANNOTATION_PROMPT_TEMPLATE_KIND,
            prompt_contract_id=TABLE_ANNOTATION_PROMPT_CONTRACT_ID,
            input_schema_version=TABLE_ANNOTATION_INPUT_SCHEMA_VERSION,
            output_schema_id=TABLE_ANNOTATION_OUTPUT_SCHEMA_ID,
            output_schema_version=TABLE_ANNOTATION_OUTPUT_SCHEMA_VERSION,
            tags=(TABLE_ANNOTATION_PROMPT_REQUIRED_TAG,),
            safe_metadata={"name": "test"},
        )
    )
    return {
        "assessment_schema_version": "offline_fixture_annotation_v1",
        "annotation_prompt_sha256": execution.content_sha256,
        "annotation_schema_sha256": "b" * 64,
        "request_parameters_sha256": "c" * 64,
        "raw_annotation_sha256": "d" * 64,
        "selected_page_bindings_sha256": "e" * 64,
        "prompt_snapshot": execution.validated_prompt_snapshot(),
    }


def _pdf_graph_with_native_table_sidecar(tmp_path: Path):
    store, graph, context, _result, _image = _pdf_graph_fixture(tmp_path)
    first_page = b"[first](table-1.html)"
    second_page = b"[second](table-2.html)"
    markdown = b"\n\n".join((first_page, second_page))
    parameters = (("include_image_base64", True),)
    extraction = PdfDocumentExtraction(
        source_pdf_sha256=hashlib.sha256(PDF_BYTES).hexdigest(),
        page_numbers=(1, 2),
        markdown_bytes=markdown,
        markdown_sha256=hashlib.sha256(markdown).hexdigest(),
        image_refs=(),
        provider_id="offline_fixture_provider",
        requested_model_id="offline_fixture_model",
        model_id="offline_fixture_model",
        adapter_id="offline_fixture_adapter_v1",
        request_contract_version="offline_fixture_request_v1",
        request_parameters=parameters,
        request_parameters_sha256=hashlib.sha256(
            b'{"include_image_base64":true}'
        ).hexdigest(),
        page_markdown_sha256=tuple(
            hashlib.sha256(page).hexdigest() for page in (first_page, second_page)
        ),
        qualification_status="offline_fixture",
        usage_page_count=2,
        page_markdown_bytes=(first_page, second_page),
        table_refs=(
            PdfDocumentTableRef(
                page_number=1,
                markdown_target="table-1.html",
                local_ref="pdftable_atomic_1",
                sha256=hashlib.sha256(
                    b"<table><tr><th>Date</th></tr><tr><td>1</td></tr></table>"
                ).hexdigest(),
                html_bytes=b"<table><tr><th>Date</th></tr><tr><td>1</td></tr></table>",
            ),
            PdfDocumentTableRef(
                page_number=2,
                markdown_target="table-2.html",
                local_ref="pdftable_atomic_2",
                sha256=hashlib.sha256(
                    b"<table><tr><td>2</td></tr></table>"
                ).hexdigest(),
                html_bytes=b"<table><tr><td>2</td></tr></table>",
            ),
        ),
    )
    result = FullSourceArtifactFactory().create().build_document_extraction(
        normalization_run_id=context.normalization_run_id,
        document_id="pdf-atomic-publication-document",
        profile_id="technical_pdf_profile_v0",
        extraction=extraction,
    )
    tables = [
        unit
        for unit in result.units
        if unit.get("document_ai_native_table_ref") is not None
    ]
    sidecar = build_physical_table_continuation_sidecar(
        normalization_run_id=context.normalization_run_id,
        document_id="pdf-atomic-publication-document",
        source_pdf_sha256=extraction.source_pdf_sha256,
        source_units=tables,
        proposed_links=[
            {
                "parent": {
                    "native_table_ref": tables[0]["document_ai_native_table_ref"],
                    "native_table_sha256": tables[0][
                        "document_ai_native_table_sha256"
                    ],
                    "page_number": 1,
                },
                "child": {
                    "native_table_ref": tables[1]["document_ai_native_table_ref"],
                    "native_table_sha256": tables[1][
                        "document_ai_native_table_sha256"
                    ],
                    "page_number": 2,
                },
            }
        ],
        annotation_receipt=_native_table_annotation_receipt(),
    )
    return store, graph, context, result, sidecar


def test_pdf_full_source_and_image_are_one_atomic_private_publication(
    tmp_path: Path,
) -> None:
    store, graph, context, result, image = _pdf_graph_fixture(tmp_path)

    graph.publish_pdf_full_source_atomic(result=result, image_refs=(image,))

    assert len(graph.collection("private_normalized_source_payloads")) == 1
    assert len(graph.collection("private_normalized_source_units")) == 1
    assert graph.refs_by_type[PRIVATE_BINARY_ARTIFACT_TYPE] == [image.local_ref]
    resolved = ArtifactResolver(store).resolve_private_binary(
        image.local_ref,
        context,
        expected_sha256=image.sha256,
    )
    assert resolved["content"] == PNG_BYTES
    assert resolved["media_type"] == "image/png"


def test_pdf_source_deletion_purges_markdown_unit_and_linked_image(
    tmp_path: Path,
) -> None:
    store, graph, context, result, image = _pdf_graph_fixture(tmp_path)
    graph.publish_pdf_full_source_atomic(result=result, image_refs=(image,))
    source_context = ArtifactAccessContext(
        user_id=context.user_id,
        normalization_run_id=context.normalization_run_id,
        case_id=context.case_id,
        chat_id=context.chat_id,
        workspace_model_id=context.workspace_model_id,
        source_file_id="pdf-upload",
        allow_private=True,
    )

    purged = store.mark_source_file_deleted(source_context)

    assert purged.records_changed == 4
    private_graph_ids = {
        *graph.refs_by_type["private_normalized_source_payload_v0"],
        *graph.refs_by_type["private_normalized_source_unit_v0"],
        *graph.refs_by_type[PRIVATE_BINARY_ARTIFACT_TYPE],
    }
    assert private_graph_ids <= set(purged.artifact_ids)
    assert all(
        store.get_record_unchecked(artifact_id).lifecycle_status == "purged"
        for artifact_id in private_graph_ids
    )
    with pytest.raises(ArtifactStoreError) as blocked:
        ArtifactResolver(store).resolve_private_binary(
            image.local_ref,
            context,
            expected_sha256=image.sha256,
        )
    assert blocked.value.code == "artifact_purged"


def test_pdf_atomic_failure_does_not_publish_images_or_update_graph_indexes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, graph, _context, result, image = _pdf_graph_fixture(tmp_path)

    def fail_atomic(_records: object) -> None:
        raise ArtifactStoreError("artifact_atomic_write_failed", "synthetic")

    monkeypatch.setattr(store, "put_records_atomic", fail_atomic)
    with pytest.raises(ArtifactStoreError, match="synthetic"):
        graph.publish_pdf_full_source_atomic(result=result, image_refs=(image,))

    assert len(graph.collection("private_normalized_source_payloads")) == 0
    assert len(graph.collection("private_normalized_source_units")) == 0
    assert PRIVATE_BINARY_ARTIFACT_TYPE not in graph.refs_by_type
    assert store.get_record_unchecked(image.local_ref) is None


def test_pdf_full_source_and_physical_table_sidecar_are_one_atomic_publication(
    tmp_path: Path,
) -> None:
    store, graph, _context, result, sidecar = _pdf_graph_with_native_table_sidecar(
        tmp_path
    )

    graph.publish_pdf_full_source_atomic(
        result=result,
        image_refs=(),
        physical_table_continuation_sidecar=sidecar,
    )

    sidecar_refs = graph.physical_table_continuation_refs_by_doc[
        "pdf-atomic-publication-document"
    ]
    assert len(sidecar_refs) == 1
    assert graph.refs_by_type[PHYSICAL_TABLE_CONTINUATION_ARTIFACT_TYPE] == sidecar_refs
    stored = store.get_record_unchecked(sidecar_refs[0])
    assert stored is not None
    assert stored.visibility == "private_case"
    assert stored.safe_metadata == {
        "schema_version": PHYSICAL_TABLE_CONTINUATION_SCHEMA_VERSION,
        "sidecar_id": sidecar["sidecar_id"],
        "document_id": "pdf-atomic-publication-document",
        "source_checksum_ref": hashlib.sha256(PDF_BYTES).hexdigest(),
        "links_total": 1,
        "contains_source_values": False,
    }
    assert store.read_payload(stored) == sidecar


def test_pdf_atomic_failure_does_not_publish_or_index_physical_table_sidecar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, graph, _context, result, sidecar = _pdf_graph_with_native_table_sidecar(
        tmp_path
    )

    def fail_atomic(_records: object) -> None:
        raise ArtifactStoreError("artifact_atomic_write_failed", "synthetic")

    monkeypatch.setattr(store, "put_records_atomic", fail_atomic)
    with pytest.raises(ArtifactStoreError, match="synthetic"):
        graph.publish_pdf_full_source_atomic(
            result=result,
            image_refs=(),
            physical_table_continuation_sidecar=sidecar,
        )

    assert graph.physical_table_continuation_refs_by_doc == {}
    assert PHYSICAL_TABLE_CONTINUATION_ARTIFACT_TYPE not in graph.refs_by_type
    assert all(
        record.artifact_type != PHYSICAL_TABLE_CONTINUATION_ARTIFACT_TYPE
        for record in store.list_by_run("pdf-atomic-publication-run")
    )


def test_pdf_rejects_invalid_physical_table_sidecar_before_atomic_store_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, graph, _context, result, sidecar = _pdf_graph_with_native_table_sidecar(
        tmp_path
    )
    invalid_sidecar = copy.deepcopy(sidecar)
    invalid_sidecar["source_pdf_sha256"] = "0" * 64
    calls = 0

    def unexpected_atomic_call(_records: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("invalid sidecar reached atomic persistence")

    monkeypatch.setattr(store, "put_records_atomic", unexpected_atomic_call)
    with pytest.raises(
        Exception, match="bounded_physical_table_continuation_invalid"
    ):
        graph.publish_pdf_full_source_atomic(
            result=result,
            image_refs=(),
            physical_table_continuation_sidecar=invalid_sidecar,
        )

    assert calls == 0
    assert graph.physical_table_continuation_refs_by_doc == {}
    assert PHYSICAL_TABLE_CONTINUATION_ARTIFACT_TYPE not in graph.refs_by_type


def test_production_pipe_uses_configured_native_mistral_once_and_nonblocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opener = _FakeOpener(
        _FakeResponse(
            _response(
                [
                    {
                        "index": page_index,
                        "markdown": f"# Page {page_index + 1}",
                        "images": [],
                    }
                    for page_index in range(28)
                ]
            )
        )
    )

    monkeypatch.setattr(
        "broker_reports_gate1.mistral_pdf_document_ai.build_opener",
        lambda *_handlers: opener,
    )
    pipe = Pipe()
    pipe.valves.artifact_store_path = str(tmp_path / "artifacts.sqlite3")
    pipe.valves.artifact_payload_root = str(tmp_path / "payloads")
    pdf_bytes = PUBLIC_PDF.read_bytes()

    class OwnedFileResolver:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        async def resolve(self, *, file_id: str, actor_user_id: str) -> object:
            self.calls.append((file_id, actor_user_id))
            return SimpleNamespace(
                filename="heartbeat.pdf",
                content_type="application/pdf",
                payload=pdf_bytes,
            )

    file_resolver = OwnedFileResolver()
    monkeypatch.setattr(
        pipe,
        "_openwebui_file_bytes_resolver",
        lambda: file_resolver,
    )
    published_files: list[dict[str, object]] = []

    async def publish_private_file(**kwargs: object) -> str:
        published_files.append(kwargs)
        content = kwargs["content"]
        assert isinstance(content, bytes)
        assert hashlib.sha256(content).hexdigest() == kwargs["content_sha256"]
        context = kwargs["context"]
        assert isinstance(context, ArtifactAccessContext)
        assert context.user_id == "mistral-heartbeat-user"
        return "mistral-heartbeat-full-source"

    monkeypatch.setattr(
        Pipe,
        "_publish_owner_scoped_private_file",
        staticmethod(publish_private_file),
    )
    body = {
        "messages": [
            {
                "role": "user",
                "content": "Normalize one PDF",
                "files": [
                    {
                        "type": "file",
                        "file": {
                            "id": "mistral-heartbeat-pdf",
                            "filename": "heartbeat.pdf",
                            "mime_type": "application/pdf",
                            "content_bytes": pdf_bytes,
                        },
                    }
                ],
            }
        ]
    }

    async def run() -> tuple[str, bool]:
        heartbeat_observed = False

        async def heartbeat_task() -> None:
            nonlocal heartbeat_observed
            await asyncio.sleep(0)
            heartbeat_observed = True

        pipe_task = asyncio.create_task(
            pipe.pipe(
                body,
                __request__=_server_request(),
                __user__={"id": "mistral-heartbeat-user"},
                __metadata__={
                    "chat_id": "mistral-heartbeat-chat",
                    "model_id": "broker_reports_gate1_pipe_test",
                },
            )
        )
        _unused, content = await asyncio.wait_for(
            asyncio.gather(heartbeat_task(), pipe_task), timeout=5.0
        )
        return content, heartbeat_observed

    content, heartbeat_observed = asyncio.run(run())

    assert heartbeat_observed is True
    assert file_resolver.calls == [
        ("mistral-heartbeat-pdf", "mistral-heartbeat-user")
    ]
    assert len(opener.calls) == 1
    assert len(published_files) == 1
    assert isinstance(content, str) and content
    assert pipe.last_safe_report is not None
    outcomes = pipe.last_safe_report["file_processing_outcomes"]["outcomes"]
    assert len(outcomes) == 1
    assert outcomes[0]["status"] == "success"
    assert outcomes[0]["reason_code"] == "completed"
    assert (
        pipe.last_safe_report["private_artifact_summary"][
            "private_normalized_source_units_count"
        ]
        > 0
    )


def test_static_provider_ownership_stays_out_of_pipe_and_downstream_modules() -> None:
    service_root = Path(__file__).resolve().parents[1]
    pipe_source = (
        service_root / "openwebui_actions" / "broker_reports_gate1_pipe.py"
    ).read_text(encoding="utf-8")
    for provider_owned_name in (
        "MISTRAL_OCR_API_KEY",
        "MISTRAL_OCR_API_BASE_URL",
        "mistral-ocr-latest",
        "mistral_pdf_document_ai",
    ):
        assert provider_owned_name not in pipe_source

    package_root = service_root / "broker_reports_gate1"
    allowed = {
        "pdf_document_ai.py",
        "mistral_pdf_document_ai.py",
        # The managed instruction contract pins this response schema but does
        # not own provider transport, credentials or endpoint selection.
        "pdf_table_continuation_annotation_prompt.py",
    }
    offenders = {
        path.name
        for path in package_root.glob("*.py")
        if path.name not in allowed
        and "mistral_pdf_document_ai" in path.read_text(encoding="utf-8")
    }
    assert offenders == set()
