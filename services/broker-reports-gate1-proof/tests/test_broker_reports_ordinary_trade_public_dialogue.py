from __future__ import annotations

import asyncio
import json

import pytest
import openwebui_actions.broker_reports_gate1_pipe as pipe_module

from broker_reports_gate1.ordinary_trade_declaration_chat_adapter import (
    ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION,
    PUBLIC_DIALOGUE_MODEL_BOUNDARY,
    adapt_current_declaration_request,
    build_public_dialogue_context,
    build_public_question_context,
    public_answer_requires_clarification,
    public_dialogue_context_sha256,
    public_dialogue_interpretation_response_format,
    public_dialogue_message_response_format,
    render_public_dialogue_fallback,
    validate_public_dialogue_interpretation,
    validate_public_dialogue_message,
)
from openwebui_actions.broker_reports_gate1_pipe import Pipe
from broker_reports_gate1.gate3_ndfl_workflow import NdflWorkflowError


def _request() -> dict:
    return {
        "request_publication_ref": "art_" + "a" * 32,
        "closure_type": "USER_FACT",
        "fact_key": "filing_instance_identity",
        "reason": "owner_reason_must_not_leak",
        "answer_contract": {
            "kind": "code",
            "allowed": ["INITIAL", "CORRECTION"],
        },
    }


def _product(*, status: str = "INPUT_REQUIRED") -> dict:
    return {
        "status": status,
        "terminal": "OWNER_INTERNAL_TERMINAL",
        "xml_created": False,
        "gate5": {"blocker_reason_codes": ["owner_internal_reason"]},
        "preparation": {
            "user_actions": [_request()] if status == "INPUT_REQUIRED" else [],
            "final_note": {
                "selected_tax_period": "2025",
                "detected_operation_years": ["2025"],
                "profile": {
                    "support": "SUPPORTED",
                    "form_version": "3-НДФЛ, электронный формат 5.20",
                    "xsd_name": "must-not-cross",
                    "methodology_version": "must-not-cross",
                },
                "positions": [],
                "calculated_disposal_fact_ids": ["owner-fact-id"],
                "filing_eligible": False,
            },
        },
    }


def _product_with_request(request: dict) -> dict:
    product = _product()
    product["preparation"]["user_actions"] = [request]
    return product


