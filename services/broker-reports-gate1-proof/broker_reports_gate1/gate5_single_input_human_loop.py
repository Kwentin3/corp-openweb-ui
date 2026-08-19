"""One missing money input through a strict structured human interaction."""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass
from typing import Any

from .artifact_models import ArtifactAccessContext, ArtifactStorePort, RetentionPolicy
from .gate2_model_contracts import (
    Gate2StructuredModelClient,
    Gate2StructuredModelResult,
)
from .gate5_supplemental_fact import (
    GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
    Gate5SupplementalFactRuntime,
    Gate5SupplementalFactRuntimeFactory,
)
from .gate5_supplemental_fact_discovery import (
    Gate5SupplementalFactDiscoveryRuntime,
    Gate5SupplementalFactDiscoveryRuntimeFactory,
)


GATE5_SINGLE_INPUT_QUESTION_SCHEMA_VERSION = (
    "broker_reports_gate5_single_input_question_v0"
)
GATE5_SINGLE_INPUT_QUESTION_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_single_input_question_result_v0"
)
GATE5_SINGLE_INPUT_PROPOSAL_SCHEMA_VERSION = (
    "broker_reports_gate5_single_input_proposal_v0"
)
GATE5_SINGLE_INPUT_SUBMISSION_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_single_input_submission_result_v0"
)

FACTORY_REQUIRED = (
    "Gate5SingleInputHumanLoopRuntimeFactory.create",
    "Gate2StructuredModelClientFactory.create supplies the model client",
    "Gate5SupplementalFactDiscoveryRuntimeFactory.create owns missing/recheck",
    "Gate5SupplementalFactRuntimeFactory.create owns persistence",
)
FORBIDDEN = (
    "direct provider SDK, HTTP or OpenWebUI completion calls",
    "model-visible case, user, run, workspace or artifact identity",
    "LLM-owned scope, fact binding or persistence",
    "TaxInterviewEngine, workflow, Tax Case or multi-input collection",
)

_PROMPT_CONTENT = """You are a conversational adapter for exactly one missing money input.
The user message is a closed JSON object with phase `ask` or `interpret`.
For `ask`, return one concise Russian question that asks for the missing amount and currency.
For `interpret`, use only `human_answer`. Return `propose_fact` only when one exact amount and currency are unambiguous; otherwise return `needs_clarification` with null values.
For `propose_fact`, format amount with exactly two fractional digits and currency as an uppercase three-letter ISO code.
Never invent a value. Return only an object allowed by the supplied strict JSON Schema."""
_PROMPT_HASH = hashlib.sha256(_PROMPT_CONTENT.encode("utf-8")).hexdigest()

_QUESTION_KEYS = frozenset({"schema_version", "action", "question_text"})
_PROPOSAL_KEYS = frozenset({"schema_version", "action", "amount", "currency"})
_CANONICAL_MONEY = re.compile(r"^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_ANSWER_AMOUNT = re.compile(
    r"(?<![0-9])"
    r"(?P<whole>(?:[1-9][0-9]{0,2}(?:[ \u00a0][0-9]{3}){1,5}|0|[1-9][0-9]{0,17}))"
    r"(?P<fraction>[.,][0-9]{1,2})?"
    r"(?![0-9])"
)
_ANSWER_CURRENCY = re.compile(
    r"(?<![A-Za-zА-Яа-яЁё])"
    r"(?P<word>RUB|RUR|руб(?:\.|ля|лей|ль|ли)?)"
    r"(?![A-Za-zА-Яа-яЁё])|(?P<symbol>₽)",
    re.IGNORECASE,
)


class Gate5SingleInputHumanLoopError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _ManagedPrompt:
    prompt_ref: str = "broker_reports_gate5_single_input_hitl_v0"
    content: str = _PROMPT_CONTENT
    hash: str = _PROMPT_HASH


class Gate5SingleInputHumanLoopRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
        retention_policy: RetentionPolicy,
        model_client: Gate2StructuredModelClient,
        model_id: str,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._retention_policy = retention_policy
        self._model_client = model_client
        self._model_id = model_id

    def create(self) -> "Gate5SingleInputHumanLoopRuntime":
        if (
            not isinstance(self._model_id, str)
            or not self._model_id
            or self._model_id != self._model_id.strip()
            or not callable(getattr(self._model_client, "extract", None))
        ):
            raise Gate5SingleInputHumanLoopError(
                "gate5_single_input_model_client_invalid"
            )
        discovery = Gate5SupplementalFactDiscoveryRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
            retention_policy=self._retention_policy,
        ).create()
        supplemental = Gate5SupplementalFactRuntimeFactory(
            store=self._store,
            retention_policy=self._retention_policy,
        ).create()
        return Gate5SingleInputHumanLoopRuntime(
            discovery=discovery,
            supplemental=supplemental,
            model_client=self._model_client,
            model_id=self._model_id,
            prompt=_ManagedPrompt(),
        )


