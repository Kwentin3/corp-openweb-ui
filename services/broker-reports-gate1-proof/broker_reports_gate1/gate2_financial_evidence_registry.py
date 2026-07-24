from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Iterable


REGISTRY_ID = "broker_reports_gate2_financial_evidence_registry"
REGISTRY_VERSION_V1 = "broker_reports_gate2_financial_evidence_registry_v1"

FACTORY_REQUIRED = (
    "Gate2FinancialEvidenceRegistryFactory.create is the only production "
    "financial evidence registry snapshot entrypoint"
)
FORBIDDEN = (
    "Prompts, providers, runtimes and artifact stores must not declare or "
    "extend financial input type IDs outside the registry factory"
)

SEMANTIC_CLASSES = frozenset({"event", "state", "aggregate", "attribute"})
LIFECYCLE_VALUES = frozenset(
    {"experimental", "active", "deprecated", "retired"}
)
ROLE_VALUE_TYPES = frozenset(
    {
        "source_decimal",
        "source_integer",
        "source_text",
        "source_date",
        "source_period",
        "source_currency",
        "source_unit",
        "source_reference",
    }
)
ROLE_CARDINALITIES = frozenset({"one", "zero_or_one", "one_or_more"})
DATE_PERIOD_REQUIREMENTS = frozenset(
    {
        "event_date_required",
        "as_of_date_required",
        "period_required",
        "date_or_period_required",
        "optional",
        "forbidden",
    }
)
CURRENCY_UNIT_REQUIREMENTS = frozenset(
    {
        "currency_required",
        "unit_required",
        "currency_or_unit_required",
        "optional",
        "forbidden",
    }
)
SOURCE_SIGN_POLICIES = frozenset(
    {
        "preserve_source_sign",
        "preserve_source_sign_and_explicit_direction",
        "unsigned_source_value",
        "not_applicable",
    }
)
LEGACY_MAPPING_STATUSES = frozenset({"explicit", "candidate", "unmapped"})

