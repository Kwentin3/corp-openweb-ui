"""Local launch guards; Docker is a boundary fixture, never executed.

Real files, receipt writes and SQLite checks are exercised. On Windows only the
POSIX file mode/UID metadata is simulated; symlink checks use actual filesystem
links when permitted. These checks do not establish runtime/product acceptance.
"""
from __future__ import annotations

import copy
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch

import launch_stage as launch


class LaunchGuards(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve() / 'task'
        self.root = self.base / 'refresh-1'
        self.root.mkdir(parents=True)
        self.approved = {role: {'Id': role + '-source-id', 'Image': 'sha256:' + str(index) * 64}
                         for index, role in enumerate(launch.SOURCE_ROLES, 1)}
        self.prepared = {
            'phase_root': str(self.root), 'source_container': self.approved['webui']['Id'],
            'source_image': self.approved['webui']['Image'],
            'source_containers': {role: {'id': value['Id'], 'image': value['Image']}
                                  for role, value in self.approved.items()},
            'source_stopped': False, 'booted': False,
            'volumes': {logical: 'openwebui-0122-refresh-1_' + logical
                        for logical in launch.VOLUME_SELECTORS.values()},
        }
        self.env = {key: str(self.root / filename) for key, filename in launch.ENV_SELECTORS.items()}
        self.env.update({key: self.prepared['volumes'][logical]
                         for key, logical in launch.VOLUME_SELECTORS.items()})
        self.metadata_overrides = {}
        native_lstat = Path.lstat
        self.uid = 1000 if os.name == 'nt' else os.geteuid()

        def metadata(path):
            original = native_lstat(path)
            fields = list(original)
            if os.name == 'nt' and stat.S_ISREG(original.st_mode):
                fields[0] = stat.S_IFREG | 0o600
                fields[4] = self.uid
            for field, value in self.metadata_overrides.get(path, {}).items():
                fields[field] = value
            return os.stat_result(fields)

        self.addCleanup(patch.stopall)
        patch.object(launch, 'BASE_ROOT', self.base).start()
        patch.object(launch.os, 'geteuid', return_value=self.uid, create=True).start()
        patch.object(Path, 'lstat', autospec=True, side_effect=metadata).start()
        previous_umask = os.umask(0o077)
        self.addCleanup(os.umask, previous_umask)
        self.write(self.base / 'production-inspect.private.json', json.dumps(self.approved))
        self.write(self.root / 'webui.env', 'ENABLE_RESPONSES_API_STATEFUL=false\nSYNTHETIC_INPUT=fixture\n')
        self.write(self.root / 'stt.env', 'SYNTHETIC_INPUT=fixture\n')
        self.write(self.root / 'terminal.env', 'SYNTHETIC_INPUT=fixture\n')
        self.save_inputs()

    @staticmethod
    def write(path, value):
        path.write_text(value, encoding='utf-8')
        path.chmod(0o600)

    def save_inputs(self):
        self.write(self.root / 'prepared.private.json', json.dumps(self.prepared))
        self.write(self.root / 'compose.env', ''.join(key + '=' + value + '\n' for key, value in self.env.items()))

    def reject_before_docker(self, message):
        self.save_inputs()
        with patch.object(launch.subprocess, 'check_output') as docker, patch.object(launch.subprocess, 'run') as up:
            with self.assertRaisesRegex(RuntimeError, message):
                launch.main('sha256:' + 'a' * 64, self.root)
        docker.assert_not_called()
        up.assert_not_called()
        self.assertFalse((self.root / 'launch-started.private.json').exists())
        self.assertFalse((self.root / 'resolved-candidate.private.json').exists())
        self.assertFalse(json.loads((self.root / 'prepared.private.json').read_text())['booted'])

    def test_new_phase_accepts_its_exact_source_paths_and_volumes(self):
        launch.validate_prepared(self.root, self.prepared, self.approved)
        self.assertEqual(launch.validate_environment(self.root, self.prepared), self.env)

    def test_relocated_receipt_fails_before_docker_or_launch_writes(self):
        self.prepared['phase_root'] = str(self.base / 'qa')
        self.reject_before_docker('different phase root')

    def test_source_identity_changes_fail_before_docker(self):
        original = copy.deepcopy(self.prepared)
        for role in launch.SOURCE_ROLES:
            for field in ('id', 'image'):
                with self.subTest(role=role, field=field):
                    self.prepared = copy.deepcopy(original)
                    self.prepared['source_containers'][role][field] = 'different'
                    self.reject_before_docker('source container/image identities')
        for field in ('source_image', 'source_container'):
            with self.subTest(field=field):
                self.prepared = copy.deepcopy(original)
                self.prepared[field] = 'different'
                self.reject_before_docker('approved source identity')

    def test_each_foreign_env_selector_fails_before_docker(self):
        for key in launch.ENV_SELECTORS:
            with self.subTest(key=key):
                original = self.env[key]
                self.env[key] = str(self.base / 'qa' / 'webui.env')
                self.reject_before_docker('different phase root')
                self.env[key] = original

    def test_each_foreign_volume_selector_fails_before_docker(self):
        for key in launch.VOLUME_SELECTORS:
            with self.subTest(key=key):
                original = self.env[key]
                self.env[key] = 'openwebui-0122-qa_data'
                self.reject_before_docker('differs from the prepared snapshot')
                self.env[key] = original

    def test_each_env_file_requires_private_mode_and_current_owner(self):
        for filename in ('compose.env', *launch.ENV_SELECTORS.values()):
            path = self.root / filename
            for changed in ({0: stat.S_IFREG | 0o644}, {4: self.uid + 1}):
                with self.subTest(filename=filename, metadata=changed):
                    self.metadata_overrides[path] = changed
                    self.reject_before_docker('owned mode-0600 regular file')
                    self.metadata_overrides.clear()

    def test_symlink_env_file_rejected_even_when_target_is_private(self):
        path = self.root / 'stt.env'
        target = self.root / 'stt-original.env'
        path.rename(target)
        try:
            path.symlink_to(target)
        except OSError as error:
            self.skipTest('Host cannot create a symlink: ' + type(error).__name__)
        self.reject_before_docker('without symlinks')

    def test_both_image_identity_overrides_are_rejected_even_if_empty(self):
        for key in ('WEBUI_BUILD_HASH', 'WEBUI_BUILD_CHANNEL'):
            for value in ('', 'old-build'):
                with self.subTest(key=key, value=value):
                    self.write(self.root / 'webui.env', key + '=' + value + '\n')
                    self.reject_before_docker('must not override candidate image build identity')

    def test_duplicate_and_export_style_env_keys_fail_closed(self):
        for value in ('SYNTHETIC_INPUT=a\nSYNTHETIC_INPUT=b\n', 'export SYNTHETIC_INPUT=fixture\n'):
            with self.subTest(value=value):
                self.write(self.root / 'stt.env', value)
                self.reject_before_docker('Unexpected or duplicate raw environment key')

    def test_legacy_requires_original_root_three_defaults_and_source_ids(self):
        legacy = copy.deepcopy(self.prepared)
        legacy.pop('phase_root')
        legacy.pop('source_containers')
        legacy.pop('source_stopped')
        legacy['volumes'] = {logical: 'openwebui-0122_' + logical
                             for logical in launch.VOLUME_SELECTORS.values()}
        launch.validate_prepared(self.base, legacy, self.approved)
        for mutate in ('root', 'volume', 'image', 'id', 'stopped'):
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(legacy)
                root = self.base
                if mutate == 'root':
                    root = self.root
                elif mutate == 'volume':
                    changed['volumes']['stt_data'] = 'openwebui-0122-qa_stt_data'
                elif mutate == 'image':
                    changed['source_image'] = 'different'
                elif mutate == 'id':
                    changed['source_container'] = 'different'
                else:
                    changed['source_stopped'] = True
                with self.assertRaises(RuntimeError):
                    launch.validate_prepared(root, changed, self.approved)

    def test_legacy_env_uses_only_original_default_volumes(self):
        previous_root = self.root
        self.root = self.base
        for key, filename in launch.ENV_SELECTORS.items():
            self.write(self.root / filename, (previous_root / filename).read_text(encoding='utf-8'))
            self.env[key] = str(self.root / filename)
        self.prepared.pop('phase_root')
        for key in launch.VOLUME_SELECTORS:
            self.env.pop(key)
        self.prepared['volumes'] = {logical: 'openwebui-0122_' + logical
                                    for logical in launch.VOLUME_SELECTORS.values()}
        self.save_inputs()
        launch.validate_prepared(self.root, self.prepared, self.approved)
        selected = launch.validate_environment(self.root, self.prepared)
        for key, logical in launch.VOLUME_SELECTORS.items():
            self.assertEqual(selected[key], self.prepared['volumes'][logical])
        self.env['RELEASE_DATA_VOLUME'] = self.prepared['volumes']['data']
        self.save_inputs()
        with self.assertRaisesRegex(RuntimeError, 'native default volume selectors'):
            launch.validate_environment(self.root, self.prepared)

    def test_fresh_launch_pins_selectors_despite_ambient_shell_overrides(self):
        self.exercise_launch_boundary()

    def test_stopped_source_launch_checks_all_four_native_source_owners(self):
        self.prepared['source_stopped'] = True
        self.save_inputs()
        self.exercise_launch_boundary()

    def exercise_launch_boundary(self):
        image_id = 'sha256:' + 'a' * 64
        bindings = {'openwebui-0122': ('data', '/app/backend/data'),
                    'stage2-stt-0122': ('stt_data', '/data/stage2-stt'),
                    'open-terminal-0122': ('terminal_home', '/home')}
        services = {name: {'labels': {'traefik.enable': 'false'},
                           'volumes': [{'type': 'volume', 'source': logical, 'target': target}],
                           'environment': {}}
                    for name, (logical, target) in bindings.items()}
        services['openwebui-0122'].update(image=image_id, ports=[{'host_ip': '127.0.0.1'}],
                                         environment={'ENABLE_RESPONSES_API_STATEFUL': 'false'})
        services['officecli-0122'] = {'labels': {'traefik.enable': 'false'}, 'init': True,
                                     'environment': {'OPENWEBUI_BASE_URL': 'http://openwebui-0122:8080'}}
        config = {'name': 'openwebui-0122', 'services': services,
                  'volumes': {logical: {'name': value} for logical, value in self.prepared['volumes'].items()}}
        resolved = json.dumps(config).encode()
        inspected = []

        def docker(args, **kwargs):
            if args[:3] == ['docker', 'ps', '-aq']:
                return ''
            if args[:2] == ['docker', 'inspect']:
                for role, approved in self.approved.items():
                    if args[2] == approved['Id']:
                        inspected.append(role)
                        return json.dumps([{**approved, 'State': {
                            'Running': not self.prepared['source_stopped'],
                            'Health': {'Status': 'healthy'}}}]).encode()
            if args[:3] == ['docker', 'image', 'inspect']:
                return json.dumps([{'Id': image_id, 'Config': {'Labels': {'corp.upstream.version': '0.12.2',
                    'corp.upstream.commit': '6a18585ff4c2e5f6805f682222cfbc46dc669ef8'}}}]).encode()
            if args[:2] == ['docker', 'compose'] and args[-3:] == ['config', '--format', 'json']:
                self.assertEqual(args[2:4], ['--env-file', str(self.root / 'compose.env')])
                for key, value in self.env.items():
                    self.assertEqual(kwargs['env'][key], value)
                return resolved
            self.fail('Unexpected Docker boundary request: ' + repr(args[:3]))

        database = self.root / 'safety-fixture.sqlite3'
        native_connect = sqlite3.connect
        with closing(native_connect(database)) as connection:
            connection.executescript('CREATE TABLE chat(timer_at INTEGER, meta TEXT);'
                                     'CREATE TABLE calendar_event(id TEXT); CREATE TABLE config(key TEXT, value TEXT);')

        def connect(database_uri, **kwargs):
            self.assertIn(self.prepared['volumes']['data'] + '/_data/webui.db?mode=ro', database_uri)
            connection = native_connect(database)
            self.addCleanup(connection.close)
            return connection

        native_as_uri = Path.as_uri

        def as_uri(path):
            if os.name == 'nt' and path == Path('/var/lib/docker/volumes') / self.prepared['volumes']['data'] / '_data/webui.db':
                return 'file:///var/lib/docker/volumes/' + self.prepared['volumes']['data'] + '/_data/webui.db'
            return native_as_uri(path)

        with patch.dict(os.environ, {key: 'foreign-phase' for key in self.env}), \
                patch.object(launch.subprocess, 'check_output', side_effect=docker), \
                patch.object(launch.subprocess, 'run') as up, \
                patch.object(launch.sqlite3, 'connect', side_effect=connect), \
                patch.object(Path, 'as_uri', autospec=True, side_effect=as_uri), \
                patch('builtins.print'):
            launch.main(image_id, self.root)
        self.assertEqual(set(inspected), set(launch.SOURCE_ROLES))
        self.assertEqual(up.call_args.args[0][-2:], ['up', '-d'])
        self.assertTrue(up.call_args.kwargs['check'])
        self.assertEqual((self.root / 'resolved-candidate.private.json').read_bytes(), resolved)
        saved = json.loads((self.root / 'prepared.private.json').read_text())
        self.assertTrue(saved['booted'])
        self.assertEqual(saved['boot_image_id'], image_id)
        self.assertEqual(json.loads((self.root / 'launch-started.private.json').read_text())['image_id'], image_id)


if __name__ == '__main__':
    unittest.main()
