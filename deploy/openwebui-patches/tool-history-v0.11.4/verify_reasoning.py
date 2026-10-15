"""Check the installed native serialization seam without server startup or I/O."""
from __future__ import annotations

import ast
import copy
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

os.environ['WEBUI_SECRET_KEY'] = 'synthetic-reasoning-transport-test-key-only'

from open_webui.utils import misc
from apply_reasoning import ORIGINAL, PATCHED, apply


def load_native_functions():
    """Compile the exact installed pure functions, bypassing unrelated ML/DB boot."""
    namespace = dict(vars(misc))
    namespace['get_openai_connection'] = AsyncMock()
    root = Path(misc.__file__).parents[1]
    for filename, names in [
        ('utils/middleware.py', {'get_reasoning_format', 'get_output_message_options',
                                'strip_reasoning_details', 'process_messages_with_output',
                                'sanitize_tool_pairs', 'normalize_messages_for_model'}),
        ('routers/openai.py', {'RESPONSES_ALLOWED_FIELDS', '_normalize_stored_item',
                              'convert_to_responses_payload'}),
    ]:
        path = root / filename
        tree = ast.parse(path.read_text())
        selected = [node for node in tree.body if getattr(node, 'name', None) in names
                    or isinstance(node, ast.AnnAssign) and getattr(node.target, 'id', None) in names]
        if len(selected) != len(names):
            raise AssertionError(f'Native functions changed: {filename}')
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace, root


NATIVE, ROOT = load_native_functions()
IMAGE = 'data:image/png;base64,iVBORw0KGgo='
QUESTION = 'Format the prepared text as a Word document with date and signature fields.'
REASONING = {'type': 'reasoning', 'id': 'rs_original', 'summary': [], 'content': [],
             'encrypted_content': 'opaque-original-reasoning', 'status': 'completed',
             'started_at': 100, 'ended_at': 101, 'duration': 1}


def output():
    return [copy.deepcopy(REASONING),
            {'type': 'function_call', 'call_id': 'render-1', 'name': 'render_office_file',
             'arguments': '{"file_id":"native-file"}', 'status': 'completed'},
            {'type': 'function_call_output', 'call_id': 'render-1', 'output': [
                {'type': 'input_text', 'text': 'Rendered selected file.'},
                {'type': 'input_image', 'image_url': IMAGE}]},
            {**copy.deepcopy(REASONING), 'id': 'rs_second'},
            {'type': 'message', 'role': 'assistant', 'content': [
                {'type': 'output_text', 'text': 'The document is ready.'}]}]


def provider_payload(items, **options):
    messages = [{'role': 'user', 'content': QUESTION},
                {'role': 'assistant', 'output': items}]
    messages = NATIVE['process_messages_with_output'](messages, **options)
    messages = NATIVE['sanitize_tool_pairs'](messages)
    payload = NATIVE['normalize_messages_for_model']({'messages': messages})
    return NATIVE['convert_to_responses_payload'](payload)


class ReasoningTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_connection_selects_responses_once(self):
        connection = AsyncMock(return_value=('', '', {'api_type': 'responses'}))
        NATIVE['get_openai_connection'] = connection
        options = await NATIVE['get_output_message_options']({'id': 'model', 'owned_by': 'openai', 'urlIdx': 4})
        connection.assert_awaited_once_with(4)
        self.assertEqual(options, {'reasoning_format': 'responses', 'flatten_tool_images': False})

    async def test_other_providers_keep_their_native_representation(self):
        NATIVE['get_openai_connection'] = AsyncMock(return_value=('', '', {}))
        self.assertEqual(await NATIVE['get_output_message_options']({'owned_by': 'ollama'}),
                         {'reasoning_format': 'thinking', 'flatten_tool_images': True})
        self.assertEqual(await NATIVE['get_output_message_options']({'provider': 'llama.cpp', 'urlIdx': 2}),
                         {'reasoning_format': 'reasoning_content', 'flatten_tool_images': True})
        self.assertEqual(await NATIVE['get_output_message_options']({'urlIdx': 2}),
                         {'reasoning_format': None, 'flatten_tool_images': True})

    def test_replay_keeps_opaque_reasoning_order_images_and_user_intent(self):
        items = output()
        untouched = copy.deepcopy(items)
        final = provider_payload(items, reasoning_format='responses', flatten_tool_images=False)
        self.assertEqual(items, untouched)
        self.assertEqual([x['type'] for x in final['input']],
                         ['message', 'reasoning', 'function_call', 'function_call_output', 'reasoning', 'message'])
        self.assertEqual(final['input'][1], {k: REASONING[k] for k in
                         ('type', 'id', 'summary', 'content', 'encrypted_content')})
        self.assertEqual(final['input'][3]['output'][1]['image_url'], IMAGE)
        self.assertEqual([x for x in final['input'] if x.get('role') == 'user'],
                         [{'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': QUESTION}]}])

    def test_foreign_model_output_drops_bound_reasoning_at_existing_guard(self):
        items = output()
        items[0]['reasoning_details'] = [{'type': 'reasoning.encrypted', 'data': 'foreign'}]
        stripped = NATIVE['strip_reasoning_details'](items)
        self.assertNotIn('encrypted_content', stripped[0])
        self.assertNotIn('reasoning_details', stripped[0])
        self.assertIn('encrypted_content', items[0])
        final = provider_payload(stripped, reasoning_format='responses', flatten_tool_images=False)
        self.assertFalse(any(x['type'] == 'reasoning' for x in final['input']))
        self.assertEqual([x['call_id'] for x in final['input'] if x['type'] == 'function_call'], ['render-1'])

    def test_chat_completions_never_receives_opaque_reasoning(self):
        messages = misc.convert_output_to_messages(output(), raw=True, flatten_tool_images=True)
        self.assertFalse(any('output' in x or 'encrypted_content' in x for x in messages))
        self.assertEqual(messages[-2]['role'], 'user')
        self.assertEqual(messages[-2]['content'][-1]['image_url']['url'], IMAGE)

    def test_incomplete_call_is_not_reintroduced(self):
        items = output()
        items.append({'type': 'function_call', 'call_id': 'unfinished', 'name': 'edit',
                      'arguments': '{}', 'status': 'in_progress'})
        final = provider_payload(items, reasoning_format='responses', flatten_tool_images=False)
        self.assertNotIn('unfinished', [x.get('call_id') for x in final['input']])

    def test_display_only_conversion_does_not_expose_opaque_content(self):
        messages = misc.convert_output_to_messages([REASONING], raw=False, reasoning_format='responses')
        self.assertEqual(messages, [])


class InstallerTests(unittest.TestCase):
    def test_installed_sources_are_exact_and_reapplication_is_idempotent(self):
        before = {name: (ROOT / name).read_bytes() for name in PATCHED}
        for name, data in before.items():
            self.assertEqual(hashlib.sha256(data).hexdigest(), PATCHED[name])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, data in before.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(data)
            apply(root)
            self.assertEqual(before, {name: (root / name).read_bytes() for name in before})
            target = root / 'routers/openai.py'
            target.write_bytes(before['routers/openai.py'] + b'\n# source drift\n')
            dirty = {name: (root / name).read_bytes() for name in before}
            with self.assertRaises(RuntimeError):
                apply(root)
            self.assertEqual(dirty, {name: (root / name).read_bytes() for name in dirty})


if __name__ == '__main__':
    unittest.main()
