#!/usr/bin/env python3
"""Host half of the native ordinary-trade Prompt release boundary.

This small adapter moves an exact repository archive into the running
OpenWebUI container and invokes the container-side native owner adapter.  It
does not open a database or mutate a Prompt itself.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


CONTAINER = "openwebui"
SAFE_SCHEMA_VERSION = "broker_reports_native_mapping_prompt_pin_v1"
SAFE_NAME_RE = re.compile(r"^broker-reports-[0-9a-f]{12}$")
SAFE_PIN_KEYS = {"prompt_ref", "prompt_command", "prompt_history_id", "prompt_hash"}
_PROFILE_IDS = frozenset(
    {"ordinary_trade_mapping_v13", "goal391_grouped_mapping_lab_v14"}
)


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )


def _staging_dir(value: str) -> Path:
    root = Path("/opt/openwebui-prd0/.broker-reports-release-staging").resolve()
    candidate = Path(value).resolve()
    if candidate.parent != root or not SAFE_NAME_RE.fullmatch(candidate.name):
        raise RuntimeError("ordinary_trade_mapping_prompt_release_staging_invalid")
    return candidate


def _validate_output(value: str, *, status: str) -> dict[str, str]:
    try:
        parsed = json.loads(value)
    except ValueError as exc:
        raise RuntimeError("ordinary_trade_mapping_prompt_release_receipt_invalid") from exc
    if (
        not isinstance(parsed, dict)
        or parsed.get("schema_version") != SAFE_SCHEMA_VERSION
        or parsed.get("status") != status
        or not SAFE_PIN_KEYS <= set(parsed)
        or any(not isinstance(parsed[key], str) or not parsed[key] for key in SAFE_PIN_KEYS)
    ):
        raise RuntimeError("ordinary_trade_mapping_prompt_release_receipt_invalid")
    return {key: parsed[key] for key in sorted(SAFE_PIN_KEYS)}


def execute(
    *,
    staging_dir: Path,
    verify_pin: dict[str, str] | None,
    profile: str = "ordinary_trade_mapping_v13",
) -> dict[str, str]:
    if profile not in _PROFILE_IDS:
        raise RuntimeError("ordinary_trade_mapping_prompt_release_profile_invalid")
    archive = staging_dir / "ordinary_trade_mapping_prompt_source.zip"
    runner = staging_dir / "broker_reports_native_prompt_publish_container.py"
    if not archive.is_file() or archive.is_symlink() or not runner.is_file() or runner.is_symlink():
        raise RuntimeError("ordinary_trade_mapping_prompt_release_payload_missing")
    container_dir = "/tmp/broker-reports-prompt-release"
    archive_in_container = container_dir + "/source.zip"
    runner_in_container = container_dir + "/publish.py"
    _run(["docker", "exec", CONTAINER, "mkdir", "-p", container_dir])
    try:
        _run(["docker", "cp", str(archive), f"{CONTAINER}:{archive_in_container}"])
        _run(["docker", "cp", str(runner), f"{CONTAINER}:{runner_in_container}"])
        command = [
            "docker", "exec", "-w", "/app/backend", "-e", "PYTHONPATH=/app/backend", CONTAINER, "python",
            runner_in_container, "--source-archive", archive_in_container, "--profile", profile,
        ]
        expected_status = "published"
        if verify_pin is not None:
            command.extend(["--verify-pin-json", json.dumps(verify_pin, sort_keys=True)])
            expected_status = "verified"
        completed = _run(command, check=False)
        if completed.returncode != 0:
            raise RuntimeError("ordinary_trade_mapping_prompt_release_native_failed")
        return _validate_output(completed.stdout, status=expected_status)
    finally:
        _run(["docker", "exec", CONTAINER, "rm", "-rf", container_dir], check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-dir", required=True)
    parser.add_argument("--verify-pin-json", default=None)
    parser.add_argument(
        "--profile", choices=sorted(_PROFILE_IDS), default="ordinary_trade_mapping_v13"
    )
    args = parser.parse_args()
    verify_pin = None
    if args.verify_pin_json is not None:
        value = json.loads(args.verify_pin_json)
        if not isinstance(value, dict) or set(value) != SAFE_PIN_KEYS:
            raise RuntimeError("ordinary_trade_mapping_prompt_release_pin_invalid")
        verify_pin = {key: str(value[key]) for key in sorted(SAFE_PIN_KEYS)}
    print(json.dumps(execute(staging_dir=_staging_dir(args.staging_dir), verify_pin=verify_pin, profile=args.profile), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"status": "error", "code": str(exc)[:200]}, sort_keys=True))
        raise
