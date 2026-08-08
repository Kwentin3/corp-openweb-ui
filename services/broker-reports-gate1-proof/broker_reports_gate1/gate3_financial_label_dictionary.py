"""Managed Gate 3 financial-label dictionary lifecycle."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from difflib import unified_diff
import hashlib
from importlib import resources
import json
import re
from typing import Any


GATE3_DICTIONARY_SCHEMA_VERSION = (
    "broker_reports_gate3_financial_label_dictionary_v1"
)
GATE3_DICTIONARY_DRAFT_SCHEMA_VERSION = (
    "broker_reports_gate3_financial_label_dictionary_draft_v1"
)
GATE3_DICTIONARY_APPROVAL_SCHEMA_VERSION = (
    "broker_reports_gate3_financial_label_dictionary_approval_v1"
)
GATE3_DICTIONARY_ID = "broker-reports-financial-labels"
GATE3_DICTIONARY_V1_VERSION = "1.0.0"
GATE3_DICTIONARY_V1_RESOURCE = "gate3_financial_label_dictionary.v1.json"
GATE3_DICTIONARY_V1_FILE_SHA256 = (
    "182e8d7f3604ad3d06d93c4d913df17979f21aeea669123d70c10be9d9652850"
)
GATE3_DICTIONARY_V1_MODEL_VIEW_SHA256 = (
    "b5b89e1b17932c6429b71724667053287e65f7a72b0beec7dcd86cc1190d1b5b"
)
GATE3_DICTIONARY_OPENWEBUI_SKILL_ID = (
    "broker-reports-financial-labels"
)
GATE3_DICTIONARY_OPENWEBUI_TOOL_ID = (
    "broker_reports_financial_label_dictionary"
)
GATE3_DICTIONARY_OPENWEBUI_TOOL_METHOD = (
    "load_financial_label_dictionary"
)

FACTORY_REQUIRED = (
    "Gate3FinancialLabelDictionaryFactory.create is the only Gate 3 financial "
    "label dictionary load, draft, diff, validation and render entrypoint"
)
FORBIDDEN = (
    "The dictionary owner must not read source documents, call a provider, use "
    "RAG, activate a draft, persist annotations or duplicate label meaning in "
    "Prompt, Skill, Tool, Knowledge or renderer code"
)

_PUBLISHED_KEYS = {
    "schema_version",
    "dictionary_id",
    "semantic_version",
    "status",
    "published_at",
    "approval",
    "labels",
}
_APPROVAL_KEYS = {
    "approval_id",
    "decision",
    "approved_by_role",
    "approved_at",
    "basis",
}
_LABEL_KEYS = {
    "label_id",
    "meaning",
    "apply_when",
    "do_not_apply_when",
    "examples",
    "confusable_with",
}
_DRAFT_KEYS = {
    "schema_version",
    "dictionary_id",
    "proposal_id",
    "base_identity",
    "proposed_semantic_version",
    "status",
    "labels",
}
_REVIEW_KEYS = {
    "schema_version",
    "approval_id",
    "decision",
    "approved_by_role",
    "approved_at",
    "basis",
    "draft_sha256",
}
_LABEL_ID = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")


class Gate3FinancialLabelDictionaryError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class _PublishedDictionaryResource:
    resource_name: str
    file_sha256: str


_PUBLISHED_VERSIONS = {
    GATE3_DICTIONARY_V1_VERSION: _PublishedDictionaryResource(
        resource_name=GATE3_DICTIONARY_V1_RESOURCE,
        file_sha256=GATE3_DICTIONARY_V1_FILE_SHA256,
    )
}


class Gate3FinancialLabelDictionary:
    """Load immutable versions from the one financial-label meaning owner.

    Do not duplicate definitions in Python, prompts, Skills, Tools or RAG.
    """

    def list_published_versions(self) -> tuple[str, ...]:
        return tuple(_PUBLISHED_VERSIONS)

    def load_published(
        self,
        semantic_version: str = GATE3_DICTIONARY_V1_VERSION,
    ) -> dict[str, Any]:
        resource = _PUBLISHED_VERSIONS.get(semantic_version)
        if resource is None:
            raise Gate3FinancialLabelDictionaryError(
                "gate3_dictionary_version_not_published"
            )
        try:
            raw = (
                resources.files(__package__)
                .joinpath(resource.resource_name)
                .read_bytes()
            )
        except (FileNotFoundError, OSError) as exc:
            raise Gate3FinancialLabelDictionaryError(
                "gate3_dictionary_published_resource_unavailable"
            ) from exc
        payload = _validate_published_bytes(
            raw,
            expected_version=semantic_version,
            expected_file_sha256=resource.file_sha256,
        )
        return copy.deepcopy(payload)

    def render_model_markdown(
        self,
        semantic_version: str = GATE3_DICTIONARY_V1_VERSION,
    ) -> str:
        dictionary = self.load_published(semantic_version)
        model_view = _render_model_markdown(dictionary)
        if (
            semantic_version == GATE3_DICTIONARY_V1_VERSION
            and _sha256(model_view.encode("utf-8"))
            != GATE3_DICTIONARY_V1_MODEL_VIEW_SHA256
        ):
            raise Gate3FinancialLabelDictionaryError(
                "gate3_dictionary_model_view_hash_mismatch"
            )
        return model_view

    def managed_binding(
        self,
        semantic_version: str = GATE3_DICTIONARY_V1_VERSION,
    ) -> dict[str, Any]:
        """Return stable OpenWebUI projection IDs for the exact version."""

        dictionary = self.load_published(semantic_version)
        model_view = self.render_model_markdown(semantic_version)
        return {
            "schema_version": (
                "broker_reports_gate3_financial_label_managed_binding_v1"
            ),
            "dictionary_identity": {
                "dictionary_id": dictionary["dictionary_id"],
                "semantic_version": dictionary["semantic_version"],
                "file_sha256": (
                    GATE3_DICTIONARY_V1_FILE_SHA256
                    if semantic_version == GATE3_DICTIONARY_V1_VERSION
                    else ""
                ),
                "model_view_sha256": _sha256(
                    model_view.encode("utf-8")
                ),
            },
            "operator_surface": {
                "kind": "openwebui_skill",
                "stable_id": GATE3_DICTIONARY_OPENWEBUI_SKILL_ID,
                "gui_path": "Workspace -> Skills -> Financial labels",
            },
            "exact_delivery": {
                "kind": "openwebui_workspace_tool",
                "stable_id": GATE3_DICTIONARY_OPENWEBUI_TOOL_ID,
                "method": GATE3_DICTIONARY_OPENWEBUI_TOOL_METHOD,
            },
            "runtime_loader": (
                "Gate3FinancialLabelDictionaryFactory.create"
            ),
            "knowledge_rag_used": False,
        }

    def create_draft(
        self,
        *,
        base_semantic_version: str,
        proposed_semantic_version: str,
        proposal_id: str,
    ) -> dict[str, Any]:
        base = self.load_published(base_semantic_version)
        if not _nonempty(proposal_id):
            raise Gate3FinancialLabelDictionaryError(
                "gate3_dictionary_proposal_id_required"
            )
        if (
            not _nonempty(proposed_semantic_version)
            or proposed_semantic_version == base_semantic_version
        ):
            raise Gate3FinancialLabelDictionaryError(
                "gate3_dictionary_proposed_version_invalid"
            )
        draft = {
            "schema_version": GATE3_DICTIONARY_DRAFT_SCHEMA_VERSION,
            "dictionary_id": GATE3_DICTIONARY_ID,
            "proposal_id": proposal_id,
            "base_identity": {
                "dictionary_id": base["dictionary_id"],
                "semantic_version": base["semantic_version"],
            },
            "proposed_semantic_version": proposed_semantic_version,
            "status": "DRAFT",
            "labels": copy.deepcopy(base["labels"]),
        }
        self.validate_draft(draft)
        return draft

    def validate_draft(self, draft: dict[str, Any]) -> dict[str, Any]:
        _validate_draft(draft)
        return {
            "valid": True,
            "labels_total": len(draft["labels"]),
            "draft_sha256": _sha256(_canonical_bytes(draft)),
            "conflicts": [],
        }

    def diff_draft(self, draft: dict[str, Any]) -> str:
        self.validate_draft(draft)
        base_identity = draft["base_identity"]
        base = self.load_published(base_identity["semantic_version"])
        before = _pretty_labels(base["labels"])
        after = _pretty_labels(draft["labels"])
        return "".join(
            unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=f"published-{base['semantic_version']}",
                tofile=f"draft-{draft['proposed_semantic_version']}",
                lineterm="\n",
            )
        )

    def review_template(self, draft: dict[str, Any]) -> dict[str, Any]:
        validation = self.validate_draft(draft)
        return {
            "schema_version": GATE3_DICTIONARY_APPROVAL_SCHEMA_VERSION,
            "approval_id": "",
            "decision": "PENDING",
            "approved_by_role": "",
            "approved_at": "",
            "basis": "",
            "draft_sha256": validation["draft_sha256"],
        }

    def prepare_published_version(
        self,
        *,
        draft: dict[str, Any],
        approval: dict[str, Any],
    ) -> dict[str, Any]:
        validation = self.validate_draft(draft)
        _validate_review_approval(
            approval,
            expected_draft_sha256=validation["draft_sha256"],
        )
        proposed_version = draft["proposed_semantic_version"]
        if proposed_version in _PUBLISHED_VERSIONS:
            raise Gate3FinancialLabelDictionaryError(
                "gate3_dictionary_version_already_published"
            )
        published = {
            "schema_version": GATE3_DICTIONARY_SCHEMA_VERSION,
            "dictionary_id": GATE3_DICTIONARY_ID,
            "semantic_version": proposed_version,
            "status": "PUBLISHED",
            "published_at": approval["approved_at"],
            "approval": {
                key: approval[key]
                for key in (
                    "approval_id",
                    "decision",
                    "approved_by_role",
                    "approved_at",
                    "basis",
                )
            },
            "labels": copy.deepcopy(draft["labels"]),
        }
        _validate_dictionary_material(published["labels"])
        _validate_unpinned_published_payload(published)
        return published

    def serialize_prepared_version(self, published: dict[str, Any]) -> bytes:
        _validate_unpinned_published_payload(published)
        return (
            json.dumps(
                published,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")


class Gate3FinancialLabelDictionaryFactory:
    @staticmethod
    def create() -> Gate3FinancialLabelDictionary:
        return Gate3FinancialLabelDictionary()


def _validate_published_bytes(
    raw: bytes,
    *,
    expected_version: str,
    expected_file_sha256: str,
) -> dict[str, Any]:
    if _sha256(raw) != expected_file_sha256:
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_published_file_hash_mismatch"
        )
    try:
        payload: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_published_json_invalid"
        ) from exc
    _validate_unpinned_published_payload(payload)
    if payload["semantic_version"] != expected_version:
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_published_identity_mismatch"
        )
    return payload


def _validate_unpinned_published_payload(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != _PUBLISHED_KEYS:
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_published_shape_invalid"
        )
    if (
        payload.get("schema_version") != GATE3_DICTIONARY_SCHEMA_VERSION
        or payload.get("dictionary_id") != GATE3_DICTIONARY_ID
        or payload.get("status") != "PUBLISHED"
        or not _nonempty(payload.get("semantic_version"))
        or not _nonempty(payload.get("published_at"))
    ):
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_published_identity_invalid"
        )
    approval = payload.get("approval")
    if (
        not isinstance(approval, dict)
        or set(approval) != _APPROVAL_KEYS
        or approval.get("decision") != "APPROVED"
        or any(not _nonempty(approval.get(key)) for key in _APPROVAL_KEYS - {"decision"})
    ):
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_published_approval_invalid"
        )
    _validate_dictionary_material(payload.get("labels"))


def _validate_draft(draft: Any) -> None:
    if not isinstance(draft, dict) or set(draft) != _DRAFT_KEYS:
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_draft_shape_invalid"
        )
    base_identity = draft.get("base_identity")
    if (
        draft.get("schema_version")
        != GATE3_DICTIONARY_DRAFT_SCHEMA_VERSION
        or draft.get("dictionary_id") != GATE3_DICTIONARY_ID
        or draft.get("status") != "DRAFT"
        or not _nonempty(draft.get("proposal_id"))
        or not _nonempty(draft.get("proposed_semantic_version"))
        or not isinstance(base_identity, dict)
        or set(base_identity) != {"dictionary_id", "semantic_version"}
        or base_identity.get("dictionary_id") != GATE3_DICTIONARY_ID
        or not _nonempty(base_identity.get("semantic_version"))
        or draft.get("proposed_semantic_version")
        == base_identity.get("semantic_version")
    ):
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_draft_identity_invalid"
        )
    _validate_dictionary_material(draft.get("labels"))


def _validate_review_approval(
    approval: Any,
    *,
    expected_draft_sha256: str,
) -> None:
    if (
        not isinstance(approval, dict)
        or set(approval) != _REVIEW_KEYS
        or approval.get("schema_version")
        != GATE3_DICTIONARY_APPROVAL_SCHEMA_VERSION
        or approval.get("decision") != "APPROVED"
        or approval.get("draft_sha256") != expected_draft_sha256
        or any(
            not _nonempty(approval.get(key))
            for key in (
                "approval_id",
                "approved_by_role",
                "approved_at",
                "basis",
            )
        )
    ):
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_human_approval_required"
        )


def _validate_dictionary_material(labels: Any) -> None:
    if not isinstance(labels, list) or not labels:
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_labels_required"
        )
    label_ids: list[str] = []
    example_owner: dict[str, str] = {}
    for label in labels:
        if not isinstance(label, dict) or set(label) != _LABEL_KEYS:
            raise Gate3FinancialLabelDictionaryError(
                "gate3_dictionary_label_shape_invalid"
            )
        label_id = label.get("label_id")
        if not isinstance(label_id, str) or _LABEL_ID.fullmatch(label_id) is None:
            raise Gate3FinancialLabelDictionaryError(
                "gate3_dictionary_label_id_invalid"
            )
        label_ids.append(label_id)
        if not _nonempty(label.get("meaning")):
            raise Gate3FinancialLabelDictionaryError(
                "gate3_dictionary_label_meaning_required"
            )
        for field in (
            "apply_when",
            "do_not_apply_when",
            "examples",
            "confusable_with",
        ):
            values = label.get(field)
            if (
                not isinstance(values, list)
                or not values
                or any(not _nonempty(value) for value in values)
                or len({_normalized(value) for value in values}) != len(values)
            ):
                raise Gate3FinancialLabelDictionaryError(
                    f"gate3_dictionary_label_{field}_invalid"
                )
        if set(map(_normalized, label["apply_when"])) & set(
            map(_normalized, label["do_not_apply_when"])
        ):
            raise Gate3FinancialLabelDictionaryError(
                "gate3_dictionary_label_rule_conflict"
            )
        for example in label["examples"]:
            normalized = _normalized(example)
            owner = example_owner.setdefault(normalized, label_id)
            if owner != label_id:
                raise Gate3FinancialLabelDictionaryError(
                    "gate3_dictionary_cross_label_example_conflict"
                )
    if len(label_ids) != len(set(label_ids)):
        raise Gate3FinancialLabelDictionaryError(
            "gate3_dictionary_label_id_duplicate"
        )


def _render_model_markdown(dictionary: dict[str, Any]) -> str:
    lines = ["# Financial labels"]
    for label in dictionary["labels"]:
        lines.extend(
            [
                "",
                f"## {label['label_id']}",
                "",
                f"Смысл: {label['meaning']}",
                "",
                "Ставить, если:",
                *[f"- {value}" for value in label["apply_when"]],
                "",
                "Не ставить, если:",
                *[f"- {value}" for value in label["do_not_apply_when"]],
                "",
                "Примеры:",
                *[f"- `{value}`" for value in label["examples"]],
                "",
                "Не путать с:",
                *[f"- {value}" for value in label["confusable_with"]],
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _pretty_labels(labels: list[dict[str, Any]]) -> str:
    return json.dumps(
        labels,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ) + "\n"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "GATE3_DICTIONARY_APPROVAL_SCHEMA_VERSION",
    "GATE3_DICTIONARY_DRAFT_SCHEMA_VERSION",
    "GATE3_DICTIONARY_ID",
    "GATE3_DICTIONARY_SCHEMA_VERSION",
    "GATE3_DICTIONARY_V1_FILE_SHA256",
    "GATE3_DICTIONARY_V1_MODEL_VIEW_SHA256",
    "GATE3_DICTIONARY_V1_VERSION",
    "GATE3_DICTIONARY_OPENWEBUI_SKILL_ID",
    "GATE3_DICTIONARY_OPENWEBUI_TOOL_ID",
    "GATE3_DICTIONARY_OPENWEBUI_TOOL_METHOD",
    "Gate3FinancialLabelDictionary",
    "Gate3FinancialLabelDictionaryError",
    "Gate3FinancialLabelDictionaryFactory",
]
