"""Exact Definition-root income-group base and tax-settlement component."""

from __future__ import annotations

import copy
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import re
from typing import Any

from .gate5_income_group_tax_base import (
    GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
    Gate5IncomeGroupTaxBaseRuntime,
    Gate5IncomeGroupTaxBaseRuntimeFactory,
)
from .gate5_trusted_methodology import (
    GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID,
    GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthority,
    Gate5TrustedMethodologyAuthorityFactory,
    Gate5TrustedMethodologyError,
)


GATE5_INCOME_GROUP_TAX_RESULTS_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_income_group_tax_results_input_v0"
)
GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION = (
    "broker_reports_gate5_income_group_tax_results_component_v0"
)
GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_OWNER = (
    "Gate5DeclarationTaxSettlementRuntimeFactory.create.validate_component"
)
GATE5_INCOME_GROUP_TAX_RESULTS_DOMAIN_ID = "income_group_tax_results"
GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_FAMILY = "income_group_tax_results"
GATE5_INCOME_GROUP_TAX_RESULTS_OBLIGATION_REFS = (
    "obl_income_group_tax_base_results",
    "obl_income_group_tax_settlement_results",
)

FACTORY_REQUIRED = (
    "Gate5DeclarationTaxSettlementRuntimeFactory.create owns exact settlement validation",
    "Gate5IncomeGroupTaxBaseRuntimeFactory.create owns native tax-base validation",
    "Gate5TrustedMethodologyAuthorityFactory.create owns rate methodology resolution",
)
FORBIDDEN = (
    "caller formula, implicit rate, float arithmetic, LLM calculation or fallback",
    "raw Gate 4, SQL, ArtifactStore, source document or provider reads",
    "form projection, PROJECT, XML/PDF, generic rules engine or mutable registry",
)

