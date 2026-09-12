#!/usr/bin/env python3
"""Container half of the closed native Broker Reports Prompt release boundary.

The script runs *inside* the pinned OpenWebUI container.  It imports only the
repository package staged for this release and delegates every Prompt mutation
and history read to OpenWebUI's own ``Prompts`` and ``PromptHistories`` owners.
It intentionally has no SQLite, HTTP, credential or Pipe mutation path.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


SAFE_SCHEMA_VERSION = "broker_reports_native_mapping_prompt_pin_v1"
_PROFILE_IDS = frozenset(
    {
        "ordinary_trade_mapping_v13",
        "goal391_grouped_mapping_lab_v14",
        "ordinary_trade_mapping_v14",
        "ordinary_trade_mapping_v15",
        "ordinary_trade_mapping_v16",
        "ordinary_trade_mapping_v17",
        "ordinary_trade_mapping_v18",
        "ordinary_trade_mapping_v19",
        "pdf_table_continuation_annotation_v3",
        "document_metadata_passport_v1",
    }
)


def _safe_output(*, status: str, publication: Any) -> dict[str, str]:
    return {
        "schema_version": SAFE_SCHEMA_VERSION,
        "status": status,
        "prompt_ref": publication.prompt_ref,
        "prompt_command": publication.prompt_command,
        "prompt_history_id": publication.prompt_history_id,
        "prompt_hash": publication.prompt_hash,
        "action": publication.action,
    }


async def _existing_actor_id() -> str:
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.prompts import Prompts
    from broker_reports_gate1.ordinary_trade_mapping_prompt import PROMPT_COMMAND

    async with get_async_db_context() as session:
        existing = await Prompts.get_prompt_by_command(PROMPT_COMMAND, db=session)
    if existing is None or not hasattr(existing, "model_dump"):
        raise RuntimeError("ordinary_trade_mapping_prompt_release_actor_unavailable")
    actor_user_id = str(existing.model_dump().get("user_id") or "").strip()
    if not actor_user_id:
        raise RuntimeError("ordinary_trade_mapping_prompt_release_actor_unavailable")
    return actor_user_id


async def _run(
    *,
    asset_root: Path,
    verify_pin: dict[str, str] | None,
    profile_id: str,
) -> dict[str, str]:
    from broker_reports_gate1.ordinary_trade_mapping_prompt_publication import (
        GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE,
        ORDINARY_TRADE_MAPPING_V14_PROFILE,
        ORDINARY_TRADE_MAPPING_V15_PROFILE,
        ORDINARY_TRADE_MAPPING_V16_PROFILE,
        ORDINARY_TRADE_MAPPING_V17_PROFILE,
        ORDINARY_TRADE_MAPPING_V18_PROFILE,
        ORDINARY_TRADE_MAPPING_V19_PROFILE,
        PDF_TABLE_CONTINUATION_ANNOTATION_V3_PROFILE,
        DOCUMENT_METADATA_PASSPORT_V1_PROFILE,
        ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE,
        OrdinaryTradeMappingPromptPublication,
        OrdinaryTradeMappingPromptPublisher,
        publication_input_from_asset,
    )

    profiles = {
        ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE.profile_id: ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE,
        GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE.profile_id: GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE,
        ORDINARY_TRADE_MAPPING_V14_PROFILE.profile_id: ORDINARY_TRADE_MAPPING_V14_PROFILE,
        ORDINARY_TRADE_MAPPING_V15_PROFILE.profile_id: ORDINARY_TRADE_MAPPING_V15_PROFILE,
        ORDINARY_TRADE_MAPPING_V16_PROFILE.profile_id: ORDINARY_TRADE_MAPPING_V16_PROFILE,
        ORDINARY_TRADE_MAPPING_V17_PROFILE.profile_id: ORDINARY_TRADE_MAPPING_V17_PROFILE,
        ORDINARY_TRADE_MAPPING_V18_PROFILE.profile_id: ORDINARY_TRADE_MAPPING_V18_PROFILE,
        ORDINARY_TRADE_MAPPING_V19_PROFILE.profile_id: ORDINARY_TRADE_MAPPING_V19_PROFILE,
        PDF_TABLE_CONTINUATION_ANNOTATION_V3_PROFILE.profile_id: PDF_TABLE_CONTINUATION_ANNOTATION_V3_PROFILE,
        DOCUMENT_METADATA_PASSPORT_V1_PROFILE.profile_id: DOCUMENT_METADATA_PASSPORT_V1_PROFILE,
    }
    profile = profiles.get(profile_id)
    if profile is None:
        raise RuntimeError("ordinary_trade_mapping_prompt_release_profile_invalid")
    publisher = OrdinaryTradeMappingPromptPublisher(profile=profile)
    if verify_pin is not None:
        publication = OrdinaryTradeMappingPromptPublication(
            prompt_ref=verify_pin["prompt_ref"],
            prompt_command=verify_pin["prompt_command"],
            prompt_history_id=verify_pin["prompt_history_id"],
            prompt_hash=verify_pin["prompt_hash"],
            action="released",
        )
        return _safe_output(status="verified", publication=await publisher.verify(publication))
    request = publication_input_from_asset(
        actor_user_id=await _existing_actor_id(),
        asset_root=asset_root,
        profile=profile,
    )
    return _safe_output(status="published", publication=await publisher.publish(request))


def _pin(value: str | None) -> dict[str, str] | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except ValueError as exc:
        raise RuntimeError("ordinary_trade_mapping_prompt_release_pin_invalid") from exc
    keys = {"prompt_ref", "prompt_command", "prompt_history_id", "prompt_hash"}
    if not isinstance(parsed, dict) or set(parsed) != keys or any(
        not isinstance(parsed[key], str) or not parsed[key] for key in keys
    ):
        raise RuntimeError("ordinary_trade_mapping_prompt_release_pin_invalid")
    return {key: parsed[key] for key in sorted(keys)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-archive", required=True)
    parser.add_argument("--verify-pin-json", default=None)
    parser.add_argument(
        "--profile", choices=sorted(_PROFILE_IDS), default="ordinary_trade_mapping_v16"
    )
    args = parser.parse_args()
    archive = Path(args.source_archive)
    if not archive.is_file() or archive.is_symlink():
        raise RuntimeError("ordinary_trade_mapping_prompt_release_archive_invalid")
    root = Path(tempfile.mkdtemp(prefix="broker-reports-prompt-", dir="/tmp"))
    try:
        with zipfile.ZipFile(archive) as payload:
            names = payload.namelist()
            if not names or any(Path(name).is_absolute() or ".." in Path(name).parts for name in names):
                raise RuntimeError("ordinary_trade_mapping_prompt_release_archive_invalid")
            payload.extractall(root)
        service_root = root / "services" / "broker-reports-gate1-proof"
        if not (service_root / "broker_reports_gate1").is_dir() or not (
            service_root / "managed_assets" / "prompts"
        ).is_dir():
            raise RuntimeError("ordinary_trade_mapping_prompt_release_archive_invalid")
        sys.path.insert(0, str(service_root))
        print(json.dumps(asyncio.run(_run(
            asset_root=service_root / "managed_assets" / "prompts",
            verify_pin=_pin(args.verify_pin_json),
            profile_id=args.profile,
        )), ensure_ascii=False, sort_keys=True))
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "error", "code": str(exc)[:200]}, sort_keys=True))
        raise
