"""
title: Broker Reports Gate 1 Pipe Backend Normalizer
author: Alpha Soft
version: 0.13.0-pdf-structural-semantic-shadow
required_open_webui_version: 0.9.6
requirements: pydantic,pypdf==6.7.5,pdfplumber==0.11.10,pdfminer.six==20260107,PyMuPDF==1.26.5
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import inspect
import json
import re
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
    FileProcessingOutcomeFactory,
    Gate1Normalizer,
    ManagedPrompt,
    NORMALIZER_VERSION,
    PromptUserContext,
    SAFETY_STATEMENT as SAFETY_STATEMENT,
    RetentionPolicyError,
    apply_document_passport_stage,
    apply_clarification_request_stage,
    apply_metadata_gap_report_stage,
    build_llm_document_packages,
    build_metadata_gap_report,
    build_retention_policy,
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
)
from broker_reports_gate1.detectors import extension_from_name
from broker_reports_gate1.normalizer import NormalizationResult
from broker_reports_gate1.pdf_hybrid_evidence import PdfHybridEvidenceConfig
from broker_reports_gate1.pdf_hybrid_provider import (
    PdfHybridProviderConfig,
    PdfHybridProviderError,
    PdfHybridProviderFactory,
)
from broker_reports_gate1.pdf_hybrid_shadow import (
    PdfHybridShadowConfig,
    PdfHybridShadowFactory,
)
from broker_reports_gate1.pdf_grid_experiment_provider import (
    PdfGridExperimentProviderFactory,
    PdfGridProviderConfig,
    PdfGridProviderError,
)
from broker_reports_gate1.pdf_structural_repair_runtime import (
    PdfStructuralRepairRuntimeConfig,
)
from broker_reports_gate1.pdf_structural_repair_shadow import (
    PdfStructuralRepairShadowConfig,
    PdfStructuralRepairShadowError,
    PdfStructuralRepairShadowFactory,
)
from broker_reports_gate1.safe_report import render_safe_report
from broker_reports_gate1.validators import validate_safe_report


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
        artifact_store_path: str = Field(default="/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
        artifact_payload_root: str = Field(default="/app/backend/data/broker_reports_gate1/payloads")
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
        clarification_prompt_command: str = Field(default="broker_gate1_clarification_request")
        clarification_model_id: str = Field(default="")
        clarification_criticality_refinement_enabled: bool = Field(default=True)
        pdf_compact_canonical_dual_write: bool = Field(default=False)
        pdf_hybrid_shadow_enabled: bool = Field(default=False)
        pdf_hybrid_shadow_table_allowlist: str = Field(default="")
        pdf_hybrid_provider_profile: str = Field(default="google_gemini")
        pdf_hybrid_model_id: str = Field(default="models/gemini-3.5-flash")
        pdf_hybrid_max_candidates: int = Field(default=512)
        pdf_hybrid_max_context_bytes: int = Field(default=128 * 1024)
        pdf_hybrid_primary_dpi: int = Field(default=150)
        pdf_hybrid_escalation_dpi: int = Field(default=200)
        pdf_structural_repair_shadow_enabled: bool = Field(default=False)
        pdf_vlm_guided_intake_shadow_enabled: bool = Field(default=False)
        pdf_vlm_guided_intake_shadow_page_allowlist: str = Field(default="")
        pdf_semantic_header_shadow_enabled: bool = Field(default=False)
        pdf_structural_repair_shadow_table_allowlist: str = Field(default="")
        pdf_structural_repair_provider_profile: str = Field(default="google_gemini")
        pdf_structural_repair_model_id: str = Field(default="models/gemini-3.5-flash")
        pdf_structural_repair_max_tables: int = Field(default=8, ge=1, le=32)
        live_smoke_trigger_phrases: str = Field(
            default="artifactstore retention smoke,gate1 artifactstore smoke"
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self._normalizer = Gate1Normalizer()
        self.last_safe_report: dict | None = None
        self.last_artifact_manifest: dict | None = None

    async def pipe(
        self,
        body: dict,
        __user__=None,
        __request__=None,
        __metadata__=None,
        __files__=None,
        __messages__=None,
        __event_emitter__=None,
        **kwargs,
    ) -> str:
        await self._emit(__event_emitter__, "Checking uploaded file refs...", done=False)
        safe_body = body if isinstance(body, dict) else {}
        safe_metadata = __metadata__ if isinstance(__metadata__, dict) else {}
        messages_arg = __messages__ or kwargs.get("__messages__")
        files_arg = __files__ or kwargs.get("__files__")

        if self.valves.require_trigger_phrase and not self._has_trigger_phrase(safe_body, messages_arg):
            await self._emit(__event_emitter__, "Gate 1 trigger phrase was not found.", done=True)
            return (
                "Gate 1 normalization is available. Attach documents and send "
                "`Gate 1 normalization` in the same message."
            )

        file_refs = self._collect_file_refs(safe_body, safe_metadata, files_arg, messages_arg)
        input_context = self._safe_input_context(safe_body, safe_metadata, files_arg, messages_arg)
        case_group_id = self._case_group_id(safe_body, safe_metadata)
        if case_group_id:
            input_context["case_group_id"] = case_group_id
        body_metadata = safe_body.get("metadata") if isinstance(safe_body.get("metadata"), dict) else {}
        case_id = safe_metadata.get("case_id") or body_metadata.get("case_id") or safe_body.get("case_id")
        if case_id:
            input_context["case_id"] = str(case_id)
        criticality_refinement_enabled = self._criticality_refinement_enabled(safe_body, safe_metadata)
        file_inputs = [self._to_file_input(file_ref) for file_ref in file_refs]
        retention_policy = self._retention_policy(safe_body, safe_metadata)
        result = self._normalizer.normalize(
            file_inputs,
            entrypoint="broker_reports_gate1_pipe",
            trigger_type="pipe_backend_normalizer",
            input_context={
                **input_context,
                "normalizer_version": NORMALIZER_VERSION,
                "retention_policy_mode": retention_policy.mode,
                "retention_policy_explicit": retention_policy.explicit,
                "clarification_criticality_refinement_enabled": criticality_refinement_enabled,
                "pdf_compact_canonical_dual_write": bool(
                    self.valves.pdf_compact_canonical_dual_write
                ),
                "pdf_semantic_header_shadow_enabled": bool(
                    self.valves.pdf_semantic_header_shadow_enabled
                ),
                "pdf_vlm_guided_intake_shadow_enabled": bool(
                    self.valves.pdf_vlm_guided_intake_shadow_enabled
                ),
            },
            extra_private_markers=self._private_markers(file_refs),
        )
        artifact_context = self._artifact_context(
            user=__user__,
            metadata=safe_metadata,
            body=safe_body,
            kwargs=kwargs,
            normalization_run_id=result.package["normalization_run"]["run_id"],
        )
        artifact_store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=Path(self.valves.artifact_store_path),
                payload_root=Path(self.valves.artifact_payload_root),
            )
        ).create()
        structural_shadow = self._maybe_run_pdf_structural_repair_shadow(
            store=artifact_store,
            result=result,
            context=artifact_context,
            retention_policy=retention_policy,
            file_inputs=file_inputs,
            request=__request__,
        )
        result = self._attach_pdf_structural_repair_shadow(
            result=result,
            shadow_result=structural_shadow,
        )
        result = await self._maybe_run_passport_stage(
            result=result,
            user=__user__,
            request=__request__,
            metadata=safe_metadata,
            body=safe_body,
            event_emitter=__event_emitter__,
        )
        result = await self._maybe_run_clarification_stage(
            result=result,
            user=__user__,
            request=__request__,
            metadata=safe_metadata,
            body=safe_body,
            event_emitter=__event_emitter__,
        )
        artifact_manifest = persist_gate1_result(
            store=artifact_store,
            result=result,
            context=artifact_context,
            retention_policy=retention_policy,
            source_file_refs=self._source_file_refs(file_refs),
        )
        hybrid_shadow = self._maybe_run_pdf_hybrid_shadow(
            store=artifact_store,
            result=result,
            context=artifact_context,
            retention_policy=retention_policy,
            file_inputs=file_inputs,
            request=__request__,
        )
        self.last_safe_report = result.safe_report
        self.last_artifact_manifest = {
            **artifact_manifest.to_dict(),
            "pdf_structural_repair_shadow": structural_shadow,
            "pdf_semantic_header_shadow": self._semantic_shadow_manifest(
                structural_shadow
            ),
            "pdf_hybrid_shadow": hybrid_shadow,
        }

        if not file_refs:
            await self._emit(__event_emitter__, "No uploaded file refs were visible.", done=True)
        else:
            await self._emit(__event_emitter__, "Gate 1 artifacts persisted and compact report ready.", done=True)
        chat_content = render_chat_content(result.safe_report)
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

    def _maybe_run_pdf_structural_repair_shadow(
        self,
        *,
        store,
        result: NormalizationResult,
        context: ArtifactAccessContext,
        retention_policy,
        file_inputs: list[FileInput],
        request: Any,
    ) -> dict[str, Any]:
        if not self.valves.pdf_structural_repair_shadow_enabled:
            runtime = PdfStructuralRepairShadowFactory(
                PdfStructuralRepairShadowConfig(
                    enabled=False,
                    vlm_guided_intake_enabled=False,
                    semantic_header_shadow_enabled=bool(
                        self.valves.pdf_semantic_header_shadow_enabled
                    ),
                )
            ).create(provider=None)
            return runtime.run(
                store=store,
                package=result.package,
                context=context,
                retention_policy=retention_policy,
                pdf_bytes_by_sha256={},
            )
        pdf_bytes_by_sha256: dict[str, bytes] = {}
        for file_input in file_inputs:
            read = file_input.read_bytes()
            if read.status != "available" or not isinstance(read.content_bytes, bytes):
                continue
            pdf_bytes_by_sha256[hashlib.sha256(read.content_bytes).hexdigest()] = read.content_bytes
        provider = None
        try:
            provider = PdfGridExperimentProviderFactory(
                PdfGridProviderConfig(
                    provider_profile=self.valves.pdf_structural_repair_provider_profile,
                    model_id=self.valves.pdf_structural_repair_model_id,
                    maximum_counted_input_tokens=20_000,
                )
            ).create_for_openwebui(request)
        except (PdfGridProviderError, RuntimeError, ValueError):
            provider = None
        allowlist = tuple(
            sorted(
                {
                    item.strip()
                    for item in self.valves.pdf_structural_repair_shadow_table_allowlist.split(",")
                    if item.strip()
                }
            )
        )
        page_allowlist = tuple(
            sorted(
                {
                    item.strip()
                    for item in self.valves.pdf_vlm_guided_intake_shadow_page_allowlist.split(",")
                    if item.strip()
                }
            )
        )
        try:
            runtime = PdfStructuralRepairShadowFactory(
                PdfStructuralRepairShadowConfig(
                    enabled=True,
                    vlm_guided_intake_enabled=bool(
                        self.valves.pdf_vlm_guided_intake_shadow_enabled
                    ),
                    semantic_header_shadow_enabled=bool(
                        self.valves.pdf_semantic_header_shadow_enabled
                    ),
                    maximum_tables=self.valves.pdf_structural_repair_max_tables,
                    table_allowlist=allowlist,
                    page_allowlist=page_allowlist,
                ),
                runtime_config=PdfStructuralRepairRuntimeConfig(
                    provider_profile=self.valves.pdf_structural_repair_provider_profile,
                    model_id=self.valves.pdf_structural_repair_model_id,
                ),
            ).create(provider=provider)
            return runtime.run(
                store=store,
                package=result.package,
                context=context,
                retention_policy=retention_policy,
                pdf_bytes_by_sha256=pdf_bytes_by_sha256,
            )
        except (PdfStructuralRepairShadowError, RuntimeError, ValueError):
            return self._pdf_structural_repair_safe_fallback(
                result,
                vlm_guided_intake_enabled=bool(
                    self.valves.pdf_vlm_guided_intake_shadow_enabled
                ),
                semantic_header_shadow_enabled=bool(
                    self.valves.pdf_semantic_header_shadow_enabled
                ),
            )

    def _attach_pdf_structural_repair_shadow(
        self,
        *,
        result: NormalizationResult,
        shadow_result: dict[str, Any],
    ) -> NormalizationResult:
        summary = shadow_result.get("summary")
        safe_projection = {
            "enabled": shadow_result.get("enabled") is True,
            "summary_ref": shadow_result.get("summary_ref"),
            "summary": summary if isinstance(summary, dict) else None,
            "authority_state": "non_authoritative",
            "production_gate2_selection_changed": False,
        }
        result.package["pdf_structural_repair_shadow"] = safe_projection
        safe_report = render_safe_report(result.package)
        validation = validate_safe_report(
            safe_report=safe_report,
            private_markers=result.private_markers,
            run_id=result.package["normalization_run"]["run_id"],
        )
        if validation.get("status") != "passed":
            fallback = self._pdf_structural_repair_safe_fallback(
                result,
                vlm_guided_intake_enabled=bool(
                    self.valves.pdf_vlm_guided_intake_shadow_enabled
                ),
                semantic_header_shadow_enabled=bool(
                    self.valves.pdf_semantic_header_shadow_enabled
                ),
            )
            result.package["pdf_structural_repair_shadow"] = {
                "enabled": True,
                "summary_ref": None,
                "summary": fallback["summary"],
                "authority_state": "non_authoritative",
                "production_gate2_selection_changed": False,
            }
            safe_report = render_safe_report(result.package)
        return NormalizationResult(
            package=result.package,
            safe_report=safe_report,
            private_markers=result.private_markers,
        )

    @staticmethod
    def _pdf_structural_repair_safe_fallback(
        result: NormalizationResult,
        *,
        vlm_guided_intake_enabled: bool = False,
        semantic_header_shadow_enabled: bool = False,
    ) -> dict[str, Any]:
        documents = [
            item
            for item in result.package.get("document_inventory", {}).get("documents", [])
            if isinstance(item, dict) and item.get("container_format") == "pdf"
        ]
        outcomes = None
        if documents:
            service = FileProcessingOutcomeFactory().create()
            records = [
                service.failed(
                    file_ref=str(item.get("document_id")),
                    stage="processing",
                    reason_code="internal_processing_failed",
                )
                for item in documents
            ]
            outcomes = service.batch(records).model_context()
        return {
            "enabled": True,
            "artifact_refs": [],
            "semantic_projection_refs": [],
            "semantic_diagnostic_refs": [],
            "summary_ref": None,
            "summary": {
                "schema_version": "broker_reports_pdf_structural_repair_shadow_summary_v1",
                "enabled": True,
                "vlm_guided_intake_enabled": vlm_guided_intake_enabled,
                "tables_discovered": 0,
                "tables_selected": 0,
                "accepted_supplied_consensus_tables": 0,
                "accepted_physical_structure_tables": 0,
                "continuation_groups_discovered": 0,
                "continuation_groups_accepted": 0,
                "continuation_groups_failed": 0,
                "continuation_group_outcomes": [],
                "terminal_outcomes": {"internal_failure": len(documents)},
                "semantic_header_shadow_enabled": (
                    semantic_header_shadow_enabled
                ),
                "semantic_projection_status_counts": (
                    {"not_projected_structural_failure": len(documents)}
                    if semantic_header_shadow_enabled and documents
                    else {}
                ),
                "semantic_projection_reason_counts": (
                    {
                        "pdf_semantic_header_not_projected_structural_failure": (
                            len(documents)
                        )
                    }
                    if semantic_header_shadow_enabled and documents
                    else {}
                ),
                "private_semantic_projections_persisted": 0,
                "private_semantic_diagnostics_persisted": 0,
                "file_processing_outcomes": outcomes,
                "authority_state": "non_authoritative",
                "production_ready": False,
                "production_gate2_selection_changed": False,
            },
        }

    @staticmethod
    def _semantic_shadow_manifest(
        structural_shadow: dict[str, Any],
    ) -> dict[str, Any]:
        summary = (
            structural_shadow.get("summary")
            if isinstance(structural_shadow.get("summary"), dict)
            else {}
        )
        refs = structural_shadow.get("semantic_projection_refs")
        return {
            "enabled": summary.get("semantic_header_shadow_enabled") is True,
            "artifact_refs": list(refs) if isinstance(refs, list) else [],
            "status_counts": dict(
                summary.get("semantic_projection_status_counts") or {}
            ),
            "reason_counts": dict(
                summary.get("semantic_projection_reason_counts") or {}
            ),
            "private_projections_persisted": int(
                summary.get("private_semantic_projections_persisted") or 0
            ),
            "private_diagnostics_persisted": int(
                summary.get("private_semantic_diagnostics_persisted") or 0
            ),
            "authority_state": "non_authoritative",
            "production_gate2_selection_changed": False,
        }

    def _maybe_run_pdf_hybrid_shadow(
        self,
        *,
        store,
        result: NormalizationResult,
        context: ArtifactAccessContext,
        retention_policy,
        file_inputs: list[FileInput],
        request: Any,
    ) -> dict[str, Any]:
        if not self.valves.pdf_hybrid_shadow_enabled:
            return {"enabled": False, "artifact_refs": [], "summary": None}
        pdf_bytes_by_sha256: dict[str, bytes] = {}
        for file_input in file_inputs:
            read = file_input.read_bytes()
            if read.status != "available" or not isinstance(read.content_bytes, bytes):
                continue
            pdf_bytes_by_sha256[hashlib.sha256(read.content_bytes).hexdigest()] = read.content_bytes
        provider = None
        try:
            provider = PdfHybridProviderFactory(
                PdfHybridProviderConfig(
                    provider_profile=self.valves.pdf_hybrid_provider_profile,
                    model_id=self.valves.pdf_hybrid_model_id,
                )
            ).create_for_openwebui(request)
        except (PdfHybridProviderError, RuntimeError, ValueError):
            provider = None
        allowlist = tuple(
            sorted(
                {
                    item.strip()
                    for item in self.valves.pdf_hybrid_shadow_table_allowlist.split(",")
                    if item.strip()
                }
            )
        )
        runtime = PdfHybridShadowFactory(
            PdfHybridShadowConfig(
                enabled=True,
                primary_dpi=self.valves.pdf_hybrid_primary_dpi,
                escalation_dpi=self.valves.pdf_hybrid_escalation_dpi,
                table_allowlist=allowlist,
            ),
            evidence_config=PdfHybridEvidenceConfig(
                maximum_candidates=self.valves.pdf_hybrid_max_candidates,
                maximum_candidate_json_bytes=self.valves.pdf_hybrid_max_context_bytes,
            ),
        ).create(provider=provider)
        return runtime.run(
            store=store,
            package=result.package,
            context=context,
            retention_policy=retention_policy,
            pdf_bytes_by_sha256=pdf_bytes_by_sha256,
        )

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
        criticality_refinement_enabled = self._criticality_refinement_enabled(body, metadata)
        await self._emit(event_emitter, "Resolving managed Document Metadata Passport prompt...", done=False)
        try:
            prompt = self._resolve_passport_prompt(user=user, metadata=metadata, body=body)
            model_id = self._passport_model_id(body, metadata)
        except DocumentPassportError:
            await self._emit(
                event_emitter,
                "Document metadata passport stage unavailable; continuing with safe Gate 1 fallback.",
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
        await self._emit(event_emitter, "Calling OpenWebUI model for document metadata passports...", done=False)
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
                    raise DocumentPassportError("passport_model_invalid_response", "Completion response is empty")
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
                        "normalization_run_id": document_package["normalization_run_id"],
                        "llm_input_package_id": document_package["llm_input_package_id"],
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
                        "normalization_run_id": document_package["normalization_run_id"],
                        "llm_input_package_id": document_package["llm_input_package_id"],
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
        await self._emit(event_emitter, "Document metadata passports validated.", done=False)
        return NormalizationResult(
            package=applied["package"],
            safe_report=applied["safe_report"],
            private_markers=result.private_markers,
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
        criticality_refinement_enabled = self._criticality_refinement_enabled(body, metadata)
        await self._emit(event_emitter, "Building deterministic Gate 1 metadata gap report...", done=False)
        gap_report = build_metadata_gap_report(
            result.package,
            criticality_refinement_enabled=criticality_refinement_enabled,
        )
        if int((gap_report.get("summary") or {}).get("resolvable_gaps_total") or 0) == 0:
            applied_gap = apply_metadata_gap_report_stage(
                result.package,
                private_markers=result.private_markers,
                criticality_refinement_enabled=criticality_refinement_enabled,
            )
            return NormalizationResult(
                package=applied_gap["package"],
                safe_report=applied_gap["safe_report"],
                private_markers=result.private_markers,
            )
        try:
            prompt = self._resolve_clarification_prompt(user=user, metadata=metadata, body=body)
            model_id = self._clarification_model_id(body, metadata)
        except ClarificationError:
            await self._emit(
                event_emitter,
                "Clarification prompt unavailable; persisting deterministic metadata gap report only.",
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
            )
        await self._emit(event_emitter, "Calling OpenWebUI model for Gate 1 clarification questions...", done=False)
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
            )
        await self._emit(event_emitter, "Gate 1 clarification questions prepared.", done=False)
        return NormalizationResult(
            package=applied["package"],
            safe_report=applied["safe_report"],
            private_markers=result.private_markers,
        )

    def _resolve_passport_prompt(self, *, user: Any, metadata: dict[str, Any], body: dict[str, Any]) -> ManagedPrompt:
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

    def _resolve_clarification_prompt(self, *, user: Any, metadata: dict[str, Any], body: dict[str, Any]):
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
            raise DocumentPassportError("passport_model_unavailable", "OpenWebUI request object is required")
        user_id = self._user_id(user, {})
        if not user_id:
            raise DocumentPassportError("passport_model_unavailable", "OpenWebUI user id is required")
        package_json = json.dumps(document_package, ensure_ascii=False, sort_keys=True)
        system_content = prompt.content.replace("{{document_package_json}}", package_json)
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
        raise DocumentPassportError("passport_model_unavailable", "Structured output model call failed")

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
            raise DocumentPassportError("passport_model_unavailable", "OpenWebUI request object is required")
        user_id = self._user_id(user, {})
        if not user_id:
            raise DocumentPassportError("passport_model_unavailable", "OpenWebUI user id is required")
        package_json = json.dumps(document_package, ensure_ascii=False, sort_keys=True)
        system_content = prompt.content.replace("{{document_package_json}}", package_json)
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
            structured_output_mode=str(audit.get("structured_output_mode") or "openwebui_response_format_json_object_fallback"),
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

    def _passport_allowed_evidence_refs(self, document_package: dict[str, Any]) -> list[str]:
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
            raise ClarificationError("clarification_model_unavailable", "OpenWebUI request object is required")
        user_id = self._user_id(user, {})
        if not user_id:
            raise ClarificationError("clarification_model_unavailable", "OpenWebUI user id is required")
        gap_report_json = json.dumps(gap_report, ensure_ascii=False, sort_keys=True)
        schema_json = json.dumps(clarification_json_schema_response_format()["json_schema"]["schema"], ensure_ascii=False, sort_keys=True)
        system_content = (
            prompt.content
            .replace("{{metadata_gap_report_json}}", gap_report_json)
            .replace("{{allowed_answer_schema_json}}", schema_json)
        )
        user_content = json.dumps(
            {
                "task": "write_gate1_clarification_request_v0",
                "metadata_gap_report": gap_report,
                "allowed_schema": clarification_json_schema_response_format()["json_schema"]["schema"],
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
                raise ClarificationError("clarification_model_call_failed", exc.code) from exc
        raise ClarificationError("clarification_model_unavailable", "Structured output model call failed")

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
                    or document_package.get("output_schema", {}).get("output_schema_hash"),
                }
            },
        }
        try:
            completion_fn, user_model = self._openwebui_completion_dependencies(user_id)
        except Exception as exc:
            raise DocumentPassportError("passport_model_unavailable", exc.__class__.__name__) from exc
        if inspect.isawaitable(user_model):
            user_model = await user_model
        if user_model is None:
            raise DocumentPassportError("passport_model_unavailable", "OpenWebUI user is unavailable")
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
                    response = completion_fn(request=request, form_data=form_data, user=user_model)
                except TypeError:
                    response = completion_fn(request, form_data, user_model)
        except Exception as exc:
            raise DocumentPassportError("passport_model_call_failed", exc.__class__.__name__) from exc
        if inspect.isawaitable(response):
            try:
                response = await response
            except Exception as exc:
                raise DocumentPassportError("passport_model_call_failed", exc.__class__.__name__) from exc
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
                raise DocumentPassportError("passport_model_invalid_response", "Completion response body is not JSON")
        if isinstance(response, str):
            return response
        raise DocumentPassportError("passport_model_invalid_response", "Unsupported completion response shape")

    def _completion_dict_content(self, payload: dict[str, Any]) -> Any:
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            message = first.get("message") if isinstance(first.get("message"), dict) else {}
            if isinstance(message.get("content"), str) and message.get("content"):
                return message["content"]
            if isinstance(first.get("text"), str) and first.get("text"):
                return first["text"]
        if isinstance(payload.get("content"), str) and payload.get("content"):
            return payload["content"]
        if isinstance(payload.get("response"), str) and payload.get("response"):
            return payload["response"]
        raise DocumentPassportError("passport_model_invalid_response", "Completion response has no content")

    def _passport_model_id(self, body: dict[str, Any], metadata: dict[str, Any]) -> str:
        value = (
            self._passport_config_value(body, metadata, "passport_model_id", "llm_model_id")
            or self._passport_nested_config_value(body, metadata, "model_id")
            or self.valves.passport_model_id
        )
        if not value:
            raise DocumentPassportError("passport_model_unavailable", "Passport model id is not configured")
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

    def _passport_prompt_config(self, body: dict[str, Any], metadata: dict[str, Any]) -> dict[str, str | None]:
        db_path = (
            self._passport_config_value(body, metadata, "passport_prompt_db_path", "prompt_db_path")
            or self.valves.passport_prompt_db_path
        )
        prompt_id = (
            self._passport_config_value(body, metadata, "passport_prompt_id", "prompt_id")
            or self.valves.passport_prompt_id
        )
        command = (
            self._passport_config_value(body, metadata, "passport_prompt_command", "prompt_command", "command")
            or self.valves.passport_prompt_command
        )
        return {
            "db_path": str(db_path),
            "prompt_id": str(prompt_id).strip() or None,
            "command": str(command).strip() or None,
        }

    def _passport_max_documents(self, body: dict[str, Any], metadata: dict[str, Any]) -> int | None:
        value = self._passport_config_value(body, metadata, "passport_max_documents", "max_documents")
        limit = self._optional_int(value)
        if limit is None:
            limit = self.valves.passport_max_documents
        return limit if limit > 0 else None

    def _passport_config_value(self, body: dict[str, Any], metadata: dict[str, Any], *keys: str) -> Any:
        for context in self._passport_contexts(body, metadata):
            for key in keys:
                if key in context and context.get(key) not in (None, ""):
                    return context.get(key)
        return self._passport_message_config_value(body, *keys)

    def _passport_nested_config_value(self, body: dict[str, Any], metadata: dict[str, Any], *keys: str) -> Any:
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

    def _passport_contexts(self, body: dict[str, Any], metadata: dict[str, Any]) -> list[dict[str, Any]]:
        contexts: list[dict[str, Any]] = []
        body_metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
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

    def _passport_nested_contexts(self, body: dict[str, Any], metadata: dict[str, Any]) -> list[dict[str, Any]]:
        contexts: list[dict[str, Any]] = []
        body_metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
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

    def _clarification_enabled(self, body: dict[str, Any], metadata: dict[str, Any]) -> bool:
        value = self._clarification_config_value(
            body,
            metadata,
            "clarification_enabled",
            "enabled",
            "metadata_clarification_enabled",
        )
        return self._optional_bool(value, default=bool(self.valves.clarification_enabled))

    def _criticality_refinement_enabled(self, body: dict[str, Any], metadata: dict[str, Any]) -> bool:
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

    def _clarification_model_id(self, body: dict[str, Any], metadata: dict[str, Any]) -> str:
        value = (
            self._clarification_config_value(body, metadata, "clarification_model_id", "llm_model_id")
            or self._clarification_nested_config_value(body, metadata, "model_id")
            or self.valves.clarification_model_id
        )
        if not value:
            try:
                value = self._passport_model_id(body, metadata)
            except DocumentPassportError:
                value = None
        if not value:
            raise ClarificationError("clarification_model_unavailable", "Clarification model id is not configured")
        return str(value)

    def _clarification_prompt_config(self, body: dict[str, Any], metadata: dict[str, Any]) -> dict[str, str | None]:
        db_path = (
            self._clarification_config_value(body, metadata, "clarification_prompt_db_path", "prompt_db_path")
            or self.valves.clarification_prompt_db_path
        )
        prompt_id = (
            self._clarification_config_value(body, metadata, "clarification_prompt_id", "prompt_id")
            or self.valves.clarification_prompt_id
        )
        command = (
            self._clarification_config_value(body, metadata, "clarification_prompt_command", "prompt_command", "command")
            or self.valves.clarification_prompt_command
        )
        return {
            "db_path": str(db_path),
            "prompt_id": str(prompt_id).strip() or None,
            "command": str(command).strip() or None,
        }

    def _clarification_answers(self, body: dict[str, Any], metadata: dict[str, Any]) -> list[dict[str, Any]]:
        for context in self._clarification_contexts(body, metadata):
            answers = context.get("answers")
            if isinstance(answers, list):
                return [item for item in answers if isinstance(item, dict)]
            direct = context.get("gate1_clarification_answers")
            if isinstance(direct, list):
                return [item for item in direct if isinstance(item, dict)]
        return []

    def _clarification_answer_source(self, body: dict[str, Any], metadata: dict[str, Any]) -> str:
        value = self._clarification_config_value(body, metadata, "answer_source", "source")
        return str(value or "operator_confirmed")

    def _clarification_config_value(self, body: dict[str, Any], metadata: dict[str, Any], *keys: str) -> Any:
        for context in self._clarification_contexts(body, metadata):
            for key in keys:
                if key in context and context.get(key) not in (None, ""):
                    return context.get(key)
        return self._clarification_message_config_value(body, *keys)

    def _clarification_nested_config_value(self, body: dict[str, Any], metadata: dict[str, Any], *keys: str) -> Any:
        body_metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
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

    def _clarification_contexts(self, body: dict[str, Any], metadata: dict[str, Any]) -> list[dict[str, Any]]:
        contexts: list[dict[str, Any]] = []
        body_metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
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

    def _clarification_message_config_value(self, body: dict[str, Any], *keys: str) -> Any:
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

    def _case_group_id(self, body: dict[str, Any], metadata: dict[str, Any]) -> str | None:
        body_metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        contexts = [
            body.get("broker_reports_gate1") if isinstance(body.get("broker_reports_gate1"), dict) else {},
            metadata.get("broker_reports_gate1") if isinstance(metadata.get("broker_reports_gate1"), dict) else {},
            body_metadata.get("broker_reports_gate1") if isinstance(body_metadata.get("broker_reports_gate1"), dict) else {},
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
        body_metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
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
        private_records = [record for record in records if record.visibility == "private_case"]
        if not private_records or not manifest.private_slice_refs:
            raise RuntimeError("private_slice_artifacts_missing")
        if not all(record.payload_ref and record.payload is None for record in private_records):
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
        if handoff_record.validation_status == "blocked" or handoff_record.lifecycle_status == "blocked":
            self._assert_resolver_denies(
                resolver,
                manifest.gate2_handoff_ref,
                context,
                "artifact_blocked",
            )
            handoff = store.read_payload(handoff_record)
        else:
            handoff = resolver.resolve(manifest.gate2_handoff_ref, context)["payload"]
        handoff_private_refs = [str(ref) for ref in handoff.get("private_slice_refs") or [] if ref]
        manifest_private_refs = {str(ref) for ref in manifest.private_slice_refs}
        if handoff.get("handoff_status") == "blocked":
            if handoff_private_refs:
                raise RuntimeError("blocked_gate2_handoff_private_refs_present")
        else:
            if not handoff_private_refs:
                raise RuntimeError("gate2_handoff_private_refs_missing")
            if any(private_ref not in manifest_private_refs for private_ref in handoff_private_refs):
                raise RuntimeError("gate2_handoff_private_refs_missing")
            for private_ref in handoff_private_refs:
                resolver.resolve(private_ref, context)
        clarification_refs = [str(ref) for ref in handoff.get("clarification_resolution_refs") or [] if ref]
        if any(private_ref not in manifest_private_refs for private_ref in clarification_refs):
            raise RuntimeError("gate2_handoff_clarification_refs_missing")
        for private_ref in clarification_refs:
            resolver.resolve(private_ref, context)
        if "```json" in str(handoff) or any(marker and marker in str(handoff) for marker in private_markers):
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
        store.expire_artifacts(now=datetime.now(timezone.utc) + timedelta(seconds=2))
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
        purged_ids = store.purge_run(probe_context.normalization_run_id)
        purged_private_record = store.get_record_unchecked(purge_private_ref)
        if not purged_ids or purge_payload_path.exists() or purged_private_record is None:
            raise RuntimeError("purge_probe_failed")
        if purged_private_record.storage_backend != "none_tombstone" or purged_private_record.payload_ref:
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

    def _append_message_file_candidates(self, candidates: list[Any], source: Any) -> None:
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
                if isinstance(message, dict) and self._safe_len(message.get("files")) > 0
            ),
        }
        source_policy = self._source_policy_context(body, metadata)
        if source_policy:
            context["source_policy"] = source_policy
        return context

    def _safe_len(self, value: Any) -> int:
        return len(value) if isinstance(value, list) else 0

    def _source_policy_context(self, body: dict, metadata: dict) -> dict[str, Any]:
        body_metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
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
            result["explicit"] = self._optional_bool(value.get("explicit"), default=False)
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
            sanitized_hints = [self._sanitize_source_policy_hint(item) for item in hints[:200]]
            result["safe_registry_role_hints"] = [item for item in sanitized_hints if item]
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
        if sha256 is not None and "sha256_prefix" not in result and "hash_prefix" not in result:
            result["sha256_prefix"] = str(sha256)[:12]
        if "methodology_or_output_candidate" in hint:
            result["methodology_or_output_candidate"] = self._optional_bool(
                hint.get("methodology_or_output_candidate"),
                default=False,
            )
        secondary_roles = hint.get("secondary_role_candidates")
        if isinstance(secondary_roles, list):
            result["secondary_role_candidates"] = [
                str(item)[:96]
                for item in secondary_roles[:10]
                if item is not None
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
        user_id = self._user_id(user, metadata)
        chat_id = (
            metadata.get("chat_id")
            or kwargs.get("__chat_id__")
            or kwargs.get("chat_id")
            or body.get("chat_id")
            or metadata.get("session_id")
        )
        body_metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        case_id = metadata.get("case_id") or body_metadata.get("case_id") or body.get("case_id")
        workspace_model_id = metadata.get("model_id") or body.get("model") or body.get("model_id")
        return ArtifactAccessContext(
            user_id=user_id,
            normalization_run_id=normalization_run_id,
            case_id=str(case_id) if case_id else None,
            chat_id=str(chat_id) if chat_id else None,
            workspace_model_id=str(workspace_model_id) if workspace_model_id else None,
            allow_private=True,
        )

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

    def _source_file_refs(self, file_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        file_obj = file_ref.get("_private_file_obj")
        if isinstance(file_obj, dict):
            inline = self._inline_bytes(file_obj)
            if inline is not None:
                return inline

        if not self.valves.allow_upload_path_access:
            raise BytesUnavailable("upload_path_access_disabled")

        candidate_result = self._upload_root_candidate(file_ref)
        if candidate_result.get("status") == "blocked":
            raise BytesUnavailable(str(candidate_result.get("reason") or "upload_candidate_blocked"))
        candidate = candidate_result.get("path")
        if isinstance(candidate, Path) and candidate.exists() and candidate.is_file():
            return candidate.read_bytes()
        raise BytesUnavailable("upload_file_not_found")

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
