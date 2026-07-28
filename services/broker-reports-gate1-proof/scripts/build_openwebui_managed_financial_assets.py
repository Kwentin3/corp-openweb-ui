#!/usr/bin/env python3
"""Build the deterministic managed OpenWebUI Financial Domain asset family."""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import textwrap
import zlib
from pathlib import Path
from typing import Any

from broker_reports_financial_decision_reason_catalog_contracts import (
    Gate2FinancialDecisionReasonCatalogContractFactory,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
ASSET_ROOT = SERVICE_ROOT / "managed_assets"

SKILL_PATH = ASSET_ROOT / "skills" / "broker_reports_financial_domain_skill.v1.md"
PROMPT_PATH = (
    ASSET_ROOT / "prompts" / "broker_reports_gate2_financial_matching_prompt.v1.md"
)
TOOL_PATH = ASSET_ROOT / "tools" / "broker_reports_financial_semantic_pack_tool.v1.py"
MANIFEST_PATH = ASSET_ROOT / "broker_reports_financial_domain_assets.v1.manifest.json"
MANIFEST_V2_PATH = (
    ASSET_ROOT / "broker_reports_financial_domain_assets.v2.manifest.json"
)
MANIFEST_V2_SCHEMA_PATH = (
    ASSET_ROOT / "broker_reports_financial_domain_assets.v2.manifest.schema.json"
)
DECISION_REASON_ROOT = ASSET_ROOT / "decision_reasons"
DECISION_REASON_CATALOG_PATH = (
    DECISION_REASON_ROOT
    / "broker_reports_gate2_financial_decision_reason_catalog.v1.json"
)
DECISION_REASON_CATALOG_SCHEMA_PATH = (
    DECISION_REASON_ROOT
    / "broker_reports_gate2_financial_decision_reason_catalog.v1.schema.json"
)
DECISION_REASON_CATALOG_CONTRACT_PATH = (
    SCRIPT_DIR / "broker_reports_financial_decision_reason_catalog_contracts.py"
)
PACK_PATH = (
    SERVICE_ROOT / "semantic_packs" / "broker_reports_financial_semantic_pack.v1.json"
)
PACK_SCHEMA_PATH = (
    SERVICE_ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.schema.json"
)
CONSUMER_SCHEMA_PATH = (
    REPO_ROOT
    / "docs"
    / "stage2"
    / "contracts"
    / "BROKER_REPORTS_MANAGED_FINANCIAL_DOMAIN.v1.schema.json"
)
DECISION_CONTRACT_PATH = (
    SERVICE_ROOT / "broker_reports_gate1" / "gate2_financial_evidence_decision.py"
)

PACK_ID = "broker_reports_managed_financial_semantic_pack"
PACK_VERSION = "1.0.0"
PACK_INTEGRITY_SHA256 = (
    "ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8"
)
PACK_CANONICAL_SEMANTIC_BYTES = 9404

TOOL_TEMPLATE = '''"""
title: Broker Reports Financial Semantic Pack
author: Corp OpenWebUI
version: 1.0.0
required_open_webui_version: 0.9.6
"""

from __future__ import annotations

import base64
import hashlib
import json
import zlib
from typing import Any


PACK_ID = "broker_reports_managed_financial_semantic_pack"
PACK_SEMANTIC_VERSION = "1.0.0"
PACK_GIT_BLOB_SHA256 = (
    "__PACK_GIT_BLOB_SHA256__"
)
PACK_INTEGRITY_SHA256 = (
    "ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8"
)
PACK_CANONICAL_SEMANTIC_BYTES = 9404
FACTORY_REQUIRED = (
    "Tools.load_financial_semantic_pack is the only managed OpenWebUI Pack "
    "delivery entrypoint"
)
FORBIDDEN = (
    "The Tool must not read a runtime filesystem path, use network or RAG, "
    "return a partial Pack, or reinterpret financial semantics"
)

_PACK_PAYLOAD_B85 = (
__PACK_PAYLOAD_LINES__
)


class Tools:
    """Expose the exact versioned Financial Semantic Pack to OpenWebUI."""

    def __init__(self) -> None:
        self._pack_json = _verified_pack_json()

    def load_financial_semantic_pack(self) -> str:
        """Return the complete pinned Financial Semantic Pack JSON.

        :return: Exact UTF-8 repository Git-blob Pack content.
        """

        return self._pack_json


def _verified_pack_json() -> str:
    try:
        raw = zlib.decompress(base64.b85decode(_PACK_PAYLOAD_B85))
    except Exception as exc:
        raise RuntimeError("financial_semantic_pack_payload_invalid") from exc
    if hashlib.sha256(raw).hexdigest() != PACK_GIT_BLOB_SHA256:
        raise RuntimeError("financial_semantic_pack_blob_hash_mismatch")

    try:
        payload: Any = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("financial_semantic_pack_json_invalid") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("pack_id") != PACK_ID
        or payload.get("semantic_version") != PACK_SEMANTIC_VERSION
        or payload.get("runtime_activation") is not False
    ):
        raise RuntimeError("financial_semantic_pack_identity_mismatch")

    material = dict(payload)
    supplied_integrity = material.pop("integrity_sha256", None)
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if (
        len(canonical) != PACK_CANONICAL_SEMANTIC_BYTES
        or hashlib.sha256(canonical).hexdigest() != PACK_INTEGRITY_SHA256
        or supplied_integrity != PACK_INTEGRITY_SHA256
    ):
        raise RuntimeError("financial_semantic_pack_integrity_mismatch")
    return raw.decode("utf-8")
'''


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _repo_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _portable_text_blob(path: Path) -> bytes:
    """Return the LF text bytes stored by Git, independent of checkout EOL."""

    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _strict_schema_object(
    properties: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def _pack_identity(pack_bytes: bytes) -> dict[str, Any]:
    payload = json.loads(pack_bytes)
    if not isinstance(payload, dict):
        raise ValueError("managed_asset_pack_object_required")
    material = copy.deepcopy(payload)
    supplied = material.pop("integrity_sha256", None)
    canonical = _canonical_json(material)
    integrity = _sha256(canonical)
    if (
        payload.get("pack_id") != PACK_ID
        or payload.get("semantic_version") != PACK_VERSION
        or payload.get("runtime_activation") is not False
        or supplied != PACK_INTEGRITY_SHA256
        or integrity != PACK_INTEGRITY_SHA256
        or len(canonical) != PACK_CANONICAL_SEMANTIC_BYTES
    ):
        raise ValueError("managed_asset_pack_identity_invalid")
    return {
        "git_blob_sha256": _sha256(pack_bytes),
        "integrity_sha256": integrity,
        "canonical_semantic_bytes": len(canonical),
    }


def _render_tool(pack_bytes: bytes, pack_identity: dict[str, Any]) -> bytes:
    encoded = base64.b85encode(zlib.compress(pack_bytes, level=9)).decode("ascii")
    payload_lines = "\n".join(
        f'    b"{part}"'
        for part in textwrap.wrap(
            encoded,
            width=88,
            break_long_words=True,
            break_on_hyphens=False,
        )
    )
    content = (
        TOOL_TEMPLATE.replace(
            "__PACK_GIT_BLOB_SHA256__",
            pack_identity["git_blob_sha256"],
        )
        .replace("__PACK_PAYLOAD_LINES__", payload_lines)
        .replace("\r\n", "\n")
    )
    return content.encode("utf-8")


def _asset(
    *,
    asset_id: str,
    kind: str,
    path: Path,
    media_type: str,
    content: bytes,
    api_identity: dict[str, Any],
) -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "kind": kind,
        "semantic_version": "1.0.0",
        "repository_relative_path": _repo_path(path),
        "media_type": media_type,
        "git_blob_sha256": _sha256(content),
        "activation": "repository_managed_not_live",
        "api_identity": api_identity,
    }


def _dependency(
    *,
    dependency_id: str,
    kind: str,
    identity: str,
    path: Path,
    content: bytes,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "dependency_id": dependency_id,
        "kind": kind,
        "contract_identity": identity,
        "repository_relative_path": _repo_path(path),
        "git_blob_sha256": _sha256(content),
        **(extra or {}),
    }


def _render_manifest(
    *,
    skill_bytes: bytes,
    prompt_bytes: bytes,
    tool_bytes: bytes,
    pack_bytes: bytes,
    pack_identity: dict[str, Any],
) -> bytes:
    pack_schema_bytes = _portable_text_blob(PACK_SCHEMA_PATH)
    consumer_schema_bytes = _portable_text_blob(CONSUMER_SCHEMA_PATH)
    decision_contract_bytes = _portable_text_blob(DECISION_CONTRACT_PATH)
    manifest = {
        "schema_version": ("broker_reports_financial_domain_managed_asset_manifest_v1"),
        "family_id": "broker_reports_gate2_financial_domain_assets",
        "semantic_version": "1.0.0",
        "authority_status": "target_normative_not_live",
        "runtime_activation": False,
        "hash_boundary": "git_blob_bytes",
        "openwebui": {
            "distribution": "open-webui",
            "target_version": "0.9.6",
            "upstream_tag": "v0.9.6",
            "skill_api": "/api/v1/skills",
            "prompt_api": "/api/v1/prompts",
            "tool_api": "/api/v1/tools",
        },
        "assets": [
            _asset(
                asset_id="broker_reports_financial_domain_skill",
                kind="openwebui_skill",
                path=SKILL_PATH,
                media_type="text/markdown",
                content=skill_bytes,
                api_identity={
                    "id": "broker-reports-financial-domain-matching",
                    "name": "Broker Reports Financial Domain Matching",
                    "description": (
                        "Pack-only method for bounded Gate 2 financial matching"
                    ),
                    "is_active": True,
                    "meta": {
                        "tags": [
                            "broker-reports",
                            "financial-domain",
                            "managed",
                        ]
                    },
                },
            ),
            _asset(
                asset_id="broker_reports_gate2_financial_matching_prompt",
                kind="openwebui_prompt",
                path=PROMPT_PATH,
                media_type="text/markdown",
                content=prompt_bytes,
                api_identity={
                    "id": "broker-reports-gate2-financial-matching-v1",
                    "name": "Broker Reports Gate 2 Financial Matching v1",
                    "description": (
                        "One bounded Pack-authoritative matching operation"
                    ),
                    "command": "broker_gate2_financial_match_v1",
                    "version_id": "1.0.0",
                    "is_active": True,
                    "meta": {
                        "structured_output_required": True,
                        "output_schema_version": (
                            "broker_reports_gate2_financial_evidence_decision_v1"
                        ),
                    },
                },
            ),
            _asset(
                asset_id="broker_reports_financial_semantic_pack_tool",
                kind="openwebui_workspace_tool",
                path=TOOL_PATH,
                media_type="text/x-python",
                content=tool_bytes,
                api_identity={
                    "id": "broker_reports_financial_semantic_pack",
                    "name": "Broker Reports Financial Semantic Pack",
                    "description": (
                        "Returns the complete byte-exact pinned Semantic Pack"
                    ),
                    "is_active": True,
                    "meta": {
                        "tool_method": "load_financial_semantic_pack",
                        "network_access": False,
                    },
                },
            ),
        ],
        "dependencies": [
            _dependency(
                dependency_id="broker_reports_financial_semantic_pack",
                kind="semantic_pack",
                identity=("broker_reports_managed_financial_semantic_pack@1.0.0"),
                path=PACK_PATH,
                content=pack_bytes,
                extra={
                    "semantic_version": "1.0.0",
                    "semantic_integrity_sha256": pack_identity["integrity_sha256"],
                    "canonical_semantic_bytes": pack_identity[
                        "canonical_semantic_bytes"
                    ],
                },
            ),
            _dependency(
                dependency_id="broker_reports_financial_semantic_pack_schema",
                kind="semantic_pack_schema",
                identity="broker_reports_financial_semantic_pack_v1",
                path=PACK_SCHEMA_PATH,
                content=pack_schema_bytes,
            ),
            _dependency(
                dependency_id="broker_reports_managed_financial_domain_schema",
                kind="consumer_contract_schema",
                identity=("broker_reports_managed_financial_domain_contract_v1"),
                path=CONSUMER_SCHEMA_PATH,
                content=consumer_schema_bytes,
            ),
            _dependency(
                dependency_id="broker_reports_financial_decision_contract",
                kind="decision_contract_source",
                identity=("broker_reports_gate2_financial_evidence_decision_v1"),
                path=DECISION_CONTRACT_PATH,
                content=decision_contract_bytes,
            ),
        ],
        "composition": {
            "method_asset_id": "broker_reports_financial_domain_skill",
            "operation_asset_id": ("broker_reports_gate2_financial_matching_prompt"),
            "pack_loader_asset_id": ("broker_reports_financial_semantic_pack_tool"),
            "pack_loader_method": "load_financial_semantic_pack",
            "semantic_pack_dependency_id": ("broker_reports_financial_semantic_pack"),
            "strict_output_contract": (
                "broker_reports_gate2_financial_evidence_decision_v1"
            ),
            "bounded_input_placeholder": ("{{financial_semantic_matching_input_json}}"),
        },
        "authority": {
            "financial_semantic_authority_dependency_id": (
                "broker_reports_financial_semantic_pack"
            ),
            "full_pack_required": True,
            "rag_only_authority_allowed": False,
            "knowledge_authority_allowed": False,
            "python_type_meanings_allowed": False,
            "prompt_type_meanings_allowed": False,
        },
        "supporting_knowledge": [],
    }
    manifest["manifest_sha256"] = _sha256(_canonical_json(manifest))
    return (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _render_manifest_v2(
    *,
    manifest_v1_bytes: bytes,
    catalog_bytes: bytes,
    catalog_schema_bytes: bytes,
    catalog_contract_bytes: bytes,
    catalog_snapshot: Any,
) -> bytes:
    manifest_v1 = json.loads(manifest_v1_bytes)
    if (
        not isinstance(manifest_v1, dict)
        or manifest_v1.get("schema_version")
        != "broker_reports_financial_domain_managed_asset_manifest_v1"
        or manifest_v1.get("semantic_version") != "1.0.0"
        or manifest_v1.get("runtime_activation") is not False
    ):
        raise ValueError("managed_asset_v1_rollback_identity_invalid")
    manifest = {
        "schema_version": ("broker_reports_financial_domain_managed_asset_manifest_v2"),
        "family_id": manifest_v1["family_id"],
        "semantic_version": "1.1.0",
        "authority_status": "target_normative_not_live",
        "runtime_activation": False,
        "lifecycle": {
            "status": "draft",
            "previous_family_semantic_version": "1.0.0",
            "draft_rollback": "discard_without_runtime_mutation",
            "active_rollback": ("select_previous_validated_immutable_family_version"),
            "rollback_manifest_schema_version": manifest_v1["schema_version"],
            "rollback_manifest_sha256": manifest_v1["manifest_sha256"],
            "rollback_manifest_git_blob_sha256": _sha256(manifest_v1_bytes),
            "live_publisher_implemented": False,
        },
        "hash_boundary": "git_blob_bytes",
        "openwebui": copy.deepcopy(manifest_v1["openwebui"]),
        "assets": copy.deepcopy(manifest_v1["assets"]),
        "dependencies": [
            *copy.deepcopy(manifest_v1["dependencies"]),
            _dependency(
                dependency_id=(
                    "broker_reports_gate2_financial_decision_reason_catalog"
                ),
                kind="decision_reason_catalog",
                identity=(
                    "broker_reports_gate2_financial_decision_reason_catalog@1.0.0"
                ),
                path=DECISION_REASON_CATALOG_PATH,
                content=catalog_bytes,
                extra={
                    "semantic_version": catalog_snapshot.semantic_version,
                    "semantic_integrity_sha256": (catalog_snapshot.integrity_sha256),
                    "canonical_semantic_bytes": (
                        catalog_snapshot.canonical_semantic_bytes
                    ),
                    "lifecycle_status": (catalog_snapshot.lifecycle_status),
                    "runtime_activation": (catalog_snapshot.runtime_activation),
                },
            ),
            _dependency(
                dependency_id=(
                    "broker_reports_gate2_financial_decision_reason_catalog_schema"
                ),
                kind="decision_reason_catalog_schema",
                identity=("broker_reports_gate2_financial_decision_reason_catalog_v1"),
                path=DECISION_REASON_CATALOG_SCHEMA_PATH,
                content=catalog_schema_bytes,
            ),
            _dependency(
                dependency_id=(
                    "broker_reports_gate2_financial_decision_reason_catalog_contract"
                ),
                kind="decision_reason_catalog_contract_source",
                identity=(
                    "broker_reports_gate2_financial_decision_reason_"
                    "catalog_contracts_v1"
                ),
                path=DECISION_REASON_CATALOG_CONTRACT_PATH,
                content=catalog_contract_bytes,
            ),
        ],
        "composition": {
            **copy.deepcopy(manifest_v1["composition"]),
            "decision_reason_catalog_dependency_id": (
                "broker_reports_gate2_financial_decision_reason_catalog"
            ),
            "decision_reason_catalog_schema_dependency_id": (
                "broker_reports_gate2_financial_decision_reason_catalog_schema"
            ),
            "decision_reason_catalog_contract_dependency_id": (
                "broker_reports_gate2_financial_decision_reason_catalog_contract"
            ),
        },
        "authority": {
            **copy.deepcopy(manifest_v1["authority"]),
            "decision_reason_code_authority_dependency_id": (
                "broker_reports_financial_decision_contract"
            ),
            "decision_reason_meaning_authority_dependency_id": (
                "broker_reports_gate2_financial_decision_reason_catalog"
            ),
            "decision_reason_schema_authority_dependency_id": (
                "broker_reports_gate2_financial_decision_reason_catalog_contract"
            ),
        },
        "supporting_knowledge": [],
    }
    manifest["manifest_sha256"] = _sha256(_canonical_json(manifest))
    return (
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _render_manifest_v2_schema() -> bytes:
    sha256 = {
        "type": "string",
        "pattern": "^[0-9a-f]{64}$",
    }
    safe_id = {
        "type": "string",
        "pattern": "^[a-z][a-z0-9_.:-]{2,127}$",
    }
    repository_path = {
        "type": "string",
        "minLength": 3,
        "maxLength": 260,
        "pattern": ("^(?!/)(?!.*(?:^|/)\\.\\.(?:/|$))(?!.*\\\\)[A-Za-z0-9_.\\-/]+$"),
    }
    api_identity = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "name",
        ],
        "properties": {
            "id": {
                "type": "string",
                "minLength": 3,
                "maxLength": 128,
            },
            "name": {
                "type": "string",
                "minLength": 3,
                "maxLength": 160,
            },
            "description": {
                "type": "string",
                "minLength": 3,
                "maxLength": 500,
            },
            "command": {
                "type": "string",
                "pattern": "^[a-z][a-z0-9_-]{2,127}$",
            },
            "version_id": {"const": "1.0.0"},
            "is_active": {"const": True},
            "meta": {"type": "object"},
        },
    }
    asset = _strict_schema_object(
        {
            "asset_id": copy.deepcopy(safe_id),
            "kind": {
                "enum": [
                    "openwebui_skill",
                    "openwebui_prompt",
                    "openwebui_workspace_tool",
                ]
            },
            "semantic_version": {"const": "1.0.0"},
            "repository_relative_path": copy.deepcopy(repository_path),
            "media_type": {
                "enum": [
                    "text/markdown",
                    "text/x-python",
                ]
            },
            "git_blob_sha256": copy.deepcopy(sha256),
            "activation": {"const": "repository_managed_not_live"},
            "api_identity": api_identity,
        }
    )
    dependency_properties = {
        "dependency_id": copy.deepcopy(safe_id),
        "kind": {
            "enum": [
                "semantic_pack",
                "semantic_pack_schema",
                "consumer_contract_schema",
                "decision_contract_source",
                "decision_reason_catalog",
                "decision_reason_catalog_schema",
                "decision_reason_catalog_contract_source",
            ]
        },
        "contract_identity": {
            "type": "string",
            "minLength": 3,
            "maxLength": 180,
        },
        "repository_relative_path": copy.deepcopy(repository_path),
        "git_blob_sha256": copy.deepcopy(sha256),
        "semantic_version": {"const": "1.0.0"},
        "semantic_integrity_sha256": copy.deepcopy(sha256),
        "canonical_semantic_bytes": {
            "type": "integer",
            "minimum": 1,
        },
        "lifecycle_status": {"const": "draft"},
        "runtime_activation": {"const": False},
    }
    dependency = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "dependency_id",
            "kind",
            "contract_identity",
            "repository_relative_path",
            "git_blob_sha256",
        ],
        "properties": dependency_properties,
    }
    lifecycle = _strict_schema_object(
        {
            "status": {"const": "draft"},
            "previous_family_semantic_version": {"const": "1.0.0"},
            "draft_rollback": {"const": "discard_without_runtime_mutation"},
            "active_rollback": {
                "const": ("select_previous_validated_immutable_family_version")
            },
            "rollback_manifest_schema_version": {
                "const": ("broker_reports_financial_domain_managed_asset_manifest_v1")
            },
            "rollback_manifest_sha256": copy.deepcopy(sha256),
            "rollback_manifest_git_blob_sha256": copy.deepcopy(sha256),
            "live_publisher_implemented": {"const": False},
        }
    )
    composition = {
        "method_asset_id": "broker_reports_financial_domain_skill",
        "operation_asset_id": ("broker_reports_gate2_financial_matching_prompt"),
        "pack_loader_asset_id": ("broker_reports_financial_semantic_pack_tool"),
        "pack_loader_method": "load_financial_semantic_pack",
        "semantic_pack_dependency_id": ("broker_reports_financial_semantic_pack"),
        "strict_output_contract": (
            "broker_reports_gate2_financial_evidence_decision_v1"
        ),
        "bounded_input_placeholder": ("{{financial_semantic_matching_input_json}}"),
        "decision_reason_catalog_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog"
        ),
        "decision_reason_catalog_schema_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog_schema"
        ),
        "decision_reason_catalog_contract_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog_contract"
        ),
    }
    authority = {
        "financial_semantic_authority_dependency_id": (
            "broker_reports_financial_semantic_pack"
        ),
        "full_pack_required": True,
        "rag_only_authority_allowed": False,
        "knowledge_authority_allowed": False,
        "python_type_meanings_allowed": False,
        "prompt_type_meanings_allowed": False,
        "decision_reason_code_authority_dependency_id": (
            "broker_reports_financial_decision_contract"
        ),
        "decision_reason_meaning_authority_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog"
        ),
        "decision_reason_schema_authority_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog_contract"
        ),
    }
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:broker-reports:managed-assets:financial-domain:v2",
        "title": ("Broker Reports Financial Domain managed asset family v2"),
        **_strict_schema_object(
            {
                "schema_version": {
                    "const": (
                        "broker_reports_financial_domain_managed_asset_manifest_v2"
                    )
                },
                "family_id": {"const": "broker_reports_gate2_financial_domain_assets"},
                "semantic_version": {"const": "1.1.0"},
                "authority_status": {"const": "target_normative_not_live"},
                "runtime_activation": {"const": False},
                "lifecycle": lifecycle,
                "hash_boundary": {"const": "git_blob_bytes"},
                "openwebui": {
                    "const": {
                        "distribution": "open-webui",
                        "target_version": "0.9.6",
                        "upstream_tag": "v0.9.6",
                        "skill_api": "/api/v1/skills",
                        "prompt_api": "/api/v1/prompts",
                        "tool_api": "/api/v1/tools",
                    }
                },
                "assets": {
                    "type": "array",
                    "minItems": 3,
                    "maxItems": 3,
                    "uniqueItems": True,
                    "items": asset,
                },
                "dependencies": {
                    "type": "array",
                    "minItems": 7,
                    "maxItems": 7,
                    "uniqueItems": True,
                    "items": dependency,
                },
                "composition": {"const": composition},
                "authority": {"const": authority},
                "supporting_knowledge": {
                    "const": [],
                },
                "manifest_sha256": copy.deepcopy(sha256),
            }
        ),
    }
    return (
        json.dumps(
            schema,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def build() -> tuple[bytes, bytes]:
    skill_bytes = _portable_text_blob(SKILL_PATH)
    prompt_bytes = _portable_text_blob(PROMPT_PATH)
    pack_bytes = _portable_text_blob(PACK_PATH)
    pack_identity = _pack_identity(pack_bytes)
    tool_bytes = _render_tool(pack_bytes, pack_identity)
    manifest_bytes = _render_manifest(
        skill_bytes=skill_bytes,
        prompt_bytes=prompt_bytes,
        tool_bytes=tool_bytes,
        pack_bytes=pack_bytes,
        pack_identity=pack_identity,
    )
    return tool_bytes, manifest_bytes


def build_decision_reason_catalog_family_v2() -> tuple[bytes, bytes, bytes]:
    decision_contract_bytes = _portable_text_blob(DECISION_CONTRACT_PATH)
    decision_contract_source = decision_contract_bytes.decode("utf-8")
    factory = Gate2FinancialDecisionReasonCatalogContractFactory(
        decision_contract_source=decision_contract_source
    )
    catalog_bytes = _portable_text_blob(DECISION_REASON_CATALOG_PATH)
    try:
        catalog_payload = json.loads(catalog_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("managed_decision_reason_catalog_json_invalid") from exc
    catalog_snapshot = factory.create(catalog=catalog_payload)
    catalog_schema_bytes = (
        json.dumps(
            factory.schema(),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    catalog_contract_bytes = _portable_text_blob(DECISION_REASON_CATALOG_CONTRACT_PATH)
    _, manifest_v1_bytes = build()
    manifest_v2_bytes = _render_manifest_v2(
        manifest_v1_bytes=manifest_v1_bytes,
        catalog_bytes=catalog_bytes,
        catalog_schema_bytes=catalog_schema_bytes,
        catalog_contract_bytes=catalog_contract_bytes,
        catalog_snapshot=catalog_snapshot,
    )
    manifest_v2_schema_bytes = _render_manifest_v2_schema()
    return (
        catalog_schema_bytes,
        manifest_v2_bytes,
        manifest_v2_schema_bytes,
    )


def _write_or_check(path: Path, expected: bytes, *, check: bool) -> None:
    if check:
        if not path.is_file() or _portable_text_blob(path) != expected:
            raise ValueError(
                "managed_asset_generated_content_mismatch:" + _repo_path(path)
            )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Fail unless generated Tool, schemas, and family manifests "
            "match their Git-blob text."
        ),
    )
    args = parser.parse_args()
    tool_bytes, manifest_bytes = build()
    (
        catalog_schema_bytes,
        manifest_v2_bytes,
        manifest_v2_schema_bytes,
    ) = build_decision_reason_catalog_family_v2()
    _write_or_check(TOOL_PATH, tool_bytes, check=args.check)
    _write_or_check(MANIFEST_PATH, manifest_bytes, check=args.check)
    _write_or_check(
        DECISION_REASON_CATALOG_SCHEMA_PATH,
        catalog_schema_bytes,
        check=args.check,
    )
    _write_or_check(
        MANIFEST_V2_PATH,
        manifest_v2_bytes,
        check=args.check,
    )
    _write_or_check(
        MANIFEST_V2_SCHEMA_PATH,
        manifest_v2_schema_bytes,
        check=args.check,
    )
    print(
        json.dumps(
            {
                "status": "passed",
                "mode": "check" if args.check else "write",
                "hash_boundary": "git_blob_bytes",
                "tool_git_blob_sha256": _sha256(tool_bytes),
                "manifest_git_blob_sha256": _sha256(manifest_bytes),
                "decision_reason_catalog_schema_git_blob_sha256": (
                    _sha256(catalog_schema_bytes)
                ),
                "manifest_v2_git_blob_sha256": _sha256(manifest_v2_bytes),
                "manifest_v2_schema_git_blob_sha256": _sha256(manifest_v2_schema_bytes),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
