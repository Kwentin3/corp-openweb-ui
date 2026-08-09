"""Minimal methodology-driven selection over the official Gate 4 boundary."""

from __future__ import annotations

from typing import Any

from .artifact_models import ArtifactAccessContext
from .gate4_financial_case_cache import Gate4FinancialCaseRuntimeFactory


GATE5_METHODOLOGY_REQUIREMENTS_SCHEMA_VERSION = (
    "broker_reports_gate5_methodology_requirements_v0"
)
GATE5_METHODOLOGY_SELECTION_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_methodology_selection_result_v0"
)
FACTORY_REQUIRED = (
    "Gate5MethodologySelectionRuntimeFactory.create is the only G5.2 "
    "selection entrypoint and must compose "
    "Gate4FinancialCaseRuntimeFactory.create"
)
FORBIDDEN = (
    "G5.2 must not read broker reports, CanonicalArtifact, Gate 3 targets or "
    "Gate 4 SQL; calculate tax; persist methodology or results; or hardcode "
    "tax-scenario fact requirements in runtime control flow"
)

_METHODOLOGY_KEYS = frozenset({"schema_version", "requirements"})
_REQUIREMENT_KEYS = frozenset(
    {"requirement_id", "financial_type", "roles"}
)


class Gate5MethodologySelectionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate5MethodologySelectionRuntimeFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate5MethodologySelectionRuntime":
        gate4_runtime = Gate4FinancialCaseRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        return Gate5MethodologySelectionRuntime(gate4_runtime=gate4_runtime)


class Gate5MethodologySelectionRuntime:
    """Selects Gate 4 facts from an external closed requirement list."""

    def __init__(self, *, gate4_runtime: Any) -> None:
        self._gate4_runtime = gate4_runtime

    def select(
        self,
        *,
        methodology: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        requirements = _validated_requirements(methodology)
        results = [
            self._select_requirement(requirement=requirement, context=context)
            for requirement in requirements
        ]
        return {
            "schema_version": (
                GATE5_METHODOLOGY_SELECTION_RESULT_SCHEMA_VERSION
            ),
            "requirements": results,
            "summary": {
                "requirements_total": len(results),
                "found": sum(item["status"] == "found" for item in results),
                "partial": sum(
                    item["status"] == "partial" for item in results
                ),
                "missing": sum(
                    item["status"] == "missing" for item in results
                ),
            },
        }

    def _select_requirement(
        self,
        *,
        requirement: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        facts = self._gate4_runtime.list_by_financial_type(
            context=context,
            financial_type=requirement["financial_type"],
        )
        matches = [
            _project_fact(fact=fact, roles=requirement["roles"])
            for fact in facts
        ]
        if not matches:
            status = "missing"
        elif any(match["missing_roles"] for match in matches):
            status = "partial"
        else:
            status = "found"
        return {
            "requirement_id": requirement["requirement_id"],
            "financial_type": requirement["financial_type"],
            "roles": list(requirement["roles"]),
            "status": status,
            "matches": matches,
        }


def _validated_requirements(
    methodology: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    if not isinstance(methodology, dict) or set(methodology) != _METHODOLOGY_KEYS:
        raise Gate5MethodologySelectionError(
            "gate5_methodology_requirements_invalid"
        )
    if (
        methodology.get("schema_version")
        != GATE5_METHODOLOGY_REQUIREMENTS_SCHEMA_VERSION
    ):
        raise Gate5MethodologySelectionError(
            "gate5_methodology_requirements_version_unsupported"
        )
    raw_requirements = methodology.get("requirements")
    if not isinstance(raw_requirements, list) or not raw_requirements:
        raise Gate5MethodologySelectionError(
            "gate5_methodology_requirements_invalid"
        )

    requirement_ids: set[str] = set()
    requirements: list[dict[str, Any]] = []
    for raw in raw_requirements:
        requirement = _validated_requirement(raw)
        requirement_id = requirement["requirement_id"]
        if requirement_id in requirement_ids:
            raise Gate5MethodologySelectionError(
                "gate5_methodology_requirement_id_duplicate"
            )
        requirement_ids.add(requirement_id)
        requirements.append(requirement)
    return tuple(requirements)


def _validated_requirement(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _REQUIREMENT_KEYS:
        raise Gate5MethodologySelectionError(
            "gate5_methodology_requirement_invalid"
        )
    requirement_id = _clean_string(value.get("requirement_id"))
    financial_type = _clean_string(value.get("financial_type"))
    raw_roles = value.get("roles")
    if not isinstance(raw_roles, list) or not raw_roles:
        raise Gate5MethodologySelectionError(
            "gate5_methodology_requirement_invalid"
        )
    roles = tuple(_clean_string(role) for role in raw_roles)
    if len(set(roles)) != len(roles):
        raise Gate5MethodologySelectionError(
            "gate5_methodology_requirement_role_duplicate"
        )
    return {
        "requirement_id": requirement_id,
        "financial_type": financial_type,
        "roles": roles,
    }


def _clean_string(value: Any) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise Gate5MethodologySelectionError(
            "gate5_methodology_requirement_invalid"
        )
    return value


def _project_fact(*, fact: Any, roles: tuple[str, ...]) -> dict[str, Any]:
    if not isinstance(fact, dict):
        raise Gate5MethodologySelectionError("gate5_financial_case_fact_invalid")
    fact_id = fact.get("fact_id")
    financial_type = fact.get("financial_type")
    fact_status = fact.get("status")
    raw_roles = fact.get("roles")
    if (
        not isinstance(fact_id, str)
        or not isinstance(financial_type, str)
        or fact_status not in {"role_complete", "role_incomplete"}
        or not isinstance(raw_roles, list)
        or any(not isinstance(item, dict) for item in raw_roles)
    ):
        raise Gate5MethodologySelectionError("gate5_financial_case_fact_invalid")

    by_role: dict[str, dict[str, Any]] = {}
    for item in raw_roles:
        role = item.get("role")
        if not isinstance(role, str) or role in by_role:
            raise Gate5MethodologySelectionError(
                "gate5_financial_case_fact_invalid"
            )
        by_role[role] = item

    values: dict[str, str] = {}
    missing_roles: list[str] = []
    for role in roles:
        item = by_role.get(role)
        if item is None or item.get("status") != "value":
            missing_roles.append(role)
            continue
        value = item.get("value")
        if not isinstance(value, str):
            raise Gate5MethodologySelectionError(
                "gate5_financial_case_fact_invalid"
            )
        values[role] = value

    return {
        "fact_id": fact_id,
        "financial_type": financial_type,
        "fact_status": fact_status,
        "values": values,
        "missing_roles": missing_roles,
    }
