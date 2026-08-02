from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
STAGE2_ROOT = REPO_ROOT / "docs" / "stage2"
REPORT_ROOT = REPO_ROOT / "docs" / "reports" / "2026-08-03"

RECOVERY_PATH = (
    STAGE2_ROOT / "BROKER_REPORTS_DOC6_LOGICAL_ROW_RECOVERY_RESULTS.safe.json"
)
PARITY_PATH = STAGE2_ROOT / "BROKER_REPORTS_DOC6_ROW_PARITY.safe.json"
STATE_PATH = STAGE2_ROOT / "BROKER_REPORTS_CURRENT_STATE.v1.json"
STATE_GUIDE_PATH = STAGE2_ROOT / "BROKER_REPORTS_CURRENT_STATE.v1.md"
EVIDENCE_INDEX_PATH = STAGE2_ROOT / "BROKER_REPORTS_EVIDENCE_INDEX.v1.md"
REPORT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY.report.md"
)
RECEIPT_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY.receipt.safe.json"
)
BRIEF_PATH = REPORT_ROOT / (
    "BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY_BRIEF.md"
)

EXPECTED_DOCUMENTS = {
    "real_pdf_1": (4, 22, 42, 8, 4, 0),
    "real_pdf_2": (0, 0, 0, 0, 0, 0),
    "real_pdf_4": (12, 123, 369, 32, 12, 0),
    "real_pdf_5": (12, 212, 1927, 108, 14, 2),
}
EXPECTED_TOTALS = {
    "tables_total": 28,
    "rows_total": 357,
    "entries_total": 2338,
    "logical_columns_total": 148,
    "source_parts_total": 30,
    "continued_tables_total": 2,
}
CANONICAL_DOC6_PATHS = {
    "docs/stage2/BROKER_REPORTS_DOC6_LOGICAL_ROW_MODEL_DECISION.v1.md",
    "docs/stage2/BROKER_REPORTS_DOC6_LOGICAL_ROW_RECOVERY_RESULTS.safe.json",
    "docs/stage2/BROKER_REPORTS_DOC6_ROW_PARITY.safe.json",
    "docs/stage2/contracts/BROKER_REPORTS_MANAGED_DOCUMENT.v2.md",
    "docs/stage2/contracts/BROKER_REPORTS_MANAGED_DOCUMENT.v2.schema.json",
    "docs/stage2/contracts/BROKER_REPORTS_LLM_DOCUMENT_VIEW.v2.md",
    "docs/reports/2026-08-03/"
    "BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY.report.md",
    "docs/reports/2026-08-03/"
    "BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY.receipt.safe.json",
    "docs/reports/2026-08-03/"
    "BROKER_REPORTS_DOC6_LOGICAL_ROW_TABLE_RECOVERY_BRIEF.md",
}
PUBLIC_DOCS = (
    RECOVERY_PATH,
    PARITY_PATH,
    STATE_PATH,
    STATE_GUIDE_PATH,
    EVIDENCE_INDEX_PATH,
    REPORT_PATH,
    RECEIPT_PATH,
    BRIEF_PATH,
)
LOCAL_PATH_PATTERN = re.compile(
    r"(?i)(?:[a-z]:[\\/]+users[\\/]+|/home/|/users/|local/stage2/)"
)
FORBIDDEN_PRIVATE_PAYLOAD_KEYS = {
    "anchor_id",
    "anchor_ids",
    "bbox",
    "bboxes",
    "coordinates",
    "geometry_evidence_ids",
    "llm_view_sha256",
    "managed_document_sha256",
    "raw_source_text",
    "raw_text",
    "source_anchor_ids",
    "source_value",
    "word_id",
    "word_ids",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_integrity(payload: dict[str, Any]) -> str:
    material = copy.deepcopy(payload)
    material.pop("integrity_sha256")
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _repository_lf_sha256(path: Path) -> str:
    raw = path.read_bytes()
    normalized = raw.replace(b"\r\n", b"\n")
    assert b"\r" not in normalized, f"lone CR in {path}"
    return hashlib.sha256(normalized).hexdigest()


def _walk_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key
            for item in value.values()
            for key in _walk_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _walk_keys(item)}
    return set()


