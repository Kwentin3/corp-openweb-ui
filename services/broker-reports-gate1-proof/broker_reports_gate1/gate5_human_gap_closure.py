"""Exact, minimal human or document actions for deterministic case gaps."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from .gate5_evidence_intake import (
    GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION,
)
from .gate5_client_evidence_review import (
    GATE5_CLIENT_EVIDENCE_REVIEW_SCHEMA_VERSION,
)
from .gate5_declaration_scope_resolution import (
    GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION,
)
from .gate5_residency_evidence import (
    GATE5_RESIDENCY_CLASSIFICATION_SCHEMA_VERSION,
    GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
    Gate5ResidencyEvidenceRuntimeFactory,
)


GATE5_HUMAN_GAP_CLOSURE_SCHEMA_VERSION = "broker_reports_gate5_human_gap_closure_v0"
GATE5_GAP_REQUEST_SCHEMA_VERSION = "broker_reports_gate5_gap_request_v0"
GATE5_USER_CASE_FACT_SCHEMA_VERSION = "broker_reports_gate5_user_case_fact_v0"
GATE5_HUMAN_GAP_CLOSURE_TERMINAL = "HUMAN_GAP_CLOSURE_LOOP_PROVEN"

FACTORY_REQUIRED = (
    "Gate5HumanGapClosureRuntimeFactory.create consumes only typed intake, "
    "scoped declaration demands and deterministic client findings",
)
FORBIDDEN = (
    "raw transaction prompt, LLM blocker closure, inferred answer, tax "
    "calculation, methodology mutation, source-document fact fabrication, "
    "universal questionnaire or continuation of stale LLM reasoning",
)

_USER_FACT_KEYS = frozenset({"schema_version", "fact_key", "value", "provenance"})
_KNOWN_FACT_KEYS = {
    "taxpayer_identity_confirmed",
    "filing_instance_identity",
    "signer_and_representation",
    "budget_disposition",
    "residency_evidence",
}
_CLOSURE_TYPES = {
    "EXISTING_EVIDENCE",
    "EXTERNAL_AUTHORITY",
    "USER_FACT",
    "ADDITIONAL_DOCUMENT",
    "METHODOLOGY_RESEARCH",
    "OWNER_UNRESOLVED",
}
_USER_FACING_CLOSURE_TYPES = {"USER_FACT", "ADDITIONAL_DOCUMENT"}


class Gate5HumanGapClosureError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class Gate5HumanGapClosureRuntimeFactory:
    @classmethod
    def create(cls) -> "Gate5HumanGapClosureRuntime":
        return Gate5HumanGapClosureRuntime()


_IDENTITY_METADATA_FACT_TYPES = {
    "PARTY_NAME",
    "PERSON_BIRTH_DATE",
    "PERSON_CITIZENSHIP",
    "TAXPAYER_TAX_IDENTIFIER",
}


class Gate5HumanGapClosureRuntime:
    def plan(
        self,
        *,
        intake: dict[str, Any],
        scope_activation: dict[str, Any],
        client_review: dict[str, Any],
        user_case_facts: list[dict[str, Any]],
        residency_classification: dict[str, Any],
    ) -> dict[str, Any]:
        _validate_inputs(
            intake=intake,
            scope_activation=scope_activation,
            client_review=client_review,
        )
        facts = _validated_user_facts(user_case_facts)
        if (
            not isinstance(residency_classification, dict)
            or residency_classification.get("schema_version")
            != GATE5_RESIDENCY_CLASSIFICATION_SCHEMA_VERSION
        ):
            _fail("gate5_gap_residency_classification_invalid")
        facts_by_key = {item["fact_key"]: item for item in facts}
        known_document_facts_reused = sum(
            item.get("fact_type") in _IDENTITY_METADATA_FACT_TYPES
            for item in intake.get("metadata_facts", [])
        )
        requests: list[dict[str, Any]] = []
        requests.extend(_source_requests(client_review))
        requests.extend(
            _declaration_requests(
                intake=intake,
                scope_activation=scope_activation,
                facts_by_key=facts_by_key,
                source_requests=requests,
                residency_classification=residency_classification,
            )
        )
        requests = _deduplicated_requests(requests)
        required = [item for item in requests if item["kind"] == "REQUIRED"]
        advisory = [item for item in requests if item["kind"] == "ADVISORY"]
        deferred = [item for item in requests if item["kind"] == "DEFERRED"]
        user_required = [
            item
            for item in required
            if item["closure_type"] in _USER_FACING_CLOSURE_TYPES
        ]
        internal_required = [
            item
            for item in required
            if item["closure_type"] not in _USER_FACING_CLOSURE_TYPES
        ]
        user_advisory = [
            item
            for item in advisory
            if item["closure_type"] in _USER_FACING_CLOSURE_TYPES
        ]
        internal_advisory = [
            item
            for item in advisory
            if item["closure_type"] not in _USER_FACING_CLOSURE_TYPES
        ]
        return {
            "schema_version": GATE5_HUMAN_GAP_CLOSURE_SCHEMA_VERSION,
            "status": "exact_gap_actions_ready",
            "terminals": [GATE5_HUMAN_GAP_CLOSURE_TERMINAL],
            "required_actions": copy.deepcopy(required),
            "advisory_actions": copy.deepcopy(advisory),
            "deferred_actions": copy.deepcopy(deferred),
            "user_facing_required_actions": copy.deepcopy(user_required),
            "internal_owner_required_actions": copy.deepcopy(internal_required),
            "user_facing_advisory_actions": copy.deepcopy(user_advisory),
            "internal_owner_advisory_actions": copy.deepcopy(internal_advisory),
            "known_user_case_facts": copy.deepcopy(facts),
            "search_order": [
                "NORMALIZED_DOCUMENT_FACTS",
                "INTERNAL_SOURCE_OWNER_REVIEW",
                "DOCUMENT_METADATA",
                "OTHER_SUPPLIED_DOCUMENTS",
                "AUTHORITATIVE_EXTERNAL_REFERENCES",
                "USER_OR_ADDITIONAL_DOCUMENT",
            ],
            "llm_adapter_input": {
                "schema_version": "broker_reports_gate5_gap_dialog_adapter_input_v0",
                "required_actions": [
                    _adapter_request(item) for item in user_required
                ],
                "advisory_actions": [
                    _adapter_request(item) for item in user_advisory
                ],
                "internal_owner_action_count": (
                    len(internal_required) + len(internal_advisory)
                ),
                "raw_transactions_supplied": False,
                "may_close_by_assumption": False,
                "calculation_authority": False,
            },
            "replay_contract": {
                "entrypoint": "Gate5DeclarationPreparationRuntimeFactory.create",
                "new_document_route": "ordinary normalization path through Gate 1 to Gate 4",
                "new_user_fact_route": "validated typed user/case fact input",
                "reuse_previous_llm_reasoning_as_authority": False,
            },
            "residency_classification": copy.deepcopy(residency_classification),
            "metrics": {
                "required_actions": len(required),
                "user_facing_required_actions": len(user_required),
                "internal_owner_required_actions": len(internal_required),
                "advisory_actions": len(advisory),
                "deferred_actions": len(deferred),
                "already_known_not_asked": len(facts),
                "known_document_facts_reused": known_document_facts_reused,
                "invented_facts": 0,
                "invented_relations": 0,
            },
        }

    def normalize_answer(
        self, *, request: dict[str, Any], answer: dict[str, Any]
    ) -> dict[str, Any]:
        validated = _validated_request(request)
        if not isinstance(answer, dict) or set(answer) != {"kind", "value"}:
            _fail("gate5_gap_answer_invalid")
        if validated["closure_type"] == "ADDITIONAL_DOCUMENT":
            if (
                answer.get("kind") != "document_submission"
                or answer.get("value") is not True
            ):
                _fail("gate5_gap_document_answer_invalid")
            return {
                "status": "NORMALIZATION_REQUIRED",
                "request_id": validated["request_id"],
                "typed_user_case_fact": None,
                "route": "ordinary normalization path through Gate 1 to Gate 4",
            }
        if validated["closure_type"] != "USER_FACT":
            _fail("gate5_gap_answer_not_user_fact")
        expected = validated["answer_contract"]
        if answer.get("kind") != expected["kind"]:
            _fail("gate5_gap_answer_kind_invalid")
        value = copy.deepcopy(answer["value"])
        if expected["kind"] == "residency_evidence":
            if not isinstance(value, dict) or set(value) != {
                "human_answer",
                "proposal",
            }:
                _fail("gate5_gap_answer_value_invalid")
            value = (
                Gate5ResidencyEvidenceRuntimeFactory.create().normalize_human_answer(
                    human_answer=value["human_answer"],
                    proposal=value["proposal"],
                    source_ref=validated["request_id"],
                )
            )
        if expected["kind"] == "confirmation" and not isinstance(value, bool):
            _fail("gate5_gap_answer_value_invalid")
        if expected["kind"] in {"text", "code"} and (
            not isinstance(value, str) or not value.strip() or len(value) > 512
        ):
            _fail("gate5_gap_answer_value_invalid")
        if expected.get("allowed") and value not in expected["allowed"]:
            _fail("gate5_gap_answer_value_invalid")
        fact = {
            "schema_version": GATE5_USER_CASE_FACT_SCHEMA_VERSION,
            "fact_key": validated["fact_key"],
            "value": {"kind": expected["kind"], "value": value},
            "provenance": {
                "source_kind": "authenticated_user_case_fact",
                "request_id": validated["request_id"],
                "calculation_authority": False,
                "document_source_fact": False,
            },
        }
        _validated_user_facts([fact])
        return {
            "status": "TYPED_USER_CASE_FACT_READY",
            "request_id": validated["request_id"],
            "typed_user_case_fact": fact,
            "route": "deterministic case replay",
        }

    def validate_user_case_facts(
        self, value: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return _validated_user_facts(value)


def _source_requests(review: dict[str, Any]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for finding in review["required_blockers"]:
        subject = finding["subject"]
        routing = _validated_routing(finding.get("routing"))
        if finding["closure_type"] != routing["closure_type"]:
            _fail("gate5_gap_owner_routing_invalid")
        group_key = (
            finding["closure_type"],
            finding["reason_code"],
            routing["route"],
            routing["owner"],
            subject.get("asset"),
            subject.get("currency"),
        )
        grouped.setdefault(group_key, []).append(finding)
    for group in grouped.values():
        first = group[0]
        quantitative = first["quantitative_gap"]
        minimum_gap = quantitative.get("minimum_missing_quantity")
        subject = first["subject"]
        routing = _validated_routing(first.get("routing"))
        if routing["user_or_additional_document_allowed"]:
            if first["closure_type"] != "ADDITIONAL_DOCUMENT":
                _fail("gate5_gap_external_route_invalid")
        elif first["closure_type"] in _USER_FACING_CLOSURE_TYPES:
            _fail("gate5_gap_internal_route_exposed_to_user")
        if minimum_gap is not None and first["closure_type"] == "ADDITIONAL_DOCUMENT":
            prompt = (
                "A disposal is documented, but acquisition evidence covers less "
                "than the required quantity. Please provide an earlier broker "
                f"statement or other acquisition document for at least {minimum_gap} "
                "additional units of the exact instrument and currency."
            )
            answer_contract = {"kind": "document_submission"}
        elif first["closure_type"] == "ADDITIONAL_DOCUMENT":
            prompt = (
                "The supplied source fact cannot satisfy the deterministic tax "
                f"input because {first['reason_code']}. Please provide the specific "
                "source document described in helpful_evidence."
            )
            answer_contract = {"kind": "document_submission"}
        elif first["closure_type"] == "EXISTING_EVIDENCE":
            prompt = (
                f"Internal action {routing['route']}: replay the existing source "
                f"through {routing['owner']}; do not ask the user for evidence."
            )
            answer_contract = {
                "kind": "owner_replay",
                "owner": routing["owner"],
            }
        elif first["closure_type"] == "METHODOLOGY_RESEARCH":
            prompt = (
                "Internal methodology action: resolve the published-methodology "
                "gap through its existing authority; do not ask the user."
            )
            answer_contract = {
                "kind": "methodology_review",
                "owner": routing["owner"],
            }
        elif first["closure_type"] == "EXTERNAL_AUTHORITY":
            prompt = (
                "External-authority action: resolve the authoritative reference "
                "through its existing owner; do not ask the user to restate it."
            )
            answer_contract = {
                "kind": "external_authority_review",
                "owner": routing["owner"],
            }
        else:
            prompt = (
                "Internal ownership is unresolved. Stop and assign an explicit "
                "owner; do not ask the user for another document."
            )
            answer_contract = {"kind": "owner_resolution"}
        requests.append(
            _request(
                kind="REQUIRED",
                priority="HIGH",
                closure_type=first["closure_type"],
                fact_key=None,
                demand_refs=sorted(
                    {
                        demand
                        for finding in group
                        for demand in finding["consumer_demands"]
                    }
                ),
                evidence_refs=sorted(finding["finding_id"] for finding in group),
                question=prompt,
                reason=first["why"],
                helpful_evidence=first["helpful_evidence"],
                client_benefit=first["client_benefit_rationale"],
                answer_contract=answer_contract,
                subject=subject,
                routing=routing,
            )
        )
    for finding in review["advisory_findings"]:
        requests.append(
            _request(
                kind="ADVISORY",
                priority=finding["priority"],
                closure_type=finding["closure_type"],
                fact_key=None,
                demand_refs=finding["consumer_demands"],
                evidence_refs=[finding["finding_id"]],
                question=(
                    "If available, provide the additional document described in "
                    "helpful_evidence; this is recommended and does not become a "
                    "hard blocker by itself."
                ),
                reason=finding["why"],
                helpful_evidence=finding["helpful_evidence"],
                client_benefit=finding["client_benefit_rationale"],
                answer_contract={"kind": "document_submission"},
                subject=finding["subject"],
            )
        )
    return requests


def _declaration_requests(
    *,
    intake: dict[str, Any],
    scope_activation: dict[str, Any],
    facts_by_key: dict[str, dict[str, Any]],
    source_requests: list[dict[str, Any]],
    residency_classification: dict[str, Any],
) -> list[dict[str, Any]]:
    active = {item["demand"] for item in scope_activation["active_demands"]}
    metadata = intake["metadata_facts"]
    requests: list[dict[str, Any]] = []
    filing_demands = {
        "obl_filing_instance_identity",
        "obl_taxpayer_identity_and_period_status",
        "obl_signer_and_representation_authority",
    }
    if active & filing_demands:
        party_facts = [
            item
            for item in metadata
            if item["fact_type"] in _IDENTITY_METADATA_FACT_TYPES
        ]
        if "taxpayer_identity_confirmed" not in facts_by_key:
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="USER_FACT",
                    fact_key="taxpayer_identity_confirmed",
                    demand_refs=["obl_taxpayer_identity_and_period_status"],
                    evidence_refs=[item["fact_id"] for item in party_facts],
                    question=(
                        "Confirm that the taxpayer for this declaration is the person "
                        "named in the supplied broker evidence."
                        if party_facts
                        else "Provide and confirm the taxpayer identity for this declaration."
                    ),
                    reason="authenticated taxpayer identity is required",
                    helpful_evidence="authenticated user confirmation",
                    client_benefit="prevents filing for the wrong taxpayer",
                    answer_contract={"kind": "confirmation"},
                    subject={},
                )
            )
        if residency_classification["status"] == "INSUFFICIENT_EVIDENCE":
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="USER_FACT",
                    fact_key="residency_evidence",
                    demand_refs=["obl_taxpayer_identity_and_period_status"],
                    evidence_refs=[],
                    question=(
                        "Describe the dates or intervals when you were physically present "
                        "in and absent from Russia during 2025, and state any relevant "
                        "absence reasons or exception documents. Do not answer only with "
                        "a resident/non-resident conclusion."
                    ),
                    reason=residency_classification["reason"],
                    helpful_evidence=(
                        "complete dated presence/absence intervals and factual absence-reason evidence"
                    ),
                    client_benefit=(
                        "allows the published residency methodology to classify period status without accepting a user tax conclusion"
                    ),
                    answer_contract={
                        "kind": "residency_evidence",
                        "proposal_schema_version": (
                            GATE5_RESIDENCY_EVIDENCE_PROPOSAL_SCHEMA_VERSION
                        ),
                    },
                    subject={"tax_period": "2025"},
                )
            )
        if "filing_instance_identity" not in facts_by_key:
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="USER_FACT",
                    fact_key="filing_instance_identity",
                    demand_refs=["obl_filing_instance_identity"],
                    evidence_refs=[],
                    question=(
                        "State the filing instance: initial or correction, and the "
                        "destination tax authority for the 2025 declaration."
                    ),
                    reason="filing instance and destination are absent from broker evidence",
                    helpful_evidence="authenticated filing instruction",
                    client_benefit="prevents projection to the wrong filing instance",
                    answer_contract={"kind": "text"},
                    subject={},
                )
            )
        if "signer_and_representation" not in facts_by_key:
            requests.append(
                _request(
                    kind="REQUIRED",
                    priority="HIGH",
                    closure_type="USER_FACT",
                    fact_key="signer_and_representation",
                    demand_refs=["obl_signer_and_representation_authority"],
                    evidence_refs=[],
                    question=(
                        "State whether the taxpayer signs personally or a representative "
                        "signs with supporting authority."
                    ),
                    reason="signer authority is not a broker-document fact",
                    helpful_evidence="authenticated signer instruction and authority if represented",
                    client_benefit="prevents an unauthorised filing",
                    answer_contract={
                        "kind": "code",
                        "allowed": ["SELF", "REPRESENTATIVE"],
                    },
                    subject={},
                )
            )
    source_demands = {
        "obl_russian_source_taxable_income",
        "obl_foreign_source_taxable_income_and_foreign_tax",
    }
    if active & source_demands:
        requests.append(
            _request(
                kind="REQUIRED",
                priority="HIGH",
                closure_type="ADDITIONAL_DOCUMENT",
                fact_key=None,
                demand_refs=sorted(active & source_demands),
                evidence_refs=[],
                question=(
                    "Provide the tax-agent certificate, foreign broker tax statement, "
                    "or other source document that states the payer, jurisdiction and "
                    "withheld or foreign tax facts for this income."
                ),
                reason=(
                    "income-source classification is a methodology decision; broker "
                    "identity, country and a user conclusion are not authority"
                ),
                helpful_evidence=(
                    "tax-agent certificate or foreign broker tax statement containing factual source evidence"
                ),
                client_benefit="supports the correct source schedule and foreign-tax treatment",
                answer_contract={"kind": "document_submission"},
                subject={},
            )
        )
    if "obl_declaration_budget_disposition" in active and (
        "budget_disposition" not in facts_by_key
    ):
        source_blocked = any(item["kind"] == "REQUIRED" for item in source_requests)
        requests.append(
            _request(
                kind="DEFERRED" if source_blocked else "REQUIRED",
                priority="LOW" if source_blocked else "HIGH",
                closure_type="USER_FACT",
                fact_key="budget_disposition",
                demand_refs=["obl_declaration_budget_disposition"],
                evidence_refs=[],
                question=(
                    "Choose payment, additional payment, reduction or refund disposition "
                    "after the supported settlement amount is known."
                ),
                reason="budget disposition depends on the completed tax settlement",
                helpful_evidence="authenticated disposition instruction after calculation",
                client_benefit="avoids asking for a downstream election before it is actionable",
                answer_contract={
                    "kind": "code",
                    "allowed": ["PAYMENT", "ADDITIONAL_PAYMENT", "REDUCTION", "REFUND"],
                },
                subject={},
            )
        )
    return requests


def _request(
    *,
    kind: str,
    priority: str,
    closure_type: str,
    fact_key: str | None,
    demand_refs: list[str],
    evidence_refs: list[str],
    question: str,
    reason: str,
    helpful_evidence: str,
    client_benefit: str,
    answer_contract: dict[str, Any],
    subject: dict[str, Any],
    routing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if closure_type not in _CLOSURE_TYPES:
        _fail("gate5_gap_closure_type_invalid")
    base = {
        "schema_version": GATE5_GAP_REQUEST_SCHEMA_VERSION,
        "kind": kind,
        "priority": priority,
        "closure_type": closure_type,
        "fact_key": fact_key,
        "demand_refs": sorted(demand_refs),
        "evidence_refs": sorted(evidence_refs),
        "subject": copy.deepcopy(subject),
        "question": question,
        "reason": reason,
        "helpful_evidence": helpful_evidence,
        "client_benefit": client_benefit,
        "answer_contract": copy.deepcopy(answer_contract),
    }
    if routing is not None:
        base["routing"] = _validated_routing(routing)
    return {**base, "request_id": "g5request_" + _sha256(base)[:32]}


def _validated_routing(value: Any) -> dict[str, Any]:
    required = {
        "ownership_state",
        "route",
        "owner",
        "closure_type",
        "user_or_additional_document_allowed",
    }
    if (
        not isinstance(value, dict)
        or set(value) != required
        or value.get("closure_type") not in _CLOSURE_TYPES
        or not all(
            isinstance(value.get(key), str) and value[key]
            for key in ("ownership_state", "route", "owner")
        )
        or not isinstance(value.get("user_or_additional_document_allowed"), bool)
    ):
        _fail("gate5_gap_owner_routing_invalid")
    if value["user_or_additional_document_allowed"] is False and value[
        "closure_type"
    ] in _USER_FACING_CLOSURE_TYPES:
        _fail("gate5_gap_internal_route_exposed_to_user")
    return copy.deepcopy(value)


def _validated_request(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != GATE5_GAP_REQUEST_SCHEMA_VERSION
        or value.get("closure_type") not in _CLOSURE_TYPES
        or not isinstance(value.get("request_id"), str)
        or not isinstance(value.get("answer_contract"), dict)
    ):
        _fail("gate5_gap_request_invalid")
    base = {
        key: copy.deepcopy(item) for key, item in value.items() if key != "request_id"
    }
    if value["request_id"] != "g5request_" + _sha256(base)[:32]:
        _fail("gate5_gap_request_invalid")
    if "routing" in value:
        routing = _validated_routing(value["routing"])
        if value["closure_type"] != routing["closure_type"]:
            _fail("gate5_gap_owner_routing_invalid")
    return copy.deepcopy(value)


def _validated_user_facts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        _fail("gate5_user_case_facts_invalid")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if (
            not isinstance(item, dict)
            or set(item) != _USER_FACT_KEYS
            or item.get("schema_version") != GATE5_USER_CASE_FACT_SCHEMA_VERSION
            or item.get("fact_key") not in _KNOWN_FACT_KEYS
            or item["fact_key"] in seen
            or not isinstance(item.get("value"), dict)
            or set(item["value"]) != {"kind", "value"}
            or not isinstance(item.get("provenance"), dict)
            or item["provenance"].get("source_kind") != "authenticated_user_case_fact"
            or item["provenance"].get("calculation_authority") is not False
            or item["provenance"].get("document_source_fact") is not False
        ):
            _fail("gate5_user_case_facts_invalid")
        seen.add(item["fact_key"])
        result.append(copy.deepcopy(item))
    return sorted(result, key=lambda item: item["fact_key"])


def _validate_inputs(
    *,
    intake: dict[str, Any],
    scope_activation: dict[str, Any],
    client_review: dict[str, Any],
) -> None:
    if intake.get("schema_version") != GATE5_EVIDENCE_INTAKE_SCHEMA_VERSION:
        _fail("gate5_gap_intake_invalid")
    if (
        scope_activation.get("schema_version")
        != GATE5_DECLARATION_SCOPE_ACTIVATION_SCHEMA_VERSION
    ):
        _fail("gate5_gap_scope_invalid")
    if (
        client_review.get("schema_version")
        != GATE5_CLIENT_EVIDENCE_REVIEW_SCHEMA_VERSION
    ):
        _fail("gate5_gap_review_invalid")


def _deduplicated_requests(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["request_id"]: item for item in value}
    return sorted(
        (copy.deepcopy(item) for item in by_id.values()),
        key=lambda item: (
            {"REQUIRED": 0, "ADVISORY": 1, "DEFERRED": 2}[item["kind"]],
            item["priority"],
            item["request_id"],
        ),
    )


def _adapter_request(item: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: copy.deepcopy(item[key])
        for key in (
            "request_id",
            "kind",
            "priority",
            "closure_type",
            "question",
            "reason",
            "helpful_evidence",
            "client_benefit",
            "answer_contract",
        )
    }
    if "routing" in item:
        result["routing"] = copy.deepcopy(item["routing"])
    return result


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
    raise Gate5HumanGapClosureError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_GAP_REQUEST_SCHEMA_VERSION",
    "GATE5_HUMAN_GAP_CLOSURE_SCHEMA_VERSION",
    "GATE5_HUMAN_GAP_CLOSURE_TERMINAL",
    "GATE5_USER_CASE_FACT_SCHEMA_VERSION",
    "Gate5HumanGapClosureError",
    "Gate5HumanGapClosureRuntime",
    "Gate5HumanGapClosureRuntimeFactory",
]
