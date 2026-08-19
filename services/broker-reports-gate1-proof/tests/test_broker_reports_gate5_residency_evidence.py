from __future__ import annotations

import pytest

from broker_reports_gate1 import (
    GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
    GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
    GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
    Gate5ResidencyEvidenceError,
    Gate5ResidencyEvidenceRuntimeFactory,
    gate5_residency_methodology_input,
)


def test_natural_language_presence_intervals_become_typed_evidence_then_resident() -> None:
    runtime = Gate5ResidencyEvidenceRuntimeFactory.create()
    evidence = runtime.normalize_human_answer(
        human_answer=(
            "В 2025 году я находился в России с 01.01.2025 по 02.07.2025, "
            "а отсутствовал с 03.07.2025 по 31.12.2025. Иных причин отсутствия нет."
        ),
        proposal=_proposal(
            presence=[("2025-01-01", "2025-07-02")],
            absence=[("2025-07-03", "2025-12-31")],
            all_reasons=True,
        ),
        source_ref="residency-request-1",
    )

    assert evidence["presence_days"] == 183
    assert evidence["interval_coverage"] == "COMPLETE_WINDOW"
    assert evidence["provenance"]["calculation_authority"] is False
    assert evidence["provenance"]["user_tax_status_accepted"] is False
    assert "human_answer" not in evidence

    result = runtime.classify(evidence=evidence)

    assert result["status"] == "RESIDENT"
    assert result["period_status"] == "resident_individual"
    assert result["reason"] == "presence_days_gte_183"
    assert result["methodology_binding"]["methodology_id"] == (
        GATE5_DECLARATION_INPUT_METHODOLOGY_ID
    )
    assert result["methodology_binding"]["methodology_version"] == (
        GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION
    )
    assert result["methodology_binding"]["rule_id"] == (
        "taxpayer-residency-article-207-v1"
    )
    downstream = gate5_residency_methodology_input(
        result, input_channel="minimal_tax_context"
    )
    assert downstream["value"] == "resident_individual"
    assert downstream["provenance"]["source_kind"] == "methodology_derived_result"
    assert downstream["provenance"]["source_ref"].startswith(
        "residency-classification:"
    )
    assert downstream["provenance"]["input_channel"] == "minimal_tax_context"


def test_user_resident_claim_without_interval_evidence_is_not_authoritative() -> None:
    runtime = Gate5ResidencyEvidenceRuntimeFactory.create()
    evidence = runtime.normalize_human_answer(
        human_answer="Я налоговый резидент.",
        proposal=_proposal(presence=[], absence=[], all_reasons=False),
        source_ref="residency-request-2",
    )

    result = runtime.classify(evidence=evidence)

    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["period_status"] is None
    assert result["user_tax_status_accepted"] is False
    assert result["reason"] == "article_207_exception_evidence_requires_review"


def test_complete_window_under_183_days_becomes_nonresident_by_methodology() -> None:
    runtime = Gate5ResidencyEvidenceRuntimeFactory.create()
    evidence = runtime.normalize_human_answer(
        human_answer=(
            "В 2025 году был в России 01.01.2025, затем отсутствовал "
            "с 02.01.2025 по 31.12.2025. Других причин отсутствия нет."
        ),
        proposal=_proposal(
            presence=[("2025-01-01", "2025-01-01")],
            absence=[("2025-01-02", "2025-12-31")],
            all_reasons=True,
        ),
        source_ref="residency-request-3",
    )

    result = runtime.classify(evidence=evidence)

    assert result["status"] == "NON_RESIDENT"
    assert result["period_status"] == "nonresident_individual"
    assert result["presence_days"] == 1


def test_adapter_cannot_invent_interval_dates_absent_from_human_answer() -> None:
    runtime = Gate5ResidencyEvidenceRuntimeFactory.create()
    proposal = _proposal(
        presence=[("2025-01-01", "2025-07-02")],
        absence=[],
        all_reasons=True,
    )

    with pytest.raises(Gate5ResidencyEvidenceError) as caught:
        runtime.normalize_human_answer(
            human_answer="Я был в России больше половины года.",
            proposal=proposal,
            source_ref="residency-request-4",
        )

    assert caught.value.code == "gate5_residency_interval_not_supported_by_answer"


def test_tax_status_field_is_not_part_of_the_adapter_proposal_contract() -> None:
    runtime = Gate5ResidencyEvidenceRuntimeFactory.create()
    proposal = _proposal(presence=[], absence=[], all_reasons=False)
    proposal["tax_status"] = "resident_individual"

    with pytest.raises(Gate5ResidencyEvidenceError) as caught:
        runtime.normalize_human_answer(
            human_answer="Я налоговый резидент.",
            proposal=proposal,
            source_ref="residency-request-5",
        )

    assert caught.value.code == "gate5_residency_evidence_proposal_invalid"


def _proposal(
    *,
    presence: list[tuple[str, str]],
    absence: list[tuple[str, str]],
    all_reasons: bool,
) -> dict:
    return {
        "schema_version": GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
        "tax_period": "2025",
        "window_start": "2025-01-01",
        "window_end": "2025-12-31",
        "presence_intervals": [
            {"start_date": start, "end_date": end} for start, end in presence
        ],
        "absence_intervals": [
            {"start_date": start, "end_date": end} for start, end in absence
        ],
        "absence_reason_evidence": [],
        "all_absence_reasons_reported": all_reasons,
        "evidence_refs": ["authenticated-human-answer"],
    }
