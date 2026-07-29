from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from .gate2_financial_evidence_decision import (
    FinancialEvidenceValueBinding,
    Gate2FinancialEvidenceDecisionError,
    TypedFinancialInputDecision,
    UnclassifiedFinancialInputDecision,
)
from .gate2_financial_evidence_materialization import (
    Gate2FinancialEvidenceSourcePackage,
    Gate2FinancialEvidenceValidatedDecisionFactory,
)
from .gate2_financial_evidence_materialization_contracts import (
    FinancialEvidenceValidatedDecision,
    sha256_json,
)
from .gate2_financial_evidence_registry import (
    Gate2FinancialEvidenceRegistrySnapshot,
)
from .gate2_financial_semantic_v6_bundle import (
    Gate2FinancialEvidenceBundle,
)
from .gate2_financial_semantic_v6_candidate_compiler import (
    Gate2FinancialCandidateCompilation,
)
from .gate2_financial_semantic_v6_canonical import (
    Gate2FinancialSemanticV6CanonicalDecisionContractFactory,
    Gate2FinancialSemanticV6CanonicalError,
)
from .gate2_financial_semantic_v6_choice import (
    Gate2FinancialSemanticV6ChoiceContract,
    Gate2FinancialSemanticV6ChoiceError,
    normalize_financial_semantic_v6_context_v2_1_choice,
    normalize_financial_semantic_v6_local_choice,
    validate_financial_semantic_v6_choice_contract,
)
from .gate2_financial_semantic_v6_packet import (
    Gate2FinancialSemanticV6Packet,
)


DECISION_EXPANSION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_decision_expansion_v6"
)
DECISION_EXPANSION_POLICY_VERSION = (
    "broker_reports_gate2_candidate_records_by_construction_v1"
)
_MAX_MODEL_CHOICE_BYTES = 8192

FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6DecisionExpansionFactory.create is the only "
    "minimal-choice-to-canonical-decision expansion entrypoint"
)
FORBIDDEN = (
    "The expander must not accept model-provided type IDs, refs, bindings "
    "or retention, repair unknown options, or convert a rejected typed "
    "choice into unclassified"
)


class Gate2FinancialSemanticV6ExpansionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ExpandedDecision:
    schema_version: str
    policy_version: str
    packet_hash: str
    choice_schema_hash: str
    candidate_compilation_integrity_hash: str
    evidence_bundle_integrity_hash: str
    model_choice_hash: str
    disposition: str
    selected_typed_option_id: str | None
    retained_source_value_refs: tuple[str, ...]
    retention_set_hash: str
    validated_decision: FinancialEvidenceValidatedDecision
    canonical_decision_hash: str
    post_response_repair_allowed: bool
    integrity_hash: str

    def to_private_dict(self) -> dict[str, Any]:
        return {
            **_expansion_payload_without_integrity(self),
            "integrity_hash": self.integrity_hash,
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "packet_hash": self.packet_hash,
            "choice_schema_hash": self.choice_schema_hash,
            "candidate_compilation_integrity_hash": (
                self.candidate_compilation_integrity_hash
            ),
            "evidence_bundle_integrity_hash": (self.evidence_bundle_integrity_hash),
            "model_choice_hash": self.model_choice_hash,
            "disposition": self.disposition,
            "typed_option_selected": (self.selected_typed_option_id is not None),
            "retained_source_values_total": len(self.retained_source_value_refs),
            "retention_set_hash": self.retention_set_hash,
            "canonical_decision_hash": self.canonical_decision_hash,
            "post_response_repair_allowed": (self.post_response_repair_allowed),
            "model_source_refs_total": 0,
            "model_role_bindings_total": 0,
            "provider_calls_total": 0,
            "contains_source_value_refs": False,
            "integrity_hash": self.integrity_hash,
        }


