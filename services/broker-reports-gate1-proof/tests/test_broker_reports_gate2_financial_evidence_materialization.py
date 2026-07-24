from __future__ import annotations

import ast
import copy
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_catalog import (  # noqa: E402
    SUPPORTED_SOURCE_FAMILIES,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContractFactory,
    Gate2FinancialEvidenceDecisionError,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402
    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
    MATERIALIZATION_POLICY_VERSION,
    FinancialEvidenceAuthoritativeSourceValue,
    FinancialEvidenceExecutionMetadata,
    FinancialEvidenceSourceLineage,
    Gate2FinancialEvidenceMaterializationError,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceSourcePackageFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
    validate_financial_evidence_inputs,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)


MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_materialization.py"
)

_VALUE_DEFINITIONS = (
    (
        "value:amount:1",
        "source:cell:amount",
        "source_decimal",
        "-00120.500",
        ("amount",),
    ),
    (
        "value:date:1",
        "source:cell:date",
        "source_date",
        "2025-12-31",
        ("as_of_date",),
    ),
    (
        "value:scope:1",
        "source:table:1",
        "source_reference",
        "Synthetic Statement",
        ("statement_scope",),
    ),
    (
        "value:printed_label:1",
        "source:cell:printed-label",
        "source_reference",
        "Printed synthetic total",
        ("printed_label_evidence_ref",),
    ),
    (
        "value:period:1",
        "source:header:period",
        "source_period",
        "2025 Q4",
        ("period",),
    ),
    (
        "value:currency:1",
        "source:header:currency",
        "source_currency",
        "rub",
        ("currency",),
    ),
    (
        "value:label:1",
        "source:cell:label",
        "source_text",
        "  Synthetic cash balance  ",
        ("source_label",),
    ),
)


def _lineage(index: int) -> FinancialEvidenceSourceLineage:
    return FinancialEvidenceSourceLineage(
        document_ref="document:synthetic:1",
        page_ref="page:1",
        table_ref="table:1",
        row_ref=f"row:{index}",
        cell_ref=f"cell:{index}",
    )


def _source_values():
    return tuple(
        FinancialEvidenceAuthoritativeSourceValue(
            source_value_ref=source_value_ref,
            source_ref=source_ref,
            value_type=value_type,
            literal_value=literal_value,
            source_evidence_refs=(
                "evidence:table:1",
                f"evidence:cell:{index}",
            ),
            lineage=_lineage(index),
        )
        for index, (
            source_value_ref,
            source_ref,
            value_type,
            literal_value,
            _,
        ) in enumerate(_VALUE_DEFINITIONS, start=1)
    )


def _candidates(
    *,
    source_ref_override: str | None = None,
) -> tuple[FinancialEvidenceValueCandidate, ...]:
    return tuple(
        FinancialEvidenceValueCandidate(
            source_value_ref=source_value_ref,
            source_ref=(
                source_ref_override
                if source_ref_override and index == 1
                else source_ref
            ),
            value_type=value_type,
            allowed_roles=allowed_roles,
        )
        for index, (
            source_value_ref,
            source_ref,
            value_type,
            _,
            allowed_roles,
        ) in enumerate(_VALUE_DEFINITIONS, start=1)
    )


def _contract(
    *,
    source_ref_override: str | None = None,
):
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    package = FinancialEvidenceDecisionPackage(
        source_scope_ref="scope:table:1",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        candidates=_candidates(source_ref_override=source_ref_override),
    )
    return Gate2FinancialEvidenceDecisionContractFactory(
        registry=registry,
        package=package,
    ).create()


def _source_package(
    *,
    source_values=None,
):
    return Gate2FinancialEvidenceSourcePackageFactory(
        package_ref="source-package:synthetic:1",
        normalization_run_ref="normalization:synthetic:1",
        document_ref="document:synthetic:1",
        source_scope_ref="scope:table:1",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        source_values=(
            _source_values() if source_values is None else source_values
        ),
        source_evidence_refs=(
            "evidence:document:1",
            "evidence:table:1",
        ),
        completeness="restricted",
        restriction_codes=("restriction:synthetic:1",),
        issue_refs=("issue:synthetic:1",),
    ).create()


