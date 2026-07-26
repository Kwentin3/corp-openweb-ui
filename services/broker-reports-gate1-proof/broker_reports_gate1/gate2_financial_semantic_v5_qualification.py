from __future__ import annotations

import copy
import re
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Callable

from .gate2_deterministic_financial_scopes import (
    Gate2DeterministicFinancialScope,
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from .gate2_economy_budget import Gate2EconomyBudgetSessionFactory
from .gate2_economy_model_policy import WORKLOAD_GATE2_FINANCIAL_EVIDENCE
from .gate2_economy_qualification_policy import (
    Gate2EconomyQualificationContractIdentity,
    Gate2EconomyQualificationPolicyFactory,
)
from .gate2_financial_context import Gate2FinancialContextProjectionFactory
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_evidence_source_context import (
    Gate2FinancialEvidenceSourceContextFactory,
)
from .gate2_financial_semantic_v5_ambiguity import (
    V5_BINDING_AMBIGUITY_POLICY_VERSION,
    Gate2FinancialSemanticV5AmbiguityGuardFactory,
    Gate2FinancialSemanticV5AmbiguityResult,
)
from .gate2_financial_semantic_v5_benchmark import (
    V5_RISK_BENCHMARK_SHA256,
    validate_financial_semantic_v5_benchmark,
)
from .gate2_financial_semantic_v5_contract import (
    V5_MODEL_CONTRACT_POLICY_VERSION,
    V5_MODEL_CONTRACT_SCHEMA_VERSION,
    Gate2FinancialSemanticV5ModelContract,
    Gate2FinancialSemanticV5ModelContractFactory,
)
from .gate2_financial_semantic_v5_evidence import (
    V5_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION,
    V5_SAFE_DECISION_RECEIPT_SCHEMA_VERSION,
    Gate2FinancialSemanticV5DecisionEvidenceFactory,
    Gate2FinancialSemanticV5ProviderCallReceipt,
)
from .gate2_financial_semantic_v5_execution import (
    V5_PROMPT_VERSION,
    Gate2FinancialSemanticV5ExecutionContract,
    Gate2FinancialSemanticV5ExecutionContractFactory,
)
from .gate2_financial_semantic_v5_local_proof import (
    Gate2FinancialSemanticV5LocalProofFactory,
)
from .gate2_financial_semantic_v5_packet import (
    V5_DECISION_PACKET_SCHEMA_VERSION,
    Gate2FinancialSemanticV5DecisionPacket,
    Gate2FinancialSemanticV5DecisionPacketFactory,
    structural_binding_candidates_from_source_context,
)
from .gate2_financial_semantic_v5_preclose import (
    Gate2FinancialSemanticV5PrecloseFactory,
    Gate2TechnicalPrecloseEvidence,
)
from .gate2_financial_semantic_v5_projection import (
    V5_SEMANTIC_PROJECTION_SCHEMA_VERSION,
    V5_SEMANTIC_PROJECTION_VERSION,
    Gate2FinancialSemanticV5Projection,
    Gate2FinancialSemanticV5ProjectionFactory,
)
from .gate2_model_contracts import (
    Gate2StructuredModelClient,
    gate2_provider_execution_safe_metadata,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from .gate2_successor_local_proof import _fixture_package, _model_output
from .gate2_successor_product_comparator import (
    Gate2SuccessorProductComparatorFactory,
    Gate2SuccessorProductExpectation,
    Gate2SuccessorScopeObservation,
)


V5_QUALIFICATION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v5_qualification_v1"
)
V5_QUALIFICATION_POLICY_VERSION = (
    "broker_reports_gate2_nano_v5_one_attempt_qualification_v1"
)
EXACT_MODEL_ID = "gpt-5.4-nano-2026-03-17"
PROVIDER_PROFILE_ID = "openai_gpt"
SEMANTIC_CASES_TOTAL = 10
TECHNICAL_CASES_TOTAL = 2
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV5QualificationFixtureFactory.create, "
    "Gate2FinancialSemanticV5QualificationPreflightFactory.create and "
    "qualify_financial_semantic_v5 are the only V5 qualification routes"
)
FORBIDDEN = (
    "The V5 qualification route must not use customer data, aliases, "
    "fallback, repair, hidden retry, paid tools, production admission, "
    "technical-case provider calls or repository-safe private evidence"
)

_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class Gate2FinancialSemanticV5QualificationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV5QualificationCase:
    case_id: str
    feature_families: tuple[str, ...]
    route: str
    expected_disposition: str
    expected_input_type_id: str | None
    scope: Gate2DeterministicFinancialScope
    expected_model_output: dict[str, Any]
    execution: Gate2FinancialSemanticV5ExecutionContract | None = None
    projection: Gate2FinancialSemanticV5Projection | None = None
    ambiguity: Gate2FinancialSemanticV5AmbiguityResult | None = None
    packet: Gate2FinancialSemanticV5DecisionPacket | None = None
    model_contract: Gate2FinancialSemanticV5ModelContract | None = None


