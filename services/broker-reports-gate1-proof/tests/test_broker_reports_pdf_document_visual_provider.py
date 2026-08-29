from __future__ import annotations

import ast
import base64
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from broker_reports_gate1.gate2_provider_adapters import (
    Gate2OpenWebUIProviderConnection,
)
from broker_reports_gate1.contracts import sha256_json
from broker_reports_gate1.pdf_table_locator_provider import (
    DOCUMENT_VISUAL_FACTORY_REQUIRED,
    DOCUMENT_VISUAL_FORBIDDEN,
    PDF_DOCUMENT_VISUAL_RESPONSE_SCHEMA,
    PdfTableLocatorProviderConfig,
    PdfTableLocatorProviderError,
    PdfTableLocatorProviderFactory,
)
from broker_reports_gate1.pdf_table_raster import PdfTableRasterFactory


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = SERVICE_ROOT / "broker_reports_gate1"


def test_one_document_request_preserves_page_and_raster_order() -> None:
    pages = _page_images()
    value = {
        "pages": [
            {"tables": [_table([50, 40, 300, 900])]},
            {"tables": []},
        ]
    }
    transport = _Transport(value)
    adapter = _adapter(transport)

    result = adapter.invoke_document_visual_geometry(
        task_id="document_visual_proposal",
        phase="PROPOSAL",
        page_images=pages,
        first_geometry_proposal=None,
        attempt_number=1,
        attempt_lineage=[],
    )

    assert len(transport.requests) == 2
    count_request = json.loads(transport.requests[0].data.decode("utf-8"))
    request = json.loads(transport.requests[1].data.decode("utf-8"))
    counted_generation = copy.deepcopy(
        count_request["generateContentRequest"]
    )
    assert counted_generation.pop("model") == "models/gemini-3.5-flash"
    assert counted_generation == request
    parts = request["contents"][0]["parts"]
    assert len(parts) == 5
    model_view = json.loads(parts[0]["text"])
    assert model_view["phase"] == "PROPOSAL"
    assert model_view["page_ordinals"] == [1, 2]
    assert "page_ref" not in model_view
    assert [json.loads(parts[index]["text"]) for index in (1, 3)] == [
        {"page_ordinal": 1},
        {"page_ordinal": 2},
    ]
    assert [
        base64.b64decode(parts[index]["inlineData"]["data"])
        for index in (2, 4)
    ] == [page["png_bytes"] for page in pages]
    schema = request["generationConfig"]["responseJsonSchema"]
    assert schema["$id"] == PDF_DOCUMENT_VISUAL_RESPONSE_SCHEMA
    assert schema["properties"]["pages"]["minItems"] == 2
    assert schema["properties"]["pages"]["maxItems"] == 2
    assert schema["properties"]["pages"]["items"]["properties"][
        "tables"
    ]["maxItems"] == 64
    assert "candidateCount" not in request["generationConfig"]
    rendered_schema = json.dumps(schema, sort_keys=True)
    assert all(token not in rendered_schema for token in ('"text"', '"table_id"'))

    assert result["json_output"] == value
    assert "text" not in result
    attempt = result["attempt"]
    assert attempt["provider_calls"] == 2
    assert attempt["provider_http_calls"] == 2
    assert attempt["count_tokens_http_calls"] == 1
    assert attempt["model_generation_calls"] == 1
    assert attempt["request_hash"] == sha256_json(request)
    assert attempt["generation_request_hash"] == sha256_json(request)
    assert attempt["count_tokens_request_hash"] == sha256_json(count_request)
    assert attempt["counted_generation_body_hash"] == sha256_json(request)
    assert attempt["counted_input_tokens"] == 100
    assert attempt["maximum_counted_input_tokens"] == 1000
    assert attempt["count_tokens_within_hard_guard"] is True
    assert attempt["terminal_failure_class"] is None
    assert attempt["finish_reason"] == "STOP"
    assert attempt["hidden_retry"] is False
    assert attempt["provider_failover"] is False
    assert attempt["product_reachability"] is False
    assert attempt["table_identity_assigned"] is False
    assert attempt["continuation_decided"] is False
    assert [
        page["page_ref"] for page in attempt["document_binding"]["pages"]
    ] == [
        page["raster_manifest"]["page_ref"] for page in pages
    ]
    assert [
        page["raster_manifest_hash"]
        for page in attempt["document_binding"]["pages"]
    ] == [
        page["raster_manifest"]["manifest_hash"] for page in pages
    ]


