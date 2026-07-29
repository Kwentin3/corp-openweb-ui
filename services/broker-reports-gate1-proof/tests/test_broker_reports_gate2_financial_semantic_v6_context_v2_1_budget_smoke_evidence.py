from __future__ import annotations

import copy
import json
import socket
from pathlib import Path
from typing import Any

import pytest

from broker_reports_gate1.gate2_economy_budget import (
    Gate2EconomyBudgetSessionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_budget_smoke import (
    Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjector,
    build_financial_semantic_v6_context_v2_1_budget_smoke_plan,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_budget_smoke_plan import (
    financial_semantic_v6_context_v2_1_budget_smoke_operation_identity,
    resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (
    Gate2FinancialSemanticV6ContextV21BudgetSmokeEvidenceBundle,
    Gate2FinancialSemanticV6ContextV21BudgetSmokeFailureEvidenceBundle,
    Gate2FinancialSemanticV6DecisionEvidenceError,
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    replay_financial_semantic_v6_context_v2_1_budget_smoke_decision,
    restore_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence,
    serialize_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence,
    validate_financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_model_contracts import (
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (
    Gate2OpenWebUIRequestBuilder,
)
from broker_reports_gate1.gate2_provider_adapters import (
    CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE,
    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
    Gate2NativeProviderTransportConfig,
    Gate2ProviderAdapterFactory,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = (
    ROOT
    / "benchmarks"
    / "gate2_financial_semantic_v6_outcome_audit_v1"
    / "manifest.json"
)
HISTORICAL_PATH = ROOT / "benchmarks" / "gate2_financial_semantic_v6" / "manifest.json"
BASE_PATH = ROOT / "benchmarks" / "gate2_financial_successor_v2" / "manifest.json"
SNAPSHOT_KEY = b"context-v2-1-budget-smoke-evidence-snapshot"
CONTINUATION_KEY = b"context-v2-1-budget-smoke-evidence-continuation"
PRIVATE_RESPONSE_ID = "response-evidence-private-only"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _project(*, context: dict[str, Any], slot):
    case = context["cases"][slot.case_id]
    return Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjector(
        registry=context["registry"]
    )(
        case=case,
        provider_profile=gate2_provider_profile(slot.provider_profile_id),
        exact_model_id=slot.exact_model_id,
        request_profile=slot.request_profile,
        parameters=slot.parameters,
    )


def _adapter_for_slot(slot):
    return Gate2ProviderAdapterFactory(
        profile=gate2_provider_profile(slot.provider_profile_id),
        capability_probe=True,
        native_transport_config=Gate2NativeProviderTransportConfig(
            timeout_seconds=slot.transport_contract["timeout_seconds"],
        ),
    ).create()


def _local_answer(
    *,
    case: Any,
    expected_answer: dict[str, Any],
) -> dict[str, Any]:
    if expected_answer["disposition"] == "unclassified_financial_input":
        return {
            "choice": "unclassified",
            "reason": expected_answer["reason_code"],
        }
    matches = tuple(
        item
        for item in case.packet.context_v2_mapping_receipt.choice_restoration
        if item["typed_option_id"] == expected_answer["typed_option_id"]
    )
    assert len(matches) == 1
    return {"choice": matches[0]["choice_key"]}


def _raw_response(
    *,
    provider_profile_id: str,
    exact_model_id: str,
    local_answer: dict[str, Any],
) -> dict[str, Any]:
    if provider_profile_id == "anthropic_claude":
        return {
            "id": f"{PRIVATE_RESPONSE_ID}:anthropic",
            "model": exact_model_id,
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        local_answer,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                }
            ],
            "stop_reason": "end_turn",
            "usage": {
                "input_tokens": 101,
                "output_tokens": 7,
            },
        }
    provider_output = {"broker_reports_gate2_choice": copy.deepcopy(local_answer)}
    return {
        "id": PRIVATE_RESPONSE_ID,
        "model": exact_model_id,
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        provider_output,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 101,
            "completion_tokens": 7,
            "total_tokens": 108,
        },
    }


def _success_evidence(
    context: dict[str, Any],
    *,
    provider_profile_id: str,
):
    plan = context["plan"]
    slot = next(
        item
        for item in plan.slots
        if item.provider_profile_id == provider_profile_id
        and item.immutable_model_id_proven
    )
    case = context["cases"][slot.case_id]
    projection = _project(context=context, slot=slot)
    operation_identity = (
        financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
            plan=plan,
            slot=slot,
        )
    )
    expected_answer = (
        resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer(
            plan=plan,
            slot=slot,
            fixture=context["fixture"],
            outcome_audit_manifest=context["audit_manifest"],
        )
    )
    local_answer = _local_answer(
        case=case,
        expected_answer=expected_answer,
    )
    raw_response = _raw_response(
        provider_profile_id=slot.provider_profile_id,
        exact_model_id=slot.exact_model_id,
        local_answer=local_answer,
    )
    adapter = _adapter_for_slot(slot)
    session = Gate2EconomyBudgetSessionFactory().create(
        request_profile=slot.request_profile,
    )
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=slot.request_profile,
    ).build_from_sealed_context_v2_1(
        model_visible_request=(projection.sealed_request.model_visible_request),
        model_id=slot.exact_model_id,
    )
    authorization = session.prepare_call(
        form_data=form_data,
        model_id=slot.exact_model_id,
        provider_profile_id=slot.provider_profile_id,
        operation_identity=operation_identity,
    )
    prepared_request = adapter.prepare_context_v2_1_budget_smoke_form_data(
        form_data=authorization.prepared_form_data,
        response_format=projection.sealed_request.response_format,
    )
    assert prepared_request == projection.prepared_request
    adapter_output = adapter.extract_context_v2_1_budget_smoke_prepared_content(
        raw_response,
        prepared_request=prepared_request,
        canonical_schema=(
            case.choice_contract.context_v2_1_response_profile.canonical_schema()
        ),
        model_visible_request=(projection.sealed_request.model_visible_request),
        exact_model_id=slot.exact_model_id,
        operation_identity=operation_identity,
    )
    execution_metadata = adapter.context_v2_1_budget_smoke_execution_metadata(
        payload=raw_response,
        requested_model_id=slot.exact_model_id,
        duration_ms=19,
        prepared_request=prepared_request,
        transport_contract=projection.transport_contract,
    )
    budget_receipt = session.finalize_call(
        authorization=authorization,
        execution_metadata=execution_metadata,
    )
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=context["registry"],
        exact_model_id=slot.exact_model_id,
        provider_profile_id=slot.provider_profile_id,
    ).create_context_v2_1_budget_smoke_candidate(
        plan=plan,
        plan_slot=slot,
        expected_answer=expected_answer,
        operation_identity=operation_identity,
        sealed_request=projection.sealed_request,
        prepared_request=prepared_request,
        adapter_extracted_output=adapter_output,
        raw_provider_response=raw_response,
        execution_metadata=execution_metadata,
        economy_budget_receipt=budget_receipt,
        choice_contract=case.choice_contract,
        packet=case.packet,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
    )
    return {
        "slot": slot,
        "case": case,
        "projection": projection,
        "operation_identity": operation_identity,
        "expected_answer": expected_answer,
        "local_answer": local_answer,
        "adapter_output": adapter_output,
        "raw_response": raw_response,
        "prepared_request": prepared_request,
        "execution_metadata": execution_metadata,
        "budget_receipt": budget_receipt,
        "evidence": evidence,
    }


