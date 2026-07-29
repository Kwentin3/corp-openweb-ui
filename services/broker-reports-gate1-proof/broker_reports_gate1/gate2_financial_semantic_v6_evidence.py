from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any

from .gate2_financial_evidence_materialization import (
    Gate2FinancialEvidenceSourcePackage,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v6_bundle import (
    Gate2FinancialEvidenceBundle,
)
from .gate2_financial_semantic_v6_candidate_compiler import (
    Gate2FinancialCandidateCompilation,
)
from .gate2_financial_semantic_v6_choice import (
    Gate2FinancialSemanticV6ChoiceContract,
    Gate2FinancialSemanticV6ChoiceError,
)
from .gate2_financial_semantic_v6_context_linter import (
    Gate2FinancialSemanticV6ContextV21SealedRequest,
    validate_financial_semantic_v6_context_v2_1_sealed_request,
)
from .gate2_financial_semantic_v6_execution_identity import (
    V6_EXACT_MODEL_ID,
    V6_PROVIDER_PROFILE_ID,
    V6_QUALIFICATION_REQUEST_PROFILE,
    Gate2FinancialSemanticV6CapturedExecution,
    Gate2FinancialSemanticV6ExecutionIdentity,
    Gate2FinancialSemanticV6ExecutionIdentityError,
    Gate2FinancialSemanticV6ExecutionIdentityFactory,
    financial_semantic_v6_response_format,
    validate_financial_semantic_v6_execution_identity,
)
from .gate2_financial_semantic_v6_expansion import (
    Gate2FinancialSemanticV6DecisionExpansionFactory,
    Gate2FinancialSemanticV6ExpandedDecision,
    Gate2FinancialSemanticV6ExpansionError,
)
from .gate2_financial_semantic_v6_packet import (
    Gate2FinancialSemanticV6Packet,
)
from .gate2_financial_semantic_v6_prompt import (
    V6_SEMANTIC_SYSTEM_PROMPT,
    Gate2FinancialSemanticV6QualificationPrompt,
    financial_semantic_v6_prompt,
)
from .gate2_financial_semantic_v6_totality import (
    Gate2FinancialSemanticV6TotalMaterialization,
    Gate2FinancialSemanticV6TotalMaterializerFactory,
    Gate2FinancialSemanticV6TotalityError,
)
from .gate2_model_contracts import (
    Gate2ProviderExecutionMetadata,
    Gate2SourceFactRuntimeError,
    gate2_provider_profile,
    gate2_provider_profile_revision,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE,
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE,
    FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from .gate2_provider_adapters import (
    CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE,
    CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY,
    Gate2ContextV21BudgetSmokeTransportContract,
    Gate2NativeProviderTransportConfig,
    Gate2PreparedProviderRequest,
    Gate2ProviderAdapterFactory,
)


V6_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_private_evidence_v1"
)
V6_SAFE_DECISION_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_safe_receipt_v1"
)
V6_DECISION_REPLAY_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_replay_v1"
)
V6_CONTEXT_V2_1_PRIVATE_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_context_v2_1_"
    "private_evidence_v1"
)
V6_CONTEXT_V2_1_REPLAY_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_context_v2_1_replay_v1"
)
V6_CONTEXT_V2_1_BUDGET_SMOKE_PRIVATE_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_context_v2_1_"
    "budget_smoke_private_evidence_v1"
)
V6_CONTEXT_V2_1_BUDGET_SMOKE_FAILURE_PRIVATE_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_context_v2_1_"
    "budget_smoke_failure_private_evidence_v1"
)
V6_CONTEXT_V2_1_BUDGET_SMOKE_SAFE_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_context_v2_1_"
    "budget_smoke_safe_receipt_v1"
)
V6_CONTEXT_V2_1_BUDGET_SMOKE_REPLAY_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v6_context_v2_1_budget_smoke_replay_v1"
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6DecisionEvidenceFactory.create, "
    "its additive create_context_v2_1_candidate method, "
    "its additive create_context_v2_1_budget_smoke_candidate and "
    "create_context_v2_1_budget_smoke_failure methods, "
    "restore_financial_semantic_v6_private_evidence and "
    "the additive Context V2.1 serialize/restore/replay functions are the "
    "only V6 exact-decision evidence entrypoints"
)
FORBIDDEN = (
    "Repository-safe receipts and Git must not contain canonical requests, "
    "semantic choices, expanded decisions, source refs, literals, provider "
    "response IDs, raw provider output or private transport bytes"
)
COMPATIBILITY_WRAPPER_DELEGATES_ONLY = True

_CASE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_PRIVATE_FIELDS = (
    "schema_version",
    "case_id",
    "exact_canonical_request_object",
    "canonical_request_hash",
    "response_format_hash",
    "provider_schema_hash",
    "normalized_semantic_choice",
    "semantic_choice_hash",
    "expanded_canonical_decision",
    "validation_result",
    "materialized_artifact_hash",
    "materialized_artifact_integrity_hash",
    "total_materialization_integrity_hash",
    "provider_execution_identity",
    "replay_authorities",
    "exact_choice_preserved",
    "raw_provider_transport_preserved",
)
_SAFE_FIELDS = {
    "schema_version",
    "case_id",
    "decision_classification",
    "hashes",
    "counts",
    "provider_metrics",
    "validator_status",
    "materializer_status",
    "exact_choice_preserved",
    "offline_replay",
    "private_safe_hash_link",
    "private_safe_hash_link_verified",
    "raw_private_data_in_receipt",
    "raw_private_data_in_git",
    "receipt_hash",
}
_CONTEXT_V2_1_PRIVATE_FIELDS = (
    "schema_version",
    "case_id",
    "provider_profile_id",
    "provider_adapter_id",
    "provider_adapter_version",
    "local_projection_model_id",
    "schema_projection_policy_version",
    "request_profile",
    "exact_final_provider_request",
    "final_provider_request_hash",
    "provider_visible_schema",
    "provider_visible_schema_hash",
    "adapter_canonical_schema_hash",
    "adapter_adapted_schema_hash",
    "response_profile_hash",
    "mapping_receipt_hash",
    "adapter_extracted_output",
    "adapter_extracted_output_hash",
    "normalized_semantic_choice",
    "semantic_choice_hash",
    "expanded_canonical_decision",
    "validation_result",
    "materialized_artifact_hash",
    "materialized_artifact_integrity_hash",
    "total_materialization_integrity_hash",
    "replay_authorities",
    "execution_accounting",
)
_ZERO_CALL_ACCOUNTING = {
    "provider_calls_total": 0,
    "semantic_repair_total": 0,
    "fallback_total": 0,
    "retry_total": 0,
}
_BUDGET_SMOKE_SUCCESS_PRIVATE_FIELDS = (
    "schema_version",
    "case_id",
    "plan_integrity_hash",
    "plan_slot_id",
    "plan_slot_ordinal",
    "plan_slot_integrity_hash",
    "provider_profile_id",
    "provider_profile_revision",
    "provider_id",
    "provider_adapter_id",
    "provider_adapter_version",
    "exact_model_id",
    "model_identity_kind",
    "immutable_model_id_proven",
    "model_identity_caveat",
    "operation_identity",
    "operation_identity_hash",
    "request_profile",
    "transport_policy",
    "transport_contract",
    "transport_contract_hash",
    "exact_sealed_request",
    "sealed_request_hash",
    "exact_model_visible_request",
    "model_visible_request_hash",
    "exact_prepared_request",
    "prepared_request_hash",
    "exact_final_provider_request",
    "final_provider_request_hash",
    "provider_visible_schema",
    "provider_visible_schema_hash",
    "schema_projection_policy_version",
    "adapter_canonical_schema_hash",
    "adapter_adapted_schema_hash",
    "response_profile_hash",
    "mapping_receipt_hash",
    "adapter_extracted_output",
    "adapter_extracted_output_hash",
    "raw_provider_response",
    "raw_provider_response_hash",
    "normalized_semantic_choice",
    "semantic_choice_hash",
    "expected_answer",
    "expected_answer_hash",
    "field_level_diff",
    "field_level_diff_hash",
    "semantic_exact_match",
    "technical_verdict",
    "semantic_verdict",
    "error_category",
    "expanded_canonical_decision",
    "validation_result",
    "materialized_artifact_hash",
    "materialized_artifact_integrity_hash",
    "total_materialization_integrity_hash",
    "provider_execution_metadata",
    "provider_execution_metadata_hash",
    "economy_budget_receipt",
    "economy_budget_receipt_hash",
    "provider_metrics",
    "execution_accounting",
    "replay_authorities",
)
_BUDGET_SMOKE_FAILURE_PRIVATE_FIELDS = (
    "schema_version",
    "case_id",
    "plan_integrity_hash",
    "plan_slot_id",
    "plan_slot_ordinal",
    "plan_slot_integrity_hash",
    "provider_profile_id",
    "provider_profile_revision",
    "provider_id",
    "provider_adapter_id",
    "provider_adapter_version",
    "exact_model_id",
    "model_identity_kind",
    "immutable_model_id_proven",
    "model_identity_caveat",
    "operation_identity",
    "operation_identity_hash",
    "request_profile",
    "transport_policy",
    "transport_contract",
    "transport_contract_hash",
    "exact_sealed_request",
    "sealed_request_hash",
    "exact_model_visible_request",
    "model_visible_request_hash",
    "exact_prepared_request",
    "prepared_request_hash",
    "exact_final_provider_request",
    "final_provider_request_hash",
    "provider_visible_schema",
    "provider_visible_schema_hash",
    "schema_projection_policy_version",
    "adapter_canonical_schema_hash",
    "adapter_adapted_schema_hash",
    "response_profile_hash",
    "mapping_receipt_hash",
    "failure_code",
    "failure_class",
    "error_category",
    "adapter_extracted_output",
    "adapter_extracted_output_hash",
    "normalized_semantic_choice",
    "semantic_choice_hash",
    "expected_answer",
    "expected_answer_hash",
    "field_level_diff",
    "field_level_diff_hash",
    "semantic_exact_match",
    "raw_output",
    "raw_output_hash",
    "provider_execution_metadata",
    "provider_execution_metadata_hash",
    "economy_budget_receipt",
    "economy_budget_receipt_hash",
    "provider_metrics",
    "execution_accounting",
    "technical_verdict",
    "semantic_verdict",
)
_BUDGET_SMOKE_SAFE_FIELDS = {
    "schema_version",
    "case_id",
    "plan_slot_id",
    "provider_profile_id",
    "exact_model_id",
    "status",
    "verdicts",
    "transport",
    "hashes",
    "counts",
    "provider_metrics",
    "receipt_hash",
}
_BUDGET_SMOKE_SEMANTIC_ERROR_CATEGORIES = frozenset(
    {
        "wrong_typed_type",
        "unsafe_typed",
        "safe_under_typing",
        "wrong_unclassified_reason",
    }
)
_BUDGET_SMOKE_FAILURE_ERROR_CATEGORIES = frozenset(
    {
        "invalid_response",
        "infrastructure_provider_failure",
    }
)
_BUDGET_SMOKE_SEMANTIC_FIELDS = (
    "disposition",
    "typed_option_id",
    "reason_code",
)
_BUDGET_SMOKE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,255}$")
_BUDGET_SMOKE_SUCCESS_ACCOUNTING = {
    "local_invocations_total": 1,
    "provider_submissions_total": 1,
    "provider_responses_total": 1,
    "semantic_repair_total": 0,
    "retry_total": 0,
    "repair_total": 0,
    "fallback_total": 0,
}


class Gate2FinancialSemanticV6DecisionEvidenceError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6DecisionEvidenceBundle:
    private_evidence: dict[str, Any]
    safe_receipt: dict[str, Any]
    materialized_artifact: dict[str, Any]


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ReplayResult:
    schema_version: str
    status: str
    semantic_choice_hash: str
    expansion_integrity_hash: str
    materialized_artifact_hash: str
    materialized_artifact: dict[str, Any]
    safe_receipt: dict[str, Any]
    provider_calls_total: int


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21EvidenceBundle:
    private_evidence: dict[str, Any]
    normalized_semantic_choice: dict[str, Any]
    expansion: Gate2FinancialSemanticV6ExpandedDecision
    total_materialization: Gate2FinancialSemanticV6TotalMaterialization


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21ReplayResult:
    schema_version: str
    status: str
    private_evidence_hash: str
    semantic_choice_hash: str
    expansion_integrity_hash: str
    materialized_artifact_hash: str
    normalized_semantic_choice: dict[str, Any]
    expansion: Gate2FinancialSemanticV6ExpandedDecision
    total_materialization: Gate2FinancialSemanticV6TotalMaterialization
    provider_calls_total: int


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21BudgetSmokeEvidenceBundle:
    private_evidence: dict[str, Any]
    safe_receipt: dict[str, Any]
    materialized_artifact: dict[str, Any]


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21BudgetSmokeFailureEvidenceBundle:
    private_evidence: dict[str, Any]
    safe_receipt: dict[str, Any]


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21BudgetSmokeReplayResult:
    schema_version: str
    status: str
    private_evidence_hash: str
    semantic_choice_hash: str
    expansion_integrity_hash: str
    materialized_artifact_hash: str
    materialized_artifact: dict[str, Any]
    safe_receipt: dict[str, Any]
    provider_calls_total: int
    provider_responses_total: int
    retry_total: int
    repair_total: int
    fallback_total: int


