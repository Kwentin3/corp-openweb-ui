from __future__ import annotations

import ast
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_context import (  # noqa: E402
    FINANCIAL_CONTEXT_PROJECTION_POLICY_VERSION,
    FINANCIAL_CONTEXT_SCHEMA_VERSION,
    Gate2FinancialContextProjectionError,
    Gate2FinancialContextProjectionFactory,
    validate_financial_context,
)
from broker_reports_gate1.gate2_financial_evidence_catalog import (  # noqa: E402
    SUPPORTED_SOURCE_FAMILIES,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContractFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceExecutionMetadata,
    FinancialEvidenceSourceLineage,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceSourcePackageFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)


BOUNDARY_MODULE_PATHS = (
    ROOT / "broker_reports_gate1" / "gate2_financial_context.py",
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_context_contracts.py",
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_context_validation.py",
)

_DEFINITIONS = (
    (
        "amount",
        "source_decimal",
        "-120.50",
        ("amount",),
    ),
    (
        "date",
        "source_date",
        "2025-12-31",
        ("as_of_date",),
    ),
    (
        "scope",
        "source_reference",
        "Synthetic statement",
        ("statement_scope",),
    ),
    (
        "printed-label",
        "source_reference",
        "Synthetic printed total",
        ("printed_label_evidence_ref",),
    ),
    (
        "period",
        "source_period",
        "2025 Q4",
        ("period",),
    ),
    (
        "currency",
        "source_currency",
        "RUB",
        ("currency",),
    ),
    (
        "label",
        "source_text",
        "Synthetic source label",
        ("source_label",),
    ),
)


def _registry():
    return Gate2FinancialEvidenceRegistryFactory().create()


def _source_values(suffix: str):
    return tuple(
        FinancialEvidenceAuthoritativeSourceValue(
            source_value_ref=f"value:{name}:{suffix}",
            source_ref=f"source:cell:{name}:{suffix}",
            value_type=value_type,
            literal_value=literal_value,
            source_evidence_refs=(
                f"evidence:table:{suffix}",
                f"evidence:cell:{name}:{suffix}",
            ),
            lineage=FinancialEvidenceSourceLineage(
                document_ref=f"document:synthetic:{suffix}",
                page_ref=f"page:{suffix}:1",
                table_ref=f"table:{suffix}:1",
                row_ref=f"row:{suffix}:{index}",
                cell_ref=f"cell:{suffix}:{index}",
            ),
        )
        for index, (
            name,
            value_type,
            literal_value,
            _,
        ) in enumerate(_DEFINITIONS, start=1)
    )


def _candidates(suffix: str):
    return tuple(
        FinancialEvidenceValueCandidate(
            source_value_ref=f"value:{name}:{suffix}",
            source_ref=f"source:cell:{name}:{suffix}",
            value_type=value_type,
            allowed_roles=allowed_roles,
        )
        for name, value_type, _, allowed_roles in _DEFINITIONS
    )


def _source_package(suffix: str):
    return Gate2FinancialEvidenceSourcePackageFactory(
        package_ref=f"source-package:synthetic:{suffix}",
        normalization_run_ref=f"normalization:synthetic:{suffix}",
        document_ref=f"document:synthetic:{suffix}",
        source_scope_ref=f"scope:table:{suffix}",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        source_values=_source_values(suffix),
        source_evidence_refs=(
            f"evidence:document:{suffix}",
            f"evidence:table:{suffix}",
        ),
        completeness="restricted",
        restriction_codes=(f"restriction:synthetic:{suffix}",),
        issue_refs=(f"issue:synthetic:{suffix}",),
    ).create()


