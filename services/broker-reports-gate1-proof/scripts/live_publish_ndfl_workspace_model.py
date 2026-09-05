#!/usr/bin/env python3
"""Publish/read back the one stable-ID NDFL Workspace Model topology."""

from __future__ import annotations

import argparse
import copy
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

from broker_reports_gate1.gate3_ndfl_workflow import (  # noqa: E402
    NDFL_OPENWEBUI_BASE_PIPE_ID,
    NDFL_WORKFLOW_DISPLAY_NAME,
    NDFL_WORKSPACE_MODEL_STABLE_ID,
    ndfl_product_binding_snapshot,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


LEGACY_WORKSPACE_MODEL_ID = "test"
LEGACY_NDFL_MODEL_ID = "broker_reports_ndfl"
FUNCTION_ID = NDFL_OPENWEBUI_BASE_PIPE_ID
LEGACY_PIPE_IDS = (
    "broker_reports_gate2_source_fact_pipe",
    "broker_reports_gate2_domain_source_fact_pipe",
)
TECHNICAL_PIPE_IDS = LEGACY_PIPE_IDS
PRODUCT_ROUTE_IDS = (
    NDFL_WORKSPACE_MODEL_STABLE_ID,
    NDFL_OPENWEBUI_BASE_PIPE_ID,
    LEGACY_NDFL_MODEL_ID,
    LEGACY_WORKSPACE_MODEL_ID,
    *TECHNICAL_PIPE_IDS,
)
HIDDEN_ROUTE_SCHEMA_VERSION = "broker_reports_hidden_technical_route_v1"

FACTORY_REQUIRED = (
    "NDFL Workspace publication must bind the one user-facing facade to the "
    "maintained technical Gate 1 Pipe; OpenWebUI model APIs are addressed by "
    "ID only"
)
FORBIDDEN = (
    "The publisher must not detach or deactivate the technical Gate 1 Pipe, "
    "resolve behavior by display name, create another Function, attach "
    "Knowledge/RAG, call a provider, alias model IDs or delete historical models"
)


class NdflWorkspacePublishError(RuntimeError):
    pass


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    allow_not_found: bool = False,
) -> Any:
    response = session.request(method, url, json=payload, timeout=30)
    if allow_not_found and response.status_code in {401, 404}:
        return None
    if response.status_code < 200 or response.status_code >= 300:
        raise NdflWorkspacePublishError(
            f"openwebui_model_request_failed:{method}:{response.status_code}"
        )
    try:
        return response.json()
    except requests.JSONDecodeError as exc:
        raise NdflWorkspacePublishError(
            "openwebui_model_response_not_json"
        ) from exc


def _get_model(
    session: requests.Session,
    base_url: str,
    stable_id: str,
) -> dict[str, Any] | None:
    value = _request_json(
        session,
        "GET",
        _url(base_url, f"/api/v1/models/model?id={stable_id}"),
        allow_not_found=True,
    )
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("id") != stable_id:
        raise NdflWorkspacePublishError("openwebui_model_readback_invalid")
    return value


def _get_function(
    session: requests.Session,
    base_url: str,
    stable_id: str,
) -> dict[str, Any]:
    value = _request_json(
        session,
        "GET",
        _url(base_url, f"/api/v1/functions/id/{stable_id}"),
    )
    if not isinstance(value, dict) or value.get("id") != stable_id:
        raise NdflWorkspacePublishError("openwebui_function_readback_invalid")
    return value


def _get_visible_models(
    session: requests.Session,
    base_url: str,
) -> list[dict[str, Any]]:
    value = _request_json(
        session,
        "GET",
        _url(base_url, "/api/models?refresh=true"),
    )
    items = value.get("data") if isinstance(value, dict) else value
    if not isinstance(items, list) or any(
        not isinstance(item, dict) for item in items
    ):
        raise NdflWorkspacePublishError("openwebui_visible_models_invalid")
    return items


def _grant_payload(record: dict[str, Any] | None) -> list[dict[str, Any]]:
    grants = record.get("access_grants") if record else []
    if not isinstance(grants, list):
        return []
    return [
        {
            key: grant[key]
            for key in ("principal_type", "principal_id", "permission")
            if key in grant
        }
        for grant in grants
        if isinstance(grant, dict)
    ]


