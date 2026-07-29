from __future__ import annotations

import copy
import hashlib
import inspect
import json
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
from broker_reports_gate1.gate2_financial_semantic_v6_context_linter import (
    Gate2FinancialSemanticV6ContextLinterFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_context_v2_1_budget_smoke_plan import (
    BUDGET_SMOKE_CASES,
    BUDGET_SMOKE_PROVIDER_MODELS,
    Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory,
    Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection,
    financial_semantic_v6_context_v2_1_budget_smoke_operation_identity,
    resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer,
)
from broker_reports_gate1.gate2_financial_semantic_v6_evidence import (
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_outcome_audit import (
    validate_financial_semantic_v6_outcome_audit,
)
from broker_reports_gate1.gate2_financial_semantic_v6_prompt import (
    V6_SEMANTIC_SYSTEM_PROMPT,
)
from broker_reports_gate1.gate2_financial_semantic_v6_qualification import (
    Gate2FinancialSemanticV6QualificationFixtureFactory,
)
from broker_reports_gate1.gate2_financial_semantic_v6_smoke_report import (
    CONTEXT_V2_1_BUDGET_SMOKE_CASE_SCHEMA_VERSION,
    CONTEXT_V2_1_BUDGET_SMOKE_ERROR_CATEGORIES,
    CONTEXT_V2_1_BUDGET_SMOKE_REPORT_SCHEMA_VERSION,
    CONTEXT_V2_1_PROVIDER_PROOF_CASE_SCHEMA_VERSION,
    CONTEXT_V2_1_PROVIDER_PROOF_REPORT_SCHEMA_VERSION,
    SEMANTIC_SMOKE_FAILED,
    SEMANTIC_SMOKE_PASSED,
    TECHNICAL_SMOKE_FAILED,
    TECHNICAL_SMOKE_PASSED,
    Gate2FinancialSemanticV6TransparentSmokeReportError,
    Gate2FinancialSemanticV6TransparentSmokeReportFactory,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    gate2_provider_profile,
)
from broker_reports_gate1.gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE,
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
PACK_PATH = ROOT / "semantic_packs" / "broker_reports_financial_semantic_pack.v1.json"
REASON_CATALOG_PATH = (
    ROOT
    / "managed_assets"
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v2.json"
)
REQUEST_PROFILE = FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
SNAPSHOT_KEY = b"context-v2-1-budget-smoke-report-snapshot-key"
CONTINUATION_KEY = b"context-v2-1-budget-smoke-report-continuation"
PRIVATE_RESPONSE_ID = "PRIVATE_PROVIDER_RESPONSE_ID_SENTINEL"
PRIVATE_CREDENTIAL = "PRIVATE_CREDENTIAL_SENTINEL"
PRIVATE_PATH = "PRIVATE_FILESYSTEM_PATH_SENTINEL"
PRIVATE_REASONING = "PRIVATE_HIDDEN_REASONING_SENTINEL"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class _DeterministicProjector:
    def __init__(self, *, registry) -> None:
        self.registry = registry
        self.budget_session = Gate2EconomyBudgetSessionFactory().create(
            request_profile=REQUEST_PROFILE,
        )
        self.projections: dict[
            tuple[str, str],
            Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection,
        ] = {}

    def __call__(
        self,
        *,
        case,
        provider_profile,
        exact_model_id,
        request_profile,
        parameters,
    ):
        response_profile = case.choice_contract.context_v2_1_response_profile
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "strict": True,
                "schema": response_profile.canonical_schema(),
            },
        }
        serialized_context = json.dumps(
            case.packet.context_v2_candidate.payload,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        sealed_request = Gate2FinancialSemanticV6ContextLinterFactory(
            registry=self.registry
        ).create_context_v2_1(
            packet=case.packet,
            choice_contract=case.choice_contract,
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            system_message=V6_SEMANTIC_SYSTEM_PROMPT,
            serialized_context=serialized_context,
            response_format=response_format,
            mapping_receipt=(case.packet.context_v2_mapping_receipt),
        )
        form_data = Gate2OpenWebUIRequestBuilder(
            request_profile=request_profile,
        ).build_from_sealed_context_v2_1(
            model_visible_request=sealed_request.model_visible_request,
            model_id=exact_model_id,
        )
        authorization = self.budget_session.prepare_call(
            form_data=form_data,
            model_id=exact_model_id,
            provider_profile_id=provider_profile.profile_id,
            operation_identity=(
                "broker-reports-goal12-preflight:"
                f"{provider_profile.profile_id}:{case.case_id}"
            ),
        )
        adapter = Gate2ProviderAdapterFactory(
            profile=provider_profile,
            capability_probe=True,
        ).create()
        prepared_request = adapter.prepare_context_v2_1_budget_smoke_form_data(
            form_data=authorization.prepared_form_data,
            response_format=sealed_request.response_format,
        )
        transport_contract = adapter.context_v2_1_budget_smoke_transport_contract(
            transport_policy=parameters.transport_policy,
        )
        projection = Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection(
            request_profile=request_profile,
            sealed_request=sealed_request,
            prepared_request=prepared_request,
            transport_contract=transport_contract,
        )
        self.projections[(provider_profile.profile_id, case.case_id)] = projection
        return projection


@pytest.fixture(scope="module")
def report_context() -> dict[str, Any]:
    audit_manifest = _read(AUDIT_PATH)
    historical_manifest = _read(HISTORICAL_PATH)
    base_manifest = _read(BASE_PATH)
    audit = validate_financial_semantic_v6_outcome_audit(
        manifest=audit_manifest,
        historical_manifest=historical_manifest,
        base_manifest=base_manifest,
        semantic_pack=_read(PACK_PATH),
        reason_catalog_v2=_read(REASON_CATALOG_PATH),
    )
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    fixture = Gate2FinancialSemanticV6QualificationFixtureFactory(
        registry=registry,
        snapshot_authority_key=SNAPSHOT_KEY,
        continuation_key=CONTINUATION_KEY,
    ).create(
        manifest=historical_manifest,
        base_manifest=base_manifest,
    )
    projector = _DeterministicProjector(registry=registry)
    plan = Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory(
        request_profile=REQUEST_PROFILE,
        slot_projector=projector,
    ).create(
        fixture=fixture,
        outcome_audit_manifest=audit_manifest,
    )
    return {
        "audit": audit,
        "audit_manifest": audit_manifest,
        "cases": {item.case_id: item for item in fixture.semantic_cases},
        "evidence_factory": (
            Gate2FinancialSemanticV6DecisionEvidenceFactory(registry=registry)
        ),
        "fixture": fixture,
        "plan": plan,
        "projector": projector,
        "registry": registry,
        "report_factory": (Gate2FinancialSemanticV6TransparentSmokeReportFactory()),
    }


def _projection(context: dict[str, Any], slot):
    return context["projector"].projections[(slot.provider_profile_id, slot.case_id)]


def _expected_answer(
    context: dict[str, Any],
    slot,
) -> dict[str, Any]:
    return resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer(
        plan=context["plan"],
        slot=slot,
        fixture=context["fixture"],
        outcome_audit_manifest=context["audit_manifest"],
    )


def _expected_model_output(
    context: dict[str, Any],
    slot,
) -> dict[str, Any]:
    expected = _expected_answer(context, slot)
    if expected["disposition"] == "unclassified_financial_input":
        return {
            "choice": "unclassified",
            "reason": expected["reason_code"],
        }
    case = context["cases"][slot.case_id]
    matches = [
        item
        for item in (case.packet.context_v2_mapping_receipt.choice_restoration)
        if item["typed_option_id"] == expected["typed_option_id"]
    ]
    assert len(matches) == 1
    return {"choice": matches[0]["choice_key"]}


def _prepared_execution(
    context: dict[str, Any],
    slot,
):
    projection = _projection(context, slot)
    operation_identity = (
        financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
            plan=context["plan"],
            slot=slot,
        )
    )
    form_data = Gate2OpenWebUIRequestBuilder(
        request_profile=REQUEST_PROFILE,
    ).build_from_sealed_context_v2_1(
        model_visible_request=copy.deepcopy(
            projection.sealed_request.model_visible_request
        ),
        model_id=slot.exact_model_id,
    )
    session = Gate2EconomyBudgetSessionFactory().create(
        request_profile=REQUEST_PROFILE,
    )
    authorization = session.prepare_call(
        form_data=form_data,
        model_id=slot.exact_model_id,
        provider_profile_id=slot.provider_profile_id,
        operation_identity=operation_identity,
    )
    profile = gate2_provider_profile(slot.provider_profile_id)
    prepared_request = (
        Gate2ProviderAdapterFactory(
            profile=profile,
            capability_probe=True,
            native_transport_config=Gate2NativeProviderTransportConfig(
                timeout_seconds=slot.transport_contract["timeout_seconds"],
            ),
        )
        .create()
        .prepare_context_v2_1_budget_smoke_form_data(
            form_data=authorization.prepared_form_data,
            response_format=projection.sealed_request.response_format,
        )
    )
    assert prepared_request == projection.prepared_request
    return operation_identity, session, authorization, prepared_request


