from __future__ import annotations

import json
from pathlib import Path

from broker_reports_gate1.gemini_normalized_table_boxes import (
    GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA,
    GeminiNormalizedTableBoxProjectionFactory,
)
from scripts.local_minimal_native_pdfplumber_plan_g5100 import _sha256_json
from scripts.local_table_instance_holdout_g5104 import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    PROMPT,
    _metrics,
    _terminals,
)
from scripts.local_table_instance_separation_g5103 import PROMPT as G5103_PROMPT


SERVICE_ROOT = Path(__file__).resolve().parents[1]
HARNESS_PATH = SERVICE_ROOT / "scripts" / "local_table_instance_holdout_g5104.py"
MANIFEST_PATH = (
    SERVICE_ROOT
    / "benchmarks"
    / "table_instance_separation_holdout_g5104"
    / "manifest.json"
)
PACKAGE_INIT = SERVICE_ROOT / "broker_reports_gate1" / "__init__.py"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_g5104_freezes_exact_g5103_prompt_schema_and_policy() -> None:
    manifest = _manifest()
    contract = manifest["frozen_contract"]
    assert PROMPT == G5103_PROMPT
    assert contract["prompt_sha256"] == _sha256_json(PROMPT)
    assert contract["response_schema_sha256"] == _sha256_json(
        GEMINI_NORMALIZED_TABLE_BOX_RESPONSE_SCHEMA
    )
    assert contract["model"] == "models/gemini-3.5-flash"
    assert contract["thinking_level"] == "minimal"
    assert contract["attempts_per_page"] == 1
    assert contract["retry"] is False
    assert contract["best_of_n"] is False
    assert contract["prompt_repair"] is False
    assert contract["broker_or_domain_hint"] is False


def test_g5104_manifest_has_two_reports_three_tables_and_two_negatives() -> None:
    manifest = _manifest()
    assert manifest["status"] == "frozen_before_provider"
    assert manifest["corpus_role"] == "cross_report_holdout_relative_to_g5103"
    assert manifest["global_unseen_claim"] is False
    assert manifest["expected_totals"] == {
        "documents": 2,
        "pages": 5,
        "positive_pages": 3,
        "negative_pages": 2,
        "visual_tables": 3,
    }
    cases = manifest["cases"]
    assert len(cases) == 5
    assert len({item["case_id"] for item in cases}) == 5
    assert len({item["document_id"] for item in cases}) == 2
    assert sum(item["expected_visual_tables"] for item in cases) == 3
    assert sum(item["expected_visual_tables"] == 0 for item in cases) == 2
    assert all(len(item["page_png_sha256"]) == 64 for item in cases)


def test_g5104_reuses_projection_and_factory_route_without_new_runtime() -> None:
    source = HARNESS_PATH.read_text(encoding="utf-8")
    package_source = PACKAGE_INIT.read_text(encoding="utf-8")
    projection = GeminiNormalizedTableBoxProjectionFactory().create()
    assert projection.config.coordinate_normalizer == 1000
    assert "from scripts.local_table_instance_separation_g5103 import PROMPT" in source
    assert "PROMPT = \"\"\"" not in source
    assert "GeminiNormalizedTableBoxProjectionFactory" in source
    assert "_provider" in source
    assert "attempt_number=1" in source
    assert "NativePdfPointNavigationOverlayFactory" not in source
    assert "VisualPdfPlumberTableAdapterFactory" not in source
    assert "explicit_vertical_lines" not in source
    assert "GeminiNormalizedTableBoxProjectionFactory" not in package_source
    assert FACTORY_REQUIRED.startswith("PdfTableRasterFactory.create frozen render")
    assert FORBIDDEN.startswith("No prompt/schema/model change")


def test_g5104_metrics_and_terminals_assert_observable_holdout_outcomes() -> None:
    def result(expected: int, proposed: int, *, invalid: bool = False) -> dict[str, object]:
        return {
            "document_id": "doc",
            "expected_visual_tables": expected,
            "provider_value": {"tables": [{"box_2d": [1, 2, 3, 4]}] * proposed},
            "projection": {"tables": [{}] * proposed},
            "projection_error": "invalid" if invalid else None,
            "attempt": {
                "finish_reason": "STOP",
                "terminal_failure_class": None,
            },
        }

    passing = [result(0, 0), result(1, 1), result(0, 0), result(1, 1), result(1, 1)]
    metrics = _metrics(passing)
    assert metrics["pages"] == 5
    assert metrics["expected_visual_tables"] == 3
    assert metrics["proposed_tables"] == 3
    assert metrics["pages_with_exact_table_count"] == 5
    assert metrics["false_boxes_on_negative_pages"] == 0
    assert _terminals(metrics) == [
        "TABLE_INSTANCE_HOLDOUT_MACHINE_COUNTS_PASSED_VISUAL_REVIEW_REQUIRED"
    ]

    count_failure = _metrics([result(0, 1), *passing[1:]])
    assert _terminals(count_failure) == ["TABLE_INSTANCE_HOLDOUT_COUNT_FAILED"]

    contract_failure = _metrics([result(0, 0, invalid=True), *passing[1:]])
    assert _terminals(contract_failure) == ["TABLE_INSTANCE_HOLDOUT_CONTRACT_FAILED"]
