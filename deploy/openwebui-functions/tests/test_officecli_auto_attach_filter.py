from __future__ import annotations

import asyncio
import copy
import importlib.util
import pytest
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
    instance.valves = instance.Valves(
        target_model_ids=MODULE.DEFAULT_TARGET_MODEL_IDS,
        multi_xlsx_native_model_ids=MODULE.DEFAULT_TARGET_MODEL_IDS,
    )
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


def test_default_catalog_covers_exactly_the_eleven_qualified_direct_models():
    expected = {
        "claude-opus-5",
        "claude-sonnet-4-6",
        "gpt-5.4-mini",
        "gpt-5.6-luna",
        "models/gemini-3.5-flash",
        "models/gemini-3.6-flash",
        "models/gemini-3.1-flash-lite",
        "models/gemini-3.5-flash-lite",
        "gpt-6-luna",
        "gpt-6-sol",
        "claude-opus-5-5",
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


def xlsx_files():
    return [
        {"type": "file", "id": "jan-id", "url": "jan-id", "name": "January.xlsx"},
        {"type": "file", "id": "feb-id", "url": "feb-id", "name": "February.xlsx"},
    ]


def test_multiple_xlsx_select_native_owner_before_tool_resolution():
    body = {**eligible_body(), "files": xlsx_files()}
    metadata = {"chat_id": "chat", "params": {"temperature": 0.2}}
    files_before = copy.deepcopy(body["files"])
    instance = configured_filter()
    run_inlet(instance, body, metadata)
    run_inlet(instance, body, metadata)
    assert metadata["params"] == {"temperature": 0.2, "function_calling": "native"}
    assert body["files"] == files_before
    assert body["tool_ids"].count("server:officecli") == 1
    instruction = body["messages"][0]["content"]
    assert instruction.count(MODULE.MULTI_XLSX_INSTRUCTION_MARKER) == 1
    assert "explicit file_id before deriving" in instruction
    assert "create_office_spreadsheet after reading" in instruction


def test_single_duplicate_or_non_xlsx_references_do_not_change_execution_mode():
    for files in ([xlsx_files()[0]], [xlsx_files()[0]] * 2,
                  [xlsx_files()[0], {"type": "file", "id": "word", "name": "a.docx"}],
                  [{"type": "folder", "id": "a", "name": "a.xlsx"}, xlsx_files()[0]]):
        body = {**eligible_body(), "files": files}
        metadata = {"params": {}}
        run_inlet(configured_filter(), body, metadata)
        assert metadata["params"] == {}
        assert MODULE.MULTI_XLSX_INSTRUCTION_MARKER not in body["messages"][0]["content"]


def test_multiple_xlsx_do_not_override_task_explicit_tools_or_unqualified_model():
    for model, task, tools in (("claude-opus-5", "title_generation", None),
                                ("office-documents", None, None),
                                ("claude-opus-5", None, [])):
        body = {**eligible_body(), "model": model, "files": xlsx_files()}
        if tools is not None:
            body["tools"] = tools
        metadata = {"params": {}}
        if task:
            metadata["task"] = task
        before = copy.deepcopy(body)
        run_inlet(configured_filter(), body, metadata)
        assert body == before
        assert metadata["params"] == {}


def test_native_multi_xlsx_routing_can_be_disabled_without_disabling_officecli():
    instance = configured_filter()
    instance.valves.multi_xlsx_native_model_ids = ""
    body = {**eligible_body(), "files": xlsx_files()}
    metadata = {"params": {}}
    run_inlet(instance, body, metadata)
    assert "server:officecli" in body["tool_ids"]
    assert metadata["params"] == {}


def test_followup_with_files_retains_native_route_without_new_upload():
    body = {**eligible_body(), "files": xlsx_files()}
    body["messages"][-1]["content"] = "Recalculate the output using the same inputs."
    metadata = {"params": {}}
    run_inlet(configured_filter(), body, metadata)
    assert metadata["params"]["function_calling"] == "native"


def test_already_published_office_alias_can_be_explicitly_qualified():
    instance = configured_filter()
    instance.valves.target_model_ids += ",office-documents"
    instance.valves.multi_xlsx_native_model_ids += ",office-documents"
    body = {**eligible_body(), "model": "office-documents", "files": xlsx_files(),
            "tool_ids": ["server:officecli"]}
    metadata = {"params": {}}
    run_inlet(instance, body, metadata)
    assert body["tool_ids"] == ["server:officecli"]
    assert metadata["params"]["function_calling"] == "native"
    assert MODULE.MULTI_XLSX_INSTRUCTION_MARKER in body["messages"][0]["content"]


@pytest.mark.parametrize("model", ["gpt-5.6-luna", "gpt-6-luna", "gpt-6-sol"])
def test_provider_compatibility_is_explicit_and_does_not_silently_lower_requested_reasoning(model):
    instance = configured_filter()
    instance.valves.multi_xlsx_no_reasoning_model_ids = "gpt-5.6-luna,gpt-6-luna,gpt-6-sol"
    body = {**eligible_body(), "model": model, "files": xlsx_files()}
    run_inlet(instance, body, {"params": {}})
    assert body["reasoning_effort"] == "none"
    requested = {**eligible_body(), "model": model, "files": xlsx_files(), "reasoning_effort": "high"}
    with pytest.raises(ValueError, match="cannot combine reasoning"):
        run_inlet(instance, requested, {"params": {"reasoning_effort": "high"}})
    assert requested["reasoning_effort"] == "high"
    single = {**eligible_body(), "model": model, "files": [xlsx_files()[0]]}
    run_inlet(instance, single, {"params": {}})
    assert "reasoning_effort" not in single