def test_doc6_safe_artifacts_are_integrity_and_repository_lf_bound() -> None:
    recovery = _read_json(RECOVERY_PATH)
    parity = _read_json(PARITY_PATH)
    receipt = _read_json(RECEIPT_PATH)

    for artifact in (recovery, parity, receipt):
        assert artifact["integrity_sha256"] == _canonical_integrity(artifact)

    safe_artifacts = receipt["safe_artifacts"]
    assert receipt["artifact_hash_policy"] == (
        "sha256_repository_lf_bytes_reject_lone_cr"
    )
    for descriptor in safe_artifacts.values():
        path = REPO_ROOT / descriptor["path"]
        assert path.is_file()
        assert descriptor["repository_lf_sha256"] == _repository_lf_sha256(path)

    assert safe_artifacts["recovery_results"][
        "canonical_integrity_sha256"
    ] == recovery["integrity_sha256"]
    assert safe_artifacts["row_parity"][
        "canonical_integrity_sha256"
    ] == parity["integrity_sha256"]


def test_doc6_recovery_totals_ownership_and_uncertainty_are_exact() -> None:
    recovery = _read_json(RECOVERY_PATH)
    assert recovery["status"] == "PASSED"
    assert recovery["contract"]["canonical_table_model"] == (
        "ORDERED_LOGICAL_ROWS"
    )
    assert recovery["contract"]["rectangular_grid_is_canonical"] is False
    assert recovery["contract"]["logical_columns_are_optional"] is True
    assert recovery["contract"]["product_reachability"] is False

    documents = {
        item["document_key"]: item for item in recovery["corpus"]["documents"]
    }
    assert set(documents) == set(EXPECTED_DOCUMENTS)
    for key, expected in EXPECTED_DOCUMENTS.items():
        item = documents[key]
        actual = (
            item["represented_tables_total"],
            item["rows_total"],
            item["entries_total"],
            item["logical_columns_total"],
            item["source_parts_total"],
            item["continued_tables_total"],
        )
        assert actual == expected
        assert item["expected_tables_total"] == expected[0]

    aggregate = recovery["aggregate"]
    assert aggregate["expected_logical_tables_total"] == 28
    assert aggregate["represented_logical_tables_total"] == 28
    for field, expected in EXPECTED_TOTALS.items():
        recovery_field = {
            "tables_total": "represented_logical_tables_total",
            "rows_total": "visual_gold_rows_total",
            "entries_total": "visual_gold_entries_total",
        }.get(field, field)
        assert aggregate[recovery_field] == expected

    assert sum(aggregate["role_counts"].values()) == 357
    assert aggregate["role_counts"]["UNKNOWN"] == 1
    assert sum(aggregate["entry_kind_counts"].values()) == 2338
    assert aggregate["entry_kind_counts"]["UNKNOWN"] == 0
    assert aggregate["baseline_tables_total"] == 6
    assert aggregate["baseline_tables_regressed_total"] == 0
    assert aggregate["continuation_source_parts_total"] == 4
    assert aggregate["unresolved_column_bindings_total"] == 0
    assert aggregate["unresolved_row_parents_total"] == 1
    assert aggregate["noncritical_ambiguities_total"] == 5
    assert aggregate["visual_gold_blockers_total"] == 0

    accounting = recovery["source_accounting"]
    assert accounting["source_words_total"] == (
        accounting["table_words_total"] + accounting["paragraph_words_total"]
    ) == 11396
    for field in (
        "unresolved_table_words_total",
        "multiple_entry_word_owners_total",
        "table_words_duplicated_as_paragraph_total",
        "paragraph_table_overlap_total",
    ):
        assert accounting[field] == 0
    assert set(recovery["value_accounting"].values()) == {0}
    assert set(recovery["critical_outcomes"].values()) == {0}

    uncertainties = [
        (
            item["table_key"],
            item["row_ordinal"],
            item["issue_code"],
            item["critical"],
        )
        for item in recovery["noncritical_uncertainties"]
    ]
    assert uncertainties == [
        ("real_pdf_5_table_11", 4, "UNKNOWN_ROW_ROLE", False),
        ("real_pdf_5_table_11", 5, "UNRESOLVED_ROW_PARENT", False),
    ]
    assert recovery["unresolved_column_bindings"] == []
    assert [
        (item["table_key"], item["source_parts_total"], item["rows_total"])
        for item in recovery["continued_tables"]
    ] == [
        ("real_pdf_5_table_05", 2, 45),
        ("real_pdf_5_table_06", 2, 74),
    ]


