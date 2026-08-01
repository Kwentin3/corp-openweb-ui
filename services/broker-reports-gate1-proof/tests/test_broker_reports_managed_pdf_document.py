from __future__ import annotations

import ast
import copy
import json
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    NumberObject,
)
from jsonschema import Draft202012Validator

from broker_reports_gate1.artifact_models import ARTIFACT_TYPES
from broker_reports_gate1.managed_document_coverage import (
    canonical_sha256,
    seal_private_contract,
    validate_managed_document_coverage,
    validate_parity_checklist,
    validate_source_observation_inventory,
)
from broker_reports_gate1.managed_document_parity import (
    build_artifact_only_checklist,
    build_pdf_only_checklist,
    compare_parity_checklists,
)
from broker_reports_gate1.managed_pdf_document import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    MANAGED_DOCUMENT_ARTIFACT_TYPE,
    MANAGED_DOCUMENT_BUILD_TRACE_ARTIFACT_TYPE,
    MANAGED_DOCUMENT_COVERAGE_ARTIFACT_TYPE,
    SOURCE_OBSERVATION_ARTIFACT_TYPE,
    ManagedPdfDocumentFactory,
    PdfReadingOrderAssembler,
    inactive_doc2_artifact_type_scope,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT.v1.schema.json"
)
MODULE_PATH = SERVICE_ROOT / "broker_reports_gate1" / "managed_pdf_document.py"
COVERAGE_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT_COVERAGE.v1.schema.json"
)
PARITY_SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_PDF_ARTIFACT_PARITY_CHECKLIST.v1.schema.json"
)
COVERAGE_SAFE_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "BROKER_REPORTS_DOC2_REAL_PDF_COVERAGE.safe.json"
)
PARITY_SAFE_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "BROKER_REPORTS_DOC2_PDF_ARTIFACT_PARITY.safe.json"
)


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _font_resource(writer: PdfWriter):
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    return writer._add_object(font)


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(
    *,
    texts: list[tuple[float, float, str]],
    vectors: list[str] | None = None,
    image: bool = False,
    encrypted: bool = False,
) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=320, height=320)
    font_ref = _font_resource(writer)
    resources = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    operators = [
        f"BT /F1 10 Tf {x:g} {y:g} Td ({_escape(text)}) Tj ET" for x, y, text in texts
    ]
    operators.extend(vectors or [])
    if image:
        image_stream = DecodedStreamObject()
        image_stream.set_data(b"\x00")
        image_stream.update(
            {
                NameObject("/Type"): NameObject("/XObject"),
                NameObject("/Subtype"): NameObject("/Image"),
                NameObject("/Width"): NumberObject(1),
                NameObject("/Height"): NumberObject(1),
                NameObject("/ColorSpace"): NameObject("/DeviceGray"),
                NameObject("/BitsPerComponent"): NumberObject(8),
            }
        )
        image_ref = writer._add_object(image_stream)
        resources[NameObject("/XObject")] = DictionaryObject(
            {NameObject("/Im1"): image_ref}
        )
        operators.append("q 10 0 0 10 20 20 cm /Im1 Do Q")
    page[NameObject("/Resources")] = resources
    content = DecodedStreamObject()
    content.set_data("\n".join(operators).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(content)
    if encrypted:
        writer.encrypt("synthetic-secret")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _paragraph_pdf(*, image: bool = False) -> bytes:
    return _pdf_bytes(
        texts=[
            (20, 280, "Synthetic broker report"),
            (20, 250, "Paragraph before the end"),
        ],
        image=image,
    )


def _ruled_table_pdf() -> bytes:
    texts = [
        (30, 270, "Before table"),
        (30, 220, "Date"),
        (125, 220, "Amount"),
        (225, 220, "Currency"),
        (30, 195, "2026-01-01"),
        (125, 195, "10.00"),
        (225, 195, "USD"),
        (30, 170, "2026-01-02"),
        (125, 170, "20.00"),
        (225, 170, "EUR"),
        (30, 125, "After table"),
    ]
    vectors = [
        "20 155 m 300 155 l S",
        "20 180 m 300 180 l S",
        "20 205 m 300 205 l S",
        "20 230 m 300 230 l S",
        "20 155 m 20 230 l S",
        "110 155 m 110 230 l S",
        "210 155 m 210 230 l S",
        "300 155 m 300 230 l S",
    ]
    return _pdf_bytes(texts=texts, vectors=vectors)


def test_doc2_factory_anchors_and_forbidden_boundary_are_explicit() -> None:
    assert "ManagedPdfDocumentFactory.create" in FACTORY_REQUIRED
    assert "PdfLayoutUnitBuilder._build_page_units" in FORBIDDEN
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "pdf_layout_units" not in imported_modules
    assert "gate2_handoff" not in imported_modules
    assert "semantic_pack" not in source.lower()


def test_plain_pdf_build_is_complete_deterministic_and_fully_covered() -> None:
    builder = ManagedPdfDocumentFactory().create(_schema())
    content = _paragraph_pdf()

    first = builder.build(content)
    second = builder.build(content)

    assert first.status == "COMPLETE"
    assert first.managed_document is not None
    assert first.managed_document.payload == second.managed_document.payload
    assert first.source_observation_inventory == second.source_observation_inventory
    assert first.coverage_receipt == second.coverage_receipt
    assert first.build_trace == second.build_trace
    assert first.coverage_receipt["counters"]["unresolved_total"] == 0
    assert first.coverage_receipt["counters"]["unaccounted_context_loss_total"] == 0
    assert first.coverage_receipt["counters"]["invented_source_content_total"] == 0
    assert validate_source_observation_inventory(first.source_observation_inventory)[
        "passed"
    ]
    assert validate_managed_document_coverage(
        first.coverage_receipt, first.source_observation_inventory
    )["passed"]
    required_observation_fields = {
        "available_text",
        "related_observation_ids",
        "overlap_observation_ids",
        "source_parser",
        "source_parser_version",
        "source_parser_config_ref",
        "processing_status",
    }
    assert all(
        required_observation_fields <= set(item)
        for item in first.source_observation_inventory["observations"]
    )
    assert any(
        item["observation_type"] == "TEXT_LINE"
        and item["available_text"] == "Synthetic broker report"
        for item in first.source_observation_inventory["observations"]
    )
    coverage_schema = json.loads(COVERAGE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(coverage_schema)
    Draft202012Validator(coverage_schema).validate(first.coverage_receipt)


def test_validated_table_is_inside_source_order_and_not_duplicated_as_paragraph() -> (
    None
):
    result = ManagedPdfDocumentFactory().create(_schema()).build(_ruled_table_pdf())
    assert result.managed_document is not None
    document = result.managed_document.payload
    types = [item["block_type"] for item in document["blocks"]]
    assert "TABLE" in types
    table_index = types.index("TABLE")
    paragraph_texts = [
        item["content"]["raw_text"]
        for item in document["blocks"]
        if item["block_type"] == "PARAGRAPH"
    ]
    assert any("Before table" in text for text in paragraph_texts)
    assert any("After table" in text for text in paragraph_texts)
    assert any(
        index < table_index and item["block_type"] == "PARAGRAPH"
        for index, item in enumerate(document["blocks"])
    )
    assert any(
        index > table_index and item["block_type"] == "PARAGRAPH"
        for index, item in enumerate(document["blocks"])
    )
    assert all("10.00" not in text for text in paragraph_texts)
    table_entries = [
        item
        for item in result.coverage_receipt["entries"]
        if item["coverage_status"] == "REPRESENTED_BY_TABLE"
    ]
    assert table_entries
    assert all(item["table_ids"] for item in table_entries)
    assert all(
        item["mapping_method"]
        == "source_word_ownership_to_validated_table_block_v1"
        for item in table_entries
    )
    coverage_schema = json.loads(COVERAGE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(coverage_schema).validate(result.coverage_receipt)


def test_visual_is_preserved_as_private_partial_loss() -> None:
    result = (
        ManagedPdfDocumentFactory().create(_schema()).build(_paragraph_pdf(image=True))
    )
    assert result.status == "PARTIAL"
    assert result.managed_document is not None
    document = result.managed_document.payload
    visual = next(item for item in document["blocks"] if item["block_type"] == "VISUAL")
    assert visual["content"]["private_artifact"]["status"] == "PRESENT"
    assert document["quality"]["known_losses_total"] == 2
    assert document["quality"]["unaccounted_context_loss_total"] == 0


def test_encrypted_pdf_is_terminal_blocked_without_managed_document() -> None:
    content = _pdf_bytes(texts=[(20, 280, "Encrypted synthetic")], encrypted=True)
    result = ManagedPdfDocumentFactory().create(_schema()).build(content)
    assert result.status == "BLOCKED"
    assert result.managed_document is None
    assert "pdf_encrypted_without_key" in result.reason_codes
    assert result.coverage_receipt["counters"]["blocked_at_source_total"] == 1
    assert result.coverage_receipt["counters"]["unresolved_total"] == 0


def test_coverage_tampering_fails_closed() -> None:
    result = ManagedPdfDocumentFactory().create(_schema()).build(_paragraph_pdf())
    tampered = copy.deepcopy(result.coverage_receipt)
    tampered["entries"][0]["coverage_status"] = "UNRESOLVED"
    validation = validate_managed_document_coverage(
        tampered, result.source_observation_inventory
    )
    assert not validation["passed"]
    assert "managed_document_coverage_counters_mismatch" in validation["reason_codes"]
    assert "managed_document_coverage_integrity_mismatch" in validation["reason_codes"]


def test_duplicate_suppression_requires_exact_source_observation_proof() -> None:
    result = ManagedPdfDocumentFactory().create(_schema()).build(_paragraph_pdf())
    inventory = copy.deepcopy(result.source_observation_inventory)
    duplicate = copy.deepcopy(inventory["observations"][0])
    duplicate["observation_id"] = "observation_exact_duplicate_fixture"
    inventory["observations"].append(duplicate)
    inventory["observations_total"] += 1
    inventory = seal_private_contract(inventory)

    receipt = copy.deepcopy(result.coverage_receipt)
    primary_entry = receipt["entries"][0]
    receipt["entries"].append(
        {
            "observation_id": duplicate["observation_id"],
            "coverage_status": "DUPLICATE_SUPPRESSED",
            "duplicate_of_observation_id": inventory["observations"][0][
                "observation_id"
            ],
            "block_ids": copy.deepcopy(primary_entry["block_ids"]),
            "anchor_ids": copy.deepcopy(primary_entry["anchor_ids"]),
            "table_ids": [],
            "loss_ids": [],
            "mapping_method": None,
            "reason_code": "source_observation_duplicate_suppressed",
        }
    )
    receipt["counters"]["source_observations_total"] += 1
    receipt["counters"]["coverage_entries_total"] += 1
    receipt = seal_private_contract(receipt)
    assert validate_managed_document_coverage(receipt, inventory)["passed"]

    unproven = copy.deepcopy(receipt)
    unproven["entries"][-1].pop("duplicate_of_observation_id")
    unproven = seal_private_contract(unproven)
    validation = validate_managed_document_coverage(unproven, inventory)
    assert not validation["passed"]
    assert (
        "managed_document_coverage_duplicate_not_proven" in validation["reason_codes"]
    )


def test_coverage_dispositions_require_status_specific_owners() -> None:
    result = ManagedPdfDocumentFactory().create(_schema()).build(_paragraph_pdf())
    tampered = copy.deepcopy(result.coverage_receipt)
    represented = next(
        item
        for item in tampered["entries"]
        if item["coverage_status"] == "REPRESENTED_BY_BLOCK"
    )
    represented["block_ids"] = []
    tampered = seal_private_contract(tampered)
    validation = validate_managed_document_coverage(
        tampered, result.source_observation_inventory
    )
    assert not validation["passed"]
    assert "managed_document_coverage_block_owner_missing" in validation["reason_codes"]


def test_reading_order_ambiguity_is_terminal_blocked() -> None:
    line = {
        "line_ref": "line_fixture",
        "line_observation_id": "observation_line_fixture",
        "word_refs": [],
    }
    observation = {
        "status": "READY",
        "document_id": "document_fixture",
        "source_checksum_sha256": "a" * 64,
        "pages": [
            {
                "page_number": 1,
                "words": [],
                "table_candidates": [],
                "text_lines": [line],
                "text_blocks": [
                    {"line_refs": ["line_fixture"]},
                    {"line_refs": ["line_fixture"]},
                ],
            }
        ],
    }
    assembled = PdfReadingOrderAssembler().assemble(observation)
    assert assembled["status"] == "BLOCKED"
    assert assembled["reason_codes"] == ["managed_pdf_reading_order_ambiguity"]


def test_unowned_parser_word_is_terminal_reading_order_ambiguity() -> None:
    observation = {
        "status": "READY",
        "document_id": "document_fixture",
        "source_checksum_sha256": "a" * 64,
        "pages": [
            {
                "page_number": 1,
                "words": [{"word_ref": "word_fixture"}],
                "table_candidates": [],
                "text_lines": [
                    {
                        "line_ref": "line_fixture",
                        "line_observation_id": "observation_line_fixture",
                        "word_refs": [],
                    }
                ],
                "text_blocks": [{"line_refs": ["line_fixture"]}],
            }
        ],
    }
    assembled = PdfReadingOrderAssembler().assemble(observation)
    assert assembled["status"] == "BLOCKED"
    assert assembled["reason_codes"] == ["managed_pdf_reading_order_ambiguity"]


def test_isolated_pdf_and_artifact_checklists_compare_with_full_parity() -> None:
    content = _ruled_table_pdf()
    result = ManagedPdfDocumentFactory().create(_schema()).build(content)
    assert result.managed_document is not None
    pdf_checklist = build_pdf_only_checklist(content)
    artifact_checklist = build_artifact_only_checklist(result.managed_document.payload)
    comparison = compare_parity_checklists(pdf_checklist, artifact_checklist)
    assert validate_parity_checklist(pdf_checklist)["passed"]
    assert validate_parity_checklist(artifact_checklist)["passed"]
    assert validate_parity_checklist(comparison)["passed"]
    assert comparison["critical_mismatches_total"] == 0
    assert comparison["noncritical_mismatches_total"] == 0
    assert comparison["full_parity"] is True
    assert all(item["status"] == "MATCH" for item in comparison["dimensions"])
    assert all(
        item["critical_category"] is None for item in comparison["dimensions"]
    )
    assert pdf_checklist["summary"]["value_sample_policy"] == "ALL_VALUES"
    assert artifact_checklist["summary"]["value_sample_policy"] == "ALL_VALUES"
    assert pdf_checklist["summary"]["tables"]
    assert artifact_checklist["summary"]["tables"]
    assert all(
        item["source_pointer"]
        for checklist in (pdf_checklist, artifact_checklist)
        for item in checklist["summary"]["value_samples"]
    )
    parity_schema = json.loads(PARITY_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(parity_schema)
    validator = Draft202012Validator(parity_schema)
    validator.validate(pdf_checklist)
    validator.validate(artifact_checklist)
    validator.validate(comparison)


def test_private_doc2_artifact_types_are_explicitly_admitted() -> None:
    doc2_types = {
        MANAGED_DOCUMENT_ARTIFACT_TYPE,
        SOURCE_OBSERVATION_ARTIFACT_TYPE,
        MANAGED_DOCUMENT_COVERAGE_ARTIFACT_TYPE,
        MANAGED_DOCUMENT_BUILD_TRACE_ARTIFACT_TYPE,
    }
    assert not doc2_types & ARTIFACT_TYPES
    with inactive_doc2_artifact_type_scope():
        assert doc2_types <= ARTIFACT_TYPES
    assert not doc2_types & ARTIFACT_TYPES


def test_safe_real_corpus_summaries_are_integrity_sealed_and_private_free() -> None:
    coverage = json.loads(COVERAGE_SAFE_PATH.read_text(encoding="utf-8"))
    parity = json.loads(PARITY_SAFE_PATH.read_text(encoding="utf-8"))
    assert coverage["integrity_sha256"] == canonical_sha256(coverage)
    assert parity["integrity_sha256"] == canonical_sha256(parity)
    assert coverage["aggregate"]["readable_real_pdfs_total"] == 4
    assert coverage["aggregate"]["unresolved_source_observations_total"] == 0
    assert coverage["aggregate"]["unaccounted_context_loss_total"] == 0
    assert coverage["aggregate"]["invented_source_content_total"] == 0
    assert parity["aggregate"]["full_parity_documents_total"] == 4
    assert parity["aggregate"]["critical_parity_mismatches_total"] == 0
    for payload in (coverage, parity):
        encoded = json.dumps(payload, ensure_ascii=False).lower()
        assert "local/" not in encoded
        assert "local\\" not in encoded
        assert "c:\\" not in encoded
