"""
title: Broker Reports Gate 2 Domain Source Fact Extraction
author: Alpha Soft
version: 0.5.0
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
    Gate2DomainPromptConfig,
    Gate2DomainPromptResolverFactory,
    Gate2DomainSourceFactRuntimeConfig,
    Gate2DomainSourceFactRuntimeFactory,
    Gate2NativeProviderTransportConfig,
    Gate2PromptUserContext,
    Gate2SourceFactRuntimeError,
    Gate2StructuredModelClientConfig,
    Gate2StructuredModelClientFactory,
    DOMAIN_REQUEST_PROFILE,
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
        model_id: str = Field(default="")
        provider_profile_id: str = Field(default="openai_gpt")
        anthropic_api_key: str = Field(
            default="",
            repr=False,
            json_schema_extra={"input": {"type": "password"}},
        )
        anthropic_api_version: str = Field(default="2023-06-01")
        native_provider_timeout_seconds: int = Field(default=180)
        default_wave: str = Field(default="primary")
        default_document_batch_limit: int = Field(default=1)
        default_source_unit_limit: int = Field(default=1)
        segmentation_enabled: bool = Field(default=True)
        prefer_table_projections: bool = Field(default=False)
        candidate_binding_enabled: bool = Field(default=False)
        default_source_segment_limit: int = Field(default=1)
        table_segment_max_refs: int = Field(default=8)
        text_segment_max_refs: int = Field(default=12)
        max_repair_attempts: int = Field(default=1)
        table_max_rows: int = Field(default=40)
        text_max_chars: int = Field(default=6000)

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
                "Gate 2 domain extraction blocked: user and DCP ref are required.",
                done=True,
            )
            return "Gate 2 не запущен: нужен авторизованный пользователь и безопасный DCP ref."

        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=Path(
                    str(config.get("artifact_store_path") or self.valves.artifact_store_path)
                ),
                payload_root=Path(
                    str(config.get("artifact_payload_root") or self.valves.artifact_payload_root)
                ),
            )
        ).create()
        dcp_record = store.get_record_unchecked(dcp_ref)
        if dcp_record is None or dcp_record.artifact_type != "domain_context_packet_v0":
            await self._emit(
                __event_emitter__,
                "Gate 2 domain extraction blocked: DCP ref is unavailable.",
                done=True,
            )
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
        try:
            run_mode = str(config.get("run_mode") or "customer")
            provider_capability_probe = self._config_bool(
                config.get("provider_capability_probe"), default=False
            )
            if provider_capability_probe and run_mode != "provider_qualification":
                raise ValueError("gate2_provider_capability_probe_mode_invalid")
            provider_profile_id = str(
                config.get("provider_profile_id") or self.valves.provider_profile_id
            )
            prompt_ids = config.get("prompt_ids")
            prompt_commands = config.get("prompt_commands")
            prompt_resolver = Gate2DomainPromptResolverFactory(
                Gate2DomainPromptConfig(
                    source="openwebui_sqlite",
                    db_path=Path(
                        str(config.get("prompt_db_path") or self.valves.prompt_db_path)
                    ),
                    prompt_ids=(prompt_ids if isinstance(prompt_ids, dict) else {}),
                    prompt_commands=(
                        prompt_commands if isinstance(prompt_commands, dict) else {}
                    ),
                )
            ).create()
            domain_allowlist = config.get("domain_allowlist")
            runtime = Gate2DomainSourceFactRuntimeFactory(
                store=store,
                prompt_resolver=prompt_resolver,
                model_client=Gate2StructuredModelClientFactory(
                    config=Gate2StructuredModelClientConfig(
                        request_profile=DOMAIN_REQUEST_PROFILE,
                        provider_profile_id=provider_profile_id,
                        capability_probe=provider_capability_probe,
                    ),
                    user=__user__,
                    request=__request__,
                    native_transport_config=Gate2NativeProviderTransportConfig(
                        anthropic_api_key=self.valves.anthropic_api_key,
                        anthropic_api_version=self.valves.anthropic_api_version,
                        timeout_seconds=self.valves.native_provider_timeout_seconds,
                    ),
                ).create(),
                config=Gate2DomainSourceFactRuntimeConfig(
                    model_id=model_id,
                    provider_profile_id=provider_profile_id,
                    provider_capability_probe=provider_capability_probe,
                    wave=str(config.get("wave") or self.valves.default_wave),
                    run_mode=run_mode,
                    document_batch_start=int(config.get("document_batch_start") or 0),
                    document_batch_limit=(
                        int(config["document_batch_limit"])
                        if config.get("document_batch_limit") is not None
                        else self.valves.default_document_batch_limit
                    ),
                    source_unit_limit=(
                        int(config["source_unit_limit"])
                        if config.get("source_unit_limit") is not None
                        else self.valves.default_source_unit_limit
                    ),
                    source_unit_start=int(config.get("source_unit_start") or 0),
                    segmentation_enabled=self._config_bool(
                        config.get("segmentation_enabled"),
                        default=self.valves.segmentation_enabled,
                    ),
                    prefer_table_projections=self._config_bool(
                        config.get("prefer_table_projections"),
                        default=self.valves.prefer_table_projections,
                    ),
                    candidate_binding_enabled=self._config_bool(
                        config.get("candidate_binding_enabled"),
                        default=self.valves.candidate_binding_enabled,
                    ),
                    source_segment_start=int(
                        config.get("source_segment_start") or 0
                    ),
                    source_segment_limit=(
                        int(config["source_segment_limit"])
                        if config.get("source_segment_limit") is not None
                        else self.valves.default_source_segment_limit
                    ),
                    table_segment_max_refs=int(
                        config.get("table_segment_max_refs")
                        or self.valves.table_segment_max_refs
                    ),
                    text_segment_max_refs=int(
                        config.get("text_segment_max_refs")
                        or self.valves.text_segment_max_refs
                    ),
                    domain_allowlist=tuple(
                        str(item)
                        for item in domain_allowlist or []
                        if item is not None and str(item)
                    )
                    if isinstance(domain_allowlist, list)
                    else (),
                    max_repair_attempts=int(
                        config.get("max_repair_attempts")
                        if config.get("max_repair_attempts") is not None
                        else self.valves.max_repair_attempts
                    ),
                    table_max_rows=int(
                        config.get("table_max_rows") or self.valves.table_max_rows
                    ),
                    text_max_chars=int(
                        config.get("text_max_chars") or self.valves.text_max_chars
                    ),
                ),
            ).create()
            await self._emit(
                __event_emitter__,
                "Gate 2 domain routing and structured extraction started.",
                done=False,
            )
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
                "Gate 2 domain extraction reached a terminal state.",
                done=True,
            )
            return result.compact_russian_summary
        except (Gate2SourceFactRuntimeError, Gate2PromptError, ArtifactStoreError, ValueError) as exc:
            error_code = str(
                getattr(exc, "code", None) or str(exc) or "gate2_domain_failed_safe"
            )
            await self._emit(
                __event_emitter__,
                f"Gate 2 domain extraction blocked: {error_code}",
                done=True,
            )
            safe_message = (
                "Gate 2 завершён безопасной блокировкой. "
                "Подтверждённые доменные исходные факты не созданы. "
                "Расчёт налогов, декларация и XLS/XLSX не выполнялись."
            )
            if run_mode == "provider_qualification":
                return f"{safe_message} Blocker code: {error_code}."
            return safe_message

    def _runtime_config(self, body: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for source in (
            metadata.get("broker_reports_gate2_domain"),
            body.get("broker_reports_gate2_domain"),
        ):
            if isinstance(source, dict):
                result.update(source)
        return result

    def _user_id(self, user: Any) -> str:
        if isinstance(user, dict):
            return str(user.get("id") or user.get("user_id") or "")
        return str(getattr(user, "id", "") or "")

    def _config_bool(self, value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        raise ValueError("gate2_segmentation_enabled_invalid")

    def _user_role(self, user: Any) -> str:
        if isinstance(user, dict):
            return str(user.get("role") or "user")
        return str(getattr(user, "role", "user") or "user")

    def _user_groups(self, user: Any) -> list[str]:
        groups = user.get("groups") or [] if isinstance(user, dict) else getattr(user, "groups", []) or []
        result = []
        for group in groups if isinstance(groups, list) else []:
            value = group.get("id") or group.get("name") if isinstance(group, dict) else group
            if value:
                result.append(str(value))
        return result

    async def _emit(self, emitter, description: str, *, done: bool) -> None:
        if emitter is None:
            return
        result = emitter(
            {"type": "status", "data": {"description": description, "done": done}}
        )
        if inspect.isawaitable(result):
            await result
