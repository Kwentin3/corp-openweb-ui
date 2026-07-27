from __future__ import annotations

import copy
import json
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
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v5_preclose import (
    Gate2FinancialSemanticV5PrecloseFactory,
    Gate2TechnicalPrecloseEvidence,
)
from .gate2_financial_semantic_v5_projection import (
    V5_SEMANTIC_PROJECTION_SCHEMA_VERSION,
    V5_SEMANTIC_PROJECTION_VERSION,
)
from .gate2_financial_semantic_v6_benchmark import (
    V6_BENCHMARK_SHA256,
    validate_financial_semantic_v6_benchmark,
)
from .gate2_financial_semantic_v6_bundle import (
    EVIDENCE_BUNDLE_POLICY_VERSION,
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    Gate2FinancialEvidenceBundle,
    Gate2FinancialEvidenceBundleFactory,
)
from .gate2_financial_semantic_v6_candidate_compiler import (
    CANDIDATE_COMPILATION_POLICY_VERSION,
    CANDIDATE_COMPILATION_SCHEMA_VERSION,
    Gate2FinancialCandidateCompilation,
    Gate2FinancialCandidateCompilerFactory,
)
from .gate2_financial_semantic_v6_choice import (
    SEMANTIC_CHOICE_POLICY_VERSION,
    SEMANTIC_CHOICE_SCHEMA_VERSION,
    Gate2FinancialSemanticV6ChoiceContract,
    Gate2FinancialSemanticV6ChoiceContractFactory,
)
from .gate2_financial_semantic_v6_evidence import (
    V6_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION,
    V6_SAFE_DECISION_RECEIPT_SCHEMA_VERSION,
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    financial_semantic_v6_canonical_request,
)
from .gate2_financial_semantic_v6_execution_identity import (
    V6_EXACT_MODEL_ID,
    V6_EXECUTION_IDENTITY_POLICY_VERSION,
    V6_EXECUTION_IDENTITY_SCHEMA_VERSION,
    V6_PROVIDER_PROFILE_ID,
    V6_QUALIFICATION_REQUEST_PROFILE,
    Gate2FinancialSemanticV6CapturedExecution,
    Gate2FinancialSemanticV6ExecutionIdentityFactory,
    financial_semantic_v6_response_format,
)
from .gate2_financial_semantic_v6_expansion import (
    DECISION_EXPANSION_POLICY_VERSION,
    DECISION_EXPANSION_SCHEMA_VERSION,
)
from .gate2_financial_semantic_v6_local_proof import (
    Gate2FinancialSemanticV6LocalProofFactory,
)
from .gate2_financial_semantic_v6_packet import (
    SEMANTIC_PACKET_AMBIGUITY_RULE,
    SEMANTIC_PACKET_POLICY_VERSION,
    SEMANTIC_PACKET_SCHEMA_VERSION,
    Gate2FinancialSemanticV6Packet,
    Gate2FinancialSemanticV6PacketFactory,
)
from .gate2_financial_semantic_v6_prompt import (
    V6_SEMANTIC_PROMPT_HASH,
    V6_SEMANTIC_PROMPT_VERSION,
    financial_semantic_v6_prompt,
)
from .gate2_financial_semantic_v6_totality import (
    TOTAL_MATERIALIZATION_POLICY_VERSION,
    TOTAL_MATERIALIZATION_SCHEMA_VERSION,
)
from .gate2_financial_semantic_v6_typed_option import (
    TYPED_OPTION_POLICY_VERSION,
    TYPED_OPTION_SCHEMA_VERSION,
)
from .gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE,
)
from .gate2_provider_adapters import Gate2ProviderAdapterFactory
from .gate2_successor_local_proof import _fixture_package


