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


def generic_delegation_spec():
    # Actual community Tool advertises a general 3+ steps mandatory delegate.
    return {"name": "run_sub_agent", "description": "Delegate a task to a sub-agent for autonomous completion. MANDATORY: 3+ steps MUST delegate.",
            "parameters": {"type": "object", "required": ["description", "prompt"], "properties": {
                "description": {"type": "string", "description": "Brief task summary shown to the user"},
                "prompt": {"type": "string", "description": "Detailed instructions for the sub-agent; this can be written in any language that best suits the task."}}}}


@pytest.mark.parametrize("flat", [False, True])
@pytest.mark.parametrize("provider_copy", [False, True])
def test_corporate_schema_scopes_generic_delegate_without_mutating_factory(flat, provider_copy):
    spec = generic_delegation_spec()
    provider_spec = copy.deepcopy(spec) if provider_copy else spec
    schema = {"type": "function", **provider_spec} if flat else {"type": "function", "function": provider_spec}
    original = copy.deepcopy(spec)
    original_schema = copy.deepcopy(schema)
    async def delegate(description, prompt): pass
    source_tool = {"tool_id": "corporate_document_delegation", "spec": spec, "callable": delegate}
    tools = {"run_sub_agent": source_tool}
    body = {"tools": [schema]}
    MODULE._scope_corporate_delegation_schema(body, tools)
    adapted = tools["run_sub_agent"]["spec"]
    assert adapted["description"] == MODULE.CORPORATE_DELEGATION_DESCRIPTION
    assert adapted["parameters"]["properties"]["prompt"]["description"] == MODULE.CORPORATE_DELEGATION_PROMPT_DESCRIPTION
    restored = copy.deepcopy(adapted)
    restored["description"] = original["description"]
    restored["parameters"]["properties"]["prompt"]["description"] = original["parameters"]["properties"]["prompt"]["description"]
    assert restored == original  # Same name, argument types, required list and fields.
    assert body["tools"][0].get("function", body["tools"][0])["description"] == adapted["description"]
    assert spec == original and schema == original_schema
    assert source_tool["spec"] is spec and source_tool["callable"] is delegate
    assert tools["run_sub_agent"]["callable"] is delegate
    before = copy.deepcopy(body)
    MODULE._scope_corporate_delegation_schema(body, tools)
    assert body == before


def test_corporate_schema_preserves_same_named_foreign_tool_and_shared_schema():
    owned, foreign = generic_delegation_spec(), generic_delegation_spec()
    other_tool = {"tool_id": "other", "spec": foreign}
    tools = {"owned": {"tool_id": "corporate_document_delegation", "spec": owned}, "foreign": other_tool}
    schemas = [{"type": "function", "function": s} for s in (owned, foreign)]
    original = copy.deepcopy(schemas)
    body = {"tools": schemas}
    MODULE._scope_corporate_delegation_schema(body, tools)
    assert body["tools"][0]["function"]["description"] == MODULE.CORPORATE_DELEGATION_DESCRIPTION
    assert body["tools"][1] is schemas[1] and tools["foreign"] is other_tool
    assert schemas == original and foreign == original[1]["function"]


@pytest.mark.parametrize("excluded", ["worker", "other_model", "explicit_caller", "auxiliary", "unsaved"])
def test_corporate_schema_request_preserves_excluded_routes(native_guard_context, excluded):
    spec = generic_delegation_spec()
    tool = {"tool_id": "corporate_document_delegation", "spec": spec}
    metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "ui", "chat_id": "saved-chat", "tools": {"run_sub_agent": tool}}
    body = {"model": "gpt-6-luna", "tools": [{"type": "function", "function": spec}]}
    if excluded == "worker": body["model"] = "corporate-office-worker"
    elif excluded == "other_model": body["model"] = "other-model"
    elif excluded == "explicit_caller": metadata.pop(MODULE.WORKFLOW_REQUEST_MARKER)
    elif excluded == "auxiliary": metadata["task"] = "title_generation"
    elif excluded == "unsaved": metadata["chat_id"] = "local-chat"
    before = copy.deepcopy(body)
    asyncio.run(configured_filter().request(body, __metadata__=metadata, __user__={"id": "user"}))
    assert body == before and metadata["tools"]["run_sub_agent"] is tool


