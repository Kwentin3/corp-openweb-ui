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


STATE = Path("/proof-private/webui-state.private.json")
FILTER_ID = "employee_budget_cost"
TOOL_ID = "goal584_budget_echo"
FILTER_SOURCE = Path("/proof/budgets/cost_filter.py")
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
            and function.get("is_active") is True and function.get("is_global") is False
            and function.get("meta", {}).get("toggle") is False,
            "Native cost Function is not active, model-scoped and non-toggleable")
    content = function.get("content")
    require(isinstance(content, str) and source_hash(content) == state["cost_display"]["source_sha256"],
            "Native Function content differs from mounted cost source")
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
    return {"filter_id": FILTER_ID, "source_sha256": source_hash(content), "active": True,
            "toggleable": False, "global": False, "attached_models": list(MODELS),
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
    for model in MODELS:
        add_model_meta(webui, state, model, "filterIds", FILTER_ID)
    for user in state["users"]:
        # Native GET returns null until there is a stored record. Store empty
        # overrides via the owner, leaving enabled=True solely the native default.
        saved = webui.ok("POST", function_path + "/valves/user/update", token=user["token"], body={})
        require(saved == {}, "Native empty UserValves initialization changed defaults")
    display_readback(webui, state)
    state["cost_display"]["stage"] = "setup_complete"
    write_private(path, state)


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
    for account in [state.get("admin", {}), *state.get("users", [])]:
        values.extend(account.get(key) for key in ("password", "token"))
    values.extend(entry.get("key") for entry in state.get("native_keys", []))
    values.append((state.get("cost_reader") or {}).get("key"))
    return [value for value in values if isinstance(value, str) and value]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("setup", "scenario", "snapshot"))
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
        if args.phase == "scenario":
            receipt["tool_scenario"] = scenario(webui, state, args.private_state)
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