def _capabilities(record: dict[str, Any] | None) -> dict[str, Any]:
    meta = record.get("meta") if record else None
    value = meta.get("capabilities") if isinstance(meta, dict) else None
    if not isinstance(value, dict):
        value = {}
    return {
        **copy.deepcopy(value),
        "file_upload": True,
        "file_context": False,
    }


def desired_ndfl_model(
    *,
    previous: dict[str, Any] | None,
    legacy: dict[str, Any] | None,
) -> dict[str, Any]:
    grants_source = previous if previous is not None else legacy
    capabilities_source = previous if previous is not None else legacy
    source_meta = copy.deepcopy((previous or legacy or {}).get("meta") or {})
    source_binding = source_meta.get("broker_reports_product_binding")
    binding = (
        copy.deepcopy(source_binding)
        if isinstance(source_binding, dict)
        else ndfl_product_binding_snapshot()
    )
    # This publisher owns topology only. Existing provider, model, dictionary
    # and role-pack semantics must survive an identity repair unchanged.
    binding.update(
        {
            "workspace_model_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
            "base_pipe_id": NDFL_OPENWEBUI_BASE_PIPE_ID,
            "workflow_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
        }
    )
    if previous is not None:
        meta = source_meta
        meta.update(
            {
                "capabilities": _capabilities(capabilities_source),
                "knowledge": [],
                "toolIds": [],
                "skillIds": [],
                "broker_reports_product_binding": binding,
            }
        )
    else:
        meta = {
            "profile_image_url": "/static/favicon.png",
            "description": (
                "Помогает проверить брокерский отчёт, рассчитать подтверждённые "
                "операции и подготовить 3-НДФЛ либо честно объяснить, чего не хватает."
            ),
            "capabilities": _capabilities(capabilities_source),
            "suggestion_prompts": [
                {
                    "title": ["Подготовить", "3-НДФЛ"],
                    "content": "Помогите подготовить 3-НДФЛ по брокерскому отчёту.",
                },
                {
                    "title": ["Проверить", "операции"],
                    "content": (
                        "Проверьте брокерский отчёт и объясните, какие операции "
                        "можно рассчитать."
                    ),
                },
            ],
            "tags": [
                {"name": "broker-reports"},
                {"name": "ndfl"},
                {"name": "managed"},
            ],
            "knowledge": [],
            "toolIds": [],
            "skillIds": [],
            "broker_reports_product_binding": binding,
        }
    return {
        "id": NDFL_WORKSPACE_MODEL_STABLE_ID,
        "base_model_id": NDFL_OPENWEBUI_BASE_PIPE_ID,
        "name": NDFL_WORKFLOW_DISPLAY_NAME,
        "meta": meta,
        "params": copy.deepcopy(previous.get("params") or {}) if previous else {},
        "access_grants": _grant_payload(grants_source),
        "is_active": True,
    }


