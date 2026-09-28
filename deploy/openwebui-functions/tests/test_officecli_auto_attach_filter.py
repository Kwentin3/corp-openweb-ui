from __future__ import annotations

import asyncio
import copy
import json
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


def publication_body():
    url = "/api/v1/files/12345678-1234-1234-1234-123456789abc/content"
    text = f"[Download](sandbox:{url})"
    return {
        "id": "answer", "model": "gpt-6-sol",
        "messages": [{"id": "answer", "role": "assistant", "content": text, "output": [
            {"type": "function_call", "call_id": "publish", "name": "create_office_document", "status": "completed"},
            {"type": "function_call_output", "call_id": "publish", "status": "completed", "output": [
                {"type": "input_text", "text": json.dumps({
                    "result_file_id": "12345678-1234-1234-1234-123456789abc",
                    "result_file": {"id": "12345678-1234-1234-1234-123456789abc"},
                    "download_url": url,
                })},
            ]},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]},
        ]}],
    }


@pytest.mark.parametrize("tool_name", ["create_office_document", "publish_terminal_file"])
def test_outlet_repairs_proven_download_in_content_and_output_without_touching_receipt(tool_name):
    body = publication_body()
    output = body["messages"][0]["output"]
    output[0]["name"] = tool_name
    if tool_name == "publish_terminal_file":
        receipt = json.loads(output[1]["output"][0]["text"])
        receipt["status"] = "published"
        output[1]["output"][0]["text"] = json.dumps(receipt)
    evidence = copy.deepcopy(body["messages"][0]["output"][:2])
    instance = configured_filter()
    for _ in range(2):
        assert asyncio.run(instance.outlet(body)) is body
    message = body["messages"][0]
    expected = "[Download](/api/v1/files/12345678-1234-1234-1234-123456789abc/content)"
    assert message["content"] == expected
    assert message["output"][2]["content"][0]["text"] == expected
    assert message["output"][:2] == evidence


def test_outlet_does_not_treat_incomplete_terminal_publication_as_success():
    body = publication_body()
    body["messages"][0]["output"][0]["name"] = "publish_terminal_file"
    before = copy.deepcopy(body)
    asyncio.run(configured_filter().outlet(body))
    assert body == before


@pytest.mark.parametrize("mutation", ["unknown_tool", "failed", "foreign_call", "missing_call", "foreign_file", "foreign_url", "invalid_json", "wrong_turn", "user", "unlisted", "no_receipt"])
def test_outlet_does_not_invent_or_repair_unproven_downloads(mutation):
    body = publication_body()
    message = body["messages"][0]
    call, result, _ = message["output"]
    receipt = json.loads(result["output"][0]["text"])
    if mutation == "unknown_tool":
        call["name"] = "web_search"
    elif mutation == "failed":
        result["status"] = "failed"
    elif mutation == "foreign_call":
        result["call_id"] = "elsewhere"
    elif mutation == "missing_call":
        call.pop("call_id")
        result.pop("call_id")
    elif mutation == "foreign_file":
        receipt["result_file"]["id"] = "other"
    elif mutation == "foreign_url":
        receipt["download_url"] = "https://elsewhere.example/download"
    elif mutation == "wrong_turn":
        body["id"] = "other"
    elif mutation == "user":
        message["role"] = "user"
    elif mutation == "unlisted":
        body["model"] = "specialized-pipe"
    elif mutation == "no_receipt":
        result["output"] = []
    if result["output"]:
        result["output"][0]["text"] = "not JSON" if mutation == "invalid_json" else json.dumps(receipt)
    before = copy.deepcopy(body)
    asyncio.run(configured_filter().outlet(body))
    assert body == before


def test_outlet_scopes_to_current_message_and_preserves_unknown_links_and_auxiliary_tasks():
    body = publication_body()
    prior = copy.deepcopy(body["messages"][0])
    prior["id"] = "prior"
    body["messages"].insert(0, prior)
    unknown = " [Other](sandbox:/api/v1/files/unknown/content) [Web](https://example.com)"
    body["messages"][-1]["content"] += unknown
    before = copy.deepcopy(body)
    asyncio.run(configured_filter().outlet(body, __metadata__={"task": "title_generation"}))
    assert body == before
    asyncio.run(configured_filter().outlet(body))
    assert body["messages"][0] == before["messages"][0]
    assert body["messages"][-1]["content"].endswith(unknown)


