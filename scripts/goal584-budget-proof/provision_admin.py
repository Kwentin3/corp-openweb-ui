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
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
from uuid import UUID, uuid4, uuid5
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
from prove_native_budgets import BUDGET_EXCEEDED_STATUS, amount, expected_budget_message


TOOL_ID = "employee_budget_admin"
SKILL_ID = "goal584-budget-admin-guide"
MODEL_ID = "goal584-budget-admin"
SOURCE = Path("/proof/budgets/admin_tools.py")
UNKNOWN_ADMIN_STATE = Path('/proof-private/admin-unknown-state.private.json')
UNKNOWN_ADMIN_ACCOUNTS = Path('/proof-private/admin-unknown-accounts.private.json')
# Stand-only headroom for the native reservation of both full-context Tool rounds.
UNKNOWN_ADMIN_CAP = Decimal('10')
SKILL = """# Employee budget administration

For a request to view or configure employee budgets, call open_budget_form.
Use view_json only for display filters. Present the native form to the admin.
When the current user turn is a JSON employee_budget_plan,
employee_budget_template, employee_budget_initialize or provider_balance_snapshot, call apply_budget_form
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


def installation(webui, state, *, managed_model_ids=MODELS, base_model_id=None, user_catalogs=None):
    base_model_id = MODELS[0] if base_model_id is None else base_model_id
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
    require(valves == {"managed_model_ids": list(managed_model_ids), "employee_limit": 100},
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
        catalog = webui.catalog(user) if user_catalogs is None else {'model_ids': sorted(user_catalogs[user['id']])}
        access.append({"user_id": user["id"], "model_ids": catalog["model_ids"],
                       "tool_status": denied_admin_get(webui, user["token"], "/api/v1/tools/id/" + TOOL_ID),
                       "tool_valves_status": denied_admin_get(webui, user["token"], "/api/v1/tools/id/" + TOOL_ID + "/valves"),
                       "skill_status": denied_admin_get(webui, user["token"], "/api/v1/skills/id/" + SKILL_ID),
                       "preset_status": denied_admin_get(webui, user["token"], "/api/v1/models/model?id=" + MODEL_ID)})
    return {"tool_id": TOOL_ID, "source_sha256": fixture["source_sha256"], "admin_only": True,
            "native_specs": specs, "valves_readback": True, "managed_model_ids": list(managed_model_ids),
            "management_credential_owner": "Function/" + FILTER_ID,
            "management_key_readback": True, "tool_valves_secret_free": True,
            "skill_id": SKILL_ID, "skill_sha256": source_hash(SKILL), "skill_active": True,
            "model_id": MODEL_ID, "base_model_id": base_model_id, "builtin_tools": False,
            "filter_ids": [FILTER_ID], "tool_ids": [TOOL_ID], "skill_ids": [SKILL_ID],
            "employee_access": access}


def setup(webui, state, path):
    require("admin_fixture" not in state and "admin_budgetnative_keys" not in state,
            "Admin setup requires a fresh disposable installation")
    # Representative native profile data for the local department filter.
    for account, department in zip(state["users"], ("Продажи", "Разработка")):
        info = webui.ok("POST", "/api/v1/users/user/info/update", token=account["token"],
                        body={"department": department})
        require(info.get("department") == department, "Native fixture department did not persist")
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
    state["admin_fixture"]["preset"] = install_resources(webui, state, source)
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


def install_resources(webui, state, source, *, managed_model_ids=MODELS, base_model_id=None):
    """Single canonical Tool/Skill/preset installer; callers own fresh scope."""
    base_model_id = MODELS[0] if base_model_id is None else base_model_id
    admin = state['admin']
    grants = [{"principal_type": "user", "principal_id": admin["id"], "permission": "read"}]
    webui.ok("POST", "/api/v1/tools/create", token=admin["token"], body={"id": TOOL_ID,
             "name": "Employee budget administration", "content": source, "meta": {}, "access_grants": grants})
    filter_admin_key(webui, state, install=True)
    webui.ok("POST", "/api/v1/tools/id/" + TOOL_ID + "/valves/update", token=admin["token"],
             body={"managed_model_ids": list(managed_model_ids), "employee_limit": 100})
    webui.ok("POST", "/api/v1/skills/create", token=admin["token"], body={"id": SKILL_ID,
             "name": "Employee budget administration guide", "description": "Native form and confirmation workflow",
             "content": SKILL, "meta": {}, "is_active": True, "access_grants": grants})
    base = webui.model(admin["token"], base_model_id)
    preset = {"id": MODEL_ID, "base_model_id": base_model_id, "name": "Employee budgets",
              "meta": {"capabilities": {"builtin_tools": False}, "filterIds": [FILTER_ID],
                       "toolIds": [TOOL_ID], "skillIds": [SKILL_ID]},
              "params": copy.deepcopy(base["params"]), "access_grants": grants, "is_active": True}
    webui.ok("POST", "/api/v1/models/create", token=admin["token"], body=preset)
    # Native ModelMeta may materialize defaults. Preserve actual fields for future drift checks.
    actual_preset = model_body(webui.model(admin["token"], MODEL_ID))
    require(actual_preset["base_model_id"] == base_model_id and actual_preset["is_active"] is True
            and actual_preset["params"] == preset["params"] and grant_set(actual_preset) == grant_set(preset)
            and all(actual_preset["meta"].get(k) == v for k, v in preset["meta"].items()),
            "Native admin preset did not retain requested fields")
    return actual_preset


def unknown_inputs(common, office, unknown):
    from prove_unknown_usage_policy import ALIASES
    require(common.get('stage') == office.get('stage') == unknown.get('stage') == 'setup_complete'
            and len(common.get('users', [])) == 2 and len(common.get('native_keys', [])) == 4
            and common.get('cost_display', {}).get('stage') == 'setup_complete'
            and office.get('admin') == unknown.get('admin') == common.get('admin')
            and len(office.get('users', [])) == len(unknown.get('users', [])) == 1
            and unknown.get('unknown_gui_verification', {}).get('stage') == 'verified'
            and isinstance(unknown['unknown_gui_verification'].get('native'), dict)
            and set(unknown.get('unknown_gui_setup', {}).get('models', {})) == set(ALIASES),
            'Admin unknown setup requires the actual verified ordinary-user fixture')
    actors = [common['admin'], *common['users'], *office['users'], *unknown['users']]
    if common.get('role_probe_control'): actors.append(common['role_probe_control'])
    require(len({a['id'] for a in actors}) == len(actors), 'Admin unknown fixture actors collide')
    return actors


def unknown_webui_state(webui, common, office, unknown):
    """Raw native technical preservation readback, not a financial projection."""
    from prove_service_tasks import response
    admin = common['admin']
    actors = unknown_inputs(common, office, unknown)
    get = lambda route: webui.ok('GET', route, token=admin['token'])
    directory = get('/api/v1/users/all')
    rows = directory.get('users')
    require(isinstance(rows, list) and len(rows) <= 100 and directory.get('total') == len(rows)
            and len({r.get('id') for r in rows}) == len(rows), 'Admin unknown directory incomplete')
    directory = {r['id']: {k: r.get(k) for k in ('id', 'name', 'email', 'role', 'info')} for r in rows}
    catalogs = {}
    for actor in actors:
        role = 'admin' if actor['id'] in {admin['id'], common.get('role_probe_control', {}).get('id')} else 'user'
        webui.session(actor, role)
        require(directory.get(actor['id'], {}).get('role') == role, 'Admin unknown native role drift')
        data = webui.ok('GET', '/api/models?refresh=true', token=actor['token']).get('data')
        require(isinstance(data, list) and len(data) <= 100 and all(isinstance(r.get('id'), str) for r in data)
                and len({r['id'] for r in data}) == len(data), 'Admin unknown catalog incomplete')
        catalogs[actor['id']] = {r['id']: r for r in data}
    status, functions = response(webui, 'GET', '/api/v1/functions/export?include_valves=true', admin['token'])
    require(status == 200 and isinstance(functions, list) and all(isinstance(r.get('id'), str) for r in functions)
            and len({r['id'] for r in functions}) == len(functions), 'Admin unknown Function export unavailable')
    models = {mid: webui.model(admin['token'], mid) for mid, row in catalogs[admin['id']].items()
              if (row.get('info') or {}).get('id') == mid and mid != MODEL_ID}
    return {'directory': directory, 'catalogs': catalogs, 'models': models,
        'functions': {r['id']: r for r in functions},
        'valves': get('/api/v1/functions/id/' + FILTER_ID + '/valves'),
        'connections': get('/openai/config'), 'tasks': get('/api/v1/tasks/config'),
        'chat_config': get('/api/v1/chats/config'), 'tool_servers': get('/api/v1/configs/tool_servers')}


async def unknown_observation(webui, common, office, unknown, selected=None):
    """Reuse actual existing native DTO/history owners; keep service separate."""
    import prove_unknown_usage_policy as U
    from prove_unknown_usage_gui import old_accounts, wire_json
    unknown_inputs(common, office, unknown)
    native = native_client()
    native.started_at = datetime.fromisoformat(common['started_at_utc'])
    operator = read_private(OPERATOR_STATE)['operator_token']
    async with ClientSession(trust_env=False) as session:
        client = BudgetAdminClient(session, PROXY_URL, operator)
        old = await old_accounts(client, native, common, office, webui)
        actor = unknown['users'][0]
        budget = await client.read_employee(actor['id'], U.ALIASES)
        result = {'unknown': {'budget': wire_json(asdict(budget)), 'native': U.snapshot(native, budget)}, 'old': old}
        if selected is not None:
            own = await client.read_employee(selected['admin']['id'], (U.ALIASES[0],))
            result['own'] = {'budget': wire_json(asdict(own)), 'native': U.snapshot(native, own)}
    result['route_sha256'] = U.routing(native, buffered=True)
    result['model_info'] = [row for row in native.ok('GET', '/model/info')['data'] if row.get('model_name') in U.ALIASES]
    valves = webui.ok('GET', '/api/v1/functions/id/' + FILTER_ID + '/valves', token=common['admin']['token'])
    payer = valves.get('service_payer_id')
    require(not payer or payer in old, 'Admin unknown service owner missing')
    result['service'] = result['old'].pop(payer) if payer else None
    return result


def unknown_view(common, selected):
    return {**common, 'admin': selected['admin'], 'users': [], 'admin_fixture': selected['admin_fixture']}


def unknown_preserved(before, after, *, new_admin=None, installing=False):
    expected = copy.deepcopy(before)
    if installing:
        expected['directory'][new_admin['id']] = after['directory'].get(new_admin['id'])
        require(isinstance(expected['directory'][new_admin['id']], dict)
                and expected['directory'][new_admin['id']].get('role') == 'admin'
                and expected['directory'][new_admin['id']].get('email') == new_admin['email'],
                'New admin native identity/role differs')
        operator = read_private(OPERATOR_STATE)['operator_token']
        expected['valves']['ledger_admin_key'] = operator
        old_filter, current = expected['functions'][FILTER_ID], after['functions'][FILTER_ID]
        old_filter['valves'] = expected['valves']
        require(type(current.get('updated_at')) is int and current['updated_at'] >= old_filter['updated_at'],
                'Native Function update timestamp differs')
        old_filter['updated_at'] = current['updated_at']
        from prove_unknown_usage_policy import ALIASES
        for mid in (ALIASES[0], 'gpt-6-luna'):
            original, current = expected['models'][mid], after['models'][mid]
            wanted = model_body(original)
            wanted['access_grants'].append({'principal_type': 'user', 'principal_id': new_admin['id'], 'permission': 'read'})
            require(not model_grant_changes(wanted, model_body(current)), 'Admin source/target read grant changed model fields')
            allowed = copy.deepcopy(original)
            allowed['access_grants'] = current['access_grants']
            if 'updated_at' in original:
                require(type(current.get('updated_at')) is int and current['updated_at'] >= original['updated_at'],
                        'Admin source/target model update timestamp differs')
                allowed['updated_at'] = current['updated_at']
            require(current == allowed, 'Admin source/target read grant changed model owner or native state')
            expected['models'][mid] = allowed
            for uid, catalog in expected['catalogs'].items():
                if mid not in catalog: continue
                info = catalog[mid].get('info', {})
                observed_info = after['catalogs'][uid][mid].get('info', {})
                if 'access_grants' in info:
                    require(grant_set(observed_info) == grant_set(current), 'Admin source/target catalog grants differ')
                    info['access_grants'] = observed_info['access_grants']
                if 'updated_at' in info: info['updated_at'] = current['updated_at']
        for uid, catalog in expected['catalogs'].items():
            if expected['directory'][uid]['role'] == 'admin':
                require(MODEL_ID in after['catalogs'][uid], 'Native admin cannot discover canonical preset')
                catalog[MODEL_ID] = after['catalogs'][uid][MODEL_ID]
    require(after == expected, 'Admin unknown setup/readback changed existing native state')


def unknown_admin_read_grants(webui, common, office, selected, before, path):
    """Prepare only the fresh stand admin's existing native source/target reads."""
    from prove_unknown_usage_policy import ALIASES
    require(office.get('service_fixture', {}).get('target_model_id') == 'gpt-6-luna',
            'Admin follow-up requires the prepared canonical Office service target')
    owner = common['admin']
    webui.session(owner, 'admin')
    for mid in (ALIASES[0], 'gpt-6-luna'):
        original = webui.model(owner['token'], mid)
        require(original == before['models'].get(mid) and original.get('user_id') == owner['id'],
                'Admin source/target read grant requires the unchanged native owner')
        grant = {'principal_type': 'user', 'principal_id': selected['admin']['id'], 'permission': 'read'}
        require(('user', selected['admin']['id'], 'read') not in grant_set(original),
                'Fresh admin already has a source/target read grant')
        wanted = model_body(original)
        wanted['access_grants'].append(grant)
        entry = {'stage': 'native-model-read-grant', 'model_id': mid, 'original': original,
                 'requested': wanted, 'returned': False}
        selected['journal'].append(entry); write_private(path, selected)
        webui.ok('POST', '/api/v1/models/model/update', token=owner['token'], body=wanted)
        observed = webui.model(owner['token'], mid)
        require(observed.get('user_id') == original['user_id']
                and not model_grant_changes(wanted, model_body(observed)),
                'Admin source/target native read grant changed owner or model fields')
        entry.update(returned=True, readback=observed); write_private(path, selected)