def test_corporate_schema_request_retains_native_callable_guard_and_idempotence(native_guard_context):
    async def delegate(description, prompt, __messages__=None): return "unused"
    async def scenario():
        function = await native_guard_context["bind"](delegate, {"__messages__": ["original"]})
        source_tool = {"tool_id": "corporate_document_delegation", "spec": generic_delegation_spec(), "callable": function}
        original_spec = copy.deepcopy(source_tool["spec"])
        metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "ui", "chat_id": "saved-chat", "tools": {"run_sub_agent": source_tool}}
        body = {"model": "gpt-6-luna", "tools": [{"type": "function", "function": source_tool["spec"]}]}
        instance = configured_filter()
        await instance.request(body, __metadata__=metadata, __user__={"id": "user"})
        guarded = metadata["tools"]["run_sub_agent"]["callable"]
        assert guarded._office_tasks_guard and guarded.__signature__ == function.__signature__
        assert source_tool["callable"] is function and source_tool["spec"] == original_spec
        await instance.request(body, __metadata__=metadata, __user__={"id": "user"})
        assert metadata["tools"]["run_sub_agent"]["callable"] is guarded
        assert native_guard_context["reads"] == [] and native_guard_context["writes"] == []
    asyncio.run(scenario())


@pytest.fixture
def native_template_context(native_guard_context, monkeypatch):
    import sys
    import types
    from fastapi import HTTPException
    state = native_guard_context
    state.update(skill_reads=[], snapshot_reads=[], denied=set(), inactive=set(), snapshots={}, native_errors={})
    state["native_http_error"] = HTTPException

    def published(skill_id):
        content = (f"# Fill {skill_id}\nRepeat every mapped field. Preserve the note and footer.\n"
                   f"\n## Original template\n\nOriginal native File ID: `source-{skill_id}`.\n"
                   "Template Knowledge ID: `library`.\n"
                   f"[Download original DOCX](/api/v1/files/source-{skill_id}/content).\n"
                   "Retrieve this original with the existing OfficeCLI file workflow, make a new copy, "
                   "and fill that copy. Preserve the original document and its formatting.\n")
        return {"name": f'Pinned "{skill_id}"', "content": content,
                "data": {"files": [{"path": "SKILL.md", "content": content}]}}

    state["published"] = published
    state["snapshots"][("artifact-workflow", "root-v")] = {"content": "Shared root"}
    state["snapshots"][("template-a", "read-v")] = published("template-a")
    state["metadata"] = {"chat_context": {"skill_versions": {"artifact-workflow": "root-v", "template-a": "read-v"}}}

    async def authorized(skill_id, user):
        state["skill_reads"].append((skill_id, user.id))
        if skill_id in state["native_errors"]:
            raise state["native_errors"][skill_id]
        if skill_id in state["denied"]:
            raise HTTPException(403, "Native read ACL denied")
        return types.SimpleNamespace(id=skill_id, name="Changed current name", version_id="current-v",
                                     is_active=skill_id not in state["inactive"])

    async def snapshot(skill, version):
        state["snapshot_reads"].append((skill.id, version))
        if (skill.id, version) not in state["snapshots"]:
            raise HTTPException(404, "Native pinned snapshot not found")
        return copy.deepcopy(state["snapshots"][(skill.id, version)])

    def overview(content, files, tools_enabled=True):
        assert tools_enabled is False and files == []
        return {"content": content[:100000], "next_offset": 100000 if len(content) > 100000 else None}

    for module_name, attrs in {
        "open_webui.routers.skills": {"authorized_skill": authorized},
        "open_webui.models.skills": {"get_skill_snapshot": snapshot},
        "open_webui.utils.skill_files": {"skill_overview": overview,
                                         "format_skill_content": lambda page, sid, enabled: page["content"]},
    }.items():
        module = types.ModuleType(module_name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, module_name, module)
    return state


