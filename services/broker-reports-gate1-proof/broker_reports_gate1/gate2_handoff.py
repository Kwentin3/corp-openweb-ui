from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import ArtifactAccessContext, ArtifactRecord, RetentionPolicy, utc_now_iso
from .artifact_store import SqliteArtifactStoreAdapter, new_artifact_id


@dataclass(frozen=True)
class Gate1ArtifactManifest:
    normalization_run_id: str
    gate2_handoff_ref: str
    safe_refs: list[str]
    private_slice_refs: list[str]
    blocker_refs: list[str]
    artifact_refs_by_type: dict[str, list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalization_run_id": self.normalization_run_id,
            "gate2_handoff_ref": self.gate2_handoff_ref,
            "safe_refs": list(self.safe_refs),
            "private_slice_refs": list(self.private_slice_refs),
            "blocker_refs": list(self.blocker_refs),
            "artifact_refs_by_type": {key: list(value) for key, value in self.artifact_refs_by_type.items()},
        }


def persist_gate1_result(
    *,
    store: SqliteArtifactStoreAdapter,
    result,
    context: ArtifactAccessContext,
    retention_policy: RetentionPolicy,
    source_file_refs: list[dict[str, Any]] | None = None,
) -> Gate1ArtifactManifest:
    package = result.package
    safe_report = result.safe_report
    run_id = package["normalization_run"]["run_id"]
    validation_status = _validation_status(package)
    documents = package.get("document_inventory", {}).get("documents", [])
    source_refs = _source_refs_for_documents(documents, source_file_refs or [])
    refs_by_type: dict[str, list[str]] = {}
    safe_refs: list[str] = []
    private_refs: list[str] = []
    blocker_refs: list[str] = []

    def put(record: ArtifactRecord) -> ArtifactRecord:
        stored = store.put_record(record)
        refs_by_type.setdefault(stored.artifact_type, []).append(stored.artifact_id)
        return stored

    access_policy = {
        "requires_user_id": True,
        "requires_case_or_chat": True,
        "requires_workspace_model_id_when_present": bool(context.workspace_model_id),
    }

    source_records_by_doc: dict[str, dict[str, Any]] = {}
    for document, source_ref in zip(documents, source_refs):
        source_record = put(
            _record(
                artifact_type="source_file_ref_v0",
                context=context,
                retention_policy=retention_policy,
                document_id=document.get("document_id"),
                source_file_ref=source_ref,
                visibility="safe_internal",
                storage_backend="openwebui_file",
                validation_status=validation_status,
                payload=source_ref,
                safe_metadata={
                    "source_kind": document.get("source_kind"),
                    "container_format": document.get("container_format"),
                },
                access_policy=access_policy,
            )
        )
        source_records_by_doc[str(document.get("document_id"))] = source_record.source_file_ref or source_ref
        safe_refs.append(source_record.artifact_id)

    safe_payloads = [
        ("normalization_run_v0", package["normalization_run"], None),
        ("document_inventory_v0", package["document_inventory"], None),
        ("technical_readability_profile_v0", package["technical_readability_profiles"], None),
        ("taxonomy_candidates_v0", package["taxonomy_candidates"], None),
        ("normalization_blockers_v0", package["normalization_blockers"], None),
        ("validation_result_v0", package["validation_result"], None),
        ("chat_visible_normalization_report_v0", safe_report, "openwebui_chat"),
    ]
    for artifact_type, payload, backend_override in safe_payloads:
        record = put(
            _record(
                artifact_type=artifact_type,
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                source_file_ref=None,
                visibility="chat_visible" if artifact_type == "chat_visible_normalization_report_v0" else "safe_internal",
                storage_backend=backend_override or "project_artifact_store",
                validation_status=validation_status,
                payload=payload,
                safe_metadata=_safe_metadata_for_payload(package, artifact_type),
                access_policy=access_policy,
                warning_codes=_warning_codes(package),
            )
        )
        if artifact_type == "normalization_blockers_v0":
            blocker_refs.append(record.artifact_id)
        else:
            safe_refs.append(record.artifact_id)

    for private_slice in package.get("private_normalized_slices", []):
        artifact_type = (
            "private_normalized_table_slice_v0"
            if private_slice.get("slice_type") == "table_rows"
            else "private_normalized_text_slice_v0"
        )
        document_id = private_slice.get("document_id")
        record = put(
            _record(
                artifact_type=artifact_type,
                context=context,
                retention_policy=retention_policy,
                document_id=document_id,
                source_file_ref=source_records_by_doc.get(str(document_id)),
                visibility="private_case",
                storage_backend="project_artifact_payload",
                validation_status=validation_status,
                payload=private_slice,
                safe_metadata={
                    "slice_type": private_slice.get("slice_type"),
                    "document_id": document_id,
                    "profile_id": private_slice.get("profile_id"),
                },
                access_policy={**access_policy, "requires_gate2_resolver": True},
            )
        )
        private_refs.append(record.artifact_id)

    handoff_payload = {
        "artifact_type": "gate2_handoff_v0",
        "normalization_run_id": run_id,
        "case_id": context.case_id,
        "chat_id": context.chat_id,
        "user_id": context.user_id,
        "validation_status": validation_status,
        "handoff_status": package["normalization_run"]["gate2_handoff_status"],
        "safe_refs": safe_refs,
        "private_slice_refs": private_refs,
        "blocker_refs": blocker_refs,
        "created_at": utc_now_iso(),
    }
    handoff_record = put(
        _record(
            artifact_type="gate2_handoff_v0",
            context=context,
            retention_policy=retention_policy,
            document_id=None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            validation_status=validation_status if handoff_payload["handoff_status"] != "blocked" else "blocked",
            payload=handoff_payload,
            safe_metadata={"handoff_status": handoff_payload["handoff_status"]},
            access_policy={**access_policy, "requires_validated_gate1": True},
            warning_codes=_warning_codes(package),
        )
    )
    refs_by_type.setdefault("gate2_handoff_v0", [])
    return Gate1ArtifactManifest(
        normalization_run_id=run_id,
        gate2_handoff_ref=handoff_record.artifact_id,
        safe_refs=safe_refs,
        private_slice_refs=private_refs,
        blocker_refs=blocker_refs,
        artifact_refs_by_type=refs_by_type,
    )