class Gate5SingleInputHumanLoopRuntime:
    def __init__(
        self,
        *,
        discovery: Gate5SupplementalFactDiscoveryRuntime,
        supplemental: Gate5SupplementalFactRuntime,
        model_client: Gate2StructuredModelClient,
        model_id: str,
        prompt: _ManagedPrompt,
    ) -> None:
        self._discovery = discovery
        self._supplemental = supplemental
        self._model_client = model_client
        self._model_id = model_id
        self._prompt = prompt

    async def ask(
        self,
        *,
        methodology: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        requirement, _check = self._one_missing_requirement(
            methodology=methodology,
            context=context,
        )
        result = await self._model_client.extract(
            prompt=self._prompt,
            package=_model_package(requirement=requirement, phase="ask"),
            model_id=self._model_id,
            response_format=gate5_single_input_question_response_format(),
        )
        question = _validated_question(_strict_content(result))
        return {
            "schema_version": GATE5_SINGLE_INPUT_QUESTION_RESULT_SCHEMA_VERSION,
            "status": "awaiting_human",
            "question": question,
        }

    async def submit(
        self,
        *,
        methodology: dict[str, Any],
        human_answer: str,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        answer = _validated_human_answer(human_answer)
        requirement, before = self._one_missing_requirement(
            methodology=methodology,
            context=context,
        )
        result = await self._model_client.extract(
            prompt=self._prompt,
            package=_model_package(
                requirement=requirement,
                phase="interpret",
                human_answer=answer,
            ),
            model_id=self._model_id,
            response_format=gate5_single_input_proposal_response_format(),
        )
        proposal = _validated_proposal_shape(_strict_content(result))
        validation_errors = _proposal_validation_errors(
            proposal=proposal,
            human_answer=answer,
        )
        if validation_errors:
            return {
                "schema_version": (GATE5_SINGLE_INPUT_SUBMISSION_RESULT_SCHEMA_VERSION),
                "status": "rejected",
                "proposal": copy.deepcopy(proposal),
                "validation": {
                    "status": "failed",
                    "errors": validation_errors,
                },
                "supplemental_fact_ref": None,
                "requirement_check": before,
            }

        stored = self._supplemental.put(
            supplemental_input={
                "schema_version": GATE5_SUPPLEMENTAL_FACT_INPUT_SCHEMA_VERSION,
                "requirement_ref": requirement["requirement_id"],
                "subject_ref": requirement["subject_ref"],
                "fact_key": requirement["value_key"],
                "value": {
                    "kind": "money",
                    "amount": proposal["amount"],
                    "currency": proposal["currency"],
                },
            },
            context=context,
        )
        after = self._discovery.check(
            methodology=methodology,
            context=context,
        )
        selected = next(
            (
                item
                for item in after["requirements"]
                if item["requirement_id"] == requirement["requirement_id"]
            ),
            None,
        )
        if not isinstance(selected, dict) or selected.get("status") != "satisfied":
            raise Gate5SingleInputHumanLoopError(
                "gate5_single_input_persisted_requirement_not_satisfied"
            )
        return {
            "schema_version": GATE5_SINGLE_INPUT_SUBMISSION_RESULT_SCHEMA_VERSION,
            "status": "accepted",
            "proposal": copy.deepcopy(proposal),
            "validation": {"status": "passed", "errors": []},
            "supplemental_fact_ref": stored["supplemental_fact_ref"],
            "requirement_check": after,
        }

    def _one_missing_requirement(
        self,
        *,
        methodology: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        check = self._discovery.check(
            methodology=methodology,
            context=context,
        )
        missing = [
            item for item in check["requirements"] if item["status"] == "missing"
        ]
        if len(missing) != 1:
            raise Gate5SingleInputHumanLoopError(
                "gate5_single_input_exactly_one_missing_required"
            )
        return missing[0], check


def gate5_single_input_question_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "gate5_single_input_question",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["schema_version", "action", "question_text"],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "const": GATE5_SINGLE_INPUT_QUESTION_SCHEMA_VERSION,
                    },
                    "action": {"type": "string", "const": "ask_user"},
                    "question_text": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 700,
                    },
                },
            },
        },
    }


