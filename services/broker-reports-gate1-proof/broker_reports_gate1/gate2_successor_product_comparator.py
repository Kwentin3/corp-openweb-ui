from __future__ import annotations

import copy
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .gate2_deterministic_financial_scopes import (
    Gate2DeterministicFinancialScope,
    Gate2DeterministicFinancialScopeError,
    validate_deterministic_financial_scope,
)
from .gate2_financial_context import (
    Gate2FinancialContextProjectionError,
    Gate2FinancialContextProjectionFactory,
)
from .gate2_financial_evidence_decision import (
    DISPOSITIONS,
    Gate2FinancialEvidenceDecisionError,
    TypedFinancialInputDecision,
    UnclassifiedFinancialInputDecision,
)
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializationError,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)


SUCCESSOR_COMPARATOR_SCHEMA_VERSION = (
    "broker_reports_gate2_successor_product_comparator_v1"
)
SUCCESSOR_COMPARATOR_POLICY_VERSION = (
    "gate2_successor_product_invariants_v1"
)
COMPARATOR_CLASSIFICATIONS = (
    "model_wrong",
    "acceptable_alternative",
    "comparator_defect",
    "contract_gap",
    "actual_data_loss",
    "unknown",
)
COMPARATOR_FAILURE_LAYERS = (
    "package",
    "schema",
    "canonical",
    "semantic",
    "materialization",
    "context",
)

FACTORY_REQUIRED = (
    "Gate2SuccessorProductComparatorFactory.create is the only successor "
    "product-invariant comparison entrypoint"
)
FORBIDDEN = (
    "Comparators must not require exact legacy candidate, relation, path, "
    "confidence, completeness, uncertainty, audit or graph serialization"
)


class Gate2SuccessorProductComparatorError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2SuccessorProductExpectation:
    expected_disposition: str | None = None
    acceptable_alternative_dispositions: tuple[str, ...] = ()
    expected_input_type_id: str | None = None
    acceptable_alternative_input_type_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Gate2SuccessorScopeObservation:
    source_scope_ref: str
    model_output: str | dict[str, Any]
    materialized_artifact: dict[str, Any]
    execution_ref: str
    decision_validation_ref: str
    expectation: Gate2SuccessorProductExpectation | None = None


class Gate2SuccessorProductComparatorFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(self) -> "Gate2SuccessorProductComparator":
        return Gate2SuccessorProductComparator(registry=self.registry)


