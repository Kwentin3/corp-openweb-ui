#!/usr/bin/env python3
"""Exercise the installed native parser, output builder and history converter.

Run inside the candidate image. Optional --provider-call accepts a real Google
tool-call JSON and --wire-output emits the reconstructed native messages for
a provider replay. This is protocol evidence, not browser product acceptance.
"""
from __future__ import annotations

import argparse
import ast
import copy
import importlib.util
import json
from pathlib import Path


def load_native_functions(root: Path):
    helper_path = root / "utils/google_openai_tool_compat.py"
    spec = importlib.util.spec_from_file_location("compat", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    namespace = {"json": json, "google_tool_call_index": helper.google_tool_call_index,
                 "google_tool_fields": helper.google_tool_fields,
                 "output_id": lambda prefix: prefix + "_probe"}
    middleware = ast.parse((root / "utils/middleware.py").read_text(encoding="utf-8"))
    misc = ast.parse((root / "utils/misc.py").read_text(encoding="utf-8"))

    def install_function(tree, name):
        nodes = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
        assert len(nodes) == 1, name
        module = ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(nodes[0])], type_ignores=[]))
        exec(compile(module, "installed-native-functions", "exec"), namespace)

    install_function(misc, "reconcile_tool_pairs")
    install_function(misc, "convert_output_to_messages")
    install_function(middleware, "process_messages_with_output")

    def install_loop(target, signature, result, required_name=None):
        nodes = [node for node in ast.walk(middleware) if isinstance(node, ast.For)
                 and isinstance(node.target, ast.Name) and node.target.id == target]
        if required_name:
            nodes = [node for node in nodes if any(isinstance(child, ast.Name) and child.id == required_name
                                                   for child in ast.walk(node))]
        assert len(nodes) == 1, (target, len(nodes))
        wrapper = ast.parse(signature + ":\n    pass\n").body[0]
        wrapper.body = [copy.deepcopy(nodes[0]), ast.Return(value=ast.Name(id=result, ctx=ast.Load()))]
        module = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
        exec(compile(module, "installed-native-loop", "exec"), namespace)

    install_loop("delta_tool_call", "def accumulate(model_id, delta_tool_calls, response_tool_calls)", "response_tool_calls")
    install_loop("tc", "def capture(response_tool_calls, output, existing_call_ids)", "output", "existing_call_ids")
    return namespace


def replay_native(root: Path, model: str, calls: list[dict]) -> list[dict]:
    native = load_native_functions(root)
    accumulated = []
    for call in calls:
        native["accumulate"](model, [copy.deepcopy(call)], accumulated)
    assert len(accumulated) == len(calls), "Native stream discarded a complete call"
    assert len({call["index"] for call in accumulated}) == len(calls), "Merged distinct calls"
    output = native["capture"](accumulated, [], set())
    for call in accumulated:
        output.append({"type": "function_call_output", "call_id": call["id"],
                       "output": [{"type": "input_text", "text": '{"jan":350,"feb":550}'}]})
    # Exercise the same JSON representation persisted in native Chat history.
    output = json.loads(json.dumps(output))
    messages = native["process_messages_with_output"]([{"role": "assistant", "output": output}])
    replayed = [call for message in messages for call in message.get("tool_calls", [])]
    assert [call["id"] for call in replayed] == [call["id"] for call in calls]
    for original, call in zip(calls, replayed):
        assert call["function"] == original["function"]
        assert call.get("extra_content") == original.get("extra_content")
    return messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/app/backend/open_webui"))
    parser.add_argument("--provider-call", type=Path)
    parser.add_argument("--wire-output", type=Path)
    args = parser.parse_args()
    google = {"id": "one", "type": "function", "function": {"name": "read", "arguments": "{}"},
              "extra_content": {"google": {"thought_signature": "original-opaque-value"}}}
    second = {**google, "id": "two"}
    replay_native(args.root, "models/gemini-3.5-flash", [google, second])
    openai = {"id": "normal", "type": "function", "index": 5,
              "function": {"name": "read", "arguments": "{}"}}
    replay_native(args.root, "gpt-5.4-mini", [openai])
    if args.provider_call:
        actual = json.loads(args.provider_call.read_text(encoding="utf-8"))
        messages = replay_native(args.root, actual["model"], [actual["call"]])
        if args.wire_output:
            args.wire_output.write_text(json.dumps(messages), encoding="utf-8")
    print(json.dumps({"native_parser": "pass", "native_output": "pass", "native_history_replay": "pass",
                      "parallel_indices": "pass", "openai_unchanged": "pass",
                      "real_provider_call": bool(args.provider_call)}))


if __name__ == "__main__":
    main()
