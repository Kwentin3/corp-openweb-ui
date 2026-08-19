"""Consumer-owned evidence demands that never read or re-extract source data."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .gate3_evidence_demand_port import (
    SOURCE_SEMANTIC_EVIDENCE_DEMAND_SCHEMA_VERSION,
)


GATE5_EVIDENCE_DEMAND_COLLECTION_SCHEMA_VERSION = (
    "broker_reports_gate5_evidence_demand_collection_v2"
)
GATE5_EVIDENCE_DEMAND_SCHEMA_VERSION = "broker_reports_gate5_evidence_demand_v2"
GATE5_SOURCE_OWNER_REQUEST_SCHEMA_VERSION = (
    SOURCE_SEMANTIC_EVIDENCE_DEMAND_SCHEMA_VERSION
)

METHODOLOGY_DRIVEN_EVIDENCE_DEMAND_PROVEN = "METHODOLOGY_DRIVEN_EVIDENCE_DEMAND_PROVEN"
EVIDENCE_DEMAND_IS_REQUEST_NOT_READER = "EVIDENCE_DEMAND_IS_REQUEST_NOT_READER"
PREMATURE_GAP_DECLARATION_ELIMINATED = "PREMATURE_GAP_DECLARATION_ELIMINATED"
EVIDENCE_AUTHORITY_ROUTING_PROVEN = "EVIDENCE_AUTHORITY_ROUTING_PROVEN"

FACTORY_REQUIRED = (
    "Gate5EvidenceDemandRuntimeFactory.create is the only Evidence Demand "
    "classification and upstream source-request constructor",
)
FORBIDDEN = (
    "Canonical or source reads, provider calls, extraction strategy selection, "
    "source mutation, tax consequence assignment, inferred roles, generic "
    "semantic harvest, financial-event relations, reconciliation or persistence",
)

EVIDENCE_CLASSIFICATIONS = frozenset(
    {
        "FACT_AVAILABLE",
        "SOURCE_OWNER_REQUESTED",
        "SOURCE_FACT_CONTRACT_MISSING",
        "USER_CASE_FACT_REQUIRED",
        "EXTERNAL_REFERENCE_FACT_REQUIRED",
        "METHODOLOGY_UNRESOLVED",
    }
)
PREFERRED_AUTHORITIES = frozenset(
    {"SOURCE_DOCUMENT", "USER_CASE", "EXTERNAL_REFERENCE", "MIXED"}
)
ABSENCE_EFFECTS = frozenset({"BLOCKS", "ADVISORY", "CONDITIONAL"})
AUDIT_CAUSES = frozenset({"NONE", "DEMAND_DISCOVERED_CONTRACT_GAP", "NOT_SOURCE_LOSS"})


class Gate5EvidenceDemandError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Gate5EvidenceDemandRuntimeFactory:
    @classmethod
    def create(cls) -> "Gate5EvidenceDemandRuntime":
        return Gate5EvidenceDemandRuntime()


class Gate5EvidenceDemandRuntime:
    def evaluate(
        self,
        *,
        active_demands: list[str],
        methodology: dict[str, Any],
        evidence_contract: dict[str, Any],
        normalized_facts: list[dict[str, Any]],
        user_case_facts: list[dict[str, Any]] | None = None,
        external_reference_facts: list[dict[str, Any]] | None = None,
        methodology_results: list[dict[str, Any]] | None = None,
        client_requirements: list[dict[str, Any]] | None = None,
        active_rule_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        active = _validated_active_demands(active_demands)
        contracts = _validated_contract(evidence_contract)
        requirements = _methodology_requirements(
            active_demands=active,
            methodology=methodology,
            contracts=contracts,
            active_rule_ids=active_rule_ids,
        )
        requirements.extend(_validated_client_requirements(client_requirements or []))
        requirements = _merged_requirements(requirements)
        normalized = _validated_fact_list(normalized_facts, "normalized_facts")
        user = _validated_fact_list(user_case_facts or [], "user_case_facts")
        external = _validated_fact_list(
            external_reference_facts or [], "external_reference_facts"
        )
        method_results = _validated_fact_list(
            methodology_results or [], "methodology_results"
        )

        rows = [
            _evidence_row(
                requirement=requirement,
                normalized_facts=normalized,
                user_case_facts=user,
                external_reference_facts=external,
                methodology_results=method_results,
            )
            for requirement in requirements
        ]
        source_requests = _source_owner_requests(rows)
        classification_counts = {
            classification: sum(
                item["classification"] == classification for item in rows
            )
            for classification in sorted(EVIDENCE_CLASSIFICATIONS)
        }
        audit_counts = {
            cause: sum(item["audit_cause"] == cause for item in rows)
            for cause in sorted(AUDIT_CAUSES)
        }
        return {
            "schema_version": GATE5_EVIDENCE_DEMAND_COLLECTION_SCHEMA_VERSION,
            "status": "evidence_demands_classified",
            "terminals": [
                METHODOLOGY_DRIVEN_EVIDENCE_DEMAND_PROVEN,
                EVIDENCE_DEMAND_IS_REQUEST_NOT_READER,
                PREMATURE_GAP_DECLARATION_ELIMINATED,
                EVIDENCE_AUTHORITY_ROUTING_PROVEN,
            ],
            "active_demands": active,
            "active_rule_ids": sorted(set(active_rule_ids or [])),
            "evidence_demands": rows,
            "source_owner_requests": source_requests,
            "authority_search_order": [
                "EXISTING_NORMALIZED_FACTS",
                "UPSTREAM_SOURCE_SEMANTICS_OWNER",
                "AUTHORITATIVE_EXTERNAL_REFERENCE_WHEN_ALLOWED",
                "USER_OR_ADDITIONAL_DOCUMENT_LAST",
            ],
            "metrics": {
                "requirements": len(rows),
                "named_consumers": sum(bool(item["consumers"]) for item in rows),
                "classification_counts": classification_counts,
                "demand_discovered_contract_gap": audit_counts[
                    "DEMAND_DISCOVERED_CONTRACT_GAP"
                ],
                "source_owner_requests": len(source_requests),
                "source_documents_read": 0,
                "provider_calls": 0,
                "invented_facts": 0,
                "invented_relations": 0,
            },
            "source_or_canonical_read": False,
            "ingestion_rerun": False,
            "source_bytes_read": False,
            "persistence": "none_new",
        }


def _methodology_requirements(
    *,
    active_demands: list[str],
    methodology: dict[str, Any],
    contracts: dict[str, dict[str, Any]],
    active_rule_ids: list[str] | None,
) -> list[dict[str, Any]]:
    if not isinstance(methodology, dict):
        _fail("gate5_evidence_methodology_invalid")
    rules = methodology.get("rules")
    bindings = methodology.get("demand_bindings")
    if not isinstance(rules, list) or not isinstance(bindings, list):
        _fail("gate5_evidence_methodology_invalid")
    rules_by_id: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if (
            not isinstance(rule, dict)
            or not isinstance(rule.get("rule_id"), str)
            or not isinstance(rule.get("required_inputs"), list)
            or not isinstance(rule.get("output"), str)
        ):
            _fail("gate5_evidence_methodology_rule_invalid")
        rules_by_id[rule["rule_id"]] = rule
    result: list[dict[str, Any]] = []
    active = set(active_demands)
    active_rules = set(active_rule_ids) if active_rule_ids is not None else None
    for binding in bindings:
        if (
            not isinstance(binding, dict)
            or binding.get("demand") not in active
            or not isinstance(binding.get("owner"), str)
            or not isinstance(binding.get("rule_ids"), list)
        ):
            continue
        for rule_id in binding["rule_ids"]:
            if active_rules is not None and rule_id not in active_rules:
                continue
            rule = rules_by_id.get(rule_id)
            if rule is None:
                _fail("gate5_evidence_methodology_binding_invalid")
            for required in rule["required_inputs"]:
                input_id, inline_contract = _required_input(required)
                contract = inline_contract or contracts.get(input_id)
                if contract is None:
                    contract = _missing_contract(input_id)
                result.append(
                    {
                        "required_input": input_id,
                        "consumers": [binding["owner"]],
                        "consumer_demands": [binding["demand"]],
                        "rule_ids": [rule_id],
                        "why_required": (
                            f"{rule_id} requires {input_id} to produce {rule['output']}"
                        ),
                        "contract": copy.deepcopy(contract),
                        "producer_kind": "ACTIVE_TAX_METHODOLOGY",
                    }
                )
    return result


def _required_input(value: Any) -> tuple[str, dict[str, Any] | None]:
    if isinstance(value, str) and value:
        return value, None
    if (
        isinstance(value, dict)
        and set(value) == {"input_id", "evidence_contract"}
        and isinstance(value.get("input_id"), str)
        and value["input_id"]
        and isinstance(value.get("evidence_contract"), dict)
    ):
        return value["input_id"], _validated_contract_item(
            value["evidence_contract"], expected_input=value["input_id"]
        )
    _fail("gate5_evidence_required_input_invalid")


def _validated_contract(value: Any) -> dict[str, dict[str, Any]]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version")
        != "broker_reports_gate5_evidence_demand_contract_v2"
        or not isinstance(value.get("fact_contracts"), list)
    ):
        _fail("gate5_evidence_contract_invalid")
    result: dict[str, dict[str, Any]] = {}
    for item in value["fact_contracts"]:
        validated = _validated_contract_item(item)
        required_input = validated["required_input"]
        if required_input in result:
            _fail("gate5_evidence_contract_duplicate")
        result[required_input] = validated
    return result


def _validated_contract_item(
    value: Any, *, expected_input: str | None = None
) -> dict[str, Any]:
    required_keys = {
        "required_input",
        "fact_meaning",
        "fact_role",
        "preferred_authority",
        "required_scope",
        "granularity",
        "cardinality",
        "absence_effect",
        "normalized_fact_contracts",
        "source_fact_request",
        "fallback_authority",
        "fact_key",
        "methodology_result_key",
    }
    if not isinstance(value, dict) or set(value) != required_keys:
        _fail("gate5_evidence_contract_item_invalid")
    if (
        not isinstance(value.get("required_input"), str)
        or not value["required_input"]
        or (expected_input is not None and value["required_input"] != expected_input)
        or not isinstance(value.get("fact_meaning"), str)
        or not value["fact_meaning"]
        or not isinstance(value.get("fact_role"), str)
        or not value["fact_role"]
        or value.get("preferred_authority") not in PREFERRED_AUTHORITIES
        or value.get("absence_effect") not in ABSENCE_EFFECTS
        or not isinstance(value.get("required_scope"), str)
        or not value["required_scope"]
        or not isinstance(value.get("granularity"), str)
        or not value["granularity"]
        or not isinstance(value.get("cardinality"), str)
        or not value["cardinality"]
        or not isinstance(value.get("normalized_fact_contracts"), list)
        or value.get("fallback_authority")
        not in {None, "USER_CASE", "EXTERNAL_REFERENCE", "ADDITIONAL_DOCUMENT"}
        or value.get("fact_key") is not None
        and not isinstance(value.get("fact_key"), str)
        or value.get("methodology_result_key") is not None
        and not isinstance(value.get("methodology_result_key"), str)
    ):
        _fail("gate5_evidence_contract_item_invalid")
    for selector in value["normalized_fact_contracts"]:
        _validate_selector(selector)
    source_request = value.get("source_fact_request")
    if source_request is not None:
        if (
            not isinstance(source_request, dict)
            or set(source_request)
            != {
                "fact_type",
                "explicit_role_labels",
                "allowed_source_structures",
                "source_ceiling",
            }
            or not isinstance(source_request.get("fact_type"), str)
            or not source_request["fact_type"]
            or not isinstance(source_request.get("explicit_role_labels"), list)
            or not source_request["explicit_role_labels"]
            or not all(
                isinstance(item, str) and item.strip()
                for item in source_request["explicit_role_labels"]
            )
            or not isinstance(source_request.get("allowed_source_structures"), list)
            or not source_request["allowed_source_structures"]
            or source_request.get("source_ceiling") != "EXPLICIT_ROLE_LITERAL_ONLY"
        ):
            _fail("gate5_evidence_source_fact_request_invalid")
    return copy.deepcopy(value)


def _validate_selector(selector: Any) -> None:
    if (
        not isinstance(selector, dict)
        or set(selector) != {"fact_type", "required_roles"}
        or not isinstance(selector.get("fact_type"), str)
        or not selector["fact_type"]
        or not isinstance(selector.get("required_roles"), list)
        or not all(
            isinstance(item, str) and item for item in selector["required_roles"]
        )
    ):
        _fail("gate5_evidence_contract_selector_invalid")


def _missing_contract(required_input: str) -> dict[str, Any]:
    return {
        "required_input": required_input,
        "fact_meaning": required_input,
        "fact_role": required_input,
        "preferred_authority": "SOURCE_DOCUMENT",
        "required_scope": "active_consumer_scope",
        "granularity": "unspecified",
        "cardinality": "unspecified",
        "absence_effect": "BLOCKS",
        "normalized_fact_contracts": [],
        "source_fact_request": None,
        "fallback_authority": None,
        "fact_key": None,
        "methodology_result_key": None,
        "contract_missing": True,
    }


def _validated_client_requirements(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item)
            != {
                "required_input",
                "consumer",
                "consumer_demands",
                "why_required",
                "evidence_contract",
            }
            or not isinstance(item.get("consumer"), str)
            or not isinstance(item.get("consumer_demands"), list)
            or not all(isinstance(entry, str) for entry in item["consumer_demands"])
        ):
            _fail("gate5_evidence_client_requirement_invalid")
        contract = _validated_contract_item(
            item["evidence_contract"], expected_input=item["required_input"]
        )
        result.append(
            {
                "required_input": item["required_input"],
                "consumers": [item["consumer"]],
                "consumer_demands": sorted(set(item["consumer_demands"])),
                "rule_ids": [],
                "why_required": item["why_required"],
                "contract": contract,
                "producer_kind": "CLIENT_REVIEW_REQUIREMENT",
            }
        )
    return result


def _merged_requirements(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in value:
        key = item["required_input"]
        existing = result.get(key)
        if existing is None:
            result[key] = copy.deepcopy(item)
            continue
        if existing["contract"] != item["contract"]:
            _fail("gate5_evidence_contract_conflict")
        for field in ("consumers", "consumer_demands", "rule_ids"):
            existing[field] = sorted(set([*existing[field], *item[field]]))
        existing["why_required"] = "; ".join(
            sorted(set([existing["why_required"], item["why_required"]]))
        )
        if existing["producer_kind"] != item["producer_kind"]:
            existing["producer_kind"] = "METHODOLOGY_AND_CLIENT_REVIEW"
    return [copy.deepcopy(result[key]) for key in sorted(result)]


def _evidence_row(
    *,
    requirement: dict[str, Any],
    normalized_facts: list[dict[str, Any]],
    user_case_facts: list[dict[str, Any]],
    external_reference_facts: list[dict[str, Any]],
    methodology_results: list[dict[str, Any]],
) -> dict[str, Any]:
    contract = requirement["contract"]
    demand_base = {
        "schema_version": GATE5_EVIDENCE_DEMAND_SCHEMA_VERSION,
        "required_input": requirement["required_input"],
        "fact_meaning": contract["fact_meaning"],
        "fact_role": contract["fact_role"],
        "consumers": sorted(requirement["consumers"]),
        "consumer_demands": sorted(requirement["consumer_demands"]),
        "rule_ids": sorted(requirement["rule_ids"]),
        "why_required": requirement["why_required"],
        "preferred_authority": contract["preferred_authority"],
        "required_scope": contract["required_scope"],
        "granularity": contract["granularity"],
        "cardinality": contract["cardinality"],
        "absence_effect": contract["absence_effect"],
        "fallback_authority": contract["fallback_authority"],
        "normalized_fact_contracts": copy.deepcopy(
            contract["normalized_fact_contracts"]
        ),
        "source_fact_request_contract": copy.deepcopy(contract["source_fact_request"]),
        "producer_kind": requirement["producer_kind"],
    }
    demand_id = "g5demand_" + _sha256(demand_base)[:32]
    normalized_matches, normalized_satisfies = _normalized_satisfaction(
        normalized_facts,
        contract["normalized_fact_contracts"],
        cardinality=contract["cardinality"],
    )
    classification = "SOURCE_FACT_CONTRACT_MISSING"
    audit_cause = "DEMAND_DISCOVERED_CONTRACT_GAP"
    satisfying: list[dict[str, Any]] = []
    if normalized_satisfies:
        classification, audit_cause, satisfying = (
            "FACT_AVAILABLE",
            "NONE",
            normalized_matches,
        )
    elif contract.get("fact_key") and _matching_keyed_fact(
        user_case_facts, contract["fact_key"]
    ):
        classification, audit_cause = "FACT_AVAILABLE", "NONE"
        satisfying = _matching_keyed_fact(user_case_facts, contract["fact_key"])
    elif contract.get("methodology_result_key") and _matching_keyed_fact(
        methodology_results, contract["methodology_result_key"]
    ):
        classification, audit_cause = "FACT_AVAILABLE", "NOT_SOURCE_LOSS"
        satisfying = _matching_keyed_fact(
            methodology_results, contract["methodology_result_key"]
        )
    elif contract["preferred_authority"] == "USER_CASE":
        classification, audit_cause = "USER_CASE_FACT_REQUIRED", "NOT_SOURCE_LOSS"
    elif contract["preferred_authority"] == "EXTERNAL_REFERENCE":
        satisfying = _matching_keyed_fact(
            external_reference_facts,
            contract.get("fact_key") or requirement["required_input"],
        )
        classification = (
            "FACT_AVAILABLE" if satisfying else "EXTERNAL_REFERENCE_FACT_REQUIRED"
        )
        audit_cause = "NOT_SOURCE_LOSS"
    elif contract.get("methodology_result_key"):
        classification, audit_cause = "METHODOLOGY_UNRESOLVED", "NOT_SOURCE_LOSS"
    elif contract["normalized_fact_contracts"] or contract["source_fact_request"]:
        classification, audit_cause = "SOURCE_OWNER_REQUESTED", "NONE"
    return {
        **demand_base,
        "demand_id": demand_id,
        "classification": classification,
        "audit_cause": audit_cause,
        "existing_normalized_satisfies": normalized_satisfies,
        "satisfying_fact_ids": _fact_ids(satisfying),
        "search_receipt": {
            "normalized_facts_checked": True,
            "source_owner_request_emitted": classification == "SOURCE_OWNER_REQUESTED",
            "source_or_canonical_read_by_gate5": False,
            "provider_called_by_gate5": False,
            "external_reference_routed": classification
            == "EXTERNAL_REFERENCE_FACT_REQUIRED",
            "user_case_routed": classification == "USER_CASE_FACT_REQUIRED",
        },
    }


def _source_owner_requests(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Gate 5 owns WHAT is required. It must not read Canonical/source artifacts
    # or select chunks/providers; recovery routes through the published Gate 3 port.
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["classification"] != "SOURCE_OWNER_REQUESTED":
            continue
        candidates = copy.deepcopy(row["normalized_fact_contracts"])
        source_request = row.get("source_fact_request_contract")
        if source_request is not None:
            candidates.append(
                {
                    "fact_type": source_request["fact_type"],
                    "required_roles": ["value"],
                }
            )
        for candidate in candidates:
            key = _sha256(
                {
                    "fact_type": candidate["fact_type"],
                    "required_roles": sorted(candidate["required_roles"]),
                    "required_scope": row["required_scope"],
                }
            )
            existing = grouped.get(key)
            if existing is None:
                base = {
                    "schema_version": GATE5_SOURCE_OWNER_REQUEST_SCHEMA_VERSION,
                    "fact_type": candidate["fact_type"],
                    "required_roles": sorted(candidate["required_roles"]),
                    "required_scope": row["required_scope"],
                    "demand_ids": [row["demand_id"]],
                    "consumers": copy.deepcopy(row["consumers"]),
                    "consumer_demands": copy.deepcopy(row["consumer_demands"]),
                    "strategy_owner": "UPSTREAM_SOURCE_SEMANTICS_OWNER",
                }
                base["request_id"] = "source_request_" + _sha256(base)[:32]
                grouped[key] = base
                continue
            existing["demand_ids"] = sorted(
                set([*existing["demand_ids"], row["demand_id"]])
            )
            existing["consumers"] = sorted(
                set([*existing["consumers"], *row["consumers"]])
            )
            existing["consumer_demands"] = sorted(
                set([*existing["consumer_demands"], *row["consumer_demands"]])
            )
            material = {
                key: value for key, value in existing.items() if key != "request_id"
            }
            existing["request_id"] = "source_request_" + _sha256(material)[:32]
    return [copy.deepcopy(grouped[key]) for key in sorted(grouped)]


def _normalized_satisfaction(
    facts: list[dict[str, Any]],
    selectors: list[dict[str, Any]],
    *,
    cardinality: str,
) -> tuple[list[dict[str, Any]], bool]:
    result: list[dict[str, Any]] = []
    applicable_by_type: dict[str, list[dict[str, Any]]] = {}
    for fact in facts:
        fact_type = fact.get("fact_type") or fact.get("financial_type")
        for selector in selectors:
            if fact_type != selector["fact_type"]:
                continue
            applicable_by_type.setdefault(fact_type, []).append(fact)
            roles = {
                item.get("role")
                for item in fact.get("roles") or []
                if item.get("status") == "value"
            }
            if set(selector["required_roles"]).issubset(roles):
                result.append(fact)
                break
    if not result:
        return [], False
    if cardinality != "per applicable observation":
        return copy.deepcopy(result), True
    matched_ids = {id(item) for item in result}
    all_applicable = [item for values in applicable_by_type.values() for item in values]
    return copy.deepcopy(result), all(
        id(item) in matched_ids for item in all_applicable
    )


def _matching_keyed_fact(facts: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [
        copy.deepcopy(item)
        for item in facts
        if item.get("fact_key") == key
        or item.get("fact_type") == key
        or item.get("result_key") == key
    ]


def _fact_ids(facts: list[dict[str, Any]]) -> list[str]:
    return sorted(
        {
            str(
                item.get("fact_id")
                or item.get("request_id")
                or item.get("result_id")
                or ("evidence_" + _sha256(item)[:24])
            )
            for item in facts
        }
    )


def _validated_active_demands(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        _fail("gate5_evidence_active_demands_invalid")
    return sorted(set(value))


def _validated_fact_list(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        _fail(f"gate5_evidence_{field}_invalid")
    return copy.deepcopy(value)


def _sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _fail(code: str) -> None:
    raise Gate5EvidenceDemandError(code)


__all__ = [
    "ABSENCE_EFFECTS",
    "AUDIT_CAUSES",
    "EVIDENCE_AUTHORITY_ROUTING_PROVEN",
    "EVIDENCE_CLASSIFICATIONS",
    "EVIDENCE_DEMAND_IS_REQUEST_NOT_READER",
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_EVIDENCE_DEMAND_COLLECTION_SCHEMA_VERSION",
    "GATE5_EVIDENCE_DEMAND_SCHEMA_VERSION",
    "GATE5_SOURCE_OWNER_REQUEST_SCHEMA_VERSION",
    "METHODOLOGY_DRIVEN_EVIDENCE_DEMAND_PROVEN",
    "PREFERRED_AUTHORITIES",
    "PREMATURE_GAP_DECLARATION_ELIMINATED",
    "Gate5EvidenceDemandError",
    "Gate5EvidenceDemandRuntime",
    "Gate5EvidenceDemandRuntimeFactory",
]
