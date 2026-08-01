from __future__ import annotations

import ast
import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError

from broker_reports_gate1.managed_document_contracts import (
    BlockType,
    ManagedDocumentContractError,
    ManagedDocumentContractValidator,
    RelationType,
    SourceFormat,
    canonical_document_json_bytes,
    compute_document_integrity_sha256,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"
MODULE_PATH = PACKAGE_ROOT / "managed_document_contracts.py"
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT.v1.schema.json"
)
CONTRACT_PATH = SCHEMA_PATH.with_suffix("").with_suffix(".md")
DECISION_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "BROKER_REPORTS_DOC1_DOCUMENT_CONTRACT_DECISION.v1.md"
)
COVERAGE_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "BROKER_REPORTS_DOC0_TO_DOC1_CONTEXT_COVERAGE.v1.json"
)
DOC0_MATRIX_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "BROKER_REPORTS_CONTEXT_LOSS_MATRIX.v1.json"
)
CORPUS_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "broker_reports_managed_document_v1_corpus.safe.json"
)
BUNDLE_BUILDER = SERVICE_ROOT / "scripts" / "build_openwebui_pipe_bundle.py"
BUNDLE_PATHS = (
    SERVICE_ROOT / "openwebui_actions" / "broker_reports_gate1_pipe_bundled.py",
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_source_fact_pipe_bundled.py",
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_domain_source_fact_pipe_bundled.py",
)


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return _read_json(SCHEMA_PATH)


@pytest.fixture(scope="module")
def corpus() -> dict[str, Any]:
    return _read_json(CORPUS_PATH)


@pytest.fixture(scope="module")
def validator(schema: dict[str, Any]) -> ManagedDocumentContractValidator:
    return ManagedDocumentContractValidator(schema)


def test_schema_and_python_contract_accept_all_safe_fixtures(
    schema: dict[str, Any],
    corpus: dict[str, Any],
    validator: ManagedDocumentContractValidator,
) -> None:
    schema_validator = Draft202012Validator(schema)
    assert len(corpus["documents"]) == 6
    for document in corpus["documents"]:
        schema_validator.validate(document)
        assert validator.validate(document).payload == document


def test_fixture_corpus_is_synthetic_private_safe_and_keeps_real_gap(
    corpus: dict[str, Any],
) -> None:
    assert corpus["fixture_policy"] == (
        "hand_authored_synthetic_contract_expressiveness_only"
    )
    assert corpus["privacy"] == {
        "customer_data_included": False,
        "private_paths_included": False,
        "real_source_refs_included": False,
        "provider_payloads_included": False,
    }
    assert corpus["real_corpus_gap"] is True
    rendered = json.dumps(corpus, ensure_ascii=False).lower()
    assert "c:\\users\\" not in rendered
    assert "/home/" not in rendered
    assert "d:\\users\\" not in rendered


