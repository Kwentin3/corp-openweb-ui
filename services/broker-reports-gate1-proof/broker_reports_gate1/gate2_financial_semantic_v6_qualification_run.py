from __future__ import annotations

import copy
import json
import re
import time
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from .gate2_financial_context import Gate2FinancialContextProjectionFactory
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_semantic_v6_evidence import (
    V6_SEMANTIC_SYSTEM_PROMPT,
    Gate2FinancialSemanticV6DecisionEvidenceFactory,
    financial_semantic_v6_canonical_request,
)
from .gate2_financial_semantic_v6_execution_identity import (
    V6_EXACT_MODEL_ID,
    V6_PROVIDER_PROFILE_ID,
    V6_QUALIFICATION_REQUEST_PROFILE,
    Gate2FinancialSemanticV6CapturedExecution,
    Gate2FinancialSemanticV6ExecutionIdentity,
    Gate2FinancialSemanticV6ExecutionIdentityFactory,
    financial_semantic_v6_response_format,
)
from .gate2_financial_semantic_v6_qualification import (
    SEMANTIC_CASES_TOTAL,
    TECHNICAL_CASES_TOTAL,
    V6_QUALIFICATION_POLICY_VERSION,
    V6_QUALIFICATION_SCHEMA_VERSION,
    Gate2FinancialSemanticV6QualificationCase,
    Gate2FinancialSemanticV6QualificationFixture,
    _fail,
    _semantic_authorities,
)
from .gate2_model_contracts import (
    Gate2StructuredModelClient,
    Gate2StructuredModelResult,
)
V6_QUALIFICATION_RUN_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_qualification_run_v1"
)
V6_PRIVATE_FAILURE_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_private_failure_evidence_v1"
)
V6_SAFE_FAILURE_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_safe_failure_receipt_v1"
)
FACTORY_REQUIRED = (
    "qualify_financial_semantic_v6 is the only terminal V6 qualification "
    "execution and product-gate evaluation entrypoint"
)
FORBIDDEN = (
    "The V6 runner must not call technical cases, retry, repair, fallback, "
    "write production state or place exact private evidence in a safe receipt"
)

_SAFE_CODE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,199}$")


