from __future__ import annotations

import copy
import hashlib
import inspect
import json
from dataclasses import replace
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    Gate4FinancialCaseRuntimeFactory,
    build_retention_policy,
)
from broker_reports_gate1 import gate5_declaration_scope_resolution as module
from broker_reports_gate1.artifact_models import ArtifactStoreError
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION,
    GATE5_DECLARATION_SCOPE_HUMAN_ANSWER_SCHEMA_VERSION,
    GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION,
    GATE5_DECLARATION_SCOPE_SEMANTICS,
    GATE5_DECLARATION_SCOPE_SCHEMA_VERSION,
    Gate5DeclarationScopeResolutionError,
    Gate5DeclarationScopeResolutionRuntimeFactory,
)
from broker_reports_gate1.gate5_full_declaration_definition import (
    Gate5FullDeclarationDefinitionError,
    Gate5TrustedFullDeclarationDefinitionAuthorityFactory,
)
from broker_reports_gate1.gate5_securities_disposal_tax_model import (
    GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION,
)
import test_broker_reports_gate5_tax_period_category_aggregation as aggregation_fixtures
import test_broker_reports_gate4_sql_materialization as gate4_fixtures


def test_definition_drives_every_domain_and_existing_component_is_positive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model = _proof_case(tmp_path, monkeypatch)
    runtime = _runtime(store)

    receipt = runtime.resolve(
        definition_ref=_definition_ref(),
        scope=_scope(context),
        typed_component_evidence=[_component_evidence(model)],
        assertion_refs=[],
        context=context,
    )

    trusted_domains = [
        item["domain_id"]
        for item in Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create().definition()[
            "domains"
        ]
    ]
    assert [item["domain_id"] for item in receipt["domains"]] == trusted_domains
    assert len(receipt["domains"]) == 11
    assert receipt["status"] == "SCOPE_RESOLVED_FOR_SUPPLIED_CASE"
    assert receipt["scope_semantics"] == GATE5_DECLARATION_SCOPE_SEMANTICS
    states = {item["domain_id"]: item for item in receipt["domains"]}
    assert {
        states[domain_id]["state"]
        for domain_id in (
            "filing_and_party_identity",
            "declaration_budget_disposition",
            "income_group_tax_results",
            "financial_investment_results",
        )
    } == {"APPLICABLE"}
    assert states["financial_investment_results"]["resolution_route"] == "EXECUTE"
    assert states["refundable_amount_disposal"]["state"] == (
        "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
    )
    assert all(
        states[domain_id]["state"] != "NOT_APPLICABLE" for domain_id in trusted_domains
    )
    assert receipt["gate4_binding"]["boundary"] == (
        "Gate4FinancialCaseRuntimeFactory.create"
    )
    assert receipt["gate4_binding"]["status"] == ("CASE_COMPLETE_FOR_CURRENT_INPUT_SET")
    assert receipt["unresolved_domains"] == []
    assert receipt["missing_source_requests"] == []
    assert receipt["human_residual"] is None
    assert receipt["first_downstream_blocker"] == {
        "domain_id": "filing_and_party_identity",
        "component_family": "filing_and_party_identity",
        "component_availability": "missing",
        "reason": "required_component_missing",
    }
    assert runtime.validate_receipt(receipt=receipt, context=context) == receipt


