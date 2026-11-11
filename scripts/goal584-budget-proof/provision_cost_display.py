#!/usr/bin/env python3
"""Provision only the disposable cost-display fixture through native APIs.

Run beside provision_webui.py in the pinned proxy, with feature source mounted
at /proof/budgets. Fixed internal targets and existing native clients are reused.
No inference requests are issued. Keys stay in the existing 0600 private state;
receipts contain only explicit safe readback fields, never source or Valves.

Stock WebUI6a18585: Functions create/toggle/Valves routers207/293/527,
UserValves579/600/628; Tools create/read385/474; ModelForm242..253.
LiteLLMd665dc1a: session spend4505..4617; viewer role scope4552/4835.
"""

from __future__ import annotations

import argparse
import ast
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request
import uuid

from provision_webui import (
    MODELS, OPERATOR_STATE, WEBUI_URL, WebUI, amount, close_amount, native_client,
    read_private, require, snapshot as base_snapshot, write_private, ProofError,
)
from provenance import ProtocolError, validate_persisted_scope
from prove_native_budgets import expected_budget_message


STATE = Path("/proof-private/webui-state.private.json")
FILTER_ID = "employee_budget_cost"
ACTION_ID = "employee_budget_cost_details"
ACTION_LABEL = "Стоимость: детали"
TOOL_ID = "goal584_budget_echo"
FILTER_SOURCE = Path("/proof/budgets/cost_filter.py")
ACTION_SOURCE = Path("/proof/budgets/cost_action.py")
LEDGER_URL = "http://proxy:4000"
READ_ROUTES = ["/spend/logs/session/ui"]
MODEL_FIELDS = ("id", "base_model_id", "name", "meta", "params", "access_grants", "is_active")
TOOL_SOURCE = '''"""
title: GOAL584 synthetic budget echo
description: Disposable local tool; no network, files or model calls.
version: 0.1.0
"""

class Tools:
    async def budget_echo(self) -> str:
        """Return the deterministic synthetic tool result."""
        return "proof-tool-result"
'''


def assert_private_text_absent(value) -> None:
    """Check actual native rows against this fixture's complete known text set."""
    if isinstance(value, dict):
        for child in value.values():
            assert_private_text_absent(child)
    elif isinstance(value, list):
        for child in value:
            assert_private_text_absent(child)
    elif isinstance(value, str):
        require(value not in {"Hi", "Proof", "proof-tool-result"}, "Native spend row retained fixture chat text")
        require(re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", value) is None,
                "Native spend row retained a provenance/session token")
        if len(value) < 128 * 1024 and value.startswith(("{", "[")):
            try:
                nested = json.loads(value)
            except ValueError:
                return
            assert_private_text_absent(nested)


