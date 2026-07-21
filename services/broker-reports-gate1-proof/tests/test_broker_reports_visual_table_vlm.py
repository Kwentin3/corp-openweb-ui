from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from io import BytesIO
from typing import Any

import pytest
from PIL import Image

from broker_reports_gate1.visual_table_vlm import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PRODUCTION_VISUAL_PROVIDER_PROFILE_IDS,
    VisualTableProviderAdapterFactory,
    VisualTableProviderBoundaryError,
    VisualTableRecoveryConfig,
    VisualTableRecoveryFactory,
    VisualTableRecoveryRuntime,
    VisualTableRuntimeError,
    visual_provider_profile,
)
from broker_reports_gate1.visual_table_vlm_contracts import (
    VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION,
    VISUAL_TABLE_SCOPE_SCHEMA_VERSION,
    VISUAL_TABLE_TERMINAL_RESULTS,
    VisualTableContractConfig,
    sha256_json,
    visual_table_proposal_json_schema,
)


def _raster_bytes(*, image_format: str, width: int, height: int) -> bytes:
    output = BytesIO()
    with Image.new("RGB", (width, height), color=(248, 248, 248)) as raster:
        raster.save(output, format=image_format)
    encoded = output.getvalue()
    with Image.open(BytesIO(encoded)) as decoded:
        decoded.load()
        assert decoded.size == (width, height)
        assert decoded.format == image_format
    return encoded


IMAGE_BYTES = _raster_bytes(image_format="PNG", width=1000, height=1400)
CROP_IMAGE_BYTES = _raster_bytes(image_format="PNG", width=400, height=300)
JPEG_IMAGE_BYTES = _raster_bytes(image_format="JPEG", width=320, height=240)


class DeterministicCompletionBoundary:
    """Deterministic external boundary; production logic remains unmodified."""

    def __init__(self, response: dict[str, Any] | bytes | str | Exception) -> None:
        self.response = response
        self.requests = []
        self.raw_response: bytes | str | None = None

    def complete(self, request):
        self.requests.append(request)
        if isinstance(self.response, Exception):
            raise self.response
        response = copy.deepcopy(self.response)
        if isinstance(response, dict):
            response["request_ref"] = request.request_ref
            self.raw_response = json.dumps(
                response,
                ensure_ascii=False,
                sort_keys=False,
            ).encode("utf-8")
            return self.raw_response
        self.raw_response = response
        return response


class RawJsonCompletionBoundary:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.requests = []
        self.raw_response: bytes | None = None

    def complete(self, request):
        self.requests.append(request)
        response = copy.deepcopy(self.response)
        response["request_ref"] = request.request_ref
        self.raw_response = json.dumps(
            response,
            ensure_ascii=False,
            sort_keys=False,
            indent=2,
        ).encode("utf-8")
        return self.raw_response


def _region(
    ref: str,
    bbox: list[float],
    *,
    material: bool = True,
    deterministic_text: str | None = None,
) -> dict:
    region = {
        "source_region_ref": ref,
        "normalized_bbox": bbox,
        "segment_sha256": hashlib.sha256(ref.encode("utf-8")).hexdigest(),
        "material": material,
    }
    if deterministic_text is not None:
        region.update(
            deterministic_text=deterministic_text,
            deterministic_text_sha256=hashlib.sha256(
                deterministic_text.encode("utf-8")
            ).hexdigest(),
            deterministic_extractor_ref="pdf_text_layer_literal_v1",
        )
    return region


def _scope(*, inventory: list[dict] | None = None, page_number: int = 7) -> dict:
    return {
        "schema_version": VISUAL_TABLE_SCOPE_SCHEMA_VERSION,
        "scope_kind": "declared_page",
        "source_ref": "private-source-17",
        "document_ref": "document-17",
        "page_number": page_number,
        "region_ref": f"page-{page_number}",
        "declared_region_bbox": [0, 0, 1000, 1400],
        "page_size_pixels": [1000, 1400],
        "image_size_pixels": [1000, 1400],
        "image_sha256": hashlib.sha256(IMAGE_BYTES).hexdigest(),
        "image_mime_type": "image/png",
        "renderer_version": "pdf-renderer-4.2",
        "source_region_inventory": inventory
        or [
            _region("src-h1", [0.15, 0.15, 0.25, 0.20]),
            _region("src-h2", [0.55, 0.15, 0.65, 0.20]),
            _region("src-b1", [0.15, 0.40, 0.25, 0.45]),
            _region("src-b2", [0.55, 0.40, 0.65, 0.45]),
        ],
    }


