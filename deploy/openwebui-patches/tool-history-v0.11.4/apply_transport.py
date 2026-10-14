"""Keep multimodal tool results native on stateless Responses connections.

The connection catalog owns the API type. Middleware only selects the existing
converter representation; it must not create a new user instruction for Responses.
Remove when upstream preserves multimodal tool results on this path.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

ORIGINAL_SHA256 = "bda81a45b4169ec2af351c3eed7a574b0e43cf1026c3d6945dada7290a5af497"
PATCHED_SHA256 = "31d57eae3ad43c04905e3d89ec9b361c0b6f1a17d0c8bf351807eda8b591453c"


def transform(source: str) -> str:
    replacements = [
        ("from open_webui.routers.pipelines import (",
         "from open_webui.routers.openai import get_openai_connection\n"
         "from open_webui.routers.pipelines import ("),
        ("def process_messages_with_output(\n",
         "async def should_flatten_tool_images(model: dict) -> bool:\n"
         "    # Reuse the same native connection owner as the provider sender.\n"
         "    if model.get('owned_by') == 'ollama' or model.get('urlIdx') is None:\n"
         "        return True\n"
         "    _, _, connection = await get_openai_connection(model['urlIdx'])\n"
         "    return connection.get('api_type') != 'responses'\n\n\n"
         "def process_messages_with_output(\n"),
        ("    reasoning_format: str | None = None,\n) -> list[dict]:",
         "    reasoning_format: str | None = None,\n"
         "    flatten_tool_images: bool = True,\n) -> list[dict]:"),
        ("                flatten_tool_images=True,\n            )\n            if output_messages:",
         "                flatten_tool_images=flatten_tool_images,\n            )\n            if output_messages:"),
        ("        reasoning_format=get_reasoning_format(model),\n    )\n    form_data['messages'] = sanitize_tool_pairs",
         "        reasoning_format=get_reasoning_format(model),\n"
         "        flatten_tool_images=await should_flatten_tool_images(model),\n"
         "    )\n    form_data['messages'] = sanitize_tool_pairs"),
        ("                reasoning_format=get_reasoning_format(model),\n            )\n            form_data['messages'] = sanitize_tool_pairs",
         "                reasoning_format=get_reasoning_format(model),\n"
         "                flatten_tool_images=await should_flatten_tool_images(model),\n"
         "            )\n            form_data['messages'] = sanitize_tool_pairs"),
        ("                        else:\n                            tool_messages = convert_output_to_messages(",
         "                        else:\n"
         "                            flatten_tool_images = await should_flatten_tool_images(model)\n"
         "                            tool_messages = convert_output_to_messages("),
        ("                                flatten_tool_images=True,\n                            )\n\n                            # Chat Completions providers",
         "                                flatten_tool_images=flatten_tool_images,\n                            )\n\n                            # Chat Completions providers"),
        ("                                if message.get('role') == 'tool' and isinstance(message.get('content'), list):",
         "                                if flatten_tool_images and message.get('role') == 'tool' and isinstance(message.get('content'), list):"),
        ("                                        flatten_tool_images=True,\n                                    ),",
         "                                        flatten_tool_images=await should_flatten_tool_images(model),\n                                    ),"),
    ]
    for old, new in replacements:
        if source.count(old) != 1:
            raise RuntimeError(f"Expected one transport anchor: {old[:90]!r}")
        source = source.replace(old, new)
    return source


def apply(root: Path, *, check: bool = False) -> str:
    path = root / "utils/middleware.py"
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest == PATCHED_SHA256:
        return "Native Responses tool-image transport already present"
    if digest != ORIGINAL_SHA256:
        raise RuntimeError(f"Unsupported middleware.py sha256={digest}")
    updated = transform(data.decode("utf-8")).encode("utf-8")
    if hashlib.sha256(updated).hexdigest() != PATCHED_SHA256:
        raise RuntimeError("Unexpected transport patch result")
    compile(updated, str(path), "exec")
    if not check:
        path.write_bytes(updated)
    return "Native Responses tool-image transport applicable" if check else "Native Responses tool-image transport applied"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/app/backend/open_webui"))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(apply(args.root, check=args.check))