def test_no_positive_case_evidence_does_not_activate_conditional_domains(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, _model = _proof_case(tmp_path, monkeypatch)

    receipt = _runtime(store).resolve(
        definition_ref=_definition_ref(),
        scope=_scope(context),
        typed_component_evidence=[],
        assertion_refs=[],
        context=context,
    )

    mandatory = [row for row in receipt["domains"] if row["mode"] == "always"]
    conditional = [
        row for row in receipt["domains"] if row["mode"] == "conditional"
    ]
    assert receipt["status"] == "SCOPE_RESOLVED_FOR_SUPPLIED_CASE"
    assert mandatory and all(row["state"] == "APPLICABLE" for row in mandatory)
    assert conditional and all(
        row["state"] == "NOT_ACTIVATED_FOR_SUPPLIED_CASE" for row in conditional
    )
    assert receipt["human_residual"] is None
    assert receipt["scope_semantics"]["real_world_taxpayer_absence_asserted"] is False


def test_observed_incomplete_fact_creates_source_bound_blocker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, fact = _missing_source_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    indication = {
        "schema_version": (
            GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION
        ),
        "component_contract_id": (
            GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
        ),
        "source_fact_id": fact["fact_id"],
        "source_fact_sha256": _sha256(fact),
        "missing_role_names": ["amount"],
    }

    receipt = runtime.resolve(
        definition_ref=_definition_ref(),
        scope=_scope(context),
        typed_component_evidence=[],
        assertion_refs=[],
        missing_source_indications=[indication],
        context=context,
    )

    row = _row(receipt, "financial_investment_results")
    request = receipt["missing_source_requests"][0]
    assert receipt["status"] == "SCOPE_INCOMPLETE_FOR_SUPPLIED_CASE"
    assert row["state"] == "UNRESOLVED"
    assert row["resolution_route"] == "ACQUIRE"
    assert row["evidence_bindings"][0]["polarity"] == "blocking"
    assert request["source_fact_id"] == fact["fact_id"]
    assert request["source_fact_sha256"] == _sha256(fact)
    assert request["missing_role_names"] == ["amount"]
    assert request["action"] == "provide_missing_source_or_values"
    assert receipt["human_residual"] is None
    assert runtime.validate_receipt(receipt=receipt, context=context) == receipt

    swapped = copy.deepcopy(receipt)
    financial = _row(swapped, "financial_investment_results")
    gift = _row(swapped, "gift_income")
    gift["evidence_bindings"] = financial["evidence_bindings"]
    gift["state"] = "UNRESOLVED"
    gift["resolution_route"] = "ACQUIRE"
    financial["evidence_bindings"] = []
    financial["state"] = "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
    financial["resolution_route"] = "RESOLVE"
    for changed_row in (financial, gift):
        decision_base = {
            key: copy.deepcopy(value)
            for key, value in changed_row.items()
            if key != "decision_sha256"
        }
        changed_row["decision_sha256"] = _sha256(decision_base)
    swapped["unresolved_domains"] = ["gift_income"]
    receipt_base = {
        key: copy.deepcopy(value)
        for key, value in swapped.items()
        if key != "receipt_sha256"
    }
    swapped["receipt_sha256"] = _sha256(receipt_base)
    assert (
        _error_code(
            lambda: runtime.validate_receipt(receipt=swapped, context=context)
        )
        == "gate5_declaration_scope_missing_source_accounting_invalid"
    )


def test_policy_bound_no_becomes_negative_and_opposed_answers_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model = _proof_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    first = runtime.resolve(
        definition_ref=_definition_ref(),
        scope=_scope(context),
        typed_component_evidence=[_component_evidence(model)],
        assertion_refs=[],
        context=context,
    )

    denial = runtime.submit_human_answer(
        receipt=first,
        human_answer=_answer("no"),
        context=context,
        domain_id="refundable_amount_disposal",
    )
    denied = runtime.resolve(
        definition_ref=_definition_ref(),
        scope=_scope(context),
        typed_component_evidence=[_component_evidence(model)],
        assertion_refs=[denial["assertion_ref"]],
        context=context,
    )
    denied_row = _row(denied, "refundable_amount_disposal")
    assert denied_row["state"] == "NOT_APPLICABLE"
    assert denied_row["resolution_route"] == "ACQUIRE"
    assert denied["human_residual"] is None

    affirmation = runtime.submit_human_answer(
        receipt=first,
        human_answer=_answer("yes"),
        context=context,
        domain_id="refundable_amount_disposal",
    )
    conflicted = runtime.resolve(
        definition_ref=_definition_ref(),
        scope=_scope(context),
        typed_component_evidence=[_component_evidence(model)],
        assertion_refs=[denial["assertion_ref"], affirmation["assertion_ref"]],
        context=context,
    )
    conflict_row = _row(conflicted, "refundable_amount_disposal")
    assert conflict_row["state"] == "CONFLICT"
    assert {item["polarity"] for item in conflict_row["evidence_bindings"]} == {
        "positive",
        "negative",
    }
    assert conflicted["conflicts"] == ["refundable_amount_disposal"]
    assert conflicted["human_residual"] is None


def test_definition_policy_rejects_component_for_wrong_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model = _proof_case(tmp_path, monkeypatch)
    evidence = _component_evidence(model)
    evidence["component_contract_id"] = (
        "broker_reports_gate5_income_group_tax_base_model_v0"
    )

    assert (
        _error_code(
            lambda: _runtime(store).resolve(
                definition_ref=_definition_ref(),
                scope=_scope(context),
                typed_component_evidence=[evidence],
                assertion_refs=[],
                context=context,
            )
        )
        == "gate5_declaration_scope_policy_evidence_incompatible"
    )


def test_stale_component_source_and_scope_mismatch_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model = _proof_case(tmp_path, monkeypatch)
    stale = copy.deepcopy(model)
    source = _financial_sources(stale)[0]
    source["matches"][0]["fact_id"] = "stale-financial-fact"

    assert (
        _error_code(
            lambda: _runtime(store).resolve(
                definition_ref=_definition_ref(),
                scope=_scope(context),
                typed_component_evidence=[_component_evidence(stale)],
                assertion_refs=[],
                context=context,
            )
        )
        == "gate5_declaration_scope_component_financial_source_stale"
    )

    foreign_scope = _scope(context)
    foreign_scope["tax_period"] = "2024"
    assert (
        _error_code(
            lambda: _runtime(store).resolve(
                definition_ref=_definition_ref(),
                scope=foreign_scope,
                typed_component_evidence=[],
                assertion_refs=[],
                context=context,
            )
        )
        == "gate5_declaration_scope_scope_binding_invalid"
    )


def test_wrong_trusted_definition_hash_fails_before_resolution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, _model = _proof_case(tmp_path, monkeypatch)
    definition_ref = _definition_ref()
    definition_ref["definition_sha256"] = "0" * 64

    with pytest.raises(Gate5FullDeclarationDefinitionError) as exc_info:
        _runtime(store).resolve(
            definition_ref=definition_ref,
            scope=_scope(context),
            typed_component_evidence=[],
            assertion_refs=[],
            context=context,
        )
    assert exc_info.value.code == "gate5_full_declaration_definition_not_published"


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "hash"])
def test_receipt_accounting_and_hash_drift_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    store, context, model = _proof_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    receipt = runtime.resolve(
        definition_ref=_definition_ref(),
        scope=_scope(context),
        typed_component_evidence=[_component_evidence(model)],
        assertion_refs=[],
        context=context,
    )
    changed = copy.deepcopy(receipt)
    if mutation == "missing":
        changed["domains"].pop()
    elif mutation == "extra":
        row = copy.deepcopy(changed["domains"][-1])
        row["domain_id"] = "unknown_extra_domain"
        changed["domains"].append(row)
    elif mutation == "duplicate":
        changed["domains"][-1] = copy.deepcopy(changed["domains"][-2])
    else:
        changed["receipt_sha256"] = "0" * 64

    code = _error_code(
        lambda: runtime.validate_receipt(receipt=changed, context=context)
    )
    assert code in {
        "gate5_declaration_scope_domain_accounting_invalid",
        "gate5_declaration_scope_receipt_hash_mismatch",
    }


