"""Synthetic projection and preparation checks; no Docker, network or real keys.

Main preparation uses actual files/new-file writes. Only native GET, Docker
identity and POSIX protected-path metadata are boundary fixtures on Windows.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import prepare_google_gateway as owner


def fixture():
    names = ['gpt-6.1-sol', 'gpt-5.6-luna', 'claude-example', None, 'models/gemini-example']
    source = {'ENABLE_OPENAI_API': True,
              'OPENAI_API_BASE_URLS': ['https://responses.invalid/v1', 'https://api.openai.com/v1',
                                      'https://api.anthropic.com/v1', 'https://unclassified.invalid/v1', owner.GOOGLE_URL],
              'OPENAI_API_KEYS': ['provider-response', 'provider-openai', 'provider-anthropic', 'unused-provider', 'provider-google'],
              'OPENAI_API_CONFIGS': {str(i): {'enable': name is not None,
                  'api_type': 'responses' if i == 0 else 'chat_completions',
                  'headers': {'X-Chat': '{{CHAT_ID}}', 'X-Message': '{{MESSAGE_ID}}'}}
                  for i, name in enumerate(names)}}
    models = {'data': [{'id': name, 'urlIdx': i} for i, name in enumerate(names) if name]}
    gateway = {'model_list': [{'model_name': name, 'litellm_params': {'model': 'openai/' + name},
                'model_info': {'mode': 'responses' if i == 0 else 'chat',
                               'input_cost_per_token': 0, 'output_cost_per_token': 0.002}}
                for i, name in enumerate(names) if name],
               'litellm_settings': {'block_requests_for_models_without_pricing': True,
                                   'callbacks': ['budget_errors.handler', 'pricing_snapshot.handler',
                                                 'budget_runtime.responses_handler', 'budget_runtime.cc_stream_handler']},
               'router_settings': {'fallbacks': [], 'num_retries': 0},
               'general_settings': {'master_key': 'os.environ/LITELLM_MASTER_KEY',
                                    'database_url': 'os.environ/DATABASE_URL', 'custom_auth': 'litellm_auth.gateway_auth',
                                    'custom_auth_run_common_checks': True, 'fail_closed_budget_enforcement': True,
                                    'disable_spend_logs': False, 'missing_session_id': 'omit'}}
    return source, models, gateway


class ManagedProjection(unittest.TestCase):
    def test_all_enabled_connections_and_protocols_preserved_without_source_mutation(self):
        source, models, gateway = fixture()
        before = copy.deepcopy((source, models, gateway))
        pending, catalogs = owner.project_managed(source, models, 'sk-inference-example', gateway)
        self.assertEqual((source, models, gateway), before)
        self.assertEqual(set(catalogs), {0, 1, 2, 4})
        for i, config in source['OPENAI_API_CONFIGS'].items():
            projected = pending['OPENAI_API_CONFIGS'][i]
            if config['enable']:
                self.assertEqual(pending['OPENAI_API_BASE_URLS'][int(i)], owner.GATEWAY_URL)
                self.assertEqual(pending['OPENAI_API_KEYS'][int(i)], 'sk-inference-example')
                self.assertEqual(projected['api_type'], config['api_type'])
                self.assertEqual(projected['headers']['X-Chat'], '{{CHAT_ID}}')
                self.assertEqual(projected['headers']['X-Message'], '{{MESSAGE_ID}}')
                self.assertEqual(projected['headers']['X-OpenWebUI-User-Id'], '{{USER_ID}}')
                self.assertEqual(projected['headers']['X-OpenWebUI-Task'], '{{TASK}}')
            else:
                self.assertEqual(pending['OPENAI_API_KEYS'][int(i)], '')
                self.assertEqual(pending['OPENAI_API_BASE_URLS'][int(i)], '')
        self.assertNotIn('provider-', json.dumps(pending))

    def test_native_prefix_preserves_visible_ids_and_projects_wire_catalog(self):
        source, models, gateway = fixture()
        source['OPENAI_API_CONFIGS']['0'].update(prefix_id='team', model_ids=['gpt-6.1-sol'])
        models['data'][0]['id'] = 'team.gpt-6.1-sol'
        pending, catalogs = owner.project_managed(source, models, 'sk-inference-example', gateway)
        self.assertEqual(catalogs[0], ['team.gpt-6.1-sol'])
        self.assertEqual(pending['OPENAI_API_CONFIGS']['0']['prefix_id'], 'team')
        self.assertEqual(pending['OPENAI_API_CONFIGS']['0']['model_ids'], ['gpt-6.1-sol'])

    def test_unreferenced_approved_native_service_models_are_preserved(self):
        source, models, gateway = fixture()
        gateway['model_list'].append({'model_name': 'native-embedding-example',
                                     'litellm_params': {'model': 'openai/text-embedding-example'},
                                     'model_info': {'mode': 'embedding'}})
        before = copy.deepcopy(gateway)
        pending, catalogs = owner.project_managed(source, models, 'sk-inference-example', gateway)
        self.assertEqual(gateway, before)
        self.assertEqual(set(catalogs), {0, 1, 2, 4})
        self.assertNotIn('native-embedding-example', json.dumps(pending))

    def test_unclassified_enabled_connection_cannot_survive(self):
        source, models, gateway = fixture()
        source['OPENAI_API_CONFIGS']['3']['enable'] = True
        with self.assertRaisesRegex(RuntimeError, 'explicit classification'):
            owner.project_managed(source, models, 'sk-inference-example', gateway)
        with self.assertRaisesRegex(RuntimeError, 'Explicit shared inference'):
            owner.project_managed(source, models, 'sk-', gateway)

    def test_disabled_connection_does_not_retain_hidden_provider_credentials(self):
        source, models, gateway = fixture()
        source['OPENAI_API_CONFIGS']['3']['headers'] = {'Authorization': 'provider-disabled-secret'}
        pending, _ = owner.project_managed(source, models, 'sk-inference-example', gateway)
        self.assertEqual(pending['OPENAI_API_CONFIGS']['3'], {'enable': False})
        self.assertNotIn('provider-disabled-secret', json.dumps(pending))
        self.assertEqual(source['OPENAI_API_CONFIGS']['3']['headers']['Authorization'], 'provider-disabled-secret')

    def test_conflicting_auth_headers_aliases_and_prices_fail_closed(self):
        def duplicate_wire(source, models, gateway):
            source['OPENAI_API_CONFIGS']['1']['prefix_id'] = 'other'
            models['data'][1]['id'] = 'other.gpt-6.1-sol'

        changes = {
            'azure': lambda s, m, g: s['OPENAI_API_CONFIGS']['0'].update(azure=True),
            'session': lambda s, m, g: s['OPENAI_API_CONFIGS']['0'].update(auth_type='session'),
            'cookie': lambda s, m, g: s['OPENAI_API_CONFIGS']['0'].update(forward_cookies=True),
            'provider': lambda s, m, g: s['OPENAI_API_CONFIGS']['0'].update(provider='anthropic'),
            'authorization': lambda s, m, g: s['OPENAI_API_CONFIGS']['0']['headers'].update(Authorization='provider-key'),
            'key-header': lambda s, m, g: s['OPENAI_API_CONFIGS']['0']['headers'].update({'X-API_Key': 'provider-key'}),
            'identity': lambda s, m, g: s['OPENAI_API_CONFIGS']['0']['headers'].update({'x-openwebui-user-id': 'other'}),
            'duplicate-model': lambda s, m, g: m['data'].append(dict(m['data'][0])),
            'duplicate-wire': duplicate_wire,
            'duplicate-approved': lambda s, m, g: g['model_list'].append(copy.deepcopy(g['model_list'][0])),
            'missing-price': lambda s, m, g: g['model_list'][0]['model_info'].pop('input_cost_per_token'),
            'unknown-price': lambda s, m, g: g['model_list'][0]['model_info'].update(input_cost_per_token=None),
            'nan-price': lambda s, m, g: g['model_list'][0]['model_info'].update(input_cost_per_token=float('nan')),
            'missing-model': lambda s, m, g: g['model_list'].pop(0),
            'wrong-mode': lambda s, m, g: g['model_list'][0]['model_info'].update(mode='chat'),
            'wildcard': lambda s, m, g: g['model_list'][0].update(model_name='gpt-*'),
            'fallback': lambda s, m, g: g['router_settings'].update(fallbacks=[{'a': ['b']}]),
            'pricing-flag': lambda s, m, g: g['litellm_settings'].update(block_requests_for_models_without_pricing=False),
            'auth-profile': lambda s, m, g: g['general_settings'].pop('custom_auth'),
            'common-checks': lambda s, m, g: g['general_settings'].update(custom_auth_run_common_checks=False),
            'fail-closed': lambda s, m, g: g['general_settings'].update(fail_closed_budget_enforcement=False),
            'spend-logs': lambda s, m, g: g['general_settings'].update(disable_spend_logs=True),
            'database': lambda s, m, g: g['general_settings'].pop('database_url'),
            'missing-session-id': lambda s, m, g: g['general_settings'].update(missing_session_id='create'),
            'callbacks': lambda s, m, g: g['litellm_settings'].update(callbacks=['pricing_snapshot.handler']),
            'legacy-stream-policy': lambda s, m, g: g['litellm_settings'].update(callbacks=[
                'budget_errors.handler', 'pricing_snapshot.handler', 'budget_runtime.handler']),
            'duplicate-stream-policy': lambda s, m, g: g['litellm_settings']['callbacks'].append(
                'budget_runtime.cc_stream_handler'),
            'mixed-stream-policy': lambda s, m, g: g['litellm_settings']['callbacks'].append(
                'budget_runtime.handler'),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                source, models, gateway = fixture()
                change(source, models, gateway)
                with self.assertRaises(RuntimeError):
                    owner.project_managed(source, models, 'sk-inference-example', gateway)

    def test_legacy_default_cc_projection_still_preserves_responses(self):
        source, models, _ = fixture()
        source['OPENAI_API_CONFIGS']['0']['api_type'] = 'responses'
        for index in (1, 2, 4):
            source['OPENAI_API_CONFIGS'][str(index)].pop('api_type')
        models['data'] = [row for row in models['data'] if row['urlIdx'] != 4]
        models['data'].extend({'id': name, 'urlIdx': 4} for name in sorted(owner.REQUIRED_GOOGLE_MODELS))
        pending, catalogs, keys = owner.project(source, models, 'legacy-master-example')
        self.assertEqual(set(catalogs), {1, 2, 4})
        self.assertEqual(pending['OPENAI_API_KEYS'][0], source['OPENAI_API_KEYS'][0])
        self.assertEqual(pending['OPENAI_API_BASE_URLS'][0], source['OPENAI_API_BASE_URLS'][0])
        self.assertEqual(set(keys), {'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'GEMINI_API_KEY'})

    def test_managed_main_copies_exact_approved_config_and_never_applies(self):
        source, models, gateway = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / 'private').mkdir()
            (root / 'webui.env').write_text('', encoding='utf-8')
            (root / 'compose.env').write_text('EXISTING=preserved\n', encoding='utf-8')
            (root / 'admin-native-session.private.json').write_text(
                json.dumps({'role': 'admin', 'token': 'synthetic-session'}), encoding='utf-8')
            config_path, env_path = root / 'private/approved.json', root / 'private/approved.env'
            approved_bytes = (json.dumps(gateway, indent=4) + '\n\n').encode()
            config_path.write_bytes(approved_bytes)
            env_path.write_text('OWUI_BUDGET_GATEWAY_SECRET=sk-inference-example\nLITELLM_MASTER_KEY=sk-master-example\n', encoding='utf-8')
            def native_get(path, token):
                self.assertEqual(token, 'synthetic-session')
                if path == '/openai/config':
                    return copy.deepcopy(source)
                if path == '/api/models':
                    # Legitimate workspace/Pipe rows belong to another owner.
                    return {'data': [*copy.deepcopy(models['data']), {'id': 'workspace-pipe', 'pipe': True}]}
                self.assertEqual(path, '/openai/models')
                return copy.deepcopy(models)
            with patch.object(owner, 'phase_root', return_value=root), \
                 patch.object(owner, 'protected'), \
                 patch.object(owner.os, 'O_NOFOLLOW', 0, create=True), \
                 patch.object(owner.os, 'geteuid', return_value=(root / 'compose.env').stat().st_uid, create=True), \
                 patch.object(owner.stat, 'S_IMODE', return_value=0o600), \
                 patch.object(owner, 'candidate_identity', return_value=('candidate-example', 'image-example')), \
                 patch.object(owner, 'native_get', side_effect=native_get), \
                 patch.object(owner, 'docker_read', side_effect=AssertionError('Unexpected Docker boundary')):
                env_path.write_text('OWUI_BUDGET_GATEWAY_SECRET=sk-same-example\nLITELLM_MASTER_KEY=sk-same-example\n', encoding='utf-8')
                with self.assertRaisesRegex(RuntimeError, 'Separate master'):
                    owner.main(root, managed_config=config_path, managed_env=env_path)
                self.assertFalse((root / 'google-gateway').exists())
                env_path.write_text('OWUI_BUDGET_GATEWAY_SECRET=sk-inference-example\nLITELLM_MASTER_KEY=sk-master-example\nOWUI_BUDGET_OPERATOR_KEY=sk-operator-example\nDATABASE_URL=postgresql://synthetic.invalid/native\n', encoding='utf-8')
                config_path.write_text('model_list:\n  - model_name: example\n', encoding='utf-8')
                with self.assertRaisesRegex(RuntimeError, 'explicitly export native YAML as JSON'):
                    owner.main(root, managed_config=config_path, managed_env=env_path)
                self.assertFalse((root / 'google-gateway').exists())
                config_path.write_bytes(approved_bytes)
                owner.main(root, managed_config=config_path, managed_env=env_path)
                self.assertEqual((root / 'google-gateway/config.yaml').read_bytes(), approved_bytes)
                pending = json.loads((root / 'private/google-openai-pending.private.json').read_text())
                self.assertNotIn('sk-master-example', json.dumps(pending))
                self.assertNotIn('provider-', json.dumps(pending))
                receipt = json.loads((root / 'private/google-gateway-prepared.private.json').read_text())
                self.assertFalse(receipt['native_config_applied'])
                self.assertFalse(receipt['containers_started'])
                with self.assertRaisesRegex(RuntimeError, 'Gateway selectors already exist'):
                    owner.main(root, managed_config=config_path, managed_env=env_path)


if __name__ == '__main__':
    unittest.main()
