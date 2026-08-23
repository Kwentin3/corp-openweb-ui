from __future__ import annotations

import copy
import hashlib
import inspect
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from broker_reports_gate1 import (
    GATE5_INCOME_GROUP_TAX_BASE_BEHAVIOR_ID,
    GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
    GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
    GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
    GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION,
    GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
    GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE,
    GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE_SHA256,
    GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    Gate5IncomeGroupTaxBaseError,
    Gate5IncomeGroupTaxBaseRuntimeFactory,
    Gate5PublishedTypedBehaviorError,
    Gate5RuntimeCapabilityResolverV1Factory,
    build_retention_policy,
)
from broker_reports_gate1 import gate5_income_group_tax_base as tax_base_module
import test_broker_reports_gate5_published_typed_behavior as typed_fixtures


SERVICE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = SERVICE_ROOT / "broker_reports_gate1"


def test_published_behavior_calculates_complete_stable_group_tax_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, category = _complete_category(tmp_path, monkeypatch)
    owner = Gate5IncomeGroupTaxBaseRuntimeFactory.create()
    status = _tagged("resident_individual", "taxpayer-status", "taxpayer_status")
    values = _group_values(
        other_income="10.00",
        other_expenses="4.00",
        non_taxable="5.00",
        deductions="3.00",
    )
    binding = owner.describe_input(
        category_tax_model=category,
        taxpayer_status=status,
        group_values=values,
    )

    result = _typed_runtime(store).execute(
        behavior_ref=_behavior_ref(),
        input_contract_id=GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
        output_contract_id=GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
        behavior_input=_behavior_input(
            category=category,
            status=status,
            values=values,
            binding_sha256=binding["input_binding_sha256"],
        ),
        context=context,
    )

    model = result["result_payload"]
    assert result["status"] == "executed"
    assert result["behavior_binding"] == {
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": (
            GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION
        ),
        "behavior_id": GATE5_INCOME_GROUP_TAX_BASE_BEHAVIOR_ID,
        "input_contract_id": GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
        "output_contract_id": GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
    }
    assert model["total_income"]["value"] == _money("160.00")
    assert model["taxable_income"]["value"] == _money("155.00")
    assert model["accepted_expenses"]["value"] == _money("104.00")
    assert model["tax_base"]["value"] == _money("48.00")
    assert model["calculation_scope"]["income_group_semantic"] == (
        "resident_securities_and_derivatives_non_iis"
    )
    assert model["calculation_scope"]["input_binding"] == binding
    assert model["input_snapshot"]["category_tax_model"] == category
    assert result["provenance"] == {
        "retention": "exact_in_result_payload",
        "source_kinds": [
                "financial_case",
                "methodology_derived",
                "methodology_derived_result",
                "proof_assumption",
            "supplemental_fact",
            "user_provided_supplemental",
            "user_verified_fact",
        ],
        "includes_methodology_derived_result": True,
    }


@pytest.mark.parametrize(
    ("mutation", "expected"),
    (
        (
            lambda value: value.__setitem__("completeness_evidence", None),
            "gate5_income_group_tax_base_completeness_invalid",
        ),
        (
            lambda value: value["completeness_evidence"].__setitem__(
                "input_binding_sha256", "0" * 64
            ),
            "gate5_income_group_tax_base_completeness_invalid",
        ),
        (
            lambda value: value["group_values"].pop(
                "other_group_allowable_expenses"
            ),
            "gate5_income_group_tax_base_group_values_invalid",
        ),
        (
            lambda value: value["taxpayer_status"].__setitem__(
                "value", "nonresident_individual"
            ),
            "gate5_income_group_tax_base_completeness_invalid",
        ),
    ),
)
def test_missing_or_stale_group_prerequisites_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation,
    expected: str,
) -> None:
    _store, _context, category = _complete_category(tmp_path, monkeypatch)
    behavior_input = _valid_input(category)
    mutation(behavior_input)

    with pytest.raises(Gate5IncomeGroupTaxBaseError) as caught:
        Gate5IncomeGroupTaxBaseRuntimeFactory.create().run(
            methodology_ref=_methodology_ref(),
            behavior_input=behavior_input,
        )

    assert caught.value.code == expected


