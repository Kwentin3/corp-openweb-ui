from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v6_choice import (
    Gate2FinancialSemanticV6ChoiceContract,
    Gate2FinancialSemanticV6ChoiceContractFactory,
    normalize_financial_semantic_v6_local_choice,
)
from .gate2_financial_semantic_v6_context_linter import (
    Gate2FinancialSemanticV6ContextLinterFactory,
    Gate2FinancialSemanticV6LintedRequest,
    validate_financial_semantic_v6_linted_request,
)
from .gate2_financial_semantic_v6_execution_identity import (
    V6_EXACT_MODEL_ID,
    V6_PROVIDER_PROFILE_ID,
)
from .gate2_financial_semantic_v6_expansion import (
    Gate2FinancialSemanticV6DecisionExpansionFactory,
)
from .gate2_financial_semantic_v6_packet import (
    Gate2FinancialSemanticV6Packet,
    Gate2FinancialSemanticV6PacketFactory,
)
from .gate2_financial_semantic_v6_qualification import (
    Gate2FinancialSemanticV6QualificationCase,
    Gate2FinancialSemanticV6QualificationFixture,
    _semantic_authorities,
)
from .gate2_financial_semantic_v6_qualification_run import (
    V6_PROVIDER_SMOKE_CASES,
)
from .gate2_financial_semantic_v6_stronger_candidate import (
    V6_GOAL12_EXACT_MODEL_ID,
    V6_GOAL12_PROVIDER_PROFILE_ID,
)
from .gate2_financial_semantic_v6_totality import (
    Gate2FinancialSemanticV6TotalMaterializerFactory,
)
from .gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    Gate2StructuredModelClient,
    Gate2StructuredModelResult,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE,
)


V6_SLIM_DIAGNOSTIC_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_slim_diagnostic_v1"
)
V6_SLIM_DIAGNOSTIC_POLICY_VERSION = (
    "broker_reports_gate2_llm_semantic_context_goal4_v1"
)
V6_SLIM_DIAGNOSTIC_CONFIGURATIONS = (
    {
        "configuration_id": "nano_slim",
        "exact_model_id": V6_EXACT_MODEL_ID,
        "provider_profile_id": V6_PROVIDER_PROFILE_ID,
        "option_order": "canonical",
    },
    {
        "configuration_id": "haiku_slim",
        "exact_model_id": V6_GOAL12_EXACT_MODEL_ID,
        "provider_profile_id": V6_GOAL12_PROVIDER_PROFILE_ID,
        "option_order": "canonical",
    },
    {
        "configuration_id": "nano_slim_reversed",
        "exact_model_id": V6_EXACT_MODEL_ID,
        "provider_profile_id": V6_PROVIDER_PROFILE_ID,
        "option_order": "reversed",
    },
)
V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL = 6
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6SlimDiagnosticFactory.create is the only GOAL 4 "
    "six-cell Slim diagnostic plan constructor; run_financial_semantic_v6_"
    "slim_diagnostic is its only provider execution entrypoint"
)
FORBIDDEN = (
    "The GOAL 4 diagnostic must not build a second packet, compile options, "
    "change Prompt or type meanings, run the full benchmark, retry, fallback, "
    "repair, admit a model or mutate product runtime"
)

_REVISION_LENGTH = 40
_SEMANTIC_FIELDS = ("disposition", "typed_option_id", "reason_code")


class Gate2FinancialSemanticV6SlimDiagnosticError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6SlimDiagnosticCell:
    ordinal: int
    configuration_id: str
    case_id: str
    smoke_role: str
    exact_model_id: str
    provider_profile_id: str
    option_order: str
    registry: Gate2FinancialEvidenceRegistrySnapshot
    case: Gate2FinancialSemanticV6QualificationCase
    packet: Gate2FinancialSemanticV6Packet
    choice_contract: Gate2FinancialSemanticV6ChoiceContract
    linted_request: Gate2FinancialSemanticV6LintedRequest
    expected_answer: dict[str, Any]
    expected_model_output: dict[str, Any]

    def safe_plan_summary(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "configuration_id": self.configuration_id,
            "case_id": self.case_id,
            "smoke_role": self.smoke_role,
            "exact_model_id": self.exact_model_id,
            "provider_profile_id": self.provider_profile_id,
            "option_order": self.option_order,
            "model_visible_request_hash": (
                self.linted_request.lint_receipt.model_visible_request_hash
            ),
            "model_visible_utf8_bytes": (
                self.linted_request.lint_receipt.model_visible_utf8_bytes
            ),
            "estimated_input_tokens": (
                self.linted_request.lint_receipt.estimated_input_tokens
            ),
            "slim_view_hash": self.packet.slim_candidate.view_hash,
            "local_choice_schema_hash": (
                self.choice_contract.local_candidate.response_schema_hash
            ),
            "expected_answer": copy.deepcopy(self.expected_answer),
            "expected_model_output": copy.deepcopy(
                self.expected_model_output
            ),
            "context_lint_status": self.linted_request.lint_receipt.status,
            "local_totality_proven": True,
            "provider_calls_total": 0,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6SlimDiagnosticPlan:
    schema_version: str
    policy_version: str
    repository_revision: str
    request_profile: str
    cells: tuple[Gate2FinancialSemanticV6SlimDiagnosticCell, ...]
    plan_hash: str

    def safe_summary(self) -> dict[str, Any]:
        cells = [cell.safe_plan_summary() for cell in self.cells]
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "repository_revision": self.repository_revision,
            "request_profile": self.request_profile,
            "status": "passed",
            "preflight_only": True,
            "provider_submissions_planned_total": len(cells),
            "provider_calls_total": 0,
            "fallback_total": 0,
            "repair_total": 0,
            "hidden_retry_total": 0,
            "benchmark_run": False,
            "production_admissions_total": 0,
            "cells": cells,
            "plan_hash": self.plan_hash,
        }


