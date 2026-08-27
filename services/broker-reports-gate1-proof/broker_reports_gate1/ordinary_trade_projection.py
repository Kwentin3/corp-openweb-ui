"""Immutable persistence and current-view access for ordinary-trade projections."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, ArtifactStoreError
from .artifact_resolver import ArtifactResolver
from .canonical_store import CanonicalReaderFactory
from .ordinary_trade_semantic_compiler import (
    ORDINARY_TRADE_PROJECTION_SCHEMA_VERSION,
    OrdinaryTradeSemanticCompilerFactory,
    validate_ordinary_trade_projection,
)
from .ordinary_trade_qualified_mappings import (
    OrdinaryTradeQualifiedMappingAuthorityFactory,
)
from .ordinary_trade_mapping_case import (
    MAPPING_CASE_ARTIFACT_TYPE,
    OrdinaryTradeMappingCaseFactory,
)


ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE = (
    ORDINARY_TRADE_PROJECTION_SCHEMA_VERSION
)
ORDINARY_TRADE_CURRENT_CASE_COVERAGE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_current_case_coverage_v2"
)
FACTORY_REQUIRED = (
    "OrdinaryTradeProjectionFactory.create is the only production-candidate "
    "projection persistence and current-view entrypoint"
)
FORBIDDEN = (
    "projection overwrite, caller-supplied tenant identity, stale Canonical reuse, "
    "latest-wins ambiguity, caller-supplied mappings or persistence outside "
    "ArtifactStore"
)


class OrdinaryTradeProjectionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class OrdinaryTradeProjectionFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "OrdinaryTradeProjectionRuntime":
        return OrdinaryTradeProjectionRuntime(
            store=self._store,
            read_enabled=self._read_enabled,
        )


class OrdinaryTradeProjectionRuntime:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._reader = CanonicalReaderFactory(
            store=store, read_enabled=read_enabled
        ).create()
        self._resolver = ArtifactResolver(store)
        self._compiler = OrdinaryTradeSemanticCompilerFactory.create()
        self._mappings = (
            OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()
        )
        self._mapping_cases = OrdinaryTradeMappingCaseFactory(
            store=store, read_enabled=read_enabled
        ).create()

    def compile_and_save(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
    ) -> ArtifactRecord:
        _private_case(context)
        envelope = self._reader.read_active_envelope(document_id, context)
        source = envelope.artifact.get("source") or {}
        binding = {
            "document_id": envelope.document_id,
            "canonical_version_id": envelope.canonical_version_id,
            "canonical_root_sha256": envelope.canonical_root_sha256,
            "source_artifact_ref": str(source.get("source_artifact_ref") or ""),
            "source_sha256": str(source.get("source_sha256") or ""),
        }
        case_material = self._mapping_cases.qualified_material(
            document_id=document_id,
            context=context,
        )
        case_material = case_material or {
            "mapping_case_artifact_id": None,
            "qualified_mappings": [],
            "table_resolutions": [],
        }
        projection = self._compiler.compile(
            canonical=envelope.artifact,
            canonical_binding=binding,
            mappings=[
                *self._mappings,
                *case_material["qualified_mappings"],
            ],
            table_resolutions=case_material["table_resolutions"],
            semantic_mapping_case_ref=case_material[
                "mapping_case_artifact_id"
            ],
        )
        active = self._store.get_active_canonical_version(
            context=context, document_id=document_id
        )
        if not active.manifest_ref:
            raise OrdinaryTradeProjectionError(
                "ordinary_trade_canonical_manifest_missing"
            )
        manifest = self._resolver.resolve_record(active.manifest_ref, context)
        artifact_id = "art_otproj_" + projection["projection_sha256"][:40]
        record = ArtifactRecord(
            artifact_id=artifact_id,
            artifact_type=ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE,
            case_id=context.case_id,
            chat_id=context.chat_id,
            user_id=context.user_id,
            workspace_model_id=context.workspace_model_id,
            normalization_run_id=context.normalization_run_id,
            document_id=document_id,
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
                "ordinary_trade_projection_sidecar_only": True,
            },
            validation_status="validated",
            lifecycle_status=lifecycle_for_visibility(
                visibility="private_case", validation_status="validated"
            ),
            payload_kind="json_file",
            payload=projection,
            safe_metadata={
                "canonical_version_id": envelope.canonical_version_id,
                "canonical_root_sha256": envelope.canonical_root_sha256,
                "source_observations": len(projection["source_observations"]),
                "runtime_records": len(projection["runtime_records"]),
                "runtime_ready_observations": sum(
                    item["disposition"] == "RUNTIME_READY"
                    for item in projection["source_observations"]
                ),
                "relevant_unmapped_observations": sum(
                    item["disposition"] == "RELEVANT_UNMAPPED"
                    for item in projection["source_observations"]
                ),
                "source_retained_no_consumer_observations": sum(
                    item["disposition"] == "SOURCE_RETAINED_NO_CONSUMER"
                    for item in projection["source_observations"]
                ),
                "broker_or_year_profiles": 0,
            },
        )
        return self._store.put_record(record)

    def read(
        self, *, artifact_id: str, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        resolved = self._resolver.resolve(artifact_id, context)
        record = resolved["record"]
        payload = resolved["payload"]
        if (
            record.artifact_type != ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE
            or not isinstance(payload, dict)
            or record.document_id
            != (payload.get("canonical_binding") or {}).get("document_id")
        ):
            raise OrdinaryTradeProjectionError(
                "ordinary_trade_projection_artifact_invalid"
            )
        validate_ordinary_trade_projection(payload)
        return copy.deepcopy(payload)

    def current_case(
        self, *, context: ArtifactAccessContext
    ) -> list[tuple[ArtifactRecord, dict[str, Any]]]:
        _private_case(context)
        catalog = self._resolver.catalog_case(context)
        records = [
            item
            for item in catalog
            if item.artifact_type == ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE
        ]
        mapping_case_documents = {
            item.document_id
            for item in catalog
            if item.artifact_type == MAPPING_CASE_ARTIFACT_TYPE
            and item.document_id
        }
        current: list[tuple[ArtifactRecord, dict[str, Any]]] = []
        by_document: dict[str, int] = {}
        for record in records:
            if not record.document_id:
                continue
            try:
                active = self._store.get_active_canonical_version(
                    context=context, document_id=record.document_id
                )
            except ArtifactStoreError:
                continue
            record_context = replace(
                context, normalization_run_id=record.normalization_run_id
            )
            payload = self.read(
                artifact_id=record.artifact_id,
                context=record_context,
            )
            material = (
                self._mapping_cases.qualified_material(
                    document_id=record.document_id,
                    context=record_context,
                )
                if record.document_id in mapping_case_documents
                else None
            )
            expected_mapping_case_ref = (
                material["mapping_case_artifact_id"]
                if material is not None
                else None
            )
            if (
                payload["canonical_binding"]["canonical_version_id"]
                != active.canonical_version_id
                or payload.get("semantic_mapping_case_ref")
                != expected_mapping_case_ref
            ):
                continue
            current.append((record, payload))
            by_document[record.document_id] = by_document.get(record.document_id, 0) + 1
        if any(count > 1 for count in by_document.values()):
            raise OrdinaryTradeProjectionError(
                "ordinary_trade_current_projection_ambiguous"
            )
        return sorted(current, key=lambda item: str(item[0].document_id))

    def current_case_coverage(
        self, *, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        """Describe complete current Canonical coverage; callers cannot select rows."""

        projections = self.current_case(context=context)
        document_scope = []
        for record in self._resolver.catalog_case(context):
            if (
                record.artifact_type != "broker_reports_canonical_artifact_v1"
                or not record.document_id
            ):
                continue
            try:
                active = self._store.get_active_canonical_version(
                    context=context,
                    document_id=record.document_id,
                )
            except ArtifactStoreError:
                continue
            if active.manifest_ref != record.artifact_id:
                continue
            document_scope.append(
                {
                    "document_id": active.document_id,
                    "canonical_version_id": active.canonical_version_id,
                    "canonical_root_sha256": active.canonical_root_sha256,
                    "manifest_ref": active.manifest_ref,
                }
            )
        document_scope.sort(key=lambda item: item["document_id"])
        rows = [
            {
                "projection_artifact_id": record.artifact_id,
                "document_id": record.document_id,
                "canonical_version_id": payload["canonical_binding"][
                    "canonical_version_id"
                ],
                "canonical_root_sha256": payload["canonical_binding"][
                    "canonical_root_sha256"
                ],
                "projection_sha256": payload["projection_sha256"],
                "runtime_ready_observations": sum(
                    item["disposition"] == "RUNTIME_READY"
                    for item in payload["source_observations"]
                ),
                "relevant_unmapped_observations": sum(
                    item["disposition"] == "RELEVANT_UNMAPPED"
                    for item in payload["source_observations"]
                ),
            }
            for record, payload in projections
        ]
        projected_bindings = {
            (
                row["document_id"],
                row["canonical_version_id"],
                row["canonical_root_sha256"],
            )
            for row in rows
        }
        scoped_bindings = {
            (
                row["document_id"],
                row["canonical_version_id"],
                row["canonical_root_sha256"],
            )
            for row in document_scope
        }
        missing_projection_documents = sorted(
            item[0] for item in scoped_bindings - projected_bindings
        )
        unexpected_projection_documents = sorted(
            item[0] for item in projected_bindings - scoped_bindings
        )
        if missing_projection_documents or unexpected_projection_documents:
            status = "missing_projection"
        elif rows and not any(
            row["relevant_unmapped_observations"] for row in rows
        ):
            status = "complete"
        else:
            status = "relevant_unmapped"
        base = {
            "schema_version": ORDINARY_TRADE_CURRENT_CASE_COVERAGE_SCHEMA_VERSION,
            "case_id": context.case_id,
            "status": status,
            "document_scope": document_scope,
            "projections": rows,
            "missing_projection_documents": missing_projection_documents,
            "unexpected_projection_documents": unexpected_projection_documents,
            "runtime_ready_observations": sum(
                row["runtime_ready_observations"] for row in rows
            ),
            "relevant_unmapped_observations": sum(
                row["relevant_unmapped_observations"] for row in rows
            ),
        }
        coverage_sha256 = hashlib.sha256(
            json.dumps(
                base,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        return {
            **base,
            "coverage_ref": "ordinary_trade_coverage_" + coverage_sha256[:32],
            "coverage_sha256": coverage_sha256,
        }


def _private_case(context: ArtifactAccessContext) -> None:
    if (
        not isinstance(context, ArtifactAccessContext)
        or not context.user_id
        or not context.case_id
        or not context.allow_private
    ):
        raise OrdinaryTradeProjectionError(
            "ordinary_trade_private_case_context_required"
        )


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "ORDINARY_TRADE_CURRENT_CASE_COVERAGE_SCHEMA_VERSION",
    "ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE",
    "OrdinaryTradeProjectionError",
    "OrdinaryTradeProjectionFactory",
    "OrdinaryTradeProjectionRuntime",
]
