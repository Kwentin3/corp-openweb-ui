"""Published source-semantic port for consumer-owned evidence demands.

Gate 5 owns WHAT evidence is required.  This Gate 3 port owns only contract
acceptance and routing to the existing source-semantic owner; it never reads
Canonical/source artifacts or executes a provider call itself.
"""

from __future__ import annotations

import copy
from typing import Any

from .gate3_financial_label_dictionary import (
    GATE3_DICTIONARY_CURRENT_VERSION,
    Gate3FinancialLabelDictionaryFactory,
)
from .gate3_financial_role_pack import (
    GATE3_ROLE_PACK_CURRENT_VERSION,
    Gate3FinancialRolePackFactory,
)


SOURCE_SEMANTIC_EVIDENCE_DEMAND_SCHEMA_VERSION = (
    "broker_reports_source_fact_demand_v1"
)
GATE3_EVIDENCE_DEMAND_BINDING_SCHEMA_VERSION = (
    "broker_reports_gate3_evidence_demand_binding_v1"
)
FACTORY_REQUIRED = (
    "Gate3EvidenceDemandPortFactory.create is the published consumer-to-source "
    "port and must bind accepted requests to Gate3ChunkBatchLabelingFactory.create"
)
FORBIDDEN = (
    "source or Canonical reads, provider calls, role-profile duplication, "
    "new fact taxonomy, Gate 4 projection, persistence or tax interpretation"
)


class Gate3EvidenceDemandPortError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Gate3EvidenceDemandPortFactory:
    @classmethod
    def create(cls) -> "Gate3EvidenceDemandPort":
        return Gate3EvidenceDemandPort()


class Gate3EvidenceDemandPort:
    def bind(self, requests: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(requests, list) or not all(
            isinstance(item, dict) for item in requests
        ):
            raise Gate3EvidenceDemandPortError(
                "gate3_evidence_demand_requests_invalid"
            )
        dictionary = Gate3FinancialLabelDictionaryFactory.create().load_published(
            GATE3_DICTIONARY_CURRENT_VERSION
        )
        role_pack = Gate3FinancialRolePackFactory.create().load_published(
            GATE3_ROLE_PACK_CURRENT_VERSION
        )
        labels = {item["label_id"] for item in dictionary["labels"]}
        profiles = {item["financial_label"]: item for item in role_pack["profiles"]}
        bindings = [
            _binding(request=request, labels=labels, profiles=profiles)
            for request in requests
        ]
        return {
            "schema_version": GATE3_EVIDENCE_DEMAND_BINDING_SCHEMA_VERSION,
            "status": "demands_bound_to_existing_owner",
            "dictionary_identity": {
                "dictionary_id": dictionary["dictionary_id"],
                "semantic_version": dictionary["semantic_version"],
            },
            "role_pack_identity": {
                "role_pack_id": role_pack["role_pack_id"],
                "semantic_version": role_pack["semantic_version"],
            },
            "bindings": bindings,
            "counts": {
                outcome: sum(item["outcome"] == outcome for item in bindings)
                for outcome in (
                    "BOUND_TO_EXISTING_GATE3_OWNER",
                    "UPSTREAM_FACT_CONTRACT_GAP",
                    "UPSTREAM_ROLE_CONTRACT_MISMATCH",
                )
            },
            "source_or_canonical_read": False,
            "provider_calls": 0,
        }


def _binding(
    *,
    request: dict[str, Any],
    labels: set[str],
    profiles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    required_keys = {
        "schema_version",
        "fact_type",
        "required_roles",
        "required_scope",
        "demand_ids",
        "consumers",
        "consumer_demands",
        "strategy_owner",
        "request_id",
    }
    if (
        set(request) != required_keys
        or request.get("schema_version")
        != SOURCE_SEMANTIC_EVIDENCE_DEMAND_SCHEMA_VERSION
        or not isinstance(request.get("request_id"), str)
        or not request["request_id"].startswith("source_request_")
        or not isinstance(request.get("fact_type"), str)
        or not isinstance(request.get("required_roles"), list)
        or not all(isinstance(item, str) for item in request["required_roles"])
        or request.get("strategy_owner") != "UPSTREAM_SOURCE_SEMANTICS_OWNER"
    ):
        raise Gate3EvidenceDemandPortError("gate3_evidence_demand_request_invalid")
    fact_type = request["fact_type"]
    profile = profiles.get(fact_type)
    base = {
        "request_id": request["request_id"],
        "fact_type": fact_type,
        "consumer_required_roles": sorted(set(request["required_roles"])),
        "demand_ids": copy.deepcopy(request["demand_ids"]),
        "consumers": copy.deepcopy(request["consumers"]),
    }
    if fact_type not in labels or profile is None:
        return {
            **base,
            "outcome": "UPSTREAM_FACT_CONTRACT_GAP",
            "owner_factory": None,
            "owner_required_roles": [],
        }
    owner_roles = [*profile["required_roles"], *profile["optional_roles"]]
    if not set(request["required_roles"]).issubset(owner_roles):
        return {
            **base,
            "outcome": "UPSTREAM_ROLE_CONTRACT_MISMATCH",
            "owner_factory": None,
            "owner_required_roles": copy.deepcopy(profile["required_roles"]),
        }
    return {
        **base,
        "outcome": "BOUND_TO_EXISTING_GATE3_OWNER",
        "owner_factory": "Gate3ChunkBatchLabelingFactory.create",
        "owner_arguments": {"requested_financial_labels": [fact_type]},
        "context_factory": "Gate3StructuralChunkFactory.create",
        "role_context_factory": "Gate3RoleContextFactory.create_from_accepted_facts",
        "owner_required_roles": copy.deepcopy(profile["required_roles"]),
        "owner_optional_roles": copy.deepcopy(profile["optional_roles"]),
        "source_strategy_selected_by_gate5": False,
    }


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_EVIDENCE_DEMAND_BINDING_SCHEMA_VERSION",
    "SOURCE_SEMANTIC_EVIDENCE_DEMAND_SCHEMA_VERSION",
    "Gate3EvidenceDemandPort",
    "Gate3EvidenceDemandPortError",
    "Gate3EvidenceDemandPortFactory",
]