def _scope_with_deterministic_values() -> dict:
    return _scope(
        inventory=[
            _region(
                "src-h1",
                [0.15, 0.15, 0.25, 0.20],
                deterministic_text="Account",
            ),
            _region(
                "src-h2",
                [0.55, 0.15, 0.65, 0.20],
                deterministic_text="Amount",
            ),
            _region(
                "src-b1",
                [0.15, 0.40, 0.25, 0.45],
                deterministic_text="Cash",
            ),
            _region(
                "src-b2",
                [0.55, 0.40, 0.65, 0.45],
                deterministic_text="100.00",
            ),
        ]
    )


def _base_proposal() -> dict:
    return {
        "schema_version": VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION,
        "request_ref": "filled-by-boundary",
        "layout_status": "supported",
        "detected_table_regions": [
            {
                "table_ref": "table-1",
                "normalized_bbox": [0.10, 0.10, 0.90, 0.90],
                "ordered_rows": [
                    {
                        "row_ref": "row-h",
                        "order": 0,
                        "structural_role": "header",
                    },
                    {
                        "row_ref": "row-b",
                        "order": 1,
                        "structural_role": "body",
                    },
                ],
                "ordered_columns": [
                    {"column_ref": "col-1", "order": 0},
                    {"column_ref": "col-2", "order": 1},
                ],
                "cells": [
                    _cell(
                        "cell-h1",
                        "row-h",
                        "col-1",
                        "Account",
                        [0.10, 0.10, 0.50, 0.30],
                        ["src-h1"],
                    ),
                    _cell(
                        "cell-h2",
                        "row-h",
                        "col-2",
                        "Amount",
                        [0.50, 0.10, 0.90, 0.30],
                        ["src-h2"],
                    ),
                    _cell(
                        "cell-b1",
                        "row-b",
                        "col-1",
                        "Cash",
                        [0.10, 0.30, 0.50, 0.90],
                        ["src-b1"],
                    ),
                    _cell(
                        "cell-b2",
                        "row-b",
                        "col-2",
                        "100.00",
                        [0.50, 0.30, 0.90, 0.90],
                        ["src-b2"],
                    ),
                ],
                "headers": [
                    {
                        "header_cell_ref": "cell-h1",
                        "parent_header_cell_ref": "",
                        "applies_to_column_refs": ["col-1"],
                        "applies_to_cell_refs": ["cell-b1"],
                    },
                    {
                        "header_cell_ref": "cell-h2",
                        "parent_header_cell_ref": "",
                        "applies_to_column_refs": ["col-2"],
                        "applies_to_cell_refs": ["cell-b2"],
                    },
                ],
                "spanning_cells": [],
                "totals": [],
                "continuation_evidence": {
                    "state": "none",
                    "evidence_cell_refs": [],
                    "adjacent_page_numbers": [],
                },
            }
        ],
        "source_region_relationships": [
            _relationship("src-h1", "cell-h1"),
            _relationship("src-h2", "cell-h2"),
            _relationship("src-b1", "cell-b1"),
            _relationship("src-b2", "cell-b2"),
        ],
        "uncertainties": [],
        "omissions": [],
    }


def _cell(
    cell_ref: str,
    row_ref: str,
    column_ref: str,
    text: str,
    bbox: list[float],
    source_refs: list[str],
    *,
    row_span: int = 1,
    column_span: int = 1,
    state: str = "present",
) -> dict:
    return {
        "cell_ref": cell_ref,
        "row_ref": row_ref,
        "column_ref": column_ref,
        "row_span": row_span,
        "column_span": column_span,
        "content_state": state,
        "source_text": text,
        "normalized_bbox": bbox,
        "source_region_refs": source_refs,
    }


def _relationship(source_ref: str, target_ref: str, kind: str = "cell_value") -> dict:
    return {
        "source_region_ref": source_ref,
        "relationship_type": kind,
        "target_ref": target_ref,
    }


def _runtime(
    response,
    *,
    profile_id: str = "google_gemini",
    contract: VisualTableContractConfig | None = None,
):
    boundary = DeterministicCompletionBoundary(response)
    runtime = VisualTableRecoveryFactory(
        adapter_factory=VisualTableProviderAdapterFactory(boundary=boundary),
        config=VisualTableRecoveryConfig(
            profile_id=profile_id,
            model_id="test-vision-model",
            contract=contract or VisualTableContractConfig(),
        ),
    ).create()
    return runtime, boundary


