"""Minimal access-scoped persistence boundary for one supplemental fact."""

from __future__ import annotations

import copy
import re
from typing import Any

from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStorePort,
    ArtifactStoreError,
    RetentionPolicy,
    new_artifact_id,
)
from .artifact_resolver import ArtifactResolver


GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION = (
    "broker_reports_gate5_supplemental_fact_input_v0"
)
GATE5_SUPPLEMENTAL_FACT_SCHEMA_VERSION = (
    "broker_reports_gate5_supplemental_fact_v0"
)
GATE5_SUPPLEMENTAL_FACT_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_supplemental_fact_result_v0"
)
GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE = (
    "broker_reports_gate5_supplemental_fact_v0"
)

FACTORY_REQUIRED = (
    "Gate5SupplementalFactRuntimeFactory.create",
    "ArtifactStoreFactory.create supplies the existing store",
    "ArtifactResolver.resolve enforces access and lifecycle on read",
)
FORBIDDEN = (
    "caller-provided user, case, run or workspace identity",
    "SqliteArtifactStoreAdapter construction or direct SQL",
    "Gate4FinancialCaseFactV1 or Gate 4 SQL mutation",
    "LLM, chat, Knowledge or Tax Case persistence",
)

_INPUT_KEYS = frozenset(
    {"schema_version", "requirement_ref", "subject_ref", "fact_key", "value"}
)
_VALUE_KEYS = frozenset({"kind", "amount", "currency"})
_FACT_KEYS = frozenset(
    {
        "schema_version",
        "supplemental_fact_ref",
        "requirement_ref",
        "subject_ref",
        "fact_key",
        "value",
        "scope_binding",
        "provenance",
    }
)
_SCOPE_KEYS = frozenset(
    {"scope_kind", "case_id", "normalization_run_id", "workspace_model_id"}
)
_PROVENANCE = {
    "source_kind": "user_provided_supplemental",
    "provided_by": "authenticated_user",
    "gate4_derived": False,
    "captured_via": "gate5_supplemental_fact_boundary_v0",
}
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_FACT_KEY = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MONEY = re.compile(r"^(?:0|[1-9][0-9]{0,17})(?:\.[0-9]{1,2})?$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_ARTIFACT_REF = re.compile(r"^art_[A-Za-z0-9_-]{32}$")


class Gate5SupplementalFactError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate5SupplementalFactRuntimeFactory:
    """Compose the proof boundary over the existing ArtifactStore owner."""

    def __init__(
        self, *, store: ArtifactStorePort, retention_policy: RetentionPolicy
    ) -> None:
        self._store = store
        self._retention_policy = retention_policy

    def create(self) -> "Gate5SupplementalFactRuntime":
        if not isinstance(self._retention_policy, RetentionPolicy):
            raise Gate5SupplementalFactError(
                "gate5_supplemental_fact_retention_policy_required"
            )
        return Gate5SupplementalFactRuntime(
            store=self._store,
            resolver=ArtifactResolver(self._store),
            retention_policy=self._retention_policy,
        )


class Gate5SupplementalFactRuntime:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        resolver: ArtifactResolver,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._store = store
        self._resolver = resolver
        self._retention_policy = retention_policy

    def put(
        self,
        *,
        supplemental_input: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        scope = _validated_context(context)
        value = _validated_input(supplemental_input)
        supplemental_fact_ref = new_artifact_id()
        fact = {
            "schema_version": GATE5_SUPPLEMENTAL_FACT_SCHEMA_VERSION,
            "supplemental_fact_ref": supplemental_fact_ref,
            "requirement_ref": value["requirement_ref"],
            "subject_ref": value["subject_ref"],
            "fact_key": value["fact_key"],
            "value": copy.deepcopy(value["value"]),
            "scope_binding": scope,
            "provenance": copy.deepcopy(_PROVENANCE),
        }
        record = ArtifactRecord(
            artifact_id=supplemental_fact_ref,
            artifact_type=GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=None,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=None,
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=self._retention_policy,
            access_policy={
                "scope": "case_private",
                "requires_user_id": True,
                "requires_case_id": True,
            },
            validation_status="validated",
            lifecycle_status="private_ready",
            payload=fact,
            safe_metadata={
                "schema_version": GATE5_SUPPLEMENTAL_FACT_SCHEMA_VERSION,
                "source_kind": _PROVENANCE["source_kind"],
                "gate4_derived": False,
            },
        )
        self._store.put_record(record)
        persisted = self._resolve_fact(
            supplemental_fact_ref=supplemental_fact_ref,
            context=context,
        )
        return _result(
            status="stored",
            supplemental_fact_ref=supplemental_fact_ref,
            fact=persisted,
        )

    def get(
        self,
        *,
        supplemental_fact_ref: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        _validated_context(context)
        _validated_artifact_ref(supplemental_fact_ref)
        try:
            fact = self._resolve_fact(
                supplemental_fact_ref=supplemental_fact_ref,
                context=context,
            )
        except ArtifactStoreError as exc:
            if exc.code != "artifact_not_found":
                raise
            return _result(
                status="missing",
                supplemental_fact_ref=supplemental_fact_ref,
                fact=None,
            )
        return _result(
            status="found",
            supplemental_fact_ref=supplemental_fact_ref,
            fact=fact,
        )

    def _resolve_fact(
        self,
        *,
        supplemental_fact_ref: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        resolved = self._resolver.resolve(supplemental_fact_ref, context)
        record = resolved["record"]
        if record.artifact_type != GATE5_SUPPLEMENTAL_FACT_ARTIFACT_TYPE:
            raise Gate5SupplementalFactError(
                "gate5_supplemental_fact_artifact_type_invalid"
            )
        return _validated_persisted_fact(
            resolved["payload"],
            supplemental_fact_ref=supplemental_fact_ref,
            context=context,
        )


def _validated_context(context: ArtifactAccessContext) -> dict[str, Any]:
    if not isinstance(context, ArtifactAccessContext):
        raise Gate5SupplementalFactError(
            "gate5_supplemental_fact_trusted_case_context_required"
        )
    identities = (context.user_id, context.normalization_run_id, context.case_id)
    if (
        not all(isinstance(item, str) and item and item == item.strip() for item in identities)
        or not context.allow_private
    ):
        raise Gate5SupplementalFactError(
            "gate5_supplemental_fact_trusted_case_context_required"
        )
    if context.workspace_model_id is not None and (
        not isinstance(context.workspace_model_id, str)
        or not context.workspace_model_id
        or context.workspace_model_id != context.workspace_model_id.strip()
    ):
        raise Gate5SupplementalFactError(
            "gate5_supplemental_fact_trusted_case_context_required"
        )
    return {
        "scope_kind": "case",
        "case_id": context.case_id,
        "normalization_run_id": context.normalization_run_id,
        "workspace_model_id": context.workspace_model_id,
    }


def _validated_input(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _INPUT_KEYS:
        raise Gate5SupplementalFactError("gate5_supplemental_fact_input_invalid")
    if value.get("schema_version") != GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION:
        raise Gate5SupplementalFactError(
            "gate5_supplemental_fact_input_version_unsupported"
        )
    if not _valid_ref(value.get("requirement_ref")) or not _valid_ref(
        value.get("subject_ref")
    ):
        raise Gate5SupplementalFactError("gate5_supplemental_fact_input_invalid")
    fact_key = value.get("fact_key")
    money = value.get("value")
    if (
        not isinstance(fact_key, str)
        or _FACT_KEY.fullmatch(fact_key) is None
        or not isinstance(money, dict)
        or set(money) != _VALUE_KEYS
        or money.get("kind") != "money"
        or not isinstance(money.get("amount"), str)
        or _MONEY.fullmatch(money["amount"]) is None
        or not isinstance(money.get("currency"), str)
        or _CURRENCY.fullmatch(money["currency"]) is None
    ):
        raise Gate5SupplementalFactError("gate5_supplemental_fact_input_invalid")
    return copy.deepcopy(value)


def _validated_persisted_fact(
    value: Any,
    *,
    supplemental_fact_ref: str,
    context: ArtifactAccessContext,
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _FACT_KEYS
        or value.get("schema_version") != GATE5_SUPPLEMENTAL_FACT_SCHEMA_VERSION
        or value.get("supplemental_fact_ref") != supplemental_fact_ref
        or not isinstance(value.get("scope_binding"), dict)
        or set(value["scope_binding"]) != _SCOPE_KEYS
        or value["scope_binding"] != _validated_context(context)
        or value.get("provenance") != _PROVENANCE
    ):
        raise Gate5SupplementalFactError(
            "gate5_supplemental_fact_payload_invalid"
        )
    _validated_input(
        {
            "schema_version": GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
            "requirement_ref": value.get("requirement_ref"),
            "subject_ref": value.get("subject_ref"),
            "fact_key": value.get("fact_key"),
            "value": value.get("value"),
        }
    )
    return copy.deepcopy(value)


def _validated_artifact_ref(value: Any) -> str:
    if not isinstance(value, str) or _ARTIFACT_REF.fullmatch(value) is None:
        raise Gate5SupplementalFactError(
            "gate5_supplemental_fact_ref_invalid"
        )
    return value


def _valid_ref(value: Any) -> bool:
    return isinstance(value, str) and _REF.fullmatch(value) is not None


def _result(
    *,
    status: str,
    supplemental_fact_ref: str,
    fact: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": GATE5_SUPPLEMENTAL_FACT_RESULT_SCHEMA_VERSION,
        "status": status,
        "supplemental_fact_ref": supplemental_fact_ref,
        "fact": copy.deepcopy(fact),
    }
