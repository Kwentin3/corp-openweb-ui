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
    assert body["tool_ids"] == ["server:other", "server:officecli", *MODULE.CORPORATE_TOOL_IDS]
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
    assert gemini_body["tool_ids"] == ["server:other", "server:officecli", *MODULE.CORPORATE_TOOL_IDS]
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

    assert body["tool_ids"] == ["server:other", "server:officecli", *MODULE.CORPORATE_TOOL_IDS]
    assert MODULE.OFFICECLI_INSTRUCTION_MARKER in body["messages"][0]["content"]


@pytest.mark.parametrize("prompt", ["Create a new document", "Continue from the last result_file_id"])
def test_workflow_activates_without_current_attachments_and_preserves_user_text(prompt):
    body = eligible_body()
    body["messages"][-1]["content"] = prompt
    user_before = copy.deepcopy(body["messages"][-1])
    metadata = native_metadata()

    run_inlet(configured_filter(), body, metadata)

    assert metadata["chat_context"]["mentioned_skill_ids"] == ["artifact-workflow"]
    assert body["messages"][-1] == user_before
    assert "skill_ids" not in body
    assert "terminal_id" not in body
    assert "terminal_file_transfer" not in body["tool_ids"]


def test_workflow_activation_preserves_native_context_and_is_idempotent():
    body = eligible_body()
    instance = configured_filter()
    instance.valves.artifact_workflow_skill_id = "configured-workflow"
    context = {"mentioned_skill_ids": ["another-skill"],
               "skill_versions": {"another-skill": "version-a", "configured-workflow": "version-b"},
               "messages": [{"role": "system", "content": "Existing context"}]}
    metadata = {"params": {}, "chat_context": context}
    versions = copy.deepcopy(context["skill_versions"])
    messages = copy.deepcopy(context["messages"])

    run_inlet(instance, body, metadata)
    run_inlet(instance, body, metadata)

    assert metadata["chat_context"] is context
    assert context["mentioned_skill_ids"] == ["another-skill", "configured-workflow"]
    assert context["skill_versions"] == versions
    assert context["messages"] == messages


@pytest.mark.parametrize("files", [[], [{"type": "file", "id": "word", "name": "form.docx"}]])
def test_empty_workflow_valve_preserves_context_without_activation(files):
    instance = configured_filter()
    instance.valves.artifact_workflow_skill_id = " "
    body = {**eligible_body(), "files": files}
    metadata = {"params": {}, "chat_context": {"mentioned_skill_ids": ["another-skill"],
                "skill_versions": {"another-skill": "version-a"}}}
    context_before = copy.deepcopy(metadata["chat_context"])

    run_inlet(instance, body, metadata)

    assert metadata["chat_context"] == context_before
    assert "skill_ids" not in body
    assert "server:officecli" in body["tool_ids"]


def test_task_and_caller_supplied_tools_are_unchanged():
    filter_instance = configured_filter()
    task_body = eligible_body()
    supplied_tools_body = {**eligible_body(), "tools": []}

    for body, metadata in (
        (task_body, native_metadata(task="title_generation")),
        (supplied_tools_body, native_metadata()),
    ):
        before = copy.deepcopy(body)
        metadata_before = copy.deepcopy(metadata)

        run_inlet(filter_instance, body, metadata)

        assert body == before
        assert metadata == metadata_before


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
    assert body["tool_ids"].count("terminal_file_transfer") == 1
    assert body["skill_ids"] == ["artifact-workflow"]
    assert body["terminal_id"] == "office-linux"
    assert metadata["terminal_id"] == "office-linux"
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
        metadata_before = copy.deepcopy(metadata)
        run_inlet(configured_filter(), body, metadata)
        assert body == before
        assert metadata == metadata_before


def test_followup_with_files_retains_native_route_without_new_upload():
    body = {**eligible_body(), "files": xlsx_files()}
    body["messages"][-1]["content"] = "Recalculate the output using the same inputs."
    metadata = {"params": {}}
    run_inlet(configured_filter(), body, metadata)
    assert metadata["params"]["function_calling"] == "native"
    assert body["terminal_id"] == "office-linux"


