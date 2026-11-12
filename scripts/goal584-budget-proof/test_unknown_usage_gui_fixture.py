"""Actual public clients over finite memory HTTP leaves; sockets/DNS denied."""
import asyncio
import copy
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import socket
import stat
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1] / 'deploy/openwebui-budgets')]
# Reuse the existing transport-only budget HTTP fixtures and real module aliases.
from test_unknown_usage_policy import Wire, Response
import unknown_usage_gui_fixture as F
import prove_native_budgets as native_owner
import prove_gateway_auth as private_owner


class GuiWire(Wire):
    def __init__(self):
        super().__init__()
        self.admin = {'id': str(uuid4()), 'token': 'synthetic-admin-session'}
        self.old_user = {'id': str(uuid4()), 'token': 'synthetic-old-user-session'}
        self.office_user = {'id': str(uuid4()), 'token': 'synthetic-office-session'}
        self.actor_id, self.actor_token = str(uuid4()), 'synthetic-new-user-session'
        self.accounts = {self.admin['token']: (self.admin['id'], 'admin'),
                         self.old_user['token']: (self.old_user['id'], 'user'),
                         self.office_user['token']: (self.office_user['id'], 'user')}
        self.config = {'ENABLE_OPENAI_API': True, 'OPENAI_API_BASE_URLS': ['http://proxy:4000/v1', 'http://proxy:4000/v1'],
            'OPENAI_API_KEYS': [self.gateway, self.gateway], 'OPENAI_API_CONFIGS': {
                '0': {'enable': True, 'auth_type': 'bearer', 'api_type': 'responses', 'model_ids': ['gpt-5.4-mini', 'gpt-6-luna'],
                      'headers': {F.fixture.USER_ID_HEADER: '{{USER_ID}}', F.fixture.TASK_HEADER: '{{TASK}}', 'Preserve': 'yes'}},
                '1': {'enable': True, 'model_ids': ['goal584-a'], 'headers': {'Unrelated': 'yes'}}}}
        self.workspace = {mid: {'id': mid, 'name': mid, 'base_model_id': None, 'is_active': True,
            'user_id': self.admin['id'], 'write_access': True, 'params': {'system': 'PRIVATE_OLD_SYSTEM', 'max_tokens': 1024},
            'meta': {'capabilities': {'builtin_tools': False}, 'filterIds': [F.FILTER_ID]},
            'access_grants': [{'id': str(uuid4()), 'principal_type': 'user', 'principal_id': self.office_user['id'], 'permission': 'read'}]}
            for mid in ('gpt-5.4-mini', 'gpt-6-luna', 'goal584-a')}
        self.source = (HERE.parents[1] / 'deploy/openwebui-budgets/cost_filter.py').read_text(encoding='utf8')
        self.functions = {F.FILTER_ID: {'id': F.FILTER_ID, 'type': 'filter', 'is_active': True, 'is_global': False,
                                      'meta': {'toggle': False}, 'content': self.source},
            'officecli_auto_attach_filter': {'id': 'officecli_auto_attach_filter', 'is_active': True, 'is_global': True,
                                             'content': 'PRIVATE_OFFICE_SOURCE'}}
        self.valves = {F.FILTER_ID: {'ledger_base_url': 'http://proxy:4000', 'ledger_read_key': self.viewer, 'read_wait_seconds': 8.0},
                       'officecli_auto_attach_filter': {'enabled_models': ['gpt-5.4-mini']}}
        self.tasks = {'TASK_MODEL': 'gpt-6-luna', 'ENABLE_TITLE_GENERATION': True, 'PRIVATE_TASK': 'preserve'}
        self.chat_config = {'ENABLE_CONTEXT_COMPACTION': False}
        self.servers = {'TOOL_SERVER_CONNECTIONS': [{'url': 'http://office:8080', 'headers': {'Private': 'preserve'}}]}
        self.fault = None
        self.journal_path = None

    def web_handle(self, method, url, headers, body=None):
        parsed = urlsplit(url); path = parsed.path; query = parse_qs(parsed.query)
        token = {k.lower(): v for k, v in headers.items()}.get('authorization', '').removeprefix('Bearer ')
        self.requests.append((method, path, copy.deepcopy(body)))
        if method == 'POST':
            assert token == self.admin['token']
            saved = F.fixture.read_private(self.journal_path)
            assert saved['unknown_gui_setup']['journal'][-1]['readback_confirmed'] is False
        if self.fault:
            failure = self.fault(method, path, body)
            if failure: return failure
        if path == '/api/version': value = {'version': '0.12.2'}
        elif path == '/api/v1/auths/':
            uid, role = self.accounts[token]; value = {'id': uid, 'role': role}
        elif path == '/api/v1/auths/add':
            assert method == 'POST' and body['role'] == 'user'
            self.accounts[self.actor_token] = (self.actor_id, 'user')
            value = {'id': self.actor_id, 'token': self.actor_token, 'role': 'user'}
        elif path == '/openai/config': value = self.config
        elif path == '/openai/config/update': self.config = copy.deepcopy(body); value = body
        elif path == '/api/models':
            uid, role = self.accounts[token]; rows = []
            for idx, conf in self.config['OPENAI_API_CONFIGS'].items():
                for mid in conf['model_ids']:
                    record = self.workspace.get(mid)
                    if record is None: continue
                    if role != 'admin' and ('user', uid, 'read') not in F.grant_set(record): continue
                    info = copy.deepcopy(record)
                    if role != 'admin': info['params'] = {}
                    rows.append({'id': mid, 'info': info, 'owned_by': 'openai', 'urlIdx': int(idx)})
            value = {'data': rows}
        elif path == '/api/v1/models/model':
            mid = query['id'][0]
            if mid not in self.workspace: return 404, {'detail': 'absent'}
            value = self.workspace[mid]
        elif path in ('/api/v1/models/create', '/api/v1/models/model/update'):
            assert method == 'POST'
            record = copy.deepcopy(body)
            # Actual native API adds nullable ModelMeta defaults and ACL IDs.
            record['meta'] = {'profile_image_url': None, 'knowledge': None, **record['meta']}
            for grant in record['access_grants']: grant.setdefault('id', str(uuid4()))
            value = record | {'user_id': self.admin['id'], 'write_access': True}
            self.workspace[body['id']] = value
        elif path == '/api/v1/functions/export':
            value = [dict(f, valves=self.valves[k]) for k, f in self.functions.items()]
        elif path.startswith('/api/v1/functions/id/'):
            identifier = path.split('/')[5]
            assert method == 'GET'  # No install, toggle, valve or preference writes.
            value = self.valves[identifier] if path.endswith('/valves') else self.functions[identifier]
        elif path == '/api/v1/tasks/config': assert method == 'GET'; value = self.tasks
        elif path == '/api/v1/chats/config': assert method == 'GET'; value = self.chat_config
        elif path == '/api/v1/configs/tool_servers': assert method == 'GET'; value = self.servers
        else: raise AssertionError('Unexpected GUI fixture HTTP endpoint: ' + path)
        return 200, copy.deepcopy(value)

    def open(self, request, timeout):
        assert urlsplit(request.full_url).hostname == 'webui'
        return Response(*self.web_handle(request.get_method(), request.full_url, dict(request.header_items()),
                                        json.loads(request.data) if request.data else None))

    def native_open(self, request, timeout):
        return Response(*self.native_handle(request.get_method(), request.full_url, dict(request.header_items()),
                                           json.loads(request.data) if request.data else None))

    def native_handle(self, method, url, headers, body=None, params=None):
        path = urlsplit(url).path
        assert path in ('/model/info', '/user/info', '/key/info', '/key/list', '/user/new', '/key/generate')
        if method == 'POST':
            saved = F.fixture.read_private(self.journal_path)
            assert saved['unknown_gui_setup']['journal'][-1]['stage'] == 'native-budget-initialize-post'
            assert saved['unknown_gui_setup']['journal'][-1]['readback_confirmed'] is False
        query = params or {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        if path == '/key/info' and query['key'] == self.viewer:
            return 200, {'info': {'user_id': self.viewer_id, 'key_alias': 'old-viewer', 'models': [],
                'allowed_routes': ['/spend/logs/session/ui'], 'team_id': None}}
        return super().handle(method, url, headers, body, params)


class UnknownGuiSetupTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        private = Path(temporary.name) / 'private'; private.mkdir(mode=0o700)
        if os.name == 'nt':
            self.enterContext(patch.object(private_owner.stat, 'S_IMODE', side_effect=lambda m: 0o700 if stat.S_ISDIR(m) else 0o600))
        self.wire = GuiWire(); self.path = private / 'gui.private.json'; self.wire.journal_path = self.path
        self.common = {'schema': 1, 'stage': 'setup_complete', 'admin': self.wire.admin, 'users': [self.wire.old_user],
                       'cost_reader': {'key': self.wire.viewer, 'key_alias': 'old-viewer', 'user_id': self.wire.viewer_id}}
        self.office = {'schema': 1, 'stage': 'setup_complete', 'admin': copy.deepcopy(self.wire.admin), 'users': [self.wire.office_user]}
        self.before = copy.deepcopy((self.common, self.office, self.wire.config, self.wire.workspace,
                                     self.wire.functions, self.wire.valves, self.wire.tasks, self.wire.servers))
        operator = private / 'operator.private.json'
        F.fixture.write_private(operator, {'schema': 1, 'operator_token': self.wire.operator})
        self.enterContext(patch.object(F.fixture, 'OPERATOR_STATE', operator))
        self.enterContext(patch.object(F, 'FILTER_SOURCE', HERE.parents[1] / 'deploy/openwebui-budgets/cost_filter.py'))
        self.enterContext(patch.dict(os.environ, OWUI_BUDGET_GATEWAY_SECRET=self.wire.gateway))
        from types import SimpleNamespace
        self.enterContext(patch.object(native_owner, 'build_opener', return_value=SimpleNamespace(open=self.wire.native_open)))
        wire = self.wire
        def request(session, method, url, *, params, json, headers, allow_redirects, timeout):
            assert allow_redirects is False
            return Response(*wire.native_handle(method, url, headers, json, params))
        self.enterContext(patch.object(F.ClientSession, 'request', request))
        # Windows builds its event-loop self-pipe through loopback socketpair.
        # Create that stdlib resource before denying all application networking.
        self.loop = asyncio.new_event_loop(); self.addCleanup(self.loop.close)
        self.network_attempts = []
        def denied(*args, **kwargs):
            self.network_attempts.append(True); raise AssertionError('Network forbidden in source-only tests')
        self.enterContext(patch.object(socket.socket, 'connect', denied))
        self.enterContext(patch.object(socket.socket, 'connect_ex', denied))
        self.enterContext(patch.object(socket, 'getaddrinfo', denied))
        self.webui = F.fixture.WebUI(); self.webui.opener = self.wire

    def run_setup(self):
        return self.loop.run_until_complete(F.setup_unknown_usage_gui(self.webui, self.common, self.office, self.path))

    def tearDown(self):
        self.assertEqual(self.network_attempts, [], 'No application socket or DNS attempts are permitted')

    def test_actual_returned_uid_initializes_three_canonical_budgets_and_preserves_office(self):
        output = StringIO()
        with redirect_stdout(output): result = self.run_setup()
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(result['actor_id'], self.wire.actor_id)
        saved = F.fixture.read_private(self.path)
        self.assertEqual(saved['stage'], 'setup_complete')
        self.assertTrue(all(j['readback_confirmed'] for j in saved['unknown_gui_setup']['journal']))
        self.assertEqual(set(self.wire.users), {self.wire.actor_id})
        self.assertEqual(len(self.wire.keys), 3)
        self.assertEqual(self.wire.users[self.wire.actor_id]['max_budget'], 6)
        self.assertEqual({k['max_budget'] for k in self.wire.keys.values()}, {2})
        for key in self.wire.keys.values():
            self.assertEqual(key['user_id'], self.wire.actor_id)
            model = key['models'][0]
            self.assertEqual(key['key_alias'], sys.modules['employee_budget_assignment'].assignment_alias(self.wire.actor_id, model))
        expected = copy.deepcopy(self.before[2]); expected['OPENAI_API_CONFIGS']['0']['model_ids'] += list(F.ALIASES)
        self.assertEqual(self.wire.config, expected)
        for mid, old in self.before[3].items(): self.assertEqual(self.wire.workspace[mid], old)
        self.assertEqual((self.common, self.office), self.before[:2])
        self.assertEqual((self.wire.functions, self.wire.valves, self.wire.tasks, self.wire.servers), self.before[4:])
        for alias in F.ALIASES:
            model = self.wire.workspace[alias]
            self.assertEqual(F.grant_set(model), {('user', self.wire.actor_id, 'read')})
            self.assertEqual(model['params'], {'max_tokens': 16, 'custom_params': {'store': False}})
            self.assertEqual(model['meta']['filterIds'], [F.FILTER_ID])
            self.assertFalse(model['meta']['capabilities']['builtin_tools'])
        self.assertFalse(result['settings_configured']); self.assertFalse(result['browser_accepted'])
        self.assertFalse(result['inference_issued']); self.assertFalse(result['unknown_cost_finality'])
        self.assertEqual(self.network_attempts, [])
        safe = json.dumps(result)
        for secret in (self.wire.actor_token, self.wire.gateway, self.wire.viewer, 'PRIVATE_OLD_SYSTEM'):
            self.assertNotIn(secret, safe)

    def test_external_route_or_wrong_rate_stops_before_any_write(self):
        for field, value in (('api_base', 'https://paid.invalid/v1'), ('model', 'openai/paid')):
            with self.subTest(field=field):
                original = copy.deepcopy(self.wire.models)
                self.wire.models[1]['litellm_params'][field] = value
                with self.assertRaisesRegex(F.ProofError, 'unknown_non_synthetic'): self.run_setup()
                self.assertFalse(self.path.exists())
                self.assertFalse(any(m == 'POST' for m, _, _ in self.wire.requests))
                self.wire.models = original
        self.wire.models[2]['model_info']['input_cost_per_token'] = .02
        with self.assertRaisesRegex(F.ProofError, 'unknown_non_synthetic'): self.run_setup()
        self.assertFalse(any(m == 'POST' for m, _, _ in self.wire.requests))

    def test_existing_native_employee_is_never_reset_or_reinitialized(self):
        existing = {'user_id': self.wire.actor_id, 'user_role': 'internal_user', 'models': list(F.ALIASES),
                    'spend': 1, 'max_budget': 7, 'budget_duration': '1mo', 'budget_reset_at': '2099-01-01T00:00:00Z'}
        self.wire.users[self.wire.actor_id] = copy.deepcopy(existing)
        with self.assertRaisesRegex(F.ProofError, 'inspect private handoff'): self.run_setup()
        self.assertEqual(self.wire.users[self.wire.actor_id], existing)
        self.assertFalse(self.wire.keys)
        self.assertFalse(any(m == 'POST' and p in ('/user/new', '/key/generate') for m, p, _ in self.wire.requests))
        self.assertEqual(F.fixture.read_private(self.path)['stage'], 'setup_failed')

    def test_partial_failure_keeps_uncertain_journal_and_cannot_retry(self):
        original = self.wire.native_handle
        def failing(method, url, headers, body=None, params=None):
            if method == 'POST' and urlsplit(url).path == '/key/generate':
                self.wire.requests.append((method, '/key/generate', copy.deepcopy(body)))
                return 503, {'detail': 'PRIVATE_NATIVE_FAILURE'}
            return original(method, url, headers, body, params)
        with patch.object(self.wire, 'native_handle', side_effect=failing):
            with self.assertRaisesRegex(F.ProofError, 'no automatic retry') as raised: self.run_setup()
        self.assertNotIn('PRIVATE_NATIVE_FAILURE', str(raised.exception))
        saved = F.fixture.read_private(self.path)
        self.assertEqual(saved['stage'], 'setup_failed')
        journal = saved['unknown_gui_setup']['journal']
        self.assertFalse(journal[-1]['readback_confirmed'])
        self.assertTrue(journal[-2]['readback_confirmed'])
        self.assertEqual(len(self.wire.users), 1); self.assertFalse(self.wire.keys)
        self.assertEqual(sum(m == 'POST' and p == '/key/generate' for m, p, _ in self.wire.requests), 1)
        calls = len(self.wire.requests)
        with self.assertRaisesRegex(F.ProofError, 'fresh separate handoff'): self.run_setup()
        self.assertEqual(len(self.wire.requests), calls)

    def test_native_actor_role_and_route_rechecked_before_write(self):
        original = self.wire.web_handle
        def change(method, url, headers, body=None):
            result = original(method, url, headers, body)
            if urlsplit(url).path == '/api/v1/auths/add':
                self.wire.accounts[self.wire.actor_token] = (self.wire.actor_id, 'admin')
            return result
        with patch.object(self.wire, 'web_handle', side_effect=change):
            with self.assertRaisesRegex(F.ProofError, 'inspect private handoff'): self.run_setup()
        self.assertFalse(self.wire.users)
        self.assertEqual(sum(m == 'POST' for m, _, _ in self.wire.requests), 1)

    def test_native_model_readback_rejects_foreign_acl(self):
        def fault(method, path, body):
            if method == 'POST' and path == '/api/v1/models/create':
                body['access_grants'][0]['principal_id'] = self.wire.old_user['id']
        self.wire.fault = fault
        with self.assertRaisesRegex(F.ProofError, 'inspect private handoff'): self.run_setup()
        saved = F.fixture.read_private(self.path)
        self.assertIn('ACL', saved['private_error']['message'])
        self.assertFalse(saved['unknown_gui_setup']['journal'][-1]['readback_confirmed'])

    def test_route_changed_after_actor_creation_stops_before_native_write(self):
        def fault(method, path, body):
            if method == 'POST' and path == '/api/v1/auths/add':
                self.wire.models[0]['litellm_params']['api_base'] = 'https://paid.invalid/v1'
        self.wire.fault = fault
        with self.assertRaisesRegex(F.ProofError, 'inspect private handoff'): self.run_setup()
        self.assertFalse(self.wire.users)
        self.assertFalse(any(m == 'POST' and p in ('/user/new', '/key/generate') for m, p, _ in self.wire.requests))
        self.assertIn('unknown_non_synthetic', F.fixture.read_private(self.path)['private_error']['message'])

    def test_connection_readback_cannot_silently_change_existing_header(self):
        def fault(method, path, body):
            if method == 'POST' and path == '/openai/config/update':
                body['OPENAI_API_CONFIGS']['0']['headers']['Preserve'] = 'changed'
        self.wire.fault = fault
        with self.assertRaisesRegex(F.ProofError, 'inspect private handoff'): self.run_setup()
        saved = F.fixture.read_private(self.path)
        self.assertIn('connection append', saved['private_error']['message'])
        self.assertFalse(saved['unknown_gui_setup']['journal'][-1]['readback_confirmed'])
        self.assertFalse(set(self.wire.workspace) & set(F.ALIASES))

    def test_existing_office_model_change_is_detected_at_final_preservation_readback(self):
        def fault(method, path, body):
            if method == 'POST' and path == '/api/v1/models/create':
                self.wire.workspace['gpt-5.4-mini']['params']['system'] = 'changed'
        self.wire.fault = fault
        with self.assertRaisesRegex(F.ProofError, 'inspect private handoff'): self.run_setup()
        self.assertIn('existing models', F.fixture.read_private(self.path)['private_error']['message'])


if __name__ == '__main__': unittest.main()