async def qualify_financial_semantic_v6(
    *,
    fixture: Gate2FinancialSemanticV6QualificationFixture,
    model_client: Gate2StructuredModelClient,
    exact_identity: dict[str, Any],
    private_case_checkpoint: Callable[[str, dict[str, Any]], None],
    safe_checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    _validate_exact_identity(exact_identity)

    case_receipts: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    source_packages: list[Any] = []
    provider_calls = 0
    private_evidence_cases = 0
    input_tokens = 0
    output_tokens = 0
    actual_cost = Decimal("0")
    latency_ms_total = 0
    latency_ms_max = 0
    unsafe_typed = 0
    unclassified_value_loss = 0
    invalid_options = 0
    wrong_type = 0
    canonical_failures = 0
    materialization_failures = 0

    def current(*, terminal: bool) -> dict[str, Any]:
        return _qualification_receipt(
            fixture=fixture,
            exact_identity=exact_identity,
            case_receipts=case_receipts,
            artifacts=artifacts,
            source_packages=source_packages,
            provider_calls=provider_calls,
            private_evidence_cases=private_evidence_cases,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost=actual_cost,
            latency_ms_total=latency_ms_total,
            latency_ms_max=latency_ms_max,
            unsafe_typed=unsafe_typed,
            unclassified_value_loss=unclassified_value_loss,
            invalid_options=invalid_options,
            wrong_type=wrong_type,
            canonical_failures=canonical_failures,
            materialization_failures=materialization_failures,
            terminal=terminal,
        )

    if safe_checkpoint is not None:
        safe_checkpoint(current(terminal=False))

    for case in fixture.cases:
        execution_ref = f"execution:v6-qualification:{case.case_id}"
        validation_ref = f"validation:v6-qualification:{case.case_id}"
        if case.route == "technical_preclose":
            model_output = copy.deepcopy(case.expected_model_choice)
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
                "provider_calls_total": 0,
                "canonical_validation_ran": True,
                "exact_evidence_preserved": True,
            }
        else:
            (
                evidence_bundle,
                compilation,
                packet,
                choice_contract,
            ) = _semantic_authorities(case)
            canonical_request = financial_semantic_v6_canonical_request(
                packet=packet,
                choice_contract=choice_contract,
            )
            response_format = financial_semantic_v6_response_format(
                choice_contract
            )
            provider_calls += 1
            started = time.perf_counter()
            result: Gate2StructuredModelResult | None = None
            model_output: Any = None
            execution_identity: Gate2FinancialSemanticV6ExecutionIdentity | None = (
                None
            )
            try:
                result = await model_client.extract(
                    prompt=V6_SEMANTIC_SYSTEM_PROMPT,
                    package=packet.payload,
                    model_id=V6_EXACT_MODEL_ID,
                    response_format=response_format,
                )
                model_output = copy.deepcopy(result.content)
                _validate_provider_result(result)
                budget = _required_budget(result)
                capture = Gate2FinancialSemanticV6CapturedExecution(
                    request_profile=V6_QUALIFICATION_REQUEST_PROFILE,
                    response_format_hash=sha256_json(response_format),
                    execution_metadata=result.execution_metadata,
                    actual_cost_usd=str(budget["actual_cost_usd"]),
                )
                execution_identity = (
                    Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
                        capture=capture,
                        choice_contract=choice_contract,
                    )
                )
                evidence = Gate2FinancialSemanticV6DecisionEvidenceFactory(
                    registry=fixture.registry
                ).create(
                    case_id=case.case_id,
                    canonical_request=canonical_request,
                    model_output=model_output,
                    execution_capture=capture,
                    execution_identity=execution_identity,
                    choice_contract=choice_contract,
                    packet=packet,
                    evidence_bundle=evidence_bundle,
                    source_package=case.scope.source_package,
                    compilation=compilation,
                )
                private_case_checkpoint(case.case_id, evidence.private_evidence)
                private_evidence_cases += 1

                safe = evidence.safe_receipt
                normalized_choice = evidence.private_evidence[
                    "normalized_semantic_choice"
                ]
                observed_disposition = normalized_choice["disposition"]
                observed_type = _observed_input_type(
                    normalized_choice=normalized_choice,
                    case=case,
                )
                unsafe_typed += int(
                    observed_disposition == "typed_input"
                    and case.expected_disposition != "typed_input"
                )
                wrong_type += int(
                    observed_disposition == "typed_input"
                    and observed_type != case.expected_input_type_id
                )
                unclassified_value_loss += _unclassified_value_loss(
                    artifact=evidence.materialized_artifact,
                    expected_refs=set(evidence_bundle.retention_set),
                )
                artifact = evidence.materialized_artifact
                model_output = copy.deepcopy(
                    evidence.private_evidence["expanded_canonical_decision"][
                        "validated_decision"
                    ]["decision"]
                )
                receipt = {
                    "case_id": case.case_id,
                    "route": case.route,
                    "status": "passed",
                    "provider_calls_total": 1,
                    "canonical_validation_ran": True,
                    "exact_evidence_preserved": True,
                    "safe_decision_receipt": safe,
                }
            except Exception as exc:
                code = _failure_code(exc)
                available_output = (
                    model_output
                    if model_output is not None
                    else copy.deepcopy(getattr(exc, "raw_output", None))
                )
                canonical_failures += 1
                invalid_options += _invalid_choice_total(
                    model_output=available_output,
                    case=case,
                )
                materialization_failures += int("materialization" in code)
                elapsed_ms = _elapsed_ms(started)
                private_failure = _private_failure_evidence(
                    case_id=case.case_id,
                    canonical_request=canonical_request,
                    response_format=response_format,
                    model_output=available_output,
                    result=result,
                    execution_identity=execution_identity,
                    exception=exc,
                    failure_code=code,
                    elapsed_ms=elapsed_ms,
                )
                private_case_checkpoint(case.case_id, private_failure)
                private_evidence_cases += 1
                receipt = _safe_failure_receipt(
                    case_id=case.case_id,
                    route=case.route,
                    private_failure=private_failure,
                    failure_code=code,
                    provider_decision_returned=available_output is not None,
                )
            call_metrics = _provider_metrics(
                result=result,
                execution_identity=execution_identity,
                elapsed_ms=_elapsed_ms(started),
            )
            input_tokens += call_metrics["input_tokens"]
            output_tokens += call_metrics["output_tokens"]
            actual_cost += call_metrics["actual_cost"]
            latency_ms_total += call_metrics["latency_ms"]
            latency_ms_max = max(latency_ms_max, call_metrics["latency_ms"])

        case_receipts.append(receipt)
        if receipt["status"] == "passed":
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
    fixture: Gate2FinancialSemanticV6QualificationFixture,
    exact_identity: dict[str, Any],
    case_receipts: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    source_packages: list[Any],
    provider_calls: int,
    private_evidence_cases: int,
    input_tokens: int,
    output_tokens: int,
    actual_cost: Decimal,
    latency_ms_total: int,
    latency_ms_max: int,
    unsafe_typed: int,
    unclassified_value_loss: int,
    invalid_options: int,
    wrong_type: int,
    canonical_failures: int,
    materialization_failures: int,
    terminal: bool,
) -> dict[str, Any]:
    passed_case_ids = {
        item["case_id"] for item in case_receipts if item["status"] == "passed"
    }
    semantic_receipts = [
        item for item in case_receipts if item["route"] == "semantic_model"
    ]
    expected_typed = sum(
        item.expected_disposition == "typed_input"
        for item in fixture.semantic_cases
    )
    observed_typed = sum(
        (item.get("safe_decision_receipt") or {})
        .get("decision_classification", {})
        .get("disposition")
        == "typed_input"
        for item in semantic_receipts
    )
    exact_typed = observed_typed - wrong_type
    unclassified = sum(
        (item.get("safe_decision_receipt") or {})
        .get("decision_classification", {})
        .get("disposition")
        == "unclassified_financial_input"
        for item in semantic_receipts
    )

    product_invariants = _v6_product_invariants(
        fixture=fixture,
        artifacts=artifacts,
        source_packages=source_packages,
        passed_case_ids=passed_case_ids,
        terminal=terminal,
    )
    comparator_metrics = product_invariants["metrics"]

    hard_gates = {
        "unsafe_typed_total": unsafe_typed,
        "unclassified_value_loss_total": unclassified_value_loss,
        "inventions_total": comparator_metrics["invented_values_total"],
        "invalid_options_total": invalid_options,
        "wrong_type_total": wrong_type,
        "canonical_failures_total": canonical_failures,
        "materialization_failures_total": materialization_failures,
        "ownership_gaps_total": comparator_metrics["terminal_ownership_gap_total"],
        "duplicate_bindings_total": comparator_metrics["duplicate_bindings_total"],
        "cross_scope_bindings_total": comparator_metrics[
            "cross_scope_bindings_total"
        ],
    }
    quality = {
        "typed_precision_basis_points": _rate(exact_typed, observed_typed),
        "typed_recall_basis_points": _rate(exact_typed, expected_typed),
        "typed_expected_total": expected_typed,
        "typed_observed_total": observed_typed,
        "typed_exact_total": exact_typed,
        "unclassified_total": unclassified,
        "unclassified_rate_basis_points": _rate(
            unclassified,
            SEMANTIC_CASES_TOTAL,
        ),
    }
    terminal_complete = (
        terminal
        and len(case_receipts) == len(fixture.cases)
        and provider_calls == SEMANTIC_CASES_TOTAL
        and private_evidence_cases == SEMANTIC_CASES_TOTAL
    )
    safe_for_shadow = (
        terminal_complete
        and all(item["status"] == "passed" for item in case_receipts)
        and all(value == 0 for value in hard_gates.values())
        and product_invariants["status"] == "passed"
        and quality["typed_precision_basis_points"] == 10_000
        and quality["typed_recall_basis_points"] == 10_000
    )
    product_gate = (
        "MODEL_SAFE_FOR_SHADOW"
        if safe_for_shadow
        else "MODEL_NOT_SAFE_FOR_SHADOW"
        if terminal_complete
        else None
    )
    exact_evidence_preserved = (
        private_evidence_cases == provider_calls
        and all(
            item.get("exact_evidence_preserved") is True
            for item in case_receipts
        )
    )
    receipt: dict[str, Any] = {
        "schema_version": V6_QUALIFICATION_RUN_SCHEMA_VERSION,
        "harness_schema_version": V6_QUALIFICATION_SCHEMA_VERSION,
        "policy_version": V6_QUALIFICATION_POLICY_VERSION,
        "execution_state": "terminal" if terminal else "in_progress",
        "status": (
            "passed"
            if product_gate == "MODEL_SAFE_FOR_SHADOW"
            else "failed"
            if terminal
            else "in_progress"
        ),
        "product_gate": product_gate,
        "acceptance": {
            "provider_attempts": "EXACTLY_ONE",
            "hidden_retry": "ZERO",
            "exact_evidence": (
                "PRESERVED" if exact_evidence_preserved else "IN_PROGRESS"
            ),
            "product_gate": product_gate,
        },
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
        "quality": quality,
        "provider_metrics": {
            "input_tokens_total": input_tokens,
            "output_tokens_total": output_tokens,
            "actual_cost_usd": format(actual_cost, "f"),
            "latency_total_ms": latency_ms_total,
            "latency_average_ms": (
                latency_ms_total // provider_calls if provider_calls else 0
            ),
            "latency_max_ms": latency_ms_max,
        },
        "cases_total": len(fixture.cases),
        "cases_executed": len(case_receipts),
        "cases_passed": sum(
            item["status"] == "passed" for item in case_receipts
        ),
        "cases_failed": sum(
            item["status"] == "failed" for item in case_receipts
        ),
        "private_evidence_cases_total": private_evidence_cases,
        "case_receipts": copy.deepcopy(case_receipts),
        "product_comparator": copy.deepcopy(product_invariants),
        "exact_evidence_preserved": exact_evidence_preserved,
        "raw_private_data_in_receipt": False,
        "production_admissions_total": 0,
    }
    receipt["integrity_sha256"] = sha256_json(receipt)
    return receipt