def _execution_metadata(
    *,
    slot,
    prepared_request,
    raw_provider_response,
) -> Gate2ProviderExecutionMetadata:
    projection_contract = _transport_contract_from_slot(slot)
    return (
        Gate2ProviderAdapterFactory(
            profile=gate2_provider_profile(slot.provider_profile_id),
            capability_probe=True,
            native_transport_config=Gate2NativeProviderTransportConfig(
                timeout_seconds=projection_contract.timeout_seconds,
            ),
        )
        .create()
        .context_v2_1_budget_smoke_execution_metadata(
            payload=raw_provider_response,
            requested_model_id=slot.exact_model_id,
            duration_ms=20 + slot.ordinal,
            prepared_request=prepared_request,
            transport_contract=projection_contract,
        )
    )


def _transport_contract_from_slot(slot):
    return (
        Gate2ProviderAdapterFactory(
            profile=gate2_provider_profile(slot.provider_profile_id),
            capability_probe=True,
            native_transport_config=Gate2NativeProviderTransportConfig(
                timeout_seconds=slot.transport_contract["timeout_seconds"],
            ),
        )
        .create()
        .context_v2_1_budget_smoke_transport_contract(
            transport_policy=slot.transport_policy,
        )
    )


def _provider_response(
    *,
    slot,
    model_output: dict[str, Any],
) -> tuple[dict[str, Any], Any]:
    private_fields = {
        "credential": PRIVATE_CREDENTIAL,
        "filesystem_path": PRIVATE_PATH,
        "hidden_reasoning": PRIVATE_REASONING,
    }
    visible_output: dict[str, Any] = copy.deepcopy(model_output)
    if slot.provider_profile_id == "openai_gpt":
        visible_output = {
            "broker_reports_gate2_choice": visible_output,
        }
    serialized_output = json.dumps(
        visible_output,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if slot.provider_adapter_id == "anthropic_native_messages":
        return (
            {
                "id": f"{PRIVATE_RESPONSE_ID}:{slot.slot_id}",
                "model": slot.exact_model_id,
                "content": [{"type": "text", "text": serialized_output}],
                "stop_reason": "end_turn",
                "usage": {
                    "input_tokens": 100 + slot.ordinal,
                    "output_tokens": 12,
                },
                **private_fields,
            },
            serialized_output,
        )
    return (
        {
            "id": f"{PRIVATE_RESPONSE_ID}:{slot.slot_id}",
            "model": slot.exact_model_id,
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": serialized_output,
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 100 + slot.ordinal,
                "completion_tokens": 12,
                "total_tokens": 112 + slot.ordinal,
            },
            **private_fields,
        },
        (
            copy.deepcopy(model_output)
            if slot.provider_profile_id == "openai_gpt"
            else serialized_output
        ),
    )


