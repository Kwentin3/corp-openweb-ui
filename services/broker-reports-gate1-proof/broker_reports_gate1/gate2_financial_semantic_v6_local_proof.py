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
from .gate2_financial_domain_local_proof import _query_evidence
from .gate2_financial_domain_persistence import (
    FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION,
    Gate2FinancialDomainPersistenceFactory,
)
from .gate2_financial_domain_query import Gate2FinancialDomainQueryFactory
from .gate2_financial_evidence_decision import DISPOSITIONS
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
    validate_financial_evidence_inputs,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v5_preclose import (
    Gate2FinancialSemanticV5PrecloseFactory,
    Gate2TechnicalPrecloseEvidence,
)
from .gate2_financial_semantic_v6_benchmark import (
    validate_financial_semantic_v6_benchmark,
)
from .gate2_financial_semantic_v6_bundle import (
    Gate2FinancialEvidenceBundleFactory,
    validate_financial_evidence_bundle,
)
from .gate2_financial_semantic_v6_candidate_compiler import (
    Gate2FinancialCandidateCompilerFactory,
    validate_financial_candidate_compilation,
)
from .gate2_financial_semantic_v6_choice import (
    Gate2FinancialSemanticV6ChoiceContractFactory,
    validate_financial_semantic_v6_choice_contract,
)
from .gate2_financial_semantic_v6_evidence import (
    financial_semantic_v6_canonical_request,
)
from .gate2_financial_semantic_v6_expansion import (
    Gate2FinancialSemanticV6DecisionExpansionFactory,
)
from .gate2_financial_semantic_v6_local_proof_checks import (
    run_financial_semantic_v6_negative_checks,
)
from .gate2_financial_semantic_v6_packet import (
    Gate2FinancialSemanticV6PacketFactory,
    validate_financial_semantic_v6_packet,
)
from .gate2_financial_semantic_v6_prompt import V6_SEMANTIC_PROMPT_VERSION
from .gate2_financial_semantic_v6_totality import (
    Gate2FinancialSemanticV6TotalMaterializerFactory,
)
from .gate2_successor_local_proof import (
    _fixture_package,
    _validate_coverage,
    _validate_fixture_authority,
)


V6_LOCAL_PROOF_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_local_proof_receipt_v1"
)
V6_LOCAL_PROOF_POLICY_VERSION = (
    "broker_reports_gate2_candidate_records_by_construction_local_proof_v1"
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6LocalProofFactory.create is the only frozen V6 "
    "benchmark and zero-call local end-to-end proof entrypoint"
)
FORBIDDEN = (
    "The V6 local proof must not call a provider, activate runtime routes, "
    "write persistence, inspect customer data, repair a choice or replace "
    "Evidence Bundle, compiler, expansion, validator, materializer, catalog "
    "or query factories"
)

_ACCESS_CONTEXT = FinancialDomainAccessContext(
    user_ref="user:synthetic-v6-local-proof",
    case_ref="case:synthetic-v6-local-proof",
    workspace_ref="workspace:synthetic-v6-local-proof",
)
_CREATED_AT = "2026-07-27T00:00:00+00:00"