def _decision(status: str, suffix: str):
    if status == "cash":
        return {
            "decision": {
                "disposition": "typed_input",
                "input_type_id": "cash_balance_snapshot_v1",
                "value_bindings": {
                    "amount": f"value:amount:{suffix}",
                    "as_of_date": f"value:date:{suffix}",
                    "statement_scope": f"value:scope:{suffix}",
                    "balance_class": None,
                    "currency": f"value:currency:{suffix}",
                    "source_label": f"value:label:{suffix}",
                    "unit": None,
                },
                "reason_code": "typed_supported",
            }
        }
    if status == "printed":
        return {
            "decision": {
                "disposition": "typed_input",
                "input_type_id": "printed_financial_metric_v1",
                "value_bindings": {
                    "amount": f"value:amount:{suffix}",
                    "printed_label_evidence_ref": (
                        f"value:printed-label:{suffix}"
                    ),
                    "statement_scope": f"value:scope:{suffix}",
                    "as_of_date": None,
                    "currency": f"value:currency:{suffix}",
                    "period": f"value:period:{suffix}",
                    "source_label": f"value:label:{suffix}",
                    "unit": None,
                },
                "reason_code": "typed_supported",
            }
        }
    if status == "unclassified":
        return {
            "decision": {
                "disposition": "unclassified_financial_input",
                "value_bindings": [
                    {
                        "role_id": allowed_roles[0],
                        "source_value_ref": f"value:{name}:{suffix}",
                    }
                    for name, _, _, allowed_roles in _DEFINITIONS
                ],
                "reason_code": "no_registry_type",
            }
        }
    if status == "no_financial":
        return {
            "decision": {
                "disposition": "no_financial_input",
                "reason_code": "non_financial_content",
            }
        }
    return {
        "decision": {
            "disposition": "unsupported",
            "reason_code": "source_shape_unsupported",
        }
    }


def _case(
    status: str,
    suffix: str,
    *,
    execution_suffix: str = "1",
):
    registry = _registry()
    source_package = _source_package(suffix)
    decision_package = FinancialEvidenceDecisionPackage(
        source_scope_ref=source_package.source_scope_ref,
        source_family_id=source_package.source_family_id,
        candidates=_candidates(suffix),
    )
    contract = Gate2FinancialEvidenceDecisionContractFactory(
        registry=registry,
        package=decision_package,
    ).create()
    validated = Gate2FinancialEvidenceValidatedDecisionFactory(
        contract=contract
    ).create(_decision(status, suffix))
    artifact = Gate2FinancialEvidenceMaterializerFactory(
        registry=registry,
        source_package=source_package,
        execution_metadata=FinancialEvidenceExecutionMetadata(
            execution_ref=(
                f"execution:synthetic:{suffix}:{execution_suffix}"
            ),
            decision_validation_ref=(
                f"validation:synthetic:{suffix}:{execution_suffix}"
            ),
        ),
    ).create().materialize(validated_decision=validated)
    return artifact, source_package


def _project(*cases):
    return Gate2FinancialContextProjectionFactory(
        registry=_registry()
    ).create(
        materialized_artifacts=tuple(item[0] for item in cases),
        source_packages=tuple(item[1] for item in cases),
    )


def test_context_contract_is_explicit_and_minimal():
    assert FINANCIAL_CONTEXT_SCHEMA_VERSION == (
        "broker_reports_gate2_financial_context_v1"
    )
    assert FINANCIAL_CONTEXT_PROJECTION_POLICY_VERSION == (
        "broker_reports_gate2_financial_context_projection_v1"
    )


def test_typed_context_is_structured_literal_and_source_bound():
    context = _project(_case("cash", "cash"))
    entry = context["entries"][0]
    interpretation = entry["interpretation_representation"]

    assert entry["status"] == "typed_input"
    assert interpretation["representation_role"] == "interpretation"
    assert interpretation["input_type"]["input_type_id"] == (
        "cash_balance_snapshot_v1"
    )
    assert interpretation["literal_source_labels"] == [
        "Synthetic source label"
    ]
    assert {
        item["role_id"] for item in interpretation["values"]
    } >= {"amount", "as_of_date", "statement_scope"}
    assert interpretation["date_period"] == {
        "as_of_date": "2025-12-31"
    }
    assert interpretation["currency_unit"] == {"currency": "RUB"}
    assert interpretation["source_location"] == {
        "document_ref": "document:synthetic:cash",
        "page_refs": ["page:cash:1"],
        "source_scope_ref": "scope:table:cash",
    }


