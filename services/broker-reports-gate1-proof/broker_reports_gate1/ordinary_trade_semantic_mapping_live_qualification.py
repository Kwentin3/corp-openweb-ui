"""One-shot local bridge for the Goal #391 mapping R&D call.

The bridge composes the existing Gate 2 client with the existing mapping
qualification runner.  It deliberately does not know how an authenticated
OpenWebUI request is sent: the caller injects that one boundary.  This keeps
browser/session credentials, provider configuration, persisted chats and the
product Pipe outside the R&D seam.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping

from .gate2_model_clients import Gate2StructuredModelClientFactory
from .gate2_model_contracts import Gate2StructuredModelClientConfig
from .gate2_model_requests import ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE
from .ordinary_trade_mapping_prompt import (
    OrdinaryTradeMappingManagedPrompt,
    validate_ordinary_trade_mapping_prompt_snapshot,
)
from .ordinary_trade_semantic_mapping_qualification import (
    OrdinaryTradeSemanticMappingQualificationFactory,
)


LIVE_QUALIFICATION_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_semantic_mapping_live_qualification_receipt_v1"
)
GOAL391_PROVIDER_PROFILE_ID = "google_gemini"
GOAL391_MODEL_ID = "models/gemini-3.5-flash"


class OrdinaryTradeSemanticMappingLiveQualificationError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


CompletionRequest = Callable[[dict[str, Any]], Any | Awaitable[Any]]


@dataclass(frozen=True)
class _AuthenticatedUser:
    id: str


class StatelessOpenWebUICompletionResolver:
    """Adapt one authenticated, stateless OpenWebUI completion call.

    ``call_chat_completions_once`` is the sole network seam.  A browser-side
    adapter may implement it with ``fetch('/api/chat/completions', ...)`` and
    its ambient ordinary-user session; this module never sees a token, cookie,
    provider key or server configuration.
    """

    def __init__(
        self,
        *,
        authenticated_user_id: str,
        call_chat_completions_once: CompletionRequest,
    ) -> None:
        if not isinstance(authenticated_user_id, str) or not authenticated_user_id:
            raise OrdinaryTradeSemanticMappingLiveQualificationError(
                "ordinary_trade_mapping_live_authenticated_user_required"
            )
        if not callable(call_chat_completions_once):
            raise OrdinaryTradeSemanticMappingLiveQualificationError(
                "ordinary_trade_mapping_live_completion_boundary_required"
            )
        self._authenticated_user = _AuthenticatedUser(id=authenticated_user_id)
        self._call_chat_completions_once = call_chat_completions_once
        self._calls_total = 0

    def __call__(self, user_id: str):
        if user_id != self._authenticated_user.id:
            raise OrdinaryTradeSemanticMappingLiveQualificationError(
                "ordinary_trade_mapping_live_user_scope_mismatch"
            )
        return self._complete_once, self._authenticated_user

    @property
    def calls_total(self) -> int:
        return self._calls_total

    def _complete_once(self, *, request, form_data, user, **_ignored):
        if request is None or getattr(user, "id", None) != self._authenticated_user.id:
            raise OrdinaryTradeSemanticMappingLiveQualificationError(
                "ordinary_trade_mapping_live_authenticated_request_required"
            )
        _validate_stateless_form_data(form_data)
        if self._calls_total != 0:
            raise OrdinaryTradeSemanticMappingLiveQualificationError(
                "ordinary_trade_mapping_live_single_call_exceeded"
            )
        self._calls_total = 1
        return self._call_chat_completions_once(copy.deepcopy(form_data))


class OrdinaryTradeSemanticMappingLiveQualificationFactory:
    """Compose exactly the existing client and validator for a local R&D run."""

    def __init__(
        self,
        *,
        request: Any,
        authenticated_user_id: str,
        call_chat_completions_once: CompletionRequest,
        mapping_prompt: OrdinaryTradeMappingManagedPrompt,
    ) -> None:
        self._request = request
        self._resolver = StatelessOpenWebUICompletionResolver(
            authenticated_user_id=authenticated_user_id,
            call_chat_completions_once=call_chat_completions_once,
        )
        self._user = _AuthenticatedUser(id=authenticated_user_id)
        try:
            validate_ordinary_trade_mapping_prompt_snapshot(mapping_prompt.snapshot())
        except Exception as exc:
            raise OrdinaryTradeSemanticMappingLiveQualificationError(
                "ordinary_trade_mapping_live_prompt_invalid"
            ) from exc
        if mapping_prompt.source != "openwebui_prompt_history":
            raise OrdinaryTradeSemanticMappingLiveQualificationError(
                "ordinary_trade_mapping_live_native_prompt_required"
            )
        self._mapping_prompt = mapping_prompt

    def create(self) -> "OrdinaryTradeSemanticMappingLiveQualificationRunner":
        if self._request is None:
            raise OrdinaryTradeSemanticMappingLiveQualificationError(
                "ordinary_trade_mapping_live_authenticated_request_required"
            )
        client = Gate2StructuredModelClientFactory(
            config=Gate2StructuredModelClientConfig(
                request_profile=ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
                provider_profile_id=GOAL391_PROVIDER_PROFILE_ID,
                transport="openwebui",
                capability_probe=False,
                economy_budget_enforcement=False,
            ),
            user=self._user,
            request=self._request,
            completion_resolver=self._resolver,
        ).create()
        return OrdinaryTradeSemanticMappingLiveQualificationRunner(
            qualification=OrdinaryTradeSemanticMappingQualificationFactory(
                model_client=client, mapping_prompt=self._mapping_prompt
            ).create(),
            resolver=self._resolver,
        )


class OrdinaryTradeSemanticMappingLiveQualificationRunner:
    def __init__(self, *, qualification, resolver) -> None:
        self._qualification = qualification
        self._resolver = resolver

    async def run(self, *, fixture: Mapping[str, Any]) -> dict[str, Any]:
        receipt = await self._qualification.run(
            fixture=fixture,
            model_id=GOAL391_MODEL_ID,
            provider_profile_id=GOAL391_PROVIDER_PROFILE_ID,
        )
        if self._resolver.calls_total != 1:
            raise OrdinaryTradeSemanticMappingLiveQualificationError(
                "ordinary_trade_mapping_live_single_call_required"
            )
        return {
            **receipt,
            "schema_version": LIVE_QUALIFICATION_RECEIPT_SCHEMA_VERSION,
            "transport": "openwebui_chat_completions_stateless_injected_v1",
            "chat_persistence": "forbidden",
        }


def _validate_stateless_form_data(value: Any) -> None:
    if not isinstance(value, dict) or value.get("stream") is not False:
        raise OrdinaryTradeSemanticMappingLiveQualificationError(
            "ordinary_trade_mapping_live_stateless_request_invalid"
        )
    forbidden = {"chat_id", "parent_id", "id", "user_message", "files"}
    if forbidden.intersection(value):
        raise OrdinaryTradeSemanticMappingLiveQualificationError(
            "ordinary_trade_mapping_live_chat_persistence_forbidden"
        )


__all__ = [
    "GOAL391_MODEL_ID",
    "GOAL391_PROVIDER_PROFILE_ID",
    "LIVE_QUALIFICATION_RECEIPT_SCHEMA_VERSION",
    "OrdinaryTradeSemanticMappingLiveQualificationError",
    "OrdinaryTradeSemanticMappingLiveQualificationFactory",
    "OrdinaryTradeSemanticMappingLiveQualificationRunner",
    "StatelessOpenWebUICompletionResolver",
]
