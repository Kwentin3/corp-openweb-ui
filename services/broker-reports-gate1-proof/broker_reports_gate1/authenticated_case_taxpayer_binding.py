"""Authenticated case-to-taxpayer identity owner over an injected provider."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Protocol

from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
    ArtifactStorePort,
    RetentionPolicy,
)
from .artifact_resolver import ArtifactResolver


AUTHENTICATED_CASE_TAXPAYER_ASSERTION_SCHEMA_VERSION = (
    "broker_reports_authenticated_case_taxpayer_assertion_v1"
)
AUTHENTICATED_CASE_TAXPAYER_BINDING_SCHEMA_VERSION = (
    "broker_reports_authenticated_case_taxpayer_binding_v1"
)
AUTHENTICATED_CASE_TAXPAYER_BINDING_ARTIFACT_TYPE = (
    AUTHENTICATED_CASE_TAXPAYER_BINDING_SCHEMA_VERSION
)

FACTORY_REQUIRED = (
    "AuthenticatedCaseTaxpayerBindingRuntimeFactory.create is the only owner "
    "adapter from an injected authenticated identity provider to a persisted "
    "case-to-taxpayer binding",
)
FORBIDDEN = (
    "case hash, user ID, operation subject or caller-supplied taxpayer ref as "
    "taxpayer identity; timestamp/list/ref ordering; tax or filing meaning",
)

_IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:@/-]{0,255}$")
_INN = re.compile(r"^[0-9]{12}$")
_ASSERTION_KEYS = frozenset(
    {
        "schema_version",
        "assertion_id",
        "authenticated_user_id",
        "case_id",
        "taxpayer_scope_ref",
        "taxpayer",
        "origin",
    }
)
_TAXPAYER_KEYS = frozenset(
    {"inn", "last_name", "first_name", "middle_name"}
)
_ORIGIN_KEYS = frozenset({"kind", "provider_id"})
_BINDING_KEYS = frozenset(
    {
        "schema_version",
        "assertion_id",
        "scope",
        "taxpayer",
        "origin",
        "provider_assertion_sha256",
        "binding_sha256",
        "binding_ref",
    }
)


class AuthenticatedCaseTaxpayerBindingError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AuthenticatedTaxpayerIdentityProvider(Protocol):
    """External authentication/case owner boundary, not a caller DTO."""

    def current_assertions(
        self, *, context: ArtifactAccessContext
    ) -> tuple[dict[str, Any], ...]: ...


class AuthenticatedCaseTaxpayerBindingRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        retention_policy: RetentionPolicy,
        identity_provider: AuthenticatedTaxpayerIdentityProvider,
    ) -> None:
        self._store = store
        self._retention_policy = retention_policy
        self._identity_provider = identity_provider

    def create(self) -> "AuthenticatedCaseTaxpayerBindingRuntime":
        if not isinstance(self._retention_policy, RetentionPolicy):
            _fail("authenticated_taxpayer_binding_retention_policy_required")
        if self._identity_provider is None:
            _fail("authenticated_taxpayer_binding_provider_required")
        return AuthenticatedCaseTaxpayerBindingRuntime(
            store=self._store,
            retention_policy=self._retention_policy,
            identity_provider=self._identity_provider,
        )


class AuthenticatedCaseTaxpayerBindingRuntime:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        retention_policy: RetentionPolicy,
        identity_provider: AuthenticatedTaxpayerIdentityProvider,
    ) -> None:
        self._store = store
        self._retention_policy = retention_policy
        self._identity_provider = identity_provider
        self._resolver = ArtifactResolver(store)

    def publish_current(
        self, *, context: ArtifactAccessContext
    ) -> tuple[dict[str, Any], ...]:
        bindings = self._current_bindings(context=context)
        for binding in bindings:
            self._put_or_reuse(binding=binding, context=context)
        return tuple(copy.deepcopy(item) for item in bindings)

    def validate_current(
        self,
        *,
        binding: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        validated = _validated_binding(binding)
        try:
            resolved = self._resolver.resolve_case(validated["binding_ref"], context)
        except ArtifactStoreError as exc:
            raise AuthenticatedCaseTaxpayerBindingError(
                "authenticated_taxpayer_binding_owner_artifact_invalid"
            ) from exc
        if (
            resolved["record"].artifact_type
            != AUTHENTICATED_CASE_TAXPAYER_BINDING_ARTIFACT_TYPE
            or resolved["payload"] != validated
        ):
            _fail("authenticated_taxpayer_binding_owner_artifact_invalid")
        current = {
            item["binding_ref"]: item
            for item in self._current_bindings(context=context)
        }
        if current.get(validated["binding_ref"]) != validated:
            _fail("authenticated_taxpayer_binding_stale")
        return copy.deepcopy(validated)

    def _current_bindings(
        self, *, context: ArtifactAccessContext
    ) -> tuple[dict[str, Any], ...]:
        if not isinstance(context, ArtifactAccessContext) or not context.case_id:
            _fail("authenticated_taxpayer_binding_case_context_required")
        raw = self._identity_provider.current_assertions(context=context)
        if not isinstance(raw, tuple) or not raw:
            _fail("authenticated_taxpayer_binding_missing")
        bindings = tuple(
            _binding_from_assertion(value, context=context) for value in raw
        )
        refs = [item["taxpayer_scope_ref"] for item in (b["scope"] for b in bindings)]
        if len(refs) != len(set(refs)):
            _fail("authenticated_taxpayer_binding_ambiguous")
        return tuple(
            sorted(bindings, key=lambda item: item["scope"]["taxpayer_scope_ref"])
        )

    def _put_or_reuse(
        self,
        *,
        binding: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> None:
        artifact_ref = binding["binding_ref"]
        existing = self._store.get_record_unchecked(artifact_ref)
        if existing is not None:
            try:
                resolved = self._resolver.resolve_case(artifact_ref, context)
            except ArtifactStoreError as exc:
                raise AuthenticatedCaseTaxpayerBindingError(
                    "authenticated_taxpayer_binding_artifact_conflict"
                ) from exc
            if (
                resolved["record"].artifact_type
                != AUTHENTICATED_CASE_TAXPAYER_BINDING_ARTIFACT_TYPE
                or resolved["payload"] != binding
            ):
                _fail("authenticated_taxpayer_binding_artifact_conflict")
            return
        self._store.put_record(
            ArtifactRecord(
                artifact_id=artifact_ref,
                artifact_type=AUTHENTICATED_CASE_TAXPAYER_BINDING_ARTIFACT_TYPE,
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
                    "requires_workspace_model_id_when_present": True,
                },
                validation_status="validated",
                lifecycle_status="private_ready",
                payload=copy.deepcopy(binding),
                safe_metadata={
                    "schema_version": binding["schema_version"],
                    "provider_id": binding["origin"]["provider_id"],
                },
            )
        )


def _binding_from_assertion(
    value: Any, *, context: ArtifactAccessContext
) -> dict[str, Any]:
    assertion = _validated_assertion(value)
    if (
        assertion["authenticated_user_id"] != context.user_id
        or assertion["case_id"] != context.case_id
    ):
        _fail("authenticated_taxpayer_binding_context_mismatch")
    base = {
        "schema_version": AUTHENTICATED_CASE_TAXPAYER_BINDING_SCHEMA_VERSION,
        "assertion_id": assertion["assertion_id"],
        "scope": {
            "authenticated_user_id": assertion["authenticated_user_id"],
            "case_id": assertion["case_id"],
            "taxpayer_scope_ref": assertion["taxpayer_scope_ref"],
        },
        "taxpayer": copy.deepcopy(assertion["taxpayer"]),
        "origin": copy.deepcopy(assertion["origin"]),
        "provider_assertion_sha256": _sha(assertion),
    }
    binding_sha256 = _sha(base)
    return {
        **base,
        "binding_sha256": binding_sha256,
        "binding_ref": "auth_taxpayer_binding_" + binding_sha256[:32],
    }


def _validated_assertion(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _ASSERTION_KEYS:
        _fail("authenticated_taxpayer_assertion_invalid")
    taxpayer = value.get("taxpayer")
    origin = value.get("origin")
    if (
        value.get("schema_version")
        != AUTHENTICATED_CASE_TAXPAYER_ASSERTION_SCHEMA_VERSION
        or not all(
            _identifier(value.get(key))
            for key in (
                "assertion_id",
                "authenticated_user_id",
                "case_id",
                "taxpayer_scope_ref",
            )
        )
        or not isinstance(taxpayer, dict)
        or set(taxpayer) != _TAXPAYER_KEYS
        or _INN.fullmatch(str(taxpayer.get("inn") or "")) is None
        or not all(
            isinstance(taxpayer.get(key), str) and taxpayer[key].strip()
            for key in ("last_name", "first_name")
        )
        or not isinstance(taxpayer.get("middle_name"), str)
        or not isinstance(origin, dict)
        or set(origin) != _ORIGIN_KEYS
        or origin.get("kind") != "authenticated_identity_provider"
        or not _identifier(origin.get("provider_id"))
    ):
        _fail("authenticated_taxpayer_assertion_invalid")
    return copy.deepcopy(value)


def _validated_binding(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _BINDING_KEYS:
        _fail("authenticated_taxpayer_binding_invalid")
    scope = value.get("scope")
    if (
        value.get("schema_version")
        != AUTHENTICATED_CASE_TAXPAYER_BINDING_SCHEMA_VERSION
        or not isinstance(scope, dict)
        or set(scope)
        != {"authenticated_user_id", "case_id", "taxpayer_scope_ref"}
        or not all(_identifier(item) for item in scope.values())
        or not _identifier(value.get("assertion_id"))
        or not isinstance(value.get("taxpayer"), dict)
        or set(value["taxpayer"]) != _TAXPAYER_KEYS
        or _INN.fullmatch(str(value["taxpayer"].get("inn") or "")) is None
        or not all(
            isinstance(value["taxpayer"].get(key), str)
            and value["taxpayer"][key].strip()
            for key in ("last_name", "first_name")
        )
        or not isinstance(value["taxpayer"].get("middle_name"), str)
        or not isinstance(value.get("origin"), dict)
        or set(value["origin"]) != _ORIGIN_KEYS
        or value["origin"].get("kind") != "authenticated_identity_provider"
        or not _identifier(value["origin"].get("provider_id"))
        or not _sha256(value.get("provider_assertion_sha256"))
        or not _sha256(value.get("binding_sha256"))
        or value.get("binding_ref")
        != "auth_taxpayer_binding_" + str(value.get("binding_sha256"))[:32]
    ):
        _fail("authenticated_taxpayer_binding_invalid")
    base = {
        key: copy.deepcopy(value[key])
        for key in (
            "schema_version",
            "assertion_id",
            "scope",
            "taxpayer",
            "origin",
            "provider_assertion_sha256",
        )
    }
    if value["binding_sha256"] != _sha(base):
        _fail("authenticated_taxpayer_binding_invalid")
    assertion = {
        "schema_version": AUTHENTICATED_CASE_TAXPAYER_ASSERTION_SCHEMA_VERSION,
        "assertion_id": value["assertion_id"],
        **copy.deepcopy(scope),
        "taxpayer": copy.deepcopy(value["taxpayer"]),
        "origin": copy.deepcopy(value["origin"]),
    }
    if value["provider_assertion_sha256"] != _sha(assertion):
        _fail("authenticated_taxpayer_binding_invalid")
    return copy.deepcopy(value)


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _sha(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fail(code: str) -> None:
    raise AuthenticatedCaseTaxpayerBindingError(code)


__all__ = [
    "AUTHENTICATED_CASE_TAXPAYER_ASSERTION_SCHEMA_VERSION",
    "AUTHENTICATED_CASE_TAXPAYER_BINDING_ARTIFACT_TYPE",
    "AUTHENTICATED_CASE_TAXPAYER_BINDING_SCHEMA_VERSION",
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "AuthenticatedCaseTaxpayerBindingError",
    "AuthenticatedCaseTaxpayerBindingRuntime",
    "AuthenticatedCaseTaxpayerBindingRuntimeFactory",
    "AuthenticatedTaxpayerIdentityProvider",
]
