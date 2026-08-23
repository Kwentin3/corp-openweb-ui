from __future__ import annotations

import ast
import inspect
from importlib import resources
import json
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE,
    GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE_SHA256,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_SCHEMA_VERSION,
    GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    ArtifactStoreFactory,
    Gate5CombinedRequirementCheckError,
    Gate5SecuritiesDisposalTaxModelError,
    Gate5SecuritiesDisposalTaxModelRuntime,
    Gate5SecuritiesDisposalTaxModelRuntimeFactory,
    Gate5SupplementalFactRuntimeFactory,
    Gate5TrustedMethodologyAuthorityFactory,
    build_retention_policy,
)
from broker_reports_gate1 import (
    gate5_securities_disposal_tax_model as tax_model_module,
)
from broker_reports_gate1.gate5_securities_disposal_tax_model import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)
import test_broker_reports_gate5_methodology_calculation as calculation_fixtures


def test_first_declaration_driven_tax_model_replays_and_projects_appendix8(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, store, context = calculation_fixtures._representative_case(
        tmp_path,
        monkeypatch,
    )
    acquisition = calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="acquisition-cost-required",
        fact_key="acquisition_cost",
        amount="70.00",
    )
    transaction = calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="transaction-expense-required",
        fact_key="transaction_expense",
        amount="2.00",
    )
    gate4_before = calculation_fixtures._financial_case(
        store=store,
        context=context,
    )
    supplemental_before = calculation_fixtures._supplemental_refs(store, context)
    methodology_before = _resource_bytes(
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE
    )
    projection_before = _resource_bytes(GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE)

    first = _runtime(store).run(
        methodology_ref=_methodology_ref(),
        resolved_inputs=_resolved_inputs(),
        context=context,
    )
    reopened_store = ArtifactStoreFactory(config).create()
    replayed = _runtime(reopened_store).run(
        methodology_ref=_methodology_ref(),
        resolved_inputs=_resolved_inputs(),
        context=context,
    )

    assert replayed == first
    model = first["tax_model"]
    assert model["schema_version"] == (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_SCHEMA_VERSION
    )
    assert model["status"] == "complete"
    assert model["operation"]["category"]["value"] == (
        "organized_market_securities_outside_iis"
    )
    assert model["category_gross_income"]["value"] == _money("100.00")
    assert model["related_expenses"]["total"] == _money("72.00")
    assert model["allowable_expenses"]["total"] == _money("72.00")
    assert model["loss_treatment"]["value"] == "none"
    assert model["calculation_scope"]["completeness"]["value"] == (
        "complete_for_category_in_proof"
    )
    assert model["methodology_binding"]["resource_sha256"] == (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE_SHA256
    )

    gross_sources = model["category_gross_income"]["sources"]
    assert {item["source"]["source_kind"] for item in gross_sources} == {
        "financial_case"
    }
    related = {
        item["component_id"]: item for item in model["related_expenses"]["components"]
    }
    assert related["acquisition_cost"]["sources"][0]["source"] == (
        calculation_fixtures._supplemental_source(acquisition["fact"])
    )
    assert related["transaction_expense"]["sources"][0]["source"] == (
        calculation_fixtures._supplemental_source(transaction["fact"])
    )
    assert {item["status"] for item in model["allowable_expenses"]["decisions"]} == {
        "allowed"
    }
    assert all(
        item["legal_evidence_refs"]
        and item["methodology_projection_sha256"]
        == model["methodology_binding"]["projection_sha256"]
        for item in model["allowable_expenses"]["decisions"]
    )
    assert len(model["proof_assumptions"]) == 13
    assert {item["input_path"] for item in model["proof_assumptions"]} >= {
        "operation_properties.organized_market_status",
        "tax_context.loss_treatment",
        "scope.scope_completeness",
        "expense_evidence.transaction_expense.documented",
    }

    assert first["declaration_semantics"] == {
        "schema_version": "broker_reports_gate5_declaration_projection_proof_input_v0",
        "operation_category": "organized_market_securities_outside_iis",
        "operation_category_gross_income": _consumer_money("100.00"),
        "related_expenses": _consumer_money("72.00"),
        "allowable_expenses": _consumer_money("72.00"),
        "loss_treatment": "none",
    }
    assert first["declaration_fragment"]["attributes"] == {
        "ВидОпер": "01",
        "ДохСовОпер": "100.00",
        "РасхРеалЦБ": "72.00",
        "РасхУмДохОпер": "72.00",
        "ПризУчетУбыт": "0",
    }
    serialized_model = json.dumps(model, ensure_ascii=False, sort_keys=True)
    for declaration_owned_literal in (
        "ВидОпер",
        "ДохСовОпер",
        "РасхРеалЦБ",
        "РасхУмДохОпер",
        "ПризУчетУбыт",
    ):
        assert declaration_owned_literal not in serialized_model
    assert '"tax_base"' not in serialized_model
    assert '"net_result"' not in serialized_model

    assert (
        calculation_fixtures._financial_case(
            store=reopened_store,
            context=context,
        )
        == gate4_before
    )
    assert (
        calculation_fixtures._supplemental_refs(reopened_store, context)
        == supplemental_before
    )
    assert (
        _resource_bytes(GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE)
        == methodology_before
    )
    assert _resource_bytes(GATE5_DECLARATION_PROJECTION_SPEC_RESOURCE) == (
        projection_before
    )


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    (
        (
            lambda value: value["operation_properties"].pop("organized_market_status"),
            "gate5_tax_model_classification_prerequisite_missing",
        ),
        (
            lambda value: value["tax_context"].pop("loss_treatment"),
            "gate5_tax_model_loss_treatment_missing",
        ),
        (
            lambda value: value["scope"]["scope_completeness"].update(
                value="incomplete"
            ),
            "gate5_tax_model_scope_incomplete",
        ),
    ),
)
def test_unresolved_classification_loss_or_scope_blocks_tax_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutate,
    expected_code: str,
) -> None:
    _config, store, context = _complete_case(tmp_path, monkeypatch)
    resolved_inputs = _resolved_inputs()
    mutate(resolved_inputs)

    with pytest.raises(Gate5SecuritiesDisposalTaxModelError) as caught:
        _runtime(store).run(
            methodology_ref=_methodology_ref(),
            resolved_inputs=resolved_inputs,
            context=context,
        )

    assert caught.value.code == expected_code


