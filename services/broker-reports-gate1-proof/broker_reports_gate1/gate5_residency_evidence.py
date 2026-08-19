"""Typed residency evidence and one deterministic methodology interpretation."""

from __future__ import annotations

import copy
from datetime import date, timedelta
import hashlib
import json
import re
from typing import Any

from .gate5_trusted_methodology import (
    GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
    GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
    Gate5TrustedMethodologyAuthority,
    Gate5TrustedMethodologyAuthorityFactory,
)


GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION = (
    "broker_reports_gate5_residency_evidence_proposal_v0"
)
GATE5_RESIDENCY_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate5_residency_evidence_v0"
)
GATE5_RESIDENCY_CLASSIFICATION_SCHEMA_VERSION = (
    "broker_reports_gate5_residency_classification_v0"
)
GATE5_RESIDENCY_EVIDENCE_BOUNDARY_TERMINAL = (
    "RESIDENCY_EVIDENCE_BOUNDARY_PROVEN"
)

FACTORY_REQUIRED = (
    "Gate5ResidencyEvidenceRuntimeFactory.create composes "
    "Gate5TrustedMethodologyAuthorityFactory.create",
)
FORBIDDEN = (
    "user-authored resident or non-resident status, LLM tax classification, "
    "missing interval assumptions or unversioned residency rules",
)

_RULE_ID = "taxpayer-residency-article-207-v1"
_PROPOSAL_KEYS = frozenset(
    {
        "schema_version",
        "tax_period",
        "window_start",
        "window_end",
        "presence_intervals",
        "absence_intervals",
        "absence_reason_evidence",
        "all_absence_reasons_reported",
        "evidence_refs",
    }
)
_INTERVAL_KEYS = frozenset({"start_date", "end_date"})
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class Gate5ResidencyEvidenceError(ValueError):
    def __init__(self, code: str, field: str = "") -> None:
        self.code = code
        self.field = field
        super().__init__(code if not field else f"{code}:{field}")


class Gate5ResidencyEvidenceRuntimeFactory:
    @staticmethod
    def create() -> "Gate5ResidencyEvidenceRuntime":
        return Gate5ResidencyEvidenceRuntime(
            authority=Gate5TrustedMethodologyAuthorityFactory.create()
        )