def gate5_single_input_proposal_response_format() -> dict[str, Any]:
    nullable_amount = {
        "anyOf": [
            {"type": "string", "pattern": r"^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$"},
            {"type": "null"},
        ]
    }
    nullable_currency = {
        "anyOf": [
            {"type": "string", "pattern": r"^[A-Z]{3}$"},
            {"type": "null"},
        ]
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "gate5_single_input_proposal",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": ["schema_version", "action", "amount", "currency"],
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "const": GATE5_SINGLE_INPUT_PROPOSAL_SCHEMA_VERSION,
                    },
                    "action": {
                        "type": "string",
                        "enum": ["propose_fact", "needs_clarification"],
                    },
                    "amount": nullable_amount,
                    "currency": nullable_currency,
                },
            },
        },
    }


def _model_package(
    *,
    requirement: dict[str, Any],
    phase: str,
    human_answer: str | None = None,
) -> dict[str, Any]:
    package = {
        "phase": phase,
        "missing_input": {
            "financial_type": requirement["financial_type"],
            "value_key": requirement["value_key"],
            "value_kind": "money",
            "currency_required": True,
        },
    }
    if phase == "interpret":
        package["human_answer"] = human_answer
    return package


def _strict_content(result: Any) -> dict[str, Any]:
    if (
        not isinstance(result, Gate2StructuredModelResult)
        or result.structured_output_mode != "openwebui_response_format_json_schema"
        or result.response_format_type != "json_schema"
        or result.response_format_schema_mode != "strict_json_schema"
        or result.fallback_used is not False
        or not isinstance(result.content, dict)
    ):
        raise Gate5SingleInputHumanLoopError(
            "gate5_single_input_strict_model_output_required"
        )
    return copy.deepcopy(result.content)


def _validated_question(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _QUESTION_KEYS
        or value.get("schema_version") != GATE5_SINGLE_INPUT_QUESTION_SCHEMA_VERSION
        or value.get("action") != "ask_user"
        or not isinstance(value.get("question_text"), str)
        or not value["question_text"]
        or value["question_text"] != value["question_text"].strip()
        or len(value["question_text"]) > 700
    ):
        raise Gate5SingleInputHumanLoopError("gate5_single_input_question_invalid")
    return copy.deepcopy(value)


def _validated_human_answer(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 700
    ):
        raise Gate5SingleInputHumanLoopError("gate5_single_input_human_answer_invalid")
    return value


def _validated_proposal_shape(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _PROPOSAL_KEYS
        or value.get("schema_version") != GATE5_SINGLE_INPUT_PROPOSAL_SCHEMA_VERSION
        or value.get("action") not in {"propose_fact", "needs_clarification"}
    ):
        raise Gate5SingleInputHumanLoopError("gate5_single_input_proposal_invalid")
    action = value["action"]
    amount = value.get("amount")
    currency = value.get("currency")
    if action == "needs_clarification":
        valid = amount is None and currency is None
    else:
        valid = (
            isinstance(amount, str)
            and _CANONICAL_MONEY.fullmatch(amount) is not None
            and isinstance(currency, str)
            and _CURRENCY.fullmatch(currency) is not None
        )
    if not valid:
        raise Gate5SingleInputHumanLoopError("gate5_single_input_proposal_invalid")
    return copy.deepcopy(value)


def _proposal_validation_errors(
    *,
    proposal: dict[str, Any],
    human_answer: str,
) -> list[str]:
    if proposal["action"] == "needs_clarification":
        return ["human_answer_needs_clarification"]
    amounts = [
        _normalized_amount(match) for match in _ANSWER_AMOUNT.finditer(human_answer)
    ]
    currencies = {
        _normalized_currency(match) for match in _ANSWER_CURRENCY.finditer(human_answer)
    }
    errors: list[str] = []
    if len(amounts) != 1:
        errors.append("human_answer_amount_ambiguous")
    if len(currencies) != 1:
        errors.append("human_answer_currency_ambiguous")
    if len(amounts) == 1 and proposal["amount"] != amounts[0]:
        errors.append("proposal_amount_not_supported_by_answer")
    if len(currencies) == 1 and proposal["currency"] not in currencies:
        errors.append("proposal_currency_not_supported_by_answer")
    return errors


def _normalized_amount(match: re.Match[str]) -> str:
    whole = match.group("whole").replace(" ", "").replace("\u00a0", "")
    fraction = (match.group("fraction") or "").lstrip(".,")
    return f"{int(whole)}.{fraction.ljust(2, '0')}"


def _normalized_currency(match: re.Match[str]) -> str:
    word = (match.group("word") or "").upper()
    return (
        "RUB"
        if match.group("symbol") or word == "RUR" or word.startswith("РУБ")
        else word
    )