V6_QUALIFICATION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_qualification_preflight_v1"
)
V6_QUALIFICATION_POLICY_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_one_attempt_v1"
)
SEMANTIC_CASES_TOTAL = 10
TECHNICAL_CASES_TOTAL = 2
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6QualificationFixtureFactory.create and "
    "Gate2FinancialSemanticV6QualificationPreflightFactory.create are the "
    "only Goal 11A V6 harness routes"
)
FORBIDDEN = (
    "Goal 11A must not call a provider, consume the one V6 attempt, use "
    "customer data, admit a production model, fallback, repair, retry or "
    "route technical cases to a provider"
)

_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")


class Gate2FinancialSemanticV6QualificationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6QualificationCase:
    case_id: str
    feature_families: tuple[str, ...]
    route: str
    expected_disposition: str
    expected_input_type_id: str | None
    expected_reason_code: str | None
    scope: Gate2DeterministicFinancialScope
    expected_model_choice: dict[str, Any]
    evidence_bundle: Gate2FinancialEvidenceBundle | None = None
    compilation: Gate2FinancialCandidateCompilation | None = None
    packet: Gate2FinancialSemanticV6Packet | None = None
    choice_contract: Gate2FinancialSemanticV6ChoiceContract | None = None


@dataclass(frozen=True)
class Gate2FinancialSemanticV6QualificationFixture:
    registry: Gate2FinancialEvidenceRegistrySnapshot
    local_proof_receipt: dict[str, Any]
    benchmark_hash: str
    cases: tuple[Gate2FinancialSemanticV6QualificationCase, ...]

    @property
    def semantic_cases(
        self,
    ) -> tuple[Gate2FinancialSemanticV6QualificationCase, ...]:
        return tuple(item for item in self.cases if item.route == "semantic_model")


def financial_semantic_v6_qualification_publication() -> dict[str, Any]:
    return {
        "schema_version": V6_QUALIFICATION_SCHEMA_VERSION,
        "policy_version": V6_QUALIFICATION_POLICY_VERSION,
        "scope": "qualification_only",
        "workload_identity": V6_QUALIFICATION_REQUEST_PROFILE,
        "exact_model_id": V6_EXACT_MODEL_ID,
        "provider_profile_id": V6_PROVIDER_PROFILE_ID,
        "attempts_total": 1,
        "semantic_provider_calls_total": SEMANTIC_CASES_TOTAL,
        "technical_provider_calls_total": 0,
        "fallback_total": 0,
        "repair_total": 0,
        "hidden_retry_total": 0,
        "production_admissions": [],
    }


V6_QUALIFICATION_PUBLICATION_HASH = sha256_json(
    financial_semantic_v6_qualification_publication()
)


