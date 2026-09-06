"""Explicit private Canonical export for the Goal #391 R&D laboratory.

This is deliberately a narrow laboratory composition seam.  It receives an
already chosen manifest, asks the existing ``CanonicalReader`` for each exact
manifest reference under its stated access context, and writes a local pack
below the repository-ignored ``_private_test_corpora`` root.  It does not
discover artifacts, interpret financial data, call a model, or mutate the
ArtifactStore.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .artifact_models import ArtifactAccessContext


PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION = "goal391_private_corpus_selection_v1"
PRIVATE_CORPUS_PACK_SCHEMA_VERSION = "goal391_private_corpus_pack_v1"
PRIVATE_CORPUS_EXPORT_RECEIPT_SCHEMA_VERSION = "goal391_private_corpus_export_receipt_v1"

_CORPUS_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class Goal391PrivateCorpusExportError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PrivateCorpusSelection:
    """One explicitly authorised Canonical read; no query or selector exists."""

    slot_id: str
    manifest_ref: str
    user_id: str
    normalization_run_id: str
    case_id: str | None
    chat_id: str | None
    workspace_model_id: str | None

    def access_context(self) -> ArtifactAccessContext:
        return ArtifactAccessContext(
            user_id=self.user_id,
            normalization_run_id=self.normalization_run_id,
            case_id=self.case_id,
            chat_id=self.chat_id,
            workspace_model_id=self.workspace_model_id,
            allow_private=True,
        )


@dataclass(frozen=True)
class PrivateCorpusSelectionManifest:
    corpus_id: str
    selections: tuple[PrivateCorpusSelection, ...]


def load_private_corpus_selection(path: str | Path) -> PrivateCorpusSelectionManifest:
    """Load one closed-world local selection manifest."""

    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Goal391PrivateCorpusExportError(
            "goal391_private_corpus_selection_json_invalid"
        ) from exc
    return parse_private_corpus_selection(value)


def parse_private_corpus_selection(value: Mapping[str, Any]) -> PrivateCorpusSelectionManifest:
    """Validate every selected identity before any Canonical read occurs."""

    if not isinstance(value, Mapping) or set(value) != {
        "schema_version",
        "corpus_id",
        "selections",
    } or value.get("schema_version") != PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION:
        raise Goal391PrivateCorpusExportError(
            "goal391_private_corpus_selection_invalid"
        )
    corpus_id = value.get("corpus_id")
    raw_selections = value.get("selections")
    if not isinstance(corpus_id, str) or not _CORPUS_ID.fullmatch(corpus_id):
        raise Goal391PrivateCorpusExportError("goal391_private_corpus_id_invalid")
    if not isinstance(raw_selections, list) or not raw_selections:
        raise Goal391PrivateCorpusExportError(
            "goal391_private_corpus_selection_empty"
        )
    selections = tuple(_parse_selection(item) for item in raw_selections)
    if len({item.slot_id for item in selections}) != len(selections):
        raise Goal391PrivateCorpusExportError(
            "goal391_private_corpus_slot_duplicate"
        )
    if len({item.manifest_ref for item in selections}) != len(selections):
        raise Goal391PrivateCorpusExportError(
            "goal391_private_corpus_manifest_duplicate"
        )
    return PrivateCorpusSelectionManifest(corpus_id=corpus_id, selections=selections)


def _parse_selection(value: Any) -> PrivateCorpusSelection:
    required = {
        "slot_id",
        "manifest_ref",
        "user_id",
        "normalization_run_id",
        "case_id",
        "chat_id",
        "workspace_model_id",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise Goal391PrivateCorpusExportError(
            "goal391_private_corpus_selection_invalid"
        )
    slot_id = value.get("slot_id")
    required_strings = ("manifest_ref", "user_id", "normalization_run_id")
    if not isinstance(slot_id, str) or not _CORPUS_ID.fullmatch(slot_id) or any(
        not isinstance(value.get(key), str) or not value[key].strip()
        for key in required_strings
    ):
        raise Goal391PrivateCorpusExportError(
            "goal391_private_corpus_selection_invalid"
        )
    case_id = value.get("case_id")
    chat_id = value.get("chat_id")
    workspace_model_id = value.get("workspace_model_id")
    if (
        (case_id is None) == (chat_id is None)
        or case_id is not None and (not isinstance(case_id, str) or not case_id)
        or chat_id is not None and (not isinstance(chat_id, str) or not chat_id)
        or workspace_model_id is not None
        and (not isinstance(workspace_model_id, str) or not workspace_model_id)
    ):
        raise Goal391PrivateCorpusExportError(
            "goal391_private_corpus_selection_scope_invalid"
        )
    return PrivateCorpusSelection(
        slot_id=slot_id,
        manifest_ref=str(value["manifest_ref"]),
        user_id=str(value["user_id"]),
        normalization_run_id=str(value["normalization_run_id"]),
        case_id=case_id,
        chat_id=chat_id,
        workspace_model_id=workspace_model_id,
    )


class Goal391PrivateCorpusExportCoordinator:
    """Copy an explicit immutable Canonical set into a private local pack."""

    def __init__(self, *, reader: Any, private_corpus_root: str | Path) -> None:
        if reader is None or not callable(getattr(reader, "read_envelope", None)):
            raise Goal391PrivateCorpusExportError(
                "goal391_private_corpus_reader_required"
            )
        self._reader = reader
        self._root = _private_corpus_root(private_corpus_root)

    def export(self, *, selection: PrivateCorpusSelectionManifest) -> dict[str, Any]:
        """Export only manifest-listed Canonical artifacts, atomically locally."""

        if not isinstance(selection, PrivateCorpusSelectionManifest):
            raise Goal391PrivateCorpusExportError(
                "goal391_private_corpus_selection_required"
            )
        target = self._root / selection.corpus_id
        if target.exists():
            raise Goal391PrivateCorpusExportError(
                "goal391_private_corpus_target_exists"
            )
        staging = self._root / f".{selection.corpus_id}.staging-{secrets.token_hex(8)}"
        try:
            staging.mkdir(mode=0o700)
            cases_root = staging / "canonical"
            cases_root.mkdir(mode=0o700)
            entries = []
            for item in selection.selections:
                envelope = self._reader.read_envelope(
                    item.manifest_ref, item.access_context()
                )
                entry = _pack_entry(item, envelope)
                canonical_path = cases_root / f"{item.slot_id}.json"
                _write_json(canonical_path, envelope.artifact)
                entry["canonical_file"] = f"canonical/{item.slot_id}.json"
                entry["canonical_file_sha256"] = _sha256(envelope.artifact)
                entries.append(entry)
            pack = {
                "schema_version": PRIVATE_CORPUS_PACK_SCHEMA_VERSION,
                "corpus_id": selection.corpus_id,
                "entries": entries,
            }
            _write_json(staging / "corpus_manifest.private.json", pack)
            receipt = {
                "schema_version": PRIVATE_CORPUS_EXPORT_RECEIPT_SCHEMA_VERSION,
                "status": "EXPORTED",
                "contains_private_payload": False,
                "selection_count": len(entries),
                "selection_manifest_sha256": _sha256(_selection_as_dict(selection)),
                "corpus_manifest_sha256": _sha256(pack),
                "canonical_file_sha256s": sorted(
                    entry["canonical_file_sha256"] for entry in entries
                ),
            }
            _write_json(staging / "export_receipt.json", receipt)
            os.replace(staging, target)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return receipt


def _pack_entry(selection: PrivateCorpusSelection, envelope: Any) -> dict[str, Any]:
    artifact = getattr(envelope, "artifact", None)
    source = artifact.get("source") if isinstance(artifact, Mapping) else None
    required = (
        getattr(envelope, "document_id", None),
        getattr(envelope, "canonical_version_id", None),
        getattr(envelope, "canonical_root_sha256", None),
        source.get("source_artifact_ref") if isinstance(source, Mapping) else None,
        source.get("source_sha256") if isinstance(source, Mapping) else None,
    )
    if (
        not isinstance(artifact, Mapping)
        or artifact.get("tenant_id") != selection.user_id
        or not all(isinstance(item, str) and item for item in required)
        or artifact.get("canonical_root_hash") != envelope.canonical_root_sha256
    ):
        raise Goal391PrivateCorpusExportError(
            "goal391_private_corpus_reader_binding_invalid"
        )
    return {
        "slot_id": selection.slot_id,
        "canonical_binding": {
            "document_id": envelope.document_id,
            "canonical_version_id": envelope.canonical_version_id,
            "canonical_root_sha256": envelope.canonical_root_sha256,
            "source_artifact_ref": source["source_artifact_ref"],
            "source_sha256": source["source_sha256"],
        },
    }


def _private_corpus_root(value: str | Path) -> Path:
    root = Path(value).resolve()
    if root.name != "_private_test_corpora" or not root.is_dir():
        raise Goal391PrivateCorpusExportError(
            "goal391_private_corpus_root_invalid"
        )
    return root


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _selection_as_dict(selection: PrivateCorpusSelectionManifest) -> dict[str, Any]:
    return {
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


def _sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "Goal391PrivateCorpusExportCoordinator",
    "Goal391PrivateCorpusExportError",
    "PRIVATE_CORPUS_EXPORT_RECEIPT_SCHEMA_VERSION",
    "PRIVATE_CORPUS_PACK_SCHEMA_VERSION",
    "PRIVATE_CORPUS_SELECTION_SCHEMA_VERSION",
    "PrivateCorpusSelection",
    "PrivateCorpusSelectionManifest",
    "load_private_corpus_selection",
    "parse_private_corpus_selection",
]