# OWNER:
# Sole minimal-choice-to-canonical-decision expansion authority.
#
# REUSE:
# Call Gate2FinancialSemanticV6DecisionExpansionFactory.create(...).
#
# MUST NOT:
# Do not trust model-provided refs, bindings, type IDs or retention.
class Gate2FinancialSemanticV6DecisionExpansionFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        model_output: str | dict[str, Any],
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6ExpandedDecision:
        return self._expand(
            model_output=model_output,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            context_v2_1_candidate=False,
        )

    def create_from_local_candidate(
        self,
        *,
        model_output: str | dict[str, Any],
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6ExpandedDecision:
        try:
            canonical_choice = normalize_financial_semantic_v6_local_choice(
                model_output=model_output,
                choice_contract=choice_contract,
                packet=packet,
            )
        except Gate2FinancialSemanticV6ChoiceError as exc:
            raise Gate2FinancialSemanticV6ExpansionError(
                "financial_semantic_v6_local_choice_normalization_failed"
            ) from exc
        return self._expand(
            model_output=canonical_choice,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            context_v2_1_candidate=False,
        )

    def create_from_context_v2_1_candidate(
        self,
        *,
        model_output: str | dict[str, Any],
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6ExpandedDecision:
        try:
            canonical_choice = (
                normalize_financial_semantic_v6_context_v2_1_choice(
                    model_output=model_output,
                    choice_contract=choice_contract,
                    packet=packet,
                )
            )
        except Gate2FinancialSemanticV6ChoiceError as exc:
            raise Gate2FinancialSemanticV6ExpansionError(
                "financial_semantic_v6_context_v2_1_choice_"
                "normalization_failed"
            ) from exc
        return self._expand(
            model_output=canonical_choice,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            context_v2_1_candidate=True,
        )

    def _expand(
        self,
        *,
        model_output: str | dict[str, Any],
        choice_contract: Gate2FinancialSemanticV6ChoiceContract,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
        context_v2_1_candidate: bool = False,
    ) -> Gate2FinancialSemanticV6ExpandedDecision:
        _validate_choice_contract(
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        choice = _parse_minimal_choice(
            model_output=model_output,
            contract=choice_contract,
            unclassified_reason_codes=(
                choice_contract.context_v2_1_response_profile
                .unclassified_reason_codes
                if context_v2_1_candidate
                else choice_contract.unclassified_reason_codes
            ),
        )
        allowed_type_ids = tuple(
            sorted({option.input_type_id for option in compilation.typed_options})
        )
        try:
            canonical_factory = (
                Gate2FinancialSemanticV6CanonicalDecisionContractFactory(
                    registry=self.registry
                )
            )
            canonical_contract = (
                canonical_factory.create_context_v2_1_candidate(
                    evidence_bundle=evidence_bundle,
                    source_package=source_package,
                    allowed_type_ids=allowed_type_ids,
                )
                if context_v2_1_candidate
                else canonical_factory.create(
                    evidence_bundle=evidence_bundle,
                    source_package=source_package,
                    allowed_type_ids=allowed_type_ids,
                )
            )
        except Gate2FinancialSemanticV6CanonicalError as exc:
            raise Gate2FinancialSemanticV6ExpansionError(
                "financial_semantic_v6_expansion_canonical_contract_invalid"
            ) from exc

        selected_option_id: str | None = None
        if choice["disposition"] == "typed_input":
            selected_option_id = choice["typed_option_id"]
            option = _exact_option(
                typed_option_id=selected_option_id,
                compilation=compilation,
            )
            canonical_choice = _typed_canonical_choice(option)
            retained_refs = tuple(
                binding.source_value_ref for binding in option.role_bindings
            )
        else:
            canonical_choice = _unclassified_canonical_choice(
                reason_code=choice["reason_code"],
                canonical_contract=canonical_contract,
            )
            retained_refs = tuple(evidence_bundle.retention_set)
        try:
            validated = Gate2FinancialEvidenceValidatedDecisionFactory(
                contract=canonical_contract
            ).create({"decision": canonical_choice})
        except Gate2FinancialEvidenceDecisionError as exc:
            raise Gate2FinancialSemanticV6ExpansionError(
                "financial_semantic_v6_expansion_canonical_validation_failed"
            ) from exc

        _validate_expanded_decision(
            validated=validated,
            selected_typed_option_id=selected_option_id,
            compilation=compilation,
            retained_refs=retained_refs,
            evidence_bundle=evidence_bundle,
        )
        material = {
            "schema_version": DECISION_EXPANSION_SCHEMA_VERSION,
            "policy_version": DECISION_EXPANSION_POLICY_VERSION,
            "packet_hash": packet.packet_hash,
            "choice_schema_hash": choice_contract.choice_schema_hash,
            "candidate_compilation_integrity_hash": (compilation.integrity_hash),
            "evidence_bundle_integrity_hash": evidence_bundle.integrity_hash,
            "model_choice_hash": sha256_json(choice),
            "disposition": choice["disposition"],
            "selected_typed_option_id": selected_option_id,
            "retained_source_value_refs": list(retained_refs),
            "retention_set_hash": sha256_json(list(retained_refs)),
            "validated_decision": asdict(validated),
            "canonical_decision_hash": sha256_json(asdict(validated)),
            "post_response_repair_allowed": False,
        }
        return Gate2FinancialSemanticV6ExpandedDecision(
            schema_version=DECISION_EXPANSION_SCHEMA_VERSION,
            policy_version=DECISION_EXPANSION_POLICY_VERSION,
            packet_hash=packet.packet_hash,
            choice_schema_hash=choice_contract.choice_schema_hash,
            candidate_compilation_integrity_hash=(compilation.integrity_hash),
            evidence_bundle_integrity_hash=evidence_bundle.integrity_hash,
            model_choice_hash=sha256_json(choice),
            disposition=choice["disposition"],
            selected_typed_option_id=selected_option_id,
            retained_source_value_refs=retained_refs,
            retention_set_hash=sha256_json(list(retained_refs)),
            validated_decision=validated,
            canonical_decision_hash=sha256_json(asdict(validated)),
            post_response_repair_allowed=False,
            integrity_hash=sha256_json(material),
        )


def validate_financial_semantic_v6_expanded_decision(
    *,
    expansion: Gate2FinancialSemanticV6ExpandedDecision,
    model_output: str | dict[str, Any],
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if not isinstance(
        expansion,
        Gate2FinancialSemanticV6ExpandedDecision,
    ):
        _fail("financial_semantic_v6_expansion_invalid")
    expected = Gate2FinancialSemanticV6DecisionExpansionFactory(
        registry=registry
    )._expand(
        model_output=model_output,
        choice_contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        context_v2_1_candidate=False,
    )
    if expansion != expected:
        _fail("financial_semantic_v6_expansion_integrity_invalid")


def validate_financial_semantic_v6_context_v2_1_expanded_decision(
    *,
    expansion: Gate2FinancialSemanticV6ExpandedDecision,
    model_output: str | dict[str, Any],
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if not isinstance(
        expansion,
        Gate2FinancialSemanticV6ExpandedDecision,
    ):
        _fail("financial_semantic_v6_context_v2_1_expansion_invalid")
    expected = Gate2FinancialSemanticV6DecisionExpansionFactory(
        registry=registry
    ).create_from_context_v2_1_candidate(
        model_output=model_output,
        choice_contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
    )
    if expansion != expected:
        _fail(
            "financial_semantic_v6_context_v2_1_expansion_integrity_invalid"
        )


def _parse_minimal_choice(
    *,
    model_output: str | dict[str, Any],
    contract: Gate2FinancialSemanticV6ChoiceContract,
    unclassified_reason_codes: tuple[str, ...] | None = None,
) -> dict[str, str]:
    if isinstance(model_output, str):
        if (
            not model_output
            or len(model_output.encode("utf-8")) > _MAX_MODEL_CHOICE_BYTES
        ):
            _fail("financial_semantic_v6_expansion_output_size_invalid")
        try:
            parsed = json.loads(
                model_output,
                object_pairs_hook=_unique_object,
            )
        except json.JSONDecodeError as exc:
            raise Gate2FinancialSemanticV6ExpansionError(
                "financial_semantic_v6_expansion_json_invalid"
            ) from exc
    else:
        parsed = model_output
    if not isinstance(parsed, dict):
        _fail("financial_semantic_v6_expansion_choice_invalid")
    disposition = parsed.get("disposition")
    if disposition == "typed_input":
        if set(parsed) != {"disposition", "typed_option_id"}:
            _fail("financial_semantic_v6_expansion_typed_shape_invalid")
        typed_option_id = parsed["typed_option_id"]
        if (
            not isinstance(typed_option_id, str)
            or typed_option_id not in contract.typed_option_ids
        ):
            _fail("financial_semantic_v6_expansion_option_unknown")
        return {
            "disposition": disposition,
            "typed_option_id": typed_option_id,
        }
    if disposition == "unclassified_financial_input":
        if set(parsed) != {"disposition", "reason_code"}:
            _fail("financial_semantic_v6_expansion_unclassified_shape_invalid")
        reason_code = parsed["reason_code"]
        if (
            not isinstance(reason_code, str)
            or reason_code
            not in (
                unclassified_reason_codes
                if unclassified_reason_codes is not None
                else contract.unclassified_reason_codes
            )
        ):
            _fail("financial_semantic_v6_expansion_reason_invalid")
        return {
            "disposition": disposition,
            "reason_code": reason_code,
        }
    _fail("financial_semantic_v6_expansion_disposition_invalid")


def _unique_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("financial_semantic_v6_expansion_duplicate_key")
        result[key] = value
    return result


def _exact_option(
    *,
    typed_option_id: str,
    compilation: Gate2FinancialCandidateCompilation,
):
    matches = tuple(
        option
        for option in compilation.typed_options
        if option.typed_option_id == typed_option_id
    )
    if len(matches) != 1:
        _fail("financial_semantic_v6_expansion_option_unknown")
    return matches[0]


def _typed_canonical_choice(option) -> dict[str, Any]:
    bindings: dict[str, str | None] = {
        role_id: None
        for role_id in (
            *option.required_roles,
            *option.optional_roles,
        )
    }
    for binding in option.role_bindings:
        bindings[binding.role_id] = binding.source_value_ref
    return {
        "disposition": "typed_input",
        "input_type_id": option.input_type_id,
        "value_bindings": bindings,
        "reason_code": "typed_supported",
    }


def _unclassified_canonical_choice(
    *,
    reason_code: str,
    canonical_contract,
) -> dict[str, Any]:
    return {
        "disposition": "unclassified_financial_input",
        "value_bindings": [
            {
                "role_id": candidate.allowed_roles[0],
                "source_value_ref": candidate.source_value_ref,
            }
            for candidate in canonical_contract.package.candidates
        ],
        "reason_code": reason_code,
    }


def _validate_expanded_decision(
    *,
    validated: FinancialEvidenceValidatedDecision,
    selected_typed_option_id: str | None,
    compilation: Gate2FinancialCandidateCompilation,
    retained_refs: tuple[str, ...],
    evidence_bundle: Gate2FinancialEvidenceBundle,
) -> None:
    decision = validated.decision
    if selected_typed_option_id is not None:
        option = _exact_option(
            typed_option_id=selected_typed_option_id,
            compilation=compilation,
        )
        if not isinstance(decision, TypedFinancialInputDecision):
            _fail("financial_semantic_v6_expansion_typed_result_invalid")
        expected_bindings = tuple(
            FinancialEvidenceValueBinding(
                role_id=item.role_id,
                source_value_ref=item.source_value_ref,
            )
            for item in option.role_bindings
        )
        if (
            decision.input_type_id != option.input_type_id
            or decision.value_bindings != expected_bindings
            or retained_refs
            != tuple(item.source_value_ref for item in option.role_bindings)
        ):
            _fail("financial_semantic_v6_expansion_typed_result_invalid")
        return
    if not isinstance(decision, UnclassifiedFinancialInputDecision):
        _fail("financial_semantic_v6_expansion_unclassified_result_invalid")
    observed_refs = tuple(item.source_value_ref for item in decision.value_bindings)
    if (
        observed_refs != evidence_bundle.retention_set
        or retained_refs != evidence_bundle.retention_set
        or len(observed_refs) != len(set(observed_refs))
    ):
        _fail("financial_semantic_v6_expansion_retention_loss")


def _validate_choice_contract(
    *,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    try:
        validate_financial_semantic_v6_choice_contract(
            contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=registry,
        )
    except Gate2FinancialSemanticV6ChoiceError as exc:
        raise Gate2FinancialSemanticV6ExpansionError(
            "financial_semantic_v6_expansion_choice_contract_invalid"
        ) from exc


def _expansion_payload_without_integrity(
    expansion: Gate2FinancialSemanticV6ExpandedDecision,
) -> dict[str, Any]:
    return {
        "schema_version": expansion.schema_version,
        "policy_version": expansion.policy_version,
        "packet_hash": expansion.packet_hash,
        "choice_schema_hash": expansion.choice_schema_hash,
        "candidate_compilation_integrity_hash": (
            expansion.candidate_compilation_integrity_hash
        ),
        "evidence_bundle_integrity_hash": (expansion.evidence_bundle_integrity_hash),
        "model_choice_hash": expansion.model_choice_hash,
        "disposition": expansion.disposition,
        "selected_typed_option_id": expansion.selected_typed_option_id,
        "retained_source_value_refs": list(expansion.retained_source_value_refs),
        "retention_set_hash": expansion.retention_set_hash,
        "validated_decision": asdict(expansion.validated_decision),
        "canonical_decision_hash": expansion.canonical_decision_hash,
        "post_response_repair_allowed": (expansion.post_response_repair_allowed),
    }


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6ExpansionError(code)