def _interpretation_completion(
    *, context: dict, disposition: str, normalized_answer: str = "", evidence: str = ""
):
    if disposition == "CANDIDATE":
        visible = (
            f"Я понял ваш ответ как «{normalized_answer}». "
            "Подтверждаете эту интерпретацию?"
        )
    else:
        visible = "Уточните, пожалуйста, что именно вы имеете в виду."

    def completion(**_kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "disposition": disposition,
                                "message": visible,
                                "normalized_answer": normalized_answer,
                                "evidence_quote": evidence,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    return completion


def _residency_request() -> dict:
    return {
        "request_publication_ref": "art_" + "b" * 32,
        "closure_type": "USER_FACT",
        "fact_key": "residency_evidence",
        "answer_contract": {"kind": "residency_evidence"},
    }


@pytest.mark.parametrize("separator", ["..", "—", "–"])
def test_residency_owner_accepts_explicit_no_absence_without_model_authority(
    separator: str,
) -> None:
    result = adapt_current_declaration_request(
        message=(
            f"Присутствие: 2025-01-01{separator}2025-12-31; "
            "отсутствие: нет; причины: нет"
        ),
        current_requests=[_residency_request()],
    )

    assert result["status"] == "ANSWER_READY"
    proposal = result["answer"]["value"]["proposal"]
    assert proposal["presence_intervals"] == [
        {"start_date": "2025-01-01", "end_date": "2025-12-31"}
    ]
    assert proposal["absence_intervals"] == []


@pytest.mark.parametrize(
    "message",
    [
        "Присутствие: 2025-01-01-2025-12-31; отсутствие: нет; причины: нет",
        "Присутствие: 2025-01-01..2025-12-31; отсутствие: не знаю; причины: нет",
        "Присутствие: 2025-01-01..2025-12-31; отсутствие: нет; причины: не помню",
    ],
)
def test_residency_owner_rejects_ambiguous_no_absence_phrasing(message: str) -> None:
    assert adapt_current_declaration_request(
        message=message,
        current_requests=[_residency_request()],
    )["status"] == "ANSWER_REJECTED"


def test_presentation_model_boundary_is_local_and_has_no_business_authority() -> None:
    assert PUBLIC_DIALOGUE_MODEL_BOUNDARY == {
        "classification": "PRESENTATION_ADAPTER",
        "uncertainty": "plain_language_dialogue_wording_and_answer_proposal",
        "strict_contracts": [
            "broker_reports_ordinary_trade_public_dialogue_message_v1",
            "broker_reports_ordinary_trade_public_interpretation_v1",
        ],
        "business_authority": False,
    }
    schema = public_dialogue_interpretation_response_format()["json_schema"]["schema"]
    assert schema["properties"]["disposition"]["enum"] == ["CLARIFY", "CANDIDATE"]
    assert set(schema["required"]) == {
        "disposition",
        "message",
        "normalized_answer",
        "evidence_quote",
    }
    assert "schema_version" not in schema["properties"]


def test_short_model_candidate_is_composed_with_exact_owner_context() -> None:
    context = build_public_dialogue_context(product=_product())
    interpreted = validate_public_dialogue_interpretation(
        {
            "disposition": "CANDIDATE",
            "message": (
                "Вы указали первичную декларацию. "
                "Подтверждаете эту интерпретацию?"
            ),
            "normalized_answer": "Первичная декларация",
            "evidence_quote": "первый раз",
        },
        context=context,
        user_message="Подаю декларацию первый раз",
    )

    assert interpreted["schema_version"] == (
        "broker_reports_ordinary_trade_public_interpretation_v1"
    )
    assert interpreted["message"].startswith("Вы указали первичную декларацию.")
    assert render_public_dialogue_fallback(context) in interpreted["message"]
    validate_public_dialogue_message(
        {
            "schema_version": ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION,
            "message": interpreted["message"],
        },
        context=context,
    )


def test_genuine_short_candidate_with_confirm_imperative_is_accepted() -> None:
    context = build_public_dialogue_context(product=_product())
    interpreted = validate_public_dialogue_interpretation(
        {
            "disposition": "CANDIDATE",
            "message": (
                "Вы хотите подать первичную декларацию. "
                "Пожалуйста, подтвердите этот выбор."
            ),
            "normalized_answer": "Первичная декларация",
            "evidence_quote": "первый раз",
        },
        context=context,
        user_message="Подаю декларацию первый раз",
    )

    assert "Предлагаемое значение: Первичная декларация." in interpreted["message"]


def test_runtime_owns_confirmation_wording_for_plain_model_understanding() -> None:
    context = build_public_dialogue_context(product=_product())
    interpreted = validate_public_dialogue_interpretation(
        {
            "disposition": "CANDIDATE",
            "message": "Вы хотите подать первичную декларацию. Это верно?",
            "normalized_answer": "Первичная декларация",
            "evidence_quote": "первый раз",
        },
        context=context,
        user_message="Подаю декларацию первый раз",
    )

    assert "Подтвердите эту интерпретацию." in interpreted["message"]


def test_runtime_owns_clarification_marker_for_plain_model_question() -> None:
    context = build_public_dialogue_context(product=_product())
    interpreted = validate_public_dialogue_interpretation(
        {
            "disposition": "CLARIFY",
            "message": "Вы имеете в виду первичную или корректирующую декларацию?",
            "normalized_answer": "",
            "evidence_quote": "",
        },
        context=context,
        user_message="Кажется, первый, хотя не уверен",
    )

    assert "Уточните ответ на текущий вопрос." in interpreted["message"]


def test_model_cannot_choose_or_echo_interpretation_schema_version() -> None:
    context = build_public_dialogue_context(product=_product())

    with pytest.raises(
        ValueError, match="public_dialogue_interpretation_shape_invalid"
    ):
        validate_public_dialogue_interpretation(
            {
                "schema_version": "broker_reports_ordinary_trade_public_dialogue_context_v1",
                "disposition": "CANDIDATE",
                "message": (
                    "Вы указали первичную декларацию. "
                    "Подтверждаете эту интерпретацию?"
                ),
                "normalized_answer": "Первичная декларация",
                "evidence_quote": "первый раз",
            },
            context=context,
            user_message="Подаю декларацию первый раз",
        )


def test_public_context_strips_owner_identity_and_keeps_one_current_question() -> None:
    context = build_public_dialogue_context(product=_product())
    serialized = json.dumps(context, ensure_ascii=False, sort_keys=True)

    assert context["current_question"] == {
        "question": "Выберите вид декларации за 2025 год.",
        "help": (
            "Допустимые ответы: Первичная декларация; Корректирующая декларация."
        ),
        "options": ["Первичная декларация", "Корректирующая декларация"],
        "accepted_answer_examples": [
            "Первичная декларация",
            "Корректирующая декларация",
        ],
        "candidate_hint": None,
    }
    for hidden in (
        "request_publication_ref",
        "fact_key",
        "owner_reason",
        "OWNER_INTERNAL_TERMINAL",
        "owner_internal_reason",
        "xsd_name",
        "methodology_version",
        "INITIAL",
        "CORRECTION",
        "art_",
    ):
        assert hidden not in serialized
    assert public_dialogue_context_sha256(context) == public_dialogue_context_sha256(
        context
    )


@pytest.mark.parametrize(
    "status",
    [
        "INPUT_REQUIRED",
        "DRAFT_READY",
        "DECLARATION_XML_READY",
        "PREPARATION_INCOMPLETE",
        "OPEN_POSITION_RETAINED",
        "ANALYSIS_READY_WITH_OPEN_ITEMS",
        "ANALYSIS_ONLY_READY",
        "NON_FILING_SURROGATE_READY",
        "STOPPED_RESUMABLE",
    ],
)
def test_every_deterministic_public_branch_forbids_engineering_vocabulary(
    status: str,
) -> None:
    product = _product(status=status)
    if status == "DECLARATION_XML_READY":
        product["xml_created"] = True
        product["private_download"] = {"url": "/private-file"}
        product["preparation"]["final_note"]["filing_eligible"] = True
    context = build_public_dialogue_context(product=product)
    content = render_public_dialogue_fallback(context)

    for hidden in (
        "xsd",
        "tax model",
        "pinned",
        "типизированн",
        "reason_code",
        "fact_key",
        "request_publication_ref",
        "gate5_",
        "owner_internal",
    ):
        assert hidden not in content.casefold()


def test_public_message_rejects_leaks_and_false_filing_claims() -> None:
    context = build_public_dialogue_context(product=_product())
    fallback = render_public_dialogue_fallback(context)

    with pytest.raises(ValueError, match="internal_vocabulary"):
        validate_public_dialogue_message(
            {
                "schema_version": ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION,
                "message": fallback + " Решение подтверждено Tax Model.",
            },
            context=context,
        )
    with pytest.raises(ValueError, match="filing_claim"):
        validate_public_dialogue_message(
            {
                "schema_version": ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION,
                "message": fallback + " Декларация готова к подаче.",
            },
            context=context,
        )
    with pytest.raises(ValueError, match="current_question"):
        validate_public_dialogue_message(
            {
                "schema_version": ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION,
                "message": "Ответьте на другой вопрос.",
            },
            context=context,
        )

    feedback_context = build_public_dialogue_context(
        product=_product(),
        answer_feedback="Нужно уточнить ваш ответ.",
    )
    without_feedback = render_public_dialogue_fallback(context)
    with pytest.raises(ValueError, match="answer_feedback"):
        validate_public_dialogue_message(
            {
                "schema_version": ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION,
                "message": without_feedback,
            },
            context=feedback_context,
        )


@pytest.mark.parametrize(
    ("user_message", "request_action", "candidate", "owner_answer"),
    [
        (
            "подаю первый раз",
            _request(),
            "Первичная декларация",
            {"kind": "code", "value": "INITIAL"},
        ),
        (
            "подписывать буду сам",
            {
                "request_publication_ref": "art_" + "d" * 32,
                "closure_type": "USER_FACT",
                "fact_key": "signer_and_representation",
                "answer_contract": {"kind": "code", "allowed": ["SELF", "REPRESENTATIVE"]},
            },
            "Подписываю лично",
            {"kind": "code", "value": "SELF"},
        ),
        (
            "я обычный человек, не ИП",
            {
                "request_publication_ref": "art_" + "e" * 32,
                "closure_type": "USER_FACT",
                "fact_key": "taxpayer_capacity",
                "answer_contract": {
                    "kind": "code",
                    "allowed": [
                        "individual_not_ip_not_private_practice",
                        "individual_entrepreneur",
                        "private_practice_professional",
                    ],
                },
            },
            "Обычное физическое лицо — не ИП и не лицо частной практики",
            {"kind": "code", "value": "individual_not_ip_not_private_practice"},
        ),
    ],
)
def test_pipe_free_answer_uses_one_llm_candidate_then_native_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    user_message: str,
    request_action: dict,
    candidate: str,
    owner_answer: dict,
) -> None:
    pipe = Pipe()
    product = _product_with_request(request_action)
    context = build_public_dialogue_context(product=product)
    calls: list[dict] = []
    monkeypatch.setattr(
        pipe,
        "_openwebui_completion_dependencies",
        lambda user_id: (
            _interpretation_completion(
                context=context,
                disposition="CANDIDATE",
                normalized_answer=candidate,
                evidence=user_message,
            ),
            type("User", (), {"id": user_id})(),
        ),
    )

    async def confirm(payload):
        calls.append(payload)
        return True

    adapted, dialogue = asyncio.run(
        pipe._adapt_ndfl_public_answer(
            message=user_message,
            current_actions=[request_action],
            product=product,
            declaration=None,
            user={"id": "user-a"},
            request=object(),
            event_call=confirm,
        )
    )

    assert adapted == {
        "schema_version": "broker_reports_ordinary_trade_declaration_chat_action_v1",
        "status": "ANSWER_READY",
        "request_publication_ref": request_action["request_publication_ref"],
        "answer": owner_answer,
    }
    assert len(calls) == 1
    assert calls[0]["type"] == "confirmation"
    assert calls[0]["data"]["title"] == "Подтвердите понимание ответа"
    assert candidate in calls[0]["data"]["message"]
    assert "Подтверждаете эту интерпретацию?" in calls[0]["data"]["message"]
    assert dialogue["candidate_proposed"] is True
    assert dialogue["explicit_confirmation_received"] is True
    assert dialogue["interpretation_model_used"] is True
    assert dialogue["interpretation_disposition"] == "CANDIDATE"
    assert dialogue["presentation_llm_calls_total"] == 1


