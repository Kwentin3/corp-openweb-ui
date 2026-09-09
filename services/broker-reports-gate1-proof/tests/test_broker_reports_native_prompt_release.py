from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "services" / "broker-reports-gate1-proof" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import broker_reports_native_prompt_publish_host as host  # noqa: E402
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
    assert any(
        call[:9] == ["docker", "exec", "-w", "/app/backend", "-e", "PYTHONPATH=/app/backend", "openwebui", "python", "/tmp/broker-reports-prompt-release/publish.py"]
        for call in calls
    )


def test_release_pin_is_complete_before_it_is_projected_into_pipe_valves():
    assert release._mapping_prompt_valves(_PIN) == {
        "ordinary_trade_mapping_prompt_id": "prompt-1",
        "ordinary_trade_mapping_prompt_command": "broker_ordinary_trade_semantic_mapping_v1",
        "ordinary_trade_mapping_prompt_version": "history-1",
        "ordinary_trade_mapping_prompt_hash": "a" * 64,
    }
    with pytest.raises(release.StageReleaseDriverError, match="publication_receipt_invalid"):
        release._mapping_prompt_valves({key: value for key, value in _PIN.items() if key != "prompt_hash"})


@pytest.mark.parametrize(
    "profile",
    ["goal391_grouped_mapping_lab_v14", "ordinary_trade_mapping_v14"],
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
    assert '"ordinary_trade_mapping_v14"' in container_source
