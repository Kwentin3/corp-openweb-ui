"""Public representation contract for an already-qualified Runtime fact.

It owns only the closed V3 wire representation and identity.  Canonical,
mapping, projection, tax and XML owners remain separate.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping


QUALIFIED_PROJECTION_FACT_V3_SCHEMA_VERSION = "broker_reports_qualified_projection_fact_v3"
_KEYS = {
    "schema_version", "fact_id", "case_binding", "qualified_projection_binding",
    "semantic_kind", "semantic_binding", "financial_type", "annotation_target",
    "roles", "status",
}
_BINDING_KEYS = {
    "projection_artifact_id", "canonical_binding", "source_observation_id",
    "semantic_mapping_case_ref", "runtime_record_id",
}
_CANONICAL_KEYS = {"document_id", "canonical_version_id", "canonical_root_sha256"}
_ROLE_KEYS = {"role", "requirement", "status", "value", "source_binding"}
_ROLE_SOURCE_KEYS = {"target", "exact_text", "source_literal"}
_SHA256 = re.compile(r"[0-9a-f]{64}")


class QualifiedProjectionFactV3Error(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def build_qualified_projection_fact_v3(
    *,
    case_binding: Mapping[str, Any],
    projection_artifact_id: str,
    canonical_binding: Mapping[str, Any],
    source_observation_id: str,
    semantic_mapping_case_ref: str,
    runtime_record_id: str,
    semantic_kind: str,
    semantic_binding: Mapping[str, Any],
    financial_type: str,
    annotation_target: Mapping[str, Any],
    roles: list[Mapping[str, Any]],
    status: str,
) -> dict[str, Any]:
    """Build a fact from an existing qualified projection record only."""

    fact = {
        "schema_version": QUALIFIED_PROJECTION_FACT_V3_SCHEMA_VERSION,
        "fact_id": "",
        "case_binding": copy.deepcopy(dict(case_binding)),
        "qualified_projection_binding": {
            "projection_artifact_id": projection_artifact_id,
            "canonical_binding": copy.deepcopy(dict(canonical_binding)),
            "source_observation_id": source_observation_id,
            "semantic_mapping_case_ref": semantic_mapping_case_ref,
            "runtime_record_id": runtime_record_id,
        },
        "semantic_kind": semantic_kind,
        "semantic_binding": copy.deepcopy(dict(semantic_binding)),
        "financial_type": financial_type,
        "annotation_target": copy.deepcopy(dict(annotation_target)),
        "roles": copy.deepcopy(list(roles)),
        "status": status,
    }
    _validate_shape(fact)
    fact["fact_id"] = qualified_projection_fact_v3_id(fact)
    return validate_qualified_projection_fact_v3(fact)


def qualified_projection_fact_v3_id(value: Mapping[str, Any]) -> str:
    material = copy.deepcopy(dict(value)) if isinstance(value, Mapping) else None
    if material is None:
        _fail("qualified_projection_fact_v3_contract_invalid")
    material["fact_id"] = ""
    _validate_shape(material)
    return "qpf3_" + hashlib.sha256(_json(material).encode("utf-8")).hexdigest()[:32]


def validate_qualified_projection_fact_v3(value: Any) -> dict[str, Any]:
    _validate_shape(value)
    if value.get("fact_id") != qualified_projection_fact_v3_id(value):
        _fail("qualified_projection_fact_v3_identity_invalid")
    return copy.deepcopy(dict(value))


def qualified_projection_binding(value: Mapping[str, Any]) -> dict[str, Any]:
    return validate_qualified_projection_fact_v3(value)["qualified_projection_binding"]


def _validate_shape(value: Any) -> None:
    if (
        not isinstance(value, Mapping) or set(value) != _KEYS
        or value.get("schema_version") != QUALIFIED_PROJECTION_FACT_V3_SCHEMA_VERSION
        or not isinstance(value.get("fact_id"), str)
        or value.get("semantic_kind") != "normalized_source_fact"
        or value.get("status") not in {"role_complete", "role_incomplete"}
        or not _identifier(value.get("financial_type"))
        or not isinstance(value.get("annotation_target"), Mapping)
        or not value["annotation_target"]
    ):
        _fail("qualified_projection_fact_v3_contract_invalid")
    case = value.get("case_binding")
    if not isinstance(case, Mapping) or set(case) != {"scope_kind", "scope_id"} or case.get("scope_kind") != "case" or not _identifier(case.get("scope_id")):
        _fail("qualified_projection_fact_v3_case_binding_invalid")
    _validate_binding(value.get("qualified_projection_binding"))
    semantic = value.get("semantic_binding")
    if not isinstance(semantic, Mapping) or set(semantic) != {"dictionary", "role_pack"}:
        _fail("qualified_projection_fact_v3_semantic_binding_invalid")
    for authority in semantic.values():
        if not isinstance(authority, Mapping) or set(authority) != {"authority_id", "semantic_version"} or not all(_identifier(authority.get(key)) for key in authority):
            _fail("qualified_projection_fact_v3_semantic_binding_invalid")
    _validate_roles(value.get("roles"))


def _validate_binding(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != _BINDING_KEYS or not all(_identifier(value.get(key)) for key in _BINDING_KEYS - {"canonical_binding"}):
        _fail("qualified_projection_fact_v3_binding_invalid")
    canonical = value.get("canonical_binding")
    if (
        not isinstance(canonical, Mapping) or set(canonical) != _CANONICAL_KEYS
        or not _identifier(canonical.get("document_id"))
        or not _identifier(canonical.get("canonical_version_id"))
        or not isinstance(canonical.get("canonical_root_sha256"), str)
        or _SHA256.fullmatch(canonical["canonical_root_sha256"]) is None
    ):
        _fail("qualified_projection_fact_v3_canonical_binding_invalid")


def _validate_roles(value: Any) -> None:
    if not isinstance(value, list) or not value:
        _fail("qualified_projection_fact_v3_roles_invalid")
    for role in value:
        source = role.get("source_binding") if isinstance(role, Mapping) else None
        target = source.get("target") if isinstance(source, Mapping) else None
        if (
            not isinstance(role, Mapping) or set(role) != _ROLE_KEYS
            or not _identifier(role.get("role"))
            or role.get("requirement") not in {"required", "optional"}
            or role.get("status") not in {"value", "missing"}
            or (role["status"] == "value" and not isinstance(role.get("value"), str))
            or (role["status"] == "missing" and role.get("value") is not None)
            or not isinstance(source, Mapping) or set(source) != _ROLE_SOURCE_KEYS
            or not isinstance(target, Mapping)
            or not isinstance(source.get("exact_text"), str)
            or not isinstance(source.get("source_literal"), str)
        ):
            _fail("qualified_projection_fact_v3_roles_invalid")
        if target.get("kind") == "table_cell":
            valid = set(target) == {"kind", "node_id", "row", "column"} and _identifier(target.get("node_id")) and isinstance(target.get("row"), int) and isinstance(target.get("column"), int)
        elif target.get("kind") == "user_assertion":
            valid = set(target) == {"kind", "assertion_id"} and role.get("role") == "currency" and _identifier(target.get("assertion_id"))
        else:
            valid = False
        if not valid:
            _fail("qualified_projection_fact_v3_roles_invalid")


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fail(code: str) -> None:
    raise QualifiedProjectionFactV3Error(code)


__all__ = [
    "QUALIFIED_PROJECTION_FACT_V3_SCHEMA_VERSION",
    "QualifiedProjectionFactV3Error",
    "build_qualified_projection_fact_v3",
    "qualified_projection_binding",
    "qualified_projection_fact_v3_id",
    "validate_qualified_projection_fact_v3",
]
