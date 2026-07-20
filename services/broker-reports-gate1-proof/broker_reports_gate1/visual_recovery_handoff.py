from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .artifact_lifecycle import lifecycle_for_visibility
from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    RetentionPolicy,
)
from .artifact_resolver import ArtifactResolver
from .artifact_store import SqliteArtifactStoreAdapter, new_artifact_id
from .visual_neutral_tables import validate_visual_neutral_table_result


VISUAL_RECOVERY_MANIFEST_SCHEMA_VERSION = (
    "broker_reports_gate1_visual_recovery_manifest_v1"
)

FACTORY_REQUIRED = (
    "Gate1VisualRecoveryHandoffFactory.create is the only ArtifactStore "
    "persistence entrypoint for visual-neutral table results"
)
FORBIDDEN = (
    "Callers must not inject visual tables into Gate 2 packages, persist an "
    "unvalidated result as canonical, or bypass source-unit lineage checks"
)


class VisualRecoveryHandoffError(RuntimeError):
    def __init__(self, code: str, subject: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.subject = subject


@dataclass(frozen=True)
class Gate1VisualRecoveryArtifactManifest:
    manifest_ref: str
    result_refs: list[str]
    accepted_result_refs: list[str]
    confirmed_empty_result_refs: list[str]
    blocked_result_refs: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_ref": self.manifest_ref,
            "result_refs": list(self.result_refs),
            "accepted_result_refs": list(self.accepted_result_refs),
            "confirmed_empty_result_refs": list(
                self.confirmed_empty_result_refs
            ),
            "blocked_result_refs": list(self.blocked_result_refs),
        }


class Gate1VisualRecoveryHandoffFactory:
    def __init__(self, *, store: SqliteArtifactStoreAdapter) -> None:
        self.store = store

    def create(self) -> "Gate1VisualRecoveryHandoffService":
        return Gate1VisualRecoveryHandoffService(store=self.store)


