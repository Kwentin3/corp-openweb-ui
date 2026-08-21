from __future__ import annotations

from collections import Counter
import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_canonical_typed_broker_registers_benchmark.py"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("typed_registers_benchmark", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def _row(source_id: str, row: int) -> dict:
    headers = [
        ("t101", 1, "Дата заключения"),
        ("t102", 2, "Наименование ЦБ"),
        ("t103", 3, "Валюта"),
        ("t104", 4, "Вид"),
        ("t105", 5, "Количество, шт."),
        ("t106", 6, "Цена"),
        ("t107", 7, "Сумма"),
        ("t108", 8, "НКД"),
        ("t109", 9, "Комиссия Брокера"),
        ("t110", 10, "Комиссия Биржи"),
    ]
    cells = [
        (f"t{row}01", 1, "01.02.2024"),
        (f"t{row}02", 2, "Bond A"),
        (f"t{row}03", 3, "RUB"),
        (f"t{row}04", 4, "Продажа"),
        (f"t{row}05", 5, "2"),
        (f"t{row}06", 6, "100.00"),
        (f"t{row}07", 7, "200.00"),
        (f"t{row}08", 8, "1.00"),
        (f"t{row}09", 9, "0.50"),
        (f"t{row}10", 10, "0.10"),
    ]
    return {
        "source_record_id": source_id,
        "logical_table_id": "g001",
        "source_identity": {
            "canonical_root_sha256": benchmark.FROZEN_CANONICAL_ROOT_SHA256,
            "kind": "table_row",
            "node_id": "node_trade",
            "row": row,
        },
        "header_context": [
            {"source_ref": ref, "column": column, "literal": literal}
            for ref, column, literal in headers
        ],
        "elements": [
            {"source_ref": ref, "column": column, "literal": literal}
            for ref, column, literal in cells
        ],
        "row_view": "test row",
    }


def _mapping() -> dict:
    roles = [
        "DATE",
        "ASSET",
        "CURRENCY",
        "SIDE",
        "QUANTITY",
        "UNIT_PRICE",
        "AMOUNT",
        "ACCRUED_COUPON",
        "BROKER_COMMISSION",
        "EXCHANGE_COMMISSION",
    ]
    return {
        "schema_version": benchmark.MAPPING_SCHEMA_VERSION,
        "classifications": [
            {
                "assertion_id": "g001",
                "register_kind": "SECURITY_TRADES",
                "column_bindings": [
                    {"header_ref": f"t{100 + index}", "column_role": role}
                    for index, role in enumerate(roles, 1)
                ],
                "side_markers": [
                    {"meaning": "PURCHASE", "literal": "Покупка"},
                    {"meaning": "DISPOSAL", "literal": "Продажа"},
                ],
            }
        ],
    }


def test_missing_source_record_is_rejected_by_accounting() -> None:
    batch = {"schema_version": "broker_typed_projection_batch_v0", "source_records": [_row("r001", 2), _row("r002", 3)]}
    response = {
        "schema_version": benchmark.RESPONSE_SCHEMA_VERSION,
        "classifications": [
            {"assertion_id": "r001", "disposition": "NOT_RELEVANT", "typed_records": []}
        ],
    }
    with pytest.raises(benchmark.TypedRegistersBenchmarkError, match="typed_response_accounting_invalid"):
        benchmark.validate_typed_response(response, batch=batch)


def test_invented_literal_is_rejected() -> None:
    row = _row("r001", 2)
    batch = {"schema_version": "broker_typed_projection_batch_v0", "source_records": [row]}
    response = {
        "schema_version": benchmark.RESPONSE_SCHEMA_VERSION,
        "classifications": [
            {
                "assertion_id": "r001",
                "disposition": "MATERIALIZED",
                "typed_records": [
                    {
                        "record_type": "COMMISSION",
                        "claim_refs": ["t209"],
                        "roles": [
                            {"role": "amount", "source_ref": "t209", "literal_fragment": "999.00"},
                            {"role": "currency", "source_ref": "t203", "literal_fragment": "RUB"},
                        ],
                        "withholding_status": "NOT_APPLICABLE",
                    }
                ],
            }
        ],
    }
    with pytest.raises(benchmark.TypedRegistersBenchmarkError, match="typed_record_invented_literal"):
        benchmark.validate_typed_response(response, batch=batch)


