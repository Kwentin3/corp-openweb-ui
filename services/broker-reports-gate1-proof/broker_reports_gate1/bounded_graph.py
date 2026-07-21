from __future__ import annotations

import copy
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    RetentionPolicy,
    utc_now_iso,
)
from .artifact_store import SqliteArtifactStoreAdapter, new_artifact_id
from .full_source import (
    SOURCE_PAYLOAD_SCHEMA_VERSION,
    validate_full_source_unit,
)
from .pdf_text_layer import validate_pdf_text_layer_payload
from .source_provenance import validate_normalized_slice_provenance
from .table_projection import TableProjectionValidator


BOUNDED_GRAPH_CONTRACT_VERSION = "broker_reports_gate1_bounded_graph_v1"
FACTORY_REQUIRED = (
    "Gate1BoundedGraphFactory.create is the only production bounded-graph entrypoint"
)
FORBIDDEN = (
    "Callers must not construct store-backed collections directly, retain "
    "decoded run-wide representations, or publish a partial run as complete"
)

_COLLECTION_NAMES = (
    "private_normalized_slices",
    "private_normalized_source_payloads",
    "private_normalized_source_units",
    "private_normalized_table_projections",
)


class Gate1BoundedGraphError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate1BoundedGraphConfig:
    store: SqliteArtifactStoreAdapter
    context: ArtifactAccessContext
    retention_policy: RetentionPolicy
    source_file_refs: tuple[dict[str, Any], ...]


class Gate1BoundedGraphFactory:
    def __init__(self, config: Gate1BoundedGraphConfig) -> None:
        self.config = config

    def create(self, *, normalization_run_id: str) -> "Gate1BoundedGraph":
        if not normalization_run_id:
            raise Gate1BoundedGraphError("bounded_graph_run_id_required")
        if self.config.context.normalization_run_id != normalization_run_id:
            raise Gate1BoundedGraphError("bounded_graph_context_run_mismatch")
        return Gate1BoundedGraph(
            store=self.config.store,
            context=self.config.context,
            retention_policy=self.config.retention_policy,
            source_file_refs=self.config.source_file_refs,
            normalization_run_id=normalization_run_id,
            _factory_token=_FACTORY_TOKEN,
        )


class _FactoryToken:
    pass


_FACTORY_TOKEN = _FactoryToken()


class ArtifactStoreBackedList(list[dict[str, Any]]):
    """A sealed list-compatible view whose values live in ArtifactStore.

    The inherited list storage intentionally remains empty.  Compatibility
    operations load one immutable payload at a time; the collection itself
    retains only artifact ids and document indexes.
    """

    def __init__(
        self,
        owner: "Gate1BoundedGraph",
        collection_name: str,
        *,
        _factory_token: _FactoryToken,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise Gate1BoundedGraphError("bounded_collection_factory_required")
        super().__init__()
        self._owner = owner
        self.collection_name = collection_name
        self._artifact_ids: list[str] = []
        self._artifact_ids_by_document: dict[str, list[str]] = {}
        self._compact_values: list[dict[str, Any]] = []
        self._compact_values_by_document: dict[str, list[dict[str, Any]]] = {}
        self._sealed = False

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def artifact_ids(self) -> tuple[str, ...]:
        return tuple(self._artifact_ids)

    def append(self, value: dict[str, Any]) -> None:
        if self._sealed:
            raise Gate1BoundedGraphError("bounded_collection_already_sealed")
        artifact_id, document_id = self._owner._persist_value(
            self.collection_name,
            value,
        )
        self._artifact_ids.append(artifact_id)
        self._artifact_ids_by_document.setdefault(document_id, []).append(artifact_id)
        compact_value = self._owner._compact_value(self.collection_name, value)
        self._compact_values.append(compact_value)
        self._compact_values_by_document.setdefault(document_id, []).append(
            compact_value
        )

    def extend(self, values) -> None:
        for value in values:
            self.append(value)

    def seal(self) -> None:
        self._sealed = True

    def iter_document(self, document_id: str) -> Iterator[dict[str, Any]]:
        for artifact_id in self._artifact_ids_by_document.get(str(document_id), []):
            yield self._read(artifact_id)

    def iter_document_compact(self, document_id: str) -> Iterator[dict[str, Any]]:
        yield from self._compact_values_by_document.get(str(document_id), [])

    def iter_compact(self) -> Iterator[dict[str, Any]]:
        yield from self._compact_values

    def bounded_validation_receipt(self) -> dict[str, Any]:
        return {
            "sealed": self._sealed,
            "artifact_records_total": len(self._artifact_ids),
            "prevalidated_compact_entries_total": len(self._compact_values),
            "document_buckets_total": len(self._artifact_ids_by_document),
            "validation_authority": "validated_before_final_artifactstore_persistence",
        }

    def __iter__(self) -> Iterator[dict[str, Any]]:
        for artifact_id in self._artifact_ids:
            yield self._read(artifact_id)

    def __len__(self) -> int:
        return len(self._artifact_ids)

    def __bool__(self) -> bool:
        return bool(self._artifact_ids)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self._read(value) for value in self._artifact_ids[index]]
        return self._read(self._artifact_ids[index])

    def __deepcopy__(self, memo):
        if not self._sealed:
            raise Gate1BoundedGraphError("bounded_collection_copy_before_seal")
        memo[id(self)] = self
        return self

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ArtifactStoreBackedList):
            return list(self) == list(other)
        if isinstance(other, list):
            return list(self) == other
        return False

    def _read(self, artifact_id: str) -> dict[str, Any]:
        record = self._owner.store.get_record_unchecked(artifact_id)
        if record is None:
            raise Gate1BoundedGraphError("bounded_artifact_record_missing")
        payload = self._owner.store.read_payload(record)
        if not isinstance(payload, dict):
            raise Gate1BoundedGraphError("bounded_artifact_payload_not_object")
        return payload


