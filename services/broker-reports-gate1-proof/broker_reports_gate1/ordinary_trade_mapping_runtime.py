"""One-attempt source-semantic coordinator for unknown ordinary-trade schemas."""

from __future__ import annotations

import re
from typing import Any

from .artifact_models import ArtifactAccessContext
from .gate2_model_contracts import Gate2SourceFactRuntimeError
from .ordinary_trade_mapping_case import (
    OrdinaryTradeMappingCaseFactory,
)
from .ordinary_trade_semantic_mapping import (
    OrdinaryTradeSemanticMappingError,
    OrdinaryTradeSemanticMappingFactory,
)
from .ordinary_trade_qualified_mappings import (
    OrdinaryTradeQualifiedMappingAuthorityFactory,
)
from .ordinary_trade_semantic_compiler import (
    OrdinaryTradeSemanticCompilerFactory,
)


_USER_CURRENCY_ANSWER = re.compile(
    r"^(?:currency|валюта)\s*:\s*([A-Z]{3})$", re.IGNORECASE
)


FACTORY_REQUIRED = (
    "OrdinaryTradeAutomaticMappingRuntimeFactory.create is the only model-call "
    "coordinator for unknown ordinary-trade schemas and answers"
)
FORBIDDEN = (
    "retry, repair, fallback, direct provider call, mapping invention, regex or "
    "keyword interpretation, unconfirmed answer application, partial Fact v2"
)