@pytest.mark.parametrize(
    (
        "other_income",
        "other_expenses",
        "non_taxable",
        "deductions",
        "expected",
    ),
    (
        (
            "0.00",
            "0.00",
            "151.00",
            "0.00",
            "gate5_income_group_tax_base_non_taxable_exceeds_income",
        ),
        (
            "0.00",
            "1.00",
            "49.00",
            "1.00",
            "gate5_income_group_tax_base_reductions_exceed_taxable_income",
        ),
    ),
)
def test_invalid_calculation_domain_is_rejected_without_clamping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    other_income: str,
    other_expenses: str,
    non_taxable: str,
    deductions: str,
    expected: str,
) -> None:
    _store, _context, category = _complete_category(tmp_path, monkeypatch)
    owner = Gate5IncomeGroupTaxBaseRuntimeFactory.create()
    status = _tagged("resident_individual", "taxpayer-status", "taxpayer_status")
    values = _group_values(
        other_income=other_income,
        other_expenses=other_expenses,
        non_taxable=non_taxable,
        deductions=deductions,
    )
    binding = owner.describe_input(
        category_tax_model=category,
        taxpayer_status=status,
        group_values=values,
    )

    with pytest.raises(Gate5IncomeGroupTaxBaseError) as caught:
        owner.run(
            methodology_ref=_methodology_ref(),
            behavior_input=_behavior_input(
                category=category,
                status=status,
                values=values,
                binding_sha256=binding["input_binding_sha256"],
            ),
        )

    assert caught.value.code == expected


def test_nonresident_status_fails_exact_applicability_after_valid_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, category = _complete_category(tmp_path, monkeypatch)
    owner = Gate5IncomeGroupTaxBaseRuntimeFactory.create()
    status = _tagged(
        "nonresident_individual", "taxpayer-status", "taxpayer_status"
    )
    values = _group_values()
    binding = owner.describe_input(
        category_tax_model=category,
        taxpayer_status=status,
        group_values=values,
    )

    with pytest.raises(Gate5IncomeGroupTaxBaseError) as caught:
        owner.run(
            methodology_ref=_methodology_ref(),
            behavior_input=_behavior_input(
                category=category,
                status=status,
                values=values,
                binding_sha256=binding["input_binding_sha256"],
            ),
        )

    assert caught.value.code == (
        "gate5_income_group_tax_base_applicability_unsupported"
    )
    assert caught.value.field == "taxpayer_status"


def test_direct_user_residency_status_is_rejected_before_income_group_calculation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, category = _complete_category(tmp_path, monkeypatch)
    direct_user_status = _tagged(
        "resident_individual", "direct-user-claim", "taxpayer_status"
    )
    direct_user_status["provenance"] = {
        "source_kind": "user_verified_fact",
        "source_ref": "direct-user-claim",
        "input_channel": "taxpayer_status",
    }

    with pytest.raises(Gate5IncomeGroupTaxBaseError) as caught:
        Gate5IncomeGroupTaxBaseRuntimeFactory.create().describe_input(
            category_tax_model=category,
            taxpayer_status=direct_user_status,
            group_values=_group_values(),
        )

    assert caught.value.code == "gate5_income_group_tax_base_provenance_invalid"


def test_mixed_group_currency_fails_before_completeness_can_be_asserted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store, _context, category = _complete_category(tmp_path, monkeypatch)
    values = _group_values()
    values["tax_deductions"]["value"]["currency"] = "USD"

    with pytest.raises(Gate5IncomeGroupTaxBaseError) as caught:
        Gate5IncomeGroupTaxBaseRuntimeFactory.create().describe_input(
            category_tax_model=category,
            taxpayer_status=_tagged(
                "resident_individual", "taxpayer-status", "taxpayer_status"
            ),
            group_values=values,
        )

    assert caught.value.code == "gate5_income_group_tax_base_currency_mismatch"


