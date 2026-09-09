from __future__ import annotations

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import qualify_goal391_instructional_classification_lab as lab


def _expected(disposition: str, no_consumer_kind: str | None = None) -> dict:
    return {"expected_assessment": {"required_table_decisions": [{"disposition": disposition, "no_consumer_kind": no_consumer_kind}]}}


def test_expected_instructional_label_is_derived_from_existing_mapping_decision() -> None:
    assert lab._expected_classification(_expected("NO_NAMED_CONSUMER", "INSTRUCTIONAL_REFERENCE")) == "INSTRUCTIONAL_REFERENCE"
    assert lab._expected_classification(_expected("SECURITY_TRADES")) == "NOT_INSTRUCTIONAL"


def test_unknown_or_ambiguous_expectations_fail_closed() -> None:
    with pytest.raises(ValueError):
        lab._expected_classification(_expected("NO_NAMED_CONSUMER", "OTHER"))
    with pytest.raises(ValueError):
        lab._expected_classification({"expected_assessment": {"required_table_decisions": []}})


def test_response_content_accepts_exactly_one_choice_message() -> None:
    assert lab._response_content({"choices": [{"message": {"content": "{}"}}]}) == "{}"
    assert lab._response_content({"choices": []}) is None