def test_doc6_raw_and_adjudicated_parity_are_both_preserved() -> None:
    recovery = _read_json(RECOVERY_PATH)
    parity = _read_json(PARITY_PATH)
    assert parity["status"] == "PASSED"
    assert parity["comparison_authority"]["precomparison_gold_unchanged"] is True
    assert parity["comparison_authority"]["raw_base_preserved"] is True
    assert parity["totals"]["expected"] == parity["totals"]["managed"]
    assert parity["totals"]["managed"] == parity["totals"]["view"]

    expected_totals = parity["totals"]["expected"]
    for field, expected in EXPECTED_TOTALS.items():
        assert expected_totals[field] == expected
    assert expected_totals["unknown_row_roles_total"] == 1
    assert expected_totals["unresolved_column_bindings_total"] == 0
    assert expected_totals["unresolved_row_parents_total"] == 1

    recovery_documents = {
        item["document_key"]: item for item in recovery["corpus"]["documents"]
    }
    for item in parity["documents"]:
        assert item["expected"] == item["managed"] == item["view"]
        source = recovery_documents[item["document_key"]]
        expected = item["expected"]
        assert expected["tables_total"] == source["represented_tables_total"]
        for field in (
            "rows_total",
            "entries_total",
            "logical_columns_total",
            "source_parts_total",
            "continued_tables_total",
        ):
            assert expected[field] == source[field]
        assert item["factory_route_match"] is True

    for comparison in parity["raw_base_comparisons"].values():
        assert comparison == {
            "status": "FAILED",
            "critical_mismatches_total": 29,
            "source_value_mismatches_total": 29,
            "source_surface_mismatches_total": 27,
            "alignment_ambiguities_total": 0,
            "critical_mismatch_categories": ["ENTRY_TEXT", "HEADER_PATH"],
        }

    errata = parity["errata_adjudication"]
    assert errata["entries_total"] == errata["resolved_total"] == 27
    assert errata["unresolved_total"] == 0
    assert errata["header_path_comparisons_total"] == 2
    assert errata["raw_critical_accounting_total"] == (
        errata["entries_total"] + errata["header_path_comparisons_total"]
    ) == 29
    assert errata["acceptance_ready"] is True

    for comparison in parity["terminal_comparisons"].values():
        assert comparison["status"] == "PASSED"
        for field, value in comparison.items():
            if field.endswith("_total"):
                assert value == 0
    assert set(parity["mismatch_dimensions"].values()) == {0}
    assert parity["pipeline_errors_total"] == 0
    assert parity["evaluator_self_tests_passed"] is True
    assert parity["recovery_module_stable_during_run"] is True


