"""G5.64 single replay qualification guards."""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "qualify_g564_llm_replay.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("g564_replay", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G564 = _load_script()


def test_semantic_key_is_type_sensitive_and_value_stable() -> None:
    value = {"kind": "text", "normalized": "opaque"}
    assert G564._semantic_key("PARTY_NAME", value) == (
        "PARTY_NAME",
        '{"kind": "text", "normalized": "opaque"}',
    )
    assert G564._semantic_key("PARTY_NAME", value) != G564._semantic_key(
        "ACCOUNT_IDENTIFIER",
        value,
    )


def test_qualification_is_offline_and_preserves_raw_output() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert "requests" not in imports
    assert not any(name.startswith("broker_reports_gate1.gate2_") for name in imports)
    assert '"provider_calls_during_qualification": 0' in source
    assert '"raw_output_repaired": False' in source
