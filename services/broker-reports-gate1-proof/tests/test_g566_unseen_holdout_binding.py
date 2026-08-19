"""G5.66 exact text-line binding and oracle-independence guards."""

from __future__ import annotations

import importlib.util
import inspect
from pathlib import Path

from broker_reports_gate1.gate3_llm_metadata_adapter import (
    build_metadata_context_package,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "qualify_g566_unseen_holdout_binding.py"
LIVE_SCRIPT_PATH = SERVICE_ROOT / "scripts" / "live_g566_unseen_holdout_replay.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("g566_binding", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


G566 = _load_script()


def test_exact_fragment_lookup_distinguishes_same_literal_by_line() -> None:
    registry = {
        "targets": {
            "m001": {
                "node_id": "text-a",
                "fragments": [
                    {
                        "field_path": "content.text.lines[0]",
                        "literal": "Client: Ada Lovelace",
                    }
                ],
            },
            "m002": {
                "node_id": "text-a",
                "fragments": [
                    {
                        "field_path": "content.text.lines[1]",
                        "literal": "Signed by: Ada Lovelace",
                    }
                ],
            },
        }
    }

    assert G566._aliases_for_fragment(
        registry=registry,
        node_id="text-a",
        field_path="content.text.lines[0]",
        literal="Ada Lovelace",
    ) == ["m001"]
    assert G566._aliases_for_fragment(
        registry=registry,
        node_id="text-a",
        field_path="content.text.lines[1]",
        literal="Ada Lovelace",
    ) == ["m002"]


def test_packager_selection_does_not_accept_or_read_oracle() -> None:
    signature = inspect.signature(build_metadata_context_package)
    source = inspect.getsource(build_metadata_context_package).lower()

    assert set(signature.parameters) == {
        "artifact",
        "document_id",
        "canonical_version_id",
    }
    assert "oracle" not in source
    assert "selected = candidates" in source


def test_live_replay_uses_both_factories_and_one_submission_guard() -> None:
    source = LIVE_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "Gate3LlmMetadataAdapterFactory(" in source
    assert "Gate2StructuredModelClientFactory(" in source
    assert "exactly_one_g566_holdout_submission_required" in source
    assert '"retries": 0' in source
    assert '"best_of_n": False' in source
    assert '"manual_output_repair": False' in source
