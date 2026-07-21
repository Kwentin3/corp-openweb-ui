from __future__ import annotations

import base64
import copy
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .contracts import stable_digest
from .pdf_dual_vlm_canonical_table_contracts import (
    CANONICAL_TABLE_SCHEMA_VERSION,
    NORMALIZER_PROMPT,
    PROMPT_CONTRACT_VERSION,
    canonical_table_schema,
    canonicalize_table,
    compare_tables,
    normalizer_model_view,
    sha256_json,
    validate_table_output,
)
from .pdf_dual_vlm_fact_providers import (
    DEFAULT_GEMINI_MODEL_ID,
    DEFAULT_OPENAI_MODEL_ID,
    PdfDualVlmFactProviderConfig,
    PdfDualVlmFactProviderFactory,
)
from .pdf_table_raster import PDF_TABLE_CANDIDATE_SCHEMA


PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION = "pdf_dual_vlm_provider_selection_v1"
PDF_DUAL_VLM_RUNTIME_POLICY_VERSION = "pdf_dual_vlm_runtime_policy_v1"
PDF_DUAL_VLM_DECISION_SCHEMA = "broker_reports_pdf_dual_vlm_decision_v1"
PDF_DUAL_VLM_EXECUTION_SCHEMA = "broker_reports_pdf_dual_vlm_execution_v1"
PDF_DUAL_VLM_RUN_SCHEMA = "broker_reports_pdf_dual_vlm_run_v1"
PDF_DUAL_VLM_VALIDATOR_VERSION = "pdf_dual_vlm_deterministic_validator_v1"
PDF_DUAL_VLM_PROMPT_ID = "pdf_dual_vlm_canonical_table_normalizer"

DECISION_STATUSES = frozenset(
    {
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
        "resolved_model_mismatch",
    }
)

