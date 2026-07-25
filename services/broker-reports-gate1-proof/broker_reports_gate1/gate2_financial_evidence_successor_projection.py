from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_decision import (
    DISPOSITIONS,
    Gate2FinancialEvidenceDecisionContract,
)
from .gate2_financial_evidence_materialization_contracts import sha256_json


SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_evidence_provider_projection_v3"
)
SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION = (
    "gate2_financial_evidence_unclassified_first_projection_v3"
)

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceSuccessorProviderProjectionFactory.create is "
    "the only successor response-format projection v3 entrypoint"
)
FORBIDDEN = (
    "The provider projection must not add a decision branch, admit a type, "
    "change canonical branch semantics, call a model, relax strict schema "
    "mode or replace canonical decision validation"
)

_DISPOSITION_ORDER = {
    "unclassified_financial_input": 0,
    "typed_input": 1,
    "no_financial_input": 2,
    "unsupported": 3,
}


class Gate2FinancialEvidenceSuccessorProviderProjectionError(
    ValueError
):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate2FinancialEvidenceSuccessorProviderProjection:
    response_format: dict[str, Any]
    response_format_hash: str
    disposition_order: tuple[str, ...]
    typed_type_ids: tuple[str, ...]

    def safe_summary(self) -> dict[str, Any]:
        return {
            "schema_version": (
                SUCCESSOR_PROVIDER_PROJECTION_SCHEMA_VERSION
            ),
            "policy_version": (
                SUCCESSOR_PROVIDER_PROJECTION_POLICY_VERSION
            ),
            "response_format_hash": self.response_format_hash,
            "disposition_order": list(self.disposition_order),
            "typed_type_ids": list(self.typed_type_ids),
            "strict_json_schema": True,
            "canonical_semantics_changed": False,
            "provider_calls_total": 0,
        }


class Gate2FinancialEvidenceSuccessorProviderProjectionFactory:
    def create(
        self,
        *,
        contract: Gate2FinancialEvidenceDecisionContract,
    ) -> Gate2FinancialEvidenceSuccessorProviderProjection:
        response_format = copy.deepcopy(
            contract.openai_response_format()
        )
        variants = _decision_variants(response_format)
        variants.sort(
            key=lambda item: (
                _DISPOSITION_ORDER[_variant_disposition(item)],
                _variant_type_id(item) or "",
            )
        )
        disposition_order = tuple(
            _variant_disposition(item) for item in variants
        )
        typed_type_ids = tuple(
            type_id
            for item in variants
            if (type_id := _variant_type_id(item)) is not None
        )
        result = (
            Gate2FinancialEvidenceSuccessorProviderProjection(
                response_format=response_format,
                response_format_hash=sha256_json(response_format),
                disposition_order=disposition_order,
                typed_type_ids=typed_type_ids,
            )
        )
        validate_successor_provider_projection(
            projection=result,
            contract=contract,
        )
        return result


def validate_successor_provider_projection(
    *,
    projection: Gate2FinancialEvidenceSuccessorProviderProjection,
    contract: Gate2FinancialEvidenceDecisionContract,
) -> None:
    if not isinstance(
        projection,
        Gate2FinancialEvidenceSuccessorProviderProjection,
    ):
        _fail("successor_provider_projection_type_invalid")
    projected = copy.deepcopy(projection.response_format)
    canonical = copy.deepcopy(contract.openai_response_format())
    projected_variants = _decision_variants(projected)
    canonical_variants = _decision_variants(canonical)
    if (
        projected.get("type") != "json_schema"
        or (projected.get("json_schema") or {}).get("strict") is not True
        or projection.response_format_hash
        != sha256_json(projection.response_format)
    ):
        _fail("successor_provider_projection_identity_invalid")
    projected_dispositions = tuple(
        _variant_disposition(item) for item in projected_variants
    )
    expected_dispositions = set(DISPOSITIONS)
    if not contract.eligible_type_ids:
        expected_dispositions.remove("typed_input")
    if (
        projected_dispositions != projection.disposition_order
        or set(projected_dispositions) != expected_dispositions
        or projected_dispositions
        != tuple(
            sorted(
                projected_dispositions,
                key=lambda item: _DISPOSITION_ORDER[item],
            )
        )
    ):
        _fail("successor_provider_projection_order_invalid")
    projected_type_ids = tuple(
        type_id
        for item in projected_variants
        if (type_id := _variant_type_id(item)) is not None
    )
    if (
        projected_type_ids != projection.typed_type_ids
        or projected_type_ids != contract.eligible_type_ids
    ):
        _fail("successor_provider_projection_typed_ids_invalid")
    if sorted(
        sha256_json(item) for item in projected_variants
    ) != sorted(sha256_json(item) for item in canonical_variants):
        _fail("successor_provider_projection_branch_semantics_changed")
    _decision_variants(projected).clear()
    _decision_variants(canonical).clear()
    if projected != canonical:
        _fail("successor_provider_projection_outer_contract_changed")


def _decision_variants(
    response_format: dict[str, Any],
) -> list[dict[str, Any]]:
    try:
        variants = response_format["json_schema"]["schema"][
            "properties"
        ]["decision"]["anyOf"]
    except (KeyError, TypeError) as exc:
        raise (
            Gate2FinancialEvidenceSuccessorProviderProjectionError(
                "successor_provider_projection_schema_shape_invalid"
            )
        ) from exc
    if (
        not isinstance(variants, list)
        or not variants
        or not all(isinstance(item, dict) for item in variants)
    ):
        _fail("successor_provider_projection_schema_shape_invalid")
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
        or values[0] not in DISPOSITIONS
    ):
        _fail("successor_provider_projection_disposition_invalid")
    return str(values[0])


def _variant_type_id(variant: dict[str, Any]) -> str | None:
    disposition = _variant_disposition(variant)
    values = (
        (variant.get("properties") or {})
        .get("input_type_id", {})
        .get("enum")
    )
    if disposition != "typed_input":
        if values is not None:
            _fail("successor_provider_projection_non_typed_id_invalid")
        return None
    if (
        not isinstance(values, list)
        or len(values) != 1
        or not isinstance(values[0], str)
        or not values[0]
    ):
        _fail("successor_provider_projection_typed_id_invalid")
    return values[0]


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceSuccessorProviderProjectionError(code)
