from __future__ import annotations

import copy
import hashlib
import inspect
import json
from dataclasses import replace
from pathlib import Path

import pytest

from broker_reports_gate1 import build_retention_policy
from broker_reports_gate1 import gate5_resolved_declaration_package as module
from broker_reports_gate1.gate5_full_declaration_definition import (
    Gate5TrustedFullDeclarationDefinitionAuthorityFactory,
)
from broker_reports_gate1.gate5_resolved_declaration_package import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate5ResolvedDeclarationPackageError,
    Gate5ResolvedDeclarationPackageRuntimeFactory,
)
import test_broker_reports_gate5_declaration_scope_resolution as scope_fixtures
import test_broker_reports_ordinary_trade_tax_model_bridge as bridge_fixtures
import test_broker_reports_gate5_declaration_financial_investment_results as financial_fixtures
from broker_reports_gate1.gate4_ordinary_trade_candidate import Gate4OrdinaryTradeCandidateRuntimeFactory
from broker_reports_gate1.gate5_declaration_scope_resolution import Gate5DeclarationScopeResolutionRuntimeFactory


def test_representative_package_accounts_every_definition_domain_without_promotion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model, scope_receipt = _scope_case(tmp_path, monkeypatch)
    runtime = _runtime(store)

    package = runtime.assemble(
        definition_ref=_definition_ref(),
        scope_receipt=scope_receipt,
        typed_component_snapshots=[_component(model)],
        context=context,
    )

    domain_ids = [
        item["domain_id"]
        for item in Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create().definition()[
            "domains"
        ]
    ]
    assert [item["domain_id"] for item in package["requirement_resolutions"]] == (
        domain_ids
    )
    assert package["status"] == "DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE"
    states = {item["domain_id"]: item for item in package["requirement_resolutions"]}
    assert sum(item["state"] == "REQUIRED_MISSING" for item in states.values()) == 4
    assert (
        sum(
            item["state"] == "NOT_ACTIVATED_FOR_SUPPLIED_CASE"
            for item in states.values()
        )
        == 7
    )
    assert all(item["state"] != "RESOLVED" for item in states.values())
    financial = next(
        item for item in package["requirement_resolutions"] if item["component_refs"]
    )
    assert financial["state"] == "REQUIRED_MISSING"
    assert financial["required_component"]["availability"] == "published_bounded"
    assert financial["diagnostics"] == ["bounded_component_available"]
    assert package["component_snapshots"][0]["snapshot"] == model
    assert package["completeness_receipt"]["first_blocker"] == {
        "domain_id": domain_ids[0],
        "blocker_class": "component",
        "state": "REQUIRED_MISSING",
        "reason": "required_component_missing",
    }
    assert runtime.validate_package(package=package) == package


