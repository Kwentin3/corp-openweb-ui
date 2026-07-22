from __future__ import annotations

import base64
import copy
import hashlib
import json
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .contracts import stable_digest
from .pdf_dual_vlm_fact_providers import (
    DEFAULT_GEMINI_MODEL_ID,
    DEFAULT_OPENAI_MODEL_ID,
    PdfDualVlmFactProviderConfig,
    PdfDualVlmFactProviderFactory,
)
from .pdf_table_raster import PDF_TABLE_CANDIDATE_SCHEMA
from .semantic_visual_table_contracts import (
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT,
    SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION,
    SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION,
    parse_semantic_table_transcription,
    semantic_table_transcription_boundary_errors,
    semantic_table_transcription_model_view,
    semantic_table_transcription_schema,
)


PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION = (
    "pdf_semantic_vlm_provider_selection_v1"
)
PDF_DUAL_VLM_OPENAI_POLICY_VERSION = "pdf_semantic_vlm_openai_policy_v1"
PDF_DUAL_VLM_RUNTIME_POLICY_VERSION = "pdf_semantic_vlm_runtime_policy_v1"
PDF_DUAL_VLM_DECISION_SCHEMA = "broker_reports_pdf_semantic_vlm_decision_v1"
PDF_DUAL_VLM_EXECUTION_SCHEMA = "broker_reports_pdf_semantic_vlm_execution_v1"
PDF_DUAL_VLM_RUN_SCHEMA = "broker_reports_pdf_semantic_vlm_run_v1"
PDF_DUAL_VLM_VALIDATOR_VERSION = "pdf_semantic_vlm_boundary_validator_v1"
PDF_SEMANTIC_VLM_PRIVATE_EVIDENCE_SCHEMA = (
    "broker_reports_pdf_semantic_vlm_private_provider_evidence_v1"
)
PDF_DUAL_VLM_PROMPT_ID = "pdf_semantic_visual_table_transcription"

DECISION_STATUSES = frozenset(
    {
        "semantic_transcription_valid",
        "proposal_validated_and_accepted",
        "proposal_requires_review",
        "proposal_rejected",
        "malformed_provider_output",
        "provider_refusal_or_incomplete",
        "unresolved_visual_scope",
        "unsupported_visual_layout",
    }
)
PROVIDER_ORDER = ("gemini", "openai")
DEFAULT_PROVIDER_ORDER = ("gemini",)
OPENAI_INVOCATION_POLICIES = frozenset(
    {
        "disabled",
        "fallback_on_gemini_terminal_failure",
        "diagnostic_control",
    }
)
REFUSAL_OR_INCOMPLETE_FAILURES = frozenset(
    {
        "provider_refusal",
        "provider_incomplete",
        "provider_non_terminal",
        "timeout",
        "timeout_or_transport",
        "response_budget",
    }
)
MALFORMED_FAILURES = frozenset(
    {
        "parse_failure",
        "provider_invalid_json",
        "semantic_schema_violation",
        "resolved_model_mismatch",
    }
)

FACTORY_REQUIRED = (
    "PdfDualVlmRuntimeFactory.create_for_openwebui is the only maintained "
    "semantic visual-table runtime entrypoint"
)
FORBIDDEN = (
    "Callers must not construct provider payloads, resolve credentials, upload "
    "whole documents, retry, merge or repair provider output, invoke OpenAI "
    "without the versioned policy, or promote provider agreement to authority"
)


class PdfDualVlmRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfDualVlmRuntimeConfig:
    enabled: bool = False
    provider_selection_policy_version: str = (
        PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION
    )
    execution_mode: str = "gemini_master"
    primary_provider: str = "gemini"
    review_provider: str = "openai"
    openai_policy_version: str = PDF_DUAL_VLM_OPENAI_POLICY_VERSION
    openai_invocation_policy: str = "disabled"
    gemini_model_id: str = DEFAULT_GEMINI_MODEL_ID
    openai_model_id: str = DEFAULT_OPENAI_MODEL_ID
    timeout_seconds: int = 240
    maximum_output_tokens: int = 16_384
    maximum_counted_input_tokens: int = 24_000
    maximum_candidates: int = 8


@dataclass(frozen=True)
class PdfDualVlmRuntimeResult:
    safe_summary: dict[str, Any]
    private_decisions: list[dict[str, Any]]
    private_provider_evidence: list[dict[str, Any]]


