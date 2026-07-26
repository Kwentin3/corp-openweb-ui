#!/usr/bin/env python3
"""Qualify exact Nano for the managed V4 Financial Domain shadow route."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_economy_qualification_policy import (  # noqa: E402
    Gate2EconomyQualificationContractIdentity,
    Gate2EconomyQualificationPolicyFactory,
)
from broker_reports_gate1.gate2_financial_domain_local_proof import (  # noqa: E402,E501
    Gate2FinancialDomainLocalProofFactory,
)
from broker_reports_gate1.gate2_financial_context import (  # noqa: E402
    Gate2FinancialContextProjectionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    DECISION_SCHEMA_VERSION,
    DISPOSITIONS,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402,E501
    MATERIALIZATION_POLICY_VERSION,
    VALIDATED_DECISION_SCHEMA_VERSION,
)
from broker_reports_gate1.gate2_financial_evidence_source_context import (  # noqa: E402,E501
    SOURCE_CONTEXT_POLICY_VERSION,
    SOURCE_CONTEXT_SCHEMA_VERSION,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (  # noqa: E402,E501
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4,
    SUCCESSOR_PROMPT_CONTRACT_ID_V4,
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorPromptFactory,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
)
from broker_reports_gate1.gate2_financial_evidence_successor_projection import (  # noqa: E402,E501
    SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION,
    SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION,
    Gate2FinancialEvidenceSuccessorProviderProjectionFactory,
)
from broker_reports_gate1.gate2_financial_semantic_model_assets import (  # noqa: E402,E501
    load_gate2_financial_semantic_model_assets,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    gate2_provider_execution_summary,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V3,
)
from broker_reports_gate1.gate2_successor_artifacts_v2 import (  # noqa: E402
    SUCCESSOR_ARTIFACT_POLICY_VERSION_V2,
)
from broker_reports_gate1.gate2_successor_product_comparator import (  # noqa: E402,E501
    SUCCESSOR_COMPARATOR_POLICY_VERSION,
    SUCCESSOR_COMPARATOR_SCHEMA_VERSION,
    Gate2SuccessorProductComparatorFactory,
    Gate2SuccessorProductExpectation,
    Gate2SuccessorScopeObservation,
)
from live_gate2_domain_economy_qualification import (  # noqa: E402
    write_safe_receipt_atomically,
)
from live_gate2_economy_contract_qualification import (  # noqa: E402
    _completion_boundary,
    _dry_build,
    _live_qualification_action,
    _model_client,
    _published_model_ids,
    _request_context,
    _safe_error,
)
from live_gate2_financial_successor_qualification import (  # noqa: E402
    _actual_model_output,
)
from live_gate2_financial_successor_qualification_v2 import (  # noqa: E402,E501
    DEFAULT_MANIFEST_PATH,
    EXACT_MODEL_ID,
    PROVIDER_PROFILE_ID,
    SuccessorQualificationFixtureV2,
    _SuccessfulCaseV2,
    build_successor_qualification_fixture_v2,
)
from live_gate2_synthetic_extraction_smoke import (  # noqa: E402
    _current_user,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
)


MANAGED_SHADOW_QUALIFICATION_SCHEMA_VERSION = (
    "broker_reports_gate2_managed_financial_domain_shadow_qualification_v1"
)
MANAGED_SHADOW_QUALIFICATION_POLICY_VERSION = (
    "gate2_managed_financial_domain_risk_based_shadow_qualification_v1"
)
MANAGED_SHADOW_RISK_POLICY_VERSION = (
    "gate2_financial_domain_shadow_safety_gates_v1"
)
_LOCAL_SNAPSHOT_AUTHORITY_KEY = (
    b"synthetic-goal10-local-snapshot-authority-key"
)
_LOCAL_CONTINUATION_KEY = b"synthetic-goal10-local-continuation-key"

FACTORY_REQUIRED = (
    "Gate2EconomyQualificationPolicyFactory, "
    "Gate2FinancialEvidenceSuccessorRunnerFactory and the canonical "
    "validator/materializer/comparator factories are the only Goal 10 "
    "authorization, execution and safety-proof entrypoints"
)
FORBIDDEN = (
    "Goal 10 must not use customer data, retry the exact V4 attempt, call "
    "vendors directly, use fallback, repair, paid tools or expensive models, "
    "activate production, or persist raw provider output"
)


class _NoCallClient:
    async def extract(self, **_kwargs):
        raise AssertionError(
            "managed_shadow_qualification_preflight_must_not_call_provider"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--model-id",
        choices=(EXACT_MODEL_ID,),
        default=EXACT_MODEL_ID,
    )
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--receipt-path",
        help=(
            "Required for the one live attempt. The path must not already "
            "exist and must be ignored by Git."
        ),
    )
    args = parser.parse_args()
    if not args.preflight_only and not args.receipt_path:
        parser.error("--receipt-path is required for live execution")
    receipt_path = (
        Path(args.receipt_path).resolve() if args.receipt_path else None
    )
    if (
        receipt_path is not None
        and (
            not receipt_path.name.endswith(".safe.json")
            or receipt_path.exists()
            or not receipt_path.is_relative_to(
                (SERVICE_ROOT / "local").resolve()
            )
        )
    ):
        parser.error(
            "--receipt-path must be a new .safe.json path under local/"
        )

    env = _read_env(Path(args.env_file))
    base_url = (
        args.base_url.rstrip("/") if args.base_url else _base_url(env)
    )
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    live_action = _live_qualification_action(session, base_url)
    published = _published_model_ids(session, base_url)
    if args.model_id not in published:
        print(
            json.dumps(
                {
                    "schema_version": (
                        MANAGED_SHADOW_QUALIFICATION_SCHEMA_VERSION
                    ),
                    "status": "blocked",
                    "failure_code": "stage_models_endpoint_model_absent",
                    "qualification_subject": _subject(),
                    "provider_calls": 0,
                    "customer_calls": 0,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    fixture = build_successor_qualification_fixture_v2()
    local_domain_proof = Gate2FinancialDomainLocalProofFactory(
        registry=fixture.registry,
        snapshot_authority_key=_LOCAL_SNAPSHOT_AUTHORITY_KEY,
        continuation_key=_LOCAL_CONTINUATION_KEY,
    ).create(
        manifest=json.loads(
            DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8")
        )
    )
    identity = managed_shadow_contract_identity(fixture=fixture)
    authorization = (
        Gate2EconomyQualificationPolicyFactory()
        .create()
        .authorize(
            workload_class="gate2_financial_evidence",
            exact_model_id=EXACT_MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
            receipt_identity=identity,
        )
    )
    preflight_cases = managed_shadow_preflight_cases(fixture=fixture)
    estimated_tokens = sum(
        int(item["schema_dry_build"]["estimated_input_tokens"])
        for item in preflight_cases
    )
    estimated_cost = sum(
        (
            Decimal(str(item["schema_dry_build"]["estimated_cost_usd"]))
            for item in preflight_cases
        ),
        Decimal("0"),
    )
    output: dict[str, Any] = {
        "schema_version": MANAGED_SHADOW_QUALIFICATION_SCHEMA_VERSION,
        "policy_version": MANAGED_SHADOW_QUALIFICATION_POLICY_VERSION,
        "risk_policy_version": MANAGED_SHADOW_RISK_POLICY_VERSION,
        "qualification_subject": _subject(),
        "attempt_policy": {
            "exact_v4_attempts_authorized": 1,
            "retry_authorized": False,
            "candidate_search_authorized": False,
            "previous_v3_terminal_receipt_transferred": False,
        },
        "boundary": {
            "synthetic_non_customer_only": True,
            "customer_calls": 0,
            "live_production_pipe_used": False,
            "direct_vendor_calls": False,
            "source_model_calls": 0,
            "domain_model_calls": 0,
            "free_json_used": False,
            "fallback_calls": 0,
            "repair_attempts": 0,
            "hidden_retry": 0,
            "paid_tools_used": 0,
            "expensive_model_calls": 0,
            "raw_provider_output_included": False,
        },
        "inventory": {
            "exact_model_published": True,
            "published_models_total": len(published),
            "qualification_action": live_action,
        },
        "qualification_authorization": authorization.safe_receipt(),
        "qualification_identity": _identity_summary(
            identity=identity,
            fixture=fixture,
            local_domain_proof=local_domain_proof,
        ),
        "fixture": {
            "benchmark_id": "gate2_financial_successor_v2",
            "manifest_file_sha256": fixture.manifest_file_sha256,
            "manifest_canonical_hash": fixture.manifest_canonical_hash,
            "contains_customer_data": False,
            "frozen": True,
            "cases_total": len(fixture.cases),
            "local_domain_proof": (
                local_domain_proof["acceptance"]["local_domain_proof"]
            ),
            "literal_loss": (
                local_domain_proof["acceptance"]["literal_loss"]
            ),
            "query_gaps": (
                local_domain_proof["acceptance"]["query_gaps"]
            ),
            "provider_calls": (
                local_domain_proof["acceptance"]["provider_calls"]
            ),
        },
        "preflight_cases": preflight_cases,
        "preflight_aggregate": {
            "provider_calls_if_executed": len(fixture.cases),
            "estimated_input_tokens_total": estimated_tokens,
            "estimated_maximum_cost_usd": format(estimated_cost, "f"),
            "maximum_output_tokens_per_call": max(
                int(item["schema_dry_build"]["maximum_output_tokens"])
                for item in preflight_cases
            ),
        },
    }
    if args.preflight_only:
        output.update(
            {
                "status": "passed",
                "preflight_only": True,
                "provider_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "actual_cost_usd": "0",
            }
        )
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    user = _current_user(session, base_url)
    client = _model_client(
        request_profile=(
            FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V3
        ),
        provider_profile_id=PROVIDER_PROFILE_ID,
        user_id=str(user["id"]),
        request_context=_request_context(session, base_url),
        completion=_completion_boundary(
            session=session,
            base_url=base_url,
            timeout=args.timeout,
        ),
    )
    assert receipt_path is not None

    def persist_execution(execution: dict[str, Any]) -> None:
        _apply_execution(output=output, execution=execution)
        output["receipt_checkpoint"] = {
            "state": execution["execution_state"],
            "cases_persisted": len(execution["qualification"]["cases"]),
            "atomic_write": True,
            "raw_provider_output_included": False,
        }
        write_safe_receipt_atomically(path=receipt_path, payload=output)

    execution = asyncio.run(
        qualify_managed_shadow_model(
            model_client=client,
            fixture=fixture,
            checkpoint=persist_execution,
        )
    )
    _apply_execution(output=output, execution=execution)
    write_safe_receipt_atomically(path=receipt_path, payload=output)
    aggregate = output["qualification"]["aggregate_metrics"]
    print(
        json.dumps(
            {
                "schema_version": (
                    MANAGED_SHADOW_QUALIFICATION_SCHEMA_VERSION
                ),
                "status": output["status"],
                "qualification_subject": output[
                    "qualification_subject"
                ],
                "provider_calls": output["provider_calls"],
                "input_tokens": output["input_tokens"],
                "output_tokens": output["output_tokens"],
                "actual_cost_usd": output["actual_cost_usd"],
                "unsafe_typed_total": aggregate["unsafe_typed_total"],
                "data_loss_total": aggregate["data_loss_total"],
                "typed_precision": aggregate["typed_precision"],
                "typed_recall": aggregate["typed_recall"],
                "safe_under_typing_total": aggregate[
                    "safe_under_typing_total"
                ],
                "latency_observed_attempts": aggregate[
                    "latency_observed_attempts"
                ],
                "latency_total_ms": aggregate["latency_total_ms"],
                "latency_average_ms": aggregate["latency_average_ms"],
                "latency_max_ms": aggregate["latency_max_ms"],
                "receipt_path": str(receipt_path),
                "receipt_sha256": hashlib.sha256(
                    receipt_path.read_bytes()
                ).hexdigest(),
                "raw_provider_output_included": False,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if output["status"] == "passed" else 1


def _runner(*, fixture, model_client):
    return Gate2FinancialEvidenceSuccessorRunnerFactory(
        registry=fixture.registry,
        model_client=model_client,
        config=Gate2FinancialEvidenceSuccessorConfig(
            model_id=EXACT_MODEL_ID,
            provider_profile_id=PROVIDER_PROFILE_ID,
            model_input_schema_version=(
                SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
            ),
            prompt_contract_id=SUCCESSOR_PROMPT_CONTRACT_ID_V4,
        ),
    ).create()


def managed_shadow_preflight_cases(
    *,
    fixture: SuccessorQualificationFixtureV2,
) -> list[dict[str, Any]]:
    runner = _runner(fixture=fixture, model_client=_NoCallClient())
    projection_factory = (
        Gate2FinancialEvidenceSuccessorProviderProjectionFactory()
    )
    return [
        {
            "case_id": case.case_id,
            "feature_families": list(case.features),
            "source_values_total": len(
                case.scope.source_package.source_values
            ),
            "eligible_registry_types_total": len(
                case.scope.decision_contract.eligible_type_ids
            ),
            "source_context_integrity_hash": (
                case.source_context.integrity_hash
            ),
            "model_input_hash": _sha256_json(
                runner.model_input(
                    scope=case.scope,
                    source_context=case.source_context,
                )
            ),
            "schema_dry_build": _dry_build(
                request_profile=(
                    FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V3
                ),
                provider_profile_id=PROVIDER_PROFILE_ID,
                model_id=EXACT_MODEL_ID,
                prompt=runner.prompt,
                package=runner.model_input(
                    scope=case.scope,
                    source_context=case.source_context,
                ),
                response_format=projection_factory.create(
                    contract=case.scope.decision_contract
                ).response_format,
            ),
        }
        for case in fixture.cases
    ]


async def qualify_managed_shadow_model(
    *,
    model_client,
    fixture: SuccessorQualificationFixtureV2,
    checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    runner = _runner(fixture=fixture, model_client=model_client)
    case_receipts: list[dict[str, Any]] = []
    successful: list[_SuccessfulCaseV2] = []
    input_tokens = 0
    output_tokens = 0
    actual_cost = Decimal("0")

    def current(*, terminal: bool) -> dict[str, Any]:
        return _execution_result(
            fixture=fixture,
            successful=successful,
            case_receipts=case_receipts,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost=actual_cost,
            terminal=terminal,
        )

    if checkpoint is not None:
        checkpoint(current(terminal=False))
    for case in fixture.cases:
        execution_ref = (
            f"execution:managed-shadow-qualification:{case.case_id}"
        )
        decision_validation_ref = (
            f"validation:managed-shadow-qualification:{case.case_id}"
        )
        try:
            result = await runner.run(
                scope=case.scope,
                source_context=case.source_context,
                execution_ref=execution_ref,
                decision_validation_ref=decision_validation_ref,
            )
            budget = result.economy_budget_receipt
            if (
                not isinstance(budget, dict)
                or budget.get("status") != "passed"
            ):
                raise ValueError(
                    "managed_shadow_budget_receipt_missing"
                )
            input_tokens += int(budget["input_tokens"])
            output_tokens += int(budget["output_tokens"])
            actual_cost += Decimal(str(budget["actual_cost_usd"]))
            actual = _actual_model_output(
                result=result,
                registry=fixture.registry,
            )
            observed_disposition = actual["decision"]["disposition"]
            observed_input_type_id = actual["decision"].get(
                "input_type_id"
            )
            risk = _case_risk(
                expected_disposition=case.expected_disposition,
                expected_input_type_id=case.expected_input_type_id,
                observed_disposition=observed_disposition,
                observed_input_type_id=observed_input_type_id,
            )
            summary = result.safe_summary
            checks = {
                "canonical_validation_passed": True,
                "deterministic_materialization_passed": True,
                "unsafe_typed_zero": risk["unsafe_typed"] is False,
                "data_loss_zero": risk["data_loss"] is False,
                "exact_model": (
                    result.provider_execution.get("requested_model_id")
                    == EXACT_MODEL_ID
                    and result.provider_execution.get(
                        "resolved_model_id"
                    )
                    == EXACT_MODEL_ID
                ),
                "strict_schema": (
                    result.provider_execution.get("response_format_type")
                    == "json_schema"
                    and result.provider_execution.get(
                        "response_format_schema_mode"
                    )
                    == "strict_json_schema"
                ),
                "model_input_v4": (
                    summary.get("model_input_schema_version")
                    == SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
                ),
                "managed_prompt_v4": (
                    summary.get("prompt_contract_id")
                    == SUCCESSOR_PROMPT_CONTRACT_ID_V4
                ),
                "fallback_zero": True,
                "repair_zero": True,
                "budget_receipt_passed": True,
            }
            case_receipts.append(
                {
                    "case_id": case.case_id,
                    "feature_families": list(case.features),
                    "status": (
                        "passed" if all(checks.values()) else "failed"
                    ),
                    "expected_disposition": case.expected_disposition,
                    "observed_disposition": observed_disposition,
                    "expected_input_type_id": (
                        case.expected_input_type_id
                    ),
                    "observed_input_type_id": observed_input_type_id,
                    "risk": risk,
                    "checks": checks,
                    "provider_execution": copy.deepcopy(
                        result.provider_execution
                    ),
                    "economy_budget_receipt": copy.deepcopy(budget),
                    "source_context_integrity_hash": (
                        case.source_context.integrity_hash
                    ),
                    "model_input_hash": result.model_input_hash,
                    "provider_response_format_hash": summary[
                        "provider_response_format_hash"
                    ],
                    "materialized_artifact_integrity_hash": (
                        result.materialized_artifact["integrity_hash"]
                    ),
                    "provider_generated_output": True,
                    "canonical_validation_ran": True,
                    "raw_provider_output_included": False,
                }
            )
            successful.append(
                _SuccessfulCaseV2(
                    case=case,
                    result=result,
                    actual_model_output=actual,
                    execution_ref=execution_ref,
                    decision_validation_ref=decision_validation_ref,
                )
            )
        except Exception as exc:
            safe_error = _safe_error(exc)
            budget = safe_error.get("economy_budget_receipt")
            if isinstance(budget, dict):
                input_tokens += int(budget.get("input_tokens") or 0)
                output_tokens += int(budget.get("output_tokens") or 0)
                actual_cost += Decimal(
                    str(budget.get("actual_cost_usd") or "0")
                )
            case_receipts.append(
                {
                    "case_id": case.case_id,
                    "feature_families": list(case.features),
                    "status": "failed",
                    "expected_disposition": case.expected_disposition,
                    "expected_input_type_id": (
                        case.expected_input_type_id
                    ),
                    **safe_error,
                    "provider_generated_output": bool(
                        safe_error.get("provider_execution")
                    ),
                    "canonical_validation_ran": False,
                    "fallback_used": False,
                    "repair_attempt_count": 0,
                    "raw_provider_output_included": False,
                }
            )
        if checkpoint is not None:
            checkpoint(current(terminal=False))
    terminal_result = current(terminal=True)
    if checkpoint is not None:
        checkpoint(terminal_result)
    return terminal_result


def _execution_result(
    *,
    fixture: SuccessorQualificationFixtureV2,
    successful: list[_SuccessfulCaseV2],
    case_receipts: list[dict[str, Any]],
    input_tokens: int,
    output_tokens: int,
    actual_cost: Decimal,
    terminal: bool,
) -> dict[str, Any]:
    disposition_counts = Counter(
        str(item.get("observed_disposition"))
        for item in case_receipts
        if item.get("observed_disposition") in DISPOSITIONS
    )
    safety_proof = None
    if terminal and len(successful) == len(fixture.cases):
        safety_proof = _terminal_safety_proof(
            fixture=fixture,
            successful=successful,
        )
    risks = [
        item["risk"] for item in case_receipts if "risk" in item
    ]
    expected_typed = sum(
        item["expected_typed"] for item in risks
    )
    observed_typed = sum(
        item["observed_typed"] for item in risks
    )
    correct_typed = sum(item["correct_typed"] for item in risks)
    unsafe_typed = sum(item["unsafe_typed"] for item in risks)
    data_loss = sum(item["data_loss"] for item in risks)
    safe_under_typing = sum(
        item["safe_under_typing"] for item in risks
    )
    exact_matches = sum(item["exact_match"] for item in risks)
    canonical_errors = sum(
        item.get("canonical_validation_ran") is not True
        for item in case_receipts
    )
    metrics = (
        {}
        if not isinstance(safety_proof, dict)
        else safety_proof["comparator"]["metrics"]
    )
    provider_summary = gate2_provider_execution_summary(case_receipts)
    latency_observed = int(
        provider_summary["latency_observed_attempts"]
    )
    latency_total = int(provider_summary["latency_total_ms"])
    aggregate = {
        "cases_total": len(fixture.cases),
        "cases_executed": len(case_receipts),
        "safety_cases_passed": sum(
            item.get("status") == "passed" for item in case_receipts
        ),
        "safety_cases_failed": sum(
            item.get("status") != "passed" for item in case_receipts
        ),
        "unsafe_typed_total": unsafe_typed,
        "data_loss_total": data_loss
        + int(metrics.get("literal_loss_total") or 0),
        "invented_values_total": int(
            metrics.get("invented_values_total") or 0
        ),
        "invalid_refs_total": 0 if canonical_errors == 0 else None,
        "wrong_roles_total": 0 if canonical_errors == 0 else None,
        "duplicate_bindings_total": int(
            metrics.get("duplicate_bindings_total") or 0
        ),
        "cross_scope_bindings_total": int(
            metrics.get("cross_scope_bindings_total") or 0
        ),
        "ownership_gaps_total": int(
            metrics.get("terminal_ownership_gap_total") or 0
        ),
        "canonical_materialization_errors_total": canonical_errors,
        "typed_expected_total": expected_typed,
        "typed_observed_total": observed_typed,
        "typed_correct_total": correct_typed,
        "typed_precision": _ratio(correct_typed, observed_typed),
        "typed_recall": _ratio(correct_typed, expected_typed),
        "safe_under_typing_total": safe_under_typing,
        "unclassified_total": disposition_counts[
            "unclassified_financial_input"
        ],
        "unclassified_rate": _ratio(
            disposition_counts["unclassified_financial_input"],
            len(fixture.cases),
        ),
        "exact_quality_matches_total": exact_matches,
        "exact_quality_match_rate": _ratio(
            exact_matches,
            len(fixture.cases),
        ),
        "latency_observed_attempts": latency_observed,
        "latency_total_ms": latency_total,
        "latency_average_ms": (
            round(latency_total / latency_observed, 3)
            if latency_observed
            else None
        ),
        "latency_max_ms": provider_summary["latency_max_ms"],
        "four_dispositions_observed": (
            set(disposition_counts) == set(DISPOSITIONS)
            and all(disposition_counts[item] > 0 for item in DISPOSITIONS)
        ),
        "terminal_disposition_counts": {
            item: disposition_counts[item] for item in DISPOSITIONS
        },
        "fallback_total": 0,
        "repair_attempts_total": 0,
        "source_model_calls_total": 0,
        "domain_model_calls_total": 0,
        "expensive_model_calls_total": 0,
    }
    hard_gates = {
        "unsafe_typed_zero": aggregate["unsafe_typed_total"] == 0,
        "data_loss_zero": aggregate["data_loss_total"] == 0,
        "inventions_zero": aggregate["invented_values_total"] == 0,
        "invalid_refs_zero": aggregate["invalid_refs_total"] == 0,
        "wrong_roles_zero": aggregate["wrong_roles_total"] == 0,
        "duplicate_cross_scope_zero": (
            aggregate["duplicate_bindings_total"] == 0
            and aggregate["cross_scope_bindings_total"] == 0
        ),
        "ownership_gaps_zero": aggregate["ownership_gaps_total"] == 0,
        "canonical_materialization_errors_zero": (
            aggregate["canonical_materialization_errors_total"] == 0
        ),
        "product_safety_proof_passed": (
            isinstance(safety_proof, dict)
            and safety_proof["status"] == "passed"
        ),
    }
    status = "in_progress"
    if terminal:
        status = "passed" if all(hard_gates.values()) else "failed"
    return {
        "execution_state": "terminal" if terminal else "in_progress",
        "status": status,
        "provider_calls": len(case_receipts),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "actual_cost_usd": format(actual_cost, "f"),
        "qualification": {
            "status": status,
            "model_safe_for_shadow": (
                "yes" if status == "passed" else "no"
            ),
            "hard_gates": hard_gates,
            "aggregate_metrics": aggregate,
            "cases": copy.deepcopy(case_receipts),
            "product_safety_proof": safety_proof,
            "fallback_used": False,
            "repair_attempt_count": 0,
            "raw_provider_output_included": False,
        },
    }


def _terminal_safety_proof(
    *,
    fixture: SuccessorQualificationFixtureV2,
    successful: list[_SuccessfulCaseV2],
) -> dict[str, Any]:
    context = Gate2FinancialContextProjectionFactory(
        registry=fixture.registry
    ).create(
        materialized_artifacts=(
            item.result.materialized_artifact for item in successful
        ),
        source_packages=(
            item.case.scope.source_package for item in successful
        ),
    )
    comparator = Gate2SuccessorProductComparatorFactory(
        registry=fixture.registry
    ).create().compare(
        authorized_scopes=(
            item.case.scope for item in successful
        ),
        observations=(
            Gate2SuccessorScopeObservation(
                source_scope_ref=(
                    item.case.scope.source_package.source_scope_ref
                ),
                model_output=item.actual_model_output,
                materialized_artifact=item.result.materialized_artifact,
                execution_ref=item.execution_ref,
                decision_validation_ref=item.decision_validation_ref,
                expectation=Gate2SuccessorProductExpectation(
                    expected_disposition=(
                        item.case.expected_disposition
                    ),
                    expected_input_type_id=(
                        item.case.expected_input_type_id
                    ),
                ),
            )
            for item in successful
        ),
        final_context=context,
    )
    comparator_checks = comparator["checks"]
    checks = {
        "eligible_dispositions": comparator_checks[
            "eligible_dispositions"
        ],
        "eligible_registry_types": comparator_checks[
            "eligible_registry_types"
        ],
        "exact_package_ref_membership": comparator_checks[
            "exact_package_ref_membership"
        ],
        "role_compatibility": comparator_checks[
            "role_compatibility"
        ],
        "literal_preservation": comparator_checks[
            "literal_preservation"
        ],
        "invented_values_zero": comparator_checks[
            "invented_values_zero"
        ],
        "duplicate_bindings_zero": comparator_checks[
            "duplicate_bindings_zero"
        ],
        "cross_scope_bindings_zero": comparator_checks[
            "cross_scope_bindings_zero"
        ],
        "terminal_ownership_complete": comparator_checks[
            "terminal_ownership_complete"
        ],
        "unclassified_value_preservation": comparator_checks[
            "unclassified_value_preservation"
        ],
        "deterministic_materialization_exact": comparator_checks[
            "deterministic_materialization_exact"
        ],
        "final_context_integrity_exact": comparator_checks[
            "final_context_integrity_exact"
        ],
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "quality_expectations_met": comparator_checks[
            "product_expectations_met"
        ],
        "comparator": copy.deepcopy(comparator),
        "financial_context_integrity_hash": context["integrity_hash"],
        "production_write_admitted": False,
        "private_source_context_stored": False,
        "raw_provider_output_included": False,
    }


def _case_risk(
    *,
    expected_disposition: str,
    expected_input_type_id: str | None,
    observed_disposition: str,
    observed_input_type_id: str | None,
) -> dict[str, bool]:
    expected_typed = expected_disposition == "typed_input"
    observed_typed = observed_disposition == "typed_input"
    correct_typed = (
        expected_typed
        and observed_typed
        and observed_input_type_id == expected_input_type_id
    )
    unsafe_typed = observed_typed and not correct_typed
    safe_under_typing = (
        expected_typed
        and observed_disposition == "unclassified_financial_input"
    )
    expected_financial = expected_disposition in {
        "typed_input",
        "unclassified_financial_input",
    }
    data_loss = (
        expected_financial
        and observed_disposition in {
            "no_financial_input",
            "unsupported",
        }
    )
    return {
        "expected_typed": expected_typed,
        "observed_typed": observed_typed,
        "correct_typed": correct_typed,
        "unsafe_typed": unsafe_typed,
        "safe_under_typing": safe_under_typing,
        "data_loss": data_loss,
        "exact_match": (
            expected_disposition == observed_disposition
            and expected_input_type_id == observed_input_type_id
        ),
    }


def managed_shadow_contract_identity(
    *,
    fixture: SuccessorQualificationFixtureV2,
) -> Gate2EconomyQualificationContractIdentity:
    profile = gate2_provider_profile(PROVIDER_PROFILE_ID)
    prompt = Gate2FinancialEvidenceSuccessorPromptFactory().create(
        prompt_contract_id=SUCCESSOR_PROMPT_CONTRACT_ID_V4
    )
    projections = [
        Gate2FinancialEvidenceSuccessorProviderProjectionFactory().create(
            contract=case.scope.decision_contract
        )
        for case in fixture.cases
    ]
    assets = load_gate2_financial_semantic_model_assets()
    provider_schema_hash = _sha256_json(
        [item.response_format_hash for item in projections]
    )
    context_hash = _sha256_json(
        [
            case.source_context.integrity_hash
            for case in fixture.cases
        ]
    )
    validator_revision = _sha256_files(
        (
            SERVICE_ROOT
            / "broker_reports_gate1"
            / "gate2_financial_evidence_successor.py",
            SERVICE_ROOT
            / "broker_reports_gate1"
            / "gate2_financial_evidence_decision.py",
            SERVICE_ROOT
            / "broker_reports_gate1"
            / "gate2_financial_evidence_materialization.py",
            SERVICE_ROOT
            / "broker_reports_gate1"
            / "gate2_successor_product_comparator.py",
            SERVICE_ROOT
            / "broker_reports_gate1"
            / "gate2_successor_artifacts_v2.py",
            SERVICE_ROOT
            / "broker_reports_gate1"
            / "gate2_financial_domain_risk_benchmark.py",
        )
    )
    return Gate2EconomyQualificationContractIdentity(
        provider_route_revision=gate2_provider_profile_revision(profile),
        input_contract_version=(
            "broker_reports_gate2_deterministic_financial_scope_package_v2:"
            f"{SOURCE_CONTEXT_SCHEMA_VERSION}:{context_hash}:"
            f"{SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4}:"
            f"{assets['semantic_pack']['integrity_sha256']}:"
            f"{assets['managed_assets']['manifest_sha256']}:"
            f"{fixture.manifest_canonical_hash}"
        ),
        output_contract_version=(
            f"{DECISION_SCHEMA_VERSION}:"
            f"{SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION}:"
            f"{provider_schema_hash}:"
            f"{MANAGED_SHADOW_RISK_POLICY_VERSION}"
        ),
        prompt_version=(
            f"{SUCCESSOR_PROMPT_CONTRACT_ID_V4}:{prompt.hash}"
        ),
        adapter_projection_revision=(
            f"{profile.adapter_id}:{profile.adapter_version}:"
            f"{gate2_provider_profile_revision(profile)}:"
            f"{SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION}"
        ),
        canonical_validator_revision=(
            f"{VALIDATED_DECISION_SCHEMA_VERSION}:"
            f"{MATERIALIZATION_POLICY_VERSION}:"
            f"{SUCCESSOR_COMPARATOR_SCHEMA_VERSION}:"
            f"{SUCCESSOR_COMPARATOR_POLICY_VERSION}:"
            f"{SUCCESSOR_ARTIFACT_POLICY_VERSION_V2}:"
            f"{validator_revision}"
        ),
    )


def _identity_summary(
    *,
    identity: Gate2EconomyQualificationContractIdentity,
    fixture: SuccessorQualificationFixtureV2,
    local_domain_proof: dict[str, Any],
) -> dict[str, Any]:
    assets = load_gate2_financial_semantic_model_assets()
    return {
        **identity.to_dict(),
        "exact_model_id": EXACT_MODEL_ID,
        "provider_profile_id": PROVIDER_PROFILE_ID,
        "source_context_schema": SOURCE_CONTEXT_SCHEMA_VERSION,
        "source_context_policy": SOURCE_CONTEXT_POLICY_VERSION,
        "successor_model_input_schema": (
            SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
        ),
        "successor_prompt_contract": SUCCESSOR_PROMPT_CONTRACT_ID_V4,
        "provider_projection_schema": (
            SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
        ),
        "semantic_pack_sha256": assets["semantic_pack"][
            "integrity_sha256"
        ],
        "managed_asset_manifest_sha256": assets["managed_assets"][
            "manifest_sha256"
        ],
        "fixture_manifest_canonical_hash": (
            fixture.manifest_canonical_hash
        ),
        "local_domain_proof_integrity_sha256": local_domain_proof[
            "integrity_sha256"
        ],
    }


def _subject() -> dict[str, str]:
    return {
        "exact_model_id": EXACT_MODEL_ID,
        "provider_profile_id": PROVIDER_PROFILE_ID,
        "workload_class": (
            "gate2_managed_financial_domain_shadow_v1"
        ),
        "model_input_schema_version": (
            SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V4
        ),
        "prompt_contract_id": SUCCESSOR_PROMPT_CONTRACT_ID_V4,
    }


def _apply_execution(
    *,
    output: dict[str, Any],
    execution: dict[str, Any],
) -> None:
    output["qualification"] = execution["qualification"]
    output["status"] = execution["status"]
    output["provider_calls"] = execution["provider_calls"]
    output["input_tokens"] = execution["input_tokens"]
    output["output_tokens"] = execution["output_tokens"]
    output["actual_cost_usd"] = execution["actual_cost_usd"]


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 6)


def _sha256_files(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
