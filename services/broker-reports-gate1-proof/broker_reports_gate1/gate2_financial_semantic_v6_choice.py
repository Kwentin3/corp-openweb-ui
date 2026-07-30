from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_decision import (
    DISPOSITIONS,
    UNCLASSIFIED_REASON_CODES,
)
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
from .gate2_financial_semantic_v6_packet import (
    CONTEXT_V2_1_CANDIDATE_SCHEMA_VERSION,
    CONTEXT_V2_1_MAPPING_RECEIPT_SCHEMA_VERSION,
    CONTEXT_V2_1_POLICY_VERSION,
    TYPE_FIRST_CONTEXT_PROFILE,
    TYPE_FIRST_DECISION_POLICY_VERSION,
    TYPE_FIRST_MAPPING_RECEIPT_SCHEMA_VERSION,
    Gate2FinancialSemanticV6ContextV21Candidate,
    Gate2FinancialSemanticV6ContextV21MappingReceipt,
    Gate2FinancialSemanticV6Packet,
    Gate2FinancialSemanticV6PacketError,
    Gate2FinancialSemanticV6TypeFirstCandidate,
    Gate2FinancialSemanticV6TypeFirstMappingReceipt,
    validate_financial_semantic_v6_packet,
    validate_financial_semantic_v6_type_first_material,
)


SEMANTIC_CHOICE_SCHEMA_VERSION = "broker_reports_gate2_financial_semantic_choice_v6"
SEMANTIC_CHOICE_POLICY_VERSION = (
    "broker_reports_gate2_candidate_records_by_construction_v1"
)
LOCAL_CHOICE_CANDIDATE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_local_choice_candidate_v1"
)
LOCAL_CHOICE_CANDIDATE_POLICY_VERSION = (
    "broker_reports_gate2_llm_semantic_context_local_choice_v1"
)
CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_context_v2_1_choice_response_profile_v1"
)
CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_POLICY_VERSION = (
    "broker_reports_gate2_llm_semantic_context_v2_1_local_choice_v1"
)
CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES = (
    "no_registry_type",
    "single_registry_type_no_safe_record",
    "ambiguous_registry_type",
)
SINGLE_REGISTRY_TYPE_NO_SAFE_RECORD_REASON_CODE = (
    CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES[1]
)
SEMANTIC_CHOICE_PROVIDER_DISPOSITIONS = (
    "typed_input",
    "unclassified_financial_input",
)
SEMANTIC_CHOICE_OUTPUT_FIELDS = frozenset(
    {
        "disposition",
        "typed_option_id",
        "reason_code",
    }
)
LOCAL_CHOICE_OUTPUT_FIELDS = frozenset({"choice", "reason"})
_MAX_LOCAL_CHOICE_BYTES = 1024
_MAX_CONTEXT_V2_1_CHOICE_BYTES = 1024
_MAX_TYPE_FIRST_RESPONSE_BYTES = 1024
TYPE_FIRST_RESPONSE_PROFILE_SCHEMA_VERSION = (
    "broker_reports_gate2_type_first_plausible_types_response_v1"
)
_CANONICAL_GATE2_DISPOSITIONS = (
    "typed_input",
    "unclassified_financial_input",
    "no_financial_input",
    "unsupported",
)

FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6ChoiceContractFactory.create and its additive "
    "create_type_first_response_profile method are the only V6 "
    "active minimal semantic-choice, historical non-active local-choice, and "
    "non-active Context V2.1 or Type-First response-profile contract "
    "entrypoints"
)
FORBIDDEN = (
    "The provider choice must not return a type ID, source ref, role binding, "
    "literal, provenance, dimension or record field; technical preclose "
    "dispositions must not be exposed to the model; the local candidate must "
    "not expose canonical option IDs or become an active request schema; "
    "Context V2.1 choices and Type-First types must restore only through "
    "their private mapping receipts"
)


class Gate2FinancialSemanticV6ChoiceError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialSemanticV6LocalChoiceCandidate:
    schema_version: str
    policy_version: str
    active: bool
    packet_hash: str
    slim_view_hash: str
    slim_alias_receipt_integrity_hash: str
    canonical_choice_schema_hash: str
    choice_aliases: tuple[str, ...]
    unclassified_reason_codes: tuple[str, ...]
    response_schema: dict[str, Any]
    response_schema_hash: str
    provider_calls_total: int
    post_response_repair_allowed: bool
    integrity_hash: str

    def canonical_schema(self) -> dict[str, Any]:
        return copy.deepcopy(self.response_schema)

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "active": self.active,
            "slim_view_hash": self.slim_view_hash,
            "slim_alias_receipt_integrity_hash": (
                self.slim_alias_receipt_integrity_hash
            ),
            "canonical_choice_schema_hash": (
                self.canonical_choice_schema_hash
            ),
            "response_schema_hash": self.response_schema_hash,
            "choice_aliases": list(self.choice_aliases),
            "unclassified_reason_codes": list(
                self.unclassified_reason_codes
            ),
            "model_output_fields": sorted(LOCAL_CHOICE_OUTPUT_FIELDS),
            "canonical_option_ids_visible_total": 0,
            "provider_calls_total": self.provider_calls_total,
            "post_response_repair_allowed": (
                self.post_response_repair_allowed
            ),
            "integrity_hash": self.integrity_hash,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ContextV21ChoiceResponseProfile:
    schema_version: str
    policy_version: str
    active: bool
    transport_eligible: bool
    packet_hash: str
    context_view_hash: str
    mapping_receipt_integrity_hash: str
    canonical_choice_schema_hash: str
    choice_keys: tuple[str, ...]
    unclassified_reason_codes: tuple[str, ...]
    response_schema: dict[str, Any]
    response_schema_hash: str
    provider_calls_total: int
    post_response_repair_allowed: bool
    integrity_hash: str

    def canonical_schema(self) -> dict[str, Any]:
        return copy.deepcopy(self.response_schema)

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "active": self.active,
            "transport_eligible": self.transport_eligible,
            "context_view_hash": self.context_view_hash,
            "mapping_receipt_integrity_hash": (
                self.mapping_receipt_integrity_hash
            ),
            "canonical_choice_schema_hash": (
                self.canonical_choice_schema_hash
            ),
            "response_schema_hash": self.response_schema_hash,
            "choice_keys": list(self.choice_keys),
            "unclassified_reason_codes": list(
                self.unclassified_reason_codes
            ),
            "model_output_fields": sorted(LOCAL_CHOICE_OUTPUT_FIELDS),
            "canonical_option_ids_visible_total": 0,
            "provider_calls_total": self.provider_calls_total,
            "post_response_repair_allowed": (
                self.post_response_repair_allowed
            ),
            "integrity_hash": self.integrity_hash,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6TypeFirstResponseProfile:
    schema_version: str
    policy_version: str
    active: bool
    transport_eligible: bool
    packet_hash: str
    context_view_sha256: str
    mapping_receipt_integrity_sha256: str
    canonical_choice_schema_hash: str
    type_keys: tuple[str, ...]
    response_schema: dict[str, Any]
    response_schema_sha256: str
    provider_calls_total: int
    post_response_repair_allowed: bool
    integrity_sha256: str

    def canonical_schema(self) -> dict[str, Any]:
        return copy.deepcopy(self.response_schema)

    def integrity_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "active": self.active,
            "transport_eligible": self.transport_eligible,
            "packet_hash": self.packet_hash,
            "context_view_sha256": self.context_view_sha256,
            "mapping_receipt_integrity_sha256": (
                self.mapping_receipt_integrity_sha256
            ),
            "canonical_choice_schema_hash": (
                self.canonical_choice_schema_hash
            ),
            "type_keys": list(self.type_keys),
            "response_schema": copy.deepcopy(self.response_schema),
            "response_schema_sha256": self.response_schema_sha256,
            "provider_calls_total": self.provider_calls_total,
            "post_response_repair_allowed": (
                self.post_response_repair_allowed
            ),
        }

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "active": self.active,
            "transport_eligible": self.transport_eligible,
            "context_view_sha256": self.context_view_sha256,
            "mapping_receipt_integrity_sha256": (
                self.mapping_receipt_integrity_sha256
            ),
            "response_schema_sha256": self.response_schema_sha256,
            "visible_type_keys_total": len(self.type_keys),
            "provider_calls_total": self.provider_calls_total,
            "post_response_repair_allowed": (
                self.post_response_repair_allowed
            ),
            "integrity_sha256": self.integrity_sha256,
        }


