from __future__ import annotations

from pathlib import Path

from broker_reports_gate1.gemini_normalized_table_boxes import (
    GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA,
    GeminiNormalizedTableBoxProjectionFactory,
)
from scripts.local_gemini_table_boxes_g5102 import PROMPT as G5102_PROMPT
from scripts.local_table_instance_separation_g5103 import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    G5102_INSTANCE_RULE,
    G5103_INSTANCE_RULE,
    PROMPT,
    _derive_prompt,
    _terminals,
)


SERVICE_ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = (
    SERVICE_ROOT / "scripts" / "local_table_instance_separation_g5103.py"
)
PACKAGE_INIT = SERVICE_ROOT / "broker_reports_gate1" / "__init__.py"


def test_g5103_changes_only_the_table_instance_prompt_rule() -> None:
    assert G5102_PROMPT.count(G5102_INSTANCE_RULE) == 1
    assert PROMPT == G5102_PROMPT.replace(
        G5102_INSTANCE_RULE,
        G5103_INSTANCE_RULE,
    )
    assert _derive_prompt() == PROMPT
    assert "zero, one, or multiple table" in PROMPT
    assert "exactly one box per table instance" in PROMPT
    assert "Never use one box that" in PROMPT
    assert "Do not split one continuous grid" in PROMPT
    assert "broker" not in PROMPT.lower()
    assert "financial" not in PROMPT.lower()


def test_g5103_reuses_the_g5102_schema_and_projection_owner() -> None:
    projection = GeminiNormalizedTableBoxProjectionFactory().create()
    assert projection.config.coordinate_normalizer == 1000
    box = GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA["properties"]["tables"][
        "items"
    ]["properties"]["box_2d"]
    assert "[ymin, xmin, ymax, xmax]" in box["description"]
    assert box["items"] == {
        "type": "integer",
        "minimum": 0,
        "maximum": 1000,
    }


def test_g5103_harness_preserves_factory_route_and_research_stops() -> None:
    source = HARNESS_PATH.read_text(encoding="utf-8")
    package_source = PACKAGE_INIT.read_text(encoding="utf-8")
    assert "PdfTableRasterFactory" in source
    assert "GeminiNormalizedTableBoxProjectionFactory" in source
    assert "_provider" in source
    assert "attempt_number=1" in source
    assert '"retry": False' in source
    assert '"best_of_n": False' in source
    assert "NativePdfPointNavigationOverlayFactory" not in source
    assert "VisualPdfPlumberTableAdapterFactory" not in source
    assert "explicit_vertical_lines" not in source
    assert "GeminiNormalizedTableBoxProjectionFactory" not in package_source
    assert "FACTORY_REQUIRED" in source
    assert "FORBIDDEN" in source
    assert FACTORY_REQUIRED.startswith("PdfTableRasterFactory.create")
    assert FORBIDDEN.startswith("No broker/domain hint")


def test_g5103_terminals_are_fail_closed_and_observable() -> None:
    base = {
        "provider_non_success_terminals": 0,
        "invalid_responses": 0,
        "pages_with_exact_table_count": 9,
        "pages": 9,
        "false_boxes_on_negative_pages": 0,
        "exact_truth_regions": 7,
        "expressible_truth_regions": 7,
    }
    assert _terminals(base) == ["TABLE_INSTANCE_SEPARATION_MACHINE_CHECKS_PASSED"]

    count_failure = dict(base, pages_with_exact_table_count=8)
    assert _terminals(count_failure) == [
        "TABLE_INSTANCE_SEPARATION_COUNT_INSUFFICIENT"
    ]

    localization_failure = dict(base, exact_truth_regions=6)
    assert _terminals(localization_failure) == [
        "TABLE_INSTANCE_SEPARATION_LOCALIZATION_INSUFFICIENT"
    ]

    contract_failure = dict(base, invalid_responses=1)
    assert _terminals(contract_failure) == [
        "TABLE_INSTANCE_SEPARATION_CONTRACT_FAILED"
    ]
