"""One-shot setup for a later ordinary-user unknown-cost GUI proof.

Call only after the host admits the existing six-service Office/C72 API stand.
Native WebUI owns actor/config/models; BudgetAdminClient owns initialization.
No inference, settings changes, retries, reset, Filter install or cost arithmetic.
"""
from __future__ import annotations

import copy
from dataclasses import asdict
from decimal import Decimal
import json
import os
from pathlib import Path
import secrets
from uuid import uuid4
from urllib.parse import urlencode

from aiohttp import ClientSession
from employee_budget_admin_client import BudgetAdminClient
from provision_cost_display import (
    FILTER_ID, FILTER_SOURCE, add_model_meta, grant_set, model_body,
    reader_readback, source_hash,
)
import provision_webui as fixture
from prove_native_budgets import ProofError, require
from prove_service_tasks import response
from prove_unknown_usage_policy import ALIASES, routing


async def setup_unknown_usage_gui(webui, common: dict, office: dict, path: Path) -> dict:
    """Create one fresh user and three private WorkspaceModels; return safe IDs.

    The separate 0600 handoff retains credentials and before/after observations.
    A failed handoff is deliberately not resumable: inspect partial state first.
    AdminClient has a before-write hook only. Its prior POST is marked confirmed
    only after its own readback reaches the next hook or the final readback.
    """
    require(common.get('stage') == office.get('stage') == 'setup_complete'
            and not path.exists(), 'Unknown GUI setup requires a fresh separate handoff')
    admin = common['admin']
    require(office.get('admin') == admin and len(office.get('users', [])) == 1,
            'Unknown GUI setup requires the existing Office actor')
    actors = [admin, *common['users'], *office['users']]
    if common.get('role_probe_control'): actors.append(common['role_probe_control'])
    require(len({a['id'] for a in actors}) == len(actors), 'Unknown GUI existing actors collide')
    gateway = os.environ.get('OWUI_BUDGET_GATEWAY_SECRET', '')
    require(bool(gateway) and not any(c.isspace() for c in gateway), 'Unknown GUI gateway missing')
    require(webui.ok('GET', '/api/version').get('version') == '0.12.2', 'Unknown GUI WebUI version differs')
    native = fixture.native_client()
    route = routing(native)
    operator = fixture.read_private(fixture.OPERATOR_STATE)['operator_token']
    require(operator != gateway, 'Unknown GUI management/gateway authority collision')

    def get(route, token=None):
        return webui.ok('GET', route, token=admin['token'] if token is None else token)

    def catalog(account):
        webui.session(account, 'admin' if account is admin or account is common.get('role_probe_control') else 'user')
        rows = get('/api/models?refresh=true', account['token']).get('data')
        require(isinstance(rows, list) and all(isinstance(r, dict) and isinstance(r.get('id'), str) for r in rows)
                and len({r['id'] for r in rows}) == len(rows), 'Unknown GUI native catalog malformed')
        return {r['id']: r for r in rows}

    def functions():
        status, rows = response(webui, 'GET', '/api/v1/functions/export?include_valves=true', admin['token'])
        require(status == 200 and isinstance(rows, list) and all(isinstance(r, dict) and isinstance(r.get('id'), str) for r in rows)
                and len({r['id'] for r in rows}) == len(rows), 'Unknown GUI native Function export unavailable')
        return {r['id']: r for r in rows}

    old_catalogs = {a['id']: catalog(a) for a in actors}
    old_models = {mid: webui.model(admin['token'], mid) for mid, row in old_catalogs[admin['id']].items()
                  if (row.get('info') or {}).get('id') == mid}
    connections = get('/openai/config')
    urls, keys, configs = (connections.get(k) for k in ('OPENAI_API_BASE_URLS', 'OPENAI_API_KEYS', 'OPENAI_API_CONFIGS'))
    require(connections.get('ENABLE_OPENAI_API') is True and isinstance(urls, list) and isinstance(keys, list)
            and len(urls) == len(keys) > 0 and isinstance(configs, dict)
            and set(configs) == {str(i) for i in range(len(urls))}
            and all(isinstance(c, dict) and isinstance(c.get('model_ids'), list) for c in configs.values()),
            'Unknown GUI connection indices/model lists are not explicit')
    indices = [i for i, url in enumerate(urls) if url == 'http://proxy:4000/v1'
               and keys[i] == gateway and configs[str(i)].get('api_type') == 'responses']
    require(len(indices) == 1, 'Unknown GUI requires one existing Responses connection')
    index = indices[0]; config = configs[str(index)]
    require(config.get('enable') is True and config.get('auth_type') == 'bearer'
            and config.get('headers', {}).get(fixture.USER_ID_HEADER) == '{{USER_ID}}'
            and config.get('headers', {}).get(fixture.TASK_HEADER) == '{{TASK}}'
            and all(not (set(c['model_ids']) & set(ALIASES)) for c in configs.values()),
            'Unknown GUI existing Responses scope differs')
    for alias in ALIASES:
        require(response(webui, 'GET', '/api/v1/models/model?' + urlencode({'id': alias}), admin['token'])[0] == 404,
                'Unknown GUI WorkspaceModel exists or absence unavailable')
    before = {'connections': connections, 'catalogs': old_catalogs, 'models': old_models,
              'functions': functions(), 'tasks': get('/api/v1/tasks/config'),
              'chat_config': get('/api/v1/chats/config'), 'tool_servers': get('/api/v1/configs/tool_servers')}
    cost = get('/api/v1/functions/id/' + FILTER_ID)
    valves = get('/api/v1/functions/id/' + FILTER_ID + '/valves')
    require(cost.get('id') == FILTER_ID and cost.get('type') == 'filter' and cost.get('is_active') is True
            and cost.get('is_global') is True and (cost.get('meta') or {}).get('toggle') is False
            and source_hash(cost.get('content', '')) == source_hash(FILTER_SOURCE.read_text(encoding='utf8'))
            and valves.get('ledger_base_url') == 'http://proxy:4000'
            and valves.get('ledger_read_key') == common['cost_reader']['key'], 'Unknown GUI installed cost Filter differs')
    reader = reader_readback(native, common)
    handoff = {'schema': 1, 'stage': 'setup_in_progress', 'admin': copy.deepcopy(admin), 'users': [],
               'cost_reader': copy.deepcopy(common['cost_reader']),
               'unknown_gui_setup': {'before': before, 'journal': [], 'route_sha256': route, 'reader': reader}}
    expected_connections = copy.deepcopy(connections)
    actor = None

    def save(): fixture.write_private(path, handoff)

    def guard():
        webui.session(admin, 'admin')
        if actor is not None: webui.session(actor, 'user')
        require(routing(native) == route and get('/openai/config') == expected_connections
                and get('/api/v1/functions/id/' + FILTER_ID) == cost
                and get('/api/v1/functions/id/' + FILTER_ID + '/valves') == valves
                and get('/api/v1/tasks/config') == before['tasks'], 'Unknown GUI pre-write prerequisite changed')

    def journal(stage, body=None):
        guard()
        entry = {'stage': stage, 'body': copy.deepcopy(body), 'readback_confirmed': False}
        handoff['unknown_gui_setup']['journal'].append(entry); save()
        return entry

    def post(route, body):
        entry = journal(route, body)
        result = webui.ok('POST', route, token=admin['token'], body=body)
        entry.update(returned=True, response=result); save()
        return result, entry

    try:
        email, password = 'unknown-gui-' + uuid4().hex + '@example.com', 'Aa1!' + secrets.token_urlsafe(32)
        result, entry = post('/api/v1/auths/add', {'name': 'Unknown usage GUI employee', 'email': email,
                                               'password': password, 'role': 'user'})
        actor = fixture.account_from_response(result, email, password, 'user')
        require(actor['id'] not in {a['id'] for a in actors}, 'Unknown GUI new WebUI actor collided')
        handoff['users'] = [actor]; webui.session(actor, 'user'); entry['readback_confirmed'] = True; save()
        pending = None
        async def before_write():
            nonlocal pending
            if pending is not None: pending['readback_confirmed'] = True; save()
            pending = journal('native-budget-initialize-post', {'user_id': actor['id'], 'models': list(ALIASES),
                                                               'model_cap': '2', 'total_cap': '6'})
        async with ClientSession(trust_env=False) as session:
            client = BudgetAdminClient(session, fixture.PROXY_URL, operator)
            budget = await client.initialize_employee(actor['id'], tuple((a, Decimal(2)) for a in ALIASES),
                                                       Decimal(6), gateway, before_write=before_write)
            require(await client.read_employee(actor['id'], ALIASES) == budget, 'Unknown GUI native budget readback changed')
        pending['readback_confirmed'] = True
        handoff['unknown_gui_setup']['budget'] = json.loads(json.dumps(asdict(budget), default=str)); save()
        requested = copy.deepcopy(connections)
        requested['OPENAI_API_CONFIGS'][str(index)]['model_ids'] += list(ALIASES)
        _, entry = post('/openai/config/update', requested)
        expected_connections = requested
        require(get('/openai/config') == requested, 'Unknown GUI connection append readback differs')
        entry['readback_confirmed'] = True; save()
        models = {}
        for alias in ALIASES:
            body = {'id': alias, 'name': alias, 'base_model_id': None, 'is_active': True,
                    'params': {'max_tokens': 16, 'custom_params': {'store': False}},
                    'meta': {'capabilities': {'builtin_tools': False}},
                    'access_grants': [{'principal_type': 'user', 'principal_id': actor['id'], 'permission': 'read'}]}
            _, entry = post('/api/v1/models/create', body)
            record = webui.model(admin['token'], alias)
            editable = model_body(record)
            require(all(editable[k] == body[k] for k in ('id', 'name', 'base_model_id', 'is_active', 'params'))
                    and editable['meta'].get('capabilities') == body['meta']['capabilities']
                    and not any(editable['meta'].get(k) for k in ('toolIds', 'skillIds', 'actionIds', 'knowledge', 'filterIds'))
                    and record.get('user_id') == admin['id']
                    and len(record['access_grants']) == 1 and grant_set(record) == {('user', actor['id'], 'read')},
                    'Unknown GUI new model/actor ACL readback differs')
            entry['readback_confirmed'] = True; save()
            entry = journal('attach-existing-budget-filter', {'model': alias, 'filter': FILTER_ID})
            models[alias] = add_model_meta(webui, handoff, alias, 'filterIds', FILTER_ID)
            expected_meta = copy.deepcopy(editable['meta']); expected_meta['filterIds'] = [FILTER_ID]
            require(models[alias]['meta'] == expected_meta,
                    'Unknown GUI unexpected model tools/system profile')
            entry['readback_confirmed'] = True; save()
        guard()
        require(functions() == before['functions'] and get('/api/v1/chats/config') == before['chat_config']
                and get('/api/v1/configs/tool_servers') == before['tool_servers']
                and all(webui.model(admin['token'], mid) == row for mid, row in old_models.items()),
                'Unknown GUI changed existing models/Functions/Office configuration')
        for account in actors:
            after = catalog(account)
            require(all(after.get(mid) == row for mid, row in old_catalogs[account['id']].items()),
                    'Unknown GUI changed an existing actor catalog/model/read grant')
            if account is not admin and account is not common.get('role_probe_control'):
                require(not set(ALIASES) & set(after), 'Unknown GUI aliases escaped new actor ACL')
        visible = catalog(actor)
        require(all(a in visible and visible[a].get('owned_by') == 'openai' and not visible[a].get('pipe')
                    and visible[a].get('urlIdx') == index
                    and FILTER_ID in ((visible[a].get('info') or {}).get('meta') or {}).get('filterIds', []) for a in ALIASES),
                'Unknown GUI actor route/Filter catalog readback differs')
        require(reader_readback(native, common) == reader, 'Unknown GUI changed existing viewer')
        handoff['unknown_gui_setup'].update(models=models, connections=requested, actor_catalog=visible)
        handoff['stage'] = 'setup_complete'; save()
    except Exception as error:
        handoff.update(stage='setup_failed', private_error={'type': type(error).__name__, 'message': str(error)})
        save()
        raise ProofError('Unknown GUI setup failed; inspect private handoff; no automatic retry') from None
    return {'status': 'readback_ready', 'actor_id': actor['id'], 'model_ids': list(ALIASES),
            'inference_issued': False, 'settings_configured': False, 'browser_accepted': False,
            'unknown_cost_finality': False}
