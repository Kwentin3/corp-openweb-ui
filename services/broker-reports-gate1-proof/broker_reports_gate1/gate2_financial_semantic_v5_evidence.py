from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .gate2_financial_evidence_decision import (
    Gate2FinancialEvidenceDecisionContract,
)
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceExecutionMetadata,
    FinancialEvidenceValidatedDecision,
    Gate2FinancialEvidenceMaterializerFactory,
)
from .gate2_financial_evidence_materialization_contracts import (
    Gate2FinancialEvidenceSourcePackage,
    sha256_json,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v5_ambiguity import (
    Gate2FinancialSemanticV5AmbiguityResult,
)
from .gate2_financial_semantic_v5_contract import (
    Gate2FinancialSemanticV5ModelContract,
)
from .gate2_financial_semantic_v5_execution import (
    Gate2FinancialSemanticV5ExecutionContract,
)
from .gate2_financial_semantic_v5_packet import (
    Gate2FinancialSemanticV5DecisionPacket,
)
from .gate2_financial_semantic_v5_projection import (
    Gate2FinancialSemanticV5Projection,
)
from .gate2_model_requests import (
    FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE,
    Gate2OpenWebUIRequestBuilder,
)


V5_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v5_private_evidence_v1"
)
V5_SAFE_DECISION_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v5_safe_receipt_v1"
)
V5_DECISION_REPLAY_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_v5_replay_v1"
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV5DecisionEvidenceFactory.create and "
    "replay_financial_semantic_v5_decision are the only V5 exact decision "
    "evidence entrypoints"
)
FORBIDDEN = (
    "Repository-safe receipts must not contain canonical requests, model "
    "decisions, source refs, literals, raw provider output or private "
    "transport bytes"
)

_CASE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")
_COST_RE = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,12})?$")
_PRIVATE_FIELDS = (
    "schema_version",
    "case_id",
    "exact_canonical_request_object",
    "canonical_request_hash",
    "response_schema_hash",
    "normalized_canonical_model_decision",
    "decision_hash",
    "validator_result",
    "materialized_artifact_hash",
    "materialized_artifact_integrity_hash",
    "replay_authorities",
    "provider_receipt",
    "raw_provider_transport_preserved",
)


class Gate2FinancialSemanticV5DecisionEvidenceError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV5ProviderCallReceipt:
    input_tokens: int
    output_tokens: int
    cost_usd: str
    latency_ms: int


@dataclass(frozen=True)
class Gate2FinancialSemanticV5DecisionEvidenceBundle:
    private_evidence: dict[str, Any]
    safe_receipt: dict[str, Any]
    materialized_artifact: dict[str, Any]


@dataclass(frozen=True)
class Gate2FinancialSemanticV5ReplayResult:
    schema_version: str
    status: str
    decision_hash: str
    materialized_artifact_hash: str
    materialized_artifact: dict[str, Any]
    safe_receipt: dict[str, Any]


