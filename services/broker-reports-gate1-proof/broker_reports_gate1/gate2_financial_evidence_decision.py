from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .gate2_financial_evidence_registry import (
    ROLE_VALUE_TYPES,
    FinancialEvidenceInputTypeDeclaration,
    Gate2FinancialEvidenceRegistrySnapshot,
)


DECISION_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_evidence_decision_v1"
)
OPENAI_SCHEMA_NAME = "broker_reports_gate2_financial_evidence_decision"
GEMINI_SCHEMA_NAME = (
    "broker_reports_gate2_financial_evidence_decision_gemini"
)

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceDecisionContractFactory.create is the only "
    "production decision-contract entrypoint"
)
FORBIDDEN = (
    "Prompts and providers must not add dispositions, registry type IDs, "
    "source-value refs, bindings or free-JSON fallbacks outside the factory"
)

DISPOSITIONS = (
    "typed_input",
    "unclassified_financial_input",
    "no_financial_input",
    "unsupported",
)
TYPED_REASON_CODES = ("typed_supported",)
UNCLASSIFIED_REASON_CODES = (
    "ambiguous_registry_type",
    "no_registry_type",
)
NO_FINANCIAL_REASON_CODES = (
    "duplicate_representation",
    "header_or_layout",
    "non_financial_content",
)
UNSUPPORTED_REASON_CODES = (
    "extractor_profile_unsupported",
    "provider_schema_unsupported",
    "source_shape_unsupported",
)

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_:.\\/-]*$")
_MAX_CANDIDATES = 64
_OPENAI_REMOVED_KEYWORDS = frozenset({"uniqueItems"})
_GEMINI_REMOVED_KEYWORDS = frozenset(
    {"$schema", "maxItems", "minItems", "uniqueItems"}
)


class Gate2FinancialEvidenceDecisionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialEvidenceValueCandidate:
    source_value_ref: str
    source_ref: str
    value_type: str
    allowed_roles: tuple[str, ...]


@dataclass(frozen=True)
class FinancialEvidenceDecisionPackage:
    source_scope_ref: str
    source_family_id: str
    candidates: tuple[FinancialEvidenceValueCandidate, ...]
    allowed_type_ids: tuple[str, ...] | None = None


@dataclass(frozen=True)
class FinancialEvidenceValueBinding:
    role_id: str
    source_value_ref: str


@dataclass(frozen=True)
class TypedFinancialInputDecision:
    disposition: str
    input_type_id: str
    value_bindings: tuple[FinancialEvidenceValueBinding, ...]
    reason_code: str


@dataclass(frozen=True)
class UnclassifiedFinancialInputDecision:
    disposition: str
    value_bindings: tuple[FinancialEvidenceValueBinding, ...]
    reason_code: str


@dataclass(frozen=True)
class NoFinancialInputDecision:
    disposition: str
    reason_code: str


@dataclass(frozen=True)
class UnsupportedFinancialInputDecision:
    disposition: str
    reason_code: str


FinancialEvidenceDecision = (
    TypedFinancialInputDecision
    | UnclassifiedFinancialInputDecision
    | NoFinancialInputDecision
    | UnsupportedFinancialInputDecision
)


