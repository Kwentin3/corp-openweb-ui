from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SERVICE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SERVICE_ROOT / "scripts" / "local_pdf_ingestion_ab_g594.py"
MANIFEST_PATH = (
    SERVICE_ROOT / "benchmarks" / "pdf_ingestion_ab_g594" / "manifest.json"
)


def _load_runner():
    spec = importlib.util.spec_from_file_location("g594_runner_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = _load_runner()


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_frozen_manifest_rejects_current_product_source_drift() -> None:
    manifest = RUNNER._load_manifest(MANIFEST_PATH)

    with pytest.raises(RUNNER.G594Error, match="g594_variant_a_source_hash_drift"):
        RUNNER._verify_variant_a_hashes(manifest)

    assert manifest["goal"] == "G5.94"
    assert manifest["frozen"] is True
    assert manifest["variant_a"]["baseline"] == "G5.93"
    assert manifest["corpus"]["pages_total"] == 103


def test_variant_b_view_has_only_frozen_transcription_task() -> None:
    manifest = RUNNER._load_manifest(MANIFEST_PATH)

    model_view = RUNNER._variant_b_model_view(manifest)
    serialized = json.dumps(model_view, ensure_ascii=False).lower()

    assert set(model_view) == {"task"}
    assert "canonical artifact" not in serialized
    assert "parser output" not in serialized
    assert "dividend_income" not in serialized
    assert "tax_withheld" not in serialized


def test_slots_execute_every_page_once_and_repeats_are_not_selectable() -> None:
    manifest = RUNNER._load_manifest(MANIFEST_PATH)

    slots = RUNNER._build_slots(manifest)
    primary = [slot for slot in slots if slot["run_ordinal"] == 1]
    repeats = [slot for slot in slots if slot["run_ordinal"] == 2]

    assert len(primary) == 103
    assert len({slot["page_id"] for slot in primary}) == 103
    assert len(repeats) == 8
    assert all(slot["response_selection_eligible"] is False for slot in slots)
    assert all(":" not in RUNNER._slot_file_stem(slot["slot_id"]) for slot in slots)


def test_markdown_validator_accepts_content_without_semantic_repair() -> None:
    source = "## Heading\r\n\r\n| A | B |\r\n|---|---|\r\n| -1 | 2,5 |"

    markdown, error = RUNNER._validated_markdown({"markdown": source})

    assert error is None
    assert markdown == source.replace("\r\n", "\n")
    assert "-1" in markdown
    assert "2,5" in markdown


def test_markdown_validator_fails_closed_on_wrong_shape() -> None:
    markdown, error = RUNNER._validated_markdown(
        {"markdown": "visible", "classification": "financial"}
    )

    assert markdown is None
    assert error == "markdown_response_shape_invalid"


def test_repeatability_measures_pairs_without_selecting_output() -> None:
    signature = {"lines": 2, "headings": 1}
    results = [
        {
            "page_id": f"document_01:p{index:03d}",
            "run_ordinal": run,
            "status": "accepted",
            "markdown_sha256": f"hash-{index}",
            "structure_signature": signature,
        }
        for index in range(1, 9)
        for run in (1, 2)
    ]

    measured = RUNNER._repeatability(results)

    assert measured["classification"] == "STABLE"
    assert measured["exact_match_pairs"] == 8
    assert measured["structural_match_pairs"] == 8
    assert measured["outputs_selected"] == 0


def test_review_aggregate_keeps_literal_and_structure_errors_separate() -> None:
    manifest = RUNNER._load_manifest(MANIFEST_PATH)
    review = RUNNER._review_template(manifest)
    for page in review["pages"]:
        page["source_truth_reviewed"] = True
        for arm in ("A", "B"):
            for field in RUNNER.ERROR_FIELDS:
                page[arm][field] = 0
    review["pages"][0]["A"]["changed_literals"] = 2
    review["pages"][0]["A"]["lost_rows"] = 1

    RUNNER._validate_review(review, manifest)
    aggregate = RUNNER._aggregate_review(review, "all", "A")

    assert aggregate["pages"] == 53
    assert aggregate["literal_errors_total"] == 2
    assert aggregate["structural_errors_total"] == 1


def test_sparse_review_decisions_fail_closed_and_materialize_zeroes() -> None:
    manifest = RUNNER._load_manifest(MANIFEST_PATH)
    template = RUNNER._review_template(manifest)
    decisions = {
        "schema_version": RUNNER.REVIEW_DECISIONS_SCHEMA,
        "manifest_sha256": template["manifest_sha256"],
        "unlisted_findings_confirmed_zero": True,
        "overrides": {
            template["pages"][0]["page_id"]: {
                "B": {"changed_literals": 3},
                "disagreement_verdict": "A",
            }
        },
        "recommendation": "HYBRID_JUSTIFIED",
        "recommendation_basis": "separate strengths",
    }

    review = RUNNER._materialize_review(template, decisions)

    RUNNER._validate_review(review, manifest)
    assert review["pages"][0]["B"]["changed_literals"] == 3
    assert review["pages"][1]["B"]["changed_literals"] == 0
    assert review["pages"][1]["source_truth_reviewed"] is True


def test_economics_summary_keeps_failed_terminal_pages_in_denominator() -> None:
    results = [
        {
            "status": "accepted",
            "duration_ms": 100,
            "usage": {"input_tokens": 1000, "output_tokens": 2000},
        },
        {
            "status": "failed",
            "duration_ms": 300,
            "usage": {"input_tokens": 1000, "output_tokens": None},
        },
    ]
    pricing = {
        "currency": "USD",
        "input_usd_per_1m_tokens": 1.5,
        "output_usd_per_1m_tokens": 9.0,
        "effective_date": "2026-08-17",
        "source_url": "https://example.invalid/pricing",
    }

    summary = RUNNER._economics_summary(results, pricing)

    assert summary["pages"] == 2
    assert summary["accepted"] == 1
    assert summary["availability_ratio"] == 0.5
    assert summary["duration_mean_ms"] == 200
    assert summary["tokens"]["total"] == 4000
    assert summary["estimated_cost"]["total"] == 0.021
