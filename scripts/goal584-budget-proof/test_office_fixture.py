"""Actual inherited topology methods with only external Docker IO doubled."""
import ast
import asyncio
import base64
import contextlib
import copy
from datetime import datetime
import io
import json
import hashlib
import os
import mimetypes
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
from typing import Optional
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

import yaml
import pytest
import office_fixture as office
import build_office_profile as builder
from prove_pricing_browser import PricingFixture, ROOT
from prove_native_budgets import ProofError

SERVICES = ('proxy', 'postgres', 'provider', 'redis', 'webui', 'office')
SECRET = 'synthetic-private-config-must-not-be-exported'
BASE = 'http://172.29.0.6:8080'


class OfficeTokenizerCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Retained public bytes, independently checked against the native
        # tiktoken openai_public.py URLs/hashes; never synthesize an encoding.
        cache = ROOT / 'local/goal584/office-request-rehearsal/tokenizer-cache'
        native = ROOT / 'local/goal584/native55-main-review/native-library-venv/Lib/site-packages/tiktoken_ext/openai_public.py'
        rows = (
            ('cl100k_base', '9b5ad71b2ce5302211f9c61530b329a4922fc6a4', '223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7'),
            ('o200k_base', 'fb374d419588a4632f3f557e76b4b70aebbca790', '446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d'))
        if not native.is_file() or not all((cache / key).is_file() for _, key, _ in rows):
            raise unittest.SkipTest('Retained public tokenizer assets/native source unavailable; no network fallback')
        source = native.read_text(encoding='utf8'); tree = ast.parse(source); cls.assets = {}
        for name, key, expected in rows:
            function = ast.get_source_segment(source, next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name))
            url = 'https://openaipublic.blob.core.windows.net/encodings/' + name + '.tiktoken'
            assert url in function and expected in function and hashlib.sha1(url.encode()).hexdigest() == key
            raw = (cache / key).read_bytes(); assert hashlib.sha256(raw).hexdigest() == expected
            cls.assets[url] = {'key': key, 'sha256': expected, 'raw': raw}

    def network_leaf(self, mutation=None):
        calls = []
        class Response(io.BytesIO):
            def read(response, size=-1):
                self.assertEqual(size, 5 * 1024 * 1024 + 1)
                return super().read(size)
        def open_asset(url, *, timeout):
            self.assertEqual(timeout, 30); self.assertIn(url, self.assets); calls.append(url)
            raw = self.assets[url]['raw']
            return Response(mutation(url, raw) if mutation else raw)
        def factory(handler):
            self.assertIsInstance(handler, office.ProxyHandler); self.assertEqual(handler.proxies, {})
            return SimpleNamespace(open=open_asset)
        return factory, calls

    def test_real_public_assets_are_written_with_native_url_cache_keys_and_read_back(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'cache'; factory, calls = self.network_leaf(); stdout = io.StringIO()
            with patch.object(office, 'build_opener', side_effect=factory), contextlib.redirect_stdout(stdout):
                result = office.prepare_native_tokenizers(target)
            self.assertEqual(calls, list(self.assets)); self.assertEqual(stdout.getvalue(), '')
            self.assertEqual(result, {'schema': 1, 'model_calls': 0, 'assets': [
                {'url': url, 'sha256': asset['sha256'], 'bytes': len(asset['raw'])} for url, asset in self.assets.items()]})
            self.assertEqual({p.name for p in target.iterdir()}, {a['key'] for a in self.assets.values()})
            for asset in self.assets.values():
                path = target / asset['key']; self.assertEqual(path.read_bytes(), asset['raw'])
                if os.name != 'nt': self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            if os.name != 'nt': self.assertEqual(target.stat().st_mode & 0o777, 0o700)

    def test_empty_oversize_and_wrong_hash_never_accept_offending_asset_or_retry_partial_cache(self):
        urls = list(self.assets)
        for failed_url, corrupt in ((urls[0], lambda raw: b''),
                (urls[0], lambda raw: b'x' * (5 * 1024 * 1024 + 1)),
                (urls[0], lambda raw: b'bad' + raw[3:]), (urls[1], lambda raw: raw[:-1])):
            with self.subTest(asset=failed_url), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / 'cache'
                factory, calls = self.network_leaf(lambda url, raw: corrupt(raw) if url == failed_url else raw)
                with patch.object(office, 'build_opener', side_effect=factory):
                    with self.assertRaisesRegex(AssertionError, 'native tokenizer asset hash differs'):
                        office.prepare_native_tokenizers(target)
                    self.assertFalse((target / self.assets[failed_url]['key']).exists())
                    accepted = [] if failed_url == urls[0] else [self.assets[urls[0]]['key']]
                    self.assertEqual(sorted(p.name for p in target.iterdir()), accepted)
                    before = {p.name: p.read_bytes() for p in target.iterdir()}; previous = list(calls)
                    with self.assertRaisesRegex(AssertionError, 'cache must be fresh'):
                        office.prepare_native_tokenizers(target)
                    self.assertEqual(calls, previous); self.assertEqual({p.name: p.read_bytes() for p in target.iterdir()}, before)

    def test_existing_and_relative_cache_fail_before_any_public_network_leaf(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory); sentinel = existing / 'prior-native-cache'; sentinel.write_bytes(b'preserve')
            with patch.object(office, 'build_opener', side_effect=AssertionError('Network leaf must not be reached')):
                for target in (existing, Path('relative-native-cache')):
                    with self.subTest(target=target), self.assertRaisesRegex(AssertionError, 'cache must be fresh'):
                        office.prepare_native_tokenizers(target)
            self.assertEqual(sentinel.read_bytes(), b'preserve')


class OfficeConfigTests(unittest.TestCase):
    def original(self):
        return (ROOT / 'scripts/goal584-budget-proof/litellm_config.yaml').read_bytes()

    def test_primary_buffered_capability_is_the_only_office_descriptor_change(self):
        import subprocess
        baseline = subprocess.check_output(['git', 'show',
            'b0193586c5dae6335762583d311f2837116deb9b:scripts/goal584-budget-proof/office_fixture.py'], cwd=ROOT)
        node = next(n for n in ast.parse(baseline).body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'OFFICE_MODELS' for t in n.targets))
        namespace = {'MODEL': office.MODEL}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'before-buffered-Office-descriptors', 'exec'), namespace)
        before = yaml.safe_load('model_list:\n' + namespace['OFFICE_MODELS'])['model_list']
        after = yaml.safe_load('model_list:\n' + office.OFFICE_MODELS)['model_list']
        self.assertIs(after[0]['model_info'].pop('supports_native_streaming'), False)
        self.assertEqual(after, before)

    def test_byte_splice_preserves_ab_unknown_fields_comments_and_crlf(self):
        original = self.original().replace(b'    model_info:', b'    keep_model_option: [one, two]\n    model_info:', 1)
        original = original.replace(b'general_settings:',
            b'# private host comment\ngeneral_settings: # keep this comment\n  keep_native_option: {nested: [false, 17]}')
        original += '# UTF-8 host note: сохранено\nunknown_native_option:\n  value: unchanged\n'.encode()
        for newline in (b'\n', b'\r\n'):
            with self.subTest(newline=newline):
                supplied = original.replace(b'\r\n', b'\n').replace(b'\n', newline)
                frozen = hashlib.sha256(supplied).hexdigest()
                with patch.object(office.subprocess, 'run', side_effect=AssertionError('Unexpected process')), \
                        patch.object(office.subprocess, 'check_output', side_effect=AssertionError('Unexpected process')), \
                        patch('builtins.open', side_effect=AssertionError('Unexpected file IO')):
                    prepared = office.prepare_office_config(supplied)
                self.assertEqual(hashlib.sha256(supplied).hexdigest(), frozen)
                block = office.OFFICE_MODELS.replace('\n', newline.decode()).encode()
                self.assertEqual(prepared.count(block), 1)
                self.assertEqual(prepared.replace(block, b'', 1), supplied)
                before, after = yaml.safe_load(supplied), yaml.safe_load(prepared)
                self.assertEqual(after['model_list'][:2], before['model_list'])
                self.assertEqual({k: v for k, v in after.items() if k != 'model_list'},
                                 {k: v for k, v in before.items() if k != 'model_list'})
                self.assertEqual([v['model_name'] for v in after['model_list']],
                                 ['goal584-a', 'goal584-b', office.MODEL, 'gpt-6-luna'])
                for row in after['model_list'][2:]:
                    self.assertEqual(row['litellm_params']['api_base'], 'http://provider:8000/v1')
                    self.assertEqual(row['model_info']['mode'], 'responses')
                    self.assertTrue(row['model_info']['supports_reasoning'])
                    self.assertTrue(row['model_info']['supports_function_calling'])
                    self.assertEqual(tuple(row['model_info'][key] for key in (
                        'max_input_tokens', 'max_output_tokens', 'max_tokens',
                        'input_cost_per_token', 'output_cost_per_token')), (10000, 1024, 11024, .01, .02))
                    self.assertEqual(row['model_info']['max_tokens'], row['model_info']['max_input_tokens']
                                     + row['model_info']['max_output_tokens'])
                primary, service = after['model_list'][2:]
                self.assertEqual((primary['litellm_params']['model'], primary['model_info']['id']),
                                 ('openai/goal584-fake-office', 'goal584-office-primary'))
                self.assertEqual((service['litellm_params']['model'], service['model_info']['id']),
                                 ('openai/goal584-fake-office-service', 'goal584-office-service'))

    def test_unknown_root_setting_before_general_stays_outside_model_list(self):
        original = self.original().replace(b'general_settings:', b'unknown_before_general:\n  keep: true\n\ngeneral_settings:')
        prepared = office.prepare_office_config(original)
        self.assertEqual(prepared.replace(office.OFFICE_MODELS.encode(), b'', 1), original)
        self.assertEqual(yaml.safe_load(prepared)['unknown_before_general'], {'keep': True})
        self.assertEqual(len(yaml.safe_load(prepared)['model_list']), 4)

    def test_guard_profile_composes_existing_usage_and_office_owners_only(self):
        from prove_pricing_usage import configuration
        original = self.original()
        base = yaml.safe_load(original)
        prepared = yaml.safe_load(office.prepare_usage_guard_config(original))
        prior = yaml.safe_load(office.prepare_office_config(original))
        usage = configuration(base, 'v1')
        buffered = copy.deepcopy(usage['model_list'][2:])
        for model in buffered: model['model_info']['supports_native_streaming'] = False
        self.assertEqual(prepared['model_list'], prior['model_list'] + buffered)
        self.assertEqual(configuration(base, 'v1'), usage)
        self.assertEqual(prepared['litellm_settings'], dict(base['litellm_settings'],
            callbacks=base['litellm_settings']['callbacks'] + ['usage_guard_fixture.handler']))
        self.assertEqual({k: v for k, v in prepared.items() if k not in ('model_list', 'litellm_settings')},
                         {k: v for k, v in base.items() if k not in ('model_list', 'litellm_settings')})
        for deployment in prepared['model_list']:
            self.assertEqual(deployment['litellm_params']['api_base'], 'http://provider:8000/v1')

    def test_guard_profile_cannot_reregister_a_caller_supplied_callback(self):
        original = self.original().replace(b'budget_errors.handler', b'usage_guard_fixture.handler')
        with self.assertRaisesRegex(AssertionError, 'callback registration differs'):
            office.prepare_usage_guard_config(original)

    def test_actual_descriptor_owner_validates_exact_synthetic_terms_and_rejects_yaml_timestamp_coercion(self):
        # Execute the existing owner's exact primitive validator, without its
        # unrelated native-runtime imports or a copied declaration schema.
        source = ROOT / 'deploy/openwebui-budgets/pricing_snapshot.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        constants = {'DESCRIPTOR_FIELDS', '_REFERENCE', '_CREDENTIAL', '_UTC'}
        nodes = [node for node in tree.body if
            isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in constants
                                                for target in node.targets)
            or isinstance(node, ast.FunctionDef) and node.name in ('_utc', '_descriptor')]
        owner = {'re': re, 'datetime': datetime, 'urlsplit': urlsplit, 'unquote': unquote}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), owner)
        prepared = office.prepare_office_config(self.original())
        rows = yaml.safe_load(prepared)['model_list']
        self.assertNotIn('owui_pricing', rows[0]['model_info'])
        self.assertNotIn('owui_pricing', rows[1]['model_info'])
        for row in rows[2:]:
            descriptor = row['model_info']['owui_pricing']
            frozen = copy.deepcopy(descriptor)
            expected = {'schema': 1, 'deployment_id': row['model_info']['id'], 'currency': 'USD',
                'source_ref': 'goal584-office-synthetic-v1',
                'source_url': 'https://pricing.example.invalid/goal584/office',
                'source_checked_at_utc': '2026-11-05T00:00:00Z',
                'declared_effective_from_utc': '2026-11-05T00:00:00Z',
                'declared_effective_until_utc': None, 'activation_ref': 'goal584-office-stand-v1',
                'qualified_usage': 'flat_input_output'}
            self.assertEqual(owner['_descriptor'](descriptor), expected)
            self.assertEqual(descriptor, frozen)
            for mutation in (lambda d: d.update(schema=True),
                    lambda d: d.pop('source_checked_at_utc'),
                    lambda d: d.update(declared_effective_until_utc='2026-11-05T00:00:00Z'),
                    lambda d: d.update(source_url='https://user:secret@pricing.example.invalid/office')):
                invalid = copy.deepcopy(descriptor); mutation(invalid)
                with self.assertRaises(ValueError): owner['_descriptor'](invalid)
        unquoted = prepared.replace(b'"2026-11-05T00:00:00Z"', b'2026-11-05T00:00:00Z')
        for row in yaml.safe_load(unquoted)['model_list'][2:]:
            self.assertIsInstance(row['model_info']['owui_pricing']['source_checked_at_utc'], datetime)
            with self.assertRaises(ValueError): owner['_descriptor'](row['model_info']['owui_pricing'])

    def test_valid_unknown_yaml_merge_and_alias_are_preserved(self):
        original = self.original().replace(b'general_settings:',
            b'host_defaults: &host_defaults\n  keep: original\n\ngeneral_settings:\n  host_options:\n    <<: *host_defaults\n    keep: overridden')
        prepared = office.prepare_office_config(original)
        self.assertEqual(prepared.replace(office.OFFICE_MODELS.encode(), b'', 1), original)
        self.assertEqual(yaml.safe_load(prepared)['general_settings']['host_options'], {'keep': 'overridden'})

    def test_real_provider_foreign_identity_and_duplicate_prior_alias_are_refused(self):
        original = self.original()
        variants = (original.replace(b'goal584-b', b'goal584-a'),
            original.replace(b'goal584-b', b'foreign'),
            original.replace(b'goal584-deployment-a', b'foreign-deployment'),
            original.replace(b'http://provider:8000/v1', b'https://api.openai.com/v1', 1),
            original.replace(b'openai/goal584-fake-a', b'openai/gpt-5.4-mini'),
            original.replace(b'synthetic-provider-only-not-a-credential', b'os.environ/REAL_API_KEY', 1),
            office.prepare_office_config(original))
        for value in variants:
            with self.subTest(value=value[:40]), self.assertRaises(AssertionError):
                office.prepare_office_config(value)

    def test_duplicate_mapping_keys_and_ambiguous_marker_never_hide_prior_values(self):
        original = self.original()
        variants = (original + b'general_settings: {}\n',
            original.replace(b'model_list:', b'model_list: []\nmodel_list:'),
            original.replace(b'  - model_name: goal584-a', b'  - model_name: foreign\n    model_name: goal584-a'),
            original.replace(b'      api_base: http://provider:8000/v1',
                b'      api_base: https://api.openai.com/v1\n      api_base: http://provider:8000/v1', 1),
            original.replace(b'general_settings:', b'"general_settings":'))
        for value in variants:
            with self.subTest(value=value[:40]), self.assertRaises(AssertionError):
                office.prepare_office_config(value)

    def test_empty_nonbytes_size_bad_encoding_malformed_and_extra_documents_reject_safely(self):
        original = self.original()
        variants = (b'', bytearray(original), original.decode(), b' ' * (office.CONFIG_LIMIT + 1),
            b'\xff' + original, original + b'invalid: [\n', original + b'---\nother: true\n',
            original + b'#' + b'x' * (office.CONFIG_LIMIT - len(original) - 2) + b'\n')
        for value in variants:
            with self.subTest(kind=type(value).__name__), self.assertRaises(AssertionError) as caught:
                office.prepare_office_config(value)
            self.assertNotIn('api_key:', str(caught.exception))


