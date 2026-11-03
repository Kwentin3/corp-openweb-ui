"""Offline native producer/helper and proof boundaries; no Docker/API runtime."""
import ast
import asyncio
import contextlib
import copy
import datetime
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import types
import unittest
from unittest.mock import patch
from typing import Union

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prove_rag_service as p
import mock_provider

PINNED = p.ROOT / 'local/goal584/cost-display/open-webui'
LITELLM = p.ROOT / 'local/goal584/litellm/upstream'
IDS = [f'{i:08d}-1111-4111-8111-111111111111' for i in range(1, 7)]
PAYER, ACTOR = IDS[4], IDS[0]
KEY_HASH = 'f' * 64


def extract(source, names, globals):
    tree = ast.parse(source)
    nodes = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    for node in nodes:
        node.decorator_list = []
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), '<actual pinned native helpers>', 'exec'), globals)
    return globals


def raw_row(identifier='native-embedding-1'):
    return {'request_id': identifier, 'user': PAYER, 'api_key': KEY_HASH,
        'model': p.WIRE, 'model_group': p.MODEL, 'model_id': p.DEPLOYMENT, 'status': 'success',
        'spend': .10, 'prompt_tokens': 10, 'completion_tokens': 0, 'total_tokens': 10, 'session_id': None,
        'metadata': {'litellm_call_id': 'actual-native-call-1', 'spend_logs_metadata': {'owui_budget': copy.deepcopy(p.SCOPE)}}}


def native_pair(count=1):
    budgets = []
    for uid in IDS[:5]:
        service = uid == PAYER
        models = []
        for model in (('goal584-a', p.MODEL) if service else ('goal584-a', 'goal584-b')):
            models.append({'model': model, 'key_hash': KEY_HASH, 'key_alias': 'owui-budget-v1-' + 'a' * 64,
                'max_budget': '20', 'spend': '.8' if service and model == 'goal584-a' else '0', 'blocked': False,
                'budget_duration': '1mo', 'budget_reset_at': '2026-12-03T00:00:00Z'})
        budgets.append({'user_id': uid, 'max_budget': '20', 'spend': '.8' if service else '0', 'models': models,
            'budget_duration': '1mo', 'budget_reset_at': '2026-12-03T00:00:00Z'})
    before = {'budgets': budgets, 'history': [{'request_id': 'old-native-' + uid, 'user_id': uid,
        'model_group': 'goal584-a', 'spend_usd': '.8' if uid == PAYER else '0', 'full_row_sha256': 'a' * 64} for uid in IDS[:5]], 'rag_rows': []}
    after = copy.deepcopy(before)
    for index in range(count):
        after['history'].append({'request_id': 'native-embedding-' + str(index), 'user_id': PAYER,
            'model_group': p.MODEL, 'spend_usd': '.10', 'full_row_sha256': 'b' * 64})
    service = after['budgets'][4]
    service['spend'] = str(p.amount(service['spend']) + p.Decimal('.10') * count)
    service['models'][1]['spend'] = str(p.Decimal('.10') * count)
    return before, after


def capture_pair():
    body = {'model': p.MODEL, 'input': ['doc: proof abc123']}
    auth = {'route': '/v1/embeddings', 'body': body, 'body_after_auth': copy.deepcopy(body),
        'native_auth_user_id': PAYER, 'native_auth_key_hash': KEY_HASH,
        'native_estimated_max_cost_usd': .03, 'provenance_removed_after': True, '_observation_id': 'a' * 32}
    response = {'object': 'list', 'data': [{'object': 'embedding', 'index': 0, 'embedding': [.1, .2, .3]}],
        'model': p.WIRE, 'usage': {'prompt_tokens': 10, 'total_tokens': 10}}
    physical = {'id': 'embedding-observation-goal584-' + 'a' * 32, 'id_kind': 'provider_observation_only',
        'route': '/v1/embeddings', 'body': {'model': p.WIRE, 'input': body['input']},
        'usage': response['usage'], 'response': response, 'lifecycle': {'terminal': True, 'outcome': 'completed'}}
    a = {'synthetic': True, 'control': {'delay_ms': 0}, 'requests': [{'id': 'previous'}]}
    b = copy.deepcopy(a); b['requests'].append(physical)
    c = {'schema': 1, 'requests': [{'prior': 'retained'}]}
    d = copy.deepcopy(c); d['requests'].append(auth)
    return a, b, c, d


