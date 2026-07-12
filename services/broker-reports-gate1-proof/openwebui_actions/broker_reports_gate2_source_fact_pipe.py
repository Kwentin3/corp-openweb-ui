"""
title: Broker Reports Gate 2 Source Fact Extraction
author: Alpha Soft
version: 0.3.1
required_open_webui_version: 0.9.6
requirements: pydantic
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    Gate2ManagedPromptResolverFactory,
    Gate2NativeProviderTransportConfig,
    Gate2PromptConfig,
    Gate2PromptUserContext,
    Gate2SourceFactRuntimeConfig,
    Gate2SourceFactRuntimeError,
    Gate2SourceFactRuntimeFactory,
    Gate2StructuredModelClientConfig,
    Gate2StructuredModelClientFactory,
    SOURCE_REQUEST_PROFILE,
)
from broker_reports_gate1.gate2_source_fact_contracts import Gate2PromptError


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
        provider_profile_id: str = Field(default="openai_gpt")
        anthropic_api_version: str = Field(default="2023-06-01")
        native_provider_timeout_seconds: int = Field(default=180)
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
                model_client=Gate2StructuredModelClientFactory(
                    config=Gate2StructuredModelClientConfig(
                        request_profile=SOURCE_REQUEST_PROFILE,
                        provider_profile_id=str(
                            config.get("provider_profile_id")
                            or self.valves.provider_profile_id
                        ),
                    ),
                    user=__user__,
                    request=__request__,
                    native_transport_config=Gate2NativeProviderTransportConfig(
                        anthropic_api_version=self.valves.anthropic_api_version,
                        timeout_seconds=self.valves.native_provider_timeout_seconds,
                    ),
                ).create(),
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
