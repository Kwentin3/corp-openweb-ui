"""Build one inactive declaration-driven securities-disposal Tax Model slice."""

from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate5_combined_requirement_check import GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION
from .gate5_declaration_projection import (
    GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION,
    Gate5DeclarationProjectionRuntime,
    Gate5DeclarationProjectionRuntimeFactory,
)
from .gate5_deterministic_source_fact_consumption import (
    Gate5DeterministicSourceFactConsumptionRuntime,
    Gate5DeterministicSourceFactConsumptionRuntimeFactory,
    gate5_source_fact_tax_model_inputs,
)
from .gate5_supplemental_fact_discovery import (
    Gate5SupplementalFactDiscoveryRuntime,
    Gate5SupplementalFactDiscoveryRuntimeFactory,
)
from .gate5_trusted_methodology import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthority,
    Gate5TrustedMethodologyAuthorityFactory,
)


GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION = (
    "broker_reports_gate5_securities_disposal_resolved_inputs_v0"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_SCHEMA_VERSION = (
    "broker_reports_gate5_securities_disposal_tax_model_v0"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_securities_disposal_tax_model_result_v0"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_BEHAVIOR_ID = "securities_disposal_tax_model_v0"
GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID = (
    "securities_disposal_operation_tax_model_v0"
)
GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION = (
    "broker_reports_gate5_securities_disposal_operation_tax_model_v0"
)
GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_securities_disposal_operation_tax_model_result_v0"
)
GATE5_SECURITIES_DISPOSAL_CURRENT_SOURCE_FACT_OPERATION_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_current_source_fact_operation_tax_model_result_v0"
)

FACTORY_REQUIRED = (
    "Gate5SecuritiesDisposalTaxModelRuntimeFactory.create",
    "Gate5TrustedMethodologyAuthorityFactory.create owns methodology resolution",
    "Gate5SupplementalFactDiscoveryRuntimeFactory.create owns case input discovery",
    "Gate5DeclarationProjectionRuntimeFactory.create owns declaration representation",
    "Gate5DeterministicSourceFactConsumptionRuntimeFactory.create owns the "
    "normalized-source-fact result consumed by run_from_current_source_facts",
    "Gate5SecuritiesDisposalTaxModelRuntimeFactory."
    "create_current_source_fact_operation owns inactive Fact v2 consumer injection",
)
FORBIDDEN = (
    "direct Gate 4, Supplemental Fact, ArtifactStore, SQL, source or provider reads",
    "caller-supplied methodology contents, hidden classification defaults or LLM",
    "declaration paths, attributes or codes inside the Tax Model behavior",
    "Tax Engine, Tax Case, Tax Model persistence, annual aggregation, rate or tax",
)

