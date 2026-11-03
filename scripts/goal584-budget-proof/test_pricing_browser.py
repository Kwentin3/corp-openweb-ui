"""Offline host coordinator boundaries; no browser, Docker, API or inference."""
import copy
import contextlib
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prove_pricing_browser as p

IDS = [f'{n:08d}-1111-4111-8111-111111111111' for n in range(1, 9)]
ACTOR, PAYER, CHAT, ANSWER = IDS[0], IDS[4], IDS[5], IDS[6]
OLD_ID, NEW_ID = 'chatcmpl-goal584-' + 'a' * 32, 'chatcmpl-goal584-' + 'b' * 32
CALL = {'model': p.MODEL, 'chat_id': CHAT, 'message_id': ANSWER, 'outcome': 'success', 'terminal_persisted': True, 'native_cost_status': True}


def native_row(identifier, cost):
    scope = {'schema': 1, 'user_id': ACTOR, 'model': p.MODEL, 'category': 'personal', 'call_id': IDS[7],
             'chat_id': CHAT, 'root_chat_id': CHAT, 'answer_id': ANSWER, 'root_answer_id': ANSWER}
    return {'request_id': identifier, 'user_id': ACTOR, 'key_hash': 'f' * 64, 'model': p.MODEL,
            'session_id': CHAT, 'status': 'success', 'spend_usd': cost,
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}, 'scope': scope}


def native_pair():
    budgets = []
    for uid in IDS[:5]:
        value = '.2' if uid == ACTOR else '0'
        models = [{'model': model, 'spend': value if model == p.MODEL else '0', 'max_budget': '40',
                   'key_hash': 'f' * 64, 'key_alias': 'fixture-' + model, 'budget_duration': '1mo', 'budget_reset_at': '2026-12-01T00:00:00Z'}
                  for model in ([p.MODEL] if uid == PAYER else [p.MODEL, 'goal584-b'])]
        budgets.append({'user_id': uid, 'spend': value, 'max_budget': '40', 'models': models,
                        'budget_duration': '1mo', 'budget_reset_at': '2026-12-01T00:00:00Z'})
    before = {'budgets': budgets, 'rows': [native_row(OLD_ID, '.20')], 'models': {'modelA': 'unchanged'},
              'unqualified_zero_request_ids': {uid: [] for uid in IDS[:5]}}
    after = copy.deepcopy(before)
    after['rows'].append(native_row(NEW_ID, '0.4'))
    after['budgets'][0]['spend'] = '.6000000000000001'
    after['budgets'][0]['models'][0]['spend'] = '.6000000000000001'
    return before, after