def handoff(state, prompt="Fill using agreed facts", messages=None):
    return asyncio.run(MODULE._template_handoff_messages(
        prompt, messages if messages is not None else [{"role": "system", "content": "Parent root"}],
        state["metadata"], {"id": "user"},
    ))


def test_template_handoff_uses_authorized_pinned_complete_snapshot_without_parent_mutation(native_template_context):
    state = native_template_context
    root = state["snapshots"][("template-a", "read-v")]["content"]
    messages = [{"role": "system", "content": "Parent root"},
                {"role": "tool", "content": root}]  # view_skill results are not transferable system tags.
    before, metadata_before = copy.deepcopy(messages), copy.deepcopy(state["metadata"])
    result = handoff(state, messages=messages)
    assert messages == before and state["metadata"] == metadata_before
    assert result[-1]["role"] == "system" and result[-1]["content"].count(root) == 1
    assert 'name="Pinned &quot;template-a&quot;"' in result[-1]["content"]
    assert "Preserve the note and footer." in result[-1]["content"]
    assert ("template-a", "read-v") in state["snapshot_reads"]
    assert all(user == "user" for sid, user in state["skill_reads"])
    result[0]["content"] = "Child change"
    assert messages == before


@pytest.mark.parametrize("where", ["prompt", "system"])
def test_template_handoff_does_not_duplicate_already_complete_transfer(native_template_context, where):
    state = native_template_context
    root = state["snapshots"][("template-a", "read-v")]["content"]
    tag = f'<skill id="template-a" name="Pinned">\n{root}\n</skill>'
    messages = [{"role": "system", "content": tag if where == "system" else "Parent root"}]
    prompt = root if where == "prompt" else "Fill agreed facts"
    result = handoff(state, prompt, messages)
    assert result == messages and result is not messages
    assert prompt.count(root) + sum(message["content"].count(root) for message in result) == 1


def test_template_selection_requires_explicit_exact_id_when_multiple_read(native_template_context):
    state = native_template_context
    state["snapshots"][("template-b", "b-v")] = state["published"]("template-b")
    state["metadata"]["chat_context"]["skill_versions"]["template-b"] = "b-v"
    for prompt in ("Fill the last template", "template-a-extra", "template-a and template-b"):
        with pytest.raises(ValueError, match="exactly one Skill ID"):
            handoff(state, prompt)
    result = handoff(state, "Use Skill `template-a` with these agreed facts")
    assert state["snapshots"][("template-a", "read-v")]["content"] in result[-1]["content"]
    assert state["snapshots"][("template-b", "b-v")]["content"] not in result[-1]["content"]


@pytest.mark.parametrize("failure", ["no_template", "denied", "inactive", "missing_pin", "mismatched_file",
                                      "supporting_file", "encoded", "too_large", "invalid_binding"])
def test_template_handoff_fails_before_delegation_on_incomplete_or_unauthorized_source(native_template_context, failure):
    state = native_template_context
    template = state["snapshots"][("template-a", "read-v")]
    if failure == "no_template": state["metadata"]["chat_context"]["skill_versions"].pop("template-a")
    elif failure == "denied": state["denied"].add("template-a")
    elif failure == "inactive": state["inactive"].add("template-a")
    elif failure == "missing_pin": state["snapshots"].pop(("template-a", "read-v"))
    elif failure == "mismatched_file": template["data"]["files"][0]["content"] = "Different"
    elif failure == "supporting_file": template["data"]["files"].append({"path": "map.md", "content": "Additional rules"})
    elif failure == "encoded": template["data"]["files"][0]["encoding"] = "base64"
    elif failure == "too_large":
        template["content"] = "x" * 100001 + template["content"]
        template["data"]["files"][0]["content"] = template["content"]
    elif failure == "invalid_binding": template["content"] = template["content"].replace("/source-template-a/content", "/foreign/content")
    with pytest.raises((ValueError, state["native_http_error"])):
        handoff(state)
    assert not state["writes"]