class Gate2FinancialSemanticV5DecisionEvidenceFactory:
    def create(
        self,
        *,
        case_id: str,
        model_id: str,
        canonical_request: dict[str, Any],
        model_output: str | dict[str, Any],
        provider_receipt: Gate2FinancialSemanticV5ProviderCallReceipt,
        model_contract: Gate2FinancialSemanticV5ModelContract,
        execution: Gate2FinancialSemanticV5ExecutionContract,
        projection: Gate2FinancialSemanticV5Projection,
        ambiguity: Gate2FinancialSemanticV5AmbiguityResult,
        packet: Gate2FinancialSemanticV5DecisionPacket,
        canonical_contract: Gate2FinancialEvidenceDecisionContract,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        source_package: Gate2FinancialEvidenceSourcePackage,
        execution_metadata: FinancialEvidenceExecutionMetadata,
    ) -> Gate2FinancialSemanticV5DecisionEvidenceBundle:
        _case_id(case_id)
        _model_id(model_id)
        exact_request = _validate_exact_request(
            canonical_request=canonical_request,
            model_id=model_id,
            model_contract=model_contract,
            execution=execution,
            packet=packet,
        )
        normalized_decision = _normalize_model_decision(model_output)
        validated = model_contract.validate_and_adapt(
            model_output=normalized_decision,
            execution=execution,
            projection=projection,
            ambiguity=ambiguity,
            packet=packet,
            canonical_contract=canonical_contract,
        )
        artifact = _materialize(
            validated=validated,
            registry=registry,
            source_package=source_package,
            execution_metadata=execution_metadata,
        )
        private_material = {
            "schema_version": (
                V5_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION
            ),
            "case_id": case_id,
            "exact_canonical_request_object": exact_request,
            "canonical_request_hash": sha256_json(exact_request),
            "response_schema_hash": (
                model_contract.response_format_hash
            ),
            "normalized_canonical_model_decision": (
                normalized_decision
            ),
            "decision_hash": sha256_json(normalized_decision),
            "validator_result": _validator_result(
                validated=validated,
                model_contract=model_contract,
            ),
            "materialized_artifact_hash": sha256_json(artifact),
            "materialized_artifact_integrity_hash": artifact[
                "integrity_hash"
            ],
            "replay_authorities": _replay_authorities(
                validated=validated,
                model_id=model_id,
                registry=registry,
                source_package=source_package,
                execution_metadata=execution_metadata,
            ),
            "provider_receipt": _provider_receipt(provider_receipt),
            "raw_provider_transport_preserved": False,
        }
        private_evidence = {
            **copy.deepcopy(private_material),
            "private_evidence_hash": sha256_json(private_material),
        }
        safe_receipt = _safe_receipt(
            private_evidence=private_evidence,
            validated=validated,
            candidates_total=len(
                canonical_contract.package.candidates
            ),
        )
        _validate_private_evidence(
            private_evidence=private_evidence,
            model_contract=model_contract,
        )
        _validate_safe_receipt(
            safe_receipt=safe_receipt,
            private_evidence=private_evidence,
        )
        return Gate2FinancialSemanticV5DecisionEvidenceBundle(
            private_evidence=copy.deepcopy(private_evidence),
            safe_receipt=copy.deepcopy(safe_receipt),
            materialized_artifact=copy.deepcopy(artifact),
        )


def replay_financial_semantic_v5_decision(
    *,
    private_evidence: dict[str, Any],
    model_id: str,
    model_contract: Gate2FinancialSemanticV5ModelContract,
    execution: Gate2FinancialSemanticV5ExecutionContract,
    projection: Gate2FinancialSemanticV5Projection,
    ambiguity: Gate2FinancialSemanticV5AmbiguityResult,
    packet: Gate2FinancialSemanticV5DecisionPacket,
    canonical_contract: Gate2FinancialEvidenceDecisionContract,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    source_package: Gate2FinancialEvidenceSourcePackage,
    execution_metadata: FinancialEvidenceExecutionMetadata,
) -> Gate2FinancialSemanticV5ReplayResult:
    _validate_private_evidence(
        private_evidence=private_evidence,
        model_contract=model_contract,
    )
    request = private_evidence["exact_canonical_request_object"]
    _validate_exact_request(
        canonical_request=request,
        model_id=model_id,
        model_contract=model_contract,
        execution=execution,
        packet=packet,
    )
    try:
        validated = model_contract.validate_and_adapt(
            model_output=private_evidence[
                "normalized_canonical_model_decision"
            ],
            execution=execution,
            projection=projection,
            ambiguity=ambiguity,
            packet=packet,
            canonical_contract=canonical_contract,
        )
    except ValueError as exc:
        raise Gate2FinancialSemanticV5DecisionEvidenceError(
            "financial_semantic_v5_offline_replay_validation_failed"
        ) from exc
    artifact = _materialize(
        validated=validated,
        registry=registry,
        source_package=source_package,
        execution_metadata=execution_metadata,
    )
    expected_validator = _validator_result(
        validated=validated,
        model_contract=model_contract,
    )
    expected_authorities = _replay_authorities(
        validated=validated,
        model_id=model_id,
        registry=registry,
        source_package=source_package,
        execution_metadata=execution_metadata,
    )
    if (
        private_evidence["decision_hash"]
        != sha256_json(
            private_evidence["normalized_canonical_model_decision"]
        )
        or private_evidence["validator_result"]
        != expected_validator
        or private_evidence["replay_authorities"]
        != expected_authorities
        or private_evidence["materialized_artifact_hash"]
        != sha256_json(artifact)
        or private_evidence[
            "materialized_artifact_integrity_hash"
        ]
        != artifact["integrity_hash"]
    ):
        _fail("financial_semantic_v5_offline_replay_mismatch")
    safe_receipt = _safe_receipt(
        private_evidence=private_evidence,
        validated=validated,
        candidates_total=len(canonical_contract.package.candidates),
    )
    _validate_safe_receipt(
        safe_receipt=safe_receipt,
        private_evidence=private_evidence,
    )
    return Gate2FinancialSemanticV5ReplayResult(
        schema_version=V5_DECISION_REPLAY_SCHEMA_VERSION,
        status="exact",
        decision_hash=private_evidence["decision_hash"],
        materialized_artifact_hash=sha256_json(artifact),
        materialized_artifact=copy.deepcopy(artifact),
        safe_receipt=copy.deepcopy(safe_receipt),
    )


