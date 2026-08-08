from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "live_gate3_strict_alias_closeout.py"


def _module():
    spec = importlib.util.spec_from_file_location(
        "live_gate3_strict_alias_closeout",
        SCRIPT_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_live_plan_is_exactly_two_predeclared_existing_batch_calls() -> None:
    module = _module()
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert tuple(module.DOCUMENTS) == ("compact_html", "large_csv_chunk3")
    assert module.SELECTIONS == {
        "compact_html": None,
        "large_csv_chunk3": (3,),
    }
    assert module.FROZEN_SAFE_SHAPES["compact_html"]["available_chunks"] == 1
    assert module.FROZEN_SAFE_SHAPES["large_csv_chunk3"] == {
        "available_chunks": 6,
        "ordinal": 3,
        "structural_kind": "table_rows",
        "row_start": 488,
        "row_end": 761,
        "model_view_chars": 59964,
        "target_count": 2106,
    }
    assert "Gate3ChunkBatchLabelingFactory" in source
    assert "Gate2StructuredModelClientFactory" in source
    assert "expected_provider_submissions\": 2" in source
    assert "retry_count\": 0" in source
    assert "repair_count\": 0" in source
    assert "persistence_writes\": 0" in source


def test_live_script_has_no_alias_repair_or_semantic_selector() -> None:
    module = _module()
    source = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "normalize or repair aliases" in module.FORBIDDEN
    assert "start G3.5" in module.FORBIDDEN
    for forbidden in (
        "strip_brackets",
        "normalize_alias",
        "repair_alias",
        "re.sub(",
        "re.search(",
        "ACCRUED_COUPON_COMPONENT\": (",
        "SECURITIES_LENDING_INCOME\": (",
        "asyncio.gather",
    ):
        assert forbidden not in source


def test_frozen_shape_check_fails_before_transport_on_drift() -> None:
    module = _module()
    valid = {
        "ordinal": 1,
        "structural_kind": "whole_document",
        "structural_scope": {"row_start": None, "row_end": None},
        "metrics": {"model_view_chars": 15042, "target_count": 612},
    }
    module._validate_frozen_shape(
        label="compact_html",
        chunk_set={"chunks": [valid]},
        selected=[valid],
    )

    changed = {**valid, "metrics": {"model_view_chars": 15043, "target_count": 612}}
    with pytest.raises(SystemExit, match="compact_html_frozen_shape_changed"):
        module._validate_frozen_shape(
            label="compact_html",
            chunk_set={"chunks": [changed]},
            selected=[changed],
        )