_ROOT_KEYS = {
    "schema_version",
    "subject_ref",
    "operation_properties",
    "tax_context",
    "scope",
    "expense_evidence",
}
_SECTIONS = {
    "operation_properties": (
        {"operation_kind", "organized_market_status", "iis_status"},
        "resolved_operation_property",
    ),
    "tax_context": (
        {"tax_period", "residency", "exemption_applicability", "loss_treatment"},
        "minimal_tax_context",
    ),
    "scope": ({"scope_completeness"}, "scope_binding"),
}
_EXPENSE_FLAGS = {"actually_incurred", "documented", "related_to_operation"}
_SOURCE_KINDS = {
    "authenticated_user_case_fact",
    "USER_ATTESTED_CASE_FACT",
    "current_fact_v2",
    "external_authoritative_evidence",
    "methodology_derived_result",
    "proof_assumption",
    "user_verified_fact",
}
_CLASSIFICATION_INPUTS = {
    "operation_kind",
    "organized_market_status",
    "iis_status",
    "tax_period",
    "residency",
    "exemption_applicability",
    "loss_treatment",
}
_LEGACY_CATEGORY_INPUTS = {
    *_CLASSIFICATION_INPUTS,
    "scope_completeness",
}
_BEHAVIOR_INPUTS = {
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_BEHAVIOR_ID: _LEGACY_CATEGORY_INPUTS,
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID: (_CLASSIFICATION_INPUTS),
}
_MONEY_INPUTS = {"gross_income", "acquisition_cost", "transaction_expense"}
_MONEY = re.compile(r"^(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,2})?$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_INPUT_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Gate5SecuritiesDisposalTaxModelError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5SecuritiesDisposalTaxModelRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy

    def create(self) -> "Gate5SecuritiesDisposalTaxModelRuntime":
        return Gate5SecuritiesDisposalTaxModelRuntime(
            authority=Gate5TrustedMethodologyAuthorityFactory.create(),
            discovery=Gate5SupplementalFactDiscoveryRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
                retention_policy=self._retention_policy,
            ).create(),
            source_fact_consumption=(
                Gate5DeterministicSourceFactConsumptionRuntimeFactory(
                    store=self._store,
                    read_enabled=self._read_enabled,
                ).create()
            ),
            projector=Gate5DeclarationProjectionRuntimeFactory.create(),
        )

    def create_current_source_fact_operation(
        self,
        *,
        source_fact_consumption: Gate5DeterministicSourceFactConsumptionRuntime,
    ) -> "Gate5SecuritiesDisposalTaxModelRuntime":
        """Compose the existing owner with one factory-built Fact v2 consumer."""

        return Gate5SecuritiesDisposalTaxModelRuntime(
            authority=Gate5TrustedMethodologyAuthorityFactory.create(),
            discovery=None,
            source_fact_consumption=source_fact_consumption,
            projector=None,
        )


