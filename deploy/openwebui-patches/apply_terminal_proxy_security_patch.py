#!/usr/bin/env python3
"""Backport the OpenWebUI 0.10 terminal WebSocket path fix to pinned 0.9.6.

OpenWebUI 0.9.6 interpolates ``session_id`` into an upstream URL after FastAPI
has decoded it once.  An encoded query delimiter can therefore inject a second
``user_id`` before the authenticated caller's value.  The upstream 0.10 fix
quotes the value as one opaque path segment.  This overlay also rejects the
delimiter, slash, percent, backslash, and control characters named in the
upstream advisory, including values that would become dangerous after another
decode pass.

The replacement is intentionally exact and fail closed.  Remove this overlay
when the pinned base image is upgraded to OpenWebUI 0.10.0 or newer.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


PATCH_ID = "openwebui-0.9.6-terminal-session-path-cve-2026-59224"

OLD = """    import urllib.parse

    if policy_id:
        upstream_url = f'{ws_base}/p/{policy_id}/api/terminals/{session_id}'
    else:
        upstream_url = f'{ws_base}/api/terminals/{session_id}'
"""

NEW = """    import urllib.parse

    # Treat session_id as one opaque path segment. Reject characters called
    # out by GHSA-j657-m4c4-24jq before quoting so repeated decoding upstream
    # cannot turn a path value into an attacker-controlled query string.
    forbidden = '?#&/%\\\\'
    if (
        not session_id
        or any(char in session_id for char in forbidden)
        or any(ord(char) < 32 or ord(char) == 127 for char in session_id)
    ):
        await ws.close(code=4003, reason='Invalid terminal session ID')
        return
    safe_session_id = urllib.parse.quote(session_id, safe='')
    if policy_id:
        upstream_url = f'{ws_base}/p/{policy_id}/api/terminals/{safe_session_id}'
    else:
        upstream_url = f'{ws_base}/api/terminals/{safe_session_id}'
"""


def patch_source(source: str) -> tuple[str, str]:
    old_count = source.count(OLD)
    new_count = source.count(NEW)

    if old_count == 1 and new_count == 0:
        patched = source.replace(OLD, NEW)
        ast.parse(patched)
        return patched, "patched"

    if old_count == 0 and new_count == 1:
        ast.parse(source)
        return source, "already_patched"

    raise RuntimeError(
        f"Unexpected terminal proxy patch signature counts old={old_count} new={new_count}"
    )


def patch_file(path: Path, dry_run: bool = False) -> str:
    source = path.read_text(encoding="utf-8")
    patched, status = patch_source(source)
    if status == "patched" and not dry_run:
        path.write_text(patched, encoding="utf-8")
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--path",
        type=Path,
        default=Path("/app/backend/open_webui/routers/terminals.py"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.path.is_file():
        raise RuntimeError(f"OpenWebUI terminal router does not exist: {args.path}")
    status = patch_file(args.path, dry_run=args.dry_run)
    prefix = "dry-run " if args.dry_run else ""
    print(f"{prefix}{PATCH_ID}: {status} {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
