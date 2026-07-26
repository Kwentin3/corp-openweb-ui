from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_decision import (
    Gate2FinancialEvidenceDecisionContract,
    TypedFinancialInputDecision,
    UnclassifiedFinancialInputDecision,
)
from .gate2_financial_evidence_materialization import (
    FinancialEvidenceValidatedDecision,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_materialization_contracts import (
    sha256_json,
)
from .gate2_financial_semantic_v5_ambiguity import (
    Gate2FinancialSemanticV5AmbiguityResult,
)
from .gate2_financial_semantic_v5_execution import (
    Gate2FinancialSemanticV5ExecutionContract,
    Gate2FinancialSemanticV5ExecutionContractFactory,
)
from .gate2_financial_semantic_v5_packet import (
    Gate2FinancialSemanticV5DecisionPacket,
)
from .gate2_financial_semantic_v5_projection import (
    Gate2FinancialSemanticV5Projection,
    validate_financial_semantic_v5_projection,
)


V5_MODEL_CONTRACT_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_model_contract_v5"
)
V5_MODEL_CONTRACT_POLICY_VERSION = (
    "broker_reports_gate2_two_disposition_provider_projection_v1"
)
V5_PROVIDER_DISPOSITIONS = (
    "typed_input",
    "unclassified_financial_input",
)
FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV5ModelContractFactory.create is the only V5 "
    "two-disposition provider-contract entrypoint"
)
FORBIDDEN = (
    "The V5 provider contract must not expose technical terminal branches, "
    "create financial decision semantics, admit an ambiguity-blocked typed "
    "branch, repair a response or bypass canonical decision validation"
)


class Gate2FinancialSemanticV5ModelContractError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV5ModelContract:
    schema_version: str
    policy_version: str
    response_format: dict[str, Any]
    response_format_hash: str
    canonical_schema_hash: str
    prompt_ref: str
    prompt_hash: str
    semantic_projection_hash: str
    packet_hash: str
    ambiguity_policy_hash: str
    ambiguity_input_hash: str
    technical_evidence_hash: str
    provider_dispositions: tuple[str, ...]
    typed_type_ids: tuple[str, ...]

    def validate_and_adapt(
        self,
        *,
        model_output: str | dict[str, Any],
        execution: Gate2FinancialSemanticV5ExecutionContract,
        projection: Gate2FinancialSemanticV5Projection,
        ambiguity: Gate2FinancialSemanticV5AmbiguityResult,
        packet: Gate2FinancialSemanticV5DecisionPacket,
        canonical_contract: Gate2FinancialEvidenceDecisionContract,
    ) -> FinancialEvidenceValidatedDecision:
        _validate_exact_authorities(
            model_contract=self,
            execution=execution,
            projection=projection,
            ambiguity=ambiguity,
            packet=packet,
            canonical_contract=canonical_contract,
        )
        validated = Gate2FinancialEvidenceValidatedDecisionFactory(
            contract=canonical_contract
        ).create(model_output)
        decision = validated.decision
        if isinstance(decision, TypedFinancialInputDecision):
            if decision.input_type_id not in self.typed_type_ids:
                _fail("financial_semantic_v5_typed_branch_prohibited")
        elif not isinstance(
            decision,
            UnclassifiedFinancialInputDecision,
        ):
            _fail("financial_semantic_v5_technical_branch_prohibited")
        return validated

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "response_format_hash": self.response_format_hash,
            "canonical_schema_hash": self.canonical_schema_hash,
            "prompt_hash": self.prompt_hash,
            "semantic_projection_hash": self.semantic_projection_hash,
            "packet_hash": self.packet_hash,
            "ambiguity_policy_hash": self.ambiguity_policy_hash,
            "ambiguity_input_hash": self.ambiguity_input_hash,
            "provider_dispositions": list(self.provider_dispositions),
            "typed_type_ids": list(self.typed_type_ids),
            "canonical_gate2_dispositions_total": 4,
            "technical_terminal_model_branches_total": 0,
            "duplicate_decision_authorities_total": 0,
            "provider_calls_total": 0,
        }


