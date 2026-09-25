#!/usr/bin/env python3
"""Replace the active native STT Filter source while OpenWebUI is stopped."""

import asyncio
import argparse
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from open_webui.internal.db import get_async_db_context
from open_webui.models.functions import Function, Functions


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    source = Path("/tmp/stage2_audio_context_filter.py").read_text(encoding="utf-8")
    if "version: 0.2.2" not in source or "file_handler =" in source:
        raise RuntimeError("Unexpected STT Filter source")
    async with get_async_db_context() as db:
        rows = (await db.execute(select(Function).where(Function.type == "filter"))).scalars().all()
    matches = [row for row in rows if "title: Audio context for ordinary chats" in (row.content or "")]
    if len(matches) != 1 or not matches[0].is_active or not matches[0].is_global:
        raise RuntimeError("Expected exactly one active global audio context Filter")
    row = matches[0]
    old_version = (row.meta or {}).get("manifest", {}).get("version")
    if args.dry_run:
        print(json.dumps({"filter_id": row.id, "old_version": old_version, "candidate_sha256": hashlib.sha256(source.encode()).hexdigest()}))
        return
    meta = {**(row.meta or {}), "manifest": {**(row.meta or {}).get("manifest", {}), "version": "0.2.2"}}
    updated = await Functions.update_function_by_id(row.id, {"content": source, "meta": meta})
    if updated is None or updated.content != source or not updated.is_active or not updated.is_global:
        raise RuntimeError("STT Filter update did not persist")
    print(json.dumps({"filter_id": row.id, "old_version": old_version, "version": "0.2.2", "sha256": hashlib.sha256(source.encode()).hexdigest()}))


if __name__ == "__main__":
    asyncio.run(main())
