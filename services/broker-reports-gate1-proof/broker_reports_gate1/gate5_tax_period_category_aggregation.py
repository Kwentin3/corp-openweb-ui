"""Aggregate complete G5.13 operation models for one explicit tax scope."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any

from .gate5_declaration_projection import (
    GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION,
    Gate5DeclarationProjectionRuntime,
    Gate5DeclarationProjectionRuntimeFactory,
)
from .gate5_securities_disposal_tax_model import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID,
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
)
from .gate5_trusted_methodology import (
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthority,
    Gate5TrustedMethodologyAuthorityFactory,
    Gate5TrustedMethodologyError,
)


GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION = (
    "broker_reports_gate5_tax_period_category_scope_v0"
)
GATE5_TAX_PERIOD_CATEGORY_SCOPE_BINDING_SCHEMA_VERSION = (
    "broker_reports_gate5_tax_period_category_scope_binding_v0"
)
GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate5_tax_period_completeness_evidence_v0"
)
GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_SCHEMA_VERSION = (
    "broker_reports_gate5_tax_period_category_tax_model_v0"
)
GATE5_TAX_PERIOD_CATEGORY_AGGREGATION_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_tax_period_category_aggregation_result_v0"
)
GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_tax_period_category_tax_model_result_v0"
)
GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT = (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
)
GATE5_OPERATION_TAXPAYER_SCOPE_BINDING_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_taxpayer_binding_v0"
)

FACTORY_REQUIRED = (
    "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create",
    "Gate5TrustedMethodologyAuthorityFactory.create validates member methodology",
    "Gate5DeclarationProjectionRuntimeFactory.create owns declaration representation",
)
FORBIDDEN = (
    "raw Gate 4 or Supplemental Fact aggregation and direct source/store/SQL reads",
    "CASE_COMPLETE_FOR_CURRENT_INPUT_SET as tax-period completeness",
    "category classification, expense allowability or loss rules at aggregate level",
    "best-effort declaration output, LLM, Tax Case, DB or generic aggregation engine",
)

_SCOPE_KEYS = {
    "schema_version",
    "scope_ref",
    "taxpayer_scope_ref",
    "tax_period",
    "operation_category",
}
_MEMBER_KEYS = {"operation_ref", "source_scope_ref", "tax_model"}
_MODEL_KEYS = {
    "schema_version",
    "status",
    "model_id",
    "model_kind",
    "operation_scope",
    "methodology_binding",
    "operation",
    "gross_income",
    "related_expenses",
    "allowable_expenses",
    "loss_treatment",
    "proof_assumptions",
}
_METHODOLOGY_BINDING_KEYS = {
    "authority_owner",
    "methodology_id",
    "methodology_version",
    "resource_sha256",
    "projection_sha256",
    "behavior_id",
    "applicability_rule_id",
}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TAX_PERIOD = re.compile(r"^[0-9]{4}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_AMOUNT = re.compile(r"^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TAGGED_SOURCE_KINDS = {
    "authenticated_identity_provider",
    "authenticated_user_case_fact",
    "current_fact_v2",
    "external_authoritative_evidence",
    "methodology_derived_result",
    "proof_assumption",
    "user_verified_fact",
}


class Gate5TaxPeriodCategoryAggregationError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5TaxPeriodCategoryAggregationRuntimeFactory:
    @staticmethod
    def create() -> "Gate5TaxPeriodCategoryAggregationRuntime":
        return Gate5TaxPeriodCategoryAggregationRuntime(
            authority=Gate5TrustedMethodologyAuthorityFactory.create(),
            projector=Gate5DeclarationProjectionRuntimeFactory.create(),
        )


class Gate5TaxPeriodCategoryAggregationRuntime:
    def __init__(
        self,
        *,
        authority: Gate5TrustedMethodologyAuthority,
        projector: Gate5DeclarationProjectionRuntime,
    ) -> None:
        self._authority = authority
        self._projector = projector

    def validate_operation_member(self, *, tax_model: dict[str, Any]) -> dict[str, Any]:
        """Validate one producer result against the exact G5.14 member boundary."""
        return _operation_model(tax_model, authority=self._authority)

    def validate_category_model(self, *, tax_model: dict[str, Any]) -> dict[str, Any]:
        """Validate one complete category result for a downstream tax behavior."""
        return _validated_category_tax_model(tax_model, authority=self._authority)

    def validate_operation_taxpayer_scope_binding(
        self, *, binding: Any
    ) -> dict[str, Any] | None:
        """Validate the explicit subject-to-taxpayer identity seam."""

        return validate_operation_taxpayer_scope_binding(binding)

    def describe_scope(
        self,
        *,
        scope: dict[str, Any],
        members: list[dict[str, Any]],
    ) -> dict[str, Any]:
        validated_scope = _scope(scope)
        validated_members = _members(
            members,
            scope=validated_scope,
            authority=self._authority,
        )
        return _scope_binding(validated_scope, validated_members)

    def run(
        self,
        *,
        scope: dict[str, Any],
        members: list[dict[str, Any]],
        completeness_evidence: dict[str, Any] | None,
    ) -> dict[str, Any]:
        model_result = self.run_tax_model(
            scope=scope,
            members=members,
            completeness_evidence=completeness_evidence,
        )
        base = {
            **copy.deepcopy(model_result),
            "schema_version": GATE5_TAX_PERIOD_CATEGORY_AGGREGATION_RESULT_SCHEMA_VERSION,
        }
        if model_result["status"] == "incomplete_scope":
            return {
                **base,
                "declaration_semantics": None,
                "declaration_fragment": None,
            }
        category_model = model_result["category_tax_model"]
        semantics = _declaration_semantics(category_model)
        return {
            **base,
            "declaration_semantics": semantics,
            "declaration_fragment": self._projector.project(proof_input=semantics),
        }

    def run_tax_model(
        self,
        *,
        scope: dict[str, Any],
        members: list[dict[str, Any]],
        completeness_evidence: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Aggregate through G5.14 without crossing into declaration projection."""

        validated_scope = _scope(scope)
        validated_members = _members(
            members,
            scope=validated_scope,
            authority=self._authority,
        )
        binding = _scope_binding(validated_scope, validated_members)
        known_values = _known_values(validated_members)
        evidence = _completeness_evidence(
            completeness_evidence,
            scope_binding_sha256=binding["scope_binding_sha256"],
        )
        base = {
            "schema_version": GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_RESULT_SCHEMA_VERSION,
            "scope_binding": binding,
            "known_values": known_values,
        }
        if evidence is None:
            return {
                **base,
                "status": "incomplete_scope",
                "completeness": {
                    "status": "not_proven",
                    "reason": "completeness_evidence_absent",
                },
                "category_tax_model": None,
            }
        return {
            **base,
            "status": "complete",
            "completeness": copy.deepcopy(evidence),
            "category_tax_model": _category_tax_model(
                scope=validated_scope,
                scope_binding=binding,
                completeness_evidence=evidence,
                members=validated_members,
                known_values=known_values,
            ),
        }


