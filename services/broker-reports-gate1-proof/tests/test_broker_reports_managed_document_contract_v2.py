from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from broker_reports_gate1.managed_document_contracts import (
    compute_document_integrity_sha256,
)
from broker_reports_gate1.managed_document_contracts_v2 import (
    SCHEMA_CANONICAL_SHA256,
    ManagedDocumentContractV2Error,
    ManagedDocumentContractV2Validator,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
SCHEMA_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json"
)
V1_SCHEMA_PATH = SCHEMA_PATH.with_name(
    "BROKER_REPORTS_MANAGED_DOCUMENT.v1.schema.json"
)
V1_MODULE_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "managed_document_contracts.py"
)
V1_CONTRACT_PATH = SCHEMA_PATH.with_name("BROKER_REPORTS_MANAGED_DOCUMENT.v1.md")
V1_BUILDER_PATH = (
    SERVICE_ROOT / "broker_reports_gate1" / "managed_pdf_document.py"
)
V1_VIEW_PATH = (
    SERVICE_ROOT / "broker_reports_gate1" / "managed_document_llm_view.py"
)
V1_CORPUS_PATH = (
    SERVICE_ROOT
    / "tests"
    / "fixtures"
    / "broker_reports_managed_document_v1_corpus.safe.json"
)
V1_REPOSITORY_LF_SHA256 = {
    V1_CONTRACT_PATH: "ee2ddf38bef9ac61c4be9c6ba039910a975a8bb9f2ee0e3fbcd7fbaf52dc2f82",
    V1_SCHEMA_PATH: "46f9b182c945c217fe2c76fa314bd0e9d083cc9b7ba028c9ddb19e67819ae22e",
    V1_MODULE_PATH: "bce62babc12c5b21d52433b329e2535dc0f55db14c23ef54034af49c674bee92",
    V1_BUILDER_PATH: "91d9780728b494329494f8bc3513db2ceadcf7745d61ddbc2eeb22acbd73e515",
    V1_VIEW_PATH: "5b6e19d7be8ad68c58ac4a16661ef460047dbb9d4c8b99cdd8ef04b15b98ef9b",
}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return _read_json(SCHEMA_PATH)


@pytest.fixture(scope="module")
def validator(
    schema: dict[str, Any],
) -> ManagedDocumentContractV2Validator:
    return ManagedDocumentContractV2Validator(schema)


@pytest.fixture()
def candidate() -> dict[str, Any]:
    corpus = _read_json(V1_CORPUS_PATH)
    source = next(
        item
        for item in corpus["documents"]
        if item["document_id"] == "document_fixture_a_broker_report"
    )
    document = copy.deepcopy(source)
    document["schema_version"] = "broker_reports_managed_document_v2"
    document["information_partition"]["PRIVATE_SOURCE"] = [
        "/document_id",
        "/source/artifact",
        "/anchors/*/locator/private_locator",
        "/blocks/*/content/private_artifact",
        "/geometry_evidence",
        "/source_word_ownership",
    ]

    geometry_id = "geometry_fixture_table_region"
    document["geometry_evidence"] = [
        {
            "information_class": "PRIVATE_SOURCE",
            "geometry_evidence_id": geometry_id,
            "kind": "TABLE_REGION",
            "origin": "SOURCE_EXPLICIT",
            "source_anchor_ids": ["anchor_a_table"],
            "private_artifact": {
                "information_class": "PRIVATE_SOURCE",
                "status": "PRESENT",
                "ref": "private_geometry_fixture_table_region",
                "checksum_sha256": "a" * 64,
            },
            "evidence_checksum_sha256": "b" * 64,
            "issue_ids": [],
        }
    ]

    rows = [
        _row(
            "row_fixture_title",
            0,
            "TABLE_TITLE",
            [_entry("entry_fixture_title", 0, "LABEL", "Positions")],
            geometry_id,
        ),
        _row(
            "row_fixture_header",
            1,
            "COLUMN_HEADER",
            [
                _entry(
                    "entry_fixture_header_asset",
                    0,
                    "LABEL",
                    "Asset",
                    column_id="column_fixture_asset",
                ),
                _entry(
                    "entry_fixture_header_amount",
                    1,
                    "LABEL",
                    "Amount",
                    column_id="column_fixture_amount",
                ),
            ],
            geometry_id,
        ),
        _row(
            "row_fixture_data_a",
            2,
            "DATA",
            [
                _entry(
                    "entry_fixture_data_a_label",
                    0,
                    "LABEL",
                    "Synthetic A",
                    column_id="column_fixture_asset",
                ),
                _entry(
                    "entry_fixture_data_a_value",
                    1,
                    "VALUE",
                    "100.00",
                    column_id="column_fixture_amount",
                ),
            ],
            geometry_id,
        ),
        _row(
            "row_fixture_data_b",
            3,
            "DATA",
            [
                _entry(
                    "entry_fixture_data_b_label",
                    0,
                    "LABEL",
                    "Synthetic B",
                    column_id="column_fixture_asset",
                )
            ],
            geometry_id,
        ),
    ]
    table_block = next(
        item for item in document["blocks"] if item["block_type"] == "TABLE"
    )
    table_block["content"] = {
        "information_class": "CONTENT",
        "table_id": "table_fixture_a_positions",
        "completeness_status": "COMPLETE",
        "ordered_rows": rows,
        "logical_columns": [
            _column(
                "column_fixture_asset",
                0,
                ["entry_fixture_header_asset"],
                geometry_id,
            ),
            _column(
                "column_fixture_amount",
                1,
                ["entry_fixture_header_amount"],
                geometry_id,
            ),
        ],
        "source_parts": [
            {
                "source_part_id": "source_part_fixture_a_table",
                "ordinal": 0,
                "page": 1,
                "region_anchor_id": "anchor_a_table",
                "first_row_id": "row_fixture_title",
                "last_row_id": "row_fixture_data_b",
                "continuation_status": "SINGLE",
                "geometry_evidence_ids": [geometry_id],
                "continuation_evidence_ids": [],
                "issue_ids": [],
            }
        ],
        "relations": [
            "relation_a_note_for_table",
            "relation_a_table_section",
        ],
        "issues": [],
        "known_gap_ids": [],
    }

    for relation in document["relations"]:
        for endpoint in (relation["source"], relation["target"]):
            endpoint["row_id"] = endpoint.pop("row_index")
            endpoint["entry_id"] = endpoint.pop("column_index")

    entries = [
        entry
        for row in rows
        for entry in row["entries"]
    ]
    _install_unique_source_word_ownership(
        document,
        entries,
        table_id="table_fixture_a_positions",
    )
    _reseal(document)
    return document


