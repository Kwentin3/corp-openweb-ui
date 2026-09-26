from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPAT = load("google_openai_tool_compat")
PATCH = load("apply_google_openai_tool_protocol_patch")


def call(identity="one", arguments='{"file_id":"jan"}'):
    return {"id": identity, "type": "function", "function": {
        "name": "inspect_office_spreadsheet", "arguments": arguments}}


def test_complete_google_calls_keep_distinct_indices_across_chunks():
    first = call()
    first["index"] = COMPAT.google_tool_call_index("models/gemini-3.5-flash", first, [])
    second = call("two")
    second["index"] = COMPAT.google_tool_call_index("models/gemini-3.5-flash", second, [first])
    assert (first["index"], second["index"]) == (0, 1)
    assert COMPAT.google_tool_call_index("models/gemini-3.5-flash", first, [first, second]) == 0


@pytest.mark.parametrize("model,tool", [
    ("gpt-5.4-mini", call()),
    ("models/gemini-3.5-flash", call(arguments='{"file_id":')),
    ("models/gemini-3.5-flash", call(arguments="null")),
    ("models/gemini-3.5-flash", {"function": {"name": "read", "arguments": "{}"}}),
])
def test_other_providers_and_unbound_fragments_are_not_guessed(model, tool):
    assert COMPAT.google_tool_call_index(model, tool, []) is None


def test_opaque_google_fields_are_preserved_without_cache_or_placeholder():
    item = {"extra_content": {"google": {"thought_signature": "opaque-original", "other": 7}}}
    fields = COMPAT.google_tool_fields(item)
    assert fields == item
    fields["extra_content"]["google"]["thought_signature"] = "changed"
    assert item["extra_content"]["google"]["thought_signature"] == "opaque-original"
    assert COMPAT.google_tool_fields({}) == {}
    assert COMPAT.google_tool_fields({"extra_content": {"unrelated": "not Google"}}) == {}


def test_unknown_native_source_is_rejected_before_any_write(tmp_path):
    utils = tmp_path / "utils"
    utils.mkdir()
    paths = [utils / name for name in PATCH.EXPECTED]
    for path in paths:
        path.write_text("# another runtime\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in paths}
    with pytest.raises(RuntimeError, match="Unsupported OpenWebUI native source"):
        PATCH.patch(tmp_path)
    assert {path: path.read_bytes() for path in paths} == before