class Gate2FinancialSemanticV6DecisionEvidenceFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        exact_model_id: str = V6_EXACT_MODEL_ID,
        provider_profile_id: str = V6_PROVIDER_PROFILE_ID,
    ) -> None:
        self.registry = registry
        self.exact_model_id = exact_model_id
        self.provider_profile_id = provider_profile_id

    def create(
        self,
        *,
        case_id: str,
        canonical_request: dict[str, Any],
        model_output: str | dict[str, Any],
        execution_capture: Gate2FinancialSemanticV6CapturedExecution,
        execution_identity: Gate2FinancialSemanticV6ExecutionIdentity,
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6DecisionEvidenceBundle:
        _case_id(case_id)
        exact_request = _validate_exact_request(
            canonical_request=canonical_request,
            packet=packet,
            choice_contract=choice_contract,
            exact_model_id=self.exact_model_id,
        )
        if (
            execution_capture.exact_model_id != self.exact_model_id
            or execution_capture.provider_profile_id != self.provider_profile_id
        ):
            _fail("financial_semantic_v6_evidence_candidate_identity_invalid")
        try:
            validate_financial_semantic_v6_execution_identity(
                identity=execution_identity,
                capture=execution_capture,
                choice_contract=choice_contract,
            )
        except Gate2FinancialSemanticV6ExecutionIdentityError as exc:
            raise Gate2FinancialSemanticV6DecisionEvidenceError(
                "financial_semantic_v6_evidence_execution_identity_invalid"
            ) from exc
        expansion, normalized_choice, total = _execute_chain(
            model_output=model_output,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        private_material = {
            "schema_version": V6_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION,
            "case_id": case_id,
            "exact_canonical_request_object": exact_request,
            "canonical_request_hash": sha256_json(exact_request),
            "response_format_hash": execution_identity.response_format_hash,
            "provider_schema_hash": choice_contract.choice_schema_hash,
            "normalized_semantic_choice": copy.deepcopy(normalized_choice),
            "semantic_choice_hash": sha256_json(normalized_choice),
            "expanded_canonical_decision": expansion.to_private_dict(),
            "validation_result": _validation_result(
                expansion=expansion,
                total=total,
            ),
            "materialized_artifact_hash": total.canonical_artifact_hash,
            "materialized_artifact_integrity_hash": (
                total.canonical_artifact["integrity_hash"]
            ),
            "total_materialization_integrity_hash": total.integrity_hash,
            "provider_execution_identity": (execution_identity.to_private_dict()),
            "replay_authorities": _replay_authorities(
                choice_contract=choice_contract,
                packet=packet,
                evidence_bundle=evidence_bundle,
                source_package=source_package,
                compilation=compilation,
                registry=self.registry,
                exact_model_id=self.exact_model_id,
            ),
            "exact_choice_preserved": True,
            "raw_provider_transport_preserved": False,
        }
        private_evidence = {
            **copy.deepcopy(private_material),
            "private_evidence_hash": sha256_json(private_material),
        }
        safe_receipt = _safe_receipt(
            private_evidence=private_evidence,
            expansion=expansion,
            total=total,
            execution_identity=execution_identity,
            compilation=compilation,
        )
        _validate_private_evidence(
            private_evidence=private_evidence,
            choice_contract=choice_contract,
        )
        _validate_safe_receipt(
            safe_receipt=safe_receipt,
            private_evidence=private_evidence,
        )
        return Gate2FinancialSemanticV6DecisionEvidenceBundle(
            private_evidence=copy.deepcopy(private_evidence),
            safe_receipt=copy.deepcopy(safe_receipt),
            materialized_artifact=copy.deepcopy(total.canonical_artifact),
        )

    def create_context_v2_1_candidate(
        self,
        *,
        case_id: str,
        provider_profile_id: str,
        provider_adapter_id: str,
        provider_adapter_version: str,
        local_projection_model_id: str,
        sealed_request: (
            Gate2FinancialSemanticV6ContextV21SealedRequest
        ),
        prepared_request: Gate2PreparedProviderRequest,
        adapter_extracted_output: Any,
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6ContextV21EvidenceBundle:
        _case_id(case_id)
        for value in (
            provider_profile_id,
            provider_adapter_id,
            provider_adapter_version,
            local_projection_model_id,
        ):
            _bounded_context_v2_1_identity(value)
        if not isinstance(
            prepared_request,
            Gate2PreparedProviderRequest,
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "private_evidence_request_invalid"
            )
        prepared_request.validate_schema_binding()
        schema_projection_policy_version = (
            prepared_request.projection_policy_version
        )
        _bounded_context_v2_1_identity(
            schema_projection_policy_version
        )
        response_profile = choice_contract.context_v2_1_response_profile
        if (
            not isinstance(prepared_request.form_data, dict)
            or prepared_request.form_data.get("model")
            != local_projection_model_id
            or prepared_request.provider_adapter_id
            != provider_adapter_id
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "private_evidence_request_invalid"
            )
        if not _context_v2_1_prepared_authority_is_valid(
            sealed_request=sealed_request,
            prepared_request=prepared_request,
            provider_profile_id=provider_profile_id,
            provider_adapter_id=provider_adapter_id,
            provider_adapter_version=provider_adapter_version,
            local_projection_model_id=local_projection_model_id,
            canonical_schema=response_profile.canonical_schema(),
            packet=packet,
            choice_contract=choice_contract,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "private_evidence_canonical_schema_mismatch"
            )
        exact_request = _json_roundtrip(prepared_request.form_data)
        exact_schema = _json_roundtrip(
            prepared_request.provider_visible_schema
        )
        exact_output = _json_roundtrip(adapter_extracted_output)
        expansion, normalized_choice, total = (
            _execute_context_v2_1_chain(
                model_output=exact_output,
                choice_contract=choice_contract,
                packet=packet,
                evidence_bundle=evidence_bundle,
                source_package=source_package,
                compilation=compilation,
                registry=self.registry,
            )
        )
        private_material = {
            "schema_version": (
                V6_CONTEXT_V2_1_PRIVATE_EVIDENCE_SCHEMA_VERSION
            ),
            "case_id": case_id,
            "provider_profile_id": provider_profile_id,
            "provider_adapter_id": provider_adapter_id,
            "provider_adapter_version": provider_adapter_version,
            "local_projection_model_id": local_projection_model_id,
            "schema_projection_policy_version": (
                schema_projection_policy_version
            ),
            "request_profile": (
                FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE
            ),
            "exact_final_provider_request": exact_request,
            "final_provider_request_hash": sha256_json(exact_request),
            "provider_visible_schema": exact_schema,
            "provider_visible_schema_hash": sha256_json(exact_schema),
            "adapter_canonical_schema_hash": (
                prepared_request.canonical_schema_hash
            ),
            "adapter_adapted_schema_hash": (
                prepared_request.adapted_schema_hash
            ),
            "response_profile_hash": response_profile.response_schema_hash,
            "mapping_receipt_hash": (
                packet.context_v2_mapping_receipt.integrity_hash
            ),
            "adapter_extracted_output": exact_output,
            "adapter_extracted_output_hash": sha256_json(exact_output),
            "normalized_semantic_choice": copy.deepcopy(
                normalized_choice
            ),
            "semantic_choice_hash": sha256_json(normalized_choice),
            "expanded_canonical_decision": _json_roundtrip(
                expansion.to_private_dict()
            ),
            "validation_result": _validation_result(
                expansion=expansion,
                total=total,
            ),
            "materialized_artifact_hash": total.canonical_artifact_hash,
            "materialized_artifact_integrity_hash": (
                total.canonical_artifact["integrity_hash"]
            ),
            "total_materialization_integrity_hash": total.integrity_hash,
            "replay_authorities": _context_v2_1_replay_authorities(
                choice_contract=choice_contract,
                packet=packet,
                evidence_bundle=evidence_bundle,
                source_package=source_package,
                compilation=compilation,
                registry=self.registry,
                provider_profile_id=provider_profile_id,
                provider_adapter_id=provider_adapter_id,
                provider_adapter_version=provider_adapter_version,
                local_projection_model_id=local_projection_model_id,
                schema_projection_policy_version=(
                    schema_projection_policy_version
                ),
                final_provider_request_hash=sha256_json(exact_request),
                provider_visible_schema_hash=sha256_json(exact_schema),
                adapter_canonical_schema_hash=(
                    prepared_request.canonical_schema_hash
                ),
                adapter_adapted_schema_hash=(
                    prepared_request.adapted_schema_hash
                ),
            ),
            "execution_accounting": copy.deepcopy(
                _ZERO_CALL_ACCOUNTING
            ),
        }
        private_evidence = {
            **copy.deepcopy(private_material),
            "private_evidence_hash": sha256_json(private_material),
        }
        _validate_context_v2_1_private_evidence(private_evidence)
        return Gate2FinancialSemanticV6ContextV21EvidenceBundle(
            private_evidence=copy.deepcopy(private_evidence),
            normalized_semantic_choice=copy.deepcopy(normalized_choice),
            expansion=expansion,
            total_materialization=total,
        )

    def create_context_v2_1_budget_smoke_candidate(
        self,
        *,
        plan: Any,
        plan_slot: Any,
        expected_answer: dict[str, Any],
        operation_identity: str,
        sealed_request: (Gate2FinancialSemanticV6ContextV21SealedRequest),
        prepared_request: Gate2PreparedProviderRequest,
        adapter_extracted_output: Any,
        raw_provider_response: dict[str, Any],
        execution_metadata: Gate2ProviderExecutionMetadata,
        economy_budget_receipt: dict[str, Any],
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6ContextV21BudgetSmokeEvidenceBundle:
        slot_identity = _budget_smoke_plan_slot_identity(
            plan=plan,
            plan_slot=plan_slot,
        )
        if (
            operation_identity != slot_identity["operation_identity"]
            or plan_slot.immutable_model_id_proven is not True
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_execution_identity_invalid"
            )
        request_authority = _budget_smoke_request_authority(
            plan_slot=plan_slot,
            operation_identity=operation_identity,
            sealed_request=sealed_request,
            prepared_request=prepared_request,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        exact_expected = _budget_smoke_expected_answer(
            expected_answer,
            expected_hash=plan_slot.expected_answer_hash,
        )
        exact_raw_response = _budget_smoke_ordered_json_roundtrip(raw_provider_response)
        exact_adapter_output = _budget_smoke_ordered_json_roundtrip(
            adapter_extracted_output
        )
        independently_extracted = _budget_smoke_extract_adapter_output(
            plan_slot=plan_slot,
            operation_identity=operation_identity,
            prepared_request=prepared_request,
            model_visible_request=(sealed_request.model_visible_request),
            canonical_schema=(
                choice_contract.context_v2_1_response_profile.canonical_schema()
            ),
            raw_provider_response=exact_raw_response,
        )
        if independently_extracted != exact_adapter_output:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_adapter_output_mismatch"
            )
        (
            metadata_snapshot,
            budget_snapshot,
            provider_metrics,
        ) = _budget_smoke_success_execution_evidence(
            plan_slot=plan_slot,
            operation_identity=operation_identity,
            prepared_request=prepared_request,
            raw_provider_response=exact_raw_response,
            execution_metadata=execution_metadata,
            economy_budget_receipt=economy_budget_receipt,
        )
        expansion, normalized_choice, total = _execute_context_v2_1_chain(
            model_output=exact_adapter_output,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        comparison = _budget_smoke_semantic_comparison(
            normalized_answer=normalized_choice,
            expected_answer=exact_expected,
        )
        private_material = {
            "schema_version": (
                V6_CONTEXT_V2_1_BUDGET_SMOKE_PRIVATE_EVIDENCE_SCHEMA_VERSION
            ),
            "case_id": plan_slot.case_id,
            **slot_identity["private_identity"],
            "operation_identity": operation_identity,
            "operation_identity_hash": _sha256_text(operation_identity),
            "request_profile": plan_slot.request_profile,
            **request_authority,
            "adapter_extracted_output": exact_adapter_output,
            "adapter_extracted_output_hash": sha256_json(exact_adapter_output),
            "raw_provider_response": exact_raw_response,
            "raw_provider_response_hash": sha256_json(exact_raw_response),
            "normalized_semantic_choice": copy.deepcopy(normalized_choice),
            "semantic_choice_hash": sha256_json(normalized_choice),
            "expected_answer": exact_expected,
            "expected_answer_hash": sha256_json(exact_expected),
            **comparison,
            "expanded_canonical_decision": _json_roundtrip(expansion.to_private_dict()),
            "validation_result": _validation_result(
                expansion=expansion,
                total=total,
            ),
            "materialized_artifact_hash": (total.canonical_artifact_hash),
            "materialized_artifact_integrity_hash": (
                total.canonical_artifact["integrity_hash"]
            ),
            "total_materialization_integrity_hash": (total.integrity_hash),
            "provider_execution_metadata": metadata_snapshot,
            "provider_execution_metadata_hash": sha256_json(metadata_snapshot),
            "economy_budget_receipt": budget_snapshot,
            "economy_budget_receipt_hash": sha256_json(budget_snapshot),
            "provider_metrics": provider_metrics,
            "execution_accounting": copy.deepcopy(_BUDGET_SMOKE_SUCCESS_ACCOUNTING),
        }
        private_material["replay_authorities"] = _budget_smoke_replay_authorities(
            plan_slot=plan_slot,
            registry=self.registry,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            private_material=private_material,
        )
        private_evidence = {
            **copy.deepcopy(private_material),
            "private_evidence_hash": sha256_json(private_material),
        }
        safe_receipt = _budget_smoke_safe_receipt(
            private_evidence=private_evidence,
        )
        bundle = Gate2FinancialSemanticV6ContextV21BudgetSmokeEvidenceBundle(
            private_evidence=copy.deepcopy(private_evidence),
            safe_receipt=copy.deepcopy(safe_receipt),
            materialized_artifact=copy.deepcopy(total.canonical_artifact),
        )
        validate_financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle(
            evidence_bundle=bundle,
            plan=plan,
            plan_slot=plan_slot,
        )
        return bundle

    def create_context_v2_1_budget_smoke_failure(
        self,
        *,
        plan: Any,
        plan_slot: Any,
        operation_identity: str,
        sealed_request: (Gate2FinancialSemanticV6ContextV21SealedRequest),
        prepared_request: Gate2PreparedProviderRequest,
        lifecycle: dict[str, int],
        expected_answer: dict[str, Any],
        failure_code: str,
        failure_class: str,
        error_category: str,
        raw_output: Any,
        adapter_extracted_output: Any = None,
        execution_metadata: Gate2ProviderExecutionMetadata | None = None,
        economy_budget_receipt: dict[str, Any] | None = None,
        elapsed_ms: int = 0,
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6ContextV21BudgetSmokeFailureEvidenceBundle:
        slot_identity = _budget_smoke_plan_slot_identity(
            plan=plan,
            plan_slot=plan_slot,
        )
        if operation_identity != slot_identity["operation_identity"]:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_execution_identity_invalid"
            )
        request_authority = _budget_smoke_request_authority(
            plan_slot=plan_slot,
            operation_identity=operation_identity,
            sealed_request=sealed_request,
            prepared_request=prepared_request,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        exact_failure_code = _budget_smoke_identifier(failure_code)
        exact_failure_class = _budget_smoke_identifier(failure_class)
        exact_expected = _budget_smoke_expected_answer(
            expected_answer,
            expected_hash=plan_slot.expected_answer_hash,
        )
        if error_category not in _BUDGET_SMOKE_FAILURE_ERROR_CATEGORIES:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_failure_category_invalid"
            )
        execution_accounting = _budget_smoke_failure_accounting(lifecycle)
        if plan_slot.immutable_model_id_proven is not True and (
            error_category != "infrastructure_provider_failure"
            or execution_accounting["provider_submissions_total"] != 0
            or execution_accounting["provider_responses_total"] != 0
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_unproven_model_executed"
            )
        (
            metadata_snapshot,
            budget_snapshot,
            provider_metrics,
        ) = _budget_smoke_failure_execution_evidence(
            plan_slot=plan_slot,
            operation_identity=operation_identity,
            prepared_request=prepared_request,
            execution_metadata=execution_metadata,
            economy_budget_receipt=economy_budget_receipt,
            elapsed_ms=elapsed_ms,
            execution_accounting=execution_accounting,
        )
        exact_raw_output = _budget_smoke_ordered_json_roundtrip(raw_output)
        exact_adapter_output = _budget_smoke_ordered_json_roundtrip(
            adapter_extracted_output
        )
        private_material = {
            "schema_version": (
                V6_CONTEXT_V2_1_BUDGET_SMOKE_FAILURE_PRIVATE_EVIDENCE_SCHEMA_VERSION
            ),
            "case_id": plan_slot.case_id,
            **slot_identity["private_identity"],
            "operation_identity": operation_identity,
            "operation_identity_hash": _sha256_text(operation_identity),
            "request_profile": plan_slot.request_profile,
            **request_authority,
            "failure_code": exact_failure_code,
            "failure_class": exact_failure_class,
            "error_category": error_category,
            "adapter_extracted_output": exact_adapter_output,
            "adapter_extracted_output_hash": sha256_json(exact_adapter_output),
            "normalized_semantic_choice": None,
            "semantic_choice_hash": sha256_json(None),
            "expected_answer": exact_expected,
            "expected_answer_hash": sha256_json(exact_expected),
            "field_level_diff": _budget_smoke_failure_diff(exact_expected),
            "field_level_diff_hash": sha256_json(
                _budget_smoke_failure_diff(exact_expected)
            ),
            "semantic_exact_match": False,
            "raw_output": exact_raw_output,
            "raw_output_hash": sha256_json(exact_raw_output),
            "provider_execution_metadata": metadata_snapshot,
            "provider_execution_metadata_hash": sha256_json(metadata_snapshot),
            "economy_budget_receipt": budget_snapshot,
            "economy_budget_receipt_hash": sha256_json(budget_snapshot),
            "provider_metrics": provider_metrics,
            "execution_accounting": execution_accounting,
            "technical_verdict": "TECHNICAL_SMOKE_FAILED",
            "semantic_verdict": "SEMANTIC_SMOKE_FAILED",
        }
        private_evidence = {
            **copy.deepcopy(private_material),
            "private_evidence_hash": sha256_json(private_material),
        }
        safe_receipt = _budget_smoke_safe_receipt(
            private_evidence=private_evidence,
        )
        bundle = Gate2FinancialSemanticV6ContextV21BudgetSmokeFailureEvidenceBundle(
            private_evidence=copy.deepcopy(private_evidence),
            safe_receipt=copy.deepcopy(safe_receipt),
        )
        validate_financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle(
            evidence_bundle=bundle,
            plan=plan,
            plan_slot=plan_slot,
        )
        return bundle


def financial_semantic_v6_canonical_request(
    *,
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    exact_model_id: str = V6_EXACT_MODEL_ID,
    prompt: Gate2FinancialSemanticV6QualificationPrompt | None = None,
) -> dict[str, Any]:
    if (
        not isinstance(packet, Gate2FinancialSemanticV6Packet)
        or packet.packet_hash != sha256_json(packet.payload)
        or not isinstance(
            choice_contract,
            Gate2FinancialSemanticV6ChoiceContract,
        )
        or choice_contract.packet_hash != packet.packet_hash
    ):
        _fail("financial_semantic_v6_canonical_request_authority_invalid")
    response_format = financial_semantic_v6_response_format(choice_contract)
    exact_prompt = prompt or financial_semantic_v6_prompt(
        packet=packet,
        choice_contract=choice_contract,
    )
    return Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE
    ).build(
        prompt=exact_prompt,
        package=packet.payload,
        model_id=exact_model_id,
        response_format=response_format,
    )


def replay_financial_semantic_v6_decision(
    *,
    private_evidence: dict[str, Any],
    safe_receipt: dict[str, Any],
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> Gate2FinancialSemanticV6ReplayResult:
    _validate_private_evidence(
        private_evidence=private_evidence,
        choice_contract=choice_contract,
    )
    _validate_safe_receipt(
        safe_receipt=safe_receipt,
        private_evidence=private_evidence,
    )
    private_identity = private_evidence["provider_execution_identity"]
    exact_model_id = private_identity.get("requested_model_id")
    if not isinstance(exact_model_id, str) or not exact_model_id:
        _fail("financial_semantic_v6_private_execution_identity_invalid")
    _validate_exact_request(
        canonical_request=private_evidence["exact_canonical_request_object"],
        packet=packet,
        choice_contract=choice_contract,
        exact_model_id=exact_model_id,
    )
    expected_authorities = _replay_authorities(
        choice_contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        registry=registry,
        exact_model_id=exact_model_id,
    )
    if private_evidence["replay_authorities"] != expected_authorities:
        _fail("financial_semantic_v6_offline_replay_authority_mismatch")
    expansion, normalized_choice, total = _execute_chain(
        model_output=private_evidence["normalized_semantic_choice"],
        choice_contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        registry=registry,
    )
    identity = _execution_identity_from_private(
        private_evidence["provider_execution_identity"],
        choice_contract=choice_contract,
    )
    expected_validation = _validation_result(
        expansion=expansion,
        total=total,
    )
    if (
        private_evidence["normalized_semantic_choice"] != normalized_choice
        or private_evidence["semantic_choice_hash"] != sha256_json(normalized_choice)
        or private_evidence["expanded_canonical_decision"]
        != expansion.to_private_dict()
        or private_evidence["validation_result"] != expected_validation
        or private_evidence["materialized_artifact_hash"]
        != total.canonical_artifact_hash
        or private_evidence["materialized_artifact_integrity_hash"]
        != total.canonical_artifact["integrity_hash"]
        or private_evidence["total_materialization_integrity_hash"]
        != total.integrity_hash
    ):
        _fail("financial_semantic_v6_offline_replay_mismatch")
    expected_safe = _safe_receipt(
        private_evidence=private_evidence,
        expansion=expansion,
        total=total,
        execution_identity=identity,
        compilation=compilation,
    )
    if safe_receipt != expected_safe:
        _fail("financial_semantic_v6_offline_replay_safe_receipt_mismatch")
    return Gate2FinancialSemanticV6ReplayResult(
        schema_version=V6_DECISION_REPLAY_SCHEMA_VERSION,
        status="EXACT",
        semantic_choice_hash=private_evidence["semantic_choice_hash"],
        expansion_integrity_hash=expansion.integrity_hash,
        materialized_artifact_hash=total.canonical_artifact_hash,
        materialized_artifact=copy.deepcopy(total.canonical_artifact),
        safe_receipt=copy.deepcopy(safe_receipt),
        provider_calls_total=0,
    )


def serialize_financial_semantic_v6_context_v2_1_private_evidence(
    *,
    private_evidence: dict[str, Any],
) -> str:
    _validate_context_v2_1_private_evidence(private_evidence)
    return json.dumps(
        private_evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def restore_financial_semantic_v6_context_v2_1_private_evidence(
    *,
    serialized: str,
) -> dict[str, Any]:
    if not isinstance(serialized, str) or not serialized:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "private_evidence_serialization_invalid"
        )
    try:
        restored = json.loads(
            serialized,
            object_pairs_hook=_unique_context_v2_1_evidence_object,
            parse_constant=_reject_context_v2_1_non_finite_number,
        )
    except (
        TypeError,
        ValueError,
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_"
            "private_evidence_serialization_invalid"
        ) from exc
    _validate_context_v2_1_private_evidence(restored)
    return copy.deepcopy(restored)


def _context_v2_1_prepared_authority_is_valid(
    *,
    sealed_request: Gate2FinancialSemanticV6ContextV21SealedRequest,
    prepared_request: Gate2PreparedProviderRequest,
    provider_profile_id: str,
    provider_adapter_id: str,
    provider_adapter_version: str,
    local_projection_model_id: str,
    canonical_schema: dict[str, Any],
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> bool:
    if (
        not isinstance(
            sealed_request,
            Gate2FinancialSemanticV6ContextV21SealedRequest,
        )
        or not isinstance(
            prepared_request,
            Gate2PreparedProviderRequest,
        )
    ):
        return False
    try:
        validate_financial_semantic_v6_context_v2_1_sealed_request(
            sealed_request=sealed_request,
            packet=packet,
            choice_contract=choice_contract,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=registry,
            system_message=V6_SEMANTIC_SYSTEM_PROMPT,
            mapping_receipt=packet.context_v2_mapping_receipt,
        )
        provider_profile = gate2_provider_profile(provider_profile_id)
    except (
        AttributeError,
        TypeError,
        ValueError,
        Gate2SourceFactRuntimeError,
    ):
        return False
    if (
        provider_profile.profile_id != provider_profile_id
        or provider_profile.adapter_id != provider_adapter_id
        or provider_profile.adapter_version
        != provider_adapter_version
    ):
        return False
    return prepared_request.context_v2_1_contract_is_bound(
        canonical_schema=canonical_schema,
        provider_profile=provider_profile,
        model_visible_request=sealed_request.model_visible_request,
        local_projection_model_id=local_projection_model_id,
    )


def replay_financial_semantic_v6_context_v2_1_decision(
    *,
    private_evidence: dict[str, Any],
    expected_provider_profile_id: str,
    expected_provider_adapter_id: str,
    expected_provider_adapter_version: str,
    expected_local_projection_model_id: str,
    expected_sealed_request: (
        Gate2FinancialSemanticV6ContextV21SealedRequest
    ),
    expected_prepared_request: Gate2PreparedProviderRequest,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> Gate2FinancialSemanticV6ContextV21ReplayResult:
    _validate_context_v2_1_private_evidence(private_evidence)
    if not isinstance(
        expected_prepared_request,
        Gate2PreparedProviderRequest,
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "offline_replay_projection_mismatch"
        )
    expected_prepared_request.validate_schema_binding()
    expected_request = _json_roundtrip(
        expected_prepared_request.form_data
    )
    expected_schema = _json_roundtrip(
        expected_prepared_request.provider_visible_schema
    )
    expected_schema_projection_policy_version = (
        expected_prepared_request.projection_policy_version
    )
    response_profile = choice_contract.context_v2_1_response_profile
    for value in (
        expected_provider_profile_id,
        expected_provider_adapter_id,
        expected_provider_adapter_version,
        expected_local_projection_model_id,
        expected_schema_projection_policy_version,
    ):
        _bounded_context_v2_1_identity(value)
    if (
        expected_request.get("model")
        != expected_local_projection_model_id
        or expected_prepared_request.provider_adapter_id
        != expected_provider_adapter_id
        or not _context_v2_1_prepared_authority_is_valid(
            sealed_request=expected_sealed_request,
            prepared_request=expected_prepared_request,
            provider_profile_id=expected_provider_profile_id,
            provider_adapter_id=expected_provider_adapter_id,
            provider_adapter_version=(
                expected_provider_adapter_version
            ),
            local_projection_model_id=(
                expected_local_projection_model_id
            ),
            canonical_schema=response_profile.canonical_schema(),
            packet=packet,
            choice_contract=choice_contract,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=registry,
        )
        or private_evidence["provider_profile_id"]
        != expected_provider_profile_id
        or private_evidence["provider_adapter_id"]
        != expected_provider_adapter_id
        or private_evidence["provider_adapter_version"]
        != expected_provider_adapter_version
        or private_evidence["local_projection_model_id"]
        != expected_local_projection_model_id
        or private_evidence["schema_projection_policy_version"]
        != expected_schema_projection_policy_version
        or private_evidence["exact_final_provider_request"]
        != expected_request
        or private_evidence["provider_visible_schema"]
        != expected_schema
        or private_evidence["adapter_adapted_schema_hash"]
        != expected_prepared_request.adapted_schema_hash
        or private_evidence["adapter_canonical_schema_hash"]
        != expected_prepared_request.canonical_schema_hash
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "offline_replay_projection_mismatch"
        )
    expected_authorities = _context_v2_1_replay_authorities(
        choice_contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        registry=registry,
        provider_profile_id=expected_provider_profile_id,
        provider_adapter_id=expected_provider_adapter_id,
        provider_adapter_version=expected_provider_adapter_version,
        local_projection_model_id=expected_local_projection_model_id,
        schema_projection_policy_version=(
            expected_schema_projection_policy_version
        ),
        final_provider_request_hash=sha256_json(expected_request),
        provider_visible_schema_hash=sha256_json(expected_schema),
        adapter_canonical_schema_hash=(
            expected_prepared_request.canonical_schema_hash
        ),
        adapter_adapted_schema_hash=(
            expected_prepared_request.adapted_schema_hash
        ),
    )
    if (
        private_evidence["replay_authorities"] != expected_authorities
        or private_evidence["response_profile_hash"]
        != response_profile.response_schema_hash
        or private_evidence["mapping_receipt_hash"]
        != packet.context_v2_mapping_receipt.integrity_hash
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "offline_replay_authority_mismatch"
        )
    expansion, normalized_choice, total = _execute_context_v2_1_chain(
        model_output=private_evidence["adapter_extracted_output"],
        choice_contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        registry=registry,
    )
    expected_validation = _validation_result(
        expansion=expansion,
        total=total,
    )
    if (
        private_evidence["normalized_semantic_choice"]
        != normalized_choice
        or private_evidence["semantic_choice_hash"]
        != sha256_json(normalized_choice)
        or private_evidence["expanded_canonical_decision"]
        != _json_roundtrip(expansion.to_private_dict())
        or private_evidence["validation_result"] != expected_validation
        or private_evidence["materialized_artifact_hash"]
        != total.canonical_artifact_hash
        or private_evidence["materialized_artifact_integrity_hash"]
        != total.canonical_artifact["integrity_hash"]
        or private_evidence["total_materialization_integrity_hash"]
        != total.integrity_hash
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "offline_replay_mismatch"
        )
    return Gate2FinancialSemanticV6ContextV21ReplayResult(
        schema_version=V6_CONTEXT_V2_1_REPLAY_SCHEMA_VERSION,
        status="EXACT",
        private_evidence_hash=private_evidence[
            "private_evidence_hash"
        ],
        semantic_choice_hash=private_evidence["semantic_choice_hash"],
        expansion_integrity_hash=expansion.integrity_hash,
        materialized_artifact_hash=total.canonical_artifact_hash,
        normalized_semantic_choice=copy.deepcopy(normalized_choice),
        expansion=expansion,
        total_materialization=total,
        provider_calls_total=0,
    )


def serialize_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
    *,
    private_evidence: dict[str, Any],
) -> str:
    _validate_budget_smoke_private_evidence(private_evidence)
    return json.dumps(
        private_evidence,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def restore_financial_semantic_v6_context_v2_1_budget_smoke_private_evidence(
    *,
    serialized: str,
) -> dict[str, Any]:
    if not isinstance(serialized, str) or not serialized:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_private_evidence_serialization_invalid"
        )
    try:
        restored = json.loads(
            serialized,
            object_pairs_hook=_unique_context_v2_1_evidence_object,
            parse_constant=_reject_context_v2_1_non_finite_number,
        )
    except (
        TypeError,
        ValueError,
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_private_evidence_serialization_invalid"
        ) from exc
    _validate_budget_smoke_private_evidence(restored)
    return copy.deepcopy(restored)


def validate_financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle(
    *,
    evidence_bundle: Any,
    plan: Any,
    plan_slot: Any,
) -> None:
    if type(evidence_bundle) not in {
        Gate2FinancialSemanticV6ContextV21BudgetSmokeEvidenceBundle,
        Gate2FinancialSemanticV6ContextV21BudgetSmokeFailureEvidenceBundle,
    }:
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_evidence_bundle_invalid")
    private_evidence = evidence_bundle.private_evidence
    safe_receipt = evidence_bundle.safe_receipt
    _validate_budget_smoke_private_evidence(private_evidence)
    _validate_budget_smoke_private_plan_binding(
        private_evidence=private_evidence,
        plan=plan,
        plan_slot=plan_slot,
    )
    _validate_budget_smoke_safe_receipt(
        safe_receipt=safe_receipt,
        private_evidence=private_evidence,
    )
    if type(evidence_bundle) is (
        Gate2FinancialSemanticV6ContextV21BudgetSmokeEvidenceBundle
    ):
        artifact = evidence_bundle.materialized_artifact
        if (
            private_evidence["schema_version"]
            != V6_CONTEXT_V2_1_BUDGET_SMOKE_PRIVATE_EVIDENCE_SCHEMA_VERSION
            or not isinstance(artifact, dict)
            or sha256_json(artifact) != private_evidence["materialized_artifact_hash"]
            or artifact.get("integrity_hash")
            != private_evidence["materialized_artifact_integrity_hash"]
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_materialized_artifact_invalid"
            )
    elif private_evidence["schema_version"] != (
        V6_CONTEXT_V2_1_BUDGET_SMOKE_FAILURE_PRIVATE_EVIDENCE_SCHEMA_VERSION
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_failure_evidence_invalid"
        )


def replay_financial_semantic_v6_context_v2_1_budget_smoke_decision(
    *,
    private_evidence: dict[str, Any],
    safe_receipt: dict[str, Any],
    plan: Any,
    plan_slot: Any,
    expected_answer: dict[str, Any],
    expected_sealed_request: (Gate2FinancialSemanticV6ContextV21SealedRequest),
    expected_prepared_request: Gate2PreparedProviderRequest,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> Gate2FinancialSemanticV6ContextV21BudgetSmokeReplayResult:
    _validate_budget_smoke_private_evidence(private_evidence)
    if private_evidence["schema_version"] != (
        V6_CONTEXT_V2_1_BUDGET_SMOKE_PRIVATE_EVIDENCE_SCHEMA_VERSION
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_failure_not_replayable")
    _validate_budget_smoke_private_plan_binding(
        private_evidence=private_evidence,
        plan=plan,
        plan_slot=plan_slot,
    )
    _validate_budget_smoke_safe_receipt(
        safe_receipt=safe_receipt,
        private_evidence=private_evidence,
    )
    operation_identity = _budget_smoke_plan_slot_identity(
        plan=plan,
        plan_slot=plan_slot,
    )["operation_identity"]
    request_authority = _budget_smoke_request_authority(
        plan_slot=plan_slot,
        operation_identity=operation_identity,
        sealed_request=expected_sealed_request,
        prepared_request=expected_prepared_request,
        choice_contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        registry=registry,
    )
    exact_expected = _budget_smoke_expected_answer(
        expected_answer,
        expected_hash=plan_slot.expected_answer_hash,
    )
    request_fields = (
        "exact_sealed_request",
        "sealed_request_hash",
        "exact_model_visible_request",
        "model_visible_request_hash",
        "exact_prepared_request",
        "transport_policy",
        "transport_contract",
        "transport_contract_hash",
        "prepared_request_hash",
        "exact_final_provider_request",
        "final_provider_request_hash",
        "provider_visible_schema",
        "provider_visible_schema_hash",
        "schema_projection_policy_version",
        "adapter_canonical_schema_hash",
        "adapter_adapted_schema_hash",
        "response_profile_hash",
        "mapping_receipt_hash",
    )
    if (
        any(
            private_evidence[field] != request_authority[field]
            for field in request_fields
        )
        or private_evidence["expected_answer"] != exact_expected
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_offline_replay_projection_mismatch"
        )
    independently_extracted = _budget_smoke_extract_adapter_output(
        plan_slot=plan_slot,
        operation_identity=operation_identity,
        prepared_request=expected_prepared_request,
        model_visible_request=(expected_sealed_request.model_visible_request),
        canonical_schema=(
            choice_contract.context_v2_1_response_profile.canonical_schema()
        ),
        raw_provider_response=private_evidence["raw_provider_response"],
    )
    if independently_extracted != private_evidence["adapter_extracted_output"]:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_offline_replay_adapter_mismatch"
        )
    expansion, normalized_choice, total = _execute_context_v2_1_chain(
        model_output=independently_extracted,
        choice_contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        registry=registry,
    )
    comparison = _budget_smoke_semantic_comparison(
        normalized_answer=normalized_choice,
        expected_answer=exact_expected,
    )
    expected_validation = _validation_result(
        expansion=expansion,
        total=total,
    )
    expected_replay_authorities = _budget_smoke_replay_authorities(
        plan_slot=plan_slot,
        registry=registry,
        choice_contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        private_material=private_evidence,
    )
    if (
        private_evidence["normalized_semantic_choice"] != normalized_choice
        or private_evidence["semantic_choice_hash"] != sha256_json(normalized_choice)
        or any(private_evidence[field] != value for field, value in comparison.items())
        or private_evidence["expanded_canonical_decision"]
        != _json_roundtrip(expansion.to_private_dict())
        or private_evidence["validation_result"] != expected_validation
        or private_evidence["materialized_artifact_hash"]
        != total.canonical_artifact_hash
        or private_evidence["materialized_artifact_integrity_hash"]
        != total.canonical_artifact["integrity_hash"]
        or private_evidence["total_materialization_integrity_hash"]
        != total.integrity_hash
        or private_evidence["replay_authorities"] != expected_replay_authorities
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_offline_replay_mismatch")
    expected_safe = _budget_smoke_safe_receipt(
        private_evidence=private_evidence,
    )
    if safe_receipt != expected_safe:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_offline_replay_safe_receipt_mismatch"
        )
    return Gate2FinancialSemanticV6ContextV21BudgetSmokeReplayResult(
        schema_version=(V6_CONTEXT_V2_1_BUDGET_SMOKE_REPLAY_SCHEMA_VERSION),
        status="EXACT",
        private_evidence_hash=private_evidence["private_evidence_hash"],
        semantic_choice_hash=private_evidence["semantic_choice_hash"],
        expansion_integrity_hash=expansion.integrity_hash,
        materialized_artifact_hash=total.canonical_artifact_hash,
        materialized_artifact=copy.deepcopy(total.canonical_artifact),
        safe_receipt=copy.deepcopy(safe_receipt),
        provider_calls_total=0,
        provider_responses_total=0,
        retry_total=0,
        repair_total=0,
        fallback_total=0,
    )


def financial_semantic_v6_private_evidence_hash(
    private_evidence_without_hash: dict[str, Any],
) -> str:
    if (
        not isinstance(private_evidence_without_hash, dict)
        or tuple(private_evidence_without_hash) != _PRIVATE_FIELDS
    ):
        _fail("financial_semantic_v6_private_evidence_shape_invalid")
    return sha256_json(private_evidence_without_hash)


def restore_financial_semantic_v6_private_evidence(
    serialized: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(serialized, dict) or set(serialized) != {
        *_PRIVATE_FIELDS,
        "private_evidence_hash",
    }:
        _fail("financial_semantic_v6_private_evidence_shape_invalid")
    material = {
        field: copy.deepcopy(serialized[field]) for field in _PRIVATE_FIELDS
    }
    if serialized["private_evidence_hash"] != (
        financial_semantic_v6_private_evidence_hash(material)
    ):
        _fail("financial_semantic_v6_private_evidence_hash_invalid")
    expanded = material.get("expanded_canonical_decision")
    validated = (
        expanded.get("validated_decision")
        if isinstance(expanded, dict)
        else None
    )
    decision = (
        validated.get("decision")
        if isinstance(validated, dict)
        else None
    )
    candidate_refs = (
        validated.get("candidate_refs")
        if isinstance(validated, dict)
        else None
    )
    value_bindings = (
        decision.get("value_bindings")
        if isinstance(decision, dict)
        else None
    )
    if not isinstance(candidate_refs, list) or not isinstance(
        value_bindings,
        list,
    ):
        _fail("financial_semantic_v6_private_evidence_json_types_invalid")
    validated["candidate_refs"] = tuple(candidate_refs)
    decision["value_bindings"] = tuple(value_bindings)
    return {
        **material,
        "private_evidence_hash": serialized["private_evidence_hash"],
    }


def _execute_chain(
    *,
    model_output: str | dict[str, Any],
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> tuple[
    Gate2FinancialSemanticV6ExpandedDecision,
    dict[str, Any],
    Gate2FinancialSemanticV6TotalMaterialization,
]:
    try:
        expansion = Gate2FinancialSemanticV6DecisionExpansionFactory(
            registry=registry
        ).create(
            model_output=model_output,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
        )
    except Gate2FinancialSemanticV6ExpansionError as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_evidence_expansion_failed"
        ) from exc
    normalized_choice = _normalized_choice(expansion)
    if sha256_json(normalized_choice) != expansion.model_choice_hash:
        _fail("financial_semantic_v6_exact_choice_not_preserved")
    try:
        total = Gate2FinancialSemanticV6TotalMaterializerFactory(
            registry=registry
        ).create(
            expansion=expansion,
            model_output=normalized_choice,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
        )
    except Gate2FinancialSemanticV6TotalityError as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_evidence_materialization_failed"
        ) from exc
    return expansion, normalized_choice, total


def _execute_context_v2_1_chain(
    *,
    model_output: str | dict[str, Any],
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> tuple[
    Gate2FinancialSemanticV6ExpandedDecision,
    dict[str, Any],
    Gate2FinancialSemanticV6TotalMaterialization,
]:
    try:
        expansion = Gate2FinancialSemanticV6DecisionExpansionFactory(
            registry=registry
        ).create_from_context_v2_1_candidate(
            model_output=model_output,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
        )
    except Gate2FinancialSemanticV6ExpansionError as exc:
        cause = exc.__cause__
        if isinstance(cause, Gate2FinancialSemanticV6ChoiceError):
            raise Gate2FinancialSemanticV6DecisionEvidenceError(
                cause.code
            ) from exc
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_"
            "evidence_expansion_failed"
        ) from exc
    normalized_choice = _normalized_choice(expansion)
    if sha256_json(normalized_choice) != expansion.model_choice_hash:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "exact_choice_not_preserved"
        )
    try:
        total = Gate2FinancialSemanticV6TotalMaterializerFactory(
            registry=registry
        ).create_context_v2_1_candidate(
            expansion=expansion,
            model_output=model_output,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
        )
    except Gate2FinancialSemanticV6TotalityError as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_"
            "evidence_materialization_failed"
        ) from exc
    return expansion, normalized_choice, total


def _normalized_choice(
    expansion: Gate2FinancialSemanticV6ExpandedDecision,
) -> dict[str, Any]:
    if expansion.disposition == "typed_input":
        return {
            "disposition": "typed_input",
            "typed_option_id": expansion.selected_typed_option_id,
        }
    reason_code = expansion.validated_decision.decision.reason_code
    return {
        "disposition": "unclassified_financial_input",
        "reason_code": reason_code,
    }


def _validate_exact_request(
    *,
    canonical_request: Any,
    packet: Gate2FinancialSemanticV6Packet,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    exact_model_id: str,
) -> dict[str, Any]:
    expected = financial_semantic_v6_canonical_request(
        packet=packet,
        choice_contract=choice_contract,
        exact_model_id=exact_model_id,
    )
    if not isinstance(canonical_request, dict) or canonical_request != expected:
        _fail("financial_semantic_v6_canonical_request_identity_mismatch")
    try:
        return json.loads(
            json.dumps(
                canonical_request,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_canonical_request_invalid"
        ) from exc


def _validation_result(
    *,
    expansion: Gate2FinancialSemanticV6ExpandedDecision,
    total: Gate2FinancialSemanticV6TotalMaterialization,
) -> dict[str, Any]:
    return {
        "status": "passed",
        "expansion_integrity_hash": expansion.integrity_hash,
        "canonical_decision_hash": expansion.canonical_decision_hash,
        "validated_decision_hash": sha256_json(asdict(expansion.validated_decision)),
        "total_materialization_integrity_hash": total.integrity_hash,
        "materializer_totality_status": total.materializer_totality_status,
        "validated_but_unmaterializable": (total.validated_but_unmaterializable),
    }


def _replay_authorities(
    *,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    exact_model_id: str,
) -> dict[str, Any]:
    return {
        "model_id": exact_model_id,
        "request_profile": V6_QUALIFICATION_REQUEST_PROFILE,
        "registry_hash": registry.registry_hash,
        "source_package_integrity_hash": source_package.integrity_hash,
        "evidence_bundle_integrity_hash": evidence_bundle.integrity_hash,
        "candidate_compilation_integrity_hash": compilation.integrity_hash,
        "packet_hash": packet.packet_hash,
        "choice_schema_hash": choice_contract.choice_schema_hash,
    }


def _context_v2_1_replay_authorities(
    *,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    provider_profile_id: str,
    provider_adapter_id: str,
    provider_adapter_version: str,
    local_projection_model_id: str,
    schema_projection_policy_version: str,
    final_provider_request_hash: str,
    provider_visible_schema_hash: str,
    adapter_canonical_schema_hash: str,
    adapter_adapted_schema_hash: str,
) -> dict[str, Any]:
    return {
        "request_profile": (
            FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE
        ),
        "registry_hash": registry.registry_hash,
        "source_package_integrity_hash": source_package.integrity_hash,
        "evidence_bundle_integrity_hash": evidence_bundle.integrity_hash,
        "candidate_compilation_integrity_hash": compilation.integrity_hash,
        "packet_hash": packet.packet_hash,
        "context_v2_1_view_hash": packet.context_v2_candidate.view_hash,
        "mapping_receipt_hash": (
            packet.context_v2_mapping_receipt.integrity_hash
        ),
        "response_schema_hash": (
            choice_contract.context_v2_1_response_profile
            .response_schema_hash
        ),
        "canonical_choice_schema_hash": (
            choice_contract.choice_schema_hash
        ),
        "provider_profile_id": provider_profile_id,
        "provider_adapter_id": provider_adapter_id,
        "provider_adapter_version": provider_adapter_version,
        "local_projection_model_id": local_projection_model_id,
        "schema_projection_policy_version": (
            schema_projection_policy_version
        ),
        "final_provider_request_hash": final_provider_request_hash,
        "provider_visible_schema_hash": provider_visible_schema_hash,
        "adapter_canonical_schema_hash": adapter_canonical_schema_hash,
        "adapter_adapted_schema_hash": adapter_adapted_schema_hash,
    }


def _budget_smoke_plan_slot_identity(
    *,
    plan: Any,
    plan_slot: Any,
) -> dict[str, Any]:
    try:
        from .gate2_financial_semantic_v6_context_v2_1_budget_smoke_plan import (
            Gate2FinancialSemanticV6ContextV21BudgetSmokePlanError,
            financial_semantic_v6_context_v2_1_budget_smoke_operation_identity,
            validate_financial_semantic_v6_context_v2_1_budget_smoke_plan,
        )

        validate_financial_semantic_v6_context_v2_1_budget_smoke_plan(plan)
        operation_identity = (
            financial_semantic_v6_context_v2_1_budget_smoke_operation_identity(
                plan=plan,
                slot=plan_slot,
            )
        )
    except (
        AttributeError,
        TypeError,
        ValueError,
        Gate2FinancialSemanticV6ContextV21BudgetSmokePlanError,
    ) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_budget_smoke_plan_identity_invalid"
        ) from exc
    if (
        plan_slot not in plan.slots
        or plan_slot.request_profile
        != FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_plan_identity_invalid")
    for value in (
        plan.integrity_hash,
        plan_slot.integrity_hash,
        plan_slot.slot_id,
        plan_slot.provider_profile_id,
        plan_slot.provider_profile_revision,
        plan_slot.provider_id,
        plan_slot.provider_adapter_id,
        plan_slot.provider_adapter_version,
        plan_slot.exact_model_id,
        plan_slot.model_identity_kind,
        operation_identity,
    ):
        _bounded_context_v2_1_identity(value)
    caveat = plan_slot.model_identity_caveat
    if caveat is not None:
        _bounded_context_v2_1_identity(caveat)
    private_identity = {
        "plan_integrity_hash": plan.integrity_hash,
        "plan_slot_id": plan_slot.slot_id,
        "plan_slot_ordinal": plan_slot.ordinal,
        "plan_slot_integrity_hash": plan_slot.integrity_hash,
        "provider_profile_id": plan_slot.provider_profile_id,
        "provider_profile_revision": (plan_slot.provider_profile_revision),
        "provider_id": plan_slot.provider_id,
        "provider_adapter_id": plan_slot.provider_adapter_id,
        "provider_adapter_version": (plan_slot.provider_adapter_version),
        "exact_model_id": plan_slot.exact_model_id,
        "model_identity_kind": plan_slot.model_identity_kind,
        "immutable_model_id_proven": (plan_slot.immutable_model_id_proven),
        "model_identity_caveat": caveat,
    }
    return {
        "operation_identity": operation_identity,
        "private_identity": private_identity,
    }


def _budget_smoke_transport_contract_from_slot(
    plan_slot: Any,
) -> Gate2ContextV21BudgetSmokeTransportContract:
    try:
        snapshot = _budget_smoke_ordered_json_roundtrip(plan_slot.transport_contract)
        transport_policy = plan_slot.transport_policy
        transport_contract_hash = plan_slot.transport_contract_hash
        timeout_seconds = snapshot["timeout_seconds"]
        profile = gate2_provider_profile(plan_slot.provider_profile_id)
        if (
            not isinstance(snapshot, dict)
            or isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or transport_policy != CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
            or snapshot.get("transport_policy") != transport_policy
            or snapshot.get("actual_transport_type")
            != CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE
            or transport_contract_hash != sha256_json(snapshot)
        ):
            raise ValueError("transport_contract_identity_invalid")
        contract = (
            Gate2ProviderAdapterFactory(
                profile=profile,
                capability_probe=True,
                native_transport_config=Gate2NativeProviderTransportConfig(
                    timeout_seconds=timeout_seconds,
                ),
            )
            .create()
            .context_v2_1_budget_smoke_transport_contract(
                transport_policy=transport_policy,
            )
        )
        if (
            _budget_smoke_ordered_json_roundtrip(contract.safe_snapshot()) != snapshot
            or contract.integrity_hash != transport_contract_hash
        ):
            raise ValueError("transport_contract_projection_invalid")
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        Gate2SourceFactRuntimeError,
    ) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_budget_smoke_transport_contract_invalid"
        ) from exc
    return contract


def _budget_smoke_request_authority(
    *,
    plan_slot: Any,
    operation_identity: str,
    sealed_request: Gate2FinancialSemanticV6ContextV21SealedRequest,
    prepared_request: Gate2PreparedProviderRequest,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> dict[str, Any]:
    if (
        not isinstance(
            sealed_request,
            Gate2FinancialSemanticV6ContextV21SealedRequest,
        )
        or not isinstance(
            prepared_request,
            Gate2PreparedProviderRequest,
        )
        or plan_slot.request_profile
        != FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_request_invalid")
    try:
        validate_financial_semantic_v6_context_v2_1_sealed_request(
            sealed_request=sealed_request,
            packet=packet,
            choice_contract=choice_contract,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=registry,
            system_message=V6_SEMANTIC_SYSTEM_PROMPT,
            mapping_receipt=packet.context_v2_mapping_receipt,
        )
        provider_profile = gate2_provider_profile(plan_slot.provider_profile_id)
        prepared_request.validate_schema_binding()
    except (
        AttributeError,
        TypeError,
        ValueError,
        Gate2SourceFactRuntimeError,
    ) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_budget_smoke_request_invalid"
        ) from exc
    canonical_schema = choice_contract.context_v2_1_response_profile.canonical_schema()
    exact_sealed_request = _budget_smoke_ordered_json_roundtrip(asdict(sealed_request))
    exact_model_visible_request = _budget_smoke_ordered_json_roundtrip(
        sealed_request.model_visible_request
    )
    exact_prepared_request = _budget_smoke_ordered_json_roundtrip(
        asdict(prepared_request)
    )
    exact_final_provider_request = _budget_smoke_ordered_json_roundtrip(
        prepared_request.form_data
    )
    provider_visible_schema = _budget_smoke_ordered_json_roundtrip(
        prepared_request.provider_visible_schema
    )
    response_profile = choice_contract.context_v2_1_response_profile
    transport_contract = _budget_smoke_transport_contract_from_slot(plan_slot)
    transport_contract_snapshot = _budget_smoke_ordered_json_roundtrip(
        transport_contract.safe_snapshot()
    )
    if (
        provider_profile.profile_id != plan_slot.provider_profile_id
        or provider_profile.provider_id != plan_slot.provider_id
        or gate2_provider_profile_revision(provider_profile)
        != plan_slot.provider_profile_revision
        or provider_profile.adapter_id != plan_slot.provider_adapter_id
        or provider_profile.adapter_version != plan_slot.provider_adapter_version
        or prepared_request.provider_adapter_id != plan_slot.provider_adapter_id
        or exact_final_provider_request.get("model") != plan_slot.exact_model_id
        or (
            plan_slot.provider_adapter_id != "anthropic_native_messages"
            and exact_final_provider_request.get("stream") is not False
        )
        or (
            plan_slot.provider_adapter_id == "anthropic_native_messages"
            and "stream" in exact_final_provider_request
        )
        or sha256_json(exact_sealed_request) != plan_slot.sealed_request_hash
        or sealed_request.sealed_request_receipt.integrity_hash
        != plan_slot.sealed_request_receipt_integrity_hash
        or _budget_smoke_model_visible_request_hash(exact_model_visible_request)
        != plan_slot.model_visible_request_hash
        or sealed_request.sealed_request_receipt.model_visible_request_hash
        != plan_slot.model_visible_request_hash
        or sha256_json(canonical_schema) != plan_slot.canonical_schema_hash
        or sha256_json(exact_prepared_request) != plan_slot.prepared_request_hash
        or sha256_json(provider_visible_schema)
        != plan_slot.provider_visible_schema_hash
        or plan_slot.transport_policy != CONTEXT_V2_1_BUDGET_SMOKE_TRANSPORT_POLICY
        or transport_contract_snapshot != plan_slot.transport_contract
        or transport_contract.integrity_hash != plan_slot.transport_contract_hash
        or not prepared_request.context_v2_1_budget_smoke_contract_is_bound(
            canonical_schema=canonical_schema,
            provider_profile=provider_profile,
            model_visible_request=(sealed_request.model_visible_request),
            exact_model_id=plan_slot.exact_model_id,
            operation_identity=operation_identity,
        )
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_request_authority_mismatch"
        )
    return {
        "exact_sealed_request": exact_sealed_request,
        "sealed_request_hash": sha256_json(exact_sealed_request),
        "exact_model_visible_request": exact_model_visible_request,
        "model_visible_request_hash": _budget_smoke_model_visible_request_hash(
            exact_model_visible_request
        ),
        "exact_prepared_request": exact_prepared_request,
        "transport_policy": plan_slot.transport_policy,
        "transport_contract": transport_contract_snapshot,
        "transport_contract_hash": transport_contract.integrity_hash,
        "prepared_request_hash": sha256_json(exact_prepared_request),
        "exact_final_provider_request": (exact_final_provider_request),
        "final_provider_request_hash": sha256_json(exact_final_provider_request),
        "provider_visible_schema": provider_visible_schema,
        "provider_visible_schema_hash": sha256_json(provider_visible_schema),
        "schema_projection_policy_version": (
            prepared_request.projection_policy_version
        ),
        "adapter_canonical_schema_hash": (prepared_request.canonical_schema_hash),
        "adapter_adapted_schema_hash": (prepared_request.adapted_schema_hash),
        "response_profile_hash": (response_profile.response_schema_hash),
        "mapping_receipt_hash": (packet.context_v2_mapping_receipt.integrity_hash),
    }


def _budget_smoke_extract_adapter_output(
    *,
    plan_slot: Any,
    operation_identity: str,
    prepared_request: Gate2PreparedProviderRequest,
    model_visible_request: dict[str, Any],
    canonical_schema: dict[str, Any],
    raw_provider_response: dict[str, Any],
) -> Any:
    try:
        provider_profile = gate2_provider_profile(plan_slot.provider_profile_id)
        adapter = Gate2ProviderAdapterFactory(
            profile=provider_profile,
            capability_probe=True,
        ).create()
        extracted = adapter.extract_context_v2_1_budget_smoke_prepared_content(
            raw_provider_response,
            prepared_request=prepared_request,
            canonical_schema=canonical_schema,
            model_visible_request=model_visible_request,
            exact_model_id=plan_slot.exact_model_id,
            operation_identity=operation_identity,
        )
        return _json_roundtrip(extracted)
    except (
        TypeError,
        ValueError,
        Gate2SourceFactRuntimeError,
    ) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_budget_smoke_adapter_output_invalid"
        ) from exc


def _budget_smoke_success_execution_evidence(
    *,
    plan_slot: Any,
    operation_identity: str,
    prepared_request: Gate2PreparedProviderRequest,
    raw_provider_response: dict[str, Any],
    execution_metadata: Gate2ProviderExecutionMetadata,
    economy_budget_receipt: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    _budget_smoke_validate_raw_execution_metadata(
        plan_slot=plan_slot,
        prepared_request=prepared_request,
        raw_provider_response=raw_provider_response,
        execution_metadata=execution_metadata,
    )
    metadata_snapshot = _budget_smoke_execution_metadata_snapshot(
        plan_slot=plan_slot,
        prepared_request=prepared_request,
        execution_metadata=execution_metadata,
        require_terminal=True,
    )
    budget_snapshot = _budget_smoke_budget_receipt_snapshot(
        plan_slot=plan_slot,
        operation_identity=operation_identity,
        execution_metadata=execution_metadata,
        economy_budget_receipt=economy_budget_receipt,
    )
    return (
        metadata_snapshot,
        budget_snapshot,
        _budget_smoke_provider_metrics(
            metadata_snapshot=metadata_snapshot,
            budget_snapshot=budget_snapshot,
            elapsed_ms=execution_metadata.duration_ms,
            zero_when_absent=False,
        ),
    )


def _budget_smoke_failure_execution_evidence(
    *,
    plan_slot: Any,
    operation_identity: str,
    prepared_request: Gate2PreparedProviderRequest,
    execution_metadata: Gate2ProviderExecutionMetadata | None,
    economy_budget_receipt: dict[str, Any] | None,
    elapsed_ms: int,
    execution_accounting: dict[str, int],
) -> tuple[Any, Any, dict[str, Any]]:
    if (
        isinstance(elapsed_ms, bool)
        or not isinstance(elapsed_ms, int)
        or elapsed_ms < 0
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_failure_latency_invalid")
    if execution_metadata is None:
        metadata_snapshot = None
    else:
        metadata_snapshot = _budget_smoke_execution_metadata_snapshot(
            plan_slot=plan_slot,
            prepared_request=prepared_request,
            execution_metadata=execution_metadata,
            require_terminal=False,
        )
    if economy_budget_receipt is None:
        budget_snapshot = None
    else:
        if execution_metadata is None:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_failure_budget_without_metadata"
            )
        budget_snapshot = _budget_smoke_budget_receipt_snapshot(
            plan_slot=plan_slot,
            operation_identity=operation_identity,
            execution_metadata=execution_metadata,
            economy_budget_receipt=economy_budget_receipt,
        )
    if (
        execution_accounting["provider_responses_total"] == 0
        and budget_snapshot is not None
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_failure_execution_evidence_invalid"
        )
    return (
        metadata_snapshot,
        budget_snapshot,
        _budget_smoke_provider_metrics(
            metadata_snapshot=metadata_snapshot,
            budget_snapshot=budget_snapshot,
            elapsed_ms=elapsed_ms,
            zero_when_absent=(execution_accounting["provider_submissions_total"] == 0),
        ),
    )


def _budget_smoke_execution_metadata_snapshot(
    *,
    plan_slot: Any,
    prepared_request: Gate2PreparedProviderRequest,
    execution_metadata: Gate2ProviderExecutionMetadata,
    require_terminal: bool,
) -> dict[str, Any]:
    if not isinstance(
        execution_metadata,
        Gate2ProviderExecutionMetadata,
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_execution_metadata_invalid"
        )
    profile = gate2_provider_profile(plan_slot.provider_profile_id)
    transport_contract = _budget_smoke_transport_contract_from_slot(plan_slot)
    snapshot = _json_roundtrip(asdict(execution_metadata))
    if (
        execution_metadata.provider_id != plan_slot.provider_id
        or execution_metadata.provider_profile_id != plan_slot.provider_profile_id
        or execution_metadata.provider_profile_revision
        != plan_slot.provider_profile_revision
        or execution_metadata.adapter_id != plan_slot.provider_adapter_id
        or execution_metadata.adapter_version != plan_slot.provider_adapter_version
        or execution_metadata.requested_model_id != plan_slot.exact_model_id
        or execution_metadata.structured_output_mode != profile.structured_output_mode
        or execution_metadata.response_format_type != profile.response_format_type
        or execution_metadata.response_format_schema_mode
        != profile.response_format_schema_mode
        or execution_metadata.transport_type != transport_contract.actual_transport_type
        or execution_metadata.transport_type
        != CONTEXT_V2_1_BUDGET_SMOKE_ACTUAL_TRANSPORT_TYPE
        or execution_metadata.canonical_request_schema_hash
        != prepared_request.canonical_schema_hash
        or execution_metadata.adapted_request_schema_hash
        != prepared_request.adapted_schema_hash
        or execution_metadata.schema_transform_count
        != prepared_request.schema_transform_count
        or (
            execution_metadata.resolved_model_id is not None
            and execution_metadata.resolved_model_id != plan_slot.exact_model_id
        )
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_execution_metadata_invalid"
        )
    if require_terminal:
        expected_finish = (
            "end_turn"
            if plan_slot.provider_adapter_id == "anthropic_native_messages"
            else "stop"
        )
        for value in (
            execution_metadata.duration_ms,
            execution_metadata.input_tokens,
            execution_metadata.output_tokens,
            execution_metadata.total_tokens,
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                _fail(
                    "financial_semantic_v6_context_v2_1_"
                    "budget_smoke_execution_usage_invalid"
                )
        if (
            execution_metadata.resolved_model_id != plan_slot.exact_model_id
            or execution_metadata.finish_reason != expected_finish
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_execution_terminal_invalid"
            )
    return snapshot


def _budget_smoke_validate_raw_execution_metadata(
    *,
    plan_slot: Any,
    prepared_request: Gate2PreparedProviderRequest,
    raw_provider_response: dict[str, Any],
    execution_metadata: Gate2ProviderExecutionMetadata,
) -> None:
    try:
        profile = gate2_provider_profile(plan_slot.provider_profile_id)
        transport_contract = _budget_smoke_transport_contract_from_slot(plan_slot)
        derived = (
            Gate2ProviderAdapterFactory(
                profile=profile,
                capability_probe=True,
                native_transport_config=Gate2NativeProviderTransportConfig(
                    timeout_seconds=transport_contract.timeout_seconds,
                ),
            )
            .create()
            .context_v2_1_budget_smoke_execution_metadata(
                payload=raw_provider_response,
                requested_model_id=plan_slot.exact_model_id,
                duration_ms=execution_metadata.duration_ms,
                prepared_request=prepared_request,
                transport_contract=transport_contract,
            )
        )
    except (
        TypeError,
        ValueError,
        Gate2SourceFactRuntimeError,
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_raw_execution_metadata_invalid"
        ) from exc
    derived_snapshot = asdict(derived)
    observed_snapshot = asdict(execution_metadata)
    for optional_usage_field in (
        "cached_input_tokens",
        "reasoning_tokens",
    ):
        if derived_snapshot[optional_usage_field] in {None, 0} and observed_snapshot[
            optional_usage_field
        ] in {None, 0}:
            derived_snapshot[optional_usage_field] = None
            observed_snapshot[optional_usage_field] = None
    if derived_snapshot != observed_snapshot:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_raw_execution_metadata_invalid"
        )


def _budget_smoke_budget_receipt_snapshot(
    *,
    plan_slot: Any,
    operation_identity: str,
    execution_metadata: Gate2ProviderExecutionMetadata,
    economy_budget_receipt: dict[str, Any],
) -> dict[str, Any]:
    receipt = _json_roundtrip(economy_budget_receipt)
    if not isinstance(receipt, dict):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_budget_receipt_invalid")
    material = {
        key: copy.deepcopy(value)
        for key, value in receipt.items()
        if key != "integrity_hash"
    }
    if (
        receipt.get("integrity_hash") != sha256_json(material)
        or receipt.get("status") != "passed"
        or receipt.get("budget_status") != "within_budget"
        or receipt.get("provider_id") != plan_slot.provider_id
        or receipt.get("provider_profile_id") != plan_slot.provider_profile_id
        or receipt.get("requested_model_id") != plan_slot.exact_model_id
        or receipt.get("exact_model_id") != plan_slot.exact_model_id
        or receipt.get("resolved_model_id") != plan_slot.exact_model_id
        or receipt.get("operation_identity_sha256") != _sha256_text(operation_identity)
        or receipt.get("input_tokens") != execution_metadata.input_tokens
        or receipt.get("output_tokens") != execution_metadata.output_tokens
        or receipt.get("call_count") != 1
        or receipt.get("fallback_call") is not False
        or receipt.get("fallback_calls_authorized_total") != 0
        or receipt.get("paid_tools_used") != 0
        or receipt.get("actual_cost_observation", {}).get("status") != "recorded"
        or receipt.get("actual_cost_observation", {}).get("cost_usd")
        != receipt.get("actual_cost_usd")
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_budget_receipt_invalid")
    _budget_smoke_cost(receipt.get("actual_cost_usd"))
    return receipt


def _budget_smoke_provider_metrics(
    *,
    metadata_snapshot: dict[str, Any] | None,
    budget_snapshot: dict[str, Any] | None,
    elapsed_ms: int | None,
    zero_when_absent: bool,
) -> dict[str, Any]:
    if zero_when_absent:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "actual_cost_usd": "0",
            "latency_ms": 0,
        }
    metadata = metadata_snapshot or {}
    budget = budget_snapshot or {}
    input_tokens = budget.get("input_tokens")
    if input_tokens is None:
        input_tokens = metadata.get("input_tokens")
    output_tokens = budget.get("output_tokens")
    if output_tokens is None:
        output_tokens = metadata.get("output_tokens")
    input_tokens = _budget_smoke_nonnegative_int(
        input_tokens,
        default=None,
    )
    output_tokens = _budget_smoke_nonnegative_int(
        output_tokens,
        default=None,
    )
    total_tokens = metadata.get("total_tokens")
    inferred_total = (
        input_tokens + output_tokens
        if input_tokens is not None and output_tokens is not None
        else None
    )
    total_tokens = _budget_smoke_nonnegative_int(
        total_tokens,
        default=inferred_total,
    )
    measured_elapsed = elapsed_ms if metadata_snapshot is not None else None
    latency_ms = _budget_smoke_nonnegative_int(
        metadata.get("duration_ms"),
        default=_budget_smoke_nonnegative_int(
            measured_elapsed,
            default=None,
        ),
    )
    actual_cost = budget.get("actual_cost_usd")
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "actual_cost_usd": (
            _budget_smoke_cost(actual_cost) if actual_cost is not None else None
        ),
        "latency_ms": latency_ms,
    }


def _budget_smoke_expected_answer(
    value: Any,
    *,
    expected_hash: str,
) -> dict[str, Any]:
    answer = _json_roundtrip(value)
    if not isinstance(answer, dict):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_expected_answer_invalid")
    disposition = answer.get("disposition")
    if disposition == "typed_input":
        valid = (
            set(answer) == {"disposition", "typed_option_id"}
            and isinstance(answer.get("typed_option_id"), str)
            and bool(answer["typed_option_id"])
        )
    elif disposition == "unclassified_financial_input":
        valid = set(answer) == {"disposition", "reason_code"} and answer.get(
            "reason_code"
        ) in {
            "no_registry_type",
            "ambiguous_registry_type",
            "single_registry_type_no_safe_record",
        }
    else:
        valid = False
    if (
        not valid
        or _SHA256_RE.fullmatch(expected_hash) is None
        or sha256_json(answer) != expected_hash
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_expected_answer_invalid")
    return answer


def _budget_smoke_semantic_comparison(
    *,
    normalized_answer: dict[str, Any],
    expected_answer: dict[str, Any],
) -> dict[str, Any]:
    exact_normalized = _json_roundtrip(normalized_answer)
    exact_expected = _json_roundtrip(expected_answer)
    field_level_diff = _budget_smoke_mechanical_diff(
        expected_answer=exact_expected,
        actual_answer=exact_normalized,
    )
    semantic_exact_match = field_level_diff["all_fields_match"]
    error_category: str | None = None
    if not semantic_exact_match:
        expected_disposition = exact_expected["disposition"]
        observed_disposition = exact_normalized["disposition"]
        if (
            expected_disposition == "typed_input"
            and observed_disposition == "typed_input"
        ):
            error_category = "wrong_typed_type"
        elif (
            expected_disposition == "unclassified_financial_input"
            and observed_disposition == "typed_input"
        ):
            error_category = "unsafe_typed"
        elif (
            expected_disposition == "typed_input"
            and observed_disposition == "unclassified_financial_input"
        ):
            error_category = "safe_under_typing"
        elif (
            expected_disposition == "unclassified_financial_input"
            and observed_disposition == "unclassified_financial_input"
        ):
            error_category = "wrong_unclassified_reason"
        if error_category not in _BUDGET_SMOKE_SEMANTIC_ERROR_CATEGORIES:
            _fail(
                "financial_semantic_v6_context_v2_1_budget_smoke_semantic_diff_invalid"
            )
    return {
        "field_level_diff": field_level_diff,
        "field_level_diff_hash": sha256_json(field_level_diff),
        "semantic_exact_match": semantic_exact_match,
        "technical_verdict": "TECHNICAL_SMOKE_PASSED",
        "semantic_verdict": (
            "SEMANTIC_SMOKE_PASSED" if semantic_exact_match else "SEMANTIC_SMOKE_FAILED"
        ),
        "error_category": error_category,
    }


def _budget_smoke_failure_diff(
    expected_answer: dict[str, Any],
) -> dict[str, Any]:
    return _budget_smoke_mechanical_diff(
        expected_answer=expected_answer,
        actual_answer=None,
    )


def _budget_smoke_mechanical_diff(
    *,
    expected_answer: dict[str, Any],
    actual_answer: dict[str, Any] | None,
) -> dict[str, Any]:
    actual_mapping = actual_answer or {}
    field_rows = []
    for field in _BUDGET_SMOKE_SEMANTIC_FIELDS:
        expected_present = field in expected_answer
        actual_present = field in actual_mapping
        if not expected_present and not actual_present:
            continue
        field_rows.append(
            {
                "field": field,
                "expected_present": expected_present,
                "expected_value": (
                    copy.deepcopy(expected_answer.get(field))
                    if expected_present
                    else None
                ),
                "actual_present": actual_present,
                "actual_value": (
                    copy.deepcopy(actual_mapping.get(field)) if actual_present else None
                ),
                "exact_match": (
                    expected_present
                    and actual_present
                    and expected_answer[field] == actual_mapping[field]
                ),
            }
        )
    return {
        "all_fields_match": (
            actual_answer is not None
            and expected_answer == actual_answer
            and all(row["exact_match"] for row in field_rows)
        ),
        "fields": field_rows,
    }


def _budget_smoke_failure_accounting(
    lifecycle: Any,
) -> dict[str, int]:
    expected_fields = set(_BUDGET_SMOKE_SUCCESS_ACCOUNTING)
    if not isinstance(lifecycle, dict) or set(lifecycle) != expected_fields:
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_failure_lifecycle_invalid"
        )
    values = tuple(lifecycle.values())
    if (
        any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in values
        )
        or lifecycle["provider_responses_total"]
        > lifecycle["provider_submissions_total"]
        or lifecycle["provider_submissions_total"]
        > lifecycle["local_invocations_total"]
        or any(
            lifecycle[field] != 0
            for field in (
                "semantic_repair_total",
                "retry_total",
                "repair_total",
                "fallback_total",
            )
        )
        or any(
            lifecycle[field] not in {0, 1}
            for field in (
                "local_invocations_total",
                "provider_submissions_total",
                "provider_responses_total",
            )
        )
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_failure_lifecycle_invalid"
        )
    return copy.deepcopy(lifecycle)


def _budget_smoke_replay_authorities(
    *,
    plan_slot: Any,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    private_material: dict[str, Any],
) -> dict[str, Any]:
    return {
        "request_profile": (
            FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
        ),
        "plan_integrity_hash": private_material["plan_integrity_hash"],
        "plan_slot_integrity_hash": plan_slot.integrity_hash,
        "registry_hash": registry.registry_hash,
        "source_package_integrity_hash": source_package.integrity_hash,
        "evidence_bundle_integrity_hash": (evidence_bundle.integrity_hash),
        "candidate_compilation_integrity_hash": (compilation.integrity_hash),
        "packet_hash": packet.packet_hash,
        "context_v2_1_view_hash": (packet.context_v2_candidate.view_hash),
        "mapping_receipt_hash": private_material["mapping_receipt_hash"],
        "response_schema_hash": private_material["response_profile_hash"],
        "canonical_choice_schema_hash": (choice_contract.choice_schema_hash),
        "provider_profile_id": plan_slot.provider_profile_id,
        "provider_profile_revision": (plan_slot.provider_profile_revision),
        "provider_adapter_id": plan_slot.provider_adapter_id,
        "provider_adapter_version": (plan_slot.provider_adapter_version),
        "exact_model_id": plan_slot.exact_model_id,
        "operation_identity_hash": private_material["operation_identity_hash"],
        "sealed_request_hash": private_material["sealed_request_hash"],
        "prepared_request_hash": private_material["prepared_request_hash"],
        "transport_policy": private_material["transport_policy"],
        "transport_contract_hash": private_material["transport_contract_hash"],
        "provider_visible_schema_hash": private_material[
            "provider_visible_schema_hash"
        ],
        "adapter_extracted_output_hash": private_material[
            "adapter_extracted_output_hash"
        ],
        "raw_provider_response_hash": private_material["raw_provider_response_hash"],
        "expected_answer_hash": private_material["expected_answer_hash"],
        "provider_execution_metadata_hash": private_material[
            "provider_execution_metadata_hash"
        ],
        "economy_budget_receipt_hash": private_material["economy_budget_receipt_hash"],
    }


def _validate_budget_smoke_private_evidence(
    private_evidence: Any,
) -> None:
    if not isinstance(private_evidence, dict):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_private_evidence_shape_invalid"
        )
    schema_version = private_evidence.get("schema_version")
    if schema_version == (V6_CONTEXT_V2_1_BUDGET_SMOKE_PRIVATE_EVIDENCE_SCHEMA_VERSION):
        fields = _BUDGET_SMOKE_SUCCESS_PRIVATE_FIELDS
        success = True
    elif schema_version == (
        V6_CONTEXT_V2_1_BUDGET_SMOKE_FAILURE_PRIVATE_EVIDENCE_SCHEMA_VERSION
    ):
        fields = _BUDGET_SMOKE_FAILURE_PRIVATE_FIELDS
        success = False
    else:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_private_evidence_schema_invalid"
        )
    if set(private_evidence) != {*fields, "private_evidence_hash"}:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_private_evidence_shape_invalid"
        )
    json_safe = _json_roundtrip(private_evidence)
    if json_safe != private_evidence:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_private_evidence_json_invalid"
        )
    material = {field: copy.deepcopy(private_evidence[field]) for field in fields}
    if private_evidence["private_evidence_hash"] != sha256_json(material):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_private_evidence_hash_invalid"
        )
    _case_id(private_evidence["case_id"])
    for field in (
        "plan_integrity_hash",
        "plan_slot_integrity_hash",
        "operation_identity_hash",
        "sealed_request_hash",
        "model_visible_request_hash",
        "prepared_request_hash",
        "transport_contract_hash",
        "final_provider_request_hash",
        "provider_visible_schema_hash",
        "adapter_canonical_schema_hash",
        "adapter_adapted_schema_hash",
        "response_profile_hash",
        "mapping_receipt_hash",
        "adapter_extracted_output_hash",
        "semantic_choice_hash",
        "expected_answer_hash",
        "field_level_diff_hash",
        "provider_execution_metadata_hash",
        "economy_budget_receipt_hash",
        "private_evidence_hash",
    ):
        if _SHA256_RE.fullmatch(private_evidence[field]) is None:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_private_evidence_identity_invalid"
            )
    raw_hash_field = "raw_provider_response_hash" if success else "raw_output_hash"
    if _SHA256_RE.fullmatch(private_evidence[raw_hash_field]) is None:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_private_evidence_identity_invalid"
        )
    for field in (
        "plan_slot_id",
        "provider_profile_id",
        "provider_profile_revision",
        "provider_id",
        "provider_adapter_id",
        "provider_adapter_version",
        "exact_model_id",
        "model_identity_kind",
        "operation_identity",
        "request_profile",
        "transport_policy",
        "schema_projection_policy_version",
    ):
        _bounded_context_v2_1_identity(private_evidence[field])
    if private_evidence["model_identity_caveat"] is not None:
        _bounded_context_v2_1_identity(private_evidence["model_identity_caveat"])
    if (
        private_evidence["request_profile"]
        != FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_BUDGET_SMOKE_REQUEST_PROFILE
        or private_evidence["operation_identity_hash"]
        != _sha256_text(private_evidence["operation_identity"])
        or private_evidence["sealed_request_hash"]
        != sha256_json(private_evidence["exact_sealed_request"])
        or private_evidence["model_visible_request_hash"]
        != _budget_smoke_model_visible_request_hash(
            private_evidence["exact_model_visible_request"]
        )
        or private_evidence["prepared_request_hash"]
        != sha256_json(private_evidence["exact_prepared_request"])
        or private_evidence["transport_contract_hash"]
        != sha256_json(private_evidence["transport_contract"])
        or private_evidence["final_provider_request_hash"]
        != sha256_json(private_evidence["exact_final_provider_request"])
        or private_evidence["provider_visible_schema_hash"]
        != sha256_json(private_evidence["provider_visible_schema"])
        or private_evidence["adapter_extracted_output_hash"]
        != sha256_json(private_evidence["adapter_extracted_output"])
        or private_evidence["semantic_choice_hash"]
        != sha256_json(private_evidence["normalized_semantic_choice"])
        or private_evidence["expected_answer_hash"]
        != sha256_json(private_evidence["expected_answer"])
        or private_evidence["field_level_diff_hash"]
        != sha256_json(private_evidence["field_level_diff"])
        or private_evidence["provider_execution_metadata_hash"]
        != sha256_json(private_evidence["provider_execution_metadata"])
        or private_evidence["economy_budget_receipt_hash"]
        != sha256_json(private_evidence["economy_budget_receipt"])
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_private_evidence_identity_invalid"
        )
    prepared_request = _budget_smoke_prepared_request_from_snapshot(
        private_evidence["exact_prepared_request"]
    )
    private_slot = _budget_smoke_private_slot(private_evidence)
    _budget_smoke_transport_contract_from_slot(private_slot)
    canonical_schema = (
        private_evidence["exact_model_visible_request"]
        .get("response_format", {})
        .get("json_schema", {})
        .get("schema")
    )
    profile = gate2_provider_profile(private_evidence["provider_profile_id"])
    if (
        not isinstance(canonical_schema, dict)
        or private_evidence["exact_final_provider_request"]
        != prepared_request.form_data
        or private_evidence["provider_visible_schema"]
        != prepared_request.provider_visible_schema
        or private_evidence["adapter_canonical_schema_hash"]
        != prepared_request.canonical_schema_hash
        or private_evidence["adapter_adapted_schema_hash"]
        != prepared_request.adapted_schema_hash
        or private_evidence["schema_projection_policy_version"]
        != prepared_request.projection_policy_version
        or profile.provider_id != private_slot.provider_id
        or gate2_provider_profile_revision(profile)
        != private_slot.provider_profile_revision
        or profile.adapter_id != private_slot.provider_adapter_id
        or profile.adapter_version != private_slot.provider_adapter_version
        or not prepared_request.context_v2_1_budget_smoke_contract_is_bound(
            canonical_schema=canonical_schema,
            provider_profile=profile,
            model_visible_request=private_evidence["exact_model_visible_request"],
            exact_model_id=private_slot.exact_model_id,
            operation_identity=private_evidence["operation_identity"],
        )
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_private_request_invalid")
    exact_expected = _budget_smoke_expected_answer(
        private_evidence["expected_answer"],
        expected_hash=private_evidence["expected_answer_hash"],
    )
    accounting = private_evidence["execution_accounting"]
    _validate_budget_smoke_accounting(accounting, success=success)
    if success:
        _validate_budget_smoke_success_private(
            private_evidence=private_evidence,
            private_slot=private_slot,
            prepared_request=prepared_request,
            canonical_schema=canonical_schema,
            exact_expected=exact_expected,
        )
    else:
        _validate_budget_smoke_failure_private(
            private_evidence=private_evidence,
            private_slot=private_slot,
            prepared_request=prepared_request,
            canonical_schema=canonical_schema,
            exact_expected=exact_expected,
        )


def _validate_budget_smoke_success_private(
    *,
    private_evidence: dict[str, Any],
    private_slot: Any,
    prepared_request: Gate2PreparedProviderRequest,
    canonical_schema: dict[str, Any],
    exact_expected: dict[str, Any],
) -> None:
    if private_evidence["immutable_model_id_proven"] is not True:
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_unproven_model_executed")
    raw_response = private_evidence["raw_provider_response"]
    if not isinstance(raw_response, dict) or private_evidence[
        "raw_provider_response_hash"
    ] != sha256_json(raw_response):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_raw_provider_response_invalid"
        )
    extracted = _budget_smoke_extract_adapter_output(
        plan_slot=private_slot,
        operation_identity=private_evidence["operation_identity"],
        prepared_request=prepared_request,
        model_visible_request=private_evidence["exact_model_visible_request"],
        canonical_schema=canonical_schema,
        raw_provider_response=raw_response,
    )
    comparison = _budget_smoke_semantic_comparison(
        normalized_answer=private_evidence["normalized_semantic_choice"],
        expected_answer=exact_expected,
    )
    metadata = _budget_smoke_execution_metadata_from_snapshot(
        private_evidence["provider_execution_metadata"]
    )
    _budget_smoke_validate_raw_execution_metadata(
        plan_slot=private_slot,
        prepared_request=prepared_request,
        raw_provider_response=raw_response,
        execution_metadata=metadata,
    )
    metadata_snapshot = _budget_smoke_execution_metadata_snapshot(
        plan_slot=private_slot,
        prepared_request=prepared_request,
        execution_metadata=metadata,
        require_terminal=True,
    )
    budget_snapshot = _budget_smoke_budget_receipt_snapshot(
        plan_slot=private_slot,
        operation_identity=private_evidence["operation_identity"],
        execution_metadata=metadata,
        economy_budget_receipt=private_evidence["economy_budget_receipt"],
    )
    metrics = _budget_smoke_provider_metrics(
        metadata_snapshot=metadata_snapshot,
        budget_snapshot=budget_snapshot,
        elapsed_ms=metadata.duration_ms,
        zero_when_absent=False,
    )
    if (
        extracted != private_evidence["adapter_extracted_output"]
        or any(private_evidence[field] != value for field, value in comparison.items())
        or private_evidence["provider_metrics"] != metrics
        or not isinstance(
            private_evidence["expanded_canonical_decision"],
            dict,
        )
        or not isinstance(private_evidence["validation_result"], dict)
        or not isinstance(private_evidence["replay_authorities"], dict)
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_success_evidence_invalid"
        )


