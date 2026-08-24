"""Exact taxable-income source component over validated income-group results."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from decimal import Decimal
from typing import Any

from .gate5_declaration_tax_settlement import (
    Gate5DeclarationTaxSettlementRuntime,
    Gate5DeclarationTaxSettlementRuntimeFactory,
)


GATE5_TAXABLE_INCOME_SOURCE_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_taxable_income_by_source_input_v0"
)
GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION = (
    "broker_reports_gate5_taxable_income_by_source_component_v0"
)
GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_OWNER = (
    "Gate5DeclarationIncomeSourcesRuntimeFactory.create.validate_component"
)
GATE5_TAXABLE_INCOME_SOURCE_DOMAIN_ID = "taxable_income_by_source"
GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_FAMILY = "taxable_income_by_source"
GATE5_TAXABLE_INCOME_SOURCE_OBLIGATION_REFS = (
    "obl_russian_source_taxable_income",
    "obl_foreign_source_taxable_income_and_foreign_tax",
)

FACTORY_REQUIRED = (
    "Gate5DeclarationIncomeSourcesRuntimeFactory.create owns exact source validation",
    "Gate5DeclarationTaxSettlementRuntimeFactory.create owns income-result validation",
)
FORBIDDEN = (
    "source inference from transport, missing-source default, fake foreign-tax zero",
    "Gate 4, SQL, ArtifactStore, provider, LLM or direct source-document read",
    "generic source classifier, rule engine, PROJECT, XML/PDF or product activation",
)

_INPUT_KEYS = frozenset(
    {
        "schema_version",
        "scope_binding",
        "income_group_results_component",
        "source_entries",
        "completeness_evidence",
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
        "source_entries",
        "obligation_resolutions",
        "completeness_evidence",
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
_ENTRY_KEYS = frozenset(
    {
        "source_ref",
        "income_group_semantic",
        "jurisdiction_kind",
        "jurisdiction_code",
        "income_kind",
        "source_party",
        "gross_income",
        "taxable_income",
        "tax_agent",
        "foreign_tax",
        "provenance",
    }
)
_SOURCE_PARTY_KEYS = frozenset(
    {"party_kind", "display_name", "inn", "kpp", "oktmo"}
)
_TAX_AGENT_KEYS = frozenset({"status", "withheld_tax"})
_PROVENANCE_KEYS = frozenset(
    {"source_kind", "source_ref", "input_channel", "real_user_fact"}
)
_COMPLETENESS_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "coverage_kind",
        "scope_binding_sha256",
        "income_group_results_component_id",
        "source_refs",
        "provenance",
    }
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_COUNTRY_CODE = re.compile(r"^[A-Z]{2}$")
_INN_LEGAL_ENTITY = re.compile(r"^[0-9]{10}$")
_KPP = re.compile(r"^[0-9]{4}[0-9A-Z]{2}[0-9]{3}$")
_OKTMO = re.compile(r"^(?:[0-9]{8}|[0-9]{11})$")
_AMOUNT = re.compile(r"^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Gate5DeclarationIncomeSourcesError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5DeclarationIncomeSourcesRuntimeFactory:
    @staticmethod
    def create() -> "Gate5DeclarationIncomeSourcesRuntime":
        return Gate5DeclarationIncomeSourcesRuntime(
            settlement_runtime=Gate5DeclarationTaxSettlementRuntimeFactory.create()
        )


class Gate5DeclarationIncomeSourcesRuntime:
    def __init__(
        self,
        *,
        settlement_runtime: Gate5DeclarationTaxSettlementRuntime,
    ) -> None:
        self._settlement_runtime = settlement_runtime

    def create_component(self, *, component_input: dict[str, Any]) -> dict[str, Any]:
        validated = self._validated_input(component_input)
        base = {
            "schema_version": GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION,
            "status": "complete",
            "domain_id": GATE5_TAXABLE_INCOME_SOURCE_DOMAIN_ID,
            "component_family": GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_FAMILY,
            "root_coverage": "exact_root_domain",
            "covered_obligation_refs": list(
                GATE5_TAXABLE_INCOME_SOURCE_OBLIGATION_REFS
            ),
            "scope_binding": copy.deepcopy(validated["scope"]),
            "source_entries": copy.deepcopy(validated["entries"]),
            "obligation_resolutions": [
                {
                    "obligation_ref": obligation_ref,
                    "state": (
                        "RESOLVED"
                        if any(
                            item["jurisdiction_kind"] == jurisdiction_kind
                            for item in validated["entries"]
                        )
                        else "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
                    ),
                    "real_world_absence_asserted": False,
                }
                for obligation_ref, jurisdiction_kind in (
                    ("obl_russian_source_taxable_income", "russian_source"),
                    (
                        "obl_foreign_source_taxable_income_and_foreign_tax",
                        "foreign_source",
                    ),
                )
            ],
            "completeness_evidence": copy.deepcopy(validated["completeness"]),
            "input_snapshot": copy.deepcopy(component_input),
        }
        return {
            **base,
            "component_id": f"taxable-income-sources:{_canonical_sha256(base)}",
        }

    def validate_component(
        self,
        *,
        component: dict[str, Any],
        scope_binding: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(component, dict) or set(component) != _COMPONENT_KEYS:
            _fail("gate5_income_sources_component_invalid")
        expected = self.create_component(
            component_input=component.get("input_snapshot")
        )
        if component != expected:
            _fail("gate5_income_sources_component_mismatch")
        if component["scope_binding"] != _validated_scope(scope_binding):
            _fail("gate5_income_sources_scope_mismatch")
        return copy.deepcopy(component)

    def _validated_input(self, value: Any) -> dict[str, Any]:
        if (
            not isinstance(value, dict)
            or set(value) != _INPUT_KEYS
            or value.get("schema_version")
            != GATE5_TAXABLE_INCOME_SOURCE_INPUT_SCHEMA_VERSION
        ):
            _fail("gate5_income_sources_input_invalid")
        scope = _validated_scope(value.get("scope_binding"))
        try:
            income = self._settlement_runtime.validate_component(
                component=value.get("income_group_results_component"),
                scope_binding=scope,
            )
        except ValueError as exc:
            raise Gate5DeclarationIncomeSourcesError(
                "gate5_income_sources_dependency_invalid"
            ) from exc
        entries_raw = value.get("source_entries")
        if not isinstance(entries_raw, list) or not entries_raw:
            _fail("gate5_income_sources_entries_invalid")
        results = {row["income_group_semantic"]: row for row in income["group_results"]}
        entries = []
        seen = set()
        accounted = {
            group_id: {
                "gross": Decimal("0.00"),
                "taxable": Decimal("0.00"),
                "withheld": Decimal("0.00"),
            }
            for group_id in results
        }
        for position, entry in enumerate(entries_raw):
            if not isinstance(entry, dict) or set(entry) != _ENTRY_KEYS:
                _fail("gate5_income_sources_entry_invalid", str(position))
            source_ref = entry.get("source_ref")
            group_id = entry.get("income_group_semantic")
            result = results.get(group_id)
            jurisdiction = entry.get("jurisdiction_kind")
            jurisdiction_code = entry.get("jurisdiction_code")
            foreign_tax = entry.get("foreign_tax")
            if (
                not _identifier(source_ref)
                or source_ref in seen
                or result is None
                or jurisdiction not in {"russian_source", "foreign_source"}
                or not isinstance(jurisdiction_code, str)
                or _COUNTRY_CODE.fullmatch(jurisdiction_code) is None
                or not _identifier(entry.get("income_kind"))
                or (
                    jurisdiction == "russian_source"
                    and (jurisdiction_code != "RU" or foreign_tax is not None)
                )
                or (
                    jurisdiction == "foreign_source"
                    and (jurisdiction_code == "RU" or not _foreign_tax(foreign_tax))
                )
            ):
                _fail("gate5_income_sources_entry_invalid", str(position))
            seen.add(source_ref)
            gross = _money(entry.get("gross_income"), "gross_income")
            taxable = _money(entry.get("taxable_income"), "taxable_income")
            source_party = entry.get("source_party")
            if (
                not isinstance(source_party, dict)
                or set(source_party) != _SOURCE_PARTY_KEYS
                or source_party.get("party_kind") != "organization"
                or not isinstance(source_party.get("display_name"), str)
                or not source_party["display_name"].strip()
                or len(source_party["display_name"]) > 1000
                or _INN_LEGAL_ENTITY.fullmatch(source_party.get("inn", "")) is None
                or _KPP.fullmatch(source_party.get("kpp", "")) is None
                or _OKTMO.fullmatch(source_party.get("oktmo", "")) is None
            ):
                _fail("gate5_income_sources_source_party_invalid", str(position))
            tax_agent = entry.get("tax_agent")
            if not isinstance(tax_agent, dict) or set(tax_agent) != _TAX_AGENT_KEYS:
                _fail("gate5_income_sources_tax_agent_invalid", str(position))
            withheld = _money(tax_agent.get("withheld_tax"), "withheld_tax")
            if tax_agent.get("status") not in {"present", "absent"} or (
                tax_agent["status"] == "absent" and withheld["amount"] != "0.00"
            ):
                _fail("gate5_income_sources_tax_agent_invalid", str(position))
            accounted[group_id]["gross"] += Decimal(gross["amount"])
            accounted[group_id]["taxable"] += Decimal(taxable["amount"])
            accounted[group_id]["withheld"] += Decimal(withheld["amount"])
            provenance = _provenance(entry.get("provenance"), "taxable_income_source")
            entries.append(
                {
                    **copy.deepcopy(entry),
                    "gross_income": gross,
                    "taxable_income": taxable,
                    "source_party": copy.deepcopy(source_party),
                    "tax_agent": {**copy.deepcopy(tax_agent), "withheld_tax": withheld},
                    "provenance": provenance,
                }
            )
        entries.sort(key=lambda item: item["source_ref"])
        if {item["income_group_semantic"] for item in entries} != set(results):
            _fail("gate5_income_sources_group_accounting_invalid")
        for group_id, totals in accounted.items():
            result = results[group_id]
            model = result["tax_base_model"]
            if (
                totals["gross"] != Decimal(model["total_income"]["value"]["amount"])
                or totals["taxable"]
                != Decimal(model["taxable_income"]["value"]["amount"])
                or totals["withheld"]
                != Decimal(
                    result["settlement_facts"]["withheld_at_source"]["value"]["amount"]
                )
            ):
                _fail("gate5_income_sources_value_mismatch", group_id)
        completeness = value.get("completeness_evidence")
        if (
            not isinstance(completeness, dict)
            or set(completeness) != _COMPLETENESS_KEYS
            or completeness.get("schema_version")
            != "broker_reports_gate5_taxable_income_source_completeness_v0"
            or completeness.get("status") != "asserted_complete"
            or completeness.get("coverage_kind")
            != "all_taxable_income_sources_for_declaration_scope"
            or completeness.get("scope_binding_sha256") != scope["scope_binding_sha256"]
            or completeness.get("income_group_results_component_id")
            != income["component_id"]
            or completeness.get("source_refs")
            != [item["source_ref"] for item in entries]
        ):
            _fail("gate5_income_sources_completeness_invalid")
        completeness = copy.deepcopy(completeness)
        completeness["provenance"] = _provenance(
            completeness.get("provenance"), "taxable_income_source_completeness"
        )
        return {
            "scope": scope,
            "entries": entries,
            "completeness": completeness,
        }


def _money(value: Any, field: str) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or set(value) != {"kind", "amount", "currency"}
        or value.get("kind") != "money"
        or value.get("currency") != "RUB"
        or _AMOUNT.fullmatch(value.get("amount", "")) is None
    ):
        _fail("gate5_income_sources_money_invalid", field)
    return copy.deepcopy(value)


def _foreign_tax(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"paid_tax", "authority_ref", "evidence_ref"}
        and _money(value.get("paid_tax"), "foreign_tax") is not None
        and _identifier(value.get("authority_ref"))
        and _identifier(value.get("evidence_ref"))
    )


def _provenance(value: Any, input_channel: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _PROVENANCE_KEYS
        or value.get("source_kind")
        not in {
            "synthetic_proof_evidence",
            "external_authoritative_evidence",
            "current_canonical_source_fact",
        }
        or not _identifier(value.get("source_ref"))
        or value.get("input_channel") != input_channel
        or value.get("real_user_fact") is not False
    ):
        _fail("gate5_income_sources_provenance_invalid", input_channel)
    return copy.deepcopy(value)


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
        _fail("gate5_income_sources_scope_invalid")
    base = {
        key: copy.deepcopy(value[key]) for key in value if key != "scope_binding_sha256"
    }
    if value["scope_binding_sha256"] != _canonical_sha256(base):
        _fail("gate5_income_sources_scope_invalid")
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
    raise Gate5DeclarationIncomeSourcesError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_FAMILY",
    "GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_OWNER",
    "GATE5_TAXABLE_INCOME_SOURCE_COMPONENT_SCHEMA_VERSION",
    "GATE5_TAXABLE_INCOME_SOURCE_DOMAIN_ID",
    "GATE5_TAXABLE_INCOME_SOURCE_INPUT_SCHEMA_VERSION",
    "GATE5_TAXABLE_INCOME_SOURCE_OBLIGATION_REFS",
    "Gate5DeclarationIncomeSourcesError",
    "Gate5DeclarationIncomeSourcesRuntime",
    "Gate5DeclarationIncomeSourcesRuntimeFactory",
]
