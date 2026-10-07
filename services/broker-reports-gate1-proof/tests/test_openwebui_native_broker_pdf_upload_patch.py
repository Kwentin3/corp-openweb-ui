from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
PATCH_PATH = (
    ROOT
    / "deploy"
    / "openwebui-patches"
    / "apply_native_broker_pdf_upload_patch.py"
)
TERMINAL_PATCH_PATH = (
    ROOT
    / "deploy"
    / "openwebui-patches"
    / "apply_terminal_proxy_security_patch.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("native_broker_pdf_patch", PATCH_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _terminal_module():
    spec = importlib.util.spec_from_file_location(
        "terminal_proxy_security_patch", TERMINAL_PATCH_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_patch_moves_exact_broker_pdf_default_to_native_process_false(tmp_path: Path):
    patch = _module()
    chunk = tmp_path / "chat.js"
    chunk.write_text(f"before;{patch.OLD}after", encoding="utf-8")

    assert patch.patch_file(chunk, dry_run=False) == "patched"

    result = chunk.read_text(encoding="utf-8")
    assert result.count(patch.NEW) == 1
    assert '["broker_reports_gate1_pipe","broker-reports-ndfl"].includes(M()[0])' in result
    assert 'De.type==="application/pdf"' in result
    assert 'String(De.name||"").toLowerCase().endsWith(".pdf")' in result
    assert "&&(st=!1);" in result


def test_patch_is_idempotent_for_the_pinned_chunk(tmp_path: Path):
    patch = _module()
    chunk = tmp_path / "chat.js"
    chunk.write_text(f"before;{patch.NEW}after", encoding="utf-8")

    assert patch.patch_file(chunk, dry_run=False) == "already_patched"
    assert chunk.read_text(encoding="utf-8").count(patch.NEW) == 1


def test_patch_rejects_ambiguous_pinned_signatures(tmp_path: Path):
    patch = _module()
    chunk = tmp_path / "chat.js"
    chunk.write_text(f"{patch.OLD}{patch.OLD}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="unexpected patch signature counts"):
        patch.patch_file(chunk, dry_run=False)


def test_dockerfile_applies_broker_patch_without_the_retired_web_stt_patch():
    dockerfile = (ROOT / "deploy" / "openwebui-patches" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "RUN python /usr/local/bin/apply_native_broker_pdf_upload_patch.py" in dockerfile
    assert "RUN python /usr/local/bin/apply_terminal_proxy_security_patch.py" in dockerfile
    assert "apply_native_web_stt_patch.py" not in dockerfile


def test_terminal_patch_quotes_and_rejects_ambiguous_session_path_values():
    patch = _terminal_module()
    source = "async def route(ws, policy_id, ws_base, session_id):\n" + patch.OLD

    result, status = patch.patch_source(source)

    assert status == "patched"
    assert "safe_session_id = urllib.parse.quote(session_id, safe='')" in result
    assert "{safe_session_id}" in result
    assert "{session_id}" not in result
    assert "forbidden = '?#&/%\\\\'" in result
    assert "any(ord(char) < 32 or ord(char) == 127" in result
    compile(result, "terminals.py", "exec")


def test_terminal_patch_is_idempotent_and_fails_on_source_drift():
    patch = _terminal_module()
    source = "async def route(ws, policy_id, ws_base, session_id):\n" + patch.OLD
    once, assert_status = patch.patch_source(source)
    assert assert_status == "patched"

    twice, status = patch.patch_source(once)
    assert status == "already_patched"
    assert twice == once

    with pytest.raises(RuntimeError, match="signature counts"):
        patch.patch_source(source.replace("if policy_id:", "if bool(policy_id):"))
