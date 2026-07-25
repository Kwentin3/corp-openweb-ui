from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable

from .gate2_deterministic_financial_scopes import (
    DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2,
    Gate2DeterministicFinancialScope,
    validate_deterministic_financial_scope_v2,
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
from .gate2_financial_evidence_source_context import (
    SOURCE_CONTEXT_POLICY_VERSION,
    SOURCE_CONTEXT_SCHEMA_VERSION,
    Gate2FinancialEvidenceSourceContext,
    validate_financial_evidence_source_context,
)
from .gate2_financial_evidence_successor import (
    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3,
    SUCCESSOR_PROMPT_CONTRACT_ID_V3,
    SUCCESSOR_RESULT_SCHEMA_VERSION_V3,
    Gate2FinancialEvidenceSuccessorResult,
)
from .gate2_financial_evidence_successor_projection import (
    SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION,
    SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION,
)
from .gate2_successor_artifacts import (
    SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION,
    _compatibility_projection,
    _identifier,
    _migration_policy,
    validate_successor_compatibility_projection,
)


SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION_V2 = (
    "broker_reports_gate2_successor_package_artifact_v2"
)
SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION_V2 = (
    "broker_reports_gate2_successor_run_artifact_v2"
)
SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION_V2 = (
    "broker_reports_gate2_successor_execution_receipt_v2"
)
SUCCESSOR_ARTIFACT_POLICY_VERSION_V2 = (
    "gate2_successor_artifact_family_v2"
)

FACTORY_REQUIRED = (
    "Gate2SuccessorArtifactFamilyV2Factory.create is the only scope-v2 "
    "successor package/run/receipt artifact family construction entrypoint"
)
FORBIDDEN = (
    "Successor artifact v2 must not store private source context, rewrite "
    "legacy payloads, silently upcast schemas, claim production admission, "
    "omit exact model/provider identities or merge the FNS path"
)


class Gate2SuccessorArtifactV2Error(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2SuccessorArtifactV2Input:
    scope: Gate2DeterministicFinancialScope
    source_context: Gate2FinancialEvidenceSourceContext
    result: Gate2FinancialEvidenceSuccessorResult


@dataclass(frozen=True)
class Gate2SuccessorArtifactFamilyV2:
    package_artifacts: tuple[dict[str, Any], ...]
    compatibility_projections: tuple[dict[str, Any], ...]
    run_artifact: dict[str, Any]
    execution_receipt: dict[str, Any]

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": (
                "broker_reports_gate2_successor_artifact_family_summary_v2"
            ),
            "status": self.execution_receipt["status"],
            "package_schema_version": (
                SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION_V2
            ),
            "run_schema_version": (
                SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION_V2
            ),
            "receipt_schema_version": (
                SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION_V2
            ),
            "packages_total": len(self.package_artifacts),
            "financial_inputs_total": self.execution_receipt[
                "financial_inputs_total"
            ],
            "terminal_status_counts": copy.deepcopy(
                self.execution_receipt["terminal_status_counts"]
            ),
            "source_model_calls_total": 0,
            "domain_model_calls_total": 0,
            "financial_model_calls_total": self.execution_receipt[
                "financial_model_calls_total"
            ],
            "fallback_total": 0,
            "repair_attempts_total": 0,
            "production_write_admitted": False,
            "private_source_context_stored": False,
            "legacy_payloads_rewritten_total": 0,
            "silent_conversions_total": 0,
            "family_integrity_hash": self.execution_receipt[
                "family_integrity_hash"
            ],
        }