@pytest.fixture(scope="module")
def evidence_context() -> dict[str, Any]:
    audit_manifest = _read(AUDIT_PATH)
    historical_manifest = _read(HISTORICAL_PATH)
    base_manifest = _read(BASE_PATH)
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=registry,
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=historical_manifest,
        base_manifest=base_manifest,
    )
    plan = build_financial_semantic_v6_context_v2_1_budget_smoke_plan(
        fixture=fixture,
        outcome_audit_manifest=audit_manifest,
        registry=registry,
    )
    context = {
        "audit_manifest": audit_manifest,
        "fixture": fixture,
        "registry": registry,
        "plan": plan,
        "cases": {item.case_id: item for item in fixture.semantic_cases},
    }
    context["success"] = _success_evidence(
        context,
        provider_profile_id="openai_gpt",
    )
    context["anthropic_success"] = _success_evidence(
        context,
        provider_profile_id="anthropic_claude",
    )
    return context


def _reseal_private_evidence(value: dict[str, Any]) -> None:
    material = {
        key: copy.deepcopy(item)
        for key, item in value.items()
        if key != "private_evidence_hash"
    }
    value["private_evidence_hash"] = sha256_json(material)


def test_success_private_evidence_binds_exact_live_artifacts_and_safe_summary(
    evidence_context,
) -> None:
    success = evidence_context["success"]
    evidence = success["evidence"]
    private = evidence.private_evidence
    safe = evidence.safe_receipt

    assert isinstance(
        evidence,
        Gate2FinancialSemanticV6ContextV21BudgetSmokeEvidenceBundle,
    )
    assert private["exact_prepared_request"] == (success["prepared_request"].__dict__)
    assert private["raw_provider_response"] == success["raw_response"]
    assert private["adapter_extracted_output"] == (success["adapter_output"])
    assert private["provider_execution_metadata"] == (
        success["execution_metadata"].__dict__
    )
    assert private["economy_budget_receipt"] == (success["budget_receipt"])
    assert private["transport_policy"] == (CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY)
    assert private["transport_contract"] == (
        success["projection"].transport_contract.safe_snapshot()
    )
    assert private["transport_contract_hash"] == (
        success["projection"].transport_contract.integrity_hash
    )
    assert private["provider_execution_metadata"]["transport_type"] == (
        CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE
    )
    assert private["normalized_semantic_choice"] == (success["expected_answer"])
    assert private["field_level_diff"]["all_fields_match"] is True
    assert all(row["exact_match"] for row in private["field_level_diff"]["fields"])
    assert private["execution_accounting"] == {
        "local_invocations_total": 1,
        "provider_submissions_total": 1,
        "provider_responses_total": 1,
        "semantic_repair_total": 0,
        "retry_total": 0,
        "repair_total": 0,
        "fallback_total": 0,
    }
    assert private["provider_metrics"] == {
        "input_tokens": 101,
        "output_tokens": 7,
        "total_tokens": 108,
        "actual_cost_usd": success["budget_receipt"]["actual_cost_usd"],
        "latency_ms": 19,
    }
    safe_text = json.dumps(safe, sort_keys=True)
    assert PRIVATE_RESPONSE_ID not in safe_text
    assert "raw_provider_response" not in safe_text
    assert "exact_model_visible_request" not in safe_text
    assert (
        safe["hashes"]["raw_execution_output_hash"]
        == (private["raw_provider_response_hash"])
    )
    assert safe["verdicts"]["technical"] == "TECHNICAL_SMOKE_PASSED"
    assert safe["verdicts"]["semantic"] == "SEMANTIC_SMOKE_PASSED"
    assert safe["transport"] == {
        "policy": private["transport_policy"],
        "contract": private["transport_contract"],
        "contract_hash": private["transport_contract_hash"],
    }
    assert (
        safe["hashes"]["transport_contract_hash"] == private["transport_contract_hash"]
    )
    validate_financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle(
        evidence_bundle=evidence,
        plan=evidence_context["plan"],
        plan_slot=success["slot"],
    )