@dataclass(frozen=True)
class Gate2FinancialSemanticV5QualificationFixture:
    registry: Gate2FinancialEvidenceRegistrySnapshot
    local_proof_receipt: dict[str, Any]
    benchmark_hash: str
    cases: tuple[Gate2FinancialSemanticV5QualificationCase, ...]

    @property
    def semantic_cases(
        self,
    ) -> tuple[Gate2FinancialSemanticV5QualificationCase, ...]:
        return tuple(item for item in self.cases if item.route == "semantic_model")


class Gate2FinancialSemanticV5QualificationFixtureFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        snapshot_authority_key: bytes,
        continuation_key: bytes,
    ) -> None:
        self.registry = registry
        self._snapshot_authority_key = bytes(snapshot_authority_key)
        self._continuation_key = bytes(continuation_key)

    def create(
        self,
        *,
        manifest: dict[str, Any],
        base_manifest: dict[str, Any],
    ) -> Gate2FinancialSemanticV5QualificationFixture:
        frozen_manifest = copy.deepcopy(manifest)
        frozen_base = copy.deepcopy(base_manifest)
        validate_financial_semantic_v5_benchmark(
            manifest=frozen_manifest,
            base_manifest=frozen_base,
        )
        local_proof = Gate2FinancialSemanticV5LocalProofFactory(
            registry=self.registry,
            snapshot_authority_key=self._snapshot_authority_key,
            continuation_key=self._continuation_key,
        ).create(
            manifest=frozen_manifest,
            base_manifest=frozen_base,
        )
        if (
            local_proof.get("status") != "passed"
            or local_proof.get("execution_accounting", {}).get(
                "provider_calls_total"
            )
            != 0
        ):
            _fail("financial_semantic_v5_qualification_local_proof_failed")

        base_cases = {item["case_id"]: item for item in frozen_base["cases"]}
        scope_factory = Gate2DeterministicFinancialScopeFromGate1V2Factory(
            registry=self.registry
        )
        context_factory = Gate2FinancialEvidenceSourceContextFactory()
        projection = Gate2FinancialSemanticV5ProjectionFactory().create()
        execution = Gate2FinancialSemanticV5ExecutionContractFactory().create()
        cases: list[Gate2FinancialSemanticV5QualificationCase] = []
        for benchmark_case in frozen_manifest["cases"]:
            case_id = benchmark_case["case_id"]
            source_case = copy.deepcopy(base_cases[case_id])
            fixture = _fixture_package(source_case)
            batch = scope_factory.create(gate1_packages=(fixture.payload,))
            if len(batch.scopes) != 1:
                _fail("financial_semantic_v5_qualification_scope_invalid")
            scope = batch.scopes[0]
            route = benchmark_case["expected_route"]
            if route == "technical_preclose":
                preclose = Gate2FinancialSemanticV5PrecloseFactory().create(
                    evidence=Gate2TechnicalPrecloseEvidence(
                        **benchmark_case["technical_evidence"]
                    )
                )
                if (
                    preclose.provider_call_required is not False
                    or preclose.canonical_decision is None
                ):
                    _fail(
                        "financial_semantic_v5_qualification_preclose_invalid"
                    )
                model_output = copy.deepcopy(preclose.canonical_decision)
                case = Gate2FinancialSemanticV5QualificationCase(
                    case_id=case_id,
                    feature_families=tuple(
                        benchmark_case["feature_families"]
                    ),
                    route=route,
                    expected_disposition=benchmark_case[
                        "expected_disposition"
                    ],
                    expected_input_type_id=benchmark_case[
                        "expected_input_type_id"
                    ],
                    scope=scope,
                    expected_model_output=model_output,
                )
            else:
                source_context = context_factory.create(
                    source_scope_ref=scope.source_package.source_scope_ref,
                    source_values=scope.source_package.source_values,
                    candidates=scope.decision_contract.package.candidates,
                    gate1_packages=(fixture.payload,),
                )
                candidates = structural_binding_candidates_from_source_context(
                    source_context=source_context
                )
                preclose = Gate2FinancialSemanticV5PrecloseFactory().create(
                    evidence=Gate2TechnicalPrecloseEvidence(
                        source_support="supported",
                        authoritative_layout_only=False,
                        source_value_candidates_total=len(candidates),
                        scope_valid=True,
                    )
                )
                if preclose.provider_call_required is not True:
                    _fail(
                        "financial_semantic_v5_qualification_preclose_invalid"
                    )
                ambiguity = (
                    Gate2FinancialSemanticV5AmbiguityGuardFactory().create(
                        projection=projection,
                        candidates=candidates,
                    )
                )
                packet = Gate2FinancialSemanticV5DecisionPacketFactory().create(
                    source_context=source_context,
                    projection=projection,
                    ambiguity=ambiguity,
                    candidates=candidates,
                    preclose=preclose,
                )
                model_contract = (
                    Gate2FinancialSemanticV5ModelContractFactory().create(
                        execution=execution,
                        projection=projection,
                        ambiguity=ambiguity,
                        packet=packet,
                        canonical_contract=scope.decision_contract,
                    )
                )
                case = Gate2FinancialSemanticV5QualificationCase(
                    case_id=case_id,
                    feature_families=tuple(
                        benchmark_case["feature_families"]
                    ),
                    route=route,
                    expected_disposition=benchmark_case[
                        "expected_disposition"
                    ],
                    expected_input_type_id=benchmark_case[
                        "expected_input_type_id"
                    ],
                    scope=scope,
                    expected_model_output=_model_output(
                        case=source_case,
                        scope=scope,
                        selected_value_refs=fixture.selected_value_refs,
                    ),
                    execution=execution,
                    projection=projection,
                    ambiguity=ambiguity,
                    packet=packet,
                    model_contract=model_contract,
                )
            cases.append(case)
        if (
            len(cases) != SEMANTIC_CASES_TOTAL + TECHNICAL_CASES_TOTAL
            or sum(item.route == "semantic_model" for item in cases)
            != SEMANTIC_CASES_TOTAL
        ):
            _fail("financial_semantic_v5_qualification_case_set_invalid")
        return Gate2FinancialSemanticV5QualificationFixture(
            registry=self.registry,
            local_proof_receipt=copy.deepcopy(local_proof),
            benchmark_hash=V5_RISK_BENCHMARK_SHA256,
            cases=tuple(cases),
        )