def test_internally_rehashed_stale_gate4_binding_fails_against_live_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model = _proof_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    receipt = runtime.resolve(
        definition_ref=_definition_ref(),
        scope=_scope(context),
        typed_component_evidence=[_component_evidence(model)],
        assertion_refs=[],
        context=context,
    )
    changed = copy.deepcopy(receipt)
    changed["gate4_binding"]["facts"] = []
    gate4_base = {
        key: copy.deepcopy(value)
        for key, value in changed["gate4_binding"].items()
        if key != "binding_sha256"
    }
    changed["gate4_binding"]["binding_sha256"] = _sha256(gate4_base)
    receipt_base = {
        key: copy.deepcopy(value)
        for key, value in changed.items()
        if key != "receipt_sha256"
    }
    changed["receipt_sha256"] = _sha256(receipt_base)

    assert (
        _error_code(lambda: runtime.validate_receipt(receipt=changed, context=context))
        == "gate5_declaration_scope_gate4_binding_stale"
    )


def test_human_cannot_select_a_policy_incompatible_domain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model = _proof_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    receipt = runtime.resolve(
        definition_ref=_definition_ref(),
        scope=_scope(context),
        typed_component_evidence=[_component_evidence(model)],
        assertion_refs=[],
        context=context,
    )
    assert (
        _error_code(
            lambda: runtime.submit_human_answer(
                receipt=receipt,
                human_answer=_answer("no"),
                context=context,
                domain_id="professional_activity_results",
            )
        )
        == "gate5_declaration_scope_human_policy_incompatible"
    )


def test_foreign_user_cannot_reuse_case_bound_assertion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model = _proof_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    receipt = runtime.resolve(
        definition_ref=_definition_ref(),
        scope=_scope(context),
        typed_component_evidence=[_component_evidence(model)],
        assertion_refs=[],
        context=context,
    )
    stored = runtime.submit_human_answer(
        receipt=receipt,
        human_answer=_answer("no"),
        context=context,
        domain_id="refundable_amount_disposal",
    )
    foreign = replace(context, user_id="foreign-scope-user")

    with pytest.raises(ArtifactStoreError) as exc_info:
        _runtime(store).resolve(
            definition_ref=_definition_ref(),
            scope=_scope(foreign),
            typed_component_evidence=[],
            assertion_refs=[stored["assertion_ref"]],
            context=foreign,
        )
    assert exc_info.value.code == "artifact_access_denied"