def _scope(value: Any) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or set(value) != _SCOPE_KEYS
        or value.get("schema_version") != GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION
        or not _identifier(value.get("scope_ref"))
        or not _identifier(value.get("taxpayer_scope_ref"))
        or not isinstance(value.get("tax_period"), str)
        or _TAX_PERIOD.fullmatch(value["tax_period"]) is None
        or not _identifier(value.get("operation_category"))
    ):
        _fail("gate5_tax_period_scope_invalid")
    return copy.deepcopy(value)


def _members(
    value: Any,
    *,
    scope: dict[str, str],
    authority: Gate5TrustedMethodologyAuthority,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _fail("gate5_tax_period_members_invalid")
    result = []
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != _MEMBER_KEYS
            or not _identifier(item.get("operation_ref"))
            or not _identifier(item.get("source_scope_ref"))
        ):
            _fail("gate5_tax_period_operation_identity_ambiguous")
        model = _operation_model(item.get("tax_model"), authority=authority)
        result.append(
            {
                "operation_ref": item["operation_ref"],
                "source_scope_ref": item["source_scope_ref"],
                "operation_model_sha256": _canonical_sha256(model),
                "tax_model": model,
            }
        )
    refs = [item["operation_ref"] for item in result]
    if len(set(refs)) != len(refs):
        _fail("gate5_tax_period_duplicate_operation_ref")
    hashes = [item["operation_model_sha256"] for item in result]
    if len(set(hashes)) != len(hashes):
        _fail("gate5_tax_period_duplicate_operation_model")
    result.sort(key=lambda item: (item["operation_ref"], item["source_scope_ref"]))
    _member_consensus(result, scope=scope)
    return result