def _v6_product_invariants(
    *,
    fixture: Gate2FinancialSemanticV6QualificationFixture,
    artifacts: list[dict[str, Any]],
    source_packages: list[Any],
    passed_case_ids: set[str],
    terminal: bool,
) -> dict[str, Any]:
    metrics = {
        "invented_values_total": 0,
        "duplicate_bindings_total": 0,
        "cross_scope_bindings_total": 0,
        "terminal_ownership_gap_total": sum(
            len(case.scope.source_package.source_values)
            for case in fixture.cases
            if case.case_id not in passed_case_ids
        ),
        "literal_loss_total": 0,
    }
    owners: dict[str, set[str]] = {}
    for case in fixture.cases:
        package = case.scope.source_package
        for value in package.source_values:
            owners.setdefault(value.source_value_ref, set()).add(
                package.source_scope_ref
            )
    for artifact, package in zip(
        artifacts,
        source_packages,
        strict=True,
    ):
        disposition = artifact["terminal_disposition"]
        if disposition in {"no_financial_input", "unsupported"}:
            continue
        terminals = (
            artifact["typed_inputs"]
            if disposition == "typed_input"
            else artifact["unclassified_inputs"]
        )
        if len(terminals) != 1:
            metrics["terminal_ownership_gap_total"] += 1
            continue
        terminal_item = terminals[0]
        observed_refs = [
            item["source_value_ref"]
            for item in terminal_item["source_values"]
        ]
        expected_refs = {
            item.source_value_ref for item in package.source_values
        }
        metrics["invented_values_total"] += len(
            set(observed_refs) - expected_refs
        )
        metrics["duplicate_bindings_total"] += len(observed_refs) - len(
            set(observed_refs)
        )
        metrics["cross_scope_bindings_total"] += sum(
            owners.get(ref) != {package.source_scope_ref}
            for ref in observed_refs
        )
        if disposition == "unclassified_financial_input":
            metrics["literal_loss_total"] += len(
                expected_refs - set(observed_refs)
            )
        if terminal_item["source_ownership"] != {
            "normalization_run_ref": package.normalization_run_ref,
            "document_ref": package.document_ref,
            "source_package_ref": package.package_ref,
            "source_scope_ref": package.source_scope_ref,
        }:
            metrics["terminal_ownership_gap_total"] += len(observed_refs)

    context_hash = None
    context_exact = False
    if terminal and len(artifacts) == len(fixture.cases):
        context = Gate2FinancialContextProjectionFactory(
            registry=fixture.registry
        ).create(
            materialized_artifacts=artifacts,
            source_packages=source_packages,
        )
        context_hash = sha256_json(context)
        context_exact = True
    checks = {
        "exact_package_ref_membership": (
            metrics["invented_values_total"] == 0
        ),
        "invented_values_zero": metrics["invented_values_total"] == 0,
        "duplicate_bindings_zero": (
            metrics["duplicate_bindings_total"] == 0
        ),
        "cross_scope_bindings_zero": (
            metrics["cross_scope_bindings_total"] == 0
        ),
        "terminal_ownership_complete": (
            metrics["terminal_ownership_gap_total"] == 0
        ),
        "unclassified_value_preservation": (
            metrics["literal_loss_total"] == 0
        ),
        "final_context_integrity_exact": context_exact,
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "metrics": metrics,
        "final_context_hash": context_hash,
    }


