"""Offline contract/rehearsal only; never a mocked whole native qualification."""
import ast
import base64
import collections.abc
import copy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import ModuleType, SimpleNamespace
from typing import Callable, TypedDict
import unittest
from unittest.mock import patch
from uuid import uuid4

import prove_responses_chat as P

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent.parent
NATIVE = Path(os.environ.get('GOAL584_NATIVE_SOURCE_ROOT', str(REPO / 'local/goal584/cost-display/open-webui/backend/open_webui')))
LLM = Path(os.environ.get('GOAL584_LITELLM_SOURCE_ROOT', str(REPO / 'local/goal584/litellm/upstream')))
OWUI_PIN = '6a18585ff4c2e5f6805f682222cfbc46dc669ef8'
LLM_PIN = 'd665dc1a6315847fcad6cc2c1264ceb47c06abce'


def load_owner(name):
    spec = importlib.util.spec_from_file_location('responses_rehearsal_' + name, SCRIPTS / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def native_functions():
    env = {'JSONCodec': SimpleNamespace(dumps=json.dumps, loads=json.loads, JSONDecodeError=json.JSONDecodeError),
           'Callable': Callable, 'collections': collections, 'copy': copy, 'deepcopy': copy.deepcopy}
    def extract(path, names):
        nodes = [n for n in ast.parse((NATIVE / path).read_bytes()).body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names
                 or isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id in names]
        if len(nodes) != len(names):
            raise AssertionError('Exact cached native owner functions unavailable')
        exec(compile(ast.Module(body=nodes, type_ignores=[]), path, 'exec'), env)
    extract('utils/misc.py', {'deep_update', 'get_provider_function', 'convert_output_to_messages',
        'get_paired_tool_call_ids', 'reconcile_tool_pairs', 'get_content_from_message'})
    extract('utils/payload.py', {'remove_open_webui_params', 'apply_model_params_to_body', 'apply_model_params_to_body_openai'})
    extract('routers/openai.py', {'RESPONSES_ALLOWED_FIELDS', '_normalize_stored_item', 'convert_to_responses_payload'})
    return env


def original_model():
    return {'id': 'goal584-a', 'base_model_id': None, 'name': 'goal584-a',
        'meta': {'capabilities': {'builtin_tools': False, 'vision': True}, 'filterIds': ['employee_budget_cost'],
                 'actionIds': ['employee_budget_cost_details'], 'toolIds': ['goal584_budget_echo']},
        'params': {'max_tokens': 5}, 'is_active': True,
        'access_grants': [{'principal_type': 'user', 'principal_id': str(uuid4()), 'permission': 'read'}]}


def scope(actor, chat, answer, call_id=None):
    return {'schema': 1, 'user_id': actor, 'chat_id': chat, 'answer_id': answer,
        'root_chat_id': chat, 'root_answer_id': answer, 'call_id': call_id or str(uuid4()), 'model': P.MODEL, 'category': 'personal'}


def synthetic_pair():
    actor, chat, answer = (str(uuid4()) for _ in range(3))
    key_hash = 'a' * 64
    tool = {'type': 'function', 'name': 'goal584_budget_echo_budget_echo', 'description': 'Native fixture Tool',
            'parameters': {'type': 'object', 'properties': {}, 'required': []}, 'strict': False}
    body = {'model': P.MODEL, 'input': [{'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'Hi'}]}],
        'instructions': P.SYSTEM, 'max_output_tokens': 16, 'stream': True, 'tools': [tool], 'parallel_tool_calls': False,
        'reasoning': P.REASONING, 'include': ['reasoning.encrypted_content'], 'store': False,
        'metadata': {'goal584_fixture': 'responses'}}
    reasoning = {'type': 'reasoning', 'id': 'rs_native_fixture', 'status': 'completed',
                 'summary': [{'type': 'summary_text', 'text': 'Synthetic reasoning'}], 'encrypted_content': 'synthetic-opaque'}
    call = {'type': 'function_call', 'id': 'fc_fixture', 'status': 'completed', 'call_id': 'call_native_fixture',
            'name': tool['name'], 'arguments': '{}'}
    followup = {**copy.deepcopy(body), 'input': body['input'] + [{k: call[k] for k in ('type', 'call_id', 'name', 'arguments')},
        {'type': 'function_call_output', 'call_id': call['call_id'], 'output': 'proof-tool-result'}]}
    p0, c0 = {'synthetic': True, 'control': {'admin_mode': True, 'tool_round': True}, 'requests': []}, {'schema': 1, 'requests': []}
    p1, c1 = copy.deepcopy(p0), copy.deepcopy(c0)
    usage = {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15,
        'input_tokens_details': {'cached_tokens': 0}, 'output_tokens_details': {'reasoning_tokens': 0}}
    for i, b in enumerate((body, followup)):
        output = [reasoning, call] if i == 0 else [reasoning, {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Proof'}]}]
        provider_id = 'resp_goal584_' + str(i) * 32
        p1['requests'].append({'id': provider_id, 'route': '/v1/responses', 'id_kind': 'provider_response',
            'body': {**copy.deepcopy(b), 'model': P.WIRE}, 'usage': copy.deepcopy(usage),
            'response': {'id': provider_id, 'model': P.WIRE, 'status': 'completed', 'usage': copy.deepcopy(usage),
                         'output': copy.deepcopy(output)}, 'lifecycle': {'terminal': True, 'outcome': 'completed'}})
        c1['requests'].append({'body': copy.deepcopy(b), 'body_after_auth': copy.deepcopy(b), 'route': '/v1/responses',
            'native_auth_user_id': actor, 'native_auth_key_hash': key_hash, 'attestation_present_before': True,
            'provenance_removed_after': True, 'verified_cost_scope': scope(actor, chat, answer)})
    return (p0, p1, c0, c1), {'actor': actor, 'key_hash': key_hash, 'chat_id': chat, 'answer_id': answer}


class ConfigurationTests(unittest.TestCase):
    def original_yaml(self):
        rag = load_owner('prove_rag_service')
        original = (SCRIPTS / 'litellm_config.yaml').read_bytes().replace(b'general_settings:',
            b'general_settings:\n  custom_auth: capture_webui_auth.gateway_auth\n  custom_auth_run_common_checks: true\n  missing_session_id: omit')
        return rag.append_embedding(original)

    def test_fixed_r_append_preserves_every_original_byte_and_all_existing_semantics(self):
        for newline in (b'\n', b'\r\n'):
            original = self.original_yaml().replace(b'\r\n', b'\n').replace(b'\n', newline)
            active = P.append_r(original)
            result = P.validate_config(original, active)
            self.assertEqual(result['original_sha256'], hashlib.sha256(original).hexdigest())
            self.assertEqual(result['active_sha256'], hashlib.sha256(active).hexdigest())
            self.assertIn(b'supports_reasoning: true', active)
            self.assertIn(b'max_output_tokens: 16', active)
            self.assertIn(b'max_tokens: 26', active)
            self.assertEqual(active.replace(P.R_BLOCK.replace('\n', newline.decode()).encode(), b'', 1), original)

    def test_config_refuses_ab_only_duplicate_r_or_change_to_prior_models(self):
        original = self.original_yaml()
        for bad in (b'', original.replace(b'goal584-e', b'goal584-x'), P.append_r(original)):
            with self.assertRaises(P.ProofError):
                P.append_r(bad)
        with self.assertRaises(P.ProofError):
            P.validate_config(original, P.append_r(original).replace(b'output_cost_per_token: 0.02', b'output_cost_per_token: 0.03', 1))

    def test_connection_append_keeps_exact_native_cc_connection_and_uses_numeric_r_index(self):
        gateway = 'synthetic-private-gateway'
        before = {'ENABLE_OPENAI_API': True, 'OPENAI_API_BASE_URLS': ['http://proxy:4000/v1'], 'OPENAI_API_KEYS': [gateway],
            'OPENAI_API_CONFIGS': {'0': {'enable': True, 'auth_type': 'bearer', 'model_ids': ['goal584-a', 'goal584-b'],
                'headers': {'X-OpenWebUI-User-Id': '{{USER_ID}}', 'X-OpenWebUI-Task': '{{TASK}}'}, 'keep_native_option': True}}}
        frozen = copy.deepcopy(before)
        actual = P.connection_config(before, gateway)
        self.assertEqual(before, frozen)
        self.assertEqual(actual['OPENAI_API_CONFIGS']['0'], frozen['OPENAI_API_CONFIGS']['0'])
        self.assertEqual(actual['OPENAI_API_CONFIGS']['1']['api_type'], 'responses')
        self.assertEqual(actual['OPENAI_API_CONFIGS']['1']['model_ids'], [P.MODEL])
        self.assertEqual(actual['OPENAI_API_BASE_URLS'], ['http://proxy:4000/v1', 'http://proxy:4000'])
        with self.assertRaises(P.ProofError):
            P.connection_config(before, 'different-owner-secret')

    def test_workspace_clone_is_independent_r_only_with_native_tools_and_no_builtin_extras(self):
        original, actor = original_model(), str(uuid4())
        frozen = copy.deepcopy(original)
        model = P.workspace_model(original, actor, 'employee_budget_cost', 'employee_budget_cost_details', 'goal584_budget_echo')
        self.assertEqual(original, frozen)
        self.assertEqual(model['access_grants'], [{'principal_type': 'user', 'principal_id': actor, 'permission': 'read'}])
        self.assertEqual(model['meta']['filterIds'], ['employee_budget_cost', P.PROBE_ID])
        self.assertIs(model['meta']['capabilities']['builtin_tools'], False)
        self.assertEqual(model['params']['function_calling'], 'native')
        self.assertEqual(model['params']['max_tokens'], 16)

    def test_controls_restore_exact_absence_and_values_without_provider_reset(self):
        before = {'tool_round': False, 'admin_mode': True, 'delay_ms': 0}
        after = {**before, 'tool_round': True, 'response_status': 200}
        self.assertEqual(P.controls_patch(before, after), {'tool_round': False, 'response_status': None})
        self.assertEqual(P.controls_patch(before, before), {})

    def test_worker_protocol_is_whole_stdout_bound_source_phase_and_secret_safe(self):
        packet = {'schema': 1, 'proof': P.PROOF, 'phase': 'prepare', 'passed': True, 'source_sha256': 'a' * 64,
                  'not_qualified': P.LIMITS, 'result': {}, 'stage': 'prepared'}
        result = SimpleNamespace(stdout=json.dumps(packet).encode(), stderr=b'')
        self.assertEqual(P.worker_packet(result, 'prepare', 'a' * 64), packet)
        for raw in (b'prefix' + result.stdout, result.stdout + b'\n{}', json.dumps({**packet, 'phase': 'restore'}).encode(),
                    json.dumps({**packet, 'schema': True}).encode(), json.dumps({**packet, 'unexpected': 'sk-' + 'x' * 32}).encode(),
                    json.dumps({**packet, 'unknown_field': 'do not silently ignore'}).encode()):
            with self.assertRaises(P.ProofError):
                P.worker_packet(SimpleNamespace(stdout=raw, stderr=b''), 'prepare', 'a' * 64)

    def test_root_saturates_at_shallow_worker_mount_and_top_level_import_is_cold(self):
        self.assertEqual(Path('/proof/prove_responses_chat.py').parent.parent.parent, Path('/'))
        tree = ast.parse(Path(P.__file__).read_bytes())
        imports = [n.module or '' for n in tree.body if isinstance(n, ast.ImportFrom)]
        self.assertFalse(any(name.startswith(('playwright', 'litellm', 'provision_')) for name in imports))

    def test_original_worker_failure_is_retained_and_no_late_error_can_keep_pass_true(self):
        original = {'schema': 1, 'proof': P.PROOF, 'phase': 'observe', 'passed': False,
                    'error_class': 'ProofError', 'failed_stage': 'observing_two_native_r_calls'}
        receipt = {'passed': True, 'stage': 'observe'}
        P.record_failure(receipt, P.WorkerFailure(original))
        self.assertIs(receipt['failure']['worker'], original)
        self.assertIs(receipt['passed'], False)
        P.record_failure(receipt, ValueError('later restoration must not replace original'))
        self.assertIs(receipt['failure']['worker'], original)
        self.assertEqual(receipt['failure']['stage'], 'observe')

    def test_failure_restoration_attempts_later_independent_native_owners_after_first_failure(self):
        worker = object.__new__(P.Worker)
        worker.r = {'schema': 1, 'key_hash': 'a' * 64, 'original_openai': {'profile': 'original'},
                    'original_tool': {'access_grants': []}, 'original_controls': {'tool_round': False}}
        worker.admin = 'private-admin-token'
        calls = []
        def native_ok(method, path, **kwargs):
            calls.append(path)
            raise ValueError('original cap restoration failure')
        def webui_ok(method, path, **kwargs):
            calls.append(path)
            if path == '/openai/config':
                return {'profile': 'original'}
            return {'access_grants': []}
        controls = {'tool_round': True}
        def provider(method='GET', path='/__proof/requests', body=None):
            calls.append(path)
            if body:
                controls.update(body)
            return {'control': controls.copy()}
        worker.native = SimpleNamespace(ok=native_ok)
        worker.webui = SimpleNamespace(ok=webui_ok)
        worker.d = {'TOOL_ID': 'native_echo', 'provider': provider,
                    'grant_set': lambda value: {tuple(sorted(v.items())) for v in value['access_grants']}}
        worker.stage = lambda name: calls.append(name)
        result = worker.restore()
        self.assertEqual(result['restoration']['r_cap'], {'completed': False, 'error_class': 'ValueError'})
        self.assertTrue(all(result['restoration'][name]['completed'] for name in ('openai_config', 'tool_grants', 'provider_controls')))
        self.assertEqual(controls, {'tool_round': False})
        self.assertFalse(result['financial_rows_users_keys_deleted'])
        self.assertNotIn('/user/delete', calls)
        self.assertNotIn('/key/delete', calls)


class DenialDiagnosticTests(unittest.TestCase):
    """Actual Worker.denied/worker_main; only external API/file-mode boundaries doubled."""
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'responses-state.private.json'
        self.gateway = load_owner('prove_gateway_auth')
        # Windows cannot attest POSIX modes. Exercise the real atomic-write bytes;
        # the native private_parent/mode guard remains an explicit runtime gate.
        self.mode_patch = patch.object(self.gateway, 'private_parent', return_value=None)
        self.mode_patch.start(); self.addCleanup(self.mode_patch.stop)
        self.state_patch = patch.object(P, 'R_STATE', self.path)
        self.state_patch.start(); self.addCleanup(self.state_patch.stop)
        self.uid, self.chat, self.answer = (str(uuid4()) for _ in range(3))
        self.secret = 'sk-' + 'z' * 32
        self.rows = [{'request_id': 'resp_native_' + str(i), 'status': 'success', 'spend': .2,
            'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15,
            'metadata': {'private': self.secret, 'headers': {'Authorization': 'private-native-header'}}} for i in range(2)]
        self.provider = {'synthetic': True, 'control': {'tool_round': True}, 'requests': [{'id': 'physical_1'}, {'id': 'physical_2'}]}
        self.capture = {'schema': 1, 'requests': [{'body': {'input': 'private chat text', 'secret': self.secret}}]}
        self.user = {'user_id': self.uid, 'user_role': 'internal_user', 'models': [P.MODEL], 'max_budget': 20,
            'spend': .4, 'budget_duration': '1mo', 'budget_reset_at': '2026-12-01T00:00:00Z', 'teams': []}
        self.key = {'user_id': self.uid, 'models': [P.MODEL], 'key_alias': 'private-alias', 'metadata': {'private': self.secret},
            'token': self.secret, 'max_budget': 0, 'spend': .4, 'budget_duration': '1mo',
            'budget_reset_at': '2026-12-01T00:00:00+00:00', 'blocked': False, 'allowed_routes': ['llm_api_routes']}
        self.calls = []

    def worker(self, *, extra_rows=(), provider_changed=False, failures=()):
        worker = object.__new__(P.Worker)
        worker.secrets = [self.secret]
        worker.r = {'schema': 1, 'actor': {'id': self.uid, 'token': self.secret}, 'stage': 'ready_for_ordinary_zero_denial',
            'success_rows': copy.deepcopy(self.rows), 'post_native_zero_rows': copy.deepcopy(self.rows), 'denial_provider_baseline': copy.deepcopy(self.provider),
            'context_before': {'requests': []}, 'protected_r': P.protected_r(self.user, {**self.key, 'max_budget': 20})}
        def read(name, value):
            self.calls.append(name)
            if name in failures:
                raise OSError('private exception ' + self.secret)
            return copy.deepcopy(value)
        current = copy.deepcopy(self.provider)
        if provider_changed:
            current['requests'].append({'id': 'unexpected_physical'})
        def captures():
            return read('captures', (current, self.capture))
        worker.captures = captures
        worker.native = SimpleNamespace(logs=lambda uid: read('logs', self.rows + list(extra_rows)),
                                        user_info=lambda uid: read('user', self.user))
        worker.key = lambda: read('key', self.key)
        worker.d = {'write_private': lambda path, state: read('write', self.gateway.write_private(path, state))
                    if 'write' not in failures else read('write', None)}
        worker.webui = SimpleNamespace(ok=lambda *a, **kw: (_ for _ in ()).throw(AssertionError('financial guard must fail first')))
        return worker

    def zero_row(self):
        return {'request_id': 'native_zero_failure', 'status': 'failure', 'spend': 0,
                'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
                'metadata': {'private': self.secret, 'body': 'foreign private text'}}

    def assert_denied_failure(self, worker, message):
        with self.assertRaisesRegex(P.ProofError, message):
            worker.denied(self.chat, self.answer)
        diagnostic = worker.denial_diagnostic
        self.assertIs(P.validate_denial_diagnostic(diagnostic), diagnostic)
        exported = json.dumps(diagnostic)
        for private in (self.secret, 'Authorization', 'private-native-header', 'private chat text', 'foreign private text', 'private exception'):
            self.assertNotIn(private, exported)
        for name in ('captures', 'logs', 'user', 'key'):
            self.assertEqual(self.calls.count(name), 1)
        return diagnostic

    def test_native_zero_raw_row_still_fails_and_exact_raws_use_existing_private_writer(self):
        extra = self.zero_row(); worker = self.worker(extra_rows=[extra])
        diagnostic = self.assert_denied_failure(worker, 'changed the bracketed native raw journal')
        self.assertTrue(diagnostic['provider_snapshot_equal'])
        self.assertEqual((diagnostic['provider_count'], diagnostic['baseline_provider_count'], diagnostic['raw_row_count']), (2, 2, 3))
        self.assertTrue(diagnostic['raw_snapshot_retained'])
        self.assertEqual(diagnostic['capture_errors'], [])
        self.assertEqual(diagnostic['rows'][-1]['status'], 'failure')
        self.assertEqual(diagnostic['rows'][-1]['spend_usd'], '0')
        self.assertFalse(diagnostic['rows'][-1]['is_original_success_id'])
        self.assertFalse(diagnostic['rows'][-1]['original_full_row_unchanged'])
        self.assertTrue(all(row['original_full_row_unchanged'] for row in diagnostic['rows'][:2]))
        self.assertEqual(diagnostic['raw_rows_sha256'], P.digest(self.rows + [extra]))
        saved = json.loads(self.path.read_text(encoding='utf8'))
        self.assertEqual(saved['denial_observation'], {'provider': self.provider, 'capture': self.capture,
            'rows': self.rows + [extra], 'user': self.user, 'key': self.key})
        self.assertEqual(saved['denial_diagnostic'], diagnostic)
        self.assertEqual(diagnostic['budgets']['key_cap_usd'], '0')
        self.assertEqual(diagnostic['budgets']['user_spend_usd'], '0.4')
        self.assertTrue(diagnostic['budgets']['protected_fields_equal_except_key_cap'])

    def test_primary_provider_violation_survives_user_key_and_private_write_failures(self):
        worker = self.worker(provider_changed=True, failures={'user', 'key', 'write'})
        diagnostic = self.assert_denied_failure(worker, 'changed the full provider snapshot')
        self.assertFalse(diagnostic['provider_snapshot_equal'])
        self.assertFalse(diagnostic['raw_snapshot_retained'])
        self.assertIsNone(diagnostic['budgets'])
        self.assertEqual(set(diagnostic['capture_errors']), {'native_user_read_failed', 'native_key_read_failed', 'private_snapshot_write_failed'})

    def test_primary_journal_violation_survives_capture_and_private_write_failures(self):
        worker = self.worker(extra_rows=[self.zero_row()], failures={'captures', 'write'})
        diagnostic = self.assert_denied_failure(worker, 'changed the bracketed native raw journal')
        self.assertIsNone(diagnostic['provider_count'])
        self.assertIsNone(diagnostic['provider_snapshot_equal'])
        self.assertEqual(diagnostic['raw_row_count'], 3)
        self.assertIn('provider_capture_read_failed', diagnostic['capture_errors'])

    def test_actual_atomic_private_replace_failure_cannot_mask_journal_violation(self):
        worker = self.worker(extra_rows=[self.zero_row()])
        with patch.object(self.gateway.os, 'replace', side_effect=OSError('private replace ' + self.secret)):
            diagnostic = self.assert_denied_failure(worker, 'changed the bracketed native raw journal')
        self.assertIn('private_snapshot_write_failed', diagnostic['capture_errors'])
        self.assertFalse(diagnostic['raw_snapshot_retained'])
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_unavailable_native_journal_is_not_defaulted_to_empty_or_accepted(self):
        worker = self.worker(failures={'logs'})
        diagnostic = self.assert_denied_failure(worker, 'observation is unavailable')
        self.assertIsNone(diagnostic['raw_row_count'])
        self.assertIsNone(diagnostic['raw_rows_sha256'])
        self.assertIsNone(diagnostic['rows'])
        self.assertIn('native_rows_read_failed', diagnostic['capture_errors'])

    def test_original_row_metadata_mutation_is_still_a_strict_raw_journal_failure(self):
        worker = self.worker()
        self.rows[0]['metadata']['late_change'] = 'private late value'
        diagnostic = self.assert_denied_failure(worker, 'changed the bracketed native raw journal')
        self.assertTrue(diagnostic['rows'][0]['is_original_success_id'])
        self.assertFalse(diagnostic['rows'][0]['original_full_row_unchanged'])
        self.assertTrue(diagnostic['rows'][1]['original_full_row_unchanged'])
        self.assertNotIn('private late value', json.dumps(diagnostic))

    def test_user_read_failure_with_equal_financial_snapshots_is_its_own_failure(self):
        worker = self.worker(failures={'user'})
        diagnostic = self.assert_denied_failure(worker, 'observation is unavailable')
        self.assertTrue(diagnostic['provider_snapshot_equal'])
        self.assertEqual(diagnostic['raw_row_count'], 2)
        self.assertIn('native_user_read_failed', diagnostic['capture_errors'])

    def test_oversized_raw_snapshot_retains_counts_hashes_and_remains_failure(self):
        extra = self.zero_row(); extra['metadata']['body'] = 'private-large-' * 4000
        worker = self.worker(extra_rows=[extra])
        with patch.object(P, 'MAX_BYTES', 10000):
            diagnostic = self.assert_denied_failure(worker, 'changed the bracketed native raw journal')
        self.assertEqual(diagnostic['raw_row_count'], 3)
        self.assertEqual(diagnostic['raw_rows_sha256'], P.diagnostic_hash(self.rows + [extra]))
        self.assertIn('raw_snapshot_exceeded_bound', diagnostic['capture_errors'])
        self.assertFalse(diagnostic['raw_snapshot_retained'])
        saved = json.loads(self.path.read_text(encoding='utf8'))
        self.assertNotIn('denial_observation', saved)
        self.assertLess(self.path.stat().st_size, 10000)

    def test_private_bound_counts_actual_existing_writer_format_not_compact_json(self):
        value = {'schema': 1, 'rows': [{'field': n} for n in range(50)]}
        compact = len(P.encoded(value))
        actual = len(json.dumps(value, allow_nan=False).encode()) + len(os.linesep.encode())
        self.assertGreater(actual, compact)
        with patch.object(P, 'MAX_BYTES', compact), self.assertRaises(P.ProofError):
            P.bound_private_snapshot(value)
        with patch.object(P, 'MAX_BYTES', actual):
            P.bound_private_snapshot(value)

    def test_foreign_owner_invalid_usage_and_nonfinite_money_never_escape_projection(self):
        for kind in ('foreign_owner', 'usage', 'money', 'unknown_status'):
            with self.subTest(kind=kind):
                self.calls.clear(); extra = self.zero_row()
                if kind == 'foreign_owner':
                    self.user['user_id'] = self.secret
                elif kind == 'usage':
                    extra['prompt_tokens'] = True
                elif kind == 'money':
                    extra['spend'] = 'NaN'
                else:
                    extra['status'] = self.secret
                worker = self.worker(extra_rows=[extra])
                diagnostic = self.assert_denied_failure(worker, 'changed the bracketed native raw journal')
                if kind == 'foreign_owner':
                    self.assertIsNone(diagnostic['budgets']); self.assertIn('budget_projection_failed', diagnostic['capture_errors'])
                    self.user['user_id'] = self.uid
                elif kind in ('usage', 'money'):
                    self.assertIsNone(diagnostic['rows']); self.assertIn('rows_projection_failed', diagnostic['capture_errors'])
                else:
                    self.assertEqual(diagnostic['rows'][-1]['status'], 'other')

    def test_worker_failure_packet_and_host_record_keep_diagnostic_and_primary_error(self):
        worker = self.worker(extra_rows=[self.zero_row()], failures={'write'})
        output = io.StringIO()
        args = SimpleNamespace(worker_action='denied', chat_id=self.chat, answer_id=self.answer)
        with patch.object(P, 'Worker', return_value=worker), redirect_stdout(output):
            self.assertEqual(P.worker_main(args), 1)
        packet = P.worker_packet(SimpleNamespace(stdout=output.getvalue().encode(), stderr=b''), 'denied',
                                 hashlib.sha256(Path(P.__file__).read_bytes()).hexdigest(), [self.secret])
        self.assertFalse(packet['passed'])
        self.assertEqual(packet['error_message'], 'Responses ordinary zero changed the bracketed native raw journal')
        self.assertEqual(packet['denial_diagnostic']['raw_row_count'], 3)
        self.assertIn('private_snapshot_write_failed', packet['denial_diagnostic']['capture_errors'])
        host = {'stage': 'worker_denied'}
        P.record_failure(host, P.WorkerFailure(packet))
        P.record_failure(host, ValueError('late rollback failure'))
        self.assertIs(host['failure']['worker'], packet)
        self.assertEqual(host['failure']['stage'], 'worker_denied')
        # Execute the actual nested host phase, not a replacement coordinator.
        tree = ast.parse(Path(P.__file__).read_bytes())
        owner = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'host_main')
        phase = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == 'phase')
        saved = []
        response = SimpleNamespace(returncode=1, stdout=output.getvalue().encode(), stderr=b'')
        receipt = {'stage': 'one_ordinary_send'}
        namespace = {**P.__dict__, 'receipt': receipt, 'fixture': SimpleNamespace(command=['existing-compose-owner']),
            'args': SimpleNamespace(output=Path(self.directory.name)), 'source': packet['source_sha256'],
            'secrets': [self.secret], 'subprocess': SimpleNamespace(run=lambda *a, **kw: response),
            'write_json': lambda path, data: saved.append((path.name, copy.deepcopy(data)))}
        exec(compile(ast.Module(body=[phase], type_ignores=[]), '<actual-host-phase>', 'exec'), namespace)
        with self.assertRaises(P.WorkerFailure) as raised:
            namespace['phase']('denied', {'chat_id': self.chat, 'message_id': self.answer})
        P.record_failure(receipt, raised.exception)
        self.assertEqual(receipt['failure']['stage'], 'worker_denied')
        self.assertEqual(receipt['denial_diagnostic'], packet['denial_diagnostic'])
        self.assertEqual(saved, [('responses-denied.json', packet)])
        restored = {**packet, 'phase': 'restore', 'passed': True, 'result': {}, 'stage': 'failure_restoration_attempted'}
        restored.pop('denial_diagnostic')
        response.stdout, response.returncode = json.dumps(restored).encode(), 0
        namespace['phase']('restore')
        self.assertEqual(receipt['stage'], 'worker_denied')
        self.assertEqual(receipt['failure']['worker'], packet)

    def test_worker_protocol_rejects_unknown_nested_fields_errors_values_and_wrong_phase(self):
        worker = self.worker(extra_rows=[self.zero_row()])
        diagnostic = self.assert_denied_failure(worker, 'changed the bracketed native raw journal')
        base = {'schema': 1, 'proof': P.PROOF, 'phase': 'denied', 'passed': False, 'source_sha256': 'a' * 64,
                'not_qualified': P.LIMITS, 'error_class': 'ProofError', 'denial_diagnostic': diagnostic}
        mutations = []
        for kind in ('top', 'row', 'budget', 'error', 'status', 'nan', 'bool_count', 'phase'):
            packet = copy.deepcopy(base); d = packet['denial_diagnostic']
            if kind == 'top': d['headers'] = {'Authorization': 'private'}
            elif kind == 'row': d['rows'][0]['metadata'] = {'unknown': 'private'}
            elif kind == 'budget': d['budgets']['token'] = 'unrecognized'
            elif kind == 'error': d['capture_errors'] = ['unrecognized error text']
            elif kind == 'status': d['rows'][0]['status'] = 'unknown'
            elif kind == 'nan': d['rows'][0]['spend_usd'] = 'NaN'
            elif kind == 'bool_count': d['raw_row_count'] = True
            else: packet['phase'] = 'observe'
            mutations.append((kind, packet))
        for kind, packet in mutations:
            with self.subTest(kind=kind), self.assertRaises(P.ProofError):
                P.worker_packet(SimpleNamespace(stdout=json.dumps(packet).encode(), stderr=b''), packet['phase'], 'a' * 64)


class NativeAuditBracketTests(unittest.TestCase):
    """Real Worker.limit/denied and NativeProof.poll; local external I/O only."""
    def setUp(self):
        import prove_native_budgets as native
        self.native_module = native
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'responses-state.private.json'
        self.gateway = load_owner('prove_gateway_auth')
        modes = patch.object(self.gateway, 'private_parent', return_value=None)
        modes.start(); self.addCleanup(modes.stop)
        state = patch.object(P, 'R_STATE', self.path); state.start(); self.addCleanup(state.stop)
        self.now = 100.0
        monotonic = patch.object(P.time, 'monotonic', side_effect=lambda: self.now)
        sleep = patch.object(P.time, 'sleep', side_effect=lambda seconds: setattr(self, 'now', self.now + seconds))
        monotonic.start(); sleep.start(); self.addCleanup(monotonic.stop); self.addCleanup(sleep.stop)
        self.uid, self.chat, self.answer = (str(uuid4()) for _ in range(3))
        self.key_hash = 'a' * 64
        self.original = [{'request_id': 'original-' + str(i), 'status': 'success', 'spend': .2,
                          'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15} for i in range(2)]
        self.audit = {'request_id': str(uuid4()), 'user': self.uid, 'api_key': self.key_hash,
            'status': 'failure', 'spend': 0.0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0,
            'model_group': P.MODEL, 'model_id': P.DEPLOYMENT, 'model': 'openai/' + P.WIRE,
            'custom_llm_provider': 'openai', 'call_type': 'aresponses',
            'metadata': {'error_information': {'error_class': 'BudgetExceededError', 'error_code': '422',
                'error_budget_entity_type': 'key', 'error_budget_entity_id': self.key_hash,
                'error_budget_limit': 0, 'error_budget_spend': .4}}}

    def worker(self, *, delay_reads=0, wrong_rows=None, read_error=False, late=False):
        values, _ = synthetic_pair(); p0, p1, c0, c1 = values
        self.p, self.c = copy.deepcopy(p1), copy.deepcopy(c1)
        self.pending = delay_reads
        self.audit_reads, self.native_attempts = 0, 0
        self.current_rows = copy.deepcopy(wrong_rows if wrong_rows is not None else [self.audit] + self.original)
        self.user = {'user_id': self.uid, 'user_role': 'internal_user', 'models': [P.MODEL], 'max_budget': 20,
            'spend': .4, 'budget_duration': '1mo', 'budget_reset_at': '2026-12-01T00:00:00Z', 'teams': []}
        self.key = {**copy.deepcopy(self.user), 'key_alias': 'canonical-private-R',
                    'metadata': {'owui_budget_model': P.MODEL, 'owui_budget_namespace': 'user-model-v1'},
                    'blocked': False, 'allowed_routes': ['llm_api_routes']}
        worker = object.__new__(P.Worker)
        worker.secrets = ['sk-' + 'x' * 32]
        worker.r = {'schema': 1, 'stage': 'two_native_calls_observed', 'actor': {'id': self.uid, 'token': 'private-session'},
            'key': worker.secrets[0], 'key_hash': self.key_hash, 'success_rows': copy.deepcopy(self.original),
            'protected_r': P.protected_r(self.user, self.key), 'context_before': copy.deepcopy(c0),
            'success_context': copy.deepcopy(c1), 'original_finance': {'unchanged': True},
            'original_controls': {**copy.deepcopy(p1['control']), 'tool_round': False}}
        worker.captures = lambda: (copy.deepcopy(self.p), copy.deepcopy(self.c))
        def unsigned(webui, method, path, token, body):
            self.assertEqual((method, path, body), ('POST', '/openai/responses', P.unsigned_raw_body()))
            self.c['requests'].append({'route': '/responses', 'body': copy.deepcopy(body), 'body_after_auth': copy.deepcopy(body),
                'attestation_present_before': False, 'provenance_removed_after': True,
                'auth_failure': {'scope': 'custom_auth', 'status_code': 403, 'code': 'unclassified'}})
            return 403, {'detail': 'Signed budget provenance required'}
        def logs(uid):
            self.assertEqual(uid, self.uid)
            if not self.native_attempts:
                return copy.deepcopy(self.original)
            self.audit_reads += 1
            if read_error:
                raise OSError('private native observation failure')
            if late:
                self.now += 60.01
            if self.pending:
                self.pending -= 1
                return copy.deepcopy(self.original)
            return copy.deepcopy(self.current_rows)
        def request(method, path, *, token, body):
            self.assertEqual((method, path, token), ('POST', '/v1/responses', worker.secrets[0]))
            self.assertEqual(body, {'model': P.MODEL, 'input': 'Hi', 'max_output_tokens': 16, 'store': False, 'stream': False})
            self.native_attempts += 1
            self.c['requests'].append({'route': '/v1/responses', 'body': copy.deepcopy(body), 'body_after_auth': copy.deepcopy(body),
                'attestation_present_before': False, 'provenance_removed_after': True,
                'auth_failure': {'scope': 'custom_auth', 'status_code': 422, 'code': 'unclassified'}})
            return 422, {'error': {'type': 'budget_exceeded', 'message': self.native_module.BUDGET_GENERIC_MESSAGE}}, {}
        def cap(method, path, *, body):
            self.assertEqual((method, path), ('POST', '/key/update'))
            self.assertEqual(body['key'], self.key_hash)
            self.key['max_budget'] = body['max_budget']; return {}
        native = object.__new__(self.native_module.NativeProof)
        native.timeout, native.poll_deadline = 60, None
        native.logs, native.request, native.ok = logs, request, cap
        native.user_info = lambda uid: copy.deepcopy(self.user)
        worker.native, worker.key = native, lambda: copy.deepcopy(self.key)
        worker.webui = SimpleNamespace(session=lambda *a: None, ok=lambda *a, **kw: {'user_id': self.uid,
            'chat': {'history': {'messages': {self.answer: {'done': True, 'content': '',
                'error': {'message': self.native_module.BUDGET_GENERIC_MESSAGE}}}}}})
        worker.protected_main = lambda: {'unchanged': True}
        def provider(method='GET', path='/__proof/requests', body=None):
            if body is not None:
                self.assertEqual((method, path), ('POST', '/__proof/control'))
                self.p['control'].update(body)
            return copy.deepcopy(self.p)
        worker.d = {'response': unsigned, 'write_private': self.gateway.write_private, 'provider': provider}
        return worker

    def ordinary_denial(self):
        body = copy.deepcopy(self.c['requests'][0]['body'])
        self.c['requests'].append({'body': body, 'body_after_auth': copy.deepcopy(body),
            'attestation_present_before': True, 'provenance_removed_after': True,
            'auth_failure': {'scope': 'custom_auth', 'status_code': 422, 'code': 'unclassified'}})

    def test_delayed_audit_is_read_settled_before_ui_without_repeating_native_attempt(self):
        worker = self.worker(delay_reads=2)
        result = worker.limit()
        self.assertEqual(self.native_attempts, 1)
        self.assertEqual(self.audit_reads, 3)
        self.assertGreater(self.now, 100)
        self.assertIsNone(worker.native.poll_deadline)
        self.assertEqual(result['native_audit']['native_audit_row_count'], 1)
        self.assertEqual(result['native_audit']['native_call_type'], 'aresponses')
        self.assertEqual(worker.r['native_audit_row'], self.audit)
        self.assertEqual(worker.r['post_native_zero_rows'], self.current_rows)
        self.assertEqual(json.loads(self.path.read_text(encoding='utf8'))['native_audit_row'], self.audit)
        self.assertEqual(worker.r['stage'], 'ready_for_ordinary_zero_denial')
        self.assertEqual(len(self.p['requests']), 2)

    def test_missing_audit_hits_bounded_read_timeout_without_extra_inference(self):
        worker = self.worker(delay_reads=1000)
        with self.assertRaisesRegex(P.ProofError, 'Timed out|read deadline'):
            worker.limit()
        self.assertLessEqual(self.now, 160)
        self.assertEqual(self.native_attempts, 1)
        self.assertNotIn('native_audit_evidence', worker.r)
        self.assertIsNone(worker.native.poll_deadline)

    def test_perfect_audit_observed_after60_cannot_be_accepted_by_native_poll(self):
        worker = self.worker(late=True)
        with self.assertRaisesRegex(P.ProofError, 'exceeded its read deadline'):
            worker.limit()
        self.assertEqual(self.native_attempts, 1)
        self.assertEqual(self.audit_reads, 1)
        self.assertEqual(worker.denial_diagnostic['raw_row_count'], 3)
        self.assertNotIn('native_audit_evidence', worker.r)

    def test_unknown_duplicate_foreign_nonzero_or_mutated_rows_fail_on_first_read(self):
        cases = ['duplicate', 'extra', 'missing', 'positive_mutation', 'user', 'key', 'model', 'group', 'deployment',
                 'provider', 'call_type', 'cost', 'status', 'usage', 'float_usage', 'error_class', 'error_code',
                 'entity_type', 'entity_id', 'limit', 'spend', 'claimed_scope', 'malformed_metadata']
        for kind in cases:
            with self.subTest(kind=kind):
                self.now = 100
                rows = copy.deepcopy([self.audit] + self.original); row = rows[0]; error = row['metadata']['error_information']
                if kind == 'duplicate': row['request_id'] = rows[1]['request_id']
                elif kind == 'extra': rows.append({**copy.deepcopy(row), 'request_id': str(uuid4())})
                elif kind == 'missing': rows = [row]
                elif kind == 'positive_mutation': rows[1]['spend'] = .21
                elif kind == 'user': row['user'] = str(uuid4())
                elif kind == 'key': row['api_key'] = 'b' * 64
                elif kind == 'model': row['model'] = P.MODEL
                elif kind == 'group': row['model_group'] = 'goal584-a'
                elif kind == 'deployment': row['model_id'] = 'goal584-deployment-a'
                elif kind == 'provider': row['custom_llm_provider'] = 'other'
                elif kind == 'call_type': row['call_type'] = 'acompletion'
                elif kind == 'cost': row['spend'] = .001
                elif kind == 'status': row['status'] = 'success'
                elif kind == 'usage': row['total_tokens'] = 1
                elif kind == 'float_usage': row['prompt_tokens'] = 0.0
                elif kind == 'error_class': error['error_class'] = 'HTTPException'
                elif kind == 'error_code': error['error_code'] = '403'
                elif kind == 'entity_type': error['error_budget_entity_type'] = 'user'
                elif kind == 'entity_id': error['error_budget_entity_id'] = 'b' * 64
                elif kind == 'limit': error['error_budget_limit'] = 20
                elif kind == 'spend': error['error_budget_spend'] = .6
                elif kind == 'claimed_scope': row['metadata']['spend_logs_metadata'] = {'owui_budget': {'schema': 1}}
                else: row['metadata'] = 'not-json'
                worker = self.worker(wrong_rows=rows)
                with self.assertRaises(P.ProofError): worker.limit()
                self.assertEqual(self.audit_reads, 1)
                self.assertEqual(self.native_attempts, 1)
                self.assertNotIn('native_audit_evidence', worker.r)

    def test_optional_native_owner_fields_are_not_invented_and_metadata_string_is_parsed(self):
        audit = copy.deepcopy(self.audit)
        audit['metadata'] = json.dumps({'error_information': {'error_class': 'BudgetExceededError', 'error_code': '422'}})
        worker = self.worker(wrong_rows=[audit] + self.original)
        result = worker.limit()['native_audit']
        self.assertEqual(result['verified_native_budget_fields'], [])
        self.assertEqual(result['lineage'], 'causal_before_after_single_native_http_attempt_not_provider_response_id')
        self.assertNotIn('provider_response_id', result)

    def test_native_api_read_error_is_not_pending_or_retried(self):
        worker = self.worker(read_error=True)
        with self.assertRaisesRegex(P.ProofError, 'observation is unavailable'):
            worker.limit()
        self.assertEqual(self.audit_reads, 1)
        self.assertEqual(self.native_attempts, 1)
        self.assertIn('native_rows_read_failed', worker.denial_diagnostic['capture_errors'])

    def test_limit_failure_packet_keeps_actual_audit_diagnostic_under_strict_phase_protocol(self):
        wrong = copy.deepcopy(self.audit); wrong['metadata']['error_information']['error_code'] = '403'
        worker = self.worker(wrong_rows=[wrong] + self.original)
        output = io.StringIO()
        with patch.object(P, 'Worker', return_value=worker), redirect_stdout(output):
            self.assertEqual(P.worker_main(SimpleNamespace(worker_action='limit')), 1)
        packet = P.worker_packet(SimpleNamespace(stdout=output.getvalue().encode(), stderr=b''), 'limit',
                                 hashlib.sha256(Path(P.__file__).read_bytes()).hexdigest(), worker.secrets)
        self.assertFalse(packet['passed'])
        self.assertEqual(packet['failed_stage'], 'settling_one_direct_native_zero_audit')
        self.assertEqual(packet['denial_diagnostic']['raw_row_count'], 3)
        self.assertIn('not the exact native budget422 class', packet['error_message'])
        self.assertEqual(self.native_attempts, 1)

    def test_ui_denial_preserves_all_three_rows_and_restores_native_caps_controls(self):
        worker = self.worker(); worker.limit(); self.ordinary_denial()
        result = worker.denied(self.chat, self.answer)
        self.assertTrue(result['original_positive_rows_unchanged'])
        self.assertEqual(result['native_audit_row_count'], 1)
        self.assertTrue(result['native_audit_row_unchanged'])
        self.assertNotIn('native_rows_unchanged', result)
        self.assertEqual(self.key['max_budget'], 20)
        self.assertEqual(self.key['spend'], .4)
        self.assertEqual(self.native_attempts, 1)
        self.assertFalse(self.p['control']['tool_round'])
        self.assertEqual(worker.r['stage'], 'qualified_native_responses_financial_profile')

    def test_ui_cannot_add_or_mutate_even_a_zero_cost_audit(self):
        for mutation in ('extra', 'audit_changed', 'positive_changed', 'provider_changed'):
            with self.subTest(mutation=mutation):
                worker = self.worker(); worker.limit(); self.ordinary_denial()
                if mutation == 'extra': self.current_rows.append({**copy.deepcopy(self.audit), 'request_id': str(uuid4())})
                elif mutation == 'audit_changed': self.current_rows[0]['metadata']['changed'] = True
                elif mutation == 'positive_changed': self.current_rows[1]['prompt_tokens'] = 10.0
                else: self.p['requests'].append({'id': 'unexpected'})
                with self.assertRaisesRegex(P.ProofError, 'provider snapshot|bracketed native raw journal'):
                    worker.denied(self.chat, self.answer)
                self.assertEqual(self.native_attempts, 1)


class ContextEvidenceTests(unittest.TestCase):
    def test_exact_two_call_contract_retains_actual_context_and_explicit_reasoning_gap(self):
        values, owner = synthetic_pair()
        actual = P.verify_two_calls(*values, **owner)
        self.assertEqual(len(actual['calls']), 2)
        self.assertEqual(len(set(actual['issued_call_ids'])), 2)
        self.assertIs(actual['reasoning_baseline']['full_continuity_qualified'], False)
        self.assertEqual(actual['calls'][0]['body']['instructions'], P.SYSTEM)

    def test_different_tool_result_truncated_instructions_extra_dispatch_wrong_scope_or_usage_fail(self):
        for mutation in ('result', 'instructions', 'extra', 'scope', 'usage', 'body_after', 'provider_extra'):
            with self.subTest(mutation=mutation):
                values, owner = synthetic_pair()
                p0, p1, c0, c1 = values
                if mutation == 'result':
                    c1['requests'][1]['body']['input'][-1]['output'] = 'invented result'
                elif mutation == 'instructions':
                    c1['requests'][0]['body']['instructions'] = 'truncated'
                elif mutation == 'extra':
                    p1['requests'].append(copy.deepcopy(p1['requests'][-1]))
                elif mutation == 'scope':
                    c1['requests'][1]['verified_cost_scope']['root_answer_id'] = str(uuid4())
                elif mutation == 'usage':
                    p1['requests'][1]['usage']['output_tokens'] = 16
                elif mutation == 'body_after':
                    c1['requests'][0]['body_after_auth']['metadata'] = {'rewritten': True}
                else:
                    p1['requests'][0]['body']['unknown_provider_field'] = 'not silently dropped'
                with self.assertRaises(P.ProofError):
                    P.verify_two_calls(*values, **owner)

    def test_caller_model_context_is_not_used_as_identity_and_nonce_cannot_be_reused(self):
        values, owner = synthetic_pair()
        values[3]['requests'][1]['verified_cost_scope']['call_id'] = values[3]['requests'][0]['verified_cost_scope']['call_id']
        with self.assertRaises(P.ProofError):
            P.verify_two_calls(*values, **owner)

    def test_financial_profile_records_reasoning_gap_without_requiring_the_inherited_loss(self):
        values, owner = synthetic_pair()
        reasoning = copy.deepcopy(values[1]['requests'][0]['response']['output'][0])
        for body in (values[3]['requests'][1]['body'], values[3]['requests'][1]['body_after_auth'], values[1]['requests'][1]['body']):
            body['input'].insert(1, copy.deepcopy(reasoning))
        actual = P.verify_two_calls(*values, **owner)
        self.assertFalse(actual['reasoning_baseline']['native_followup_reasoning_item_absent'])
        self.assertFalse(actual['reasoning_baseline']['full_continuity_qualified'])
        self.assertEqual(actual['reasoning_baseline']['normative_history_missing'], [])

    def test_hidden_statuses_are_owned_actual_ids_and_final_cost_status_remains_visible(self):
        actor, chat, answer = (str(uuid4()) for _ in range(3))
        history = [{'action': P.PROBE_ACTION, 'hidden': True, 'done': True, 'description': json.dumps({
            'schema': 1, 'actor_id': actor, 'chat_id': chat, 'answer_id': answer, 'response_id': 'resp_encrypted_' + str(i)})} for i in range(2)]
        history += [{'action': 'employee_budget_cost', 'description': 'Visible actual cost', 'done': True}]
        self.assertEqual(P.advertised_ids({'statusHistory': history}, actor, chat, answer), ['resp_encrypted_0', 'resp_encrypted_1'])
        for bad in (history[:-1], [history[0], history[0], history[-1]]):
            with self.assertRaises(P.ProofError):
                P.advertised_ids({'statusHistory': bad}, actor, chat, answer)
        foreign = copy.deepcopy(history)
        data = json.loads(foreign[0]['description']); data['actor_id'] = str(uuid4()); foreign[0]['description'] = json.dumps(data)
        with self.assertRaises(P.ProofError):
            P.advertised_ids({'statusHistory': foreign}, actor, chat, answer)


@unittest.skipUnless(all((NATIVE / v).is_file() for v in ('routers/openai.py', 'utils/payload.py', 'utils/misc.py')), 'Exact native cache unavailable; set GOAL584_NATIVE_SOURCE_ROOT')
class NativeRehearsalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        env = {**os.environ, 'GIT_NO_LAZY_FETCH': '1'}
        repository = NATIVE.parents[1]
        try:
            revision = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], env=env, stderr=subprocess.DEVNULL).decode().strip()
            if revision != OWUI_PIN:
                raise AssertionError('Native source cache is not the exact approved OWUI revision')
            for relative in ('routers/openai.py', 'utils/payload.py', 'utils/misc.py', 'utils/filter.py', 'utils/middleware.py', 'socket/main.py'):
                canonical = subprocess.check_output(['git', '-C', str(repository), 'show', OWUI_PIN + ':backend/open_webui/' + relative], env=env, stderr=subprocess.DEVNULL)
                actual = (NATIVE / relative).read_bytes()
                if canonical.replace(b'\r\n', b'\n') != actual.replace(b'\r\n', b'\n'):
                    raise AssertionError('Tested native owner differs from its exact Git blob: ' + relative)
        except (OSError, subprocess.CalledProcessError):
            raise unittest.SkipTest('Exact native Git cache identity unavailable; no lazy fetch')

    def test_final_workspace_params_actual_native_converter_provider_profile_and_plain_reasoning_baseline(self):
        env = native_functions()
        actor = str(uuid4())
        model = P.workspace_model(original_model(), actor, 'employee_budget_cost', 'employee_budget_cost_details', 'goal584_budget_echo')
        params = copy.deepcopy(model['params']); system = params.pop('system')
        tool = {'type': 'function', 'function': {'name': 'goal584_budget_echo_budget_echo', 'description': 'Native Tool source',
                'parameters': {'type': 'object', 'properties': {}, 'required': []}}}
        prepared = env['apply_model_params_to_body_openai'](params,
            {'model': P.MODEL, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': 'Hi'}], 'tools': [tool], 'stream': True})
        wire1 = env['convert_to_responses_payload'](copy.deepcopy(prepared))
        provider = load_owner('mock_provider')
        provider.responses_input({**wire1, 'model': P.WIRE})
        self.assertEqual(wire1['instructions'], P.SYSTEM)
        self.assertEqual(wire1['max_output_tokens'], 16)
        self.assertEqual(wire1['reasoning'], P.REASONING)
        self.assertFalse(wire1['store'])
        output = [{'type': 'reasoning', 'id': 'rs_probe', 'status': 'completed',
                   'summary': [{'type': 'summary_text', 'text': 'synthetic summary'}], 'encrypted_content': 'synthetic-opaque'},
            {'type': 'function_call', 'id': 'fc_probe', 'status': 'completed', 'call_id': 'call_probe',
             'name': wire1['tools'][0]['name'], 'arguments': '{}'},
            {'type': 'function_call_output', 'call_id': 'call_probe', 'output': [{'type': 'input_text', 'text': 'proof-tool-result'}]}]
        native_tool_messages = env['convert_output_to_messages'](copy.deepcopy(output), raw=True, reasoning_format=None, flatten_tool_images=True)
        second = {**copy.deepcopy(prepared), 'messages': copy.deepcopy(prepared['messages']) + native_tool_messages}
        wire2 = env['convert_to_responses_payload'](second)
        provider.responses_input({**wire2, 'model': P.WIRE})
        self.assertEqual(wire2['input'][-1], {'type': 'function_call_output', 'call_id': 'call_probe', 'output': 'proof-tool-result'})
        self.assertNotIn('synthetic-opaque', json.dumps(wire2))
        self.assertNotIn('synthetic summary', json.dumps(wire2))
        self.assertEqual(wire2['instructions'], wire1['instructions'])
        self.assertEqual(wire2['tools'], wire1['tools'])

    def test_native_pre_routing_audit_call_type_and_exact_single_r_deployment_model(self):
        from enum import Enum
        from types import MappingProxyType
        from typing import cast
        env = {**os.environ, 'GIT_NO_LAZY_FETCH': '1'}
        paths = ('litellm/types/utils.py', 'litellm/litellm_core_utils/api_route_to_call_types.py',
                 'litellm/proxy/utils.py', 'litellm/litellm_core_utils/core_helpers.py', 'litellm/constants.py')
        try:
            trees = {p: ast.parse(subprocess.check_output(['git', '-c', 'gc.auto=0', '-C', str(LLM),
                'show', LLM_PIN + ':' + p], env=env, stderr=subprocess.DEVNULL)) for p in paths}
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('Exact known-path native audit owners unavailable; no fetch')
        namespace = {'Enum': Enum, 'MappingProxyType': MappingProxyType, 'Mapping': collections.abc.Mapping,
                     'cast': cast, '_EMPTY_LIFT': MappingProxyType({}),
                     'litellm': SimpleNamespace(get_llm_provider=lambda **kw: (kw['model'], 'openai', None, None))}
        selected = []
        for path, tree in trees.items():
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == 'CallTypes': selected.append(node)
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == 'API_ROUTE_TO_CALL_TYPES': selected.append(node)
        def function(path, name):
            return next(n for n in trees[path].body if isinstance(n, ast.FunctionDef) and n.name == name)
        selected += [function(paths[1], n) for n in ('_segment_matches', '_pattern_tail_spans_segments', '_route_matches_pattern', 'get_call_types_for_route')]
        selected += [function(paths[2], n) for n in ('_call_type_for_route', '_stamp_deployment_attribution', '_deployment_attribution_for_model_group')]
        selected += [function(paths[3], 'reconstruct_model_name')]
        constant = next(n for n in trees[paths[4]].body if isinstance(n, (ast.Assign, ast.AnnAssign)) and
            (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == 'PROXY_REJECTED_BEFORE_ROUTING_KEY'
             or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PROXY_REJECTED_BEFORE_ROUTING_KEY' for t in n.targets)))
        selected.append(constant)
        selected = ast.parse('from __future__ import annotations').body + selected
        exec(compile(ast.Module(body=selected, type_ignores=[]), '<actual-native-audit-owners>', 'exec'), namespace)
        self.assertEqual(namespace['_call_type_for_route']('/v1/responses'), 'aresponses')
        deployment = {'litellm_params': {'model': 'openai/' + P.WIRE}, 'model_info': {'id': P.DEPLOYMENT}}
        proxy = ModuleType('audit_external_router'); proxy.llm_router = SimpleNamespace(get_model_list=lambda **kw: [deployment])
        with patch.dict('sys.modules', {'litellm': ModuleType('audit_external_litellm'),
                'litellm.proxy': ModuleType('audit_external_proxy'), 'litellm.proxy.proxy_server': proxy}):
            params = {'metadata': {}}
            namespace['_stamp_deployment_attribution'](params, P.MODEL, None, dispatched=False)
        self.assertEqual(params['metadata']['model_group'], P.MODEL)
        self.assertEqual(params['metadata']['model_info']['id'], P.DEPLOYMENT)
        self.assertEqual(namespace['reconstruct_model_name'](P.MODEL, params['custom_llm_provider'], params['metadata']), 'openai/' + P.WIRE)

    def test_native_responses_projection_excludes_persisted_hidden_status_from_model_context(self):
        env = native_functions()
        hidden = {'action': P.PROBE_ACTION, 'hidden': True, 'description': 'resp_actual_encrypted_fixture'}
        body = env['convert_to_responses_payload']({'model': P.MODEL, 'messages': [
            {'role': 'user', 'content': 'Hi'}, {'role': 'assistant', 'content': 'Proof', 'statusHistory': [hidden]}]})
        self.assertNotIn(P.PROBE_ACTION, json.dumps(body))
        self.assertNotIn('resp_actual_encrypted_fixture', json.dumps(body))
        self.assertEqual(body['input'][-1]['content'], [{'type': 'output_text', 'text': 'Proof'}])

    def test_exact_stream_emitter_status_persistence_and_ui_hiding_order_source_seams(self):
        middleware = (NATIVE / 'utils/middleware.py').read_text(encoding='utf-8')
        self.assertIn("'__event_emitter__': event_emitter", middleware)
        self.assertIn("filter_extra_params = {'__body__': form_data, **extra_params}", middleware)
        stream = middleware.index("filter_type='stream'", middleware.index('async def stream_body_handler'))
        parse = middleware.index('handle_responses_streaming_event(data, output)', stream)
        self.assertLess(stream, parse)
        socket = (NATIVE / 'socket/main.py').read_text(encoding='utf-8')
        self.assertIn("if event_type == 'status':", socket)
        self.assertIn('await Chats.add_message_status_to_chat_by_id_and_message_id(', socket)
        ui = NATIVE.parents[1] / 'src/lib/components/chat/Messages/ResponseMessage'
        self.assertIn('status?.hidden !== true', (ui / 'StatusHistory.svelte').read_text(encoding='utf-8'))
        self.assertIn('!status?.hidden', (ui / 'StatusHistory/StatusItem.svelte').read_text(encoding='utf-8'))

    def test_native_minimum_output_owner_is_16_without_equating_it_to_billed_usage(self):
        env = {**os.environ, 'GIT_NO_LAZY_FETCH': '1'}
        try:
            raw = subprocess.check_output(['git', '-C', str(LLM), 'show', LLM_PIN + ':litellm/llms/openai/responses/transformation.py'], env=env, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('Exact known-path LiteLLM cache unavailable; no lazy fetch')
        tree = ast.parse(raw)
        constant = next(n for n in tree.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == 'OPENAI_RESPONSES_API_MIN_MAX_OUTPUT_TOKENS')
        function = next(n for cls in tree.body if isinstance(cls, ast.ClassDef) for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_enforce_min_max_output_tokens')
        function.decorator_list = []
        function.returns = None
        for arg in function.args.args:
            arg.annotation = None
        namespace = {'OPENAI_RESPONSES_API_MIN_MAX_OUTPUT_TOKENS': ast.literal_eval(constant.value)}
        exec(compile(ast.Module(body=[function], type_ignores=[]), 'native-responses-minimum', 'exec'), namespace)
        self.assertEqual(namespace['_enforce_min_max_output_tokens'](5), 16)
        self.assertEqual(namespace['_enforce_min_max_output_tokens'](16), 16)
        values, owner = synthetic_pair()
        result = P.verify_two_calls(*values, **owner)
        self.assertEqual(result['calls'][0]['usage']['output_tokens'], 5)

    def test_native_sdk_decoder_same_row_scope_rates_and_actual_call_nonce_cannot_be_swapped(self):
        env = {**os.environ, 'GIT_NO_LAZY_FETCH': '1'}
        try:
            raw = subprocess.check_output(['git', '-C', str(LLM), 'show', LLM_PIN + ':litellm/responses/utils.py'], env=env, stderr=subprocess.DEVNULL)
            types_raw = subprocess.check_output(['git', '-C', str(LLM), 'show', LLM_PIN + ':litellm/types/responses/main.py'], env=env, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('Exact native SDK decoder source unavailable; no fetch')
        node = next(n for cls in ast.parse(raw).body if isinstance(cls, ast.ClassDef) and cls.name == 'ResponsesAPIRequestUtils'
                    for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_decode_responses_api_response_id')
        node.decorator_list, node.returns = [], None
        for arg in node.args.args:
            arg.annotation = None
        # Preserve the native return owner itself: TypedDict constructs dicts.
        namespace = {'base64': base64, 'TypedDict': TypedDict, 'verbose_logger': SimpleNamespace(debug=lambda *args: None)}
        decoded_type = next(n for n in ast.parse(types_raw).body if isinstance(n, ast.ClassDef) and n.name == 'DecodedResponseId')
        exec(compile(ast.Module(body=[decoded_type], type_ignores=[]), 'native-sdk-decoded-type', 'exec'), namespace)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'native-sdk-responses-id', 'exec'), namespace)
        protocol_spec = importlib.util.spec_from_file_location('responses_row_protocol', REPO / 'deploy/openwebui-budgets/provenance.py')
        protocol = importlib.util.module_from_spec(protocol_spec); protocol_spec.loader.exec_module(protocol)
        pricing = load_owner('prove_pricing_snapshots')
        callback_tree = ast.parse((REPO / 'deploy/openwebui-budgets/pricing_snapshot.py').read_bytes())
        fields = ast.literal_eval(next(n.value for n in callback_tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'RATE_FIELDS' for t in n.targets)))
        representation = ModuleType('pricing_snapshot'); representation.RATE_FIELDS = fields
        values, owner = synthetic_pair()
        evidence = P.verify_two_calls(*values, **owner)
        expected = {v['provider_response_id']: v['scope'] for v in evidence['calls']}
        provider_id = evidence['calls'][0]['provider_response_id']
        identifier = 'resp_' + base64.b64encode(('litellm:custom_llm_provider:openai;model_id:' + P.DEPLOYMENT + ';response_id:' + provider_id).encode()).decode()
        rates = {k: None for k in fields}; rates.update(input_cost_per_token=.01, output_cost_per_token=.02)
        snapshot = {'schema': 1, 'availability': 'partial', 'observed_at_utc': '2026-11-03T00:00:00Z', 'rates': rates}
        row = {'request_id': identifier, 'user': owner['actor'], 'api_key': owner['key_hash'], 'model': 'openai/' + P.WIRE,
            'model_group': P.MODEL, 'model_id': P.DEPLOYMENT, 'status': 'success', 'session_id': owner['chat_id'],
            'spend': .20, 'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15,
            'metadata': {'litellm_call_id': str(uuid4()), 'spend_logs_metadata': {
                'owui_budget': expected[provider_id], 'owui_billed_token_rates': snapshot}}}
        kwargs = {**owner, 'scope_by_provider': expected, 'validate_scope': protocol.validate_persisted_scope,
                  'validate_rates': pricing.validate_snapshot, 'decode': namespace['_decode_responses_api_response_id']}
        with patch.dict('sys.modules', {'pricing_snapshot': representation}):
            decoded = kwargs['decode'](identifier)
            self.assertIs(type(decoded), dict)
            self.assertEqual(set(decoded), {'custom_llm_provider', 'model_id', 'response_id'})
            result = P.row_evidence(row, **kwargs)
            self.assertEqual(result['native_request_id'], identifier)
            self.assertEqual(result['provider_response_id'], provider_id)
            self.assertNotEqual(identifier, provider_id)
            for mutation in ('nonce', 'rate', 'key', 'session', 'usage', 'model'):
                changed = copy.deepcopy(row)
                if mutation == 'nonce':
                    changed['metadata']['spend_logs_metadata']['owui_budget'] = evidence['calls'][1]['scope']
                elif mutation == 'rate':
                    changed['metadata']['spend_logs_metadata']['owui_billed_token_rates']['rates']['output_cost_per_token'] = .03
                elif mutation == 'key':
                    changed['api_key'] = 'b' * 64
                elif mutation == 'session':
                    changed['session_id'] = str(uuid4())
                elif mutation == 'usage':
                    changed['completion_tokens'] = 16
                else:
                    changed['model_group'] = 'goal584-a'
                with self.subTest(mutation=mutation), self.assertRaises(P.ProofError):
                    P.row_evidence(changed, **kwargs)
            for malformed in (object(), {'response_id': provider_id}, {**decoded, 'unexpected': 'field'},
                              {**decoded, 'model_id': None}):
                with self.subTest(malformed_type=type(malformed).__name__), self.assertRaises(P.ProofError):
                    P.row_evidence(row, **{**kwargs, 'decode': lambda value: malformed})


class MissingGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_missing_capsule_owner_and_real_capture_match_precise_guard_not_invalid_signature(self):
        from fastapi import HTTPException, Request
        auth_spec = importlib.util.spec_from_file_location('responses_missing_product_guard', REPO / 'deploy/openwebui-budgets/litellm_auth.py')
        auth = importlib.util.module_from_spec(auth_spec); auth_spec.loader.exec_module(auth)
        capture = load_owner('capture_webui_auth')
        request = Request({'type': 'http', 'method': 'POST', 'path': '/responses', 'headers': []})
        request.data, request.route = P.unsigned_raw_body(), '/responses'
        actor = str(uuid4())
        decoder_calls = []
        def decoder(*args, **kwargs):
            decoder_calls.append(True)
            self.fail('Missing-token guard must reject before decoder')
        async def actual_guard(actual, api_key):
            auth._apply_provenance(actual, actual.data, shared_gateway=True, required=True,
                secret='synthetic-local-gateway-only', user_id=actor, model=P.MODEL, decoder=decoder,
                chain_id=None, metadata_slot='litellm_metadata', metadata_session_id=None, task='')
        async def read_body(actual):
            return actual.data
        def module(**values):
            result = ModuleType('missing_guard_external_boundary'); result.__dict__.update(values); return result
        modules = {name: module() for name in ('litellm', 'litellm.proxy', 'litellm.proxy.auth', 'litellm.proxy.common_utils', 'litellm.proxy.spend_tracking')}
        modules['litellm.proxy'].proxy_server = SimpleNamespace(llm_router=object())
        modules.update({'litellm.proxy.auth.auth_utils': module(get_request_route=lambda value: value.route),
            'litellm.proxy.common_utils.http_parsing_utils': module(_read_request_body=read_body),
            'litellm.proxy.spend_tracking.budget_reservation': module(estimate_request_max_cost=lambda *args: .42)})
        with tempfile.TemporaryDirectory() as directory, patch.object(capture, 'CAPTURE', Path(directory) / 'capture.private.json'), patch.dict(
                'sys.modules', modules), patch.object(capture, 'product_auth', return_value=actual_guard):
            with self.assertRaises(HTTPException) as caught:
                await capture.gateway_auth(request, 'synthetic-local-gateway-only')
            self.assertEqual((caught.exception.status_code, caught.exception.detail), (403, 'Signed budget provenance required'))
            self.assertEqual(decoder_calls, [])
            with capture.capture_lock():
                records = capture._read_locked()['requests']
            self.assertEqual(len(records), 1)
            row = records[0]
            self.assertEqual(row['auth_failure'], {'scope': 'custom_auth', 'status_code': 403, 'code': 'unclassified'})
            payloads = [{'detail': caught.exception.detail}, {'error': {'message': caught.exception.detail, 'type': 'auth_error', 'code': '403'}}]
            for payload in payloads:
                result = P.missing_provenance_denied(caught.exception.status_code, payload, row)
                self.assertEqual(result['native_guard'], 'signed_budget_provenance_required')
                self.assertEqual(result['capture_failure_code'], 'unclassified')
            for status, payload, evidence in ((401, payloads[0], row), (403, {'detail': 'Access denied'}, row),
                    (403, {'error': {'message': 'Invalid signed budget provenance'}}, row),
                    (403, payloads[0], {**row, 'attestation_present_before': True}),
                    (403, payloads[0], {**row, 'route': '/foreign'})):
                with self.assertRaises(P.ProofError):
                    P.missing_provenance_denied(status, payload, evidence)


class ProbeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        try:
            import pydantic
        except ImportError:
            self.skipTest('Existing Pydantic unavailable; no install')
        namespace = {}
        exec(compile(P.PROBE_SOURCE, '<fixed-inline-native-filter>', 'exec'), namespace)
        self.filter = namespace['Filter']()
        self.actor, self.chat, self.answer = (str(uuid4()) for _ in range(3))
        self.filter.valves.actor_id = self.actor
        self.metadata = {'user_id': self.actor, 'chat_id': self.chat, 'message_id': self.answer}
        self.events = []
        async def user(uid):
            self.assertEqual(uid, self.actor)
            return SimpleNamespace(id=uid, role='user')
        async def chat(cid, actual, permission):
            self.assertEqual((cid, actual.id, permission), (self.chat, self.actor, 'write'))
            return SimpleNamespace(user_id=self.actor)
        async def message(cid, aid):
            self.assertEqual((cid, aid), (self.chat, self.answer))
            return {'role': 'assistant', 'model': P.MODEL}
        async def binding(body, model, request, url, **kwargs):
            self.assertEqual(body, {'model': P.MODEL}); self.assertEqual(url, 'http://proxy:4000')
            return 'gw-' + 'x' * 32, P.MODEL
        def module(**values):
            item = ModuleType('probe_external_boundary'); item.__dict__.update(values); return item
        self.boundaries = patch.dict('sys.modules', {'open_webui': module(), 'open_webui.models': module(),
            'open_webui.models.users': module(Users=SimpleNamespace(get_user_by_id=user)),
            'open_webui.models.chats': module(Chats=SimpleNamespace(get_accessible_chat_by_id=chat, get_message_by_id_and_message_id=message)),
            'employee_budget_webui_model_binding': module(native_connection=binding)})
        self.boundaries.start(); self.addCleanup(self.boundaries.stop)

    async def emit(self, value):
        self.events.append(copy.deepcopy(value))

    async def run_probe(self, identifier, **changes):
        event = {'type': 'response.created', 'response': {'id': identifier, 'usage': None, 'status': 'in_progress'}}
        expected = copy.deepcopy(event)
        params = {'__user__': {'id': self.actor}, '__metadata__': self.metadata, '__model__': {'id': P.MODEL},
                  '__request__': object(), '__event_emitter__': self.emit, **changes}
        returned = await self.filter.stream(event, **params)
        self.assertIs(returned, event); self.assertEqual(event, expected)
        return returned

    async def test_fixed_probe_emits_first_unique_actual_ids_as_hidden_native_status_only(self):
        await self.run_probe('resp_encrypted_actual_1')
        await self.run_probe('resp_encrypted_actual_1')
        await self.run_probe('resp_encrypted_actual_2')
        self.assertEqual(len(self.events), 2)
        for event in self.events:
            self.assertEqual(event['type'], 'status')
            self.assertEqual(event['data']['action'], P.PROBE_ACTION)
            self.assertIs(event['data']['hidden'], True)
            value = json.loads(event['data']['description'])
            self.assertEqual((value['actor_id'], value['chat_id'], value['answer_id']), (self.actor, self.chat, self.answer))
        self.assertNotIn('gw-' + 'x' * 32, json.dumps(self.events))

    async def test_probe_rejects_foreign_context_unsafe_ids_and_exhausted_bound(self):
        for changes in ({'__user__': {'id': str(uuid4())}}, {'__model__': {'id': 'goal584-a'}}):
            with self.assertRaises(ValueError):
                await self.run_probe('resp_encrypted_actual', **changes)
        for identifier in ('foreign', 'resp_unsafe space', 'resp_gw-' + 'x' * 32):
            with self.assertRaises(ValueError):
                await self.run_probe(identifier)
        for i in range(8):
            await self.run_probe('resp_encrypted_actual_' + str(i))
        with self.assertRaises(ValueError):
            await self.run_probe('resp_encrypted_actual_9')
        self.assertEqual(len(self.events), 8)


if __name__ == '__main__':
    unittest.main()
