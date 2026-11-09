"""Finite native collector for the six ordinary GUI Sends; never issues inference.

Host Playwright stays outside the proxy. All nonces/scopes below are read from
native rows; GUI ACK200 is never presented as a native authentication401.
"""
from __future__ import annotations
import argparse
import asyncio
import base64
import copy
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import re
import sys
from pathlib import Path
from uuid import UUID

import prove_unknown_usage_policy as P
from unknown_usage_gui_fixture import setup_unknown_usage_gui
from provision_cost_display import FILTER_ID, reader_readback

PRIVATE = Path('/proof-private')
STATE = PRIVATE / 'unknown-usage-gui-state.private.json'
PACKET = PRIVATE / 'unknown-usage-browser.private.json'
COMMON = PRIVATE / 'webui-state.private.json'
OFFICE = PRIVATE / 'office-state.private.json'
ADMIN_SETUP = PRIVATE / 'admin-unknown-state.private.json'
ADMIN_STATE = PRIVATE / 'admin-unknown-readback.private.json'
ADMIN_BROWSER = PRIVATE / 'admin-unknown-browser.private.json'
ADMIN_PROOF = 'goal584-admin-unknown-presence'
PROOF = 'goal584-unknown-usage-gui'
UNKNOWN = 'Расход неизвестен. Обратитесь к администратору.'
KNOWN = 'Ответ: $0.166 · Чат: $0.166'
BLOCKED = 'Authentication Error, Доступ заблокирован. Обратитесь к администратору.'
CHAT_NOT_FOUND = "We could not find what you're looking for :/"
ORDER = (0, 1, 1, 2, 2, 0)
DENIED = (2, 4)
# Actual imports, not host browser modules; host adds these readonly mounts.
EXTRA_SOURCES = {n: Path(__file__).with_name(n) for n in
                 ('prove_unknown_usage_gui.py', 'unknown_usage_gui_fixture.py', 'provision_cost_display.py')}
require = P.require
wire_json = lambda value: json.loads(json.dumps(value, default=str, allow_nan=False))

# Explicit public diagnostics only. Unknown/new codes stay private until reviewed.
ADMIN_PUBLIC_PROOF_CODES = frozenset({
    'admin_unknown_background_active', 'admin_unknown_baseline_changed', 'admin_unknown_baseline_exists',
    'admin_unknown_browser_packet', 'admin_unknown_capture_capacity', 'admin_unknown_cost_snapshot',
    'admin_unknown_dispatch_count', 'admin_unknown_dispatch_model', 'admin_unknown_dispatch_partition',
    'admin_unknown_duplicate_dispatch', 'admin_unknown_fresh_payer', 'admin_unknown_native_cardinality',
    'admin_unknown_native_counter', 'admin_unknown_native_preservation', 'admin_unknown_native_tool_output',
    'admin_unknown_personal_scope', 'admin_unknown_primary_provider', 'admin_unknown_prior_context',
    'admin_unknown_render_counter', 'admin_unknown_render_model_counter', 'admin_unknown_saved_binding',
    'admin_unknown_saved_embed', 'admin_unknown_saved_parent', 'admin_unknown_saved_rows', 'admin_unknown_saved_tool',
    'admin_unknown_service_assignment', 'admin_unknown_terminal_context', 'admin_unknown_tool_context_binding',
    'admin_unknown_tool_context_count', 'admin_unknown_tool_result_binding',
    'office_delegation_auth_context', 'office_delegation_provider_join',
    'office_continuation_service_context', 'office_saved_followups', 'office_service_wire',
    'office_buffered_client_stream', 'office_buffered_profile', 'office_provider_transport',
    'office_service_caps_changed', 'office_service_dispatch_binding', 'office_service_dispatch_observation',
    'office_service_duplicate_row', 'office_service_native_spend_delta', 'office_service_old_row_changed',
    'office_service_owner', 'office_service_rates', 'office_service_raw_rows', 'office_service_row_count',
    'office_service_row_identity_usage_cost', 'office_service_tariff_source',
})
ADMIN_PUBLIC_COST_CODES = frozenset({
    'accounting_unavailable', 'duplicate_request_id', 'foreign_answer', 'foreign_scope', 'incomplete_pagination',
    'invalid_attribution', 'invalid_configuration', 'invalid_observation_range', 'invalid_pagination',
    'invalid_row', 'invalid_scope', 'invalid_spend', 'invalid_usage', 'response_too_large',
    'spend_api_unavailable', 'usage_unavailable',
})
ADMIN_PUBLIC_BUDGET_CODES = frozenset({
    'duplicate_assignment', 'duplicate_key', 'foreign_assignment', 'incomplete_pagination', 'invalid_assignment',
    'invalid_cap', 'invalid_configuration', 'invalid_employee', 'invalid_key_hash', 'invalid_models',
    'invalid_native_amount', 'invalid_native_response', 'invalid_user_id', 'missing_assignment',
    'native_response_too_large', 'native_transport', 'service_configuration_changed', 'unsupported_assignment',
    'native_http_400', 'native_http_401', 'native_http_403', 'native_http_404', 'native_http_409',
    'native_http_422', 'native_http_429', 'native_http_500', 'native_http_502', 'native_http_503', 'native_http_504',
})