@pytest.mark.parametrize("kind", ["duplicate_prompt", "duplicate_system", "prompt_and_system", "partial_tag", "untagged_system", "foreign_tag", "body_id"])
def test_template_handoff_rejects_conflicting_transfer_context(native_template_context, kind):
    state = native_template_context
    root = state["snapshots"][("template-a", "read-v")]["content"]
    tag = f'<skill id="template-a" name="Pinned">\n{root}\n</skill>'
    prompt, content = "Agreed facts", "Parent root"
    if kind == "duplicate_prompt": prompt = root * 2
    elif kind == "duplicate_system": content = tag * 2
    elif kind == "prompt_and_system": prompt, content = root, tag
    elif kind == "partial_tag": content = '<skill id="template-a" name="Pinned">\nShort excerpt\n</skill>'
    elif kind == "foreign_tag": content = f'<skill id="other-skill" name="Other">\n{root}\n</skill>'
    elif kind == "body_id": content = f'<skill id="other-skill" name="Other">\nid="template-a"\n{root}\n</skill>'
    else: content = root
    with pytest.raises(ValueError):
        handoff(state, prompt, [{"role": "system", "content": content}])


def test_corporate_guard_transfers_only_temporary_fresh_messages_and_keeps_public_prompt(native_template_context):
    state = native_template_context
    state["tasks"] = [{"content": "Fill and verify", "status": "in_progress"}]
    parent = [{"role": "system", "content": "Fresh parent root"}]
    async def delegate(description, prompt, __messages__=None, __metadata__=None, __user__=None):
        state["writes"].append((description, prompt, copy.deepcopy(__messages__)))
        __messages__[0]["content"] = "Child-only modification"
        return "delegated"
    async def scenario():
        metadata = {**state["metadata"], MODULE.WORKFLOW_REQUEST_MARKER: True,
                    "session_id": "ui", "chat_id": "saved-chat", "tools": {}}
        tool = {"tool_id": "corporate_document_delegation", "spec": {"name": "run_sub_agent"},
                "callable": await state["bind"](delegate, {"__messages__": [{"role": "system", "content": "Stale"}],
                                                         "__metadata__": metadata, "__user__": {"id": "user"}})}
        metadata["tools"]["run_sub_agent"] = tool
        factory_callable = tool["callable"]
        instance = configured_filter()
        await instance.request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        guarded = metadata["tools"]["run_sub_agent"]["callable"]
        await instance.request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        assert metadata["tools"]["run_sub_agent"]["callable"] is guarded
        assert tool["callable"] is factory_callable
        fresh = await state["bind"](guarded.__function__, {**guarded.__extra_params__, "__messages__": parent})
        for _ in range(2):
            assert await fresh(description="Fill", prompt="Exact agreed facts") == "delegated"
        assert parent == [{"role": "system", "content": "Fresh parent root"}]
        root = state["snapshots"][("template-a", "read-v")]["content"]
        for description, prompt, messages in state["writes"]:
            assert (description, prompt) == ("Fill", "Exact agreed facts")
            assert messages[0] == parent[0]
            assert messages[-1]["content"].count(root) == 1
    asyncio.run(scenario())


def test_unrelated_delegation_owner_does_not_receive_corporate_skill_handoff(native_template_context):
    state = native_template_context
    state["tasks"] = [{"content": "Other task", "status": "pending"}]
    async def delegate(prompt, __messages__=None):
        state["writes"].append(__messages__)
        return "delegated"
    async def scenario():
        parent = [{"role": "system", "content": "Other context"}]
        tool = {"tool_id": "other", "spec": {"name": "run_sub_agent"},
                "callable": await state["bind"](delegate, {"__messages__": parent})}
        metadata = {MODULE.WORKFLOW_REQUEST_MARKER: True, "session_id": "ui", "chat_id": "saved-chat",
                    "tools": {"run_sub_agent": tool}}
        await configured_filter().request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        assert await tool["callable"](prompt="Other task") == "delegated"
        assert state["writes"] == [parent] and not state["skill_reads"]
    asyncio.run(scenario())


