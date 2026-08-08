"""G3.6 deterministic NDFL case readiness derived from existing artifacts."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStoreError
from .artifact_resolver import ArtifactResolver
from .gate3_financial_annotations_persistence import (
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
    Gate3FinancialAnnotationsPersistenceError,
    Gate3FinancialAnnotationsPersistenceFactory,
)


GATE3_NDFL_CASE_READINESS_SCHEMA_VERSION = (
    "broker_reports_gate3_ndfl_case_readiness_v1"
)
WORKFLOW_ID = "NDFL"
FACTORY_REQUIRED = (
    "Gate3NdflCaseReadinessFactory.create is the only G3.6 case-readiness "
    "entrypoint; it must derive state through ArtifactResolver and existing "
    "canonical/FinancialAnnotations records"
)
FORBIDDEN = (
    "G3.6 must not persist workflow state, accept caller tenant/case ids, "
    "combine documents for labeling, call an LLM, infer financial meaning, "
    "create a database or implement Gate 4"
)

_ACTION_IDS = (
    "ADD_DOCUMENT",
    "PROCESS_REMAINING_DOCUMENT",
    "SHOW_FINANCIAL_FACTS",
    "VIEW_DICTIONARY",
    "PROPOSE_DICTIONARY_CHANGE",
    "PREPARE_DECLARATION",
)


class Gate3NdflCaseReadinessError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Gate3NdflCaseReadinessFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._resolver = ArtifactResolver(store)

    def create(self, *, context: ArtifactAccessContext) -> dict[str, Any]:
        if not context.case_id:
            raise Gate3NdflCaseReadinessError(
                "gate3_ndfl_case_scope_required"
            )
        if not context.allow_private:
            raise ArtifactStoreError(
                "artifact_access_denied",
                "NDFL readiness requires authenticated private case access",
            )
        records = self._resolver.catalog_case(context)
        document_ids = sorted(
            {
                record.document_id
                for record in records
                if isinstance(record.document_id, str) and record.document_id
            }
        )
        annotation_records = [
            record
            for record in records
            if record.artifact_type
            == GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
        ]
        documents = [
            self._document_state(
                document_id=document_id,
                context=context,
                annotation_records=annotation_records,
            )
            for document_id in document_ids
        ]
        documents_total = len(documents)
        gate2_ready = sum(item["gate2_ready"] for item in documents)
        gate3_ready = sum(item["gate3_ready"] for item in documents)
        handoff_ready = documents_total > 0 and gate3_ready == documents_total
        if documents_total == 0:
            case_status = "empty"
        elif gate2_ready != documents_total:
            case_status = "gate2_incomplete"
        elif not handoff_ready:
            case_status = "gate3_incomplete"
        else:
            case_status = "ready_for_gate4_handoff"
        snapshot = {
            "schema_version": GATE3_NDFL_CASE_READINESS_SCHEMA_VERSION,
            "workflow_id": WORKFLOW_ID,
            "case_status": case_status,
            "state_source": "derived_from_existing_artifacts",
            "state_persisted": False,
            "summary": {
                "documents_total": documents_total,
                "gate2_ready_documents": gate2_ready,
                "gate3_ready_documents": gate3_ready,
                "gate4_handoff_ready": handoff_ready,
            },
            "documents": documents,
            "follow_up_actions": _actions(
                documents_total=documents_total,
                gate3_ready=gate3_ready,
                handoff_ready=handoff_ready,
            ),
        }
        _validate_snapshot(snapshot)
        return snapshot

    def _document_state(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        annotation_records: list[Any],
    ) -> dict[str, Any]:
        active_version = None
        try:
            active_version = self._store.get_active_canonical_version(
                context=context,
                document_id=document_id,
            )
        except ArtifactStoreError as exc:
            if exc.code not in {
                "artifact_not_found",
                "canonical_version_not_active",
            }:
                raise
        candidates = [
            record
            for record in annotation_records
            if record.document_id == document_id
        ]
        current: list[tuple[Any, dict[str, Any]]] = []
        stale = 0
        incomplete = 0
        persistence = Gate3FinancialAnnotationsPersistenceFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        for record in candidates:
            if (
                record.validation_status != "validated"
                or record.lifecycle_status
                in {"blocked", "expired", "purge_pending", "purged", "privacy_failed"}
                or record.purge_status
                in {"blocked", "expired", "purge_pending", "purged"}
            ):
                incomplete += 1
                continue
            record_context = replace(
                context,
                normalization_run_id=record.normalization_run_id,
            )
            try:
                payload = persistence.read(
                    artifact_id=record.artifact_id,
                    context=record_context,
                )
            except (
                ArtifactStoreError,
                Gate3FinancialAnnotationsPersistenceError,
            ):
                incomplete += 1
                continue
            if (
                active_version is not None
                and payload["canonical_binding"]["canonical_version_id"]
                == active_version.canonical_version_id
            ):
                current.append((record, payload))
            else:
                stale += 1
        current.sort(key=lambda item: (item[0].created_at, item[0].artifact_id))
        selected_record, selected_payload = (
            current[-1] if current else (None, None)
        )
        gate2_ready = active_version is not None
        gate3_ready = selected_payload is not None
        reasons: list[str] = []
        if not gate2_ready:
            reasons.append("GATE2_CANONICAL_MISSING")
        elif not gate3_ready:
            reasons.append("GATE3_ANNOTATIONS_MISSING")
        if stale:
            reasons.append("GATE3_ANNOTATIONS_STALE")
        if incomplete:
            reasons.append("GATE3_ANNOTATIONS_INCOMPLETE")
        return {
            "document_id": document_id,
            "gate2_ready": gate2_ready,
            "gate3_ready": gate3_ready,
            "current_canonical_version_id": (
                active_version.canonical_version_id
                if active_version is not None
                else None
            ),
            "selected_annotations_artifact_id": (
                selected_record.artifact_id
                if selected_record is not None
                else None
            ),
            "selected_dictionary_version": (
                selected_payload["dictionary_identity"]["semantic_version"]
                if selected_payload is not None
                else None
            ),
            "annotations_total": (
                len(selected_payload["annotations"])
                if selected_payload is not None
                else 0
            ),
            "annotation_candidates_total": len(candidates),
            "stale_annotation_candidates_total": stale,
            "incomplete_annotation_candidates_total": incomplete,
            "reason_codes": reasons,
        }


def _actions(
    *,
    documents_total: int,
    gate3_ready: int,
    handoff_ready: bool,
) -> list[dict[str, Any]]:
    rules = {
        "ADD_DOCUMENT": (True, "ALLOWED"),
        "PROCESS_REMAINING_DOCUMENT": (
            documents_total > gate3_ready,
            "ALLOWED"
            if documents_total > gate3_ready
            else "NO_REMAINING_DOCUMENTS",
        ),
        "SHOW_FINANCIAL_FACTS": (
            gate3_ready > 0,
            "ALLOWED" if gate3_ready > 0 else "NO_READY_ANNOTATIONS",
        ),
        "VIEW_DICTIONARY": (True, "ALLOWED"),
        "PROPOSE_DICTIONARY_CHANGE": (True, "ALLOWED"),
        "PREPARE_DECLARATION": (
            handoff_ready,
            "ALLOWED" if handoff_ready else "GATE3_CASE_NOT_READY",
        ),
    }
    return [
        {
            "action_id": action_id,
            "allowed": rules[action_id][0],
            "reason_code": rules[action_id][1],
        }
        for action_id in _ACTION_IDS
    ]


def _validate_snapshot(value: dict[str, Any]) -> None:
    if (
        set(value)
        != {
            "schema_version",
            "workflow_id",
            "case_status",
            "state_source",
            "state_persisted",
            "summary",
            "documents",
            "follow_up_actions",
        }
        or value["schema_version"]
        != GATE3_NDFL_CASE_READINESS_SCHEMA_VERSION
        or value["workflow_id"] != WORKFLOW_ID
        or value["state_source"] != "derived_from_existing_artifacts"
        or value["state_persisted"] is not False
        or [item["action_id"] for item in value["follow_up_actions"]]
        != list(_ACTION_IDS)
        or value["summary"]["documents_total"] != len(value["documents"])
        or value["summary"]["gate2_ready_documents"]
        != sum(item["gate2_ready"] for item in value["documents"])
        or value["summary"]["gate3_ready_documents"]
        != sum(item["gate3_ready"] for item in value["documents"])
    ):
        raise Gate3NdflCaseReadinessError(
            "gate3_ndfl_case_state_invalid"
        )
    declaration = next(
        item
        for item in value["follow_up_actions"]
        if item["action_id"] == "PREPARE_DECLARATION"
    )
    if declaration["allowed"] is not value["summary"]["gate4_handoff_ready"]:
        raise Gate3NdflCaseReadinessError(
            "gate3_ndfl_gate4_action_not_fail_closed"
        )


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_NDFL_CASE_READINESS_SCHEMA_VERSION",
    "Gate3NdflCaseReadinessError",
    "Gate3NdflCaseReadinessFactory",
    "WORKFLOW_ID",
]