def source_hash(content: str) -> str:
    return hashlib.sha256(content.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def grant_set(record: dict) -> set[tuple]:
    grants = record.get("access_grants")
    require(isinstance(grants, list), "Native access grants are missing")
    return {(g.get("principal_type"), g.get("principal_id"), g.get("permission")) for g in grants}


def model_body(record: dict) -> dict:
    require(all(field in record for field in MODEL_FIELDS), "Native editable model fields are missing")
    return {field: copy.deepcopy(record[field]) for field in MODEL_FIELDS}


def add_model_meta(webui: WebUI, state: dict, model: str, field: str, value: str) -> dict:
    admin = state["admin"]["token"]
    before = webui.model(admin, model)
    body = model_body(before)
    existing = body["meta"].get(field) or []
    require(isinstance(existing, list) and all(isinstance(item, str) for item in existing),
            "Native model extension IDs are malformed")
    body["meta"][field] = existing if value in existing else [*existing, value]
    webui.ok("POST", "/api/v1/models/model/update", token=admin, body=body)
    after = webui.model(admin, model)
    require(all(after.get(key) == body[key] for key in MODEL_FIELDS if key != "access_grants")
            and grant_set(after) == grant_set(before),
            "Native model update changed fields beyond the requested extension ID")
    return after


def denied_admin_get(webui: WebUI, token: str, path: str) -> int:
    """Use the existing bounded/no-redirect opener; inspect status, never body."""
    request = Request(WEBUI_URL + path, method="GET", headers={"Authorization": "Bearer " + token})
    try:
        response = webui.opener.open(request, timeout=20)
    except HTTPError as error:
        response = error
    except (URLError, TimeoutError, OSError):
        raise ProofError("Ordinary-user admin access probe transport failed") from None
    with response:
        status = response.code
    require(status in (401, 403), "Ordinary employee was not denied the admin-only Function API")
    return status


def reader_readback(native, state: dict) -> dict:
    reader = state.get("cost_reader") or {}
    require(isinstance(reader.get("key"), str) and reader["key"].startswith("sk-"),
            "Private cost reader credential is missing")
    user = native.user_info(reader["user_id"])
    info = native.ok("GET", "/key/info", query={"key": reader["key"]}).get("info")
    require(user.get("user_id") == reader["user_id"] and user.get("user_role") == "proxy_admin_viewer"
            and isinstance(info, dict) and info.get("user_id") == reader["user_id"]
            and info.get("key_alias") == reader["key_alias"] and info.get("models") == []
            and info.get("allowed_routes") == READ_ROUTES and info.get("team_id") is None,
            "Native cost-reader identity or restricted route readback differs")
    return {"user_id": reader["user_id"], "native_role": user["user_role"],
            "allowed_routes": list(READ_ROUTES), "models": [], "team_id": None}


def display_readback(webui: WebUI, state: dict) -> dict:
    admin = state["admin"]["token"]
    function_path = "/api/v1/functions/id/" + FILTER_ID
    function = webui.ok("GET", function_path, token=admin)
    require(function.get("id") == FILTER_ID and function.get("type") == "filter"
            and function.get("is_active") is True and function.get("is_global") is True
            and function.get("meta", {}).get("toggle") is False,
            "Native cost Function is not active, global and non-toggleable")
    content = function.get("content")
    require(isinstance(content, str) and source_hash(content) == state["cost_display"]["source_sha256"],
            "Native Function content differs from mounted cost source")
    action = webui.ok("GET", "/api/v1/functions/id/" + ACTION_ID, token=admin)
    require(action.get("id") == ACTION_ID and action.get("type") == "action"
            and action.get("is_active") is True and action.get("is_global") is False
            and action.get("name") == ACTION_LABEL
            and source_hash(action.get("content", "")) == state["cost_display"]["action_source_sha256"],
            "Native cost details Action differs from the installed source or scope")
    valves = webui.ok("GET", function_path + "/valves", token=admin)
    require(valves.get("ledger_base_url") == LEDGER_URL
            and valves.get("ledger_read_key") == state["cost_reader"]["key"]
            and valves.get("read_wait_seconds") == 8.0,
            "Native admin Function Valves did not retain the reader configuration")
    preferences, access = [], []
    for user in state["users"]:
        webui.session(user, "user")
        spec = webui.ok("GET", function_path + "/valves/user/spec", token=user["token"])
        enabled = (spec.get("properties") or {}).get("enabled") or {}
        require(enabled.get("type") == "boolean" and enabled.get("default") is True,
                "Native cost UserValves does not default to enabled")
        stored = webui.ok("GET", function_path + "/valves/user", token=user["token"])
        require(set(stored) <= {"enabled"} and ("enabled" not in stored or type(stored["enabled"]) is bool),
                "Native cost UserValves contains an unexpected override")
        preferences.append({"user_id": user["id"], "default_enabled": True,
                            "stored_overrides": stored, "effective_enabled": stored.get("enabled", True)})
        access.append({"user_id": user["id"],
                       "admin_valves_status": denied_admin_get(webui, user["token"], function_path + "/valves"),
                       "admin_export_status": denied_admin_get(
                           webui, user["token"], "/api/v1/functions/export?include_valves=true")})
        catalog = webui.ok("GET", "/api/models?refresh=true", token=user["token"])
        models = catalog.get("data")
        require(isinstance(models, list) and {m.get("id") for m in models} == set(MODELS),
                "Ordinary cost-display catalog differs from managed aliases")
        require(all(FILTER_ID in ((m.get("info") or {}).get("meta") or {}).get("filterIds", [])
                    for m in models), "Ordinary catalog omitted the mandatory cost Filter")
        require(all(any(a.get("id") == ACTION_ID and a.get("name") == ACTION_LABEL for a in m.get("actions", []))
                    for m in models), "Ordinary model catalog omitted the cost details Action")
    return {"filter_id": FILTER_ID, "source_sha256": source_hash(content), "active": True,
            "toggleable": False, "global": True, "attached_models": list(MODELS),
            "action_id": ACTION_ID, "action_source_sha256": source_hash(action["content"]),
            "reader_valves_readback": True, "user_valves": preferences, "employee_admin_denials": access}


def setup(webui: WebUI, state: dict, path: Path) -> None:
    require("cost_reader" not in state and "cost_display" not in state,
            "Cost setup requires a fresh disposable feature state")
    source = FILTER_SOURCE.read_text(encoding="utf-8")
    require(0 < len(source.encode("utf-8")) <= 128 * 1024, "Cost Filter source exceeded fixture bound")
    parsed_source = ast.parse(source)
    require(any(isinstance(node, ast.ClassDef) and node.name == "Filter" for node in parsed_source.body),
            "Mounted source does not contain a native Filter")
    native = native_client(state)
    native.schema()
    user_id = state["run_id"] + "-cost-reader"
    alias = user_id + "-session-only"
    native.ok("POST", "/user/new", body={
        "user_id": user_id, "user_role": "proxy_admin_viewer", "models": [],
        "auto_create_key": False, "send_invite_email": False,
    })
    generated = native.ok("POST", "/key/generate", body={
        "user_id": user_id, "key_alias": alias, "models": [], "allowed_routes": READ_ROUTES,
    })
    key = generated.get("key")
    require(isinstance(key, str) and key.startswith("sk-"), "Native cost-reader key was not returned")
    state["cost_reader"] = {"user_id": user_id, "key": key, "key_alias": alias,
                            "allowed_routes": list(READ_ROUTES)}
    state["cost_display"] = {"stage": "installing", "source_sha256": source_hash(source),
                             "action_source_sha256": source_hash(ACTION_SOURCE.read_text(encoding="utf-8")),
                             "scenario_complete": False}
    write_private(path, state)
    reader_readback(native, state)
    # The exact session endpoint is intentionally hidden from OpenAPI. Probe it
    # through the actual restricted viewer identity, with a fresh empty session.
    empty = native.ok("GET", READ_ROUTES[0], token=key,
                      query={"session_id": str(uuid.uuid4()), "page": 1, "page_size": 100})
    require(empty.get("data") == [] and empty.get("total") == 0 and empty.get("total_pages") == 0,
            "Native restricted reader session API did not return an empty exact session")
    admin = state["admin"]["token"]
    created = webui.ok("POST", "/api/v1/functions/create", token=admin, body={
        "id": FILTER_ID, "name": "Employee budget costs", "content": source, "meta": {},
    })
    require(created.get("id") == FILTER_ID and created.get("type") == "filter"
            and created.get("is_active") is False, "Native Function creation did not return an inactive Filter")
    function_path = "/api/v1/functions/id/" + FILTER_ID
    webui.ok("POST", function_path + "/valves/update", token=admin, body={
        "ledger_base_url": LEDGER_URL, "ledger_read_key": key, "read_wait_seconds": 8.0,
    })
    webui.ok("POST", function_path + "/toggle", token=admin)
    webui.ok("POST", function_path + "/toggle/global", token=admin)
    created_action = webui.ok("POST", "/api/v1/functions/create", token=admin, body={
        "id": ACTION_ID, "name": ACTION_LABEL, "content": ACTION_SOURCE.read_text(encoding="utf-8"), "meta": {},
    })
    require(created_action.get("id") == ACTION_ID and created_action.get("type") == "action"
            and created_action.get("is_active") is False, "Native cost details Action creation failed")
    webui.ok("POST", "/api/v1/functions/id/" + ACTION_ID + "/toggle", token=admin)
    for model in MODELS:
        add_model_meta(webui, state, model, "filterIds", FILTER_ID)
        add_model_meta(webui, state, model, "actionIds", ACTION_ID)
    for user in state["users"]:
        # Native GET returns null until there is a stored record. Store empty
        # overrides via the owner, leaving enabled=True solely the native default.
        saved = webui.ok("POST", function_path + "/valves/user/update", token=user["token"], body={})
        require(saved == {}, "Native empty UserValves initialization changed defaults")
    display_readback(webui, state)
    state["cost_display"]["stage"] = "setup_complete"
    write_private(path, state)


def monthly(webui: WebUI, state: dict) -> dict:
    """Enable the existing monthly owner on the same GUI fixture and Valves."""
    function_id = "employee_budget_monthly_view"
    admin = state["admin"]["token"]
    common = webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID + "/valves", token=admin)
    require(common.get("ledger_base_url") == LEDGER_URL and bool(common.get("ledger_admin_key")),
            "Monthly GUI requires the existing admin setup")
    source = (FILTER_SOURCE.parent / "monthly_view.py").read_text(encoding="utf-8")
    made = webui.ok("POST", "/api/v1/functions/create", token=admin, body={
        "id": function_id, "name": "Employee monthly budget", "content": source, "meta": {}})
    require(made.get("id") == function_id and made.get("type") == "event" and made.get("is_active") is False,
            "Monthly Event creation failed")
    stored = webui.ok("GET", "/api/v1/functions/id/" + function_id, token=admin)
    require(stored.get("content") == source, "Monthly Event source differs")
    enabled = webui.ok("POST", "/api/v1/functions/id/" + function_id + "/toggle", token=admin)
    require(enabled.get("is_active") is True, "Monthly Event did not activate")
    require(webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID + "/valves", token=admin) == common,
            "Monthly activation changed shared Valves")
    return {"function_id": function_id, "source_sha256": source_hash(source),
            "active": True, "shared_valves_preserved": True}