class OrdinaryTradeAutomaticMappingError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class OrdinaryTradeAutomaticMappingRuntimeFactory:
    def __init__(
        self,
        *,
        store: Any,
        read_enabled: bool,
        model_client: Any,
        answer_model_client: Any | None = None,
        model_id: str,
        provider_profile_id: str,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._model_client = model_client
        self._answer_model_client = answer_model_client or model_client
        self._model_id = model_id
        self._provider_profile_id = provider_profile_id

    def create(self) -> "OrdinaryTradeAutomaticMappingRuntime":
        if (
            self._model_client is None
            or not isinstance(self._model_id, str)
            or not self._model_id
            or not isinstance(self._provider_profile_id, str)
            or not self._provider_profile_id
        ):
            raise OrdinaryTradeAutomaticMappingError(
                "ordinary_trade_automatic_mapping_configuration_invalid"
            )
        return OrdinaryTradeAutomaticMappingRuntime(
            cases=OrdinaryTradeMappingCaseFactory(
                store=self._store,
                read_enabled=self._read_enabled,
            ).create(),
            semantic=OrdinaryTradeSemanticMappingFactory.create(),
            model_client=self._model_client,
            answer_model_client=self._answer_model_client,
            model_id=self._model_id,
            provider_profile_id=self._provider_profile_id,
            frozen_mappings=(
                OrdinaryTradeQualifiedMappingAuthorityFactory.create().list_mappings()
            ),
            compiler=OrdinaryTradeSemanticCompilerFactory.create(),
        )


class OrdinaryTradeAutomaticMappingRuntime:
    def __init__(
        self,
        *,
        cases: Any,
        semantic: Any,
        model_client: Any,
        answer_model_client: Any,
        model_id: str,
        provider_profile_id: str,
        frozen_mappings: list[dict[str, Any]],
        compiler: Any,
    ) -> None:
        self._cases = cases
        self._semantic = semantic
        self._model_client = model_client
        self._answer_model_client = answer_model_client
        self._model_id = model_id
        self._provider_profile_id = provider_profile_id
        self._frozen_mappings = frozen_mappings
        self._compiler = compiler

    async def resolve(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        user_message: str = "",
        confirmation: bool | None = None,
        expected_confirmation_artifact_id: str | None = None,
    ) -> dict[str, Any]:
        current = self._cases.current(document_id=document_id, context=context)
        if current is not None and current[1]["status"] == "COMPLETE":
            return self._result(
                current=current, context=context, provider_calls_this_turn=0
            )
        if current is not None and current[1]["status"] in {
            "UNSUPPORTED",
            "SPECIALIST_REVIEW_REQUIRED",
            "SOURCE_CONTEXT_LIMIT",
            "MAPPING_OUTPUT_INVALID",
        }:
            return self._result(
                current=current, context=context, provider_calls_this_turn=0
            )
        if current is not None and current[1]["status"] == "CURRENCY_ASSERTION_REQUIRED":
            currency_code = _user_currency_code(user_message)
            if currency_code is None:
                return self._result(
                    current=current, context=context, provider_calls_this_turn=0
                )
            plan = current[1]["pending_candidate"]
            table_node_ids = _currency_plan_table_node_ids(plan)
            prior_currency_code = _confirmed_currency_code(
                confirmed_understandings=current[1]["confirmed_understandings"],
                table_node_ids=table_node_ids,
            )
            if prior_currency_code is not None and prior_currency_code != currency_code:
                return self._result(
                    current=current, context=context, provider_calls_this_turn=0
                )
            response = dict(plan["response"])
            response["status"] = "COMPLETE"
            saved_assertion = current
            if prior_currency_code is None:
                saved_assertion = self._cases.record_user_currency_assertion(
                    document_id=document_id,
                    context=context,
                    currency_code=currency_code,
                    table_node_ids=table_node_ids,
                )
            else:
                saved_assertion = self._cases.resume_existing_currency_assertion(
                    document_id=document_id,
                    context=context,
                    currency_code=currency_code,
                    table_node_ids=table_node_ids,
                )
            if "target_table_node_ids" not in plan:
                # Older private cases did not retain the positional table-ref
                # scope.  Their saved response must not be replayed against a
                # guessed order; rebuild one strict package from the Canonical.
                return await self._map_document(
                    document_id=document_id, context=context
                )
            binding = self._cases.case_binding(document_id=document_id, context=context)
            outcome = self._semantic.validate_mapping_response(
                response=response,
                canonical=binding["canonical"],
                canonical_binding=binding["canonical_binding"],
                model_id=self._model_id,
                provider_profile_id=self._provider_profile_id,
                execution_metadata=plan["execution_metadata"],
                confirmed_understandings=saved_assertion[1]["confirmed_understandings"],
                user_scope_sha256=binding["user_scope_sha256"],
                target_table_node_ids=_currency_plan_target_table_node_ids(plan),
                frozen_mappings=self._frozen_mappings,
            )
            saved = self._cases.save_mapping_outcome(
                document_id=document_id,
                context=context,
                outcome=outcome,
                provider_calls_total=0,
            )
            return self._result(
                current=saved, context=context, provider_calls_this_turn=0
            )
        if current is not None and current[1]["status"] == "CONFIRMATION_REQUIRED":
            if not _is_exclusion_confirmation(current[1]):
                retired = self._cases.save_deterministic_terminal(
                    document_id=document_id,
                    context=context,
                    status="SPECIALIST_REVIEW_REQUIRED",
                    reason_code="ordinary_trade_mapping_interactive_loop_retired",
                    message="Старый технический шаг mapping передан специалисту.",
                )
                return self._result(
                    current=retired, context=context, provider_calls_this_turn=0
                )
            if confirmation is None:
                confirmation = self._semantic.interpret_manual_confirmation(user_message)
                if confirmation is not None:
                    expected_confirmation_artifact_id = current[0].artifact_id
            if confirmation is None:
                return self._result(
                    current=current, context=context, provider_calls_this_turn=0
                )
            if expected_confirmation_artifact_id is None:
                raise OrdinaryTradeAutomaticMappingError(
                    "ordinary_trade_mapping_confirmation_ref_required"
                )
            current = self._cases.confirm_pending_answer(
                document_id=document_id,
                context=context,
                expected_artifact_id=expected_confirmation_artifact_id,
                accepted=confirmation,
            )
            if not confirmation:
                return self._result(
                    current=current, context=context, provider_calls_this_turn=0
                )
        if current is not None and current[1]["status"] == "CLARIFICATION_REQUIRED":
            if _is_exclusion_confirmation(current[1]):
                promoted = self._cases.promote_exclusion_confirmation(
                    document_id=document_id, context=context
                )
                return self._result(
                    current=promoted, context=context, provider_calls_this_turn=0
                )
            retired = self._cases.save_deterministic_terminal(
                document_id=document_id,
                context=context,
                status="SPECIALIST_REVIEW_REQUIRED",
                reason_code="ordinary_trade_mapping_interactive_loop_retired",
                message="Техническая неоднозначность mapping передана специалисту.",
            )
            return self._result(
                current=retired, context=context, provider_calls_this_turn=0
            )
        if (
            current is not None
            and current[1]["status"] == "PROVIDER_UNAVAILABLE"
        ):
            return await self._map_document(document_id=document_id, context=context)
        return await self._map_document(
            document_id=document_id,
            context=context,
        )

    async def _map_document(
        self, *, document_id: str, context: ArtifactAccessContext
    ) -> dict[str, Any]:
        binding = self._cases.case_binding(
            document_id=document_id, context=context
        )
        current = self._cases.current(document_id=document_id, context=context)
        confirmed = (
            current[1]["confirmed_understandings"] if current is not None else []
        )
        target_table_node_ids = self._compiler.unmapped_table_node_ids(
            canonical=binding["canonical"],
            mappings=self._frozen_mappings,
        )
        confirmed_exclusion_ids = {
            str((item.get("decision") or {}).get("table_node_id") or "")
            for item in confirmed
            if (item.get("decision") or {}).get("decision_kind")
            == "TABLE_DISPOSITION"
            and (item.get("decision") or {}).get("disposition")
            == "NO_NAMED_CONSUMER"
        }
        target_table_node_ids = [
            table_node_id
            for table_node_id in target_table_node_ids
            if table_node_id not in confirmed_exclusion_ids
        ]
        if not target_table_node_ids:
            saved = self._cases.save_deterministic_terminal(
                document_id=document_id,
                context=context,
                status="SPECIALIST_REVIEW_REQUIRED",
                reason_code="ordinary_trade_known_mapping_row_incomplete",
                message=(
                    "Exact schema mapping is already known, but at least one source "
                    "row is incomplete for the ordinary-trade consumer. No semantic "
                    "remapping or partial facts were applied."
                ),
            )
            return self._result(
                current=saved,
                context=context,
                provider_calls_this_turn=0,
            )
        try:
            package = self._semantic.build_mapping_package(
                canonical=binding["canonical"],
                confirmed_understandings=confirmed,
                target_table_node_ids=target_table_node_ids,
            )
        except OrdinaryTradeSemanticMappingError as exc:
            if exc.code != "ordinary_trade_semantic_mapping_context_limit":
                raise
            saved = self._cases.save_provider_terminal(
                document_id=document_id,
                context=context,
                status="SOURCE_CONTEXT_LIMIT",
                reason_code=exc.code,
                message=(
                    "Структура отчёта слишком велика для безопасного semantic "
                    "mapping; требуется специалист."
                ),
                provider_calls_total=0,
            )
            return self._result(
                current=saved, context=context, provider_calls_this_turn=0
            )
        try:
            response = await self._model_client.extract(
                prompt=self._semantic.mapping_prompt(),
                package=package,
                model_id=self._model_id,
                response_format=self._semantic.mapping_response_format(),
            )
        except Exception as exc:
            code = getattr(exc, "code", "ordinary_trade_mapping_provider_failed")
            saved = self._cases.save_provider_terminal(
                document_id=document_id,
                context=context,
                status="PROVIDER_UNAVAILABLE",
                reason_code=str(code),
                message=(
                    "Модель semantic mapping сейчас недоступна. Сохранённый case "
                    "можно безопасно продолжить позже."
                ),
                provider_calls_total=1,
            )
            return self._result(
                current=saved, context=context, provider_calls_this_turn=1
            )
        try:
            _strict_result(response)
            contract_failure = self._semantic.mapping_response_contract_failure_code(
                response
            )
            if contract_failure is not None:
                raise OrdinaryTradeSemanticMappingError(contract_failure)
            outcome = self._semantic.validate_mapping_response(
                response=response,
                canonical=binding["canonical"],
                canonical_binding=binding["canonical_binding"],
                model_id=self._model_id,
                provider_profile_id=self._provider_profile_id,
                execution_metadata=response.execution_metadata,
                confirmed_understandings=confirmed,
                user_scope_sha256=binding["user_scope_sha256"],
                target_table_node_ids=target_table_node_ids,
                frozen_mappings=self._frozen_mappings,
            )
        except Exception as exc:
            code = getattr(
                exc, "code", "ordinary_trade_semantic_mapping_output_invalid"
            )
            incomplete = str(code) in {
                "ordinary_trade_semantic_mapping_side_invalid",
                "ordinary_trade_semantic_mapping_dry_run_incomplete",
            }
            saved = self._cases.save_provider_terminal(
                document_id=document_id,
                context=context,
                status="MAPPING_OUTPUT_INVALID",
                reason_code=str(code),
                message=(
                    (
                        "Mapping не покрывает все значения и строки полного "
                        "Canonical. Факты не опубликованы; требуется уточнение "
                        "mapping или проверка специалиста."
                    )
                    if incomplete
                    else (
                        "Ответ модели противоречив или не связан с Canonical. "
                        "Факты не опубликованы; требуется проверка специалиста."
                    )
                ),
                provider_calls_total=1,
            )
            return self._result(
                current=saved, context=context, provider_calls_this_turn=1
            )
        if outcome["status"] == "CLARIFICATION_REQUIRED":
            saved = self._cases.save_mapping_outcome(
                document_id=document_id,
                context=context,
                outcome=outcome,
                provider_calls_total=1,
            )
            if _is_exclusion_confirmation(saved[1]):
                promoted = self._cases.promote_exclusion_confirmation(
                    document_id=document_id, context=context
                )
                return self._result(
                    current=promoted, context=context, provider_calls_this_turn=1
                )
            retired = self._cases.save_deterministic_terminal(
                document_id=document_id,
                context=context,
                status="SPECIALIST_REVIEW_REQUIRED",
                reason_code="ordinary_trade_mapping_interactive_loop_forbidden",
                message="Техническая неоднозначность mapping передана специалисту.",
            )
            return self._result(
                current=retired, context=context, provider_calls_this_turn=1
            )
        if outcome["status"] == "CURRENCY_ASSERTION_REQUIRED":
            saved = self._cases.save_mapping_outcome(
                document_id=document_id,
                context=context,
                outcome=outcome,
                provider_calls_total=1,
            )
            return self._result(
                current=saved, context=context, provider_calls_this_turn=1
            )
        saved = self._cases.save_mapping_outcome(
            document_id=document_id,
            context=context,
            outcome=outcome,
            provider_calls_total=1,
        )
        return self._result(
            current=saved, context=context, provider_calls_this_turn=1
        )

    async def _interpret_answer(
        self,
        *,
        document_id: str,
        context: ArtifactAccessContext,
        current: tuple[Any, dict[str, Any]],
        user_message: str,
    ) -> dict[str, Any]:
        payload = current[1]
        package = self._semantic.build_answer_package(
            question=payload["question"],
            user_message=user_message,
        )
        try:
            response = await self._answer_model_client.extract(
                prompt=self._semantic.answer_prompt(),
                package=package,
                model_id=self._model_id,
                response_format=self._semantic.answer_response_format(),
            )
        except Exception as exc:
            code = getattr(exc, "code", "ordinary_trade_mapping_provider_failed")
            saved = self._cases.save_provider_terminal(
                document_id=document_id,
                context=context,
                status="PROVIDER_UNAVAILABLE",
                reason_code=str(code),
                message=(
                    "Модель понимания ответа сейчас недоступна. Mapping case "
                    "сохранён и может быть продолжен позже."
                ),
                provider_calls_total=1,
            )
            return self._result(
                current=saved, context=context, provider_calls_this_turn=1
            )
        try:
            _strict_result(response)
            interpretation = self._semantic.validate_answer_response(
                response=response,
                question=payload["question"],
                user_message=user_message,
            )
        except Exception as exc:
            code = getattr(exc, "code", "ordinary_trade_mapping_answer_invalid")
            saved = self._cases.save_provider_terminal(
                document_id=document_id,
                context=context,
                status="MAPPING_OUTPUT_INVALID",
                reason_code=str(code),
                message=(
                    "Ответ не удалось безопасно связать с текущим вопросом. "
                    "Состояние mapping не изменено финансовым решением."
                ),
                provider_calls_total=1,
            )
            return self._result(
                current=saved, context=context, provider_calls_this_turn=1
            )
        saved = self._cases.save_answer_candidate(
            document_id=document_id,
            context=context,
            interpretation=interpretation,
            provider_calls_total=1,
        )
        return self._result(
            current=saved, context=context, provider_calls_this_turn=1
        )

    def _result(
        self,
        *,
        current: tuple[Any, dict[str, Any]],
        context: ArtifactAccessContext,
        provider_calls_this_turn: int,
    ) -> dict[str, Any]:
        record, payload = current
        return {
            "schema_version": "broker_reports_ordinary_trade_mapping_turn_v1",
            "status": payload["status"],
            "mapping_case_artifact_id": record.artifact_id,
            "provider_calls_this_turn": provider_calls_this_turn,
            "public_state": self._cases.public_state(
                document_id=str(record.document_id),
                context=context,
            ),
        }


def _strict_result(response: Any) -> None:
    if (
        response is None
        or getattr(response, "structured_output_mode", None)
        != "openwebui_response_format_json_schema"
        or getattr(response, "response_format_type", None) != "json_schema"
        or getattr(response, "response_format_schema_mode", None)
        != "strict_json_schema"
        or getattr(response, "fallback_used", None) is not False
        or getattr(response, "repair_attempt_count", None) != 0
        or getattr(response, "execution_metadata", None) is None
    ):
        raise Gate2SourceFactRuntimeError(
            "ordinary_trade_mapping_strict_output_required",
            "Semantic mapping requires one strict output without repair",
        )


def _is_exclusion_confirmation(payload: dict[str, Any]) -> bool:
    question = payload.get("question")
    return isinstance(question, dict) and question.get("question_id") == "q_exclusion_batch"


def _user_currency_code(user_message: str) -> str | None:
    """Accept only the code-owned, explicitly rendered currency answer."""

    match = _USER_CURRENCY_ANSWER.fullmatch(str(user_message or "").strip())
    return match.group(1).upper() if match is not None else None


def _currency_plan_table_node_ids(plan: dict[str, Any]) -> list[str]:
    """Accept only node ids frozen by the semantic owner in the pending case."""

    table_node_ids = plan.get("table_node_ids")
    if (
        not isinstance(table_node_ids, list)
        or not table_node_ids
        or table_node_ids != sorted(set(table_node_ids))
        or any(not isinstance(item, str) or not item for item in table_node_ids)
    ):
        raise OrdinaryTradeAutomaticMappingError(
            "ordinary_trade_user_currency_request_invalid"
        )
    return list(table_node_ids)


def _currency_plan_target_table_node_ids(plan: dict[str, Any]) -> list[str]:
    """Use the source scope frozen with a currency request, never a broad retry."""

    target = plan.get("target_table_node_ids")
    if (
        not isinstance(target, list)
        or not target
        or len(target) != len(set(target))
        or any(not isinstance(item, str) or not item for item in target)
    ):
        raise OrdinaryTradeAutomaticMappingError(
            "ordinary_trade_user_currency_request_invalid"
        )
    return list(target)


def _confirmed_currency_code(
    *, confirmed_understandings: list[dict[str, Any]], table_node_ids: list[str]
) -> str | None:
    """Return one previously accepted user value only for the exact table scope."""

    matches = {
        decision.get("currency_code")
        for item in confirmed_understandings
        if isinstance(item, dict)
        and isinstance((decision := item.get("decision")), dict)
        and decision.get("decision_kind") == "USER_PROVIDED_CURRENCY"
        and set(table_node_ids).issubset(set(decision.get("table_node_ids") or []))
        and isinstance(decision.get("currency_code"), str)
        and re.fullmatch(r"[A-Z]{3}", decision["currency_code"]) is not None
    }
    if len(matches) > 1:
        raise OrdinaryTradeAutomaticMappingError(
            "ordinary_trade_user_currency_assertion_ambiguous"
        )
    return next(iter(matches), None)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "OrdinaryTradeAutomaticMappingError",
    "OrdinaryTradeAutomaticMappingRuntime",
    "OrdinaryTradeAutomaticMappingRuntimeFactory",
]