def financial_semantic_v5_private_evidence_hash(
    private_evidence_without_hash: dict[str, Any],
) -> str:
    if (
        not isinstance(private_evidence_without_hash, dict)
        or set(private_evidence_without_hash) != set(_PRIVATE_FIELDS)
    ):
        _fail("financial_semantic_v5_private_evidence_shape_invalid")
    return sha256_json(private_evidence_without_hash)


def _validate_exact_request(
    *,
    canonical_request: Any,
    model_id: Any,
    model_contract: Gate2FinancialSemanticV5ModelContract,
    execution: Gate2FinancialSemanticV5ExecutionContract,
    packet: Gate2FinancialSemanticV5DecisionPacket,
) -> dict[str, Any]:
    _model_id(model_id)
    if not isinstance(canonical_request, dict):
        _fail("financial_semantic_v5_canonical_request_invalid")
    expected = Gate2OpenWebUIRequestBuilder(
        request_profile=FINANCIAL_SEMANTIC_V5_REQUEST_PROFILE
    ).build(
        prompt=execution.prompt,
        package=packet.payload,
        model_id=model_id,
        response_format=model_contract.response_format,
    )
    if canonical_request != expected:
        _fail("financial_semantic_v5_canonical_request_identity_mismatch")
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
        raise Gate2FinancialSemanticV5DecisionEvidenceError(
            "financial_semantic_v5_canonical_request_invalid"
        ) from exc


def _normalize_model_decision(
    model_output: str | dict[str, Any],
) -> dict[str, Any]:
    if isinstance(model_output, str):
        try:
            parsed = json.loads(model_output)
        except json.JSONDecodeError as exc:
            raise Gate2FinancialSemanticV5DecisionEvidenceError(
                "financial_semantic_v5_model_decision_json_invalid"
            ) from exc
    else:
        parsed = model_output
    if not isinstance(parsed, dict):
        _fail("financial_semantic_v5_model_decision_invalid")
    try:
        return json.loads(
            json.dumps(
                parsed,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError) as exc:
        raise Gate2FinancialSemanticV5DecisionEvidenceError(
            "financial_semantic_v5_model_decision_invalid"
        ) from exc


def _materialize(
    *,
    validated: FinancialEvidenceValidatedDecision,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    source_package: Gate2FinancialEvidenceSourcePackage,
    execution_metadata: FinancialEvidenceExecutionMetadata,
) -> dict[str, Any]:
    return Gate2FinancialEvidenceMaterializerFactory(
        registry=registry,
        source_package=source_package,
        execution_metadata=execution_metadata,
    ).create().materialize(validated_decision=validated)


def _validator_result(
    *,
    validated: FinancialEvidenceValidatedDecision,
    model_contract: Gate2FinancialSemanticV5ModelContract,
) -> dict[str, Any]:
    return {
        "status": "passed",
        "validated_decision_schema_version": validated.schema_version,
        "canonical_decision_schema_version": (
            validated.decision_schema_version
        ),
        "canonical_decision_schema_hash": (
            validated.decision_schema_hash
        ),
        "validated_decision_hash": sha256_json(asdict(validated)),
        "response_schema_hash": model_contract.response_format_hash,
        "prompt_hash": model_contract.prompt_hash,
        "semantic_projection_hash": (
            model_contract.semantic_projection_hash
        ),
        "packet_hash": model_contract.packet_hash,
        "ambiguity_policy_hash": (
            model_contract.ambiguity_policy_hash
        ),
        "ambiguity_input_hash": model_contract.ambiguity_input_hash,
    }


def _replay_authorities(
    *,
    validated: FinancialEvidenceValidatedDecision,
    model_id: str,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
    source_package: Gate2FinancialEvidenceSourcePackage,
    execution_metadata: FinancialEvidenceExecutionMetadata,
) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "registry_hash": registry.registry_hash,
        "source_package_integrity_hash": source_package.integrity_hash,
        "candidate_authority_hash": (
            validated.candidate_authority_hash
        ),
        "execution_metadata": asdict(execution_metadata),
    }


