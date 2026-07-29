from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass
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
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_CONTEXT_V2_1_LOCAL_PROOF_REQUEST_PROFILE,
    FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)
from .gate2_provider_adapters import Gate2PreparedProviderRequest


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
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6DecisionEvidenceFactory.create, "
    "its additive create_context_v2_1_candidate method, "
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
