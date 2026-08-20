from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RECEIPT = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-08-20"
    / "BROKER_REPORTS_CURRENT_GATE3_REPEATABILITY.receipt.safe.json"
)
SCRIPT = (
    REPO_ROOT
    / "services"
    / "broker-reports-gate1-proof"
    / "scripts"
    / "qualify_current_gate3_repeatability.py"
)


def test_current_repeatability_is_one_frozen_contract_without_result_selection() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert receipt["status"] == (
        "CURRENT_GATE3_VARIANCE_OBSERVED_ON_FROZEN_CANONICAL"
    )
    assert receipt["exact_semantic_repeatability"] is False
    assert [item["annotations_validated"] for item in receipt["runs"]] == [
        74,
        49,
        83,
    ]
    assert len({item["semantic_output_sha256"] for item in receipt["runs"]}) == 3
    assert all(item["document_status"] == "complete" for item in receipt["runs"])
    assert all(item["provider_submissions"] == 2 for item in receipt["runs"])
    assert receipt["provider_submissions"] == 6
    assert receipt["retry_count"] == 0
    assert receipt["repair_count"] == 0
    assert receipt["fallback_count"] == 0
    assert receipt["best_of_n_selection"] is False
    assert receipt["manual_fact_changes"] == 0


def test_repeatability_script_fails_closed_and_does_not_persist_annotations() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "Gate3ChunkBatchLabelingFactory" in source
    assert "Gate3FinancialAnnotationsPersistenceFactory" not in source
    assert "tenacity" not in source.lower()
    assert ".retry(" not in source.lower()
    assert "range(1, RUNS + 1)" in source
    assert '"retry_count": 0' in source
    assert '"repair_count": 0' in source
    assert '"best_of_n_selection": False' in source
    assert "return 0 if exact else 2" in source
