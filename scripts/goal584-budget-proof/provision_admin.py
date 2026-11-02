#!/usr/bin/env python3
"""Install/read back the isolated native admin Tool, Skill and Workspace preset.

Only native management APIs mutate state. The optional native-probe issues one
synthetic request that MUST be denied at a zero native key cap; its receipt alone
does not establish provider absence. All credentials remain in 0600 private files.
Pinned WebUI6a18585: tools385/474/832; skills219/298; models356/797.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request

from aiohttp import ClientSession

from employee_budget_assignment import assignment_alias, assignment_metadata
from employee_budget_admin_client import BudgetAdminClient
from employee_budget_admin_contract import BudgetAdminError
from provision_webui import MODELS, OPERATOR_STATE, PROXY_URL, WEBUI_URL, WebUI, account_from_response, native_client, read_private, require, write_private, ProofError
from provision_cost_display import (
    STATE, FILTER_ID, assert_private_text_absent, denied_admin_get, grant_set,
    model_body, persisted_scope, secret_values, source_hash,
)
from prove_native_budgets import BUDGET_EXCEEDED_STATUS, amount


TOOL_ID = "employee_budget_admin"
SKILL_ID = "goal584-budget-admin-guide"
MODEL_ID = "goal584-budget-admin"
SOURCE = Path("/proof/budgets/admin_tools.py")
SKILL = """# Employee budget administration

