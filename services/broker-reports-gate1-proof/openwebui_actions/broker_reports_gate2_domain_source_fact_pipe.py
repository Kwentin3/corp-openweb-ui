"""
title: Broker Reports Gate 2 Domain Source Fact Extraction
author: Alpha Soft
version: 0.15.0-financial-evidence-registry-v1
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
from broker_reports_gate1.gate2_chat_dcp_resolution import (
    Gate2ChatDcpResolutionError,
    Gate2ChatDcpResolverConfig,
    Gate2ChatDcpResolverFactory,
)
from broker_reports_gate1.gate2_financial_evidence_production_runtime import (
    Gate2FinancialEvidenceProductionConfig,
    Gate2FinancialEvidenceProductionRuntimeFactory,
)
from broker_reports_gate1.gate2_financial_evidence_registry import (
    REGISTRY_VERSION_V1,
    Gate2FinancialEvidenceRegistryFactory,
)
from broker_reports_gate1.gate2_model_requests import (
    FINANCIAL_EVIDENCE_REQUEST_PROFILE,
)


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
        model_id: str = Field(default="")
        provider_profile_id: str = Field(default="openai_gpt")
        anthropic_api_version: str = Field(default="2023-06-01")
        native_provider_timeout_seconds: int = Field(default=180)
        default_wave: str = Field(default="primary")
        default_document_batch_limit: int = Field(default=1)
        default_source_unit_limit: int = Field(default=1)
        segmentation_enabled: bool = Field(default=True)
        prefer_table_projections: bool = Field(default=False)
        allow_standalone_semantic_visual_projections: bool = Field(default=False)
        candidate_binding_enabled: bool = Field(default=False)
        gate3_context_manifest_enabled: bool = Field(default=False)
        answer_context_selection_enabled: bool = Field(default=True)
        default_source_segment_limit: int = Field(default=1)
        table_segment_max_refs: int = Field(default=8)
        text_segment_max_refs: int = Field(default=12)
        max_repair_attempts: int = Field(default=1)
        table_max_rows: int = Field(default=40)
        text_max_chars: int = Field(default=6000)
        financial_evidence_enabled: bool = Field(default=False)
        financial_evidence_registry_version: str = Field(
            default=REGISTRY_VERSION_V1
        )
        financial_evidence_maximum_scopes: int = Field(
            default=64, ge=1, le=256
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self.last_safe_summary: dict[str, Any] | None = None
        self.last_runtime_result = None
        self.last_workload_job_id: str | None = None
        self.last_workload_snapshot: dict[str, Any] | None = None
        self.last_financial_evidence_result = None

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
        user_id = self._user_id(__user__)
        artifact_store_path = Path(
            str(config.get("artifact_store_path") or self.valves.artifact_store_path)
        )
        dcp_ref = self._resolve_dcp_ref(
            resolver=Gate2ChatDcpResolverFactory(
                Gate2ChatDcpResolverConfig(
                    artifact_store_path=artifact_store_path
                )
            ).create(),
            body=body,
            metadata=metadata,
            config=config,
            user_id=user_id,
        )
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
                sqlite_path=artifact_store_path,
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
        workload_session = None
        try:
            authority = self._workload_authority()
            workload_access = WorkloadAccessContext.from_artifact_context(context)
            self._assert_gate1_workload_completed(
                authority=authority,
                context=context,
                dcp_record=dcp_record,
            )
            run_mode = str(config.get("run_mode") or "customer")
            provider_capability_probe = self._config_bool(
                config.get("provider_capability_probe"), default=False
            )
            if provider_capability_probe and run_mode != "provider_qualification":
                raise ValueError("gate2_provider_capability_probe_mode_invalid")
            provider_profile_id = str(
                config.get("provider_profile_id") or self.valves.provider_profile_id
            )
            model_id = gate2_resolve_extraction_model_id(
                provider_profile_id,
                str(config.get("model_id") or self.valves.model_id or ""),
            )
            ticket = authority.submit(
                job_kind=WorkloadKind.GATE2_DOMAIN,
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
                        anthropic_api_version=self.valves.anthropic_api_version,
                        timeout_seconds=self.valves.native_provider_timeout_seconds,
                    ),
                ).create(),
                config=Gate2DomainSourceFactRuntimeConfig(
                    model_id=model_id,
                    workload_job_id=ticket.job_id,
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
                    allow_standalone_semantic_visual_projections=self._config_bool(
                        config.get(
                            "allow_standalone_semantic_visual_projections"
                        ),
                        default=(
                            self.valves.allow_standalone_semantic_visual_projections
                        ),
                    ),
                    candidate_binding_enabled=self._config_bool(
                        config.get("candidate_binding_enabled"),
                        default=self.valves.candidate_binding_enabled,
                    ),
                    gate3_context_manifest_enabled=self._config_bool(
                        config.get("gate3_context_manifest_enabled"),
                        default=self.valves.gate3_context_manifest_enabled,
                    ),
                    answer_context_selection_enabled=self._config_bool(
                        config.get("answer_context_selection_enabled"),
                        default=self.valves.answer_context_selection_enabled,
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
                        financial_result = None
                        if (
                            self.valves.financial_evidence_enabled
                            and run_mode
                            not in {"provider_qualification"}
                            and result.terminal_status == "completed"
                            and result.domain_package_refs
                        ):
                            financial_registry = (
                                Gate2FinancialEvidenceRegistryFactory().create()
                            )
                            if (
                                self.valves.financial_evidence_registry_version
                                != financial_registry.registry_version
                            ):
                                raise ValueError(
                                    "gate2_financial_registry_version_mismatch"
                                )
                            financial_result = await (
                                Gate2FinancialEvidenceProductionRuntimeFactory(
                                    store=store,
                                    registry=financial_registry,
                                    model_client=(
                                        Gate2StructuredModelClientFactory(
                                            config=(
                                                Gate2StructuredModelClientConfig(
                                                    request_profile=(
                                                        FINANCIAL_EVIDENCE_REQUEST_PROFILE
                                                    ),
                                                    provider_profile_id=(
                                                        provider_profile_id
                                                    ),
                                                )
                                            ),
                                            user=__user__,
                                            request=__request__,
                                            native_transport_config=(
                                                Gate2NativeProviderTransportConfig(
                                                    anthropic_api_version=(
                                                        self.valves.anthropic_api_version
                                                    ),
                                                    timeout_seconds=(
                                                        self.valves.native_provider_timeout_seconds
                                                    ),
                                                )
                                            ),
                                        ).create()
                                    ),
                                    config=(
                                        Gate2FinancialEvidenceProductionConfig(
                                            model_id=model_id,
                                            provider_profile_id=(
                                                provider_profile_id
                                            ),
                                            maximum_scopes=(
                                                self.valves.financial_evidence_maximum_scopes
                                            ),
                                        )
                                    ),
                                ).create().run(
                                    domain_package_refs=(
                                        result.domain_package_refs
                                    ),
                                    source_extraction_run_ref=(
                                        result.extraction_run_ref
                                    ),
                                    context=context,
                                    retention_policy=(
                                        dcp_record.retention_policy
                                    ),
                                )
                            )
                    self.last_workload_snapshot = workload_session.complete(
                        safe_detail={"partial_success_published": False}
                    )
            self.last_runtime_result = result
            self.last_financial_evidence_result = financial_result
            self.last_safe_summary = {
                **result.safe_summary,
                "financial_evidence": (
                    None
                    if financial_result is None
                    else financial_result.safe_summary
                ),
            }
            await self._emit(
                __event_emitter__,
                "Gate 2 domain extraction reached a terminal state.",
                done=True,
            )
            await self._emit_workload_snapshot(
                __event_emitter__, self.last_workload_snapshot, done=True
            )
            if financial_result is None:
                return result.compact_russian_summary
            return (
                result.compact_russian_summary
                + "\nGate 2 structured financial evidence context: "
                + financial_result.status
                + "."
            )
        except WorkloadCancelledError:
            if workload_session is not None:
                self.last_workload_snapshot = workload_session.snapshot()
            await self._emit(
                __event_emitter__,
                "Gate 2 domain workload cancelled; no partial success was published.",
                done=True,
            )
            return "Gate 2 domain workload cancelled. Partial successful output was not published."
        except asyncio.CancelledError:
            if workload_session is not None and not workload_session.terminal:
                workload_session.cancel("caller_task_cancelled")
            raise
        except (
            Gate2SourceFactRuntimeError,
            Gate2PromptError,
            ArtifactStoreError,
            WorkloadAuthorityError,
            ValueError,
        ) as exc:
            if workload_session is not None and not workload_session.terminal:
                workload_session.fail(self._workload_failure_code(exc))
                self.last_workload_snapshot = workload_session.snapshot()
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
        except Exception as exc:
            if workload_session is not None and not workload_session.terminal:
                workload_session.fail(self._workload_failure_code(exc))
                self.last_workload_snapshot = workload_session.snapshot()
            raise

    def _workload_authority(self):
        # Only server-managed valves can select the single coordination store.
        # Request/body configuration is intentionally not workload authority.
        artifact_db = Path(self.valves.artifact_store_path)
        payload_root = Path(self.valves.artifact_payload_root)
        workload_db = (
            Path(self.valves.workload_store_path)
            if str(self.valves.workload_store_path or "").strip()
            else artifact_db.with_name("workloads.sqlite3")
        )
        temp_root = (
            Path(self.valves.workload_temp_root)
            if str(self.valves.workload_temp_root or "").strip()
            else payload_root.parent / "workload-temp"
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

    def _runtime_config(self, body: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for source in (
            metadata.get("broker_reports_gate2_domain"),
            body.get("broker_reports_gate2_domain"),
        ):
            if isinstance(source, dict):
                result.update(source)
        return result

    @staticmethod
    def _resolve_dcp_ref(
        *,
        resolver,
        body: dict[str, Any],
        metadata: dict[str, Any],
        config: dict[str, Any],
        user_id: str,
    ) -> str:
        explicit = str(config.get("domain_context_packet_ref") or "").strip()
        if explicit:
            return explicit
        body_metadata = (
            body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        )
        chat_id = str(
            metadata.get("chat_id")
            or body.get("chat_id")
            or body_metadata.get("chat_id")
            or ""
        ).strip()
        if not user_id or not chat_id:
            return ""
        try:
            return resolver.resolve(
                user_id=user_id,
                chat_id=chat_id,
            )
        except Gate2ChatDcpResolutionError:
            return ""

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