async def unknown_setup(webui, common, office, unknown, path, handoff):
    from prove_service_tasks import response
    from prove_unknown_usage_policy import ALIASES
    actors = unknown_inputs(common, office, unknown)
    require(not path.exists() and handoff is not None and not handoff.exists(), 'Admin unknown setup needs fresh private outputs')
    source = SOURCE.read_text(encoding='utf-8')
    require(0 < len(source.encode()) <= 128 * 1024, 'Admin Tool source exceeds fixture bounds')
    gateway = os.environ.get('OWUI_BUDGET_GATEWAY_SECRET', '')
    require(bool(gateway) and not any(c.isspace() for c in gateway), 'Admin unknown gateway missing')
    for route in ('/api/v1/tools/id/' + TOOL_ID, '/api/v1/skills/id/' + SKILL_ID,
                  '/api/v1/models/model?id=' + MODEL_ID):
        require(response(webui, 'GET', route, common['admin']['token'])[0] == 404,
                'Canonical admin resource exists or absence unproven')
    before = unknown_webui_state(webui, common, office, unknown)
    require(all(before['models'].get(alias) == unknown['unknown_gui_setup']['models'][alias] for alias in ALIASES),
            'Admin unknown Workspace profiles differ from the verified fixture')
    require(before['valves'].get('ledger_admin_key') in (None, '', read_private(OPERATOR_STATE)['operator_token']),
            'Existing management credential cannot be replaced by admin fixture')
    initial = await unknown_observation(webui, common, office, unknown)
    require(initial['unknown']['native'] == unknown['unknown_gui_verification']['native'],
            'Admin initial unknown rows differ from the verified GUI witness')
    selected = {'schema': 1, 'stage': 'installing', 'actor_id': unknown['users'][0]['id'],
        'managed_model_ids': list(ALIASES), 'known_model_id': ALIASES[0], 'before': before,
        'initial': initial, 'admin_fixture': {'source_sha256': source_hash(source)}, 'journal': []}
    write_private(path, selected)
    try:
        email, password = 'admin-unknown-' + secrets.token_hex(12) + '@example.com', 'Aa1!' + secrets.token_urlsafe(32)
        result = webui.ok('POST', '/api/v1/auths/add', token=common['admin']['token'],
            body={'name': 'Unknown usage budget administrator', 'email': email, 'password': password, 'role': 'admin'})
        selected['admin'] = account_from_response(result, email, password, 'admin')
        require(selected['admin']['id'] not in {a['id'] for a in actors}, 'Admin unknown identity collided')
        write_private(path, selected)
        unknown_admin_read_grants(webui, common, office, selected, before, path)
        async def guard():
            webui.session(common['admin'], 'admin'); webui.session(selected['admin'], 'admin')
            selected['journal'].append('native-initialization-before-write'); write_private(path, selected)
        async with ClientSession(trust_env=False) as session:
            client = BudgetAdminClient(session, PROXY_URL, read_private(OPERATOR_STATE)['operator_token'])
            own = await client.initialize_employee(selected['admin']['id'], ((ALIASES[0], UNKNOWN_ADMIN_CAP),),
                                                   UNKNOWN_ADMIN_CAP, gateway, before_write=guard)
            require(await client.read_employee(own.user_id, (ALIASES[0],)) == own, 'New admin native budget readback differs')
        selected['admin_fixture']['preset'] = install_resources(webui, unknown_view(common, selected), source,
            managed_model_ids=ALIASES, base_model_id=ALIASES[0])
        observed = await unknown_observation(webui, common, office, unknown, selected)
        require({k: v for k, v in observed.items() if k != 'own'} == initial,
                'Admin setup changed existing personal/service budgets or history')
        own = observed['own']['budget']
        require(own['user_id'] == selected['admin']['id'] and Decimal(own['max_budget']) == UNKNOWN_ADMIN_CAP
                and Decimal(own['spend']) == 0 and len(own['models']) == 1
                and own['models'][0]['model'] == ALIASES[0] and Decimal(own['models'][0]['max_budget']) == UNKNOWN_ADMIN_CAP,
                'New admin native budget differs from the known-only synthetic assignment')
        after = unknown_webui_state(webui, common, office, unknown)
        unknown_preserved(before, after, new_admin=selected['admin'], installing=True)
        selected.update(protected=after, observation=observed, stage='setup_complete')
        receipt = unknown_snapshot(webui, common, office, unknown, selected, observed=observed)
        write_private(path, selected)
        write_private(handoff, {'schema': 1, 'admin': {k: selected['admin'][k] for k in ('id', 'email', 'password')},
            'model_id': MODEL_ID, 'tool_id': TOOL_ID, 'skill_id': SKILL_ID, 'actor_id': selected['actor_id'],
            'managed_model_ids': list(ALIASES), 'employee_ids': receipt['employee_ids']})
        return receipt | {'inference_issued': False}
    except Exception:
        selected['stage'] = 'setup_failed'; write_private(path, selected)
        raise


