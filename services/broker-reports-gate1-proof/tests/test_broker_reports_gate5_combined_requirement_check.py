from __future__ import annotations

import ast
import copy
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from broker_reports_gate1 import (
    GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION,
    GATE5_COMBINED_REQUIREMENT_CHECK_RESULT_SCHEMA_VERSION,
    GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    Gate4FinancialCaseRuntimeFactory,
    Gate5CombinedRequirementCheckError,
    Gate5CombinedRequirementCheckRuntime,
    Gate5CombinedRequirementCheckRuntimeFactory,
    Gate5SupplementalFactRuntimeFactory,
    build_retention_policy,
)
from broker_reports_gate1 import (
    gate5_combined_requirement_check as combined_module,
)
from broker_reports_gate1.gate5_combined_requirement_check import (
    FACTORY_REQUIRED,
    FORBIDDEN,
)
from test_broker_reports_gate4_sql_materialization import _publish_document


def test_combined_check_moves_from_missing_to_persistent_supplemental_satisfied(
    tmp_path: Path,
) -> None:
    config, store, context = _representative_case(tmp_path)
    gate4 = Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create()
    financial_case_before = gate4.list_by_financial_type(
        context=context,
        financial_type="SECURITY_DISPOSAL",
    )
    assert len(financial_case_before) == 1
    assert "acquisition_cost" not in {
        role["role"] for role in financial_case_before[0]["roles"]
    }
    methodology = _methodology(
        requirement_id="acquisition-cost-required",
        value_key="acquisition_cost",
    )
    unchanged_methodology = copy.deepcopy(methodology)

    before_supplemental = _combined_runtime(store).check(
        methodology=methodology,
        supplemental_fact_refs=[],
        context=context,
    )

    assert methodology == unchanged_methodology
    assert before_supplemental == {
        "schema_version": GATE5_COMBINED_REQUIREMENT_CHECK_RESULT_SCHEMA_VERSION,
        "requirements": [
            {
                "requirement_id": "acquisition-cost-required",
                "financial_type": "SECURITY_DISPOSAL",
                "value_key": "acquisition_cost",
                "subject_ref": "security-disposal-1",
                "status": "missing",
                "checks": {
                    "financial_case": "partial",
                    "supplemental_facts": "missing",
                },
                "source": None,
            }
        ],
        "summary": {
            "requirements_total": 1,
            "satisfied": 0,
            "missing": 1,
        },
    }

    supplemental = _supplemental_runtime(store).put(
        supplemental_input={
            "schema_version": GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
            "requirement_ref": "acquisition-cost-required",
            "subject_ref": "security-disposal-1",
            "fact_key": "acquisition_cost",
            "value": {
                "kind": "money",
                "amount": "70000.00",
                "currency": "RUB",
            },
        },
        context=context,
    )

    reopened_store = ArtifactStoreFactory(config).create()
    satisfied = _combined_runtime(reopened_store).check(
        methodology=methodology,
        supplemental_fact_refs=[supplemental["supplemental_fact_ref"]],
        context=context,
    )

    requirement = satisfied["requirements"][0]
    assert satisfied["summary"] == {
        "requirements_total": 1,
        "satisfied": 1,
        "missing": 0,
    }
    assert requirement["status"] == "satisfied"
    assert requirement["checks"] == {
        "financial_case": "partial",
        "supplemental_facts": "found",
    }
    assert requirement["source"] == {
        "source_kind": "supplemental_fact",
        "supplemental_fact_ref": supplemental["supplemental_fact_ref"],
        "value": {
            "kind": "money",
            "amount": "70000.00",
            "currency": "RUB",
        },
        "scope_binding": supplemental["fact"]["scope_binding"],
        "provenance": {
            "source_kind": "user_provided_supplemental",
            "provided_by": "authenticated_user",
            "gate4_derived": False,
            "captured_via": "gate5_supplemental_fact_boundary_v0",
        },
    }

    financial_requirement = _combined_runtime(reopened_store).check(
        methodology=_methodology(
            requirement_id="disposal-amount-required",
            value_key="amount",
        ),
        supplemental_fact_refs=[],
        context=context,
    )["requirements"][0]
    assert financial_requirement["status"] == "satisfied"
    assert financial_requirement["checks"] == {
        "financial_case": "found",
        "supplemental_facts": "not_needed",
    }
    assert financial_requirement["source"] == {
        "source_kind": "financial_case",
        "matches": [
            {
                "fact_id": financial_case_before[0]["fact_id"],
                "role": "amount",
                "value": "60.00",
            }
        ],
    }

    financial_case_after = Gate4FinancialCaseRuntimeFactory(
        store=reopened_store,
        read_enabled=True,
    ).create().list_by_financial_type(
        context=context,
        financial_type="SECURITY_DISPOSAL",
    )
    assert financial_case_after == financial_case_before


