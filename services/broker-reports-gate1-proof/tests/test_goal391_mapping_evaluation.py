from __future__ import annotations

from broker_reports_gate1.goal391_mapping_evaluation import (
    GOAL391_MAPPING_EVALUATOR_VERSION,
    normalized_trade_row_identity,
)


def test_row_identity_treats_only_visual_date_time_separators_as_equal() -> None:
    wrapped = "2026-01-01,\n12:00"
    inline = "2026-01-01 12:00"

    assert normalized_trade_row_identity(
        instrument_id=" abc ", timestamp=wrapped
    ) == normalized_trade_row_identity(instrument_id="ABC", timestamp=inline)
    assert wrapped == "2026-01-01,\n12:00"


def test_row_identity_does_not_hide_a_different_date_or_time() -> None:
    baseline = normalized_trade_row_identity(
        instrument_id="ABC", timestamp="2026-01-01, 12:00"
    )

    assert baseline != normalized_trade_row_identity(
        instrument_id="ABC", timestamp="2026-01-02 12:00"
    )
    assert baseline != normalized_trade_row_identity(
        instrument_id="ABC", timestamp="2026-01-01 12:01"
    )


def test_row_identity_rejects_missing_identity_parts() -> None:
    assert (
        normalized_trade_row_identity(instrument_id="", timestamp="2026-01-01 12:00")
        is None
    )
    assert normalized_trade_row_identity(instrument_id="ABC", timestamp=" \t") is None
    assert normalized_trade_row_identity(instrument_id="ABC", timestamp=12) is None


def test_evaluator_version_is_explicit() -> None:
    assert GOAL391_MAPPING_EVALUATOR_VERSION == "goal391_role_mapping_evaluator_v3"