def _cash_bindings():
    return {
        "amount": "value:amount:1",
        "as_of_date": "value:date:1",
        "statement_scope": "value:scope:1",
        "balance_class": None,
        "currency": "value:currency:1",
        "source_label": "value:label:1",
        "unit": None,
    }


def _printed_bindings():
    return {
        "amount": "value:amount:1",
        "printed_label_evidence_ref": "value:printed_label:1",
        "statement_scope": "value:scope:1",
        "as_of_date": None,
        "currency": "value:currency:1",
        "period": "value:period:1",
        "source_label": "value:label:1",
        "unit": None,
    }


def _typed_payload(
    input_type_id: str = "cash_balance_snapshot_v1",
    bindings=None,
):
    return {
        "decision": {
            "disposition": "typed_input",
            "input_type_id": input_type_id,
            "value_bindings": (
                _cash_bindings() if bindings is None else bindings
            ),
            "reason_code": "typed_supported",
        }
    }


def _unclassified_payload(*, drop_last: bool = False):
    bindings = [
        {
            "role_id": allowed_roles[0],
            "source_value_ref": source_value_ref,
        }
        for (
            source_value_ref,
            _,
            _,
            _,
            allowed_roles,
        ) in _VALUE_DEFINITIONS
    ]
    if drop_last:
        bindings.pop()
    return {
        "decision": {
            "disposition": "unclassified_financial_input",
            "value_bindings": bindings,
            "reason_code": "no_registry_type",
        }
    }


def _validated(model_output, *, contract=None):
    active_contract = contract or _contract()
    return Gate2FinancialEvidenceValidatedDecisionFactory(
        contract=active_contract
    ).create(model_output)


def _materializer(
    *,
    source_package=None,
    execution_ref: str = "execution:synthetic:1",
):
    package = source_package or _source_package()
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    return Gate2FinancialEvidenceMaterializerFactory(
        registry=registry,
        source_package=package,
        execution_metadata=FinancialEvidenceExecutionMetadata(
            execution_ref=execution_ref,
            decision_validation_ref="validation:synthetic:1",
        ),
    ).create()


def _materialize(model_output, **kwargs):
    return _materializer(**kwargs).materialize(
        validated_decision=_validated(model_output)
    )


def _sha256_json(payload) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_successor_schema_is_explicit_and_does_not_redefine_source_facts():
    assert FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION == (
        "broker_reports_financial_evidence_inputs_v1"
    )
    assert MATERIALIZATION_POLICY_VERSION == (
        "broker_reports_financial_evidence_materialization_v1"
    )
    assert FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION != (
        "broker_reports_source_facts_v0"
    )


@pytest.mark.parametrize(
    ("input_type_id", "bindings", "temporal_role"),
    (
        (
            "cash_balance_snapshot_v1",
            _cash_bindings(),
            "as_of_date",
        ),
        (
            "printed_financial_metric_v1",
            _printed_bindings(),
            "period",
        ),
    ),
)
def test_typed_input_materialization_is_registry_bound_and_complete(
    input_type_id: str,
    bindings,
    temporal_role: str,
):
    result = _materialize(_typed_payload(input_type_id, bindings))
    typed = result["typed_inputs"][0]

    assert result["terminal_disposition"] == "typed_input"
    assert result["unclassified_inputs"] == []
    assert typed["input_type_id"] == input_type_id
    assert typed["registry_hash"] == result["registry"]["registry_hash"]
    assert typed["date_period"][temporal_role]
    assert typed["currency_unit"] == {"currency": "RUB"}
    assert typed["source_sign_by_value_ref"]["value:amount:1"] == (
        "negative"
    )
    assert typed["completeness"] == "restricted"
    assert typed["restriction_codes"] == ["restriction:synthetic:1"]
    assert typed["issue_refs"] == ["issue:synthetic:1"]
    assert result["coverage"]["scope_accounted"] is True


