"""Consume Gate 4 normalized source facts with bounded deterministic rules."""

from __future__ import annotations

import copy
from datetime import date
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort
from .gate4_financial_case_cache import Gate4FinancialCaseRuntimeFactory
from .gate4_financial_case_materialization import (
    GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION,
)
from .gate5_trusted_methodology import (
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_SCHEMA_VERSION,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthority,
    Gate5TrustedMethodologyAuthorityFactory,
)


GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_deterministic_source_fact_consumption_result_v0"
)
GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_TERMINAL = (
    "DETERMINISTIC_SOURCE_FACT_CONSUMPTION_PROVEN"
)
GATE5_FIFO_WITHOUT_STORED_EVENT_TERMINAL = "FIFO_WITHOUT_STORED_EVENT_PROVEN"
GATE5_SOURCE_GRANULARITY_TERMINAL = "SOURCE_GRANULARITY_PRESERVED"
GATE5_SOURCE_FACT_ASSESSMENT_SCHEMA_VERSION = (
    "broker_reports_gate5_source_fact_assessment_v0"
)
GATE5_SOURCE_FACT_ASSERTIONS_TERMINAL = "SOURCE_FACT_ASSERTIONS_PRESERVED"
GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_SCHEMA_VERSION = (
    "broker_reports_gate5_available_source_fact_assembly_v0"
)
GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_TERMINAL = (
    "AVAILABLE_SOURCE_FACTS_DETERMINISTICALLY_ASSEMBLED"
)
GATE5_COMMISSION_EVIDENCE_COVERAGE_SCHEMA_VERSION = (
    "broker_reports_gate5_commission_evidence_coverage_v0"
)
GATE5_COMMISSION_EVIDENCE_SELECTION_SCHEMA_VERSION = (
    "broker_reports_gate5_commission_evidence_selection_v0"
)
GATE5_COMMISSION_SELECTION_CONTRACT_TERMINAL = (
    "COMMISSION_SELECTION_CONTRACT_PROVEN"
)
GATE5_ACQUISITION_BASIS_COVERAGE_SCHEMA_VERSION = (
    "broker_reports_gate5_acquisition_basis_coverage_v0"
)
GATE5_ACQUISITION_BASIS_COVERAGE_CONTRACT_TERMINAL = (
    "ACQUISITION_BASIS_COVERAGE_CONTRACT_PROVEN"
)

FACTORY_REQUIRED = (
    "Gate5DeterministicSourceFactConsumptionRuntimeFactory.create composes "
    "Gate4FinancialCaseRuntimeFactory.create and "
    "Gate5TrustedMethodologyAuthorityFactory.create",
)
FORBIDDEN = (
    "direct SQL, Canonical, Gate 3 target parsing, broker/source reads, LLM, "
    "provider, reconciliation, inferred financial events or persisted relations",
    "default zero, aggregate allocation, partial acquisition commission "
    "methodology or currency conversion",
)

