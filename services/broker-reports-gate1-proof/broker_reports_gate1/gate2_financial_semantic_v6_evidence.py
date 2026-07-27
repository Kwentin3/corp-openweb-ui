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
    Gate2FinancialSemanticV6QualificationPrompt,
    financial_semantic_v6_prompt,
)
from .gate2_financial_semantic_v6_totality import (
    Gate2FinancialSemanticV6TotalMaterialization,
    Gate2FinancialSemanticV6TotalMaterializerFactory,
    Gate2FinancialSemanticV6TotalityError,
)
from .gate2_model_contracts import Gate2ProviderExecutionMetadata
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V6_QUALIFICATION_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
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
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6DecisionEvidenceFactory.create, "
    "restore_financial_semantic_v6_private_evidence and "
    "replay_financial_semantic_v6_decision are the only V6 exact-decision "
    "evidence entrypoints"
)
FORBIDDEN = (
    "Repository-safe receipts and Git must not contain canonical requests, "
    "semantic choices, expanded decisions, source refs, literals, provider "
    "response IDs, raw provider output or private transport bytes"
)
COMPATIBILITY_WRAPPER_DELEGATES_ONLY = True

_CASE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
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