def _operation_model(
    value: Any,
    *,
    authority: Gate5TrustedMethodologyAuthority,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _MODEL_KEYS
        or value.get("schema_version")
        != GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT
        or value.get("status") != "complete"
        or value.get("model_kind") != "securities_disposal"
        or not _identifier(value.get("model_id"))
    ):
        _fail("gate5_tax_period_operation_model_incomplete")
    operation_scope = value.get("operation_scope")
    operation = value.get("operation")
    binding = value.get("methodology_binding")
    if (
        not isinstance(operation_scope, dict)
        or set(operation_scope)
        != {
            "subject_ref",
            "tax_period",
            "residency",
            "exemption_applicability",
            "aggregation_kind",
        }
        or not _identifier(operation_scope.get("subject_ref"))
        or operation_scope.get("aggregation_kind") != "single_operation_only"
        or not isinstance(operation, dict)
        or set(operation) != {"kind", "category"}
        or not isinstance(operation.get("category"), dict)
        or set(operation["category"]) != {"value", "decision_provenance"}
        or not _identifier(operation["category"].get("value"))
        or not isinstance(binding, dict)
        or set(binding) != _METHODOLOGY_BINDING_KEYS
    ):
        _fail("gate5_tax_period_operation_model_invalid")
    period = _tagged(operation_scope.get("tax_period"), "minimal_tax_context")
    if not isinstance(period["value"], str) or not _TAX_PERIOD.fullmatch(
        period["value"]
    ):
        _fail("gate5_tax_period_operation_model_invalid")
    residency = _tagged(operation_scope.get("residency"), "minimal_tax_context")
    if residency["provenance"].get(
        "source_kind"
    ) != "methodology_derived_result" or not residency["provenance"].get(
        "source_ref", ""
    ).startswith("residency-classification:"):
        _fail("gate5_tax_period_residency_classification_required")
    _tagged(operation_scope.get("exemption_applicability"), "minimal_tax_context")
    _tagged(operation.get("kind"), "resolved_operation_property")
    _tagged(value.get("loss_treatment"), "minimal_tax_context")
    if not isinstance(value.get("proof_assumptions"), list):
        _fail("gate5_tax_period_operation_model_invalid")
    _methodology_binding(binding, value=value, authority=authority)
    for path in ("gross_income", "related_expenses", "allowable_expenses"):
        section = value.get(path)
        if not isinstance(section, dict):
            _fail("gate5_tax_period_operation_model_invalid", path)
    gross = value["gross_income"]
    related = value["related_expenses"]
    allowable = value["allowable_expenses"]
    if (
        set(gross) != {"value", "sources", "derivation"}
        or not isinstance(gross["sources"], list)
        or set(related) != {"components", "total"}
        or not isinstance(related["components"], list)
        or set(allowable) != {"decisions", "components", "total"}
        or not isinstance(allowable["decisions"], list)
        or not isinstance(allowable["components"], list)
    ):
        _fail("gate5_tax_period_operation_model_invalid")
    money = [_money(gross["value"], "gross_income")]
    money.append(_money(related["total"], "related_expenses"))
    money.append(_money(allowable["total"], "allowable_expenses"))
    for section_name, components in (
        ("related_expenses", related["components"]),
        ("allowable_expenses", allowable["components"]),
    ):
        for component in components:
            if (
                not isinstance(component, dict)
                or not _identifier(component.get("component_id"))
                or not isinstance(component.get("sources"), list)
            ):
                _fail("gate5_tax_period_operation_model_invalid", section_name)
            money.append(_money(component.get("value"), section_name))
    if len({item["currency"] for item in money}) != 1:
        _fail("gate5_tax_period_currency_mismatch")
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise Gate5TaxPeriodCategoryAggregationError(
            "gate5_tax_period_operation_model_invalid"
        ) from exc


