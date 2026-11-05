"""Actual inherited topology methods with only external Docker IO doubled."""
import ast
import contextlib
import copy
from datetime import datetime
import io
import json
import hashlib
import os
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

import yaml
import office_fixture as office
import build_office_profile as builder
from prove_pricing_browser import PricingFixture, ROOT
from prove_native_budgets import ProofError

SERVICES = ('proxy', 'postgres', 'provider', 'redis', 'webui', 'office')
SECRET = 'synthetic-private-config-must-not-be-exported'
BASE = 'http://172.29.0.6:8080'


class OfficeConfigTests(unittest.TestCase):
    def original(self):
        return (ROOT / 'scripts/goal584-budget-proof/litellm_config.yaml').read_bytes()

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
            if command[3] == '{{json .NetworkSettings.Networks}}': value = self.rows[self.ids['webui']]['networks']
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


if __name__ == '__main__':
    unittest.main()
