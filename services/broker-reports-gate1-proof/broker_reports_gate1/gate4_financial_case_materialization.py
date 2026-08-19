"""Deterministic FinancialAnnotationsV2 to Gate 4 fact materialization."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import re
from typing import Any

from .artifact_models import ArtifactAccessContext
from .artifact_resolver import ArtifactResolver
from .gate3_financial_annotations_persistence import (
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
    Gate3FinancialAnnotationsPersistenceError,
    Gate3FinancialAnnotationsPersistenceFactory,
)
from .gate3_financial_role_pack import (
    Gate3FinancialRolePackError,
    Gate3FinancialRolePackFactory,
)
from .gate3_role_labeling import (
    FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION,
    Gate3RoleLabelingError,
    Gate3RoleValueResolverFactory,
)


GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION = "broker_reports_gate4_financial_case_fact_v2"
FACTORY_REQUIRED = (
    "Gate4FinancialCaseMaterializerFactory.create is the only deterministic "
    "FinancialAnnotationsV2 to Gate4FinancialCaseFactV2 entrypoint"
)
FORBIDDEN = (
    "Gate 4 materialization must not read source formats, classify facts, "
    "choose roles, call an LLM, guess values, add broker rules, relate facts "
    "or apply tax logic"
)

_FACT_KEYS = {
    "schema_version",
    "fact_id",
    "case_binding",
    "gate3_binding",
    "semantic_kind",
    "semantic_binding",
    "financial_type",
    "annotation_target",
    "roles",
    "status",
}
_DECIMAL_TEXT = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:[.,][0-9]+)?$")
_SPACE_GROUPED_DECIMAL = re.compile(
    r"^-?(?:[1-9][0-9]{0,2})(?:[ \u00a0\u202f][0-9]{3})+(?:[.,][0-9]+)?$"
)
_COMMA_GROUPED_DOT_DECIMAL = re.compile(
    r"^-?(?:[1-9][0-9]{0,2})(?:,[0-9]{3})+\.[0-9]+$"
)
_DOT_GROUPED_COMMA_DECIMAL = re.compile(
    r"^-?(?:[1-9][0-9]{0,2})(?:\.[0-9]{3})+,[0-9]+$"
)
_ISO_DATE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")
_DMY_DATE = re.compile(r"^([0-9]{2})\.([0-9]{2})\.([0-9]{4})$")


class Gate4FinancialCaseMaterializationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Gate4FinancialCaseMaterialization:
    """One exact upstream document materialized into zero or more facts."""

    financial_annotations_artifact_id: str
    document_id: str
    canonical_version_id: str
    facts: tuple[dict[str, Any], ...]
    non_materialized_presence_annotations: tuple[dict[str, Any], ...] = ()


class Gate4FinancialCaseMaterializerFactory:
    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled

    def create(self) -> "Gate4FinancialCaseMaterializer":
        return Gate4FinancialCaseMaterializer(
            store=self._store,
            read_enabled=self._read_enabled,
        )


class Gate4FinancialCaseMaterializer:
    """Mechanically project one current validated Gate 3 sidecar."""

    def __init__(self, *, store: Any, read_enabled: bool) -> None:
        self._store = store
        self._read_enabled = read_enabled
        self._resolver = ArtifactResolver(store)
        self._persistence = Gate3FinancialAnnotationsPersistenceFactory(
            store=store,
            read_enabled=read_enabled,
        ).create()

    def materialize(
        self,
        *,
        financial_annotations_artifact_id: str,
        context: ArtifactAccessContext,
    ) -> Gate4FinancialCaseMaterialization:
        if (
            not isinstance(financial_annotations_artifact_id, str)
            or not financial_annotations_artifact_id
        ):
            raise Gate4FinancialCaseMaterializationError(
                "gate4_financial_annotations_artifact_id_required"
            )
        case_binding = _case_binding(context)
        record = self._resolver.resolve_record(
            financial_annotations_artifact_id,
            context,
        )
        if record.artifact_type != GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE:
            raise Gate4FinancialCaseMaterializationError(
                "gate4_financial_annotations_v2_required"
            )
        try:
            payload = self._persistence.read(
                artifact_id=financial_annotations_artifact_id,
                context=context,
            )
        except Gate3FinancialAnnotationsPersistenceError as exc:
            raise Gate4FinancialCaseMaterializationError(
                "gate4_upstream_invalid"
            ) from exc
        binding = payload["canonical_binding"]
        if (
            payload.get("schema_version") != FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION
            or record.document_id != binding.get("document_id")
        ):
            raise Gate4FinancialCaseMaterializationError("gate4_upstream_invalid")
        try:
            resolver = Gate3RoleValueResolverFactory.create_from_active_canonical(
                store=self._store,
                read_enabled=self._read_enabled,
                document_id=binding["document_id"],
                expected_canonical_version_id=binding["canonical_version_id"],
                context=context,
            )
            role_pack = Gate3FinancialRolePackFactory.create().load_published(
                payload["role_pack_identity"]["semantic_version"]
            )
        except Gate3RoleLabelingError as exc:
            code = (
                "gate4_upstream_stale"
                if exc.code == "gate3_role_canonical_binding_stale"
                else "gate4_upstream_invalid"
            )
            raise Gate4FinancialCaseMaterializationError(code) from exc
        except Gate3FinancialRolePackError as exc:
            raise Gate4FinancialCaseMaterializationError(
                "gate4_upstream_invalid"
            ) from exc
        if payload["role_pack_identity"] != {
            "role_pack_id": role_pack["role_pack_id"],
            "semantic_version": role_pack["semantic_version"],
        }:
            raise Gate4FinancialCaseMaterializationError("gate4_upstream_invalid")
        profiles = {item["financial_label"]: item for item in role_pack["profiles"]}
        semantic_binding = _semantic_binding(payload)
        decisions = [
            gate4_annotation_materialization_decision(
                annotation,
                structurally_atomic_target=(
                    resolver.is_unambiguously_atomic_assertion_target(
                        annotation.get("target")
                    )
                ),
                unambiguous_literal_anchor=(
                    resolver.has_unambiguous_literal_anchor(annotation)
                ),
            )
            for annotation in payload["annotations"]
        ]
        facts = tuple(
            self._materialize_annotation(
                annotation=annotation,
                annotation_index=annotation_index,
                financial_annotations_artifact_id=(financial_annotations_artifact_id),
                canonical_binding=binding,
                case_binding=case_binding,
                semantic_binding=semantic_binding,
                profile=profiles.get(annotation["financial_label"]),
                resolver=resolver,
            )
            for annotation_index, annotation in enumerate(payload["annotations"])
            if decisions[annotation_index]["materializable"]
        )
        non_materialized = tuple(
            {
                "annotation_index": annotation_index,
                "financial_label": annotation["financial_label"],
                "target": copy.deepcopy(annotation["target"]),
                "reason_code": decisions[annotation_index]["reason_code"],
            }
            for annotation_index, annotation in enumerate(payload["annotations"])
            if not decisions[annotation_index]["materializable"]
        )
        return Gate4FinancialCaseMaterialization(
            financial_annotations_artifact_id=(financial_annotations_artifact_id),
            document_id=binding["document_id"],
            canonical_version_id=binding["canonical_version_id"],
            facts=facts,
            non_materialized_presence_annotations=non_materialized,
        )

    @staticmethod
    def _materialize_annotation(
        *,
        annotation: dict[str, Any],
        annotation_index: int,
        financial_annotations_artifact_id: str,
        canonical_binding: dict[str, str],
        case_binding: dict[str, str],
        semantic_binding: dict[str, Any],
        profile: dict[str, Any] | None,
        resolver: Any,
    ) -> dict[str, Any]:
        if profile is None:
            raise Gate4FinancialCaseMaterializationError("gate4_role_profile_unknown")
        required = tuple(profile["required_roles"])
        optional = tuple(profile["optional_roles"])
        expected_roles = (*required, *optional)
        role_bindings = annotation.get("roles")
        if (
            not isinstance(role_bindings, list)
            or tuple(item.get("role") for item in role_bindings) != expected_roles
        ):
            raise Gate4FinancialCaseMaterializationError("gate4_role_profile_mismatch")
        roles: list[dict[str, Any]] = []
        for role_binding in role_bindings:
            role = role_binding["role"]
            requirement = "required" if role in required else "optional"
            if role_binding["status"] == "missing":
                roles.append(
                    {
                        "role": role,
                        "requirement": requirement,
                        "status": "missing",
                    }
                )
                continue
            try:
                source_literal = resolver.resolve(role_binding)
            except Gate3RoleLabelingError as exc:
                raise Gate4FinancialCaseMaterializationError(
                    "gate4_role_source_invalid"
                ) from exc
            if not isinstance(source_literal, str) or not source_literal:
                raise Gate4FinancialCaseMaterializationError(
                    "gate4_role_source_invalid"
                )
            source_binding = {
                "target": copy.deepcopy(role_binding["target"]),
                "source_literal": source_literal,
            }
            if "exact_text" in role_binding:
                source_binding["exact_text"] = role_binding["exact_text"]
            roles.append(
                {
                    "role": role,
                    "requirement": requirement,
                    "status": "value",
                    "value": _normalize_role_value(role, source_literal),
                    "source_binding": source_binding,
                }
            )
        status = (
            "role_incomplete"
            if any(
                item["requirement"] == "required" and item["status"] == "missing"
                for item in roles
            )
            else "role_complete"
        )
        fact: dict[str, Any] = {
            "schema_version": GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION,
            "fact_id": "",
            "case_binding": copy.deepcopy(case_binding),
            "gate3_binding": {
                "financial_annotations_artifact_id": (
                    financial_annotations_artifact_id
                ),
                "financial_annotations_schema_version": (
                    FINANCIAL_ANNOTATIONS_V2_SCHEMA_VERSION
                ),
                "annotation_index": annotation_index,
                "canonical_binding": copy.deepcopy(canonical_binding),
            },
            "semantic_kind": "normalized_source_fact",
            "semantic_binding": copy.deepcopy(semantic_binding),
            "financial_type": annotation["financial_label"],
            "annotation_target": copy.deepcopy(annotation["target"]),
            "roles": roles,
            "status": status,
        }
        fact["fact_id"] = gate4_financial_case_fact_id(fact)
        _validate_materialized_fact(fact, expected_roles=expected_roles)
        return fact


def gate4_financial_case_fact_id(fact: dict[str, Any]) -> str:
    try:
        material = {
            "schema_version": fact["schema_version"],
            "case_binding": fact["case_binding"],
            "financial_annotations_artifact_id": fact["gate3_binding"][
                "financial_annotations_artifact_id"
            ],
            "annotation_index": fact["gate3_binding"]["annotation_index"],
            "canonical_binding": fact["gate3_binding"]["canonical_binding"],
            "semantic_kind": fact["semantic_kind"],
            "semantic_binding": fact["semantic_binding"],
            "financial_type": fact["financial_type"],
        }
        encoded = json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (KeyError, TypeError, ValueError) as exc:
        raise Gate4FinancialCaseMaterializationError(
            "gate4_fact_identity_invalid"
        ) from exc
    return "g4fact_" + hashlib.sha256(encoded).hexdigest()[:32]


def gate4_annotation_materialization_decision(
    annotation: dict[str, Any],
    *,
    structurally_atomic_target: bool | None = None,
    unambiguous_literal_anchor: bool = False,
) -> dict[str, Any]:
    """Keep coarse label-only presence observations outside Gate 4 facts."""

    target = annotation.get("target")
    target_kind = target.get("kind") if isinstance(target, dict) else None
    structurally_atomic = (
        target_kind in {"table_row", "table_cell", "list_item"}
        if structurally_atomic_target is None
        else structurally_atomic_target
    )
    if structurally_atomic or unambiguous_literal_anchor:
        return {"materializable": True, "reason_code": "atomic_source_assertion"}
    return {
        "materializable": False,
        "reason_code": "non_atomic_region_presence_only",
    }


def _case_binding(context: ArtifactAccessContext) -> dict[str, str]:
    if not isinstance(context, ArtifactAccessContext):
        raise Gate4FinancialCaseMaterializationError("gate4_trusted_context_required")
    if not context.user_id or not context.allow_private:
        raise Gate4FinancialCaseMaterializationError("gate4_private_context_required")
    if context.case_id:
        return {"scope_kind": "case", "scope_id": context.case_id}
    if context.chat_id:
        return {"scope_kind": "chat", "scope_id": context.chat_id}
    raise Gate4FinancialCaseMaterializationError("gate4_case_or_chat_scope_required")


def _semantic_binding(payload: dict[str, Any]) -> dict[str, Any]:
    dictionary = payload.get("dictionary_identity")
    role_pack = payload.get("role_pack_identity")
    if (
        not isinstance(dictionary, dict)
        or set(dictionary) != {"dictionary_id", "semantic_version"}
        or not all(isinstance(item, str) and item for item in dictionary.values())
        or not isinstance(role_pack, dict)
        or set(role_pack) != {"role_pack_id", "semantic_version"}
        or not all(isinstance(item, str) and item for item in role_pack.values())
    ):
        raise Gate4FinancialCaseMaterializationError("gate4_semantic_binding_invalid")
    return {
        "dictionary": {
            "authority_id": dictionary["dictionary_id"],
            "semantic_version": dictionary["semantic_version"],
        },
        "role_pack": {
            "authority_id": role_pack["role_pack_id"],
            "semantic_version": role_pack["semantic_version"],
        },
    }


def _normalize_role_value(role: str, source_literal: str) -> str:
    if len(source_literal) > 65536:
        raise Gate4FinancialCaseMaterializationError("gate4_role_value_invalid")
    value = source_literal.strip()
    if role == "date":
        return _normalize_date(value)
    if role in {"quantity", "unit_price", "amount"}:
        if not value:
            raise Gate4FinancialCaseMaterializationError("gate4_role_value_invalid")
        return _normalize_decimal_literal(value)
    if role in {"asset", "currency", "source_wording"} and value:
        return value
    raise Gate4FinancialCaseMaterializationError("gate4_role_value_invalid")


def _normalize_date(value: str) -> str:
    if not value:
        raise Gate4FinancialCaseMaterializationError("gate4_role_value_invalid")
    match = _ISO_DATE.fullmatch(value)
    if match is not None:
        year, month, day = (int(item) for item in match.groups())
    else:
        match = _DMY_DATE.fullmatch(value)
        if match is None:
            return value
        day, month, year = (int(item) for item in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return value


def _normalize_decimal_literal(value: str) -> str:
    if _DECIMAL_TEXT.fullmatch(value) is not None:
        return value.replace(",", ".")
    if _SPACE_GROUPED_DECIMAL.fullmatch(value) is not None:
        return re.sub(r"[ \u00a0\u202f]", "", value).replace(",", ".")
    if _COMMA_GROUPED_DOT_DECIMAL.fullmatch(value) is not None:
        return value.replace(",", "")
    if _DOT_GROUPED_COMMA_DECIMAL.fullmatch(value) is not None:
        return value.replace(".", "").replace(",", ".")
    return value


def _validate_materialized_fact(
    fact: dict[str, Any], *, expected_roles: tuple[str, ...]
) -> None:
    roles = fact.get("roles")
    if (
        set(fact) != _FACT_KEYS
        or fact.get("schema_version") != GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION
        or fact.get("fact_id") != gate4_financial_case_fact_id(fact)
        or fact.get("semantic_kind") != "normalized_source_fact"
        or not isinstance(fact.get("semantic_binding"), dict)
        or not isinstance(roles, list)
        or tuple(item.get("role") for item in roles) != expected_roles
        or fact.get("status") not in {"role_complete", "role_incomplete"}
    ):
        raise Gate4FinancialCaseMaterializationError("gate4_fact_contract_invalid")
    incomplete = any(
        item.get("requirement") == "required" and item.get("status") == "missing"
        for item in roles
    )
    expected_status = "role_incomplete" if incomplete else "role_complete"
    if fact["status"] != expected_status:
        raise Gate4FinancialCaseMaterializationError("gate4_fact_contract_invalid")


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE4_FINANCIAL_CASE_FACT_SCHEMA_VERSION",
    "Gate4FinancialCaseMaterialization",
    "Gate4FinancialCaseMaterializationError",
    "Gate4FinancialCaseMaterializer",
    "Gate4FinancialCaseMaterializerFactory",
    "gate4_financial_case_fact_id",
]