def native_inspect(row):
    """Docker's native JSON shape, including omitempty optional fields."""
    host = {'ReadonlyRootfs': row['readonly'], 'Privileged': row['privileged'], 'NetworkMode': row['networkmode']}
    for key, source in (('Init', 'init'), ('Tmpfs', 'tmpfs'), ('CapDrop', 'capdrop'), ('SecurityOpt', 'security')):
        if row[source] is not None: host[key] = row[source]
    state = {'Running': row['running']}
    if row['health'] is not None: state['Health'] = {'Status': row['health']}
    result = {'Id': row['id'], 'Config': {'Labels': row['labels'], 'Env': ['PRIVATE=' + SECRET]},
        'State': state, 'HostConfig': host, 'NetworkSettings': {'Networks': row['networks'], 'Ports': row['ports']},
        'Mounts': row['mounts']}
    if 'terminal_inspect' in row:
        extra = copy.deepcopy(row['terminal_inspect'])
        result['Config'].update(extra.pop('Config'))
        result['HostConfig'].update(extra.pop('HostConfig'))
        result.update(extra)
    return result


class DockerWorld:
    def __init__(self, fixture, six=True):
        self.fixture = fixture; self.calls = []
        names = SERVICES if six else SERVICES[:-1]
        self.ids = {name: format(index + 1, '064x') for index, name in enumerate(names)}
        self.network = 'goal584-native-budget-proof_proof'
        self.config = {'name': 'goal584-native-budget-proof', 'networks': {'proof': {'name': self.network, 'internal': True}},
            'services': {name: {'networks': {'proof': None}, 'ports': []} for name in names}}
        self.config['services']['proxy']['volumes'] = [
            {'type': 'bind', 'source': str(path), 'target': target, 'read_only': target != '/proof-private'}
            for target, path in {'/proof/config.yaml': fixture.config, '/proof-private': fixture.private,
                '/proof/pricing_snapshot.py': ROOT / 'deploy/openwebui-budgets/pricing_snapshot.py',
                '/proof/prove_pricing_snapshots.py': ROOT / 'scripts/goal584-budget-proof/prove_pricing_snapshots.py'}.items()]
        self.config['services']['postgres']['environment'] = {'POSTGRES_PASSWORD': SECRET}
        if six:
            self.config['services']['office'].update(read_only=True, init=True, volumes=[],
                tmpfs=['/tmp:rw,noexec,nosuid,size=128m'], cap_drop=['ALL'], security_opt=['no-new-privileges:true'],
                environment={'OPENWEBUI_BASE_URL': 'http://webui:8080'})
        self.rows = {identifier: {'id': identifier, 'labels': {'com.docker.compose.project': self.config['name'],
            'com.docker.compose.service': name}, 'running': True, 'health': 'healthy',
            'networks': {self.network: {'IPAddress': '172.29.0.' + str(i + 2), 'NetworkID': 'f' * 64}},
            'ports': {'8080/tcp': None}, 'mounts': [], 'readonly': name == 'office', 'init': name == 'office',
            'tmpfs': {'/tmp': 'rw,noexec,nosuid,size=128m'}, 'capdrop': ['ALL'], 'privileged': False,
            'security': ['no-new-privileges:true'], 'networkmode': self.network}
            for i, (name, identifier) in enumerate(self.ids.items())}
        self.selected_ids = list(self.ids.values())
        self.actual_network = [{'Id': 'f' * 64, 'Name': self.network, 'Internal': True,
            'Labels': {'com.docker.compose.project': self.config['name'], 'com.docker.compose.network': 'proof'}}]
        self.environment = ['PATH=/usr/bin', 'OPENWEBUI_BASE_URL=http://webui:8080']

    def run(self, command, **kwargs):
        self.calls.append(command)
        assert kwargs['capture_output'] is True and kwargs['timeout'] in (15, 30)
        if command[:len(self.fixture.command)] == self.fixture.command:
            tail = command[len(self.fixture.command):]
            if tail == ['config', '--format', 'json']: value = self.config
            elif tail == ['ps', '-q', 'webui']: return SimpleNamespace(returncode=0, stdout=self.ids['webui'].encode())
            elif tail == ['ps', '--all', '--quiet']: return SimpleNamespace(returncode=0, stdout='\n'.join(self.selected_ids).encode())
            else: raise AssertionError('Unexpected Compose IO')
        elif command[:3] == ['docker', 'inspect', '--format']:
            if command[3] == '{{json .}}': value = native_inspect(self.rows[command[-1]])
            elif command[3] == '{{json .NetworkSettings.Networks}}': value = self.rows[self.ids['webui']]['networks']
            elif command[3] == '{{json .Config.Env}}':
                assert command[-1] == self.ids['office']; value = self.environment
            else:
                assert '"readonly"' in command[3] and '"networks"' in command[3]; value = self.rows[command[-1]]
        elif command == ['docker', 'network', 'inspect', self.network]: value = self.actual_network
        else: raise AssertionError('Unexpected external IO')
        return SimpleNamespace(returncode=0, stdout=json.dumps(value).encode())


class OfficeTopologyTests(unittest.TestCase):
    def exercise(self, mutate=None, *, cls=office.OfficeFixture, six=True, base=BASE):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); fixture = cls(path / 'proof.env', path / 'output', path / 'config.yaml', path / 'private', [SECRET])
            world = DockerWorld(fixture, six=six)
            if mutate: mutate(world)
            output = io.StringIO()
            with patch.object(office.subprocess, 'run', side_effect=world.run), contextlib.redirect_stdout(output):
                result = fixture.bind(base)
            self.assertEqual(output.getvalue(), '')
            self.assertFalse((path / 'output').exists())
            return fixture, world, result

    def test_literal_wrappers_preserve_old_five_and_add_only_office_overlay(self):
        old, _, result = self.exercise(cls=PricingFixture, six=False)
        self.assertIsNone(result)
        new, world, result = self.exercise()
        self.assertIsNone(result)
        self.assertEqual(new.command[:3] + new.command[4:], old.command[:3] + old.command[4:] + ['-f', 'compose/goal584.office-proof.yml'])
        self.assertEqual(new.command[-2:], ['-f', 'compose/goal584.office-proof.yml'])
        self.assertEqual(len([c for c in world.calls if c[:3] == ['docker', 'inspect', '--format']]), 8)
        with self.assertRaisesRegex(AssertionError, 'isolated native fixture topology'): self.exercise(cls=PricingFixture)
        with self.assertRaisesRegex(AssertionError, 'isolated native fixture topology'): self.exercise(six=False)

    def test_native_json_omits_optional_other_service_fields_without_exporting_env(self):
        def absent(world):
            for name, identifier in world.ids.items():
                if name != 'office': world.rows[identifier].update(init=None, tmpfs=None, health=None)
        fixture, world, _ = self.exercise(absent)
        commands = [c for c in world.calls if c[:3] == ['docker', 'inspect', '--format'] and c[3] == '{{json .}}']
        self.assertEqual(len(commands), 6)
        row = office.topology_row(native_inspect(world.rows[world.ids['postgres']]))
        self.assertIsNone(row['init']); self.assertIsNone(row['tmpfs']); self.assertIsNone(row['health'])
        self.assertNotIn(SECRET, json.dumps(row)); self.assertNotIn('Env', json.dumps(row))
        self.assertFalse(fixture.output.exists())
        with self.assertRaises(AssertionError):
            self.exercise(lambda w: w.rows[w.ids['office']].update(init=None))

    def test_native_projection_keeps_required_fields_and_safe_command_failure_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); fixture = office.OfficeFixture(root/'env', root/'output', root/'config', root/'private', [SECRET])
            world = DockerWorld(fixture)
            raw = native_inspect(world.rows[world.ids['office']]); del raw['HostConfig']['ReadonlyRootfs']
            with patch.object(office.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(raw).encode())):
                with self.assertRaisesRegex(AssertionError, 'native projection differs'):
                    fixture._docker_json(['inspect', '--format', '{{json .}}', world.ids['office']], project=office.topology_row)
            with patch.object(office.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout=b'', stderr=SECRET.encode())):
                with self.assertRaisesRegex(AssertionError, 'inspect; exit=1; stdout_bytes=0') as failed:
                    fixture._docker_json(['inspect', '--format', '{{json .}}', world.ids['office']], project=office.topology_row)
                self.assertNotIn(SECRET, str(failed.exception))

    def test_common_proxy_mounts_still_reject_before_runtime_topology(self):
        for mutate in (lambda w: w.config['services']['proxy']['volumes'].pop(),
                       lambda w: w.config['services']['proxy']['volumes'][0].update(source='/foreign/config.yaml'),
                       lambda w: w.config['services']['proxy']['volumes'][2].update(read_only=False)):
            with self.subTest(mutate=mutate), self.assertRaisesRegex(AssertionError, 'mounts differ'): self.exercise(mutate)

    def test_finite_actual_services_ids_project_state_and_ports_are_required(self):
        def extra(w): w.config['services']['foreign'] = {'networks': {'proof': None}}
        def duplicate_service(w): w.rows[w.ids['office']]['labels']['com.docker.compose.service'] = 'webui'
        def duplicate_inspected_id(w): w.rows[w.ids['office']]['id'] = w.ids['webui']
        cases = (extra, lambda w: w.selected_ids.pop(), lambda w: w.selected_ids.append('e' * 64),
            lambda w: w.selected_ids.__setitem__(5, w.selected_ids[4]), duplicate_service, duplicate_inspected_id,
            lambda w: w.rows[w.ids['office']]['labels'].update({'com.docker.compose.project': 'foreign'}),
            lambda w: w.rows[w.ids['office']].update(running=False),
            lambda w: w.rows[w.ids['proxy']]['ports'].update({'4000/tcp': [{'HostIp': '0.0.0.0', 'HostPort': '4000'}]}),
            lambda w: w.config['services']['office'].update(ports=['8080:8080']))
        for mutate in cases:
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError): self.exercise(mutate)

    def test_declared_and_actual_networks_remain_only_the_same_internal_proof_owner(self):
        cases = (lambda w: w.config['networks'].update(public={'internal': False}),
            lambda w: w.config['networks']['proof'].update(internal=False),
            lambda w: w.config['networks']['proof'].update(external=True),
            lambda w: w.config['services']['office']['networks'].update(public=None),
            lambda w: w.config['services']['office'].update(network_mode='host'),
            lambda w: w.rows[w.ids['office']]['networks'].update(public={'IPAddress': '10.1.2.3'}),
            lambda w: w.rows[w.ids['office']].update(networkmode='host'),
            lambda w: w.rows[w.ids['office']]['networks'][w.network].update(NetworkID='e' * 64),
            lambda w: w.actual_network[0].update(Internal=False),
            lambda w: w.actual_network[0]['Labels'].update({'com.docker.compose.project': 'foreign'}))
        for mutate in cases:
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError): self.exercise(mutate)

    def test_office_security_and_ephemeral_storage_are_checked_declared_and_actual(self):
        cases = (lambda w: w.config['services']['office'].update(read_only=False),
            lambda w: w.config['services']['office'].update(init=False),
            lambda w: w.config['services']['office'].update(volumes=[{'type': 'bind', 'source': '/private', 'target': '/app'}]),
            lambda w: w.config['services']['office'].update(tmpfs=['/tmp:rw,size=128m']),
            lambda w: w.config['services']['office'].update(cap_drop=[]),
            lambda w: w.config['services']['office'].update(security_opt=[]),
            lambda w: w.rows[w.ids['office']].update(readonly=False),
            lambda w: w.rows[w.ids['office']].update(init=False),
            lambda w: w.rows[w.ids['office']].update(privileged=True),
            lambda w: w.rows[w.ids['office']].update(health='starting'),
            lambda w: w.rows[w.ids['office']].update(tmpfs={}),
            lambda w: w.rows[w.ids['office']].update(capdrop=[]),
            lambda w: w.rows[w.ids['office']].update(security=[]),
            lambda w: w.rows[w.ids['office']].update(mounts=[{'Type': 'volume', 'Destination': '/data'}]),
            lambda w: w.rows[w.ids['office']].update(mounts=[{'Type': 'bind', 'Destination': '/app'}]))
        for mutate in cases:
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError): self.exercise(mutate)

    def test_native_webui_ip_and_both_callback_owners_must_match(self):
        for mutate in (lambda w: w.rows[w.ids['webui']]['networks'][w.network].update(IPAddress='172.29.0.99'),
                       lambda w: w.config['services']['office']['environment'].update(OPENWEBUI_BASE_URL='http://foreign:8080'),
                       lambda w: w.environment.__setitem__(1, 'OPENWEBUI_BASE_URL=http://foreign:8080'),
                       lambda w: w.environment.append('OPENWEBUI_BASE_URL=http://webui:8080')):
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError): self.exercise(mutate)
        for base in ('https://172.29.0.6:8080', 'http://172.29.0.6:4000', 'http://user:secret@172.29.0.6:8080',
                     BASE + '/foreign', BASE + '?foreign=true'):
            with self.subTest(base=base), self.assertRaises(AssertionError): self.exercise(base=base)

    def test_docker_json_fails_closed_without_exporting_private_data(self):
        for result, kind in ((SimpleNamespace(returncode=1, stdout=b'private Docker error'), AssertionError),
                             (SimpleNamespace(returncode=0, stdout=b'not-json'), AssertionError),
                             (SimpleNamespace(returncode=0, stdout=b'[' + b' ' * office.MAX_BYTES + b']'), AssertionError),
                             (SimpleNamespace(returncode=0, stdout=json.dumps([SECRET]).encode()), ProofError)):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory); fixture = office.OfficeFixture(path / 'env', path, path / 'config', path, [SECRET])
                with patch.object(office.subprocess, 'run', return_value=result), self.assertRaises(kind) as raised:
                    fixture._docker_json(['inspect', 'fixed'])
                self.assertNotIn(SECRET, str(raised.exception))

    def test_external_docker_errors_are_bounded_and_do_not_export_private_exception_text(self):
        for error in (OSError(SECRET), office.subprocess.TimeoutExpired('fixed-inspect', 30, output=SECRET)):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory); fixture = office.OfficeFixture(path / 'env', path, path / 'config', path, [SECRET])
                with patch.object(office.subprocess, 'run', side_effect=error), self.assertRaisesRegex(AssertionError, 'Office Docker topology unavailable') as raised:
                    fixture._docker_json(['inspect', 'fixed'])
                self.assertNotIn(SECRET, str(raised.exception))