def scenario(webui: WebUI, state: dict, path: Path) -> dict:
    require(state.get("cost_display", {}).get("stage") == "setup_complete"
            and state["cost_display"].get("scenario_complete") is False,
            "Cost tool scenario requires completed setup and a fresh scenario")
    native = native_client(state)
    for user in state["users"]:
        native.ok("POST", "/user/update", body={"user_id": user["id"], "max_budget": 20.0})
        for model in MODELS:
            key = next(k["key"] for k in state["native_keys"] if k["user_id"] == user["id"] and k["model"] == model)
            native.ok("POST", "/key/update", body={"key": key, "max_budget": 10.0})

    def caps_changed():
        return True if all(close_amount(native.user_info(u["id"]).get("max_budget"), Decimal("20"))
                           and all(close_amount(native.key_info(u["id"], m).get("max_budget"), Decimal("10"))
                                   for m in MODELS) for u in state["users"]) else None
    native.poll("synthetic equal-share cost scenario cap readback", caps_changed)
    admin = state["admin"]["token"]
    grants = [{"principal_type": "user", "principal_id": user["id"], "permission": "read"}
              for user in state["users"]]
    webui.ok("POST", "/api/v1/tools/create", token=admin, body={
        "id": TOOL_ID, "name": "Budget proof echo", "content": TOOL_SOURCE,
        "meta": {"description": "Synthetic local echo for native tool-round qualification"}, "access_grants": grants,
    })
    tool = webui.ok("GET", "/api/v1/tools/id/" + TOOL_ID, token=admin)
    specs = tool.get("specs")
    require(tool.get("write_access") is True and tool.get("content") == TOOL_SOURCE
            and grant_set(tool) == {("user", user["id"], "read") for user in state["users"]}
            and isinstance(specs, list) and len(specs) == 1 and specs[0].get("name") == "budget_echo"
            and specs[0].get("parameters", {}).get("properties") == {},
            "Native echo Tool source, schema or read grants differ")
    before_b = model_body(webui.model(admin, MODELS[1]))
    model_a = add_model_meta(webui, state, MODELS[0], "toolIds", TOOL_ID)
    require(model_body(webui.model(admin, MODELS[1])) == before_b, "Tool attachment changed model B")
    for model in MODELS:
        record = webui.model(admin, model)
        require(record["meta"].get("capabilities", {}).get("builtin_tools") is False
                and FILTER_ID in record["meta"].get("filterIds", []),
                "Tool scenario changed native built-in capability or cost Filter")
    for user in state["users"]:
        visible = webui.ok("GET", "/api/v1/tools/id/" + TOOL_ID, token=user["token"])
        require(visible.get("id") == TOOL_ID and visible.get("write_access") is False
                and visible.get("content") is None, "Ordinary native Tool access is not read-only")
        catalog = webui.ok("GET", "/api/models?refresh=true", token=user["token"]).get("data")
        require(isinstance(catalog, list), "Ordinary tool scenario catalog is malformed")
        metadata = {m["id"]: (m.get("info") or {}).get("meta") or {} for m in catalog}
        require(TOOL_ID in metadata.get(MODELS[0], {}).get("toolIds", [])
                and TOOL_ID not in metadata.get(MODELS[1], {}).get("toolIds", []),
                "Ordinary catalog did not retain model-A-only echo Tool")
    state["cost_display"]["scenario_complete"] = True
    write_private(path, state)
    return {"tool_id": TOOL_ID, "tool_method": "budget_echo", "source_sha256": source_hash(TOOL_SOURCE),
            "attached_model": model_a["id"], "read_user_ids": [u["id"] for u in state["users"]],
            "personal_caps_usd": "20", "per_model_caps_usd": "10", "normalized_equal_shares": True,
            "builtin_tools": False, "model_b_preserved": True, "source_readonly_for_employees": True}


def persisted_scope(row: dict, user_id: str) -> dict:
    metadata = row.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except ValueError:
            raise ProofError("Native spend metadata is malformed") from None
    try:
        require(isinstance(metadata, dict), "Native spend metadata is missing")
        scope = validate_persisted_scope((metadata.get("spend_logs_metadata") or {}).get("owui_budget"))
    except (ProtocolError, AttributeError):
        raise ProofError("Native persisted cost attribution is malformed") from None
    require(row.get("user") == user_id and scope["user_id"] == user_id
            and row.get("session_id") == scope["root_chat_id"], "Native cost attribution crossed user/session scope")
    return scope


def off_pair(native, user_id: str, model: str) -> dict:
    """Narrow native readback, excluding credentials, hashes and activity fields."""
    user, key = native.user_info(user_id), native.key_info(user_id, model)
    require(user.get("user_id") == user_id and key.get("user_id") == user_id
            and key.get("models") == [model] and key.get("team_id") is None,
            "OFF fixture native identity differs")
    fields = ("user_id", "models", "budget_duration", "budget_reset_at", "spend", "max_budget")
    return {"user": {name: copy.deepcopy(user.get(name)) for name in (*fields, "user_role")},
            "key": {name: copy.deepcopy(key.get(name)) for name in
                    (*fields, "team_id", "key_alias", "metadata", "allowed_routes")}}


def off_unchanged(observed: dict, prior: dict, cap: Decimal) -> bool:
    for owner in ("user", "key"):
        for field, value in prior[owner].items():
            expected = cap if owner == "key" and field == "max_budget" else value
            if field in ("spend", "max_budget"):
                if not close_amount(observed[owner].get(field), amount(expected)):
                    return False
            elif observed[owner].get(field) != expected:
                return False
    return True


def off_summary(control: dict, observed: dict) -> dict:
    return {"status": control["status"], "user_id": control["user_id"], "model": control["model"],
            "key_alias": observed["key"]["key_alias"],
            "key_spend_usd": str(amount(observed["key"]["spend"])),
            "key_max_budget_usd": str(amount(observed["key"]["max_budget"])),
            "user_spend_usd": str(amount(observed["user"]["spend"])),
            "user_max_budget_usd": str(amount(observed["user"]["max_budget"])),
            "prior_key_max_budget_usd": str(amount(control["before"]["key"]["max_budget"]))}


