from __future__ import annotations

import copy
from typing import Any

from .pdf_dual_vlm_canonical_table_contracts import (
    sha256_json,
    validate_table_output,
)


LEGACY_PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION = (
    "pdf_dual_vlm_provider_selection_v1"
)
LEGACY_PDF_DUAL_VLM_RUNTIME_POLICY_VERSION = "pdf_dual_vlm_runtime_policy_v1"
LEGACY_PDF_DUAL_VLM_DECISION_SCHEMA = "broker_reports_pdf_dual_vlm_decision_v1"
LEGACY_PDF_DUAL_VLM_EXECUTION_SCHEMA = "broker_reports_pdf_dual_vlm_execution_v1"
LEGACY_PDF_DUAL_VLM_VALIDATOR_VERSION = (
    "pdf_dual_vlm_deterministic_validator_v1"
)
LEGACY_PROVIDER_ORDER = ("gemini", "openai")
LEGACY_DECISION_STATUSES = frozenset(
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


def validate_legacy_pdf_dual_vlm_decision(value: Any) -> list[str]:
    """Validate persisted pre-semantic decisions without executing that route."""

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
        value.get("schema_version") != LEGACY_PDF_DUAL_VLM_DECISION_SCHEMA
        or value.get("policy_version") != LEGACY_PDF_DUAL_VLM_RUNTIME_POLICY_VERSION
        or status not in LEGACY_DECISION_STATUSES
    ):
        errors.append("pdf_dual_vlm_decision_invalid")
    selection = _object(value.get("provider_selection"))
    if (
        selection.get("policy_version")
        != LEGACY_PDF_DUAL_VLM_PROVIDER_SELECTION_POLICY_VERSION
        or selection.get("execution_mode") != "dual_provider_comparison"
        or selection.get("primary_provider") != "gemini"
        or selection.get("review_provider") != "openai"
        or selection.get("provider_order") != list(LEGACY_PROVIDER_ORDER)
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
        errors.extend(_legacy_execution_errors(execution))
    if executions and [item.get("provider") for item in executions] != list(
        LEGACY_PROVIDER_ORDER
    ):
        errors.append("pdf_dual_vlm_provider_order_invalid")
    validator = _object(value.get("deterministic_validator"))
    if validator.get(
        "validator_version"
    ) != LEGACY_PDF_DUAL_VLM_VALIDATOR_VERSION or validator.get(
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


def _legacy_execution_errors(value: Any) -> list[str]:
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
        value.get("schema_version") != LEGACY_PDF_DUAL_VLM_EXECUTION_SCHEMA
        or value.get("policy_version") != LEGACY_PDF_DUAL_VLM_RUNTIME_POLICY_VERSION
        or value.get("provider") not in LEGACY_PROVIDER_ORDER
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
