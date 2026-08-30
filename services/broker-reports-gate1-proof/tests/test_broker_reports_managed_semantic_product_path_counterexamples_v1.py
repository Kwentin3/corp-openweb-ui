from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from broker_reports_gate1.gate2_model_clients import Gate2OpenWebUIStructuredModelClient
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MANAGED_DOCUMENT_SEMANTIC_CRITIC_SCHEMA_VERSION,
    MANAGED_DOCUMENT_SEMANTIC_PROPOSAL_SCHEMA_VERSION,
)
from tests.test_broker_reports_logical_row_table_recovery import _page_candidate_refs
from tests.test_broker_reports_managed_pdf_document_v2 import (
    _GeminiBoundary,
    _managed_full_source,
    _openwebui_request,
    _route_openwebui_resolver_to_boundary,
)
from tests.test_broker_reports_managed_semantic_provider_review_v1 import (
    MODEL_ID,
    _provider_builder,
)
from tests.test_broker_reports_pdf_document_visual_adjudication import _visual_table
from tests.test_broker_reports_pdf_layout_slice2 import _pdf_bytes


def _table_page(
    *,
    title: str,
    parent_headers: tuple[str, ...],
    leaf_headers: tuple[str, ...],
    rows: tuple[tuple[str | None, ...], ...],
) -> dict:
    width = len(parent_headers)
    assert len(leaf_headers) == width
    if width == 8:
        xs = (10, 70, 125, 165, 195, 220, 250, 280)
        bounds = (7, 67, 122, 162, 192, 217, 247, 277, 319)
    elif width == 5:
        xs = (10, 70, 130, 200, 260)
        bounds = (7, 67, 127, 197, 257, 319)
    else:
        raise AssertionError(f"unsupported fixture width: {width}")
    ys = (38, 22)
    texts = [(10, 96, title)]
    texts.extend((x, 72, value) for x, value in zip(xs, parent_headers, strict=True))
    texts.extend((x, 55, value) for x, value in zip(xs, leaf_headers, strict=True))
    for y, row in zip(ys, rows, strict=True):
        texts.extend(
            (x, y, value)
            for x, value in zip(xs, row, strict=True)
            if value is not None
        )
    return {
        "texts": texts,
        "vectors": [
            *[f"7 {y} m 319 {y} l S" for y in (15, 30, 46, 63, 82)],
            *[f"{x} 15 m {x} 82 l S" for x in bounds],
        ],
    }


def _trade_page(
    *,
    title: str = "Trades",
    blank_first_asset_currency: bool = False,
    indistinguishable_money: bool = False,
) -> dict:
    return _table_page(
        title=title,
        parent_headers=(
            "Trade", "Settl", "Asset", "Oper", "Qty",
            "X" if indistinguishable_money else "Unit", "Curr",
            "Y" if indistinguishable_money else "Gross",
        ),
        leaf_headers=("Date", "Date", "Name", "Side", "Qty", "Value" if indistinguishable_money else "Price", "Code", "Value" if indistinguishable_money else "Amt"),
        rows=(
            (
                "15.01.2025",
                "16.01.2025",
                None if blank_first_asset_currency else "GAZP",
                "BUY",
                "1" if indistinguishable_money else "10",
                "1000" if indistinguishable_money else "100",
                None if blank_first_asset_currency else "RUB",
                "1000",
            ),
            (
                "17.01.2025",
                "18.01.2025",
                "SBER",
                "BUY",
                "1" if indistinguishable_money else "20",
                "2000" if indistinguishable_money else "200",
                "RUB",
                "2000" if indistinguishable_money else "4000",
            ),
        ),
    )


def _dividend_page() -> dict:
    return _table_page(
        title="Dividends",
        parent_headers=("Payment", "Security", "Dividend", "Tax", "Currency"),
        leaf_headers=("Date", "Name", "Amount", "Withheld", "Code"),
        rows=(
            ("15.01.2025", "GAZP", "1000.00", "130.00", "RUB"),
            ("16.01.2025", "SBER", "500.00", "65.00", "RUB"),
        ),
    )