def test_office_handoff_is_generic_and_preserves_explicit_terminal_and_selections():
    for name in ("book.XLSX", "letter.docx", "deck.pptx", "macros.xlsm"):
        body = {**eligible_body(), "files": [{"type": "file", "id": "source", "name": name}],
                "tool_ids": ["terminal_file_transfer"], "skill_ids": ["artifact-workflow"],
                "terminal_id": "user-selected"}
        metadata = {"params": {}}
        run_inlet(configured_filter(), body, metadata)
        assert body["tool_ids"] == ["terminal_file_transfer", "server:officecli", *MODULE.CORPORATE_TOOL_IDS]
        assert body["skill_ids"] == ["artifact-workflow"]
        assert body["terminal_id"] == "user-selected"
        assert "terminal_id" not in metadata


def test_non_office_chat_does_not_receive_terminal_capability():
    for files in ([], [{"type": "file", "id": "pdf", "name": "report.pdf"}],
                  [{"type": "folder", "id": "folder", "name": "book.xlsx"}]):
        body = {**eligible_body(), "files": files}
        metadata = {"params": {}}
        run_inlet(configured_filter(), body, metadata)
        assert body["tool_ids"] == ["server:other", "server:officecli", *MODULE.CORPORATE_TOOL_IDS]
        assert "skill_ids" not in body
        assert "terminal_id" not in body
        assert "terminal_id" not in metadata


def test_handoff_can_be_disabled_without_disabling_officecli():
    instance = configured_filter()
    instance.valves.terminal_transfer_tool_id = ""
    instance.valves.artifact_workflow_skill_id = ""
    instance.valves.default_terminal_id = ""
    body = {**eligible_body(), "files": xlsx_files()}
    run_inlet(instance, body, {"params": {}})
    assert body["tool_ids"] == ["server:other", "server:officecli", *MODULE.CORPORATE_TOOL_IDS]
    assert "skill_ids" not in body
    assert "terminal_id" not in body


def test_invalid_skill_contract_stops_before_any_mutation():
    body = {**eligible_body(), "files": xlsx_files(), "skill_ids": "not-a-list"}
    metadata = {"params": {}}
    before = copy.deepcopy(body)
    run_inlet(configured_filter(), body, metadata)
    assert body == before
    assert metadata == {"params": {}}


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
    assert metadata["params"] == {"temperature": 0.2, "function_calling": "native"}
    assert metadata["chat_id"] == "chat"
    assert metadata["chat_context"]["mentioned_skill_ids"] == ["artifact-workflow"]
    assert body["files"] == files
    if files:
        assert metadata["terminal_id"] == "office-linux"
        assert body["terminal_id"] == "office-linux"
        assert body["tool_ids"] == ["server:other", "server:officecli", *MODULE.CORPORATE_TOOL_IDS, "terminal_file_transfer"]
        assert body["skill_ids"] == ["artifact-workflow"]
    else:
        assert "terminal_id" not in metadata
        assert "terminal_id" not in body
        assert body["tool_ids"] == ["server:other", "server:officecli", *MODULE.CORPORATE_TOOL_IDS]
        assert "skill_ids" not in body


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
    assert len(MODULE.OFFICECLI_INSTRUCTION) < 1700


@pytest.mark.parametrize("name", sorted(MODULE.PLAN_REQUIRED_TOOLS))
def test_native_plan_policy_requires_plan_for_construction_and_corporate_lifecycle(name):
    assert MODULE._requires_native_plan(name, {})


@pytest.mark.parametrize("commands,required", [
    ([{"command": "set", "path": "/body/p[1]", "props": {"text": "New"}}], False),
    ([{"command": "set", "path": "/"}], True),
    ([{"command": "add", "path": "/body"}], True),
    ([{"command": "set", "path": "/body/p[1]"}] * 2, True),
    ([], True),
])
def test_native_plan_policy_only_exempts_single_addressed_set(commands, required):
    for name in MODULE.APPLY_TOOLS:
        assert MODULE._requires_native_plan(name, {"commands": commands}) is required
    assert not MODULE._requires_native_plan("export_answer_to_word", {})
    assert not MODULE._requires_native_plan("run_command", {})


@pytest.mark.parametrize("model", ["corporate-documents", "corporate-template-author"])
def test_optional_presets_get_shared_root_without_direct_tools(model):
    body = {**eligible_body(), "model": model}
    before = copy.deepcopy(body)
    metadata = native_metadata()
    run_inlet(configured_filter(), body, metadata)
    assert body == before
    assert metadata["chat_context"]["mentioned_skill_ids"] == ["artifact-workflow"]
    assert metadata[MODULE.WORKFLOW_REQUEST_MARKER] is True


