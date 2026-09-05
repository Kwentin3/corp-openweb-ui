"""
title: Broker Reports Gate 1 Pipe Backend Normalizer
author: Alpha Soft
version: 0.40.2-observed-image-review
required_open_webui_version: 0.9.6
requirements: pydantic,pypdf==6.7.5,lxml==6.1.1
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import copy
import hashlib
import html
import inspect
import io
import json
import re
import urllib.parse
import urllib.request
import uuid
from contextlib import nullcontext
from dataclasses import asdict, is_dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    BytesUnavailable,
    ClarificationError,
    ClarificationPromptConfig,
    ClarificationPromptResolverFactory,
    DocumentPassportError,
    DocumentPassportPromptConfig,
    DocumentPassportPromptResolverFactory,
    FileInput,
    Gate1BoundedGraphConfig,
    Gate1BoundedGraphFactory,
    Gate1Normalizer,
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
    ManagedPrompt,
    NORMALIZER_VERSION,
    PromptUserContext,
    SAFETY_STATEMENT as SAFETY_STATEMENT,
    RetentionPolicyError,
    WorkloadAccessContext,
    WorkloadAuthorityConfig,
    WorkloadAuthorityFactory,
    WorkloadCancelledError,
    WorkloadKind,
    WorkloadState,
    apply_document_passport_stage,
    apply_clarification_request_stage,
    apply_metadata_gap_report_stage,
    build_llm_document_packages,
    build_metadata_gap_report,
    build_retention_policy,
    is_terminal_pdf_document_ai_request,
    clarification_json_object_response_format,
    clarification_json_schema_response_format,
    clarification_model_call_audit_metadata,
    gate1_clarification_request_schema_hash,
    model_call_audit_metadata,
    parse_clarification_request_model_output,
    parse_document_passport_model_output,
    passport_json_object_response_format,
    passport_json_schema_response_format,
    persist_gate1_result,
    render_chat_content,
    validate_document_metadata_passport,
    validation_error_summary,
    provider_budgets_from_json,
)
from broker_reports_gate1.detectors import extension_from_name
from broker_reports_gate1.normalizer import NormalizationResult
from broker_reports_gate1.ordinary_trade_production_runtime import (
    OrdinaryTradeProductionRuntimeFactory,
)
from broker_reports_gate1.ordinary_trade_projection import (
    OrdinaryTradeProjectionFactory,
)
from broker_reports_gate1.gate5_human_gap_closure import (
    Gate5HumanGapClosureError,
)
from broker_reports_gate1.ordinary_trade_declaration_chat_adapter import (
    adapt_current_declaration_request,
    build_public_dialogue_context,
    build_public_question_context,
    declaration_change_intent,
    declaration_request_help,
    declaration_request_question,
    public_answer_candidate_conflicts_with_explicit_negation,
    public_answer_requires_clarification,
    public_dialogue_context_sha256,
    public_dialogue_interpretation_messages,
    public_dialogue_interpretation_response_format,
    public_dialogue_message_response_format,
    public_dialogue_render_messages,
    public_mapping_verification_messages,
    public_mapping_verification_response_format,
    render_public_dialogue_fallback,
    validate_public_dialogue_interpretation,
    validate_public_dialogue_message,
)
from broker_reports_gate1.private_intake_bytes import (
    OpenWebUIPrivateIntakeBytesResolverFactory,
    PrivateIntakeBytesError,
    is_private_intake_source_id,
)
from broker_reports_gate1.pdf_document_ai_qualification import (
    PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES,
    PdfDocumentAiQualificationError,
    PdfDocumentAiQualificationExecutor,
    PdfDocumentAiQualificationPlanFactory,
)
from broker_reports_gate1.pdf_document_ai_qualification_review import (
    PDF_DOCUMENT_AI_REVIEW_CHECKS,
    PdfDocumentAiQualificationReviewFactory,
    PdfDocumentAiQualificationReviewVerdict,
    PdfDocumentAiQualificationReviewView,
)
from broker_reports_gate1.gate2_model_clients import (
    Gate2StructuredModelClientFactory,
)
from broker_reports_gate1.gate2_model_contracts import (
    Gate2StructuredModelClientConfig,
)
from broker_reports_gate1.gate2_model_requests import (
    GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
    ORDINARY_TRADE_MAPPING_ANSWER_REQUEST_PROFILE,
    ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE,
)
from broker_reports_gate1.gate3_ndfl_workflow import (
    NDFL_PROVIDER_MODEL_ID,
    NDFL_PROVIDER_PROFILE_ID,
    NDFL_WORKFLOW_STABLE_ID,
    NDFL_WORKSPACE_MODEL_STABLE_ID,
    NdflWorkflowError,
    NdflWorkflowFactory,
    ndfl_product_binding_snapshot,
)
from broker_reports_gate1.gate4_financial_case_cache import (
    Gate4FinancialCaseRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_preparation import (
    Gate5DeclarationPreparationRuntimeFactory,
)
from broker_reports_gate1.gate5_declaration_scope_resolution import (
    GATE5_USER_INTENT_SCHEMA_VERSION,
)
from broker_reports_gate1.gate5_trusted_methodology import (
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID,
    GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION,
    GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
)


_GATE1_WORKLOAD_SCOPE_MODEL_ID = "broker_reports_gate1_pipe"
_GATE1_IDEMPOTENCY_POLICY_VERSION = "broker_reports_gate1_native_request_idempotency_v1"
_GATE2_USABLE_HANDOFF_STATUSES = frozenset(
    {"ready_with_safe_refs", "ready_with_reduced_subset"}
)
_COMPLETED_WITH_REVIEW_ADVISORY = "completed_with_review_advisory"
NDFL_PRESENTATION_COMPLETION_TIMEOUT_SECONDS = 45.0
NDFL_PRESENTATION_MAX_RESPONSE_BYTES = 1024 * 1024
PDF_DOCUMENT_AI_QUALIFICATION_COMMAND = "PDF Document AI live qualification"
PDF_DOCUMENT_AI_QUALIFICATION_REVIEW_TTL_SECONDS = 15 * 60


class _NdflPresentationNoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep the user credential on the one administrator-pinned origin."""

    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


def _trusted_taxpayer_scope_ref_required() -> str:
    raise NdflWorkflowError("ndfl_trusted_taxpayer_scope_binding_required")