def _candidate_bundle(
    context: dict[str, Any],
    slot,
    *,
    model_output: dict[str, Any] | None = None,
):
    (
        operation_identity,
        session,
        authorization,
        prepared_request,
    ) = _prepared_execution(context, slot)
    exact_output = (
        copy.deepcopy(model_output)
        if model_output is not None
        else _expected_model_output(context, slot)
    )
    raw_response, adapter_output = _provider_response(
        slot=slot,
        model_output=exact_output,
    )
    metadata = _execution_metadata(
        slot=slot,
        prepared_request=prepared_request,
        raw_provider_response=raw_response,
    )
    budget_receipt = session.finalize_call(
        authorization=authorization,
        execution_metadata=metadata,
    )
    case = context["cases"][slot.case_id]
    return context["evidence_factory"].create_context_v2_1_budget_smoke_candidate(
        plan=context["plan"],
        plan_slot=slot,
        expected_answer=_expected_answer(context, slot),
        operation_identity=operation_identity,
        sealed_request=_projection(
            context,
            slot,
        ).sealed_request,
        prepared_request=prepared_request,
        adapter_extracted_output=adapter_output,
        raw_provider_response=raw_response,
        execution_metadata=metadata,
        economy_budget_receipt=budget_receipt,
        choice_contract=case.choice_contract,
        packet=case.packet,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
    )