def _validate_budget_smoke_failure_private(
    *,
    private_evidence: dict[str, Any],
    private_slot: Any,
    prepared_request: Gate2PreparedProviderRequest,
    canonical_schema: dict[str, Any],
    exact_expected: dict[str, Any],
) -> None:
    if (
        private_evidence["error_category"] not in _BUDGET_SMOKE_FAILURE_ERROR_CATEGORIES
        or private_evidence["failure_code"]
        != _budget_smoke_identifier(private_evidence["failure_code"])
        or private_evidence["failure_class"]
        != _budget_smoke_identifier(private_evidence["failure_class"])
        or private_evidence["normalized_semantic_choice"] is not None
        or private_evidence["semantic_exact_match"] is not False
        or private_evidence["technical_verdict"] != "TECHNICAL_SMOKE_FAILED"
        or private_evidence["semantic_verdict"] != "SEMANTIC_SMOKE_FAILED"
        or private_evidence["field_level_diff"]
        != _budget_smoke_failure_diff(exact_expected)
        or private_evidence["raw_output_hash"]
        != sha256_json(private_evidence["raw_output"])
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_failure_evidence_invalid"
        )
    accounting = private_evidence["execution_accounting"]
    metadata_snapshot = private_evidence["provider_execution_metadata"]
    budget_snapshot = private_evidence["economy_budget_receipt"]
    if metadata_snapshot is None:
        metadata = None
    else:
        metadata = _budget_smoke_execution_metadata_from_snapshot(metadata_snapshot)
        expected_metadata = _budget_smoke_execution_metadata_snapshot(
            plan_slot=private_slot,
            prepared_request=prepared_request,
            execution_metadata=metadata,
            require_terminal=(private_evidence["adapter_extracted_output"] is not None),
        )
        if metadata_snapshot != expected_metadata:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_failure_metadata_invalid"
            )
    independently_extracted = None
    adapter_extraction_succeeded = False
    if (
        accounting["provider_responses_total"] == 1
        and metadata is not None
        and isinstance(private_evidence["raw_output"], dict)
    ):
        try:
            independently_extracted = _budget_smoke_extract_adapter_output(
                plan_slot=private_slot,
                operation_identity=private_evidence["operation_identity"],
                prepared_request=prepared_request,
                model_visible_request=private_evidence["exact_model_visible_request"],
                canonical_schema=canonical_schema,
                raw_provider_response=private_evidence["raw_output"],
            )
        except Gate2FinancialSemanticV6DecisionEvidenceError:
            independently_extracted = None
        else:
            adapter_extraction_succeeded = True
            _budget_smoke_validate_raw_execution_metadata(
                plan_slot=private_slot,
                prepared_request=prepared_request,
                raw_provider_response=private_evidence["raw_output"],
                execution_metadata=metadata,
            )
            terminal_metadata = _budget_smoke_execution_metadata_snapshot(
                plan_slot=private_slot,
                prepared_request=prepared_request,
                execution_metadata=metadata,
                require_terminal=True,
            )
            if metadata_snapshot != terminal_metadata:
                _fail(
                    "financial_semantic_v6_context_v2_1_"
                    "budget_smoke_failure_metadata_invalid"
                )
    if (
        adapter_extraction_succeeded
        and independently_extracted != private_evidence["adapter_extracted_output"]
    ) or (
        not adapter_extraction_succeeded
        and private_evidence["adapter_extracted_output"] is not None
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_failure_adapter_output_invalid"
        )
    if budget_snapshot is not None:
        if metadata is None:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_failure_budget_without_metadata"
            )
        expected_budget = _budget_smoke_budget_receipt_snapshot(
            plan_slot=private_slot,
            operation_identity=private_evidence["operation_identity"],
            execution_metadata=metadata,
            economy_budget_receipt=budget_snapshot,
        )
        if budget_snapshot != expected_budget:
            _fail(
                "financial_semantic_v6_context_v2_1_budget_smoke_failure_budget_invalid"
            )
    if accounting["provider_responses_total"] == 0 and budget_snapshot is not None:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_failure_execution_evidence_invalid"
        )
    if metadata is not None:
        response_only_values = (
            metadata.provider_response_id,
            metadata.input_tokens,
            metadata.output_tokens,
            metadata.total_tokens,
            metadata.finish_reason,
        )
        if accounting["provider_responses_total"] == 0 and any(
            value is not None for value in response_only_values
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "budget_smoke_failure_execution_evidence_invalid"
            )
    if accounting["provider_responses_total"] == 1 and metadata_snapshot is None:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_failure_execution_evidence_invalid"
        )
    if private_evidence["immutable_model_id_proven"] is not True and (
        private_evidence["error_category"] != "infrastructure_provider_failure"
        or accounting["provider_submissions_total"] != 0
        or accounting["provider_responses_total"] != 0
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_unproven_model_executed")
    metrics = _budget_smoke_provider_metrics(
        metadata_snapshot=metadata_snapshot,
        budget_snapshot=budget_snapshot,
        elapsed_ms=private_evidence["provider_metrics"].get("latency_ms"),
        zero_when_absent=(accounting["provider_submissions_total"] == 0),
    )
    if private_evidence["provider_metrics"] != metrics:
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_failure_metrics_invalid")


def _validate_budget_smoke_accounting(
    accounting: Any,
    *,
    success: bool,
) -> None:
    expected_fields = set(_BUDGET_SMOKE_SUCCESS_ACCOUNTING)
    if (
        not isinstance(accounting, dict)
        or set(accounting) != expected_fields
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in accounting.values()
        )
        or accounting["provider_responses_total"]
        > accounting["provider_submissions_total"]
        or accounting["provider_submissions_total"]
        > accounting["local_invocations_total"]
        or any(
            accounting[field] != 0
            for field in (
                "semantic_repair_total",
                "retry_total",
                "repair_total",
                "fallback_total",
            )
        )
        or (success and accounting != _BUDGET_SMOKE_SUCCESS_ACCOUNTING)
        or (
            not success
            and any(
                accounting[field] not in {0, 1}
                for field in (
                    "local_invocations_total",
                    "provider_submissions_total",
                    "provider_responses_total",
                )
            )
        )
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_execution_accounting_invalid"
        )


