"""Resolve closed hash-pinned methodologies and retain the G5.7 adapter."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
from importlib import resources
import json
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate5_methodology_calculation import (
    GATE5_CALCULATION_METHODOLOGY_SCHEMA_VERSION,
    Gate5MethodologyCalculationRuntime,
    Gate5MethodologyCalculationRuntimeFactory,
)


GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION = (
    "broker_reports_gate5_trusted_methodology_ref_v0"
)
GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_trusted_calculation_result_v0"
)
GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER = "repository_versioned_package_resource"
GATE5_TRUSTED_METHODOLOGY_ID = "ru-ndfl-securities-proof"
GATE5_TRUSTED_METHODOLOGY_VERSION = "2026.0-experimental"
GATE5_TRUSTED_METHODOLOGY_RESOURCE = (
    "gate5_tax_methodology.ru_ndfl_securities_proof.v0.json"
)
GATE5_TRUSTED_METHODOLOGY_RESOURCE_SHA256 = (
    "220844b6e39678b4e26e6f5ff4eec3784b0086213767f1444b832fe99cecf4e9"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_SCHEMA_VERSION = (
    "broker_reports_gate5_securities_disposal_tax_model_methodology_v0"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID = (
    "ru-ndfl-securities-tax-model-proof"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION = "2026.0-experimental"
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE = (
    "gate5_tax_methodology.ru_ndfl_securities_tax_model_proof.v0.json"
)
GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE_SHA256 = (
    "a1b2db00a78e92e1b47d873b5841edd6c34794a09f0a483c0cb0bda3abd6fc63"
)

FACTORY_REQUIRED = (
    "Gate5TrustedMethodologyAuthorityFactory.create is the only trusted Tax "
    "Methodology resolution entrypoint",
    "Gate5TrustedMethodologyCalculationRuntimeFactory.create composes trusted "
    "resolution with Gate5MethodologyCalculationRuntimeFactory.create",
)
FORBIDDEN = (
    "caller-supplied methodology contents, caller-supplied authority hash or "
    "implicit default methodology",
    "direct Gate 4, supplemental, ArtifactStore, SQL, OpenWebUI table, source "
    "or provider reads",
    "methodology CRUD, lifecycle workflow, mutable registry, new DB, LLM, DSL "
    "or calculator behavior changes",
)

_REFERENCE_KEYS = frozenset({"schema_version", "methodology_id", "methodology_version"})


class Gate5TrustedMethodologyError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _PublishedMethodologyResource:
    resource_name: str
    resource_sha256: str
    schema_version: str


_PUBLISHED_METHODOLOGIES = {
    (
        GATE5_TRUSTED_METHODOLOGY_ID,
        GATE5_TRUSTED_METHODOLOGY_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=GATE5_TRUSTED_METHODOLOGY_RESOURCE,
        resource_sha256=GATE5_TRUSTED_METHODOLOGY_RESOURCE_SHA256,
        schema_version=GATE5_CALCULATION_METHODOLOGY_SCHEMA_VERSION,
    ),
    (
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID,
        GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION,
    ): _PublishedMethodologyResource(
        resource_name=GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE,
        resource_sha256=(
            GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE_SHA256
        ),
        schema_version=(GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_SCHEMA_VERSION),
    ),
}


class Gate5TrustedMethodologyAuthorityFactory:
    @staticmethod
    def create() -> "Gate5TrustedMethodologyAuthority":
        return Gate5TrustedMethodologyAuthority()


class Gate5TrustedMethodologyAuthority:
    def resolve(self, methodology_ref: dict[str, Any]) -> dict[str, Any]:
        identity = _validated_reference(methodology_ref)
        published = _PUBLISHED_METHODOLOGIES.get(identity)
        if published is None:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_not_published"
            )
        try:
            raw = (
                resources.files(__package__)
                .joinpath(published.resource_name)
                .read_bytes()
            )
        except (FileNotFoundError, OSError) as exc:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_resource_unavailable"
            ) from exc
        resource_sha256 = hashlib.sha256(raw).hexdigest()
        if resource_sha256 != published.resource_sha256:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_resource_hash_mismatch"
            )
        try:
            methodology: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_resource_json_invalid"
            ) from exc
        if (
            not isinstance(methodology, dict)
            or methodology.get("schema_version") != published.schema_version
            or methodology.get("methodology_id") != identity[0]
            or methodology.get("methodology_version") != identity[1]
        ):
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_resource_identity_mismatch"
            )
        try:
            projection_sha256 = _projection_sha256(methodology)
        except (RecursionError, TypeError, ValueError) as exc:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_resource_json_invalid"
            ) from exc
        return {
            "authority_binding": {
                "authority_owner": GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER,
                "methodology_id": identity[0],
                "methodology_version": identity[1],
                "resource_sha256": resource_sha256,
                "projection_sha256": projection_sha256,
            },
            "methodology": copy.deepcopy(methodology),
        }


class Gate5TrustedMethodologyCalculationRuntimeFactory:
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

    def create(self) -> "Gate5TrustedMethodologyCalculationRuntime":
        authority = Gate5TrustedMethodologyAuthorityFactory.create()
        calculator = Gate5MethodologyCalculationRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
            retention_policy=self._retention_policy,
        ).create()
        return Gate5TrustedMethodologyCalculationRuntime(
            authority=authority,
            calculator=calculator,
        )


class Gate5TrustedMethodologyCalculationRuntime:
    def __init__(
        self,
        *,
        authority: Gate5TrustedMethodologyAuthority,
        calculator: Gate5MethodologyCalculationRuntime,
    ) -> None:
        self._authority = authority
        self._calculator = calculator

    def calculate(
        self,
        *,
        methodology_ref: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        resolved = self._authority.resolve(methodology_ref)
        result = self._calculator.calculate(
            methodology=resolved["methodology"],
            context=context,
        )
        authority_binding = resolved["authority_binding"]
        if result.get("methodology_binding") != {
            "methodology_id": authority_binding["methodology_id"],
            "methodology_version": authority_binding["methodology_version"],
            "projection_sha256": authority_binding["projection_sha256"],
        }:
            raise Gate5TrustedMethodologyError(
                "gate5_trusted_methodology_result_binding_mismatch"
            )
        return {
            "schema_version": GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION,
            "status": "calculated",
            "authority_binding": copy.deepcopy(authority_binding),
            "calculation_result": copy.deepcopy(result),
        }


def _validated_reference(value: Any) -> tuple[str, str]:
    if (
        not isinstance(value, dict)
        or set(value) != _REFERENCE_KEYS
        or value.get("schema_version") != GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION
        or not isinstance(value.get("methodology_id"), str)
        or not value["methodology_id"]
        or not isinstance(value.get("methodology_version"), str)
        or not value["methodology_version"]
    ):
        raise Gate5TrustedMethodologyError("gate5_trusted_methodology_ref_invalid")
    return value["methodology_id"], value["methodology_version"]


def _projection_sha256(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_TRUSTED_CALCULATION_RESULT_SCHEMA_VERSION",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_ID",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_RESOURCE_SHA256",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_SCHEMA_VERSION",
    "GATE5_SECURITIES_DISPOSAL_TAX_MODEL_METHODOLOGY_VERSION",
    "GATE5_TRUSTED_METHODOLOGY_AUTHORITY_OWNER",
    "GATE5_TRUSTED_METHODOLOGY_ID",
    "GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION",
    "GATE5_TRUSTED_METHODOLOGY_RESOURCE",
    "GATE5_TRUSTED_METHODOLOGY_RESOURCE_SHA256",
    "GATE5_TRUSTED_METHODOLOGY_VERSION",
    "Gate5TrustedMethodologyAuthority",
    "Gate5TrustedMethodologyAuthorityFactory",
    "Gate5TrustedMethodologyCalculationRuntime",
    "Gate5TrustedMethodologyCalculationRuntimeFactory",
    "Gate5TrustedMethodologyError",
]