def captures():
    body = {'model': p.MODEL, 'stream': True, 'messages': [{'role': 'user', 'content': 'Hi'}], 'max_tokens': 5}
    scope = native_row(NEW_ID, '0.4')['scope']
    captured = {'body': body, 'body_after_auth': copy.deepcopy(body), 'user_id': ACTOR, 'task': '',
        'attestation_present_before': True, 'provenance_removed_after': True, 'native_auth_user_id': ACTOR,
        'native_stream_usage_patch': {'stream_options': {'include_usage': True}}, 'verified_cost_scope': scope}
    physical = {'id': NEW_ID, 'body': {**body, 'model': 'goal584-fake-a', 'stream_options': {'include_usage': True}},
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
    before = {'synthetic': True, 'control': {'prompt_tokens': 10}, 'requests': [{'id': OLD_ID}]}
    after = copy.deepcopy(before); after['requests'].append(physical)
    old_context = {'schema': 1, 'requests': [{'old': 'actual-prior-record'}]}
    new_context = copy.deepcopy(old_context); new_context['requests'].append(captured)
    return before, after, old_context, new_context


class NativePriceBoundaryTests(unittest.TestCase):
    def test_actual_config_observer_checks_native_yaml_route_callback_and_other_model_prices(self):
        raw = (HERE / 'litellm_config.yaml').read_text(encoding='utf8')
        raw = raw.replace('general_settings:\n', 'general_settings:\n  custom_auth: capture_webui_auth.gateway_auth\n  custom_auth_run_common_checks: true\n  missing_session_id: omit\n')
        raw = raw.replace('["budget_errors.handler"]', '["budget_errors.handler", "pricing_snapshot.handler"]')
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.yaml'
            script = p.CONFIG_OBSERVATION.replace("Path('/proof/config.yaml')", 'Path(' + repr(str(config)) + ')')
            for target, source in [('/proof/pricing_snapshot.py', p.ROOT / 'deploy/openwebui-budgets/pricing_snapshot.py'),
                                   ('/proof/prove_pricing_snapshots.py', HERE / 'prove_pricing_snapshots.py')]:
                script = script.replace('Path(' + repr(target) + ')', 'Path(' + repr(str(source)) + ')')
            def observe(text, rates):
                config.write_text(text, encoding='utf8')
                with patch.object(sys, 'argv', ['native', *rates]), patch.dict(os.environ, STORE_PROMPTS_IN_SPEND_LOGS='false'), contextlib.redirect_stdout(io.StringIO()) as output:
                    exec(compile(script, 'actual_config_observer', 'exec'), {})
                return json.loads(output.getvalue())
            self.assertTrue(observe(raw, ['0.01', '0.02'])['fixture_routes_and_rates_validated'])
            self.assertTrue(observe(p.changed_config(raw.encode()).decode(), ['0.02', '0.04'])['fixture_routes_and_rates_validated'])
            parts = raw.split('  - model_name: goal584-b')
            bad_b = parts[0] + '  - model_name: goal584-b' + parts[1].replace('input_cost_per_token: 0.01', 'input_cost_per_token: 0.02')
            for value in [bad_b, raw.replace('http://provider:8000/v1', 'https://external.invalid/v1', 1),
                          raw.replace(', "pricing_snapshot.handler"', ''), raw.replace('custom_auth_run_common_checks: true', 'custom_auth_run_common_checks: false')]:
                with self.subTest(value=value[-20:]), self.assertRaises(AssertionError): observe(value, ['0.01', '0.02'])

    def test_native_observation_uses_actual_accounting_owner_without_rejecting_counter_ahead_of_pending_witness(self):
        before, after = native_pair()
        state = {'schema': 1, 'stage': 'setup_complete', 'run_id': 'goal584-webui-123456789abc',
                 'users': [{'id': uid, 'token': 'private-session'} for uid in IDS[:2]], 'admin': {'id': IDS[2], 'token': 'private-session'},
                 'bootstrap_fixture': {'employee': {'id': IDS[3]}}, 'service_fixture': {'payer_id': PAYER},
                 'background_fixture': {'stage': 'qualified_automatic_background', 'task_config_restored': True,
                    'provider_controls_restored': True, 'baseline_chat': {'chat_id': CHAT}, 'service_chat': {'chat_id': CHAT}}}
        flags = ('ENABLE_TITLE_GENERATION', 'ENABLE_TAGS_GENERATION', 'ENABLE_FOLLOW_UP_GENERATION')
        class WebUI:
            def session(self, *args): pass
            def ok(self, method, path, token):
                return {flag: False for flag in flags} if path == '/api/v1/tasks/config' else {'task_ids': []}
        native = SimpleNamespace(schema=lambda: None)
        modules = {}
        for name, values in {
            'prove_background_tasks': {'snapshot': lambda *args: snapshot},
            'prove_service_tasks': {'task_config_evidence': lambda value: {'sha256': 'actual-task-readback'}},
            'provision_webui': {'WebUI': WebUI, 'native_client': lambda *args: native, 'read_private': lambda *args: state,
                               'TASK_FLAGS': flags, 'require': p.require}}.items():
            module = ModuleType(name); module.__dict__.update(values); modules[name] = module
        def observe(value, target):
            nonlocal snapshot
            snapshot = value
            with patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['native', target]), contextlib.redirect_stdout(io.StringIO()) as output:
                exec(compile(p.OBSERVE, 'actual_native_observer', 'exec'), {})
            return json.loads(output.getvalue())
        snapshot = before
        self.assertTrue(observe(before, 'baseline')['accounting_ready'])
        ahead = copy.deepcopy(before); ahead['budgets'][0]['spend'] = '.6'; ahead['budgets'][0]['models'][0]['spend'] = '.6'
        self.assertFalse(observe(ahead, NEW_ID)['accounting_ready'])
        lag = copy.deepcopy(after); lag['budgets'][0]['spend'] = '.2'
        self.assertFalse(observe(lag, NEW_ID)['accounting_ready'])
        self.assertTrue(observe(after, NEW_ID)['accounting_ready'])
        with self.assertRaises(AssertionError): observe(ahead, 'baseline')

    def test_changes_only_two_model_a_literals_preserving_bytes_and_file_inode(self):
        original = (HERE / 'litellm_config.yaml').read_bytes()
        changed = p.changed_config(original)
        old, new = original.decode().split('  - model_name: goal584-b'), changed.decode().split('  - model_name: goal584-b')
        self.assertEqual(old[1], new[1])
        self.assertEqual(new[0], old[0].replace('      input_cost_per_token: 0.01', '      input_cost_per_token: 0.02')
                         .replace('      output_cost_per_token: 0.02', '      output_cost_per_token: 0.04'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.yaml'; path.write_bytes(original); path.chmod(0o600)
            identity = path.stat().st_ino
            p.overwrite_config(path, changed)
            self.assertEqual(path.stat().st_ino, identity)
            p.overwrite_config(path, original)
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(p.changed_config(original.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')).count(b'\r\n'), original.count(b'\n'))

    def test_unknown_or_duplicate_or_already_changed_rate_layout_fails_before_write(self):
        raw = (HERE / 'litellm_config.yaml').read_bytes()
        for mutate in [lambda b: b.replace(b'input_cost_per_token: 0.01', b'input_cost_per_token: 0', 1),
                       lambda b: b.replace(b'goal584-a', b'unapproved', 1),
                       lambda b: b.replace(b'      input_cost_per_token: 0.01', b'      input_cost_per_token: 0.01\n      input_cost_per_token: 0.01', 1),
                       p.changed_config]:
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError): p.changed_config(mutate(raw))

    def test_actual_scope_and_one_explicit_native_cost_required_and_lag_can_wait(self):
        before, after = native_pair()
        expected_scope = native_row(NEW_ID, '0.4')['scope']
        self.assertTrue(p.finance_ready(before, after, CALL, ACTOR, NEW_ID, expected_scope))
        self.assertFalse(p.finance_ready(before, before, CALL, ACTOR, NEW_ID, expected_scope))
        lag = copy.deepcopy(after); lag['budgets'][0]['spend'] = '.2'
        self.assertFalse(p.finance_ready(before, lag, CALL, ACTOR, NEW_ID, expected_scope))
        for mutate in [lambda v: v['rows'][0].update(spend_usd='.4'),
                       lambda v: v['rows'].pop(0), lambda v: v['rows'].append(copy.deepcopy(v['rows'][-1])),
                       lambda v: v['rows'][-1].update(request_id=OLD_ID),
                       lambda v: v['rows'][-1]['scope'].update(category='service'),
                       lambda v: v['rows'][-1]['scope'].update(call_id=IDS[6]),
                       lambda v: v['rows'][-1]['scope'].update(root_answer_id=IDS[7]),
                       lambda v: v['budgets'][0].update(spend='1'),
                       lambda v: v['budgets'][4].update(spend='.4'),
                       lambda v: v['budgets'][0]['models'][0].update(max_budget='100'),
                       lambda v: v['unqualified_zero_request_ids'][PAYER].append('extra')]:
            value = copy.deepcopy(after); mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError): p.finance_ready(before, value, CALL, ACTOR, NEW_ID, expected_scope)

    def test_full_provider_causality_rejects_extra_fields_history_loss_and_foreign_scope(self):
        self.assertEqual(p.causal_request(*captures(), CALL, ACTOR), NEW_ID)
        for mutate in [lambda v: v[1]['requests'].append(copy.deepcopy(v[1]['requests'][-1])),
                       lambda v: v[1]['requests'].pop(0),
                       lambda v: v[1]['requests'][-1]['body'].update(unknown='hidden-transform'),
                       lambda v: v[1]['requests'][-1]['body']['messages'][0].update(content='changed'),
                       lambda v: v[3]['requests'][-1].update(native_auth_user_id=PAYER),
                       lambda v: v[3]['requests'][-1]['verified_cost_scope'].update(category='service'),
                       lambda v: v[1]['control'].update(prompt_tokens=20)]:
            values = copy.deepcopy(captures()); mutate(values)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError): p.causal_request(*values, CALL, ACTOR)

    def test_known_native_internal_usage_marker_is_exact_true_and_only_that_marker_is_not_on_wire(self):
        values = captures()
        values[3]['requests'][-1]['native_stream_usage_patch']['_litellm_strip_stream_usage'] = True
        self.assertEqual(p.causal_request(*values, CALL, ACTOR), NEW_ID)
        def unknown_both(v):
            for body in (v[3]['requests'][-1]['body'], v[3]['requests'][-1]['body_after_auth'], v[1]['requests'][-1]['body']):
                body['unknown_semantic'] = 'must-not-be-dropped'
        for mutate in [*[lambda v, flag=flag: v[3]['requests'][-1]['native_stream_usage_patch'].update(_litellm_strip_stream_usage=flag)
                         for flag in (False, 1, 'true', None)],
                       lambda v: v[3]['requests'][-1]['native_stream_usage_patch'].update(unknown_native_flag=True),
                       lambda v: v[3]['requests'][-1]['native_stream_usage_patch'].update(stream_options={'include_usage': False}),
                       lambda v: v[1]['requests'][-1]['body'].update(_litellm_strip_stream_usage=True),
                       lambda v: v[1]['requests'][-1]['body'].update(temperature=.7), unknown_both]:
            actual = copy.deepcopy(values); mutate(actual)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError): p.causal_request(*actual, CALL, ACTOR)

    def test_actual_run34_ordinary_hi_capture_and_whole_provider_body_replay(self):
        root = p.ROOT / 'local/goal584/runtime-proof-41630590813/receipts/bootstrap'
        if not (root / 'webui-gateway-context.json').exists() or not (root / 'webui-provider-calls.json').exists():
            self.skipTest('Optional local run34 artifact unavailable; synthetic native boundary tests still run')
        context = json.loads((root / 'webui-gateway-context.json').read_text(encoding='utf8'))
        physical = json.loads((root / 'webui-provider-calls.json').read_text(encoding='utf8'))
        captured = context['requests'][-1]
        self.assertEqual(captured['body']['messages'], [{'role': 'user', 'content': 'Hi'}])
        self.assertEqual(captured['native_stream_usage_patch'],
                         {'stream_options': {'include_usage': True}, '_litellm_strip_stream_usage': True})
        scope = captured['verified_cost_scope']
        call = {'model': p.MODEL, 'chat_id': scope['chat_id'], 'message_id': scope['answer_id']}
        before, prior = copy.deepcopy(physical), copy.deepcopy(context)
        before['requests'].pop(); prior['requests'].pop()
        observed_id = p.causal_request(before, physical, prior, context, call, captured['user_id'])
        self.assertEqual(observed_id, physical['requests'][-1]['id'])
        self.assertNotIn('_litellm_strip_stream_usage', physical['requests'][-1]['body'])