_TYPE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*_v[1-9][0-9]*$")
_ROLE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_PROFILE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*_v[1-9][0-9]*$")
_REGISTRY_VERSION_RE = re.compile(
    r"^broker_reports_gate2_financial_evidence_registry_v[1-9][0-9]*$"
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class Gate2FinancialEvidenceRegistryError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class FinancialEvidenceRoleSpec:
    role_id: str
    value_type: str
    cardinality: str
    source_ref_required: bool = True


@dataclass(frozen=True)
class FinancialEvidenceIdentityPolicy:
    identity_roles: tuple[str, ...]
    include_source_scope: bool = True
    include_source_evidence_refs: bool = True


@dataclass(frozen=True)
class FinancialEvidenceLegacyMapping:
    legacy_type_id: str
    artifact_schema_versions: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class FinancialEvidenceCompatibility:
    compatible_registry_versions: tuple[str, ...] = ()
    predecessor_input_type_ids: tuple[str, ...] = ()
    legacy_mappings: tuple[FinancialEvidenceLegacyMapping, ...] = ()


@dataclass(frozen=True)
class FinancialEvidenceInputTypeDeclaration:
    input_type_id: str
    registry_version: str
    title: str
    definition: str
    semantic_class: str
    lifecycle: str
    compatible_source_families: tuple[str, ...]
    required_roles: tuple[str, ...]
    optional_roles: tuple[str, ...]
    forbidden_roles: tuple[str, ...]
    role_specs: tuple[FinancialEvidenceRoleSpec, ...]
    date_period_requirement: str
    currency_unit_requirement: str
    source_sign_policy: str
    identity_policy: FinancialEvidenceIdentityPolicy
    provider_description: str
    materialization_profile_id: str
    validation_profile_id: str
    context_projection_rule_id: str
    examples: tuple[str, ...]
    counterexamples: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    test_refs: tuple[str, ...]
    compatibility: FinancialEvidenceCompatibility


@dataclass(frozen=True)
class FinancialEvidenceTypeAlias:
    alias_id: str
    target_id: str
    artifact_schema_versions: tuple[str, ...]


@dataclass(frozen=True)
class Gate2FinancialEvidenceRegistrySnapshot:
    registry_id: str
    registry_version: str
    declarations: tuple[FinancialEvidenceInputTypeDeclaration, ...]
    aliases: tuple[FinancialEvidenceTypeAlias, ...]
    registry_hash: str

    def get(
        self, input_type_id: str
    ) -> FinancialEvidenceInputTypeDeclaration:
        resolved = self.resolve_type_id(input_type_id)
        for declaration in self.declarations:
            if declaration.input_type_id == resolved:
                return declaration
        raise Gate2FinancialEvidenceRegistryError(
            "financial_evidence_registry_type_unknown"
        )

    def resolve_type_id(self, input_type_id: str) -> str:
        canonical_ids = {
            declaration.input_type_id for declaration in self.declarations
        }
        if input_type_id in canonical_ids:
            return input_type_id
        target_by_alias = {
            alias.alias_id: alias.target_id for alias in self.aliases
        }
        visited: set[str] = set()
        current = input_type_id
        while current in target_by_alias:
            if current in visited:
                raise Gate2FinancialEvidenceRegistryError(
                    "financial_evidence_registry_alias_cycle"
                )
            visited.add(current)
            current = target_by_alias[current]
        if current not in canonical_ids:
            raise Gate2FinancialEvidenceRegistryError(
                "financial_evidence_registry_type_unknown"
            )
        return current

    def provider_type_enum(
        self, *, include_experimental: bool = False
    ) -> tuple[str, ...]:
        allowed_lifecycle = {"active"}
        if include_experimental:
            allowed_lifecycle.add("experimental")
        return tuple(
            declaration.input_type_id
            for declaration in self.declarations
            if declaration.lifecycle in allowed_lifecycle
        )

    def provider_description(self, input_type_id: str) -> str:
        return self.get(input_type_id).provider_description

    def materialization_profile_id(self, input_type_id: str) -> str:
        return self.get(input_type_id).materialization_profile_id

    def validation_profile_id(self, input_type_id: str) -> str:
        return self.get(input_type_id).validation_profile_id

    def context_projection_rule_id(self, input_type_id: str) -> str:
        return self.get(input_type_id).context_projection_rule_id

    def canonical_payload(self) -> dict[str, Any]:
        return _snapshot_payload(
            registry_version=self.registry_version,
            declarations=self.declarations,
            aliases=self.aliases,
        )


class Gate2FinancialEvidenceRegistryFactory:
    def __init__(
        self,
        *,
        registry_version: str = REGISTRY_VERSION_V1,
        declarations: Iterable[
            FinancialEvidenceInputTypeDeclaration
        ] = (),
        aliases: Iterable[FinancialEvidenceTypeAlias] = (),
        semantic_identity_pins: Iterable[tuple[str, str]] = (),
    ) -> None:
        self.registry_version = registry_version
        self.declarations = tuple(declarations)
        self.aliases = tuple(aliases)
        self.semantic_identity_pins = tuple(semantic_identity_pins)

    def create(self) -> Gate2FinancialEvidenceRegistrySnapshot:
        declarations = tuple(
            sorted(self.declarations, key=lambda item: item.input_type_id)
        )
        aliases = tuple(sorted(self.aliases, key=lambda item: item.alias_id))
        _validate_registry(
            registry_version=self.registry_version,
            declarations=declarations,
            aliases=aliases,
            semantic_identity_pins=self.semantic_identity_pins,
        )
        payload = _snapshot_payload(
            registry_version=self.registry_version,
            declarations=declarations,
            aliases=aliases,
        )
        return Gate2FinancialEvidenceRegistrySnapshot(
            registry_id=REGISTRY_ID,
            registry_version=self.registry_version,
            declarations=declarations,
            aliases=aliases,
            registry_hash=_sha256_json(payload),
        )


def financial_evidence_semantic_fingerprint(
    declaration: FinancialEvidenceInputTypeDeclaration,
) -> str:
    return _sha256_json(
        {
            "input_type_id": declaration.input_type_id,
            "definition": declaration.definition,
            "semantic_class": declaration.semantic_class,
            "compatible_source_families": list(
                declaration.compatible_source_families
            ),
            "required_roles": list(declaration.required_roles),
            "optional_roles": list(declaration.optional_roles),
            "forbidden_roles": list(declaration.forbidden_roles),
            "role_specs": [
                _role_spec_payload(item) for item in declaration.role_specs
            ],
            "date_period_requirement": declaration.date_period_requirement,
            "currency_unit_requirement": (
                declaration.currency_unit_requirement
            ),
            "source_sign_policy": declaration.source_sign_policy,
            "identity_policy": _identity_policy_payload(
                declaration.identity_policy
            ),
        }
    )


def _validate_registry(
    *,
    registry_version: str,
    declarations: tuple[FinancialEvidenceInputTypeDeclaration, ...],
    aliases: tuple[FinancialEvidenceTypeAlias, ...],
    semantic_identity_pins: tuple[tuple[str, str], ...],
) -> None:
    if not _REGISTRY_VERSION_RE.fullmatch(registry_version):
        _fail("financial_evidence_registry_version_invalid")
    type_ids = [item.input_type_id for item in declarations]
    if len(type_ids) != len(set(type_ids)):
        _fail("financial_evidence_registry_duplicate_type_id")
    alias_ids = [item.alias_id for item in aliases]
    if len(alias_ids) != len(set(alias_ids)):
        _fail("financial_evidence_registry_duplicate_alias_id")
    if set(alias_ids) & set(type_ids):
        _fail("financial_evidence_registry_alias_type_collision")

    pins = _semantic_pins(semantic_identity_pins)
    if set(pins) != set(type_ids):
        _fail("financial_evidence_registry_semantic_pin_set_invalid")

    for declaration in declarations:
        _validate_declaration(
            declaration=declaration,
            registry_version=registry_version,
            type_ids=set(type_ids),
        )
        if (
            financial_evidence_semantic_fingerprint(declaration)
            != pins[declaration.input_type_id]
        ):
            _fail("financial_evidence_registry_semantic_identity_changed")

    _validate_aliases(
        aliases=aliases,
        canonical_type_ids=set(type_ids),
    )


def _validate_declaration(
    *,
    declaration: FinancialEvidenceInputTypeDeclaration,
    registry_version: str,
    type_ids: set[str],
) -> None:
    if not _TYPE_ID_RE.fullmatch(declaration.input_type_id):
        _fail("financial_evidence_registry_type_id_invalid")
    if declaration.registry_version != registry_version:
        _fail("financial_evidence_registry_declaration_version_mismatch")
    _bounded_text(declaration.title, "title", maximum=160)
    _bounded_text(declaration.definition, "definition", maximum=1_200)
    _bounded_text(
        declaration.provider_description,
        "provider_description",
        maximum=500,
    )
    if declaration.semantic_class not in SEMANTIC_CLASSES:
        _fail("financial_evidence_registry_semantic_class_invalid")
    if declaration.lifecycle not in LIFECYCLE_VALUES:
        _fail("financial_evidence_registry_lifecycle_invalid")
    if not declaration.compatible_source_families:
        _fail("financial_evidence_registry_source_families_missing")
    if any(
        not _ROLE_ID_RE.fullmatch(item)
        for item in declaration.compatible_source_families
    ):
        _fail("financial_evidence_registry_source_family_invalid")

    required = _unique_roles(declaration.required_roles, "required")
    optional = _unique_roles(declaration.optional_roles, "optional")
    forbidden = _unique_roles(declaration.forbidden_roles, "forbidden")
    if required & optional or required & forbidden or optional & forbidden:
        _fail("financial_evidence_registry_conflicting_roles")
    if not required:
        _fail("financial_evidence_registry_required_roles_missing")

    specs = declaration.role_specs
    spec_ids = [item.role_id for item in specs]
    if len(spec_ids) != len(set(spec_ids)):
        _fail("financial_evidence_registry_duplicate_role_spec")
    if set(spec_ids) != required | optional:
        _fail("financial_evidence_registry_role_specs_incomplete")
    for spec in specs:
        _validate_role_spec(spec)

    if declaration.date_period_requirement not in DATE_PERIOD_REQUIREMENTS:
        _fail("financial_evidence_registry_date_period_policy_invalid")
    if (
        declaration.currency_unit_requirement
        not in CURRENCY_UNIT_REQUIREMENTS
    ):
        _fail("financial_evidence_registry_currency_unit_policy_invalid")
    if declaration.source_sign_policy not in SOURCE_SIGN_POLICIES:
        _fail("financial_evidence_registry_source_sign_policy_invalid")

    if (
        declaration.semantic_class == "state"
        and declaration.date_period_requirement
        not in {"as_of_date_required", "date_or_period_required"}
    ):
        _fail("financial_evidence_registry_state_date_policy_invalid")
    if (
        declaration.semantic_class == "event"
        and declaration.date_period_requirement
        not in {"event_date_required", "date_or_period_required"}
    ):
        _fail("financial_evidence_registry_event_date_policy_invalid")
    if (
        "amount" in required | optional
        and declaration.currency_unit_requirement == "forbidden"
    ):
        _fail("financial_evidence_registry_amount_unit_policy_invalid")

    _validate_identity_policy(
        declaration.identity_policy,
        available_roles=required | optional,
    )
    for profile_id in (
        declaration.materialization_profile_id,
        declaration.validation_profile_id,
        declaration.context_projection_rule_id,
    ):
        if not _PROFILE_ID_RE.fullmatch(profile_id):
            _fail("financial_evidence_registry_profile_id_invalid")

    _validate_safe_examples(
        declaration.examples,
        "examples",
        required=declaration.lifecycle in {"active", "experimental"},
    )
    _validate_safe_examples(
        declaration.counterexamples,
        "counterexamples",
        required=declaration.lifecycle in {"active", "experimental"},
    )
    if declaration.lifecycle == "active" and (
        not declaration.evidence_refs or not declaration.test_refs
    ):
        _fail("financial_evidence_registry_active_evidence_missing")
    for ref in declaration.evidence_refs + declaration.test_refs:
        _bounded_identifier(ref, "evidence_or_test_ref")

    compatibility = declaration.compatibility
    if len(compatibility.compatible_registry_versions) != len(
        set(compatibility.compatible_registry_versions)
    ):
        _fail("financial_evidence_registry_compatibility_duplicate")
    if any(
        not _REGISTRY_VERSION_RE.fullmatch(item)
        for item in compatibility.compatible_registry_versions
    ):
        _fail("financial_evidence_registry_compatibility_version_invalid")
    if any(
        item not in type_ids
        for item in compatibility.predecessor_input_type_ids
    ):
        _fail("financial_evidence_registry_compatibility_target_unknown")
    _validate_legacy_mappings(compatibility.legacy_mappings)


def _validate_role_spec(spec: FinancialEvidenceRoleSpec) -> None:
    if not _ROLE_ID_RE.fullmatch(spec.role_id):
        _fail("financial_evidence_registry_role_id_invalid")
    if spec.value_type not in ROLE_VALUE_TYPES:
        _fail("financial_evidence_registry_role_value_type_invalid")
    if spec.cardinality not in ROLE_CARDINALITIES:
        _fail("financial_evidence_registry_role_cardinality_invalid")
    if not isinstance(spec.source_ref_required, bool):
        _fail("financial_evidence_registry_role_source_ref_policy_invalid")


def _validate_identity_policy(
    policy: FinancialEvidenceIdentityPolicy,
    *,
    available_roles: set[str],
) -> None:
    if (
        not policy.identity_roles
        or len(policy.identity_roles) != len(set(policy.identity_roles))
        or any(item not in available_roles for item in policy.identity_roles)
    ):
        _fail("financial_evidence_registry_identity_roles_invalid")
    if (
        policy.include_source_scope is not True
        or policy.include_source_evidence_refs is not True
    ):
        _fail("financial_evidence_registry_source_identity_incomplete")


def _validate_legacy_mappings(
    mappings: tuple[FinancialEvidenceLegacyMapping, ...],
) -> None:
    legacy_ids = [item.legacy_type_id for item in mappings]
    if len(legacy_ids) != len(set(legacy_ids)):
        _fail("financial_evidence_registry_legacy_mapping_duplicate")
    for mapping in mappings:
        if not _ROLE_ID_RE.fullmatch(mapping.legacy_type_id):
            _fail("financial_evidence_registry_legacy_id_invalid")
        if mapping.status not in LEGACY_MAPPING_STATUSES:
            _fail("financial_evidence_registry_legacy_status_invalid")
        if not mapping.artifact_schema_versions:
            _fail("financial_evidence_registry_legacy_version_scope_missing")
        for version in mapping.artifact_schema_versions:
            _bounded_identifier(version, "legacy_artifact_schema_version")


def _validate_aliases(
    *,
    aliases: tuple[FinancialEvidenceTypeAlias, ...],
    canonical_type_ids: set[str],
) -> None:
    targets = {item.alias_id: item.target_id for item in aliases}
    for alias in aliases:
        if not _TYPE_ID_RE.fullmatch(alias.alias_id):
            _fail("financial_evidence_registry_alias_id_invalid")
        if not alias.artifact_schema_versions:
            _fail("financial_evidence_registry_alias_version_scope_missing")
        for version in alias.artifact_schema_versions:
            _bounded_identifier(version, "alias_artifact_schema_version")
        visited: set[str] = set()
        current = alias.alias_id
        while current in targets:
            if current in visited:
                _fail("financial_evidence_registry_alias_cycle")
            visited.add(current)
            current = targets[current]
        if current not in canonical_type_ids:
            _fail("financial_evidence_registry_alias_target_unknown")


def _semantic_pins(
    values: tuple[tuple[str, str], ...],
) -> dict[str, str]:
    result: dict[str, str] = {}
    for type_id, fingerprint in values:
        if type_id in result:
            _fail("financial_evidence_registry_semantic_pin_duplicate")
        if not _SHA256_RE.fullmatch(fingerprint):
            _fail("financial_evidence_registry_semantic_pin_invalid")
        result[type_id] = fingerprint
    return result


def _snapshot_payload(
    *,
    registry_version: str,
    declarations: tuple[FinancialEvidenceInputTypeDeclaration, ...],
    aliases: tuple[FinancialEvidenceTypeAlias, ...],
) -> dict[str, Any]:
    return {
        "registry_id": REGISTRY_ID,
        "registry_version": registry_version,
        "declarations": [
            _declaration_payload(item) for item in declarations
        ],
        "aliases": [_alias_payload(item) for item in aliases],
    }


def _declaration_payload(
    declaration: FinancialEvidenceInputTypeDeclaration,
) -> dict[str, Any]:
    return {
        "input_type_id": declaration.input_type_id,
        "registry_version": declaration.registry_version,
        "title": declaration.title,
        "definition": declaration.definition,
        "semantic_class": declaration.semantic_class,
        "lifecycle": declaration.lifecycle,
        "compatible_source_families": list(
            declaration.compatible_source_families
        ),
        "required_roles": list(declaration.required_roles),
        "optional_roles": list(declaration.optional_roles),
        "forbidden_roles": list(declaration.forbidden_roles),
        "role_specs": [
            _role_spec_payload(item) for item in declaration.role_specs
        ],
        "date_period_requirement": declaration.date_period_requirement,
        "currency_unit_requirement": (
            declaration.currency_unit_requirement
        ),
        "source_sign_policy": declaration.source_sign_policy,
        "identity_policy": _identity_policy_payload(
            declaration.identity_policy
        ),
        "provider_description": declaration.provider_description,
        "materialization_profile_id": (
            declaration.materialization_profile_id
        ),
        "validation_profile_id": declaration.validation_profile_id,
        "context_projection_rule_id": (
            declaration.context_projection_rule_id
        ),
        "examples": list(declaration.examples),
        "counterexamples": list(declaration.counterexamples),
        "evidence_refs": list(declaration.evidence_refs),
        "test_refs": list(declaration.test_refs),
        "compatibility": {
            "compatible_registry_versions": list(
                declaration.compatibility.compatible_registry_versions
            ),
            "predecessor_input_type_ids": list(
                declaration.compatibility.predecessor_input_type_ids
            ),
            "legacy_mappings": [
                {
                    "legacy_type_id": item.legacy_type_id,
                    "artifact_schema_versions": list(
                        item.artifact_schema_versions
                    ),
                    "status": item.status,
                }
                for item in declaration.compatibility.legacy_mappings
            ],
        },
    }


def _role_spec_payload(spec: FinancialEvidenceRoleSpec) -> dict[str, Any]:
    return {
        "role_id": spec.role_id,
        "value_type": spec.value_type,
        "cardinality": spec.cardinality,
        "source_ref_required": spec.source_ref_required,
    }


def _identity_policy_payload(
    policy: FinancialEvidenceIdentityPolicy,
) -> dict[str, Any]:
    return {
        "identity_roles": list(policy.identity_roles),
        "include_source_scope": policy.include_source_scope,
        "include_source_evidence_refs": (
            policy.include_source_evidence_refs
        ),
    }


def _alias_payload(alias: FinancialEvidenceTypeAlias) -> dict[str, Any]:
    return {
        "alias_id": alias.alias_id,
        "target_id": alias.target_id,
        "artifact_schema_versions": list(
            alias.artifact_schema_versions
        ),
    }


def _unique_roles(values: tuple[str, ...], label: str) -> set[str]:
    if len(values) != len(set(values)):
        _fail(f"financial_evidence_registry_{label}_role_duplicate")
    if any(not _ROLE_ID_RE.fullmatch(item) for item in values):
        _fail("financial_evidence_registry_role_id_invalid")
    return set(values)


def _validate_safe_examples(
    values: tuple[str, ...],
    label: str,
    *,
    required: bool,
) -> None:
    if required and not values:
        _fail(f"financial_evidence_registry_{label}_missing")
    for value in values:
        _bounded_text(value, label, maximum=500)


def _bounded_text(value: str, label: str, *, maximum: int) -> None:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > maximum
        or not value.isprintable()
    ):
        _fail(f"financial_evidence_registry_{label}_invalid")


def _bounded_identifier(value: str, label: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 200
        or not value.isascii()
        or not value.isprintable()
    ):
        _fail(f"financial_evidence_registry_{label}_invalid")


def _sha256_json(value: Any) -> str:
    rendered = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _fail(code: str) -> None:
    raise Gate2FinancialEvidenceRegistryError(code)
