from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from .artifact_models import (
    PRIVATE_BINARY_ARTIFACT_SCHEMA_VERSION,
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
    ArtifactStorePort,
    decode_private_binary_payload,
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

    def resolve_private_binary(
        self,
        artifact_id: str,
        context: ArtifactAccessContext,
        *,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        """Resolve one ACL-checked private binary envelope and verify its inner seal."""

        resolved = self.resolve(artifact_id, context)
        record = resolved["record"]
        if (
            record.artifact_type != PRIVATE_BINARY_ARTIFACT_SCHEMA_VERSION
            or record.visibility != "private_case"
            or record.storage_backend != "project_artifact_payload"
        ):
            raise ArtifactStoreError(
                "artifact_binary_payload_invalid",
                "Artifact is not a private binary envelope",
            )
        content, media_type, content_sha256 = decode_private_binary_payload(
            resolved["payload"]
        )
        if expected_sha256 is not None and expected_sha256 != content_sha256:
            raise ArtifactStoreError(
                "artifact_binary_checksum_mismatch",
                "Private binary content does not match the expected checksum",
            )
        return {
            "record": record,
            "content": content,
            "media_type": media_type,
            "content_sha256": content_sha256,
        }

    def resolve_case(
        self, artifact_id: str, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        """Resolve an immutable case artifact across runs in the same ACL scope."""

        record = self.store.get_record_unchecked(artifact_id)
        if record is None:
            raise ArtifactStoreError("artifact_not_found", "Artifact ref was not found")
        self._validate_case_scope(record, context)
        self._validate_lifecycle(record, context)
        return {
            "record": record,
            "payload": self.store.read_payload(record),
        }

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

    def catalog_case(self, context: ArtifactAccessContext) -> list[ArtifactRecord]:
        """Return access-checked metadata across runs in one authenticated case."""

        if not context.case_id:
            raise ArtifactStoreError(
                "artifact_scope_unverified", "Artifact case context is required"
            )
        records = self.store.list_by_case_context(context)
        result: list[ArtifactRecord] = []
        for record in records:
            if record.case_id != context.case_id:
                continue
            if record.user_id != context.user_id:
                continue
            if (
                record.workspace_model_id
                and record.workspace_model_id != context.workspace_model_id
            ):
                continue
            if record.visibility in PRIVATE_VISIBILITIES and not context.allow_private:
                raise ArtifactStoreError(
                    "artifact_access_denied",
                    "Private case catalog access was not requested",
                )
            item = copy.deepcopy(record)
            item.payload = None
            item.payload_ref = None
            result.append(item)
        return result

    def _validate(self, record: ArtifactRecord, context: ArtifactAccessContext) -> None:
        self._validate_scope(record, context)
        self._validate_lifecycle(record, context)

    @staticmethod
    def _validate_lifecycle(
        record: ArtifactRecord, context: ArtifactAccessContext
    ) -> None:
        if record.visibility in PRIVATE_VISIBILITIES and not context.allow_private:
            raise ArtifactStoreError("artifact_access_denied", "Private artifact access was not requested")
        if record.lifecycle_status == "privacy_failed" or record.validation_status == "privacy_failed":
            raise ArtifactStoreError("artifact_privacy_failed", "Artifact failed privacy validation")
        if record.lifecycle_status == "blocked" or record.validation_status == "blocked":
            raise ArtifactStoreError("artifact_blocked", "Artifact is blocked")
        if record.lifecycle_status == "purged" or record.purge_status == "purged":
            raise ArtifactStoreError("artifact_purged", "Artifact was purged")
        if (
            record.lifecycle_status == "purge_pending"
            or record.purge_status == "purge_pending"
        ):
            raise ArtifactStoreError(
                "artifact_purge_pending",
                "Artifact purge is pending",
            )
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

    @staticmethod
    def _validate_case_scope(
        record: ArtifactRecord, context: ArtifactAccessContext
    ) -> None:
        if not isinstance(context, ArtifactAccessContext) or not context.case_id:
            raise ArtifactStoreError(
                "artifact_scope_unverified", "Artifact case context is required"
            )
        if record.user_id != context.user_id:
            raise ArtifactStoreError(
                "artifact_access_denied", "Artifact user context mismatch"
            )
        if not record.case_id:
            raise ArtifactStoreError(
                "artifact_scope_unverified", "Artifact has no case scope"
            )
        if record.case_id != context.case_id:
            raise ArtifactStoreError(
                "artifact_access_denied", "Artifact case context mismatch"
            )
        if record.workspace_model_id:
            if not context.workspace_model_id:
                raise ArtifactStoreError(
                    "artifact_scope_unverified",
                    "Artifact workspace context is missing",
                )
            if record.workspace_model_id != context.workspace_model_id:
                raise ArtifactStoreError(
                    "artifact_access_denied",
                    "Artifact workspace context mismatch",
                )

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
