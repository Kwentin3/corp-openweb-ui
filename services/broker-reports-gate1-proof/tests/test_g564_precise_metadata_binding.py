"""G5.64 structural binding and oracle-independence guards."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

import pytest

from broker_reports_gate1.gate3_llm_metadata_adapter import (
    build_metadata_context_package,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "qualify_g564_precise_metadata_binding.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("g564_binding", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G564 = _load_script()


def test_precise_binding_requires_exact_canonical_fragment_path() -> None:
    registry = {
        "targets": {
            "m001": {
                "node_id": "table-a",
                "fragments": [
                    {
                        "field_path": "content.cells[4]",
                        "literal": "TF1467223",
                    },
                    {
                        "field_path": "content.cells[5]",
                        "literal": "Example Person",
                    },
                ],
            },
            "m002": {
                "node_id": "table-a",
                "fragments": [
                    {
                        "field_path": "content.cells[12]",
                        "literal": "D1467223",
                    },
                    {
                        "field_path": "content.cells[13]",
                        "literal": "Example Person",
                    },
                ],
            },
        }
    }

    assert G564.find_structural_target_aliases(
        registry=registry,
        node_id="table-a",
        field_path="content.cells[12].displayed_value",
        literal="1467223",
    ) == ["m002"]
    assert G564.find_structural_target_aliases(
        registry=registry,
        node_id="table-a",
        field_path="content.cells[13].displayed_value",
        literal="Example Person",
    ) == ["m002"]


def test_packager_has_no_oracle_or_semantic_selector_input() -> None:
    signature = inspect.signature(build_metadata_context_package)
    source = inspect.getsource(build_metadata_context_package).lower()

    assert set(signature.parameters) == {
        "artifact",
        "document_id",
        "canonical_version_id",
    }
    assert "oracle" not in source
    assert "party_name" not in source
    assert "account_identifier" not in source
    assert "selected = candidates" in source


def test_ambiguous_or_missing_precise_binding_blocks_replay() -> None:
    with pytest.raises(G564.G564BindingError, match="g564_fact_binding_ambiguous"):
        G564.qualify_case(
            alias="pdf_002",
            oracle_case={
                "facts": [
                    {
                        "fact_id": "fact-1",
                        "fact_type": "PARTY_NAME",
                        "canonical_binding": {
                            "node_id": "missing",
                            "field_path": "content.text.lines[0]",
                            "literal": "not visible",
                        },
                    }
                ]
            },
            package={"metrics": {}},
            registry={"targets": {}},
        )