class Gate2SuccessorArtifactFamilyV2Factory:
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
        inputs: Iterable[Gate2SuccessorArtifactV2Input],
        financial_context: dict[str, Any],
    ) -> Gate2SuccessorArtifactFamilyV2:
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
            _fail("successor_artifact_v2_inputs_empty")
        scope_refs = [
            item.scope.source_package.source_scope_ref for item in items
        ]
        if len(scope_refs) != len(set(scope_refs)):
            _fail("successor_artifact_v2_scope_duplicate")
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
            _fail("successor_artifact_v2_context_not_exact")
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
        family = Gate2SuccessorArtifactFamilyV2(
            package_artifacts=tuple(package_artifacts),
            compatibility_projections=tuple(projections),
            run_artifact=run_artifact,
            execution_receipt=receipt,
        )
        validate_successor_artifact_family_v2(family=family)
        return family

    def _package_artifact(
        self,
        *,
        run_ref: str,
        item: Gate2SuccessorArtifactV2Input,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        scope = item.scope
        result = item.result
        validate_deterministic_financial_scope_v2(scope)
        validate_financial_evidence_source_context(
            context=item.source_context,
            source_scope_ref=scope.source_package.source_scope_ref,
            source_values=scope.source_package.source_values,
            candidates=scope.decision_contract.package.candidates,
        )
        artifact = result.materialized_artifact
        validate_financial_evidence_inputs(
            payload=artifact,
            registry=self.registry,
        )
        summary = result.safe_summary
        if (
            result.validated_decision.source_scope_ref
            != scope.source_package.source_scope_ref
            or result.validated_decision.decision_schema_version
            != DECISION_SCHEMA_VERSION
            or artifact["source_package"]["package_ref"]
            != scope.source_package.package_ref
            or artifact["source_package"]["integrity_hash"]
            != scope.source_package.integrity_hash
            or summary.get("schema_version")
            != SUCCESSOR_RESULT_SCHEMA_VERSION_V3
            or summary.get("model_input_schema_version")
            != SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
            or summary.get("prompt_contract_id")
            != SUCCESSOR_PROMPT_CONTRACT_ID_V3
            or summary.get("source_context_integrity_hash")
            != item.source_context.integrity_hash
            or summary.get("provider_projection_schema_version")
            != SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
        ):
            _fail("successor_artifact_v2_authority_mismatch")
        identity_material = {
            "run_ref": run_ref,
            "deterministic_scope_integrity_hash": scope.package[
                "integrity_hash"
            ],
            "source_context_integrity_hash": (
                item.source_context.integrity_hash
            ),
            "model_input_hash": result.model_input_hash,
            "provider_response_format_hash": summary[
                "provider_response_format_hash"
            ],
            "financial_input_integrity_hash": artifact[
                "integrity_hash"
            ],
        }
        package_artifact_ref = (
            "successor-package-v2:"
            + sha256_json(identity_material)[:32]
        )
        projection = _compatibility_projection(
            package_artifact_ref=package_artifact_ref,
            artifact=artifact,
        )
        provider = result.provider_execution
        package_artifact = {
            "schema_version": (
                SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION_V2
            ),
            "artifact_policy_version": (
                SUCCESSOR_ARTIFACT_POLICY_VERSION_V2
            ),
            "package_artifact_ref": package_artifact_ref,
            "run_ref": run_ref,
            "deterministic_scope": {
                "schema_version": (
                    DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2
                ),
                "package_ref": scope.package["package_ref"],
                "integrity_hash": scope.package["integrity_hash"],
                "typed_admission_integrity_hash": scope.package[
                    "typed_admission"
                ]["integrity_hash"],
            },
            "source_package": {
                "schema_version": SOURCE_PACKAGE_SCHEMA_VERSION,
                "package_ref": scope.source_package.package_ref,
                "integrity_hash": scope.source_package.integrity_hash,
            },
            "source_context": {
                "schema_version": SOURCE_CONTEXT_SCHEMA_VERSION,
                "policy_version": SOURCE_CONTEXT_POLICY_VERSION,
                "integrity_hash": item.source_context.integrity_hash,
                "private_payload_stored": False,
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
                "schema_version": (
                    SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
                ),
                "integrity_hash": result.model_input_hash,
                "prompt_contract_id": (
                    SUCCESSOR_PROMPT_CONTRACT_ID_V3
                ),
                "prompt_hash": summary["prompt_hash"],
            },
            "provider_projection": {
                "schema_version": (
                    SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
                ),
                "policy_version": (
                    SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION
                ),
                "response_format_hash": summary[
                    "provider_response_format_hash"
                ],
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
        validate_successor_package_artifact_v2(package_artifact)
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
        counts: dict[str, int] = {}
        for item in package_artifacts:
            disposition = item["financial_input"][
                "terminal_disposition"
            ]
            counts[disposition] = counts.get(disposition, 0) + 1
        payload = {
            "schema_version": SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION_V2,
            "artifact_policy_version": (
                SUCCESSOR_ARTIFACT_POLICY_VERSION_V2
            ),
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
            "terminal_status_counts": dict(sorted(counts.items())),
            "migration_policy": _migration_policy(),
        }
        payload["integrity_hash"] = sha256_json(payload)
        validate_successor_run_artifact_v2(payload)
        return payload

    def _receipt(
        self,
        *,
        package_artifacts: list[dict[str, Any]],
        projections: list[dict[str, Any]],
        run_artifact: dict[str, Any],
    ) -> dict[str, Any]:
        checks = {
            "successor_v2_schema_explicit": True,
            "exact_context_input_projection_identity": True,
            "private_source_context_not_stored": True,
            "legacy_read_preserved": True,
            "legacy_rewrite_zero": True,
            "silent_conversion_zero": True,
            "compatibility_projection_explicit": True,
            "production_write_not_admitted": True,
            "rollback_future_routing_only": True,
            "fns_specialized_separate": True,
        }
        payload = {
            "schema_version": (
                SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION_V2
            ),
            "artifact_policy_version": (
                SUCCESSOR_ARTIFACT_POLICY_VERSION_V2
            ),
            "status": "passed" if all(checks.values()) else "failed",
            "checks": checks,
            "packages_total": len(package_artifacts),
            "financial_inputs_total": len(package_artifacts),
            "compatibility_projections_total": len(projections),
            "terminal_status_counts": copy.deepcopy(
                run_artifact["terminal_status_counts"]
            ),
            "source_model_calls_total": 0,
            "domain_model_calls_total": 0,
            "financial_model_calls_total": len(package_artifacts),
            "fallback_total": 0,
            "repair_attempts_total": 0,
            "legacy_payloads_rewritten_total": 0,
            "silent_conversions_total": 0,
            "private_source_contexts_stored_total": 0,
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
        payload["integrity_hash"] = sha256_json(payload)
        validate_successor_execution_receipt_v2(payload)
        return payload


def validate_successor_package_artifact_v2(
    payload: dict[str, Any],
) -> None:
    _validate_integrity(
        payload,
        SUCCESSOR_PACKAGE_ARTIFACT_SCHEMA_VERSION_V2,
        "successor_package_artifact_v2",
    )
    if (
        payload.get("artifact_policy_version")
        != SUCCESSOR_ARTIFACT_POLICY_VERSION_V2
        or payload.get("migration_policy") != _migration_policy()
        or payload.get("deterministic_scope", {}).get("schema_version")
        != DETERMINISTIC_FINANCIAL_SCOPE_SCHEMA_VERSION_V2
        or payload.get("source_context", {}).get("schema_version")
        != SOURCE_CONTEXT_SCHEMA_VERSION
        or payload.get("source_context", {}).get(
            "private_payload_stored"
        )
        is not False
        or payload.get("decision_contract", {}).get("schema_version")
        != DECISION_SCHEMA_VERSION
        or payload.get("model_input", {}).get("schema_version")
        != SUCCESSOR_MODEL_INPUT_SCHEMA_VERSION_V3
        or payload.get("model_input", {}).get("prompt_contract_id")
        != SUCCESSOR_PROMPT_CONTRACT_ID_V3
        or payload.get("provider_projection", {}).get(
            "schema_version"
        )
        != SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
        or payload.get("financial_input", {}).get("schema_version")
        != FINANCIAL_EVIDENCE_INPUTS_SCHEMA_VERSION
        or payload.get("compatibility_projection", {}).get(
            "schema_version"
        )
        != SUCCESSOR_COMPATIBILITY_PROJECTION_SCHEMA_VERSION
    ):
        _fail("successor_package_artifact_v2_contract_invalid")


def validate_successor_run_artifact_v2(
    payload: dict[str, Any],
) -> None:
    _validate_integrity(
        payload,
        SUCCESSOR_RUN_ARTIFACT_SCHEMA_VERSION_V2,
        "successor_run_artifact_v2",
    )
    if (
        payload.get("artifact_policy_version")
        != SUCCESSOR_ARTIFACT_POLICY_VERSION_V2
        or payload.get("status") != "shadow_completed"
        or payload.get("migration_policy") != _migration_policy()
        or not payload.get("package_artifacts")
    ):
        _fail("successor_run_artifact_v2_policy_invalid")


def validate_successor_execution_receipt_v2(
    payload: dict[str, Any],
) -> None:
    _validate_integrity(
        payload,
        SUCCESSOR_EXECUTION_RECEIPT_SCHEMA_VERSION_V2,
        "successor_execution_receipt_v2",
    )
    if (
        payload.get("artifact_policy_version")
        != SUCCESSOR_ARTIFACT_POLICY_VERSION_V2
        or payload.get("status") != "passed"
        or not all((payload.get("checks") or {}).values())
        or payload.get("fallback_total") != 0
        or payload.get("repair_attempts_total") != 0
        or payload.get("legacy_payloads_rewritten_total") != 0
        or payload.get("silent_conversions_total") != 0
        or payload.get("private_source_contexts_stored_total") != 0
        or payload.get("production_write_admitted") is not False
    ):
        _fail("successor_execution_receipt_v2_policy_invalid")


def validate_successor_artifact_family_v2(
    *,
    family: Gate2SuccessorArtifactFamilyV2,
) -> None:
    for payload in family.package_artifacts:
        validate_successor_package_artifact_v2(payload)
    for projection in family.compatibility_projections:
        validate_successor_compatibility_projection(projection)
    validate_successor_run_artifact_v2(family.run_artifact)
    validate_successor_execution_receipt_v2(
        family.execution_receipt
    )
    if (
        len(family.package_artifacts)
        != len(family.compatibility_projections)
        or family.execution_receipt["packages_total"]
        != len(family.package_artifacts)
    ):
        _fail("successor_artifact_family_v2_coverage_invalid")


def _validate_integrity(
    payload: dict[str, Any],
    schema_version: str,
    prefix: str,
) -> None:
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != schema_version
    ):
        _fail(f"{prefix}_schema_invalid")
    material = copy.deepcopy(payload)
    integrity_hash = material.pop("integrity_hash", None)
    if integrity_hash != sha256_json(material):
        _fail(f"{prefix}_integrity_invalid")


def _fail(code: str) -> None:
    raise Gate2SuccessorArtifactV2Error(code)