class Gate5ResidencyEvidenceRuntime:
    def __init__(self, *, authority: Gate5TrustedMethodologyAuthority) -> None:
        self._authority = authority

    def normalize_human_answer(
        self,
        *,
        human_answer: str,
        proposal: dict[str, Any],
        source_ref: str,
    ) -> dict[str, Any]:
        """Validate an adapter proposal against the bounded human text."""

        if (
            not isinstance(human_answer, str)
            or not human_answer.strip()
            or len(human_answer) > 4000
            or not _identifier(source_ref)
        ):
            _fail("gate5_residency_human_answer_invalid")
        normalized = _validated_proposal(proposal, human_answer=human_answer)
        presence_days = _covered_days(normalized["presence_intervals"])
        absence_days = _covered_days(normalized["absence_intervals"])
        if presence_days & absence_days:
            _fail("gate5_residency_interval_overlap")
        window_days = _date_range(
            date.fromisoformat(normalized["window_start"]),
            date.fromisoformat(normalized["window_end"]),
        )
        covered_days = presence_days | absence_days
        coverage_status = (
            "COMPLETE_WINDOW" if covered_days == window_days else "PARTIAL_WINDOW"
        )
        reasons = normalized["absence_reason_evidence"]
        exception_status = (
            "NO_RELEVANT_REASON_REPORTED"
            if normalized["all_absence_reasons_reported"] and not reasons
            else "REVIEW_REQUIRED"
        )
        evidence = {
            "schema_version": GATE5_RESIDENCY_EVIDENCE_SCHEMA_VERSION,
            "fact_key": "residency_evidence",
            "tax_period": normalized["tax_period"],
            "window": {
                "start_date": normalized["window_start"],
                "end_date": normalized["window_end"],
            },
            "presence_intervals": copy.deepcopy(normalized["presence_intervals"]),
            "absence_intervals": copy.deepcopy(normalized["absence_intervals"]),
            "presence_days": len(presence_days),
            "absence_days": len(absence_days),
            "interval_coverage": coverage_status,
            "absence_reason_evidence": copy.deepcopy(reasons),
            "absence_reason_coverage": (
                "COMPLETE"
                if normalized["all_absence_reasons_reported"]
                else "INCOMPLETE"
            ),
            "exception_review_status": exception_status,
            "evidence_refs": copy.deepcopy(normalized["evidence_refs"]),
            "provenance": {
                "source_kind": "authenticated_user_case_fact",
                "source_ref": source_ref,
                "input_channel": "residency_evidence",
                "human_answer_sha256": hashlib.sha256(
                    human_answer.encode("utf-8")
                ).hexdigest(),
                "adapter_proposal_validated": True,
                "calculation_authority": False,
                "user_tax_status_accepted": False,
            },
        }
        return _validated_evidence(evidence)

    def classify(self, *, evidence: dict[str, Any] | None) -> dict[str, Any]:
        resolved = self._authority.resolve(
            {
                "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                "methodology_id": GATE5_DECLARATION_INPUT_METHODOLOGY_ID,
                "methodology_version": GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION,
            }
        )
        rule = _residency_rule(resolved["methodology"])
        binding = {
            **copy.deepcopy(resolved["authority_binding"]),
            "rule_id": rule["rule_id"],
        }
        if evidence is None:
            return _classification(
                binding=binding,
                status="INSUFFICIENT_EVIDENCE",
                period_status=None,
                reason="residency_evidence_missing",
                evidence_sha256=None,
                presence_days=None,
            )
        validated = _validated_evidence(evidence)
        evidence_sha256 = _canonical_sha256(validated)
        if (
            validated["absence_reason_coverage"] != "COMPLETE"
            or validated["exception_review_status"] != "NO_RELEVANT_REASON_REPORTED"
        ):
            return _classification(
                binding=binding,
                status="INSUFFICIENT_EVIDENCE",
                period_status=None,
                reason="article_207_exception_evidence_requires_review",
                evidence_sha256=evidence_sha256,
                presence_days=validated["presence_days"],
            )
        if validated["presence_days"] >= 183:
            return _classification(
                binding=binding,
                status="RESIDENT",
                period_status="resident_individual",
                reason="presence_days_gte_183",
                evidence_sha256=evidence_sha256,
                presence_days=validated["presence_days"],
            )
        if validated["interval_coverage"] == "COMPLETE_WINDOW":
            return _classification(
                binding=binding,
                status="NON_RESIDENT",
                period_status="nonresident_individual",
                reason="complete_window_presence_days_lt_183",
                evidence_sha256=evidence_sha256,
                presence_days=validated["presence_days"],
            )
        return _classification(
            binding=binding,
            status="INSUFFICIENT_EVIDENCE",
            period_status=None,
            reason="presence_interval_coverage_incomplete",
            evidence_sha256=evidence_sha256,
            presence_days=validated["presence_days"],
        )