def _methodology_binding(
    binding: dict[str, Any],
    *,
    value: dict[str, Any],
    authority: Gate5TrustedMethodologyAuthority,
) -> None:
    if (
        binding.get("behavior_id")
        != GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID
        or not _identifier(binding.get("applicability_rule_id"))
        or not all(
            isinstance(binding.get(name), str)
            and _SHA256.fullmatch(binding[name]) is not None
            for name in ("resource_sha256", "projection_sha256")
        )
    ):
        _fail("gate5_tax_period_methodology_unsupported")
    methodology_ref = {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": binding.get("methodology_id"),
        "methodology_version": binding.get("methodology_version"),
    }
    try:
        resolved = authority.resolve(methodology_ref)
    except Gate5TrustedMethodologyError as exc:
        raise Gate5TaxPeriodCategoryAggregationError(
            "gate5_tax_period_methodology_unknown"
        ) from exc
    expected = resolved["authority_binding"]
    behavior = resolved["methodology"].get("behavior")
    if (
        any(binding.get(name) != expected.get(name) for name in expected)
        or not isinstance(behavior, dict)
        or behavior.get("behavior_id") != binding["behavior_id"]
        or behavior.get("model_id") != value["model_id"]
        or not isinstance(behavior.get("applicability_rule"), dict)
        or behavior["applicability_rule"].get("rule_id")
        != binding["applicability_rule_id"]
    ):
        _fail("gate5_tax_period_methodology_binding_mismatch")


def _member_consensus(members: list[dict[str, Any]], *, scope: dict[str, str]) -> None:
    models = [item["tax_model"] for item in members]
    periods = {item["operation_scope"]["tax_period"]["value"] for item in models}
    if periods != {scope["tax_period"]}:
        _fail("gate5_tax_period_member_period_mismatch")
    categories = {item["operation"]["category"]["value"] for item in models}
    if categories != {scope["operation_category"]}:
        _fail("gate5_tax_period_member_category_mismatch")
    currencies = {item["gross_income"]["value"]["currency"] for item in models}
    if len(currencies) != 1:
        _fail("gate5_tax_period_currency_mismatch")
    loss_states = {item["loss_treatment"]["value"] for item in models}
    if len(loss_states) != 1:
        _fail("gate5_tax_period_loss_treatment_incompatible")
    methodology = [item["methodology_binding"] for item in models]
    if any(item != methodology[0] for item in methodology[1:]):
        _fail("gate5_tax_period_methodology_mismatch")


def _scope_binding(
    scope: dict[str, str], members: list[dict[str, Any]]
) -> dict[str, Any]:
    result = {
        "schema_version": GATE5_TAX_PERIOD_CATEGORY_SCOPE_BINDING_SCHEMA_VERSION,
        "scope": copy.deepcopy(scope),
        "members": [
            {
                "operation_ref": item["operation_ref"],
                "source_scope_ref": item["source_scope_ref"],
                "operation_model_sha256": item["operation_model_sha256"],
            }
            for item in members
        ],
    }
    return {**result, "scope_binding_sha256": _canonical_sha256(result)}


def _completeness_evidence(
    value: Any, *, scope_binding_sha256: str
) -> dict[str, Any] | None:
    if value is None:
        return None
    provenance = value.get("provenance") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "status",
            "coverage_kind",
            "scope_binding_sha256",
            "provenance",
        }
        or value.get("schema_version")
        != GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION
        or value.get("status") != "asserted_complete"
        or value.get("coverage_kind")
        != "all_operations_in_taxpayer_category_period_scope"
        or not isinstance(provenance, dict)
        or set(provenance) != {"source_kind", "source_ref", "input_channel"}
        or provenance.get("source_kind")
        not in {"user_verified_fact", "current_fact_v2"}
        or not _identifier(provenance.get("source_ref"))
        or provenance.get("input_channel") != "tax_period_scope_completeness"
    ):
        _fail("gate5_tax_period_completeness_evidence_invalid")
    if value.get("scope_binding_sha256") != scope_binding_sha256:
        _fail("gate5_tax_period_completeness_binding_mismatch")
    return copy.deepcopy(value)


