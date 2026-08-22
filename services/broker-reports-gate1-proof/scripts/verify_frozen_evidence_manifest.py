#!/usr/bin/env python3
"""Verify frozen historical proof bytes without rebuilding them."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
DEFAULT_MANIFEST = SERVICE_ROOT / "frozen_evidence_manifest.v1.json"


def verify(manifest_path: Path = DEFAULT_MANIFEST) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"schema_version", "files"}
        or manifest.get("schema_version")
        != "broker_reports_frozen_evidence_manifest_v1"
        or not isinstance(manifest.get("files"), list)
        or not manifest["files"]
    ):
        raise RuntimeError("frozen_evidence_manifest_contract_invalid")
    seen: set[str] = set()
    for item in manifest["files"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "sha256"}
            or not isinstance(item.get("path"), str)
            or not isinstance(item.get("sha256"), str)
            or item["path"] in seen
        ):
            raise RuntimeError("frozen_evidence_manifest_entry_invalid")
        seen.add(item["path"])
        path = (REPO_ROOT / item["path"]).resolve()
        try:
            path.relative_to(REPO_ROOT.resolve())
        except ValueError as exc:
            raise RuntimeError("frozen_evidence_path_outside_repository") from exc
        if not path.is_file():
            raise RuntimeError(f"frozen_evidence_missing:{item['path']}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != item["sha256"]:
            raise RuntimeError(f"frozen_evidence_drift:{item['path']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    arguments = parser.parse_args()
    verify(arguments.manifest)
    print("FROZEN_EVIDENCE_BYTES_CONFIRMED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
