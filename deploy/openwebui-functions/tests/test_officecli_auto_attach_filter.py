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
    instance.valves = instance.Valves(target_model_ids=MODULE.DEFAULT_TARGET_MODEL_IDS)
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
    instruction = body["messages"][0]["content"]
    assert MODULE.OFFICECLI_INSTRUCTION_MARKER in instruction
    assert "never call load_officecli_skill or get_officecli_help" in instruction
    assert "create_office_document" in instruction
    assert '"parent":"/body","type":"markdown"' in instruction
    assert "create_office_spreadsheet" in instruction
    assert '"path":"/Sheet1/A1"' in instruction
    assert '"numFmt":"#,##0 ₽"' in instruction
    assert "Use formulas for requested calculations" in instruction
    assert "create_office_presentation" in instruction
    assert '"parent":"/","type":"slide"' in instruction
    assert '"x":"2cm","y":"3cm","width":"29cm","height":"3cm"' in instruction
    assert "result_file_id" in instruction
    assert "A successful create result is terminal" in instruction
    assert "inspect it first and use the matching apply batch" in instruction
    assert "table, chart, or picture" in instruction
    assert MODULE.GEMINI_COMPATIBILITY_MARKER not in instruction


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


def test_default_direct_model_catalog_includes_gemini_but_not_specialized_models():
    filter_instance = MODULE.Filter()

    gemini_body = {**eligible_body(), "model": "models/gemini-3.5-flash"}
    run_inlet(filter_instance, gemini_body, native_metadata())
    assert gemini_body["tool_ids"] == ["server:other", "server:officecli"]
    assert MODULE.GEMINI_COMPATIBILITY_MARKER not in gemini_body["messages"][0]["content"]
    assert '"parent":"/body"' in gemini_body["messages"][0]["content"]
    assert '"path":"/Sheet1/A1"' in gemini_body["messages"][0]["content"]
    assert '"parent":"/","type":"slide"' in gemini_body["messages"][0]["content"]
    assert MODULE.OFFICECLI_INSTRUCTION_MARKER in gemini_body["messages"][0]["content"]

    specialized_body = {**eligible_body(), "model": "office-documents"}
    before = copy.deepcopy(specialized_body)
    run_inlet(filter_instance, specialized_body, native_metadata())
    assert specialized_body == before


def test_default_catalog_covers_exactly_the_eight_qualified_direct_models():
    expected = {
        "claude-opus-5",
        "claude-sonnet-4-6",
        "gpt-5.4-mini",
        "gpt-5.6-luna",
        "models/gemini-3.5-flash",
        "models/gemini-3.6-flash",
        "models/gemini-3.1-flash-lite",
        "models/gemini-3.5-flash-lite",
    }

    assert MODULE._comma_separated_values(MODULE.DEFAULT_TARGET_MODEL_IDS) == expected


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


def test_empty_valve_is_still_disabled():
    body = eligible_body()
    before = copy.deepcopy(body)

    filter_instance = MODULE.Filter()
    filter_instance.valves = filter_instance.Valves(target_model_ids="")
    run_inlet(filter_instance, body, native_metadata())

    assert body == before