def test_schema_is_row_first_and_has_no_grid_core(
    schema: dict[str, Any],
) -> None:
    table = schema["$defs"]["tableContent"]
    assert set(table["properties"]) == {
        "information_class",
        "table_id",
        "completeness_status",
        "ordered_rows",
        "logical_columns",
        "source_parts",
        "relations",
        "issues",
        "known_gap_ids",
        "covered_source_atom_refs",
        "covered_source_word_refs",
    }
    serialized = json.dumps(table, sort_keys=True)
    for forbidden in (
        '"rows"',
        "cell_annotations",
        "cell_spans",
        "COVERED_BY_SPAN",
        "row_index",
        "column_index",
    ):
        assert forbidden not in serialized


def test_schema_identity_is_exactly_hash_pinned(
    schema: dict[str, Any],
) -> None:
    canonical = json.dumps(
        schema,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == SCHEMA_CANONICAL_SHA256
    assert (
        ManagedDocumentContractV2Validator(schema).schema_canonical_sha256
        == SCHEMA_CANONICAL_SHA256
    )

    same_id_tamper = copy.deepcopy(schema)
    same_id_tamper["$defs"]["tableContent"][
        "additionalProperties"
    ] = True
    assert same_id_tamper["$id"] == schema["$id"]
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_schema_hash_invalid",
    ):
        ManagedDocumentContractV2Validator(same_id_tamper)


def test_schema_and_python_validator_accept_sparse_row_document(
    schema: dict[str, Any],
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    Draft202012Validator(schema).validate(candidate)
    validated = validator.validate(candidate).payload
    table = next(
        item["content"]
        for item in validated["blocks"]
        if item["block_type"] == "TABLE"
    )
    assert [len(row["entries"]) for row in table["ordered_rows"]] == [
        1,
        2,
        2,
        1,
    ]
    assert table["logical_columns"][0]["header_path"] == [
        "entry_fixture_header_asset"
    ]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_validator_rejects_non_finite_numbers_on_every_entrypoint(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
    value: float,
) -> None:
    anchor = next(
        item
        for item in candidate["anchors"]
        if item["locator"]["kind"] == "PDF"
        and isinstance(item["locator"]["bbox"], list)
    )
    anchor["locator"]["bbox"][0] = value

    for operation in (
        lambda: validator.validate(candidate),
        lambda: validator.seal(candidate),
        lambda: validator.parse_json(json.dumps({"value": value})),
    ):
        with pytest.raises(
            ManagedDocumentContractV2Error,
            match="managed_document_v2_non_finite_number_forbidden",
        ):
            operation()


def test_row_and_entry_ordinals_are_contiguous(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    table = _table(candidate)
    table["ordered_rows"][2]["ordinal"] = 8
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_row_ordinal_invalid",
    ):
        validator.validate(candidate)

    candidate = _fresh_candidate()
    table = _table(candidate)
    table["ordered_rows"][2]["entries"][1]["ordinal"] = 8
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_entry_ordinal_invalid",
    ):
        validator.validate(candidate)


def test_unknown_role_and_column_binding_require_local_issue(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    table = _table(candidate)
    table["ordered_rows"][3]["role"] = "UNKNOWN"
    table["ordered_rows"][3]["role_origin"] = "UNKNOWN_ORIGIN"
    table["completeness_status"] = "PARTIAL"
    candidate["quality"]["status"] = "PARTIAL"
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_unknown_row_issue_missing",
    ):
        validator.validate(candidate)

    issue_id = _add_issue(candidate, "unknown_row_role")
    table["ordered_rows"][3]["issue_ids"] = [issue_id]
    table["issues"] = [issue_id]
    _reseal(candidate)
    assert validator.validate(candidate).payload == candidate

    candidate = _fresh_candidate()
    table = _table(candidate)
    entry = table["ordered_rows"][3]["entries"][0]
    entry["column_binding_status"] = "UNKNOWN"
    entry["logical_column_id"] = None
    table["completeness_status"] = "PARTIAL"
    candidate["quality"]["status"] = "PARTIAL"
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_schema_validation_failed",
    ):
        validator.validate(candidate)

    issue_id = _add_issue(candidate, "unknown_column_binding")
    entry["issue_ids"] = [issue_id]
    table["issues"] = [issue_id]
    _reseal(candidate)
    assert validator.validate(candidate).payload == candidate

    candidate = _fresh_candidate()
    table = _table(candidate)
    entry = table["ordered_rows"][3]["entries"][0]
    entry["column_binding_status"] = "UNKNOWN"
    entry["logical_column_id"] = None
    entry["issue_ids"] = ["issue_fixture_missing"]
    table["completeness_status"] = "PARTIAL"
    candidate["quality"]["status"] = "PARTIAL"
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_entry_issue_ref_invalid",
    ):
        validator.validate(candidate)


