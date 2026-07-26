from __future__ import annotations

import copy
import time
from decimal import Decimal
from typing import Any, Callable

from .gate2_financial_context import Gate2FinancialContextProjectionFactory
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_semantic_v5_evidence import (
    Gate2FinancialSemanticV5DecisionEvidenceFactory,
    Gate2FinancialSemanticV5ProviderCallReceipt,
)
from .gate2_financial_semantic_v5_contract import (
    Gate2FinancialSemanticV5ModelContract,
)
from .gate2_financial_semantic_v5_qualification import (
    EXACT_MODEL_ID,
    PROVIDER_PROFILE_ID,
    SEMANTIC_CASES_TOTAL,
    TECHNICAL_CASES_TOTAL,
    V5_QUALIFICATION_POLICY_VERSION,
    V5_QUALIFICATION_SCHEMA_VERSION,
    Gate2FinancialSemanticV5QualificationCase,
    Gate2FinancialSemanticV5QualificationFixture,
    _fail,
    _request,
    _semantic_authorities,
)
from .gate2_model_contracts import (
    Gate2StructuredModelClient,
    gate2_provider_execution_safe_metadata,
)
from .gate2_successor_product_comparator import (
    Gate2SuccessorProductComparatorFactory,
    Gate2SuccessorProductExpectation,
    Gate2SuccessorScopeObservation,
)


FACTORY_REQUIRED = (
    "qualify_financial_semantic_v5 is the only terminal V5 qualification "
    "execution and product-gate evaluation entrypoint"
)
FORBIDDEN = (
    "The V5 runner must not call technical cases, retry, repair, fallback, "
    "write production state or place exact private evidence in a safe receipt"
)


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
            artifact = (
                Gate2FinancialEvidenceMaterializerFactory(
                    registry=fixture.registry,
                    source_package=case.scope.source_package,
                    execution_metadata=FinancialEvidenceExecutionMetadata(
                        execution_ref=execution_ref,
                        decision_validation_ref=validation_ref,
                    ),
                )
                .create()
                .materialize(validated_decision=validated)
            )
            receipt = {
                "case_id": case.case_id,
                "route": case.route,
                "status": "passed",
                "expected_disposition": case.expected_disposition,
                "observed_disposition": (validated.decision.disposition),
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
                elapsed_ms = int(round((time.perf_counter() - started) * 1000))
                model_output = copy.deepcopy(result.content)
                _validate_provider_result(
                    result=result,
                    model_contract=model_contract,
                )
                budget = result.economy_budget_receipt
                if not isinstance(budget, dict) or budget.get("status") != "passed":
                    _fail("financial_semantic_v5_qualification_budget_missing")
                call_input = int(budget["input_tokens"])
                call_output = int(budget["output_tokens"])
                call_cost = Decimal(str(budget["actual_cost_usd"]))
                metadata = result.execution_metadata
                call_latency = int(
                    metadata.duration_ms
                    if metadata is not None and metadata.duration_ms is not None
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
                evidence = Gate2FinancialSemanticV5DecisionEvidenceFactory().create(
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
                    and observed_disposition == "unclassified_financial_input"
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
                elapsed_ms = int(round((time.perf_counter() - started) * 1000))
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
                    "failure_code": str(getattr(exc, "code", exc.__class__.__name__)),
                    "canonical_validation_ran": False,
                    "provider_decision_returned": (model_output is not None),
                    "exact_decision_preserved": (model_output is not None),
                }
                continue_after_failure = True
                if result is not None and isinstance(
                    result.economy_budget_receipt, dict
                ):
                    budget = result.economy_budget_receipt
                    input_tokens += int(budget.get("input_tokens") or 0)
                    output_tokens += int(budget.get("output_tokens") or 0)
                    actual_cost += Decimal(str(budget.get("actual_cost_usd") or "0"))
                latency_ms_total += elapsed_ms
                if not continue_after_failure:  # pragma: no cover
                    raise
        case_receipts.append(receipt)
        if receipt["status"] == "passed":
            observations.append(
                Gate2SuccessorScopeObservation(
                    source_scope_ref=(case.scope.source_package.source_scope_ref),
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
        item.get("observed_disposition") == "typed_input" for item in case_receipts
    )
    expected_typed = sum(
        item.expected_disposition == "typed_input" for item in fixture.cases
    )
    true_typed = sum(
        item.get("observed_disposition") == "typed_input"
        and item.get("observed_input_type_id") == item.get("expected_input_type_id")
        for item in case_receipts
    )
    unclassified = sum(
        item.get("observed_disposition") == "unclassified_financial_input"
        for item in case_receipts
    )
    comparator = None
    comparator_metrics = {
        "literal_loss_total": 0,
        "terminal_ownership_gap_total": sum(
            len(case.scope.selected_source_refs)
            for case in fixture.cases
            if case.case_id
            not in {
                item["case_id"] for item in case_receipts if item["status"] == "passed"
            }
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
        comparator = (
            Gate2SuccessorProductComparatorFactory(registry=fixture.registry)
            .create()
            .compare(
                authorized_scopes=(item.scope for item in fixture.cases),
                observations=observations,
                final_context=context,
            )
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
        "ownership_gaps_total": comparator_metrics["terminal_ownership_gap_total"],
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
            "typed_precision_basis_points": _rate(true_typed, observed_typed),
            "typed_recall_basis_points": _rate(true_typed, expected_typed),
            "safe_under_typed_total": safe_under_typed,
            "safe_under_typed_rate_basis_points": _rate(
                safe_under_typed, expected_typed
            ),
            "unclassified_total": unclassified,
            "unclassified_rate_basis_points": _rate(unclassified, SEMANTIC_CASES_TOTAL),
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
        or metadata.canonical_request_schema_hash != model_contract.response_format_hash
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
            owners.setdefault(candidate.source_value_ref, set()).add(scope_ref)
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
            (str(role), str(ref)) for role, ref in raw.items() if ref is not None
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
        and candidate_owners[ref] != {case.scope.source_package.source_scope_ref}
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
