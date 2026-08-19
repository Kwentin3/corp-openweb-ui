from __future__ import annotations

import ast
import copy
from importlib import resources
import inspect
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_RESOURCE,
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_RESOURCE_SHA256,
    GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION,
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
    GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_SCHEMA_VERSION,
    GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5SecuritiesDisposalTaxModelRuntimeFactory,
    Gate5TaxPeriodCategoryAggregationError,
    Gate5TaxPeriodCategoryAggregationRuntimeFactory,
    Gate5TrustedMethodologyAuthorityFactory,
    build_retention_policy,
)
from broker_reports_gate1 import gate5_tax_period_category_aggregation as module
from broker_reports_gate1.gate5_tax_period_category_aggregation import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)
import test_broker_reports_gate4_sql_materialization as gate4_fixtures
import test_broker_reports_gate5_methodology_calculation as calculation_fixtures
import test_broker_reports_gate5_securities_disposal_tax_model as model_fixtures


def test_two_operation_scope_aggregates_only_with_exact_completeness_and_projects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    model_a, context_a = _operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="a",
        gross="100.00",
        acquisition="70.00",
        fee="2.00",
    )
    model_b, context_b = _operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="b",
        gross="50.00",
        acquisition="28.00",
        fee="2.00",
        fee_documented=False,
    )
    model_c, _ = _operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="c",
        gross="25.00",
        acquisition="9.00",
        fee="1.00",
    )
    assert model_a["schema_version"] == (
        GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
    )
    assert model_a["operation_scope"]["aggregation_kind"] == ("single_operation_only")
    assert "completeness" not in model_a["operation_scope"]

    members = _members(model_a, model_b)
    scope = _scope()
    runtime = Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
    binding = runtime.describe_scope(scope=scope, members=members)
    evidence = _completeness(binding["scope_binding_sha256"])
    gate4_before = {
        "a": _gate4_facts(store, context_a),
        "b": _gate4_facts(store, context_b),
    }

    complete = runtime.run(
        scope=scope,
        members=members,
        completeness_evidence=evidence,
    )
    replayed = runtime.run(
        scope=scope,
        members=list(reversed(members)),
        completeness_evidence=evidence,
    )
    incomplete = runtime.run(
        scope=scope,
        members=members,
        completeness_evidence=None,
    )

    assert replayed == complete
    assert complete["status"] == "complete"
    category = complete["category_tax_model"]
    assert category["schema_version"] == (
        GATE5_TAX_PERIOD_CATEGORY_TAX_MODEL_SCHEMA_VERSION
    )
    assert category["operation_category"]["value"] == (
        "organized_market_securities_outside_iis"
    )
    assert category["category_gross_income"]["value"] == _money("150.00")
    assert category["related_expenses"]["value"] == _money("102.00")
    assert category["allowable_expenses"]["value"] == _money("100.00")
    assert category["loss_treatment"]["value"] == "none"
    assert category["calculation_scope"]["completeness"] == evidence
    assert [item["operation_ref"] for item in category["member_operations"]] == [
        "operation-a",
        "operation-b",
    ]
    assert complete["declaration_fragment"]["attributes"] == {
        "ВидОпер": "01",
        "ДохСовОпер": "150.00",
        "РасхРеалЦБ": "102.00",
        "РасхУмДохОпер": "100.00",
        "ПризУчетУбыт": "0",
    }
    gross_contributions = category["category_gross_income"]["derivation"][
        "contributions"
    ]
    assert [item["value"]["amount"] for item in gross_contributions] == [
        "100.00",
        "50.00",
    ]
    assert {
        source["source"]["source_kind"]
        for item in gross_contributions
        for source in item["source_evidence"]
    } == {"financial_case"}
    assert {
        source["source"]["source_kind"]
        for item in category["allowable_expenses"]["derivation"]["contributions"]
        for component in item["source_evidence"]
        for source in component["sources"]
    } == {"supplemental_fact"}

    assert incomplete["status"] == "incomplete_scope"
    assert incomplete["known_values"]["gross_income"]["value"] == _money("150.00")
    assert incomplete["category_tax_model"] is None
    assert incomplete["declaration_semantics"] is None
    assert incomplete["declaration_fragment"] is None

    changed_members = [*members, _member("operation-c", "case-c", model_c)]
    with pytest.raises(Gate5TaxPeriodCategoryAggregationError) as exc_info:
        runtime.run(
            scope=scope,
            members=changed_members,
            completeness_evidence=evidence,
        )
    assert exc_info.value.code == "gate5_tax_period_completeness_binding_mismatch"
    assert _gate4_facts(store, context_a) == gate4_before["a"]
    assert _gate4_facts(store, context_b) == gate4_before["b"]