class Gate2FinancialSemanticV5QualificationPreflightFactory:
    def create(
        self,
        *,
        fixture: Gate2FinancialSemanticV5QualificationFixture,
        repository_revision: str,
        stage_action: dict[str, Any],
        published_model_ids: set[str],
    ) -> dict[str, Any]:
        if _REVISION_RE.fullmatch(repository_revision) is None:
            _fail("financial_semantic_v5_repository_revision_invalid")
        if EXACT_MODEL_ID not in published_model_ids:
            _fail("financial_semantic_v5_exact_model_not_published")
        if (
            not isinstance(stage_action, dict)
            or stage_action.get("production_admissions_empty") is not True
            or not all((stage_action.get("checks") or {}).values())
        ):
            _fail("financial_semantic_v5_stage_action_parity_failed")

        identity = _qualification_contract_identity(fixture)
        authorization = (
            Gate2EconomyQualificationPolicyFactory()
            .create()
            .authorize(
                workload_class=WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
                exact_model_id=EXACT_MODEL_ID,
                provider_profile_id=PROVIDER_PROFILE_ID,
                receipt_identity=identity,
            )
        )
        budget_session = Gate2EconomyBudgetSessionFactory().create(
            request_profile=FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE
        )
        case_preflights: list[dict[str, Any]] = []
        evidence_hashes: list[str] = []
        for case in fixture.semantic_cases:
            execution, projection, ambiguity, packet, model_contract = (
                _semantic_authorities(case)
            )
            request = _request(case)
            budget = budget_session.prepare_call(
                form_data=request,
                model_id=EXACT_MODEL_ID,
                provider_profile_id=PROVIDER_PROFILE_ID,
                operation_identity=f"v5-qualification:{case.case_id}",
            )
            evidence = Gate2FinancialSemanticV5DecisionEvidenceFactory().create(
                case_id=case.case_id,
                model_id=EXACT_MODEL_ID,
                canonical_request=request,
                model_output=case.expected_model_output,
                provider_receipt=(
                    Gate2FinancialSemanticV5ProviderCallReceipt(
                        input_tokens=0,
                        output_tokens=0,
                        cost_usd="0",
                        latency_ms=0,
                    )
                ),
                model_contract=model_contract,
                execution=execution,
                projection=projection,
                ambiguity=ambiguity,
                packet=packet,
                canonical_contract=case.scope.decision_contract,
                registry=fixture.registry,
                source_package=case.scope.source_package,
                execution_metadata=FinancialEvidenceExecutionMetadata(
                    execution_ref=f"execution:v5-preflight:{case.case_id}",
                    decision_validation_ref=(
                        f"validation:v5-preflight:{case.case_id}"
                    ),
                ),
            )
            evidence_hashes.append(
                evidence.private_evidence["private_evidence_hash"]
            )
            case_preflights.append(
                {
                    "case_id": case.case_id,
                    "canonical_request_hash": sha256_json(request),
                    "packet_hash": packet.packet_hash,
                    "response_schema_hash": (
                        model_contract.response_format_hash
                    ),
                    "estimated_input_tokens": (
                        budget.estimated_input_tokens
                    ),
                    "maximum_output_tokens": (
                        budget.maximum_output_tokens
                    ),
                    "estimated_cost_usd": budget.estimated_cost_usd,
                    "evidence_contract_validated": True,
                    "provider_calls_total": 0,
                }
            )

        exact_identity = _exact_identity(
            fixture=fixture,
            repository_revision=repository_revision,
            authorization=authorization.safe_receipt(),
            stage_action=stage_action,
            case_preflights=case_preflights,
        )
        receipt: dict[str, Any] = {
            "schema_version": V5_QUALIFICATION_SCHEMA_VERSION,
            "policy_version": V5_QUALIFICATION_POLICY_VERSION,
            "status": "passed",
            "preflight_only": True,
            "acceptance": {
                "v5_harness": "READY",
                "exact_identity": "PINNED",
                "local_preflight": "PASSED",
                "provider_calls": "ZERO",
                "production_admission": "EMPTY",
            },
            "exact_identity": exact_identity,
            "stage": copy.deepcopy(stage_action),
            "local_proof": {
                "status": fixture.local_proof_receipt["status"],
                "integrity_sha256": fixture.local_proof_receipt[
                    "integrity_sha256"
                ],
                "provider_calls_total": 0,
            },
            "authorization": authorization.safe_receipt(),
            "routes": {
                "cases_total": len(fixture.cases),
                "semantic_cases_total": len(fixture.semantic_cases),
                "technical_cases_total": TECHNICAL_CASES_TOTAL,
                "technical_case_provider_calls_total": 0,
            },
            "budget": {
                "planned_provider_calls_total": len(case_preflights),
                "estimated_input_tokens_total": sum(
                    item["estimated_input_tokens"]
                    for item in case_preflights
                ),
                "estimated_input_tokens_max": max(
                    item["estimated_input_tokens"]
                    for item in case_preflights
                ),
                "maximum_output_tokens_per_call": max(
                    item["maximum_output_tokens"]
                    for item in case_preflights
                ),
                "estimated_cost_usd": _sum_costs(case_preflights),
                "within_budget": True,
            },
            "evidence_contract": {
                "private_schema_version": (
                    V5_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION
                ),
                "safe_schema_version": (
                    V5_SAFE_DECISION_RECEIPT_SCHEMA_VERSION
                ),
                "cases_validated_total": len(evidence_hashes),
                "evidence_hashes_sha256": sha256_json(
                    sorted(evidence_hashes)
                ),
                "exact_replay_ready": True,
            },
            "case_preflights": case_preflights,
            "execution_accounting": {
                "provider_attempts_total": 0,
                "provider_calls_total": 0,
                "technical_case_provider_calls_total": 0,
                "fallback_total": 0,
                "repair_total": 0,
                "hidden_retry_total": 0,
                "production_admissions_total": 0,
            },
        }
        receipt["integrity_sha256"] = sha256_json(receipt)
        return receipt