def _known_values(members: list[dict[str, Any]]) -> dict[str, Any]:
    currency = members[0]["tax_model"]["gross_income"]["value"]["currency"]
    return {
        "gross_income": _aggregate_money(
            members,
            section="gross_income",
            currency=currency,
        ),
        "related_expenses": _aggregate_money(
            members,
            section="related_expenses",
            currency=currency,
        ),
        "allowable_expenses": _aggregate_money(
            members,
            section="allowable_expenses",
            currency=currency,
        ),
        "loss_treatment": {
            "value": members[0]["tax_model"]["loss_treatment"]["value"],
            "member_provenance": [
                {
                    "operation_ref": item["operation_ref"],
                    "operation_model_sha256": item["operation_model_sha256"],
                    "value": copy.deepcopy(item["tax_model"]["loss_treatment"]),
                }
                for item in members
            ],
        },
    }


def _aggregate_money(
    members: list[dict[str, Any]], *, section: str, currency: str
) -> dict[str, Any]:
    contributions = []
    total = Decimal("0.00")
    for item in members:
        model_section = item["tax_model"][section]
        value = (
            model_section["value"]
            if section == "gross_income"
            else model_section["total"]
        )
        total += Decimal(value["amount"])
        evidence = (
            copy.deepcopy(model_section["sources"])
            if section == "gross_income"
            else [
                {
                    "component_id": component["component_id"],
                    "value": copy.deepcopy(component["value"]),
                    "sources": copy.deepcopy(component["sources"]),
                }
                for component in model_section["components"]
            ]
        )
        contributions.append(
            {
                "operation_ref": item["operation_ref"],
                "source_scope_ref": item["source_scope_ref"],
                "operation_model_sha256": item["operation_model_sha256"],
                "operation_value_path": section,
                "value": copy.deepcopy(value),
                "source_evidence": evidence,
            }
        )
    return {
        "value": {"kind": "money", "amount": f"{total:.2f}", "currency": currency},
        "derivation": {
            "kind": "sum_of_complete_operation_tax_models",
            "contributions": contributions,
        },
    }


def _category_tax_model(
    *,
    scope: dict[str, str],
    scope_binding: dict[str, Any],
    completeness_evidence: dict[str, Any],
    members: list[dict[str, Any]],
    known_values: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_SCHEMA_VERSION,
        "status": "complete",
        "model_kind": "securities_disposal_category",
        "calculation_scope": {
            **copy.deepcopy(scope),
            "scope_binding_sha256": scope_binding["scope_binding_sha256"],
            "completeness": copy.deepcopy(completeness_evidence),
        },
        "methodology_binding": copy.deepcopy(
            members[0]["tax_model"]["methodology_binding"]
        ),
        "operation_category": {
            "value": scope["operation_category"],
            "derivation": {
                "kind": "stable_member_classification_consensus",
                "member_operation_refs": [item["operation_ref"] for item in members],
            },
        },
        "member_operations": copy.deepcopy(scope_binding["members"]),
        "category_gross_income": copy.deepcopy(known_values["gross_income"]),
        "related_expenses": copy.deepcopy(known_values["related_expenses"]),
        "allowable_expenses": copy.deepcopy(known_values["allowable_expenses"]),
        "loss_treatment": copy.deepcopy(known_values["loss_treatment"]),
    }