def desired_hidden_pipe_model(
    pipe_id: str,
    *,
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    runtime_base_required = False
    return {
        "id": pipe_id,
        "base_model_id": None,
        "name": pipe_id,
        "meta": {
            "description": (
                "ACL-restricted runtime base owned by the NDFL product model."
                if runtime_base_required
                else "Inactive legacy route owned by the NDFL product model."
            ),
            "tags": [
                {"name": "broker-reports"},
                {"name": "technical-route"},
                {"name": "managed"},
            ],
            "broker_reports_hidden_route": {
                "schema_version": HIDDEN_ROUTE_SCHEMA_VERSION,
                "route_id": pipe_id,
                "user_facing_owner_id": NDFL_WORKSPACE_MODEL_STABLE_ID,
                "runtime_base_required": runtime_base_required,
            },
        },
        "params": {},
        "access_grants": _grant_payload(previous),
        "is_active": runtime_base_required,
    }


def _model_form(record: dict[str, Any], *, is_active: bool | None = None) -> dict[str, Any]:
    return {
        "id": record["id"],
        "base_model_id": record.get("base_model_id"),
        "name": record.get("name") or record["id"],
        "meta": copy.deepcopy(record.get("meta") or {}),
        "params": copy.deepcopy(record.get("params") or {}),
        "access_grants": _grant_payload(record),
        "is_active": (
            bool(record.get("is_active", True))
            if is_active is None
            else is_active
        ),
    }


def _is_managed_ndfl(record: dict[str, Any]) -> bool:
    meta = record.get("meta")
    binding = (
        meta.get("broker_reports_product_binding")
        if isinstance(meta, dict)
        else None
    )
    return bool(
        record.get("id") == NDFL_WORKSPACE_MODEL_STABLE_ID
        and record.get("base_model_id") == NDFL_OPENWEBUI_BASE_PIPE_ID
        and isinstance(binding, dict)
        and binding.get("workspace_model_id")
        == NDFL_WORKSPACE_MODEL_STABLE_ID
        and binding.get("base_pipe_id") == NDFL_OPENWEBUI_BASE_PIPE_ID
    )


def _is_managed_legacy_ndfl(record: dict[str, Any]) -> bool:
    meta = record.get("meta")
    binding = (
        meta.get("broker_reports_product_binding")
        if isinstance(meta, dict)
        else None
    )
    return bool(
        record.get("id") == LEGACY_NDFL_MODEL_ID
        and isinstance(binding, dict)
        and binding.get("workspace_model_id") == LEGACY_NDFL_MODEL_ID
    )


def evaluate_required_base_model(record: dict[str, Any] | None) -> dict[str, bool]:
    checks = {
        "present": record is not None,
        "stable_id_match": bool(
            record and record.get("id") == NDFL_OPENWEBUI_BASE_PIPE_ID
        ),
        "not_a_facade": bool(record and record.get("base_model_id") is None),
        "active": bool(record and record.get("is_active") is True),
    }
    return {**checks, "passed": all(checks.values())}


def evaluate_required_base_function(
    record: dict[str, Any] | None,
) -> dict[str, bool]:
    checks = {
        "present": record is not None,
        "stable_id_match": bool(record and record.get("id") == FUNCTION_ID),
        "pipe": bool(record and record.get("type") == "pipe"),
        "active": bool(record and record.get("is_active") is True),
        "not_global": bool(record and record.get("is_global") is False),
    }
    return {**checks, "passed": all(checks.values())}


def _is_managed_hidden_route(record: dict[str, Any], pipe_id: str) -> bool:
    meta = record.get("meta")
    marker = (
        meta.get("broker_reports_hidden_route")
        if isinstance(meta, dict)
        else None
    )
    return bool(
        record.get("id") == pipe_id
        and isinstance(marker, dict)
        and marker.get("schema_version") == HIDDEN_ROUTE_SCHEMA_VERSION
        and marker.get("route_id") == pipe_id
    )


def _is_safe_existing_pipe_override(
    record: dict[str, Any],
    pipe_id: str,
) -> bool:
    """Accept the native ACL/model override already created for this Pipe ID."""

    meta = record.get("meta")
    return bool(
        record.get("id") == pipe_id
        and record.get("base_model_id") is None
        and isinstance(meta, dict)
        and "broker_reports_product_binding" not in meta
        and (record.get("params") or {}) == {}
    )


def _publish_model(
    session: requests.Session,
    base_url: str,
    *,
    desired: dict[str, Any],
    previous: dict[str, Any] | None,
) -> str:
    endpoint = (
        "/api/v1/models/create"
        if previous is None
        else "/api/v1/models/model/update"
    )
    value = _request_json(
        session,
        "POST",
        _url(base_url, endpoint),
        payload=desired,
    )
    if not isinstance(value, dict) or value.get("id") != desired["id"]:
        raise NdflWorkspacePublishError("openwebui_model_publish_invalid")
    return "created" if previous is None else "updated"


def _restore_model(
    session: requests.Session,
    base_url: str,
    *,
    stable_id: str,
    previous: dict[str, Any] | None,
) -> None:
    if previous is None:
        _request_json(
            session,
            "POST",
            _url(base_url, "/api/v1/models/model/delete"),
            payload={"id": stable_id},
        )
        return
    _request_json(
        session,
        "POST",
        _url(base_url, "/api/v1/models/model/update"),
        payload=_model_form(previous),
    )


def _rollback_models(
    session: requests.Session,
    base_url: str,
    *,
    mutated: list[str],
    previous: dict[str, dict[str, Any] | None],
) -> list[str]:
    rollback_errors: list[str] = []
    for stable_id in reversed(mutated):
        try:
            _restore_model(
                session,
                base_url,
                stable_id=stable_id,
                previous=previous[stable_id],
            )
        except Exception as exc:
            rollback_errors.append(f"{stable_id}:{type(exc).__name__}")
    return rollback_errors


def evaluate_ndfl_model(record: dict[str, Any] | None) -> dict[str, Any]:
    meta = record.get("meta") if record else None
    binding = (
        meta.get("broker_reports_product_binding")
        if isinstance(meta, dict)
        else None
    )
    tags = meta.get("tags") if isinstance(meta, dict) else []
    tag_names = sorted(
        str(item.get("name"))
        for item in tags
        if isinstance(item, dict) and item.get("name")
    )
    routing_checks = {
        "present": record is not None,
        "workspace_model_id_match": bool(
            record
            and record.get("id") == NDFL_WORKSPACE_MODEL_STABLE_ID
        ),
        "base_pipe_id_match": bool(
            record and record.get("base_model_id") == NDFL_OPENWEBUI_BASE_PIPE_ID
        ),
        "function_id_match": FUNCTION_ID == NDFL_OPENWEBUI_BASE_PIPE_ID,
        "active": bool(record and record.get("is_active") is True),
        "stable_binding_topology_exact": bool(
            isinstance(binding, dict)
            and binding.get("workspace_model_id")
            == NDFL_WORKSPACE_MODEL_STABLE_ID
            and binding.get("base_pipe_id") == NDFL_OPENWEBUI_BASE_PIPE_ID
            and binding.get("workflow_id") == NDFL_WORKSPACE_MODEL_STABLE_ID
        ),
        "knowledge_empty": bool(
            isinstance(meta, dict) and meta.get("knowledge") == []
        ),
        "tool_ids_empty": bool(
            isinstance(meta, dict) and meta.get("toolIds") == []
        ),
        "skill_ids_empty": bool(
            isinstance(meta, dict) and meta.get("skillIds") == []
        ),
    }
    return {
        **routing_checks,
        "display_name_match": bool(
            record and record.get("name") == NDFL_WORKFLOW_DISPLAY_NAME
        ),
        "managed_tags_match": tag_names
        == ["broker-reports", "managed", "ndfl"],
        "routing_passed": all(routing_checks.values()),
    }


def evaluate_hidden_pipe_model(
    record: dict[str, Any] | None,
    pipe_id: str,
) -> dict[str, Any]:
    expected_active = False
    return {
        "present": record is not None,
        "stable_id_match": bool(record and record.get("id") == pipe_id),
        "base_model_override": bool(
            record and record.get("base_model_id") is None
        ),
        "runtime_state_match": bool(
            record and record.get("is_active") is expected_active
        ),
        "runtime_base_required_match": bool(
            record
            and isinstance((record.get("meta") or {}).get(
                "broker_reports_hidden_route"
            ), dict)
            and (record["meta"]["broker_reports_hidden_route"].get(
                "runtime_base_required"
            ) is expected_active)
        ),
        "managed_marker": bool(
            record and _is_managed_hidden_route(record, pipe_id)
        ),
    }


def evaluate_visible_routes(
    visible_models: list[dict[str, Any]],
) -> dict[str, Any]:
    visible_ids = {
        str(item.get("id"))
        for item in visible_models
        if item.get("id") in PRODUCT_ROUTE_IDS
    }
    internal_base_ids = visible_ids & {NDFL_OPENWEBUI_BASE_PIPE_ID}
    competing_ids = visible_ids - {
        NDFL_WORKSPACE_MODEL_STABLE_ID,
        NDFL_OPENWEBUI_BASE_PIPE_ID,
    }
    return {
        "visible_product_route_ids": sorted(
            visible_ids & {NDFL_WORKSPACE_MODEL_STABLE_ID}
        ),
        "visible_internal_runtime_base_ids": sorted(internal_base_ids),
        "user_facing_ndfl_models": int(
            NDFL_WORKSPACE_MODEL_STABLE_ID in visible_ids
        ),
        "legacy_or_competing_routes_visible": sorted(competing_ids),
        "passed": bool(
            NDFL_WORKSPACE_MODEL_STABLE_ID in visible_ids and not competing_ids
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish the NDFL facade and deactivate only managed legacy routes.",
    )
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    tracked_ids = (
        NDFL_WORKSPACE_MODEL_STABLE_ID,
        NDFL_OPENWEBUI_BASE_PIPE_ID,
        LEGACY_NDFL_MODEL_ID,
        LEGACY_WORKSPACE_MODEL_ID,
        *TECHNICAL_PIPE_IDS,
    )
    previous = {
        stable_id: _get_model(session, base_url, stable_id)
        for stable_id in tracked_ids
    }
    base_model_check = evaluate_required_base_model(
        previous[NDFL_OPENWEBUI_BASE_PIPE_ID]
    )
    base_function_check = evaluate_required_base_function(
        _get_function(session, base_url, FUNCTION_ID)
    )
    if not base_model_check["passed"] or not base_function_check["passed"]:
        raise NdflWorkspacePublishError("ndfl_base_pipe_topology_invalid")
    if (
        previous[NDFL_WORKSPACE_MODEL_STABLE_ID] is not None
        and not _is_managed_ndfl(previous[NDFL_WORKSPACE_MODEL_STABLE_ID])
    ):
        raise NdflWorkspacePublishError("ndfl_workspace_model_id_collision")
    if (
        previous[LEGACY_NDFL_MODEL_ID] is not None
        and not _is_managed_legacy_ndfl(previous[LEGACY_NDFL_MODEL_ID])
    ):
        raise NdflWorkspacePublishError("legacy_ndfl_workspace_model_id_collision")
    for pipe_id in TECHNICAL_PIPE_IDS:
        if previous[pipe_id] is not None and not (
            _is_managed_hidden_route(previous[pipe_id], pipe_id)
            or _is_safe_existing_pipe_override(previous[pipe_id], pipe_id)
        ):
            raise NdflWorkspacePublishError(
                f"technical_route_override_id_collision:{pipe_id}"
            )
    legacy_workspace = previous[LEGACY_WORKSPACE_MODEL_ID]
    legacy_ndfl = previous[LEGACY_NDFL_MODEL_ID]
    legacy = legacy_ndfl or legacy_workspace
    if legacy_workspace is not None and (
        legacy_workspace.get("base_model_id") != NDFL_OPENWEBUI_BASE_PIPE_ID
        or legacy_workspace.get("id") != LEGACY_WORKSPACE_MODEL_ID
    ):
        raise NdflWorkspacePublishError("legacy_workspace_model_identity_changed")

    desired = {
        NDFL_WORKSPACE_MODEL_STABLE_ID: desired_ndfl_model(
            previous=previous[NDFL_WORKSPACE_MODEL_STABLE_ID],
            legacy=legacy,
        ),
        **{
            pipe_id: desired_hidden_pipe_model(
                pipe_id,
                previous=previous[pipe_id],
            )
            for pipe_id in TECHNICAL_PIPE_IDS
        },
    }
    if legacy_ndfl is not None:
        desired[LEGACY_NDFL_MODEL_ID] = _model_form(
            legacy_ndfl,
            is_active=False,
        )
    if legacy_workspace is not None:
        desired[LEGACY_WORKSPACE_MODEL_ID] = _model_form(
            legacy_workspace,
            is_active=False,
        )

    actions = {stable_id: "read_only" for stable_id in tracked_ids}
    mutated: list[str] = []
    if args.publish:
        try:
            for stable_id in (
                NDFL_WORKSPACE_MODEL_STABLE_ID,
                LEGACY_NDFL_MODEL_ID,
                *TECHNICAL_PIPE_IDS,
                LEGACY_WORKSPACE_MODEL_ID,
            ):
                if stable_id not in desired:
                    actions[stable_id] = "absent"
                    continue
                if (
                    previous[stable_id] is not None
                    and _model_form(previous[stable_id]) == desired[stable_id]
                ):
                    actions[stable_id] = "already_exact"
                    continue
                actions[stable_id] = _publish_model(
                    session,
                    base_url,
                    desired=desired[stable_id],
                    previous=previous[stable_id],
                )
                mutated.append(stable_id)
        except Exception as exc:
            rollback_errors = _rollback_models(
                session,
                base_url,
                mutated=mutated,
                previous=previous,
            )
            raise NdflWorkspacePublishError(
                f"ndfl_workspace_publish_failed:{type(exc).__name__}:"
                f"rollback_errors={','.join(rollback_errors) or 'none'}"
            ) from exc

    try:
        current = {
            stable_id: _get_model(session, base_url, stable_id)
            for stable_id in tracked_ids
        }
        current_base_model_check = evaluate_required_base_model(
            current[NDFL_OPENWEBUI_BASE_PIPE_ID]
        )
        current_base_function_check = evaluate_required_base_function(
            _get_function(session, base_url, FUNCTION_ID)
        )
        ndfl_check = evaluate_ndfl_model(
            current[NDFL_WORKSPACE_MODEL_STABLE_ID]
        )
        hidden_checks = {
            pipe_id: evaluate_hidden_pipe_model(current[pipe_id], pipe_id)
            for pipe_id in TECHNICAL_PIPE_IDS
        }
        legacy_ndfl_inactive = bool(
            current[LEGACY_NDFL_MODEL_ID] is None
            or current[LEGACY_NDFL_MODEL_ID].get("is_active") is False
        )
        legacy_workspace_inactive = bool(
            current[LEGACY_WORKSPACE_MODEL_ID] is None
            or current[LEGACY_WORKSPACE_MODEL_ID].get("is_active") is False
        )
        visible_check = evaluate_visible_routes(
            _get_visible_models(session, base_url)
        )
        hidden_pass = all(
            all(check.values()) for check in hidden_checks.values()
        )
        passed = bool(
            current_base_model_check["passed"]
            and current_base_function_check["passed"]
            and ndfl_check["routing_passed"]
            and ndfl_check["display_name_match"]
            and ndfl_check["managed_tags_match"]
            and hidden_pass
            and legacy_ndfl_inactive
            and legacy_workspace_inactive
            and visible_check["passed"]
        )
    except Exception as exc:
        rollback_errors = (
            _rollback_models(
                session,
                base_url,
                mutated=mutated,
                previous=previous,
            )
            if args.publish
            else []
        )
        raise NdflWorkspacePublishError(
            f"ndfl_workspace_readback_failed:{type(exc).__name__}:"
            f"rollback_errors={','.join(rollback_errors) or 'none'}"
        ) from exc

    if args.publish and not passed:
        rollback_errors = _rollback_models(
            session,
            base_url,
            mutated=mutated,
            previous=previous,
        )
        raise NdflWorkspacePublishError(
            "ndfl_workspace_publish_failed:postcondition_failed:"
            f"rollback_errors={','.join(rollback_errors) or 'none'}"
        )
    result = {
        "schema_version": "broker_reports_ndfl_workspace_model_live_binding_v1",
        "mode": "publish" if args.publish else "read_only",
        "status": "passed" if passed else "not_bound",
        "gui_path": "Workspace -> Models -> NDFL",
        "stable_bindings": ndfl_product_binding_snapshot(),
        "actions": actions,
        "checks": {
            "required_base_model": current_base_model_check,
            "required_base_function": current_base_function_check,
            "ndfl_workspace_model": ndfl_check,
            "hidden_technical_routes": hidden_checks,
            "legacy_ndfl_model_inactive": legacy_ndfl_inactive,
            "legacy_workspace_model_inactive": legacy_workspace_inactive,
            "visible_routes": visible_check,
            "behavioral_display_name_lookups": 0,
            "rename_safety": "covered_by_integration_test",
        },
        "knowledge_rag": "none",
        "provider_calls": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
