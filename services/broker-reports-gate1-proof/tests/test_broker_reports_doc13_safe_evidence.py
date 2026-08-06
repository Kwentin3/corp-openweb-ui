from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
RESULTS = REPO / "docs/stage2/BROKER_REPORTS_DOC13_SIMPLE_GATE1_JSON_RESULTS.safe.json"
EFFECT = REPO / "docs/stage2/BROKER_REPORTS_DOC13_SOURCE_TEXT_EFFECT.safe.json"
ACCOUNTING = REPO / "docs/stage2/BROKER_REPORTS_DOC13_CALL_ACCOUNTING.safe.json"
REPORT = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC13_SIMPLE_GATE1_JSON.report.md"
RECEIPT = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC13_SIMPLE_GATE1_JSON.receipt.safe.json"
BRIEF = REPO / "docs/reports/2026-08-03/BROKER_REPORTS_DOC13_SIMPLE_GATE1_JSON_BRIEF.md"

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


def _walk_values(value: Any):
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_values(nested)
    else:
        yield value


def _walk_keys(value: Any):
    if isinstance(value, dict):
        yield from value
        for nested in value.values():
            yield from _walk_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_keys(nested)


def test_doc13_safe_artifacts_are_integrity_bound_and_privacy_safe() -> None:
    payloads = [_load(RESULTS), _load(EFFECT), _load(ACCOUNTING), _load(RECEIPT)]
    forbidden_keys = {
        "raw_output", "provider_private", "parser_text", "source_critical_values",
        "output_critical_values", "api_key", "request_body", "response_body",
        "fragment_private_map", "parser_inventory", "fragment_ids", "bbox",
    }
    known_private_values = ("48121a290", "73,320,834", "$1.17")
    for payload in payloads:
        keys = {str(value).casefold() for value in _walk_keys(payload)}
        values = "\n".join(str(value) for value in _walk_values(payload) if isinstance(value, str)).casefold()
        assert forbidden_keys.isdisjoint(keys)
        assert "local/stage2" not in values
        assert "c:\\users\\" not in values and "d:\\users\\" not in values
        assert "api_key" not in values and "authorization" not in values and "sk-" not in values
        assert not any(value in values for value in known_private_values)
    public_text = (REPORT.read_text(encoding="utf-8-sig") + BRIEF.read_text(encoding="utf-8-sig")).casefold()
    assert not any(value in public_text for value in known_private_values)
    assert "c:\\users\\" not in public_text and "d:\\users\\" not in public_text


def test_doc13_exact_models_and_two_arm_inputs_are_reported() -> None:
    results = _load(RESULTS)
    assert {key: value["requested_model_id"] for key, value in results["model_identity"].items()} == MODELS
    assert {
        key: value["resolved_model_ids"] for key, value in results["model_identity"].items()
    } == {key: [model] for key, model in MODELS.items()}
    assert results["arms"] == {
        "IMAGE_ONLY": {
            "images_per_call": 1,
            "source_parser_text_included": False,
            "common_instruction": True,
        },
        "IMAGE_PLUS_SOURCE_TEXT": {
            "images_per_call": 1,
            "source_parser_text_included": True,
            "source_text_structure_neutral": True,
            "fragment_ids_included": False,
            "geometry_included": False,
            "financial_dictionary_included": False,
            "common_instruction": True,
        },
    }


def test_doc13_accounts_for_all_calls_without_retry_or_exclusion() -> None:
    accounting = _load(ACCOUNTING)
    calls = accounting["calls"]
    assert accounting["expected_calls_total"] == 32
    assert accounting["slots_accounted_total"] == 32
    assert accounting["http_responses_total"] == 32
    assert accounting["http_200_total"] == 32
    assert accounting["terminal_statuses"] == {"COMPLETED": 32}
    assert accounting["retry_total"] == 0
    assert accounting["fallback_total"] == 0
    assert accounting["failed_tables_excluded_total"] == 0
    assert accounting["maximum_parallelism"] == 1
    assert len(calls) == len({item["slot_id"] for item in calls}) == 32
    assert all(item["attempts_total"] == 1 and item["image_count"] == 1 for item in calls)


