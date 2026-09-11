from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.ordinary_trade_semantic_compiler import (
    ORDINARY_TRADE_EXPLICIT_HEADER_SOURCE_CONTINUATION_SCHEMA_VERSION,
    OrdinaryTradeSemanticCompilerError,
    OrdinaryTradeSemanticCompilerFactory,
    compile_schema_mapping,
    structural_fingerprint,
)


_HEADERS = (
    "Date",
    "Asset",
    "Side",
    "Quantity",
    "Price",
    "Currency",
    "Amount",
    "Broker fee",
    "Exchange fee",
)
_BINDING = {
    "document_id": "continuation-document",
    "canonical_version_id": "canv_continuation_v1",
    "canonical_root_sha256": "a" * 64,
    "source_artifact_ref": "art_continuation_source",
    "source_sha256": "b" * 64,
}


def _cell(*, row: int, column: int, value: str, provenance: str) -> dict:
    return {
        "row": row,
        "column": column,
        "displayed_value": value,
        "source_coordinate": f"page-{provenance}:r{row}:c{column}",
        "source_refs": [provenance],
    }


def _table(*, node_id: str, provenance: str, rows: tuple[tuple[str, ...], ...], headerless: bool) -> dict:
    return {
        "node_id": node_id,
        "node_type": "TABLE",
        "source_refs": [provenance],
        "content": {
            "header": [] if headerless else list(_HEADERS),
            "metadata": {"physical_header_state": "ABSENT" if headerless else "PRESENT"},
            "cells": [
                _cell(row=row, column=column, value=value, provenance=provenance)
                for row, cells in enumerate(rows, start=1)
                for column, value in enumerate(cells, start=1)
            ],
        },
    }


def _canonical() -> dict:
    parent_rows = (
        _HEADERS,
        ("01.01.2026", "AAA", "BUY", "1", "10", "USD", "10", "1", "0"),
    )
    child_rows = (
        ("02.01.2026", "BBB", "SELL", "2", "20", "USD", "40", "2", "0"),
        ("Total", "", "", "", "", "", "50", "3"),
    )
    return {
        "canonical_root_hash": _BINDING["canonical_root_sha256"],
        "source": {
            "source_artifact_ref": _BINDING["source_artifact_ref"],
            "source_sha256": _BINDING["source_sha256"],
        },
        "provenance": [
            {"provenance_id": "prov-parent"},
            {"provenance_id": "prov-child"},
        ],
        "nodes": [
            _table(
                node_id="table-parent",
                provenance="prov-parent",
                rows=parent_rows,
                headerless=False,
            ),
            _table(
                node_id="table-child",
                provenance="prov-child",
                rows=child_rows,
                headerless=True,
            ),
        ],
    }


def _mapping() -> dict:
    return compile_schema_mapping(
        title_literal=None,
        headers=[
            {"column": index, "literal": literal}
            for index, literal in enumerate(_HEADERS, start=1)
        ],
        model_columns=[
            {"column": 1, "semantic_role": "trade_date"},
            {"column": 2, "semantic_role": "asset_name"},
            {"column": 3, "semantic_role": "side"},
            {"column": 4, "semantic_role": "quantity"},
            {"column": 5, "semantic_role": "unit_price"},
            {"column": 6, "semantic_role": "currency"},
            {"column": 7, "semantic_role": "gross_amount"},
            {"column": 8, "semantic_role": "broker_commission"},
            {"column": 9, "semantic_role": "exchange_commission"},
        ],
        amount_currency_bindings=[
            {"amount_column": column, "currency_column": 6}
            for column in (7, 8, 9)
        ],
        side_values=[
            {"source_literal": "BUY", "normalized_value": "PURCHASE"},
            {"source_literal": "SELL", "normalized_value": "DISPOSAL"},
        ],
        qualification_ref={"qualification_id": "otqual_test", "receipt_sha256": "c" * 64},
    )


