from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from .gate2_financial_evidence_decision import (
    NO_FINANCIAL_REASON_CODES,
    UNSUPPORTED_REASON_CODES,
)


V5_TECHNICAL_PRECLOSE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v5_preclose_v1"
)
V5_TECHNICAL_PRECLOSE_POLICY_VERSION = (
    "broker_reports_gate2_technical_preclose_policy_v1"
)
V5_SUPPORTED_SOURCE = "supported"
V5_UNSUPPORTED_SOURCE_REASONS = frozenset(
    {
        "extractor_profile_unsupported",
        "source_shape_unsupported",
    }
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV5PrecloseFactory.create is the only V5 "
    "technical preclose entrypoint"
)
FORBIDDEN = (
    "Technical preclose must not inspect labels, literals, type IDs, Pack "
    "meanings, expected benchmark outcomes, or semantic regular expressions"
)


class Gate2FinancialSemanticV5PrecloseError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2TechnicalPrecloseEvidence:
    source_support: str
    authoritative_layout_only: bool
    source_value_candidates_total: int
    scope_valid: bool


@dataclass(frozen=True)
class Gate2TechnicalPrecloseResult:
    schema_version: str
    policy_version: str
    status: str
    provider_call_required: bool
    canonical_decision: dict[str, Any] | None
    technical_evidence_hash: str


class Gate2FinancialSemanticV5PrecloseFactory:
    def create(
        self,
        *,
        evidence: Gate2TechnicalPrecloseEvidence,
    ) -> Gate2TechnicalPrecloseResult:
        _validate_evidence(evidence)
        evidence_hash = _sha256_json(asdict(evidence))
        if evidence.source_support in V5_UNSUPPORTED_SOURCE_REASONS:
            return Gate2TechnicalPrecloseResult(
                schema_version=V5_TECHNICAL_PRECLOSE_SCHEMA_VERSION,
                policy_version=V5_TECHNICAL_PRECLOSE_POLICY_VERSION,
                status="terminal",
                provider_call_required=False,
                canonical_decision={
                    "decision": {
                        "disposition": "unsupported",
                        "reason_code": evidence.source_support,
                    }
                },
                technical_evidence_hash=evidence_hash,
            )
        if evidence.authoritative_layout_only:
            return Gate2TechnicalPrecloseResult(
                schema_version=V5_TECHNICAL_PRECLOSE_SCHEMA_VERSION,
                policy_version=V5_TECHNICAL_PRECLOSE_POLICY_VERSION,
                status="terminal",
                provider_call_required=False,
                canonical_decision={
                    "decision": {
                        "disposition": "no_financial_input",
                        "reason_code": "header_or_layout",
                    }
                },
                technical_evidence_hash=evidence_hash,
            )
        return Gate2TechnicalPrecloseResult(
            schema_version=V5_TECHNICAL_PRECLOSE_SCHEMA_VERSION,
            policy_version=V5_TECHNICAL_PRECLOSE_POLICY_VERSION,
            status="model_required",
            provider_call_required=True,
            canonical_decision=None,
            technical_evidence_hash=evidence_hash,
        )


def _validate_evidence(evidence: Any) -> None:
    if not isinstance(evidence, Gate2TechnicalPrecloseEvidence):
        _fail("financial_semantic_v5_preclose_evidence_invalid")
    if evidence.scope_valid is not True:
        _fail("financial_semantic_v5_preclose_scope_invalid")
    if (
        evidence.source_support
        not in {V5_SUPPORTED_SOURCE, *V5_UNSUPPORTED_SOURCE_REASONS}
        or not isinstance(evidence.authoritative_layout_only, bool)
        or isinstance(evidence.source_value_candidates_total, bool)
        or not isinstance(evidence.source_value_candidates_total, int)
        or evidence.source_value_candidates_total < 0
        or evidence.source_value_candidates_total > 64
    ):
        _fail("financial_semantic_v5_preclose_evidence_invalid")
    if (
        evidence.source_support != V5_SUPPORTED_SOURCE
        and evidence.authoritative_layout_only
    ):
        _fail("financial_semantic_v5_preclose_evidence_conflict")
    if (
        evidence.authoritative_layout_only
        and evidence.source_value_candidates_total != 0
    ):
        _fail("financial_semantic_v5_preclose_layout_value_conflict")
    if (
        evidence.source_support == V5_SUPPORTED_SOURCE
        and not evidence.authoritative_layout_only
        and evidence.source_value_candidates_total == 0
    ):
        _fail("financial_semantic_v5_preclose_empty_content_scope")
    if (
        "header_or_layout" not in NO_FINANCIAL_REASON_CODES
        or not V5_UNSUPPORTED_SOURCE_REASONS.issubset(
            UNSUPPORTED_REASON_CODES
        )
    ):
        _fail("financial_semantic_v5_preclose_canonical_contract_mismatch")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV5PrecloseError(code)