@dataclass(frozen=True)
class Gate2FinancialEvidenceDecisionContract:
    registry: Gate2FinancialEvidenceRegistrySnapshot
    package: FinancialEvidenceDecisionPackage
    eligible_type_ids: tuple[str, ...]

    def canonical_schema(self) -> dict[str, Any]:
        variants: list[dict[str, Any]] = []
        for input_type_id in self.eligible_type_ids:
            declaration = self.registry.get(input_type_id)
            typed = _typed_variant_schema(
                declaration=declaration,
                candidates=self.package.candidates,
            )
            if typed is not None:
                variants.append(typed)
        unclassified = _unclassified_variant_schema(self.package.candidates)
        if unclassified is not None:
            variants.append(unclassified)
        variants.extend(
            (
                _terminal_variant_schema(
                    disposition="no_financial_input",
                    reason_codes=NO_FINANCIAL_REASON_CODES,
                ),
                _terminal_variant_schema(
                    disposition="unsupported",
                    reason_codes=UNSUPPORTED_REASON_CODES,
                ),
            )
        )
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": DECISION_SCHEMA_VERSION,
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "decision": {
                    "anyOf": variants,
                }
            },
            "required": ["decision"],
        }

    def canonical_schema_hash(self) -> str:
        return _sha256_json(self.canonical_schema())

    def openai_response_format(self) -> dict[str, Any]:
        schema = copy.deepcopy(self.canonical_schema())
        _project_openai_schema(schema)
        return {
            "type": "json_schema",
            "json_schema": {
                "name": OPENAI_SCHEMA_NAME,
                "strict": True,
                "schema": schema,
            },
        }

    def gemini_response_format(self) -> dict[str, Any]:
        schema = copy.deepcopy(self.canonical_schema())
        _project_gemini_schema(schema)
        return {
            "type": "json_schema",
            "json_schema": {
                "name": GEMINI_SCHEMA_NAME,
                "strict": True,
                "schema": schema,
            },
        }

    def provider_schema_hash(self, provider: str) -> str:
        if provider == "openai":
            payload = self.openai_response_format()
        elif provider == "gemini":
            payload = self.gemini_response_format()
        else:
            _fail("financial_evidence_decision_provider_unknown")
        return _sha256_json(payload)

    def parse_model_output(
        self, payload: str | dict[str, Any]
    ) -> FinancialEvidenceDecision:
        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                _fail("financial_evidence_decision_json_invalid")
        else:
            parsed = payload
        if not isinstance(parsed, dict) or set(parsed) != {"decision"}:
            _fail("financial_evidence_decision_root_invalid")
        decision = parsed["decision"]
        if not isinstance(decision, dict):
            _fail("financial_evidence_decision_object_invalid")
        disposition = decision.get("disposition")
        if disposition not in DISPOSITIONS:
            _fail("financial_evidence_decision_disposition_invalid")
        if disposition == "typed_input":
            return self._parse_typed(decision)
        if disposition == "unclassified_financial_input":
            return self._parse_unclassified(decision)
        if disposition == "no_financial_input":
            return _parse_terminal(
                decision=decision,
                disposition=disposition,
                reason_codes=NO_FINANCIAL_REASON_CODES,
                decision_type=NoFinancialInputDecision,
            )
        return _parse_terminal(
            decision=decision,
            disposition=disposition,
            reason_codes=UNSUPPORTED_REASON_CODES,
            decision_type=UnsupportedFinancialInputDecision,
        )

    def _parse_typed(
        self, decision: dict[str, Any]
    ) -> TypedFinancialInputDecision:
        if set(decision) != {
            "disposition",
            "input_type_id",
            "reason_code",
            "value_bindings",
        }:
            _fail("financial_evidence_decision_typed_shape_invalid")
        input_type_id = decision["input_type_id"]
        if (
            not isinstance(input_type_id, str)
            or input_type_id not in self.eligible_type_ids
        ):
            _fail("financial_evidence_decision_type_not_allowed")
        if decision["reason_code"] not in TYPED_REASON_CODES:
            _fail("financial_evidence_decision_reason_invalid")
        declaration = self.registry.get(input_type_id)
        raw_bindings = decision["value_bindings"]
        expected_roles = set(
            declaration.required_roles + declaration.optional_roles
        )
        if not isinstance(raw_bindings, dict) or set(raw_bindings) != (
            expected_roles
        ):
            _fail("financial_evidence_decision_typed_roles_invalid")
        candidates = {
            item.source_value_ref: item for item in self.package.candidates
        }
        specs = {item.role_id: item for item in declaration.role_specs}
        bindings: list[FinancialEvidenceValueBinding] = []
        for role_id in sorted(expected_roles):
            source_value_ref = raw_bindings[role_id]
            if source_value_ref is None:
                if role_id in declaration.required_roles:
                    _fail(
                        "financial_evidence_decision_required_binding_missing"
                    )
                continue
            if not isinstance(source_value_ref, str):
                _fail("financial_evidence_decision_binding_ref_invalid")
            candidate = candidates.get(source_value_ref)
            if candidate is None:
                _fail("financial_evidence_decision_binding_outside_package")
            if (
                role_id not in candidate.allowed_roles
                or candidate.value_type != specs[role_id].value_type
            ):
                _fail("financial_evidence_decision_binding_incompatible")
            bindings.append(
                FinancialEvidenceValueBinding(
                    role_id=role_id,
                    source_value_ref=source_value_ref,
                )
            )
        return TypedFinancialInputDecision(
            disposition="typed_input",
            input_type_id=input_type_id,
            value_bindings=tuple(bindings),
            reason_code=decision["reason_code"],
        )

    def _parse_unclassified(
        self, decision: dict[str, Any]
    ) -> UnclassifiedFinancialInputDecision:
        if set(decision) != {
            "disposition",
            "reason_code",
            "value_bindings",
        }:
            _fail("financial_evidence_decision_unclassified_shape_invalid")
        if decision["reason_code"] not in UNCLASSIFIED_REASON_CODES:
            _fail("financial_evidence_decision_reason_invalid")
        raw_bindings = decision["value_bindings"]
        if (
            not isinstance(raw_bindings, list)
            or not raw_bindings
            or len(raw_bindings) > len(self.package.candidates)
        ):
            _fail("financial_evidence_decision_unclassified_bindings_invalid")
        candidates = {
            item.source_value_ref: item for item in self.package.candidates
        }
        bindings: list[FinancialEvidenceValueBinding] = []
        seen_refs: set[str] = set()
        for raw_binding in raw_bindings:
            if not isinstance(raw_binding, dict) or set(raw_binding) != {
                "role_id",
                "source_value_ref",
            }:
                _fail(
                    "financial_evidence_decision_unclassified_binding_invalid"
                )
            role_id = raw_binding["role_id"]
            source_value_ref = raw_binding["source_value_ref"]
            if (
                not isinstance(role_id, str)
                or not isinstance(source_value_ref, str)
            ):
                _fail(
                    "financial_evidence_decision_unclassified_binding_invalid"
                )
            candidate = candidates.get(source_value_ref)
            if candidate is None:
                _fail("financial_evidence_decision_binding_outside_package")
            if role_id not in candidate.allowed_roles:
                _fail("financial_evidence_decision_binding_incompatible")
            if source_value_ref in seen_refs:
                _fail("financial_evidence_decision_binding_duplicate")
            seen_refs.add(source_value_ref)
            bindings.append(
                FinancialEvidenceValueBinding(
                    role_id=role_id,
                    source_value_ref=source_value_ref,
                )
            )
        return UnclassifiedFinancialInputDecision(
            disposition="unclassified_financial_input",
            value_bindings=tuple(
                sorted(
                    bindings,
                    key=lambda item: (
                        item.source_value_ref,
                        item.role_id,
                    ),
                )
            ),
            reason_code=decision["reason_code"],
        )


