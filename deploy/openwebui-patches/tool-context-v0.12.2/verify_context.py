"""Exercise exact installed converters without a server, DB or provider request."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from apply_context import ORIGINAL, PATCHED, apply, transform

ROOT = Path('/app/backend/open_webui')
NATIVE = {}
IMAGE = 'data:image/png;base64,iVBORw0KGgo='
QUESTION = 'Format the approved text as a Word document with date and signature fields.'
REASONING = {
    'type': 'reasoning', 'id': 'rs_first', 'summary': [], 'content': [],
    'encrypted_content': 'opaque-original-reasoning', 'status': 'completed',
    'started_at': 100, 'ended_at': 101, 'duration': 1,
}


def load_functions(root: Path) -> dict:
    """Execute actual pure source definitions; no copied converter implementation."""
    namespace = {'JSONCodec': json, 'get_openai_connection': AsyncMock(), 'hashlib': hashlib}
    selections = {
        'utils/misc.py': {
            'get_output_text', 'get_content_from_message', 'get_paired_tool_call_ids',
            'reconcile_tool_pairs', 'get_provider_function', 'convert_output_to_messages',
            'strip_empty_content_blocks', 'merge_system_messages',
        },
        'utils/middleware.py': {
            'get_reasoning_format', 'get_output_message_options', 'strip_reasoning_details',
            'process_messages_with_output', 'sanitize_tool_pairs', 'normalize_messages_for_model',
        },
        'routers/openai.py': {
            'RESPONSES_ALLOWED_FIELDS', '_normalize_stored_item', 'convert_to_responses_payload',
        },
    }
    for filename, names in selections.items():
        path = root / filename
        tree = ast.parse(path.read_text(encoding='utf-8'))
        selected = [
            node for node in tree.body
            if getattr(node, 'name', None) in names
            or isinstance(node, ast.AnnAssign) and getattr(node.target, 'id', None) in names
        ]
        if len(selected) != len(names):
            raise AssertionError(f'Native function selection changed: {filename}')
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace


def output():
    return [
        copy.deepcopy(REASONING),
        {'type': 'function_call', 'call_id': 'render-1', 'name': 'render_office_file',
         'arguments': '{"file_id":"native-file"}', 'status': 'completed'},
        {'type': 'function_call_output', 'call_id': 'render-1', 'output': [
            {'type': 'input_text', 'text': 'Rendered selected file.'},
            {'type': 'input_image', 'image_url': IMAGE}]},
        {**copy.deepcopy(REASONING), 'id': 'rs_second'},
        {'type': 'function_call', 'call_id': 'edit-2', 'name': 'apply_office_batch',
         'arguments': '{}', 'status': 'completed'},
        {'type': 'function_call_output', 'call_id': 'edit-2', 'output': [
            {'type': 'input_text', 'text': 'New version created.'}]},
        {'type': 'message', 'role': 'assistant', 'content': [
            {'type': 'output_text', 'text': 'The document is ready.'}]},
    ]


def provider_payload(items, **options):
    messages = [{'role': 'user', 'content': QUESTION},
                {'role': 'assistant', 'output': items}]
    messages = NATIVE['process_messages_with_output'](messages, **options)
    messages = NATIVE['sanitize_tool_pairs'](messages)
    payload = NATIVE['normalize_messages_for_model']({'messages': messages})
    return NATIVE['convert_to_responses_payload'](payload)


class ContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_connection_selects_responses_once(self):
        connection = AsyncMock(return_value=('', '', {'api_type': 'responses'}))
        NATIVE['get_openai_connection'] = connection
        options = await NATIVE['get_output_message_options']({'owned_by': 'openai', 'urlIdx': 4})
        connection.assert_awaited_once_with(4)
        self.assertEqual(options, {'reasoning_format': 'responses', 'flatten_tool_images': False})

    async def test_native_provider_options_remain_unchanged(self):
        NATIVE['get_openai_connection'] = AsyncMock(return_value=('', '', {}))
        self.assertEqual(await NATIVE['get_output_message_options']({'owned_by': 'ollama'}),
                         {'reasoning_format': 'thinking', 'flatten_tool_images': True})
        self.assertEqual(await NATIVE['get_output_message_options']({'provider': 'llama.cpp', 'urlIdx': 2}),
                         {'reasoning_format': 'reasoning_content', 'flatten_tool_images': True})
        self.assertEqual(await NATIVE['get_output_message_options']({'urlIdx': 2}),
                         {'reasoning_format': None, 'flatten_tool_images': True})
        connection = AsyncMock()
        NATIVE['get_openai_connection'] = connection
        await NATIVE['get_output_message_options']({'owned_by': 'ollama', 'urlIdx': 0})
        await NATIVE['get_output_message_options']({'id': 'pipe'})
        connection.assert_not_awaited()

    def test_whole_replay_preserves_reasoning_order_images_and_user_intent(self):
        items = output()
        untouched = copy.deepcopy(items)
        final = provider_payload(items, reasoning_format='responses', flatten_tool_images=False)
        self.assertEqual(items, untouched)
        self.assertEqual([x['type'] for x in final['input']], [
            'message', 'reasoning', 'function_call', 'function_call_output',
            'reasoning', 'function_call', 'function_call_output', 'message'])
        self.assertEqual(final['input'][1], {key: REASONING[key] for key in
                         ('type', 'id', 'summary', 'content', 'encrypted_content')})
        self.assertEqual(final['input'][3]['output'][1]['image_url'], IMAGE)
        self.assertEqual([x for x in final['input'] if x.get('role') == 'user'], [
            {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': QUESTION}]}])

    def test_continuation_reconstruction_keeps_reasoning_when_no_compaction_occurs(self):
        # v0.12.2 rebuilds already-converted messages after the compaction call,
        # even when compaction is disabled or below threshold. Exercise that path.
        options = {'reasoning_format': 'responses', 'flatten_tool_images': False}
        once = NATIVE['convert_output_to_messages'](output(), raw=True, **options)
        twice = NATIVE['process_messages_with_output'](once, **options)
        self.assertEqual(once, twice)
        payload = NATIVE['convert_to_responses_payload']({'messages': twice})
        self.assertEqual([x['id'] for x in payload['input'] if x['type'] == 'reasoning'],
                         ['rs_first', 'rs_second'])
        self.assertEqual(payload['input'][2]['output'][1]['image_url'], IMAGE)

    def test_foreign_model_guard_removes_bound_items_without_mutating_source(self):
        items = output()
        items[0]['reasoning_details'] = [{'type': 'reasoning.encrypted', 'data': 'foreign'}]
        stripped = NATIVE['strip_reasoning_details'](items)
        self.assertNotIn('encrypted_content', stripped[0])
        self.assertNotIn('reasoning_details', stripped[0])
        self.assertIn('encrypted_content', items[0])
        final = provider_payload(stripped, reasoning_format='responses', flatten_tool_images=False)
        self.assertFalse(any(x['type'] == 'reasoning' for x in final['input']))
        self.assertEqual([x['call_id'] for x in final['input'] if x['type'] == 'function_call'],
                         ['render-1', 'edit-2'])

    def test_chat_completions_image_fallback_excludes_opaque_reasoning(self):
        messages = NATIVE['process_messages_with_output']([
            {'role': 'assistant', 'output': output()}], flatten_tool_images=True)
        self.assertFalse(any('output' in x or 'encrypted_content' in x for x in messages))
        self.assertEqual(messages[1]['role'], 'tool')
        self.assertEqual(messages[1]['content'], 'Rendered selected file.')
        self.assertEqual(messages[2]['role'], 'user')
        self.assertEqual(messages[2]['content'][-1]['image_url']['url'], IMAGE)

    def test_parallel_and_sequential_pairs_keep_upstream_order_and_prefix(self):
        initial = output()[:3]
        first = NATIVE['convert_output_to_messages'](initial, raw=True,
                    reasoning_format='responses', flatten_tool_images=False)
        full = NATIVE['convert_output_to_messages'](output(), raw=True,
                    reasoning_format='responses', flatten_tool_images=False)
        self.assertEqual(first, full[:len(first)])
        parallel = [
            {'type': 'function_call', 'call_id': 'a', 'name': 'a', 'arguments': '{}', 'status': 'completed'},
            {'type': 'function_call', 'call_id': 'b', 'name': 'b', 'arguments': '{}', 'status': 'completed'},
            {'type': 'function_call_output', 'call_id': 'a', 'output': []},
            {'type': 'function_call_output', 'call_id': 'b', 'output': []},
        ]
        result = NATIVE['convert_output_to_messages'](parallel, raw=True)
        self.assertEqual([call['id'] for call in result[0]['tool_calls']], ['a', 'b'])
        self.assertEqual([x['tool_call_id'] for x in result[1:]], ['a', 'b'])

    def test_incomplete_calls_and_display_only_reasoning_are_not_reintroduced(self):
        items = output() + [{'type': 'function_call', 'call_id': 'unfinished',
                            'name': 'edit', 'arguments': '{}', 'status': 'in_progress'}]
        final = provider_payload(items, reasoning_format='responses', flatten_tool_images=False)
        self.assertNotIn('unfinished', [x.get('call_id') for x in final['input']])
        self.assertEqual(NATIVE['convert_output_to_messages'](
            [REASONING], raw=False, reasoning_format='responses'), [])

    def test_all_installed_middleware_reconstruction_sites_select_native_options(self):
        tree = ast.parse((ROOT / 'utils/middleware.py').read_text(encoding='utf-8'))
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id in {'process_messages_with_output', 'convert_output_to_messages'}]
        self.assertEqual(len(calls), 8)
        for call in calls:
            expanded = [kw.value for kw in call.keywords if kw.arg is None]
            if call.func.id == 'convert_output_to_messages' and any(
                kw.arg == 'flatten_tool_images' and isinstance(kw.value, ast.Name)
                and kw.value.id == 'flatten_tool_images' for kw in call.keywords
            ):
                # The sole nested pure converter inherits the enclosing selected options.
                continue
            self.assertEqual(len(expanded), 1, ast.unparse(call))
            option = expanded[0]
            self.assertTrue(
                isinstance(option, ast.Name) and option.id == 'message_options'
                or isinstance(option, ast.Await) and isinstance(option.value, ast.Call)
                and isinstance(option.value.func, ast.Name)
                and option.value.func.id == 'get_output_message_options', ast.unparse(call))


class CallIdProjectionTests(unittest.TestCase):
    @staticmethod
    def pair(call_id):
        return [
            {'type': 'function_call', 'call_id': call_id, 'name': 'render_office_file',
             'arguments': '{"file_id":"source-file"}'},
            {'type': 'function_call_output', 'call_id': call_id, 'output': [
                {'type': 'input_text', 'text': 'Rendered selected file.'},
                {'type': 'input_image', 'image_url': IMAGE}]},
        ]

    def test_63_64_65_character_boundaries_for_both_native_input_shapes(self):
        for length in (63, 64, 65):
            call_id = 'x' * length
            for shape in ('stored_output', 'chat_messages'):
                with self.subTest(length=length, shape=shape):
                    if shape == 'stored_output':
                        messages = [{'role': 'assistant', 'output': self.pair(call_id)}]
                    else:
                        messages = [
                            {'role': 'assistant', 'tool_calls': [{'id': call_id, 'type': 'function',
                                'function': {'name': 'render_office_file', 'arguments': '{}'}}]},
                            {'role': 'tool', 'tool_call_id': call_id, 'content': 'Rendered selected file.'},
                        ]
                    payload = {'model': 'synthetic-responses', 'messages': messages, 'stream': True}
                    untouched = copy.deepcopy(payload)
                    final = NATIVE['convert_to_responses_payload'](payload)
                    expected = call_id if length <= 64 else hashlib.sha256(call_id.encode('utf-8')).hexdigest()
                    self.assertEqual([item['call_id'] for item in final['input']], [expected, expected])
                    self.assertEqual(payload, untouched)

    def test_long_signature_changes_only_outbound_ids_and_can_return_to_google(self):
        items = output()
        long_id = 'call_synthetic__thought__'
        long_id += 'S' * (166 - len(long_id))
        for item in items:
            if item.get('call_id') == 'render-1':
                item['call_id'] = long_id
        untouched = copy.deepcopy(items)
        expected = provider_payload(output(), reasoning_format='responses', flatten_tool_images=False)
        expected_id = hashlib.sha256(long_id.encode('utf-8')).hexdigest()
        expected['input'][2]['call_id'] = expected_id
        expected['input'][3]['call_id'] = expected_id
        final = provider_payload(items, reasoning_format='responses', flatten_tool_images=False)
        self.assertEqual(final, expected)
        self.assertEqual(items, untouched)
        # CC/Google reconstruction still receives the original persisted signature.
        google_messages = NATIVE['process_messages_with_output']([
            {'role': 'assistant', 'output': items}], flatten_tool_images=True)
        self.assertEqual(google_messages[0]['tool_calls'][0]['id'], long_id)
        self.assertEqual(google_messages[1]['tool_call_id'], long_id)
        self.assertEqual(items, untouched)

    def test_distinct_long_ids_with_the_same_first_64_characters_stay_paired(self):
        first, second = 'x' * 64 + 'A', 'x' * 64 + 'B'
        payload = {'messages': [{'role': 'assistant', 'output': self.pair(first) + self.pair(second)}]}
        untouched = copy.deepcopy(payload)
        final = NATIVE['convert_to_responses_payload'](payload)
        first_hash, second_hash = (hashlib.sha256(value.encode()).hexdigest() for value in (first, second))
        self.assertNotEqual(first_hash, second_hash)
        self.assertEqual([item['call_id'] for item in final['input']],
                         [first_hash, first_hash, second_hash, second_hash])
        self.assertEqual(payload, untouched)

    def test_collision_with_an_unchanged_native_id_refuses_without_mutation(self):
        long_id = 'x' * 65
        native_id = hashlib.sha256(long_id.encode()).hexdigest()
        payload = {'messages': [{'role': 'assistant', 'output': self.pair(long_id) + self.pair(native_id)}]}
        untouched = copy.deepcopy(payload)
        with self.assertRaisesRegex(ValueError, 'merge distinct IDs') as raised:
            NATIVE['convert_to_responses_payload'](payload)
        self.assertNotIn(long_id, str(raised.exception))
        self.assertEqual(payload, untouched)

    def test_each_unpaired_long_item_refuses_without_mutation(self):
        for item in self.pair('x' * 65):
            with self.subTest(item_type=item['type']):
                payload = {'messages': [{'role': 'assistant', 'output': [item]}]}
                untouched = copy.deepcopy(payload)
                with self.assertRaisesRegex(ValueError, 'matching call and output'):
                    NATIVE['convert_to_responses_payload'](payload)
                self.assertEqual(payload, untouched)

    def test_long_projection_refuses_previous_response_id_without_mutation(self):
        payload = {'previous_response_id': 'resp_native_previous',
                   'messages': [{'role': 'assistant', 'output': self.pair('x' * 65)}]}
        untouched = copy.deepcopy(payload)
        with self.assertRaisesRegex(ValueError, 'cannot be projected with previous_response_id'):
            NATIVE['convert_to_responses_payload'](payload)
        self.assertEqual(payload, untouched)

    def test_native_stateful_output_only_id_remains_unchanged(self):
        call_id = 'call_native_' + 'x' * 52
        payload = {'previous_response_id': 'resp_native_previous',
                   'messages': [{'role': 'tool', 'tool_call_id': call_id, 'content': 'Result.'}]}
        untouched = copy.deepcopy(payload)
        final = NATIVE['convert_to_responses_payload'](payload)
        self.assertEqual(final['previous_response_id'], untouched['previous_response_id'])
        self.assertEqual(final['input'], [{'type': 'function_call_output', 'call_id': call_id, 'output': 'Result.'}])
        self.assertEqual(payload, untouched)

    def test_projection_does_not_rewrite_item_ids_arguments_or_user_content(self):
        call_id = 'opaque-' + '\u03a9' * 65
        pair = self.pair(call_id)
        pair[0]['id'] = 'fc_native_item_id'
        pair[0]['arguments'] = json.dumps({'original_id': call_id, 'text': QUESTION}, ensure_ascii=False)
        payload = {'messages': [{'role': 'user', 'content': call_id + '\n' + QUESTION},
                                {'role': 'assistant', 'output': pair}],
                   'tools': [{'type': 'function', 'function': {'name': 'render_office_file',
                              'parameters': {'type': 'object', 'properties': {}}}}]}
        untouched = copy.deepcopy(payload)
        final = NATIVE['convert_to_responses_payload'](payload)
        self.assertEqual(final['input'][0]['content'][0]['text'], untouched['messages'][0]['content'])
        self.assertEqual(final['input'][1]['id'], 'fc_native_item_id')
        self.assertEqual(final['input'][1]['arguments'], pair[0]['arguments'])
        self.assertEqual(final['input'][2]['output'], pair[1]['output'])
        self.assertEqual(final['input'][1]['call_id'], hashlib.sha256(call_id.encode('utf-8')).hexdigest())
        self.assertEqual(payload, untouched)


class InstallerTests(unittest.TestCase):
    def test_previous_overlay_router_is_refused_before_any_write(self):
        source = (ROOT / 'routers/openai.py').read_text(encoding='utf-8')
        start = source.index('    # Project only the outgoing Responses representation;')
        end = source.index("    responses_payload = {**payload, 'input': input_items}\n", start)
        previous = source[:start] + source[end:]
        previous = previous.replace(
            '    payload = dict(payload)  # Keep caller input intact, including on projection refusal.\n', '', 1)
        self.assertEqual(hashlib.sha256(previous.encode()).hexdigest(),
                         '109217b80dd70cef9b2f8dcf97c2612ae2b0c31cd112efb95bd82c18d10ca620')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in PATCHED:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / name).read_bytes())
            (root / 'routers/openai.py').write_bytes(previous.encode())
            before = {name: (root / name).read_bytes() for name in PATCHED}
            for check in (True, False):
                with self.assertRaisesRegex(RuntimeError, 'Unsupported routers/openai.py sha256='):
                    apply(root, check=check)
            self.assertEqual(before, {name: (root / name).read_bytes() for name in PATCHED})

    def test_installed_hashes_and_idempotence(self):
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

    def test_unknown_source_fails_before_any_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in PATCHED:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((ROOT / name).read_bytes())
            # Leave an earlier file genuinely unpatched: it would be written if
            # the installer mutated before validating the later drifted router.
            misc_path = root / 'utils/misc.py'
            fragment = ("            if raw and reasoning_format == 'responses' and item.get('encrypted_content'):\n"
                        "                flush_pending()\n"
                        "                messages.append({'role': 'assistant', 'content': '', 'output': [item]})\n"
                        "                continue\n")
            misc_path.write_bytes(misc_path.read_bytes().replace(fragment.encode(), b''))
            self.assertEqual(hashlib.sha256(misc_path.read_bytes()).hexdigest(), ORIGINAL['utils/misc.py'])
            target = root / 'routers/openai.py'
            target.write_bytes(target.read_bytes() + b'\n# unsupported drift\n')
            before = {name: (root / name).read_bytes() for name in PATCHED}
            with self.assertRaises(RuntimeError):
                apply(root)
            self.assertEqual(before, {name: (root / name).read_bytes() for name in before})

    def test_duplicate_or_missing_anchor_fails_closed(self):
        filename = 'utils/misc.py'
        source = (ROOT / filename).read_text(encoding='utf-8')
        # Reconstruct the upstream exact source for the narrowly changed reasoning branch.
        fragment = ("            if raw and reasoning_format == 'responses' and item.get('encrypted_content'):\n"
                    "                flush_pending()\n"
                    "                messages.append({'role': 'assistant', 'content': '', 'output': [item]})\n"
                    "                continue\n")
        original = source.replace(fragment, '')
        self.assertEqual(hashlib.sha256(original.encode()).hexdigest(), ORIGINAL[filename])
        self.assertEqual(transform(filename, original), source)
        with self.assertRaises(RuntimeError):
            transform(filename, original + original)
        with self.assertRaises(RuntimeError):
            transform(filename, '')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--root', type=Path, default=ROOT)
    args, remaining = parser.parse_known_args()
    ROOT = args.root
    NATIVE = load_functions(ROOT)
    unittest.main(argv=[__file__, *remaining])