def test_schema_rejects_invalid_column_binding_shapes(
    schema: dict[str, Any],
) -> None:
    invalid: list[tuple[str, dict[str, Any]]] = []

    document = _fresh_candidate()
    entry = _table(document)["ordered_rows"][3]["entries"][0]
    entry["column_binding_status"] = "BOUND"
    entry["logical_column_id"] = None
    invalid.append(("bound_without_binding", document))

    document = _fresh_candidate()
    entry = _table(document)["ordered_rows"][3]["entries"][0]
    entry["column_binding_status"] = "NOT_APPLICABLE"
    invalid.append(("not_applicable_with_direct", document))

    document = _fresh_candidate()
    entry = _table(document)["ordered_rows"][3]["entries"][0]
    _set_coverage_binding(
        document,
        entry,
        covers=["column_fixture_asset", "column_fixture_amount"],
        direct=None,
        suffix="schema_not_applicable",
    )
    entry["column_binding_status"] = "NOT_APPLICABLE"
    invalid.append(("not_applicable_with_coverage", document))

    document = _fresh_candidate()
    entry = _table(document)["ordered_rows"][3]["entries"][0]
    entry["column_binding_status"] = "UNKNOWN"
    entry["logical_column_id"] = None
    invalid.append(("unknown_without_issue", document))

    document = _fresh_candidate()
    entry = _table(document)["ordered_rows"][3]["entries"][0]
    entry["column_binding_status"] = "UNKNOWN"
    entry["issue_ids"] = ["issue_fixture_schema_probe"]
    invalid.append(("unknown_with_direct", document))

    document = _fresh_candidate()
    entry = _table(document)["ordered_rows"][3]["entries"][0]
    _set_coverage_binding(
        document,
        entry,
        covers=["column_fixture_asset", "column_fixture_amount"],
        direct=None,
        suffix="schema_unknown_coverage",
    )
    entry["column_binding_status"] = "UNKNOWN"
    entry["issue_ids"] = ["issue_fixture_schema_probe"]
    invalid.append(("unknown_with_coverage", document))

    document = _fresh_candidate()
    entry = _table(document)["ordered_rows"][3]["entries"][0]
    entry["covers_logical_column_ids"] = ["column_fixture_asset"]
    invalid.append(("single_covered_column", document))

    document = _fresh_candidate()
    entry = _table(document)["ordered_rows"][3]["entries"][0]
    entry["covers_logical_column_ids"] = [
        "column_fixture_asset",
        "column_fixture_asset",
    ]
    invalid.append(("duplicate_covered_column", document))

    document = _fresh_candidate()
    entry = _table(document)["ordered_rows"][3]["entries"][0]
    entry["column_binding_status"] = "BOUND"
    entry["logical_column_id"] = None
    entry["covers_logical_column_ids"] = [
        "column_fixture_asset",
        "column_fixture_amount",
    ]
    entry["geometry_evidence_ids"] = []
    invalid.append(("coverage_without_geometry", document))

    schema_validator = Draft202012Validator(schema)
    for _, document in invalid:
        with pytest.raises(ValidationError):
            schema_validator.validate(document)


@pytest.mark.parametrize(
    "coverage_kind",
    ["ENTRY_REGION", "VISUAL_COVERAGE", "COLUMN_ALIGNMENT"],
)
def test_cover_only_header_binding_is_valid_and_reusable_across_paths(
    schema: dict[str, Any],
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
    coverage_kind: str,
) -> None:
    table = _table(candidate)
    entry = table["ordered_rows"][1]["entries"][0]
    _set_coverage_binding(
        candidate,
        entry,
        covers=["column_fixture_asset", "column_fixture_amount"],
        direct=None,
        suffix=coverage_kind.lower(),
        kind=coverage_kind,
    )
    for column in table["logical_columns"]:
        column["header_path"] = [entry["entry_id"]]
    _reseal(candidate)

    Draft202012Validator(schema).validate(candidate)
    validated = validator.validate(candidate).payload
    assert [
        column["header_path"] for column in _table(validated)["logical_columns"]
    ] == [[entry["entry_id"]], [entry["entry_id"]]]