class Gate2FinancialSemanticV6QualificationFixtureFactory:
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
    ) -> Gate2FinancialSemanticV6QualificationFixture:
        frozen_manifest = copy.deepcopy(manifest)
        frozen_base = copy.deepcopy(base_manifest)
        validate_financial_semantic_v6_benchmark(
            manifest=frozen_manifest,
            base_manifest=frozen_base,
        )
        local_proof = Gate2FinancialSemanticV6LocalProofFactory(
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
            _fail("financial_semantic_v6_qualification_local_proof_failed")

        base_cases = {item["case_id"]: item for item in frozen_base["cases"]}
        scope_factory = Gate2DeterministicFinancialScopeFromGate1V2Factory(
            registry=self.registry
        )
        cases: list[Gate2FinancialSemanticV6QualificationCase] = []
        for benchmark_case in frozen_manifest["cases"]:
            case_id = benchmark_case["case_id"]
            source_case = copy.deepcopy(base_cases[case_id])
            source_fixture = _fixture_package(source_case)
            batch = scope_factory.create(gate1_packages=(source_fixture.payload,))
            if len(batch.scopes) != 1:
                _fail("financial_semantic_v6_qualification_scope_invalid")
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
                    _fail("financial_semantic_v6_qualification_preclose_invalid")
                expected_choice = copy.deepcopy(preclose.canonical_decision)
                case = Gate2FinancialSemanticV6QualificationCase(
                    case_id=case_id,
                    feature_families=tuple(benchmark_case["feature_families"]),
                    route=route,
                    expected_disposition=benchmark_case["expected_disposition"],
                    expected_input_type_id=benchmark_case["expected_input_type_id"],
                    expected_reason_code=benchmark_case["expected_reason_code"],
                    scope=scope,
                    expected_model_choice=expected_choice,
                )
            else:
                evidence_bundle = Gate2FinancialEvidenceBundleFactory().create(
                    source_package=scope.source_package,
                    gate1_packages=(source_fixture.payload,),
                )
                compilation = Gate2FinancialCandidateCompilerFactory(
                    registry=self.registry
                ).create(
                    evidence_bundle=evidence_bundle,
                    source_package=scope.source_package,
                )
                if (
                    len(compilation.typed_options)
                    != benchmark_case["expected_typed_options"]
                ):
                    _fail("financial_semantic_v6_qualification_options_invalid")
                packet = Gate2FinancialSemanticV6PacketFactory(
                    registry=self.registry
                ).create(
                    evidence_bundle=evidence_bundle,
                    source_package=scope.source_package,
                    compilation=compilation,
                )
                choice_contract = Gate2FinancialSemanticV6ChoiceContractFactory(
                    registry=self.registry
                ).create(
                    packet=packet,
                    evidence_bundle=evidence_bundle,
                    source_package=scope.source_package,
                    compilation=compilation,
                )
                expected_choice = _expected_model_choice(
                    benchmark_case=benchmark_case,
                    compilation=compilation,
                )
                case = Gate2FinancialSemanticV6QualificationCase(
                    case_id=case_id,
                    feature_families=tuple(benchmark_case["feature_families"]),
                    route=route,
                    expected_disposition=benchmark_case["expected_disposition"],
                    expected_input_type_id=benchmark_case["expected_input_type_id"],
                    expected_reason_code=benchmark_case["expected_reason_code"],
                    scope=scope,
                    expected_model_choice=expected_choice,
                    evidence_bundle=evidence_bundle,
                    compilation=compilation,
                    packet=packet,
                    choice_contract=choice_contract,
                )
            cases.append(case)
        if (
            len(cases) != SEMANTIC_CASES_TOTAL + TECHNICAL_CASES_TOTAL
            or sum(item.route == "semantic_model" for item in cases)
            != SEMANTIC_CASES_TOTAL
        ):
            _fail("financial_semantic_v6_qualification_case_set_invalid")
        return Gate2FinancialSemanticV6QualificationFixture(
            registry=self.registry,
            local_proof_receipt=copy.deepcopy(local_proof),
            benchmark_hash=V6_BENCHMARK_SHA256,
            cases=tuple(cases),
        )


class Gate2FinancialSemanticV6QualificationPreflightFactory:
    def create(
        self,
        *,
        fixture: Gate2FinancialSemanticV6QualificationFixture,
        repository_revision: str,
        stage_action: dict[str, Any],
        published_model_ids: set[str],
        exact_model_id: str = V6_EXACT_MODEL_ID,
        provider_profile_id: str = V6_PROVIDER_PROFILE_ID,
    ) -> dict[str, Any]:
        if _REVISION_RE.fullmatch(repository_revision) is None:
            _fail("financial_semantic_v6_repository_revision_invalid")
        if exact_model_id not in published_model_ids:
            _fail("financial_semantic_v6_exact_model_not_published")
        if (
            not isinstance(stage_action, dict)
            or stage_action.get("production_admissions_empty") is not True
            or stage_action.get("v6_qualification_snapshot_hash")
            != V6_QUALIFICATION_PUBLICATION_HASH
            or not all((stage_action.get("checks") or {}).values())
        ):
            _fail("financial_semantic_v6_stage_action_parity_failed")

        contract_identity = _qualification_contract_identity(
            fixture,
            provider_profile_id=provider_profile_id,
        )
        authorization = (
            Gate2EconomyQualificationPolicyFactory()
            .create()
            .authorize(
                workload_class=WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
                exact_model_id=exact_model_id,
                provider_profile_id=provider_profile_id,
                receipt_identity=contract_identity,
            )
        )
        budget_session = Gate2EconomyBudgetSessionFactory().create(
            request_profile=FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE
        )
        case_preflights: list[dict[str, Any]] = []
        private_evidence_hashes: list[str] = []
        response_format_hashes: list[str] = []
        source_projection_hashes: list[str] = []
        compact_projection_hashes: list[str] = []
        for case in fixture.semantic_cases:
            evidence_bundle, compilation, packet, choice_contract = (
                _semantic_authorities(case)
            )
            prompt = financial_semantic_v6_prompt(
                packet=packet,
                choice_contract=choice_contract,
            )
            response_format = financial_semantic_v6_response_format(choice_contract)
            canonical_request = financial_semantic_v6_canonical_request(
                packet=packet,
                choice_contract=choice_contract,
                exact_model_id=exact_model_id,
                prompt=prompt,
            )
            budget = budget_session.prepare_call(
                form_data=canonical_request,
                model_id=exact_model_id,
                provider_profile_id=provider_profile_id,
                operation_identity=f"v6-qualification:{case.case_id}",
            )
            capture = _synthetic_capture(
                case_id=case.case_id,
                choice_contract=choice_contract,
                exact_model_id=exact_model_id,
                provider_profile_id=provider_profile_id,
            )
            execution_identity = (
                Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
                    capture=capture,
                    choice_contract=choice_contract,
                )
            )
            evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
                registry=fixture.registry,
                exact_model_id=exact_model_id,
                provider_profile_id=provider_profile_id,
            ).create(
                case_id=case.case_id,
                canonical_request=canonical_request,
                model_output=json.dumps(
                    case.expected_model_choice,
                    ensure_ascii=False,
                ),
                execution_capture=capture,
                execution_identity=execution_identity,
                choice_contract=choice_contract,
                packet=packet,
                evidence_bundle=evidence_bundle,
                source_package=case.scope.source_package,
                compilation=compilation,
            )
            private_evidence_hashes.append(
                evidence.private_evidence["private_evidence_hash"]
            )
            response_format_hashes.append(sha256_json(response_format))
            source_projection_hashes.append(packet.semantic_projection_hash)
            compact_projection_hash = sha256_json(
                packet.payload["available_type_cards"]
            )
            compact_projection_hashes.append(compact_projection_hash)
            case_preflights.append(
                {
                    "case_id": case.case_id,
                    "canonical_request_hash": sha256_json(canonical_request),
                    "budgeted_request_hash": sha256_json(budget.prepared_form_data),
                    "evidence_bundle_hash": evidence_bundle.integrity_hash,
                    "typed_options_hash": sha256_json(
                        [item.integrity_hash for item in compilation.typed_options]
                    ),
                    "packet_hash": packet.packet_hash,
                    "compact_pack_projection_hash": compact_projection_hash,
                    "choice_schema_hash": choice_contract.choice_schema_hash,
                    "response_format_hash": sha256_json(response_format),
                    "estimated_input_tokens": budget.estimated_input_tokens,
                    "maximum_output_tokens": budget.maximum_output_tokens,
                    "estimated_cost_usd": budget.estimated_cost_usd,
                    "evidence_contract_validated": True,
                    "provider_calls_total": 0,
                }
            )

        authorization_receipt = authorization.safe_receipt()
        exact_identity = _exact_identity(
            fixture=fixture,
            repository_revision=repository_revision,
            authorization=authorization_receipt,
            stage_action=stage_action,
            case_preflights=case_preflights,
            source_projection_hashes=source_projection_hashes,
            compact_projection_hashes=compact_projection_hashes,
            response_format_hashes=response_format_hashes,
            exact_model_id=exact_model_id,
            provider_profile_id=provider_profile_id,
        )
        receipt: dict[str, Any] = {
            "schema_version": V6_QUALIFICATION_SCHEMA_VERSION,
            "policy_version": V6_QUALIFICATION_POLICY_VERSION,
            "status": "passed",
            "preflight_only": True,
            "acceptance": {
                "v6_harness": "READY",
                "action_repository_live_parity": "EXACT",
                "local_preflight": "PASSED",
                "provider_calls": "ZERO",
            },
            "exact_identity": exact_identity,
            "stage": copy.deepcopy(stage_action),
            "local_proof": {
                "status": fixture.local_proof_receipt["status"],
                "integrity_sha256": fixture.local_proof_receipt["integrity_sha256"],
                "provider_calls_total": 0,
            },
            "authorization": authorization_receipt,
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
                "private_schema_version": (V6_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION),
                "safe_schema_version": V6_SAFE_DECISION_RECEIPT_SCHEMA_VERSION,
                "cases_validated_total": len(private_evidence_hashes),
                "evidence_hashes_sha256": sha256_json(sorted(private_evidence_hashes)),
                "exact_replay_ready": True,
            },
            "case_preflights": case_preflights,
            "execution_accounting": {
                "provider_attempts_total": 0,
                "provider_calls_total": 0,
                "technical_case_provider_calls_total": 0,
                "synthetic_execution_captures_total": len(case_preflights),
                "fallback_total": 0,
                "repair_total": 0,
                "hidden_retry_total": 0,
                "production_admissions_total": 0,
            },
        }
        if exact_model_id != V6_EXACT_MODEL_ID:
            receipt["candidate_experiment"] = {
                "architecture": "FROZEN",
                "variable_changed": "exact_candidate",
                "exact_model_id": exact_model_id,
                "provider_profile_id": provider_profile_id,
                "same_v6_workload": True,
                "base_v6_publication_hash": V6_QUALIFICATION_PUBLICATION_HASH,
            }
        receipt["integrity_sha256"] = sha256_json(receipt)
        return receipt


