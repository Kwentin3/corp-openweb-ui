from __future__ import annotations

import copy
import hashlib
import math
from dataclasses import replace
from functools import lru_cache

import pytest

import broker_reports_gate1.source_bound_table_scope as scope_module
from broker_reports_gate1.full_source import FullSourceArtifactFactory
from broker_reports_gate1.pdf_table_raster import PdfTableRasterFactory
from broker_reports_gate1.source_bound_table_scope import (
    FORBIDDEN,
    SOURCE_BOUND_TABLE_SCOPE_PROPOSAL_SCHEMA,
    SourceBoundTableScopeError,
    SourceBoundTableScopeFactory,
    proposal_schema,
)
from tests.test_broker_reports_pdf_layout_slice2 import _ruled_table_pdf


PDF_BYTES = _ruled_table_pdf()
SOURCE_SHA256 = hashlib.sha256(PDF_BYTES).hexdigest()


@lru_cache(maxsize=1)
def _full_source_payload() -> dict:
    result = FullSourceArtifactFactory().create().build(
        normalization_run_id="normrun_source_bound_scope",
        document_id="brdoc_source_bound_scope",
        profile_id="techprof_source_bound_scope",
        container_format="pdf",
        content_bytes=PDF_BYTES,
        source_checksum_sha256=SOURCE_SHA256,
    )
    assert result.summary["parser_completeness_status"] == "complete"
    assert result.summary["pdf_layout_projection_status"] == "complete"
    return result.payloads[0]


def _projection(payload: dict | None = None) -> dict:
    return (payload or _full_source_payload())["pdf_text_layer_projection"]


def _page(payload: dict | None = None) -> dict:
    return _projection(payload)["page_inventory"][0]


@lru_cache(maxsize=1)
def _owned_raster_manifest() -> dict:
    payload = _full_source_payload()
    page = _page(payload)
    width = float(page["layout_page_width"])
    height = float(page["layout_page_height"])
    rendered = PdfTableRasterFactory().create().render_full_page(
        pdf_bytes=PDF_BYTES,
        pdf_sha256=SOURCE_SHA256,
        document_ref=payload["document_ref"],
        page_ref=page["page_ref"],
        page_number=page["page_number"],
        expected_page_bbox=[0.0, 0.0, width, height],
        dpi=150,
    )
    return rendered["manifest"]


def _raster_manifest(payload: dict | None = None) -> dict:
    assert (
        payload is None
        or payload["document_ref"] == _full_source_payload()["document_ref"]
    )
    return copy.deepcopy(_owned_raster_manifest())


def _word_refs_by_text(payload: dict, texts: set[str]) -> list[str]:
    return [
        word["word_ref"]
        for word in _projection(payload)["word_inventory"]
        if word["text"] in texts
    ]


def _normalized_box(payload: dict, refs: list[str]) -> list[int]:
    projection = _projection(payload)
    bbox_by_ref = {
        item["bbox_ref"]: item["bbox"] for item in projection["bbox_inventory"]
    }
    word_by_ref = {item["word_ref"]: item for item in projection["word_inventory"]}
    boxes = [bbox_by_ref[word_by_ref[ref]["bbox_ref"]] for ref in refs]
    page = _page(payload)
    width = float(page["layout_page_width"])
    height = float(page["layout_page_height"])
    x0 = min(float(box[0]) for box in boxes)
    top = min(float(box[1]) for box in boxes)
    x1 = max(float(box[2]) for box in boxes)
    bottom = max(float(box[3]) for box in boxes)
    return [
        max(0, math.floor(top * 1000 / height) - 2),
        max(0, math.floor(x0 * 1000 / width) - 2),
        min(1000, math.ceil(bottom * 1000 / height) + 2),
        min(1000, math.ceil(x1 * 1000 / width) + 2),
    ]


def _proposal(*, body_status: str = "HAS_DATA", payload: dict | None = None) -> dict:
    payload = payload or _full_source_payload()
    candidate_refs = _projection(payload)["table_candidate_inventory"][0][
        "contributing_word_refs"
    ]
    title_refs = _word_refs_by_text(payload, {"Synthetic", "Table"})
    return {
        "schema_version": SOURCE_BOUND_TABLE_SCOPE_PROPOSAL_SCHEMA,
        "tables": [
            {
                "title_status": "PRESENT",
                "title_boxes_2d": [_normalized_box(payload, title_refs)],
                "header_status": "PRESENT",
                "header_boxes_2d": [_normalized_box(payload, candidate_refs[:3])],
                "body_status": body_status,
                "body_anchor_boxes_2d": (
                    []
                    if body_status == "EMPTY_TEMPLATE"
                    else [_normalized_box(payload, candidate_refs[3:6])]
                ),
            }
        ],
    }


