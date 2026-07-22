"""
title: Broker Reports Gate 2 Source Fact Extraction
author: Alpha Soft
version: 0.15.0-positional-coverage-v1
required_open_webui_version: 0.9.6
requirements: pydantic
"""

from __future__ import annotations

import asyncio
import inspect
import re
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
    WorkloadAccessContext,
    WorkloadAuthorityConfig,
    WorkloadAuthorityError,
    WorkloadAuthorityFactory,
    WorkloadCancelledError,
    WorkloadKind,
    WorkloadState,
    gate2_resolve_extraction_model_id,
    provider_budgets_from_json,
)
from broker_reports_gate1.gate2_source_fact_contracts import Gate2PromptError


_GATE1_WORKLOAD_SCOPE_MODEL_ID = "broker_reports_gate1_pipe"


class Pipe:
    class Valves(BaseModel):
        priority: int = Field(default=0)
        artifact_store_path: str = Field(
            default="/app/backend/data/broker_reports_gate1/artifacts.sqlite3"
        )
        artifact_payload_root: str = Field(
            default="/app/backend/data/broker_reports_gate1/payloads"
        )
        workload_store_path: str = Field(default="")
        workload_temp_root: str = Field(default="")
        workload_lease_seconds: float = Field(default=90.0, ge=5.0, le=600.0)
        workload_poll_interval_seconds: float = Field(
            default=0.2, ge=0.05, le=5.0
        )
        workload_provider_budgets_json: str = Field(
            default=(
                '{"google_gemini":1,"openai_gpt":2,"anthropic_claude":1,'
                '"deepseek":1,"zai_glm":1,"alibaba_qwen":1,'
                '"openwebui_completion":2}'
            )
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
        semantic_selection_enabled: bool = Field(default=True)

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.last_safe_summary: dict[str, Any] | None = None
        self.last_runtime_result = None
        self.last_workload_job_id: str | None = None
        self.last_workload_snapshot: dict[str, Any] | None = None

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
        wave = str(config.get("wave") or self.valves.default_wave or "primary")
        run_mode = str(config.get("run_mode") or "customer")
        workload_session = None
        try:
            authority = self._workload_authority()
            workload_access = WorkloadAccessContext.from_artifact_context(context)
            self._assert_gate1_workload_completed(
                authority=authority,
                context=context,
                dcp_record=dcp_record,
            )
            provider_profile_id = str(
                config.get("provider_profile_id") or self.valves.provider_profile_id
            )
            model_id = gate2_resolve_extraction_model_id(
                provider_profile_id,
                str(config.get("model_id") or self.valves.model_id or ""),
            )
            ticket = authority.submit(
                job_kind=WorkloadKind.GATE2_SOURCE,
                access=workload_access,
                safe_metadata={"provider_profile_id": provider_profile_id},
            )
            self.last_workload_job_id = ticket.job_id
            self.last_workload_snapshot = authority.snapshot(
                job_id=ticket.job_id,
                access=workload_access,
            )
            await self._emit_workload_snapshot(
                __event_emitter__, self.last_workload_snapshot, done=False
            )
            workload_session = await authority.wait_for_admission(
                job_id=ticket.job_id,
                access=workload_access,
                on_wait=lambda snapshot: self._on_workload_wait(
                    __event_emitter__, snapshot
                ),
            )
            self.last_workload_snapshot = workload_session.snapshot()
            await self._emit_workload_snapshot(
                __event_emitter__, self.last_workload_snapshot, done=False
            )
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
                        provider_profile_id=provider_profile_id,
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
                    workload_job_id=ticket.job_id,
                    wave=wave,
                    run_mode=run_mode,
                    table_max_rows=int(config.get("table_max_rows") or self.valves.table_max_rows),
                    text_max_chars=int(config.get("text_max_chars") or self.valves.text_max_chars),
                    max_estimated_input_tokens=int(
                        config.get("max_estimated_input_tokens")
                        or self.valves.max_estimated_input_tokens
                    ),
                    semantic_selection_enabled=bool(
                        config.get(
                            "semantic_selection_enabled",
                            self.valves.semantic_selection_enabled,
                        )
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
            with workload_session.keepalive():
                async with workload_session.cancellation_scope():
                    async with workload_session.provider_slot_async(
                        provider_profile_id,
                        resume_state=WorkloadState.VALIDATING,
                    ):
                        result = await runtime.run(
                            domain_context_packet_ref=dcp_ref,
                            context=context,
                            prompt_user_context=Gate2PromptUserContext(
                                user_id=user_id,
                                user_role=self._user_role(__user__),
                                user_groups=tuple(self._user_groups(__user__)),
                            ),
                        )
                    self.last_workload_snapshot = workload_session.complete(
                        safe_detail={"partial_success_published": False}
                    )
            self.last_runtime_result = result
            self.last_safe_summary = result.safe_summary
            await self._emit(
                __event_emitter__,
                "Gate 2 structured extraction reached a terminal state.",
                done=True,
            )
            await self._emit_workload_snapshot(
                __event_emitter__, self.last_workload_snapshot, done=True
            )
            return result.compact_russian_summary
        except WorkloadCancelledError:
            if workload_session is not None:
                self.last_workload_snapshot = workload_session.snapshot()
            await self._emit(
                __event_emitter__,
                "Gate 2 workload cancelled; no partial success was published.",
                done=True,
            )
            return "Gate 2 workload cancelled. Partial successful output was not published."
        except asyncio.CancelledError:
            if workload_session is not None and not workload_session.terminal:
                workload_session.cancel("caller_task_cancelled")
            raise
        except (
            Gate2SourceFactRuntimeError,
            Gate2PromptError,
            ArtifactStoreError,
            WorkloadAuthorityError,
        ) as exc:
            if workload_session is not None and not workload_session.terminal:
                workload_session.fail(self._workload_failure_code(exc))
                self.last_workload_snapshot = workload_session.snapshot()
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
        except Exception as exc:
            if workload_session is not None and not workload_session.terminal:
                workload_session.fail(self._workload_failure_code(exc))
                self.last_workload_snapshot = workload_session.snapshot()
            raise

    def _workload_authority(self):
        artifact_db = Path(self.valves.artifact_store_path)
        workload_db = (
            Path(self.valves.workload_store_path)
            if str(self.valves.workload_store_path or "").strip()
            else artifact_db.with_name("workloads.sqlite3")
        )
        temp_root = (
            Path(self.valves.workload_temp_root)
            if str(self.valves.workload_temp_root or "").strip()
            else Path(self.valves.artifact_payload_root).parent / "workload-temp"
        )
        return WorkloadAuthorityFactory(
            WorkloadAuthorityConfig(
                sqlite_path=workload_db,
                temp_root=temp_root,
                gate1_concurrency=1,
                gate2_concurrency=2,
                provider_budgets=provider_budgets_from_json(
                    self.valves.workload_provider_budgets_json
                ),
                lease_seconds=float(self.valves.workload_lease_seconds),
                poll_interval_seconds=float(
                    self.valves.workload_poll_interval_seconds
                ),
            )
        ).create()

    @staticmethod
    def _assert_gate1_workload_completed(*, authority, context, dcp_record) -> None:
        job_id = str(dcp_record.safe_metadata.get("workload_job_id") or "").strip()
        if not job_id:
            raise WorkloadAuthorityError("gate1_workload_receipt_missing")
        gate1_access = WorkloadAccessContext(
            user_id=context.user_id,
            case_id=context.case_id,
            chat_id=context.chat_id,
            workspace_model_id=_GATE1_WORKLOAD_SCOPE_MODEL_ID,
        )
        snapshot = authority.snapshot(job_id=job_id, access=gate1_access)
        if snapshot["state"] != WorkloadState.COMPLETED.value:
            raise WorkloadAuthorityError("gate1_workload_not_completed")

    async def _on_workload_wait(self, emitter, snapshot: dict[str, Any]) -> None:
        self.last_workload_snapshot = snapshot
        await self._emit_workload_snapshot(emitter, snapshot, done=False)

    async def _emit_workload_snapshot(
        self,
        emitter,
        snapshot: dict[str, Any] | None,
        *,
        done: bool,
    ) -> None:
        if not snapshot:
            return
        description = (
            f"Broker Reports job {snapshot['job_id']} state: {snapshot['state']}"
        )
        if snapshot.get("queue_position") is not None:
            description += f" (queue {snapshot['queue_position']})"
        if snapshot.get("provider_queue_position") is not None:
            description += f" (provider queue {snapshot['provider_queue_position']})"
        await self._emit(emitter, description, done=done)

    @staticmethod
    def _workload_failure_code(exc: BaseException) -> str:
        raw = str(getattr(exc, "code", "") or exc.__class__.__name__).lower()
        normalized = re.sub(r"[^a-z0-9_.:-]+", "_", raw).strip("_")
        return (normalized or "operation_failed")[:128]

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
