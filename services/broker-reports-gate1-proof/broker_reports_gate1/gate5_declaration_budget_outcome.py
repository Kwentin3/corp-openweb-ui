"""Exact declaration-level budget disposition over validated tax settlements."""

from __future__ import annotations

import copy
from decimal import Decimal
import hashlib
import json
import re
from typing import Any

from .gate5_declaration_filing_context import (
    Gate5FilingAndPartyIdentityRuntime,
    Gate5FilingAndPartyIdentityRuntimeFactory,
)
from .gate5_declaration_tax_settlement import (
    Gate5DeclarationTaxSettlementRuntime,
    Gate5DeclarationTaxSettlementRuntimeFactory,
)


GATE5_DECLARATION_BUDGET_DISPOSITION_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_budget_disposition_input_v0"
)
GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION = (
    "broker_reports_gate5_declaration_budget_disposition_component_v0"
)
GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_OWNER = (
    "Gate5DeclarationBudgetOutcomeRuntimeFactory.create.validate_component"
)
GATE5_DECLARATION_BUDGET_DISPOSITION_DOMAIN_ID = "declaration_budget_disposition"
GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_FAMILY = "declaration_budget_disposition"
GATE5_DECLARATION_BUDGET_DISPOSITION_OBLIGATION_REFS = (
    "obl_declaration_budget_disposition",
)

FACTORY_REQUIRED = (
    "Gate5DeclarationBudgetOutcomeRuntimeFactory.create owns budget disposition",
    "Gate5FilingAndPartyIdentityRuntimeFactory.create owns filing-context validation",
    "Gate5DeclarationTaxSettlementRuntimeFactory.create owns settlement validation",
)
FORBIDDEN = (
    "tax recalculation, implicit zero, caller disposition kind or unvalidated allocation",
    "Gate 4, SQL, ArtifactStore, source/provider read, LLM or user interaction",
    "refund election, PROJECT, XML/PDF, workflow, DB or mutable registry",
)