def _bind(
    *,
    proposal: dict | None = None,
    payload: dict | None = None,
    raster_manifest: dict | None = None,
    source_sha256: str = SOURCE_SHA256,
):
    payload = payload or _full_source_payload()
    page = _page(payload)
    return SourceBoundTableScopeFactory().create().bind(
        proposal=proposal or _proposal(payload=payload),
        full_source_payload=payload,
        source_checksum_sha256=source_sha256,
        page_ref=page["page_ref"],
        page_number=page["page_number"],
        raster_manifest=raster_manifest or _raster_manifest(payload),
    )


def test_binds_geometry_to_one_existing_candidate_and_exact_fullsource_refs() -> None:
    payload = _full_source_payload()
    candidate = _projection(payload)["table_candidate_inventory"][0]
    candidate_refs = candidate["contributing_word_refs"]
    title_refs = _word_refs_by_text(payload, {"Synthetic", "Table"})
    result = _bind(payload=payload)
    scope = result.scopes[0]

    assert scope.binding_status == "BOUND"
    assert scope.locator_candidate_ref == candidate["table_candidate_ref"]
    assert scope.title_word_refs == tuple(title_refs)
    assert scope.header_word_ref_groups == (tuple(candidate_refs[:3]),)
    assert scope.body_anchor_word_refs == tuple(candidate_refs[3:6])
    assert scope.body_word_refs == tuple(candidate_refs[3:])
    assert set(scope.scope_word_refs) == {*title_refs, *candidate_refs}
    assert result.as_dict()["model_literals_used_as_source_values"] is False
    assert result.as_dict()["downstream_authority"] is False
    assert "authoritative_structure" not in scope.as_dict()
    assert result.proposal_sha256 == scope.proposal_sha256


def test_receipt_cannot_be_upgraded_to_downstream_authority() -> None:
    result = _bind(proposal=_proposal(body_status="EMPTY_TEMPLATE"))
    assert result.scopes[0].binding_status == "PARTIAL"
    forged = replace(result.scopes[0], binding_status="BOUND", issue_codes=())

    assert "authoritative_structure" not in forged.as_dict()
    assert result.as_dict()["downstream_authority"] is False
    assert not hasattr(scope_module, "source_bound_table_scope_ref")


def test_rejects_source_sha_not_bound_to_validated_fullsource_payload() -> None:
    with pytest.raises(
        SourceBoundTableScopeError,
        match="source_bound_table_scope_source_binding_mismatch",
    ):
        _bind(source_sha256="c" * 64)


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("pdf_sha256", "c" * 64),
        ("document_ref", "other_document"),
        ("page_ref", "other_page"),
        ("page_number", 2),
    ],
)
def test_rejects_raster_artifact_from_other_source_or_page(
    field: str, replacement: object
) -> None:
    manifest = _raster_manifest()
    manifest[field] = replacement

    with pytest.raises(
        SourceBoundTableScopeError,
        match="source_bound_table_scope_source_binding_mismatch",
    ):
        _bind(raster_manifest=manifest)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda projection: projection.update({"schema_version": "other_projection"}),
        lambda projection: projection["bbox_inventory"].append(
            copy.deepcopy(projection["bbox_inventory"][0])
        ),
        lambda projection: projection["table_candidate_inventory"].append(
            copy.deepcopy(projection["table_candidate_inventory"][0])
        ),
        lambda projection: projection["word_inventory"][0].update(
            {"page_ref": "foreign_page"}
        ),
        lambda projection: projection["table_candidate_inventory"][0][
            "contributing_word_refs"
        ].append("word_unknown"),
    ],
)
def test_rejects_mutated_or_foreign_fullsource_projection(mutation) -> None:
    payload = copy.deepcopy(_full_source_payload())
    mutation(_projection(payload))

    with pytest.raises(SourceBoundTableScopeError):
        _bind(payload=payload)


