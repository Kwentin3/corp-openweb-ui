from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.physical_table_continuation import (
    PhysicalTableContinuationError,
    build_physical_table_continuation_sidecar,
)
from broker_reports_gate1.pdf_table_continuation_annotation_prompt import (
    INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_ID,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_COMMAND,
    PROMPT_CONTRACT_ID,
    PROMPT_REQUIRED_TAG,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND,
    PdfTableContinuationAnnotationManagedPrompt,
    execution_from_managed_prompt,
    pdf_table_continuation_annotation_prompt_hash,
)


SOURCE_SHA = "a" * 64
TABLE_A_SHA = "b" * 64
TABLE_B_SHA = "c" * 64


def _unit(*, ref: str, table_ref: str, table_sha: str, page: int) -> dict:
    return {
        "unit_ref": ref,
        "normalization_run_id": "run-1",
        "document_id": "document-1",
        "source_checksum_sha256": SOURCE_SHA,
        "document_ai_native_table_ref": table_ref,
        "document_ai_native_table_sha256": table_sha,
        "source_location": {"kind": "document_ai_native_table_html", "page": page},
    }


def _proposal() -> dict:
    return {
        "parent": {
            "native_table_ref": "native-a",
            "native_table_sha256": TABLE_A_SHA,
            "page_number": 3,
        },
        "child": {
            "native_table_ref": "native-b",
            "native_table_sha256": TABLE_B_SHA,
            "page_number": 4,
        },
    }


def _annotation_receipt() -> dict:
    content = "Assess physical table continuations only."
    execution = execution_from_managed_prompt(
        PdfTableContinuationAnnotationManagedPrompt(
            prompt_ref="test-prompt",
            command=PROMPT_COMMAND,
            version="test-history",
            content=content,
            hash=pdf_table_continuation_annotation_prompt_hash(content),
            source="test",
            template_id=PROMPT_TEMPLATE_ID,
            template_kind=PROMPT_TEMPLATE_KIND,
            prompt_contract_id=PROMPT_CONTRACT_ID,
            input_schema_version=INPUT_SCHEMA_VERSION,
            output_schema_id=OUTPUT_SCHEMA_ID,
            output_schema_version=OUTPUT_SCHEMA_VERSION,
            tags=(PROMPT_REQUIRED_TAG,),
            safe_metadata={"name": "test"},
        )
    )
    return {
        "assessment_schema_version": "broker_reports_pdf_document_table_continuation_assessment_v1",
        "annotation_prompt_sha256": execution.content_sha256,
        "annotation_schema_sha256": "e" * 64,
        "request_parameters_sha256": "f" * 64,
        "raw_annotation_sha256": "1" * 64,
        "selected_page_bindings_sha256": "2" * 64,
        "prompt_snapshot": execution.validated_prompt_snapshot(),
    }


def _build(
    *,
    units: list[dict] | None = None,
    links: list[dict] | None = None,
    receipt: dict | None = None,
) -> dict:
    return build_physical_table_continuation_sidecar(
        normalization_run_id="run-1",
        document_id="document-1",
        source_pdf_sha256=SOURCE_SHA,
        source_units=units
        or [
            _unit(ref="unit-a", table_ref="native-a", table_sha=TABLE_A_SHA, page=3),
            _unit(ref="unit-b", table_ref="native-b", table_sha=TABLE_B_SHA, page=4),
        ],
        proposed_links=links or [_proposal()],
        annotation_receipt=receipt or _annotation_receipt(),
    )


def test_binds_only_exact_same_run_physical_table_units() -> None:
    sidecar = _build()
    assert sidecar["visibility"] == "private_case"
    assert sidecar["links"] == [
        {
            "parent": {
                "unit_ref": "unit-a",
                "native_table_ref": "native-a",
                "native_table_sha256": TABLE_A_SHA,
                "page_number": 3,
            },
            "child": {
                "unit_ref": "unit-b",
                "native_table_ref": "native-b",
                "native_table_sha256": TABLE_B_SHA,
                "page_number": 4,
            },
        }
    ]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda units, link: units[0].update(normalization_run_id="other-run"),
        lambda units, link: units[0].update(document_id="other-document"),
        lambda units, link: units[0].update(source_checksum_sha256="d" * 64),
        lambda units, link: units[0].update(document_ai_native_table_sha256="e" * 64),
        lambda units, link: units[0]["source_location"].update(page=2),
        lambda units, link: link["child"].update(page_number=5),
        lambda units, link: link["parent"].update(native_table_ref="missing"),
    ],
)
def test_rejects_any_unbound_or_nonadjacent_identity(mutate) -> None:
    units = [
        _unit(ref="unit-a", table_ref="native-a", table_sha=TABLE_A_SHA, page=3),
        _unit(ref="unit-b", table_ref="native-b", table_sha=TABLE_B_SHA, page=4),
    ]
    proposal = _proposal()
    mutate(units, proposal)
    with pytest.raises(PhysicalTableContinuationError):
        _build(units=units, links=[proposal])


def test_rejects_conflicting_parent_or_child() -> None:
    second = copy.deepcopy(_proposal())
    second["child"]["native_table_ref"] = "native-a"
    second["child"]["native_table_sha256"] = TABLE_A_SHA
    second["child"]["page_number"] = 4
    with pytest.raises(PhysicalTableContinuationError):
        _build(links=[_proposal(), second])


def test_rejects_annotation_receipt_with_prompt_body() -> None:
    receipt = _annotation_receipt()
    receipt["prompt_snapshot"]["content"] = "must not persist"
    with pytest.raises(PhysicalTableContinuationError):
        build_physical_table_continuation_sidecar(
            normalization_run_id="run-1",
            document_id="document-1",
            source_pdf_sha256=SOURCE_SHA,
            source_units=[
                _unit(
                    ref="unit-a",
                    table_ref="native-a",
                    table_sha=TABLE_A_SHA,
                    page=3,
                ),
                _unit(
                    ref="unit-b",
                    table_ref="native-b",
                    table_sha=TABLE_B_SHA,
                    page=4,
                ),
            ],
            proposed_links=[_proposal()],
            annotation_receipt=receipt,
        )


def test_rejects_annotation_receipt_not_bound_to_sealed_prompt_snapshot() -> None:
    receipt = _annotation_receipt()
    receipt["annotation_prompt_sha256"] = "0" * 64

    with pytest.raises(PhysicalTableContinuationError):
        _build(receipt=receipt)