def _validate_budget_smoke_private_plan_binding(
    *,
    private_evidence: dict[str, Any],
    plan: Any,
    plan_slot: Any,
) -> None:
    identity = _budget_smoke_plan_slot_identity(
        plan=plan,
        plan_slot=plan_slot,
    )
    expected_private = identity["private_identity"]
    if (
        any(
            private_evidence[field] != value
            for field, value in expected_private.items()
        )
        or private_evidence["case_id"] != plan_slot.case_id
        or private_evidence["operation_identity"] != identity["operation_identity"]
        or private_evidence["request_profile"] != plan_slot.request_profile
        or private_evidence["sealed_request_hash"] != plan_slot.sealed_request_hash
        or private_evidence["model_visible_request_hash"]
        != plan_slot.model_visible_request_hash
        or private_evidence["prepared_request_hash"] != plan_slot.prepared_request_hash
        or private_evidence["transport_policy"] != plan_slot.transport_policy
        or private_evidence["transport_contract"] != plan_slot.transport_contract
        or private_evidence["transport_contract_hash"]
        != plan_slot.transport_contract_hash
        or private_evidence["provider_visible_schema_hash"]
        != plan_slot.provider_visible_schema_hash
        or private_evidence["expected_answer_hash"] != plan_slot.expected_answer_hash
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_plan_evidence_mismatch")


def _budget_smoke_safe_receipt(
    *,
    private_evidence: dict[str, Any],
) -> dict[str, Any]:
    success = private_evidence["schema_version"] == (
        V6_CONTEXT_V2_1_BUDGET_SMOKE_PRIVATE_EVIDENCE_SCHEMA_VERSION
    )
    accounting = private_evidence["execution_accounting"]
    metrics = private_evidence["provider_metrics"]
    raw_hash = private_evidence[
        "raw_provider_response_hash" if success else "raw_output_hash"
    ]
    verdicts = {
        "technical": private_evidence["technical_verdict"],
        "semantic": private_evidence["semantic_verdict"],
        "semantic_exact_match": private_evidence["semantic_exact_match"],
        "error_category": private_evidence["error_category"],
        "failure_code": (None if success else private_evidence["failure_code"]),
        "failure_class": (None if success else private_evidence["failure_class"]),
    }
    material = {
        "schema_version": (V6_CONTEXT_V2_1_BUDGET_SMOKE_SAFE_RECEIPT_SCHEMA_VERSION),
        "case_id": private_evidence["case_id"],
        "plan_slot_id": private_evidence["plan_slot_id"],
        "provider_profile_id": private_evidence["provider_profile_id"],
        "exact_model_id": private_evidence["exact_model_id"],
        "status": (
            "passed"
            if verdicts["technical"] == "TECHNICAL_SMOKE_PASSED"
            and verdicts["semantic"] == "SEMANTIC_SMOKE_PASSED"
            else "failed"
        ),
        "verdicts": verdicts,
        "transport": {
            "policy": private_evidence["transport_policy"],
            "contract": copy.deepcopy(private_evidence["transport_contract"]),
            "contract_hash": private_evidence["transport_contract_hash"],
        },
        "hashes": {
            "plan_integrity_hash": private_evidence["plan_integrity_hash"],
            "plan_slot_integrity_hash": private_evidence["plan_slot_integrity_hash"],
            "private_evidence_hash": private_evidence["private_evidence_hash"],
            "sealed_request_hash": private_evidence["sealed_request_hash"],
            "prepared_request_hash": private_evidence["prepared_request_hash"],
            "transport_contract_hash": private_evidence["transport_contract_hash"],
            "provider_visible_schema_hash": private_evidence[
                "provider_visible_schema_hash"
            ],
            "adapter_extracted_output_hash": private_evidence[
                "adapter_extracted_output_hash"
            ],
            "raw_execution_output_hash": raw_hash,
            "semantic_choice_hash": private_evidence["semantic_choice_hash"],
            "expected_answer_hash": private_evidence["expected_answer_hash"],
            "field_level_diff_hash": private_evidence["field_level_diff_hash"],
            "provider_execution_metadata_hash": private_evidence[
                "provider_execution_metadata_hash"
            ],
            "economy_budget_receipt_hash": private_evidence[
                "economy_budget_receipt_hash"
            ],
            "materialized_artifact_hash": (
                private_evidence["materialized_artifact_hash"] if success else None
            ),
        },
        "counts": {
            "provider_submissions_total": accounting["provider_submissions_total"],
            "provider_responses_total": accounting["provider_responses_total"],
            "input_tokens": metrics["input_tokens"],
            "output_tokens": metrics["output_tokens"],
            "total_tokens": metrics["total_tokens"],
            "retry_total": accounting["retry_total"],
            "repair_total": accounting["repair_total"],
            "fallback_total": accounting["fallback_total"],
        },
        "provider_metrics": {
            "actual_cost_usd": metrics["actual_cost_usd"],
            "latency_ms": metrics["latency_ms"],
        },
    }
    return {**material, "receipt_hash": sha256_json(material)}


def _validate_budget_smoke_safe_receipt(
    *,
    safe_receipt: Any,
    private_evidence: dict[str, Any],
) -> None:
    if (
        not isinstance(safe_receipt, dict)
        or set(safe_receipt) != _BUDGET_SMOKE_SAFE_FIELDS
        or safe_receipt != _budget_smoke_safe_receipt(private_evidence=private_evidence)
    ):
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_safe_receipt_invalid")
    serialized = json.dumps(
        safe_receipt,
        ensure_ascii=False,
        sort_keys=True,
    )
    if any(
        forbidden in serialized
        for forbidden in (
            "exact_sealed_request",
            "exact_model_visible_request",
            "exact_prepared_request",
            "exact_final_provider_request",
            'provider_visible_schema":',
            'adapter_extracted_output":',
            "raw_provider_response",
            'raw_output":',
            "normalized_semantic_choice",
            'expected_answer":',
            'field_level_diff":',
            "provider_response_id",
            'economy_budget_receipt":',
            "source_value_ref",
            "literal_value",
        )
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_safe_receipt_private_data"
        )


def _budget_smoke_prepared_request_from_snapshot(
    snapshot: Any,
) -> Gate2PreparedProviderRequest:
    if not isinstance(snapshot, dict):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_prepared_request_invalid"
        )
    try:
        prepared_request = Gate2PreparedProviderRequest(**snapshot)
        prepared_request.validate_schema_binding()
    except (TypeError, Gate2SourceFactRuntimeError) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_budget_smoke_prepared_request_invalid"
        ) from exc
    return prepared_request


