"""Immutable persistence and current-view access for ordinary-trade projections."""

from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any, Iterable, Mapping

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, ArtifactStoreError
from .artifact_resolver import ArtifactResolver
from .canonical_store import CanonicalReaderFactory
from .ordinary_trade_semantic_compiler import (
    ORDINARY_TRADE_PROJECTION_SCHEMA_VERSION,
    OrdinaryTradeSemanticCompilerFactory,
    validate_ordinary_trade_projection,
)


ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE = (
    ORDINARY_TRADE_PROJECTION_SCHEMA_VERSION
)
FACTORY_REQUIRED = (
    "OrdinaryTradeProjectionFactory.create is the only production-candidate "
    "projection persistence and current-view entrypoint"
)
FORBIDDEN = (
    "projection overwrite, caller-supplied tenant identity, stale Canonical reuse, "
    "latest-wins ambiguity or persistence outside ArtifactStore"
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

    def compile_and_save(
        self,
        *,
        document_id: str,
        mappings: Iterable[Mapping[str, Any]],
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
        projection = self._compiler.compile(
            canonical=envelope.artifact,
            canonical_binding=binding,
            mappings=mappings,
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
        records = [
            item
            for item in self._resolver.catalog_case(context)
            if item.artifact_type == ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE
        ]
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
            if (
                payload["canonical_binding"]["canonical_version_id"]
                != active.canonical_version_id
            ):
                continue
            current.append((record, payload))
            by_document[record.document_id] = by_document.get(record.document_id, 0) + 1
        if any(count > 1 for count in by_document.values()):
            raise OrdinaryTradeProjectionError(
                "ordinary_trade_current_projection_ambiguous"
            )
        return sorted(current, key=lambda item: str(item[0].document_id))


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
    "ORDINARY_TRADE_PROJECTION_ARTIFACT_TYPE",
    "OrdinaryTradeProjectionError",
    "OrdinaryTradeProjectionFactory",
    "OrdinaryTradeProjectionRuntime",
]
