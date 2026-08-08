from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Mapping

from .gate2_economy_budget import Gate2EconomyBudgetSessionFactory
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v6_context_linter import (
    Gate2FinancialSemanticV6ContextLinterFactory,
    Gate2FinancialSemanticV6ContextV21SealedRequest,
    validate_financial_semantic_v6_context_v2_1_sealed_request,
)
from .gate2_financial_semantic_v6_context_v2_1_budget_smoke_plan import (
    Gate2FinancialSemanticV6ContextV21BudgetSmokeParameters,
    Gate2FinancialSemanticV6ContextV21BudgetSmokePlan,
    Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory,
    Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot,
    Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection,
    financial_semantic_v6_context_v2_1_budget_smoke_operation_identity,
    resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer,
    validate_financial_semantic_v6_context_v2_1_budget_smoke_plan,
)
from .gate2_financial_semantic_v6_evidence import (
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
)
from .gate2_financial_semantic_v6_prompt import V6_SEMANTIC_SYSTEM_PROMPT
from .gate2_financial_semantic_v6_qualification import (
    Gate2FinancialSemanticV6QualificationCase,
    Gate2FinancialSemanticV6QualificationFixture,
)
from .gate2_model_clients import (
    Gate2ContextV21BudgetSmokeModelResult,
    Gate2OpenWebUIStructuredModelClient,
)
from .gate2_model_contracts import (
    Gate2ProviderProfile,
    Gate2SourceFactRuntimeError,
    gate2_provider_profile,
)
from .gate2_model_requests import Gate2OpenWebUIRequestBuilder
from .gate2_provider_adapters import (
    Gate2ContextV21BudgetSmokeTransportContract,
    Gate2PreparedProviderRequest,
    Gate2ProviderAdapterFactory,
)


ERROR_WRONG_TYPED_TYPE = "wrong_typed_type"
ERROR_UNSAFE_TYPED = "unsafe_typed"
ERROR_SAFE_UNDER_TYPING = "safe_under_typing"
ERROR_WRONG_UNCLASSIFIED_REASON = "wrong_unclassified_reason"
ERROR_INVALID_RESPONSE = "invalid_response"
ERROR_INFRASTRUCTURE_PROVIDER_FAILURE = (
    "infrastructure_provider_failure"
)
BUDGET_SMOKE_ERROR_CATEGORIES = frozenset(
    {
        ERROR_WRONG_TYPED_TYPE,
        ERROR_UNSAFE_TYPED,
        ERROR_SAFE_UNDER_TYPING,
        ERROR_WRONG_UNCLASSIFIED_REASON,
        ERROR_INVALID_RESPONSE,
        ERROR_INFRASTRUCTURE_PROVIDER_FAILURE,
    }
)
_INVALID_RESPONSE_FAILURE_CLASSES = frozenset(
    {"provider_response_invalid", "response_budget"}
)
_INVALID_RESPONSE_FAILURE_CODES = frozenset(
    {
        "gate2_model_invalid_response",
        "gate2_model_response_budget_exceeded",
        "gate2_model_response_not_terminal",
        "gate2_economy_usage_accounting_missing",
        "financial_semantic_v6_context_v2_1_choice_duplicate_key",
        "financial_semantic_v6_context_v2_1_choice_invalid",
        "financial_semantic_v6_context_v2_1_choice_json_invalid",
        "financial_semantic_v6_context_v2_1_choice_key_unknown",
        "financial_semantic_v6_context_v2_1_choice_reason_invalid",
        "financial_semantic_v6_context_v2_1_choice_size_invalid",
        "financial_semantic_v6_context_v2_1_choice_typed_shape_invalid",
        (
            "financial_semantic_v6_context_v2_1_"
            "choice_unclassified_shape_invalid"
        ),
    }
)
BUDGET_SMOKE_SNAPSHOT_AUTHORITY_KEY = (
    b"broker-reports-context-v2-1-goal12-snapshot-authority-v1"
)
BUDGET_SMOKE_CONTINUATION_KEY = (
    b"broker-reports-context-v2-1-goal12-continuation-v1"
)

FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator executes only "
    "the immutable plan through the existing linter, request-builder, "
    "economy-budget, provider-adapter, model-client and evidence owners"
)
FORBIDDEN = (
    "GOAL 12 must not alter a frozen model or parameter, retry, repair, fall "
    "back, call an unproven immutable selector, admit production, activate "
    "Context V2.1 or bypass the provider/evidence factories"
)


class Gate2FinancialSemanticV6ContextV21BudgetSmokeError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21BudgetSmokeCaseOutcome:
    slot_id: str
    ordinal: int
    provider_profile_id: str
    exact_model_id: str
    case_id: str
    taxonomy_state: str
    operation_identity_sha256: str
    status: str
    technical_pipeline_exact: bool
    semantic_answer_exact: bool
    error_category: str | None
    failure_code: str | None
    failure_class: str | None
    local_invocations_total: int
    provider_submissions_total: int
    provider_responses_total: int
    semantic_repair_total: int
    retry_total: int
    repair_total: int
    fallback_total: int
    expected_answer: dict[str, Any]
    normalized_answer: dict[str, Any] | None
    adapter_extracted_output: Any = field(repr=False)
    sealed_request: Gate2FinancialSemanticV6ContextV21SealedRequest = field(
        repr=False
    )
    prepared_request: Gate2PreparedProviderRequest = field(repr=False)
    evidence_bundle: Any = field(repr=False, compare=False)
    private_evidence: dict[str, Any] = field(repr=False)
    safe_receipt: dict[str, Any]

    def safe_summary(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "ordinal": self.ordinal,
            "provider_profile_id": self.provider_profile_id,
            "exact_model_id": self.exact_model_id,
            "case_id": self.case_id,
            "taxonomy_state": self.taxonomy_state,
            "operation_identity_sha256": (
                self.operation_identity_sha256
            ),
            "status": self.status,
            "technical_pipeline_exact": self.technical_pipeline_exact,
            "semantic_answer_exact": self.semantic_answer_exact,
            "error_category": self.error_category,
            "failure_code": self.failure_code,
            "failure_class": self.failure_class,
            "execution_accounting": {
                "local_invocations_total": (
                    self.local_invocations_total
                ),
                "provider_submissions_total": (
                    self.provider_submissions_total
                ),
                "provider_responses_total": (
                    self.provider_responses_total
                ),
                "semantic_repair_total": self.semantic_repair_total,
                "retry_total": self.retry_total,
                "repair_total": self.repair_total,
                "fallback_total": self.fallback_total,
            },
            "private_evidence_hash": self.private_evidence.get(
                "private_evidence_hash"
            ),
            "safe_receipt": copy.deepcopy(self.safe_receipt),
        }


class Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjector:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def __call__(
        self,
        *,
        case: Gate2FinancialSemanticV6QualificationCase,
        provider_profile: Gate2ProviderProfile,
        exact_model_id: str,
        request_profile: str,
        parameters: (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeParameters
        ),
    ) -> Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection:
        response_profile = (
            case.choice_contract.context_v2_1_response_profile
        )
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
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        sealed_request = (
            Gate2FinancialSemanticV6ContextLinterFactory(
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
                mapping_receipt=(
                    case.packet.context_v2_mapping_receipt
                ),
            )
        )
        validate_financial_semantic_v6_context_v2_1_sealed_request(
            sealed_request=sealed_request,
            packet=case.packet,
            choice_contract=case.choice_contract,
            evidence_bundle=case.evidence_bundle,
            source_package=case.scope.source_package,
            compilation=case.compilation,
            registry=self.registry,
            system_message=V6_SEMANTIC_SYSTEM_PROMPT,
            mapping_receipt=case.packet.context_v2_mapping_receipt,
        )
        form_data = Gate2OpenWebUIRequestBuilder(
            request_profile=request_profile
        ).build_from_sealed_context_v2_1(
            model_visible_request=sealed_request.model_visible_request,
            model_id=exact_model_id,
        )
        authorization = (
            Gate2EconomyBudgetSessionFactory()
            .create(request_profile=request_profile)
            .prepare_call(
                form_data=form_data,
                model_id=exact_model_id,
                provider_profile_id=provider_profile.profile_id,
                operation_identity=(
                    "broker-reports-goal12-preflight:"
                    f"{provider_profile.profile_id}:{case.case_id}"
                ),
            )
        )
        if (
            authorization.exact_model_id != exact_model_id
            or authorization.maximum_output_tokens
            != parameters.maximum_output_tokens
            or authorization.fallback_call
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_projection_budget_invalid"
            )
        provider_adapter = Gate2ProviderAdapterFactory(
            profile=provider_profile,
            capability_probe=True,
        ).create()
        prepared_request = (
            provider_adapter.prepare_context_v2_1_budget_smoke_form_data(
            form_data=authorization.prepared_form_data,
            response_format=sealed_request.response_format,
            )
        )
        transport_contract = (
            provider_adapter.context_v2_1_budget_smoke_transport_contract(
                transport_policy=parameters.transport_policy,
            )
        )
        return (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection(
                request_profile=request_profile,
                sealed_request=sealed_request,
                prepared_request=prepared_request,
                transport_contract=transport_contract,
            )
        )


def build_financial_semantic_v6_context_v2_1_budget_smoke_plan(
    *,
    fixture: Gate2FinancialSemanticV6QualificationFixture,
    outcome_audit_manifest: dict[str, Any],
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    provider_profile_resolver: Callable[
        [str], Gate2ProviderProfile
    ] = gate2_provider_profile,
) -> Gate2FinancialSemanticV6ContextV21BudgetSmokePlan:
    return (
        Gate2FinancialSemanticV6ContextV21BudgetSmokePlanFactory(
            request_profile=(
                "financial_semantic_v6_context_v2_1_budget_smoke_v1"
            ),
            slot_projector=(
                Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjector(
                    registry=registry
                )
            ),
            provider_profile_resolver=provider_profile_resolver,
        ).create(
            fixture=fixture,
            outcome_audit_manifest=outcome_audit_manifest,
        )
    )