def _budget_smoke_execution_metadata_from_snapshot(
    snapshot: Any,
) -> Gate2ProviderExecutionMetadata:
    if not isinstance(snapshot, dict):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_execution_metadata_invalid"
        )
    try:
        return Gate2ProviderExecutionMetadata(**snapshot)
    except TypeError as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_budget_smoke_execution_metadata_invalid"
        ) from exc


def _budget_smoke_private_slot(
    private_evidence: dict[str, Any],
) -> Any:
    return SimpleNamespace(
        provider_profile_id=private_evidence["provider_profile_id"],
        provider_profile_revision=private_evidence["provider_profile_revision"],
        provider_id=private_evidence["provider_id"],
        provider_adapter_id=private_evidence["provider_adapter_id"],
        provider_adapter_version=private_evidence["provider_adapter_version"],
        exact_model_id=private_evidence["exact_model_id"],
        transport_policy=private_evidence["transport_policy"],
        transport_contract=copy.deepcopy(private_evidence["transport_contract"]),
        transport_contract_hash=private_evidence["transport_contract_hash"],
    )


def _budget_smoke_identifier(value: Any) -> str:
    if (
        not isinstance(value, str)
        or _BUDGET_SMOKE_IDENTIFIER_RE.fullmatch(value) is None
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_budget_smoke_failure_identity_invalid"
        )
    return value