TERMINAL_KEY = 'goal584-terminal-fixture-private-' + 'k' * 32


class TerminalWorld(DockerWorld):
    """Finite native config/inspect IO, never a Python Compose merge emulator."""
    def __init__(self, fixture):
        super().__init__(fixture)
        self.version = b'2.24.4\n'
        name = office.TERMINAL_SERVICE
        self.ids[name] = '7' * 64
        self.selected_ids.append(self.ids[name])
        service = copy.deepcopy(yaml.safe_load((ROOT/'compose/openwebui.staging-terminal.compose.yml').read_text(encoding='utf8'))['services'][name])
        # These are explicit CLI JSON leaves. They do not claim native !override ran.
        service.update(networks={'proof': None}, mem_limit=805306368, memswap_limit=1073741824,
            volumes=[{'type': 'volume', 'source': 'terminal_home', 'target': '/home'}])
        service['environment']['OPEN_TERMINAL_API_KEY'] = TERMINAL_KEY
        self.config['services'][name] = service
        volume = self.config['name'] + '_terminal_home'
        self.config['volumes'] = {'terminal_home': {'name': volume}}
        proxy = 'localhost,127.0.0.1,webui,proxy,provider,postgres,redis,office,open-terminal-office,open-terminal-office:8000'
        self.config['services']['webui']['environment'] = {'NO_PROXY': proxy, 'no_proxy': proxy}
        self.webui_proxy = ['NO_PROXY=' + proxy, 'no_proxy=' + proxy, 'PRIVATE=' + SECRET]
        row = copy.deepcopy(self.rows[self.ids['webui']])
        row.update(id=self.ids[name], labels={'com.docker.compose.project': self.config['name'],
            'com.docker.compose.service': name}, ports={'8000/tcp': None}, init=None, tmpfs=None, capdrop=None,
            security=None, mounts=[{'Type': 'volume', 'Name': volume, 'Destination': '/home', 'RW': True,
                                  'Source': '/engine/volumes/' + volume + '/_data'}])
        row['terminal_inspect'] = {'Image': office.TERMINAL_IMAGE_ID,
            'Config': {'Image': service['image'], 'User': 'user', 'WorkingDir': '/home/user',
                'Entrypoint': ['/usr/bin/tini', '--', '/app/entrypoint.sh'], 'Cmd': ['run'],
                'Env': ['OPEN_TERMINAL_API_KEY=' + TERMINAL_KEY, 'OPEN_TERMINAL_MULTI_USER=true']},
            'HostConfig': {'Memory': 805306368, 'MemorySwap': 1073741824, 'NanoCpus': 500000000,
                'PidsLimit': 256, 'RestartPolicy': {'Name': 'no'}, 'CapAdd': None, 'Devices': []}}
        self.rows[self.ids[name]] = row
        self.volume = [{'Name': volume, 'Driver': 'local', 'Options': None,
            'Mountpoint': row['mounts'][0]['Source'], 'Labels': {'com.docker.compose.project': self.config['name'],
                'com.docker.compose.volume': 'terminal_home'}}]
        self.platform = {'id': office.TERMINAL_IMAGE_ID, 'os': 'linux', 'architecture': 'amd64'}

    def run(self, command, **kwargs):
        if command == ['docker', 'compose', 'version', '--short']:
            self.calls.append(command)
            return SimpleNamespace(returncode=0, stdout=self.version)
        if command[:3] == ['docker', 'volume', 'inspect']:
            self.calls.append(command)
            assert command[3] == self.config['name'] + '_terminal_home'
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.volume).encode())
        if command[:3] == ['docker', 'image', 'inspect']:
            self.calls.append(command)
            assert command[-1] == office.TERMINAL_IMAGE_ID
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.platform).encode())
        if command[:4] == ['docker','inspect','--format','{{json .Config.Env}}'] and command[-1] == self.ids['webui']:
            self.calls.append(command)
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.webui_proxy).encode())
        return super().run(command, **kwargs)


