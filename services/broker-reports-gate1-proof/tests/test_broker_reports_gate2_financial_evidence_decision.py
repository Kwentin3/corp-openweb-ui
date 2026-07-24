from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_evidence_catalog import (  # noqa: E402
    SUPPORTED_SOURCE_FAMILIES,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    DECISION_SCHEMA_VERSION,
    DISPOSITIONS,
    FinancialEvidenceDecisionPackage,
    FinancialEvidenceValueCandidate,
    Gate2FinancialEvidenceDecisionContractFactory,
    Gate2FinancialEvidenceDecisionError,
    NoFinancialInputDecision,
    TypedFinancialInputDecision,
    UnclassifiedFinancialInputDecision,
    UnsupportedFinancialInputDecision,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
)


MODULE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_evidence_decision.py"
)


def _candidates() -> tuple[FinancialEvidenceValueCandidate, ...]:
    return (
        FinancialEvidenceValueCandidate(
            source_value_ref="value:amount:1",
            source_ref="source:row:1",
            value_type="source_decimal",
            allowed_roles=("amount",),
        ),
        FinancialEvidenceValueCandidate(
            source_value_ref="value:date:1",
            source_ref="source:cell:date",
            value_type="source_date",
            allowed_roles=("as_of_date",),
        ),
        FinancialEvidenceValueCandidate(
            source_value_ref="value:scope:1",
            source_ref="source:table:1",
            value_type="source_reference",
            allowed_roles=("statement_scope",),
        ),
        FinancialEvidenceValueCandidate(
            source_value_ref="value:printed_label:1",
            source_ref="source:cell:label",
            value_type="source_reference",
            allowed_roles=("printed_label_evidence_ref",),
        ),
        FinancialEvidenceValueCandidate(
            source_value_ref="value:period:1",
            source_ref="source:header:period",
            value_type="source_period",
            allowed_roles=("period",),
        ),
        FinancialEvidenceValueCandidate(
            source_value_ref="value:currency:1",
            source_ref="source:header:currency",
            value_type="source_currency",
            allowed_roles=("currency",),
        ),
        FinancialEvidenceValueCandidate(
            source_value_ref="value:label:1",
            source_ref="source:cell:label",
            value_type="source_text",
            allowed_roles=("source_label",),
        ),
    )


def _contract(
    *,
    candidates: tuple[FinancialEvidenceValueCandidate, ...] | None = None,
    allowed_type_ids: tuple[str, ...] | None = None,
):
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    package = FinancialEvidenceDecisionPackage(
        source_scope_ref="scope:table:1",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        candidates=_candidates() if candidates is None else candidates,
        allowed_type_ids=allowed_type_ids,
    )
    return Gate2FinancialEvidenceDecisionContractFactory(
        registry=registry,
        package=package,
    ).create()


def _cash_bindings() -> dict[str, str | None]:
    return {
        "amount": "value:amount:1",
        "as_of_date": "value:date:1",
        "statement_scope": "value:scope:1",
        "balance_class": None,
        "currency": "value:currency:1",
        "source_label": "value:label:1",
        "unit": None,
    }


def _printed_bindings() -> dict[str, str | None]:
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
    input_type_id: str,
    bindings: dict[str, str | None],
) -> dict[str, object]:
    return {
        "decision": {
            "disposition": "typed_input",
            "input_type_id": input_type_id,
            "value_bindings": bindings,
            "reason_code": "typed_supported",
        }
    }


def _assert_error(code: str, payload: dict[str, object]) -> None:
    with pytest.raises(Gate2FinancialEvidenceDecisionError) as exc:
        _contract().parse_model_output(payload)
    assert exc.value.code == code


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def test_contract_exposes_exactly_four_dispositions_and_version():
    assert DECISION_SCHEMA_VERSION == (
        "broker_reports_gate2_financial_evidence_decision_v1"
    )
    assert DISPOSITIONS == (
        "typed_input",
        "unclassified_financial_input",
        "no_financial_input",
        "unsupported",
    )


@pytest.mark.parametrize(
    ("input_type_id", "bindings"),
    (
        ("cash_balance_snapshot_v1", _cash_bindings()),
        ("printed_financial_metric_v1", _printed_bindings()),
    ),
)
def test_typed_decision_is_registry_and_required_role_bound(
    input_type_id: str,
    bindings: dict[str, str | None],
):
    result = _contract().parse_model_output(
        json.dumps(_typed_payload(input_type_id, bindings))
    )

    assert isinstance(result, TypedFinancialInputDecision)
    assert result.input_type_id == input_type_id
    assert result.reason_code == "typed_supported"
    assert {item.role_id for item in result.value_bindings} >= {
        "amount",
        "statement_scope",
    }