def test_post_extraction_failure_binds_exact_output_to_terminal_response(
    evidence_context,
) -> None:
    success = evidence_context["success"]
    case = success["case"]
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=evidence_context["registry"],
        exact_model_id=success["slot"].exact_model_id,
        provider_profile_id=success["slot"].provider_profile_id,
    ).create_context_v2_1_budget_smoke_failure(
        plan=evidence_context["plan"],
        plan_slot=success["slot"],
        operation_identity=success["operation_identity"],
        sealed_request=success["projection"].sealed_request,
        prepared_request=success["prepared_request"],
        lifecycle={
            "local_invocations_total": 1,
            "provider_submissions_total": 1,
            "provider_responses_total": 1,
            "semantic_repair_total": 0,
            "retry_total": 0,
            "repair_total": 0,
            "fallback_total": 0,
        },
        expected_answer=success["expected_answer"],
        failure_code=("financial_semantic_v6_context_v2_1_choice_reason_invalid"),
        failure_class="Gate2FinancialSemanticV6DecisionEvidenceError",
        error_category="invalid_response",
        raw_output=success["raw_response"],
        adapter_extracted_output=success["adapter_output"],
        execution_metadata=success["execution_metadata"],
        economy_budget_receipt=success["budget_receipt"],
        elapsed_ms=19,
        choice_contract=case.choice_contract,
        packet=case.packet,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
    )

    private = evidence.private_evidence
    assert private["adapter_extracted_output"] == success["adapter_output"]
    assert private["adapter_extracted_output_hash"] == sha256_json(
        success["adapter_output"]
    )
    assert private["raw_output"] == success["raw_response"]
    assert (
        evidence.safe_receipt["hashes"]["adapter_extracted_output_hash"]
        == private["adapter_extracted_output_hash"]
    )
    validate_financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle(
        evidence_bundle=evidence,
        plan=evidence_context["plan"],
        plan_slot=success["slot"],
    )

    tampered = copy.deepcopy(private)
    tampered["raw_output"]["choices"][0]["message"]["content"] = json.dumps(
        {
            "broker_reports_gate2_choice": {
                "choice": "unclassified",
                "reason": "no_registry_type",
            }
        },
        separators=(",", ":"),
    )
    tampered["raw_output_hash"] = sha256_json(tampered["raw_output"])
    _reseal_private_evidence(tampered)
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
        match="budget_smoke_failure_adapter_output_invalid",
    ):
        serialize_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
            private_evidence=tampered,
        )