class Gate2FinancialSemanticV6SlimDiagnosticFactory:
    def create(
        self,
        *,
        fixture: Gate2FinancialSemanticV6QualificationFixture,
        repository_revision: str,
    ) -> Gate2FinancialSemanticV6SlimDiagnosticPlan:
        if (
            not isinstance(repository_revision, str)
            or len(repository_revision) != _REVISION_LENGTH
            or any(
                character not in "0123456789abcdef"
                for character in repository_revision
            )
        ):
            _fail("financial_semantic_v6_slim_diagnostic_revision_invalid")
        cases_by_id = {
            case.case_id: case for case in fixture.semantic_cases
        }
        expected_case_ids = tuple(
            case_id for _role, case_id, _disposition in V6_PROVIDER_SMOKE_CASES
        )
        if any(case_id not in cases_by_id for case_id in expected_case_ids):
            _fail("financial_semantic_v6_slim_diagnostic_case_missing")

        cells: list[Gate2FinancialSemanticV6SlimDiagnosticCell] = []
        ordinal = 0
        for configuration in V6_SLIM_DIAGNOSTIC_CONFIGURATIONS:
            for smoke_role, case_id, expected_disposition in (
                V6_PROVIDER_SMOKE_CASES
            ):
                case = cases_by_id[case_id]
                if (
                    case.route != "semantic_model"
                    or case.expected_disposition != expected_disposition
                ):
                    _fail(
                        "financial_semantic_v6_slim_diagnostic_case_invalid"
                    )
                packet, choice_contract = _candidate_authorities(
                    fixture=fixture,
                    case=case,
                    option_order=str(configuration["option_order"]),
                )
                linted = _linted_request(
                    fixture=fixture,
                    case=case,
                    packet=packet,
                    choice_contract=choice_contract,
                    exact_model_id=str(configuration["exact_model_id"]),
                )
                expected_answer = copy.deepcopy(
                    case.expected_model_choice
                )
                expected_model_output = _local_expected_output(
                    expected_answer=expected_answer,
                    packet=packet,
                )
                normalized_expected = (
                    normalize_financial_semantic_v6_local_choice(
                        model_output=expected_model_output,
                        choice_contract=choice_contract,
                        packet=packet,
                    )
                )
                if normalized_expected != expected_answer:
                    _fail(
                        "financial_semantic_v6_slim_diagnostic_expected_drift"
                    )
                ordinal += 1
                cells.append(
                    Gate2FinancialSemanticV6SlimDiagnosticCell(
                        ordinal=ordinal,
                        configuration_id=str(
                            configuration["configuration_id"]
                        ),
                        case_id=case.case_id,
                        smoke_role=smoke_role,
                        exact_model_id=str(configuration["exact_model_id"]),
                        provider_profile_id=str(
                            configuration["provider_profile_id"]
                        ),
                        option_order=str(configuration["option_order"]),
                        registry=fixture.registry,
                        case=case,
                        packet=packet,
                        choice_contract=choice_contract,
                        linted_request=linted,
                        expected_answer=expected_answer,
                        expected_model_output=expected_model_output,
                    )
                )
        if (
            len(cells) != V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL
            or tuple(cell.ordinal for cell in cells)
            != tuple(
                range(1, V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL + 1)
            )
        ):
            _fail("financial_semantic_v6_slim_diagnostic_plan_invalid")
        material = _plan_material(
            repository_revision=repository_revision,
            cells=tuple(cells),
        )
        return Gate2FinancialSemanticV6SlimDiagnosticPlan(
            schema_version=V6_SLIM_DIAGNOSTIC_SCHEMA_VERSION,
            policy_version=V6_SLIM_DIAGNOSTIC_POLICY_VERSION,
            repository_revision=repository_revision,
            request_profile=(
                FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE
            ),
            cells=tuple(cells),
            plan_hash=sha256_json(material),
        )


