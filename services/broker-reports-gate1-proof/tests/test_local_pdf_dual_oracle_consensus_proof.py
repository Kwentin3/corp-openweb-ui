from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "local_pdf_dual_oracle_consensus_proof.py"
)
SPEC = importlib.util.spec_from_file_location(
    "local_pdf_dual_oracle_consensus_proof", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
proof = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(proof)


def test_strict_json_rejects_duplicate_keys_and_nonfinite_numbers(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"a":1,"a":2}', encoding="utf-8")
    with pytest.raises(proof.ProofError, match="dual_oracle_json_duplicate_key"):
        proof._load_json(duplicate, dict, "fixture")

    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"a":NaN}', encoding="utf-8")
    with pytest.raises(proof.ProofError, match="dual_oracle_json_nonfinite_number"):
        proof._load_json(nonfinite, dict, "fixture")


def test_safe_payload_guard_rejects_identifiers_and_paths() -> None:
    proof._assert_safe_payload(
        {
            "table_key": "1:2",
            "terminal_status": "human_review_required",
            "result_checksum": "a" * 64,
        }
    )
    with pytest.raises(proof.ProofError, match="dual_oracle_safe_forbidden_key"):
        proof._assert_safe_payload({"candidate_ids": ["0"]})
    with pytest.raises(proof.ProofError, match="dual_oracle_safe_private_path_detected"):
        proof._assert_safe_payload({"message": r"C:\Users\someone\private.pdf"})


def test_safe_repeatability_summary_drops_private_identity_and_legacy_pass() -> None:
    v2 = proof._safe_repeatability_summary(
        {
            "schema_version": "broker_reports_pdf_dual_oracle_repeatability_record_v2",
            "attempt_history": [
                {
                    "attempt_id": "private-attempt",
                    "alternative_set_checksum": "a" * 64,
                }
            ],
            "supplied_history_structurally_complete": True,
            "attempt_alternative_sets_identical": True,
            "every_attempt_has_unique_consensus": True,
            "external_prior_conflict_claimed": False,
            "ever_conflicted": False,
            "passed": True,
            "crop_manifest_hash": "b" * 64,
        },
        accepted_by_solver=True,
    )
    assert v2["attempt_count"] == 1
    assert v2["current_supplied_set_passed"] is True
    assert v2["accepted_by_solver"] is True
    assert "attempt_history" not in v2
    assert "crop_manifest_hash" not in v2
    proof._assert_safe_payload(v2)

    legacy = proof._safe_repeatability_summary(
        {"required": True, "passed": True, "ever_conflicted": True},
        accepted_by_solver=True,
    )
    assert legacy["schema_version"] is None
    assert legacy["current_supplied_set_passed"] is False
    assert legacy["accepted_by_solver"] is False
    assert legacy["ever_conflicted"] is True


def test_diagnostic_score_resolves_only_candidate_dictionary_values() -> None:
    ledger = {
        "private_candidate_dictionary": {
            "0": {"exact_source_span": "Header"},
            "1": {"exact_source_span": "42"},
        }
    }
    binding = {
        "row_count": 2,
        "column_count": 1,
        "header_rows": [1],
        "rows": [
            {"row_ordinal": 1, "cells": [["0"]]},
            {"row_ordinal": 2, "cells": [["1"]]},
        ],
    }
    reference = {
        "rows": 2,
        "columns": 1,
        "header_rows": 1,
        "cells": [["Header"], ["42"]],
    }

    score = proof._score_binding(reference, binding, ledger)

    assert score == {
        "available": True,
        "reference_rows": 2,
        "reference_columns": 1,
        "predicted_rows": 2,
        "predicted_columns": 1,
        "structure_exact": True,
        "headers_exact": True,
        "cells_exact": 2,
        "cells_total": 2,
        "numeric_exact": 1,
        "numeric_total": 1,
        "empty_exact": 0,
        "empty_total": 0,
        "hallucinated_nonempty": 0,
        "omitted_nonempty": 0,
    }


def test_terminal_seal_contains_only_terminal_statuses_and_checksums() -> None:
    results = {
        key: {
            "terminal_status": "human_review_required",
            "result_checksum": key.replace(":", "") * 16,
            "unsealed_detail": object(),
        }
        for key in proof.TARGET_KEYS
    }
    continuation = {
        "terminal_status": "human_review_required",
        "result_checksum": "c" * 64,
        "unsealed_detail": object(),
    }

    seal = proof._terminal_seal(results, continuation)

    assert len(seal["tables"]) == 6
    assert all(set(item) == {"table_key", "terminal_status", "result_checksum"} for item in seal["tables"])
    assert set(seal["continuation"]) == {"terminal_status", "result_checksum"}


def test_unavailable_consensus_scores_do_not_create_aggregate_accuracy() -> None:
    score = proof._unavailable_score(
        {
            "rows": 2,
            "columns": 2,
            "header_rows": 1,
            "cells": [["A", ""], ["1", "2"]],
        }
    )

    aggregate = proof._aggregate_scores([score])

    assert aggregate["available_tables"] == 0
    assert aggregate["accuracy_status"] == "not_available"
    assert aggregate["cells_total"] == 0
    assert aggregate["cell_accuracy"] is None