class TerminalTopologyTests(unittest.TestCase):
    def exercise(self, mutate=None, *, terminal=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); env = root/'proof.env'
            env.write_text('PROOF_DB_PASSWORD=' + SECRET + '\nSTAGING_TERMINAL_API_KEY=' + TERMINAL_KEY + '\n', encoding='utf8')
            env.chmod(0o600)
            fixture = office.OfficeFixture(env, root/'output', root/'config', root/'private', [SECRET, TERMINAL_KEY], terminal=terminal)
            world = TerminalWorld(fixture)
            if mutate: mutate(world)
            output = io.StringIO(); error = None
            with patch.object(office.subprocess, 'run', side_effect=world.run), contextlib.redirect_stdout(output):
                try: fixture.bind(BASE)
                except (AssertionError, ProofError) as caught: error = caught
            self.assertEqual(output.getvalue(), ''); self.assertFalse(fixture.output.exists())
            if error:
                self.assertIsNone(fixture._office_binding)
                self.assertNotIn(TERMINAL_KEY, str(error)); self.assertNotIn(SECRET, str(error))
            return fixture, world, error

    def test_overlay_reuses_only_native_extends_and_network_override_with_existing_no_proxy_prefix(self):
        path = ROOT/office.TERMINAL_OVERLAY
        tree = yaml.compose(path.read_text(encoding='utf8'))
        root = dict((key.value, value) for key,value in tree.value)
        services = dict((key.value, value) for key,value in root['services'].value)
        terminal = dict((key.value, value) for key,value in services[office.TERMINAL_SERVICE].value)
        self.assertEqual(set(terminal), {'extends', 'networks'})
        self.assertEqual({key.value:value.value for key,value in terminal['extends'].value},
                         {'file': 'openwebui.staging-terminal.compose.yml', 'service': office.TERMINAL_SERVICE})
        self.assertEqual(terminal['networks'].tag, '!override')
        self.assertEqual([node.value for node in terminal['networks'].value], ['proof'])
        self.assertEqual([key.value for key,_ in root['volumes'].value], ['terminal_home'])
        with self.assertRaises(yaml.constructor.ConstructorError): yaml.safe_load(path.read_text(encoding='utf8'))
        # The actual fixture consumes native CLI JSON, never safe_load on this overlay.
        prior = yaml.safe_load((ROOT/'compose/goal584.office-proof.yml').read_text(encoding='utf8'))
        webui = dict((key.value,value) for key,value in services['webui'].value)
        env = {key.value:value.value for key,value in webui['environment'].value}
        expected = prior['services']['webui']['environment']['NO_PROXY'] + ',open-terminal-office,open-terminal-office:8000'
        self.assertEqual(env, {'NO_PROXY': expected, 'no_proxy': expected})
        self.assertIn('>=2.24.4', path.read_text(encoding='utf8'))

    def test_explicit_seven_binding_keeps_default_office_artifact_binding_unchanged_and_env_private(self):
        fixture, world, error = self.exercise()
        self.assertIsNone(error)
        self.assertEqual(fixture.command[-2:], ['-f', office.TERMINAL_OVERLAY])
        self.assertEqual(set(fixture._office_binding['services']), {'webui', 'office'})
        self.assertEqual(fixture._terminal_binding['image_id'], world.platform['id'])
        row = office.topology_row(native_inspect(world.rows[world.ids[office.TERMINAL_SERVICE]]), terminal=True)
        self.assertNotIn(TERMINAL_KEY, json.dumps(row)); self.assertNotIn('Env', json.dumps(row))
        self.assertEqual(row['terminal']['key_sha256'], [hashlib.sha256(TERMINAL_KEY.encode()).hexdigest()])

    def test_default_false_rejects_seven_without_private_env_or_version_probe(self):
        fixture, world, error = self.exercise(terminal=False)
        self.assertIsNotNone(error)
        self.assertNotIn(office.TERMINAL_OVERLAY, fixture.command)
        self.assertNotIn(['docker', 'compose', 'version', '--short'], world.calls)
        with self.assertRaisesRegex(AssertionError, 'explicit boolean'):
            office.OfficeFixture(Path('env'), Path('out'), Path('config'), Path('private'), [], terminal='true')

    def test_optin_requires_exact_seven_declared_and_actual_services(self):
        cases = (lambda w:w.config['services'].pop(office.TERMINAL_SERVICE),
            lambda w:w.config['services'].update(foreign={'networks': {'proof': None}}),
            lambda w:w.selected_ids.pop(), lambda w:w.selected_ids.append('8'*64),
            lambda w:w.rows[w.ids[office.TERMINAL_SERVICE]]['labels'].update({'com.docker.compose.service':'webui'}))
        for change in cases:
            with self.subTest(change=change): self.assertIsNotNone(self.exercise(change)[2])

    def test_terminal_declared_image_resources_security_key_and_proxy_drift_fail(self):
        for field, value in (('image','foreign:latest'), ('build',{}), ('restart','always'), ('privileged',True),
                ('read_only',True), ('cap_add',['SYS_ADMIN']), ('devices',['/dev/sda']), ('user','0'),
                ('cap_drop',['ALL']), ('security_opt',['no-new-privileges:true']), ('init',True),
                ('command',['sh']), ('entrypoint',['sh']), ('mem_limit',1), ('memswap_limit',1), ('cpus',1), ('pids_limit',512)):
            with self.subTest(field=field):
                change = lambda w:w.config['services'][office.TERMINAL_SERVICE].update({field:value})
                self.assertIsNotNone(self.exercise(change)[2])
        for key, value in (('OPEN_TERMINAL_API_KEY',SECRET), ('OPEN_TERMINAL_MULTI_USER','false')):
            with self.subTest(key=key):
                self.assertIsNotNone(self.exercise(lambda w:w.config['services'][office.TERMINAL_SERVICE]['environment'].update({key:value}))[2])
        for key in ('NO_PROXY','no_proxy'):
            self.assertIsNotNone(self.exercise(lambda w:w.config['services']['webui']['environment'].update({key:'localhost'}))[2])
        self.assertIsNotNone(self.exercise(lambda w:w.webui_proxy.pop(0))[2])
        self.assertIsNotNone(self.exercise(lambda w:w.webui_proxy.append(w.webui_proxy[0]))[2])

    def test_terminal_actual_config_env_image_resources_health_and_privilege_drift_fail(self):
        for section, field, value in (('Config','Image','foreign:latest'), ('Config','User','root'),
                ('Config','WorkingDir','/'), ('Config','Entrypoint',['sh']), ('Config','Cmd',['sleep']),
                ('Config','Env',['OPEN_TERMINAL_API_KEY='+SECRET,'OPEN_TERMINAL_MULTI_USER=true']),
                ('Config','Env',['OPEN_TERMINAL_API_KEY='+TERMINAL_KEY]*2+['OPEN_TERMINAL_MULTI_USER=true']),
                ('Config','Env',['OPEN_TERMINAL_API_KEY='+TERMINAL_KEY]),
                ('HostConfig','Memory',1), ('HostConfig','MemorySwap',1), ('HostConfig','NanoCpus',1),
                ('HostConfig','PidsLimit',512), ('HostConfig','RestartPolicy',{'Name':'always'}),
                ('HostConfig','CapAdd',['SYS_ADMIN']), ('HostConfig','Devices',[{'PathOnHost':'/dev/sda'}])):
            with self.subTest(field=field, value=value):
                self.assertIsNotNone(self.exercise(lambda w:w.rows[w.ids[office.TERMINAL_SERVICE]]['terminal_inspect'][section].update({field:value}))[2])
        for field, value in (('privileged',True), ('readonly',True), ('health','starting'),
                             ('capdrop',['ALL']), ('security',['no-new-privileges']), ('init',True)):
            self.assertIsNotNone(self.exercise(lambda w:w.rows[w.ids[office.TERMINAL_SERVICE]].update({field:value}))[2])
        self.assertIsNotNone(self.exercise(lambda w:w.rows[w.ids[office.TERMINAL_SERVICE]]['terminal_inspect'].update(Image='sha256:'+'f'*64))[2])
        self.assertIsNotNone(self.exercise(lambda w:w.platform.update(architecture='arm64'))[2])

    def test_terminal_network_and_host_ports_keep_common_native_boundaries(self):
        cases = (lambda w:w.config['services'][office.TERMINAL_SERVICE]['networks'].update(isolated=None),
            lambda w:w.rows[w.ids[office.TERMINAL_SERVICE]]['networks'].update(public={}),
            lambda w:w.rows[w.ids[office.TERMINAL_SERVICE]].update(networkmode='host'),
            lambda w:w.config['services'][office.TERMINAL_SERVICE].update(ports=['8000:8000']),
            lambda w:w.rows[w.ids[office.TERMINAL_SERVICE]]['ports'].update({'8000/tcp':[{'HostPort':'8000'}]}))
        for change in cases:
            with self.subTest(change=change): self.assertIsNotNone(self.exercise(change)[2])

    def test_home_volume_must_be_project_owned_local_single_writable_mount(self):
        cases = (lambda w:w.config['volumes']['terminal_home'].update(external=True),
            lambda w:w.config['volumes']['terminal_home'].update(driver_opts={'device':'/host'}),
            lambda w:w.config['volumes']['terminal_home'].update(name='foreign'),
            lambda w:w.config['services'][office.TERMINAL_SERVICE]['volumes'][0].update(type='bind'),
            lambda w:w.config['services'][office.TERMINAL_SERVICE]['volumes'].append({'target':'/var/run/docker.sock'}),
            lambda w:w.rows[w.ids[office.TERMINAL_SERVICE]]['mounts'][0].update(Type='bind'),
            lambda w:w.rows[w.ids[office.TERMINAL_SERVICE]]['mounts'][0].update(Name='foreign'),
            lambda w:w.rows[w.ids[office.TERMINAL_SERVICE]]['mounts'][0].update(RW=False),
            lambda w:w.volume[0]['Labels'].update({'com.docker.compose.project':'foreign'}),
            lambda w:w.volume[0].update(Options={'device':'/host'}),
            lambda w:w.volume[0].update(Mountpoint='/foreign'))
        for change in cases:
            with self.subTest(change=change): self.assertIsNotNone(self.exercise(change)[2])

    def test_private_env_duplicates_malformed_or_unprotected_key_stop_before_cli(self):
        for content in ('STAGING_TERMINAL_API_KEY=x\n',
                'STAGING_TERMINAL_API_KEY='+TERMINAL_KEY+'\nSTAGING_TERMINAL_API_KEY='+TERMINAL_KEY+'\n',
                'STAGING_TERMINAL_API_KEY='+TERMINAL_KEY+'\nMALFORMED\n',
                'STAGING_TERMINAL_API_KEY="'+TERMINAL_KEY+'"\n',
                'STAGING_TERMINAL_API_KEY='+TERMINAL_KEY+'\nOTHER_KEY='+TERMINAL_KEY+'\n',
                'STAGING_TERMINAL_API_KEY='+TERMINAL_KEY+'\n#'+'x'*65536):
            with self.subTest(content=content[:40]):
                _, world, error = self.exercise(lambda w:w.fixture._terminal_env_file.write_text(content,encoding='utf8'))
                self.assertIsNotNone(error); self.assertEqual(world.calls, [])
        _, _, error = self.exercise(lambda w:w.fixture._terminal_env_file.write_text('STAGING_TERMINAL_API_KEY='+TERMINAL_KEY,encoding='utf8'))
        self.assertIsNone(error)
        _, world, error = self.exercise(lambda w:w.fixture.secrets.remove(TERMINAL_KEY))
        self.assertIsNotNone(error); self.assertEqual(world.calls, [])
        if os.name != 'nt':
            _, world, error = self.exercise(lambda w:w.fixture._terminal_env_file.chmod(0o644))
            self.assertIsNotNone(error); self.assertEqual(world.calls, [])

    def test_compose_minimum_and_bounded_version_are_explicit_without_fallback_parser(self):
        for version in (b'2.24.3\n', b'2.24.4-rc1\n', b'garbage', b'2.24.4 '+b'x'*129):
            with self.subTest(version=version):
                _, world, error = self.exercise(lambda w:setattr(w,'version',version))
                self.assertEqual(str(error), 'Terminal requires Docker Compose >=2.24.4')
                self.assertEqual(world.calls, [['docker','compose','version','--short']])
        self.assertIsNone(self.exercise(lambda w:setattr(w,'version',b'v2.39.4-desktop.1\n'))[2])


class ReadbackWorld(DockerWorld):
    """Actual container Python/verifier bytes; only Docker/Git/CLI IO is doubled."""
    def __init__(self, fixture, root):
        super().__init__(fixture)
        self.root, self.execs, self.cli_calls = root, [], []
        self.platform = {'os': 'linux', 'architecture': 'amd64'}
        self.revision = 'a' * 40
        self.verifier = (ROOT / 'deploy/openwebui-upgrade-0122/verify_frontend_artifact.py').read_bytes()
        inputs = {'source_commit': self.revision, 'upstream_commit': builder.UPSTREAM,
            'source_archive_sha256': 'a' * 64, 'git_inputs_sha256': 'b' * 64, 'frontend_sources_sha256': 'c' * 64}
        identity = hashlib.sha256((json.dumps(inputs, indent=2, sort_keys=True) + '\n').encode()).hexdigest()
        self.receipt = {'schema': 1, 'source_commit': self.revision, 'inputs': inputs, 'build_identity': identity,
            'native_office_accepted': False, 'images': {n: {'id': 'sha256:' + str(i) * 64}
                for i, n in enumerate(('frontend', 'webui', 'office'), 7)}}
        for name, files, base in (('webui', office.WEBUI_FILES, '/app/backend/open_webui'),
                                   ('office', office.OFFICE_FILES, '/app/officecli_openapi_proof')):
            for item in files:
                path = self.path(name, base + '/' + item); path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(('synthetic owned module ' + item).encode())
            modules = {item: builder.sha(self.path(name, base + '/' + item)) for item in files}
            self.receipt[name] = {'modules': modules}
            image = self.receipt['images'][name]['id']
            self.config['services'][name]['image'] = image
            self.rows[self.ids[name]].update(image_ref=image, image_id=image)
        build = self.path('webui', '/app/build'); (build / '_app').mkdir(parents=True)
        builder.write(build / '_app/version.json', {'version': identity}); (build / 'entry.js').write_bytes(b'actual frontend fixture')
        package = self.path('webui', '/usr/local/lib/openwebui-media-upload'); package.mkdir(parents=True)
        builder.write(package / 'frontend-files.json', builder.manifest(build))
        manifest_sha = builder.sha(package / 'frontend-files.json')
        builder.write(package / 'frontend-receipt.json', {'upstream_commit': builder.UPSTREAM,
            'build_identity': identity, 'input_receipt_sha256': identity,
            'source_archive_sha256': inputs['source_archive_sha256'], 'frontend_sources_sha256': inputs['frontend_sources_sha256'],
            'build_files_manifest_sha256': manifest_sha, 'build_files': 2})
        (package / 'verify_frontend_artifact.py').write_bytes(self.verifier)
        self.receipt.update(frontend_manifest_sha256=manifest_sha)
        self.receipt['webui'].update(build_hash=identity, version=identity)
        binary = self.path('office', '/usr/local/bin/officecli'); binary.parent.mkdir(parents=True)
        binary.write_bytes(b'fixed synthetic CLI bytes')
        self.receipt['office'].update(binary_sha256=builder.sha(binary), version='1.0.152')

    def path(self, name, value): return self.root / name / str(value).lstrip('/')

    def run(self, command, **kwargs):
        if command[:3] == ['git', '-c', 'gc.auto=0']:
            self.calls.append(command)
            assert command[3:] == ['show', self.revision + ':deploy/openwebui-upgrade-0122/verify_frontend_artifact.py']
            assert kwargs['env']['GIT_NO_LAZY_FETCH'] == '1' and kwargs['timeout'] == 15
            return SimpleNamespace(returncode=0, stdout=self.verifier)
        if command[:4] == ['docker', 'image', 'inspect', '--format']:
            self.calls.append(command)
            assert '"architecture"' in command[4] and kwargs['timeout'] == 30
            return SimpleNamespace(returncode=0, stdout=json.dumps({'id': command[-1], **self.platform}).encode())
        if command[:2] == ['docker', 'exec']:
            self.calls.append(command)
            name = next(n for n in ('webui', 'office') if self.ids[n] == command[2])
            assert command[3:6] == ['python', '-B', '-c'] and len(command) == 7
            assert kwargs['timeout'] == 30
            code = command[-1]; self.execs.append((name, code))
            real_pathlib = __import__('pathlib'); mapped = ModuleType('pathlib'); mapped.__dict__.update(vars(real_pathlib))
            mapped.Path = lambda value: self.path(name, value)
            def cli(arguments, **options):
                assert arguments == [str(self.path('office', '/usr/local/bin/officecli')), '--version']
                assert options == {'text': True, 'timeout': 10}
                self.cli_calls.append(arguments); return '1.0.152\n'
            output = io.StringIO()
            try:
                with patch.dict(sys.modules, {'pathlib': mapped}), patch.dict(os.environ, {'WEBUI_BUILD_HASH': self.receipt['build_identity'],
                        'ENABLE_RESPONSES_API_STATEFUL': 'false'}), \
                        patch.object(office.subprocess, 'check_output', side_effect=cli), contextlib.redirect_stdout(output):
                    exec(compile(code, 'actual-container-python', 'exec'), {})
            except (AssertionError, OSError, ValueError):
                return SimpleNamespace(returncode=1, stdout=b'')
            return SimpleNamespace(returncode=0, stdout=output.getvalue().encode())
        if command[:3] == ['docker', 'inspect', '--format'] and '"image_ref"' in command[3]:
            self.calls.append(command)
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.rows[command[-1]]).encode())
        return super().run(command, **kwargs)


