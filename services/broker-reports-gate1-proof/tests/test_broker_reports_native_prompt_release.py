from __future__ import annotations

import json
import shlex
import subprocess
import sys
import zipfile
from pathlib import Path
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "services" / "broker-reports-gate1-proof" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import broker_reports_native_prompt_publish_host as host  # noqa: E402
import broker_reports_native_prompt_publish_container as container  # noqa: E402
import live_release_broker_reports_atomic_stage as release  # noqa: E402


_PIN = {
    "prompt_ref": "prompt-1",
    "prompt_command": "broker_ordinary_trade_semantic_mapping_v1",
    "prompt_history_id": "history-1",
    "prompt_hash": "a" * 64,
}


def test_host_uses_container_native_runner_and_returns_only_safe_pin(tmp_path: Path):
    archive = tmp_path / "ordinary_trade_mapping_prompt_source.zip"
    runner = tmp_path / "broker_reports_native_prompt_publish_container.py"
    archive.write_bytes(b"release-source")
    runner.write_text("# runner", encoding="utf-8")
    calls: list[list[str]] = []

    def run(args, *, check=True):
        calls.append(args)
        if "python" in args:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps(
                    {
                        "schema_version": host.SAFE_SCHEMA_VERSION,
                        "status": "published",
                        "action": "updated",
                        **_PIN,
                    }
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with mock.patch.object(host, "_run", side_effect=run):
        result = host.execute(staging_dir=tmp_path, verify_pin=None)

    assert result == _PIN
    assert any(call[:2] == ["docker", "cp"] for call in calls)
    python_call = next(call for call in calls if "python" in call)
    assert python_call[:9] == [
        "docker", "exec", "-w", "/app/backend", "-e", "PYTHONPATH=/app/backend",
        "openwebui", "python", "/tmp/broker-reports-prompt-release/publish.py",
    ]
    assert python_call[-2:] == ["--profile", "ordinary_trade_mapping_v15"]


def test_release_pin_is_complete_before_it_is_projected_into_pipe_valves():
    assert release._mapping_prompt_valves(_PIN) == {
        "ordinary_trade_mapping_profile_id": "ordinary_trade_mapping_v15",
        "ordinary_trade_mapping_prompt_id": "prompt-1",
        "ordinary_trade_mapping_prompt_command": "broker_ordinary_trade_semantic_mapping_v1",
        "ordinary_trade_mapping_prompt_version": "history-1",
        "ordinary_trade_mapping_prompt_hash": "a" * 64,
    }
    with pytest.raises(release.StageReleaseDriverError, match="publication_receipt_invalid"):
        release._mapping_prompt_valves({key: value for key, value in _PIN.items() if key != "prompt_hash"})


def test_physical_table_prompt_pin_projects_only_its_four_release_valves():
    pin = {**_PIN, "prompt_command": "broker_pdf_table_continuation_annotation_v3"}

    assert release._pdf_table_continuation_annotation_prompt_valves(pin) == {
        "pdf_table_continuation_annotation_prompt_id": "prompt-1",
        "pdf_table_continuation_annotation_prompt_command": (
            "broker_pdf_table_continuation_annotation_v3"
        ),
        "pdf_table_continuation_annotation_prompt_version": "history-1",
        "pdf_table_continuation_annotation_prompt_hash": "a" * 64,
    }
    with pytest.raises(
        release.StageReleaseDriverError,
        match="pdf_table_continuation_prompt_command_invalid",
    ):
        release._pdf_table_continuation_annotation_prompt_valves(_PIN)


def test_atomic_release_publishes_and_rechecks_the_production_v15_profile():
    calls: list[list[str]] = []

    def run(args, *, check=True, timeout=None):
        calls.append(args)
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps(_PIN),
            stderr="",
        )

    with mock.patch.object(release, "_run", side_effect=run):
        assert release._run_native_prompt_publication(
            ssh_target="release-host",
            remote_dir="/safe/staging",
            verify_pin=None,
        ) == _PIN

    assert len(calls) == 1
    assert calls[0][-4:] == [
        "--staging-dir",
        "/safe/staging",
        "--profile",
        "ordinary_trade_mapping_v15",
    ]


def test_prompt_readback_keeps_json_pin_as_one_remote_shell_argument():
    calls: list[list[str]] = []

    def run(args, *, check=True, timeout=None):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(_PIN), stderr="")

    with mock.patch.object(release, "_run", side_effect=run):
        assert release._run_native_prompt_publication(
            ssh_target="release-host",
            remote_dir="/safe/staging",
            verify_pin=_PIN,
        ) == _PIN

    assert calls[0][-2:] == [
        "--verify-pin-json",
        shlex.quote(json.dumps(_PIN, sort_keys=True)),
    ]


def test_atomic_release_archives_the_same_v15_prompt_profile_it_pins(tmp_path: Path):
    archive = tmp_path / "source.zip"
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    release._write_prompt_source_archive(
        source_revision=revision,
        destination=archive,
    )

    with zipfile.ZipFile(archive) as payload:
        names = set(payload.namelist())
    assert release.ORDINARY_TRADE_MAPPING_PRODUCTION_ASSET in names
    assert not any(name.endswith("broker_reports_ordinary_trade_mapping_prompt.v13.md") for name in names)


