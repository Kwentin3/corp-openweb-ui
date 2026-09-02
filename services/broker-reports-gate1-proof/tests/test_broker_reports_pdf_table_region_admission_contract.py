from __future__ import annotations

import ast
import copy
import inspect
from dataclasses import replace

import pytest

from broker_reports_gate1.contracts import sha256_json
from broker_reports_gate1.pdf_table_region_admission import (
    PDF_TABLE_REGION_ADMISSION_RESPONSE_SCHEMA,
    PdfTableRegionAdmissionError,
    ValidatedTableRegionAdmission,
    build_region_admission_request,
    require_validated_table_region_admission,
    validate_region_admission_response,
    validate_table_region_admission_receipt,
    validate_table_region_admissions,
)


def _request():
    return build_region_admission_request(
        source_pdf_sha256="a" * 64,
        page_number=2,
        regions=[
            {"region_ref": "r1", "bbox_pdf_points": [1, 2, 30, 40]},
            {"region_ref": "r2", "bbox_pdf_points": [4, 50, 34, 80]},
        ],
    )


def _response(request, *decisions):
    value = {
        "schema_version": PDF_TABLE_REGION_ADMISSION_RESPONSE_SCHEMA,
        "source_pdf_sha256": request["source_pdf_sha256"],
        "page_number": request["page_number"],
        "region_set_checksum": request["region_set_checksum"],
        "decisions": [
            {"region_ref": ref, "decision": decision}
            for ref, decision in zip(request["region_refs"], decisions, strict=True)
        ],
    }
    value["response_checksum"] = sha256_json(value)
    return value


def _reseal(value):
    unsigned = copy.deepcopy(value)
    unsigned.pop("response_checksum", None)
    value["response_checksum"] = sha256_json(unsigned)


def test_table_receipt_is_owner_bound_and_rebinds() -> None:
    request = _request()
    response = _response(request, "TABLE", "PROSE")
    admissions = validate_table_region_admissions(request=request, response=response)
    assert len(admissions) == 1
    admission = admissions[0]
    assert admission.bbox_pdf_points == (1.0, 2.0, 30.0, 40.0)
    rebound = validate_table_region_admission_receipt(
        receipt=admission.to_dict(),
        request=request,
        response=response,
        region_ref="r1",
    )
    assert require_validated_table_region_admission(
        admission=rebound,
        source_pdf_sha256="a" * 64,
        page_number=2,
        region_ref="r1",
        bbox_pdf_points=[1, 2, 30, 40],
        region_set_checksum=request["region_set_checksum"],
    ) is rebound
    assert all(item.region_ref != "r2" for item in admissions)


def test_ambiguity_blocks_document_and_prose_mints_no_receipt() -> None:
    request = _request()
    with pytest.raises(PdfTableRegionAdmissionError, match="_ambiguous"):
        validate_table_region_admissions(
            request=request, response=_response(request, "TABLE", "AMBIGUOUS")
        )
    assert validate_table_region_admissions(
        request=request, response=_response(request, "PROSE", "PROSE")
    ) == ()


@pytest.mark.parametrize(
    "mutation",
    ("foreign", "missing", "extra", "duplicate", "reorder", "bad_checksum"),
)
def test_response_requires_exact_ordered_closed_coverage(mutation: str) -> None:
    request = _request()
    response = _response(request, "TABLE", "PROSE")
    if mutation == "foreign":
        response["decisions"][1]["region_ref"] = "foreign"
    elif mutation == "missing":
        response["decisions"].pop()
    elif mutation == "extra":
        response["decisions"].append({"region_ref": "r3", "decision": "TABLE"})
    elif mutation == "duplicate":
        response["decisions"][1]["region_ref"] = "r1"
    elif mutation == "reorder":
        response["decisions"].reverse()
    else:
        response["response_checksum"] = "0" * 64
        with pytest.raises(PdfTableRegionAdmissionError, match="response_invalid"):
            validate_region_admission_response(request=request, response=response)
        return
    _reseal(response)
    with pytest.raises(PdfTableRegionAdmissionError, match="response_invalid"):
        validate_region_admission_response(request=request, response=response)


@pytest.mark.parametrize("bad_ref", ("", "r1"))
def test_request_rejects_blank_or_duplicate_refs(bad_ref: str) -> None:
    with pytest.raises(PdfTableRegionAdmissionError, match="scope_invalid"):
        build_region_admission_request(
            source_pdf_sha256="a" * 64,
            page_number=1,
            regions=[
                {"region_ref": "r1", "bbox_pdf_points": [1, 2, 3, 4]},
                {"region_ref": bad_ref, "bbox_pdf_points": [5, 6, 7, 8]},
            ],
        )