def admin_failure_fields(error):
    """Represent a known failure; never authorize acceptance or expose raw text."""
    code = None
    if isinstance(error, P.CostReadError):
        category, allowed = 'CostReadError', ADMIN_PUBLIC_COST_CODES
    elif isinstance(error, P.BudgetAdminError):
        category, allowed = 'BudgetAdminError', ADMIN_PUBLIC_BUDGET_CODES
    else:
        category = {P.ProofError: 'ProofError', AssertionError: 'AssertionError', ValueError: 'ValueError',
                    TypeError: 'TypeError', KeyError: 'KeyError', TimeoutError: 'TimeoutError'}.get(type(error), 'unavailable')
        allowed = ADMIN_PUBLIC_PROOF_CODES
        if type(error) in (P.ProofError, AssertionError) and len(error.args) == 1:
            code = error.args[0]
    if category in ('CostReadError', 'BudgetAdminError'):
        try:
            code = error.code
        except Exception:
            pass
    result = {'failure_code': code if type(code) is str and code in allowed else 'unavailable',
              'error_class': category}
    if type(error) is P.ProofError and result['failure_code'] == 'admin_unknown_dispatch_count':
        observed = getattr(error, '_admin_unknown_dispatch', None)
        if (type(observed) is dict
                and set(observed) == {'physical_requests', 'captured_requests', 'synthetic', 'control_unchanged'}
                and all(type(observed[key]) is int and 0 <= observed[key] <= 4096
                        for key in ('physical_requests', 'captured_requests'))
                and all(type(observed[key]) is bool for key in ('synthetic', 'control_unchanged'))):
            result['dispatch_observation'] = {
                'physical_requests': observed['physical_requests'],
                'captured_requests': observed['captured_requests'],
                'synthetic': observed['synthetic'],
                'control_unchanged': observed['control_unchanged'],
            }
    return result


def canonical(value):
    try: valid = isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError): valid = False
    require(valid, 'unknown_gui_identity')
    return value


def window(native, start):
    try: value = datetime.fromisoformat(start)
    except (ValueError, TypeError): raise P.ProofError('unknown_gui_query_window') from None
    require(value.tzinfo is not None and 0 <= (datetime.now(timezone.utc) - value).total_seconds() <= 900,
            'unknown_gui_query_window')
    native.started_at = value


def packet_calls(packet, actor, foreign_actor):
    require(packet.get('schema') == 1 and packet.get('actor_id') == actor and 'failure' not in packet
            and len(packet.get('calls', [])) == 6, 'unknown_gui_packet')
    result = []; seen = set()
    for index, call in enumerate(packet['calls']):
        alias = P.ALIASES[ORDER[index]]; sent = call.get('submitted', {}); stored = call.get('stored', {})
        chat = canonical(call.get('chat_id')); answer = canonical(sent.get('id'))
        user = sent.get('user_message', {}); user_id = canonical(user.get('id'))
        require(len({chat, answer, user_id}) == 3 and chat not in seen, 'unknown_gui_fresh_chat'); seen.add(chat)
        require(call.get('http_status') == 200 and call.get('acknowledgement', {}).get('chat_id') == chat
                and sent.get('chat_id',chat)==chat
                and call.get('task_ids') == [] and call.get('model') == sent.get('model') == alias
                and sent.get('message_ids')==[{'model_id':alias,'message_id':answer,'modelIdx':0}]
                and sent.get('stream') is True and sent.get('parent_id') is None
                and user.get('role') == 'user' and user.get('parentId') is None and user.get('content') == 'Hi'
                and sent.get('background_tasks') == {'title_generation': False, 'tags_generation': False, 'follow_up_generation': False}
                and not any(sent.get(k) for k in ('messages', 'tool_ids', 'skill_ids', 'files', 'tool_servers', 'regeneration_prompt')),
                'unknown_gui_submitted_context')
        require(stored.get('id') == chat and stored.get('user_id') == actor, 'unknown_gui_chat_owner')
        data = stored.get('chat', {}); history = data.get('history', {}); messages = history.get('messages', {})
        require(set(messages) == {user_id, answer} and data.get('models') == [alias]
                and history.get('currentId') == answer, 'unknown_gui_saved_history')
        u, a = messages[user_id], messages[answer]
        require(u.get('id') == user_id and u.get('role') == 'user' and u.get('parentId') is None
                and u.get('content') == 'Hi' and u.get('childrenIds') == [answer]
                and a.get('id') == answer and a.get('parentId') == user_id and a.get('model') == alias
                and a.get('role') == 'assistant' and (a.get('user_id') or stored['user_id']) == actor and a.get('done') is True,
                'unknown_gui_saved_answer')
        statuses = [s for s in a.get('statusHistory', []) if s.get('action') == FILTER_ID]
        visible = call.get('visible_text')
        require(isinstance(visible,str) and bool(visible), 'unknown_gui_visible_text')
        if index in DENIED:
            require(bool(a.get('error')) and BLOCKED in json.dumps(a['error'], ensure_ascii=False)
                    and BLOCKED in (call.get('visible_error') or '') and BLOCKED in visible and not a.get('output')
                    and '/key/unblock' not in visible
                    and a.get('content') != 'Proof' and not statuses and call.get('visible_status') is None,
                    'unknown_gui_saved_denial')
        else:
            output = a.get('output') or []
            content = output[0].get('content') if len(output)==1 else None
            require(a.get('error') is None and len(output) == 1 and output[0].get('type') == 'message'
                    and output[0].get('role','assistant')=='assistant' and isinstance(content,list) and len(content)==1
                    and content[0].get('type')=='output_text' and content[0].get('text')=='Proof' and not content[0].get('annotations')
                    and len(statuses) == 1 and statuses[0].get('done') is True
                    and call.get('visible_status') == statuses[0].get('description')
                    and call.get('visible_error') is None, 'unknown_gui_saved_success')
            text = statuses[0]['description']
            require(text == UNKNOWN if ORDER[index] else isinstance(text, str) and
                    re.fullmatch(re.escape(KNOWN) + r' · на \d{2}:\d{2}:\d{2} UTC', text), 'unknown_gui_cost_status')
            require(text in visible and (not ORDER[index] or '$' not in visible), 'unknown_gui_visible_unknown_amount')
        result.append({'index': index, 'alias': alias, 'chat': chat, 'answer': answer, 'denied': index in DENIED})
    foreign = packet.get('foreign_auth', {}); session = foreign.get('session', {})
    require(foreign.get('http_status') == 200 and packet.get('foreign_auth_confirmed') is True
            and canonical(session.get('id')) == canonical(foreign_actor) != actor
            and session.get('role') == 'user', 'unknown_gui_foreign_session')
    require(packet.get('foreign_chat_status') == 401 and packet.get('foreign_chat_detail') == CHAT_NOT_FOUND
            and packet.get('foreign_chat_not_found') is True
            and packet.get('office_settings_before') == packet.get('office_settings_after'),
            'unknown_gui_foreign_or_office_settings')
    return result