def _validated_category_tax_model(
    value: Any,
    *,
    authority: Gate5TrustedMethodologyAuthority,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "status",
            "model_kind",
            "calculation_scope",
            "methodology_binding",
            "operation_category",
            "member_operations",
            "category_gross_income",
            "related_expenses",
            "allowable_expenses",
            "loss_treatment",
        }
        or value.get("schema_version")
        != GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_SCHEMA_VERSION
        or value.get("status") != "complete"
        or value.get("model_kind") != "securities_disposal_category"
    ):
        _fail("gate5_tax_period_category_model_invalid")

    calculation_scope = value.get("calculation_scope")
    if (
        not isinstance(calculation_scope, dict)
        or set(calculation_scope)
        != {*_SCOPE_KEYS, "scope_binding_sha256", "completeness"}
        or not isinstance(calculation_scope.get("scope_binding_sha256"), str)
        or _SHA256.fullmatch(calculation_scope["scope_binding_sha256"]) is None
    ):
        _fail("gate5_tax_period_category_model_invalid", "calculation_scope")
    scope = _scope({key: calculation_scope[key] for key in _SCOPE_KEYS})
    completeness = _completeness_evidence(
        calculation_scope.get("completeness"),
        scope_binding_sha256=calculation_scope["scope_binding_sha256"],
    )
    if completeness is None:
        _fail("gate5_tax_period_category_model_incomplete")

    members = _validated_category_member_refs(value.get("member_operations"))
    scope_binding = {
        "schema_version": GATE5_TAX_PERIOD_CATEGORY_SCOPE_BINDING_SCHEMA_VERSION,
        "scope": scope,
        "members": members,
    }
    if _canonical_sha256(scope_binding) != calculation_scope["scope_binding_sha256"]:
        _fail("gate5_tax_period_category_model_scope_binding_mismatch")

    category = value.get("operation_category")
    expected_refs = [item["operation_ref"] for item in members]
    if (
        not isinstance(category, dict)
        or set(category) != {"value", "derivation"}
        or category.get("value") != scope["operation_category"]
        or not isinstance(category.get("derivation"), dict)
        or category["derivation"]
        != {
            "kind": "stable_member_classification_consensus",
            "member_operation_refs": expected_refs,
        }
    ):
        _fail("gate5_tax_period_category_model_invalid", "operation_category")

    gross = _validated_category_aggregate(
        value.get("category_gross_income"),
        members=members,
        operation_value_path="gross_income",
        field="category_gross_income",
    )
    related = _validated_category_aggregate(
        value.get("related_expenses"),
        members=members,
        operation_value_path="related_expenses",
        field="related_expenses",
    )
    allowable = _validated_category_aggregate(
        value.get("allowable_expenses"),
        members=members,
        operation_value_path="allowable_expenses",
        field="allowable_expenses",
    )
    if (
        len(
            {
                gross["value"]["currency"],
                related["value"]["currency"],
                allowable["value"]["currency"],
            }
        )
        != 1
    ):
        _fail("gate5_tax_period_currency_mismatch")

    _validated_category_loss_treatment(
        value.get("loss_treatment"),
        members=members,
    )
    _category_methodology_binding(
        value.get("methodology_binding"),
        operation_category=scope["operation_category"],
        authority=authority,
    )
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise Gate5TaxPeriodCategoryAggregationError(
            "gate5_tax_period_category_model_invalid"
        ) from exc


def _validated_category_member_refs(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        _fail("gate5_tax_period_category_model_invalid", "member_operations")
    result: list[dict[str, str]] = []
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item)
            != {"operation_ref", "source_scope_ref", "operation_model_sha256"}
            or not _identifier(item.get("operation_ref"))
            or not _identifier(item.get("source_scope_ref"))
            or not isinstance(item.get("operation_model_sha256"), str)
            or _SHA256.fullmatch(item["operation_model_sha256"]) is None
        ):
            _fail("gate5_tax_period_category_model_invalid", "member_operations")
        result.append(copy.deepcopy(item))
    identities = [(item["operation_ref"], item["source_scope_ref"]) for item in result]
    hashes = [item["operation_model_sha256"] for item in result]
    if (
        len(set(identities)) != len(identities)
        or len(set(hashes)) != len(hashes)
        or identities != sorted(identities)
    ):
        _fail("gate5_tax_period_category_model_invalid", "member_operations")
    return result