FACTORY_REQUIRED = (
    "PdfDualVlmRuntimeFactory.create_for_openwebui is the only maintained "
    "dual-provider visual-table runtime entrypoint"
)
FORBIDDEN = (
    "Callers must not construct provider payloads, resolve credentials, upload "
    "whole documents, retry, fail over, hide disagreement, or promote provider "
    "agreement to canonical authority"
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
    execution_mode: str = "dual_provider_comparison"
    primary_provider: str = "gemini"
    review_provider: str = "openai"
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


class PdfDualVlmRuntimeFactory:
    def __init__(self, config: PdfDualVlmRuntimeConfig | None = None) -> None:
        self.config = config or PdfDualVlmRuntimeConfig()
        self._validate_config()

    def create_for_openwebui(self, request: Any) -> "PdfDualVlmRuntime":
        provider_config = PdfDualVlmFactProviderConfig(
            gemini_model_id=self.config.gemini_model_id,
            openai_model_id=self.config.openai_model_id,
            timeout_seconds=self.config.timeout_seconds,
            extraction_maximum_output_tokens=self.config.maximum_output_tokens,
            maximum_counted_input_tokens=self.config.maximum_counted_input_tokens,
        )
        bundle = PdfDualVlmFactProviderFactory(provider_config).create_for_openwebui(
            request
        )
        return self._create(gemini=bundle.gemini, openai=bundle.openai)

    def create_with_providers(self, *, gemini: Any, openai: Any) -> "PdfDualVlmRuntime":
        """Explicit provider seam for deterministic transport/decision tests."""

        return self._create(gemini=gemini, openai=openai)

    def _create(self, *, gemini: Any, openai: Any) -> "PdfDualVlmRuntime":
        return PdfDualVlmRuntime(self.config, gemini=gemini, openai=openai)

    def _validate_config(self) -> None:
        if (
            self.config.provider_selection_policy_version
            != PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION
            or self.config.execution_mode != "dual_provider_comparison"
            or self.config.primary_provider != "gemini"
            or self.config.review_provider != "openai"
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
    def __init__(self, config: PdfDualVlmRuntimeConfig, *, gemini: Any, openai: Any):
        self.config = config
        self.providers = {"gemini": gemini, "openai": openai}

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
            )

        qualifications = self._qualify_providers()
        decisions = [
            self._run_candidate(candidate, qualifications=qualifications)
            for candidate in candidates
        ]
        return PdfDualVlmRuntimeResult(
            safe_summary=self._summary(
                status="completed",
                candidates_total=len(candidates),
                decisions=decisions,
                qualifications=qualifications,
            ),
            private_decisions=decisions,
        )

    def _qualify_providers(self) -> dict[str, dict[str, Any]]:
        qualifications: dict[str, dict[str, Any]] = {}
        for provider_name in PROVIDER_ORDER:
            try:
                value = self.providers[provider_name].qualify()
            except Exception as exc:
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
    ) -> dict[str, Any]:
        try:
            bounded = _bounded_candidate(candidate)
        except PdfDualVlmRuntimeError as exc:
            return self._decision(
                status="unresolved_visual_scope",
                reason_codes=[exc.code],
                lineage=None,
                executions=[],
                proposals={},
                comparison=None,
            )

        manifest = bounded["manifest"]
        png_bytes = bounded["png_bytes"]
        table_id = str(manifest["candidate_ref"])
        model_view = normalizer_model_view(
            crop_sha256=str(manifest["png_sha256"]),
            table_id=table_id,
            image_width=int(manifest["width"]),
            image_height=int(manifest["height"]),
        )
        output_schema = canonical_table_schema()
        lineage = _lineage(manifest)
        executions: list[dict[str, Any]] = []
        proposals: dict[str, dict[str, Any] | None] = {}
        failures: dict[str, str] = {}

        for provider_name in PROVIDER_ORDER:
            record, proposal, failure_class = self._invoke_provider(
                provider_name=provider_name,
                provider=self.providers[provider_name],
                qualification=qualifications[provider_name],
                lineage=lineage,
                model_view=model_view,
                output_schema=output_schema,
                png_bytes=png_bytes,
                table_id=table_id,
            )
            executions.append(record)
            proposals[provider_name] = proposal
            if failure_class:
                failures[provider_name] = failure_class

        if any(value in MALFORMED_FAILURES for value in failures.values()):
            status = "malformed_provider_output"
            reasons = [
                f"{provider_name}_{failures[provider_name]}"
                for provider_name in PROVIDER_ORDER
                if provider_name in failures
            ]
            comparison = None
        elif any(
            value in REFUSAL_OR_INCOMPLETE_FAILURES for value in failures.values()
        ):
            status = "provider_refusal_or_incomplete"
            reasons = [
                f"{provider_name}_{failures[provider_name]}"
                for provider_name in PROVIDER_ORDER
                if provider_name in failures
            ]
            comparison = None
        elif failures:
            status = "proposal_requires_review"
            reasons = [
                f"{provider_name}_{failures[provider_name]}"
                for provider_name in PROVIDER_ORDER
                if provider_name in failures
            ]
            comparison = None
        else:
            comparison = compare_tables(
                proposals["gemini"] or {}, proposals["openai"] or {}
            )
            status = "proposal_requires_review"
            if comparison["FULL_TABLE_CONSENSUS"] is True:
                reasons = [
                    "provider_agreement_has_no_canonical_authority",
                    "source_to_table_accounting_unavailable",
                ]
            else:
                reasons = [
                    "provider_disagreement",
                    "source_to_table_accounting_unavailable",
                ]

        return self._decision(
            status=status,
            reason_codes=reasons,
            lineage=lineage,
            executions=executions,
            proposals=proposals,
            comparison=comparison,
        )

    def _invoke_provider(
        self,
        *,
        provider_name: str,
        provider: Any,
        qualification: dict[str, Any],
        lineage: dict[str, Any],
        model_view: dict[str, Any],
        output_schema: dict[str, Any],
        png_bytes: bytes,
        table_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any] | None, str | None]:
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
                PROMPT_CONTRACT_VERSION,
            ],
            length=24,
        )
        try:
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
                validator_errors = validate_table_output(output, table_id=table_id)
                if validator_errors:
                    failure_class = "parse_failure"
                else:
                    proposal = canonicalize_table(output, table_id=table_id)
        except Exception as exc:
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
            "provider_profile": attempt.get("provider_profile")
            or qualification.get("provider_profile"),
            "provider_profile_revision": attempt.get("provider_profile_revision")
            or qualification.get("provider_profile_revision"),
            "requested_model_id": attempt.get("model_requested")
            or qualification.get("requested_model_id"),
            "resolved_model_id": attempt.get("model_resolved")
            or qualification.get("resolved_model_id"),
            "prompt_id": PDF_DUAL_VLM_PROMPT_ID,
            "prompt_version": PROMPT_CONTRACT_VERSION,
            "prompt_hash": hashlib.sha256(
                NORMALIZER_PROMPT.encode("utf-8")
            ).hexdigest(),
            "model_view_hash": sha256_json(model_view),
            "output_schema_version": CANONICAL_TABLE_SCHEMA_VERSION,
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
                "canonical_proposal_hash": (
                    sha256_json(proposal) if proposal is not None else None
                ),
            },
            "hidden_retry": False,
            "provider_failover": False,
            "provider_switch": False,
            "whole_document_uploaded": False,
        }
        record["execution_hash"] = sha256_json(record)
        return record, proposal, failure_class

    def _decision(
        self,
        *,
        status: str,
        reason_codes: list[str],
        lineage: dict[str, Any] | None,
        executions: list[dict[str, Any]],
        proposals: dict[str, dict[str, Any] | None],
        comparison: dict[str, Any] | None,
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
            "deterministic_validator": {
                "validator_version": PDF_DUAL_VLM_VALIDATOR_VERSION,
                "provider_contracts_valid": bool(executions)
                and all(
                    _object(item.get("validator_result")).get("status") == "passed"
                    for item in executions
                ),
                "same_bounded_input_for_all_providers": bool(executions)
                and len({item.get("input_hash") for item in executions}) == 1,
                "source_to_table_accounting": "unavailable",
                "canonical_promotion_allowed": False,
            },
            "canonical_table": None,
            "provider_proposal_canonical_authority": False,
            "review_required": status != "proposal_validated_and_accepted",
            "hidden_retry": False,
            "provider_failover": False,
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
            "primary_provider": self.config.primary_provider,
            "primary_model_id": self.config.gemini_model_id,
            "review_provider": self.config.review_provider,
            "review_model_id": self.config.openai_model_id,
            "provider_order": list(PROVIDER_ORDER),
            "hidden_retry": False,
            "provider_failover": False,
            "provider_switch": False,
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
            "whole_document_provider_uploads": 0,
            "hidden_retries": 0,
            "provider_failovers": 0,
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
                "prompt_version": PROMPT_CONTRACT_VERSION,
                "canonical_schema_version": CANONICAL_TABLE_SCHEMA_VERSION,
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
        "deterministic_validator",
        "canonical_table",
        "provider_proposal_canonical_authority",
        "review_required",
        "hidden_retry",
        "provider_failover",
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
        selection.get("policy_version")
        != PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION
        or selection.get("execution_mode") != "dual_provider_comparison"
        or selection.get("primary_provider") != "gemini"
        or selection.get("review_provider") != "openai"
        or selection.get("provider_order") != list(PROVIDER_ORDER)
        or selection.get("hidden_retry") is not False
        or selection.get("provider_failover") is not False
        or selection.get("provider_switch") is not False
    ):
        errors.append("pdf_dual_vlm_provider_selection_invalid")
    executions = value.get("executions")
    if not isinstance(executions, list) or len(executions) > 2:
        errors.append("pdf_dual_vlm_executions_invalid")
        executions = []
    for execution in executions:
        errors.extend(_execution_errors(execution))
    if executions and [item.get("provider") for item in executions] != list(
        PROVIDER_ORDER
    ):
        errors.append("pdf_dual_vlm_provider_order_invalid")
    validator = _object(value.get("deterministic_validator"))
    if validator.get(
        "validator_version"
    ) != PDF_DUAL_VLM_VALIDATOR_VERSION or validator.get(
        "source_to_table_accounting"
    ) not in {"unavailable", "passed", "failed"}:
        errors.append("pdf_dual_vlm_validator_envelope_invalid")
    accepted = status == "proposal_validated_and_accepted"
    canonical = value.get("canonical_table")
    if accepted:
        if (
            validate_table_output(canonical)
            or validator.get("provider_contracts_valid") is not True
            or validator.get("same_bounded_input_for_all_providers") is not True
            or validator.get("source_to_table_accounting") != "passed"
            or validator.get("canonical_promotion_allowed") is not True
            or value.get("review_required") is not False
        ):
            errors.append("pdf_dual_vlm_acceptance_authority_invalid")
    elif (
        canonical is not None
        or validator.get("canonical_promotion_allowed") is not False
        or value.get("review_required") is not True
    ):
        errors.append("pdf_dual_vlm_nonaccepted_canonical_invalid")
    if (
        value.get("provider_proposal_canonical_authority") is not False
        or value.get("hidden_retry") is not False
        or value.get("provider_failover") is not False
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
        or value.get("input_hash") != value.get("crop_sha256")
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


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
