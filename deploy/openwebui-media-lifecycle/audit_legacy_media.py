#!/usr/bin/env python3
"""Read-only inventory of video Files and their native chat links."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".mpeg", ".mpg"}

def inventory(db_path: Path, upload_dir: Path) -> dict:
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    links = Counter(row["file_id"] for row in db.execute("SELECT file_id FROM chat_file"))
    videos = []
    derived = Counter()
    rows = list(db.execute("SELECT id, filename, path, meta, data FROM file"))
    referenced_paths = {Path(row["path"]).name for row in rows if row["path"]}
    orphan_blobs = [path for path in upload_dir.iterdir()
                    if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
                    and path.name not in referenced_paths]
    for row in rows:
        data = json.loads(row["data"] or "{}")
        source_id = (data.get("stage2_media_lifecycle") or {}).get("source_file_id")
        if source_id:
            derived[source_id] += 1
    for row in rows:
        meta = json.loads(row["meta"] or "{}")
        if not str(meta.get("content_type") or "").startswith("video/"):
            continue
        path = upload_dir / Path(row["path"] or "").name
        data = json.loads(row["data"] or "{}")
        relations = []
        for link in db.execute("SELECT chat_id, message_id FROM chat_file WHERE file_id = ?", (row["id"],)):
            chat = db.execute("SELECT chat FROM chat WHERE id = ?", (link["chat_id"],)).fetchone()
            message = db.execute("SELECT files FROM chat_message WHERE id = ?", (f'{link["chat_id"]}-{link["message_id"]}',)).fetchone()
            history = (json.loads(chat["chat"] or "{}") if chat else {}).get("history") or {}
            stored = (history.get("messages") or {}).get(link["message_id"]) or {}
            relations.append({
                "chat_exists": chat is not None,
                "history_message_exists": bool(stored),
                "history_file_count": len(stored.get("files") or []),
                "message_exists": message is not None,
                "message_file_count": len(json.loads(message["files"] or "[]")) if message else 0,
            })
        videos.append({
            "id": row["id"],
            "size": path.stat().st_size if path.is_file() else 0,
            "blob_exists": path.is_file(),
            "chat_links": links[row["id"]],
            "derived_audio_rows": derived[row["id"]],
            "chat_json_mentions": db.execute("SELECT COUNT(*) FROM chat WHERE chat LIKE ?", (f'%{row["id"]}%',)).fetchone()[0],
            "relations": relations,
            "status": data.get("status"),
        })
    return {
        "video_rows": len(videos),
        "video_bytes": sum(v["size"] for v in videos),
        "chat_link_counts": dict(sorted(Counter(v["chat_links"] for v in videos).items())),
        "unreferenced_video_blobs": len(orphan_blobs),
        "unreferenced_video_bytes": sum(path.stat().st_size for path in orphan_blobs),
        "videos": videos,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--uploads", type=Path, required=True)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    result = inventory(args.db, args.uploads)
    if args.summary:
        result.pop("videos")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