def test_post_remote_prompt_readback_uses_fresh_staging_and_always_cleans_it(
    tmp_path: Path,
):
    archive = tmp_path / "source.zip"
    archive.write_bytes(b"prompt-source")
    events: list[tuple[str, str]] = []

    with (
        mock.patch.object(
            release,
            "_prepare_remote_staging",
            side_effect=lambda _target, _release: events.append(("prepare", _release)) or "/verify",
        ),
        mock.patch.object(
            release,
            "_copy_prompt_publication_payload",
            side_effect=lambda **kwargs: events.append(("copy", kwargs["remote_dir"])),
        ),
        mock.patch.object(
            release,
            "_run_native_prompt_publication",
            side_effect=lambda **kwargs: events.append(("verify", kwargs["remote_dir"])) or _PIN,
        ),
        mock.patch.object(
            release,
            "_cleanup_remote_staging",
            side_effect=lambda _target, remote_dir: events.append(("cleanup", remote_dir)),
        ),
    ):
        assert release._verify_native_prompt_publication_after_remote_release(
            ssh_target="release-host",
            source_revision="0123456789abcdef0123456789abcdef01234567",
            source_archive=archive,
            expected_pin=_PIN,
        ) == _PIN

    assert events == [
        (
            "prepare",
            "broker-reports-"
            + release.hashlib.sha256(
                b"prompt-verify:0123456789abcdef0123456789abcdef01234567"
            ).hexdigest()[:12],
        ),
        ("copy", "/verify"),
        ("verify", "/verify"),
        ("cleanup", "/verify"),
    ]


@pytest.mark.parametrize("failure_point", ["copy", "verify"])
def test_post_remote_prompt_readback_cleans_fresh_staging_after_failure(
    tmp_path: Path, failure_point: str
):
    archive = tmp_path / "source.zip"
    archive.write_bytes(b"prompt-source")
    events: list[tuple[str, str]] = []

    def fail_copy(**kwargs):
        events.append(("copy", kwargs["remote_dir"]))
        raise RuntimeError("copy_failed")

    def fail_verify(**kwargs):
        events.append(("verify", kwargs["remote_dir"]))
        raise RuntimeError("verify_failed")

    with (
        mock.patch.object(release, "_prepare_remote_staging", return_value="/verify"),
        mock.patch.object(
            release,
            "_copy_prompt_publication_payload",
            side_effect=(
                fail_copy
                if failure_point == "copy"
                else lambda **kwargs: events.append(("copy", kwargs["remote_dir"]))
            ),
        ),
        mock.patch.object(
            release,
            "_run_native_prompt_publication",
            side_effect=fail_verify if failure_point == "verify" else _PIN,
        ),
        mock.patch.object(
            release,
            "_cleanup_remote_staging",
            side_effect=lambda _target, remote_dir: events.append(("cleanup", remote_dir)),
        ),
    ):
        with pytest.raises(RuntimeError, match=f"{failure_point}_failed"):
            release._verify_native_prompt_publication_after_remote_release(
                ssh_target="release-host",
                source_revision="0123456789abcdef0123456789abcdef01234567",
                source_archive=archive,
                expected_pin=_PIN,
            )

    assert events[-1] == ("cleanup", "/verify")
    assert events.count(("cleanup", "/verify")) == 1


@pytest.mark.parametrize(
    "profile",
    [
        "goal391_grouped_mapping_lab_v14",
        "ordinary_trade_mapping_v14",
        "ordinary_trade_mapping_v15",
        "pdf_table_continuation_annotation_v3",
    ],
)
def test_host_profile_selector_is_closed_and_reaches_only_native_runner(
    tmp_path: Path, profile: str
):
    archive = tmp_path / "ordinary_trade_mapping_prompt_source.zip"
    runner = tmp_path / "broker_reports_native_prompt_publish_container.py"
    archive.write_bytes(b"release-source")
    runner.write_text("# runner", encoding="utf-8")
    calls: list[list[str]] = []

    def run(args, *, check=True):
        calls.append(args)
        if "python" in args:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=json.dumps(
                    {
                        "schema_version": host.SAFE_SCHEMA_VERSION,
                        "status": "published",
                        "action": "created",
                        **_PIN,
                    }
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with mock.patch.object(host, "_run", side_effect=run):
        host.execute(
            staging_dir=tmp_path,
            verify_pin=None,
            profile=profile,
        )
    python_call = next(call for call in calls if "python" in call)
    assert python_call[-2:] == ["--profile", profile]
    with pytest.raises(RuntimeError, match="profile_invalid"):
        host.execute(staging_dir=tmp_path, verify_pin=None, profile="untrusted")


def test_native_release_helpers_do_not_add_sqlite_or_http_prompt_mutation_path():
    for name in (
        "broker_reports_native_prompt_publish_container.py",
        "broker_reports_native_prompt_publish_host.py",
    ):
        source = (SCRIPTS / name).read_text(encoding="utf-8")
        assert "sqlite3" not in source
        assert "requests" not in source
    container_source = (
        SCRIPTS / "broker_reports_native_prompt_publish_container.py"
    ).read_text(encoding="utf-8")
    assert "OrdinaryTradeMappingPromptPublisher" in container_source
    assert "from open_webui.models.prompt_history" not in container_source
    assert '"ordinary_trade_mapping_v15"' in container_source
    assert "pdf_table_continuation_annotation_v3" in container._PROFILE_IDS
    assert "pdf_table_continuation_annotation_v3" in host._PROFILE_IDS