def provider_suffix(before, after):
    require(after.get('synthetic') is True and before.get('synthetic') is True
            and after.get('control') == before.get('control'), 'unknown_gui_provider_control')
    old = before['requests']; rows = after['requests']
    require(rows[:len(old)] == old and len(rows) == len(old) + 4, 'unknown_gui_provider_prefix')
    require(len({r.get('id') for r in rows[len(old):]})==4, 'unknown_gui_provider_duplicate_id')
    for record, index in zip(rows[len(old):], (0, 1, 2, 0)):
        expected = {'model': P.WIRES[index], 'input': [{'type': 'message', 'role': 'user',
                    'content': [{'type': 'input_text', 'text': 'Hi'}]}],
                    'max_output_tokens': 16, 'store': False}
        life, response = record.get('lifecycle', {}), record.get('response', {})
        require(record.get('route') == '/v1/responses' and record.get('body') == expected
                and record.get('id_kind') == 'provider_response' and isinstance(record.get('id'), str)
                and life.get('response_status') == 200 and life.get('terminal') is True and life.get('outcome') == 'completed'
                and response.get('id') == record['id'] and response.get('model') == P.WIRES[index]
                and response.get('status') == 'completed' and response.get('object') == 'response'
                and response.get('error') is None, 'unknown_gui_provider_context')
        require(record.get('usage') == (P.RAW_USAGE if index == 0 else None)
                and (response.get('usage') == P.RAW_USAGE if index == 0 else
                     'usage' not in response if index == 1 else 'usage' in response and response['usage'] is None),
                'unknown_gui_provider_usage')


def scopes_and_rows(observation, calls, budget):
    keys = {m.model: m.key_hash for m in budget.models}; scopes = {}; audited = set(); unbound_audits=0
    for row in observation['rows']:
        meta = P.metadata(row); raw = meta.get('spend_logs_metadata', {}).get('owui_budget')
        if raw is None:
            # Native auth denial can precede signed-scope admission. Do not
            # invent a chat/nonce/HTTP binding for that native failure row.
            model=row.get('model_group');unbound_audits+=1
            require(unbound_audits+len(audited)<=2 and model in P.ALIASES[1:]
                    and row.get('user')==budget.user_id and row.get('api_key')==keys[model]
                    and row.get('status')=='failure' and P.close_amount(row.get('spend'),Decimal(0)),
                    'unknown_gui_unbound_failure_audit')
            continue
        scope = P.validate_persisted_scope(raw)
        matches = [c for c in calls if c['chat'] == scope['chat_id'] and c['answer'] == scope['answer_id']]
        require(len(matches) == 1, 'unknown_gui_foreign_scope'); call = matches[0]
        require(scope['user_id'] == budget.user_id and scope['model'] == call['alias'] and scope['category'] == 'personal'
                and scope['root_chat_id'] == call['chat'] and scope['root_answer_id'] == call['answer']
                and row.get('user') == budget.user_id and row.get('session_id') == call['chat']
                and row.get('api_key') == keys[call['alias']] and row.get('model_group') == call['alias'],
                'unknown_gui_native_row_binding')
        if call['denied']:
            require(call['index'] not in audited and unbound_audits+len(audited)<2 and row.get('status') == 'failure'
                    and P.close_amount(row.get('spend'), Decimal(0))
                    and BLOCKED in json.dumps(meta.get('error_information', {})), 'unknown_gui_denial_audit')
            audited.add(call['index']); continue
        require(call['index'] not in scopes and scope['call_id'] not in {s['call_id'] for s in scopes.values()}
                and row.get('model_id') == call['alias'] + '-v1', 'unknown_gui_duplicate_scope')
        require(P.close_amount(row.get('spend'), Decimal(0) if ORDER[call['index']] else P.KNOWN_COST),
                'unknown_gui_native_amount')
        if not ORDER[call['index']]:
            require(row.get('status') == 'success' and {k: row.get(k) for k in ('prompt_tokens','completion_tokens','total_tokens')}
                    == {'prompt_tokens':10,'completion_tokens':5,'total_tokens':15}, 'unknown_gui_native_known_usage')
        scopes[call['index']] = scope
    return scopes


