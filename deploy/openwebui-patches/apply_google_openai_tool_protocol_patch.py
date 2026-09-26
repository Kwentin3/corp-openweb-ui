#!/usr/bin/env python3
"""Apply the small Google tool-protocol overlay to verified OpenWebUI 0.9.6.

No provider client, credential, tool executor or signature cache is added.
Remove when the selected provider/native runtime supports this protocol itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


MARKER = "# ALPHASOFT_GOOGLE_TOOL_PROTOCOL_V2"
EXPECTED = {
    "middleware.py": "861978ea80b69c4201c0742d1401691834ea7202e75d4eb47250ac0c14af2ea9",
    "misc.py": "636d5aa53907733def4999677f1720d5d0a900934c67d3e88f115584d2ba9db8",
}


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise RuntimeError(f"Expected exactly one native source anchor: {old[:100]!r}")
    return source.replace(old, new)


def transform(name: str, source: str) -> str:
    if name == "middleware.py":
        source = replace_once(source, "from open_webui.utils.misc import (", (
            f"{MARKER}\n"
            "from open_webui.utils.google_openai_tool_compat import google_tool_call_index, google_tool_fields\n"
            "from open_webui.utils.misc import ("
        ))
        old = "                                            tool_call_index = delta_tool_call.get('index')"
        source = replace_once(source, old, old + "\n" + (
            "                                            if tool_call_index is None:\n"
            "                                                tool_call_index = google_tool_call_index(\n"
            "                                                    form_data.get('model', ''), delta_tool_call, response_tool_calls\n"
            "                                                )\n"
            "                                                if tool_call_index is not None:\n"
            "                                                    delta_tool_call['index'] = tool_call_index"
        ))
        old = (
            "                                    'arguments': func.get('arguments', '{}'),\n"
            "                                    'status': 'in_progress',\n"
        )
        source = replace_once(source, old, old + "                                    **google_tool_fields(tc),\n")
    elif name == "misc.py":
        source = replace_once(source, "import json\n", (
            "import json\n" + MARKER + "\n"
            "from open_webui.utils.google_openai_tool_compat import google_tool_fields\n"
        ))
        old = (
            "                        'arguments': arguments,\n"
            "                    },\n"
            "                }\n"
        )
        source = replace_once(source, old, (
            "                        'arguments': arguments,\n"
            "                    },\n"
            "                    **google_tool_fields(item),\n"
            "                }\n"
        ))
    else:
        raise ValueError(name)
    compile(source, name, "exec")
    return source


def patch(root: Path) -> dict:
    # Validate both files before writing either; reject source drift even if an
    # anchor happens to exist in a different runtime version.
    staged = []
    for name, expected in EXPECTED.items():
        path = root / "utils" / name
        source = path.read_text(encoding="utf-8")
        digest = hashlib.sha256(source.encode()).hexdigest()
        if MARKER in source:
            # Reconstruct the expected patched bytes from the captured original
            # supplied at build time is unnecessary: all owned fragments must be
            # unique and the whole file must match the recorded first application.
            receipt = root / "utils" / "google_openai_tool_protocol_receipt.json"
            hashes = json.loads(receipt.read_text(encoding="utf-8"))["patched"]
            if hashes.get(name) != digest:
                raise RuntimeError(f"Patched native source drift: {name}")
            staged.append((path, source))
        else:
            if digest != expected:
                raise RuntimeError(f"Unsupported OpenWebUI native source: {name} sha256={digest}")
            staged.append((path, transform(name, source)))
    helper = root / "utils" / "google_openai_tool_compat.py"
    if not helper.is_file():
        raise RuntimeError("Google tool representation module is not packaged in the image")
    compile(helper.read_text(encoding="utf-8"), str(helper), "exec")
    patched = {}
    for path, source in staged:
        path.write_text(source, encoding="utf-8", newline="\n")
        patched[path.name] = hashlib.sha256(source.encode()).hexdigest()
    receipt = {"runtime": "OpenWebUI 0.9.6", "original": EXPECTED, "patched": patched,
               "helper_sha256": hashlib.sha256(helper.read_bytes()).hexdigest()}
    (root / "utils" / "google_openai_tool_protocol_receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/app/backend/open_webui"))
    args = parser.parse_args()
    print(json.dumps(patch(args.root)))