def _budget_smoke_nonnegative_int(
    value: Any,
    *,
    default: int | None,
) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_metric_invalid")
    return value


def _budget_smoke_cost(value: Any) -> str:
    if not isinstance(value, str) or not value:
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_cost_invalid")
    try:
        normalized = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_budget_smoke_cost_invalid"
        ) from exc
    if not normalized.is_finite() or normalized < 0:
        _fail("financial_semantic_v6_context_v2_1_budget_smoke_cost_invalid")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _budget_smoke_model_visible_request_hash(value: Any) -> str:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_"
            "budget_smoke_model_visible_request_invalid"
        ) from exc
    return hashlib.sha256(serialized).hexdigest()


def _budget_smoke_ordered_json_roundtrip(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=False,
                separators=(",", ":"),
                allow_nan=False,
            ),
            object_pairs_hook=_unique_context_v2_1_evidence_object,
            parse_constant=_reject_context_v2_1_non_finite_number,
        )
    except (
        TypeError,
        ValueError,
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_budget_smoke_json_invalid"
        ) from exc


def _validate_context_v2_1_private_evidence(
    private_evidence: Any,
) -> None:
    expected_fields = {
        *_CONTEXT_V2_1_PRIVATE_FIELDS,
        "private_evidence_hash",
    }
    if (
        not isinstance(private_evidence, dict)
        or set(private_evidence) != expected_fields
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "private_evidence_shape_invalid"
        )
    try:
        json_safe = _json_roundtrip(private_evidence)
    except Gate2FinancialSemanticV6DecisionEvidenceError as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_"
            "private_evidence_json_types_invalid"
        ) from exc
    if json_safe != private_evidence:
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "private_evidence_json_types_invalid"
        )
    material = {
        field: copy.deepcopy(private_evidence[field])
        for field in _CONTEXT_V2_1_PRIVATE_FIELDS
    }
    hash_fields = (
        "private_evidence_hash",
        "final_provider_request_hash",
        "provider_visible_schema_hash",
        "adapter_canonical_schema_hash",
        "adapter_adapted_schema_hash",
        "response_profile_hash",
        "mapping_receipt_hash",
        "adapter_extracted_output_hash",
        "semantic_choice_hash",
        "materialized_artifact_hash",
        "materialized_artifact_integrity_hash",
        "total_materialization_integrity_hash",
    )
    for field in hash_fields:
        if _SHA256_RE.fullmatch(private_evidence[field]) is None:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "private_evidence_identity_invalid"
            )
    for field in (
        "provider_profile_id",
        "provider_adapter_id",
        "provider_adapter_version",
        "local_projection_model_id",
        "schema_projection_policy_version",
    ):
        _bounded_context_v2_1_identity(private_evidence[field])
    exact_request = private_evidence["exact_final_provider_request"]
    exact_schema = private_evidence["provider_visible_schema"]
    if (
        private_evidence["schema_version"]
        != V6_CONTEXT_V2_1_PRIVATE_EVIDENCE_SCHEMA_VERSION
        or private_evidence["private_evidence_hash"]
        != sha256_json(material)
        or private_evidence["request_profile"]
        != FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE
        or not isinstance(exact_request, dict)
        or exact_request.get("model")
        != private_evidence["local_projection_model_id"]
        or private_evidence["final_provider_request_hash"]
        != sha256_json(exact_request)
        or not isinstance(exact_schema, dict)
        or private_evidence["provider_visible_schema_hash"]
        != sha256_json(exact_schema)
        or private_evidence["adapter_extracted_output_hash"]
        != sha256_json(private_evidence["adapter_extracted_output"])
        or not isinstance(
            private_evidence["normalized_semantic_choice"],
            dict,
        )
        or private_evidence["semantic_choice_hash"]
        != sha256_json(private_evidence["normalized_semantic_choice"])
        or not isinstance(
            private_evidence["expanded_canonical_decision"],
            dict,
        )
        or not isinstance(private_evidence["validation_result"], dict)
        or not isinstance(private_evidence["replay_authorities"], dict)
        or private_evidence["execution_accounting"]
        != _ZERO_CALL_ACCOUNTING
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "private_evidence_identity_invalid"
        )
    authorities = private_evidence["replay_authorities"]
    if (
        authorities.get("request_profile")
        != private_evidence["request_profile"]
        or authorities.get("provider_profile_id")
        != private_evidence["provider_profile_id"]
        or authorities.get("provider_adapter_id")
        != private_evidence["provider_adapter_id"]
        or authorities.get("provider_adapter_version")
        != private_evidence["provider_adapter_version"]
        or authorities.get("local_projection_model_id")
        != private_evidence["local_projection_model_id"]
        or authorities.get("schema_projection_policy_version")
        != private_evidence["schema_projection_policy_version"]
        or authorities.get("final_provider_request_hash")
        != private_evidence["final_provider_request_hash"]
        or authorities.get("provider_visible_schema_hash")
        != private_evidence["provider_visible_schema_hash"]
        or authorities.get("adapter_adapted_schema_hash")
        != private_evidence["adapter_adapted_schema_hash"]
        or authorities.get("adapter_canonical_schema_hash")
        != private_evidence["adapter_canonical_schema_hash"]
        or authorities.get("mapping_receipt_hash")
        != private_evidence["mapping_receipt_hash"]
        or authorities.get("response_schema_hash")
        != private_evidence["response_profile_hash"]
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "private_evidence_authority_invalid"
        )