def test_single_operation_scope_uses_same_path_and_exact_completeness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    model, _ = _operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="singleton",
        gross="100.00",
        acquisition="70.00",
        fee="2.00",
    )
    members = [_member("operation-singleton", "case-singleton", model)]
    scope = _scope()
    runtime = Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()
    binding = runtime.describe_scope(scope=scope, members=members)

    incomplete = runtime.run(
        scope=scope,
        members=members,
        completeness_evidence=None,
    )
    complete = runtime.run(
        scope=scope,
        members=members,
        completeness_evidence=_completeness(binding["scope_binding_sha256"]),
    )

    assert binding["members"] == [
        {
            "operation_ref": "operation-singleton",
            "source_scope_ref": "case-singleton",
            "operation_model_sha256": binding["members"][0]["operation_model_sha256"],
        }
    ]
    assert incomplete["status"] == "incomplete_scope"
    assert incomplete["known_values"]["gross_income"]["value"] == _money("100.00")
    assert incomplete["category_tax_model"] is None
    assert incomplete["declaration_fragment"] is None

    assert complete["status"] == "complete"
    category = complete["category_tax_model"]
    assert category["member_operations"] == binding["members"]
    assert category["category_gross_income"]["value"] == _money("100.00")
    assert category["related_expenses"]["value"] == _money("72.00")
    assert category["allowable_expenses"]["value"] == _money("72.00")
    assert runtime.validate_category_model(tax_model=category) == category
    assert complete["declaration_fragment"]["attributes"] == {
        "ВидОпер": "01",
        "ДохСовОпер": "100.00",
        "РасхРеалЦБ": "72.00",
        "РасхУмДохОпер": "72.00",
        "ПризУчетУбыт": "0",
    }

    changed_identity = [_member("operation-singleton-updated", "case-singleton", model)]
    with pytest.raises(Gate5TaxPeriodCategoryAggregationError) as exc_info:
        runtime.run(
            scope=scope,
            members=changed_identity,
            completeness_evidence=_completeness(binding["scope_binding_sha256"]),
        )
    assert exc_info.value.code == "gate5_tax_period_completeness_binding_mismatch"


def test_zero_operation_scope_remains_invalid() -> None:
    runtime = Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()

    with pytest.raises(Gate5TaxPeriodCategoryAggregationError) as exc_info:
        runtime.describe_scope(scope=_scope(), members=[])

    assert exc_info.value.code == "gate5_tax_period_members_invalid"


def test_period_category_currency_loss_and_methodology_mismatch_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    model_a, _ = _operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="a",
        gross="100.00",
        acquisition="70.00",
        fee="2.00",
    )
    model_b, _ = _operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="b",
        gross="50.00",
        acquisition="28.00",
        fee="2.00",
    )
    runtime = Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()

    mutations = []
    period = copy.deepcopy(model_b)
    period["operation_scope"]["tax_period"]["value"] = "2024"
    mutations.append((period, "gate5_tax_period_member_period_mismatch"))
    category = copy.deepcopy(model_b)
    category["operation"]["category"]["value"] = "other_category"
    mutations.append((category, "gate5_tax_period_member_category_mismatch"))
    currency = copy.deepcopy(model_b)
    _replace_model_currency(currency, "USD")
    mutations.append((currency, "gate5_tax_period_currency_mismatch"))
    loss = copy.deepcopy(model_b)
    loss["loss_treatment"]["value"] = "carryforward"
    mutations.append((loss, "gate5_tax_period_loss_treatment_incompatible"))
    incomplete = copy.deepcopy(model_b)
    incomplete["status"] = "incomplete"
    mutations.append((incomplete, "gate5_tax_period_operation_model_incomplete"))
    unknown = copy.deepcopy(model_b)
    unknown["methodology_binding"]["methodology_version"] = "2099.0-unknown"
    mutations.append((unknown, "gate5_tax_period_methodology_unknown"))

    for mutated, expected in mutations:
        with pytest.raises(Gate5TaxPeriodCategoryAggregationError) as exc_info:
            runtime.describe_scope(
                scope=_scope(),
                members=[
                    _member("operation-a", "case-a", model_a),
                    _member("operation-b", "case-b", mutated),
                ],
            )
        assert exc_info.value.code == expected


def test_duplicate_or_ambiguous_operation_identity_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    model_a, _ = _operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="a",
        gross="100.00",
        acquisition="70.00",
        fee="2.00",
    )
    model_b, _ = _operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="b",
        gross="50.00",
        acquisition="28.00",
        fee="2.00",
    )
    runtime = Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()

    cases = (
        (
            [
                _member("operation-a", "case-a", model_a),
                _member("operation-a", "case-b", model_b),
            ],
            "gate5_tax_period_duplicate_operation_ref",
        ),
        (
            [
                _member("operation-a", "case-a", model_a),
                _member("operation-b", "case-b", model_a),
            ],
            "gate5_tax_period_duplicate_operation_model",
        ),
        (
            [
                _member("operation-a", "case-a", model_a),
                _member("", "case-b", model_b),
            ],
            "gate5_tax_period_operation_identity_ambiguous",
        ),
    )
    for members, expected in cases:
        with pytest.raises(Gate5TaxPeriodCategoryAggregationError) as exc_info:
            runtime.describe_scope(scope=_scope(), members=members)
        assert exc_info.value.code == expected


def test_operation_methodology_is_new_hash_pinned_version() -> None:
    resolved = Gate5TrustedMethodologyAuthorityFactory.create().resolve(
        _operation_methodology_ref()
    )
    raw = (
        resources.files("broker_reports_gate1")
        .joinpath(GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_RESOURCE)
        .read_bytes()
    )
    assert resolved["authority_binding"]["resource_sha256"] == (
        GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_RESOURCE_SHA256
    )
    assert resolved["methodology"]["behavior"]["applicability_rule"][
        "required_values"
    ].keys() >= {"tax_period", "organized_market_status"}
    assert (
        "scope_completeness"
        not in resolved["methodology"]["behavior"]["applicability_rule"][
            "required_values"
        ]
    )
    assert len(raw) > 0


def test_aggregation_factory_reuses_authority_models_and_projector_only() -> None:
    factory_source = inspect.getsource(
        Gate5TaxPeriodCategoryAggregationRuntimeFactory.create
    )
    runtime_source = inspect.getsource(module.Gate5TaxPeriodCategoryAggregationRuntime)
    module_source = inspect.getsource(module)
    imports: set[str] = set()
    for node in ast.walk(ast.parse(module_source)):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create" in FACTORY_REQUIRED
    assert "Gate5TrustedMethodologyAuthorityFactory.create()" in factory_source
    assert "Gate5DeclarationProjectionRuntimeFactory.create()" in factory_source
    assert "self._authority" in runtime_source
    assert "self._projector.project(" in runtime_source
    assert "len(members) == 1" not in module_source
    assert "special_singleton" not in module_source
    assert "raw Gate 4" in FORBIDDEN[0]
    assert imports == {
        "__future__",
        "copy",
        "decimal",
        "hashlib",
        "json",
        "re",
        "typing",
        "gate5_declaration_projection",
        "gate5_securities_disposal_tax_model",
        "gate5_trusted_methodology",
    }
    for forbidden in (
        "Gate4FinancialCaseRuntimeFactory",
        "Gate5SupplementalFactRuntimeFactory",
        "ArtifactStoreFactory",
        "ArtifactResolver",
        "sqlite3",
        "requests",
        "httpx",
        "model_client",
        "chat_completion",
        "CASE_COMPLETE_FOR_CURRENT_INPUT_SET ==",
    ):
        assert forbidden not in module_source
    for declaration_literal in (
        "ВидОпер",
        "ДохСовОпер",
        "РасхРеалЦБ",
        "РасхУмДохОпер",
        "ПризУчетУбыт",
    ):
        assert declaration_literal not in module_source


def _store(tmp_path: Path):
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()