@dataclass(frozen=True)
class Gate2FinancialSemanticV6ChoiceContract:
    schema_version: str
    policy_version: str
    packet_hash: str
    candidate_compilation_integrity_hash: str
    choice_schema: dict[str, Any]
    choice_schema_hash: str
    provider_dispositions: tuple[str, ...]
    available_provider_dispositions: tuple[str, ...]
    typed_option_ids: tuple[str, ...]
    unclassified_reason_codes: tuple[str, ...]
    canonical_gate2_dispositions: tuple[str, ...]
    local_candidate: Gate2FinancialSemanticV6LocalChoiceCandidate
    context_v2_1_response_profile: (
        Gate2FinancialSemanticV6ContextV21ChoiceResponseProfile
    )

    def canonical_schema(self) -> dict[str, Any]:
        return copy.deepcopy(self.choice_schema)

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "policy_version": self.policy_version,
            "packet_hash": self.packet_hash,
            "candidate_compilation_integrity_hash": (
                self.candidate_compilation_integrity_hash
            ),
            "choice_schema_hash": self.choice_schema_hash,
            "provider_dispositions": list(self.provider_dispositions),
            "available_provider_dispositions": list(
                self.available_provider_dispositions
            ),
            "typed_options_total": len(self.typed_option_ids),
            "unclassified_reason_codes": list(self.unclassified_reason_codes),
            "model_output_fields": sorted(SEMANTIC_CHOICE_OUTPUT_FIELDS),
            "model_source_refs_total": 0,
            "model_role_bindings_total": 0,
            "technical_preclose_model_dispositions_total": 0,
            "canonical_gate2_dispositions_total": len(
                self.canonical_gate2_dispositions
            ),
            "provider_calls_total": 0,
            "non_active_local_candidate": (
                self.local_candidate.safe_summary()
            ),
            "non_active_context_v2_1_response_profile": (
                self.context_v2_1_response_profile.safe_summary()
            ),
        }