def _qualification_contract_identity(
    fixture: Gate2FinancialSemanticV6QualificationFixture,
    *,
    provider_profile_id: str = V6_PROVIDER_PROFILE_ID,
) -> Gate2EconomyQualificationContractIdentity:
    profile = gate2_provider_profile(provider_profile_id)
    contracts = [_semantic_authorities(item)[3] for item in fixture.semantic_cases]
    packets = [_semantic_authorities(item)[2] for item in fixture.semantic_cases]
    compact_projection_hashes = [
        sha256_json(item.payload["available_type_cards"]) for item in packets
    ]
    return Gate2EconomyQualificationContractIdentity(
        provider_route_revision=gate2_provider_profile_revision(profile),
        input_contract_version=(
            f"{EVIDENCE_BUNDLE_SCHEMA_VERSION}:"
            f"{TYPED_OPTION_SCHEMA_VERSION}:"
            f"{SEMANTIC_PACKET_SCHEMA_VERSION}:"
            f"{V5_SEMANTIC_PROJECTION_SCHEMA_VERSION}:"
            f"{V5_SEMANTIC_PROJECTION_VERSION}:"
            f"{sha256_json(sorted(item.semantic_projection_hash for item in packets))}:"
            f"{sha256_json(sorted(compact_projection_hashes))}:"
            f"{fixture.benchmark_hash}"
        ),
        output_contract_version=(
            f"{SEMANTIC_CHOICE_SCHEMA_VERSION}:"
            f"{sha256_json(sorted(item.choice_schema_hash for item in contracts))}"
        ),
        prompt_version=(
            f"{V6_SEMANTIC_PROMPT_VERSION}:{V6_SEMANTIC_PROMPT_HASH}"
        ),
        adapter_projection_revision=(
            f"{profile.adapter_id}:{profile.adapter_version}:"
            f"{V6_QUALIFICATION_REQUEST_PROFILE}"
        ),
        canonical_validator_revision=(
            f"{DECISION_EXPANSION_SCHEMA_VERSION}:"
            f"{DECISION_EXPANSION_POLICY_VERSION}:"
            f"{TOTAL_MATERIALIZATION_SCHEMA_VERSION}:"
            f"{TOTAL_MATERIALIZATION_POLICY_VERSION}:"
            f"{V6_EXECUTION_IDENTITY_POLICY_VERSION}:"
            f"{V6_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION}"
        ),
    )


