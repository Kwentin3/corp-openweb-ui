#!/usr/bin/env python3
"""Verify the quiesced, media-scoped production rollback copy."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    source_db = args.source / "webui.db"
    backup_db = args.backup / "webui.db"
    if digest(source_db) != digest(backup_db):
        raise RuntimeError("SQLite source and backup differ")
    db = sqlite3.connect(str(backup_db))
    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"Backup SQLite integrity: {integrity}")
    for name in ("uploads", "stage2_stt_data"):
        source_dir = args.source / name if name == "uploads" else Path("/var/lib/docker/volumes/stage2_stt_data/_data")
        backup_dir = args.backup / name
        source_files = {p.relative_to(source_dir): p.stat().st_size for p in source_dir.rglob("*") if p.is_file()}
        backup_files = {p.relative_to(backup_dir): p.stat().st_size for p in backup_dir.rglob("*") if p.is_file()}
        if source_files != backup_files:
            raise RuntimeError(f"{name} backup file inventory differs")
        print(json.dumps({"area": name, "files": len(source_files), "bytes": sum(source_files.values())}))
    print(json.dumps({"sqlite_integrity": integrity, "db_bytes": source_db.stat().st_size, "db_sha256": digest(source_db)}))


if __name__ == "__main__":
    main()
