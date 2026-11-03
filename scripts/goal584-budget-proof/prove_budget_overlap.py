#!/usr/bin/env python3
"""Prepared two-container scalar-budget proof. No Docker is started by this CLI.

Host mode coordinates already scaled native proxy containers; worker mode reuses
NativeProof's protected loopback HTTP owner. Credentials/raw observations stay
in the existing private fixture directory. This is not a WebUI acceptance test.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import stat
import sys
import time
from uuid import uuid4
from urllib.parse import urlsplit

from prove_native_budgets import NativeProof, ProofError, MODELS, CALL_COST, amount, close_amount, expected_budget_message, require
from prove_gateway_auth import read_private as native_read_private, write_private as native_write_private

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT / 'deploy/litellm-patches/positive-floor-v1.105.1'))
import native_floor_identity as native_sdk
STATE = Path('/proof-private/budget-overlap.private.json')
IMAGE = 'ghcr.io/berriai/litellm:v1.105.1@sha256:b7b9e2c306343721802253d0dd9436b9634a2eb4e14da7c7cf06c5c7b7530802'
PROMPT = 'Hi. Please read this bounded synthetic fixture sentence. ' * 8
BODY = {'messages': [{'role': 'user', 'content': PROMPT}], 'max_tokens': 5, 'stream': False}
SOURCE_PATHS = {'native_floor_identity.py': 'deploy/litellm-patches/positive-floor-v1.105.1/native_floor_identity.py',
    'manifest.json': 'deploy/litellm-patches/positive-floor-v1.105.1/manifest.json',
    'prove_budget_overlap.py': 'scripts/goal584-budget-proof/prove_budget_overlap.py',
    'prove_native_budgets.py': 'scripts/goal584-budget-proof/prove_native_budgets.py',
    'prove_gateway_auth.py': 'scripts/goal584-budget-proof/prove_gateway_auth.py',
    'capture_webui_auth.py': 'scripts/goal584-budget-proof/capture_webui_auth.py',
    'prove_service_tasks.py': 'scripts/goal584-budget-proof/prove_service_tasks.py',
    'provenance.py': 'deploy/openwebui-budgets/provenance.py',
    'litellm_auth.py': 'deploy/openwebui-budgets/litellm_auth.py',
    'employee_budget_assignment.py': 'deploy/openwebui-budgets/assignment.py',
    'budget_errors.py': 'deploy/openwebui-budgets/budget_errors.py',
    'pricing_snapshot.py': 'deploy/openwebui-budgets/pricing_snapshot.py',
    'provision_webui.py': 'scripts/goal584-budget-proof/provision_webui.py',
    'provision_cost_display.py': 'scripts/goal584-budget-proof/provision_cost_display.py',
    'provision_admin.py': 'scripts/goal584-budget-proof/provision_admin.py',
    'verify_admin_calls.py': 'scripts/goal584-budget-proof/verify_admin_calls.py',
    'employee_budget_admin_client.py': 'deploy/openwebui-budgets/admin_client.py',
    'employee_budget_admin_contract.py': 'deploy/openwebui-budgets/admin_contract.py'}
PROVIDER_SOURCE = 'scripts/goal584-budget-proof/mock_provider.py'


def read_private(path):
    require(path.is_file() and path.stat().st_size<=8*1024*1024,'Overlap private state unavailable or oversized')
    return native_read_private(path)


def write_private(path,value):
    require(len(json.dumps(value,allow_nan=False).encode())<=8*1024*1024,'Overlap private state exceeded bound')
    native_write_private(path,value)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def safe(value):
    require(not re.search(r'(?:sk-|gw-)[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',
                          json.dumps(value)), 'Credential-shaped overlap evidence suppressed')
    return value


def request_id(value):
    require(isinstance(value, str) and re.fullmatch(r'chatcmpl-goal584-[0-9a-f]{32}', value), 'Invalid fixture provider ID')
    return value


def cap(value):
    value = amount(value)
    result = float(value)
    require(Decimal(str(result)) == value, 'Native cap cannot preserve fixture precision')
    return result


def calibrated_caps(estimates):
    a, b = (amount(estimates[model]) for model in MODELS)
    require(abs(a-b) <= Decimal('0.000000001') and CALL_COST < min(a,b) and max(a,b) < 5, 'Native calibration does not isolate reservations')
    reserve = max(a,b)
    lower, upper = reserve + CALL_COST, 2*min(a,b)
    budget = (lower + upper)/2
    require(lower < budget < upper, 'Calibration lacks an interior overlap rejection interval')
    cap(budget); cap(2*budget)
    return reserve, budget


def capture():
    from capture_webui_auth import capture_lock, _read_locked
    with capture_lock():
        return copy.deepcopy(_read_locked()['requests'])


def provider(*args, **kwargs):
    # Existing fixture HTTP/control owner, not a second provider client.
    from prove_service_tasks import provider as existing
    return existing(*args, **kwargs)


def proof():
    operator = read_private(Path('/proof-private/gateway-state.private.json'))
    native = NativeProof('http://127.0.0.1:4000', operator['operator_token'], 45, {})
    native.started_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    return native, operator


def old_snapshot(native, users):
    result = {}
    fields = ('user_id','user_role','models','spend','max_budget','budget_duration','budget_reset_at')
    key_fields = ('token','user_id','models','key_alias','spend','max_budget','budget_duration','budget_reset_at','blocked','metadata','team_id')
    for uid in users:
        info = native.user_info(uid)
        require(isinstance(info.get('keys'),list) and all(isinstance(k,dict) for k in info['keys']), 'Native old key rows unavailable')
        result[uid] = {'user': {k:info.get(k) for k in fields},
            'keys': sorted(({k:entry.get(k) for k in key_fields} for entry in info['keys']),key=lambda r:r['token']),
            'rows': sorted(native.logs(uid),key=lambda r:r['request_id'])}
    return result


def nonspend(snapshot):
    return {'user': {k:v for k,v in snapshot['user'].items() if k != 'spend'},
            'keys': [{k:v for k,v in entry.items() if k != 'spend'} for entry in snapshot['keys']]}


def create(native, state, name, total, per_key):
    from employee_budget_assignment import assignment_alias, assignment_metadata
    uid = state['users'][name]
    state.setdefault('user_caps',{})[uid] = str(total)
    native.ok('POST', '/user/new', body={'user_id': uid, 'user_role': 'internal_user', 'models': list(MODELS),
        'max_budget': cap(total), 'budget_duration': '30d', 'auto_create_key': False, 'send_invite_email': False, 'teams': []})
    for model in MODELS:
        generated = native.ok('POST', '/key/generate', body={'user_id': uid, 'models': [model],
            'key_alias': assignment_alias(uid, model), 'metadata': assignment_metadata(model),
            'max_budget': cap(per_key), 'budget_duration': '30d', 'allowed_routes': ['llm_api_routes']})
        token = generated.get('key')
        require(isinstance(token, str) and token.startswith('sk-'), 'Native overlap assignment missing')
        state['keys'][uid+'|'+model] = {'token': token, 'hash': hashlib.sha256(token.encode()).hexdigest(),
            'alias': assignment_alias(uid, model), 'cap': str(per_key)}
        write_private(STATE, state)
        native.keys[uid, model] = state['keys'][uid+'|'+model]
        actual = native.key_info(uid, model)
        metadata=actual.get('metadata') or {}
        if isinstance(metadata,str):metadata=json.loads(metadata)
        require(actual.get('key_alias') == assignment_alias(uid, model) and amount(actual.get('max_budget')) == per_key
                and amount(actual.get('spend')) == 0 and actual.get('blocked') is not True
                and all(metadata.get(k)==v for k,v in assignment_metadata(model).items())
                and metadata.get('throttle_on_budget_exceeded') is not True,
                'Native overlap assignment readback differs')
    created = old_snapshot(native, [uid])[uid]
    info = created['user']
    require(info.get('user_id') == uid and info.get('user_role')=='internal_user' and info.get('models') == list(MODELS)
            and amount(info.get('max_budget')) == total and amount(info.get('spend')) == 0
            and info.get('budget_duration') == '30d' and info.get('budget_reset_at'),
            'Native overlap user cap readback differs')
    require(len(created['keys']) == 2 and {k['token'] for k in created['keys']} ==
            {state['keys'][uid+'|'+model]['hash'] for model in MODELS} and not created['rows']
            and all(amount(k['spend']) == 0 for k in created['keys']), 'Native overlap creation population differs')
    for model in MODELS:
        key = next(k for k in created['keys'] if k['token'] == state['keys'][uid+'|'+model]['hash'])
        metadata = key.get('metadata') or {}
        if isinstance(metadata, str): metadata = json.loads(metadata)
        require(key['user_id'] == uid and key['models'] == [model] and key['key_alias'] == assignment_alias(uid, model)
                and amount(key['max_budget']) == per_key and key['team_id'] is None and key['blocked'] is not True
                and key['budget_duration'] == '30d' and key['budget_reset_at']
                and all(metadata.get(k) == v for k,v in assignment_metadata(model).items())
                and metadata.get('throttle_on_budget_exceeded') is not True, 'Native overlap creation key policy differs')
    state.setdefault('created', {})[uid] = created
    write_private(STATE, state)


def call(native, state, label, *, denied=None):
    from provenance import encode_call, validate_persisted_scope
    item = state['plan'][label]
    uid, model = state['users'][item['user']], item['model']
    body = {'model': model, **copy.deepcopy(BODY), 'litellm_metadata': {'owui_budget_provenance': encode_call(
        os.environ['OWUI_BUDGET_GATEWAY_SECRET'], user_id=uid, model=model, chat_id=item['chat'], answer_id=item['answer'],
        root_chat_id=item['chat'], root_answer_id=item['answer'])}}
    earlier = {r['_observation_id'] for r in capture()}
    status, response, _ = native.request('POST', '/v1/chat/completions', token=os.environ['OWUI_BUDGET_GATEWAY_SECRET'],
        extra_headers={'X-OpenWebUI-User-Id': uid, 'X-OpenWebUI-Task': ''}, body=body)
    records = [r for r in capture() if r['_observation_id'] not in earlier and r.get('user_id') == uid
               and r.get('body', {}).get('model') == model and
               (denied is not None or r.get('verified_cost_scope', {}).get('chat_id') == item['chat'])]
    require(len(records) == 1, 'Native overlap diagnostic identity is missing or ambiguous')
    record = records[0]
    semantic = {'model': model, **BODY}
    require(record['body'] == record['body_after_auth'] == semantic, 'Overlap auth changed native model context')
    estimate = amount(record['native_estimated_max_cost_usd'])
    require('reserve_usd' not in state or abs(estimate-amount(state['reserve_usd']))<=Decimal('0.000000001'),
            'Actual native request reservation estimate changed after calibration')
    evidence = {'schema': 1, 'label': label, 'user_id': uid, 'model': model, 'http_status': status,
                'native_estimate_usd': str(estimate), 'context_sha256': digest(semantic)}
    if denied:
        require(status == 422 and isinstance(response.get('error'),dict) and response['error'].get('type')=='budget_exceeded',
                'Overlap contender did not reach native budget rejection')
        expected_budget_message(response, scope=denied)
        evidence.update(outcome='budget_exceeded', scope=denied)
    else:
        require(status == 200 and not response.get('error'), 'Native overlap inference failed')
        identifier = request_id(response.get('id'))
        require(response.get('usage', {}).get('prompt_tokens') == 10 and response['usage'].get('completion_tokens') == 5
                and response['usage'].get('total_tokens') == 15, 'Native overlap response usage differs')
        physical = [r for r in provider()['requests'] if r['id'] == identifier]
        expected = {**semantic, 'model': 'goal584-fake-' + model[-1]}; expected.pop('stream')
        require(len(physical) == 1 and physical[0]['body'] == expected
                and physical[0]['usage'] == {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
                'Overlap actual provider context or usage differs')
        scope = validate_persisted_scope(record.get('verified_cost_scope'))
        require(scope['user_id'] == uid and scope['model'] == model and scope['chat_id'] == item['chat']
                and scope['answer_id'] == item['answer'], 'Overlap signed native scope differs')
        evidence.update(outcome='success', provider_id=identifier, scope=scope)
    write_private(STATE.with_name('overlap-'+label+'.private.json'), safe(evidence))
    return evidence


def results(state):
    return [read_private(STATE.with_name('overlap-'+label+'.private.json')) for label in state['plan']
            if STATE.with_name('overlap-'+label+'.private.json').exists()]


def reconcile(native, state):
    admitted = [r for r in results(state) if r['outcome'] == 'success']
    expected = {r['provider_id']: r for r in admitted}
    require(len(expected) == len(admitted), 'Overlap response IDs collided')
    snapshots, positive, pending = [], [], False
    def settled(value, expected):
        actual = amount(value)
        require(actual >= 0, 'Overlap native counter regressed below zero')
        if expected == 0:
            require(actual == 0, 'Overlap untouched native counter changed')
            return True
        require(actual <= expected or close_amount(actual, expected), 'Overlap native counter exceeded expected spend')
        return close_amount(actual, expected)
    for uid in state['users'].values():
        current = old_snapshot(native, [uid])[uid]
        require(nonspend(current) == nonspend(state['created'][uid]), 'Overlap native creation identity or policy changed')
        actual = current['user']
        selected = [r for r in admitted if r['user_id'] == uid]
        pending |= not settled(actual.get('spend'), len(selected)*CALL_COST)
        snapshots.append({'user_id': uid, 'spend_usd': str(amount(actual['spend'])), 'cap_usd': str(amount(actual['max_budget']))})
        rows = [r for r in current['rows'] if amount(r.get('spend', 0)) > 0]
        require(len({r['request_id'] for r in rows})==len(rows)
                and {r['request_id'] for r in rows}<={r['provider_id'] for r in selected}, 'Unexpected or duplicate native positive spend rows')
        pending |= {r['request_id'] for r in rows} != {r['provider_id'] for r in selected}
        for row in rows:
            observed = expected[row['request_id']]
            metadata = row.get('metadata') or {}
            if isinstance(metadata, str): metadata = json.loads(metadata)
            require(row['api_key'] == state['keys'][uid+'|'+observed['model']]['hash'] and row['user'] == uid
                    and row['model_group'] == observed['model'] and row['session_id'] == observed['scope']['chat_id']
                    and (metadata.get('spend_logs_metadata') or {}).get('owui_budget') == observed['scope']
                    and close_amount(row['spend'], CALL_COST) and row.get('status') == 'success'
                    and [row.get(k) for k in ('prompt_tokens','completion_tokens','total_tokens')] == [10,5,15],
                    'Overlap persisted native spend attribution differs')
            positive.append({'request_id': row['request_id'], 'user_id': uid, 'api_key_hash': row['api_key'],
                'model': row['model_group'], 'spend_usd': str(amount(row['spend'])), 'scope': observed['scope']})
        for model in MODELS:
            matches = [key for key in current['keys'] if key['token'] == state['keys'][uid+'|'+model]['hash']]
            require(len(matches) == 1, 'Overlap native key identity is ambiguous')
            info = matches[0]
            count = sum(r['model'] == model for r in selected)
            pending |= not settled(info.get('spend'), count*CALL_COST)
            snapshots.append({'user_id': uid, 'model': model, 'api_key_hash': state['keys'][uid+'|'+model]['hash'],
                              'spend_usd': str(amount(info['spend'])), 'cap_usd': str(amount(info['max_budget']))})
    return None if pending else {'counters': snapshots, 'positive_rows': positive}


def prepare(native, operator):
    require(not STATE.exists(), 'Overlap preparation requires fresh private state')
    webui = read_private(Path('/proof-private/webui-state.private.json'))
    old = set(operator['users']) | {operator['operator_user'], webui['admin']['id'], *(u['id'] for u in webui['users']),
        webui['bootstrap_fixture']['employee']['id'], webui['service_fixture']['payer_id']}
    observed = provider()
    from capture_webui_auth import MAX_RECORDS
    require(len(capture())+11<=MAX_RECORDS,'Existing diagnostic has insufficient capacity for bounded overlap phase')
    require(observed.get('synthetic') is True and all(r.get('lifecycle', {}).get('terminal') is True for r in observed['requests']),
            'Overlap requires a quiescent synthetic provider')
    desired = {'prompt_tokens':10,'completion_tokens':5,'delay_ms':0,'tool_round':False,'admin_mode':False,
               'title_mode':False,'native_tasks_mode':False,'response_status':200,'after_first_chunk_delay_ms':0}
    require(isinstance(observed.get('control'),dict)
            and {'prompt_tokens','completion_tokens','delay_ms','tool_round','admin_mode','title_mode'}<=set(observed['control'])
            and set(observed['control'])<=set(desired),'Synthetic provider controls have an unsupported shape')
    state = {'schema': 1, 'users': {name: str(uuid4()) for name in ('calibration','key','user','other')}, 'keys': {},
             'plan': {}, 'original_control': observed['control'], 'provider_before': observed['requests'],
             'old_users': sorted(old), 'old_before': old_snapshot(native, old)}
    for label, user, model in [('cal_a','calibration',MODELS[0]),('cal_b','calibration',MODELS[1]),
        ('key_hold','key',MODELS[0]),('key_deny','key',MODELS[0]),('key_model','key',MODELS[1]),
        ('key_other','other',MODELS[0]),('key_resume','key',MODELS[0]),
        ('user_hold','user',MODELS[0]),('user_deny','user',MODELS[1]),('user_other','other',MODELS[0]),('user_resume','user',MODELS[1])]:
        state['plan'][label] = {'user': user, 'model': model, 'chat': str(uuid4()), 'answer': str(uuid4())}
    write_private(STATE, state)
    # Keep optional presence unchanged; restoration needs only the saved object
    # and never resets provider history or introduces optional controls.
    provider('POST', '/__proof/control', {key:desired[key] for key in observed['control']})
    create(native, state, 'calibration', Decimal(20), Decimal(10))
    estimates = {model: call(native, state, label)['native_estimate_usd'] for label,model in zip(('cal_a','cal_b'),MODELS)}
    native.poll('calibration native settlement', lambda: reconcile(native,{**state,'users':{'calibration':state['users']['calibration']}}))
    reserve, budget = calibrated_caps(estimates)
    state.update(reserve_usd=str(reserve), budget_usd=str(budget))
    create(native, state, 'key', 2*budget, budget)
    create(native, state, 'user', budget, Decimal(10))
    create(native, state, 'other', Decimal(20), Decimal(10))
    write_private(STATE, state)
    return {'native_estimates': estimates, 'reserve_usd': str(reserve), 'budget_usd': str(budget),
            'actual_cost_usd': str(CALL_COST), 'user_probe_allocation': 'deliberate native-only keys10+10 over userB; not admin policy'}


def held_witness(state, case):
    current = provider()['requests']
    new = [r for r in current if r['id'] not in state[case+'_before_ids']]
    require(len(new) <= 1, 'Unexpected provider arrival before overlap witness')
    if not new: return None
    row = new[0]
    require(row['body'] == {'model': 'goal584-fake-a', **{k:v for k,v in BODY.items() if k != 'stream'}},
            'Held provider context differs')
    require(row.get('lifecycle', {}).get('started') is True and row['lifecycle'].get('terminal') is False,
            'Held provider request is already terminal')
    return {'provider_id': request_id(row['id']), 'started': True, 'terminal': False}


def worker(action, label=None, case=None):
    native, operator = proof()
    if action == 'identity':
        import yaml
        config = yaml.safe_load(Path('/proof/config.yaml').read_text(encoding='utf-8'))
        general, settings = config['general_settings'],config['litellm_settings']
        database=os.environ.get('DATABASE_URL',''); parsed=urlsplit(database)
        require(general.get('coordination_redis')=={'host':'redis','port':6379}
                and general.get('fail_closed_budget_enforcement') is True
                and general.get('custom_auth')=='capture_webui_auth.gateway_auth'
                and settings.get('callbacks') == ['budget_errors.handler', 'pricing_snapshot.handler']
                and settings.get('block_requests_for_models_without_pricing') is True
                and settings.get('num_retries')==config.get('router_settings',{}).get('num_retries')==0
                and settings.get('default_redis_ttl') in (None,60)
                and parsed.hostname=='postgres' and parsed.path=='/goal584'
                and os.environ.get('OWUI_BUDGET_REQUIRE_PROVENANCE','').lower()=='true', 'Native shared DB/Redis/auth configuration differs')
        models=config['model_list']
        require(len(models)==2 and {r['model_name'] for r in models}==set(MODELS)
                and all(r['litellm_params']['api_base']=='http://provider:8000/v1'
                    and r['model_info']['max_output_tokens']==5 and r['model_info']['input_cost_per_token']==.01
                    and r['model_info']['output_cost_per_token']==.02 for r in models), 'Synthetic overlap model/price source differs')
        native.schema()
        return {'files_sha256': {name: hashlib.sha256((Path('/proof')/name).read_bytes()).hexdigest() for name in SOURCE_PATHS},
                'config_sha256': hashlib.sha256(Path('/proof/config.yaml').read_bytes()).hexdigest(),
                'database_url_sha256':hashlib.sha256(database.encode()).hexdigest()}
    if action == 'restore':
        if STATE.exists():
            state = read_private(STATE)
            provider('POST','/__proof/control',state['original_control'])
            require(provider()['control'] == state['original_control'], 'Original provider controls were not restored')
        return {'controls_restored': True}
    if action == 'prepare': return prepare(native, operator)
    state = read_private(STATE)
    if action == 'call':
        require(label in state['plan'] and label.endswith('_hold'), 'Unsupported standalone overlap call')
        return call(native, state, label)
    require(case in ('key','user'), 'Unknown overlap case')
    if action == 'arm':
        state[case+'_before_ids'] = [request_id(r['id']) for r in provider()['requests']]
        write_private(STATE,state)
        provider('POST','/__proof/control',{'delay_ms':3000})
        return {'provider_ids_before': state[case+'_before_ids'], 'delay_ms':3000}
    if action == 'witness':
        witness = native.poll('actual provider arrival', lambda: held_witness(state,case))
        state[case+'_held_id'] = witness['provider_id']; write_private(STATE,state)
        provider('POST','/__proof/control',{'delay_ms':0})
        return witness
    if action == 'contend':
        def still_live():
            rows = [r for r in provider()['requests'] if r['id'] == state[case+'_held_id']]
            require(len(rows)==1 and rows[0]['lifecycle']['terminal'] is False, 'Overlap hold settled before contender guard')
        still_live()
        before_ids = [r['id'] for r in provider()['requests']]
        rejected = call(native,state,case+'_deny',denied=case)
        require([r['id'] for r in provider()['requests']] == before_ids, 'Rejected contender reached provider')
        still_live()
        admitted = [call(native,state,case+'_model')] if case=='key' else []
        admitted.append(call(native,state,case+'_other'))
        still_live()
        return {'rejected':rejected,'isolation_calls':admitted,'held_terminal_after':False}
    if action == 'resume':
        native.poll('held native cost settlement', lambda: reconcile(native,state))
        admitted = call(native,state,case+'_resume')
        counters = native.poll('resumed native settlement', lambda: reconcile(native,state))
        return {'admitted':admitted, **counters}
    if action == 'final':
        financial = native.poll('final native overlap settlement', lambda: reconcile(native,state))
        require(old_snapshot(native,state['old_users']) == state['old_before'], 'Overlap changed prior fixture financial rows')
        calls = results(state); actual = provider()['requests']
        old = {r['id']:r for r in state['provider_before']}
        new = {r['provider_id'] for r in calls if r['outcome']=='success'}
        require(len(calls)==11 and len(new)==9 and len(actual)==len(old)+9
                and {r['id'] for r in actual} == set(old)|new
                and all(r==old[r['id']] for r in actual if r['id'] in old), 'Unexpected physical provider calls or changed prior evidence')
        return {'calls':calls, **financial, 'new_physical_calls':9, 'unexpected_physical_calls':0,
                'old_financial_rows_unchanged':True,'old_financial_sha256':digest(state['old_before'])}
    raise ProofError('Unknown overlap worker action')


class Coordinator:
    def __init__(self,args):
        self.args=args
        self.command=['docker','compose','--project-name',args.project,'--env-file',str(args.env_file.resolve())]
        for path in args.compose_file: self.command.extend(['-f',str(path)])

    def run_json(self,command,timeout=60):
        try: result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=timeout)
        except (OSError,subprocess.SubprocessError): raise ProofError('Overlap subprocess failed or timed out') from None
        require(result.returncode==0 and len(result.stdout)<=1024*1024,'Overlap worker command failed')
        try: value=json.loads(result.stdout)
        except (ValueError,UnicodeError): raise ProofError('Overlap worker returned invalid JSON') from None
        return safe(value)

    def invoke(self,index,action,**values):
        command=self.command+['exec','-T','--index',str(index),'proxy','python','-B','/proof/prove_budget_overlap.py','--worker-action',action]
        for name,value in values.items(): command.extend(['--'+name,str(value)])
        return self.run_json(command)

    def topology(self):
        template='{"id":"{{.Id}}","image_ref":"{{.Config.Image}}","image_id":"{{.Image}}","health":"{{.State.Health.Status}}","number":"{{index .Config.Labels "com.docker.compose.container-number"}}","project":"{{index .Config.Labels "com.docker.compose.project"}}","service":"{{index .Config.Labels "com.docker.compose.service"}}","network_mode":"{{.HostConfig.NetworkMode}}","private_mount":"{{range .Mounts}}{{if eq .Destination "/proof-private"}}{{.Source}}{{end}}{{end}}","command":{{json .Config.Cmd}}}'
        result=subprocess.run(self.command+['ps','-q','proxy'],cwd=ROOT,capture_output=True,timeout=15)
        require(result.returncode==0,'Cannot observe overlap Compose containers')
        ids=result.stdout.decode('ascii').split()
        require(len(ids)==len(set(ids))==2 and all(re.fullmatch('[0-9a-f]{64}',v) for v in ids),'Expected exactly two distinct proxy containers')
        rows=[self.run_json(['docker','inspect','--format',template,identifier]) for identifier in ids]
        expected_command=['--config','/proof/config.yaml','--host','0.0.0.0','--port','4000','--num_workers','1','--telemetry','false']
        require({r['id'] for r in rows}==set(ids) and {r['number'] for r in rows}=={'1','2'} and all(r['image_ref']==native_sdk.image_ref() and r['health']=='healthy'
                and r['project']==self.args.project and r['service']=='proxy' and r['network_mode']==self.args.project+'_proof'
                and r['private_mount']==str(self.args.private_root)
                and r['command']==expected_command for r in rows)
                and len({r['image_id'] for r in rows})==1,'Proxy topology/image/health binding differs')
        identities=[self.invoke(i,'identity') for i in (1,2)]
        expected={name:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for name,path in SOURCE_PATHS.items()}
        require(all(r['files_sha256']==expected for r in identities) and identities[0]['config_sha256']==identities[1]['config_sha256'],
                'Proxy mounted source/config identity differs')
        require(identities[0]['database_url_sha256']==identities[1]['database_url_sha256'],'Proxy workers use different database connections')
        native_code = "import json,sys;sys.path.insert(0,'/proof');import native_floor_identity as n;print(json.dumps(n.inspect_sources()))"
        sdk = [self.run_json(self.command + ['exec','-T','--index',str(i),'proxy','python','-B','-c',native_code]) for i in (1,2)]
        expected_sdk = native_sdk.selected_hashes({key.removeprefix('litellm/'):value for key,value in native_sdk.load_manifest()['native_export_sha256'].items()})
        require(all(value == {'native_sha256':expected_sdk,'native_artifact':native_sdk.identity()} for value in sdk),
                'Overlap workers native source/artifact identity differs')
        if native_sdk.variant() != 'stock':
            require(all(row['image_id'] == native_sdk.image_ref() for row in rows), 'Overlap derivative image ID differs')
        provider_source = self.run_json(self.command+['exec','-T','provider','python','-c',
            "import hashlib,json;from pathlib import Path;print(json.dumps({'mock_provider.py':hashlib.sha256(Path('/proof/mock_provider.py').read_bytes()).hexdigest()}))"])
        require(provider_source == {'mock_provider.py': hashlib.sha256((ROOT/PROVIDER_SOURCE).read_bytes()).hexdigest()},
                'Provider mounted source identity differs')
        return {'containers':rows,'source_sha256':expected,'provider_source_sha256':provider_source, 'native_sdk':sdk,
                'config_sha256':identities[0]['config_sha256']}

    def execute(self,receipt):
        receipt['topology']=self.topology()
        try:
            receipt['calibration']=self.invoke(1,'prepare')
            with ThreadPoolExecutor(max_workers=1) as executor:
                for case in ('key','user'):
                    receipt['stage']=case+'_arm'
                    arm=self.invoke(1,'arm',case=case)
                    held=executor.submit(self.invoke,1,'call',label=case+'_hold')
                    try:
                        witness=self.invoke(2,'witness',case=case)
                        require(not held.done(),'Client future settled before provider overlap witness')
                        receipt[case]={'arm':arm,'witness':witness,'client_future_unfinished':True}
                        receipt['stage']=case+'_contend'
                        receipt[case]['contenders']=self.invoke(2,'contend',case=case)
                        require(not held.done(),'Client future settled before isolation observations')
                    finally:
                        # Await the admitted native request even after a later guard fails;
                        # cancellation and control restoration must not fake settlement.
                        completion=held.result(timeout=45)
                        receipt.setdefault(case,{})['held_result']=completion
                    require(completion['provider_id']==witness['provider_id'],'Held response/provider witness identity differs')
                    settled_at=time.monotonic()
                    receipt[case]['resume']=self.invoke(2,'resume',case=case)
                    elapsed=time.monotonic()-settled_at
                    receipt[case]['resume_after_held_seconds']=elapsed
                    require(elapsed<15,'Native reservation recovery exceeded the bounded no-TTL-wait profile')
            receipt['stage']='final_reconciliation'
            receipt['final']=self.invoke(1,'final',case='key')
        finally:
            receipt['controls']=self.invoke(1,'restore')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-action',choices=('identity','prepare','arm','witness','call','contend','resume','final','restore'))
    parser.add_argument('--label');parser.add_argument('--case',choices=('key','user'))
    parser.add_argument('--env-file',type=Path);parser.add_argument('--project')
    parser.add_argument('--compose-file',action='append',default=[]);parser.add_argument('--receipt',type=Path)
    args=parser.parse_args()
    receipt={'schema':1,'proof':'goal584-two-native-process-budget-overlap','passed':False,
        'not_qualified':['WebUI','cancellation','restart','calendar','Redis_data_loss','production','paid_provider']}
    output_valid=False
    try:
        if args.worker_action:
            result=worker(args.worker_action,args.label,args.case)
        else:
            require(args.env_file and args.env_file.is_file() and args.receipt and not args.receipt.exists()
                    and re.fullmatch('[a-z0-9][a-z0-9_-]{1,63}',args.project or '') and args.compose_file,
                    'Host overlap arguments are incomplete')
            require(args.env_file.resolve()!=args.receipt.resolve(),'Safe overlap receipt overlaps credentials')
            values=dict(line.split('=',1) for line in args.env_file.read_text(encoding='utf-8').splitlines() if line and not line.startswith('#'))
            private=Path(values.get('PROOF_PRIVATE_DIR',''))
            require(private.is_absolute() and private.is_dir() and not private.is_symlink()
                    and not args.receipt.resolve().is_relative_to(private.resolve())
                    and not private.resolve().is_relative_to(args.receipt.resolve().parent), 'Safe overlap receipt overlaps private fixture root')
            require(all((ROOT/path).resolve().is_relative_to(ROOT) and (ROOT/path).is_file() for path in args.compose_file),
                    'Overlap Compose source escaped this checkout')
            if os.name=='posix':
                require(stat.S_IMODE(private.stat().st_mode)&0o077==0 and stat.S_IMODE(args.env_file.stat().st_mode)&0o077==0,
                        'Overlap private fixture permissions are unsafe')
            args.private_root=private.resolve()
            output_valid=True
            Coordinator(args).execute(receipt)
            receipt['stage']='qualified_native_overlap'
            receipt['passed']=True;result=receipt
        print(json.dumps(safe(result),allow_nan=False))
        if not args.worker_action:
            args.receipt.parent.mkdir(parents=True,exist_ok=True)
            args.receipt.write_text(json.dumps(safe(receipt),indent=2)+'\n',encoding='utf-8')
        return 0
    except Exception as error:
        receipt['passed']=False
        receipt['failure']=str(error) if isinstance(error,ProofError) else 'Overlap fixture failure: '+type(error).__name__
        print(json.dumps(safe(receipt)))
        if output_valid:
            args.receipt.parent.mkdir(parents=True,exist_ok=True)
            args.receipt.write_text(json.dumps(safe(receipt),indent=2)+'\n',encoding='utf-8')
        return 1


if __name__=='__main__': raise SystemExit(main())