def _observations(payload: dict, widths: tuple[int, ...]) -> dict:
    projection = payload["pdf_text_layer_projection"]
    pages = []
    for page_number, width in enumerate(widths, start=1):
        refs = _page_candidate_refs(payload, page_number)
        assert len(refs) >= width
        page_ref = next(
            item["page_ref"]
            for item in projection["page_inventory"]
            if item["page_number"] == page_number
        )
        ref_set = set(refs)
        title_refs = [
            item["word_ref"]
            for item in projection["word_inventory"]
            if item["page_ref"] == page_ref and item["word_ref"] not in ref_set
        ]
        pages.append(
            {
                "tables": [
                    _visual_table(
                        payload,
                        page_number=page_number,
                        title_refs=title_refs,
                        header_groups=[refs[:width], refs[width : 2 * width]],
                        body_refs=refs[2 * width :],
                    )
                ]
            }
        )
    return {"pages": pages}


def _header_cells(table: dict) -> list[dict]:
    rows = [row for row in table["rows"] if row["row_role"] == "COLUMN_HEADER"]
    assert len(rows) == 2
    return rows[-1]["cells"]


def _column_paths(table: dict) -> dict[str, tuple[str, ...]]:
    rows = [row for row in table["rows"] if row["row_role"] == "COLUMN_HEADER"]
    output = {}
    for row in rows:
        for cell in row["cells"]:
            output.setdefault(cell["column_ref"], []).append(cell["source_literal"])
    return {key: tuple(value) for key, value in output.items()}


def _security_option(table: dict, *, swap_dates: bool = False, swap_money: bool = False) -> dict:
    headers = _header_cells(table)
    paths = _column_paths(table)
    roles = {
        ("Trade", "Date"): "settlement_date" if swap_dates else "trade_date",
        ("Settl", "Date"): "trade_date" if swap_dates else "settlement_date",
        ("Asset", "Name"): "asset_name",
        ("Oper", "Side"): "side",
        ("Qty", "Qty"): "quantity",
        ("Unit", "Price"): "unit_price",
        ("Curr", "Code"): "currency",
        ("Gross", "Amt"): "gross_amount",
    }
    money_columns = [ref for ref, path in paths.items() if path not in roles]
    assert len(money_columns) in {0, 2}
    columns = []
    for cell in headers:
        path = paths[cell["column_ref"]]
        if path not in roles:
            index = money_columns.index(cell["column_ref"])
            role = ("gross_amount", "unit_price")[index] if swap_money else ("unit_price", "gross_amount")[index]
        else:
            role = roles[path]
        columns.append({"column_ref": cell["column_ref"], "semantic_role": role})
    currency_ref = next(item["column_ref"] for item in columns if item["semantic_role"] == "currency")
    amount_ref = next(item["column_ref"] for item in columns if item["semantic_role"] == "gross_amount")
    buy_refs = {
        cell["value_ref"]
        for row in table["rows"]
        for cell in row["cells"]
        if cell["source_literal"] == "BUY"
    }
    assert len(buy_refs) == 1
    return {
        "disposition": "SECURITY_TRADES",
        "columns": columns,
        "amount_currency_bindings": [
            {"amount_column_ref": amount_ref, "currency_column_ref": currency_ref}
        ],
        "side_values": [
            {"value_ref": next(iter(buy_refs)), "normalized_value": "PURCHASE"}
        ],
    }


