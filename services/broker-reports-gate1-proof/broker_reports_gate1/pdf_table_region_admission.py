"""Strict admission contract for already-located PDF regions.

This module owns only the TABLE/PROSE/AMBIGUOUS decision boundary.  It does
not locate regions, recover table structure, or activate any product route.
"""

from __future__ import annotations

import copy
import math
import weakref
from dataclasses import dataclass
from typing import Any

from .contracts import sha256_json


PDF_TABLE_REGION_ADMISSION_REQUEST_SCHEMA = (
    "broker_reports_pdf_table_region_admission_request_v1"
)
PDF_TABLE_REGION_ADMISSION_RESPONSE_SCHEMA = (
    "broker_reports_pdf_table_region_admission_response_v1"
)
PDF_TABLE_REGION_ADMISSION_RECEIPT_SCHEMA = (
    "broker_reports_pdf_table_region_admission_receipt_v1"
)
_DECISIONS = frozenset({"TABLE", "PROSE", "AMBIGUOUS"})


class PdfTableRegionAdmissionError(RuntimeError):
    """The admission boundary is incomplete, foreign, or internally invalid."""


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ValidatedTableRegionAdmission:
    source_pdf_sha256: str
    page_number: int
    region_ref: str
    bbox_pdf_points: tuple[float, float, float, float]
    region_set_checksum: str
    decision_checksum: str
    response_checksum: str
    receipt_checksum: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PDF_TABLE_REGION_ADMISSION_RECEIPT_SCHEMA,
            "source_pdf_sha256": self.source_pdf_sha256,
            "page_number": self.page_number,
            "region_ref": self.region_ref,
            "bbox_pdf_points": list(self.bbox_pdf_points),
            "region_set_checksum": self.region_set_checksum,
            "decision_checksum": self.decision_checksum,
            "response_checksum": self.response_checksum,
            "receipt_checksum": self.receipt_checksum,
        }


def _identity_registry():
    entries: dict[
        int, tuple[weakref.ReferenceType[ValidatedTableRegionAdmission], str]
    ] = {}

    def register(value: ValidatedTableRegionAdmission, fingerprint: str) -> None:
        identity = id(value)

        def cleanup(reference: weakref.ReferenceType[ValidatedTableRegionAdmission]) -> None:
            current = entries.get(identity)
            if current is not None and current[0] is reference:
                entries.pop(identity, None)

        reference = weakref.ref(value, cleanup)
        entries[identity] = (reference, fingerprint)

    def fingerprint(value: object) -> str | None:
        entry = entries.get(id(value))
        if entry is None or entry[0]() is not value:
            return None
        return entry[1]

    return register, fingerprint


_register_validated, _registered_fingerprint = _identity_registry()


def build_region_admission_request(
    *, source_pdf_sha256: str, page_number: int, regions: list[dict[str, Any]]
) -> dict[str, Any]:
    if (
        not isinstance(source_pdf_sha256, str)
        or len(source_pdf_sha256) != 64
        or any(character not in "0123456789abcdef" for character in source_pdf_sha256)
    ):
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_scope_invalid")
    if not isinstance(page_number, int) or isinstance(page_number, bool) or page_number < 1:
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_scope_invalid")
    if not isinstance(regions, list):
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_scope_invalid")
    manifest: list[dict[str, Any]] = []
    for region in regions:
        if not isinstance(region, dict) or set(region) != {
            "region_ref",
            "bbox_pdf_points",
        }:
            raise PdfTableRegionAdmissionError("pdf_table_region_admission_scope_invalid")
        region_ref = region.get("region_ref")
        bbox = _bbox(region.get("bbox_pdf_points"))
        if not isinstance(region_ref, str) or not region_ref.strip() or bbox is None:
            raise PdfTableRegionAdmissionError("pdf_table_region_admission_scope_invalid")
        manifest.append({"region_ref": region_ref, "bbox_pdf_points": list(bbox)})
    refs = [item["region_ref"] for item in manifest]
    if not refs or len(refs) != len(set(refs)):
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_scope_invalid")
    scope = {
        "source_pdf_sha256": source_pdf_sha256,
        "page_number": page_number,
        "region_refs": refs,
        "region_manifest": manifest,
    }
    return {
        "schema_version": PDF_TABLE_REGION_ADMISSION_REQUEST_SCHEMA,
        **scope,
        "region_set_checksum": sha256_json(scope),
    }


def validate_region_admission_response(
    *, request: dict[str, Any], response: Any
) -> dict[str, Any]:
    _validate_request(request)
    required = {
        "schema_version",
        "source_pdf_sha256",
        "page_number",
        "region_set_checksum",
        "decisions",
        "response_checksum",
    }
    if not isinstance(response, dict) or set(response) != required:
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_response_invalid")
    if (
        response.get("schema_version") != PDF_TABLE_REGION_ADMISSION_RESPONSE_SCHEMA
        or response.get("source_pdf_sha256") != request["source_pdf_sha256"]
        or response.get("page_number") != request["page_number"]
        or response.get("region_set_checksum") != request["region_set_checksum"]
        or not isinstance(response.get("decisions"), list)
    ):
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_response_invalid")
    decisions = response["decisions"]
    if len(decisions) != len(request["region_refs"]):
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_response_invalid")
    for expected_ref, decision in zip(request["region_refs"], decisions, strict=True):
        if (
            not isinstance(decision, dict)
            or set(decision) != {"region_ref", "decision"}
            or decision.get("region_ref") != expected_ref
            or decision.get("decision") not in _DECISIONS
        ):
            raise PdfTableRegionAdmissionError("pdf_table_region_admission_response_invalid")
    unsigned = copy.deepcopy(response)
    checksum = unsigned.pop("response_checksum")
    if not isinstance(checksum, str) or checksum != sha256_json(unsigned):
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_response_invalid")
    return copy.deepcopy(response)