class Gate2FinancialSemanticV6ChoiceContractFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
    ) -> None:
        self.registry = registry

    def create(
        self,
        *,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6ChoiceContract:
        return self._build(
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
        )

    def create_type_first_response_profile(
        self,
        *,
        packet: Gate2FinancialSemanticV6Packet,
        type_first_candidate: (
            Gate2FinancialSemanticV6TypeFirstCandidate
        ),
        mapping_receipt: (
            Gate2FinancialSemanticV6TypeFirstMappingReceipt
        ),
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6TypeFirstResponseProfile:
        try:
            validate_financial_semantic_v6_type_first_material(
                candidate=type_first_candidate,
                receipt=mapping_receipt,
                packet=packet,
                evidence_bundle=evidence_bundle,
                source_package=source_package,
                compilation=compilation,
                registry=self.registry,
            )
        except Gate2FinancialSemanticV6PacketError as exc:
            raise Gate2FinancialSemanticV6ChoiceError(exc.code) from exc
        choice_contract = self._build(
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
        )
        type_keys = tuple(
            item["type_key"]
            for item in type_first_candidate.payload["type_cards"]
        )
        response_schema = _type_first_response_schema(type_keys)
        _validate_type_first_response_schema(
            schema=response_schema,
            type_keys=type_keys,
        )
        material = {
            "schema_version": (
                TYPE_FIRST_RESPONSE_PROFILE_SCHEMA_VERSION
            ),
            "policy_version": TYPE_FIRST_DECISION_POLICY_VERSION,
            "active": False,
            "transport_eligible": False,
            "packet_hash": packet.packet_hash,
            "context_view_sha256": (
                type_first_candidate.context_view_sha256
            ),
            "mapping_receipt_integrity_sha256": (
                mapping_receipt.integrity_sha256
            ),
            "canonical_choice_schema_hash": (
                choice_contract.choice_schema_hash
            ),
            "type_keys": list(type_keys),
            "response_schema": copy.deepcopy(response_schema),
            "response_schema_sha256": sha256_json(response_schema),
            "provider_calls_total": 0,
            "post_response_repair_allowed": False,
        }
        profile = Gate2FinancialSemanticV6TypeFirstResponseProfile(
            schema_version=TYPE_FIRST_RESPONSE_PROFILE_SCHEMA_VERSION,
            policy_version=TYPE_FIRST_DECISION_POLICY_VERSION,
            active=False,
            transport_eligible=False,
            packet_hash=packet.packet_hash,
            context_view_sha256=(
                type_first_candidate.context_view_sha256
            ),
            mapping_receipt_integrity_sha256=(
                mapping_receipt.integrity_sha256
            ),
            canonical_choice_schema_hash=(
                choice_contract.choice_schema_hash
            ),
            type_keys=type_keys,
            response_schema=copy.deepcopy(response_schema),
            response_schema_sha256=sha256_json(response_schema),
            provider_calls_total=0,
            post_response_repair_allowed=False,
            integrity_sha256=sha256_json(material),
        )
        validate_financial_semantic_v6_type_first_response_profile(
            profile=profile,
            type_first_candidate=type_first_candidate,
            mapping_receipt=mapping_receipt,
            choice_contract=choice_contract,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        return profile

    def _build(
        self,
        *,
        packet: Gate2FinancialSemanticV6Packet,
        evidence_bundle: Gate2FinancialEvidenceBundle,
        source_package: Gate2FinancialEvidenceSourcePackage,
        compilation: Gate2FinancialCandidateCompilation,
    ) -> Gate2FinancialSemanticV6ChoiceContract:
        _validate_packet(
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=self.registry,
        )
        if DISPOSITIONS != _CANONICAL_GATE2_DISPOSITIONS:
            _fail("financial_semantic_v6_canonical_dispositions_changed")
        typed_option_ids = tuple(
            item["option_id"] for item in packet.payload["typed_options"]
        )
        if typed_option_ids != tuple(
            item.typed_option_id for item in compilation.typed_options
        ) or len(typed_option_ids) != len(set(typed_option_ids)):
            _fail("financial_semantic_v6_choice_option_set_invalid")
        choice_schema = _choice_schema(typed_option_ids)
        available_dispositions = (
            SEMANTIC_CHOICE_PROVIDER_DISPOSITIONS
            if typed_option_ids
            else ("unclassified_financial_input",)
        )
        _validate_choice_schema(
            schema=choice_schema,
            typed_option_ids=typed_option_ids,
            available_dispositions=available_dispositions,
        )
        local_choice_aliases = tuple(
            packet.slim_alias_receipt.choice_aliases
        )
        if (
            set(packet.slim_alias_receipt.choice_aliases.values())
            != set(typed_option_ids)
            or len(local_choice_aliases) != len(typed_option_ids)
        ):
            _fail("financial_semantic_v6_local_choice_alias_mapping_invalid")
        local_schema = _local_choice_schema(local_choice_aliases)
        _validate_local_choice_schema(
            schema=local_schema,
            choice_aliases=local_choice_aliases,
        )
        local_material = {
            "schema_version": LOCAL_CHOICE_CANDIDATE_SCHEMA_VERSION,
            "policy_version": LOCAL_CHOICE_CANDIDATE_POLICY_VERSION,
            "active": False,
            "packet_hash": packet.packet_hash,
            "slim_view_hash": packet.slim_candidate.view_hash,
            "slim_alias_receipt_integrity_hash": (
                packet.slim_alias_receipt.integrity_hash
            ),
            "canonical_choice_schema_hash": sha256_json(choice_schema),
            "choice_aliases": list(local_choice_aliases),
            "unclassified_reason_codes": list(
                UNCLASSIFIED_REASON_CODES
            ),
            "response_schema": copy.deepcopy(local_schema),
            "response_schema_hash": sha256_json(local_schema),
            "provider_calls_total": 0,
            "post_response_repair_allowed": False,
        }
        local_candidate = Gate2FinancialSemanticV6LocalChoiceCandidate(
            schema_version=LOCAL_CHOICE_CANDIDATE_SCHEMA_VERSION,
            policy_version=LOCAL_CHOICE_CANDIDATE_POLICY_VERSION,
            active=False,
            packet_hash=packet.packet_hash,
            slim_view_hash=packet.slim_candidate.view_hash,
            slim_alias_receipt_integrity_hash=(
                packet.slim_alias_receipt.integrity_hash
            ),
            canonical_choice_schema_hash=sha256_json(choice_schema),
            choice_aliases=local_choice_aliases,
            unclassified_reason_codes=UNCLASSIFIED_REASON_CODES,
            response_schema=copy.deepcopy(local_schema),
            response_schema_hash=sha256_json(local_schema),
            provider_calls_total=0,
            post_response_repair_allowed=False,
            integrity_hash=sha256_json(local_material),
        )
        context_v2_1_choice_keys = tuple(
            item["choice_key"]
            for item in packet.context_v2_candidate.payload["choices"]
        )
        context_v2_1_reason_codes = tuple(
            item["code"]
            for item in packet.context_v2_candidate.payload[
                "unclassified_reasons"
            ]
        )
        context_v2_1_schema = _context_v2_1_choice_schema(
            choice_keys=context_v2_1_choice_keys,
            reason_codes=context_v2_1_reason_codes,
        )
        _validate_context_v2_1_choice_schema(
            schema=context_v2_1_schema,
            choice_keys=context_v2_1_choice_keys,
            reason_codes=context_v2_1_reason_codes,
        )
        context_v2_1_material = {
            "schema_version": (
                CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_SCHEMA_VERSION
            ),
            "policy_version": (
                CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_POLICY_VERSION
            ),
            "active": False,
            "transport_eligible": False,
            "packet_hash": packet.packet_hash,
            "context_view_hash": packet.context_v2_candidate.view_hash,
            "mapping_receipt_integrity_hash": (
                packet.context_v2_mapping_receipt.integrity_hash
            ),
            "canonical_choice_schema_hash": sha256_json(choice_schema),
            "choice_keys": list(context_v2_1_choice_keys),
            "unclassified_reason_codes": list(context_v2_1_reason_codes),
            "response_schema": copy.deepcopy(context_v2_1_schema),
            "response_schema_hash": sha256_json(context_v2_1_schema),
            "provider_calls_total": 0,
            "post_response_repair_allowed": False,
        }
        context_v2_1_response_profile = (
            Gate2FinancialSemanticV6ContextV21ChoiceResponseProfile(
                schema_version=(
                    CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_SCHEMA_VERSION
                ),
                policy_version=(
                    CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_POLICY_VERSION
                ),
                active=False,
                transport_eligible=False,
                packet_hash=packet.packet_hash,
                context_view_hash=packet.context_v2_candidate.view_hash,
                mapping_receipt_integrity_hash=(
                    packet.context_v2_mapping_receipt.integrity_hash
                ),
                canonical_choice_schema_hash=sha256_json(choice_schema),
                choice_keys=context_v2_1_choice_keys,
                unclassified_reason_codes=context_v2_1_reason_codes,
                response_schema=copy.deepcopy(context_v2_1_schema),
                response_schema_hash=sha256_json(context_v2_1_schema),
                provider_calls_total=0,
                post_response_repair_allowed=False,
                integrity_hash=sha256_json(context_v2_1_material),
            )
        )
        return Gate2FinancialSemanticV6ChoiceContract(
            schema_version=SEMANTIC_CHOICE_SCHEMA_VERSION,
            policy_version=SEMANTIC_CHOICE_POLICY_VERSION,
            packet_hash=packet.packet_hash,
            candidate_compilation_integrity_hash=(compilation.integrity_hash),
            choice_schema=choice_schema,
            choice_schema_hash=sha256_json(choice_schema),
            provider_dispositions=(SEMANTIC_CHOICE_PROVIDER_DISPOSITIONS),
            available_provider_dispositions=available_dispositions,
            typed_option_ids=typed_option_ids,
            unclassified_reason_codes=UNCLASSIFIED_REASON_CODES,
            canonical_gate2_dispositions=DISPOSITIONS,
            local_candidate=local_candidate,
            context_v2_1_response_profile=context_v2_1_response_profile,
        )


def validate_financial_semantic_v6_choice_contract(
    *,
    contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    if not isinstance(
        contract,
        Gate2FinancialSemanticV6ChoiceContract,
    ):
        _fail("financial_semantic_v6_choice_contract_invalid")
    expected = Gate2FinancialSemanticV6ChoiceContractFactory(registry=registry)._build(
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
    )
    if (
        contract != expected
        or _model_json_bytes(
            contract.context_v2_1_response_profile.response_schema
        )
        != _model_json_bytes(
            expected.context_v2_1_response_profile.response_schema
        )
    ):
        _fail("financial_semantic_v6_choice_contract_integrity_invalid")


def normalize_financial_semantic_v6_local_choice(
    *,
    model_output: str | dict[str, Any],
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
) -> dict[str, str]:
    _validate_local_candidate_binding(
        choice_contract=choice_contract,
        packet=packet,
    )
    if isinstance(model_output, str):
        if (
            not model_output
            or len(model_output.encode("utf-8"))
            > _MAX_LOCAL_CHOICE_BYTES
        ):
            _fail("financial_semantic_v6_local_choice_size_invalid")
        try:
            parsed = json.loads(
                model_output,
                object_pairs_hook=_unique_local_object,
            )
        except json.JSONDecodeError as exc:
            raise Gate2FinancialSemanticV6ChoiceError(
                "financial_semantic_v6_local_choice_json_invalid"
            ) from exc
    else:
        parsed = model_output
    if not isinstance(parsed, dict):
        _fail("financial_semantic_v6_local_choice_invalid")
    choice = parsed.get("choice")
    if choice == "unclassified":
        if set(parsed) != {"choice", "reason"}:
            _fail(
                "financial_semantic_v6_local_choice_unclassified_shape_invalid"
            )
        reason = parsed["reason"]
        if (
            not isinstance(reason, str)
            or reason
            not in choice_contract.local_candidate.unclassified_reason_codes
        ):
            _fail("financial_semantic_v6_local_choice_reason_invalid")
        return {
            "disposition": "unclassified_financial_input",
            "reason_code": reason,
        }
    if set(parsed) != {"choice"} or not isinstance(choice, str):
        _fail("financial_semantic_v6_local_choice_typed_shape_invalid")
    exact_option_id = packet.slim_alias_receipt.choice_aliases.get(choice)
    if exact_option_id is None:
        _fail("financial_semantic_v6_local_choice_alias_unknown")
    return {
        "disposition": "typed_input",
        "typed_option_id": exact_option_id,
    }


def normalize_financial_semantic_v6_context_v2_1_choice(
    *,
    model_output: str | dict[str, Any],
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
) -> dict[str, str]:
    _validate_context_v2_1_response_profile_binding(
        choice_contract=choice_contract,
        packet=packet,
    )
    if isinstance(model_output, str):
        if (
            not model_output
            or len(model_output.encode("utf-8"))
            > _MAX_CONTEXT_V2_1_CHOICE_BYTES
        ):
            _fail("financial_semantic_v6_context_v2_1_choice_size_invalid")
        try:
            parsed = json.loads(
                model_output,
                object_pairs_hook=_unique_context_v2_1_choice_object,
            )
        except json.JSONDecodeError as exc:
            raise Gate2FinancialSemanticV6ChoiceError(
                "financial_semantic_v6_context_v2_1_choice_json_invalid"
            ) from exc
    else:
        parsed = model_output
    if not isinstance(parsed, dict):
        _fail("financial_semantic_v6_context_v2_1_choice_invalid")
    choice = parsed.get("choice")
    profile = choice_contract.context_v2_1_response_profile
    if choice == "unclassified":
        if set(parsed) != {"choice", "reason"}:
            _fail(
                "financial_semantic_v6_context_v2_1_choice_"
                "unclassified_shape_invalid"
            )
        reason = parsed["reason"]
        if (
            not isinstance(reason, str)
            or reason not in profile.unclassified_reason_codes
        ):
            _fail(
                "financial_semantic_v6_context_v2_1_choice_reason_invalid"
            )
        return {
            "disposition": "unclassified_financial_input",
            "reason_code": reason,
        }
    if set(parsed) != {"choice"} or not isinstance(choice, str):
        _fail(
            "financial_semantic_v6_context_v2_1_choice_typed_shape_invalid"
        )
    restoration = {
        item["choice_key"]: item["typed_option_id"]
        for item in packet.context_v2_mapping_receipt.choice_restoration
    }
    exact_option_id = restoration.get(choice)
    if exact_option_id is None:
        _fail("financial_semantic_v6_context_v2_1_choice_key_unknown")
    return {
        "disposition": "typed_input",
        "typed_option_id": exact_option_id,
    }


def normalize_financial_semantic_v6_type_first_response(
    *,
    model_output: str | dict[str, Any],
    response_profile: (
        Gate2FinancialSemanticV6TypeFirstResponseProfile
    ),
    type_first_candidate: Gate2FinancialSemanticV6TypeFirstCandidate,
    mapping_receipt: Gate2FinancialSemanticV6TypeFirstMappingReceipt,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
) -> dict[str, tuple[str, ...]]:
    _validate_type_first_response_profile_binding(
        profile=response_profile,
        type_first_candidate=type_first_candidate,
        mapping_receipt=mapping_receipt,
        choice_contract=choice_contract,
        packet=packet,
    )
    if isinstance(model_output, str):
        if (
            not model_output
            or len(model_output.encode("utf-8"))
            > _MAX_TYPE_FIRST_RESPONSE_BYTES
        ):
            _fail("malformed_json")
        try:
            decoded = json.loads(
                model_output,
                object_pairs_hook=_TypeFirstJsonObject,
                parse_constant=_reject_type_first_json_constant,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise Gate2FinancialSemanticV6ChoiceError(
                "malformed_json"
            ) from exc
        if isinstance(decoded, _TypeFirstJsonObject):
            root_pairs = decoded.pairs
            if len({key for key, _ in root_pairs}) != len(root_pairs):
                _fail("duplicate_response_field")
            parsed: Any = dict(root_pairs)
        else:
            parsed = decoded
    else:
        parsed = copy.deepcopy(model_output)
    if not isinstance(parsed, dict):
        _fail("response_root_not_object")
    if "plausible_types" not in parsed:
        _fail("missing_plausible_types")
    if set(parsed) != {"plausible_types"}:
        _fail("extra_response_field")
    plausible_types = parsed["plausible_types"]
    if plausible_types is None:
        _fail("plausible_types_null")
    if not isinstance(plausible_types, list):
        _fail("plausible_types_not_array")
    canonical_ids = frozenset(
        mapping_receipt.local_to_canonical_type_ids.values()
    )
    if any(
        isinstance(item, str) and item in canonical_ids
        for item in plausible_types
    ):
        _fail("backend_type_id_forbidden")
    if any(
        not isinstance(item, str)
        or item not in response_profile.type_keys
        for item in plausible_types
    ):
        _fail("unknown_type_key")
    if len(plausible_types) != len(set(plausible_types)):
        _fail("duplicate_type_key")
    positions = tuple(
        response_profile.type_keys.index(item)
        for item in plausible_types
    )
    if positions != tuple(sorted(positions)):
        _fail("out_of_order_type_keys")
    local_keys = tuple(plausible_types)
    return {
        "plausible_type_keys": local_keys,
    }


def _choice_schema(
    typed_option_ids: tuple[str, ...],
) -> dict[str, Any]:
    variants = []
    if typed_option_ids:
        variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "disposition": {
                        "type": "string",
                        "enum": ["typed_input"],
                    },
                    "typed_option_id": {
                        "type": "string",
                        "enum": list(typed_option_ids),
                    },
                },
                "required": [
                    "disposition",
                    "typed_option_id",
                ],
            }
        )
    variants.append(
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "disposition": {
                    "type": "string",
                    "enum": ["unclassified_financial_input"],
                },
                "reason_code": {
                    "type": "string",
                    "enum": list(UNCLASSIFIED_REASON_CODES),
                },
            },
            "required": ["disposition", "reason_code"],
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": SEMANTIC_CHOICE_SCHEMA_VERSION,
        "anyOf": variants,
    }


def _local_choice_schema(
    choice_aliases: tuple[str, ...],
) -> dict[str, Any]:
    variants = []
    if choice_aliases:
        variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "choice": {
                        "type": "string",
                        "enum": list(choice_aliases),
                    },
                },
                "required": ["choice"],
            }
        )
    variants.append(
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "choice": {
                    "type": "string",
                    "enum": ["unclassified"],
                },
                "reason": {
                    "type": "string",
                    "enum": list(UNCLASSIFIED_REASON_CODES),
                },
            },
            "required": ["choice", "reason"],
        }
    )
    return {
        "title": "Semantic choice",
        "anyOf": variants,
    }