def _json_roundtrip(value: Any) -> Any:
    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
            object_pairs_hook=_unique_context_v2_1_evidence_object,
            parse_constant=_reject_context_v2_1_non_finite_number,
        )
    except (
        TypeError,
        ValueError,
        Gate2FinancialSemanticV6DecisionEvidenceError,
    ) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_context_v2_1_json_invalid"
        ) from exc


def _bounded_context_v2_1_identity(value: Any) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 512
        or value != value.strip()
        or not value.isprintable()
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_"
            "private_evidence_identity_invalid"
        )


def _unique_context_v2_1_evidence_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(
                "financial_semantic_v6_context_v2_1_"
                "private_evidence_duplicate_key"
            )
        result[key] = value
    return result


def _reject_context_v2_1_non_finite_number(value: str) -> Any:
    del value
    _fail(
        "financial_semantic_v6_context_v2_1_"
        "private_evidence_non_finite_number"
    )


def _execution_identity_from_private(
    snapshot: Any,
    *,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
) -> Gate2FinancialSemanticV6ExecutionIdentity:
    if not isinstance(snapshot, dict):
        _fail("financial_semantic_v6_private_execution_identity_invalid")
    try:
        identity = Gate2FinancialSemanticV6ExecutionIdentity(**snapshot)
        metadata = Gate2ProviderExecutionMetadata(
            provider_id=identity.provider_id,
            provider_profile_id=identity.provider_profile_id,
            provider_profile_revision=identity.provider_route_revision,
            adapter_id=identity.adapter_id,
            adapter_version=identity.adapter_version,
            requested_model_id=identity.requested_model_id,
            structured_output_mode=identity.structured_output_mode,
            response_format_type=identity.response_format_type,
            response_format_schema_mode=identity.response_format_schema_mode,
            transport_type=identity.transport_type,
            canonical_request_schema_hash=(identity.canonical_request_schema_hash),
            adapted_request_schema_hash=identity.adapted_request_schema_hash,
            schema_transform_count=identity.schema_transform_count,
            resolved_model_id=identity.resolved_model_id,
            provider_response_id=identity.provider_response_id,
            duration_ms=identity.duration_ms,
            input_tokens=identity.input_tokens,
            output_tokens=identity.output_tokens,
            total_tokens=identity.total_tokens,
            cached_input_tokens=identity.cached_input_tokens,
            reasoning_tokens=identity.reasoning_tokens,
            finish_reason=identity.finish_reason,
        )
        capture = Gate2FinancialSemanticV6CapturedExecution(
            request_profile=identity.request_profile,
            response_format_hash=identity.response_format_hash,
            execution_metadata=metadata,
            actual_cost_usd=identity.actual_cost_usd,
            exact_model_id=identity.requested_model_id,
            provider_profile_id=identity.provider_profile_id,
        )
        expected = Gate2FinancialSemanticV6ExecutionIdentityFactory().create(
            capture=capture,
            choice_contract=choice_contract,
        )
    except (
        TypeError,
        Gate2FinancialSemanticV6ExecutionIdentityError,
    ) as exc:
        raise Gate2FinancialSemanticV6DecisionEvidenceError(
            "financial_semantic_v6_private_execution_identity_invalid"
        ) from exc
    if identity != expected:
        _fail("financial_semantic_v6_private_execution_identity_invalid")
    return identity


