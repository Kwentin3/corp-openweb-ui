from __future__ import annotations

import asyncio
import json

import pytest

from broker_reports_gate1.ordinary_trade_declaration_chat_adapter import (
    ORDINARY_TRADE_PUBLIC_ANSWER_INTERPRETATION_SCHEMA_VERSION,
    ORDINARY_TRADE_PUBLIC_DIALOGUE_MESSAGE_SCHEMA_VERSION,
    PUBLIC_DIALOGUE_MODEL_BOUNDARY,
    build_public_dialogue_context,
    build_public_question_context,
    public_dialogue_context_sha256,
    render_public_dialogue_fallback,
    validate_public_answer_interpretation,
    validate_public_dialogue_message,
)
from openwebui_actions.broker_reports_gate1_pipe import Pipe


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


def test_presentation_model_boundary_is_local_and_has_no_business_authority() -> None:
    assert PUBLIC_DIALOGUE_MODEL_BOUNDARY == {
        "classification": "PRESENTATION_ADAPTER",
        "uncertainty": "plain_language_dialogue_wording_and_answer_phrasing",
        "strict_contracts": [
            "broker_reports_ordinary_trade_public_dialogue_message_v1",
            "broker_reports_ordinary_trade_public_answer_interpretation_v1",
        ],
        "business_authority": False,
    }


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


def test_interpretation_contract_cannot_select_request_or_fact_identity() -> None:
    question = build_public_question_context(_request())
    assert question is not None
    accepted = validate_public_answer_interpretation(
        {
            "schema_version": (
                ORDINARY_TRADE_PUBLIC_ANSWER_INTERPRETATION_SCHEMA_VERSION
            ),
            "disposition": "ANSWER_CANDIDATE",
            "normalized_answer": "Первичная декларация",
            "clarification": None,
        },
        question_context=question,
    )
    assert accepted["normalized_answer"] == "Первичная декларация"

    with pytest.raises(ValueError, match="shape_invalid"):
        validate_public_answer_interpretation(
            {
                "schema_version": (
                    ORDINARY_TRADE_PUBLIC_ANSWER_INTERPRETATION_SCHEMA_VERSION
                ),
                "disposition": "ANSWER_CANDIDATE",
                "normalized_answer": "Первичная декларация",
                "clarification": None,
                "request_publication_ref": "art_" + "b" * 32,
            },
            question_context=question,
        )


def test_pipe_model_candidate_is_rebound_to_current_owner_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipe = Pipe()
    calls: list[dict] = []

    def completion(*, request, form_data, user, **_kwargs):
        calls.append(form_data)
        assert request is not None
        assert user.id == "user-a"
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "schema_version": (
                                    ORDINARY_TRADE_PUBLIC_ANSWER_INTERPRETATION_SCHEMA_VERSION
                                ),
                                "disposition": "ANSWER_CANDIDATE",
                                "normalized_answer": "Первичная декларация",
                                "clarification": None,
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
    adapted, dialogue = asyncio.run(
        pipe._adapt_ndfl_public_answer(
            message="Это будет моя первая декларация.",
            current_actions=[_request()],
            user={"id": "user-a"},
            request=object(),
            event_call=None,
        )
    )

    assert adapted == {
        "schema_version": "broker_reports_ordinary_trade_declaration_chat_action_v1",
        "status": "ANSWER_READY",
        "request_publication_ref": "art_" + "a" * 32,
        "answer": {"kind": "code", "value": "INITIAL"},
    }
    assert dialogue["interpretation_model_used"] is True
    assert dialogue["presentation_llm_calls_total"] == 1
    model_input = calls[0]["messages"][1]["content"]
    assert "request_publication_ref" not in model_input
    assert "fact_key" not in model_input
    assert "INITIAL" not in model_input


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