def _context_v2_1_choice_schema(
    *,
    choice_keys: tuple[str, ...],
    reason_codes: tuple[str, ...],
) -> dict[str, Any]:
    variants = []
    if choice_keys:
        variants.append(
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "choice": {
                        "type": "string",
                        "enum": list(choice_keys),
                    },
                },
                "required": ["choice"],
            }
        )
    variants.append(
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "choice": {
                    "type": "string",
                    "enum": ["unclassified"],
                },
                "reason": {
                    "type": "string",
                    "enum": list(reason_codes),
                },
            },
            "required": ["choice", "reason"],
        }
    )
    return {"anyOf": variants}


def _type_first_response_schema(
    type_keys: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "plausible_types": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": list(type_keys),
                },
                "minItems": 0,
                "maxItems": len(type_keys),
                "uniqueItems": True,
            }
        },
        "required": ["plausible_types"],
    }


def _validate_type_first_response_schema(
    *,
    schema: Any,
    type_keys: tuple[str, ...],
) -> None:
    if (
        not type_keys
        or len(type_keys) != len(set(type_keys))
        or type_keys
        != tuple(f"type_{index}" for index in range(1, len(type_keys) + 1))
        or schema != _type_first_response_schema(type_keys)
    ):
        _fail("context_profile_schema_hash_mismatch")