def gate5_residency_methodology_input(
    classification: Any, *, input_channel: str
) -> dict[str, Any]:
    """Bind only a successful owned classification to a downstream consumer."""

    allowed_channels = {"minimal_tax_context", "taxpayer_status"}
    binding = (
        classification.get("methodology_binding")
        if isinstance(classification, dict)
        else None
    )
    status_map = {
        "RESIDENT": "resident_individual",
        "NON_RESIDENT": "nonresident_individual",
    }
    status = classification.get("status") if isinstance(classification, dict) else None
    if (
        not isinstance(classification, dict)
        or classification.get("schema_version")
        != GATE5_RESIDENCY_CLASSIFICATION_SCHEMA_VERSION
        or status not in status_map
        or classification.get("period_status") != status_map[status]
        or classification.get("terminals")
        != [GATE5_RESIDENCY_EVIDENCE_BOUNDARY_TERMINAL]
        or classification.get("calculation_authority")
        != "Gate5ResidencyEvidenceRuntimeFactory.create"
        or classification.get("user_tax_status_accepted") is not False
        or not isinstance(binding, dict)
        or binding.get("methodology_id") != GATE5_DECLARATION_INPUT_METHODOLOGY_ID
        or binding.get("methodology_version")
        != GATE5_DECLARATION_INPUT_METHODOLOGY_VERSION
        or binding.get("rule_id") != _RULE_ID
        or input_channel not in allowed_channels
    ):
        _fail("gate5_residency_classification_input_invalid")
    return {
        "value": classification["period_status"],
        "provenance": {
            "source_kind": "methodology_derived_result",
            "source_ref": "residency-classification:" + _canonical_sha256(classification),
            "input_channel": input_channel,
        },
    }


def _validated_proposal(value: Any, *, human_answer: str) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _PROPOSAL_KEYS
        or value.get("schema_version")
        != GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION
        or not isinstance(value.get("tax_period"), str)
        or re.fullmatch(r"[0-9]{4}", value["tax_period"]) is None
        or not isinstance(value.get("all_absence_reasons_reported"), bool)
        or not isinstance(value.get("absence_reason_evidence"), list)
        or not all(
            isinstance(item, str)
            and item.strip()
            and len(item) <= 256
            and item.casefold() in human_answer.casefold()
            for item in value["absence_reason_evidence"]
        )
        or not _evidence_refs(value.get("evidence_refs"))
    ):
        _fail("gate5_residency_evidence_proposal_invalid")
    start = _iso_date(value.get("window_start"), "window_start")
    end = _iso_date(value.get("window_end"), "window_end")
    if (
        start > end
        or start != date(int(value["tax_period"]), 1, 1)
        or end != date(int(value["tax_period"]), 12, 31)
    ):
        _fail("gate5_residency_window_invalid")
    presence = _validated_intervals(
        value.get("presence_intervals"), human_answer=human_answer, window=(start, end)
    )
    absence = _validated_intervals(
        value.get("absence_intervals"), human_answer=human_answer, window=(start, end)
    )
    return {
        **copy.deepcopy(value),
        "presence_intervals": presence,
        "absence_intervals": absence,
        "absence_reason_evidence": [item.strip() for item in value["absence_reason_evidence"]],
        "evidence_refs": sorted(value["evidence_refs"]),
    }