_INPUT_KEYS = frozenset(
    {
        "schema_version",
        "scope_binding",
        "filing_component",
        "income_group_results_component",
        "allocation_evidence",
    }
)
_COMPONENT_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "component_id",
        "domain_id",
        "component_family",
        "root_coverage",
        "covered_obligation_refs",
        "scope_binding",
        "disposition",
        "input_snapshot",
    }
)
_SCOPE_KEYS = frozenset(
    {
        "schema_version",
        "scope_ref",
        "taxpayer_scope_ref",
        "tax_period",
        "authenticated_user_ref",
        "case_id",
        "normalization_run_ref",
        "scope_binding_sha256",
    }
)
_EVIDENCE_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "source_ref",
        "budget_allocation_ref",
        "kbk",
        "oktmo",
        "simplified_procedure_returned_or_credited_amount",
        "case_id",
        "tax_period",
        "input_channel",
        "real_user_fact",
    }
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_KBK = re.compile(r"^[0-9]{20}$")
_OKTMO = re.compile(r"^(?:[0-9]{8}|[0-9]{11})$")
_AMOUNT = re.compile(r"^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Gate5DeclarationBudgetOutcomeError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5DeclarationBudgetOutcomeRuntimeFactory:
    @staticmethod
    def create() -> "Gate5DeclarationBudgetOutcomeRuntime":
        return Gate5DeclarationBudgetOutcomeRuntime(
            filing_runtime=Gate5FilingAndPartyIdentityRuntimeFactory.create(),
            settlement_runtime=Gate5DeclarationTaxSettlementRuntimeFactory.create(),
        )


class Gate5DeclarationBudgetOutcomeRuntime:
    def __init__(
        self,
        *,
        filing_runtime: Gate5FilingAndPartyIdentityRuntime,
        settlement_runtime: Gate5DeclarationTaxSettlementRuntime,
    ) -> None:
        self._filing_runtime = filing_runtime
        self._settlement_runtime = settlement_runtime

    def create_component(self, *, component_input: dict[str, Any]) -> dict[str, Any]:
        validated = self._validated_input(component_input)
        settlements = validated["income"]["group_results"]
        calculated = sum(
            (Decimal(row["calculated_tax"]["amount"]) for row in settlements),
            Decimal("0"),
        )
        credits = sum(
            (
                Decimal(fact["value"]["amount"])
                for row in settlements
                for fact in row["settlement_facts"].values()
            ),
            Decimal("0"),
        )
        payment = sum(
            (Decimal(row["tax_payable"]["amount"]) for row in settlements),
            Decimal("0"),
        )
        refund = sum(
            (Decimal(row["tax_refundable"]["amount"]) for row in settlements),
            Decimal("0"),
        )
        reduction = min(calculated, credits)
        kind = (
            "additional_payment"
            if payment > 0
            else "refund_available"
            if refund > 0
            else "balanced"
        )
        filing = validated["filing"]["input_snapshot"]["filing_instance"]
        allocations = (
            [
                {
                    "allocation_kind": "tax_payment",
                    "destination_tax_authority_ref": filing[
                        "destination_tax_authority_ref"
                    ],
                    "budget_allocation_ref": validated["evidence"][
                        "budget_allocation_ref"
                    ],
                    "kbk": validated["evidence"]["kbk"],
                    "oktmo": validated["evidence"]["oktmo"],
                    "amount": _money(payment),
                }
            ]
            if payment > 0
            else []
        )
        disposition = {
            "kind": kind,
            "calculated_tax": _money(calculated),
            "credited_or_withheld_amount": _money(credits),
            "reduction_amount": _money(reduction),
            "payment_or_additional_payment_amount": _money(payment),
            "refund_available_amount": _money(refund),
            "simplified_procedure_returned_or_credited_amount": copy.deepcopy(
                validated["evidence"][
                    "simplified_procedure_returned_or_credited_amount"
                ]
            ),
            "budget_allocations": allocations,
            "derivation": {
                "source_kind": "declaration_filing_context",
                "income_group_results_component_id": validated["income"][
                    "component_id"
                ],
                "filing_component_id": validated["filing"]["component_id"],
                "allocation_evidence": copy.deepcopy(validated["evidence"]),
            },
        }
        base = {
            "schema_version": (
                GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION
            ),
            "status": "complete",
            "domain_id": GATE5_DECLARATION_BUDGET_DISPOSITION_DOMAIN_ID,
            "component_family": (GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_FAMILY),
            "root_coverage": "exact_root_domain",
            "covered_obligation_refs": list(
                GATE5_DECLARATION_BUDGET_DISPOSITION_OBLIGATION_REFS
            ),
            "scope_binding": copy.deepcopy(validated["scope"]),
            "disposition": disposition,
            "input_snapshot": copy.deepcopy(component_input),
        }
        return {
            **base,
            "component_id": f"budget-disposition:{_canonical_sha256(base)}",
        }

    def validate_component(
        self,
        *,
        component: dict[str, Any],
        scope_binding: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(component, dict) or set(component) != _COMPONENT_KEYS:
            _fail("gate5_budget_disposition_component_invalid")
        expected = self.create_component(
            component_input=component.get("input_snapshot")
        )
        if component != expected:
            _fail("gate5_budget_disposition_component_mismatch")
        if component["scope_binding"] != _validated_scope(scope_binding):
            _fail("gate5_budget_disposition_scope_mismatch")
        return copy.deepcopy(component)

    def _validated_input(self, value: Any) -> dict[str, Any]:
        if (
            not isinstance(value, dict)
            or set(value) != _INPUT_KEYS
            or value.get("schema_version")
            != GATE5_DECLARATION_BUDGET_DISPOSITION_INPUT_SCHEMA_VERSION
        ):
            _fail("gate5_budget_disposition_input_invalid")
        scope = _validated_scope(value.get("scope_binding"))
        try:
            filing = self._filing_runtime.validate_component(
                component=value.get("filing_component"),
                scope_binding=scope,
            )
            income = self._settlement_runtime.validate_component(
                component=value.get("income_group_results_component"),
                scope_binding=scope,
            )
        except ValueError as exc:
            raise Gate5DeclarationBudgetOutcomeError(
                "gate5_budget_disposition_dependency_invalid"
            ) from exc
        evidence = value.get("allocation_evidence")
        if (
            not isinstance(evidence, dict)
            or set(evidence) != _EVIDENCE_KEYS
            or (
                evidence.get("schema_version"),
                evidence.get("status"),
                evidence.get("real_user_fact"),
            )
            not in {
                (
                    "broker_reports_gate5_synthetic_case_evidence_v0",
                    "synthetic_proof_evidence",
                    False,
                ),
                (
                    "broker_reports_gate5_owner_case_evidence_v1",
                    "owner_verified_evidence",
                    False,
                ),
            }
            or not _identifier(evidence.get("source_ref"))
            or not _identifier(evidence.get("budget_allocation_ref"))
            or _KBK.fullmatch(evidence.get("kbk", "")) is None
            or _OKTMO.fullmatch(evidence.get("oktmo", "")) is None
            or not _money_value(
                evidence.get("simplified_procedure_returned_or_credited_amount")
            )
            or evidence.get("case_id") != scope["case_id"]
            or evidence.get("tax_period") != scope["tax_period"]
            or evidence.get("input_channel") != "declaration_budget_disposition"
        ):
            _fail("gate5_budget_disposition_evidence_invalid")
        return {
            "scope": scope,
            "filing": filing,
            "income": income,
            "evidence": copy.deepcopy(evidence),
        }


def _money(value: Decimal) -> dict[str, str]:
    return {"kind": "money", "amount": f"{value:.2f}", "currency": "RUB"}


def _money_value(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"kind", "amount", "currency"}
        and value.get("kind") == "money"
        and value.get("currency") == "RUB"
        and _AMOUNT.fullmatch(value.get("amount", "")) is not None
    )


def _validated_scope(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _SCOPE_KEYS
        or not all(
            _identifier(value.get(key))
            for key in (
                "scope_ref",
                "taxpayer_scope_ref",
                "tax_period",
                "authenticated_user_ref",
                "case_id",
                "normalization_run_ref",
            )
        )
        or not isinstance(value.get("schema_version"), str)
        or _SHA256.fullmatch(value.get("scope_binding_sha256", "")) is None
    ):
        _fail("gate5_budget_disposition_scope_invalid")
    base = {
        key: copy.deepcopy(value[key]) for key in value if key != "scope_binding_sha256"
    }
    if value["scope_binding_sha256"] != _canonical_sha256(base):
        _fail("gate5_budget_disposition_scope_invalid")
    return copy.deepcopy(value)


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str, field: str = "") -> None:
    raise Gate5DeclarationBudgetOutcomeError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_FAMILY",
    "GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_OWNER",
    "GATE5_DECLARATION_BUDGET_DISPOSITION_COMPONENT_SCHEMA_VERSION",
    "GATE5_DECLARATION_BUDGET_DISPOSITION_DOMAIN_ID",
    "GATE5_DECLARATION_BUDGET_DISPOSITION_INPUT_SCHEMA_VERSION",
    "GATE5_DECLARATION_BUDGET_DISPOSITION_OBLIGATION_REFS",
    "Gate5DeclarationBudgetOutcomeError",
    "Gate5DeclarationBudgetOutcomeRuntime",
    "Gate5DeclarationBudgetOutcomeRuntimeFactory",
]