def settled(native, initial, budget, calls, observed=None):
    if observed is None: observed = P.snapshot(native, budget)
    old = {r['request_id']: r for r in initial['rows']}; new = {r['request_id']: r for r in observed['rows']}
    require(all(new.get(k) == v for k, v in old.items()), 'unknown_gui_old_history')
    policy = copy.deepcopy(P.protected(initial))
    for alias in P.ALIASES: policy[alias]['key']['blocked'] = alias != P.ALIASES[0]
    current = copy.deepcopy(P.protected(observed))
    for alias in P.ALIASES:
        blocked = observed['keys'][alias].get('blocked')
        require(type(blocked) is bool and (alias != P.ALIASES[0] or blocked is False), 'unknown_gui_known_blocked')
        current[alias]['key']['blocked'] = policy[alias]['key']['blocked']
    require(current == policy, 'unknown_gui_caps_or_policy')
    scopes = scopes_and_rows(observed, calls, budget)
    if len(scopes) != 4: return None
    if not all(observed['keys'][a].get('blocked') is (a != P.ALIASES[0]) for a in P.ALIASES): return None
    if not P.close_amount(observed['user'].get('spend'), Decimal('.332')): return None
    for alias in P.ALIASES:
        target = Decimal('.332') if alias == P.ALIASES[0] else Decimal(0)
        if not P.close_amount(observed['keys'][alias].get('spend'), target): return None
        if not P.close_amount(observed['keys'][alias].get('total_spend'), target): return None
    return observed, scopes


async def old_accounts(admin, native, common, office, webui):
    # Existing fixture identities and installed service configuration own scope.
    ids = {a['id'] for a in [*common['users'], *office['users']]}
    valves = webui.ok('GET', '/api/v1/functions/id/' + FILTER_ID + '/valves', token=common['admin']['token'])
    if valves.get('service_payer_id'): ids.add(canonical(valves['service_payer_id']))
    previous = native.started_at
    try:
        start = datetime.fromisoformat(common['started_at_utc'])
        require(start.tzinfo is not None and start <= previous, 'unknown_gui_old_history_window')
        native.started_at = start
        result = {}
        for uid in sorted(ids):
            budget = await admin.read_service(uid)
            result[uid] = {'budget': wire_json(asdict(budget)), 'snapshot': P.snapshot(native, budget)}
        return result
    finally: native.started_at = previous


def sources():
    modules = (P.__name__, P.fixture.__name__, P.BudgetAdminClient.__module__, P.BudgetAdminError.__module__,
               P.assignment_matches.__module__, P.fixture.write_private.__module__, P.encode_call.__module__,
               P.protected_r.__module__, P.no_credentials.__module__, P.provider.__module__,
               P.read_cost_snapshot.__module__, 'litellm_auth', P.read_cost_snapshot.__globals__['validate_persisted_scope'].__module__)
    return {'source_sha256': {Path(sys.modules[n].__file__).name: sha256(Path(sys.modules[n].__file__).read_bytes()).hexdigest() for n in modules},
            'mounted_source_sha256': {n: sha256(p.read_bytes()).hexdigest() for n,p in (P.MOUNTED_SOURCES | EXTRA_SOURCES).items()}}


