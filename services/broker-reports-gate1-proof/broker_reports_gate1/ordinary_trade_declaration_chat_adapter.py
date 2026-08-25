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
    "изменить налоговый период": "selected_tax_period",
}
_UNAVAILABLE_REQUEST = "Ответ на этот запрос временно недоступен."

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
    "declaration_request_question",
    "declaration_surrogate_preview",
]