def off_existing_chat_ids(webui: WebUI, token: str) -> list[str]:
    # Existing WebUI.ok intentionally accepts object responses only. This native
    # list route uses the same bounded/no-proxy/no-redirect opener, not a new client.
    request = Request(WEBUI_URL + "/api/v1/chats/?page=1&include_pinned=true&include_folders=true",
                      headers={"Authorization": "Bearer " + token})
    try:
        with webui.opener.open(request, timeout=20) as response:
            require(response.code == 200, "OFF fixture native chat list failed")
            raw = response.read(4 * 1024 * 1024 + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise ProofError("OFF fixture native chat list transport failed") from None
    require(len(raw) <= 4 * 1024 * 1024, "OFF fixture native chat list exceeded size bound")
    try:
        chats = json.loads(raw)
        ids = [chat["id"] for chat in chats]
        require(isinstance(chats, list) and len(chats) < 60
                and all(str(uuid.UUID(value)) == value for value in ids)
                and len(set(ids)) == len(ids), "OFF fixture existing-chat bound is incomplete")
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ProofError("OFF fixture native chat list is malformed") from None
    return ids


def off_limit(webui: WebUI, state: dict, path: Path) -> dict:
    require(state["cost_display"].get("scenario_complete") is True
            and "off_denial" not in state["cost_display"], "OFF limit requires a fresh tool scenario")
    user, model = state["users"][0], MODELS[1]
    preference = webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID + "/valves/user", token=user["token"])
    require(preference.get("enabled") is False, "OFF limit requires the actual native preference to be disabled")
    native = native_client(state)
    def settled_before():
        observed = off_pair(native, user["id"], model)
        return observed if (close_amount(observed["key"]["spend"], Decimal("0.80"))
                            and close_amount(observed["key"]["max_budget"], Decimal("10"))
                            and close_amount(observed["user"]["spend"], Decimal("1.80"))
                            and close_amount(observed["user"]["max_budget"], Decimal("20"))) else None
    before = native.poll("OFF observed native counters reached the completed-call boundary", settled_before)
    existing_ids = off_existing_chat_ids(webui, user["token"])
    prior_rows = native.logs(user["id"])
    prior_ids = [row.get("request_id") for row in prior_rows]
    require(all(isinstance(value, str) and value for value in prior_ids) and len(set(prior_ids)) == len(prior_ids),
            "OFF fixture native baseline row IDs are incomplete")
    control = {"status": "limit_pending", "user_id": user["id"], "model": model, "before": before,
               "existing_chat_ids": existing_ids, "prior_request_ids": prior_ids,
               "started_at_utc": datetime.now(timezone.utc).isoformat()}
    state["cost_display"]["off_denial"] = control
    write_private(path, state)
    key = next(entry["key"] for entry in state["native_keys"]
               if entry["user_id"] == user["id"] and entry["model"] == model)
    native.ok("POST", "/key/update", body={"key": key, "max_budget": float(amount(before["key"]["spend"]))})
    def changed():
        observed = off_pair(native, user["id"], model)
        return observed if off_unchanged(observed, before, amount(before["key"]["spend"])) else None
    observed = native.poll("OFF native exhausted key cap and unchanged identity/spend/reset", changed)
    control["status"] = "limited"
    write_private(path, state)
    return off_summary(control, observed)


def off_control(state: dict, expected_status: str) -> dict:
    control = state["cost_display"].get("off_denial")
    require(isinstance(control, dict) and control.get("status") == expected_status
            and control.get("user_id") == state["users"][0]["id"] and control.get("model") == MODELS[1],
            "OFF fixture stage or synthetic employee/model differs")
    return control


def off_row(row: dict, control: dict, chat_id: str, answer_id: str) -> dict:
    require(isinstance(row, dict) and row.get("user") == control["user_id"], "OFF native row crossed user scope")
    identifier = row.get("request_id")
    require(isinstance(identifier, str) and 0 < len(identifier) <= 512
            and all(ord(char) >= 32 for char in identifier), "OFF native row ID is malformed")
    metadata = row.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except ValueError:
            raise ProofError("OFF native row metadata is malformed") from None
    require(metadata is None or isinstance(metadata, dict), "OFF native row metadata is malformed")
    spend_metadata = (metadata or {}).get("spend_logs_metadata")
    require(spend_metadata is None or isinstance(spend_metadata, dict), "OFF native spend metadata is malformed")
    scope = (spend_metadata or {}).get("owui_budget")
    if scope is not None:
        try:
            scope = validate_persisted_scope(scope)
        except ProtocolError:
            raise ProofError("OFF native row attribution is malformed") from None
        require(scope["user_id"] == control["user_id"] and scope["model"] == control["model"]
                and scope["chat_id"] == scope["root_chat_id"] == chat_id
                and scope["answer_id"] == scope["root_answer_id"] == answer_id,
                "OFF native row attribution differs from its actual denied answer")
    spend = row.get("spend")
    if spend is not None:
        require(amount(spend) == 0, "OFF denied request unexpectedly accrued native spend")
    error = (metadata or {}).get("error_information")
    error = error if isinstance(error, dict) else {}
    code = error.get("error_code")
    safe_code = code if type(code) is int or isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,80}", code) else None
    usage = {}
    for name in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = row.get(name)
        require(value is None or type(value) is int and value >= 0, "OFF native usage is malformed")
        usage[name] = value
    status = row.get("status")
    session_id = row.get("session_id")
    require(session_id is None or isinstance(session_id, str) and len(session_id) <= 512,
            "OFF native row session is malformed")
    return {"request_id": identifier, "user_id": row["user"], "session_id": session_id,
            "status": status if status in ("success", "failure") else "unknown",
            "model_group": row.get("model_group") if row.get("model_group") in MODELS else None,
            "spend_usd": str(amount(spend)) if spend is not None else None, **usage,
            "owui_budget": scope, "scope_status": "observed" if scope is not None else "unknown",
            "native_error_code": safe_code}