def test_critic_is_one_call_and_existing_attempt_lineage_is_preserved() -> None:
    pages = _page_images()
    first = {"pages": [{"tables": []}, {"tables": []}]}
    reviewed = {
        "pages": [
            {"tables": []},
            {"tables": [_table([100, 100, 600, 900])]},
        ]
    }
    transport = _Transport(reviewed)
    adapter = _adapter(transport)

    result = adapter.invoke_document_visual_geometry(
        task_id="document_visual_critic",
        phase="CRITIC",
        page_images=pages,
        first_geometry_proposal=first,
        attempt_number=2,
        attempt_lineage=["document_visual_critic_a1"],
    )

    assert len(transport.requests) == 2
    body = json.loads(transport.requests[1].data.decode("utf-8"))
    model_view = json.loads(body["contents"][0]["parts"][0]["text"])
    assert model_view["first_geometry_proposal"] == first
    assert model_view["phase"] == "CRITIC"
    assert result["json_output"] == reviewed
    assert result["attempt"]["attempt_number"] == 2
    assert result["attempt"]["attempt_lineage"] == [
        "document_visual_critic_a1"
    ]
    assert result["attempt"]["provider_calls"] == 2
    assert result["attempt"]["provider_http_calls"] == 2
    assert result["attempt"]["model_generation_calls"] == 1
    assert result["attempt"]["hidden_retry"] is False

    rejected = _Transport(reviewed)
    with pytest.raises(PdfTableLocatorProviderError) as raised:
        _adapter(rejected).invoke_document_visual_geometry(
            task_id="document_visual_critic",
            phase="CRITIC",
            page_images=pages,
            first_geometry_proposal=first,
            attempt_number=2,
            attempt_lineage=[],
        )
    assert raised.value.code == "pdf_grid_attempt_lineage_invalid"
    assert rejected.requests == []


def test_response_is_closed_and_terminal_before_public_json() -> None:
    pages = _page_images()
    invalid_values = [
        {"pages": [{"tables": []}]},
        {
            "pages": [
                {"tables": []},
                {"tables": []},
                {"tables": []},
            ]
        },
        {
            "pages": [
                {"tables": [{**_table([50, 40, 300, 900]), "text": "bad"}]},
                {"tables": []},
            ]
        },
    ]
    for value in invalid_values:
        transport = _Transport(value)
        result = _adapter(transport).invoke_document_visual_geometry(
            task_id="document_visual_invalid",
            phase="PROPOSAL",
            page_images=pages,
            first_geometry_proposal=None,
            attempt_number=1,
            attempt_lineage=[],
        )
        assert len(transport.requests) == 2
        assert result["json_output"] is None
        assert result["attempt"]["parse_result"] == (
            "parsed_object_schema_invalid"
        )
        assert result["attempt"]["terminal_failure_class"] == (
            "provider_invalid_json"
        )


def test_nonterminal_response_has_one_preflight_and_one_generation_no_retry() -> None:
    transport = _Transport(
        {"pages": [{"tables": []}, {"tables": []}]},
        finish_reason="MAX_TOKENS",
    )

    result = _adapter(transport).invoke_document_visual_geometry(
        task_id="document_visual_nonterminal",
        phase="PROPOSAL",
        page_images=_page_images(),
        first_geometry_proposal=None,
        attempt_number=1,
        attempt_lineage=[],
    )

    assert len(transport.requests) == 2
    assert result["json_output"] is None
    assert result["attempt"]["finish_reason"] == "MAX_TOKENS"
    assert result["attempt"]["terminal_failure_class"] == "response_budget"
    assert result["attempt"]["provider_calls"] == 2
    assert result["attempt"]["provider_http_calls"] == 2
    assert result["attempt"]["model_generation_calls"] == 1
    assert result["attempt"]["hidden_retry"] is False