class Gate2SuccessorProductComparator:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def compare(
        self,
        *,
        authorized_scopes: Iterable[Gate2DeterministicFinancialScope],
        observations: Iterable[Gate2SuccessorScopeObservation],
        final_context: dict[str, Any],
    ) -> dict[str, Any]:
        scopes = tuple(
            sorted(
                authorized_scopes,
                key=lambda item: item.source_package.source_scope_ref,
            )
        )
        observed = tuple(
            sorted(
                observations,
                key=lambda item: item.source_scope_ref,
            )
        )
        if not scopes:
            _fail("successor_comparator_scopes_empty")

        checks = {
            "eligible_dispositions": True,
            "eligible_registry_types": True,
            "exact_package_ref_membership": True,
            "role_compatibility": True,
            "literal_preservation": True,
            "invented_values_zero": True,
            "duplicate_bindings_zero": True,
            "cross_scope_bindings_zero": True,
            "terminal_ownership_complete": True,
            "unclassified_value_preservation": True,
            "deterministic_materialization_exact": True,
            "final_context_integrity_exact": True,
            "product_expectations_met": True,
            "internal_graph_exactness_not_compared": True,
        }
        mismatches: list[dict[str, Any]] = []
        metrics: Counter[str] = Counter()

        scope_by_ref: dict[str, Gate2DeterministicFinancialScope] = {}
        scope_index_by_ref: dict[str, int] = {}
        candidate_owners: defaultdict[str, set[str]] = defaultdict(set)
        for index, scope in enumerate(scopes):
            try:
                validate_deterministic_financial_scope(scope)
            except Gate2DeterministicFinancialScopeError as exc:
                checks["exact_package_ref_membership"] = False
                _mismatch(
                    mismatches,
                    path=_path(index, "package"),
                    failure_layer="package",
                    classification="contract_gap",
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    reason_code=exc.code,
                )
                continue
            scope_ref = scope.source_package.source_scope_ref
            if scope_ref in scope_by_ref:
                checks["terminal_ownership_complete"] = False
                metrics["ownership_gap_total"] += len(
                    scope.selected_source_refs
                )
                _mismatch(
                    mismatches,
                    path="$.authorized_scopes",
                    failure_layer="package",
                    classification="contract_gap",
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    terminal_ownership_gap_total=len(
                        scope.selected_source_refs
                    ),
                    reason_code="authorized_scope_identity_duplicate",
                )
                continue
            scope_by_ref[scope_ref] = scope
            scope_index_by_ref[scope_ref] = index
            for candidate in scope.decision_contract.package.candidates:
                candidate_owners[candidate.source_value_ref].add(scope_ref)

        cross_scope_candidate_refs = {
            ref for ref, owners in candidate_owners.items() if len(owners) > 1
        }
        if cross_scope_candidate_refs:
            checks["cross_scope_bindings_zero"] = False
            metrics["cross_scope_binding_total"] += len(
                cross_scope_candidate_refs
            )
            _mismatch(
                mismatches,
                path="$.authorized_scopes[*].decision_contract.candidates",
                failure_layer="package",
                classification="contract_gap",
                affected_source_refs_total=len(
                    cross_scope_candidate_refs
                ),
                reason_code="candidate_ref_has_multiple_scope_owners",
            )

        observations_by_ref: defaultdict[
            str, list[Gate2SuccessorScopeObservation]
        ] = defaultdict(list)
        for observation in observed:
            observations_by_ref[observation.source_scope_ref].append(
                observation
            )
        unknown_observations = sorted(
            set(observations_by_ref) - set(scope_by_ref)
        )
        if unknown_observations:
            checks["cross_scope_bindings_zero"] = False
            metrics["cross_scope_binding_total"] += len(
                unknown_observations
            )
            _mismatch(
                mismatches,
                path="$.observations.out_of_scope",
                failure_layer="package",
                classification="contract_gap",
                affected_source_refs_total=0,
                reason_code="observation_scope_not_authorized",
            )

        recomputed_artifacts: list[dict[str, Any]] = []
        recomputed_packages = []
        for scope_ref, scope in sorted(scope_by_ref.items()):
            index = scope_index_by_ref[scope_ref]
            candidates = {
                item.source_value_ref: item
                for item in scope.decision_contract.package.candidates
            }
            scope_observations = observations_by_ref.get(scope_ref, [])
            if len(scope_observations) != 1:
                checks["terminal_ownership_complete"] = False
                gap = len(scope.selected_source_refs)
                metrics["ownership_gap_total"] += gap
                _mismatch(
                    mismatches,
                    path=_path(index, "terminal_ownership"),
                    failure_layer="semantic",
                    classification="actual_data_loss",
                    affected_source_refs_total=gap,
                    terminal_ownership_gap_total=gap,
                    reason_code=(
                        "terminal_observation_missing"
                        if not scope_observations
                        else "terminal_observation_duplicate"
                    ),
                )
                continue
            observation = scope_observations[0]
            raw_bindings = _raw_bindings(observation.model_output)
            try:
                validated = Gate2FinancialEvidenceValidatedDecisionFactory(
                    contract=scope.decision_contract
                ).create(observation.model_output)
            except Gate2FinancialEvidenceDecisionError as exc:
                checks["eligible_dispositions"] = False
                checks["eligible_registry_types"] = False
                checks["exact_package_ref_membership"] = False
                checks["role_compatibility"] = False
                checks["terminal_ownership_complete"] = False
                raw_refs = [ref for _, ref in raw_bindings]
                raw_invented = {
                    ref for ref in raw_refs if ref not in candidates
                }
                if raw_invented:
                    checks["invented_values_zero"] = False
                    metrics["invented_values_total"] += len(
                        raw_invented
                    )
                raw_duplicates = len(raw_refs) - len(set(raw_refs))
                if raw_duplicates:
                    checks["duplicate_bindings_zero"] = False
                    metrics["duplicate_bindings_total"] += raw_duplicates
                if any(
                    ref in candidates
                    and role not in candidates[ref].allowed_roles
                    for role, ref in raw_bindings
                ):
                    checks["role_compatibility"] = False
                if any(
                    ref in candidate_owners
                    and (
                        len(candidate_owners[ref]) != 1
                        or scope_ref not in candidate_owners[ref]
                    )
                    for ref in raw_refs
                ):
                    checks["cross_scope_bindings_zero"] = False
                    metrics["cross_scope_binding_total"] += 1
                gap = len(scope.selected_source_refs)
                metrics["ownership_gap_total"] += gap
                _mismatch(
                    mismatches,
                    path=_path(index, "decision"),
                    failure_layer="canonical",
                    classification="model_wrong",
                    affected_source_refs_total=gap,
                    terminal_ownership_gap_total=gap,
                    reason_code=exc.code,
                )
                continue

            decision = validated.decision
            disposition = decision.disposition
            if disposition not in DISPOSITIONS:
                checks["eligible_dispositions"] = False
                _mismatch(
                    mismatches,
                    path=_path(index, "decision.disposition"),
                    failure_layer="semantic",
                    classification="model_wrong",
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    reason_code="decision_disposition_not_eligible",
                )
            input_type_id = (
                decision.input_type_id
                if isinstance(decision, TypedFinancialInputDecision)
                else None
            )
            if (
                input_type_id is not None
                and input_type_id
                not in scope.decision_contract.eligible_type_ids
            ):
                checks["eligible_registry_types"] = False
                _mismatch(
                    mismatches,
                    path=_path(index, "decision.input_type_id"),
                    failure_layer="semantic",
                    classification="model_wrong",
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    reason_code="decision_registry_type_not_eligible",
                )

            bindings = tuple(getattr(decision, "value_bindings", ()))
            binding_refs = [item.source_value_ref for item in bindings]
            invented_binding_refs = {
                ref for ref in binding_refs if ref not in candidates
            }
            if invented_binding_refs:
                checks["exact_package_ref_membership"] = False
                checks["invented_values_zero"] = False
                metrics["invented_values_total"] += len(
                    invented_binding_refs
                )
                _mismatch(
                    mismatches,
                    path=_path(index, "decision.value_bindings[*]"),
                    failure_layer="canonical",
                    classification="model_wrong",
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    reason_code="binding_ref_not_in_package",
                )
            duplicate_binding_refs = len(binding_refs) - len(
                set(binding_refs)
            )
            if duplicate_binding_refs:
                checks["duplicate_bindings_zero"] = False
                metrics["duplicate_bindings_total"] += duplicate_binding_refs
                _mismatch(
                    mismatches,
                    path=_path(index, "decision.value_bindings[*]"),
                    failure_layer="canonical",
                    classification="model_wrong",
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    reason_code="binding_ref_duplicate",
                )
            incompatible_roles = [
                item
                for item in bindings
                if item.source_value_ref in candidates
                and item.role_id
                not in candidates[item.source_value_ref].allowed_roles
            ]
            if incompatible_roles:
                checks["role_compatibility"] = False
                _mismatch(
                    mismatches,
                    path=_path(index, "decision.value_bindings[*].role_id"),
                    failure_layer="canonical",
                    classification="model_wrong",
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    reason_code="binding_role_not_compatible",
                )
            if any(
                len(candidate_owners.get(ref, ())) != 1
                or scope_ref not in candidate_owners.get(ref, ())
                for ref in binding_refs
            ):
                checks["cross_scope_bindings_zero"] = False
                metrics["cross_scope_binding_total"] += 1
                _mismatch(
                    mismatches,
                    path=_path(index, "decision.value_bindings[*]"),
                    failure_layer="semantic",
                    classification="model_wrong",
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    reason_code="binding_crosses_scope_boundary",
                )

            if isinstance(
                decision,
                UnclassifiedFinancialInputDecision,
            ) and set(binding_refs) != set(candidates):
                checks["unclassified_value_preservation"] = False
                loss = len(set(candidates) - set(binding_refs))
                metrics["literal_loss_total"] += loss
                _mismatch(
                    mismatches,
                    path=_path(index, "decision.value_bindings"),
                    failure_layer="semantic",
                    classification="actual_data_loss",
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    literal_loss_total=loss,
                    reason_code="unclassified_candidate_value_not_preserved",
                )

            self._compare_expectation(
                index=index,
                scope=scope,
                expectation=observation.expectation,
                disposition=disposition,
                input_type_id=input_type_id,
                checks=checks,
                mismatches=mismatches,
            )

            try:
                expected_artifact = (
                    Gate2FinancialEvidenceMaterializerFactory(
                        registry=self.registry,
                        source_package=scope.source_package,
                        execution_metadata=(
                            FinancialEvidenceExecutionMetadata(
                                execution_ref=observation.execution_ref,
                                decision_validation_ref=(
                                    observation.decision_validation_ref
                                ),
                            )
                        ),
                    )
                    .create()
                    .materialize(validated_decision=validated)
                )
            except Gate2FinancialEvidenceMaterializationError as exc:
                checks["deterministic_materialization_exact"] = False
                _mismatch(
                    mismatches,
                    path=_path(index, "materialized_artifact"),
                    failure_layer="materialization",
                    classification=(
                        "actual_data_loss"
                        if metrics["literal_loss_total"]
                        else "contract_gap"
                    ),
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    reason_code=exc.code,
                )
                continue
            actual_values = _artifact_values(
                observation.materialized_artifact
            )
            expected_values = {
                item.source_value_ref: item.literal_value
                for item in scope.source_package.source_values
            }
            actual_refs = [ref for ref, _ in actual_values]
            invented_actual = {
                ref for ref in actual_refs if ref not in expected_values
            }
            if invented_actual:
                checks["invented_values_zero"] = False
                metrics["invented_values_total"] += len(invented_actual)
            duplicate_actual = len(actual_refs) - len(set(actual_refs))
            if duplicate_actual:
                checks["duplicate_bindings_zero"] = False
                metrics["duplicate_bindings_total"] += duplicate_actual
            expected_bound_refs = set(binding_refs)
            actual_literal_by_ref = {
                ref: literal for ref, literal in actual_values
            }
            literal_loss = sum(
                1
                for ref in expected_bound_refs
                if ref not in actual_literal_by_ref
                or actual_literal_by_ref[ref] != expected_values.get(ref)
            )
            if literal_loss:
                checks["literal_preservation"] = False
                metrics["literal_loss_total"] += literal_loss
            if (
                observation.materialized_artifact
                != expected_artifact
            ):
                checks["deterministic_materialization_exact"] = False
                classification = (
                    "actual_data_loss"
                    if literal_loss or invented_actual
                    else "contract_gap"
                )
                _mismatch(
                    mismatches,
                    path=_path(index, "materialized_artifact"),
                    failure_layer="materialization",
                    classification=classification,
                    affected_source_refs_total=len(
                        scope.selected_source_refs
                    ),
                    literal_loss_total=literal_loss,
                    reason_code="deterministic_materialization_not_exact",
                )
            recomputed_artifacts.append(expected_artifact)
            recomputed_packages.append(scope.source_package)

        expected_context: dict[str, Any] | None = None
        if len(recomputed_artifacts) == len(scope_by_ref):
            try:
                expected_context = Gate2FinancialContextProjectionFactory(
                    registry=self.registry
                ).create(
                    materialized_artifacts=recomputed_artifacts,
                    source_packages=recomputed_packages,
                )
            except (
                Gate2FinancialContextProjectionError,
                Gate2FinancialEvidenceMaterializationError,
            ) as exc:
                checks["final_context_integrity_exact"] = False
                _mismatch(
                    mismatches,
                    path="$.final_context",
                    failure_layer="context",
                    classification="contract_gap",
                    affected_source_refs_total=sum(
                        len(item.selected_source_refs) for item in scopes
                    ),
                    reason_code=getattr(
                        exc,
                        "code",
                        "context_recomputation_failed",
                    ),
                )
        if expected_context is None or final_context != expected_context:
            checks["final_context_integrity_exact"] = False
            if not any(
                item["failure_layer"] == "context"
                for item in mismatches
            ):
                _mismatch(
                    mismatches,
                    path="$.final_context",
                    failure_layer="context",
                    classification=(
                        "actual_data_loss"
                        if metrics["literal_loss_total"]
                        or metrics["ownership_gap_total"]
                        else "contract_gap"
                    ),
                    affected_source_refs_total=sum(
                        len(item.selected_source_refs) for item in scopes
                    ),
                    literal_loss_total=metrics["literal_loss_total"],
                    terminal_ownership_gap_total=metrics[
                        "ownership_gap_total"
                    ],
                    reason_code="final_context_not_deterministically_exact",
                )

        classification_counts = Counter(
            item["classification"] for item in mismatches
        )
        blocking_mismatches = sum(
            1 for item in mismatches if item["blocking"]
        )
        receipt: dict[str, Any] = {
            "schema_version": SUCCESSOR_COMPARATOR_SCHEMA_VERSION,
            "policy_version": SUCCESSOR_COMPARATOR_POLICY_VERSION,
            "status": (
                "passed"
                if all(checks.values()) and blocking_mismatches == 0
                else "failed"
            ),
            "checks": checks,
            "authorized_scopes_total": len(scope_by_ref),
            "observations_total": len(observed),
            "mismatch_paths": [
                item["path"] for item in mismatches
            ],
            "mismatches": mismatches,
            "classification_counts": {
                classification: classification_counts.get(
                    classification,
                    0,
                )
                for classification in COMPARATOR_CLASSIFICATIONS
            },
            "metrics": {
                "affected_source_refs_total": _affected_refs_total(
                    mismatches=mismatches,
                    scopes=scopes,
                ),
                "affected_source_ref_events_total": sum(
                    item["affected_source_refs_total"]
                    for item in mismatches
                ),
                "literal_loss_total": metrics["literal_loss_total"],
                "terminal_ownership_gap_total": metrics[
                    "ownership_gap_total"
                ],
                "invented_values_total": metrics[
                    "invented_values_total"
                ],
                "duplicate_bindings_total": metrics[
                    "duplicate_bindings_total"
                ],
                "cross_scope_bindings_total": metrics[
                    "cross_scope_binding_total"
                ],
                "actual_data_loss_detected": bool(
                    metrics["literal_loss_total"]
                    or metrics["ownership_gap_total"]
                    or metrics["invented_values_total"]
                ),
            },
            "comparison_boundary": {
                "exact_equality_applied_to": [
                    "deterministic_materialized_artifacts",
                    "deterministic_final_context",
                ],
                "exact_equality_not_applied_to": [
                    "legacy_candidate_graph",
                    "legacy_relation_graph",
                    "legacy_fact_paths",
                    "model_confidence",
                    "model_completeness",
                    "model_uncertainty",
                    "model_audit_fields",
                ],
                "legacy_benchmark_rewritten": False,
            },
        }
        receipt["integrity_hash"] = sha256_json(receipt)
        _validate_value_free_receipt(
            receipt=receipt,
            scopes=scopes,
        )
        return receipt

    def _compare_expectation(
        self,
        *,
        index: int,
        scope: Gate2DeterministicFinancialScope,
        expectation: Gate2SuccessorProductExpectation | None,
        disposition: str,
        input_type_id: str | None,
        checks: dict[str, bool],
        mismatches: list[dict[str, Any]],
    ) -> None:
        if expectation is None:
            return
        _validate_expectation(expectation)
        if (
            expectation.expected_disposition is not None
            and disposition != expectation.expected_disposition
        ):
            acceptable = (
                disposition
                in expectation.acceptable_alternative_dispositions
            )
            if not acceptable:
                checks["product_expectations_met"] = False
            _mismatch(
                mismatches,
                path=_path(index, "decision.disposition"),
                failure_layer="semantic",
                classification=(
                    "acceptable_alternative"
                    if acceptable
                    else "model_wrong"
                ),
                affected_source_refs_total=len(
                    scope.selected_source_refs
                ),
                reason_code=(
                    "accepted_equivalent_disposition"
                    if acceptable
                    else "product_disposition_expectation_failed"
                ),
                blocking=not acceptable,
            )
        if (
            expectation.expected_input_type_id is not None
            and input_type_id != expectation.expected_input_type_id
        ):
            acceptable = (
                input_type_id is not None
                and input_type_id
                in expectation.acceptable_alternative_input_type_ids
            )
            if not acceptable:
                checks["product_expectations_met"] = False
            _mismatch(
                mismatches,
                path=_path(index, "decision.input_type_id"),
                failure_layer="semantic",
                classification=(
                    "acceptable_alternative"
                    if acceptable
                    else "model_wrong"
                ),
                affected_source_refs_total=len(
                    scope.selected_source_refs
                ),
                reason_code=(
                    "accepted_equivalent_registry_type"
                    if acceptable
                    else "product_registry_type_expectation_failed"
                ),
                blocking=not acceptable,
            )