def off_denial_observe(webui: WebUI, state: dict, path: Path, chat_id: str) -> dict:
    stage = state["cost_display"].get("off_denial", {}).get("status")
    control = off_control(state, "observed" if stage == "observed" else "limited")
    try:
        require(str(uuid.UUID(chat_id)) == chat_id, "OFF denial requires a canonical chat UUID")
    except (ValueError, TypeError, AttributeError):
        raise ProofError("OFF denial requires a canonical chat UUID") from None
    require(chat_id not in control["existing_chat_ids"], "OFF denial must use a fresh isolated chat")
    require(control.get("chat_id") in (None, chat_id), "OFF observation cannot switch denial chats")
    user = state["users"][0]
    preference = webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID + "/valves/user", token=user["token"])
    require(preference.get("enabled") is False, "OFF denial observation requires the disabled native preference")
    chat = webui.ok("GET", "/api/v1/chats/" + chat_id, token=user["token"])
    require(chat.get("user_id") == control["user_id"] and type(chat.get("created_at")) is int
            and chat["created_at"] >= int(datetime.fromisoformat(control["started_at_utc"]).timestamp()),
            "OFF denial chat is not fresh and owned by the synthetic employee")
    messages = (chat.get("chat") or {}).get("history", {}).get("messages", {})
    require(isinstance(messages, dict), "OFF denial chat history is malformed")
    assistants = [(key, value) for key, value in messages.items()
                  if isinstance(value, dict) and value.get("role") == "assistant"]
    require(len(assistants) == 1, "OFF denial chat must contain one fresh assistant answer")
    answer_id, answer = assistants[0]
    require(str(uuid.UUID(answer_id)) == answer_id and answer.get("model") == control["model"]
            and answer.get("done") is True and bool(answer.get("error")),
            "OFF native terminal answer is not a localized budget failure")
    expected_budget_message(answer["error"], scope="key")
    statuses = answer.get("statusHistory")
    require(statuses is None or isinstance(statuses, list) and all(isinstance(item, dict) for item in statuses),
            "OFF denial native status history is malformed")
    require(not any(item.get("action") == "employee_budget_cost" for item in statuses or []),
            "OFF denial unexpectedly persisted a cost display status")
    native = native_client(state)
    observed = off_pair(native, control["user_id"], control["model"])
    require(off_unchanged(observed, control["before"], amount(control["before"]["key"]["spend"])),
            "OFF denial changed native spend/reset/identity or capped key")
    rows, counts, page = [], None, 1
    while True:
        payload = native.ok("GET", READ_ROUTES[0], token=state["cost_reader"]["key"],
                            query={"session_id": chat_id, "page": page, "page_size": 100})
        total, pages, data = payload.get("total"), payload.get("total_pages"), payload.get("data")
        require(type(total) is int and 0 <= total <= 1000 and type(pages) is int
                and pages == (total + 99) // 100 and type(payload.get("page")) is int
                and payload["page"] == page and type(payload.get("page_size")) is int
                and payload["page_size"] == 100 and payload.get("total_is_capped", False) is False
                and isinstance(data, list) and len(data) == min(100, max(0, total-(page-1)*100)),
                "OFF native session pagination is incomplete")
        require(counts is None or counts == (total, pages), "OFF native session changed during pagination")
        counts = (total, pages)
        require(all(row.get("session_id") == chat_id for row in data if isinstance(row, dict)),
                "OFF native exact session query crossed scope")
        rows.extend(off_row(row, control, chat_id, answer_id) for row in data)
        if page >= pages:
            break
        page += 1
    require(len({row["request_id"] for row in rows}) == len(rows), "OFF native session repeated row IDs")
    delta = [row for row in native.logs(control["user_id"]) if row.get("request_id") not in control["prior_request_ids"]]
    new_rows = [off_row(row, control, chat_id, answer_id) for row in delta]
    require(len({row["request_id"] for row in new_rows}) == len(new_rows)
            and {row["request_id"] for row in rows} <= {row["request_id"] for row in new_rows},
            "OFF native denial row reconciliation is incomplete")
    control.update(status="observed", chat_id=chat_id, answer_id=answer_id)
    write_private(path, state)
    return {**off_summary(control, observed), "chat_id": chat_id, "answer_id": answer_id,
            "terminal_budget_failure": True, "cost_status_absent": True, "rows": rows,
            "new_user_rows": new_rows, "total_rows": len(rows),
            "rows_status": "observed" if rows else "no_rows_observed",
            "row_absence_is_not_zero_cost_proof": True}


