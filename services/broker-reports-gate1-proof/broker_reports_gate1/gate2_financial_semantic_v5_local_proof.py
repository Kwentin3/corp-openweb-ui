from __future__ import annotations

import copy
import json
from collections import Counter
from typing import Any

from .gate2_deterministic_financial_scopes import (
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
    validate_deterministic_financial_scope_v2,
)
from .gate2_financial_context import (
    Gate2FinancialContextProjectionFactory,
    validate_financial_context,
)
from .gate2_financial_domain_catalog import (
    Gate2FinancialDomainCatalogFactory,
)
from .gate2_financial_domain_contracts import (
    FINANCIAL_DOMAIN_QUERY_POLICY_VERSION,
    FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION,
    FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION,
    FinancialDomainAccessContext,
    canonical_json,
)
from .gate2_financial_domain_local_proof import (
    _query_evidence,
)
from .gate2_financial_domain_persistence import (
    FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION,
    Gate2FinancialDomainPersistenceFactory,
)
from .gate2_financial_domain_query import (
    Gate2FinancialDomainQueryFactory,
)
from .gate2_financial_evidence_decision import DISPOSITIONS
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
    validate_financial_evidence_inputs,
)
from .gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_evidence_source_context import (
    Gate2FinancialEvidenceSourceContextFactory,
    validate_financial_evidence_source_context,
)
from .gate2_financial_semantic_model_assets import (
    load_gate2_financial_semantic_model_assets,
)
from .gate2_financial_semantic_v5_benchmark import (
    validate_financial_semantic_v5_benchmark,
)
from .gate2_financial_semantic_v5_ambiguity import (
    Gate2FinancialSemanticV5AmbiguityGuardFactory,
)
from .gate2_financial_semantic_v5_contract import (
    V5_MODEL_CONTRACT_POLICY_VERSION,
    V5_MODEL_CONTRACT_SCHEMA_VERSION,
    Gate2FinancialSemanticV5ModelContractFactory,
)
from .gate2_financial_semantic_v5_execution import (
    V5_PROMPT_VERSION,
    Gate2FinancialSemanticV5ExecutionContractFactory,
)
from .gate2_financial_semantic_v5_local_proof_checks import (
    run_financial_semantic_v5_negative_checks,
)
from .gate2_financial_semantic_v5_packet import (
    V5_DECISION_PACKET_SCHEMA_VERSION,
    Gate2FinancialSemanticV5DecisionPacketFactory,
    structural_binding_candidates_from_source_context,
)
from .gate2_financial_semantic_v5_preclose import (
    V5_TECHNICAL_PRECLOSE_POLICY_VERSION,
    Gate2FinancialSemanticV5PrecloseFactory,
    Gate2TechnicalPrecloseEvidence,
)
from .gate2_financial_semantic_v5_projection import (
    V5_SEMANTIC_PROJECTION_SCHEMA_VERSION,
    V5_SEMANTIC_PROJECTION_VERSION,
    Gate2FinancialSemanticV5ProjectionFactory,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from .gate2_successor_local_proof import (
    _EvaluatedCase,
    _fixture_package,
    _model_output,
    _validate_coverage,
    _validate_fixture_authority,
)
from .gate2_successor_product_comparator import (
    Gate2SuccessorProductComparatorFactory,
    Gate2SuccessorProductExpectation,
    Gate2SuccessorScopeObservation,
)


V5_LOCAL_PROOF_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v5_local_proof_receipt_v1"
)
V5_LOCAL_PROOF_POLICY_VERSION = (
    "broker_reports_gate2_financial_semantic_v5_local_proof_v1"
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV5LocalProofFactory.create is the only frozen "
    "V5 risk benchmark and local proof entrypoint"
)
FORBIDDEN = (
    "The V5 local proof must not call a provider, activate runtime routes, "
    "write persistence, inspect customer data, alter source evidence or "
    "replace canonical validators, materializers, domain or query factories"
)

