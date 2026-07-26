from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

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
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
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
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from .gate2_successor_local_proof import _fixture_package, _model_output


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
            or local_proof.get("execution_accounting", {}).get("provider_calls_total")
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
                    _fail("financial_semantic_v5_qualification_preclose_invalid")
                model_output = copy.deepcopy(preclose.canonical_decision)
                case = Gate2FinancialSemanticV5QualificationCase(
                    case_id=case_id,
                    feature_families=tuple(benchmark_case["feature_families"]),
                    route=route,
                    expected_disposition=benchmark_case["expected_disposition"],
                    expected_input_type_id=benchmark_case["expected_input_type_id"],
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
                    _fail("financial_semantic_v5_qualification_preclose_invalid")
                ambiguity = Gate2FinancialSemanticV5AmbiguityGuardFactory().create(
                    projection=projection,
                    candidates=candidates,
                )
                packet = Gate2FinancialSemanticV5DecisionPacketFactory().create(
                    source_context=source_context,
                    projection=projection,
                    ambiguity=ambiguity,
                    candidates=candidates,
                    preclose=preclose,
                )
                model_contract = Gate2FinancialSemanticV5ModelContractFactory().create(
                    execution=execution,
                    projection=projection,
                    ambiguity=ambiguity,
                    packet=packet,
                    canonical_contract=scope.decision_contract,
                )
                case = Gate2FinancialSemanticV5QualificationCase(
                    case_id=case_id,
                    feature_families=tuple(benchmark_case["feature_families"]),
                    route=route,
                    expected_disposition=benchmark_case["expected_disposition"],
                    expected_input_type_id=benchmark_case["expected_input_type_id"],
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
                    decision_validation_ref=(f"validation:v5-preflight:{case.case_id}"),
                ),
            )
            evidence_hashes.append(evidence.private_evidence["private_evidence_hash"])
            case_preflights.append(
                {
                    "case_id": case.case_id,
                    "canonical_request_hash": sha256_json(request),
                    "packet_hash": packet.packet_hash,
                    "response_schema_hash": (model_contract.response_format_hash),
                    "estimated_input_tokens": (budget.estimated_input_tokens),
                    "maximum_output_tokens": (budget.maximum_output_tokens),
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
                "integrity_sha256": fixture.local_proof_receipt["integrity_sha256"],
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
                    item["estimated_input_tokens"] for item in case_preflights
                ),
                "estimated_input_tokens_max": max(
                    item["estimated_input_tokens"] for item in case_preflights
                ),
                "maximum_output_tokens_per_call": max(
                    item["maximum_output_tokens"] for item in case_preflights
                ),
                "estimated_cost_usd": _sum_costs(case_preflights),
                "within_budget": True,
            },
            "evidence_contract": {
                "private_schema_version": (V5_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION),
                "safe_schema_version": (V5_SAFE_DECISION_RECEIPT_SCHEMA_VERSION),
                "cases_validated_total": len(evidence_hashes),
                "evidence_hashes_sha256": sha256_json(sorted(evidence_hashes)),
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


def _qualification_contract_identity(
    fixture: Gate2FinancialSemanticV5QualificationFixture,
) -> Gate2EconomyQualificationContractIdentity:
    profile = gate2_provider_profile(PROVIDER_PROFILE_ID)
    contracts = [_semantic_authorities(item)[4] for item in fixture.semantic_cases]
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
        "ambiguity_policy_version": (V5_BINDING_AMBIGUITY_POLICY_VERSION),
        "ambiguity_policy_hashes_sha256": sha256_json(
            sorted(
                _semantic_authorities(item)[2].policy_hash
                for item in fixture.semantic_cases
            )
        ),
        "provider_schema_version": V5_MODEL_CONTRACT_SCHEMA_VERSION,
        "provider_schema_hashes_sha256": sha256_json(
            sorted(item["response_schema_hash"] for item in case_preflights)
        ),
        "benchmark_hash": fixture.benchmark_hash,
        "exact_model_id": EXACT_MODEL_ID,
        "provider_profile_id": PROVIDER_PROFILE_ID,
        "request_profile": FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
        "workload_class": WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
        "workload_policy_version": authorization["workload_policy_version"],
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