def _validated_category_aggregate(
    value: Any,
    *,
    members: list[dict[str, str]],
    operation_value_path: str,
    field: str,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != {"value", "derivation"}
        or not isinstance(value.get("derivation"), dict)
        or set(value["derivation"]) != {"kind", "contributions"}
        or value["derivation"].get("kind") != "sum_of_complete_operation_tax_models"
        or not isinstance(value["derivation"].get("contributions"), list)
        or len(value["derivation"]["contributions"]) != len(members)
    ):
        _fail("gate5_tax_period_category_model_invalid", field)
    aggregate = _money(value.get("value"), field)
    total = Decimal("0.00")
    for member, contribution in zip(
        members,
        value["derivation"]["contributions"],
        strict=True,
    ):
        if (
            not isinstance(contribution, dict)
            or set(contribution)
            != {
                "operation_ref",
                "source_scope_ref",
                "operation_model_sha256",
                "operation_value_path",
                "value",
                "source_evidence",
            }
            or any(
                contribution.get(name) != member[name]
                for name in (
                    "operation_ref",
                    "source_scope_ref",
                    "operation_model_sha256",
                )
            )
            or contribution.get("operation_value_path") != operation_value_path
            or not isinstance(contribution.get("source_evidence"), list)
            or not contribution["source_evidence"]
            or not _contains_source_kind(contribution["source_evidence"])
        ):
            _fail("gate5_tax_period_category_model_invalid", field)
        money = _money(contribution.get("value"), field)
        if money["currency"] != aggregate["currency"]:
            _fail("gate5_tax_period_currency_mismatch")
        total += Decimal(money["amount"])
    if f"{total:.2f}" != aggregate["amount"]:
        _fail("gate5_tax_period_category_model_total_mismatch", field)
    return value


def _validated_category_loss_treatment(
    value: Any,
    *,
    members: list[dict[str, str]],
) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"value", "member_provenance"}
        or not isinstance(value.get("value"), str)
        or not isinstance(value.get("member_provenance"), list)
        or len(value["member_provenance"]) != len(members)
    ):
        _fail("gate5_tax_period_category_model_invalid", "loss_treatment")
    for member, provenance in zip(
        members,
        value["member_provenance"],
        strict=True,
    ):
        if (
            not isinstance(provenance, dict)
            or set(provenance) != {"operation_ref", "operation_model_sha256", "value"}
            or provenance.get("operation_ref") != member["operation_ref"]
            or provenance.get("operation_model_sha256")
            != member["operation_model_sha256"]
            or _tagged(provenance.get("value"), "minimal_tax_context")["value"]
            != value["value"]
        ):
            _fail("gate5_tax_period_category_model_invalid", "loss_treatment")


def _category_methodology_binding(
    value: Any,
    *,
    operation_category: str,
    authority: Gate5TrustedMethodologyAuthority,
) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != _METHODOLOGY_BINDING_KEYS
        or value.get("behavior_id")
        != GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID
        or not _identifier(value.get("applicability_rule_id"))
    ):
        _fail("gate5_tax_period_methodology_unsupported")
    try:
        resolved = authority.resolve(
            {
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": value.get("methodology_id"),
                "methodology_version": value.get("methodology_version"),
            }
        )
    except Gate5TrustedMethodologyError as exc:
        raise Gate5TaxPeriodCategoryAggregationError(
            "gate5_tax_period_methodology_unknown"
        ) from exc
    authority_binding = resolved["authority_binding"]
    behavior = resolved["methodology"].get("behavior")
    if (
        any(
            value.get(name) != authority_binding.get(name) for name in authority_binding
        )
        or not isinstance(behavior, dict)
        or behavior.get("behavior_id") != value["behavior_id"]
        or not isinstance(behavior.get("applicability_rule"), dict)
        or behavior["applicability_rule"].get("rule_id")
        != value["applicability_rule_id"]
        or behavior["applicability_rule"].get("result_category") != operation_category
    ):
        _fail("gate5_tax_period_methodology_binding_mismatch")