def test_missing_expense_methodology_inputs_fail_closed_without_relation_inference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, store, context = calculation_fixtures._representative_case(
        tmp_path,
        monkeypatch,
    )

    with pytest.raises(Gate5SecuritiesDisposalTaxModelError) as caught:
        _runtime(store).run_operation(
            methodology_ref={
                **_methodology_ref(),
                "methodology_version": (
                    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION
                ),
            },
            resolved_inputs={
                **_resolved_inputs(),
                "scope": {},
            },
            context=context,
        )

    assert caught.value.code == "gate5_tax_model_inputs_not_satisfied"
    source = inspect.getsource(tax_model_module)
    assert "related_financial_case" not in source
    assert "run_operation_from_related_events" not in source


def test_related_but_unproven_expense_is_not_automatically_allowable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, store, context = _complete_case(tmp_path, monkeypatch)
    resolved_inputs = _resolved_inputs()
    resolved_inputs["expense_evidence"]["transaction_expense"]["documented"][
        "value"
    ] = False

    result = _runtime(store).run(
        methodology_ref=_methodology_ref(),
        resolved_inputs=resolved_inputs,
        context=context,
    )

    model = result["tax_model"]
    assert model["related_expenses"]["total"] == _money("72.00")
    assert model["allowable_expenses"]["total"] == _money("70.00")
    transaction = next(
        item
        for item in model["allowable_expenses"]["decisions"]
        if item["component_id"] == "transaction_expense"
    )
    assert transaction["status"] == "not_allowed_unproven"
    assert transaction["failed_prerequisites"] == ["documented"]
    assert result["declaration_semantics"]["related_expenses"] == (
        _consumer_money("72.00")
    )
    assert result["declaration_semantics"]["allowable_expenses"] == (
        _consumer_money("70.00")
    )