def test_anthropic_native_evidence_accepts_canonical_request_without_stream(
    evidence_context,
) -> None:
    success = evidence_context["anthropic_success"]
    private = success["evidence"].private_evidence

    assert success["slot"].provider_adapter_id == ("anthropic_native_messages")
    assert "stream" not in private["exact_final_provider_request"]
    assert private["raw_provider_response"] == success["raw_response"]
    assert private["adapter_extracted_output"] == (success["adapter_output"])
    assert private["normalized_semantic_choice"] == (success["expected_answer"])
    assert private["technical_verdict"] == "TECHNICAL_SMOKE_PASSED"
    validate_financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle(
        evidence_bundle=success["evidence"],
        plan=evidence_context["plan"],
        plan_slot=success["slot"],
    )


def test_private_restore_and_offline_replay_are_exact_and_network_free(
    evidence_context,
    monkeypatch,
) -> None:
    success = evidence_context["success"]
    evidence = success["evidence"]
    serialized = (
        serialize_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
            private_evidence=evidence.private_evidence,
        )
    )
    restored = restore_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
        serialized=serialized,
    )
    assert restored == evidence.private_evidence

    def _network_forbidden(*_args, **_kwargs):
        raise AssertionError("offline replay attempted network access")

    monkeypatch.setattr(socket.socket, "connect", _network_forbidden)
    replay = replay_financial_semantic_v6_context_v2_1_budget_smoke_decision(
        private_evidence=restored,
        safe_receipt=evidence.safe_receipt,
        plan=evidence_context["plan"],
        plan_slot=success["slot"],
        expected_answer=success["expected_answer"],
        expected_sealed_request=(success["projection"].sealed_request),
        expected_prepared_request=success["prepared_request"],
        choice_contract=success["case"].choice_contract,
        packet=success["case"].packet,
        evidence_bundle=success["case"].evidence_bundle,
        source_package=success["case"].scope.source_package,
        compilation=success["case"].compilation,
        registry=evidence_context["registry"],
    )
    assert replay.status == "EXACT"
    assert replay.materialized_artifact == evidence.materialized_artifact
    assert (
        replay.private_evidence_hash
        == (evidence.private_evidence["private_evidence_hash"])
    )
    assert replay.provider_calls_total == 0
    assert replay.provider_responses_total == 0
    assert replay.retry_total == replay.repair_total == 0
    assert replay.fallback_total == 0


