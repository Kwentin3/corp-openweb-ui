"""Focused operator contract tests; no production or oikb network operations."""
import copy
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

SPEC = importlib.util.spec_from_file_location('portal_help_sync', Path(__file__).parents[1] / 'sync-portal-help.py')
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class NativeAPI:
    def __init__(self, content):
        self.original = content
        self.posts = []
        self.skill = None
        self.files = {}
        self.reject_update = False

    def request(self, method, path, payload=None, **kwargs):
        if method == 'POST':
            self.posts.append((path, copy.deepcopy(payload)))
            if path.endswith('/sync/diff'):
                return {'unmodified_count': 1}
            if path.startswith('/skills/'):
                if self.reject_update:
                    raise sync.ContractError('Native POST failed with HTTP 409; inspect state before retry')
                self.skill = {**payload, 'user_id': 'owner', 'write_access': True, 'version_id': 'v2',
                              'content': next(f['content'] for f in payload['files'] if f['path'] == 'SKILL.md')}
                self.files = {f['path']: f['content'] for f in payload['files']}
                return self.skill
            raise AssertionError(path)
        if path == '/auths/':
            return {'id': 'owner'}
        if path == '/knowledge/kb':
            return {'id': 'kb', 'description': sync.MARKER, 'write_access': True, 'access_grants': sync.GRANTS}
        if path.startswith('/knowledge/kb/files?'):
            return {'items': [{'id': 'native-file', 'filename': 'help.md'}], 'total': 1}
        if path == '/files/native-file':
            return {'id': 'native-file', 'filename': 'help.md', 'data': {'status': 'completed', 'content': '# Actual document'}}
        if path == '/files/native-file/content':
            return self.original
        if path == '/skills/id/help':
            return self.skill
        if path.startswith('/skills/id/help/files?'):
            return {'version_id': self.skill['version_id'], 'files': [{'path': p} for p in self.files]}
        if path.startswith('/skills/id/help/files/content?'):
            query = sync.urllib.parse.parse_qs(sync.urllib.parse.urlsplit(path).query)
            return self.files[query['path'][0]].encode('utf-8')
        raise AssertionError((method, path))


class SyncContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.data = b'# Source title\n\nCanonical fact.\n'
        self.skill_content = '---\ndescription: "Specific prompt discovery"\n---\n' + sync.MARKER + '\nUse the index.\n'
        (self.root / 'skill.md').write_text(self.skill_content, encoding='utf-8')
        (self.root / 'token').write_text('private-token', encoding='utf-8')
        self.args = SimpleNamespace(source_dir=self.source, skill_source=self.root / 'skill.md',
                                    token_file=self.root / 'token', url='http://example.invalid',
                                    knowledge_id='kb', skill_id='help', oikb='unused', dry_run=False)

    def invoke(self, api):
        return sync.execute(self.args, api_factory=lambda *_: api, sync=lambda *_: None)

    def test_empty_source_fails_before_api_or_mutation(self):
        def forbidden(*args):
            self.fail('Empty source reached external state')
        with self.assertRaisesRegex(sync.ContractError, 'Empty'):
            sync.execute(self.args, api_factory=forbidden, sync=forbidden)

    def test_changed_native_original_blocks_skill_publication(self):
        (self.source / 'help.md').write_bytes(self.data)
        api = NativeAPI(b'# Different native document\n')
        with self.assertRaisesRegex(sync.ContractError, 'hash differs'):
            self.invoke(api)
        self.assertFalse(api.posts, 'Unverified original must not publish any Skill/index')

    def test_dry_run_only_uses_nonmutating_diff_and_does_not_publish(self):
        (self.source / 'help.md').write_bytes(self.data)
        self.args.dry_run = True
        api = NativeAPI(b'Not yet synced')
        result = self.invoke(api)
        self.assertEqual(result['status'], 'dry-run')
        self.assertFalse(result['skill_published'])
        self.assertIn('planned_changes', result)
        self.assertEqual([path for path, _ in api.posts], ['/knowledge/kb/sync/diff'])
        self.assertIsNone(api.skill)

    def test_index_is_pointer_only_noop_and_cas_conflict_is_not_retried(self):
        (self.source / 'help.md').write_bytes(self.data)
        api = NativeAPI(self.data)
        result = self.invoke(api)
        self.assertTrue(result['skill_published'])
        self.assertIn('native-file', api.files[sync.INDEX])
        self.assertIn(sync.sha(self.data), api.files[sync.INDEX])
        self.assertNotIn('Canonical fact', api.files[sync.INDEX])
        self.assertEqual(api.skill['description'], 'Specific prompt discovery')
        api.posts.clear()
        self.assertFalse(self.invoke(api)['skill']['changed'])
        self.assertFalse(any(p.startswith('/skills/') for p, _ in api.posts))
        api.reject_update = True
        api.posts.clear()
        changed = self.skill_content + 'Changed instructions.\n'
        with self.assertRaisesRegex(sync.ContractError, '409'):
            sync.publish_skill(api, 'help', 'owner', changed, api.files[sync.INDEX], api.skill)
        self.assertEqual(len(api.posts), 1)
        self.assertEqual(api.posts[0][1]['expected_version_id'], 'v2')
        self.assertEqual(api.files['SKILL.md'], self.skill_content)


if __name__ == '__main__':
    unittest.main()