class OfficeReadbackTests(unittest.TestCase):
    def exercise(self, mutate=None, fail=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory); fixture = office.OfficeFixture(path / 'env', path / 'output', path / 'config', path / 'private', [SECRET])
            world = ReadbackWorld(fixture, path / 'artifacts')
            if mutate: mutate(world)
            def run(command, **kwargs):
                if fail and fail(command): return SimpleNamespace(returncode=1, stdout=SECRET.encode())
                return world.run(command, **kwargs)
            output = io.StringIO(); error = None; result = None
            with patch.object(office.subprocess, 'run', side_effect=run), contextlib.redirect_stdout(output):
                try: result = fixture.running_readback(BASE, world.receipt, world.revision)
                except (AssertionError, ProofError) as caught: error = caught
            self.assertEqual(output.getvalue(), ''); self.assertFalse((path / 'output').exists())
            if error: self.assertNotIn(SECRET, str(error))
            return result, error, world

    def test_actual_inspection_scripts_and_existing_frontend_verifier_produce_native_running_contract(self):
        result, error, world = self.exercise()
        self.assertIsNone(error)
        self.assertEqual(set(result), {'webui', 'office'})
        for name in result:
            self.assertEqual(result[name]['modules'], world.receipt[name]['modules'])
            self.assertEqual(result[name]['image_id'], world.receipt['images'][name]['id'])
            self.assertEqual(result[name]['image_ref'], result[name]['image_id'])
        self.assertEqual(result['webui']['frontend_result'], {'frontend_files': 2,
            'native_build_hash': world.receipt['build_identity'], 'complete_manifest': 'verified'})
        self.assertEqual(result['office']['version'], '1.0.152')
        self.assertEqual(result['webui']['responses_stateful_env'], 'false')
        self.assertEqual(len(world.execs), 3); self.assertEqual(len(world.cli_calls), 1)

    def test_wrong_declared_live_image_scope_and_shadowing_mounts_reject_before_any_exec(self):
        cases = (lambda w: w.config['services']['webui'].update(image='foreign:tag'),
            lambda w: w.receipt.update(source_commit='f' * 40),
            lambda w: w.platform.update(architecture='arm64'),
            lambda w: w.rows[w.ids['webui']].update(image_id='sha256:' + 'f' * 64),
            lambda w: w.rows[w.ids['office']].update(image_ref='foreign:tag'),
            lambda w: w.rows[w.ids['webui']]['mounts'].append({'Type': 'bind', 'Destination': '/app'}),
            lambda w: w.rows[w.ids['webui']]['mounts'].append({'Type': 'bind', 'Destination': '/app/backend/open_webui/utils/tools.py'}),
            lambda w: w.rows[w.ids['webui']]['mounts'].append({'Type': 'volume', 'Destination': '/app/build'}),
            lambda w: w.rows[w.ids['webui']]['mounts'].append({'Type': 'bind', 'Destination': '/usr/local/lib/openwebui-media-upload/verify_frontend_artifact.py'}),
            lambda w: w.rows[w.ids['office']]['mounts'].append({'Type': 'bind', 'Destination': '/usr/local/bin/officecli'}),
            lambda w: w.rows[w.ids['webui']]['mounts'].append({'Type': 'bind', 'Destination': '/app/../app/build'}))
        for mutate in cases:
            with self.subTest(mutate=mutate):
                result, error, world = self.exercise(mutate)
                self.assertIsNone(result); self.assertIsNotNone(error); self.assertEqual(world.execs, [])

    def test_wrong_actual_frontend_verifier_bytes_never_execute_that_verifier(self):
        def change(world): world.path('webui', '/usr/local/lib/openwebui-media-upload/verify_frontend_artifact.py').write_bytes(b'raise RuntimeError("must not execute")')
        result, error, world = self.exercise(change)
        self.assertIsNone(result); self.assertRegex(str(error), 'verifier source differs')
        self.assertEqual(len(world.execs), 1); self.assertNotIn('exec(compile', world.execs[0][1])

    def test_actual_file_module_cli_and_frontend_changes_reject_at_real_owner_boundary(self):
        def module(world): world.path('webui', '/app/backend/open_webui/config.py').write_bytes(b'foreign module')
        def binary(world): world.path('office', '/usr/local/bin/officecli').write_bytes(b'foreign binary')
        def frontend(world): world.path('webui', '/app/build/entry.js').write_bytes(b'foreign frontend')
        for mutate in (module, binary, frontend):
            with self.subTest(mutate=mutate):
                result, error, world = self.exercise(mutate)
                self.assertIsNone(result); self.assertIsNotNone(error)
                if mutate is binary: self.assertEqual(world.cli_calls, [])

    def test_external_git_inspect_and_exec_failures_stop_with_safe_bounded_error(self):
        for fail in (lambda c: c[0] == 'git', lambda c: c[:3] == ['docker', 'image', 'inspect'],
                     lambda c: c[:2] == ['docker', 'exec']):
            with self.subTest(fail=fail):
                result, error, world = self.exercise(fail=fail)
                self.assertIsNone(result); self.assertIsNotNone(error)


def native_context_owners():
    import test_office_compatibility as owner
    source = os.environ.get('GOAL584_NATIVE_SOURCE_ROOT')
    if source: owner.NATIVE = Path(source)
    native = owner.native.__wrapped__()
    # Extend the existing scratch extractor's return only; its real appliers and
    # deployed SHA assertions still bind the exact router bytes we import below.
    tree = ast.parse(Path(owner.__file__).read_bytes())
    extractor = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'deployed_context_owner')
    result = next(n for n in ast.walk(extractor) if isinstance(n, ast.Return))
    result.value = ast.Tuple(elts=[result.value, ast.parse(
        "{name:(mirror/name).read_bytes() for name in ('routers/openai.py','utils/misc.py','utils/middleware.py')}",
        mode='eval').body], ctx=ast.Load())
    namespace = vars(owner).copy()
    exec(compile(ast.fix_missing_locations(ast.Module(body=[extractor], type_ignores=[])), 'existing-native-source-extractor', 'exec'), namespace)
    _, deployed = namespace['deployed_context_owner']()
    sources = {'utils/tools.py': (owner.NATIVE / 'utils/tools.py').read_bytes().replace(b'\r\n', b'\n'), **deployed}
    assert {n: hashlib.sha256(v).hexdigest() for n, v in sources.items()} == {
        **{n: owner.P.WEBUI_MODULES[n] for n in sources if n in owner.P.WEBUI_MODULES},
        'utils/misc.py': '9098c447441e2f6bfa529ae8506a03acab6400a8205c7942e86b004c07833068'}
    return owner, native, sources


def native_resolution_world(world, native_root):
    """Actual native models/repositories/ACL/resolver; only DB/query IO leaves.

    Storage uses the actual local-provider get_file method and aiofiles reads a
    real temporary PNG. No success resolver or authenticated user DTO is mocked.
    """
    import aiofiles
    import importlib.util
    import pydantic
    from typing import Any
    raw = {name: (native_root / name).read_bytes().replace(b'\r\n', b'\n')
           for name in office.NATIVE_RESOLUTION_SOURCES}
    # Replay the existing runtime media stage, rather than attesting upstream
    # storage bytes as if they were the deployed resolver owner.
    media = ROOT / 'deploy/openwebui-patches/media-upload-v0.12.2'
    manifest = json.loads((media / 'manifest.json').read_bytes())['files']['backend/open_webui/storage/provider.py']
    if hashlib.sha256(raw['storage/provider.py']).hexdigest() == manifest['upstream_sha256']:
        spec = importlib.util.spec_from_file_location('office_existing_resolution_media', media / 'apply_media.py')
        applier = importlib.util.module_from_spec(spec); spec.loader.exec_module(applier)
        raw['storage/provider.py'] = applier.transform('backend/open_webui/storage/provider.py', raw['storage/provider.py'].decode()).encode()
    assert hashlib.sha256(raw['storage/provider.py']).hexdigest() == manifest['candidate_sha256']
    assert {name: hashlib.sha256(value).hexdigest() for name, value in raw.items()} == office.NATIVE_RESOLUTION_SOURCES
    for name, value in raw.items():
        target = world.path('webui', '/app/backend/open_webui/' + name)
        target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(value)
        if name in world.receipt['webui']['modules']:
            world.receipt['webui']['modules'][name] = hashlib.sha256(value).hexdigest()
    world.user_rows = {'caller': SimpleNamespace(id='caller', email='native@example.invalid', name='Native fixture',
        role='user', last_active_at=0, updated_at=0, created_at=0)}
    world.file_rows, world.db_reads, world.access_queries = {}, [], []
    User, File = type('NativeUserTableMarker', (), {}), type('NativeFileTableMarker', (), {})

    class Database:
        async def get(self, table, key):
            world.db_reads.append(('user' if table is User else 'file', key))
            return (world.user_rows if table is User else world.file_rows).get(key)

    @contextlib.asynccontextmanager
    async def database(db=None): yield Database()

    ns = {'__name__': __name__, 'datetime': __import__('datetime'), 'Optional': Optional, 'Any': Any,
        'BaseModel': pydantic.BaseModel, 'ConfigDict': pydantic.ConfigDict, 'Field': pydantic.Field,
        'field_validator': pydantic.field_validator, 'model_validator': pydantic.model_validator,
        'AsyncSession': Any, 'User': User, 'File': File, 'get_async_db_context': database,
        'log': SimpleNamespace(debug=lambda *a: None, exception=lambda *a: None)}

    def extract(relative, names, *, method=None):
        tree = ast.parse(raw[relative]); nodes = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in names:
                if method:
                    node = copy.deepcopy(node)
                    node.body = [n for n in node.body if isinstance(n, ast.AsyncFunctionDef) and n.name == method]
                    assert len(node.body) == 1
                nodes.append(node)
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets):
                nodes.append(node)
        assert len(nodes) == len(names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'actual-native-' + relative, 'exec'), ns)

    extract('models/users.py', {'UserSettings', '_DEFAULT_PROFILE_IMAGE_URL', 'UserModel'})
    extract('models/users.py', {'UsersTable'}, method='get_user_by_id')
    extract('models/files.py', {'FileModel'})
    extract('models/files.py', {'FilesTable'}, method='get_file_by_id')
    ns.update(Users=ns['UsersTable'](), Files=ns['FilesTable']())

    def query_owner(name, methods):
        result = SimpleNamespace()
        for method in methods:
            async def read(*args, _method=method, **kwargs):
                world.access_queries.append((name, _method))
                return []
            setattr(result, method, read)
        return result
    for name, methods in {
        'Knowledges': ('get_knowledges_by_file_id',), 'Groups': ('get_groups_by_member_id',),
        'Channels': ('get_channels_by_file_id_and_user_id',),
        'Chats': ('get_shared_chat_ids_by_file_id', 'get_accessible_chat_by_id'),
        'Notes': ('get_note_ids_by_file_id',), 'Models': ('get_model_owner_ids_by_file_id',),
        'AccessGrants': ('has_access', 'get_accessible_resource_ids')}.items(): ns[name] = query_owner(name, methods)
    # This query returns a mapping, as required by the actual native ACL owner.
    async def model_owners(*args, **kwargs):
        world.access_queries.append(('Models', 'get_model_owner_ids_by_file_id')); return {}
    ns['Models'].get_model_owner_ids_by_file_id = model_owners
    extract('utils/access_control/files.py', {'has_access_to_file'})
    storage = next(n for n in ast.parse(raw['storage/provider.py']).body if isinstance(n, ast.ClassDef) and n.name == 'LocalStorageProvider')
    get_file = next(n for n in storage.body if isinstance(n, ast.FunctionDef) and n.name == 'get_file')
    exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(name='LocalStorageProvider', bases=[],
        keywords=[], body=[get_file], decorator_list=[])], type_ignores=[])), 'actual-native-storage-provider', 'exec'), ns)
    ns.update(Storage=ns['LocalStorageProvider'], asyncio=asyncio, base64=base64, mimetypes=mimetypes,
        aiofiles=aiofiles, Path=Path, re=re, ENABLE_IMAGE_CONTENT_TYPE_EXTENSION_FALLBACK=False)
    extract('utils/files.py', {'FILE_CONTENT_URL_PATTERN', '_IMAGE_MIME_FALLBACK',
        'get_image_base64_from_url', 'get_image_base64_from_file_id'})
    middleware = ast.parse(world.path('webui', '/app/backend/open_webui/utils/middleware.py').read_bytes())
    converter = next(n for n in middleware.body if isinstance(n, ast.AsyncFunctionDef) and n.name == 'convert_url_images_to_base64')
    exec(compile(ast.Module(body=[converter], type_ignores=[]), 'actual-deployed-native-image-converter', 'exec'), ns)
    return ns