class Gate2FinancialSemanticV5ModelContractFactory:
    def create(
        self,
        *,
        execution: Gate2FinancialSemanticV5ExecutionContract,
        projection: Gate2FinancialSemanticV5Projection,
        ambiguity: Gate2FinancialSemanticV5AmbiguityResult,
        packet: Gate2FinancialSemanticV5DecisionPacket,
        canonical_contract: Gate2FinancialEvidenceDecisionContract,
    ) -> Gate2FinancialSemanticV5ModelContract:
        _validate_source_authorities(
            execution=execution,
            projection=projection,
            ambiguity=ambiguity,
            packet=packet,
            canonical_contract=canonical_contract,
        )
        available_type_ids = _packet_type_ids(packet)
        response_format, typed_type_ids = _provider_projection(
            canonical_contract=canonical_contract,
            available_type_ids=available_type_ids,
        )
        if typed_type_ids != available_type_ids:
            _fail("financial_semantic_v5_type_branch_unrepresentable")
        result = Gate2FinancialSemanticV5ModelContract(
            schema_version=V5_MODEL_CONTRACT_SCHEMA_VERSION,
            policy_version=V5_MODEL_CONTRACT_POLICY_VERSION,
            response_format=response_format,
            response_format_hash=sha256_json(response_format),
            canonical_schema_hash=(
                canonical_contract.canonical_schema_hash()
            ),
            prompt_ref=execution.prompt.prompt_ref,
            prompt_hash=execution.prompt.hash,
            semantic_projection_hash=projection.projection_hash,
            packet_hash=packet.packet_hash,
            ambiguity_policy_hash=ambiguity.policy_hash,
            ambiguity_input_hash=ambiguity.guard_input_hash,
            technical_evidence_hash=packet.technical_evidence_hash,
            provider_dispositions=V5_PROVIDER_DISPOSITIONS,
            typed_type_ids=typed_type_ids,
        )
        _validate_exact_authorities(
            model_contract=result,
            execution=execution,
            projection=projection,
            ambiguity=ambiguity,
            packet=packet,
            canonical_contract=canonical_contract,
        )
        return result