def _failure_bundle(
    context: dict[str, Any],
    slot,
    *,
    error_category: str,
    lifecycle: dict[str, int],
    with_metadata: bool,
    failure_code: str | None = None,
    failure_class: str | None = None,
):
    projection = _projection(context, slot)
    operation_identity = (
        financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
            plan=context["plan"],
            slot=slot,
        )
    )
    if with_metadata:
        raw_output, adapter_extracted_output = _provider_response(
            slot=slot,
            model_output={"unexpected": "invalid-choice-shape"},
        )
        metadata = _execution_metadata(
            slot=slot,
            prepared_request=projection.prepared_request,
            raw_provider_response=raw_output,
        )
    else:
        raw_output = None
        adapter_extracted_output = None
        metadata = None
    case = context["cases"][slot.case_id]
    return context["evidence_factory"].create_context_v2_1_budget_smoke_failure(
        plan=context["plan"],
        plan_slot=slot,
        operation_identity=operation_identity,
        sealed_request=projection.sealed_request,
        prepared_request=projection.prepared_request,
        lifecycle=lifecycle,
        expected_answer=_expected_answer(context, slot),
        failure_code=(
            failure_code
            or (
                "gate2_model_invalid_response"
                if error_category == "invalid_response"
                else "google_model_identity_not_immutable"
            )
        ),
        failure_class=(
            failure_class
            or (
                "provider_response_invalid"
                if error_category == "invalid_response"
                else "provider_model_identity_unproven"
            )
        ),
        error_category=error_category,
        raw_output=raw_output,
        adapter_extracted_output=adapter_extracted_output,
        execution_metadata=metadata,
        economy_budget_receipt=None,
        elapsed_ms=31 if with_metadata else 0,
        choice_contract=case.choice_contract,
        packet=case.packet,
        evidence_bundle=case.evidence_bundle,
        source_package=case.scope.source_package,
        compilation=case.compilation,
    )


def _google_identity_failure(
    context: dict[str, Any],
    slot,
):
    return _failure_bundle(
        context,
        slot,
        error_category="infrastructure_provider_failure",
        lifecycle={
            "local_invocations_total": 0,
            "provider_submissions_total": 0,
            "provider_responses_total": 0,
            "semantic_repair_total": 0,
            "retry_total": 0,
            "repair_total": 0,
            "fallback_total": 0,
        },
        with_metadata=False,
    )


def _report_case(context: dict[str, Any], slot, bundle):
    return context["report_factory"].create_context_v2_1_budget_smoke_case(
        plan=context["plan"],
        plan_slot=slot,
        evidence_bundle=bundle,
    )


