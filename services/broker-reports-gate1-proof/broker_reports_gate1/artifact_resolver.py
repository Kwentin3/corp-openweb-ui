from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .artifact_models import (
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
    ArtifactStorePort,
)


PRIVATE_VISIBILITIES = {"private_case"}


class ArtifactResolver:
    def __init__(self, store: ArtifactStorePort) -> None:
        self.store = store

    def resolve(self, artifact_id: str, context: ArtifactAccessContext) -> dict[str, Any]:
        record = self.store.get_record_unchecked(artifact_id)
        if record is None:
            raise ArtifactStoreError("artifact_not_found", "Artifact ref was not found")
        self._validate(record, context)
        return {
            "record": record,
            "payload": self.store.read_payload(record),
        }

    def resolve_record(
        self, artifact_id: str, context: ArtifactAccessContext
    ) -> ArtifactRecord:
        """Resolve one record through access/lifecycle checks without exposing payload."""

        record = self.store.get_record_unchecked(artifact_id)
        if record is None:
            raise ArtifactStoreError("artifact_not_found", "Artifact ref was not found")
        self._validate(record, context)
        result = copy.deepcopy(record)
        result.payload = None
        result.payload_ref = None
        return result

    def catalog_run(self, context: ArtifactAccessContext) -> list[ArtifactRecord]:
        """Return same-scope record metadata; payload access still requires resolve()."""

        result: list[ArtifactRecord] = []
        for record in self.store.list_by_run(context.normalization_run_id):
            if not _record_matches_context_scope(record, context):
                continue
            self._validate_scope(record, context)
            item = copy.deepcopy(record)
            item.payload = None
            item.payload_ref = None
            result.append(item)
        return result

    def _validate(self, record: ArtifactRecord, context: ArtifactAccessContext) -> None:
        self._validate_scope(record, context)
        if record.visibility in PRIVATE_VISIBILITIES and not context.allow_private:
            raise ArtifactStoreError("artifact_access_denied", "Private artifact access was not requested")
        if record.lifecycle_status == "privacy_failed" or record.validation_status == "privacy_failed":
            raise ArtifactStoreError("artifact_privacy_failed", "Artifact failed privacy validation")
        if record.lifecycle_status == "blocked" or record.validation_status == "blocked":
            raise ArtifactStoreError("artifact_blocked", "Artifact is blocked")
        if record.lifecycle_status == "purged" or record.purge_status == "purged":
            raise ArtifactStoreError("artifact_purged", "Artifact was purged")
        if record.lifecycle_status == "expired" or record.purge_status == "expired":
            raise ArtifactStoreError("artifact_expired", "Artifact is expired")
        if record.expires_at:
            try:
                expires_at = datetime.fromisoformat(record.expires_at)
            except ValueError as exc:
                raise ArtifactStoreError("artifact_payload_unavailable", "Artifact expiry is invalid") from exc
            if expires_at <= datetime.now(timezone.utc):
                raise ArtifactStoreError("artifact_expired", "Artifact is expired")
        if record.validation_status != "validated":
            raise ArtifactStoreError("artifact_blocked", "Artifact is not validated")
        if context.require_source_available:
            source_ref = record.source_file_ref or {}
            if source_ref.get("source_deleted") is True:
                raise ArtifactStoreError("source_file_unavailable", "Source file was deleted")

    def _validate_scope(
        self, record: ArtifactRecord, context: ArtifactAccessContext
    ) -> None:
        if record.user_id != context.user_id:
            raise ArtifactStoreError("artifact_access_denied", "Artifact user context mismatch")
        if record.normalization_run_id != context.normalization_run_id:
            raise ArtifactStoreError("artifact_access_denied", "Artifact run context mismatch")
        if record.case_id:
            if not context.case_id:
                raise ArtifactStoreError("artifact_scope_unverified", "Artifact case context is missing")
            if record.case_id != context.case_id:
                raise ArtifactStoreError("artifact_access_denied", "Artifact case context mismatch")
        elif record.chat_id:
            if not context.chat_id:
                raise ArtifactStoreError("artifact_scope_unverified", "Artifact chat context is missing")
            if record.chat_id != context.chat_id:
                raise ArtifactStoreError("artifact_access_denied", "Artifact chat context mismatch")
        else:
            raise ArtifactStoreError("artifact_scope_unverified", "Artifact has no case/chat scope")
        if record.workspace_model_id:
            if not context.workspace_model_id:
                raise ArtifactStoreError("artifact_scope_unverified", "Artifact workspace context is missing")
            if record.workspace_model_id != context.workspace_model_id:
                raise ArtifactStoreError("artifact_access_denied", "Artifact workspace context mismatch")


def _record_matches_context_scope(
    record: ArtifactRecord, context: ArtifactAccessContext
) -> bool:
    if record.user_id != context.user_id:
        return False
    if record.normalization_run_id != context.normalization_run_id:
        return False
    if record.case_id:
        if record.case_id != context.case_id:
            return False
    elif record.chat_id != context.chat_id:
        return False
    if record.workspace_model_id and record.workspace_model_id != context.workspace_model_id:
        return False
    return True