def test_sealed_package_validation_reads_no_store_or_gate4(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model, scope_receipt = _scope_case(tmp_path, monkeypatch)
    package = _runtime(store).assemble(
        definition_ref=_definition_ref(),
        scope_receipt=scope_receipt,
        typed_component_snapshots=[_component(model)],
        context=context,
    )

    closed_validator = _closed_runtime()

    assert closed_validator.validate_package(package=package) == package


def test_policy_bound_not_applicable_is_terminal_without_component(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model, scope_receipt = _scope_case(tmp_path, monkeypatch)
    scope_runtime = scope_fixtures._runtime(store)
    denial = scope_runtime.submit_human_answer(
        receipt=scope_receipt,
        human_answer=scope_fixtures._answer("no"),
        context=context,
        domain_id="refundable_amount_disposal",
    )
    denied_receipt = scope_runtime.resolve(
        definition_ref=_definition_ref(),
        scope=scope_fixtures._scope(context),
        typed_component_evidence=[_component(model)],
        assertion_refs=[denial["assertion_ref"]],
        context=context,
    )

    package = _runtime(store).assemble(
        definition_ref=_definition_ref(),
        scope_receipt=denied_receipt,
        typed_component_snapshots=[_component(model)],
        context=context,
    )
    row = _resolution_with_state(package, "NOT_APPLICABLE")

    assert row["scope_state"] == "NOT_APPLICABLE"
    assert row["component_refs"] == []
    assert row["diagnostics"] == []
    assert package["status"] == "DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE"


def test_scope_conflict_remains_nonterminal_and_is_not_adjudicated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model, scope_receipt = _scope_case(tmp_path, monkeypatch)
    scope_runtime = scope_fixtures._runtime(store)
    denial = scope_runtime.submit_human_answer(
        receipt=scope_receipt,
        human_answer=scope_fixtures._answer("no"),
        context=context,
        domain_id="refundable_amount_disposal",
    )
    affirmation = scope_runtime.submit_human_answer(
        receipt=scope_receipt,
        human_answer=scope_fixtures._answer("yes"),
        context=context,
        domain_id="refundable_amount_disposal",
    )
    conflicted_receipt = scope_runtime.resolve(
        definition_ref=_definition_ref(),
        scope=scope_fixtures._scope(context),
        typed_component_evidence=[_component(model)],
        assertion_refs=[denial["assertion_ref"], affirmation["assertion_ref"]],
        context=context,
    )

    package = _runtime(store).assemble(
        definition_ref=_definition_ref(),
        scope_receipt=conflicted_receipt,
        typed_component_snapshots=[_component(model)],
        context=context,
    )

    assert _resolution_with_state(package, "SCOPE_CONFLICT")["scope_state"] == (
        "CONFLICT"
    )
    assert any(
        blocker["blocker_class"] == "scope"
        and blocker["reason"] == "applicability_conflict"
        for blocker in package["completeness_receipt"]["blockers"]
    )
    assert package["status"] == "DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE"


def test_wrong_definition_scope_receipt_or_case_fails_before_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model, scope_receipt = _scope_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    wrong_definition = _definition_ref()
    wrong_definition["definition_sha256"] = "0" * 64
    assert (
        _error_code(
            lambda: runtime.assemble(
                definition_ref=wrong_definition,
                scope_receipt=scope_receipt,
                typed_component_snapshots=[_component(model)],
                context=context,
            )
        )
        == "gate5_resolved_package_definition_binding_invalid"
    )

    drifted_receipt = copy.deepcopy(scope_receipt)
    drifted_receipt["receipt_sha256"] = "0" * 64
    assert (
        _error_code(
            lambda: runtime.assemble(
                definition_ref=_definition_ref(),
                scope_receipt=drifted_receipt,
                typed_component_snapshots=[_component(model)],
                context=context,
            )
        )
        == "gate5_resolved_package_scope_receipt_invalid"
    )

    foreign_context = replace(context, case_id="foreign-declaration-package-case")
    assert (
        _error_code(
            lambda: runtime.assemble(
                definition_ref=_definition_ref(),
                scope_receipt=scope_receipt,
                typed_component_snapshots=[_component(model)],
                context=foreign_context,
            )
        )
        == "gate5_resolved_package_scope_receipt_invalid"
    )


@pytest.mark.parametrize("mutation", ["missing", "extra"])
def test_sealed_scope_domain_accounting_fails_even_when_rehashed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    package = _package(tmp_path, monkeypatch)
    changed = copy.deepcopy(package)
    domains = changed["scope_receipt_snapshot"]["domains"]
    if mutation == "missing":
        domains.pop()
    else:
        extra = copy.deepcopy(domains[-1])
        extra["domain_id"] = "unknown_extra_domain"
        decision_base = {
            key: copy.deepcopy(value)
            for key, value in extra.items()
            if key != "decision_sha256"
        }
        extra["decision_sha256"] = _sha256(decision_base)
        domains.append(extra)
    _rehash_scope_and_package(changed)

    assert (
        _error_code(lambda: _closed_runtime().validate_package(package=changed))
        == "gate5_resolved_package_scope_domain_accounting_invalid"
    )


def test_scope_unresolved_cannot_be_promoted_by_rehashed_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, fact = scope_fixtures._missing_source_case(
        tmp_path, monkeypatch
    )
    scope_receipt = scope_fixtures._runtime(store).resolve(
        definition_ref=_definition_ref(),
        scope=scope_fixtures._scope(context),
        typed_component_evidence=[],
        assertion_refs=[],
        missing_source_indications=[
            {
                "schema_version": (
                    scope_fixtures.GATE5_DECLARATION_SCOPE_MISSING_SOURCE_INDICATION_SCHEMA_VERSION
                ),
                "component_contract_id": (
                    scope_fixtures.GATE5_SECURITIES_DISPOSAL_OPERATION_TAX_MODEL_SCHEMA_VERSION
                ),
                "source_fact_id": fact["fact_id"],
                "source_fact_sha256": _sha256(fact),
                "missing_role_names": ["amount"],
            }
        ],
        context=context,
    )
    package = _runtime(store).assemble(
        definition_ref=_definition_ref(),
        scope_receipt=scope_receipt,
        typed_component_snapshots=[],
        context=context,
    )
    changed = copy.deepcopy(package)
    row = _resolution_with_state(changed, "SCOPE_UNRESOLVED")
    row["state"] = "RESOLVED"
    _rehash_resolution(row)
    _rehash_completeness_and_package(changed)

    assert (
        _error_code(lambda: _closed_runtime().validate_package(package=changed))
        == "gate5_resolved_package_resolution_manifest_invalid"
    )


def test_component_hash_drift_or_bounded_promotion_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _package(tmp_path, monkeypatch)
    drifted = copy.deepcopy(package)
    drifted["component_snapshots"][0]["snapshot"]["operation_scope"]["subject_ref"] = (
        "different-taxpayer-scope"
    )
    _rehash_package(drifted)
    assert (
        _error_code(lambda: _closed_runtime().validate_package(package=drifted))
        == "gate5_resolved_package_component_invalid"
    )

    promoted = copy.deepcopy(package)
    bounded = next(
        item
        for item in promoted["requirement_resolutions"]
        if item["diagnostics"] == ["bounded_component_available"]
    )
    bounded["required_component"]["availability"] = "published_exact"
    bounded["state"] = "RESOLVED"
    bounded["diagnostics"] = []
    _rehash_resolution(bounded)
    _rehash_completeness_and_package(promoted)
    assert (
        _error_code(lambda: _closed_runtime().validate_package(package=promoted))
        == "gate5_resolved_package_resolution_manifest_invalid"
    )


def test_component_from_wrong_taxpayer_scope_fails_after_receipt_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model, scope_receipt = _scope_case(tmp_path, monkeypatch)
    foreign = copy.deepcopy(model)
    foreign["operation_scope"]["subject_ref"] = "different-taxpayer-scope"
    component = _component(foreign)
    rebound_receipt = copy.deepcopy(scope_receipt)
    _rebind_scope_component(
        rebound_receipt,
        old_sha256=_component(model)["component_sha256"],
        new_sha256=component["component_sha256"],
    )

    assert (
        _error_code(
            lambda: _runtime(store).assemble(
                definition_ref=_definition_ref(),
                scope_receipt=rebound_receipt,
                typed_component_snapshots=[component],
                context=context,
            )
        )
        == "gate5_resolved_package_component_scope_mismatch"
    )


def test_orphan_and_duplicate_component_inputs_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, model, scope_receipt = _scope_case(tmp_path, monkeypatch)
    runtime = _runtime(store)
    component = _component(model)
    orphan = copy.deepcopy(component)
    orphan["component_contract_id"] = "unknown_component_contract"

    assert (
        _error_code(
            lambda: runtime.assemble(
                definition_ref=_definition_ref(),
                scope_receipt=scope_receipt,
                typed_component_snapshots=[component, orphan],
                context=context,
            )
        )
        == "gate5_resolved_package_component_scope_binding_missing"
    )
    assert (
        _error_code(
            lambda: runtime.assemble(
                definition_ref=_definition_ref(),
                scope_receipt=scope_receipt,
                typed_component_snapshots=[component, copy.deepcopy(component)],
                context=context,
            )
        )
        == "gate5_resolved_package_component_ambiguous"
    )


def _two_operation_package_case(tmp_path):
    store, context, _ = bridge_fixtures._case(tmp_path, rows=bridge_fixtures._two_disposal_rows())
    bridge = bridge_fixtures._runtime(store)
    preflight = bridge_fixtures._run_operation_set(bridge, context=context, completeness_evidence=None)
    result = bridge_fixtures._run_operation_set(
        bridge, context=context,
        completeness_evidence=bridge_fixtures._completeness(preflight["operation_set"]["scope_binding"]["scope_binding_sha256"]),
    )
    assert result["status"] == "proven"
    components = [_component(item["operation_result"]["tax_model"]) for item in result["operation_results"]]
    retention = build_retention_policy(mode="synthetic_dev")
    scope_owner = Gate5DeclarationScopeResolutionRuntimeFactory(
        store=store, read_enabled=True, retention_policy=retention,
    ).create_current_source_fact_scope(
        gate4_runtime=Gate4OrdinaryTradeCandidateRuntimeFactory(store=store, read_enabled=True).create(),
        source_boundary="ordinary_trade_current_fact_v2",
    )
    scope = scope_owner.resolve(
        definition_ref=_definition_ref(),
        scope={"schema_version": scope_fixtures.GATE5_DECLARATION_SCOPE_SCHEMA_VERSION,
               "scope_ref": "two-operation-package", "taxpayer_scope_ref": "synthetic-taxpayer-control", "tax_period": "2025"},
        typed_component_evidence=components, assertion_refs=[], context=context,
        taxpayer_binding=bridge_fixtures._taxpayer_binding(),
    )
    runtime = Gate5ResolvedDeclarationPackageRuntimeFactory(
        store=store, read_enabled=True, retention_policy=retention,
    ).create_current_source_fact_package(scope_runtime=scope_owner)
    return runtime, context, scope, components, result


def test_distinct_scope_bound_operations_assemble_and_replay_in_hash_order(tmp_path):
    runtime, context, scope, components, _ = _two_operation_package_case(tmp_path)
    packages = [runtime.assemble(definition_ref=_definition_ref(), scope_receipt=scope,
        typed_component_snapshots=items, context=context) for items in (components, list(reversed(components)))]
    assert packages[0] == packages[1]
    package = packages[0]
    assert len(package["component_snapshots"]) == 2
    assert [item["content_sha256"] for item in package["component_snapshots"]] == sorted(item["component_sha256"] for item in components)
    assert package["status"] == "DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE"
    assert _closed_runtime().validate_package(package=package) == package


@pytest.mark.parametrize("mutation,code", [("duplicate", "gate5_resolved_package_component_ambiguous"), ("omit", "gate5_resolved_package_scope_component_snapshot_missing")])
def test_operation_set_duplicate_and_omission_fail_assembly_and_replay(tmp_path, mutation, code):
    runtime, context, scope, components, _ = _two_operation_package_case(tmp_path)
    package = runtime.assemble(definition_ref=_definition_ref(), scope_receipt=scope, typed_component_snapshots=components, context=context)
    changed = components + [copy.deepcopy(components[0])] if mutation == "duplicate" else components[:1]
    assert _error_code(lambda: runtime.assemble(definition_ref=_definition_ref(), scope_receipt=scope, typed_component_snapshots=changed, context=context)) == code
    if mutation == "duplicate":
        package["component_snapshots"].append(copy.deepcopy(package["component_snapshots"][0]))
    else:
        package["component_snapshots"].pop()
    _rehash_package(package)
    assert _error_code(lambda: _closed_runtime().validate_package(package=package)) == code


def test_other_component_duplicate_remains_rejected_with_operation_set(tmp_path):
    runtime, context, scope, components, result = _two_operation_package_case(tmp_path)
    root = financial_fixtures._component(scope["scope_binding"], result["category_result"]["category_tax_model"])
    evidence = financial_fixtures._component_evidence(root)
    package = runtime.assemble(definition_ref=_definition_ref(), scope_receipt=scope, typed_component_snapshots=components + [evidence], context=context)
    assert _error_code(lambda: runtime.assemble(definition_ref=_definition_ref(), scope_receipt=scope, typed_component_snapshots=components + [evidence, copy.deepcopy(evidence)], context=context)) == "gate5_resolved_package_component_ambiguous"
    root_snapshot = next(item for item in package["component_snapshots"] if item["root_coverage"] == "exact_root_domain")
    package["component_snapshots"].append(copy.deepcopy(root_snapshot))
    _rehash_package(package)
    assert _error_code(lambda: _closed_runtime().validate_package(package=package)) == "gate5_resolved_package_component_ambiguous"


def test_completeness_receipt_hash_drift_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _package(tmp_path, monkeypatch)
    changed = copy.deepcopy(package)
    changed["completeness_receipt"]["receipt_sha256"] = "0" * 64
    _rehash_package(changed)

    assert (
        _error_code(lambda: _closed_runtime().validate_package(package=changed))
        == "gate5_resolved_package_completeness_receipt_invalid"
    )


def test_factory_and_source_anchors_prevent_authority_drift() -> None:
    source = inspect.getsource(module)
    factory_source = inspect.getsource(
        module.Gate5ResolvedDeclarationPackageRuntimeFactory
    )
    validate_source = inspect.getsource(
        module.Gate5ResolvedDeclarationPackageRuntime.validate_package
    )
    assert "Gate5ResolvedDeclarationPackageRuntimeFactory.create" in FACTORY_REQUIRED[0]
    assert "Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create()" in (
        factory_source
    )
    assert "Gate5DeclarationScopeResolutionRuntimeFactory(" in factory_source
    assert "Gate5TaxPeriodCategoryAggregationRuntimeFactory.create()" in factory_source
    assert any("bounded component promotion" in item for item in FORBIDDEN)
    assert any("sixth primitive" in item for item in FORBIDDEN)
    authority_source = source.replace(
        "gate5_declaration_financial_investment_results", ""
    )
    for (
        domain
    ) in Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create().definition()[
        "domains"
    ]:
        assert domain["domain_id"] not in authority_source
    for forbidden in (
        "Gate4FinancialCaseRuntimeFactory",
        "SqliteArtifactStoreAdapter",
        "from .canonical_",
        "from .gate3_",
        "import sqlite3",
        "SELECT ",
    ):
        assert forbidden not in source
    assert "validate_receipt" not in validate_source
    assert "read_case" not in validate_source


def _scope_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store, context, model = scope_fixtures._proof_case(tmp_path, monkeypatch)
    scope_receipt = scope_fixtures._runtime(store).resolve(
        definition_ref=_definition_ref(),
        scope=scope_fixtures._scope(context),
        typed_component_evidence=[_component(model)],
        assertion_refs=[],
        context=context,
    )
    return store, context, model, scope_receipt


def _package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    store, context, model, scope_receipt = _scope_case(tmp_path, monkeypatch)
    return _runtime(store).assemble(
        definition_ref=_definition_ref(),
        scope_receipt=scope_receipt,
        typed_component_snapshots=[_component(model)],
        context=context,
    )


def _runtime(store):
    return Gate5ResolvedDeclarationPackageRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _closed_runtime():
    return Gate5ResolvedDeclarationPackageRuntimeFactory(
        store=None,
        read_enabled=False,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _definition_ref() -> dict:
    return Gate5TrustedFullDeclarationDefinitionAuthorityFactory.create().publication()


def _component(model: dict) -> dict:
    return scope_fixtures._component_evidence(model)


def _resolution_with_state(package: dict, state: str) -> dict:
    return next(
        item for item in package["requirement_resolutions"] if item["state"] == state
    )


def _rehash_scope_and_package(package: dict) -> None:
    scope_receipt = package["scope_receipt_snapshot"]
    scope_base = {
        key: copy.deepcopy(value)
        for key, value in scope_receipt.items()
        if key != "receipt_sha256"
    }
    scope_receipt["receipt_sha256"] = _sha256(scope_base)
    _rehash_package(package)


def _rebind_scope_component(
    scope_receipt: dict,
    *,
    old_sha256: str,
    new_sha256: str,
) -> None:
    for row in scope_receipt["domains"]:
        for evidence in row["evidence_bindings"]:
            if evidence["evidence_sha256"] == old_sha256:
                evidence["evidence_ref"] = new_sha256
                evidence["evidence_sha256"] = new_sha256
                decision_base = {
                    key: copy.deepcopy(value)
                    for key, value in row.items()
                    if key != "decision_sha256"
                }
                row["decision_sha256"] = _sha256(decision_base)
                receipt_base = {
                    key: copy.deepcopy(value)
                    for key, value in scope_receipt.items()
                    if key != "receipt_sha256"
                }
                scope_receipt["receipt_sha256"] = _sha256(receipt_base)
                return
    raise AssertionError("scope component evidence was not found")


def _rehash_resolution(row: dict) -> None:
    base = {
        key: copy.deepcopy(value)
        for key, value in row.items()
        if key != "resolution_sha256"
    }
    row["resolution_sha256"] = _sha256(base)


def _rehash_completeness_and_package(package: dict) -> None:
    receipt = package["completeness_receipt"]
    receipt["resolution_manifest_sha256"] = _sha256(package["requirement_resolutions"])
    receipt_base = {
        key: copy.deepcopy(value)
        for key, value in receipt.items()
        if key != "receipt_sha256"
    }
    receipt["receipt_sha256"] = _sha256(receipt_base)
    _rehash_package(package)


def _rehash_package(package: dict) -> None:
    base = {
        key: copy.deepcopy(value)
        for key, value in package.items()
        if key != "package_sha256"
    }
    package["package_sha256"] = _sha256(base)


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
    with pytest.raises(Gate5ResolvedDeclarationPackageError) as exc_info:
        call()
    return exc_info.value.code