def _provider_projection(
    *,
    canonical_contract: Gate2FinancialEvidenceDecisionContract,
    available_type_ids: tuple[str, ...],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    response_format = copy.deepcopy(
        canonical_contract.openai_response_format()
    )
    variants = _decision_variants(response_format)
    retained: list[dict[str, Any]] = []
    typed_type_ids: list[str] = []
    unclassified_total = 0
    for variant in variants:
        disposition = _variant_disposition(variant)
        if disposition == "typed_input":
            input_type_id = _variant_type_id(variant)
            if input_type_id in available_type_ids:
                retained.append(variant)
                typed_type_ids.append(input_type_id)
        elif disposition == "unclassified_financial_input":
            retained.append(variant)
            unclassified_total += 1
    variants[:] = retained
    if (
        unclassified_total != 1
        or not retained
        or len(typed_type_ids) != len(set(typed_type_ids))
    ):
        _fail("financial_semantic_v5_provider_projection_invalid")
    return response_format, tuple(typed_type_ids)


def _validate_source_authorities(
    *,
    execution: Any,
    projection: Any,
    ambiguity: Any,
    packet: Any,
    canonical_contract: Any,
) -> None:
    if (
        not isinstance(
            execution,
            Gate2FinancialSemanticV5ExecutionContract,
        )
        or not isinstance(
            projection,
            Gate2FinancialSemanticV5Projection,
        )
        or not isinstance(
            ambiguity,
            Gate2FinancialSemanticV5AmbiguityResult,
        )
        or not isinstance(
            packet,
            Gate2FinancialSemanticV5DecisionPacket,
        )
        or not isinstance(
            canonical_contract,
            Gate2FinancialEvidenceDecisionContract,
        )
    ):
        _fail("financial_semantic_v5_model_contract_input_invalid")
    if execution != (
        Gate2FinancialSemanticV5ExecutionContractFactory().create()
    ):
        _fail("financial_semantic_v5_prompt_identity_invalid")
    validate_financial_semantic_v5_projection(projection.payload)
    if (
        execution.prompt.hash == ""
        or packet.packet_hash != sha256_json(packet.payload)
        or packet.semantic_projection_hash != projection.projection_hash
        or packet.ambiguity_policy_hash != ambiguity.policy_hash
        or packet.ambiguity_input_hash != ambiguity.guard_input_hash
        or ambiguity.post_response_repair_allowed is not False
        or list(ambiguity.available_type_cards)
        != packet.payload.get("available_types")
    ):
        _fail("financial_semantic_v5_model_contract_identity_invalid")


def _validate_exact_authorities(
    *,
    model_contract: Gate2FinancialSemanticV5ModelContract,
    execution: Gate2FinancialSemanticV5ExecutionContract,
    projection: Gate2FinancialSemanticV5Projection,
    ambiguity: Gate2FinancialSemanticV5AmbiguityResult,
    packet: Gate2FinancialSemanticV5DecisionPacket,
    canonical_contract: Gate2FinancialEvidenceDecisionContract,
) -> None:
    _validate_source_authorities(
        execution=execution,
        projection=projection,
        ambiguity=ambiguity,
        packet=packet,
        canonical_contract=canonical_contract,
    )
    if (
        model_contract.schema_version
        != V5_MODEL_CONTRACT_SCHEMA_VERSION
        or model_contract.policy_version
        != V5_MODEL_CONTRACT_POLICY_VERSION
        or model_contract.provider_dispositions
        != V5_PROVIDER_DISPOSITIONS
        or model_contract.prompt_ref != execution.prompt.prompt_ref
        or model_contract.prompt_hash != execution.prompt.hash
        or model_contract.semantic_projection_hash
        != projection.projection_hash
        or model_contract.packet_hash != packet.packet_hash
        or model_contract.ambiguity_policy_hash != ambiguity.policy_hash
        or model_contract.ambiguity_input_hash
        != ambiguity.guard_input_hash
        or model_contract.technical_evidence_hash
        != packet.technical_evidence_hash
        or model_contract.canonical_schema_hash
        != canonical_contract.canonical_schema_hash()
        or model_contract.response_format_hash
        != sha256_json(model_contract.response_format)
        or model_contract.typed_type_ids != _packet_type_ids(packet)
    ):
        _fail("financial_semantic_v5_exact_identity_mismatch")
    expected_response, expected_type_ids = _provider_projection(
        canonical_contract=canonical_contract,
        available_type_ids=_packet_type_ids(packet),
    )
    if (
        model_contract.response_format != expected_response
        or model_contract.typed_type_ids != expected_type_ids
    ):
        _fail("financial_semantic_v5_provider_projection_mismatch")


def _packet_type_ids(
    packet: Gate2FinancialSemanticV5DecisionPacket,
) -> tuple[str, ...]:
    cards = packet.payload.get("available_types")
    if not isinstance(cards, list):
        _fail("financial_semantic_v5_available_types_invalid")
    result: list[str] = []
    for card in cards:
        if (
            not isinstance(card, dict)
            or not isinstance(card.get("input_type_id"), str)
            or not card["input_type_id"]
        ):
            _fail("financial_semantic_v5_available_types_invalid")
        result.append(card["input_type_id"])
    if len(result) != len(set(result)):
        _fail("financial_semantic_v5_available_types_invalid")
    return tuple(result)


def _decision_variants(
    response_format: dict[str, Any],
) -> list[dict[str, Any]]:
    try:
        variants = response_format["json_schema"]["schema"][
            "properties"
        ]["decision"]["anyOf"]
    except (KeyError, TypeError) as exc:
        raise Gate2FinancialSemanticV5ModelContractError(
            "financial_semantic_v5_response_schema_invalid"
        ) from exc
    if (
        not isinstance(variants, list)
        or not variants
        or not all(isinstance(item, dict) for item in variants)
    ):
        _fail("financial_semantic_v5_response_schema_invalid")
    return variants


def _variant_disposition(variant: dict[str, Any]) -> str:
    values = (
        (variant.get("properties") or {})
        .get("disposition", {})
        .get("enum")
    )
    if (
        not isinstance(values, list)
        or len(values) != 1
        or not isinstance(values[0], str)
    ):
        _fail("financial_semantic_v5_response_disposition_invalid")
    return values[0]


def _variant_type_id(variant: dict[str, Any]) -> str:
    values = (
        (variant.get("properties") or {})
        .get("input_type_id", {})
        .get("enum")
    )
    if (
        not isinstance(values, list)
        or len(values) != 1
        or not isinstance(values[0], str)
        or not values[0]
    ):
        _fail("financial_semantic_v5_response_type_id_invalid")
    return values[0]


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV5ModelContractError(code)