@pytest.mark.parametrize("profile_id", ["google_gemini", "openai_gpt"])
def test_each_production_adapter_requires_review_without_source_value_evidence(
    profile_id: str,
) -> None:
    runtime, boundary = _runtime(_base_proposal(), profile_id=profile_id)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "proposal_requires_review"
    assert result["reason_codes"] == [
        "visual_table_evidence_origin_not_server_authenticated",
        "visual_table_source_value_evidence_required",
    ]
    assert result["provider"]["provider_profile_id"] == profile_id
    assert result["implementation_status"] == (
        "contract_scaffold_not_runtime_integrated"
    )
    assert result["production_integration_claimed"] is False
    assert result["lineage"] == {
        "source_ref": "private-source-17",
        "document_ref": "document-17",
        "page_number": 7,
        "region_ref": "page-7",
        "scope_kind": "declared_page",
        "declared_region_bbox": [0, 0, 1000, 1400],
        "image_sha256": hashlib.sha256(IMAGE_BYTES).hexdigest(),
        "declared_image_sha256": hashlib.sha256(IMAGE_BYTES).hexdigest(),
        "renderer_version": "pdf-renderer-4.2",
        "source_region_inventory_sha256": sha256_json(
            _scope()["source_region_inventory"]
        ),
        "source_regions_total": 4,
    }
    assert result["prompt"]["prompt_id"]
    assert result["prompt"]["prompt_version"] == "v1"
    assert len(result["prompt"]["prompt_sha256"]) == 64
    assert result["output_schema_version"] == VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION
    assert result["validator_version"]
    assert result["whole_document_uploads"] == 0
    assert result["model_canonical_authority"] is False
    assert result["canonical_promotion_performed"] is False
    assert result["provider_confidence_used_as_authority"] is False
    assert result["provider_agreement_used_as_authority"] is False
    assert result["validated_proposal"]["detected_table_regions"]
    assert isinstance(boundary.raw_response, bytes)
    assert (
        result["provider_response_sha256"]
        == hashlib.sha256(boundary.raw_response).hexdigest()
    )
    assert result["provider_response_sha256"] != result["proposal_sha256"]
    assert len(boundary.requests) == 1
    request = boundary.requests[0]
    assert request.wire_payload["store"] is False
    assert request.image_sha256 == hashlib.sha256(IMAGE_BYTES).hexdigest()
    assert request.request_payload_sha256 == sha256_json(request.wire_payload)
    assert request.request_payload_bytes > len(IMAGE_BYTES)
    assert request.response_byte_limit == 4_194_304
    assert result["provider_request_payload_sha256"] == request.request_payload_sha256
    assert result["provider_request_payload_bytes"] == request.request_payload_bytes
    assert result["provider_response_byte_limit"] == request.response_byte_limit
    if profile_id == "google_gemini":
        assert "max_output_tokens" not in request.wire_payload
        assert request.wire_payload["generation_config"]["max_output_tokens"] == (
            131_072
        )
        assert (
            request.wire_payload["response_format"]["mime_type"] == "application/json"
        )
        assert request.wire_payload["input"][0]["type"] == "image"
        assert request.wire_payload["input"][1]["type"] == "text"
        assert "$id" not in request.wire_payload["response_format"]["schema"]
        assert not _contains_schema_key(
            request.wire_payload["response_format"]["schema"],
            {"minLength", "maxLength", "pattern"},
        )
    else:
        assert request.wire_payload["max_output_tokens"] == 131_072
        assert request.wire_payload["text"]["format"]["strict"] is True
        assert request.wire_payload["input"][0]["content"][1]["type"] == "input_image"
        assert "$id" not in request.wire_payload["text"]["format"]["schema"]
    serialized_result = json.dumps(result, ensure_ascii=False)
    assert base64_image_payload() not in serialized_result
    assert "wire_payload" not in serialized_result
    unsigned = dict(result)
    stored_hash = unsigned.pop("result_sha256")
    assert stored_hash == sha256_json(unsigned)


def test_self_asserted_deterministic_source_values_cannot_authorize_acceptance() -> (
    None
):
    runtime, _ = _runtime(_base_proposal())

    result = runtime.recover(
        scope=_scope_with_deterministic_values(), image_bytes=IMAGE_BYTES
    )

    assert result["terminal_result"] == "proposal_requires_review"
    assert result["reason_codes"] == [
        "visual_table_evidence_origin_not_server_authenticated"
    ]
    assert result["acceptance_status"] == (
        "disabled_until_server_authenticated_evidence_binding"
    )
    assert result["canonical_promotion_performed"] is False