def test_literal_value_is_preserved_and_comparison_value_is_code_derived():
    result = _materialize(_typed_payload())
    values = {
        item["source_value_ref"]: item
        for item in result["typed_inputs"][0]["source_values"]
    }

    assert values["value:amount:1"]["literal_value"] == "-00120.500"
    assert values["value:amount:1"][
        "normalized_comparison_value"
    ] == "-120.5"
    assert values["value:label:1"]["literal_value"] == (
        "  Synthetic cash balance  "
    )
    assert values["value:label:1"][
        "normalized_comparison_value"
    ] == "synthetic cash balance"
    assert values["value:currency:1"][
        "normalized_comparison_value"
    ] == "RUB"


def test_source_provenance_and_ownership_are_complete():
    result = _materialize(_typed_payload())
    typed = result["typed_inputs"][0]

    assert typed["source_evidence_refs"] == sorted(
        typed["source_evidence_refs"]
    )
    assert {
        "evidence:document:1",
        "evidence:table:1",
        "evidence:cell:1",
    } <= set(typed["source_evidence_refs"])
    assert all(
        item["document_ref"] == "document:synthetic:1"
        and item["page_ref"] == "page:1"
        and item["table_ref"] == "table:1"
        and item["row_ref"]
        for item in typed["lineage"]
    )
    assert typed["source_ownership"] == {
        "normalization_run_ref": "normalization:synthetic:1",
        "document_ref": "document:synthetic:1",
        "source_package_ref": "source-package:synthetic:1",
        "source_scope_ref": "scope:table:1",
    }


def test_stable_input_identity_is_independent_of_execution_metadata():
    first = _materialize(
        _typed_payload(),
        execution_ref="execution:synthetic:1",
    )
    second = _materialize(
        _typed_payload(),
        execution_ref="execution:synthetic:2",
    )

    assert first["typed_inputs"][0]["input_id"] == (
        second["typed_inputs"][0]["input_id"]
    )
    assert first["artifact_id"] == second["artifact_id"]
    assert first["integrity_hash"] != second["integrity_hash"]


def test_stable_identity_changes_when_registry_identity_value_changes():
    first = _materialize(_typed_payload())
    changed_values = tuple(
        replace(item, literal_value="2026-01-31")
        if item.source_value_ref == "value:date:1"
        else item
        for item in _source_values()
    )
    changed_package = _source_package(source_values=changed_values)
    changed = _materializer(
        source_package=changed_package
    ).materialize(validated_decision=_validated(_typed_payload()))

    assert first["typed_inputs"][0]["input_id"] != (
        changed["typed_inputs"][0]["input_id"]
    )


def test_ordering_does_not_change_materialization_or_hashes():
    first = _materialize(_typed_payload())
    reversed_package = _source_package(
        source_values=tuple(reversed(_source_values()))
    )
    second = _materializer(
        source_package=reversed_package
    ).materialize(validated_decision=_validated(_typed_payload()))

    assert first == second


def test_unclassified_terminal_preserves_every_literal_value_and_ref():
    result = _materialize(_unclassified_payload())
    unclassified = result["unclassified_inputs"][0]

    assert result["typed_inputs"] == []
    assert unclassified["registry_gap"] is True
    assert unclassified["typed_input_published"] is False
    assert len(unclassified["source_values"]) == len(_VALUE_DEFINITIONS)
    assert {
        item["source_value_ref"] for item in unclassified["source_values"]
    } == {
        item[0] for item in _VALUE_DEFINITIONS
    }
    assert {
        item["literal_value"] for item in unclassified["source_values"]
    } == {
        item[3] for item in _VALUE_DEFINITIONS
    }
    assert len(result["coverage"]["bound_source_value_refs"]) == (
        len(_VALUE_DEFINITIONS)
    )


def test_unclassified_candidate_omission_fails_closed():
    with pytest.raises(Gate2FinancialEvidenceMaterializationError) as exc:
        _materialize(_unclassified_payload(drop_last=True))

    assert exc.value.code == "financial_evidence_unclassified_value_loss"