def _contains_source_kind(value: Any) -> bool:
    if isinstance(value, dict):
        if isinstance(value.get("source_kind"), str):
            return True
        return any(_contains_source_kind(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_source_kind(item) for item in value)
    return False


def _declaration_semantics(model: dict[str, Any]) -> dict[str, Any]:
    def money(section: str) -> dict[str, str]:
        value = model[section]["value"]
        return {"amount": value["amount"], "currency": value["currency"]}

    return {
        "schema_version": GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION,
        "operation_category": model["operation_category"]["value"],
        "operation_category_gross_income": money("category_gross_income"),
        "related_expenses": money("related_expenses"),
        "allowable_expenses": money("allowable_expenses"),
        "loss_treatment": model["loss_treatment"]["value"],
    }


def validate_operation_taxpayer_scope_binding(
    value: Any,
) -> dict[str, Any] | None:
    """Validate a provenance-bound operation subject to taxpayer-scope join."""

    provenance = value.get("provenance") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "operation_subject_ref",
            "taxpayer_scope_ref",
            "provenance",
        }
        or value.get("schema_version")
        != GATE5_OPERATION_TAXPAYER_SCOPE_BINDING_SCHEMA_VERSION
        or not _identifier(value.get("operation_subject_ref"))
        or not _identifier(value.get("taxpayer_scope_ref"))
        or not isinstance(provenance, dict)
        or set(provenance) != {"source_kind", "source_ref", "input_channel"}
        or provenance.get("source_kind")
        not in {"user_verified_fact", "authenticated_identity_provider"}
        or not _identifier(provenance.get("source_ref"))
        or provenance.get("input_channel") != "operation_taxpayer_binding"
    ):
        return None
    return copy.deepcopy(value)


def _tagged(value: Any, channel: str) -> dict[str, Any]:
    provenance = value.get("provenance") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or set(value) != {"value", "provenance"}
        or not isinstance(provenance, dict)
        or set(provenance) != {"source_kind", "source_ref", "input_channel"}
        or not _identifier(provenance.get("source_ref"))
        or provenance.get("input_channel") != channel
        or provenance.get("source_kind") not in _TAGGED_SOURCE_KINDS
    ):
        _fail("gate5_tax_period_operation_model_invalid")
    return value


def _money(value: Any, field: str) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or set(value) != {"kind", "amount", "currency"}
        or value.get("kind") != "money"
        or not isinstance(value.get("amount"), str)
        or _AMOUNT.fullmatch(value["amount"]) is None
        or not isinstance(value.get("currency"), str)
        or _CURRENCY.fullmatch(value["currency"]) is None
    ):
        _fail("gate5_tax_period_money_invalid", field)
    try:
        Decimal(value["amount"])
    except InvalidOperation as exc:
        raise Gate5TaxPeriodCategoryAggregationError(
            "gate5_tax_period_money_invalid", field
        ) from exc
    return value


def _canonical_sha256(value: Any) -> str:
    try:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Gate5TaxPeriodCategoryAggregationError(
            "gate5_tax_period_contract_not_canonical"
        ) from exc
    return hashlib.sha256(raw).hexdigest()


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _fail(code: str, field: str = "") -> None:
    raise Gate5TaxPeriodCategoryAggregationError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_TAX_PERIOD_CATEGORY_AGGREGATION_RESULT_SCHEMA_VERSION",
    "GATE5_OPERATION_TAXPAYER_SCOPE_BINDING_SCHEMA_VERSION",
    "GATE5_TAX_PERIOD_CATEGORY_OPERATION_MEMBER_CONTRACT",
    "GATE5_TAX_PERIOD_CATEGORY_SCOPE_BINDING_SCHEMA_VERSION",
    "GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION",
    "GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_SCHEMA_VERSION",
    "GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_RESULT_SCHEMA_VERSION",
    "GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION",
    "Gate5TaxPeriodCategoryAggregationError",
    "Gate5TaxPeriodCategoryAggregationRuntime",
    "Gate5TaxPeriodCategoryAggregationRuntimeFactory",
    "validate_operation_taxpayer_scope_binding",
]