class PdfDualVlmRuntimeFactory:
    def __init__(self, config: PdfDualVlmRuntimeConfig | None = None) -> None:
        self.config = config or PdfDualVlmRuntimeConfig()
        self._validate_config()

    def create_for_openwebui(
        self,
        request: Any,
        *,
        provider_budget=None,
    ) -> "PdfDualVlmRuntime":
        provider_config = PdfDualVlmFactProviderConfig(
            gemini_model_id=self.config.gemini_model_id,
            openai_model_id=self.config.openai_model_id,
            timeout_seconds=self.config.timeout_seconds,
            extraction_maximum_output_tokens=self.config.maximum_output_tokens,
            maximum_counted_input_tokens=self.config.maximum_counted_input_tokens,
        )
        bundle = PdfDualVlmFactProviderFactory(provider_config).create_for_openwebui(
            request,
            include_openai=self.config.openai_invocation_policy != "disabled",
        )
        return self._create(
            gemini=bundle.gemini,
            openai=bundle.openai,
            provider_budget=provider_budget,
        )

    def create_with_providers(
        self,
        *,
        gemini: Any,
        openai: Any = None,
        provider_budget=None,
    ) -> "PdfDualVlmRuntime":
        """Explicit provider seam for deterministic transport/decision tests."""

        return self._create(
            gemini=gemini,
            openai=openai,
            provider_budget=provider_budget,
        )

    def _create(
        self,
        *,
        gemini: Any,
        openai: Any,
        provider_budget,
    ) -> "PdfDualVlmRuntime":
        if self.config.openai_invocation_policy != "disabled" and openai is None:
            raise PdfDualVlmRuntimeError("pdf_semantic_vlm_openai_provider_required")
        return PdfDualVlmRuntime(
            self.config,
            gemini=gemini,
            openai=openai,
            provider_budget=provider_budget,
        )

    def _validate_config(self) -> None:
        if (
            self.config.provider_selection_policy_version
            != PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION
            or self.config.execution_mode not in {
                "gemini_master",
                "diagnostic_control",
            }
            or self.config.primary_provider != "gemini"
            or self.config.review_provider != "openai"
            or self.config.openai_policy_version
            != PDF_DUAL_VLM_OPENAI_POLICY_VERSION
            or self.config.openai_invocation_policy
            not in OPENAI_INVOCATION_POLICIES
            or (
                self.config.execution_mode == "diagnostic_control"
                and self.config.openai_invocation_policy != "diagnostic_control"
            )
            or (
                self.config.execution_mode == "gemini_master"
                and self.config.openai_invocation_policy == "diagnostic_control"
            )
        ):
            raise PdfDualVlmRuntimeError(
                "pdf_dual_vlm_provider_selection_policy_invalid"
            )
        if (
            self.config.timeout_seconds < 1
            or self.config.timeout_seconds > 600
            or self.config.maximum_output_tokens < 1
            or self.config.maximum_output_tokens > 32_768
            or self.config.maximum_counted_input_tokens < 1
            or self.config.maximum_counted_input_tokens > 128_000
            or self.config.maximum_candidates < 1
            or self.config.maximum_candidates > 32
        ):
            raise PdfDualVlmRuntimeError("pdf_dual_vlm_runtime_budget_invalid")