async def execute(phase):
    if phase in ('admin-baseline', 'admin-verify'):
        return await execute_admin(phase)
    common, office = P.fixture.read_private(COMMON), P.fixture.read_private(OFFICE)
    webui = P.fixture.WebUI()
    if phase == 'setup': return await setup_unknown_usage_gui(webui, common, office, STATE)
    state = P.fixture.read_private(STATE); require(state.get('stage') == 'setup_complete', 'unknown_gui_setup')
    actor = state['users'][0]; webui.session(actor, 'user')
    native = P.fixture.native_client(); route = P.routing(native, buffered=True)
    operator = P.fixture.read_private(P.fixture.OPERATOR_STATE); viewer = common['cost_reader']
    reader_readback(native, common)
    async with P.ClientSession(trust_env=False) as session:
        admin = P.BudgetAdminClient(session, P.fixture.PROXY_URL, operator['operator_token'])
        budget = await admin.read_employee(canonical(actor['id']), P.ALIASES)
        if phase == 'baseline':
            require('unknown_gui_baseline' not in state, 'unknown_gui_baseline_exists')
            start = datetime.now(timezone.utc).isoformat(); window(native, start)
            own = P.snapshot(native, budget)
            require(not own['rows'] and budget.max_budget == Decimal(6) and budget.spend == 0
                    and all(m.max_budget == Decimal(2) and m.spend == 0 and m.blocked is False for m in budget.models),
                    'unknown_gui_fresh_budget')
            state['unknown_gui_baseline'] = {'start_utc': start, 'route': route, 'own': own,
                'budget': wire_json(asdict(budget)), 'provider': P.provider(),
                'old': await old_accounts(admin, native, common, office, webui)}
            P.fixture.write_private(STATE, state)
            return {'status':'baseline_ready','inference_issued':False}
        baseline = state.get('unknown_gui_baseline', {}); window(native, baseline.get('start_utc'))
        require(route == baseline.get('route'), 'unknown_gui_route_changed')
        packet = P.fixture.read_private(PACKET); calls = packet_calls(packet, actor['id'], common['users'][0]['id'])
        # Persist exact raw evidence before any verification can fail.
        state['unknown_gui_verification'] = {'packet': packet, 'stage':'reading_native'}; P.fixture.write_private(STATE,state)
        def observe_ready():
            window(native,baseline['start_utc'])
            actual=P.snapshot(native,budget)
            state['unknown_gui_verification']['native']=actual
            P.fixture.write_private(STATE,state)
            return settled(native,baseline['own'],budget,calls,actual)
        observed, scopes = native.poll('GUI accounting settlement', observe_ready)
        provider = P.provider()
        state['unknown_gui_verification']['provider']=provider;P.fixture.write_private(STATE,state)
        provider_suffix(baseline['provider'], provider)
        require(budget.max_budget == Decimal(6) and {m.model for m in budget.models} == set(P.ALIASES), 'unknown_gui_budget_readback')
        # Admin DTO read may predate the bounded counter poll; read it fresh.
        final_budget = await admin.read_employee(actor['id'], P.ALIASES)
        require(final_budget.max_budget == Decimal(6) and final_budget.spend == Decimal('.332')
                and all(m.max_budget == Decimal(2) and m.spend == (Decimal('.332') if m.model == P.ALIASES[0] else 0)
                        and m.blocked is (m.model != P.ALIASES[0]) for m in final_budget.models), 'unknown_gui_budget_readback')
        for index, scope in scopes.items():
            try:
                value = await P.read_cost_snapshot(session, base_url=P.fixture.PROXY_URL, read_key=viewer['key'],
                    user_id=actor['id'], root_chat_id=scope['chat_id'], root_answer_id=scope['answer_id'],
                    observed_call_ids=[scope['call_id']])
            except P.CostReadError as error:
                require(ORDER[index] != 0 and error.code == 'usage_unavailable', 'unknown_gui_viewer_failure')
            else:
                require(ORDER[index] == 0 and value.complete and P.close_amount(value.answer.spend, P.KNOWN_COST)
                        and P.close_amount(value.chat.spend,P.KNOWN_COST), 'unknown_gui_viewer_false_confirmation')
        require(await old_accounts(admin,native,common,office,webui) == baseline['old'], 'unknown_gui_old_accounts_changed')
        window(native,baseline['start_utc'])
        state['unknown_gui_verification'].update(stage='verified',native=observed,provider=provider,scopes=scopes)
        P.fixture.write_private(STATE,state)
    result = {'schema':1,'proof':PROOF,'passed':True,'gui_sends':6,'provider_dispatches':4,'positive_chats':2,
              'unknown_chats':2,'saved_key_denials':2,'known_positive_total':'.332','blocked_assignments':2,
              'native_401_inferred':False,'unknown_cost_finality':False,'whole_goal_accepted':False,
              'unbound_denial_audit_chat_association_independently_proven':False,
              'foreign_chat_status':401,'foreign_chat_not_found':True,'foreign_auth_confirmed':True,
              'production_accepted':False,'inference_issued':False,**sources()}
    P.no_credentials(result,[*P.private_credentials(common),*P.private_credentials(office),*P.private_credentials(state),*P.private_credentials(operator)])
    return result


def admin_sources():
    """Native cold-import/source closure only; no HTTP or private state writes."""
    import provision_admin
    import verify_admin_calls
    import prove_office_delegation_readback
    import prove_office_readback
    import prove_office_compatibility
    import mock_provider
    import capture_webui_auth
    result = sources()
    result['admin_source_sha256'] = {Path(module.__file__).name: sha256(Path(module.__file__).read_bytes()).hexdigest()
        for module in (provision_admin, verify_admin_calls, prove_office_delegation_readback,
                       prove_office_readback, prove_office_compatibility, mock_provider, capture_webui_auth)}
    result['admin_producer_sha256'] = {name: sha256((provision_admin.SOURCE.parent / name).read_bytes()).hexdigest()
        for name in ('admin_tools.py', 'admin_ui.py', 'admin_policy.py')}
    return result


def admin_calls(before, provider, captured):
    """The admin slice's finite partition over the shared whole-body join."""
    from prove_office_delegation_readback import join_responses_call
    import mock_provider
    for name, current in (('provider', provider), ('capture', captured)):
        require(current['requests'][:len(before[name]['requests'])] == before[name]['requests'], 'admin_unknown_prior_context')
    physical = provider['requests'][len(before['provider']['requests']):]
    observed = captured['requests'][len(before['capture']['requests']):]
    try:
        require(provider.get('synthetic') is True and provider.get('control') == before['provider'].get('control')
                and len(physical) == len(observed) == 3, 'admin_unknown_dispatch_count')
    except P.ProofError as error:
        # Already-read operands only; no payload, identity, money or extra IO.
        error._admin_unknown_dispatch = {'physical_requests': len(physical), 'captured_requests': len(observed),
            'synthetic': provider.get('synthetic') is True,
            'control_unchanged': provider.get('control') == before['provider'].get('control')}
        raise
    main, service, used, nonces = [], [], set(), set()
    for row in observed:
        model = row['body'].get('model')
        require(model in (P.ALIASES[0], 'gpt-6-luna'), 'admin_unknown_dispatch_model')
        call = join_responses_call(row, physical, wire_model=P.WIRES[0] if model == P.ALIASES[0] else 'goal584-fake-office-service',
                                   provider_transport='buffered' if model == P.ALIASES[0] else 'native')
        p, scope = call['provider'], call['verified_cost_scope']
        require(p['id'] not in used and scope['call_id'] not in nonces, 'admin_unknown_duplicate_dispatch')
        used.add(p['id']); nonces.add(scope['call_id'])
        if model == P.ALIASES[0]:
            index = next(i for i, actual in enumerate(provider['requests']) if actual['id'] == p['id'])
            step = mock_provider.admin_responses_step(p['body'], mock_provider.responses_input(p['body']),
                                                       prior_requests=provider['requests'][:index])
            require(step is not None and p.get('usage') == p['response'].get('usage') == P.RAW_USAGE
                    and p['response'].get('id') == p['id'] and p['response'].get('model') == P.WIRES[0]
                    and p['response'].get('status') == 'completed' and p['lifecycle'] == {'terminal': True, 'outcome': 'completed'},
                    'admin_unknown_primary_provider')
            main.append(call)
        else: service.append(call)
    require(len(main) == 2 and len(service) == 1 and len(used) == 3, 'admin_unknown_dispatch_partition')
    return main, service[0]


