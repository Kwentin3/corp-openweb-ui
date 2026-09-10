"""Bind provider-proposed physical table links to one Full Source run.

This is provenance plumbing only.  It never merges rows, cells, headers or
Canonical nodes, and it does not call a provider.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .contracts import stable_digest
from .pdf_document_ai import (
    PdfDocumentExtraction,
    PdfSourceContext,
    PdfDocumentTableContinuationAssessment,
    validate_table_continuation_assessment,
)


PHYSICAL_TABLE_CONTINUATION_SCHEMA_VERSION = "physical_table_continuation_v2"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class PhysicalTableContinuationError(ValueError):
    """A proposed relation cannot be bound to this exact Full Source run."""


def proposed_links_from_native_assessment(
    *,
    extraction: PdfDocumentExtraction,
    assessment: PdfDocumentTableContinuationAssessment,
    source_context: PdfSourceContext,
) -> list[dict[str, dict[str, Any]]]:
    """Turn one validated native response into opaque Full Source link inputs."""

    try:
        validate_table_continuation_assessment(
            assessment,
            extraction=extraction,
            source_context=source_context,
        )
    except ValueError as exc:
        raise PhysicalTableContinuationError(
            "physical_table_continuation_assessment_unbound"
        ) from exc
    tables = {item.local_ref: item for item in extraction.table_refs}
    proposals: list[dict[str, dict[str, Any]]] = []
    for link in assessment.links:
        parent = tables.get(link.parent_table_ref)
        child = tables.get(link.child_table_ref)
        if parent is None or child is None:
            raise PhysicalTableContinuationError(
                "physical_table_continuation_assessment_unbound"
            )
        proposals.append(
            {
                "parent": {
                    "native_table_ref": parent.local_ref,
                    "native_table_sha256": parent.sha256,
                    "page_number": parent.page_number,
                },
                "child": {
                    "native_table_ref": child.local_ref,
                    "native_table_sha256": child.sha256,
                    "page_number": child.page_number,
                },
            }
        )
    return proposals


def build_physical_table_continuation_sidecar(
    *,
    normalization_run_id: str,
    document_id: str,
    source_pdf_sha256: str,
    source_units: Sequence[Mapping[str, Any]],
    proposed_links: Sequence[Mapping[str, Any]],
    annotation_receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an append-only, private relation between existing table units.

    Each proposal endpoint is an exact native OCR identity: ``native_table_ref``,
    ``native_table_sha256`` and one-based ``page_number``.  A missing or
    mismatched identity is an error; there is intentionally no shape, header,
    markdown or source-hash-only fallback.
    """

    _require_text(normalization_run_id, "physical_table_continuation_run_invalid")
    _require_text(document_id, "physical_table_continuation_document_invalid")
    _require_sha256(source_pdf_sha256, "physical_table_continuation_source_invalid")
    annotation_receipt = _validated_annotation_receipt(annotation_receipt)
    units_by_native_ref = _eligible_units(
        source_units=source_units,
        normalization_run_id=normalization_run_id,
        document_id=document_id,
        source_pdf_sha256=source_pdf_sha256,
    )
    links: list[dict[str, Any]] = []
    parents: set[str] = set()
    children: set[str] = set()
    for proposal in proposed_links:
        if not isinstance(proposal, Mapping) or set(proposal) != {"parent", "child"}:
            raise PhysicalTableContinuationError("physical_table_continuation_proposal_invalid")
        parent = _resolve_endpoint(proposal["parent"], units_by_native_ref)
        child = _resolve_endpoint(proposal["child"], units_by_native_ref)
        if child["page_number"] != parent["page_number"] + 1:
            raise PhysicalTableContinuationError("physical_table_continuation_pages_not_adjacent")
        if parent["unit_ref"] in parents or child["unit_ref"] in children:
            raise PhysicalTableContinuationError("physical_table_continuation_conflicting_link")
        parents.add(parent["unit_ref"])
        children.add(child["unit_ref"])
        links.append({"parent": parent, "child": child})
    if parents & children:
        raise PhysicalTableContinuationError("physical_table_continuation_cycle")
    material = {
        "schema_version": PHYSICAL_TABLE_CONTINUATION_SCHEMA_VERSION,
        "normalization_run_id": normalization_run_id,
        "document_id": document_id,
        "source_pdf_sha256": source_pdf_sha256,
        "links": links,
        "annotation_receipt": annotation_receipt,
        "visibility": "private_case",
    }
    return {
        **copy.deepcopy(material),
        "sidecar_id": "ptcont_" + stable_digest([material], length=24),
    }