@pytest.mark.parametrize("fault", ("tuple", "missing_key", "extra_key", "bad_sha"))
def test_request_is_closed_and_source_hash_is_canonical(fault: str) -> None:
    region = {"region_ref": "r1", "bbox_pdf_points": [1, 2, 3, 4]}
    regions = [region]
    source_sha256 = "a" * 64
    if fault == "tuple":
        regions = tuple(regions)  # type: ignore[assignment]
    elif fault == "missing_key":
        region.pop("bbox_pdf_points")
    elif fault == "extra_key":
        region["title"] = "not-owned-here"
    else:
        source_sha256 = "A" * 64
    with pytest.raises(PdfTableRegionAdmissionError, match="scope_invalid"):
        build_region_admission_request(
            source_pdf_sha256=source_sha256,
            page_number=1,
            regions=regions,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_pdf_sha256", "b" * 64),
        ("page_number", 3),
        ("region_ref", "r2"),
        ("bbox_pdf_points", [2.0, 2.0, 30.0, 40.0]),
        ("decision_checksum", "0" * 64),
    ),
)
def test_resealed_receipt_or_moved_scope_is_rejected(field: str, value) -> None:
    request = _request()
    response = _response(request, "TABLE", "PROSE")
    admission = validate_table_region_admissions(request=request, response=response)[0]
    forged = admission.to_dict()
    forged[field] = value
    unsigned = copy.deepcopy(forged)
    unsigned.pop("receipt_checksum")
    forged["receipt_checksum"] = sha256_json(unsigned)
    with pytest.raises(PdfTableRegionAdmissionError, match="receipt_invalid"):
        validate_table_region_admission_receipt(
            receipt=forged,
            request=request,
            response=response,
            region_ref="r1",
        )


def test_reconstructed_or_copied_dto_has_no_owner_authority() -> None:
    request = _request()
    admission = validate_table_region_admissions(
        request=request, response=_response(request, "TABLE", "PROSE")
    )[0]
    for forged in (
        copy.deepcopy(admission),
        replace(admission),
        ValidatedTableRegionAdmission(
            **{
                field: getattr(admission, field)
                for field in admission.__dataclass_fields__
            }
        ),
        admission.to_dict(),
    ):
        with pytest.raises(PdfTableRegionAdmissionError, match="receipt_invalid"):
            require_validated_table_region_admission(
                admission=forged,
                source_pdf_sha256="a" * 64,
                page_number=2,
                region_ref="r1",
                bbox_pdf_points=[1, 2, 30, 40],
                region_set_checksum=request["region_set_checksum"],
            )


@pytest.mark.parametrize(
    "field",
    tuple(ValidatedTableRegionAdmission.__dataclass_fields__),
)
@pytest.mark.parametrize("reseal", (False, True))
def test_frozen_dto_backdoor_mutation_never_retains_owner_authority(
    field: str, reseal: bool
) -> None:
    request = _request()
    admission = validate_table_region_admissions(
        request=request, response=_response(request, "TABLE", "PROSE")
    )[0]
    original = getattr(admission, field)
    if isinstance(original, int):
        mutated = original + 1
    elif isinstance(original, tuple):
        mutated = (2.0, 2.0, 30.0, 40.0)
    else:
        mutated = "f" * 64 if original != "f" * 64 else "e" * 64
    object.__setattr__(admission, field, mutated)
    if reseal:
        unsigned = admission.to_dict()
        unsigned.pop("receipt_checksum")
        object.__setattr__(admission, "receipt_checksum", sha256_json(unsigned))
        if field == "receipt_checksum":
            object.__setattr__(admission, "receipt_checksum", mutated)
    with pytest.raises(PdfTableRegionAdmissionError, match="receipt_invalid"):
        require_validated_table_region_admission(
            admission=admission,
            source_pdf_sha256="a" * 64,
            page_number=2,
            region_ref="r1",
            bbox_pdf_points=[1, 2, 30, 40],
            region_set_checksum=request["region_set_checksum"],
        )


def test_truncated_genuine_receipt_cannot_satisfy_full_document_scope() -> None:
    full_request = _request()
    with pytest.raises(PdfTableRegionAdmissionError, match="_ambiguous"):
        validate_table_region_admissions(
            request=full_request,
            response=_response(full_request, "TABLE", "AMBIGUOUS"),
        )

    truncated_request = build_region_admission_request(
        source_pdf_sha256="a" * 64,
        page_number=2,
        regions=[{"region_ref": "r1", "bbox_pdf_points": [1, 2, 30, 40]}],
    )
    truncated_admission = validate_table_region_admissions(
        request=truncated_request,
        response=_response(truncated_request, "TABLE"),
    )[0]
    assert truncated_admission.region_set_checksum != full_request["region_set_checksum"]
    with pytest.raises(PdfTableRegionAdmissionError, match="receipt_invalid"):
        require_validated_table_region_admission(
            admission=truncated_admission,
            source_pdf_sha256="a" * 64,
            page_number=2,
            region_ref="r1",
            bbox_pdf_points=[1, 2, 30, 40],
            region_set_checksum=full_request["region_set_checksum"],
        )


def test_module_imports_only_neutral_stdlib_and_contract_checksum() -> None:
    import broker_reports_gate1.pdf_table_region_admission as module

    tree = ast.parse(inspect.getsource(module))
    relative = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level
    }
    assert relative == {"contracts"}