@pytest.fixture(scope="module")
def baseline_report(report_context) -> dict[str, Any]:
    bundles = {}
    case_evidence = []
    for slot in report_context["plan"].slots:
        bundle = (
            _candidate_bundle(report_context, slot)
            if slot.immutable_model_id_proven
            else _google_identity_failure(report_context, slot)
        )
        bundles[slot.slot_id] = bundle
        case_evidence.append(_report_case(report_context, slot, bundle))
    report = report_context["report_factory"].create_context_v2_1_budget_smoke_report(
        plan=report_context["plan"],
        case_evidence=case_evidence,
    )
    return {
        "bundles": bundles,
        "case_evidence": case_evidence,
        "report": report,
    }


def _provider_verdict(
    report: dict[str, Any],
    provider_profile_id: str,
) -> dict[str, Any]:
    matches = [
        item
        for item in report["provider_verdicts"]
        if item["provider_profile_id"] == provider_profile_id
    ]
    assert len(matches) == 1
    return matches[0]


def test_all_executable_slots_pass_and_google_is_blocked_pretransport(
    report_context,
    baseline_report,
) -> None:
    report = baseline_report["report"]
    plan = report_context["plan"]
    assert report["schema_version"] == (CONTEXT_V2_1_BUDGET_SMOKE_REPORT_SCHEMA_VERSION)
    assert report["status"] == "completed"
    assert report["active"] is False
    assert report["production_admissions"] == []
    assert report["provider_profiles_total"] == 3
    assert report["frozen_plan_slots_total"] == 12
    assert [
        (item["provider"]["provider_profile_id"], item["case_id"])
        for item in report["cases"]
    ] == [(slot.provider_profile_id, slot.case_id) for slot in plan.slots]

    for slot, item in zip(plan.slots, report["cases"], strict=True):
        projection = _projection(report_context, slot)
        messages = projection.sealed_request.model_visible_request["messages"]
        assert item["schema_version"] == (CONTEXT_V2_1_BUDGET_SMOKE_CASE_SCHEMA_VERSION)
        assert item["exact_synthetic_final_provider_request"] == (
            projection.prepared_request.form_data
        )
        assert item["exact_system_message"] == messages[0]["content"]
        assert item["exact_user_content"] == messages[1]["content"]
        assert (
            item["exact_provider_visible_response_schema"]
            == projection.prepared_request.provider_visible_schema
        )
        assert item["provider"]["exact_model_id"] == slot.exact_model_id
        assert item["provider"]["adapter_id"] == (slot.provider_adapter_id)
        assert item["provider"]["transport_policy"] == (
            CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
        )
        assert item["provider"]["transport_contract"] == (slot.transport_contract)
        assert item["provider"]["transport_contract_hash"] == (
            slot.transport_contract_hash
        )
        assert (
            item["provider"]["transport_contract"]["actual_transport_type"]
            == CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE
        )
        if slot.immutable_model_id_proven:
            assert item["technical_smoke_verdict"] == (TECHNICAL_SMOKE_PASSED)
            assert item["semantic_smoke_verdict"] == (SEMANTIC_SMOKE_PASSED)
            assert item["error_category"] is None
            assert item["mechanical_diff"]["all_fields_match"] is True
            assert item["execution_accounting"]["provider_submissions_total"] == 1
            assert item["execution_accounting"]["provider_responses_total"] == 1
        else:
            assert item["technical_smoke_verdict"] == (TECHNICAL_SMOKE_FAILED)
            assert item["semantic_smoke_verdict"] == (SEMANTIC_SMOKE_FAILED)
            assert item["error_category"] == ("infrastructure_provider_failure")
            assert item["normalized_canonical_answer"] is None
            assert item["execution_accounting"]["provider_submissions_total"] == 0
            assert item["execution_accounting"]["provider_responses_total"] == 0

    for profile_id in ("openai_gpt", "anthropic_claude"):
        verdict = _provider_verdict(report, profile_id)
        assert verdict["technical_smoke_verdict"] == (TECHNICAL_SMOKE_PASSED)
        assert verdict["semantic_smoke_verdict"] == (SEMANTIC_SMOKE_PASSED)
        assert verdict["answers_exact_total"] == 4
        assert verdict["admission_eligible"] is True
        assert verdict["transport_policy"] == (
            CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
        )
        assert verdict["transport_contract_hash"] == sha256_json(
            verdict["transport_contract"]
        )
    google = _provider_verdict(report, "google_gemini")
    assert google["technical_smoke_verdict"] == (TECHNICAL_SMOKE_FAILED)
    assert google["semantic_smoke_verdict"] == (SEMANTIC_SMOKE_FAILED)
    assert google["immutable_model_id_proven"] is False
    assert google["admission_eligible"] is False
    assert google["error_category_counts"]["infrastructure_provider_failure"] == 4
    assert report["execution_accounting"]["provider_submissions_total"] == 8
    assert report["execution_accounting"]["provider_responses_total"] == 8
    draft = copy.deepcopy(report)
    integrity_hash = draft.pop("integrity_hash")
    assert integrity_hash == sha256_json(draft)


