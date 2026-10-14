"""Backport OpenWebUI #31593 to the exact deployed 0.11.4 source.

Remove this overlay when the selected runtime includes upstream commit
e88e1f8119fa88110beca57ffa7f0578d97ce699. No tool execution or state owner changes.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ORIGINAL_SHA256 = "930bc3271439c0ccef10d303365940e7687cb1ec9664b9c6bbeb89fb44bb62b0"
PATCHED_SHA256 = "5ce742935aebfcdb1aaa3134db34a441398c9506e79cd09d768267afdb18d4c3"
OLD = "        if item_type not in {'function_call', 'function_call_output'}:"
NEW = "        if item_type != 'function_call_output':"


def apply(root: Path, *, check: bool = False) -> str:
    path = root / "utils" / "misc.py"
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest == PATCHED_SHA256:
        return "Exact upstream backport already present"
    if digest != ORIGINAL_SHA256:
        raise RuntimeError(f"Unsupported OpenWebUI misc.py sha256={digest}")
    source = data.decode("utf-8")
    if source.count(OLD) != 1:
        raise RuntimeError("Expected exactly one upstream #31593 anchor")
    updated = source.replace(OLD, NEW).encode("utf-8")
    if hashlib.sha256(updated).hexdigest() != PATCHED_SHA256:
        raise RuntimeError("Result differs from the exact upstream backport")
    compile(updated, str(path), "exec")
    if check:
        return "Exact upstream backport applicable; source unchanged"
    path.write_bytes(updated)
    return "Exact upstream #31593 backport applied"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/app/backend/open_webui"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(apply(args.root, check=args.check))