def unknown_snapshot(webui, common, office, unknown, selected, *, observed=None):
    from prove_unknown_usage_policy import ALIASES
    unknown_inputs(common, office, unknown)
    require(selected.get('stage') == 'setup_complete' and selected.get('actor_id') == unknown['users'][0]['id']
            and selected.get('managed_model_ids') == list(ALIASES) and selected.get('known_model_id') == ALIASES[0],
            'Admin unknown private identity/model handoff differs')
    webui.session(selected['admin'], 'admin')
    observed = asyncio.run(unknown_observation(webui, common, office, unknown, selected)) if observed is None else observed
    require(observed['unknown'] == selected['initial']['unknown'] and observed['old'] == selected['initial']['old'],
            'Admin unknown readback changed existing personal budgets/history')
    current = unknown_webui_state(webui, common, office, unknown)
    unknown_preserved(selected['protected'], current)
    actor = selected['actor_id']
    require(current['directory'][actor]['role'] == 'user'
            and set(ALIASES) <= set(current['catalogs'][actor])
            and all(not (set(catalog) & set(ALIASES)) for uid, catalog in current['catalogs'].items()
                    if uid != actor and current['directory'][uid]['role'] == 'user'), 'Prepared native employee roster differs')
    selected['observation'] = observed
    view = unknown_view(common, selected)
    view['users'] = [*common['users'], *office['users'], *unknown['users']]
    installed = installation(webui, view, managed_model_ids=ALIASES, base_model_id=ALIASES[0],
                             user_catalogs=current['catalogs'])
    return {'admin_id': selected['admin']['id'], 'actor_id': actor, 'employee_ids': [actor],
        'stage': 'setup_complete',
        'installation': installed, 'existing_personal_unchanged': True,
        'service_observed_separately': observed['service'] is not None,
        'native_acceptance': False}


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