def test_pipe_rejects_model_choice_not_grounded_in_ambiguous_user_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()
    request = {
        "request_publication_ref": "art_" + "c" * 32,
        "closure_type": "USER_FACT",
        "fact_key": "selected_tax_period",
        "subject": {"detected_operation_years": ["2024", "2025"]},
        "answer_contract": {"kind": "code", "pattern": "(?!0000$)[0-9]{4}"},
    }

    def completion(**_kwargs):
        raise AssertionError("delegated choice must not reach the model")

    monkeypatch.setattr(
        pipe,
        "_openwebui_completion_dependencies",
        lambda user_id: (completion, type("User", (), {"id": user_id})()),
    )
    adapted, dialogue = asyncio.run(
        pipe._adapt_ndfl_public_answer(
            message="Выберите подходящий год за меня.",
            current_actions=[request],
            product=_product_with_request(request),
            declaration=None,
            user={"id": "user-a"},
            request=object(),
            event_call=None,
        )
    )

    assert adapted["status"] == "ANSWER_REJECTED"
    assert adapted["reason_code"] == "declaration_chat_answer_delegates_choice"
    assert dialogue["answer_feedback"] == (
        "Не буду выбирать за вас. Уточните ответ на текущий вопрос своими словами."
    )


@pytest.mark.parametrize(
    ("user_message", "request_action", "candidate"),
    [
        ("не подтверждаю", _request(), "Первичная декларация"),
        (
            "не 2025",
            {
                "request_publication_ref": "art_" + "f" * 32,
                "closure_type": "USER_FACT",
                "fact_key": "selected_tax_period",
                "subject": {"detected_operation_years": ["2025"]},
                "answer_contract": {"kind": "code", "pattern": "(?!0000$)[0-9]{4}"},
            },
            "2025",
        ),
    ],
)
def test_model_cannot_invert_explicit_refusal_or_negated_year(
    monkeypatch: pytest.MonkeyPatch,
    user_message: str,
    request_action: dict,
    candidate: str,
) -> None:
    pipe = Pipe()
    product = _product_with_request(request_action)
    context = build_public_dialogue_context(product=product)
    monkeypatch.setattr(
        pipe,
        "_openwebui_completion_dependencies",
        lambda user_id: (
            _interpretation_completion(
                context=context,
                disposition="CANDIDATE",
                normalized_answer=candidate,
                evidence=user_message,
            ),
            type("User", (), {"id": user_id})(),
        ),
    )

    async def must_not_confirm(_payload):
        raise AssertionError("conflicting candidate must not reach confirmation")

    adapted, dialogue = asyncio.run(
        pipe._adapt_ndfl_public_answer(
            message=user_message,
            current_actions=[request_action],
            product=product,
            declaration=None,
            user={"id": "user-a"},
            request=object(),
            event_call=must_not_confirm,
        )
    )

    assert adapted == {
        "status": "ANSWER_REJECTED",
        "reason_code": "declaration_chat_interpretation_conflicts_with_user",
    }
    assert dialogue["candidate_proposed"] is False
    assert dialogue["explicit_confirmation_received"] is False
    assert dialogue["presentation_llm_calls_total"] == 1


