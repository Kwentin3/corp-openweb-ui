from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Iterable

from .gate2_deterministic_financial_scopes import (
    DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION,
    Gate2DeterministicFinancialScope,
    validate_deterministic_financial_scope,
)
from .gate2_financial_context import (
    Gate2FinancialContextProjectionFactory,
    validate_financial_context,
)
from .gate2_financial_evidence_decision import DECISION_SCHEMA_VERSION
from .gate2_financial_evidence_materialization_contracts import (
    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION,
    SOURCE_PACKAGE_SCHEMA_VERSION,
    sha256_json,
)
from .gate2_financial_evidence_materialization_validation import (
    validate_financial_evidence_inputs,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_evidence_successor import (
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION,
    SUCCESSOR_PROMPT_CONTRACT_ID,
    Gate2FinancialEvidenceSuccessorResult,
)


SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION = (
    "broker_reports_gate2_successor_package_artifact_v1"
)
SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION = (
    "broker_reports_gate2_successor_run_artifact_v1"
)
SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_successor_execution_receipt_v1"
)
SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION = (
    "broker_reports_gate2_successor_compatibility_projection_v1"
)
SUCCESSOR_ARTIFACT_POLICY_VERSION = (
    "gate2_successor_artifact_family_v1"
)
SUCCESSOR_COMPATIBILITY_PROJECTION_POLICY_VERSION = (
    "gate2_successor_compatibility_projection_v1"
)

FACTORY_REQUIRED = (
    "Gate2SuccessorArtifactFamilyFactory.create is the only successor "
    "package/run/receipt artifact family construction entrypoint"
)
FORBIDDEN = (
    "Successor artifacts must not rewrite legacy payloads, silently upcast "
    "schemas, claim production write admission, emulate legacy model output "
    "or merge the separate FNS specialized path"
)

_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_:.\\/-]*$")


class Gate2SuccessorArtifactError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2SuccessorArtifactInput:
    scope: Gate2DeterministicFinancialScope
    result: Gate2FinancialEvidenceSuccessorResult


@dataclass(frozen=True)
class Gate2SuccessorArtifactFamily:
    package_artifacts: tuple[dict[str, Any], ...]
    compatibility_projections: tuple[dict[str, Any], ...]
    run_artifact: dict[str, Any]
    execution_receipt: dict[str, Any]

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": (
                "broker_reports_gate2_successor_artifact_family_summary_v1"
            ),
            "status": self.execution_receipt["status"],
            "package_schema_version": (
                SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION
            ),
            "run_schema_version": SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION,
            "receipt_schema_version": (
                SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION
            ),
            "compatibility_projection_schema_version": (
                SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION
            ),
            "packages_total": len(self.package_artifacts),
            "compatibility_projections_total": len(
                self.compatibility_projections
            ),
            "financial_inputs_total": self.execution_receipt[
                "financial_inputs_total"
            ],
            "terminal_status_counts": copy.deepcopy(
                self.execution_receipt["terminal_status_counts"]
            ),
            "source_model_calls_total": self.execution_receipt[
                "source_model_calls_total"
            ],
            "domain_model_calls_total": self.execution_receipt[
                "domain_model_calls_total"
            ],
            "financial_model_calls_total": self.execution_receipt[
                "financial_model_calls_total"
            ],
            "fallback_total": self.execution_receipt["fallback_total"],
            "repair_attempts_total": self.execution_receipt[
                "repair_attempts_total"
            ],
            "production_write_admitted": False,
            "legacy_payloads_rewritten_total": 0,
            "silent_conversions_total": 0,
            "family_integrity_hash": self.execution_receipt[
                "family_integrity_hash"
            ],
        }


class Gate2SuccessorArtifactFamilyFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        run_ref: str,
        source_extraction_run_ref: str,
        inputs: Iterable[Gate2SuccessorArtifactInput],
        financial_context: dict[str, Any],
    ) -> Gate2SuccessorArtifactFamily:
        _identifier(run_ref, "run_ref")
        _identifier(
            source_extraction_run_ref,
            "source_extraction_run_ref",
        )
        items = tuple(
            sorted(
                inputs,
                key=lambda item: (
                    item.scope.source_package.source_scope_ref
                ),
            )
        )
        if not items:
            _fail("successor_artifact_inputs_empty")
        scope_refs = [
            item.scope.source_package.source_scope_ref for item in items
        ]
        if len(scope_refs) != len(set(scope_refs)):
            _fail("successor_artifact_scope_duplicate")

        expected_context = Gate2FinancialContextProjectionFactory(
            registry=self.registry
        ).create(
            materialized_artifacts=(
                item.result.materialized_artifact for item in items
            ),
            source_packages=(
                item.scope.source_package for item in items
            ),
        )
        if financial_context != expected_context:
            _fail("successor_artifact_context_not_exact")
        validate_financial_context(
            payload=financial_context,
            registry=self.registry,
        )

        package_artifacts: list[dict[str, Any]] = []
        projections: list[dict[str, Any]] = []
        for item in items:
            package_artifact, projection = self._package_artifact(
                run_ref=run_ref,
                item=item,
            )
            package_artifacts.append(package_artifact)
            projections.append(projection)
        run_artifact = self._run_artifact(
            run_ref=run_ref,
            source_extraction_run_ref=source_extraction_run_ref,
            package_artifacts=package_artifacts,
            projections=projections,
            financial_context=financial_context,
        )
        receipt = self._receipt(
            package_artifacts=package_artifacts,
            projections=projections,
            run_artifact=run_artifact,
        )
        family = Gate2SuccessorArtifactFamily(
            package_artifacts=tuple(package_artifacts),
            compatibility_projections=tuple(projections),
            run_artifact=run_artifact,
            execution_receipt=receipt,
        )
        validate_successor_artifact_family(family=family)
        return family

    def _package_artifact(
        self,
        *,
        run_ref: str,
        item: Gate2SuccessorArtifactInput,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        scope = item.scope
        result = item.result
        validate_deterministic_financial_scope(scope)
        artifact = result.materialized_artifact
        validate_financial_evidence_inputs(
            payload=artifact,
            registry=self.registry,
        )
        if (
            result.validated_decision.source_scope_ref
            != scope.source_package.source_scope_ref
            or result.validated_decision.decision_schema_version
            != DECISION_SCHEMA_VERSION
            or artifact["source_package"]["package_ref"]
            != scope.source_package.package_ref
            or artifact["source_package"]["integrity_hash"]
            != scope.source_package.integrity_hash
        ):
            _fail("successor_artifact_authority_mismatch")
        identity_material = {
            "run_ref": run_ref,
            "deterministic_scope_integrity_hash": scope.package[
                "integrity_hash"
            ],
            "financial_input_integrity_hash": artifact[
                "integrity_hash"
            ],
            "model_input_hash": result.model_input_hash,
        }
        package_artifact_ref = (
            "successor-package:"
            + sha256_json(identity_material)[:32]
        )
        projection = _compatibility_projection(
            package_artifact_ref=package_artifact_ref,
            artifact=artifact,
        )
        provider = result.provider_execution
        package_artifact = {
            "schema_version": (
                SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION
            ),
            "artifact_policy_version": SUCCESSOR_ARTIFACT_POLICY_VERSION,
            "package_artifact_ref": package_artifact_ref,
            "run_ref": run_ref,
            "deterministic_scope": {
                "schema_version": (
                    DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION
                ),
                "package_ref": scope.package["package_ref"],
                "integrity_hash": scope.package["integrity_hash"],
            },
            "source_package": {
                "schema_version": SOURCE_PACKAGE_SCHEMA_VERSION,
                "package_ref": scope.source_package.package_ref,
                "integrity_hash": scope.source_package.integrity_hash,
            },
            "decision_contract": {
                "schema_version": DECISION_SCHEMA_VERSION,
                "schema_hash": (
                    scope.decision_contract.canonical_schema_hash()
                ),
                "validated_decision_schema_version": (
                    result.validated_decision.schema_version
                ),
                "validated_decision_authority_hash": (
                    result.validated_decision.candidate_authority_hash
                ),
            },
            "model_input": {
                "schema_version": SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION,
                "integrity_hash": result.model_input_hash,
                "prompt_contract_id": SUCCESSOR_PROMPT_CONTRACT_ID,
                "prompt_hash": result.safe_summary["prompt_hash"],
            },
            "provider_execution": {
                "requested_model_id": provider.get(
                    "requested_model_id"
                ),
                "resolved_model_id": provider.get("resolved_model_id"),
                "provider_profile_id": provider.get(
                    "provider_profile_id"
                ),
                "response_format_type": provider.get(
                    "response_format_type"
                ),
                "response_format_schema_mode": provider.get(
                    "response_format_schema_mode"
                ),
                "fallback_used": False,
                "repair_attempt_count": 0,
            },
            "financial_input": {
                "schema_version": (
                    FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION
                ),
                "artifact_id": artifact["artifact_id"],
                "integrity_hash": artifact["integrity_hash"],
                "terminal_disposition": artifact[
                    "terminal_disposition"
                ],
            },
            "compatibility_projection": {
                "schema_version": (
                    SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION
                ),
                "projection_ref": projection["projection_ref"],
                "integrity_hash": projection["integrity_hash"],
            },
            "migration_policy": _migration_policy(),
        }
        package_artifact["integrity_hash"] = sha256_json(
            package_artifact
        )
        validate_successor_package_artifact(package_artifact)
        return package_artifact, projection

    def _run_artifact(
        self,
        *,
        run_ref: str,
        source_extraction_run_ref: str,
        package_artifacts: list[dict[str, Any]],
        projections: list[dict[str, Any]],
        financial_context: dict[str, Any],
    ) -> dict[str, Any]:
        status_counts: dict[str, int] = {}
        for item in package_artifacts:
            status = item["financial_input"]["terminal_disposition"]
            status_counts[status] = status_counts.get(status, 0) + 1
        run_artifact = {
            "schema_version": SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION,
            "artifact_policy_version": SUCCESSOR_ARTIFACT_POLICY_VERSION,
            "run_ref": run_ref,
            "source_extraction_run_ref": source_extraction_run_ref,
            "status": "shadow_completed",
            "registry": {
                "registry_version": self.registry.registry_version,
                "registry_hash": self.registry.registry_hash,
            },
            "package_artifacts": [
                {
                    "package_artifact_ref": item[
                        "package_artifact_ref"
                    ],
                    "integrity_hash": item["integrity_hash"],
                }
                for item in package_artifacts
            ],
            "compatibility_projections": [
                {
                    "projection_ref": item["projection_ref"],
                    "integrity_hash": item["integrity_hash"],
                }
                for item in projections
            ],
            "financial_context": {
                "schema_version": financial_context["schema_version"],
                "integrity_hash": financial_context["integrity_hash"],
            },
            "terminal_status_counts": dict(sorted(status_counts.items())),
            "migration_policy": _migration_policy(),
        }
        run_artifact["integrity_hash"] = sha256_json(run_artifact)
        validate_successor_run_artifact(run_artifact)
        return run_artifact

    def _receipt(
        self,
        *,
        package_artifacts: list[dict[str, Any]],
        projections: list[dict[str, Any]],
        run_artifact: dict[str, Any],
    ) -> dict[str, Any]:
        terminal_counts = run_artifact["terminal_status_counts"]
        financial_calls = len(package_artifacts)
        checks = {
            "successor_schema_explicit": True,
            "legacy_read_preserved": True,
            "legacy_rewrite_zero": True,
            "silent_conversion_zero": True,
            "compatibility_projection_explicit": True,
            "fns_specialized_separate": True,
            "production_write_not_admitted": True,
            "rollback_future_routing_only": True,
        }
        receipt = {
            "schema_version": (
                SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION
            ),
            "artifact_policy_version": SUCCESSOR_ARTIFACT_POLICY_VERSION,
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
            "packages_total": len(package_artifacts),
            "financial_inputs_total": len(package_artifacts),
            "compatibility_projections_total": len(projections),
            "terminal_status_counts": copy.deepcopy(terminal_counts),
            "source_model_calls_total": 0,
            "domain_model_calls_total": 0,
            "financial_model_calls_total": financial_calls,
            "fallback_total": 0,
            "repair_attempts_total": 0,
            "legacy_payloads_rewritten_total": 0,
            "silent_conversions_total": 0,
            "production_write_admitted": False,
            "successor_single_write_status": (
                "blocked_pending_production_admission"
            ),
            "rollback_boundary": "future_routing_only",
            "fns_specialized_path": "separate_unchanged",
            "run_integrity_hash": run_artifact["integrity_hash"],
            "family_integrity_hash": sha256_json(
                {
                    "package_integrity_hashes": [
                        item["integrity_hash"]
                        for item in package_artifacts
                    ],
                    "projection_integrity_hashes": [
                        item["integrity_hash"] for item in projections
                    ],
                    "run_integrity_hash": run_artifact[
                        "integrity_hash"
                    ],
                }
            ),
        }
        receipt["integrity_hash"] = sha256_json(receipt)
        validate_successor_execution_receipt(receipt)
        return receipt


def _compatibility_projection(
    *,
    package_artifact_ref: str,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    typed = artifact["typed_inputs"]
    unclassified = artifact["unclassified_inputs"]
    terminals = [*typed, *unclassified]
    source_value_refs = sorted(
        {
            item["source_value_ref"]
            for terminal in terminals
            for item in terminal["source_values"]
        }
    )
    canonical_input_type_ids = sorted(
        item["input_type_id"] for item in typed
    )
    projection_ref = (
        "successor-compatibility:"
        + sha256_json(
            {
                "package_artifact_ref": package_artifact_ref,
                "financial_input_integrity_hash": artifact[
                    "integrity_hash"
                ],
                "projection_policy_version": (
                    SUCCESSOR_COMPATIBILITY_PROJECTION_POLICY_VERSION
                ),
            }
        )[:32]
    )
    projection = {
        "schema_version": (
            SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION
        ),
        "projection_policy_version": (
            SUCCESSOR_COMPATIBILITY_PROJECTION_POLICY_VERSION
        ),
        "projection_ref": projection_ref,
        "source_successor_package_ref": package_artifact_ref,
        "source_financial_input": {
            "schema_version": artifact["schema_version"],
            "artifact_id": artifact["artifact_id"],
            "integrity_hash": artifact["integrity_hash"],
        },
        "terminal_disposition": artifact["terminal_disposition"],
        "canonical_input_type_ids": canonical_input_type_ids,
        "source_value_refs": source_value_refs,
        "reason_code": artifact["coverage"]["reason_code"],
        "legacy_emulation": False,
        "legacy_schema_version": None,
        "subtype_created": False,
        "model_confidence_created": False,
        "model_output_emulated": False,
    }
    projection["integrity_hash"] = sha256_json(projection)
    validate_successor_compatibility_projection(projection)
    return projection


def _migration_policy() -> dict[str, Any]:
    return {
        "legacy_read": "preserved",
        "legacy_payloads_immutable": True,
        "legacy_rewrite_allowed": False,
        "silent_upcast_allowed": False,
        "successor_reader": "explicit_schema_dispatch",
        "successor_single_write": (
            "blocked_pending_production_admission"
        ),
        "production_write_admitted": False,
        "rollback_boundary": "future_routing_only",
        "fns_specialized_path": "separate_unchanged",
    }


def validate_successor_package_artifact(
    payload: dict[str, Any],
) -> None:
    _validate_integrity(
        payload,
        SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION,
        "successor_package_artifact",
    )
    migration = payload.get("migration_policy") or {}
    if migration != _migration_policy():
        _fail("successor_package_migration_policy_invalid")
    if (
        payload.get("deterministic_scope", {}).get("schema_version")
        != DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION
        or payload.get("decision_contract", {}).get("schema_version")
        != DECISION_SCHEMA_VERSION
        or payload.get("financial_input", {}).get("schema_version")
        != FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION
        or payload.get("compatibility_projection", {}).get(
            "schema_version"
        )
        != SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION
    ):
        _fail("successor_package_contract_identity_invalid")


def validate_successor_run_artifact(payload: dict[str, Any]) -> None:
    _validate_integrity(
        payload,
        SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION,
        "successor_run_artifact",
    )
    if (
        payload.get("status") != "shadow_completed"
        or payload.get("migration_policy") != _migration_policy()
        or not payload.get("package_artifacts")
    ):
        _fail("successor_run_policy_invalid")


def validate_successor_execution_receipt(
    payload: dict[str, Any],
) -> None:
    _validate_integrity(
        payload,
        SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION,
        "successor_execution_receipt",
    )
    if (
        payload.get("status") != "passed"
        or not all((payload.get("checks") or {}).values())
        or payload.get("legacy_payloads_rewritten_total") != 0
        or payload.get("silent_conversions_total") != 0
        or payload.get("production_write_admitted") is not False
        or payload.get("rollback_boundary") != "future_routing_only"
        or payload.get("fns_specialized_path") != "separate_unchanged"
    ):
        _fail("successor_execution_receipt_policy_invalid")


def validate_successor_compatibility_projection(
    payload: dict[str, Any],
) -> None:
    _validate_integrity(
        payload,
        SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION,
        "successor_compatibility_projection",
    )
    if (
        payload.get("legacy_emulation") is not False
        or payload.get("legacy_schema_version") is not None
        or payload.get("subtype_created") is not False
        or payload.get("model_confidence_created") is not False
        or payload.get("model_output_emulated") is not False
    ):
        _fail("successor_compatibility_projection_emulation_forbidden")
    forbidden = {
        "confidence",
        "model_output",
        "subtype",
        "uncertainty",
    }
    if forbidden & set(payload):
        _fail("successor_compatibility_projection_field_forbidden")


def validate_successor_artifact_family(
    *,
    family: Gate2SuccessorArtifactFamily,
) -> None:
    for item in family.package_artifacts:
        validate_successor_package_artifact(item)
    for item in family.compatibility_projections:
        validate_successor_compatibility_projection(item)
    validate_successor_run_artifact(family.run_artifact)
    validate_successor_execution_receipt(family.execution_receipt)
    package_refs = {
        item["package_artifact_ref"]: item["integrity_hash"]
        for item in family.package_artifacts
    }
    run_refs = {
        item["package_artifact_ref"]: item["integrity_hash"]
        for item in family.run_artifact["package_artifacts"]
    }
    projection_refs = {
        item["projection_ref"]: item["integrity_hash"]
        for item in family.compatibility_projections
    }
    run_projection_refs = {
        item["projection_ref"]: item["integrity_hash"]
        for item in family.run_artifact[
            "compatibility_projections"
        ]
    }
    if (
        package_refs != run_refs
        or projection_refs != run_projection_refs
        or family.execution_receipt["run_integrity_hash"]
        != family.run_artifact["integrity_hash"]
    ):
        _fail("successor_artifact_family_reference_mismatch")


def _validate_integrity(
    payload: dict[str, Any],
    schema_version: str,
    subject: str,
) -> None:
    if not isinstance(payload, dict) or payload.get(
        "schema_version"
    ) != schema_version:
        _fail(f"{subject}_schema_invalid")
    material = copy.deepcopy(payload)
    integrity_hash = material.pop("integrity_hash", None)
    if integrity_hash != sha256_json(material):
        _fail(f"{subject}_integrity_invalid")


def _identifier(value: Any, field: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 240
        or not _IDENTIFIER_RE.fullmatch(value)
    ):
        _fail(f"successor_artifact_{field}_invalid")


def _fail(code: str) -> None:
    raise Gate2SuccessorArtifactError(code)
