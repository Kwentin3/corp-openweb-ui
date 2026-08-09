"""Read-only G5.2 + G5.3 requirement sufficiency proof adapter."""

from __future__ import annotations

import copy
import re
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate5_methodology_selection import (
    GATE5_METHODOLOGY_REQUIREMENTS_SCHEMA_VERSION,
    Gate5MethodologySelectionRuntime,
    Gate5MethodologySelectionRuntimeFactory,
)
from .gate5_supplemental_fact import (
    Gate5SupplementalFactRuntime,
    Gate5SupplementalFactRuntimeFactory,
)


GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION = (
    "broker_reports_gate5_combined_requirements_v0"
)
GATE5_COMBINED_REQUIREMENT_CHECK_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_combined_requirement_check_result_v0"
)

FACTORY_REQUIRED = (
    "Gate5CombinedRequirementCheckRuntimeFactory.create",
    "Gate5MethodologySelectionRuntimeFactory.create",
    "Gate5SupplementalFactRuntimeFactory.create",
)
FORBIDDEN = (
    "direct Gate 4, ArtifactStore, SQL or source reads",
    "caller-provided user, case, run or workspace identity",
    "untyped Financial Case and Supplemental Fact value merging",
    "Tax Case, generic query, conflict resolution or persistence",
)

_METHODOLOGY_KEYS = frozenset({"schema_version", "requirements"})
_REQUIREMENT_KEYS = frozenset(
    {"requirement_id", "financial_type", "value_key", "subject_ref"}
)
_OPAQUE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FINANCIAL_TYPE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_VALUE_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class Gate5CombinedRequirementCheckError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate5CombinedRequirementCheckRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy

    def create(self) -> "Gate5CombinedRequirementCheckRuntime":
        financial = Gate5MethodologySelectionRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        supplemental = Gate5SupplementalFactRuntimeFactory(
            store=self._store,
            retention_policy=self._retention_policy,
        ).create()
        return Gate5CombinedRequirementCheckRuntime(
            financial=financial,
            supplemental=supplemental,
        )