def _validate_context_v2_1_choice_schema(
    *,
    schema: Any,
    choice_keys: tuple[str, ...],
    reason_codes: tuple[str, ...],
) -> None:
    if (
        not isinstance(schema, dict)
        or set(schema) != {"anyOf"}
        or not isinstance(schema["anyOf"], list)
        or not schema["anyOf"]
        or choice_keys
        != tuple(f"choice_{index}" for index in range(1, len(choice_keys) + 1))
        or "unclassified" in choice_keys
        or len(choice_keys) != len(set(choice_keys))
        or reason_codes != CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES
        or len(reason_codes) != len(set(reason_codes))
    ):
        _fail("financial_semantic_v6_context_v2_1_choice_schema_invalid")
    expected = _context_v2_1_choice_schema(
        choice_keys=choice_keys,
        reason_codes=reason_codes,
    )
    if schema != expected:
        _fail(
            "financial_semantic_v6_context_v2_1_choice_"
            "schema_authority_mismatch"
        )


def _validate_local_choice_schema(
    *,
    schema: Any,
    choice_aliases: tuple[str, ...],
) -> None:
    if (
        not isinstance(schema, dict)
        or set(schema) != {"title", "anyOf"}
        or schema["title"] != "Semantic choice"
        or not isinstance(schema["anyOf"], list)
        or not schema["anyOf"]
    ):
        _fail("financial_semantic_v6_local_choice_schema_invalid")
    expected = _local_choice_schema(choice_aliases)
    if schema != expected:
        _fail("financial_semantic_v6_local_choice_schema_authority_mismatch")


