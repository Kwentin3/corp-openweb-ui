from __future__ import annotations

from broker_reports_gate1 import (
    Gate2TablePackageFactory,
    PdfVisualTableReviewFactory,
    VisualReviewAuthorityContext,
    validate_gate2_table_package,
    validate_reviewed_visual_projection,
)
from broker_reports_gate1.pdf_dual_vlm_canonical_table_contracts import (
    compare_tables,
    sha256_json,
)
from broker_reports_gate1.pdf_visual_table_review import (
    VISUAL_REVIEW_SUBMISSION_SCHEMA_VERSION,
)
from scripts.prove_broker_reports_goal5_integrated_actual_corpus import (
    _attestations,
    _build_region_accounting_submission,
    build_candidate_from_literal_reference,
)
from tests.test_broker_reports_visual_table_review_promotion import _decision


def test_literal_reference_review_reaches_terminal_gate2_package() -> None:
    decision = _decision(openai_value="11")
    reference = {
        "entries": [
            _entry("Cash", ["Minimum", "Office"], "$ 10"),
            _entry("Cash", ["Retail"], "$ 20"),
            _entry("Total", ["Minimum", "Office"], "$ 30"),
            _entry("Total", ["Retail"], "$ 40"),
        ]
    }
    candidate = build_candidate_from_literal_reference(
        table=reference,
        table_id=decision["source_lineage"]["candidate_ref"],
        sparse_currency_columns=True,
    )
    comparison = compare_tables(decision["proposals"]["gemini"], candidate)
    differences = comparison["differences"]
    changed_cells = {
        tuple(item["cell"])
        for item in differences
        if isinstance(item.get("cell"), list) and len(item["cell"]) == 2
    }
    accounting = _build_region_accounting_submission(
        decision=decision,
        candidate=candidate,
        geometry={
            "row_edges": [0.1, 0.2, 0.3, 0.5, 0.7],
            "column_edges": [0.1, 0.3, 0.4, 0.55, 0.65, 0.8],
        },
        corrected_cells=changed_cells,
    )
    submission = {
        "schema_version": VISUAL_REVIEW_SUBMISSION_SCHEMA_VERSION,
        "reviewed_at": "2026-07-21T21:30:00+03:00",
        "review_decision": "accepted_with_correction",
        "decision_reason_codes": ["source_crop_review_completed"],
        "selected_proposal_provider": "gemini",
        "canonical_candidate": candidate,
        "correction_acknowledgements": [
            {
                "difference_sha256": sha256_json(item),
                "reviewer_reason_code": "source_crop_verified_correction",
            }
            for item in differences
        ],
        "region_cell_accounting": accounting,
        "attestations": _attestations(accepted=True),
    }
    result = PdfVisualTableReviewFactory().create(
        authority=VisualReviewAuthorityContext(
            authenticated_user_id="delegating-user",
            reviewer_id="codex-technical-reviewer",
            reviewer_type="delegated_agent_reviewed",
            authority_ref="user_delegation_goal5_2026_07_21",
        )
    ).review(decision=decision, submission=submission)

    assert candidate["row_count"] == 4
    assert candidate["column_count"] == 5
    assert result.review_receipt["decision"] == "accepted_with_correction"
    assert result.review_receipt["region_cell_accounting_summary"][
        "source_region_inventory_complete"
    ] is True
    assert result.canonical_projection is not None
    assert validate_reviewed_visual_projection(result.canonical_projection)[
        "validator_status"
    ] == "passed"
    package = Gate2TablePackageFactory().create().build(
        projection=result.canonical_projection,
        case_id="goal5-test-case",
    )
    assert validate_gate2_table_package(
        package, result.canonical_projection
    )["validator_status"] == "passed"
    assert package["upstream_source_representation"]["reviewer_type"] == (
        "delegated_agent_reviewed"
    )
    assert package["prompt_contract"]["model_call_performed"] is False


def _entry(row: str, header: list[str], value: str) -> dict[str, object]:
    return {
        "row_label_text": row,
        "column_header_path": header,
        "visible_value_text": value,
        "cell_state": "value",
    }