class Gate5CombinedRequirementCheckRuntime:
    def __init__(
        self,
        *,
        financial: Gate5MethodologySelectionRuntime,
        supplemental: Gate5SupplementalFactRuntime,
    ) -> None:
        self._financial = financial
        self._supplemental = supplemental

    def check(
        self,
        *,
        methodology: dict[str, Any],
        supplemental_fact_refs: list[str],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        requirements = _validated_requirements(methodology)
        refs = _validated_supplemental_refs(supplemental_fact_refs)
        supplemental_facts = self._read_supplemental_facts(
            refs=refs,
            context=context,
        )
        results = [
            self._check_requirement(
                requirement=requirement,
                supplemental_facts=supplemental_facts,
                context=context,
            )
            for requirement in requirements
        ]
        return {
            "schema_version": (
                GATE5_COMBINED_REQUIREMENT_CHECK_RESULT_SCHEMA_VERSION
            ),
            "requirements": results,
            "summary": {
                "requirements_total": len(results),
                "satisfied": sum(
                    item["status"] == "satisfied" for item in results
                ),
                "missing": sum(item["status"] == "missing" for item in results),
            },
        }

    def _read_supplemental_facts(
        self,
        *,
        refs: tuple[str, ...],
        context: ArtifactAccessContext,
    ) -> tuple[dict[str, Any], ...]:
        facts: list[dict[str, Any]] = []
        for supplemental_fact_ref in refs:
            result = self._supplemental.get(
                supplemental_fact_ref=supplemental_fact_ref,
                context=context,
            )
            if result["status"] == "found":
                facts.append(result["fact"])
        return tuple(facts)

    def _check_requirement(
        self,
        *,
        requirement: dict[str, str],
        supplemental_facts: tuple[dict[str, Any], ...],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        financial_result = self._financial.select(
            methodology={
                "schema_version": GATE5_METHODOLOGY_REQUIREMENTS_SCHEMA_VERSION,
                "requirements": [
                    {
                        "requirement_id": requirement["requirement_id"],
                        "financial_type": requirement["financial_type"],
                        "roles": [requirement["value_key"]],
                    }
                ],
            },
            context=context,
        )["requirements"][0]
        if financial_result["status"] == "found":
            source = _financial_source(
                result=financial_result,
                value_key=requirement["value_key"],
            )
            return _requirement_result(
                requirement=requirement,
                status="satisfied",
                financial_status="found",
                supplemental_status="not_needed",
                source=source,
            )

        matching = [
            fact
            for fact in supplemental_facts
            if fact["requirement_ref"] == requirement["requirement_id"]
            and fact["subject_ref"] == requirement["subject_ref"]
            and fact["fact_key"] == requirement["value_key"]
        ]
        if len(matching) > 1:
            raise Gate5CombinedRequirementCheckError(
                "gate5_combined_requirement_supplemental_ambiguous"
            )
        if matching:
            return _requirement_result(
                requirement=requirement,
                status="satisfied",
                financial_status=financial_result["status"],
                supplemental_status="found",
                source=_supplemental_source(matching[0]),
            )
        return _requirement_result(
            requirement=requirement,
            status="missing",
            financial_status=financial_result["status"],
            supplemental_status="missing",
            source=None,
        )


def _validated_requirements(value: Any) -> tuple[dict[str, str], ...]:
    if not isinstance(value, dict) or set(value) != _METHODOLOGY_KEYS:
        raise Gate5CombinedRequirementCheckError(
            "gate5_combined_requirements_invalid"
        )
    if value.get("schema_version") != GATE5_COMBINED_REQUIREMENTS_SCHEMA_VERSION:
        raise Gate5CombinedRequirementCheckError(
            "gate5_combined_requirements_version_unsupported"
        )
    raw_requirements = value.get("requirements")
    if not isinstance(raw_requirements, list) or not raw_requirements:
        raise Gate5CombinedRequirementCheckError(
            "gate5_combined_requirements_invalid"
        )
    requirements: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in raw_requirements:
        requirement = _validated_requirement(raw)
        if requirement["requirement_id"] in seen:
            raise Gate5CombinedRequirementCheckError(
                "gate5_combined_requirement_id_duplicate"
            )
        seen.add(requirement["requirement_id"])
        requirements.append(requirement)
    return tuple(requirements)


def _validated_requirement(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != _REQUIREMENT_KEYS:
        raise Gate5CombinedRequirementCheckError(
            "gate5_combined_requirement_invalid"
        )
    requirement = {
        "requirement_id": value.get("requirement_id"),
        "financial_type": value.get("financial_type"),
        "value_key": value.get("value_key"),
        "subject_ref": value.get("subject_ref"),
    }
    if (
        not _matches(_OPAQUE_REF, requirement["requirement_id"])
        or not _matches(_FINANCIAL_TYPE, requirement["financial_type"])
        or not _matches(_VALUE_KEY, requirement["value_key"])
        or not _matches(_OPAQUE_REF, requirement["subject_ref"])
    ):
        raise Gate5CombinedRequirementCheckError(
            "gate5_combined_requirement_invalid"
        )
    return requirement


def _validated_supplemental_refs(value: Any) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
    ):
        raise Gate5CombinedRequirementCheckError(
            "gate5_combined_supplemental_refs_invalid"
        )
    return tuple(value)


def _matches(pattern: re.Pattern[str], value: Any) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _financial_source(*, result: dict[str, Any], value_key: str) -> dict[str, Any]:
    matches = []
    for match in result["matches"]:
        value = match["values"].get(value_key)
        if value is None:
            raise Gate5CombinedRequirementCheckError(
                "gate5_combined_financial_projection_invalid"
            )
        matches.append(
            {
                "fact_id": match["fact_id"],
                "role": value_key,
                "value": value,
            }
        )
    return {"source_kind": "financial_case", "matches": matches}


def _supplemental_source(fact: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_kind": "supplemental_fact",
        "supplemental_fact_ref": fact["supplemental_fact_ref"],
        "value": copy.deepcopy(fact["value"]),
        "scope_binding": copy.deepcopy(fact["scope_binding"]),
        "provenance": copy.deepcopy(fact["provenance"]),
    }


def _requirement_result(
    *,
    requirement: dict[str, str],
    status: str,
    financial_status: str,
    supplemental_status: str,
    source: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        **requirement,
        "status": status,
        "checks": {
            "financial_case": financial_status,
            "supplemental_facts": supplemental_status,
        },
        "source": copy.deepcopy(source),
    }