def _validate_expectation(
    expectation: Gate2SuccessorProductExpectation,
) -> None:
    dispositions = {
        item
        for item in (
            expectation.expected_disposition,
            *expectation.acceptable_alternative_dispositions,
        )
        if item is not None
    }
    if not dispositions <= set(DISPOSITIONS):
        _fail("successor_comparator_expectation_disposition_invalid")
    if (
        len(expectation.acceptable_alternative_dispositions)
        != len(set(expectation.acceptable_alternative_dispositions))
        or len(expectation.acceptable_alternative_input_type_ids)
        != len(set(expectation.acceptable_alternative_input_type_ids))
    ):
        _fail("successor_comparator_expectation_duplicate")


def _artifact_values(
    artifact: dict[str, Any],
) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    if not isinstance(artifact, dict):
        return values
    terminals = []
    for field in ("typed_inputs", "unclassified_inputs"):
        items = artifact.get(field)
        if isinstance(items, list):
            terminals.extend(
                item for item in items if isinstance(item, dict)
            )
    for terminal in terminals:
        source_values = terminal.get("source_values")
        if not isinstance(source_values, list):
            continue
        for item in source_values:
            if not isinstance(item, dict):
                continue
            ref = item.get("source_value_ref")
            literal = item.get("literal_value")
            if isinstance(ref, str) and isinstance(literal, str):
                values.append((ref, literal))
    return values


