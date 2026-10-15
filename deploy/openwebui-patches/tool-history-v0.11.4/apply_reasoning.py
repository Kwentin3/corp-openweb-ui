"""Preserve native encrypted reasoning on the exact stateless Responses path.

The existing connection owner chooses the representation. The existing provider
converter owns API field admission; model-bound replay uses the existing model
identity check. Remove when upstream passes the same continuation checks.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ORIGINAL = {
    'utils/misc.py': '5ce742935aebfcdb1aaa3134db34a441398c9506e79cd09d768267afdb18d4c3',
    'utils/middleware.py': '31d57eae3ad43c04905e3d89ec9b361c0b6f1a17d0c8bf351807eda8b591453c',
    'routers/openai.py': 'c6b514f057e9273206cd7d61e064e000ffe4db5cd5e06c0379a408e9aa1e964a',
}
PATCHED = {
    'utils/misc.py': 'b6bd33dcbe366296b6fbfb608f8f70ddb91e07162651a43a16d54defcaa980ee',
    'utils/middleware.py': 'a71e7f82b9690cd395a7684b0191f2175157c2784da5379638fa6a549dc92941',
    'routers/openai.py': '7349062e8f97c687296701eb120dda0944d9d379cbf2adf80b6366342547519b',
}


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f'Expected one reasoning transport anchor: {old[:100]!r}')
    return source.replace(old, new)


def transform(filename: str, source: str) -> str:
    if filename == 'utils/misc.py':
        return replace_once(source,
            "        elif item_type == 'reasoning':\n            reasoning_details =",
            "        elif item_type == 'reasoning':\n"
            "            if raw and reasoning_format == 'responses' and item.get('encrypted_content'):\n"
            "                flush_pending()\n"
            "                messages.append({'role': 'assistant', 'content': '', 'output': [item]})\n"
            "                continue\n"
            "            reasoning_details =")
    if filename == 'routers/openai.py':
        return replace_once(source,
            "    'function_call_output': {'type', 'call_id', 'output'},\n}",
            "    'function_call_output': {'type', 'call_id', 'output'},\n"
            "    'reasoning': {'type', 'id', 'summary', 'content', 'encrypted_content'},\n}")
    if filename != 'utils/middleware.py':
        raise ValueError(filename)
    source = replace_once(source,
        "async def should_flatten_tool_images(model: dict) -> bool:\n"
        "    # Reuse the same native connection owner as the provider sender.\n"
        "    if model.get('owned_by') == 'ollama' or model.get('urlIdx') is None:\n"
        "        return True\n"
        "    _, _, connection = await get_openai_connection(model['urlIdx'])\n"
        "    return connection.get('api_type') != 'responses'\n",
        "async def get_output_message_options(model: dict) -> dict:\n"
        "    # One native connection lookup selects both transport representations.\n"
        "    responses = False\n"
        "    if model.get('owned_by') != 'ollama' and model.get('urlIdx') is not None:\n"
        "        _, _, connection = await get_openai_connection(model['urlIdx'])\n"
        "        responses = connection.get('api_type') == 'responses'\n"
        "    return {\n"
        "        'reasoning_format': 'responses' if responses else get_reasoning_format(model),\n"
        "        'flatten_tool_images': not responses,\n"
        "    }\n\n\n"
        "async def should_flatten_tool_images(model: dict) -> bool:\n"
        "    return (await get_output_message_options(model))['flatten_tool_images']\n")
    source = replace_once(source,
        "if key != 'reasoning_details'} if isinstance(item, dict) else item",
        "if key not in {'reasoning_details', 'encrypted_content'}} if isinstance(item, dict) else item")
    for indentation in (8, 16, 40):
        prefix = ' ' * indentation
        source = replace_once(source,
            prefix + "reasoning_format=get_reasoning_format(model),\n" +
            prefix + "flatten_tool_images=await should_flatten_tool_images(model),",
            prefix + "**await get_output_message_options(model),")
    source = replace_once(source,
        "                            flatten_tool_images = await should_flatten_tool_images(model)\n",
        "                            message_options = await get_output_message_options(model)\n"
        "                            flatten_tool_images = message_options['flatten_tool_images']\n")
    source = replace_once(source,
        "                                reasoning_format=get_reasoning_format(model),\n"
        "                                flatten_tool_images=flatten_tool_images,",
        "                                **message_options,")
    return source


def apply(root: Path, *, check: bool = False) -> str:
    updates = []
    for filename, original in ORIGINAL.items():
        path = root / filename
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest == PATCHED.get(filename):
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
    return f'Reasoning transport {"applicable" if check else "applied"}: {len(updates)} files'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('/app/backend/open_webui'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(apply(args.root, check=args.check))