def test_actual_inline_request_over_twenty_mb_fails_before_http() -> None:
    pages = _page_images()
    oversized = pages[0]["png_bytes"] + b"\0" * (16 * 1024 * 1024)
    pages[0]["png_bytes"] = oversized
    manifest = pages[0]["raster_manifest"]
    manifest["png_sha256"] = hashlib.sha256(oversized).hexdigest()
    manifest["png_bytes"] = len(oversized)
    unhashed = copy.deepcopy(manifest)
    unhashed.pop("manifest_hash")
    manifest["manifest_hash"] = sha256_json(unhashed)
    transport = _Transport({"pages": [{"tables": []}, {"tables": []}]})

    with pytest.raises(PdfTableLocatorProviderError) as raised:
        _adapter(transport).invoke_document_visual_geometry(
            task_id="document_visual_oversized",
            phase="PROPOSAL",
            page_images=pages,
            first_geometry_proposal=None,
            attempt_number=1,
            attempt_lineage=[],
        )

    assert raised.value.code == "pdf_document_visual_request_budget_exceeded"
    assert raised.value.failure_class == "context_budget"
    assert raised.value.safe_details["generation_request_bytes"] >= 20 * 1024 * 1024
    assert raised.value.safe_details["provider_http_calls"] == 0
    assert raised.value.safe_details["model_generation_calls"] == 0
    assert transport.requests == []


def test_counted_token_budget_blocks_generation_after_one_http_call() -> None:
    transport = _Transport(
        {"pages": [{"tables": []}, {"tables": []}]},
        count_total=1001,
    )

    with pytest.raises(PdfTableLocatorProviderError) as raised:
        _adapter(transport).invoke_document_visual_geometry(
            task_id="document_visual_token_budget",
            phase="PROPOSAL",
            page_images=_page_images(),
            first_geometry_proposal=None,
            attempt_number=1,
            attempt_lineage=[],
        )

    assert raised.value.code == "pdf_grid_provider_counted_input_budget_exceeded"
    assert raised.value.failure_class == "context_budget"
    assert raised.value.safe_details == {
        "observed_total_tokens": 1001,
        "maximum_counted_input_tokens": 1000,
        "provider_http_calls": 1,
        "model_generation_calls": 0,
    }
    assert len(transport.requests) == 1
    assert transport.requests[0].full_url.endswith(":countTokens")


def test_real_raster_identity_mutations_fail_before_transport() -> None:
    pages = _page_images()
    cases = []
    changed_png = copy.deepcopy(pages)
    changed_png[0]["png_bytes"] += b"x"
    cases.append(changed_png)
    swapped = list(reversed(copy.deepcopy(pages)))
    cases.append(swapped)
    stale_manifest = copy.deepcopy(pages)
    stale_manifest[0]["raster_manifest"]["page_ref"] = "foreign-page"
    cases.append(stale_manifest)
    foreign_document = copy.deepcopy(pages)
    foreign_document[1]["raster_manifest"]["document_ref"] = "foreign-document"
    cases.append(foreign_document)

    for mutated in cases:
        transport = _Transport({"pages": [{"tables": []}, {"tables": []}]})
        with pytest.raises(PdfTableLocatorProviderError):
            _adapter(transport).invoke_document_visual_geometry(
                task_id="document_visual_mutated",
                phase="PROPOSAL",
                page_images=mutated,
                first_geometry_proposal=None,
                attempt_number=1,
                attempt_lineage=[],
            )
        assert transport.requests == []


def test_existing_single_page_request_shape_is_unchanged() -> None:
    value = {"tables": []}
    transport = _Transport(value)
    adapter = _adapter(transport)
    png = b"single-page-png"
    model_view = {"task": "existing single page"}
    output_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["tables"],
        "properties": {"tables": {"type": "array", "maxItems": 1}},
    }

    result = adapter.invoke(
        task_id="single_page",
        model_view=model_view,
        output_schema=output_schema,
        png_bytes=png,
        crop_sha256=hashlib.sha256(png).hexdigest(),
        attempt_number=1,
        attempt_lineage=[],
    )

    assert len(transport.requests) == 1
    body = json.loads(transport.requests[0].data.decode("utf-8"))
    parts = body["contents"][0]["parts"]
    assert parts == [
        {"text": json.dumps(model_view, separators=(",", ":"), sort_keys=True)},
        {
            "inlineData": {
                "mimeType": "image/png",
                "data": base64.b64encode(png).decode("ascii"),
            }
        },
    ]
    assert body["generationConfig"]["candidateCount"] == 1
    assert "maxItems" not in body["generationConfig"]["responseJsonSchema"][
        "properties"
    ]["tables"]
    assert result["json_output"] == value
    assert result["attempt"]["transport_identity"] == (
        "gemini_generate_content_native_table_crop_json_schema"
    )
    assert "document_binding" not in result["attempt"]