_ACCESS_CONTEXT = FinancialDomainAccessContext(
    user_ref="user:synthetic-v5-local-proof",
    case_ref="case:synthetic-v5-local-proof",
    workspace_ref="workspace:synthetic-v5-local-proof",
)
_CREATED_AT = "2026-07-26T00:00:00+00:00"
class Gate2FinancialSemanticV5LocalProofError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate2FinancialSemanticV5LocalProofFactory:
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
    ) -> dict[str, Any]:
        frozen_manifest = copy.deepcopy(manifest)
        frozen_base = copy.deepcopy(base_manifest)
        validate_financial_semantic_v5_benchmark(
            manifest=frozen_manifest,
            base_manifest=frozen_base,
        )
        base_cases = {
            item["case_id"]: item for item in frozen_base["cases"]
        }
        projection = Gate2FinancialSemanticV5ProjectionFactory().create()
        execution = (
            Gate2FinancialSemanticV5ExecutionContractFactory().create()
        )
        assets = load_gate2_financial_semantic_model_assets()
        scope_factory = Gate2DeterministicFinancialScopeFromGate1V2Factory(
            registry=self.registry
        )
        context_factory = Gate2FinancialEvidenceSourceContextFactory()

        evaluated: list[_EvaluatedCase] = []
        artifacts: list[dict[str, Any]] = []
        source_packages = []
        disposition_counts: Counter[str] = Counter()
        provider_disposition_counts: Counter[str] = Counter()
        preclose_status_counts: Counter[str] = Counter()
        packet_hashes: list[str] = []
        response_schema_hashes: list[str] = []
        context_bytes: list[int] = []
        estimated_tokens: list[int] = []
        case_receipts: list[dict[str, Any]] = []
        model_bundles: dict[str, dict[str, Any]] = {}
        typed_expected_total = 0
        typed_observed_total = 0
        typed_true_positive_total = 0
        safe_under_typed_total = 0
        unsafe_typed_total = 0
        unclassified_provider_total = 0

        for benchmark_case in frozen_manifest["cases"]:
            case_id = benchmark_case["case_id"]
            source_case = copy.deepcopy(base_cases[case_id])
            fixture = _fixture_package(source_case)
            batch = scope_factory.create(gate1_packages=(fixture.payload,))
            repeated = scope_factory.create(
                gate1_packages=(copy.deepcopy(fixture.payload),)
            )
            if batch != repeated or len(batch.scopes) != 1:
                _fail("financial_semantic_v5_scope_not_deterministic")
            _validate_coverage(batch.coverage)
            scope = batch.scopes[0]
            validate_deterministic_financial_scope_v2(scope)
            _validate_fixture_authority(scope=scope, fixture=fixture)

            route = benchmark_case["expected_route"]
            packet_hash = None
            response_schema_hash = None
            available_type_cards = None
            request_context_bytes = 0
            request_estimated_tokens = 0
            if route == "technical_preclose":
                preclose = Gate2FinancialSemanticV5PrecloseFactory().create(
                    evidence=Gate2TechnicalPrecloseEvidence(
                        **benchmark_case["technical_evidence"]
                    )
                )
                if (
                    preclose.status != "terminal"
                    or preclose.provider_call_required is not False
                    or preclose.canonical_decision is None
                ):
                    _fail("financial_semantic_v5_technical_preclose_failed")
                model_output = copy.deepcopy(
                    preclose.canonical_decision
                )
                validated = (
                    Gate2FinancialEvidenceValidatedDecisionFactory(
                        contract=scope.decision_contract
                    ).create(model_output)
                )
                preclose_status_counts[
                    validated.decision.disposition
                ] += 1
            else:
                source_context = context_factory.create(
                    source_scope_ref=(
                        scope.source_package.source_scope_ref
                    ),
                    source_values=scope.source_package.source_values,
                    candidates=(
                        scope.decision_contract.package.candidates
                    ),
                    gate1_packages=(fixture.payload,),
                )
                validate_financial_evidence_source_context(
                    context=source_context,
                    source_scope_ref=(
                        scope.source_package.source_scope_ref
                    ),
                    source_values=scope.source_package.source_values,
                    candidates=(
                        scope.decision_contract.package.candidates
                    ),
                )
                candidates = (
                    structural_binding_candidates_from_source_context(
                        source_context=source_context
                    )
                )
                preclose = Gate2FinancialSemanticV5PrecloseFactory().create(
                    evidence=Gate2TechnicalPrecloseEvidence(
                        source_support="supported",
                        authoritative_layout_only=False,
                        source_value_candidates_total=len(candidates),
                        scope_valid=True,
                    )
                )
                if (
                    preclose.status != "model_required"
                    or preclose.provider_call_required is not True
                    or preclose.canonical_decision is not None
                ):
                    _fail("financial_semantic_v5_model_preclose_failed")
                preclose_status_counts["model_required"] += 1
                ambiguity = (
                    Gate2FinancialSemanticV5AmbiguityGuardFactory().create(
                        projection=projection,
                        candidates=candidates,
                    )
                )
                packet = (
                    Gate2FinancialSemanticV5DecisionPacketFactory().create(
                        source_context=source_context,
                        projection=projection,
                        ambiguity=ambiguity,
                        candidates=candidates,
                        preclose=preclose,
                    )
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
                available_type_cards = len(
                    model_contract.typed_type_ids
                )
                if available_type_cards != benchmark_case[
                    "expected_available_type_cards"
                ]:
                    _fail(
                        "financial_semantic_v5_available_types_mismatch"
                    )
                model_output = _model_output(
                    case=source_case,
                    scope=scope,
                    selected_value_refs=fixture.selected_value_refs,
                )
                validated = model_contract.validate_and_adapt(
                    model_output=model_output,
                    execution=execution,
                    projection=projection,
                    ambiguity=ambiguity,
                    packet=packet,
                    canonical_contract=scope.decision_contract,
                )
                request = Gate2OpenWebUIRequestBuilder(
                    request_profile=FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE
                ).build(
                    prompt=execution.prompt,
                    package=packet.payload,
                    model_id="synthetic-v5-local-no-call",
                    response_format=model_contract.response_format,
                )
                request_context_bytes = len(
                    request["messages"][0]["content"].encode("utf-8")
                ) + len(
                    canonical_json(model_contract.response_format).encode(
                        "utf-8"
                    )
                )
                request_estimated_tokens = (
                    request_context_bytes + 3
                ) // 4
                context_bytes.append(request_context_bytes)
                estimated_tokens.append(request_estimated_tokens)
                packet_hash = packet.packet_hash
                response_schema_hash = (
                    model_contract.response_format_hash
                )
                packet_hashes.append(packet_hash)
                response_schema_hashes.append(response_schema_hash)
                provider_disposition_counts[
                    validated.decision.disposition
                ] += 1
                if (
                    validated.decision.disposition
                    == "unclassified_financial_input"
                ):
                    unclassified_provider_total += 1
                model_bundles[case_id] = {
                    "scope": scope,
                    "projection": projection,
                    "ambiguity": ambiguity,
                    "packet": packet,
                    "model_contract": model_contract,
                    "model_output": model_output,
                }

            actual_disposition = validated.decision.disposition
            actual_type_id = getattr(
                validated.decision,
                "input_type_id",
                None,
            )
            if (
                actual_disposition
                != benchmark_case["expected_disposition"]
                or actual_type_id
                != benchmark_case["expected_input_type_id"]
            ):
                _fail("financial_semantic_v5_fixture_outcome_mismatch")
            expected_typed = (
                benchmark_case["expected_disposition"] == "typed_input"
            )
            observed_typed = actual_disposition == "typed_input"
            typed_expected_total += int(expected_typed)
            typed_observed_total += int(observed_typed)
            typed_true_positive_total += int(
                expected_typed and observed_typed
            )
            safe_under_typed_total += int(
                expected_typed
                and actual_disposition
                == "unclassified_financial_input"
            )
            unsafe_typed_total += int(
                observed_typed and not expected_typed
            )

            execution_ref = f"execution:v5-local:{case_id}"
            validation_ref = f"validation:v5-local:{case_id}"
            artifact = Gate2FinancialEvidenceMaterializerFactory(
                registry=self.registry,
                source_package=scope.source_package,
                execution_metadata=FinancialEvidenceExecutionMetadata(
                    execution_ref=execution_ref,
                    decision_validation_ref=validation_ref,
                ),
            ).create().materialize(validated_decision=validated)
            validate_financial_evidence_inputs(
                payload=artifact,
                registry=self.registry,
                source_package=scope.source_package,
            )
            evaluated.append(
                _EvaluatedCase(
                    scope=scope,
                    model_output=model_output,
                    materialized_artifact=artifact,
                    execution_ref=execution_ref,
                    decision_validation_ref=validation_ref,
                    expected_disposition=benchmark_case[
                        "expected_disposition"
                    ],
                    expected_input_type_id=benchmark_case[
                        "expected_input_type_id"
                    ],
                )
            )
            artifacts.append(artifact)
            source_packages.append(scope.source_package)
            disposition_counts[actual_disposition] += 1
            case_receipts.append(
                {
                    "case_id": case_id,
                    "route": route,
                    "disposition": actual_disposition,
                    "input_type_id": actual_type_id,
                    "available_type_cards": available_type_cards,
                    "packet_hash": packet_hash,
                    "response_schema_hash": response_schema_hash,
                    "context_bytes": request_context_bytes,
                    "estimated_tokens": request_estimated_tokens,
                    "provider_calls_total": 0,
                }
            )

        product_receipt = self._product_receipt(
            evaluated=evaluated,
            artifacts=artifacts,
            source_packages=source_packages,
        )
        snapshot = Gate2FinancialDomainCatalogFactory(
            registry=self.registry,
            snapshot_authority_key=self._snapshot_authority_key,
        ).create(
            materialized_artifacts=artifacts,
            source_packages=source_packages,
            access_context=_ACCESS_CONTEXT,
            created_at=_CREATED_AT,
            expires_at=None,
        )
        persistence = Gate2FinancialDomainPersistenceFactory(
            snapshot_authority_key=self._snapshot_authority_key
        )
        serialized = persistence.serialize(snapshot=snapshot)
        restored = persistence.restore(serialized=serialized)
        if restored != snapshot:
            _fail("financial_semantic_v5_persistence_roundtrip_invalid")
        query = Gate2FinancialDomainQueryFactory(
            snapshot=restored,
            registry=self.registry,
            access_context=_ACCESS_CONTEXT,
            snapshot_authority_key=self._snapshot_authority_key,
            continuation_key=self._continuation_key,
        ).create()
        query_evidence = _query_evidence(
            query=query,
            snapshot=restored,
        )
        negative_checks = run_financial_semantic_v5_negative_checks(
            registry=self.registry,
            snapshot_authority_key=self._snapshot_authority_key,
            access_context=_ACCESS_CONTEXT,
            created_at=_CREATED_AT,
            model_bundles=model_bundles,
            artifacts=artifacts,
            source_packages=source_packages,
            snapshot=restored,
            serialized=serialized,
        )
        metrics = product_receipt["metrics"]
        comparator_checks = product_receipt["checks"]
        full_pack_bytes = len(
            canonical_json(assets["semantic_pack"]).encode("utf-8")
        )
        projection_basis_points = (
            projection.canonical_bytes * 10000 // full_pack_bytes
        )
        hard_gates = {
            "unsafe_typed_total": unsafe_typed_total,
            "invented_values_total": metrics["invented_values_total"],
            "invalid_refs_total": (
                0
                if comparator_checks["exact_package_ref_membership"]
                else 1
            ),
            "wrong_roles_total": (
                0 if comparator_checks["role_compatibility"] else 1
            ),
            "duplicate_bindings_total": metrics[
                "duplicate_bindings_total"
            ],
            "cross_scope_bindings_total": metrics[
                "cross_scope_bindings_total"
            ],
            "literal_or_provenance_loss_total": (
                metrics["literal_loss_total"]
                + query_evidence["provenance_gaps_total"]
            ),
            "ownership_gaps_total": metrics[
                "terminal_ownership_gap_total"
            ],
            "query_gaps_total": query_evidence["query_gaps_total"],
        }
        checks = {
            "benchmark_identity_exact": True,
            "all_preclose_branches": preclose_status_counts
            == Counter(
                {
                    "model_required": 10,
                    "no_financial_input": 1,
                    "unsupported": 1,
                }
            ),
            "both_provider_dispositions": set(
                provider_disposition_counts
            )
            == {"typed_input", "unclassified_financial_input"},
            "canonical_four_dispositions": set(disposition_counts)
            == set(DISPOSITIONS),
            "adjacent_equal_unclassified_only": (
                model_bundles[
                    "syn_successor_v2_adjacent_equal"
                ]["model_contract"].typed_type_ids
                == ()
                and next(
                    item
                    for item in case_receipts
                    if item["case_id"]
                    == "syn_successor_v2_adjacent_equal"
                )["disposition"]
                == "unclassified_financial_input"
            ),
            "canonical_product_invariants": (
                product_receipt["status"] == "passed"
            ),
            "hard_gates_zero": all(
                value == 0 for value in hard_gates.values()
            ),
            "projection_under_4096": projection.canonical_bytes < 4096,
            "projection_under_half_full_pack": (
                projection.canonical_bytes * 2 < full_pack_bytes
            ),
            "persistence_roundtrip": restored == snapshot,
            "domain_catalog_validated": True,
            "query_complete": query_evidence["query_gaps_total"] == 0,
            "negative_fail_closed": all(negative_checks.values()),
            "provider_calls_zero": True,
        }
        passed = all(checks.values())
        receipt: dict[str, Any] = {
            "schema_version": V5_LOCAL_PROOF_RECEIPT_SCHEMA_VERSION,
            "policy_version": V5_LOCAL_PROOF_POLICY_VERSION,
            "status": "passed" if passed else "failed",
            "acceptance": {
                "local_v5_proof": "PASSED" if passed else "FAILED",
                "adjacent_equal": (
                    "UNCLASSIFIED_ONLY"
                    if checks["adjacent_equal_unclassified_only"]
                    else "FAILED"
                ),
                "technical_preclose": (
                    "PASSED"
                    if checks["all_preclose_branches"]
                    else "FAILED"
                ),
                "literal_loss": (
                    "ZERO"
                    if hard_gates[
                        "literal_or_provenance_loss_total"
                    ]
                    == 0
                    else "NONZERO"
                ),
                "query_gaps": (
                    "ZERO"
                    if hard_gates["query_gaps_total"] == 0
                    else "NONZERO"
                ),
                "provider_calls": "ZERO",
            },
            "benchmark": {
                "schema_version": frozen_manifest["schema_version"],
                "benchmark_id": frozen_manifest["benchmark_id"],
                "integrity_sha256": sha256_json(frozen_manifest),
                "base_manifest_sha256": sha256_json(frozen_base),
                "cases_total": len(frozen_manifest["cases"]),
                "contains_customer_data": False,
                "frozen": True,
            },
            "exact_contracts": {
                "prompt_version": V5_PROMPT_VERSION,
                "prompt_hash": execution.prompt.hash,
                "projection_schema_version": (
                    V5_SEMANTIC_PROJECTION_SCHEMA_VERSION
                ),
                "projection_version": V5_SEMANTIC_PROJECTION_VERSION,
                "projection_hash": projection.projection_hash,
                "packet_schema_version": (
                    V5_DECISION_PACKET_SCHEMA_VERSION
                ),
                "preclose_policy_version": (
                    V5_TECHNICAL_PRECLOSE_POLICY_VERSION
                ),
                "model_contract_schema_version": (
                    V5_MODEL_CONTRACT_SCHEMA_VERSION
                ),
                "model_contract_policy_version": (
                    V5_MODEL_CONTRACT_POLICY_VERSION
                ),
                "domain_snapshot_schema_version": (
                    FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION
                ),
                "persistence_schema_version": (
                    FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION
                ),
                "query_schema_version": (
                    FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION
                ),
                "query_policy_version": (
                    FINANCIAL_DOMAIN_QUERY_POLICY_VERSION
                ),
            },
            "checks": checks,
            "hard_gates": hard_gates,
            "quality": {
                "typed_precision_basis_points": _rate(
                    typed_true_positive_total,
                    typed_observed_total,
                ),
                "typed_recall_basis_points": _rate(
                    typed_true_positive_total,
                    typed_expected_total,
                ),
                "safe_under_typed_total": safe_under_typed_total,
                "safe_under_typed_rate_basis_points": _rate(
                    safe_under_typed_total,
                    typed_expected_total,
                ),
                "unclassified_provider_cases_total": (
                    unclassified_provider_total
                ),
                "unclassified_provider_rate_basis_points": _rate(
                    unclassified_provider_total,
                    sum(provider_disposition_counts.values()),
                ),
                "model_context_bytes_total": sum(context_bytes),
                "model_context_bytes_max": max(context_bytes),
                "estimated_tokens_total": sum(estimated_tokens),
                "estimated_tokens_max": max(estimated_tokens),
                "full_pack_canonical_bytes": full_pack_bytes,
                "projection_canonical_bytes": projection.canonical_bytes,
                "projection_of_full_pack_basis_points": (
                    projection_basis_points
                ),
            },
            "routes": {
                "technical_cases_total": 2,
                "semantic_model_cases_total": 10,
                "preclose_status_counts": {
                    key: preclose_status_counts[key]
                    for key in (
                        "model_required",
                        "no_financial_input",
                        "unsupported",
                    )
                },
                "provider_disposition_counts": {
                    key: provider_disposition_counts[key]
                    for key in (
                        "typed_input",
                        "unclassified_financial_input",
                    )
                },
                "canonical_disposition_counts": {
                    key: disposition_counts[key] for key in DISPOSITIONS
                },
            },
            "domain": {
                "snapshot_integrity_sha256": (
                    restored.integrity_sha256
                ),
                "serialized_snapshot_sha256": sha256_json(
                    json.loads(serialized)
                ),
                **query_evidence,
            },
            "case_receipts": case_receipts,
            "exact_hashes": {
                "packet_hashes": sorted(packet_hashes),
                "response_schema_hashes": sorted(
                    response_schema_hashes
                ),
                "product_receipt_hash": product_receipt[
                    "integrity_hash"
                ],
            },
            "negative_checks": negative_checks,
            "execution_accounting": {
                "provider_calls_total": 0,
                "source_model_calls_total": 0,
                "domain_model_calls_total": 0,
                "financial_model_calls_total": 0,
                "fallback_total": 0,
                "repair_attempts_total": 0,
                "hidden_retry_total": 0,
                "persistence_writes_total": 0,
                "production_route_activations_total": 0,
            },
        }
        receipt["integrity_sha256"] = sha256_json(receipt)
        if not passed:
            _fail("financial_semantic_v5_local_proof_failed")
        return receipt

    def _product_receipt(
        self,
        *,
        evaluated: list[_EvaluatedCase],
        artifacts: list[dict[str, Any]],
        source_packages: list[Any],
    ) -> dict[str, Any]:
        context = Gate2FinancialContextProjectionFactory(
            registry=self.registry
        ).create(
            materialized_artifacts=artifacts,
            source_packages=source_packages,
        )
        validate_financial_context(payload=context, registry=self.registry)
        receipt = Gate2SuccessorProductComparatorFactory(
            registry=self.registry
        ).create().compare(
            authorized_scopes=(item.scope for item in evaluated),
            observations=(
                Gate2SuccessorScopeObservation(
                    source_scope_ref=(
                        item.scope.source_package.source_scope_ref
                    ),
                    model_output=item.model_output,
                    materialized_artifact=item.materialized_artifact,
                    execution_ref=item.execution_ref,
                    decision_validation_ref=(
                        item.decision_validation_ref
                    ),
                    expectation=Gate2SuccessorProductExpectation(
                        expected_disposition=item.expected_disposition,
                        expected_input_type_id=(
                            item.expected_input_type_id
                        ),
                    ),
                )
                for item in evaluated
            ),
            final_context=context,
        )
        if receipt["status"] != "passed":
            _fail("financial_semantic_v5_product_invariants_failed")
        return receipt

def _rate(numerator: int, denominator: int) -> int:
    if denominator == 0:
        return 0
    return numerator * 10000 // denominator


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV5LocalProofError(code)