def off_restore(state: dict, path: Path) -> dict:
    control = off_control(state, "observed")
    native = native_client(state)
    before, cap = control["before"], amount(control["before"]["key"]["max_budget"])
    require(off_unchanged(off_pair(native, control["user_id"], control["model"]), before,
                          amount(before["key"]["spend"])), "OFF restore detected native state drift")
    key = next(entry["key"] for entry in state["native_keys"]
               if entry["user_id"] == control["user_id"] and entry["model"] == control["model"])
    native.ok("POST", "/key/update", body={"key": key, "max_budget": float(cap)})
    def restored():
        observed = off_pair(native, control["user_id"], control["model"])
        return observed if off_unchanged(observed, before, cap) else None
    observed = native.poll("OFF original native key cap restored without identity/spend/reset changes", restored)
    control["status"] = "restored"
    write_private(path, state)
    return off_summary(control, observed)


def snapshot(webui: WebUI, state: dict) -> dict:
    result = base_snapshot(webui, state)
    native = native_client(state)
    reader = reader_readback(native, state)
    expected: dict[tuple[str, str], set[str]] = {}
    attributed = []
    for user in state["users"]:
        for row in native.logs(user["id"]):
            if amount(row.get("spend", 0)) == 0:
                continue
            assert_private_text_absent(row)
            scope = persisted_scope(row, user["id"])
            require(row.get("status") == "success", "Positive cost row is not a qualified success")
            expected.setdefault((user["id"], scope["root_chat_id"]), set()).add(row["request_id"])
            attributed.append({"request_id": row["request_id"], "user_id": user["id"],
                               "session_id": row["session_id"], "owui_budget": scope,
                               "spend_usd": str(amount(row["spend"])), "prompt_tokens": row["prompt_tokens"],
                               "completion_tokens": row["completion_tokens"], "total_tokens": row["total_tokens"]})
    sessions = []
    for (user_id, session_id), expected_ids in sorted(expected.items()):
        positive_ids, all_ids = set(), set()
        counts = None
        page = 1
        while True:
            payload = native.ok("GET", READ_ROUTES[0], token=state["cost_reader"]["key"],
                                query={"session_id": session_id, "page": page, "page_size": 100})
            total, pages = payload.get("total"), payload.get("total_pages")
            require(type(total) is int and 0 <= total <= 1000 and type(pages) is int
                    and pages == (total + 99) // 100 and type(payload.get("page")) is int
                    and payload["page"] == page and type(payload.get("page_size")) is int
                    and payload["page_size"] == 100 and payload.get("total_is_capped", False) is False,
                    "Native viewer session pagination is incomplete")
            require(counts is None or counts == (total, pages), "Native viewer session changed during pagination")
            counts = (total, pages)
            rows = payload.get("data")
            require(isinstance(rows, list) and len(rows) == min(100, max(0, total-(page-1)*100)),
                    "Native viewer session row count differs")
            for row in rows:
                require(isinstance(row, dict), "Native viewer session contains a malformed row")
                persisted_scope(row, user_id)
                request_id = row.get("request_id")
                require(isinstance(request_id, str) and request_id not in all_ids,
                        "Native viewer session request ID is missing or duplicated")
                all_ids.add(request_id)
                if amount(row.get("spend", 0)) > 0:
                    positive_ids.add(request_id)
            if page >= pages:
                break
            page += 1
        require(len(all_ids) == counts[0] and positive_ids == expected_ids,
                "Restricted viewer cannot read the exact native employee session rows")
        sessions.append({"user_id": user_id, "session_id": session_id,
                         "total_rows": len(all_ids), "positive_request_ids": sorted(positive_ids)})
    result.update(cost_reader=reader, cost_display=display_readback(webui, state),
                  attributed_spend_logs=attributed, viewer_sessions=sessions)
    return result


def secret_values(state: dict) -> list[str]:
    values = []
    for account in [state.get("admin", {}), state.get("role_probe_control", {}), *state.get("users", [])]:
        values.extend(account.get(key) for key in ("password", "token"))
    values.extend(entry.get("key") for entry in state.get("native_keys", []))
    values.append((state.get("cost_reader") or {}).get("key"))
    return [value for value in values if isinstance(value, str) and value]