For a request to view or configure employee budgets, call open_budget_form.
Use view_json only for display filters. Present the native form to the admin.
When the current user turn is a JSON employee_budget_plan, call apply_budget_form
with no business arguments. The server reads the exact saved parent user turn;
do not copy, rewrite or interpret its changes as tool arguments. Applying requires
the native server confirmation. Treat the returned fresh form as the result;
never claim that limits changed merely because a plan was drafted or submitted.
"""


def money(value):
    return None if value is None else format(value, "f")


def normalize(states):
    """Project actual client DTOs; preserve unknown/unlimited caps as null."""
    users, keys = [], []
    for state in states:
        users.append({"user_id": state.user_id, "max_budget_usd": money(state.max_budget),
                      "spend_usd": money(state.spend), "budget_duration": state.budget_duration,
                      "budget_reset_at": state.budget_reset_at})
        keys.extend({"user_id": state.user_id, "model": key.model, "key_alias": key.key_alias,
                     "max_budget_usd": money(key.max_budget), "spend_usd": money(key.spend),
                     "budget_duration": key.budget_duration, "budget_reset_at": key.budget_reset_at}
                    for key in state.models)
    return {"users": users, "keys": keys}


async def actual_states(state, *, include_admin=True):
    operator = read_private(OPERATOR_STATE)["operator_token"]
    async with ClientSession(trust_env=False) as session:
        client = BudgetAdminClient(session, PROXY_URL, operator)
        accounts = [*state["users"], *([state["admin"]] if include_admin else [])]
        result = [await client.read_employee(account["id"], tuple(MODELS)) for account in accounts]
    private_keys = [*state["native_keys"], *(state.get("admin_budgetnative_keys", []) if include_admin else [])]
    for employee in result:
        for key in employee.models:
            matches = [entry for entry in private_keys if entry["user_id"] == employee.user_id
                       and entry["model"] == key.model]
            require(len(matches) == 1 and matches[0]["key_alias"] == key.key_alias
                    and hashlib.sha256(matches[0]["key"].encode()).hexdigest() == key.key_hash,
                    "Native canonical assignment differs from the private fixture identity")
    return result


def read_states(state, *, include_admin=True):
    return asyncio.run(actual_states(state, include_admin=include_admin))


def staff_profiles(webui, state):
    return {model: source_hash(json.dumps(model_body(webui.model(state["admin"]["token"], model)),
                                         sort_keys=True, allow_nan=False)) for model in MODELS}


def filter_admin_key(webui, state, *, install=False):
    """One credential owner: existing admin-only Function Valves, full native payload."""
    path, token = "/api/v1/functions/id/" + FILTER_ID + "/valves", state["admin"]["token"]
    before = webui.ok("GET", path, token=token)
    require(before.get("ledger_base_url") == "http://proxy:4000"
            and before.get("ledger_read_key") == state["cost_reader"]["key"]
            and before.get("read_wait_seconds") == 8.0, "Existing cost Filter configuration differs")
    expected = {**copy.deepcopy(before), "ledger_admin_key": read_private(OPERATOR_STATE)["operator_token"]}
    if install:
        webui.ok("POST", path + "/update", token=token, body=expected)
        after = webui.ok("GET", path, token=token)
    else:
        after = before
    require(after == expected, "Native Filter management key readback changed or lost existing Valves")


def installation(webui, state):
    admin, fixture = state["admin"], state["admin_fixture"]
    expected_grants = {("user", admin["id"], "read")}
    tool = webui.ok("GET", "/api/v1/tools/id/" + TOOL_ID, token=admin["token"])
    require(tool.get("user_id") == admin["id"] and tool.get("write_access") is True
            and grant_set(tool) == expected_grants and isinstance(tool.get("content"), str)
            and source_hash(tool["content"]) == fixture["source_sha256"]
            == source_hash(SOURCE.read_text(encoding="utf-8")), "Native admin Tool source/owner/ACL differs")
    specs = tool.get("specs")
    require(isinstance(specs, list) and len(specs) == 2, "Native admin Tool schema count differs")
    methods = {spec.get("name"): spec for spec in specs}
    require(set(methods) == {"open_budget_form", "apply_budget_form"}
            and set(methods["open_budget_form"].get("parameters", {}).get("properties", {})) == {"view_json"}
            and methods["open_budget_form"]["parameters"]["properties"]["view_json"].get("type") == "string"
            and methods["open_budget_form"]["parameters"]["properties"]["view_json"].get("default") == "{}"
            and methods["apply_budget_form"].get("parameters", {}).get("properties") == {},
            "Native admin Tool exposed business/reserved arguments")
    valves = webui.ok("GET", "/api/v1/tools/id/" + TOOL_ID + "/valves", token=admin["token"])
    require(valves == {"managed_model_ids": list(MODELS), "employee_limit": 100},
            "Native Tool Valves contain credentials or differ from the public configuration")
    filter_admin_key(webui, state)
    skill = webui.ok("GET", "/api/v1/skills/id/" + SKILL_ID, token=admin["token"])
    require(skill.get("user_id") == admin["id"] and skill.get("write_access") is True
            and skill.get("is_active") is True and grant_set(skill) == expected_grants
            and skill.get("content") == SKILL, "Native admin Skill content/owner/ACL differs")
    preset = webui.model(admin["token"], MODEL_ID)
    require(model_body(preset) == fixture["preset"], "Native admin model preset changed")
    function = webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID, token=admin["token"])
    require(function.get("is_active") is True and function.get("type") == "filter"
            and function.get("meta", {}).get("toggle") is False, "Mandatory native cost Filter is unavailable")
    access = []
    for user in state["users"]:
        catalog = webui.catalog(user)
        access.append({"user_id": user["id"], "model_ids": catalog["model_ids"],
                       "tool_status": denied_admin_get(webui, user["token"], "/api/v1/tools/id/" + TOOL_ID),
                       "tool_valves_status": denied_admin_get(webui, user["token"], "/api/v1/tools/id/" + TOOL_ID + "/valves"),
                       "skill_status": denied_admin_get(webui, user["token"], "/api/v1/skills/id/" + SKILL_ID),
                       "preset_status": denied_admin_get(webui, user["token"], "/api/v1/models/model?id=" + MODEL_ID)})
    return {"tool_id": TOOL_ID, "source_sha256": fixture["source_sha256"], "admin_only": True,
            "native_specs": specs, "valves_readback": True, "managed_model_ids": list(MODELS),
            "management_credential_owner": "Function/" + FILTER_ID,
            "management_key_readback": True, "tool_valves_secret_free": True,
            "skill_id": SKILL_ID, "skill_sha256": source_hash(SKILL), "skill_active": True,
            "model_id": MODEL_ID, "base_model_id": MODELS[0], "builtin_tools": False,
            "filter_ids": [FILTER_ID], "tool_ids": [TOOL_ID], "skill_ids": [SKILL_ID],
            "employee_access": access}


def setup(webui, state, path):
    require("admin_fixture" not in state and "admin_budgetnative_keys" not in state,
            "Admin setup requires a fresh disposable installation")
    source = SOURCE.read_text(encoding="utf-8")
    require(0 < len(source.encode()) <= 128 * 1024, "Admin Tool source exceeds fixture bounds")
    before = read_states(state, include_admin=False)
    profiles = staff_profiles(webui, state)
    admin, native = state["admin"], native_client(state)
    state["admin_fixture"] = {"stage": "installing", "source_sha256": source_hash(source),
                              "staff_baseline": normalize(before), "staff_profiles": profiles}
    state["admin_budgetnative_keys"] = []
    write_private(path, state)
    native.schema()
    native.ok("POST", "/user/new", body={"user_id": admin["id"], "user_role": "internal_user",
              "models": list(MODELS), "max_budget": 1000.0, "budget_duration": "30d",
              "auto_create_key": False, "send_invite_email": False})
    for model in MODELS:
        alias = assignment_alias(admin["id"], model)
        generated = native.ok("POST", "/key/generate", body={"user_id": admin["id"], "models": [model],
            "key_alias": alias, "metadata": assignment_metadata(model), "max_budget": 500.0,
            "budget_duration": "30d", "allowed_routes": ["llm_api_routes"]})
        key = generated.get("key")
        require(isinstance(key, str) and key.startswith("sk-"), "Native admin personal key was not returned")
        state["admin_budgetnative_keys"].append({"user_id": admin["id"], "model": model,
                                               "key_alias": alias, "key": key})
        write_private(path, state)
    grants = [{"principal_type": "user", "principal_id": admin["id"], "permission": "read"}]
    webui.ok("POST", "/api/v1/tools/create", token=admin["token"], body={"id": TOOL_ID,
             "name": "Employee budget administration", "content": source, "meta": {}, "access_grants": grants})
    filter_admin_key(webui, state, install=True)
    webui.ok("POST", "/api/v1/tools/id/" + TOOL_ID + "/valves/update", token=admin["token"],
             body={"managed_model_ids": list(MODELS), "employee_limit": 100})
    webui.ok("POST", "/api/v1/skills/create", token=admin["token"], body={"id": SKILL_ID,
             "name": "Employee budget administration guide", "description": "Native form and confirmation workflow",
             "content": SKILL, "meta": {}, "is_active": True, "access_grants": grants})
    base = webui.model(admin["token"], MODELS[0])
    preset = {"id": MODEL_ID, "base_model_id": MODELS[0], "name": "Employee budgets",
              "meta": {"capabilities": {"builtin_tools": False}, "filterIds": [FILTER_ID],
                       "toolIds": [TOOL_ID], "skillIds": [SKILL_ID]},
              "params": copy.deepcopy(base["params"]), "access_grants": grants, "is_active": True}
    webui.ok("POST", "/api/v1/models/create", token=admin["token"], body=preset)
    # Native ModelMeta may materialize defaults. Preserve actual fields for future drift checks.
    actual_preset = model_body(webui.model(admin["token"], MODEL_ID))
    require(actual_preset["base_model_id"] == MODELS[0] and actual_preset["is_active"] is True
            and actual_preset["params"] == preset["params"] and grant_set(actual_preset) == grant_set(preset)
            and all(actual_preset["meta"].get(k) == v for k, v in preset["meta"].items()),
            "Native admin preset did not retain requested fields")
    state["admin_fixture"]["preset"] = actual_preset
    after = read_states(state)
    require(after[:2] == before and staff_profiles(webui, state) == profiles,
            "Admin setup changed existing staff state or native model profiles")
    own = after[2]
    require(own.max_budget == Decimal("1000") and own.spend == 0 and own.budget_duration == "30d"
            and own.budget_reset_at is not None and len(own.models) == 2
            and all(key.max_budget == Decimal("500") and key.spend == 0
                    and key.budget_duration == "30d" and key.budget_reset_at is not None for key in own.models),
            "Admin personal native caps/spend differ from the synthetic setup")
    installation(webui, state)
    state["admin_fixture"]["stage"] = "setup_complete"
    write_private(path, state)


def positive_logs(native, state):
    result, unqualified = [], 0
    for account in [*state["users"], state["admin"]]:
        for row in native.logs(account["id"]):
            spend = amount(row.get("spend"))
            require(spend >= 0, "Native spend is negative")
            if spend == 0:
                unqualified += 1  # Unknown/failure zero is deliberately not presented as verified free usage.
                continue
            assert_private_text_absent(row)
            scope = persisted_scope(row, account["id"])
            tokens = [row.get(field) for field in ("prompt_tokens", "completion_tokens", "total_tokens")]
            request_id = row.get("request_id")
            require(row.get("status") == "success" and row.get("model_group") == scope["model"]
                    and scope["model"] in MODELS and isinstance(request_id, str) and 0 < len(request_id) <= 512
                    and all(type(n) is int and n >= 0 for n in tokens) and tokens[0] + tokens[1] == tokens[2],
                    "Positive native admin/staff row has unqualified identity/usage")
            result.append({"request_id": request_id, "user_id": account["id"], "model_group": scope["model"],
                           "session_id": row["session_id"], "owui_budget": scope,
                           "spend_usd": money(spend), "prompt_tokens": tokens[0],
                           "completion_tokens": tokens[1], "total_tokens": tokens[2]})
    require(len({r["request_id"] for r in result}) == len(result), "Duplicate positive native request ID")
    return result, unqualified


def snapshot(webui, state):
    states = read_states(state)
    staff, admin = normalize(states[:2]), normalize(states[2:])
    baseline = state["admin_fixture"]["staff_baseline"]
    rows, unqualified = positive_logs(native_client(state), state)
    return {**staff, "admin_accounting": {**admin, "native_role": "internal_user"},
            "installation": installation(webui, state), "attributed_spend_logs": rows,
            "unqualified_zero_row_count": unqualified,
            "no_change_checks": {"staff_budgets_equal_setup": staff == baseline,
                                  "staff_model_profiles_equal_setup": staff_profiles(webui, state)
                                  == state["admin_fixture"]["staff_profiles"]},
            "source_endpoints": ["/user/info", "/key/list", "/spend/logs/v2"]}


def native_probe(state, *, deny):
    before, native = read_states(state), native_client(state)
    own = before[2]
    key = next(key for key in own.models if key.model == MODELS[1])
    require(key.spend == 0 and key.max_budget == Decimal("500"), "Native probe requires unused admin B cap500")

    async def cap(value):
        async with ClientSession(trust_env=False) as session:
            await BudgetAdminClient(session, PROXY_URL, read_private(OPERATOR_STATE)["operator_token"]).set_model_cap(key.key_hash, value)

    def expect(expected):
        def condition():
            actual = read_states(state)
            return actual if actual == expected else None
        native.poll("admin native hash-update exact readback", condition)

    asyncio.run(cap(key.max_budget))
    expect(before)
    result = {"by_native_hash": True, "same_cap_identity_spend_reset_unchanged": True}
    if not deny:
        return result
    limited = [*before[:2], replace(own, models=tuple(replace(k, max_budget=Decimal(0))
                                                    if k.model == key.model else k for k in own.models))]
    try:
        asyncio.run(cap(Decimal(0)))
        expect(limited)
        raw = next(entry["key"] for entry in state["admin_budgetnative_keys"] if entry["model"] == key.model)
        status, payload, _ = native.request("POST", "/v1/chat/completions", token=raw,
            body={"model": key.model, "messages": [{"role": "user", "content": "Hi"}],
                  "max_tokens": 5, "stream": False})
        error = payload.get("error")
        require(status == BUDGET_EXCEEDED_STATUS and isinstance(error, dict)
                and error.get("type") == "budget_exceeded"
                and "Key=" + key.key_alias in str(error.get("message", "")),
                "Zero-cap native admin key did not yield the expected native key budget denial")
        expect(limited)
        result.update(zero_cap_readback=True, denial_http_status=status, denial_type="budget_exceeded",
                      provider_absence_requires_external_comparison=True)
    finally:
        # Explicit disposable probe restoration; do not conceal partial failure or replace identities.
        asyncio.run(cap(key.max_budget))
        expect(before)
    result["original_cap_restored_exactly"] = True
    return result


def denied_status(webui, method, path, token, *, body=None):
    """Use the existing no-redirect/proxy opener; consume no error body or secret."""
    request = Request(WEBUI_URL + path, method=method,
                      headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
                      data=None if body is None else json.dumps(body, allow_nan=False).encode("utf-8"))
    try:
        response = webui.opener.open(request, timeout=20)
    except HTTPError as error:
        response = error
    except (URLError, TimeoutError, OSError):
        raise ProofError("Native role probe transport failed") from None
    with response:
        status = response.code
    require(status in (401, 403), "Demoted native owner was not denied the protected API")
    return status


def refresh_login(webui, account, role):
    response = webui.ok("POST", "/api/v1/auths/signin",
                        body={"email": account["email"], "password": account["password"]})
    fresh = account_from_response(response, account["email"], account["password"], role)
    require(fresh["id"] == account["id"], "Native role-probe sign-in changed owner identity")
    account.update(fresh)
    webui.session(account, role)


def role_probe(webui, state, path):
    """Actual native role transition; fixture's primary control admin restores in finally."""
    owner, control = state["admin"], state.get("role_probe_control")
    require(isinstance(control, dict) and control.get("id") != owner["id"],
            "Role probe requires a distinct primary native control administrator")
    webui.session(control, "admin")
    webui.session(owner, "admin")
    permissions = webui.ok("GET", "/api/v1/users/default/permissions", token=control["token"])
    require(permissions.get("workspace", {}).get("tools") is False
            and permissions.get("workspace", {}).get("tools_import") is False,
            "Role probe requires native workspace Tool-code permissions disabled")
    before, profiles = read_states(state), staff_profiles(webui, state)
    preset = model_body(webui.model(owner["token"], MODEL_ID))
    tool = webui.ok("GET", "/api/v1/tools/id/" + TOOL_ID, token=owner["token"])
    function = webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID, token=owner["token"])
    require(tool.get("user_id") == owner["id"] and function.get("user_id") == owner["id"],
            "Role probe target is not the actual Tool and Filter owner")
    filter_admin_key(webui, state)
    result = {"native_owner_demotion": True, "workspace_tool_code_permissions": False}
    try:
        changed = webui.ok("POST", "/api/v1/users/" + owner["id"] + "/update",
                           token=control["token"], body={"role": "user"})
        require(changed.get("id") == owner["id"] and changed.get("role") == "user",
                "Native owner role demotion did not persist")
        refresh_login(webui, owner, "user")
        valves = webui.ok("GET", "/api/v1/tools/id/" + TOOL_ID + "/valves", token=owner["token"])
        require(valves == {"managed_model_ids": list(MODELS), "employee_limit": 100},
                "Demoted native Tool owner could read a credential-bearing Valves field")
        result["tool_valves_http_status"] = 200
        result["tool_valves_secret_free"] = True
        function_path = "/api/v1/functions/id/" + FILTER_ID + "/valves"
        result["function_valves_get_status"] = denied_status(webui, "GET", function_path, owner["token"])
        result["function_valves_post_status"] = denied_status(
            webui, "POST", function_path + "/update", owner["token"], body={"ledger_admin_key": ""})
        form = {field: copy.deepcopy(tool[field]) for field in ("id", "name", "content", "meta", "access_grants")}
        form["content"] += "\n# unauthorized synthetic role-probe source change\n"
        result["tool_code_update_status"] = denied_status(
            webui, "POST", "/api/v1/tools/id/" + TOOL_ID + "/update", owner["token"], body=form)
    finally:
        restored = webui.ok("POST", "/api/v1/users/" + owner["id"] + "/update",
                            token=control["token"], body={"role": "admin"})
        require(restored.get("id") == owner["id"] and restored.get("role") == "admin",
                "Native owner administrator role restoration failed")
        refresh_login(webui, owner, "admin")
        write_private(path, state)
    require(read_states(state) == before and staff_profiles(webui, state) == profiles
            and model_body(webui.model(owner["token"], MODEL_ID)) == preset,
            "Role probe changed native caps/spend/reset/identities or model profiles")
    installation(webui, state)
    result.update(owner_admin_restored=True, native_budget_state_unchanged=True,
                  model_profiles_unchanged=True, installed_source_and_key_unchanged=True,
                  inference_requests_issued=0, provider_absence_requires_external_comparison=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("setup", "snapshot", "hash-probe", "native-probe", "role-probe"))
    parser.add_argument("--private-state", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--browser-accounts", type=Path)
    args = parser.parse_args()
    receipt = {"schema": 1, "proof": "goal584-native-admin-provisioning", "phase": args.phase,
               "passed": False, "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "not_qualified": ["admin_GUI_in_this_script", "production", "paid_provider"]}
    state, credentials, output_valid = {}, [], False
    try:
        require(args.private_state.resolve() == STATE.resolve(), "Admin provisioning requires the fixed private state")
        paths = [args.private_state.resolve(), args.receipt.resolve(), OPERATOR_STATE.resolve()]
        if args.browser_accounts:
            paths.append(args.browser_accounts.resolve())
        require(len(set(paths)) == len(paths), "Private state/handoff and receipt paths must be separate")
        output_valid = True
        require(args.browser_accounts is None or args.phase == "setup", "Browser handoff is setup-only")
        state = read_private(args.private_state)
        credentials.append(read_private(OPERATOR_STATE)["operator_token"])
        require(state.get("stage") == "setup_complete" and len(state.get("users", [])) == 2
                and len(state.get("native_keys", [])) == 4
                and state.get("cost_display", {}).get("stage") == "setup_complete", "Native base/cost setup is incomplete")
        webui = WebUI()
        require(webui.ok("GET", "/api/version").get("version") == "0.12.2", "WebUI version differs from fixture")
        webui.session(state["admin"], "admin")
        if args.phase == "setup":
            setup(webui, state, args.private_state)
            if args.browser_accounts:
                require(not args.browser_accounts.exists(), "Browser admin handoff must be a new private file")
                write_private(args.browser_accounts, {"schema": 1, "admin": {
                    field: state["admin"][field] for field in ("id", "email", "password")},
                    "model_id": MODEL_ID, "tool_id": TOOL_ID, "skill_id": SKILL_ID})
        require(state.get("admin_fixture", {}).get("stage") == "setup_complete", "Admin installation is incomplete")
        if args.phase in ("hash-probe", "native-probe"):
            receipt["native_probe"] = native_probe(state, deny=args.phase == "native-probe")
        elif args.phase == "role-probe":
            receipt["role_probe"] = role_probe(webui, state, args.private_state)
        receipt.update(snapshot(webui, state))
        receipt["passed"] = True
    except ProofError as error:
        receipt["failure"] = str(error)
    except BudgetAdminError as error:
        receipt["failure"] = "Native admin client: " + error.code
    except Exception as error:
        receipt["failure"] = "Unexpected admin fixture error: " + type(error).__name__
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    rendered = json.dumps(receipt, indent=2, allow_nan=False)
    credentials += secret_values(state) + [entry["key"] for entry in state.get("admin_budgetnative_keys", [])]
    credentials += [state.get("role_probe_control", {}).get(field) for field in ("password", "token")]
    if any(value and value in rendered for value in credentials) or re.search(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", rendered):
        receipt = {"schema": 1, "proof": "goal584-native-admin-provisioning", "phase": args.phase,
                   "passed": False, "failure": "Unsafe credential-bearing receipt suppressed"}
        rendered = json.dumps(receipt, indent=2)
    if output_valid:
        write_private(args.receipt, receipt)
    print(rendered)
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
