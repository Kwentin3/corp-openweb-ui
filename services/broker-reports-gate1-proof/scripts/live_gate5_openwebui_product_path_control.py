#!/usr/bin/env python3
"""Prepare and restore the bounded G5.36 OpenWebUI browser-proof window."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
FUNCTION_ID = "broker_reports_ndfl"
MODEL_ID = FUNCTION_ID
LEGACY_FUNCTION_ID = "broker_reports_gate1_pipe"
BUNDLE_PATH = SERVICE_ROOT / "openwebui_actions/broker_reports_gate1_pipe_bundled.py"
VISIBLE_PROOF_USER_SUFFIXES = ("a", "c", "d", "e", "f", "g", "h")
HIDDEN_PROOF_USER_SUFFIX = "b"

sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_atomic_stage_release_contracts import (  # noqa: E402
    GATE1_RELEASE_VALVES,
    GATE1_RETIRED_VALVE_KEYS,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


class G536ControlError(RuntimeError):
    pass


def _request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    payload: Any = None,
    timeout: int = 60,
    allow_missing: bool = False,
) -> Any:
    response = session.request(method, url, json=payload, timeout=timeout)
    if allow_missing and response.status_code in {400, 401, 404}:
        return None
    if not 200 <= response.status_code < 300:
        raise G536ControlError(
            f"openwebui_control_request_failed:{method}:{response.status_code}"
        )
    if not response.content:
        return None
    try:
        return response.json()
    except requests.JSONDecodeError as exc:
        raise G536ControlError("openwebui_control_response_not_json") from exc


def _admin_session(env: dict[str, str], base_url: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def _get_function(session: requests.Session, base_url: str) -> dict[str, Any]:
    value = _request_json(
        session,
        "GET",
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}"),
    )
    if not isinstance(value, dict) or value.get("id") != FUNCTION_ID:
        raise G536ControlError("function_readback_invalid")
    return value


def _get_legacy_function(
    session: requests.Session,
    base_url: str,
) -> dict[str, Any] | None:
    value = _request_json(
        session,
        "GET",
        _url(base_url, f"/api/v1/functions/id/{LEGACY_FUNCTION_ID}"),
        allow_missing=True,
    )
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("id") != LEGACY_FUNCTION_ID:
        raise G536ControlError("legacy_function_readback_invalid")
    return value


def _toggle_function_active(
    session: requests.Session,
    base_url: str,
    function_id: str,
) -> dict[str, Any]:
    value = _request_json(
        session,
        "POST",
        _url(base_url, f"/api/v1/functions/id/{function_id}/toggle"),
    )
    if not isinstance(value, dict) or value.get("id") != function_id:
        raise G536ControlError("function_active_toggle_invalid")
    return value


def _get_valves(session: requests.Session, base_url: str) -> dict[str, Any]:
    value = _request_json(
        session,
        "GET",
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/valves"),
    )
    if not isinstance(value, dict):
        raise G536ControlError("function_valves_readback_invalid")
    return value


def _update_valves(
    session: requests.Session,
    base_url: str,
    valves: dict[str, Any],
) -> dict[str, Any]:
    value = _request_json(
        session,
        "POST",
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/valves/update"),
        payload=valves,
    )
    if not isinstance(value, dict):
        raise G536ControlError("function_valves_update_invalid")
    return value


def _get_model(session: requests.Session, base_url: str) -> dict[str, Any]:
    value = _request_json(
        session,
        "GET",
        _url(base_url, f"/api/v1/models/model?id={MODEL_ID}"),
    )
    if not isinstance(value, dict) or value.get("id") != MODEL_ID:
        raise G536ControlError("workspace_model_readback_invalid")
    return value


def _grant_payload(record: dict[str, Any]) -> list[dict[str, str]]:
    grants = record.get("access_grants")
    if not isinstance(grants, list):
        return []
    return [
        {
            key: str(grant[key])
            for key in ("principal_type", "principal_id", "permission")
            if key in grant
        }
        for grant in grants
        if isinstance(grant, dict)
    ]


def _update_model_grants(
    session: requests.Session,
    base_url: str,
    grants: list[dict[str, str]],
) -> dict[str, Any]:
    value = _request_json(
        session,
        "POST",
        _url(base_url, "/api/v1/models/model/access/update"),
        payload={"id": MODEL_ID, "name": MODEL_ID, "access_grants": grants},
    )
    if not isinstance(value, dict) or value.get("id") != MODEL_ID:
        raise G536ControlError("workspace_model_grants_update_invalid")
    return value


def _toggle_global(session: requests.Session, base_url: str) -> dict[str, Any]:
    value = _request_json(
        session,
        "POST",
        _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/toggle/global"),
    )
    if not isinstance(value, dict) or value.get("id") != FUNCTION_ID:
        raise G536ControlError("function_global_toggle_invalid")
    return value


def _create_user(
    session: requests.Session,
    base_url: str,
    *,
    suffix: str,
    role: str,
) -> dict[str, str]:
    email = f"g536-{suffix}-{secrets.token_hex(6)}@example.invalid"
    password = "G536!" + secrets.token_urlsafe(24)
    value = _request_json(
        session,
        "POST",
        _url(base_url, "/api/v1/auths/add"),
        payload={
            "name": f"G5.36 User {suffix.upper()}",
            "email": email,
            "password": password,
            "role": role,
        },
    )
    if not isinstance(value, dict) or not value.get("id"):
        raise G536ControlError("temporary_user_create_invalid")
    return {
        "id": str(value["id"]),
        "email": email,
        "password": password,
        "role": role,
    }


def _delete_user(
    session: requests.Session,
    base_url: str,
    user_id: str,
) -> None:
    _request_json(
        session,
        "DELETE",
        _url(base_url, f"/api/v1/users/{user_id}"),
        allow_missing=True,
    )


def _user_model_visibility(
    base_url: str,
    email: str,
    password: str,
) -> bool:
    session = requests.Session()
    signed_in = _request_json(
        session,
        "POST",
        _url(base_url, "/api/v1/auths/signin"),
        payload={"email": email, "password": password},
    )
    if not isinstance(signed_in, dict) or not signed_in.get("token"):
        raise G536ControlError("temporary_user_signin_invalid")
    session.headers.update(
        {
            "Accept": "application/json",
            "Authorization": f"Bearer {signed_in['token']}",
        }
    )
    value = _request_json(
        session,
        "GET",
        _url(base_url, "/api/models?refresh=true"),
    )
    models = value.get("data") if isinstance(value, dict) else value
    if not isinstance(models, list):
        raise G536ControlError("visible_models_response_invalid")
    return any(isinstance(item, dict) and item.get("id") == MODEL_ID for item in models)


def _deploy_bundle(
    session: requests.Session,
    base_url: str,
    function: dict[str, Any],
) -> tuple[str, str]:
    source = BUNDLE_PATH.read_text(encoding="utf-8")
    source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
    previous_sha256 = hashlib.sha256(
        str(function.get("content") or "").encode("utf-8")
    ).hexdigest()
    try:
        _request_json(
            session,
            "POST",
            _url(base_url, f"/api/v1/functions/id/{FUNCTION_ID}/update"),
            payload={
                "id": FUNCTION_ID,
                "name": function.get("name") or "Broker Reports Gate 1",
                "meta": function.get("meta")
                if isinstance(function.get("meta"), dict)
                else {},
                "content": source,
            },
            timeout=360,
        )
    except requests.Timeout:
        pass
    live = _get_function(session, base_url)
    live_sha256 = hashlib.sha256(
        str(live.get("content") or "").encode("utf-8")
    ).hexdigest()
    if live_sha256 != source_sha256:
        raise G536ControlError("deployed_bundle_hash_mismatch")
    return previous_sha256, live_sha256


def _write_private_state(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _safe_result(state: dict[str, Any], *, status: str) -> dict[str, Any]:
    applied_valves = state.get("applied_valves") or {}
    base = {
        "schema_version": "broker_reports_gate5_openwebui_control_v0",
        "status": status,
        "function_id": FUNCTION_ID,
        "workspace_model_id": MODEL_ID,
        "control_run_id": state.get("control_run_id"),
        "deployed_bundle_sha256": state.get("deployed_bundle_sha256"),
        "predecessor_control_prepared_receipt_sha256": (
            state.get("control_prepared_receipt_sha256")
            if status in {"prepared", "restored"}
            else None
        ),
        "temporary_users": len(state.get("users") or []),
        "user_a_model_visible": state.get("user_a_model_visible"),
        "user_b_model_hidden": state.get("user_b_model_hidden"),
        "model_public_grant_added": False,
        "proof_valves_enabled": status == "prepared",
        "release_valves_exact": bool(
            status == "prepared"
            and all(
                applied_valves.get(key) == expected
                for key, expected in GATE1_RELEASE_VALVES.items()
            )
        ),
        "legacy_function_inactive": bool(
            status == "prepared" and state.get("legacy_function_inactive") is True
        ),
        "state_restored": status == "restored",
    }
    encoded = json.dumps(
        base, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return {**base, "receipt_sha256": hashlib.sha256(encoded).hexdigest()}


def _proof_valves(
    before_valves: dict[str, Any],
    *,
    audit_id: str,
) -> dict[str, Any]:
    current = {
        key: value
        for key, value in before_valves.items()
        if key not in GATE1_RETIRED_VALVE_KEYS
    }
    return {
        **current,
        **GATE1_RELEASE_VALVES,
        "ndfl_gate3_private_audit_enabled": bool(audit_id),
        "ndfl_gate3_private_audit_id": audit_id or "",
    }


def _prepare(args: argparse.Namespace) -> int:
    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    state_path = output_dir / "control.private.json"
    safe_path = output_dir / "control-prepared.safe.json"
    session = _admin_session(env, base_url)

    before_function = _get_function(session, base_url)
    before_legacy_function = _get_legacy_function(session, base_url)
    before_valves = _get_valves(session, base_url)
    before_model = _get_model(session, base_url)
    before_grants = _grant_payload(before_model)
    users: list[dict[str, str]] = []
    grants_changed = False
    global_changed = False
    valves_changed = False
    legacy_function_changed = False
    try:
        live_legacy_function = before_legacy_function
        if bool(
            isinstance(live_legacy_function, dict)
            and live_legacy_function.get("is_active") is not False
        ):
            live_legacy_function = _toggle_function_active(
                session,
                base_url,
                LEGACY_FUNCTION_ID,
            )
            legacy_function_changed = True
        legacy_function_inactive = bool(
            live_legacy_function is None
            or live_legacy_function.get("is_active") is False
        )
        if not legacy_function_inactive:
            raise G536ControlError("legacy_function_active_in_proof_window")

        previous_bundle_sha256, deployed_bundle_sha256 = _deploy_bundle(
            session, base_url, before_function
        )
        visible_users = [
            _create_user(session, base_url, suffix=suffix, role="user")
            for suffix in VISIBLE_PROOF_USER_SUFFIXES
        ]
        user_a = visible_users[0]
        user_b = _create_user(
            session,
            base_url,
            suffix=HIDDEN_PROOF_USER_SUFFIX,
            role="user",
        )
        users.extend([user_a, user_b, *visible_users[1:]])
        proof_grants = [
            *before_grants,
            *[
                {
                    "principal_type": "user",
                    "principal_id": user["id"],
                    "permission": "read",
                }
                for user in visible_users
            ],
        ]
        updated_model = _update_model_grants(session, base_url, proof_grants)
        grants_changed = True
        if _grant_payload(updated_model) != proof_grants:
            raise G536ControlError("workspace_model_grants_readback_mismatch")

        live_function = _get_function(session, base_url)
        if not bool(live_function.get("is_global")):
            live_function = _toggle_global(session, base_url)
            global_changed = True
        if not bool(live_function.get("is_global")):
            raise G536ControlError("function_not_global_in_proof_window")

        proof_valves = _proof_valves(
            before_valves,
            audit_id=args.audit_id,
        )
        updated_valves = _update_valves(session, base_url, proof_valves)
        valves_changed = True
        if updated_valves != proof_valves:
            raise G536ControlError("proof_valves_readback_mismatch")

        visible_user_results = [
            _user_model_visibility(base_url, user["email"], user["password"])
            for user in visible_users
        ]
        user_a_visible = all(visible_user_results)
        user_b_visible = _user_model_visibility(
            base_url,
            user_b["email"],
            user_b["password"],
        )
        if not user_a_visible or user_b_visible:
            raise G536ControlError("temporary_model_visibility_invalid")

        state = {
            "schema_version": "broker_reports_gate5_openwebui_control_private_v0",
            "control_run_id": secrets.token_hex(16),
            "base_url": base_url,
            "original_model_access_grants": before_grants,
            "original_function_global": bool(before_function.get("is_global")),
            "original_legacy_function_active": (
                None
                if before_legacy_function is None
                else before_legacy_function.get("is_active") is not False
            ),
            "legacy_function_inactive": legacy_function_inactive,
            "original_valves": before_valves,
            "applied_valves": proof_valves,
            "previous_bundle_sha256": previous_bundle_sha256,
            "deployed_bundle_sha256": deployed_bundle_sha256,
            "users": users,
            "user_a_model_visible": user_a_visible,
            "user_b_model_hidden": not user_b_visible,
        }
        safe = _safe_result(state, status="prepared")
        state["control_prepared_receipt_sha256"] = safe["receipt_sha256"]
        _write_private_state(state_path, state)
        safe_path.write_text(
            json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({**safe, "private_state_path": str(state_path)}))
        return 0
    except Exception:
        rollback_errors: list[str] = []
        if valves_changed:
            try:
                _update_valves(session, base_url, before_valves)
            except Exception as exc:
                rollback_errors.append(f"valves:{type(exc).__name__}")
        if global_changed:
            try:
                if bool(_get_function(session, base_url).get("is_global")) != bool(
                    before_function.get("is_global")
                ):
                    _toggle_global(session, base_url)
            except Exception as exc:
                rollback_errors.append(f"global:{type(exc).__name__}")
        if grants_changed:
            try:
                _update_model_grants(session, base_url, before_grants)
            except Exception as exc:
                rollback_errors.append(f"grants:{type(exc).__name__}")
        if legacy_function_changed:
            try:
                legacy = _get_legacy_function(session, base_url)
                if legacy is not None and legacy.get("is_active") is False:
                    _toggle_function_active(
                        session,
                        base_url,
                        LEGACY_FUNCTION_ID,
                    )
            except Exception as exc:
                rollback_errors.append(f"legacy_function:{type(exc).__name__}")
        for user in reversed(users):
            try:
                _delete_user(session, base_url, user["id"])
            except Exception as exc:
                rollback_errors.append(f"user:{type(exc).__name__}")
        if rollback_errors:
            raise G536ControlError(
                "preparation_failed_and_rollback_incomplete:" + ",".join(rollback_errors)
            )
        raise


def _set_audit(args: argparse.Namespace) -> int:
    state = json.loads(Path(args.state).read_text(encoding="utf-8"))
    env = _read_env(Path(args.env_file))
    base_url = str(state["base_url"])
    session = _admin_session(env, base_url)
    valves = _get_valves(session, base_url)
    expected = {
        **valves,
        "ndfl_gate3_private_audit_enabled": bool(args.audit_id),
        "ndfl_gate3_private_audit_id": args.audit_id or "",
    }
    actual = _update_valves(session, base_url, expected)
    if actual != expected:
        raise G536ControlError("audit_valves_readback_mismatch")
    print(
        json.dumps(
            {
                "schema_version": "broker_reports_gate5_openwebui_control_v0",
                "status": "audit_configured",
                "private_audit_enabled": bool(args.audit_id),
            }
        )
    )
    return 0


def _redeploy(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    env = _read_env(Path(args.env_file))
    base_url = str(state["base_url"])
    session = _admin_session(env, base_url)
    _, deployed_sha256 = _deploy_bundle(
        session,
        base_url,
        _get_function(session, base_url),
    )
    state["deployed_bundle_sha256"] = deployed_sha256
    safe = _safe_result(state, status="prepared")
    state["control_prepared_receipt_sha256"] = safe["receipt_sha256"]
    _write_private_state(state_path, state)
    safe_path = state_path.parent / "control-prepared.safe.json"
    safe_path.write_text(
        json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema_version": "broker_reports_gate5_openwebui_control_v0",
                "status": "bundle_deployed",
                "deployed_bundle_sha256": deployed_sha256,
                "control_prepared_receipt_sha256": safe["receipt_sha256"],
            }
        )
    )
    return 0


def _cleanup(args: argparse.Namespace) -> int:
    state_path = Path(args.state).resolve()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    env = _read_env(Path(args.env_file))
    base_url = str(state["base_url"])
    session = _admin_session(env, base_url)
    errors: list[str] = []
    try:
        _update_valves(session, base_url, dict(state["original_valves"]))
    except Exception as exc:
        errors.append(f"valves:{type(exc).__name__}")
    try:
        live_global = bool(_get_function(session, base_url).get("is_global"))
        original_global = bool(state["original_function_global"])
        if live_global != original_global:
            _toggle_global(session, base_url)
        if bool(_get_function(session, base_url).get("is_global")) != original_global:
            raise G536ControlError("function_global_restore_mismatch")
    except Exception as exc:
        errors.append(f"global:{type(exc).__name__}")
    try:
        restored_model = _update_model_grants(
            session,
            base_url,
            list(state["original_model_access_grants"]),
        )
        if _grant_payload(restored_model) != list(state["original_model_access_grants"]):
            raise G536ControlError("workspace_model_grants_restore_mismatch")
    except Exception as exc:
        errors.append(f"grants:{type(exc).__name__}")
    try:
        original_legacy_active = state.get("original_legacy_function_active")
        legacy = _get_legacy_function(session, base_url)
        if legacy is not None and isinstance(original_legacy_active, bool):
            live_legacy_active = legacy.get("is_active") is not False
            if live_legacy_active != original_legacy_active:
                legacy = _toggle_function_active(
                    session,
                    base_url,
                    LEGACY_FUNCTION_ID,
                )
            if (legacy.get("is_active") is not False) != original_legacy_active:
                raise G536ControlError("legacy_function_active_restore_mismatch")
    except Exception as exc:
        errors.append(f"legacy_function:{type(exc).__name__}")
    for user in reversed(list(state.get("users") or [])):
        try:
            _delete_user(session, base_url, str(user["id"]))
        except Exception as exc:
            errors.append(f"user:{type(exc).__name__}")
    if errors:
        raise G536ControlError("cleanup_incomplete:" + ",".join(errors))
    safe = _safe_result(state, status="restored")
    safe_path = state_path.parent / "control-restored.safe.json"
    safe_path.write_text(
        json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(safe))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--output-dir", required=True)
    prepare.add_argument("--audit-id", default="")

    set_audit = subparsers.add_parser("set-audit")
    set_audit.add_argument("--state", required=True)
    set_audit.add_argument("--audit-id", default="")

    redeploy = subparsers.add_parser("deploy")
    redeploy.add_argument("--state", required=True)

    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--state", required=True)

    args = parser.parse_args()
    if args.command == "prepare":
        return _prepare(args)
    if args.command == "set-audit":
        return _set_audit(args)
    if args.command == "deploy":
        return _redeploy(args)
    return _cleanup(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema_version": "broker_reports_gate5_openwebui_control_v0",
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "error_code": str(exc)[:200],
                }
            )
        )
        raise