_INPUT_KEYS = frozenset(
    {
        "schema_version",
        "methodology_ref",
        "scope_binding",
        "income_group_tax_base_models",
        "settlement_facts",
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
        "methodology_binding",
        "group_results",
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
_SETTLEMENT_FACT_KEYS = frozenset(
    {
        "income_group_model_sha256",
        "withheld_at_source",
        "material_benefit_withheld",
        "trade_fee_credit",
        "fixed_advance_credit",
        "foreign_tax_credit",
        "patent_credit",
    }
)
_OFFSET_NAMES = (
    "withheld_at_source",
    "material_benefit_withheld",
    "trade_fee_credit",
    "fixed_advance_credit",
    "foreign_tax_credit",
    "patent_credit",
)
_TAGGED_MONEY_KEYS = frozenset({"value", "provenance"})
_PROVENANCE_KEYS = frozenset(
    {"source_kind", "source_ref", "input_channel", "real_user_fact"}
)
_COMPLETENESS_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "coverage_kind",
        "scope_binding_sha256",
        "income_group_model_sha256s",
        "provenance",
    }
)
_METHODOLOGY_KEYS = frozenset(
    {
        "schema_version",
        "methodology_id",
        "methodology_version",
        "behavior",
        "legal_evidence",
    }
)
_BEHAVIOR_KEYS = frozenset(
    {
        "behavior_id",
        "input_contract_id",
        "output_contract_id",
        "applicability",
        "rate_schedule",
        "rounding",
        "settlement_inputs",
    }
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_AMOUNT = re.compile(r"^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Gate5DeclarationTaxSettlementError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5DeclarationTaxSettlementRuntimeFactory:
    @staticmethod
    def create() -> "Gate5DeclarationTaxSettlementRuntime":
        return Gate5DeclarationTaxSettlementRuntime(
            authority=Gate5TrustedMethodologyAuthorityFactory.create(),
            tax_base_runtime=Gate5IncomeGroupTaxBaseRuntimeFactory.create(),
        )


class Gate5DeclarationTaxSettlementRuntime:
    def __init__(
        self,
        *,
        authority: Gate5TrustedMethodologyAuthority,
        tax_base_runtime: Gate5IncomeGroupTaxBaseRuntime,
    ) -> None:
        self._authority = authority
        self._tax_base_runtime = tax_base_runtime

    def create_component(self, *, component_input: dict[str, Any]) -> dict[str, Any]:
        validated = self._validated_input(component_input)
        results = [
            _group_result(
                model=model,
                facts=validated["facts_by_model"][_canonical_sha256(model)],
                methodology=validated["methodology"],
                methodology_binding=validated["methodology_binding"],
            )
            for model in validated["models"]
        ]
        base = {
            "schema_version": GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION,
            "status": "complete",
            "domain_id": GATE5_INCOME_GROUP_TAX_RESULTS_DOMAIN_ID,
            "component_family": GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_FAMILY,
            "root_coverage": "exact_root_domain",
            "covered_obligation_refs": list(
                GATE5_INCOME_GROUP_TAX_RESULTS_OBLIGATION_REFS
            ),
            "scope_binding": copy.deepcopy(validated["scope"]),
            "methodology_binding": copy.deepcopy(validated["methodology_binding"]),
            "group_results": results,
            "input_snapshot": copy.deepcopy(component_input),
        }
        return {
            **base,
            "component_id": f"income-group-results:{_canonical_sha256(base)}",
        }

    def validate_component(
        self,
        *,
        component: dict[str, Any],
        scope_binding: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(component, dict) or set(component) != _COMPONENT_KEYS:
            _fail("gate5_income_group_results_component_invalid")
        expected = self.create_component(
            component_input=component.get("input_snapshot")
        )
        if component != expected:
            _fail("gate5_income_group_results_component_mismatch")
        if component["scope_binding"] != _validated_scope(scope_binding):
            _fail("gate5_income_group_results_scope_mismatch")
        return copy.deepcopy(component)

    def _validated_input(self, value: Any) -> dict[str, Any]:
        if (
            not isinstance(value, dict)
            or set(value) != _INPUT_KEYS
            or value.get("schema_version")
            != GATE5_INCOME_GROUP_TAX_RESULTS_INPUT_SCHEMA_VERSION
        ):
            _fail("gate5_income_group_results_input_invalid")
        scope = _validated_scope(value.get("scope_binding"))
        methodology_ref = value.get("methodology_ref")
        try:
            resolved = self._authority.resolve(methodology_ref)
        except Gate5TrustedMethodologyError as exc:
            raise Gate5DeclarationTaxSettlementError(
                "gate5_income_group_results_methodology_unavailable"
            ) from exc
        methodology = resolved["methodology"]
        _validated_methodology(methodology)
        models_raw = value.get("income_group_tax_base_models")
        if not isinstance(models_raw, list) or not models_raw:
            _fail("gate5_income_group_results_models_invalid")
        models = []
        model_hashes = []
        group_ids = set()
        for position, model in enumerate(models_raw):
            if not isinstance(model, dict):
                _fail("gate5_income_group_results_models_invalid", str(position))
            binding = model.get("methodology_binding")
            if not isinstance(binding, dict):
                _fail("gate5_income_group_results_model_invalid", str(position))
            native_ref = {
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": binding.get("methodology_id"),
                "methodology_version": binding.get("methodology_version"),
            }
            try:
                native = self._tax_base_runtime.validate_model(
                    methodology_ref=native_ref,
                    tax_base_model=model,
                )
            except ValueError as exc:
                raise Gate5DeclarationTaxSettlementError(
                    "gate5_income_group_results_model_invalid", str(position)
                ) from exc
            calculation_scope = native["calculation_scope"]
            group_id = calculation_scope["income_group_semantic"]
            if (
                calculation_scope["tax_period"] != scope["tax_period"]
                or calculation_scope["taxpayer_scope_ref"]
                != scope["taxpayer_scope_ref"]
                or group_id in group_ids
            ):
                _fail("gate5_income_group_results_model_scope_invalid", str(position))
            group_ids.add(group_id)
            models.append(native)
            model_hashes.append(_canonical_sha256(native))
        models_and_hashes = sorted(
            zip(models, model_hashes, strict=True),
            key=lambda item: item[0]["calculation_scope"]["income_group_semantic"],
        )
        models = [item[0] for item in models_and_hashes]
        model_hashes = [item[1] for item in models_and_hashes]
        facts_by_model = _settlement_facts(value.get("settlement_facts"), model_hashes)
        _completeness(
            value.get("completeness_evidence"),
            scope_binding_sha256=scope["scope_binding_sha256"],
            model_hashes=model_hashes,
        )
        applicability = methodology["behavior"]["applicability"]
        if any(
            model["calculation_scope"]["income_group_semantic"]
            != applicability["income_group_semantic"]
            or model["tax_base"]["value"]["currency"] != applicability["currency"]
            for model in models
        ):
            _fail("gate5_income_group_results_methodology_not_applicable")
        return {
            "scope": scope,
            "methodology": methodology,
            "methodology_binding": resolved["authority_binding"],
            "models": models,
            "facts_by_model": facts_by_model,
        }


def _validated_methodology(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != _METHODOLOGY_KEYS
        or value.get("schema_version")
        != GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_SCHEMA_VERSION
        or value.get("methodology_id")
        != GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_ID
        or value.get("methodology_version")
        != GATE5_INCOME_GROUP_TAX_SETTLEMENT_METHODOLOGY_VERSION
    ):
        _fail("gate5_income_group_results_methodology_invalid")
    behavior = value.get("behavior")
    if (
        not isinstance(behavior, dict)
        or set(behavior) != _BEHAVIOR_KEYS
        or behavior.get("behavior_id") != "income_group_tax_settlement_v1"
        or behavior.get("input_contract_id")
        != GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION
        or behavior.get("output_contract_id")
        != GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION
        or behavior.get("rounding")
        != "tax_amount_less_than_50_kopecks_discarded_50_or_more_to_full_ruble"
        or behavior.get("settlement_inputs") != list(_OFFSET_NAMES)
    ):
        _fail("gate5_income_group_results_methodology_invalid")
    applicability = behavior.get("applicability")
    if (
        not isinstance(applicability, dict)
        or applicability
        != {
            "tax_period": "2025",
            "taxpayer_status": "resident_individual",
            "income_group_semantic": "resident_securities_and_derivatives_non_iis",
            "income_group_code": "01",
            "currency": "RUB",
        }
        or not _valid_schedule(behavior.get("rate_schedule"))
    ):
        _fail("gate5_income_group_results_methodology_invalid")
    evidence = value.get("legal_evidence")
    evidence_by_ref = (
        {item.get("evidence_ref"): item for item in evidence}
        if isinstance(evidence, list)
        and all(isinstance(item, dict) for item in evidence)
        else {}
    )
    article_210 = evidence_by_ref.get("nk-rf-article-210-paragraph-6-2025", {})
    article_224 = evidence_by_ref.get("nk-rf-article-224-paragraph-1.1-2025", {})
    form_procedure = evidence_by_ref.get(
        "fns-order-ed-7-11-913-2025-procedure-paragraphs-6-46-55", {}
    )
    if (
        len(evidence_by_ref) != 3
        or article_210.get("authority_kind") != "tax_code_primary"
        or article_210.get("provision_ref")
        != "Tax Code article 210 paragraph 6"
        or article_210.get("source_url")
        != "https://nalog.garant.ru/fns/nk/6a3eaa02cea3fe2db1e9b04e275d1439/"
        or article_224.get("authority_kind") != "tax_code_primary"
        or article_224.get("provision_ref")
        != "Tax Code article 224 paragraph 1.1"
        or article_224.get("source_url")
        != "https://nalog.garant.ru/fns/nk/3cc8460732effc45905a5a1a311b451e/"
        or any(
            item.get("effective_tax_period") != "2025"
            for item in (article_210, article_224, form_procedure)
        )
        or any(
            item.get("capture_status") != "official_tax_code_page_verified"
            for item in (article_210, article_224)
        )
        or form_procedure.get("authority_kind") != "tax_authority_primary"
        or form_procedure.get("capture_status")
        != "downloaded_official_bytes_verified"
        or form_procedure.get("content_sha256")
        != "7bc11cad8d0465c03c834c50c7832fb2edc7291d9b4b161ef5b2c6cabdcb0fdc"
        or not form_procedure.get("source_url", "").startswith(
            "https://www.nalog.gov.ru/"
        )
    ):
        _fail("gate5_income_group_results_methodology_evidence_invalid")


def _valid_schedule(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 2:
        return False
    expected = [
        (None, "2400000.00", "0.00", "0.13"),
        ("2400000.00", None, "312000.00", "0.15"),
    ]
    return all(
        isinstance(row, dict)
        and set(row)
        == {
            "lower_bound_exclusive",
            "upper_bound_inclusive",
            "base_tax",
            "marginal_rate",
        }
        and (
            row["lower_bound_exclusive"],
            row["upper_bound_inclusive"],
            row["base_tax"],
            row["marginal_rate"],
        )
        == expected[position]
        for position, row in enumerate(value)
    )


def _settlement_facts(value: Any, model_hashes: list[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list) or len(value) != len(model_hashes):
        _fail("gate5_income_group_results_settlement_facts_invalid")
    result = {}
    for position, row in enumerate(value):
        if (
            not isinstance(row, dict)
            or set(row) != _SETTLEMENT_FACT_KEYS
            or row.get("income_group_model_sha256") not in model_hashes
            or row["income_group_model_sha256"] in result
        ):
            _fail("gate5_income_group_results_settlement_facts_invalid", str(position))
        result[row["income_group_model_sha256"]] = {
            name: _tagged_tax_money(row.get(name), name) for name in _OFFSET_NAMES
        }
    if set(result) != set(model_hashes):
        _fail("gate5_income_group_results_settlement_facts_invalid")
    return result


def _tagged_tax_money(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _TAGGED_MONEY_KEYS:
        _fail("gate5_income_group_results_settlement_fact_invalid", field)
    money = value.get("value")
    provenance = value.get("provenance")
    if (
        not isinstance(money, dict)
        or set(money) != {"kind", "amount", "currency"}
        or money.get("kind") != "money"
        or money.get("currency") != "RUB"
        or _AMOUNT.fullmatch(money.get("amount", "")) is None
        or Decimal(money["amount"]) != Decimal(money["amount"]).to_integral_value()
        or not isinstance(provenance, dict)
        or set(provenance) != _PROVENANCE_KEYS
        or provenance.get("source_kind")
        not in {
            "synthetic_proof_evidence",
            "authenticated_user_case_fact",
            "USER_ATTESTED_CASE_FACT",
        }
        or not _identifier(provenance.get("source_ref"))
        or provenance.get("input_channel") != "income_group_tax_settlement"
        or provenance.get("real_user_fact")
        is not (
            provenance.get("source_kind")
            in {"authenticated_user_case_fact", "USER_ATTESTED_CASE_FACT"}
        )
    ):
        _fail("gate5_income_group_results_settlement_fact_invalid", field)
    return copy.deepcopy(value)


def _completeness(
    value: Any,
    *,
    scope_binding_sha256: str,
    model_hashes: list[str],
) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != _COMPLETENESS_KEYS
        or value.get("schema_version")
        != "broker_reports_gate5_income_group_results_completeness_v0"
        or value.get("status") != "asserted_complete"
        or value.get("coverage_kind")
        != "all_applicable_income_groups_for_declaration_scope"
        or value.get("scope_binding_sha256") != scope_binding_sha256
        or value.get("income_group_model_sha256s") != model_hashes
    ):
        _fail("gate5_income_group_results_completeness_invalid")
    provenance = value.get("provenance")
    if (
        not isinstance(provenance, dict)
        or set(provenance) != _PROVENANCE_KEYS
        or provenance.get("source_kind")
        not in {
            "synthetic_proof_evidence",
            "authenticated_user_case_fact",
            "USER_ATTESTED_CASE_FACT",
        }
        or not _identifier(provenance.get("source_ref"))
        or provenance.get("input_channel") != "income_group_results_completeness"
        or provenance.get("real_user_fact")
        is not (
            provenance.get("source_kind")
            in {"authenticated_user_case_fact", "USER_ATTESTED_CASE_FACT"}
        )
    ):
        _fail("gate5_income_group_results_completeness_invalid")


def _group_result(
    *,
    model: dict[str, Any],
    facts: dict[str, Any],
    methodology: dict[str, Any],
    methodology_binding: dict[str, Any],
) -> dict[str, Any]:
    tax_base = Decimal(model["tax_base"]["value"]["amount"])
    schedule = methodology["behavior"]["rate_schedule"]
    band = next(
        row
        for row in schedule
        if row["upper_bound_inclusive"] is None
        or tax_base <= Decimal(row["upper_bound_inclusive"])
    )
    lower = Decimal(band["lower_bound_exclusive"] or "0.00")
    calculated_exact = Decimal(band["base_tax"]) + (
        (tax_base - lower) * Decimal(band["marginal_rate"])
    )
    calculated = calculated_exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    credits = sum(
        (Decimal(facts[name]["value"]["amount"]) for name in _OFFSET_NAMES),
        Decimal("0"),
    )
    payable = max(calculated - credits, Decimal("0"))
    refundable = max(credits - calculated, Decimal("0"))
    return {
        "income_group_semantic": model["calculation_scope"]["income_group_semantic"],
        "income_group_code": methodology["behavior"]["applicability"][
            "income_group_code"
        ],
        "tax_base_model_sha256": _canonical_sha256(model),
        "tax_base_model": copy.deepcopy(model),
        "calculated_tax": _money(calculated),
        "settlement_facts": copy.deepcopy(facts),
        "tax_payable": _money(payable),
        "tax_refundable": _money(refundable),
        "derivation": {
            "source_kind": "methodology_derived_tax_fact",
            "rate_band": copy.deepcopy(band),
            "unrounded_tax": f"{calculated_exact:.2f}",
            "rounding": methodology["behavior"]["rounding"],
            "methodology_projection_sha256": methodology_binding["projection_sha256"],
        },
    }


def _money(value: Decimal) -> dict[str, str]:
    return {"kind": "money", "amount": f"{value:.2f}", "currency": "RUB"}


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
        _fail("gate5_income_group_results_scope_invalid")
    base = {
        key: copy.deepcopy(value[key]) for key in value if key != "scope_binding_sha256"
    }
    if value["scope_binding_sha256"] != _canonical_sha256(base):
        _fail("gate5_income_group_results_scope_invalid")
    return copy.deepcopy(value)


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _canonical_sha256(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise Gate5DeclarationTaxSettlementError(
            "gate5_income_group_results_json_invalid"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _fail(code: str, field: str = "") -> None:
    raise Gate5DeclarationTaxSettlementError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_FAMILY",
    "GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_OWNER",
    "GATE5_INCOME_GROUP_TAX_RESULTS_COMPONENT_SCHEMA_VERSION",
    "GATE5_INCOME_GROUP_TAX_RESULTS_DOMAIN_ID",
    "GATE5_INCOME_GROUP_TAX_RESULTS_INPUT_SCHEMA_VERSION",
    "GATE5_INCOME_GROUP_TAX_RESULTS_OBLIGATION_REFS",
    "Gate5DeclarationTaxSettlementError",
    "Gate5DeclarationTaxSettlementRuntime",
    "Gate5DeclarationTaxSettlementRuntimeFactory",
]
