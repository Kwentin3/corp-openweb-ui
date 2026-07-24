from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_context import (  # noqa: E402
    validate_financial_context,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_semantic_visual_financial_context import (  # noqa: E402
    SEMANTIC_VISUAL_ADAPTER_VERSION,
    Gate2SemanticVisualFinancialContextFactory,
    Gate2SemanticVisualFinancialContextError,
    Gate2SemanticVisualTableEvidence,
)


MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_semantic_visual_financial_context.py"
)


def _registry():
    return Gate2FinancialEvidenceRegistryFactory().create()


def _context():
    return Gate2SemanticVisualFinancialContextFactory(
        registry=_registry()
    ).create(
        tables=(
            Gate2SemanticVisualTableEvidence(
                document_ref="document:synthetic",
                table_ref="table:synthetic:1",
                page_ref="page:1",
                description_literals=("Amounts in RUB thousands",),
                header_literals=("Metric", "2025 Q4"),
                data_rows=(
                    ("Cash", "120.50"),
                    ("Receivables", "40.25"),
                    ("Total assets", "160.75"),
                ),
            ),
        )
    )


def test_adapter_materializes_each_data_row_as_valid_gate2_context():
    context = _context()

    validate_financial_context(payload=context, registry=_registry())
    assert SEMANTIC_VISUAL_ADAPTER_VERSION.endswith("_v1")
    assert context["scope_coverage"]["source_scopes_total"] == 3
    assert context["scope_coverage"]["status_counts"] == {
        "no_financial_input": 0,
        "typed_input": 0,
        "unclassified_financial_input": 3,
        "unsupported": 0,
    }
    assert all(
        entry["interpretation_representation"]["source_location"][
            "page_refs"
        ]
        == ["page:1"]
        for entry in context["entries"]
    )
    assert all(
        entry["interpretation_representation"]["currency_unit"]
        == {"currency": "RUB", "unit": "thousands"}
        for entry in context["entries"]
    )


def test_adapter_retains_header_description_and_row_but_not_raw_container():
    context = _context()
    entries = context["entries"]

    assert all(
        "Amounts in RUB thousands"
        in entry["interpretation_representation"]["literal_source_labels"]
        for entry in entries
    )
    assert all(
        "Metric"
        in entry["interpretation_representation"]["literal_source_labels"]
        for entry in entries
    )
    assert {
        label
        for entry in entries
        for label in entry["interpretation_representation"][
            "literal_source_labels"
        ]
    } >= {"Cash", "Receivables", "Total assets"}
    assert "rows" not in repr(context)
    assert "description_literals" not in repr(context)
    assert "header_literals" not in repr(context)


def test_adapter_uses_financial_factories_without_provider_bypass():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
    }

    assert not any(name.startswith("requests") for name in imports)
    assert "post" not in calls
    assert "materialize" in calls
    assert "create" in calls


def test_document_currency_normalization_fails_closed_on_conflict():
    with pytest.raises(
        Gate2SemanticVisualFinancialContextError
    ) as rejected:
        Gate2SemanticVisualFinancialContextFactory(
            registry=_registry()
        ).create(
            tables=(
                Gate2SemanticVisualTableEvidence(
                    document_ref="document:conflict",
                    table_ref="table:conflict",
                    page_ref="page:1",
                    description_literals=("Amounts in EUR",),
                    header_literals=("Metric", "$"),
                    data_rows=(("Total", "1"),),
                ),
            )
        )

    assert rejected.value.code == (
        "semantic_visual_document_currency_conflict"
    )