def test_output_tamper_and_contract_mismatch_fail_at_published_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, context, category = _complete_category(tmp_path, monkeypatch)
    behavior_input = _valid_input(category)
    runtime = _typed_runtime(store)
    executed = runtime.execute(
        behavior_ref=_behavior_ref(),
        input_contract_id=GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
        output_contract_id=GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
        behavior_input=behavior_input,
        context=context,
    )
    tampered = copy.deepcopy(executed["result_payload"])
    tampered["tax_base"]["value"]["amount"] = "49.00"

    with pytest.raises(Gate5PublishedTypedBehaviorError) as output_error:
        runtime.validate_registered_output(
            behavior_ref=_behavior_ref(),
            input_contract_id=GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
            output_contract_id=GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
            payload=tampered,
        )
    assert output_error.value.code == (
        "gate5_published_typed_behavior_output_validation_failed"
    )

    with pytest.raises(Gate5PublishedTypedBehaviorError) as contract_error:
        runtime.execute(
            behavior_ref=_behavior_ref(),
            input_contract_id="caller_defined_income_group_input_v9",
            output_contract_id=GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
            behavior_input=behavior_input,
            context=context,
        )
    assert contract_error.value.code == (
        "gate5_published_typed_behavior_input_contract_mismatch"
    )


def test_methodology_resource_is_hash_pinned_and_runtime_has_no_form_projection() -> None:
    raw = (PACKAGE_ROOT / GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == (
        GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE_SHA256
    )
    source = inspect.getsource(tax_base_module).lower()
    for forbidden in (
        "section2",
        "line_010",
        "line_020",
        "line_030",
        "line_040",
        "line_050",
        "line_060",
        "income_group_code",
        "xml.etree",
        "reportlab",
        '"2025"',
        '"resident_individual"',
        '"organized_market_securities_outside_iis"',
        '"rub"',
    ):
        assert forbidden not in source


def test_new_behavior_executes_from_a_closed_package_copy(tmp_path: Path) -> None:
    package_copy = tmp_path / "broker_reports_gate1"
    shutil.copytree(
        PACKAGE_ROOT,
        package_copy,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    script = """
from broker_reports_gate1 import Gate5PublishedTypedBehaviorRegistryFactory
r=Gate5PublishedTypedBehaviorRegistryFactory.create().describe({'schema_version':'broker_reports_gate5_published_behavior_ref_v1','methodology_id':'ru-ndfl-securities-tax-model-proof','methodology_version':'2026.3-audited','behavior_id':'securities_income_group_tax_base_v0'})
print(r['input_contract_id'])
print(r['output_contract_id'])
"""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.splitlines() == [
        GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
        GATE5_INCOME_GROUP_TAX_BASE_MODEL_SCHEMA_VERSION,
    ]


def test_income_group_methodology_hash_drift_fails_in_package_copy(
    tmp_path: Path,
) -> None:
    package_copy = tmp_path / "broker_reports_gate1"
    shutil.copytree(
        PACKAGE_ROOT,
        package_copy,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    resource = (
        package_copy
        / GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_RESOURCE
    )
    resource.write_bytes(
        resource.read_bytes().replace(
            b"securities-income-group-tax-base",
            b"unapproved-income-group-tax-base",
            1,
        )
    )
    script = """
from broker_reports_gate1 import Gate5TrustedMethodologyAuthorityFactory
Gate5TrustedMethodologyAuthorityFactory.create().resolve({'schema_version':'broker_reports_gate5_trusted_methodology_ref_v0','methodology_id':'ru-ndfl-securities-tax-model-proof','methodology_version':'2026.3-audited'})
"""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "gate5_trusted_methodology_resource_hash_mismatch" in completed.stderr


def _complete_category(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()
    first, first_context = typed_fixtures._execute_operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="a",
        gross="100.00",
        acquisition="70.00",
        fee="2.00",
    )
    second, _second_context = typed_fixtures._execute_operation_model(
        store=store,
        monkeypatch=monkeypatch,
        ref="b",
        gross="50.00",
        acquisition="28.00",
        fee="2.00",
        fee_documented=False,
    )
    members = [
        typed_fixtures._member("operation-a", "case-a", first["result_payload"]),
        typed_fixtures._member("operation-b", "case-b", second["result_payload"]),
    ]
    aggregate = (
        Gate5RuntimeCapabilityResolverV1Factory.create()
        .resolve(
            {
                "schema_version": GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION,
                "capability_id": "aggregate_complete_category_scope_v0",
            }
        )
        .create_runtime()
    )
    scope = typed_fixtures._scope()
    binding = aggregate.describe_scope(scope=scope, members=members)
    result = aggregate.run(
        scope=scope,
        members=members,
        completeness_evidence=typed_fixtures._completeness(
            binding["scope_binding_sha256"]
        ),
    )
    assert result["status"] == "complete"
    return store, first_context, result["category_tax_model"]


def _valid_input(category: dict) -> dict:
    owner = Gate5IncomeGroupTaxBaseRuntimeFactory.create()
    status = _tagged("resident_individual", "taxpayer-status", "taxpayer_status")
    values = _group_values()
    binding = owner.describe_input(
        category_tax_model=category,
        taxpayer_status=status,
        group_values=values,
    )
    return _behavior_input(
        category=category,
        status=status,
        values=values,
        binding_sha256=binding["input_binding_sha256"],
    )


def _behavior_input(
    *,
    category: dict,
    status: dict,
    values: dict,
    binding_sha256: str,
) -> dict:
    return {
        "schema_version": GATE5_INCOME_GROUP_TAX_BASE_INPUT_SCHEMA_VERSION,
        "category_tax_model": copy.deepcopy(category),
        "taxpayer_status": copy.deepcopy(status),
        "group_values": copy.deepcopy(values),
        "completeness_evidence": {
            "schema_version": (
                GATE5_INCOME_GROUP_TAX_BASE_COMPLETENESS_SCHEMA_VERSION
            ),
            "status": "asserted_complete",
            "coverage_kind": "all_income_and_reductions_in_stable_income_group",
            "input_binding_sha256": binding_sha256,
            "provenance": {
                "source_kind": "user_verified_fact",
                "source_ref": "complete-income-group-2025",
                "input_channel": "income_group_completeness",
            },
        },
    }


def _group_values(
    *,
    other_income: str = "0.00",
    other_expenses: str = "0.00",
    non_taxable: str = "0.00",
    deductions: str = "0.00",
) -> dict:
    return {
        "other_group_income": _tagged_money(
            other_income, "other-income-group-2025"
        ),
        "other_group_allowable_expenses": _tagged_money(
            other_expenses, "other-expenses-group-2025"
        ),
        "non_taxable_income": _tagged_money(
            non_taxable, "non-taxable-group-2025"
        ),
        "tax_deductions": _tagged_money(deductions, "deductions-group-2025"),
    }


def _tagged_money(amount: str, source_ref: str) -> dict:
    return {
        "value": _money(amount),
        "provenance": {
            "source_kind": "user_verified_fact",
            "source_ref": source_ref,
            "input_channel": "income_group_tax_base",
        },
    }


def _tagged(value: str, source_ref: str, input_channel: str) -> dict:
    return {
        "value": value,
        "provenance": {
            "source_kind": "methodology_derived_result",
            "source_ref": f"residency-classification:{source_ref}",
            "input_channel": input_channel,
        },
    }


def _money(amount: str) -> dict[str, str]:
    return {"kind": "money", "amount": amount, "currency": "RUB"}


def _behavior_ref() -> dict[str, str]:
    return {
        "schema_version": GATE5_PUBLISHED_BEHAVIOR_REF_SCHEMA_VERSION,
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": (
            GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION
        ),
        "behavior_id": GATE5_INCOME_GROUP_TAX_BASE_BEHAVIOR_ID,
    }


def _methodology_ref() -> dict[str, str]:
    return {
        "schema_version": "broker_reports_gate5_trusted_methodology_ref_v0",
        "methodology_id": GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        "methodology_version": (
            GATE5_SECURITIES_INCOME_GROUP_TAX_BASE_METHODOLOGY_VERSION
        ),
    }


def _typed_runtime(store):
    return (
        Gate5RuntimeCapabilityResolverV1Factory.create()
        .resolve(
            {
                "schema_version": GATE5_RUNTIME_CAPABILITY_REF_V1_SCHEMA_VERSION,
                "capability_id": "execute_published_typed_behavior_v1",
            }
        )
        .create_runtime(
            store=store,
            read_enabled=True,
            retention_policy=build_retention_policy(mode="synthetic_dev"),
        )
    )
