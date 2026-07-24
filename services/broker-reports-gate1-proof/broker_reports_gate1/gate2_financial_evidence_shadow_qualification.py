from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable

from .gate2_financial_context import (
    Gate2FinancialContextProjectionFactory,
)
from .gate2_financial_evidence_decision import (
    Gate2FinancialEvidenceDecisionContract,
)
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    Gate2FinancialEvidenceMaterializerFactory,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_materialization_contracts import (
    Gate2FinancialEvidenceSourcePackage,
    sha256_json,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_model_contracts import (
    Gate2StructuredModelClient,
    gate2_provider_execution_safe_metadata,
)


SHADOW_QUALIFICATION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_evidence_shadow_qualification_v1"
)
SHADOW_PROMPT_CONTRACT_ID = (
    "broker_reports_gate2_financial_evidence_shadow_prompt_v1"
)
FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceShadowDecisionRunnerFactory.create and "
    "Gate2FinancialEvidenceShadowQualificationFactory.create are the only "
    "Goal 7 decision and qualification entrypoints"
)
FORBIDDEN = (
    "Shadow scripts must not call providers directly, repair output, hide "
    "failed scopes, or write customer values into repository evidence"
)


class Gate2FinancialEvidenceShadowQualificationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialEvidenceShadowPrompt:
    prompt_ref: str
    content: str
    hash: str


@dataclass(frozen=True)
class FinancialEvidenceShadowDecisionResult:
    artifact: dict[str, Any]
    source_package: Gate2FinancialEvidenceSourcePackage
    provider_execution: dict[str, Any]
    fallback_used: bool
    repair_attempt_count: int


@dataclass(frozen=True)
class FinancialEvidenceShadowScope:
    source_scope_ref: str
    selected_source_refs: tuple[str, ...]
    candidate_source_value_refs: tuple[str, ...]
    bound_source_value_refs: tuple[str, ...]
    terminal_disposition: str
    artifact_id: str
    provider_status: str = "passed"
    schema_status: str = "passed"
    fallback_used: bool = False
    repair_attempt_count: int = 0


@dataclass(frozen=True)
class FinancialEvidenceShadowQualificationInput:
    authorized_source_refs: tuple[str, ...]
    compatibility_no_financial_refs: tuple[str, ...]
    scopes: tuple[FinancialEvidenceShadowScope, ...]
    source_ready_documents_total: int
    parent_units_total: int
    derived_segments_total: int
    domain_packages_total: int
    canonical_decision_scopes_total: int
    baseline_selected_refs_total: int
    baseline_accounted_refs_total: int
    baseline_uncovered_refs_total: int
    baseline_rejected_packages_total: int
    browser_limits_used: bool
    shadow_only: bool
    private_evidence_hash: str


class Gate2FinancialEvidenceShadowPromptFactory:
    def create(self) -> FinancialEvidenceShadowPrompt:
        content = (
            "You are the bounded Gate 2 financial evidence decision step. "
            "Use only the Registry types, candidate refs, literal source "
            "values, and roles in the embedded package. Never infer missing "
            "values, currency, unit, date, period, or system metadata. "
            "Choose typed_input only when every Registry requirement is "
            "explicitly bound. Use unclassified_financial_input for "
            "financial content that cannot be safely typed; in that case "
            "bind every candidate exactly once using one of its allowed "
            "roles so no value is lost. Use no_financial_input only for "
            "non-financial/header/layout/duplicate content. Use unsupported "
            "only when the source shape or strict schema genuinely prevents "
            "a decision. Return only the strict schema object.\n"
            "{{financial_evidence_package_json}}"
        )
        digest = hashlib.sha256(
            (
                content
                + "\ncontract:"
                + SHADOW_PROMPT_CONTRACT_ID
            ).encode("utf-8")
        ).hexdigest()
        return FinancialEvidenceShadowPrompt(
            prompt_ref="code:" + SHADOW_PROMPT_CONTRACT_ID,
            content=content,
            hash=digest,
        )