def test_group_spanner_may_be_bound_by_coverage_without_direct_column(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    table = _table(candidate)
    row = table["ordered_rows"][3]
    row["role"] = "GROUP_HEADER"
    entry = row["entries"][0]
    _set_coverage_binding(
        candidate,
        entry,
        covers=["column_fixture_asset", "column_fixture_amount"],
        direct=None,
        suffix="group_spanner",
    )
    _reseal(candidate)

    assert validator.validate(candidate).payload == candidate


@pytest.mark.parametrize("summary_role", ["SUBTOTAL", "TOTAL"])
def test_summary_coverage_directly_binds_leftmost_column(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
    summary_role: str,
) -> None:
    table = _table(candidate)
    row = table["ordered_rows"][2]
    row["role"] = summary_role
    entry = row["entries"][0]
    _set_coverage_binding(
        candidate,
        entry,
        covers=["column_fixture_asset", "column_fixture_amount"],
        direct="column_fixture_asset",
        suffix=summary_role.lower(),
    )
    _reseal(candidate)

    assert validator.validate(candidate).payload == candidate


def test_direct_and_coverage_binding_must_share_leftmost_column(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    entry = _table(candidate)["ordered_rows"][2]["entries"][0]
    _set_coverage_binding(
        candidate,
        entry,
        covers=["column_fixture_asset", "column_fixture_amount"],
        direct="column_fixture_amount",
        suffix="direct_mismatch",
    )
    _reseal(candidate)

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_direct_column_not_leftmost_cover",
    ):
        validator.validate(candidate)


def test_direct_binding_must_resolve_in_same_table(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    entry = _table(candidate)["ordered_rows"][2]["entries"][0]
    entry["logical_column_id"] = "column_fixture_missing"
    _reseal(candidate)

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_bound_column_missing",
    ):
        validator.validate(candidate)


@pytest.mark.parametrize("summary_role", ["SUBTOTAL", "TOTAL"])
@pytest.mark.parametrize(
    "direct",
    [None, "column_fixture_amount"],
    ids=["missing_direct", "nonleftmost_direct"],
)
def test_summary_coverage_rejects_invalid_direct_binding(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
    summary_role: str,
    direct: str | None,
) -> None:
    table = _table(candidate)
    row = table["ordered_rows"][2]
    row["role"] = summary_role
    entry = row["entries"][0]
    _set_coverage_binding(
        candidate,
        entry,
        covers=["column_fixture_asset", "column_fixture_amount"],
        direct=direct,
        suffix=(
            f"{summary_role.lower()}_"
            f"{'missing' if direct is None else 'nonleftmost'}_direct"
        ),
    )
    _reseal(candidate)

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_summary_coverage_binding_invalid",
    ):
        validator.validate(candidate)


def test_covered_columns_resolve_and_follow_logical_order(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    entry = _table(candidate)["ordered_rows"][2]["entries"][0]
    _set_coverage_binding(
        candidate,
        entry,
        covers=["column_fixture_amount", "column_fixture_asset"],
        direct="column_fixture_amount",
        suffix="reverse_order",
    )
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_covered_column_order_invalid",
    ):
        validator.validate(candidate)

    candidate = _fresh_candidate()
    entry = _table(candidate)["ordered_rows"][2]["entries"][0]
    _set_coverage_binding(
        candidate,
        entry,
        covers=["column_fixture_asset", "column_fixture_missing"],
        direct="column_fixture_asset",
        suffix="missing_column",
    )
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_entry_covered_column_ref_invalid",
    ):
        validator.validate(candidate)


def test_coverage_requires_allowed_object_local_geometry(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    entry = _table(candidate)["ordered_rows"][2]["entries"][0]
    entry["covers_logical_column_ids"] = [
        "column_fixture_asset",
        "column_fixture_amount",
    ]
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_column_coverage_evidence_invalid",
    ):
        validator.validate(candidate)

    candidate = _fresh_candidate()
    entry = _table(candidate)["ordered_rows"][2]["entries"][0]
    _set_coverage_binding(
        candidate,
        entry,
        covers=["column_fixture_asset", "column_fixture_amount"],
        direct="column_fixture_asset",
        suffix="wrong_scope",
        evidence_anchor_ids=["anchor_a_paragraph"],
    )
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_column_coverage_evidence_invalid",
    ):
        validator.validate(candidate)


def test_group_spanner_is_not_a_column_header_path_entry(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    table = _table(candidate)
    row = table["ordered_rows"][3]
    row["role"] = "GROUP_HEADER"
    entry = row["entries"][0]
    _set_coverage_binding(
        candidate,
        entry,
        covers=["column_fixture_asset", "column_fixture_amount"],
        direct=None,
        suffix="group_header_path",
    )
    table["logical_columns"][0]["header_path"] = [entry["entry_id"]]
    _reseal(candidate)

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_header_path_role_invalid",
    ):
        validator.validate(candidate)


def test_logical_columns_are_optional_without_fake_entries(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    table = _table(candidate)
    table["logical_columns"] = []
    for row in table["ordered_rows"]:
        for entry in row["entries"]:
            entry["column_binding_status"] = "NOT_APPLICABLE"
            entry["logical_column_id"] = None
            entry["covers_logical_column_ids"] = []
    _reseal(candidate)
    validated = validator.validate(candidate).payload
    assert _table(validated)["logical_columns"] == []
    assert len(_table(validated)["ordered_rows"][3]["entries"]) == 1


def test_parent_is_earlier_group_row_with_matching_nesting(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    table = _table(candidate)
    parent = table["ordered_rows"][2]
    child = table["ordered_rows"][3]
    parent["role"] = "GROUP_HEADER"
    child["nesting_level"] = 1
    child["parent_row_id"] = parent["row_id"]
    _reseal(candidate)
    assert validator.validate(candidate).payload == candidate

    child["parent_row_id"] = table["ordered_rows"][1]["row_id"]
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_parent_row_role_invalid",
    ):
        validator.validate(candidate)


def test_column_header_path_must_resolve_to_header_entry(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    table = _table(candidate)
    table["logical_columns"][0]["header_path"] = [
        "entry_fixture_data_a_label"
    ]
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_header_path_role_invalid",
    ):
        validator.validate(candidate)

    candidate = _fresh_candidate()
    table = _table(candidate)
    table["logical_columns"][0]["header_path"] = [
        "entry_fixture_header_amount"
    ]
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_header_path_binding_invalid",
    ):
        validator.validate(candidate)