def _raw_bindings(
    model_output: str | dict[str, Any],
) -> list[tuple[str, str]]:
    if isinstance(model_output, str):
        try:
            payload = json.loads(model_output)
        except (TypeError, ValueError):
            return []
    else:
        payload = model_output
    if not isinstance(payload, dict):
        return []
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        return []
    bindings = decision.get("value_bindings")
    result: list[tuple[str, str]] = []
    if isinstance(bindings, dict):
        for role, ref in bindings.items():
            if isinstance(role, str) and isinstance(ref, str):
                result.append((role, ref))
    elif isinstance(bindings, list):
        for item in bindings:
            if not isinstance(item, dict):
                continue
            role = item.get("role_id")
            ref = item.get("source_value_ref")
            if isinstance(role, str) and isinstance(ref, str):
                result.append((role, ref))
    return result


def _affected_refs_total(
    *,
    mismatches: list[dict[str, Any]],
    scopes: tuple[Gate2DeterministicFinancialScope, ...],
) -> int:
    affected: set[str] = set()
    global_failure = any(
        item["affected_source_refs_total"] > 0
        and not item["path"].startswith("$.scopes[")
        for item in mismatches
    )
    if global_failure:
        affected.update(
            ref for scope in scopes for ref in scope.selected_source_refs
        )
    for index, scope in enumerate(scopes):
        if any(
            item["path"].startswith(f"$.scopes[{index}].")
            for item in mismatches
        ):
            affected.update(scope.selected_source_refs)
    return len(affected)