class Gate2FinancialSemanticV6ContextV21BudgetSmokeCoordinator:
    def __init__(
        self,
        *,
        plan: Gate2FinancialSemanticV6ContextV21BudgetSmokePlan,
        fixture: Gate2FinancialSemanticV6QualificationFixture,
        outcome_audit_manifest: dict[str, Any],
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        clients: Mapping[str, Gate2OpenWebUIStructuredModelClient],
        consume_slot: Callable[
            [
                Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot,
                str,
            ],
            None,
        ],
        private_checkpoint: Callable[[str, dict[str, Any]], None],
        safe_checkpoint: (
            Callable[[str, dict[str, Any]], None] | None
        ) = None,
        provider_profile_resolver: Callable[
            [str], Gate2ProviderProfile
        ] = gate2_provider_profile,
    ) -> None:
        validate_financial_semantic_v6_context_v2_1_budget_smoke_plan(
            plan,
            provider_profile_resolver=provider_profile_resolver,
        )
        rebuilt = (
            build_financial_semantic_v6_context_v2_1_budget_smoke_plan(
                fixture=fixture,
                outcome_audit_manifest=outcome_audit_manifest,
                registry=registry,
                provider_profile_resolver=provider_profile_resolver,
            )
        )
        if rebuilt != plan:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_plan_rebuild_mismatch"
            )
        if (
            not isinstance(clients, Mapping)
            or not callable(consume_slot)
            or not callable(private_checkpoint)
            or (
                safe_checkpoint is not None
                and not callable(safe_checkpoint)
            )
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_coordinator_invalid"
            )
        all_semantic_cases = {
            item.case_id: item for item in fixture.semantic_cases
        }
        selected_case_ids = tuple(
            dict.fromkeys(item.case_id for item in plan.slots)
        )
        if (
            len(all_semantic_cases) != len(fixture.semantic_cases)
            or not selected_case_ids
            or any(
                case_id not in all_semantic_cases
                for case_id in selected_case_ids
            )
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_fixture_mismatch"
            )
        self.plan = plan
        self.fixture = fixture
        self.outcome_audit_manifest = copy.deepcopy(
            outcome_audit_manifest
        )
        self.registry = registry
        self.clients = dict(clients)
        self.consume_slot = consume_slot
        self.private_checkpoint = private_checkpoint
        self.safe_checkpoint = safe_checkpoint
        self.provider_profile_resolver = provider_profile_resolver
        self._cases = {
            case_id: all_semantic_cases[case_id]
            for case_id in selected_case_ids
        }
        self._projector = (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjector(
                registry=registry
            )
        )

    async def execute_slot(
        self,
        *,
        slot: Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot,
    ) -> Gate2FinancialSemanticV6ContextV21BudgetSmokeCaseOutcome:
        if slot not in self.plan.slots:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_slot_invalid"
            )
        case = self._cases[slot.case_id]
        expected_answer = (
            resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer(
                plan=self.plan,
                slot=slot,
                fixture=self.fixture,
                outcome_audit_manifest=self.outcome_audit_manifest,
                provider_profile_resolver=self.provider_profile_resolver,
            )
        )
        projection = self._projector(
            case=case,
            provider_profile=self.provider_profile_resolver(
                slot.provider_profile_id
            ),
            exact_model_id=slot.exact_model_id,
            request_profile=slot.request_profile,
            parameters=slot.parameters,
        )
        _validate_slot_projection(slot=slot, projection=projection)
        operation_identity = (
            financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
                plan=self.plan,
                slot=slot,
                provider_profile_resolver=self.provider_profile_resolver,
            )
        )
        if not slot.immutable_model_id_proven:
            return self._preflight_failure(
                slot=slot,
                case=case,
                expected_answer=expected_answer,
                projection=projection,
                operation_identity=operation_identity,
                failure_code=(
                    slot.model_identity_caveat
                    or "immutable_model_identity_not_proven"
                ),
                failure_class="provider_model_identity_preflight",
                raw_output={
                    "model_identity_kind": slot.model_identity_kind,
                    "immutable_model_id_proven": False,
                },
            )

        client = self.clients.get(slot.provider_profile_id)
        if client is None:
            return self._preflight_failure(
                slot=slot,
                case=case,
                expected_answer=expected_answer,
                projection=projection,
                operation_identity=operation_identity,
                failure_code="provider_client_preflight_unavailable",
                failure_class="provider_configuration",
                raw_output=None,
            )
        lifecycle_before = client.qualification_lifecycle_snapshot()
        self.consume_slot(slot, operation_identity)
        started = time.monotonic()
        result: Gate2ContextV21BudgetSmokeModelResult | None = None
        try:
            result = await client.extract_context_v2_1_once(
                model_visible_request=(
                    projection.sealed_request.model_visible_request
                ),
                canonical_schema=(
                    case.choice_contract.context_v2_1_response_profile
                    .canonical_schema()
                ),
                model_id=slot.exact_model_id,
                operation_identity=operation_identity,
                expected_prepared_request_hash=(
                    slot.prepared_request_hash
                ),
                transport_policy=slot.transport_policy,
                expected_transport_contract_hash=(
                    slot.transport_contract_hash
                ),
            )
            lifecycle = _lifecycle_delta(
                before=lifecycle_before,
                after=client.qualification_lifecycle_snapshot(),
            )
            if lifecycle != {
                "local_invocations_total": 1,
                "provider_submissions_total": 1,
                "provider_responses_total": 1,
                "semantic_repair_total": 0,
                "retry_total": 0,
                "repair_total": 0,
                "fallback_total": 0,
            }:
                _fail(
                    "financial_semantic_v6_context_v2_1_"
                    "budget_smoke_lifecycle_invalid"
                )
            evidence = (
                Gate2FinancialSemanticV6DecisionEvidenceFactory(
                    registry=self.registry,
                    exact_model_id=slot.exact_model_id,
                    provider_profile_id=slot.provider_profile_id,
                ).create_context_v2_1_budget_smoke_candidate(
                    plan=self.plan,
                    plan_slot=slot,
                    expected_answer=expected_answer,
                    operation_identity=operation_identity,
                    sealed_request=projection.sealed_request,
                    prepared_request=result.prepared_request,
                    adapter_extracted_output=(
                        result.adapter_extracted_output
                    ),
                    raw_provider_response=result.raw_provider_response,
                    execution_metadata=result.execution_metadata,
                    economy_budget_receipt=(
                        result.economy_budget_receipt
                    ),
                    choice_contract=case.choice_contract,
                    packet=case.packet,
                    evidence_bundle=case.evidence_bundle,
                    source_package=case.scope.source_package,
                    compilation=case.compilation,
                )
            )
            normalized = copy.deepcopy(
                evidence.private_evidence[
                    "normalized_semantic_choice"
                ]
            )
            error_category = evidence.private_evidence[
                "error_category"
            ]
            semantic_exact = evidence.private_evidence[
                "semantic_exact_match"
            ]
            if (
                semantic_exact is not (normalized == expected_answer)
                or (
                    error_category is not None
                    and error_category
                    not in {
                        ERROR_WRONG_TYPED_TYPE,
                        ERROR_UNSAFE_TYPED,
                        ERROR_SAFE_UNDER_TYPING,
                        ERROR_WRONG_UNCLASSIFIED_REASON,
                    }
                )
                or (semantic_exact and error_category is not None)
                or (not semantic_exact and error_category is None)
            ):
                _fail(
                    "financial_semantic_v6_context_v2_1_"
                    "budget_smoke_semantic_comparison_invalid"
                )
            outcome = (
                Gate2FinancialSemanticV6ContextV21BudgetSmokeCaseOutcome(
                    slot_id=slot.slot_id,
                    ordinal=slot.ordinal,
                    provider_profile_id=slot.provider_profile_id,
                    exact_model_id=slot.exact_model_id,
                    case_id=slot.case_id,
                    taxonomy_state=slot.taxonomy_state,
                    operation_identity_sha256=_sha256_text(
                        operation_identity
                    ),
                    status="passed" if semantic_exact else "failed",
                    technical_pipeline_exact=True,
                    semantic_answer_exact=semantic_exact,
                    error_category=error_category,
                    failure_code=None,
                    failure_class=None,
                    expected_answer=copy.deepcopy(expected_answer),
                    normalized_answer=normalized,
                    adapter_extracted_output=copy.deepcopy(
                        result.adapter_extracted_output
                    ),
                    sealed_request=projection.sealed_request,
                    prepared_request=result.prepared_request,
                    evidence_bundle=evidence,
                    private_evidence=copy.deepcopy(
                        evidence.private_evidence
                    ),
                    safe_receipt=copy.deepcopy(evidence.safe_receipt),
                    **lifecycle,
                )
            )
        except Exception as exc:
            lifecycle = _lifecycle_delta(
                before=lifecycle_before,
                after=client.qualification_lifecycle_snapshot(),
            )
            outcome = self._failure_outcome(
                slot=slot,
                case=case,
                expected_answer=expected_answer,
                projection=projection,
                operation_identity=operation_identity,
                lifecycle=lifecycle,
                exc=exc,
                elapsed_ms=_elapsed_ms(started),
                result=result,
            )
        self._checkpoint(outcome)
        return outcome

    def record_preflight_failure(
        self,
        *,
        slot: Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot,
        failure_code: str,
        failure_class: str,
        raw_output: Any = None,
    ) -> Gate2FinancialSemanticV6ContextV21BudgetSmokeCaseOutcome:
        if slot not in self.plan.slots:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_slot_invalid"
            )
        case = self._cases[slot.case_id]
        expected_answer = (
            resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer(
                plan=self.plan,
                slot=slot,
                fixture=self.fixture,
                outcome_audit_manifest=self.outcome_audit_manifest,
                provider_profile_resolver=self.provider_profile_resolver,
            )
        )
        projection = self._projector(
            case=case,
            provider_profile=self.provider_profile_resolver(
                slot.provider_profile_id
            ),
            exact_model_id=slot.exact_model_id,
            request_profile=slot.request_profile,
            parameters=slot.parameters,
        )
        _validate_slot_projection(slot=slot, projection=projection)
        operation_identity = (
            financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
                plan=self.plan,
                slot=slot,
                provider_profile_resolver=self.provider_profile_resolver,
            )
        )
        return self._preflight_failure(
            slot=slot,
            case=case,
            expected_answer=expected_answer,
            projection=projection,
            operation_identity=operation_identity,
            failure_code=failure_code,
            failure_class=failure_class,
            raw_output=raw_output,
        )

    def record_consumed_slot_failure(
        self,
        *,
        slot: Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot,
    ) -> Gate2FinancialSemanticV6ContextV21BudgetSmokeCaseOutcome:
        if slot not in self.plan.slots:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_slot_invalid"
            )
        case = self._cases[slot.case_id]
        expected_answer = (
            resolve_financial_semantic_v6_context_v2_1_budget_smoke_expected_answer(
                plan=self.plan,
                slot=slot,
                fixture=self.fixture,
                outcome_audit_manifest=self.outcome_audit_manifest,
                provider_profile_resolver=self.provider_profile_resolver,
            )
        )
        projection = self._projector(
            case=case,
            provider_profile=self.provider_profile_resolver(
                slot.provider_profile_id
            ),
            exact_model_id=slot.exact_model_id,
            request_profile=slot.request_profile,
            parameters=slot.parameters,
        )
        _validate_slot_projection(slot=slot, projection=projection)
        operation_identity = (
            financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
                plan=self.plan,
                slot=slot,
                provider_profile_resolver=self.provider_profile_resolver,
            )
        )
        exc = Gate2SourceFactRuntimeError(
            "consumed_slot_response_unavailable",
            "Consumed slot has no recoverable terminal response",
            failure_class="provider_transport",
        )
        outcome = self._failure_outcome(
            slot=slot,
            case=case,
            expected_answer=expected_answer,
            projection=projection,
            operation_identity=operation_identity,
            lifecycle={
                "local_invocations_total": 1,
                "provider_submissions_total": 1,
                "provider_responses_total": 0,
                "semantic_repair_total": 0,
                "retry_total": 0,
                "repair_total": 0,
                "fallback_total": 0,
            },
            exc=exc,
            elapsed_ms=0,
            result=None,
        )
        self._checkpoint(outcome)
        return outcome

    def _preflight_failure(
        self,
        *,
        slot: Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot,
        case: Gate2FinancialSemanticV6QualificationCase,
        expected_answer: dict[str, Any],
        projection: (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection
        ),
        operation_identity: str,
        failure_code: str,
        failure_class: str,
        raw_output: Any,
    ) -> Gate2FinancialSemanticV6ContextV21BudgetSmokeCaseOutcome:
        lifecycle = {
            "local_invocations_total": 0,
            "provider_submissions_total": 0,
            "provider_responses_total": 0,
            "semantic_repair_total": 0,
            "retry_total": 0,
            "repair_total": 0,
            "fallback_total": 0,
        }
        exc = Gate2SourceFactRuntimeError(
            failure_code,
            "Provider preflight did not authorize a submission",
            raw_output=copy.deepcopy(raw_output),
            failure_class=failure_class,
        )
        outcome = self._failure_outcome(
            slot=slot,
            case=case,
            expected_answer=expected_answer,
            projection=projection,
            operation_identity=operation_identity,
            lifecycle=lifecycle,
            exc=exc,
            elapsed_ms=0,
            result=None,
        )
        self._checkpoint(outcome)
        return outcome

    def _failure_outcome(
        self,
        *,
        slot: Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot,
        case: Gate2FinancialSemanticV6QualificationCase,
        expected_answer: dict[str, Any],
        projection: (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection
        ),
        operation_identity: str,
        lifecycle: dict[str, int],
        exc: Exception,
        elapsed_ms: int,
        result: Gate2ContextV21BudgetSmokeModelResult | None,
    ) -> Gate2FinancialSemanticV6ContextV21BudgetSmokeCaseOutcome:
        failure_code = str(
            getattr(exc, "code", None) or exc.__class__.__name__
        )
        failure_class = str(
            getattr(exc, "failure_class", None)
            or exc.__class__.__name__
        )
        error_category = _technical_error_category(
            failure_code=failure_code,
            failure_class=failure_class,
        )
        prepared_request = (
            result.prepared_request
            if result is not None
            else projection.prepared_request
        )
        adapter_extracted_output = (
            result.adapter_extracted_output
            if result is not None
            else getattr(exc, "adapter_extracted_output", None)
        )
        raw_provider_response = (
            result.raw_provider_response
            if result is not None
            else getattr(exc, "raw_provider_response", None)
        )
        evidence = (
            Gate2FinancialSemanticV6DecisionEvidenceFactory(
                registry=self.registry,
                exact_model_id=slot.exact_model_id,
                provider_profile_id=slot.provider_profile_id,
            ).create_context_v2_1_budget_smoke_failure(
                plan=self.plan,
                plan_slot=slot,
                operation_identity=operation_identity,
                sealed_request=projection.sealed_request,
                prepared_request=prepared_request,
                lifecycle=lifecycle,
                expected_answer=expected_answer,
                failure_code=failure_code,
                failure_class=failure_class,
                error_category=error_category,
                adapter_extracted_output=copy.deepcopy(
                    adapter_extracted_output
                ),
                raw_output=copy.deepcopy(
                    raw_provider_response
                    if raw_provider_response is not None
                    else (
                        getattr(exc, "raw_output", None)
                    )
                ),
                execution_metadata=(
                    getattr(exc, "execution_metadata", None)
                    or (
                        result.execution_metadata
                        if result is not None
                        else None
                    )
                ),
                economy_budget_receipt=(
                    getattr(exc, "economy_budget_receipt", None)
                    or (
                        result.economy_budget_receipt
                        if result is not None
                        else None
                    )
                ),
                elapsed_ms=elapsed_ms,
                choice_contract=case.choice_contract,
                packet=case.packet,
                evidence_bundle=case.evidence_bundle,
                source_package=case.scope.source_package,
                compilation=case.compilation,
            )
        )
        return Gate2FinancialSemanticV6ContextV21BudgetSmokeCaseOutcome(
            slot_id=slot.slot_id,
            ordinal=slot.ordinal,
            provider_profile_id=slot.provider_profile_id,
            exact_model_id=slot.exact_model_id,
            case_id=slot.case_id,
            taxonomy_state=slot.taxonomy_state,
            operation_identity_sha256=_sha256_text(
                operation_identity
            ),
            status="failed",
            technical_pipeline_exact=False,
            semantic_answer_exact=False,
            error_category=error_category,
            failure_code=failure_code,
            failure_class=failure_class,
            expected_answer=copy.deepcopy(expected_answer),
            normalized_answer=None,
            adapter_extracted_output=copy.deepcopy(
                adapter_extracted_output
            ),
            sealed_request=projection.sealed_request,
            prepared_request=prepared_request,
            evidence_bundle=evidence,
            private_evidence=copy.deepcopy(
                evidence.private_evidence
            ),
            safe_receipt=copy.deepcopy(evidence.safe_receipt),
            **lifecycle,
        )

    def _checkpoint(
        self,
        outcome: (
            Gate2FinancialSemanticV6ContextV21BudgetSmokeCaseOutcome
        ),
    ) -> None:
        self.private_checkpoint(
            outcome.slot_id,
            {
                "private_evidence": copy.deepcopy(
                    outcome.private_evidence
                ),
                "safe_receipt": copy.deepcopy(outcome.safe_receipt),
                "materialized_artifact": copy.deepcopy(
                    getattr(
                        outcome.evidence_bundle,
                        "materialized_artifact",
                        None,
                    )
                ),
            },
        )
        if self.safe_checkpoint is not None:
            self.safe_checkpoint(
                outcome.slot_id,
                outcome.safe_summary(),
            )