def test_ordinary_office_delegation_without_template_is_blocked_before_original_call(native_template_context):
    state = native_template_context
    state["tasks"] = [{"content": "Create ordinary presentation", "status": "pending"}]
    state["metadata"]["chat_context"]["skill_versions"].pop("template-a")
    async def delegate(description, prompt, __messages__=None, __metadata__=None):
        state["writes"].append(prompt)
        return "must not run"
    async def scenario():
        metadata = {**state["metadata"], MODULE.WORKFLOW_REQUEST_MARKER: True,
                    "session_id": "ui", "chat_id": "saved-chat", "tools": {}}
        tool = {"tool_id": "corporate_document_delegation", "spec": {"name": "run_sub_agent"},
                "callable": await state["bind"](delegate, {"__messages__": [], "__metadata__": metadata})}
        metadata["tools"]["run_sub_agent"] = tool
        await configured_filter().request({"model": "gpt-6-sol"}, __metadata__=metadata, __user__={"id": "user"})
        with pytest.raises(ValueError, match="Use OfficeCLI tools directly for ordinary Office files"):
            await metadata["tools"]["run_sub_agent"]["callable"](description="Create slides", prompt="Make an ordinary PPTX")
        assert not state["writes"]
    asyncio.run(scenario())


def test_published_original_direct_write_is_blocked_after_tasks_before_side_effect(native_template_context):
    state = native_template_context
    async def remote(**kwargs):
        state["writes"].append(kwargs)
        return "written"
    async def scenario():
        metadata = {**state["metadata"], MODULE.WORKFLOW_REQUEST_MARKER: True,
                    "session_id": "ui", "chat_id": "saved-chat", "tools": {}}
        tool = {"tool_id": MODULE.OFFICECLI_TOOL_ID, "spec": {"name": "apply_office_batch"},
                "callable": await state["bind"](remote, {})}
        metadata["tools"]["apply_office_batch"] = tool
        instance = configured_filter()
        await instance.request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        guarded = tool["callable"]
        await instance.request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        assert tool["callable"] is guarded
        fresh = await state["bind"](guarded.__function__, guarded.__extra_params__)
        commands = [{"command": "set", "path": "/body/p[1]"}] * 2
        with pytest.raises(ValueError, match="create_tasks"):
            await fresh(file_id="source-template-a", commands=commands)
        assert not state["writes"] and not state["snapshot_reads"]
        state["tasks"] = [{"content": "Fill agreed template", "status": "pending"}]
        before = copy.deepcopy(metadata["chat_context"])
        with pytest.raises(ValueError, match="Use run_sub_agent.*template-a"):
            await fresh(file_id="source-template-a", commands=commands)
        assert not state["writes"]
        assert ("template-a", "read-v") in state["snapshot_reads"]
        assert metadata["chat_context"] == before
        # A completed copy has its own ID and stays on the ordinary edit route.
        assert await fresh(file_id="filled-copy-id", commands=commands) == "written"
        state["tasks"] = []
        assert await fresh(file_id="ordinary-file-id", commands=commands[:1]) == "written"
        assert [write["file_id"] for write in state["writes"]] == ["filled-copy-id", "ordinary-file-id"]
        with pytest.raises(ValueError, match="Use run_sub_agent"):
            await fresh(file_id="source-template-a", commands=commands[:1])
        # Reading the authorized native authoring owner enables revisions without
        # granting a role/profile blanket bypass or skipping the Tasks policy.
        metadata["chat_context"]["skill_versions"]["corporate-template-authoring"] = "author-v"
        state["snapshots"][("corporate-template-authoring", "author-v")] = {"content": "Native authoring workflow"}
        assert await fresh(file_id="source-template-a", commands=commands[:1]) == "written"
        with pytest.raises(ValueError, match="create_tasks"):
            await fresh(file_id="source-template-a", commands=commands)
    asyncio.run(scenario())


def test_direct_template_check_does_not_guess_unread_binding_or_missing_file_id(native_template_context):
    state = native_template_context
    state["metadata"]["chat_context"]["skill_versions"].pop("template-a")
    # The template exists in native storage fixtures, but was not read/pinned.
    asyncio.run(MODULE._require_corporate_template_route("source-template-a", state["metadata"], {"id": "user"}))
    before = list(state["skill_reads"])
    asyncio.run(MODULE._require_corporate_template_route(None, state["metadata"], {"id": "user"}))
    assert state["skill_reads"] == before