def _validate_local_candidate_binding(
    *,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
) -> None:
    if (
        not isinstance(
            choice_contract,
            Gate2FinancialSemanticV6ChoiceContract,
        )
        or not isinstance(packet, Gate2FinancialSemanticV6Packet)
    ):
        _fail("financial_semantic_v6_local_choice_authority_invalid")
    candidate = choice_contract.local_candidate
    if not isinstance(
        candidate,
        Gate2FinancialSemanticV6LocalChoiceCandidate,
    ):
        _fail("financial_semantic_v6_local_choice_candidate_invalid")
    try:
        receipt_payload = packet.slim_alias_receipt.to_private_dict()
        receipt_integrity_hash = receipt_payload.pop("integrity_hash")
    except (AttributeError, KeyError):
        _fail("financial_semantic_v6_local_choice_receipt_invalid")
    material = {
        "schema_version": candidate.schema_version,
        "policy_version": candidate.policy_version,
        "active": candidate.active,
        "packet_hash": candidate.packet_hash,
        "slim_view_hash": candidate.slim_view_hash,
        "slim_alias_receipt_integrity_hash": (
            candidate.slim_alias_receipt_integrity_hash
        ),
        "canonical_choice_schema_hash": (
            candidate.canonical_choice_schema_hash
        ),
        "choice_aliases": list(candidate.choice_aliases),
        "unclassified_reason_codes": list(
            candidate.unclassified_reason_codes
        ),
        "response_schema": copy.deepcopy(candidate.response_schema),
        "response_schema_hash": candidate.response_schema_hash,
        "provider_calls_total": candidate.provider_calls_total,
        "post_response_repair_allowed": (
            candidate.post_response_repair_allowed
        ),
    }
    if (
        candidate.schema_version
        != LOCAL_CHOICE_CANDIDATE_SCHEMA_VERSION
        or candidate.policy_version
        != LOCAL_CHOICE_CANDIDATE_POLICY_VERSION
        or candidate.active is not False
        or packet.packet_hash != sha256_json(packet.payload)
        or packet.slim_candidate.view_hash
        != sha256_json(packet.slim_candidate.payload)
        or packet.slim_alias_receipt.slim_view_hash
        != packet.slim_candidate.view_hash
        or receipt_integrity_hash
        != packet.slim_alias_receipt.integrity_hash
        or receipt_integrity_hash != sha256_json(receipt_payload)
        or candidate.packet_hash != packet.packet_hash
        or candidate.slim_view_hash != packet.slim_candidate.view_hash
        or candidate.slim_alias_receipt_integrity_hash
        != packet.slim_alias_receipt.integrity_hash
        or candidate.canonical_choice_schema_hash
        != choice_contract.choice_schema_hash
        or choice_contract.choice_schema_hash
        != sha256_json(choice_contract.choice_schema)
        or candidate.choice_aliases
        != tuple(packet.slim_alias_receipt.choice_aliases)
        or set(packet.slim_alias_receipt.choice_aliases.values())
        != set(choice_contract.typed_option_ids)
        or len(candidate.choice_aliases)
        != len(choice_contract.typed_option_ids)
        or candidate.unclassified_reason_codes
        != choice_contract.unclassified_reason_codes
        or candidate.response_schema_hash
        != sha256_json(candidate.response_schema)
        or candidate.provider_calls_total != 0
        or candidate.post_response_repair_allowed is not False
        or candidate.integrity_hash != sha256_json(material)
    ):
        _fail("financial_semantic_v6_local_choice_integrity_invalid")
    _validate_local_choice_schema(
        schema=candidate.response_schema,
        choice_aliases=candidate.choice_aliases,
    )


