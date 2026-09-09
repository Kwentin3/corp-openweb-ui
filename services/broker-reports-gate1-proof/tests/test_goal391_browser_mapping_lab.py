from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import qualify_goal391_browser_mapping_lab as lab  # noqa: E402


def test_browser_bridge_decodes_utf8_response_explicitly(monkeypatch) -> None:
    def fake_run(*_args, **kwargs):
        assert kwargs["encoding"] == "utf-8"
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {"ok": True, "value": {"text": "Пример — «данные»"}},
                ensure_ascii=False,
            ),
        )

    monkeypatch.setattr(lab.subprocess, "run", fake_run)

    value = lab.Bridge(Path("bridge.mjs")).call({"op": "preflight"})

    assert value == {"text": "Пример — «данные»"}