def admin_browser(packet, saved, selected):
    """Join actual native persistence to raw browser evidence using the pure parser."""
    from verify_admin_calls import editor_rows
    from mock_provider import ADMIN_USER_REQUEST as intent
    admin, actor = selected['admin']['id'], selected['actor_id']
    sent = packet['submitted']; ack = packet['acknowledgement']
    chat, answer = canonical(ack.get('chat_id') or sent.get('chat_id')), canonical(sent.get('id'))
    require(packet.get('schema') == 1 and 'failure' not in packet and packet.get('admin_id') == admin
            and packet.get('actor_id') == actor and packet.get('model_id') == 'goal584-budget-admin'
            and packet.get('http_status') == 200 and packet.get('task_ids') == []
            and json.loads(packet['raw_submission']) == sent
            and json.loads(base64.b64decode(packet['raw_acknowledgement_base64'], validate=True)) == ack,
            'admin_unknown_browser_packet')
    require(saved == packet['stored_chat'] and saved.get('id') == chat and saved.get('user_id') == admin,
            'admin_unknown_saved_binding')
    history = saved['chat']['history']; messages = history['messages']; final = messages[answer]
    parent = messages[canonical(final.get('parentId'))]
    require(history['currentId'] == answer and len(messages) == 2 and final.get('id') == answer
            and final.get('role') == 'assistant' and final.get('model') == 'goal584-budget-admin'
            and final.get('done') is True and not final.get('error')
            and parent.get('role') == 'user' and parent.get('content') == intent
            and parent.get('id') == sent.get('user_message', {}).get('id')
            and sent.get('user_message', {}).get('content') == intent and parent.get('parentId') is None
            and parent.get('childrenIds') == [answer] and sent.get('parent_id') is None
            and sent.get('model') == 'goal584-budget-admin', 'admin_unknown_saved_parent')
    calls = [v for v in final.get('output', []) if v.get('type') == 'function_call']
    require(len(calls) == 1 and calls[0].get('status') == 'completed'
            and calls[0].get('name', '').endswith('open_budget_form')
            and json.loads(calls[0]['arguments']) == {'view_json': '{}'}, 'admin_unknown_saved_tool')
    outputs = [v for v in final['output'] if v.get('type') == 'function_call_output']
    require(len(outputs) == 1 and outputs[0].get('call_id') == calls[0].get('call_id')
            and outputs[0].get('status') == 'completed' and outputs[0].get('embeds') == [packet['html']]
            and sha256(packet['html'].encode()).hexdigest() == packet['html_sha256'], 'admin_unknown_saved_embed')
    rows = editor_rows(packet['html'], expected_count=1)
    require(rows == packet['rows'] and rows[0]['user_id'] == actor and rows[0].get('expense_status') == 'unknown'
            and rows[0].get('known_subtotal_usd') is None
            and {m['id'] for m in rows[0]['models']} == set(P.ALIASES)
            and all(m.get('expense_status') == ('unavailable' if m['id'] == P.ALIASES[0] else 'unknown')
                    and m.get('known_subtotal_usd') is None for m in rows[0]['models']), 'admin_unknown_saved_rows')
    return chat, answer, final, rows


def admin_native(before, after, main, cost, *, admin, chat, answer):
    """Reconcile native identity/cardinality/counters against the existing cost owner."""
    require(cost.user_id == admin and cost.root_chat_id == chat and cost.root_answer_id == answer
            and cost.complete and not cost.pending and cost.answer.calls == cost.chat.calls == 2
            and P.close_amount(cost.answer.spend, Decimal('.332')) and cost.answer == cost.chat,
            'admin_unknown_cost_snapshot')
    first, current = before['own']['native'], after['own']['native']
    require(after['unknown'] == before['unknown'] and after['old'] == before['old']
            and P.protected(current) == P.protected(first), 'admin_unknown_native_preservation')
    key = first['keys'][P.ALIASES[0]]['token']
    scopes = []
    for call in main:
        scope = P.validate_persisted_scope(call['verified_cost_scope'])
        require(scope['user_id'] == call['auth_user_id'] == admin and call['auth_key_hash'] == key
                and scope['model'] == P.ALIASES[0] and scope['chat_id'] == scope['root_chat_id'] == chat
                and scope['answer_id'] == scope['root_answer_id'] == answer, 'admin_unknown_personal_scope')
        scopes.append(scope)
    P.history(first['rows'], current['rows'], {P.ALIASES[0]: key}, [{'status': 200, 'scope': s} for s in scopes])
    require(len(current['rows']) == len(first['rows']) + 2, 'admin_unknown_native_cardinality')
    for owner, old in ((current['user'], first['user']), (current['keys'][P.ALIASES[0]], first['keys'][P.ALIASES[0]])):
        require(P.close_amount(Decimal(str(owner['spend'])) - Decimal(str(old['spend'])), cost.answer.spend),
                'admin_unknown_native_counter')