def test_rejects_cross_role_word_overlap() -> None:
    proposal = _proposal()
    proposal["tables"][0]["title_boxes_2d"] = copy.deepcopy(
        proposal["tables"][0]["header_boxes_2d"]
    )

    with pytest.raises(
        SourceBoundTableScopeError,
        match="source_bound_table_scope_cross_role_overlap",
    ):
        _bind(proposal=proposal)


def test_rejects_cross_table_word_overlap() -> None:
    proposal = _proposal()
    proposal["tables"].append(copy.deepcopy(proposal["tables"][0]))

    with pytest.raises(
        SourceBoundTableScopeError,
        match="source_bound_table_scope_cross_table_overlap",
    ):
        _bind(proposal=proposal)


def test_geometry_mutation_changes_host_owned_proposal_hash() -> None:
    before = _bind()
    proposal = _proposal()
    proposal["tables"][0]["body_anchor_boxes_2d"][0][3] += 1
    after = _bind(proposal=proposal)

    assert before.proposal_sha256 != after.proposal_sha256


@pytest.mark.parametrize(
    ("path", "replacement"),
    [
        (("page_rotation",), 90),
        (("silent_resize_performed",), True),
        (("source_to_pixel_transform", "scale_x"), 1.0),
        (("rendered_bbox",), [0.0, 0.0, 319.0, 320.0]),
    ],
)
def test_rejects_unowned_raster_coordinate_transform(
    path: tuple[str, ...], replacement: object
) -> None:
    manifest = _raster_manifest()
    target = manifest
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replacement

    with pytest.raises(
        SourceBoundTableScopeError,
        match="source_bound_table_scope_raster_manifest_invalid",
    ):
        _bind(raster_manifest=manifest)


def test_rejects_raster_page_dimensions_not_owned_by_fullsource_page() -> None:
    manifest = _raster_manifest()
    manifest["actual_page_bbox"] = [0.0, 0.0, 321.0, 320.0]
    manifest["rendered_bbox"] = [0.0, 0.0, 321.0, 320.0]
    manifest["source_to_pixel_transform"]["scale_x"] = manifest["width"] / 321

    with pytest.raises(
        SourceBoundTableScopeError,
        match="source_bound_table_scope_raster_page_mismatch",
    ):
        _bind(raster_manifest=manifest)


def test_legacy_scope_keeps_exact_page_dimension_tolerance() -> None:
    manifest = _raster_manifest()
    manifest["actual_page_bbox"] = [0.0, 0.0, 320.00005, 320.0]
    manifest["rendered_bbox"] = [0.0, 0.0, 320.00005, 320.0]
    manifest["source_to_pixel_transform"]["scale_x"] = (
        manifest["width"] / 320.00005
    )

    with pytest.raises(
        SourceBoundTableScopeError,
        match="source_bound_table_scope_raster_page_mismatch",
    ):
        _bind(raster_manifest=manifest)


@pytest.mark.parametrize(
    ("body_status", "issue_code"),
    [
        ("EMPTY_TEMPLATE", "source_bound_table_scope_empty_template_partial"),
        ("EXPLAINER", "source_bound_table_scope_explainer_non_authoritative"),
    ],
)
def test_empty_and_explainer_are_retained_non_authoritative(
    body_status: str, issue_code: str
) -> None:
    result = _bind(proposal=_proposal(body_status=body_status))
    scope = result.scopes[0]

    assert scope.binding_status == "PARTIAL"
    assert issue_code in scope.issue_codes
    assert scope.title_word_refs
    assert result.as_dict()["downstream_authority"] is False
    if body_status == "EXPLAINER":
        assert scope.body_word_refs
        assert scope.scope_word_refs


def test_contract_is_closed_geometry_only_and_does_not_mutate_inputs() -> None:
    proposal = _proposal()
    payload = copy.deepcopy(_full_source_payload())
    manifest = _raster_manifest(payload)
    original_proposal = copy.deepcopy(proposal)
    original_payload = copy.deepcopy(payload)
    original_manifest = copy.deepcopy(manifest)

    _bind(proposal=proposal, payload=payload, raster_manifest=manifest)
    serialized = repr(proposal_schema()).lower()

    assert proposal == original_proposal
    assert payload == original_payload
    assert manifest == original_manifest
    assert "source_binding" not in serialized
    assert "title_text" not in serialized
    assert "header_text" not in serialized
    assert "table_id" not in serialized
    assert "body_anchor_boxes_2d" in serialized
    assert FORBIDDEN.startswith("inactive only")