class Gate1VisualRecoveryHandoffService:
    def __init__(self, *, store: SqliteArtifactStoreAdapter) -> None:
        self.store = store
        self.resolver = ArtifactResolver(store)

    def persist(
        self,
        *,
        results: list[dict[str, Any]],
        context: ArtifactAccessContext,
        retention_policy: RetentionPolicy,
    ) -> Gate1VisualRecoveryArtifactManifest:
        if not context.allow_private:
            raise VisualRecoveryHandoffError("visual_handoff_private_access_required")
        if not results:
            raise VisualRecoveryHandoffError("visual_handoff_results_missing")

        records = self.resolver.catalog_run(context)
        source_records_by_unit: dict[str, list[ArtifactRecord]] = {}
        existing_recovery_ids: set[str] = set()
        for record in records:
            if record.artifact_type == "private_normalized_source_unit_v0":
                unit_ref = str(record.safe_metadata.get("unit_ref") or "")
                if unit_ref:
                    source_records_by_unit.setdefault(unit_ref, []).append(record)
            elif record.artifact_type == "broker_reports_gate1_visual_neutral_table_v1":
                recovery_id = str(record.safe_metadata.get("recovery_id") or "")
                if recovery_id:
                    existing_recovery_ids.add(recovery_id)

        result_refs: list[str] = []
        accepted_refs: list[str] = []
        confirmed_empty_refs: list[str] = []
        blocked_refs: list[str] = []
        manifest_entries: list[dict[str, Any]] = []
        seen_recovery_ids: set[str] = set()

        for result in results:
            errors = validate_visual_neutral_table_result(result)
            if errors:
                raise VisualRecoveryHandoffError(
                    "visual_handoff_result_invalid", errors[0].get("code") or ""
                )
            recovery_id = str(result.get("recovery_id") or "")
            if (
                not recovery_id
                or recovery_id in seen_recovery_ids
                or recovery_id in existing_recovery_ids
            ):
                raise VisualRecoveryHandoffError(
                    "visual_handoff_recovery_identity_not_unique", recovery_id
                )
            seen_recovery_ids.add(recovery_id)

            source_unit_ref = str(result.get("source_unit_ref") or "")
            source_candidates = source_records_by_unit.get(source_unit_ref, [])
            if len(source_candidates) != 1:
                raise VisualRecoveryHandoffError(
                    "visual_handoff_source_unit_lineage_ambiguous", source_unit_ref
                )
            source_record = source_candidates[0]
            if (
                source_record.validation_status != "validated"
                or str(source_record.document_id or "")
                != str(result.get("source_document_ref") or "")
            ):
                raise VisualRecoveryHandoffError(
                    "visual_handoff_source_unit_lineage_invalid", source_unit_ref
                )
            source_payload = self.resolver.resolve(
                source_record.artifact_id, context
            )["payload"]
            if (
                not isinstance(source_payload, dict)
                or source_payload.get("pdf_unit_type") != "pdf_visual_page_unit"
                or source_payload.get("private_media_sha256")
                != result.get("image_sha256")
                or int(source_payload.get("page_number") or 0)
                != int(result.get("page_number") or 0)
            ):
                raise VisualRecoveryHandoffError(
                    "visual_handoff_source_unit_payload_mismatch", source_unit_ref
                )

            accepted = str(result.get("promotion_state") or "").startswith(
                "canonical_table_accepted_"
            )
            confirmed_empty = (
                result.get("promotion_state") == "confirmed_empty_source_scope"
            )
            record = self.store.put_record(
                _record(
                    artifact_type="broker_reports_gate1_visual_neutral_table_v1",
                    context=context,
                    retention_policy=retention_policy,
                    document_id=str(result.get("source_document_ref") or ""),
                    source_file_ref=source_record.source_file_ref,
                    validation_status=(
                        "validated" if accepted or confirmed_empty else "blocked"
                    ),
                    payload=result,
                    safe_metadata={
                        "schema_version": result.get("schema_version"),
                        "recovery_id": recovery_id,
                        "source_unit_ref": source_unit_ref,
                        "promotion_state": result.get("promotion_state"),
                        "integrity_ref": result.get("integrity_ref"),
                        "tables_total": len(result.get("canonical_tables") or []),
                        "cells_total": int(
                            (result.get("source_to_table_accounting") or {}).get(
                                "cells_total"
                            )
                            or 0
                        ),
                        "source_to_table_accounting_passed": bool(
                            (result.get("source_to_table_accounting") or {}).get(
                                "source_to_table_accounting_passed"
                            )
                        ),
                        "model_canonical_authority": False,
                        "knowledge_rag_used": False,
                        "vectorization_performed": False,
                    },
                )
            )
            result_refs.append(record.artifact_id)
            if accepted:
                accepted_refs.append(record.artifact_id)
            elif confirmed_empty:
                confirmed_empty_refs.append(record.artifact_id)
            else:
                blocked_refs.append(record.artifact_id)
            manifest_entries.append(
                {
                    "result_artifact_ref": record.artifact_id,
                    "source_document_ref": result.get("source_document_ref"),
                    "source_unit_ref": source_unit_ref,
                    "recovery_id": recovery_id,
                    "promotion_state": result.get("promotion_state"),
                    "integrity_ref": result.get("integrity_ref"),
                    "accepted_as_gate2_canonical_input": accepted,
                    "confirmed_empty_source_scope": confirmed_empty,
                    "terminally_accounted": accepted or confirmed_empty,
                }
            )

        manifest_payload = {
            "schema_version": VISUAL_RECOVERY_MANIFEST_SCHEMA_VERSION,
            "normalization_run_id": context.normalization_run_id,
            "entries": manifest_entries,
            "results_total": len(result_refs),
            "accepted_results_total": len(accepted_refs),
            "confirmed_empty_results_total": len(confirmed_empty_refs),
            "blocked_results_total": len(blocked_refs),
            "all_results_structurally_valid": True,
            "all_results_accepted": len(accepted_refs) == len(result_refs),
            "all_results_terminally_accounted": not blocked_refs,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
            "model_canonical_authority": False,
        }
        manifest_record = self.store.put_record(
            _record(
                artifact_type=VISUAL_RECOVERY_MANIFEST_SCHEMA_VERSION,
                context=context,
                retention_policy=retention_policy,
                document_id=None,
                source_file_ref=None,
                validation_status="validated",
                payload=manifest_payload,
                safe_metadata={
                    "schema_version": VISUAL_RECOVERY_MANIFEST_SCHEMA_VERSION,
                    "results_total": len(result_refs),
                    "accepted_results_total": len(accepted_refs),
                    "confirmed_empty_results_total": len(confirmed_empty_refs),
                    "blocked_results_total": len(blocked_refs),
                    "all_results_accepted": len(accepted_refs) == len(result_refs),
                    "all_results_terminally_accounted": not blocked_refs,
                    "knowledge_rag_used": False,
                    "vectorization_performed": False,
                    "model_canonical_authority": False,
                },
            )
        )
        return Gate1VisualRecoveryArtifactManifest(
            manifest_ref=manifest_record.artifact_id,
            result_refs=result_refs,
            accepted_result_refs=accepted_refs,
            confirmed_empty_result_refs=confirmed_empty_refs,
            blocked_result_refs=blocked_refs,
        )


def _record(
    *,
    artifact_type: str,
    context: ArtifactAccessContext,
    retention_policy: RetentionPolicy,
    document_id: str | None,
    source_file_ref: dict[str, Any] | None,
    validation_status: str,
    payload: dict[str, Any],
    safe_metadata: dict[str, Any],
) -> ArtifactRecord:
    visibility = "private_case"
    return ArtifactRecord(
        artifact_id=new_artifact_id(),
        artifact_type=artifact_type,
        case_id=context.case_id,
        chat_id=context.chat_id,
        user_id=context.user_id,
        workspace_model_id=context.workspace_model_id,
        normalization_run_id=context.normalization_run_id,
        document_id=document_id,
        source_file_ref=copy.deepcopy(source_file_ref),
        visibility=visibility,
        storage_backend="project_artifact_payload",
        retention_policy=retention_policy,
        access_policy={
            "requires_user_id": True,
            "requires_case_or_chat": True,
            "requires_workspace_model_id_when_present": bool(
                context.workspace_model_id
            ),
            "requires_gate2_resolver": True,
        },
        validation_status=validation_status,
        lifecycle_status=lifecycle_for_visibility(
            visibility=visibility,
            validation_status=validation_status,
        ),
        payload_kind="json_file",
        payload=copy.deepcopy(payload),
        safe_metadata=copy.deepcopy(safe_metadata),
    )