def _contains_schema_key(value: Any, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        return bool(set(value) & forbidden) or any(
            _contains_schema_key(item, forbidden) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_schema_key(item, forbidden) for item in value)
    return False


def base64_image_payload() -> str:
    import base64

    return base64.b64encode(IMAGE_BYTES).decode("ascii")


def test_deterministic_validator_proves_spans_totals_and_continuation() -> None:
    inventory = [
        _region("src-header", [0.20, 0.12, 0.40, 0.18]),
        _region("src-b1", [0.15, 0.40, 0.25, 0.45]),
        _region("src-b2", [0.55, 0.40, 0.65, 0.45]),
        _region("src-total-label", [0.15, 0.75, 0.25, 0.80]),
        _region("src-total-value", [0.55, 0.75, 0.65, 0.80]),
    ]
    proposal = _merged_total_proposal()
    runtime, _ = _runtime(proposal)

    result = runtime.recover(scope=_scope(inventory=inventory), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "proposal_requires_review"
    assert "visual_table_continuation_requires_review" in result["reason_codes"]
    assert "visual_table_source_value_evidence_required" in result["reason_codes"]
    table = result["validated_proposal"]["detected_table_regions"][0]
    assert table["spanning_cells"][0]["covered_column_refs"] == ["col-1", "col-2"]
    assert table["totals"][0]["structural_role"] == "total"
    assert table["continuation_evidence"] == {
        "state": "continues_to_next",
        "evidence_cell_refs": ["cell-header"],
        "adjacent_page_numbers": [8],
    }


def test_unresolved_continuation_cannot_claim_adjacent_page_lineage() -> None:
    proposal = _base_proposal()
    proposal["detected_table_regions"][0]["continuation_evidence"] = {
        "state": "unresolved",
        "evidence_cell_refs": [],
        "adjacent_page_numbers": [8],
    }
    runtime, _ = _runtime(proposal)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "proposal_rejected"
    assert "visual_table_continuation_page_lineage_invalid" in result["reason_codes"]


def test_exact_table_crop_is_the_only_non_page_image_scope() -> None:
    runtime, boundary = _runtime(_base_proposal())
    scope = _scope()
    scope.update(
        scope_kind="table_crop",
        region_ref="page-7-table-3",
        declared_region_bbox=[100, 200, 500, 500],
        image_size_pixels=[400, 300],
        image_sha256=hashlib.sha256(CROP_IMAGE_BYTES).hexdigest(),
    )

    result = runtime.recover(scope=scope, image_bytes=CROP_IMAGE_BYTES)

    assert result["terminal_result"] == "proposal_requires_review"
    assert result["lineage"]["scope_kind"] == "table_crop"
    assert result["lineage"]["declared_region_bbox"] == [100, 200, 500, 500]
    assert len(boundary.requests) == 1
    assert boundary.requests[0].wire_payload["store"] is False


def _merged_total_proposal() -> dict:
    cells = [
        _cell(
            "cell-header",
            "row-h",
            "col-1",
            "Statement",
            [0.10, 0.10, 0.90, 0.25],
            ["src-header"],
            column_span=2,
        ),
        _cell(
            "cell-b1",
            "row-b",
            "col-1",
            "Cash",
            [0.10, 0.25, 0.50, 0.65],
            ["src-b1"],
        ),
        _cell(
            "cell-b2",
            "row-b",
            "col-2",
            "100.00",
            [0.50, 0.25, 0.90, 0.65],
            ["src-b2"],
        ),
        _cell(
            "cell-t1",
            "row-t",
            "col-1",
            "Итого",
            [0.10, 0.65, 0.50, 0.90],
            ["src-total-label"],
        ),
        _cell(
            "cell-t2",
            "row-t",
            "col-2",
            "100.00",
            [0.50, 0.65, 0.90, 0.90],
            ["src-total-value"],
        ),
    ]
    relationships = [
        _relationship("src-header", "cell-header"),
        _relationship("src-b1", "cell-b1"),
        _relationship("src-b2", "cell-b2"),
        _relationship("src-total-label", "cell-t1"),
        _relationship("src-total-value", "cell-t2"),
    ]
    return {
        "schema_version": VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION,
        "request_ref": "filled-by-boundary",
        "layout_status": "supported",
        "detected_table_regions": [
            {
                "table_ref": "table-1",
                "normalized_bbox": [0.10, 0.10, 0.90, 0.90],
                "ordered_rows": [
                    {"row_ref": "row-h", "order": 0, "structural_role": "header"},
                    {"row_ref": "row-b", "order": 1, "structural_role": "body"},
                    {"row_ref": "row-t", "order": 2, "structural_role": "total"},
                ],
                "ordered_columns": [
                    {"column_ref": "col-1", "order": 0},
                    {"column_ref": "col-2", "order": 1},
                ],
                "cells": cells,
                "headers": [
                    {
                        "header_cell_ref": "cell-header",
                        "parent_header_cell_ref": "",
                        "applies_to_column_refs": ["col-1", "col-2"],
                        "applies_to_cell_refs": [
                            "cell-b1",
                            "cell-b2",
                            "cell-t1",
                            "cell-t2",
                        ],
                    }
                ],
                "spanning_cells": [
                    {
                        "cell_ref": "cell-header",
                        "row_span": 1,
                        "column_span": 2,
                        "covered_row_refs": ["row-h"],
                        "covered_column_refs": ["col-1", "col-2"],
                    }
                ],
                "totals": [
                    {
                        "row_ref": "row-t",
                        "structural_role": "total",
                        "label_cell_refs": ["cell-t1"],
                        "value_cell_refs": ["cell-t2"],
                    }
                ],
                "continuation_evidence": {
                    "state": "continues_to_next",
                    "evidence_cell_refs": ["cell-header"],
                    "adjacent_page_numbers": [8],
                },
            }
        ],
        "source_region_relationships": relationships,
        "uncertainties": [],
        "omissions": [],
    }


def test_material_omission_and_uncertainty_require_review() -> None:
    proposal = _base_proposal()
    cell = proposal["detected_table_regions"][0]["cells"][3]
    cell.update(
        content_state="empty",
        source_text="",
        source_region_refs=[],
    )
    proposal["omissions"] = [
        {
            "omission_ref": "omission-1",
            "source_region_refs": ["src-b2"],
            "reason_code": "value_not_legible",
            "material": True,
        }
    ]
    proposal["source_region_relationships"][3] = _relationship(
        "src-b2", "omission-1", "omission"
    )
    proposal["uncertainties"] = [
        {
            "uncertainty_ref": "uncertainty-1",
            "subject_ref": "omission-1",
            "code": "material_value_not_legible",
            "material": True,
        }
    ]
    runtime, _ = _runtime(proposal)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "proposal_requires_review"
    assert set(result["reason_codes"]) == {
        "visual_table_evidence_origin_not_server_authenticated",
        "visual_table_empty_cell_requires_review",
        "visual_table_material_omission_requires_review",
        "visual_table_source_value_evidence_required",
        "visual_table_uncertainty_requires_review",
    }


def test_duplicate_source_region_ownership_is_rejected() -> None:
    proposal = _base_proposal()
    proposal["detected_table_regions"][0]["cells"][3]["source_region_refs"].append(
        "src-b1"
    )
    runtime, _ = _runtime(proposal)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "proposal_rejected"
    assert "visual_table_source_region_ownership_duplicate" in result["reason_codes"]
    assert result["canonical_promotion_performed"] is False


def _non_success_proposal(layout_status: str) -> dict[str, Any]:
    source_refs = ["src-h1", "src-h2", "src-b1", "src-b2"]
    return {
        "schema_version": VISUAL_TABLE_PROPOSAL_SCHEMA_VERSION,
        "request_ref": "filled-by-boundary",
        "layout_status": layout_status,
        "detected_table_regions": [],
        "source_region_relationships": [
            _relationship(source_ref, "omission-layout", "omission")
            for source_ref in source_refs
        ],
        "uncertainties": [
            {
                "uncertainty_ref": "uncertainty-layout",
                "subject_ref": "src-h1",
                "code": "layout_cannot_be_resolved",
                "material": True,
            }
        ],
        "omissions": [
            {
                "omission_ref": "omission-layout",
                "source_region_refs": source_refs,
                "reason_code": "layout_cannot_be_resolved",
                "material": True,
            }
        ],
    }


@pytest.mark.parametrize(
    ("mutate", "reason_code"),
    [
        (
            lambda proposal: proposal["detected_table_regions"][0]["ordered_columns"][
                0
            ].update(column_ref="row-h"),
            "visual_table_proposal_identity_duplicate",
        ),
        (
            lambda proposal: proposal["detected_table_regions"][0]["cells"][0].update(
                cell_ref="table-1"
            ),
            "visual_table_cell_identity_duplicate",
        ),
    ],
)
def test_identity_namespaces_cannot_collide(mutate, reason_code: str) -> None:
    proposal = _base_proposal()
    mutate(proposal)
    runtime, _ = _runtime(proposal)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "proposal_rejected"
    assert reason_code in result["reason_codes"]


def test_deterministic_source_value_mismatch_is_rejected() -> None:
    scope = _scope_with_deterministic_values()
    scope["source_region_inventory"][3]["deterministic_text"] = "999.00"
    scope["source_region_inventory"][3]["deterministic_text_sha256"] = hashlib.sha256(
        b"999.00"
    ).hexdigest()
    runtime, _ = _runtime(_base_proposal())

    result = runtime.recover(scope=scope, image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "proposal_rejected"
    assert result["reason_codes"] == ["visual_table_source_value_evidence_mismatch"]


def test_invalid_deterministic_evidence_hash_never_reaches_provider() -> None:
    scope = _scope_with_deterministic_values()
    scope["source_region_inventory"][0]["deterministic_text_sha256"] = "0" * 64
    runtime, boundary = _runtime(_base_proposal())

    result = runtime.recover(scope=scope, image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "unresolved_visual_scope"
    assert result["reason_codes"] == [
        "visual_table_source_value_evidence_hash_mismatch"
    ]
    assert result["provider_calls"] == 0
    assert boundary.requests == []


@pytest.mark.parametrize("forbidden_field", ["confidence", "provider_agreement"])
def test_confidence_or_provider_agreement_cannot_enter_contract_or_authority(
    forbidden_field: str,
) -> None:
    proposal = _base_proposal()
    proposal[forbidden_field] = 1.0
    runtime, _ = _runtime(proposal)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "malformed_provider_output"
    assert result["reason_codes"] == ["visual_table_proposal_shape_invalid"]
    assert result["validated_proposal"] is None
    assert result["canonical_promotion_performed"] is False


def test_provider_strings_are_bounded_before_semantic_validation() -> None:
    proposal = _base_proposal()
    proposal["detected_table_regions"][0]["cells"][0]["source_text"] = "x" * 4_097
    runtime, _ = _runtime(proposal)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "malformed_provider_output"
    assert result["reason_codes"] == ["visual_table_cell_text_type_invalid"]


@pytest.mark.parametrize(
    ("layout_status", "terminal_result"),
    [
        ("unresolved", "unresolved_visual_scope"),
        ("unsupported", "unsupported_visual_layout"),
    ],
)
def test_structured_non_success_layouts_terminate_explicitly(
    layout_status: str, terminal_result: str
) -> None:
    proposal = _non_success_proposal(layout_status)
    runtime, _ = _runtime(proposal)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == terminal_result
    assert result["validated_proposal"] is not None
    assert result["canonical_promotion_performed"] is False


def test_non_success_layout_still_requires_lineage_and_source_accounting() -> None:
    proposal = _non_success_proposal("unsupported")
    proposal["uncertainties"][0]["subject_ref"] = "invented-subject"
    proposal["source_region_relationships"].pop()
    runtime, _ = _runtime(proposal)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "proposal_rejected"
    assert result["validated_proposal"] is None
    assert {
        "visual_table_source_relationships_incomplete",
        "visual_table_uncertainty_subject_unknown",
    } <= set(result["reason_codes"])


def test_invalid_scope_hash_never_crosses_provider_boundary() -> None:
    runtime, boundary = _runtime(_base_proposal())
    scope = _scope()
    scope["image_sha256"] = "0" * 64

    result = runtime.recover(scope=scope, image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "unresolved_visual_scope"
    assert result["reason_codes"] == ["visual_table_scope_image_hash_mismatch"]
    assert result["lineage"]["declared_image_sha256"] == "0" * 64
    assert result["lineage"]["image_sha256"] == hashlib.sha256(IMAGE_BYTES).hexdigest()
    assert result["provider_calls"] == 0
    assert boundary.requests == []


def test_non_raster_payload_never_crosses_provider_boundary() -> None:
    runtime, boundary = _runtime(_base_proposal())
    payload = b"%PDF-1.7 forbidden whole-document payload"
    scope = _scope()
    scope["image_sha256"] = hashlib.sha256(payload).hexdigest()

    result = runtime.recover(scope=scope, image_bytes=payload)

    assert result["terminal_result"] == "unresolved_visual_scope"
    assert result["reason_codes"] == ["visual_table_scope_image_encoding_invalid"]
    assert result["provider_calls"] == 0
    assert boundary.requests == []


def test_truncated_png_with_valid_header_never_crosses_provider_boundary() -> None:
    runtime, boundary = _runtime(_base_proposal())
    truncated = IMAGE_BYTES[: len(IMAGE_BYTES) // 2]
    scope = _scope()
    scope["image_sha256"] = hashlib.sha256(truncated).hexdigest()

    result = runtime.recover(scope=scope, image_bytes=truncated)

    assert result["terminal_result"] == "unresolved_visual_scope"
    assert result["reason_codes"] == ["visual_table_scope_image_encoding_invalid"]
    assert result["provider_calls"] == 0
    assert boundary.requests == []


def test_truncated_jpeg_with_valid_header_never_crosses_provider_boundary() -> None:
    runtime, boundary = _runtime(_base_proposal())
    truncated = JPEG_IMAGE_BYTES[: len(JPEG_IMAGE_BYTES) // 2]
    scope = _scope()
    scope.update(
        declared_region_bbox=[0, 0, 320, 240],
        page_size_pixels=[320, 240],
        image_size_pixels=[320, 240],
        image_sha256=hashlib.sha256(truncated).hexdigest(),
        image_mime_type="image/jpeg",
    )

    result = runtime.recover(scope=scope, image_bytes=truncated)

    assert result["terminal_result"] == "unresolved_visual_scope"
    assert result["reason_codes"] == ["visual_table_scope_image_encoding_invalid"]
    assert result["provider_calls"] == 0
    assert boundary.requests == []


def test_valid_jpeg_is_fully_decoded_before_provider_boundary() -> None:
    runtime, boundary = _runtime(_base_proposal())
    scope = _scope()
    scope.update(
        declared_region_bbox=[0, 0, 320, 240],
        page_size_pixels=[320, 240],
        image_size_pixels=[320, 240],
        image_sha256=hashlib.sha256(JPEG_IMAGE_BYTES).hexdigest(),
        image_mime_type="image/jpeg",
    )

    result = runtime.recover(scope=scope, image_bytes=JPEG_IMAGE_BYTES)

    assert result["terminal_result"] == "proposal_requires_review"
    assert result["provider_calls"] == 1
    assert len(boundary.requests) == 1


def test_pixel_budget_is_terminal_before_provider_boundary() -> None:
    contract = replace(
        VisualTableContractConfig(),
        maximum_image_pixels=1_000_000,
    )
    runtime, boundary = _runtime(_base_proposal(), contract=contract)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "unresolved_visual_scope"
    assert result["reason_codes"] == ["visual_table_scope_image_pixel_budget_exceeded"]
    assert result["provider_calls"] == 0
    assert boundary.requests == []


def test_non_dict_scope_has_typed_terminal_outcome() -> None:
    runtime, boundary = _runtime(_base_proposal())

    result = runtime.recover(scope=["not", "a", "scope"], image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "unresolved_visual_scope"
    assert result["reason_codes"] == ["visual_table_scope_shape_invalid"]
    assert result["lineage"]["source_ref"] is None
    assert result["lineage"]["image_sha256"] == hashlib.sha256(IMAGE_BYTES).hexdigest()
    assert result["provider_calls"] == 0
    assert boundary.requests == []


def test_actual_raw_response_and_image_hashes_are_preserved() -> None:
    boundary = RawJsonCompletionBoundary(_base_proposal())
    runtime = VisualTableRecoveryFactory(
        adapter_factory=VisualTableProviderAdapterFactory(boundary=boundary),
        config=VisualTableRecoveryConfig(
            profile_id="google_gemini",
            model_id="test-vision-model",
        ),
    ).create()

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert boundary.raw_response is not None
    assert (
        result["provider_response_sha256"]
        == hashlib.sha256(boundary.raw_response).hexdigest()
    )
    assert result["provider_response_sha256"] != result["proposal_sha256"]
    assert result["lineage"]["image_sha256"] == hashlib.sha256(IMAGE_BYTES).hexdigest()


def test_request_and_response_budgets_terminate_explicitly() -> None:
    encoded_image_ceiling = 4 * ((len(IMAGE_BYTES) + 2) // 3)
    request_limited = replace(
        VisualTableContractConfig(),
        maximum_image_bytes=len(IMAGE_BYTES),
        maximum_request_bytes=encoded_image_ceiling + 1,
    )
    runtime, boundary = _runtime(_base_proposal(), contract=request_limited)

    request_result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert request_result["terminal_result"] == "unresolved_visual_scope"
    assert request_result["reason_codes"] == [
        "visual_table_provider_request_budget_exceeded"
    ]
    assert request_result["provider_calls"] == 0
    assert boundary.requests == []

    response_limited = replace(
        VisualTableContractConfig(),
        maximum_response_bytes=131_072,
        maximum_output_tokens=65_536,
    )
    runtime, boundary = _runtime(b"x" * 131_073, contract=response_limited)

    response_result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert response_result["terminal_result"] == "malformed_provider_output"
    assert response_result["reason_codes"] == ["visual_table_provider_output_too_large"]
    assert (
        response_result["provider_response_sha256"]
        == hashlib.sha256(b"x" * 131_073).hexdigest()
    )
    assert len(boundary.requests) == 1


def test_expected_provider_boundary_failure_has_terminal_outcome() -> None:
    runtime, boundary = _runtime(
        VisualTableProviderBoundaryError("visual_table_provider_rate_limited")
    )

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "unresolved_visual_scope"
    assert result["reason_codes"] == ["visual_table_provider_rate_limited"]
    assert result["provider_calls"] == 1
    assert len(boundary.requests) == 1


@pytest.mark.parametrize(
    ("failure", "reason_code"),
    [
        (TimeoutError("provider stalled"), "visual_table_provider_timeout"),
        (
            ConnectionError("provider unavailable"),
            "visual_table_provider_connection_failed",
        ),
        (RuntimeError("opaque SDK failure"), "visual_table_provider_boundary_failed"),
    ],
)
def test_generic_provider_failures_are_mapped_to_typed_terminals(
    failure: Exception, reason_code: str
) -> None:
    runtime, boundary = _runtime(failure)

    result = runtime.recover(scope=_scope(), image_bytes=IMAGE_BYTES)

    assert result["terminal_result"] == "unresolved_visual_scope"
    assert result["reason_codes"] == [reason_code]
    assert result["provider_calls"] == 1
    assert len(boundary.requests) == 1


def test_factory_and_schema_guards_prevent_adapter_drift() -> None:
    assert PRODUCTION_VISUAL_PROVIDER_PROFILE_IDS == {
        "google_gemini",
        "openai_gpt",
    }
    assert "VisualTableRecoveryFactory.create" in FACTORY_REQUIRED
    assert "whole document" in FORBIDDEN
    assert "confidence/agreement" in FORBIDDEN
    with pytest.raises(
        VisualTableRuntimeError,
        match="visual_table_provider_profile_not_production",
    ):
        visual_provider_profile("paddle_ocr", model_id="local")

    adapter = VisualTableProviderAdapterFactory(
        boundary=DeterministicCompletionBoundary(_base_proposal())
    ).create(profile_id="google_gemini", model_id="test")
    with pytest.raises(
        VisualTableRuntimeError,
        match="visual_table_recovery_factory_required",
    ):
        VisualTableRecoveryRuntime(  # type: ignore[call-arg]
            adapter=adapter,
            contract=VisualTableRecoveryConfig(
                profile_id="google_gemini", model_id="test"
            ).contract,
        )

    schema = visual_table_proposal_json_schema()
    assert schema["additionalProperties"] is False
    assert "confidence" not in schema["properties"]
    assert "provider_agreement" not in schema["properties"]
    table_properties = schema["properties"]["detected_table_regions"]["items"][
        "properties"
    ]
    assert schema["properties"]["request_ref"]["maxLength"] == 255
    assert table_properties["cells"]["maxItems"] == 4_096
    assert (
        table_properties["cells"]["items"]["properties"]["source_text"]["maxLength"]
        == 4_096
    )
    assert schema["properties"]["uncertainties"]["maxItems"] == 4_096
    assert {
        "ordered_rows",
        "ordered_columns",
        "cells",
        "headers",
        "spanning_cells",
        "totals",
        "continuation_evidence",
    } <= set(table_properties)
    assert {
        "source_region_relationships",
        "uncertainties",
        "omissions",
    } <= set(schema["properties"])
    assert VISUAL_TABLE_TERMINAL_RESULTS == {
        "proposal_validated_and_accepted",
        "proposal_requires_review",
        "proposal_rejected",
        "malformed_provider_output",
        "unresolved_visual_scope",
        "unsupported_visual_layout",
    }