def _validate_context_v2_1_response_profile_binding(
    *,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
) -> None:
    if (
        not isinstance(
            choice_contract,
            Gate2FinancialSemanticV6ChoiceContract,
        )
        or not isinstance(packet, Gate2FinancialSemanticV6Packet)
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_choice_authority_invalid"
        )
    profile = choice_contract.context_v2_1_response_profile
    candidate = packet.context_v2_candidate
    receipt = packet.context_v2_mapping_receipt
    if (
        not isinstance(
            profile,
            Gate2FinancialSemanticV6ContextV21ChoiceResponseProfile,
        )
        or not isinstance(
            candidate,
            Gate2FinancialSemanticV6ContextV21Candidate,
        )
        or not isinstance(
            receipt,
            Gate2FinancialSemanticV6ContextV21MappingReceipt,
        )
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_choice_profile_invalid"
        )
    try:
        active_typed_option_rows = packet.payload["typed_options"]
        visible_choice_rows = candidate.payload["choices"]
        visible_reason_rows = candidate.payload["unclassified_reasons"]
        if (
            not isinstance(active_typed_option_rows, list)
            or not isinstance(visible_choice_rows, list)
            or not isinstance(visible_reason_rows, list)
            or any(
                not isinstance(item, dict)
                for item in active_typed_option_rows
            )
            or any(not isinstance(item, dict) for item in visible_choice_rows)
            or any(not isinstance(item, dict) for item in visible_reason_rows)
        ):
            raise TypeError
        active_typed_option_ids = tuple(
            item["option_id"] for item in active_typed_option_rows
        )
        visible_choice_keys = tuple(
            item["choice_key"] for item in visible_choice_rows
        )
        visible_reason_codes = tuple(
            item["code"] for item in visible_reason_rows
        )
        restoration_rows = receipt.choice_restoration
        if not isinstance(restoration_rows, tuple) or any(
            not isinstance(item, dict) for item in restoration_rows
        ):
            raise TypeError
        restoration_choice_keys = tuple(
            item["choice_key"] for item in restoration_rows
        )
        restoration_option_ids = tuple(
            item["typed_option_id"] for item in restoration_rows
        )
        restoration_pointers = tuple(
            item["json_pointer"] for item in restoration_rows
        )
        receipt_material = receipt.to_private_dict()
        receipt_integrity_hash = receipt_material.pop("integrity_hash")
        presentation_choice_keys = tuple(
            receipt.presentation_order["choice_keys"]
        )
        presentation_reason_codes = tuple(
            receipt.presentation_order["reason_codes"]
        )
        if (
            any(
                not {"choice_key", "json_pointer", "typed_option_id"}.issubset(
                    item
                )
                for item in restoration_rows
            )
            or any(
                not isinstance(item, str) or not item
                for item in (
                    *active_typed_option_ids,
                    *visible_choice_keys,
                    *visible_reason_codes,
                    *restoration_choice_keys,
                    *restoration_option_ids,
                    *restoration_pointers,
                    *presentation_choice_keys,
                    *presentation_reason_codes,
                )
            )
        ):
            raise TypeError
    except (AttributeError, KeyError, TypeError):
        _fail(
            "financial_semantic_v6_context_v2_1_choice_receipt_invalid"
        )
    profile_material = {
        "schema_version": profile.schema_version,
        "policy_version": profile.policy_version,
        "active": profile.active,
        "transport_eligible": profile.transport_eligible,
        "packet_hash": profile.packet_hash,
        "context_view_hash": profile.context_view_hash,
        "mapping_receipt_integrity_hash": (
            profile.mapping_receipt_integrity_hash
        ),
        "canonical_choice_schema_hash": (
            profile.canonical_choice_schema_hash
        ),
        "choice_keys": list(profile.choice_keys),
        "unclassified_reason_codes": list(
            profile.unclassified_reason_codes
        ),
        "response_schema": copy.deepcopy(profile.response_schema),
        "response_schema_hash": profile.response_schema_hash,
        "provider_calls_total": profile.provider_calls_total,
        "post_response_repair_allowed": (
            profile.post_response_repair_allowed
        ),
    }
    context_view_hash = hashlib.sha256(
        json.dumps(
            candidate.payload,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    expected_pointers = tuple(
        f"/choices/{index}" for index in range(len(restoration_rows))
    )
    presentation_material = {
        "source_occurrence_pointers": receipt.presentation_order.get(
            "source_occurrence_pointers"
        ),
        "type_keys": receipt.presentation_order.get("type_keys"),
        "choice_keys": list(presentation_choice_keys),
        "reason_codes": list(presentation_reason_codes),
    }
    if (
        profile.schema_version
        != CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_SCHEMA_VERSION
        or profile.policy_version
        != CONTEXT_V2_1_CHOICE_RESPONSE_PROFILE_POLICY_VERSION
        or profile.active is not False
        or profile.transport_eligible is not False
        or profile.provider_calls_total != 0
        or profile.post_response_repair_allowed is not False
        or candidate.schema_version
        != CONTEXT_V2_1_CANDIDATE_SCHEMA_VERSION
        or candidate.policy_version != CONTEXT_V2_1_POLICY_VERSION
        or candidate.active is not False
        or candidate.transport_eligible is not False
        or candidate.provider_calls_total != 0
        or receipt.schema_version
        != CONTEXT_V2_1_MAPPING_RECEIPT_SCHEMA_VERSION
        or receipt.policy_version != CONTEXT_V2_1_POLICY_VERSION
        or receipt.provider_calls_total != 0
        or packet.packet_hash != sha256_json(packet.payload)
        or profile.packet_hash != packet.packet_hash
        or candidate.view_hash != context_view_hash
        or profile.context_view_hash != candidate.view_hash
        or receipt.identities.get("active_packet_hash")
        != packet.packet_hash
        or receipt.identities.get("context_view_hash")
        != candidate.view_hash
        or receipt_integrity_hash != receipt.integrity_hash
        or receipt_integrity_hash != sha256_json(receipt_material)
        or profile.mapping_receipt_integrity_hash
        != receipt.integrity_hash
        or profile.canonical_choice_schema_hash
        != choice_contract.choice_schema_hash
        or choice_contract.choice_schema_hash
        != sha256_json(choice_contract.choice_schema)
        or choice_contract.typed_option_ids != active_typed_option_ids
        or len(active_typed_option_ids) != len(set(active_typed_option_ids))
        or choice_contract.choice_schema
        != _choice_schema(active_typed_option_ids)
        or profile.choice_keys != visible_choice_keys
        or profile.choice_keys != restoration_choice_keys
        or profile.choice_keys != presentation_choice_keys
        or profile.choice_keys
        != tuple(
            f"choice_{index}"
            for index in range(1, len(profile.choice_keys) + 1)
        )
        or len(profile.choice_keys) != len(set(profile.choice_keys))
        or "unclassified" in profile.choice_keys
        or profile.unclassified_reason_codes != visible_reason_codes
        or profile.unclassified_reason_codes != presentation_reason_codes
        or profile.unclassified_reason_codes
        != CONTEXT_V2_1_UNCLASSIFIED_REASON_CODES
        or len(profile.unclassified_reason_codes)
        != len(set(profile.unclassified_reason_codes))
        or restoration_option_ids != active_typed_option_ids
        or len(restoration_option_ids) != len(set(restoration_option_ids))
        or restoration_pointers != expected_pointers
        or receipt.presentation_order.get("presentation_identity")
        != sha256_json(presentation_material)
        or profile.response_schema_hash
        != sha256_json(profile.response_schema)
        or profile.integrity_hash != sha256_json(profile_material)
    ):
        _fail(
            "financial_semantic_v6_context_v2_1_choice_integrity_invalid"
        )
    _validate_context_v2_1_choice_schema(
        schema=profile.response_schema,
        choice_keys=profile.choice_keys,
        reason_codes=profile.unclassified_reason_codes,
    )


def validate_financial_semantic_v6_type_first_response_profile(
    *,
    profile: Gate2FinancialSemanticV6TypeFirstResponseProfile,
    type_first_candidate: Gate2FinancialSemanticV6TypeFirstCandidate,
    mapping_receipt: Gate2FinancialSemanticV6TypeFirstMappingReceipt,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    try:
        validate_financial_semantic_v6_type_first_material(
            candidate=type_first_candidate,
            receipt=mapping_receipt,
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=registry,
        )
    except Gate2FinancialSemanticV6PacketError as exc:
        raise Gate2FinancialSemanticV6ChoiceError(exc.code) from exc
    validate_financial_semantic_v6_choice_contract(
        contract=choice_contract,
        packet=packet,
        evidence_bundle=evidence_bundle,
        source_package=source_package,
        compilation=compilation,
        registry=registry,
    )
    _validate_type_first_response_profile_binding(
        profile=profile,
        type_first_candidate=type_first_candidate,
        mapping_receipt=mapping_receipt,
        choice_contract=choice_contract,
        packet=packet,
    )


def _validate_type_first_response_profile_binding(
    *,
    profile: Gate2FinancialSemanticV6TypeFirstResponseProfile,
    type_first_candidate: Gate2FinancialSemanticV6TypeFirstCandidate,
    mapping_receipt: Gate2FinancialSemanticV6TypeFirstMappingReceipt,
    choice_contract: Gate2FinancialSemanticV6ChoiceContract,
    packet: Gate2FinancialSemanticV6Packet,
) -> None:
    if (
        not isinstance(
            profile,
            Gate2FinancialSemanticV6TypeFirstResponseProfile,
        )
        or not isinstance(
            type_first_candidate,
            Gate2FinancialSemanticV6TypeFirstCandidate,
        )
        or not isinstance(
            mapping_receipt,
            Gate2FinancialSemanticV6TypeFirstMappingReceipt,
        )
        or not isinstance(
            choice_contract,
            Gate2FinancialSemanticV6ChoiceContract,
        )
        or not isinstance(packet, Gate2FinancialSemanticV6Packet)
    ):
        _fail("context_profile_schema_hash_mismatch")
    if (
        mapping_receipt.schema_version
        != TYPE_FIRST_MAPPING_RECEIPT_SCHEMA_VERSION
        or mapping_receipt.policy_version
        != TYPE_FIRST_DECISION_POLICY_VERSION
        or mapping_receipt.provider_calls_total != 0
        or mapping_receipt.integrity_sha256
        != sha256_json(mapping_receipt.integrity_payload())
        or type_first_candidate.schema_version
        != TYPE_FIRST_CONTEXT_PROFILE
        or type_first_candidate.policy_version
        != TYPE_FIRST_DECISION_POLICY_VERSION
        or type_first_candidate.active is not False
        or type_first_candidate.transport_eligible is not False
        or type_first_candidate.provider_calls_total != 0
        or mapping_receipt.context_view_sha256
        != type_first_candidate.context_view_sha256
        or mapping_receipt.visible_type_card_order
        != tuple(
            item.get("type_key")
            for item in type_first_candidate.payload.get(
                "type_cards",
                (),
            )
        )
        or tuple(mapping_receipt.local_to_canonical_type_ids)
        != mapping_receipt.visible_type_card_order
    ):
        _fail("mapping_receipt_mismatch")
    if (
        profile.schema_version
        != TYPE_FIRST_RESPONSE_PROFILE_SCHEMA_VERSION
        or profile.policy_version
        != TYPE_FIRST_DECISION_POLICY_VERSION
        or profile.active is not False
        or profile.transport_eligible is not False
        or profile.provider_calls_total != 0
        or profile.post_response_repair_allowed is not False
        or profile.packet_hash != packet.packet_hash
        or profile.context_view_sha256
        != type_first_candidate.context_view_sha256
        or profile.mapping_receipt_integrity_sha256
        != mapping_receipt.integrity_sha256
        or profile.canonical_choice_schema_hash
        != choice_contract.choice_schema_hash
        or profile.type_keys
        != mapping_receipt.visible_type_card_order
        or profile.response_schema_sha256
        != sha256_json(profile.response_schema)
        or profile.integrity_sha256
        != sha256_json(profile.integrity_payload())
    ):
        _fail("context_profile_schema_hash_mismatch")
    _validate_type_first_response_schema(
        schema=profile.response_schema,
        type_keys=profile.type_keys,
    )


def _model_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Gate2FinancialSemanticV6ChoiceError(
            "financial_semantic_v6_context_v2_1_choice_"
            "schema_serialization_invalid"
        ) from exc


def _unique_local_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("financial_semantic_v6_local_choice_duplicate_key")
        result[key] = value
    return result


def _unique_context_v2_1_choice_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail(
                "financial_semantic_v6_context_v2_1_choice_duplicate_key"
            )
        result[key] = value
    return result


@dataclass(frozen=True)
class _TypeFirstJsonObject:
    pairs: list[tuple[str, Any]]


def _reject_type_first_json_constant(value: str) -> None:
    raise ValueError(value)


def _validate_choice_schema(
    *,
    schema: Any,
    typed_option_ids: tuple[str, ...],
    available_dispositions: tuple[str, ...],
) -> None:
    if (
        not isinstance(schema, dict)
        or set(schema) != {"$schema", "title", "anyOf"}
        or schema["title"] != SEMANTIC_CHOICE_SCHEMA_VERSION
        or not isinstance(schema["anyOf"], list)
        or not schema["anyOf"]
    ):
        _fail("financial_semantic_v6_choice_schema_invalid")
    observed_dispositions = []
    observed_option_ids: tuple[str, ...] = ()
    for variant in schema["anyOf"]:
        if (
            not isinstance(variant, dict)
            or set(variant)
            != {
                "type",
                "additionalProperties",
                "properties",
                "required",
            }
            or variant["type"] != "object"
            or variant["additionalProperties"] is not False
            or not isinstance(variant["properties"], dict)
            or set(variant["properties"]) != set(variant["required"])
        ):
            _fail("financial_semantic_v6_choice_variant_invalid")
        properties = variant["properties"]
        disposition_values = (properties.get("disposition") or {}).get("enum")
        if (
            not isinstance(disposition_values, list)
            or len(disposition_values) != 1
            or disposition_values[0] not in SEMANTIC_CHOICE_PROVIDER_DISPOSITIONS
        ):
            _fail("financial_semantic_v6_choice_disposition_invalid")
        disposition = disposition_values[0]
        observed_dispositions.append(disposition)
        if disposition == "typed_input":
            if set(properties) != {
                "disposition",
                "typed_option_id",
            }:
                _fail("financial_semantic_v6_choice_typed_shape_invalid")
            values = properties["typed_option_id"].get("enum")
            if not isinstance(values, list) or any(
                not isinstance(item, str) for item in values
            ):
                _fail("financial_semantic_v6_choice_option_enum_invalid")
            observed_option_ids = tuple(values)
        elif set(properties) != {"disposition", "reason_code"}:
            _fail("financial_semantic_v6_choice_unclassified_shape_invalid")
        elif tuple(properties["reason_code"].get("enum") or ()) != (
            UNCLASSIFIED_REASON_CODES
        ):
            _fail("financial_semantic_v6_choice_reason_enum_invalid")
    if (
        tuple(observed_dispositions) != available_dispositions
        or observed_option_ids != typed_option_ids
        or len(observed_dispositions) != len(set(observed_dispositions))
    ):
        _fail("financial_semantic_v6_choice_schema_authority_mismatch")


def _validate_packet(
    *,
    packet: Gate2FinancialSemanticV6Packet,
    evidence_bundle: Gate2FinancialEvidenceBundle,
    source_package: Gate2FinancialEvidenceSourcePackage,
    compilation: Gate2FinancialCandidateCompilation,
    registry: Gate2FinancialEvidenceRegistrySnapshot,
) -> None:
    try:
        validate_financial_semantic_v6_packet(
            packet=packet,
            evidence_bundle=evidence_bundle,
            source_package=source_package,
            compilation=compilation,
            registry=registry,
        )
    except Gate2FinancialSemanticV6PacketError as exc:
        raise Gate2FinancialSemanticV6ChoiceError(
            "financial_semantic_v6_choice_packet_invalid"
        ) from exc


def _fail(code: str) -> None:
    raise Gate2FinancialSemanticV6ChoiceError(code)