def test_provider_seam_is_factory_routed_closed_world_and_product_inactive() -> None:
    provider_source = (PACKAGE / "pdf_table_locator_provider.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(provider_source)
    external_imports = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.level == 0
        and isinstance(node.module, str)
    }
    assert external_imports <= {
        "__future__",
        "dataclasses",
        "datetime",
        "typing",
        "urllib",
    }
    assert "open_webui" not in provider_source
    assert "PdfTableLocatorProviderFactory" in DOCUMENT_VISUAL_FACTORY_REQUIRED
    assert "no product call site" in DOCUMENT_VISUAL_FORBIDDEN
    for path in PACKAGE.glob("*.py"):
        if path.name == "pdf_table_locator_provider.py":
            continue
        assert ".invoke_document_visual_geometry(" not in path.read_text(
            encoding="utf-8"
        )
    intake_source = (PACKAGE / "pdf_table_intake_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "invoke_document_visual_geometry" not in intake_source


def _table(box: list[int]) -> dict[str, Any]:
    return {
        "table_box_2d": box,
        "title_status": "ABSENT",
        "title_boxes_2d": [],
        "header_status": "UNCERTAIN",
        "header_boxes_2d": [],
        "body_status": "UNCERTAIN",
        "body_anchor_boxes_2d": [],
    }


def _page_images() -> list[dict[str, Any]]:
    import fitz

    document = fitz.open()
    for page_number in (1, 2):
        page = document.new_page(width=300, height=400)
        page.insert_text((30, 50), f"Page {page_number}")
    try:
        pdf_bytes = document.tobytes()
    finally:
        document.close()
    pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    renderer = PdfTableRasterFactory().create()
    pages = []
    for page_number in (1, 2):
        rendered = renderer.render_full_page(
            pdf_bytes=pdf_bytes,
            pdf_sha256=pdf_sha256,
            document_ref="document-visual-provider",
            page_ref=f"page-ref-{page_number}",
            page_number=page_number,
            expected_page_bbox=[0.0, 0.0, 300.0, 400.0],
            dpi=150,
        )
        pages.append(
            {
                "png_bytes": base64.b64decode(
                    rendered["private_png_base64"].encode("ascii"), validate=True
                ),
                "raster_manifest": rendered["manifest"],
            }
        )
    return pages


def _adapter(transport: "_Transport"):
    return PdfTableLocatorProviderFactory(
        PdfTableLocatorProviderConfig(maximum_counted_input_tokens=1000),
        urlopen_fn=transport,
    ).create_with_connection(
        Gate2OpenWebUIProviderConnection(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key="secret",
        )
    )


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.status = 200
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit: int) -> bytes:
        return self._body


class _Transport:
    def __init__(
        self,
        value: dict[str, Any],
        *,
        finish_reason: str = "STOP",
        count_total: int = 100,
    ) -> None:
        self.value = value
        self.finish_reason = finish_reason
        self.count_total = count_total
        self.requests = []

    def __call__(self, request, timeout: int):
        assert timeout == 240
        self.requests.append(request)
        if request.full_url.endswith(":countTokens"):
            return _Response(
                {
                    "totalTokens": self.count_total,
                    "promptTokensDetails": [
                        {"modality": "IMAGE", "tokenCount": self.count_total}
                    ],
                }
            )
        return _Response(
            {
                "responseId": "document-visual-response",
                "modelVersion": "models/gemini-3.5-flash",
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        self.value,
                                        separators=(",", ":"),
                                        sort_keys=True,
                                    )
                                }
                            ]
                        },
                        "finishReason": self.finish_reason,
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 100,
                    "candidatesTokenCount": 20,
                    "totalTokenCount": 120,
                },
            }
        )