class PdfDualVlmRuntime:
    def __init__(
        self,
        config: PdfDualVlmRuntimeConfig,
        *,
        gemini: Any,
        openai: Any,
        provider_budget,
    ):
        self.config = config
        self.providers = {"gemini": gemini}
        if openai is not None:
            self.providers["openai"] = openai
        self.provider_budget = provider_budget

    def run(self, candidates: list[dict[str, Any]]) -> PdfDualVlmRuntimeResult:
        if not self.config.enabled:
            return PdfDualVlmRuntimeResult(
                safe_summary=self._summary(
                    status="disabled",
                    candidates_total=0,
                    decisions=[],
                    qualifications=None,
                ),
                private_decisions=[],
                private_provider_evidence=[],
            )
        if not isinstance(candidates, list):
            raise PdfDualVlmRuntimeError("pdf_dual_vlm_candidates_invalid")
        if len(candidates) > self.config.maximum_candidates:
            raise PdfDualVlmRuntimeError("pdf_dual_vlm_candidate_budget_exceeded")
        if not candidates:
            return PdfDualVlmRuntimeResult(
                safe_summary=self._summary(
                    status="completed",
                    candidates_total=0,
                    decisions=[],
                    qualifications=None,
                ),
                private_decisions=[],
                private_provider_evidence=[],
            )

        qualifications = self._qualify_providers()
        decisions: list[dict[str, Any]] = []
        private_provider_evidence: list[dict[str, Any]] = []
        for candidate in candidates:
            decision, candidate_evidence = self._run_candidate(
                candidate,
                qualifications=qualifications,
            )
            decisions.append(decision)
            private_provider_evidence.extend(candidate_evidence)
        return PdfDualVlmRuntimeResult(
            safe_summary=self._summary(
                status="completed",
                candidates_total=len(candidates),
                decisions=decisions,
                qualifications=qualifications,
            ),
            private_decisions=decisions,
            private_provider_evidence=private_provider_evidence,
        )

    def _qualify_providers(self) -> dict[str, dict[str, Any]]:
        qualifications: dict[str, dict[str, Any]] = {}
        provider_names = ["gemini"]
        if self.config.openai_invocation_policy != "disabled":
            provider_names.append("openai")
        for provider_name in provider_names:
            try:
                with self._provider_budget_context(provider_name):
                    value = self.providers[provider_name].qualify()
            except Exception as exc:
                if str(getattr(exc, "code", "")).startswith("workload_"):
                    raise
                raise PdfDualVlmRuntimeError(
                    f"pdf_dual_vlm_{provider_name}_qualification_failed"
                ) from exc
            if (
                not isinstance(value, dict)
                or value.get("status") != "qualified"
                or value.get("exact_model_match") is not True
                or value.get("image_input_supported") is not True
                or value.get("structured_output_supported") is not True
                or value.get("native_provider_transport") is not True
                or value.get("credentials_from_openwebui_connection") is not True
                or value.get("hidden_retry") is not False
                or value.get("provider_failover") is not False
            ):
                raise PdfDualVlmRuntimeError(
                    f"pdf_dual_vlm_{provider_name}_not_qualified"
                )
            qualifications[provider_name] = copy.deepcopy(value)
        return qualifications

    def _run_candidate(
        self,
        candidate: dict[str, Any],
        *,
        qualifications: dict[str, dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        try:
            bounded = _bounded_candidate(candidate)
        except PdfDualVlmRuntimeError as exc:
            return (
                self._decision(
                    status="unresolved_visual_scope",
                    reason_codes=[exc.code],
                    lineage=None,
                    executions=[],
                    proposals={},
                    comparison=None,
                ),
                [],
            )

        manifest = bounded["manifest"]
        png_bytes = bounded["png_bytes"]
        table_id = str(manifest["candidate_ref"])
        model_view = semantic_table_transcription_model_view()
        output_schema = semantic_table_transcription_schema()
        lineage = _lineage(manifest)
        executions: list[dict[str, Any]] = []
        proposals: dict[str, dict[str, Any] | None] = {}
        failures: dict[str, str] = {}
        evidence_seeds: list[dict[str, Any]] = []
        gemini_record, gemini_proposal, gemini_failure, gemini_evidence = (
            self._invoke_provider(
            provider_name="gemini",
            invocation_role="master",
            provider=self.providers["gemini"],
            qualification=qualifications["gemini"],
            lineage=lineage,
            model_view=model_view,
            output_schema=output_schema,
            png_bytes=png_bytes,
            table_id=table_id,
            )
        )
        executions.append(gemini_record)
        evidence_seeds.append(gemini_evidence)
        proposals["gemini"] = gemini_proposal
        if gemini_failure:
            failures["gemini"] = gemini_failure

        selected_provider = "gemini" if gemini_proposal is not None else None
        openai_invocation_role: str | None = None
        should_call_openai = False
        if self.config.openai_invocation_policy == "diagnostic_control":
            should_call_openai = True
            openai_invocation_role = "control"
        elif (
            self.config.openai_invocation_policy
            == "fallback_on_gemini_terminal_failure"
            and gemini_failure is not None
        ):
            should_call_openai = True
            openai_invocation_role = "fallback"

        if should_call_openai:
            openai_record, openai_proposal, openai_failure, openai_evidence = (
                self._invoke_provider(
                provider_name="openai",
                invocation_role=str(openai_invocation_role),
                provider=self.providers["openai"],
                qualification=qualifications["openai"],
                lineage=lineage,
                model_view=model_view,
                output_schema=output_schema,
                png_bytes=png_bytes,
                table_id=table_id,
                )
            )
            executions.append(openai_record)
            evidence_seeds.append(openai_evidence)
            proposals["openai"] = openai_proposal
            if openai_failure:
                failures["openai"] = openai_failure
            if openai_invocation_role == "fallback" and openai_proposal is not None:
                selected_provider = "openai"

        if selected_provider is not None:
            status = "semantic_transcription_valid"
            reasons = [f"{selected_provider}_semantic_transcription_valid"]
            if openai_invocation_role == "control":
                control_failure = failures.get("openai")
                reasons.append(
                    "openai_diagnostic_control_valid"
                    if control_failure is None
                    else f"openai_diagnostic_control_{control_failure}"
                )
            elif openai_invocation_role == "fallback":
                reasons.extend(
                    [
                        f"gemini_{gemini_failure}",
                        "openai_explicit_fallback_selected",
                    ]
                )
        else:
            status = _terminal_status(failures.values())
            reasons = [
                f"{provider_name}_{failures[provider_name]}"
                for provider_name in PROVIDER_ORDER
                if provider_name in failures
            ]

        decision = self._decision(
            status=status,
            reason_codes=reasons,
            lineage=lineage,
            executions=executions,
            proposals=proposals,
            comparison=None,
            selected_provider=selected_provider,
            openai_invocation_role=openai_invocation_role,
        )
        evidence = [
            _bind_private_provider_evidence(decision, item)
            for item in evidence_seeds
        ]
        return decision, evidence

    def _invoke_provider(
        self,
        *,
        provider_name: str,
        invocation_role: str,
        provider: Any,
        qualification: dict[str, Any],
        lineage: dict[str, Any],
        model_view: dict[str, Any],
        output_schema: dict[str, Any],
        png_bytes: bytes,
        table_id: str,
    ) -> tuple[
        dict[str, Any],
        dict[str, Any] | None,
        str | None,
        dict[str, Any],
    ]:
        started = datetime.now(timezone.utc)
        preflight: dict[str, Any] | None = None
        response: dict[str, Any] | None = None
        failure_class: str | None = None
        validator_errors: list[str] = []
        proposal: dict[str, Any] | None = None
        task_id = "pdfdualvlm_" + stable_digest(
            [
                PDF_DUAL_VLM_RUNTIME_POLICY_VERSION,
                provider_name,
                lineage["crop_sha256"],
                table_id,
                qualification.get("requested_model_id"),
                SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION,
            ],
            length=24,
        )
        try:
            with self._provider_budget_context(provider_name):
                preflight = provider.count_tokens(
                    model_view=model_view,
                    output_schema=output_schema,
                    png_bytes=png_bytes,
                    crop_sha256=lineage["crop_sha256"],
                )
                response = provider.invoke(
                    task_id=task_id,
                    model_view=model_view,
                    output_schema=output_schema,
                    png_bytes=png_bytes,
                    crop_sha256=lineage["crop_sha256"],
                    attempt_number=1,
                    attempt_lineage=[],
                )
            attempt = _object(response.get("attempt"))
            raw_failure = attempt.get("terminal_failure_class")
            if isinstance(raw_failure, str) and raw_failure:
                failure_class = raw_failure
            else:
                output = response.get("json_output")
                validator_errors = semantic_table_transcription_boundary_errors(output)
                if validator_errors:
                    failure_class = "semantic_schema_violation"
                else:
                    proposal = parse_semantic_table_transcription(output)
        except Exception as exc:
            if str(getattr(exc, "code", "")).startswith("workload_"):
                raise
            raw = getattr(exc, "failure_class", None)
            failure_class = str(raw or "provider_operation_failed")

        ended = datetime.now(timezone.utc)
        attempt = _object(response.get("attempt")) if response else {}
        record = {
            "schema_version": PDF_DUAL_VLM_EXECUTION_SCHEMA,
            "policy_version": PDF_DUAL_VLM_RUNTIME_POLICY_VERSION,
            "task_id": task_id,
            "source_lineage_hash": sha256_json(lineage),
            "source_ref": lineage["source_ref"],
            "source_sha256": lineage["source_sha256"],
            "page_number": lineage["page_number"],
            "crop_id": lineage["crop_id"],
            "crop_sha256": lineage["crop_sha256"],
            "input_hash": lineage["crop_sha256"],
            "provider": provider_name,
            "invocation_role": invocation_role,
            "provider_profile": attempt.get("provider_profile")
            or qualification.get("provider_profile"),
            "provider_profile_revision": attempt.get("provider_profile_revision")
            or qualification.get("provider_profile_revision"),
            "requested_model_id": attempt.get("model_requested")
            or qualification.get("requested_model_id"),
            "resolved_model_id": attempt.get("model_resolved")
            or qualification.get("resolved_model_id"),
            "prompt_id": PDF_DUAL_VLM_PROMPT_ID,
            "prompt_version": SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION,
            "prompt_hash": hashlib.sha256(
                SEMANTIC_TABLE_TRANSCRIPTION_PROMPT.encode("utf-8")
            ).hexdigest(),
            "model_view_hash": sha256_json(model_view),
            "output_schema_version": SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION,
            "canonical_schema_hash": attempt.get("canonical_schema_hash")
            or _object(preflight).get("canonical_schema_hash")
            or sha256_json(output_schema),
            "provider_adapted_schema_hash": attempt.get("adapted_schema_hash")
            or _object(preflight).get("adapted_schema_hash"),
            "schema_transform_count": attempt.get("schema_transform_count")
            if attempt
            else _object(preflight).get("schema_transform_count"),
            "maximum_output_tokens": self.config.maximum_output_tokens,
            "maximum_counted_input_tokens": self.config.maximum_counted_input_tokens,
            "transport_timeout_seconds": self.config.timeout_seconds,
            "deadline_policy": "per_native_request_no_retry",
            "operation_started_at": started.isoformat(),
            "operation_deadline_at": (
                started + timedelta(seconds=self.config.timeout_seconds)
            ).isoformat(),
            "operation_ended_at": ended.isoformat(),
            "attempt_number": attempt.get("attempt_number", 1),
            "attempt_lineage": copy.deepcopy(attempt.get("attempt_lineage") or []),
            "preflight": _safe_preflight(preflight),
            "usage": copy.deepcopy(attempt.get("usage") or {}),
            "latency_ms": attempt.get("duration_ms"),
            "terminal_provider_status": failure_class or "completed",
            "finish_reason": attempt.get("finish_reason"),
            "response_hash": response.get("response_hash") if response else None,
            "validator_result": {
                "validator_version": PDF_DUAL_VLM_VALIDATOR_VERSION,
                "status": "passed" if proposal is not None else "failed",
                "error_codes": validator_errors,
                "semantic_transcription_hash": (
                    sha256_json(proposal) if proposal is not None else None
                ),
            },
            "hidden_retry": False,
            "provider_failover": False,
            "provider_switch": False,
            "whole_document_uploaded": False,
        }
        record["execution_hash"] = sha256_json(record)
        evidence_seed = {
            "execution_hash": record["execution_hash"],
            "provider": provider_name,
            "invocation_role": invocation_role,
            "input_hash": lineage["crop_sha256"],
            "response_hash": record["response_hash"],
            "terminal_provider_status": record["terminal_provider_status"],
            "raw_provider_response": copy.deepcopy(
                response.get("raw_private_response") if response else None
            ),
            "parsed_semantic_response": copy.deepcopy(proposal),
        }
        return record, proposal, failure_class, evidence_seed

    def _provider_budget_context(self, provider_name: str):
        if self.provider_budget is None:
            return nullcontext()
        return self.provider_budget(provider_name)

    def _decision(
        self,
        *,
        status: str,
        reason_codes: list[str],
        lineage: dict[str, Any] | None,
        executions: list[dict[str, Any]],
        proposals: dict[str, dict[str, Any] | None],
        comparison: dict[str, Any] | None,
        selected_provider: str | None = None,
        openai_invocation_role: str | None = None,
    ) -> dict[str, Any]:
        if status not in DECISION_STATUSES:
            raise PdfDualVlmRuntimeError("pdf_dual_vlm_decision_status_invalid")
        input_hash = lineage.get("crop_sha256") if lineage else None
        decision_id = "pdfdualvlmdecision_" + stable_digest(
            [
                PDF_DUAL_VLM_DECISION_SCHEMA,
                status,
                input_hash,
                [item.get("execution_hash") for item in executions],
                reason_codes,
            ],
            length=24,
        )
        decision = {
            "schema_version": PDF_DUAL_VLM_DECISION_SCHEMA,
            "policy_version": PDF_DUAL_VLM_RUNTIME_POLICY_VERSION,
            "decision_id": decision_id,
            "status": status,
            "reason_codes": sorted(set(reason_codes)),
            "source_lineage": copy.deepcopy(lineage),
            "input_hash": input_hash,
            "provider_selection": self._provider_selection(),
            "executions": copy.deepcopy(executions),
            "proposals": copy.deepcopy(proposals),
            "comparison": copy.deepcopy(comparison),
            "selected_provider": selected_provider,
            "semantic_transcription": copy.deepcopy(
                proposals.get(selected_provider) if selected_provider else None
            ),
            "openai_invocation_role": openai_invocation_role,
            "deterministic_validator": {
                "validator_version": PDF_DUAL_VLM_VALIDATOR_VERSION,
                "provider_contracts_valid": bool(executions)
                and all(
                    _object(item.get("validator_result")).get("status") == "passed"
                    for item in executions
                ),
                "same_bounded_input_for_all_providers": bool(executions)
                and len({item.get("input_hash") for item in executions}) == 1,
                "selected_provider_contract_valid": selected_provider is not None
                and any(
                    item.get("provider") == selected_provider
                    and _object(item.get("validator_result")).get("status") == "passed"
                    for item in executions
                ),
                "semantic_response_contract_passed": selected_provider is not None,
                "source_to_table_accounting": "unavailable",
                "canonical_promotion_allowed": False,
            },
            "canonical_table": None,
            "provider_proposal_canonical_authority": False,
            "review_required": status != "semantic_transcription_valid",
            "hidden_retry": False,
            "provider_failover": False,
            "provider_merge": False,
            "openai_fallback_used": openai_invocation_role == "fallback",
            "whole_document_provider_upload": False,
        }
        decision["decision_hash"] = sha256_json(decision)
        validation_errors = validate_pdf_dual_vlm_decision(decision)
        if validation_errors:
            raise PdfDualVlmRuntimeError(validation_errors[0])
        return decision

    def _provider_selection(self) -> dict[str, Any]:
        return {
            "policy_version": self.config.provider_selection_policy_version,
            "execution_mode": self.config.execution_mode,
            "master_provider": self.config.primary_provider,
            "master_model_id": self.config.gemini_model_id,
            "optional_provider": self.config.review_provider,
            "optional_model_id": self.config.openai_model_id,
            "default_provider_order": list(DEFAULT_PROVIDER_ORDER),
            "openai_policy_version": self.config.openai_policy_version,
            "openai_invocation_policy": self.config.openai_invocation_policy,
            "mandatory_consensus": False,
            "hidden_retry": False,
            "provider_failover": False,
            "provider_switch": False,
            "provider_merge": False,
        }

    def _summary(
        self,
        *,
        status: str,
        candidates_total: int,
        decisions: list[dict[str, Any]],
        qualifications: dict[str, dict[str, Any]] | None,
    ) -> dict[str, Any]:
        status_counts = {
            decision_status: sum(
                item.get("status") == decision_status for item in decisions
            )
            for decision_status in sorted(DECISION_STATUSES)
        }
        safe_qualifications = None
        if qualifications is not None:
            safe_qualifications = {
                name: {
                    key: value.get(key)
                    for key in (
                        "status",
                        "provider_profile",
                        "provider_profile_revision",
                        "requested_model_id",
                        "resolved_model_id",
                        "exact_model_match",
                        "image_input_supported",
                        "structured_output_supported",
                        "maximum_output_tokens",
                        "maximum_input_tokens",
                        "http_status",
                        "response_hash",
                        "native_provider_transport",
                        "credentials_from_openwebui_connection",
                        "hidden_retry",
                        "provider_failover",
                    )
                }
                for name, value in qualifications.items()
            }
        summary = {
            "schema_version": PDF_DUAL_VLM_RUN_SCHEMA,
            "policy_version": PDF_DUAL_VLM_RUNTIME_POLICY_VERSION,
            "enabled": self.config.enabled,
            "status": status,
            "candidates_total": candidates_total,
            "decisions_total": len(decisions),
            "decision_status_counts": status_counts,
            "provider_selection": self._provider_selection(),
            "provider_qualifications": safe_qualifications,
            "decision_hashes": [item.get("decision_hash") for item in decisions],
            "provider_proposal_canonical_authority": False,
            "canonical_tables_published": 0,
            "semantic_transcriptions_valid": status_counts.get(
                "semantic_transcription_valid", 0
            ),
            "whole_document_provider_uploads": 0,
            "hidden_retries": 0,
            "provider_failovers": 0,
            "provider_merges": 0,
            "openai_fallbacks": sum(
                item.get("openai_fallback_used") is True for item in decisions
            ),
            "openai_control_calls": sum(
                item.get("openai_invocation_role") == "control" for item in decisions
            ),
            "paddle_dependency": False,
        }
        summary["configuration_hash"] = sha256_json(
            {
                "policy_version": summary["policy_version"],
                "provider_selection": summary["provider_selection"],
                "maximum_output_tokens": self.config.maximum_output_tokens,
                "maximum_counted_input_tokens": (
                    self.config.maximum_counted_input_tokens
                ),
                "maximum_candidates": self.config.maximum_candidates,
                "prompt_version": SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION,
                "output_schema_version": (
                    SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION
                ),
            }
        )
        return summary


def _bounded_candidate(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict) or set(candidate) != {
        "manifest",
        "private_png_base64",
    }:
        raise PdfDualVlmRuntimeError("pdf_dual_vlm_crop_envelope_invalid")
    manifest = candidate.get("manifest")
    encoded = candidate.get("private_png_base64")
    if not isinstance(manifest, dict) or not isinstance(encoded, str):
        raise PdfDualVlmRuntimeError("pdf_dual_vlm_crop_envelope_invalid")
    if (
        manifest.get("schema_version") != PDF_TABLE_CANDIDATE_SCHEMA
        or manifest.get("semantic_interpretation_performed") is not False
        or manifest.get("lossless") is not True
        or manifest.get("silent_resize_performed") is not False
        or manifest.get("dpi") != 150
    ):
        raise PdfDualVlmRuntimeError("pdf_dual_vlm_crop_contract_invalid")
    required_strings = (
        "crop_id",
        "document_ref",
        "pdf_sha256",
        "candidate_ref",
        "png_sha256",
        "manifest_hash",
        "renderer",
        "renderer_version",
    )
    if any(
        not isinstance(manifest.get(key), str) or not manifest.get(key)
        for key in required_strings
    ):
        raise PdfDualVlmRuntimeError("pdf_dual_vlm_crop_lineage_invalid")
    if (
        not isinstance(manifest.get("page_number"), int)
        or isinstance(manifest.get("page_number"), bool)
        or int(manifest["page_number"]) < 1
        or not isinstance(manifest.get("width"), int)
        or not isinstance(manifest.get("height"), int)
        or int(manifest["width"]) < 1
        or int(manifest["height"]) < 1
    ):
        raise PdfDualVlmRuntimeError("pdf_dual_vlm_crop_lineage_invalid")
    expected_manifest_hash = manifest.get("manifest_hash")
    unhashed = copy.deepcopy(manifest)
    unhashed.pop("manifest_hash", None)
    if sha256_json(unhashed) != expected_manifest_hash:
        raise PdfDualVlmRuntimeError("pdf_dual_vlm_crop_manifest_hash_mismatch")
    try:
        png_bytes = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise PdfDualVlmRuntimeError("pdf_dual_vlm_crop_bytes_invalid") from exc
    if (
        not png_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        or hashlib.sha256(png_bytes).hexdigest() != manifest.get("png_sha256")
        or len(png_bytes) != manifest.get("png_bytes")
    ):
        raise PdfDualVlmRuntimeError("pdf_dual_vlm_crop_hash_mismatch")
    return {"manifest": copy.deepcopy(manifest), "png_bytes": png_bytes}


def _lineage(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "declared_scope": "one_table_crop",
        "source_ref": manifest["document_ref"],
        "source_sha256": manifest["pdf_sha256"],
        "page_number": manifest["page_number"],
        "crop_id": manifest["crop_id"],
        "candidate_ref": manifest["candidate_ref"],
        "crop_sha256": manifest["png_sha256"],
        "crop_manifest_hash": manifest["manifest_hash"],
        "declared_table_bbox": copy.deepcopy(manifest.get("declared_table_bbox")),
        "rendered_bbox": copy.deepcopy(manifest.get("rendered_bbox")),
        "renderer": manifest["renderer"],
        "renderer_version": manifest["renderer_version"],
        "dpi": manifest["dpi"],
        "image_width": manifest["width"],
        "image_height": manifest["height"],
        "whole_document_available": False,
    }


def _safe_preflight(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        key: copy.deepcopy(value.get(key))
        for key in (
            "total_tokens",
            "input_tokens",
            "http_status",
            "request_hash",
            "response_hash",
            "canonical_schema_hash",
            "adapted_schema_hash",
            "schema_transform_count",
            "model_requested",
            "transport_identity",
            "within_hard_guard",
        )
    }


def validate_pdf_dual_vlm_decision(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["pdf_dual_vlm_decision_invalid"]
    required = {
        "schema_version",
        "policy_version",
        "decision_id",
        "status",
        "reason_codes",
        "source_lineage",
        "input_hash",
        "provider_selection",
        "executions",
        "proposals",
        "comparison",
        "selected_provider",
        "semantic_transcription",
        "openai_invocation_role",
        "deterministic_validator",
        "canonical_table",
        "provider_proposal_canonical_authority",
        "review_required",
        "hidden_retry",
        "provider_failover",
        "provider_merge",
        "openai_fallback_used",
        "whole_document_provider_upload",
        "decision_hash",
    }
    errors: list[str] = []
    if set(value) != required:
        errors.append("pdf_dual_vlm_decision_fields_invalid")
    status = value.get("status")
    if (
        value.get("schema_version") != PDF_DUAL_VLM_DECISION_SCHEMA
        or value.get("policy_version") != PDF_DUAL_VLM_RUNTIME_POLICY_VERSION
        or status not in DECISION_STATUSES
    ):
        errors.append("pdf_dual_vlm_decision_invalid")
    selection = _object(value.get("provider_selection"))
    if (
        set(selection)
        != {
            "policy_version",
            "execution_mode",
            "master_provider",
            "master_model_id",
            "optional_provider",
            "optional_model_id",
            "default_provider_order",
            "openai_policy_version",
            "openai_invocation_policy",
            "mandatory_consensus",
            "hidden_retry",
            "provider_failover",
            "provider_switch",
            "provider_merge",
        }
        or selection.get("policy_version")
        != PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION
        or selection.get("execution_mode")
        not in {"gemini_master", "diagnostic_control"}
        or selection.get("master_provider") != "gemini"
        or selection.get("optional_provider") != "openai"
        or selection.get("default_provider_order") != list(DEFAULT_PROVIDER_ORDER)
        or selection.get("openai_policy_version")
        != PDF_DUAL_VLM_OPENAI_POLICY_VERSION
        or selection.get("openai_invocation_policy")
        not in OPENAI_INVOCATION_POLICIES
        or selection.get("mandatory_consensus") is not False
        or selection.get("hidden_retry") is not False
        or selection.get("provider_failover") is not False
        or selection.get("provider_switch") is not False
        or selection.get("provider_merge") is not False
    ):
        errors.append("pdf_dual_vlm_provider_selection_invalid")
    executions = value.get("executions")
    if not isinstance(executions, list) or len(executions) > 2:
        errors.append("pdf_dual_vlm_executions_invalid")
        executions = []
    for execution in executions:
        errors.extend(_execution_errors(execution))
    provider_names = [item.get("provider") for item in executions]
    if provider_names not in ([], ["gemini"], ["gemini", "openai"]):
        errors.append("pdf_dual_vlm_provider_order_invalid")
    proposals = value.get("proposals")
    if not isinstance(proposals, dict) or set(proposals) != set(provider_names):
        errors.append("pdf_dual_vlm_proposals_invalid")
        proposals = {}
    openai_role = value.get("openai_invocation_role")
    openai_policy = selection.get("openai_invocation_policy")
    if (
        openai_role not in {None, "control", "fallback"}
        or ("openai" not in provider_names and openai_role is not None)
        or ("openai" in provider_names and openai_role is None)
        or (openai_role == "control" and openai_policy != "diagnostic_control")
        or (
            openai_role == "fallback"
            and openai_policy != "fallback_on_gemini_terminal_failure"
        )
        or (openai_policy == "disabled" and "openai" in provider_names)
    ):
        errors.append("pdf_dual_vlm_openai_invocation_policy_invalid")
    validator = _object(value.get("deterministic_validator"))
    if (
        set(validator)
        != {
            "validator_version",
            "provider_contracts_valid",
            "same_bounded_input_for_all_providers",
            "selected_provider_contract_valid",
            "semantic_response_contract_passed",
            "source_to_table_accounting",
            "canonical_promotion_allowed",
        }
        or validator.get("validator_version") != PDF_DUAL_VLM_VALIDATOR_VERSION
        or validator.get("source_to_table_accounting") != "unavailable"
        or validator.get("canonical_promotion_allowed") is not False
    ):
        errors.append("pdf_dual_vlm_validator_envelope_invalid")
    selected_provider = value.get("selected_provider")
    semantic = value.get("semantic_transcription")
    semantic_valid = status == "semantic_transcription_valid"
    if semantic_valid:
        if (
            selected_provider not in provider_names
            or selected_provider not in {"gemini", "openai"}
            or semantic != proposals.get(selected_provider)
            or semantic_table_transcription_boundary_errors(semantic)
            or validator.get("selected_provider_contract_valid") is not True
            or validator.get("semantic_response_contract_passed") is not True
            or validator.get("same_bounded_input_for_all_providers") is not True
            or value.get("review_required") is not False
            or (selected_provider == "openai" and openai_role != "fallback")
            or (openai_role == "control" and selected_provider != "gemini")
        ):
            errors.append("pdf_dual_vlm_semantic_selection_invalid")
    elif (
        selected_provider is not None
        or semantic is not None
        or validator.get("selected_provider_contract_valid") is not False
        or validator.get("semantic_response_contract_passed") is not False
        or value.get("review_required") is not True
    ):
        errors.append("pdf_dual_vlm_terminal_selection_invalid")
    if (
        value.get("comparison") is not None
        or value.get("canonical_table") is not None
        or value.get("provider_proposal_canonical_authority") is not False
        or value.get("hidden_retry") is not False
        or value.get("provider_failover") is not False
        or value.get("provider_merge") is not False
        or value.get("openai_fallback_used") is not (openai_role == "fallback")
        or value.get("whole_document_provider_upload") is not False
    ):
        errors.append("pdf_dual_vlm_authority_or_transport_invalid")
    unhashed = copy.deepcopy(value)
    actual_hash = unhashed.pop("decision_hash", None)
    if not _is_sha256(actual_hash) or sha256_json(unhashed) != actual_hash:
        errors.append("pdf_dual_vlm_decision_hash_invalid")
    return sorted(set(errors))


def _execution_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["pdf_dual_vlm_execution_invalid"]
    required = {
        "schema_version",
        "policy_version",
        "task_id",
        "source_lineage_hash",
        "source_ref",
        "source_sha256",
        "page_number",
        "crop_id",
        "crop_sha256",
        "input_hash",
        "provider",
        "invocation_role",
        "provider_profile",
        "provider_profile_revision",
        "requested_model_id",
        "resolved_model_id",
        "prompt_id",
        "prompt_version",
        "prompt_hash",
        "model_view_hash",
        "output_schema_version",
        "canonical_schema_hash",
        "provider_adapted_schema_hash",
        "schema_transform_count",
        "maximum_output_tokens",
        "maximum_counted_input_tokens",
        "transport_timeout_seconds",
        "deadline_policy",
        "operation_started_at",
        "operation_deadline_at",
        "operation_ended_at",
        "attempt_number",
        "attempt_lineage",
        "preflight",
        "usage",
        "latency_ms",
        "terminal_provider_status",
        "finish_reason",
        "response_hash",
        "validator_result",
        "hidden_retry",
        "provider_failover",
        "provider_switch",
        "whole_document_uploaded",
        "execution_hash",
    }
    errors = []
    if set(value) != required:
        errors.append("pdf_dual_vlm_execution_fields_invalid")
    if (
        value.get("schema_version") != PDF_DUAL_VLM_EXECUTION_SCHEMA
        or value.get("policy_version") != PDF_DUAL_VLM_RUNTIME_POLICY_VERSION
        or value.get("provider") not in PROVIDER_ORDER
        or (
            value.get("provider") == "gemini"
            and value.get("invocation_role") != "master"
        )
        or (
            value.get("provider") == "openai"
            and value.get("invocation_role") not in {"control", "fallback"}
        )
        or value.get("input_hash") != value.get("crop_sha256")
        or value.get("prompt_id") != PDF_DUAL_VLM_PROMPT_ID
        or value.get("prompt_version")
        != SEMANTIC_TABLE_TRANSCRIPTION_PROMPT_VERSION
        or value.get("output_schema_version")
        != SEMANTIC_TABLE_TRANSCRIPTION_SCHEMA_VERSION
        or value.get("attempt_number") != 1
        or value.get("attempt_lineage") != []
        or value.get("deadline_policy") != "per_native_request_no_retry"
        or value.get("hidden_retry") is not False
        or value.get("provider_failover") is not False
        or value.get("provider_switch") is not False
        or value.get("whole_document_uploaded") is not False
        or "raw_private_response" in value
        or "text" in value
    ):
        errors.append("pdf_dual_vlm_execution_invalid")
    unhashed = copy.deepcopy(value)
    actual_hash = unhashed.pop("execution_hash", None)
    if not _is_sha256(actual_hash) or sha256_json(unhashed) != actual_hash:
        errors.append("pdf_dual_vlm_execution_hash_invalid")
    return errors


def _terminal_status(failures: Any) -> str:
    values = list(failures)
    if any(value in MALFORMED_FAILURES for value in values):
        return "malformed_provider_output"
    if any(value in REFUSAL_OR_INCOMPLETE_FAILURES for value in values):
        return "provider_refusal_or_incomplete"
    return "proposal_rejected"


def sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bind_private_provider_evidence(
    decision: dict[str, Any], seed: dict[str, Any]
) -> dict[str, Any]:
    evidence = {
        "schema_version": PDF_SEMANTIC_VLM_PRIVATE_EVIDENCE_SCHEMA,
        "decision_id": decision["decision_id"],
        **copy.deepcopy(seed),
    }
    evidence["evidence_hash"] = sha256_json(evidence)
    return evidence


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