class _SemanticBoundary:
    def __init__(self, *, cross_table_critic: bool = False) -> None:
        self.cross_table_critic = cross_table_critic
        self.calls: list[dict] = []

    def resolve(self, user_id: str):
        return self.complete, SimpleNamespace(id=user_id, role="user")

    def complete(self, *, form_data, **_kwargs):
        package = json.loads(form_data["messages"][1]["content"])
        self.calls.append(copy.deepcopy(form_data))
        if package["phase"] == "managed_semantic_proposal":
            tables = []
            for table in package["evidence"]["tables"]:
                literals = {
                    literal for path in _column_paths(table).values() for literal in path
                }
                if "Dividend" in literals:
                    options = [{
                        "disposition": "UNSUPPORTED_FINANCIAL",
                        "columns": [],
                        "amount_currency_bindings": [],
                        "side_values": [],
                    }]
                elif len(
                    set(_column_paths(table).values())
                    - {
                        ("Trade", "Date"),
                        ("Settl", "Date"),
                        ("Asset", "Name"),
                        ("Oper", "Side"),
                        ("Qty", "Qty"),
                        ("Curr", "Code"),
                        ("Unit", "Price"),
                        ("Gross", "Amt"),
                    }
                ) == 2:
                    options = [
                        _security_option(table),
                        _security_option(table, swap_money=True),
                    ]
                elif "Settl" in literals:
                    options = [
                        _security_option(table),
                        _security_option(table, swap_dates=True),
                    ]
                else:
                    raise AssertionError(literals)
                tables.append({"table_ref": table["table_ref"], "options": options})
            output = {
                "schema_version": MANAGED_DOCUMENT_SEMANTIC_PROPOSAL_SCHEMA_VERSION,
                "evidence_scope_ref": package["evidence_scope_ref"],
                "tables": tables,
            }
        else:
            host_tables = package["host_options"]
            decisions = []
            title_by_ref = {
                table["table_ref"]: next(
                    cell["source_literal"]
                    for row in table["rows"]
                    if row["row_role"] == "TABLE_TITLE"
                    for cell in row["cells"]
                )
                for table in package["evidence"]["tables"]
            }
            option_by_title = {
                title_by_ref[table["table_ref"]]: table["options"][0]["option_ref"]
                for table in host_tables
            }
            for table in host_tables:
                visible = table["options"]
                evidence_table = next(
                    item
                    for item in package["evidence"]["tables"]
                    if item["table_ref"] == table["table_ref"]
                )
                roles_by_column = {}
                for option in visible:
                    for column in option["columns"]:
                        roles_by_column.setdefault(column["column_ref"], set()).add(
                            column["semantic_role"]
                        )
                money_refs = sorted(
                    ref
                    for ref, roles in roles_by_column.items()
                    if roles == {"unit_price", "gross_amount"}
                )
                data_literals = {
                    ref: [
                        cell["source_literal"]
                        for row in evidence_table["rows"]
                        if row["row_role"] == "DATA"
                        for cell in row["cells"]
                        if cell["column_ref"] == ref
                    ]
                    for ref in money_refs
                }
                quantity_refs = {
                    column["column_ref"]
                    for option in visible
                    for column in option["columns"]
                    if column["semantic_role"] == "quantity"
                }
                quantity_literals = [
                    cell["source_literal"]
                    for row in evidence_table["rows"]
                    if row["row_role"] == "DATA"
                    for cell in row["cells"]
                    if cell["column_ref"] in quantity_refs
                ]
                if len(visible) > 1 and all(
                    any(column["semantic_role"] == role for column in option["columns"])
                    for option in visible
                    for role in ("unit_price", "gross_amount")
                ) and any(
                    sum(column["semantic_role"] == "gross_amount" for column in option["columns"]) == 1
                    for option in visible
                ) and (
                    len(money_refs) == 2
                    and data_literals[money_refs[0]] == data_literals[money_refs[1]]
                    and quantity_literals
                    and set(quantity_literals) == {"1"}
                ):
                    decisions.append({
                        "table_ref": table["table_ref"],
                        "decision": "UNRESOLVED",
                        "option_ref": None,
                    })
                    continue
                selected = next(
                    option
                    for option in visible
                    if any(
                        column["semantic_role"] == "trade_date"
                        and column["column_ref"]
                        == next(
                            cell["column_ref"]
                            for evidence_table in package["evidence"]["tables"]
                            if evidence_table["table_ref"] == table["table_ref"]
                            for cell in _header_cells(evidence_table)
                            if _column_paths(evidence_table)[cell["column_ref"]]
                            == ("Trade", "Date")
                        )
                        for column in option["columns"]
                    )
                    if option["disposition"] == "SECURITY_TRADES"
                ) if visible[0]["disposition"] == "SECURITY_TRADES" else visible[0]
                decisions.append({
                    "table_ref": table["table_ref"],
                    "decision": "SELECT_OPTION",
                    "option_ref": (
                        option_by_title["Second trades"]
                        if self.cross_table_critic
                        and title_by_ref[table["table_ref"]] == "First trades"
                        else selected["option_ref"]
                    ),
                })
            output = {
                "schema_version": MANAGED_DOCUMENT_SEMANTIC_CRITIC_SCHEMA_VERSION,
                "evidence_scope_ref": package["evidence_scope_ref"],
                "proposal_ref": package["proposal_ref"],
                "tables": decisions,
            }
        return {
            "id": f"semantic-counterexample-{len(self.calls)}",
            "model": MODEL_ID,
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
            "choices": [{"finish_reason": "stop", "message": {"content": output}}],
        }