class Gate2FinancialEvidenceDecisionContractFactory:
    def __init__(
        self,
        *,
        registry: Gate2FinancialEvidenceRegistrySnapshot,
        package: FinancialEvidenceDecisionPackage,
    ) -> None:
        self.registry = registry
        self.package = package

    def create(self) -> Gate2FinancialEvidenceDecisionContract:
        package = _normalize_package(self.package)
        active_type_ids = set(self.registry.provider_type_enum())
        if package.allowed_type_ids is None:
            allowed_type_ids = active_type_ids
        else:
            allowed_type_ids = set(package.allowed_type_ids)
            if not allowed_type_ids <= active_type_ids:
                _fail("financial_evidence_decision_allowed_type_unknown")
        eligible_type_ids = tuple(
            declaration.input_type_id
            for declaration in self.registry.declarations
            if declaration.input_type_id in allowed_type_ids
            and package.source_family_id
            in declaration.compatible_source_families
        )
        return Gate2FinancialEvidenceDecisionContract(
            registry=self.registry,
            package=package,
            eligible_type_ids=eligible_type_ids,
        )


def _normalize_package(
    package: FinancialEvidenceDecisionPackage,
) -> FinancialEvidenceDecisionPackage:
    _bounded_identifier(package.source_scope_ref, "source_scope_ref")
    _bounded_identifier(package.source_family_id, "source_family_id")
    if len(package.candidates) > _MAX_CANDIDATES:
        _fail("financial_evidence_decision_candidate_limit_exceeded")
    refs = [item.source_value_ref for item in package.candidates]
    if len(refs) != len(set(refs)):
        _fail("financial_evidence_decision_candidate_ref_duplicate")
    normalized: list[FinancialEvidenceValueCandidate] = []
    for candidate in package.candidates:
        _bounded_identifier(candidate.source_value_ref, "source_value_ref")
        _bounded_identifier(candidate.source_ref, "source_ref")
        if candidate.value_type not in ROLE_VALUE_TYPES:
            _fail("financial_evidence_decision_candidate_value_type_invalid")
        roles = tuple(sorted(candidate.allowed_roles))
        if not roles or len(roles) != len(set(roles)):
            _fail("financial_evidence_decision_candidate_roles_invalid")
        for role_id in roles:
            _bounded_identifier(role_id, "allowed_role")
        normalized.append(
            FinancialEvidenceValueCandidate(
                source_value_ref=candidate.source_value_ref,
                source_ref=candidate.source_ref,
                value_type=candidate.value_type,
                allowed_roles=roles,
            )
        )
    allowed_type_ids = package.allowed_type_ids
    if allowed_type_ids is not None:
        if len(allowed_type_ids) != len(set(allowed_type_ids)):
            _fail("financial_evidence_decision_allowed_type_duplicate")
        allowed_type_ids = tuple(sorted(allowed_type_ids))
    return FinancialEvidenceDecisionPackage(
        source_scope_ref=package.source_scope_ref,
        source_family_id=package.source_family_id,
        candidates=tuple(
            sorted(normalized, key=lambda item: item.source_value_ref)
        ),
        allowed_type_ids=allowed_type_ids,
    )