def test_bounded_worker_is_excluded():
    body = {**eligible_body(), "model": "corporate-office-worker"}
    before, metadata = copy.deepcopy(body), native_metadata()
    metadata_before = copy.deepcopy(metadata)
    run_inlet(configured_filter(), body, metadata)
    assert body == before and metadata == metadata_before


@pytest.fixture
def native_guard_context(monkeypatch):
    import inspect
    import sys
    import types
    state = {"tasks": [], "reads": [], "writes": []}

    class Chats:
        @staticmethod
        async def get_chat_by_id_and_user_id(chat_id, user_id):
            state["reads"].append((chat_id, user_id))
            return types.SimpleNamespace(tasks=state["tasks"])

    async def bind(function, extra_params):
        signature = inspect.signature(function)
        bound = {k: v for k, v in extra_params.items() if k in signature.parameters}
        async def invoke(**kwargs):
            return await function(**{**bound, **kwargs})
        # Native binding exposes these fields and unwraps them on execution.
        invoke.__function__, invoke.__extra_params__ = function, bound
        invoke.__signature__ = signature
        invoke._office_tasks_guard = getattr(function, "_office_tasks_guard", False)
        return invoke

    for module_name, attrs in {
        "open_webui.models.chats": {"Chats": Chats},
        "open_webui.utils.chat_id": {"is_saved_chat_id": lambda value: value == "saved-chat"},
        "open_webui.utils.tools": {"get_async_tool_function_and_apply_extra_params": bind},
    }.items():
        module = types.ModuleType(module_name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, module_name, module)
    state["bind"] = bind
    return state


def test_request_guard_reads_current_native_tasks_and_preserves_fresh_binding(native_guard_context):
    state = native_guard_context

    async def write(commands=None, __messages__=None, __files__=None, __user__=None):
        state["writes"].append((commands, __messages__, __files__, __user__))
        return "written"

    async def scenario():
        tool = {"spec": {"name": "apply_office_batch", "parameters": {"properties": {"commands": {}}}},
                "callable": await state["bind"](write, {"__messages__": ["old"], "__files__": [],
                                                       "__user__": {"id": "user"}})}
        schema = copy.deepcopy(tool["spec"])
        metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "ui", "chat_id": "saved-chat",
                    "tools": {"apply_office_batch": tool}}
        instance = configured_filter()
        await instance.request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        guarded = tool["callable"]
        await instance.request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        assert tool["callable"] is guarded and tool["spec"] == schema
        # Reproduce execute_tool_call's native __function__/__extra_params__ rebind.
        fresh = await state["bind"](guarded.__function__, {**guarded.__extra_params__,
                                  "__messages__": ["fresh"], "__files__": ["file"]})
        batch = [{"command": "set", "path": "/body/p[1]"}] * 2
        for tasks in ([], [{"content": "old", "status": "completed"}],
                      [{"content": "cancelled", "status": "cancelled"}],
                      [{"content": " ", "status": "in_progress"}]):
            state["tasks"] = tasks
            with pytest.raises(ValueError, match="create_tasks"):
                await fresh(commands=batch)
        assert not state["writes"]
        state["tasks"] = [{"content": "Prepare and verify result", "status": "in_progress"}]
        assert await fresh(commands=batch) == "written"
        assert state["writes"][-1][1:] == (["fresh"], ["file"], {"id": "user"})
        state["tasks"] = []
        assert await fresh(commands=batch[:1]) == "written"
        assert state["reads"] == [("saved-chat", "user")] * 5

    asyncio.run(scenario())


def test_native_openapi_kwargs_closure_keeps_atomic_edit_exemption(native_guard_context):
    state = native_guard_context
    async def remote(**kwargs):
        state["writes"].append(kwargs)
        return "written"
    async def scenario():
        tool = {"callable": await state["bind"](remote, {}), "type": "external"}
        metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "ui", "chat_id": "saved-chat",
                    "tools": {"apply_office_batch": tool}}
        await configured_filter().request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        atomic = [{"command": "set", "path": "/body/p[1]"}]
        assert await tool["callable"](commands=atomic) == "written"
        with pytest.raises(ValueError, match="create_tasks"):
            await tool["callable"](commands=atomic * 2)
        assert state["writes"] == [{"commands": atomic}]
    asyncio.run(scenario())


