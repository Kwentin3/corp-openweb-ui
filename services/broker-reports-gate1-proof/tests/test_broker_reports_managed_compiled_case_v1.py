from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.ordinary_trade_qualified_mappings import (
    OrdinaryTradeQualifiedMappingAuthorityFactory,
)
from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    ORDINARY_TRADE_MANAGED_COMPILED_CASE_SCHEMA_VERSION,
    normalize_runtime_value,
)
from tests.test_broker_reports_managed_case_mapping_v4 import (
    _canonical_for_parents,
    _model_decision,
)
from tests.test_broker_reports_managed_case_qualification_v1 import (
    USER_SCOPE_SHA256,
    _rehash_receipt,
    _side_decisions,
    _understandings,
)
from tests.test_broker_reports_managed_header_view import (
    _reseal_canonical_root,
    _reseal_entry_locator,
)


def _set_literal(cell: dict, literal: str) -> None:
    cell["value"] = literal
    cell["raw_value"] = literal
    cell["displayed_value"] = literal


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key
            for item in value.values()
            for key in _all_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def _compile_inputs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    incomplete_first_row: bool = False,
    case_suffix: str = "base",
) -> tuple[dict, dict, dict, dict]:
    canonical, table, binding = _canonical_for_parents(
        monkeypatch,
        left_parent="Trade",
        right_parent="Settle",
        case_suffix=case_suffix,
    )
    sequence = table["content"]["metadata"]["managed_row_sequence"]
    data_rows = [
        index
        for index, item in enumerate(sequence, start=1)
        if item["role"] == "DATA"
    ]
    for ordinal, row_number in enumerate(data_rows, start=1):
        date_cell = next(
            cell
            for cell in table["content"]["cells"]
            if cell["row"] == row_number and cell["column"] == 1
        )
        date_literal = f"{14 + ordinal:02d}.01.2025"
        _set_literal(date_cell, date_literal)
        sequence[row_number - 1]["entry_texts"][0] = date_literal
    if incomplete_first_row:
        row_number = data_rows[0]
        asset_cell = next(
            cell
            for cell in table["content"]["cells"]
            if cell["row"] == row_number and cell["column"] == 2
        )
        _set_literal(asset_cell, "")
        sequence[row_number - 1]["entry_texts"][1] = ""
    binding = _reseal_canonical_root(canonical, binding)
    authority = OrdinaryTradeQualifiedMappingAuthorityFactory.create()
    _, receipt = authority.qualify_managed_header_case_mapping(
        canonical=canonical,
        canonical_binding=binding,
        table_node_id=table["node_id"],
        model_mapping_decision=_model_decision(),
        user_scope_sha256=USER_SCOPE_SHA256,
        model_side_normalization_decisions=_side_decisions(),
        confirmed_understandings=_understandings(),
    )
    return canonical, table, binding, receipt


def _compile(
    canonical: dict,
    table: dict,
    binding: dict,
    receipt: dict,
) -> dict:
    return (
        OrdinaryTradeQualifiedMappingAuthorityFactory.create()
        .compile_managed_header_case(
            canonical=canonical,
            canonical_binding=binding,
            table_node_id=table["node_id"],
            model_mapping_decision=_model_decision(),
            user_scope_sha256=USER_SCOPE_SHA256,
            model_side_normalization_decisions=_side_decisions(),
            confirmed_understandings=_understandings(),
            receipt=receipt,
        )
    )