def test_consumed_unknown_metrics_remain_none_in_case_and_provider_total(
    report_context,
) -> None:
    plan = report_context["plan"]
    target = next(
        slot for slot in plan.slots if slot.provider_profile_id == "openai_gpt"
    )
    case_evidence = []
    for slot in plan.slots:
        if slot == target:
            bundle = _failure_bundle(
                report_context,
                slot,
                error_category="infrastructure_provider_failure",
                lifecycle={
                    "local_invocations_total": 1,
                    "provider_submissions_total": 1,
                    "provider_responses_total": 0,
                    "semantic_repair_total": 0,
                    "retry_total": 0,
                    "repair_total": 0,
                    "fallback_total": 0,
                },
                with_metadata=False,
                failure_code="consumed_slot_response_unavailable",
                failure_class="provider_transport",
            )
        elif slot.immutable_model_id_proven:
            bundle = _candidate_bundle(report_context, slot)
        else:
            bundle = _google_identity_failure(report_context, slot)
        case_evidence.append(_report_case(report_context, slot, bundle))

    report = report_context["report_factory"].create_context_v2_1_budget_smoke_report(
        plan=plan,
        case_evidence=case_evidence,
    )

    target_case = next(
        item for item in report["cases"] if item["slot_id"] == target.slot_id
    )
    assert target_case["actual_metrics"] == {
        "input_tokens": None,
        "output_tokens": None,
        "cost_usd": None,
        "latency_ms": None,
    }
    openai = _provider_verdict(report, "openai_gpt")
    assert openai["actual_metrics"] == {
        "input_tokens_total": None,
        "output_tokens_total": None,
        "cost_usd_total": None,
        "latency_ms_total": None,
    }


def _alternate_typed_output(context: dict[str, Any], slot):
    expected = _expected_answer(context, slot)
    case = context["cases"][slot.case_id]
    alternatives = [
        item["choice_key"]
        for item in (case.packet.context_v2_mapping_receipt.choice_restoration)
        if item["typed_option_id"] != expected.get("typed_option_id")
    ]
    assert alternatives
    return {"choice": alternatives[0]}


def _first_typed_output(context: dict[str, Any], slot):
    case = context["cases"][slot.case_id]
    choices = case.packet.context_v2_mapping_receipt.choice_restoration
    assert choices
    return {"choice": choices[0]["choice_key"]}