async def _run(monkeypatch, pages: list[dict], widths: tuple[int, ...], *, cross_table_critic: bool = False):
    pdf_bytes = _pdf_bytes(pages)
    source_ref = "private_pdf_semantic_product_counterexamples"
    payload = _managed_full_source(pdf_bytes, source_artifact_ref=source_ref).payloads[0]
    observations = _observations(payload, widths)
    request = _openwebui_request()
    semantic = _SemanticBoundary(cross_table_critic=cross_table_critic)
    with _GeminiBoundary([observations, observations]) as visual:
        _route_openwebui_resolver_to_boundary(monkeypatch, request=request, boundary=visual)
        monkeypatch.setattr(
            Gate2OpenWebUIStructuredModelClient,
            "_resolve_openwebui_completion_dependencies",
            lambda _self, user_id: semantic.resolve(user_id),
        )
        result = await _provider_builder(request).build_with_semantic_compiled_document_candidate(
            pdf_bytes,
            tenant_id="tenant",
            artifact_version=1,
            source_artifact_ref=source_ref,
            task_id="semantic_product_counterexamples",
            user_scope_sha256="a" * 64,
            proposal_model_id=MODEL_ID,
            critic_model_id=MODEL_ID,
            created_at="2026-08-30T00:00:00Z",
        )
    return result, semantic


def _recursive_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value).union(*(_recursive_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_recursive_keys(item) for item in value), set())
    return set()


def _assert_review_coverage(result, *, tables_total: int) -> None:
    review = result.semantic_review_contract
    assert review is not None
    evidence_refs = {
        item["table_ref"]
        for item in result.evidence_result.semantic_evidence["model_evidence"]["tables"]
    }
    assert len(evidence_refs) == tables_total
    assert {item["table_ref"] for item in review["table_options"]} == evidence_refs
    assert {item["table_ref"] for item in review["table_reviews"]} == evidence_refs
    assert result.execution_receipt["provider_submissions"] == 2
    assert not {"facts", "runtime_records"}.intersection(_recursive_keys(result.__dict__))


@pytest.mark.asyncio
async def test_trade_plus_actual_dividend_blocks_whole_document(monkeypatch) -> None:
    result, boundary = await _run(monkeypatch, [_trade_page(), _dividend_page()], (8, 5))
    assert (result.status, result.reason_code) == ("BLOCKED", None)
    assert [
        item["reason_code"]
        for item in result.semantic_review_contract["blockers"]
    ] == ["UNSUPPORTED_FINANCIAL_CONTENT"]
    assert result.document_candidate is None
    assert result.semantic_review_candidate_binding is None
    assert result.execution_receipt["provider_submissions"] == 2
    assert len(boundary.calls) == 2
    _assert_review_coverage(result, tables_total=2)


@pytest.mark.asyncio
async def test_actual_blank_instrument_and_currency_blocks_atomically(monkeypatch) -> None:
    result, _ = await _run(monkeypatch, [_trade_page(blank_first_asset_currency=True)], (8,))
    assert result.evidence_result.canonical_result.safe_diagnostics["status"] == "COMPLETE"
    assert result.status == "BLOCKED"
    assert result.document_candidate is not None
    assert result.document_candidate["document_record_candidates"] == []
    assert result.document_candidate["table_outcomes"][0]["terminal"] == "RELEVANT_PARTIAL"
    assert result.document_candidate["blockers"][0]["reason_code"] == "TABLE_RELEVANT_PARTIAL"
    relevant = result.document_candidate["table_outcomes"][0]["relevant_unmapped"]
    assert len(relevant) == 1
    assert relevant[0]["reason_code"] == "ORDINARY_TRADE_ROW_CONTRACT_INCOMPLETE"
    retained_roles = {item["semantic_role"] for item in relevant[0]["fields"]}
    assert {"asset_name", "currency"}.isdisjoint(retained_roles)
    assert all(
        field["canonical_cell"]["source_coordinate"]
        and field["canonical_cell"]["provenance_refs"]
        and field["canonical_cell"]["node_id"]
        == result.document_candidate["table_outcomes"][0]["table_node_id"]
        for field in relevant[0]["fields"]
    )
    _assert_review_coverage(result, tables_total=1)