def test_withholding_statement_without_amount_is_preserved() -> None:
    row = _row("r001", 2)
    row["elements"][1]["literal"] = "Coupon. Tax withheld."
    batch = {"schema_version": "broker_typed_projection_batch_v0", "source_records": [row]}
    response = {
        "schema_version": benchmark.RESPONSE_SCHEMA_VERSION,
        "classifications": [
            {
                "assertion_id": "r001",
                "disposition": "MATERIALIZED",
                "typed_records": [
                    {
                        "record_type": "TAX_WITHHELD",
                        "claim_refs": ["t202"],
                        "roles": [
                            {"role": "date", "source_ref": "t201", "literal_fragment": "01.02.2024"},
                            {"role": "currency", "source_ref": "t203", "literal_fragment": "RUB"},
                        ],
                        "withholding_status": "STATED_WITHOUT_AMOUNT",
                    }
                ],
            }
        ],
    }
    validated = benchmark.validate_typed_response(response, batch=batch)
    record = validated["classifications"][0]["typed_records"][0]
    assert record["withholding_status"] == "STATED_WITHOUT_AMOUNT"
    assert all(item["role"] != "amount" for item in record["roles"])


def test_deterministic_materialization_preserves_components_and_residuals() -> None:
    trade = _row("r001", 2)
    residual = _row("r002", 3)
    residual["logical_table_id"] = "g002"
    batch = {"schema_version": "broker_typed_projection_batch_v0", "source_records": [trade, residual]}
    mapping = _mapping()
    mapping["classifications"].append(
        {"assertion_id": "g002", "register_kind": "CASH_OPERATIONS", "column_bindings": [], "side_markers": []}
    )
    deterministic, residual_rows = benchmark.deterministic_materialize(batch=batch, mapping=mapping)
    assert [item["assertion_id"] for item in deterministic] == ["r001"]
    assert Counter(record["record_type"] for record in deterministic[0]["typed_records"]) == Counter(
        {"SECURITY_DISPOSAL": 1, "ACCRUED_COUPON_COMPONENT": 1, "TRANSACTION_CHARGE": 2}
    )
    assert [item["source_record_id"] for item in residual_rows] == ["r002"]


def test_idempotency_keeps_same_values_from_distinct_source_rows() -> None:
    rows = [_row("r001", 2), _row("r002", 3)]
    batch = {"schema_version": "broker_typed_projection_batch_v0", "source_records": rows}
    deterministic, residual = benchmark.deterministic_materialize(batch=batch, mapping=_mapping())
    assert residual == []
    projection = {"schema_version": benchmark.RESPONSE_SCHEMA_VERSION, "classifications": deterministic}
    ids = [record["typed_record_id"] for item in deterministic for record in item["typed_records"]]
    probe = benchmark.sqlite_idempotency_probe(projection)
    assert len(ids) == len(set(ids)) == 8
    assert probe == {"first_projection_records": 8, "after_second_materialization": 8, "duplicates_created": 0}


def test_verdict_prefers_only_fully_qualified_deterministic_first() -> None:
    qualified = {
        "validated_runs": 3,
        "exact_repeatability": True,
        "source_accounting_exact": True,
        "source_fidelity_exact": True,
        "provenance_valid": True,
        "idempotency_proven": True,
    }
    failed = {**qualified, "source_fidelity_exact": False}
    assert benchmark.choose_verdict(
        {
            "A_structural_direct": failed,
            "B_deterministic_first": qualified,
            "C_large_context_direct": failed,
        }
    ) == "DETERMINISTIC_FIRST_BROKER_ETL_PREFERRED"


def test_fidelity_allows_a_valid_claim_ref_superset() -> None:
    base = {
        "record_type": "COMMISSION",
        "claim_refs": ["t201"],
        "roles": [
            {"role": "amount", "source_ref": "t209", "literal_fragment": "0.50"},
            {"role": "currency", "source_ref": "t203", "literal_fragment": "RUB"},
        ],
        "withholding_status": "NOT_APPLICABLE",
    }
    superset = {**base, "claim_refs": ["t201", "t203", "t209"]}
    assert benchmark._record_signature(base) == benchmark._record_signature(superset)
