from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_canonical_semantic_task_forms.py"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("semantic_task_forms", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
forms = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(forms)


def _context() -> dict:
    return {
        "logical_table_id": "g001",
        "table_identity": {"source_ref": "t100", "literal": "Trades"},
        "headers": [
            {"source_ref": "t101", "column": 1, "literal": "Trade date"},
            {"source_ref": "t102", "column": 2, "literal": "Asset"},
        ],
    }


def _truth() -> dict:
    return {
        "schema_mappings": [
            {
                "logical_table_id": "g001",
                "table_type": "SECURITY_TRADES",
                "title_ref": "t100",
                "columns": [
                    {"header_ref": "t101", "normalized_role": "trade_date"},
                    {"header_ref": "t102", "normalized_role": "asset_name"},
                ],
            }
        ]
    }


def test_forward_header_mapping_requires_exact_source_order() -> None:
    raw = {
        "schema_version": "v",
        "classifications": [
            {
                "assertion_id": "g001",
                "columns": [
                    {"header_ref": "t101", "normalized_role": "trade_date"},
                    {"header_ref": "t102", "normalized_role": "asset_name"},
                ],
            }
        ],
    }
    mapping = forms.validate_header_forward(raw, version="v", contexts=[_context()])
    assert forms.score_headers(mappings=mapping, truth=_truth())["exact"] is True

    raw["classifications"][0]["columns"].reverse()
    with pytest.raises(forms.TaskFormError, match="header_order_invalid"):
        forms.validate_header_forward(raw, version="v", contexts=[_context()])


def test_inverse_header_mapping_returns_same_canonical_mapping() -> None:
    raw = {
        "schema_version": "v",
        "classifications": [
            {
                "assertion_id": "g001",
                "role_bindings": [
                    {"normalized_role": "asset_name", "header_ref": "t102"},
                    {"normalized_role": "trade_date", "header_ref": "t101"},
                ],
            }
        ],
    }
    mapping = forms.validate_header_inverse(raw, version="v", context=_context())
    assert forms.score_headers(mappings=mapping, truth=_truth()) == {
        "projection_sha256": forms.typed._stable_sha256(mapping),
        "correct": 2,
        "total": 2,
        "exact": True,
        "tables": 1,
        "table_types_correct": None,
        "table_types_total": 0,
    }


def _side_context() -> dict:
    return {
        "logical_table_id": "g001",
        "candidates": [
            {"value_ref": "v001", "source_ref": "t201", "literal": "BUY"},
            {"value_ref": "v002", "source_ref": "t202", "literal": "SELL"},
        ],
    }


def _side_expected() -> list[dict[str, str]]:
    return [
        {"column_role": "side", "source_literal": "BUY", "normalized_value": "PURCHASE"},
        {"column_role": "side", "source_literal": "SELL", "normalized_value": "DISPOSAL"},
    ]


def test_value_refs_remove_literal_copy_from_model_contract() -> None:
    raw = {
        "schema_version": "v",
        "classifications": [
            {
                "assertion_id": "g001",
                "value_bindings": [
                    {"value_ref": "v001", "normalized_value": "PURCHASE"},
                    {"value_ref": "v002", "normalized_value": "DISPOSAL"},
                ],
            }
        ],
    }
    value = forms.validate_side(raw, version="v", mode="ref", context=_side_context(), expected=_side_expected())
    assert forms.score_side(value, _side_expected())["exact"] is True
    assert all("value_ref" not in item for item in value)


def test_single_purchase_ref_deterministically_infers_disposal() -> None:
    raw = {
        "schema_version": "v",
        "classifications": [{"assertion_id": "g001", "purchase_value_ref": "v001"}],
    }
    value = forms.validate_side(
        raw,
        version="v",
        mode="purchase_ref",
        context=_side_context(),
        expected=_side_expected(),
    )
    assert forms.score_side(value, _side_expected())["exact"] is True


def test_codes_only_is_explicitly_not_downstream_complete() -> None:
    batch = {
        "schema_version": "broker_closed_residual_batch_v0",
        "records": [
            {
                "source_record_id": "r001",
                "table_type": "INCOME_PAYMENTS",
                "source_wording_ref": "t301",
                "source_wording": "Coupon Bond A",
            }
        ],
    }
    raw = {
        "schema_version": "v",
        "classifications": [{"assertion_id": "r001", "codes": ["COUPON_PAYMENT"]}],
    }
    value = forms.validate_codes_only(raw, version="v", residual_batch=batch)
    score = forms.score_codes_only(
        value,
        {
            "residuals": [
                {
                    "source_record_id": "r001",
                    "expected_codes": ["COUPON_PAYMENT"],
                }
            ]
        },
    )
    assert score["exact"] is True
    assert score["downstream_complete"] is False


def test_token_refs_reconstruct_exact_source_span_and_reject_cross_record() -> None:
    batch = {
        "schema_version": "broker_closed_residual_batch_v0",
        "records": [
            {
                "source_record_id": "r001",
                "table_type": "INCOME_PAYMENTS",
                "source_wording_ref": "t301",
                "source_wording": "Coupon Bond A.",
            },
            {
                "source_record_id": "r002",
                "table_type": "INCOME_PAYMENTS",
                "source_wording_ref": "t302",
                "source_wording": "Coupon Bond B.",
            },
        ],
    }
    token_batch, index = forms.tokenize_residual_batch(batch)
    first = token_batch["records"][0]
    refs = [first["tokens"][1]["token_ref"], first["tokens"][2]["token_ref"]]
    assert forms._span_from_refs(
        refs=refs,
        record_id="r001",
        wording=first["source_wording"],
        token_index=index,
    ) == "Bond A"
    with pytest.raises(forms.TaskFormError, match="token_ref_cross_record"):
        forms._span_from_refs(
            refs=[token_batch["records"][1]["tokens"][1]["token_ref"]],
            record_id="r001",
            wording=first["source_wording"],
            token_index=index,
        )


def test_terminal_requires_all_table_mapping_and_three_exact_final_runs() -> None:
    final = [
        {
            "ordinal": ordinal,
            "terminal_status": "validated",
            "projection_sha256": "same",
            "exact": True,
        }
        for ordinal in range(1, 4)
    ]
    assert forms.choose_terminal(
        header_winner="H3_ALL_TABLES_FORWARD_REFS",
        side_winner="H6_SIDE_SINGLE_PURCHASE_REF",
        residual_winner="H8_RESIDUAL_TABLE_CONTRACTS",
        final_runs=final,
    ) == "TASK_FORM_SEMANTIC_COMPILER_PROVEN"


def test_summary_uses_terminal_results_not_attempt_presence() -> None:
    runs = [
        {
            "ordinal": 1,
            "terminal_status": "validated",
            "projection_sha256": "a",
            "exact": True,
            "correct": 1,
            "total": 1,
            "provider_calls": 1,
        },
        {"ordinal": 2, "terminal_status": "rejected", "error_type": "TaskFormError", "provider_calls": 1},
        {
            "ordinal": 3,
            "terminal_status": "validated",
            "projection_sha256": "a",
            "exact": True,
            "correct": 1,
            "total": 1,
            "provider_calls": 1,
        },
    ]
    summary = forms.summarize(runs)
    assert summary["validated_runs"] == 2
    assert summary["exact_repeatability"] is False
    assert summary["provider_calls"] == 3