def _validate_exact_identity(exact_identity: dict[str, Any]) -> None:
    material = {
        key: value for key, value in exact_identity.items() if key != "identity_hash"
    }
    attempt = exact_identity.get("attempt_policy") or {}
    model_provider = exact_identity.get("model_provider") or {}
    if (
        exact_identity.get("identity_hash") != sha256_json(material)
        or model_provider.get("exact_model_id") != V6_EXACT_MODEL_ID
        or model_provider.get("provider_profile_id") != V6_PROVIDER_PROFILE_ID
        or model_provider.get("request_profile")
        != V6_QUALIFICATION_REQUEST_PROFILE
        or attempt.get("full_scope_attempts_total") != 1
        or attempt.get("semantic_provider_calls_total") != SEMANTIC_CASES_TOTAL
        or attempt.get("technical_provider_calls_total") != 0
        or attempt.get("fallback_total") != 0
        or attempt.get("repair_total") != 0
        or attempt.get("hidden_retry_total") != 0
    ):
        _fail("financial_semantic_v6_qualification_identity_invalid")


def _validate_provider_result(result: Gate2StructuredModelResult) -> None:
    if (
        not isinstance(result, Gate2StructuredModelResult)
        or result.execution_metadata is None
        or result.fallback_used is not False
        or result.repair_attempt_count != 0
    ):
        _fail("financial_semantic_v6_provider_result_invalid")