def test_additional_metadata_cannot_shadow_standard_field(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    additional = copy.deepcopy(candidate["metadata"]["title"])
    additional["name"] = "title"
    candidate["metadata"]["additional"] = [additional]
    _reseal(candidate)

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_duplicate_additional_metadata_name",
    ):
        validator.validate(candidate)


def test_geometry_evidence_must_be_kind_compatible_and_object_local(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    unrelated_anchor_id = next(
        anchor["anchor_id"]
        for anchor in candidate["anchors"]
        if anchor["anchor_id"] != "anchor_a_table"
    )
    candidate["geometry_evidence"][0]["source_anchor_ids"] = [
        unrelated_anchor_id
    ]
    _reseal(candidate)

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_row_geometry_scope_invalid",
    ):
        validator.validate(candidate)


def test_row_and_entry_geometry_may_be_absent_when_not_claimed(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    row = _table(candidate)["ordered_rows"][-1]
    row["geometry_evidence_ids"] = []
    row["entries"][0]["geometry_evidence_ids"] = []
    _reseal(candidate)

    assert validator.validate(candidate).payload == candidate


def test_row_anchor_must_be_local_to_its_source_part_page(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    anchor = copy.deepcopy(
        next(
            item
            for item in candidate["anchors"]
            if item["anchor_id"] == "anchor_a_table"
        )
    )
    anchor["anchor_id"] = "anchor_a_table_page_2"
    anchor["locator"]["source_part_index"] = 2
    anchor["locator"]["page"] = 2
    candidate["anchors"].append(anchor)
    candidate["source"]["source_part_count"] = 2
    row_evidence = copy.deepcopy(candidate["geometry_evidence"][0])
    row_evidence["geometry_evidence_id"] = "geometry_fixture_row_page_2"
    row_evidence["kind"] = "ROW_BAND"
    row_evidence["source_anchor_ids"] = ["anchor_a_table_page_2"]
    row_evidence["evidence_checksum_sha256"] = "e" * 64
    row_evidence["private_artifact"]["ref"] = (
        "private_geometry_fixture_row_page_2"
    )
    row_evidence["private_artifact"]["checksum_sha256"] = "e" * 64
    candidate["geometry_evidence"].append(row_evidence)
    row = _table(candidate)["ordered_rows"][-1]
    row["source_anchor_ids"] = ["anchor_a_table_page_2"]
    row["geometry_evidence_ids"] = ["geometry_fixture_row_page_2"]
    _reseal(candidate)

    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_row_source_part_page_mismatch",
    ):
        validator.validate(candidate)


def test_source_parts_cover_rows_and_prove_continuation(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    table = _table(candidate)
    anchor = copy.deepcopy(
        next(
            item
            for item in candidate["anchors"]
            if item["anchor_id"] == "anchor_a_table"
        )
    )
    anchor["anchor_id"] = "anchor_a_table_page_2"
    anchor["locator"]["source_part_index"] = 2
    anchor["locator"]["page"] = 2
    candidate["anchors"].append(anchor)
    candidate["source"]["source_part_count"] = 2

    page_2_region = copy.deepcopy(candidate["geometry_evidence"][0])
    page_2_region["geometry_evidence_id"] = (
        "geometry_fixture_table_region_page_2"
    )
    page_2_region["source_anchor_ids"] = ["anchor_a_table_page_2"]
    page_2_region["evidence_checksum_sha256"] = "c" * 64
    page_2_region["private_artifact"]["ref"] = (
        "private_geometry_fixture_table_region_page_2"
    )
    page_2_region["private_artifact"]["checksum_sha256"] = "c" * 64
    continuation = copy.deepcopy(candidate["geometry_evidence"][0])
    continuation["geometry_evidence_id"] = "geometry_fixture_continuation"
    continuation["kind"] = "CONTINUATION"
    continuation["source_anchor_ids"] = [
        "anchor_a_table",
        "anchor_a_table_page_2",
    ]
    continuation["evidence_checksum_sha256"] = "d" * 64
    continuation["private_artifact"]["ref"] = (
        "private_geometry_fixture_continuation"
    )
    continuation["private_artifact"]["checksum_sha256"] = "d" * 64
    candidate["geometry_evidence"].extend([page_2_region, continuation])

    ownership_by_entry = {
        item["owner_entry_id"]: item
        for item in candidate["source_word_ownership"]
    }
    anchor_by_id = {
        item["anchor_id"]: item for item in candidate["anchors"]
    }
    page_2_entry_index = 0
    for row in table["ordered_rows"][2:]:
        row["source_anchor_ids"] = ["anchor_a_table_page_2"]
        row["geometry_evidence_ids"] = [
            "geometry_fixture_table_region_page_2"
        ]
        for entry in row["entries"]:
            ownership = ownership_by_entry[entry["entry_id"]]
            old_word_anchor_id = ownership["source_anchor_id"]
            new_word_anchor_id = f"{old_word_anchor_id}_page_2"
            word_anchor = copy.deepcopy(anchor_by_id[old_word_anchor_id])
            word_anchor["anchor_id"] = new_word_anchor_id
            word_anchor["checksum_sha256"] = (
                f"{page_2_entry_index + 32:064x}"
            )
            word_anchor["locator"]["source_part_index"] = 2
            word_anchor["locator"]["page"] = 2
            word_anchor["locator"]["source_block_ref"] = (
                f"synthetic_source_word_page_2_{page_2_entry_index:02d}"
            )
            ownership["source_word_id"] = _source_word_id_for_ref(
                word_anchor["locator"]["source_block_ref"]
            )
            candidate["anchors"].append(word_anchor)
            entry["source_anchor_ids"] = [
                "anchor_a_table_page_2",
                new_word_anchor_id,
            ]
            entry["geometry_evidence_ids"] = [
                "geometry_fixture_table_region_page_2"
            ]
            ownership["source_anchor_id"] = new_word_anchor_id
            page_2_entry_index += 1

    table["source_parts"] = [
        {
            **table["source_parts"][0],
            "last_row_id": "row_fixture_header",
            "continuation_status": "START",
            "continuation_evidence_ids": [
                "geometry_fixture_continuation"
            ],
        },
        {
            "source_part_id": "source_part_fixture_a_table_2",
            "ordinal": 1,
            "page": 2,
            "region_anchor_id": "anchor_a_table_page_2",
            "first_row_id": "row_fixture_data_a",
            "last_row_id": "row_fixture_data_b",
            "continuation_status": "END",
            "geometry_evidence_ids": [
                "geometry_fixture_table_region_page_2"
            ],
            "continuation_evidence_ids": [
                "geometry_fixture_continuation"
            ],
            "issue_ids": [],
        },
    ]
    _reseal(candidate)
    assert validator.validate(candidate).payload == candidate

    table["source_parts"][0]["continuation_evidence_ids"] = [
        "geometry_fixture_table_region"
    ]
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_continuation_geometry_invalid",
    ):
        validator.validate(candidate)
    table["source_parts"][0]["continuation_evidence_ids"] = [
        "geometry_fixture_continuation"
    ]

    table["source_parts"][1]["first_row_id"] = "row_fixture_data_b"
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_table_source_part_row_gap",
    ):
        validator.validate(candidate)


