"""Exact repository source objects for Broker Reports release tooling."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath


REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
LOADER_REPOSITORY_PATH = PurePosixPath("deploy/openwebui-static/loader.js")


def git_blob_bytes(
    *,
    root: Path,
    source_revision: str,
    repository_path: PurePosixPath,
) -> bytes:
    if not REVISION_RE.fullmatch(source_revision):
        raise ValueError("stage_release_source_revision_invalid")
    if (
        repository_path.is_absolute()
        or ".." in repository_path.parts
        or repository_path != LOADER_REPOSITORY_PATH
    ):
        raise ValueError("stage_release_source_path_invalid")
    completed = subprocess.run(
        [
            "git",
            "cat-file",
            "blob",
            f"{source_revision}:{repository_path.as_posix()}",
        ],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ValueError("stage_release_source_blob_missing")
    if not completed.stdout:
        raise ValueError("stage_release_source_blob_empty")
    return completed.stdout