def test_resealed_raw_response_tamper_fails_closed(
    evidence_context,
) -> None:
    private = copy.deepcopy(evidence_context["success"]["evidence"].private_evidence)
    private["raw_provider_response"]["id"] = "forged-response-id"
    private["raw_provider_response_hash"] = sha256_json(
        private["raw_provider_response"]
    )
    private["replay_authorities"]["raw_provider_response_hash"] = private[
        "raw_provider_response_hash"
    ]
    _reseal_private_evidence(private)

    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
        match="raw_execution_metadata_invalid",
    ):
        serialize_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
            private_evidence=private,
        )


def test_resealed_prepared_request_tamper_fails_closed(
    evidence_context,
) -> None:
    private = copy.deepcopy(evidence_context["success"]["evidence"].private_evidence)
    private["exact_prepared_request"]["form_data"]["stream"] = True
    private["exact_final_provider_request"]["stream"] = True
    private["prepared_request_hash"] = sha256_json(private["exact_prepared_request"])
    private["final_provider_request_hash"] = sha256_json(
        private["exact_final_provider_request"]
    )
    private["replay_authorities"]["prepared_request_hash"] = private[
        "prepared_request_hash"
    ]
    _reseal_private_evidence(private)

    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ):
        serialize_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
            private_evidence=private,
        )


def test_resealed_direct_transport_metadata_or_contract_tamper_fails_closed(
    evidence_context,
) -> None:
    original = evidence_context["success"]["evidence"].private_evidence

    forged_metadata = copy.deepcopy(original)
    forged_metadata["provider_execution_metadata"]["transport_type"] = (
        "legacy_framework_transport"
    )
    forged_metadata["provider_execution_metadata_hash"] = sha256_json(
        forged_metadata["provider_execution_metadata"]
    )
    _reseal_private_evidence(forged_metadata)
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
        match="budget_smoke_(raw_)?execution_metadata_invalid",
    ):
        serialize_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
            private_evidence=forged_metadata,
        )

    forged_contract = copy.deepcopy(original)
    forged_contract["transport_contract"]["endpoint_url"] = (
        "https://example.invalid/v1/chat/completions"
    )
    forged_contract["transport_contract_hash"] = sha256_json(
        forged_contract["transport_contract"]
    )
    forged_contract["replay_authorities"]["transport_contract_hash"] = forged_contract[
        "transport_contract_hash"
    ]
    _reseal_private_evidence(forged_contract)
    with pytest.raises(
        Gate2FinancialSemanticV6DecisionEvidenceError,
        match="budget_smoke_transport_contract_invalid",
    ):
        serialize_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
            private_evidence=forged_contract,
        )