class Pipe:
    """OpenWebUI adapter: file refs -> backend Gate 1 normalizer -> safe report."""

    class Valves(BaseModel):
        require_trigger_phrase: bool = Field(default=False)
        trigger_phrases: str = Field(
            default=(
                "gate1,gate 1,normalization,normalize,"
                "\u043d\u043e\u0440\u043c\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f,"
                "\u043d\u043e\u0440\u043c\u0430\u043b\u0438\u0437\u0443\u0439"
            )
        )
        upload_root: str = Field(default="/app/backend/data/uploads")
        allow_upload_path_access: bool = Field(default=True)
        artifact_store_path: str = Field(
            default="/app/backend/data/broker_reports_gate1/artifacts.sqlite3"
        )
        artifact_payload_root: str = Field(
            default="/app/backend/data/broker_reports_gate1/payloads"
        )
        pdf_document_ai_qualification_repository_head: str = Field(default="")
        workload_store_path: str = Field(default="")
        workload_temp_root: str = Field(default="")
        workload_lease_seconds: float = Field(default=90.0, ge=5.0, le=600.0)
        workload_poll_interval_seconds: float = Field(default=0.2, ge=0.05, le=5.0)
        workload_provider_budgets_json: str = Field(
            default=(
                '{"google_gemini":1,"openai_gpt":2,"anthropic_claude":1,'
                '"deepseek":1,"zai_glm":1,"alibaba_qwen":1,'
                '"openwebui_completion":2}'
            )
        )
        artifact_retention_mode: str = Field(default="api_smoke")
        artifact_retention_ttl_seconds: int = Field(default=24 * 60 * 60)
        artifact_retention_explicit: bool = Field(default=True)
        passport_enabled: bool = Field(default=False)
        passport_prompt_db_path: str = Field(default="/app/backend/data/webui.db")
        passport_prompt_id: str = Field(default="")
        passport_prompt_command: str = Field(default="broker_gate1_document_passport")
        passport_model_id: str = Field(default="")
        passport_max_documents: int = Field(default=32)
        clarification_enabled: bool = Field(default=False)
        clarification_prompt_db_path: str = Field(default="/app/backend/data/webui.db")
        clarification_prompt_id: str = Field(default="")
        clarification_prompt_command: str = Field(
            default="broker_gate1_clarification_request"
        )
        clarification_model_id: str = Field(default="")
        clarification_criticality_refinement_enabled: bool = Field(default=True)
        canonical_gate2_write_enabled: bool = Field(
            default=False,
            description="Write Gate 2 CanonicalArtifactV1 shadow versions only.",
        )
        canonical_gate2_read_enabled: bool = Field(
            default=False,
            description="Reserved for controlled Gate 2 consumer cutover; keep false in DOC26.",
        )
        ndfl_gate3_enabled: bool = Field(
            default=False,
            description="Run Gate 3 only for the stable NDFL Workspace Model ID.",
        )
        ordinary_trade_candidate_enabled: bool = Field(
            default=False,
            description=(
                "Use the ordinary-trade source-semantic compiler before Gate 5."
            ),
        )
        ordinary_trade_semantic_mapping_enabled: bool = Field(
            default=True,
            description=(
                "Resolve unknown schemas through one strict case-scoped semantic "
                "mapping call; known exact schemas remain zero-call."
            ),
        )
        ordinary_trade_mapping_provider_profile_id: str = Field(
            default=NDFL_PROVIDER_PROFILE_ID
        )
        ordinary_trade_mapping_model_id: str = Field(
            default=NDFL_PROVIDER_MODEL_ID
        )
        ndfl_gate3_provider_profile_id: str = Field(default=NDFL_PROVIDER_PROFILE_ID)
        ndfl_gate3_model_id: str = Field(default=NDFL_PROVIDER_MODEL_ID)
        ndfl_gate3_private_audit_enabled: bool = Field(default=False)
        ndfl_gate3_private_audit_root: str = Field(
            default="/app/backend/data/broker_reports_gate1/gate3-product-proof"
        )
        ndfl_gate3_private_audit_id: str = Field(default="")
        ndfl_presentation_llm_enabled: bool = Field(default=True)
        ndfl_presentation_model_id: str = Field(default=NDFL_PROVIDER_MODEL_ID)
        ndfl_presentation_openwebui_origin: str = Field(
            default="",
            description=(
                "Administrator-pinned HTTPS origin for the native OpenWebUI "
                "completion endpoint; never derived from request metadata."
            ),
        )
        live_smoke_trigger_phrases: str = Field(
            default="artifactstore retention smoke,gate1 artifactstore smoke"
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self._normalizer = Gate1Normalizer()
        self.last_safe_report: dict | None = None
        self.last_artifact_manifest: dict | None = None
        self.last_workload_job_id: str | None = None
        self.last_workload_snapshot: dict[str, Any] | None = None
        self._active_workload_session = None
        self._workload_review_items = 0
        self._presentation_llm_calls_total = 0

    async def pipe(
        self,
        body: dict,
        __user__=None,
        __request__=None,
        __metadata__=None,
        __files__=None,
        __messages__=None,
        __event_emitter__=None,
        __event_call__=None,
        **kwargs,
    ) -> str:
        self._presentation_llm_calls_total = 0
        safe_body = body if isinstance(body, dict) else {}
        messages_arg = __messages__ or kwargs.get("__messages__")
        metadata = await self._server_attested_runtime_metadata(
            request=__request__,
            metadata=(__metadata__ if isinstance(__metadata__, dict) else {}),
            user=__user__,
        )
        if metadata.get("model_id") == NDFL_WORKFLOW_STABLE_ID:
            return self._ndfl_legacy_route_content()
        interaction_message = await self._trusted_interaction_message(
            body=safe_body,
            messages_arg=messages_arg,
            request=__request__,
            metadata=metadata,
            user=__user__,
        )
        if interaction_message.strip() == PDF_DOCUMENT_AI_QUALIFICATION_COMMAND:
            direct_message = self._latest_user_message(safe_body, messages_arg)
            if (
                metadata.get("task")
                or direct_message.strip() != PDF_DOCUMENT_AI_QUALIFICATION_COMMAND
            ):
                return "PDF Document AI qualification is unavailable for internal tasks."
            return await self._run_pdf_document_ai_qualification(
                body=safe_body,
                user=__user__,
                request=__request__,
                metadata=metadata,
                files=__files__,
                messages=__messages__,
                event_emitter=__event_emitter__,
                event_call=__event_call__,
                kwargs=kwargs,
            )
        if "broker_reports_declaration_action" in safe_body:
            raise NdflWorkflowError("ordinary_trade_declaration_hidden_action_forbidden")
        completed_turn = await self._server_attested_completed_turn_content(
            metadata=metadata,
            user=__user__,
            interaction_message=interaction_message,
        )
        if completed_turn is not None:
            self.last_artifact_manifest = {
                "resumed_case": True,
                "replayed_completed_openwebui_turn": True,
            }
            return completed_turn
        resumed = await self._maybe_resume_ndfl_chat_turn(
            body=safe_body,
            metadata=metadata,
            user=__user__,
            request=__request__,
            event_emitter=__event_emitter__,
            event_call=__event_call__,
            interaction_message=interaction_message,
            kwargs=kwargs,
        )
        if resumed is not None:
            return resumed
        if self.valves.require_trigger_phrase and not self._has_trigger_phrase(
            safe_body, messages_arg
        ):
            return await self._run_workload(
                body,
                __user__=__user__,
                __request__=__request__,
                __metadata__=metadata,
                __files__=__files__,
                __messages__=__messages__,
                __event_emitter__=__event_emitter__,
                __event_call__=__event_call__,
                __trusted_interaction_message__=interaction_message,
                **kwargs,
            )

        session = None
        hide_internal_workload = (
            metadata.get("model_id") == NDFL_WORKSPACE_MODEL_STABLE_ID
        )
        try:
            access = WorkloadAccessContext.from_artifact_context(
                self._artifact_context(
                    user=__user__,
                    metadata=metadata,
                    body=safe_body,
                    kwargs=kwargs,
                    normalization_run_id="workload_admission_preflight",
                )
            )
            access = self._canonical_workload_access(access)
            files_arg = __files__ or kwargs.get("__files__")
            file_refs = self._collect_file_refs(
                safe_body,
                metadata,
                files_arg,
                messages_arg,
            )
            idempotency_key = self._workload_idempotency_key(
                access=access,
                file_refs=file_refs,
                interaction_sha256=(
                    hashlib.sha256(interaction_message.encode("utf-8")).hexdigest()
                    if interaction_message
                    else None
                ),
            )
            authority = self._workload_authority()
            ticket = authority.submit(
                job_kind=WorkloadKind.GATE1,
                access=access,
                idempotency_key=idempotency_key,
                safe_metadata={
                    "idempotency_policy_version": (_GATE1_IDEMPOTENCY_POLICY_VERSION),
                    "idempotency_key_present": idempotency_key is not None,
                    "source_refs_total": len(file_refs),
                },
            )
            self.last_workload_job_id = ticket.job_id
            self.last_workload_snapshot = authority.snapshot(
                job_id=ticket.job_id,
                access=access,
            )
            if ticket.reused_existing:
                self.last_workload_snapshot = {
                    **self.last_workload_snapshot,
                    "idempotency_reused": True,
                }
                await self._emit_workload_snapshot(
                    __event_emitter__,
                    self.last_workload_snapshot,
                    done=self.last_workload_snapshot.get("state")
                    in {"completed", "failed", "cancelled", "awaiting_review"},
                    hide_internal=hide_internal_workload,
                )
                return self._reused_workload_content(
                    self.last_workload_snapshot,
                    hide_internal=hide_internal_workload,
                )
            await self._emit_workload_snapshot(
                __event_emitter__,
                self.last_workload_snapshot,
                done=False,
                hide_internal=hide_internal_workload,
            )

            async def on_wait(snapshot):
                self.last_workload_snapshot = snapshot
                await self._emit_workload_snapshot(
                    __event_emitter__,
                    snapshot,
                    done=False,
                    hide_internal=hide_internal_workload,
                )

            session = await authority.wait_for_admission(
                job_id=ticket.job_id,
                access=access,
                on_wait=on_wait,
            )
            self._active_workload_session = session
            self._workload_review_items = 0
            self.last_workload_snapshot = session.snapshot()
            await self._emit_workload_snapshot(
                __event_emitter__,
                self.last_workload_snapshot,
                done=False,
                hide_internal=hide_internal_workload,
            )
            with session.keepalive():
                async with session.cancellation_scope():
                    content = await self._run_workload(
                        body,
                        __user__=__user__,
                        __request__=__request__,
                        __metadata__=metadata,
                        __files__=__files__,
                        __messages__=__messages__,
                        __event_emitter__=__event_emitter__,
                        __event_call__=__event_call__,
                        __trusted_interaction_message__=interaction_message,
                        **kwargs,
                    )
                if not session.terminal:
                    self._finalize_workload_publication()
                else:
                    self.last_workload_snapshot = session.snapshot()
            await self._emit_workload_snapshot(
                __event_emitter__,
                self.last_workload_snapshot,
                done=True,
                hide_internal=hide_internal_workload,
            )
            return content
        except WorkloadCancelledError:
            if session is not None:
                self.last_workload_snapshot = session.snapshot()
            await self._emit(
                __event_emitter__,
                (
                    "Подготовка 3-НДФЛ отменена. Незавершённый результат не опубликован."
                    if hide_internal_workload
                    else "Broker Reports workload cancelled; no partial success was published."
                ),
                done=True,
            )
            return (
                "Подготовка 3-НДФЛ отменена. Незавершённый результат не опубликован."
                if hide_internal_workload
                else "Broker Reports workload cancelled. Partial successful output was not published."
            )
        except asyncio.CancelledError:
            if session is not None and not session.terminal:
                session.cancel("caller_task_cancelled")
            raise
        except Exception as exc:
            if session is not None and not session.terminal:
                session.fail(
                    self._workload_failure_code(exc),
                    safe_detail=self._workload_failure_detail(exc),
                )
                self.last_workload_snapshot = session.snapshot()
            raise
        finally:
            self._active_workload_session = None

    @staticmethod
    def _canonical_workload_access(
        access: WorkloadAccessContext,
    ) -> WorkloadAccessContext:
        return WorkloadAccessContext(
            user_id=access.user_id,
            case_id=access.case_id,
            chat_id=access.chat_id,
            workspace_model_id=_GATE1_WORKLOAD_SCOPE_MODEL_ID,
        )

    @staticmethod
    def _workload_idempotency_key(
        *,
        access: WorkloadAccessContext,
        file_refs: list[dict[str, Any]],
        interaction_sha256: str | None = None,
    ) -> str | None:
        source_ids = sorted(
            {
                str(item.get("file_id") or "").strip()
                for item in file_refs
                if str(item.get("file_id") or "").strip()
            }
        )
        if not source_ids:
            return None
        material = json.dumps(
            {
                "policy_version": (_GATE1_IDEMPOTENCY_POLICY_VERSION),
                "user_id": access.user_id,
                "case_id": access.case_id,
                "chat_id": access.chat_id,
                "workspace_model_id": access.workspace_model_id,
                "source_file_ids": source_ids,
                "interaction_sha256": interaction_sha256,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return "bridem_" + hashlib.sha256(material.encode("utf-8")).hexdigest()

    @staticmethod
    def _reused_workload_content(
        snapshot: dict[str, Any], *, hide_internal: bool = False
    ) -> str:
        state = str(snapshot.get("state") or "")
        if hide_internal:
            return {
                "completed": (
                    "Этот файл уже обработан. Текущий результат доступен в кейсе."
                ),
                "awaiting_review": (
                    "Обработка завершена, но результат требует проверки специалистом."
                ),
                "failed": (
                    "Файл обработать не удалось. Незавершённый результат не опубликован."
                ),
                "cancelled": (
                    "Обработка файла отменена. Незавершённый результат не опубликован."
                ),
            }.get(state, "Этот файл уже обрабатывается.")
        if state == "completed":
            if snapshot.get("terminal_code") == _COMPLETED_WITH_REVIEW_ADVISORY:
                return (
                    "Broker Reports processing completed. "
                    "The processed data are available for questions. "
                    "Some unsupported scopes require review."
                )
            return (
                "Broker Reports processing completed. "
                "The processed data are available for questions."
            )
        if state == "awaiting_review":
            return (
                "Broker Reports processing requires review before the data can "
                "be used for questions."
            )
        if state == "failed":
            return (
                "Broker Reports processing failed. No completed result was published."
            )
        if state == "cancelled":
            return (
                "Broker Reports processing was cancelled. "
                "No partial result was published."
            )
        return "Broker Reports processing is already in progress."

    async def _run_pdf_document_ai_qualification(
        self,
        *,
        body: dict[str, Any],
        user: Any,
        request: Any,
        metadata: dict[str, Any],
        files: Any,
        messages: Any,
        event_emitter: Any,
        event_call: Any,
        kwargs: dict[str, Any],
    ) -> str:
        """Bind the exact two-slot qualification to the real authenticated Pipe."""

        if not isinstance(user, dict) or str(user.get("role") or "") != "admin":
            raise PdfDocumentAiQualificationError(
                "pdf_document_ai_qualification_admin_required"
            )
        self._artifact_context(
            user=user,
            metadata=metadata,
            body=body,
            kwargs=kwargs,
            normalization_run_id="pdf_document_ai_qualification_preflight",
        )
        self._artifact_store()
        repository_head = str(
            self.valves.pdf_document_ai_qualification_repository_head or ""
        ).strip()
        file_refs = self._collect_file_refs(body, metadata, files, messages)
        await self._hydrate_private_intake_file_refs(
            file_refs,
            actor_user_id=self._authenticated_user_id(user),
        )
        if len(file_refs) != len(PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES):
            raise PdfDocumentAiQualificationError(
                "pdf_document_ai_qualification_exact_fixture_set_required"
            )

        expected_by_path = {
            repository_path: expected_sha256
            for _fixture_id, repository_path, expected_sha256 in (
                PDF_DOCUMENT_AI_QUALIFICATION_FIXTURES
            )
        }
        payload_by_sha256: dict[str, bytes] = {}
        file_ref_by_sha256: dict[str, dict[str, Any]] = {}
        for file_ref in file_refs:
            payload = self._read_original_bytes(file_ref)
            observed_sha256 = hashlib.sha256(payload).hexdigest()
            if observed_sha256 in file_ref_by_sha256:
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_exact_fixture_set_required"
                )
            payload_by_sha256[observed_sha256] = payload
            file_ref_by_sha256[observed_sha256] = file_ref
        if set(payload_by_sha256) != set(expected_by_path.values()):
            raise PdfDocumentAiQualificationError(
                "pdf_document_ai_qualification_exact_fixture_set_required"
            )

        def fixture_reader(repository_path: str) -> bytes:
            expected_sha256 = expected_by_path.get(repository_path)
            if expected_sha256 is None:
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_fixture_path_forbidden"
                )
            return payload_by_sha256[expected_sha256]

        plan = PdfDocumentAiQualificationPlanFactory.create(
            repository_head=repository_head,
            fixture_reader=fixture_reader,
        )
        safe_metadata = {
            key: value
            for key, value in metadata.items()
            if key not in {"file", "files", "message", "messages"}
        }
        safe_kwargs = {
            key: value
            for key, value in kwargs.items()
            if key not in {"__file__", "__files__", "__message__", "__messages__"}
        }

        async def run_existing_pipe(**runner_input: Any) -> dict[str, object]:
            expected_sha256 = str(runner_input["expected_sha256"])
            file_ref = file_ref_by_sha256[expected_sha256]
            if runner_input["pdf_bytes"] != payload_by_sha256[expected_sha256]:
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_fixture_hash_mismatch"
                )
            result = await self._run_workload(
                {"messages": [{"role": "user", "content": "Gate 1 normalization"}]},
                __user__=user,
                __request__=request,
                __metadata__=safe_metadata,
                __files__=[file_ref["_private_file_obj"]],
                __messages__=None,
                __event_emitter__=event_emitter,
                __event_call__=event_call,
                __pdf_document_ai_qualification_permit__=runner_input[
                    "qualification_permit"
                ],
                __pdf_document_ai_qualification_only__=True,
                __pdf_document_ai_qualification_fixture_id__=runner_input[
                    "fixture_id"
                ],
                __pdf_document_ai_qualification_source_pdf_bytes__=runner_input[
                    "pdf_bytes"
                ],
                __pdf_document_ai_qualification_source_pdf_sha256__=runner_input[
                    "expected_sha256"
                ],
                __pdf_document_ai_qualification_source_file_id__=file_ref["file_id"],
                **safe_kwargs,
            )
            if not isinstance(result, dict):
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_pipe_result_invalid"
                )
            return result

        claim_root = (
            Path(self.valves.artifact_payload_root).parent
            / "pdf-document-ai-qualification-claims"
        )
        receipt = await PdfDocumentAiQualificationExecutor(
            claim_root=claim_root
        ).execute_async(
            plan=plan,
            fixture_reader=fixture_reader,
            pipe_runner=run_existing_pipe,
        )
        return json.dumps(receipt, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _qualification_review_text_panel(content: str) -> str:
        """Keep native confirmation controls visible around long private text."""

        return (
            '<div style="max-height:52vh;overflow:auto;overscroll-behavior:contain;'
            'border:1px solid rgba(128,128,128,.35);border-radius:.5rem;'
            'padding:.75rem">'
            '<pre style="margin:0;white-space:pre-wrap;overflow-wrap:anywhere">'
            f"{html.escape(content)}"
            "</pre></div>"
        )

    @staticmethod
    def _qualification_review_image_panel(
        *,
        page: int,
        target: str,
        image_sha256: str,
        content: bytes,
        media_type: str,
    ) -> str:
        """Bound a private image preview without pushing dialog controls off-screen."""

        encoded = base64.b64encode(content).decode("ascii")
        description = html.escape(
            f"page={page} target={target} sha256={image_sha256}"
        )
        safe_media_type = html.escape(media_type, quote=True)
        return (
            '<div style="max-height:52vh;overflow:auto;overscroll-behavior:contain">'
            f"<p><code>{description}</code></p>"
            '<img alt="private qualification image" '
            f'src="data:{safe_media_type};base64,{encoded}" '
            'style="display:block;max-width:100%;max-height:44vh;'
            'object-fit:contain;margin:auto" />'
            "</div>"
        )

    @staticmethod
    def _qualification_reviewer(event_call: Any):
        """Adapt the existing private OpenWebUI interaction to one review verdict."""

        async def review(
            view: PdfDocumentAiQualificationReviewView,
        ) -> PdfDocumentAiQualificationReviewVerdict:
            if not callable(event_call):
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_private_review_required"
                )
            source_accepted = await event_call(
                {
                    "type": "confirmation",
                    "data": {
                        "title": f"Private PDF review: {view.fixture_id} source",
                        "message": (
                            f"Source SHA-256: `{view.source_pdf_sha256}`\n\n"
                            "Review the matching pinned fixture that was opened "
                            "outside this modal before the qualification started. "
                            f"The bound OpenWebUI file id is `{view.source_file_id}`."
                        ),
                    },
                }
            )
            if source_accepted is not True:
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_review_aborted"
                )
            binding_accepted = await event_call(
                {
                    "type": "confirmation",
                    "data": {
                        "title": f"Private PDF review: {view.fixture_id} binding",
                        "message": Pipe._qualification_review_text_panel(
                            json.dumps(
                                {
                                    "repository_head": view.repository_head,
                                    "live_output_digest": view.live_output_digest,
                                    "execution_binding": view.execution_binding,
                                    "structural_counts": view.structural_counts,
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                            )
                        ),
                    },
                }
            )
            if binding_accepted is not True:
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_review_aborted"
                )
            chunks = [
                view.markdown[index : index + 5_000]
                for index in range(0, len(view.markdown), 5_000)
            ] or [""]
            for ordinal, chunk in enumerate(chunks, start=1):
                accepted = await event_call(
                    {
                        "type": "confirmation",
                        "data": {
                            "title": (
                                f"Private PDF review: {view.fixture_id} "
                                f"Markdown {ordinal}/{len(chunks)}"
                            ),
                            "message": Pipe._qualification_review_text_panel(chunk),
                        },
                    }
                )
                if accepted is not True:
                    raise PdfDocumentAiQualificationError(
                        "pdf_document_ai_qualification_review_aborted"
                    )
            for ordinal, (page, target, image_sha256, content, media_type) in enumerate(
                view.images, start=1
            ):
                accepted = await event_call(
                    {
                        "type": "confirmation",
                        "data": {
                            "title": (
                                f"Private PDF review: {view.fixture_id} "
                                f"image {ordinal}/{len(view.images)}"
                            ),
                            "message": Pipe._qualification_review_image_panel(
                                page=page,
                                target=target,
                                image_sha256=image_sha256,
                                content=content,
                                media_type=media_type,
                            ),
                        },
                    }
                )
                if accepted is not True:
                    raise PdfDocumentAiQualificationError(
                        "pdf_document_ai_qualification_review_aborted"
                    )
            checks: dict[str, bool] = {}
            for check in PDF_DOCUMENT_AI_REVIEW_CHECKS:
                value = await event_call(
                    {
                        "type": "confirmation",
                        "data": {
                            "title": f"Private PDF review: {view.fixture_id}",
                            "message": (
                                f"Confirm `{check}` for live output digest "
                                f"`{view.live_output_digest}`."
                            ),
                        },
                    }
                )
                checks[check] = value is True
            return PdfDocumentAiQualificationReviewVerdict(
                live_output_digest=view.live_output_digest,
                checks=checks,
            )

        return review

    async def _run_workload(
        self,
        body: dict,
        __user__=None,
        __request__=None,
        __metadata__=None,
        __files__=None,
        __messages__=None,
        __event_emitter__=None,
        __event_call__=None,
        **kwargs,
    ) -> str | dict[str, object]:
        safe_body = body if isinstance(body, dict) else {}
        safe_metadata = __metadata__ if isinstance(__metadata__, dict) else {}
        qualification_only = bool(
            kwargs.pop("__pdf_document_ai_qualification_only__", False)
        )
        qualification_fixture_id = kwargs.pop(
            "__pdf_document_ai_qualification_fixture_id__", None
        )
        qualification_source_pdf_bytes = kwargs.pop(
            "__pdf_document_ai_qualification_source_pdf_bytes__", None
        )
        qualification_source_pdf_sha256 = kwargs.pop(
            "__pdf_document_ai_qualification_source_pdf_sha256__", None
        )
        qualification_source_file_id = kwargs.pop(
            "__pdf_document_ai_qualification_source_file_id__", None
        )
        await self._emit(
            __event_emitter__,
            self._progress_description(
                safe_metadata,
                user_message="Проверяю загруженный файл…",
                internal_message="Checking uploaded file refs...",
            ),
            done=False,
        )
        trusted_interaction_message = str(
            kwargs.pop("__trusted_interaction_message__", "") or ""
        ).strip()
        messages_arg = __messages__ or kwargs.get("__messages__")
        files_arg = __files__ or kwargs.get("__files__")
        if self.valves.require_trigger_phrase and not self._has_trigger_phrase(
            safe_body, messages_arg
        ):
            await self._emit(
                __event_emitter__, "Gate 1 trigger phrase was not found.", done=True
            )
            return (
                "Gate 1 normalization is available. Attach documents and send "
                "`Gate 1 normalization` in the same message."
            )

        file_refs = self._collect_file_refs(
            safe_body, safe_metadata, files_arg, messages_arg
        )
        await self._hydrate_private_intake_file_refs(
            file_refs,
            actor_user_id=self._authenticated_user_id(__user__),
        )
        input_context = self._safe_input_context(
            safe_body, safe_metadata, files_arg, messages_arg
        )
        case_group_id = self._case_group_id(safe_body, safe_metadata)
        if case_group_id:
            input_context["case_group_id"] = case_group_id
        body_metadata = (
            safe_body.get("metadata")
            if isinstance(safe_body.get("metadata"), dict)
            else {}
        )
        case_id = (
            safe_metadata.get("case_id")
            or body_metadata.get("case_id")
            or safe_body.get("case_id")
        )
        if case_id:
            input_context["case_id"] = str(case_id)
        criticality_refinement_enabled = self._criticality_refinement_enabled(
            safe_body, safe_metadata
        )
        file_inputs = [self._to_file_input(file_ref) for file_ref in file_refs]
        retention_policy = self._retention_policy(safe_body, safe_metadata)
        if qualification_only:
            retention_policy = build_retention_policy(
                mode="expires_after_ttl",
                ttl_seconds=PDF_DOCUMENT_AI_QUALIFICATION_REVIEW_TTL_SECONDS,
            )
        normalizer = Gate1Normalizer(
            _server_request=__request__,
            _pdf_image_root=Path(self.valves.artifact_payload_root),
            _pdf_document_ai_qualification_permit=kwargs.pop(
                "__pdf_document_ai_qualification_permit__", None
            ),
        )
        planned_run_id = normalizer.plan_run_id(file_inputs)
        artifact_context = self._artifact_context(
            user=__user__,
            metadata=safe_metadata,
            body=safe_body,
            kwargs=kwargs,
            normalization_run_id=planned_run_id,
        )
        artifact_store = self._artifact_store()
        bounded_graph = Gate1BoundedGraphFactory(
            Gate1BoundedGraphConfig(
                store=artifact_store,
                context=artifact_context,
                retention_policy=retention_policy,
                source_file_refs=tuple(self._source_file_refs(file_refs)),
            )
        ).create(normalization_run_id=planned_run_id)
        result = await asyncio.to_thread(
            normalizer.normalize,
            file_inputs,
            entrypoint="broker_reports_gate1_pipe",
            trigger_type="pipe_backend_normalizer",
            input_context={
                **input_context,
                "normalizer_version": NORMALIZER_VERSION,
                "workload_job_id": (
                    self._active_workload_session.job_id
                    if self._active_workload_session is not None
                    else None
                ),
                "retention_policy_mode": retention_policy.mode,
                "retention_policy_explicit": retention_policy.explicit,
                "clarification_criticality_refinement_enabled": criticality_refinement_enabled,
                "canonical_gate2_write_enabled": bool(
                    self.valves.canonical_gate2_write_enabled
                ),
                "canonical_gate2_read_enabled": bool(
                    self.valves.canonical_gate2_read_enabled
                ),
            },
            extra_private_markers=self._private_markers(file_refs),
            bounded_graph=bounded_graph,
            workload_checkpoint=self._workload_checkpoint,
            workload_progress=self._workload_progress,
        )
        if qualification_only:
            artifact_manifest = persist_gate1_result(
                store=artifact_store,
                result=result,
                context=artifact_context,
                retention_policy=retention_policy,
                source_file_refs=self._source_file_refs(file_refs),
            )
            private_full_source_refs = list(
                artifact_manifest.artifact_refs_by_type.get(
                    "private_normalized_source_payload_v0", []
                )
            )
            if not private_full_source_refs:
                raise PdfDocumentAiQualificationError(
                    "pdf_document_ai_qualification_full_source_missing"
                )
            expires_at = datetime.fromisoformat(str(retention_policy.expires_at))
            review = await PdfDocumentAiQualificationReviewFactory.create(
                store=artifact_store,
                context=artifact_context,
                full_source_refs=private_full_source_refs,
                repository_head=str(
                    self.valves.pdf_document_ai_qualification_repository_head or ""
                ),
                fixture_id=str(qualification_fixture_id or ""),
                source_file_id=str(qualification_source_file_id or ""),
                source_pdf_bytes=qualification_source_pdf_bytes,
                expected_source_pdf_sha256=str(qualification_source_pdf_sha256 or ""),
                expires_at=expires_at,
            ).review(
                actor_context=artifact_context,
                reviewer=self._qualification_reviewer(__event_call__),
            )
            observed_image_count = review["structural_counts"]["images_count"]
            return {
                "status": "succeeded" if review["status"] == "passed" else "failed",
                "normalization_run_id": artifact_manifest.normalization_run_id,
                "private_full_source_readback": True,
                "private_image_readback_count": observed_image_count,
                "private_artifacts_purged": True,
                "provider_calls_total": 1,
                "review": review,
            }
        if is_terminal_pdf_document_ai_request(
            result.package.get("document_inventory", {}).get("documents", []),
            result.package.get("normalization_blockers", []),
        ):
            self._workload_review_items = 1
            artifact_manifest = persist_gate1_result(
                store=artifact_store,
                result=result,
                context=artifact_context,
                retention_policy=retention_policy,
                source_file_refs=self._source_file_refs(file_refs),
            )
            self.last_safe_report = result.safe_report
            self.last_artifact_manifest = artifact_manifest.to_dict()
            self._finalize_workload_publication(gate2_handoff_status="blocked")
            await self._emit(
                __event_emitter__,
                self._progress_description(
                    safe_metadata,
                    user_message="PDF Document AI is not configured or live-qualified.",
                    internal_message=(
                        "Gate 1 stopped at the PDF Document AI boundary; "
                        "no downstream artifacts were created."
                    ),
                ),
                done=True,
            )
            return render_chat_content(result.safe_report)
        result = await self._run_provider_awaitable(
            self._maybe_run_passport_stage(
                result=result,
                user=__user__,
                request=__request__,
                metadata=safe_metadata,
                body=safe_body,
                event_emitter=__event_emitter__,
            ),
            enabled=bool(self.valves.passport_enabled),
            provider_id="openwebui_completion",
        )
        result = await self._run_provider_awaitable(
            self._maybe_run_clarification_stage(
                result=result,
                user=__user__,
                request=__request__,
                metadata=safe_metadata,
                body=safe_body,
                event_emitter=__event_emitter__,
            ),
            enabled=bool(self.valves.clarification_enabled),
            provider_id="openwebui_completion",
        )
        self._workload_review_items = 0
        self._workload_checkpoint()
        artifact_manifest = persist_gate1_result(
            store=artifact_store,
            result=result,
            context=artifact_context,
            retention_policy=retention_policy,
            source_file_refs=self._source_file_refs(file_refs),
        )
        ndfl_gate3 = await self._run_provider_awaitable(
            self._maybe_run_ndfl_gate3(
                store=artifact_store,
                context=artifact_context,
                artifact_manifest=artifact_manifest,
                user=__user__,
                request=__request__,
                event_emitter=__event_emitter__,
                retention_policy=retention_policy,
                trusted_interaction_message=trusted_interaction_message,
                event_call=__event_call__,
                source_turn=bool(file_refs),
            ),
            enabled=(
                bool(self.valves.ndfl_gate3_enabled)
                and not bool(self.valves.ordinary_trade_candidate_enabled)
            ),
            provider_id=self.valves.ndfl_gate3_provider_profile_id,
        )
        product_result = ndfl_gate3.get("product")
        declaration_result = ndfl_gate3.get("declaration")
        if (
            isinstance(product_result, dict)
            and product_result.get("status") == "DECLARATION_XML_READY"
            and isinstance(declaration_result, dict)
        ):
            file_id = await self._publish_ndfl_xml_file(
                user=__user__,
                context=artifact_context,
                filename="3-ndfl-2025.xml",
                xml_bytes=declaration_result["xml_bytes"],
                xml_sha256=declaration_result["xml_sha256"],
                receipt_sha256=declaration_result["receipt_sha256"],
            )
            product_result["private_download"] = {
                "file_id": file_id,
                "url": f"/api/v1/files/{file_id}/content?attachment=true",
                "content_type": "application/xml",
            }
        self._finalize_workload_publication(
            gate2_handoff_status=str(
                result.package.get("normalization_run", {}).get("gate2_handoff_status")
                or ""
            )
        )
        self.last_safe_report = result.safe_report
        self.last_artifact_manifest = {
            **artifact_manifest.to_dict(),
            "ndfl_gate3": ndfl_gate3,
        }

        if not file_refs:
            await self._emit(
                __event_emitter__,
                self._progress_description(
                    safe_metadata,
                    user_message="Загруженный файл не найден.",
                    internal_message="No uploaded file refs were visible.",
                ),
                done=True,
            )
        else:
            await self._emit(
                __event_emitter__,
                self._progress_description(
                    safe_metadata,
                    user_message="Отчёт обработан, результат сохранён в кейсе.",
                    internal_message=(
                        "Gate 1 artifacts persisted and compact report ready."
                    ),
                ),
                done=True,
            )
        if artifact_context.workspace_model_id == NDFL_WORKSPACE_MODEL_STABLE_ID:
            chat_content = await self._render_ndfl_public_dialogue(
                result=ndfl_gate3,
                user=__user__,
                request=__request__,
            )
        else:
            chat_content = render_chat_content(result.safe_report)
            if ndfl_gate3.get("status") == "completed":
                semantic_status = (
                    "Обычные сделки с ценными бумагами обработаны по "
                    "квалифицированной точной схеме; неизвестные строки сохранены "
                    "без догадок."
                    if ndfl_gate3.get("route_owner")
                    == "ordinary_trade_exact_fingerprint_v1"
                    else (
                        "Финансовые операции из текущей версии документа "
                        "классифицированы без изменения исходных значений."
                    )
                )
                chat_content = "\n".join([chat_content, "", semantic_status])
        if self._live_smoke_requested(safe_body, messages_arg):
            smoke_lines = self._run_live_artifactstore_smoke(
                store=artifact_store,
                result=result,
                context=artifact_context,
                retention_policy=retention_policy,
                manifest=artifact_manifest,
                file_inputs=file_inputs,
                file_refs=file_refs,
                chat_content=chat_content,
            )
            chat_content = "\n".join(
                [
                    chat_content,
                    "",
                    "Проверка ArtifactStore:",
                    *[f"- {line}" for line in smoke_lines],
                ]
            )
        return chat_content

    @staticmethod
    def _ndfl_source_user_content(product: Any) -> str:
        """Keep source-owner diagnostics behind the direct NDFL UI boundary."""

        if not isinstance(product, dict):
            return (
                "Расчёт остановлен: загруженный документ не образует подтверждённый "
                "поддерживаемый набор операций. XML не создан. Проверьте тип и "
                "полноту брокерского отчёта или передайте документ на review."
            )
        return (
            "Источник прочитан и привязан к текущему кейсу. Релевантные "
            "неразобранные строки не используются молча: при их наличии выпуск "
            "XML будет остановлен."
        )

    @staticmethod
    def _ndfl_legacy_route_content() -> str:
        return (
            "Подготовка 3-НДФЛ в этом чате недоступна: он открыт через "
            "устаревшую карточку сервиса. Загруженный файл не использован для "
            "расчёта, XML не создан. Начните новый чат через актуальную карточку "
            "«NDFL». Если она не видна, обратитесь к администратору сервиса."
        )

    async def _maybe_resume_ndfl_chat_turn(
        self,
        *,
        body: dict[str, Any],
        metadata: dict[str, Any],
        user: Any,
        request: Any,
        event_emitter: Any,
        event_call: Any,
        interaction_message: str,
        kwargs: dict[str, Any],
    ) -> str | None:
        """Resume an existing case without re-reading its source document."""

        if (
            not self.valves.ordinary_trade_candidate_enabled
            or not self.valves.canonical_gate2_write_enabled
            or not self.valves.canonical_gate2_read_enabled
            or metadata.get("model_id") != NDFL_WORKSPACE_MODEL_STABLE_ID
            or not interaction_message
            or self._current_turn_has_files(body)
        ):
            return None
        context = self._artifact_context(
            user=user,
            metadata=metadata,
            body=body,
            kwargs=kwargs,
            normalization_run_id=(
                "declaration-chat-"
                + hashlib.sha256(
                    (
                        str(metadata.get("chat_id") or metadata.get("case_id") or "")
                        + "\0"
                        + interaction_message
                    ).encode("utf-8")
                ).hexdigest()[:24]
            ),
        )
        store = self._artifact_store()
        context = self._current_declaration_execution_context(
            store=store,
            context=context,
        )
        result = await self._maybe_run_ndfl_gate3(
            store=store,
            context=context,
            artifact_manifest={},
            user=user,
            request=request,
            event_emitter=event_emitter,
            retention_policy=self._retention_policy(body, metadata),
            trusted_interaction_message=interaction_message,
            event_call=event_call,
        )
        product = result.get("product")
        if (
            not isinstance(product, dict)
            or product.get("terminal") == "ordinary_trade_canonical_evidence_missing"
        ):
            return None
        declaration = result.get("declaration")
        if (
            product.get("status") == "DECLARATION_XML_READY"
            and isinstance(declaration, dict)
        ):
            file_id = await self._publish_ndfl_xml_file(
                user=user,
                context=context,
                filename="3-ndfl-2025.xml",
                xml_bytes=declaration["xml_bytes"],
                xml_sha256=declaration["xml_sha256"],
                receipt_sha256=declaration["receipt_sha256"],
            )
            product["private_download"] = {
                "file_id": file_id,
                "url": f"/api/v1/files/{file_id}/content?attachment=true",
                "content_type": "application/xml",
            }
        content = await self._render_ndfl_public_dialogue(
            result=result,
            user=user,
            request=request,
        )
        self.last_artifact_manifest = {"ndfl_gate3": result, "resumed_case": True}
        return content

    @staticmethod
    def _current_declaration_execution_context(
        *,
        store: Any,
        context: ArtifactAccessContext,
    ) -> ArtifactAccessContext:
        """Bind chat retries to the current source-owner projection set."""

        current = OrdinaryTradeProjectionFactory(
            store=store,
            read_enabled=True,
        ).create().current_case(context=context)
        if not current:
            return context
        owner_run_ids = {record.normalization_run_id for record, _payload in current}
        if len(owner_run_ids) != 1:
            raise NdflWorkflowError(
                "ordinary_trade_current_projection_run_ambiguous"
            )
        return ArtifactAccessContext(
            user_id=context.user_id,
            normalization_run_id=next(iter(owner_run_ids)),
            case_id=context.case_id,
            chat_id=context.chat_id,
            workspace_model_id=context.workspace_model_id,
            allow_private=context.allow_private,
            require_source_available=context.require_source_available,
            source_file_id=context.source_file_id,
        )

    @staticmethod
    def _current_turn_has_files(body: dict[str, Any]) -> bool:
        # OpenWebUI keeps every chat file in top-level ``files`` on later
        # turns.  That collection is case context, not proof that the current
        # user message attached a new source.  Only the owner-produced current
        # message (or the latest message on older transports) may select the
        # intake path instead of resuming the current declaration case.
        current_user = body.get("user_message")
        if isinstance(current_user, dict):
            return bool(
                isinstance(current_user.get("files"), list)
                and current_user["files"]
            )
        messages = body.get("messages")
        if not isinstance(messages, list):
            return False
        latest_user = next(
            (
                item
                for item in reversed(messages)
                if isinstance(item, dict) and item.get("role") == "user"
            ),
            None,
        )
        return bool(
            isinstance(latest_user, dict)
            and isinstance(latest_user.get("files"), list)
            and latest_user["files"]
        )

    async def _adapt_ndfl_public_answer(
        self,
        *,
        message: str,
        current_actions: list[dict[str, Any]],
        product: dict[str, Any],
        declaration: Any,
        user: Any,
        request: Any,
        event_call: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Propose one public interpretation; bind only through the owner."""

        baseline = self._presentation_llm_calls_total
        question = build_public_question_context(current_actions[0])
        dialogue = {
            "schema_version": "broker_reports_ndfl_public_dialogue_turn_v1",
            "answer_feedback": None,
            "interpretation_model_used": False,
            "interpretation_disposition": None,
            "candidate_proposed": False,
            "explicit_confirmation_received": False,
            "presentation_call_already_used": False,
            "presentation_fallback_used": False,
        }
        direct = adapt_current_declaration_request(
            message=message,
            current_requests=current_actions,
        )
        adapted: dict[str, Any]
        if question is None:
            adapted = adapt_current_declaration_request(
                message=message,
                current_requests=current_actions,
            )
            dialogue["presentation_fallback_used"] = True
        elif public_answer_requires_clarification(message):
            adapted = {
                "status": "ANSWER_REJECTED",
                "reason_code": "declaration_chat_answer_delegates_choice",
            }
            dialogue["answer_feedback"] = (
                "Не буду выбирать за вас. Уточните ответ на текущий вопрос "
                "своими словами."
            )
        elif direct.get("status") == "ANSWER_READY":
            adapted = direct
        else:
            interpretation: dict[str, str] | None = None
            if self.valves.ndfl_presentation_llm_enabled:
                try:
                    context = build_public_dialogue_context(
                        product=product,
                        declaration=declaration,
                    )
                    system_content, user_content = (
                        public_dialogue_interpretation_messages(
                            context=context,
                            user_message=message,
                        )
                    )
                    raw = await self._call_openwebui_presentation_completion(
                        system_content=system_content,
                        user_content=user_content,
                        response_format=(
                            public_dialogue_interpretation_response_format()
                        ),
                        user=user,
                        request=request,
                        task="ordinary_trade_public_answer_interpretation",
                    )
                    interpretation = validate_public_dialogue_interpretation(
                        raw,
                        context=context,
                        user_message=message,
                    )
                    dialogue["interpretation_model_used"] = True
                    dialogue["interpretation_disposition"] = interpretation[
                        "disposition"
                    ]
                    dialogue["presentation_call_already_used"] = True
                    dialogue["pre_rendered_context_sha256"] = (
                        public_dialogue_context_sha256(context)
                    )
                    dialogue["pre_rendered_message"] = interpretation["message"]
                except Exception:
                    dialogue["presentation_call_already_used"] = True
                    dialogue["presentation_fallback_used"] = True
            if interpretation is None:
                adapted = {
                    "status": "ANSWER_REJECTED",
                    "reason_code": "declaration_chat_answer_requires_explicit_value",
                }
                dialogue["answer_feedback"] = (
                    "Ответ пока не принят. Укажите один точный вариант для "
                    "текущего вопроса своими словами."
                )
            elif interpretation["disposition"] == "CLARIFY":
                adapted = {
                    "status": "ANSWER_REJECTED",
                    "reason_code": "declaration_chat_answer_requires_clarification",
                }
            else:
                normalized_answer = interpretation["normalized_answer"]
                owner_candidate = adapt_current_declaration_request(
                    message=normalized_answer,
                    current_requests=current_actions,
                )
                conflicts = public_answer_candidate_conflicts_with_explicit_negation(
                    user_message=message,
                    normalized_answer=normalized_answer,
                )
                if owner_candidate.get("status") != "ANSWER_READY" or conflicts:
                    adapted = {
                        "status": "ANSWER_REJECTED",
                        "reason_code": (
                            "declaration_chat_interpretation_conflicts_with_user"
                            if conflicts
                            else "declaration_chat_interpretation_not_owner_accepted"
                        ),
                    }
                    dialogue.pop("pre_rendered_message", None)
                    dialogue["answer_feedback"] = (
                        "Ответ пока не принят. Уточните один вариант без отрицания "
                        "или двусмысленности."
                    )
                else:
                    dialogue["candidate_proposed"] = True
                    confirmed = await self._declaration_candidate_confirmation(
                        event_call=event_call,
                        normalized_answer=normalized_answer,
                        visible_message=interpretation["message"],
                    )
                    if confirmed is True:
                        adapted = owner_candidate
                        dialogue["explicit_confirmation_received"] = True
                        dialogue.pop("pre_rendered_message", None)
                    elif confirmed is False:
                        adapted = {
                            "status": "ANSWER_REJECTED",
                            "reason_code": (
                                "declaration_chat_interpretation_not_confirmed"
                            ),
                        }
                        dialogue.pop("pre_rendered_message", None)
                        dialogue["answer_feedback"] = (
                            "Интерпретация не подтверждена и не сохранена. "
                            "Ответьте на текущий вопрос ещё раз своими словами."
                        )
                    else:
                        adapted = {
                            "status": "ANSWER_CONFIRMATION_REQUIRED",
                            "reason_code": (
                                "declaration_chat_interpretation_confirmation_required"
                            ),
                        }
        if adapted.get("status") == "ANSWER_REJECTED" and not dialogue.get(
            "answer_feedback"
        ) and not dialogue.get("pre_rendered_message"):
            dialogue["answer_feedback"] = (
                "Ответ пока не принят. Уточните его для текущего вопроса."
            )
        dialogue["presentation_llm_calls_total"] = (
            self._presentation_llm_calls_total - baseline
        )
        dialogue["domain_provider_calls_total"] = 0
        return adapted, dialogue

    async def _render_ndfl_public_dialogue(
        self,
        *,
        result: dict[str, Any],
        user: Any,
        request: Any,
    ) -> str:
        product = result.get("product")
        if not isinstance(product, dict):
            return self._ndfl_source_user_content(product)
        existing = result.get("public_dialogue")
        existing = existing if isinstance(existing, dict) else {}
        context = build_public_dialogue_context(
            product=product,
            declaration=result.get("declaration"),
            answer_feedback=existing.get("answer_feedback"),
        )
        fallback_used = bool(existing.get("presentation_fallback_used"))
        model_used = False
        content = ""
        context_sha256 = public_dialogue_context_sha256(context)
        call_already_used = bool(existing.get("presentation_call_already_used"))
        if (
            call_already_used
            and existing.get("pre_rendered_context_sha256") == context_sha256
            and isinstance(existing.get("pre_rendered_message"), str)
        ):
            content = existing["pre_rendered_message"]
            model_used = bool(existing.get("interpretation_model_used"))
        elif call_already_used:
            fallback_used = True
        elif (
            isinstance(context.get("current_question"), dict)
            and context["current_question"].get("authority_kind")
            == "source_choice_confirmation"
        ):
            content = render_public_dialogue_fallback(context)
        elif self.valves.ndfl_presentation_llm_enabled:
            try:
                system_content, user_content = public_dialogue_render_messages(context)
                raw = await self._call_openwebui_presentation_completion(
                    system_content=system_content,
                    user_content=user_content,
                    response_format=public_dialogue_message_response_format(
                        context=context
                    ),
                    user=user,
                    request=request,
                    task="ordinary_trade_public_dialogue_render",
                )
                question = context.get("current_question")
                mapping_verification = None
                if (
                    isinstance(question, dict)
                    and question.get("authority_kind") == "source_choice"
                ):
                    verifier_system, verifier_user = (
                        public_mapping_verification_messages(
                            context=context, draft=raw
                        )
                    )
                    mapping_verification = (
                        await self._call_openwebui_presentation_completion(
                            system_content=verifier_system,
                            user_content=verifier_user,
                            response_format=(
                                public_mapping_verification_response_format()
                            ),
                            user=user,
                            request=request,
                            task="ordinary_trade_public_mapping_verification",
                        )
                    )
                content = validate_public_dialogue_message(
                    raw,
                    context=context,
                    mapping_verification=mapping_verification,
                )
                model_used = True
            except Exception:
                fallback_used = True
        if not content:
            content = render_public_dialogue_fallback(context)
        download = product.get("private_download")
        if (
            context["outcome"]["download_available"] is True
            and isinstance(download, dict)
            and isinstance(download.get("url"), str)
            and download["url"]
        ):
            content = "\n\n".join(
                [content, f"[Скачать приватный XML]({download['url']})"]
            )
        result["public_dialogue"] = {
            **existing,
            "schema_version": "broker_reports_ndfl_public_dialogue_turn_v1",
            "context": context,
            "context_sha256": context_sha256,
            "presentation_model_used": bool(
                model_used or existing.get("interpretation_model_used")
            ),
            "presentation_fallback_used": fallback_used,
            "presentation_llm_calls_total": self._presentation_llm_calls_total,
            "domain_provider_calls_total": int(result.get("provider_calls_total") or 0),
            "visible_message_sha256": hashlib.sha256(
                content.encode("utf-8")
            ).hexdigest(),
        }
        return content

    async def _call_openwebui_presentation_completion(
        self,
        *,
        system_content: str,
        user_content: str,
        response_format: dict[str, Any],
        user: Any,
        request: Any,
        task: str,
    ) -> Any:
        if request is None:
            raise NdflWorkflowError("ndfl_presentation_model_unavailable")
        user_id = self._user_id(user, {})
        model_id = str(self.valves.ndfl_presentation_model_id or "").strip()
        if not user_id or not model_id:
            raise NdflWorkflowError("ndfl_presentation_model_unavailable")
        form_data = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "response_format": response_format,
            "metadata": {
                "broker_reports_gate1": {
                    "presentation_only": True,
                    "task": task,
                }
            },
        }
        self._presentation_llm_calls_total += 1
        try:
            http_target = self._openwebui_presentation_http_target(request)
            if http_target is not None:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._openwebui_presentation_http_completion,
                        target=http_target,
                        form_data=form_data,
                    ),
                    timeout=NDFL_PRESENTATION_COMPLETION_TIMEOUT_SECONDS + 5.0,
                )
                return self._extract_completion_content(response)
            completion_fn, user_model = self._openwebui_completion_dependencies(user_id)
            if inspect.isawaitable(user_model):
                user_model = await user_model
            if user_model is None:
                raise NdflWorkflowError("ndfl_presentation_model_unavailable")
            try:
                response = completion_fn(
                    request=request,
                    form_data=form_data,
                    user=user_model,
                    bypass_filter=True,
                    bypass_system_prompt=True,
                )
            except TypeError:
                try:
                    response = completion_fn(
                        request=request,
                        form_data=form_data,
                        user=user_model,
                    )
                except TypeError:
                    response = completion_fn(request, form_data, user_model)
            if inspect.isawaitable(response):
                response = await asyncio.wait_for(
                    response,
                    timeout=NDFL_PRESENTATION_COMPLETION_TIMEOUT_SECONDS,
                )
            return self._extract_completion_content(response)
        except Exception as exc:
            raise NdflWorkflowError("ndfl_presentation_model_call_failed") from exc

    def _openwebui_presentation_http_target(
        self,
        request: Any,
    ) -> tuple[str, str] | None:
        headers = getattr(request, "headers", None)
        origin = str(
            self.valves.ndfl_presentation_openwebui_origin or ""
        ).strip()
        authorization = (
            str(headers.get("authorization") or "").strip()
            if headers is not None and hasattr(headers, "get")
            else ""
        )
        if not origin:
            return None
        try:
            parsed = urllib.parse.urlsplit(origin)
            port = parsed.port
        except ValueError as exc:
            raise NdflWorkflowError(
                "ndfl_presentation_openwebui_origin_invalid"
            ) from exc
        if (
            parsed.scheme.casefold() != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise NdflWorkflowError("ndfl_presentation_openwebui_origin_invalid")
        if not authorization.startswith("Bearer "):
            raise NdflWorkflowError("ndfl_presentation_bearer_required")
        netloc = parsed.hostname
        if ":" in netloc and not netloc.startswith("["):
            netloc = f"[{netloc}]"
        if port is not None:
            netloc = f"{netloc}:{port}"
        url = urllib.parse.urlunsplit(
            ("https", netloc, "/api/chat/completions", "", "")
        )
        return url, authorization

    @staticmethod
    def _openwebui_presentation_http_completion(
        *,
        target: tuple[str, str],
        form_data: dict[str, Any],
    ) -> dict[str, Any]:
        url, authorization = target
        body = json.dumps(
            form_data,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        outbound = urllib.request.Request(
            url,
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": authorization,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        opener = urllib.request.build_opener(_NdflPresentationNoRedirectHandler())
        with opener.open(
            outbound,
            timeout=NDFL_PRESENTATION_COMPLETION_TIMEOUT_SECONDS,
        ) as response:
            if int(getattr(response, "status", 0) or 0) != 200:
                raise NdflWorkflowError("ndfl_presentation_model_http_failed")
            raw = response.read(NDFL_PRESENTATION_MAX_RESPONSE_BYTES + 1)
            if len(raw) > NDFL_PRESENTATION_MAX_RESPONSE_BYTES:
                raise NdflWorkflowError("ndfl_presentation_model_http_too_large")
            value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise NdflWorkflowError("ndfl_presentation_model_http_invalid")
        return value

    def _standalone_ndfl_chat_content(self, result: dict[str, Any]) -> str:
        product = result.get("product")
        if not isinstance(product, dict):
            return self._ndfl_source_user_content(product)
        existing = result.get("public_dialogue")
        existing = existing if isinstance(existing, dict) else {}
        context = build_public_dialogue_context(
            product=product,
            declaration=result.get("declaration"),
            answer_feedback=existing.get("answer_feedback"),
        )
        content = render_public_dialogue_fallback(context)
        download = product.get("private_download")
        if (
            context["outcome"]["download_available"] is True
            and isinstance(download, dict)
            and isinstance(download.get("url"), str)
            and download["url"]
        ):
            content += f"\n\n[Скачать приватный XML]({download['url']})"
        return content

    async def _maybe_run_ndfl_gate3(
        self,
        *,
        store: Any,
        context: ArtifactAccessContext,
        artifact_manifest: Any,
        user: Any,
        request: Any,
        event_emitter: Any,
        retention_policy: Any | None = None,
        trusted_interaction_message: str = "",
        event_call: Any = None,
        source_turn: bool = False,
    ) -> dict[str, Any]:
        candidate_enabled = bool(self.valves.ordinary_trade_candidate_enabled)
        if not candidate_enabled and not self.valves.ndfl_gate3_enabled:
            return {
                "schema_version": "broker_reports_ndfl_gate3_product_run_v1",
                "enabled": False,
                "status": "disabled",
                "provider_calls_total": 0,
            }
        if context.workspace_model_id != NDFL_WORKSPACE_MODEL_STABLE_ID:
            raise NdflWorkflowError("ndfl_workspace_model_identity_required")
        if (
            not self.valves.canonical_gate2_write_enabled
            or not self.valves.canonical_gate2_read_enabled
        ):
            raise NdflWorkflowError("ndfl_gate2_canonical_lifecycle_disabled")
        refs_by_type = getattr(artifact_manifest, "artifact_refs_by_type", None)
        canonical_refs = (
            list(refs_by_type.get("broker_reports_canonical_artifact_v1") or [])
            if isinstance(refs_by_type, dict)
            else []
        )
        if len(canonical_refs) != len(set(canonical_refs)):
            raise NdflWorkflowError("ndfl_gate2_canonical_artifact_duplicate")
        if candidate_enabled:
            await self._emit(
                event_emitter,
                "Проверяю операции и рассчитываю подтверждённые закрытые сделки…",
                done=False,
            )
            mapping_client = None
            answer_client = None
            if self.valves.ordinary_trade_semantic_mapping_enabled:
                mapping_client = Gate2StructuredModelClientFactory(
                    config=Gate2StructuredModelClientConfig(
                        request_profile=(
                            ORDINARY_TRADE_SEMANTIC_MAPPING_REQUEST_PROFILE
                        ),
                        provider_profile_id=(
                            self.valves.ordinary_trade_mapping_provider_profile_id
                        ),
                        capability_probe=False,
                        economy_budget_enforcement=False,
                    ),
                    user=user,
                    request=request,
                ).create()
                answer_client = Gate2StructuredModelClientFactory(
                    config=Gate2StructuredModelClientConfig(
                        request_profile=(
                            ORDINARY_TRADE_MAPPING_ANSWER_REQUEST_PROFILE
                        ),
                        provider_profile_id=(
                            self.valves.ordinary_trade_mapping_provider_profile_id
                        ),
                        capability_probe=False,
                        economy_budget_enforcement=False,
                    ),
                    user=user,
                    request=request,
                ).create()
            runtime = OrdinaryTradeProductionRuntimeFactory(
                store=store,
                read_enabled=True,
                retention_policy=retention_policy,
                mapping_model_client=mapping_client,
                mapping_answer_model_client=answer_client,
                mapping_model_id=(
                    self.valves.ordinary_trade_mapping_model_id
                    if mapping_client is not None
                    else None
                ),
                mapping_provider_profile_id=(
                    self.valves.ordinary_trade_mapping_provider_profile_id
                    if mapping_client is not None
                    else None
                ),
            ).create()
            action_receipt = None
            result = await runtime.run_with_automatic_mapping(
                canonical_artifact_refs=canonical_refs,
                context=context,
                user_message=(
                    trusted_interaction_message if not source_turn else ""
                ),
            )
            semantic_turn = result.get("semantic_mapping")
            if (
                isinstance(semantic_turn, dict)
                and semantic_turn.get("status") == "CONFIRMATION_REQUIRED"
            ):
                confirmation_value = await self._mapping_candidate_confirmation(
                    event_call=event_call,
                    visible_message=str(
                        (semantic_turn.get("public_state") or {}).get(
                            "confirmation_message"
                        )
                        or ""
                    ),
                )
                if confirmation_value is not None:
                    result = await runtime.run_with_automatic_mapping(
                        canonical_artifact_refs=canonical_refs,
                        context=context,
                        confirmation=confirmation_value,
                        expected_confirmation_artifact_id=str(
                            semantic_turn["mapping_case_artifact_id"]
                        ),
                    )
            preparation = result.get("product", {}).get("preparation")
            preparation = preparation if isinstance(preparation, dict) else {}
            current_actions = preparation.get("user_actions")
            current_actions = (
                current_actions if isinstance(current_actions, list) else []
            )
            change = declaration_change_intent(trusted_interaction_message)
            adapted = None
            dialogue = None
            if change is not None:
                if change["status"] == "ANSWER_REJECTED":
                    adapted = change
                else:
                    request_action = runtime.publish_declaration_change_action(
                        fact_key=change["fact_key"],
                        context=context,
                    )
                    if change["answer"] is None:
                        result = runtime.run(
                            canonical_artifact_refs=canonical_refs,
                            context=context,
                        )
                        result["declaration_chat_receipt"] = {
                            "status": "CHANGE_REQUEST_PUBLISHED",
                            "answer_accepted": False,
                        }
                        return result
                    adapted = {
                        "status": "ANSWER_READY",
                        "request_publication_ref": request_action[
                            "request_publication_ref"
                        ],
                        "answer": change["answer"],
                    }
            elif current_actions:
                # The source workload is already durably published at this point.
                # Human think time belongs to the Human Fact request owner and must
                # not retain the scarce Gate 1 admission lease.
                self._finalize_workload_publication()
                if source_turn or not trusted_interaction_message:
                    return result
                if (
                    trusted_interaction_message.casefold()
                    == "показать точный ввод"
                ):
                    dialogue = {
                        "schema_version": "broker_reports_ndfl_public_dialogue_turn_v1",
                        "answer_feedback": None,
                        "interpretation_model_used": False,
                        "interpretation_disposition": None,
                        "candidate_proposed": False,
                        "explicit_confirmation_received": False,
                        "presentation_call_already_used": False,
                        "presentation_fallback_used": False,
                    }
                    interactive_answer = await self._declaration_event_answer(
                        event_call=event_call,
                        current_actions=current_actions,
                    )
                    adapted = adapt_current_declaration_request(
                        message=interactive_answer,
                        current_requests=current_actions,
                    )
                else:
                    adapted, dialogue = await self._adapt_ndfl_public_answer(
                        message=trusted_interaction_message,
                        current_actions=current_actions,
                        product=result["product"],
                        declaration=result.get("declaration"),
                        user=user,
                        request=request,
                        event_call=event_call,
                    )
                    result["public_dialogue"] = dialogue
            else:
                return result
            if adapted["status"] == "ANSWER_READY":
                try:
                    action_receipt = runtime.normalize_declaration_action(
                        request_publication_ref=adapted["request_publication_ref"],
                        answer=adapted["answer"],
                        context=context,
                    )
                except Gate5HumanGapClosureError as exc:
                    result = runtime.run(
                        canonical_artifact_refs=canonical_refs,
                        context=context,
                    )
                    if isinstance(dialogue, dict):
                        dialogue["answer_feedback"] = (
                            "Ответ не принят и не сохранён. Исправьте значение "
                            "для текущего вопроса."
                        )
                        result["public_dialogue"] = dialogue
                    result["declaration_chat_receipt"] = {
                        "status": "ANSWER_REJECTED",
                        "answer_accepted": False,
                        "reason_code": exc.code,
                    }
                    return result
                result = runtime.run(
                    canonical_artifact_refs=canonical_refs,
                    context=context,
                )
                if isinstance(dialogue, dict):
                    result["public_dialogue"] = dialogue
            elif adapted["status"] == "ANSWER_REJECTED":
                result["declaration_chat_receipt"] = {
                    "status": "ANSWER_REJECTED",
                    "answer_accepted": False,
                    "reason_code": adapted["reason_code"],
                }
            elif adapted["status"] == "ANSWER_CONFIRMATION_REQUIRED":
                result["declaration_chat_receipt"] = {
                    "status": "ANSWER_CONFIRMATION_REQUIRED",
                    "answer_accepted": False,
                    "fact_created": False,
                    "reason_code": adapted["reason_code"],
                }
            if action_receipt is not None:
                result["declaration_action_receipt"] = {
                    "status": action_receipt["status"],
                    "request_id": action_receipt["request_id"],
                    "fact_created": (
                        action_receipt["typed_user_case_fact"] is not None
                    ),
                }
                result["declaration_chat_receipt"] = {
                    "status": "ANSWER_ACCEPTED",
                    "answer_accepted": True,
                    "fact_created": (
                        action_receipt["typed_user_case_fact"] is not None
                    ),
                }
            return result
        if self.valves.ndfl_gate3_provider_profile_id != NDFL_PROVIDER_PROFILE_ID:
            raise NdflWorkflowError("ndfl_provider_profile_binding_mismatch")
        if self.valves.ndfl_gate3_model_id != NDFL_PROVIDER_MODEL_ID:
            raise NdflWorkflowError("ndfl_provider_model_binding_mismatch")

        if not canonical_refs:
            persisted_annotations_artifact_id = (
                self._persisted_gate3_annotations_artifact_id(
                    store=store,
                    context=context,
                )
            )
            if persisted_annotations_artifact_id is not None:
                product = self._run_ndfl_current_pipeline(
                    store=store,
                    context=context,
                )
                return {
                    "schema_version": "broker_reports_ndfl_gate3_product_run_v1",
                    "enabled": True,
                    "status": "completed",
                    "workspace_model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
                    "workflow_id": NDFL_WORKFLOW_STABLE_ID,
                    "binding": ndfl_product_binding_snapshot(),
                    "documents_total": 1,
                    "provider_calls_total": 0,
                    "canonical_version_ids": [],
                    "canonical_root_sha256": [],
                    "annotations_artifact_ids": [persisted_annotations_artifact_id],
                    "gate2_mutation": "none",
                    "persisted_gate3_continuation": True,
                    "private_audit": {
                        "enabled": False,
                        "status": "not_repeated_for_persisted_continuation",
                    },
                    "product": product,
                }
            raise NdflWorkflowError("ndfl_gate2_canonical_artifact_missing")
        await self._emit(
            event_emitter,
            "Проверяю операции текущей версии отчёта…",
            done=False,
        )
        model_client = Gate2StructuredModelClientFactory(
            config=Gate2StructuredModelClientConfig(
                request_profile=GATE3_BOUNDED_LABELING_REQUEST_PROFILE,
                provider_profile_id=NDFL_PROVIDER_PROFILE_ID,
                capability_probe=False,
                economy_budget_enforcement=False,
            ),
            user=user,
            request=request,
        ).create()
        workflow = NdflWorkflowFactory(
            store=store,
            read_enabled=True,
            model_client=model_client,
            model_id=NDFL_PROVIDER_MODEL_ID,
            provider_profile_id=NDFL_PROVIDER_PROFILE_ID,
        ).create()
        executions = []
        for canonical_ref in canonical_refs:
            self._workload_checkpoint()
            executions.append(
                await workflow.run_product_path(
                    canonical_artifact_ref=canonical_ref,
                    context=context,
                )
            )

        audit = self._write_ndfl_private_audit(executions)
        provider_calls_total = self._ndfl_provider_calls_total(executions)
        product = self._run_ndfl_current_pipeline(
            store=store,
            context=context,
        )
        return {
            "schema_version": "broker_reports_ndfl_gate3_product_run_v1",
            "enabled": True,
            "status": "completed",
            "workspace_model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
            "workflow_id": NDFL_WORKFLOW_STABLE_ID,
            "binding": ndfl_product_binding_snapshot(),
            "documents_total": len(executions),
            "provider_calls_total": provider_calls_total,
            "canonical_version_ids": [
                execution.canonical_before_gate3.canonical_version_id
                for execution in executions
            ],
            "canonical_root_sha256": [
                execution.canonical_before_gate3.canonical_root_sha256
                for execution in executions
            ],
            "annotations_artifact_ids": [
                execution.gate3.annotations_artifact_id for execution in executions
            ],
            "gate2_mutation": "none",
            "private_audit": audit,
            "product": product,
        }

    @staticmethod
    def _persisted_gate3_annotations_artifact_id(
        *,
        store: Any,
        context: ArtifactAccessContext,
    ) -> str | None:
        resolver = ArtifactResolver(store)
        candidates = [
            record
            for record in resolver.catalog_run(context)
            if record.artifact_type == GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE
        ]
        if not candidates:
            return None
        if len(candidates) != 1:
            raise NdflWorkflowError("ndfl_gate3_financial_annotations_ambiguous")
        resolver.resolve_record(candidates[0].artifact_id, context)
        return candidates[0].artifact_id

    @staticmethod
    def _ndfl_provider_calls_total(executions: list[Any]) -> int:
        return sum(
            int(
                execution.gate3.batch_result.metrics.get(
                    "financial_labeling_provider_calls", 0
                )
            )
            + int(
                execution.gate3.batch_result.metrics.get(
                    "role_labeling_provider_calls", 0
                )
            )
            for execution in executions
        )

    def _run_ndfl_current_pipeline(
        self,
        *,
        store: Any,
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        taxpayer_scope_ref = _trusted_taxpayer_scope_ref_required()
        financial_case = (
            Gate4FinancialCaseRuntimeFactory(
                store=store,
                read_enabled=True,
            )
            .create()
            .rebuild_case(context=context)
        )
        preparation = (
            Gate5DeclarationPreparationRuntimeFactory(
                store=store,
                read_enabled=True,
            )
            .create()
            .prepare(
                source_fact_methodology_ref={
                    "schema_version": GATE5_TRUSTED_METHODOLOGY_REF_SCHEMA_VERSION,
                    "methodology_id": (GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_ID),
                    "methodology_version": (
                        GATE5_SOURCE_FACT_CONSUMPTION_METHODOLOGY_VERSION
                    ),
                },
                context=context,
                evidence_mode="REAL_EVIDENCE",
                user_intent={
                    "schema_version": GATE5_USER_INTENT_SCHEMA_VERSION,
                    "form": "3-NDFL",
                    "tax_period": "2025",
                    "task": "prepare_tax_declaration",
                    "domains": ["broker_securities_income"],
                },
                taxpayer_scope_ref=taxpayer_scope_ref,
                user_case_facts=[],
            )
        )
        return {
            "schema_version": "broker_reports_current_pipeline_result_v1",
            "status": preparation["status"],
            "terminal": preparation["terminals"][-1],
            "declaration_ready": preparation["declaration_readiness"]["ready"],
            "xml_created": False,
            "pdf_created": False,
            "legacy_fallback_used": False,
            "gate4": {
                "status": financial_case.status,
                "gate3_case_status": financial_case.gate3_case_status,
                "sources_total": len(financial_case.sources),
                "facts_total": len(financial_case.facts),
            },
            "preparation": preparation,
        }

    @staticmethod
    async def _publish_ndfl_xml_file(
        *,
        user: Any,
        context: ArtifactAccessContext,
        filename: str,
        xml_bytes: bytes,
        xml_sha256: str,
        receipt_sha256: str,
    ) -> str:
        if not isinstance(user, dict) or not str(user.get("id") or "").strip():
            raise NdflWorkflowError(
                "ordinary_trade_declaration_authenticated_user_required"
            )
        try:
            from open_webui.models.files import FileForm, Files
            from open_webui.storage.provider import Storage
        except ImportError as exc:
            raise NdflWorkflowError(
                "ordinary_trade_declaration_private_file_boundary_unavailable"
            ) from exc
        if (
            not isinstance(context, ArtifactAccessContext)
            or context.user_id != str(user["id"])
            or not context.case_id
            or re.fullmatch(r"[0-9a-f]{64}", xml_sha256) is None
            or re.fullmatch(r"[0-9a-f]{64}", receipt_sha256) is None
            or hashlib.sha256(xml_bytes).hexdigest() != xml_sha256
        ):
            raise NdflWorkflowError(
                "ordinary_trade_declaration_private_file_binding_invalid"
            )
        case_scope_sha256 = hashlib.sha256(context.case_id.encode("utf-8")).hexdigest()
        file_material = json.dumps(
            {
                "owner": "OpenWebUIFiles",
                "authenticated_user_ref": context.user_id,
                "case_scope_sha256": case_scope_sha256,
                "xml_sha256": xml_sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        publication_identity_sha256 = hashlib.sha256(
            file_material.encode("utf-8")
        ).hexdigest()
        file_id = str(
            uuid.uuid5(
                uuid.UUID("99ab3cab-969f-4c79-bf48-3e7e5030911b"),
                file_material,
            )
        )
        stable_expected_data = {
            "broker_reports_declaration_product": True,
            "private_user_artifact": True,
            "case_scope_sha256": case_scope_sha256,
            "publication_identity_sha256": publication_identity_sha256,
        }
        inserted_data = {
            **stable_expected_data,
            "receipt_sha256": receipt_sha256,
        }

        async def existing_valid() -> str | None:
            getter = getattr(Files, "get_file_by_id", None)
            if not callable(getter):
                raise NdflWorkflowError(
                    "ordinary_trade_declaration_private_file_lookup_unavailable"
                )
            row = await getter(file_id)
            if row is None:
                return None
            meta = getattr(row, "meta", None)
            meta = meta if isinstance(meta, dict) else {}
            data = meta.get("data") if isinstance(meta.get("data"), dict) else {}
            row_path = str(getattr(row, "path", "") or "")
            stored_receipt_sha256 = str(data.get("receipt_sha256") or "")
            if (
                str(getattr(row, "user_id", "") or "") != context.user_id
                or str(getattr(row, "hash", "") or "") != xml_sha256
                or set(data) != {*stable_expected_data, "receipt_sha256"}
                or any(
                    data.get(key) != value
                    for key, value in stable_expected_data.items()
                )
                or re.fullmatch(r"[0-9a-f]{64}", stored_receipt_sha256) is None
                or not row_path
            ):
                raise NdflWorkflowError(
                    "ordinary_trade_declaration_private_file_reuse_binding_invalid"
                )
            try:
                resolved_path = await asyncio.to_thread(
                    Storage.get_file, row_path
                )
                stored_bytes = await asyncio.to_thread(
                    Path(str(resolved_path)).read_bytes
                )
            except Exception as exc:
                raise NdflWorkflowError(
                    "ordinary_trade_declaration_private_file_reuse_unavailable"
                ) from exc
            if hashlib.sha256(stored_bytes).hexdigest() != xml_sha256:
                raise NdflWorkflowError(
                    "ordinary_trade_declaration_private_file_reuse_hash_mismatch"
                )
            return row_path

        if await existing_valid() is not None:
            return file_id
        upload_attempt_id = uuid.uuid4().hex
        contents, file_path = await asyncio.to_thread(
            Storage.upload_file,
            io.BytesIO(xml_bytes),
            f"{file_id}_{upload_attempt_id}_{filename}",
            {
                "OpenWebUI-User-Email": str(user.get("email") or ""),
                "OpenWebUI-User-Id": str(user["id"]),
                "OpenWebUI-User-Name": str(user.get("name") or ""),
                "OpenWebUI-File-Id": file_id,
            },
        )
        if hashlib.sha256(contents).hexdigest() != xml_sha256:
            await Pipe._delete_partial_ndfl_file(Storage=Storage, file_path=file_path)
            raise NdflWorkflowError("ordinary_trade_declaration_private_file_hash_mismatch")
        try:
            file_item = await Files.insert_new_file(
                str(user["id"]),
                FileForm(
                    id=file_id,
                    hash=xml_sha256,
                    filename=filename,
                    path=file_path,
                    data={},
                    meta={
                        "name": filename,
                        "content_type": "application/xml",
                        "size": len(contents),
                        "file_hash": xml_sha256,
                        "data": inserted_data,
                    },
                ),
            )
        except Exception as exc:
            winner_path = await existing_valid()
            if winner_path is not None:
                if winner_path != str(file_path):
                    await Pipe._delete_partial_ndfl_file(
                        Storage=Storage,
                        file_path=file_path,
                    )
                return file_id
            await Pipe._delete_partial_ndfl_file(Storage=Storage, file_path=file_path)
            raise NdflWorkflowError(
                "ordinary_trade_declaration_private_file_record_failed"
            ) from exc
        if file_item is None:
            winner_path = await existing_valid()
            if winner_path is not None:
                if winner_path != str(file_path):
                    await Pipe._delete_partial_ndfl_file(
                        Storage=Storage,
                        file_path=file_path,
                    )
                return file_id
            await Pipe._delete_partial_ndfl_file(Storage=Storage, file_path=file_path)
            raise NdflWorkflowError("ordinary_trade_declaration_private_file_record_failed")
        return file_id

    @staticmethod
    async def _delete_partial_ndfl_file(*, Storage: Any, file_path: str) -> None:
        try:
            await asyncio.to_thread(Storage.delete_file, file_path)
        except Exception as exc:
            raise NdflWorkflowError(
                "ordinary_trade_declaration_private_file_cleanup_failed"
            ) from exc

    @staticmethod
    async def _declaration_event_answer(
        *, event_call: Any, current_actions: list[dict[str, Any]]
    ) -> str:
        """Ask for one answer while the current owner request stays server-bound."""

        if not callable(event_call) or not current_actions:
            return ""
        request_action = current_actions[0]
        if not isinstance(request_action, dict):
            raise NdflWorkflowError(
                "ordinary_trade_declaration_interaction_request_invalid"
            )
        answer_contract = request_action.get("answer_contract")
        if not isinstance(answer_contract, dict):
            raise NdflWorkflowError(
                "ordinary_trade_declaration_interaction_request_invalid"
            )
        question = declaration_request_question(request_action)
        help_text = declaration_request_help(request_action)
        candidate_note = ""
        candidate = answer_contract.get("candidate")
        if isinstance(candidate, dict):
            inn = str(candidate.get("inn") or "")
            if re.fullmatch(r"[0-9]{12}", inn):
                candidate_note = f" Кандидат ИНН: {inn[:4]}••••{inn[-4:]}."
        kind = str(answer_contract.get("kind") or "")
        event_type = "confirmation" if kind == "confirmation" else "input"
        data = {
            "title": "Данные для 3-НДФЛ",
            "message": " ".join(
                part for part in (question, candidate_note.strip(), help_text) if part
            ),
        }
        if event_type == "input":
            data["placeholder"] = help_text
        try:
            value = await event_call({"type": event_type, "data": data})
        except Exception as exc:
            raise NdflWorkflowError(
                "ordinary_trade_declaration_interaction_boundary_failed"
            ) from exc
        if isinstance(value, dict) and value.get("error"):
            raise NdflWorkflowError(
                "ordinary_trade_declaration_interaction_boundary_failed"
            )
        if event_type == "confirmation" and isinstance(value, bool):
            return "Да" if value else "Нет"
        return value if isinstance(value, str) else ""

    @staticmethod
    async def _declaration_candidate_confirmation(
        *, event_call: Any, normalized_answer: str, visible_message: str
    ) -> bool | None:
        """Confirm a presentation-only candidate without publishing it."""

        if not callable(event_call):
            return None
        candidate = str(normalized_answer or "").strip()
        message = str(visible_message or "").strip()
        if (
            not candidate
            or len(candidate) > 2048
            or not message
            or len(message) > 6000
            or candidate.casefold() not in message.casefold()
        ):
            raise NdflWorkflowError(
                "ordinary_trade_declaration_interaction_request_invalid"
            )
        try:
            value = await event_call(
                {
                    "type": "confirmation",
                    "data": {
                        "title": "Подтвердите понимание ответа",
                        "message": message,
                    },
                }
            )
        except Exception as exc:
            raise NdflWorkflowError(
                "ordinary_trade_declaration_interaction_boundary_failed"
            ) from exc
        if isinstance(value, dict) and value.get("error"):
            raise NdflWorkflowError(
                "ordinary_trade_declaration_interaction_boundary_failed"
            )
        return value if isinstance(value, bool) else None

    @staticmethod
    async def _mapping_candidate_confirmation(
        *, event_call: Any, visible_message: str
    ) -> bool | None:
        """Confirm one server-bound semantic understanding without parsing text."""

        if not callable(event_call):
            return None
        message = str(visible_message or "").strip()
        if not message or len(message) > 6000:
            raise NdflWorkflowError(
                "ordinary_trade_mapping_interaction_request_invalid"
            )
        try:
            value = await event_call(
                {
                    "type": "confirmation",
                    "data": {
                        "title": "Подтвердите понимание отчёта",
                        "message": message,
                    },
                }
            )
        except Exception as exc:
            raise NdflWorkflowError(
                "ordinary_trade_mapping_interaction_boundary_failed"
            ) from exc
        if isinstance(value, dict) and value.get("error"):
            raise NdflWorkflowError(
                "ordinary_trade_mapping_interaction_boundary_failed"
            )
        return value if isinstance(value, bool) else None

    def _write_ndfl_private_audit(self, executions: list[Any]) -> dict[str, Any]:
        if not self.valves.ndfl_gate3_private_audit_enabled:
            return {"enabled": False, "status": "disabled"}
        audit_id = str(self.valves.ndfl_gate3_private_audit_id or "").strip()
        if re.fullmatch(r"g3c5_[a-z0-9][a-z0-9_-]{7,63}", audit_id) is None:
            raise NdflWorkflowError("ndfl_private_audit_id_invalid")
        root = Path(self.valves.ndfl_gate3_private_audit_root).resolve()
        audit_dir = (root / audit_id).resolve()
        if audit_dir.parent != root or audit_dir.exists():
            raise NdflWorkflowError("ndfl_private_audit_target_not_new")
        audit_dir.mkdir(parents=True, exist_ok=False)

        files: list[dict[str, Any]] = []
        for document_ordinal, execution in enumerate(executions, start=1):
            attempts = []
            for outcome in execution.gate3.batch_result.outcomes:
                attempt = outcome.attempt
                if attempt is None:
                    raise NdflWorkflowError("ndfl_private_audit_attempt_missing")
                attempts.append(
                    {
                        "chunk": outcome.chunk,
                        "projection": attempt.projection,
                        "dictionary": attempt.dictionary,
                        "dictionary_managed_binding": (
                            attempt.dictionary_managed_binding
                        ),
                        "dictionary_markdown": attempt.dictionary_markdown,
                        "instruction": attempt.instruction,
                        "model_visible_request": attempt.model_visible_request,
                        "final_provider_request": attempt.final_provider_request,
                        "raw_provider_response": attempt.raw_provider_response,
                        "raw_model_output": attempt.raw_model_output,
                        "validated_output": attempt.validated_output,
                        "validation_status": attempt.validation_status,
                        "validation_error_code": attempt.validation_error_code,
                        "execution_metadata": self._ndfl_json_value(
                            attempt.execution_metadata
                        ),
                        "metrics": attempt.metrics,
                        "role_attempt": (
                            {
                                "facts": outcome.role_attempt.facts,
                                "role_context": outcome.role_attempt.role_context,
                                "role_provenance": (
                                    outcome.role_attempt.role_provenance
                                ),
                                "role_pack": outcome.role_attempt.role_pack,
                                "role_pack_markdown": (
                                    outcome.role_attempt.role_pack_markdown
                                ),
                                "instruction": outcome.role_attempt.instruction,
                                "model_visible_request": (
                                    outcome.role_attempt.model_visible_request
                                ),
                                "final_provider_request": (
                                    outcome.role_attempt.final_provider_request
                                ),
                                "raw_provider_response": (
                                    outcome.role_attempt.raw_provider_response
                                ),
                                "raw_model_output": (
                                    outcome.role_attempt.raw_model_output
                                ),
                                "validated_output": (
                                    outcome.role_attempt.validated_output
                                ),
                                "execution_status": (
                                    outcome.role_attempt.execution_status
                                ),
                                "validation_error_code": (
                                    outcome.role_attempt.validation_error_code
                                ),
                                "execution_metadata": self._ndfl_json_value(
                                    outcome.role_attempt.execution_metadata
                                ),
                                "metrics": outcome.role_attempt.metrics,
                            }
                            if outcome.role_attempt is not None
                            else None
                        ),
                    }
                )
            payload = {
                "schema_version": "broker_reports_ndfl_gate3_private_audit_v2",
                "product_binding": ndfl_product_binding_snapshot(),
                "canonical_artifact_ref": execution.canonical_artifact_ref,
                "activation_receipt": (
                    execution.activation_receipt.to_safe_dict()
                    if execution.activation_receipt is not None
                    else None
                ),
                "canonical_before_gate3": self._ndfl_envelope_audit(
                    execution.canonical_before_gate3
                ),
                "attempts": attempts,
                "merged_output": execution.gate3.batch_result.merged_output,
                "financial_annotations_v2": execution.gate3.annotations_payload,
                "annotations_artifact_id": (execution.gate3.annotations_artifact_id),
                "canonical_after_gate3": self._ndfl_envelope_audit(
                    execution.canonical_after_gate3
                ),
            }
            filename = f"document_{document_ordinal:03d}.exact.json"
            encoded = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            ).encode("utf-8")
            (audit_dir / filename).write_bytes(encoded)
            files.append(
                {
                    "filename": filename,
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                    "bytes": len(encoded),
                    "attempts": len(attempts),
                }
            )
        manifest = {
            "schema_version": "broker_reports_ndfl_gate3_private_audit_manifest_v1",
            "audit_id": audit_id,
            "files": files,
            "exact_private_evidence": True,
            "git_tracked": False,
        }
        manifest_bytes = json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
        (audit_dir / "manifest.safe.json").write_bytes(manifest_bytes)
        return {
            "enabled": True,
            "status": "saved",
            "audit_id": audit_id,
            "documents_total": len(files),
            "exact_files_sha256": [item["sha256"] for item in files],
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "private_bytes_in_git": False,
        }

    @classmethod
    def _ndfl_json_value(cls, value: Any) -> Any:
        if is_dataclass(value):
            return cls._ndfl_json_value(asdict(value))
        if isinstance(value, dict):
            return {str(key): cls._ndfl_json_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._ndfl_json_value(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @classmethod
    def _ndfl_envelope_audit(cls, envelope: Any) -> dict[str, Any]:
        return {
            "document_id": envelope.document_id,
            "canonical_version_id": envelope.canonical_version_id,
            "canonical_version_number": envelope.canonical_version_number,
            "version_status": envelope.version_status,
            "schema_version": envelope.schema_version,
            "canonical_root_sha256": envelope.canonical_root_sha256,
            "physical_layout": envelope.physical_layout,
            "component_count": envelope.component_count,
            "payload_bytes": envelope.payload_bytes,
            "artifact": envelope.artifact,
        }

    async def _maybe_run_passport_stage(
        self,
        *,
        result: NormalizationResult,
        user: Any,
        request: Any,
        metadata: dict[str, Any],
        body: dict[str, Any],
        event_emitter: Any,
    ) -> NormalizationResult:
        if not self._passport_enabled(body, metadata):
            return result
        criticality_refinement_enabled = self._criticality_refinement_enabled(
            body, metadata
        )
        await self._emit(
            event_emitter,
            self._progress_description(
                metadata,
                user_message="Проверяю реквизиты документа…",
                internal_message=(
                    "Resolving managed Document Metadata Passport prompt..."
                ),
            ),
            done=False,
        )
        try:
            prompt = self._resolve_passport_prompt(
                user=user, metadata=metadata, body=body
            )
            model_id = self._passport_model_id(body, metadata)
        except DocumentPassportError:
            await self._emit(
                event_emitter,
                self._progress_description(
                    metadata,
                    user_message=(
                        "Автоматическая проверка реквизитов недоступна; "
                        "продолжаю без предположений."
                    ),
                    internal_message=(
                        "Document metadata passport stage unavailable; "
                        "continuing with safe Gate 1 fallback."
                    ),
                ),
                done=False,
            )
            return result
        case_group_id = self._case_group_id(body, metadata)
        llm_packages = build_llm_document_packages(
            package=result.package,
            prompt=prompt,
            model_id=model_id,
            case_group_id=case_group_id,
            max_documents=self._passport_max_documents(body, metadata),
        )
        await self._emit(
            event_emitter,
            self._progress_description(
                metadata,
                user_message="Сверяю реквизиты документа…",
                internal_message=(
                    "Calling OpenWebUI model for document metadata passports..."
                ),
            ),
            done=False,
        )
        raw_outputs = []
        for document_package in llm_packages:
            try:
                completion = await self._openwebui_passport_completion(
                    prompt=prompt,
                    document_package=document_package,
                    model_id=model_id,
                    user=user,
                    request=request,
                )
                output = completion["content"]
                if output is None or (isinstance(output, str) and not output.strip()):
                    raise DocumentPassportError(
                        "passport_model_invalid_response",
                        "Completion response is empty",
                    )
                audit = dict(completion["audit"])
                parsed = parse_document_passport_model_output(output)
                validation = validate_document_metadata_passport(
                    passport=parsed if isinstance(parsed, dict) else {},
                    document_package=document_package,
                    prompt=prompt,
                    model_id=model_id,
                )
                if validation["validator_status"] != "passed":
                    initial_summary = validation_error_summary(validation)
                    repaired = await self._openwebui_passport_repair_completion(
                        prompt=prompt,
                        document_package=document_package,
                        model_id=model_id,
                        user=user,
                        request=request,
                        invalid_output=output,
                        validator_summary=initial_summary,
                        audit=audit,
                    )
                    output = repaired["content"]
                    audit = dict(repaired["audit"])
                raw_outputs.append(
                    {
                        "schema_version": "llm_passport_raw_output_v0",
                        "document_id": document_package["document_id"],
                        "normalization_run_id": document_package[
                            "normalization_run_id"
                        ],
                        "llm_input_package_id": document_package[
                            "llm_input_package_id"
                        ],
                        "model_call_status": "passed",
                        "raw_output": output,
                        "error_code": None,
                        **audit,
                    }
                )
            except DocumentPassportError as exc:
                audit = model_call_audit_metadata(
                    prompt=prompt,
                    model_id=model_id,
                    structured_output_mode="model_call_failed",
                    response_format_type="unknown",
                    response_format_schema_mode=None,
                    schema_attempted=True,
                    native_error_code=exc.code,
                )
                raw_outputs.append(
                    {
                        "schema_version": "llm_passport_raw_output_v0",
                        "document_id": document_package["document_id"],
                        "normalization_run_id": document_package[
                            "normalization_run_id"
                        ],
                        "llm_input_package_id": document_package[
                            "llm_input_package_id"
                        ],
                        "model_call_status": "failed",
                        "raw_output": None,
                        "error_code": exc.code,
                        **audit,
                    }
                )
        applied = apply_document_passport_stage(
            package=result.package,
            prompt=prompt,
            model_id=model_id,
            llm_packages=llm_packages,
            raw_outputs=raw_outputs,
            private_markers=result.private_markers,
            criticality_refinement_enabled=criticality_refinement_enabled,
        )
        await self._emit(
            event_emitter,
            self._progress_description(
                metadata,
                user_message="Реквизиты документа проверены.",
                internal_message="Document metadata passports validated.",
            ),
            done=False,
        )
        return NormalizationResult(
            package=applied["package"],
            safe_report=applied["safe_report"],
            private_markers=result.private_markers,
            bounded_graph=result.bounded_graph,
        )

    async def _maybe_run_clarification_stage(
        self,
        *,
        result: NormalizationResult,
        user: Any,
        request: Any,
        metadata: dict[str, Any],
        body: dict[str, Any],
        event_emitter: Any,
    ) -> NormalizationResult:
        if not self._clarification_enabled(body, metadata):
            return result
        criticality_refinement_enabled = self._criticality_refinement_enabled(
            body, metadata
        )
        await self._emit(
            event_emitter,
            self._progress_description(
                metadata,
                user_message="Проверяю, какие сведения нужно уточнить…",
                internal_message=(
                    "Building deterministic Gate 1 metadata gap report..."
                ),
            ),
            done=False,
        )
        gap_report = build_metadata_gap_report(
            result.package,
            criticality_refinement_enabled=criticality_refinement_enabled,
        )
        if (
            int((gap_report.get("summary") or {}).get("resolvable_gaps_total") or 0)
            == 0
        ):
            applied_gap = apply_metadata_gap_report_stage(
                result.package,
                private_markers=result.private_markers,
                criticality_refinement_enabled=criticality_refinement_enabled,
            )
            return NormalizationResult(
                package=applied_gap["package"],
                safe_report=applied_gap["safe_report"],
                private_markers=result.private_markers,
                bounded_graph=result.bounded_graph,
            )
        try:
            prompt = self._resolve_clarification_prompt(
                user=user, metadata=metadata, body=body
            )
            model_id = self._clarification_model_id(body, metadata)
        except ClarificationError:
            await self._emit(
                event_emitter,
                self._progress_description(
                    metadata,
                    user_message=(
                        "Автоматическое уточнение недоступно; сохраняю только "
                        "подтверждённые сведения."
                    ),
                    internal_message=(
                        "Clarification prompt unavailable; persisting "
                        "deterministic metadata gap report only."
                    ),
                ),
                done=False,
            )
            applied_gap = apply_metadata_gap_report_stage(
                result.package,
                private_markers=result.private_markers,
                criticality_refinement_enabled=criticality_refinement_enabled,
            )
            return NormalizationResult(
                package=applied_gap["package"],
                safe_report=applied_gap["safe_report"],
                private_markers=result.private_markers,
                bounded_graph=result.bounded_graph,
            )
        await self._emit(
            event_emitter,
            self._progress_description(
                metadata,
                user_message="Готовлю уточняющие вопросы по документу…",
                internal_message=(
                    "Calling OpenWebUI model for Gate 1 clarification questions..."
                ),
            ),
            done=False,
        )
        try:
            completion = await self._openwebui_clarification_completion(
                prompt=prompt,
                gap_report=gap_report,
                model_id=model_id,
                user=user,
                request=request,
            )
            raw_output = {
                "schema_version": "llm_clarification_raw_output_v0",
                "normalization_run_id": gap_report["normalization_run_id"],
                "gap_report_id": gap_report["gap_report_id"],
                "model_call_status": "passed",
                "raw_output": completion["content"],
                "error_code": None,
                **completion["audit"],
            }
        except ClarificationError as exc:
            raw_output = {
                "schema_version": "llm_clarification_raw_output_v0",
                "normalization_run_id": gap_report["normalization_run_id"],
                "gap_report_id": gap_report["gap_report_id"],
                "model_call_status": "failed",
                "raw_output": None,
                "error_code": exc.code,
                **clarification_model_call_audit_metadata(
                    prompt=prompt,
                    model_id=model_id,
                    structured_output_mode="model_call_failed",
                    response_format_type="unknown",
                    response_format_schema_mode=None,
                    schema_attempted=True,
                    native_error_code=exc.code,
                ),
            }
        try:
            applied = apply_clarification_request_stage(
                package=result.package,
                prompt=prompt,
                model_id=model_id,
                raw_output=raw_output,
                private_markers=result.private_markers,
                answers=self._clarification_answers(body, metadata),
                answered_by=self._user_id(user, metadata) or "operator",
                answer_source=self._clarification_answer_source(body, metadata),
                criticality_refinement_enabled=criticality_refinement_enabled,
            )
        except ClarificationError:
            applied_gap = apply_metadata_gap_report_stage(
                result.package,
                private_markers=result.private_markers,
                criticality_refinement_enabled=criticality_refinement_enabled,
            )
            return NormalizationResult(
                package=applied_gap["package"],
                safe_report=applied_gap["safe_report"],
                private_markers=result.private_markers,
                bounded_graph=result.bounded_graph,
            )
        await self._emit(
            event_emitter,
            self._progress_description(
                metadata,
                user_message="Уточняющие вопросы по документу готовы.",
                internal_message="Gate 1 clarification questions prepared.",
            ),
            done=False,
        )
        return NormalizationResult(
            package=applied["package"],
            safe_report=applied["safe_report"],
            private_markers=result.private_markers,
            bounded_graph=result.bounded_graph,
        )

    def _resolve_passport_prompt(
        self, *, user: Any, metadata: dict[str, Any], body: dict[str, Any]
    ) -> ManagedPrompt:
        user_context = PromptUserContext(
            user_id=self._user_id(user, metadata),
            user_role=self._user_role(user, metadata),
            user_groups=tuple(self._user_groups(user, metadata)),
        )
        prompt_config = self._passport_prompt_config(body, metadata)
        resolver = DocumentPassportPromptResolverFactory(
            DocumentPassportPromptConfig(
                source="openwebui_sqlite",
                db_path=Path(prompt_config["db_path"]),
                prompt_id=prompt_config["prompt_id"],
                command=prompt_config["command"],
            )
        ).create()
        return resolver.resolve(user_context)

    def _resolve_clarification_prompt(
        self, *, user: Any, metadata: dict[str, Any], body: dict[str, Any]
    ):
        user_context = PromptUserContext(
            user_id=self._user_id(user, metadata),
            user_role=self._user_role(user, metadata),
            user_groups=tuple(self._user_groups(user, metadata)),
        )
        prompt_config = self._clarification_prompt_config(body, metadata)
        resolver = ClarificationPromptResolverFactory(
            ClarificationPromptConfig(
                source="openwebui_sqlite",
                db_path=Path(prompt_config["db_path"]),
                prompt_id=prompt_config["prompt_id"],
                command=prompt_config["command"],
            )
        ).create()
        return resolver.resolve(user_context)

    async def _openwebui_passport_completion(
        self,
        *,
        prompt: ManagedPrompt,
        document_package: dict[str, Any],
        model_id: str,
        user: Any,
        request: Any,
    ) -> dict[str, Any]:
        if request is None:
            raise DocumentPassportError(
                "passport_model_unavailable", "OpenWebUI request object is required"
            )
        user_id = self._user_id(user, {})
        if not user_id:
            raise DocumentPassportError(
                "passport_model_unavailable", "OpenWebUI user id is required"
            )
        package_json = json.dumps(document_package, ensure_ascii=False, sort_keys=True)
        system_content = prompt.content.replace(
            "{{document_package_json}}", package_json
        )
        allowed_evidence_refs = self._passport_allowed_evidence_refs(document_package)
        user_content = (
            "Return the strict document_metadata_passport_v0 JSON object for the package embedded in the managed "
            "prompt. evidence_refs and llm_input_refs must use only these allowed refs: "
            + json.dumps(allowed_evidence_refs, ensure_ascii=False, sort_keys=True)
            if system_content != prompt.content
            else package_json
        )
        native_error_code = None
        attempts = [
            {
                "structured_output_mode": "openwebui_response_format_json_schema",
                "response_format_type": "json_schema",
                "response_format_schema_mode": "strict_json_schema",
                "response_format": passport_json_schema_response_format(),
                "fallback_used": False,
            },
            {
                "structured_output_mode": "openwebui_response_format_json_object_fallback",
                "response_format_type": "json_object",
                "response_format_schema_mode": None,
                "response_format": passport_json_object_response_format(),
                "fallback_used": True,
            },
        ]
        for attempt in attempts:
            try:
                content = await self._call_openwebui_completion(
                    system_content=system_content,
                    user_content=user_content,
                    response_format=attempt["response_format"],
                    structured_output_mode=attempt["structured_output_mode"],
                    prompt=prompt,
                    document_package=document_package,
                    model_id=model_id,
                    user_id=user_id,
                    request=request,
                )
                audit = model_call_audit_metadata(
                    prompt=prompt,
                    model_id=model_id,
                    structured_output_mode=attempt["structured_output_mode"],
                    response_format_type=attempt["response_format_type"],
                    response_format_schema_mode=attempt["response_format_schema_mode"],
                    schema_attempted=True,
                    fallback_used=bool(attempt["fallback_used"]),
                    native_error_code=native_error_code,
                )
                return {"content": content, "audit": audit}
            except DocumentPassportError as exc:
                if attempt["response_format_type"] == "json_schema":
                    native_error_code = exc.code
                    continue
                raise
        raise DocumentPassportError(
            "passport_model_unavailable", "Structured output model call failed"
        )

    async def _openwebui_passport_repair_completion(
        self,
        *,
        prompt: ManagedPrompt,
        document_package: dict[str, Any],
        model_id: str,
        user: Any,
        request: Any,
        invalid_output: Any,
        validator_summary: dict[str, Any],
        audit: dict[str, Any],
    ) -> dict[str, Any]:
        if request is None:
            raise DocumentPassportError(
                "passport_model_unavailable", "OpenWebUI request object is required"
            )
        user_id = self._user_id(user, {})
        if not user_id:
            raise DocumentPassportError(
                "passport_model_unavailable", "OpenWebUI user id is required"
            )
        package_json = json.dumps(document_package, ensure_ascii=False, sort_keys=True)
        system_content = prompt.content.replace(
            "{{document_package_json}}", package_json
        )
        allowed_evidence_refs = self._passport_allowed_evidence_refs(document_package)
        repair_payload = {
            "task": "repair_document_metadata_passport_v0",
            "validator_error_summary": validator_summary,
            "allowed_evidence_refs": allowed_evidence_refs,
            "instruction": (
                "Return one complete document_metadata_passport_v0 JSON object using only the embedded "
                "document package and these validator error codes. evidence_refs and llm_input_refs must be "
                "subsets of allowed_evidence_refs. If validator_error_summary.error_subjects_by_code contains "
                "passport_missing_metadata_not_declared, add those field names to missing_metadata_fields unless "
                "the field can be safely filled from the embedded package. Do not copy raw rows, filenames, file ids, "
                "paths, personal data, account numbers, source facts, tax calculations, declaration fields, or XLS rows."
            ),
        }
        response_format = (
            passport_json_schema_response_format()
            if audit.get("response_format_type") == "json_schema"
            else passport_json_object_response_format()
        )
        content = await self._call_openwebui_completion(
            system_content=system_content,
            user_content=json.dumps(repair_payload, ensure_ascii=False, sort_keys=True),
            response_format=response_format,
            structured_output_mode=str(
                audit.get("structured_output_mode")
                or "openwebui_response_format_json_object_fallback"
            ),
            prompt=prompt,
            document_package=document_package,
            model_id=model_id,
            user_id=user_id,
            request=request,
        )
        repaired_audit = dict(audit)
        repaired_audit["repair_attempted"] = True
        repaired_audit["repair_attempt_count"] = 1
        repaired_audit["validator_error_summary"] = validator_summary
        return {"content": content, "audit": repaired_audit}

    def _passport_allowed_evidence_refs(
        self, document_package: dict[str, Any]
    ) -> list[str]:
        refs = [
            str(ref)
            for ref in document_package.get("evidence_refs") or []
            if ref is not None and str(ref).strip()
        ]
        package_id = document_package.get("llm_input_package_id")
        if package_id:
            refs.append(str(package_id))
        return list(dict.fromkeys(refs))

    async def _openwebui_clarification_completion(
        self,
        *,
        prompt: Any,
        gap_report: dict[str, Any],
        model_id: str,
        user: Any,
        request: Any,
    ) -> dict[str, Any]:
        if request is None:
            raise ClarificationError(
                "clarification_model_unavailable",
                "OpenWebUI request object is required",
            )
        user_id = self._user_id(user, {})
        if not user_id:
            raise ClarificationError(
                "clarification_model_unavailable", "OpenWebUI user id is required"
            )
        gap_report_json = json.dumps(gap_report, ensure_ascii=False, sort_keys=True)
        schema_json = json.dumps(
            clarification_json_schema_response_format()["json_schema"]["schema"],
            ensure_ascii=False,
            sort_keys=True,
        )
        system_content = prompt.content.replace(
            "{{metadata_gap_report_json}}", gap_report_json
        ).replace("{{allowed_answer_schema_json}}", schema_json)
        user_content = json.dumps(
            {
                "task": "write_gate1_clarification_request_v0",
                "metadata_gap_report": gap_report,
                "allowed_schema": clarification_json_schema_response_format()[
                    "json_schema"
                ]["schema"],
                "instruction": (
                    "Return gate1_clarification_request_v0 JSON only. Use exactly the question_id values "
                    "from metadata_gap_report.question_stubs. Preserve criticality, blocking_scope, blocks_gate2, "
                    "resolution_required, can_proceed_with_warning, ask_policy and answer_impact from the stubs. "
                    "Do not add new blockers, do not decide eligibility, "
                    "do not ask for source facts, tax data, trades, operations, dividends, coupons, cashflows, "
                    "declaration fields, XLS rows, raw filenames, file ids, private paths, account numbers or personal data."
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        native_error_code = None
        attempts = [
            {
                "structured_output_mode": "openwebui_response_format_json_schema",
                "response_format_type": "json_schema",
                "response_format_schema_mode": "strict_json_schema",
                "response_format": clarification_json_schema_response_format(),
                "fallback_used": False,
            },
            {
                "structured_output_mode": "openwebui_response_format_json_object_fallback",
                "response_format_type": "json_object",
                "response_format_schema_mode": None,
                "response_format": clarification_json_object_response_format(),
                "fallback_used": True,
            },
        ]
        for attempt in attempts:
            try:
                content = await self._call_openwebui_completion(
                    system_content=system_content,
                    user_content=user_content,
                    response_format=attempt["response_format"],
                    structured_output_mode=attempt["structured_output_mode"],
                    prompt=prompt,
                    document_package={
                        "output_schema": {
                            "output_schema_hash": gate1_clarification_request_schema_hash(),
                        }
                    },
                    model_id=model_id,
                    user_id=user_id,
                    request=request,
                    metadata_task="gate1_clarification_request",
                    output_schema_hash=gate1_clarification_request_schema_hash(),
                )
                try:
                    parse_clarification_request_model_output(content)
                except ClarificationError as exc:
                    if attempt["response_format_type"] == "json_schema":
                        native_error_code = exc.code
                        continue
                    raise
                audit = clarification_model_call_audit_metadata(
                    prompt=prompt,
                    model_id=model_id,
                    structured_output_mode=attempt["structured_output_mode"],
                    response_format_type=attempt["response_format_type"],
                    response_format_schema_mode=attempt["response_format_schema_mode"],
                    schema_attempted=True,
                    fallback_used=bool(attempt["fallback_used"]),
                    native_error_code=native_error_code,
                )
                return {"content": content, "audit": audit}
            except DocumentPassportError as exc:
                if attempt["response_format_type"] == "json_schema":
                    native_error_code = exc.code
                    continue
                raise ClarificationError(
                    "clarification_model_call_failed", exc.code
                ) from exc
        raise ClarificationError(
            "clarification_model_unavailable", "Structured output model call failed"
        )

    async def _call_openwebui_completion(
        self,
        *,
        system_content: str,
        user_content: str,
        response_format: dict[str, Any],
        structured_output_mode: str,
        prompt: Any,
        document_package: dict[str, Any],
        model_id: str,
        user_id: str,
        request: Any,
        metadata_task: str = "document_metadata_passport",
        output_schema_hash: str | None = None,
    ) -> Any:
        form_data = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "response_format": response_format,
            "metadata": {
                "broker_reports_gate1": {
                    metadata_task: True,
                    "structured_output_mode": structured_output_mode,
                    "llm_prompt_ref": prompt.prompt_ref,
                    "llm_prompt_hash": prompt.hash,
                    "output_schema_version": prompt.output_schema_version,
                    "output_schema_hash": output_schema_hash
                    or document_package.get("output_schema", {}).get(
                        "output_schema_hash"
                    ),
                }
            },
        }
        try:
            completion_fn, user_model = self._openwebui_completion_dependencies(user_id)
        except Exception as exc:
            raise DocumentPassportError(
                "passport_model_unavailable", exc.__class__.__name__
            ) from exc
        if inspect.isawaitable(user_model):
            user_model = await user_model
        if user_model is None:
            raise DocumentPassportError(
                "passport_model_unavailable", "OpenWebUI user is unavailable"
            )
        try:
            try:
                response = completion_fn(
                    request=request,
                    form_data=form_data,
                    user=user_model,
                    bypass_filter=True,
                    bypass_system_prompt=True,
                )
            except TypeError:
                try:
                    response = completion_fn(
                        request=request, form_data=form_data, user=user_model
                    )
                except TypeError:
                    response = completion_fn(request, form_data, user_model)
        except Exception as exc:
            raise DocumentPassportError(
                "passport_model_call_failed", exc.__class__.__name__
            ) from exc
        if inspect.isawaitable(response):
            try:
                response = await response
            except Exception as exc:
                raise DocumentPassportError(
                    "passport_model_call_failed", exc.__class__.__name__
                ) from exc
        return self._extract_completion_content(response)

    def _openwebui_completion_dependencies(self, user_id: str):
        try:
            from open_webui.utils.chat import generate_chat_completion as completion_fn
        except Exception:
            from open_webui.main import generate_chat_completions as completion_fn
        from open_webui.models.users import Users

        user_model = Users.get_user_by_id(user_id)
        return completion_fn, user_model

    def _extract_completion_content(self, response: Any) -> Any:
        if isinstance(response, dict):
            return self._completion_dict_content(response)
        body = getattr(response, "body", None)
        if isinstance(body, bytes):
            try:
                return self._completion_dict_content(json.loads(body.decode("utf-8")))
            except (UnicodeDecodeError, ValueError):
                raise DocumentPassportError(
                    "passport_model_invalid_response",
                    "Completion response body is not JSON",
                )
        if isinstance(response, str):
            return response
        raise DocumentPassportError(
            "passport_model_invalid_response", "Unsupported completion response shape"
        )

    def _completion_dict_content(self, payload: dict[str, Any]) -> Any:
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            message = (
                first.get("message") if isinstance(first.get("message"), dict) else {}
            )
            if isinstance(message.get("content"), str) and message.get("content"):
                return message["content"]
            if isinstance(first.get("text"), str) and first.get("text"):
                return first["text"]
        if isinstance(payload.get("content"), str) and payload.get("content"):
            return payload["content"]
        if isinstance(payload.get("response"), str) and payload.get("response"):
            return payload["response"]
        raise DocumentPassportError(
            "passport_model_invalid_response", "Completion response has no content"
        )

    def _passport_model_id(self, body: dict[str, Any], metadata: dict[str, Any]) -> str:
        value = (
            self._passport_config_value(
                body, metadata, "passport_model_id", "llm_model_id"
            )
            or self._passport_nested_config_value(body, metadata, "model_id")
            or self.valves.passport_model_id
        )
        if not value:
            raise DocumentPassportError(
                "passport_model_unavailable", "Passport model id is not configured"
            )
        return str(value)

    def _passport_enabled(self, body: dict[str, Any], metadata: dict[str, Any]) -> bool:
        value = self._passport_config_value(
            body,
            metadata,
            "passport_enabled",
            "enabled",
            "document_metadata_passport_enabled",
        )
        return self._optional_bool(value, default=bool(self.valves.passport_enabled))

    def _passport_prompt_config(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> dict[str, str | None]:
        db_path = (
            self._passport_config_value(
                body, metadata, "passport_prompt_db_path", "prompt_db_path"
            )
            or self.valves.passport_prompt_db_path
        )
        prompt_id = (
            self._passport_config_value(
                body, metadata, "passport_prompt_id", "prompt_id"
            )
            or self.valves.passport_prompt_id
        )
        command = (
            self._passport_config_value(
                body, metadata, "passport_prompt_command", "prompt_command", "command"
            )
            or self.valves.passport_prompt_command
        )
        return {
            "db_path": str(db_path),
            "prompt_id": str(prompt_id).strip() or None,
            "command": str(command).strip() or None,
        }

    def _passport_max_documents(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> int | None:
        value = self._passport_config_value(
            body, metadata, "passport_max_documents", "max_documents"
        )
        limit = self._optional_int(value)
        if limit is None:
            limit = self.valves.passport_max_documents
        return limit if limit > 0 else None

    def _passport_config_value(
        self, body: dict[str, Any], metadata: dict[str, Any], *keys: str
    ) -> Any:
        for context in self._passport_contexts(body, metadata):
            for key in keys:
                if key in context and context.get(key) not in (None, ""):
                    return context.get(key)
        return self._passport_message_config_value(body, *keys)

    def _passport_nested_config_value(
        self, body: dict[str, Any], metadata: dict[str, Any], *keys: str
    ) -> Any:
        for context in self._passport_nested_contexts(body, metadata):
            for key in keys:
                if key in context and context.get(key) not in (None, ""):
                    return context.get(key)
        return None

    def _passport_message_config_value(self, body: dict[str, Any], *keys: str) -> Any:
        messages = body.get("messages")
        if not isinstance(messages, list):
            return None
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = str(message.get("content") or "")
            if "broker_reports_gate1_passport" not in content:
                continue
            for key in keys:
                match = re.search(rf"\b{re.escape(key)}\s*=\s*([^\s,;]+)", content)
                if match:
                    return match.group(1).strip()
        return None

    def _passport_contexts(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> list[dict[str, Any]]:
        contexts: list[dict[str, Any]] = []
        body_metadata = (
            body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        )
        for source in (metadata, body, body_metadata):
            if not isinstance(source, dict):
                continue
            broker_context = source.get("broker_reports_gate1")
            if isinstance(broker_context, dict):
                nested = broker_context.get("document_metadata_passport")
                if isinstance(nested, dict):
                    contexts.append(nested)
                contexts.append(broker_context)
            direct = source.get("document_metadata_passport")
            if isinstance(direct, dict):
                contexts.append(direct)
            contexts.append(source)
        return contexts

    def _passport_nested_contexts(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> list[dict[str, Any]]:
        contexts: list[dict[str, Any]] = []
        body_metadata = (
            body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        )
        for source in (metadata, body, body_metadata):
            if not isinstance(source, dict):
                continue
            broker_context = source.get("broker_reports_gate1")
            if isinstance(broker_context, dict):
                nested = broker_context.get("document_metadata_passport")
                if isinstance(nested, dict):
                    contexts.append(nested)
                contexts.append(broker_context)
            direct = source.get("document_metadata_passport")
            if isinstance(direct, dict):
                contexts.append(direct)
        return contexts

    def _clarification_enabled(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> bool:
        value = self._clarification_config_value(
            body,
            metadata,
            "clarification_enabled",
            "enabled",
            "metadata_clarification_enabled",
        )
        return self._optional_bool(
            value, default=bool(self.valves.clarification_enabled)
        )

    def _criticality_refinement_enabled(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> bool:
        value = self._clarification_config_value(
            body,
            metadata,
            "clarification_criticality_refinement_enabled",
            "criticality_refinement_enabled",
            "metadata_criticality_refinement_enabled",
        )
        return self._optional_bool(
            value,
            default=bool(self.valves.clarification_criticality_refinement_enabled),
        )

    def _clarification_model_id(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> str:
        value = (
            self._clarification_config_value(
                body, metadata, "clarification_model_id", "llm_model_id"
            )
            or self._clarification_nested_config_value(body, metadata, "model_id")
            or self.valves.clarification_model_id
        )
        if not value:
            try:
                value = self._passport_model_id(body, metadata)
            except DocumentPassportError:
                value = None
        if not value:
            raise ClarificationError(
                "clarification_model_unavailable",
                "Clarification model id is not configured",
            )
        return str(value)

    def _clarification_prompt_config(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> dict[str, str | None]:
        db_path = (
            self._clarification_config_value(
                body, metadata, "clarification_prompt_db_path", "prompt_db_path"
            )
            or self.valves.clarification_prompt_db_path
        )
        prompt_id = (
            self._clarification_config_value(
                body, metadata, "clarification_prompt_id", "prompt_id"
            )
            or self.valves.clarification_prompt_id
        )
        command = (
            self._clarification_config_value(
                body,
                metadata,
                "clarification_prompt_command",
                "prompt_command",
                "command",
            )
            or self.valves.clarification_prompt_command
        )
        return {
            "db_path": str(db_path),
            "prompt_id": str(prompt_id).strip() or None,
            "command": str(command).strip() or None,
        }

    def _clarification_answers(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> list[dict[str, Any]]:
        for context in self._clarification_contexts(body, metadata):
            answers = context.get("answers")
            if isinstance(answers, list):
                return [item for item in answers if isinstance(item, dict)]
            direct = context.get("gate1_clarification_answers")
            if isinstance(direct, list):
                return [item for item in direct if isinstance(item, dict)]
        return []

    def _clarification_answer_source(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> str:
        value = self._clarification_config_value(
            body, metadata, "answer_source", "source"
        )
        return str(value or "operator_confirmed")

    def _clarification_config_value(
        self, body: dict[str, Any], metadata: dict[str, Any], *keys: str
    ) -> Any:
        for context in self._clarification_contexts(body, metadata):
            for key in keys:
                if key in context and context.get(key) not in (None, ""):
                    return context.get(key)
        return self._clarification_message_config_value(body, *keys)

    def _clarification_nested_config_value(
        self, body: dict[str, Any], metadata: dict[str, Any], *keys: str
    ) -> Any:
        body_metadata = (
            body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        )
        for source in (metadata, body, body_metadata):
            if not isinstance(source, dict):
                continue
            broker_context = source.get("broker_reports_gate1")
            if isinstance(broker_context, dict):
                nested = broker_context.get("clarification")
                if isinstance(nested, dict):
                    for key in keys:
                        if key in nested and nested.get(key) not in (None, ""):
                            return nested.get(key)
            direct = source.get("gate1_clarification")
            if isinstance(direct, dict):
                for key in keys:
                    if key in direct and direct.get(key) not in (None, ""):
                        return direct.get(key)
        return None

    def _clarification_contexts(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> list[dict[str, Any]]:
        contexts: list[dict[str, Any]] = []
        body_metadata = (
            body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        )
        for source in (metadata, body, body_metadata):
            if not isinstance(source, dict):
                continue
            broker_context = source.get("broker_reports_gate1")
            if isinstance(broker_context, dict):
                nested = broker_context.get("clarification")
                if isinstance(nested, dict):
                    contexts.append(nested)
                contexts.append(broker_context)
            direct = source.get("gate1_clarification")
            if isinstance(direct, dict):
                contexts.append(direct)
            contexts.append(source)
        return contexts

    def _clarification_message_config_value(
        self, body: dict[str, Any], *keys: str
    ) -> Any:
        messages = body.get("messages")
        if not isinstance(messages, list):
            return None
        for message in messages:
            if not isinstance(message, dict):
                continue
            content = str(message.get("content") or "")
            if "broker_reports_gate1_clarification" not in content:
                continue
            for key in keys:
                match = re.search(rf"\b{re.escape(key)}\s*=\s*([^\s,;]+)", content)
                if match:
                    return match.group(1).strip()
        return None

    def _case_group_id(
        self, body: dict[str, Any], metadata: dict[str, Any]
    ) -> str | None:
        body_metadata = (
            body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        )
        contexts = [
            body.get("broker_reports_gate1")
            if isinstance(body.get("broker_reports_gate1"), dict)
            else {},
            metadata.get("broker_reports_gate1")
            if isinstance(metadata.get("broker_reports_gate1"), dict)
            else {},
            body_metadata.get("broker_reports_gate1")
            if isinstance(body_metadata.get("broker_reports_gate1"), dict)
            else {},
            body,
            metadata,
            body_metadata,
        ]
        for context in contexts:
            value = context.get("case_group_id") if isinstance(context, dict) else None
            if value:
                return str(value)
        return None

    def _retention_policy(self, body: dict, metadata: dict):
        override = self._retention_policy_override(body, metadata)
        mode = str(override.get("mode") or self.valves.artifact_retention_mode)
        explicit = self._optional_bool(
            override.get("explicit"),
            default=bool(self.valves.artifact_retention_explicit),
        )
        ttl_seconds = self._optional_int(override.get("ttl_seconds"))
        if ttl_seconds is None:
            ttl_seconds = self.valves.artifact_retention_ttl_seconds
        return build_retention_policy(
            mode=mode,
            explicit=explicit,
            ttl_seconds=ttl_seconds,
        )

    def _retention_policy_override(self, body: dict, metadata: dict) -> dict[str, Any]:
        body_metadata = (
            body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        )
        candidates = [
            metadata.get("retention_policy"),
            self._nested_retention_policy(metadata),
            body.get("retention_policy"),
            self._nested_retention_policy(body),
            body_metadata.get("retention_policy"),
            self._nested_retention_policy(body_metadata),
        ]
        for candidate in candidates:
            if isinstance(candidate, dict):
                return candidate
        return {}

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
                poll_interval_seconds=float(self.valves.workload_poll_interval_seconds),
            )
        ).create()

    def _workload_checkpoint(self) -> None:
        if self._active_workload_session is not None:
            self._active_workload_session.checkpoint()

    def _workload_progress(self, state: str, detail: dict[str, Any]) -> None:
        if self._active_workload_session is not None:
            self.last_workload_snapshot = self._active_workload_session.transition(
                WorkloadState(state),
                event_code=f"{state}_started",
                safe_detail=detail,
            )

    def _provider_slot_if_enabled(
        self,
        enabled: bool,
        provider_id: str,
        *,
        resume_state: WorkloadState = WorkloadState.VALIDATING,
    ):
        if not enabled or self._active_workload_session is None:
            return nullcontext()
        return self._active_workload_session.provider_slot(
            str(provider_id),
            resume_state=resume_state,
        )

    async def _run_provider_awaitable(
        self,
        awaitable,
        *,
        enabled: bool,
        provider_id: str,
    ):
        if not enabled or self._active_workload_session is None:
            return await awaitable
        try:
            async with self._active_workload_session.provider_slot_async(
                provider_id,
                resume_state=WorkloadState.VALIDATING,
            ):
                return await awaitable
        except BaseException:
            if inspect.iscoroutine(awaitable):
                awaitable.close()
            raise

    def _finalize_workload_publication(
        self,
        *,
        gate2_handoff_status: str | None = None,
    ) -> None:
        session = self._active_workload_session
        if session is None or session.terminal:
            return
        if self._workload_review_items:
            safe_detail = {
                "review_items": self._workload_review_items,
                "gate2_handoff_status": str(gate2_handoff_status or "unknown"),
            }
            if gate2_handoff_status in _GATE2_USABLE_HANDOFF_STATUSES:
                self.last_workload_snapshot = session.complete(
                    terminal_code=_COMPLETED_WITH_REVIEW_ADVISORY,
                    safe_detail={
                        **safe_detail,
                        "canonical_publication": True,
                        "review_advisory_preserved": True,
                        "partial_success_published": False,
                    },
                )
            else:
                self.last_workload_snapshot = session.await_review(
                    safe_detail={
                        **safe_detail,
                        "canonical_publication": False,
                    }
                )
        else:
            self.last_workload_snapshot = session.complete(
                safe_detail={"partial_success_published": False}
            )

    async def _emit_workload_snapshot(
        self,
        emitter,
        snapshot: dict[str, Any] | None,
        *,
        done: bool,
        hide_internal: bool = False,
    ) -> None:
        if not snapshot:
            return
        if hide_internal:
            description = (
                "Подготовка 3-НДФЛ: обработка завершена."
                if done
                else "Подготовка 3-НДФЛ: источник обрабатывается."
            )
        else:
            description = (
                f"Broker Reports job {snapshot['job_id']} state: {snapshot['state']}"
            )
            if snapshot.get("queue_position") is not None:
                description += f" (queue {snapshot['queue_position']})"
            if snapshot.get("provider_queue_position") is not None:
                description += (
                    f" (provider queue {snapshot['provider_queue_position']})"
                )
        await self._emit(emitter, description, done=done)

    @staticmethod
    def _progress_description(
        metadata: dict[str, Any], *, user_message: str, internal_message: str
    ) -> str:
        if metadata.get("model_id") == NDFL_WORKSPACE_MODEL_STABLE_ID:
            return user_message
        return internal_message

    @staticmethod
    def _workload_failure_code(exc: BaseException) -> str:
        raw = str(getattr(exc, "code", "") or exc.__class__.__name__).lower()
        normalized = re.sub(r"[^a-z0-9_.:-]+", "_", raw).strip("_")
        return (normalized or "operation_failed")[:128]

    @staticmethod
    def _workload_failure_detail(
        exc: BaseException,
    ) -> dict[str, Any] | None:
        value = getattr(exc, "safe_details", None)
        return copy.deepcopy(value) if isinstance(value, dict) and value else None

    async def _emit(self, emitter, description: str, *, done: bool) -> None:
        if emitter is None:
            return
        await emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done, "hidden": False},
            }
        )

    def _live_smoke_requested(self, body: dict, messages_arg: Any) -> bool:
        text_parts = []
        for message in self._message_iter(body.get("messages")):
            if isinstance(message, dict):
                text_parts.append(str(message.get("content") or ""))
        for message in self._message_iter(messages_arg):
            if isinstance(message, dict):
                text_parts.append(str(message.get("content") or ""))
        text = "\n".join(text_parts).lower()
        return any(
            phrase.strip().lower() in text
            for phrase in str(self.valves.live_smoke_trigger_phrases or "").split(",")
            if phrase.strip()
        )

    def _run_live_artifactstore_smoke(
        self,
        *,
        store,
        result,
        context: ArtifactAccessContext,
        retention_policy,
        manifest,
        file_inputs: list[FileInput],
        file_refs: list[dict[str, Any]],
        chat_content: str,
    ) -> list[str]:
        if not context.case_id:
            raise RuntimeError("case_context_missing_for_wrong_case_resolver_proof")
        records = store.list_by_run(context.normalization_run_id)
        type_counts = self._artifact_type_counts(records)
        private_slice_types = {
            (
                "private_normalized_table_slice_v0"
                if item.get("slice_type") == "table_rows"
                else "private_normalized_text_slice_v0"
            )
            for item in result.package.get("private_normalized_slices", [])
            if isinstance(item, dict)
        }
        required_types = {
            "normalization_run_v0",
            "document_inventory_v0",
            "technical_readability_profile_v0",
            "taxonomy_candidates_v0",
            "normalization_blockers_v0",
            "document_source_eligibility_v0",
            "validation_result_v0",
            "chat_visible_normalization_report_v0",
            "gate2_handoff_v0",
            "source_file_ref_v0",
        } | private_slice_types
        missing = sorted(required_types - set(type_counts))
        if missing:
            raise RuntimeError(f"artifact_type_missing:{missing[0]}")
        private_records = [
            record for record in records if record.visibility == "private_case"
        ]
        if not private_records or not manifest.private_slice_refs:
            raise RuntimeError("private_slice_artifacts_missing")
        if not all(
            record.payload_ref and record.payload is None for record in private_records
        ):
            raise RuntimeError("private_payload_storage_invalid")
        private_payload_paths = [
            self._payload_path(record.payload_ref)
            for record in private_records
            if record.payload_ref
        ]
        if not all(path.exists() for path in private_payload_paths):
            raise RuntimeError("private_payload_file_missing")

        private_markers = self._private_markers(file_refs)
        if any(marker and marker in chat_content for marker in private_markers):
            raise RuntimeError("chat_private_marker_leak")
        if "private_normalized_slices" in chat_content or "```json" in chat_content:
            raise RuntimeError("chat_full_json_or_private_slice_leak")
        if any(record.storage_backend == "openwebui_knowledge" for record in records):
            raise RuntimeError("knowledge_storage_forbidden_bypassed")
        if result.safe_report["safety_flags"]["customer_docs_loaded_to_knowledge"]:
            raise RuntimeError("customer_docs_loaded_to_knowledge_true")

        resolver = ArtifactResolver(store)
        resolver.resolve(manifest.safe_refs[0], context)
        resolver.resolve(manifest.private_slice_refs[0], context)
        self._assert_resolver_denies(
            resolver,
            manifest.safe_refs[0],
            ArtifactAccessContext(**{**context.__dict__, "user_id": "wrong-user"}),
            "artifact_access_denied",
        )
        self._assert_resolver_denies(
            resolver,
            manifest.safe_refs[0],
            ArtifactAccessContext(**{**context.__dict__, "case_id": "wrong-case"}),
            "artifact_access_denied",
        )

        handoff_record = store.get_record_unchecked(manifest.gate2_handoff_ref)
        if handoff_record is None:
            raise RuntimeError("gate2_handoff_missing")
        if (
            handoff_record.validation_status == "blocked"
            or handoff_record.lifecycle_status == "blocked"
        ):
            self._assert_resolver_denies(
                resolver,
                manifest.gate2_handoff_ref,
                context,
                "artifact_blocked",
            )
            handoff = store.read_payload(handoff_record)
        else:
            handoff = resolver.resolve(manifest.gate2_handoff_ref, context)["payload"]
        handoff_private_refs = [
            str(ref) for ref in handoff.get("private_slice_refs") or [] if ref
        ]
        manifest_private_refs = {str(ref) for ref in manifest.private_slice_refs}
        if handoff.get("handoff_status") == "blocked":
            if handoff_private_refs:
                raise RuntimeError("blocked_gate2_handoff_private_refs_present")
        else:
            if not handoff_private_refs:
                raise RuntimeError("gate2_handoff_private_refs_missing")
            if any(
                private_ref not in manifest_private_refs
                for private_ref in handoff_private_refs
            ):
                raise RuntimeError("gate2_handoff_private_refs_missing")
            for private_ref in handoff_private_refs:
                resolver.resolve(private_ref, context)
        clarification_refs = [
            str(ref)
            for ref in handoff.get("clarification_resolution_refs") or []
            if ref
        ]
        if any(
            private_ref not in manifest_private_refs
            for private_ref in clarification_refs
        ):
            raise RuntimeError("gate2_handoff_clarification_refs_missing")
        for private_ref in clarification_refs:
            resolver.resolve(private_ref, context)
        if "```json" in str(handoff) or any(
            marker and marker in str(handoff) for marker in private_markers
        ):
            raise RuntimeError("gate2_handoff_private_marker_leak")

        probe_result = self._normalizer.normalize(
            file_inputs,
            entrypoint="broker_reports_gate1_live_retention_probe",
            trigger_type="live_retention_smoke_probe",
            input_context={"smoke_probe": "retention"},
            extra_private_markers=private_markers,
        )
        probe_context = ArtifactAccessContext(
            user_id=context.user_id,
            normalization_run_id=probe_result.package["normalization_run"]["run_id"],
            case_id=f"{context.case_id}-retention-probe",
            chat_id=context.chat_id,
            workspace_model_id=context.workspace_model_id,
            allow_private=True,
        )
        probe_manifest = persist_gate1_result(
            store=store,
            result=probe_result,
            context=probe_context,
            retention_policy=build_retention_policy(
                mode="expires_after_ttl",
                explicit=True,
                ttl_seconds=1,
            ),
            source_file_refs=self._source_file_refs(file_refs),
        )
        store.expire_run(
            probe_context,
            now=datetime.now(timezone.utc) + timedelta(seconds=2),
        )
        self._assert_resolver_denies(
            resolver,
            probe_manifest.safe_refs[0],
            probe_context,
            "artifact_expired",
        )
        purge_private_ref = probe_manifest.private_slice_refs[0]
        purge_private_record = store.get_record_unchecked(purge_private_ref)
        if purge_private_record is None or not purge_private_record.payload_ref:
            raise RuntimeError("purge_probe_private_payload_missing")
        purge_payload_path = self._payload_path(purge_private_record.payload_ref)
        if not purge_payload_path.exists():
            raise RuntimeError("purge_probe_payload_file_missing")
        purge_result = store.purge_run(probe_context)
        purged_private_record = store.get_record_unchecked(purge_private_ref)
        if (
            purge_result.status != "changed"
            or purge_payload_path.exists()
            or purged_private_record is None
        ):
            raise RuntimeError("purge_probe_failed")
        if (
            purged_private_record.storage_backend != "none_tombstone"
            or purged_private_record.payload_ref
        ):
            raise RuntimeError("purge_tombstone_invalid")
        self._assert_resolver_denies(
            resolver,
            purge_private_ref,
            probe_context,
            "artifact_purged",
        )

        try:
            build_retention_policy(mode="customer_approved_test", explicit=False)
        except RetentionPolicyError as exc:
            if exc.code != "retention_policy_missing":
                raise
        else:
            raise RuntimeError("customer_approved_test_missing_policy_accepted")

        flags = result.safe_report["safety_flags"]
        if any(
            flags[key]
            for key in (
                "source_fact_extraction_performed",
                "tax_correctness_claimed",
                "declaration_generated",
                "xlsx_generated",
                "ocr_performed",
            )
        ):
            raise RuntimeError("forbidden_gate1_flag_true")

        return [
            "хранилище доступно для записи: да",
            (
                "retention policy: "
                f"mode={retention_policy.mode}, explicit={retention_policy.explicit}, "
                f"ttl_seconds={retention_policy.ttl_seconds}"
            ),
            "обязательные артефакты сохранены: " + ", ".join(sorted(required_types)),
            "private slices в chat: нет",
            "private slices в Knowledge: нет",
            "customer_docs_loaded_to_knowledge=false",
            "Gate 2 handoff использует opaque refs, не chat JSON",
            "resolver same-context: allow",
            "resolver denies wrong-user/wrong-case/expired/purged: ok",
            "purge удалил private payloads и оставил tombstones",
            "source facts/tax/declaration/xlsx/ocr flags=false",
        ]

    def _artifact_type_counts(self, records) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in records:
            counts[record.artifact_type] = counts.get(record.artifact_type, 0) + 1
        return counts

    def _assert_resolver_denies(
        self,
        resolver: ArtifactResolver,
        artifact_id: str,
        context: ArtifactAccessContext,
        expected_code: str,
    ) -> None:
        try:
            resolver.resolve(artifact_id, context)
        except ArtifactStoreError as exc:
            if exc.code == expected_code:
                return
            raise
        raise RuntimeError(f"resolver_expected_denial_missing:{expected_code}")

    def _payload_path(self, payload_ref: str) -> Path:
        return Path(self.valves.artifact_payload_root) / payload_ref

    def _has_trigger_phrase(self, body: dict, messages_arg: Any) -> bool:
        text_parts = []
        for message in self._message_iter(body.get("messages")):
            if isinstance(message, dict):
                text_parts.append(str(message.get("content") or ""))
        for message in self._message_iter(messages_arg):
            if isinstance(message, dict):
                text_parts.append(str(message.get("content") or ""))
        text = "\n".join(text_parts).lower()
        return any(
            phrase.strip().lower() in text
            for phrase in str(self.valves.trigger_phrases or "").split(",")
            if phrase.strip()
        )

    def _collect_file_refs(
        self,
        body: dict,
        metadata: dict,
        files_arg: Any,
        messages_arg: Any = None,
    ) -> list[dict[str, Any]]:
        candidates: list[Any] = []
        for source in (files_arg, metadata.get("files"), body.get("files")):
            self._append_file_candidates(candidates, source)
        for source in (
            body.get("message"),
            body.get("messages"),
            metadata.get("message"),
            metadata.get("messages"),
            messages_arg,
        ):
            self._append_message_file_candidates(candidates, source)

        refs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in candidates:
            file_obj = self._file_obj(item)
            if not isinstance(file_obj, dict):
                continue
            file_id = self._file_id(file_obj)
            filename = self._filename(file_obj)
            mime_type = self._mime_type(file_obj)
            if not file_id:
                continue
            stable_key = str(file_id)
            if stable_key in seen:
                continue
            seen.add(stable_key)
            refs.append(
                {
                    "file_id": stable_key,
                    "filename": filename,
                    "extension": extension_from_name(filename, mime_type),
                    "mime_type": mime_type,
                    "size_bytes": self._optional_int(
                        file_obj.get("size") or file_obj.get("size_bytes")
                    ),
                    "_private_file_obj": file_obj,
                }
            )
        return refs

    def _append_file_candidates(self, candidates: list[Any], source: Any) -> None:
        if isinstance(source, list):
            candidates.extend(source)
        elif isinstance(source, dict):
            candidates.append(source)

    def _append_message_file_candidates(
        self, candidates: list[Any], source: Any
    ) -> None:
        for message in self._message_iter(source):
            if isinstance(message, dict):
                self._append_file_candidates(candidates, message.get("files"))
                self._append_nested_file_candidates(candidates, message, depth=0)

    def _append_nested_file_candidates(
        self,
        candidates: list[Any],
        value: Any,
        *,
        depth: int,
    ) -> None:
        if depth > 4:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "files":
                    self._append_file_candidates(candidates, child)
                    continue
                if key in {"content", "text"}:
                    continue
                self._append_nested_file_candidates(candidates, child, depth=depth + 1)
            return
        if isinstance(value, list):
            for item in value:
                self._append_nested_file_candidates(candidates, item, depth=depth + 1)

    def _message_iter(self, source: Any) -> list[Any]:
        if isinstance(source, list):
            return source
        if isinstance(source, dict):
            return [source]
        return []

    def _latest_user_message(self, body: dict, messages_arg: Any) -> str:
        structured = self._find_structured_case_fact_message(
            (body, messages_arg),
            depth=0,
        )
        if structured:
            return structured
        messages: list[str] = []
        for source in (
            body.get("message"),
            body.get("messages"),
            messages_arg,
        ):
            for item in self._message_iter(source):
                if not isinstance(item, dict) or item.get("role") in {
                    "assistant",
                    "system",
                    "tool",
                }:
                    continue
                content_value = item.get("content")
                text = self._message_text(
                    content_value
                    if content_value is not None and content_value != ""
                    else item.get("text")
                )
                if text:
                    messages.append(text)
        if messages:
            return messages[-1]
        for key in ("prompt", "query", "content", "text"):
            text = self._message_text(body.get(key))
            if text:
                return text
        return ""

    @classmethod
    def _find_structured_case_fact_message(
        cls,
        value: Any,
        *,
        depth: int,
    ) -> str:
        if depth > 8:
            return ""
        if isinstance(value, str):
            return value if "3-НДФЛ факты:" in value else ""
        if isinstance(value, dict):
            for item in value.values():
                found = cls._find_structured_case_fact_message(
                    item,
                    depth=depth + 1,
                )
                if found:
                    return found
        if isinstance(value, (list, tuple)):
            for item in reversed(value):
                found = cls._find_structured_case_fact_message(
                    item,
                    depth=depth + 1,
                )
                if found:
                    return found
        return ""

    @classmethod
    def _message_text(cls, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, list):
            return "\n".join(
                part for item in value if (part := cls._message_text(item))
            )
        if isinstance(value, dict):
            for key in ("text", "input_text", "content", "value"):
                part = cls._message_text(value.get(key))
                if part:
                    return part
        return ""

    def _latest_user_message_sha256(
        self,
        body: dict,
        messages_arg: Any,
    ) -> str | None:
        value = self._latest_user_message(body, messages_arg)
        return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None

    async def _server_attested_runtime_metadata(
        self,
        *,
        request: Any,
        metadata: dict[str, Any],
        user: Any,
    ) -> dict[str, Any]:
        """Recover a native chat scope only after an owner-bound DB lookup."""

        result = dict(metadata)
        if result.get("chat_id") and result.get("model_id"):
            return result
        if request is None or not callable(getattr(request, "json", None)):
            return result
        try:
            request_body = await request.json()
        except Exception:
            request_body = {}
        if not isinstance(request_body, dict):
            return result
        request_metadata = request_body.get("metadata")
        request_metadata = (
            request_metadata if isinstance(request_metadata, dict) else {}
        )
        chat_id = str(
            result.get("chat_id")
            or request_metadata.get("chat_id")
            or request_body.get("chat_id")
            or ""
        ).strip()
        user_id = (
            str(user.get("id") or user.get("user_id") or "").strip()
            if isinstance(user, dict)
            else ""
        )
        if not chat_id or not user_id:
            return result
        try:
            from open_webui.models.chats import Chats

            chat = await Chats.get_chat_by_id_and_user_id(chat_id, user_id)
        except (ImportError, AttributeError):
            return result
        if chat is None:
            return result
        result["chat_id"] = chat_id
        chat_payload = chat.chat if isinstance(chat.chat, dict) else {}
        models = chat_payload.get("models")
        if isinstance(models, list) and NDFL_WORKSPACE_MODEL_STABLE_ID in models:
            result["model_id"] = NDFL_WORKSPACE_MODEL_STABLE_ID
        return result

    async def _trusted_interaction_message(
        self,
        *,
        body: dict,
        messages_arg: Any,
        request: Any,
        metadata: dict,
        user: Any,
    ) -> str:
        value = self._latest_user_message(body, messages_arg)
        if "3-НДФЛ факты:" in value:
            return value
        if request is None or not callable(getattr(request, "json", None)):
            return value
        try:
            request_body = await request.json()
        except Exception:
            request_body = {}
        if not isinstance(request_body, dict):
            request_body = {}
        trusted = self._latest_user_message(request_body, None)
        if "3-НДФЛ факты:" in trusted:
            return trusted
        chat_id = str(metadata.get("chat_id") or "").strip()
        user_id = (
            str(user.get("id") or user.get("user_id") or "").strip()
            if isinstance(user, dict)
            else ""
        )
        if not chat_id or not user_id:
            return trusted or value
        try:
            from open_webui.models.chats import Chats

            chat = await Chats.get_chat_by_id_and_user_id(chat_id, user_id)
        except (ImportError, AttributeError):
            return trusted or value
        if chat is None:
            return trusted or value
        history = (
            chat.chat.get("history", {}).get("messages", {})
            if isinstance(chat.chat, dict)
            else {}
        )
        candidates = []
        for message_id, message in history.items() if isinstance(history, dict) else ():
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            text = self._message_text(message.get("content"))
            if "3-НДФЛ факты:" not in text:
                continue
            candidates.append(
                (
                    float(message.get("timestamp") or message.get("created_at") or 0),
                    str(message_id),
                    text,
                )
            )
        return max(candidates)[2] if candidates else (trusted or value)

    @classmethod
    async def _server_attested_completed_turn_content(
        cls,
        *,
        metadata: dict[str, Any],
        user: Any,
        interaction_message: str,
    ) -> str | None:
        """Replay only the host-owned completed leaf for this exact user turn."""

        chat_id = str(metadata.get("chat_id") or "").strip()
        if metadata.get("model_id") != NDFL_WORKSPACE_MODEL_STABLE_ID:
            return None
        user_id = (
            str(user.get("id") or user.get("user_id") or "").strip()
            if isinstance(user, dict)
            else ""
        )
        if not chat_id or not user_id or not interaction_message:
            return None
        try:
            from open_webui.models.chats import Chats

            chat = await Chats.get_chat_by_id_and_user_id(chat_id, user_id)
        except (ImportError, AttributeError):
            return None
        if chat is None or not isinstance(chat.chat, dict):
            return None
        history = chat.chat.get("history")
        history = history if isinstance(history, dict) else {}
        messages = history.get("messages")
        messages = messages if isinstance(messages, dict) else {}
        current_id = str(history.get("currentId") or "").strip()
        current = messages.get(current_id)
        if (
            not isinstance(current, dict)
            or current.get("role") != "assistant"
            or current.get("done") is not True
            or str(current.get("model") or "").strip()
            != NDFL_WORKSPACE_MODEL_STABLE_ID
        ):
            return None
        parent = messages.get(str(current.get("parentId") or ""))
        if (
            not isinstance(parent, dict)
            or parent.get("role") != "user"
            or cls._message_text(parent.get("content")) != interaction_message
        ):
            return None
        content = current.get("content")
        return content if isinstance(content, str) and content.strip() else None

    def _file_obj(self, item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        nested = item.get("file")
        if isinstance(nested, dict):
            merged = dict(item)
            merged.update(nested)
            return merged
        return item

    def _file_id(self, file_obj: dict[str, Any]) -> str:
        value = file_obj.get("id") or file_obj.get("file_id")
        if value:
            return str(value)
        for key in ("url", "path", "href"):
            parsed = self._file_id_from_path(file_obj.get(key))
            if parsed:
                return parsed
        return ""

    def _file_id_from_path(self, value: Any) -> str:
        text = str(value or "")
        marker = "/api/v1/files/"
        if marker not in text:
            return ""
        suffix = text.split(marker, 1)[1]
        return suffix.split("/", 1)[0].split("?", 1)[0].strip()

    def _filename(self, file_obj: dict[str, Any]) -> str:
        meta = file_obj.get("meta") if isinstance(file_obj.get("meta"), dict) else {}
        return str(
            file_obj.get("filename")
            or file_obj.get("name")
            or file_obj.get("original_filename")
            or meta.get("filename")
            or meta.get("name")
            or ""
        )

    def _mime_type(self, file_obj: dict[str, Any]) -> str:
        meta = file_obj.get("meta") if isinstance(file_obj.get("meta"), dict) else {}
        return str(
            file_obj.get("mime_type")
            or file_obj.get("content_type")
            or meta.get("mime_type")
            or meta.get("content_type")
            or ""
        )

    def _safe_input_context(
        self,
        body: dict,
        metadata: dict,
        files_arg: Any,
        messages_arg: Any,
    ) -> dict[str, Any]:
        message_sources = [
            body.get("message"),
            body.get("messages"),
            metadata.get("message"),
            metadata.get("messages"),
            messages_arg,
        ]
        messages = []
        for source in message_sources:
            messages.extend(self._message_iter(source))
        context = {
            "body_files_count": self._safe_len(body.get("files")),
            "metadata_files_count": self._safe_len(metadata.get("files")),
            "files_arg_count": self._safe_len(files_arg),
            "messages_count": len(messages),
            "messages_with_files_count": sum(
                1
                for message in messages
                if isinstance(message, dict)
                and self._safe_len(message.get("files")) > 0
            ),
        }
        source_policy = self._source_policy_context(body, metadata)
        if source_policy:
            context["source_policy"] = source_policy
        return context

    def _safe_len(self, value: Any) -> int:
        return len(value) if isinstance(value, list) else 0

    def _source_policy_context(self, body: dict, metadata: dict) -> dict[str, Any]:
        body_metadata = (
            body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        )
        candidates = [
            metadata.get("source_policy"),
            self._nested_source_policy(metadata),
            body.get("source_policy"),
            self._nested_source_policy(body),
            body_metadata.get("source_policy"),
            self._nested_source_policy(body_metadata),
        ]
        for candidate in candidates:
            if isinstance(candidate, dict):
                sanitized = self._sanitize_source_policy(candidate)
                if sanitized:
                    return sanitized
        return {}

    def _sanitize_source_policy(self, value: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key in ("mode", "pdf_html_source_policy"):
            if value.get(key) is not None:
                result[key] = str(value.get(key))[:96]
        if "explicit" in value:
            result["explicit"] = self._optional_bool(
                value.get("explicit"), default=False
            )
        if "source_registry_role_hints_allowed" in value:
            result["source_registry_role_hints_allowed"] = self._optional_bool(
                value.get("source_registry_role_hints_allowed"),
                default=False,
            )
        if "accept_pdf_html_source_roles" in value:
            result["accept_pdf_html_source_roles"] = self._optional_bool(
                value.get("accept_pdf_html_source_roles"),
                default=False,
            )
        hints = value.get("safe_registry_role_hints")
        if isinstance(hints, list):
            sanitized_hints = [
                self._sanitize_source_policy_hint(item) for item in hints[:200]
            ]
            result["safe_registry_role_hints"] = [
                item for item in sanitized_hints if item
            ]
        return result

    def _sanitize_source_policy_hint(self, hint: Any) -> dict[str, Any]:
        if not isinstance(hint, dict):
            return {}
        result: dict[str, Any] = {}
        string_keys = (
            "safe_document_id",
            "registry_document_id",
            "container_format",
            "extension",
            "document_role_candidate",
            "source_evidence_candidate",
            "source_vs_output",
            "sha256_prefix",
            "hash_prefix",
        )
        for key in string_keys:
            value = hint.get(key)
            if value is not None:
                result[key] = str(value)[:128]
        document_id = hint.get("document_id")
        if document_id is not None and "safe_document_id" not in result:
            result["safe_document_id"] = str(document_id)[:128]
        sha256 = hint.get("sha256")
        if (
            sha256 is not None
            and "sha256_prefix" not in result
            and "hash_prefix" not in result
        ):
            result["sha256_prefix"] = str(sha256)[:12]
        if "methodology_or_output_candidate" in hint:
            result["methodology_or_output_candidate"] = self._optional_bool(
                hint.get("methodology_or_output_candidate"),
                default=False,
            )
        secondary_roles = hint.get("secondary_role_candidates")
        if isinstance(secondary_roles, list):
            result["secondary_role_candidates"] = [
                str(item)[:96] for item in secondary_roles[:10] if item is not None
            ]
        return result

    def _artifact_context(
        self,
        *,
        user: Any,
        metadata: dict,
        body: dict,
        kwargs: dict[str, Any],
        normalization_run_id: str,
    ) -> ArtifactAccessContext:
        del body  # Raw request fields are never lifecycle authority.
        user_id = self._authenticated_user_id(user)

        # __metadata__ and double-underscore kwargs are injected by OpenWebUI's
        # function runtime. Client body/metadata fallbacks are intentionally
        # excluded so a caller cannot select another lifecycle scope.
        chat_id = metadata.get("chat_id") or kwargs.get("__chat_id__")
        case_id = metadata.get("case_id")
        model_context = kwargs.get("__model__")
        if isinstance(model_context, dict):
            model_context = model_context.get("id") or model_context.get("model_id")
        workspace_model_id = metadata.get("model_id") or model_context
        if (
            not case_id
            and chat_id
            and workspace_model_id == NDFL_WORKSPACE_MODEL_STABLE_ID
        ):
            # An authenticated server-attested chat is the natural bounded case
            # for the existing NDFL Workspace Model product path.
            case_id = str(chat_id)
        if not case_id and not chat_id:
            raise ArtifactStoreError(
                "artifact_scope_unverified",
                "Server-attested case or chat context is required",
            )
        return ArtifactAccessContext(
            user_id=user_id,
            normalization_run_id=normalization_run_id,
            case_id=str(case_id) if case_id else None,
            chat_id=str(chat_id) if chat_id else None,
            workspace_model_id=str(workspace_model_id) if workspace_model_id else None,
            allow_private=True,
        )

    def _artifact_store(self):
        return ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=Path(self.valves.artifact_store_path),
                payload_root=Path(self.valves.artifact_payload_root),
            )
        ).create()

    @staticmethod
    def _authenticated_user_id(user: Any) -> str:
        if not isinstance(user, dict):
            raise ArtifactStoreError(
                "artifact_scope_unverified",
                "Authenticated server user context is required",
            )
        user_id = str(user.get("id") or user.get("user_id") or "").strip()
        if not user_id:
            raise ArtifactStoreError(
                "artifact_scope_unverified",
                "Authenticated server user identity is required",
            )
        return user_id

    def _user_id(self, user: Any, metadata: dict) -> str:
        if isinstance(user, dict):
            value = user.get("id") or user.get("user_id")
            if value:
                return str(value)
        nested = metadata.get("user") if isinstance(metadata.get("user"), dict) else {}
        value = metadata.get("user_id") or nested.get("id") or nested.get("user_id")
        if value:
            return str(value)
        return "openwebui_user_unavailable"

    def _user_role(self, user: Any, metadata: dict) -> str:
        if isinstance(user, dict):
            value = user.get("role")
            if value:
                return str(value)
        nested = metadata.get("user") if isinstance(metadata.get("user"), dict) else {}
        value = metadata.get("role") or nested.get("role")
        return str(value or "user")

    def _user_groups(self, user: Any, metadata: dict) -> list[str]:
        values: list[Any] = []
        if isinstance(user, dict):
            for key in ("groups", "group_ids"):
                if isinstance(user.get(key), list):
                    values.extend(user[key])
        nested = metadata.get("user") if isinstance(metadata.get("user"), dict) else {}
        for source in (metadata, nested):
            for key in ("groups", "group_ids"):
                if isinstance(source.get(key), list):
                    values.extend(source[key])
        return [str(value) for value in values if value]

    def _source_file_refs(
        self, file_refs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for file_ref in file_refs:
            refs.append(
                {
                    "provider": "openwebui",
                    "openwebui_file_id": str(file_ref.get("file_id") or ""),
                    "content_type": str(file_ref.get("mime_type") or ""),
                    "size_bytes": self._optional_int(file_ref.get("size_bytes")),
                    "source_deleted": False,
                    "source_delete_observed_at": None,
                }
            )
        return refs

    def _to_file_input(self, file_ref: dict[str, Any]) -> FileInput:
        file_id = str(file_ref.get("file_id") or "")
        filename = str(file_ref.get("filename") or "")
        return FileInput(
            private_ref=file_id,
            original_filename_private=filename,
            mime_type=str(file_ref.get("mime_type") or ""),
            source_kind="openwebui_pipe",
            declared_size_bytes=self._optional_int(file_ref.get("size_bytes")),
            bytes_provider=lambda ref=file_ref: self._read_original_bytes(ref),
            provider_label="openwebui_pipe",
            privacy_markers=[],
        )

    def _read_original_bytes(self, file_ref: dict[str, Any]) -> bytes:
        if is_private_intake_source_id(file_ref.get("file_id")):
            trusted = file_ref.get("_trusted_private_intake_bytes")
            if isinstance(trusted, bytes) and trusted:
                return trusted
            raise BytesUnavailable(
                str(
                    file_ref.get("_private_intake_bytes_error")
                    or "private_intake_bytes_unresolved"
                )
            )

        file_obj = file_ref.get("_private_file_obj")
        if isinstance(file_obj, dict):
            inline = self._inline_bytes(file_obj)
            if inline is not None:
                return inline

        if not self.valves.allow_upload_path_access:
            raise BytesUnavailable("upload_path_access_disabled")

        candidate_result = self._upload_root_candidate(file_ref)
        if candidate_result.get("status") == "blocked":
            raise BytesUnavailable(
                str(candidate_result.get("reason") or "upload_candidate_blocked")
            )
        candidate = candidate_result.get("path")
        if isinstance(candidate, Path) and candidate.exists() and candidate.is_file():
            return candidate.read_bytes()
        raise BytesUnavailable("upload_file_not_found")

    async def _hydrate_private_intake_file_refs(
        self,
        file_refs: list[dict[str, Any]],
        *,
        actor_user_id: str,
    ) -> None:
        resolver = None
        for file_ref in file_refs:
            source_id = str(file_ref.get("file_id") or "")
            if not is_private_intake_source_id(source_id):
                continue
            if resolver is None:
                resolver = self._private_intake_bytes_resolver()
            try:
                file_ref["_trusted_private_intake_bytes"] = await resolver.resolve(
                    source_id=source_id,
                    actor_user_id=actor_user_id,
                )
            except PrivateIntakeBytesError as exc:
                file_ref["_private_intake_bytes_error"] = exc.code

    def _private_intake_bytes_resolver(self):
        return OpenWebUIPrivateIntakeBytesResolverFactory().create()

    def _inline_bytes(self, file_obj: dict[str, Any]) -> bytes | None:
        for key in ("content_bytes", "bytes", "data_bytes"):
            value = file_obj.get(key)
            if isinstance(value, bytes):
                return value
        for key in ("content_base64", "data_base64"):
            value = file_obj.get(key)
            if isinstance(value, str):
                try:
                    return base64.b64decode(value.encode("ascii"), validate=True)
                except (binascii.Error, UnicodeEncodeError):
                    return None
        for key in ("content", "data"):
            value = file_obj.get(key)
            if isinstance(value, str):
                return value.encode("utf-8")
        return None

    def _upload_root_candidate(self, file_ref: dict[str, Any]) -> dict[str, Any]:
        upload_root = Path(self.valves.upload_root).resolve()
        file_id = str(file_ref.get("file_id") or "")
        filename = str(file_ref.get("filename") or "")
        if self._has_path_separator(file_id) or self._has_path_separator(filename):
            return {"status": "blocked", "reason": "upload_path_escape_detected"}
        candidate = (upload_root / f"{file_id}_{filename}").resolve()
        if upload_root not in candidate.parents and candidate != upload_root:
            return {"status": "blocked", "reason": "upload_path_escape_detected"}
        return {"status": "candidate", "path": candidate}

    def _has_path_separator(self, value: str) -> bool:
        return "/" in value or "\\" in value or Path(value).name != value

    def _private_markers(self, file_refs: list[dict[str, Any]]) -> list[str]:
        markers: list[str] = []
        for file_ref in file_refs:
            markers.extend(
                [
                    str(file_ref.get("file_id") or ""),
                    str(file_ref.get("filename") or ""),
                ]
            )
            file_obj = file_ref.get("_private_file_obj")
            if isinstance(file_obj, dict):
                for key in ("content", "data"):
                    value = file_obj.get(key)
                    if isinstance(value, str):
                        markers.append(value)
                for key in ("content_bytes", "bytes", "data_bytes"):
                    value = file_obj.get(key)
                    if isinstance(value, bytes):
                        try:
                            markers.append(value.decode("utf-8"))
                        except UnicodeDecodeError:
                            pass
        return [marker for marker in markers if marker]

    def _optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            result = int(value)
        except (TypeError, ValueError):
            return None
        return result if result >= 0 else None

    def _optional_bool(self, value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y", "on"}:
                return True
            if normalized in {"0", "false", "no", "n", "off"}:
                return False
        return bool(value)

    def _nested_retention_policy(self, value: dict[str, Any]) -> Any:
        broker_context = value.get("broker_reports_gate1")
        if not isinstance(broker_context, dict):
            return None
        return broker_context.get("retention_policy")

    def _nested_source_policy(self, value: dict[str, Any]) -> Any:
        broker_context = value.get("broker_reports_gate1")
        if not isinstance(broker_context, dict):
            return None
        return broker_context.get("source_policy")