def test_doc13_metrics_and_source_effect_are_complete() -> None:
    results = _load(RESULTS)
    effect = _load(EFFECT)
    required = {
        "raw_json_validity", "normalized_json_validity", "critical_value_recall",
        "critical_value_precision", "row_association_accuracy", "column_association_accuracy",
        "header_accuracy", "row_order_accuracy", "complete_table_exact_rate",
        "input_tokens", "output_tokens", "thinking_tokens", "average_latency_seconds",
        "estimated_cost_usd_total", "error_classes", "critical_value_categories",
    }
    for model in MODELS:
        for arm in ("IMAGE_ONLY", "IMAGE_PLUS_SOURCE_TEXT"):
            assert required.issubset(results["per_model_arm"][model][arm])
        assert effect["per_model"][model]["decision_eligible"] is True
    assert {key: value["SOURCE_TEXT_EFFECT"] for key, value in effect["per_model"].items()} == {
        "openai_mini": "NEGATIVE",
        "google_flash_lite": "INCONCLUSIVE",
        "anthropic_haiku": "NO_MEANINGFUL_EFFECT",
        "anthropic_opus": "NEGATIVE",
    }
    assert not any(
        results["per_model_arm"][model]["IMAGE_PLUS_SOURCE_TEXT"]["promising_threshold_passed"]
        for model in MODELS
    )


def test_doc13_terminal_decisions_and_stop_boundary_are_exact() -> None:
    results = _load(RESULTS)
    assert results["classifications"] == {
        "DOC13_EXPERIMENT": "COMPLETED",
        "SOURCE_TEXT_IMPROVES_RELATION_RECOVERY": "NOT_CONFIRMED",
        "BEST_CHEAP_MODEL": "NONE",
        "BEST_REFERENCE_MODEL": "anthropic_opus",
        "SIMPLE_GATE1_JSON": "NOT_CONFIRMED",
    }
    acceptance = results["acceptance"]
    assert acceptance["DUPLICATE_MECHANISMS_CREATED"] == 0
    assert acceptance["NEW_PROVIDER_TRANSPORTS_CREATED"] == 0
    assert acceptance["NEW_PARSERS_CREATED"] == 0
    assert acceptance["NEW_GOLD_SYSTEMS_CREATED"] == 0
    assert acceptance["PARSER_PRODUCT_CODE_CHANGED"] is False
    assert acceptance["DOC6_CHANGED"] is False
    assert acceptance["PRODUCT_PIPELINE_CHANGED"] is False


def test_doc13_receipt_binds_outputs_and_markdown_is_utf8_bom() -> None:
    receipt = _load(RECEIPT)
    for relative, expected in receipt["artifact_sha256"].items():
        assert _sha(REPO / relative) == expected
    assert receipt["verification"] == {
        "private_integrity_verified": True,
        "protocol_bindings_verified": True,
        "package_hashes_verified": True,
        "transport_hash_verified": True,
        "product_source_hashes_verified": True,
        "safe_integrity_verified": True,
        "privacy_scan_passed": True,
        "deterministic_publisher_replay_passed": True,
        "factory_first_transport_reuse_verified": True,
        "closed_world_import_or_dependency_change": False,
        "literal_denylist_initial_result": "FALSE_POSITIVE",
        "literal_denylist_false_positive_terms_total": 3,
        "privacy_scan_method": "KEY_VALUE_AWARE_WITH_CONTROLLED_PUBLIC_VOCABULARY_ADJUDICATION",
        "privacy_scan_adjudication": "PASS",
    }
    assert len(receipt["code_change_sha256"]["privacy_adjudication"]) == 64
    assert REPORT.read_bytes().startswith(b"\xef\xbb\xbf")
    assert BRIEF.read_bytes().startswith(b"\xef\xbb\xbf")
    report = REPORT.read_text(encoding="utf-8-sig")
    for marker in (
        "DOC13_EXPERIMENT = COMPLETED",
        "SOURCE_TEXT_IMPROVES_RELATION_RECOVERY = NOT_CONFIRMED",
        "BEST_CHEAP_MODEL = NONE",
        "BEST_REFERENCE_MODEL = anthropic_opus",
        "SIMPLE_GATE1_JSON = NOT_CONFIRMED",
        "Gate 2 не реализован",
    ):
        assert marker in report