def test_printed_total_is_explicitly_not_a_calculated_aggregate():
    printed = _project(_case("printed", "printed"))
    cash = _project(_case("cash", "cash"))

    assert printed["entries"][0]["interpretation_representation"][
        "aggregate_semantics"
    ] == "source_printed"
    assert cash["entries"][0]["interpretation_representation"][
        "aggregate_semantics"
    ] == "not_aggregate"
    assert printed["scope_coverage"]["calculated_aggregates_total"] == 0


def test_unclassified_values_remain_visible_without_canonical_type():
    context = _project(_case("unclassified", "gap"))
    interpretation = context["entries"][0][
        "interpretation_representation"
    ]

    assert interpretation["status"] == (
        "unclassified_financial_input"
    )
    assert interpretation["input_type"] is None
    assert interpretation["aggregate_semantics"] == "unclassified"
    assert len(interpretation["values"]) == len(_DEFINITIONS)
    assert interpretation["terminal_reason_code"] == "no_registry_type"


@pytest.mark.parametrize("status", ("no_financial", "unsupported"))
def test_non_input_terminal_scope_has_one_interpretation_without_values(
    status: str,
):
    context = _project(_case(status, status))
    interpretation = context["entries"][0][
        "interpretation_representation"
    ]

    assert interpretation["representation_role"] == "interpretation"
    assert interpretation["input_type"] is None
    assert interpretation["values"] == []
    assert interpretation["aggregate_semantics"] == "not_applicable"
    assert context["scope_coverage"][
        "interpretation_representations_total"
    ] == 1


def test_other_source_representations_are_provenance_only_and_literal_free():
    context = _project(_case("cash", "cash"))
    entry = context["entries"][0]
    provenance = entry["provenance_only_representations"]
    rendered = json.dumps(provenance)

    assert provenance
    assert all(
        item["representation_role"] == "provenance_only"
        for item in provenance
    )
    assert "literal_value" not in rendered
    assert "Synthetic source label" not in rendered
    assert {
        ref
        for item in provenance
        for ref in item["source_value_refs"]
    } == {
        f"value:{name}:cash" for name, *_ in _DEFINITIONS
    }


def test_unbound_package_values_are_only_provenance_in_typed_context():
    context = _project(_case("cash", "cash"))
    entry = context["entries"][0]
    interpretation_refs = {
        item["source_value_ref"]
        for item in entry["interpretation_representation"]["values"]
    }
    provenance_refs = {
        ref
        for item in entry["provenance_only_representations"]
        for ref in item["source_value_refs"]
    }

    assert "value:printed-label:cash" not in interpretation_refs
    assert "value:period:cash" not in interpretation_refs
    assert {"value:printed-label:cash", "value:period:cash"} <= (
        provenance_refs
    )


def test_exact_duplicate_artifact_is_deduplicated_by_code():
    case = _case("cash", "cash")
    context = Gate2FinancialContextProjectionFactory(
        registry=_registry()
    ).create(
        materialized_artifacts=(case[0], case[0]),
        source_packages=(case[1], case[1]),
    )

    assert len(context["entries"]) == 1
    assert context["scope_coverage"][
        "duplicate_interpretation_representations_total"
    ] == 0


def test_conflicting_artifact_for_same_scope_fails_closed():
    first = _case("cash", "cash", execution_suffix="1")
    second = _case("cash", "cash", execution_suffix="2")

    with pytest.raises(Gate2FinancialContextProjectionError) as exc:
        _project(first, second)

    assert exc.value.code == (
        "financial_context_duplicate_interpretation_scope"
    )