def model_grant_changes(expected, actual):
    """Compare editable model state at the native grant meaning boundary.

    Stock0.12.2 replace_access_grants regenerates every grant row's id and
    created_at. Those row receipts and SQL ordering do not define access;
    principal_type/principal_id/permission do. Preserve every other model field.
    """
    changed = [field for field in expected if field != "access_grants" and actual.get(field) != expected[field]]
    observed_grants, requested_grants = grant_set(actual), grant_set(expected)
    if (observed_grants != requested_grants or len(actual["access_grants"]) != len(expected["access_grants"])
            or len(observed_grants) != len(actual["access_grants"])):
        changed.append("access_grants")
    return changed


def bootstrap_setup(webui, state, path, handoff):
    """Add only a WebUI employee after the original two-employee proof phase."""
    require("bootstrap_fixture" not in state and handoff is not None and not handoff.exists(),
            "Bootstrap setup requires a fresh private employee handoff")
    before = snapshot(webui, state)
    email = "newhire-" + secrets.token_hex(12) + "@example.com"
    password = "Aa1!" + secrets.token_urlsafe(32)
    response = webui.ok("POST", "/api/v1/auths/add", token=state["admin"]["token"], body={
        "name": "Proof new employee", "email": email, "password": password, "role": "user"})
    account = account_from_response(response, email, password, "user")
    require(account["id"] not in {entry["id"] for entry in [*state["users"], state["admin"], state["role_probe_control"]]},
            "Bootstrap employee identity duplicates the existing fixture")
    # Persist the native identity before changing grants; no hidden signup retry.
    state["bootstrap_fixture"] = {"stage": "installing", "employee": account,
        "original_staff": {key: before[key] for key in ("users", "keys")},
        "original_positive_request_ids": sorted(row["request_id"] for row in before["attributed_spend_logs"])}
    write_private(path, state)
    for model in MODELS:
        expected = model_body(webui.model(state["admin"]["token"], model))
        expected["access_grants"].append({"principal_type": "user", "principal_id": account["id"], "permission": "read"})
        webui.ok("POST", "/api/v1/models/model/update", token=state["admin"]["token"], body=expected)
        changed = model_grant_changes(expected, model_body(webui.model(state["admin"]["token"], model)))
        require(not changed, "Bootstrap model grant changed unrelated native model fields: " + ",".join(changed))
    webui.catalog(account)
    observed = asyncio.run(bootstrap_inspection(state))
    require(observed["kind"] == "absent", "Fresh WebUI employee already has a native budget identity")
    state["bootstrap_fixture"]["stage"] = "setup_complete"
    write_private(path, state)
    write_private(handoff, {"schema": 1, "user": {key: account[key] for key in ("id", "email", "password")},
                            "model_id": MODEL_ID})


