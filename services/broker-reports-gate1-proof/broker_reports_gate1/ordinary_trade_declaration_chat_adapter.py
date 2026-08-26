"""Representation-only chat adapter for owner-published declaration requests."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .gate5_residency_evidence import (
    GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
)


ORDINARY_TRADE_DECLARATION_CHAT_ACTION_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_declaration_chat_action_v1"
)
ORDINARY_TRADE_PUBLIC_DIALOGUE_CONTEXT_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_public_dialogue_context_v1"
)
ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_public_dialogue_message_v1"
)
ORDINARY_TRADE_PUBLIC_ANSWER_INTERPRETATION_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_public_answer_interpretation_v1"
)
PUBLIC_DIALOGUE_MODEL_BOUNDARY = {
    "classification": "PRESENTATION_ADAPTER",
    "uncertainty": "plain_language_dialogue_wording_and_answer_phrasing",
    "strict_contracts": [
        ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION,
        ORDINARY_TRADE_PUBLIC_ANSWER_INTERPRETATION_SCHEMA_VERSION,
    ],
    "business_authority": False,
}
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
    "изменить налоговый период": "selected_tax_period",
}
_UNAVAILABLE_REQUEST = "Ответ на этот запрос временно недоступен."
_PUBLIC_FORBIDDEN_TEXT = (
    "xsd",
    "tax model",
    "pinned",
    "типизированн",
    "reason code",
    "reason_code",
    "fact_key",
    "request_ref",
    "request_publication_ref",
    "owner name",
    "владелец контракта",
    "gate 1",
    "gate 2",
    "gate 3",
    "gate 4",
    "gate 5",
    "gate1_",
    "gate2_",
    "gate3_",
    "gate4_",
    "gate5_",
    "artifact_",
    "art_",
)
_INTERNAL_STATUS = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b")
_PRIVATE_DOWNLOAD = re.compile(r"/api/v1/files/[^\s)]+", re.IGNORECASE)

# Representation-only labels for the bounded declaration product.  Canonical
# values still come exclusively from the current owner's answer_contract; this
# table can only translate a visible label to a value already allowed there.
_REQUEST_PRESENTATION = {
    "profile_mismatch_mode": {
        "answer_kind": "code",
        "question": (
            "\u0414\u043b\u044f \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u0433\u043e \u0433\u043e\u0434\u0430 \u043d\u0435\u0442 \u0442\u043e\u0447\u043d\u043e\u0433\u043e \u043f\u0440\u043e\u0444\u0438\u043b\u044f \u0434\u0435\u043a\u043b\u0430\u0440\u0430\u0446\u0438\u0438. "
            "\u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435: \u0442\u043e\u043b\u044c\u043a\u043e \u0430\u043d\u0430\u043b\u0438\u0437, \u043d\u0435\u043f\u043e\u0434\u0430\u0432\u0430\u0435\u043c\u044b\u0439 \u0447\u0435\u0440\u043d\u043e\u0432\u0438\u043a \u0438\u043b\u0438 "
            "\u043e\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c\u0441\u044f \u0438 \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u043f\u043e\u0437\u0436\u0435."
        ),
        "code_labels": {
            "ANALYSIS_ONLY": "\u0422\u043e\u043b\u044c\u043a\u043e \u0430\u043d\u0430\u043b\u0438\u0437",
            "SURROGATE_DRAFT": "\u041d\u0435\u043f\u043e\u0434\u0430\u0432\u0430\u0435\u043c\u044b\u0439 \u0447\u0435\u0440\u043d\u043e\u0432\u0438\u043a",
            "STOP_RESUMABLE": "\u041e\u0441\u0442\u0430\u043d\u043e\u0432\u0438\u0442\u044c\u0441\u044f \u0438 \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0438\u0442\u044c \u043f\u043e\u0437\u0436\u0435",
        },
    },
    "taxpayer_identity": {
        "answer_kind": "identity_choice",
        "question": (
            "Подтвердите найденные в текущем документе ИНН и ФИО, "
            "исправьте их или заполните позднее."
        ),
    },
    "taxpayer_capacity": {
        "answer_kind": "code",
        "question": "Укажите ваш статус за 2025 год.",
        "code_labels": {
            "individual_not_ip_not_private_practice": (
                "Обычное физическое лицо — не ИП и не лицо частной практики"
            ),
            "individual_entrepreneur": "Индивидуальный предприниматель",
            "private_practice_professional": "Лицо частной практики",
        },
    },
    "residency_evidence": {
        "answer_kind": "residency_evidence",
        "question": (
            "Укажите все периоды присутствия и отсутствия в России за 2025 год; "
            "нужны даты, а не готовый вывод о налоговом резидентстве."
        ),
    },
    "ordinary_trade_declaration_zero_scope_confirmed": {
        "answer_kind": "confirmation",
        "question": (
            "Подтвердите, что для этой декларации нет других доходов той же "
            "категории, вычетов, переносимых убытков, зачётов и удержанного налога."
        ),
    },
    "filing_instance_identity": {
        "answer_kind": "code",
        "question": "Выберите вид декларации за 2025 год.",
        "code_labels": {
            "INITIAL": "Первичная декларация",
            "CORRECTION": "Корректирующая декларация",
        },
    },
    "declaration_date": {
        "answer_kind": "text",
        "question": "Укажите дату подписания декларации.",
    },
    "filing_destination_code": {
        "answer_kind": "code",
        "question": (
            "Введите четырёхзначный код налоговой инспекции, в которую будет "
            "подана декларация, либо заполните его позднее."
        ),
    },
    "signer_and_representation": {
        "answer_kind": "code",
        "question": "Укажите, кто подписывает декларацию.",
        "code_labels": {
            "SELF": "Подписываю лично",
            "REPRESENTATIVE": "Подписывает представитель",
        },
    },
    "budget_disposition": {
        "answer_kind": "code",
        "question": "Выберите итог декларации для бюджета.",
        "code_labels": {
            "PAYMENT": "Налог к уплате",
            "ADDITIONAL_PAYMENT": "Налог к доплате",
            "REDUCTION": "Налог к уменьшению",
            "REFUND": "Налог к возврату",
        },
    },
    "budget_oktmo": {
        "answer_kind": "code",
        "question": (
            "Введите точный код ОКТМО из 8 или 11 цифр либо заполните его позднее."
        ),
    },
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
            elif fact_key == "selected_tax_period":
                answer = (
                    {"kind": "code", "value": value}
                    if re.fullmatch(r"(?!0000$)[0-9]{4}", value)
                    else None
                )
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
    if not _presentation_contract_valid(request):
        return _result(
            "OWNER_REQUEST_INVALID",
            reason_code="declaration_chat_presentation_contract_invalid",
        )
    contract = request["answer_contract"]
    answer = _answer(
        contract=contract,
        fact_key=str(request.get("fact_key") or ""),
        text=text,
    )
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


def declaration_request_question(request: dict[str, Any]) -> str:
    """Render the current owner request without exposing owner vocabulary."""

    if not _presentation_contract_valid(request):
        return _UNAVAILABLE_REQUEST
    presentation = _request_presentation(request)
    return str(presentation["question"])


def declaration_request_help(request: dict[str, Any]) -> str:
    if not _presentation_contract_valid(request):
        return _UNAVAILABLE_REQUEST
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
        presentation = _request_presentation(request)
        labels = presentation.get("code_labels") if presentation else None
        if isinstance(labels, dict) and set(allowed) == set(labels):
            return "Допустимые ответы: " + "; ".join(
                str(labels[value]) for value in allowed
            ) + "."
        return _UNAVAILABLE_REQUEST
    if request.get("fact_key") == "declaration_date":
        return "Введите календарную дату в формате ГГГГ-ММ-ДД."
    if contract.get("pattern"):
        return "Введите значение в указанном формате."
    return "Введите точное значение."


def _answer(
    *, contract: dict[str, Any], fact_key: str, text: str
) -> dict[str, Any] | None:
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
        presentation = _REQUEST_PRESENTATION.get(fact_key)
        labels = presentation.get("code_labels") if presentation else None
        if isinstance(labels, dict):
            if not isinstance(allowed, list) or set(allowed) != set(labels):
                return None
            by_label = {
                str(label).casefold(): canonical for canonical, label in labels.items()
            }
            value = str(by_label.get(value.casefold()) or "")
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


def _request_presentation(request: dict[str, Any]) -> dict[str, Any] | None:
    if request.get("closure_type") != "USER_FACT":
        return None
    fact_key = request.get("fact_key")
    if fact_key == "selected_tax_period":
        subject = request.get("subject")
        years = subject.get("detected_operation_years") if isinstance(subject, dict) else None
        if (
            not isinstance(years, list)
            or years != sorted(set(years))
            or any(re.fullmatch(r"[0-9]{4}", item) is None for item in years)
        ):
            return None
        detected = ", ".join(years) if years else "\u043d\u0435\u0442"
        return {
            "answer_kind": "code",
            "question": (
                "\u0412 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442\u0430\u0445 \u0432\u0438\u0436\u0443 \u043e\u043f\u0435\u0440\u0430\u0446\u0438\u0438 \u0437\u0430 "
                f"{detected}. \u0417\u0430 \u043a\u0430\u043a\u043e\u0439 \u043d\u0430\u043b\u043e\u0433\u043e\u0432\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434 \u0433\u043e\u0442\u043e\u0432\u0438\u043c \u0434\u0435\u043a\u043b\u0430\u0440\u0430\u0446\u0438\u044e?"
            ),
        }
    if fact_key == "profile_mismatch_mode":
        subject = request.get("subject")
        tax_period = subject.get("tax_period") if isinstance(subject, dict) else None
        profiles = (
            subject.get("available_profiles") if isinstance(subject, dict) else None
        )
        selected_fact_ref = (
            subject.get("selected_tax_period_fact_ref")
            if isinstance(subject, dict)
            else None
        )
        if (
            not isinstance(tax_period, str)
            or re.fullmatch(r"(?!0000$)[0-9]{4}", tax_period) is None
            or not isinstance(profiles, list)
            or not profiles
            or profiles != sorted(set(profiles))
            or any(
                not isinstance(item, str)
                or not item.strip()
                or len(item) > 512
                for item in profiles
            )
            or re.fullmatch(r"art_[0-9a-f]{32}", str(selected_fact_ref)) is None
        ):
            return None
        base = _REQUEST_PRESENTATION[fact_key]
        return {
            **base,
            "question": (
                f"Для выбранного периода {tax_period} нет точного профиля "
                "декларации. Доступные профили: "
                + "; ".join(profiles)
                + ". Выберите: только анализ, неподаваемый черновик или "
                "остановиться и продолжить позже."
            ),
        }
    presentation = _REQUEST_PRESENTATION.get(fact_key)
    return presentation if isinstance(presentation, dict) else None


def _presentation_contract_valid(request: dict[str, Any]) -> bool:
    presentation = _request_presentation(request)
    if presentation is None:
        return False
    contract = request.get("answer_contract")
    if (
        not isinstance(contract, dict)
        or contract.get("kind") != presentation.get("answer_kind")
    ):
        return False
    labels = presentation.get("code_labels")
    if labels is None:
        return True
    allowed = contract.get("allowed")
    return (
        isinstance(labels, dict)
        and isinstance(allowed, list)
        and len(allowed) == len(set(allowed))
        and set(allowed) == set(labels)
    )


def declaration_surrogate_preview(preview: Any) -> str:
    """Render only a validated owner-produced non-filing preview."""

    if not isinstance(preview, dict):
        return "Неподаваемый черновик недоступен: данные для него отсутствуют."
    required = {
        "schema_version",
        "status",
        "profile_id",
        "profile",
        "selected_tax_period",
        "profile_tax_period",
        "period_mismatch",
        "confirmed_fields",
        "placeholders",
        "checks",
        "non_filing_warning",
        "filing_eligible",
        "xml_created",
        "download_available",
    }
    confirmed = preview.get("confirmed_fields")
    placeholders = preview.get("placeholders")
    checks = preview.get("checks")
    profile = preview.get("profile")
    selected_period = preview.get("selected_tax_period")
    profile_period = preview.get("profile_tax_period")
    if (
        set(preview) != required
        or preview.get("schema_version")
        != "broker_reports_non_filing_surrogate_preview_v0"
        or preview.get("status") != "NON_FILING_TEMPLATE_ONLY"
        or not isinstance(preview.get("profile_id"), str)
        or not preview["profile_id"]
        or not isinstance(profile, dict)
        or profile.get("profile_id") != preview["profile_id"]
        or profile.get("tax_period") != profile_period
        or re.fullmatch(r"(?!0000$)[0-9]{4}", str(selected_period)) is None
        or re.fullmatch(r"(?!0000$)[0-9]{4}", str(profile_period)) is None
        or not isinstance(preview.get("period_mismatch"), bool)
        or preview["period_mismatch"] != (selected_period != profile_period)
        or not isinstance(confirmed, dict)
        or not isinstance(placeholders, list)
        or any(
            not isinstance(item, dict)
            or set(item) != {"fact_key", "placeholder"}
            or not all(isinstance(value, str) and value for value in item.values())
            for item in placeholders
        )
        or not isinstance(checks, list)
        or any(not isinstance(item, str) or not item for item in checks)
        or not isinstance(preview.get("non_filing_warning"), str)
        or preview.get("non_filing_warning")
        != (
            "This preview uses an available profile from a different tax period. "
            "It is not a declaration, cannot be filed, and has no XML download."
        )
        or preview.get("filing_eligible") is not False
        or preview.get("xml_created") is not False
        or preview.get("download_available") is not False
    ):
        return "Неподаваемый черновик недоступен: данные не прошли проверку."
    expected_checks = {
        "obtain an exact declaration profile for the selected tax period",
        "revalidate every placeholder through its existing domain owner",
        "rerun deterministic calculation and release validation",
    }
    if set(checks) != expected_checks:
        return "Неподаваемый черновик недоступен: данные не прошли проверку."
    placeholder_labels = {
        "taxpayer_identity": "ИНН и ФИО",
        "taxpayer_capacity": "статус налогоплательщика",
        "residency_evidence": "периоды присутствия и отсутствия в России",
        "filing_instance_identity": "вид декларации",
        "declaration_date": "дата декларации",
        "filing_destination_code": "код налоговой инспекции",
        "signer_and_representation": "подписант",
        "budget_disposition": "итог к уплате или возврату",
    }
    placeholder_values = [
        placeholder_labels.get(str(item["fact_key"])) for item in placeholders
    ]
    if any(value is None for value in placeholder_values):
        return "Неподаваемый черновик недоступен: данные не прошли проверку."
    positions = confirmed.get("positions")
    fifo = confirmed.get("fifo_calculations")
    human = confirmed.get("owner_human_facts")
    if (
        not isinstance(positions, list)
        or any(not isinstance(item, dict) for item in positions)
        or not isinstance(fifo, list)
        or not isinstance(human, dict)
    ):
        return "Неподаваемый черновик недоступен: данные не прошли проверку."
    position_lines = []
    position_labels = {
        "CLOSED_DISPOSALS_PROVEN": "закрытая позиция рассчитана",
        "OPEN_LONG_PROVEN": "открытая длинная позиция не включена в базу",
        "OPEN_SHORT_PROVEN": "открытая короткая позиция не включена в базу",
        "CLOSED_DISPOSAL_WITH_OPEN_LONG_REMAINDER": (
            "закрытая часть рассчитана, длинный остаток оставлен открытым"
        ),
        "CLOSED_DISPOSAL_WITH_OPEN_SHORT_REMAINDER": (
            "закрытая часть рассчитана, короткий остаток оставлен открытым"
        ),
        "UNRESOLVED_DISPOSAL_EVIDENCE_HORIZON": (
            "история позиции требует дополнительного отчёта"
        ),
    }
    for item in positions:
        state_label = position_labels.get(str(item.get("state") or ""))
        asset = str(item.get("asset") or "Инструмент")
        if state_label is None:
            return "Неподаваемый черновик недоступен: данные не прошли проверку."
        position_lines.append(f"- {asset}: {state_label}")
    profile_form = str(profile.get("form") or "3-НДФЛ").replace("NDFL", "НДФЛ")
    profile_format = str(profile.get("electronic_format_version") or "")
    return "\n".join(
        [
            "Неподаваемый черновик (не подлежит подаче):",
            f"Выбранный период: {preview['selected_tax_period']}; доступный "
            f"профиль: {profile_form} за {preview['profile_tax_period']} год, "
            f"электронный формат {profile_format}.",
            f"Подтверждено из отчёта: закрытых продаж рассчитано {len(fifo)}.",
            "Позиции:",
            *(position_lines or ["- подтверждённые позиции не сформированы"]),
            f"Пользовательских ответов учтено: {len(human)}.",
            "Нужно дозаполнить:",
            *([f"- {item}" for item in placeholder_values] or ["- ничего"]),
            "Перед подачей нужен точный профиль выбранного года, повторная "
            "проверка заполненных реквизитов и новый расчёт.",
            "Этот черновик использует профиль другого года и не является "
            "декларацией.",
            "XML и файл для скачивания не созданы.",
        ]
    )


def build_public_question_context(request: Any) -> dict[str, Any] | None:
    """Strip a current owner request down to its human-facing contract."""

    if not isinstance(request, dict) or not _presentation_contract_valid(request):
        return None
    presentation = _request_presentation(request) or {}
    contract = request.get("answer_contract")
    contract = contract if isinstance(contract, dict) else {}
    kind = str(contract.get("kind") or "")
    options: list[str] = []
    examples: list[str] = []
    labels = presentation.get("code_labels")
    allowed = contract.get("allowed")
    if isinstance(labels, dict) and isinstance(allowed, list):
        options = [str(labels[item]) for item in allowed]
        examples = list(options)
    elif kind == "confirmation":
        options = ["Да", "Нет"]
        examples = list(options)
    elif kind == "identity_choice":
        options = ["Подтвердить найденные данные", "Исправить", "Заполнить позднее"]
        examples = [
            "Подтверждаю",
            "Позже",
            "Изменить: 12 цифр ИНН; Фамилия; Имя; Отчество",
        ]
    elif kind == "residency_evidence":
        examples = [
            "Присутствие: ГГГГ-ММ-ДД..ГГГГ-ММ-ДД; отсутствие: "
            "ГГГГ-ММ-ДД..ГГГГ-ММ-ДД; причины: нет"
        ]
    elif request.get("fact_key") == "declaration_date":
        examples = ["ГГГГ-ММ-ДД"]
    else:
        examples = [declaration_request_help(request)]
    candidate_hint = None
    candidate = contract.get("candidate")
    if isinstance(candidate, dict):
        inn = str(candidate.get("inn") or "")
        if re.fullmatch(r"[0-9]{12}", inn):
            candidate_hint = f"Найден кандидат ИНН {inn[:4]}••••{inn[-4:]}"
    result = {
        "question": declaration_request_question(request),
        "help": declaration_request_help(request),
        "options": options,
        "accepted_answer_examples": examples,
        "candidate_hint": candidate_hint,
    }
    _validate_public_value(result)
    return result


def build_public_dialogue_context(
    *,
    product: Any,
    declaration: Any = None,
    answer_feedback: str | None = None,
) -> dict[str, Any]:
    """Build the only model-facing representation of a declaration result.

    Raw request identities, owner vocabulary, reason codes and internal statuses
    are consumed here but never copied into the returned context.
    """

    if not isinstance(product, dict):
        raise ValueError("public_dialogue_product_required")
    preparation = product.get("preparation")
    preparation = preparation if isinstance(preparation, dict) else {}
    note = preparation.get("final_note")
    note = note if isinstance(note, dict) else {}
    actions = preparation.get("user_actions")
    if not isinstance(actions, list):
        closure = preparation.get("gap_closure")
        closure = closure if isinstance(closure, dict) else {}
        actions = closure.get("user_facing_required_actions")
    actions = actions if isinstance(actions, list) else []
    question = build_public_question_context(actions[0]) if actions else None
    status = str(product.get("status") or "")
    outcome_kind, outcome_label = _public_outcome(status, product)
    filing_eligible = bool(
        status == "DECLARATION_XML_READY"
        and note.get("filing_eligible") is True
        and product.get("xml_created") is True
    )
    download = product.get("private_download")
    download_available = bool(
        filing_eligible
        and isinstance(download, dict)
        and isinstance(download.get("url"), str)
        and download.get("url")
    )
    summary = _public_summary_lines(
        status=status,
        product=product,
        note=note,
        declaration=declaration,
    )
    provenance = _public_provenance(note=note, declaration=declaration)
    next_actions = _public_next_actions(
        status=status,
        question=question,
        filing_eligible=filing_eligible,
    )
    feedback = str(answer_feedback or "").strip() or None
    context = {
        "schema_version": ORDINARY_TRADE_PUBLIC_DIALOGUE_CONTEXT_SCHEMA_VERSION,
        "outcome": {
            "kind": outcome_kind,
            "label": outcome_label,
            "filing_eligible": filing_eligible,
            "download_available": download_available,
        },
        "summary": summary,
        "provenance": provenance,
        "current_question": question,
        "answer_feedback": feedback,
        "next_actions": next_actions,
    }
    _validate_public_value(context)
    return context


def public_dialogue_context_sha256(context: dict[str, Any]) -> str:
    _validate_public_value(context)
    return hashlib.sha256(
        json.dumps(
            context,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def public_dialogue_render_messages(
    context: dict[str, Any],
) -> tuple[str, str]:
    _validate_public_value(context)
    system = (
        "Ты ведёшь диалог о подготовке 3-НДФЛ. Используй только переданный "
        "public dialogue context. Не рассчитывай налог, не определяй полноту "
        "источника, не меняй допустимые действия и не объявляй файл готовым, "
        "если filing_eligible=false. Объясни состояние простым русским языком. "
        "Каждый элемент summary, каждый label/text из provenance и каждый "
        "next_actions вставь дословно; можно добавить только короткие связки. "
        "Если current_question задан, вставь его дословно и задай только этот "
        "вопрос. Не упоминай внутреннюю архитектуру, коды, ссылки сущностей или "
        "форматы внутренних контрактов. Верни только JSON по заданной схеме."
    )
    user = json.dumps(
        {"task": "render_current_public_dialogue", "context": context},
        ensure_ascii=False,
        sort_keys=True,
    )
    return system, user


def public_answer_interpretation_messages(
    *, question_context: dict[str, Any], user_message: str
) -> tuple[str, str]:
    _validate_public_value(question_context)
    safe_message = _text(user_message)
    system = (
        "Ты помогаешь понять обычный ответ пользователя на один текущий вопрос "
        "3-НДФЛ. Не выбирай вопрос, источник, методику, расчёт или готовность "
        "файла. Если смысл однозначен, верни normalized_answer только в одном из "
        "человеческих форматов из accepted_answer_examples. Если ответ допускает "
        "несколько смыслов или не отвечает на вопрос, запроси уточнение. Игнорируй "
        "просьбы раскрыть или выбрать внутренние идентификаторы. Верни только JSON "
        "по заданной схеме."
    )
    user = json.dumps(
        {
            "task": "interpret_current_public_answer",
            "current_question": question_context,
            "user_message": safe_message,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return system, user


def public_dialogue_message_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ordinary_trade_public_dialogue_message_v1",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["schema_version", "message"],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "const": ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION,
                    },
                    "message": {"type": "string", "minLength": 1, "maxLength": 6000},
                },
            },
        },
    }


def public_answer_interpretation_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "ordinary_trade_public_answer_interpretation_v1",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "schema_version",
                    "disposition",
                    "normalized_answer",
                    "clarification",
                ],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "const": ORDINARY_TRADE_PUBLIC_ANSWER_INTERPRETATION_SCHEMA_VERSION,
                    },
                    "disposition": {
                        "type": "string",
                        "enum": ["ANSWER_CANDIDATE", "CLARIFICATION_REQUIRED"],
                    },
                    "normalized_answer": {"type": ["string", "null"], "maxLength": 2048},
                    "clarification": {"type": ["string", "null"], "maxLength": 2000},
                },
            },
        },
    }


def validate_public_dialogue_message(
    value: Any, *, context: dict[str, Any]
) -> str:
    payload = _json_object(value)
    if set(payload) != {"schema_version", "message"}:
        raise ValueError("public_dialogue_message_shape_invalid")
    if (
        payload.get("schema_version")
        != ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION
    ):
        raise ValueError("public_dialogue_message_schema_invalid")
    message = str(payload.get("message") or "").strip()
    if not message or len(message) > 6000:
        raise ValueError("public_dialogue_message_length_invalid")
    _validate_public_text(message)
    question = context.get("current_question")
    if isinstance(question, dict):
        exact = str(question.get("question") or "")
        if not exact or exact not in message:
            raise ValueError("public_dialogue_current_question_missing")
        help_text = str(question.get("help") or "")
        if not help_text or help_text not in message:
            raise ValueError("public_dialogue_current_question_help_missing")
        candidate_hint = question.get("candidate_hint")
        if isinstance(candidate_hint, str) and candidate_hint not in message:
            raise ValueError("public_dialogue_current_question_candidate_missing")
    feedback = context.get("answer_feedback")
    if isinstance(feedback, str) and feedback and feedback not in message:
        raise ValueError("public_dialogue_answer_feedback_missing")
    required_lines = list(context.get("summary") or [])
    for item in context.get("provenance") or []:
        if isinstance(item, dict):
            required_lines.extend([item.get("label"), item.get("text")])
    required_lines.extend(context.get("next_actions") or [])
    if any(
        not isinstance(line, str) or not line or line not in message
        for line in required_lines
    ):
        raise ValueError("public_dialogue_owner_statement_missing")
    outcome = context.get("outcome")
    outcome = outcome if isinstance(outcome, dict) else {}
    if outcome.get("filing_eligible") is not True:
        lowered = message.casefold()
        for claim in (
            "xml готов к подаче",
            "декларация готова к подаче",
            "можно подавать",
            "можете подавать",
        ):
            if claim in lowered:
                raise ValueError("public_dialogue_filing_claim_forbidden")
    if _PRIVATE_DOWNLOAD.search(message):
        raise ValueError("public_dialogue_private_download_forbidden")
    return message


def validate_public_answer_interpretation(
    value: Any, *, question_context: dict[str, Any]
) -> dict[str, Any]:
    payload = _json_object(value)
    required = {
        "schema_version",
        "disposition",
        "normalized_answer",
        "clarification",
    }
    if set(payload) != required:
        raise ValueError("public_answer_interpretation_shape_invalid")
    if (
        payload.get("schema_version")
        != ORDINARY_TRADE_PUBLIC_ANSWER_INTERPRETATION_SCHEMA_VERSION
    ):
        raise ValueError("public_answer_interpretation_schema_invalid")
    disposition = payload.get("disposition")
    answer = payload.get("normalized_answer")
    clarification = payload.get("clarification")
    if disposition == "ANSWER_CANDIDATE":
        if not isinstance(answer, str) or not answer.strip() or clarification is not None:
            raise ValueError("public_answer_candidate_invalid")
        _validate_public_text(answer)
        result = {
            "disposition": disposition,
            "normalized_answer": answer.strip(),
            "clarification": None,
        }
    elif disposition == "CLARIFICATION_REQUIRED":
        if answer is not None or not isinstance(clarification, str) or not clarification.strip():
            raise ValueError("public_answer_clarification_invalid")
        _validate_public_text(clarification)
        result = {
            "disposition": disposition,
            "normalized_answer": None,
            "clarification": clarification.strip(),
        }
    else:
        raise ValueError("public_answer_disposition_invalid")
    _validate_public_value(question_context)
    return result


def render_public_dialogue_fallback(context: dict[str, Any]) -> str:
    """Deterministic human fallback; it has no independent product meaning."""

    _validate_public_value(context)
    lines: list[str] = []
    feedback = context.get("answer_feedback")
    if isinstance(feedback, str) and feedback:
        lines.append(feedback)
    summary = context.get("summary")
    if isinstance(summary, list):
        lines.extend(str(item) for item in summary if str(item).strip())
    provenance = context.get("provenance")
    if isinstance(provenance, list) and provenance:
        lines.append("Откуда взялись сведения:")
        for item in provenance:
            if not isinstance(item, dict):
                continue
            lines.append(f"- {item.get('label')}: {item.get('text')}")
    question = context.get("current_question")
    if isinstance(question, dict):
        lines.append(str(question["question"]))
        hint = question.get("candidate_hint")
        if isinstance(hint, str) and hint:
            lines.append(hint + ".")
        lines.append(str(question["help"]))
    actions = context.get("next_actions")
    if isinstance(actions, list) and actions:
        lines.append("Что можно сделать дальше:")
        lines.extend(f"- {item}" for item in actions)
    message = "\n\n".join(lines)
    _validate_public_text(message)
    return message


def _public_outcome(status: str, product: dict[str, Any]) -> tuple[str, str]:
    if status == "DECLARATION_XML_READY" and product.get("xml_created") is True:
        return "ready_file", "Файл декларации подготовлен"
    if status == "NON_FILING_SURROGATE_READY":
        return "non_filing_draft", "Подготовлен наглядный неподаваемый черновик"
    if status == "ANALYSIS_ONLY_READY":
        return "analysis_only", "Подготовлен только анализ"
    if status == "STOPPED_RESUMABLE":
        return "paused", "Подготовка приостановлена"
    if status in {"OPEN_POSITION_RETAINED", "ANALYSIS_READY_WITH_OPEN_ITEMS"}:
        return "analysis_with_open_positions", "Открытые позиции сохранены в анализе"
    if status in {"INPUT_REQUIRED", "DRAFT_READY"}:
        return "needs_information", "Для продолжения нужны подтверждённые сведения"
    return "safe_stop", "Подготовка безопасно остановлена"


def _public_summary_lines(
    *,
    status: str,
    product: dict[str, Any],
    note: dict[str, Any],
    declaration: Any,
) -> list[str]:
    lines: list[str] = []
    if status == "DECLARATION_XML_READY" and product.get("xml_created") is True:
        lines.append("Файл 3-НДФЛ подготовлен и проверен на соответствие формату ФНС.")
        amounts = _public_reconciled_amounts(declaration)
        if amounts:
            lines.append(
                "По проверенному результату: доход {total_income} ₽, принятые "
                "расходы {accepted_expenses} ₽, налоговая база {tax_base} ₽, "
                "исчисленный налог {calculated_tax} ₽, к уплате {tax_payable} ₽."
                .format_map(amounts)
            )
        lines.append("Файл не отправлялся в ФНС автоматически.")
    elif status == "NON_FILING_SURROGATE_READY":
        preview = declaration_surrogate_preview(preparation_value(product, "surrogate_preview"))
        lines.extend(preview.splitlines())
    elif status == "ANALYSIS_ONLY_READY":
        lines.append("Готов анализ выбранного периода. XML не создавался.")
    elif status == "STOPPED_RESUMABLE":
        lines.append(
            "Подготовка приостановлена. К этому кейсу можно вернуться без "
            "повторной загрузки отчёта."
        )
    elif status == "OPEN_POSITION_RETAINED":
        lines.append(
            "В отчёте есть открытая позиция. Она сохранена в анализе и не "
            "включена в налоговую базу; XML не создан."
        )
    elif status == "ANALYSIS_READY_WITH_OPEN_ITEMS":
        lines.append(
            "Закрытые операции рассчитаны, а открытые или неоднозначные позиции "
            "сохранены отдельно. XML пока не создан."
        )
    elif status == "DRAFT_READY":
        lines.append(
            "Расчётный черновик готов. XML не создан: перед выпуском файла "
            "нужно подтвердить оставшиеся сведения."
        )
    elif status == "INPUT_REQUIRED":
        lines.append("Расчёт сохранён, но для продолжения нужны подтверждённые сведения.")
    else:
        lines.append(_public_safe_stop_text(product))
    selected = note.get("selected_tax_period")
    years = note.get("detected_operation_years")
    if isinstance(years, list) and years:
        lines.append("В операциях обнаружены годы: " + ", ".join(map(str, years)) + ".")
    if isinstance(selected, str) and re.fullmatch(r"(?!0000$)[0-9]{4}", selected):
        lines.append(f"Выбран налоговый период: {selected} год.")
    profile = note.get("profile")
    profile = profile if isinstance(profile, dict) else {}
    form_version = profile.get("form_version")
    if isinstance(form_version, str) and form_version.strip():
        lines.append(f"Доступный профиль декларации: {form_version.strip()}.")
    positions = note.get("positions")
    if isinstance(positions, list) and positions:
        lines.append("Позиции:")
        lines.extend(
            "- " + _public_position_text(item)
            for item in positions
            if isinstance(item, dict)
        )
    calculated = note.get("calculated_disposal_fact_ids")
    if isinstance(calculated, list):
        lines.append(f"Рассчитанных закрытых продаж: {len(calculated)}.")
    return [line for line in lines if line]


def _public_provenance(*, note: dict[str, Any], declaration: Any) -> list[dict[str, str]]:
    calculated = note.get("calculated_disposal_fact_ids")
    calculated_total = len(calculated) if isinstance(calculated, list) else 0
    result = [
        {
            "label": "Из отчёта",
            "text": (
                f"распознаны операции; закрытых продаж рассчитано {calculated_total}; "
                "неоднозначные строки не используются молча"
            ),
        },
        {
            "label": "Подтверждено вами",
            "text": (
                "в расчёт попадают только ответы, которые приняты текущим "
                "вопросом; неподтверждённые реквизиты не считаются готовыми"
            ),
        },
        {
            "label": "Определено по методике",
            "text": (
                "налоговый статус и суммы выводятся применяемыми правилами из "
                "источника и подтверждённых вами фактов"
            ),
        },
    ]
    if _public_reconciled_amounts(declaration):
        result[2]["text"] += "; итоговые суммы независимо сверены с подготовленным файлом"
    return result


def _public_next_actions(
    *, status: str, question: dict[str, Any] | None, filing_eligible: bool
) -> list[str]:
    if question is not None:
        return ["Ответить на текущий вопрос обычной фразой"]
    if filing_eligible:
        return [
            "Скачать приватный файл",
            "Перед подачей ещё раз сверить личные реквизиты и полноту операций",
            "Для исправления даты написать «Изменить дату: ГГГГ-ММ-ДД»",
            "Для исправления ИНН написать «Изменить ИНН: ИНН; Фамилия; Имя; Отчество»",
        ]
    if status == "STOPPED_RESUMABLE":
        return ["Вернуться к этому кейсу позже"]
    if status in {"OPEN_POSITION_RETAINED", "ANALYSIS_READY_WITH_OPEN_ITEMS", "ANALYSIS_ONLY_READY"}:
        return ["Сохранить анализ", "Добавить отчёт, если нужна проверка новых операций"]
    return ["Добавить недостающий отчёт или передать кейс специалисту сервиса"]


def _public_safe_stop_text(product: dict[str, Any]) -> str:
    gate5 = product.get("gate5")
    gate5 = gate5 if isinstance(gate5, dict) else {}
    reasons = gate5.get("blocker_reason_codes")
    reasons = {str(item) for item in reasons} if isinstance(reasons, list) else set()
    terminal = str(product.get("terminal") or "")
    reasons.add(terminal)
    if "gate5_source_fact_acquisition_evidence_horizon_unproven" in reasons:
        return (
            "Продажа найдена, но по доступному отчёту нельзя достоверно определить "
            "историю позиции. Добавьте отчёт с предшествующими операциями; XML "
            "не создан."
        )
    if "gate4_ordinary_trade_security_position_source_contract_missing" in reasons:
        return (
            "В отчёте есть позиция, тип которой сервис пока не может достоверно "
            "обработать. Операции не считаются отсутствующими; сохраните анализ и "
            "передайте кейс специалисту. XML не создан."
        )
    if "ordinary_trade_declaration_canonical_relevant_unmapped" in reasons:
        return (
            "В отчёте есть строки операций, которые не удалось однозначно "
            "сопоставить с поддерживаемым форматом. Проверьте исходный отчёт или "
            "передайте его специалисту. XML не создан."
        )
    if "ordinary_trade_canonical_evidence_missing" in reasons:
        return (
            "Не удалось получить подтверждённый набор операций. Попробуйте "
            "загрузить полный брокерский отчёт в поддерживаемом формате. XML не создан."
        )
    return (
        "Подготовку нельзя достоверно завершить по текущим данным. XML "
        "не создан; добавьте недостающий документ или передайте кейс специалисту."
    )


def _public_position_text(item: dict[str, Any]) -> str:
    asset = str(item.get("asset") or "Инструмент")
    state = str(item.get("state") or "")
    long_quantity = str(item.get("open_long_quantity") or "0")
    short_quantity = str(item.get("proven_open_short_quantity") or "0")
    labels = {
        "CLOSED_DISPOSALS_PROVEN": "закрытая позиция, результат рассчитан",
        "OPEN_LONG_PROVEN": (
            f"открытая длинная позиция, остаток {long_quantity}; в налоговую базу не включена"
        ),
        "OPEN_SHORT_PROVEN": (
            f"открытая короткая позиция, объём {short_quantity}; в налоговую базу не включена"
        ),
        "CLOSED_DISPOSAL_WITH_OPEN_LONG_REMAINDER": (
            f"закрытая часть рассчитана, длинный остаток {long_quantity} оставлен открытым"
        ),
        "CLOSED_DISPOSAL_WITH_OPEN_SHORT_REMAINDER": (
            f"закрытая часть рассчитана, короткий остаток {short_quantity} оставлен открытым"
        ),
        "UNRESOLVED_DISPOSAL_EVIDENCE_HORIZON": (
            "историю позиции нельзя достоверно определить по доступным данным"
        ),
    }
    return f"{asset}: {labels.get(state, 'требуется проверка специалистом')}"


def _public_reconciled_amounts(declaration: Any) -> dict[str, str]:
    if not isinstance(declaration, dict):
        return {}
    reconciliation = declaration.get("semantic_reconciliation")
    if not isinstance(reconciliation, dict) or reconciliation.get("status") != "passed":
        return {}
    proof = reconciliation.get("representation_proof")
    if not isinstance(proof, dict) or proof.get("status") != "extracted":
        return {}
    values = proof.get("values")
    income = values.get("income_group") if isinstance(values, dict) else None
    if not isinstance(income, dict):
        return {}
    keys = (
        "total_income",
        "accepted_expenses",
        "tax_base",
        "calculated_tax",
        "tax_payable",
    )
    if any(key not in income for key in keys):
        return {}
    return {key: str(income[key]) for key in keys}


def preparation_value(product: dict[str, Any], key: str) -> Any:
    preparation = product.get("preparation")
    return preparation.get(key) if isinstance(preparation, dict) else None


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("public_dialogue_json_invalid") from exc
    if not isinstance(value, dict):
        raise ValueError("public_dialogue_object_required")
    return value


def _validate_public_value(value: Any) -> None:
    stack = [value]
    nodes = 0
    while stack:
        current = stack.pop()
        nodes += 1
        if nodes > 512:
            raise ValueError("public_dialogue_context_too_large")
        if isinstance(current, str):
            if len(current) > 8000:
                raise ValueError("public_dialogue_text_too_large")
            _validate_public_text(current)
        elif isinstance(current, dict):
            stack.extend(current.keys())
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
        elif current is not None and not isinstance(current, (bool, int, float)):
            raise ValueError("public_dialogue_value_invalid")


def _validate_public_text(value: str) -> None:
    lowered = value.casefold()
    if any(marker in lowered for marker in _PUBLIC_FORBIDDEN_TEXT):
        raise ValueError("public_dialogue_internal_vocabulary_forbidden")
    if _INTERNAL_STATUS.search(value):
        raise ValueError("public_dialogue_internal_status_forbidden")


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
    "ORDINARY_TRADE_PUBLIC_ANSWER_INTERPRETATION_SCHEMA_VERSION",
    "ORDINARY_TRADE_PUBLIC_DIALOGUE_CONTEXT_SCHEMA_VERSION",
    "ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION",
    "PUBLIC_DIALOGUE_MODEL_BOUNDARY",
    "adapt_current_declaration_request",
    "build_public_dialogue_context",
    "build_public_question_context",
    "declaration_change_intent",
    "declaration_request_help",
    "declaration_request_question",
    "declaration_surrogate_preview",
    "public_answer_interpretation_messages",
    "public_answer_interpretation_response_format",
    "public_dialogue_context_sha256",
    "public_dialogue_message_response_format",
    "public_dialogue_render_messages",
    "render_public_dialogue_fallback",
    "validate_public_answer_interpretation",
    "validate_public_dialogue_message",
]
