"""G5.63 context visibility and oracle-independence guards."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

from broker_reports_gate1.gate3_llm_metadata_adapter import (
    build_metadata_context_package,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "qualify_g563_metadata_context_visibility.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("g563_visibility", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G563 = _load_script()


def test_visibility_binding_requires_same_node_and_literal() -> None:
    registry = {
        "targets": {
            "m001": {"node_id": "node-a", "content": "opaque value"},
            "m002": {"node_id": "node-b", "content": "other value"},
        }
    }
    assert G563.find_visible_target_aliases(
        registry=registry,
        node_id="node-a",
        literal="opaque value",
    ) == ["m001"]
    assert G563.find_visible_target_aliases(
        registry=registry,
        node_id="node-b",
        literal="opaque value",
    ) == []


def test_selector_has_no_oracle_input_or_position_cutoff() -> None:
    signature = inspect.signature(build_metadata_context_package)
    source = inspect.getsource(build_metadata_context_package).lower()

    assert set(signature.parameters) == {
        "artifact",
        "document_id",
        "canonical_version_id",
    }
    assert "oracle" not in source
    assert "text_head" not in source
    assert "break" not in source
    assert "selected = candidates" in source


def test_incomplete_case_fails_before_replay_authorization() -> None:
    with pytest.raises(G563.G563VisibilityError, match="g563_fact_visibility_ambiguous"):
        G563.qualify_case(
            alias="pdf_002",
            oracle_case={
                "facts": [
                    {
                        "fact_id": "fact-1",
                        "fact_type": "PARTY_NAME",
                        "canonical_binding": {
                            "node_id": "missing",
                            "literal": "not visible",
                        },
                    }
                ]
            },
            package={"metrics": {}},
            registry={"targets": {}},
        )