def test_same_named_other_owner_direct_edit_keeps_original_route(native_template_context):
    state = native_template_context
    async def write(file_id, commands):
        state["writes"].append(file_id)
        return "written"
    async def scenario():
        tool = {"tool_id": "other", "spec": {"name": "apply_office_batch"},
                "callable": await state["bind"](write, {})}
        metadata = {**state["metadata"], MODULE.WORKFLOW_REQUEST_MARKER: True,
                    "session_id": "ui", "chat_id": "saved-chat", "tools": {"apply_office_batch": tool}}
        await configured_filter().request({"model": "gpt-6-luna"}, __metadata__=metadata, __user__={"id": "user"})
        assert await tool["callable"](file_id="source-template-a", commands=[{"command": "set", "path": "/body/p[1]"}]) == "written"
        assert state["writes"] == ["source-template-a"] and not state["skill_reads"]
    asyncio.run(scenario())


@pytest.mark.parametrize("condition", ["inactive", "denied", "missing_snapshot"])
def test_unrelated_native_pins_do_not_block_ordinary_or_filled_copy_edits(native_template_context, condition):
    state = native_template_context
    state["metadata"]["chat_context"]["skill_versions"]["unrelated"] = "old-v"
    state["snapshots"][("unrelated", "old-v")] = {"content": "Unrelated read-only instructions"}
    if condition == "inactive": state["inactive"].add("unrelated")
    elif condition == "denied": state["denied"].add("unrelated")
    else: state["snapshots"].pop(("unrelated", "old-v"))
    for file_id in ("ordinary-file", "filled-copy-id"):
        asyncio.run(MODULE._require_corporate_template_route(file_id, state["metadata"], {"id": "user"}))
    # An authorized original still has an exact binding despite unrelated pins.
    with pytest.raises(ValueError, match="Use run_sub_agent"):
        asyncio.run(MODULE._require_corporate_template_route("source-template-a", state["metadata"], {"id": "user"}))


@pytest.mark.parametrize("condition", ["valid", "not_read", "denied", "inactive", "missing_snapshot", "empty_snapshot"])
def test_only_authorized_active_pinned_authoring_owner_exempts_original_route(native_template_context, condition):
    state = native_template_context
    pins = state["metadata"]["chat_context"]["skill_versions"]
    if condition != "not_read":
        pins["corporate-template-authoring"] = "author-read-v"
    state["snapshots"][("corporate-template-authoring", "author-read-v")] = {"content": "Prepare, agree and publish corporate templates"}
    if condition == "denied": state["denied"].add("corporate-template-authoring")
    elif condition == "inactive": state["inactive"].add("corporate-template-authoring")
    elif condition == "missing_snapshot": state["snapshots"].pop(("corporate-template-authoring", "author-read-v"))
    elif condition == "empty_snapshot": state["snapshots"][("corporate-template-authoring", "author-read-v")]["content"] = " "
    if condition == "valid":
        asyncio.run(MODULE._require_corporate_template_route("source-template-a", state["metadata"], {"id": "user"}))
        assert ("corporate-template-authoring", "author-read-v") in state["snapshot_reads"]
    else:
        # Admin status does not turn consumer filling into an authoring workflow.
        with pytest.raises(ValueError, match="Use run_sub_agent"):
            asyncio.run(MODULE._require_corporate_template_route("source-template-a", state["metadata"], {"id": "user", "role": "admin"}))


def test_inactive_known_original_stays_gated_but_unexpected_native_errors_are_not_hidden(native_template_context):
    state = native_template_context
    state["inactive"].add("template-a")
    with pytest.raises(ValueError, match="Use run_sub_agent"):
        asyncio.run(MODULE._require_corporate_template_route("source-template-a", state["metadata"], {"id": "user"}))
    state["metadata"]["chat_context"]["skill_versions"]["unrelated"] = "old-v"
    state["native_errors"]["unrelated"] = state["native_http_error"](500, "Native storage unavailable")
    with pytest.raises(state["native_http_error"]) as failure:
        asyncio.run(MODULE._require_corporate_template_route("ordinary-file", state["metadata"], {"id": "user"}))
    assert failure.value.status_code == 500