@pytest.mark.asyncio
async def test_obvious_trade_date_option_is_selected_by_semantic_content(monkeypatch) -> None:
    result, _ = await _run(monkeypatch, [_trade_page()], (8,))
    assert result.status == "CANDIDATE_COMPLETE"
    assert len(result.document_candidate["document_record_candidates"]) == 2
    review = result.semantic_review_contract
    selected_ref = review["table_reviews"][0]["selected_option_ref"]
    selected = next(
        option for option in review["table_options"][0]["options"]
        if option["option_ref"] == selected_ref
    )
    trade_column = next(
        item["column"] for item in selected["mapping_candidate"]["columns"]
        if item["semantic_role"] == "trade_date"
    )
    assert trade_column == 1
    compiled_trade_date = next(
        field
        for field in result.document_candidate["table_outcomes"][0][
            "row_compilations"
        ][0]["fields"]
        if field["semantic_role"] == "trade_date"
    )
    assert compiled_trade_date["literal"] == "15.01.2025"
    assert compiled_trade_date["canonical_cell"]["column"] == 1
    assert compiled_trade_date["canonical_cell"]["source_coordinate"]
    assert compiled_trade_date["canonical_cell"]["provenance_refs"]
    assert result.execution_receipt["provider_submissions"] == 2
    _assert_review_coverage(result, tables_total=1)


@pytest.mark.asyncio
async def test_genuine_indistinguishable_money_columns_remain_unresolved(monkeypatch) -> None:
    result, _ = await _run(monkeypatch, [_trade_page(indistinguishable_money=True)], (8,))
    assert result.status == "CLARIFICATION_REQUIRED"
    assert result.document_candidate is None
    assert result.semantic_review_candidate_binding is None
    assert result.execution_receipt["provider_submissions"] == 2
    review = result.semantic_review_contract
    options = review["table_options"][0]["options"]
    assert len(options) == 2
    assert len({item["option_ref"] for item in options}) == 2
    assert review["unresolved"] == [
        {
            "table_ref": review["table_reviews"][0]["table_ref"],
            "reason_code": "SEMANTIC_REVIEW_UNRESOLVED",
        }
    ]
    assert "question" not in _recursive_keys(review)
    _assert_review_coverage(result, tables_total=1)


@pytest.mark.asyncio
async def test_same_shape_tables_compile_distinctly_and_reject_cross_table_option(monkeypatch) -> None:
    pages = [_trade_page(title="First trades"), _trade_page(title="Second trades")]
    result, _ = await _run(monkeypatch, pages, (8, 8))
    assert result.status == "CANDIDATE_COMPLETE"
    candidate = result.document_candidate
    assert len(candidate["table_outcomes"]) == 2
    assert len({item["table_node_id"] for item in candidate["table_outcomes"]}) == 2
    assert len(
        {item["managed_header_view_sha256"] for item in candidate["table_outcomes"]}
    ) == 2
    assert len({item["compiled_case_sha256"] for item in candidate["table_outcomes"]}) == 2
    assert len(
        {
            item["qualification_binding"]["qualification_id"]
            for item in candidate["table_outcomes"]
        }
    ) == 2
    assert len(
        {
            item["qualification_binding"]["receipt_sha256"]
            for item in candidate["table_outcomes"]
        }
    ) == 2
    for outcome in candidate["table_outcomes"]:
        assert outcome["row_compilations"]
        assert all(
            row["table_node_id"] == outcome["table_node_id"]
            and row["row_id"]
            and all(
                field["canonical_cell"]["node_id"] == outcome["table_node_id"]
                and field["canonical_cell"]["source_coordinate"]
                and field["canonical_cell"]["provenance_refs"]
                for field in row["fields"]
            )
            for row in outcome["row_compilations"]
        )
    assert len(candidate["document_record_candidates"]) == 4
    _assert_review_coverage(result, tables_total=2)
    rejected, _ = await _run(monkeypatch, pages, (8, 8), cross_table_critic=True)
    assert rejected.status == "BLOCKED"
    assert rejected.reason_code == "CRITIC_RESPONSE_INVALID"
    assert rejected.document_candidate is None
    assert rejected.semantic_review_candidate_binding is None
    assert rejected.execution_receipt["provider_submissions"] == 2