async def qualify_financial_semantic_v5(
    *,
    fixture: Gate2FinancialSemanticV5QualificationFixture,
    model_client: Gate2StructuredModelClient,
    exact_identity: dict[str, Any],
    private_case_checkpoint: Callable[[str, dict[str, Any]], None],
    safe_checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    if (
        exact_identity.get("identity_hash")
        != sha256_json(
            {
                key: value
                for key, value in exact_identity.items()
                if key != "identity_hash"
            }
        )
        or exact_identity.get("exact_model_id") != EXACT_MODEL_ID
    ):
        _fail("financial_semantic_v5_qualification_identity_invalid")

    case_receipts: list[dict[str, Any]] = []
    observations: list[Gate2SuccessorScopeObservation] = []
    artifacts: list[dict[str, Any]] = []
    source_packages: list[Any] = []
    provider_calls = 0
    input_tokens = 0
    output_tokens = 0
    actual_cost = Decimal("0")
    latency_ms_total = 0
    unsafe_typed = 0
    safe_under_typed = 0
    canonical_errors = 0
    raw_invalid_refs = 0
    raw_wrong_roles = 0
    raw_duplicates = 0
    raw_cross_scope = 0
    candidate_owners = _candidate_owners(fixture)

    def current(*, terminal: bool) -> dict[str, Any]:
        return _qualification_receipt(
            fixture=fixture,
            exact_identity=exact_identity,
            case_receipts=case_receipts,
            observations=observations,
            artifacts=artifacts,
            source_packages=source_packages,
            provider_calls=provider_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost=actual_cost,
            latency_ms_total=latency_ms_total,
            unsafe_typed=unsafe_typed,
            safe_under_typed=safe_under_typed,
            canonical_errors=canonical_errors,
            raw_invalid_refs=raw_invalid_refs,
            raw_wrong_roles=raw_wrong_roles,
            raw_duplicates=raw_duplicates,
            raw_cross_scope=raw_cross_scope,
            terminal=terminal,
        )

    if safe_checkpoint is not None:
        safe_checkpoint(current(terminal=False))
    for case in fixture.cases:
        execution_ref = f"execution:v5-qualification:{case.case_id}"
        validation_ref = f"validation:v5-qualification:{case.case_id}"
        model_output: Any = copy.deepcopy(case.expected_model_output)
        if case.route == "technical_preclose":
            validated = Gate2FinancialEvidenceValidatedDecisionFactory(
                contract=case.scope.decision_contract
            ).create(model_output)
            artifact = Gate2FinancialEvidenceMaterializerFactory(
                registry=fixture.registry,
                source_package=case.scope.source_package,
                execution_metadata=FinancialEvidenceExecutionMetadata(
                    execution_ref=execution_ref,
                    decision_validation_ref=validation_ref,
                ),
            ).create().materialize(validated_decision=validated)
            receipt = {
                "case_id": case.case_id,
                "route": case.route,
                "status": "passed",
                "expected_disposition": case.expected_disposition,
                "observed_disposition": (
                    validated.decision.disposition
                ),
                "expected_input_type_id": case.expected_input_type_id,
                "observed_input_type_id": None,
                "provider_calls_total": 0,
                "canonical_validation_ran": True,
                "exact_decision_preserved": True,
            }
        else:
            model_output = None
            provider_calls += 1
            request = _request(case)
            started = time.perf_counter()
            result = None
            try:
                execution, projection, ambiguity, packet, model_contract = (
                    _semantic_authorities(case)
                )
                result = await model_client.extract(
                    prompt=execution.prompt,
                    package=packet.payload,
                    model_id=EXACT_MODEL_ID,
                    response_format=model_contract.response_format,
                )
                elapsed_ms = int(
                    round((time.perf_counter() - started) * 1000)
                )
                model_output = copy.deepcopy(result.content)
                _validate_provider_result(
                    result=result,
                    model_contract=model_contract,
                )
                budget = result.economy_budget_receipt
                if not isinstance(budget, dict) or budget.get("status") != "passed":
                    _fail(
                        "financial_semantic_v5_qualification_budget_missing"
                    )
                call_input = int(budget["input_tokens"])
                call_output = int(budget["output_tokens"])
                call_cost = Decimal(str(budget["actual_cost_usd"]))
                metadata = result.execution_metadata
                call_latency = int(
                    metadata.duration_ms
                    if metadata is not None
                    and metadata.duration_ms is not None
                    else elapsed_ms
                )
                raw = _raw_binding_risks(
                    model_output=model_output,
                    case=case,
                    candidate_owners=candidate_owners,
                )
                raw_invalid_refs += raw["invalid_refs_total"]
                raw_wrong_roles += raw["wrong_roles_total"]
                raw_duplicates += raw["duplicate_bindings_total"]
                raw_cross_scope += raw["cross_scope_bindings_total"]
                evidence = (
                    Gate2FinancialSemanticV5DecisionEvidenceFactory().create(
                        case_id=case.case_id,
                        model_id=EXACT_MODEL_ID,
                        canonical_request=request,
                        model_output=model_output,
                        provider_receipt=(
                            Gate2FinancialSemanticV5ProviderCallReceipt(
                                input_tokens=call_input,
                                output_tokens=call_output,
                                cost_usd=format(call_cost, "f"),
                                latency_ms=call_latency,
                            )
                        ),
                        model_contract=model_contract,
                        execution=execution,
                        projection=projection,
                        ambiguity=ambiguity,
                        packet=packet,
                        canonical_contract=case.scope.decision_contract,
                        registry=fixture.registry,
                        source_package=case.scope.source_package,
                        execution_metadata=(
                            FinancialEvidenceExecutionMetadata(
                                execution_ref=execution_ref,
                                decision_validation_ref=validation_ref,
                            )
                        ),
                    )
                )
                private_case_checkpoint(
                    case.case_id,
                    evidence.private_evidence,
                )
                safe = evidence.safe_receipt
                artifact = evidence.materialized_artifact
                observed = safe["decision_classification"]
                observed_disposition = observed["disposition"]
                observed_type = observed["input_type_id"]
                unsafe_typed += int(
                    observed_disposition == "typed_input"
                    and (
                        case.expected_disposition != "typed_input"
                        or observed_type != case.expected_input_type_id
                    )
                )
                safe_under_typed += int(
                    case.expected_disposition == "typed_input"
                    and observed_disposition
                    == "unclassified_financial_input"
                )
                input_tokens += call_input
                output_tokens += call_output
                actual_cost += call_cost
                latency_ms_total += call_latency
                receipt = {
                    "case_id": case.case_id,
                    "route": case.route,
                    "status": "passed",
                    "expected_disposition": case.expected_disposition,
                    "observed_disposition": observed_disposition,
                    "expected_input_type_id": case.expected_input_type_id,
                    "observed_input_type_id": observed_type,
                    "provider_calls_total": 1,
                    "canonical_validation_ran": True,
                    "exact_decision_preserved": True,
                    "safe_decision_receipt": safe,
                    "provider_execution": (
                        gate2_provider_execution_safe_metadata(
                            result.execution_metadata
                        )
                    ),
                }
            except Exception as exc:
                canonical_errors += 1
                elapsed_ms = int(
                    round((time.perf_counter() - started) * 1000)
                )
                private_case_checkpoint(
                    case.case_id,
                    {
                        "schema_version": (
                            "broker_reports_gate2_financial_semantic_v5_"
                            "private_failure_evidence_v1"
                        ),
                        "case_id": case.case_id,
                        "exact_canonical_request_object": request,
                        "canonical_request_hash": sha256_json(request),
                        "model_output": copy.deepcopy(model_output),
                        "failure_code": str(
                            getattr(exc, "code", exc.__class__.__name__)
                        ),
                        "elapsed_ms": elapsed_ms,
                    },
                )
                receipt = {
                    "case_id": case.case_id,
                    "route": case.route,
                    "status": "failed",
                    "expected_disposition": case.expected_disposition,
                    "expected_input_type_id": case.expected_input_type_id,
                    "provider_calls_total": 1,
                    "failure_code": str(
                        getattr(exc, "code", exc.__class__.__name__)
                    ),
                    "canonical_validation_ran": False,
                    "provider_decision_returned": (
                        model_output is not None
                    ),
                    "exact_decision_preserved": (
                        model_output is not None
                    ),
                }
                continue_after_failure = True
                if result is not None and isinstance(
                    result.economy_budget_receipt, dict
                ):
                    budget = result.economy_budget_receipt
                    input_tokens += int(budget.get("input_tokens") or 0)
                    output_tokens += int(budget.get("output_tokens") or 0)
                    actual_cost += Decimal(
                        str(budget.get("actual_cost_usd") or "0")
                    )
                latency_ms_total += elapsed_ms
                if not continue_after_failure:  # pragma: no cover
                    raise
        case_receipts.append(receipt)
        if receipt["status"] == "passed":
            observations.append(
                Gate2SuccessorScopeObservation(
                    source_scope_ref=(
                        case.scope.source_package.source_scope_ref
                    ),
                    model_output=copy.deepcopy(model_output),
                    materialized_artifact=copy.deepcopy(artifact),
                    execution_ref=execution_ref,
                    decision_validation_ref=validation_ref,
                    expectation=Gate2SuccessorProductExpectation(
                        expected_disposition=case.expected_disposition,
                        expected_input_type_id=case.expected_input_type_id,
                    ),
                )
            )
            artifacts.append(copy.deepcopy(artifact))
            source_packages.append(case.scope.source_package)
        if safe_checkpoint is not None:
            safe_checkpoint(current(terminal=False))
    terminal_receipt = current(terminal=True)
    if safe_checkpoint is not None:
        safe_checkpoint(terminal_receipt)
    return terminal_receipt


def _qualification_receipt(
    *,
    fixture: Gate2FinancialSemanticV5QualificationFixture,
    exact_identity: dict[str, Any],
    case_receipts: list[dict[str, Any]],
    observations: list[Gate2SuccessorScopeObservation],
    artifacts: list[dict[str, Any]],
    source_packages: list[Any],
    provider_calls: int,
    input_tokens: int,
    output_tokens: int,
    actual_cost: Decimal,
    latency_ms_total: int,
    unsafe_typed: int,
    safe_under_typed: int,
    canonical_errors: int,
    raw_invalid_refs: int,
    raw_wrong_roles: int,
    raw_duplicates: int,
    raw_cross_scope: int,
    terminal: bool,
) -> dict[str, Any]:
    passed_cases = sum(item["status"] == "passed" for item in case_receipts)
    observed_typed = sum(
        item.get("observed_disposition") == "typed_input"
        for item in case_receipts
    )
    expected_typed = sum(
        item.expected_disposition == "typed_input" for item in fixture.cases
    )
    true_typed = sum(
        item.get("observed_disposition") == "typed_input"
        and item.get("observed_input_type_id")
        == item.get("expected_input_type_id")
        for item in case_receipts
    )
    unclassified = sum(
        item.get("observed_disposition")
        == "unclassified_financial_input"
        for item in case_receipts
    )
    comparator = None
    comparator_metrics = {
        "literal_loss_total": 0,
        "terminal_ownership_gap_total": sum(
            len(case.scope.selected_source_refs)
            for case in fixture.cases
            if case.case_id
            not in {item["case_id"] for item in case_receipts if item["status"] == "passed"}
        ),
        "invented_values_total": raw_invalid_refs,
        "duplicate_bindings_total": raw_duplicates,
        "cross_scope_bindings_total": raw_cross_scope,
    }
    if terminal and len(observations) == len(fixture.cases):
        context = Gate2FinancialContextProjectionFactory(
            registry=fixture.registry
        ).create(
            materialized_artifacts=artifacts,
            source_packages=source_packages,
        )
        comparator = Gate2SuccessorProductComparatorFactory(
            registry=fixture.registry
        ).create().compare(
            authorized_scopes=(item.scope for item in fixture.cases),
            observations=observations,
            final_context=context,
        )
        comparator_metrics = comparator["metrics"]
    hard_gates = {
        "unsafe_typed_total": unsafe_typed,
        "data_loss_total": comparator_metrics["literal_loss_total"],
        "inventions_total": max(
            raw_invalid_refs,
            comparator_metrics["invented_values_total"],
        ),
        "invalid_refs_total": raw_invalid_refs,
        "wrong_roles_total": raw_wrong_roles,
        "duplicate_bindings_total": max(
            raw_duplicates,
            comparator_metrics["duplicate_bindings_total"],
        ),
        "cross_scope_bindings_total": max(
            raw_cross_scope,
            comparator_metrics["cross_scope_bindings_total"],
        ),
        "ownership_gaps_total": comparator_metrics[
            "terminal_ownership_gap_total"
        ],
        "canonical_materialization_errors_total": canonical_errors,
    }
    all_hard_gates_zero = all(value == 0 for value in hard_gates.values())
    terminal_complete = (
        terminal
        and len(case_receipts) == len(fixture.cases)
        and provider_calls == SEMANTIC_CASES_TOTAL
    )
    product_status = (
        "MODEL_SAFE_FOR_SHADOW"
        if terminal_complete
        and passed_cases == len(fixture.cases)
        and all_hard_gates_zero
        else "MODEL_NOT_SAFE_FOR_SHADOW"
        if terminal_complete
        else None
    )
    receipt: dict[str, Any] = {
        "schema_version": V5_QUALIFICATION_SCHEMA_VERSION,
        "policy_version": V5_QUALIFICATION_POLICY_VERSION,
        "execution_state": "terminal" if terminal else "in_progress",
        "status": (
            "passed"
            if product_status == "MODEL_SAFE_FOR_SHADOW"
            else "failed"
            if terminal
            else "in_progress"
        ),
        "product_gate": product_status,
        "exact_identity": copy.deepcopy(exact_identity),
        "attempt_accounting": {
            "provider_attempts_total": 1,
            "provider_calls_total": provider_calls,
            "semantic_cases_total": SEMANTIC_CASES_TOTAL,
            "technical_cases_total": TECHNICAL_CASES_TOTAL,
            "technical_case_provider_calls_total": 0,
            "hidden_retry_total": 0,
            "fallback_total": 0,
            "repair_total": 0,
        },
        "hard_gates": hard_gates,
        "quality": {
            "typed_precision_basis_points": _rate(
                true_typed, observed_typed
            ),
            "typed_recall_basis_points": _rate(
                true_typed, expected_typed
            ),
            "safe_under_typed_total": safe_under_typed,
            "safe_under_typed_rate_basis_points": _rate(
                safe_under_typed, expected_typed
            ),
            "unclassified_total": unclassified,
            "unclassified_rate_basis_points": _rate(
                unclassified, SEMANTIC_CASES_TOTAL
            ),
        },
        "provider_metrics": {
            "input_tokens_total": input_tokens,
            "output_tokens_total": output_tokens,
            "actual_cost_usd": format(actual_cost, "f"),
            "latency_total_ms": latency_ms_total,
            "latency_average_ms": (
                latency_ms_total // provider_calls if provider_calls else 0
            ),
        },
        "cases_total": len(fixture.cases),
        "cases_executed": len(case_receipts),
        "cases_passed": passed_cases,
        "cases_failed": len(case_receipts) - passed_cases,
        "case_receipts": copy.deepcopy(case_receipts),
        "product_comparator": (
            None
            if comparator is None
            else {
                "status": comparator["status"],
                "checks": copy.deepcopy(comparator["checks"]),
                "metrics": copy.deepcopy(comparator["metrics"]),
            }
        ),
        "exact_decisions_preserved": all(
            item.get("exact_decision_preserved") is True
            for item in case_receipts
            if item.get("provider_decision_returned", True)
        ),
        "raw_private_data_in_receipt": False,
    }
    receipt["integrity_sha256"] = sha256_json(receipt)
    return receipt


def _qualification_contract_identity(
    fixture: Gate2FinancialSemanticV5QualificationFixture,
) -> Gate2EconomyQualificationContractIdentity:
    profile = gate2_provider_profile(PROVIDER_PROFILE_ID)
    contracts = [
        _semantic_authorities(item)[4] for item in fixture.semantic_cases
    ]
    execution = _semantic_authorities(fixture.semantic_cases[0])[0]
    projection = _semantic_authorities(fixture.semantic_cases[0])[1]
    return Gate2EconomyQualificationContractIdentity(
        provider_route_revision=gate2_provider_profile_revision(profile),
        input_contract_version=(
            f"{V5_DECISION_PACKET_SCHEMA_VERSION}:"
            f"{V5_SEMANTIC_PROJECTION_SCHEMA_VERSION}:"
            f"{V5_SEMANTIC_PROJECTION_VERSION}:"
            f"{projection.projection_hash}:"
            f"{fixture.benchmark_hash}"
        ),
        output_contract_version=(
            f"{V5_MODEL_CONTRACT_SCHEMA_VERSION}:"
            f"{V5_MODEL_CONTRACT_POLICY_VERSION}:"
            f"{sha256_json(sorted(item.response_format_hash for item in contracts))}"
        ),
        prompt_version=f"{V5_PROMPT_VERSION}:{execution.prompt.hash}",
        adapter_projection_revision=(
            f"{profile.adapter_id}:{profile.adapter_version}:"
            f"{FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE}"
        ),
        canonical_validator_revision=(
            "gate2_financial_evidence_canonical_validator:"
            f"{sha256_json(sorted(item.canonical_schema_hash for item in contracts))}:"
            f"{V5_BINDING_AMBIGUITY_POLICY_VERSION}:"
            f"{sha256_json(sorted(item.ambiguity_policy_hash for item in contracts))}"
        ),
    )


def _exact_identity(
    *,
    fixture: Gate2FinancialSemanticV5QualificationFixture,
    repository_revision: str,
    authorization: dict[str, Any],
    stage_action: dict[str, Any],
    case_preflights: list[dict[str, Any]],
) -> dict[str, Any]:
    local_contracts = fixture.local_proof_receipt["exact_contracts"]
    material = {
        "repository_revision": repository_revision,
        "model_input_schema": V5_DECISION_PACKET_SCHEMA_VERSION,
        "projection_version": local_contracts["projection_version"],
        "projection_hash": local_contracts["projection_hash"],
        "prompt_version": local_contracts["prompt_version"],
        "prompt_hash": local_contracts["prompt_hash"],
        "ambiguity_policy_version": (
            V5_BINDING_AMBIGUITY_POLICY_VERSION
        ),
        "ambiguity_policy_hashes_sha256": sha256_json(
            sorted(
                _semantic_authorities(item)[2].policy_hash
                for item in fixture.semantic_cases
            )
        ),
        "provider_schema_version": V5_MODEL_CONTRACT_SCHEMA_VERSION,
        "provider_schema_hashes_sha256": sha256_json(
            sorted(
                item["response_schema_hash"] for item in case_preflights
            )
        ),
        "benchmark_hash": fixture.benchmark_hash,
        "exact_model_id": EXACT_MODEL_ID,
        "provider_profile_id": PROVIDER_PROFILE_ID,
        "request_profile": FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
        "workload_class": WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
        "workload_policy_version": authorization[
            "workload_policy_version"
        ],
        "workload_policy_hash": authorization["workload_policy_hash"],
        "qualification_authorization_hash": authorization[
            "authorization_identity_sha256"
        ],
        "stage_action_content_hash": stage_action["content_sha256"],
        "attempt_policy": {
            "full_scope_attempts_total": 1,
            "semantic_provider_calls_total": SEMANTIC_CASES_TOTAL,
            "technical_provider_calls_total": 0,
            "fallback_total": 0,
            "repair_total": 0,
            "hidden_retry_total": 0,
        },
    }
    return {**material, "identity_hash": sha256_json(material)}


def _request(
    case: Gate2FinancialSemanticV5QualificationCase,
) -> dict[str, Any]:
    execution, _, _, packet, model_contract = _semantic_authorities(case)
    return Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE
    ).build(
        prompt=execution.prompt,
        package=packet.payload,
        model_id=EXACT_MODEL_ID,
        response_format=model_contract.response_format,
    )