def test_ambiguous_sources_mixed_currency_and_unknown_behavior_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _config, ambiguous_store, ambiguous_context = (
        calculation_fixtures._representative_case(tmp_path / "ambiguous", monkeypatch)
    )
    for amount in ("70.00", "71.00"):
        calculation_fixtures._put_money(
            store=ambiguous_store,
            context=ambiguous_context,
            requirement_ref="acquisition-cost-required",
            fact_key="acquisition_cost",
            amount=amount,
        )
    calculation_fixtures._put_money(
        store=ambiguous_store,
        context=ambiguous_context,
        requirement_ref="transaction-expense-required",
        fact_key="transaction_expense",
        amount="2.00",
    )
    with pytest.raises(Gate5CombinedRequirementCheckError) as ambiguous:
        _runtime(ambiguous_store).run(
            methodology_ref=_methodology_ref(),
            resolved_inputs=_resolved_inputs(),
            context=ambiguous_context,
        )
    assert ambiguous.value.code == ("gate5_combined_requirement_supplemental_ambiguous")

    _config, mixed_store, mixed_context = calculation_fixtures._representative_case(
        tmp_path / "mixed",
        monkeypatch,
    )
    calculation_fixtures._put_money(
        store=mixed_store,
        context=mixed_context,
        requirement_ref="acquisition-cost-required",
        fact_key="acquisition_cost",
        amount="70.00",
    )
    _put_money_with_currency(
        store=mixed_store,
        context=mixed_context,
        requirement_ref="transaction-expense-required",
        fact_key="transaction_expense",
        amount="2.00",
        currency="USD",
    )
    with pytest.raises(Gate5SecuritiesDisposalTaxModelError) as mixed:
        _runtime(mixed_store).run(
            methodology_ref=_methodology_ref(),
            resolved_inputs=_resolved_inputs(),
            context=mixed_context,
        )
    assert mixed.value.code == "gate5_tax_model_currency_mismatch"

    _config, behavior_store, behavior_context = _complete_case(
        tmp_path / "behavior",
        monkeypatch,
    )
    monkeypatch.setattr(
        tax_model_module,
        "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_BEHAVIOR_ID",
        "behavior-disabled-for-proof",
    )
    with pytest.raises(Gate5SecuritiesDisposalTaxModelError) as unknown:
        _runtime(behavior_store).run(
            methodology_ref=_methodology_ref(),
            resolved_inputs=_resolved_inputs(),
            context=behavior_context,
        )
    assert unknown.value.code == "gate5_tax_model_behavior_unsupported"


def test_new_methodology_is_hash_pinned_by_existing_trusted_authority() -> None:
    resolved = Gate5TrustedMethodologyAuthorityFactory.create().resolve(
        _methodology_ref()
    )

    assert resolved["authority_binding"]["resource_sha256"] == (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE_SHA256
    )
    assert resolved["methodology"]["methodology_id"] == (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID
    )
    assert {
        item["authority_kind"] for item in resolved["methodology"]["legal_evidence"]
    } == {
        "official_legal_text",
        "tax_authority_primary",
    }


def test_factory_composes_existing_owners_without_form_or_storage_logic() -> None:
    factory_source = inspect.getsource(
        Gate5SecuritiesDisposalTaxModelRuntimeFactory.create
    )
    runtime_source = inspect.getsource(Gate5SecuritiesDisposalTaxModelRuntime)
    module_source = inspect.getsource(tax_model_module)
    tree = ast.parse(module_source)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert "Gate5SecuritiesDisposalTaxModelRuntimeFactory.create" in FACTORY_REQUIRED
    assert "Gate5TrustedMethodologyAuthorityFactory.create()" in factory_source
    assert "Gate5SupplementalFactDiscoveryRuntimeFactory(" in factory_source
    assert (
        "Gate5DeterministicSourceFactConsumptionRuntimeFactory(" in factory_source
    )
    assert "Gate5DeclarationProjectionRuntimeFactory.create()" in factory_source
    assert "self._authority.resolve(methodology_ref)" in runtime_source
    assert "self._require_discovery().check(" in runtime_source
    assert "self._require_projector().project(" in runtime_source
    assert "direct Gate 4" in FORBIDDEN[0]
    assert imports == {
        "__future__",
        "copy",
        "decimal",
        "re",
        "typing",
        "artifact_models",
        "gate5_combined_requirement_check",
            "gate5_declaration_projection",
            "gate5_deterministic_source_fact_consumption",
            "gate5_supplemental_fact_discovery",
        "gate5_trusted_methodology",
    }
    for forbidden_path in (
        "Gate4FinancialCaseRuntimeFactory",
        "Gate5SupplementalFactRuntimeFactory",
        "ArtifactResolver",
        "ArtifactStoreFactory",
        "sqlite3",
        "requests",
        "httpx",
        "model_client",
        "chat_completion",
    ):
        assert forbidden_path not in module_source
    for declaration_owned_literal in (
        "ВидОпер",
        "ДохСовОпер",
        "РасхРеалЦБ",
        "РасхУмДохОпер",
        "ПризУчетУбыт",
        '"01"',
    ):
        assert declaration_owned_literal not in module_source
    assert ".put(" not in runtime_source