def test_source_word_ownership_is_exact_and_entry_bound(
    validator: ManagedDocumentContractV2Validator,
    candidate: dict[str, Any],
) -> None:
    candidate["source_word_ownership"].pop()
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_entry_without_owned_source_word",
    ):
        validator.validate(candidate)

    candidate = _fresh_candidate()
    candidate["source_word_ownership"][1]["source_word_id"] = (
        candidate["source_word_ownership"][0]["source_word_id"]
    )
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_duplicate_source_word_ownership_id",
    ):
        validator.validate(candidate)

    candidate = _fresh_candidate()
    candidate["source_word_ownership"][1]["source_anchor_id"] = (
        candidate["source_word_ownership"][0]["source_anchor_id"]
    )
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_duplicate_source_word_anchor",
    ):
        validator.validate(candidate)

    candidate = _fresh_candidate()
    owner = candidate["source_word_ownership"][0]
    table = _table(candidate)
    other_entry = next(
        entry
        for row in table["ordered_rows"]
        for entry in row["entries"]
        if entry["entry_id"] != owner["owner_entry_id"]
    )
    other_entry["source_anchor_ids"].append(owner["source_anchor_id"])
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_word_owner_anchor_multiple_entries",
    ):
        validator.validate(candidate)

    candidate = _fresh_candidate()
    owner = candidate["source_word_ownership"][0]
    owner_entry = next(
        entry
        for row in _table(candidate)["ordered_rows"]
        for entry in row["entries"]
        if entry["entry_id"] == owner["owner_entry_id"]
    )
    original_anchor = next(
        anchor
        for anchor in candidate["anchors"]
        if anchor["anchor_id"] == owner["source_anchor_id"]
    )
    extra_anchor = copy.deepcopy(original_anchor)
    extra_anchor["anchor_id"] = "anchor_source_word_fixture_extra"
    extra_anchor["checksum_sha256"] = "f" * 64
    extra_source_ref = "synthetic_source_word_extra"
    extra_anchor["locator"]["source_block_ref"] = extra_source_ref
    candidate["anchors"].append(extra_anchor)
    owner_entry["source_anchor_ids"].append(extra_anchor["anchor_id"])
    extra_owner = copy.deepcopy(owner)
    extra_owner["source_word_id"] = _source_word_id_for_ref(extra_source_ref)
    extra_owner["source_anchor_id"] = extra_anchor["anchor_id"]
    candidate["source_word_ownership"].append(extra_owner)
    _reseal(candidate)
    assert validator.validate(candidate).payload == candidate
    candidate["source_word_ownership"].pop()
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_entry_word_ownership_partition_invalid",
    ):
        validator.validate(candidate)

    candidate = _fresh_candidate()
    candidate["source_word_ownership"][0]["source_word_id"] = (
        "source_word_000000000000000000000000"
    )
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_word_owner_identity_mismatch",
    ):
        validator.validate(candidate)

    candidate = _fresh_candidate()
    owner = candidate["source_word_ownership"][0]
    anchor = next(
        item
        for item in candidate["anchors"]
        if item["anchor_id"] == owner["source_anchor_id"]
    )
    anchor["locator"]["bbox"] = None
    _reseal(candidate)
    with pytest.raises(
        ManagedDocumentContractV2Error,
        match="managed_document_v2_word_owner_pdf_locator_invalid",
    ):
        validator.validate(candidate)