def _semantic_authorities(
    case: Gate2FinancialSemanticV5QualificationCase,
) -> tuple[
    Gate2FinancialSemanticV5ExecutionContract,
    Gate2FinancialSemanticV5Projection,
    Gate2FinancialSemanticV5AmbiguityResult,
    Gate2FinancialSemanticV5DecisionPacket,
    Gate2FinancialSemanticV5ModelContract,
]:
    values = (
        case.execution,
        case.projection,
        case.ambiguity,
        case.packet,
        case.model_contract,
    )
    if any(value is None for value in values):
        _fail("financial_semantic_v5_semantic_case_authority_missing")
    return values  # type: ignore[return-value]


def _validate_provider_result(
    *,
    result: Any,
    model_contract: Gate2FinancialSemanticV5ModelContract,
) -> None:
    metadata = getattr(result, "execution_metadata", None)
    if (
        metadata is None
        or metadata.provider_profile_id != PROVIDER_PROFILE_ID
        or metadata.requested_model_id != EXACT_MODEL_ID
        or metadata.resolved_model_id != EXACT_MODEL_ID
        or metadata.response_format_type != "json_schema"
        or metadata.response_format_schema_mode != "strict_json_schema"
        or metadata.canonical_request_schema_hash
        != model_contract.response_format_hash
        or getattr(result, "fallback_used", None) is not False
        or getattr(result, "repair_attempt_count", None) != 0
    ):
        _fail("financial_semantic_v5_provider_execution_identity_invalid")