def _exact_identity(
    *,
    fixture: Gate2FinancialSemanticV6QualificationFixture,
    repository_revision: str,
    authorization: dict[str, Any],
    stage_action: dict[str, Any],
    case_preflights: list[dict[str, Any]],
    source_projection_hashes: list[str],
    compact_projection_hashes: list[str],
    response_format_hashes: list[str],
    exact_model_id: str = V6_EXACT_MODEL_ID,
    provider_profile_id: str = V6_PROVIDER_PROFILE_ID,
) -> dict[str, Any]:
    material = {
        "repository_revision": repository_revision,
        "evidence_bundle_schema": EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "evidence_bundle_policy": EVIDENCE_BUNDLE_POLICY_VERSION,
        "typed_option_schema": TYPED_OPTION_SCHEMA_VERSION,
        "typed_option_policy": TYPED_OPTION_POLICY_VERSION,
        "candidate_compilation_schema": CANDIDATE_COMPILATION_SCHEMA_VERSION,
        "candidate_compilation_policy": CANDIDATE_COMPILATION_POLICY_VERSION,
        "semantic_packet_schema": SEMANTIC_PACKET_SCHEMA_VERSION,
        "semantic_packet_policy": SEMANTIC_PACKET_POLICY_VERSION,
        "semantic_choice_schema": SEMANTIC_CHOICE_SCHEMA_VERSION,
        "semantic_choice_policy": SEMANTIC_CHOICE_POLICY_VERSION,
        "compact_pack_projection": {
            "schema_version": V5_SEMANTIC_PROJECTION_SCHEMA_VERSION,
            "projection_version": V5_SEMANTIC_PROJECTION_VERSION,
            "source_authority_hashes_sha256": sha256_json(
                sorted(source_projection_hashes)
            ),
            "compact_projection_hashes_sha256": sha256_json(
                sorted(compact_projection_hashes)
            ),
        },
        "prompt": {
            "version": V6_SEMANTIC_PROMPT_VERSION,
            "hash": V6_SEMANTIC_PROMPT_HASH,
        },
        "ambiguity_policy": {
            "rule": SEMANTIC_PACKET_AMBIGUITY_RULE,
            "hash": sha256_json(SEMANTIC_PACKET_AMBIGUITY_RULE),
        },
        "provider_schema": {
            "schema_version": SEMANTIC_CHOICE_SCHEMA_VERSION,
            "schema_hashes_sha256": sha256_json(
                sorted(item["choice_schema_hash"] for item in case_preflights)
            ),
            "response_format_hashes_sha256": sha256_json(
                sorted(response_format_hashes)
            ),
        },
        "benchmark": {
            "hash": fixture.benchmark_hash,
            "cases_total": len(fixture.cases),
        },
        "model_provider": {
            "exact_model_id": exact_model_id,
            "provider_profile_id": provider_profile_id,
            "provider_route_revision": authorization["receipt_identity"][
                "provider_route_revision"
            ],
            "request_profile": V6_QUALIFICATION_REQUEST_PROFILE,
            "workload_class": WORKLOAD_GATE2_FINANCIAL_EVIDENCE,
        },
        "execution_identity": {
            "schema_version": V6_EXECUTION_IDENTITY_SCHEMA_VERSION,
            "policy_version": V6_EXECUTION_IDENTITY_POLICY_VERSION,
        },
        "evidence_contract": {
            "private_schema_version": (V6_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION),
            "safe_schema_version": V6_SAFE_DECISION_RECEIPT_SCHEMA_VERSION,
        },
        "qualification_authorization_hash": authorization[
            "authorization_identity_sha256"
        ],
        "action": {
            "content_hash": stage_action["content_sha256"],
            "publication_hash": V6_QUALIFICATION_PUBLICATION_HASH,
        },
        "attempt_policy": {
            "full_scope_attempts_total": 1,
            "semantic_provider_calls_total": SEMANTIC_CASES_TOTAL,
            "technical_provider_calls_total": 0,
            "fallback_total": 0,
            "repair_total": 0,
            "hidden_retry_total": 0,
        },
    }
    if exact_model_id != V6_EXACT_MODEL_ID:
        material["candidate_experiment"] = {
            "architecture": "FROZEN",
            "variable_changed": "exact_candidate",
            "same_v6_workload": True,
            "base_v6_publication_hash": V6_QUALIFICATION_PUBLICATION_HASH,
        }
    return {**material, "identity_hash": sha256_json(material)}