def configured_filter():
    instance = MODULE.Filter()
    instance.valves = instance.Valves(
        target_model_ids=MODULE.DEFAULT_TARGET_MODEL_IDS,
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
    assert "load_officecli_skill" in instruction
    assert "get_officecli_help" in instruction
    assert body["messages"][-1] == eligible_body()["messages"][-1]



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
    assert instruction.count(MODULE.OFFICECLI_INSTRUCTION_MARKER) == 1
    assert instruction == run_inlet(configured_filter(), eligible_body(), native_metadata())["messages"][0]["content"]


def test_single_duplicate_or_non_xlsx_references_use_native_without_multi_xlsx_guidance():
    for files in ([xlsx_files()[0]], [xlsx_files()[0]] * 2,
                  [xlsx_files()[0], {"type": "file", "id": "word", "name": "a.docx"}],
                  [{"type": "folder", "id": "a", "name": "a.xlsx"}, xlsx_files()[0]]):
        body = {**eligible_body(), "files": files}
        metadata = {"params": {}}
        run_inlet(configured_filter(), body, metadata)
        assert metadata["params"] == {"function_calling": "native"}
        assert MODULE.OFFICECLI_INSTRUCTION_MARKER in body["messages"][0]["content"]


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


def test_followup_with_files_retains_native_route_without_new_upload():
    body = {**eligible_body(), "files": xlsx_files()}
    body["messages"][-1]["content"] = "Recalculate the output using the same inputs."
    metadata = {"params": {}}
    run_inlet(configured_filter(), body, metadata)
    assert metadata["params"]["function_calling"] == "native"


@pytest.mark.parametrize("model", ["gpt-5.6-luna", "gpt-6-luna", "gpt-6-sol"])
def test_provider_compatibility_is_explicit_and_does_not_silently_lower_requested_reasoning(model):
    instance = configured_filter()
    body = {**eligible_body(), "model": model, "files": xlsx_files()}
    run_inlet(instance, body, {"params": {}})
    assert body["reasoning_effort"] == "none"
    requested = {**eligible_body(), "model": model, "files": xlsx_files(), "reasoning_effort": "high"}
    with pytest.raises(ValueError, match="cannot combine reasoning"):
        run_inlet(instance, requested, {"params": {"reasoning_effort": "high"}})
    assert requested["reasoning_effort"] == "high"
    single = {**eligible_body(), "model": model, "files": [xlsx_files()[0]]}
    run_inlet(instance, single, {"params": {}})
    assert single["reasoning_effort"] == "none"


@pytest.mark.parametrize("model", MODULE.DEFAULT_TARGET_MODEL_IDS.split(","))
@pytest.mark.parametrize("files", [[], [{"type": "file", "id": "word", "name": "form.docx"}],
    [{"type": "file", "id": "deck", "name": "deck.pptx"}],
    [{"type": "file", "id": "word", "name": "form.docx"}, {"type": "file", "id": "deck", "name": "deck.pptx"}]])
def test_native_office_route_is_independent_of_format_and_attachment_count(model, files):
    instance = configured_filter()
    body = {**eligible_body(), "model": model, "files": copy.deepcopy(files)}
    metadata = {"params": {"temperature": 0.2, "function_calling": "default"}, "chat_id": "chat"}
    run_inlet(instance, body, metadata)
    assert metadata == {"params": {"temperature": 0.2, "function_calling": "native"}, "chat_id": "chat"}
    assert body["files"] == files
    assert body["tool_ids"] == ["server:other", "server:officecli"]


@pytest.mark.parametrize("files", [[], [{"type": "file", "id": "word", "name": "form.docx"}],
    [{"type": "file", "id": "deck", "name": "deck.pptx"}]])
@pytest.mark.parametrize("model", ["gpt-5.6-luna", "gpt-6-luna", "gpt-6-sol"])
def test_reasoning_rejection_precedes_mutation_for_every_office_format(model, files):
    body = {**eligible_body(), "model": model, "files": files, "reasoning_effort": "high"}
    metadata = {"params": {"function_calling": "default"}}
    before = copy.deepcopy(body)
    with pytest.raises(ValueError, match="cannot combine reasoning with Office tools"):
        run_inlet(configured_filter(), body, metadata)
    assert body == before
    assert metadata == {"params": {"function_calling": "default"}}


@pytest.mark.parametrize("prompt", ["List the sheets without edits", "Analyze the uploaded report", "Create a document", "Edit slide 2"])
def test_file_count_and_task_do_not_select_a_business_recipe(prompt):
    results = []
    for files in ([], xlsx_files()[:1], xlsx_files()):
        body = {**eligible_body(), "files": files}
        body["messages"][-1]["content"] = prompt
        run_inlet(configured_filter(), body, native_metadata())
        assert body["messages"][-1]["content"] == prompt
        results.append(body["messages"][0]["content"])
    assert len(set(results)) == 1
    assert len(MODULE.OFFICECLI_INSTRUCTION) < 1500
