"""Issue a closed Goal #391 R&D selection from one authenticated scope.

This coordinator has no catalogue, persistence or product route.  It binds a
caller-named document to the store's single active Canonical pointer and to
the source record in the same normalization run.  Finalized Canonicals use a
different run by design and are rejected rather than silently mixing runs.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable

from .artifact_models import ArtifactAccessContext
from .goal391_private_corpus_export import (
    Goal391PrivateCorpusExportError,
    PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION,
    PrivateCorpusSelection,
    PrivateCorpusSelectionManifest,
    parse_private_corpus_selection,
)


class Goal391PrivateSelectionBindingError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Goal391PrivateSelectionRequest:
    slot_id: str
    document_id: str
    context: ArtifactAccessContext


class Goal391PrivateSelectionBindingIssuer:
    """Return existing selection data only after exact owner-backed binding."""

    def __init__(self, *, store: Any, reader: Any, resolver: Any) -> None:
        if not callable(getattr(store, "get_active_canonical_version", None)):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_store_required"
            )
        if not callable(getattr(reader, "read_envelope", None)):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_reader_required"
            )
        if not callable(getattr(resolver, "resolve_record", None)):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_resolver_required"
            )
        self._store = store
        self._reader = reader
        self._resolver = resolver

    def issue(
        self,
        *,
        corpus_id: str,
        requests: Iterable[Goal391PrivateSelectionRequest],
    ) -> PrivateCorpusSelectionManifest:
        requests = list(requests)
        if not requests or any(
            not isinstance(request, Goal391PrivateSelectionRequest)
            for request in requests
        ):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_request_invalid"
            )
        self._validate_request_shape(corpus_id=corpus_id, requests=requests)
        selections = tuple(self._issue_one(request) for request in requests)
        return self._parse_manifest(corpus_id=corpus_id, selections=selections)

    def _issue_one(
        self, request: Goal391PrivateSelectionRequest
    ) -> PrivateCorpusSelection:
        context = request.context
        if not _private_context(context) or not str(request.document_id or "").strip():
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_request_invalid"
            )
        source_context = replace(context, require_source_available=True)
        version = self._store.get_active_canonical_version(
            context=source_context, document_id=request.document_id
        )
        manifest_ref = str(getattr(version, "manifest_ref", "") or "")
        version_run_id = str(getattr(version, "normalization_run_id", "") or "")
        if (
            getattr(version, "document_id", None) != request.document_id
            or not manifest_ref
            or not version_run_id
            or version_run_id != context.normalization_run_id
        ):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_cross_run_unsupported"
            )
        envelope = self._reader.read_envelope(
            manifest_ref,
            source_context,
            expected_normalization_run_id=version_run_id,
        )
        source = (
            getattr(envelope, "artifact", {}).get("source")
            if isinstance(getattr(envelope, "artifact", None), dict)
            else None
        )
        source_ref = str(source.get("source_artifact_ref") or "") if isinstance(source, dict) else ""
        source_sha256 = str(source.get("source_sha256") or "") if isinstance(source, dict) else ""
        if (
            getattr(envelope, "document_id", None) != request.document_id
            or getattr(envelope, "canonical_version_id", None)
            != getattr(version, "canonical_version_id", None)
            or getattr(envelope, "canonical_root_sha256", None)
            != getattr(version, "canonical_root_sha256", None)
            or source_ref != str(getattr(version, "source_artifact_ref", "") or "")
            or source_sha256 != str(getattr(version, "source_sha256", "") or "")
        ):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_canonical_invalid"
            )
        record = self._resolver.resolve_record(
            source_ref, source_context
        )
        source_file_ref = getattr(record, "source_file_ref", None)
        if (
            getattr(record, "artifact_type", None) != "source_file_ref_v0"
            or getattr(record, "document_id", None) != request.document_id
            or getattr(record, "normalization_run_id", None) != version_run_id
            or not isinstance(source_file_ref, dict)
            or source_file_ref.get("source_deleted") is True
            or str(source_file_ref.get("file_hash_sha256") or "") != source_sha256
        ):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_source_invalid"
            )
        return PrivateCorpusSelection(
            slot_id=request.slot_id,
            manifest_ref=manifest_ref,
            user_id=context.user_id,
            normalization_run_id=version_run_id,
            case_id=context.case_id,
            chat_id=None if context.case_id else context.chat_id,
            workspace_model_id=context.workspace_model_id,
        )

    @staticmethod
    def _validate_request_shape(
        *, corpus_id: str, requests: list[Goal391PrivateSelectionRequest]
    ) -> None:
        # Canonical references do not exist until the owner resolves each
        # request. Give the schema validator unique synthetic references so
        # its real duplicate check remains meaningful for a request batch.
        raw = {
            "schema_version": PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION,
            "corpus_id": corpus_id,
            "selections": [
                {
                    "slot_id": request.slot_id,
                    "manifest_ref": f"pending-{index}",
                    "user_id": request.context.user_id
                    if isinstance(request.context, ArtifactAccessContext)
                    else "",
                    "normalization_run_id": "pending",
                    "case_id": request.context.case_id
                    if isinstance(request.context, ArtifactAccessContext)
                    else None,
                    "chat_id": None
                    if isinstance(request.context, ArtifactAccessContext)
                    and request.context.case_id
                    else (
                        request.context.chat_id
                        if isinstance(request.context, ArtifactAccessContext)
                        else None
                    ),
                    "workspace_model_id": request.context.workspace_model_id
                    if isinstance(request.context, ArtifactAccessContext)
                    else None,
                }
                for index, request in enumerate(requests, start=1)
            ],
        }
        try:
            parse_private_corpus_selection(raw)
        except Goal391PrivateCorpusExportError as exc:
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_request_invalid"
            ) from exc

    @staticmethod
    def _parse_manifest(
        *, corpus_id: str, selections: tuple[PrivateCorpusSelection, ...]
    ) -> PrivateCorpusSelectionManifest:
        try:
            return parse_private_corpus_selection(
                {
                    "schema_version": PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION,
                    "corpus_id": corpus_id,
                    "selections": [
                        {
                            "slot_id": selection.slot_id,
                            "manifest_ref": selection.manifest_ref,
                            "user_id": selection.user_id,
                            "normalization_run_id": selection.normalization_run_id,
                            "case_id": selection.case_id,
                            "chat_id": selection.chat_id,
                            "workspace_model_id": selection.workspace_model_id,
                        }
                        for selection in selections
                    ],
                }
            )
        except Goal391PrivateCorpusExportError as exc:
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_invalid"
            ) from exc


def _private_context(context: Any) -> bool:
    return (
        isinstance(context, ArtifactAccessContext)
        and bool(context.allow_private)
        and bool(str(context.user_id or "").strip())
        and bool(str(context.normalization_run_id or "").strip())
        and bool(context.case_id or context.chat_id)
    )


__all__ = [
    "Goal391PrivateSelectionBindingError",
    "Goal391PrivateSelectionBindingIssuer",
    "Goal391PrivateSelectionRequest",
]