class EvidenceBoundaryTests(unittest.TestCase):
    def test_append_preserves_all_original_bytes_and_only_adds_approved_local_model(self):
        raw = (HERE / 'litellm_config.yaml').read_bytes()
        for raw in (raw, raw.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')):
            changed = p.append_embedding(raw)
            self.assertEqual(changed.count(b'model_name: goal584-e'), 1)
            self.assertEqual(changed.split(b'  - model_name: goal584-e')[0], raw.split(b'general_settings:')[0])
            self.assertEqual(changed.split(b'general_settings:')[1], raw.split(b'general_settings:')[1])
            configured = raw.replace(b'general_settings:', b'general_settings:\n  custom_auth: capture_webui_auth.gateway_auth\n  custom_auth_run_common_checks: true')
            self.assertTrue(p.validate_config(configured, p.append_embedding(configured))['other_native_configuration_unchanged'])
        for value in [raw.replace(b'goal584-b', b'goal584-e'), raw + b'general_settings:\n', b'', raw * 1000]:
            with self.subTest(value=len(value)), self.assertRaises(p.ProofError): p.append_embedding(value)

    def test_config_rejects_changed_prices_external_target_or_weakened_owner(self):
        raw = (HERE / 'litellm_config.yaml').read_bytes().replace(b'general_settings:',
            b'general_settings:\n  custom_auth: capture_webui_auth.gateway_auth\n  custom_auth_run_common_checks: true')
        for bad in [raw.replace(b'input_cost_per_token: 0.01', b'input_cost_per_token: 0.02', 1),
                    raw.replace(b'http://provider:8000/v1', b'https://external.invalid/v1', 1),
                    raw.replace(b'fail_closed_budget_enforcement: true', b'fail_closed_budget_enforcement: false')]:
            with self.subTest(value=bad[-10:]), self.assertRaises(p.ProofError): p.validate_config(bad, p.append_embedding(bad))
        with self.assertRaises(p.ProofError): p.validate_config(raw, p.append_embedding(raw).replace(b'max_input_tokens: 10', b'max_input_tokens: 20', 1))

    def test_full_history_loss_changed_hash_and_personal_key_or_service_a_drift_fail(self):
        before, after = native_pair()
        self.assertTrue(p.verify_finance(before, after, PAYER, count=1))
        for mutate in [lambda s: s['history'].pop(0), lambda s: s['history'][0].update(full_row_sha256='c' * 64),
                       lambda s: s['budgets'][0]['models'][0].update(max_budget='0'),
                       lambda s: s['budgets'][4]['models'][0].update(spend='.9'),
                       lambda s: s['budgets'][4].update(budget_reset_at='2027-01-01T00:00:00Z'),
                       lambda s: s['history'].append(copy.deepcopy(s['history'][0])),
                       lambda s: s['history'][-1].update(user_id=ACTOR)]:
            bad = copy.deepcopy(after); mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(p.ProofError): p.verify_finance(before, bad, PAYER, count=1)
        lag = copy.deepcopy(after); lag['budgets'][4]['spend'] = '.8'
        self.assertFalse(p.verify_finance(before, lag, PAYER, count=1))
        no_row = copy.deepcopy(after); no_row['history'].pop()
        self.assertFalse(p.verify_finance(before, no_row, PAYER, count=1))

    def test_native_rag_projection_is_same_row_owned_and_does_not_fabricate_provider_id(self):
        # Use the actual product syntax validator, extracted without auth bootstrap.
        source = (p.ROOT / 'deploy/openwebui-budgets/provenance.py').read_text(encoding='utf8')
        scope = extract(source, {'validate_persisted_rag_scope'}, {'_check': lambda condition: p.require(condition, 'scope differs')})['validate_persisted_rag_scope']
        raw = raw_row()
        projected = p.row_evidence(raw, PAYER, KEY_HASH, scope)
        self.assertEqual(projected['litellm_call_id'], 'actual-native-call-1')
        self.assertNotIn('provider_response_id', projected)
        self.assertEqual(projected['scope'], p.SCOPE)
        for path, value in [('user', ACTOR), ('api_key', 'e' * 64), ('model_group', 'goal584-a'), ('model_id', 'wrong'),
                            ('model', 'unknown'), ('completion_tokens', 1), ('spend', 0), ('session_id', IDS[5])]:
            bad = copy.deepcopy(raw); bad[path] = value
            with self.subTest(path=path), self.assertRaises(p.ProofError): p.row_evidence(bad, PAYER, KEY_HASH, scope)
        bad = copy.deepcopy(raw); bad['metadata']['spend_logs_metadata']['owui_budget']['actor_id'] = ACTOR
        with self.assertRaises(p.ProofError): p.row_evidence(bad, PAYER, KEY_HASH, scope)

    def test_actual_provider_and_auth_context_are_full_equality_not_field_dropping(self):
        a, b, c, d = capture_pair()
        evidence = p.causal_call(a, b, c, d, key_hash=KEY_HASH, payer=PAYER, expected_input='doc: proof abc123')
        self.assertTrue(evidence['provider_response_has_no_id'])
        for mutate in [lambda s: s['requests'][-1]['body'].update(user='forged'),
                       lambda s: s['requests'][-1].update(id_kind='native_call_id'),
                       lambda s: s['requests'][-1]['response'].update(id='invented'),
                       lambda s: s['requests'][-1]['response']['data'][0].update(embedding=[float('nan'), .2, .3]),
                       lambda s: s['requests'].append(copy.deepcopy(s['requests'][-1])),
                       lambda s: s['requests'][0].update(id='changed-old')]:
            bad = copy.deepcopy(b); mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(p.ProofError):
                p.causal_call(a, bad, c, d, key_hash=KEY_HASH, payer=PAYER, expected_input='doc: proof abc123')
        for field, value in [('native_auth_user_id', ACTOR), ('native_auth_key_hash', 'e' * 64), ('body_after_auth', {'input': ['changed']})]:
            bad = copy.deepcopy(d); bad['requests'][-1][field] = value
            with self.assertRaises(p.ProofError): p.causal_call(a, b, c, bad, key_hash=KEY_HASH, payer=PAYER, expected_input='doc: proof abc123')

    def test_actual_retrieval_requires_stored_content_owner_and_native_vector_distance(self):
        value = {'ids': [['actual-chunk-id']], 'documents': [['proof abc123']], 'distances': [[.01]],
                 'metadatas': [[{'created_by': ACTOR, 'embedding_config': str({'engine': 'openai', 'model': p.MODEL})}]]}
        self.assertTrue(p.retrieved(value, 'collection', 'proof abc123', ACTOR)['actual_text_equal'])
        for mutate in [lambda x: x.update(documents=[['different']]), lambda x: x['metadatas'][0][0].update(created_by=PAYER),
                       lambda x: x.update(distances=[[float('inf')]]), lambda x: x.update(documents=[])]:
            bad = copy.deepcopy(value); mutate(bad)
            with self.assertRaises(p.ProofError): p.retrieved(bad, 'collection', 'proof abc123', ACTOR)

    def test_protected_config_update_preserves_nonselected_fields_and_secret_is_not_safe(self):
        original = {'status': True, 'RAG_EMBEDDING_ENGINE': 'openai', 'RAG_EMBEDDING_MODEL': 'old',
            'RAG_EMBEDDING_BATCH_SIZE': 16, 'ENABLE_ASYNC_EMBEDDING': False, 'RAG_EMBEDDING_CONCURRENT_REQUESTS': 3,
            'openai_config': {'url': 'http://provider:8000/v1', 'key': 'synthetic'},
            'ollama_config': {'url': 'http://ollama:11434', 'key': None},
            'azure_openai_config': {'url': '', 'key': '', 'version': 'old-version'}}
        body = p.rag_update(original, 'sk-' + 'z' * 32)
        self.assertEqual(body['ollama_config'], original['ollama_config'])
        self.assertEqual(body['azure_openai_config'], original['azure_openai_config'])
        self.assertEqual(p.rag_update(original)['openai_config'], original['openai_config'])
        self.assertEqual(original['RAG_EMBEDDING_MODEL'], 'old')
        with self.assertRaises(p.ProofError): p.safe(body)
        with self.assertRaises(p.ProofError): p.safe({'password': 'actual-private-password'}, ['actual-private-password'])

    def test_worker_failure_diagnostics_never_echo_raw_exception_or_false_pass(self):
        fake = SimpleNamespace(rag={'stage': 'query_request'}, secrets=['private-secret'],
            run=lambda receipt: (_ for _ in ()).throw(RuntimeError('private-secret raw response')),
            restore=lambda: {'rag_settings_restored': True})
        with patch.object(p, 'Worker', return_value=fake), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(p.worker_main('run'), 1)
        result = json.loads(out.getvalue())
        self.assertFalse(result['passed']); self.assertEqual(result['failure_phase'], 'query_request')
        self.assertEqual(result['error_class'], 'NativeBoundaryError')
        self.assertNotIn('private-secret', out.getvalue())

    def test_restore_does_not_accept_http_success_without_actual_readback(self):
        fake = SimpleNamespace(rag={'stage': 'failed_partial'}, secrets=[],
            restore=lambda: {'rag_settings_restored': False, 'e_cap_restored': True})
        with patch.object(p, 'Worker', return_value=fake), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(p.worker_main('restore'), 1)
        self.assertFalse(json.loads(out.getvalue())['passed'])
        worker = p.Worker.__new__(p.Worker)
        worker.rag = {'key_hash': KEY_HASH, 'restore_e_cap': True, 'hard_zero_baseline': {'actual': 'saved native snapshot'}}
        worker.native = SimpleNamespace(ok=lambda *args, **kwargs: {})
        worker.settle = lambda *args: (_ for _ in ()).throw(p.ProofError('native readback failed'))
        worker.save = lambda *args: None
        with self.assertRaises(p.ProofError): worker.restore()
        self.assertTrue(worker.rag['restore_e_cap'])

    def test_hard_zero_requires_real_gateway_budget_envelope_and_restores_cap_on_every_failure(self):
        from prove_native_budgets import BUDGET_MODEL_MESSAGE
        for mode in ('pass', 'transport', 'wrong_error_type', 'unexpected_rag_body'):
            with self.subTest(mode=mode):
                worker = p.Worker.__new__(p.Worker)
                worker.rag = {'key_hash': KEY_HASH, 'key': 'sk-' + 'z' * 32, 'fixture_text': 'proof abc123'}
                worker.state = {'users': [{'id': ACTOR, 'token': 'private-token'}]}
                worker.payer = PAYER; worker.d = {'WEBUI_URL': 'http://webui:8080'}
                worker.save = lambda stage: worker.rag.update(stage=stage)
                worker.native_prefixes = lambda: {'content': 'doc: ', 'query': 'query: ', 'field': None}
                mutations = []
                def update(method, path, body):
                    mutations.append((method, path, body))
                    return {}
                worker.native = SimpleNamespace(ok=update, request=lambda *args, **kwargs: (422,
                    {'error': {'type': 'budget_exceeded' if mode != 'wrong_error_type' else 'transport_error',
                               'message': BUDGET_MODEL_MESSAGE}}, {}))
                worker.settle = lambda baseline, count, **kwargs: {'history': []}
                physical = {'synthetic': True, 'control': {}, 'requests': []}
                attempt = {'route': '/v1/embeddings', 'body': {'model': p.MODEL,
                    'input': ['doc: proof abc123 denied aaaaaaaa']}}
                states = [({'schema': 1, 'requests': []}), ({'schema': 1, 'requests': [attempt]}),
                          ({'schema': 1, 'requests': [attempt, {'witness': True}]})]
                worker.captures = lambda: (copy.deepcopy(physical), states.pop(0))
                class Response:
                    code = 500
                    def __enter__(self): return self
                    def __exit__(self, *args): pass
                    def read(self, bound): return b'Internal Server Error' if mode != 'unexpected_rag_body' else b'unknown upstream'
                def open_request(*args, **kwargs):
                    if mode == 'transport': raise OSError('private transport details')
                    return Response()
                worker.webui = SimpleNamespace(session=lambda *args: None, opener=SimpleNamespace(open=open_request))
                receipt = {}
                with patch.object(p, 'uuid4', return_value=SimpleNamespace(hex='a' * 32)):
                    if mode == 'pass':
                        worker.hard_zero({'history': []}, receipt)
                        self.assertEqual(receipt['hard_zero']['native_error_type'], 'budget_exceeded')
                        self.assertTrue(receipt['hard_zero']['provider_requests_unchanged'])
                    else:
                        with self.assertRaises((p.ProofError, OSError)): worker.hard_zero({'history': []}, receipt)
                self.assertEqual(mutations, [('POST', '/key/update', {'key': KEY_HASH, 'max_budget': 0}),
                                             ('POST', '/key/update', {'key': KEY_HASH, 'max_budget': 20})])
                self.assertFalse(worker.rag['restore_e_cap'])

    def test_host_failed_worker_restores_yaml_and_attempts_rag_restore_without_deleting_history(self):
        # Replace only external owner boundaries; execute the actual coordinator,
        # real temp-file byte restoration and all of its finally branches.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); private = root / 'private'; private.mkdir()
            output = root / 'receipts'; config = private / 'config.yaml'
            original = (HERE / 'litellm_config.yaml').read_bytes(); config.write_bytes(original)
            prior_price = root / 'price.json'; prior_overlap = root / 'overlap.json'
            prior_price.write_text(json.dumps({'passed': True, 'proof': 'goal584-native-pricing-browser'}))
            prior_overlap.write_text(json.dumps({'passed': True, 'proof': 'goal584-two-native-process-budget-overlap', 'stage': 'qualified_native_overlap'}))
            args = SimpleNamespace(base_url='http://172.20.0.2:8080', env_file=private / 'proof.env', accounts=private / 'accounts.json',
                output=output, prior_pricing_receipt=prior_price, prior_overlap_receipt=prior_overlap)
            phases, restarts = [], []
            source_sha = hashlib.sha256(Path(p.__file__).read_bytes()).hexdigest()
            env = {'VECTOR_DB': 'pgvector', 'PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH': '3',
                   'PGVECTOR_DB_URL': 'postgresql+psycopg://goal584:synthetic@postgres:5432/goal584_vectors'}
            vector_env = {'values': {k: env.get(k) for k in ('VECTOR_DB', 'PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH', 'PGVECTOR_PGCRYPTO',
                'RAG_EMBEDDING_CONTENT_PREFIX', 'RAG_EMBEDDING_QUERY_PREFIX', 'RAG_EMBEDDING_PREFIX_FIELD_NAME')},
                'vector_url_sha256': hashlib.sha256(env['PGVECTOR_DB_URL'].encode()).hexdigest(), 'sqlite_metadata_default': True}
            vector_env['values']['USE_SLIM_DOCKER'] = 'true'
            class Fixture:
                def __init__(self, *args): self.command = ['existing-compose-owner']
                def bind(self, *args): pass
                def config_observation(self): return {}
                def restart(self): restarts.append('native-restart')
                def command_json(self, *args): return vector_env
            fake_price = types.ModuleType('prove_pricing_browser')
            fake_price.PricingFixture = Fixture
            fake_price.private_fixture = lambda *args: (private, config, [{'password': 'private-password'}], [])
            fake_price.overwrite_config = lambda path, raw: path.write_bytes(raw)
            fake_browser = types.ModuleType('prove_webui_browser')
            fake_browser.write_json = lambda path, value: path.write_text(json.dumps(value), encoding='utf8')
            composition = {'services': {'webui': {'environment': env}, 'proxy': {'volumes': [{'target': '/proof/prove_rag_service.py',
                'source': str(Path(p.__file__).resolve()), 'type': 'bind', 'read_only': True}]},
                'postgres': {'image': 'docker.io/pgvector/pgvector:0.8.7-pg16-bookworm@sha256:0dd3149a06e4579a0d70d8fef9945636cd514005e7237deb27f9b67886f8dc4f'}}}
            def run(command, **kwargs):
                if 'config' in command:
                    return SimpleNamespace(returncode=0, stdout=json.dumps(composition).encode())
                phase = command[command.index('--worker-action') + 1]; phases.append(phase)
                value = {'schema': 1, 'passed': phase != 'run', 'source_sha256': source_sha}
                return SimpleNamespace(returncode=1 if phase == 'run' else 0, stdout=json.dumps(value).encode())
            with patch.dict(sys.modules, {'prove_pricing_browser': fake_price, 'prove_webui_browser': fake_browser}), \
                 patch.object(subprocess, 'run', side_effect=run), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(p.host_main(args), 1)
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual((private / p.BACKUP.name).read_bytes(), original)
            self.assertEqual(phases, ['prepare', 'run', 'restore'])
            self.assertEqual(len(restarts), 2)
            receipt = json.loads((output / 'rag-service.json').read_text())
            self.assertFalse(receipt['passed'])
            self.assertTrue(receipt['restoration']['yaml_bytes_and_readiness_restored'])
            self.assertTrue(receipt['restoration']['partial_native_state_retained'])


class ActualPinnedNativeTests(unittest.TestCase):
    def setUp(self):
        if not (PINNED / 'backend/open_webui/retrieval/utils.py').is_file() or not (LITELLM / 'litellm/proxy/spend_tracking/spend_tracking_utils.py').is_file():
            self.skipTest('Pinned ignored native sources unavailable; runtime context/ledger gates remain mandatory')

    def test_actual_native_pgvector_metadata_producer_uses_dict_string_not_guessed_json_object(self):
        source = (PINNED / 'backend/open_webui/retrieval/vector/utils.py').read_text(encoding='utf8')
        globals = {'KEYS_TO_EXCLUDE': [], 'RAG_METADATA_MAX_VALUE_CHARS': None, 'dt': datetime,
                   'sanitize_text_for_db': lambda value: value}
        extract(source, {'process_metadata'}, globals)
        metadata = globals['process_metadata']({'created_by': ACTOR, 'embedding_config': {'engine': 'openai', 'model': p.MODEL}})
        self.assertEqual(metadata['embedding_config'], "{'engine': 'openai', 'model': 'goal584-e'}")
        value = {'ids': [['native-chunk']], 'documents': [['proof abc123']], 'distances': [[0]], 'metadatas': [[metadata]]}
        self.assertTrue(p.retrieved(value, 'own-collection', 'proof abc123', ACTOR)['native_owner_equal'])
        value['metadatas'][0][0]['embedding_config'] = {'engine': 'openai', 'model': p.MODEL}
        with self.assertRaises(p.ProofError): p.retrieved(value, 'own-collection', 'proof abc123', ACTOR)

    def test_actual_native_prefix_batch_producer_and_frozen_provider_response_contract(self):
        source = (PINNED / 'backend/open_webui/retrieval/utils.py').read_text(encoding='utf8')
        requests = []
        class Result:
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def raise_for_status(self): pass
            async def json(self): return self.value
        class Session(Result):
            def __init__(self, **kwargs): pass
            def post(self, url, **kwargs):
                requests.append((url, kwargs))
                data = kwargs['json']; response = Result()
                class Handler:
                    def begin_record(self, payload, **kwargs): return {}, {'usage': {'prompt_tokens': 10, 'total_tokens': 10}}
                    def controlled_failure(self, *args, **kwargs): return False
                    def send_json(self, status, value, **kwargs):
                        assert status == 200
                        response.value = value
                    def mark(self, *args, **kwargs): pass
                # Actual frozen transport producer, with only I/O replaced.
                mock_provider.Handler.embeddings(Handler(), {**data, 'model': p.WIRE})
                return response
        globals = {'asyncio': asyncio, 'Union': Union, 'log': logging.getLogger('native-rag-offline'),
            'aiohttp': SimpleNamespace(ClientSession=Session, ClientTimeout=lambda **kw: None),
            'RAG_EMBEDDING_PREFIX_FIELD_NAME': None, 'ENABLE_FORWARD_USER_INFO_HEADERS': False,
            'AIOHTTP_CLIENT_TIMEOUT': 5, 'AIOHTTP_CLIENT_SESSION_SSL': True, 'AIOHTTP_CLIENT_ALLOW_REDIRECTS': False,
            'get_json_bearer_headers': lambda key: {'Authorization': 'Bearer ' + key}}
        extract(source, {'get_embedding_function', 'generate_embeddings', 'agenerate_openai_batch_embeddings'}, globals)
        function = globals['get_embedding_function']('openai', p.MODEL, None, 'http://proxy:4000/v1', 'private', 1)
        document = asyncio.run(function(['proof abc123'], prefix='doc: ', user=SimpleNamespace(id=ACTOR)))
        query = asyncio.run(function('proof abc123', prefix='query: ', user=SimpleNamespace(id=ACTOR)))
        self.assertEqual(len(document), 1); self.assertEqual(len(document[0]), 3); self.assertEqual(len(query), 3)
        self.assertEqual([v[1]['json'] for v in requests], [
            {'input': ['doc: proof abc123'], 'model': p.MODEL}, {'input': ['query: proof abc123'], 'model': p.MODEL}])
        self.assertTrue(all(v[0] == 'http://proxy:4000/v1/embeddings' for v in requests))
        self.assertNotIn('dimensions', requests[0][1]['json'])

    def test_actual_native_collection_acl_accepts_only_selected_actor_namespace(self):
        source = (PINNED / 'backend/open_webui/retrieval/utils.py').read_text(encoding='utf8')
        async def denied(*args, **kwargs): return False
        globals = {'_SAFE_COLLECTION_NAME_RE': re.compile(r'^[A-Za-z0-9_-]{1,255}$'),
            'ENABLE_RETRIEVAL_UNSCOPED_COLLECTIONS': False, 'Knowledges': SimpleNamespace(check_access_by_user_id=denied)}
        extract(source, {'filter_accessible_collections', '_is_safe_collection_name'}, globals)
        own, foreign = 'web-search-' + ACTOR + '-abc123', 'web-search-' + PAYER + '-abc123'
        result = asyncio.run(globals['filter_accessible_collections']({own, foreign, 'a' * 64}, SimpleNamespace(id=ACTOR, role='user'), access_type='write'))
        self.assertEqual(result, {own})

    def test_actual_litellm_embedding_transport_does_not_inject_sdk_encoding_defaults(self):
        result = subprocess.run(['git', '-c', 'gc.auto=0', '-C', str(LITELLM), 'show', 'HEAD:litellm/llms/openai/openai.py'],
            capture_output=True, env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'}, timeout=15)
        if result.returncode != 0:
            self.skipTest('Targeted native transport blob unavailable locally; no lazy fetch allowed')
        source = result.stdout.decode()
        class Adapter:
            def validate_python(self, value): return value
        globals = {'types': types, '_SDK_OPTION_KEYS': frozenset(('extra_headers', 'extra_query', 'extra_body')),
            '_EXTRA_HEADERS_ADAPTER': Adapter(), '_EXTRA_QUERY_ADAPTER': Adapter(), '_NO_EXTRA_HEADERS': {},
            'RAW_RESPONSE_HEADER': 'X-Stainless-Raw-Response', 'make_request_options': lambda **kwargs: kwargs}
        extract(source, {'_embedding_request_without_sdk_defaults'}, globals)
        data = {'model': p.WIRE, 'input': ['proof abc123'], 'extra_headers': {'x-fixture': 'test'}}
        body, options = globals['_embedding_request_without_sdk_defaults'](data, 5)
        self.assertEqual(body, {'model': p.WIRE, 'input': ['proof abc123']})
        self.assertNotIn('encoding_format', body); self.assertIn('extra_headers', options)
        node = next(n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.AsyncFunctionDef) and n.name == 'make_openai_embedding_request')
        branch = ast.get_source_segment(source, node)
        self.assertIn('if "encoding_format" not in data:', branch)
        self.assertIn('openai_aclient.post(', branch)

    def test_actual_native_no_response_id_falls_back_to_actual_logging_call_id(self):
        source = (LITELLM / 'litellm/proxy/spend_tracking/spend_tracking_utils.py').read_text(encoding='utf8')
        globals = {'CallTypes': SimpleNamespace(aretrieve_batch=SimpleNamespace(value='aretrieve_batch'))}
        extract(source, {'get_spend_logs_id'}, globals)
        self.assertEqual(globals['get_spend_logs_id']('aembedding', {'object': 'list'}, {'litellm_call_id': 'native-actual-call'}), 'native-actual-call')
        self.assertEqual(globals['get_spend_logs_id']('aembedding', {}, {'standard_logging_object': {'id': 'native-standard'},
            'litellm_call_id': 'native-actual-call'}), 'native-standard')


if __name__ == '__main__':
    unittest.main()