def admin_context(main, final):
    """Actual native Tool persistence must be the provider's same correlated IO."""
    emitted = [v for v in main[0]['provider']['response'].get('output', []) if v.get('type') == 'function_call']
    stored_calls = [v for v in final['output'] if v.get('type') == 'function_call']
    stored_results = [v for v in final['output'] if v.get('type') == 'function_call_output']
    inputs = main[1]['wire_before_auth'].get('input', [])
    next_calls = [v for v in inputs if isinstance(v, dict) and v.get('type') == 'function_call']
    next_results = [v for v in inputs if isinstance(v, dict) and v.get('type') == 'function_call_output']
    require(len(emitted) == len(stored_calls) == len(stored_results) == len(next_calls) == len(next_results) == 1,
            'admin_unknown_tool_context_count')
    for name in ('call_id', 'name', 'arguments'):
        require(emitted[0].get(name) == stored_calls[0].get(name) == next_calls[0].get(name), 'admin_unknown_tool_context_binding')
    parts = stored_results[0]['output']
    require(isinstance(parts, list) and len(parts) == 1 and parts[0].get('type') == 'input_text'
            and isinstance(parts[0].get('text'), str), 'admin_unknown_native_tool_output')
    require(next_results[0].get('call_id') == stored_results[0].get('call_id') == emitted[0].get('call_id')
            and json.loads(next_results[0]['output']) == json.loads(parts[0]['text']),
            'admin_unknown_tool_result_binding')
    expected = [v for item in main[1]['provider']['response'].get('output', []) if item.get('type') == 'message'
                for v in item.get('content', []) if v.get('type') == 'output_text']
    actual = [v for item in final['output'] if item.get('type') == 'message'
              for v in item.get('content', []) if v.get('type') == 'output_text']
    require(expected and [v.get('text') for v in actual] == [v.get('text') for v in expected], 'admin_unknown_terminal_context')


def admin_row_counters(rows, actor_budget):
    """Compare displayed native fields; do not derive costs or remaining amounts."""
    rendered = rows[0]
    require(P.close_amount(rendered['spend_usd'], Decimal(actor_budget['spend']))
            and P.close_amount(rendered['budget_usd'], Decimal(actor_budget['max_budget'])), 'admin_unknown_render_counter')
    models = {m['model']: m for m in actor_budget['models']}
    require(all(P.close_amount(m['spend_usd'], Decimal(models[m['id']]['spend']))
                and P.close_amount(m['cap_usd'], Decimal(models[m['id']]['max_budget'])) for m in rendered['models']),
            'admin_unknown_render_model_counter')