def _validated_annotation_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    """Accept only a body-free receipt for the exact native annotation call."""

    required = {
        "assessment_schema_version",
        "annotation_prompt_sha256",
        "annotation_schema_sha256",
        "request_parameters_sha256",
        "raw_annotation_sha256",
        "selected_page_bindings_sha256",
        "prompt_snapshot",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise PhysicalTableContinuationError(
            "physical_table_continuation_annotation_receipt_invalid"
        )
    for field in (
        "annotation_prompt_sha256",
        "annotation_schema_sha256",
        "request_parameters_sha256",
        "raw_annotation_sha256",
        "selected_page_bindings_sha256",
    ):
        _require_sha256(value.get(field), "physical_table_continuation_annotation_receipt_invalid")
    if not isinstance(value.get("assessment_schema_version"), str) or not value[
        "assessment_schema_version"
    ]:
        raise PhysicalTableContinuationError(
            "physical_table_continuation_annotation_receipt_invalid"
        )
    snapshot = value.get("prompt_snapshot")
    if not isinstance(snapshot, Mapping) or _contains_prompt_body(snapshot):
        raise PhysicalTableContinuationError(
            "physical_table_continuation_annotation_receipt_invalid"
        )
    return copy.deepcopy(dict(value))


def _contains_prompt_body(value: object) -> bool:
    if isinstance(value, Mapping):
        return any(
            key == "content" or _contains_prompt_body(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_prompt_body(item) for item in value)
    return False


def _eligible_units(
    *,
    source_units: Sequence[Mapping[str, Any]],
    normalization_run_id: str,
    document_id: str,
    source_pdf_sha256: str,
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for unit in source_units:
        if not isinstance(unit, Mapping):
            continue
        if (
            unit.get("normalization_run_id") != normalization_run_id
            or unit.get("document_id") != document_id
            or unit.get("source_checksum_sha256") != source_pdf_sha256
        ):
            continue
        native_ref = unit.get("document_ai_native_table_ref")
        if not isinstance(native_ref, str) or not native_ref:
            continue
        if native_ref in result:
            raise PhysicalTableContinuationError("physical_table_continuation_native_ref_ambiguous")
        result[native_ref] = unit
    return result


def _resolve_endpoint(
    endpoint: object, units_by_native_ref: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(endpoint, Mapping) or set(endpoint) != {
        "native_table_ref",
        "native_table_sha256",
        "page_number",
    }:
        raise PhysicalTableContinuationError("physical_table_continuation_endpoint_invalid")
    native_ref = endpoint.get("native_table_ref")
    native_sha256 = endpoint.get("native_table_sha256")
    page_number = endpoint.get("page_number")
    if not isinstance(native_ref, str) or not native_ref:
        raise PhysicalTableContinuationError("physical_table_continuation_native_ref_invalid")
    _require_sha256(native_sha256, "physical_table_continuation_native_sha256_invalid")
    if type(page_number) is not int or page_number < 1:
        raise PhysicalTableContinuationError("physical_table_continuation_page_invalid")
    unit = units_by_native_ref.get(native_ref)
    if unit is None:
        raise PhysicalTableContinuationError("physical_table_continuation_evidence_unbound")
    location = unit.get("source_location")
    if (
        unit.get("document_ai_native_table_sha256") != native_sha256
        or not isinstance(location, Mapping)
        or location.get("page") != page_number
    ):
        raise PhysicalTableContinuationError("physical_table_continuation_evidence_unbound")
    unit_ref = unit.get("unit_ref")
    if not isinstance(unit_ref, str) or not unit_ref:
        raise PhysicalTableContinuationError("physical_table_continuation_unit_invalid")
    return {
        "unit_ref": unit_ref,
        "native_table_ref": native_ref,
        "native_table_sha256": native_sha256,
        "page_number": page_number,
    }


def _require_text(value: object, code: str) -> None:
    if not isinstance(value, str) or not value:
        raise PhysicalTableContinuationError(code)


def _require_sha256(value: object, code: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise PhysicalTableContinuationError(code)