class Gate1BoundedGraph:
    def __init__(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
        source_file_refs: tuple[dict[str, Any], ...],
        normalization_run_id: str,
        _factory_token: _FactoryToken,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise Gate1BoundedGraphError("bounded_graph_factory_required")
        self.store = store
        self.context = context
        self.retention_policy = retention_policy
        self.source_file_refs = source_file_refs
        self.normalization_run_id = normalization_run_id
        self.refs_by_type: dict[str, list[str]] = {}
        self.source_records_by_doc: dict[str, dict[str, Any]] = {}
        self.source_artifact_ids_by_doc: dict[str, str] = {}
        self.private_refs_by_doc: dict[str, list[str]] = {}
        self.private_source_payload_refs_by_doc: dict[str, list[str]] = {}
        self.private_source_unit_refs_by_doc: dict[str, list[str]] = {}
        self.table_projection_refs_by_doc: dict[str, list[str]] = {}
        self._payload_logical_refs: set[str] = set()
        self._unit_logical_refs: set[str] = set()
        self._documents_registered: set[str] = set()
        self._sealed = False
        self.collections = {
            name: ArtifactStoreBackedList(
                self,
                name,
                _factory_token=_FACTORY_TOKEN,
            )
            for name in _COLLECTION_NAMES
        }

    @property
    def sealed(self) -> bool:
        return self._sealed

    def collection(self, name: str) -> ArtifactStoreBackedList:
        try:
            return self.collections[name]
        except KeyError as exc:
            raise Gate1BoundedGraphError("bounded_collection_name_unsupported") from exc

    def register_document(self, document: dict[str, Any]) -> None:
        if self._sealed:
            raise Gate1BoundedGraphError("bounded_graph_already_sealed")
        document_id = str(document.get("document_id") or "")
        if not document_id:
            raise Gate1BoundedGraphError("bounded_document_id_required")
        if document_id in self._documents_registered:
            raise Gate1BoundedGraphError("bounded_document_registered_twice")
        source_ref = self._source_ref_for_document(document)
        record = self._put(
            artifact_type="source_file_ref_v0",
            document_id=document_id,
            source_file_ref=source_ref,
            visibility="safe_internal",
            storage_backend="openwebui_file",
            validation_status="validated",
            payload=source_ref,
            safe_metadata={
                "source_kind": document.get("source_kind"),
                "container_format": document.get("container_format"),
            },
            access_policy=self._access_policy(),
        )
        self.source_records_by_doc[document_id] = source_ref
        self.source_artifact_ids_by_doc[document_id] = record.artifact_id
        self._documents_registered.add(document_id)

    def seal(self) -> None:
        if self._sealed:
            return
        for collection in self.collections.values():
            collection.seal()
        self._sealed = True

    def assert_compatible(
        self,
        *,
        store: SqliteArtifactStoreAdapter,
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> None:
        if not self._sealed:
            raise Gate1BoundedGraphError("bounded_graph_not_sealed")
        if store is not self.store:
            raise Gate1BoundedGraphError("bounded_graph_store_mismatch")
        if context != self.context:
            raise Gate1BoundedGraphError("bounded_graph_context_mismatch")
        if retention_policy != self.retention_policy:
            raise Gate1BoundedGraphError("bounded_graph_retention_mismatch")

    def compact_receipt(self) -> dict[str, Any]:
        return {
            "schema_version": BOUNDED_GRAPH_CONTRACT_VERSION,
            "normalization_run_id": self.normalization_run_id,
            "sealed": self._sealed,
            "source_records_total": len(self.source_artifact_ids_by_doc),
            "representation_counts": {
                name: len(collection)
                for name, collection in sorted(self.collections.items())
            },
            "artifact_type_counts": {
                key: len(value) for key, value in sorted(self.refs_by_type.items())
            },
            "retained_payload_objects": 0,
            "retained_compact_refs_only": True,
            "store_factory_required": True,
        }

    def _persist_value(
        self,
        collection_name: str,
        value: dict[str, Any],
    ) -> tuple[str, str]:
        if not isinstance(value, dict):
            raise Gate1BoundedGraphError("bounded_value_not_object")
        artifact_type, document_id, safe_metadata = self._value_contract(
            collection_name,
            value,
        )
        if document_id not in self._documents_registered:
            raise Gate1BoundedGraphError("bounded_value_source_not_registered")
        self._validate_value(collection_name, value, document_id)
        record = self._put(
            artifact_type=artifact_type,
            document_id=document_id,
            source_file_ref=self.source_records_by_doc[document_id],
            visibility="private_case",
            storage_backend="project_artifact_payload",
            validation_status=(
                "validated"
                if collection_name != "private_normalized_table_projections"
                or (
                    value.get("validator_status") == "passed"
                    and value.get("projection_status") == "ready"
                )
                else "blocked"
            ),
            payload=value,
            safe_metadata=safe_metadata,
            access_policy={
                **self._access_policy(),
                "requires_gate2_resolver": True,
            },
        )
        if collection_name == "private_normalized_slices":
            self.private_refs_by_doc.setdefault(document_id, []).append(
                record.artifact_id
            )
        elif collection_name == "private_normalized_source_payloads":
            self.private_source_payload_refs_by_doc.setdefault(document_id, []).append(
                record.artifact_id
            )
            self._payload_logical_refs.add(str(value.get("source_payload_ref") or ""))
        elif collection_name == "private_normalized_source_units":
            self.private_source_unit_refs_by_doc.setdefault(document_id, []).append(
                record.artifact_id
            )
            self._unit_logical_refs.add(str(value.get("unit_ref") or ""))
        elif collection_name == "private_normalized_table_projections":
            self.table_projection_refs_by_doc.setdefault(document_id, []).append(
                record.artifact_id
            )
        return record.artifact_id, document_id

    def _validate_value(
        self,
        collection_name: str,
        value: dict[str, Any],
        document_id: str,
    ) -> None:
        errors: list[Any] = []
        source_ref = self.source_records_by_doc[document_id]
        source_checksum = str(source_ref.get("file_hash_sha256") or "")
        if collection_name == "private_normalized_slices":
            validation = validate_normalized_slice_provenance(
                private_slice=value,
                normalization_run_id=self.normalization_run_id,
                document_id=document_id,
                source_checksum_sha256=source_checksum,
            )
            errors.extend(validation.get("errors") or [])
        elif collection_name == "private_normalized_source_payloads":
            if value.get("schema_version") != SOURCE_PAYLOAD_SCHEMA_VERSION:
                errors.append("full_source_payload_schema_mismatch")
            if value.get("document_ref") != document_id:
                errors.append("full_source_payload_document_mismatch")
            if value.get("container_format") == "pdf":
                errors.extend(
                    validate_pdf_text_layer_payload(value).get("errors") or []
                )
        elif collection_name == "private_normalized_source_units":
            if (
                str(value.get("parent_payload_ref") or "")
                not in self._payload_logical_refs
            ):
                errors.append("full_source_unit_parent_payload_missing")
            validation = validate_full_source_unit(
                unit=value,
                normalization_run_id=self.normalization_run_id,
                document_id=document_id,
                source_checksum_sha256=source_checksum,
            )
            errors.extend(validation.get("errors") or [])
        elif collection_name == "private_normalized_table_projections":
            if str(value.get("source_unit_ref") or "") not in self._unit_logical_refs:
                errors.append("table_projection_unknown_source_unit_ref")
            errors.extend(
                TableProjectionValidator().validate(value).get("errors") or []
            )
        if errors:
            raise Gate1BoundedGraphError("bounded_value_validation_failed")

    def _value_contract(
        self,
        collection_name: str,
        value: dict[str, Any],
    ) -> tuple[str, str, dict[str, Any]]:
        if collection_name == "private_normalized_slices":
            artifact_type = (
                "private_normalized_table_slice_v0"
                if value.get("slice_type") == "table_rows"
                else "private_normalized_text_slice_v0"
            )
            document_id = str(value.get("document_id") or "")
            metadata = {
                "slice_type": value.get("slice_type"),
                "schema_version": value.get("schema_version"),
                "source_unit_schema_version": value.get("source_unit_schema_version"),
                "document_id": document_id,
                "profile_id": value.get("profile_id"),
                "table_ref": value.get("table_ref"),
                "row_range_ref": value.get("row_range_ref"),
                "row_refs_count": len(value.get("row_refs") or []),
                "cell_refs_count": len(value.get("cell_refs") or []),
                "source_value_refs_count": len(value.get("source_value_refs") or []),
                "text_segment_refs_count": len(value.get("text_segment_refs") or []),
                "source_checksum_ref": value.get("source_checksum_ref"),
                "parser_ref": value.get("parser_ref"),
                "coverage_ref": (value.get("coverage") or {}).get("coverage_ref"),
                "coverage_complete": (value.get("coverage") or {}).get(
                    "all_selected_refs_accounted"
                ),
            }
            return artifact_type, document_id, metadata
        if collection_name == "private_normalized_source_payloads":
            document_id = str(value.get("document_ref") or "")
            return (
                "private_normalized_source_payload_v0",
                document_id,
                {
                    "schema_version": value.get("schema_version"),
                    "document_ref": document_id,
                    "container_format": value.get("container_format"),
                    "logical_identity": value.get("logical_identity"),
                    "parser_ref": value.get("parser_ref"),
                    "source_checksum_ref": value.get("source_checksum_ref"),
                    "payload_checksum_ref": value.get("payload_checksum_ref"),
                    "parser_completeness_status": value.get(
                        "parser_completeness_status"
                    ),
                    "parser_completeness_reason_codes": list(
                        value.get("parser_completeness_reason_codes") or []
                    ),
                    "rows_total": int(value.get("rows_total") or 0),
                    "cells_total": int(value.get("cells_total") or 0),
                    "text_characters_total": int(
                        value.get("text_characters_total") or 0
                    ),
                    "extraction_units_total": len(
                        value.get("extraction_unit_refs") or []
                    ),
                    "full_source_coverage_available": (
                        value.get("coverage_index") or {}
                    ).get("full_source_coverage_available")
                    is True,
                    "pdf_text_layer_projection_status": value.get(
                        "text_layer_projection_status"
                    ),
                    "pdf_visible_content_coverage_status": value.get(
                        "visible_content_coverage_status"
                    ),
                    "ocr_vlm_used": value.get("ocr_vlm_used"),
                    "page_rendering_used_for_extraction": value.get(
                        "page_rendering_used_for_extraction"
                    ),
                },
            )
        if collection_name == "private_normalized_source_units":
            document_id = str(value.get("document_id") or "")
            return (
                "private_normalized_source_unit_v0",
                document_id,
                {
                    "schema_version": value.get("schema_version"),
                    "document_ref": document_id,
                    "unit_ref": value.get("unit_ref"),
                    "parent_payload_ref": value.get("parent_payload_ref"),
                    "parser_ref": value.get("parser_ref"),
                    "source_checksum_ref": value.get("source_checksum_ref"),
                    "payload_checksum_ref": value.get("payload_checksum_ref"),
                    "source_unit_checksum_ref": value.get("source_unit_checksum_ref"),
                    "coverage_ref": (value.get("coverage") or {}).get("coverage_ref"),
                    "coverage_selected_total": (value.get("coverage") or {}).get(
                        "selected_total"
                    ),
                    "source_slice_truncated": value.get("source_slice_truncated"),
                    "parent_remainder_status": value.get("parent_remainder_status"),
                    "parser_completeness_status": value.get(
                        "parser_completeness_status"
                    ),
                    "pdf_unit_type": value.get("pdf_unit_type"),
                    "pdf_text_layer_projection_status": value.get(
                        "text_layer_projection_status"
                    ),
                    "ocr_vlm_used": value.get("ocr_vlm_used"),
                    "page_rendering_used_for_extraction": value.get(
                        "page_rendering_used_for_extraction"
                    ),
                },
            )
        if collection_name == "private_normalized_table_projections":
            document_id = str(value.get("source_document_ref") or "")
            return (
                "broker_reports_normalized_table_projection_v0",
                document_id,
                {
                    "schema_version": value.get("schema_version"),
                    "table_projection_id": value.get("table_projection_id"),
                    "table_ref": value.get("table_ref"),
                    "source_document_ref": document_id,
                    "source_unit_ref": value.get("source_unit_ref"),
                    "source_unit_refs_count": len(value.get("source_unit_refs") or []),
                    "source_format": value.get("source_format"),
                    "table_origin": value.get("table_origin"),
                    "projection_status": value.get("projection_status"),
                    "table_candidate_status": value.get("table_candidate_status"),
                    "reconstruction_quality": value.get("reconstruction_quality"),
                    "row_count": int(value.get("row_count") or 0),
                    "column_count": int(value.get("column_count") or 0),
                    "cell_count": int(value.get("cell_count") or 0),
                    "source_value_refs_count": len(
                        value.get("source_value_refs") or []
                    ),
                    "fallback_refs_count": len(
                        (value.get("coverage") or {}).get("fallback_text_refs") or []
                    ),
                    "coverage_status": (value.get("coverage") or {}).get(
                        "coverage_status"
                    ),
                    "canonical_table_id": value.get("canonical_table_id"),
                    "logical_table_id": value.get("logical_table_id"),
                    "canonical_profile_id": value.get("canonical_profile_id"),
                    "canonical_table_scope": value.get("canonical_table_scope"),
                    "canonical_validation_status": (
                        value.get("canonical_validation") or {}
                    ).get("validator_status"),
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                },
            )
        raise Gate1BoundedGraphError("bounded_collection_name_unsupported")

    @staticmethod
    def _compact_value(
        collection_name: str,
        value: dict[str, Any],
    ) -> dict[str, Any]:
        """Retain only safe accounting metadata needed after persistence."""

        if collection_name == "private_normalized_source_payloads":
            coverage = value.get("coverage_index") or {}
            source_location = value.get("source_location") or {}
            return {
                "source_payload_ref": value.get("source_payload_ref"),
                "document_ref": value.get("document_ref"),
                "container_format": value.get("container_format"),
                "source_location": {"encoding": source_location.get("encoding")},
                "format_reason_codes": list(value.get("format_reason_codes") or []),
                "extraction_unit_refs": list(value.get("extraction_unit_refs") or []),
                "coverage_index": {
                    "all_selected_refs_accounted": coverage.get(
                        "all_selected_refs_accounted"
                    ),
                    "unaccounted_refs": list(coverage.get("unaccounted_refs") or []),
                    "duplicate_accounted_refs": list(
                        coverage.get("duplicate_accounted_refs") or []
                    ),
                },
                "rows_total": int(value.get("rows_total") or 0),
                "cells_total": int(value.get("cells_total") or 0),
                "text_characters_total": int(value.get("text_characters_total") or 0),
                "page_refs_count": len(value.get("page_refs") or []),
            }
        if collection_name == "private_normalized_source_units":
            coverage = value.get("coverage") or {}
            return {
                "unit_ref": value.get("unit_ref"),
                "parent_payload_ref": value.get("parent_payload_ref"),
                "document_id": value.get("document_id"),
                "slice_type": value.get("slice_type"),
                "container_format": value.get("container_format"),
                "pdf_unit_type": value.get("pdf_unit_type"),
                "rows_count": int(value.get("rows_count") or 0),
                "rows_in_slice": int(value.get("rows_in_slice") or 0),
                "cell_refs_count": len(value.get("cell_refs") or []),
                "chars_count": int(value.get("chars_count") or 0),
                "characters_in_slice": int(value.get("characters_in_slice") or 0),
                "coverage": {
                    "all_selected_refs_accounted": coverage.get(
                        "all_selected_refs_accounted"
                    ),
                    "unaccounted_refs": list(coverage.get("unaccounted_refs") or []),
                },
            }
        if collection_name == "private_normalized_table_projections":
            coverage = value.get("coverage") or {}
            return {
                "table_projection_id": value.get("table_projection_id"),
                "source_document_ref": value.get("source_document_ref"),
                "source_unit_ref": value.get("source_unit_ref"),
                "source_format": value.get("source_format"),
                "validator_status": value.get("validator_status"),
                "coverage": {
                    "all_selected_refs_accounted": coverage.get(
                        "all_selected_refs_accounted"
                    )
                },
            }
        return {}

    def _put(
        self,
        *,
        artifact_type: str,
        document_id: str,
        source_file_ref: dict[str, Any],
        visibility: str,
        storage_backend: str,
        validation_status: str,
        payload: dict[str, Any],
        safe_metadata: dict[str, Any],
        access_policy: dict[str, Any],
    ) -> ArtifactRecord:
        now = utc_now_iso()
        record = ArtifactRecord(
            artifact_id=new_artifact_id(),
            artifact_type=artifact_type,
            case_id=self.context.case_id,
            chat_id=self.context.chat_id,
            user_id=self.context.user_id,
            workspace_model_id=self.context.workspace_model_id,
            normalization_run_id=self.context.normalization_run_id,
            document_id=document_id,
            source_file_ref=copy.deepcopy(source_file_ref),
            visibility=visibility,
            storage_backend=storage_backend,
            retention_policy=self.retention_policy,
            access_policy=access_policy,
            validation_status=validation_status,
            lifecycle_status=lifecycle_for_visibility(
                visibility=visibility,
                validation_status=validation_status,
            ),
            payload_kind=(
                "json_file"
                if storage_backend == "project_artifact_payload"
                else "inline_json"
            ),
            payload=payload,
            safe_metadata=safe_metadata,
            created_at=now,
            updated_at=now,
        )
        stored = self.store.put_record(record)
        self.refs_by_type.setdefault(artifact_type, []).append(stored.artifact_id)
        return stored

    def _source_ref_for_document(self, document: dict[str, Any]) -> dict[str, Any]:
        root_ordinal = int(document.get("root_input_ordinal") or 0)
        provided = (
            self.source_file_refs[root_ordinal - 1]
            if 0 < root_ordinal <= len(self.source_file_refs)
            else {}
        )
        return {
            "provider": (
                "bounded_zip_member"
                if document.get("archive_member_ref")
                else provided.get("provider")
                or document.get("source_kind")
                or "unknown"
            ),
            "openwebui_file_id": provided.get("openwebui_file_id"),
            "file_hash_sha256": document.get("sha256")
            or provided.get("file_hash_sha256"),
            "content_type": document.get("declared_mime_type")
            or provided.get("content_type"),
            "size_bytes": document.get("size_bytes") or provided.get("size_bytes"),
            "source_deleted": bool(provided.get("source_deleted", False)),
            "source_delete_observed_at": provided.get("source_delete_observed_at"),
            "archive_parent_document_ref": document.get("archive_parent_document_ref"),
            "archive_member_ref": document.get("archive_member_ref"),
            "archive_member_index": document.get("archive_member_index"),
        }

    def _access_policy(self) -> dict[str, bool]:
        return {
            "requires_user_id": True,
            "requires_case_or_chat": True,
            "requires_workspace_model_id_when_present": bool(
                self.context.workspace_model_id
            ),
        }


def iter_document_values(value: Any, document_id: str) -> Iterator[dict[str, Any]]:
    if isinstance(value, ArtifactStoreBackedList):
        yield from value.iter_document(document_id)
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item


def is_bounded_collection(value: Any) -> bool:
    return isinstance(value, ArtifactStoreBackedList)