def _validate_slot_projection(
    *,
    slot: Gate2FinancialSemanticV6ContextV21BudgetSmokePlanSlot,
    projection: (
        Gate2FinancialSemanticV6ContextV21BudgetSmokeSlotProjection
    ),
) -> None:
    sealed = projection.sealed_request
    prepared = projection.prepared_request
    transport_contract = projection.transport_contract
    if (
        type(transport_contract)
        is not Gate2ContextV21BudgetSmokeTransportContract
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_slot_projection_mismatch"
        )
    transport_snapshot = transport_contract.safe_snapshot()
    if (
        sha256_json(asdict(sealed)) != slot.sealed_request_hash
        or sealed.sealed_request_receipt.integrity_hash
        != slot.sealed_request_receipt_integrity_hash
        or sealed.sealed_request_receipt.model_visible_request_hash
        != slot.model_visible_request_hash
        or sha256_json(
            sealed.response_format["json_schema"]["schema"]
        )
        != slot.canonical_schema_hash
        or sha256_json(asdict(prepared))
        != slot.prepared_request_hash
        or sha256_json(prepared.provider_visible_schema)
        != slot.provider_visible_schema_hash
        or transport_snapshot != slot.transport_contract
        or transport_contract.integrity_hash
        != slot.transport_contract_hash
        or sha256_json(transport_snapshot)
        != slot.transport_contract_hash
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_slot_projection_mismatch"
        )


def _technical_error_category(
    *,
    failure_code: str,
    failure_class: str,
) -> str:
    if (
        failure_class in _INVALID_RESPONSE_FAILURE_CLASSES
        or failure_code in _INVALID_RESPONSE_FAILURE_CODES
    ):
        return ERROR_INVALID_RESPONSE
    return ERROR_INFRASTRUCTURE_PROVIDER_FAILURE


def _lifecycle_delta(
    *,
    before: dict[str, int],
    after: dict[str, int],
) -> dict[str, int]:
    expected = {
        "local_invocations_total",
        "provider_submissions_total",
        "provider_responses_total",
    }
    if (
        not isinstance(before, dict)
        or not isinstance(after, dict)
        or set(before) != expected
        or set(after) != expected
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_lifecycle_invalid"
        )
    values = {
        key: after[key] - before[key]
        for key in sorted(expected)
    }
    if (
        any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > 1
            for value in values.values()
        )
        or values["provider_responses_total"]
        > values["provider_submissions_total"]
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_lifecycle_invalid"
        )
    return {
        **values,
        "semantic_repair_total": 0,
        "retry_total": 0,
        "repair_total": 0,
        "fallback_total": 0,
    }


def _elapsed_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6ContextV21BudgetSmokeError(code)