def _required_budget(result: Gate2StructuredModelResult) -> dict[str, Any]:
    budget = result.economy_budget_receipt
    if not isinstance(budget, dict) or budget.get("status") != "passed":
        _fail("financial_semantic_v6_qualification_budget_missing")
    try:
        Decimal(str(budget["actual_cost_usd"]))
        int(budget["input_tokens"])
        int(budget["output_tokens"])
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError(
            "financial_semantic_v6_qualification_budget_invalid"
        ) from exc
    return budget


def _observed_input_type(
    *,
    normalized_choice: dict[str, Any],
    case: Gate2FinancialSemanticV6QualificationCase,
) -> str | None:
    if normalized_choice.get("disposition") != "typed_input":
        return None
    _, compilation, _, _ = _semantic_authorities(case)
    option_id = normalized_choice.get("typed_option_id")
    matches = [
        item.input_type_id
        for item in compilation.typed_options
        if item.typed_option_id == option_id
    ]
    return matches[0] if len(matches) == 1 else None


def _unclassified_value_loss(
    *,
    artifact: dict[str, Any],
    expected_refs: set[str],
) -> int:
    if artifact.get("terminal_disposition") != "unclassified_financial_input":
        return 0
    inputs = artifact.get("unclassified_inputs") or []
    if len(inputs) != 1:
        return len(expected_refs)
    retained = {
        item.get("source_value_ref")
        for item in inputs[0].get("source_values") or []
        if isinstance(item, dict)
    }
    return len(expected_refs - retained)


def _invalid_choice_total(
    *,
    model_output: Any,
    case: Gate2FinancialSemanticV6QualificationCase,
) -> int:
    _, _, _, contract = _semantic_authorities(case)
    payload = model_output
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return 1
    if not isinstance(payload, dict):
        return 1
    disposition = payload.get("disposition")
    if disposition == "typed_input":
        return int(
            set(payload) != {"disposition", "typed_option_id"}
            or payload.get("typed_option_id") not in contract.typed_option_ids
        )
    if disposition == "unclassified_financial_input":
        return int(
            set(payload) != {"disposition", "reason_code"}
            or payload.get("reason_code") not in contract.unclassified_reason_codes
        )
    return 1


