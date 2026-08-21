from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_canonical_minimal_semantic_compiler.py"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("minimal_semantic_compiler", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
compiler = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compiler)


TRADE_HEADERS = [
    ("t101", 1, "Trade date", "trade_date"),
    ("t102", 2, "Asset", "asset_name"),
    ("t103", 3, "Currency", "currency"),
    ("t104", 4, "Side", "side"),
    ("t105", 5, "Quantity", "quantity"),
    ("t106", 6, "Price", "unit_price"),
    ("t107", 7, "Amount", "gross_amount"),
    ("t108", 8, "ACI", "accrued_interest"),
    ("t109", 9, "Broker fee", "broker_commission"),
    ("t110", 10, "Exchange fee", "exchange_commission"),
]


def _trade_row(source_id: str, row: int, side: str = "Продажа") -> dict:
    values = ["01.02.2024", "Bond A", "RUB", side, "2", "100.00", "200.00", "1.00", "0.50", "0.10"]
    return {
        "source_record_id": source_id,
        "logical_table_id": "g002",
        "source_identity": {
            "canonical_root_sha256": compiler.FROZEN_CANONICAL_ROOT_SHA256,
            "kind": "table_row",
            "node_id": "node_trade",
            "row": row,
        },
        "header_context": [
            {"source_ref": ref, "column": column, "literal": literal}
            for ref, column, literal, _ in TRADE_HEADERS
        ],
        "elements": [
            {"source_ref": f"t{row}{column:02d}", "column": column, "literal": literal}
            for (_, column, _, _), literal in zip(TRADE_HEADERS, values, strict=True)
        ],
        "row_view": "test trade row",
    }


def _trade_mapping() -> dict:
    return {
        "assertion_id": "g002",
        "table_type": "SECURITY_TRADES",
        "columns": [
            {"header_ref": ref, "normalized_role": role}
            for ref, _, _, role in TRADE_HEADERS
        ],
        "value_bindings": [
            {"column_role": "side", "source_literal": "Покупка", "normalized_value": "PURCHASE"},
            {"column_role": "side", "source_literal": "Продажа", "normalized_value": "DISPOSAL"},
        ],
    }


def test_mapping_contract_requires_every_header_in_source_order() -> None:
    mapping = _trade_mapping()
    raw = {
        "schema_version": compiler.MAPPING_RESPONSE_VERSION,
        "classifications": [mapping],
    }
    validated = compiler.validate_mapping_response(
        raw,
        version=compiler.MAPPING_RESPONSE_VERSION,
        table_id="g002",
        header_refs=[item[0] for item in TRADE_HEADERS],
        allowed_literals={"Покупка", "Продажа"},
        expect_type=True,
    )
    assert validated == mapping

    raw["classifications"][0]["columns"] = mapping["columns"][:-1]
    with pytest.raises(compiler.SemanticCompilerError, match="mapping_response_accounting_invalid"):
        compiler.validate_mapping_response(
            raw,
            version=compiler.MAPPING_RESPONSE_VERSION,
            table_id="g002",
            header_refs=[item[0] for item in TRADE_HEADERS],
            allowed_literals={"Покупка", "Продажа"},
            expect_type=True,
        )


def test_headers_only_context_rejects_invented_value_binding() -> None:
    raw = {
        "schema_version": compiler.MAPPING_RESPONSE_VERSION,
        "classifications": [_trade_mapping()],
    }
    with pytest.raises(compiler.SemanticCompilerError, match="mapping_value_binding_invalid"):
        compiler.validate_mapping_response(
            raw,
            version=compiler.MAPPING_RESPONSE_VERSION,
            table_id="g002",
            header_refs=[item[0] for item in TRADE_HEADERS],
            allowed_literals=set(),
            expect_type=True,
        )


def test_deterministic_trade_expansion_preserves_components_and_distinct_rows() -> None:
    rows = [
        _trade_row("r004", 4),
        _trade_row("r005", 5, side="Покупка"),
        _trade_row("r006", 6),
    ]
    batch = {"schema_version": "broker_typed_projection_batch_v0", "source_records": rows}
    projection, events = compiler.deterministic_trade_projection(
        source_batch=batch,
        mapping=_trade_mapping(),
    )
    assert len(events) == 3
    assert len({item["event_id"] for item in events}) == 3
    assert [len(item["typed_records"]) for item in projection["classifications"]] == [4, 4, 4]
    assert compiler.typed.sqlite_idempotency_probe(projection) == {
        "first_projection_records": 12,
        "after_second_materialization": 12,
        "duplicates_created": 0,
    }


def test_residual_contract_rejects_invented_span() -> None:
    batch = {
        "schema_version": "broker_closed_residual_batch_v0",
        "records": [
            {
                "source_record_id": "r009",
                "table_type": "INCOME_PAYMENTS",
                "source_wording_ref": "t902",
                "source_wording": "Coupon Bond A. Tax withheld.",
            }
        ],
    }
    raw = {
        "schema_version": compiler.RESIDUAL_RESPONSE_VERSION,
        "classifications": [
            {
                "assertion_id": "r009",
                "codes": ["COUPON_PAYMENT", "WITHHOLDING_STATED"],
                "asset_span": "Bond B",
                "currency_span": "",
            }
        ],
    }
    with pytest.raises(compiler.SemanticCompilerError, match="residual_span_invented"):
        compiler.validate_residual_response(raw, residual_batch=batch)


