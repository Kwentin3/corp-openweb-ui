#!/usr/bin/env python3
"""Qualify GPT-5.4 Nano on the frozen ambiguity-discipline v2 workload."""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.gate2_deterministic_financial_scopes import (  # noqa: E402
    DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2,
    Gate2DeterministicFinancialScope,
    Gate2DeterministicFinancialScopeFromGate1V2Factory,
)
from broker_reports_gate1.gate2_economy_qualification_policy import (  # noqa: E402
    Gate2EconomyQualificationContractIdentity,
    Gate2EconomyQualificationPolicyFactory,
)
from broker_reports_gate1.gate2_financial_context import (  # noqa: E402
    Gate2FinancialContextProjectionFactory,
)
from broker_reports_gate1.gate2_financial_evidence_decision import (  # noqa: E402
    DECISION_SCHEMA_VERSION,
    DISPOSITIONS,
)
from broker_reports_gate1.gate2_financial_evidence_materialization import (  # noqa: E402
    MATERIALIZATION_POLICY_VERSION,
    VALIDATED_DECISION_SCHEMA_VERSION,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (  # noqa: E402
    Gate2FinancialEvidenceRegistryFactory,
    Gate2FinancialEvidenceRegistrySnapshot,
)
from broker_reports_gate1.gate2_financial_evidence_source_context import (  # noqa: E402
    SOURCE_CONTEXT_POLICY_VERSION,
    SOURCE_CONTEXT_SCHEMA_VERSION,
    Gate2FinancialEvidenceSourceContext,
    Gate2FinancialEvidenceSourceContextFactory,
)
from broker_reports_gate1.gate2_financial_evidence_successor import (  # noqa: E402
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3,
    SUCCESSOR_PROMPT_CONTRACT_ID_V3,
    Gate2FinancialEvidenceSuccessorConfig,
    Gate2FinancialEvidenceSuccessorPromptFactory,
    Gate2FinancialEvidenceSuccessorResult,
    Gate2FinancialEvidenceSuccessorRunnerFactory,
)
from broker_reports_gate1.gate2_financial_evidence_successor_projection import (  # noqa: E402
    SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION,
    SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION,
    Gate2FinancialEvidenceSuccessorProviderProjectionFactory,
)
from broker_reports_gate1.gate2_model_contracts import (  # noqa: E402
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from broker_reports_gate1.gate2_model_requests import (  # noqa: E402
    FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V2,
)
from broker_reports_gate1.gate2_successor_artifacts_v2 import (  # noqa: E402
    SUCCESSOR_ARTIFACT_POLICY_VERSION_V2,
    Gate2SuccessorArtifactFamilyV2Factory,
    Gate2SuccessorArtifactV2Input,
)
from broker_reports_gate1.gate2_successor_compatibility import (  # noqa: E402
    SUCCESSOR_COMPATIBILITY_READER_POLICY_VERSION,
    Gate2SuccessorCompatibilityReaderFactory,
)
from broker_reports_gate1.gate2_successor_local_proof import (  # noqa: E402
    _fixture_package,
    _model_output,
)
from broker_reports_gate1.gate2_successor_local_proof_v2 import (  # noqa: E402
    LOCAL_PROOF_V2_MANIFEST_SCHEMA_VERSION,
    Gate2SuccessorLocalProofV2Factory,
)
from broker_reports_gate1.gate2_successor_product_comparator import (  # noqa: E402
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
from live_gate2_synthetic_extraction_smoke import (  # noqa: E402
    _current_user,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
)


FINANCIAL_SUCCESSOR_QUALIFICATION_SCHEMA_VERSION_V2 = (
    "broker_reports_gate2_financial_successor_qualification_v2"
)
FINANCIAL_SUCCESSOR_QUALIFICATION_POLICY_VERSION_V2 = (
    "gate2_financial_successor_exact_model_qualification_v2"
)
DEFAULT_MANIFEST_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "gate2_financial_successor_v2"
    / "manifest.json"
)
EXACT_MODEL_ID = "gpt-5.4-nano-2026-03-17"
PROVIDER_PROFILE_ID = "openai_gpt"
HAIKU_EXACT_MODEL_ID = "claude-haiku-4-5-20251001"
HAIKU_PROVIDER_PROFILE_ID = "anthropic_claude"
EXACT_CANDIDATE_PROVIDER_PROFILES = {
    EXACT_MODEL_ID: PROVIDER_PROFILE_ID,
    HAIKU_EXACT_MODEL_ID: HAIKU_PROVIDER_PROFILE_ID,
}

FACTORY_REQUIRED = (
    "Gate2EconomyQualificationPolicyFactory, "
    "Gate2FinancialEvidenceSuccessorRunnerFactory, "
    "Gate2SuccessorProductComparatorFactory and "
    "Gate2SuccessorArtifactFamilyV2Factory are the only authorization, live "
    "execution, product validation and artifact construction entrypoints"
)
FORBIDDEN = (
    "This v2 qualification harness must not use customer data, production "
    "routing, direct vendor calls, source/domain models, free JSON, retry, "
    "repair, fallback, paid tools, expensive models or raw provider output "
    "in its safe receipt"
)


@dataclass(frozen=True)
class SuccessorQualificationCaseV2:
    case_id: str
    features: tuple[str, ...]
    scope: Gate2DeterministicFinancialScope
    source_context: Gate2FinancialEvidenceSourceContext
    expected_model_output: dict[str, Any]
    expected_disposition: str
    expected_input_type_id: str | None


@dataclass(frozen=True)
class SuccessorQualificationFixtureV2:
    manifest_file_sha256: str
    manifest_canonical_hash: str
    local_proof_receipt: dict[str, Any]
    registry: Gate2FinancialEvidenceRegistrySnapshot
    cases: tuple[SuccessorQualificationCaseV2, ...]


@dataclass(frozen=True)
class _SuccessfulCaseV2:
    case: SuccessorQualificationCaseV2
    result: Gate2FinancialEvidenceSuccessorResult
    actual_model_output: dict[str, Any]
    execution_ref: str
    decision_validation_ref: str


class _NoCallClient:
    async def extract(self, **_kwargs):
        raise AssertionError("qualification_v2_preflight_must_not_call_provider")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--model-id",
        choices=tuple(EXACT_CANDIDATE_PROVIDER_PROFILES),
        default=EXACT_MODEL_ID,
    )
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument(
        "--receipt-path",
        help=(
            "Required for live execution. Atomically persists a safe "
            "checkpoint before calls and after every case."
        ),
    )
    args = parser.parse_args()
    if not args.preflight_only and not args.receipt_path:
        parser.error("--receipt-path is required for live execution")
    receipt_path = (
        Path(args.receipt_path).resolve() if args.receipt_path else None
    )
    if receipt_path is not None and not receipt_path.name.endswith(
        ".safe.json"
    ):
        parser.error("--receipt-path must end with .safe.json")

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
    provider_profile_id = _provider_profile_id(args.model_id)
    if args.model_id not in published:
        print(
            json.dumps(
                {
                    "schema_version": (
                        FINANCIAL_SUCCESSOR_QUALIFICATION_SCHEMA_VERSION_V2
                    ),
                    "status": "blocked",
                    "failure_code": "stage_models_endpoint_model_absent",
                    "qualification_subject": _subject(args.model_id),
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
    identity = successor_qualification_contract_identity_v2(
        fixture=fixture,
        model_id=args.model_id,
    )
    authorization = (
        Gate2EconomyQualificationPolicyFactory()
        .create()
        .authorize(
            workload_class="gate2_financial_evidence",
            exact_model_id=args.model_id,
            provider_profile_id=provider_profile_id,
            receipt_identity=identity,
        )
    )
    preflight_cases = successor_preflight_cases_v2(
        fixture=fixture,
        model_id=args.model_id,
    )
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
        "schema_version": (
            FINANCIAL_SUCCESSOR_QUALIFICATION_SCHEMA_VERSION_V2
        ),
        "policy_version": (
            FINANCIAL_SUCCESSOR_QUALIFICATION_POLICY_VERSION_V2
        ),
        "qualification_subject": _subject(args.model_id),
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
        "qualification_identity": _identity_summary_v2(
            identity=identity,
            fixture=fixture,
            model_id=args.model_id,
        ),
        "fixture": {
            "manifest_schema_version": (
                LOCAL_PROOF_V2_MANIFEST_SCHEMA_VERSION
            ),
            "manifest_file_sha256": fixture.manifest_file_sha256,
            "manifest_canonical_hash": fixture.manifest_canonical_hash,
            "contains_customer_data": False,
            "frozen": True,
            "cases_total": len(fixture.cases),
            "feature_families_total": len(
                {
                    feature
                    for case in fixture.cases
                    for feature in case.features
                }
            ),
            "local_q0_status": fixture.local_proof_receipt[
                "q0_contract_tests"
            ]["status"],
            "local_q1_status": fixture.local_proof_receipt[
                "q1_product_invariant_fixtures"
            ]["status"],
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
        print(
            json.dumps(
                output,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    user = _current_user(session, base_url)
    client = _model_client(
        request_profile=(
            FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V2
        ),
        provider_profile_id=provider_profile_id,
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
            "cases_persisted": len(
                execution["qualification"]["cases"]
            ),
            "atomic_write": True,
            "raw_provider_output_included": False,
        }
        write_safe_receipt_atomically(path=receipt_path, payload=output)

    execution = asyncio.run(
        qualify_successor_model_v2(
            model_client=client,
            model_id=args.model_id,
            fixture=fixture,
            checkpoint=persist_execution,
        )
    )
    _apply_execution(output=output, execution=execution)
    write_safe_receipt_atomically(path=receipt_path, payload=output)
    print(
        json.dumps(
            {
                "schema_version": (
                    FINANCIAL_SUCCESSOR_QUALIFICATION_SCHEMA_VERSION_V2
                ),
                "status": output["status"],
                "qualification_subject": output[
                    "qualification_subject"
                ],
                "provider_calls": output["provider_calls"],
                "input_tokens": output["input_tokens"],
                "output_tokens": output["output_tokens"],
                "actual_cost_usd": output["actual_cost_usd"],
                "cases_passed": output["qualification"][
                    "aggregate_metrics"
                ]["cases_passed"],
                "cases_failed": output["qualification"][
                    "aggregate_metrics"
                ]["cases_failed"],
                "four_dispositions_passed": output["qualification"][
                    "aggregate_metrics"
                ]["four_dispositions_passed"],
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


def build_successor_qualification_fixture_v2(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> SuccessorQualificationFixtureV2:
    manifest_bytes = manifest_path.read_bytes()
    manifest_file_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    registry = Gate2FinancialEvidenceRegistryFactory().create()
    local_proof = Gate2SuccessorLocalProofV2Factory(
        registry=registry
    ).create(manifest=manifest)
    if local_proof["status"] != "passed":
        raise ValueError("successor_qualification_v2_local_proof_failed")
    scope_factory = Gate2DeterministicFinancialScopeFromGate1V2Factory(
        registry=registry
    )
    context_factory = Gate2FinancialEvidenceSourceContextFactory()
    cases = []
    for case in manifest["cases"]:
        fixture = _fixture_package(case)
        batch = scope_factory.create(gate1_packages=(fixture.payload,))
        if len(batch.scopes) != 1:
            raise ValueError(
                "successor_qualification_v2_scope_count_invalid"
            )
        scope = batch.scopes[0]
        source_context = context_factory.create(
            source_scope_ref=scope.source_package.source_scope_ref,
            source_values=scope.source_package.source_values,
            candidates=scope.decision_contract.package.candidates,
            gate1_packages=(fixture.payload,),
        )
        expected = _model_output(
            case=case,
            scope=scope,
            selected_value_refs=fixture.selected_value_refs,
        )
        cases.append(
            SuccessorQualificationCaseV2(
                case_id=case["case_id"],
                features=tuple(case["features"]),
                scope=scope,
                source_context=source_context,
                expected_model_output=expected,
                expected_disposition=expected["decision"][
                    "disposition"
                ],
                expected_input_type_id=expected["decision"].get(
                    "input_type_id"
                ),
            )
        )
    return SuccessorQualificationFixtureV2(
        manifest_file_sha256=manifest_file_sha256,
        manifest_canonical_hash=local_proof["manifest"][
            "integrity_hash"
        ],
        local_proof_receipt=local_proof,
        registry=registry,
        cases=tuple(cases),
    )


def _runner(*, fixture, model_client, model_id: str):
    provider_profile_id = _provider_profile_id(model_id)
    return Gate2FinancialEvidenceSuccessorRunnerFactory(
        registry=fixture.registry,
        model_client=model_client,
        config=Gate2FinancialEvidenceSuccessorConfig(
            model_id=model_id,
            provider_profile_id=provider_profile_id,
            model_input_schema_version=(
                SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
            ),
            prompt_contract_id=SUCCESSOR_PROMPT_CONTRACT_ID_V3,
        ),
    ).create()


def successor_preflight_cases_v2(
    *,
    fixture: SuccessorQualificationFixtureV2,
    model_id: str,
) -> list[dict[str, Any]]:
    provider_profile_id = _provider_profile_id(model_id)
    runner = _runner(
        fixture=fixture,
        model_client=_NoCallClient(),
        model_id=model_id,
    )
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
            "typed_branch_admitted": (
                case.scope.package["typed_admission"][
                    "typed_branch_available"
                ]
            ),
            "source_context_integrity_hash": (
                case.source_context.integrity_hash
            ),
            "schema_dry_build": _dry_build(
                request_profile=(
                    FINANCIAL_EVIDENCE_SUCCESSOR_QUALIFICATION_REQUEST_PROFILE_V2
                ),
                provider_profile_id=provider_profile_id,
                model_id=model_id,
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


async def qualify_successor_model_v2(
    *,
    model_client,
    model_id: str,
    fixture: SuccessorQualificationFixtureV2,
    checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    runner = _runner(
        fixture=fixture,
        model_client=model_client,
        model_id=model_id,
    )
    case_receipts: list[dict[str, Any]] = []
    successful: list[_SuccessfulCaseV2] = []
    provider_calls = 0
    input_tokens = 0
    output_tokens = 0
    actual_cost = Decimal("0")

    def current(*, terminal: bool) -> dict[str, Any]:
        return _successor_execution_result_v2(
            fixture=fixture,
            successful=successful,
            case_receipts=case_receipts,
            provider_calls=provider_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            actual_cost=actual_cost,
            terminal=terminal,
        )

    if checkpoint is not None:
        checkpoint(current(terminal=False))
    for case in fixture.cases:
        provider_calls += 1
        execution_ref = (
            f"execution:successor-v2-qualification:{case.case_id}"
        )
        decision_validation_ref = (
            f"validation:successor-v2-qualification:{case.case_id}"
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
                    "successor_qualification_v2_budget_receipt_missing"
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
            summary = result.safe_summary
            checks = {
                "canonical_validation_passed": True,
                "deterministic_materialization_passed": True,
                "expected_disposition": (
                    observed_disposition
                    == case.expected_disposition
                ),
                "expected_input_type": (
                    observed_input_type_id
                    == case.expected_input_type_id
                ),
                "exact_model": (
                    result.provider_execution.get(
                        "requested_model_id"
                    )
                    == model_id
                    and result.provider_execution.get(
                        "resolved_model_id"
                    )
                    == model_id
                ),
                "strict_schema": (
                    result.provider_execution.get(
                        "response_format_type"
                    )
                    == "json_schema"
                    and result.provider_execution.get(
                        "response_format_schema_mode"
                    )
                    == "strict_json_schema"
                ),
                "scope_v2": (
                    case.scope.package.get("schema_version")
                    == DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2
                ),
                "source_context_v2": (
                    summary.get("source_context_schema_version")
                    == SOURCE_CONTEXT_SCHEMA_VERSION
                    and summary.get("source_context_integrity_hash")
                    == case.source_context.integrity_hash
                ),
                "model_input_v3": (
                    summary.get("model_input_schema_version")
                    == SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
                ),
                "prompt_v3": (
                    summary.get("prompt_contract_id")
                    == SUCCESSOR_PROMPT_CONTRACT_ID_V3
                ),
                "provider_projection_v3": (
                    summary.get("provider_projection_schema_version")
                    == SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
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


def _successor_execution_result_v2(
    *,
    fixture: SuccessorQualificationFixtureV2,
    successful: list[_SuccessfulCaseV2],
    case_receipts: list[dict[str, Any]],
    provider_calls: int,
    input_tokens: int,
    output_tokens: int,
    actual_cost: Decimal,
    terminal: bool,
) -> dict[str, Any]:
    cases_passed = sum(
        item.get("status") == "passed" for item in case_receipts
    )
    disposition_counts = Counter(
        str(item.get("observed_disposition"))
        for item in case_receipts
        if item.get("observed_disposition") in DISPOSITIONS
    )
    product_proof = None
    if terminal and len(successful) == len(fixture.cases):
        product_proof = _terminal_product_proof_v2(
            fixture=fixture,
            successful=successful,
        )
    four_dispositions = (
        set(disposition_counts) == set(DISPOSITIONS)
        and all(disposition_counts[item] > 0 for item in DISPOSITIONS)
    )
    aggregate = {
        "cases_total": len(fixture.cases),
        "cases_executed": len(case_receipts),
        "cases_passed": cases_passed,
        "cases_failed": len(case_receipts) - cases_passed,
        "four_dispositions_passed": four_dispositions,
        "terminal_disposition_counts": {
            item: disposition_counts[item] for item in DISPOSITIONS
        },
        "canonical_validation_passed": (
            len(case_receipts) == len(fixture.cases)
            and all(
                item.get("canonical_validation_ran") is True
                for item in case_receipts
            )
        ),
        "fallback_total": 0,
        "repair_attempts_total": 0,
        "source_model_calls_total": 0,
        "domain_model_calls_total": 0,
        "expensive_model_calls_total": 0,
    }
    status = "in_progress"
    if terminal:
        status = (
            "passed"
            if cases_passed == len(fixture.cases)
            and four_dispositions
            and aggregate["canonical_validation_passed"]
            and isinstance(product_proof, dict)
            and product_proof["status"] == "passed"
            else "failed"
        )
    return {
        "execution_state": "terminal" if terminal else "in_progress",
        "status": status,
        "provider_calls": provider_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "actual_cost_usd": format(actual_cost, "f"),
        "qualification": {
            "status": status,
            "aggregate_metrics": aggregate,
            "cases": copy.deepcopy(case_receipts),
            "product_proof": product_proof,
            "fallback_used": False,
            "repair_attempt_count": 0,
            "raw_provider_output_included": False,
        },
    }


def _terminal_product_proof_v2(
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
        authorized_scopes=(item.case.scope for item in successful),
        observations=(
            Gate2SuccessorScopeObservation(
                source_scope_ref=(
                    item.case.scope.source_package.source_scope_ref
                ),
                model_output=item.actual_model_output,
                materialized_artifact=item.result.materialized_artifact,
                execution_ref=item.execution_ref,
                decision_validation_ref=(
                    item.decision_validation_ref
                ),
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
    artifact_family = Gate2SuccessorArtifactFamilyV2Factory(
        registry=fixture.registry
    ).create(
        run_ref="run:successor-v2-qualification:gpt54-nano",
        source_extraction_run_ref=(
            "run:synthetic-source:successor-v2-qualification"
        ),
        inputs=(
            Gate2SuccessorArtifactV2Input(
                scope=item.case.scope,
                source_context=item.case.source_context,
                result=item.result,
            )
            for item in successful
        ),
        financial_context=context,
    )
    reader = Gate2SuccessorCompatibilityReaderFactory(
        registry=fixture.registry
    ).create()
    compatibility_reads = [
        reader.read(
            artifact_ref=payload["package_artifact_ref"],
            payload=payload,
        )
        for payload in artifact_family.package_artifacts
    ]
    metrics = comparator["metrics"]
    checks = {
        "product_comparator_passed": comparator["status"] == "passed",
        "literal_loss_zero": metrics["literal_loss_total"] == 0,
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
        "artifact_family_v2_passed": (
            artifact_family.execution_receipt["status"] == "passed"
        ),
        "production_write_not_admitted": (
            artifact_family.execution_receipt[
                "production_write_admitted"
            ]
            is False
        ),
        "private_source_context_not_stored": (
            artifact_family.execution_receipt[
                "private_source_contexts_stored_total"
            ]
            == 0
        ),
        "compatibility_reads_passed": (
            len(compatibility_reads) == len(successful)
            and all(
                item.validator_status == "passed"
                and item.legacy_payload_rewritten is False
                and item.silent_conversion_used is False
                for item in compatibility_reads
            )
        ),
    }
    return {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "comparator": {
            "schema_version": comparator["schema_version"],
            "policy_version": comparator["policy_version"],
            "checks": copy.deepcopy(comparator["checks"]),
            "metrics": copy.deepcopy(metrics),
        },
        "artifact_family": artifact_family.safe_summary(),
        "compatibility_reads_total": len(compatibility_reads),
        "financial_context_integrity_hash": context["integrity_hash"],
        "raw_provider_output_included": False,
    }


def successor_qualification_contract_identity_v2(
    *,
    fixture: SuccessorQualificationFixtureV2,
    model_id: str = EXACT_MODEL_ID,
) -> Gate2EconomyQualificationContractIdentity:
    profile = gate2_provider_profile(
        _provider_profile_id(model_id)
    )
    prompt = Gate2FinancialEvidenceSuccessorPromptFactory().create(
        prompt_contract_id=SUCCESSOR_PROMPT_CONTRACT_ID_V3
    )
    projections = [
        Gate2FinancialEvidenceSuccessorProviderProjectionFactory().create(
            contract=case.scope.decision_contract
        )
        for case in fixture.cases
    ]
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
            / "gate2_financial_evidence_typed_admission.py",
            SERVICE_ROOT
            / "broker_reports_gate1"
            / "gate2_financial_evidence_source_context.py",
            SERVICE_ROOT
            / "broker_reports_gate1"
            / "gate2_financial_evidence_successor.py",
            SERVICE_ROOT
            / "broker_reports_gate1"
            / "gate2_financial_evidence_successor_projection.py",
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
        )
    )
    return Gate2EconomyQualificationContractIdentity(
        provider_route_revision=gate2_provider_profile_revision(profile),
        input_contract_version=(
            f"{DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2}:"
            f"{SOURCE_CONTEXT_SCHEMA_VERSION}:{context_hash}:"
            f"{SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3}:"
            f"{fixture.registry.registry_hash}:"
            f"{fixture.manifest_canonical_hash}"
        ),
        output_contract_version=(
            f"{DECISION_SCHEMA_VERSION}:"
            f"{SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION}:"
            f"{provider_schema_hash}"
        ),
        prompt_version=(
            f"{SUCCESSOR_PROMPT_CONTRACT_ID_V3}:{prompt.hash}"
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


def _identity_summary_v2(
    *,
    identity: Gate2EconomyQualificationContractIdentity,
    fixture: SuccessorQualificationFixtureV2,
    model_id: str = EXACT_MODEL_ID,
) -> dict[str, Any]:
    provider_profile_id = _provider_profile_id(model_id)
    return {
        **identity.to_dict(),
        "exact_model_id": model_id,
        "provider_profile_id": provider_profile_id,
        "deterministic_scope_schema": (
            DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2
        ),
        "source_context_schema": SOURCE_CONTEXT_SCHEMA_VERSION,
        "source_context_policy": SOURCE_CONTEXT_POLICY_VERSION,
        "registry_version": fixture.registry.registry_version,
        "registry_hash": fixture.registry.registry_hash,
        "financial_decision_contract": DECISION_SCHEMA_VERSION,
        "successor_model_input_schema": (
            SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
        ),
        "successor_prompt_contract": (
            SUCCESSOR_PROMPT_CONTRACT_ID_V3
        ),
        "provider_projection_schema": (
            SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
        ),
        "provider_projection_policy": (
            SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION
        ),
        "validated_decision_schema": VALIDATED_DECISION_SCHEMA_VERSION,
        "materializer_policy": MATERIALIZATION_POLICY_VERSION,
        "comparator_policy": SUCCESSOR_COMPARATOR_POLICY_VERSION,
        "artifact_policy": SUCCESSOR_ARTIFACT_POLICY_VERSION_V2,
        "compatibility_reader_policy": (
            SUCCESSOR_COMPATIBILITY_READER_POLICY_VERSION
        ),
        "fixture_manifest_canonical_hash": (
            fixture.manifest_canonical_hash
        ),
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


def _subject(model_id: str) -> dict[str, str]:
    return {
        "exact_model_id": model_id,
        "provider_profile_id": _provider_profile_id(model_id),
        "workload_class": (
            "gate2_financial_evidence_successor_v2"
        ),
    }


def _provider_profile_id(model_id: str) -> str:
    try:
        return EXACT_CANDIDATE_PROVIDER_PROFILES[model_id]
    except KeyError as exc:
        raise ValueError(
            "successor_qualification_exact_candidate_unknown"
        ) from exc


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