def test_mixed_failures_preserve_all_six_error_categories(
    report_context,
) -> None:
    plan = report_context["plan"]
    outputs: dict[tuple[str, str], dict[str, Any]] = {}
    unique_case = "syn_successor_v2_unique_cash"
    no_type_case = "syn_successor_v2_no_registry_type"
    openai_unique = next(
        slot
        for slot in plan.slots
        if (
            slot.provider_profile_id,
            slot.case_id,
        )
        == ("openai_gpt", unique_case)
    )
    openai_no_type = next(
        slot
        for slot in plan.slots
        if (
            slot.provider_profile_id,
            slot.case_id,
        )
        == ("openai_gpt", no_type_case)
    )
    outputs[("openai_gpt", unique_case)] = _alternate_typed_output(
        report_context,
        openai_unique,
    )
    outputs[("openai_gpt", no_type_case)] = _first_typed_output(
        report_context,
        openai_no_type,
    )
    outputs[("anthropic_claude", unique_case)] = {
        "choice": "unclassified",
        "reason": "single_registry_type_no_safe_record",
    }
    outputs[("anthropic_claude", no_type_case)] = {
        "choice": "unclassified",
        "reason": "ambiguous_registry_type",
    }
    invalid_pair = (
        "openai_gpt",
        "syn_successor_v2_multiple_compatible",
    )

    case_evidence = []
    for slot in plan.slots:
        pair = (slot.provider_profile_id, slot.case_id)
        if not slot.immutable_model_id_proven:
            bundle = _google_identity_failure(report_context, slot)
        elif pair == invalid_pair:
            bundle = _failure_bundle(
                report_context,
                slot,
                error_category="invalid_response",
                lifecycle={
                    "local_invocations_total": 1,
                    "provider_submissions_total": 1,
                    "provider_responses_total": 1,
                    "semantic_repair_total": 0,
                    "retry_total": 0,
                    "repair_total": 0,
                    "fallback_total": 0,
                },
                with_metadata=True,
            )
        else:
            bundle = _candidate_bundle(
                report_context,
                slot,
                model_output=outputs.get(pair),
            )
        case_evidence.append(_report_case(report_context, slot, bundle))
    report = report_context["report_factory"].create_context_v2_1_budget_smoke_report(
        plan=plan,
        case_evidence=case_evidence,
    )
    observed_categories = {
        item["error_category"]
        for item in report["cases"]
        if item["error_category"] is not None
    }
    assert observed_categories == set(CONTEXT_V2_1_BUDGET_SMOKE_ERROR_CATEGORIES)
    openai = _provider_verdict(report, "openai_gpt")
    assert openai["technical_smoke_verdict"] == (TECHNICAL_SMOKE_FAILED)
    assert openai["semantic_smoke_verdict"] == (SEMANTIC_SMOKE_FAILED)
    assert openai["admission_eligible"] is False
    assert openai["error_category_counts"]["wrong_typed_type"] == 1
    assert openai["error_category_counts"]["unsafe_typed"] == 1
    assert openai["error_category_counts"]["invalid_response"] == 1
    anthropic = _provider_verdict(report, "anthropic_claude")
    assert anthropic["technical_smoke_verdict"] == (TECHNICAL_SMOKE_PASSED)
    assert anthropic["semantic_smoke_verdict"] == (SEMANTIC_SMOKE_FAILED)
    assert anthropic["admission_eligible"] is False
    assert anthropic["error_category_counts"]["safe_under_typing"] == 1
    assert anthropic["error_category_counts"]["wrong_unclassified_reason"] == 1
    assert all(
        verdict["acceptance"]["unsafe_typed_total"] == 0
        or verdict["admission_eligible"] is False
        for verdict in report["provider_verdicts"]
    )
    assert report["active"] is False
    assert report["production_admissions"] == []


def test_report_excludes_raw_envelopes_ids_credentials_paths_and_reasoning(
    baseline_report,
) -> None:
    serialized = json.dumps(
        baseline_report["report"],
        ensure_ascii=False,
        sort_keys=True,
    )
    for forbidden in (
        PRIVATE_RESPONSE_ID,
        PRIVATE_CREDENTIAL,
        PRIVATE_PATH,
        PRIVATE_REASONING,
        "provider_response_id",
        "raw_provider_response",
        "raw_output",
        "failure_code",
        "failure_class",
    ):
        assert forbidden not in serialized