def validate_table_region_admissions(
    *, request: dict[str, Any], response: Any
) -> tuple[ValidatedTableRegionAdmission, ...]:
    validated = validate_region_admission_response(request=request, response=response)
    if any(item["decision"] == "AMBIGUOUS" for item in validated["decisions"]):
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_ambiguous")
    by_ref = {item["region_ref"]: item for item in request["region_manifest"]}
    result = []
    for decision in validated["decisions"]:
        if decision["decision"] != "TABLE":
            continue
        region_ref = decision["region_ref"]
        bbox = tuple(by_ref[region_ref]["bbox_pdf_points"])
        decision_checksum = sha256_json(decision)
        unsigned = {
            "schema_version": PDF_TABLE_REGION_ADMISSION_RECEIPT_SCHEMA,
            "source_pdf_sha256": validated["source_pdf_sha256"],
            "page_number": validated["page_number"],
            "region_ref": region_ref,
            "bbox_pdf_points": list(bbox),
            "region_set_checksum": validated["region_set_checksum"],
            "decision_checksum": decision_checksum,
            "response_checksum": validated["response_checksum"],
        }
        value = ValidatedTableRegionAdmission(
            source_pdf_sha256=validated["source_pdf_sha256"],
            page_number=validated["page_number"],
            region_ref=region_ref,
            bbox_pdf_points=bbox,
            region_set_checksum=validated["region_set_checksum"],
            decision_checksum=decision_checksum,
            response_checksum=validated["response_checksum"],
            receipt_checksum=sha256_json(unsigned),
        )
        _register_validated(value, value.receipt_checksum)
        result.append(value)
    return tuple(result)


def validate_table_region_admission_receipt(
    *,
    receipt: Any,
    request: dict[str, Any],
    response: Any,
    region_ref: str,
) -> ValidatedTableRegionAdmission:
    expected = [
        item
        for item in validate_table_region_admissions(request=request, response=response)
        if item.region_ref == region_ref
    ]
    if len(expected) != 1 or not isinstance(receipt, dict) or receipt != expected[0].to_dict():
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_receipt_invalid")
    return expected[0]


def require_validated_table_region_admission(
    *,
    admission: ValidatedTableRegionAdmission,
    source_pdf_sha256: str,
    page_number: int,
    region_ref: str,
    bbox_pdf_points: list[float] | tuple[float, ...],
    region_set_checksum: str,
) -> ValidatedTableRegionAdmission:
    """Consume an admission minted in this process after full owner validation.

    The identity registry is cooperative architectural authority, not a
    cryptographic defence against hostile code in this process.  After a
    restart the admission owner must revalidate its request and response and
    mint a fresh value; serialized receipts always use the rebind API above.
    """
    bbox = _bbox(bbox_pdf_points)
    current_unsigned = _receipt_unsigned(admission) if isinstance(
        admission, ValidatedTableRegionAdmission
    ) else None
    current_fingerprint = (
        sha256_json(current_unsigned) if current_unsigned is not None else None
    )
    if (
        not isinstance(admission, ValidatedTableRegionAdmission)
        or _registered_fingerprint(admission) != current_fingerprint
        or admission.receipt_checksum != current_fingerprint
        or admission.source_pdf_sha256 != source_pdf_sha256
        or admission.page_number != page_number
        or admission.region_ref != region_ref
        or bbox is None
        or admission.bbox_pdf_points != bbox
        or admission.region_set_checksum != region_set_checksum
    ):
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_receipt_invalid")
    return admission


def _receipt_unsigned(value: ValidatedTableRegionAdmission) -> dict[str, Any]:
    material = value.to_dict()
    material.pop("receipt_checksum")
    return material


def _validate_request(request: Any) -> None:
    required = {
        "schema_version",
        "source_pdf_sha256",
        "page_number",
        "region_refs",
        "region_manifest",
        "region_set_checksum",
    }
    if not isinstance(request, dict) or set(request) != required:
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_request_invalid")
    try:
        rebuilt = build_region_admission_request(
            source_pdf_sha256=request["source_pdf_sha256"],
            page_number=request["page_number"],
            regions=request["region_manifest"],
        )
    except (KeyError, TypeError, PdfTableRegionAdmissionError) as exc:
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_request_invalid") from exc
    if rebuilt != request:
        raise PdfTableRegionAdmissionError("pdf_table_region_admission_request_invalid")


def _bbox(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        return None
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        return None
    left, top, right, bottom = result
    return result if left < right and top < bottom else None
