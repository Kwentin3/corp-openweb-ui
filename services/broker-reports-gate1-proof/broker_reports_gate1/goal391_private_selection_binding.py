"""Issue a closed Goal #391 R&D selection from one authenticated scope.

This coordinator has no catalogue, persistence or product route.  It offers
two deliberately narrow selection modes:

* an already named document may use the store's active Canonical pointer;
* an already authenticated OpenWebUI source file may resolve the exact
  document/run/source binding, then one Canonical from that same run.

The second mode exists for source-review R&D: a later active Canonical is not
silently substituted for the Canonical that produced the reviewed Full
Source.  Neither mode discovers documents outside the caller's authenticated
scope.
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


@dataclass(frozen=True)
class Goal391PrivateSourceFileSelectionRequest:
    """Name one source file inside an already server-attested scope.

    ``context.normalization_run_id`` is deliberately not used as authority by
    this request.  The resolver derives the run from the authenticated source
    record before any Canonical is selected.
    """

    slot_id: str
    openwebui_file_id: str
    context: ArtifactAccessContext


class Goal391PrivateSelectionBindingIssuer:
    """Return existing selection data only after exact owner-backed binding."""

    def __init__(self, *, store: Any, reader: Any, resolver: Any) -> None:
        if not callable(getattr(store, "get_active_canonical_version", None)):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_store_required"
            )
        if not callable(getattr(store, "list_canonical_versions", None)):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_store_required"
            )
        if not callable(getattr(reader, "read_envelope", None)):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_reader_required"
            )
        if (
            not callable(getattr(resolver, "resolve_record", None))
            or not callable(
                getattr(resolver, "resolve_authenticated_source_file_binding", None)
            )
        ):
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

    def issue_from_source_files(
        self,
        *,
        corpus_id: str,
        requests: Iterable[Goal391PrivateSourceFileSelectionRequest],
    ) -> PrivateCorpusSelectionManifest:
        """Issue one selection per exact authenticated source-file binding.

        This is a representation-only bridge.  ArtifactResolver owns
        source-file identity and lifecycle validation; ArtifactStore owns
        Canonical history; CanonicalReader owns immutable envelope validation.
        """

        requests = list(requests)
        if not requests or any(
            not isinstance(request, Goal391PrivateSourceFileSelectionRequest)
            for request in requests
        ):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_request_invalid"
            )
        self._validate_source_file_request_shape(corpus_id=corpus_id, requests=requests)
        selections = tuple(self._issue_one_source_file(request) for request in requests)
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

    def _issue_one_source_file(
        self, request: Goal391PrivateSourceFileSelectionRequest
    ) -> PrivateCorpusSelection:
        scope_context = request.context
        if not _private_scope_context(scope_context):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_request_invalid"
            )
        binding = self._resolver.resolve_authenticated_source_file_binding(
            context=replace(scope_context, require_source_available=True),
            openwebui_file_id=request.openwebui_file_id,
        )
        exact_context = replace(
            scope_context,
            normalization_run_id=binding.normalization_run_id,
            require_source_available=True,
            source_file_id=request.openwebui_file_id,
        )
        matches = [
            version
            for version in self._store.list_canonical_versions(
                context=exact_context, document_id=binding.document_id
            )
            if getattr(version, "normalization_run_id", None)
            == binding.normalization_run_id
            and getattr(version, "source_artifact_ref", None)
            == binding.source_artifact_id
            and getattr(version, "source_sha256", None) == binding.file_hash_sha256
            and bool(str(getattr(version, "manifest_ref", "") or ""))
        ]
        if len(matches) != 1:
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_exact_canonical_ambiguous"
                if len(matches) > 1
                else "goal391_selection_binding_exact_canonical_missing"
            )
        version = matches[0]
        manifest_ref = str(getattr(version, "manifest_ref", "") or "")
        envelope = self._reader.read_envelope(
            manifest_ref,
            exact_context,
            expected_normalization_run_id=binding.normalization_run_id,
        )
        source = (
            getattr(envelope, "artifact", {}).get("source")
            if isinstance(getattr(envelope, "artifact", None), dict)
            else None
        )
        if (
            getattr(envelope, "document_id", None) != binding.document_id
            or getattr(envelope, "canonical_version_id", None)
            != getattr(version, "canonical_version_id", None)
            or getattr(envelope, "canonical_root_sha256", None)
            != getattr(version, "canonical_root_sha256", None)
            or not isinstance(source, dict)
            or str(source.get("source_artifact_ref") or "")
            != binding.source_artifact_id
            or str(source.get("source_sha256") or "") != binding.file_hash_sha256
        ):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_canonical_invalid"
            )
        return PrivateCorpusSelection(
            slot_id=request.slot_id,
            manifest_ref=manifest_ref,
            user_id=scope_context.user_id,
            normalization_run_id=binding.normalization_run_id,
            case_id=scope_context.case_id,
            chat_id=None if scope_context.case_id else scope_context.chat_id,
            workspace_model_id=scope_context.workspace_model_id,
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
    def _validate_source_file_request_shape(
        *,
        corpus_id: str,
        requests: list[Goal391PrivateSourceFileSelectionRequest],
    ) -> None:
        if any(
            not _private_scope_context(request.context)
            or not str(request.openwebui_file_id or "").strip()
            for request in requests
        ):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_request_invalid"
            )
        if len({str(request.openwebui_file_id) for request in requests}) != len(requests):
            raise Goal391PrivateSelectionBindingError(
                "goal391_selection_binding_request_invalid"
            )
        Goal391PrivateSelectionBindingIssuer._validate_request_shape(
            corpus_id=corpus_id,
            requests=[
                Goal391PrivateSelectionRequest(
                    slot_id=request.slot_id,
                    document_id="source-file-selection",
                    context=replace(request.context, normalization_run_id="pending"),
                )
                for request in requests
            ],
        )

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


def _private_scope_context(context: Any) -> bool:
    return (
        isinstance(context, ArtifactAccessContext)
        and bool(context.allow_private)
        and bool(str(context.user_id or "").strip())
        and bool(context.case_id or context.chat_id)
    )


__all__ = [
    "Goal391PrivateSelectionBindingError",
    "Goal391PrivateSelectionBindingIssuer",
    "Goal391PrivateSelectionRequest",
    "Goal391PrivateSourceFileSelectionRequest",
]
