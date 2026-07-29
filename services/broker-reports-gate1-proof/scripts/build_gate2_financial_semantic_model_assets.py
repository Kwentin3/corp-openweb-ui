#!/usr/bin/env python3
"""Build the closed-world Gate 2 model projection of managed financial assets."""

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

from broker_reports_financial_decision_reason_catalog_v2_contracts import (
    Gate2FinancialDecisionReasonCatalogV2ContractFactory,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
ASSET_ROOT = SERVICE_ROOT / "managed_assets"
RUNTIME_PATH = (
    SERVICE_ROOT
    / "broker_reports_gate1"
    / "gate2_financial_semantic_model_assets.py"
)
PACK_PATH = (
    SERVICE_ROOT
    / "semantic_packs"
    / "broker_reports_financial_semantic_pack.v1.json"
)
MANIFEST_PATH = (
    ASSET_ROOT / "broker_reports_financial_domain_assets.v1.manifest.json"
)
CONTEXT_V2_MANIFEST_PATH = (
    ASSET_ROOT / "broker_reports_financial_domain_assets.v2.manifest.json"
)
MINIMAL_MANAGED_MANIFEST_PATH = (
    ASSET_ROOT / "broker_reports_financial_domain_assets.v3.manifest.json"
)
DECISION_REASON_CATALOG_PATH = (
    ASSET_ROOT
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v1.json"
)
DECISION_REASON_CATALOG_V2_PATH = (
    ASSET_ROOT
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v2.json"
)
DECISION_REASON_CATALOG_V2_SCHEMA_PATH = (
    ASSET_ROOT
    / "decision_reasons"
    / "broker_reports_gate2_financial_decision_reason_catalog.v2.schema.json"
)
DECISION_REASON_CATALOG_V2_CONTRACT_PATH = (
    SCRIPT_DIR
    / "broker_reports_financial_decision_reason_catalog_v2_contracts.py"
)
SKILL_PATH = (
    ASSET_ROOT
    / "skills"
    / "broker_reports_financial_domain_skill.v1.md"
)
PROMPT_PATH = (
    ASSET_ROOT
    / "prompts"
    / "broker_reports_gate2_financial_matching_prompt.v1.md"
)

PACK_ID = "broker_reports_managed_financial_semantic_pack"
PACK_VERSION = "1.0.0"
PACK_INTEGRITY_SHA256 = (
    "ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8"
)
PACK_CANONICAL_SEMANTIC_BYTES = 9404
CONTEXT_V2_MANAGED_ASSET_FAMILY_VERSION = "1.1.0"
CONTEXT_V2_MANAGED_ASSET_FAMILY_MANIFEST_SHA256 = (
    "4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d"
)
MINIMAL_MANAGED_ASSET_FAMILY_VERSION = "1.2.0"
MINIMAL_MANAGED_PROJECTION_PROFILE_ID = (
    "broker_reports_gate2_minimal_managed_projection_v1_candidate"
)
MINIMAL_MANAGED_PROJECTION_PROFILE_VERSION = "1.0.0"
DECISION_REASON_CATALOG_ID = (
    "broker_reports_gate2_financial_decision_reason_catalog"
)
DECISION_REASON_CATALOG_VERSION = "1.0.0"
DECISION_REASON_CATALOG_INTEGRITY_SHA256 = (
    "d7290593410cafd6b35281ed3a6159802f0d7e87b7a085f3ec2cd2b46f4a3e15"
)
DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES = 3603
DECISION_CODE_CONTRACT_VERSION = (
    "broker_reports_gate2_financial_evidence_decision_v1"
)
REGISTRY_VERSION = "broker_reports_gate2_financial_evidence_registry_v1"
REGISTRY_SHA256 = (
    "0bac59aad259b9e11a5037bb73b09642c2a87fd2baca36b8e4db7c5d5e852ac8"
)
DECISION_REASON_CODES = frozenset(
    {"ambiguous_registry_type", "no_registry_type"}
)
SKILL_ASSET_ID = "broker_reports_financial_domain_skill"
PROMPT_ASSET_ID = "broker_reports_gate2_financial_matching_prompt"
PROMPT_MARKER = "{{financial_semantic_matching_input_json}}"

RUNTIME_TEMPLATE = '''from __future__ import annotations

import base64
import copy
import hashlib
import json
import zlib
from typing import Any


SEMANTIC_MODEL_ASSET_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_model_assets_v1"
)
PACK_ID = "broker_reports_managed_financial_semantic_pack"
PACK_SEMANTIC_VERSION = "1.0.0"
PACK_GIT_BLOB_SHA256 = (
    "__PACK_GIT_BLOB_SHA256__"
)
PACK_INTEGRITY_SHA256 = (
    "ab0b5aaaa4cd8133ab26d7dce8e501770c2d14f2c1bd2205cbad3fa2c6e0e7f8"
)
PACK_CANONICAL_SEMANTIC_BYTES = 9404
MANAGED_PROMPT_GIT_BLOB_SHA256 = (
    "__PROMPT_GIT_BLOB_SHA256__"
)
MANAGED_ASSET_IDENTITIES_SHA256 = (
    "__MANAGED_ASSET_IDENTITIES_SHA256__"
)
MANAGED_PROMPT_INPUT_MARKER = (
    "{{financial_semantic_matching_input_json}}"
)
FACTORY_REQUIRED = (
    "load_gate2_financial_semantic_model_assets is the only closed-world "
    "managed financial model-asset projection entrypoint"
)
FORBIDDEN = (
    "The projection must not read runtime files, use network or RAG, omit "
    "Pack semantic entries, expose repository paths, or reinterpret meaning"
)

_PACK_PAYLOAD_B85 = (
__PACK_PAYLOAD_LINES__
)
_PROMPT_PAYLOAD_B85 = (
__PROMPT_PAYLOAD_LINES__
)
_IDENTITIES_PAYLOAD_B85 = (
__IDENTITIES_PAYLOAD_LINES__
)

__CONTEXT_V2_RUNTIME_FRAGMENT__
__MINIMAL_MANAGED_RUNTIME_FRAGMENT__


def load_gate2_financial_semantic_model_assets(
    *,
    profile: str = "active",
) -> dict[str, Any]:
    """Return one exact closed-world managed-asset projection profile."""

    pack = _verified_pack()
    prompt_content = _verified_prompt()
    managed_assets = _verified_identities()
    active_assets = {
        "schema_version": SEMANTIC_MODEL_ASSET_SCHEMA_VERSION,
        "semantic_pack": {
            "schema_version": pack["schema_version"],
            "pack_id": pack["pack_id"],
            "semantic_version": pack["semantic_version"],
            "managed_asset_ref": pack["managed_asset_ref"],
            "consumer_contract_version": pack[
                "consumer_contract_version"
            ],
            "integrity_sha256": pack["integrity_sha256"],
            "full_compact_snapshot": copy.deepcopy(
                pack["full_compact_snapshot"]
            ),
        },
        "managed_assets": copy.deepcopy(managed_assets),
        "prompt_content": prompt_content,
        "prompt_ref": (
            "openwebui:"
            + managed_assets["prompt"]["api_identity"]["id"]
            + "@"
            + managed_assets["prompt"]["api_identity"]["version_id"]
        ),
        "prompt_git_blob_sha256": MANAGED_PROMPT_GIT_BLOB_SHA256,
    }
    if profile == "active":
        return active_assets
    if profile == "context_v2_candidate":
        return _context_v2_candidate_assets(
            active_pack=active_assets["semantic_pack"],
        )
    if profile == "minimal_model_surface_v1_candidate":
        return _minimal_managed_projection_assets(
            full_pack=pack,
        )
    raise RuntimeError("financial_semantic_model_asset_profile_unknown")


def _verified_pack() -> dict[str, Any]:
    raw = _decompress(_PACK_PAYLOAD_B85, "financial_semantic_pack")
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
        or not isinstance(payload.get("full_compact_snapshot"), list)
        or not payload["full_compact_snapshot"]
    ):
        raise RuntimeError("financial_semantic_pack_identity_mismatch")
    material = copy.deepcopy(payload)
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
        or hashlib.sha256(canonical).hexdigest()
        != PACK_INTEGRITY_SHA256
        or supplied_integrity != PACK_INTEGRITY_SHA256
    ):
        raise RuntimeError("financial_semantic_pack_integrity_mismatch")
    return payload


def _verified_prompt() -> str:
    raw = _decompress(
        _PROMPT_PAYLOAD_B85,
        "financial_semantic_prompt",
    )
    if hashlib.sha256(raw).hexdigest() != MANAGED_PROMPT_GIT_BLOB_SHA256:
        raise RuntimeError("financial_semantic_prompt_hash_mismatch")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RuntimeError("financial_semantic_prompt_utf8_invalid") from exc
    if content.count(MANAGED_PROMPT_INPUT_MARKER) != 1:
        raise RuntimeError("financial_semantic_prompt_marker_invalid")
    return content


def _verified_identities() -> dict[str, Any]:
    raw = _decompress(
        _IDENTITIES_PAYLOAD_B85,
        "financial_semantic_asset_identities",
    )
    if hashlib.sha256(raw).hexdigest() != MANAGED_ASSET_IDENTITIES_SHA256:
        raise RuntimeError("financial_semantic_asset_identities_hash_mismatch")
    try:
        identities: Any = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "financial_semantic_asset_identities_json_invalid"
        ) from exc
    if (
        not isinstance(identities, dict)
        or set(identities) != {
            "family_id",
            "manifest_sha256",
            "semantic_version",
            "skill",
            "prompt",
        }
        or identities.get("family_id")
        != "broker_reports_gate2_financial_domain_assets"
        or identities.get("semantic_version") != "1.0.0"
        or identities.get("prompt", {}).get("git_blob_sha256")
        != MANAGED_PROMPT_GIT_BLOB_SHA256
        or identities.get("skill", {}).get("asset_id")
        != "broker_reports_financial_domain_skill"
        or identities.get("prompt", {}).get("asset_id")
        != "broker_reports_gate2_financial_matching_prompt"
    ):
        raise RuntimeError("financial_semantic_asset_identities_invalid")
    return identities


def _decompress(payload: bytes, label: str) -> bytes:
    try:
        return zlib.decompress(base64.b85decode(payload))
    except Exception as exc:
        raise RuntimeError(label + "_payload_invalid") from exc
'''

CONTEXT_V2_RUNTIME_TEMPLATE = '''
CONTEXT_V2_MODEL_ASSET_SCHEMA_VERSION = (
    "broker_reports_gate2_financial_semantic_context_v2_assets_v1"
)
MANAGED_ASSET_FAMILY_ID = "broker_reports_gate2_financial_domain_assets"
MANAGED_ASSET_FAMILY_VERSION = "1.1.0"
MANAGED_ASSET_FAMILY_MANIFEST_SHA256 = (
    "4e5328554056741ecb783d130a5fd43034a6876484a25c98dfdd5e68bf76499d"
)
DECISION_REASON_CATALOG_ID = (
    "broker_reports_gate2_financial_decision_reason_catalog"
)
DECISION_REASON_CATALOG_VERSION = "1.0.0"
DECISION_REASON_CATALOG_INTEGRITY_SHA256 = (
    "d7290593410cafd6b35281ed3a6159802f0d7e87b7a085f3ec2cd2b46f4a3e15"
)
DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES = 3603
DECISION_CODE_CONTRACT_VERSION = (
    "broker_reports_gate2_financial_evidence_decision_v1"
)
CONTEXT_V2_CANDIDATE_PAYLOAD_SHA256 = (
    "__CONTEXT_V2_CANDIDATE_PAYLOAD_SHA256__"
)
CONTEXT_V2_CANDIDATE_REQUIRED = (
    "load_gate2_financial_semantic_model_assets remains the only "
    "closed-world managed financial model-asset projection entrypoint"
)
CONTEXT_V2_CANDIDATE_FORBIDDEN = (
    "The non-active candidate asset projection must not read runtime files, "
    "use network or RAG, duplicate Pack meaning, activate family v2, expose "
    "repository paths, or reinterpret reason semantics"
)

_CONTEXT_V2_CANDIDATE_PAYLOAD_B85 = (
__CONTEXT_V2_CANDIDATE_PAYLOAD_LINES__
)


def _context_v2_candidate_assets(
    *,
    active_pack: dict[str, Any],
) -> dict[str, Any]:
    """Return the verified non-active V2 family, Pack baseline, and reasons."""

    active_pack = copy.deepcopy(active_pack)
    candidate = _verified_candidate_payload()
    expected_pack_identity = candidate["semantic_pack_identity"]
    if (
        not isinstance(active_pack, dict)
        or active_pack.get("pack_id") != PACK_ID
        or active_pack.get("semantic_version") != PACK_SEMANTIC_VERSION
        or active_pack.get("integrity_sha256") != PACK_INTEGRITY_SHA256
        or expected_pack_identity
        != {
            "pack_id": PACK_ID,
            "semantic_version": PACK_SEMANTIC_VERSION,
            "integrity_sha256": PACK_INTEGRITY_SHA256,
        }
        or not isinstance(active_pack.get("full_compact_snapshot"), list)
        or not active_pack["full_compact_snapshot"]
    ):
        raise RuntimeError("financial_semantic_context_v2_pack_identity_mismatch")
    baseline = candidate["semantic_pack_source_baseline"]
    type_ids = [
        item.get("input_type_id")
        for item in active_pack["full_compact_snapshot"]
        if isinstance(item, dict)
    ]
    if (
        len(type_ids) != len(active_pack["full_compact_snapshot"])
        or len(type_ids) != len(set(type_ids))
        or type_ids != baseline.get("accepted_type_ids")
    ):
        raise RuntimeError("financial_semantic_context_v2_pack_baseline_mismatch")
    semantic_pack = {
        "schema_version": active_pack["schema_version"],
        "pack_id": active_pack["pack_id"],
        "semantic_version": active_pack["semantic_version"],
        "managed_asset_ref": active_pack["managed_asset_ref"],
        "consumer_contract_version": active_pack[
            "consumer_contract_version"
        ],
        "integrity_sha256": active_pack["integrity_sha256"],
        "source_baseline": copy.deepcopy(baseline),
        "full_compact_snapshot": copy.deepcopy(
            active_pack["full_compact_snapshot"]
        ),
    }
    return {
        "schema_version": CONTEXT_V2_MODEL_ASSET_SCHEMA_VERSION,
        "managed_asset_family": copy.deepcopy(
            candidate["managed_asset_family"]
        ),
        "semantic_pack": semantic_pack,
        "decision_reason_catalog": copy.deepcopy(
            candidate["decision_reason_catalog"]
        ),
    }


def _verified_candidate_payload() -> dict[str, Any]:
    raw = _decompress(
        _CONTEXT_V2_CANDIDATE_PAYLOAD_B85,
        "financial_semantic_context_v2_candidate_assets",
    )
    if hashlib.sha256(raw).hexdigest() != (
        CONTEXT_V2_CANDIDATE_PAYLOAD_SHA256
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_candidate_assets_hash_mismatch"
        )
    try:
        payload: Any = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "financial_semantic_context_v2_candidate_assets_json_invalid"
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "managed_asset_family",
            "semantic_pack_identity",
            "semantic_pack_source_baseline",
            "decision_reason_catalog",
        }
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_candidate_assets_shape_invalid"
        )
    family = payload["managed_asset_family"]
    if (
        not isinstance(family, dict)
        or family
        != {
            "family_id": MANAGED_ASSET_FAMILY_ID,
            "semantic_version": MANAGED_ASSET_FAMILY_VERSION,
            "manifest_sha256": MANAGED_ASSET_FAMILY_MANIFEST_SHA256,
            "runtime_activation": False,
        }
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_family_identity_mismatch"
        )
    baseline = payload["semantic_pack_source_baseline"]
    if (
        not isinstance(baseline, dict)
        or set(baseline)
        != {
            "registry_version",
            "registry_sha256",
            "accepted_type_ids",
            "deferred_candidate_ids",
            "legacy_python_status",
        }
        or not isinstance(baseline.get("accepted_type_ids"), list)
        or not baseline["accepted_type_ids"]
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_pack_baseline_invalid"
        )
    _validate_reason_catalog(payload["decision_reason_catalog"])
    return payload


def _validate_reason_catalog(catalog: Any) -> None:
    if (
        not isinstance(catalog, dict)
        or catalog.get("catalog_id") != DECISION_REASON_CATALOG_ID
        or catalog.get("semantic_version")
        != DECISION_REASON_CATALOG_VERSION
        or catalog.get("managed_asset_family_id")
        != MANAGED_ASSET_FAMILY_ID
        or catalog.get("code_contract_version")
        != DECISION_CODE_CONTRACT_VERSION
        or catalog.get("runtime_activation") is not False
        or not isinstance(catalog.get("reasons"), list)
        or not catalog["reasons"]
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_reason_catalog_identity_mismatch"
        )
    material = copy.deepcopy(catalog)
    supplied_integrity = material.pop("integrity_sha256", None)
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    reason_codes = [
        item.get("code")
        for item in catalog["reasons"]
        if isinstance(item, dict)
    ]
    if (
        len(canonical)
        != DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES
        or hashlib.sha256(canonical).hexdigest()
        != DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or supplied_integrity
        != DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or len(reason_codes) != len(catalog["reasons"])
        or len(reason_codes) != len(set(reason_codes))
        or set(reason_codes)
        != {"ambiguous_registry_type", "no_registry_type"}
    ):
        raise RuntimeError(
            "financial_semantic_context_v2_reason_catalog_integrity_mismatch"
        )
'''

MINIMAL_MANAGED_RUNTIME_TEMPLATE = '''
MINIMAL_MANAGED_MODEL_ASSET_SCHEMA_VERSION = (
    "broker_reports_gate2_minimal_managed_model_assets_v1"
)
MINIMAL_MANAGED_ASSET_FAMILY_VERSION = "1.2.0"
MINIMAL_MANAGED_ASSET_FAMILY_MANIFEST_SHA256 = (
    "__MINIMAL_MANAGED_ASSET_FAMILY_MANIFEST_SHA256__"
)
MINIMAL_MANAGED_PROJECTION_PROFILE_ID = (
    "broker_reports_gate2_minimal_managed_projection_v1_candidate"
)
MINIMAL_MANAGED_PROJECTION_PROFILE_VERSION = "1.0.0"
MINIMAL_MANAGED_DECISION_REASON_CATALOG_VERSION = "2.0.0"
MINIMAL_MANAGED_DECISION_REASON_CATALOG_INTEGRITY_SHA256 = (
    "__MINIMAL_MANAGED_DECISION_REASON_CATALOG_INTEGRITY_SHA256__"
)
MINIMAL_MANAGED_DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES = (
    __MINIMAL_MANAGED_DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES__
)
MINIMAL_MANAGED_CANDIDATE_PAYLOAD_SHA256 = (
    "__MINIMAL_MANAGED_CANDIDATE_PAYLOAD_SHA256__"
)
MINIMAL_MANAGED_CANDIDATE_REQUIRED = (
    "load_gate2_financial_semantic_model_assets and "
    "Gate2FinancialSemanticV5ProjectionFactory remain the only managed "
    "asset-loader and shared Pack/reason projection owners"
)
MINIMAL_MANAGED_CANDIDATE_FORBIDDEN = (
    "The inactive minimal profile must not alter active assets, read runtime "
    "files, use network or RAG, embed replacement wording, build a Packet or "
    "Choice, or activate provider transport"
)

_MINIMAL_MANAGED_CANDIDATE_PAYLOAD_B85 = (
__MINIMAL_MANAGED_CANDIDATE_PAYLOAD_LINES__
)


def _minimal_managed_projection_assets(
    *,
    full_pack: dict[str, Any],
) -> dict[str, Any]:
    """Return exact non-active family-v3 Pack and reason authorities."""

    full_pack = copy.deepcopy(full_pack)
    candidate = _verified_minimal_managed_candidate_payload()
    if (
        not isinstance(full_pack, dict)
        or candidate["semantic_pack_identity"]
        != {
            "pack_id": full_pack.get("pack_id"),
            "semantic_version": full_pack.get("semantic_version"),
            "integrity_sha256": full_pack.get("integrity_sha256"),
        }
        or full_pack.get("pack_id") != PACK_ID
        or full_pack.get("semantic_version") != PACK_SEMANTIC_VERSION
        or full_pack.get("integrity_sha256") != PACK_INTEGRITY_SHA256
        or full_pack.get("runtime_activation") is not False
        or not isinstance(full_pack.get("full_compact_snapshot"), list)
        or len(full_pack["full_compact_snapshot"]) != 2
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_pack_identity_mismatch"
        )
    return {
        "schema_version": MINIMAL_MANAGED_MODEL_ASSET_SCHEMA_VERSION,
        "managed_asset_family": copy.deepcopy(
            candidate["managed_asset_family"]
        ),
        "projection_profile": copy.deepcopy(
            candidate["projection_profile"]
        ),
        "semantic_pack": full_pack,
        "decision_reason_catalog": copy.deepcopy(
            candidate["decision_reason_catalog"]
        ),
    }


def _verified_minimal_managed_candidate_payload() -> dict[str, Any]:
    raw = _decompress(
        _MINIMAL_MANAGED_CANDIDATE_PAYLOAD_B85,
        "financial_semantic_minimal_managed_candidate_assets",
    )
    if hashlib.sha256(raw).hexdigest() != (
        MINIMAL_MANAGED_CANDIDATE_PAYLOAD_SHA256
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_candidate_assets_hash_mismatch"
        )
    try:
        payload: Any = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "financial_semantic_minimal_managed_candidate_assets_json_invalid"
        ) from exc
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "managed_asset_family",
            "projection_profile",
            "semantic_pack_identity",
            "decision_reason_catalog",
        }
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_candidate_assets_shape_invalid"
        )
    if payload["managed_asset_family"] != {
        "family_id": MANAGED_ASSET_FAMILY_ID,
        "semantic_version": MINIMAL_MANAGED_ASSET_FAMILY_VERSION,
        "manifest_sha256": (
            MINIMAL_MANAGED_ASSET_FAMILY_MANIFEST_SHA256
        ),
        "runtime_activation": False,
    }:
        raise RuntimeError(
            "financial_semantic_minimal_managed_family_identity_mismatch"
        )
    profile = payload["projection_profile"]
    if (
        not isinstance(profile, dict)
        or set(profile)
        != {
            "profile_id",
            "semantic_version",
            "status",
            "runtime_activation",
            "response_profile_status",
            "transport_eligible",
            "semantic_pack_dependency_id",
            "decision_reason_catalog_dependency_id",
            "decision_reason_catalog_schema_dependency_id",
            "decision_reason_catalog_contract_dependency_id",
            "model_surface_contract_identity",
            "projection_owner_entrypoint",
        }
        or profile.get("profile_id")
        != MINIMAL_MANAGED_PROJECTION_PROFILE_ID
        or profile.get("semantic_version")
        != MINIMAL_MANAGED_PROJECTION_PROFILE_VERSION
        or profile.get("status") != "inactive_candidate"
        or profile.get("runtime_activation") is not False
        or profile.get("response_profile_status") != "not_implemented"
        or profile.get("transport_eligible") is not False
        or profile.get("semantic_pack_dependency_id")
        != "broker_reports_financial_semantic_pack"
        or profile.get("decision_reason_catalog_dependency_id")
        != "broker_reports_gate2_financial_decision_reason_catalog"
        or profile.get("decision_reason_catalog_schema_dependency_id")
        != "broker_reports_gate2_financial_decision_reason_catalog_schema"
        or profile.get("decision_reason_catalog_contract_dependency_id")
        != "broker_reports_gate2_financial_decision_reason_catalog_contract"
        or profile.get("model_surface_contract_identity")
        != "broker_reports_gate2_minimal_model_surface_v1"
        or profile.get("projection_owner_entrypoint")
        != (
            "Gate2FinancialSemanticV5ProjectionFactory."
            "create_minimal_managed_projection"
        )
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_profile_identity_mismatch"
        )
    catalog = payload["decision_reason_catalog"]
    if (
        not isinstance(catalog, dict)
        or catalog.get("catalog_id") != DECISION_REASON_CATALOG_ID
        or catalog.get("semantic_version")
        != MINIMAL_MANAGED_DECISION_REASON_CATALOG_VERSION
        or catalog.get("managed_asset_family_id")
        != MANAGED_ASSET_FAMILY_ID
        or catalog.get("runtime_activation") is not False
        or not isinstance(catalog.get("reasons"), list)
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_reason_catalog_identity_mismatch"
        )
    material = copy.deepcopy(catalog)
    supplied_integrity = material.pop("integrity_sha256", None)
    canonical = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    reason_codes = [
        item.get("code")
        for item in catalog["reasons"]
        if isinstance(item, dict)
    ]
    if (
        len(canonical)
        != MINIMAL_MANAGED_DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES
        or hashlib.sha256(canonical).hexdigest()
        != MINIMAL_MANAGED_DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or supplied_integrity
        != MINIMAL_MANAGED_DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or reason_codes
        != [
            "no_registry_type",
            "single_registry_type_no_safe_record",
            "ambiguous_registry_type",
        ]
    ):
        raise RuntimeError(
            "financial_semantic_minimal_managed_reason_catalog_integrity_mismatch"
        )
    return payload
'''


def _portable_text_blob(path: Path) -> bytes:
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _payload_lines(value: bytes) -> str:
    encoded = base64.b85encode(zlib.compress(value, level=9)).decode("ascii")
    return "\n".join(
        f'    b"{part}"'
        for part in textwrap.wrap(
            encoded,
            width=88,
            break_long_words=True,
            break_on_hyphens=False,
        )
    )


def _asset_identity(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": asset["asset_id"],
        "kind": asset["kind"],
        "semantic_version": asset["semantic_version"],
        "git_blob_sha256": asset["git_blob_sha256"],
        "api_identity": copy.deepcopy(asset["api_identity"]),
    }


def _verified_source_material() -> tuple[bytes, bytes, bytes]:
    pack_bytes = _portable_text_blob(PACK_PATH)
    prompt_bytes = _portable_text_blob(PROMPT_PATH)
    skill_bytes = _portable_text_blob(SKILL_PATH)
    manifest = json.loads(_portable_text_blob(MANIFEST_PATH))
    assets = {
        item["asset_id"]: item for item in manifest.get("assets", [])
    }
    dependencies = {
        item["dependency_id"]: item
        for item in manifest.get("dependencies", [])
    }
    skill = assets.get(SKILL_ASSET_ID)
    prompt = assets.get(PROMPT_ASSET_ID)
    pack_dependency = dependencies.get(
        "broker_reports_financial_semantic_pack"
    )
    pack = json.loads(pack_bytes)
    material = copy.deepcopy(pack)
    supplied_integrity = material.pop("integrity_sha256", None)
    canonical = _canonical_json(material)
    if (
        not isinstance(skill, dict)
        or not isinstance(prompt, dict)
        or not isinstance(pack_dependency, dict)
        or _sha256(skill_bytes) != skill.get("git_blob_sha256")
        or _sha256(prompt_bytes) != prompt.get("git_blob_sha256")
        or _sha256(pack_bytes) != pack_dependency.get("git_blob_sha256")
        or pack.get("pack_id") != PACK_ID
        or pack.get("semantic_version") != PACK_VERSION
        or pack.get("runtime_activation") is not False
        or supplied_integrity != PACK_INTEGRITY_SHA256
        or _sha256(canonical) != PACK_INTEGRITY_SHA256
        or len(canonical) != PACK_CANONICAL_SEMANTIC_BYTES
        or prompt_bytes.decode("utf-8").count(PROMPT_MARKER) != 1
    ):
        raise ValueError("financial_semantic_model_asset_source_invalid")
    identities = {
        "family_id": manifest["family_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "semantic_version": manifest["semantic_version"],
        "skill": _asset_identity(skill),
        "prompt": _asset_identity(prompt),
    }
    return pack_bytes, prompt_bytes, _canonical_json(identities)


def _verified_context_v2_source_material() -> bytes:
    pack_bytes = _portable_text_blob(PACK_PATH)
    manifest_bytes = _portable_text_blob(CONTEXT_V2_MANIFEST_PATH)
    catalog_bytes = _portable_text_blob(DECISION_REASON_CATALOG_PATH)
    pack = json.loads(pack_bytes)
    manifest = json.loads(manifest_bytes)
    catalog = json.loads(catalog_bytes)
    dependencies = {
        item["dependency_id"]: item
        for item in manifest.get("dependencies", [])
        if isinstance(item, dict) and isinstance(item.get("dependency_id"), str)
    }
    pack_dependency = dependencies.get(
        "broker_reports_financial_semantic_pack"
    )
    catalog_dependency = dependencies.get(
        "broker_reports_gate2_financial_decision_reason_catalog"
    )
    manifest_material = copy.deepcopy(manifest)
    supplied_manifest_hash = manifest_material.pop("manifest_sha256", None)
    pack_material = copy.deepcopy(pack)
    supplied_pack_integrity = pack_material.pop("integrity_sha256", None)
    catalog_material = copy.deepcopy(catalog)
    supplied_catalog_integrity = catalog_material.pop(
        "integrity_sha256",
        None,
    )
    baseline = pack.get("source_baseline")
    pack_type_ids = [
        item.get("input_type_id")
        for item in pack.get("full_compact_snapshot", [])
        if isinstance(item, dict)
    ]
    reason_codes = [
        item.get("code")
        for item in catalog.get("reasons", [])
        if isinstance(item, dict)
    ]
    if (
        manifest.get("schema_version")
        != "broker_reports_financial_domain_managed_asset_manifest_v2"
        or manifest.get("family_id")
        != "broker_reports_gate2_financial_domain_assets"
        or manifest.get("semantic_version")
        != CONTEXT_V2_MANAGED_ASSET_FAMILY_VERSION
        or manifest.get("runtime_activation") is not False
        or supplied_manifest_hash
        != CONTEXT_V2_MANAGED_ASSET_FAMILY_MANIFEST_SHA256
        or _sha256(_canonical_json(manifest_material))
        != CONTEXT_V2_MANAGED_ASSET_FAMILY_MANIFEST_SHA256
        or not isinstance(pack_dependency, dict)
        or pack_dependency.get("contract_identity")
        != f"{PACK_ID}@{PACK_VERSION}"
        or pack_dependency.get("semantic_integrity_sha256")
        != PACK_INTEGRITY_SHA256
        or pack_dependency.get("git_blob_sha256") != _sha256(pack_bytes)
        or not isinstance(catalog_dependency, dict)
        or catalog_dependency.get("contract_identity")
        != (
            f"{DECISION_REASON_CATALOG_ID}"
            f"@{DECISION_REASON_CATALOG_VERSION}"
        )
        or catalog_dependency.get("semantic_integrity_sha256")
        != DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or catalog_dependency.get("git_blob_sha256")
        != _sha256(catalog_bytes)
        or catalog_dependency.get("runtime_activation") is not False
        or pack.get("pack_id") != PACK_ID
        or pack.get("semantic_version") != PACK_VERSION
        or pack.get("runtime_activation") is not False
        or supplied_pack_integrity != PACK_INTEGRITY_SHA256
        or _sha256(_canonical_json(pack_material))
        != PACK_INTEGRITY_SHA256
        or len(_canonical_json(pack_material))
        != PACK_CANONICAL_SEMANTIC_BYTES
        or not isinstance(baseline, dict)
        or baseline.get("registry_version") != REGISTRY_VERSION
        or baseline.get("registry_sha256") != REGISTRY_SHA256
        or pack_type_ids != baseline.get("accepted_type_ids")
        or len(pack_type_ids) != len(set(pack_type_ids))
        or catalog.get("catalog_id") != DECISION_REASON_CATALOG_ID
        or catalog.get("semantic_version")
        != DECISION_REASON_CATALOG_VERSION
        or catalog.get("managed_asset_family_id")
        != manifest.get("family_id")
        or catalog.get("code_contract_version")
        != DECISION_CODE_CONTRACT_VERSION
        or catalog.get("runtime_activation") is not False
        or supplied_catalog_integrity
        != DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or _sha256(_canonical_json(catalog_material))
        != DECISION_REASON_CATALOG_INTEGRITY_SHA256
        or len(_canonical_json(catalog_material))
        != DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES
        or len(reason_codes) != len(catalog.get("reasons", []))
        or len(reason_codes) != len(set(reason_codes))
        or set(reason_codes) != DECISION_REASON_CODES
    ):
        raise ValueError(
            "financial_semantic_context_v2_model_asset_source_invalid"
        )
    candidate_payload = {
        "managed_asset_family": {
            "family_id": manifest["family_id"],
            "semantic_version": manifest["semantic_version"],
            "manifest_sha256": manifest["manifest_sha256"],
            "runtime_activation": manifest["runtime_activation"],
        },
        "semantic_pack_identity": {
            "pack_id": pack["pack_id"],
            "semantic_version": pack["semantic_version"],
            "integrity_sha256": pack["integrity_sha256"],
        },
        "semantic_pack_source_baseline": copy.deepcopy(baseline),
        "decision_reason_catalog": copy.deepcopy(catalog),
    }
    return _canonical_json(candidate_payload)


def _verified_minimal_managed_source_material(
) -> tuple[bytes, str, int, str]:
    pack_bytes = _portable_text_blob(PACK_PATH)
    manifest_v1 = json.loads(_portable_text_blob(MANIFEST_PATH))
    manifest_v2_bytes = _portable_text_blob(CONTEXT_V2_MANIFEST_PATH)
    manifest_v2 = json.loads(manifest_v2_bytes)
    manifest_v3_bytes = _portable_text_blob(MINIMAL_MANAGED_MANIFEST_PATH)
    manifest_v3 = json.loads(manifest_v3_bytes)
    predecessor_catalog = json.loads(
        _portable_text_blob(DECISION_REASON_CATALOG_PATH)
    )
    catalog_bytes = _portable_text_blob(DECISION_REASON_CATALOG_V2_PATH)
    catalog = json.loads(catalog_bytes)
    catalog_schema_bytes = _portable_text_blob(
        DECISION_REASON_CATALOG_V2_SCHEMA_PATH
    )
    catalog_contract_bytes = _portable_text_blob(
        DECISION_REASON_CATALOG_V2_CONTRACT_PATH
    )
    factory = Gate2FinancialDecisionReasonCatalogV2ContractFactory(
        predecessor_catalog=predecessor_catalog,
        candidate_catalog=catalog,
    )
    catalog_snapshot = factory.create(catalog=catalog)
    expected_catalog_schema_bytes = (
        json.dumps(
            factory.schema(),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
    manifest_material = copy.deepcopy(manifest_v3)
    supplied_manifest_hash = manifest_material.pop(
        "manifest_sha256",
        None,
    )
    dependencies = {
        item.get("dependency_id"): item
        for item in manifest_v3.get("dependencies", [])
        if isinstance(item, dict)
    }
    catalog_dependency = dependencies.get(
        "broker_reports_gate2_financial_decision_reason_catalog"
    )
    catalog_schema_dependency = dependencies.get(
        "broker_reports_gate2_financial_decision_reason_catalog_schema"
    )
    catalog_contract_dependency = dependencies.get(
        "broker_reports_gate2_financial_decision_reason_catalog_contract"
    )
    profile = manifest_v3.get("composition", {}).get(
        "minimal_projection_profile"
    )
    expected_profile = {
        "profile_id": MINIMAL_MANAGED_PROJECTION_PROFILE_ID,
        "semantic_version": MINIMAL_MANAGED_PROJECTION_PROFILE_VERSION,
        "status": "inactive_candidate",
        "runtime_activation": False,
        "response_profile_status": "not_implemented",
        "transport_eligible": False,
        "semantic_pack_dependency_id": (
            "broker_reports_financial_semantic_pack"
        ),
        "decision_reason_catalog_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog"
        ),
        "decision_reason_catalog_schema_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog_schema"
        ),
        "decision_reason_catalog_contract_dependency_id": (
            "broker_reports_gate2_financial_decision_reason_catalog_contract"
        ),
        "model_surface_contract_identity": (
            "broker_reports_gate2_minimal_model_surface_v1"
        ),
        "projection_owner_entrypoint": (
            "Gate2FinancialSemanticV5ProjectionFactory."
            "create_minimal_managed_projection"
        ),
    }
    pack = json.loads(pack_bytes)
    expected_dependency_ids = [
        *[
            item["dependency_id"]
            for item in manifest_v1.get("dependencies", [])
        ],
        "broker_reports_gate2_financial_decision_reason_catalog",
        "broker_reports_gate2_financial_decision_reason_catalog_schema",
        "broker_reports_gate2_financial_decision_reason_catalog_contract",
    ]
    if (
        manifest_v3.get("schema_version")
        != "broker_reports_financial_domain_managed_asset_manifest_v3"
        or manifest_v3.get("family_id")
        != "broker_reports_gate2_financial_domain_assets"
        or manifest_v3.get("semantic_version")
        != MINIMAL_MANAGED_ASSET_FAMILY_VERSION
        or manifest_v3.get("runtime_activation") is not False
        or supplied_manifest_hash != _sha256(
            _canonical_json(manifest_material)
        )
        or manifest_v3.get("assets") != manifest_v1.get("assets")
        or manifest_v3.get("dependencies", [])[:4]
        != manifest_v1.get("dependencies")
        or [
            item.get("dependency_id")
            for item in manifest_v3.get("dependencies", [])
            if isinstance(item, dict)
        ]
        != expected_dependency_ids
        or manifest_v3.get("lifecycle")
        != {
            "status": "draft",
            "previous_family_semantic_version": "1.1.0",
            "draft_rollback": "discard_without_runtime_mutation",
            "active_rollback": (
                "select_previous_validated_immutable_family_version"
            ),
            "rollback_manifest_schema_version": manifest_v2.get(
                "schema_version"
            ),
            "rollback_manifest_sha256": manifest_v2.get(
                "manifest_sha256"
            ),
            "rollback_manifest_git_blob_sha256": _sha256(
                manifest_v2_bytes
            ),
            "live_publisher_implemented": False,
        }
        or manifest_v2.get("manifest_sha256")
        != CONTEXT_V2_MANAGED_ASSET_FAMILY_MANIFEST_SHA256
        or profile != expected_profile
        or not isinstance(catalog_dependency, dict)
        or catalog_dependency.get("contract_identity")
        != f"{DECISION_REASON_CATALOG_ID}@2.0.0"
        or catalog_dependency.get("git_blob_sha256")
        != _sha256(catalog_bytes)
        or catalog_dependency.get("semantic_integrity_sha256")
        != catalog_snapshot.integrity_sha256
        or catalog_dependency.get("canonical_semantic_bytes")
        != catalog_snapshot.canonical_semantic_bytes
        or catalog_dependency.get("runtime_activation") is not False
        or catalog_dependency.get("family_packaging_status")
        != "packaged_in_inactive_family_v3"
        or not isinstance(catalog_schema_dependency, dict)
        or catalog_schema_dependency.get("git_blob_sha256")
        != _sha256(catalog_schema_bytes)
        or catalog_schema_bytes != expected_catalog_schema_bytes
        or not isinstance(catalog_contract_dependency, dict)
        or catalog_contract_dependency.get("git_blob_sha256")
        != _sha256(catalog_contract_bytes)
        or pack.get("pack_id") != PACK_ID
        or pack.get("semantic_version") != PACK_VERSION
        or pack.get("integrity_sha256") != PACK_INTEGRITY_SHA256
        or pack.get("runtime_activation") is not False
    ):
        raise ValueError(
            "financial_semantic_minimal_managed_model_asset_source_invalid"
        )
    candidate_payload = {
        "managed_asset_family": {
            "family_id": manifest_v3["family_id"],
            "semantic_version": manifest_v3["semantic_version"],
            "manifest_sha256": manifest_v3["manifest_sha256"],
            "runtime_activation": manifest_v3["runtime_activation"],
        },
        "projection_profile": copy.deepcopy(profile),
        "semantic_pack_identity": {
            "pack_id": pack["pack_id"],
            "semantic_version": pack["semantic_version"],
            "integrity_sha256": pack["integrity_sha256"],
        },
        "decision_reason_catalog": copy.deepcopy(catalog),
    }
    return (
        _canonical_json(candidate_payload),
        catalog_snapshot.integrity_sha256,
        catalog_snapshot.canonical_semantic_bytes,
        manifest_v3["manifest_sha256"],
    )


def build() -> bytes:
    pack_bytes, prompt_bytes, identities_bytes = _verified_source_material()
    context_v2_payload = _verified_context_v2_source_material()
    (
        minimal_managed_payload,
        minimal_catalog_integrity,
        minimal_catalog_canonical_bytes,
        minimal_manifest_integrity,
    ) = _verified_minimal_managed_source_material()
    context_v2_fragment = (
        CONTEXT_V2_RUNTIME_TEMPLATE.replace(
            "__CONTEXT_V2_CANDIDATE_PAYLOAD_SHA256__",
            _sha256(context_v2_payload),
        ).replace(
            "__CONTEXT_V2_CANDIDATE_PAYLOAD_LINES__",
            _payload_lines(context_v2_payload),
        )
    )
    minimal_managed_fragment = (
        MINIMAL_MANAGED_RUNTIME_TEMPLATE.replace(
            "__MINIMAL_MANAGED_ASSET_FAMILY_MANIFEST_SHA256__",
            minimal_manifest_integrity,
        )
        .replace(
            "__MINIMAL_MANAGED_DECISION_REASON_CATALOG_INTEGRITY_SHA256__",
            minimal_catalog_integrity,
        )
        .replace(
            "__MINIMAL_MANAGED_DECISION_REASON_CATALOG_CANONICAL_SEMANTIC_BYTES__",
            str(minimal_catalog_canonical_bytes),
        )
        .replace(
            "__MINIMAL_MANAGED_CANDIDATE_PAYLOAD_SHA256__",
            _sha256(minimal_managed_payload),
        )
        .replace(
            "__MINIMAL_MANAGED_CANDIDATE_PAYLOAD_LINES__",
            _payload_lines(minimal_managed_payload),
        )
    )
    content = (
        RUNTIME_TEMPLATE.replace(
            "__PACK_GIT_BLOB_SHA256__",
            _sha256(pack_bytes),
        )
        .replace(
            "__PROMPT_GIT_BLOB_SHA256__",
            _sha256(prompt_bytes),
        )
        .replace(
            "__MANAGED_ASSET_IDENTITIES_SHA256__",
            _sha256(identities_bytes),
        )
        .replace("__PACK_PAYLOAD_LINES__", _payload_lines(pack_bytes))
        .replace(
            "__PROMPT_PAYLOAD_LINES__",
            _payload_lines(prompt_bytes),
        )
        .replace(
            "__IDENTITIES_PAYLOAD_LINES__",
            _payload_lines(identities_bytes),
        )
        .replace(
            "__CONTEXT_V2_RUNTIME_FRAGMENT__",
            context_v2_fragment,
        )
        .replace(
            "__MINIMAL_MANAGED_RUNTIME_FRAGMENT__",
            minimal_managed_fragment,
        )
    )
    return content.replace("\r\n", "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail unless the generated closed-world projection is exact.",
    )
    args = parser.parse_args()
    expected = build()
    if args.check:
        if (
            not RUNTIME_PATH.is_file()
            or _portable_text_blob(RUNTIME_PATH) != expected
        ):
            raise ValueError(
                "financial_semantic_model_asset_generated_content_mismatch"
            )
    else:
        RUNTIME_PATH.write_bytes(expected)
    print(
        json.dumps(
            {
                "status": "passed",
                "mode": "check" if args.check else "write",
                "runtime_projection_git_blob_sha256": _sha256(expected),
                "context_v2_candidate_payload_sha256": _sha256(
                    _verified_context_v2_source_material()
                ),
                "minimal_managed_candidate_payload_sha256": _sha256(
                    _verified_minimal_managed_source_material()[0]
                ),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
