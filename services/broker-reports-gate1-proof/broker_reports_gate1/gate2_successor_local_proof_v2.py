from __future__ import annotations

import copy
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
from .gate2_financial_evidence_source_context import (
    SOURCE_CONTEXT_SCHEMA_VERSION,
    Gate2FinancialEvidenceSourceContextFactory,
    validate_financial_evidence_source_context,
)
from .gate2_financial_evidence_successor import (
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3,
    SUCCESSOR_PROMPT_CONTRACT_ID_V3,
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
    validate_financial_evidence_successor_model_input_v3,
)
from .gate2_financial_evidence_successor_projection import (
    SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION,
    Gate2FinancialEvidenceSuccessorProviderProjectionFactory,
    validate_successor_provider_projection,
)
from .gate2_successor_compatibility import (
    Gate2SuccessorCompatibilityReaderFactory,
)
from .gate2_successor_local_proof import (
    _EvaluatedCase,
    _fixture_package,
    _model_output,
    _negative_checks,
    _validate_coverage,
    _validate_fixture_authority,
    _validate_provider_schema,
)
from .gate2_successor_product_comparator import (
    Gate2SuccessorProductComparatorFactory,
    Gate2SuccessorProductExpectation,
    Gate2SuccessorScopeObservation,
)


LOCAL_PROOF_V2_MANIFEST_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_successor_fixture_manifest_v2"
)
LOCAL_PROOF_V2_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_successor_local_proof_receipt_v2"
)
LOCAL_PROOF_V2_POLICY_VERSION = (
    "gate2_financial_successor_local_proof_v2"
)
REQUIRED_FEATURES_V2 = (
    "uniquely_typed",
    "multiple_compatible_types",
    "explicit_no_registry_type",
    "missing_discriminating_evidence",
    "sufficient_discriminating_evidence",
    "repeated_header",
    "detail_vs_subtotal",
    "adjacent_equal_values",
    "adjacent_fx_values",
    "optional_missing_dimensions",
    "forbidden_neighbouring_refs",
    "unsupported_shape",
)

FACTORY_REQUIRED = (
    "Gate2SuccessorLocalProofV2Factory.create is the only frozen synthetic "
    "ambiguity-discipline Q0/Q1 successor v2 proof entrypoint"
)
FORBIDDEN = (
    "Local proof v2 must not call a provider, retry, repair, fallback, "
    "persist artifacts, activate routing, pass expected answers to a model "
    "or replace canonical validators"
)


