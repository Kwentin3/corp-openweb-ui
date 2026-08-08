#!/usr/bin/env python3
"""Disable only proven live legacy routes that compete with NDFL."""

from __future__ import annotations

import argparse
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
    NDFL_WORKSPACE_MODEL_STABLE_ID,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)
from live_publish_ndfl_workspace_model import (  # noqa: E402
    _get_model,
    _get_visible_models,
    _request_json,
    evaluate_ndfl_model,
    evaluate_visible_routes,
)


LEGACY_FUNCTIONS_TO_DISABLE = {
    "broker_reports_gate1_normalizer_action": "proof_only_global_gate1_stub",
    "broker_reports_gate2_source_fact_pipe": "legacy_user_selectable_gate2_pipe",
    "broker_reports_gate2_domain_source_fact_pipe": (
        "legacy_user_selectable_gate2_domain_pipe"
    ),
}
REQUIRED_ACTIVE_FUNCTIONS = {
    NDFL_OPENWEBUI_BASE_PIPE_ID: "ndfl_base_pipe",
    "broker_reports_private_intake_action": "server_attested_private_intake",
}
NON_COMPETING_UTILITY_FUNCTIONS = {
    "broker_reports_gate2_economy_qualification_action": (
        "qualification_only_not_global_not_attached_to_ndfl"
    ),
}

FACTORY_REQUIRED = (
    "Cleanup must preserve the NDFL base Pipe and existing factory owners; "
    "only exact stable-ID legacy Functions may be toggled inactive"
)
FORBIDDEN = (
    "Cleanup must not delete history, disable the NDFL base Pipe, change "
    "prompts/dictionary meaning, attach Knowledge/RAG or resolve by name"
)


class LegacyRouteCleanupError(RuntimeError):
    pass


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
        raise LegacyRouteCleanupError("openwebui_function_readback_invalid")
    return value


def _toggle_function(
    session: requests.Session,
    base_url: str,
    stable_id: str,
) -> dict[str, Any]:
    value = _request_json(
        session,
        "POST",
        _url(base_url, f"/api/v1/functions/id/{stable_id}/toggle"),
    )
    if not isinstance(value, dict) or value.get("id") != stable_id:
        raise LegacyRouteCleanupError("openwebui_function_toggle_invalid")
    return value


def evaluate_function_state(
    record: dict[str, Any],
    *,
    stable_id: str,
    expected_type: str,
    expected_active: bool,
    expected_global: bool | None = None,
) -> dict[str, Any]:
    checks = {
        "stable_id_match": record.get("id") == stable_id,
        "type_match": record.get("type") == expected_type,
        "active_match": record.get("is_active") is expected_active,
    }
    if expected_global is not None:
        checks["global_match"] = record.get("is_global") is expected_global
    return {**checks, "passed": all(checks.values())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Toggle the exact allowlisted legacy Functions inactive.",
    )
    args = parser.parse_args()

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    all_ids = (
        *LEGACY_FUNCTIONS_TO_DISABLE,
        *REQUIRED_ACTIVE_FUNCTIONS,
        *NON_COMPETING_UTILITY_FUNCTIONS,
    )
    previous = {
        stable_id: _get_function(session, base_url, stable_id)
        for stable_id in all_ids
    }
    expected_types = {
        "broker_reports_gate1_normalizer_action": "action",
        "broker_reports_gate2_source_fact_pipe": "pipe",
        "broker_reports_gate2_domain_source_fact_pipe": "pipe",
        NDFL_OPENWEBUI_BASE_PIPE_ID: "pipe",
        "broker_reports_private_intake_action": "action",
        "broker_reports_gate2_economy_qualification_action": "action",
    }
    for stable_id, record in previous.items():
        if record.get("type") != expected_types[stable_id]:
            raise LegacyRouteCleanupError(
                f"legacy_cleanup_function_identity_changed:{stable_id}"
            )

    actions = {stable_id: "read_only" for stable_id in all_ids}
    toggled: list[str] = []
    if args.apply:
        try:
            for stable_id in LEGACY_FUNCTIONS_TO_DISABLE:
                if previous[stable_id].get("is_active") is False:
                    actions[stable_id] = "already_inactive"
                    continue
                updated = _toggle_function(session, base_url, stable_id)
                if updated.get("is_active") is not False:
                    raise LegacyRouteCleanupError(
                        f"legacy_function_did_not_deactivate:{stable_id}"
                    )
                actions[stable_id] = "deactivated"
                toggled.append(stable_id)
        except Exception as exc:
            rollback_errors: list[str] = []
            for stable_id in reversed(toggled):
                try:
                    restored = _toggle_function(session, base_url, stable_id)
                    if restored.get("is_active") is not True:
                        raise LegacyRouteCleanupError(
                            "legacy_function_rollback_state_mismatch"
                        )
                except Exception as rollback_exc:
                    rollback_errors.append(
                        f"{stable_id}:{type(rollback_exc).__name__}"
                    )
            raise LegacyRouteCleanupError(
                f"legacy_cleanup_failed:{type(exc).__name__}:"
                f"rollback_errors={','.join(rollback_errors) or 'none'}"
            ) from exc

    current = {
        stable_id: _get_function(session, base_url, stable_id)
        for stable_id in all_ids
    }
    legacy_checks = {
        stable_id: evaluate_function_state(
            current[stable_id],
            stable_id=stable_id,
            expected_type=expected_types[stable_id],
            expected_active=False,
            expected_global=(
                False
                if stable_id != "broker_reports_gate1_normalizer_action"
                else True
            ),
        )
        for stable_id in LEGACY_FUNCTIONS_TO_DISABLE
    }
    required_checks = {
        stable_id: evaluate_function_state(
            current[stable_id],
            stable_id=stable_id,
            expected_type=expected_types[stable_id],
            expected_active=True,
            expected_global=False,
        )
        for stable_id in REQUIRED_ACTIVE_FUNCTIONS
    }
    utility_checks = {
        stable_id: {
            **evaluate_function_state(
                current[stable_id],
                stable_id=stable_id,
                expected_type=expected_types[stable_id],
                expected_active=True,
                expected_global=False,
            ),
            "classification": classification,
            "attached_to_ndfl": False,
        }
        for stable_id, classification in NON_COMPETING_UTILITY_FUNCTIONS.items()
    }
    ndfl_check = evaluate_ndfl_model(
        _get_model(session, base_url, NDFL_WORKSPACE_MODEL_STABLE_ID)
    )
    visible_check = evaluate_visible_routes(
        _get_visible_models(session, base_url)
    )
    passed = bool(
        all(check["passed"] for check in legacy_checks.values())
        and all(check["passed"] for check in required_checks.values())
        and all(check["passed"] for check in utility_checks.values())
        and ndfl_check["routing_passed"]
        and visible_check["passed"]
    )
    result = {
        "schema_version": "broker_reports_gate3_legacy_route_cleanup_live_v1",
        "mode": "apply" if args.apply else "read_only",
        "status": "passed" if passed else "not_clean",
        "actions": actions,
        "checks": {
            "legacy_functions_inactive": legacy_checks,
            "required_functions_active": required_checks,
            "non_competing_utilities": utility_checks,
            "ndfl_workspace_model": ndfl_check,
            "visible_routes": visible_check,
        },
        "deleted_records": 0,
        "knowledge_rag": "none",
        "provider_calls": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