def test_tampered_private_bundle_and_resealed_report_case_fail_closed(
    report_context,
    baseline_report,
) -> None:
    slot = report_context["plan"].slots[0]
    bundle = copy.deepcopy(baseline_report["bundles"][slot.slot_id])
    bundle.private_evidence["exact_final_provider_request"]["model"] = "forged-model"
    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as private_failure:
        _report_case(report_context, slot, bundle)
    assert private_failure.value.code == (
        "financial_semantic_v6_context_v2_1_budget_smoke_report_authority_invalid"
    )

    original_token = baseline_report["case_evidence"][0]
    forged = original_token.to_dict()
    forged["provider"]["exact_model_id"] = "forged-model"
    forged["exact_synthetic_final_provider_request"]["model"] = "forged-model"
    forged.pop("integrity_hash")
    forged["integrity_hash"] = sha256_json(forged)
    token = object.__new__(type(original_token))
    object.__setattr__(
        token,
        (
            "_Gate2FinancialSemanticV6ContextV21BudgetSmoke"
            "ReportCaseEvidence__serialized_projection"
        ),
        json.dumps(
            forged,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
    )
    forged_evidence = list(baseline_report["case_evidence"])
    forged_evidence[0] = token
    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as report_failure:
        (
            report_context["report_factory"].create_context_v2_1_budget_smoke_report(
                plan=report_context["plan"],
                case_evidence=forged_evidence,
            )
        )
    assert report_failure.value.code == (
        "financial_semantic_v6_context_v2_1_budget_smoke_report_cases_invalid"
    )

    original_transport_token = baseline_report["case_evidence"][1]
    forged_transport = original_transport_token.to_dict()
    forged_transport["provider"]["transport_contract"]["actual_transport_type"] = (
        "legacy_framework_transport"
    )
    forged_transport["provider"]["transport_contract_hash"] = sha256_json(
        forged_transport["provider"]["transport_contract"]
    )
    forged_transport.pop("integrity_hash")
    forged_transport["integrity_hash"] = sha256_json(forged_transport)
    transport_token = object.__new__(type(original_transport_token))
    object.__setattr__(
        transport_token,
        (
            "_Gate2FinancialSemanticV6ContextV21BudgetSmoke"
            "ReportCaseEvidence__serialized_projection"
        ),
        json.dumps(
            forged_transport,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ),
    )
    forged_transport_evidence = list(baseline_report["case_evidence"])
    forged_transport_evidence[1] = transport_token
    with pytest.raises(
        Gate2FinancialSemanticV6TransparentSmokeReportError,
    ) as transport_failure:
        (
            report_context["report_factory"].create_context_v2_1_budget_smoke_report(
                plan=report_context["plan"],
                case_evidence=forged_transport_evidence,
            )
        )
    assert transport_failure.value.code == (
        "financial_semantic_v6_context_v2_1_budget_smoke_report_cases_invalid"
    )


def test_goal11_report_contracts_and_method_bodies_remain_unchanged() -> None:
    assert CONTEXT_V2_1_PROVIDER_PROOF_CASE_SCHEMA_VERSION == (
        "broker_reports_gate2_context_v2_1_provider_proof_case_v1"
    )
    assert CONTEXT_V2_1_PROVIDER_PROOF_REPORT_SCHEMA_VERSION == (
        "broker_reports_gate2_context_v2_1_three_provider_local_proof_v1"
    )
    expected_hashes = {
        "create_context_v2_1_provider_case": (
            "d309aadd7b7d374c9449915aac3bb3304e68f006fc70709a0f716b72ee1e8511"
        ),
        "create_context_v2_1_provider_report": (
            "1ec6d4157a47281aa0e061d935f5225001aa5a9843a1651062ef9cc77613c90d"
        ),
        "create_case": (
            "916ca3ae42c3713f209955b8697e4cc15e8298fecec1bcfd2e42d5b1031761b9"
        ),
        "render_report": (
            "0f24fb848f8fab1ab0f2da38d42592c2592055f1c597d9131c5fdbfd8384223d"
        ),
    }
    for method_name, expected_hash in expected_hashes.items():
        method = getattr(
            Gate2FinancialSemanticV6TransparentSmokeReportFactory,
            method_name,
        )
        observed = hashlib.sha256(inspect.getsource(method).encode("utf-8")).hexdigest()
        assert observed == expected_hash


def test_report_test_never_defines_a_provider_transport_boundary() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    for forbidden_identifier in (
        "_".join(("completion", "resolver")),
        "_".join(("native", "transport", "resolver")),
        "".join(("Gate2Structured", "ModelClientFactory")),
    ):
        assert forbidden_identifier not in source
    assert tuple(BUDGET_SMOKE_PROVIDER_MODELS)
    assert tuple(BUDGET_SMOKE_CASES)
