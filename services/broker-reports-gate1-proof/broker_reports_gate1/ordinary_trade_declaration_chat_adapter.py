"""Representation-only chat adapter for owner-published declaration requests."""

from __future__ import annotations

import re
from typing import Any

from .gate5_residency_evidence import (
    GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
)


ORDINARY_TRADE_DECLARATION_CHAT_ACTION_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_declaration_chat_action_v1"
)
FACTORY_REQUIRED = (
    "Pipe obtains the current request from OrdinaryTradeProductionRuntimeFactory "
    "and passes that owner-produced request to this representation-only adapter"
)
FORBIDDEN = (
    "caller-selected request ref, fact key, taxpayer ref, source or methodology "
    "conclusion, persistence, currentness or calculation authority"
)

_CONFIRM = frozenset({"да", "подтверждаю", "подтвердить", "верно"})
_REJECT = frozenset({"нет", "неверно"})
_DEFER = frozenset({"позже", "отложить", "заполню позже"})
_PROMPT_ONLY = frozenset(
    {
        "подготовить 3-ндфл",
        "подготовь 3-ндфл",
        "продолжить подготовку 3-ндфл",
        "продолжить",
    }
)
_CHANGE_INTENTS = {
    "изменить дату": "declaration_date",
    "изменить инн": "taxpayer_identity",
}
_IDENTITY = re.compile(
    r"^изменить:\s*([0-9]{12})\s*;\s*([^;]{1,80})\s*;\s*"
    r"([^;]{1,80})\s*;\s*([^;]{0,80})$",
    re.IGNORECASE,
)
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_RESIDENCY = re.compile(
    r"^присутствие:\s*([0-9]{4}-[0-9]{2}-[0-9]{2})\.\."
    r"([0-9]{4}-[0-9]{2}-[0-9]{2})\s*;\s*отсутствие:\s*"
    r"([0-9]{4}-[0-9]{2}-[0-9]{2})\.\."
    r"([0-9]{4}-[0-9]{2}-[0-9]{2})\s*;\s*причины:\s*нет$",
    re.IGNORECASE,
)


def declaration_change_intent(message: str) -> dict[str, Any] | None:
    """Recognize only bounded display phrases; never accept a caller fact key."""

    text = _text(message)
    lowered = text.casefold()
    for phrase, fact_key in _CHANGE_INTENTS.items():
        if lowered == phrase:
            return {
                "schema_version": ORDINARY_TRADE_DECLARATION_CHAT_ACTION_SCHEMA_VERSION,
                "status": "CHANGE_REQUESTED",
                "fact_key": fact_key,
                "answer": None,
            }
        prefix = phrase + ":"
        if lowered.startswith(prefix):
            value = text[len(prefix) :].strip()
            if fact_key == "declaration_date":
                answer = {"kind": "text", "value": value}
            else:
                match = _IDENTITY.fullmatch("Изменить: " + value)
                answer = _identity_answer(match) if match else None
            return {
                "schema_version": ORDINARY_TRADE_DECLARATION_CHAT_ACTION_SCHEMA_VERSION,
                "status": "CHANGE_ANSWER_READY" if answer else "ANSWER_REJECTED",
                "fact_key": fact_key,
                "answer": answer,
                "reason_code": None if answer else "declaration_chat_change_format_invalid",
            }
    return None


def adapt_current_declaration_request(
    *, message: str, current_requests: list[dict[str, Any]]
) -> dict[str, Any]:
    """Adapt one normal chat message to the first current owner request."""

    if not isinstance(current_requests, list) or not current_requests:
        return _result("NO_CURRENT_REQUEST")
    request = current_requests[0]
    if (
        not isinstance(request, dict)
        or not isinstance(request.get("request_publication_ref"), str)
        or not request["request_publication_ref"]
        or request.get("closure_type") != "USER_FACT"
        or not isinstance(request.get("answer_contract"), dict)
    ):
        return _result("OWNER_REQUEST_INVALID", reason_code="declaration_chat_owner_request_invalid")
    text = _text(message)
    if not text:
        return _result("NO_ANSWER")
    if text.casefold() in _PROMPT_ONLY:
        return _result("NO_ANSWER")
    contract = request["answer_contract"]
    answer = _answer(contract=contract, text=text)
    if answer is None:
        return {
            **_result("ANSWER_REJECTED", reason_code="declaration_chat_answer_invalid"),
            "request_publication_ref": request["request_publication_ref"],
        }
    return {
        **_result("ANSWER_READY"),
        "request_publication_ref": request["request_publication_ref"],
        "answer": answer,
    }