class NativeContextWorld(ReadbackWorld):
    """Execute emitted Python; Docker paths/imports/argv are explicit IO doubles.

    Imported schema/converter functions are the existing fixture's actual pinned
    native owners. This does not claim whole-module or installed-image imports.
    """
    def __init__(self, fixture, root, owners, openapi):
        super().__init__(fixture, root)
        owner, self.native, sources = owners
        for name, raw in sources.items(): self.path('webui', '/app/backend/open_webui/' + name).write_bytes(raw)
        self.receipt['webui']['modules'].update({n: hashlib.sha256(v).hexdigest() for n, v in sources.items()})
        self.handoff = {'schema': 1, 'private_sentinel': SECRET, 'office_service_setup': {'stage': 'readback_ready'},
            'users': [{'id': 'caller'}], 'admin': {'id': 'native-admin'},
            'office_setup': {'openapi': copy.deepcopy(openapi)}}
        fixture.private.mkdir(); self.state = fixture.private / 'office-state.private.json'; self.save()
        self.native_commands, self.failure = [], None
        self.before_exec = self.during_convert = self.packet_mutation = None
        self.payload_mutation = self.during_output = None
        self.native_resolution = native_resolution_world(self, owner.NATIVE)

    def save(self):
        self.state.write_text(json.dumps(self.handoff)); self.state.chmod(0o600)

    def run(self, command, **kwargs):
        if command[:2] != ['docker', 'exec'] or len(command) != 8: return super().run(command, **kwargs)
        self.calls.append(command); self.native_commands.append(command)
        assert command[2] == self.ids['webui'] and command[3:6] == ['python', '-B', '-c']
        assert kwargs['capture_output'] is True and kwargs['timeout'] == 30
        if self.before_exec: self.before_exec(self)
        if self.payload_mutation:
            payload = json.loads(command[-1]); self.payload_mutation(payload)
            command[-1] = json.dumps(payload, ensure_ascii=True, allow_nan=False)
        tools, router, _ = self.native
        modules = {name: ModuleType(name) for name in ('open_webui', 'open_webui.utils', 'open_webui.routers',
            'open_webui.models', 'open_webui.models.users', 'open_webui.utils.files',
            'open_webui.utils.tools', 'open_webui.routers.openai', 'open_webui.utils.misc', 'open_webui.utils.middleware')}
        for name in ('convert_openapi_to_tool_payload', 'clean_openai_tool_schema'):
            setattr(modules['open_webui.utils.tools'], name, tools[name])
        modules['open_webui.routers.openai'].convert_to_responses_payload = router['convert_to_responses_payload']
        modules['open_webui.utils.misc'].convert_output_to_messages = router['convert_output_to_messages']
        modules['open_webui.utils.middleware'].process_messages_with_output = router['process_messages_with_output']
        for name in ('sanitize_tool_pairs', 'normalize_messages_for_model'):
            setattr(modules['open_webui.utils.middleware'], name, router[name])
        modules['open_webui.models.users'].Users = self.native_resolution['Users']
        modules['open_webui.utils.files'].FILE_CONTENT_URL_PATTERN = self.native_resolution['FILE_CONTENT_URL_PATTERN']
        modules['open_webui.utils.middleware'].convert_url_images_to_base64 = self.native_resolution['convert_url_images_to_base64']
        if self.during_output:
            def convert(saved, **options):
                value = router['convert_output_to_messages'](saved, **options); self.during_output(saved); return value
            modules['open_webui.utils.misc'].convert_output_to_messages = convert
        if self.during_convert:
            def clean(spec):
                value = tools['clean_openai_tool_schema'](spec); self.during_convert(self); return value
            modules['open_webui.utils.tools'].clean_openai_tool_schema = clean
        mapped = ModuleType('pathlib'); mapped.__dict__.update(vars(__import__('pathlib')))
        mapped.Path = lambda value: self.path('webui', value)
        output = io.StringIO()
        try:
            with patch.dict(sys.modules, modules | {'pathlib': mapped}), \
                    patch.object(sys, 'argv', ['-c', command[-1]]), contextlib.redirect_stdout(output):
                exec(compile(command[-2], 'actual-native-context-container-python', 'exec'), {})
        except Exception as error:
            self.failure = type(error).__name__
            return SimpleNamespace(returncode=1, stdout=b'', stderr=SECRET.encode())
        packet = json.loads(output.getvalue())
        if self.packet_mutation: self.packet_mutation(packet)
        return SimpleNamespace(returncode=0, stdout=json.dumps(packet).encode())


def native_context_world(tmp_path, monkeypatch, native_context_owners):
    owner, native, _ = native_context_owners
    component = owner.component.__wrapped__(monkeypatch, tmp_path, native)
    schema = component.client.get('/openapi.json').json()  # Actual Office app, no authored schema DTO.
    fixture = office.OfficeFixture(tmp_path / 'env', tmp_path / 'output', tmp_path / 'config', tmp_path / 'private', [SECRET])
    world = NativeContextWorld(fixture, tmp_path / 'images', native_context_owners, schema)
    monkeypatch.setattr(office.subprocess, 'run', world.run)
    return world


def assert_native_context_executes_actual_native_schema_converter_and_deduplicates(native_context_world):
    world = native_context_world
    reason = [{'id': 'rs-native-fixture', 'type': 'reasoning', 'summary': [{'type': 'summary_text', 'text': 'Summary'}],
        'encrypted_content': 'synthetic-opaque-reasoning'}]
    second = [*reason, {**reason[0], 'id': 'rs-second-native-fixture'}]
    cases = [[], reason, second, copy.deepcopy(reason)]; original = copy.deepcopy(cases); private = world.state.read_bytes()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        packet = world.fixture.native_context(BASE, world.receipt, world.revision, cases)
    assert output.getvalue() == '' and cases == original and world.state.read_bytes() == private
    tools, router, _ = world.native; schema = world.handoff['office_setup']['openapi']
    assert packet['native_specs'] == [tools['clean_openai_tool_schema'](s) for s in tools['convert_openapi_to_tool_payload'](schema)]
    assert len(packet['native_specs']) == 14
    assert packet['reasoning_cases'] == [{'input_reasoning': case, 'native_input': router['convert_to_responses_payload'](
        {'messages': [{'role': 'assistant', 'output': case}]})['input']} for case in ([], reason, second)]
    assert set(packet) == {'schema', 'module_sha256', 'source_body_sha256', 'native_specs', 'reasoning_cases'}
    assert set(packet['module_sha256']) == {'utils/tools.py', 'routers/openai.py'}
    assert packet['source_body_sha256'] == office.digest(schema)
    assert len(world.native_commands) == 1 and len(world.native_commands[0][-1].encode('ascii')) <= 96 * 1024
    assert world.cli_calls and any('exec(compile' in code for _, code in world.execs)
    assert SECRET not in json.dumps(packet) and not world.fixture.output.exists()


def assert_native_context_refuses_module_file_mutation_before_or_during_actual_producer(native_context_world, moment):
    world = native_context_world
    def change(w): w.path('webui', '/app/backend/open_webui/utils/tools.py').write_bytes(b'foreign producer')
    setattr(world, 'before_exec' if moment == 'before' else 'during_convert', change)
    with pytest.raises(AssertionError, match='Office Docker topology unavailable .*exec; exit=1; stdout_bytes=0'):
        world.fixture.native_context(BASE, world.receipt, world.revision, [[]])
    assert world.failure == 'AssertionError' and len(world.native_commands) == 1


def assert_native_context_private_source_reasoning_and_argument_guards(native_context_world, kind):
    world = native_context_world; cases = [[]]
    if kind == 'missing': world.state.unlink()
    elif kind == 'unprepared': world.handoff['office_service_setup']['stage'] = 'partial'; world.save()
    elif kind == 'bad_cases': cases = [[{'type': 'message', 'content': SECRET}]]
    elif kind == 'large_argument': world.handoff['office_setup']['openapi']['x-large'] = 'x' * (96 * 1024); world.save()
    else:
        operation = world.handoff['office_setup']['openapi']['paths']['/v1/officecli/documents/export-answer']['post']
        operation['description'] = SECRET; world.save()
    with pytest.raises((AssertionError, ProofError)) as failed:
        world.fixture.native_context(BASE, world.receipt, world.revision, cases)
    assert SECRET not in str(failed.value) and not world.fixture.output.exists()
    assert len(world.native_commands) == (1 if kind == 'source_secret' else 0)


def assert_native_context_rejects_mutated_producer_packet_and_private_output(native_context_world, mutate):
    world = native_context_world; world.packet_mutation = mutate
    with pytest.raises((AssertionError, ProofError)) as failed:
        world.fixture.native_context(BASE, world.receipt, world.revision, [[]])
    assert SECRET not in str(failed.value) and not world.fixture.output.exists()
    assert len(world.native_commands) == 1


class OfficeNativeContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.owners = native_context_owners()

    @contextlib.contextmanager
    def world(self):
        with tempfile.TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as monkeypatch:
            yield native_context_world(Path(directory), monkeypatch, self.owners)

    def test_actual_emitted_python_native_schemas_and_deduplicated_reasoning(self):
        with self.world() as world:
            assert_native_context_executes_actual_native_schema_converter_and_deduplicates(world)

    def test_source_module_mutation_before_and_during_producer_is_refused(self):
        for moment in ('before', 'during'):
            with self.subTest(moment=moment), self.world() as world:
                assert_native_context_refuses_module_file_mutation_before_or_during_actual_producer(world, moment)

    def test_private_handoff_reasoning_and_argv_bounds_precede_native_exec(self):
        for kind in ('missing', 'unprepared', 'bad_cases', 'large_argument', 'source_secret'):
            with self.subTest(kind=kind), self.world() as world:
                assert_native_context_private_source_reasoning_and_argument_guards(world, kind)

    def test_native_producer_packet_shape_origin_bindings_and_secret_are_failclosed(self):
        cases = (lambda p: p.update(schema=True), lambda p: p.update(module_sha256={}),
            lambda p: p.update(source_body_sha256='0' * 64), lambda p: p.update(native_specs={}),
            lambda p: p.update(reasoning_cases=[]), lambda p: p['reasoning_cases'][0].update(native_input={}),
            lambda p: p['reasoning_cases'][0].update(input_reasoning=[{'type': 'reasoning', 'id': 'foreign'}]),
            lambda p: p.update(private=SECRET))
        for index, mutate in enumerate(cases):
            with self.subTest(case=index), self.world() as world:
                assert_native_context_rejects_mutated_producer_packet_and_private_output(world, mutate)

    def saved_output(self):
        # Caller-supplied native output fixture, not a DB/history-origin claim.
        reason = {'type': 'reasoning', 'id': 'rs-first', 'summary': [], 'encrypted_content': 'opaque-fixture'}
        return [reason, {'type': 'function_call', 'call_id': 'call-first', 'name': 'render_office_file',
                'arguments': '{"file_id":"native-file"}', 'status': 'completed'},
            {'type': 'function_call_output', 'call_id': 'call-first', 'output': [
                {'type': 'input_text', 'text': 'Selected file result'},
                {'type': 'input_image', 'image_url': 'data:image/png;base64,c3ludGhldGljLWltYWdl'}]},
            {**reason, 'id': 'rs-second'},
            {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Ready'}]}]

    def test_saved_output_uses_actual_deployed_native_pipeline_without_assembling_history(self):
        with self.world() as world:
            supplied = self.saved_output(); original = copy.deepcopy(supplied); private = world.state.read_bytes()
            packet = world.fixture.native_context(BASE, world.receipt, world.revision, [[]], saved_output=supplied)
            observed = packet['saved_output_case']; native = world.native[1]
            options = {'reasoning_format': 'responses', 'flatten_tool_images': False}
            messages = native['convert_output_to_messages'](supplied, raw=True, **options)
            messages = native['process_messages_with_output'](messages, **options)
            assert observed == {'input_saved_output': original,
                'native_input': native['convert_to_responses_payload']({'messages': messages})['input']}
            assert [item['type'] for item in observed['native_input']] == [item['type'] for item in supplied]
            assert [item['id'] for item in observed['native_input'] if item['type'] == 'reasoning'] == ['rs-first', 'rs-second']
            assert observed['native_input'][2]['output'][1] == supplied[2]['output'][1]
            assert all(item.get('role') != 'user' for item in observed['native_input'])
            assert supplied == original and world.state.read_bytes() == private
            assert set(packet['module_sha256']) == {'utils/tools.py', 'routers/openai.py', 'utils/misc.py', 'utils/middleware.py'}
            assert set(packet) == {'schema', 'module_sha256', 'source_body_sha256', 'native_specs',
                'reasoning_cases', 'saved_output_case'}
            assert len(world.native_commands) == 1 and len(world.native_commands[0][-1].encode('ascii')) <= 96 * 1024
            assert not world.fixture.output.exists()

    def test_saved_output_shape_foreign_user_secrets_and_bound_fail_before_producer(self):
        cases = ({}, [], 'foreign', [{'role': 'user', 'content': 'not native output'}],
            [{'type': 'message', 'role': 'user', 'content': []}], [{'type': 'foreign'}],
            [{'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': SECRET}]}],
            [{'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'x' * (96 * 1024)}]}])
        for index, supplied in enumerate(cases):
            with self.subTest(case=index), self.world() as world:
                with self.assertRaises((AssertionError, ProofError)) as failed:
                    world.fixture.native_context(BASE, world.receipt, world.revision, [[]], saved_output=supplied)
                assert SECRET not in str(failed.exception) and not world.native_commands and not world.fixture.output.exists()

    def test_saved_output_attests_both_added_module_files_before_and_after_conversion(self):
        for name in ('utils/misc.py', 'utils/middleware.py'):
            for moment in ('before_exec', 'during_convert'):
                with self.subTest(module=name, moment=moment), self.world() as world:
                    def change(w): w.path('webui', '/app/backend/open_webui/' + name).write_bytes(b'foreign producer')
                    setattr(world, moment, change)
                    with self.assertRaisesRegex(AssertionError, 'Office Docker topology unavailable .*exec; exit=1; stdout_bytes=0'):
                        world.fixture.native_context(BASE, world.receipt, world.revision, [[]], saved_output=self.saved_output())
                    assert world.failure == 'AssertionError' and len(world.native_commands) == 1

    def test_saved_output_producer_refuses_foreign_envelope_and_mutated_supplied_input(self):
        variants = (lambda p: p.update(foreign_payload=True),
            lambda p: p['saved_output'].append({'type': 'message', 'role': 'user', 'content': []}),
            lambda p: p['saved_output'][0].update(id='foreign-saved-output'))
        for index, mutate in enumerate(variants):
            with self.subTest(case=index), self.world() as world:
                world.payload_mutation = mutate
                with self.assertRaises((AssertionError, ProofError)):
                    world.fixture.native_context(BASE, world.receipt, world.revision, [[]], saved_output=self.saved_output())
                assert len(world.native_commands) == 1 and not world.fixture.output.exists()
        with self.world() as world:
            supplied = self.saved_output(); original = copy.deepcopy(supplied)
            world.during_output = lambda value: value[0].update(id='mutated-during-native-conversion')
            with self.assertRaisesRegex(AssertionError, 'Office Docker topology unavailable .*exec; exit=1; stdout_bytes=0'):
                world.fixture.native_context(BASE, world.receipt, world.revision, [[]], saved_output=supplied)
            assert supplied == original and world.failure == 'AssertionError'

    def test_saved_output_packet_echo_shape_extra_case_and_secret_are_failclosed(self):
        variants = (lambda p: p.pop('saved_output_case'), lambda p: p.update(saved_output_case=None),
            lambda p: p['saved_output_case'].update(input_saved_output=[]),
            lambda p: p['saved_output_case'].update(native_input={}),
            lambda p: p['saved_output_case'].update(foreign_case=[]),
            lambda p: p.update(foreign_payload=[]),
            lambda p: p['saved_output_case'].update(native_input=[{'private': SECRET}]))
        for index, mutate in enumerate(variants):
            with self.subTest(case=index), self.world() as world:
                world.packet_mutation = mutate
                with self.assertRaises((AssertionError, ProofError)) as failed:
                    world.fixture.native_context(BASE, world.receipt, world.revision, [[]], saved_output=self.saved_output())
                assert SECRET not in str(failed.exception) and len(world.native_commands) == 1 and not world.fixture.output.exists()
        with self.world() as world:
            world.packet_mutation = lambda p: p.update(saved_output_case={'input_saved_output': [], 'native_input': []})
            with self.assertRaisesRegex(AssertionError, 'Office unexpected native saved output observation'):
                world.fixture.native_context(BASE, world.receipt, world.revision, [[]])

    @contextlib.contextmanager
    def image_case(self):
        # Full finite Handler/Office factory + native converters, including the
        # actual PNG. None of P's context/history/scope checks are replaced.
        owner = self.owners[0]
        with tempfile.TemporaryDirectory() as directory, pytest.MonkeyPatch.context() as monkeypatch:
            root = Path(directory)
            component = owner.component.__wrapped__(monkeypatch, root, self.owners[1])
            case = owner.saved_continuation.__wrapped__(component, monkeypatch, root, self.owners)
            observer = root / 'file-resolution'; observer.mkdir()
            world = native_context_world(observer, monkeypatch, self.owners)
            yield world, case

    def stored_image(self, world, case):
        saved = copy.deepcopy(case.kwargs['saved_output'])
        image = next(part for item in saved if item.get('type') == 'function_call_output'
            for part in item['output'] if part.get('type') == 'input_image')
        png = base64.b64decode(image['image_url'].split(',', 1)[1], validate=True)
        assert png.startswith(b'\x89PNG\r\n\x1a\n') and png == case.kwargs['png']
        path = world.root / 'stored-tool-image.png'; path.write_bytes(png)
        world.file_rows['native-tool-image'] = SimpleNamespace(id='native-tool-image', user_id='caller',
            filename=path.name, path=str(path), meta={'content_type': 'image/png'}, created_at=0, updated_at=0)
        image['image_url'] = '/api/v1/files/native-tool-image/content'
        return saved, path

    def observe_saved(self, world, case, saved):
        reasons = [[v for v in call['provider']['response']['output'] if v['type'] == 'reasoning']
                   for call in case.kwargs['first_calls']]
        return world.fixture.native_context(BASE, world.receipt, world.revision, reasons, saved_output=saved)

    def test_owned_native_file_resolves_actual_png_and_passes_entire_saved_context_without_input_mutation(self):
        with self.image_case() as (world, case):
            supplied, path = self.stored_image(world, case)
            original = copy.deepcopy(supplied); private = world.state.read_bytes(); png = path.read_bytes()
            packet = self.observe_saved(world, case, supplied)
            assert packet['saved_output_case']['native_input'] == case.kwargs['native_saved']['saved_output_case']['native_input']
            assert packet['saved_output_case']['input_saved_output'] == original == supplied
            assert world.state.read_bytes() == private and path.read_bytes() == png
            assert world.db_reads == [('user', 'caller'), ('file', 'native-tool-image')] and not world.access_queries
            assert type(world.native_resolution['Users']).__name__ == 'UsersTable'
            assert type(world.native_resolution['Files']).__name__ == 'FilesTable'
            assert self.owners[0].P.verify_saved_continuation(case.call, **(case.kwargs | {
                'saved_output': supplied, 'native_saved': packet})) == {
                    case.call['provider']['id']: case.call['verified_cost_scope']}
            assert len(world.native_commands[-1][-1].encode('ascii')) <= 96 * 1024
            assert set(packet) == set(case.kwargs['native_saved'])
            assert set(packet['module_sha256']) == set(case.kwargs['native_saved']['module_sha256'])

    def test_forbidden_missing_and_unresolved_native_file_cannot_return_context_or_read_unowned_storage(self):
        with self.image_case() as (world, case):
            supplied, path = self.stored_image(world, case); original = copy.deepcopy(supplied)
            owned = copy.deepcopy(world.file_rows['native-tool-image'])
            for mode in ('forbidden', 'missing_row', 'missing_file', 'storage_error'):
                with self.subTest(mode=mode):
                    world.file_rows = {'native-tool-image': copy.deepcopy(owned)}
                    world.db_reads.clear(); world.access_queries.clear(); world.failure = None
                    if mode == 'forbidden': world.file_rows['native-tool-image'].user_id = 'foreign-owner'
                    elif mode == 'missing_row': world.file_rows.clear()
                    elif mode == 'missing_file': path.unlink()
                    else: world.file_rows['native-tool-image'].path = None
                    with self.assertRaisesRegex(AssertionError, 'Office Docker topology unavailable .*exec; exit=1; stdout_bytes=0'):
                        self.observe_saved(world, case, supplied)
                    assert world.failure == 'AssertionError' and supplied == original
                    if mode == 'forbidden': assert world.access_queries  # actual native ACL evaluated its query leaves
                    path.write_bytes(case.kwargs['png'])

    def test_wrong_owned_png_bytes_are_rejected_by_existing_full_context_guard(self):
        with self.image_case() as (world, case):
            for mode in ('wrong_bytes', 'empty_image'):
                with self.subTest(mode=mode):
                    supplied, path = self.stored_image(world, case)
                    if mode == 'wrong_bytes':
                        path.write_bytes(case.kwargs['png'][:-1] + bytes([case.kwargs['png'][-1] ^ 1]))
                    else:
                        next(part for item in supplied if item.get('type') == 'function_call_output'
                            for part in item['output'] if part.get('type') == 'input_image')['image_url'] = ''
                    packet = self.observe_saved(world, case, supplied)
                    with self.assertRaises(self.owners[0].P.ProofError):
                        self.owners[0].P.verify_saved_continuation(case.call, **(case.kwargs | {
                            'saved_output': supplied, 'native_saved': packet}))
                    assert packet['saved_output_case']['input_saved_output'] == supplied

    def test_ordinary_native_db_principal_is_required_and_cannot_be_replaced_in_argv(self):
        for mode in ('host_missing', 'host_multiple', 'host_admin', 'db_missing', 'db_admin', 'db_pending',
                     'db_misbound', 'argv_other_user'):
            with self.subTest(mode=mode), self.world() as world:
                if mode == 'host_missing': world.handoff.pop('users'); world.save()
                elif mode == 'host_multiple': world.handoff['users'].append({'id': 'other'}); world.save()
                elif mode == 'host_admin': world.handoff['users'][0]['id'] = world.handoff['admin']['id']; world.save()
                elif mode == 'db_missing': world.user_rows.clear()
                elif mode == 'db_admin': world.user_rows['caller'].role = 'admin'
                elif mode == 'db_pending': world.user_rows['caller'].role = 'pending'
                elif mode == 'db_misbound': world.user_rows['caller'].id = 'foreign'
                else:
                    world.user_rows['other'] = copy.deepcopy(world.user_rows['caller']); world.user_rows['other'].id = 'other'
                    world.payload_mutation = lambda p: p.update(user_id='other')
                with self.assertRaises((AssertionError, ProofError)):
                    world.fixture.native_context(BASE, world.receipt, world.revision, [[]], saved_output=self.saved_output())
                assert len(world.native_commands) == (0 if mode.startswith('host_') else 1)
                if mode == 'argv_other_user': assert not world.db_reads

    def test_external_images_are_refused_before_native_file_or_network_io(self):
        for url in ('https://example.invalid/image.png', 'http://127.0.0.1/private', 'foreign-file-id'):
            with self.subTest(url=url), self.world() as world:
                supplied = self.saved_output(); supplied[2]['output'][1]['image_url'] = url
                with self.assertRaisesRegex(AssertionError, 'Office Docker topology unavailable .*exec; exit=1; stdout_bytes=0'):
                    world.fixture.native_context(BASE, world.receipt, world.revision, [[]], saved_output=supplied)
                assert not world.db_reads and not world.access_queries

    def test_inline_storage_fallback_and_image_free_final_use_no_file_io_and_keep_default_packet(self):
        with self.image_case() as (world, case):
            reasons = [[v for v in c['provider']['response']['output'] if v['type'] == 'reasoning'] for c in case.kwargs['first_calls']]
            original = copy.deepcopy(case.kwargs['saved_output'])
            packet = self.observe_saved(world, case, original)
            final = world.fixture.native_context(BASE, world.receipt, world.revision, reasons,
                saved_output=case.kwargs['first_calls'][-1]['provider']['response']['output'])
            default = world.fixture.native_context(BASE, world.receipt, world.revision, reasons)
            assert packet == case.kwargs['native_saved'] and final == case.kwargs['native_final']
            assert original == case.kwargs['saved_output'] and all(table == 'user' for table, _ in world.db_reads)
            assert len(world.db_reads) == 2 and not world.access_queries
            assert set(default) == {'schema', 'module_sha256', 'source_body_sha256', 'native_specs', 'reasoning_cases'}
            assert set(default['module_sha256']) == {'utils/tools.py', 'routers/openai.py'}
            assert 'user_id' not in json.loads(world.native_commands[-1][-1])

    def test_new_native_resolution_source_mutation_before_or_during_probe_is_rejected(self):
        for name in office.NATIVE_RESOLUTION_SOURCES:
            for moment in ('before_exec', 'during_convert'):
                with self.subTest(module=name, moment=moment), self.world() as world:
                    def change(w): w.path('webui', '/app/backend/open_webui/' + name).write_bytes(b'foreign resolver owner')
                    setattr(world, moment, change)
                    with self.assertRaisesRegex(AssertionError, 'Office Docker topology unavailable .*exec; exit=1; stdout_bytes=0'):
                        world.fixture.native_context(BASE, world.receipt, world.revision, [[]], saved_output=self.saved_output())
                    assert world.failure == 'AssertionError'


class PrepareWorld(DockerWorld):
    """Only Docker is simulated; emitted worker argv runs existing worker.main.

    Existing worker-test owners provide native API leaves inside that simulated
    container. Existing builder/frontend owners provide synthetic image DTOs;
    old readback tests independently execute the actual emitted hash scripts.
    """
    def __init__(self, fixture, root, worker, setup_case, service_case):
        super().__init__(fixture)
        from test_office_compatibility import built_candidate, frontend_owner
        self.worker, self.setup_case, self.service_case = worker, setup_case, service_case
        self.real_run = office.subprocess.run
        self.revision = self.real_run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()
        root.mkdir(parents=True)
        _, self.receipt, running, _, build, package = built_candidate.__wrapped__(root)
        self.receipt['source_commit'] = self.receipt['inputs']['source_commit'] = self.revision
        builder.write(root / 'build-inputs.json', self.receipt['inputs'])
        path = root / 'build-inputs.json'; path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
        identity = builder.sha(path); self.receipt['build_identity'] = identity
        builder.write(build / '_app/version.json', {'version': identity})
        builder.write(package / 'frontend-files.json', builder.manifest(build))
        manifest_sha = builder.sha(package / 'frontend-files.json')
        front = running['webui']['frontend_receipt']
        front.update(build_identity=identity, input_receipt_sha256=identity, build_files_manifest_sha256=manifest_sha)
        builder.write(package / 'frontend-receipt.json', front)
        self.receipt.update(frontend_manifest_sha256=manifest_sha)
        self.receipt['webui'].update(build_hash=identity, version=identity)
        self.running = {name: copy.deepcopy(self.receipt[name]) for name in ('webui', 'office')}
        self.running['webui'].update(frontend_receipt=front, frontend_manifest_sha256=manifest_sha,
            frontend_result=frontend_owner(build, package, identity))
        for name in self.running:
            image = self.receipt['images'][name]['id']
            self.config['services'][name]['image'] = image
            self.rows[self.ids[name]].update(image_ref=image, image_id=image)
        self.verifier = self.git('deploy/openwebui-upgrade-0122/verify_frontend_artifact.py')
        self.pipe = self.git('deploy/openwebui-budgets/service_pipe.py')
        self.pipe_path = root / 'trusted-git-service-pipe.py'; self.pipe_path.write_bytes(self.pipe)
        self.phases, self.provider_reads, self.git_calls = [], 0, []
        self.worker_receipts = []
        self.handoff, self.responses_env, self.after_service = None, 'false', None
        self.extra_inference = self.leak = self.fail_worker = False
        self.providers = {'requests': [{'id': 'prior-native-call', 'body': {'private_context': SECRET}}]}

    def git(self, path):
        return self.real_run(['git', '-c', 'gc.auto=0', 'show', self.revision + ':' + path],
            cwd=ROOT, capture_output=True, check=True).stdout

    def worker_main(self, command):
        import provision_webui as worker_owner
        argv = command[command.index('/proof/provision_webui.py'):]
        argv = [str(self.fixture.private / value.split('/proof-private/', 1)[1])
                if value.startswith('/proof-private/') else value for value in argv]
        output = io.StringIO()
        with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(output): code = worker_owner.main()
        return code, json.loads(output.getvalue())

    def run(self, command, **kwargs):
        if command[:3] == ['git', '-c', 'gc.auto=0']:
            self.git_calls.append(command)
            return self.real_run(command, **kwargs)
        if command[:4] == ['docker', 'image', 'inspect', '--format']:
            return SimpleNamespace(returncode=0, stdout=json.dumps({'id': command[-1], 'os': 'linux', 'architecture': 'amd64'}).encode())
        if command[:3] == ['docker', 'inspect', '--format'] and '"image_ref"' in command[3]:
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.rows[command[-1]]).encode())
        if command[:2] == ['docker', 'exec']:
            name = next(n for n in ('webui', 'office') if command[2] == self.ids[n]); code = command[-1]
            if name == 'office': value = self.running[name]
            elif 'exec(compile' in code: value = self.running[name]['frontend_result']
            else:
                assert 'os.getenv("ENABLE_RESPONSES_API_STATEFUL")' in code
                value = {k: self.running[name][k] for k in ('modules', 'build_hash', 'version', 'frontend_receipt', 'frontend_manifest_sha256')}
                value.update(responses_stateful_env=self.responses_env, verifier_sha256=hashlib.sha256(self.verifier).hexdigest())
            return SimpleNamespace(returncode=0, stdout=json.dumps(value).encode())
        if command[:len(self.fixture.command)] == self.fixture.command:
            tail = command[len(self.fixture.command):]
            if tail[:3] == ['exec', '-T', 'provider']:
                import urllib.request
                self.provider_reads += 1
                data = copy.deepcopy(self.providers)
                if self.extra_inference and self.provider_reads == 2: data['requests'].append({'id': 'forbidden-extra-inference'})
                output = io.StringIO()
                with patch.object(urllib.request, 'urlopen', return_value=io.BytesIO(json.dumps(data).encode())), contextlib.redirect_stdout(output):
                    exec(compile(tail[-1], 'actual-provider-observation', 'exec'), {})
                return SimpleNamespace(returncode=0, stdout=output.getvalue().encode())
            if tail[:2] == ['exec', '-T'] and '--phase' in tail:
                phase = tail[tail.index('--phase') + 1]; self.phases.append(command)
                assert tail[:8] == ['exec', '-T', '--user', '1001:1002', 'proxy', 'python', '-B', '/proof/provision_webui.py']
                assert kwargs['timeout'] == 180
                if self.fail_worker: return SimpleNamespace(returncode=1, stdout=SECRET.encode())
                if phase == 'office-setup':
                    result = []
                    def setup(case):
                        code, safe = self.worker_main(tail); result.append((code, safe)); return code, safe
                    self.worker.fixture = SimpleNamespace(setUp=lambda case: None, setup_phase=setup)
                    self.service_case.setUp(self.worker)
                    self.worker.enterContext(patch.object(self.worker.service, 'SOURCE', self.pipe_path))
                    self.worker.source_fault = self.pipe  # The simulated mount is the same trusted Git blob.
                    code, value = result[0]
                else:
                    code, value = self.worker_main(tail)
                    self.handoff = json.loads((self.fixture.private / 'office-state.private.json').read_bytes())
                    if self.after_service:
                        self.after_service(self.handoff)
                        self.worker.P.write_private(self.fixture.private / 'office-state.private.json', self.handoff)
                if self.leak: value['debug'] = SECRET
                self.worker_receipts.append(copy.deepcopy(value))
                return SimpleNamespace(returncode=code, stdout=json.dumps(value).encode())
        return super().run(command, **kwargs)


class OfficePrepareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_provision_webui import OfficeSetupTests, OfficeServiceSetupTests
        OfficeServiceSetupTests.setUpClass()
        cls.setup_case, cls.service_case = OfficeSetupTests, OfficeServiceSetupTests

    def exercise(self, change=None, revision=None):
        worker = self.service_case()
        self.setup_case.setUp(worker)  # Prepare the simulated container's common native owners only.
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory); fixture = office.OfficeFixture(path / 'env', path / 'output', path / 'config',
                    Path(worker.directory), [SECRET, 'synthetic-admin-token'])
                world = PrepareWorld(fixture, path / 'build', worker, self.setup_case, self.service_case)
                common = (fixture.private / 'webui-state.private.json').read_bytes()
                if change: change(world)
                result = error = None; stdout = io.StringIO()
                with patch.object(office.subprocess, 'run', side_effect=world.run), \
                        patch.object(office.os, 'getuid', return_value=1001, create=True), \
                        patch.object(office.os, 'getgid', return_value=1002, create=True), contextlib.redirect_stdout(stdout):
                    try: result = fixture.prepare(BASE, world.receipt, revision or world.revision)
                    except (AssertionError, ProofError) as caught: error = caught
                self.assertEqual(stdout.getvalue(), '')
                self.assertEqual((fixture.private / 'webui-state.private.json').read_bytes(), common)
                self.assertFalse(fixture.output.exists())
                if error: self.assertNotIn(SECRET, str(error))
                return result, error, world
        finally:
            worker.doCleanups()

    def test_two_actual_worker_entrypoints_full_private_handoff_and_pure_qualification(self):
        result, error, world = self.exercise()
        self.assertIsNone(error, [r.get('failure') for r in world.worker_receipts])
        self.assertEqual(result['status'], 'prepared')
        self.assertFalse(result['native_office_accepted']); self.assertFalse(result['inference_issued'])
        self.assertEqual(result['inference_calls'], 0); self.assertEqual(world.provider_reads, 2)
        self.assertEqual([c[c.index('--phase') + 1] for c in world.phases], ['office-setup', 'office-service-setup'])
        for command in world.phases:
            self.assertEqual(command[len(world.fixture.command):len(world.fixture.command) + 5],
                ['exec', '-T', '--user', '1001:1002', 'proxy'])
        self.assertIn('/proof-private/webui-state.private.json', world.phases[0])
        self.assertIn('/proof-private/office-state.private.json', world.phases[1])
        self.assertEqual(world.handoff['office_service_setup']['stage'], 'readback_ready')
        current = world.handoff['office_service_readback']['current']
        self.assertEqual(current['task_config']['TASK_MODEL_PARAMS']['custom_params']['reasoning']['effort'], 'none')
        self.assertEqual(current['task_config']['TASK_MODEL_PARAMS']['custom_params']['vendor_params']['keep'], ['PRIVATE_TASK_SENTINEL', 2])
        self.assertEqual(current['target_model']['params'], {})
        self.assertEqual(current['function']['content'].replace('\r\n', '\n'), world.pipe.decode().replace('\r\n', '\n'))
        self.assertTrue(any(c[-1] == world.revision + ':deploy/openwebui-budgets/service_pipe.py' for c in world.git_calls))
        public = json.dumps(result)
        for private in (SECRET, 'synthetic-admin-token', 'PRIVATE_TASK_SENTINEL', 'class Pipe:', 'OPENAI_API_KEYS'):
            self.assertNotIn(private, public)

    def test_foreign_revision_and_image_stop_before_any_worker(self):
        for change, revision in ((None, 'f' * 40),
            (lambda w: w.rows[w.ids['office']].update(image_id='sha256:' + 'f' * 64), None)):
            with self.subTest(revision=revision):
                result, error, world = self.exercise(change, revision)
                self.assertIsNone(result); self.assertIsNotNone(error); self.assertEqual(world.phases, [])
                self.assertEqual(world.provider_reads, 0)

    def test_real_private_service_selector_target_source_and_metadata_mutations_fail(self):
        def change(field, value):
            return lambda w: setattr(w, 'after_service', lambda handoff: handoff['office_service_readback']['current'][field].update(value))
        cases = (change('task_config', {'TASK_MODEL': 'gpt-6-luna'}),
            change('target_model', {'params': {'temperature': .9}}),
            change('function', {'content': 'class Pipe:\n    foreign = True\n'}),
            change('workspace_model', {'meta': {'capabilities': {'builtin_tools': True}}}))
        for mutate in cases:
            with self.subTest(mutate=mutate):
                result, error, world = self.exercise(mutate)
                self.assertIsNone(result); self.assertIsNotNone(error); self.assertEqual(len(world.phases), 2)

    def test_actual_reasoning_environment_and_connection_are_not_invented(self):
        cases = (lambda w: setattr(w, 'responses_env', 'true'),
            lambda w: setattr(w, 'after_service', lambda h: h['office_setup']['before']['chat_config'].update(ENABLE_CONTEXT_COMPACTION=True)),
            lambda w: setattr(w, 'after_service', lambda h: h['office_setup']['connections']['OPENAI_API_CONFIGS']['0'].update(api_type='chat')))
        for mutate in cases:
            with self.subTest(mutate=mutate):
                result, error, _ = self.exercise(mutate)
                self.assertIsNone(result); self.assertIsNotNone(error)

    def test_extra_inference_worker_failure_and_public_secret_never_prepare(self):
        for name in ('extra_inference', 'fail_worker', 'leak'):
            with self.subTest(name=name):
                result, error, _ = self.exercise(lambda w: setattr(w, name, True))
                self.assertIsNone(result); self.assertIsNotNone(error)

    def test_private_file_origin_size_and_schema_are_bounded_before_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); private = root / 'private'; private.mkdir()
            fixture = office.OfficeFixture(root / 'env', root / 'output', root / 'config', private, [SECRET])
            outside = root / 'outside.json'; outside.write_bytes(b'{"schema":1}')
            with self.assertRaises(AssertionError): fixture._office_private('../outside.json')
            target = private / 'office-state.private.json'; target.write_bytes(b' ' * (office.MAX_BYTES + 1)); target.chmod(0o600)
            with self.assertRaises(AssertionError): fixture._office_private(target.name)
            target.write_bytes(b'{"schema":true}')
            with self.assertRaises(AssertionError): fixture._office_private(target.name)
            target.write_bytes(b'{"schema":1,"private":"retained only here"}')
            raw, value = fixture._office_private(target.name)
            self.assertEqual(raw, target.read_bytes()); self.assertEqual(value['private'], 'retained only here')
            self.assertFalse(fixture.output.exists())


