"""Preserve context and project outbound call IDs on v0.12.2 Responses paths.

This overlay uses the existing connection catalog and provider converter. It adds
no provider client, prompt, tool loop, persistence or history-ordering backport.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

UPSTREAM_COMMIT = '6a18585ff4c2e5f6805f682222cfbc46dc669ef8'
ORIGINAL = {
    'utils/misc.py': '24b39f1c7c7ef24c5cc436820af62df2e3eae11d94e498ae30fe9fda33b7d6c1',
    'utils/middleware.py': 'a4139811ba7e75b12dc4590be69623332293a3eb724bb8b536718887d23ee52e',
    'routers/openai.py': 'af02463b799a817b307da5d03af25874ca14f477b883e913051b3b797d365955',
}
PATCHED = {
    'utils/misc.py': '9098c447441e2f6bfa529ae8506a03acab6400a8205c7942e86b004c07833068',
    'utils/middleware.py': 'd0c6eb1d111db4f977da98d14f2f0f668b828729f304469cebb9d11d8cf35201',
    'routers/openai.py': 'a543d986125e66f5161bf60f480a6fa15bd2d95ebcac4b03b856d1ff9619f834',
}


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f'Expected one v0.12.2 context anchor: {old[:110]!r}')
    return source.replace(old, new)


def transform(filename: str, source: str) -> str:
    if filename == 'utils/misc.py':
        return replace_once(
            source,
            "        elif item_type == 'reasoning':\n            reasoning_details =",
            "        elif item_type == 'reasoning':\n"
            "            if raw and reasoning_format == 'responses' and item.get('encrypted_content'):\n"
            "                flush_pending()\n"
            "                messages.append({'role': 'assistant', 'content': '', 'output': [item]})\n"
            "                continue\n"
            "            reasoning_details =",
        )
    if filename == 'routers/openai.py':
        source = replace_once(
            source,
            "    'function_call_output': {'type', 'call_id', 'output'},\n}",
            "    'function_call_output': {'type', 'call_id', 'output'},\n"
            "    'reasoning': {'type', 'id', 'summary', 'content', 'encrypted_content'},\n}",
        )
        source = replace_once(
            source,
            "    messages = payload.pop('messages', [])\n",
            "    payload = dict(payload)  # Keep caller input intact, including on projection refusal.\n"
            "    messages = payload.pop('messages', [])\n",
        )
        return replace_once(
            source,
            "    responses_payload = {**payload, 'input': input_items}\n",
            "    # Project only the outgoing Responses representation; persisted provider IDs\n"
            "    # may carry opaque signatures required when returning to their original provider.\n"
            "    call_ids = {item.get('call_id') for item in input_items\n"
            "                if item.get('type') == 'function_call' and isinstance(item.get('call_id'), str)}\n"
            "    result_ids = {item.get('call_id') for item in input_items\n"
            "                  if item.get('type') == 'function_call_output' and isinstance(item.get('call_id'), str)}\n"
            "    original_ids = call_ids | result_ids\n"
            "    long_ids = {call_id for call_id in original_ids if len(call_id) > 64}\n"
            "    if long_ids:\n"
            "        if payload.get('previous_response_id'):\n"
            "            raise ValueError('Long Responses call IDs cannot be projected with previous_response_id')\n"
            "        if not long_ids <= call_ids & result_ids:\n"
            "            raise ValueError('Long Responses call IDs require matching call and output items')\n"
            "        projected = {call_id: hashlib.sha256(call_id.encode('utf-8')).hexdigest() for call_id in long_ids}\n"
            "        if len({projected.get(call_id, call_id) for call_id in original_ids}) != len(original_ids):\n"
            "            raise ValueError('Responses call ID projection would merge distinct IDs')\n"
            "        input_items = [\n"
            "            {**item, 'call_id': projected[item['call_id']]}\n"
            "            if item.get('type') in {'function_call', 'function_call_output'}\n"
            "            and item.get('call_id') in projected else item\n"
            "            for item in input_items\n"
            "        ]\n\n"
            "    responses_payload = {**payload, 'input': input_items}\n",
        )
    if filename != 'utils/middleware.py':
        raise ValueError(filename)
    replacements = [
        (
            'from open_webui.routers.pipelines import (',
            'from open_webui.routers.openai import get_openai_connection\n'
            'from open_webui.routers.pipelines import (',
        ),
        (
            "if key != 'reasoning_details'} if isinstance(item, dict) else item",
            "if key not in {'reasoning_details', 'encrypted_content'}} if isinstance(item, dict) else item",
        ),
        (
            'def process_messages_with_output(\n',
            'async def get_output_message_options(model: dict) -> dict:\n'
            '    # Reuse the same native connection owner as the provider sender.\n'
            '    responses = False\n'
            "    if model.get('owned_by') != 'ollama' and model.get('urlIdx') is not None:\n"
            "        _, _, connection = await get_openai_connection(model['urlIdx'])\n"
            "        responses = connection.get('api_type') == 'responses'\n"
            '    return {\n'
            "        'reasoning_format': 'responses' if responses else get_reasoning_format(model),\n"
            "        'flatten_tool_images': not responses,\n"
            '    }\n\n\n'
            'def process_messages_with_output(\n',
        ),
        (
            '    include_file_context: bool = False,\n) -> list[dict]:',
            '    include_file_context: bool = False,\n'
            '    flatten_tool_images: bool = True,\n) -> list[dict]:',
        ),
        (
            '                flatten_tool_images=True,\n            )\n            if output_messages:',
            '                flatten_tool_images=flatten_tool_images,\n            )\n            if output_messages:',
        ),
        (
            '        reasoning_format=get_reasoning_format(model),\n'
            "        include_file_context=metadata['include_file_context'],",
            "        include_file_context=metadata['include_file_context'],\n"
            '        **await get_output_message_options(model),',
        ),
        (
            '            process_messages_with_output([assistant_message], reasoning_format=get_reasoning_format(model))\n',
            '            process_messages_with_output([assistant_message], **await get_output_message_options(model))\n',
        ),
        (
            '                *process_messages_with_output([assistant_message], reasoning_format=get_reasoning_format(model)),\n',
            '                *process_messages_with_output([assistant_message], **await get_output_message_options(model)),\n',
        ),
        (
            "                        if ENABLE_RESPONSES_API_STATEFUL and last_response_id:\n",
            '                        message_options = await get_output_message_options(model)\n'
            "                        if ENABLE_RESPONSES_API_STATEFUL and last_response_id:\n",
        ),
        (
            '                                output, raw=True, reasoning_format=get_reasoning_format(model)\n',
            '                                output, raw=True, **message_options\n',
        ),
        (
            '                                reasoning_format=get_reasoning_format(model),\n'
            '                                flatten_tool_images=True,',
            '                                **message_options,',
        ),
        (
            "                                if message.get('role') == 'tool' and isinstance(message.get('content'), list):",
            "                                if message_options['flatten_tool_images'] and message.get('role') == 'tool' and isinstance(message.get('content'), list):",
        ),
        (
            "                            new_form_data['messages'] = process_messages_with_output(messages)\n",
            "                            new_form_data['messages'] = process_messages_with_output(messages, **message_options)\n",
        ),
        (
            '                                        reasoning_format=get_reasoning_format(model),\n'
            '                                        flatten_tool_images=True,',
            '                                        **await get_output_message_options(model),',
        ),
    ]
    for old, new in replacements:
        source = replace_once(source, old, new)
    return source


def apply(root: Path, *, check: bool = False) -> str:
    # Preflight every file before writing any: unknown input must never partly apply.
    updates = []
    for filename, original in ORIGINAL.items():
        path = root / filename
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest == PATCHED[filename]:
            continue
        if digest != original:
            raise RuntimeError(f'Unsupported {filename} sha256={digest}')
        updated = transform(filename, data.decode('utf-8')).encode('utf-8')
        if hashlib.sha256(updated).hexdigest() != PATCHED[filename]:
            raise RuntimeError(f'Unexpected {filename} patch result')
        compile(updated, str(path), 'exec')
        updates.append((path, updated))
    if not check:
        for path, data in updates:
            path.write_bytes(data)
    return f'v0.12.2 Responses context {"applicable" if check else "applied"}: {len(updates)} files'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/app/backend/open_webui'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(apply(args.root, check=args.check))
