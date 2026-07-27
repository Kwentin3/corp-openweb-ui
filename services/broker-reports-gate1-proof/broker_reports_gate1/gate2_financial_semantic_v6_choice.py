from __future__ import annotations

import copy
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
_CANONICAL_GATE2_DISPOSITIONS = (
    "typed_input",
    "unclassified_financial_input",
    "no_financial_input",
    "unsupported",
)

FACTORY_REQUIRED = (
    "Gate2FinancialSemanticV6ChoiceContractFactory.create is the only V6 "
    "minimal semantic-choice contract entrypoint"
)
FORBIDDEN = (
    "The provider choice must not return a type ID, source ref, role binding, "
    "literal, provenance, dimension or record field; technical preclose "
    "dispositions must not be exposed to the model"
)


class Gate2FinancialSemanticV6ChoiceError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


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
