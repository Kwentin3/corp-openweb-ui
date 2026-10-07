#!/usr/bin/env python3
"""Align the VPS Stage 2 build inputs with the tested release image."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


AREAS = (
    "services/stage2-stt/stage2_stt",
    "services/stage2-stt/openwebui_actions",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--production", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    args = parser.parse_args()
    paths = [Path("services/stage2-stt/pyproject.toml")]
    for area in AREAS:
        source_dir = args.candidate / area
        target_dir = args.production / area
        source_names = {path.relative_to(args.candidate) for path in source_dir.rglob("*") if path.is_file()}
        target_names = {path.relative_to(args.production) for path in target_dir.rglob("*")
                        if path.is_file() and "__pycache__" not in path.parts}
        if source_names != target_names:
            raise RuntimeError(f"Stage 2 source file inventory differs in {area}")
        paths.extend(sorted(source_names))
    for relative in paths:
        source = args.candidate / relative
        target = args.production / relative
        backup = args.backup / relative
        if not source.is_file() or not target.is_file():
            raise RuntimeError(f"Stage 2 source is missing: {relative}")
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, backup)
        shutil.copy2(source, target)
        if hashlib.sha256(source.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
            raise RuntimeError(f"Stage 2 source copy differs: {relative}")
    print(json.dumps({"stage2_source_files": len(paths), "status": "aligned"}))


if __name__ == "__main__":
    main()