async def bootstrap_inspection(state):
    employee = state["bootstrap_fixture"]["employee"]
    async with ClientSession(trust_env=False) as session:
        client = BudgetAdminClient(session, PROXY_URL, read_private(OPERATOR_STATE)["operator_token"])
        inspection = await client.inspect_employee(employee["id"], tuple(MODELS))
    result = {"user_id": employee["id"], "kind": inspection.kind, "code": inspection.code}
    if inspection.employee_budget is not None:
        result.update(normalize([inspection.employee_budget]))
    return result


def bootstrap_snapshot(webui, state):
    fixture = state.get("bootstrap_fixture")
    require(isinstance(fixture, dict) and fixture.get("stage") == "setup_complete",
            "Bootstrap WebUI employee setup is incomplete")
    result = snapshot(webui, state)
    require({key: result[key] for key in ("users", "keys")} == fixture["original_staff"],
            "Bootstrap phase changed existing employee caps/spend/reset/identities")
    result["bootstrap"] = asyncio.run(bootstrap_inspection(state))
    expanded = {**state, "users": [*state["users"], fixture["employee"]]}
    rows, unqualified = positive_logs(native_client(state), expanded)
    result["attributed_spend_logs"], result["unqualified_zero_row_count"] = rows, unqualified
    result["baseline_positive_request_ids"] = fixture["original_positive_request_ids"]
    result["existing_employee_native_state_unchanged"] = True
    config = webui.ok("GET", "/api/v1/functions/id/" + FILTER_ID + "/valves", token=state["admin"]["token"])
    result["default_template"] = copy.deepcopy(config.get("default_budget_template"))
    result["employee_function_valves_get_status"] = denied_status(webui, "GET",
        "/api/v1/functions/id/" + FILTER_ID + "/valves", fixture["employee"]["token"])
    return result


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
                and error.get("type") == "budget_exceeded",
                "Zero-cap native admin key did not yield the expected native key budget denial")
        message = expected_budget_message(error, scope="key")
        expect(limited)
        result.update(zero_cap_readback=True, denial_http_status=status, denial_type="budget_exceeded",
                      budget_message=message, friendly_budget_feedback=True,
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


def public_prices(state, *, restore=False):
    """Change only the existing disposable public catalog, never native spend."""
    require(os.environ.get('LITELLM_MODEL_COST_MAP_URL') == 'http://provider:8000/__proof/catalog'
            and os.environ.get('LITELLM_LOCAL_MODEL_COST_MAP', '').lower() == 'false',
            'Public price observation requires the isolated synthetic catalog')
    native = native_client(state)
    before = read_states(state)
    old_rows, old_zero = positive_logs(native, state)
    variant = 'S1' if restore else 'S2'
    request = Request('http://provider:8000/__proof/catalog/control', method='POST',
        data=json.dumps({'variant': variant}).encode(), headers={'Content-Type': 'application/json'})
    with native.opener.open(request, timeout=5) as response:
        require(response.status == 200, 'Synthetic catalog selection failed')
        response.read(8192)
    synced = native.ok('POST', '/reload/model_cost_map', body={})
    source = native.ok('GET', '/model/cost_map/source')
    require(source.get('source') == 'remote' and source.get('url') == 'http://provider:8000/__proof/catalog'
            and isinstance(source.get('source_revision'), str), 'Native public source differs')
    info = native.ok('GET', '/model/info')['data']
    observed = {}
    for wire in MODELS:
        rows = [r for r in info if r.get('model_name') == wire]
        require(len(rows) == 1, 'Public rate lookup is ambiguous')
        rates = rows[0]['model_info']
        factor = Decimal(1 if restore or wire == MODELS[1] else 2)
        require(amount(rates.get('input_cost_per_token')) == Decimal('.01') * factor
                and amount(rates.get('output_cost_per_token')) == Decimal('.02') * factor,
                'Native applied public rates differ')
        observed[wire] = {k: str(rates[k]) for k in ('input_cost_per_token', 'output_cost_per_token')}
    if restore:
        native.ok('DELETE', '/schedule/model_cost_map_reload')
    else:
        native.ok('POST', '/schedule/model_cost_map_reload', query={'hours': 1}, body={})
    scheduled = native.ok('GET', '/schedule/model_cost_map_reload/status')
    require(scheduled.get('scheduled') is (not restore), 'Native price schedule readback differs')
    after_rows, after_zero = positive_logs(native, state)
    require(read_states(state) == before and after_rows == old_rows and after_zero == old_zero,
            'Public catalog reload rewrote native financial history')
    return {'variant': variant, 'applied_rates': observed, 'source_revision': source['source_revision'],
            'loaded_at': source.get('loaded_at'), 'scheduled': scheduled['scheduled'],
            'financial_history_unchanged': True, 'inference_calls': 0}


async def provider_refusal_recovery(state, session, client, user_id, created, secret):
    """Two synthetic calls, with status derived from actual durable native rows."""
    from employee_budget_cost_readback import read_admin_overview, _financial_refusal
    from litellm_auth import PROVENANCE_FIELD, TASK_HEADER, USER_ID_HEADER
    from provenance import decode_call, encode_call
    import httpx
    import openai

    require(os.environ.get('LITELLM_MODEL_COST_MAP_URL') == 'http://provider:8000/__proof/catalog',
            'Provider account proof requires the isolated synthetic catalog')
    native = native_client(state)
    native.timeout = 10
    def provider(path, body=None):
        request = Request('http://provider:8000' + path, method='GET' if body is None else 'POST',
            data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
        with native.opener.open(request, timeout=5) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            require(response.status == 200 and len(raw) <= 2 * 1024 * 1024, 'Provider proof read/control failed')
            return json.loads(raw)
    def control(status):
        provider('/__proof/control', {'response_status': status, 'admin_mode': False, 'tool_round': False})
    def diagnostic(expected, since, last):
        """Bounded safe schema evidence, including rows lacking deployment ids."""
        result = {'expected': expected, 'last_projection': last, 'rows': []}
        try:
            native.timeout = 5
            status, payload, _ = native.request('GET', '/spend/logs/v2', query={'user_id': user_id,
                'page': 1, 'page_size': 100, 'start_date': since.strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')})
            data = payload.get('data', []) if status == 200 else []
            result.update(spend_http_status=status, returned_rows=len(data) if isinstance(data, list) else None)
            for row in data[:3] if isinstance(data, list) else []:
                if not isinstance(row, dict) or row.get('user') != user_id:
                    continue
                metadata = row.get('metadata') if isinstance(row.get('metadata'), dict) else {}
                info = metadata.get('error_information')
                info = info if isinstance(info, dict) else {}
                message = info.get('error_message')
                message = message if isinstance(message, str) else ''
                error_class, error_code, model_id = info.get('error_class'), str(info.get('error_code', '')), row.get('model_id')
                cache = row.get('cache_hit')
                result['rows'].append({'status': row.get('status') if row.get('status') in ('success', 'failure') else 'other',
                    'model_id': model_id if model_id in ('goal584-deployment-a', 'goal584-deployment-b') else ('other' if model_id else 'missing'),
                    'cache_hit': cache if cache in (True, False, 'True', 'False', 'true', 'false', '', None) else 'other',
                    'error_class': error_class if isinstance(error_class, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', error_class) else None,
                    'error_code': error_code if re.fullmatch(r'[0-9]{3}', error_code) else None,
                    'provider_present': bool(info.get('llm_provider')), 'recognized_financial_marker': _financial_refusal(metadata),
                    'message_chars': min(len(message), 32769), 'python_dict_repr': "{'" in message,
                    'json_object_repr': '{"' in message, 'native_router_suffix': '\n\nLiteLLM: model group ' in message})
            status, source, _ = native.request('GET', '/model/cost_map/source')
            result['source'] = {'http_status': status, 'kind': source.get('source') if source.get('source') in ('local', 'remote') else 'other',
                'url': 'http://provider:8000/__proof/catalog' if source.get('url') == 'http://provider:8000/__proof/catalog' else 'other'}
        except Exception as error:
            result['capture_error_type'] = type(error).__name__
        finally:
            native.timeout = 10
        return result
    async def observed(expected, since):
        last = {}
        try:
            async with asyncio.timeout(20):
                while True:
                    overview = await read_admin_overview(session, base_url=PROXY_URL,
                        admin_key=read_private(OPERATOR_STATE)['operator_token'], models={MODELS[1]: 'Synthetic B'}, configsnapshots={})
                    accounts = overview.get('accounts', [])
                    require(len(accounts) == 1, 'Native provider account projection is ambiguous')
                    account = accounts[0]
                    timestamp = account.get('event_at')
                    stamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else None
                    actual = await client.read_employee(user_id, tuple(MODELS))
                    last = {'status': account.get('status'), 'event_at': timestamp, 'complete': overview.get('complete'),
                            'native_user_spend_usd': str(actual.spend), 'native_model_spend_usd': str(actual.models[1].spend)}
                    expected_spend = Decimal('.20') if expected == 'success' else Decimal(0)
                    if (account.get('status') == expected and stamp is not None and stamp >= since
                            and actual.spend == expected_spend and actual.models[1].spend == expected_spend):
                        return {'status': expected, 'event_at': timestamp, 'account_id': account['id'],
                                'native_user_and_model_spend_usd': str(expected_spend)}
                    await asyncio.sleep(.25)
        except asyncio.TimeoutError:
            failure = ProofError('Actual native provider status/usage/counters remain unconfirmed: ' + expected)
            failure.provider_observation_diagnostic = diagnostic(expected, since, last)
            raise failure from None
    async def stream_call():
        """Reuse the installed SDK SSE owner; no retries or alternate routes."""
        answer = str(uuid4())
        capsule = encode_call(secret, user_id=user_id, chat_id=proof_chat, answer_id=answer,
                              root_chat_id=proof_chat, root_answer_id=answer, model=MODELS[1])
        claims = decode_call(capsule, secret, user_id=user_id, model=MODELS[1])
        evidence = {'http_status': None, 'usage': None, 'response_id': None, 'chunks': 0, 'signed_call_id': claims['jti']}
        try:
            async with asyncio.timeout(15):
                async with httpx.AsyncClient(trust_env=False, timeout=10) as http_client:
                    async with openai.AsyncOpenAI(api_key=secret, base_url=PROXY_URL.rstrip('/') + '/v1',
                            max_retries=0, http_client=http_client) as sdk:
                        stream = await sdk.chat.completions.create(**body,
                            extra_headers={USER_ID_HEADER: user_id, TASK_HEADER: ''},
                            extra_body={'litellm_metadata': {PROVENANCE_FIELD: capsule}})
                        evidence['http_status'] = stream.response.status_code
                        async with stream:
                            async for chunk in stream:
                                evidence['chunks'] += 1
                                require(evidence['chunks'] <= 32 and isinstance(chunk.id, str) and bool(chunk.id),
                                        'Native provider stream exceeded its bounded response shape')
                                require(evidence['response_id'] in (None, chunk.id), 'Native provider stream changed response ids')
                                evidence['response_id'] = chunk.id
                                if chunk.usage is not None:
                                    evidence['usage'] = {field: getattr(chunk.usage, field) for field in
                                        ('prompt_tokens', 'completion_tokens', 'total_tokens')}
        except openai.APIError as error:
            code = getattr(error, 'code', None)
            evidence.update(http_status=getattr(error, 'status_code', None), error_class=type(error).__name__,
                error_code=code if code in ('402', '503', 'usage_unavailable', 'budget_exceeded', 402, 503) else None,
                usage_unavailable='Usage unavailable' in str(error))
        except asyncio.TimeoutError:
            evidence.update(error_class='TimeoutError')
        return evidence
    await client.set_model_cap(created.key_hash, Decimal('.60'))
    proof_chat = str(uuid4())  # API-only lineage; no WebUI chat is claimed.
    before = len(provider('/__proof/requests')['requests'])
    body = {'model': MODELS[1], 'messages': [{'role': 'user', 'content': 'Hi'}], 'stream': True,
            'stream_options': {'include_usage': True}, 'max_tokens': 5}
    try:
        control(402)
        sent = datetime.now(timezone.utc)
        refused_stream = await stream_call()
        require(refused_stream['http_status'] == 402, 'Explicit synthetic payment refusal did not reach the native API')
        refusal = await observed('financial_refusal', sent)
        control(200)
        sent = datetime.now(timezone.utc)
        recovered_stream = await stream_call()
        if (recovered_stream['http_status'] != 200 or recovered_stream['usage'] !=
                {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}):
            failure = ProofError('Synthetic recovery did not return actual native streamed paid usage')
            last = {'status': refusal['status'], 'event_at': refusal['event_at']}
            try:
                actual = await client.read_employee(user_id, tuple(MODELS))
                last.update(native_user_spend_usd=str(actual.spend), native_model_spend_usd=str(actual.models[1].spend))
            except BudgetAdminError as error:
                last['counter_read_error'] = error.code
            failure.provider_observation_diagnostic = diagnostic('success', sent, last)
            failure.provider_observation_diagnostic['stream'] = {key: value for key, value in recovered_stream.items()
                                                               if key != 'response_id'}
            failure.provider_observation_diagnostic['stream']['response_id_seen'] = bool(recovered_stream['response_id'])
            raise failure
        recovery = await observed('success', sent)
        require(recovery['account_id'] == refusal['account_id'], 'Recovery switched provider accounts')
        require(refused_stream['signed_call_id'] != recovered_stream['signed_call_id'], 'Signed provider calls reused a nonce')
        calls = provider('/__proof/requests')['requests'][before:]
        require(len(calls) == 2 and [row['lifecycle']['response_status'] for row in calls] == [402, 200]
                and calls[0].get('usage') is None and calls[1].get('usage') == recovered_stream['usage']
                and calls[1].get('id') == recovered_stream['response_id'],
                'Native provider proof added calls or reused cached/fallback success')
        return {'refusal': refusal, 'recovery': recovery, 'inference_calls': 2, 'physical_calls': 2,
                'synthetic_paid_cost_usd': '0.20', 'separate_after_browser_reconciliation': True,
                'transport': 'native_chat_completions_stream', 'streamed_usage_verified': True,
                'signed_personal_scope': True, 'distinct_call_nonces': True,
                'coverage': 'signed native API and durable account projection; synthetic UUID lineage, no WebUI chat'}
    finally:
        control(200)


async def model_expansion(state):
    """Native pending -> zero assignment, then one synthetic account recovery."""
    before = await actual_states(state)
    user_id = str(uuid5(UUID(state['admin']['id']), 'goal584-model-expansion'))
    key = read_private(OPERATOR_STATE)['operator_token']
    secret = os.environ.get('OWUI_BUDGET_GATEWAY_SECRET', '')
    async def before_write():
        require(await actual_states(state) == before, 'Model expansion changed an existing employee')
    async with ClientSession(trust_env=False) as session:
        client = BudgetAdminClient(session, PROXY_URL, key)
        initial = await client.initialize_employee(user_id, ((MODELS[0], Decimal(1)),), Decimal(1),
                                                    secret, before_write=before_write)
        pending = await client.read_employee(user_id, tuple(MODELS))
        require(pending.max_budget == 1 and pending.spend == 0 and pending.models[0] == initial.models[0]
                and pending.models[1].pending and pending.models[1].max_budget is None
                and pending.models[1].spend is None, 'New model read projection changed native values')
        created = await client.create_model_assignment(user_id, MODELS[1], secret, before_write=before_write)
        actual = await client.read_employee(user_id, tuple(MODELS))
        require(actual.max_budget == initial.max_budget and actual.spend == initial.spend
                and actual.budget_reset_at == initial.budget_reset_at
                and actual.models[0] == initial.models[0] and actual.models[1] == created
                and created.max_budget == 0 and created.spend == 0 and not created.pending,
                'New native assignment did not preserve existing budget state')
        account_proof = await provider_refusal_recovery(state, session, client, user_id, created, secret)
    require(await actual_states(state) == before, 'Expansion changed primary fixture finances')
    return {'pending_model_visible_without_native_amount': True, 'created_native_cap_usd': '0',
            'existing_assignment_and_user_unchanged': True, 'primary_fixture_unchanged': True,
            'inference_calls': 2, 'provider_account_observations': account_proof}


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
    parser.add_argument("--phase", required=True, choices=("setup", "snapshot", "hash-probe", "native-probe", "role-probe",
                                                          "bootstrap-setup", "bootstrap-snapshot", "unknown-setup", "unknown-snapshot",
                                                          "public-prices-up", "public-prices-restore", "model-expansion"))
    parser.add_argument("--private-state", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--browser-accounts", type=Path)
    parser.add_argument('--office-state', type=Path)
    parser.add_argument('--unknown-state', type=Path)
    parser.add_argument('--admin-unknown-state', type=Path)
    args = parser.parse_args()
    receipt = {"schema": 1, "proof": "goal584-native-admin-provisioning", "phase": args.phase,
               "passed": False, "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "not_qualified": ["admin_GUI_in_this_script", "production", "paid_provider"]}
    state, selected, credentials, output_valid = {}, {}, [], False
    try:
        require(args.private_state.resolve() == STATE.resolve(), "Admin provisioning requires the fixed private state")
        paths = [args.private_state.resolve(), args.receipt.resolve(), OPERATOR_STATE.resolve()]
        if args.browser_accounts:
            paths.append(args.browser_accounts.resolve())
        unknown_phase = args.phase in ('unknown-setup', 'unknown-snapshot')
        if unknown_phase:
            require(args.office_state == Path('/proof-private/office-state.private.json')
                    and args.unknown_state == Path('/proof-private/unknown-usage-gui-state.private.json')
                    and args.admin_unknown_state == UNKNOWN_ADMIN_STATE,
                    'Admin unknown provisioning requires fixed separate private inputs')
            require(args.browser_accounts == UNKNOWN_ADMIN_ACCOUNTS if args.phase == 'unknown-setup'
                    else args.browser_accounts is None, 'Admin unknown browser handoff is setup-only and fixed')
            paths += [args.office_state.resolve(), args.unknown_state.resolve(), args.admin_unknown_state.resolve()]
        else:
            require(args.office_state is None and args.unknown_state is None and args.admin_unknown_state is None,
                    'Unknown fixture inputs are opt-in only')
        require(len(set(paths)) == len(paths), "Private state/handoff and receipt paths must be separate")
        output_valid = True
        require(args.browser_accounts is None or args.phase in ("setup", "bootstrap-setup", 'unknown-setup'), "Browser handoff is setup-only")
        state = read_private(args.private_state)
        credentials.append(read_private(OPERATOR_STATE)["operator_token"])
        require(state.get("stage") == "setup_complete" and len(state.get("users", [])) == 2
                and len(state.get("native_keys", [])) == 4
                and state.get("cost_display", {}).get("stage") == "setup_complete", "Native base/cost setup is incomplete")
        webui = WebUI()
        require(webui.ok("GET", "/api/version").get("version") == "0.12.2", "WebUI version differs from fixture")
        webui.session(state["admin"], "admin")
        if unknown_phase:
            office, unknown = read_private(args.office_state), read_private(args.unknown_state)
            credentials += secret_values(office) + secret_values(unknown)
            if args.phase == 'unknown-setup':
                receipt.update(asyncio.run(unknown_setup(webui, state, office, unknown, args.admin_unknown_state, args.browser_accounts)))
                selected = read_private(args.admin_unknown_state)
            else:
                selected = read_private(args.admin_unknown_state)
                receipt.update(unknown_snapshot(webui, state, office, unknown, selected))
                write_private(args.admin_unknown_state, selected)
        elif args.phase == "setup":
            setup(webui, state, args.private_state)
            if args.browser_accounts:
                require(not args.browser_accounts.exists(), "Browser admin handoff must be a new private file")
                write_private(args.browser_accounts, {"schema": 1, "admin": {
                    field: state["admin"][field] for field in ("id", "email", "password")},
                    "model_id": MODEL_ID, "tool_id": TOOL_ID, "skill_id": SKILL_ID})
        if not unknown_phase:
            require(state.get("admin_fixture", {}).get("stage") == "setup_complete", "Admin installation is incomplete")
        if args.phase in ("hash-probe", "native-probe"):
            receipt["native_probe"] = native_probe(state, deny=args.phase == "native-probe")
        elif args.phase == "role-probe":
            receipt["role_probe"] = role_probe(webui, state, args.private_state)
        elif args.phase in ('public-prices-up', 'public-prices-restore'):
            receipt['public_prices'] = public_prices(state, restore=args.phase.endswith('restore'))
        elif args.phase == 'model-expansion':
            receipt['model_expansion'] = asyncio.run(model_expansion(state))
        elif args.phase == "bootstrap-setup":
            bootstrap_setup(webui, state, args.private_state, args.browser_accounts)
        if not unknown_phase:
            receipt.update(bootstrap_snapshot(webui, state) if args.phase.startswith("bootstrap-") else snapshot(webui, state))
        receipt["passed"] = True
    except ProofError as error:
        receipt["failure"] = str(error)
        if args.phase == 'model-expansion' and isinstance(getattr(error, 'provider_observation_diagnostic', None), dict):
            receipt['provider_observation_diagnostic'] = error.provider_observation_diagnostic
    except BudgetAdminError as error:
        receipt["failure"] = "Native admin client: " + error.code
    except Exception as error:
        receipt["failure"] = "Unexpected admin fixture error: " + type(error).__name__
    receipt["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    rendered = json.dumps(receipt, indent=2, allow_nan=False)
    credentials += secret_values(state) + [entry["key"] for entry in state.get("admin_budgetnative_keys", [])]
    credentials += [state.get("role_probe_control", {}).get(field) for field in ("password", "token")]
    credentials += [state.get("bootstrap_fixture", {}).get("employee", {}).get(field) for field in ("password", "token")]
    credentials += secret_values(selected)
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
