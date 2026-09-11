"""Prepare one sealed, value-free Goal #391 mapping-lab plan on the server.

This is an operator-only R&D command, not an OpenWebUI route.  It proves one
ordinary user's chat/file scope through OpenWebUI owners, then asks the
existing ArtifactResolver, ArtifactStore and Canonical reader for the exact
bound Canonical.  It never calls a provider or writes product state.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import os
from pathlib import Path
from typing import Any, Mapping

from broker_reports_gate1.artifact_models import ArtifactAccessContext
from broker_reports_gate1.artifact_resolver import ArtifactResolver
from broker_reports_gate1.artifact_store import ArtifactStoreConfig, ArtifactStoreFactory
from broker_reports_gate1.canonical_store import CanonicalReaderFactory
from broker_reports_gate1.gate3_ndfl_workflow import NDFL_WORKSPACE_MODEL_STABLE_ID
from broker_reports_gate1.goal391_mapping_lab_control_plan import (
    SERVER_BOUND_CASE_PLAN_SCHEMA_VERSION,
    canonical_table_node_ids,
    sha256_json,
    valid_expected_assessment,
)
from broker_reports_gate1.goal391_private_selection_binding import (
    Goal391PrivateSelectionBindingIssuer,
    Goal391PrivateSourceFileSelectionRequest,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingFactory,
)


_SOURCE_SELECTION_RUN_ID = "goal391-source-file-selection"


class Goal391MappingLabPlanError(RuntimeError):
    """A value-free stop before a temporary lab Function is configured."""


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    assessment = _read_assessment(arguments.expected_assessment_json)
    result = asyncio.run(
        _prepare(
            user_email=arguments.user_email,
            slot_id=arguments.slot_id,
            chat_id=arguments.chat_id,
            file_id=arguments.file_id,
            plan_ref=arguments.plan_ref,
            assessment=assessment,
            sqlite_path=arguments.sqlite_path,
            payload_root=arguments.payload_root,
        )
    )
    _write_new_private_json(arguments.output_path, result["plan"])
    print(
        json.dumps(
            {
                "status": "GOAL391_MAPPING_LAB_PLAN_READY",
                "plan_sha256": result["plan_sha256"],
                "slots_total": 1,
                "target_tables_total": result["target_tables_total"],
                "provider_calls_total": 0,
                "artifact_store_mutation": False,
            },
            sort_keys=True,
        )
    )
    return 0


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--slot-id", required=True)
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--file-id", required=True)
    parser.add_argument("--plan-ref", required=True)
    parser.add_argument("--expected-assessment-json", type=Path, required=True)
    parser.add_argument("--sqlite-path", type=Path, required=True)
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, required=True)
    arguments = parser.parse_args(argv)
    if any(
        not str(value or "").strip()
        for value in (
            arguments.user_email,
            arguments.slot_id,
            arguments.chat_id,
            arguments.file_id,
            arguments.plan_ref,
        )
    ):
        raise SystemExit("goal391_mapping_lab_plan_argument_invalid")
    return arguments


async def _prepare(
    *,
    user_email: str,
    slot_id: str,
    chat_id: str,
    file_id: str,
    plan_ref: str,
    assessment: Mapping[str, Any],
    sqlite_path: Path,
    payload_root: Path,
) -> dict[str, Any]:
    user = await _attest_browser_file(
        user_email=user_email,
        chat_id=chat_id,
        file_id=file_id,
    )
    user_id = str(getattr(user, "id", "") or "").strip()
    if not user_id:
        raise Goal391MappingLabPlanError("goal391_mapping_lab_user_invalid")
    source_context = ArtifactAccessContext(
        user_id=user_id,
        normalization_run_id=_SOURCE_SELECTION_RUN_ID,
        case_id=chat_id,
        workspace_model_id=NDFL_WORKSPACE_MODEL_STABLE_ID,
        allow_private=True,
        require_source_available=True,
    )
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite", sqlite_path=sqlite_path, payload_root=payload_root
        )
    ).create_read_only()
    reader = CanonicalReaderFactory(store=store, read_enabled=True).create()
    selection = Goal391PrivateSelectionBindingIssuer(
        store=store, reader=reader, resolver=ArtifactResolver(store)
    ).issue_from_source_files(
        corpus_id=plan_ref,
        requests=(
            Goal391PrivateSourceFileSelectionRequest(
                slot_id=slot_id,
                openwebui_file_id=file_id,
                context=source_context,
            ),
        ),
    )
    if len(selection.selections) != 1:
        raise Goal391MappingLabPlanError("goal391_mapping_lab_selection_invalid")
    item = selection.selections[0]
    context = item.access_context(require_source_available=True)
    envelope = reader.read_envelope(
        item.manifest_ref,
        context,
        expected_normalization_run_id=item.normalization_run_id,
    )
    canonical = getattr(envelope, "artifact", None)
    identity = _canonical_identity(envelope)
    try:
        table_node_ids = list(canonical_table_node_ids(canonical))
    except ValueError as exc:
        raise Goal391MappingLabPlanError("goal391_mapping_lab_tables_invalid") from exc
    if not valid_expected_assessment(
        assessment, target_table_node_ids=table_node_ids
    ):
        raise Goal391MappingLabPlanError("goal391_mapping_lab_assessment_invalid")
    # Admission remains owned by the existing semantic mapping owner.  The
    # returned package is deliberately transient and never written or emitted.
    OrdinaryTradeSemanticMappingFactory.create().build_mapping_package(
        canonical=canonical,
        confirmed_understandings=[],
        target_table_node_ids=table_node_ids,
    )
    slot = {
        "slot_id": slot_id,
        "historical_source_scope": {
            "case_id": chat_id,
            "chat_id": None,
            "workspace_model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
        },
        "source_openwebui_file_id": file_id,
        "canonical_identity": identity,
        "target_table_node_ids": table_node_ids,
        "confirmed_understandings": [],
        "frozen_mappings": [],
        "expected_assessment": dict(assessment),
    }
    plan = {
        "schema_version": SERVER_BOUND_CASE_PLAN_SCHEMA_VERSION,
        "plan_ref": plan_ref,
        "plan_digest": "",
        "ordinary_test_user_id": user_id,
        "slots": [slot],
    }
    digest_material = dict(plan)
    digest_material.pop("plan_digest")
    plan["plan_digest"] = sha256_json(digest_material)
    return {
        "plan": plan,
        "plan_sha256": sha256_json(plan),
        "target_tables_total": len(table_node_ids),
    }


async def _attest_browser_file(*, user_email: str, chat_id: str, file_id: str):
    # Import inside the server-only boundary: local contract tests must not
    # need an OpenWebUI installation, and this command never opens SQLite.
    from open_webui.models.chats import Chats
    from open_webui.models.files import Files
    from open_webui.models.users import Users

    user = await _await_if_needed(Users.get_user_by_email(user_email))
    if user is None or str(getattr(user, "role", "") or "") != "user":
        raise Goal391MappingLabPlanError("goal391_mapping_lab_user_invalid")
    user_id = str(getattr(user, "id", "") or "").strip()
    if not user_id or not await _await_if_needed(Chats.is_chat_owner(chat_id, user_id)):
        raise Goal391MappingLabPlanError("goal391_mapping_lab_chat_access_denied")
    chat = await _await_if_needed(Chats.get_chat_by_id(chat_id))
    if file_id not in _attached_file_ids(chat):
        raise Goal391MappingLabPlanError("goal391_mapping_lab_file_not_attached")
    file_record = await _await_if_needed(Files.get_file_by_id_and_user_id(file_id, user_id))
    if file_record is None:
        raise Goal391MappingLabPlanError("goal391_mapping_lab_file_access_denied")
    return user


async def _await_if_needed(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _attached_file_ids(chat: Any) -> set[str]:
    if hasattr(chat, "model_dump"):
        chat = chat.model_dump()
    elif not isinstance(chat, Mapping):
        chat = getattr(chat, "chat", None)
    if not isinstance(chat, Mapping):
        return set()
    files = chat.get("files")
    if not isinstance(files, list):
        return set()
    return {
        str(file.get("id") or "")
        for file in files
        if isinstance(file, Mapping) and str(file.get("id") or "")
    }


def _canonical_identity(envelope: Any) -> dict[str, str]:
    artifact = getattr(envelope, "artifact", None)
    source = artifact.get("source") if isinstance(artifact, Mapping) else None
    identity = {
        "document_id": str(getattr(envelope, "document_id", "") or ""),
        "canonical_root_sha256": str(
            getattr(envelope, "canonical_root_sha256", "") or ""
        ),
        "source_sha256": str(
            source.get("source_sha256") if isinstance(source, Mapping) else ""
        ),
    }
    if not all(identity.values()):
        raise Goal391MappingLabPlanError("goal391_mapping_lab_canonical_invalid")
    return identity


def _read_assessment(path: Path) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit("goal391_mapping_lab_assessment_read_invalid") from exc
    if not isinstance(value, Mapping):
        raise SystemExit("goal391_mapping_lab_assessment_read_invalid")
    return value


def _write_new_private_json(path: Path, value: Mapping[str, Any]) -> None:
    parent = path.parent
    if not parent.is_dir() or path.exists():
        raise SystemExit("goal391_mapping_lab_output_invalid")
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(encoded)
            output.write("\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
