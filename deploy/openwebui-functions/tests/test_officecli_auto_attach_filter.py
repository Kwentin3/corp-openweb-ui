from __future__ import annotations

import asyncio
import copy
import importlib.util
from pathlib import Path


SOURCE = Path(__file__).parents[1] / "officecli_auto_attach_filter.py"
SPEC = importlib.util.spec_from_file_location("officecli_auto_attach_filter", SOURCE)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def run_inlet(filter_instance, body, metadata):
    return asyncio.run(filter_instance.inlet(body, __metadata__=metadata))


def configured_filter():
    instance = MODULE.Filter()
    instance.valves = instance.Valves(target_model_ids="claude-opus-5,gpt-5.4-mini")
    return instance


def native_metadata(task=None):
    metadata = {"params": {"function_calling": "native"}}
    if task is not None:
        metadata["task"] = task
    return metadata


def eligible_body():
    return {
        "model": "claude-opus-5",
        "tool_ids": ["server:other"],
        "messages": [
            {"role": "system", "content": "Keep this existing instruction."},
            {"role": "user", "content": "Update the attached proposal."},
        ],
    }


def test_eligible_native_model_adds_only_existing_tool_and_preserves_system_prompt():
    body = eligible_body()

    result = run_inlet(configured_filter(), body, native_metadata())

    assert result is body
    assert body["tool_ids"] == ["server:other", "server:officecli"]
    assert body["messages"][0]["content"].startswith("Keep this existing instruction.")
    assert MODULE.OFFICECLI_INSTRUCTION_MARKER in body["messages"][0]["content"]
    assert "table-row" in body["messages"][0]["content"]
    assert "actual formula value" in body["messages"][0]["content"]
    assert "official PPTX skill" in body["messages"][0]["content"]
    assert "pptx table, pptx chart, or pptx picture help" in body["messages"][0]["content"]
    assert "guessed rNcN cell keys" in body["messages"][0]["content"]
    assert "add every requested slide at the document root" in body["messages"][0]["content"]
    assert "rather than adding a competing overlay" in body["messages"][0]["content"]
    assert "shape inventory" in body["messages"][0]["content"]
    assert "never guess a generic shape name" in body["messages"][0]["content"]
    assert "most recent successful OfficeCLI batch" in body["messages"][0]["content"]
    assert "result_file_id" in body["messages"][0]["content"]
    assert "attachment://image" in body["messages"][0]["content"]
    assert "Never invent a local path" in body["messages"][0]["content"]


def test_repeated_inlet_is_idempotent():
    body = eligible_body()
    filter_instance = configured_filter()

    run_inlet(filter_instance, body, native_metadata())
    run_inlet(filter_instance, body, native_metadata())

    assert body["tool_ids"].count("server:officecli") == 1
    assert body["messages"][0]["content"].count(MODULE.OFFICECLI_INSTRUCTION_MARKER) == 1


def test_unlisted_models_are_unchanged():
    filter_instance = configured_filter()
    for body, metadata in (({**eligible_body(), "model": "office-documents"}, native_metadata()),):
        before = copy.deepcopy(body)

        run_inlet(filter_instance, body, metadata)

        assert body == before


def test_ordinary_chat_without_function_calling_metadata_receives_officecli():
    body = eligible_body()

    run_inlet(configured_filter(), body, {"params": {}})

    assert body["tool_ids"] == ["server:other", "server:officecli"]
    assert MODULE.OFFICECLI_INSTRUCTION_MARKER in body["messages"][0]["content"]


def test_task_and_caller_supplied_tools_are_unchanged():
    filter_instance = configured_filter()
    task_body = eligible_body()
    supplied_tools_body = {**eligible_body(), "tools": []}

    for body, metadata in (
        (task_body, native_metadata(task="title_generation")),
        (supplied_tools_body, native_metadata()),
    ):
        before = copy.deepcopy(body)

        run_inlet(filter_instance, body, metadata)

        assert body == before


def test_empty_valve_is_disabled_by_default():
    body = eligible_body()
    before = copy.deepcopy(body)

    run_inlet(MODULE.Filter(), body, native_metadata())

    assert body == before