class Gate2FinancialEvidenceShadowDecisionRunnerFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        model_client: Gate2StructuredModelClient,
        model_id: str,
        provider_profile_id: str,
    ) -> None:
        self.registry = registry
        self.model_client = model_client
        self.model_id = model_id
        self.provider_profile_id = provider_profile_id

    def create(self) -> "Gate2FinancialEvidenceShadowDecisionRunner":
        if not self.model_id or not self.provider_profile_id:
            _fail("financial_evidence_shadow_provider_config_invalid")
        return Gate2FinancialEvidenceShadowDecisionRunner(
            registry=self.registry,
            model_client=self.model_client,
            model_id=self.model_id,
            provider_profile_id=self.provider_profile_id,
            prompt=Gate2FinancialEvidenceShadowPromptFactory().create(),
        )


class Gate2FinancialEvidenceShadowDecisionRunner:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        model_client: Gate2StructuredModelClient,
        model_id: str,
        provider_profile_id: str,
        prompt: FinancialEvidenceShadowPrompt,
    ) -> None:
        self.registry = registry
        self.model_client = model_client
        self.model_id = model_id
        self.provider_profile_id = provider_profile_id
        self.prompt = prompt

    async def run(
        self,
        *,
        contract: Gate2FinancialEvidenceDecisionContract,
        source_package: Gate2FinancialEvidenceSourcePackage,
        execution_ref: str,
        decision_validation_ref: str,
    ) -> FinancialEvidenceShadowDecisionResult:
        if (
            contract.registry.registry_hash != self.registry.registry_hash
            or contract.package.source_scope_ref
            != source_package.source_scope_ref
        ):
            _fail("financial_evidence_shadow_authority_mismatch")
        result = await self.model_client.extract(
            prompt=self.prompt,
            package=self._model_package(contract, source_package),
            model_id=self.model_id,
            response_format=contract.openai_response_format(),
        )
        if result.fallback_used:
            _fail("financial_evidence_shadow_fallback_forbidden")
        if result.repair_attempt_count:
            _fail("financial_evidence_shadow_repair_forbidden")
        validated = Gate2FinancialEvidenceValidatedDecisionFactory(
            contract=contract
        ).create(result.content)
        artifact = Gate2FinancialEvidenceMaterializerFactory(
            registry=self.registry,
            source_package=source_package,
            execution_metadata=FinancialEvidenceExecutionMetadata(
                execution_ref=execution_ref,
                decision_validation_ref=decision_validation_ref,
            ),
        ).create().materialize(validated_decision=validated)
        metadata = (
            {}
            if result.execution_metadata is None
            else gate2_provider_execution_safe_metadata(
                result.execution_metadata
            )
        )
        return FinancialEvidenceShadowDecisionResult(
            artifact=artifact,
            source_package=source_package,
            provider_execution=metadata,
            fallback_used=False,
            repair_attempt_count=0,
        )

    def _model_package(
        self,
        contract: Gate2FinancialEvidenceDecisionContract,
        source_package: Gate2FinancialEvidenceSourcePackage,
    ) -> dict[str, Any]:
        candidates = {
            item.source_value_ref: item
            for item in contract.package.candidates
        }
        declarations = [
            declaration
            for declaration in self.registry.declarations
            if declaration.input_type_id in contract.eligible_type_ids
        ]
        return {
            "source_scope_ref": source_package.source_scope_ref,
            "llm_context_package": {
                "decision_schema_version": (
                    contract.canonical_schema()["title"]
                ),
                "decision_schema_hash": contract.canonical_schema_hash(),
                "eligible_types": [
                    {
                        "input_type_id": item.input_type_id,
                        "definition": item.definition,
                        "required_roles": list(item.required_roles),
                        "optional_roles": list(item.optional_roles),
                        "date_period_requirement": (
                            item.date_period_requirement
                        ),
                        "currency_unit_requirement": (
                            item.currency_unit_requirement
                        ),
                    }
                    for item in declarations
                ],
                "source_values": [
                    {
                        "source_value_ref": item.source_value_ref,
                        "source_ref": item.source_ref,
                        "value_type": item.value_type,
                        "literal_value": item.literal_value,
                        "allowed_roles": list(
                            candidates[item.source_value_ref].allowed_roles
                        ),
                    }
                    for item in source_package.source_values
                ],
            },
        }