def test_ambiguous_free_answer_is_clarified_by_one_llm_call_and_never_published(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()
    product = _product()
    context = build_public_dialogue_context(product=product)
    calls = 0
    base_completion = _interpretation_completion(
        context=context,
        disposition="CLARIFY",
    )

    def completion(**kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise AssertionError("one conversation turn must use only one LLM call")
        return base_completion(**kwargs)

    monkeypatch.setattr(
        pipe,
        "_openwebui_completion_dependencies",
        lambda user_id: (completion, type("User", (), {"id": user_id})()),
    )
    adapted, dialogue = asyncio.run(
        pipe._adapt_ndfl_public_answer(
            message="кажется, первый, хотя не уверен",
            current_actions=[_request()],
            product=product,
            declaration=None,
            user={"id": "user-a"},
            request=object(),
            event_call=None,
        )
    )
    result = {
        "provider_calls_total": 0,
        "product": product,
        "declaration": None,
        "public_dialogue": dialogue,
    }
    content = asyncio.run(
        pipe._render_ndfl_public_dialogue(
            result=result,
            user={"id": "user-a"},
            request=object(),
        )
    )

    assert adapted == {
        "status": "ANSWER_REJECTED",
        "reason_code": "declaration_chat_answer_requires_clarification",
    }
    assert "Уточните, пожалуйста" in content
    assert calls == 1
    assert result["public_dialogue"]["interpretation_disposition"] == "CLARIFY"
    assert result["public_dialogue"]["candidate_proposed"] is False


def test_model_cannot_return_hidden_owner_code_as_public_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()
    product = _product()
    context = build_public_dialogue_context(product=product)
    monkeypatch.setattr(
        pipe,
        "_openwebui_completion_dependencies",
        lambda user_id: (
            _interpretation_completion(
                context=context,
                disposition="CANDIDATE",
                normalized_answer="INITIAL",
                evidence="подаю первый раз",
            ),
            type("User", (), {"id": user_id})(),
        ),
    )
    adapted, dialogue = asyncio.run(
        pipe._adapt_ndfl_public_answer(
            message="подаю первый раз",
            current_actions=[_request()],
            product=product,
            declaration=None,
            user={"id": "user-a"},
            request=object(),
            event_call=None,
        )
    )

    assert adapted["status"] == "ANSWER_REJECTED"
    assert dialogue["candidate_proposed"] is False
    assert dialogue["presentation_fallback_used"] is True


def test_invalid_model_render_uses_same_context_fallback_without_new_meaning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()

    def completion(**_kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "schema_version": (
                                    ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION
                                ),
                                "message": (
                                    "Выберите вид декларации за 2025 год. "
                                    "Tax Model разрешил подачу."
                                ),
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(
        pipe,
        "_openwebui_completion_dependencies",
        lambda user_id: (completion, type("User", (), {"id": user_id})()),
    )
    result = {"provider_calls_total": 0, "product": _product(), "declaration": None}
    content = asyncio.run(
        pipe._render_ndfl_public_dialogue(
            result=result,
            user={"id": "user-a"},
            request=object(),
        )
    )

    context = result["public_dialogue"]["context"]
    assert content == render_public_dialogue_fallback(context)
    assert "Tax Model" not in content
    assert result["public_dialogue"]["presentation_model_used"] is False
    assert result["public_dialogue"]["presentation_fallback_used"] is True
    assert result["public_dialogue"]["presentation_llm_calls_total"] == 1
    assert result["public_dialogue"]["domain_provider_calls_total"] == 0


def test_stalled_presentation_model_is_bounded_and_uses_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()

    async def completion(**_kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(
        pipe,
        "_openwebui_completion_dependencies",
        lambda user_id: (completion, type("User", (), {"id": user_id})()),
    )
    monkeypatch.setattr(
        pipe_module,
        "NDFL_PRESENTATION_COMPLETION_TIMEOUT_SECONDS",
        0.01,
    )
    result = {"provider_calls_total": 0, "product": _product(), "declaration": None}
    content = asyncio.run(
        pipe._render_ndfl_public_dialogue(
            result=result,
            user={"id": "user-a"},
            request=object(),
        )
    )

    assert content == render_public_dialogue_fallback(
        result["public_dialogue"]["context"]
    )
    assert result["public_dialogue"]["presentation_fallback_used"] is True
    assert result["public_dialogue"]["presentation_llm_calls_total"] == 1


def test_live_request_uses_authenticated_native_openwebui_completion_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()
    captured: dict = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def read(limit: int) -> bytes:
            captured["read_limit"] = limit
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "schema_version": (
                                            ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION
                                        ),
                                        "message": "Безопасный ответ",
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        }
                    ]
                },
                ensure_ascii=False,
            ).encode("utf-8")

    class Opener:
        @staticmethod
        def open(outbound, *, timeout):
            captured["url"] = outbound.full_url
            captured["authorization"] = outbound.headers["Authorization"]
            captured["payload"] = json.loads(outbound.data.decode("utf-8"))
            captured["timeout"] = timeout
            return Response()

    def build_opener(handler):
        captured["redirect_handler"] = handler
        return Opener()

    monkeypatch.setattr(pipe_module.urllib.request, "build_opener", build_opener)
    monkeypatch.setattr(
        pipe,
        "_openwebui_completion_dependencies",
        lambda _user_id: (_ for _ in ()).throw(
            AssertionError("live request must use the bounded HTTP boundary")
        ),
    )
    request = type(
        "Request",
        (),
        {
            "base_url": "https://attacker.example/",
            "headers": {"authorization": "Bearer proof-token"},
        },
    )()
    pipe.valves.ndfl_presentation_openwebui_origin = (
        "https://openwebui.internal.example"
    )
    result = asyncio.run(
        pipe._call_openwebui_presentation_completion(
            system_content="system",
            user_content="context",
            response_format=public_dialogue_message_response_format(),
            user={"id": "user-a"},
            request=request,
            task="ordinary_trade_public_dialogue_render",
        )
    )

    assert "Безопасный ответ" in result
    assert captured["url"] == (
        "https://openwebui.internal.example/api/chat/completions"
    )
    assert captured["authorization"] == "Bearer proof-token"
    assert captured["payload"]["model"] == "models/gemini-3.5-flash"
    assert captured["payload"]["metadata"]["broker_reports_gate1"] == {
        "presentation_only": True,
        "task": "ordinary_trade_public_dialogue_render",
    }
    assert captured["timeout"] == 45.0
    assert captured["read_limit"] == 1024 * 1024 + 1
    assert captured["redirect_handler"].redirect_request() is None