@pytest.mark.parametrize("name,params,files,required", [
    ("stage_chat_file", {"file_id": "word"}, [{"id": "word", "filename": "form.DOCX"}], True),
    ("stage_chat_file", {"file_id": "word"}, [{"type": "file", "file": {"id": "word", "filename": "form.xlsx"}}], True),
    ("stage_chat_file", {"file_id": "word"}, [{"url": "word", "name": "form.pptx"}], True),
    ("stage_chat_file", {"file_id": "image"}, [{"id": "image", "name": "image.png"}], False),
    ("stage_chat_file", {"file_id": "unknown"}, [{"id": "word", "name": "form.docx"}], False),
    ("stage_chat_file", {"file_id": "word"}, [{"type": "folder", "id": "word", "name": "form.docx"}], False),
    ("publish_terminal_file", {"path": "/result/report.DOCX"}, [], True),
    ("publish_terminal_file", {"path": "/result/image.png"}, [], False),
    ("publish_terminal_file", {"path": "/result/report.csv"}, [], False),
    ("publish_terminal_file", {"path": "/result/report.pdf"}, [], False),
])
def test_terminal_boundary_uses_known_office_file_metadata_or_publication_extension(name, params, files, required):
    assert MODULE._requires_native_plan(name, params, files) is required


def test_stage_guard_uses_fresh_native_files_without_forwarding_hidden_argument(native_guard_context):
    state = native_guard_context
    async def stage(file_id, __metadata__=None):
        state["writes"].append((file_id, __metadata__))
        return "staged"
    async def scenario():
        metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "ui", "chat_id": "saved-chat",
                    "files": [{"id": "source", "name": "snapshot.png"}], "tools": {}}
        tool = {"callable": await state["bind"](stage, {"__metadata__": metadata})}
        metadata["tools"]["stage_chat_file"] = tool
        await configured_filter().request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        guarded = tool["callable"]
        fresh = await state["bind"](guarded.__function__, {**guarded.__extra_params__,
                                   "__files__": [{"id": "source", "file": {"filename": "actual.docx"}}]})
        with pytest.raises(ValueError, match="create_tasks"):
            await fresh(file_id="source")
        assert not state["writes"]
        state["tasks"] = [{"content": "Fill and verify template", "status": "pending"}]
        assert await fresh(file_id="source") == "staged"
        assert state["writes"][-1] == ("source", metadata)
        state["tasks"] = []
        assert await fresh(file_id="unknown") == "staged"
        # Without fresh __files__, the native metadata snapshot is the fallback.
        assert await guarded(file_id="source") == "staged"
        assert state["reads"] == [("saved-chat", "user")] * 2
    asyncio.run(scenario())


def test_terminal_publication_guard_blocks_office_but_preserves_image_publication(native_guard_context):
    state = native_guard_context
    async def publish(path):
        state["writes"].append(path)
        return "published"
    async def scenario():
        tool = {"callable": await state["bind"](publish, {})}
        metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "ui", "chat_id": "saved-chat",
                    "tools": {"publish_terminal_file": tool}}
        await configured_filter().request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        with pytest.raises(ValueError, match="create_tasks"):
            await tool["callable"](path="/result/protocol.docx")
        assert not state["writes"]
        assert await tool["callable"](path="/result/image.png") == "published"
        state["tasks"] = [{"content": "Prepare artifact", "status": "pending"}]
        assert await tool["callable"](path="/result/protocol.docx") == "published"
    asyncio.run(scenario())


@pytest.mark.parametrize("change", ["unmarked", "auxiliary", "no_session", "unsaved", "no_user"])
def test_request_guard_preserves_excluded_execution_routes(native_guard_context, change):
    async def write():
        return "written"
    metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "ui", "chat_id": "saved-chat",
                "tools": {"create_office_document": {"callable": write}}}
    user = {"id": "user"}
    if change == "unmarked": metadata.pop(MODULE.WORKFLOW_REQUEST_MARKER)
    elif change == "auxiliary": metadata["task"] = "title_generation"
    elif change == "no_session": metadata.pop("session_id")
    elif change == "unsaved": metadata["chat_id"] = "local-chat"
    else: user = {}
    asyncio.run(configured_filter().request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__=user))
    assert metadata["tools"]["create_office_document"]["callable"] is write
    assert not native_guard_context["reads"]