def test_v1_contract_files_are_not_rewritten_by_v2() -> None:
    actual = {
        path: hashlib.sha256(_repository_lf_bytes(path)).hexdigest()
        for path in V1_REPOSITORY_LF_SHA256
    }
    assert actual == V1_REPOSITORY_LF_SHA256


def _repository_lf_bytes(path: Path) -> bytes:
    normalized = path.read_bytes().replace(b"\r\n", b"\n")
    assert b"\r" not in normalized, f"lone CR in repository file: {path}"
    return normalized


def _fresh_candidate() -> dict[str, Any]:
    corpus = _read_json(V1_CORPUS_PATH)
    source = next(
        item
        for item in corpus["documents"]
        if item["document_id"] == "document_fixture_a_broker_report"
    )
    document = copy.deepcopy(source)
    return _build_candidate_from_v1(document)


def _build_candidate_from_v1(document: dict[str, Any]) -> dict[str, Any]:
    document["schema_version"] = "broker_reports_managed_document_v2"
    document["information_partition"]["PRIVATE_SOURCE"] = [
        "/document_id",
        "/source/artifact",
        "/anchors/*/locator/private_locator",
        "/blocks/*/content/private_artifact",
        "/geometry_evidence",
        "/source_word_ownership",
    ]
    geometry_id = "geometry_fixture_table_region"
    document["geometry_evidence"] = [
        {
            "information_class": "PRIVATE_SOURCE",
            "geometry_evidence_id": geometry_id,
            "kind": "TABLE_REGION",
            "origin": "SOURCE_EXPLICIT",
            "source_anchor_ids": ["anchor_a_table"],
            "private_artifact": {
                "information_class": "PRIVATE_SOURCE",
                "status": "PRESENT",
                "ref": "private_geometry_fixture_table_region",
                "checksum_sha256": "a" * 64,
            },
            "evidence_checksum_sha256": "b" * 64,
            "issue_ids": [],
        }
    ]
    rows = [
        _row(
            "row_fixture_title",
            0,
            "TABLE_TITLE",
            [_entry("entry_fixture_title", 0, "LABEL", "Positions")],
            geometry_id,
        ),
        _row(
            "row_fixture_header",
            1,
            "COLUMN_HEADER",
            [
                _entry(
                    "entry_fixture_header_asset",
                    0,
                    "LABEL",
                    "Asset",
                    column_id="column_fixture_asset",
                ),
                _entry(
                    "entry_fixture_header_amount",
                    1,
                    "LABEL",
                    "Amount",
                    column_id="column_fixture_amount",
                ),
            ],
            geometry_id,
        ),
        _row(
            "row_fixture_data_a",
            2,
            "DATA",
            [
                _entry(
                    "entry_fixture_data_a_label",
                    0,
                    "LABEL",
                    "Synthetic A",
                    column_id="column_fixture_asset",
                ),
                _entry(
                    "entry_fixture_data_a_value",
                    1,
                    "VALUE",
                    "100.00",
                    column_id="column_fixture_amount",
                ),
            ],
            geometry_id,
        ),
        _row(
            "row_fixture_data_b",
            3,
            "DATA",
            [
                _entry(
                    "entry_fixture_data_b_label",
                    0,
                    "LABEL",
                    "Synthetic B",
                    column_id="column_fixture_asset",
                )
            ],
            geometry_id,
        ),
    ]
    table_block = next(
        item for item in document["blocks"] if item["block_type"] == "TABLE"
    )
    table_block["content"] = {
        "information_class": "CONTENT",
        "table_id": "table_fixture_a_positions",
        "completeness_status": "COMPLETE",
        "ordered_rows": rows,
        "logical_columns": [
            _column(
                "column_fixture_asset",
                0,
                ["entry_fixture_header_asset"],
                geometry_id,
            ),
            _column(
                "column_fixture_amount",
                1,
                ["entry_fixture_header_amount"],
                geometry_id,
            ),
        ],
        "source_parts": [
            {
                "source_part_id": "source_part_fixture_a_table",
                "ordinal": 0,
                "page": 1,
                "region_anchor_id": "anchor_a_table",
                "first_row_id": "row_fixture_title",
                "last_row_id": "row_fixture_data_b",
                "continuation_status": "SINGLE",
                "geometry_evidence_ids": [geometry_id],
                "continuation_evidence_ids": [],
                "issue_ids": [],
            }
        ],
        "relations": [
            "relation_a_note_for_table",
            "relation_a_table_section",
        ],
        "issues": [],
        "known_gap_ids": [],
    }
    for relation in document["relations"]:
        for endpoint in (relation["source"], relation["target"]):
            endpoint["row_id"] = endpoint.pop("row_index")
            endpoint["entry_id"] = endpoint.pop("column_index")
    entries = [
        entry for row in rows for entry in row["entries"]
    ]
    _install_unique_source_word_ownership(
        document,
        entries,
        table_id="table_fixture_a_positions",
    )
    _reseal(document)
    return document