def _private_failure_evidence(
    *,
    case_id: str,
    canonical_request: dict[str, Any],
    response_format: dict[str, Any],
    model_output: Any,
    result: Gate2StructuredModelResult | None,
    execution_identity: Gate2FinancialSemanticV6ExecutionIdentity | None,
    exception: Exception,
    failure_code: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    exception_metadata = getattr(exception, "execution_metadata", None)
    provider_metadata = (
        result.execution_metadata
        if result is not None and result.execution_metadata is not None
        else exception_metadata
    )
    material = {
        "schema_version": V6_PRIVATE_FAILURE_EVIDENCE_SCHEMA_VERSION,
        "case_id": case_id,
        "exact_canonical_request_object": copy.deepcopy(canonical_request),
        "canonical_request_hash": sha256_json(canonical_request),
        "response_format_hash": sha256_json(response_format),
        "exact_model_output": copy.deepcopy(model_output),
        "model_output_hash": sha256_json(model_output),
        "provider_execution_identity": (
            execution_identity.to_private_dict()
            if execution_identity is not None
            else None
        ),
        "provider_execution_metadata": (
            asdict(provider_metadata)
            if provider_metadata is not None
            else None
        ),
        "economy_budget_receipt": (
            copy.deepcopy(result.economy_budget_receipt)
            if result is not None
            else None
        ),
        "failure_code": failure_code,
        "failure_class": getattr(exception, "failure_class", None),
        "elapsed_ms": elapsed_ms,
        "exact_available_evidence_preserved": True,
        "raw_provider_transport_preserved": False,
    }
    return {**material, "private_evidence_hash": sha256_json(material)}


def _safe_failure_receipt(
    *,
    case_id: str,
    route: str,
    private_failure: dict[str, Any],
    failure_code: str,
    provider_decision_returned: bool,
) -> dict[str, Any]:
    material = {
        "schema_version": V6_SAFE_FAILURE_RECEIPT_SCHEMA_VERSION,
        "case_id": case_id,
        "route": route,
        "status": "failed",
        "provider_calls_total": 1,
        "failure_code": failure_code,
        "provider_decision_returned": provider_decision_returned,
        "canonical_validation_ran": False,
        "exact_evidence_preserved": True,
        "hashes": {
            "private_evidence_hash": private_failure["private_evidence_hash"],
            "canonical_request_hash": private_failure["canonical_request_hash"],
            "response_format_hash": private_failure["response_format_hash"],
            "model_output_hash": private_failure["model_output_hash"],
        },
        "raw_private_data_in_receipt": False,
    }
    return {**material, "receipt_hash": sha256_json(material)}


def _provider_metrics(
    *,
    result: Gate2StructuredModelResult | None,
    execution_identity: Gate2FinancialSemanticV6ExecutionIdentity | None,
    elapsed_ms: int,
) -> dict[str, Any]:
    if execution_identity is not None:
        return {
            "input_tokens": execution_identity.input_tokens,
            "output_tokens": execution_identity.output_tokens,
            "actual_cost": Decimal(execution_identity.actual_cost_usd),
            "latency_ms": execution_identity.duration_ms,
        }
    budget = (
        result.economy_budget_receipt
        if result is not None and isinstance(result.economy_budget_receipt, dict)
        else {}
    )
    metadata = result.execution_metadata if result is not None else None
    return {
        "input_tokens": _safe_nonnegative_int(budget.get("input_tokens")),
        "output_tokens": _safe_nonnegative_int(budget.get("output_tokens")),
        "actual_cost": _safe_decimal(budget.get("actual_cost_usd")),
        "latency_ms": (
            metadata.duration_ms
            if metadata is not None
            and isinstance(metadata.duration_ms, int)
            and metadata.duration_ms >= 0
            else elapsed_ms
        ),
    }


def _safe_nonnegative_int(value: Any) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return 0
    return normalized if normalized >= 0 else 0


def _safe_decimal(value: Any) -> Decimal:
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")
    return normalized if normalized >= 0 else Decimal("0")


def _failure_code(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and _SAFE_CODE_RE.fullmatch(code):
        return code
    text = str(exc)
    if _SAFE_CODE_RE.fullmatch(text):
        return text
    return exc.__class__.__name__


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))


def _rate(numerator: int, denominator: int) -> int:
    return 0 if denominator == 0 else numerator * 10_000 // denominator