def _parent_resolution() -> dict:
    headers = [
        {"column": index, "literal": literal}
        for index, literal in enumerate(_HEADERS, start=1)
    ]
    return {
        "table_node_id": "table-parent",
        "header_row": 1,
        "structural_fingerprint": structural_fingerprint(
            title_literal=None,
            columns=[
                {"column": item["column"], "header_literal": item["literal"]}
                for item in headers
            ],
        ),
        "evidence_surface": {"title_literal": None, "headers": headers},
        "disposition": "SECURITY_TRADES",
        "security_trade_rows": [2],
    }


def _continuation(mapping: dict) -> dict:
    return {
        "schema_version": ORDINARY_TRADE_EXPLICIT_HEADER_SOURCE_CONTINUATION_SCHEMA_VERSION,
        "canonical_binding": copy.deepcopy(_BINDING),
        "target_table_node_id": "table-child",
        "header_source_table_node_id": "table-parent",
        "header_source_row": 1,
        "security_trade_rows": [1],
        "mapping": mapping,
    }


def _physical_context(*, links: list[dict] | None = None) -> dict:
    return {
        "schema_version": "broker_reports_physical_table_continuation_context_v1",
        "sidecar_artifact_ref": "art_continuation_sidecar",
        "sidecar_id": "ptc_test",
        "source_binding": {
            "normalization_run_id": "run_continuation",
            **copy.deepcopy(_BINDING),
        },
        "links": links
        if links is not None
        else [
            {
                "parent_table_node_id": "table-parent",
                "child_table_node_id": "table-child",
            }
        ],
    }


def _compile(*, continuation: dict, physical_context: dict | None = None) -> dict:
    mapping = continuation["mapping"]
    return OrdinaryTradeSemanticCompilerFactory.create().compile(
        canonical=_canonical(),
        canonical_binding=_BINDING,
        mappings=[],
        scoped_mappings=[{"table_node_id": "table-parent", "mapping": mapping}],
        explicit_header_source_continuations=[continuation],
        physical_table_continuation_context=(
            _physical_context() if physical_context is None else physical_context
        ),
        table_resolutions=[_parent_resolution()],
    )


def test_explicit_header_source_reuses_only_exact_parent_header_for_selected_child_rows() -> None:
    projection = _compile(continuation=_continuation(_mapping()))

    ready = [
        item
        for item in projection["source_observations"]
        if item["disposition"] == "RUNTIME_READY"
    ]
    assert [(item["table_node_id"], item["row"]) for item in ready] == [
        ("table-parent", 2),
        ("table-child", 1),
    ]
    assert len(projection["runtime_records"]) == 4
    child_records = [
        item
        for item in projection["runtime_records"]
        if item["annotation_target"]["node_id"] == "table-child"
    ]
    assert {item["annotation_target"]["row"] for item in child_records} == {1}
    retained = [
        item
        for item in projection["source_observations"]
        if item["table_node_id"] == "table-child" and item["row"] == 2
    ]
    assert retained[0]["disposition"] == "SOURCE_RETAINED_NO_CONSUMER"


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        (lambda value: value["canonical_binding"].update({"source_sha256": "d" * 64}), "ordinary_trade_explicit_header_source_invalid"),
        (lambda value: value.update({"target_table_node_id": "missing-table"}), "ordinary_trade_explicit_header_source_invalid"),
        (lambda value: value.update({"header_source_row": 2}), "ordinary_trade_explicit_header_source_binding_invalid"),
        (lambda value: value.update({"security_trade_rows": [2]}), "ordinary_trade_explicit_header_source_column_coverage_invalid"),
    ],
)
def test_explicit_header_source_fails_closed_for_wrong_binding_or_surface(mutation, code) -> None:
    continuation = _continuation(_mapping())
    mutation(continuation)

    with pytest.raises(OrdinaryTradeSemanticCompilerError) as error:
        _compile(continuation=continuation)

    assert error.value.code == code


def test_explicit_header_source_requires_exact_source_owned_link() -> None:
    with pytest.raises(OrdinaryTradeSemanticCompilerError) as error:
        _compile(
            continuation=_continuation(_mapping()),
            physical_context=_physical_context(links=[{
                "parent_table_node_id": "table-child",
                "child_table_node_id": "table-parent",
            }]),
        )

    assert error.value.code == "ordinary_trade_explicit_header_source_link_unverified"
