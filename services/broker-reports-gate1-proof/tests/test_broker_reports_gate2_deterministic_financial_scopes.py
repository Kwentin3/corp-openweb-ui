from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_deterministic_financial_scopes.py"
)

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION,
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2DeterministicFinancialScope,
    Gate2DeterministicFinancialScopeError,
    Gate2DeterministicFinancialScopeFromGate1Factory,
    validate_deterministic_financial_scope,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)


def _factory():
    return Gate2DeterministicFinancialScopeFromGate1Factory(
        registry=Gate2FinancialEvidenceRegistryFactory().create()
    )


def _gate1_package(
    *,
    package_id: str = "base_package",
    unit_id: str = "table_unit",
    document_ref: str = "document:synthetic",
    row_ref: str = "row:income",
    amount: str = "120.50",
):
    values = ("Dividend", "2026-01-02", amount, "USD")
    headers = ("description", "date", "amount", "currency")
    cells = []
    source_value_index = []
    source_value_refs = []
    for index, (header, value) in enumerate(
        zip(headers, values, strict=True),
        start=1,
    ):
        cell_ref = f"{unit_id}:cell:{index}"
        value_ref = f"{unit_id}:value:{index}"
        source_value_refs.append(value_ref)
        cells.append(
            {
                "column_ordinal": index,
                "header_label": header,
                "cell_ref": cell_ref,
                "source_value_ref": value_ref,
                "value": value,
            }
        )
        source_value_index.append(
            {
                "source_value_ref": value_ref,
                "row_ref": row_ref,
                "cell_ref": cell_ref,
                "value_path": {
                    "kind": "table_cell",
                    "row_index": 0,
                    "column_index": index - 1,
                },
                "value_checksum_ref": f"checksum:{value_ref}",
            }
        )
    no_fact_ref = f"{unit_id}:header"
    selected_refs = [row_ref, no_fact_ref]
    return {
        "schema_version": "broker_reports_source_fact_package_v0",
        "package_id": package_id,
        "extraction_run_id": "extraction:synthetic",
        "normalization_run_id": "normalization:synthetic",
        "case_id": "case:synthetic",
        "document_ref": document_ref,
        "source_bucket_roles": ["primary_source_refs"],
        "document_context": {
            "usage_modes": ["source_fact"],
            "passport": {"document_kind_candidate": "broker_report"},
        },
        "source_unit": {
            "unit_id": unit_id,
            "unit_kind": "table_row_window",
            "source_input_mode": "normalized_table_projection",
            "private_slice_artifact_ref": f"artifact:{unit_id}",
            "slice_ref": f"slice:{unit_id}",
            "document_ref": document_ref,
            "source_checksum_ref": f"checksum:{unit_id}",
            "slice_payload_checksum_ref": f"payload-checksum:{unit_id}",
            "parser_ref": "parser:synthetic",
            "table_ref": f"table:{unit_id}",
            "row_range_ref": f"row-range:{unit_id}",
            "coverage_ref": f"coverage:{unit_id}",
            "normalized_header_descriptors": [
                {
                    "column_ordinal": index,
                    "normalized_label": header,
                }
                for index, header in enumerate(headers, start=1)
            ],
            "row_refs": [row_ref],
            "row_provenance": [
                {
                    "row_ref": row_ref,
                    "row_ordinal": 1,
                    "row_kind": "fact_candidate",
                }
            ],
            "cell_refs": [item["cell_ref"] for item in cells],
            "cell_provenance": [
                {
                    "row_ordinal": 1,
                    "column_ordinal": index,
                    "row_ref": row_ref,
                    "cell_ref": item["cell_ref"],
                    "source_value_ref": item["source_value_ref"],
                }
                for index, item in enumerate(cells, start=1)
            ],
            "cell_value_refs": source_value_refs,
            "source_value_refs": source_value_refs,
            "source_value_index": source_value_index,
            "private_values": [],
            "text_segment_refs": [],
            "section_refs": [],
            "page_refs": [],
            "character_span_refs": [],
            "segment_provenance": [],
            "normalized_source_projection": {"cells": [list(values)]},
            "model_source_projection": {
                "schema_version": "gate2_model_table_projection_v0",
                "rows": [
                    {
                        "row_ref": row_ref,
                        "row_kind": "fact_candidate",
                        "fact_type_hint": "income",
                        "fact_type_hint_policy": "synthetic",
                        "cells": cells,
                    }
                ],
            },
        },
        "allowed_evidence_refs": selected_refs,
        "allowed_source_value_refs": source_value_refs,
        "issue_context": [],
        "allowed_issue_refs": [],
        "forbidden_assumptions": ["do_not_infer_missing_values"],
        "coverage_expectation": {
            "coverage_ref": f"coverage:{unit_id}",
            "selected_source_refs": selected_refs,
            "ignorable_header_refs": [no_fact_ref],
            "ignorable_blank_refs": [],
            "layout_candidate_refs": [],
            "mandatory_no_fact_results": [
                {
                    "source_ref": no_fact_ref,
                    "reason_code": "header_row",
                }
            ],
        },
        "privacy_policy": {
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
        "created_at": "2026-07-25T00:00:00Z",
    }


def test_scope_factory_is_deterministic_and_closes_all_selected_refs():
    first = _gate1_package()
    second = _gate1_package(
        package_id="base_package_2",
        unit_id="table_unit_2",
        document_ref="document:synthetic:2",
        row_ref="row:income:2",
        amount="75.00",
    )

    result = _factory().create(gate1_packages=(first, second))
    repeated = _factory().create(gate1_packages=(second, first))

    assert [item.package for item in result.scopes] == [
        item.package for item in repeated.scopes
    ]
    assert result.safe_summary() == repeated.safe_summary()
    assert "row:income" not in str(result.safe_summary())
    assert "table_unit:header" not in str(result.safe_summary())
    assert result.coverage == {
        "selected_source_refs": [
            "row:income",
            "row:income:2",
            "table_unit:header",
            "table_unit_2:header",
        ],
        "decision_scope_source_refs": [
            "row:income",
            "row:income:2",
        ],
        "deterministic_no_fact_source_refs": [
            "table_unit:header",
            "table_unit_2:header",
        ],
        "selected_source_refs_total": 4,
        "decision_scope_source_refs_total": 2,
        "deterministic_no_fact_source_refs_total": 2,
        "unaccounted_source_refs": [],
        "duplicate_terminal_owner_refs": [],
        "all_selected_refs_terminally_accounted": True,
        "model_calls_total": 0,
    }
    assert result.safe_summary()["provider_calls_total"] == 0
    assert result.safe_summary()["persistence_writes_total"] == 0


def test_scope_preserves_gate1_values_refs_lineage_and_registry_authority():
    result = _factory().create(gate1_packages=(_gate1_package(),))
    assert len(result.scopes) == 1
    scope = result.scopes[0]
    package = scope.package

    assert (
        package["schema_version"]
        == DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION
    )
    assert package["authoritative_source_refs"] == ["row:income"]
    assert package["terminal_coverage_boundary"][
        "all_authorized_refs_accounted"
    ]
    assert package["execution_boundary"] == {
        "provider_calls": 0,
        "semantic_classification": False,
        "materialization": False,
        "persistence": False,
        "production_routing": False,
    }
    gate1_values = {
        item["source_value_ref"]: item
        for item in package["source_values"]
        if item["value_authority"] == "gate1_authoritative_literal"
    }
    assert {
        ref: item["literal_value"] for ref, item in gate1_values.items()
    } == {
        "table_unit:value:1": "Dividend",
        "table_unit:value:2": "2026-01-02",
        "table_unit:value:3": "120.50",
        "table_unit:value:4": "USD",
    }
    assert all(
        item["lineage"]["document_ref"] == "document:synthetic"
        and item["lineage"]["table_ref"] == "table:table_unit"
        and item["lineage"]["row_ref"] == "row:income"
        and item["lineage"]["cell_ref"]
        for item in gate1_values.values()
    )
    assert package["source_family_evidence"] == {
        "source_family_id": (
            "broker_reports_normalized_table_projection_v0"
        ),
        "resolution": "deterministic_gate1_unit_kind_mapping",
        "source_unit_kinds": ["table_row_window"],
        "source_unit_refs": [
            next(
                item["derived_source_unit_ref"]
                for item in package["routing_hints"]
            )
        ],
    }
    assert package["registry"]["registry_version"] == (
        scope.decision_contract.registry.registry_version
    )
    assert package["registry"]["registry_hash"] == (
        scope.decision_contract.registry.registry_hash
    )
    assert package["registry"]["eligible_input_type_ids"]
    assert set(
        package["decision_contract"]["candidate_source_value_refs"]
    ) == {item["source_value_ref"] for item in package["source_values"]}
    validate_deterministic_financial_scope(scope)


def test_scope_validator_rejects_integrity_and_terminal_coverage_tampering():
    scope = _factory().create(
        gate1_packages=(_gate1_package(),)
    ).scopes[0]
    tampered_package = copy.deepcopy(scope.package)
    tampered_package["terminal_coverage_boundary"][
        "accounted_total"
    ] = 0
    tampered = Gate2DeterministicFinancialScope(
        package=tampered_package,
        decision_contract=scope.decision_contract,
        source_package=scope.source_package,
        selected_source_refs=scope.selected_source_refs,
    )

    with pytest.raises(
        Gate2DeterministicFinancialScopeError,
        match="deterministic_financial_scope_integrity_invalid",
    ):
        validate_deterministic_financial_scope(tampered)


def test_scope_factory_fails_closed_on_literal_conflict():
    package = _gate1_package()
    conflicting_cell = copy.deepcopy(
        package["source_unit"]["model_source_projection"]["rows"][0][
            "cells"
        ][2]
    )
    conflicting_cell["value"] = "999.00"
    package["source_unit"]["model_source_projection"]["rows"][0][
        "cells"
    ].append(conflicting_cell)

    with pytest.raises(
        Gate2DeterministicFinancialScopeError,
        match=(
            "deterministic_financial_scope_authoritative_literal_conflict"
        ),
    ):
        _factory().create(gate1_packages=(package,))


def test_scope_factory_fails_closed_on_missing_lineage():
    package = _gate1_package()
    package["source_unit"]["table_ref"] = None
    for item in package["source_unit"]["source_value_index"]:
        item.pop("row_ref", None)
        item.pop("cell_ref", None)

    with pytest.raises(
        Gate2DeterministicFinancialScopeError,
        match="deterministic_financial_scope_source_ref_missing",
    ):
        _factory().create(gate1_packages=(package,))


def test_factory_boundary_anchors_are_explicit():
    assert (
        "Gate2DeterministicFinancialScopeFromGate1Factory.create"
        in FACTORY_REQUIRED
    )
    assert "must not mint deterministic financial scopes" in FORBIDDEN


def test_factory_module_has_no_provider_persistence_or_production_runtime_import():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    modules = {
        str(node.module or "")
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }

    assert not {
        name
        for name in imports
        if "StructuredModelClient" in name
        or "ArtifactStore" in name
        or "MaterializerFactory" in name
    }
    assert not {
        module
        for module in modules
        if module.endswith("gate2_financial_evidence_production_runtime")
        or module.endswith("gate2_model_clients")
        or module.endswith("artifact_store")
    }