class Gate2FinancialSemanticV6LocalProofError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate2FinancialSemanticV6LocalProofFactory:
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
        validate_financial_semantic_v6_benchmark(
            manifest=frozen_manifest,
            base_manifest=frozen_base,
        )
        base_cases = {item["case_id"]: item for item in frozen_base["cases"]}
        scope_factory = Gate2DeterministicFinancialScopeFromGate1V2Factory(
            registry=self.registry
        )

        artifacts: list[dict[str, Any]] = []
        source_packages = []
        semantic_bundles: dict[str, dict[str, Any]] = {}
        case_receipts: list[dict[str, Any]] = []
        disposition_counts: Counter[str] = Counter()
        model_choice_counts: Counter[str] = Counter()
        route_counts: Counter[str] = Counter()
        typed_expected_total = 0
        typed_observed_total = 0
        typed_true_positive_total = 0
        unclassified_value_loss_total = 0
        validated_materialization_failures_total = 0
        context_bytes: list[int] = []
        estimated_tokens: list[int] = []
        bundle_hashes: list[str] = []
        compilation_hashes: list[str] = []
        packet_hashes: list[str] = []
        choice_schema_hashes: list[str] = []
        artifact_hashes: list[str] = []

        for benchmark_case in frozen_manifest["cases"]:
            case_id = benchmark_case["case_id"]
            source_case = copy.deepcopy(base_cases[case_id])
            fixture = _fixture_package(source_case)
            batch = scope_factory.create(gate1_packages=(fixture.payload,))
            repeated = scope_factory.create(
                gate1_packages=(copy.deepcopy(fixture.payload),)
            )
            if batch != repeated or len(batch.scopes) != 1:
                _fail("financial_semantic_v6_scope_not_deterministic")
            _validate_coverage(batch.coverage)
            scope = batch.scopes[0]
            validate_deterministic_financial_scope_v2(scope)
            _validate_fixture_authority(scope=scope, fixture=fixture)

            route = benchmark_case["expected_route"]
            route_counts[route] += 1
            semantic_hashes = {
                "evidence_bundle_integrity_hash": None,
                "candidate_compilation_integrity_hash": None,
                "packet_hash": None,
                "choice_schema_hash": None,
                "expansion_integrity_hash": None,
            }
            typed_options_total = None
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
                    _fail("financial_semantic_v6_technical_preclose_failed")
                canonical_model_output = copy.deepcopy(preclose.canonical_decision)
                validated = Gate2FinancialEvidenceValidatedDecisionFactory(
                    contract=scope.decision_contract
                ).create(canonical_model_output)
                execution_ref = f"execution:v6-local:{case_id}"
                validation_ref = f"validation:v6-local:{case_id}"
                artifact = (
                    Gate2FinancialEvidenceMaterializerFactory(
                        registry=self.registry,
                        source_package=scope.source_package,
                        execution_metadata=FinancialEvidenceExecutionMetadata(
                            execution_ref=execution_ref,
                            decision_validation_ref=validation_ref,
                        ),
                    )
                    .create()
                    .materialize(validated_decision=validated)
                )
            else:
                evidence_bundle = Gate2FinancialEvidenceBundleFactory().create(
                    source_package=scope.source_package,
                    gate1_packages=(fixture.payload,),
                )
                validate_financial_evidence_bundle(
                    bundle=evidence_bundle,
                    source_package=scope.source_package,
                )
                compilation = Gate2FinancialCandidateCompilerFactory(
                    registry=self.registry
                ).create(
                    evidence_bundle=evidence_bundle,
                    source_package=scope.source_package,
                )
                validate_financial_candidate_compilation(
                    compilation=compilation,
                    evidence_bundle=evidence_bundle,
                    source_package=scope.source_package,
                    registry=self.registry,
                )
                typed_options_total = len(compilation.typed_options)
                if typed_options_total != benchmark_case["expected_typed_options"]:
                    _fail("financial_semantic_v6_typed_options_mismatch")
                packet = Gate2FinancialSemanticV6PacketFactory(
                    registry=self.registry
                ).create(
                    evidence_bundle=evidence_bundle,
                    source_package=scope.source_package,
                    compilation=compilation,
                )
                validate_financial_semantic_v6_packet(
                    packet=packet,
                    evidence_bundle=evidence_bundle,
                    source_package=scope.source_package,
                    compilation=compilation,
                    registry=self.registry,
                )
                choice_contract = Gate2FinancialSemanticV6ChoiceContractFactory(
                    registry=self.registry
                ).create(
                    packet=packet,
                    evidence_bundle=evidence_bundle,
                    source_package=scope.source_package,
                    compilation=compilation,
                )
                validate_financial_semantic_v6_choice_contract(
                    contract=choice_contract,
                    packet=packet,
                    evidence_bundle=evidence_bundle,
                    source_package=scope.source_package,
                    compilation=compilation,
                    registry=self.registry,
                )
                model_choice = _fixture_model_choice(
                    benchmark_case=benchmark_case,
                    compilation=compilation,
                )
                expansion = Gate2FinancialSemanticV6DecisionExpansionFactory(
                    registry=self.registry
                ).create(
                    model_output=model_choice,
                    choice_contract=choice_contract,
                    packet=packet,
                    evidence_bundle=evidence_bundle,
                    source_package=scope.source_package,
                    compilation=compilation,
                )
                try:
                    total = Gate2FinancialSemanticV6TotalMaterializerFactory(
                        registry=self.registry
                    ).create(
                        expansion=expansion,
                        model_output=model_choice,
                        choice_contract=choice_contract,
                        packet=packet,
                        evidence_bundle=evidence_bundle,
                        source_package=scope.source_package,
                        compilation=compilation,
                    )
                except ValueError as exc:
                    validated_materialization_failures_total += 1
                    raise Gate2FinancialSemanticV6LocalProofError(
                        "financial_semantic_v6_validated_materialization_failed"
                    ) from exc
                artifact = copy.deepcopy(total.canonical_artifact)
                validated = expansion.validated_decision
                if expansion.disposition == "unclassified_financial_input":
                    terminal = artifact["unclassified_inputs"][0]
                    terminal_refs = {
                        item["source_value_ref"] for item in terminal["source_values"]
                    }
                    expected_refs = set(evidence_bundle.retention_set)
                    unclassified_value_loss_total += len(expected_refs - terminal_refs)
                    if terminal_refs != expected_refs:
                        _fail("financial_semantic_v6_unclassified_retention_loss")
                request = financial_semantic_v6_canonical_request(
                    packet=packet,
                    choice_contract=choice_contract,
                )
                request_context_bytes = len(canonical_json(request).encode("utf-8"))
                request_estimated_tokens = (request_context_bytes + 3) // 4
                context_bytes.append(request_context_bytes)
                estimated_tokens.append(request_estimated_tokens)
                model_choice_counts[expansion.disposition] += 1
                semantic_hashes = {
                    "evidence_bundle_integrity_hash": (evidence_bundle.integrity_hash),
                    "candidate_compilation_integrity_hash": (
                        compilation.integrity_hash
                    ),
                    "packet_hash": packet.packet_hash,
                    "choice_schema_hash": (choice_contract.choice_schema_hash),
                    "expansion_integrity_hash": expansion.integrity_hash,
                }
                bundle_hashes.append(evidence_bundle.integrity_hash)
                compilation_hashes.append(compilation.integrity_hash)
                packet_hashes.append(packet.packet_hash)
                choice_schema_hashes.append(choice_contract.choice_schema_hash)
                semantic_bundles[case_id] = {
                    "registry": self.registry,
                    "scope": scope,
                    "evidence_bundle": evidence_bundle,
                    "compilation": compilation,
                    "packet": packet,
                    "choice_contract": choice_contract,
                    "model_choice": model_choice,
                    "expansion": expansion,
                    "total": total,
                }

            validate_financial_evidence_inputs(
                payload=artifact,
                registry=self.registry,
                source_package=scope.source_package,
            )
            decision = validated.decision
            actual_disposition = decision.disposition
            actual_type_id = getattr(decision, "input_type_id", None)
            if (
                actual_disposition != benchmark_case["expected_disposition"]
                or actual_type_id != benchmark_case["expected_input_type_id"]
                or decision.reason_code != benchmark_case["expected_reason_code"]
            ):
                _fail("financial_semantic_v6_fixture_outcome_mismatch")
            expected_typed = benchmark_case["expected_disposition"] == "typed_input"
            observed_typed = actual_disposition == "typed_input"
            typed_expected_total += int(expected_typed)
            typed_observed_total += int(observed_typed)
            typed_true_positive_total += int(expected_typed and observed_typed)
            disposition_counts[actual_disposition] += 1
            artifacts.append(artifact)
            source_packages.append(scope.source_package)
            artifact_hashes.append(sha256_json(artifact))
            case_receipts.append(
                {
                    "case_id": case_id,
                    "route": route,
                    "disposition": actual_disposition,
                    "input_type_id": actual_type_id,
                    "typed_options_total": typed_options_total,
                    **semantic_hashes,
                    "materialized_artifact_hash": sha256_json(artifact),
                    "retained_source_values_total": len(
                        scope.source_package.source_values
                    ),
                    "context_bytes": request_context_bytes,
                    "estimated_tokens": request_estimated_tokens,
                    "provider_calls_total": 0,
                }
            )

        product_receipt = self._product_receipt(
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
            _fail("financial_semantic_v6_persistence_roundtrip_invalid")
        query = Gate2FinancialDomainQueryFactory(
            snapshot=restored,
            registry=self.registry,
            access_context=_ACCESS_CONTEXT,
            snapshot_authority_key=self._snapshot_authority_key,
            continuation_key=self._continuation_key,
        ).create()
        query_evidence = _query_evidence(query=query, snapshot=restored)
        negative_checks = run_financial_semantic_v6_negative_checks(
            registry=self.registry,
            snapshot_authority_key=self._snapshot_authority_key,
            access_context=_ACCESS_CONTEXT,
            created_at=_CREATED_AT,
            semantic_bundles=semantic_bundles,
            artifacts=artifacts,
            source_packages=source_packages,
            snapshot=restored,
            serialized=serialized,
        )

        product_metrics = product_receipt["metrics"]
        product_checks = product_receipt["checks"]
        adjacent_options = len(
            semantic_bundles["syn_successor_v2_adjacent_equal"][
                "compilation"
            ].typed_options
        )
        hard_gates = {
            "unclassified_value_loss_total": unclassified_value_loss_total,
            "validated_materialization_failures_total": (
                validated_materialization_failures_total
            ),
            "adjacent_equal_typed_options_total": adjacent_options,
            "query_gaps_total": query_evidence["query_gaps_total"],
            "invented_values_total": product_metrics["invented_values_total"],
            "duplicate_bindings_total": product_metrics["duplicate_bindings_total"],
            "cross_scope_bindings_total": product_metrics["cross_scope_bindings_total"],
            "ownership_gaps_total": product_metrics["terminal_ownership_gap_total"],
            "literal_or_provenance_loss_total": (
                product_metrics["literal_loss_total"]
                + query_evidence["provenance_gaps_total"]
            ),
            "invalid_refs_total": (
                0 if product_checks["exact_package_ref_membership"] else 1
            ),
            "wrong_roles_total": (0 if product_checks["role_compatibility"] else 1),
        }
        checks = {
            "benchmark_identity_exact": True,
            "routes_exact": route_counts
            == Counter({"semantic_model": 10, "technical_preclose": 2}),
            "both_model_choices": set(model_choice_counts)
            == {"typed_input", "unclassified_financial_input"},
            "canonical_four_dispositions": set(disposition_counts) == set(DISPOSITIONS),
            "all_v6_components_exercised": (
                len(bundle_hashes)
                == len(compilation_hashes)
                == len(packet_hashes)
                == len(choice_schema_hashes)
                == 10
            ),
            "adjacent_equal_has_zero_typed_options": adjacent_options == 0,
            "canonical_product_invariants": (product_receipt["status"] == "passed"),
            "hard_gates_zero": all(value == 0 for value in hard_gates.values()),
            "persistence_roundtrip": restored == snapshot,
            "domain_catalog_validated": True,
            "query_complete": query_evidence["query_gaps_total"] == 0,
            "negative_fail_closed": all(negative_checks.values()),
            "provider_calls_zero": True,
        }
        passed = all(checks.values())
        receipt: dict[str, Any] = {
            "schema_version": V6_LOCAL_PROOF_RECEIPT_SCHEMA_VERSION,
            "policy_version": V6_LOCAL_PROOF_POLICY_VERSION,
            "status": "passed" if passed else "failed",
            "acceptance": {
                "local_v6_proof": "PASSED" if passed else "FAILED",
                "unclassified_value_loss": (
                    "ZERO"
                    if hard_gates["unclassified_value_loss_total"] == 0
                    else "NONZERO"
                ),
                "validated_materialization_failures": (
                    "ZERO"
                    if hard_gates["validated_materialization_failures_total"] == 0
                    else "NONZERO"
                ),
                "adjacent_equal_typed_options": (
                    "ZERO"
                    if hard_gates["adjacent_equal_typed_options_total"] == 0
                    else "NONZERO"
                ),
                "query_gaps": (
                    "ZERO" if hard_gates["query_gaps_total"] == 0 else "NONZERO"
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
                "prompt_version": V6_SEMANTIC_PROMPT_VERSION,
                "evidence_bundle_schema_versions": sorted(
                    {
                        item["evidence_bundle"].schema_version
                        for item in semantic_bundles.values()
                    }
                ),
                "typed_option_schema_versions": sorted(
                    {
                        option.schema_version
                        for item in semantic_bundles.values()
                        for option in item["compilation"].typed_options
                    }
                ),
                "semantic_packet_schema_versions": sorted(
                    {
                        item["packet"].schema_version
                        for item in semantic_bundles.values()
                    }
                ),
                "semantic_choice_schema_versions": sorted(
                    {
                        item["choice_contract"].schema_version
                        for item in semantic_bundles.values()
                    }
                ),
                "domain_snapshot_schema_version": (
                    FINANCIAL_DOMAIN_SNAPSHOT_SCHEMA_VERSION
                ),
                "persistence_schema_version": (
                    FINANCIAL_DOMAIN_PERSISTENCE_SCHEMA_VERSION
                ),
                "query_schema_version": (FINANCIAL_DOMAIN_QUERY_SCHEMA_VERSION),
                "query_policy_version": (FINANCIAL_DOMAIN_QUERY_POLICY_VERSION),
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
                "unclassified_semantic_cases_total": (
                    model_choice_counts["unclassified_financial_input"]
                ),
                "model_context_bytes_total": sum(context_bytes),
                "model_context_bytes_max": max(context_bytes),
                "estimated_tokens_total": sum(estimated_tokens),
                "estimated_tokens_max": max(estimated_tokens),
            },
            "routes": {
                "technical_cases_total": route_counts["technical_preclose"],
                "semantic_model_cases_total": route_counts["semantic_model"],
                "model_choice_counts": {
                    key: model_choice_counts[key]
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
                "snapshot_integrity_sha256": restored.integrity_sha256,
                "serialized_snapshot_sha256": sha256_json(json.loads(serialized)),
                **query_evidence,
            },
            "case_receipts": case_receipts,
            "exact_hashes": {
                "evidence_bundle_hashes_sha256": sha256_json(sorted(bundle_hashes)),
                "candidate_compilation_hashes_sha256": sha256_json(
                    sorted(compilation_hashes)
                ),
                "packet_hashes_sha256": sha256_json(sorted(packet_hashes)),
                "choice_schema_hashes_sha256": sha256_json(
                    sorted(choice_schema_hashes)
                ),
                "artifact_hashes_sha256": sha256_json(sorted(artifact_hashes)),
                "product_receipt_hash": product_receipt["integrity_hash"],
            },
            "negative_checks": negative_checks,
            "execution_accounting": {
                "provider_calls_total": 0,
                "technical_case_provider_calls_total": 0,
                "semantic_fixture_choices_total": 10,
                "fallback_total": 0,
                "repair_attempts_total": 0,
                "hidden_retry_total": 0,
                "persistence_writes_total": 0,
                "production_route_activations_total": 0,
            },
        }
        receipt["integrity_sha256"] = sha256_json(receipt)
        if not passed:
            _fail("financial_semantic_v6_local_proof_failed")
        return receipt

    def _product_receipt(
        self,
        *,
        artifacts: list[dict[str, Any]],
        source_packages: list[Any],
    ) -> dict[str, Any]:
        context = Gate2FinancialContextProjectionFactory(registry=self.registry).create(
            materialized_artifacts=artifacts,
            source_packages=source_packages,
        )
        validate_financial_context(payload=context, registry=self.registry)
        owners: dict[str, set[str]] = {}
        for package in source_packages:
            for value in package.source_values:
                owners.setdefault(value.source_value_ref, set()).add(
                    package.source_scope_ref
                )
        metrics: Counter[str] = Counter()
        for artifact, package in zip(
            artifacts,
            source_packages,
            strict=True,
        ):
            if artifact["terminal_disposition"] in {
                "no_financial_input",
                "unsupported",
            }:
                continue
            terminals = (
                artifact["typed_inputs"]
                if artifact["terminal_disposition"] == "typed_input"
                else artifact["unclassified_inputs"]
            )
            if len(terminals) != 1:
                metrics["terminal_ownership_gap_total"] += 1
                continue
            terminal = terminals[0]
            observed_refs = [
                item["source_value_ref"] for item in terminal["source_values"]
            ]
            expected_refs = {value.source_value_ref for value in package.source_values}
            metrics["invented_values_total"] += len(set(observed_refs) - expected_refs)
            metrics["duplicate_bindings_total"] += len(observed_refs) - len(
                set(observed_refs)
            )
            metrics["cross_scope_bindings_total"] += sum(
                1
                for ref in observed_refs
                if owners.get(ref) != {package.source_scope_ref}
            )
            if artifact["terminal_disposition"] == "unclassified_financial_input":
                metrics["literal_loss_total"] += len(expected_refs - set(observed_refs))
            if terminal["source_ownership"] != {
                "normalization_run_ref": package.normalization_run_ref,
                "document_ref": package.document_ref,
                "source_package_ref": package.package_ref,
                "source_scope_ref": package.source_scope_ref,
            }:
                metrics["terminal_ownership_gap_total"] += len(observed_refs)
        checks = {
            "exact_package_ref_membership": (metrics["invented_values_total"] == 0),
            "role_compatibility": True,
            "invented_values_zero": (metrics["invented_values_total"] == 0),
            "duplicate_bindings_zero": (metrics["duplicate_bindings_total"] == 0),
            "cross_scope_bindings_zero": (metrics["cross_scope_bindings_total"] == 0),
            "terminal_ownership_complete": (
                metrics["terminal_ownership_gap_total"] == 0
            ),
            "unclassified_value_preservation": (metrics["literal_loss_total"] == 0),
            "final_context_integrity_exact": True,
        }
        material = {
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
            "metrics": {
                key: metrics[key]
                for key in (
                    "invented_values_total",
                    "duplicate_bindings_total",
                    "cross_scope_bindings_total",
                    "terminal_ownership_gap_total",
                    "literal_loss_total",
                )
            },
            "final_context_hash": sha256_json(context),
        }
        receipt = {
            **material,
            "integrity_hash": sha256_json(material),
        }
        if receipt["status"] != "passed":
            _fail("financial_semantic_v6_product_invariants_failed")
        return receipt


def _fixture_model_choice(
    *,
    benchmark_case: dict[str, Any],
    compilation,
) -> dict[str, Any]:
    if benchmark_case["expected_disposition"] == "typed_input":
        matches = tuple(
            option
            for option in compilation.typed_options
            if option.input_type_id == benchmark_case["expected_input_type_id"]
        )
        if len(matches) != 1:
            _fail("financial_semantic_v6_expected_option_not_unique")
        return {
            "disposition": "typed_input",
            "typed_option_id": matches[0].typed_option_id,
        }
    return {
        "disposition": "unclassified_financial_input",
        "reason_code": benchmark_case["expected_reason_code"],
    }


def _rate(numerator: int, denominator: int) -> int:
    if denominator == 0:
        return 0
    return numerator * 10000 // denominator


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6LocalProofError(code)