@pytest.mark.parametrize(
    "caller_base_url",
    ["https://attacker.example/", "http://169.254.169.254/"],
)
def test_presentation_target_ignores_caller_base_url(
    caller_base_url: str,
) -> None:
    pipe = Pipe()
    pipe.valves.ndfl_presentation_openwebui_origin = "https://openwebui.example"
    request = type(
        "Request",
        (),
        {
            "base_url": caller_base_url,
            "headers": {"authorization": "Bearer SECRET"},
        },
    )()

    assert pipe._openwebui_presentation_http_target(request) == (
        "https://openwebui.example/api/chat/completions",
        "Bearer SECRET",
    )


def test_presentation_target_rejects_non_https_pinned_origin() -> None:
    pipe = Pipe()
    pipe.valves.ndfl_presentation_openwebui_origin = "http://169.254.169.254"
    request = type(
        "Request",
        (),
        {"headers": {"authorization": "Bearer SECRET"}},
    )()

    with pytest.raises(
        NdflWorkflowError,
        match="ndfl_presentation_openwebui_origin_invalid",
    ):
        pipe._openwebui_presentation_http_target(request)


def test_presentation_target_fails_closed_without_bearer() -> None:
    pipe = Pipe()
    pipe.valves.ndfl_presentation_openwebui_origin = "https://openwebui.example"
    request = type("Request", (), {"headers": {}})()

    with pytest.raises(
        NdflWorkflowError,
        match="ndfl_presentation_bearer_required",
    ):
        pipe._openwebui_presentation_http_target(request)


