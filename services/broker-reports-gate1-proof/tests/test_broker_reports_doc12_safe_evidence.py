from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / "docs/stage2/BROKER_REPORTS_DOC12_IMAGE_ONLY_ROW_RESULTS.safe.json"
SNAPPING = REPO / "docs/stage2/BROKER_REPORTS_DOC12_GEOMETRIC_SNAPPING.safe.json"
REPORT = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC12_IMAGE_ONLY_LOGICAL_ROWS.report.md"
RECEIPT = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC12_IMAGE_ONLY_LOGICAL_ROWS.receipt.safe.json"
BRIEF = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC12_IMAGE_ONLY_LOGICAL_ROWS_BRIEF.md"

MODELS = {
    "openai_mini": "gpt-5.4-mini-2026-03-17",
    "google_flash_lite": "models/gemini-3.5-flash-lite",
    "anthropic_haiku": "claude-haiku-4-5-20251001",
    "anthropic_opus": "claude-opus-5",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _integrity(value: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical({key: item for key, item in value.items() if key != "integrity_sha256"})).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    assert value["integrity_sha256"] == _integrity(value), path
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for key, nested in value.items():
            yield from _walk(key)
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def test_doc12_safe_artifacts_are_integrity_bound_and_privacy_safe() -> None:
    payloads = [_load(RESULTS), _load(SNAPPING), _load(RECEIPT)]
    forbidden_keys = {
        "raw_output", "api_key", "request_body", "response_body",
        "fragment_private_map", "parser_inventory", "fragment_ids",
    }
    forbidden_values = ("48121a290", "73,320,834", "$1.17", "c:\\users\\", "d:\\users\\")
    for payload in payloads:
        strings = {str(value) for value in _walk(payload) if isinstance(value, str)}
        assert forbidden_keys.isdisjoint({value.lower() for value in strings})
        flattened = "\n".join(strings).lower()
        assert "local/stage2" not in flattened
        assert not any(value in flattened for value in forbidden_values)


def test_doc12_uses_exact_models_and_one_image_only_contract() -> None:
    results = _load(RESULTS)
    assert {key: value["requested_model_id"] for key, value in results["models"].items()} == MODELS
    acceptance = results["acceptance"]
    assert acceptance["FROZEN_IMAGES_TOTAL"] == 4
    assert acceptance["IMAGES_BYTE_IDENTICAL_TO_DOC11"] is True
    assert acceptance["MODEL_VISIBLE_FILES_PER_PACKAGE"] == ["prompt.txt", "table.png"]
    assert acceptance["ONE_IMAGE_PER_CALL"] is True
    assert acceptance["MODEL_VISIBLE_PARSER_TEXT"] is False
    assert acceptance["MODEL_VISIBLE_IDS"] is False
    assert acceptance["MODEL_VISIBLE_BBOX_OR_COORDINATES"] is False
    assert acceptance["MODEL_VISIBLE_GOLD"] is False


def test_doc12_call_accounting_is_terminal_without_retry_or_exclusion() -> None:
    results = _load(RESULTS)
    receipt = _load(RECEIPT)
    calls = receipt["calls"]
    assert calls == {
        "authorized_total": 16,
        "slots_accounted_total": 16,
        "http_responses_total": 16,
        "http_200_total": 14,
        "retry_total": 0,
        "fallback_total": 0,
        "maximum_parallelism": 1,
    }
    assert results["acceptance"]["FAILED_TABLES_EXCLUDED_TOTAL"] == 0
    assert results["models"]["anthropic_opus"]["calls_completed"] == 2
    assert all(results["models"][key]["calls_completed"] == 4 for key in MODELS if key != "anthropic_opus")


def test_doc12_reports_raw_and_snapped_geometry_separately() -> None:
    results = _load(RESULTS)
    snapping = _load(SNAPPING)
    assert len(results["per_call"]) == 16
    assert len(snapping["per_call"]) == 16
    assert snapping["snap_tolerance_pixels"] == 12.0
    assert snapping["collision_policy"] == "INVALIDATE_NO_REPAIR"
    assert snapping["unsnapped_policy"] == "INVALIDATE_NO_REPAIR"
    assert [item["candidates_total"] for item in snapping["tables"]] == [8, 5, 14, 31]
    for item in results["per_call"]:
        assert "RAW_LLM_SEPARATORS" in item
        assert "SNAPPED_GEOMETRIC_SEPARATORS" in item
        assert "raw_metrics" in item and "snapped_metrics" in item
    cheap = ("openai_mini", "google_flash_lite", "anthropic_haiku")
    assert all(results["models"][key]["normalized_valid_rate"] == 1.0 for key in cheap)
    assert all(results["models"][key]["snapping_statuses"] == {"SNAPPED": 1, "UNSNAPPED": 3} for key in cheap)


def test_doc12_gold_scope_and_threshold_decisions_are_explicit() -> None:
    results = _load(RESULTS)
    acceptance = results["acceptance"]
    assert acceptance["GOLD_CREATED_AFTER_CALL_ACCOUNTING"] is True
    assert acceptance["PARSER_GEOMETRY_FRAGMENTS_TOTAL"] == 362
    assert acceptance["ROW_EVALUABLE_FRAGMENTS_TOTAL"] == 314
    assert acceptance["NON_ROW_EVALUATOR_FRAGMENTS_TOTAL"] == 48
    assert not any(results["models"][key]["promising_after_snapping_threshold_passed"] for key in MODELS)
    assert results["classifications"] == {
        "DOC12_EXPERIMENT": "BLOCKED",
        "IMAGE_ONLY_ROW_DETECTION": "INCONCLUSIVE",
        "GEOMETRIC_SNAPPING_EFFECT": "INCONCLUSIVE",
        "BEST_CHEAP_ROW_MODEL": "NONE",
        "BEST_REFERENCE_ROW_MODEL": "NONE",
        "ROW_GEOMETRY_PIPELINE": "NOT_CONFIRMED",
    }


def test_doc12_receipt_binds_outputs_and_preserves_stop_boundary() -> None:
    receipt = _load(RECEIPT)
    for item in receipt["artifacts"].values():
        assert _sha(REPO / item["repo_path"]) == item["sha256"]
    assert receipt["privacy_scan"] == "PASSED"
    assert receipt["deterministic_replay"] == "PASSED"
    assert receipt["product_parity"] == "PASSED_NO_PRODUCT_OR_RUNTIME_FILES_CHANGED"
    acceptance = receipt["acceptance"]
    assert acceptance["PARSER_CHANGED"] is False
    assert acceptance["DOC6_CHANGED"] is False
    assert acceptance["PRODUCT_PIPELINE_CHANGED"] is False


def test_doc12_report_and_brief_state_terminal_scope() -> None:
    report = REPORT.read_text(encoding="utf-8-sig")
    brief = BRIEF.read_text(encoding="utf-8-sig")
    for marker in (
        "Статус: `BLOCKED`",
        "IMAGE_ONLY_ROW_DETECTION=INCONCLUSIVE",
        "GEOMETRIC_SNAPPING_EFFECT=INCONCLUSIVE",
        "BEST_CHEAP_ROW_MODEL=NONE",
        "ROW_GEOMETRY_PIPELINE=NOT_CONFIRMED",
        "Parser, DOC6 и product pipeline не изменены",
    ):
        assert marker in report
    assert "только горизонтальные логические строки" in brief
