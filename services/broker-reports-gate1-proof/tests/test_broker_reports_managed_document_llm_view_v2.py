from __future__ import annotations

import ast
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from broker_reports_gate1.managed_document_contracts_v2 import (
    ManagedDocumentContractV2Error,
    ManagedDocumentContractV2Validator,
)
from broker_reports_gate1.managed_document_llm_view_audit_v2 import (
    ManagedDocumentLlmViewV2AuditError,
    ManagedDocumentLlmViewV2Auditor,
)
from broker_reports_gate1.managed_document_llm_view_parity_v2 import (
    build_llm_view_v2_row_checklist,
    build_managed_document_v2_row_checklist,
    compare_row_checklists,
)
from broker_reports_gate1.managed_document_llm_view_v2 import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    ManagedDocumentLlmViewV2Factory,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
SCHEMA_PATH = (
    REPO_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json"
)
AUDITOR_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "managed_document_llm_view_audit_v2.py"
)


@pytest.fixture
def schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def managed_document(schema: dict[str, Any]) -> dict[str, Any]:
    candidate = _candidate()
    return ManagedDocumentContractV2Validator(schema).seal(candidate).payload


def test_factory_renders_and_auditor_reads_complete_row_surface(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    first = ManagedDocumentLlmViewV2Factory.create(managed_document, schema)
    second = ManagedDocumentLlmViewV2Factory.create(managed_document, schema)

    assert first == second
    assert first.text.startswith("BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2\n")
    assert first.text.endswith("END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2\n")
    assert "\r" not in first.text
    assert "\n\n" not in first.text
    assert 'Context\\nTABLE_END and literal \\"bbox\\"' in first.text
    assert first.text.count("ROW_BEGIN\n") == 3
    assert first.text.count("ENTRY_BEGIN\n") == 5
    assert "CELL_" not in first.text
    assert "SPAN_" not in first.text

    parsed = ManagedDocumentLlmViewV2Auditor().audit(first.text).payload
    table = next(
        block["content"]
        for block in parsed["blocks"]
        if block["block_type"] == "TABLE"
    )
    assert [row["role"] for row in table["ordered_rows"]] == [
        "COLUMN_HEADER",
        "GROUP_HEADER",
        "DATA",
    ]
    assert [len(row["entries"]) for row in table["ordered_rows"]] == [2, 1, 2]
    assert table["ordered_rows"][2]["parent_row_id"] == "row_assets"
    assert table["ordered_rows"][2]["nesting_level"] == 1
    assert table["logical_columns"][1]["header_path"] == [
        "entry_header_amount"
    ]
    assert table["source_parts"][0]["continuation_status"] == "SINGLE"


@pytest.mark.parametrize(
    "direct_column_id",
    [None, "column_description"],
    ids=["cover-only", "direct-and-cover"],
)
def test_cover_binding_roundtrips_losslessly(
    schema: dict[str, Any], direct_column_id: str | None
) -> None:
    candidate = _three_column_candidate(
        row_role="DATA",
        direct_column_id=direct_column_id,
    )
    managed_document = ManagedDocumentContractV2Validator(schema).seal(
        candidate
    ).payload
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    parsed = ManagedDocumentLlmViewV2Auditor().audit(view).payload

    managed_entry = _table_entry(managed_document, "entry_cash")
    view_entry = _table_entry(parsed, "entry_cash")
    assert view_entry["column_binding_status"] == "BOUND"
    assert view_entry["logical_column_id"] == direct_column_id
    assert view_entry["covers_logical_column_ids"] == [
        "column_description",
        "column_amount",
        "column_auxiliary",
    ]
    assert {
        key: view_entry[key]
        for key in (
            "column_binding_status",
            "logical_column_id",
            "covers_logical_column_ids",
        )
    } == {
        key: managed_entry[key]
        for key in (
            "column_binding_status",
            "logical_column_id",
            "covers_logical_column_ids",
        )
    }
    assert _compare_document_to_view(managed_document, view)[
        "terminal_status"
    ] == "PASSED"


def test_view_metadata_order_is_independent_of_mapping_insertion_order(
    schema: dict[str, Any],
) -> None:
    first_candidate = _candidate()
    second_candidate = copy.deepcopy(first_candidate)
    second_candidate["metadata"] = dict(
        reversed(list(second_candidate["metadata"].items()))
    )
    validator = ManagedDocumentContractV2Validator(schema)
    first = validator.seal(first_candidate).payload
    second = validator.seal(second_candidate).payload

    assert first["integrity_sha256"] == second["integrity_sha256"]
    first_view = ManagedDocumentLlmViewV2Factory.create(first, schema)
    second_view = ManagedDocumentLlmViewV2Factory.create(second, schema)

    assert first_view.text == second_view.text
    assert first_view.content_sha256 == second_view.content_sha256


def test_view_omits_private_geometry_ownership_and_checksums(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text

    for forbidden in (
        "DOCUMENT_ID",
        managed_document["document_id"],
        "private://",
        '"bbox"',
        '"checksum_sha256"',
        '"geometry_evidence',
        '"source_word_ownership"',
        '"source_word_id"',
        '"confidence',
    ):
        assert forbidden not in view
    assert "a" * 64 not in view
    assert (
        'ENTRY_SOURCE [{"anchor_id":"anchor_cash","format":"PDF",'
        '"page":1,"source_part_index":1}]'
    ) in view


def test_factory_rejects_unvalidated_or_tampered_managed_document(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    tampered = copy.deepcopy(managed_document)
    tampered["blocks"][1]["content"]["ordered_rows"][2]["role"] = "TOTAL"

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_integrity_invalid",
    ):
        ManagedDocumentLlmViewV2Factory.create(tampered, schema)


def test_factory_rejects_same_id_schema_tampering(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    same_id_tamper = copy.deepcopy(schema)
    same_id_tamper["$defs"]["tableContent"][
        "additionalProperties"
    ] = True
    assert same_id_tamper["$id"] == schema["$id"]

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_schema_hash_invalid",
    ):
        ManagedDocumentLlmViewV2Factory.create(
            managed_document,
            same_id_tamper,
        )


def test_independent_auditor_rejects_private_field_in_valid_tag(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    original = next(
        line for line in view.splitlines() if line.startswith("BLOCK_CONTENT ")
    )
    content = json.loads(original.removeprefix("BLOCK_CONTENT "))
    content["bbox"] = [0, 0, 1, 1]
    replacement = "BLOCK_CONTENT " + json.dumps(
        content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )

    with pytest.raises(
        ManagedDocumentLlmViewV2AuditError,
        match="llm_document_view_v2_private_field_forbidden",
    ):
        ManagedDocumentLlmViewV2Auditor().audit(
            view.replace(original, replacement, 1)
        )


@pytest.mark.parametrize(
    ("private_key", "private_value"),
    [
        ("artifact_ref", "private://source"),
        ("continuation_evidence_ids", ["geometry_continuation"]),
    ],
)
def test_independent_auditor_rejects_private_source_context_fields(
    schema: dict[str, Any],
    managed_document: dict[str, Any],
    private_key: str,
    private_value: Any,
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    original = next(
        line
        for line in view.splitlines()
        if line.startswith("SOURCE_CONTEXT ")
    )
    context = json.loads(original.removeprefix("SOURCE_CONTEXT "))
    context[private_key] = private_value
    replacement = "SOURCE_CONTEXT " + json.dumps(
        context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )

    with pytest.raises(
        ManagedDocumentLlmViewV2AuditError,
        match="llm_document_view_v2_private_field_forbidden",
    ):
        ManagedDocumentLlmViewV2Auditor().audit(
            view.replace(original, replacement, 1)
        )


@pytest.mark.parametrize(
    ("tag", "private_key"),
    [
        ("SOURCE_CONTEXT", "artifactRef"),
        ("SOURCE_CONTEXT", "privateArtifact"),
        ("QUALITY", "sourceWordId"),
        ("QUALITY", "documentId"),
        ("QUALITY", "continuationEvidenceIds"),
    ],
)
def test_independent_auditor_rejects_camel_case_private_fields(
    schema: dict[str, Any],
    managed_document: dict[str, Any],
    tag: str,
    private_key: str,
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = _replace_json_tag(
        view,
        tag,
        lambda value: value | {private_key: "private probe"},
    )

    with pytest.raises(
        ManagedDocumentLlmViewV2AuditError,
        match="llm_document_view_v2_private_field_forbidden",
    ):
        ManagedDocumentLlmViewV2Auditor().audit(changed_view)


@pytest.mark.parametrize(
    "constant",
    ["NaN", "Infinity", "-Infinity"],
)
def test_independent_auditor_rejects_non_json_numeric_constants(
    schema: dict[str, Any],
    managed_document: dict[str, Any],
    constant: str,
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    original = next(
        line
        for line in view.splitlines()
        if line.startswith("SOURCE_CONTEXT ")
    )
    raw_context = original.removeprefix("SOURCE_CONTEXT ")
    replacement = "SOURCE_CONTEXT " + raw_context.replace(
        '"source_details":{',
        f'"source_details":{{"probe":{constant},',
        1,
    )

    with pytest.raises(
        ManagedDocumentLlmViewV2AuditError,
        match="llm_document_view_v2_non_finite_number_forbidden",
    ):
        ManagedDocumentLlmViewV2Auditor().audit(
            view.replace(original, replacement, 1)
        )


@pytest.mark.parametrize(
    "private_value_getter",
    [
        lambda document: document["source"]["artifact"]["ref"],
        lambda document: document["geometry_evidence"][0][
            "geometry_evidence_id"
        ],
        lambda document: document["geometry_evidence"][0][
            "evidence_checksum_sha256"
        ],
        lambda document: document["source_word_ownership"][0][
            "source_word_id"
        ],
    ],
)
def test_factory_rejects_private_values_echoed_by_control_text(
    schema: dict[str, Any],
    managed_document: dict[str, Any],
    private_value_getter: Any,
) -> None:
    leaked = copy.deepcopy(managed_document)
    private_value = private_value_getter(leaked)
    leaked["quality"]["issue_ledger"] = [
        {
            "issue_id": "issue_private_echo",
            "code": "private_echo_probe",
            "severity": "WARNING",
            "message": private_value,
            "anchor_ids": ["anchor_paragraph"],
            "block_ids": ["block_context"],
            "relation_ids": [],
            "recoverability": "RECOVERABLE",
            "requires_source_reread": False,
        }
    ]
    leaked = ManagedDocumentContractV2Validator(schema).seal(leaked).payload

    with pytest.raises(
        ValueError, match="llm_document_view_v2_private_source_leak"
    ):
        ManagedDocumentLlmViewV2Factory.create(leaked, schema)


@pytest.mark.parametrize(
    "private_ref",
    [
        r"C:\private\source.pdf",
        'private://source/with-"quote"',
        "private://source/with\nnewline",
    ],
)
def test_factory_rejects_json_escaped_private_ref_echo(
    schema: dict[str, Any], private_ref: str
) -> None:
    leaked = _candidate()
    leaked["source"]["artifact"]["ref"] = private_ref
    leaked["quality"]["issue_ledger"] = [
        _issue(
            "issue_private_escaped_echo",
            private_ref,
            anchor_ids=["anchor_paragraph"],
            block_ids=["block_context"],
        )
    ]
    leaked = ManagedDocumentContractV2Validator(schema).seal(leaked).payload

    with pytest.raises(
        ValueError, match="llm_document_view_v2_private_source_leak"
    ):
        ManagedDocumentLlmViewV2Factory.create(leaked, schema)


def test_factory_rejects_private_locator_value_echoed_by_control_text(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    leaked = copy.deepcopy(managed_document)
    private_ref = "parser_word_123_private"
    leaked["anchors"][0]["locator"]["source_block_ref"] = private_ref
    leaked["quality"]["issue_ledger"] = [
        {
            "issue_id": "issue_private_locator_echo",
            "code": "private_locator_echo_probe",
            "severity": "WARNING",
            "message": private_ref,
            "anchor_ids": ["anchor_paragraph"],
            "block_ids": ["block_context"],
            "relation_ids": [],
            "recoverability": "RECOVERABLE",
            "requires_source_reread": False,
        }
    ]
    leaked = ManagedDocumentContractV2Validator(schema).seal(leaked).payload

    with pytest.raises(
        ValueError, match="llm_document_view_v2_private_source_leak"
    ):
        ManagedDocumentLlmViewV2Factory.create(leaked, schema)


def test_factory_rejects_short_private_value_exact_echo(
    schema: dict[str, Any],
) -> None:
    private_ref = "secret"
    leaked = _candidate()
    leaked["source"]["artifact"]["ref"] = private_ref
    leaked["quality"]["issue_ledger"] = [
        _issue(
            "issue_short_private_echo",
            private_ref,
            anchor_ids=["anchor_paragraph"],
            block_ids=["block_context"],
        )
    ]
    leaked = ManagedDocumentContractV2Validator(schema).seal(leaked).payload

    with pytest.raises(
        ValueError, match="llm_document_view_v2_private_source_leak"
    ):
        ManagedDocumentLlmViewV2Factory.create(leaked, schema)


def test_private_taint_scan_allows_short_token_as_public_substring(
    schema: dict[str, Any],
) -> None:
    candidate = _candidate()
    candidate["anchors"][0]["locator"]["source_block_ref"] = "a"
    candidate["blocks"][0]["content"]["raw_text"] = "Data"
    managed_document = ManagedDocumentContractV2Validator(schema).seal(
        candidate
    ).payload

    view = ManagedDocumentLlmViewV2Factory.create(managed_document, schema)

    assert 'BLOCK_CONTENT {"join_events":[],"raw_text":"Data"}' in view.text
    assert "document_id" not in ManagedDocumentLlmViewV2Auditor().audit(
        view.text
    ).payload


def test_independent_auditor_rejects_invalid_typed_source_context(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    original = next(
        line
        for line in view.splitlines()
        if line.startswith("SOURCE_CONTEXT ")
    )
    context = json.loads(original.removeprefix("SOURCE_CONTEXT "))
    context["source_details"]["encrypted_status"] = "NOT_A_REAL_STATUS"
    replacement = "SOURCE_CONTEXT " + json.dumps(
        context, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )

    with pytest.raises(
        ManagedDocumentLlmViewV2AuditError,
        match="llm_document_view_v2_source_details_invalid",
    ):
        ManagedDocumentLlmViewV2Auditor().audit(
            view.replace(original, replacement, 1)
        )


@pytest.mark.parametrize(
    ("header_path", "error_code"),
    [
        (
            ["entry_header_amount"],
            "llm_document_view_v2_header_path_binding_invalid",
        ),
        ([], "llm_document_view_v2_header_path_issue_missing"),
    ],
)
def test_independent_auditor_rejects_invalid_header_path_binding(
    schema: dict[str, Any],
    managed_document: dict[str, Any],
    header_path: list[str],
    error_code: str,
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = _replace_json_tag(
        view, "COLUMN_HEADER_PATH", lambda _: header_path
    )

    with pytest.raises(ManagedDocumentLlmViewV2AuditError, match=error_code):
        ManagedDocumentLlmViewV2Auditor().audit(changed_view)


def test_header_path_requires_bound_entry_even_when_coverage_mentions_column(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = _replace_scoped_json_tags(
        view,
        begin_marker="ENTRY_BEGIN",
        end_marker="ENTRY_END",
        identity_tag="ENTRY_ID",
        identity="entry_header_description",
        replacements={
            "ENTRY_COLUMN_BINDING_STATUS": "NOT_APPLICABLE",
            "ENTRY_LOGICAL_COLUMN_ID": None,
            "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [
                "column_description",
                "column_amount",
            ],
        },
    )

    with pytest.raises(
        ManagedDocumentLlmViewV2AuditError,
        match="llm_document_view_v2_header_path_binding_invalid",
    ):
        ManagedDocumentLlmViewV2Auditor().audit(changed_view)


@pytest.mark.parametrize(
    ("replacements", "error_code"),
    [
        (
            {
                "ENTRY_COLUMN_BINDING_STATUS": "BOUND",
                "ENTRY_LOGICAL_COLUMN_ID": None,
                "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [],
            },
            "llm_document_view_v2_entry_binding_invalid",
        ),
        (
            {
                "ENTRY_LOGICAL_COLUMN_ID": "column_amount",
                "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [
                    "column_description",
                    "column_amount",
                ],
            },
            "llm_document_view_v2_direct_covered_column_invalid",
        ),
        (
            {
                "ENTRY_COLUMN_BINDING_STATUS": "NOT_APPLICABLE",
                "ENTRY_LOGICAL_COLUMN_ID": "column_description",
            },
            "llm_document_view_v2_unbound_column_invalid",
        ),
        (
            {
                "ENTRY_COLUMN_BINDING_STATUS": "NOT_APPLICABLE",
                "ENTRY_LOGICAL_COLUMN_ID": None,
                "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [
                    "column_description",
                    "column_amount",
                ],
            },
            "llm_document_view_v2_unbound_column_invalid",
        ),
        (
            {
                "ENTRY_LOGICAL_COLUMN_ID": None,
                "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [
                    "column_description",
                    "column_description",
                ],
            },
            "llm_document_view_v2_covered_column_duplicate_invalid",
        ),
        (
            {
                "ENTRY_LOGICAL_COLUMN_ID": None,
                "ENTRY_COVERS_LOGICAL_COLUMN_IDS": ["column_description"],
            },
            "llm_document_view_v2_covered_column_count_invalid",
        ),
        (
            {
                "ENTRY_LOGICAL_COLUMN_ID": None,
                "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [
                    "column_amount",
                    "column_description",
                ],
            },
            "llm_document_view_v2_covered_column_order_invalid",
        ),
        (
            {
                "ENTRY_LOGICAL_COLUMN_ID": None,
                "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [
                    "column_description",
                    "column_missing",
                ],
            },
            "llm_document_view_v2_covered_column_invalid",
        ),
        (
            {
                "ENTRY_COLUMN_BINDING_STATUS": "UNKNOWN",
                "ENTRY_LOGICAL_COLUMN_ID": None,
                "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [],
                "ENTRY_ISSUE_IDS": [],
            },
            "llm_document_view_v2_unknown_column_issue_missing",
        ),
        (
            {
                "ENTRY_COLUMN_BINDING_STATUS": "UNKNOWN",
                "ENTRY_LOGICAL_COLUMN_ID": None,
                "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [],
                "ENTRY_ISSUE_IDS": ["issue_not_in_top_level_ledger"],
            },
            "llm_document_view_v2_unknown_column_issue_invalid",
        ),
    ],
)
def test_independent_auditor_enforces_entry_binding_truth_table(
    schema: dict[str, Any],
    managed_document: dict[str, Any],
    replacements: dict[str, Any],
    error_code: str,
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = _replace_scoped_json_tags(
        view,
        begin_marker="ENTRY_BEGIN",
        end_marker="ENTRY_END",
        identity_tag="ENTRY_ID",
        identity="entry_cash",
        replacements=replacements,
    )

    with pytest.raises(ManagedDocumentLlmViewV2AuditError, match=error_code):
        ManagedDocumentLlmViewV2Auditor().audit(changed_view)


def test_independent_auditor_accepts_unknown_binding_with_resolved_issue(
    schema: dict[str, Any],
) -> None:
    candidate = _candidate()
    issue = _issue(
        "issue_cash_column_unknown",
        "Cash column cannot be resolved",
        anchor_ids=["anchor_cash"],
        block_ids=["block_statement"],
    )
    candidate["quality"]["status"] = "PARTIAL"
    candidate["quality"]["issue_ledger"] = [issue]
    table = candidate["blocks"][1]["content"]
    table["completeness_status"] = "PARTIAL"
    entry = _table_entry(candidate, "entry_cash")
    entry["column_binding_status"] = "UNKNOWN"
    entry["logical_column_id"] = None
    entry["covers_logical_column_ids"] = []
    entry["issue_ids"] = [issue["issue_id"]]
    managed_document = ManagedDocumentContractV2Validator(schema).seal(
        candidate
    ).payload

    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    parsed = ManagedDocumentLlmViewV2Auditor().audit(view).payload

    assert _table_entry(parsed, "entry_cash")["issue_ids"] == [
        "issue_cash_column_unknown"
    ]


def test_independent_auditor_requires_summary_coverage_direct_first(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = _replace_scoped_json_tags(
        view,
        begin_marker="ROW_BEGIN",
        end_marker="ROW_END",
        identity_tag="ROW_ID",
        identity="row_cash",
        replacements={"ROW_ROLE": "TOTAL"},
    )
    changed_view = _replace_scoped_json_tags(
        changed_view,
        begin_marker="ENTRY_BEGIN",
        end_marker="ENTRY_END",
        identity_tag="ENTRY_ID",
        identity="entry_cash",
        replacements={
            "ENTRY_LOGICAL_COLUMN_ID": None,
            "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [
                "column_description",
                "column_amount",
            ],
        },
    )

    with pytest.raises(
        ManagedDocumentLlmViewV2AuditError,
        match="llm_document_view_v2_summary_binding_invalid",
    ):
        ManagedDocumentLlmViewV2Auditor().audit(changed_view)


def test_independent_auditor_rejects_unresolved_nesting_without_issue(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = _replace_json_tag(
        view, "ROW_NESTING_LEVEL", lambda _: 2
    )

    with pytest.raises(
        ManagedDocumentLlmViewV2AuditError,
        match="llm_document_view_v2_unresolved_parent_issue_missing",
    ):
        ManagedDocumentLlmViewV2Auditor().audit(changed_view)


def test_independent_auditor_rejects_source_part_pointer_page_mismatch(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = _replace_json_tag(view, "SOURCE_PART_PAGE", lambda _: 2)

    with pytest.raises(
        ManagedDocumentLlmViewV2AuditError,
        match="llm_document_view_v2_source_part_page_invalid",
    ):
        ManagedDocumentLlmViewV2Auditor().audit(changed_view)


def test_independent_auditor_has_stdlib_only_imports() -> None:
    tree = ast.parse(AUDITOR_PATH.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported <= {
        "__future__",
        "dataclasses",
        "hashlib",
        "json",
        "typing",
    }
    source = AUDITOR_PATH.read_text(encoding="utf-8")
    assert "managed_document_llm_view_v2" not in source
    assert "managed_document_contracts" not in source


def test_sealed_row_checklists_pass_exact_parity(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    managed_checklist = build_managed_document_v2_row_checklist(
        managed_document
    )
    view_checklist = build_llm_view_v2_row_checklist(view)
    comparison = compare_row_checklists(managed_checklist, view_checklist)

    assert managed_checklist["inventory"] == {
        "document_records_total": 1,
        "source_context_records_total": 1,
        "metadata_fields_total": 8,
        "blocks_total": 2,
        "non_table_blocks_total": 1,
        "tables_total": 1,
        "table_associations_total": 1,
        "source_parts_total": 1,
        "columns_total": 2,
        "header_paths_total": 2,
        "rows_total": 3,
        "entries_total": 5,
        "relations_total": 0,
        "quality_records_total": 1,
        "issues_total": 0,
        "losses_total": 0,
        "pointer_bindings_total": 28,
    }
    assert comparison["terminal_status"] == "PASSED"
    assert comparison["critical_mismatches_total"] == 0
    assert all(
        item["status"] == "MATCH"
        for item in comparison["comparison_dimensions"]
    )


def test_row_parity_detects_changed_entry_value(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = view.replace('ENTRY_TEXT "679"', 'ENTRY_TEXT "680"', 1)
    comparison = compare_row_checklists(
        build_managed_document_v2_row_checklist(managed_document),
        build_llm_view_v2_row_checklist(changed_view),
    )

    assert comparison["terminal_status"] == "FAILED"
    assert "WRONG_ENTRY_VALUE" in comparison["critical_mismatch_categories"]
    entry = next(
        item
        for item in comparison["comparison_dimensions"]
        if item["dimension"] == "ENTRY"
    )
    assert entry["status"] == "MISMATCH"


def test_managed_checklist_rejects_synchronously_tampered_document_and_view(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    tampered_document = copy.deepcopy(managed_document)
    table = next(
        block["content"]
        for block in tampered_document["blocks"]
        if block["block_type"] == "TABLE"
    )
    table["ordered_rows"][2]["entries"][1]["text"] = "680"
    tampered_view = view.replace('ENTRY_TEXT "679"', 'ENTRY_TEXT "680"', 1)

    assert build_llm_view_v2_row_checklist(tampered_view)["terminal_status"] == (
        "PASSED"
    )
    with pytest.raises(
        ValueError,
        match="llm_view_v2_managed_document_integrity_invalid",
    ):
        build_managed_document_v2_row_checklist(tampered_document)


@pytest.mark.parametrize(
    ("tag", "mutator", "dimension", "category"),
    [
        (
            "SOURCE_CONTEXT",
            lambda value: value | {"mime_type": "application/x-pdf"},
            "SOURCE_CONTEXT",
            "WRONG_SOURCE_CONTEXT",
        ),
        (
            "METADATA",
            lambda value: value | {"value": "mutated metadata"},
            "METADATA",
            "WRONG_METADATA",
        ),
        (
            "RESTORATION",
            lambda value: value | {"status": "UNKNOWN"},
            "BLOCK",
            "WRONG_RESTORATION",
        ),
        (
            "BLOCK_CONTENT",
            lambda value: value | {"raw_text": "mutated block content"},
            "NON_TABLE_BLOCK_CONTENT",
            "WRONG_NON_TABLE_BLOCK_CONTENT",
        ),
        (
            "QUALITY",
            lambda value: value
            | {"source_elements_total": value["source_elements_total"] + 1},
            "QUALITY",
            "WRONG_QUALITY",
        ),
    ],
)
def test_parity_rejects_non_row_model_surface_mutation(
    schema: dict[str, Any],
    managed_document: dict[str, Any],
    tag: str,
    mutator: Any,
    dimension: str,
    category: str,
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = _replace_json_tag(view, tag, mutator)

    ManagedDocumentLlmViewV2Auditor().audit(changed_view)
    comparison = compare_row_checklists(
        build_managed_document_v2_row_checklist(managed_document),
        build_llm_view_v2_row_checklist(changed_view),
    )

    assert comparison["terminal_status"] == "FAILED"
    assert category in comparison["critical_mismatch_categories"]
    assert _comparison_dimension(comparison, dimension)["status"] == "MISMATCH"


def test_parity_rejects_dropped_table_issue_after_auditor_accepts(
    schema: dict[str, Any],
) -> None:
    managed_document = ManagedDocumentContractV2Validator(schema).seal(
        _candidate_with_table_issue()
    ).payload
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    assert _compare_document_to_view(managed_document, view)[
        "terminal_status"
    ] == "PASSED"

    changed_view = _replace_json_tag(
        view, "TABLE_ISSUE_IDS", lambda _: []
    )
    audited = ManagedDocumentLlmViewV2Auditor().audit(changed_view).payload
    table = next(
        block["content"]
        for block in audited["blocks"]
        if block["block_type"] == "TABLE"
    )
    assert table["issues"] == []

    comparison = _compare_document_to_view(managed_document, changed_view)
    assert comparison["terminal_status"] == "FAILED"
    assert "WRONG_TABLE_ISSUE_BINDING" in comparison[
        "critical_mismatch_categories"
    ]
    assert _comparison_dimension(comparison, "TABLE_ASSOCIATION")[
        "status"
    ] == "MISMATCH"


@pytest.mark.parametrize(
    ("mutator", "category"),
    [
        (
            lambda value: value | {"status": "CONFLICTING"},
            "WRONG_RELATION_STATUS",
        ),
        (
            lambda value: value
            | {
                "target": {
                    "block_id": "block_context",
                    "row_id": None,
                    "entry_id": None,
                }
            },
            "WRONG_RELATION_ENDPOINT",
        ),
    ],
)
def test_parity_rejects_relation_payload_mutation(
    schema: dict[str, Any], mutator: Any, category: str
) -> None:
    managed_document = ManagedDocumentContractV2Validator(schema).seal(
        _candidate_with_relation()
    ).payload
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    assert _compare_document_to_view(managed_document, view)[
        "terminal_status"
    ] == "PASSED"

    changed_view = _replace_json_tag(view, "RELATION", mutator)
    ManagedDocumentLlmViewV2Auditor().audit(changed_view)
    comparison = _compare_document_to_view(managed_document, changed_view)

    assert comparison["terminal_status"] == "FAILED"
    assert category in comparison["critical_mismatch_categories"]
    assert _comparison_dimension(comparison, "RELATION")[
        "status"
    ] == "MISMATCH"


def test_parity_rejects_mutated_issue_payload(
    schema: dict[str, Any],
) -> None:
    managed_document = ManagedDocumentContractV2Validator(schema).seal(
        _candidate_with_table_issue()
    ).payload
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = _replace_json_tag(
        view,
        "ISSUE",
        lambda value: value | {"message": "mutated public issue"},
    )

    ManagedDocumentLlmViewV2Auditor().audit(changed_view)
    comparison = _compare_document_to_view(managed_document, changed_view)

    assert comparison["terminal_status"] == "FAILED"
    assert "WRONG_ISSUE" in comparison["critical_mismatch_categories"]
    assert _comparison_dimension(comparison, "ISSUE")["status"] == "MISMATCH"


def test_parity_rejects_mutated_loss_payload(
    schema: dict[str, Any],
) -> None:
    managed_document = ManagedDocumentContractV2Validator(schema).seal(
        _candidate_with_loss()
    ).payload
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    assert _compare_document_to_view(managed_document, view)[
        "terminal_status"
    ] == "PASSED"
    changed_view = _replace_json_tag(
        view,
        "LOSS",
        lambda value: value | {"reason": "mutated public loss reason"},
    )

    ManagedDocumentLlmViewV2Auditor().audit(changed_view)
    comparison = _compare_document_to_view(managed_document, changed_view)

    assert comparison["terminal_status"] == "FAILED"
    assert "WRONG_LOSS" in comparison["critical_mismatch_categories"]
    assert _comparison_dimension(comparison, "LOSS")["status"] == "MISMATCH"


def test_checklist_comparison_rejects_resealed_input_tampering(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    managed_checklist = build_managed_document_v2_row_checklist(
        managed_document
    )
    view_checklist = build_llm_view_v2_row_checklist(view)
    view_checklist["dimensions"]["ENTRY"]["items"] = []
    _reseal_checklist(view_checklist)

    with pytest.raises(ValueError, match="llm_view_v2_row_checklist_invalid"):
        compare_row_checklists(managed_checklist, view_checklist)


def test_parity_diagnostics_use_exact_doc6_taxonomy(
    schema: dict[str, Any], managed_document: dict[str, Any]
) -> None:
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    managed = build_managed_document_v2_row_checklist(managed_document)
    parsed_view = build_llm_view_v2_row_checklist(view)

    split = copy.deepcopy(parsed_view)
    split_table = copy.deepcopy(
        split["dimensions"]["TABLE_IDENTITY"]["items"][0]
    )
    split_table["table_id"] = "table_split_probe"
    split_table["block_id"] = "block_split_probe"
    split["dimensions"]["TABLE_IDENTITY"]["items"].append(split_table)
    _reseal_dimension(split, "TABLE_IDENTITY", "tables_total")
    split_result = compare_row_checklists(managed, split)
    assert "FALSE_TABLE_SPLIT" in split_result[
        "critical_mismatch_categories"
    ]

    merged = copy.deepcopy(parsed_view)
    merged["dimensions"]["TABLE_IDENTITY"]["items"] = []
    _reseal_dimension(merged, "TABLE_IDENTITY", "tables_total")
    merge_result = compare_row_checklists(managed, merged)
    assert "FALSE_TABLE_MERGE" in merge_result[
        "critical_mismatch_categories"
    ]

    false_continuation = copy.deepcopy(parsed_view)
    false_continuation["dimensions"]["SOURCE_PART"]["items"][0][
        "continuation_status"
    ] = "START"
    _reseal_dimension(
        false_continuation, "SOURCE_PART", "source_parts_total"
    )
    false_continuation_result = compare_row_checklists(
        managed, false_continuation
    )
    assert "FALSE_CONTINUATION" in false_continuation_result[
        "critical_mismatch_categories"
    ]

    expected_continuation = copy.deepcopy(managed)
    expected_continuation["dimensions"]["SOURCE_PART"]["items"][0][
        "continuation_status"
    ] = "START"
    _reseal_dimension(
        expected_continuation, "SOURCE_PART", "source_parts_total"
    )
    missing_continuation_result = compare_row_checklists(
        expected_continuation, parsed_view
    )
    assert "MISSING_CONTINUATION" in missing_continuation_result[
        "critical_mismatch_categories"
    ]

    for role, category in (
        ("SUBTOTAL", "WRONG_SUBTOTAL_BINDING"),
        ("TOTAL", "WRONG_TOTAL_BINDING"),
    ):
        summary = copy.deepcopy(managed)
        summary["dimensions"]["ROW"]["items"][2]["role"] = role
        _reseal_dimension(summary, "ROW", "rows_total")
        summary_result = compare_row_checklists(summary, parsed_view)
        assert category in summary_result["critical_mismatch_categories"]

    duplicated = copy.deepcopy(parsed_view)
    duplicate_entry = copy.deepcopy(
        duplicated["dimensions"]["ENTRY"]["items"][-1]
    )
    duplicate_entry["entry_id"] = "entry_duplicate_probe"
    duplicated["dimensions"]["ENTRY"]["items"].append(duplicate_entry)
    _reseal_dimension(duplicated, "ENTRY", "entries_total")
    duplicated_result = compare_row_checklists(managed, duplicated)
    assert "DUPLICATED_SOURCE_VALUE" in duplicated_result[
        "critical_mismatch_categories"
    ]
    assert "FALSE_TABLE_SPLIT_OR_MERGE" not in {
        *split_result["critical_mismatch_categories"],
        *merge_result["critical_mismatch_categories"],
    }


@pytest.mark.parametrize(
    ("row_role", "specific_category"),
    [
        ("SUBTOTAL", "WRONG_SUBTOTAL_BINDING"),
        ("TOTAL", "WRONG_TOTAL_BINDING"),
    ],
)
def test_valid_audited_three_column_tamper_has_summary_binding_diagnostic(
    schema: dict[str, Any],
    row_role: str,
    specific_category: str,
) -> None:
    candidate = _three_column_candidate(
        row_role=row_role,
        direct_column_id="column_description",
    )
    managed_document = ManagedDocumentContractV2Validator(schema).seal(
        candidate
    ).payload
    view = ManagedDocumentLlmViewV2Factory.create(
        managed_document, schema
    ).text
    changed_view = _replace_scoped_json_tags(
        view,
        begin_marker="ENTRY_BEGIN",
        end_marker="ENTRY_END",
        identity_tag="ENTRY_ID",
        identity="entry_cash",
        replacements={
            "ENTRY_LOGICAL_COLUMN_ID": "column_amount",
            "ENTRY_COVERS_LOGICAL_COLUMN_IDS": [
                "column_amount",
                "column_auxiliary",
            ],
        },
    )

    ManagedDocumentLlmViewV2Auditor().audit(changed_view)
    comparison = _compare_document_to_view(managed_document, changed_view)

    assert comparison["terminal_status"] == "FAILED"
    assert set(comparison["critical_mismatch_categories"]) == {
        "WRONG_ENTRY_COLUMN_BINDING",
        specific_category,
    }
    assert set(
        _comparison_dimension(comparison, "ENTRY")[
            "critical_categories"
        ]
    ) == {"WRONG_ENTRY_COLUMN_BINDING", specific_category}


def test_factory_markers_pin_inactive_row_owner() -> None:
    assert "ManagedDocumentLlmViewV2Factory.create" in FACTORY_REQUIRED
    assert "product routing" in FORBIDDEN
    assert "grid projection" in FORBIDDEN


def _candidate() -> dict[str, Any]:
    anchors = [
        _anchor("anchor_paragraph"),
        _anchor("anchor_table"),
        _anchor("anchor_header_description"),
        _anchor("anchor_header_amount"),
        _anchor("anchor_assets"),
        _anchor("anchor_cash"),
        _anchor("anchor_amount"),
    ]
    metadata = {
        name: _unknown_metadata()
        for name in (
            "document_type",
            "title",
            "issuer",
            "document_date",
            "reporting_period",
            "owner_or_account",
            "language",
            "primary_currency",
        )
    }
    metadata["additional"] = []
    entries = [
        ("entry_header_description", "anchor_header_description"),
        ("entry_header_amount", "anchor_header_amount"),
        ("entry_assets", "anchor_assets"),
        ("entry_cash", "anchor_cash"),
        ("entry_amount", "anchor_amount"),
    ]
    return {
        "schema_version": "broker_reports_managed_document_v2",
        "document_id": "document_view_v2_fixture",
        "information_partition": {
            "CONTENT": ["/metadata", "/blocks/*/content"],
            "PROVENANCE": ["/source", "/anchors", "/relations"],
            "CONTROL": [
                "/information_partition",
                "/blocks/*/restoration",
                "/quality",
            ],
            "PRIVATE_SOURCE": [
                "/document_id",
                "/source/artifact",
                "/anchors/*/locator/private_locator",
                "/blocks/*/content/private_artifact",
                "/geometry_evidence",
                "/source_word_ownership",
            ],
        },
        "source": {
            "information_class": "PROVENANCE",
            "format": "PDF",
            "artifact": _present_private("private://source.pdf"),
            "checksum_sha256": "a" * 64,
            "mime_type": "application/pdf",
            "size_bytes": 123,
            "source_part_count": 1,
            "normalizer": {"name": "synthetic", "version": "1"},
            "created_at": "2026-08-02T00:00:00Z",
            "source_details": {
                "kind": "PDF",
                "encrypted_status": "NOT_ENCRYPTED",
            },
        },
        "metadata": metadata,
        "anchors": anchors,
        "geometry_evidence": [
            {
                "information_class": "PRIVATE_SOURCE",
                "geometry_evidence_id": "geometry_table_region",
                "kind": "TABLE_REGION",
                "origin": "DETERMINISTIC_DERIVED",
                "source_anchor_ids": [
                    anchor["anchor_id"] for anchor in anchors
                ],
                "private_artifact": _present_private(
                    "private://geometry/table.json"
                ),
                "evidence_checksum_sha256": "b" * 64,
                "issue_ids": [],
            }
        ],
        "source_word_ownership": [
            {
                "information_class": "PRIVATE_SOURCE",
                "source_word_id": _source_word_id_for_ref(
                    f"word_ref_{anchor_id}"
                ),
                "table_id": "table_statement",
                "owner_status": "OWNED",
                "owner_entry_id": entry_id,
                "duplicate_of_source_word_id": None,
                "source_anchor_id": anchor_id,
                "issue_ids": [],
            }
            for entry_id, anchor_id in entries
        ],
        "blocks": [
            {
                "block_id": "block_context",
                "ordinal": 0,
                "block_type": "PARAGRAPH",
                "content": {
                    "information_class": "CONTENT",
                    "raw_text": 'Context\nTABLE_END and literal "bbox"',
                    "join_events": [],
                },
                "source_anchor_ids": ["anchor_paragraph"],
                "restoration": _restoration(),
                "issue_ids": [],
            },
            {
                "block_id": "block_statement",
                "ordinal": 1,
                "block_type": "TABLE",
                "content": _table_content(),
                "source_anchor_ids": ["anchor_table"],
                "restoration": _restoration(),
                "issue_ids": [],
            },
        ],
        "relations": [],
        "quality": {
            "information_class": "CONTROL",
            "status": "COMPLETE",
            "source_elements_total": 2,
            "preserved_blocks_total": 2,
            "unknown_blocks_total": 0,
            "unsupported_elements_total": 0,
            "known_losses_total": 0,
            "conflicts_total": 0,
            "unaccounted_context_loss_total": 0,
            "blocking_losses_total": 0,
            "issue_ledger": [],
            "loss_ledger": [],
        },
    }


def _three_column_candidate(
    *, row_role: str, direct_column_id: str | None
) -> dict[str, Any]:
    candidate = _candidate()
    auxiliary_anchor = _anchor("anchor_header_auxiliary")
    candidate["anchors"].append(auxiliary_anchor)
    candidate["geometry_evidence"][0]["source_anchor_ids"].append(
        auxiliary_anchor["anchor_id"]
    )
    candidate["geometry_evidence"].append(
        {
            "information_class": "PRIVATE_SOURCE",
            "geometry_evidence_id": "geometry_cash_coverage",
            "kind": "VISUAL_COVERAGE",
            "origin": "DETERMINISTIC_DERIVED",
            "source_anchor_ids": ["anchor_cash"],
            "private_artifact": _present_private(
                "private://geometry/cash-coverage.json"
            ),
            "evidence_checksum_sha256": "c" * 64,
            "issue_ids": [],
        }
    )
    candidate["source_word_ownership"].append(
        {
            "information_class": "PRIVATE_SOURCE",
            "source_word_id": _source_word_id_for_ref(
                f"word_ref_{auxiliary_anchor['anchor_id']}"
            ),
            "table_id": "table_statement",
            "owner_status": "OWNED",
            "owner_entry_id": "entry_header_auxiliary",
            "duplicate_of_source_word_id": None,
            "source_anchor_id": auxiliary_anchor["anchor_id"],
            "issue_ids": [],
        }
    )
    table = candidate["blocks"][1]["content"]
    header_row = table["ordered_rows"][0]
    header_row["entries"].append(
        _entry(
            "entry_header_auxiliary",
            2,
            "VALUE",
            "Auxiliary",
            "column_auxiliary",
            auxiliary_anchor["anchor_id"],
        )
    )
    header_row["source_anchor_ids"].append(auxiliary_anchor["anchor_id"])
    table["logical_columns"].append(
        _column(
            "column_auxiliary",
            2,
            "entry_header_auxiliary",
            auxiliary_anchor["anchor_id"],
        )
    )
    cash_row = table["ordered_rows"][2]
    cash_row["role"] = row_role
    cash_entry = _table_entry(candidate, "entry_cash")
    cash_entry["logical_column_id"] = direct_column_id
    cash_entry["covers_logical_column_ids"] = [
        "column_description",
        "column_amount",
        "column_auxiliary",
    ]
    cash_entry["geometry_evidence_ids"].append("geometry_cash_coverage")
    return candidate


def _candidate_with_table_issue() -> dict[str, Any]:
    candidate = _candidate()
    issue = _issue(
        "issue_table_surface",
        "Public table issue",
        anchor_ids=["anchor_table"],
        block_ids=["block_statement"],
    )
    candidate["quality"]["issue_ledger"] = [issue]
    candidate["blocks"][1]["content"]["issues"] = [issue["issue_id"]]
    return candidate


def _candidate_with_relation() -> dict[str, Any]:
    candidate = _candidate()
    relation = {
        "information_class": "PROVENANCE",
        "relation_id": "relation_context_statement",
        "relation_type": "BELONGS_TO_SECTION",
        "source": {
            "block_id": "block_context",
            "row_id": None,
            "entry_id": None,
        },
        "target": {
            "block_id": "block_statement",
            "row_id": None,
            "entry_id": None,
        },
        "status": "PRESENT",
        "origin": "SOURCE_EXPLICIT",
        "evidence_anchor_ids": ["anchor_table"],
        "issue_ids": [],
    }
    candidate["relations"] = [relation]
    candidate["blocks"][1]["content"]["relations"] = [
        relation["relation_id"]
    ]
    return candidate


def _candidate_with_loss() -> dict[str, Any]:
    candidate = _candidate()
    loss = {
        "loss_id": "loss_table_gap",
        "context_class": "STRUCTURE",
        "what_lost": "Public structure detail",
        "where": "Table statement",
        "reason": "Source ambiguity",
        "recoverability": "RECOVERABLE",
        "requires_source_reread": True,
        "blocks_semantic_analysis": False,
        "accounted": True,
        "anchor_ids": ["anchor_table"],
        "block_ids": ["block_statement"],
    }
    candidate["quality"]["status"] = "PARTIAL"
    candidate["quality"]["known_losses_total"] = 1
    candidate["quality"]["loss_ledger"] = [loss]
    candidate["blocks"][1]["content"]["completeness_status"] = "PARTIAL"
    candidate["blocks"][1]["content"]["known_gap_ids"] = [loss["loss_id"]]
    return candidate


def _table_content() -> dict[str, Any]:
    return {
        "information_class": "CONTENT",
        "table_id": "table_statement",
        "completeness_status": "COMPLETE",
        "ordered_rows": [
            _row(
                "row_header",
                0,
                "COLUMN_HEADER",
                0,
                None,
                [
                    _entry(
                        "entry_header_description",
                        0,
                        "LABEL",
                        "Description",
                        "column_description",
                        "anchor_header_description",
                    ),
                    _entry(
                        "entry_header_amount",
                        1,
                        "VALUE",
                        "Amount",
                        "column_amount",
                        "anchor_header_amount",
                    ),
                ],
                ["anchor_header_description", "anchor_header_amount"],
            ),
            _row(
                "row_assets",
                1,
                "GROUP_HEADER",
                0,
                None,
                [
                    _entry(
                        "entry_assets",
                        0,
                        "LABEL",
                        "Assets",
                        "column_description",
                        "anchor_assets",
                    )
                ],
                ["anchor_assets"],
            ),
            _row(
                "row_cash",
                2,
                "DATA",
                1,
                "row_assets",
                [
                    _entry(
                        "entry_cash",
                        0,
                        "LABEL",
                        "Cash",
                        "column_description",
                        "anchor_cash",
                    ),
                    _entry(
                        "entry_amount",
                        1,
                        "VALUE",
                        "679",
                        "column_amount",
                        "anchor_amount",
                    ),
                ],
                ["anchor_cash", "anchor_amount"],
            ),
        ],
        "logical_columns": [
            _column(
                "column_description",
                0,
                "entry_header_description",
                "anchor_header_description",
            ),
            _column(
                "column_amount",
                1,
                "entry_header_amount",
                "anchor_header_amount",
            ),
        ],
        "source_parts": [
            {
                "source_part_id": "source_part_statement",
                "ordinal": 0,
                "page": 1,
                "region_anchor_id": "anchor_table",
                "first_row_id": "row_header",
                "last_row_id": "row_cash",
                "continuation_status": "SINGLE",
                "geometry_evidence_ids": ["geometry_table_region"],
                "continuation_evidence_ids": [],
                "issue_ids": [],
            }
        ],
        "relations": [],
        "issues": [],
        "known_gap_ids": [],
    }


def _row(
    row_id: str,
    ordinal: int,
    role: str,
    nesting_level: int,
    parent_row_id: str | None,
    entries: list[dict[str, Any]],
    anchor_ids: list[str],
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "ordinal": ordinal,
        "role": role,
        "role_origin": "DETERMINISTIC_DERIVED",
        "nesting_level": nesting_level,
        "parent_row_id": parent_row_id,
        "entries": entries,
        "source_anchor_ids": anchor_ids,
        "geometry_evidence_ids": ["geometry_table_region"],
        "issue_ids": [],
    }


def _entry(
    entry_id: str,
    ordinal: int,
    kind: str,
    text: str,
    column_id: str,
    anchor_id: str,
) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "ordinal": ordinal,
        "kind": kind,
        "text": text,
        "origin": "SOURCE_EXPLICIT",
        "column_binding_status": "BOUND",
        "logical_column_id": column_id,
        "covers_logical_column_ids": [],
        "source_anchor_ids": [anchor_id],
        "geometry_evidence_ids": ["geometry_table_region"],
        "issue_ids": [],
    }


def _column(
    column_id: str, ordinal: int, header_entry_id: str, anchor_id: str
) -> dict[str, Any]:
    return {
        "column_id": column_id,
        "ordinal": ordinal,
        "header_path": [header_entry_id],
        "source_anchor_ids": [anchor_id],
        "geometry_evidence_ids": ["geometry_table_region"],
        "issue_ids": [],
    }


def _anchor(anchor_id: str) -> dict[str, Any]:
    return {
        "information_class": "PROVENANCE",
        "anchor_id": anchor_id,
        "source_format": "PDF",
        "checksum_sha256": "a" * 64,
        "locator": {
            "kind": "PDF",
            "source_part_index": 1,
            "page": 1,
            "source_block_ref": f"word_ref_{anchor_id}",
            "bbox": [0.0, 0.0, 10.0, 10.0],
            "private_locator": {
                "information_class": "PRIVATE_SOURCE",
                "status": "NOT_APPLICABLE",
                "ref": None,
                "checksum_sha256": None,
            },
        },
    }


def _source_word_id_for_ref(source_block_ref: str) -> str:
    canonical = json.dumps(
        [source_block_ref],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"source_word_{hashlib.sha256(canonical).hexdigest()[:24]}"


def _unknown_metadata() -> dict[str, Any]:
    return {
        "information_class": "CONTENT",
        "status": "UNKNOWN",
        "origin": "UNKNOWN_ORIGIN",
        "value": None,
        "candidates": [],
        "evidence_anchor_ids": [],
    }


def _present_private(ref: str) -> dict[str, Any]:
    return {
        "information_class": "PRIVATE_SOURCE",
        "status": "PRESENT",
        "ref": ref,
        "checksum_sha256": "a" * 64,
    }


def _restoration() -> dict[str, Any]:
    return {
        "information_class": "CONTROL",
        "status": "RESTORED",
        "classification_origin": "DETERMINISTIC_DERIVED",
        "issue_ids": [],
    }


def _issue(
    issue_id: str,
    message: str,
    *,
    anchor_ids: list[str],
    block_ids: list[str],
) -> dict[str, Any]:
    return {
        "issue_id": issue_id,
        "code": "test_public_issue",
        "severity": "WARNING",
        "message": message,
        "anchor_ids": anchor_ids,
        "block_ids": block_ids,
        "relation_ids": [],
        "recoverability": "RECOVERABLE",
        "requires_source_reread": False,
    }


def _table_entry(
    document: dict[str, Any], entry_id: str
) -> dict[str, Any]:
    return next(
        entry
        for block in document["blocks"]
        if block["block_type"] == "TABLE"
        for row in block["content"]["ordered_rows"]
        for entry in row["entries"]
        if entry["entry_id"] == entry_id
    )


def _replace_scoped_json_tags(
    view: str,
    *,
    begin_marker: str,
    end_marker: str,
    identity_tag: str,
    identity: str,
    replacements: dict[str, Any],
) -> str:
    lines = view.removesuffix("\n").split("\n")
    identity_prefix = f"{identity_tag} "
    scope: tuple[int, int] | None = None
    for start, line in enumerate(lines):
        if line != begin_marker:
            continue
        end = next(
            position
            for position in range(start + 1, len(lines))
            if lines[position] == end_marker
        )
        if any(
            candidate.startswith(identity_prefix)
            and json.loads(candidate[len(identity_prefix) :]) == identity
            for candidate in lines[start + 1 : end]
        ):
            scope = (start, end)
            break
    if scope is None:
        raise AssertionError(f"missing scoped record: {identity_tag}={identity}")

    start, end = scope
    for tag, value in replacements.items():
        prefix = f"{tag} "
        positions = [
            position
            for position in range(start + 1, end)
            if lines[position].startswith(prefix)
        ]
        if len(positions) != 1:
            raise AssertionError(
                f"expected one {tag} in {identity_tag}={identity}"
            )
        lines[positions[0]] = prefix + json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    return "\n".join(lines) + "\n"


def _replace_json_tag(view: str, tag: str, mutator: Any) -> str:
    prefix = f"{tag} "
    lines = view.removesuffix("\n").split("\n")
    index = next(
        position
        for position, line in enumerate(lines)
        if line.startswith(prefix)
    )
    value = json.loads(lines[index][len(prefix) :])
    lines[index] = prefix + json.dumps(
        mutator(copy.deepcopy(value)),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "\n".join(lines) + "\n"


def _compare_document_to_view(
    managed_document: dict[str, Any], view: str
) -> dict[str, Any]:
    return compare_row_checklists(
        build_managed_document_v2_row_checklist(managed_document),
        build_llm_view_v2_row_checklist(view),
    )


def _comparison_dimension(
    comparison: dict[str, Any], dimension: str
) -> dict[str, Any]:
    return next(
        item
        for item in comparison["comparison_dimensions"]
        if item["dimension"] == dimension
    )


def _reseal_dimension(
    checklist: dict[str, Any], dimension: str, inventory_key: str
) -> None:
    sealed = checklist["dimensions"][dimension]
    sealed["items_total"] = len(sealed["items"])
    sealed["sha256"] = _sha256_json(sealed["items"])
    checklist["inventory"][inventory_key] = sealed["items_total"]
    _reseal_checklist(checklist)


def _sha256_json(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _reseal_checklist(checklist: dict[str, Any]) -> None:
    unsigned = copy.deepcopy(checklist)
    unsigned.pop("integrity_sha256", None)
    canonical = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    checklist["integrity_sha256"] = hashlib.sha256(canonical).hexdigest()