@pytest.mark.parametrize(
    ("disposition", "reason_code"),
    (
        ("no_financial_input", "non_financial_content"),
        ("unsupported", "source_shape_unsupported"),
    ),
)
def test_non_input_dispositions_close_scope_without_fake_object(
    disposition: str,
    reason_code: str,
):
    result = _materialize(
        {
            "decision": {
                "disposition": disposition,
                "reason_code": reason_code,
            }
        }
    )

    assert result["typed_inputs"] == []
    assert result["unclassified_inputs"] == []
    assert result["coverage"]["scope_accounted"] is True
    assert result["coverage"]["terminal_disposition"] == disposition
    assert result["coverage"]["bound_source_value_refs"] == []


def test_model_cannot_supply_system_metadata_to_materializer():
    payload = _typed_payload()
    payload["decision"]["artifact_id"] = "model-owned"  # type: ignore[index]

    with pytest.raises(Gate2FinancialEvidenceDecisionError) as exc:
        _validated(payload)

    assert exc.value.code == (
        "financial_evidence_decision_typed_shape_invalid"
    )


def test_candidate_authority_mismatch_fails_closed():
    contract = _contract(source_ref_override="source:tampered")
    validated = _validated(_typed_payload(), contract=contract)

    with pytest.raises(Gate2FinancialEvidenceMaterializationError) as exc:
        _materializer().materialize(validated_decision=validated)

    assert exc.value.code == (
        "financial_evidence_source_candidate_authority_mismatch"
    )


def test_tampered_source_package_integrity_fails_before_materialization():
    source_package = replace(
        _source_package(),
        completeness="complete",
    )

    with pytest.raises(Gate2FinancialEvidenceMaterializationError) as exc:
        _materializer(source_package=source_package)

    assert exc.value.code == (
        "financial_evidence_source_package_integrity_invalid"
    )


@pytest.mark.parametrize(
    ("source_value_ref", "literal_value", "expected_code"),
    (
        (
            "value:amount:1",
            "not-a-decimal",
            "financial_evidence_decimal_invalid",
        ),
        (
            "value:date:1",
            "31.12.2025",
            "financial_evidence_date_invalid",
        ),
    ),
)
def test_unsafe_comparison_normalization_fails_closed(
    source_value_ref: str,
    literal_value: str,
    expected_code: str,
):
    invalid_values = tuple(
        replace(item, literal_value=literal_value)
        if item.source_value_ref == source_value_ref
        else item
        for item in _source_values()
    )

    with pytest.raises(Gate2FinancialEvidenceMaterializationError) as exc:
        _source_package(source_values=invalid_values)

    assert exc.value.code == expected_code


def test_integrity_validator_detects_nested_value_tampering():
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    result = _materialize(_typed_payload())
    tampered = copy.deepcopy(result)
    tampered["typed_inputs"][0]["source_values"][0][
        "literal_value"
    ] = "999"
    unsigned = dict(tampered)
    unsigned.pop("integrity_hash")
    tampered["integrity_hash"] = _sha256_json(unsigned)

    with pytest.raises(Gate2FinancialEvidenceMaterializationError) as exc:
        validate_financial_evidence_inputs(
            payload=tampered,
            registry=registry,
        )

    assert exc.value.code == (
        "financial_evidence_terminal_integrity_invalid"
    )


def test_output_has_no_gate3_or_model_owned_fields():
    rendered = json.dumps(_materialize(_typed_payload()), sort_keys=True)

    for forbidden in (
        '"gate3"',
        '"ledger_candidate"',
        '"relevance"',
        '"tax_calculation"',
        '"provider_response"',
        '"model_artifact_id"',
    ):
        assert forbidden not in rendered


def test_materialization_is_factory_managed_and_closed_world():
    source = MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "Gate2FinancialEvidenceMaterializerFactory.create" in source
    assert "must not mint input IDs" in source
    assert imported_modules <= {
        "__future__",
        "dataclasses",
        "datetime",
        "decimal",
        "gate2_financial_evidence_decision",
        "gate2_financial_evidence_registry",
        "hashlib",
        "json",
        "re",
        "typing",
        "unicodedata",
    }
    assert "artifact_store" not in source
    assert "customer" not in source
    assert "gate3_context" not in source
