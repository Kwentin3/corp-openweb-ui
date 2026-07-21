from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path, PurePosixPath


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = SERVICE_ROOT.parents[1]
SAFE_OUTPUT_SUFFIXES = (".safe.json", ".report.md")
LOCAL_PATH_PATTERNS = (
    re.compile(r"(?i)(?:^|[\"'`\s(])(?:[a-z]:[\\/]+users[\\/]+|/home/|/users/)"),
    re.compile(r"(?i)(?:^|[\"'`\s(])local/stage2/"),
)


class RepositoryPrivacyGuardTest(unittest.TestCase):
    def test_current_index_contains_no_private_json(self) -> None:
        violations = [
            path
            for path in _tracked_paths()
            if path.name.lower().endswith((".private.json", ".private.sha256.json"))
        ]
        self.assertEqual(violations, [])

    def test_maintained_safe_outputs_contain_no_local_paths(self) -> None:
        violations: list[str] = []
        for tracked_path in _tracked_paths():
            if not _is_maintained_safe_output(tracked_path):
                continue
            disk_path = REPOSITORY_ROOT.joinpath(*tracked_path.parts)
            if not disk_path.is_file():
                continue
            content = disk_path.read_text(encoding="utf-8")
            for pattern in LOCAL_PATH_PATTERNS:
                if pattern.search(content):
                    violations.append(f"{tracked_path}:{pattern.pattern}")
        self.assertEqual(violations, [])


def _tracked_paths() -> tuple[PurePosixPath, ...]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
    )
    return tuple(
        PurePosixPath(raw.decode("utf-8"))
        for raw in completed.stdout.split(b"\0")
        if raw
    )


def _is_maintained_safe_output(path: PurePosixPath) -> bool:
    rendered = path.as_posix().lower()
    if not rendered.startswith("docs/"):
        return False
    if rendered.endswith(SAFE_OUTPUT_SUFFIXES):
        return True
    return rendered.startswith("docs/reports/") and rendered.endswith(".json")


if __name__ == "__main__":
    unittest.main()