class PrivateAndRollbackTests(unittest.TestCase):
    def private_files(self, directory):
        base = Path(directory); private = base / 'private'; private.mkdir(mode=0o700)
        config = private / 'config.yaml'; config.write_bytes((HERE / 'litellm_config.yaml').read_bytes()); config.chmod(0o600)
        accounts = private / 'staff.json'
        accounts.write_text(json.dumps({'users': [{'id': uid, 'email': 'staff@example.com', 'password': 'private-password'} for uid in IDS[:2]]}), encoding='utf8')
        accounts.chmod(0o600)
        env = base / 'proof.env'; env.write_text('PROOF_PRIVATE_DIR=' + str(private.resolve()) + '\nPROOF_CONFIG_FILE=' + str(config.resolve()) + '\n', encoding='utf8'); env.chmod(0o600)
        return private, config, accounts, env

    def test_private_fixture_root_and_upload_separation(self):
        with tempfile.TemporaryDirectory() as directory:
            private, config, accounts, env = self.private_files(directory)
            self.assertEqual(p.private_fixture(env, accounts, Path(directory) / 'artifacts')[1], config.resolve())
            with self.assertRaises(AssertionError): p.private_fixture(env, accounts, private / 'uploaded')
            outside = Path(directory) / 'outside.json'; outside.write_bytes(accounts.read_bytes())
            with self.assertRaises(AssertionError): p.private_fixture(env, outside, Path(directory) / 'artifacts')

    def run_rehearsal(self, directory, failure=None):
        private, config, _, _ = self.private_files(directory)
        original = config.read_bytes()
        before, after = native_pair(); packet = captures()
        scope = {'run_id': 'goal584-webui-fixture', 'personal_payers': IDS[:4], 'service_payer': PAYER}
        operations = []
        class Fixture:
            count = 0
            def config_observation(self, new=False):
                operations.append(('config', new))
                self.assert_config = config.read_bytes() == (p.changed_config(original) if new else original)
                if not self.assert_config: raise AssertionError('Wrong mounted YAML readback')
                return {'sha256': hashlib.sha256(config.read_bytes()).hexdigest()}
            def observe(self, target='baseline'):
                operations.append(('observe', target))
                return {'actor_id': ACTOR, 'scope': scope, 'task_config': {'sha256': 'same'}, 'schema_ready': True,
                        'accounting_ready': True, 'native': copy.deepcopy(before if target == 'baseline' else after)}
            def pricing(self, mode, witness):
                operations.append(('pricing', mode, witness))
                if failure == 'compare' and mode == 'compare': raise RuntimeError('Private comparison diagnostics')
                return {'fixture_scope': scope, 'witness_request_ids': [witness], 'row_counts': {'new': 1, 'old_immutable': 7},
                        'rows': [{'request_id': witness, 'user_id': ACTOR, 'api_key_hash': 'f' * 64,
                                  'model_group': p.MODEL, 'usage': native_row(witness, '0.4')['usage']}]}
            def captures(self, label):
                operations.append(('capture', label))
                return packet[0 if label == 'before' else 1], packet[2 if label == 'before' else 3]
            def restart(self):
                operations.append(('restart', config.read_bytes() == original)); self.count += 1
                if failure == 'restart' and self.count == 1: raise RuntimeError('Private restart diagnostics')
                if failure == 'restore' and self.count == 2: raise RuntimeError('Restoration failed')
        def browser():
            operations.append(('browser', config.read_bytes() == p.changed_config(original)))
            if failure == 'browser': raise RuntimeError('Private browser diagnostics')
            return copy.deepcopy(CALL)
        fixture, receipt = Fixture(), {}
        if failure:
            with self.assertRaises(RuntimeError): p.rehearse(fixture, config, private, ACTOR, browser, receipt)
        else:
            self.assertEqual(p.rehearse(fixture, config, private, ACTOR, browser, receipt)['native'], after)
        self.assertEqual(config.read_bytes(), original)
        self.assertEqual((private / 'pricing-config-original.private.yaml').read_bytes(), original)
        self.assertNotIn('private-password', json.dumps(receipt))
        return receipt, operations

    def test_success_delegates_both_pricing_modes_then_restores_bytes_restart_and_native_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt, operations = self.run_rehearsal(directory)
        self.assertTrue(receipt['config_bytes_restored'] and receipt['restored_native_readiness'])
        self.assertEqual([v for v in operations if v[0] == 'pricing'], [('pricing', 'record', OLD_ID), ('pricing', 'compare', NEW_ID)])
        self.assertEqual([v for v in operations if v[0] == 'restart'], [('restart', False), ('restart', True)])
        self.assertEqual(operations[-1], ('observe', 'readiness'))

    def test_browser_or_initial_restart_failure_still_restores_exact_native_config(self):
        for failure in ['browser', 'restart', 'compare']:
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                receipt, operations = self.run_rehearsal(directory, failure)
                self.assertTrue(receipt['config_bytes_restored'] and receipt['restored_native_readiness'])
                self.assertEqual([v for v in operations if v[0] == 'restart'], [('restart', False), ('restart', True)])
                self.assertEqual(any(v[:2] == ('pricing', 'compare') for v in operations), failure == 'compare')

    def test_partial_native_yaml_write_failure_still_attempts_exact_restore_and_restart(self):
        original_overwrite = p.overwrite_config
        calls = []
        def partial(path, value):
            calls.append(value)
            if len(calls) == 1:
                path.write_bytes(b'partial native YAML')
                raise RuntimeError('Write failed after partial content')
            original_overwrite(path, value)
        with tempfile.TemporaryDirectory() as directory, patch.object(p, 'overwrite_config', side_effect=partial):
            receipt, operations = self.run_rehearsal(directory, 'partial')
        self.assertEqual(len(calls), 2)
        self.assertTrue(receipt['config_bytes_restored'] and receipt['restored_native_readiness'])
        self.assertEqual([v for v in operations if v[0] == 'restart'], [('restart', True)])

    def test_failed_restore_cannot_be_qualified_even_when_original_file_was_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt, _ = self.run_rehearsal(directory, 'restore')
        self.assertTrue(receipt['config_bytes_restored'])
        self.assertFalse(receipt.get('restored_native_readiness', False))

    def test_snapshot_cli_is_read_only_existing_owner_with_explicit_causal_witness(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            fixture = p.PricingFixture(output / 'env', output, output / 'config', output, [])
            calls = []
            def command(arguments, label):
                calls.append(arguments)
                return {'passed': True, 'mode': 'compare'}
            with patch.object(fixture, 'command_json', side_effect=command): fixture.pricing('compare', NEW_ID)
            self.assertIn('/proof/prove_pricing_snapshots.py', calls[0])
            for flag, expected in [('--prior-receipt', '/proof-private/pricing-record.safe.json'),
                                   ('--witness-request-id', NEW_ID), ('--expected-cost', '0.40')]:
                self.assertEqual(calls[0][calls[0].index(flag) + 1], expected)
            self.assertFalse(any(word in calls[0] for word in ('POST', '/v1/chat/completions', 'reset')))


if __name__ == '__main__':
    unittest.main()
