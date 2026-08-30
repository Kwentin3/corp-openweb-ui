"""Inactive workflow-owned role receipt for one Canonical document.

This contract does not classify document content.  A future server-owned
acquisition slot may call the fixed registration method; no production caller
is connected in this slice.
"""

from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import json
import re
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
    ArtifactStorePort,
)
from .artifact_resolver import ArtifactResolver
from .canonical_store import CanonicalReaderFactory


WORKFLOW_DOCUMENT_ROLE_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_workflow_document_role_receipt_v1"
)
WORKFLOW_DOCUMENT_ROLE_RECEIPT_ARTIFACT_TYPE = (
    WORKFLOW_DOCUMENT_ROLE_RECEIPT_SCHEMA_VERSION
)
DECLARATION_METADATA_INPUT_ROLE = "DECLARATION_METADATA_INPUT"
ORDINARY_TRADE_DECLARATION_WORKFLOW_ID = "ordinary_trade_declaration_mvp_v1"
WORKFLOW_DOCUMENT_ROLE_SOURCE = "SERVER_OWNED_ACQUISITION_SLOT"

FACTORY_REQUIRED = (
    "OrdinaryTradeDocumentRoleReceiptRuntimeFactory.create is the only owner "
    "of persisted ordinary-trade workflow document-role receipts"
)
FORBIDDEN = (
    "generic role assignment, document text/title/header/format inference, "
    "caller-supplied source or Canonical bindings, provider/network calls, "
    "financial completeness decisions or production activation"
)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECEIPT_KEYS = frozenset(
    {
        "schema_version",
        "receipt_id",
        "workflow_id",
        "role",
        "role_source",
        "canonical_binding",
        "scope_binding",
        "source_file_ref_sha256",
        "receipt_sha256",
    }
)
_CANONICAL_BINDING_KEYS = frozenset(
    {
        "document_id",
        "canonical_version_id",
        "canonical_root_sha256",
        "manifest_ref",
        "source_artifact_ref",
        "source_sha256",
    }
)
_SCOPE_BINDING_KEYS = frozenset(
    {
        "authenticated_user_ref",
        "case_id",
        "workspace_model_id",
        "normalization_run_id",
    }
)


