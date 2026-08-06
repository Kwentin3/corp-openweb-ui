"""Gate 2 canonical version, physical-layout and reader facade."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from dataclasses import dataclass
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
    CanonicalActivationReceipt,
    CanonicalVersionRecord,
    RetentionPolicy,
)
from .artifact_resolver import ArtifactResolver
from .canonical_artifact import validate_canonical_artifact


FACTORY_REQUIRED = (
    "CanonicalArtifactStoreFactory.create is the only Gate 2 canonical "
    "persistence facade; it delegates to ArtifactStoreFactory-created storage"
)


@dataclass(frozen=True)
class CanonicalStorageConfig:
    small_payload_max_bytes: int = 256 * 1024
    large_table_cell_threshold: int = 1_000
    candidate_retention_class: str = "SUPERSEDED_CANONICAL"
    capacity_check_enabled: bool = True
    minimum_free_bytes: int = 1 * 1024 * 1024 * 1024
    critical_free_ratio: float = 0.10
    warning_free_ratio: float = 0.20
    maximum_artifact_bytes: int = 128 * 1024 * 1024
    maximum_chunk_count: int = 4_096


@dataclass(frozen=True)
class CanonicalPersistResult:
    artifact_ref: str
    compare_receipt_ref: str | None
    canonical_version_id: str
    canonical_version_number: int
    previous_version_ref: str | None
    version_status: str
    physical_layout: str
    component_count: int


@dataclass(frozen=True)
class CanonicalReadEnvelope:
    artifact: dict[str, Any]
    canonical_version_id: str
    canonical_version_number: int
    version_status: str
    schema_version: str
    canonical_root_sha256: str
    physical_layout: str
    component_count: int
    payload_bytes: int


class CanonicalArtifactStoreFactory:
    """Sole lifecycle facade over the existing ArtifactStore implementation.

    Callers must not create a second canonical storage engine or depend on a
    physical layout. The factory preserves that boundary while reusing the
    repository's authenticated storage authority.
    """

    def __init__(
        self, *, store, config: CanonicalStorageConfig | None = None
    ) -> None:
        self.store = store
        self.config = config or CanonicalStorageConfig()

    def create(self) -> "CanonicalArtifactStore":
        return CanonicalArtifactStore(self.store, config=self.config)


class CanonicalArtifactStore:
    """Publish immutable validated versions without exposing storage layout."""

    def __init__(self, store, *, config: CanonicalStorageConfig) -> None:
        self.store = store
        self.config = config
        self.resolver = ArtifactResolver(store)

    def put_candidate(
        self,
        *,
        artifact: dict[str, Any],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        compare_receipt: dict[str, Any] | None,
    ) -> CanonicalPersistResult:
        """Persist a candidate only after scope, source and content validation.

        Finalization binds immutable component hashes; activation is a separate
        compare-and-set operation so partial publication cannot move a pointer.
        """

        if artifact.get("tenant_id") != context.user_id:
            raise ArtifactStoreError(
                "artifact_access_denied",
                "Canonical tenant must come from authenticated context",
            )
        self._capacity_preflight(artifact)
        validation = validate_canonical_artifact(artifact)
        if not validation["passed"]:
            raise ArtifactStoreError(
                "artifact_blocked", "Canonical artifact failed validation"
            )
        source_ref = str(
            (artifact.get("source") or {}).get("source_artifact_ref") or ""
        )
        source_record = self.resolver.resolve_record(source_ref, context)
        if not source_record.document_id:
            raise ArtifactStoreError(
                "canonical_source_scope_mismatch",
                "Canonical source artifact has no document identity",
            )
        source = artifact.get("source") or {}
        reservation = self.store.reserve_canonical_version(
            context=context,
            document_id=source_record.document_id,
            source_artifact_ref=source_ref,
            schema_version=str(artifact.get("schema_version") or ""),
            normalizer_version=str(artifact.get("normalizer_version") or ""),
            source_sha256=str(source.get("source_sha256") or ""),
            canonical_root_sha256=str(artifact.get("canonical_root_hash") or ""),
            retention_class=self.config.candidate_retention_class,
        )
        versioned = copy.deepcopy(artifact)
        versioned["artifact_id"] = reservation.canonical_version_id
        versioned["artifact_version"] = reservation.canonical_version_number
        versioned["previous_version_ref"] = reservation.previous_version_ref
        versioned["created_at"] = reservation.created_at
        versioned["status"] = "validated"
        validation = validate_canonical_artifact(versioned)
        if not validation["passed"]:
            raise ArtifactStoreError(
                "artifact_blocked", "Versioned canonical artifact failed validation"
            )
        records, components, manifest_ref, physical_layout = self._physical_graph(
            artifact=versioned,
            reservation=reservation,
            context=context,
            retention_policy=retention_policy,
            document_id=source_record.document_id,
            source_file_ref=source_record.source_file_ref,
        )
        self.store.put_records_atomic(records)
        finalized = self.store.finalize_canonical_version(
            context=context,
            canonical_version_id=reservation.canonical_version_id,
            manifest_ref=manifest_ref,
            components=components,
        )
        compare_ref = None
        if compare_receipt is not None:
            compare_payload = copy.deepcopy(compare_receipt)
            compare_payload["canonical_artifact_id"] = finalized.canonical_version_id
            compare_record = self.store.put_record(
                _record(
                    artifact_id=_component_artifact_id(
                        finalized.canonical_version_id, "compare", "legacy"
                    ),
                    artifact_type=(
                        "broker_reports_canonical_legacy_compare_receipt_v1"
                    ),
                    context=context,
                    retention_policy=retention_policy,
                    document_id=source_record.document_id,
                    source_file_ref=source_record.source_file_ref,
                    visibility="safe_internal",
                    storage_backend="project_artifact_store",
                    payload=compare_payload,
                    safe_metadata={
                        "canonical_root_hash": compare_payload.get(
                            "canonical_root_hash"
                        ),
                        "comparison_status": compare_payload.get(
                            "comparison_status"
                        ),
                        "authoritative_representation": compare_payload.get(
                            "authoritative_representation"
                        ),
                        "canonical_version_id": finalized.canonical_version_id,
                        "retention_class": "EVIDENCE",
                        "cutover_authorized": False,
                    },
                )
            )
            compare_ref = compare_record.artifact_id
        return CanonicalPersistResult(
            artifact_ref=manifest_ref,
            compare_receipt_ref=compare_ref,
            canonical_version_id=finalized.canonical_version_id,
            canonical_version_number=finalized.canonical_version_number,
            previous_version_ref=finalized.previous_version_ref,
            version_status=finalized.status,
            physical_layout=physical_layout,
            component_count=len(components),
        )

    def put_xlsx_streaming_candidate(
        self,
        *,
        plan,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> CanonicalPersistResult:
        """Publish a validated XLSX plan one bounded component at a time."""

        from .xlsx_streaming import validate_xlsx_streaming_plan

        if plan.tenant_id != context.user_id:
            raise ArtifactStoreError(
                "artifact_access_denied",
                "Canonical tenant must come from authenticated context",
            )
        validation = validate_xlsx_streaming_plan(plan)
        if not validation["passed"]:
            raise ArtifactStoreError(
                "artifact_blocked", "XLSX streaming plan failed validation"
            )
        source_record = self.resolver.resolve_record(
            plan.source_artifact_ref, context
        )
        if source_record.document_id != plan.document_id:
            raise ArtifactStoreError(
                "canonical_source_scope_mismatch",
                "Canonical document does not match its source artifact",
            )
        component_count = 3 + len(plan.node_entries)
        staged_bytes = sum(
            (plan.stage_root / str(item["relative_path"])).stat().st_size
            for item in plan.node_entries
            if item.get("relative_path")
        )
        self._capacity_preflight_streaming(
            staged_bytes=staged_bytes, component_count=component_count
        )
        reservation = self.store.reserve_canonical_version(
            context=context,
            document_id=plan.document_id,
            source_artifact_ref=plan.source_artifact_ref,
            schema_version="canonical_artifact_v1",
            normalizer_version=plan.normalizer_version,
            source_sha256=plan.source_sha256,
            canonical_root_sha256=plan.canonical_root_hash,
            retention_class=self.config.candidate_retention_class,
        )
        if reservation.status in {"VALIDATED", "ACTIVE", "SUPERSEDED"}:
            components = self.store.list_canonical_components(
                context=context,
                canonical_version_id=reservation.canonical_version_id,
            )
            manifest = next(
                item for item in components if item["component_kind"] == "manifest"
            )
            return CanonicalPersistResult(
                artifact_ref=str(manifest["artifact_ref"]),
                compare_receipt_ref=None,
                canonical_version_id=reservation.canonical_version_id,
                canonical_version_number=reservation.canonical_version_number,
                previous_version_ref=reservation.previous_version_ref,
                version_status=reservation.status,
                physical_layout="xlsx_row_chunked_v1",
                component_count=len(components),
            )

        logical = plan.logical_envelope(created_at=reservation.created_at)
        logical["artifact_id"] = reservation.canonical_version_id
        logical["artifact_version"] = reservation.canonical_version_number
        logical["previous_version_ref"] = reservation.previous_version_ref
        descriptors: list[dict[str, Any]] = []
        chunk_descriptors: list[dict[str, Any]] = []
        written_ids: list[str] = []

        def put_component(
            *,
            kind: str,
            key: str,
            payload: dict[str, Any],
            ordinal: int,
            artifact_type: str = "broker_reports_canonical_component_v1",
        ) -> str:
            artifact_id = _component_artifact_id(
                reservation.canonical_version_id, kind, key
            )
            record = _private_component_record(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                context=context,
                retention_policy=retention_policy,
                document_id=plan.document_id,
                source_file_ref=source_record.source_file_ref,
                payload=payload,
                safe_metadata=_component_safe_metadata(
                    logical,
                    reservation,
                    kind,
                    key,
                    "xlsx_row_chunked_v1",
                ),
            )
            self.store.put_record(record)
            written_ids.append(artifact_id)
            descriptors.append(_component_descriptor(kind, key, record, ordinal))
            return artifact_id

        try:
            ordinal = 0
            container_ref = put_component(
                kind="containers",
                key="all",
                payload={"containers": list(plan.containers)},
                ordinal=ordinal,
            )
            chunk_descriptors.append(
                _stream_chunk_descriptor(
                    ordinal, "CONTAINER", container_ref,
                    _payload_sha256({"containers": list(plan.containers)}),
                    [str(item["container_id"]) for item in plan.containers], []
                )
            )
            ordinal += 1
            for node in plan.iter_nodes():
                node_id = str(node["node_id"])
                payload = {"node": node}
                artifact_ref = put_component(
                    kind="node", key=node_id, payload=payload, ordinal=ordinal
                )
                chunk_descriptors.append(
                    _stream_chunk_descriptor(
                        ordinal,
                        "TABLE" if node.get("node_type") == "TABLE" else "CONTAINER",
                        artifact_ref,
                        _payload_sha256(payload),
                        [str(node["container_ref"])],
                        [node_id],
                    )
                )
                ordinal += 1
            evidence_payload = {
                "provenance": list(plan.provenance),
                "issues": list(plan.issues),
            }
            evidence_ref = put_component(
                kind="evidence",
                key="all",
                payload=evidence_payload,
                ordinal=ordinal,
            )
            chunk_descriptors.append(
                _stream_chunk_descriptor(
                    ordinal, "CONTAINER", evidence_ref,
                    _payload_sha256(evidence_payload), [], []
                )
            )
            ordinal += 1
            logical["chunks"] = chunk_descriptors
            manifest_payload = {
                "schema_version": "canonical_physical_manifest_v1",
                "physical_layout": "xlsx_row_chunked_v1",
                "canonical_version_id": reservation.canonical_version_id,
                "envelope": logical,
                "xlsx_safe_metrics": dict(plan.safe_metrics),
            }
            manifest_ref = put_component(
                kind="manifest",
                key="xlsx-streaming",
                payload=manifest_payload,
                ordinal=ordinal,
                artifact_type="broker_reports_canonical_artifact_v1",
            )
            finalized = self.store.finalize_canonical_version(
                context=context,
                canonical_version_id=reservation.canonical_version_id,
                manifest_ref=manifest_ref,
                components=descriptors,
            )
        except Exception:
            self.store.abort_canonical_candidate(
                context=context,
                canonical_version_id=reservation.canonical_version_id,
                component_artifact_ids=written_ids,
            )
            raise
        return CanonicalPersistResult(
            artifact_ref=manifest_ref,
            compare_receipt_ref=None,
            canonical_version_id=finalized.canonical_version_id,
            canonical_version_number=finalized.canonical_version_number,
            previous_version_ref=finalized.previous_version_ref,
            version_status=finalized.status,
            physical_layout="xlsx_row_chunked_v1",
            component_count=len(descriptors),
        )

    def _capacity_preflight_streaming(
        self, *, staged_bytes: int, component_count: int
    ) -> None:
        if staged_bytes > self.config.maximum_artifact_bytes:
            raise ArtifactStoreError(
                "canonical_artifact_too_large",
                "Canonical artifact exceeds the configured maximum size",
            )
        if component_count > self.config.maximum_chunk_count:
            raise ArtifactStoreError(
                "canonical_chunk_limit_exceeded",
                "Canonical artifact exceeds the configured component limit",
            )
        if not self.config.capacity_check_enabled:
            return
        payload_root = getattr(self.store, "payload_root", None)
        if payload_root is None:
            raise ArtifactStoreError(
                "canonical_capacity_unavailable",
                "Canonical capacity root is unavailable through the store",
            )
        usage = shutil.disk_usage(payload_root)
        free_ratio = usage.free / usage.total if usage.total else 0.0
        if (
            usage.free - staged_bytes < self.config.minimum_free_bytes
            or free_ratio <= self.config.critical_free_ratio
        ):
            raise ArtifactStoreError(
                "canonical_capacity_insufficient",
                "Canonical shadow write rejected by the capacity policy",
            )

    def _capacity_preflight(self, artifact: dict[str, Any]) -> None:
        serialized_bytes = len(_json_bytes(artifact))
        if serialized_bytes > self.config.maximum_artifact_bytes:
            raise ArtifactStoreError(
                "canonical_artifact_too_large",
                "Canonical artifact exceeds the configured maximum size",
            )
        estimated_chunks = self._estimated_component_count(
            artifact, serialized_bytes=serialized_bytes
        )
        if estimated_chunks > self.config.maximum_chunk_count:
            raise ArtifactStoreError(
                "canonical_chunk_limit_exceeded",
                "Canonical artifact exceeds the configured component limit",
            )
        if not self.config.capacity_check_enabled:
            return
        payload_root = getattr(self.store, "payload_root", None)
        if payload_root is None:
            raise ArtifactStoreError(
                "canonical_capacity_unavailable",
                "Canonical capacity root is unavailable through the store",
            )
        usage = shutil.disk_usage(payload_root)
        free_ratio = usage.free / usage.total if usage.total else 0.0
        if (
            usage.free - serialized_bytes < self.config.minimum_free_bytes
            or free_ratio <= self.config.critical_free_ratio
        ):
            raise ArtifactStoreError(
                "canonical_capacity_insufficient",
                "Canonical shadow write rejected by the capacity policy",
            )

    def _estimated_component_count(
        self, artifact: dict[str, Any], *, serialized_bytes: int
    ) -> int:
        nodes = list(artifact.get("nodes") or [])
        large_tables = [
            node
            for node in nodes
            if node.get("node_type") == "TABLE"
            and len((node.get("content") or {}).get("cells") or [])
            >= self.config.large_table_cell_threshold
        ]
        if (
            serialized_bytes <= self.config.small_payload_max_bytes
            and not large_tables
        ):
            return 1
        return 3 + len(artifact.get("containers") or []) + len(large_tables)

    def _physical_graph(
        self,
        *,
        artifact: dict[str, Any],
        reservation: CanonicalVersionRecord,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        document_id: str,
        source_file_ref: dict[str, Any] | None,
    ) -> tuple[list[ArtifactRecord], list[dict[str, Any]], str, str]:
        serialized_size = len(_json_bytes(artifact))
        table_sizes = [
            len((node.get("content") or {}).get("cells") or [])
            for node in artifact.get("nodes") or []
            if node.get("node_type") == "TABLE"
        ]
        chunked = serialized_size > self.config.small_payload_max_bytes or any(
            size >= self.config.large_table_cell_threshold for size in table_sizes
        )
        if not chunked:
            manifest_ref = _component_artifact_id(
                reservation.canonical_version_id, "manifest", "single"
            )
            payload = {
                "schema_version": "canonical_physical_manifest_v1",
                "physical_layout": "single_payload",
                "canonical_version_id": reservation.canonical_version_id,
                "artifact": artifact,
            }
            record = _private_component_record(
                artifact_id=manifest_ref,
                artifact_type="broker_reports_canonical_artifact_v1",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_file_ref,
                payload=payload,
                safe_metadata=_component_safe_metadata(
                    artifact, reservation, "manifest", "single", "single_payload"
                ),
            )
            return (
                [record],
                [_component_descriptor("manifest", "single", record, 0)],
                manifest_ref,
                "single_payload",
            )

        records: list[ArtifactRecord] = []
        components: list[dict[str, Any]] = []
        chunk_descriptors: list[dict[str, Any]] = []

        def add_component(
            kind: str,
            key: str,
            payload: dict[str, Any],
            ordinal: int,
            *,
            chunk_kind: str,
            container_refs: list[str],
            node_refs: list[str],
        ) -> None:
            artifact_ref = _component_artifact_id(
                reservation.canonical_version_id, kind, key
            )
            record = _private_component_record(
                artifact_id=artifact_ref,
                artifact_type="broker_reports_canonical_component_v1",
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_file_ref,
                payload=payload,
                safe_metadata=_component_safe_metadata(
                    artifact, reservation, kind, key, "chunked"
                ),
            )
            records.append(record)
            components.append(_component_descriptor(kind, key, record, ordinal))
            chunk_descriptors.append(
                {
                    "chunk_id": f"chunk_{ordinal:06d}",
                    "chunk_kind": chunk_kind,
                    "content_ref": artifact_ref,
                    "sha256": _payload_sha256(payload),
                    "container_refs": container_refs,
                    "node_refs": node_refs,
                }
            )

        ordinal = 0
        containers = copy.deepcopy(artifact.get("containers") or [])
        add_component(
            "containers",
            "all",
            {"containers": containers},
            ordinal,
            chunk_kind="CONTAINER",
            container_refs=[str(item["container_id"]) for item in containers],
            node_refs=[],
        )
        ordinal += 1
        large_table_ids = {
            str(node["node_id"])
            for node in artifact.get("nodes") or []
            if node.get("node_type") == "TABLE"
            and len((node.get("content") or {}).get("cells") or [])
            >= self.config.large_table_cell_threshold
        }
        for container in containers:
            container_id = str(container["container_id"])
            nodes = [
                copy.deepcopy(node)
                for node in artifact.get("nodes") or []
                if node.get("container_ref") == container_id
                and str(node.get("node_id")) not in large_table_ids
            ]
            add_component(
                "nodes",
                container_id,
                {"nodes": nodes},
                ordinal,
                chunk_kind="CONTAINER",
                container_refs=[container_id],
                node_refs=[str(item["node_id"]) for item in nodes],
            )
            ordinal += 1
        for node in artifact.get("nodes") or []:
            node_id = str(node.get("node_id") or "")
            if node_id not in large_table_ids:
                continue
            add_component(
                "table",
                node_id,
                {"node": copy.deepcopy(node)},
                ordinal,
                chunk_kind="TABLE",
                container_refs=[str(node.get("container_ref") or "")],
                node_refs=[node_id],
            )
            ordinal += 1
        add_component(
            "evidence",
            "all",
            {
                "provenance": copy.deepcopy(artifact.get("provenance") or []),
                "issues": copy.deepcopy(artifact.get("issues") or []),
            },
            ordinal,
            chunk_kind="CONTAINER",
            container_refs=[],
            node_refs=[],
        )
        ordinal += 1
        logical = copy.deepcopy(artifact)
        for field in ("containers", "nodes", "provenance", "issues"):
            logical.pop(field, None)
        logical["chunks"] = chunk_descriptors
        manifest_payload = {
            "schema_version": "canonical_physical_manifest_v1",
            "physical_layout": "chunked",
            "canonical_version_id": reservation.canonical_version_id,
            "envelope": logical,
        }
        manifest_ref = _component_artifact_id(
            reservation.canonical_version_id, "manifest", "chunked"
        )
        manifest_record = _private_component_record(
            artifact_id=manifest_ref,
            artifact_type="broker_reports_canonical_artifact_v1",
            context=context,
            retention_policy=retention_policy,
            document_id=document_id,
            source_file_ref=source_file_ref,
            payload=manifest_payload,
            safe_metadata=_component_safe_metadata(
                artifact, reservation, "manifest", "chunked", "chunked"
            ),
        )
        records.append(manifest_record)
        components.append(
            _component_descriptor(
                "manifest", "chunked", manifest_record, ordinal
            )
        )
        return records, components, manifest_ref, "chunked"


class CanonicalReaderFactory:
    """Sole public reader constructor for every canonical physical layout."""

    def __init__(self, *, store, read_enabled: bool) -> None:
        self.store = store
        self.read_enabled = read_enabled

    def create(self) -> "CanonicalReader":
        return CanonicalReader(self.store, read_enabled=self.read_enabled)


class CanonicalReader:
    """Resolve, reconstruct and revalidate canonical versions fail closed.

    Consumers see the same API for single payload, chunked and XLSX row-chunked
    storage and therefore cannot couple behavior to physical layout.
    """

    def __init__(self, store, *, read_enabled: bool) -> None:
        self.store = store
        self.read_enabled = read_enabled

    def read(
        self, artifact_ref: str, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        self._require_enabled()
        version = self.store.get_canonical_version_by_manifest(
            context=context, manifest_ref=artifact_ref
        )
        return self._read_version(version, context)

    def read_active(
        self, document_id: str, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        self._require_enabled()
        version = self.store.get_active_canonical_version(
            context=context, document_id=document_id
        )
        return self._read_version(version, context)

    def read_active_envelope(
        self, document_id: str, context: ArtifactAccessContext
    ) -> CanonicalReadEnvelope:
        """Return one validated active artifact plus safe read accounting."""

        self._require_enabled()
        version = self.store.get_active_canonical_version(
            context=context, document_id=document_id
        )
        artifact = self._read_version(version, context)
        components = self.store.list_canonical_components(
            context=context, canonical_version_id=version.canonical_version_id
        )
        manifest = self._manifest(version, context)
        return CanonicalReadEnvelope(
            artifact=artifact,
            canonical_version_id=version.canonical_version_id,
            canonical_version_number=version.canonical_version_number,
            version_status=version.status,
            schema_version=version.schema_version,
            canonical_root_sha256=version.canonical_root_sha256,
            physical_layout=str(manifest.get("physical_layout") or ""),
            component_count=len(components),
            payload_bytes=len(_json_bytes(artifact)),
        )

    def history(
        self, document_id: str, context: ArtifactAccessContext
    ) -> list[CanonicalVersionRecord]:
        self._require_enabled()
        return self.store.list_canonical_versions(
            context=context, document_id=document_id
        )

    def read_container(
        self,
        document_id: str,
        container_id: str,
        context: ArtifactAccessContext,
        *,
        canonical_version_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_enabled()
        version = self._selected_version(
            document_id, context, canonical_version_id=canonical_version_id
        )
        manifest = self._manifest(version, context)
        if manifest.get("physical_layout") == "single_payload":
            artifact = self._validated(manifest.get("artifact") or {})
            container = next(
                (
                    item
                    for item in artifact["containers"]
                    if item.get("container_id") == container_id
                ),
                None,
            )
            if container is None:
                raise ArtifactStoreError(
                    "canonical_chunk_missing", "Canonical container was not found"
                )
            return {
                "container": container,
                "nodes": [
                    item
                    for item in artifact["nodes"]
                    if item.get("container_ref") == container_id
                ],
            }
        if manifest.get("physical_layout") == "xlsx_row_chunked_v1":
            containers = self.store.read_canonical_component(
                context=context,
                canonical_version_id=version.canonical_version_id,
                component_kind="containers",
                component_key="all",
            )["containers"]
            container = next(
                (item for item in containers if item.get("container_id") == container_id),
                None,
            )
            if container is None:
                raise ArtifactStoreError(
                    "canonical_chunk_missing", "Canonical container was not found"
                )
            nodes = [
                node
                for node in self._iter_streaming_nodes(version, context)
                if node.get("container_ref") == container_id
            ]
            return {"container": container, "nodes": nodes}
        containers = self.store.read_canonical_component(
            context=context,
            canonical_version_id=version.canonical_version_id,
            component_kind="containers",
            component_key="all",
        )["containers"]
        container = next(
            (item for item in containers if item.get("container_id") == container_id),
            None,
        )
        if container is None:
            raise ArtifactStoreError(
                "canonical_chunk_missing", "Canonical container was not found"
            )
        node_payload = self.store.read_canonical_component(
            context=context,
            canonical_version_id=version.canonical_version_id,
            component_kind="nodes",
            component_key=container_id,
        )
        nodes = list(node_payload.get("nodes") or [])
        for component in self.store.list_canonical_components(
            context=context, canonical_version_id=version.canonical_version_id
        ):
            if component["component_kind"] != "table":
                continue
            table_node = self.store.read_canonical_component(
                context=context,
                canonical_version_id=version.canonical_version_id,
                component_kind="table",
                component_key=str(component["component_key"]),
            )["node"]
            if table_node.get("container_ref") == container_id:
                nodes.append(table_node)
        nodes.sort(key=lambda item: int(item.get("order") or 0))
        return {"container": container, "nodes": nodes}

    def read_table(
        self,
        document_id: str,
        table_node_id: str,
        context: ArtifactAccessContext,
        *,
        canonical_version_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_enabled()
        version = self._selected_version(
            document_id, context, canonical_version_id=canonical_version_id
        )
        manifest = self._manifest(version, context)
        if manifest.get("physical_layout") == "xlsx_row_chunked_v1":
            components = self.store.list_canonical_components(
                context=context, canonical_version_id=version.canonical_version_id
            )
            if any(
                item["component_kind"] == "node"
                and item["component_key"] == table_node_id
                for item in components
            ):
                node = self.store.read_canonical_component(
                    context=context,
                    canonical_version_id=version.canonical_version_id,
                    component_kind="node",
                    component_key=table_node_id,
                )["node"]
                if node.get("node_type") == "TABLE":
                    return node
        if manifest.get("physical_layout") == "chunked":
            components = self.store.list_canonical_components(
                context=context, canonical_version_id=version.canonical_version_id
            )
            if any(
                item["component_kind"] == "table"
                and item["component_key"] == table_node_id
                for item in components
            ):
                return self.store.read_canonical_component(
                    context=context,
                    canonical_version_id=version.canonical_version_id,
                    component_kind="table",
                    component_key=table_node_id,
                )["node"]
        artifact = self._read_version(version, context)
        table = next(
            (
                item
                for item in artifact["nodes"]
                if item.get("node_id") == table_node_id
                and item.get("node_type") == "TABLE"
            ),
            None,
        )
        if table is None:
            raise ArtifactStoreError(
                "canonical_chunk_missing", "Canonical table was not found"
            )
        return table

    def activate(
        self,
        *,
        canonical_version_id: str,
        expected_previous_version_id: str | None,
        context: ArtifactAccessContext,
        actor: str,
        reason: str,
    ) -> CanonicalActivationReceipt:
        self._require_enabled()
        return self.store.activate_canonical_version(
            context=context,
            canonical_version_id=canonical_version_id,
            expected_previous_version_id=expected_previous_version_id,
            actor=actor,
            reason=reason,
        )

    def rollback(
        self,
        *,
        target_version_id: str,
        expected_current_version_id: str,
        context: ArtifactAccessContext,
        actor: str,
        reason: str,
    ) -> CanonicalActivationReceipt:
        self._require_enabled()
        return self.store.rollback_canonical_version(
            context=context,
            target_version_id=target_version_id,
            expected_current_version_id=expected_current_version_id,
            actor=actor,
            reason=reason,
        )

    def _selected_version(
        self,
        document_id: str,
        context: ArtifactAccessContext,
        *,
        canonical_version_id: str | None,
    ) -> CanonicalVersionRecord:
        if canonical_version_id:
            version = self.store.get_canonical_version(
                context=context, canonical_version_id=canonical_version_id
            )
            if version.document_id != document_id:
                raise ArtifactStoreError(
                    "canonical_source_scope_mismatch",
                    "Canonical version does not belong to the requested document",
                )
            return version
        return self.store.get_active_canonical_version(
            context=context, document_id=document_id
        )

    def _manifest(
        self, version: CanonicalVersionRecord, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        components = self.store.list_canonical_components(
            context=context, canonical_version_id=version.canonical_version_id
        )
        manifest = next(
            (item for item in components if item["component_kind"] == "manifest"),
            None,
        )
        if manifest is None:
            raise ArtifactStoreError(
                "canonical_chunk_missing", "Canonical manifest component is missing"
            )
        return self.store.read_canonical_component(
            context=context,
            canonical_version_id=version.canonical_version_id,
            component_kind="manifest",
            component_key=str(manifest["component_key"]),
        )

    def _read_version(
        self, version: CanonicalVersionRecord, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        """Reconstruct a version and recheck hashes plus logical completeness."""

        manifest = self._manifest(version, context)
        if manifest.get("physical_layout") == "single_payload":
            return self._validated(manifest.get("artifact") or {})
        if manifest.get("physical_layout") not in {"chunked", "xlsx_row_chunked_v1"}:
            raise ArtifactStoreError(
                "canonical_chunk_missing", "Canonical physical layout is unsupported"
            )
        artifact = copy.deepcopy(manifest.get("envelope") or {})
        containers = self.store.read_canonical_component(
            context=context,
            canonical_version_id=version.canonical_version_id,
            component_kind="containers",
            component_key="all",
        )
        evidence = self.store.read_canonical_component(
            context=context,
            canonical_version_id=version.canonical_version_id,
            component_kind="evidence",
            component_key="all",
        )
        artifact["containers"] = containers.get("containers") or []
        artifact["provenance"] = evidence.get("provenance") or []
        artifact["issues"] = evidence.get("issues") or []
        nodes: list[dict[str, Any]] = []
        for component in self.store.list_canonical_components(
            context=context, canonical_version_id=version.canonical_version_id
        ):
            if component["component_kind"] == "nodes":
                payload = self.store.read_canonical_component(
                    context=context,
                    canonical_version_id=version.canonical_version_id,
                    component_kind="nodes",
                    component_key=str(component["component_key"]),
                )
                nodes.extend(payload.get("nodes") or [])
            elif component["component_kind"] == "table":
                payload = self.store.read_canonical_component(
                    context=context,
                    canonical_version_id=version.canonical_version_id,
                    component_kind="table",
                    component_key=str(component["component_key"]),
                )
                nodes.append(payload["node"])
            elif component["component_kind"] == "node":
                payload = self.store.read_canonical_component(
                    context=context,
                    canonical_version_id=version.canonical_version_id,
                    component_kind="node",
                    component_key=str(component["component_key"]),
                )
                nodes.append(payload["node"])
        container_order = {
            str(item["container_id"]): index
            for index, item in enumerate(artifact["containers"])
        }
        artifact["nodes"] = sorted(
            nodes,
            key=lambda item: (
                container_order.get(str(item.get("container_ref") or ""), 10**9),
                int(item.get("order") or 0),
            ),
        )
        return self._validated(artifact)

    def validate_streaming_version(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        canonical_version_id: str | None = None,
    ) -> dict[str, Any]:
        """Validate an XLSX root without materializing all row chunks."""

        from .xlsx_streaming import canonical_root_hash_from_streaming_parts

        self._require_enabled()
        version = self._selected_version(
            document_id, context, canonical_version_id=canonical_version_id
        )
        manifest = self._manifest(version, context)
        if manifest.get("physical_layout") != "xlsx_row_chunked_v1":
            raise ArtifactStoreError(
                "canonical_chunk_missing", "Canonical version is not streaming XLSX"
            )
        envelope = manifest.get("envelope") or {}
        containers = self.store.read_canonical_component(
            context=context,
            canonical_version_id=version.canonical_version_id,
            component_kind="containers",
            component_key="all",
        ).get("containers") or []
        evidence = self.store.read_canonical_component(
            context=context,
            canonical_version_id=version.canonical_version_id,
            component_kind="evidence",
            component_key="all",
        )
        calculated = canonical_root_hash_from_streaming_parts(
            normalizer_version=str(envelope.get("normalizer_version") or ""),
            source_sha256=str((envelope.get("source") or {}).get("source_sha256") or ""),
            containers=containers,
            nodes=self._iter_streaming_nodes(version, context),
            provenance=evidence.get("provenance") or [],
            issues=evidence.get("issues") or [],
        )
        passed = calculated == version.canonical_root_sha256
        if not passed:
            raise ArtifactStoreError(
                "canonical_chunk_hash_mismatch",
                "Streaming canonical root hash does not match",
            )
        return {
            "schema_version": "canonical_xlsx_streaming_read_receipt_v1",
            "passed": True,
            "canonical_version_id": version.canonical_version_id,
            "canonical_root_sha256": calculated,
            "component_count": len(
                self.store.list_canonical_components(
                    context=context,
                    canonical_version_id=version.canonical_version_id,
                )
            ),
            "physical_layout": "xlsx_row_chunked_v1",
        }

    def _iter_streaming_nodes(
        self, version: CanonicalVersionRecord, context: ArtifactAccessContext
    ):
        for component in self.store.list_canonical_components(
            context=context, canonical_version_id=version.canonical_version_id
        ):
            if component["component_kind"] != "node":
                continue
            yield self.store.read_canonical_component(
                context=context,
                canonical_version_id=version.canonical_version_id,
                component_kind="node",
                component_key=str(component["component_key"]),
            )["node"]

    @staticmethod
    def _validated(artifact: dict[str, Any]) -> dict[str, Any]:
        validation = validate_canonical_artifact(artifact)
        if not validation["passed"]:
            raise ArtifactStoreError(
                "canonical_chunk_hash_mismatch",
                "Resolved canonical artifact failed logical validation",
            )
        return artifact

    def _require_enabled(self) -> None:
        if not self.read_enabled:
            raise ArtifactStoreError(
                "canonical_read_disabled", "Canonical reader is disabled before cutover"
            )


def _private_component_record(
    *,
    artifact_id: str,
    artifact_type: str,
    context: ArtifactAccessContext,
    retention_policy: RetentionPolicy,
    document_id: str,
    source_file_ref: dict[str, Any] | None,
    payload: dict[str, Any],
    safe_metadata: dict[str, Any],
) -> ArtifactRecord:
    return _record(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        context=context,
        retention_policy=retention_policy,
        document_id=document_id,
        source_file_ref=source_file_ref,
        visibility="private_case",
        storage_backend="project_artifact_payload",
        payload=payload,
        safe_metadata=safe_metadata,
    )


def _record(
    *,
    artifact_id: str,
    artifact_type: str,
    context: ArtifactAccessContext,
    retention_policy: RetentionPolicy,
    document_id: str | None,
    source_file_ref: dict[str, Any] | None,
    visibility: str,
    storage_backend: str,
    payload: dict[str, Any],
    safe_metadata: dict[str, Any],
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        case_id=context.case_id,
        chat_id=context.chat_id,
        user_id=context.user_id,
        workspace_model_id=context.workspace_model_id,
        normalization_run_id=context.normalization_run_id,
        document_id=document_id,
        source_file_ref=source_file_ref,
        visibility=visibility,
        storage_backend=storage_backend,
        retention_policy=retention_policy,
        access_policy={
            "requires_user_id": True,
            "requires_case_or_chat": True,
            "requires_canonical_reader": True,
        },
        validation_status="validated",
        lifecycle_status=lifecycle_for_visibility(
            visibility=visibility, validation_status="validated"
        ),
        payload_kind=(
            "json_file"
            if storage_backend == "project_artifact_payload"
            else "inline_json"
        ),
        payload=payload,
        safe_metadata=safe_metadata,
        warning_codes=[],
    )


def _component_safe_metadata(
    artifact: dict[str, Any],
    reservation: CanonicalVersionRecord,
    component_kind: str,
    component_key: str,
    physical_layout: str,
) -> dict[str, Any]:
    return {
        "schema_version": artifact.get("schema_version"),
        "canonical_version_id": reservation.canonical_version_id,
        "canonical_version_number": reservation.canonical_version_number,
        "canonical_root_hash": artifact.get("canonical_root_hash"),
        "source_format": (artifact.get("source") or {}).get("source_format"),
        "component_kind": component_kind,
        "component_key_hash": hashlib.sha256(
            component_key.encode("utf-8")
        ).hexdigest(),
        "physical_layout": physical_layout,
        "retention_class": reservation.retention_class,
        "cutover_authorized": False,
    }


def _component_descriptor(
    kind: str, key: str, record: ArtifactRecord, ordinal: int
) -> dict[str, Any]:
    return {
        "component_kind": kind,
        "component_key": key,
        "artifact_ref": record.artifact_id,
        "content_sha256": _payload_sha256(record.payload),
        "ordinal": ordinal,
    }


def _stream_chunk_descriptor(
    ordinal: int,
    chunk_kind: str,
    content_ref: str,
    sha256: str,
    container_refs: list[str],
    node_refs: list[str],
) -> dict[str, Any]:
    return {
        "chunk_id": f"chunk_{ordinal:06d}",
        "chunk_kind": chunk_kind,
        "content_ref": content_ref,
        "sha256": sha256,
        "container_refs": container_refs,
        "node_refs": node_refs,
    }


def _component_artifact_id(version_id: str, kind: str, key: str) -> str:
    digest = hashlib.sha256(
        json.dumps(
            [version_id, kind, key],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"art_{digest[:48]}"


def _payload_sha256(payload: Any) -> str:
    return hashlib.sha256(_json_bytes(payload)).hexdigest()


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