def test_pretransport_unproven_model_failure_is_private_and_zero_call(
    evidence_context,
) -> None:
    plan = evidence_context["plan"]
    slot = next(item for item in plan.slots if item.immutable_model_id_proven is False)
    case = evidence_context["cases"][slot.case_id]
    projection = _project(context=evidence_context, slot=slot)
    operation_identity = (
        financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
            plan=plan,
            slot=slot,
        )
    )
    expected_answer = (
        resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer(
            plan=plan,
            slot=slot,
            fixture=evidence_context["fixture"],
            outcome_audit_manifest=evidence_context["audit_manifest"],
        )
    )
    raw_marker = {"private_pretransport_detail": "not-for-safe-receipt"}
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=evidence_context["registry"],
        exact_model_id=slot.exact_model_id,
        provider_profile_id=slot.provider_profile_id,
    ).create_context_v2_1_budget_smoke_failure(
        plan=plan,
        plan_slot=slot,
        operation_identity=operation_identity,
        sealed_request=projection.sealed_request,
        prepared_request=projection.prepared_request,
        lifecycle={
            "local_invocations_total": 0,
            "provider_submissions_total": 0,
            "provider_responses_total": 0,
            "semantic_repair_total": 0,
            "retry_total": 0,
            "repair_total": 0,
            "fallback_total": 0,
        },
        expected_answer=expected_answer,
        failure_code=("provider_inventory_has_no_dated_immutable_google_model_id"),
        failure_class="provider_model_identity_preflight",
        error_category="infrastructure_provider_failure",
        raw_output=raw_marker,
        choice_contract=case.choice_contract,
        packet=case.packet,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
    )

    assert isinstance(
        evidence,
        Gate2FinancialSemanticV6ContextV21BudgetSmokeFailureEvidenceBundle,
    )
    assert evidence.private_evidence["raw_output"] == raw_marker
    assert evidence.private_evidence["adapter_extracted_output"] is None
    assert evidence.private_evidence["normalized_semantic_choice"] is None
    assert evidence.private_evidence["field_level_diff"]["all_fields_match"] is False
    assert evidence.safe_receipt["counts"]["provider_submissions_total"] == 0
    assert "not-for-safe-receipt" not in json.dumps(
        evidence.safe_receipt,
        sort_keys=True,
    )
    serialized = (
        serialize_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
            private_evidence=evidence.private_evidence,
        )
    )
    assert (
        restore_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
            serialized=serialized,
        )
        == evidence.private_evidence
    )
    validate_financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle(
        evidence_bundle=evidence,
        plan=plan,
        plan_slot=slot,
    )


def test_consumed_pretransport_failure_keeps_local_metadata_without_response(
    evidence_context,
) -> None:
    success = evidence_context["success"]
    slot = success["slot"]
    case = success["case"]
    adapter = _adapter_for_slot(slot)
    local_metadata = adapter.context_v2_1_budget_smoke_execution_metadata(
        payload=None,
        requested_model_id=slot.exact_model_id,
        duration_ms=3,
        prepared_request=success["prepared_request"],
        transport_contract=success["projection"].transport_contract,
    )
    evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
        registry=evidence_context["registry"],
        exact_model_id=slot.exact_model_id,
        provider_profile_id=slot.provider_profile_id,
    ).create_context_v2_1_budget_smoke_failure(
        plan=evidence_context["plan"],
        plan_slot=slot,
        operation_identity=success["operation_identity"],
        sealed_request=success["projection"].sealed_request,
        prepared_request=success["prepared_request"],
        lifecycle={
            "local_invocations_total": 1,
            "provider_submissions_total": 0,
            "provider_responses_total": 0,
            "semantic_repair_total": 0,
            "retry_total": 0,
            "repair_total": 0,
            "fallback_total": 0,
        },
        expected_answer=success["expected_answer"],
        failure_code="provider_client_preflight_unavailable",
        failure_class="provider_configuration",
        error_category="infrastructure_provider_failure",
        raw_output={"diagnostic": "private-local-pretransport"},
        execution_metadata=local_metadata,
        elapsed_ms=3,
        choice_contract=case.choice_contract,
        packet=case.packet,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
    )

    assert (
        evidence.private_evidence["provider_execution_metadata"]
        == local_metadata.__dict__
    )
    assert evidence.private_evidence["economy_budget_receipt"] is None
    assert evidence.safe_receipt["counts"]["provider_submissions_total"] == 0
    assert evidence.safe_receipt["counts"]["provider_responses_total"] == 0
