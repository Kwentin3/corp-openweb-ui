"""One declaration-required external reference fact with bounded evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from .artifact_models import ArtifactAccessContext, ArtifactStorePort
from .gate4_financial_case_cache import (
    Gate4FinancialCaseRuntime,
    Gate4FinancialCaseRuntimeFactory,
)


GATE5_EXTERNAL_EVIDENCE_REQUIREMENT_SCHEMA_VERSION = (
    "broker_reports_gate5_external_evidence_requirement_v0"
)
GATE5_EXTERNAL_EVIDENCE_RESEARCH_SCHEMA_VERSION = (
    "broker_reports_gate5_external_evidence_research_v0"
)
GATE5_EXTERNAL_EVIDENCE_ROUTING_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_external_evidence_routing_result_v0"
)
GATE5_EXTERNAL_EVIDENCE_PROPOSAL_SCHEMA_VERSION = (
    "broker_reports_gate5_external_evidence_proposal_v0"
)
GATE5_EXTERNAL_REFERENCE_FACT_SCHEMA_VERSION = (
    "broker_reports_gate5_external_reference_fact_v0"
)
GATE5_EXTERNAL_EVIDENCE_ACCEPTANCE_RESULT_SCHEMA_VERSION = (
    "broker_reports_gate5_external_evidence_acceptance_result_v0"
)

FACTORY_REQUIRED = (
    "Gate5ExternalEvidenceRuntimeFactory.create",
    "Gate4FinancialCaseRuntimeFactory.create owns Financial Case reads",
)
FORBIDDEN = (
    "direct broker, CanonicalArtifact, Gate 3 target or Gate 4 SQL reads",
    "external meaning written into Gate4FinancialCaseFactV1",
    "user Supplemental Fact used for external authoritative evidence",
    "LLM-owned authority, tax conclusion, persistence or provider transport",
    "generic research agent, source registry, reference platform or workflow",
)

_REQUIREMENT_KEYS = frozenset(
    {"schema_version", "requirement_id", "fact_key", "entity", "declaration_binding"}
)
_ENTITY_KEYS = frozenset(
    {"jurisdiction", "tax_period", "income_group_code", "taxpayer_status"}
)
_DECLARATION_KEYS = frozenset({"form", "knd"})
_ROUTING_KEYS = frozenset(
    {
        "schema_version",
        "status",
        "route",
        "financial_case_audit",
        "research_request",
        "research_request_sha256",
    }
)
_AUDIT_KEYS = frozenset(
    {
        "boundary",
        "status",
        "facts_total",
        "fact_set_sha256",
        "required_fact_status",
        "required_fact_provenance",
    }
)
_RESEARCH_KEYS = frozenset(
    {
        "schema_version",
        "research_question",
        "required_fact",
        "entity",
        "effective_context",
        "source_policy",
        "required_output",
    }
)
_PROPOSAL_KEYS = frozenset(
    {
        "schema_version",
        "action",
        "research_request_sha256",
        "claim",
        "evidence_refs",
        "conflicting_values",
        "unresolved_reason",
    }
)
_CLAIM_KEYS = frozenset({"fact_key", "entity", "value"})
_VALUE_KEYS = frozenset(
    {
        "kind",
        "currency",
        "threshold_amount",
        "lower_rate_percent",
        "amount_at_threshold",
        "excess_rate_percent",
    }
)
_EVIDENCE_KEYS = frozenset(
    {
        "evidence_ref",
        "authority_kind",
        "source_url",
        "source_document_id",
        "content_sha256",
        "locator",
        "supports",
        "effective_context",
    }
)
_EFFECTIVE_KEYS = frozenset({"tax_period_from", "tax_period_to", "source_published_on"})
_ALLOWED_AUTHORITY_KINDS = (
    "official_legal_publication",
    "tax_authority_primary",
)
_ALLOWED_HOSTS = (
    "nalog.gov.ru",
    "publication.pravo.gov.ru",
    "www.nalog.gov.ru",
)
_REQUIRED_SUPPORT = frozenset({"claim_value", "effective_period"})
_FACT_KEY = "resident_securities_income_group_rate_schedule"
_CANONICAL_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]{0,17})\.[0-9]{2}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_MAX_EVIDENCE_BYTES = 5 * 1024 * 1024


class Gate5ExternalEvidenceError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate5ExternalEvidenceDocument:
    evidence_ref: str
    source_url: str
    media_type: str
    content: bytes = field(repr=False)


class Gate5ExternalEvidenceRuntimeFactory:
    def __init__(
        self,
        *,
        store: ArtifactStorePort,
        read_enabled: bool,
    ) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate5ExternalEvidenceRuntime":
        financial_case = Gate4FinancialCaseRuntimeFactory(
            store=self._store,
            read_enabled=self._read_enabled,
        ).create()
        return Gate5ExternalEvidenceRuntime(financial_case=financial_case)


class Gate5ExternalEvidenceRuntime:
    def __init__(self, *, financial_case: Gate4FinancialCaseRuntime) -> None:
        self._financial_case = financial_case

    def prepare(
        self,
        *,
        requirement: dict[str, Any],
        context: ArtifactAccessContext,
    ) -> dict[str, Any]:
        validated = _validated_requirement(requirement)
        current_case = self._financial_case.read_case(context=context)
        if _financial_case_contains_tax_reference_role(
            facts=current_case.facts,
            fact_key=validated["fact_key"],
        ):
            raise Gate5ExternalEvidenceError(
                "gate5_external_evidence_gate4_semantic_drift"
            )

        research_request = _research_request(validated)
        request_sha256 = _digest(research_request)
        return {
            "schema_version": GATE5_EXTERNAL_EVIDENCE_ROUTING_RESULT_SCHEMA_VERSION,
            "status": "external_research_required",
            "route": "external_authoritative_research",
            "financial_case_audit": {
                "boundary": "Gate4FinancialCaseRuntimeFactory.create",
                "status": current_case.status,
                "facts_total": len(current_case.facts),
                "fact_set_sha256": _digest(list(current_case.facts)),
                "required_fact_status": "not_asserted",
                "required_fact_provenance": None,
            },
            "research_request": research_request,
            "research_request_sha256": request_sha256,
        }

    def accept(
        self,
        *,
        routing_result: dict[str, Any],
        proposal: dict[str, Any],
        evidence_documents: tuple[Gate5ExternalEvidenceDocument, ...],
    ) -> dict[str, Any]:
        routing = _validated_routing_result(routing_result)
        candidate = _validated_proposal_shape(proposal)

        if candidate["action"] == "unresolved":
            binding_errors = (
                []
                if candidate["research_request_sha256"]
                == routing["research_request_sha256"]
                else ["research_request_binding_mismatch"]
            )
            return _acceptance_result(
                status="unresolved" if not binding_errors else "rejected",
                routing=routing,
                proposal=candidate,
                validation_status="passed" if not binding_errors else "failed",
                validation_errors=binding_errors,
                external_fact=None,
            )

        validation_errors, document_metadata = _proposal_validation_errors(
            routing=routing,
            proposal=candidate,
            evidence_documents=evidence_documents,
        )
        if validation_errors:
            return _acceptance_result(
                status="rejected",
                routing=routing,
                proposal=candidate,
                validation_status="failed",
                validation_errors=validation_errors,
                external_fact=None,
            )

        external_fact = _external_fact(
            routing=routing,
            proposal=candidate,
            document_metadata=document_metadata,
        )
        return _acceptance_result(
            status="accepted",
            routing=routing,
            proposal=candidate,
            validation_status="passed",
            validation_errors=[],
            external_fact=external_fact,
        )


def gate5_external_evidence_proposal_response_format() -> dict[str, Any]:
    nullable_claim = {
        "anyOf": [
            _claim_schema(),
            {"type": "null"},
        ]
    }
    nullable_string = {
        "anyOf": [
            {"type": "string", "minLength": 1, "maxLength": 300},
            {"type": "null"},
        ]
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "gate5_external_evidence_proposal",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "required": sorted(_PROPOSAL_KEYS),
                "properties": {
                    "schema_version": {
                        "type": "string",
                        "const": GATE5_EXTERNAL_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
                    },
                    "action": {
                        "type": "string",
                        "enum": ["propose_fact", "unresolved"],
                    },
                    "research_request_sha256": {
                        "type": "string",
                        "pattern": "^[0-9a-f]{64}$",
                    },
                    "claim": nullable_claim,
                    "evidence_refs": {
                        "type": "array",
                        "maxItems": 6,
                        "items": _evidence_schema(),
                    },
                    "conflicting_values": {
                        "type": "array",
                        "maxItems": 6,
                        "items": _value_schema(),
                    },
                    "unresolved_reason": nullable_string,
                },
            },
        },
    }


def _research_request(requirement: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": GATE5_EXTERNAL_EVIDENCE_RESEARCH_SCHEMA_VERSION,
        "research_question": (
            "Установить официальную шкалу НДФЛ для группы доходов 02 "
            "налогового резидента РФ за налоговый период 2025."
        ),
        "required_fact": {
            "fact_key": requirement["fact_key"],
            "value_kind": "progressive_rate_schedule",
        },
        "entity": copy.deepcopy(requirement["entity"]),
        "effective_context": {
            "tax_period": requirement["entity"]["tax_period"],
            "declaration_form": requirement["declaration_binding"]["form"],
            "declaration_knd": requirement["declaration_binding"]["knd"],
        },
        "source_policy": {
            "allowed_authority_kinds": list(_ALLOWED_AUTHORITY_KINDS),
            "allowed_hosts": list(_ALLOWED_HOSTS),
            "required_support": sorted(_REQUIRED_SUPPORT),
            "fallback_to_model_memory": False,
            "fallback_to_search_snippet": False,
        },
        "required_output": {
            "response_format": "strict_json_schema",
            "schema_version": GATE5_EXTERNAL_EVIDENCE_PROPOSAL_SCHEMA_VERSION,
            "claim_and_evidence_separate": True,
        },
    }


def _validated_requirement(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _REQUIREMENT_KEYS
        or value.get("schema_version")
        != GATE5_EXTERNAL_EVIDENCE_REQUIREMENT_SCHEMA_VERSION
        or value.get("fact_key") != _FACT_KEY
        or not _clean_string(value.get("requirement_id"), 160)
    ):
        raise Gate5ExternalEvidenceError("gate5_external_evidence_requirement_invalid")
    entity = value.get("entity")
    declaration = value.get("declaration_binding")
    if (
        not isinstance(entity, dict)
        or set(entity) != _ENTITY_KEYS
        or entity
        != {
            "jurisdiction": "RU",
            "tax_period": "2025",
            "income_group_code": "02",
            "taxpayer_status": "resident_individual",
        }
        or not isinstance(declaration, dict)
        or set(declaration) != _DECLARATION_KEYS
        or declaration != {"form": "3-NDFL", "knd": "1151020"}
    ):
        raise Gate5ExternalEvidenceError("gate5_external_evidence_requirement_invalid")
    return copy.deepcopy(value)


def _validated_routing_result(value: Any) -> dict[str, Any]:
    audit = value.get("financial_case_audit") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or set(value) != _ROUTING_KEYS
        or value.get("schema_version")
        != GATE5_EXTERNAL_EVIDENCE_ROUTING_RESULT_SCHEMA_VERSION
        or value.get("status") != "external_research_required"
        or value.get("route") != "external_authoritative_research"
        or not isinstance(audit, dict)
        or set(audit) != _AUDIT_KEYS
        or audit.get("boundary") != "Gate4FinancialCaseRuntimeFactory.create"
        or not _clean_string(audit.get("status"), 100)
        or not isinstance(audit.get("facts_total"), int)
        or audit["facts_total"] < 0
        or not isinstance(audit.get("fact_set_sha256"), str)
        or _SHA256.fullmatch(audit["fact_set_sha256"]) is None
        or audit.get("required_fact_status") != "not_asserted"
        or audit.get("required_fact_provenance") is not None
        or not isinstance(value.get("research_request"), dict)
        or set(value["research_request"]) != _RESEARCH_KEYS
        or value["research_request"].get("schema_version")
        != GATE5_EXTERNAL_EVIDENCE_RESEARCH_SCHEMA_VERSION
        or value.get("research_request_sha256") != _digest(value["research_request"])
    ):
        raise Gate5ExternalEvidenceError("gate5_external_evidence_routing_invalid")
    return copy.deepcopy(value)


def _validated_proposal_shape(value: Any) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != _PROPOSAL_KEYS
        or value.get("schema_version")
        != GATE5_EXTERNAL_EVIDENCE_PROPOSAL_SCHEMA_VERSION
        or value.get("action") not in {"propose_fact", "unresolved"}
        or not isinstance(value.get("research_request_sha256"), str)
        or _SHA256.fullmatch(value["research_request_sha256"]) is None
        or not isinstance(value.get("evidence_refs"), list)
        or len(value["evidence_refs"]) > 6
        or any(not _valid_evidence_shape(item) for item in value["evidence_refs"])
        or not isinstance(value.get("conflicting_values"), list)
        or len(value["conflicting_values"]) > 6
    ):
        raise Gate5ExternalEvidenceError("gate5_external_evidence_proposal_invalid")
    if value["action"] == "unresolved":
        if (
            value.get("claim") is not None
            or not _clean_string(value.get("unresolved_reason"), 300)
            or any(not _valid_value_shape(item) for item in value["conflicting_values"])
        ):
            raise Gate5ExternalEvidenceError("gate5_external_evidence_proposal_invalid")
    elif (
        value.get("unresolved_reason") is not None
        or not _valid_claim_shape(value.get("claim"))
        or any(not _valid_value_shape(item) for item in value["conflicting_values"])
    ):
        raise Gate5ExternalEvidenceError("gate5_external_evidence_proposal_invalid")
    return copy.deepcopy(value)


def _proposal_validation_errors(
    *,
    routing: dict[str, Any],
    proposal: dict[str, Any],
    evidence_documents: tuple[Gate5ExternalEvidenceDocument, ...],
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    request = routing["research_request"]
    if proposal["research_request_sha256"] != routing["research_request_sha256"]:
        errors.append("research_request_binding_mismatch")
    claim = proposal["claim"]
    if claim["fact_key"] != request["required_fact"]["fact_key"]:
        errors.append("claim_fact_key_mismatch")
    if claim["entity"] != request["entity"]:
        errors.append("claim_entity_mismatch")
    if proposal["conflicting_values"]:
        errors.append("conflicting_evidence_values")
    if not _value_is_mechanically_consistent(claim["value"]):
        errors.append("claim_value_mechanically_invalid")

    documents: dict[str, Gate5ExternalEvidenceDocument] = {}
    for document in evidence_documents:
        if not _valid_document_shape(document):
            errors.append("evidence_document_invalid")
            continue
        if document.evidence_ref in documents:
            errors.append("evidence_document_duplicate")
            continue
        documents[document.evidence_ref] = document

    refs = proposal["evidence_refs"]
    ref_ids = [item["evidence_ref"] for item in refs]
    if not refs:
        errors.append("authoritative_evidence_required")
    if len(ref_ids) != len(set(ref_ids)):
        errors.append("evidence_ref_duplicate")
    if set(documents) - set(ref_ids):
        errors.append("unreferenced_evidence_document")

    covered_support: set[str] = set()
    metadata: list[dict[str, Any]] = []
    tax_period = int(request["entity"]["tax_period"])
    for item in refs:
        document = documents.get(item["evidence_ref"])
        host = _allowed_host(item["source_url"])
        if (
            item["authority_kind"]
            not in request["source_policy"]["allowed_authority_kinds"]
            or host not in request["source_policy"]["allowed_hosts"]
        ):
            errors.append("evidence_source_not_allowed")
        if document is None:
            errors.append("evidence_document_missing")
            continue
        actual_sha256 = hashlib.sha256(document.content).hexdigest()
        if item["source_url"] != document.source_url:
            errors.append("evidence_source_binding_mismatch")
        if item["content_sha256"] != actual_sha256:
            errors.append("evidence_content_hash_mismatch")
        effective = item["effective_context"]
        period_from = int(effective["tax_period_from"])
        period_to = (
            int(effective["tax_period_to"])
            if effective["tax_period_to"] is not None
            else None
        )
        if period_from != tax_period or period_to != tax_period:
            errors.append("evidence_effective_period_mismatch")
        covered_support.update(item["supports"])
        metadata.append(
            {
                "evidence_ref": document.evidence_ref,
                "source_url": document.source_url,
                "media_type": document.media_type,
                "content_sha256": actual_sha256,
                "bytes": len(document.content),
            }
        )
    if not _REQUIRED_SUPPORT.issubset(covered_support):
        errors.append("evidence_support_incomplete")
    return sorted(set(errors)), sorted(metadata, key=lambda item: item["evidence_ref"])


def _external_fact(
    *,
    routing: dict[str, Any],
    proposal: dict[str, Any],
    document_metadata: list[dict[str, Any]],
) -> dict[str, Any]:
    core = {
        "schema_version": GATE5_EXTERNAL_REFERENCE_FACT_SCHEMA_VERSION,
        "fact_key": proposal["claim"]["fact_key"],
        "entity": copy.deepcopy(proposal["claim"]["entity"]),
        "value": copy.deepcopy(proposal["claim"]["value"]),
        "provenance": {
            "source_kind": "external_authoritative_evidence",
            "evidence_class": "externally_verified_reference",
            "research_request_sha256": routing["research_request_sha256"],
            "proposal_sha256": _digest(proposal),
            "evidence_refs": copy.deepcopy(proposal["evidence_refs"]),
            "evidence_documents": copy.deepcopy(document_metadata),
            "derived_tax_conclusion": False,
        },
    }
    return {"external_fact_ref": f"g5ext_{_digest(core)[:32]}", **core}


def _acceptance_result(
    *,
    status: str,
    routing: dict[str, Any],
    proposal: dict[str, Any],
    validation_status: str,
    validation_errors: list[str],
    external_fact: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema_version": GATE5_EXTERNAL_EVIDENCE_ACCEPTANCE_RESULT_SCHEMA_VERSION,
        "status": status,
        "route": routing["route"],
        "research_request_sha256": routing["research_request_sha256"],
        "proposal": copy.deepcopy(proposal),
        "validation": {
            "status": validation_status,
            "errors": list(validation_errors),
        },
        "external_fact": copy.deepcopy(external_fact),
        "persistence": "not_persisted_g5_11",
    }


def _financial_case_contains_tax_reference_role(
    *, facts: tuple[dict[str, Any], ...], fact_key: str
) -> bool:
    return any(
        isinstance(role, dict) and role.get("role") == fact_key
        for fact in facts
        if isinstance(fact, dict)
        for role in fact.get("roles") or []
    )


def _valid_claim_shape(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == _CLAIM_KEYS
        and value.get("fact_key") == _FACT_KEY
        and value.get("entity")
        == {
            "jurisdiction": "RU",
            "tax_period": "2025",
            "income_group_code": "02",
            "taxpayer_status": "resident_individual",
        }
        and _valid_value_shape(value.get("value"))
    )


def _valid_value_shape(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == _VALUE_KEYS
        and value.get("kind") == "progressive_rate_schedule"
        and value.get("currency") == "RUB"
        and all(
            isinstance(value.get(key), str)
            and _CANONICAL_DECIMAL.fullmatch(value[key]) is not None
            for key in (
                "threshold_amount",
                "lower_rate_percent",
                "amount_at_threshold",
                "excess_rate_percent",
            )
        )
    )


def _value_is_mechanically_consistent(value: dict[str, Any]) -> bool:
    try:
        threshold = Decimal(value["threshold_amount"])
        lower_rate = Decimal(value["lower_rate_percent"])
        amount_at_threshold = Decimal(value["amount_at_threshold"])
        excess_rate = Decimal(value["excess_rate_percent"])
    except (InvalidOperation, KeyError):
        return False
    return (
        threshold > 0
        and Decimal("0") < lower_rate <= Decimal("100")
        and Decimal("0") < excess_rate <= Decimal("100")
        and amount_at_threshold
        == (threshold * lower_rate / Decimal("100")).quantize(Decimal("0.01"))
    )


def _valid_evidence_shape(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != _EVIDENCE_KEYS:
        return False
    effective = value.get("effective_context")
    return (
        _clean_string(value.get("evidence_ref"), 160)
        and _clean_string(value.get("authority_kind"), 80)
        and _clean_string(value.get("source_url"), 1000)
        and _clean_string(value.get("source_document_id"), 240)
        and isinstance(value.get("content_sha256"), str)
        and _SHA256.fullmatch(value["content_sha256"]) is not None
        and _clean_string(value.get("locator"), 500)
        and isinstance(value.get("supports"), list)
        and value["supports"]
        and len(value["supports"]) == len(set(value["supports"]))
        and all(item in _REQUIRED_SUPPORT for item in value["supports"])
        and isinstance(effective, dict)
        and set(effective) == _EFFECTIVE_KEYS
        and isinstance(effective.get("tax_period_from"), str)
        and effective["tax_period_from"].isdigit()
        and len(effective["tax_period_from"]) == 4
        and (
            effective.get("tax_period_to") is None
            or (
                isinstance(effective["tax_period_to"], str)
                and effective["tax_period_to"].isdigit()
                and len(effective["tax_period_to"]) == 4
            )
        )
        and isinstance(effective.get("source_published_on"), str)
        and _DATE.fullmatch(effective["source_published_on"]) is not None
    )


def _valid_document_shape(value: Any) -> bool:
    return (
        isinstance(value, Gate5ExternalEvidenceDocument)
        and _clean_string(value.evidence_ref, 160)
        and _clean_string(value.source_url, 1000)
        and _clean_string(value.media_type, 160)
        and isinstance(value.content, bytes)
        and 0 < len(value.content) <= _MAX_EVIDENCE_BYTES
    )


def _allowed_host(source_url: str) -> str | None:
    try:
        parsed = urlparse(source_url)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None
    return host if host in _ALLOWED_HOSTS else None


def _claim_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_CLAIM_KEYS),
        "properties": {
            "fact_key": {"type": "string", "const": _FACT_KEY},
            "entity": {
                "type": "object",
                "additionalProperties": False,
                "required": sorted(_ENTITY_KEYS),
                "properties": {
                    "jurisdiction": {"type": "string", "const": "RU"},
                    "tax_period": {"type": "string", "const": "2025"},
                    "income_group_code": {"type": "string", "const": "02"},
                    "taxpayer_status": {
                        "type": "string",
                        "const": "resident_individual",
                    },
                },
            },
            "value": _value_schema(),
        },
    }


def _value_schema() -> dict[str, Any]:
    decimal = {"type": "string", "pattern": _CANONICAL_DECIMAL.pattern}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_VALUE_KEYS),
        "properties": {
            "kind": {"type": "string", "const": "progressive_rate_schedule"},
            "currency": {"type": "string", "const": "RUB"},
            "threshold_amount": copy.deepcopy(decimal),
            "lower_rate_percent": copy.deepcopy(decimal),
            "amount_at_threshold": copy.deepcopy(decimal),
            "excess_rate_percent": copy.deepcopy(decimal),
        },
    }


def _evidence_schema() -> dict[str, Any]:
    nullable_period = {
        "anyOf": [
            {"type": "string", "pattern": "^[0-9]{4}$"},
            {"type": "null"},
        ]
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(_EVIDENCE_KEYS),
        "properties": {
            "evidence_ref": {"type": "string", "minLength": 1, "maxLength": 160},
            "authority_kind": {
                "type": "string",
                "enum": list(_ALLOWED_AUTHORITY_KINDS),
            },
            "source_url": {"type": "string", "minLength": 1, "maxLength": 1000},
            "source_document_id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 240,
            },
            "content_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "locator": {"type": "string", "minLength": 1, "maxLength": 500},
            "supports": {
                "type": "array",
                "minItems": 1,
                "maxItems": 2,
                "uniqueItems": True,
                "items": {"type": "string", "enum": sorted(_REQUIRED_SUPPORT)},
            },
            "effective_context": {
                "type": "object",
                "additionalProperties": False,
                "required": sorted(_EFFECTIVE_KEYS),
                "properties": {
                    "tax_period_from": {"type": "string", "pattern": "^[0-9]{4}$"},
                    "tax_period_to": nullable_period,
                    "source_published_on": {
                        "type": "string",
                        "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
                    },
                },
            },
        },
    }


def _clean_string(value: Any, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and value == value.strip()
        and len(value) <= maximum
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE5_EXTERNAL_EVIDENCE_ACCEPTANCE_RESULT_SCHEMA_VERSION",
    "GATE5_EXTERNAL_EVIDENCE_PROPOSAL_SCHEMA_VERSION",
    "GATE5_EXTERNAL_EVIDENCE_REQUIREMENT_SCHEMA_VERSION",
    "GATE5_EXTERNAL_EVIDENCE_RESEARCH_SCHEMA_VERSION",
    "GATE5_EXTERNAL_EVIDENCE_ROUTING_RESULT_SCHEMA_VERSION",
    "GATE5_EXTERNAL_REFERENCE_FACT_SCHEMA_VERSION",
    "Gate5ExternalEvidenceDocument",
    "Gate5ExternalEvidenceError",
    "Gate5ExternalEvidenceRuntime",
    "Gate5ExternalEvidenceRuntimeFactory",
    "gate5_external_evidence_proposal_response_format",
]