def _operation_model(
    *,
    store,
    monkeypatch: pytest.MonkeyPatch,
    ref: str,
    gross: str,
    acquisition: str,
    fee: str,
    fee_documented: bool = True,
) -> tuple[dict, ArtifactAccessContext]:
    gross_source = gross.replace(".", ",")
    monkeypatch.setitem(
        gate4_fixtures._FACT_SPEC_BY_TYPE,
        "SECURITY_DISPOSAL",
        (
            ("date", "11.02.2025"),
            ("asset", f"ASSET-{ref.upper()}"),
            ("quantity", "1"),
            ("amount", gross_source),
            ("currency", "RUB"),
            ("unit_price", gross_source),
        ),
    )
    monkeypatch.setitem(
        gate4_fixtures._SOURCE_ROW_BY_TYPE,
        "SECURITY_DISPOSAL",
        (f"Продажа|11.02.2025|ASSET-{ref.upper()}|1|{gross_source}|RUB|{gross_source}"),
    )
    context = ArtifactAccessContext(
        user_id="g5-tax-period-user",
        normalization_run_id=f"g5-tax-period-run-{ref}",
        case_id=f"g5-tax-period-case-{ref}",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    gate4_fixtures._publish_document(
        store=store,
        context=context,
        document_id=f"g5-tax-period-document-{ref}",
        financial_types=("SECURITY_DISPOSAL",),
        sidecar_artifact_id=f"g3-v2-g5-tax-period-{ref}",
        created_at="2026-08-09T18:00:00+00:00",
    )
    Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().rebuild_case(context=context)
    calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="acquisition-cost-required",
        fact_key="acquisition_cost",
        amount=acquisition,
    )
    calculation_fixtures._put_money(
        store=store,
        context=context,
        requirement_ref="transaction-expense-required",
        fact_key="transaction_expense",
        amount=fee,
    )
    resolved_inputs = model_fixtures._resolved_inputs()
    resolved_inputs["scope"] = {}
    resolved_inputs["expense_evidence"]["transaction_expense"]["documented"][
        "value"
    ] = fee_documented
    result = (
        Gate5SecuritiesDisposalTaxModelRuntimeFactory(
            store=store,
            read_enabled=True,
            retention_policy=build_retention_policy(mode="synthetic_dev"),
        )
        .create()
        .run_operation(
            methodology_ref=_operation_methodology_ref(),
            resolved_inputs=resolved_inputs,
            context=context,
        )
    )
    assert set(result) == {"schema_version", "status", "tax_model"}
    assert result["status"] == "modeled"
    return result["tax_model"], context


def _operation_methodology_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": (
            GATE5_SECURITIES_DISPOSAL_OPERATION_METHODOLOGY_VERSION
        ),
    }


def _scope() -> dict[str, str]:
    return {
        "schema_version": GATE5_TAX_PERIOD_CATEGORY_SCOPE_SCHEMA_VERSION,
        "scope_ref": "taxpayer-proof-2025-organized-securities",
        "taxpayer_scope_ref": "taxpayer-proof-1",
        "tax_period": "2025",
        "operation_category": "organized_market_securities_outside_iis",
    }


def _members(model_a: dict, model_b: dict) -> list[dict]:
    return [
        _member("operation-a", "case-a", model_a),
        _member("operation-b", "case-b", model_b),
    ]


def _member(operation_ref: str, source_scope_ref: str, tax_model: dict) -> dict:
    return {
        "operation_ref": operation_ref,
        "source_scope_ref": source_scope_ref,
        "tax_model": copy.deepcopy(tax_model),
    }


def _completeness(scope_binding_sha256: str) -> dict:
    return {
        "schema_version": GATE5_TAX_PERIOD_COMPLETENESS_EVIDENCE_SCHEMA_VERSION,
        "status": "asserted_complete",
        "coverage_kind": "all_operations_in_taxpayer_category_period_scope",
        "scope_binding_sha256": scope_binding_sha256,
        "provenance": {
            "source_kind": "user_verified_fact",
            "source_ref": "user-confirmed-complete-2025-securities-scope",
            "input_channel": "tax_period_scope_completeness",
        },
    }


def _gate4_facts(store, context: ArtifactAccessContext) -> list[dict]:
    return (
        Gate4FinancialCaseRuntimeFactory(
            store=store,
            read_enabled=True,
        )
        .create()
        .list_by_financial_type(
            context=context,
            financial_type="SECURITY_DISPOSAL",
        )
    )


def _replace_model_currency(model: dict, currency: str) -> None:
    model["gross_income"]["value"]["currency"] = currency
    for section in ("related_expenses", "allowable_expenses"):
        model[section]["total"]["currency"] = currency
        for component in model[section]["components"]:
            component["value"]["currency"] = currency


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}
