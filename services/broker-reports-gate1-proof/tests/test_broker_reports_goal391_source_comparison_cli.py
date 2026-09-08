from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "goal391_source_comparison_export.py"


def _script_module():
    spec = importlib.util.spec_from_file_location("goal391_source_comparison_cli", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mapping_scopes_are_explicit_and_private_input_only(tmp_path: Path) -> None:
    module = _script_module()
    path = tmp_path / "scopes.private.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": module.MAPPING_SCOPES_SCHEMA_VERSION,
                "scopes": [
                    {
                        "slot_id": "slot-1",
                        "target_table_node_ids": ["table-1"],
                        "confirmed_understandings": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    scopes = module._load_mapping_scopes(path)

    assert [(item.slot_id, item.target_table_node_ids) for item in scopes] == [
        ("slot-1", ("table-1",))
    ]


def test_mapping_scopes_reject_duplicate_slots_and_table_ids(tmp_path: Path) -> None:
    module = _script_module()
    path = tmp_path / "scopes.private.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": module.MAPPING_SCOPES_SCHEMA_VERSION,
                "scopes": [
                    {
                        "slot_id": "slot-1",
                        "target_table_node_ids": ["table-1", "table-1"],
                        "confirmed_understandings": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="goal391_mapping_scopes_invalid"):
        module._load_mapping_scopes(path)