class Gate2FinancialEvidenceShadowQualificationFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        qualification_input: FinancialEvidenceShadowQualificationInput,
        decision_results: Iterable[
            FinancialEvidenceShadowDecisionResult
        ],
    ) -> dict[str, Any]:
        results = tuple(decision_results)
        context = Gate2FinancialContextProjectionFactory(
            registry=self.registry
        ).create(
            materialized_artifacts=tuple(
                item.artifact for item in results
            ),
            source_packages=tuple(
                item.source_package for item in results
            ),
        )
        self._validate_scope_evidence(
            scopes=qualification_input.scopes,
            results=results,
        )
        return self._qualify(
            qualification_input=qualification_input,
            context=context,
        )

    @staticmethod
    def _validate_scope_evidence(
        *,
        scopes: tuple[FinancialEvidenceShadowScope, ...],
        results: tuple[FinancialEvidenceShadowDecisionResult, ...],
    ) -> None:
        by_scope = {
            item.artifact["source_package"]["source_scope_ref"]: item
            for item in results
        }
        if len(by_scope) != len(results) or set(by_scope) != {
            item.source_scope_ref for item in scopes
        }:
            _fail("financial_evidence_shadow_scope_evidence_mismatch")
        for scope in scopes:
            result = by_scope[scope.source_scope_ref]
            artifact = result.artifact
            if (
                scope.artifact_id != artifact["artifact_id"]
                or scope.terminal_disposition
                != artifact["terminal_disposition"]
                or set(scope.candidate_source_value_refs)
                != {
                    item.source_value_ref
                    for item in result.source_package.source_values
                }
                or set(scope.bound_source_value_refs)
                != set(artifact["coverage"]["bound_source_value_refs"])
                or scope.fallback_used != result.fallback_used
                or scope.repair_attempt_count
                != result.repair_attempt_count
            ):
                _fail("financial_evidence_shadow_scope_evidence_mismatch")

    def _qualify(
        self,
        *,
        qualification_input: FinancialEvidenceShadowQualificationInput,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        scopes = qualification_input.scopes
        authorized = set(qualification_input.authorized_source_refs)
        package_refs = {
            ref for scope in scopes for ref in scope.selected_source_refs
        }
        compatibility_refs = set(
            qualification_input.compatibility_no_financial_refs
        ) - package_refs
        terminal_refs = package_refs | compatibility_refs
        interpretation_owners: dict[str, set[str]] = {}
        for scope in scopes:
            if scope.terminal_disposition not in {
                "typed_input",
                "unclassified_financial_input",
            }:
                continue
            for ref in scope.selected_source_refs:
                interpretation_owners.setdefault(ref, set()).add(
                    scope.source_scope_ref
                )
        duplicate_interpretations = sum(
            len(owners) - 1
            for owners in interpretation_owners.values()
            if len(owners) > 1
        )
        disposition_by_ref: dict[str, set[str]] = {
            ref: {"no_financial_input"} for ref in compatibility_refs
        }
        for scope in scopes:
            for ref in scope.selected_source_refs:
                disposition_by_ref.setdefault(ref, set()).add(
                    scope.terminal_disposition
                )
        contradictions = sum(
            len(values) > 1 for values in disposition_by_ref.values()
        )
        unclassified = [
            scope
            for scope in scopes
            if scope.terminal_disposition
            == "unclassified_financial_input"
        ]
        retained = sum(
            set(scope.bound_source_value_refs)
            == set(scope.candidate_source_value_refs)
            for scope in unclassified
        )
        status_counts = Counter(
            scope.terminal_disposition for scope in scopes
        )
        uncovered = authorized - terminal_refs
        excess = terminal_refs - authorized
        provider_failures = sum(
            scope.provider_status != "passed" for scope in scopes
        )
        schema_failures = sum(
            scope.schema_status != "passed" for scope in scopes
        )
        fallback = sum(scope.fallback_used for scope in scopes)
        repairs = sum(scope.repair_attempt_count for scope in scopes)
        context_scopes = context["scope_coverage"]["source_scopes_total"]
        checks = {
            "authorized_scope_complete": (
                qualification_input.source_ready_documents_total > 0
                and qualification_input.parent_units_total > 0
                and qualification_input.derived_segments_total > 0
                and qualification_input.domain_packages_total > 0
                and len(authorized)
                == qualification_input.baseline_selected_refs_total
            ),
            "terminal_all_source_refs": not uncovered and not excess,
            "unclassified_value_retention_100_percent": (
                retained == len(unclassified)
            ),
            "contradictory_decisions_zero": contradictions == 0,
            "ownership_conflicts_zero": duplicate_interpretations == 0,
            "duplicate_interpretations_zero": (
                duplicate_interpretations == 0
                and context["scope_coverage"][
                    "duplicate_interpretation_representations_total"
                ]
                == 0
            ),
            "unexplained_rejected_scopes_zero": (
                provider_failures == 0 and schema_failures == 0
            ),
            "fallback_zero": fallback == 0,
            "hidden_repair_zero": repairs == 0,
            "coverage_regression_zero": (
                len(terminal_refs)
                >= qualification_input.baseline_accounted_refs_total
                and not uncovered
            ),
            "context_terminal_all_canonical_scopes": (
                context_scopes
                == qualification_input.canonical_decision_scopes_total
                == len(scopes)
            ),
            "browser_limits_unused": (
                qualification_input.browser_limits_used is False
            ),
            "shadow_only": qualification_input.shadow_only is True,
        }
        payload: dict[str, Any] = {
            "schema_version": SHADOW_QUALIFICATION_SCHEMA_VERSION,
            "status": "passed" if all(checks.values()) else "failed",
            "registry_version": self.registry.registry_version,
            "registry_hash": self.registry.registry_hash,
            "scope": {
                "source_ready_documents_total": (
                    qualification_input.source_ready_documents_total
                ),
                "parent_units_total": (
                    qualification_input.parent_units_total
                ),
                "derived_segments_total": (
                    qualification_input.derived_segments_total
                ),
                "domain_packages_total": (
                    qualification_input.domain_packages_total
                ),
                "canonical_decision_scopes_total": len(scopes),
                "authorized_source_refs_total": len(authorized),
            },
            "terminal": {
                "accounted_source_refs_total": len(terminal_refs),
                "uncovered_source_refs_total": len(uncovered),
                "excess_source_refs_total": len(excess),
                "status_counts": {
                    key: status_counts.get(key, 0)
                    for key in (
                        "typed_input",
                        "unclassified_financial_input",
                        "no_financial_input",
                        "unsupported",
                    )
                },
                "compatibility_no_financial_refs_total": len(
                    compatibility_refs
                ),
                "compatibility_refs_superseded_total": len(
                    set(
                        qualification_input.compatibility_no_financial_refs
                    )
                    & package_refs
                ),
            },
            "quality": {
                "unclassified_scopes_total": len(unclassified),
                "unclassified_scopes_fully_retained_total": retained,
                "contradictory_decisions_total": contradictions,
                "ownership_conflicts_total": duplicate_interpretations,
                "duplicate_interpretations_total": (
                    duplicate_interpretations
                ),
                "provider_failures_total": provider_failures,
                "schema_failures_total": schema_failures,
                "fallback_total": fallback,
                "hidden_repair_total": repairs,
            },
            "baseline": {
                "selected_refs_total": (
                    qualification_input.baseline_selected_refs_total
                ),
                "accounted_refs_total": (
                    qualification_input.baseline_accounted_refs_total
                ),
                "uncovered_refs_total": (
                    qualification_input.baseline_uncovered_refs_total
                ),
                "rejected_packages_total": (
                    qualification_input.baseline_rejected_packages_total
                ),
            },
            "checks": checks,
            "private_evidence_hash": (
                qualification_input.private_evidence_hash
            ),
            "customer_values_in_receipt": False,
        }
        payload["qualification_hash"] = sha256_json(payload)
        return payload


def shadow_scope_from_result(
    *,
    result: FinancialEvidenceShadowDecisionResult,
    selected_source_refs: tuple[str, ...],
) -> FinancialEvidenceShadowScope:
    artifact = result.artifact
    return FinancialEvidenceShadowScope(
        source_scope_ref=artifact["source_package"]["source_scope_ref"],
        selected_source_refs=tuple(sorted(set(selected_source_refs))),
        candidate_source_value_refs=tuple(
            sorted(
                item.source_value_ref
                for item in result.source_package.source_values
            )
        ),
        bound_source_value_refs=tuple(
            artifact["coverage"]["bound_source_value_refs"]
        ),
        terminal_disposition=artifact["terminal_disposition"],
        artifact_id=artifact["artifact_id"],
        fallback_used=result.fallback_used,
        repair_attempt_count=result.repair_attempt_count,
    )


def private_evidence_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceShadowQualificationError(code)