def _complete_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    config, store, context = calculation_fixtures._representative_case(
        tmp_path,
        monkeypatch,
    )
    calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="acquisition-cost-required",
        fact_key="acquisition_cost",
        amount="70.00",
    )
    calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="transaction-expense-required",
        fact_key="transaction_expense",
        amount="2.00",
    )
    return config, store, context


def _runtime(store) -> Gate5SecuritiesDisposalTaxModelRuntime:
    return Gate5SecuritiesDisposalTaxModelRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": (
            GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION
        ),
    }


def _resolved_inputs() -> dict:
    def tagged(
        value, source_ref: str, input_channel: str, *, source_kind="proof_assumption"
    ) -> dict:
        return {
            "value": value,
            "provenance": {
                "source_kind": source_kind,
                "source_ref": source_ref,
                "input_channel": input_channel,
            },
        }

    operation = "resolved_operation_property"
    tax_context = "minimal_tax_context"
    scope = "scope_binding"
    expense = "expense_eligibility_evidence"
    return {
        "schema_version": (GATE5_SECURITIES_DISPOSAL_RESOLVED_INPUTS_SCHEMA_VERSION),
        "subject_ref": "security-disposal-1",
        "operation_properties": {
            "operation_kind": tagged("sale", "proof-operation-kind", operation),
            "organized_market_status": tagged(
                "organized_market",
                "proof-organized-market-status",
                operation,
            ),
            "iis_status": tagged("outside_iis", "proof-iis-status", operation),
        },
        "tax_context": {
            "tax_period": tagged("2025", "proof-tax-period", tax_context),
            "residency": tagged(
                "resident_individual",
                "residency-classification:proof",
                tax_context,
                source_kind="methodology_derived_result",
            ),
            "exemption_applicability": tagged(
                "not_applicable", "proof-exemption", tax_context
            ),
            "loss_treatment": tagged("none", "proof-loss-treatment", tax_context),
        },
        "scope": {
            "scope_completeness": tagged(
                "complete_for_category_in_proof",
                "proof-complete-category-scope",
                scope,
            )
        },
        "expense_evidence": {
            component_id: {
                "actually_incurred": tagged(
                    True, f"proof-{component_id}-incurred", expense
                ),
                "documented": tagged(True, f"proof-{component_id}-documented", expense),
                "related_to_operation": tagged(
                    True, f"proof-{component_id}-related", expense
                ),
            }
            for component_id in ("acquisition_cost", "transaction_expense")
        },
    }


def _put_money_with_currency(
    *,
    store,
    context,
    requirement_ref: str,
    fact_key: str,
    amount: str,
    currency: str,
) -> dict:
    return (
        Gate5SupplementalFactRuntimeFactory(
            store=store,
            retention_policy=build_retention_policy(mode="synthetic_dev"),
        )
        .create()
        .put(
            supplemental_input={
                "schema_version": GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
                "requirement_ref": requirement_ref,
                "subject_ref": "security-disposal-1",
                "fact_key": fact_key,
                "value": {
                    "kind": "money",
                    "amount": amount,
                    "currency": currency,
                },
            },
            context=context,
        )
    )


def _resource_bytes(resource_name: str) -> bytes:
    return resources.files("broker_reports_gate1").joinpath(resource_name).read_bytes()


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}


def _consumer_money(amount: str) -> dict[str, str]:
    return {"amount": amount, "currency": "RUB"}
