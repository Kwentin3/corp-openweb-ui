from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_historical_safe_receipt import (  # noqa: E402
    HistoricalReceiptVerificationError,
    verify_historical_safe_receipt,
)


RECEIPT_PATH = Path(
    "docs/reports/2026-07-26/"
    "BROKER_REPORTS_GATE2_DOMAIN_GOAL9_LOCAL_DOMAIN_PROOF."
    "receipt.safe.json"
)
DELIVERABLE_PATH = Path("docs/stage2/contracts/historical.md")


def _run(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=repo,
        text=True,
    ).strip()


def _commit_all(repo: Path, message: str) -> str:
    _run(repo, "add", ".")
    _run(repo, "commit", "-m", message)
    return _run(repo, "rev-parse", "HEAD")


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def _repository(tmp_path: Path, *, recorded_hash: str | None = None):
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(repo, "init")
    _run(repo, "config", "user.email", "test@example.invalid")
    _run(repo, "config", "user.name", "Historical Receipt Test")
    _write(repo / "README.md", "base\n")
    base = _commit_all(repo, "base")
    historical_bytes = b"historical contract\n"
    _write(
        repo / DELIVERABLE_PATH,
        historical_bytes.decode("utf-8"),
    )
    receipt = {
        "hash_boundary": "git_blob_bytes",
        "base_revision": base,
        "deliverables": [
            {
                "path": DELIVERABLE_PATH.as_posix(),
                "git_blob_sha256": (
                    recorded_hash
                    or hashlib.sha256(historical_bytes).hexdigest()
                ),
            }
        ],
    }
    _write(
        repo / RECEIPT_PATH,
        json.dumps(receipt, indent=2) + "\n",
    )
    source_commit = _commit_all(repo, "historical proof")
    return repo, source_commit


def _verify(repo: Path):
    return verify_historical_safe_receipt(
        repo_root=repo,
        receipt_path=repo / RECEIPT_PATH,
    )


def test_historical_blob_match_passes(tmp_path: Path) -> None:
    repo, source_commit = _repository(tmp_path)

    result = _verify(repo)

    assert result.historical_source_commit == source_commit
    assert result.historical_blobs_checked_total == 1
    assert result.current_head_differences_total == 0


def test_current_file_difference_does_not_invalidate_history(
    tmp_path: Path,
) -> None:
    repo, source_commit = _repository(tmp_path)
    _write(repo / DELIVERABLE_PATH, "current evolved contract\n")
    _commit_all(repo, "evolve current contract")

    result = _verify(repo)

    assert result.historical_source_commit == source_commit
    assert result.current_head_differences_total == 1


def test_historical_blob_hash_corruption_fails(tmp_path: Path) -> None:
    repo, _source_commit = _repository(
        tmp_path,
        recorded_hash="0" * 64,
    )

    with pytest.raises(
        HistoricalReceiptVerificationError,
        match="historical_deliverable_blob_hash_mismatch",
    ):
        _verify(repo)


def test_missing_historical_commit_fails_closed(tmp_path: Path) -> None:
    repo, _source_commit = _repository(tmp_path)
    receipt_path = repo / RECEIPT_PATH
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["base_revision"] = "f" * 40
    _write(receipt_path, json.dumps(receipt, indent=2) + "\n")

    with pytest.raises(
        HistoricalReceiptVerificationError,
        match="historical_source_commit_missing",
    ):
        _verify(repo)


def test_changed_historical_receipt_fails(tmp_path: Path) -> None:
    repo, _source_commit = _repository(tmp_path)
    receipt_path = repo / RECEIPT_PATH
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["status"] = "tampered"
    _write(receipt_path, json.dumps(receipt, indent=2) + "\n")

    with pytest.raises(
        HistoricalReceiptVerificationError,
        match="historical_receipt_changed",
    ):
        _verify(repo)


def test_current_head_equality_is_not_required(tmp_path: Path) -> None:
    repo, _source_commit = _repository(tmp_path)
    (repo / DELIVERABLE_PATH).unlink()
    _commit_all(repo, "remove current contract")

    result = _verify(repo)

    assert result.current_head_differences_total == 1