def known_zero_observation(state, *, chat_id=None, answer_id=None, request_id=None, call_id=None):
    """Read this finite UI case through the existing native ledger/reader owners."""
    import asyncio
    from aiohttp import ClientSession
    from employee_budget_cost_readback import read_cost_snapshot
    from prove_pricing_snapshots import project_row

    native = native_client(state)
    financial = {user["id"]: {model: off_pair(native, user["id"], model) for model in MODELS}
                 for user in state["users"]}
    rows = [row for user in state["users"] for row in native.logs(user["id"])]
    fingerprints = {}
    for row in rows:
        identifier = row.get("request_id")
        require(isinstance(identifier, str) and identifier and identifier not in fingerprints,
                "Known0 native row identity is missing or duplicated")
        fingerprints[identifier] = hashlib.sha256(json.dumps(row, sort_keys=True, allow_nan=False,
            default=str).encode("utf-8")).hexdigest()
    result = {"financial": financial, "row_sha256": fingerprints}
    if chat_id is None:
        require(answer_id is None and request_id is None and call_id is None, "Known0 incomplete target")
        return result
    require(all(isinstance(value, str) and value for value in (answer_id, request_id, call_id)),
            "Known0 incomplete target")
    actor = state["users"][0]["id"]
    async def read():
        async with ClientSession() as session:
            return await read_cost_snapshot(session, base_url=LEDGER_URL,
                read_key=state["cost_reader"]["key"], user_id=actor,
                root_chat_id=chat_id, root_answer_id=answer_id,
                observed_request_ids=[request_id], observed_call_ids=[call_id], wait_seconds=8)
    observed = asyncio.run(read())
    require(not observed.pending and not observed.missing_request_ids and not observed.missing_call_ids
            and observed.answer.spend == observed.chat.spend == 0
            and observed.answer.calls == observed.chat.calls == 1
            and observed.answer.prompt_tokens == observed.answer.completion_tokens == observed.answer.total_tokens == 0,
            "Known0 existing native reader did not confirm the exact zero row")
    # Read again after the reader's bounded wait; writer settlement may have
    # completed during that wait. No independent pricing/zero classifier.
    rows = [row for user in state["users"] for row in native.logs(user["id"])]
    matches = [row for row in rows if row.get("request_id") == request_id]
    require(len(matches) == 1, "Known0 target native row is missing or duplicated")
    row = matches[0]
    scope = persisted_scope(row, actor)
    require(scope["root_chat_id"] == scope["chat_id"] == chat_id
            and scope["root_answer_id"] == scope["answer_id"] == answer_id
            and scope["call_id"] == call_id and scope["model"] == MODELS[1], "Known0 native scope differs")
    projection = project_row(row, {actor})
    projection.pop("api_key_hash")
    result["row_sha256"] = {row["request_id"]: hashlib.sha256(json.dumps(row, sort_keys=True,
        allow_nan=False, default=str).encode("utf-8")).hexdigest() for row in rows}
    require(len(result["row_sha256"]) == len(rows) and all(isinstance(value, str) and value
            for value in result["row_sha256"]), "Known0 native row identity changed during readback")
    result["target"] = {"scope": scope, "row": projection,
                        "as_of": observed.as_of.isoformat(), "reader_confirmed_zero": True}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("setup", "monthly", "scenario", "snapshot", "off-limit", "off-denial-observe", "off-restore", "known-zero"))
    parser.add_argument("--chat-id", help="Actual browser-observed fresh denial chat UUID; observation phase only")
    parser.add_argument("--answer-id")
    parser.add_argument("--request-id")
    parser.add_argument("--call-id")
    parser.add_argument("--private-state", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()
    receipt = {"schema": 1, "proof": "goal584-native-cost-provisioning", "phase": args.phase,
               "passed": False, "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "not_qualified": ["inference_in_this_script", "production", "paid_provider", "management_GUI"]}
    state, receipt_path_valid = {}, False
    try:
        require(args.private_state.resolve() == STATE.resolve(), "Cost provisioning requires the fixed private WebUI state")
        require(len({args.private_state.resolve(), args.receipt.resolve(), OPERATOR_STATE.resolve()}) == 3,
                "Private state, operator state and safe receipt must be separate")
        receipt_path_valid = True
        require(args.phase == "known-zero" or (args.phase == "off-denial-observe") == (args.chat_id is not None),
                "A denial chat UUID is required only for off-denial-observe")
        require(args.phase == "known-zero" or all(value is None for value in
                (args.answer_id, args.request_id, args.call_id)), "Known0 target is not supported for this phase")
        state = read_private(args.private_state)
        require(state.get("stage") == "setup_complete" and len(state.get("users", [])) == 2
                and len(state.get("native_keys", [])) == 4, "Base native WebUI setup is incomplete")
        webui = WebUI()
        require(webui.ok("GET", "/api/version").get("version") == "0.12.2", "WebUI version differs from fixture")
        webui.session(state["admin"], "admin")
        if args.phase == "setup":
            setup(webui, state, args.private_state)
        else:
            require(state.get("cost_display", {}).get("stage") == "setup_complete", "Cost setup is incomplete")
        if args.phase == "monthly":
            receipt["monthly_event"] = monthly(webui, state)
        elif args.phase == "scenario":
            receipt["tool_scenario"] = scenario(webui, state, args.private_state)
        elif args.phase == "off-limit":
            receipt["off_denial"] = off_limit(webui, state, args.private_state)
        elif args.phase == "off-denial-observe":
            receipt["off_denial"] = off_denial_observe(webui, state, args.private_state, args.chat_id)
        elif args.phase == "off-restore":
            receipt["off_denial"] = off_restore(state, args.private_state)
        if args.phase == "known-zero":
            receipt["known_zero"] = known_zero_observation(state, chat_id=args.chat_id,
                answer_id=args.answer_id, request_id=args.request_id, call_id=args.call_id)
        else:
            receipt.update(snapshot(webui, state))
        receipt["passed"] = True
    except ProofError as error:
        receipt["failure"] = str(error)
    except Exception as error:
        receipt["failure"] = "Unexpected cost fixture error: " + type(error).__name__
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    rendered = json.dumps(receipt, indent=2, allow_nan=False)
    if any(value in rendered for value in secret_values(state)):
        receipt = {"schema": 1, "proof": "goal584-native-cost-provisioning", "phase": args.phase,
                   "passed": False, "failure": "Unsafe credential-bearing receipt suppressed"}
        rendered = json.dumps(receipt, indent=2)
    if receipt_path_valid:
        write_private(args.receipt, receipt)
    print(rendered)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