def test_exact_multirow_case_compiles_to_inactive_record_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding, receipt = _compile_inputs(monkeypatch)

    result = _compile(canonical, table, binding, receipt)

    assert result["schema_version"] == (
        ORDINARY_TRADE_MANAGED_COMPILED_CASE_SCHEMA_VERSION
    )
    assert result["compilation_status"] == "COMPLETE"
    assert result["runtime_activation"] is False
    assert result["global_reuse"] is False
    assert result["publication_authorized"] is False
    assert result["document_completeness_asserted"] is False
    assert result["scope"] == "EXACT_TABLE_ONLY"
    assert result["canonical_binding"] == binding
    assert result["table_node_id"] == table["node_id"]
    assert result["qualification_binding"]["receipt_sha256"] == receipt[
        "receipt_sha256"
    ]
    assert all(
        len(column["header_path"]) == 2
        for column in result["semantic_scope"]["columns"]
    )
    assert result["relevant_unmapped"] == []
    assert len(result["row_compilations"]) == 2
    assert all(
        item["compilation_status"] == "MAPPED"
        for item in result["row_compilations"]
    )
    assert [
        item["record_type"] for item in result["record_candidates"]
    ] == ["SECURITY_PURCHASE", "SECURITY_PURCHASE"]
    assert {
        role["value"]
        for candidate in result["record_candidates"]
        for role in candidate["roles"]
        if role["role"] == "date"
    } == {"2025-01-15", "2025-01-16"}
    row_refs = {
        item["row_compilation_id"] for item in result["row_compilations"]
    }
    assert {
        item["source_row_compilation_ref"]
        for item in result["record_candidates"]
    } == row_refs
    compilations_by_id = {
        item["row_compilation_id"]: item for item in result["row_compilations"]
    }
    canonical_cells = {
        (cell["row"], cell["column"]): cell
        for cell in table["content"]["cells"]
    }
    for record_candidate in result["record_candidates"]:
        row_compilation = compilations_by_id[
            record_candidate["source_row_compilation_ref"]
        ]
        row_number = row_compilation["row"]
        assert record_candidate["annotation_target"] == {
            "kind": "table_row",
            "node_id": table["node_id"],
            "row": row_number,
        }
        for role in record_candidate["roles"]:
            source = role["source_binding"]
            canonical_cell = source["canonical_cell"]
            column = canonical_cell["column"]
            cell = canonical_cells[(row_number, column)]
            literal = cell["displayed_value"]
            expected_value, expected_transform = normalize_runtime_value(
                role["role"],
                literal,
                numeric_convention=row_compilation["numeric_convention"],
            )
            assert source["source_literal"] == literal
            assert role["value"] == expected_value
            assert source["deterministic_transform"] == expected_transform
            assert canonical_cell["node_id"] == table["node_id"]
            assert canonical_cell["row"] == row_number
            assert canonical_cell["column"] == column
            assert canonical_cell["source_coordinate"] == cell[
                "source_coordinate"
            ]
            assert canonical_cell["provenance_refs"] == cell["source_refs"]
            assert len(canonical_cell["provenance_refs"]) == 1
            assert source["source_ref"] == (
                f"canonical:{binding['canonical_version_id']}:"
                f"{table['node_id']}:r{row_number}:c{column}"
            )
    assert {"runtime_records", "facts"}.isdisjoint(_all_keys(result))
    assert all(
        "runtime_record_id" not in item for item in result["record_candidates"]
    )


def test_one_incomplete_relevant_row_makes_whole_case_partial_and_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding, receipt = _compile_inputs(
        monkeypatch,
        incomplete_first_row=True,
    )

    result = _compile(canonical, table, binding, receipt)

    assert result["compilation_status"] == "PARTIAL"
    assert result["record_candidates"] == []
    assert len(result["relevant_unmapped"]) == 1
    unresolved = result["relevant_unmapped"][0]
    assert unresolved["reason_code"] == "ORDINARY_TRADE_ROW_CONTRACT_INCOMPLETE"
    assert unresolved["row_id"]
    assert any(
        field["semantic_role"] == "asset_name" and field["literal"] == ""
        for field in unresolved["fields"]
    )
    assert {
        item["compilation_status"] for item in result["row_compilations"]
    } == {"MAPPED", "RELEVANT_UNMAPPED"}


def test_forged_receipt_is_rejected_before_compilation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding, receipt = _compile_inputs(monkeypatch)
    forged = copy.deepcopy(receipt)
    forged["side_normalizations"][0]["normalized_value"] = "DISPOSAL"
    _rehash_receipt(forged)

    with pytest.raises(RuntimeError) as exc:
        _compile(canonical, table, binding, forged)

    assert str(exc.value) == (
        "ordinary_trade_managed_case_qualification_receipt_invalid"
    )


def test_foreign_case_and_unknown_row_fail_before_compilation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canonical, table, binding, receipt = _compile_inputs(monkeypatch)
    foreign, foreign_table, foreign_binding, _ = _compile_inputs(
        monkeypatch,
        case_suffix="foreign",
    )
    assert foreign["canonical_root_hash"] != canonical["canonical_root_hash"]
    assert foreign["source"]["source_artifact_ref"] != canonical["source"][
        "source_artifact_ref"
    ]

    with pytest.raises(RuntimeError) as exc:
        _compile(foreign, foreign_table, foreign_binding, receipt)
    assert str(exc.value) == (
        "ordinary_trade_managed_case_qualification_receipt_invalid"
    )

    unknown = copy.deepcopy(canonical)
    unknown_table = next(
        node for node in unknown["nodes"] if node["node_id"] == table["node_id"]
    )
    sequence = unknown_table["content"]["metadata"]["managed_row_sequence"]
    row_number = next(
        index
        for index, item in enumerate(sequence, start=1)
        if item["role"] == "DATA"
    )
    sequence[row_number - 1]["role"] = "UNKNOWN"
    for cell in unknown_table["content"]["cells"]:
        if cell["row"] == row_number:
            _reseal_entry_locator(
                unknown,
                cell,
                lambda locator: locator.update({"managed_row_role": "UNKNOWN"}),
            )
    unknown_binding = _reseal_canonical_root(unknown, binding)

    with pytest.raises(RuntimeError) as exc:
        _compile(unknown, unknown_table, unknown_binding, receipt)
    assert "ordinary_trade_canonical_managed_data_replay_roles_invalid" in str(
        exc.value
    )