def _validated_intervals(
    value: Any, *, human_answer: str, window: tuple[date, date]
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        _fail("gate5_residency_intervals_invalid")
    result = []
    covered: set[date] = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != _INTERVAL_KEYS:
            _fail("gate5_residency_intervals_invalid")
        start = _iso_date(item.get("start_date"), "start_date")
        end = _iso_date(item.get("end_date"), "end_date")
        if start > end or start < window[0] or end > window[1]:
            _fail("gate5_residency_intervals_invalid")
        if not _date_is_supported(start, human_answer) or not _date_is_supported(
            end, human_answer
        ):
            _fail("gate5_residency_interval_not_supported_by_answer")
        days = _date_range(start, end)
        if covered & days:
            _fail("gate5_residency_interval_overlap")
        covered |= days
        result.append({"start_date": start.isoformat(), "end_date": end.isoformat()})
    return sorted(result, key=lambda item: (item["start_date"], item["end_date"]))


def _validated_evidence(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != GATE5_RESIDENCY_EVIDENCE_SCHEMA_VERSION
        or value.get("fact_key") != "residency_evidence"
        or value.get("interval_coverage") not in {"COMPLETE_WINDOW", "PARTIAL_WINDOW"}
        or value.get("absence_reason_coverage") not in {"COMPLETE", "INCOMPLETE"}
        or value.get("exception_review_status")
        not in {"NO_RELEVANT_REASON_REPORTED", "REVIEW_REQUIRED"}
        or not isinstance(value.get("presence_days"), int)
        or isinstance(value.get("presence_days"), bool)
        or not isinstance(value.get("absence_days"), int)
        or isinstance(value.get("absence_days"), bool)
        or not isinstance(value.get("provenance"), dict)
        or value["provenance"].get("source_kind")
        != "authenticated_user_case_fact"
        or value["provenance"].get("calculation_authority") is not False
        or value["provenance"].get("user_tax_status_accepted") is not False
    ):
        _fail("gate5_residency_evidence_invalid")
    return copy.deepcopy(value)


def _residency_rule(methodology: Any) -> dict[str, Any]:
    rules = methodology.get("rules") if isinstance(methodology, dict) else None
    matches = [item for item in rules or [] if item.get("rule_id") == _RULE_ID]
    if (
        len(matches) != 1
        or matches[0].get("operation") != "COMPARE"
        or matches[0].get("output") != "taxpayer_period_status"
        or matches[0].get("insufficient_inputs") != "FAIL_CLOSED"
        or matches[0].get("authority_refs") != ["nk-rf-article-207-paragraph-2"]
    ):
        _fail("gate5_residency_methodology_invalid")
    return copy.deepcopy(matches[0])


def _classification(
    *,
    binding: dict[str, Any],
    status: str,
    period_status: str | None,
    reason: str,
    evidence_sha256: str | None,
    presence_days: int | None,
) -> dict[str, Any]:
    return {
        "schema_version": GATE5_RESIDENCY_CLASSIFICATION_SCHEMA_VERSION,
        "status": status,
        "period_status": period_status,
        "reason": reason,
        "presence_days": presence_days,
        "evidence_sha256": evidence_sha256,
        "methodology_binding": copy.deepcopy(binding),
        "terminals": [GATE5_RESIDENCY_EVIDENCE_BOUNDARY_TERMINAL],
        "calculation_authority": "Gate5ResidencyEvidenceRuntimeFactory.create",
        "user_tax_status_accepted": False,
    }


def _covered_days(intervals: list[dict[str, str]]) -> set[date]:
    result: set[date] = set()
    for item in intervals:
        result |= _date_range(
            date.fromisoformat(item["start_date"]), date.fromisoformat(item["end_date"])
        )
    return result


def _date_range(start: date, end: date) -> set[date]:
    return {start + timedelta(days=offset) for offset in range((end - start).days + 1)}


def _iso_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        _fail("gate5_residency_date_invalid", field)
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise Gate5ResidencyEvidenceError(
            "gate5_residency_date_invalid", field
        ) from exc
    if parsed.isoformat() != value:
        _fail("gate5_residency_date_invalid", field)
    return parsed


def _date_is_supported(value: date, human_answer: str) -> bool:
    return value.isoformat() in human_answer or value.strftime("%d.%m.%Y") in human_answer


def _evidence_refs(value: Any) -> bool:
    return (
        isinstance(value, list)
        and value
        and value == sorted(set(value))
        and all(_identifier(item) for item in value)
    )


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _fail(code: str, field: str = "") -> None:
    raise Gate5ResidencyEvidenceError(code, field)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_RESIDENCY_CLASSIFICATION_SCHEMA_VERSION",
    "GATE5_RESIDENCY_EVIDENCE_BOUNDARY_TERMINAL",
    "GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION",
    "GATE5_RESIDENCY_EVIDENCE_SCHEMA_VERSION",
    "Gate5ResidencyEvidenceError",
    "Gate5ResidencyEvidenceRuntime",
    "Gate5ResidencyEvidenceRuntimeFactory",
    "gate5_residency_methodology_input",
]