async def execute_admin(phase):
    import provision_admin as setup
    import prove_office_readback as office_reader
    from mock_provider import ADMIN_USER_REQUEST as intent
    common, office, unknown = (P.fixture.read_private(path) for path in (COMMON, OFFICE, STATE))
    selected = P.fixture.read_private(ADMIN_SETUP); webui = P.fixture.WebUI()
    native = P.fixture.native_client(); native.started_at = datetime.fromisoformat(common['started_at_utc'])
    d = office_reader.dependencies(); closure = admin_sources()
    def contexts():
        with d['capture'].capture_lock(): captured = d['capture']._read_locked()
        return P.provider(), captured
    async def observation():
        value = await setup.unknown_observation(webui, common, office, unknown, selected)
        setup.unknown_snapshot(webui, common, office, unknown, copy.deepcopy(selected), observed=value)
        return value
    if phase == 'admin-baseline':
        require(not ADMIN_STATE.exists(), 'admin_unknown_baseline_exists')
        observed = await observation(); provider, captured = contexts()
        require(len(captured['requests']) + 3 <= d['capture'].MAX_RECORDS, 'admin_unknown_capture_capacity')
        require(not observed['own']['native']['rows'] and Decimal(observed['own']['budget']['spend']) == 0, 'admin_unknown_fresh_payer')
        model, = [m for m in native.ok('GET', '/model/info')['data'] if m.get('model_name') == 'gpt-6-luna']
        state = {'schema': 1, 'stage': 'baseline',
            'observation': observed, 'provider': provider, 'capture': captured,
            'descriptor': model['model_info']['owui_pricing'], 'sources': closure}
        P.fixture.write_private(ADMIN_STATE, state)
        return {'status': 'baseline_ready', 'inference_issued': False, **closure}
    state = P.fixture.read_private(ADMIN_STATE)
    require(state.get('stage') == 'baseline' and state.get('sources') == closure, 'admin_unknown_baseline_changed')
    packet = P.fixture.read_private(ADMIN_BROWSER)
    webui.session(selected['admin'], 'admin')
    sent = packet['submitted']; chat = canonical(packet['acknowledgement'].get('chat_id') or sent.get('chat_id'))
    saved = webui.ok('GET', '/api/v1/chats/' + chat, token=selected['admin']['token'])
    active = webui.ok('GET', '/api/tasks/chat/' + chat, token=selected['admin']['token'])
    require(active.get('task_ids') == [], 'admin_unknown_background_active')
    chat, answer, final, rows = admin_browser(packet, saved, selected)
    provider, captured = contexts(); main, service = admin_calls(state, provider, captured)
    admin_context(main, final)
    state['last_observation'] = dict(browser=packet, saved_chat=saved, provider=provider, capture=captured)
    P.fixture.write_private(ADMIN_STATE, state)
    async with P.ClientSession(trust_env=False) as session:
        cost = await P.read_cost_snapshot(session, base_url=P.fixture.PROXY_URL, read_key=common['cost_reader']['key'],
            user_id=selected['admin']['id'], root_chat_id=chat, root_answer_id=answer,
            observed_call_ids=[c['verified_cost_scope']['call_id'] for c in main], timeout_seconds=60, wait_seconds=60)
        client = P.BudgetAdminClient(session, P.fixture.PROXY_URL,
                                    P.fixture.read_private(P.fixture.OPERATOR_STATE)['operator_token'])
        own_budget = await client.read_employee(selected['admin']['id'], (P.ALIASES[0],))
        service_budget = await client.read_service(office['service_fixture']['payer_id'])
    after = await observation()
    # Service accounting remains the existing independent native owner.
    def service_finance(value):
        snap = value['snapshot']; keys = list(snap['keys'].values())
        require(len(keys) == 1, 'admin_unknown_service_assignment')
        return {'user': snap['user'], 'key': keys[0], 'rows': snap['rows']}
    def settled_admin():
        current = copy.deepcopy(after)
        current['own']['native'] = P.snapshot(native, own_budget)
        current['service']['snapshot'] = P.snapshot(native, service_budget)
        state['last_observation']['native'] = current; P.fixture.write_private(ADMIN_STATE, state)
        try:
            admin_native(state['observation'], current, main, cost, admin=selected['admin']['id'], chat=chat, answer=answer)
            task = office_reader.verify_service_turn(service, service_finance(state['observation']['service']),
                service_finance(current['service']), final, actor=selected['admin']['id'], payer=office['service_fixture']['payer_id'],
                chat=chat, descriptor=state['descriptor'], d=d, expected_user_request=intent)
        except P.ProofError as error:
            code = str(error)
            owner = ('own', 'native') if code == 'admin_unknown_native_counter' else ('service', 'snapshot')
            if code in ('admin_unknown_native_counter', 'office_service_native_spend_delta'):
                before_owner = state['observation'][owner[0]][owner[1]]; now = current[owner[0]][owner[1]]
                alias = P.ALIASES[0] if owner[0] == 'own' else next(iter(now['keys']))
                expected = cost.answer.spend if owner[0] == 'own' else Decimal('.20')
                deltas = [Decimal(str(a['spend'])) - Decimal(str(b['spend'])) for a,b in
                    ((now['user'],before_owner['user']), (now['keys'][alias],before_owner['keys'][alias]))]
                if all(0 <= v <= expected for v in deltas) and any(v < expected for v in deltas): return None
            if code == 'office_service_row_count' and len(current['service']['snapshot']['rows']) == len(state['observation']['service']['snapshot']['rows']):
                return None
            raise
        return current, task
    after, task = native.poll('admin unknown native rows and counters', settled_admin)
    admin_row_counters(rows, after['unknown']['budget'])
    state.update(stage='verified', after=after, cost=wire_json(asdict(cost)), service=task)
    P.fixture.write_private(ADMIN_STATE, state)
    return {'status': 'verified', 'inference_issued': False, 'personal_calls': 2, 'personal_cost_usd': '.332',
        'service': task, 'native_saved_embed_verified': True, 'unknown_employee_verified': True, **closure}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True,choices=('setup','baseline','verify','admin-baseline','admin-verify'));args=parser.parse_args()
    admin_phase = args.phase.startswith('admin-')
    target=PRIVATE/(('admin-unknown-'+args.phase.removeprefix('admin-') if admin_phase else 'unknown-usage-gui-'+args.phase)+'.safe.json')
    result={'schema':1,'proof':ADMIN_PROOF if admin_phase else PROOF,'passed':False,'phase':args.phase,'unknown_cost_finality':False,'whole_goal_accepted':False,'production_accepted':False}
    if admin_phase: result['inference_issued'] = False
    available=not target.exists() and not target.is_symlink()
    try:
        require(available,'unknown_gui_receipt_exists');value=asyncio.run(execute(args.phase));result.update(value,passed=True)
    except Exception as error:
        # Raw diagnostic belongs only in the private handoff; safe output is fixed.
        failure_path = ADMIN_STATE if admin_phase else STATE
        if failure_path.exists() or admin_phase:
            state=P.fixture.read_private(failure_path) if failure_path.exists() else {'schema': 1, 'stage': 'failed'}
            state['admin_unknown_error' if admin_phase else 'unknown_gui_error']={'type':type(error).__name__,'message':str(error)[:8192] if admin_phase else str(error)}
            P.fixture.write_private(failure_path,state)
        result.update(passed=False,failure='admin_unknown_contract_failed' if admin_phase else 'unknown_gui_contract_failed')
        if admin_phase: result.update(admin_failure_fields(error))
    P.no_credentials(result)
    if available:P.fixture.write_private(target,result)
    print(json.dumps(result,indent=2,allow_nan=False));return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
