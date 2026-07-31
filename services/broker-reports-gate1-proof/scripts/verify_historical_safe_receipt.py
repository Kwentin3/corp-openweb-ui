#!/usr/bin/env python3
"""Verify immutable safe-receipt hashes against their historical Git tree."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


_GIT_OBJECT_ID = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class HistoricalReceiptVerificationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class HistoricalReceiptVerification:
    historical_source_commit: str
    historical_blobs_checked_total: int
    current_head_differences_total: int


def _fail(code: str) -> None:
    raise HistoricalReceiptVerificationError(code)


def _git(
    repo_root: Path,
    *args: str,
    failure_code: str,
) -> bytes:
    try:
        return subprocess.check_output(
            ["git", *args],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise HistoricalReceiptVerificationError(failure_code) from exc


def _repository_path(repo_root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        _fail("historical_receipt_path_outside_repository")
    normalized = PurePosixPath(relative.as_posix())
    if normalized.is_absolute() or ".." in normalized.parts:
        _fail("historical_receipt_path_invalid")
    return normalized.as_posix()


def _receipt_payload(receipt_bytes: bytes) -> dict[str, Any]:
    try:
        value = json.loads(receipt_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise HistoricalReceiptVerificationError(
            "historical_receipt_invalid"
        ) from exc
    if (
        not isinstance(value, dict)
        or value.get("hash_boundary") != "git_blob_bytes"
        or not _GIT_OBJECT_ID.fullmatch(str(value.get("base_revision", "")))
        or not isinstance(value.get("deliverables"), list)
        or not value["deliverables"]
    ):
        _fail("historical_receipt_invalid")
    for item in value["deliverables"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not item["path"]
            or PurePosixPath(item["path"]).is_absolute()
            or ".." in PurePosixPath(item["path"]).parts
            or not _SHA256.fullmatch(str(item.get("git_blob_sha256", "")))
        ):
            _fail("historical_receipt_invalid")
    return value


def _historical_source_commit(
    *,
    repo_root: Path,
    receipt_path: str,
    base_revision: str,
) -> str:
    _git(
        repo_root,
        "cat-file",
        "-e",
        f"{base_revision}^{{commit}}",
        failure_code="historical_source_commit_missing",
    )
    raw_candidates = _git(
        repo_root,
        "log",
        "--all",
        "--diff-filter=A",
        "--format=%H",
        "--",
        receipt_path,
        failure_code="historical_source_commit_missing",
    )
    candidates: list[str] = []
    for candidate in raw_candidates.decode("ascii").splitlines():
        if not _GIT_OBJECT_ID.fullmatch(candidate):
            continue
        revision = _git(
            repo_root,
            "rev-list",
            "--parents",
            "-n",
            "1",
            candidate,
            failure_code="historical_source_commit_missing",
        ).decode("ascii").strip().split()
        if base_revision in revision[1:]:
            candidates.append(candidate)
    if not candidates:
        _fail("historical_source_commit_missing")
    if len(candidates) != 1:
        _fail("historical_source_commit_ambiguous")
    return candidates[0]


def verify_historical_safe_receipt(
    *,
    repo_root: Path,
    receipt_path: Path,
) -> HistoricalReceiptVerification:
    repo_root = repo_root.resolve()
    receipt_repository_path = _repository_path(repo_root, receipt_path)
    try:
        current_receipt_bytes = receipt_path.read_bytes()
    except OSError as exc:
        raise HistoricalReceiptVerificationError(
            "historical_receipt_missing"
        ) from exc
    receipt = _receipt_payload(current_receipt_bytes)
    source_commit = _historical_source_commit(
        repo_root=repo_root,
        receipt_path=receipt_repository_path,
        base_revision=receipt["base_revision"],
    )
    historical_receipt_object = _git(
        repo_root,
        "rev-parse",
        f"{source_commit}:{receipt_repository_path}",
        failure_code="historical_receipt_blob_missing",
    ).decode("ascii").strip()
    current_receipt_object = _git(
        repo_root,
        "hash-object",
        f"--path={receipt_repository_path}",
        receipt_repository_path,
        failure_code="historical_receipt_missing",
    ).decode("ascii").strip()
    if historical_receipt_object != current_receipt_object:
        _fail("historical_receipt_changed")

    current_differences = 0
    for deliverable in receipt["deliverables"]:
        repository_path = PurePosixPath(deliverable["path"]).as_posix()
        blob = _git(
            repo_root,
            "show",
            f"{source_commit}:{repository_path}",
            failure_code="historical_deliverable_blob_missing",
        )
        if hashlib.sha256(blob).hexdigest() != deliverable[
            "git_blob_sha256"
        ]:
            _fail("historical_deliverable_blob_hash_mismatch")
        try:
            current_blob = _git(
                repo_root,
                "show",
                f"HEAD:{repository_path}",
                failure_code="historical_current_blob_missing",
            )
        except HistoricalReceiptVerificationError:
            current_differences += 1
        else:
            current_differences += int(current_blob != blob)

    return HistoricalReceiptVerification(
        historical_source_commit=source_commit,
        historical_blobs_checked_total=len(receipt["deliverables"]),
        current_head_differences_total=current_differences,
    )
