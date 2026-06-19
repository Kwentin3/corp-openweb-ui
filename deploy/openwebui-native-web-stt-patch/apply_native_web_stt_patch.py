#!/usr/bin/env python3
"""Patch OpenWebUI's built Web API STT recorder chunk.

The source-level intent is:
- reset the per-recording transcript accumulator before SpeechRecognition starts;
- rebuild the transcript from the current SpeechRecognitionResultList instead of
  appending the last result blindly;
- increase the inactivity timeout from 2s to 5s.

The script is intentionally fail-fast. If the pinned OpenWebUI bundle changes,
the image build should fail instead of silently shipping an unpatched recorder.
"""

from __future__ import annotations

import argparse
from pathlib import Path


PATCH_ID = "stage2-native-web-stt-v1"

OLD = (
    'p=new(window.SpeechRecognition||window.webkitSpeechRecognition),'
    'p.continuous=!0;const r=2e3;let s;p.start(),'
    'p.onresult=async c=>{var y;clearTimeout(s);'
    'const k=c.results[Object.keys(c.results).length-1][0].transcript;'
    "O=`${O}${k}`,await de(),"
)

NEW = (
    'p=new(window.SpeechRecognition||window.webkitSpeechRecognition),'
    'p.continuous=!0,O="",p.__stage2NativeWebSttPatch="'
    + PATCH_ID
    + '";const r=5e3;let s;p.start(),'
    'p.onresult=async c=>{var y;clearTimeout(s);const k=[];'
    'for(let C=0;C<c.results.length;C++){const A=c.results[C];'
    'A&&A[0]&&k.push(A[0].transcript||"")}O=k.join(""),await de(),'
)


def patch_file(path: Path, dry_run: bool) -> str | None:
    text = path.read_text(encoding="utf-8")
    old_count = text.count(OLD)
    new_count = text.count(NEW)

    if old_count == 1 and new_count == 0:
        if not dry_run:
            path.write_text(text.replace(OLD, NEW), encoding="utf-8")
        return "patched"

    if old_count == 0 and new_count == 1:
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
        raise RuntimeError(f"Expected exactly one OpenWebUI Web STT recorder chunk, got {details}")

    path, status = touched[0]
    mode = "dry-run " if args.dry_run else ""
    print(f"{mode}{PATCH_ID}: {status} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
