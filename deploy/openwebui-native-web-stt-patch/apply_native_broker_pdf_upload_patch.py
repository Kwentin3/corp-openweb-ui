#!/usr/bin/env python3
"""Patch OpenWebUI's pinned chat upload path for private Broker PDF custody.

OpenWebUI v0.9.6 already owns the selected-model state and the native file
upload API's ``process`` argument.  This exact, fail-fast bundle patch changes
only the default PDF upload for the single Broker Gate 1 model to
``process=false``.  Explicit image/media behavior and every other model remain
unchanged.
"""

from __future__ import annotations

import argparse
from pathlib import Path


PATCH_ID = "broker-native-pdf-upload-v1"
MODEL_ID = "broker_reports_gate1_pipe"

# Exact signature emitted by the pinned ghcr.io/open-webui/open-webui:v0.9.6
# build.  A base-image drift must fail the image build instead of silently
# restoring process=true.
OLD = 'is=async(De,st=!0,at={})=>{'
NEW = (
    OLD
    + 'M().length===1&&M()[0]==="'
    + MODEL_ID
    + '"&&(De.type==="application/pdf"||String(De.name||"").toLowerCase().endsWith(".pdf"))&&(st=!1);'
)


def patch_file(path: Path, dry_run: bool) -> str | None:
    source = path.read_text(encoding="utf-8")
    old_count = source.count(OLD)
    new_count = source.count(NEW)

    if old_count == 1 and new_count == 0:
        if not dry_run:
            path.write_text(source.replace(OLD, NEW), encoding="utf-8")
        return "patched"

    if old_count == 1 and new_count == 1:
        # NEW contains OLD as its prefix.
        return "already_patched"

    if old_count or new_count:
        raise RuntimeError(
            f"{path}: unexpected patch signature counts old={old_count} new={new_count}"
        )

    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/app/build/_app/immutable/chunks")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise RuntimeError(f"OpenWebUI chunk root does not exist: {root}")

    touched: list[tuple[Path, str]] = []
    for path in sorted(root.glob("*.js")):
        status = patch_file(path, args.dry_run)
        if status:
            touched.append((path, status))

    if len(touched) != 1:
        details = ", ".join(f"{path.name}:{status}" for path, status in touched) or "none"
        raise RuntimeError(
            f"Expected exactly one OpenWebUI Broker PDF upload chunk, got {details}"
        )

    path, status = touched[0]
    mode = "dry-run " if args.dry_run else ""
    print(f"{mode}{PATCH_ID}: {status} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