def test_binding_scope_and_conflict_inputs_fail_closed(tmp_path: Path) -> None:
    _config, store, context = _representative_case(tmp_path)
    combined = _combined_runtime(store)
    methodology = _methodology(
        requirement_id="acquisition-cost-required",
        value_key="acquisition_cost",
    )
    mismatched = _put_supplemental(
        store=store,
        context=context,
        subject_ref="security-disposal-other",
    )

    not_eligible = combined.check(
        methodology=methodology,
        supplemental_fact_refs=[mismatched],
        context=context,
    )

    assert not_eligible["requirements"][0]["status"] == "missing"
    assert not_eligible["requirements"][0]["source"] is None

    foreign_ref = _put_supplemental(
        store=store,
        context=replace(context, user_id="foreign-user"),
        subject_ref="security-disposal-1",
    )
    with pytest.raises(ArtifactStoreError) as foreign_error:
        combined.check(
            methodology=methodology,
            supplemental_fact_refs=[foreign_ref],
            context=context,
        )
    assert foreign_error.value.code == "artifact_access_denied"

    first_match = _put_supplemental(
        store=store,
        context=context,
        subject_ref="security-disposal-1",
    )
    second_match = _put_supplemental(
        store=store,
        context=context,
        subject_ref="security-disposal-1",
    )
    with pytest.raises(Gate5CombinedRequirementCheckError) as ambiguous:
        combined.check(
            methodology=methodology,
            supplemental_fact_refs=[first_match, second_match],
            context=context,
        )
    assert (
        ambiguous.value.code
        == "gate5_combined_requirement_supplemental_ambiguous"
    )

    invalid = copy.deepcopy(methodology)
    invalid["requirements"][0]["user_id"] = "caller-user"
    with pytest.raises(Gate5CombinedRequirementCheckError) as invalid_error:
        combined.check(
            methodology=invalid,
            supplemental_fact_refs=[],
            context=context,
        )
    assert invalid_error.value.code == "gate5_combined_requirement_invalid"


def test_factory_composes_only_g5_2_and_g5_3_read_boundaries() -> None:
    factory_source = inspect.getsource(
        Gate5CombinedRequirementCheckRuntimeFactory.create
    )
    runtime_source = inspect.getsource(Gate5CombinedRequirementCheckRuntime)
    module_source = inspect.getsource(combined_module)
    tree = ast.parse(module_source)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)

    assert "Gate5CombinedRequirementCheckRuntimeFactory.create" in FACTORY_REQUIRED
    assert "Gate5MethodologySelectionRuntimeFactory.create" in FACTORY_REQUIRED
    assert "Gate5SupplementalFactRuntimeFactory.create" in FACTORY_REQUIRED
    assert "direct Gate 4, ArtifactStore, SQL or source reads" in FORBIDDEN
    assert "Gate5MethodologySelectionRuntimeFactory(" in factory_source
    assert "Gate5SupplementalFactRuntimeFactory(" in factory_source
    assert "self._financial.select(" in runtime_source
    assert "self._supplemental.get(" in runtime_source
    assert "self._supplemental.put(" not in runtime_source
    assert imports == {
        "__future__",
        "copy",
        "re",
        "typing",
        "artifact_models",
        "gate5_methodology_selection",
        "gate5_supplemental_fact",
    }
    for forbidden_read in (
        "Gate4FinancialCaseRuntimeFactory(",
        "ArtifactResolver(",
        "get_record_unchecked(",
        "list_by_case_context(",
        "sqlite3",
        "CanonicalReader",
    ):
        assert forbidden_read not in runtime_source
    for representative_literal in (
        "SECURITY_DISPOSAL",
        "acquisition_cost",
        "70000.00",
    ):
        assert representative_literal not in module_source


def _representative_case(
    tmp_path: Path,
) -> tuple[ArtifactStoreConfig, object, ArtifactAccessContext]:
    config = ArtifactStoreConfig(
        mode="sqlite",
        sqlite_path=tmp_path / "artifacts.sqlite3",
        payload_root=tmp_path / "payloads",
    )
    store = ArtifactStoreFactory(config).create()
    context = ArtifactAccessContext(
        user_id="g5-combined-user",
        normalization_run_id="g5-combined-run-1",
        case_id="g5-combined-case",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    _publish_document(
        store=store,
        context=context,
        document_id="gate5-combined-document",
        financial_types=("SECURITY_DISPOSAL",),
        sidecar_artifact_id="g3-v2-gate5-combined",
        created_at="2026-08-09T12:00:00+00:00",
    )
    Gate4FinancialCaseRuntimeFactory(
        store=store,
        read_enabled=True,
    ).create().rebuild_case(context=context)
    return config, store, context


def _combined_runtime(store) -> Gate5CombinedRequirementCheckRuntime:
    return Gate5CombinedRequirementCheckRuntimeFactory(
        store=store,
        read_enabled=True,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _supplemental_runtime(store):
    return Gate5SupplementalFactRuntimeFactory(
        store=store,
        retention_policy=build_retention_policy(mode="synthetic_dev"),
    ).create()


def _methodology(*, requirement_id: str, value_key: str) -> dict:
    return {
        "schema_version": GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION,
        "requirements": [
            {
                "requirement_id": requirement_id,
                "financial_type": "SECURITY_DISPOSAL",
                "value_key": value_key,
                "subject_ref": "security-disposal-1",
            }
        ],
    }


def _put_supplemental(
    *,
    store,
    context: ArtifactAccessContext,
    subject_ref: str,
) -> str:
    return _supplemental_runtime(store).put(
        supplemental_input={
            "schema_version": GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
            "requirement_ref": "acquisition-cost-required",
            "subject_ref": subject_ref,
            "fact_key": "acquisition_cost",
            "value": {
                "kind": "money",
                "amount": "70000.00",
                "currency": "RUB",
            },
        },
        context=context,
    )["supplemental_fact_ref"]
