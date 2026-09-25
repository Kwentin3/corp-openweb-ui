#!/usr/bin/env python3
"""Read-only post-migration check of native chat attachments and disk blobs."""

import argparse
import json
import sqlite3
from pathlib import Path


def attachment_id(item: dict) -> str | None:
    return (item.get("file") or {}).get("id") or item.get("id")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--uploads", type=Path, required=True)
    args = parser.parse_args()
    db = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity: {integrity}")
    converted = 0
    for row in db.execute("SELECT id, path, meta, data FROM file"):
        data = json.loads(row["data"] or "{}")
        if data.get("legacy_media_backfill") != "completed":
            continue
        marker = data.get("stage2_video_intake") or {}
        meta = json.loads(row["meta"] or "{}")
        if marker.get("state") != "completed" or meta.get("content_type") != "audio/mpeg":
            raise RuntimeError(f"Converted File state is inconsistent: {row['id']}")
        if not row["path"] or not (args.uploads / Path(row["path"]).name).is_file():
            raise RuntimeError(f"Converted audio blob is missing: {row['id']}")
        links = db.execute("SELECT chat_id, message_id FROM chat_file WHERE file_id = ?", (row["id"],)).fetchall()
        if len(links) != 1:
            raise RuntimeError(f"Converted File has {len(links)} chat links: {row['id']}")
        link = links[0]
        chat = db.execute("SELECT chat FROM chat WHERE id = ?", (link["chat_id"],)).fetchone()
        message = db.execute("SELECT files FROM chat_message WHERE id = ?", (f'{link["chat_id"]}-{link["message_id"]}',)).fetchone()
        if chat is None or message is None:
            raise RuntimeError(f"Converted chat or message is missing: {row['id']}")
        history = json.loads(chat["chat"] or "{}")
        stored = ((history.get("history") or {}).get("messages") or {}).get(link["message_id"])
        if not isinstance(stored, dict):
            raise RuntimeError(f"Converted history message is missing: {row['id']}")
        for files in (stored.get("files"), json.loads(message["files"] or "[]")):
            matches = [item for item in files or [] if isinstance(item, dict) and attachment_id(item) == row["id"]]
            if len(matches) != 1 or not str(matches[0].get("content_type") or "").startswith("audio/"):
                raise RuntimeError(f"Converted chat descriptor is inconsistent: {row['id']}")
        converted += 1
    print(json.dumps({"sqlite_integrity": integrity, "converted_chat_attachments": converted}))


if __name__ == "__main__":
    main()