def _synthetic_capture(
    *,
    case_id: str,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    exact_model_id: str = V6_EXACT_MODEL_ID,
    provider_profile_id: str = V6_PROVIDER_PROFILE_ID,
) -> Gate2FinancialSemanticV6CapturedExecution:
    profile = gate2_provider_profile(provider_profile_id)
    response_format = financial_semantic_v6_response_format(choice_contract)
    prepared = Gate2ProviderAdapterFactory(
        profile=profile,
        capability_probe=True,
    ).create().prepare_form_data(
        form_data={
            "model": exact_model_id,
            "messages": [{"role": "user", "content": "schema-projection"}],
            "response_format": response_format,
        },
        response_format=response_format,
    )
    metadata = Gate2ProviderExecutionMetadata(
        provider_id=profile.provider_id,
        provider_profile_id=profile.profile_id,
        provider_profile_revision=gate2_provider_profile_revision(profile),
        adapter_id=profile.adapter_id,
        adapter_version=profile.adapter_version,
        requested_model_id=exact_model_id,
        resolved_model_id=exact_model_id,
        provider_response_id=f"synthetic-preflight:{case_id}",
        structured_output_mode=profile.structured_output_mode,
        response_format_type=profile.response_format_type,
        response_format_schema_mode=profile.response_format_schema_mode,
        transport_type=profile.transport_type,
        canonical_request_schema_hash=prepared.canonical_schema_hash,
        adapted_request_schema_hash=prepared.adapted_schema_hash,
        schema_transform_count=prepared.schema_transform_count,
        duration_ms=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        cached_input_tokens=0,
        reasoning_tokens=0,
        finish_reason="preflight",
    )
    return Gate2FinancialSemanticV6CapturedExecution(
        request_profile=V6_QUALIFICATION_REQUEST_PROFILE,
        response_format_hash=sha256_json(response_format),
        execution_metadata=metadata,
        actual_cost_usd="0",
        exact_model_id=exact_model_id,
        provider_profile_id=provider_profile_id,
    )


