"""Verify the installed Linux observer using synthetic context and real storage.

Run inside the candidate OpenWebUI image. No provider or database is contacted;
only the existing chat database reader is replaced with synthetic owned rows.
"""
from __future__ import annotations

import ast
import asyncio
import copy
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


# Native env initialization must never use the image's application data.
_ENV_DIRECTORY = tempfile.TemporaryDirectory(prefix='provider-capture-env-')
os.environ['DATA_DIR'] = _ENV_DIRECTORY.name
os.environ['WEBUI_SECRET_KEY'] = 'synthetic-provider-capture-test-only'
from open_webui.env import DATA_DIR
from open_webui.utils import provider_context_capture as capture


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('capture_installer_under_test', HERE / 'apply_capture.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)
INSTALLED_ROUTER = Path(capture.__file__).resolve().parent.parent / 'routers' / 'openai.py'


def identifier():
    return str(uuid.uuid4())


def synthetic_bodies():
    """Representative final bytes, including details earlier hooks can lose."""
    instructions = 'Priority one: preserve facts and tool evidence.\n' * 120
    facts = 'PRIVATE-CAPTURE-BODY: invoice 719; amount 12500 RUB; date 2026-10-29; no missing pages.'
    schema = {'type': 'object', 'properties': {
        'path': {'type': 'string', 'description': 'Exact UTF-8 artifact path'},
        'pages': {'type': 'array', 'items': {'type': 'integer'}}},
        'required': ['path', 'pages'], 'additionalProperties': False}
    image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB'
    cc = {'model': 'provider-model', 'stream': True, 'messages': [
        {'role': 'system', 'content': instructions},
        {'role': 'user', 'content': [{'type': 'text', 'text': facts},
            {'type': 'image_url', 'image_url': {'url': image, 'detail': 'high'}}]},
        {'role': 'assistant', 'content': 'I will inspect both pages.', 'tool_calls': [
            {'id': 'call-719', 'type': 'function', 'function': {
                'name': 'read_artifact', 'arguments': '{"path":"/tmp/счёт.pdf","pages":[1,2]}'}}]},
        {'role': 'tool', 'tool_call_id': 'call-719', 'content': facts + '\nPage 2: paid.'},
        {'role': 'user', 'content': 'Compare the first image and page two; report omissions.'}],
        'tools': [{'type': 'function', 'function': {
            'name': 'read_artifact', 'description': 'Read exact page evidence', 'parameters': schema}}]}
    responses = {'model': 'provider-model', 'stream': False, 'instructions': instructions,
        'input': [
            {'type': 'message', 'role': 'user', 'content': [
                {'type': 'input_text', 'text': facts}, {'type': 'input_image', 'image_url': image}]},
            {'type': 'reasoning', 'id': 'rs_719', 'summary': [], 'encrypted_content': 'opaque+/reasoning==719'},
            {'type': 'function_call', 'id': 'fc_719', 'call_id': 'call-719',
                'name': 'read_artifact', 'arguments': '{"path":"/tmp/счёт.pdf","pages":[1,2]}'},
            {'type': 'function_call_output', 'call_id': 'call-719', 'output': [
                {'type': 'input_text', 'text': facts + '\nPage 2: paid.'},
                {'type': 'input_image', 'image_url': image}]},
            {'type': 'message', 'role': 'user', 'content': [
                {'type': 'input_text', 'text': 'Compare both pages; name every omission.'}]}],
        'tools': [{'type': 'function', 'name': 'read_artifact',
            'description': 'Read exact page evidence', 'parameters': schema, 'strict': False}]}
    return tuple(json.dumps(body, ensure_ascii=False, indent=2) + '\n' for body in (cc, responses))


class CaptureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='provider-capture-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'protected'
        self.root.mkdir(mode=0o700)
        self.chat_id, self.user_id = identifier(), identifier()
        self.config = {'chat_id': self.chat_id, 'run_id': identifier(),
            'expires_at': time.time() + 300, 'max_requests': 4, 'max_bytes': 1024 * 1024,
            'include_tasks': [], 'include_native_subagents': False}
        self.metadata = {'chat_id': self.chat_id, 'message_id': identifier()}
        self.rows = {self.chat_id: SimpleNamespace(id=self.chat_id, user_id=self.user_id, meta={})}
        self.db = AsyncMock(side_effect=self.lookup)
        self.db_patch = patch.object(capture, '_get_chat', self.db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.payload = synthetic_bodies()[0]

    async def lookup(self, chat_id):
        await asyncio.sleep(0)  # Exercise suspension across concurrent owner lookups.
        return self.rows.get(chat_id)

    def enable(self):
        path = self.root / 'capture.json'
        path.write_text(json.dumps(self.config), encoding='utf-8')
        path.chmod(0o600)

    async def record(self, metadata=None, payload=None, **kwargs):
        return await capture.capture_provider_context(
            self.metadata if metadata is None else metadata,
            self.payload if payload is None else payload,
            'https://secret-user:secret-key@provider.invalid/v1/chat/completions?api-key=secret-query',
            root=self.root, selected_model='workspace-model', user_id=self.user_id, **kwargs)

    def requests(self):
        return sorted(self.root.glob('*/*.request.json'))

    def child(self, parent, *, owner=None, meta=None):
        child_id = identifier()
        self.rows[child_id] = SimpleNamespace(id=child_id,
            user_id=owner or self.user_id, meta=meta if meta is not None else {
                'internal': True, 'type': 'subagent', 'parent_chat_id': parent,
                'delegation_id': identifier()})
        return child_id

    async def test_disabled_never_creates_storage_or_calls_database(self):
        absent = self.root / 'absent'
        self.assertIsNone(await capture.capture_provider_context(
            self.metadata, self.payload, 'https://provider.invalid', root=absent,
            user_id=self.user_id))
        self.assertFalse(absent.exists())
        self.assertIsNone(await self.record())
        self.assertEqual(list(self.root.iterdir()), [])
        self.db.assert_not_awaited()

    async def test_complete_cc_and_responses_preserved_byte_for_byte(self):
        self.enable()
        original = copy.deepcopy(self.metadata)
        for index, body in enumerate(synthetic_bodies(), 1):
            with self.subTest(protocol=index):
                receipt = await self.record(payload=body)
                self.assertIsInstance(receipt, dict)
                path = self.root / self.config['run_id'] / f'{index:03}.request.json'
                self.assertEqual(path.read_bytes(), body.encode('utf-8'))
                self.assertEqual(receipt['sha256'], hashlib.sha256(body.encode('utf-8')).hexdigest())
                self.assertEqual(receipt['bytes'], len(body.encode('utf-8')))
                self.assertEqual(receipt['selected_model'], 'workspace-model')
                self.assertEqual(receipt['provider_model'], 'provider-model')
                self.assertEqual((receipt['host'], receipt['path']),
                                 ('provider.invalid', '/v1/chat/completions'))
                self.assertEqual(receipt['agent_kind'], 'main')
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
                receipt_path = path.with_name(f'{index:03}.receipt.json')
                self.assertEqual(json.loads(receipt_path.read_text()), receipt)
                self.assertEqual(stat.S_IMODE(receipt_path.stat().st_mode), 0o600)
                self.assertNotIn('secret-', json.dumps(receipt))
        self.assertEqual(self.metadata, original)
        self.assertEqual(Path(DATA_DIR), Path(_ENV_DIRECTORY.name))

    async def test_chat_owner_and_explicit_task_scope(self):
        self.enable()
        self.assertIsNone(await self.record({'chat_id': identifier()}))
        self.db.assert_not_awaited()
        self.rows[self.chat_id].user_id = identifier()
        self.assertIsNone(await self.record())
        self.rows[self.chat_id].user_id = self.user_id
        community = {**self.metadata, 'task': 'sub_agent', 'sub_agent_iteration': 2}
        self.assertIsNone(await self.record(community))
        self.config['include_tasks'] = ['sub_agent']
        self.enable()
        receipt = await self.record(community)
        self.assertEqual(receipt['agent_kind'], 'community_subagent')
        self.assertEqual(receipt['sub_agent_iteration'], 2)
        for task in ('title_generation', 'tags_generation', 'sub_agent_summary'):
            self.assertIsNone(await self.record({**self.metadata, 'task': task}))
        self.assertEqual(len(self.requests()), 1)

    async def test_native_lineage_is_owned_database_state(self):
        self.config['include_native_subagents'] = True
        self.enable()
        child = self.child(self.chat_id)
        grandchild = self.child(child)
        receipt = await self.record({'chat_id': grandchild, 'message_id': identifier()})
        self.assertEqual(receipt['agent_kind'], 'native_subagent')
        self.assertEqual(receipt['lineage_depth'], 2)
        self.assertEqual(receipt['parent_chat_id'], child)
        self.assertEqual(receipt['delegation_id'], self.rows[grandchild].meta['delegation_id'])
        self.assertEqual(receipt['scope_chat_id'], self.chat_id)
        self.assertEqual(receipt['chat_id'], grandchild)
        forged = self.child(self.chat_id, meta={})
        self.assertIsNone(await self.record({'chat_id': forged,
            'parent_chat_id': self.chat_id, 'internal': True, 'type': 'subagent'}))
        self.rows[child].user_id = identifier()
        self.assertIsNone(await self.record({'chat_id': grandchild}))
        self.assertEqual(len(self.requests()), 1)

    async def test_native_opt_in_cycles_and_depth_are_bounded(self):
        child = self.child(self.chat_id)
        self.enable()
        self.assertIsNone(await self.record({'chat_id': child}))
        self.db.assert_not_awaited()
        self.config['include_native_subagents'] = True
        self.enable()
        self.rows[child].meta['parent_chat_id'] = child
        self.assertIsNone(await self.record({'chat_id': child}))
        current = self.chat_id
        for _ in range(8):
            current = self.child(current)
        self.assertEqual((await self.record({'chat_id': current}))['lineage_depth'], 8)
        too_deep = self.child(current)
        self.assertIsNone(await self.record({'chat_id': too_deep}))
        self.assertEqual(len(self.requests()), 1)

    async def test_stateful_receipt_describes_delta_without_reconstructing_context(self):
        self.enable()
        body = json.dumps({'model': 'provider-model', 'previous_response_id': 'resp_prior',
            'input': [{'type': 'function_call_output', 'call_id': 'call-719', 'output': 'paid'}]})
        receipt = await self.record(payload=body)
        self.assertTrue(receipt['previous_response_id_present'])
        self.assertEqual(receipt['provider_state'], 'outbound_delta')
        self.assertEqual(self.requests()[0].read_bytes(), body.encode())

    async def test_expiry_count_and_aggregate_byte_budgets(self):
        self.config['expires_at'] = time.time() - 1
        self.enable()
        self.assertIsNone(await self.record())
        self.db.assert_not_awaited()
        self.config.update(expires_at=time.time() + 300, max_requests=2)
        self.enable()
        self.assertEqual((await self.record())['round'], 1)
        self.assertEqual((await self.record())['round'], 2)
        self.assertIsNone(await self.record())
        self.config.update(run_id=identifier(), max_requests=4,
                           max_bytes=len(self.payload.encode('utf-8')) * 2 - 1)
        self.enable()
        self.assertIsNotNone(await self.record())
        self.assertIsNone(await self.record())
        self.assertEqual(len(list((self.root / self.config['run_id']).glob('*.request.json'))), 1)

    async def test_invalid_configuration_and_external_failures_are_isolated(self):
        self.enable()
        for change in ({'max_requests': 21}, {'max_bytes': 0}, {'expires_at': float('nan')},
                       {'expires_at': time.time() + 7200}, {'include_tasks': 'sub_agent'}):
            saved = dict(self.config)
            self.config.update(change)
            self.enable()
            self.assertIsNone(await self.record())
            self.config = saved
        (self.root / 'capture.json').write_text('{invalid', encoding='utf-8')
        self.assertIsNone(await self.record())
        self.enable()
        self.db.side_effect = RuntimeError('PRIVATE-DB-ERROR')
        with self.assertLogs(capture.log, level='WARNING') as logs:
            self.assertIsNone(await self.record())
        self.assertNotIn('PRIVATE-DB-ERROR', ''.join(logs.output))
        self.db.side_effect = self.lookup
        with patch.object(capture.time, 'time', side_effect=RuntimeError('PRIVATE-CLOCK-ERROR')):
            self.assertIsNone(await self.record())
        self.assertEqual(self.requests(), [])

    async def test_control_change_during_owner_lookup_prevents_stale_capture(self):
        self.enable()
        async def disable_during_lookup(chat_id):
            (self.root / 'capture.json').unlink()
            return self.rows.get(chat_id)
        self.db.side_effect = disable_during_lookup
        self.assertIsNone(await self.record())
        self.assertEqual(self.requests(), [])

    async def test_symlinks_and_unprotected_files_are_rejected(self):
        self.enable()
        self.root.chmod(0o755)
        self.assertIsNone(await self.record())
        self.root.chmod(0o700)
        config_path = self.root / 'capture.json'
        config_path.chmod(0o644)
        self.assertIsNone(await self.record())
        config_path.chmod(0o600)
        target = self.root / 'real-config.json'
        config_path.rename(target)
        config_path.symlink_to(target)
        self.assertIsNone(await self.record())
        config_path.unlink()
        target.rename(config_path)
        outside = Path(self.temporary.name) / 'outside'
        outside.mkdir(mode=0o700)
        run = self.root / self.config['run_id']
        run.symlink_to(outside, target_is_directory=True)
        self.assertIsNone(await self.record())
        self.assertEqual(list(outside.iterdir()), [])
        run.unlink()
        self.assertIsNotNone(await self.record())
        request = run / '001.request.json'
        request.unlink()
        request.symlink_to(target)
        self.assertIsNone(await self.record())
        self.assertFalse((run / '002.request.json').exists())

    async def test_concurrent_captures_share_global_count_and_byte_budgets(self):
        # Independent event loops/threads and agent kinds share the actual flock store.
        child = self.child(self.chat_id)
        identities = [self.metadata, {**self.metadata, 'task': 'sub_agent'}, {'chat_id': child}]
        self.config.update(include_tasks=['sub_agent'], include_native_subagents=True)
        size = len(self.payload.encode('utf-8'))
        for count_budget, byte_budget in ((3, size * 20), (20, size * 3)):
            with self.subTest(max_requests=count_budget, max_bytes=byte_budget):
                self.config.update(run_id=identifier(), max_requests=count_budget, max_bytes=byte_budget)
                self.enable()
                def worker(index):
                    return asyncio.run(self.record(identities[index % len(identities)]))
                with ThreadPoolExecutor(max_workers=8) as workers:
                    receipts = list(workers.map(worker, range(16)))
                accepted = [receipt for receipt in receipts if receipt is not None]
                paths = sorted((self.root / self.config['run_id']).glob('*.request.json'))
                self.assertEqual(sorted(receipt['round'] for receipt in accepted), [1, 2, 3])
                self.assertEqual(len(paths), 3)
                self.assertEqual(sum(path.stat().st_size for path in paths), size * 3)
                for path in paths:
                    self.assertEqual(path.read_bytes(), self.payload.encode('utf-8'))

    def cli(self, *args, successful=True):
        result = subprocess.run([sys.executable, '-m', 'open_webui.utils.provider_capture_control',
            '--root', str(self.root), *args], text=True, capture_output=True,
            timeout=30, env=os.environ.copy())
        self.assertEqual(result.returncode == 0, successful, result.stderr)
        self.assertNotIn('PRIVATE-CAPTURE-BODY', result.stdout + result.stderr)
        return json.loads(result.stdout) if successful else result

    async def test_installed_cli_enable_status_disable_keeps_evidence(self):
        initial = self.cli('status')
        self.assertFalse(initial['enabled'])
        armed = self.cli('enable', '--chat-id', self.chat_id, '--include-task', 'sub_agent',
            '--include-native-subagents', '--max-requests', '2', '--max-bytes', '100000',
            '--ttl-seconds', '120')
        self.assertTrue(armed['enabled'])
        self.config = armed['config']
        self.assertEqual(stat.S_IMODE((self.root / 'capture.json').stat().st_mode), 0o600)
        self.cli('enable', '--chat-id', self.chat_id, successful=False)
        receipt = await self.record()
        path = self.requests()[0]
        raw = path.read_bytes()
        receipt_path = path.with_name('001.receipt.json')
        tampered = {**receipt, 'body': 'PRIVATE-CAPTURE-BODY', 'authorization': 'PRIVATE-CREDENTIAL'}
        receipt_path.write_text(json.dumps(tampered), encoding='utf-8')
        status = self.cli('status')
        self.assertEqual((status['count'], status['bytes']), (1, len(raw)))
        self.assertNotIn('body', status['receipts'][0])
        self.assertNotIn('authorization', status['receipts'][0])
        self.assertNotIn('PRIVATE-CREDENTIAL', json.dumps(status))
        self.assertFalse(self.cli('disable')['enabled'])
        self.assertFalse(self.cli('status')['enabled'])
        self.assertFalse((self.root / 'capture.json').exists())
        self.assertEqual(path.read_bytes(), raw)
        self.assertIsNone(await self.record())


class InstalledRouterTests(unittest.TestCase):
    def test_exact_installed_artifact_and_ast_final_send_boundary(self):
        source = INSTALLED_ROUTER.read_bytes()
        self.assertIn(hashlib.sha256(source).hexdigest(), installer.SUPPORTED.values())
        module = ast.parse(source)
        function = next(node for node in module.body if isinstance(node, ast.AsyncFunctionDef)
                        and node.name == 'generate_chat_completion')
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
        hooks = [node for node in calls if isinstance(node.func, ast.Name)
                 and node.func.id == 'capture_provider_context']
        self.assertEqual(len(hooks), 1)
        hook = hooks[0]
        send = next(node for node in calls if isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == 'session' and node.func.attr == 'request')
        assignments = [node for node in ast.walk(function) if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == 'payload' for target in node.targets)
            and node.lineno < send.lineno]
        last = max(assignments, key=lambda node: node.lineno)
        self.assertEqual(ast.unparse(last.value), 'JSONCodec.dumps(payload)')
        self.assertLess(last.lineno, hook.lineno)
        self.assertLess(hook.lineno, send.lineno)
        self.assertEqual([ast.unparse(arg) for arg in hook.args], ['metadata', 'payload', 'request_url'])
        self.assertEqual({item.arg: ast.unparse(item.value) for item in hook.keywords},
                         {'selected_model': "form_data.get('model')", 'user_id': 'user.id'})
        self.assertTrue(any(isinstance(node, ast.Await) and node.value is hook for node in ast.walk(function)))
        self.assertEqual(next(ast.unparse(item.value) for item in send.keywords if item.arg == 'data'), 'payload')
        self.assertEqual(next(ast.unparse(item.value) for item in send.keywords if item.arg == 'url'), 'request_url')

    def test_installer_checks_real_source_idempotently_and_rejects_drift_without_write(self):
        with tempfile.TemporaryDirectory(prefix='capture-installer-') as temporary:
            root = Path(temporary)
            (root / 'routers').mkdir()
            path = root / 'routers' / 'openai.py'
            installed = INSTALLED_ROUTER.read_bytes()
            path.write_bytes(installed)
            installer.apply(root, check=True)
            installer.apply(root)
            self.assertEqual(path.read_bytes(), installed)
            # Reverse the one admitted overlay, then test actual check/apply bytes.
            original = installed.replace(installer.IMPORT +
                b'from open_webui.utils.provider_context_capture import capture_provider_context\n',
                installer.IMPORT).replace(installer.SERIALIZE + installer.HOOK, installer.SERIALIZE)
            self.assertIn(hashlib.sha256(original).hexdigest(), installer.SUPPORTED)
            path.write_bytes(original)
            installer.apply(root, check=True)
            self.assertEqual(path.read_bytes(), original)
            installer.apply(root)
            self.assertEqual(path.read_bytes(), installed)
            drifted = installed + b'\n# unexpected artifact drift\n'
            path.write_bytes(drifted)
            for check in (True, False):
                with self.assertRaises(RuntimeError):
                    installer.apply(root, check=check)
                self.assertEqual(path.read_bytes(), drifted)


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        _ENV_DIRECTORY.cleanup()
