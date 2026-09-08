"""
title: Goal 391 Mapping Lab
author: Alpha Soft
version: 0.1.0-native-lab
required_open_webui_version: 0.9.6
requirements: pydantic

Native, non-product qualification adapter for the Goal #391 mapping seam.

This Pipe deliberately owns no corpus, mapping rule, prompt body, storage or
provider credential.  A server-side lab harness injects a pre-authorized,
already-bound case loader.  The Pipe only composes the established Prompt,
mapping and native OpenWebUI completion owners into one stateless, bounded
attempt and returns a value-free receipt.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, Field

from broker_reports_gate1.canonical_artifact import validate_canonical_artifact
from broker_reports_gate1.gate2_model_clients import Gate2StructuredModelClientFactory
from broker_reports_gate1.gate2_model_contracts import Gate2StructuredModelClientConfig
from broker_reports_gate1.gate2_model_requests import (
    ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
)
from broker_reports_gate1.ordinary_trade_mapping_prompt import (
    OrdinaryTradeMappingPromptConfig,
    OrdinaryTradeMappingPromptResolverFactory,
    OrdinaryTradeMappingPromptUserContext,
)
from broker_reports_gate1.ordinary_trade_semantic_mapping import (
    MAPPING_RESPONSE_SCHEMA_VERSION,
    OrdinaryTradeSemanticMappingFactory,
)


PROVIDER_PROFILE_ID = "google_gemini"
MODEL_ID = "models/gemini-3.5-flash"
SAFE_RECEIPT_SCHEMA_VERSION = "goal391_native_mapping_lab_pipe_receipt_v1"
_FORBIDDEN_CHAT_KEYS = frozenset({"chat_id", "parent_id", "message_id"})
_FORBIDDEN_LAB_BODY_KEYS = frozenset(
    {
        "canonical",
        "cases",
        "expected_assessment",
        "frozen_mappings",
        "goal391_lab",
        "prompt",
        "prompt_id",
        "prompt_hash",
        "prompt_version",
    }
)


class Goal391MappingLabPipeError(RuntimeError):
    """Value-free terminal code for this adapter boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Pipe:
    class Valves(BaseModel):
        # The lab is never a general-user model.  OpenWebUI remains the access
        # owner; this valve narrows it further to the designated ordinary user.
        ordinary_test_user_id: str = Field(default="")
        cases_required_total: int = Field(default=2, ge=1, le=2)
        model_id: str = Field(default=MODEL_ID)
        provider_profile_id: str = Field(default=PROVIDER_PROFILE_ID)
        prompt_db_path: str = Field(default="/app/backend/data/webui.db")
        prompt_id: str = Field(default="")
        prompt_version: str = Field(default="")
        prompt_hash: str = Field(default="")

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.last_safe_receipt: dict[str, Any] | None = None

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: Any = None,
        __request__: Any = None,
        __task__: Any = None,
        **kwargs: Any,
    ) -> str:
        """Run through the normal selected-model Pipe invocation."""

        self.last_safe_receipt = None
        try:
            if str(__task__ or "").strip():
                raise Goal391MappingLabPipeError("goal391_lab_auxiliary_task_forbidden")
            user_id = self._ordinary_user_id(__user__)
            self._require_request(__request__)
            # A normal OpenWebUI chat body is accepted and deliberately ignored.
            # It never selects scope or enters the provider prompt.  Only a
            # caller trying to smuggle laboratory control data is rejected.
            self._require_normal_body(body)
            loader = kwargs.get("__goal391_lab_case_loader__")
            if loader is None:
                raise Goal391MappingLabPipeError("goal391_lab_case_loader_unavailable")
            prompt = self._resolve_prompt(__user__)
            cases = await self._load_cases(loader=loader, user_id=user_id)
            prepared = self._preflight(cases=cases)
            receipt = await self._execute(
                cases=prepared,
                prompt=prompt,
                request=__request__,
                user=__user__,
            )
        except Goal391MappingLabPipeError as exc:
            receipt = self._blocked_receipt(exc.code)
        except Exception as exc:  # Never return provider/source/Python details.
            receipt = self._blocked_receipt(self._safe_error_code(exc))
        self.last_safe_receipt = receipt
        return json.dumps(receipt, ensure_ascii=False, sort_keys=True)

    def _ordinary_user_id(self, user: Any) -> str:
        user_id = str(
            user.get("id") if isinstance(user, Mapping) else getattr(user, "id", "")
        ).strip()
        role = str(
            user.get("role") if isinstance(user, Mapping) else getattr(user, "role", "")
        ).strip()
        configured = str(self.valves.ordinary_test_user_id or "").strip()
        if not user_id or role != "user" or not configured or user_id != configured:
            raise Goal391MappingLabPipeError("goal391_lab_access_denied")
        return user_id

    @staticmethod
    def _require_request(request: Any) -> None:
        if request is None:
            raise Goal391MappingLabPipeError("goal391_lab_request_required")

    @staticmethod
    def _require_normal_body(body: Any) -> None:
        if not isinstance(body, Mapping):
            raise Goal391MappingLabPipeError("goal391_lab_body_invalid")
        if _FORBIDDEN_LAB_BODY_KEYS.intersection(body):
            raise Goal391MappingLabPipeError("goal391_lab_body_input_forbidden")

    def _resolve_prompt(self, user: Any):
        prompt_id = str(self.valves.prompt_id or "").strip()
        prompt_version = str(self.valves.prompt_version or "").strip()
        prompt_hash = str(self.valves.prompt_hash or "").strip()
        if not prompt_id or not prompt_version or not prompt_hash:
            raise Goal391MappingLabPipeError("goal391_lab_prompt_pin_required")
        user_id = self._ordinary_user_id(user)
        # The Pipe never opens Prompt tables.  The existing resolver owns
        # Prompt history, contract validation, grants and release pin checks.
        return OrdinaryTradeMappingPromptResolverFactory(
            OrdinaryTradeMappingPromptConfig(
                source="openwebui_sqlite",
                db_path=Path(str(self.valves.prompt_db_path)),
                prompt_id=prompt_id,
                command=None,
                release_prompt_version=prompt_version,
                release_prompt_hash=prompt_hash,
            )
        ).create().resolve(
            OrdinaryTradeMappingPromptUserContext(user_id=user_id, user_role="user")
        )

    async def _load_cases(self, *, loader: Any, user_id: str) -> list[dict[str, Any]]:
        value = loader(user_id=user_id)
        if inspect.isawaitable(value):
            value = await value
        if not isinstance(value, list):
            raise Goal391MappingLabPipeError("goal391_lab_cases_invalid")
        return value

    def _preflight(self, *, cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(cases) != self.valves.cases_required_total:
            raise Goal391MappingLabPipeError("goal391_lab_case_count_invalid")
        semantic = OrdinaryTradeSemanticMappingFactory.create()
        prepared: list[dict[str, Any]] = []
        for case in cases:
            required = {
                "case_id",
                "canonical",
                "canonical_binding",
                "confirmed_understandings",
                "target_table_node_ids",
                "frozen_mappings",
                "user_scope_sha256",
                "expected_assessment",
            }
            if not isinstance(case, Mapping) or set(case) != required:
                raise Goal391MappingLabPipeError("goal391_lab_case_invalid")
            canonical = case["canonical"]
            if not isinstance(canonical, Mapping) or validate_canonical_artifact(canonical).get("passed") is not True:
                raise Goal391MappingLabPipeError("goal391_lab_canonical_invalid")
            assessment = case["expected_assessment"]
            if not self._valid_assessment(assessment):
                raise Goal391MappingLabPipeError("goal391_lab_assessment_invalid")
            package = semantic.build_mapping_package(
                canonical=canonical,
                confirmed_understandings=case["confirmed_understandings"],
                target_table_node_ids=case["target_table_node_ids"],
            )
            required_exclusions = [
                decision["table_node_id"]
                for decision in assessment["required_table_decisions"]
                if decision["disposition"] == "NO_NAMED_CONSUMER"
            ]
            envelopes = (
                semantic.build_classification_evidence_envelopes(
                    canonical=canonical, target_table_node_ids=required_exclusions
                )
                if required_exclusions
                else {}
            )
            prepared.append(
                {
                    "case": dict(case),
                    "package": package,
                    "owner_envelopes": envelopes,
                }
            )
        if len({str(item["case"]["case_id"]) for item in prepared}) != len(prepared):
            raise Goal391MappingLabPipeError("goal391_lab_case_duplicate")
        return prepared

    @staticmethod
    def _valid_assessment(value: Any) -> bool:
        required = {
            "expected_status",
            "required_table_decisions",
            "unresolved_table_node_ids",
            "forbidden_qualified_mapping_table_node_ids",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            return False
        if not isinstance(value["expected_status"], str) or not isinstance(value["required_table_decisions"], list):
            return False
        for decision in value["required_table_decisions"]:
            if not isinstance(decision, Mapping) or set(decision) - {
                "table_node_id", "disposition", "no_consumer_kind"
            }:
                return False
            if not isinstance(decision.get("table_node_id"), str) or not isinstance(decision.get("disposition"), str):
                return False
            if decision["disposition"] == "NO_NAMED_CONSUMER" and decision.get("no_consumer_kind") not in {
                "INSTRUCTIONAL_REFERENCE", "OTHER_NO_NAMED_CONSUMER"
            }:
                return False
        return all(isinstance(value[key], list) for key in required - {"expected_status", "required_table_decisions"})

    async def _execute(self, *, cases, prompt, request: Any, user: Any) -> dict[str, Any]:
        submissions = {"count": 0}

        async def completion(*, form_data: Mapping[str, Any], **_kwargs: Any):
            self._require_stateless_form(form_data)
            submissions["count"] += 1
            # This is the native OpenWebUI provider route.  There is no SDK,
            # key read, alternative client or persisted chat identity.
            from open_webui.main import generate_chat_completion

            return await generate_chat_completion(request, dict(form_data), user=user)

        client = Gate2StructuredModelClientFactory(
            config=Gate2StructuredModelClientConfig(
                request_profile=ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
                provider_profile_id=str(self.valves.provider_profile_id),
                capability_probe=False,
                economy_budget_enforcement=False,
            ),
            user=user,
            request=request,
            completion_resolver=lambda _user_id: (completion, user),
        ).create()
        semantic = OrdinaryTradeSemanticMappingFactory.create()
        records: list[dict[str, Any]] = []
        terminal_error = None
        for item in cases:
            try:
                response = await client.extract(
                    prompt=prompt,
                    package=item["package"],
                    model_id=str(self.valves.model_id),
                    response_format=semantic.mapping_response_format(),
                )
                if semantic.mapping_response_contract_failure_code(response) is not None:
                    raise Goal391MappingLabPipeError("goal391_lab_response_contract_invalid")
                outcome = semantic.validate_mapping_response(
                    response=response,
                    canonical=item["case"]["canonical"],
                    canonical_binding=item["case"]["canonical_binding"],
                    model_id=str(self.valves.model_id),
                    provider_profile_id=str(self.valves.provider_profile_id),
                    execution_metadata=response.execution_metadata,
                    confirmed_understandings=item["case"]["confirmed_understandings"],
                    user_scope_sha256=item["case"]["user_scope_sha256"],
                    target_table_node_ids=item["case"]["target_table_node_ids"],
                    frozen_mappings=item["case"]["frozen_mappings"],
                )
                records.append(self._safe_record(item=item, outcome=outcome))
            except Exception as exc:
                terminal_error = self._safe_error_code(exc)
                break
        lifecycle = client.qualification_lifecycle_snapshot()
        expected = len(cases)
        passed = (
            terminal_error is None
            and submissions["count"] == expected
            and lifecycle == {
                "local_invocations_total": expected,
                "provider_submissions_total": expected,
                "provider_responses_total": expected,
            }
            and all(record["outcome"] == "PASS" for record in records)
        )
        return {
            "schema_version": SAFE_RECEIPT_SCHEMA_VERSION,
            "status": "PASSED" if passed else "FAILED",
            "corpus": {
                "cases_total": expected,
                "provider_calls_started_total": submissions["count"],
                "provider_calls_returned_total": lifecycle["provider_responses_total"],
                "records": records,
            },
            "constraints": {
                "retries": 0,
                "best_of_n": False,
                "manual_output_repair": False,
                "chat_persistence": "forbidden",
                "artifact_store_mutation": False,
                "canonical_mutation": False,
                "right_bank_mutation": False,
                "xml_mutation": False,
            },
            "terminal_error": terminal_error,
        }

    @staticmethod
    def _require_stateless_form(form_data: Mapping[str, Any]) -> None:
        if not isinstance(form_data, Mapping):
            raise Goal391MappingLabPipeError("goal391_lab_form_invalid")
        if any(key in form_data for key in _FORBIDDEN_CHAT_KEYS):
            raise Goal391MappingLabPipeError("goal391_lab_chat_identifier_forbidden")
        metadata = form_data.get("metadata")
        if isinstance(metadata, Mapping) and any(key in metadata for key in _FORBIDDEN_CHAT_KEYS):
            raise Goal391MappingLabPipeError("goal391_lab_chat_identifier_forbidden")

    def _safe_record(self, *, item: Mapping[str, Any], outcome: Mapping[str, Any]) -> dict[str, Any]:
        case = item["case"]
        assessment = case["expected_assessment"]
        result = outcome
        resolutions = {
            value.get("table_node_id"): {
                key: value.get(key)
                for key in ("table_node_id", "disposition", "no_consumer_kind")
                if key in value
            }
            for value in result.get("table_resolutions") or []
            if isinstance(value, Mapping) and isinstance(value.get("table_node_id"), str)
        }
        required = {
            decision["table_node_id"]: dict(decision)
            for decision in assessment["required_table_decisions"]
        }
        expected = {
            node_id: {
                key: value for key, value in decision.items()
                if key in {"table_node_id", "disposition", "no_consumer_kind"}
            }
            for node_id, decision in required.items()
        }
        qualified = sorted(
            str(value["case_scope"]["table_node_id"])
            for value in result.get("qualification_receipts") or []
            if isinstance(value, Mapping)
            and isinstance(value.get("case_scope"), Mapping)
            and isinstance(value["case_scope"].get("table_node_id"), str)
        )
        expected_envelopes = item["owner_envelopes"]
        actual_envelopes = {
            node_id: value.get("classification_evidence")
            for node_id, value in (
                (value.get("table_node_id"), value)
                for value in result.get("table_resolutions") or []
                if isinstance(value, Mapping)
            )
            if node_id in expected_envelopes
        }
        matches = (
            result.get("status") == assessment["expected_status"]
            and all(resolutions.get(node_id) == decision for node_id, decision in expected.items())
            and all(actual_envelopes.get(node_id) == envelope for node_id, envelope in expected_envelopes.items())
            and not set(qualified).intersection(assessment["forbidden_qualified_mapping_table_node_ids"])
        )
        return {
            "case_sha256": self._sha256(case["case_id"]),
            "canonical_root_sha256": str(case["canonical_binding"].get("canonical_root_sha256") or ""),
            "expected_assessment_sha256": self._sha256(assessment),
            "actual_table_decisions_sha256": self._sha256(resolutions),
            "owner_classification_envelope_sha256": self._sha256(expected_envelopes),
            "actual_owner_classification_envelope_sha256": self._sha256(actual_envelopes),
            "owner_classification_envelope_total": sum(len(value) for value in expected_envelopes.values()),
            "actual_classification_envelope_total": sum(
                len(value) for value in actual_envelopes.values() if isinstance(value, list)
            ),
            "qualified_mapping_total": len(qualified),
            "actual_status": str(result.get("status") or ""),
            "outcome": "PASS" if matches else "FAIL",
        }

    def _blocked_receipt(self, code: str) -> dict[str, Any]:
        return {
            "schema_version": SAFE_RECEIPT_SCHEMA_VERSION,
            "status": "BLOCKED",
            "corpus": {
                "cases_total": 0,
                "provider_calls_started_total": 0,
                "provider_calls_returned_total": 0,
                "records": [],
            },
            "constraints": {
                "retries": 0,
                "best_of_n": False,
                "manual_output_repair": False,
                "chat_persistence": "forbidden",
                "artifact_store_mutation": False,
                "canonical_mutation": False,
                "right_bank_mutation": False,
                "xml_mutation": False,
            },
            "terminal_error": code,
        }

    @staticmethod
    def _safe_error_code(exc: Exception) -> str:
        if isinstance(exc, Goal391MappingLabPipeError):
            return exc.code
        # Existing owners may carry source, provider or Prompt context in their
        # exception classes.  The chat-visible laboratory receipt deliberately
        # does not distinguish those failures.
        return "goal391_lab_internal_failure"

    @staticmethod
    def _sha256(value: Any) -> str:
        return hashlib.sha256(
            json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()


__all__ = ["Pipe"]