def _provider_receipt(
    value: Gate2FinancialSemanticV5ProviderCallReceipt,
) -> dict[str, Any]:
    if (
        not isinstance(
            value,
            Gate2FinancialSemanticV5ProviderCallReceipt,
        )
        or not isinstance(value.input_tokens, int)
        or isinstance(value.input_tokens, bool)
        or value.input_tokens < 0
        or not isinstance(value.output_tokens, int)
        or isinstance(value.output_tokens, bool)
        or value.output_tokens < 0
        or not isinstance(value.latency_ms, int)
        or isinstance(value.latency_ms, bool)
        or value.latency_ms < 0
        or not isinstance(value.cost_usd, str)
        or _COST_RE.fullmatch(value.cost_usd) is None
    ):
        _fail("financial_semantic_v5_provider_receipt_invalid")
    try:
        cost = Decimal(value.cost_usd)
    except InvalidOperation as exc:
        raise Gate2FinancialSemanticV5DecisionEvidenceError(
            "financial_semantic_v5_provider_receipt_invalid"
        ) from exc
    if not cost.is_finite() or cost < 0:
        _fail("financial_semantic_v5_provider_receipt_invalid")
    return asdict(value)


def _safe_receipt(
    *,
    private_evidence: dict[str, Any],
    validated: FinancialEvidenceValidatedDecision,
    candidates_total: int,
) -> dict[str, Any]:
    decision = validated.decision
    provider = private_evidence["provider_receipt"]
    material = {
        "schema_version": V5_SAFE_DECISION_RECEIPT_SCHEMA_VERSION,
        "case_id": private_evidence["case_id"],
        "decision_classification": {
            "disposition": decision.disposition,
            "input_type_id": getattr(
                decision,
                "input_type_id",
                None,
            ),
            "reason_code": decision.reason_code,
        },
        "hashes": {
            "private_evidence_hash": private_evidence[
                "private_evidence_hash"
            ],
            "canonical_request_hash": private_evidence[
                "canonical_request_hash"
            ],
            "response_schema_hash": private_evidence[
                "response_schema_hash"
            ],
            "decision_hash": private_evidence["decision_hash"],
            "validated_decision_hash": private_evidence[
                "validator_result"
            ]["validated_decision_hash"],
            "materialized_artifact_hash": private_evidence[
                "materialized_artifact_hash"
            ],
            "materialized_artifact_integrity_hash": private_evidence[
                "materialized_artifact_integrity_hash"
            ],
        },
        "counts": {
            "provider_calls_total": 1,
            "candidate_values_total": candidates_total,
            "bound_values_total": len(decision.value_bindings),
            "input_tokens": provider["input_tokens"],
            "output_tokens": provider["output_tokens"],
        },
        "provider_metrics": {
            "cost_usd": provider["cost_usd"],
            "latency_ms": provider["latency_ms"],
        },
        "validator_status": "passed",
        "exact_canonical_decision_preserved": True,
        "offline_replay": "exact",
        "private_safe_hash_link_verified": True,
        "raw_private_data_in_receipt": False,
    }
    return {
        **material,
        "receipt_hash": sha256_json(material),
    }


