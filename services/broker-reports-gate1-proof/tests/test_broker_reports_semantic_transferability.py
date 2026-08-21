from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "qualify_canonical_semantic_transferability.py"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("semantic_transferability", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
study = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(study)
REPO_ROOT = ROOT.parents[1]
REPORT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-21"
    / "BROKER_REPORTS_SEMANTIC_TRANSFERABILITY.md"
)
RECEIPT = REPORT.with_suffix(".receipt.json")


def _context() -> dict:
    return {
        "logical_table_id": "g001",
        "table_identity": {"source_ref": "title", "literal": "Trades"},
        "headers": [
            {"source_ref": f"h{column}", "column": column, "literal": literal}
            for column, literal in enumerate(
                ["Asset", "Date", "Side", "Quantity", "Price", "Amount", "Currency"],
                start=1,
            )
        ],
    }


def test_freeze_is_research_only_and_legacy_is_not_a_fallback() -> None:
    freeze = study._freeze_contract(
        [
            {
                "alias": "one",
                "source_sha256": "a" * 64,
                "size_bytes": 10,
                "pages": 2,
            },
            {
                "alias": "two",
                "source_sha256": "b" * 64,
                "size_bytes": 20,
                "pages": 3,
            },
            {
                "alias": "three",
                "source_sha256": "c" * 64,
                "size_bytes": 30,
                "pages": 4,
            },
        ]
    )
    contract = freeze["semantic_contract"]
    assert contract["task_form"] == "H3+H6+H8+deterministic_materialization"
    assert contract["legacy_fallback"] is False
    assert contract["retry"] is False
    assert contract["repair"] is False
    assert contract["best_of_n"] is False
    assert contract["production_activation"] is False
    assert freeze["expected_locator_calls"] == 9


def test_structural_fingerprint_reuses_exact_copy_and_rejects_change() -> None:
    context = _context()
    fingerprint = study.structural_fingerprint(context)
    assert study.structural_fingerprint(copy.deepcopy(context)) == fingerprint

    reordered = copy.deepcopy(context)
    reordered["headers"].reverse()
    assert study.structural_fingerprint(reordered) != fingerprint

    renamed = copy.deepcopy(context)
    renamed["headers"][0]["literal"] = "Instrument"
    assert study.structural_fingerprint(renamed) != fingerprint

    removed = copy.deepcopy(context)
    removed["headers"].pop()
    assert study.structural_fingerprint(removed) != fingerprint


def test_duplicate_normalized_role_fails_closed() -> None:
    context = _context()
    raw = {
        "schema_version": "v",
        "classifications": [
            {
                "assertion_id": "g001",
                "table_type": "SECURITY_TRADES",
                "columns": [
                    {
                        "header_ref": header["source_ref"],
                        "normalized_role": (
                            "currency" if index in {0, 6} else "unmapped"
                        ),
                    }
                    for index, header in enumerate(context["headers"])
                ],
            }
        ],
    }
    with pytest.raises(study.forms.TaskFormError, match="header_role_duplicate"):
        study.forms.validate_header_forward(
            raw,
            version="v",
            contexts=[context],
            expect_table_type=True,
        )


def test_materializer_preserves_equal_observations_by_source_identity() -> None:
    context = _context()
    truth = {
        "cases": [
            {
                "case_id": "g001",
                "materialization_rows": [2, 3],
            }
        ],
        "residuals": [],
    }
    literals = ["Bond", "01.02.2024", "Buy", "2", "100", "200", "RUB"]
    cells = {
        (row, column): {
            "source_ref": f"r{row}c{column}",
            "row": row,
            "column": column,
            "literal": literal,
        }
        for row in (2, 3)
        for column, literal in enumerate(literals, start=1)
    }
    roles = [
        "asset_name",
        "trade_date",
        "side",
        "quantity",
        "unit_price",
        "gross_amount",
        "currency",
    ]
    mapping = {
        "logical_table_id": "g001",
        "table_type": "SECURITY_TRADES",
        "columns": [
            {"header_ref": header["source_ref"], "normalized_role": role}
            for header, role in zip(context["headers"], roles, strict=True)
        ],
    }
    projection = study._materialize_selected(
        truth=truth,
        contexts={"g001": context},
        cells_by_case={"g001": cells},
        mappings=[mapping],
        side_bindings=[
            {
                "column_role": "side",
                "source_literal": "Buy",
                "normalized_value": "PURCHASE",
            },
            {
                "column_role": "side",
                "source_literal": "Sell",
                "normalized_value": "DISPOSAL",
            },
        ],
    )
    rows = projection["classifications"]
    assert [item["source_record_id"] for item in rows] == ["g001_r2", "g001_r3"]
    assert all(item["disposition"] == "MATERIALIZED" for item in rows)
    assert rows[0]["typed_records"][0]["typed_record_id"] != rows[1]["typed_records"][0]["typed_record_id"]


def test_unmapped_table_never_materializes_values() -> None:
    context = _context()
    mapping = {
        "logical_table_id": "g001",
        "table_type": "UNMAPPED",
        "columns": [
            {"header_ref": header["source_ref"], "normalized_role": "unmapped"}
            for header in context["headers"]
        ],
    }
    projection = study._materialize_selected(
        truth={
            "cases": [{"case_id": "g001", "materialization_rows": [2]}],
            "residuals": [],
        },
        contexts={"g001": context},
        cells_by_case={"g001": {}},
        mappings=[mapping],
        side_bindings=[],
    )
    assert projection["classifications"] == [
        {
            "source_record_id": "g001_r2",
            "disposition": "UNMAPPED",
            "typed_records": [],
        }
    ]


def test_safe_report_and_receipt_are_terminal_and_privacy_clean() -> None:
    report = REPORT.read_text(encoding="utf-8")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["verdict"] == "BROKER_SOURCE_DIALECT_NEEDS_RETHINKING"
    assert receipt["canonical"]["lost_targets"] == 0
    assert receipt["canonical"]["duplicated_working_targets"] == 0
    assert receipt["semantic_execution"]["provider_calls"] == 9
    assert receipt["semantic_execution"]["h3"]["rejected_runs"] == 3
    assert receipt["semantic_execution"]["h6"]["exact_runs"] == 3
    assert receipt["semantic_execution"]["h8"]["correct_decisions_per_run"] == 1
    assert receipt["semantic_execution"]["typed_records_per_run"] == 0
    assert receipt["scope"]["legacy_fallback_used"] is False
    assert receipt["scope"]["production_changed"] is False
    assert receipt["privacy"] == {
        "raw_customer_documents_in_git": False,
        "raw_canonical_in_git": False,
        "raw_model_responses_in_git": False,
        "private_values_in_safe_report": False,
        "private_evidence_outside_repository": True,
    }
    safe_text = report + RECEIPT.read_text(encoding="utf-8")
    for forbidden in (
        "C:\\Users\\",
        ".codex/private-evidence",
        '"absolute_path"',
        '"original_filename"',
    ):
        assert forbidden not in safe_text