def test_factory_and_forbidden_anchors_preserve_resolve_basis() -> None:
    assert "Gate5DeclarationScopeResolutionRuntimeFactory.create" in FACTORY_REQUIRED
    assert "Gate4FinancialCaseRuntimeFactory.create" in FACTORY_REQUIRED[2]
    assert any("current-input absence" in item for item in FORBIDDEN)
    assert any("new base primitive" in item for item in FORBIDDEN)


def test_architecture_uses_factories_and_contains_no_copied_domain_authority() -> None:
    source = inspect.getsource(module)
    factory_source = inspect.getsource(
        module.Gate5DeclarationScopeResolutionRuntimeFactory
    )
    assert "Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create()" in (
        factory_source
    )
    assert "Gate4FinancialCaseRuntimeFactory(" in factory_source
    assert "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()" in (
        factory_source
    )
    assert ".read_case(context=context)" in source
    for (
        domain
    ) in Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create().definition()[
        "domains"
    ]:
        assert domain["domain_id"] not in source
    for forbidden in (
        "SqliteArtifactStoreAdapter(",
        "Gate4FinancialCaseSqlCache(",
        "from .canonical_",
        "from .gate3_",
        "import sqlite3",
        "SELECT ",
        "CASE_COMPLETE_FOR_CURRENT_INPUT_SET ==",
    ):
        assert forbidden not in source


def _proof_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = aggregation_fixtures._store(tmp_path)
    model, context = aggregation_fixtures._operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="scope",
        gross="100.00",
        acquisition="70.00",
        fee="2.00",
    )
    return store, context, model


def _missing_source_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = aggregation_fixtures._store(tmp_path)
    monkeypatch.setitem(
        gate4_fixtures._FACT_SPEC_BY_TYPE,
        "SECURITY_DISPOSAL",
        (
            ("date", "11.02.2025"),
            ("asset", "ASSET-MISSING"),
            ("quantity", "1"),
            ("amount", None),
            ("currency", "RUB"),
            ("unit_price", "100,00"),
        ),
    )
    monkeypatch.setitem(
        gate4_fixtures._SOURCE_ROW_BY_TYPE,
        "SECURITY_DISPOSAL",
        "Продажа|11.02.2025|ASSET-MISSING|1|100,00|RUB|100,00",
    )
    context = ArtifactAccessContext(
        user_id="g5-supplied-case-user",
        normalization_run_id="g5-supplied-case-run-missing",
        case_id="g5-supplied-case-missing",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    gate4_fixtures._publish_document(
        store=store,
        context=context,
        document_id="g5-supplied-case-document-missing",
        financial_types=("SECURITY_DISPOSAL",),
        sidecar_artifact_id="g3-v2-g5-supplied-case-missing",
        created_at="2026-08-11T10:00:00+00:00",
    )
    gate4 = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    gate4.rebuild_case(context=context)
    financial_case = gate4.read_case(context=context)
    assert len(financial_case.facts) == 1
    assert financial_case.facts[0]["status"] == "role_incomplete"
    return store, context, financial_case.facts[0]


def _runtime(store):
    return Gate5DeclarationScopeResolutionRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _definition_ref() -> dict:
    return Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create().publication()


def _scope(context) -> dict[str, str]:
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_SCHEMA_VERSION,
        "scope_ref": "g529-bounded-scope-proof",
        "taxpayer_scope_ref": "security-disposal-1",
        "tax_period": "2025",
    }


def _component_evidence(model: dict) -> dict:
    return {
        "schema_version": (GATE5_DECLARATION_SCOPE_COMPONENT_EVIDENCE_SCHEMA_VERSION),
        "component_contract_id": (
            GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
        ),
        "component_sha256": _sha256(model),
        "payload": copy.deepcopy(model),
    }


def _answer(answer: str) -> dict[str, str]:
    return {
        "schema_version": GATE5_DECLARATION_SCOPE_HUMAN_ANSWER_SCHEMA_VERSION,
        "answer": answer,
    }


def _row(receipt: dict, domain_id: str) -> dict:
    return next(item for item in receipt["domains"] if item["domain_id"] == domain_id)


def _financial_sources(value):
    result = []
    if isinstance(value, dict):
        if value.get("source_kind") == "financial_case":
            result.append(value)
        for nested in value.values():
            result.extend(_financial_sources(nested))
    elif isinstance(value, list):
        for nested in value:
            result.extend(_financial_sources(nested))
    return result


def _sha256(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _error_code(call) -> str:
    with pytest.raises(Gate5DeclarationScopeResolutionError) as exc_info:
        call()
    return exc_info.value.code