def _safe_receipt(
    *,
    private_evidence: dict[str, Any],
    expansion: Gate2FinancialSemanticV6ExpandedDecision,
    total: Gate2FinancialSemanticV6TotalMaterialization,
    execution_identity: Gate2FinancialSemanticV6ExecutionIdentity,
    compilation: Gate2FinancialCandidateCompilation,
) -> dict[str, Any]:
    material = {
        "schema_version": V6_SAFE_DECISION_RECEIPT_SCHEMA_VERSION,
        "case_id": private_evidence["case_id"],
        "decision_classification": {
            "disposition": expansion.disposition,
        },
        "hashes": {
            "private_evidence_hash": private_evidence["private_evidence_hash"],
            "canonical_request_hash": private_evidence["canonical_request_hash"],
            "response_format_hash": private_evidence["response_format_hash"],
            "provider_schema_hash": private_evidence["provider_schema_hash"],
            "semantic_choice_hash": private_evidence["semantic_choice_hash"],
            "expansion_integrity_hash": expansion.integrity_hash,
            "canonical_decision_hash": expansion.canonical_decision_hash,
            "materialized_artifact_hash": total.canonical_artifact_hash,
            "materialized_artifact_integrity_hash": (
                total.canonical_artifact["integrity_hash"]
            ),
            "provider_execution_identity_hash": (execution_identity.integrity_hash),
        },
        "counts": {
            "provider_calls_total": 1,
            "typed_options_total": len(compilation.typed_options),
            "retained_source_values_total": len(expansion.retained_source_value_refs),
            "input_tokens": execution_identity.input_tokens,
            "output_tokens": execution_identity.output_tokens,
            "total_tokens": execution_identity.total_tokens,
        },
        "provider_metrics": {
            "actual_cost_usd": execution_identity.actual_cost_usd,
            "latency_ms": execution_identity.duration_ms,
        },
        "validator_status": "passed",
        "materializer_status": total.materializer_totality_status,
        "exact_choice_preserved": "YES",
        "offline_replay": "EXACT",
        "private_safe_hash_link": "VERIFIED",
        "private_safe_hash_link_verified": True,
        "raw_private_data_in_receipt": False,
        "raw_private_data_in_git": "ZERO",
    }
    return {**material, "receipt_hash": sha256_json(material)}


def _validate_private_evidence(
    *,
    private_evidence: Any,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
) -> None:
    if not isinstance(private_evidence, dict) or tuple(private_evidence) != (
        *_PRIVATE_FIELDS,
        "private_evidence_hash",
    ):
        _fail("financial_semantic_v6_private_evidence_shape_invalid")
    material = {key: copy.deepcopy(private_evidence[key]) for key in _PRIVATE_FIELDS}
    expected_response_format_hash = sha256_json(
        financial_semantic_v6_response_format(choice_contract)
    )
    if (
        private_evidence["schema_version"]
        != V6_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION
        or private_evidence["private_evidence_hash"]
        != financial_semantic_v6_private_evidence_hash(material)
        or private_evidence["canonical_request_hash"]
        != sha256_json(private_evidence["exact_canonical_request_object"])
        or private_evidence["response_format_hash"] != expected_response_format_hash
        or private_evidence["provider_schema_hash"]
        != choice_contract.choice_schema_hash
        or private_evidence["semantic_choice_hash"]
        != sha256_json(private_evidence["normalized_semantic_choice"])
        or private_evidence["exact_choice_preserved"] is not True
        or private_evidence["raw_provider_transport_preserved"] is not False
    ):
        _fail("financial_semantic_v6_private_evidence_identity_invalid")
    _case_id(private_evidence["case_id"])
    identity = _execution_identity_from_private(
        private_evidence["provider_execution_identity"],
        choice_contract=choice_contract,
    )
    if (
        identity.integrity_hash
        != private_evidence["provider_execution_identity"]["integrity_hash"]
        or identity.response_format_hash != private_evidence["response_format_hash"]
    ):
        _fail("financial_semantic_v6_private_execution_identity_invalid")


def _validate_safe_receipt(
    *,
    safe_receipt: Any,
    private_evidence: dict[str, Any],
) -> None:
    if not isinstance(safe_receipt, dict) or set(safe_receipt) != _SAFE_FIELDS:
        _fail("financial_semantic_v6_safe_receipt_invalid")
    material = {
        key: copy.deepcopy(value)
        for key, value in safe_receipt.items()
        if key != "receipt_hash"
    }
    hashes = safe_receipt.get("hashes")
    if (
        safe_receipt["schema_version"] != V6_SAFE_DECISION_RECEIPT_SCHEMA_VERSION
        or safe_receipt["receipt_hash"] != sha256_json(material)
        or not isinstance(hashes, dict)
        or hashes.get("private_evidence_hash")
        != private_evidence["private_evidence_hash"]
        or hashes.get("semantic_choice_hash")
        != private_evidence["semantic_choice_hash"]
        or hashes.get("materialized_artifact_hash")
        != private_evidence["materialized_artifact_hash"]
        or safe_receipt["exact_choice_preserved"] != "YES"
        or safe_receipt["offline_replay"] != "EXACT"
        or safe_receipt["private_safe_hash_link"] != "VERIFIED"
        or safe_receipt["private_safe_hash_link_verified"] is not True
        or safe_receipt["raw_private_data_in_receipt"] is not False
        or safe_receipt["raw_private_data_in_git"] != "ZERO"
    ):
        _fail("financial_semantic_v6_safe_receipt_invalid")
    serialized = json.dumps(safe_receipt, ensure_ascii=False, sort_keys=True)
    if any(
        forbidden in serialized
        for forbidden in (
            "exact_canonical_request_object",
            "normalized_semantic_choice",
            "expanded_canonical_decision",
            "provider_response_id",
            "source_value_ref",
            "literal_value",
            "role_bindings",
            "raw_provider_output",
            "raw_provider_transport",
        )
    ):
        _fail("financial_semantic_v6_safe_receipt_private_data")


def _case_id(value: Any) -> None:
    if not isinstance(value, str) or _CASE_ID_RE.fullmatch(value) is None:
        _fail("financial_semantic_v6_case_id_invalid")


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6DecisionEvidenceError(code)