def test_unknown_block_survives_parse_and_canonical_round_trip(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    source = _document(corpus, "document_fixture_b_unknown_structure")
    parsed = validator.parse_json(json.dumps(source, ensure_ascii=False))
    reparsed = validator.parse_json(parsed.canonical_json_bytes())
    unknown = next(
        block for block in reparsed.payload["blocks"] if block["block_type"] == "UNKNOWN"
    )
    assert unknown["content"]["raw_text"] == (
        "Synthetic unfamiliar source structure retained verbatim."
    )
    assert unknown["ordinal"] == 1


def test_unknown_metadata_does_not_require_invented_value(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    source = _document(corpus, "document_fixture_b_unknown_structure")
    document_type = validator.validate(source).payload["metadata"]["document_type"]
    assert document_type == {
        "information_class": "CONTENT",
        "status": "UNKNOWN",
        "origin": "UNKNOWN_ORIGIN",
        "value": None,
        "candidates": [],
        "evidence_anchor_ids": [],
    }
    candidate = _document(corpus, "document_fixture_a_broker_report")
    candidate["metadata"]["additional"] = [
        {
            "name": "synthetic_accounting_basis",
            "information_class": "CONTENT",
            "status": "PRESENT",
            "origin": "SOURCE_EXPLICIT",
            "value": "Synthetic basis",
            "candidates": [],
            "evidence_anchor_ids": ["anchor_a_heading"],
        }
    ]
    _reseal(candidate)
    assert validator.validate(candidate).payload["metadata"]["additional"][0][
        "name"
    ] == "synthetic_accounting_basis"


def test_block_order_is_the_only_contiguous_primary_reading_order(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    source = _document(corpus, "document_fixture_a_broker_report")
    validated = validator.validate(source).payload
    assert [block["ordinal"] for block in validated["blocks"]] == list(
        range(len(validated["blocks"]))
    )
    assert [block["block_type"] for block in validated["blocks"]] == [
        "BOUNDARY",
        "HEADING",
        "PARAGRAPH",
        "TABLE",
        "NOTE",
    ]


def test_valid_relation_endpoints_and_row_target_pass(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    source = _document(corpus, "document_fixture_c_continued_table")
    validated = validator.validate(source).payload
    footnote = next(
        relation
        for relation in validated["relations"]
        if relation["relation_type"] == RelationType.FOOTNOTE_FOR
    )
    assert footnote["target"] == {
        "block_id": "block_c_table_2",
        "row_index": 1,
        "column_index": None,
    }


def test_missing_relation_endpoint_is_rejected(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    candidate = _document(corpus, "document_fixture_a_broker_report")
    candidate["relations"][0]["target"]["block_id"] = "block_missing_target"
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractError,
        match="managed_document_relation_endpoint_missing",
    ):
        validator.validate(candidate)


def test_duplicate_block_ids_are_rejected(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    candidate = _document(corpus, "document_fixture_d_csv")
    duplicate = copy.deepcopy(candidate["blocks"][0])
    duplicate["ordinal"] = 1
    candidate["blocks"].append(duplicate)
    candidate["quality"]["source_elements_total"] = 2
    candidate["quality"]["preserved_blocks_total"] = 2
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractError,
        match="managed_document_duplicate_block_id",
    ):
        validator.validate(candidate)


def test_invalid_block_ordinal_is_rejected(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    candidate = _document(corpus, "document_fixture_a_broker_report")
    candidate["blocks"][2]["ordinal"] = 8
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractError,
        match="managed_document_block_ordinal_invalid",
    ):
        validator.validate(candidate)


def test_table_reuses_exact_description_and_rows_core(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    source = _document(corpus, "document_fixture_a_broker_report")
    table = next(
        block["content"]
        for block in validator.validate(source).payload["blocks"]
        if block["block_type"] == BlockType.TABLE
    )
    assert table["description"] == "Synthetic source-visible positions table."
    assert table["rows"] == [
        ["Asset", "Amount"],
        ["Synthetic A", "100.00"],
        ["Synthetic B", None],
    ]
    assert "bbox" not in table
    assert "column_width" not in table
    assert "physical_span" not in table


def test_table_annotation_cannot_target_missing_cell(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    candidate = _document(corpus, "document_fixture_a_broker_report")
    table = candidate["blocks"][3]["content"]
    table["cell_annotations"][0]["column_index"] = 9
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractError,
        match="managed_document_table_annotation_out_of_range",
    ):
        validator.validate(candidate)


def test_empty_and_unreadable_cells_are_distinct_contract_states(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    fixture_a = validator.validate(
        _document(corpus, "document_fixture_a_broker_report")
    ).payload
    fixture_c = validator.validate(
        _document(corpus, "document_fixture_c_continued_table")
    ).payload
    empty = fixture_a["blocks"][3]["content"]["cell_annotations"][1]
    unreadable = fixture_c["blocks"][3]["content"]["cell_annotations"][0]
    assert empty["state"] == "EMPTY"
    assert unreadable["state"] == "UNREADABLE"
    assert empty["state"] != unreadable["state"]


def test_continuation_and_footnote_relations_pass(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    source = _document(corpus, "document_fixture_c_continued_table")
    relations = validator.validate(source).payload["relations"]
    assert {relation["relation_type"] for relation in relations} == {
        RelationType.CONTINUATION_OF,
        RelationType.FOOTNOTE_FOR,
    }


def test_source_anchors_cover_pdf_html_csv_and_xlsx(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    validated = [validator.validate(document).payload for document in corpus["documents"]]
    by_format = {document["source"]["format"]: document for document in validated}
    assert {SourceFormat.PDF, SourceFormat.HTML, SourceFormat.CSV, SourceFormat.XLSX} <= (
        set(by_format)
    )
    assert by_format[SourceFormat.PDF]["anchors"][0]["locator"]["kind"] == "PDF"
    assert by_format[SourceFormat.HTML]["anchors"][0]["locator"]["dom_path"]
    assert by_format[SourceFormat.CSV]["anchors"][0]["locator"]["row_end"] == 3
    assert by_format[SourceFormat.XLSX]["anchors"][0]["locator"]["cell_range"]


def test_loss_ledger_counts_and_partial_status_are_consistent(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    source = _document(corpus, "document_fixture_c_continued_table")
    quality = validator.validate(source).payload["quality"]
    assert quality["status"] == "PARTIAL"
    assert quality["known_losses_total"] == len(quality["loss_ledger"]) == 1
    assert quality["blocking_losses_total"] == 0
    assert quality["unaccounted_context_loss_total"] == 0


def test_complete_document_with_blocking_loss_is_rejected(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    candidate = _document(corpus, "document_fixture_d_csv")
    candidate["quality"]["known_losses_total"] = 1
    candidate["quality"]["blocking_losses_total"] = 1
    candidate["quality"]["loss_ledger"] = [
        {
            "loss_id": "loss_d_blocking",
            "context_class": "CONTENT",
            "what_lost": "Synthetic required value.",
            "where": "CSV row 2.",
            "reason": "Synthetic blocking test.",
            "recoverability": "UNKNOWN",
            "requires_source_reread": True,
            "blocks_semantic_analysis": True,
            "accounted": True,
            "anchor_ids": ["anchor_d_csv"],
            "block_ids": ["block_d_table"],
        }
    ]
    candidate["blocks"][0]["content"]["known_gap_ids"] = ["loss_d_blocking"]
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractError,
        match="managed_document_complete_with_blocking_loss",
    ):
        validator.validate(candidate)


def test_unaccounted_context_loss_is_schema_rejected(
    schema: dict[str, Any], corpus: dict[str, Any]
) -> None:
    candidate = _document(corpus, "document_fixture_d_csv")
    candidate["quality"]["unaccounted_context_loss_total"] = 1
    _reseal(candidate)
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(candidate)


def test_canonical_serialization_is_deterministic_and_utf8(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    source = _document(corpus, "document_fixture_a_broker_report")
    first = validator.validate(source).canonical_json_bytes()
    reordered = {key: source[key] for key in reversed(list(source))}
    second = canonical_document_json_bytes(reordered)
    assert first == second
    assert first == first.decode("utf-8").encode("utf-8")


def test_hash_tampering_is_detected(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    candidate = _document(corpus, "document_fixture_a_broker_report")
    candidate["blocks"][2]["content"]["raw_text"] = "Tampered text"
    with pytest.raises(
        ManagedDocumentContractError,
        match="managed_document_integrity_invalid",
    ):
        validator.validate(candidate)


def test_seal_calculates_the_canonical_hash(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    candidate = _document(corpus, "document_fixture_d_csv")
    candidate.pop("integrity_sha256")
    sealed = validator.seal(candidate)
    assert sealed.integrity_sha256 == compute_document_integrity_sha256(
        sealed.payload
    )


def test_json_parser_rejects_duplicate_keys(
    validator: ManagedDocumentContractValidator,
) -> None:
    with pytest.raises(
        ManagedDocumentContractError,
        match="managed_document_duplicate_json_key",
    ):
        validator.parse_json('{"schema_version":"x","schema_version":"y"}')


def test_schema_and_python_contract_both_reject_unknown_properties(
    schema: dict[str, Any],
    corpus: dict[str, Any],
    validator: ManagedDocumentContractValidator,
) -> None:
    candidate = _document(corpus, "document_fixture_d_csv")
    candidate["invented_extension"] = {}
    _reseal(candidate)
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(candidate)
    with pytest.raises(
        ManagedDocumentContractError,
        match="managed_document_schema_validation_failed",
    ):
        validator.validate(candidate)


def test_source_explicit_metadata_requires_evidence_anchor(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    candidate = _document(corpus, "document_fixture_a_broker_report")
    candidate["metadata"]["title"]["evidence_anchor_ids"] = []
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractError,
        match="managed_document_source_explicit_evidence_missing",
    ):
        validator.validate(candidate)


def test_model_proposal_origin_remains_distinct_from_source_explicit(
    corpus: dict[str, Any], validator: ManagedDocumentContractValidator
) -> None:
    candidate = _document(corpus, "document_fixture_a_broker_report")
    candidate["metadata"]["title"]["origin"] = "MODEL_PROPOSED"
    _reseal(candidate)
    validated = validator.validate(candidate).payload
    assert validated["metadata"]["title"]["origin"] == "MODEL_PROPOSED"
    assert validated["metadata"]["title"]["origin"] != "SOURCE_EXPLICIT"


def test_doc0_coverage_accounts_for_exactly_all_53_facets() -> None:
    coverage = _read_json(COVERAGE_PATH)
    doc0 = _read_json(DOC0_MATRIX_PATH)
    coverage_ids = [facet["facet_id"] for facet in coverage["facets"]]
    doc0_ids = [facet["id"] for facet in doc0["facets"]]
    assert coverage_ids == doc0_ids
    assert len(coverage_ids) == len(set(coverage_ids)) == 53
    assert coverage["summary"] == {
        "doc0_context_facets_total": 53,
        "doc0_context_facets_represented_total": 51,
        "doc0_context_facets_explicit_unknown_total": 2,
        "doc0_context_facets_loss_ledger_total": 0,
        "doc0_context_facets_deferred_total": 0,
        "doc0_context_facets_unaccounted_total": 0,
    }
    assert coverage["integrity_sha256"] == _canonical_integrity(coverage)


def test_contract_surface_contains_no_canonical_financial_type_ids() -> None:
    pack = _read_json(
        SERVICE_ROOT
        / "semantic_packs"
        / "broker_reports_financial_semantic_pack.v1.json"
    )
    type_ids = set(pack["source_baseline"]["accepted_type_ids"])
    type_ids.update(pack["source_baseline"]["deferred_candidate_ids"])
    surfaces = [MODULE_PATH, SCHEMA_PATH, CORPUS_PATH, COVERAGE_PATH]
    surfaces.extend(path for path in (CONTRACT_PATH, DECISION_PATH) if path.is_file())
    rendered = "\n".join(path.read_text(encoding="utf-8") for path in surfaces)
    assert sorted(type_id for type_id in type_ids if type_id in rendered) == []


def test_contract_module_imports_no_parser_provider_product_or_semantic_pack() -> None:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    forbidden_markers = (
        "pdf_",
        "profiler",
        "normalizer",
        "artifact_store",
        "provider",
        "model_client",
        "semantic_pack",
        "gate2_",
        "openwebui_actions",
    )
    assert sorted(
        name for name in imports if any(marker in name for marker in forbidden_markers)
    ) == []


def test_contract_has_no_product_or_provider_reachability() -> None:
    violations = []
    for root in (PACKAGE_ROOT, SERVICE_ROOT / "openwebui_actions"):
        for path in root.glob("*.py"):
            if path == MODULE_PATH:
                continue
            if "managed_document_contracts" in path.read_text(encoding="utf-8"):
                violations.append(path.relative_to(SERVICE_ROOT).as_posix())
    assert violations == []
    module_source = MODULE_PATH.read_text(encoding="utf-8")
    assert "def main(" not in module_source
    assert "__main__" not in module_source


def test_generated_bundles_exclude_contract_and_rebuild_byte_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spec = importlib.util.spec_from_file_location(
        "doc1_bundle_builder_check",
        BUNDLE_BUILDER,
    )
    assert spec is not None and spec.loader is not None
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    generated_paths = {
        "BUNDLE_PATH": tmp_path / BUNDLE_PATHS[0].name,
        "GATE2_BUNDLE_PATH": tmp_path / BUNDLE_PATHS[1].name,
        "GATE2_DOMAIN_BUNDLE_PATH": tmp_path / BUNDLE_PATHS[2].name,
    }
    for attribute, path in generated_paths.items():
        monkeypatch.setattr(builder, attribute, path)
    monkeypatch.setattr(sys, "argv", [str(BUNDLE_BUILDER), "--target", "all"])

    builder.main()

    rebuilt = {
        source: generated_paths[attribute].read_bytes()
        for source, attribute in zip(
            BUNDLE_PATHS,
            ("BUNDLE_PATH", "GATE2_BUNDLE_PATH", "GATE2_DOMAIN_BUNDLE_PATH"),
            strict=True,
        )
    }
    assert all(rebuilt[path] == path.read_bytes() for path in BUNDLE_PATHS)
    assert all(
        b"managed_document_contracts" not in content
        for content in rebuilt.values()
    )


def test_contract_enums_are_universal_and_not_broker_specific() -> None:
    assert set(SourceFormat) == {
        SourceFormat.PDF,
        SourceFormat.HTML,
        SourceFormat.CSV,
        SourceFormat.XLSX,
        SourceFormat.XLS,
        SourceFormat.UNKNOWN,
    }
    assert set(BlockType) == {
        BlockType.HEADING,
        BlockType.PARAGRAPH,
        BlockType.LIST,
        BlockType.TABLE,
        BlockType.NOTE,
        BlockType.VISUAL,
        BlockType.BOUNDARY,
        BlockType.UNKNOWN,
    }
    module_source = MODULE_PATH.read_text(encoding="utf-8")
    assert "Operations" not in module_source
    assert "Commissions" not in module_source
    assert "Taxes" not in module_source


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _document(corpus: dict[str, Any], document_id: str) -> dict[str, Any]:
    return copy.deepcopy(
        next(
            document
            for document in corpus["documents"]
            if document["document_id"] == document_id
        )
    )


def _reseal(candidate: dict[str, Any]) -> None:
    candidate["integrity_sha256"] = compute_document_integrity_sha256(candidate)


def _canonical_integrity(payload: dict[str, Any]) -> str:
    return compute_document_integrity_sha256(payload)
