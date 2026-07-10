"""
title: Broker Reports Gate 2 Source Fact Extraction
author: Alpha Soft
version: 0.1.0
required_open_webui_version: 0.9.6
requirements: pydantic
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    Gate2ManagedPromptResolverFactory,
    Gate2PromptConfig,
    Gate2PromptUserContext,
    Gate2SourceFactRuntimeConfig,
    Gate2SourceFactRuntimeError,
    Gate2SourceFactRuntimeFactory,
    Gate2StructuredModelResult,
)
from broker_reports_gate1.gate2_source_fact_contracts import Gate2PromptError


class OpenWebUIGate2StructuredModelClient:
    def __init__(self, *, pipe: "Pipe", user: Any, request: Any) -> None:
        self.pipe = pipe
        self.user = user
        self.request = request

    async def extract(self, *, prompt, package, model_id, response_format):
        if self.request is None:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_unavailable",
                "OpenWebUI request object is required",
            )
        user_id = self.pipe._user_id(self.user)
        if not user_id:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_unavailable",
                "Authenticated OpenWebUI user is required",
            )
        marker = "{{source_fact_package_json}}"
        if marker not in prompt.content:
            raise Gate2PromptError(
                "gate2_prompt_contract_mismatch",
                "Managed Prompt input marker is missing",
            )
        package_json = json.dumps(package, ensure_ascii=False, sort_keys=True)
        system_content = prompt.content.replace(marker, package_json)
        user_content = json.dumps(
            {
                "task": "extract_broker_reports_source_facts_v0",
                "package_ref": package.get("package_artifact_ref"),
                "instruction": (
                    "Return exactly one broker_reports_source_facts_v0 JSON object. "
                    "Use only the package embedded in the managed Prompt and its allowed refs."
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        form_data = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "response_format": response_format,
            "metadata": {
                "broker_reports_gate2": {
                    "source_fact_extraction": True,
                    "structured_output_mode": "openwebui_response_format_json_schema",
                    "prompt_ref": prompt.prompt_ref,
                    "prompt_hash": prompt.hash,
                    "output_schema_id": prompt.output_schema_id,
                    "output_schema_version": prompt.output_schema_version,
                    "output_schema_hash": package.get("output_schema", {}).get(
                        "output_schema_hash"
                    ),
                    "package_ref": package.get("package_artifact_ref"),
                }
            },
        }
        try:
            completion_fn, user_model = self.pipe._openwebui_completion_dependencies(user_id)
            if inspect.isawaitable(user_model):
                user_model = await user_model
            if user_model is None:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_unavailable",
                    "OpenWebUI user model is unavailable",
                )
            try:
                response = completion_fn(
                    request=self.request,
                    form_data=form_data,
                    user=user_model,
                    bypass_filter=True,
                    bypass_system_prompt=True,
                )
            except TypeError:
                try:
                    response = completion_fn(
                        request=self.request,
                        form_data=form_data,
                        user=user_model,
                    )
                except TypeError:
                    response = completion_fn(self.request, form_data, user_model)
            if inspect.isawaitable(response):
                response = await response
        except Gate2SourceFactRuntimeError:
            raise
        except Exception as exc:
            raise Gate2SourceFactRuntimeError(
                "gate2_model_call_failed",
                exc.__class__.__name__,
            ) from exc
        return Gate2StructuredModelResult(content=self.pipe._extract_completion_content(response))


class Pipe:
    class Valves(BaseModel):
        priority: int = Field(default=0)
        artifact_store_path: str = Field(
            default="/app/backend/data/broker_reports_gate1/artifacts.sqlite3"
        )
        artifact_payload_root: str = Field(
            default="/app/backend/data/broker_reports_gate1/payloads"
        )
        prompt_db_path: str = Field(default="/app/backend/data/webui.db")
        prompt_id: str = Field(default="broker_reports_gate2_source_fact_prompt_v0")
        prompt_command: str = Field(default="broker_gate2_source_facts_v0")
        model_id: str = Field(default="")
        default_wave: str = Field(default="primary")
        table_max_rows: int = Field(default=40)
        text_max_chars: int = Field(default=6000)
        max_estimated_input_tokens: int = Field(default=12000)

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.last_safe_summary: dict[str, Any] | None = None
        self.last_runtime_result = None

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: Any = None,
        __request__: Any = None,
        __metadata__: dict[str, Any] | None = None,
        __event_emitter__=None,
        **_: Any,
    ) -> str:
        metadata = __metadata__ if isinstance(__metadata__, dict) else {}
        config = self._runtime_config(body, metadata)
        dcp_ref = str(config.get("domain_context_packet_ref") or "").strip()
        user_id = self._user_id(__user__)
        if not dcp_ref or not user_id:
            await self._emit(
                __event_emitter__,
                "Gate 2 blocked: authenticated user and DCP ref are required.",
                done=True,
            )
            return "Gate 2 не запущен: нужен авторизованный пользователь и безопасный DCP ref."

        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=Path(self.valves.artifact_store_path),
                payload_root=Path(self.valves.artifact_payload_root),
            )
        ).create()
        dcp_record = store.get_record_unchecked(dcp_ref)
        if dcp_record is None or dcp_record.artifact_type != "domain_context_packet_v0":
            await self._emit(__event_emitter__, "Gate 2 blocked: DCP ref is unavailable.", done=True)
            return "Gate 2 не запущен: безопасный DCP ref не найден."
        context = ArtifactAccessContext(
            user_id=user_id,
            normalization_run_id=dcp_record.normalization_run_id,
            case_id=dcp_record.case_id,
            chat_id=dcp_record.chat_id,
            workspace_model_id=dcp_record.workspace_model_id,
            allow_private=True,
            require_source_available=True,
        )
        model_id = str(config.get("model_id") or self.valves.model_id or "").strip()
        wave = str(config.get("wave") or self.valves.default_wave or "primary")
        run_mode = str(config.get("run_mode") or "customer")
        try:
            prompt = Gate2ManagedPromptResolverFactory(
                Gate2PromptConfig(
                    source="openwebui_sqlite",
                    db_path=Path(str(config.get("prompt_db_path") or self.valves.prompt_db_path)),
                    prompt_id=str(config.get("prompt_id") or self.valves.prompt_id) or None,
                    command=str(config.get("prompt_command") or self.valves.prompt_command) or None,
                )
            ).create()
            runtime = Gate2SourceFactRuntimeFactory(
                store=store,
                prompt_resolver=prompt,
                model_client=OpenWebUIGate2StructuredModelClient(
                    pipe=self,
                    user=__user__,
                    request=__request__,
                ),
                config=Gate2SourceFactRuntimeConfig(
                    model_id=model_id,
                    wave=wave,
                    run_mode=run_mode,
                    table_max_rows=int(config.get("table_max_rows") or self.valves.table_max_rows),
                    text_max_chars=int(config.get("text_max_chars") or self.valves.text_max_chars),
                    max_estimated_input_tokens=int(
                        config.get("max_estimated_input_tokens")
                        or self.valves.max_estimated_input_tokens
                    ),
                    document_batch_start=int(
                        config.get("document_batch_start") or 0
                    ),
                    document_batch_limit=(
                        int(config["document_batch_limit"])
                        if config.get("document_batch_limit") is not None
                        else None
                    ),
                ),
            ).create()
            await self._emit(__event_emitter__, "Gate 2 structured extraction started.", done=False)
            result = await runtime.run(
                domain_context_packet_ref=dcp_ref,
                context=context,
                prompt_user_context=Gate2PromptUserContext(
                    user_id=user_id,
                    user_role=self._user_role(__user__),
                    user_groups=tuple(self._user_groups(__user__)),
                ),
            )
            self.last_runtime_result = result
            self.last_safe_summary = result.safe_summary
            await self._emit(
                __event_emitter__,
                "Gate 2 structured extraction reached a terminal state.",
                done=True,
            )
            return result.compact_russian_summary
        except (Gate2SourceFactRuntimeError, Gate2PromptError, ArtifactStoreError) as exc:
            await self._emit(
                __event_emitter__,
                f"Gate 2 blocked: {getattr(exc, 'code', 'gate2_failed_safe')}",
                done=True,
            )
            return (
                "Gate 2 завершён безопасной блокировкой. "
                "Подтверждённые исходные факты не созданы. "
                "Расчёт налогов, декларация и XLS/XLSX не выполнялись."
            )

    def _runtime_config(
        self,
        body: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        body_config = body.get("broker_reports_gate2")
        metadata_config = metadata.get("broker_reports_gate2")
        result: dict[str, Any] = {}
        if isinstance(metadata_config, dict):
            result.update(metadata_config)
        if isinstance(body_config, dict):
            result.update(body_config)
        return result

    def _user_id(self, user: Any) -> str:
        if isinstance(user, dict):
            return str(user.get("id") or user.get("user_id") or "")
        return str(getattr(user, "id", "") or "")

    def _user_role(self, user: Any) -> str:
        if isinstance(user, dict):
            return str(user.get("role") or "user")
        return str(getattr(user, "role", "user") or "user")

    def _user_groups(self, user: Any) -> list[str]:
        if isinstance(user, dict):
            groups = user.get("groups") or []
        else:
            groups = getattr(user, "groups", []) or []
        result = []
        for group in groups if isinstance(groups, list) else []:
            if isinstance(group, dict):
                value = group.get("id") or group.get("name")
            else:
                value = group
            if value:
                result.append(str(value))
        return result

    def _openwebui_completion_dependencies(self, user_id: str):
        try:
            from open_webui.utils.chat import generate_chat_completion as completion_fn
        except Exception:
            from open_webui.main import generate_chat_completions as completion_fn
        from open_webui.models.users import Users

        return completion_fn, Users.get_user_by_id(user_id)

    def _extract_completion_content(self, response: Any) -> Any:
        if isinstance(response, dict):
            return self._completion_dict_content(response)
        body = getattr(response, "body", None)
        if isinstance(body, bytes):
            try:
                return self._completion_dict_content(json.loads(body.decode("utf-8")))
            except (UnicodeDecodeError, ValueError) as exc:
                raise Gate2SourceFactRuntimeError(
                    "gate2_model_invalid_response",
                    "Completion response body is not JSON",
                ) from exc
        if isinstance(response, str):
            return response
        raise Gate2SourceFactRuntimeError(
            "gate2_model_invalid_response",
            "Unsupported completion response shape",
        )

    def _completion_dict_content(self, payload: dict[str, Any]) -> Any:
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            message = first.get("message") if isinstance(first.get("message"), dict) else {}
            content = message.get("content")
            if isinstance(content, (str, dict)):
                return content
            if isinstance(first.get("text"), (str, dict)):
                return first["text"]
        if isinstance(payload.get("content"), (str, dict)):
            return payload["content"]
        if isinstance(payload.get("response"), (str, dict)):
            return payload["response"]
        if "detail" in payload or "error" in payload:
            raise Gate2SourceFactRuntimeError(
                self._provider_error_code(payload),
                "Provider returned a typed error object",
                raw_output=payload,
            )
        raise Gate2SourceFactRuntimeError(
            "gate2_model_invalid_response",
            "Completion response has no structured content",
        )

    def _provider_error_code(self, payload: dict[str, Any]) -> str:
        rendered = json.dumps(payload, ensure_ascii=True, sort_keys=True).lower()
        if "oneof" in rendered or "one_of" in rendered:
            return "gate2_model_schema_oneof_unsupported"
        if "required" in rendered and "properties" in rendered:
            return "gate2_model_schema_required_properties_invalid"
        if "additionalproperties" in rendered or "additional_properties" in rendered:
            return "gate2_model_schema_additional_properties_invalid"
        if "must have a 'type' key" in rendered or 'must have a \\"type\\" key' in rendered:
            return "gate2_model_schema_type_key_missing"
        if "nullable" in rendered or "invalid nullable" in rendered:
            return "gate2_model_schema_nullable_type_invalid"
        if "response_format" in rendered or "json_schema" in rendered or "schema" in rendered:
            return "gate2_model_schema_response_format_rejected"
        if "context_length" in rendered or "too many tokens" in rendered or "maximum context" in rendered:
            return "gate2_model_context_budget_exceeded"
        if "model" in rendered and ("not found" in rendered or "unavailable" in rendered):
            return "gate2_model_unavailable"
        if "unauthorized" in rendered or "authentication" in rendered or "api key" in rendered:
            return "gate2_model_provider_auth_failed"
        return "gate2_model_provider_error"

    async def _emit(self, emitter, description: str, *, done: bool) -> None:
        if emitter is None:
            return
        payload = {
            "type": "status",
            "data": {"description": description, "done": done},
        }
        result = emitter(payload)
        if inspect.isawaitable(result):
            await result