def test_presentation_http_response_is_byte_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        @staticmethod
        def read(limit: int) -> bytes:
            return b"x" * limit

    class Opener:
        @staticmethod
        def open(_outbound, *, timeout):
            assert timeout == 45.0
            return Response()

    monkeypatch.setattr(
        pipe_module.urllib.request,
        "build_opener",
        lambda _handler: Opener(),
    )

    with pytest.raises(
        NdflWorkflowError,
        match="ndfl_presentation_model_http_too_large",
    ):
        pipe._openwebui_presentation_http_completion(
            target=(
                "https://openwebui.example/api/chat/completions",
                "Bearer proof-token",
            ),
            form_data={"model": "safe"},
        )


def test_valid_model_render_is_the_primary_public_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()
    expected_context = build_public_dialogue_context(product=_product())
    model_message = (
        "Давайте продолжим спокойно.\n\n"
        + render_public_dialogue_fallback(expected_context)
    )

    def completion(**_kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "schema_version": (
                                    ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION
                                ),
                                "message": model_message,
                            },
                            ensure_ascii=False,
                        )
                    }
                }
            ]
        }

    monkeypatch.setattr(
        pipe,
        "_openwebui_completion_dependencies",
        lambda user_id: (completion, type("User", (), {"id": user_id})()),
    )
    result = {"provider_calls_total": 0, "product": _product(), "declaration": None}
    content = asyncio.run(
        pipe._render_ndfl_public_dialogue(
            result=result,
            user={"id": "user-a"},
            request=object(),
        )
    )

    assert content == model_message
    assert result["public_dialogue"]["presentation_model_used"] is True
    assert result["public_dialogue"]["presentation_fallback_used"] is False
    assert result["public_dialogue"]["presentation_llm_calls_total"] == 1
    assert result["public_dialogue"]["domain_provider_calls_total"] == 0