def test_residual_code_must_belong_to_its_table_type() -> None:
    batch = {
        "schema_version": "broker_closed_residual_batch_v0",
        "records": [
            {
                "source_record_id": "r001",
                "table_type": "CASH_OPERATIONS",
                "source_wording_ref": "t102",
                "source_wording": "Broker commission",
            }
        ],
    }
    raw = {
        "schema_version": compiler.RESIDUAL_RESPONSE_VERSION,
        "classifications": [
            {
                "assertion_id": "r001",
                "codes": ["TRADE_REGISTER_TOTAL"],
                "asset_span": "",
                "currency_span": "",
            }
        ],
    }
    with pytest.raises(compiler.SemanticCompilerError, match="residual_code_incompatible_with_table"):
        compiler.validate_residual_response(raw, residual_batch=batch)


def test_compound_coupon_withholding_preserves_missing_tax_amount() -> None:
    headers = [
        ("t901", 1, "Date", "event_date"),
        ("t902", 2, "Description", "description"),
        ("t903", 3, "Amount", "amount"),
        ("t904", 4, "Currency", "currency"),
    ]
    row = {
        "source_record_id": "r009",
        "logical_table_id": "g003",
        "source_identity": {
            "canonical_root_sha256": compiler.FROZEN_CANONICAL_ROOT_SHA256,
            "kind": "table_row",
            "node_id": "node_income",
            "row": 9,
        },
        "header_context": [
            {"source_ref": ref, "column": column, "literal": literal}
            for ref, column, literal, _ in headers
        ],
        "elements": [
            {"source_ref": "t911", "column": 1, "literal": "01.02.2024"},
            {"source_ref": "t912", "column": 2, "literal": "Coupon Bond A. Tax withheld."},
            {"source_ref": "t913", "column": 3, "literal": "10.00"},
            {"source_ref": "t914", "column": 4, "literal": "RUB"},
        ],
        "row_view": "test income row",
    }
    response = {
        "schema_version": compiler.RESIDUAL_RESPONSE_VERSION,
        "classifications": [
            {
                "assertion_id": "r009",
                "codes": ["COUPON_PAYMENT", "WITHHOLDING_STATED"],
                "asset_span": "Bond A",
                "currency_span": "",
            }
        ],
    }
    truth = {
        "schema_mappings": [
            {
                "logical_table_id": "g003",
                "table_type": "INCOME_PAYMENTS",
                "title_ref": "t900",
                "columns": [
                    {"header_ref": ref, "normalized_role": role}
                    for ref, _, _, role in headers
                ],
            }
        ],
        "residuals": [{"source_record_id": "r009", "wording_ref": "t912"}],
    }
    projection = compiler.materialize_residuals(
        response=response,
        source_batch={"schema_version": "broker_typed_projection_batch_v0", "source_records": [row]},
        semantic_truth=truth,
    )
    records = projection["classifications"][0]["typed_records"]
    assert [item["record_type"] for item in records] == ["COUPON_INCOME", "TAX_WITHHELD"]
    tax = records[1]
    assert tax["withholding_status"] == "STATED_WITHOUT_AMOUNT"
    assert all(item["role"] != "amount" for item in tax["roles"])


def test_fingerprint_reuses_only_exact_schema() -> None:
    context = {
        "headers": [
            {"source_ref": ref, "column": column, "literal": literal}
            for ref, column, literal, _ in TRADE_HEADERS
        ],
        "table_identity": {"source_ref": "t100", "literal": "Trades"},
    }
    probe = compiler.fingerprint_probe(mapping=_trade_mapping(), context=context)
    assert probe["exact_reuse"] is True
    assert probe["mutations_rejected"] == probe["mutations_total"] == 5


def test_terminal_requires_repeatable_mapping_residual_and_final_projection() -> None:
    exact = {"exact_repeatability": True, "exact_correct": True}
    final = [
        {
            "ordinal": ordinal,
            "terminal_status": "validated",
            "projection_sha256": "same",
            "source_fidelity_exact": True,
        }
        for ordinal in range(1, 4)
    ]
    assert compiler.choose_terminal(
        mapping_summary=exact,
        residual_summary=exact,
        final_runs=final,
        deterministic_control={"source_fidelity_exact": True},
    ) == "SCHEMA_MAPPING_PLUS_DETERMINISTIC_MATERIALIZATION_PREFERRED"


def test_safe_run_summary_drops_provider_trace_metadata() -> None:
    runs = [
        {
            "ordinal": ordinal,
            "terminal_status": "validated",
            "projection_sha256": "same",
            "exact": True,
            "execution": {
                "provider_calls": 1,
                "input_tokens": 10,
                "output_tokens": 2,
                "duration_ms": 100,
                "execution_metadata": {"provider_response_id": "private-trace"},
            },
        }
        for ordinal in range(1, 4)
    ]
    summary = compiler.summarize_runs(runs, hash_key="projection_sha256", exact_key="exact")
    assert summary["exact_repeatability"] is True
    assert all("execution" not in item for item in summary["runs"])
    assert all("provider_response_id" not in str(item) for item in summary["runs"])
    assert [item["input_tokens"] for item in summary["runs"]] == [10, 10, 10]
