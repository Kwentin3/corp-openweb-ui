"""Immutable Gate 3 financial-role definitions and per-label profiles."""

from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
from importlib import resources
import json
import re
from typing import Any

from .gate3_financial_label_dictionary import (
    GATE3_DICTIONARY_V1_VERSION,
    Gate3FinancialLabelDictionaryFactory,
)


GATE3_ROLE_PACK_SCHEMA_VERSION = (
    "broker_reports_gate3_financial_role_pack_v1"
)
GATE3_ROLE_PACK_ID = "broker-reports-financial-roles"
GATE3_ROLE_PACK_V1_VERSION = "1.0.0"
GATE3_ROLE_PACK_V1_RESOURCE = "gate3_financial_role_pack.v1.json"
GATE3_ROLE_PACK_V1_FILE_SHA256 = (
    "43e98dcbef4637506d79927ef19ae1790f9bcfcb69b0045f97c2af9648cd5ba6"
)

FACTORY_REQUIRED = (
    "Gate3FinancialRolePackFactory.create is the only Gate 3 role definition, "
    "financial-label profile and model-view entrypoint"
)
FORBIDDEN = (
    "Role IDs, required/optional profiles, value-source rules and cardinality "
    "must not be duplicated in Python, prompts, Skills, adapters or RAG"
)

_PUBLISHED_KEYS = {
    "schema_version",
    "role_pack_id",
    "semantic_version",
    "status",
    "published_at",
    "approval",
    "binding_contract",
    "roles",
    "profiles",
}
_APPROVAL_KEYS = {
    "approval_id",
    "decision",
    "approved_by_role",
    "approved_at",
    "basis",
}
_BINDING_CONTRACT_KEYS = {
    "value_source",
    "exact_text_policy",
    "normalized_or_computed_values_allowed",
    "maximum_bindings_per_role_per_fact",
    "missing_status",
}
_ROLE_KEYS = {"role_id", "meaning", "value_kind"}
_PROFILE_KEYS = {"financial_label", "required_roles", "optional_roles"}
_ROLE_ID = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


class Gate3FinancialRolePackError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _PublishedRolePackResource:
    resource_name: str
    file_sha256: str


_PUBLISHED_VERSIONS = {
    GATE3_ROLE_PACK_V1_VERSION: _PublishedRolePackResource(
        resource_name=GATE3_ROLE_PACK_V1_RESOURCE,
        file_sha256=GATE3_ROLE_PACK_V1_FILE_SHA256,
    )
}