def _typed_variant_schema(
    *,
    declaration: FinancialEvidenceInputTypeDeclaration,
    candidates: tuple[FinancialEvidenceValueCandidate, ...],
) -> dict[str, Any] | None:
    specs = {item.role_id: item for item in declaration.role_specs}
    properties: dict[str, Any] = {}
    for role_id in declaration.required_roles + declaration.optional_roles:
        refs = _compatible_candidate_refs(
            candidates=candidates,
            role_id=role_id,
            value_type=specs[role_id].value_type,
        )
        if role_id in declaration.required_roles and not refs:
            return None
        reference_schema: dict[str, Any] = {
            "type": "string",
            "enum": list(refs),
        }
        if role_id in declaration.optional_roles:
            properties[role_id] = {
                "anyOf": [reference_schema, {"type": "null"}]
            }
        else:
            properties[role_id] = reference_schema
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "disposition": {
                "type": "string",
                "enum": ["typed_input"],
            },
            "input_type_id": {
                "type": "string",
                "enum": [declaration.input_type_id],
            },
            "value_bindings": {
                "type": "object",
                "additionalProperties": False,
                "properties": properties,
                "required": sorted(properties),
            },
            "reason_code": {
                "type": "string",
                "enum": list(TYPED_REASON_CODES),
            },
        },
        "required": [
            "disposition",
            "input_type_id",
            "value_bindings",
            "reason_code",
        ],
    }


def _unclassified_variant_schema(
    candidates: tuple[FinancialEvidenceValueCandidate, ...],
) -> dict[str, Any] | None:
    pairs = [
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "role_id": {
                    "type": "string",
                    "enum": [role_id],
                },
                "source_value_ref": {
                    "type": "string",
                    "enum": [candidate.source_value_ref],
                },
            },
            "required": ["role_id", "source_value_ref"],
        }
        for candidate in candidates
        for role_id in candidate.allowed_roles
    ]
    if not pairs:
        return None
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "disposition": {
                "type": "string",
                "enum": ["unclassified_financial_input"],
            },
            "value_bindings": {
                "type": "array",
                "items": {"anyOf": pairs},
                "minItems": 1,
                "maxItems": len(candidates),
                "uniqueItems": True,
            },
            "reason_code": {
                "type": "string",
                "enum": list(UNCLASSIFIED_REASON_CODES),
            },
        },
        "required": ["disposition", "value_bindings", "reason_code"],
    }


def _terminal_variant_schema(
    *, disposition: str, reason_codes: tuple[str, ...]
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "disposition": {
                "type": "string",
                "enum": [disposition],
            },
            "reason_code": {
                "type": "string",
                "enum": list(reason_codes),
            },
        },
        "required": ["disposition", "reason_code"],
    }


def _compatible_candidate_refs(
    *,
    candidates: tuple[FinancialEvidenceValueCandidate, ...],
    role_id: str,
    value_type: str,
) -> tuple[str, ...]:
    return tuple(
        item.source_value_ref
        for item in candidates
        if role_id in item.allowed_roles and item.value_type == value_type
    )


def _parse_terminal(
    *,
    decision: dict[str, Any],
    disposition: str,
    reason_codes: tuple[str, ...],
    decision_type: type[
        NoFinancialInputDecision | UnsupportedFinancialInputDecision
    ],
) -> NoFinancialInputDecision | UnsupportedFinancialInputDecision:
    if set(decision) != {"disposition", "reason_code"}:
        _fail("financial_evidence_decision_terminal_shape_invalid")
    reason_code = decision["reason_code"]
    if reason_code not in reason_codes:
        _fail("financial_evidence_decision_reason_invalid")
    return decision_type(
        disposition=disposition,
        reason_code=reason_code,
    )


def _project_gemini_schema(value: Any) -> None:
    if isinstance(value, dict):
        if "const" in value:
            value["enum"] = [value.pop("const")]
        for keyword in _GEMINI_REMOVED_KEYWORDS:
            value.pop(keyword, None)
        for child in value.values():
            _project_gemini_schema(child)
    elif isinstance(value, list):
        for child in value:
            _project_gemini_schema(child)


def _project_openai_schema(value: Any) -> None:
    if isinstance(value, dict):
        for keyword in _OPENAI_REMOVED_KEYWORDS:
            value.pop(keyword, None)
        for child in value.values():
            _project_openai_schema(child)
    elif isinstance(value, list):
        for child in value:
            _project_openai_schema(child)


def _bounded_identifier(value: Any, field: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 240
        or not _IDENTIFIER_RE.fullmatch(value)
    ):
        _fail(f"financial_evidence_decision_{field}_invalid")


def _sha256_json(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceDecisionError(code)
