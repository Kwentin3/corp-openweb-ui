"""Immutable current FinancialAnnotations sidecar persistence."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import json
from typing import Any, Mapping

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    new_artifact_id,
)
from .artifact_resolver import ArtifactResolver
from .gate2_model_contracts import gate2_provider_profile
from .gate3_bounded_labeling import (
    FINANCIAL_ANNOTATIONS_SCHEMA_VERSION,
    GATE3_LABELING_INSTRUCTION_ID,
    GATE3_LABELING_INSTRUCTION_VERSION,
)
from .gate3_chunk_batch_labeling import (
    GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION,
    GATE3_SEMANTIC_PUBLICATION_MODE_DEMAND_SCOPED,
    GATE3_SEMANTIC_PUBLICATION_MODE_FULL,
)
from .gate3_financial_label_dictionary import (
    Gate3FinancialLabelDictionaryFactory,
)
from .gate3_financial_role_pack import (
    Gate3FinancialRolePackFactory,
)
from .gate3_role_labeling import (
    FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION,
    GATE3_ROLE_LABELING_INSTRUCTION_ID,
    GATE3_ROLE_LABELING_INSTRUCTION_VERSION,
    Gate3RoleLabelingError,
    Gate3RoleValueResolverFactory,
)
from .gate3_structural_chunking import Gate3StructuralChunkFactory


GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE = FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION
GATE3_HISTORICAL_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE = (
    FINANCIAL_ANNOTATIONS_SCHEMA_VERSION
)
FACTORY_REQUIRED = (
    "Gate3FinancialAnnotationsPersistenceFactory.create is the only G3.5 "
    "sidecar persistence entrypoint; it must delegate storage and lifecycle "
    "to ArtifactStore and reads to ArtifactResolver"
)
FORBIDDEN = (
    "G3.5 must not persist incomplete batches, mutate CanonicalArtifactV1, "
    "reclassify financial meaning, repair annotations, create a database or "
    "bypass ArtifactStore access, immutability, retention or purge"
)

_DOCUMENT_RESULT_KEYS = {
    "schema_version",
    "semantic_scope",
    "selected_chunk_ordinals",
    "selection_mode",
    "document_status",
    "metrics",
    "merged_output",
}
_SEMANTIC_SCOPE_KEYS = {
    "publication_mode",
    "document_id",
    "requested_financial_labels",
    "requested_roles",
    "selected_chunk_ordinals",
}
_V2_PAYLOAD_KEYS = {
    "schema_version",
    "canonical_binding",
    "dictionary_identity",
    "role_pack_identity",
    "instruction_identity",
    "role_instruction_identity",
    "model_identity",
    "annotations",
    "validation_status",
}
_V1_PAYLOAD_KEYS = _V2_PAYLOAD_KEYS - {
    "role_pack_identity",
    "role_instruction_identity",
}


class Gate3FinancialAnnotationsPersistenceError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate3FinancialAnnotationsRecoveryResult:
    record: ArtifactRecord
    receipt: dict[str, Any]


class Gate3FinancialAnnotationsPersistenceFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate3FinancialAnnotationsPersistence":
        return Gate3FinancialAnnotationsPersistence(
            store=self._store,
            read_enabled=self._read_enabled,
        )


class Gate3FinancialAnnotationsPersistence:
    """Validate and persist one complete document result as a private sidecar."""

    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._resolver = ArtifactResolver(store)

    def save(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        validated_document_result: Mapping[str, Any],
        provider_profile_id: str,
    ) -> ArtifactRecord:
        if not isinstance(document_id, str) or not document_id:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_document_id_required"
            )
        chunk_set = Gate3StructuralChunkFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create(document_id=document_id, context=context)
        payload = self._validated_payload(
            document_id=document_id,
            context=context,
            document_result=validated_document_result,
            chunk_set=chunk_set,
            provider_profile_id=provider_profile_id,
            expected_publication_mode=GATE3_SEMANTIC_PUBLICATION_MODE_FULL,
        )
        version = self._store.get_active_canonical_version(
            context=context,
            document_id=document_id,
        )
        if (
            version.canonical_version_id
            != payload["canonical_binding"]["canonical_version_id"]
            or not version.manifest_ref
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_canonical_binding_mismatch"
            )
        manifest_record = self._resolver.resolve_record(
            version.manifest_ref,
            context,
        )
        stored = self._store.put_record(
            ArtifactRecord(
                artifact_id=new_artifact_id(),
                artifact_type=GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
                case_id=context.case_id,
                chat_id=context.chat_id,
                user_id=context.user_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                document_id=document_id,
                source_file_ref=None,
                visibility="private_case",
                storage_backend="project_artifact_payload",
                retention_policy=manifest_record.retention_policy,
                access_policy={
                    "requires_user_id": True,
                    "requires_case_or_chat": True,
                    "requires_workspace_model_id_when_present": bool(
                        context.workspace_model_id
                    ),
                    "financial_annotations_sidecar_only": True,
                },
                validation_status="validated",
                lifecycle_status=lifecycle_for_visibility(
                    visibility="private_case",
                    validation_status="validated",
                ),
                payload_kind="json_file",
                payload=copy.deepcopy(payload),
                safe_metadata={
                    "provider_profile_id": provider_profile_id,
                    "document_completion_status": validated_document_result[
                        "document_status"
                    ],
                    "source_fact_completeness_status": validated_document_result[
                        "metrics"
                    ]["source_fact_completeness_status"],
                    "annotations_total": len(payload["annotations"]),
                    "facts_role_complete": validated_document_result["metrics"][
                        "facts_role_complete"
                    ],
                    "facts_role_incomplete": validated_document_result["metrics"][
                        "facts_role_incomplete"
                    ],
                    "facts_incomplete_due_to_role_rejection": (
                        validated_document_result["metrics"][
                            "facts_incomplete_due_to_role_rejection"
                        ]
                    ),
                    "facts_rejected": validated_document_result["metrics"][
                        "facts_rejected"
                    ],
                    "role_bindings_rejected": validated_document_result["metrics"][
                        "role_bindings_rejected"
                    ],
                    "chunks_with_local_failures": validated_document_result[
                        "metrics"
                    ]["chunks_with_local_failures"],
                    "publication_mode": GATE3_SEMANTIC_PUBLICATION_MODE_FULL,
                    "semantic_view_mode": "FULL_CURRENT_VIEW",
                },
            )
        )
        return stored

    def save_recovery(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        validated_document_result: Mapping[str, Any],
        provider_profile_id: str,
        base_annotations_artifact_id: str,
        demand_request_id: str,
    ) -> Gate3FinancialAnnotationsRecoveryResult:
        """Publish a demand delta as a new non-destructive full current view."""

        if not isinstance(demand_request_id, str) or not demand_request_id:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_recovery_demand_id_required"
            )
        if (
            not isinstance(base_annotations_artifact_id, str)
            or not base_annotations_artifact_id
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_recovery_base_required"
            )
        chunk_set = Gate3StructuralChunkFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create(document_id=document_id, context=context)
        delta = self._validated_payload(
            document_id=document_id,
            context=context,
            document_result=validated_document_result,
            chunk_set=chunk_set,
            provider_profile_id=provider_profile_id,
            expected_publication_mode=(GATE3_SEMANTIC_PUBLICATION_MODE_DEMAND_SCOPED),
            allow_empty=True,
        )
        current_record, current_payload = self._current_annotations(
            document_id=document_id,
            context=context,
            canonical_version_id=chunk_set["canonical_binding"]["canonical_version_id"],
        )
        if current_record.artifact_id != base_annotations_artifact_id:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_recovery_base_stale"
            )
        base_profile_id = current_record.safe_metadata.get("provider_profile_id")
        if base_profile_id != provider_profile_id:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_recovery_authority_mismatch"
            )
        requested_labels = validated_document_result["semantic_scope"][
            "requested_financial_labels"
        ]
        requested_roles = validated_document_result["semantic_scope"]["requested_roles"]
        merged_payload, counts = self._merge_recovery(
            base=current_payload,
            delta=delta,
            requested_financial_labels=requested_labels,
        )
        version = self._store.get_active_canonical_version(
            context=context,
            document_id=document_id,
        )
        if (
            version.canonical_version_id
            != merged_payload["canonical_binding"]["canonical_version_id"]
            or not version.manifest_ref
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_canonical_binding_mismatch"
            )
        manifest_record = self._resolver.resolve_record(version.manifest_ref, context)
        receipt = {
            "demand_request_id": demand_request_id,
            "base_annotations_artifact_id": base_annotations_artifact_id,
            "publication_mode": GATE3_SEMANTIC_PUBLICATION_MODE_DEMAND_SCOPED,
            "semantic_view_mode": "FULL_CURRENT_VIEW",
            "requested_financial_labels": list(requested_labels),
            "requested_roles": list(requested_roles),
            **counts,
            "conflicts_total": 0,
            "deleted_total": 0,
        }
        stored = self._store.put_record(
            ArtifactRecord(
                artifact_id=new_artifact_id(),
                artifact_type=GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
                case_id=context.case_id,
                chat_id=context.chat_id,
                user_id=context.user_id,
                workspace_model_id=context.workspace_model_id,
                normalization_run_id=context.normalization_run_id,
                document_id=document_id,
                source_file_ref=None,
                visibility="private_case",
                storage_backend="project_artifact_payload",
                retention_policy=manifest_record.retention_policy,
                access_policy={
                    "requires_user_id": True,
                    "requires_case_or_chat": True,
                    "requires_workspace_model_id_when_present": bool(
                        context.workspace_model_id
                    ),
                    "financial_annotations_sidecar_only": True,
                },
                validation_status="validated",
                lifecycle_status=lifecycle_for_visibility(
                    visibility="private_case",
                    validation_status="validated",
                ),
                payload_kind="json_file",
                payload=copy.deepcopy(merged_payload),
                safe_metadata={
                    "provider_profile_id": provider_profile_id,
                    "document_completion_status": "complete",
                    "annotations_total": len(merged_payload["annotations"]),
                    **receipt,
                },
            )
        )
        return Gate3FinancialAnnotationsRecoveryResult(
            record=stored,
            receipt={**receipt, "result_annotations_artifact_id": stored.artifact_id},
        )

    def read(
        self,
        *,
        artifact_id: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        resolved = self._resolver.resolve(artifact_id, context)
        record = resolved["record"]
        payload = resolved["payload"]
        if (
            record.artifact_type
            not in {
                GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
                GATE3_HISTORICAL_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
            }
            or not isinstance(payload, dict)
            or record.document_id
            != (payload.get("canonical_binding") or {}).get("document_id")
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_artifact_invalid"
            )
        provider_profile_id = record.safe_metadata.get("provider_profile_id")
        if record.artifact_type == GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE:
            self._validate_payload_contract(
                payload=payload,
                provider_profile_id=provider_profile_id,
            )
        else:
            self._validate_historical_v1_payload_contract(
                payload=payload,
                provider_profile_id=provider_profile_id,
            )
        version = self._store.get_canonical_version(
            context=context,
            canonical_version_id=payload["canonical_binding"]["canonical_version_id"],
        )
        if version.document_id != record.document_id:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_canonical_binding_mismatch"
            )
        return copy.deepcopy(payload)

    def _validated_payload(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        document_result: Mapping[str, Any],
        chunk_set: dict[str, Any],
        provider_profile_id: str,
        expected_publication_mode: str,
        allow_empty: bool = False,
    ) -> dict[str, Any] | None:
        semantic_scope = (
            document_result.get("semantic_scope")
            if isinstance(document_result, Mapping)
            else None
        )
        if (
            not isinstance(document_result, Mapping)
            or set(document_result) != _DOCUMENT_RESULT_KEYS
            or document_result.get("schema_version")
            != GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION
            or not isinstance(semantic_scope, Mapping)
            or set(semantic_scope) != _SEMANTIC_SCOPE_KEYS
            or semantic_scope.get("publication_mode") != expected_publication_mode
            or semantic_scope.get("document_id") != document_id
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_publication_scope_invalid"
            )
        ordinals = tuple(
            int(chunk["ordinal"]) for chunk in chunk_set.get("chunks") or []
        )
        selected = document_result.get("selected_chunk_ordinals")
        metrics = document_result.get("metrics")
        payload = document_result.get("merged_output")
        requested_labels = semantic_scope.get("requested_financial_labels")
        requested_roles = semantic_scope.get("requested_roles")
        if (
            not isinstance(requested_labels, list)
            or any(
                not isinstance(value, str) or not value for value in requested_labels
            )
            or requested_labels != sorted(set(requested_labels))
            or not isinstance(requested_roles, list)
            or any(not isinstance(value, str) or not value for value in requested_roles)
            or requested_roles != sorted(set(requested_roles))
            or semantic_scope.get("selected_chunk_ordinals") != list(selected or [])
            or (
                expected_publication_mode == GATE3_SEMANTIC_PUBLICATION_MODE_FULL
                and requested_labels
            )
            or (
                expected_publication_mode == GATE3_SEMANTIC_PUBLICATION_MODE_FULL
                and requested_roles
            )
            or (
                expected_publication_mode
                == GATE3_SEMANTIC_PUBLICATION_MODE_DEMAND_SCOPED
                and not requested_labels
            )
            or (
                expected_publication_mode
                == GATE3_SEMANTIC_PUBLICATION_MODE_DEMAND_SCOPED
                and not requested_roles
            )
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_publication_scope_invalid"
            )
        full_publication = (
            expected_publication_mode == GATE3_SEMANTIC_PUBLICATION_MODE_FULL
        )
        if (
            not ordinals
            or not isinstance(selected, (list, tuple))
            or not selected
            or any(value not in ordinals for value in selected)
            or (full_publication and tuple(selected) != ordinals)
            or not isinstance(metrics, Mapping)
            or metrics.get("chunks_total") != len(selected)
            or metrics.get("chunks_validated") != len(selected)
            or metrics.get("chunks_rejected") != 0
            or metrics.get("chunks_provider_failed") != 0
            or (
                full_publication
                and (
                    document_result.get("selection_mode") != "full_document"
                    or document_result.get("document_status") != "complete"
                )
            )
            or (
                not full_publication
                and document_result.get("document_status")
                not in {"complete", "representative_subset_validated"}
            )
            or not (isinstance(payload, dict) or allow_empty and payload is None)
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_document_result_incomplete"
            )
        if not _local_failure_metrics_valid(metrics):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_document_result_incomplete"
            )
        if payload is None:
            if metrics.get("annotations_validated") != 0:
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_document_result_incomplete"
                )
            return None
        self._validate_payload_contract(
            payload=payload,
            provider_profile_id=provider_profile_id,
        )
        binding = chunk_set.get("canonical_binding")
        if (
            payload["canonical_binding"] != binding
            or binding.get("document_id") != document_id
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_canonical_binding_mismatch"
            )
        annotations = payload["annotations"]
        if not full_publication and any(
            annotation["financial_label"] not in requested_labels
            for annotation in annotations
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_recovery_label_out_of_scope"
            )
        if metrics.get("annotations_validated") != len(annotations):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_document_result_incomplete"
            )
        known_targets = {
            _stable_json(mapping["canonical_target"])
            for chunk in chunk_set["chunks"]
            for mapping in chunk["target_mappings"]
        }
        try:
            resolver = Gate3RoleValueResolverFactory.create_from_active_canonical(
                store=self._store,
                read_enabled=self._read_enabled,
                document_id=document_id,
                expected_canonical_version_id=binding["canonical_version_id"],
                context=context,
            )
        except Gate3RoleLabelingError as exc:
            if exc.code == "gate3_role_canonical_binding_stale":
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_canonical_binding_mismatch"
                ) from exc
            raise Gate3FinancialAnnotationsPersistenceError(exc.code) from exc
        seen: set[str] = set()
        for annotation in annotations:
            identity = _stable_json(annotation)
            target = _stable_json(annotation["target"])
            if target not in known_targets:
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_target_unknown"
                )
            if identity in seen:
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_duplicate"
                )
            seen.add(identity)
            for role_binding in annotation["roles"]:
                if role_binding["status"] != "bound":
                    continue
                if _stable_json(role_binding["target"]) not in known_targets:
                    raise Gate3FinancialAnnotationsPersistenceError(
                        "gate3_annotations_role_target_unknown"
                    )
                try:
                    resolver.resolve(role_binding)
                except Gate3RoleLabelingError as exc:
                    raise Gate3FinancialAnnotationsPersistenceError(exc.code) from exc
        return copy.deepcopy(payload)

    def _current_annotations(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        canonical_version_id: str,
    ) -> tuple[ArtifactRecord, dict[str, Any]]:
        current: list[tuple[ArtifactRecord, dict[str, Any]]] = []
        for record in self._resolver.catalog_run(context):
            if (
                record.document_id != document_id
                or record.artifact_type != GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
                or record.validation_status != "validated"
                or record.lifecycle_status
                in {
                    "blocked",
                    "expired",
                    "purge_pending",
                    "purged",
                    "privacy_failed",
                }
                or record.purge_status
                in {"blocked", "expired", "purge_pending", "purged"}
            ):
                continue
            payload = self.read(artifact_id=record.artifact_id, context=context)
            if (
                payload["canonical_binding"]["canonical_version_id"]
                == canonical_version_id
            ):
                current.append((record, payload))
        if not current:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_recovery_base_missing"
            )
        current.sort(key=lambda item: (item[0].created_at, item[0].artifact_id))
        return current[-1]

    @staticmethod
    def _merge_recovery(
        *,
        base: dict[str, Any],
        delta: dict[str, Any] | None,
        requested_financial_labels: list[str],
    ) -> tuple[dict[str, Any], dict[str, int]]:
        merged = copy.deepcopy(base)
        base_annotations = merged["annotations"]
        by_assertion: dict[tuple[str, str], int] = {}
        for index, annotation in enumerate(base_annotations):
            key = (_stable_json(annotation["target"]), annotation["financial_label"])
            if key in by_assertion:
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_recovery_base_ambiguous"
                )
            by_assertion[key] = index
        for left_index, left in enumerate(base_annotations):
            if any(
                _same_table_row_source_assertion(left, right)
                for right in base_annotations[left_index + 1 :]
            ):
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_recovery_base_ambiguous"
                )
        added = 0
        superseded = 0
        unchanged = 0
        delta_annotations = [] if delta is None else delta["annotations"]
        if delta is not None:
            identity_fields = (
                "schema_version",
                "canonical_binding",
                "dictionary_identity",
                "role_pack_identity",
                "instruction_identity",
                "role_instruction_identity",
                "model_identity",
                "validation_status",
            )
            if any(delta[field] != base[field] for field in identity_fields):
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_recovery_authority_mismatch"
                )
        seen_delta: set[tuple[str, str]] = set()
        accepted_delta: list[dict[str, Any]] = []
        for proposal in delta_annotations:
            if proposal["financial_label"] not in requested_financial_labels:
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_recovery_label_out_of_scope"
                )
            key = (_stable_json(proposal["target"]), proposal["financial_label"])
            if key in seen_delta:
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_recovery_delta_ambiguous"
                )
            if any(
                _same_table_row_source_assertion(previous, proposal)
                for previous in accepted_delta
            ):
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_recovery_delta_ambiguous"
                )
            seen_delta.add(key)
            accepted_delta.append(proposal)
            existing_index = by_assertion.get(key)
            if existing_index is None:
                lineage_matches = [
                    index
                    for index, existing in enumerate(base_annotations)
                    if _same_table_row_source_assertion(existing, proposal)
                ]
                if len(lineage_matches) > 1:
                    raise Gate3FinancialAnnotationsPersistenceError(
                        "gate3_annotations_recovery_base_ambiguous"
                    )
                if lineage_matches:
                    existing_index = lineage_matches[0]
                else:
                    by_assertion[key] = len(base_annotations)
                    base_annotations.append(copy.deepcopy(proposal))
                    added += 1
                    continue
            existing = base_annotations[existing_index]
            cross_anchor = _same_table_row_source_assertion(existing, proposal)
            relation = (
                _cross_anchor_merge_relation(existing, proposal)
                if (cross_anchor)
                else _role_completeness_relation(existing, proposal)
            )
            if relation == "same":
                unchanged += 1
            elif relation == "more_complete":
                old_key = (
                    _stable_json(existing["target"]),
                    existing["financial_label"],
                )
                base_annotations[existing_index] = copy.deepcopy(proposal)
                by_assertion.pop(old_key, None)
                by_assertion[key] = existing_index
                superseded += 1
            else:
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_recovery_conflict"
                )
        return merged, {
            "added_total": added,
            "superseded_total": superseded,
            "unchanged_recovered_total": unchanged,
            "preserved_unrelated_total": sum(
                annotation["financial_label"] not in requested_financial_labels
                for annotation in base["annotations"]
            ),
        }

    @staticmethod
    def _validate_payload_contract(
        *,
        payload: dict[str, Any],
        provider_profile_id: Any,
    ) -> None:
        if (
            set(payload) != _V2_PAYLOAD_KEYS
            or payload.get("schema_version") != FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION
            or payload.get("validation_status") != "validated"
            or not isinstance(payload.get("canonical_binding"), dict)
            or set(payload["canonical_binding"])
            != {"document_id", "canonical_version_id"}
            or not all(
                isinstance(value, str) and value
                for value in payload["canonical_binding"].values()
            )
            or not isinstance(payload.get("dictionary_identity"), dict)
            or set(payload["dictionary_identity"])
            != {"dictionary_id", "semantic_version"}
            or not isinstance(payload.get("role_pack_identity"), dict)
            or set(payload["role_pack_identity"])
            != {"role_pack_id", "semantic_version"}
            or not isinstance(payload.get("instruction_identity"), dict)
            or set(payload["instruction_identity"])
            != {"instruction_id", "semantic_version"}
            or payload["instruction_identity"]
            != {
                "instruction_id": GATE3_LABELING_INSTRUCTION_ID,
                "semantic_version": GATE3_LABELING_INSTRUCTION_VERSION,
            }
            or not isinstance(payload.get("role_instruction_identity"), dict)
            or set(payload["role_instruction_identity"])
            != {"instruction_id", "semantic_version"}
            or payload["role_instruction_identity"]
            != {
                "instruction_id": GATE3_ROLE_LABELING_INSTRUCTION_ID,
                "semantic_version": GATE3_ROLE_LABELING_INSTRUCTION_VERSION,
            }
            or not isinstance(payload.get("model_identity"), dict)
            or set(payload["model_identity"]) != {"model_id"}
            or not isinstance(payload["model_identity"]["model_id"], str)
            or not payload["model_identity"]["model_id"]
            or not isinstance(payload.get("annotations"), list)
            or not isinstance(provider_profile_id, str)
            or not provider_profile_id
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_payload_contract_invalid"
            )
        dictionary = Gate3FinancialLabelDictionaryFactory.create().load_published(
            payload["dictionary_identity"]["semantic_version"]
        )
        if payload["dictionary_identity"] != {
            "dictionary_id": dictionary["dictionary_id"],
            "semantic_version": dictionary["semantic_version"],
        }:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_dictionary_identity_mismatch"
            )
        role_pack = Gate3FinancialRolePackFactory.create().load_published(
            payload.get("role_pack_identity", {}).get("semantic_version")
        )
        if payload["role_pack_identity"] != {
            "role_pack_id": role_pack["role_pack_id"],
            "semantic_version": role_pack["semantic_version"],
        }:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_role_pack_identity_mismatch"
            )
        known_labels = {item["label_id"] for item in dictionary["labels"]}
        profiles = {
            profile["financial_label"]: profile for profile in role_pack["profiles"]
        }
        for annotation in payload["annotations"]:
            if (
                not isinstance(annotation, dict)
                or set(annotation) != {"target", "financial_label", "roles"}
                or not isinstance(annotation.get("target"), dict)
                or annotation.get("financial_label") not in known_labels
                or not isinstance(annotation.get("roles"), list)
            ):
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_payload_contract_invalid"
                )
            profile = profiles[annotation["financial_label"]]
            allowed_order = [
                *profile["required_roles"],
                *profile["optional_roles"],
            ]
            if [item.get("role") for item in annotation["roles"]] != allowed_order:
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_role_cardinality_invalid"
                )
            for role_binding in annotation["roles"]:
                status = role_binding.get("status")
                if status == "missing":
                    valid = set(role_binding) == {"role", "status"}
                elif status == "bound":
                    valid = (
                        set(role_binding)
                        in (
                            {"role", "status", "target"},
                            {"role", "status", "target", "exact_text"},
                        )
                        and isinstance(role_binding.get("target"), dict)
                        and (
                            "exact_text" not in role_binding
                            or isinstance(role_binding["exact_text"], str)
                            and 0 < len(role_binding["exact_text"]) <= 2048
                        )
                    )
                else:
                    valid = False
                if not valid:
                    raise Gate3FinancialAnnotationsPersistenceError(
                        "gate3_annotations_role_binding_invalid"
                    )
        try:
            profile = gate2_provider_profile(provider_profile_id)
        except Exception as exc:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_model_identity_mismatch"
            ) from exc
        if payload["model_identity"]["model_id"] not in profile.approved_model_ids:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_model_identity_mismatch"
            )

    @staticmethod
    def _validate_historical_v1_payload_contract(
        *,
        payload: dict[str, Any],
        provider_profile_id: Any,
    ) -> None:
        if (
            set(payload) != _V1_PAYLOAD_KEYS
            or payload.get("schema_version") != FINANCIAL_ANNOTATIONS_SCHEMA_VERSION
            or payload.get("validation_status") != "validated"
            or not isinstance(payload.get("canonical_binding"), dict)
            or set(payload["canonical_binding"])
            != {"document_id", "canonical_version_id"}
            or not all(
                isinstance(value, str) and value
                for value in payload["canonical_binding"].values()
            )
            or not isinstance(payload.get("dictionary_identity"), dict)
            or set(payload["dictionary_identity"])
            != {"dictionary_id", "semantic_version"}
            or not isinstance(payload.get("instruction_identity"), dict)
            or payload["instruction_identity"]
            != {
                "instruction_id": GATE3_LABELING_INSTRUCTION_ID,
                "semantic_version": GATE3_LABELING_INSTRUCTION_VERSION,
            }
            or not isinstance(payload.get("model_identity"), dict)
            or set(payload["model_identity"]) != {"model_id"}
            or not isinstance(payload["model_identity"]["model_id"], str)
            or not payload["model_identity"]["model_id"]
            or not isinstance(payload.get("annotations"), list)
            or not isinstance(provider_profile_id, str)
            or not provider_profile_id
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_payload_contract_invalid"
            )
        dictionary = Gate3FinancialLabelDictionaryFactory.create().load_published(
            payload["dictionary_identity"]["semantic_version"]
        )
        if payload["dictionary_identity"] != {
            "dictionary_id": dictionary["dictionary_id"],
            "semantic_version": dictionary["semantic_version"],
        }:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_dictionary_identity_mismatch"
            )
        known_labels = {item["label_id"] for item in dictionary["labels"]}
        for annotation in payload["annotations"]:
            if (
                not isinstance(annotation, dict)
                or set(annotation) != {"target", "financial_label"}
                or not isinstance(annotation.get("target"), dict)
                or annotation.get("financial_label") not in known_labels
            ):
                raise Gate3FinancialAnnotationsPersistenceError(
                    "gate3_annotations_payload_contract_invalid"
                )
        try:
            profile = gate2_provider_profile(provider_profile_id)
        except Exception as exc:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_model_identity_mismatch"
            ) from exc
        if payload["model_identity"]["model_id"] not in profile.approved_model_ids:
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_model_identity_mismatch"
            )


def _local_failure_metrics_valid(metrics: Mapping[str, Any]) -> bool:
    integer_fields = (
        "chunks_total",
        "chunks_validated",
        "chunks_rejected",
        "chunks_provider_failed",
        "chunks_with_local_failures",
        "fully_unusable_chunks",
        "annotations_validated",
        "facts_role_complete",
        "facts_role_incomplete",
        "facts_incomplete_due_to_role_rejection",
        "facts_rejected",
        "role_bindings_rejected",
    )
    if any(
        isinstance(metrics.get(field), bool)
        or not isinstance(metrics.get(field), int)
        or metrics[field] < 0
        for field in integer_fields
    ):
        return False
    if (
        metrics["chunks_validated"] + metrics["chunks_rejected"]
        + metrics["chunks_provider_failed"]
        != metrics["chunks_total"]
        or metrics["chunks_with_local_failures"] > metrics["chunks_validated"]
        or metrics["fully_unusable_chunks"]
        != metrics["chunks_rejected"] + metrics["chunks_provider_failed"]
        or metrics["facts_role_complete"] + metrics["facts_role_incomplete"]
        != metrics["annotations_validated"]
        or metrics["facts_incomplete_due_to_role_rejection"]
        > metrics["facts_role_incomplete"]
        or metrics["role_bindings_rejected"]
        < metrics["facts_incomplete_due_to_role_rejection"]
    ):
        return False
    expected_completeness = (
        "complete"
        if metrics["facts_role_incomplete"] == 0
        and metrics["facts_rejected"] == 0
        and metrics["chunks_provider_failed"] == 0
        else "incomplete"
    )
    return metrics.get("source_fact_completeness_status") == expected_completeness


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise Gate3FinancialAnnotationsPersistenceError(
            "gate3_annotations_payload_contract_invalid"
        ) from exc


def _role_completeness_relation(
    existing: Mapping[str, Any], proposal: Mapping[str, Any]
) -> str:
    improved = False
    for old, new in zip(existing["roles"], proposal["roles"], strict=True):
        if old["role"] != new["role"]:
            return "conflict"
        if old["status"] == "missing" and new["status"] == "bound":
            improved = True
            continue
        if old != new:
            return "conflict"
    return "more_complete" if improved else "same"


def _same_table_row_source_assertion(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> bool:
    """Prove one row-owned assertion across cell and row Canonical anchors."""

    if left.get("financial_label") != right.get("financial_label"):
        return False
    left_target = left.get("target")
    right_target = right.get("target")
    if not isinstance(left_target, Mapping) or not isinstance(right_target, Mapping):
        return False
    if {left_target.get("kind"), right_target.get("kind")} != {
        "table_cell",
        "table_row",
    }:
        return False
    left_owner = _table_row_owner(left)
    return left_owner is not None and left_owner == _table_row_owner(right)


def _table_row_owner(annotation: Mapping[str, Any]) -> tuple[str, int] | None:
    target = annotation.get("target")
    if not isinstance(target, Mapping) or target.get("kind") not in {
        "table_cell",
        "table_row",
    }:
        return None
    node_id = target.get("node_id")
    row = target.get("row")
    if not isinstance(node_id, str) or not node_id or not isinstance(row, int):
        return None
    owner = (node_id, row)
    roles = annotation.get("roles")
    if not isinstance(roles, list):
        return None
    for binding in roles:
        if not isinstance(binding, Mapping) or binding.get("status") != "bound":
            continue
        role_target = binding.get("target")
        if (
            not isinstance(role_target, Mapping)
            or role_target.get("kind") not in {"table_cell", "table_row"}
            or (role_target.get("node_id"), role_target.get("row")) != owner
        ):
            return None
    return owner


def _cross_anchor_merge_relation(
    existing: Mapping[str, Any], proposal: Mapping[str, Any]
) -> str:
    role_relation = _role_completeness_relation(existing, proposal)
    if role_relation == "conflict":
        return "conflict"
    existing_kind = existing["target"].get("kind")
    proposal_kind = proposal["target"].get("kind")
    if existing_kind == "table_cell" and proposal_kind == "table_row":
        return "more_complete"
    if existing_kind == "table_row" and proposal_kind == "table_cell":
        return "same" if role_relation == "same" else "conflict"
    return "conflict"


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE",
    "GATE3_HISTORICAL_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE",
    "Gate3FinancialAnnotationsPersistence",
    "Gate3FinancialAnnotationsPersistenceError",
    "Gate3FinancialAnnotationsPersistenceFactory",
    "Gate3FinancialAnnotationsRecoveryResult",
]
