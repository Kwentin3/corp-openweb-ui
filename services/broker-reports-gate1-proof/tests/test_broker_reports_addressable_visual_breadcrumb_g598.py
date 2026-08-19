from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.local_addressable_visual_breadcrumb_g598 import (
    AMBIGUOUS,
    CONTRACT_NOT_VERIFIED,
    NOT_FOUND,
    RESOLVED,
    RESPONSE_SCHEMA,
    G598Error,
    resolve_page_contract,
    smoke,
    validate_page_contract,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SERVICE_ROOT / "scripts" / "local_addressable_visual_breadcrumb_g598.py"
MANIFEST = (
    SERVICE_ROOT
    / "benchmarks"
    / "addressable_visual_breadcrumb_g598"
    / "manifest.json"
)


def _line(ordinal: int, top: float, text: str) -> dict:
    return {
        "parser_ordinal": ordinal,
        "bbox": [10.0, top, 90.0, top + 5.0],
        "text": text,
        "word_parser_ordinals": [ordinal],
    }


def _page(*lines: dict, status: str = "complete") -> dict:
    return {
        "page_number": 1,
        "height": 100.0,
        "layout_projection_status": status,
        "line_inventory": list(lines),
        "word_inventory": [],
        "table_candidate_inventory": [
            {"bbox": [0.0, 0.0, 100.0, 99.0]}
        ],
    }


def _contract(
    *,
    before_relation: str = "immediately_after",
    before_tokens: list[str] | None = None,
    header_groups: list[list[str]] | None = None,
    after_boundary: str = "page_footer",
    after_tokens: list[str] | None = None,
    ordinal: int = 1,
    continuation: bool = False,
) -> dict:
    return {
        "tables": [
            {
                "before_anchor": {
                    "relation": before_relation,
                    "tokens": before_tokens if before_tokens is not None else ["Section"],
                },
                "header_token_groups": (
                    header_groups
                    if header_groups is not None
                    else [["Alpha"], ["Gamma"]]
                ),
                "after_anchor": {
                    "boundary": after_boundary,
                    "tokens": after_tokens if after_tokens is not None else ["Footer"],
                },
                "table_ordinal_in_scope": ordinal,
                "continuation_from_previous_page": continuation,
            }
        ]
    }


def test_minimal_contract_has_only_addressability_fields() -> None:
    properties = RESPONSE_SCHEMA["properties"]["tables"]["items"]["properties"]
    assert set(properties) == {
        "before_anchor",
        "header_token_groups",
        "after_anchor",
        "table_ordinal_in_scope",
        "continuation_from_previous_page",
    }
    serialized = json.dumps(RESPONSE_SCHEMA, sort_keys=True)
    for forbidden in ("body_rows", "body_values", "bbox", "canonical_id", "columns"):
        assert forbidden not in serialized


def test_resolver_composes_anchors_header_and_footer_without_candidate_ranking() -> None:
    page = _page(
        _line(1, 5, "Section One"),
        _line(2, 15, "Alpha Beta Gamma"),
        _line(3, 25, "body is source only"),
        _line(4, 96, "Footer Words"),
    )
    result = resolve_page_contract(page=page, page_number=1, contract=_contract())
    table = result["tables"][0]
    assert table["terminal"] == RESOLVED
    assert (table["region"]["first_line_ordinal"], table["region"]["last_line_ordinal"]) == (
        2,
        3,
    )
    assert table["region"]["overlapping_parser_candidate_ordinals"] == [1]


def test_repeated_anchor_stays_ambiguous_instead_of_choosing_a_winner() -> None:
    page = _page(
        _line(1, 5, "Section One"),
        _line(2, 15, "Alpha Beta Gamma"),
        _line(3, 25, "body"),
        _line(4, 35, "Section One"),
        _line(5, 45, "Alpha Beta Gamma"),
        _line(6, 55, "body"),
        _line(7, 96, "Footer Words"),
    )
    table = resolve_page_contract(page=page, page_number=1, contract=_contract())[
        "tables"
    ][0]
    assert table["terminal"] == AMBIGUOUS
    assert len(table["candidate_regions"]) == 2


def test_missing_header_is_not_found() -> None:
    page = _page(
        _line(1, 5, "Section One"),
        _line(2, 15, "Different Header"),
        _line(3, 96, "Footer Words"),
    )
    table = resolve_page_contract(page=page, page_number=1, contract=_contract())[
        "tables"
    ][0]
    assert table == {"terminal": NOT_FOUND, "reason": "composed_region_not_found"}


def test_header_group_may_span_visual_header_lines_without_fuzzy_matching() -> None:
    page = _page(
        _line(1, 5, "Section One"),
        _line(2, 15, "Alpha Middle"),
        _line(3, 20, "Beta Gamma"),
        _line(4, 30, "body"),
        _line(5, 96, "Footer Words"),
    )
    contract = _contract(header_groups=[["Alpha", "Beta"], ["Gamma"]])
    table = resolve_page_contract(page=page, page_number=1, contract=contract)[
        "tables"
    ][0]
    assert table["terminal"] == RESOLVED
    assert table["region"]["line_ordinals"] == [2, 3, 4]


def test_header_group_uses_exact_multiset_when_parser_row_order_differs() -> None:
    page = _page(
        _line(1, 5, "Section One"),
        _line(2, 15, "End Period Start Period"),
        _line(3, 20, "Market Value Price"),
        _line(4, 30, "body"),
        _line(5, 96, "Footer Words"),
    )
    contract = _contract(
        header_groups=[["Start", "Period", "Price"], ["End", "Market", "Value"]]
    )
    table = resolve_page_contract(page=page, page_number=1, contract=contract)[
        "tables"
    ][0]
    assert table["terminal"] == RESOLVED
    assert table["region"]["first_line_ordinal"] == 2


def test_numeric_footnote_suffix_does_not_change_exact_header_word() -> None:
    page = _page(
        _line(1, 5, "Section One"),
        _line(2, 15, "Amount NCD⁴"),
        _line(3, 25, "body"),
        _line(4, 96, "Footer Words"),
    )
    contract = _contract(header_groups=[["Amount"], ["NCD"]])
    table = resolve_page_contract(page=page, page_number=1, contract=contract)[
        "tables"
    ][0]
    assert table["terminal"] == RESOLVED


def test_next_anchor_uses_declared_first_exact_match_not_later_subtotal() -> None:
    page = _page(
        _line(1, 5, "Section One"),
        _line(2, 15, "Alpha Beta Gamma"),
        _line(3, 25, "body"),
        _line(4, 35, "Next Section"),
        _line(5, 45, "Alpha Beta Gamma"),
        _line(6, 55, "Total Next Section"),
        _line(7, 96, "Footer Words"),
    )
    contract = _contract(
        before_tokens=["Section", "One"],
        after_boundary="next_anchor",
        after_tokens=["Next", "Section"],
    )
    table = resolve_page_contract(page=page, page_number=1, contract=contract)[
        "tables"
    ][0]
    assert table["terminal"] == RESOLVED
    assert table["region"]["line_ordinals"] == [2, 3]


def test_unverified_layout_and_footer_have_explicit_terminal() -> None:
    incomplete = _page(_line(1, 5, "Section"), status="partial")
    table = resolve_page_contract(
        page=incomplete, page_number=1, contract=_contract()
    )["tables"][0]
    assert table["terminal"] == CONTRACT_NOT_VERIFIED

    no_footer = _page(
        _line(1, 5, "Section"),
        _line(2, 15, "Alpha Beta Gamma"),
    )
    table = resolve_page_contract(page=no_footer, page_number=1, contract=_contract())[
        "tables"
    ][0]
    assert table["terminal"] == CONTRACT_NOT_VERIFIED


def test_headerless_fragment_is_allowed_only_for_page_start_continuation() -> None:
    contract = _contract(
        before_relation="page_start",
        before_tokens=[],
        header_groups=[],
        after_boundary="next_anchor",
        after_tokens=["Next", "Section"],
        continuation=True,
    )
    page = _page(
        _line(1, 5, "continuation source line"),
        _line(2, 15, "continuation source line"),
        _line(3, 25, "Next Section"),
    )
    table = resolve_page_contract(page=page, page_number=1, contract=contract)[
        "tables"
    ][0]
    assert table["terminal"] == RESOLVED
    assert table["region"]["line_ordinals"] == [1, 2]

    invalid = copy.deepcopy(contract)
    invalid["tables"][0]["continuation_from_previous_page"] = False
    with pytest.raises(G598Error, match="g598_headerless_noncontinuation_forbidden"):
        validate_page_contract(invalid)


@pytest.mark.parametrize(
    "mutation,code",
    [
        (lambda value: value["tables"][0].update({"bbox": [0, 0, 1, 1]}), "g598_contract_domain_leakage"),
        (
            lambda value: value["tables"][0]["before_anchor"].update(
                {"tokens": ["Section 7"]}
            ),
            "g598_token_invalid",
        ),
        (
            lambda value: value["tables"][0].update(
                {"table_ordinal_in_scope": True}
            ),
            "g598_table_ordinal_invalid",
        ),
    ],
)
def test_contract_rejects_domain_leakage_and_unstable_tokens(mutation, code: str) -> None:
    value = _contract()
    mutation(value)
    with pytest.raises(G598Error, match=code):
        validate_page_contract(value)


def test_manifest_freezes_new_split_and_excludes_g597_page() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    selected = {
        (case["document_id"], int(case["page"]))
        for split in ("development", "unseen_holdout")
        for case in manifest[split]
    }
    assert manifest["frozen"] is True
    assert len(manifest["development"]) == 10
    assert len(manifest["unseen_holdout"]) == 4
    assert ("document_04", 29) not in selected
    assert manifest["selection_policy"]["holdout_opened_before_freeze"] is False


def test_factory_first_and_closed_world_anchors() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "PdfTextLayerParserFactory().create" in source
    assert "PdfPlumberLayoutAdapter(" not in source
    assert "sys.path" not in source
    assert "process.cwd" not in source
    assert smoke()["status"] == "passed"