def _install_unique_source_word_ownership(
    document: dict[str, Any],
    entries: list[dict[str, Any]],
    *,
    table_id: str,
) -> None:
    table_anchor = next(
        anchor
        for anchor in document["anchors"]
        if anchor["anchor_id"] == "anchor_a_table"
    )
    ownership: list[dict[str, Any]] = []
    for index, entry in enumerate(entries):
        anchor_id = f"anchor_source_word_fixture_{index:02d}"
        word_anchor = copy.deepcopy(table_anchor)
        word_anchor["anchor_id"] = anchor_id
        word_anchor["checksum_sha256"] = f"{index + 1:064x}"
        source_block_ref = f"synthetic_source_word_{index:02d}"
        word_anchor["locator"]["source_block_ref"] = source_block_ref
        document["anchors"].append(word_anchor)
        entry["source_anchor_ids"].append(anchor_id)
        ownership.append(
            {
                "information_class": "PRIVATE_SOURCE",
                "source_word_id": _source_word_id_for_ref(source_block_ref),
                "table_id": table_id,
                "owner_status": "OWNED",
                "owner_entry_id": entry["entry_id"],
                "duplicate_of_source_word_id": None,
                "source_anchor_id": anchor_id,
                "issue_ids": [],
            }
        )
    document["source_word_ownership"] = ownership


def _source_word_id_for_ref(source_block_ref: str) -> str:
    canonical = json.dumps(
        [source_block_ref],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"source_word_{hashlib.sha256(canonical).hexdigest()[:24]}"


def _row(
    row_id: str,
    ordinal: int,
    role: str,
    entries: list[dict[str, Any]],
    geometry_id: str,
) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "ordinal": ordinal,
        "role": role,
        "role_origin": "SOURCE_EXPLICIT",
        "nesting_level": 0,
        "parent_row_id": None,
        "entries": entries,
        "source_anchor_ids": ["anchor_a_table"],
        "geometry_evidence_ids": [geometry_id],
        "issue_ids": [],
    }


def _entry(
    entry_id: str,
    ordinal: int,
    kind: str,
    text: str,
    *,
    column_id: str | None = None,
) -> dict[str, Any]:
    return {
        "entry_id": entry_id,
        "ordinal": ordinal,
        "kind": kind,
        "text": text,
        "origin": "SOURCE_EXPLICIT",
        "column_binding_status": (
            "BOUND" if column_id is not None else "NOT_APPLICABLE"
        ),
        "logical_column_id": column_id,
        "covers_logical_column_ids": [],
        "source_anchor_ids": ["anchor_a_table"],
        "geometry_evidence_ids": ["geometry_fixture_table_region"],
        "issue_ids": [],
    }


def _set_coverage_binding(
    document: dict[str, Any],
    entry: dict[str, Any],
    *,
    covers: list[str],
    direct: str | None,
    suffix: str,
    kind: str = "VISUAL_COVERAGE",
    evidence_anchor_ids: list[str] | None = None,
) -> str:
    geometry_id = f"geometry_fixture_coverage_{suffix}"
    evidence = copy.deepcopy(document["geometry_evidence"][0])
    evidence["geometry_evidence_id"] = geometry_id
    evidence["kind"] = kind
    evidence["source_anchor_ids"] = list(
        entry["source_anchor_ids"]
        if evidence_anchor_ids is None
        else evidence_anchor_ids
    )
    evidence["private_artifact"]["ref"] = f"private_{geometry_id}"
    evidence["private_artifact"]["checksum_sha256"] = "c" * 64
    evidence["evidence_checksum_sha256"] = "d" * 64
    document["geometry_evidence"].append(evidence)

    entry["column_binding_status"] = "BOUND"
    entry["logical_column_id"] = direct
    entry["covers_logical_column_ids"] = list(covers)
    entry["geometry_evidence_ids"].append(geometry_id)
    return geometry_id


def _column(
    column_id: str,
    ordinal: int,
    header_path: list[str],
    geometry_id: str,
) -> dict[str, Any]:
    return {
        "column_id": column_id,
        "ordinal": ordinal,
        "header_path": header_path,
        "source_anchor_ids": ["anchor_a_table"],
        "geometry_evidence_ids": [geometry_id],
        "issue_ids": [],
    }


def _add_issue(document: dict[str, Any], suffix: str) -> str:
    issue_id = f"issue_fixture_{suffix}"
    document["quality"]["issue_ledger"].append(
        {
            "issue_id": issue_id,
            "code": suffix,
            "severity": "WARNING",
            "message": "Synthetic local uncertainty for contract proof.",
            "anchor_ids": ["anchor_a_table"],
            "block_ids": ["block_a_table"],
            "relation_ids": [],
            "recoverability": "RECOVERABLE",
            "requires_source_reread": True,
        }
    )
    return issue_id


def _table(document: dict[str, Any]) -> dict[str, Any]:
    return next(
        item["content"]
        for item in document["blocks"]
        if item["block_type"] == "TABLE"
    )


def _reseal(document: dict[str, Any]) -> None:
    document["integrity_sha256"] = compute_document_integrity_sha256(
        document
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
