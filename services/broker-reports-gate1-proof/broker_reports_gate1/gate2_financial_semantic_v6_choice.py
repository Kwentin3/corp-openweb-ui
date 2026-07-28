from __future__ import annotations

import copy
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
    Gate2FinancialSemanticV6Packet,
    Gate2FinancialSemanticV6PacketError,
    validate_financial_semantic_v6_packet,
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
_CANONICAL_GATE2_DISPOSITIONS = (
    "typed_input",
    "unclassified_financial_input",
    "no_financial_input",
    "unsupported",
)

FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6ChoiceContractFactory.create is the only V6 "
    "active minimal semantic-choice and non-active local-choice candidate "
    "contract entrypoint"
)
FORBIDDEN = (
    "The provider choice must not return a type ID, source ref, role binding, "
    "literal, provenance, dimension or record field; technical preclose "
    "dispositions must not be exposed to the model; the local candidate must "
    "not expose canonical option IDs or become an active request schema"
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
    if contract != expected:
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


def _unique_local_object(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("financial_semantic_v6_local_choice_duplicate_key")
        result[key] = value
    return result


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