def _candidate_owners(
    fixture: Gate2FinancialSemanticV5QualificationFixture,
) -> dict[str, set[str]]:
    owners: dict[str, set[str]] = {}
    for case in fixture.cases:
        scope_ref = case.scope.source_package.source_scope_ref
        for candidate in case.scope.decision_contract.package.candidates:
            owners.setdefault(candidate.source_value_ref, set()).add(
                scope_ref
            )
    return owners


def _raw_binding_risks(
    *,
    model_output: Any,
    case: Gate2FinancialSemanticV5QualificationCase,
    candidate_owners: dict[str, set[str]],
) -> dict[str, int]:
    payload = model_output
    if isinstance(payload, str):
        import json

        try:
            payload = json.loads(payload)
        except ValueError:
            payload = {}
    decision = payload.get("decision") if isinstance(payload, dict) else {}
    raw = decision.get("value_bindings") if isinstance(decision, dict) else None
    bindings: list[tuple[str, str]] = []
    if isinstance(raw, dict):
        bindings = [
            (str(role), str(ref))
            for role, ref in raw.items()
            if ref is not None
        ]
    elif isinstance(raw, list):
        bindings = [
            (str(item.get("role_id")), str(item.get("source_value_ref")))
            for item in raw
            if isinstance(item, dict)
        ]
    candidates = {
        item.source_value_ref: item
        for item in case.scope.decision_contract.package.candidates
    }
    refs = [ref for _, ref in bindings]
    invalid = sum(ref not in candidates for ref in refs)
    wrong_roles = sum(
        ref in candidates and role not in candidates[ref].allowed_roles
        for role, ref in bindings
    )
    cross_scope = sum(
        ref in candidate_owners
        and candidate_owners[ref]
        != {case.scope.source_package.source_scope_ref}
        for ref in refs
    )
    return {
        "invalid_refs_total": invalid,
        "wrong_roles_total": wrong_roles,
        "duplicate_bindings_total": len(refs) - len(set(refs)),
        "cross_scope_bindings_total": cross_scope,
    }


def _rate(numerator: int, denominator: int) -> int:
    return 0 if denominator == 0 else numerator * 10_000 // denominator


def _sum_costs(items: list[dict[str, Any]]) -> str:
    return format(
        sum(
            (Decimal(item["estimated_cost_usd"]) for item in items),
            Decimal("0"),
        ),
        "f",
    )


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV5QualificationError(code)
