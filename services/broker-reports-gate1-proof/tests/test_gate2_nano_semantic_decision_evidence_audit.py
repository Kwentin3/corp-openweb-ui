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
    _json_bytes,
    _sha256_bytes,
    combine_revision_snapshots,
    recover_exact_decision,
    request_token_anatomy,
    validate_local_evidence_output_path,
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
    v3_private = {
        "mode": "v3",
        "repository_revision": (
            "eb5c6011066a524d97aad9ac3b07d2d969f3db87"
        ),
        "receipt_sha256": (
            "39f6a990d233926d7493056570730bdfa82f29df9a63d3f8f9d6cfa0e47dc641"
        ),
        "cases": [{} for _ in range(12)],
    }
    v4_private = {
        "mode": "v4",
        "repository_revision": (
            "2b451e7a1168165b1b1902c0c635b7b8bf246715"
        ),
        "receipt_sha256": (
            "c371262b9c9d6911b2bb250f441f1f158e5ed1259e93d2d3eefa6df5280f5426"
        ),
        "cases": [{} for _ in range(12)],
    }
    v3_safe = {
        "mode": "v3",
        "repository_revision": v3_private["repository_revision"],
        "receipt_sha256": v3_private["receipt_sha256"],
        "cases_total": 12,
        "cases": v3_cases,
        "checks": {"all_checks": True},
        "private_annex_sha256": _sha256_bytes(_json_bytes(v3_private)),
    }
    v4_safe = {
        "mode": "v4",
        "repository_revision": v4_private["repository_revision"],
        "receipt_sha256": v4_private["receipt_sha256"],
        "cases_total": 12,
        "cases": v4_cases,
        "checks": {"all_checks": True},
        "private_annex_sha256": _sha256_bytes(_json_bytes(v4_private)),
    }

    _private, safe = combine_revision_snapshots(
        v3_private=v3_private,
        v3_safe=v3_safe,
        v4_private=v4_private,
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


def test_safe_payload_rejects_neighbour_literal():
    safe = {
        "provider_calls_created_by_audit": 0,
        "checks": {"provider_calls_zero": True},
        "summary": "private neighbour value",
    }
    private = {
        "cases": [
            {
                "manifest_case": {
                    "cells": [],
                    "neighbour_cells": [
                        {"literal": "private neighbour value"}
                    ],
                }
            }
        ]
    }

    with pytest.raises(
        Gate2NanoSemanticEvidenceAuditError,
        match="literal_in_safe_payload",
    ):
        _validate_safe_payload(safe=safe, private=private)


def test_output_paths_must_stay_under_service_local(tmp_path):
    allowed = (
        tmp_path
        / "services"
        / "broker-reports-gate1-proof"
        / "local"
        / "evidence.json"
    )
    validate_local_evidence_output_path(allowed)

    with pytest.raises(
        Gate2NanoSemanticEvidenceAuditError,
        match="output_outside_local_boundary",
    ):
        validate_local_evidence_output_path(tmp_path / "docs" / "leak.json")


def test_anti_drift_contract_forbids_provider_and_factory_bypass():
    assert "Gate2FinancialEvidenceSuccessorRunnerFactory.create" in (
        FACTORY_REQUIRED
    )
    assert "Gate2OpenWebUIRequestBuilder.build" in FACTORY_REQUIRED
    assert "must not create a provider client" in FORBIDDEN
    assert "infer raw response bytes" in FORBIDDEN
