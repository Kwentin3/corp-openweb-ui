from __future__ import annotations

import copy
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from broker_reports_gate1.active_category_declaration_assembly import (
    ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN,
    BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN,
    FACTORY_REQUIRED,
    FORBIDDEN,
    ActiveCategoryDeclarationAssemblyRuntimeFactory,
    ActiveCategoryDeclarationAssemblyError,
)
from broker_reports_gate1.artifact_retention import build_retention_policy
from broker_reports_gate1.canonical_store import CanonicalReader
from broker_reports_gate1.gate4_financial_case_cache import (
    Gate4FinancialCaseRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_projection import (
    Gate5DeclarationProjectionRuntime,
)
from broker_reports_gate1.gate5_end_to_end_full_target_xml import (
    Gate5EndToEndSuppliedCaseAuthorityFactory,
    Gate5EndToEndFullTargetXmlRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_semantic_input import (
    Gate5DeclarationSemanticInputError,
    Gate5DeclarationSemanticInputRuntimeFactory,
)
from broker_reports_gate1.gate5_resolved_declaration_package import (
    Gate5ResolvedDeclarationPackageError,
)
from broker_reports_gate1.gate5_residency_evidence import (
    Gate5ResidencyEvidenceRuntimeFactory,
    gate5_residency_methodology_input,
)
from broker_reports_gate1 import active_category_declaration_assembly as assembly_module
from broker_reports_gate1 import gate5_declaration_scope_resolution as scope_module
from broker_reports_gate1 import gate5_resolved_declaration_package as package_module

import test_broker_reports_ordinary_trade_tax_model_bridge as bridge_fixtures


def test_clean_active_fact_v2_category_reaches_consumer_first_xsd_deterministically(
    tmp_path: Path,
) -> None:
    store, context, facts = _case(tmp_path / "clean", proceeds="60.00")
    runtime = _runtime(store)
    inputs = _bridge_inputs(context, facts, store)
    right_side = _right_side(context.user_id)

    first = runtime.run(**inputs, right_side_inputs=right_side, context=context)
    second = runtime.run(**inputs, right_side_inputs=right_side, context=context)

    assert first == second
    assert first["terminal"] == ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN
    assert first["blockers"] == first["demands"] == []
    assert first["identity_binding"]["operation_subject_ref"] == "security-disposal-1"
    assert (
        first["identity_binding"]["taxpayer_scope_ref"] == "synthetic-taxpayer-control"
    )
    assert (
        first["identity_binding"]["operation_subject_ref"]
        != first["identity_binding"]["taxpayer_scope_ref"]
    )
    assert (
        first["fact_v2_binding"]["boundary"]
        == "Gate4OrdinaryTradeCandidateRuntimeFactory.create"
    )
    assert first["fact_v2_binding"]["gate3_case_status"] == "not_executed"
    assert first["target_accounting"]["deterministic_identical_xml_bytes"] is True
    assert first["target_accounting"]["xsd_conformance"]["xsd_valid"] is True
    assert first["target_accounting"]["mapping_occurrences_total"] == 49
    assert first["target_accounting"]["released_semantic_occurrences"] == 44
    assert first["target_accounting"]["official_constant_occurrences"] == 4
    assert first["target_accounting"]["target_mechanics_occurrences"] == 1
    assert first["release_accounting"]["declared_value_count"] == 44
    assert first["execution_constraints"] == {
        "active": False,
        "shadow_only": True,
        "persisted": False,
        "downloadable": False,
        "provider_calls": 0,
        "gate3_execution": False,
        "historical_sql_gate4_reads": False,
        "canonical_reads_downstream": False,
        "source_observation_reads_downstream": False,
        "prebuilt_tax_models": False,
    }


def test_partial_acquisition_commission_demand_survives_and_stops_release(
    tmp_path: Path,
) -> None:
    store, context, facts = _case(
        tmp_path / "material-commission",
        proceeds="60.00",
        purchase_charges=True,
    )
    result = _runtime(store).run(
        **_bridge_inputs(context, facts, store),
        right_side_inputs=_right_side(context.user_id),
        context=context,
    )

    assert result["terminal"] == BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN
    assert (
        result["blockers"][0]["reason_code"]
        == "partial_acquisition_commission_allocation"
    )
    assert (
        result["blockers"][0]["gap_owner_classification"]
        == "LEGAL_INTERPRETATION_REQUIRED"
    )
    assert result["demands"] == result["upstream_bridge"]["demands"]
    assert result["released_values"] is None
    assert result["target_receipt"] is None


@pytest.mark.parametrize(
    ("mutation", "reason_code", "gap_class"),
    [
        (
            "missing_taxpayer",
            "gate5_tax_model_bridge_taxpayer_binding_missing",
            "USER_CASE_FACT_MISSING",
        ),
        (
            "foreign_taxpayer",
            "gate5_tax_model_bridge_taxpayer_scope_binding_mismatch",
            "USER_CASE_FACT_MISSING",
        ),
        (
            "misbound_operation_subject",
            "gate5_tax_model_bridge_operation_subject_binding_mismatch",
            "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT",
        ),
        (
            "missing_category_completeness",
            "gate5_tax_period_completeness_evidence_absent",
            "USER_CASE_FACT_MISSING",
        ),
        (
            "stale_category_completeness",
            "gate5_tax_period_completeness_binding_mismatch",
            "USER_CASE_FACT_MISSING",
        ),
        (
            "missing_organized_market",
            "gate5_tax_model_classification_prerequisite_missing",
            "EXTERNAL_AUTHORITATIVE_FACT_MISSING",
        ),
    ],
)
def test_upstream_identity_category_and_applicability_negatives_fail_closed(
    tmp_path: Path,
    mutation: str,
    reason_code: str,
    gap_class: str,
) -> None:
    store, context, facts = _case(tmp_path / mutation, proceeds="60.00")
    inputs = _bridge_inputs(context, facts, store)
    if mutation == "missing_taxpayer":
        inputs["taxpayer_binding"] = None
    elif mutation == "foreign_taxpayer":
        inputs["category_scope"] = copy.deepcopy(inputs["category_scope"])
        inputs["category_scope"]["taxpayer_scope_ref"] = "foreign-taxpayer"
    elif mutation == "misbound_operation_subject":
        inputs["taxpayer_binding"] = bridge_fixtures._taxpayer_binding(
            operation_subject_ref="foreign-security-disposal"
        )
    elif mutation == "missing_category_completeness":
        inputs["category_completeness_evidence"] = None
    elif mutation == "stale_category_completeness":
        inputs["category_completeness_evidence"] = copy.deepcopy(
            inputs["category_completeness_evidence"]
        )
        inputs["category_completeness_evidence"]["scope_binding_sha256"] = "0" * 64
    elif mutation == "missing_organized_market":
        inputs["resolved_inputs"] = copy.deepcopy(inputs["resolved_inputs"])
        del inputs["resolved_inputs"]["operation_properties"]["organized_market_status"]

    result = _runtime(store).run(
        **inputs,
        right_side_inputs=_right_side(context.user_id),
        context=context,
    )

    assert result["terminal"] == BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN
    assert result["blockers"][0]["reason_code"] == reason_code
    assert result["blockers"][0]["gap_owner_classification"] == gap_class
    assert result["released_values"] is result["target_receipt"] is None


@pytest.mark.parametrize(
    ("mutation", "gap_class"),
    [
        ("missing_income_group_completeness", "USER_CASE_FACT_MISSING"),
        ("stale_income_group_completeness", "INTERNAL_CONTRACT_OR_PIPELINE_DEFECT"),
        ("missing_residency", "USER_CASE_FACT_MISSING"),
        ("missing_filing_identity", "USER_CASE_FACT_MISSING"),
        ("missing_source_party", "SOURCE_EVIDENCE_INSUFFICIENT"),
        ("missing_settlement", "USER_CASE_FACT_MISSING"),
        ("missing_budget", "USER_CASE_FACT_MISSING"),
    ],
)
def test_right_side_completeness_and_component_negatives_fail_closed(
    tmp_path: Path,
    mutation: str,
    gap_class: str,
) -> None:
    store, context, facts = _case(tmp_path / mutation, proceeds="60.00")
    right = _right_side(context.user_id)
    if mutation == "missing_income_group_completeness":
        del right["income_group"]["completeness_provenance"]
    elif mutation == "stale_income_group_completeness":
        right["income_group"]["completeness_input_binding_sha256"] = "0" * 64
    elif mutation == "missing_residency":
        del right["residency_evidence"]
    elif mutation == "missing_filing_identity":
        del right["filing_and_party_identity"]
    elif mutation == "missing_source_party":
        del right["taxable_income_source"]["source_party"]
    elif mutation == "missing_settlement":
        del right["settlement"]
    elif mutation == "missing_budget":
        del right["budget_disposition"]

    result = _runtime(store).run(
        **_bridge_inputs(context, facts, store),
        right_side_inputs=right,
        context=context,
    )

    assert result["terminal"] == BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN
    assert result["blockers"][0]["gap_owner_classification"] == gap_class
    assert result["blockers"][0]["owner"] != "ActiveCategoryDeclarationAssemblyRuntime"
    assert result["released_values"] is result["target_receipt"] is None


@pytest.mark.parametrize(
    ("mutation", "field"),
    [
        ("direct_income_group_status", "taxpayer_status"),
        ("direct_filing_period_status", "taxpayer.period_status"),
    ],
)
def test_right_side_rejects_caller_supplied_taxpayer_status(
    tmp_path: Path,
    mutation: str,
    field: str,
) -> None:
    store, context, facts = _case(tmp_path / mutation, proceeds="60.00")
    right = _right_side(context.user_id)
    if mutation == "direct_income_group_status":
        right["income_group"]["taxpayer_status"] = {
            "value": "nonresident_individual",
            "provenance": {
                "source_kind": "user_verified_fact",
                "source_ref": "forbidden-direct-status",
                "input_channel": "taxpayer_status",
            },
        }
    else:
        right["filing_and_party_identity"]["taxpayer"]["period_status"] = (
            "nonresident_individual"
        )

    result = _runtime(store).run(
        **_bridge_inputs(context, facts, store),
        right_side_inputs=right,
        context=context,
    )

    assert result["terminal"] == BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN
    assert result["blockers"][0]["reason_code"] == (
        "gate5_e2e_direct_taxpayer_status_forbidden"
    )
    assert result["blockers"][0]["required_input"] == field
    assert result["blockers"][0]["owner"] == (
        "Gate5DeclarationRightSideAssemblyRuntime"
    )
    assert result["released_values"] is result["target_receipt"] is None


def test_caller_supplied_raw_visual_control_is_rejected(tmp_path: Path) -> None:
    store, context, facts = _case(tmp_path / "forbidden-raw", proceeds="60.00")
    right = _right_side(context.user_id)
    right["raw_ordinary_trade_table"] = {"disposal": {"gross_amount": "1.00"}}

    result = _runtime(store).run(
        **_bridge_inputs(context, facts, store),
        right_side_inputs=right,
        context=context,
    )

    assert result["terminal"] == BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN
    assert result["blockers"][0]["reason_code"] == (
        "gate5_active_assembly_raw_control_forbidden"
    )
    assert result["released_values"] is result["target_receipt"] is None


def test_one_disposal_proceeds_cell_changes_only_bounded_g545_mapping_ids(
    tmp_path: Path,
) -> None:
    results = []
    for name, proceeds in (("baseline", "60.00"), ("delta", "64.00")):
        store, context, facts = _case(tmp_path / name, proceeds=proceeds)
        results.append(
            _runtime(store).run(
                **_bridge_inputs(context, facts, store),
                right_side_inputs=_right_side(context.user_id),
                context=context,
            )
        )
    baseline, changed = results
    before = {
        item["mapping_id"]: item["target_value_sha256"]
        for item in baseline["target_accounting"]["mapping_projection"]
    }
    after = {
        item["mapping_id"]: item["target_value_sha256"]
        for item in changed["target_accounting"]["mapping_projection"]
    }

    assert {key for key in before if before[key] != after[key]} == {
        "budget-payable",
        "total-income",
        "taxable-income",
        "tax-base",
        "calculated-tax",
        "tax-payable",
        "source-income",
        "securities-gross-income",
    }
    assert (
        baseline["stage_hashes"]["operation_tax_model_sha256"]
        != changed["stage_hashes"]["operation_tax_model_sha256"]
    )
    assert (
        baseline["stage_hashes"]["xml_sha256"] != changed["stage_hashes"]["xml_sha256"]
    )
    disposal_rows = [
        row
        for row in changed["visual_accounting"]["source_bound_fact_v2"]
        if row["financial_type"] == "SECURITY_DISPOSAL"
    ]
    gross_literals = {
        role["source_literal"]
        for row in disposal_rows
        for role in row["roles"]
        if role["role"] == "amount"
    }
    assert gross_literals == {"64.00"}


def test_changed_category_cannot_reuse_sealed_income_group_completeness(
    tmp_path: Path,
) -> None:
    store_a, context_a, facts_a = _case(tmp_path / "sealed-a", proceeds="60.00")
    baseline = _runtime(store_a).run(
        **_bridge_inputs(context_a, facts_a, store_a),
        right_side_inputs=_right_side(context_a.user_id),
        context=context_a,
    )
    old_binding = baseline["category_to_income_group_binding"]["input_binding_sha256"]

    store_b, context_b, facts_b = _case(tmp_path / "changed-b", proceeds="64.00")
    right = _right_side(context_b.user_id)
    right["income_group"]["completeness_input_binding_sha256"] = old_binding
    changed = _runtime(store_b).run(
        **_bridge_inputs(context_b, facts_b, store_b),
        right_side_inputs=right,
        context=context_b,
    )

    assert changed["terminal"] == BOUNDED_DECLARATION_ASSEMBLY_BLOCKERS_PROVEN
    assert changed["blockers"][0]["reason_code"] == (
        "gate5_income_group_tax_base_completeness_invalid"
    )
    assert changed["released_values"] is changed["target_receipt"] is None


def test_category_cannot_bypass_package_or_release_contract(tmp_path: Path) -> None:
    store, context, facts = _case(tmp_path / "bypass", proceeds="60.00")
    inputs = _bridge_inputs(context, facts, store)
    bridge = bridge_fixtures._run(
        bridge_fixtures._runtime(store),
        context=context,
        disposal_fact_id=inputs["disposal_fact_id"],
        resolved_inputs=inputs["resolved_inputs"],
        completeness_evidence=inputs["category_completeness_evidence"],
    )
    category = bridge["category_result"]["category_tax_model"]

    with pytest.raises(Gate5DeclarationSemanticInputError) as exc:
        Gate5DeclarationSemanticInputRuntimeFactory.create().compile_declaration_value_candidate(
            package=category
        )
    assert exc.value.code == "gate5_declaration_semantic_source_package_invalid"


@pytest.mark.parametrize(
    "target",
    [
        ("stage_hashes", "category_tax_model_sha256"),
        ("stage_hashes", "package_sha256"),
        ("stage_hashes", "semantic_value_sha256"),
        ("hash_chain", 3, "artifact_sha256"),
    ],
)
def test_category_package_release_and_receipt_chain_mutations_fail_closed(
    tmp_path: Path,
    target: tuple,
) -> None:
    store, context, facts = _case(tmp_path / str(target), proceeds="60.00")
    runtime = _runtime(store)
    receipt = runtime.run(
        **_bridge_inputs(context, facts, store),
        right_side_inputs=_right_side(context.user_id),
        context=context,
    )
    changed = copy.deepcopy(receipt)
    if target[0] == "stage_hashes":
        changed[target[0]][target[1]] = "0" * 64
    else:
        changed[target[0]][target[1]][target[2]] = "0" * 64

    with pytest.raises(ActiveCategoryDeclarationAssemblyError) as exc:
        runtime.validate_receipt(changed, context=context)
    assert exc.value.code in {
        "gate5_active_assembly_receipt_chain_invalid",
        "gate5_active_assembly_receipt_hash_mismatch",
        "gate5_active_assembly_owner_artifact_binding_invalid",
    }


@pytest.mark.parametrize(
    "artifact",
    ["package", "released_values", "target_receipt", "release_count", "target_count"],
)
def test_self_consistent_outer_receipt_cannot_hide_owner_artifact_mutation(
    tmp_path: Path,
    artifact: str,
) -> None:
    store, context, facts = _case(tmp_path / artifact, proceeds="60.00")
    runtime = _runtime(store)
    changed = runtime.run(
        **_bridge_inputs(context, facts, store),
        right_side_inputs=_right_side(context.user_id),
        context=context,
    )
    changed = copy.deepcopy(changed)
    if artifact == "package":
        package = changed["owner_artifacts"]["package"]
        package["status"] = "DECLARATION_INCOMPLETE_FOR_SUPPLIED_CASE"
        package["package_sha256"] = _sha(
            {key: value for key, value in package.items() if key != "package_sha256"}
        )
        changed["stage_hashes"]["package_sha256"] = package["package_sha256"]
    elif artifact == "released_values":
        changed["owner_artifacts"]["released_values"]["declaration_values"]["taxpayer"][
            "inn"
        ] = "999999999999"
    elif artifact == "target_receipt":
        target = changed["owner_artifacts"]["target_receipt"]
        target["conformance_proof"]["xsd_valid"] = False
        target["receipt_sha256"] = _sha(
            {key: value for key, value in target.items() if key != "receipt_sha256"}
        )
        changed["stage_hashes"]["projection_receipt_sha256"] = target["receipt_sha256"]
    elif artifact == "release_count":
        changed["release_accounting"]["declared_value_count"] = 43
    else:
        changed["target_accounting"]["mapping_occurrences_total"] = 48
    _reseal_outer_receipt(changed)

    with pytest.raises(
        (
            ActiveCategoryDeclarationAssemblyError,
            Gate5ResolvedDeclarationPackageError,
            Gate5DeclarationSemanticInputError,
        )
    ) as exc:
        runtime.validate_receipt(changed, context=context)
    assert getattr(exc.value, "code", "") != (
        "gate5_active_assembly_receipt_hash_mismatch"
    )


def test_self_consistent_receipt_with_inexact_stage_set_fails_closed(
    tmp_path: Path,
) -> None:
    store, context, facts = _case(tmp_path / "stage-set", proceeds="60.00")
    runtime = _runtime(store)
    changed = runtime.run(
        **_bridge_inputs(context, facts, store),
        right_side_inputs=_right_side(context.user_id),
        context=context,
    )
    changed = copy.deepcopy(changed)
    changed["stage_hashes"]["invented_stage_sha256"] = "0" * 64
    _reseal_outer_receipt(changed)

    with pytest.raises(ActiveCategoryDeclarationAssemblyError) as exc:
        runtime.validate_receipt(changed, context=context)
    assert exc.value.code == "gate5_active_assembly_receipt_chain_invalid"


def test_historical_gate3_sql_and_legacy_projection_fallbacks_are_trapped(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, facts = _case(tmp_path / "fallback-traps", proceeds="60.00")

    def forbidden(*args, **kwargs):
        raise AssertionError("forbidden historical fallback executed")

    monkeypatch.setattr(Gate4FinancialCaseRuntimeFactory, "create", forbidden)
    monkeypatch.setattr(Gate5EndToEndFullTargetXmlRuntimeFactory, "create", forbidden)
    monkeypatch.setattr(CanonicalReader, "read_active_envelope", forbidden)
    monkeypatch.setattr(Gate5DeclarationProjectionRuntime, "project", forbidden)

    result = _runtime(store).run(
        **_bridge_inputs(context, facts, store),
        right_side_inputs=_right_side(context.user_id),
        context=context,
    )
    assert result["terminal"] == ACTIVE_CATEGORY_TO_DECLARATION_ASSEMBLY_PROVEN
    assert "existing owners" in FACTORY_REQUIRED[0]
    assert "historical SQL Gate 4" in FORBIDDEN[1]
    source = inspect.getsource(assembly_module)
    for forbidden_name in (
        "Gate3",
        "Gate4FinancialCaseRuntimeFactory",
        "CanonicalReaderFactory",
        "sqlite3",
        "model_client",
        "Gate5DeclarationProjectionRuntime",
    ):
        assert forbidden_name not in source
    for right_domain in (scope_module, package_module):
        right_source = inspect.getsource(right_domain)
        assert "ordinary_trade_tax_model_bridge" not in right_source
        assert "gate4_ordinary_trade_candidate" not in right_source
    assert "Gate4OrdinaryTradeCandidateRuntimeFactory" in source
    assert "OrdinaryTradeTaxModelBridgeRuntimeFactory" in source
    g535_source = inspect.getsource(
        __import__(
            "broker_reports_gate1.gate5_end_to_end_full_target_xml",
            fromlist=["*"],
        )
    )
    assert "Gate5DeclarationRightSideAssemblyRuntimeFactory.create" in g535_source
    for duplicate in (
        "def _settlement_component(",
        "def _income_source_component(",
        "def _filing_component(",
        "def _budget_component(",
        "def _financial_component(",
    ):
        assert duplicate not in g535_source


def _case(root: Path, *, proceeds: str, purchase_charges: bool = False):
    rows = (
        bridge_fixtures._HEADERS,
        bridge_fixtures._row(
            side=bridge_fixtures._PURCHASE_SIDE, charges=purchase_charges
        ),
        _with_amount(
            bridge_fixtures._row(side=bridge_fixtures._DISPOSAL_SIDE, charges=True),
            proceeds,
        ),
    )
    return bridge_fixtures._case(root, rows=rows)


def _with_amount(row: tuple[str, ...], amount: str) -> tuple[str, ...]:
    values = list(row)
    roles = bridge_fixtures.ordinary_fixtures._ROLES
    values[roles.index("gross_amount")] = amount
    values[roles.index("unit_price")] = f"{float(amount) / 4:.2f}"
    return tuple(values)


def _runtime(store):
    return ActiveCategoryDeclarationAssemblyRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _bridge_inputs(context, facts, store) -> dict:
    disposal_fact_id = bridge_fixtures._fact_id(facts, "SECURITY_DISPOSAL")
    bridge = bridge_fixtures._runtime(store)
    resolved_inputs = bridge_fixtures._resolved_inputs()
    residency_facts = _right_side(context.user_id)["residency_evidence"]
    residency_runtime = Gate5ResidencyEvidenceRuntimeFactory.create()
    residency = residency_runtime.classify(
        evidence=residency_runtime.normalize_human_answer(
            human_answer=residency_facts["human_answer"],
            proposal=residency_facts["proposal"],
            source_ref=residency_facts["source_ref"],
        )
    )
    resolved_inputs["tax_context"]["residency"] = gate5_residency_methodology_input(
        residency,
        input_channel="minimal_tax_context",
    )
    incomplete = bridge_fixtures._run(
        bridge,
        context=context,
        disposal_fact_id=disposal_fact_id,
        resolved_inputs=resolved_inputs,
        completeness_evidence=None,
    )
    completeness = bridge_fixtures._completeness(
        incomplete["category_result"]["scope_binding"]["scope_binding_sha256"]
    )
    return {
        "operation_methodology_ref": bridge_fixtures._operation_methodology_ref(),
        "source_fact_methodology_ref": bridge_fixtures._source_methodology_ref(),
        "resolved_inputs": resolved_inputs,
        "disposal_fact_id": disposal_fact_id,
        "operation_ref": "operation-control-2025",
        "source_scope_ref": context.case_id,
        "category_scope": bridge_fixtures._category_scope(),
        "taxpayer_binding": bridge_fixtures._taxpayer_binding(),
        "category_completeness_evidence": completeness,
    }


def _right_side(user_id: str = "g4-runtime-user") -> dict:
    source = Gate5EndToEndSuppliedCaseAuthorityFactory.create().load()
    result = {
        key: copy.deepcopy(source[key])
        for key in (
            "scope",
            "residency_evidence",
            "income_group",
            "settlement",
            "filing_and_party_identity",
            "taxable_income_source",
            "budget_disposition",
            "financial_investment",
        )
    }
    result["scope"]["taxpayer_scope_ref"] = "synthetic-taxpayer-control"
    result["filing_and_party_identity"]["taxpayer"]["taxpayer_ref"] = (
        "synthetic-taxpayer-control"
    )
    result["filing_and_party_identity"]["signer"]["signer_ref"] = user_id
    return result


def _reseal_outer_receipt(receipt: dict) -> None:
    receipt["hash_chain"] = assembly_module._hash_chain(receipt["stage_hashes"])
    receipt["receipt_sha256"] = _sha(
        {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    )


def _sha(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
