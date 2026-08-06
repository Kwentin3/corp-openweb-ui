from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
STAGE = REPO / "docs/stage2"
REPORTS = REPO / "docs/reports/2026-08-03"

RESULTS = STAGE / "BROKER_REPORTS_DOC14_STRUCTURED_JSON_RESULTS.safe.json"
EFFECT = STAGE / "BROKER_REPORTS_DOC14_STRUCTURED_OUTPUT_EFFECT.safe.json"
ACCOUNTING = STAGE / "BROKER_REPORTS_DOC14_CALL_ACCOUNTING.safe.json"
REPORT = REPORTS / "BROKER_REPORTS_DOC14_STRUCTURED_JSON.report.md"
BRIEF = REPORTS / "BROKER_REPORTS_DOC14_STRUCTURED_JSON_BRIEF.md"
RECEIPT = REPORTS / "BROKER_REPORTS_DOC14_STRUCTURED_JSON.receipt.safe.json"
ADJUDICATION = STAGE / "BROKER_REPORTS_DOC14_VISUAL_GOLD_ADJUDICATION.safe.json"
ADJUDICATION_REPORT = REPORTS / "BROKER_REPORTS_DOC14_VISUAL_GOLD_ADJUDICATION.report.md"
ADJUDICATION_RECEIPT = (
    REPORTS / "BROKER_REPORTS_DOC14_VISUAL_GOLD_ADJUDICATION.receipt.safe.json"
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    expected = value["integrity_sha256"]
    actual = hashlib.sha256(
        _canonical({key: item for key, item in value.items() if key != "integrity_sha256"})
    ).hexdigest()
    assert actual == expected
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _walk(value: Any):
    yield value
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def test_doc14_primary_call_accounting_is_terminal_and_one_attempt() -> None:
    accounting = _read(ACCOUNTING)
    assert accounting["new_calls_expected_total"] == 16
    assert accounting["baseline_calls_reused_total"] == 16
    assert accounting["new_calls_accounted_total"] == 16
    assert accounting["http_200_total"] == 16
    assert accounting["provider_success_total"] == 16
    assert accounting["failed_total"] == 0
    assert accounting["attempts_total"] == 16
    assert accounting["retry_total"] == 0
    assert accounting["fallback_total"] == 0
    assert accounting["structured_output_calls_total"] == 16
    assert accounting["maximum_parallelism"] == 1


def test_doc14_raw_result_preserves_format_win_and_predefined_gate_failure() -> None:
    results = _read(RESULTS)
    classifications = results["classifications"]
    assert classifications["RUN_STATUS"] == "DONE"
    assert classifications["STRUCTURED_OUTPUT_FORMAT"] == "CONFIRMED"
    assert classifications["CHEAP_STRUCTURED_JSON"] == "NOT_CONFIRMED"
    assert classifications["SIMPLE_GATE1_STRUCTURED_JSON"] == "NOT_CONFIRMED"
    assert classifications["BEST_CHEAP_MODEL"] == "NONE"
    for model in results["models"].values():
        assert model["structured"]["normalized_json_validity"] == 1.0
        assert model["structured"]["critical_values_invented"] == 5
        assert model["structured"]["threshold_passed"] is False
    assert results["models"]["google_flash_lite"]["structured"]["exact_table_rate"] == 0.5
    assert results["models"]["anthropic_opus"]["structured"]["exact_table_rate"] == 0.5
    assert results["acceptance"]["PARSER_PRODUCT_CODE_CHANGED"] is False
    assert results["acceptance"]["DOC6_CHANGED"] is False
    assert results["acceptance"]["PRODUCT_PIPELINE_CHANGED"] is False


def test_doc14_effect_is_reported_separately_for_format_and_content() -> None:
    effect = _read(EFFECT)
    assert effect["classification"] == "CONFIRMED"
    for model in effect["per_model_effect"].values():
        assert model["STRUCTURED_OUTPUT_FORMAT"] == "CONFIRMED"
        assert model["FORMAT_EFFECT"] == "POSITIVE"
        assert model["CONTENT_EFFECT"] == "MIXED"
        assert model["OVERALL_EFFECT"] == "MIXED"


def test_doc14_visual_gold_adjudication_does_not_relabel_the_raw_verdict() -> None:
    adjudication = _read(ADJUDICATION)
    classifications = adjudication["classifications"]
    assert adjudication["post_hoc_adjudication"] is True
    assert adjudication["raw_predefined_verdict_preserved"] is True
    assert classifications["RAW_PREDEFINED_SIMPLE_GATE1_STRUCTURED_JSON"] == "NOT_CONFIRMED"
    assert classifications["VISUAL_GOLD_ADJUDICATED_CHEAP_STRUCTURED_JSON"] == "PROMISING"
    assert classifications["VISUAL_GOLD_ADJUDICATED_REFERENCE_STRUCTURED_JSON"] == "PROMISING"
    assert classifications["BEST_ADJUDICATED_CHEAP_MODEL"] == "google_flash_lite"
    assert classifications["BEST_ADJUDICATED_REFERENCE_MODEL"] == "anthropic_opus"
    for model in adjudication["models"].values():
        assert model["raw_source_text_invented_total"] == 5
        assert model["supported_by_sealed_visual_gold_total"] == 5
        assert model["unsupported_by_source_and_visual_gold_total"] == 0
    assert adjudication["models"]["google_flash_lite"][
        "visual_gold_adjudicated_threshold_passed"
    ] is True
    assert adjudication["models"]["anthropic_opus"][
        "visual_gold_adjudicated_threshold_passed"
    ] is True
    assert adjudication["models"]["openai_mini"][
        "visual_gold_adjudicated_threshold_passed"
    ] is False
    assert adjudication["models"]["anthropic_haiku"][
        "visual_gold_adjudicated_threshold_passed"
    ] is False


def test_doc14_receipts_bind_every_public_artifact() -> None:
    for receipt_path in (RECEIPT, ADJUDICATION_RECEIPT):
        receipt = _read(receipt_path)
        for relative, expected in receipt["artifact_sha256"].items():
            assert _sha(REPO / relative) == expected
    assert REPORT.read_bytes().startswith(b"\xef\xbb\xbf")
    assert BRIEF.read_bytes().startswith(b"\xef\xbb\xbf")
    assert ADJUDICATION_REPORT.read_bytes().startswith(b"\xef\xbb\xbf")


def test_doc14_public_evidence_has_no_private_payload_fields_or_local_paths() -> None:
    json_paths = (RESULTS, EFFECT, ACCOUNTING, RECEIPT, ADJUDICATION, ADJUDICATION_RECEIPT)
    forbidden = {"raw_output", "provider_private", "source_critical_values", "output_critical_values"}
    for path in json_paths:
        rendered = path.read_text(encoding="utf-8-sig")
        assert not re.search(r"[A-Za-z]:\\Users\\", rendered, flags=re.IGNORECASE)
        assert not forbidden.intersection(str(item) for item in _walk(_read(path)))
    for path in (REPORT, BRIEF, ADJUDICATION_REPORT):
        assert not re.search(
            r"[A-Za-z]:\\Users\\",
            path.read_text(encoding="utf-8-sig"),
            flags=re.IGNORECASE,
        )