def test_multiple_scopes_are_sorted_and_terminally_counted():
    context = _project(
        _case("unsupported", "z"),
        _case("cash", "a"),
        _case("unclassified", "m"),
    )

    assert [
        item["source_scope_ref"] for item in context["entries"]
    ] == [
        "scope:table:a",
        "scope:table:m",
        "scope:table:z",
    ]
    assert context["scope_coverage"]["source_scopes_total"] == 3
    assert context["scope_coverage"]["status_counts"] == {
        "no_financial_input": 0,
        "typed_input": 1,
        "unclassified_financial_input": 1,
        "unsupported": 1,
    }


def test_source_package_set_must_match_artifacts_exactly():
    case = _case("cash", "cash")
    extra = _case("cash", "extra")
    factory = Gate2FinancialContextProjectionFactory(
        registry=_registry()
    )

    with pytest.raises(Gate2FinancialContextProjectionError) as missing:
        factory.create(
            materialized_artifacts=(case[0],),
            source_packages=(),
        )
    assert missing.value.code == (
        "financial_context_source_package_set_mismatch"
    )

    with pytest.raises(Gate2FinancialContextProjectionError) as excess:
        factory.create(
            materialized_artifacts=(case[0],),
            source_packages=(case[1], extra[1]),
        )
    assert excess.value.code == (
        "financial_context_source_package_set_mismatch"
    )


def test_evidence_identity_links_artifact_terminal_and_source_package():
    case = _case("printed", "printed")
    context = _project(case)
    evidence = context["entries"][0]["interpretation_representation"][
        "evidence_identity"
    ]

    assert evidence["financial_evidence_artifact_id"] == (
        case[0]["artifact_id"]
    )
    assert evidence["terminal_object_id"] == (
        case[0]["typed_inputs"][0]["input_id"]
    )
    assert evidence["source_package_ref"] == case[1].package_ref
    assert evidence["source_package_integrity_hash"] == (
        case[1].integrity_hash
    )


def test_context_integrity_validator_detects_tampering():
    registry = _registry()
    context = _project(_case("cash", "cash"))
    tampered = copy.deepcopy(context)
    tampered["entries"][0]["interpretation_representation"][
        "literal_source_labels"
    ] = ["tampered"]

    with pytest.raises(Gate2FinancialContextProjectionError) as exc:
        validate_financial_context(
            payload=tampered,
            registry=registry,
        )

    assert exc.value.code == "financial_context_integrity_invalid"


def test_context_contains_no_raw_gate1_provider_tax_or_answer_payload():
    rendered = json.dumps(_project(_case("printed", "printed")))

    for forbidden in (
        "raw_pdf",
        "pdf_bytes",
        "full_text",
        "crop_image",
        "provider_response",
        "internal_audit",
        "tax_methodology",
        "declaration_mapping",
        "answer_instruction",
        '"calculated_aggregate":',
    ):
        assert forbidden not in rendered


def test_context_projection_is_factory_managed_and_closed_world():
    sources = [
        path.read_text(encoding="utf-8")
        for path in BOUNDARY_MODULE_PATHS
    ]
    source = "\n".join(sources)
    trees = [ast.parse(item) for item in sources]
    imported_modules = {
        node.module
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "Gate2FinancialContextProjectionFactory.create" in source
    assert "must not build, deduplicate or enrich" in source
    assert imported_modules <= {
        "__future__",
        "collections",
        "gate2_financial_context_contracts",
        "gate2_financial_context_validation",
        "gate2_financial_evidence_decision",
        "gate2_financial_evidence_materialization_contracts",
        "gate2_financial_evidence_materialization_validation",
        "gate2_financial_evidence_registry",
        "gate2_financial_evidence_source_package",
        "typing",
    }
    assert "artifact_store" not in source
    assert "provider_clients" not in source
    assert "gate3_context" not in source