def test_free_type_id_is_rejected():
    _assert_error(
        "financial_evidence_decision_type_not_allowed",
        _typed_payload("model_invented_profit_v1", _cash_bindings()),
    )


def test_typed_without_type_id_is_rejected():
    payload = _typed_payload("cash_balance_snapshot_v1", _cash_bindings())
    del payload["decision"]["input_type_id"]  # type: ignore[index]

    _assert_error(
        "financial_evidence_decision_typed_shape_invalid",
        payload,
    )


def test_typed_without_required_role_is_rejected():
    bindings = _cash_bindings()
    del bindings["amount"]

    _assert_error(
        "financial_evidence_decision_typed_roles_invalid",
        _typed_payload("cash_balance_snapshot_v1", bindings),
    )


def test_typed_null_required_role_is_rejected():
    bindings = _cash_bindings()
    bindings["amount"] = None

    _assert_error(
        "financial_evidence_decision_required_binding_missing",
        _typed_payload("cash_balance_snapshot_v1", bindings),
    )


def test_binding_outside_package_is_rejected():
    bindings = _cash_bindings()
    bindings["amount"] = "value:outside:package"

    _assert_error(
        "financial_evidence_decision_binding_outside_package",
        _typed_payload("cash_balance_snapshot_v1", bindings),
    )


def test_binding_with_wrong_role_or_value_type_is_rejected():
    bindings = _cash_bindings()
    bindings["amount"] = "value:date:1"

    _assert_error(
        "financial_evidence_decision_binding_incompatible",
        _typed_payload("cash_balance_snapshot_v1", bindings),
    )


def test_unclassified_preserves_package_value_refs_without_canonical_type():
    payload = {
        "decision": {
            "disposition": "unclassified_financial_input",
            "value_bindings": [
                {
                    "role_id": "amount",
                    "source_value_ref": "value:amount:1",
                },
                {
                    "role_id": "source_label",
                    "source_value_ref": "value:label:1",
                },
            ],
            "reason_code": "no_registry_type",
        }
    }

    result = _contract().parse_model_output(payload)

    assert isinstance(result, UnclassifiedFinancialInputDecision)
    assert [item.source_value_ref for item in result.value_bindings] == [
        "value:amount:1",
        "value:label:1",
    ]
    assert not hasattr(result, "input_type_id")


def test_unclassified_with_canonical_type_is_rejected():
    payload = {
        "decision": {
            "disposition": "unclassified_financial_input",
            "input_type_id": "cash_balance_snapshot_v1",
            "value_bindings": [
                {
                    "role_id": "amount",
                    "source_value_ref": "value:amount:1",
                }
            ],
            "reason_code": "ambiguous_registry_type",
        }
    }

    _assert_error(
        "financial_evidence_decision_unclassified_shape_invalid",
        payload,
    )


def test_unclassified_without_bindings_is_rejected_after_projection():
    payload = {
        "decision": {
            "disposition": "unclassified_financial_input",
            "value_bindings": [],
            "reason_code": "no_registry_type",
        }
    }

    _assert_error(
        "financial_evidence_decision_unclassified_bindings_invalid",
        payload,
    )


def test_no_financial_input_has_no_binding_or_type_state():
    contract = _contract()
    result = contract.parse_model_output(
        {
            "decision": {
                "disposition": "no_financial_input",
                "reason_code": "non_financial_content",
            }
        }
    )

    assert isinstance(result, NoFinancialInputDecision)
    _assert_error(
        "financial_evidence_decision_terminal_shape_invalid",
        {
            "decision": {
                "disposition": "no_financial_input",
                "value_bindings": {},
                "reason_code": "non_financial_content",
            }
        },
    )


def test_unsupported_is_separate_and_has_no_binding_or_type_state():
    result = _contract().parse_model_output(
        {
            "decision": {
                "disposition": "unsupported",
                "reason_code": "source_shape_unsupported",
            }
        }
    )

    assert isinstance(result, UnsupportedFinancialInputDecision)
    assert result.disposition != "unclassified_financial_input"
    assert not hasattr(result, "value_bindings")


def test_canonical_schema_structurally_separates_all_variants():
    schema = _contract().canonical_schema()
    variants = schema["properties"]["decision"]["anyOf"]
    variant_by_disposition = {
        variant["properties"]["disposition"]["enum"][0]: variant
        for variant in variants
    }

    assert schema["type"] == "object"
    assert schema["required"] == ["decision"]
    assert schema["additionalProperties"] is False
    assert set(variant_by_disposition) == set(DISPOSITIONS)
    assert "input_type_id" not in (
        variant_by_disposition["unclassified_financial_input"]["properties"]
    )
    for disposition in ("no_financial_input", "unsupported"):
        properties = variant_by_disposition[disposition]["properties"]
        assert set(properties) == {"disposition", "reason_code"}
        assert variant_by_disposition[disposition][
            "additionalProperties"
        ] is False


