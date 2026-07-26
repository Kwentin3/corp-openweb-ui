from __future__ import annotations

import copy

import pytest

from broker_reports_gate1.gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_successor_projection import (
    Gate2FinancialEvidenceSuccessorProviderProjectionFactory,
)
from broker_reports_gate1.gate2_model_requests import (
    Gate2OpenWebUIRequestBuilder,
)
from scripts.gate2_nano_semantic_decision_evidence_audit import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    Gate2NanoSemanticEvidenceAuditError,
    _mode_contract,
    _runner,
    _validate_safe_payload,
    combine_revision_snapshots,
    recover_exact_decision,
    request_token_anatomy,
)
from scripts.live_gate2_financial_successor_qualification_v2 import (
    EXACT_MODEL_ID,
    build_successor_qualification_fixture_v2,
)


def _artifact_hash(*, case, decision: dict, prefix: str) -> str:
    validated = Gate2FinancialEvidenceValidatedDecisionFactory(
        contract=case.scope.decision_contract
    ).create(decision)
    artifact = Gate2FinancialEvidenceMaterializerFactory(
        registry=case.scope.decision_contract.registry,
        source_package=case.scope.source_package,
        execution_metadata=FinancialEvidenceExecutionMetadata(
            execution_ref=f"execution:{prefix}:{case.case_id}",
            decision_validation_ref=(
                f"validation:{prefix}:{case.case_id}"
            ),
        ),
    ).create().materialize(validated_decision=validated)
    return artifact["integrity_hash"]


@pytest.mark.parametrize(
    "case_id",
    (
        "syn_successor_v2_unique_cash",
        "syn_successor_v2_unsupported_shape",
    ),
)
def test_exact_artifact_hash_recovers_one_semantic_decision(case_id):
    fixture = build_successor_qualification_fixture_v2()
    case = next(item for item in fixture.cases if item.case_id == case_id)
    expected = copy.deepcopy(case.expected_model_output)
    target_hash = _artifact_hash(
        case=case,
        decision=expected,
        prefix="managed-shadow-qualification",
    )

    recovered = recover_exact_decision(
        case=case,
        observed_disposition=expected["decision"]["disposition"],
        observed_input_type_id=expected["decision"].get(
            "input_type_id"
        ),
        target_artifact_hash=target_hash,
        execution_prefix="managed-shadow-qualification",
    )

    assert recovered["matching_candidates"] == 1
    assert recovered["decision"] == expected


def test_v4_request_anatomy_measures_pack_and_does_not_invent_skill_tokens():
    fixture = build_successor_qualification_fixture_v2()
    case = fixture.cases[0]
    runner = _runner(fixture=fixture, mode="v4")
    package = runner.model_input(
        scope=case.scope,
        source_context=case.source_context,
    )
    projection = (
        Gate2FinancialEvidenceSuccessorProviderProjectionFactory()
        .create(contract=case.scope.decision_contract)
    )
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=_mode_contract("v4")["request_profile"]
    ).build(
        prompt=runner.prompt,
        package=package,
        model_id=EXACT_MODEL_ID,
        response_format=projection.response_format,
    )

    anatomy = request_token_anatomy(
        mode="v4",
        prompt=runner.prompt,
        package=package,
        response_format=projection.response_format,
        form_data=form_data,
        recorded_input_tokens=1,
    )

    components = anatomy["components"]
    assert components["skill_content_transmitted_utf8_bytes"] == 0
    assert components["semantic_pack_utf8_bytes"] > (
        components["source_context_utf8_bytes"]
    )
    assert anatomy["repository_estimated_input_tokens"] > 0
    assert anatomy["provider_token_component_allocation_available"] is False


def _safe_case(case_id: str) -> dict:
    return {
        "case_id": case_id,
        "expected_disposition": "unclassified_financial_input",
        "expected_input_type_id": None,
        "observed_disposition": "unclassified_financial_input",
        "observed_input_type_id": None,
        "eligible_registry_types_total": 0,
        "provider_recorded_input_tokens": 1,
    }


def test_cross_revision_comparison_preserves_raw_response_gap():
    v3_cases = [_safe_case(f"case_{index}") for index in range(12)]
    v4_cases = copy.deepcopy(v3_cases)
    v4_cases[0]["observed_disposition"] = "typed_input"
    v4_cases[0]["observed_input_type_id"] = "type_v1"
    v3_safe = {"mode": "v3", "cases_total": 12, "cases": v3_cases}
    v4_safe = {"mode": "v4", "cases_total": 12, "cases": v4_cases}

    _private, safe = combine_revision_snapshots(
        v3_private={"cases": []},
        v3_safe=v3_safe,
        v4_private={"cases": []},
        v4_safe=v4_safe,
    )

    assert safe["decision_changes_total"] == 1
    assert (
        safe["case_level_completeness"]["raw_provider_response_bytes"]
        == "unavailable_0_of_12"
    )
    assert (
        safe["case_level_completeness"][
            "exact_semantic_provider_decision"
        ]
        == "uniquely_recovered_for_12_of_12"
    )


def test_safe_payload_rejects_source_refs():
    safe = {
        "provider_calls_created_by_audit": 0,
        "checks": {"provider_calls_zero": True},
        "source_value_ref": "forbidden",
    }
    private = {"cases": [{"manifest_case": {"cells": []}}]}

    with pytest.raises(
        Gate2NanoSemanticEvidenceAuditError,
        match="safe_payload_invalid",
    ):
        _validate_safe_payload(safe=safe, private=private)


def test_anti_drift_contract_forbids_provider_and_factory_bypass():
    assert "Gate2FinancialEvidenceSuccessorRunnerFactory.create" in (
        FACTORY_REQUIRED
    )
    assert "Gate2OpenWebUIRequestBuilder.build" in FACTORY_REQUIRED
    assert "must not create a provider client" in FORBIDDEN
    assert "infer raw response bytes" in FORBIDDEN