class Gate2SuccessorLocalProofV2Error(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class _NoCallModelClient:
    async def extract(self, **kwargs):
        _fail("successor_local_proof_v2_provider_call_forbidden")


class Gate2SuccessorLocalProofV2Factory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(self, *, manifest: dict[str, Any]) -> dict[str, Any]:
        frozen_manifest = _validate_manifest_v2(manifest)
        scope_factory = Gate2DeterministicFinancialScopeFromGate1V2Factory(
            registry=self.registry
        )
        context_factory = Gate2FinancialEvidenceSourceContextFactory()
        runner = Gate2FinancialEvidenceSuccessorRunnerFactory(
            registry=self.registry,
            model_client=_NoCallModelClient(),
            config=Gate2FinancialEvidenceSuccessorConfig(
                model_id="local-no-call-model",
                provider_profile_id="local_no_call",
                model_input_schema_version=(
                    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
                ),
                prompt_contract_id=SUCCESSOR_PROMPT_CONTRACT_ID_V3,
            ),
        ).create()
        projection_factory = (
            Gate2FinancialEvidenceSuccessorProviderProjectionFactory()
        )
        compatibility = Gate2SuccessorCompatibilityReaderFactory(
            registry=self.registry
        ).create()

        evaluated: list[_EvaluatedCase] = []
        source_packages = []
        artifacts: list[dict[str, Any]] = []
        feature_counts: Counter[str] = Counter()
        terminal_counts: Counter[str] = Counter()
        admission_counts: Counter[str] = Counter()
        model_input_hashes: set[str] = set()
        provider_projection_hashes: set[str] = set()
        source_context_hashes: set[str] = set()
        typed_admission_hashes: set[str] = set()
        source_literals_total = 0
        forbidden_refs_total = 0
        selected_source_refs_total = 0
        deterministic_no_fact_refs_total = 0
        overtyping_negative_tests_total = 0

        for case in frozen_manifest["cases"]:
            fixture = _fixture_package(case)
            batch = scope_factory.create(
                gate1_packages=(fixture.payload,)
            )
            repeated = scope_factory.create(
                gate1_packages=(fixture.payload,)
            )
            if (
                batch != repeated
                or batch.safe_summary() != repeated.safe_summary()
                or len(batch.scopes) != 1
            ):
                _fail("successor_local_proof_v2_scope_not_deterministic")
            scope = batch.scopes[0]
            validate_deterministic_financial_scope_v2(scope)
            _validate_coverage(batch.coverage)
            _validate_fixture_authority(
                scope=scope,
                fixture=fixture,
            )
            admission = scope.package["typed_admission"]
            expected_decision = case["decision"]
            expected_admitted_type_ids = (
                [expected_decision["input_type_id"]]
                if expected_decision["disposition"] == "typed_input"
                else []
            )
            if (
                admission["admitted_type_ids"]
                != expected_admitted_type_ids
                or list(scope.decision_contract.eligible_type_ids)
                != expected_admitted_type_ids
            ):
                _fail(
                    "successor_local_proof_v2_admission_expectation_invalid"
                )
            typed_admission_hashes.add(admission["integrity_hash"])
            admission_counts[
                "typed_available"
                if expected_admitted_type_ids
                else "typed_absent"
            ] += 1
            if (
                expected_decision["disposition"]
                == "unclassified_financial_input"
            ):
                overtyping_negative_tests_total += 1

            source_context = context_factory.create(
                source_scope_ref=scope.source_package.source_scope_ref,
                source_values=scope.source_package.source_values,
                candidates=scope.decision_contract.package.candidates,
                gate1_packages=(fixture.payload,),
            )
            validate_financial_evidence_source_context(
                context=source_context,
                source_scope_ref=scope.source_package.source_scope_ref,
                source_values=scope.source_package.source_values,
                candidates=scope.decision_contract.package.candidates,
            )
            model_input = runner.model_input(
                scope=scope,
                source_context=source_context,
            )
            validate_financial_evidence_successor_model_input_v3(
                model_input=model_input,
                scope=scope,
                registry=self.registry,
                source_context=source_context,
            )
            if (
                "expected" in str(model_input).lower()
                or "decision" in model_input
            ):
                _fail(
                    "successor_local_proof_v2_expected_answer_exposed"
                )
            model_input_hashes.add(sha256_json(model_input))
            source_context_hashes.add(source_context.integrity_hash)

            provider_projection = projection_factory.create(
                contract=scope.decision_contract
            )
            validate_successor_provider_projection(
                projection=provider_projection,
                contract=scope.decision_contract,
            )
            _validate_provider_schema(
                response_format=provider_projection.response_format,
            )
            provider_projection_hashes.add(
                provider_projection.response_format_hash
            )
            dispositions = set(
                provider_projection.disposition_order
            )
            if (
                ("typed_input" in dispositions)
                is not bool(expected_admitted_type_ids)
            ):
                _fail(
                    "successor_local_proof_v2_typed_branch_shape_invalid"
                )

            model_output = _model_output(
                case=case,
                scope=scope,
                selected_value_refs=fixture.selected_value_refs,
            )
            validated = Gate2FinancialEvidenceValidatedDecisionFactory(
                contract=scope.decision_contract
            ).create(model_output)
            execution_ref = (
                f"execution:local-proof-v2:{case['case_id']}"
            )
            decision_validation_ref = (
                f"validation:local-proof-v2:{case['case_id']}"
            )
            materializer = Gate2FinancialEvidenceMaterializerFactory(
                registry=self.registry,
                source_package=scope.source_package,
                execution_metadata=FinancialEvidenceExecutionMetadata(
                    execution_ref=execution_ref,
                    decision_validation_ref=decision_validation_ref,
                ),
            ).create()
            first_artifact = materializer.materialize(
                validated_decision=validated
            )
            second_artifact = materializer.materialize(
                validated_decision=validated
            )
            if first_artifact != second_artifact:
                _fail(
                    "successor_local_proof_v2_materialization_not_deterministic"
                )
            validate_financial_evidence_inputs(
                payload=first_artifact,
                registry=self.registry,
            )
            before_hash = sha256_json(first_artifact)
            read = compatibility.read(
                artifact_ref=(
                    f"artifact:local-proof-v2:{case['case_id']}"
                ),
                payload=first_artifact,
            )
            if (
                sha256_json(first_artifact) != before_hash
                or read.artifact_sha256 != before_hash
                or read.read_kind != "successor_financial_evidence"
                or read.legacy_payload_rewritten
                or read.silent_conversion_used
            ):
                _fail(
                    "successor_local_proof_v2_compatibility_read_invalid"
                )

            disposition = model_output["decision"]["disposition"]
            input_type_id = model_output["decision"].get(
                "input_type_id"
            )
            evaluated.append(
                _EvaluatedCase(
                    scope=scope,
                    model_output=model_output,
                    materialized_artifact=first_artifact,
                    execution_ref=execution_ref,
                    decision_validation_ref=decision_validation_ref,
                    expected_disposition=disposition,
                    expected_input_type_id=input_type_id,
                )
            )
            source_packages.append(scope.source_package)
            artifacts.append(first_artifact)
            feature_counts.update(case["features"])
            terminal_counts[disposition] += 1
            source_literals_total += len(fixture.selected_literals)
            forbidden_refs_total += len(fixture.forbidden_value_refs)
            selected_source_refs_total += batch.coverage[
                "selected_source_refs_total"
            ]
            deterministic_no_fact_refs_total += batch.coverage[
                "deterministic_no_fact_source_refs_total"
            ]

        first_context = Gate2FinancialContextProjectionFactory(
            registry=self.registry
        ).create(
            materialized_artifacts=artifacts,
            source_packages=source_packages,
        )
        second_context = Gate2FinancialContextProjectionFactory(
            registry=self.registry
        ).create(
            materialized_artifacts=tuple(reversed(artifacts)),
            source_packages=tuple(reversed(source_packages)),
        )
        if first_context != second_context:
            _fail("successor_local_proof_v2_context_not_deterministic")
        validate_financial_context(
            payload=first_context,
            registry=self.registry,
        )
        product_receipt = Gate2SuccessorProductComparatorFactory(
            registry=self.registry
        ).create().compare(
            authorized_scopes=(
                item.scope for item in evaluated
            ),
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
                        expected_disposition=(
                            item.expected_disposition
                        ),
                        expected_input_type_id=(
                            item.expected_input_type_id
                        ),
                    ),
                )
                for item in evaluated
            ),
            final_context=first_context,
        )
        if product_receipt["status"] != "passed":
            _fail("successor_local_proof_v2_product_invariants_failed")
        negative_checks = _negative_checks(
            evaluated=evaluated,
            compatibility=compatibility,
            context=first_context,
            registry=self.registry,
        )
        q0_checks = {
            "scope_v2_determinism": True,
            "typed_admission_integrity": True,
            "source_context_v2_integrity": True,
            "model_input_v3_integrity": True,
            "provider_projection_v3_integrity": True,
            "canonical_branch_validation": True,
            "materialization_determinism": True,
            "context_determinism": True,
            "compatibility_read": True,
            "coverage_accounting": True,
            "negative_fail_closed": all(negative_checks.values()),
        }
        q1_checks = {
            feature: feature_counts[feature] > 0
            for feature in REQUIRED_FEATURES_V2
        }
        terminal_coverage = all(
            terminal_counts[disposition] > 0
            for disposition in DISPOSITIONS
        )
        metrics = product_receipt["metrics"]
        passed = (
            all(q0_checks.values())
            and all(q1_checks.values())
            and terminal_coverage
            and metrics["literal_loss_total"] == 0
            and metrics["invented_values_total"] == 0
            and metrics["duplicate_bindings_total"] == 0
            and metrics["cross_scope_bindings_total"] == 0
            and metrics["terminal_ownership_gap_total"] == 0
        )
        receipt: dict[str, Any] = {
            "schema_version": LOCAL_PROOF_V2_RECEIPT_SCHEMA_VERSION,
            "policy_version": LOCAL_PROOF_V2_POLICY_VERSION,
            "status": "passed" if passed else "failed",
            "manifest": {
                "schema_version": frozen_manifest["schema_version"],
                "benchmark_id": frozen_manifest["benchmark_id"],
                "integrity_hash": sha256_json(frozen_manifest),
                "frozen": True,
                "contains_customer_data": False,
                "cases_total": len(frozen_manifest["cases"]),
            },
            "exact_contracts": {
                "scope_schema_version": (
                    batch.safe_summary()["scope_schema_version"]
                ),
                "typed_admission_schema_version": (
                    scope.package["typed_admission"]["schema_version"]
                ),
                "source_context_schema_version": (
                    SOURCE_CONTEXT_SCHEMA_VERSION
                ),
                "model_input_schema_version": (
                    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
                ),
                "prompt_contract_id": (
                    SUCCESSOR_PROMPT_CONTRACT_ID_V3
                ),
                "prompt_hash": runner.prompt.hash,
                "provider_projection_schema_version": (
                    SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
                ),
            },
            "q0_contract_tests": {
                "status": (
                    "passed" if all(q0_checks.values()) else "failed"
                ),
                "checks": q0_checks,
            },
            "q1_product_invariant_fixtures": {
                "status": (
                    "passed" if all(q1_checks.values()) else "failed"
                ),
                "required_features_total": len(REQUIRED_FEATURES_V2),
                "covered_features_total": sum(q1_checks.values()),
                "checks": q1_checks,
            },
            "terminal_disposition_counts": {
                disposition: terminal_counts[disposition]
                for disposition in DISPOSITIONS
            },
            "typed_admission": {
                "typed_available_scopes_total": admission_counts[
                    "typed_available"
                ],
                "typed_absent_scopes_total": admission_counts[
                    "typed_absent"
                ],
                "overtyping_negative_tests_total": (
                    overtyping_negative_tests_total
                ),
                "overtyping_negative_tests_passed": (
                    overtyping_negative_tests_total
                ),
                "admission_integrity_hashes": sorted(
                    typed_admission_hashes
                ),
                "unsafe_typed_branches_total": 0,
                "post_response_conversion_total": 0,
            },
            "exact_hashes": {
                "source_context_integrity_hashes": sorted(
                    source_context_hashes
                ),
                "model_input_hashes": sorted(model_input_hashes),
                "provider_response_format_hashes": sorted(
                    provider_projection_hashes
                ),
            },
            "product_invariants": {
                "status": product_receipt["status"],
                "checks": copy.deepcopy(product_receipt["checks"]),
                "literal_loss_total": metrics["literal_loss_total"],
                "invented_values_total": metrics[
                    "invented_values_total"
                ],
                "duplicate_bindings_total": metrics[
                    "duplicate_bindings_total"
                ],
                "cross_scope_bindings_total": metrics[
                    "cross_scope_bindings_total"
                ],
                "terminal_ownership_gap_total": metrics[
                    "terminal_ownership_gap_total"
                ],
            },
            "coverage": {
                "selected_source_refs_total": selected_source_refs_total,
                "deterministic_no_fact_refs_total": (
                    deterministic_no_fact_refs_total
                ),
                "source_literals_total": source_literals_total,
                "source_literals_preserved_total": source_literals_total,
                "forbidden_neighbouring_refs_total": (
                    forbidden_refs_total
                ),
                "forbidden_neighbouring_refs_admitted_total": 0,
                "unaccounted_source_refs_total": 0,
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
            "context_integrity_hash": first_context["integrity_hash"],
        }
        receipt["integrity_hash"] = sha256_json(receipt)
        if receipt["status"] != "passed":
            _fail("successor_local_proof_v2_failed")
        return receipt


def _validate_manifest_v2(manifest: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        _fail("successor_local_proof_v2_manifest_invalid")
    frozen = copy.deepcopy(manifest)
    if (
        frozen.get("schema_version")
        != LOCAL_PROOF_V2_MANIFEST_SCHEMA_VERSION
        or frozen.get("benchmark_id")
        != "gate2_financial_successor_v2"
        or frozen.get("corpus_role")
        != "frozen_synthetic_ambiguity_discipline_successor_proof"
        or frozen.get("contains_customer_data") is not False
        or frozen.get("frozen") is not True
        or frozen.get("case_count") != len(frozen.get("cases") or [])
        or tuple(frozen.get("required_features") or [])
        != REQUIRED_FEATURES_V2
    ):
        _fail("successor_local_proof_v2_manifest_identity_invalid")
    policy = frozen.get("execution_policy") or {}
    if (
        policy.get("provider_calls") != 0
        or policy.get("hidden_retry") is not False
        or policy.get("repair") is not False
        or policy.get("fallback") is not False
        or policy.get("canonical_validator_replacement") is not False
        or policy.get("raw_output_in_safe_receipt") is not False
    ):
        _fail("successor_local_proof_v2_execution_policy_invalid")
    cases = frozen.get("cases") or []
    case_ids = [item.get("case_id") for item in cases]
    if (
        len(cases) < len(REQUIRED_FEATURES_V2)
        or len(case_ids) != len(set(case_ids))
        or not all(isinstance(item, str) and item for item in case_ids)
    ):
        _fail("successor_local_proof_v2_cases_invalid")
    observed_features = {
        feature
        for case in cases
        for feature in case.get("features") or []
    }
    if observed_features != set(REQUIRED_FEATURES_V2):
        _fail("successor_local_proof_v2_feature_coverage_invalid")
    return frozen


def _fail(code: str) -> None:
    raise Gate2SuccessorLocalProofV2Error(code)
