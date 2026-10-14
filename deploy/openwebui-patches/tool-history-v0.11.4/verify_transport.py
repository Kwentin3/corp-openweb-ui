"""Exercise installed middleware and provider conversion without provider calls."""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

os.environ['WEBUI_SECRET_KEY'] = 'synthetic-tool-transport-test-key-only'
_data = tempfile.TemporaryDirectory()
os.environ['DATA_DIR'] = _data.name

from open_webui.utils import middleware
from open_webui.routers.openai import convert_to_responses_payload

from apply_transport import ORIGINAL_SHA256, PATCHED_SHA256, apply

IMAGE = 'data:image/png;base64,iVBORw0KGgo='
QUESTION = 'Create a Word document with date and signature fields.'


def history():
    return [
        {'role': 'user', 'content': QUESTION},
        {'role': 'assistant', 'output': [
            {'type': 'function_call', 'name': 'render_office_file',
             'call_id': 'render-1', 'arguments': '{"file_id":"native-file"}', 'status': 'completed'},
            {'type': 'function_call_output', 'call_id': 'render-1', 'output': [
                {'type': 'input_text', 'text': 'Image file read successfully.'},
                {'type': 'input_image', 'image_url': IMAGE},
            ]},
        ]},
    ]


class NativeTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_responses_preserves_tool_image_and_user_intent(self):
        source = history()
        untouched = copy.deepcopy(source)
        connection = AsyncMock(return_value=('https://provider.invalid/v1', 'unused', {'api_type': 'responses'}))
        with patch.object(middleware, 'get_openai_connection', connection):
            flatten = await middleware.should_flatten_tool_images({'owned_by': 'openai', 'urlIdx': 3})
        connection.assert_awaited_once_with(3)
        messages = middleware.process_messages_with_output(source, flatten_tool_images=flatten)
        body = await middleware.convert_url_images_to_base64({'messages': messages})
        body = middleware.normalize_messages_for_model(body)
        final = convert_to_responses_payload(body)
        self.assertEqual(source, untouched)
        self.assertEqual([x for x in final['input'] if x.get('role') == 'user'], [
            {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': QUESTION}]},
        ])
        result = final['input'][-1]
        self.assertEqual(result, {'type': 'function_call_output', 'call_id': 'render-1',
                                 'output': untouched[-1]['output'][-1]['output']})

    async def test_chat_completions_retains_native_image_fallback(self):
        with patch.object(middleware, 'get_openai_connection', AsyncMock(return_value=('', '', {}))):
            flatten = await middleware.should_flatten_tool_images({'owned_by': 'openai', 'urlIdx': 0})
        messages = middleware.process_messages_with_output(history(), flatten_tool_images=flatten)
        self.assertTrue(flatten)
        self.assertEqual(messages[-2]['role'], 'tool')
        self.assertEqual(messages[-2]['content'], 'Image file read successfully.')
        self.assertEqual(messages[-1]['content'][-1]['image_url']['url'], IMAGE)

    async def test_non_openai_models_do_not_resolve_openai_connection(self):
        with patch.object(middleware, 'get_openai_connection', AsyncMock()) as connection:
            self.assertTrue(await middleware.should_flatten_tool_images({'owned_by': 'ollama', 'urlIdx': 0}))
            self.assertTrue(await middleware.should_flatten_tool_images({'id': 'pipe'}))
        connection.assert_not_awaited()

    async def test_replayed_image_precedes_later_edit_without_new_user_message(self):
        source = history()
        source[-1]['output'].extend([
            {'type': 'function_call', 'name': 'apply_office_batch', 'call_id': 'edit-2',
             'arguments': '{}', 'status': 'completed'},
            {'type': 'function_call_output', 'call_id': 'edit-2',
             'output': [{'type': 'input_text', 'text': 'New version created.'}]},
        ])
        final = convert_to_responses_payload({'messages': middleware.process_messages_with_output(
            source, flatten_tool_images=False)})
        self.assertEqual([x['type'] for x in final['input']], [
            'message', 'function_call', 'function_call_output', 'function_call', 'function_call_output'])
        self.assertEqual(final['input'][2]['output'][1]['image_url'], IMAGE)
        self.assertEqual(final['input'][3]['name'], 'apply_office_batch')


class InstallerTests(unittest.TestCase):
    def test_installed_source_is_idempotent_and_unknown_source_fails_closed(self):
        import hashlib
        installed = Path(middleware.__file__).read_bytes()
        self.assertEqual(hashlib.sha256(installed).hexdigest(), PATCHED_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'utils').mkdir()
            target = root / 'utils/middleware.py'
            target.write_bytes(installed)
            apply(root)
            self.assertEqual(target.read_bytes(), installed)
            target.write_bytes(installed + b'\n# drift\n')
            before = target.read_bytes()
            with self.assertRaises(RuntimeError):
                apply(root)
            self.assertEqual(target.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