def declaration_request_help(request: dict[str, Any]) -> str:
    contract = request.get("answer_contract")
    contract = contract if isinstance(contract, dict) else {}
    kind = contract.get("kind")
    if kind == "identity_choice":
        return (
            "Ответьте «Подтверждаю», «Позже» или "
            "«Изменить: ИНН; Фамилия; Имя; Отчество»."
        )
    if kind == "confirmation":
        return "Ответьте «Да» или «Нет»."
    if kind == "residency_evidence":
        return (
            "Формат: «Присутствие: ГГГГ-ММ-ДД..ГГГГ-ММ-ДД; "
            "отсутствие: ГГГГ-ММ-ДД..ГГГГ-ММ-ДД; причины: нет»."
        )
    allowed = contract.get("allowed")
    if isinstance(allowed, list) and allowed:
        return "Допустимые значения: " + ", ".join(map(str, allowed)) + "."
    if request.get("fact_key") == "declaration_date":
        return "Введите календарную дату в формате ГГГГ-ММ-ДД."
    if contract.get("pattern"):
        return "Введите значение в указанном формате."
    return "Введите точное значение."


def _answer(*, contract: dict[str, Any], text: str) -> dict[str, Any] | None:
    kind = contract.get("kind")
    lowered = text.casefold()
    if kind == "identity_choice":
        if lowered in _CONFIRM:
            return {"kind": kind, "value": {"choice": "CONFIRM", "identity": None}}
        if lowered in _DEFER:
            return {"kind": kind, "value": {"choice": "DEFER", "identity": None}}
        match = _IDENTITY.fullmatch(text)
        return _identity_answer(match) if match else None
    if kind == "confirmation":
        if lowered in _CONFIRM:
            return {"kind": kind, "value": True}
        if lowered in _REJECT:
            return {"kind": kind, "value": False}
        return None
    if kind == "residency_evidence":
        match = _RESIDENCY.fullmatch(text)
        if match is None:
            return None
        present_start, present_end, absent_start, absent_end = match.groups()
        return {
            "kind": kind,
            "value": {
                "human_answer": text,
                "proposal": {
                    "schema_version": GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
                    "tax_period": "2025",
                    "window_start": "2025-01-01",
                    "window_end": "2025-12-31",
                    "presence_intervals": [
                        {"start_date": present_start, "end_date": present_end}
                    ],
                    "absence_intervals": [
                        {"start_date": absent_start, "end_date": absent_end}
                    ],
                    "absence_reason_evidence": [],
                    "all_absence_reasons_reported": True,
                    "evidence_refs": ["owner_bound_chat_answer"],
                },
            },
        }
    if kind == "code":
        allowed = contract.get("allowed")
        value = text.strip()
        if isinstance(allowed, list) and value not in allowed:
            return None
        return {"kind": kind, "value": value}
    if kind == "text":
        return {"kind": kind, "value": text.strip()}
    return None


def _identity_answer(match: re.Match[str] | None) -> dict[str, Any] | None:
    if match is None:
        return None
    inn, last_name, first_name, middle_name = (item.strip() for item in match.groups())
    return {
        "kind": "identity_choice",
        "value": {
            "choice": "CHANGE",
            "identity": {
                "inn": inn,
                "last_name": last_name,
                "first_name": first_name,
                "middle_name": middle_name,
                "source_fact_refs": [],
            },
        },
    }


def _result(status: str, *, reason_code: str | None = None) -> dict[str, Any]:
    result = {
        "schema_version": ORDINARY_TRADE_DECLARATION_CHAT_ACTION_SCHEMA_VERSION,
        "status": status,
    }
    if reason_code is not None:
        result["reason_code"] = reason_code
    return result


def _text(value: Any) -> str:
    return str(value or "").strip()[:2048]


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "ORDINARY_TRADE_DECLARATION_CHAT_ACTION_SCHEMA_VERSION",
    "adapt_current_declaration_request",
    "declaration_change_intent",
    "declaration_request_help",
]
