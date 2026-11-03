#!/usr/bin/env python3
"""Disposable native RAG HTTP text/query proof, never a pricing/ledger owner.

Host mode reuses Fixture/PricingFixture for the existing isolated Compose owner.
Worker mode uses the existing WebUI, NativeProof and structural service reader.
Only the parent enables mounts/vector infrastructure; this file never runs it
implicitly, writes a DB, resets provider history or deletes financial objects.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
from decimal import Decimal
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request
from uuid import uuid4

from prove_native_budgets import ProofError, amount, close_amount, require, expected_budget_message

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = Path('/proof-private')
STATE = PRIVATE / 'webui-state.private.json'
RAG_STATE = PRIVATE / 'rag-state.private.json'
CONFIG = Path('/proof/config.yaml')
BACKUP = PRIVATE / 'rag-original-config.yaml'
MODEL = 'goal584-e'
WIRE = 'goal584-fake-e'
DEPLOYMENT = 'goal584-deployment-e'
RAG = '/api/v1/retrieval'
SCOPE = {'schema': 1, 'category': 'service', 'operation': 'rag_embedding'}
ACCESS_PROHIBITED = 'You do not have permission to access this resource. Please contact your administrator for assistance.'
MAX_BYTES = 4 * 1024 * 1024
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}')
CREDENTIAL = re.compile(r'(?:sk-|gw-)[A-Za-z0-9_-]{16,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
LIMITS = ['native RAG HTTP text/query only; no File upload GUI',
          'exactly one proxy in serial RAG phase; no two-proxy RAG qualification',
          'serial causal attribution; no intrinsic provider/native cross-network embedding response ID',
          'selected four personal payers plus existing service payer only; other/unattributed rows excluded',
          'no chat/actor provenance tag on embeddings; optional forwarded headers are not authority',
          'no concurrency/calendar/cancel/failure recovery/global privacy/production/paid-provider qualification']
ENV_OBSERVATION = '''import hashlib,json,os
fields=('VECTOR_DB','PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH','PGVECTOR_PGCRYPTO','USE_SLIM_DOCKER',
        'RAG_EMBEDDING_CONTENT_PREFIX','RAG_EMBEDDING_QUERY_PREFIX','RAG_EMBEDDING_PREFIX_FIELD_NAME')
print(json.dumps({'values':{k:os.environ.get(k) for k in fields},
 'vector_url_sha256':hashlib.sha256(os.environ.get('PGVECTOR_DB_URL','').encode()).hexdigest(),
 'sqlite_metadata_default':not os.environ.get('DATABASE_URL')}))
'''


def encoded(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
    require(len(raw) <= MAX_BYTES, 'RAG evidence exceeded bounded JSON size')
    return raw


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def safe(value, secrets=()):
    text = encoded(value).decode()
    require(CREDENTIAL.search(text) is None and not any(secret and secret in text for secret in secrets),
            'Credential-bearing RAG evidence suppressed')
    return value


def identifier(value):
    require(isinstance(value, str) and ID.fullmatch(value) is not None, 'Native RAG identity is malformed')
    return value


def embedding_readiness(provider, context, max_records):
    """Admit the actual embedding branch, preserving unrelated chat controls."""
    require(isinstance(provider, dict) and provider.get('synthetic') is True
            and isinstance(provider.get('control'), dict) and isinstance(provider.get('requests'), list)
            and isinstance(context, dict) and isinstance(context.get('requests'), list)
            and len(context['requests']) + 4 <= max_records, 'RAG requires bounded existing provider/context observations')
    controls = provider['control']
    delay, status = controls.get('delay_ms'), controls.get('response_status', 200)
    require(type(delay) is int and delay == 0 and type(status) is int and status == 200
            and all(isinstance(row, dict) and row.get('lifecycle', {}).get('terminal') is True for row in provider['requests']),
            'RAG requires quiescent provider and successful undelayed embedding controls')
    ids = [identifier(row.get('id')) for row in provider['requests']]
    require(len(ids) == len(set(ids)), 'RAG prior provider observations duplicated IDs')
    # Native Handler.begin_record(embedding=True) fixes usage10; embeddings calls
    # controlled_failure (delay/status), then send_json. Chat admin/tool/title,
    # chat token counts and after-first-chunk controls do not alter this path.
    return {'effective_embedding_controls': {'delay_ms': delay, 'response_status': status},
            'preserved_control_sha256': digest(controls), 'prior_provider_ids': ids,
            'prior_context_count': len(context['requests']), 'prior_provider_quiescent': True}


def settings_denied(status, body):
    require(status == 401 and body == {'detail': ACCESS_PROHIBITED},
            'Ordinary RAG settings response differs from the native role guard')


def serial_proxy(fixture):
    """Observe the existing Compose owner; parent normalizes scale beforehand."""
    import subprocess
    try:
        result = subprocess.run(fixture.command + ['ps', '-q', 'proxy'], cwd=ROOT, capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        raise ProofError('RAG proxy topology observation unavailable') from None
    require(result.returncode == 0 and len(result.stdout) <= 1024, 'RAG proxy topology observation failed')
    identifiers = result.stdout.decode('ascii').splitlines()
    require(len(identifiers) == 1 and re.fullmatch(r'[0-9a-f]{64}', identifiers[0]) is not None,
            'Serial RAG requires exactly one existing running proxy; parent owns scale normalization')
    return {'running_proxy_count': 1, 'running_proxy_container_ids': identifiers}


def append_embedding(raw):
    """Insert one literal local fixture block; preserve every original byte."""
    require(0 < len(raw) <= 131072, 'Native RAG config exceeded fixture bound')
    text = raw.decode('utf8')
    require(re.findall(r'(?m)^  - model_name: (\S+)\r?$', text) == ['goal584-a', 'goal584-b']
            and len(re.findall(r'(?m)^general_settings:\r?$', text)) == 1,
            'RAG requires exactly the existing two native model blocks')
    newline = '\r\n' if '\r\n' in text else '\n'
    block = '\n'.join(['  - model_name: goal584-e', '    litellm_params:',
        '      model: openai/goal584-fake-e', '      api_base: http://provider:8000/v1',
        '      api_key: synthetic-provider-only-not-a-credential', '    model_info:',
        '      id: goal584-deployment-e', '      mode: embedding', '      max_tokens: 10',
        '      max_input_tokens: 10', '      max_output_tokens: 0',
        '      input_cost_per_token: 0.01', '      output_cost_per_token: 0.0', '', '']).replace('\n', newline)
    at = re.search(r'(?m)^general_settings:\r?$', text).start()
    return (text[:at] + block + text[at:]).encode('utf8')


def validate_config(original, current):
    """Actual private YAML parser, not a second runtime catalog."""
    import yaml
    require(current == append_embedding(original), 'RAG config changed outside the appended E block')
    old, new = (yaml.safe_load(raw) for raw in (original, current))
    require(isinstance(old, dict) and isinstance(new, dict) and set(old) == set(new)
            and new['model_list'][:2] == old['model_list'] and len(new['model_list']) == 3
            and all(new[key] == value for key, value in old.items() if key != 'model_list'),
            'RAG config did not preserve the native configuration owner')
    for item, alias in zip(old['model_list'], ('goal584-a', 'goal584-b')):
        p, m = item['litellm_params'], item['model_info']
        require(item['model_name'] == alias and p['api_base'] == 'http://provider:8000/v1'
                and p['model'] == 'openai/goal584-fake-' + alias[-1]
                and p['api_key'] == 'synthetic-provider-only-not-a-credential'
                and m['input_cost_per_token'] == .01 and m['output_cost_per_token'] == .02
                and m['id'] == 'goal584-deployment-' + alias[-1], 'RAG requires restored original A/B fixture rates/routes')
    require(new['general_settings'].get('store_prompts_in_spend_logs') is False
            and new['general_settings'].get('custom_auth') == 'capture_webui_auth.gateway_auth'
            and new['general_settings'].get('custom_auth_run_common_checks') is True
            and new['general_settings'].get('fail_closed_budget_enforcement') is True,
            'RAG requires the existing native enforcement and observation configuration')
    return {'original_sha256': hashlib.sha256(original).hexdigest(), 'active_sha256': hashlib.sha256(current).hexdigest(),
            'other_native_configuration_unchanged': True}


def rag_update(original, key=None):
    names = ('RAG_EMBEDDING_ENGINE', 'RAG_EMBEDDING_MODEL', 'RAG_EMBEDDING_BATCH_SIZE',
             'ENABLE_ASYNC_EMBEDDING', 'RAG_EMBEDDING_CONCURRENT_REQUESTS',
             'openai_config', 'ollama_config', 'azure_openai_config')
    require(isinstance(original, dict) and original.get('status') is True and all(name in original for name in names),
            'Native protected RAG config is incomplete')
    body = {name: copy.deepcopy(original[name]) for name in names}
    if key is not None:
        require(isinstance(key, str) and key.startswith('sk-'), 'Native E secret is missing')
        body.update(RAG_EMBEDDING_ENGINE='openai', RAG_EMBEDDING_MODEL=MODEL,
                    RAG_EMBEDDING_BATCH_SIZE=1, ENABLE_ASYNC_EMBEDDING=True, RAG_EMBEDDING_CONCURRENT_REQUESTS=0,
                    openai_config={'url': 'http://proxy:4000/v1', 'key': key})
    return body


def row_evidence(raw, payer, key_hash, validate_scope):
    metadata = raw.get('metadata')
    if isinstance(metadata, str):
        require(len(metadata.encode()) <= MAX_BYTES, 'Native RAG metadata exceeded bound')
        metadata = json.loads(metadata)
    require(isinstance(metadata, dict), 'Native RAG metadata is absent')
    scope = validate_scope((metadata.get('spend_logs_metadata') or {}).get('owui_budget'))
    call_id = identifier(metadata.get('litellm_call_id'))
    request_id = identifier(raw.get('request_id'))
    require(scope == SCOPE and raw.get('user') == payer and raw.get('api_key') == key_hash
            and raw.get('model_group') == MODEL and raw.get('model') in (WIRE, 'openai/' + WIRE)
            and raw.get('model_id') == DEPLOYMENT and raw.get('status') == 'success'
            and close_amount(raw.get('spend'), Decimal('.10'))
            and all(type(raw.get(name)) is int for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'))
            and [raw[name] for name in ('prompt_tokens', 'completion_tokens', 'total_tokens')] == [10, 0, 10]
            and raw.get('session_id') in (None, ''), 'Native RAG row payer/key/model/usage/cost/scope differs')
    # EmbeddingResponse has no provider ID: native get_spend_logs_id selects
    # standard logging ID, otherwise actual litellm_call_id. Retain both as read.
    return safe({'request_id': request_id, 'litellm_call_id': call_id, 'user_id': payer,
        'api_key_hash': key_hash, 'model': raw['model'], 'model_group': MODEL, 'model_id': raw['model_id'],
        'status': raw['status'], 'spend_usd': str(amount(raw['spend'])),
        'usage': {name: raw[name] for name in ('prompt_tokens', 'completion_tokens', 'total_tokens')},
        'scope': scope, 'session_id': raw.get('session_id')})


def same_history(before, after):
    old, new = ({row['request_id']: row for row in value['history']} for value in (before, after))
    require(len(old) == len(before['history']) and len(new) == len(after['history'])
            and old.keys() <= new.keys() and all(new[key] == value for key, value in old.items()),
            'Native RAG proof lost or changed historical rows')
    return [row for key, row in new.items() if key not in old]


def verify_finance(before, after, payer, *, count, cap='20'):
    """Observed native counters vs fixture constants; never token/rate math."""
    require(type(count) is int and count in (0, 1, 2) and cap in ('0', '20'), 'Unsupported bounded RAG financial phase')
    added = same_history(before, after)
    positive = [row for row in added if amount(row['spend_usd']) > 0]
    require(len(positive) <= count and all(row['user_id'] == payer and row['model_group'] == MODEL for row in added),
            'RAG attempt changed unrelated native history')
    previous, current = ({v['user_id']: v for v in value['budgets']} for value in (before, after))
    require(previous.keys() == current.keys() and len(current) == 5, 'RAG financial scope changed')
    for uid in previous:
        if uid != payer:
            require(current[uid] == previous[uid]
                    and [r for r in before['history'] if r['user_id'] == uid] == [r for r in after['history'] if r['user_id'] == uid],
                    'RAG altered a personal payer/key/history')
    old, new = copy.deepcopy(previous[payer]), copy.deepcopy(current[payer])
    old_models, new_models = ({v['model']: v for v in value.pop('models')} for value in (old, new))
    require(set(old_models) == set(new_models) == {'goal584-a', MODEL}
            and old_models['goal584-a'] == new_models['goal584-a'], 'RAG changed native service A assignment')
    delta = (Decimal('0'), Decimal('.10'), Decimal('.20'))[count]
    ready = close_amount(new.pop('spend'), amount(old.pop('spend')) + delta)
    require(new == old, 'RAG changed native service User protected budget fields')
    a, b = copy.deepcopy(old_models[MODEL]), copy.deepcopy(new_models[MODEL])
    key_ready = close_amount(b.pop('spend'), amount(a.pop('spend')) + delta)
    ready = ready and key_ready
    require(amount(a.pop('max_budget')) == 20 and amount(b.pop('max_budget')) == amount(cap),
            'RAG E cap differs from the selected cap-only phase')
    require(b == a, 'RAG changed E identity/period/cap/blocked fields')
    return len(positive) == count and ready


def causal_call(provider_before, provider_after, context_before, context_after, *, key_hash, payer, expected_input):
    require(provider_before['synthetic'] is provider_after['synthetic'] is True
            and provider_before['control'] == provider_after['control']
            and provider_after['requests'][:-1] == provider_before['requests']
            and len(provider_after['requests']) == len(provider_before['requests']) + 1
            and context_after['requests'][:-1] == context_before['requests']
            and len(context_after['requests']) == len(context_before['requests']) + 1,
            'RAG phase is not exactly one isolated new physical/auth attempt')
    record, observation = provider_after['requests'][-1], context_after['requests'][-1]
    expected = {'model': MODEL, 'input': [expected_input]}
    require(observation.get('route') == '/v1/embeddings' and observation.get('body') == expected
            and observation.get('body_after_auth') == expected and 'auth_failure' not in observation
            and observation.get('native_auth_user_id') == payer and observation.get('native_auth_key_hash') == key_hash
            and set(observation) <= {'body', 'body_after_auth', 'route', 'native_estimated_max_cost_usd', '_observation_id',
                'native_auth_user_id', 'native_auth_key_hash', 'provenance_removed_after', 'unverified_rag_scope'},
            'Native RAG auth changed input or did not resolve the actual E assignment')
    require(record.get('route') == '/v1/embeddings' and record.get('id_kind') == 'provider_observation_only'
            and isinstance(record.get('id'), str) and re.fullmatch(r'embedding-observation-goal584-[0-9a-f]{32}', record['id'])
            and record.get('body') == {'model': WIRE, 'input': [expected_input]}
            and record.get('usage') == {'prompt_tokens': 10, 'total_tokens': 10}
            and record.get('lifecycle', {}).get('terminal') is True
            and record['lifecycle'].get('outcome') == 'completed', 'Actual RAG provider body/terminal/usage differs')
    response = record.get('response')
    require(isinstance(response, dict) and set(response) == {'object', 'data', 'model', 'usage'}
            and response['object'] == 'list' and response['model'] == WIRE and response['usage'] == record['usage']
            and len(response['data']) == 1, 'Actual embedding provider response differs')
    item = response['data'][0]
    require(isinstance(item, dict) and set(item) == {'object', 'index', 'embedding'}
            and item['object'] == 'embedding' and type(item['index']) is int and item['index'] == 0
            and isinstance(item['embedding'], list) and len(item['embedding']) == 3
            and all(type(v) in (int, float) and math.isfinite(v) for v in item['embedding']),
            'Actual native RAG vector is not a finite 3D vector')
    return {'provider_observation_id': record['id'], 'provider_response_has_no_id': True,
            'auth_observation': copy.deepcopy(observation), 'provider_observation': copy.deepcopy(record)}


def retrieved(result, collection, text, actor):
    require(isinstance(result, dict) and set(result) <= {'ids', 'distances', 'documents', 'metadatas'}
            and result.get('documents') == [[text]] and isinstance(result.get('ids'), list)
            and len(result['ids']) == 1 and len(result['ids'][0]) == 1,
            'Native RAG query did not retrieve the actual stored synthetic text')
    identifier(result['ids'][0][0])
    distances, metadata = result.get('distances'), result.get('metadatas')
    require(isinstance(distances, list) and len(distances) == 1 and len(distances[0]) == 1
            and type(distances[0][0]) in (int, float) and math.isfinite(distances[0][0])
            and isinstance(metadata, list) and len(metadata) == 1 and len(metadata[0]) == 1
            and isinstance(metadata[0][0], dict) and metadata[0][0].get('created_by') == actor
            and metadata[0][0].get('embedding_config') == str({'engine': 'openai', 'model': MODEL}),
            'Native RAG retrieval distance/owner/embedding configuration differs')
    return {'collection_name': collection, 'chunk_ids': result['ids'][0], 'document_sha256': hashlib.sha256(text.encode()).hexdigest(),
            'distance': distances[0][0], 'actual_text_equal': True, 'native_owner_equal': True,
            'native_metadata_encoding': 'native process_metadata dict-to-string'}


def worker_dependencies():
    # Existing /proof mounts and aliases; no native proxy_server globals/import bootstrap.
    from aiohttp import ClientSession
    from employee_budget_admin_client import BudgetAdminClient
    from employee_budget_assignment import assignment_alias, assignment_metadata, assignment_matches
    from provenance import validate_persisted_rag_scope
    from prove_background_tasks import project_budget
    from prove_service_tasks import provider, response, canonical
    from provision_webui import WebUI, native_client, read_private, write_private, PROXY_URL, TASK_FLAGS, WEBUI_URL
    from provision_cost_display import FILTER_ID
    import capture_webui_auth as capture
    return locals()


class Worker:
    def __init__(self):
        self.d = worker_dependencies()
        self.state = self.d['read_private'](STATE)
        self.webui = self.d['WebUI']()
        self.native = self.d['native_client'](self.state)
        self.payer = self.d['canonical'](self.state['service_fixture']['payer_id'])
        self.people = [*self.state['users'], self.state['admin'], self.state['bootstrap_fixture']['employee']]
        require(len({v['id'] for v in self.people} | {self.payer}) == 5, 'RAG requires four personal and one separate existing service payer')
        self.secrets = [self.native.master_key]
        for v in self.people:
            self.secrets.extend(v.get(k, '') for k in ('token', 'password'))
        if RAG_STATE.exists():
            self.rag = self.d['read_private'](RAG_STATE)
            self.secrets.append(self.rag.get('key', ''))
        else:
            self.rag = {}

    def save(self, stage):
        self.rag['stage'] = stage
        self.d['write_private'](RAG_STATE, self.rag)

    def api(self, method, path, body=None, *, actor=False):
        account = self.state['users'][0] if actor else self.state['admin']
        self.webui.session(account, 'user' if actor else 'admin')
        return self.d['response'](self.webui, method, RAG + path, account['token'], body)

    def captures(self):
        capture = self.d['capture']
        with capture.capture_lock():
            value = capture._read_locked()
        return self.d['provider'](), value

    def snapshot(self):
        async def read():
            async with self.d['ClientSession'](trust_env=False) as session:
                client = self.d['BudgetAdminClient'](session, self.d['PROXY_URL'], self.native.master_key)
                return [*[await client.read_employee(p['id'], ('goal584-a', 'goal584-b')) for p in self.people],
                        await client.read_service(self.payer)]
        budgets = asyncio.run(read())
        history, rag_rows = [], []
        for budget in budgets:
            for row in self.native.logs(budget.user_id):
                identifier(row.get('request_id'))
                require(amount(row.get('spend')) >= 0, 'RAG history has negative spend')
                history.append({'request_id': row['request_id'], 'user_id': budget.user_id,
                    'model_group': row.get('model_group'), 'spend_usd': str(amount(row['spend'])), 'full_row_sha256': digest(row)})
                if row.get('model_group') == MODEL and amount(row['spend']) > 0:
                    rag_rows.append(row_evidence(row, self.payer, self.rag['key_hash'], self.d['validate_persisted_rag_scope']))
        result = {'budgets': sorted([self.d['project_budget'](v) for v in budgets], key=lambda v: v['user_id']),
                  'history': sorted(history, key=lambda v: v['request_id']), 'rag_rows': sorted(rag_rows, key=lambda v: v['request_id'])}
        require(len({v['request_id'] for v in history}) == len(history), 'RAG history duplicated native request IDs')
        return safe(result, self.secrets)

    def prepare(self):
        require(not self.rag and self.state.get('stage') == 'setup_complete'
                and self.state.get('background_fixture', {}).get('stage') == 'qualified_automatic_background',
                'RAG requires fresh state after completed background proof')
        self.native.schema()
        actor = self.state['users'][0]
        signed = self.webui.ok('POST', '/api/v1/auths/signin', body={'email': actor['email'], 'password': actor['password']})
        require(signed.get('id') == actor['id'] and signed.get('role') == 'user' and isinstance(signed.get('token'), str),
                'RAG ordinary fresh login differs')
        actor['token'] = signed['token']; self.secrets.append(actor['token'])
        self.d['write_private'](STATE, self.state)
        self.webui.session(actor, 'user')
        # Service is native-only; the existing Function owns its configured identity.
        common = self.webui.ok('GET', '/api/v1/functions/id/' + self.d['FILTER_ID'] + '/valves', token=self.state['admin']['token'])
        require(common.get('service_payer_id') == self.payer, 'RAG payer differs from the existing protected service configuration')
        tasks = self.webui.ok('GET', '/api/v1/tasks/config', token=self.state['admin']['token'])
        require(all(tasks.get(v) is False for v in self.d['TASK_FLAGS']), 'RAG requires settled disabled automatic tasks')
        p, c = self.captures()
        readiness = embedding_readiness(p, c, self.d['capture'].MAX_RECORDS)
        before = self.snapshot()
        service = next(v for v in before['budgets'] if v['user_id'] == self.payer)
        require(len(service['models']) == 1 and service['models'][0]['model'] == 'goal584-a'
                and close_amount(service['models'][0]['spend'], Decimal('.80'))
                and amount(service['max_budget']) == 20 and service['budget_duration'] == '1mo',
                'RAG requires the unchanged existing service A 0.80/20 monthly fixture')
        # Wait for all materialized counters, not merely green previous receipts.
        for budget in before['budgets']:
            for entry in [budget, *budget['models']]:
                rows = [r for r in before['history'] if r['user_id'] == budget['user_id']
                        and ('model' not in entry or r['model_group'] == entry['model'])]
                require(close_amount(entry['spend'], sum((amount(r['spend_usd']) for r in rows), Decimal(0))),
                        'RAG requires prior native counters settled against retained history')
        status, original = self.api('GET', '/embedding')
        require(status == 200, 'Native protected RAG config read failed')
        rag_update(original)
        self.rag = {'schema': 1, 'payer': self.payer, 'actor': actor['id'], 'original_rag': original,
            'baseline': before, 'original_native_user': self.native.user_info(self.payer), 'tasks_sha256': digest(tasks),
            'provider_baseline': p, 'context_baseline': c, 'embedding_readiness': readiness,
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        self.save('prepared')
        return {'baseline': before, 'protected_rag_sha256': digest(original), 'actor_id': actor['id'], 'payer_id': self.payer,
                'source_sha256': self.rag['source_sha256'], 'provider_request_count': len(p['requests']), 'context_count': len(c['requests']),
                'embedding_readiness': readiness}

    def configure(self):
        require(self.rag.get('stage') == 'prepared', 'RAG configuration requires prepared state')
        config = validate_config(BACKUP.read_bytes(), CONFIG.read_bytes())
        before = self.native.user_info(self.payer)
        require(before == self.rag['original_native_user'] and before.get('user_role') == 'internal_user'
                and before.get('models') == ['goal584-a'], 'Existing native service identity changed before RAG setup')
        self.save('updating_native_user_models')
        self.native.ok('POST', '/user/update', body={'user_id': self.payer, 'models': ['goal584-a', MODEL]})
        user = self.native.user_info(self.payer)
        self.rag['observed_native_user_after_update'] = user
        self.save('validating_native_user_models')
        require(user.get('models') == ['goal584-a', MODEL]
                and {k: v for k, v in user.items() if k not in ('models', 'updated_at')} ==
                    {k: v for k, v in before.items() if k not in ('models', 'updated_at')},
                'Native service model update changed other protected User fields')
        self.save('creating_canonical_e_key')
        created = self.native.ok('POST', '/key/generate', body={'user_id': self.payer, 'models': [MODEL],
            'key_alias': self.d['assignment_alias'](self.payer, MODEL),
            'metadata': {**self.d['assignment_metadata'](MODEL), 'spend_logs_metadata': {'owui_budget': SCOPE}},
            'max_budget': 20, 'budget_duration': '1mo', 'spend': 0, 'blocked': False,
            'allowed_routes': ['/v1/embeddings'], 'duration': None, 'team_id': None, 'budget_id': None, 'send_invite_email': False})
        key = created.get('key')
        require(isinstance(key, str) and re.fullmatch(r'sk-[A-Za-z0-9_-]{16,}', key), 'Native generated E secret is unavailable')
        self.rag.update(key=key, key_hash=hashlib.sha256(key.encode()).hexdigest(), config=config)
        self.secrets.append(key); self.save('reading_canonical_e_key')
        info = self.native.ok('GET', '/key/info', query={'key': self.rag['key_hash']}).get('info')
        self.rag['native_e_info'] = info
        self.save('validating_canonical_e_key')
        from types import SimpleNamespace
        require(isinstance(info, dict) and self.d['assignment_matches'](SimpleNamespace(**info), self.payer, MODEL)
                and info.get('allowed_routes') == ['/v1/embeddings'] and info.get('expires') is None
                and info.get('budget_id') is None and info.get('metadata') ==
                    {**self.d['assignment_metadata'](MODEL), 'spend_logs_metadata': {'owui_budget': SCOPE}},
                'Native E key assignment/routes/fixed metadata readback differs')
        configured = self.snapshot()
        require(same_history(self.rag['baseline'], configured) == [], 'E setup changed financial history')
        initial = copy.deepcopy(self.rag['baseline']['budgets'])
        actual = copy.deepcopy(configured['budgets'])
        service = next(v for v in actual if v['user_id'] == self.payer)
        e = next(v for v in service['models'] if v['model'] == MODEL)
        require(e['key_hash'] == self.rag['key_hash'] and amount(e['max_budget']) == 20 and amount(e['spend']) == 0
                and e['budget_duration'] == '1mo' and e['budget_reset_at'] and e['blocked'] is False,
                'Native initial E budget fields differ')
        service['models'] = [v for v in service['models'] if v['model'] != MODEL]
        require(initial == actual, 'E setup changed personal or existing service financial DTOs')
        self.rag['configured_baseline'] = configured
        self.save('configuring_protected_rag')
        status, _ = self.api('POST', '/embedding/update', rag_update(self.rag['original_rag'], key))
        require(status == 200, 'Protected native RAG config update failed')
        status, active = self.api('GET', '/embedding')
        require(status == 200 and rag_update(active) == rag_update(self.rag['original_rag'], key),
                'Protected native RAG config readback differs')
        get_status, get_body = self.api('GET', '/embedding', actor=True)
        settings_denied(get_status, get_body)
        self.webui.session(self.state['users'][0], 'user')
        post_status, post_body = self.api('POST', '/embedding/update',
            {'RAG_EMBEDDING_ENGINE': 'openai', 'RAG_EMBEDDING_MODEL': MODEL}, actor=True)
        settings_denied(post_status, post_body)
        self.webui.session(self.state['users'][0], 'user')
        self.rag['ordinary_settings_denied'] = {'get': get_status, 'post': post_status,
            'detail': ACCESS_PROHIBITED, 'same_actor_valid_user_session_before_and_after': True}
        self.rag['active_rag_sha256'] = digest(active)
        self.save('rag_active')
        return configured

    def settle(self, baseline, count, *, cap='20'):
        def observe():
            value = self.snapshot()
            return value if verify_finance(baseline, value, self.payer, count=count, cap=cap) else None
        return self.native.poll('RAG actual journal and User/key counters', observe)

    def run(self, receipt):
        before = self.configure()
        actor = self.state['users'][0]['id']
        nonce = uuid4().hex[:12]
        collection = f'web-search-{actor}-{nonce}'
        text = 'proof ' + nonce[:8]
        self.rag.update(collection=collection, fixture_text=text)
        self.save('text_request')
        p0, c0 = self.captures()
        status, stored = self.api('POST', '/process/text', {'name': 'GOAL584 RAG synthetic', 'content': text, 'collection_name': collection}, actor=True)
        require(status == 200 and stored == {'status': True, 'collection_name': collection, 'content': text},
                'Native ordinary RAG process/text response differs')
        after_text = self.settle(before, 1)
        p1, c1 = self.captures()
        prefix = self.native_prefixes()
        receipt['text'] = causal_call(p0, p1, c0, c1, key_hash=self.rag['key_hash'], payer=self.payer,
                                     expected_input=(prefix['content'] or '') + text)
        receipt['text']['native_rows'] = after_text['rag_rows']
        self.save('query_request')
        status, result = self.api('POST', '/query/doc', {'collection_name': collection, 'query': text, 'k': 1, 'hybrid': False}, actor=True)
        require(status == 200, 'Native ordinary RAG query/doc failed')
        after_query = self.settle(before, 2)
        p2, c2 = self.captures()
        receipt['query'] = causal_call(p1, p2, c1, c2, key_hash=self.rag['key_hash'], payer=self.payer,
                                      expected_input=(prefix['query'] or '') + text)
        receipt['query']['retrieval'] = retrieved(result, collection, text, actor)
        prior_ids = {row['request_id'] for row in after_text['rag_rows']}
        receipt['query']['native_rows'] = [row for row in after_query['rag_rows'] if row['request_id'] not in prior_ids]
        require(len(receipt['text']['native_rows']) == len(receipt['query']['native_rows']) == 1,
                'RAG serial phase did not identify exactly one new native row')
        require(len(after_query['rag_rows']) == 2 and len({v['litellm_call_id'] for v in after_query['rag_rows']}) == 2,
                'RAG two requests did not produce two distinct native Logging call IDs')
        receipt.update(baseline=before, after_text=after_text, after_query=after_query, native_prefixes=prefix)
        self.hard_zero(after_query, receipt)
        tasks = self.webui.ok('GET', '/api/v1/tasks/config', token=self.state['admin']['token'])
        require(digest(tasks) == self.rag['tasks_sha256'], 'RAG proof changed native TaskConfig')
        status, active = self.api('GET', '/embedding')
        require(status == 200 and digest(active) == self.rag['active_rag_sha256'], 'Protected RAG settings changed during proof')
        self.save('qualified_native_rag_http_text_query')
        receipt.update(payer_id=self.payer, actor_id=actor, collection_name=collection, e_key_hash=self.rag['key_hash'],
            service_a_unchanged=True, four_personal_payers_unchanged=True, old_full_row_hashes_retained=True,
            config=self.rag['config'], active_rag_sha256=self.rag['active_rag_sha256'],
            success_e_lifetime='active until disposable environment teardown', native_task_config_unchanged=True,
            ordinary_settings_denied=self.rag['ordinary_settings_denied'])

    def native_prefixes(self):
        # Values are module-level native env settings, not Config API fields.
        # Parent-provided Compose env is bound/read by host; native image source
        # defines these defaults. Worker receives exact values in private state.
        prefix = self.rag['prefixes']
        require(set(prefix) == {'content', 'query', 'field'} and prefix['field'] is None
                and all(v is None or isinstance(v, str) and len(v) <= 128 for v in prefix.values()),
                'RAG fixture prefix settings are unsupported')
        return prefix

    def hard_zero(self, baseline, receipt):
        self.save('hard_zero_cap_update')
        self.rag.update(restore_e_cap=True, hard_zero_baseline=baseline); self.save('hard_zero_cap_update')
        try:
            self.native.ok('POST', '/key/update', body={'key': self.rag['key_hash'], 'max_budget': 0})
            zero = self.settle(baseline, 0, cap='0')
            p0, c0 = self.captures()
            self.save('hard_zero_ordinary_rag')
            # Use the same existing WebUI opener; native unhandled upstream
            # aiohttp errors may be plain Internal Server Error, not JSON.
            account = self.state['users'][0]
            self.webui.session(account, 'user')
            content = self.rag['fixture_text'] + ' denied ' + uuid4().hex[:8]
            body = {'name': 'GOAL584 denied synthetic', 'content': content,
                    'collection_name': f'web-search-{account["id"]}-{uuid4().hex[:12]}'}
            request = Request(self.d['WEBUI_URL'] + RAG + '/process/text', method='POST',
                headers={'Authorization': 'Bearer ' + account['token'], 'Content-Type': 'application/json'}, data=encoded(body))
            try:
                response = self.webui.opener.open(request, timeout=30)
            except HTTPError as error:
                response = error
            with response:
                status, raw = response.code, response.read(MAX_BYTES + 1)
            require(len(raw) <= MAX_BYTES and status in (422, 500), 'Hard-zero ordinary RAG was not denied')
            if status == 422:
                expected_budget_message(json.loads(raw), scope='key')
            else:
                require(raw == b'Internal Server Error', 'Unexpected native RAG failure envelope')
            p1, c1 = self.captures()
            require(p1 == p0 and c1['requests'][:-1] == c0['requests'] and len(c1['requests']) == len(c0['requests']) + 1,
                    'Hard-zero ordinary RAG reached provider or omitted actual gateway attempt')
            attempt = c1['requests'][-1]
            require(attempt.get('route') == '/v1/embeddings' and attempt.get('body') ==
                    {'model': MODEL, 'input': [(self.native_prefixes()['content'] or '') + content]},
                    'Hard-zero ordinary RAG did not reach the selected native E route/input')
            self.save('hard_zero_native_status_witness')
            native_status, error, _ = self.native.request('POST', '/v1/embeddings', token=self.rag['key'],
                                                        body={'model': MODEL, 'input': ['GOAL584 native hard-zero witness']})
            require(native_status == 422 and error.get('error', {}).get('type') == 'budget_exceeded',
                    'Native E hard-zero witness was not exact422/budget_exceeded')
            expected_budget_message(error, scope='key')
            p2, c2 = self.captures()
            require(p2 == p0 and c2['requests'][:-1] == c1['requests'] and len(c2['requests']) == len(c1['requests']) + 1,
                    'Hard-zero status witness reached provider or lacked its gateway attempt')
            denied = self.settle(baseline, 0, cap='0')
            receipt['hard_zero'] = {'rag_http_status': status, 'rag_gateway_attempt': attempt,
                'native_witness_status': native_status, 'native_error_type': 'budget_exceeded',
                'provider_requests_unchanged': True, 'after_denial': denied,
                'generic_rag500_alone_is_not_budget_evidence': True,
                'new_zero_rows': len(same_history(zero, denied))}
        finally:
            self.native.ok('POST', '/key/update', body={'key': self.rag['key_hash'], 'max_budget': 20})
            restored = self.settle(baseline, 0)
            self.rag['restore_e_cap'] = False; self.save('hard_zero_cap_restored')
            receipt['after_cap_restore'] = restored

    def restore(self):
        result = {'rag_settings_restored': False, 'e_cap_restored': not self.rag.get('restore_e_cap', False),
                  'financial_history_or_keys_deleted': False, 'partial_provision_retained': True}
        if not self.rag:
            return result
        if self.rag.get('restore_e_cap'):
            self.native.ok('POST', '/key/update', body={'key': self.rag['key_hash'], 'max_budget': 20})
            self.settle(self.rag['hard_zero_baseline'], 0)
            self.rag['restore_e_cap'] = False
            result['e_cap_restored'] = True
        if 'original_rag' in self.rag:
            status, _ = self.api('POST', '/embedding/update', rag_update(self.rag['original_rag']))
            status2, current = self.api('GET', '/embedding')
            result['rag_settings_restored'] = status == status2 == 200 and rag_update(current) == rag_update(self.rag['original_rag'])
        self.save('failed_partial_provision_retained')
        return result


def worker_main(action, prefix_json=None):
    receipt = {'schema': 1, 'proof': 'goal584-native-rag-service-worker', 'phase': action, 'passed': False,
               'not_qualified': LIMITS, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    worker = None
    try:
        worker = Worker()
        if action == 'prepare':
            receipt.update(worker.prepare())
            worker.rag['prefixes'] = json.loads(prefix_json)
            worker.native_prefixes(); worker.save('prepared')
        elif action == 'run':
            worker.run(receipt)
        else:
            restored = worker.restore()
            receipt.update(restored)
            require(restored.get('rag_settings_restored') is True and restored.get('e_cap_restored') is True,
                    'RAG restoration was not confirmed by actual native readback')
        receipt['passed'] = True
    except Exception as error:
        receipt.update(failure_category='native_rag_boundary_failed',
                       failure_phase=worker.rag.get('stage', 'not_prepared') if worker else 'initialization',
                       error_class='ProofError' if isinstance(error, ProofError) else 'NativeBoundaryError')
        if worker:
            try:
                receipt['failure_restoration'] = worker.restore()
            except Exception:
                receipt['failure_restoration'] = {'completed': False, 'partial_provision_retained': True}
    if worker:
        receipt['stage'] = worker.rag.get('stage', 'not_prepared')
        safe(receipt, worker.secrets)
    print(json.dumps(safe(receipt), allow_nan=False))
    return 0 if receipt['passed'] else 1


def host_main(args):
    from prove_pricing_browser import PricingFixture, private_fixture, overwrite_config
    from prove_webui_browser import write_json
    import subprocess
    u = urlsplit(args.base_url)
    require(u.scheme == 'http' and u.port == 8080 and u.path in ('', '/') and not u.username and not u.password
            and not u.query and not u.fragment and isinstance(ipaddress.ip_address(u.hostname), ipaddress.IPv4Address)
            and ipaddress.ip_address(u.hostname).is_private, 'RAG requires disposable private IPv4:8080')
    private, config, accounts, secrets = private_fixture(args.env_file, args.accounts, args.output)
    secrets += [v['password'] for v in accounts]
    require(not (private / RAG_STATE.name).exists() and not (args.output / 'rag-service.json').exists(), 'RAG requires fresh proof state/output')
    for path, proof, stage in ((args.prior_pricing_receipt, 'goal584-native-pricing-browser', None),
                               (args.prior_overlap_receipt, 'goal584-two-native-process-budget-overlap', 'qualified_native_overlap')):
        require(path.is_file() and path.stat().st_size <= MAX_BYTES, 'RAG prior milestone receipt unavailable')
        previous = json.loads(path.read_text(encoding='utf8'))
        require(previous.get('passed') is True and previous.get('proof') == proof
                and (stage is None or previous.get('stage') == stage), 'RAG requires completed pricing and overlap phases')
    args.output.mkdir(exist_ok=True)
    fixture = PricingFixture(args.env_file, args.output, config, private, secrets)
    receipt = {'schema': 1, 'proof': 'goal584-native-rag-service', 'passed': False, 'phase': 'bind',
               'not_qualified': LIMITS, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    original, attempted = None, False
    def command(arguments, label):
        try:
            result = subprocess.run(fixture.command + arguments, cwd=ROOT, capture_output=True, timeout=240)
        except (OSError, subprocess.SubprocessError):
            raise ProofError('RAG existing fixture command unavailable') from None
        require(len(result.stdout) <= MAX_BYTES, 'RAG worker response exceeded bound')
        try:
            value = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            raise ProofError('RAG worker did not return bounded safe JSON') from None
        safe(value, secrets)
        write_json(args.output / ('rag-' + label + '.json'), value)
        require(result.returncode == 0 and value.get('passed') is True, 'RAG worker boundary failed')
        require(value.get('source_sha256') == receipt['source_sha256'], 'RAG worker mounted source differs')
        return value
    try:
        fixture.bind(args.base_url)
        fixture.config_observation()
        result = subprocess.run(fixture.command + ['config', '--format', 'json'], cwd=ROOT, capture_output=True, timeout=30)
        require(result.returncode == 0 and len(result.stdout) <= MAX_BYTES, 'RAG Compose source observation failed')
        composition = json.loads(result.stdout)
        webui, proxy = composition['services']['webui'], composition['services']['proxy']
        env = webui['environment']
        require(env.get('VECTOR_DB') == 'pgvector' and str(env.get('PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH')) == '3'
                and isinstance(env.get('PGVECTOR_DB_URL'), str)
                and re.fullmatch(r'postgresql\+psycopg://goal584:[A-Za-z0-9_-]+@postgres:5432/goal584_vectors', env['PGVECTOR_DB_URL'])
                and not env.get('DATABASE_URL') and env.get('ENABLE_RETRIEVAL_UNSCOPED_COLLECTIONS', 'False').lower() == 'false'
                and env.get('PGVECTOR_PGCRYPTO', 'false').lower() == 'false',
                'RAG requires isolated native pgvector dimension3 with SQLite metadata unchanged')
        require(composition['services']['postgres']['image'] ==
                'docker.io/pgvector/pgvector:0.8.7-pg16-bookworm@sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f',
                'RAG requires the parent-approved pgvector image identity')
        mounts = {m['target']: m for m in proxy['volumes'] if m['type'] == 'bind'}
        require('/proof/prove_rag_service.py' in mounts and mounts['/proof/prove_rag_service.py'].get('read_only') is True
                and Path(mounts['/proof/prove_rag_service.py']['source']).resolve() == Path(__file__).resolve(), 'RAG proof mount differs')
        observed_env = fixture.command_json(['exec', '-T', 'webui', 'python', '-B', '-c', ENV_OBSERVATION], 'rag_runtime_env')
        require(observed_env['vector_url_sha256'] == hashlib.sha256(env['PGVECTOR_DB_URL'].encode()).hexdigest()
                and observed_env['sqlite_metadata_default'] is True
                and all(observed_env['values'][name] == env.get(name) for name in observed_env['values'] if name != 'USE_SLIM_DOCKER')
                and observed_env['values']['USE_SLIM_DOCKER'].lower() == 'true', 'Running native WebUI vector/prefix environment differs')
        receipt['vector_runtime_env'] = observed_env
        prefixes = {short: observed_env['values'].get('RAG_EMBEDDING_' + name) for short, name in
                    (('content', 'CONTENT_PREFIX'), ('query', 'QUERY_PREFIX'), ('field', 'PREFIX_FIELD_NAME'))}
        receipt['serial_proxy_before'] = serial_proxy(fixture)
        receipt['phase'] = 'prepare'
        receipt['prepare'] = command(['exec', '-T', 'proxy', 'python', '-B', '/proof/prove_rag_service.py',
                                     '--worker-action', 'prepare', '--prefix-json', json.dumps(prefixes)], 'prepare')
        original = config.read_bytes()
        changed = append_embedding(original)
        backup = private / BACKUP.name
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(original); handle.flush(); os.fsync(handle.fileno())
        receipt['phase'] = 'append_e_and_native_reload'; attempted = True
        overwrite_config(config, changed)
        fixture.restart()
        receipt['serial_proxy_after_reload'] = serial_proxy(fixture)
        receipt['phase'] = 'native_rag_text_query_hard_zero'
        receipt['runtime'] = command(['exec', '-T', 'proxy', 'python', '-B', '/proof/prove_rag_service.py', '--worker-action', 'run'], 'runtime')
        receipt['serial_proxy_after_phase'] = serial_proxy(fixture)
        receipt.update(passed=True, phase='qualified_native_rag_http_text_query',
            success_e_lifetime='active until existing disposable teardown', original_config_sha256=hashlib.sha256(original).hexdigest(),
            active_config_sha256=hashlib.sha256(config.read_bytes()).hexdigest())
    except Exception as error:
        receipt.update(failure_phase=receipt['phase'], failure_category='native_rag_proof_boundary',
                       error_class='ProofError' if isinstance(error, ProofError) else 'FixtureBoundaryError')
    finally:
        if not receipt['passed'] and attempted:
            receipt['restoration'] = {'rag_attempted': True, 'yaml_attempted': True, 'partial_native_state_retained': True}
            try:
                receipt['restoration']['rag'] = command(['exec', '-T', 'proxy', 'python', '-B', '/proof/prove_rag_service.py',
                    '--worker-action', 'restore'], 'failure-restore')
            except Exception:
                receipt['restoration']['rag_restore_completed'] = False
            try:
                overwrite_config(config, original)
                fixture.restart()
                fixture.config_observation()
                receipt['restoration']['serial_proxy_after_restoration'] = serial_proxy(fixture)
                receipt['restoration']['yaml_bytes_and_readiness_restored'] = config.read_bytes() == original
            except Exception:
                receipt['restoration']['yaml_bytes_and_readiness_restored'] = False
        safe(receipt, secrets)
        write_json(args.output / 'rag-service.json', receipt)
        print(json.dumps(receipt, allow_nan=False))
    return 0 if receipt['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker-action', choices=('prepare', 'run', 'restore'))
    parser.add_argument('--prefix-json')
    parser.add_argument('--base-url')
    for name in ('env-file', 'accounts', 'output', 'prior-pricing-receipt', 'prior-overlap-receipt'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.worker_action:
        return worker_main(args.worker_action, args.prefix_json)
    require(all(getattr(args, name) is not None for name in
                ('base_url', 'env_file', 'accounts', 'output', 'prior_pricing_receipt', 'prior_overlap_receipt')), 'Incomplete RAG host arguments')
    return host_main(args)


if __name__ == '__main__':
    raise SystemExit(main())