_BEHAVIOR_ID = "securities_fifo_source_fact_consumption_v0"
_PURCHASE = "SECURITY_PURCHASE"
_DISPOSAL = "SECURITY_DISPOSAL"
_DIRECT_CHARGE = "TRANSACTION_CHARGE"
_COMMISSION_DETAIL_TYPES = frozenset({_DIRECT_CHARGE, "COMMISSION"})
_COMMISSION_TOTAL = "COMMISSION_TOTAL"
_WITHHELD_DETAIL = "TAX_WITHHELD"
_WITHHELD_TOTAL = "TAX_WITHHELD_TOTAL"
_SECURITY_ROLES = ("date", "asset", "quantity", "amount", "currency")
_MONEY = re.compile(r"^-?(?:0|[1-9][0-9]{0,17})(?:\.[0-9]+)?$")
_QUANTITY = re.compile(r"^(?:0|[1-9][0-9]{0,17})(?:\.[0-9]+)?$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class Gate5DeterministicSourceFactConsumptionError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5DeterministicSourceFactConsumptionRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate5DeterministicSourceFactConsumptionRuntime":
        return Gate5DeterministicSourceFactConsumptionRuntime(
            financial_case=Gate4FinancialCaseRuntimeFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            authority=Gate5TrustedMethodologyAuthorityFactory.create(),
        )


class Gate5DeterministicSourceFactConsumptionRuntime:
    def __init__(
        self,
        *,
        financial_case: Any,
        authority: Gate5TrustedMethodologyAuthority,
    ) -> None:
        self._financial_case = financial_case
        self._authority = authority

    def run(
        self,
        *,
        methodology_ref: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        resolved = self._authority.resolve(methodology_ref)
        methodology = _methodology(
            resolved["methodology"],
            authority_binding=resolved["authority_binding"],
        )
        facts = self._financial_case.list_facts(context=context)
        return _consume(
            facts=facts,
            context=context,
            authority_binding=resolved["authority_binding"],
            behavior=methodology["behavior"],
        )

    def assess(
        self,
        *,
        methodology_ref: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        """Assess real facts without dropping incomplete security proposals."""

        resolved = self._authority.resolve(methodology_ref)
        methodology = _methodology(
            resolved["methodology"],
            authority_binding=resolved["authority_binding"],
        )
        expected_case_binding = _case_binding(context)
        facts = [
            _source_fact(fact, expected_case_binding=expected_case_binding)
            for fact in self._financial_case.list_facts(context=context)
        ]
        securities = [
            _security_assessment(fact)
            for fact in facts
            if fact["financial_type"] in {_PURCHASE, _DISPOSAL}
        ]
        counts = {
            "total": len(securities),
            "ready": sum(item["status"] == "ready" for item in securities),
            "source_evidence_insufficient": sum(
                item["status"] == "source_evidence_insufficient"
                for item in securities
            ),
        }
        complete_types = {
            item["financial_type"]
            for item in securities
            if item["status"] == "ready"
        }
        tax_input_status = (
            "READY_FOR_FIFO"
            if counts["source_evidence_insufficient"] == 0
            and {_PURCHASE, _DISPOSAL}.issubset(complete_types)
            else "SOURCE_EVIDENCE_INSUFFICIENT"
        )
        document_consumption = []
        document_ids = sorted(
            {
                fact["gate3_binding"]["canonical_binding"]["document_id"]
                for fact in facts
            }
        )
        for document_id in document_ids:
            document_facts = [
                fact
                for fact in facts
                if fact["gate3_binding"]["canonical_binding"]["document_id"]
                == document_id
            ]
            document_security = [
                item
                for item in securities
                if any(
                    fact["fact_id"] == item["fact_id"]
                    for fact in document_facts
                )
            ]
            document_consumption.append(
                _document_consumption_assessment(
                    document_id=document_id,
                    facts=document_facts,
                    securities=document_security,
                    context=context,
                    authority_binding=resolved["authority_binding"],
                    behavior=methodology["behavior"],
                )
            )
        return {
            "schema_version": GATE5_SOURCE_FACT_ASSESSMENT_SCHEMA_VERSION,
            "status": "assessed",
            "terminals": [GATE5_SOURCE_FACT_ASSERTIONS_TERMINAL],
            "case_binding": copy.deepcopy(expected_case_binding),
            "methodology_binding": {
                **copy.deepcopy(resolved["authority_binding"]),
                "behavior_id": methodology["behavior"]["behavior_id"],
            },
            "facts_total": len(facts),
            "security_tax_input_status": tax_input_status,
            "security_fact_counts": counts,
            "security_facts": securities,
            "document_consumption": document_consumption,
            "assertions": {
                "commissions": _assertion_set(
                    facts=facts,
                    detail_types=_COMMISSION_DETAIL_TYPES,
                    total_type=_COMMISSION_TOTAL,
                ),
                "withheld_tax": _assertion_set(
                    facts=facts,
                    detail_types=frozenset({_WITHHELD_DETAIL}),
                    total_type=_WITHHELD_TOTAL,
                ),
            },
            "reconciliation": "not_performed",
            "stored_financial_event_relations": 0,
        }

    def assemble_available(
        self,
        *,
        methodology_ref: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        """Resolve independent FIFO groups and retain every exact blocker."""

        resolved = self._authority.resolve(methodology_ref)
        methodology = _methodology(
            resolved["methodology"],
            authority_binding=resolved["authority_binding"],
        )
        expected_case_binding = _case_binding(context)
        facts = [
            _source_fact(fact, expected_case_binding=expected_case_binding)
            for fact in self._financial_case.list_facts(context=context)
        ]
        assembly = _assemble_available_security_groups(
            facts=facts,
            context=context,
            authority_binding=resolved["authority_binding"],
            behavior=methodology["behavior"],
        )
        return {
            "schema_version": GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_SCHEMA_VERSION,
            "status": "assembled_available_evidence",
            "terminals": [
                GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_TERMINAL,
                GATE5_FIFO_WITHOUT_STORED_EVENT_TERMINAL,
                GATE5_SOURCE_GRANULARITY_TERMINAL,
                GATE5_SOURCE_FACT_ASSERTIONS_TERMINAL,
            ],
            "case_binding": copy.deepcopy(expected_case_binding),
            "methodology_binding": {
                **copy.deepcopy(resolved["authority_binding"]),
                "behavior_id": methodology["behavior"]["behavior_id"],
            },
            "source_document_ids": sorted(
                {
                    fact["gate3_binding"]["canonical_binding"]["document_id"]
                    for fact in facts
                }
            ),
            "facts_total": len(facts),
            "financial_type_counts": {
                financial_type: sum(
                    fact["financial_type"] == financial_type for fact in facts
                )
                for financial_type in sorted(
                    {fact["financial_type"] for fact in facts}
                )
            },
            "fact_ids_by_financial_type": {
                financial_type: sorted(
                    fact["fact_id"]
                    for fact in facts
                    if fact["financial_type"] == financial_type
                )
                for financial_type in sorted(
                    {fact["financial_type"] for fact in facts}
                )
            },
            **assembly,
            "assertions": {
                "commissions": _assertion_set(
                    facts=facts,
                    detail_types=_COMMISSION_DETAIL_TYPES,
                    total_type=_COMMISSION_TOTAL,
                ),
                "withheld_tax": _assertion_set(
                    facts=facts,
                    detail_types=frozenset({_WITHHELD_DETAIL}),
                    total_type=_WITHHELD_TOTAL,
                ),
            },
            "reconciliation": "not_performed",
            "invented_facts": 0,
            "invented_relations": 0,
            "stored_financial_event_relations": 0,
        }

    def select_commission_evidence(
        self,
        *,
        source_assembly: dict[str, Any],
        coverage: dict[str, Any],
    ) -> dict[str, Any]:
        """Select one source representation under explicit scope coverage."""

        assertions = _commission_assertions(source_assembly)
        resolved = self._authority.resolve(
            {
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
                "methodology_version": GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
            }
        )
        methodology = _methodology(
            resolved["methodology"],
            authority_binding=resolved["authority_binding"],
        )
        selection_policy = methodology["behavior"]["independent_assertions"][
            "commission_selection"
        ]
        scoped = _commission_coverage(coverage, assertions=assertions)
        details = {
            item["fact_id"]: item for item in assertions["detail"]
        }
        aggregates = {
            item["fact_id"]: item for item in assertions["aggregate"]
        }
        selected: list[dict[str, Any]] = []
        representation = None
        reason = "detail_coverage_unproven_and_matching_aggregate_absent"
        if (
            scoped["detail_coverage_status"] == "PROVEN_COMPLETE"
            and scoped["eligible_detail_fact_ids"]
        ):
            selected = [details[item] for item in scoped["eligible_detail_fact_ids"]]
            representation = "DETAIL"
            reason = "exact_required_scope_detail_coverage_proven"
        elif scoped["aggregate_scope_status"] == "PROVEN_MATCHING":
            selected = [aggregates[scoped["aggregate_fact_id"]]]
            representation = "AGGREGATE"
            reason = "matching_aggregate_scope_proven"
        if not selected:
            return _commission_selection_result(
                status="FAIL_CLOSED",
                representation=None,
                selected=[],
                scope=scoped,
                assertions=assertions,
                authority_binding=resolved["authority_binding"],
                policy=selection_policy,
                reason=reason,
            )
        return _commission_selection_result(
            status="SELECTED",
            representation=representation,
            selected=selected,
            scope=scoped,
            assertions=assertions,
            authority_binding=resolved["authority_binding"],
            policy=selection_policy,
            reason=reason,
        )


def _consume(
    *,
    facts: Any,
    context: ArtifactAccessContext,
    authority_binding: dict[str, Any],
    behavior: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(facts, list):
        _fail("gate5_source_fact_case_invalid")
    expected_case_binding = _case_binding(context)
    validated = [
        _source_fact(fact, expected_case_binding=expected_case_binding)
        for fact in facts
    ]
    purchases = [fact for fact in validated if fact["financial_type"] == _PURCHASE]
    disposals = [fact for fact in validated if fact["financial_type"] == _DISPOSAL]
    if not purchases:
        _fail("gate5_source_fact_acquisition_missing")
    if not disposals:
        _fail("gate5_source_fact_disposal_missing")

    purchase_inputs = [_security_input(fact) for fact in purchases]
    disposal_inputs = [_security_input(fact) for fact in disposals]
    return _consumption_result(
        validated=validated,
        purchase_inputs=purchase_inputs,
        disposal_inputs=disposal_inputs,
        expected_case_binding=expected_case_binding,
        authority_binding=authority_binding,
        behavior=behavior,
    )


def _consumption_result(
    *,
    validated: list[dict[str, Any]],
    purchase_inputs: list[dict[str, Any]],
    disposal_inputs: list[dict[str, Any]],
    expected_case_binding: dict[str, str],
    authority_binding: dict[str, Any],
    behavior: dict[str, Any],
) -> dict[str, Any]:
    _require_disposal_order_resolved(
        purchases=purchase_inputs,
        disposals=disposal_inputs,
    )
    securities = _fifo(
        purchases=purchase_inputs,
        disposals=disposal_inputs,
        all_facts=validated,
    )
    return {
        "schema_version": (
            GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_RESULT_SCHEMA_VERSION
        ),
        "status": "consumed",
        "terminals": [
            GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_TERMINAL,
            GATE5_FIFO_WITHOUT_STORED_EVENT_TERMINAL,
            GATE5_SOURCE_GRANULARITY_TERMINAL,
        ],
        "case_binding": copy.deepcopy(expected_case_binding),
        "methodology_binding": {
            **copy.deepcopy(authority_binding),
            "behavior_id": behavior["behavior_id"],
        },
        "securities": securities,
        "assertions": {
            "commissions": _assertion_set(
                facts=validated,
                detail_types=_COMMISSION_DETAIL_TYPES,
                total_type=_COMMISSION_TOTAL,
            ),
            "withheld_tax": _assertion_set(
                facts=validated,
                detail_types=frozenset({_WITHHELD_DETAIL}),
                total_type=_WITHHELD_TOTAL,
            ),
        },
        "capability_map": {
            "fifo_acquisition_cost": "SUPPORTED",
            "disposal_income": "SUPPORTED",
            "direct_disposal_charge_context": (
                "SOURCE_EVIDENCE_ONLY_WHEN_SAME_SOURCE_TRANSACTION_ROW"
            ),
            "commission_detail_aggregate_hybrid": "SUPPORTED_WITHOUT_RECONCILIATION",
            "withheld_tax_detail_aggregate_hybrid": "SUPPORTED_WITHOUT_RECONCILIATION",
            "partial_acquisition_commission": "METHODOLOGY_UNRESOLVED",
            "currency_conversion": "METHODOLOGY_UNRESOLVED",
        },
    }


def gate5_source_fact_tax_model_inputs(
    value: Any,
    *,
    disposal_fact_id: str,
    context: ArtifactAccessContext,
) -> dict[str, dict[str, Any]]:
    """Validate one consumption result and expose its three Tax Model inputs."""

    expected_terminals = [
        GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_TERMINAL,
        GATE5_FIFO_WITHOUT_STORED_EVENT_TERMINAL,
        GATE5_SOURCE_GRANULARITY_TERMINAL,
    ]
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "status",
            "terminals",
            "case_binding",
            "methodology_binding",
            "securities",
            "assertions",
            "capability_map",
        }
        or value.get("schema_version")
        != GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_RESULT_SCHEMA_VERSION
        or value.get("status") != "consumed"
        or value.get("terminals") != expected_terminals
        or value.get("case_binding") != _case_binding(context)
        or not isinstance(value.get("securities"), list)
        or not isinstance(disposal_fact_id, str)
    ):
        _fail("gate5_source_fact_consumption_result_invalid")
    binding = value.get("methodology_binding")
    if (
        not isinstance(binding, dict)
        or binding.get("methodology_id") != GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID
        or binding.get("methodology_version")
        != GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION
        or binding.get("behavior_id") != _BEHAVIOR_ID
    ):
        _fail("gate5_source_fact_consumption_result_invalid")
    matches = [
        item
        for item in value["securities"]
        if isinstance(item, dict) and item.get("disposal_fact_id") == disposal_fact_id
    ]
    if len(matches) != 1:
        _fail("gate5_source_fact_disposal_selection_invalid")
    selected = matches[0]
    expense = selected.get("direct_transaction_expense")
    if (
        not isinstance(expense, dict)
        or expense.get("status") != "available"
        or expense.get("source_context") != "SAME_SOURCE_TRANSACTION_ROW"
        or expense.get("source_semantic") != "TRANSACTION_CHARGE_EVIDENCE"
        or expense.get("tax_deductibility_status") != "NOT_EVALUATED"
    ):
        _fail("gate5_source_fact_direct_expense_missing", disposal_fact_id)
    return {
        "gross_income": _tax_model_input(
            selected.get("gross_income"), expected_name="gross_income"
        ),
        "acquisition_cost": _tax_model_input(
            selected.get("recognized_acquisition_cost"),
            expected_name="acquisition_cost",
        ),
        "transaction_expense": _tax_model_input(
            expense,
            expected_name="transaction_expense",
        ),
    }


def _tax_model_input(value: Any, *, expected_name: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("input_name") != expected_name
        or not isinstance(value.get("sources"), list)
        or not value["sources"]
    ):
        _fail("gate5_source_fact_tax_model_input_invalid", expected_name)
    money = value.get("value")
    if (
        not isinstance(money, dict)
        or money.get("kind") != "money"
        or not isinstance(money.get("amount"), str)
        or _MONEY.fullmatch(money["amount"]) is None
        or not isinstance(money.get("currency"), str)
        or _CURRENCY.fullmatch(money["currency"]) is None
    ):
        _fail("gate5_source_fact_tax_model_input_invalid", expected_name)
    for source in value["sources"]:
        if (
            not isinstance(source, dict)
            or source.get("source_kind") != "normalized_source_fact"
            or re.fullmatch(r"g4fact_[0-9a-f]{32}", source.get("fact_id", "")) is None
        ):
            _fail("gate5_source_fact_tax_model_input_invalid", expected_name)
    return {
        "input_name": expected_name,
        "value": copy.deepcopy(money),
        "sources": copy.deepcopy(value["sources"]),
    }


def _methodology(value: Any, *, authority_binding: dict[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "methodology_id",
            "methodology_version",
            "status",
            "behavior",
            "evidence_binding",
        }
        or value.get("schema_version")
        != GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_SCHEMA_VERSION
        or value.get("methodology_id") != GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID
        or value.get("methodology_version")
        != GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION
        or value.get("methodology_id") != authority_binding.get("methodology_id")
        or value.get("methodology_version")
        != authority_binding.get("methodology_version")
        or value.get("status") != "PUBLISHED_PROOF_ONLY"
    ):
        _fail("gate5_source_fact_methodology_invalid")
    behavior = value.get("behavior")
    if (
        not isinstance(behavior, dict)
        or set(behavior)
        != {
            "behavior_id",
            "source_fact_schema_version",
            "source_fact_semantic_kind",
            "acquisition",
            "disposal",
            "fifo",
            "direct_disposal_expense",
            "independent_assertions",
            "unsupported",
        }
        or behavior.get("behavior_id") != _BEHAVIOR_ID
        or behavior.get("source_fact_schema_version")
        != GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION
        or behavior.get("source_fact_semantic_kind") != "normalized_source_fact"
    ):
        _fail("gate5_source_fact_methodology_invalid")
    if behavior.get("fifo") != {
        "rule_id": "article-214.1-fifo-acquisition-cost-proof-v0",
        "order_by": ["date"],
        "allocation": (
            "source_amount_times_consumed_quantity_divided_by_source_quantity"
        ),
        "same_date_policy": (
            "fail_closed_when_unordered_same_date_facts_make_cost_attribution_material"
        ),
        "rounding_policy": "exact_currency_minor_unit_only",
    }:
        _fail("gate5_source_fact_methodology_invalid")
    if behavior.get("direct_disposal_expense") != {
        "financial_type": "TRANSACTION_CHARGE",
        "binding": "same_canonical_table_row",
        "required_roles": ["amount", "currency"],
        "money_magnitude": "absolute_source_amount",
        "source_semantic": "source_authored_transaction_charge_context",
        "tax_deductibility": "not_determined_by_source_context",
    }:
        _fail("gate5_source_fact_methodology_invalid")
    if behavior.get("independent_assertions") != {
        "commission_detail_types": ["COMMISSION", "TRANSACTION_CHARGE"],
        "commission_total_type": "COMMISSION_TOTAL",
        "withheld_tax_detail_type": "TAX_WITHHELD",
        "withheld_tax_total_type": "TAX_WITHHELD_TOTAL",
        "reconciliation": "forbidden",
        "commission_selection": {
            "detail_precedence": (
                "only_when_exact_required_scope_coverage_is_proven"
            ),
            "aggregate_fallback": (
                "only_when_detail_coverage_is_unproven_or_absent_and_exact_aggregate_scope_is_proven"
            ),
            "preserve_both_representations": True,
            "select_one_representation": True,
            "compare_detail_and_aggregate_values": False,
            "tax_eligibility": "not_decided_by_evidence_selection",
        },
    }:
        _fail("gate5_source_fact_methodology_invalid")
    return copy.deepcopy(value)


def _source_fact(
    value: Any, *, expected_case_binding: dict[str, str]
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION
        or value.get("semantic_kind") != "normalized_source_fact"
        or value.get("case_binding") != expected_case_binding
        or not isinstance(value.get("fact_id"), str)
        or re.fullmatch(r"g4fact_[0-9a-f]{32}", value["fact_id"]) is None
        or value.get("status") not in {"role_complete", "role_incomplete"}
        or not isinstance(value.get("roles"), list)
        or not isinstance(value.get("gate3_binding"), dict)
        or not isinstance(value.get("annotation_target"), dict)
    ):
        _fail("gate5_source_fact_contract_invalid")
    return copy.deepcopy(value)


def _security_input(fact: dict[str, Any]) -> dict[str, Any]:
    roles = _roles(fact)
    missing = [
        role for role in _SECURITY_ROLES if roles.get(role, {}).get("status") != "value"
    ]
    if fact.get("status") != "role_complete" or missing:
        _fail(
            "gate5_source_fact_required_role_missing",
            f"{fact['fact_id']}:{','.join(missing)}",
        )
    values = {role: roles[role]["value"] for role in _SECURITY_ROLES}
    quantity = _decimal(values["quantity"], field="quantity", positive=True)
    amount = abs(_decimal(values["amount"], field="amount"))
    if (
        not isinstance(values["date"], str)
        or _DATE.fullmatch(values["date"]) is None
        or not _valid_calendar_date(values["date"])
    ):
        _fail("gate5_source_fact_date_invalid")
    if not isinstance(values["asset"], str) or not values["asset"].strip():
        _fail("gate5_source_fact_asset_invalid")
    if (
        not isinstance(values["currency"], str)
        or _CURRENCY.fullmatch(values["currency"]) is None
    ):
        _fail("gate5_source_fact_currency_invalid")
    return {
        "fact": fact,
        "date": values["date"],
        "asset": values["asset"],
        "quantity": quantity,
        "amount": amount,
        "currency": values["currency"],
    }


def _security_assessment(fact: dict[str, Any]) -> dict[str, Any]:
    try:
        _security_input(fact)
    except Gate5DeterministicSourceFactConsumptionError as exc:
        return {
            "fact_id": fact["fact_id"],
            "financial_type": fact["financial_type"],
            "status": "source_evidence_insufficient",
            "reason_code": exc.code,
        }
    return {
        "fact_id": fact["fact_id"],
        "financial_type": fact["financial_type"],
        "status": "ready",
        "reason_code": None,
    }


def _document_consumption_assessment(
    *,
    document_id: str,
    facts: list[dict[str, Any]],
    securities: list[dict[str, Any]],
    context: ArtifactAccessContext,
    authority_binding: dict[str, Any],
    behavior: dict[str, Any],
) -> dict[str, Any]:
    if any(item["status"] != "ready" for item in securities):
        return {
            "document_id": document_id,
            "status": "SOURCE_EVIDENCE_INSUFFICIENT",
            "reason_code": "gate5_source_fact_required_input_insufficient",
            "securities_consumed": 0,
        }
    try:
        consumed = _consume(
            facts=facts,
            context=context,
            authority_binding=authority_binding,
            behavior=behavior,
        )
    except Gate5DeterministicSourceFactConsumptionError as exc:
        return {
            "document_id": document_id,
            "status": "SOURCE_EVIDENCE_INSUFFICIENT",
            "reason_code": exc.code,
            "securities_consumed": 0,
        }
    return {
        "document_id": document_id,
        "status": "DETERMINISTIC_SOURCE_FACT_CONSUMPTION_PROVEN",
        "reason_code": None,
        "securities_consumed": len(consumed["securities"]),
    }


def _assemble_available_security_groups(
    *,
    facts: list[dict[str, Any]],
    context: ArtifactAccessContext,
    authority_binding: dict[str, Any],
    behavior: dict[str, Any],
) -> dict[str, Any]:
    ready_inputs: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    security_facts = [
        fact for fact in facts if fact["financial_type"] in {_PURCHASE, _DISPOSAL}
    ]
    for fact in security_facts:
        try:
            ready_inputs.append(_security_input(fact))
        except Gate5DeterministicSourceFactConsumptionError as exc:
            blockers.append(_invalid_security_fact_blocker(fact=fact, error=exc))

    grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = {}
    for item in ready_inputs:
        group = grouped.setdefault(
            (item["asset"], item["currency"]),
            {"purchases": [], "disposals": []},
        )
        target = (
            group["purchases"]
            if item["fact"]["financial_type"] == _PURCHASE
            else group["disposals"]
        )
        target.append(item)

    groups: list[dict[str, Any]] = []
    calculations: list[dict[str, Any]] = []
    for (asset, currency), members in sorted(grouped.items()):
        purchases = sorted(
            members["purchases"],
            key=lambda item: (item["date"], item["fact"]["fact_id"]),
        )
        disposals = sorted(
            members["disposals"],
            key=lambda item: (item["date"], item["fact"]["fact_id"]),
        )
        if not disposals:
            groups.append(
                _available_group_row(
                    asset=asset,
                    currency=currency,
                    purchases=purchases,
                    disposals=disposals,
                    status="NOT_ACTIVATED_FOR_SUPPLIED_CASE",
                    resolved_disposals=0,
                    blocker=None,
                )
            )
            continue

        resolved_disposals: list[dict[str, Any]] = []
        latest_consumption: dict[str, Any] | None = None
        group_blocker: dict[str, Any] | None = None
        for position, disposal in enumerate(disposals):
            attempted = [*resolved_disposals, disposal]
            try:
                latest_consumption = _consumption_result(
                    validated=facts,
                    purchase_inputs=purchases,
                    disposal_inputs=attempted,
                    expected_case_binding=_case_binding(context),
                    authority_binding=authority_binding,
                    behavior=behavior,
                )
            except Gate5DeterministicSourceFactConsumptionError as exc:
                group_blocker = _fifo_group_blocker(
                    error=exc,
                    asset=asset,
                    currency=currency,
                    purchases=purchases,
                    resolved_disposals=resolved_disposals,
                    unresolved_disposals=disposals[position:],
                )
                blockers.append(group_blocker)
                break
            resolved_disposals.append(disposal)

        if latest_consumption is not None:
            for calculation in latest_consumption["securities"]:
                calculation_row = copy.deepcopy(calculation)
                direct = calculation_row["direct_transaction_expense"]
                calculation_row["tax_model_input_status"] = (
                    "AVAILABLE"
                    if direct["status"] == "available"
                    else "MISSING_EVIDENCE"
                )
                calculations.append(calculation_row)
                if direct["status"] != "available":
                    blockers.append(
                        _direct_expense_blocker(
                            calculation=calculation_row,
                            asset=asset,
                            currency=currency,
                        )
                    )
        status = (
            "RESOLVED"
            if group_blocker is None
            else group_blocker["terminal"]
            if not resolved_disposals
            else "PARTIALLY_RESOLVED"
        )
        groups.append(
            _available_group_row(
                asset=asset,
                currency=currency,
                purchases=purchases,
                disposals=disposals,
                status=status,
                resolved_disposals=len(resolved_disposals),
                blocker=group_blocker,
            )
        )

    return {
        "security_fact_counts": {
            "total": len(security_facts),
            "ready": len(ready_inputs),
            "source_evidence_insufficient": len(security_facts) - len(ready_inputs),
        },
        "security_groups": groups,
        "fifo_calculations": calculations,
        "tax_model_ready_calculations": sum(
            item["tax_model_input_status"] == "AVAILABLE" for item in calculations
        ),
        "blockers": sorted(
            blockers,
            key=lambda item: (
                item["terminal"],
                item["reason_code"],
                item.get("fact_id", ""),
                item.get("first_unresolved_disposal_fact_id", ""),
            ),
        ),
    }


def _available_group_row(
    *,
    asset: str,
    currency: str,
    purchases: list[dict[str, Any]],
    disposals: list[dict[str, Any]],
    status: str,
    resolved_disposals: int,
    blocker: dict[str, Any] | None,
) -> dict[str, Any]:
    source_document_ids = sorted(
        {
            item["fact"]["gate3_binding"]["canonical_binding"]["document_id"]
            for item in [*purchases, *disposals]
        }
    )
    return {
        "asset": asset,
        "currency": currency,
        "status": status,
        "purchase_fact_ids": [item["fact"]["fact_id"] for item in purchases],
        "disposal_fact_ids": [item["fact"]["fact_id"] for item in disposals],
        "source_document_ids": source_document_ids,
        "multi_source": len(source_document_ids) > 1,
        "resolved_disposals": resolved_disposals,
        "blocker": copy.deepcopy(blocker),
    }


def _invalid_security_fact_blocker(
    *,
    fact: dict[str, Any],
    error: Gate5DeterministicSourceFactConsumptionError,
) -> dict[str, Any]:
    document_id = fact["gate3_binding"]["canonical_binding"]["document_id"]
    closing_evidence = {
        "gate5_source_fact_required_role_missing": (
            "the missing required source-bound role or another normalized fact "
            "that supplies the same declaration input with its own authority"
        ),
        "gate5_source_fact_date_invalid": "a complete authoritative calendar date",
        "gate5_source_fact_asset_invalid": "an exact authoritative instrument identity",
        "gate5_source_fact_currency_invalid": (
            "an authoritative ISO currency identity or a separately proven mapping"
        ),
        "gate5_source_fact_decimal_invalid": "an authoritative unambiguous numeric literal",
    }.get(error.code, "authoritative evidence satisfying the required source-fact role")
    return {
        "terminal": "SOURCE_EVIDENCE_INSUFFICIENT",
        "reason_code": error.code,
        "fact_id": fact["fact_id"],
        "financial_type": fact["financial_type"],
        "required_fact": "date, instrument, quantity, amount and ISO currency",
        "evidence_searched": {
            "document_id": document_id,
            "source_fact_id": fact["fact_id"],
        },
        "why_insufficient": error.field or error.code,
        "closing_evidence": closing_evidence,
    }


def _fifo_group_blocker(
    *,
    error: Gate5DeterministicSourceFactConsumptionError,
    asset: str,
    currency: str,
    purchases: list[dict[str, Any]],
    resolved_disposals: list[dict[str, Any]],
    unresolved_disposals: list[dict[str, Any]],
) -> dict[str, Any]:
    first = unresolved_disposals[0]
    terminal = (
        "METHODOLOGY_UNRESOLVED"
        if error.code
        in {
            "gate5_source_fact_fifo_rounding_methodology_unresolved",
            "gate5_source_fact_same_date_fifo_methodology_unresolved",
        }
        else "MISSING_EVIDENCE"
        if not purchases
        else "SOURCE_EVIDENCE_INSUFFICIENT"
    )
    available = sum(
        (
            item["quantity"]
            for item in purchases
            if item["date"] <= first["date"]
        ),
        Decimal("0"),
    ) - sum((item["quantity"] for item in resolved_disposals), Decimal("0"))
    available = max(available, Decimal("0"))
    missing = max(first["quantity"] - available, Decimal("0"))
    coverage = _acquisition_basis_coverage(
        disposed_quantity=first["quantity"],
        supported_quantity=min(first["quantity"], available),
    )
    return {
        "terminal": terminal,
        "reason_code": error.code,
        "first_unresolved_disposal_fact_id": first["fact"]["fact_id"],
        "unresolved_disposal_fact_ids": [
            item["fact"]["fact_id"] for item in unresolved_disposals
        ],
        "asset": asset,
        "currency": currency,
        "disposal_date": first["date"],
        "required_quantity": _decimal_text(first["quantity"]),
        "available_prior_quantity": _decimal_text(available),
        "minimum_missing_quantity": _decimal_text(missing),
        "acquisition_basis_coverage": coverage,
        "current_methodology_blocking_decision": "BLOCKED",
        "current_methodology_blocking_authority": (
            "article-214.1-fifo-acquisition-cost-proof-v0"
        ),
        "required_fact": "prior acquisition quantity for the same exact instrument and currency",
        "evidence_searched": {
            "purchase_fact_ids": [item["fact"]["fact_id"] for item in purchases],
            "eligible_purchase_fact_ids": [
                item["fact"]["fact_id"]
                for item in purchases
                if item["date"] <= first["date"]
            ],
        },
        "why_insufficient": error.code,
        "closing_evidence": (
            "a normalized SECURITY_PURCHASE for the same exact instrument and "
            "currency, dated no later than the disposal, covering at least the "
            f"minimum missing quantity { _decimal_text(missing) }"
        ),
    }


def _direct_expense_blocker(
    *, calculation: dict[str, Any], asset: str, currency: str
) -> dict[str, Any]:
    return {
        "terminal": "MISSING_EVIDENCE",
        "reason_code": "gate5_source_fact_direct_expense_missing",
        "first_unresolved_disposal_fact_id": calculation["disposal_fact_id"],
        "unresolved_disposal_fact_ids": [calculation["disposal_fact_id"]],
        "asset": asset,
        "currency": currency,
        "disposal_date": calculation["disposal_date"],
        "required_fact": (
            "source-authored transaction charge context or a separately "
            "methodology-authorized expense input"
        ),
        "evidence_searched": {"same_source_transaction_row_charges": 0},
        "why_insufficient": calculation["direct_transaction_expense"]["reason"],
        "closing_evidence": (
            "a source-bound charge on the same canonical transaction row or "
            "another methodology-authorized authoritative expense fact"
        ),
    }


def _roles(fact: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in fact["roles"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("role"), str)
            or item["role"] in result
            or item.get("status") not in {"value", "missing"}
        ):
            _fail("gate5_source_fact_role_contract_invalid")
        result[item["role"]] = item
    return result


def _valid_calendar_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def _fifo(
    *,
    purchases: list[dict[str, Any]],
    disposals: list[dict[str, Any]],
    all_facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lots = [
        {
            **purchase,
            "remaining_quantity": purchase["quantity"],
        }
        for purchase in sorted(
            purchases,
            key=lambda item: (item["date"], item["fact"]["fact_id"]),
        )
    ]
    results = []
    for disposal in sorted(
        disposals,
        key=lambda item: (item["date"], item["fact"]["fact_id"]),
    ):
        remaining = disposal["quantity"]
        _require_fifo_order_resolved(
            lots=lots,
            disposal=disposal,
            quantity=remaining,
        )
        fifo_inputs = []
        acquisition_cost = Decimal("0")
        for lot in lots:
            if (
                remaining == 0
                or lot["asset"] != disposal["asset"]
                or lot["currency"] != disposal["currency"]
                or lot["date"] > disposal["date"]
                or lot["remaining_quantity"] == 0
            ):
                continue
            consumed = min(remaining, lot["remaining_quantity"])
            cost = lot["amount"] * consumed / lot["quantity"]
            if cost != cost.quantize(Decimal("0.01")):
                _fail("gate5_source_fact_fifo_rounding_methodology_unresolved")
            acquisition_cost += cost
            lot["remaining_quantity"] -= consumed
            remaining -= consumed
            fifo_inputs.append(
                {
                    "acquisition_fact_id": lot["fact"]["fact_id"],
                    "acquisition_date": lot["date"],
                    "consumed_quantity": _decimal_text(consumed),
                    "recognized_cost": _money(cost, lot["currency"]),
                }
            )
        if remaining != 0:
            _fail(
                "gate5_source_fact_acquisition_quantity_insufficient",
                disposal["fact"]["fact_id"],
            )
        direct_charges = [
            fact
            for fact in all_facts
            if fact["financial_type"] == _DIRECT_CHARGE
            and _same_source_transaction_row(fact, disposal["fact"])
        ]
        transaction_expense = _direct_expense(
            facts=direct_charges,
            currency=disposal["currency"],
        )
        results.append(
            {
                "disposal_fact_id": disposal["fact"]["fact_id"],
                "asset": disposal["asset"],
                "disposal_date": disposal["date"],
                "disposed_quantity": _decimal_text(disposal["quantity"]),
                "gross_income": _money_input(
                    name="gross_income",
                    amount=disposal["amount"],
                    currency=disposal["currency"],
                    facts=[disposal["fact"]],
                ),
                "recognized_acquisition_cost": {
                    **_money_input(
                        name="acquisition_cost",
                        amount=acquisition_cost,
                        currency=disposal["currency"],
                        facts=[
                            item["fact"]
                            for item in purchases
                            if any(
                                row["acquisition_fact_id"] == item["fact"]["fact_id"]
                                for row in fifo_inputs
                            )
                        ],
                    ),
                    "fifo_inputs": fifo_inputs,
                },
                "acquisition_basis_coverage": _acquisition_basis_coverage(
                    disposed_quantity=disposal["quantity"],
                    supported_quantity=disposal["quantity"],
                ),
                "direct_transaction_expense": transaction_expense,
            }
        )
    return results


def _require_disposal_order_resolved(
    *,
    purchases: list[dict[str, Any]],
    disposals: list[dict[str, Any]],
) -> None:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for disposal in disposals:
        key = (disposal["asset"], disposal["currency"], disposal["date"])
        groups.setdefault(key, []).append(disposal)
    for (asset, currency, date), group in groups.items():
        if len(group) < 2:
            continue
        eligible_unit_costs = {
            purchase["amount"] / purchase["quantity"]
            for purchase in purchases
            if purchase["asset"] == asset
            and purchase["currency"] == currency
            and purchase["date"] <= date
        }
        if len(eligible_unit_costs) > 1:
            _fail("gate5_source_fact_same_date_fifo_methodology_unresolved")


def _require_fifo_order_resolved(
    *,
    lots: list[dict[str, Any]],
    disposal: dict[str, Any],
    quantity: Decimal,
) -> None:
    eligible = [
        lot
        for lot in lots
        if lot["asset"] == disposal["asset"]
        and lot["currency"] == disposal["currency"]
        and lot["date"] <= disposal["date"]
        and lot["remaining_quantity"] > 0
    ]
    remaining = quantity
    for date in sorted({lot["date"] for lot in eligible}):
        group = [lot for lot in eligible if lot["date"] == date]
        group_quantity = sum(
            (lot["remaining_quantity"] for lot in group),
            Decimal("0"),
        )
        if remaining >= group_quantity:
            remaining -= group_quantity
            continue
        unit_costs = {lot["amount"] / lot["quantity"] for lot in group}
        if remaining > 0 and len(unit_costs) > 1:
            _fail("gate5_source_fact_same_date_fifo_methodology_unresolved")
        return


def _direct_expense(*, facts: list[dict[str, Any]], currency: str) -> dict[str, Any]:
    if not facts:
        return {
            "status": "missing",
            "reason": "no_same_source_transaction_row_charge",
            "source_context": "SAME_SOURCE_TRANSACTION_ROW",
            "source_semantic": "TRANSACTION_CHARGE_EVIDENCE",
            "tax_deductibility_status": "NOT_EVALUATED",
        }
    total = Decimal("0")
    for fact in facts:
        roles = _roles(fact)
        amount = roles.get("amount")
        fact_currency = roles.get("currency")
        if (
            amount is None
            or amount.get("status") != "value"
            or fact_currency is None
            or fact_currency.get("status") != "value"
        ):
            _fail("gate5_source_fact_direct_expense_incomplete")
        if fact_currency["value"] != currency:
            _fail("gate5_source_fact_currency_mismatch")
        total += abs(_decimal(amount["value"], field="transaction_expense"))
    return {
        "status": "available",
        "source_context": "SAME_SOURCE_TRANSACTION_ROW",
        "source_semantic": "TRANSACTION_CHARGE_EVIDENCE",
        "tax_deductibility_status": "NOT_EVALUATED",
        **_money_input(
            name="transaction_expense",
            amount=total,
            currency=currency,
            facts=facts,
        ),
    }


def _acquisition_basis_coverage(
    *, disposed_quantity: Decimal, supported_quantity: Decimal
) -> dict[str, Any]:
    if disposed_quantity <= 0 or supported_quantity < 0 or supported_quantity > disposed_quantity:
        _fail("gate5_acquisition_basis_coverage_invalid")
    uncovered = disposed_quantity - supported_quantity
    return {
        "schema_version": GATE5_ACQUISITION_BASIS_COVERAGE_SCHEMA_VERSION,
        "concept": "ACQUISITION_BASIS_COVERAGE_GAP",
        "coverage_status": "COMPLETE" if uncovered == 0 else "GAP",
        "disposed_quantity": _decimal_text(disposed_quantity),
        "supported_acquisition_basis_quantity": _decimal_text(supported_quantity),
        "uncovered_quantity": _decimal_text(uncovered),
        "interpretation": "quantity_level_source_evidence_coverage_only",
        "financial_event_relation_asserted": False,
        "synthetic_zero_cost_assigned": False,
        "tax_conclusion": "NOT_MADE",
        "terminals": [GATE5_ACQUISITION_BASIS_COVERAGE_CONTRACT_TERMINAL],
    }


def _money_input(
    *,
    name: str,
    amount: Decimal,
    currency: str,
    facts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "input_name": name,
        "value": _money(amount, currency),
        "sources": [_fact_source(fact) for fact in facts],
    }


def _fact_source(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": "normalized_source_fact",
        "fact_id": fact["fact_id"],
        "financial_type": fact["financial_type"],
        "gate3_binding": copy.deepcopy(fact["gate3_binding"]),
        "annotation_target": copy.deepcopy(fact["annotation_target"]),
    }


def _assertion_set(
    *,
    facts: list[dict[str, Any]],
    detail_types: frozenset[str],
    total_type: str,
) -> dict[str, Any]:
    details = [
        _assertion(fact) for fact in facts if fact["financial_type"] in detail_types
    ]
    totals = [
        _assertion(fact) for fact in facts if fact["financial_type"] == total_type
    ]
    mode = (
        "hybrid"
        if details and totals
        else ("detail" if details else ("aggregate" if totals else "none"))
    )
    return {
        "mode": mode,
        "detail": details,
        "aggregate": totals,
        "reconciliation": "not_performed",
    }


def _assertion(fact: dict[str, Any]) -> dict[str, Any]:
    roles = _roles(fact)
    return {
        "fact_id": fact["fact_id"],
        "financial_type": fact["financial_type"],
        "status": fact["status"],
        "values": {
            name: copy.deepcopy(item.get("value"))
            for name, item in roles.items()
            if item.get("status") == "value"
        },
        "source": _fact_source(fact),
    }


def _commission_assertions(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version")
        not in {
            GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_SCHEMA_VERSION,
            GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_RESULT_SCHEMA_VERSION,
        }
        or not isinstance(value.get("assertions"), dict)
        or not isinstance(value["assertions"].get("commissions"), dict)
    ):
        _fail("gate5_commission_source_assembly_invalid")
    assertions = value["assertions"]["commissions"]
    if (
        set(assertions) != {"mode", "detail", "aggregate", "reconciliation"}
        or assertions.get("mode") not in {"none", "detail", "aggregate", "hybrid"}
        or assertions.get("reconciliation") != "not_performed"
        or not isinstance(assertions.get("detail"), list)
        or not isinstance(assertions.get("aggregate"), list)
    ):
        _fail("gate5_commission_assertions_invalid")
    rows = [*assertions["detail"], *assertions["aggregate"]]
    ids = [item.get("fact_id") for item in rows if isinstance(item, dict)]
    if len(ids) != len(rows) or len(ids) != len(set(ids)):
        _fail("gate5_commission_assertions_invalid")
    return copy.deepcopy(assertions)


def _commission_coverage(
    value: Any, *, assertions: dict[str, Any]
) -> dict[str, Any]:
    keys = {
        "schema_version",
        "required_scope_ref",
        "currency",
        "eligible_detail_fact_ids",
        "detail_coverage_status",
        "aggregate_fact_id",
        "aggregate_scope_status",
        "source_structure_evidence_refs",
    }
    if (
        not isinstance(value, dict)
        or set(value) != keys
        or value.get("schema_version")
        != GATE5_COMMISSION_EVIDENCE_COVERAGE_SCHEMA_VERSION
        or not isinstance(value.get("required_scope_ref"), str)
        or _IDENTIFIER.fullmatch(value["required_scope_ref"]) is None
        or not isinstance(value.get("currency"), str)
        or _CURRENCY.fullmatch(value["currency"]) is None
        or value.get("detail_coverage_status")
        not in {"PROVEN_COMPLETE", "UNPROVEN", "ABSENT"}
        or value.get("aggregate_scope_status")
        not in {"PROVEN_MATCHING", "UNPROVEN", "ABSENT"}
        or not isinstance(value.get("eligible_detail_fact_ids"), list)
        or value["eligible_detail_fact_ids"]
        != sorted(set(value["eligible_detail_fact_ids"]))
        or not all(isinstance(item, str) for item in value["eligible_detail_fact_ids"])
        or not isinstance(value.get("source_structure_evidence_refs"), list)
        or value["source_structure_evidence_refs"]
        != sorted(set(value["source_structure_evidence_refs"]))
        or not all(
            isinstance(item, str) and _IDENTIFIER.fullmatch(item) is not None
            for item in value["source_structure_evidence_refs"]
        )
    ):
        _fail("gate5_commission_coverage_invalid")
    detail_by_id = {item["fact_id"]: item for item in assertions["detail"]}
    aggregate_by_id = {item["fact_id"]: item for item in assertions["aggregate"]}
    detail_ids = value["eligible_detail_fact_ids"]
    aggregate_id = value["aggregate_fact_id"]
    if any(item not in detail_by_id for item in detail_ids):
        _fail("gate5_commission_coverage_fact_invalid")
    if (
        value["detail_coverage_status"] == "PROVEN_COMPLETE"
        and (not detail_ids or not value["source_structure_evidence_refs"])
    ) or (
        value["detail_coverage_status"] == "ABSENT" and detail_ids
    ):
        _fail("gate5_commission_detail_coverage_invalid")
    if value["aggregate_scope_status"] == "PROVEN_MATCHING":
        if (
            not isinstance(aggregate_id, str)
            or aggregate_id not in aggregate_by_id
            or not value["source_structure_evidence_refs"]
        ):
            _fail("gate5_commission_aggregate_scope_invalid")
    elif aggregate_id is not None:
        _fail("gate5_commission_aggregate_scope_invalid")
    for item in [
        *(detail_by_id[ref] for ref in detail_ids),
        *(
            [aggregate_by_id[aggregate_id]]
            if isinstance(aggregate_id, str) and aggregate_id in aggregate_by_id
            else []
        ),
    ]:
        _commission_money(item, expected_currency=value["currency"])
    return copy.deepcopy(value)


def _commission_selection_result(
    *,
    status: str,
    representation: str | None,
    selected: list[dict[str, Any]],
    scope: dict[str, Any],
    assertions: dict[str, Any],
    authority_binding: dict[str, Any],
    policy: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    amount = sum(
        (
            _commission_money(item, expected_currency=scope["currency"])
            for item in selected
        ),
        Decimal("0"),
    )
    selected_ids = [item["fact_id"] for item in selected]
    all_ids = [
        item["fact_id"]
        for item in [*assertions["detail"], *assertions["aggregate"]]
    ]
    return {
        "schema_version": GATE5_COMMISSION_EVIDENCE_SELECTION_SCHEMA_VERSION,
        "status": status,
        "terminals": [GATE5_COMMISSION_SELECTION_CONTRACT_TERMINAL],
        "required_scope_ref": scope["required_scope_ref"],
        "selected_representation": representation,
        "selected_fact_ids": selected_ids,
        "unselected_preserved_fact_ids": sorted(set(all_ids) - set(selected_ids)),
        "selected_value": (
            None
            if not selected
            else _money(amount, scope["currency"])
        ),
        "reason": reason,
        "coverage_evidence": copy.deepcopy(scope),
        "methodology_binding": {
            **copy.deepcopy(authority_binding),
            "selection_policy": copy.deepcopy(policy),
        },
        "source_assertions_preserved": True,
        "selected_once": len(selected_ids) == len(set(selected_ids)),
        "double_counted_fact_ids": [],
        "detail_aggregate_value_comparison_performed": False,
        "reconciliation": "not_performed",
        "tax_eligibility_status": "NOT_EVALUATED",
    }


def _commission_money(value: Any, *, expected_currency: str) -> Decimal:
    values = value.get("values") if isinstance(value, dict) else None
    if (
        not isinstance(values, dict)
        or not isinstance(values.get("amount"), str)
        or not isinstance(values.get("currency"), str)
        or values["currency"] != expected_currency
    ):
        _fail("gate5_commission_money_invalid")
    return abs(_decimal(values["amount"], field="commission_amount"))


def _same_source_transaction_row(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if (
        left["gate3_binding"].get("canonical_binding")
        != right["gate3_binding"].get("canonical_binding")
    ):
        return False
    left_target = left["annotation_target"]
    right_target = right["annotation_target"]
    table_kinds = {"table_row", "table_cell"}
    return (
        left_target.get("kind") in table_kinds
        and right_target.get("kind") in table_kinds
        and left_target.get("node_id") == right_target.get("node_id")
        and isinstance(left_target.get("row"), int)
        and left_target.get("row") == right_target.get("row")
    )


def _case_binding(context: Any) -> dict[str, str]:
    if not isinstance(context, ArtifactAccessContext):
        _fail("gate5_source_fact_trusted_context_required")
    if not context.user_id or not context.allow_private:
        _fail("gate5_source_fact_private_context_required")
    if context.case_id:
        return {"scope_kind": "case", "scope_id": context.case_id}
    if context.chat_id:
        return {"scope_kind": "chat", "scope_id": context.chat_id}
    _fail("gate5_source_fact_case_or_chat_scope_required")


def _decimal(value: Any, *, field: str, positive: bool = False) -> Decimal:
    pattern = _QUANTITY if positive else _MONEY
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        _fail("gate5_source_fact_decimal_invalid", field)
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise Gate5DeterministicSourceFactConsumptionError(
            "gate5_source_fact_decimal_invalid", field
        ) from exc
    if positive and result <= 0:
        _fail("gate5_source_fact_decimal_invalid", field)
    return result


def _money(amount: Decimal, currency: str) -> dict[str, str]:
    if amount != amount.quantize(Decimal("0.01")):
        _fail("gate5_source_fact_money_precision_invalid")
    return {
        "kind": "money",
        "amount": f"{amount:.2f}",
        "currency": currency,
    }


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _fail(code: str, field: str = "") -> None:
    raise Gate5DeterministicSourceFactConsumptionError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_ACQUISITION_BASIS_COVERAGE_CONTRACT_TERMINAL",
    "GATE5_ACQUISITION_BASIS_COVERAGE_SCHEMA_VERSION",
    "GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_SCHEMA_VERSION",
    "GATE5_AVAILABLE_SOURCE_FACT_ASSEMBLY_TERMINAL",
    "GATE5_COMMISSION_EVIDENCE_COVERAGE_SCHEMA_VERSION",
    "GATE5_COMMISSION_EVIDENCE_SELECTION_SCHEMA_VERSION",
    "GATE5_COMMISSION_SELECTION_CONTRACT_TERMINAL",
    "GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_RESULT_SCHEMA_VERSION",
    "GATE5_DETERMINISTIC_SOURCE_FACT_CONSUMPTION_TERMINAL",
    "GATE5_FIFO_WITHOUT_STORED_EVENT_TERMINAL",
    "GATE5_SOURCE_GRANULARITY_TERMINAL",
    "GATE5_SOURCE_FACT_ASSESSMENT_SCHEMA_VERSION",
    "GATE5_SOURCE_FACT_ASSERTIONS_TERMINAL",
    "Gate5DeterministicSourceFactConsumptionError",
    "Gate5DeterministicSourceFactConsumptionRuntime",
    "Gate5DeterministicSourceFactConsumptionRuntimeFactory",
    "gate5_source_fact_tax_model_inputs",
]
