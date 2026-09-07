"""Immutable declaration-package bindings for an ordinary-trade case.

The bundle is deliberately a narrow sidecar.  It owns an explicit user's
``document set is complete`` intent and a receipt binding that intent to the
current Canonical/projection coverage, Gate 4 facts, and already validated
Gate 5 user facts.  It never copies source payloads, computes tax, or changes
Canonical or User Case Facts.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import replace
from typing import Any, Callable

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, ArtifactStorePort
from .artifact_resolver import ArtifactResolver
from .ordinary_trade_declaration_case_inputs import primary_taxpayer_scope_ref


ORDINARY_TRADE_DECLARATION_CASE_BUNDLE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_declaration_case_bundle_v1"
)
ORDINARY_TRADE_DECLARATION_CASE_BUNDLE_ARTIFACT_TYPE = (
    ORDINARY_TRADE_DECLARATION_CASE_BUNDLE_SCHEMA_VERSION
)
FACTORY_REQUIRED = (
    "OrdinaryTradeDeclarationCaseBundleFactory.create is the only declaration "
    "bundle persistence and current-state entrypoint"
)
FORBIDDEN = (
    "Canonical mutation, source payload copying, caller-supplied coverage or "
    "facts, tax calculation, User Case Fact validation, latest-wins selection "
    "or automatic restabilization"
)

_TAX_PERIOD = re.compile(r"^[0-9]{4}$")
_INTENT = "DOCUMENT_SET_STABILIZED"


class OrdinaryTradeDeclarationCaseBundleError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeDeclarationCaseBundleFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        retention_policy: Any,
        coverage_reader: Callable[..., dict[str, Any]],
        fact_set_reader: Callable[..., dict[str, Any]],
        user_facts_reader: Callable[..., list[dict[str, Any]]],
    ) -> None:
        self._store = store
        self._retention_policy = retention_policy
        self._coverage_reader = coverage_reader
        self._fact_set_reader = fact_set_reader
        self._user_facts_reader = user_facts_reader

    def create(self) -> "OrdinaryTradeDeclarationCaseBundleRuntime":
        return OrdinaryTradeDeclarationCaseBundleRuntime(
            store=self._store,
            retention_policy=self._retention_policy,
            coverage_reader=self._coverage_reader,
            fact_set_reader=self._fact_set_reader,
            user_facts_reader=self._user_facts_reader,
        )


class OrdinaryTradeDeclarationCaseBundleRuntime:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        retention_policy: Any,
        coverage_reader: Callable[..., dict[str, Any]],
        fact_set_reader: Callable[..., dict[str, Any]],
        user_facts_reader: Callable[..., list[dict[str, Any]]],
    ) -> None:
        self._store = store
        self._resolver = ArtifactResolver(store)
        self._retention_policy = retention_policy
        self._coverage_reader = coverage_reader
        self._fact_set_reader = fact_set_reader
        self._user_facts_reader = user_facts_reader

    def stabilize_current_scope(
        self, *, context: ArtifactAccessContext, tax_period: str
    ) -> dict[str, Any]:
        """Persist the exact current package only after explicit user intent."""

        _private_case(context)
        current = self._current_material(context=context, tax_period=tax_period)
        if current["coverage"]["status"] != "complete":
            _fail("ordinary_trade_declaration_bundle_coverage_incomplete")
        if current["fact_set"]["status"] != "READY":
            _fail("ordinary_trade_declaration_bundle_facts_incomplete")
        payload = _bundle_payload(current=current, context=context, tax_period=tax_period)
        artifact_id = "art_otbundle_" + payload["bundle_sha256"][:40]
        existing = self._store.get_record_unchecked(artifact_id)
        if existing is not None:
            resolved = self._resolver.resolve(
                artifact_id,
                replace(context, normalization_run_id=existing.normalization_run_id),
            )
            if resolved["record"].artifact_type != ORDINARY_TRADE_DECLARATION_CASE_BUNDLE_ARTIFACT_TYPE:
                _fail("ordinary_trade_declaration_bundle_artifact_conflict")
            _validate_payload(resolved["payload"])
            return {
                "status": "CURRENT",
                "bundle_artifact_ref": artifact_id,
                "bundle": copy.deepcopy(resolved["payload"]),
                "created": False,
            }
        record = ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=ORDINARY_TRADE_DECLARATION_CASE_BUNDLE_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=None,
            source_file_ref=None,
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=self._retention_policy,
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": bool(context.workspace_model_id),
                "ordinary_trade_declaration_case_bundle_sidecar_only": True,
            },
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload_kind="json_file",
            payload=payload,
            safe_metadata={
                "tax_period": tax_period,
                "coverage_sha256": payload["coverage_binding"]["coverage_sha256"],
                "facts_sha256": payload["facts_binding"]["facts_sha256"],
                "user_case_facts_total": len(payload["user_case_fact_refs"]),
                "contains_source_payload": False,
            },
        )
        saved = self._store.put_record(record)
        return {
            "status": "CURRENT",
            "bundle_artifact_ref": saved.artifact_id,
            "bundle": copy.deepcopy(payload),
            "created": True,
        }

    def read_current(
        self, *, context: ArtifactAccessContext, tax_period: str
    ) -> dict[str, Any]:
        """Return a matching bundle or an honest stale/absent terminal."""

        _private_case(context)
        _tax_period(tax_period)
        candidates = []
        for record in self._resolver.catalog_case(context):
            if record.artifact_type != ORDINARY_TRADE_DECLARATION_CASE_BUNDLE_ARTIFACT_TYPE:
                continue
            try:
                payload = self._resolver.resolve(
                    record.artifact_id,
                    replace(context, normalization_run_id=record.normalization_run_id),
                )["payload"]
                _validate_payload(payload)
            except Exception:
                continue
            if payload["tax_period"] == tax_period:
                candidates.append((record, payload))
        if not candidates:
            return {"status": "BUNDLE_STABILIZATION_REQUIRED", "bundle": None}
        candidates.sort(key=lambda item: (item[0].created_at, item[0].artifact_id), reverse=True)
        record, payload = candidates[0]
        current = self._current_material(context=context, tax_period=tax_period)
        expected = _bundle_payload(current=current, context=context, tax_period=tax_period)
        if payload["bundle_sha256"] != expected["bundle_sha256"]:
            return {
                "status": "BUNDLE_STALE",
                "bundle_artifact_ref": record.artifact_id,
                "bundle": copy.deepcopy(payload),
            }
        return {
            "status": "CURRENT",
            "bundle_artifact_ref": record.artifact_id,
            "bundle": copy.deepcopy(payload),
        }

    def _current_material(
        self, *, context: ArtifactAccessContext, tax_period: str
    ) -> dict[str, Any]:
        _tax_period(tax_period)
        taxpayer_scope_ref = primary_taxpayer_scope_ref(context=context)
        coverage = self._coverage_reader(context=context)
        fact_set = self._fact_set_reader(context=context)
        facts = self._user_facts_reader(
            context=context,
            taxpayer_scope_ref=taxpayer_scope_ref,
            tax_period=tax_period,
        )
        _validate_current_material(coverage=coverage, fact_set=fact_set, user_facts=facts)
        return {
            "coverage": coverage,
            "fact_set": fact_set,
            "user_facts": facts,
            "taxpayer_scope_ref": taxpayer_scope_ref,
        }


def _bundle_payload(*, current: dict[str, Any], context: ArtifactAccessContext, tax_period: str) -> dict[str, Any]:
    coverage = current["coverage"]
    facts = current["fact_set"]["facts"]
    user_facts = current["user_facts"]
    base = {
        "schema_version": ORDINARY_TRADE_DECLARATION_CASE_BUNDLE_SCHEMA_VERSION,
        "intent": _INTENT,
        "case_id": context.case_id,
        "authenticated_user_ref": context.user_id,
        "taxpayer_scope_ref": current["taxpayer_scope_ref"],
        "tax_period": tax_period,
        "coverage_binding": {
            "coverage_ref": coverage["coverage_ref"],
            "coverage_sha256": coverage["coverage_sha256"],
            "document_scope": copy.deepcopy(coverage["document_scope"]),
            "projection_refs": [item["projection_artifact_id"] for item in coverage["projections"]],
        },
        "facts_binding": {
            "facts_sha256": _sha256(facts),
            "fact_refs": sorted(item["fact_id"] for item in facts),
        },
        "user_case_fact_refs": sorted(item["user_case_fact_ref"] for item in user_facts),
        "user_case_facts_sha256": _sha256(user_facts),
    }
    return {**base, "bundle_sha256": _sha256(base)}


def _validate_current_material(*, coverage: Any, fact_set: Any, user_facts: Any) -> None:
    if (
        not isinstance(coverage, dict)
        or coverage.get("schema_version")
        != "broker_reports_ordinary_trade_current_case_coverage_v2"
        or not isinstance(coverage.get("coverage_ref"), str)
        or not isinstance(coverage.get("coverage_sha256"), str)
        or not isinstance(coverage.get("document_scope"), list)
        or not isinstance(coverage.get("projections"), list)
    ):
        _fail("ordinary_trade_declaration_bundle_coverage_invalid")
    if (
        not isinstance(fact_set, dict)
        or fact_set.get("schema_version")
        != "broker_reports_gate4_ordinary_trade_current_fact_set_v1"
        or not isinstance(fact_set.get("facts"), list)
        or any(not isinstance(item, dict) or not isinstance(item.get("fact_id"), str) for item in fact_set["facts"])
    ):
        _fail("ordinary_trade_declaration_bundle_fact_set_invalid")
    if (
        not isinstance(user_facts, list)
        or any(not isinstance(item, dict) or not isinstance(item.get("user_case_fact_ref"), str) for item in user_facts)
    ):
        _fail("ordinary_trade_declaration_bundle_user_facts_invalid")


def _validate_payload(payload: Any) -> None:
    required = {
        "schema_version", "intent", "case_id", "authenticated_user_ref",
        "taxpayer_scope_ref", "tax_period", "coverage_binding", "facts_binding",
        "user_case_fact_refs", "user_case_facts_sha256", "bundle_sha256",
    }
    if (
        not isinstance(payload, dict)
        or set(payload) != required
        or payload.get("schema_version") != ORDINARY_TRADE_DECLARATION_CASE_BUNDLE_SCHEMA_VERSION
        or payload.get("intent") != _INTENT
        or not all(isinstance(payload.get(key), str) and payload[key] for key in required - {"coverage_binding", "facts_binding", "user_case_fact_refs"})
        or not isinstance(payload.get("coverage_binding"), dict)
        or not isinstance(payload.get("facts_binding"), dict)
        or not isinstance(payload.get("user_case_fact_refs"), list)
    ):
        _fail("ordinary_trade_declaration_bundle_payload_invalid")
    material = {key: copy.deepcopy(value) for key, value in payload.items() if key != "bundle_sha256"}
    if _sha256(material) != payload["bundle_sha256"]:
        _fail("ordinary_trade_declaration_bundle_receipt_invalid")


def _private_case(context: ArtifactAccessContext) -> None:
    if not isinstance(context, ArtifactAccessContext) or not context.allow_private or not context.user_id or not context.case_id:
        _fail("ordinary_trade_declaration_bundle_private_case_context_required")


def _tax_period(value: str) -> None:
    if not isinstance(value, str) or _TAX_PERIOD.fullmatch(value) is None or value == "0000":
        _fail("ordinary_trade_declaration_bundle_tax_period_invalid")


def _sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _fail(code: str) -> None:
    raise OrdinaryTradeDeclarationCaseBundleError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "ORDINARY_TRADE_DECLARATION_CASE_BUNDLE_ARTIFACT_TYPE",
    "ORDINARY_TRADE_DECLARATION_CASE_BUNDLE_SCHEMA_VERSION",
    "OrdinaryTradeDeclarationCaseBundleError",
    "OrdinaryTradeDeclarationCaseBundleFactory",
    "OrdinaryTradeDeclarationCaseBundleRuntime",
]
