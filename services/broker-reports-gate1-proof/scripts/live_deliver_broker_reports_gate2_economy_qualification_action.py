#!/usr/bin/env python3
"""Deliver the qualification-only Gate 2 economy policy Action."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

from broker_reports_gate1.gate2_economy_qualification_policy import (  # noqa: E402
    Gate2EconomyQualificationPolicyFactory,
)
from live_no_rag_source_intake_smoke import (  # noqa: E402
    _base_url,
    _read_env,
    _signin,
    _url,
)


ACTION_ID = "broker_reports_gate2_economy_qualification_action"
ACTION_PATH = (
    SERVICE_ROOT
    / "openwebui_actions"
    / "broker_reports_gate2_economy_qualification_action.py"
)
MAINTAINED_FUNCTION_IDS = (
    "broker_reports_gate1_pipe",
    "broker_reports_gate2_source_fact_pipe",
    "broker_reports_gate2_domain_source_fact_pipe",
)
ALLOWED_EXACT_MODEL_IDS = (
    "models/gemini-3.1-flash-lite",
    "models/gemini-3.5-flash-lite",
    "gpt-5.4-nano-2026-03-17",
    "claude-haiku-4-5-20251001",
)
SAFE_META_KEYS = (
    "description",
    "qualification_scope",
    "qualification_policy_hash",
    "model_policy_hash",
    "workload_policy_hash",
    "source_revision",
)


class QualificationActionDeliveryError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--prove-rollback", action="store_true")
    args = parser.parse_args()
    if args.prove_rollback and not args.apply:
        raise QualificationActionDeliveryError(
            "qualification_action_rollback_requires_apply"
        )

    env = _read_env(Path(args.env_file))
    base_url = args.base_url.rstrip("/") if args.base_url else _base_url(env)
    session = requests.Session()
    session.headers.update({"Accept": "application/json"})
    token = _signin(session, base_url, env)
    session.headers.update({"Authorization": f"Bearer {token}"})

    source_revision = _source_revision()
    policy_snapshot = Gate2EconomyQualificationPolicyFactory().create().snapshot()
    source = ACTION_PATH.read_text(encoding="utf-8")
    source_sha256 = _sha256_text(source)
    payload = _candidate_payload(
        source=source,
        source_revision=source_revision,
        policy_snapshot=policy_snapshot,
    )
    before_action = _get_function(session, base_url, ACTION_ID)
    before_surrounding = _surrounding_state(session, base_url)
    before_models = _published_model_ids(session, base_url)
    _assert_target_models_published(before_models)
    _assert_production_admissions_empty(policy_snapshot)

    plan = {
        "action_id": ACTION_ID,
        "operation": ("create" if before_action is None else "update"),
        "before": (None if before_action is None else _function_state(before_action)),
        "candidate_content_sha256": source_sha256,
        "source_revision": source_revision,
        "qualification_policy_hash": policy_snapshot["qualification_policy_hash"],
    }
    if not args.apply:
        print(
            json.dumps(
                {
                    "status": "validated",
                    "applied": False,
                    "schema_version": (
                        "broker_reports_gate2_economy_qualification_action_delivery_v1"
                    ),
                    "plan": plan,
                    "checks": {
                        "target_models_published": True,
                        "production_admissions_empty": True,
                        "maintained_functions_read": True,
                    },
                    "provider_calls": 0,
                    "customer_calls": 0,
                    "stage_mutations": 0,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    mutation_counter = [0]
    candidate = _write_candidate(
        session=session,
        base_url=base_url,
        payload=payload,
        expected_source_sha256=source_sha256,
        expected_policy_hash=str(policy_snapshot["qualification_policy_hash"]),
        mutation_counter=mutation_counter,
    )
    rollback = {
        "requested": bool(args.prove_rollback),
        "previous_state_restored": False,
        "candidate_state_restored": False,
        "previous_state_identity_sha256": (
            _sha256_json(
                {"state": "absent"}
                if before_action is None
                else _function_state(before_action)
            )
        ),
    }
    if args.prove_rollback:
        if before_action is None:
            _delete_function(
                session,
                base_url,
                mutation_counter=mutation_counter,
            )
            if _get_function(session, base_url, ACTION_ID) is not None:
                raise QualificationActionDeliveryError(
                    "qualification_action_absent_rollback_failed"
                )
        else:
            restored = _restore_function(
                session=session,
                base_url=base_url,
                previous=before_action,
                mutation_counter=mutation_counter,
            )
            if _function_state(restored) != _function_state(before_action):
                raise QualificationActionDeliveryError(
                    "qualification_action_existing_rollback_failed"
                )
        rollback["previous_state_restored"] = True
        candidate = _write_candidate(
            session=session,
            base_url=base_url,
            payload=payload,
            expected_source_sha256=source_sha256,
            expected_policy_hash=str(policy_snapshot["qualification_policy_hash"]),
            mutation_counter=mutation_counter,
        )
        rollback["candidate_state_restored"] = True

    after_surrounding = _surrounding_state(session, base_url)
    after_models = _published_model_ids(session, base_url)
    if before_surrounding != after_surrounding:
        raise QualificationActionDeliveryError(
            "qualification_action_surrounding_function_delta"
        )
    if before_models != after_models:
        raise QualificationActionDeliveryError(
            "qualification_action_published_model_inventory_delta"
        )
    _assert_candidate(
        candidate,
        expected_source_sha256=source_sha256,
        expected_policy_hash=str(policy_snapshot["qualification_policy_hash"]),
    )
    receipt = {
        "status": "passed",
        "applied": True,
        "schema_version": (
            "broker_reports_gate2_economy_qualification_action_delivery_v1"
        ),
        "plan": plan,
        "action": _function_state(candidate),
        "policy": policy_snapshot,
        "rollback": rollback,
        "checks": {
            "repository_live_action_hash_exact": True,
            "qualification_policy_live_exact": True,
            "production_model_admission_empty": True,
            "target_models_published": True,
            "maintained_functions_unchanged": True,
            "gate1_visual_behavior_delta_zero": True,
            "published_model_inventory_unchanged": True,
            "active": True,
            "not_global": True,
        },
        "maintained_function_state_sha256": _sha256_json(before_surrounding),
        "published_models_total": len(after_models),
        "provider_calls": 0,
        "customer_calls": 0,
        "fallback_calls": 0,
        "repair_attempts": 0,
        "stage_mutations": mutation_counter[0],
    }
    print(
        json.dumps(
            receipt,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _candidate_payload(
    *,
    source: str,
    source_revision: str,
    policy_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "id": ACTION_ID,
        "name": "Broker Reports Gate 2 Economy Qualification Policy",
        "content": source,
        "meta": {
            "description": (
                "Read-only policy boundary for bounded Gate 2 economy "
                "model qualification."
            ),
            "qualification_scope": "qualification_only",
            "qualification_policy_hash": policy_snapshot["qualification_policy_hash"],
            "model_policy_hash": policy_snapshot["model_policy"]["policy_hash"],
            "workload_policy_hash": policy_snapshot["workload_policy"]["policy_hash"],
            "source_revision": source_revision,
        },
    }


def _write_candidate(
    *,
    session: requests.Session,
    base_url: str,
    payload: Mapping[str, Any],
    expected_source_sha256: str,
    expected_policy_hash: str,
    mutation_counter: list[int],
) -> dict[str, Any]:
    existing = _get_function(session, base_url, ACTION_ID)
    endpoint = (
        "/api/v1/functions/create"
        if existing is None
        else f"/api/v1/functions/id/{ACTION_ID}/update"
    )
    response = session.post(
        _url(base_url, endpoint),
        json=dict(payload),
        timeout=60,
    )
    response.raise_for_status()
    mutation_counter[0] += 1
    live = _require_function(session, base_url, ACTION_ID)
    live = _set_boolean_state(
        session=session,
        base_url=base_url,
        function=live,
        key="is_active",
        expected=True,
        endpoint=f"/api/v1/functions/id/{ACTION_ID}/toggle",
        mutation_counter=mutation_counter,
    )
    live = _set_boolean_state(
        session=session,
        base_url=base_url,
        function=live,
        key="is_global",
        expected=False,
        endpoint=f"/api/v1/functions/id/{ACTION_ID}/toggle/global",
        mutation_counter=mutation_counter,
    )
    _assert_candidate(
        live,
        expected_source_sha256=expected_source_sha256,
        expected_policy_hash=expected_policy_hash,
    )
    return live


def _restore_function(
    *,
    session: requests.Session,
    base_url: str,
    previous: Mapping[str, Any],
    mutation_counter: list[int],
) -> dict[str, Any]:
    payload = {
        "id": ACTION_ID,
        "name": str(previous.get("name") or ""),
        "content": str(previous.get("content") or ""),
        "meta": (
            dict(previous["meta"]) if isinstance(previous.get("meta"), dict) else {}
        ),
    }
    response = session.post(
        _url(base_url, f"/api/v1/functions/id/{ACTION_ID}/update"),
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    mutation_counter[0] += 1
    restored = _require_function(session, base_url, ACTION_ID)
    restored = _set_boolean_state(
        session=session,
        base_url=base_url,
        function=restored,
        key="is_active",
        expected=bool(previous.get("is_active")),
        endpoint=f"/api/v1/functions/id/{ACTION_ID}/toggle",
        mutation_counter=mutation_counter,
    )
    return _set_boolean_state(
        session=session,
        base_url=base_url,
        function=restored,
        key="is_global",
        expected=bool(previous.get("is_global")),
        endpoint=f"/api/v1/functions/id/{ACTION_ID}/toggle/global",
        mutation_counter=mutation_counter,
    )


def _delete_function(
    session: requests.Session,
    base_url: str,
    *,
    mutation_counter: list[int],
) -> None:
    response = session.delete(
        _url(base_url, f"/api/v1/functions/id/{ACTION_ID}/delete"),
        timeout=60,
    )
    response.raise_for_status()
    mutation_counter[0] += 1


def _set_boolean_state(
    *,
    session: requests.Session,
    base_url: str,
    function: dict[str, Any],
    key: str,
    expected: bool,
    endpoint: str,
    mutation_counter: list[int],
) -> dict[str, Any]:
    if bool(function.get(key)) == expected:
        return function
    response = session.post(_url(base_url, endpoint), timeout=30)
    response.raise_for_status()
    mutation_counter[0] += 1
    updated = _require_function(session, base_url, ACTION_ID)
    if bool(updated.get(key)) != expected:
        raise QualificationActionDeliveryError(
            "qualification_action_state_toggle_failed:" + key
        )
    return updated


def _assert_candidate(
    function: Mapping[str, Any],
    *,
    expected_source_sha256: str,
    expected_policy_hash: str,
) -> None:
    meta = function.get("meta") if isinstance(function.get("meta"), dict) else {}
    checks = {
        "id": function.get("id") == ACTION_ID,
        "type": function.get("type") == "action",
        "content": (
            _sha256_text(str(function.get("content") or "")) == expected_source_sha256
        ),
        "active": function.get("is_active") is True,
        "not_global": function.get("is_global") is False,
        "scope": meta.get("qualification_scope") == "qualification_only",
        "policy_hash": meta.get("qualification_policy_hash") == expected_policy_hash,
    }
    if not all(checks.values()):
        raise QualificationActionDeliveryError(
            "qualification_action_readback_failed:"
            + json.dumps(
                checks,
                sort_keys=True,
            )
        )


def _assert_target_models_published(model_ids: set[str]) -> None:
    missing = sorted(set(ALLOWED_EXACT_MODEL_IDS) - model_ids)
    if missing:
        raise QualificationActionDeliveryError(
            "qualification_action_target_models_missing:" + ",".join(missing)
        )


def _assert_production_admissions_empty(
    policy_snapshot: Mapping[str, Any],
) -> None:
    routes = policy_snapshot.get("workload_routes")
    if not isinstance(routes, dict) or any(
        not isinstance(route, dict) or route.get("production_admissions") != []
        for route in routes.values()
    ):
        raise QualificationActionDeliveryError(
            "qualification_action_production_admissions_not_empty"
        )


def _surrounding_state(
    session: requests.Session,
    base_url: str,
) -> dict[str, dict[str, Any]]:
    result = {}
    for function_id in MAINTAINED_FUNCTION_IDS:
        function = _get_function(session, base_url, function_id)
        if function is None:
            raise QualificationActionDeliveryError(
                "qualification_action_maintained_function_missing:" + function_id
            )
        function["valves"] = _function_valves(
            session,
            base_url,
            function_id,
        )
        result[function_id] = _function_state(function)
    return result


def _function_state(function: Mapping[str, Any]) -> dict[str, Any]:
    meta = function.get("meta") if isinstance(function.get("meta"), dict) else {}
    valves = function.get("valves") if isinstance(function.get("valves"), dict) else {}
    return {
        "id": str(function.get("id") or ""),
        "name": str(function.get("name") or ""),
        "type": str(function.get("type") or ""),
        "is_active": function.get("is_active") is True,
        "is_global": function.get("is_global") is True,
        "content_sha256": _sha256_text(str(function.get("content") or "")),
        "meta_sha256": _sha256_json(meta),
        "valves_sha256": _sha256_json(valves),
        "safe_meta": {key: meta.get(key) for key in SAFE_META_KEYS if key in meta},
    }


def _get_function(
    session: requests.Session,
    base_url: str,
    function_id: str,
) -> dict[str, Any] | None:
    response = session.get(
        _url(base_url, f"/api/v1/functions/id/{function_id}"),
        timeout=30,
    )
    if response.status_code == 401:
        probe = session.get(
            _url(base_url, "/api/v1/functions/"),
            timeout=30,
        )
        probe.raise_for_status()
        return None
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise QualificationActionDeliveryError(
            "qualification_action_function_response_invalid"
        )
    return value


def _require_function(
    session: requests.Session,
    base_url: str,
    function_id: str,
) -> dict[str, Any]:
    value = _get_function(session, base_url, function_id)
    if value is None:
        raise QualificationActionDeliveryError(
            "qualification_action_missing_after_write"
        )
    return value


def _function_valves(
    session: requests.Session,
    base_url: str,
    function_id: str,
) -> dict[str, Any]:
    response = session.get(
        _url(
            base_url,
            f"/api/v1/functions/id/{function_id}/valves",
        ),
        timeout=30,
    )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise QualificationActionDeliveryError(
            "qualification_action_function_valves_response_invalid"
        )
    return value


def _published_model_ids(
    session: requests.Session,
    base_url: str,
) -> set[str]:
    response = session.get(
        _url(base_url, "/api/models"),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise QualificationActionDeliveryError(
            "qualification_action_models_response_invalid"
        )
    return {
        str(item["id"]) for item in items if isinstance(item, dict) and item.get("id")
    }


def _source_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
    )
    revision = completed.stdout.strip()
    if len(revision) != 40 or any(
        character not in "0123456789abcdef" for character in revision
    ):
        raise QualificationActionDeliveryError(
            "qualification_action_source_revision_invalid"
        )
    return revision


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: Mapping[str, Any]) -> str:
    return _sha256_text(
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "code": str(exc)[:200],
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        raise
