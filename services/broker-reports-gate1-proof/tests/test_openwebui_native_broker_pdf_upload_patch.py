from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
PATCH_PATH = (
    ROOT
    / "deploy"
    / "openwebui-native-web-stt-patch"
    / "apply_native_broker_pdf_upload_patch.py"
)


def _module():
    spec = importlib.util.spec_from_file_location("native_broker_pdf_patch", PATCH_PATH)
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
    assert '["broker_reports_gate1_pipe","broker_reports_ndfl"].includes(M()[0])' in result
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


def test_dockerfile_applies_broker_patch_after_existing_native_patch():
    dockerfile = (
        ROOT / "deploy" / "openwebui-native-web-stt-patch" / "Dockerfile"
    ).read_text(encoding="utf-8")

    existing = dockerfile.index("RUN python /usr/local/bin/apply_native_web_stt_patch.py")
    broker = dockerfile.index(
        "RUN python /usr/local/bin/apply_native_broker_pdf_upload_patch.py"
    )
    assert existing < broker