class Gate3FinancialRolePack:
    """Load the one immutable owner of Gate 3 role meaning and profiles."""

    def list_published_versions(self) -> tuple[str, ...]:
        return tuple(_PUBLISHED_VERSIONS)

    def load_published(
        self,
        semantic_version: str = GATE3_ROLE_PACK_V1_VERSION,
    ) -> dict[str, Any]:
        resource = _PUBLISHED_VERSIONS.get(semantic_version)
        if resource is None:
            raise Gate3FinancialRolePackError(
                "gate3_role_pack_version_not_published"
            )
        try:
            raw = (
                resources.files(__package__)
                .joinpath(resource.resource_name)
                .read_bytes()
            )
        except (FileNotFoundError, OSError) as exc:
            raise Gate3FinancialRolePackError(
                "gate3_role_pack_resource_unavailable"
            ) from exc
        if hashlib.sha256(raw).hexdigest() != resource.file_sha256:
            raise Gate3FinancialRolePackError(
                "gate3_role_pack_file_hash_mismatch"
            )
        try:
            payload: Any = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise Gate3FinancialRolePackError(
                "gate3_role_pack_json_invalid"
            ) from exc
        _validate_published(payload, expected_version=semantic_version)
        return copy.deepcopy(payload)

    def profile_for_label(
        self,
        financial_label: str,
        semantic_version: str = GATE3_ROLE_PACK_V1_VERSION,
    ) -> dict[str, Any]:
        pack = self.load_published(semantic_version)
        for profile in pack["profiles"]:
            if profile["financial_label"] == financial_label:
                return copy.deepcopy(profile)
        raise Gate3FinancialRolePackError("gate3_role_pack_profile_unknown")

    def render_model_markdown(
        self,
        semantic_version: str = GATE3_ROLE_PACK_V1_VERSION,
    ) -> str:
        pack = self.load_published(semantic_version)
        lines = [
            "# Financial roles",
            "",
            f"Role Pack: `{pack['role_pack_id']}@{pack['semantic_version']}`",
            "",
            "Bindings use only canonical target text. exact_text, when used, "
            "must be a non-empty exact case-sensitive literal substring. "
            "Normalized and computed values are forbidden. Each role has at "
            "most one binding per fact; use status missing when no safe "
            "binding exists.",
            "",
            "## Role definitions",
        ]
        for role in pack["roles"]:
            lines.extend(
                [
                    "",
                    f"### {role['role_id']}",
                    f"- Meaning: {role['meaning']}",
                    f"- Value kind: `{role['value_kind']}`",
                ]
            )
        lines.extend(["", "## Financial-label profiles"])
        for profile in pack["profiles"]:
            required = ", ".join(profile["required_roles"]) or "none"
            optional = ", ".join(profile["optional_roles"]) or "none"
            lines.extend(
                [
                    "",
                    f"### {profile['financial_label']}",
                    f"- Required roles: {required}",
                    f"- Optional roles: {optional}",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"


class Gate3FinancialRolePackFactory:
    @staticmethod
    def create() -> Gate3FinancialRolePack:
        return Gate3FinancialRolePack()


def _validate_published(payload: Any, *, expected_version: str) -> None:
    if not isinstance(payload, dict) or set(payload) != _PUBLISHED_KEYS:
        raise Gate3FinancialRolePackError("gate3_role_pack_shape_invalid")
    if (
        payload.get("schema_version") != GATE3_ROLE_PACK_SCHEMA_VERSION
        or payload.get("role_pack_id") != GATE3_ROLE_PACK_ID
        or payload.get("semantic_version") != expected_version
        or payload.get("status") != "PUBLISHED"
        or not _nonempty(payload.get("published_at"))
    ):
        raise Gate3FinancialRolePackError("gate3_role_pack_identity_invalid")
    approval = payload.get("approval")
    if (
        not isinstance(approval, dict)
        or set(approval) != _APPROVAL_KEYS
        or approval.get("decision") != "APPROVED"
        or any(
            not _nonempty(approval.get(field))
            for field in _APPROVAL_KEYS - {"decision"}
        )
    ):
        raise Gate3FinancialRolePackError("gate3_role_pack_approval_invalid")
    binding = payload.get("binding_contract")
    if (
        not isinstance(binding, dict)
        or set(binding) != _BINDING_CONTRACT_KEYS
        or binding.get("value_source") != "canonical_target_text"
        or binding.get("exact_text_policy")
        != "optional_nonempty_literal_substring"
        or binding.get("normalized_or_computed_values_allowed") is not False
        or binding.get("maximum_bindings_per_role_per_fact") != 1
        or binding.get("missing_status") != "missing"
    ):
        raise Gate3FinancialRolePackError(
            "gate3_role_pack_binding_contract_invalid"
        )

    roles = payload.get("roles")
    if not isinstance(roles, list) or not roles:
        raise Gate3FinancialRolePackError("gate3_role_pack_roles_required")
    role_ids: list[str] = []
    for role in roles:
        if (
            not isinstance(role, dict)
            or set(role) != _ROLE_KEYS
            or not isinstance(role.get("role_id"), str)
            or _ROLE_ID.fullmatch(role["role_id"]) is None
            or not _nonempty(role.get("meaning"))
            or not _nonempty(role.get("value_kind"))
        ):
            raise Gate3FinancialRolePackError(
                "gate3_role_pack_role_invalid"
            )
        role_ids.append(role["role_id"])
    if len(role_ids) != len(set(role_ids)):
        raise Gate3FinancialRolePackError(
            "gate3_role_pack_role_duplicate"
        )

    dictionary = Gate3FinancialLabelDictionaryFactory.create().load_published(
        GATE3_DICTIONARY_V1_VERSION
    )
    dictionary_labels = [item["label_id"] for item in dictionary["labels"]]
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise Gate3FinancialRolePackError(
            "gate3_role_pack_profiles_required"
        )
    profile_labels: list[str] = []
    known_roles = set(role_ids)
    for profile in profiles:
        if not isinstance(profile, dict) or set(profile) != _PROFILE_KEYS:
            raise Gate3FinancialRolePackError(
                "gate3_role_pack_profile_invalid"
            )
        required = profile.get("required_roles")
        optional = profile.get("optional_roles")
        if (
            not isinstance(profile.get("financial_label"), str)
            or not isinstance(required, list)
            or not isinstance(optional, list)
            or any(not isinstance(role, str) for role in [*required, *optional])
            or len(required) != len(set(required))
            or len(optional) != len(set(optional))
            or set(required) & set(optional)
            or not set(required) | set(optional)
            or not (set(required) | set(optional)) <= known_roles
        ):
            raise Gate3FinancialRolePackError(
                "gate3_role_pack_profile_invalid"
            )
        profile_labels.append(profile["financial_label"])
    if profile_labels != dictionary_labels:
        raise Gate3FinancialRolePackError(
            "gate3_role_pack_dictionary_coverage_mismatch"
        )


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_ROLE_PACK_ID",
    "GATE3_ROLE_PACK_SCHEMA_VERSION",
    "GATE3_ROLE_PACK_V1_FILE_SHA256",
    "GATE3_ROLE_PACK_V1_VERSION",
    "Gate3FinancialRolePack",
    "Gate3FinancialRolePackError",
    "Gate3FinancialRolePackFactory",
]
