from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from broker_reports_gate1.gate2_financial_semantic_v5_preclose import (  # noqa: E402,E501
    FACTORY_REQUIRED,
    FORBIDDEN,
    V5_TECHNICAL_PRECLOSE_POLICY_VERSION,
    Gate2FinancialSemanticV5PrecloseError,
    Gate2FinancialSemanticV5PrecloseFactory,
    Gate2TechnicalPrecloseEvidence,
)
from test_broker_reports_gate2_financial_successor_projection_v3 import (  # noqa: E402,E501
    _scope_context,
)


SOURCE_PATH = (
    ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_v5_preclose.py"
)


def _evaluate(**overrides):
    values = {
        "source_support": "supported",
        "authoritative_layout_only": False,
        "source_value_candidates_total": 1,
        "scope_valid": True,
    }
    values.update(overrides)
    return Gate2FinancialSemanticV5PrecloseFactory().create(
        evidence=Gate2TechnicalPrecloseEvidence(**values)
    )


@pytest.mark.parametrize(
    "source_support",
    [
        "extractor_profile_unsupported",
        "source_shape_unsupported",
    ],
)
def test_unsupported_source_is_code_owned_terminal(source_support):
    result = _evaluate(
        source_support=source_support,
        source_value_candidates_total=0,
    )
    scope, _context, _registry = _scope_context(
        "syn_successor_signed_literal"
    )

    parsed = scope.decision_contract.parse_model_output(
        copy.deepcopy(result.canonical_decision)
    )
    assert result.status == "terminal"
    assert result.provider_call_required is False
    assert parsed.disposition == "unsupported"
    assert parsed.reason_code == source_support
    assert result.policy_version == V5_TECHNICAL_PRECLOSE_POLICY_VERSION


def test_authoritative_layout_without_values_is_code_owned_terminal():
    result = _evaluate(
        authoritative_layout_only=True,
        source_value_candidates_total=0,
    )
    scope, _context, _registry = _scope_context(
        "syn_successor_signed_literal"
    )

    parsed = scope.decision_contract.parse_model_output(
        copy.deepcopy(result.canonical_decision)
    )
    assert result.status == "terminal"
    assert result.provider_call_required is False
    assert parsed.disposition == "no_financial_input"
    assert parsed.reason_code == "header_or_layout"


def test_supported_content_with_values_requires_semantic_model():
    result = _evaluate(source_value_candidates_total=3)

    assert result.status == "model_required"
    assert result.provider_call_required is True
    assert result.canonical_decision is None
    assert len(result.technical_evidence_hash) == 64
    assert "Factory.create" in FACTORY_REQUIRED
    assert "must not inspect labels" in FORBIDDEN


@pytest.mark.parametrize(
    "overrides,code",
    [
        (
            {"scope_valid": False},
            "financial_semantic_v5_preclose_scope_invalid",
        ),
        (
            {
                "authoritative_layout_only": True,
                "source_value_candidates_total": 1,
            },
            "financial_semantic_v5_preclose_layout_value_conflict",
        ),
        (
            {"source_value_candidates_total": 0},
            "financial_semantic_v5_preclose_empty_content_scope",
        ),
        (
            {
                "source_support": "source_shape_unsupported",
                "authoritative_layout_only": True,
                "source_value_candidates_total": 0,
            },
            "financial_semantic_v5_preclose_evidence_conflict",
        ),
        (
            {"source_support": "unknown"},
            "financial_semantic_v5_preclose_evidence_invalid",
        ),
    ],
)
def test_invalid_or_damaged_technical_scope_fails_closed(overrides, code):
    with pytest.raises(
        Gate2FinancialSemanticV5PrecloseError,
        match=code,
    ):
        _evaluate(**overrides)


def test_preclose_has_no_semantic_classifier_or_benchmark_oracle():
    source = SOURCE_PATH.read_text(encoding="utf-8").casefold()
    for forbidden in (
        "cash",
        "tax",
        "fee",
        "dividend",
        "commission",
        "printed_financial_metric",
        "cash_balance_snapshot",
        "expected_answer",
        "re.compile",
        "import re",
    ):
        assert forbidden not in source
    assert "gate2_financial_domain_risk_benchmark" not in source
    assert set(Gate2TechnicalPrecloseEvidence.__dataclass_fields__) == {
        "source_support",
        "authoritative_layout_only",
        "source_value_candidates_total",
        "scope_valid",
    }