def financial_semantic_v6_slim_diagnostic_initial_receipt(
    *,
    plan: Gate2FinancialSemanticV6SlimDiagnosticPlan,
) -> dict[str, Any]:
    _validate_plan(plan)
    return _terminal_or_checkpoint_receipt(
        plan=plan,
        case_evidence=[],
        terminal=False,
    )


async def run_financial_semantic_v6_slim_diagnostic(
    *,
    plan: Gate2FinancialSemanticV6SlimDiagnosticPlan,
    model_clients: dict[str, Gate2StructuredModelClient],
    safe_checkpoint: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    _validate_plan(plan)
    required_profiles = {
        cell.provider_profile_id for cell in plan.cells
    }
    if set(model_clients) != required_profiles:
        _fail("financial_semantic_v6_slim_diagnostic_clients_invalid")
    initial_snapshots: dict[str, dict[str, int]] = {}
    for profile_id, client in model_clients.items():
        if (
            getattr(client, "request_profile", plan.request_profile)
            != plan.request_profile
        ):
            _fail(
                "financial_semantic_v6_slim_diagnostic_profile_invalid"
            )
        initial_snapshots[profile_id] = _lifecycle_snapshot(client)
        if initial_snapshots[profile_id] != {
            "local_invocations_total": 0,
            "provider_submissions_total": 0,
            "provider_responses_total": 0,
        }:
            _fail(
                "financial_semantic_v6_slim_diagnostic_client_not_fresh"
            )

    case_evidence: list[dict[str, Any]] = []
    if safe_checkpoint is not None:
        safe_checkpoint(
            _terminal_or_checkpoint_receipt(
                plan=plan,
                case_evidence=case_evidence,
                terminal=False,
            )
        )

    for cell in plan.cells:
        client = model_clients[cell.provider_profile_id]
        before = _lifecycle_snapshot(client)
        result: Gate2StructuredModelResult | None = None
        exact_output: Any = None
        normalized: dict[str, Any] | None = None
        technical_pipeline_passed = False
        canonical_materialization_hash: str | None = None
        failure_code: str | None = None
        metrics = _empty_metrics()
        try:
            result = await client.extract(
                prompt=cell.linted_request.prompt,
                package=cell.linted_request.package,
                model_id=cell.exact_model_id,
                response_format=cell.linted_request.response_format,
            )
            exact_output = copy.deepcopy(result.content)
            delta = _lifecycle_delta(
                before=before,
                after=_lifecycle_snapshot(client),
            )
            if delta != {
                "local_invocations": 1,
                "provider_submissions": 1,
                "provider_responses": 1,
            }:
                _fail(
                    "financial_semantic_v6_slim_diagnostic_lifecycle_invalid"
                )
            metrics = _result_metrics(
                result=result,
                cell=cell,
            )
            normalized = normalize_financial_semantic_v6_local_choice(
                model_output=exact_output,
                choice_contract=cell.choice_contract,
                packet=cell.packet,
            )
            evidence_bundle, compilation, _, _ = _semantic_authorities(
                cell.case
            )
            expanded = Gate2FinancialSemanticV6DecisionExpansionFactory(
                registry=cell.registry
            ).create_from_local_candidate(
                model_output=exact_output,
                choice_contract=cell.choice_contract,
                packet=cell.packet,
                evidence_bundle=evidence_bundle,
                source_package=cell.case.scope.source_package,
                compilation=compilation,
            )
            materialized = Gate2FinancialSemanticV6TotalMaterializerFactory(
                registry=cell.registry
            ).create(
                expansion=expanded,
                model_output=normalized,
                choice_contract=cell.choice_contract,
                packet=cell.packet,
                evidence_bundle=evidence_bundle,
                source_package=cell.case.scope.source_package,
                compilation=compilation,
            )
            canonical_materialization_hash = (
                materialized.canonical_artifact_hash
            )
            technical_pipeline_passed = True
        except Exception as exc:
            failure_code = _failure_code(exc)
            delta = _lifecycle_delta(
                before=before,
                after=_lifecycle_snapshot(client),
            )
            if result is not None:
                metrics = _best_effort_result_metrics(result)

        comparison = _mechanical_comparison(
            expected=cell.expected_answer,
            actual=normalized,
        )
        case_evidence.append(
            _case_evidence(
                cell=cell,
                exact_output=exact_output,
                normalized=normalized,
                comparison=comparison,
                technical_pipeline_passed=technical_pipeline_passed,
                canonical_materialization_hash=(
                    canonical_materialization_hash
                ),
                failure_code=failure_code,
                lifecycle=delta,
                metrics=metrics,
            )
        )
        if safe_checkpoint is not None:
            safe_checkpoint(
                _terminal_or_checkpoint_receipt(
                    plan=plan,
                    case_evidence=case_evidence,
                    terminal=False,
                )
            )

    terminal = _terminal_or_checkpoint_receipt(
        plan=plan,
        case_evidence=case_evidence,
        terminal=True,
    )
    if safe_checkpoint is not None:
        safe_checkpoint(terminal)
    return terminal


def _candidate_authorities(
    *,
    fixture: Gate2FinancialSemanticV6QualificationFixture,
    case: Gate2FinancialSemanticV6QualificationCase,
    option_order: str,
) -> tuple[
    Gate2FinancialSemanticV6Packet,
    Gate2FinancialSemanticV6ChoiceContract,
]:
    evidence_bundle, compilation, active_packet, active_choice = (
        _semantic_authorities(case)
    )
    if option_order == "canonical":
        return active_packet, active_choice
    if option_order != "reversed":
        _fail("financial_semantic_v6_slim_diagnostic_order_invalid")
    exact_ids = tuple(
        option.typed_option_id for option in compilation.typed_options
    )
    packet = Gate2FinancialSemanticV6PacketFactory(
        registry=fixture.registry
    ).create(
        evidence_bundle=evidence_bundle,
        source_package=case.scope.source_package,
        compilation=compilation,
        slim_choice_order=tuple(reversed(exact_ids)),
    )
    choice = Gate2FinancialSemanticV6ChoiceContractFactory(
        registry=fixture.registry
    ).create(
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=case.scope.source_package,
        compilation=compilation,
    )
    if (
        packet.payload != active_packet.payload
        or packet.packet_hash != active_packet.packet_hash
        or choice.choice_schema != active_choice.choice_schema
        or choice.choice_schema_hash != active_choice.choice_schema_hash
    ):
        _fail("financial_semantic_v6_slim_diagnostic_authority_drift")
    return packet, choice


def _linted_request(
    *,
    fixture: Gate2FinancialSemanticV6QualificationFixture,
    case: Gate2FinancialSemanticV6QualificationCase,
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    exact_model_id: str,
) -> Gate2FinancialSemanticV6LintedRequest:
    evidence_bundle, compilation, _, _ = _semantic_authorities(case)
    args = {
        "packet": packet,
        "choice_contract": choice_contract,
        "evidence_bundle": evidence_bundle,
        "source_package": case.scope.source_package,
        "compilation": compilation,
    }
    factory = Gate2FinancialSemanticV6ContextLinterFactory(
        registry=fixture.registry
    )
    linted = factory.create(
        **args,
        candidate_payload=packet.slim_candidate.payload,
        response_schema=choice_contract.local_candidate.response_schema,
        alias_receipt=packet.slim_alias_receipt,
        exact_model_id=exact_model_id,
    )
    validate_financial_semantic_v6_linted_request(
        linted_request=linted,
        registry=fixture.registry,
        **args,
    )
    totality = factory.prove_local_totality(
        linted_request=linted,
        **args,
    )
    if (
        not totality.exact_replay
        or totality.validated_but_unmaterializable_total != 0
        or totality.local_outputs_total
        != totality.total_materializations_total
        or totality.provider_calls_total != 0
    ):
        _fail("financial_semantic_v6_slim_diagnostic_totality_failed")
    return linted


def _local_expected_output(
    *,
    expected_answer: dict[str, Any],
    packet: Gate2FinancialSemanticV6Packet,
) -> dict[str, Any]:
    if expected_answer.get("disposition") == "typed_input":
        expected_id = expected_answer.get("typed_option_id")
        aliases = [
            alias
            for alias, option_id in (
                packet.slim_alias_receipt.choice_aliases.items()
            )
            if option_id == expected_id
        ]
        if len(aliases) != 1:
            _fail("financial_semantic_v6_slim_diagnostic_expected_invalid")
        return {"choice": aliases[0]}
    if (
        expected_answer.get("disposition")
        == "unclassified_financial_input"
        and set(expected_answer) == {"disposition", "reason_code"}
    ):
        return {
            "choice": "unclassified",
            "reason": expected_answer["reason_code"],
        }
    _fail("financial_semantic_v6_slim_diagnostic_expected_invalid")


def _plan_material(
    *,
    repository_revision: str,
    cells: tuple[Gate2FinancialSemanticV6SlimDiagnosticCell, ...],
) -> dict[str, Any]:
    return {
        "schema_version": V6_SLIM_DIAGNOSTIC_SCHEMA_VERSION,
        "policy_version": V6_SLIM_DIAGNOSTIC_POLICY_VERSION,
        "repository_revision": repository_revision,
        "request_profile": FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE,
        "cells": [cell.safe_plan_summary() for cell in cells],
        "provider_submissions_planned_total": (
            V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL
        ),
        "fallback_total": 0,
        "repair_total": 0,
        "hidden_retry_total": 0,
        "benchmark_run": False,
        "production_admissions_total": 0,
    }


def _validate_plan(
    plan: Gate2FinancialSemanticV6SlimDiagnosticPlan,
) -> None:
    if (
        not isinstance(plan, Gate2FinancialSemanticV6SlimDiagnosticPlan)
        or plan.schema_version != V6_SLIM_DIAGNOSTIC_SCHEMA_VERSION
        or plan.policy_version != V6_SLIM_DIAGNOSTIC_POLICY_VERSION
        or plan.request_profile
        != FINANCIAL_SEMANTIC_V6_SLIM_LINTED_REQUEST_PROFILE
        or len(plan.cells) != V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL
        or plan.plan_hash
        != sha256_json(
            _plan_material(
                repository_revision=plan.repository_revision,
                cells=plan.cells,
            )
        )
    ):
        _fail("financial_semantic_v6_slim_diagnostic_plan_invalid")


def _lifecycle_snapshot(
    client: Gate2StructuredModelClient,
) -> dict[str, int]:
    snapshot = client.qualification_lifecycle_snapshot()
    required = {
        "local_invocations_total",
        "provider_submissions_total",
        "provider_responses_total",
    }
    if (
        not isinstance(snapshot, dict)
        or set(snapshot) != required
        or any(
            isinstance(snapshot[field], bool)
            or not isinstance(snapshot[field], int)
            or snapshot[field] < 0
            for field in required
        )
        or snapshot["provider_responses_total"]
        > snapshot["provider_submissions_total"]
    ):
        _fail("financial_semantic_v6_slim_diagnostic_lifecycle_invalid")
    return copy.deepcopy(snapshot)


def _lifecycle_delta(
    *,
    before: dict[str, int],
    after: dict[str, int],
) -> dict[str, int]:
    delta = {
        "local_invocations": (
            after["local_invocations_total"]
            - before["local_invocations_total"]
        ),
        "provider_submissions": (
            after["provider_submissions_total"]
            - before["provider_submissions_total"]
        ),
        "provider_responses": (
            after["provider_responses_total"]
            - before["provider_responses_total"]
        ),
    }
    if (
        delta["local_invocations"] not in {0, 1}
        or delta["provider_submissions"] not in {0, 1}
        or delta["provider_responses"] not in {0, 1}
        or delta["provider_responses"] > delta["provider_submissions"]
        or delta["provider_submissions"] > delta["local_invocations"]
    ):
        _fail("financial_semantic_v6_slim_diagnostic_lifecycle_invalid")
    return delta


def _result_metrics(
    *,
    result: Gate2StructuredModelResult,
    cell: Gate2FinancialSemanticV6SlimDiagnosticCell,
) -> dict[str, Any]:
    metadata = result.execution_metadata
    budget = result.economy_budget_receipt
    if (
        result.fallback_used
        or result.repair_attempt_count != 0
        or not isinstance(metadata, Gate2ProviderExecutionMetadata)
        or metadata.provider_profile_id != cell.provider_profile_id
        or metadata.requested_model_id != cell.exact_model_id
        or metadata.resolved_model_id != cell.exact_model_id
        or not isinstance(budget, dict)
    ):
        _fail("financial_semantic_v6_slim_diagnostic_metadata_invalid")
    input_tokens = _required_nonnegative_int(
        budget.get("input_tokens"),
        "financial_semantic_v6_slim_diagnostic_input_tokens_invalid",
    )
    output_tokens = _required_nonnegative_int(
        budget.get("output_tokens"),
        "financial_semantic_v6_slim_diagnostic_output_tokens_invalid",
    )
    total_tokens = _required_nonnegative_int(
        metadata.total_tokens,
        "financial_semantic_v6_slim_diagnostic_total_tokens_invalid",
    )
    latency_ms = _required_nonnegative_int(
        metadata.duration_ms,
        "financial_semantic_v6_slim_diagnostic_latency_invalid",
    )
    if (
        metadata.input_tokens != input_tokens
        or metadata.output_tokens != output_tokens
        or total_tokens != input_tokens + output_tokens
    ):
        _fail("financial_semantic_v6_slim_diagnostic_usage_invalid")
    actual_cost = _required_decimal(
        budget.get("actual_cost_usd"),
        "financial_semantic_v6_slim_diagnostic_cost_invalid",
    )
    return {
        "actual_input_tokens": input_tokens,
        "actual_output_tokens": output_tokens,
        "actual_total_tokens": total_tokens,
        "actual_cost_usd": format(actual_cost, "f"),
        "latency_ms": latency_ms,
    }


def _best_effort_result_metrics(
    result: Gate2StructuredModelResult,
) -> dict[str, Any]:
    metadata = result.execution_metadata
    budget = (
        result.economy_budget_receipt
        if isinstance(result.economy_budget_receipt, dict)
        else {}
    )
    return {
        "actual_input_tokens": _optional_nonnegative_int(
            budget.get("input_tokens")
        ),
        "actual_output_tokens": _optional_nonnegative_int(
            budget.get("output_tokens")
        ),
        "actual_total_tokens": _optional_nonnegative_int(
            getattr(metadata, "total_tokens", None)
        ),
        "actual_cost_usd": _optional_decimal_text(
            budget.get("actual_cost_usd")
        ),
        "latency_ms": _optional_nonnegative_int(
            getattr(metadata, "duration_ms", None)
        ),
    }


def _empty_metrics() -> dict[str, Any]:
    return {
        "actual_input_tokens": None,
        "actual_output_tokens": None,
        "actual_total_tokens": None,
        "actual_cost_usd": None,
        "latency_ms": None,
    }


def _case_evidence(
    *,
    cell: Gate2FinancialSemanticV6SlimDiagnosticCell,
    exact_output: Any,
    normalized: dict[str, Any] | None,
    comparison: dict[str, Any],
    technical_pipeline_passed: bool,
    canonical_materialization_hash: str | None,
    failure_code: str | None,
    lifecycle: dict[str, int],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    model_input = {
        "messages": copy.deepcopy(
            cell.linted_request.canonical_request["messages"]
        ),
        "response_format": copy.deepcopy(
            cell.linted_request.canonical_request["response_format"]
        ),
    }
    exact_json = _semantic_json_object(exact_output)
    first_alias = (
        cell.packet.slim_candidate.payload["choices"][0]["alias"]
        if cell.packet.slim_candidate.payload["choices"]
        else None
    )
    selected_alias = (
        exact_json.get("choice")
        if isinstance(exact_json, dict)
        and isinstance(exact_json.get("choice"), str)
        and exact_json.get("choice") != "unclassified"
        else None
    )
    diagnosis = (
        {
            "code": "TECHNICAL_PIPELINE_ERROR",
            "basis": (
                "The sealed request, provider response, Local Choice parser "
                "and canonical expansion/materialization chain did not all "
                "complete."
            ),
            "failure_code": failure_code,
        }
        if not technical_pipeline_passed
        else (
            {
                "code": "NONE",
                "basis": (
                    "The normalized semantic answer exactly matches the "
                    "frozen expected answer."
                ),
                "failure_code": None,
            }
            if comparison["all_fields_match"]
            else {
                "code": "MODEL_SEMANTIC_ERROR",
                "basis": (
                    "The sealed Slim input parsed and materialized exactly, "
                    "but the normalized semantic choice differs from the "
                    "frozen expected answer."
                ),
                "failure_code": None,
            }
        )
    )
    return {
        "ordinal": cell.ordinal,
        "configuration_id": cell.configuration_id,
        "case_id": cell.case_id,
        "smoke_role": cell.smoke_role,
        "exact_model_id": cell.exact_model_id,
        "provider_profile_id": cell.provider_profile_id,
        "option_order": cell.option_order,
        "exact_model_visible_input": model_input,
        "model_visible_request_hash": (
            cell.linted_request.lint_receipt.model_visible_request_hash
        ),
        "model_visible_utf8_bytes": (
            cell.linted_request.lint_receipt.model_visible_utf8_bytes
        ),
        "repository_estimated_input_tokens": (
            cell.linted_request.lint_receipt.estimated_input_tokens
        ),
        "expected_model_output": copy.deepcopy(
            cell.expected_model_output
        ),
        "expected_answer": copy.deepcopy(cell.expected_answer),
        "exact_adapter_output": copy.deepcopy(exact_output),
        "exact_model_answer": exact_json,
        "normalized_answer": copy.deepcopy(normalized),
        "normalization": {
            "selected_local_alias": selected_alias,
            "selected_exact_typed_option_id": (
                normalized.get("typed_option_id")
                if isinstance(normalized, dict)
                else None
            ),
            "first_visible_choice_alias": first_alias,
            "first_visible_choice_selected": (
                selected_alias is not None and selected_alias == first_alias
            ),
            "post_response_repair_total": 0,
        },
        "mechanical_comparison": comparison,
        "technical_pipeline": {
            "status": (
                "PASSED" if technical_pipeline_passed else "FAILED"
            ),
            "failure_code": failure_code,
            "context_lint": "PASSED",
            "local_choice_parser": (
                "PASSED" if normalized is not None else "FAILED"
            ),
            "canonical_expansion_materialization": (
                "PASSED"
                if canonical_materialization_hash is not None
                else "FAILED"
            ),
            "canonical_artifact_hash": canonical_materialization_hash,
        },
        "provider_lifecycle": copy.deepcopy(lifecycle),
        "provider_metrics": copy.deepcopy(metrics),
        "diagnosis": diagnosis,
    }


def _terminal_or_checkpoint_receipt(
    *,
    plan: Gate2FinancialSemanticV6SlimDiagnosticPlan,
    case_evidence: list[dict[str, Any]],
    terminal: bool,
) -> dict[str, Any]:
    evidence = copy.deepcopy(case_evidence)
    submissions = sum(
        item["provider_lifecycle"]["provider_submissions"]
        for item in evidence
    )
    responses = sum(
        item["provider_lifecycle"]["provider_responses"]
        for item in evidence
    )
    local_invocations = sum(
        item["provider_lifecycle"]["local_invocations"]
        for item in evidence
    )
    technical_passed = (
        len(evidence) == V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL
        and submissions == V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL
        and responses == V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL
        and all(
            item["technical_pipeline"]["status"] == "PASSED"
            for item in evidence
        )
    )
    haiku = [
        item
        for item in evidence
        if item["configuration_id"] == "haiku_slim"
    ]
    haiku_passed = (
        len(haiku) == 2
        and all(
            item["mechanical_comparison"]["all_fields_match"]
            for item in haiku
        )
    )
    terminal_status = (
        "passed"
        if terminal and technical_passed and haiku_passed
        else ("failed" if terminal else "in_progress")
    )
    material = {
        "schema_version": V6_SLIM_DIAGNOSTIC_SCHEMA_VERSION,
        "policy_version": V6_SLIM_DIAGNOSTIC_POLICY_VERSION,
        "execution_state": "terminal" if terminal else "in_progress",
        "status": terminal_status,
        "repository_revision": plan.repository_revision,
        "request_profile": plan.request_profile,
        "plan_hash": plan.plan_hash,
        "scope": {
            "frozen_cases": [
                case_id
                for _role, case_id, _disposition in V6_PROVIDER_SMOKE_CASES
            ],
            "configurations": [
                item["configuration_id"]
                for item in V6_SLIM_DIAGNOSTIC_CONFIGURATIONS
            ],
            "prompt_changed": False,
            "type_meanings_changed": False,
            "expected_answers_changed": False,
            "full_benchmark_run": False,
            "runtime_route_changed": False,
        },
        "attempt_accounting": {
            "provider_submissions_planned_total": (
                V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL
            ),
            "local_invocations_total": local_invocations,
            "provider_submissions_total": submissions,
            "provider_responses_total": responses,
            "fallback_total": 0,
            "repair_total": 0,
            "hidden_retry_total": 0,
        },
        "provider_metrics": _aggregate_metrics(evidence),
        "cases_executed": len(evidence),
        "case_evidence": evidence,
        "acceptance": (
            {
                "provider_submissions": (
                    "SIX"
                    if submissions
                    == V6_SLIM_DIAGNOSTIC_SUBMISSIONS_TOTAL
                    else "FAILED"
                ),
                "technical_pipeline": (
                    "PASSED" if technical_passed else "FAILED"
                ),
                "haiku_typed": _case_acceptance(
                    evidence,
                    "haiku_slim",
                    "typed",
                ),
                "haiku_unclassified": _case_acceptance(
                    evidence,
                    "haiku_slim",
                    "unclassified",
                ),
                "nano_slim_typed": _case_acceptance(
                    evidence,
                    "nano_slim",
                    "typed",
                ),
                "nano_slim_unclassified": _case_acceptance(
                    evidence,
                    "nano_slim",
                    "unclassified",
                ),
                "nano_reversed_typed": _case_acceptance(
                    evidence,
                    "nano_slim_reversed",
                    "typed",
                ),
                "nano_reversed_unclassified": _case_acceptance(
                    evidence,
                    "nano_slim_reversed",
                    "unclassified",
                ),
                "nano_diagnostic_status": _nano_status(evidence),
                "fallback_repair_hidden_retry": "ZERO",
                "full_benchmark": "NOT_RUN",
                "production_admissions_total": 0,
            }
            if terminal
            else None
        ),
        "model_qualification_performed": False,
        "production_admissions_total": 0,
        "exact_safe_evidence_preserved": bool(evidence),
        "raw_provider_envelope_preserved": False,
    }
    return {
        **material,
        "integrity_sha256": sha256_json(material),
    }


def _aggregate_metrics(
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    input_tokens = [
        item["provider_metrics"]["actual_input_tokens"]
        for item in evidence
        if item["provider_metrics"]["actual_input_tokens"] is not None
    ]
    output_tokens = [
        item["provider_metrics"]["actual_output_tokens"]
        for item in evidence
        if item["provider_metrics"]["actual_output_tokens"] is not None
    ]
    costs = [
        Decimal(item["provider_metrics"]["actual_cost_usd"])
        for item in evidence
        if item["provider_metrics"]["actual_cost_usd"] is not None
    ]
    latencies = [
        item["provider_metrics"]["latency_ms"]
        for item in evidence
        if item["provider_metrics"]["latency_ms"] is not None
    ]
    return {
        "actual_input_tokens_total": sum(input_tokens),
        "actual_output_tokens_total": sum(output_tokens),
        "actual_cost_usd": format(sum(costs, Decimal("0")), "f"),
        "latency_total_ms": sum(latencies),
        "latency_average_ms": (
            sum(latencies) // len(latencies) if latencies else 0
        ),
        "latency_max_ms": max(latencies, default=0),
        "calls_with_complete_metrics_total": len(latencies),
    }


def _case_acceptance(
    evidence: list[dict[str, Any]],
    configuration_id: str,
    smoke_role: str,
) -> str:
    matches = [
        item
        for item in evidence
        if item["configuration_id"] == configuration_id
        and item["smoke_role"] == smoke_role
    ]
    if (
        len(matches) == 1
        and matches[0]["technical_pipeline"]["status"] == "PASSED"
        and matches[0]["mechanical_comparison"]["all_fields_match"]
    ):
        return "PASSED"
    return "FAILED_WITH_EXACT_EVIDENCE"


def _nano_status(evidence: list[dict[str, Any]]) -> str:
    nano = [
        item
        for item in evidence
        if item["configuration_id"]
        in {"nano_slim", "nano_slim_reversed"}
    ]
    if len(nano) != 4:
        return "INCOMPLETE"
    normal = [
        item for item in nano if item["configuration_id"] == "nano_slim"
    ]
    normal_passed = all(
        item["technical_pipeline"]["status"] == "PASSED"
        and item["mechanical_comparison"]["all_fields_match"]
        for item in normal
    )
    reversed_items = [
        item
        for item in nano
        if item["configuration_id"] == "nano_slim_reversed"
    ]
    reversed_passed = all(
        item["technical_pipeline"]["status"] == "PASSED"
        and item["mechanical_comparison"]["all_fields_match"]
        for item in reversed_items
    )
    if normal_passed and reversed_passed:
        return "NANO_SLIM_PASSED_ORDER_INVARIANT"
    if normal_passed:
        return "NANO_SLIM_PASSED_ORDER_SENSITIVE"
    typed = {
        item["configuration_id"]: item
        for item in nano
        if item["smoke_role"] == "typed"
    }
    if (
        set(typed) == {"nano_slim", "nano_slim_reversed"}
        and all(
            item["normalization"]["first_visible_choice_selected"]
            for item in typed.values()
        )
        and typed["nano_slim"]["normalized_answer"]
        != typed["nano_slim_reversed"]["normalized_answer"]
    ):
        return "NANO_FIRST_OPTION_BIAS"
    if all(
        item["technical_pipeline"]["status"] == "PASSED"
        and not item["mechanical_comparison"]["all_fields_match"]
        for item in nano
    ):
        return "NANO_SEMANTIC_CAPABILITY_INSUFFICIENT"
    return "NANO_MIXED_OR_ORDER_SENSITIVE"


def _mechanical_comparison(
    *,
    expected: dict[str, Any],
    actual: dict[str, Any] | None,
) -> dict[str, Any]:
    actual_mapping = actual or {}
    fields = []
    for field in _SEMANTIC_FIELDS:
        expected_present = field in expected
        actual_present = field in actual_mapping
        if not expected_present and not actual_present:
            continue
        fields.append(
            {
                "field": field,
                "expected_present": expected_present,
                "expected_value": (
                    copy.deepcopy(expected.get(field))
                    if expected_present
                    else None
                ),
                "actual_present": actual_present,
                "actual_value": (
                    copy.deepcopy(actual_mapping.get(field))
                    if actual_present
                    else None
                ),
                "exact_match": (
                    expected_present
                    and actual_present
                    and expected[field] == actual_mapping[field]
                ),
            }
        )
    return {
        "all_fields_match": actual is not None and expected == actual,
        "fields": fields,
    }


def _semantic_json_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if not isinstance(value, str):
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _failure_code(exc: Exception) -> str:
    value = getattr(exc, "code", None)
    if isinstance(value, str) and value:
        return value[:200]
    return exc.__class__.__name__[:200]


def _required_nonnegative_int(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(code)
    return value


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _required_decimal(value: Any, code: str) -> Decimal:
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError):
        _fail(code)
    if not normalized.is_finite() or normalized < 0:
        _fail(code)
    return normalized


def _optional_decimal_text(value: Any) -> str | None:
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not normalized.is_finite() or normalized < 0:
        return None
    return format(normalized, "f")


def _fail(code: str):
    raise Gate2FinancialSemanticV6SlimDiagnosticError(code)