def test_typed_schema_is_derived_from_registry_roles_and_package_refs():
    contract = _contract()
    variants = contract.canonical_schema()["properties"]["decision"]["anyOf"]
    cash = next(
        item
        for item in variants
        if item["properties"].get("input_type_id", {}).get("enum")
        == ["cash_balance_snapshot_v1"]
    )
    bindings = cash["properties"]["value_bindings"]

    assert set(bindings["required"]) == {
        "amount",
        "as_of_date",
        "balance_class",
        "currency",
        "source_label",
        "statement_scope",
        "unit",
    }
    assert bindings["properties"]["amount"]["enum"] == ["value:amount:1"]
    assert bindings["properties"]["as_of_date"]["enum"] == [
        "value:date:1"
    ]
    assert "value:outside:package" not in json.dumps(bindings)


def test_infeasible_typed_variant_is_not_exposed():
    candidates = tuple(
        item
        for item in _candidates()
        if item.source_value_ref != "value:amount:1"
    )
    contract = _contract(candidates=candidates)
    variants = contract.canonical_schema()["properties"]["decision"]["anyOf"]

    assert contract.eligible_type_ids == (
        "cash_balance_snapshot_v1",
        "printed_financial_metric_v1",
    )
    assert all(
        "input_type_id" not in item["properties"] for item in variants
    )


def test_allowed_type_scope_cannot_extend_registry():
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    package = FinancialEvidenceDecisionPackage(
        source_scope_ref="scope:table:1",
        source_family_id=SUPPORTED_SOURCE_FAMILIES[0],
        candidates=_candidates(),
        allowed_type_ids=("model_invented_profit_v1",),
    )

    with pytest.raises(Gate2FinancialEvidenceDecisionError) as exc:
        Gate2FinancialEvidenceDecisionContractFactory(
            registry=registry,
            package=package,
        ).create()
    assert exc.value.code == (
        "financial_evidence_decision_allowed_type_unknown"
    )


def test_openai_and_gemini_are_projections_of_one_canonical_contract():
    contract = _contract()
    canonical = contract.canonical_schema()
    openai = contract.openai_response_format()
    gemini = contract.gemini_response_format()
    gemini_schema = gemini["json_schema"]["schema"]

    assert openai["type"] == "json_schema"
    assert openai["json_schema"]["strict"] is True
    assert openai["json_schema"]["schema"] == canonical
    assert gemini["type"] == "json_schema"
    assert gemini["json_schema"]["strict"] is True
    assert "$schema" not in gemini_schema
    assert all("const" not in item for item in _walk_dicts(gemini_schema))
    assert all("minItems" not in item for item in _walk_dicts(gemini_schema))
    assert "typed_input" in json.dumps(gemini_schema)
    assert "cash_balance_snapshot_v1" in json.dumps(gemini_schema)
    assert contract.provider_schema_hash("openai") != (
        contract.provider_schema_hash("gemini")
    )


def test_schema_and_hashes_are_deterministic_under_package_ordering():
    first = _contract()
    reversed_candidates = tuple(
        FinancialEvidenceValueCandidate(
            source_value_ref=item.source_value_ref,
            source_ref=item.source_ref,
            value_type=item.value_type,
            allowed_roles=tuple(reversed(item.allowed_roles)),
        )
        for item in reversed(_candidates())
    )
    second = _contract(candidates=reversed_candidates)

    assert first.package == second.package
    assert first.canonical_schema() == second.canonical_schema()
    assert first.canonical_schema_hash() == second.canonical_schema_hash()
    assert first.provider_schema_hash("openai") == (
        second.provider_schema_hash("openai")
    )
    assert first.provider_schema_hash("gemini") == (
        second.provider_schema_hash("gemini")
    )


def test_model_contract_has_no_free_json_or_system_owned_fields():
    rendered = json.dumps(_contract().openai_response_format())

    assert '"json_object"' not in rendered
    assert '"strict": true' in rendered
    for forbidden in (
        "artifact_id",
        "canonical_object",
        "context_projection",
        "coverage",
        "provenance",
        "tax_field",
    ):
        assert forbidden not in rendered


def test_decision_contract_is_factory_managed_and_closed_world():
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

    assert "Gate2FinancialEvidenceDecisionContractFactory.create" in source
    assert "must not add dispositions" in source
    assert imported_modules <= {
        "__future__",
        "copy",
        "dataclasses",
        "hashlib",
        "json",
        "re",
        "typing",
        "gate2_financial_evidence_registry",
    }
    assert "artifact_store" not in source
    assert "customer" not in source
    assert "provider_clients" not in source
