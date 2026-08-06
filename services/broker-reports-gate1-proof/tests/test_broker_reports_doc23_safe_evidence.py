from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[3]
STAGE2 = REPO / "docs/stage2"
REPORT_DIR = REPO / "docs/reports/2026-08-05"

SAFE_FILES = [
    STAGE2 / "BROKER_REPORTS_DOC23_PARSER_VLM_OVERLAP.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC23_PARSER_RESCUE.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC23_CONFLICTS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC23_DEDUPLICATED_VIEW_METRICS.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC23_TOKEN_COMPRESSION.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC23_MATERIAL_SUFFICIENCY.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC23_AUTOMATED_AUDIT.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC23_CALL_ACCOUNTING.safe.json",
    STAGE2 / "BROKER_REPORTS_DOC23_DECISION.safe.json",
]
REPORT = REPORT_DIR / "BROKER_REPORTS_DOC23_DEDUPLICATED_GATE1_LLM_VIEW.report.md"
BRIEF = REPORT_DIR / "BROKER_REPORTS_DOC23_DEDUPLICATED_GATE1_LLM_VIEW_BRIEF.md"
RECEIPT = (
    REPORT_DIR
    / "BROKER_REPORTS_DOC23_DEDUPLICATED_GATE1_LLM_VIEW.receipt.safe.json"
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_checked(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = value.pop("integrity_sha256")
    assert expected == sha256_json(value), path.name
    value["integrity_sha256"] = expected
    return value


def walk(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            rows.append((path, item))
            rows.extend(walk(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(walk(item, f"{prefix}[{index}]"))
    return rows


def test_doc23_safe_artifacts_have_valid_integrity_and_privacy_boundary() -> None:
    forbidden_keys = {
        "text",
        "source_bbox",
        "target_bbox",
        "raw_output",
        "raw_private_response",
        "source_pdf_file",
        "case_package_file",
        "deduplicated_view_file",
        "direct_review_file",
        "exception_message",
    }
    forbidden_value_fragments = (
        "local/stage2/",
        "local\\stage2\\",
        ".private.json",
        ".private.txt",
        ".pdf",
        "data:image/",
    )
    for path in SAFE_FILES:
        assert path.is_file(), path
        value = load_checked(path)
        assert value.get("research_only") is True or value.get("doc23_research_only") is True
        for key_path, item in walk(value):
            key = key_path.rsplit(".", 1)[-1].split("[", 1)[0]
            assert key not in forbidden_keys, (path.name, key_path)
            if isinstance(item, str):
                lowered = item.lower()
                assert not any(
                    fragment in lowered for fragment in forbidden_value_fragments
                ), (path.name, key_path)


def test_doc23_overlap_rescue_and_compression_are_terminally_measured() -> None:
    overlap = load_checked(SAFE_FILES[0])
    rescue = load_checked(SAFE_FILES[1])
    metrics = load_checked(SAFE_FILES[3])
    compression = load_checked(SAFE_FILES[4])

    assert overlap["tables_total"] == 24
    assert overlap["gate1_provider_arms"] == 2
    assert overlap["cases_total"] == 48
    assert overlap["failed_cases_excluded"] == 0
    assert overlap["parser_lines_total"] == 34_541
    assert overlap["table_overlapping_parser_lines"] == 984
    assert sum(overlap["classification_counts"].values()) == 2_154
    assert overlap["classification_counts"] == {
        "AMBIGUOUS": 79,
        "CONFLICT": 42,
        "DUPLICATE": 752,
        "EXTERNAL_CONTEXT": 1_170,
        "PARSER_RESCUE": 111,
        "UNRELATED": 0,
    }
    assert overlap["parser_table_overlap"] == "DUPLICATE_HEAVY"

    assert rescue["doc22_rescue_elements_total"] == 100
    assert rescue["source_class_counts"] == {
        "MIXED_CONTEXT_AND_TABLE_COPY": 4,
        "PARSER_COPY_OF_TABLE": 0,
        "PARSER_ONLY_MISSING_TABLE_FRAGMENT": 0,
        "TRUE_EXTERNAL_CONTEXT": 96,
        "UNRESOLVED": 0,
    }
    assert rescue["lost_parser_rescue_fragments"] == 0
    assert rescue["parser_rescue"] == "PARTIAL"

    duplicate = metrics["duplicate_metrics_before_after"]
    assert duplicate["duplicate_numeric_tokens_before"] == 1_748
    assert duplicate["duplicate_numeric_tokens_after"] == 78
    assert duplicate["duplicate_numeric_token_reduction_percent"] >= 80.0
    assert metrics["full_evidence_preserved"] is True
    assert metrics["product_pipeline_activated"] is False

    corpus = compression["corpus_case_projection"]
    assert corpus["full_shadow_tokens"] == 8_448_750
    assert corpus["deduplicated_view_tokens"] == 5_893_591
    assert corpus["token_reduction_percent"] >= 30.0
    assert compression["minimum_30_percent_met"] is True
    assert compression["target_50_percent_met"] is False
    assert compression["context_compression"] == "MINIMUM_MET"


def test_doc23_direct_review_preserves_doc22_material_sufficiency_and_risk() -> None:
    conflicts = load_checked(SAFE_FILES[2])
    sufficiency = load_checked(SAFE_FILES[5])

    assert sufficiency["direct_agent_review_completed"] is True
    assert sufficiency["direct_cases_total"] == 48
    assert sufficiency["failed_cases_excluded"] == 0
    assert sufficiency["lost_parser_rescue_fragments_total"] == 0
    assert sufficiency["hidden_conflicts_total"] == 0
    assert sufficiency["doc22_ambiguous_upgraded_total"] == 0
    assert sufficiency["deduplicated_view_material_sufficiency"] == "CONFIRMED"
    assert sufficiency["provider_metrics"]["google_flash_lite"]["material_cases"] == 22
    assert sufficiency["provider_metrics"]["anthropic_opus"]["material_cases"] == 23
    assert sufficiency["provider_metrics"]["google_flash_lite"]["counts"][
        "DOCUMENT_CRITICAL_LOSS"
    ] == 0
    assert sufficiency["provider_metrics"]["anthropic_opus"]["counts"][
        "DOCUMENT_CRITICAL_LOSS"
    ] == 0
    assert conflicts["doc22_conflict_cases_total"] == 5
    assert conflicts["direct_ambiguous_cases_total"] == 3
    assert conflicts["hidden_conflicts_total"] == 0


def test_doc23_automated_slots_are_all_accounted_without_repair() -> None:
    automated = load_checked(SAFE_FILES[6])
    accounting = load_checked(SAFE_FILES[7])

    assert automated["exact_preflight_passed"] is True
    assert automated["rate_limit_plan_frozen"] is True
    assert automated["automated_cases_expected"] == 48
    assert automated["automated_cases_started"] == 48
    assert automated["completed_calls"] == 17
    assert automated["failed_calls"] == 31
    assert automated["structured_valid_calls"] == 17
    assert automated["corpus_agreement_eligible"] is False
    assert automated["false_safe_total"] == 0
    assert automated["false_block_total"] == 2
    assert automated["overall_agreement_percent"] == 76.4706
    assert automated["automated_audit"] == "BLOCKED"

    assert accounting["automated_starts_total"] == 48
    assert accounting["automated_attempts_total"] == 48
    assert accounting["slots_accounted_total"] == 48
    assert accounting["unaccounted_total"] == 0
    assert accounting["http_200_total"] == 18
    assert accounting["http_429_total"] == 30
    assert accounting["provider_insufficient_quota_total"] == 30
    assert accounting["structured_output_invalid_total"] == 1
    assert accounting["retry_total"] == 0
    assert accounting["fallback_total"] == 0
    assert accounting["repair_total"] == 0
    assert accounting["execution_mode"] == "SEQUENTIAL"
    assert accounting["bounded_concurrency"] == 1


def test_doc23_decision_scope_and_closure_receipt_are_explicit() -> None:
    decision = load_checked(SAFE_FILES[8])
    receipt = load_checked(RECEIPT)

    assert REPORT.is_file()
    assert BRIEF.is_file()
    assert decision["doc23_experiment"] == "COMPLETED"
    assert decision["parser_table_overlap"] == "DUPLICATE_HEAVY"
    assert decision["parser_rescue"] == "PARTIAL"
    assert decision["deduplicated_view_material_sufficiency"] == "CONFIRMED"
    assert decision["context_compression"] == "MINIMUM_MET"
    assert decision["automated_audit"] == "BLOCKED"
    assert decision["gate1_llm_view_decision"] == "NEEDS_MORE_RESEARCH"
    assert decision["crop_research_policy"] == "PAUSE"
    assert decision["minimum_document_view_contract_research_authorized_by_doc23"] is False
    assert all(
        decision["acceptance"][key] is False
        for key in (
            "gate1_product_changed_by_doc23",
            "parser_changed_by_doc23",
            "cropper_changed_by_doc23",
            "vlm_tables_regenerated",
            "gate2_changed_by_doc23",
            "gate3_created",
            "product_pipeline_activated",
        )
    )
    assert receipt["terminal_status"] == "COMPLETED_WITH_AUTOMATED_AUDIT_BLOCKED"
    assert receipt["full_evidence_preserved"] is True
    assert receipt["automated_slots_accounted"] == 48
    assert receipt["retry_total"] == 0
    assert receipt["fallback_total"] == 0
    assert receipt["repair_total"] == 0
    for row in receipt["artifacts"]:
        path = REPO / row["file"]
        assert path.is_file(), row["file"]
        assert sha256_file(path) == row["sha256"]