class OrdinaryTradeDocumentRoleReceiptError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeDocumentRoleReceiptRuntimeFactory:
    def __init__(self, *, store: ArtifactStorePort, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "OrdinaryTradeDocumentRoleReceiptRuntime":
        return OrdinaryTradeDocumentRoleReceiptRuntime(
            store=self._store,
            read_enabled=self._read_enabled,
        )


class OrdinaryTradeDocumentRoleReceiptRuntime:
    def __init__(self, *, store: ArtifactStorePort, read_enabled: bool) -> None:
        self._store = store
        self._resolver = ArtifactResolver(store)
        self._reader = CanonicalReaderFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()

    def register_declaration_metadata_input(
        self,
        *,
        canonical_artifact_ref: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        """Persist the single fixed role after owner-validated Canonical lookup."""

        _require_private_case(context)
        owner_context = replace(context, require_source_available=True)
        if not _identifier(canonical_artifact_ref):
            _fail("workflow_document_role_canonical_ref_required")
        try:
            envelope = self._reader.read_envelope(
                canonical_artifact_ref,
                owner_context,
            )
            active = self._store.get_active_canonical_version(
                context=owner_context,
                document_id=envelope.document_id,
            )
            manifest = self._resolver.resolve_record(
                canonical_artifact_ref,
                owner_context,
            )
        except (ArtifactStoreError, KeyError, TypeError) as exc:
            raise OrdinaryTradeDocumentRoleReceiptError(
                "workflow_document_role_canonical_invalid"
            ) from exc
        if (
            envelope.version_status != "ACTIVE"
            or active.canonical_version_id != envelope.canonical_version_id
            or active.manifest_ref != canonical_artifact_ref
            or manifest.artifact_type != "broker_reports_canonical_artifact_v1"
            or manifest.document_id != envelope.document_id
        ):
            _fail("workflow_document_role_canonical_not_current")
        source = envelope.artifact.get("source")
        if not isinstance(source, dict):
            _fail("workflow_document_role_canonical_invalid")
        source_artifact_ref = str(source.get("source_artifact_ref") or "")
        try:
            source_resolved = self._resolver.resolve_case(
                source_artifact_ref,
                owner_context,
            )
        except ArtifactStoreError as exc:
            raise OrdinaryTradeDocumentRoleReceiptError(
                "workflow_document_role_source_invalid"
            ) from exc
        source_record = source_resolved["record"]
        source_file_ref = source_record.source_file_ref
        source_sha256 = str(source.get("source_sha256") or "")
        if (
            source_record.artifact_type != "source_file_ref_v0"
            or source_record.document_id != envelope.document_id
            or source_record.normalization_run_id != manifest.normalization_run_id
            or not isinstance(source_file_ref, dict)
            or not source_file_ref
            or source_resolved["payload"] != source_file_ref
            or manifest.source_file_ref != source_file_ref
            or _SHA256.fullmatch(
                str(source_file_ref.get("file_hash_sha256") or "")
            )
            is None
            or source_file_ref["file_hash_sha256"] != source_sha256
        ):
            _fail("workflow_document_role_source_invalid")

        base = {
            "schema_version": WORKFLOW_DOCUMENT_ROLE_RECEIPT_SCHEMA_VERSION,
            "workflow_id": ORDINARY_TRADE_DECLARATION_WORKFLOW_ID,
            "role": DECLARATION_METADATA_INPUT_ROLE,
            "role_source": WORKFLOW_DOCUMENT_ROLE_SOURCE,
            "canonical_binding": {
                "document_id": envelope.document_id,
                "canonical_version_id": envelope.canonical_version_id,
                "canonical_root_sha256": envelope.canonical_root_sha256,
                "manifest_ref": canonical_artifact_ref,
                "source_artifact_ref": source_artifact_ref,
                "source_sha256": source_sha256,
            },
            "scope_binding": {
                "authenticated_user_ref": context.user_id,
                "case_id": context.case_id,
                "workspace_model_id": context.workspace_model_id,
                "normalization_run_id": manifest.normalization_run_id,
            },
            "source_file_ref_sha256": _sha(source_record.source_file_ref),
        }
        receipt_sha256 = _sha(base)
        receipt = {
            **base,
            "receipt_id": "workflow_doc_role_" + receipt_sha256[:32],
            "receipt_sha256": receipt_sha256,
        }
        _validated_receipt(receipt)
        self._put_or_reuse(
            receipt=receipt,
            manifest=manifest,
            context=context,
        )
        return self.validate_current(receipt=receipt, context=context)

    def validate_current(
        self,
        *,
        receipt: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        """Revalidate the persisted receipt against current owner artifacts."""

        _require_private_case(context)
        owner_context = replace(context, require_source_available=True)
        validated = _validated_receipt(receipt)
        scope = validated["scope_binding"]
        binding = validated["canonical_binding"]
        if (
            scope["authenticated_user_ref"] != context.user_id
            or scope["case_id"] != context.case_id
            or scope["workspace_model_id"] != context.workspace_model_id
        ):
            _fail("workflow_document_role_scope_mismatch")
        try:
            resolved = self._resolver.resolve_case(
                validated["receipt_id"],
                owner_context,
            )
        except ArtifactStoreError as exc:
            raise OrdinaryTradeDocumentRoleReceiptError(
                "workflow_document_role_owner_artifact_invalid"
            ) from exc
        record = resolved["record"]
        if (
            record.artifact_type
            != WORKFLOW_DOCUMENT_ROLE_RECEIPT_ARTIFACT_TYPE
            or resolved["payload"] != validated
            or record.document_id != binding["document_id"]
            or record.user_id != scope["authenticated_user_ref"]
            or record.case_id != scope["case_id"]
            or record.workspace_model_id != scope["workspace_model_id"]
            or record.normalization_run_id != scope["normalization_run_id"]
            or _sha(record.source_file_ref) != validated["source_file_ref_sha256"]
        ):
            _fail("workflow_document_role_owner_artifact_invalid")

        try:
            active = self._store.get_active_canonical_version(
                context=owner_context,
                document_id=binding["document_id"],
            )
        except ArtifactStoreError as exc:
            raise OrdinaryTradeDocumentRoleReceiptError(
                "workflow_document_role_canonical_unavailable"
            ) from exc
        if (
            active.canonical_version_id != binding["canonical_version_id"]
            or active.canonical_root_sha256 != binding["canonical_root_sha256"]
            or active.manifest_ref != binding["manifest_ref"]
        ):
            _fail("workflow_document_role_stale")
        if active.normalization_run_id != scope["normalization_run_id"]:
            _fail("workflow_document_role_binding_mismatch")

        try:
            manifest_resolved = self._resolver.resolve_case(
                binding["manifest_ref"],
                owner_context,
            )
            manifest_record = manifest_resolved["record"]
            document_context = replace(
                context,
                normalization_run_id=manifest_record.normalization_run_id,
            )
            canonical = self._reader.read(
                binding["manifest_ref"],
                document_context,
            )
            source_resolved = self._resolver.resolve_case(
                binding["source_artifact_ref"],
                owner_context,
            )
        except (ArtifactStoreError, KeyError, TypeError) as exc:
            raise OrdinaryTradeDocumentRoleReceiptError(
                "workflow_document_role_binding_unavailable"
            ) from exc
        source_record = source_resolved["record"]
        source_file_ref = source_record.source_file_ref
        canonical_source = canonical.get("source")
        if (
            manifest_record.artifact_type != "broker_reports_canonical_artifact_v1"
            or manifest_record.document_id != binding["document_id"]
            or manifest_record.normalization_run_id
            != scope["normalization_run_id"]
            or canonical.get("artifact_id") != binding["canonical_version_id"]
            or canonical.get("canonical_root_hash")
            != binding["canonical_root_sha256"]
            or not isinstance(canonical_source, dict)
            or canonical_source.get("source_artifact_ref")
            != binding["source_artifact_ref"]
            or canonical_source.get("source_sha256") != binding["source_sha256"]
            or source_record.artifact_type != "source_file_ref_v0"
            or source_record.document_id != binding["document_id"]
            or source_record.normalization_run_id
            != scope["normalization_run_id"]
            or not isinstance(source_file_ref, dict)
            or source_resolved["payload"] != source_file_ref
            or source_file_ref != manifest_record.source_file_ref
            or source_file_ref != record.source_file_ref
            or _SHA256.fullmatch(
                str(source_file_ref.get("file_hash_sha256") or "")
            )
            is None
            or source_file_ref["file_hash_sha256"] != binding["source_sha256"]
            or _sha(source_file_ref)
            != validated["source_file_ref_sha256"]
        ):
            _fail("workflow_document_role_binding_mismatch")
        self._reject_conflicts(receipt=validated, context=context)
        return copy.deepcopy(validated)

    def _put_or_reuse(
        self,
        *,
        receipt: dict[str, Any],
        manifest: ArtifactRecord,
        context: ArtifactAccessContext,
    ) -> None:
        artifact_id = receipt["receipt_id"]
        existing = self._store.get_record_unchecked(artifact_id)
        if existing is not None:
            self._require_same_owner_artifact(
                artifact_id=artifact_id,
                receipt=receipt,
                context=context,
            )
            return
        record = ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=WORKFLOW_DOCUMENT_ROLE_RECEIPT_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=manifest.normalization_run_id,
            document_id=receipt["canonical_binding"]["document_id"],
            source_file_ref=copy.deepcopy(manifest.source_file_ref),
            visibility="private_case",
            storage_backend="project_artifact_payload",
            retention_policy=manifest.retention_policy,
            access_policy={
                "requires_user_id": True,
                "requires_case_or_chat": True,
                "requires_workspace_model_id_when_present": bool(
                    context.workspace_model_id
                ),
                "workflow_document_role_receipt_only": True,
                "production_consumer_enabled": False,
            },
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case",
                validation_status="validated",
            ),
            payload_kind="json_file",
            payload=copy.deepcopy(receipt),
            safe_metadata={
                "schema_version": receipt["schema_version"],
                "workflow_id": receipt["workflow_id"],
                "role": receipt["role"],
                "canonical_root_sha256": receipt["canonical_binding"][
                    "canonical_root_sha256"
                ],
                "receipt_sha256": receipt["receipt_sha256"],
                "production_consumer_enabled": False,
            },
        )
        try:
            self._store.put_record(record)
        except Exception as exc:
            if self._store.get_record_unchecked(artifact_id) is not None:
                try:
                    self._require_same_owner_artifact(
                        artifact_id=artifact_id,
                        receipt=receipt,
                        context=context,
                    )
                except OrdinaryTradeDocumentRoleReceiptError as conflict:
                    raise conflict from exc
                return
            raise

    def _require_same_owner_artifact(
        self,
        *,
        artifact_id: str,
        receipt: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> None:
        try:
            resolved = self._resolver.resolve_case(artifact_id, context)
        except ArtifactStoreError as exc:
            raise OrdinaryTradeDocumentRoleReceiptError(
                "workflow_document_role_artifact_conflict"
            ) from exc
        if (
            resolved["record"].artifact_type
            != WORKFLOW_DOCUMENT_ROLE_RECEIPT_ARTIFACT_TYPE
            or resolved["payload"] != receipt
        ):
            _fail("workflow_document_role_artifact_conflict")

    def _reject_conflicts(
        self,
        *,
        receipt: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> None:
        binding = receipt["canonical_binding"]
        for record in self._resolver.catalog_case(context):
            if (
                record.artifact_type
                != WORKFLOW_DOCUMENT_ROLE_RECEIPT_ARTIFACT_TYPE
                or record.document_id != binding["document_id"]
                or record.artifact_id == receipt["receipt_id"]
            ):
                continue
            try:
                other = self._resolver.resolve_case(record.artifact_id, context)[
                    "payload"
                ]
                other = _validated_receipt(other)
            except (ArtifactStoreError, OrdinaryTradeDocumentRoleReceiptError) as exc:
                raise OrdinaryTradeDocumentRoleReceiptError(
                    "workflow_document_role_conflict"
                ) from exc
            if (
                other["canonical_binding"]["canonical_version_id"]
                == binding["canonical_version_id"]
            ):
                _fail("workflow_document_role_conflict")


def _validated_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != _RECEIPT_KEYS:
        _fail("workflow_document_role_receipt_invalid")
    canonical = value.get("canonical_binding")
    scope = value.get("scope_binding")
    if (
        value.get("schema_version")
        != WORKFLOW_DOCUMENT_ROLE_RECEIPT_SCHEMA_VERSION
        or value.get("workflow_id") != ORDINARY_TRADE_DECLARATION_WORKFLOW_ID
        or value.get("role") != DECLARATION_METADATA_INPUT_ROLE
        or value.get("role_source") != WORKFLOW_DOCUMENT_ROLE_SOURCE
        or not isinstance(canonical, dict)
        or set(canonical) != _CANONICAL_BINDING_KEYS
        or not isinstance(scope, dict)
        or set(scope) != _SCOPE_BINDING_KEYS
        or any(
            not _identifier(canonical.get(key))
            for key in (
                "document_id",
                "canonical_version_id",
                "manifest_ref",
                "source_artifact_ref",
            )
        )
        or any(
            _SHA256.fullmatch(str(canonical.get(key) or "")) is None
            for key in (
                "canonical_root_sha256",
                "source_sha256",
            )
        )
        or any(
            not _identifier(scope.get(key))
            for key in (
                "authenticated_user_ref",
                "case_id",
                "normalization_run_id",
            )
        )
        or (
            scope.get("workspace_model_id") is not None
            and not _identifier(scope.get("workspace_model_id"))
        )
        or _SHA256.fullmatch(str(value.get("source_file_ref_sha256") or ""))
        is None
        or _SHA256.fullmatch(str(value.get("receipt_sha256") or "")) is None
    ):
        _fail("workflow_document_role_receipt_invalid")
    material = copy.deepcopy(value)
    receipt_id = material.pop("receipt_id", None)
    receipt_sha256 = material.pop("receipt_sha256", None)
    expected_sha256 = _sha(material)
    if (
        receipt_sha256 != expected_sha256
        or receipt_id != "workflow_doc_role_" + expected_sha256[:32]
    ):
        _fail("workflow_document_role_receipt_integrity_invalid")
    return copy.deepcopy(value)


def _require_private_case(context: ArtifactAccessContext) -> None:
    if (
        not isinstance(context, ArtifactAccessContext)
        or not context.allow_private
        or not context.user_id
        or not context.case_id
    ):
        _fail("workflow_document_role_private_case_required")


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _sha(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str) -> None:
    raise OrdinaryTradeDocumentRoleReceiptError(code)
