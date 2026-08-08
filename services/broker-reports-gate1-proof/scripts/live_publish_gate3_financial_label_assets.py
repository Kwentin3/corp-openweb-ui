#!/usr/bin/env python3
"""Publish/read back the exact managed Gate 3 dictionary Skill and Tool."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

import build_openwebui_managed_financial_assets as managed_builder  # noqa: E402
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


FACTORY_REQUIRED = (
    "publish/readback must use the deterministic managed-asset builder and "
    "the native OpenWebUI Skill/Tool API stable IDs"
)
FORBIDDEN = (
    "publisher must not resolve assets by display name, publish Knowledge/RAG, "
    "edit dictionary meaning, call a model/provider or bypass exact readback"
)


class ManagedAssetPublishError(RuntimeError):
    pass


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
) -> Any:
    response = session.request(method, url, json=payload, timeout=30)
    if response.status_code < 200 or response.status_code >= 300:
        raise ManagedAssetPublishError(
            f"openwebui_managed_asset_request_failed:{method}:"
            f"{response.status_code}"
        )
    try:
        return response.json()
    except requests.JSONDecodeError as exc:
        raise ManagedAssetPublishError(
            "openwebui_managed_asset_response_not_json"
        ) from exc


def _export_records(
    session: requests.Session,
    base_url: str,
    kind: str,
) -> list[dict[str, Any]]:
    value = _request_json(
        session,
        "GET",
        _url(base_url, f"/api/v1/{kind}/export"),
    )
    if not isinstance(value, list) or any(
        not isinstance(item, dict) for item in value
    ):
        raise ManagedAssetPublishError(
            f"openwebui_{kind}_export_invalid"
        )
    return value


def _record_by_id(
    records: list[dict[str, Any]],
    stable_id: str,
) -> dict[str, Any] | None:
    matches = [record for record in records if record.get("id") == stable_id]
    if len(matches) > 1:
        raise ManagedAssetPublishError("managed_asset_stable_id_duplicate")
    return copy.deepcopy(matches[0]) if matches else None


def _expected_assets() -> dict[str, dict[str, Any]]:
    skill_bytes, tool_bytes, manifest_bytes, _ = (
        managed_builder.build_gate3_financial_label_assets()
    )
    manifest = json.loads(manifest_bytes)
    assets = {asset["kind"]: asset for asset in manifest["assets"]}
    return {
        "skills": {
            "kind": "skills",
            "content": skill_bytes.decode("utf-8"),
            "asset": assets["openwebui_skill"],
        },
        "tools": {
            "kind": "tools",
            "content": tool_bytes.decode("utf-8"),
            "asset": assets["openwebui_workspace_tool"],
        },
        "manifest": manifest,
    }


def _skill_form(
    expected: dict[str, Any],
    *,
    access_grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    identity = expected["asset"]["api_identity"]
    return {
        "id": identity["id"],
        "name": identity["name"],
        "description": identity["description"],
        "content": expected["content"],
        "meta": copy.deepcopy(identity["meta"]),
        "is_active": True,
        "access_grants": access_grants or [],
    }


def _tool_form(
    expected: dict[str, Any],
    *,
    access_grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    identity = expected["asset"]["api_identity"]
    return {
        "id": identity["id"],
        "name": identity["name"],
        "content": expected["content"],
        "meta": {
            "description": identity["description"],
            "manifest": {},
        },
        "access_grants": access_grants or [],
    }


def _grant_payload(record: dict[str, Any] | None) -> list[dict[str, Any]]:
    grants = record.get("access_grants") if record else []
    if not isinstance(grants, list):
        return []
    return [
        {
            key: grant[key]
            for key in (
                "principal_type",
                "principal_id",
                "permission",
            )
            if key in grant
        }
        for grant in grants
        if isinstance(grant, dict)
    ]


def _tool_method_names(record: dict[str, Any]) -> list[str]:
    specs = record.get("specs")
    if not isinstance(specs, list):
        return []
    result: list[str] = []
    for spec in specs:
        if not isinstance(spec, dict):
            continue
        name = spec.get("name")
        if not isinstance(name, str):
            function = spec.get("function")
            name = function.get("name") if isinstance(function, dict) else None
        if isinstance(name, str):
            result.append(name)
    return result


def evaluate_record(
    *,
    kind: str,
    expected: dict[str, Any],
    record: dict[str, Any] | None,
) -> dict[str, Any]:
    identity = expected["asset"]["api_identity"]
    content = record.get("content") if record else None
    common = {
        "present": record is not None,
        "stable_id_match": bool(record and record.get("id") == identity["id"]),
        "name_match": bool(record and record.get("name") == identity["name"]),
        "content_sha256_match": bool(
            isinstance(content, str)
            and _sha256(content.encode("utf-8"))
            == expected["asset"]["git_blob_sha256"]
        ),
    }
    if kind == "skills":
        meta = record.get("meta") if record else None
        common.update(
            {
                "description_match": bool(
                    record
                    and record.get("description")
                    == identity["description"]
                ),
                "metadata_match": bool(
                    isinstance(meta, dict)
                    and meta.get("tags") == identity["meta"]["tags"]
                ),
                "active": bool(record and record.get("is_active") is True),
            }
        )
    else:
        meta = record.get("meta") if record else None
        common.update(
            {
                "description_match": bool(
                    isinstance(meta, dict)
                    and meta.get("description") == identity["description"]
                ),
                "tool_method_match": _tool_method_names(record or {})
                == [identity["meta"]["tool_method"]],
            }
        )
    common["passed"] = all(common.values())
    return common


def _managed_collision_safe(
    *,
    kind: str,
    expected: dict[str, Any],
    record: dict[str, Any],
) -> bool:
    identity = expected["asset"]["api_identity"]
    if record.get("id") != identity["id"]:
        return False
    if kind == "skills":
        meta = record.get("meta")
        return (
            isinstance(meta, dict)
            and "managed" in (meta.get("tags") or [])
            and "financial-labels" in (meta.get("tags") or [])
        )
    meta = record.get("meta")
    manifest = meta.get("manifest") if isinstance(meta, dict) else None
    return (
        isinstance(meta, dict)
        and meta.get("description") == identity["description"]
        and isinstance(manifest, dict)
        and manifest.get("title") == "Broker Reports Financial Labels"
    )


def _publish_one(
    session: requests.Session,
    base_url: str,
    *,
    kind: str,
    expected: dict[str, Any],
    previous: dict[str, Any] | None,
) -> str:
    identity = expected["asset"]["api_identity"]
    if previous is not None and not _managed_collision_safe(
        kind=kind,
        expected=expected,
        record=previous,
    ):
        raise ManagedAssetPublishError(
            f"managed_asset_id_collision:{identity['id']}"
        )
    form = (
        _skill_form(
            expected,
            access_grants=_grant_payload(previous),
        )
        if kind == "skills"
        else _tool_form(
            expected,
            access_grants=_grant_payload(previous),
        )
    )
    if previous is None:
        endpoint = f"/api/v1/{kind}/create"
        action = "created"
    else:
        endpoint = f"/api/v1/{kind}/id/{identity['id']}/update"
        action = "updated"
    _request_json(session, "POST", _url(base_url, endpoint), payload=form)
    return action


def _restore_one(
    session: requests.Session,
    base_url: str,
    *,
    kind: str,
    stable_id: str,
    previous: dict[str, Any] | None,
) -> None:
    if previous is None:
        _request_json(
            session,
            "DELETE",
            _url(base_url, f"/api/v1/{kind}/id/{stable_id}/delete"),
        )
        return
    if kind == "skills":
        form = {
            "id": previous["id"],
            "name": previous["name"],
            "description": previous.get("description"),
            "content": previous["content"],
            "meta": previous.get("meta") or {},
            "is_active": previous.get("is_active", True),
            "access_grants": _grant_payload(previous),
        }
    else:
        form = {
            "id": previous["id"],
            "name": previous["name"],
            "content": previous["content"],
            "meta": previous.get("meta") or {},
            "access_grants": _grant_payload(previous),
        }
    _request_json(
        session,
        "POST",
        _url(base_url, f"/api/v1/{kind}/id/{stable_id}/update"),
        payload=form,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Create/update the exact stable-ID Skill and Tool.",
    )
    args = parser.parse_args()

    expected = _expected_assets()
    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    previous = {
        kind: _record_by_id(
            _export_records(session, base_url, kind),
            expected[kind]["asset"]["api_identity"]["id"],
        )
        for kind in ("skills", "tools")
    }
    actions = {"skills": "read_only", "tools": "read_only"}
    mutated: list[str] = []
    if args.publish:
        try:
            for kind in ("skills", "tools"):
                current_check = evaluate_record(
                    kind=kind,
                    expected=expected[kind],
                    record=previous[kind],
                )
                if current_check["passed"]:
                    actions[kind] = "already_exact"
                    continue
                actions[kind] = _publish_one(
                    session,
                    base_url,
                    kind=kind,
                    expected=expected[kind],
                    previous=previous[kind],
                )
                mutated.append(kind)
        except Exception as exc:
            rollback_errors: list[str] = []
            for kind in reversed(mutated):
                try:
                    _restore_one(
                        session,
                        base_url,
                        kind=kind,
                        stable_id=(
                            expected[kind]["asset"]["api_identity"]["id"]
                        ),
                        previous=previous[kind],
                    )
                except Exception as rollback_exc:
                    rollback_errors.append(
                        f"{kind}:{type(rollback_exc).__name__}"
                    )
            raise ManagedAssetPublishError(
                f"managed_asset_publish_failed:{type(exc).__name__}:"
                f"rollback_errors={','.join(rollback_errors) or 'none'}"
            ) from exc

    current = {
        kind: _record_by_id(
            _export_records(session, base_url, kind),
            expected[kind]["asset"]["api_identity"]["id"],
        )
        for kind in ("skills", "tools")
    }
    checks = {
        kind: evaluate_record(
            kind=kind,
            expected=expected[kind],
            record=current[kind],
        )
        for kind in ("skills", "tools")
    }
    passed = all(check["passed"] for check in checks.values())
    result = {
        "schema_version": (
            "broker_reports_gate3_financial_label_live_binding_v1"
        ),
        "mode": "publish" if args.publish else "read_only",
        "status": "passed" if passed else "not_bound",
        "dictionary_identity": {
            "dictionary_id": "broker-reports-financial-labels",
            "semantic_version": "1.0.0",
            "file_sha256": (
                "182e8d7f3604ad3d06d93c4d913df17979f21aeea669123d70c10be9d9652850"
            ),
            "model_view_sha256": (
                "b5b89e1b17932c6429b71724667053287e65f7a72b0beec7dcd86cc1190d1b5b"
            ),
        },
        "stable_ids": {
            "skill_id": (
                expected["skills"]["asset"]["api_identity"]["id"]
            ),
            "tool_id": (
                expected["tools"]["asset"]["api_identity"]["id"]
            ),
            "tool_method": (
                expected["tools"]["asset"]["api_identity"]["meta"][
                    "tool_method"
                ]
            ),
            "prompt_id": None,
        },
        "gui_path": "Workspace -> Skills -> Broker Reports Financial Labels",
        "actions": actions,
        "checks": checks,
        "knowledge_rag": "none",
        "provider_calls": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