class DelegatedOfficeConfigTests(unittest.TestCase):
    def test_explicit_scenario_keeps_every_legacy_descriptor_and_setting(self):
        original = (Path(__file__).with_name('litellm_config.yaml')).read_bytes()
        before = yaml.safe_load(office.prepare_usage_guard_config(original))
        after = yaml.safe_load(office.prepare_delegated_office_config(original))
        rows = after.pop('model_list')
        self.assertEqual(rows[:-2], before.pop('model_list'))
        self.assertEqual(after, before)
        self.assertEqual([r['model_name'] for r in rows[-2:]], ['gpt-6.1-sol', 'gpt-6.1-terra'])
        for row, output, rate in zip(rows[-2:], (12000, 6000), (.01, .001)):
            info = row['model_info']
            self.assertIs(info['supports_native_streaming'], False)
            self.assertEqual(info['max_output_tokens'], output)
            self.assertEqual(info['max_tokens'], info['max_input_tokens'] + output)
            self.assertEqual((info['input_cost_per_token'], info['output_cost_per_token']), (rate, 2 * rate))
            self.assertEqual(info['owui_pricing']['deployment_id'], info['id'])

    def test_opt_in_does_not_mutate_global_office_or_pricing_composition(self):
        original = Path(__file__).with_name('litellm_config.yaml').read_bytes()
        frozen = office.prepare_usage_guard_config(original)
        office.prepare_delegated_office_config(original)
        self.assertEqual(office.prepare_usage_guard_config(original), frozen)


if __name__ == '__main__':
    unittest.main()
