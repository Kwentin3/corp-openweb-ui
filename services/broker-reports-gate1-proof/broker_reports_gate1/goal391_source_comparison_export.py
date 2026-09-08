"""Private, read-only source/Full Source/Canonical packs for Goal #391 R&D.

This module is deliberately not a product route.  It composes existing public
owners for an already selected Canonical manifest and writes an owner-local
laboratory pack.  It has no discovery outside the selected run, no provider
transport, and no ArtifactStore or Canonical write capability.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .contracts import stable_digest
from .full_source import SOURCE_PAYLOAD_SCHEMA_VERSION, validate_full_source_unit
from .goal391_private_corpus_export import (
    Goal391PrivateCorpusExportError,
    PrivateCorpusSelection,
    PrivateCorpusSelectionManifest,
    PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION,
    parse_private_corpus_selection,
)


SOURCE_COMPARISON_RECEIPT_SCHEMA_VERSION = "goal391_source_comparison_receipt_v1"
_FULL_SOURCE_TYPES = {
    "private_normalized_source_payload_v0",
    "private_normalized_source_unit_v0",
}


class Goal391SourceComparisonExportError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Goal391SourceComparisonMappingScope:
    """The already-approved mapping surface for one private comparison slot.

    This is a laboratory input, not a semantic decision: table IDs and prior
    user understandings are passed unchanged to the existing projection owner.
    """

    slot_id: str
    target_table_node_ids: tuple[str, ...]
    confirmed_understandings: tuple[dict[str, Any], ...] = ()


class Goal391SourceComparisonExportCoordinator:
    """Export an explicit, source-bound private R&D comparison pack.

    ``reader``, ``artifact_resolver`` and ``file_bytes_resolver`` must be
    constructed by the server composition root from their existing public
    factories.  This coordinator intentionally accepts no store, SQL path,
    filesystem source path, provider, or caller-supplied artifact reference.
    """

    def __init__(
        self,
        *,
        reader: Any,
        artifact_resolver: Any,
        file_bytes_resolver: Any,
        mapping_package_builder: Any,
        private_corpus_root: str | Path,
    ) -> None:
        if not callable(getattr(reader, "read_envelope", None)):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_reader_required")
        if (
            not callable(getattr(artifact_resolver, "resolve", None))
            or not callable(getattr(artifact_resolver, "resolve_record", None))
            or not callable(getattr(artifact_resolver, "catalog_run", None)
            )
        ):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_resolver_required")
        if not callable(getattr(file_bytes_resolver, "resolve", None)):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_file_resolver_required")
        if not callable(getattr(mapping_package_builder, "build_mapping_package", None)):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_mapping_owner_required")
        self._reader = reader
        self._resolver = artifact_resolver
        self._file_bytes_resolver = file_bytes_resolver
        self._mapping_package_builder = mapping_package_builder
        self._root = _private_root(private_corpus_root)
        self._root_identity = _path_identity(self._root)

    async def export(
        self,
        *,
        selection: PrivateCorpusSelectionManifest,
        mapping_scopes: Iterable[Goal391SourceComparisonMappingScope],
    ) -> dict[str, Any]:
        if not isinstance(selection, PrivateCorpusSelectionManifest):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_selection_required")
        if _path_identity(self._root) != self._root_identity:
            raise Goal391SourceComparisonExportError("goal391_source_comparison_root_changed")

        selection = _validated_selection(selection)
        scopes = _mapping_scopes_by_slot(selection, mapping_scopes)
        # Read and bind every private value before opening a target directory.
        # Thus no partial corpus is left by an ACL, checksum or ownership error.
        entries = [
            await self._collect(item, mapping_scope=scopes[item.slot_id])
            for item in selection.selections
        ]
        target, marker, token = _reserve_target(
            self._root, f"{selection.corpus_id}-source-comparison"
        )
        try:
            _write_pack(target, entries)
            receipt = _safe_receipt(entries)
            _write_json(target / "export_receipt.safe.json", receipt)
        except Exception:
            _remove_reserved_target(target, marker, token)
            raise
        return receipt

    async def _collect(
        self,
        item: PrivateCorpusSelection,
        *,
        mapping_scope: Goal391SourceComparisonMappingScope,
    ) -> dict[str, Any]:
        context = item.access_context(require_source_available=True)
        envelope = self._reader.read_envelope(
            item.manifest_ref,
            context,
            expected_normalization_run_id=item.normalization_run_id,
        )
        artifact = getattr(envelope, "artifact", None)
        source = artifact.get("source") if isinstance(artifact, Mapping) else None
        if (
            not isinstance(source, Mapping)
            or artifact.get("tenant_id") != item.user_id
            or getattr(envelope, "document_id", None) is None
        ):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_canonical_binding_invalid")
        source_artifact_ref = str(source.get("source_artifact_ref") or "")
        source_sha256 = str(source.get("source_sha256") or "")
        document_id = str(getattr(envelope, "document_id") or "")
        if not source_artifact_ref or not _sha256_text(source_sha256) or not document_id:
            raise Goal391SourceComparisonExportError("goal391_source_comparison_canonical_binding_invalid")

        source_record = self._resolver.resolve_record(source_artifact_ref, context)
        source_ref = getattr(source_record, "source_file_ref", None)
        if (
            getattr(source_record, "artifact_type", None) != "source_file_ref_v0"
            or getattr(source_record, "document_id", None) != document_id
            or not isinstance(source_ref, Mapping)
            or source_ref.get("source_deleted") is True
        ):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_source_record_invalid")
        native_file_id = str(source_ref.get("openwebui_file_id") or "")
        source_ref_sha256 = str(source_ref.get("file_hash_sha256") or "")
        if not native_file_id or source_ref_sha256 != source_sha256:
            raise Goal391SourceComparisonExportError("goal391_source_comparison_source_binding_invalid")

        owned_file = await self._file_bytes_resolver.resolve(
            file_id=native_file_id,
            actor_user_id=item.user_id,
        )
        if (
            getattr(owned_file, "file_id", None) != native_file_id
            or getattr(owned_file, "user_id", None) != item.user_id
            or getattr(owned_file, "sha256", None) != source_sha256
            or not isinstance(getattr(owned_file, "payload", None), bytes)
        ):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_original_binding_invalid")

        full_source = self._collect_full_source(
            item=item,
            document_id=document_id,
            source_sha256=source_sha256,
            source_ref=source_ref,
        )
        mapping_package = self._mapping_package_builder.build_mapping_package(
            canonical=artifact,
            confirmed_understandings=[
                dict(value) for value in mapping_scope.confirmed_understandings
            ],
            target_table_node_ids=mapping_scope.target_table_node_ids,
        )
        if not isinstance(mapping_package, Mapping):
            raise Goal391SourceComparisonExportError(
                "goal391_source_comparison_mapping_package_invalid"
            )
        return {
            "slot_id": item.slot_id,
            "canonical": dict(artifact),
            "original_bytes": owned_file.payload,
            "original_extension": _extension_for_content_type(
                str(getattr(owned_file, "content_type", ""))
            ),
            "source_payloads": full_source["payloads"],
            "source_units": full_source["units"],
            "canonical_sha256": _json_sha256(artifact),
            "original_sha256": source_sha256,
            "full_source_sha256": _json_sha256(full_source),
            "mapping_package": dict(mapping_package),
            "mapping_package_sha256": _json_sha256(mapping_package),
            "mapping_tables_total": len(
                ((mapping_package.get("case") or {}).get("tables") or [])
            ),
        }

    def _collect_full_source(
        self,
        *,
        item: PrivateCorpusSelection,
        document_id: str,
        source_sha256: str,
        source_ref: Mapping[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        context = item.access_context(require_source_available=True)
        candidates = [
            record
            for record in self._resolver.catalog_run(context)
            if getattr(record, "artifact_type", None) in _FULL_SOURCE_TYPES
            and getattr(record, "document_id", None) == document_id
            and _same_source_ref(getattr(record, "source_file_ref", None), source_ref)
        ]
        if not candidates:
            raise Goal391SourceComparisonExportError("goal391_source_comparison_full_source_missing")
        payloads: list[dict[str, Any]] = []
        units: list[dict[str, Any]] = []
        for record in candidates:
            resolved = self._resolver.resolve(getattr(record, "artifact_id", ""), context)
            value = resolved.get("payload") if isinstance(resolved, Mapping) else None
            if not isinstance(value, dict):
                raise Goal391SourceComparisonExportError("goal391_source_comparison_full_source_invalid")
            if getattr(record, "artifact_type", None) == "private_normalized_source_payload_v0":
                if value.get("document_ref") != document_id or value.get("normalization_run_id") != item.normalization_run_id:
                    raise Goal391SourceComparisonExportError("goal391_source_comparison_full_source_invalid")
                payloads.append(value)
            else:
                validation = validate_full_source_unit(
                    unit=value,
                    normalization_run_id=item.normalization_run_id,
                    document_id=document_id,
                    source_checksum_sha256=source_sha256,
                )
                if not validation.get("passed"):
                    raise Goal391SourceComparisonExportError("goal391_source_comparison_full_source_invalid")
                units.append(value)
        payload_refs = {str(value.get("source_payload_ref") or "") for value in payloads}
        if not payloads or not units or not payload_refs or len(payload_refs) != len(payloads):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_full_source_binding_invalid")
        expected_source_checksum_ref = f"srcsum_{stable_digest([document_id, source_sha256], length=24)}"
        payload_by_ref = {str(value["source_payload_ref"]): value for value in payloads}
        if any(
            not _valid_full_source_payload(
                payload,
                document_id=document_id,
                normalization_run_id=item.normalization_run_id,
                expected_source_checksum_ref=expected_source_checksum_ref,
            )
            for payload in payload_by_ref.values()
        ):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_full_source_binding_invalid")
        units_by_payload: dict[str, list[dict[str, Any]]] = {}
        for unit in units:
            parent_ref = str(unit.get("parent_payload_ref") or "")
            payload = payload_by_ref.get(parent_ref)
            if (
                payload is None
                or str(unit.get("payload_checksum_ref") or "")
                != str(payload.get("payload_checksum_ref") or "")
            ):
                raise Goal391SourceComparisonExportError("goal391_source_comparison_full_source_binding_invalid")
            units_by_payload.setdefault(parent_ref, []).append(unit)
        if set(units_by_payload) != set(payload_by_ref) or any(
            len(bound_units) != 1 for bound_units in units_by_payload.values()
        ):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_full_source_binding_invalid")
        payloads.sort(key=lambda value: str(value.get("source_payload_ref") or ""))
        units.sort(key=lambda value: str(value.get("unit_ref") or ""))
        return {"payloads": payloads, "units": units}


def _same_source_ref(left: Any, right: Mapping[str, Any]) -> bool:
    if not isinstance(left, Mapping):
        return False
    return (
        str(left.get("openwebui_file_id") or "")
        == str(right.get("openwebui_file_id") or "")
        and str(left.get("file_hash_sha256") or "")
        == str(right.get("file_hash_sha256") or "")
        and left.get("source_deleted") is not True
    )


def _valid_full_source_payload(
    payload: Mapping[str, Any],
    *,
    document_id: str,
    normalization_run_id: str,
    expected_source_checksum_ref: str,
) -> bool:
    return (
        payload.get("schema_version") == SOURCE_PAYLOAD_SCHEMA_VERSION
        and payload.get("document_ref") == document_id
        and payload.get("normalization_run_id") == normalization_run_id
        and payload.get("source_checksum_ref") == expected_source_checksum_ref
        and payload.get("parser_completeness_status") == "complete"
        and payload.get("normalized_projection_status") == "materialized"
        and payload.get("visibility") == "private_case"
        and payload.get("knowledge_rag_used") is False
        and payload.get("vectorization_performed") is False
        and isinstance(payload.get("source_payload_ref"), str)
        and bool(payload["source_payload_ref"])
        and isinstance(payload.get("payload_checksum_ref"), str)
        and bool(payload["payload_checksum_ref"])
    )


def _private_root(value: str | Path) -> Path:
    root = Path(value)
    if root.name != "_private_test_corpora" or not root.is_dir() or _is_link(root):
        raise Goal391SourceComparisonExportError("goal391_source_comparison_root_invalid")
    for parent in (root, *root.parents):
        if _is_link(parent):
            raise Goal391SourceComparisonExportError("goal391_source_comparison_root_unsafe")
    root = root.resolve(strict=True)
    if os.name != "nt" and stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise Goal391SourceComparisonExportError("goal391_source_comparison_root_unsafe")
    return root


def _path_identity(path: Path) -> tuple[int, int]:
    state = path.stat()
    return state.st_dev, state.st_ino


def _is_link(path: Path) -> bool:
    try:
        state = path.lstat()
    except OSError:
        return True
    return stat.S_ISLNK(state.st_mode) or bool(
        getattr(state, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _write_pack(target: Path, entries: list[dict[str, Any]]) -> None:
    (target / "canonical").mkdir(mode=0o700)
    (target / "original").mkdir(mode=0o700)
    (target / "full-source").mkdir(mode=0o700)
    (target / "mapping-package").mkdir(mode=0o700)
    for entry in entries:
        slot = entry["slot_id"]
        _write_json(target / "canonical" / f"{slot}.json", entry["canonical"])
        _write_bytes(
            target / "original" / f"{slot}{entry['original_extension']}",
            entry["original_bytes"],
        )
        _write_json(
            target / "full-source" / f"{slot}.json",
            {"payloads": entry["source_payloads"], "units": entry["source_units"]},
        )
        _write_json(
            target / "mapping-package" / f"{slot}.json",
            entry["mapping_package"],
        )


def _safe_receipt(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SOURCE_COMPARISON_RECEIPT_SCHEMA_VERSION,
        "status": "EXPORTED",
        "contains_private_payload": False,
        "selection_count": len(entries),
        "entries": [
            {
                "slot_id": entry["slot_id"],
                "canonical_sha256": entry["canonical_sha256"],
                "original_sha256": entry["original_sha256"],
                "full_source_sha256": entry["full_source_sha256"],
                "full_source_payloads_total": len(entry["source_payloads"]),
                "full_source_units_total": len(entry["source_units"]),
                "mapping_package_sha256": entry["mapping_package_sha256"],
                "mapping_tables_total": entry["mapping_tables_total"],
            }
            for entry in entries
        ],
    }


def _mapping_scopes_by_slot(
    selection: PrivateCorpusSelectionManifest,
    mapping_scopes: Iterable[Goal391SourceComparisonMappingScope],
) -> dict[str, Goal391SourceComparisonMappingScope]:
    scopes = list(mapping_scopes)
    if any(
        not isinstance(scope, Goal391SourceComparisonMappingScope) for scope in scopes
    ):
        raise Goal391SourceComparisonExportError(
            "goal391_source_comparison_mapping_scope_invalid"
        )
    by_slot = {scope.slot_id: scope for scope in scopes}
    selected_slots = {item.slot_id for item in selection.selections}
    if (
        len(by_slot) != len(scopes)
        or set(by_slot) != selected_slots
        or any(
            not scope.target_table_node_ids
            or len(set(scope.target_table_node_ids)) != len(scope.target_table_node_ids)
            or any(
                not isinstance(table_id, str) or not table_id
                for table_id in scope.target_table_node_ids
            )
            or any(
                not isinstance(value, dict)
                for value in scope.confirmed_understandings
            )
            for scope in scopes
        )
    ):
        raise Goal391SourceComparisonExportError(
            "goal391_source_comparison_mapping_scope_invalid"
        )
    return by_slot


def _validated_selection(
    selection: PrivateCorpusSelectionManifest,
) -> PrivateCorpusSelectionManifest:
    """Reapply the closed-world manifest boundary for programmatic callers.

    The persisted-manifest loader already makes this check, but the coordinator
    accepts the dataclass so a server composition root can keep the selection
    secret out of its process arguments.  Revalidating here prevents a manually
    constructed dataclass from turning a corpus or slot name into a path.
    """

    value = {
        "schema_version": PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION,
        "corpus_id": selection.corpus_id,
        "selections": [
            {
                "slot_id": item.slot_id,
                "manifest_ref": item.manifest_ref,
                "user_id": item.user_id,
                "normalization_run_id": item.normalization_run_id,
                "case_id": item.case_id,
                "chat_id": item.chat_id,
                "workspace_model_id": item.workspace_model_id,
            }
            for item in selection.selections
        ],
    }
    try:
        return parse_private_corpus_selection(value)
    except Goal391PrivateCorpusExportError as exc:
        raise Goal391SourceComparisonExportError(
            "goal391_source_comparison_selection_invalid"
        ) from exc


def _reserve_target(root: Path, name: str) -> tuple[Path, Path, bytes]:
    target = root / name
    try:
        target.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise Goal391SourceComparisonExportError(
            "goal391_source_comparison_target_exists"
        ) from exc
    marker = target / ".goal391-reservation"
    token = secrets.token_urlsafe(24).encode("ascii")
    try:
        descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(token)
    except OSError as exc:
        _remove_reserved_target(target, marker, token)
        raise Goal391SourceComparisonExportError(
            "goal391_source_comparison_target_reservation_failed"
        ) from exc
    return target, marker, token


def _remove_reserved_target(target: Path, marker: Path, token: bytes) -> None:
    try:
        if (
            target.is_dir()
            and not _is_link(target)
            and marker.is_file()
            and not _is_link(marker)
            and marker.read_bytes() == token
        ):
            shutil.rmtree(target)
    except OSError:
        pass


def _write_json(path: Path, value: Any) -> None:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
    _write_bytes(path, encoded)


def _write_bytes(path: Path, value: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(value)


def _json_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _sha256_text(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _extension_for_content_type(content_type: str) -> str:
    return ".pdf" if content_type.lower() == "application/pdf" else ".bin"