def _validate_private_evidence(
    *,
    private_evidence: Any,
    model_contract: Gate2FinancialSemanticV5ModelContract,
) -> None:
    if (
        not isinstance(private_evidence, dict)
        or set(private_evidence)
        != {*_PRIVATE_FIELDS, "private_evidence_hash"}
    ):
        _fail("financial_semantic_v5_private_evidence_shape_invalid")
    material = {
        key: copy.deepcopy(private_evidence[key])
        for key in _PRIVATE_FIELDS
    }
    if (
        private_evidence["schema_version"]
        != V5_PRIVATE_DECISION_EVIDENCE_SCHEMA_VERSION
        or private_evidence["private_evidence_hash"]
        != financial_semantic_v5_private_evidence_hash(material)
        or private_evidence["canonical_request_hash"]
        != sha256_json(
            private_evidence["exact_canonical_request_object"]
        )
        or private_evidence["response_schema_hash"]
        != model_contract.response_format_hash
        or private_evidence["decision_hash"]
        != sha256_json(
            private_evidence[
                "normalized_canonical_model_decision"
            ]
        )
        or private_evidence["raw_provider_transport_preserved"]
        is not False
    ):
        _fail("financial_semantic_v5_private_evidence_identity_invalid")
    _case_id(private_evidence["case_id"])
    raw_receipt = private_evidence["provider_receipt"]
    if (
        not isinstance(raw_receipt, dict)
        or set(raw_receipt)
        != {
            "input_tokens",
            "output_tokens",
            "cost_usd",
            "latency_ms",
        }
    ):
        _fail("financial_semantic_v5_provider_receipt_invalid")
    try:
        receipt = Gate2FinancialSemanticV5ProviderCallReceipt(
            **raw_receipt
        )
    except TypeError as exc:
        raise Gate2FinancialSemanticV5DecisionEvidenceError(
            "financial_semantic_v5_provider_receipt_invalid"
        ) from exc
    _provider_receipt(receipt)


def _validate_safe_receipt(
    *,
    safe_receipt: Any,
    private_evidence: dict[str, Any],
) -> None:
    if not isinstance(safe_receipt, dict):
        _fail("financial_semantic_v5_safe_receipt_invalid")
    material = {
        key: copy.deepcopy(value)
        for key, value in safe_receipt.items()
        if key != "receipt_hash"
    }
    if (
        set(safe_receipt)
        != {
            "schema_version",
            "case_id",
            "decision_classification",
            "hashes",
            "counts",
            "provider_metrics",
            "validator_status",
            "exact_canonical_decision_preserved",
            "offline_replay",
            "private_safe_hash_link_verified",
            "raw_private_data_in_receipt",
            "receipt_hash",
        }
        or safe_receipt.get("schema_version")
        != V5_SAFE_DECISION_RECEIPT_SCHEMA_VERSION
        or safe_receipt.get("receipt_hash") != sha256_json(material)
        or (safe_receipt.get("hashes") or {}).get(
            "private_evidence_hash"
        )
        != private_evidence["private_evidence_hash"]
        or safe_receipt.get("raw_private_data_in_receipt") is not False
    ):
        _fail("financial_semantic_v5_safe_receipt_invalid")
    serialized = json.dumps(
        safe_receipt,
        ensure_ascii=False,
        sort_keys=True,
    )
    if any(
        field in serialized
        for field in (
            "exact_canonical_request_object",
            "normalized_canonical_model_decision",
            "source_value_ref",
            "literal_value",
            "value_bindings",
            "raw_provider_output",
            "raw_provider_transport",
        )
    ):
        _fail("financial_semantic_v5_safe_receipt_private_data")


def _case_id(value: Any) -> None:
    if (
        not isinstance(value, str)
        or _CASE_ID_RE.fullmatch(value) is None
    ):
        _fail("financial_semantic_v5_case_id_invalid")


def _model_id(value: Any) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 160
        or any(character.isspace() for character in value)
    ):
        _fail("financial_semantic_v5_model_id_invalid")


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV5DecisionEvidenceError(code)