def test_doc6_receipt_current_state_report_and_index_agree() -> None:
    recovery = _read_json(RECOVERY_PATH)
    parity = _read_json(PARITY_PATH)
    receipt = _read_json(RECEIPT_PATH)
    state = _read_json(STATE_PATH)
    guide = STATE_GUIDE_PATH.read_text(encoding="utf-8")
    index = EVIDENCE_INDEX_PATH.read_text(encoding="utf-8")
    report = REPORT_PATH.read_text(encoding="utf-8")
    brief = BRIEF_PATH.read_text(encoding="utf-8")

    assert state["integrity_sha256"] == _canonical_integrity(state)
    assert state["effective_date"] == "2026-08-03"
    assert state["doc6_started"] is True
    assert state["doc6_status"] == "PASSED"
    assert state["doc6_canonical_table_model"] == "ORDERED_LOGICAL_ROWS"
    assert state["managed_document_contract_schema_version"] == (
        "broker_reports_managed_document_v1"
    )
    assert state["llm_document_view_schema_version"] == (
        "broker_reports_llm_document_view_v1"
    )
    assert state["doc6_managed_document_v1_changed"] is False
    assert state["doc6_llm_document_view_v1_changed"] is False
    assert state["doc6_product_route_changed"] is False
    assert state["doc6_generated_bundles_changed"] is False
    assert state["doc6_live_state_changed"] is False
    assert state["doc6_provider_calls_total"] == 0
    assert state["doc6_production_model_qualification"] == "NOT_STARTED"
    assert state["doc6_product_activation"] == "NOT_STARTED"
    assert CANONICAL_DOC6_PATHS <= set(state["canonical_documents"])

    acceptance = receipt["acceptance"]
    aggregate = recovery["aggregate"]
    recovery_values = {**aggregate, **recovery["critical_outcomes"]}
    state_fields = {
        "expected_logical_tables_total": "doc6_expected_logical_tables_total",
        "represented_logical_tables_total": (
            "doc6_represented_logical_tables_total"
        ),
        "visual_gold_rows_total": "doc6_visual_gold_rows_total",
        "managed_document_rows_matched_total": (
            "doc6_managed_document_rows_matched_total"
        ),
        "visual_gold_entries_total": "doc6_visual_gold_entries_total",
        "managed_document_entries_matched_total": (
            "doc6_managed_document_entries_matched_total"
        ),
        "unknown_row_roles_total": "doc6_unknown_row_roles_total",
        "unresolved_column_bindings_total": (
            "doc6_unresolved_column_bindings_total"
        ),
        "unresolved_row_parents_total": "doc6_unresolved_row_parents_total",
        "critical_row_mismatches_total": "doc6_critical_row_mismatches_total",
        "critical_entry_mismatches_total": (
            "doc6_critical_entry_mismatches_total"
        ),
    }
    for recovery_field, state_field in state_fields.items():
        assert acceptance[recovery_field] == recovery_values[recovery_field]
        assert state[state_field] == recovery_values[recovery_field]

    assert receipt["comparison"]["raw_critical_mismatches_total"] == 29
    assert receipt["comparison"]["raw_entry_surface_mismatches_total"] == 27
    assert receipt["comparison"][
        "raw_derived_header_path_mismatches_total"
    ] == 2
    for field in (
        "pdf_to_managed_document_v2_row_parity",
        "managed_document_v2_to_llm_view_v2_parity",
        "pdf_to_llm_view_v2_row_parity",
    ):
        assert receipt["comparison"][field] == "PASSED"
        assert state[f"doc6_{field}"] == "PASSED"
    assert receipt["seals"] == {
        **parity["seals"],
    }

    assert len(guide.split()) <= 2500
    for stale in ("DOC6 has not started", "DOC4, DOC6", "begin DOC6"):
        assert stale not in guide
        assert stale not in index
    assert "DOC6_LOGICAL_ROW_TABLE_MODEL = PASSED" in guide
    assert "| DOC6 inactive logical-row table recovery |" in index
    assert "RAW_BASE_CRITICAL_MISMATCHES_TOTAL = 29" in index

    for content in (report, brief):
        assert "tables = 28/28" in content or "28/28 таблиц" in content
        assert "357" in content
        assert "2338" in content
        assert "29" in content and "27" in content and "2" in content
        assert "PRODUCT_ACTIVATION = NOT_STARTED" in content


def test_doc6_public_evidence_contains_no_private_payload_or_local_path() -> None:
    for path in PUBLIC_DOCS:
        assert path.is_file()
        content = path.read_text(encoding="utf-8")
        assert LOCAL_PATH_PATTERN.search(content) is None, path
        assert ".private.json" not in content.lower(), path

    for path in (RECOVERY_PATH, PARITY_PATH, RECEIPT_PATH, STATE_PATH):
        payload = _read_json(path)
        assert FORBIDDEN_PRIVATE_PAYLOAD_KEYS.isdisjoint(_walk_keys(payload)), path

    recovery = _read_json(RECOVERY_PATH)
    parity = _read_json(PARITY_PATH)
    receipt = _read_json(RECEIPT_PATH)
    for privacy in (
        recovery["privacy"],
        parity["privacy"],
        receipt["privacy"],
    ):
        for field, value in privacy.items():
            if field.endswith("_included"):
                assert value is False