class Gate5SecuritiesDisposalTaxModelRuntime:
    def __init__(
        self,
        *,
        authority: Gate5TrustedMethodologyAuthority,
        discovery: Gate5SupplementalFactDiscoveryRuntime | None,
        source_fact_consumption: Gate5DeterministicSourceFactConsumptionRuntime,
        projector: Gate5DeclarationProjectionRuntime | None,
    ) -> None:
        self._authority = authority
        self._discovery = discovery
        self._source_fact_consumption = source_fact_consumption
        self._projector = projector

    def run(
        self,
        *,
        methodology_ref: dict[str, Any],
        resolved_inputs: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        inputs, resolved, behavior, applicability, money_inputs = self._prepare(
            methodology_ref=methodology_ref,
            resolved_inputs=resolved_inputs,
            context=context,
            expected_behavior_id=GATE5_SECURITIES_DISPOSAL_TAX_MODEL_BEHAVIOR_ID,
        )
        tax_model = _tax_model(
            authority_binding=resolved["authority_binding"],
            behavior=behavior,
            inputs=inputs,
            applicability=applicability,
            money_inputs=money_inputs,
        )
        semantics = _declaration_semantics(tax_model)
        return {
            "schema_version": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_RESULT_SCHEMA_VERSION,
            "status": "projected",
            "tax_model": tax_model,
            "declaration_semantics": semantics,
            "declaration_fragment": self._require_projector().project(
                proof_input=semantics
            ),
        }

    def run_operation(
        self,
        *,
        methodology_ref: dict[str, Any],
        resolved_inputs: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        inputs, resolved, behavior, applicability, money_inputs = self._prepare(
            methodology_ref=methodology_ref,
            resolved_inputs=resolved_inputs,
            context=context,
            expected_behavior_id=(
                GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID
            ),
        )
        return {
            "schema_version": (
                GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_RESULT_SCHEMA_VERSION
            ),
            "status": "modeled",
            "tax_model": _operation_tax_model(
                authority_binding=resolved["authority_binding"],
                behavior=behavior,
                inputs=inputs,
                applicability=applicability,
                money_inputs=money_inputs,
            ),
        }

    def run_from_current_source_facts(
        self,
        *,
        methodology_ref: dict[str, Any],
        source_fact_methodology_ref: dict[str, Any],
        resolved_inputs: dict[str, Any],
        disposal_fact_id: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        """Build the existing category model from a validated source-fact result."""

        inputs, resolved, behavior, applicability, money_inputs, _ = (
            self._prepare_from_current_source_facts(
                methodology_ref=methodology_ref,
                source_fact_methodology_ref=source_fact_methodology_ref,
                resolved_inputs=resolved_inputs,
                disposal_fact_id=disposal_fact_id,
                context=context,
                expected_behavior_id=GATE5_SECURITIES_DISPOSAL_TAX_MODEL_BEHAVIOR_ID,
            )
        )
        tax_model = _tax_model(
            authority_binding=resolved["authority_binding"],
            behavior=behavior,
            inputs=inputs,
            applicability=applicability,
            money_inputs=money_inputs,
        )
        semantics = _declaration_semantics(tax_model)
        return {
            "schema_version": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_RESULT_SCHEMA_VERSION,
            "status": "projected",
            "tax_model": tax_model,
            "declaration_semantics": semantics,
            "declaration_fragment": self._require_projector().project(
                proof_input=semantics
            ),
        }

    def run_operation_from_current_source_facts(
        self,
        *,
        methodology_ref: dict[str, Any],
        source_fact_methodology_ref: dict[str, Any],
        resolved_inputs: dict[str, Any],
        disposal_fact_id: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        """Build one operation model from the factory-owned current Fact v2 port."""

        inputs, resolved, behavior, applicability, money_inputs, consumed = (
            self._prepare_from_current_source_facts(
                methodology_ref=methodology_ref,
                source_fact_methodology_ref=source_fact_methodology_ref,
                resolved_inputs=resolved_inputs,
                disposal_fact_id=disposal_fact_id,
                context=context,
                expected_behavior_id=(
                    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID
                ),
            )
        )
        return {
            "schema_version": (
                GATE5_SECURITIES_DISPOSAL_CURRENT_SOURCE_FACT_OPERATION_RESULT_SCHEMA_VERSION
            ),
            "status": "modeled",
            "source_fact_consumption": consumed,
            "tax_model": _operation_tax_model(
                authority_binding=resolved["authority_binding"],
                behavior=behavior,
                inputs=inputs,
                applicability=applicability,
                money_inputs=money_inputs,
            ),
        }

    def _prepare_from_current_source_facts(
        self,
        *,
        methodology_ref: dict[str, Any],
        source_fact_methodology_ref: dict[str, Any],
        resolved_inputs: dict[str, Any],
        disposal_fact_id: str,
        context: ArtifactAccessContext,
        expected_behavior_id: str,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
        dict[str, Any],
    ]:
        inputs, resolved, _, behavior, applicability = self._prepare_contract(
            methodology_ref=methodology_ref,
            resolved_inputs=resolved_inputs,
            expected_behavior_id=expected_behavior_id,
        )
        consumed = self._source_fact_consumption.run(
            methodology_ref=source_fact_methodology_ref,
            context=context,
        )
        money_inputs = gate5_source_fact_tax_model_inputs(
            consumed,
            disposal_fact_id=disposal_fact_id,
            context=context,
        )
        return inputs, resolved, behavior, applicability, money_inputs, consumed

    def _prepare(
        self,
        *,
        methodology_ref: dict[str, Any],
        resolved_inputs: dict[str, Any],
        context: ArtifactAccessContext,
        expected_behavior_id: str,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
    ]:
        inputs, resolved, methodology, behavior, applicability = (
            self._prepare_contract(
            methodology_ref=methodology_ref,
            resolved_inputs=resolved_inputs,
            expected_behavior_id=expected_behavior_id,
            )
        )
        checked = self._require_discovery().check(
            methodology={
                "schema_version": GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION,
                "requirements": copy.deepcopy(methodology["requirements"]),
            },
            context=context,
        )
        if checked["summary"]["missing"]:
            _fail("gate5_tax_model_inputs_not_satisfied")
        requirements = {
            item["requirement_id"]: item for item in checked["requirements"]
        }
        money_inputs = _money_inputs(behavior["input_bindings"], requirements)
        return inputs, resolved, behavior, applicability, money_inputs

    def _require_discovery(self) -> Gate5SupplementalFactDiscoveryRuntime:
        if self._discovery is None:
            _fail("gate5_tax_model_discovery_not_composed")
        return self._discovery

    def _require_projector(self) -> Gate5DeclarationProjectionRuntime:
        if self._projector is None:
            _fail("gate5_tax_model_projector_not_composed")
        return self._projector

    def _prepare_contract(
        self,
        *,
        methodology_ref: dict[str, Any],
        resolved_inputs: dict[str, Any],
        expected_behavior_id: str,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        dict[str, Any],
        dict[str, dict[str, Any]],
    ]:
        inputs = _resolved_inputs(resolved_inputs)
        resolved = self._authority.resolve(methodology_ref)
        methodology = _methodology(
            resolved["methodology"],
            authority_binding=resolved["authority_binding"],
        )
        behavior = methodology["behavior"]
        if behavior["behavior_id"] != expected_behavior_id:
            _fail("gate5_tax_model_behavior_unsupported")
        if any(
            item.get("subject_ref") != inputs["subject_ref"]
            for item in methodology["requirements"]
        ):
            _fail("gate5_tax_model_subject_binding_mismatch")
        applicability = {
            **inputs["operation_properties"],
            **inputs["tax_context"],
            **inputs["scope"],
        }
        _require_applicability(
            behavior["applicability_rule"]["required_values"], applicability
        )
        return inputs, resolved, methodology, behavior, applicability


def _resolved_inputs(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _ROOT_KEYS
        or value.get("schema_version")
        != GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION
        or not _identifier(value.get("subject_ref"))
    ):
        _fail("gate5_tax_model_resolved_inputs_invalid")
    result = {
        "schema_version": value["schema_version"],
        "subject_ref": value["subject_ref"],
    }
    for name, (allowed, channel) in _SECTIONS.items():
        result[name] = _tagged_section(value.get(name), allowed, channel)
    residency = result["tax_context"].get("residency")
    if (
        not isinstance(residency, dict)
        or residency["provenance"].get("source_kind")
        != "methodology_derived_result"
        or not residency["provenance"].get("source_ref", "").startswith(
            "residency-classification:"
        )
    ):
        _fail("gate5_tax_model_residency_classification_required", "residency")
    raw_evidence = value.get("expense_evidence")
    if not isinstance(raw_evidence, dict):
        _fail("gate5_tax_model_expense_evidence_invalid")
    evidence = {}
    for component, flags in raw_evidence.items():
        if not _input_name(component):
            _fail("gate5_tax_model_expense_evidence_invalid")
        evidence[component] = _tagged_section(
            flags, _EXPENSE_FLAGS, "expense_eligibility_evidence"
        )
        if any(
            not isinstance(item["value"], bool) for item in evidence[component].values()
        ):
            _fail("gate5_tax_model_expense_evidence_invalid", component)
    result["expense_evidence"] = evidence
    return result


def _tagged_section(value: Any, allowed: set[str], channel: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not set(value).issubset(allowed):
        _fail("gate5_tax_model_resolved_inputs_invalid")
    return {key: _tagged(item, channel) for key, item in value.items()}


def _tagged(value: Any, channel: str) -> dict[str, Any]:
    provenance = value.get("provenance") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or set(value) != {"value", "provenance"}
        or not isinstance(provenance, dict)
        or set(provenance) != {"source_kind", "source_ref", "input_channel"}
        or provenance.get("source_kind") not in _SOURCE_KINDS
        or not _identifier(provenance.get("source_ref"))
        or provenance.get("input_channel") != channel
        or not isinstance(value.get("value"), (str, bool))
    ):
        _fail("gate5_tax_model_resolved_inputs_invalid")
    return copy.deepcopy(value)


def _methodology(value: Any, *, authority_binding: dict[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "methodology_id",
            "methodology_version",
            "behavior",
            "requirements",
            "legal_evidence",
        }
        or value.get("schema_version")
        not in {
            GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_SCHEMA_VERSION,
            GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_SCHEMA_VERSION,
        }
        or value.get("methodology_id") != authority_binding.get("methodology_id")
        or value.get("methodology_version")
        != authority_binding.get("methodology_version")
        or not isinstance(value.get("requirements"), list)
        or not value["requirements"]
    ):
        _fail("gate5_tax_model_methodology_invalid")
    behavior = value.get("behavior")
    if not isinstance(behavior, dict) or set(behavior) != {
        "behavior_id",
        "model_id",
        "input_bindings",
        "applicability_rule",
        "expense_rules",
    }:
        _fail("gate5_tax_model_methodology_invalid")
    _validate_behavior(behavior)
    _validate_legal_evidence(value["legal_evidence"], behavior)
    return copy.deepcopy(value)


def _validate_behavior(behavior: dict[str, Any]) -> None:
    bindings = behavior.get("input_bindings")
    applicability = behavior.get("applicability_rule")
    rules = behavior.get("expense_rules")
    expected_inputs = _BEHAVIOR_INPUTS.get(behavior.get("behavior_id"))
    if (
        not _identifier(behavior.get("behavior_id"))
        or expected_inputs is None
        or not _identifier(behavior.get("model_id"))
        or not isinstance(bindings, dict)
        or set(bindings) != _MONEY_INPUTS
        or not isinstance(applicability, dict)
        or set(applicability) != {"rule_id", "required_values", "result_category"}
        or not _identifier(applicability.get("rule_id"))
        or not _identifier(applicability.get("result_category"))
        or not isinstance(applicability.get("required_values"), dict)
        or set(applicability["required_values"]) != expected_inputs
        or not isinstance(rules, list)
        or len(rules) != 2
    ):
        _fail("gate5_tax_model_methodology_invalid")
    for name, binding in bindings.items():
        if (
            not _input_name(name)
            or not isinstance(binding, dict)
            or set(binding) != {"amount_requirement_id", "currency_requirement_id"}
            or not all(_identifier(item) for item in binding.values())
        ):
            _fail("gate5_tax_model_methodology_invalid")
    components = set()
    input_names = set()
    for rule in rules:
        if (
            not isinstance(rule, dict)
            or set(rule)
            != {
                "component_id",
                "input_name",
                "expense_kind",
                "rule_id",
                "required_evidence_flags",
                "evidence_refs",
            }
            or rule.get("required_evidence_flags") != sorted(_EXPENSE_FLAGS)
            or not all(
                _identifier(rule.get(key))
                for key in ("component_id", "input_name", "expense_kind", "rule_id")
            )
            or not isinstance(rule.get("evidence_refs"), list)
            or not rule["evidence_refs"]
            or rule["evidence_refs"] != sorted(set(rule["evidence_refs"]))
        ):
            _fail("gate5_tax_model_methodology_invalid")
        components.add(rule["component_id"])
        input_names.add(rule["input_name"])
    if len(components) != 2 or input_names != set(bindings) - {"gross_income"}:
        _fail("gate5_tax_model_methodology_invalid")


def _validate_legal_evidence(value: Any, behavior: dict[str, Any]) -> None:
    if not isinstance(value, list) or not value:
        _fail("gate5_tax_model_methodology_evidence_invalid")
    evidence_refs = set()
    for item in value:
        if (
            not isinstance(item, dict)
            or item.get("authority_kind")
            not in {"official_legal_text", "tax_authority_primary"}
            or not _identifier(item.get("evidence_ref"))
            or not isinstance(item.get("source_url"), str)
            or not item["source_url"].startswith("https://")
            or item.get("effective_tax_period")
            != behavior["applicability_rule"]["required_values"]["tax_period"]
            or not _valid_capture(item)
        ):
            _fail("gate5_tax_model_methodology_evidence_invalid")
        evidence_refs.add(item["evidence_ref"])
    referenced = {
        ref for rule in behavior["expense_rules"] for ref in rule["evidence_refs"]
    }
    if len(evidence_refs) != len(value) or evidence_refs != referenced:
        _fail("gate5_tax_model_methodology_evidence_invalid")


def _valid_capture(value: dict[str, Any]) -> bool:
    if value.get("capture_status") == "official_locator_verified_no_bytes":
        return (
            value.get("content_bytes") is None and value.get("content_sha256") is None
        )
    return bool(
        value.get("capture_status") == "downloaded_official_bytes_verified"
        and isinstance(value.get("content_bytes"), int)
        and not isinstance(value["content_bytes"], bool)
        and value["content_bytes"] > 0
        and isinstance(value.get("content_sha256"), str)
        and _SHA256.fullmatch(value["content_sha256"])
    )


def _require_applicability(
    required: dict[str, str], actual: dict[str, dict[str, Any]]
) -> None:
    for name in sorted(required):
        tagged = actual.get(name)
        if tagged is None:
            if name == "loss_treatment":
                _fail("gate5_tax_model_loss_treatment_missing")
            if name == "scope_completeness":
                _fail("gate5_tax_model_scope_incomplete")
            _fail("gate5_tax_model_classification_prerequisite_missing", name)
        if tagged["value"] != required[name]:
            if name == "loss_treatment":
                _fail("gate5_tax_model_loss_treatment_unsupported")
            if name == "scope_completeness":
                _fail("gate5_tax_model_scope_incomplete")
            _fail("gate5_tax_model_classification_prerequisite_unsupported", name)


def _money_inputs(
    bindings: dict[str, dict[str, str]], requirements: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    result = {
        name: _money_input(name, binding, requirements)
        for name, binding in sorted(bindings.items())
    }
    if len({item["value"]["currency"] for item in result.values()}) != 1:
        _fail("gate5_tax_model_currency_mismatch")
    return result


def _money_input(
    name: str,
    binding: dict[str, str],
    requirements: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    amount_ref = binding["amount_requirement_id"]
    currency_ref = binding["currency_requirement_id"]
    amount_requirement = requirements.get(amount_ref)
    currency_requirement = requirements.get(currency_ref)
    if (
        not isinstance(amount_requirement, dict)
        or not isinstance(currency_requirement, dict)
        or amount_requirement.get("status") != "satisfied"
        or currency_requirement.get("status") != "satisfied"
        or amount_requirement.get("subject_ref")
        != currency_requirement.get("subject_ref")
    ):
        _fail("gate5_tax_model_input_binding_invalid", name)
    amount = _source_value(amount_requirement, "amount")
    currency = _source_value(currency_requirement, "currency")
    if not isinstance(currency, str) or not _CURRENCY.fullmatch(currency):
        _fail("gate5_tax_model_money_invalid", name)
    refs = list(dict.fromkeys((amount_ref, currency_ref)))
    return {
        "input_name": name,
        "requirement_refs": refs,
        "value": {
            "kind": "money",
            "amount": _amount(amount, name),
            "currency": currency,
        },
        "sources": [
            {
                "requirement_id": ref,
                "source": copy.deepcopy(requirements[ref]["source"]),
            }
            for ref in refs
        ],
    }


def _source_value(requirement: dict[str, Any], key: str) -> Any:
    source = requirement.get("source")
    if not isinstance(source, dict):
        _fail("gate5_tax_model_input_source_invalid")
    if source.get("source_kind") == "financial_case":
        matches = source.get("matches")
        if (
            not isinstance(matches, list)
            or len(matches) != 1
            or not isinstance(matches[0].get("value"), str)
        ):
            _fail("gate5_tax_model_source_value_ambiguous")
        return matches[0]["value"]
    value = source.get("value")
    if (
        source.get("source_kind") != "supplemental_fact"
        or not isinstance(value, dict)
        or value.get("kind") != "money"
    ):
        _fail("gate5_tax_model_input_source_invalid")
    return value.get(key)


def _amount(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _MONEY.fullmatch(value):
        _fail("gate5_tax_model_money_invalid", name)
    try:
        return f"{Decimal(value):.2f}"
    except InvalidOperation as exc:
        raise Gate5SecuritiesDisposalTaxModelError(
            "gate5_tax_model_money_invalid", name
        ) from exc


def _operation_tax_model(
    *,
    authority_binding: dict[str, Any],
    behavior: dict[str, Any],
    inputs: dict[str, Any],
    applicability: dict[str, dict[str, Any]],
    money_inputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    evidence = inputs["expense_evidence"]
    rules = sorted(behavior["expense_rules"], key=lambda item: item["component_id"])
    if set(evidence) != {item["component_id"] for item in rules}:
        _fail("gate5_tax_model_expense_evidence_invalid")
    related = []
    allowable = []
    decisions = []
    for rule in rules:
        component_id = rule["component_id"]
        flags = evidence[component_id]
        relatedness = flags.get("related_to_operation")
        if relatedness is None:
            _fail("gate5_tax_model_relatedness_missing", component_id)
        component = {
            "component_id": component_id,
            "expense_kind": rule["expense_kind"],
            "value": copy.deepcopy(money_inputs[rule["input_name"]]["value"]),
            "sources": copy.deepcopy(money_inputs[rule["input_name"]]["sources"]),
            "relatedness": copy.deepcopy(relatedness),
        }
        if relatedness["value"] is True:
            related.append(component)
        prerequisites = []
        failed = []
        for flag in rule["required_evidence_flags"]:
            tagged = flags.get(flag)
            status = (
                "missing"
                if tagged is None
                else ("satisfied" if tagged["value"] is True else "not_satisfied")
            )
            prerequisites.append(
                {
                    "flag": flag,
                    "status": status,
                    "provenance": None
                    if tagged is None
                    else copy.deepcopy(tagged["provenance"]),
                }
            )
            if status != "satisfied":
                failed.append(flag)
        if not failed:
            allowable.append(copy.deepcopy(component))
        decisions.append(
            {
                "component_id": component_id,
                "status": "allowed" if not failed else "not_allowed_unproven",
                "rule_id": rule["rule_id"],
                "methodology_projection_sha256": authority_binding["projection_sha256"],
                "legal_evidence_refs": copy.deepcopy(rule["evidence_refs"]),
                "prerequisites": prerequisites,
                "failed_prerequisites": failed,
            }
        )
    currency = money_inputs["gross_income"]["value"]["currency"]
    classification = behavior["applicability_rule"]
    return {
        "schema_version": (
            GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
        ),
        "status": "complete",
        "model_id": behavior["model_id"],
        "model_kind": "securities_disposal",
        "operation_scope": {
            "subject_ref": inputs["subject_ref"],
            "tax_period": copy.deepcopy(inputs["tax_context"]["tax_period"]),
            "residency": copy.deepcopy(inputs["tax_context"]["residency"]),
            "exemption_applicability": copy.deepcopy(
                inputs["tax_context"]["exemption_applicability"]
            ),
            "aggregation_kind": "single_operation_only",
        },
        "methodology_binding": {
            **copy.deepcopy(authority_binding),
            "behavior_id": behavior["behavior_id"],
            "applicability_rule_id": classification["rule_id"],
        },
        "operation": {
            "kind": copy.deepcopy(inputs["operation_properties"]["operation_kind"]),
            "category": {
                "value": classification["result_category"],
                "decision_provenance": {
                    "source_kind": "methodology_derived",
                    "rule_id": classification["rule_id"],
                    "methodology_projection_sha256": authority_binding[
                        "projection_sha256"
                    ],
                    "prerequisites": [
                        {
                            "property": name,
                            "value": copy.deepcopy(applicability[name]["value"]),
                            "provenance": copy.deepcopy(
                                applicability[name]["provenance"]
                            ),
                        }
                        for name in sorted(classification["required_values"])
                    ],
                },
            },
        },
        "gross_income": {
            "value": copy.deepcopy(money_inputs["gross_income"]["value"]),
            "sources": copy.deepcopy(money_inputs["gross_income"]["sources"]),
            "derivation": {
                "kind": "resolved_operation_input",
            },
        },
        "related_expenses": {
            "components": related,
            "total": _sum(related, currency),
        },
        "allowable_expenses": {
            "decisions": decisions,
            "components": allowable,
            "total": _sum(allowable, currency),
        },
        "loss_treatment": copy.deepcopy(inputs["tax_context"]["loss_treatment"]),
        "proof_assumptions": _assumptions(inputs),
    }


def _tax_model(
    *,
    authority_binding: dict[str, Any],
    behavior: dict[str, Any],
    inputs: dict[str, Any],
    applicability: dict[str, dict[str, Any]],
    money_inputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    operation_model = _operation_tax_model(
        authority_binding=authority_binding,
        behavior=behavior,
        inputs=inputs,
        applicability=applicability,
        money_inputs=money_inputs,
    )
    completeness = inputs["scope"].get("scope_completeness")
    if completeness is None:
        _fail("gate5_tax_model_scope_incomplete")
    return {
        "schema_version": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_SCHEMA_VERSION,
        "status": operation_model["status"],
        "model_id": operation_model["model_id"],
        "model_kind": operation_model["model_kind"],
        "calculation_scope": {
            "subject_ref": operation_model["operation_scope"]["subject_ref"],
            "tax_period": copy.deepcopy(
                operation_model["operation_scope"]["tax_period"]
            ),
            "residency": copy.deepcopy(operation_model["operation_scope"]["residency"]),
            "exemption_applicability": copy.deepcopy(
                operation_model["operation_scope"]["exemption_applicability"]
            ),
            "completeness": copy.deepcopy(completeness),
            "aggregation_kind": "complete_category_scope",
        },
        "methodology_binding": copy.deepcopy(operation_model["methodology_binding"]),
        "operation": copy.deepcopy(operation_model["operation"]),
        "category_gross_income": {
            "value": copy.deepcopy(operation_model["gross_income"]["value"]),
            "sources": copy.deepcopy(operation_model["gross_income"]["sources"]),
            "derivation": {
                "kind": "complete_scope_sum",
                "scope_completeness": copy.deepcopy(completeness),
            },
        },
        "related_expenses": copy.deepcopy(operation_model["related_expenses"]),
        "allowable_expenses": copy.deepcopy(operation_model["allowable_expenses"]),
        "loss_treatment": copy.deepcopy(operation_model["loss_treatment"]),
        "proof_assumptions": copy.deepcopy(operation_model["proof_assumptions"]),
    }


def _sum(components: list[dict[str, Any]], currency: str) -> dict[str, str]:
    amount = sum(
        (Decimal(item["value"]["amount"]) for item in components), Decimal("0.00")
    )
    return {"kind": "money", "amount": f"{amount:.2f}", "currency": currency}


def _assumptions(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    tagged_values = []
    for section in _SECTIONS:
        tagged_values.extend(
            (f"{section}.{name}", item) for name, item in inputs[section].items()
        )
    for component, flags in inputs["expense_evidence"].items():
        tagged_values.extend(
            (f"expense_evidence.{component}.{name}", item)
            for name, item in flags.items()
        )
    return sorted(
        (
            {
                "input_path": path,
                "value": copy.deepcopy(item["value"]),
                "source_ref": item["provenance"]["source_ref"],
            }
            for path, item in tagged_values
            if item["provenance"]["source_kind"] == "proof_assumption"
        ),
        key=lambda item: item["input_path"],
    )


def _declaration_semantics(model: dict[str, Any]) -> dict[str, Any]:
    def money(value: dict[str, str]) -> dict[str, str]:
        return {"amount": value["amount"], "currency": value["currency"]}

    return {
        "schema_version": GATE5_DECLARATION_PROJECTION_INPUT_SCHEMA_VERSION,
        "operation_category": model["operation"]["category"]["value"],
        "operation_category_gross_income": money(
            model["category_gross_income"]["value"]
        ),
        "related_expenses": money(model["related_expenses"]["total"]),
        "allowable_expenses": money(model["allowable_expenses"]["total"]),
        "loss_treatment": model["loss_treatment"]["value"],
    }


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _input_name(value: Any) -> bool:
    return isinstance(value, str) and _INPUT_NAME.fullmatch(value) is not None


def _fail(code: str, field: str = "") -> None:
    raise Gate5SecuritiesDisposalTaxModelError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_SECURITIES_DISPOSAL_CURRENT_SOURCE_FACT_OPERATION_RESULT_SCHEMA_VERSION",
    "GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_BEHAVIOR_ID",
    "GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_RESULT_SCHEMA_VERSION",
    "GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION",
    "GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_BEHAVIOR_ID",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_RESULT_SCHEMA_VERSION",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_SCHEMA_VERSION",
    "Gate5SecuritiesDisposalTaxModelError",
    "Gate5SecuritiesDisposalTaxModelRuntime",
    "Gate5SecuritiesDisposalTaxModelRuntimeFactory",
]
