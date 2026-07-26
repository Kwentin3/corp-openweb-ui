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


def load_gate2_financial_semantic_model_assets() -> dict[str, Any]:
    """Return exact managed identities, Prompt, and complete compact Pack."""

    pack = _verified_pack()
    prompt_content = _verified_prompt()
    managed_assets = _verified_identities()
    return {
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


def build() -> bytes:
    pack_bytes, prompt_bytes, identities_bytes = _verified_source_material()
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
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
