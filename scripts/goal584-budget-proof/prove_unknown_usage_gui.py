"""Finite native collector for the six ordinary GUI Sends; never issues inference.

Host Playwright stays outside the proxy. All nonces/scopes below are read from
native rows; GUI ACK200 is never presented as a native authentication401.
"""
from __future__ import annotations
import argparse
import asyncio
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
PROOF = 'goal584-unknown-usage-gui'
UNKNOWN = 'Расход неизвестен. Обратитесь к администратору.'
KNOWN = 'Ответ: $0.166 · Чат: $0.166'
BLOCKED = 'Authentication Error, Key is blocked.'
ORDER = (0, 1, 1, 2, 2, 0)
DENIED = (2, 4)
# Actual imports, not host browser modules; host adds these readonly mounts.
EXTRA_SOURCES = {n: Path(__file__).with_name(n) for n in
                 ('prove_unknown_usage_gui.py', 'unknown_usage_gui_fixture.py', 'provision_cost_display.py')}
require = P.require
wire_json = lambda value: json.loads(json.dumps(value, default=str, allow_nan=False))


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


def packet_calls(packet, actor):
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
                and sent.get('stream') is False and sent.get('parent_id') is None
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
            require(bool(a.get('error')) and BLOCKED in json.dumps(a['error'])
                    and BLOCKED in (call.get('visible_error') or '') and BLOCKED in visible and not a.get('output')
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
    require(packet.get('foreign_chat_status') == 404 and packet.get('office_settings_before') == packet.get('office_settings_after'),
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
                    'max_output_tokens': 16, 'store': False, 'stream': False}
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
    common, office = P.fixture.read_private(COMMON), P.fixture.read_private(OFFICE)
    webui = P.fixture.WebUI()
    if phase == 'setup': return await setup_unknown_usage_gui(webui, common, office, STATE)
    state = P.fixture.read_private(STATE); require(state.get('stage') == 'setup_complete', 'unknown_gui_setup')
    actor = state['users'][0]; webui.session(actor, 'user')
    native = P.fixture.native_client(); route = P.routing(native)
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
        packet = P.fixture.read_private(PACKET); calls = packet_calls(packet, actor['id'])
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
              'production_accepted':False,'inference_issued':False,**sources()}
    P.no_credentials(result,[*P.private_credentials(common),*P.private_credentials(office),*P.private_credentials(state),*P.private_credentials(operator)])
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True,choices=('setup','baseline','verify'));args=parser.parse_args()
    target=PRIVATE/('unknown-usage-gui-'+args.phase+'.safe.json')
    result={'schema':1,'proof':PROOF,'passed':False,'phase':args.phase,'unknown_cost_finality':False,'whole_goal_accepted':False,'production_accepted':False}
    available=not target.exists() and not target.is_symlink()
    try:
        require(available,'unknown_gui_receipt_exists');value=asyncio.run(execute(args.phase));result.update(value,passed=True)
    except Exception as error:
        # Raw diagnostic belongs only in the private handoff; safe output is fixed.
        if STATE.exists():
            state=P.fixture.read_private(STATE);state['unknown_gui_error']={'type':type(error).__name__,'message':str(error)}
            P.fixture.write_private(STATE,state)
        result.update(passed=False,failure='unknown_gui_contract_failed')
    P.no_credentials(result)
    if available:P.fixture.write_private(target,result)
    print(json.dumps(result,indent=2,allow_nan=False));return 0 if result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
