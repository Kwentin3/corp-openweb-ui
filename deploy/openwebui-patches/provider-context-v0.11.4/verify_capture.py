"""Exercise the installed observer with complete synthetic multimodal input."""
import copy
import hashlib
import json
import os
import stat
import tempfile
import time
import unittest
import uuid
from pathlib import Path

os.environ['WEBUI_SECRET_KEY'] = 'synthetic-provider-capture-test-only'
from open_webui.utils.provider_context_capture import capture_provider_context


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = {'chat_id': 'authorized-chat', 'run_id': str(uuid.uuid4()),
                       'expires_at': time.time() + 300, 'max_requests': 2}
        self.metadata = {'chat_id': 'authorized-chat', 'message_id': 'assistant-id'}
        self.payload = json.dumps({'model': 'test-model', 'reasoning_effort': 'none',
            'messages': [{'role': 'system', 'content': 'guide\n' * 10000},
                         {'role': 'user', 'content': [
                             {'type': 'text', 'text': 'Check the artifact'},
                             {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,AAAA'}}]}],
            'tools': [{'type': 'function', 'function': {'name': 'read_file', 'parameters': {'type': 'object'}}}]})

    def enable(self):
        (self.root / 'capture.json').write_text(json.dumps(self.config))

    def capture(self, metadata=None):
        return capture_provider_context(self.metadata if metadata is None else metadata, self.payload,
                                        'https://provider.invalid/v1/chat/completions', root=self.root)

    def test_disabled_and_other_chat_have_no_capture(self):
        self.assertIsNone(self.capture())
        self.enable()
        self.assertIsNone(self.capture({'chat_id': 'other-chat'}))
        self.assertIsNone(self.capture({**self.metadata, 'task': 'title_generation'}))
        self.assertEqual(list(self.root.glob('*/*.request.json')), [])

    def test_exact_complete_body_and_metadata_are_preserved(self):
        self.enable()
        saved = copy.deepcopy(self.metadata)
        receipt = self.capture()
        path = self.root / self.config['run_id'] / '001.request.json'
        self.assertEqual(path.read_bytes(), self.payload.encode())
        self.assertEqual(receipt['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(self.metadata, saved)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        self.assertEqual(set(receipt), {'captured_at', 'chat_id', 'message_id', 'round', 'host', 'path', 'bytes', 'sha256'})

    def test_expiry_count_and_size_limits(self):
        self.enable()
        self.assertEqual(self.capture()['round'], 1)
        self.assertEqual(self.capture()['round'], 2)
        self.assertIsNone(self.capture())
        self.config['run_id'] = str(uuid.uuid4())
        self.config['expires_at'] = time.time() - 1
        self.enable()
        self.assertIsNone(self.capture())
        self.config.update(expires_at=time.time() + 300, max_bytes=1)
        self.enable()
        self.assertIsNone(self.capture())

    def test_invalid_configuration_does_not_break_request(self):
        (self.root / 'capture.json').write_text('{invalid')
        self.assertIsNone(self.capture())


if __name__ == '__main__':
    unittest.main()
