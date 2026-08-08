"""Immutable current FinancialAnnotations sidecar persistence."""

from __future__ import annotations

import copy
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


GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE = (
    FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION
)
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
    "selected_chunk_ordinals",
    "selection_mode",
    "document_status",
    "metrics",
    "merged_output",
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
                    "document_completion_status": "complete",
                    "annotations_total": len(payload["annotations"]),
                },
            )
        )
        return stored

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
            canonical_version_id=payload["canonical_binding"][
                "canonical_version_id"
            ],
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
    ) -> dict[str, Any]:
        if (
            not isinstance(document_result, Mapping)
            or set(document_result) != _DOCUMENT_RESULT_KEYS
            or document_result.get("schema_version")
            != GATE3_CHUNK_BATCH_LABELING_RESULT_SCHEMA_VERSION
            or document_result.get("selection_mode") != "full_document"
            or document_result.get("document_status") != "complete"
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_document_result_incomplete"
            )
        ordinals = tuple(
            int(chunk["ordinal"]) for chunk in chunk_set.get("chunks") or []
        )
        selected = document_result.get("selected_chunk_ordinals")
        metrics = document_result.get("metrics")
        payload = document_result.get("merged_output")
        if (
            not ordinals
            or not isinstance(selected, (list, tuple))
            or tuple(selected) != ordinals
            or not isinstance(metrics, Mapping)
            or metrics.get("chunks_total") != len(ordinals)
            or metrics.get("chunks_validated") != len(ordinals)
            or metrics.get("chunks_rejected") != 0
            or metrics.get("chunks_provider_failed") != 0
            or not isinstance(payload, dict)
        ):
            raise Gate3FinancialAnnotationsPersistenceError(
                "gate3_annotations_document_result_incomplete"
            )
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
            resolver = (
                Gate3RoleValueResolverFactory.create_from_active_canonical(
                    store=self._store,
                    read_enabled=self._read_enabled,
                    document_id=document_id,
                    expected_canonical_version_id=binding[
                        "canonical_version_id"
                    ],
                    context=context,
                )
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
                    raise Gate3FinancialAnnotationsPersistenceError(
                        exc.code
                    ) from exc
        return copy.deepcopy(payload)

    @staticmethod
    def _validate_payload_contract(
        *,
        payload: dict[str, Any],
        provider_profile_id: Any,
    ) -> None:
        if (
            set(payload) != _V2_PAYLOAD_KEYS
            or payload.get("schema_version")
            != FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION
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
            profile["financial_label"]: profile
            for profile in role_pack["profiles"]
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
            or payload.get("schema_version")
            != FINANCIAL_ANNOTATIONS_SCHEMA_VERSION
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


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE",
    "GATE3_HISTORICAL_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE",
    "Gate3FinancialAnnotationsPersistence",
    "Gate3FinancialAnnotationsPersistenceError",
    "Gate3FinancialAnnotationsPersistenceFactory",
]