def _path(index: int, suffix: str) -> str:
    return f"$.scopes[{index}].{suffix}"


def _mismatch(
    mismatches: list[dict[str, Any]],
    *,
    path: str,
    failure_layer: str,
    classification: str,
    affected_source_refs_total: int,
    reason_code: str,
    literal_loss_total: int = 0,
    terminal_ownership_gap_total: int = 0,
    blocking: bool = True,
) -> None:
    if failure_layer not in COMPARATOR_FAILURE_LAYERS:
        _fail("successor_comparator_failure_layer_invalid")
    if classification not in COMPARATOR_CLASSIFICATIONS:
        _fail("successor_comparator_classification_invalid")
    mismatches.append(
        {
            "path": path,
            "failure_layer": failure_layer,
            "classification": classification,
            "reason_code": reason_code,
            "affected_source_refs_total": affected_source_refs_total,
            "literal_loss_total": literal_loss_total,
            "terminal_ownership_gap_total": (
                terminal_ownership_gap_total
            ),
            "blocking": blocking,
        }
    )


def _validate_value_free_receipt(
    *,
    receipt: dict[str, Any],
    scopes: tuple[Gate2DeterministicFinancialScope, ...],
) -> None:
    encoded = json.dumps(
        receipt,
        ensure_ascii=False,
        sort_keys=True,
    )
    private_tokens = {
        token
        for scope in scopes
        for token in (
            scope.source_package.package_ref,
            scope.source_package.source_scope_ref,
            scope.source_package.document_ref,
            *scope.selected_source_refs,
            *(
                value.source_value_ref
                for value in scope.source_package.source_values
            ),
            *(
                value.literal_value
                for value in scope.source_package.source_values
            ),
        )
        if isinstance(token, str) and len(token) >= 8
    }
    if any(token in encoded for token in private_tokens):
        _fail("successor_comparator_receipt_not_value_free")
    if receipt.get("schema_version") != SUCCESSOR_COMPARATOR_SCHEMA_VERSION:
        _fail("successor_comparator_receipt_schema_invalid")
    payload = copy.deepcopy(receipt)
    integrity_hash = payload.pop("integrity_hash", None)
    if integrity_hash != sha256_json(payload):
        _fail("successor_comparator_receipt_integrity_invalid")
    if any(
        item.get("path") not in receipt.get("mismatch_paths", [])
        for item in receipt.get("mismatches", [])
    ):
        _fail("successor_comparator_mismatch_path_missing")


def _fail(code: str) -> None:
    raise Gate2SuccessorProductComparatorError(code)