def _record(
    *,
    artifact_type: str,
    context: ArtifactAccessContext,
    retention_policy: RetentionPolicy,
    document_id: str | None,
    source_file_ref: dict[str, Any] | None,
    visibility: str,
    storage_backend: str,
    validation_status: str,
    payload: Any,
    safe_metadata: dict[str, Any],
    access_policy: dict[str, Any],
    warning_codes: list[str] | None = None,
) -> ArtifactRecord:
    lifecycle_status = lifecycle_for_visibility(visibility=visibility, validation_status=validation_status)
    return ArtifactRecord(
        artifact_id=new_artifact_id(),
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
        access_policy=access_policy,
        validation_status=validation_status,
        lifecycle_status=lifecycle_status,
        payload_kind="json_file" if storage_backend == "project_artifact_payload" else "inline_json",
        payload=payload,
        safe_metadata=safe_metadata,
        warning_codes=warning_codes or [],
    )


def _source_refs_for_documents(
    documents: list[dict[str, Any]],
    source_file_refs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    refs = []
    for index, document in enumerate(documents):
        provided = source_file_refs[index] if index < len(source_file_refs) else {}
        refs.append(
            {
                "provider": provided.get("provider") or document.get("source_kind") or "unknown",
                "openwebui_file_id": provided.get("openwebui_file_id"),
                "file_hash_sha256": document.get("sha256") or provided.get("file_hash_sha256"),
                "content_type": document.get("declared_mime_type") or provided.get("content_type"),
                "size_bytes": document.get("size_bytes") or provided.get("size_bytes"),
                "source_deleted": bool(provided.get("source_deleted", False)),
                "source_delete_observed_at": provided.get("source_delete_observed_at"),
            }
        )
    return refs


def _validation_status(package: dict) -> str:
    status = package.get("validation_result", {}).get("status")
    if status == "passed":
        return "validated"
    if status == "privacy_failed":
        return "privacy_failed"
    return "blocked"


def _safe_metadata_for_payload(package: dict, artifact_type: str) -> dict[str, Any]:
    run = package["normalization_run"]
    return {
        "artifact_type": artifact_type,
        "normalizer_version": package["normalizer_version"],
        "run_status": run["run_status"],
        "gate2_handoff_status": run["gate2_handoff_status"],
        "files_total": package["summary_counts"]["files_total"],
    }


def _warning_codes(package: dict) -> list[str]:
    return sorted({str(item.get("code")) for item in package.get("normalization_blockers", []) if item.get("code")})