def _semantic_authorities(
    case: Gate2FinancialSemanticV6QualificationCase,
) -> tuple[
    Gate2FinancialEvidenceBundle,
    Gate2FinancialCandidateCompilation,
    Gate2FinancialSemanticV6Packet,
    Gate2FinancialSemanticV6ChoiceContract,
]:
    values = (
        case.evidence_bundle,
        case.compilation,
        case.packet,
        case.choice_contract,
    )
    if any(value is None for value in values):
        _fail("financial_semantic_v6_semantic_case_authority_missing")
    return values  # type: ignore[return-value]


def _expected_model_choice(
    *,
    benchmark_case: dict[str, Any],
    compilation: Gate2FinancialCandidateCompilation,
) -> dict[str, Any]:
    if benchmark_case["expected_disposition"] == "typed_input":
        options = tuple(
            item
            for item in compilation.typed_options
            if item.input_type_id == benchmark_case["expected_input_type_id"]
        )
        if len(options) != 1:
            _fail("financial_semantic_v6_expected_option_not_unique")
        return {
            "disposition": "typed_input",
            "typed_option_id": options[0].typed_option_id,
        }
    return {
        "disposition": "unclassified_financial_input",
        "reason_code": benchmark_case["expected_reason_code"],
    }


def _sum_costs(items: list[dict[str, Any]]) -> str:
    return format(
        sum(
            (Decimal(item["estimated_cost_usd"]) for item in items),
            Decimal("0"),
        ),
        "f",
    )


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6QualificationError(code)