@pytest.mark.parametrize("model", ["corporate-office-worker", "unrelated-model"])
def test_request_rechecks_model_scope_with_inherited_parent_marker(native_guard_context, model):
    async def write():
        return "written"
    parallel = {"name": "run_parallel_sub_agents"}
    tools = {"create_office_document": {"callable": write},
             "run_parallel_sub_agents": {"tool_id": "corporate_document_delegation", "spec": parallel}}
    metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "inherited-ui", "chat_id": "saved-chat",
                "tools": tools}
    body = {"model": model, "tools": [{"type": "function", "function": parallel}]}
    body_before = copy.deepcopy(body)
    asyncio.run(configured_filter().request(body, __metadata__=metadata, __user__={"id": "user"}))
    assert body == body_before
    assert tools["create_office_document"]["callable"] is write
    assert tools["run_parallel_sub_agents"]["spec"] is parallel
    assert not native_guard_context["reads"]


@pytest.mark.parametrize("flat_schema", [False, True])
def test_request_removes_only_owned_parallel_variant_from_schemas_and_execution(native_guard_context, flat_schema):
    async def delegate(task):
        return "delegated"
    async def scenario():
        parallel = {"name": "run_parallel_sub_agents"}
        single = {"name": "run_sub_agent"}
        other = {"name": "other_tool"}
        tools = {
            "run_parallel_sub_agents": {"tool_id": "corporate_document_delegation", "spec": parallel},
            "run_sub_agent": {"tool_id": "corporate_document_delegation", "spec": single,
                              "callable": await native_guard_context["bind"](delegate, {})},
            "other_tool": {"tool_id": "other", "spec": other},
        }
        schemas = [dict(type="function", **spec) if flat_schema
                   else {"type": "function", "function": spec} for spec in (parallel, single, other)]
        body = {"model": "gpt-6-luna", "tools": schemas}
        metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "ui", "chat_id": "saved-chat", "tools": tools}
        instance = configured_filter()
        await instance.request(body, __metadata__=metadata, __user__={"id": "user"})
        guarded_single = tools["run_sub_agent"]["callable"]
        await instance.request(body, __metadata__=metadata, __user__={"id": "user"})
        assert set(tools) == {"run_sub_agent", "other_tool"}
        assert {spec.get("function", spec)["name"] for spec in body["tools"]} == set(tools)
        assert tools["run_sub_agent"]["callable"] is guarded_single
    asyncio.run(scenario())


def test_parallel_pruning_preserves_same_named_function_from_other_owner(native_guard_context):
    blocked = {"name": "run_parallel_sub_agents", "description": "Corporate parallel"}
    retained = {"name": "run_parallel_sub_agents", "description": "Other owner"}
    tools = {"corporate_parallel": {"tool_id": "corporate_document_delegation", "spec": blocked},
             "other_parallel": {"tool_id": "other", "spec": retained}}
    body = {"model": "gpt-6-luna", "tools": [{"type": "function", "function": spec}
                                               for spec in (blocked, retained)]}
    metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "ui", "chat_id": "saved-chat", "tools": tools}
    asyncio.run(configured_filter().request(body, __metadata__=metadata, __user__={"id": "user"}))
    assert list(tools) == ["other_parallel"]
    assert len(body["tools"]) == 1 and body["tools"][0]["function"] is retained


@pytest.mark.parametrize("excluded", ["explicit_caller", "auxiliary"])
def test_parallel_pruning_preserves_explicit_and_auxiliary_routes(native_guard_context, excluded):
    spec = {"name": "run_parallel_sub_agents"}
    tool = {"tool_id": "corporate_document_delegation", "spec": spec}
    metadata = {"session_id": "ui", "chat_id": "saved-chat", "tools": {spec["name"]: tool}}
    if excluded == "auxiliary":
        metadata.update({MODULE.WORKFLOW_REQUEST_MARKER: True, "task": "title_generation"})
    body = {"model": "gpt-6-luna", "tools": [{"type": "function", "function": spec}]}
    before = copy.deepcopy(body)
    asyncio.run(configured_filter().request(body, __metadata__=metadata, __user__={"id": "user"}))
    assert body == before and metadata["tools"][spec["name"]] is tool
