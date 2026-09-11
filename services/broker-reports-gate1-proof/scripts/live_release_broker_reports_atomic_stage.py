#!/usr/bin/env python3
"""Validate or apply one atomic Broker Reports stage release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[2]
SERVICE_ROOT = ROOT / "services" / "broker-reports-gate1-proof"
REMOTE_SCRIPT = SCRIPT_DIR / "broker_reports_atomic_stage_remote.py"
PROMPT_HOST_SCRIPT = SCRIPT_DIR / "broker_reports_native_prompt_publish_host.py"
PROMPT_CONTAINER_SCRIPT = SCRIPT_DIR / "broker_reports_native_prompt_publish_container.py"
PROMPT_ARCHIVE_NAME = "ordinary_trade_mapping_prompt_source.zip"
PROMPT_PIN_KEYS = {
    "prompt_ref",
    "prompt_command",
    "prompt_history_id",
    "prompt_hash",
}
ORDINARY_TRADE_MAPPING_PRODUCTION_PROFILE = "ordinary_trade_mapping_v16"
ORDINARY_TRADE_MAPPING_PRODUCTION_ASSET = (
    "services/broker-reports-gate1-proof/managed_assets/prompts/"
    "broker_reports_ordinary_trade_mapping_prompt.v16.md"
)
PDF_TABLE_CONTINUATION_ANNOTATION_PRODUCTION_PROFILE = (
    "pdf_table_continuation_annotation_v3"
)

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_atomic_stage_release_contracts import (  # noqa: E402
    FUNCTION_CONTRACTS,
    LOADER_PATH,
    build_manifest,
    provider_policy_manifest,
    release_id,
    validate_manifest,
)
from broker_reports_release_source import (  # noqa: E402
    LOADER_REPOSITORY_PATH,
    git_blob_bytes,
)
from broker_reports_gate1 import GATE2_PROVIDER_PROFILES  # noqa: E402
from broker_reports_gate1.pdf_table_continuation_annotation_prompt import (  # noqa: E402
    PROMPT_COMMAND as PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_COMMAND,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _default_ssh_target,
    _read_env,
)
from live_verify_broker_reports_stage2_delivery import (  # noqa: E402
    expected_prompt_contracts,
)


class StageReleaseDriverError(RuntimeError):
    pass


SAFE_REMOTE_ERROR_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")


def _run(
    args: list[str],
    *,
    cwd: Path = ROOT,
    check: bool = True,
    timeout: int = 180,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        input=input_text,
    )


def _git_revision() -> str:
    return _run(["git", "rev-parse", "HEAD"]).stdout.strip()


def _assert_release_tree(source_revision: str) -> dict[str, Any]:
    if _git_revision() != source_revision:
        raise StageReleaseDriverError("stage_release_git_revision_mismatch")
    status = _run(["git", "status", "--porcelain=v1"]).stdout
    if status.strip():
        raise StageReleaseDriverError("stage_release_git_tree_not_clean")
    ancestor = _run(
        ["git", "merge-base", "--is-ancestor", "origin/main", source_revision],
        check=False,
    )
    if ancestor.returncode != 0:
        raise StageReleaseDriverError("stage_release_origin_main_not_ancestor")
    ahead = int(
        _run(
            ["git", "rev-list", "--count", f"origin/main..{source_revision}"]
        ).stdout.strip()
    )
    return {
        "head_matches_source_revision": True,
        "worktree_clean": True,
        "origin_main_is_ancestor": True,
        "commits_ahead_of_origin_main": ahead,
    }


def _ssh_prefix(ssh_target: str) -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=yes",
        ssh_target,
    ]


def _scp_prefix() -> list[str]:
    return [
        "scp",
        "-q",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "StrictHostKeyChecking=yes",
    ]


def _prepare_remote_staging(ssh_target: str, release_name: str) -> str:
    remote_dir = "/opt/openwebui-prd0/.broker-reports-release-staging/" + release_name
    code = (
        "import os,pathlib,re;"
        f"p=pathlib.Path({remote_dir!r});"
        "root=pathlib.Path('/opt/openwebui-prd0/.broker-reports-release-staging');"
        "assert p.parent==root and re.fullmatch(r'broker-reports-[0-9a-f]{12}',p.name);"
        "root.mkdir(mode=0o700,parents=True,exist_ok=True);"
        "p.mkdir(mode=0o700,exist_ok=False);"
        "os.chmod(root,0o700);os.chmod(p,0o700)"
    )
    _run(
        [*_ssh_prefix(ssh_target), "python3", "-"],
        timeout=60,
        input_text=code,
    )
    return remote_dir


def _cleanup_remote_staging(ssh_target: str, remote_dir: str) -> None:
    code = (
        "import pathlib,re,shutil;"
        f"p=pathlib.Path({remote_dir!r});"
        "root=pathlib.Path('/opt/openwebui-prd0/.broker-reports-release-staging');"
        "assert p.parent==root and re.fullmatch(r'broker-reports-[0-9a-f]{12}',p.name);"
        "shutil.rmtree(p) if p.exists() else None"
    )
    _run(
        [*_ssh_prefix(ssh_target), "python3", "-"],
        check=False,
        timeout=60,
        input_text=code,
    )


def _copy_payload(
    *,
    ssh_target: str,
    remote_dir: str,
    manifest_path: Path,
    loader_payload_path: Path,
) -> None:
    paths = [
        manifest_path,
        REMOTE_SCRIPT,
        loader_payload_path,
        *(contract.bundle_path for contract in FUNCTION_CONTRACTS),
    ]
    for path in paths:
        if not path.is_file():
            raise StageReleaseDriverError("stage_release_payload_file_missing")
    destination = f"{ssh_target}:{remote_dir}/"
    _run(
        [*_scp_prefix(), *(str(path) for path in paths), destination],
        timeout=240,
    )


def _write_prompt_source_archive(*, source_revision: str, destination: Path) -> None:
    """Archive only release-owned source, directly from the approved Git tree."""
    paths = (
        "services/broker-reports-gate1-proof/broker_reports_gate1",
        ORDINARY_TRADE_MAPPING_PRODUCTION_ASSET,
    )
    _run(
        [
            "git",
            "archive",
            "--format=zip",
            f"--output={destination}",
            source_revision,
            *paths,
        ],
        timeout=120,
    )
    if not destination.is_file() or destination.is_symlink():
        raise StageReleaseDriverError("stage_release_prompt_source_archive_missing")
    try:
        with zipfile.ZipFile(destination) as archive:
            names = set(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise StageReleaseDriverError("stage_release_prompt_source_archive_invalid") from exc
    required = {
        "services/broker-reports-gate1-proof/broker_reports_gate1/"
        "ordinary_trade_mapping_prompt_publication.py",
        ORDINARY_TRADE_MAPPING_PRODUCTION_ASSET,
    }
    if not required <= names:
        raise StageReleaseDriverError("stage_release_prompt_source_archive_invalid")


def _copy_prompt_publication_payload(
    *, ssh_target: str, remote_dir: str, source_archive: Path
) -> None:
    paths = (source_archive, PROMPT_HOST_SCRIPT, PROMPT_CONTAINER_SCRIPT)
    if any(not path.is_file() for path in paths):
        raise StageReleaseDriverError("stage_release_prompt_publication_payload_missing")
    _run(
        [*_scp_prefix(), *(str(path) for path in paths), f"{ssh_target}:{remote_dir}/"],
        timeout=240,
    )


def _validated_prompt_pin(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != PROMPT_PIN_KEYS or any(
        not isinstance(value.get(key), str) or not value[key] for key in PROMPT_PIN_KEYS
    ):
        raise StageReleaseDriverError("stage_release_prompt_publication_receipt_invalid")
    return {key: value[key] for key in sorted(PROMPT_PIN_KEYS)}


def _run_native_prompt_publication(
    *, ssh_target: str, remote_dir: str, verify_pin: Mapping[str, str] | None
) -> dict[str, str]:
    command = [
        *_ssh_prefix(ssh_target),
        "python3",
        f"{remote_dir}/{PROMPT_HOST_SCRIPT.name}",
        "--staging-dir",
        remote_dir,
        "--profile",
        ORDINARY_TRADE_MAPPING_PRODUCTION_PROFILE,
    ]
    if verify_pin is not None:
        # ssh joins trailing argv items into a remote POSIX shell command.  Quote
        # JSON explicitly so Windows OpenSSH cannot split it at spaces/quotes.
        command.extend(
            [
                "--verify-pin-json",
                shlex.quote(json.dumps(dict(verify_pin), sort_keys=True)),
            ]
        )
    completed = _run(command, check=False, timeout=300)
    if completed.returncode != 0:
        raise StageReleaseDriverError("stage_release_prompt_publication_failed")
    try:
        value = json.loads(completed.stdout)
    except ValueError as exc:
        raise StageReleaseDriverError("stage_release_prompt_publication_receipt_invalid") from exc
    return _validated_prompt_pin(value)


def _verify_native_prompt_publication_after_remote_release(
    *,
    ssh_target: str,
    source_revision: str,
    source_archive: Path,
    expected_pin: Mapping[str, str],
) -> dict[str, str]:
    """Read back the native Prompt after the remote transaction cleaned its staging."""
    verification_release_name = "broker-reports-" + hashlib.sha256(
        ("prompt-verify:" + source_revision).encode("ascii")
    ).hexdigest()[:12]
    verification_dir = _prepare_remote_staging(ssh_target, verification_release_name)
    try:
        _copy_prompt_publication_payload(
            ssh_target=ssh_target,
            remote_dir=verification_dir,
            source_archive=source_archive,
        )
        verification = _run_native_prompt_publication(
            ssh_target=ssh_target,
            remote_dir=verification_dir,
            verify_pin=expected_pin,
        )
        if verification != _validated_prompt_pin(dict(expected_pin)):
            raise StageReleaseDriverError("stage_release_prompt_publication_pin_drift")
        return verification
    finally:
        _cleanup_remote_staging(ssh_target, verification_dir)


def _mapping_prompt_valves(pin: Mapping[str, str]) -> dict[str, str]:
    value = _validated_prompt_pin(dict(pin))
    return {
        "ordinary_trade_mapping_profile_id": ORDINARY_TRADE_MAPPING_PRODUCTION_PROFILE,
        "ordinary_trade_mapping_prompt_id": value["prompt_ref"],
        "ordinary_trade_mapping_prompt_command": value["prompt_command"],
        "ordinary_trade_mapping_prompt_version": value["prompt_history_id"],
        "ordinary_trade_mapping_prompt_hash": value["prompt_hash"],
    }


def _pdf_table_continuation_annotation_prompt_valves(
    pin: Mapping[str, str],
) -> dict[str, str]:
    """Project a native history pin; activation remains an explicit Valve."""

    value = _validated_prompt_pin(dict(pin))
    if value["prompt_command"] != PDF_TABLE_CONTINUATION_ANNOTATION_PROMPT_COMMAND:
        raise StageReleaseDriverError(
            "stage_release_pdf_table_continuation_prompt_command_invalid"
        )
    return {
        "pdf_table_continuation_annotation_prompt_id": value["prompt_ref"],
        "pdf_table_continuation_annotation_prompt_command": value["prompt_command"],
        "pdf_table_continuation_annotation_prompt_version": value["prompt_history_id"],
        "pdf_table_continuation_annotation_prompt_hash": value["prompt_hash"],
    }


def _run_remote_release(
    *,
    ssh_target: str,
    remote_dir: str,
    apply: bool,
    prove_rollback: bool,
) -> dict[str, Any]:
    command = [
        *_ssh_prefix(ssh_target),
        "python3",
        f"{remote_dir}/{REMOTE_SCRIPT.name}",
        "--staging-dir",
        remote_dir,
    ]
    if apply:
        command.append("--apply")
    if prove_rollback:
        command.append("--prove-rollback")
    completed = _run(command, check=False, timeout=900)
    return _validated_remote_receipt(completed, apply=apply)


def _validated_remote_receipt(
    completed: subprocess.CompletedProcess[str],
    *,
    apply: bool,
) -> dict[str, Any]:
    try:
        value = json.loads(completed.stdout)
    except ValueError as exc:
        raise StageReleaseDriverError("stage_release_remote_receipt_invalid") from exc
    if not isinstance(value, dict):
        raise StageReleaseDriverError("stage_release_remote_receipt_invalid")
    if completed.returncode != 0:
        remote_code = str(value.get("code") or "")
        if not SAFE_REMOTE_ERROR_RE.fullmatch(remote_code):
            remote_code = "stage_release_remote_error_unclassified"
        raise StageReleaseDriverError("stage_release_remote_failed:" + remote_code)
    expected_status = "passed" if apply else "validated"
    if value.get("status") != expected_status:
        raise StageReleaseDriverError("stage_release_remote_status_invalid")
    return value


def execute(
    *,
    source_revision: str,
    ssh_target: str,
    apply: bool,
    prove_rollback: bool,
    ordinary_trade_mapping_prompt_pin: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if prove_rollback and not apply:
        raise StageReleaseDriverError("stage_release_rollback_proof_requires_apply")
    local_checks = _assert_release_tree(source_revision)
    loader_bytes = git_blob_bytes(
        root=ROOT,
        source_revision=source_revision,
        repository_path=LOADER_REPOSITORY_PATH,
    )
    supplied_prompt_pin = (
        _validated_prompt_pin(dict(ordinary_trade_mapping_prompt_pin))
        if ordinary_trade_mapping_prompt_pin is not None
        else None
    )
    if not apply and supplied_prompt_pin is None:
        # Validation must not silently turn into a production Prompt mutation.
        # A caller can still perform a no-write release validation against an
        # already native-attested pin.
        raise StageReleaseDriverError("stage_release_prompt_publication_required")
    release_name = release_id(source_revision)
    remote_dir: str | None = None
    with tempfile.TemporaryDirectory(prefix="broker-reports-stage-release-") as temp:
        remote_dir = _prepare_remote_staging(ssh_target, release_name)
        prompt_source_archive: Path | None = None
        try:
            if apply:
                prompt_source_archive = Path(temp) / PROMPT_ARCHIVE_NAME
                _write_prompt_source_archive(
                    source_revision=source_revision,
                    destination=prompt_source_archive,
                )
                _copy_prompt_publication_payload(
                    ssh_target=ssh_target,
                    remote_dir=remote_dir,
                    source_archive=prompt_source_archive,
                )
                prompt_pin = _run_native_prompt_publication(
                    ssh_target=ssh_target,
                    remote_dir=remote_dir,
                    verify_pin=None,
                )
            else:
                prompt_pin = supplied_prompt_pin
                assert prompt_pin is not None
            manifest = build_manifest(
                source_revision=source_revision,
                prompt_contracts=expected_prompt_contracts(),
                provider_policy=provider_policy_manifest(GATE2_PROVIDER_PROFILES),
                loader_bytes=loader_bytes,
                function_valve_overrides={
                    "broker_reports_gate1_pipe": _mapping_prompt_valves(prompt_pin)
                },
            )
            validate_manifest(manifest)
            manifest_path = Path(temp) / "manifest.json"
            loader_payload_path = Path(temp) / LOADER_PATH.name
            loader_payload_path.write_bytes(loader_bytes)
            manifest_path.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            _copy_payload(
                ssh_target=ssh_target,
                remote_dir=remote_dir,
                manifest_path=manifest_path,
                loader_payload_path=loader_payload_path,
            )
            receipt = _run_remote_release(
                ssh_target=ssh_target,
                remote_dir=remote_dir,
                apply=apply,
                prove_rollback=prove_rollback,
            )
            if apply:
                assert prompt_source_archive is not None
                prompt_verification = _verify_native_prompt_publication_after_remote_release(
                    ssh_target=ssh_target,
                    source_revision=source_revision,
                    source_archive=prompt_source_archive,
                    expected_pin=prompt_pin,
                )
                receipt["ordinary_trade_mapping_prompt"] = {
                    "pin": prompt_verification,
                    "history_binding_attested": True,
                }
            remote_dir = None
        finally:
            if remote_dir is not None:
                _cleanup_remote_staging(ssh_target, remote_dir)
    receipt["local_release_checks"] = local_checks
    receipt["manifest"] = {
        "schema_version": manifest["schema_version"],
        "release_id": manifest["release_id"],
        "source_revision": manifest["source_revision"],
        "manifest_sha256": manifest["manifest_sha256"],
        "function_sha256": {
            item["function_id"]: item["content_sha256"]
            for item in manifest["functions"]
        },
        "loader_sha256": manifest["loader"]["content_sha256"],
        "prompt_sha256": {
            item["prompt_id"]: item["content_sha256"]
            for item in manifest["managed_prompts"]
        },
    }
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(ROOT / ".env"))
    parser.add_argument("--ssh-target", default=None)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--prove-rollback", action="store_true")
    parser.add_argument("--ordinary-trade-mapping-prompt-pin-json", default=None)
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    ssh_target = (
        args.ssh_target or env.get("OPENWEBUI_SSH_TARGET") or _default_ssh_target(env)
    )
    receipt = execute(
        source_revision=args.source_revision,
        ssh_target=ssh_target,
        apply=bool(args.apply),
        prove_rollback=bool(args.prove_rollback),
        ordinary_trade_mapping_prompt_pin=(
            json.loads(args.ordinary_trade_mapping_prompt_pin_json)
            if args.ordinary_trade_mapping_prompt_pin_json is not None
            else None
        ),
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "code": str(exc)[:200],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise
