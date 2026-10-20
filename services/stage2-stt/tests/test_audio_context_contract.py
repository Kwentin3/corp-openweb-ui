"""Observable chat contracts, with only native I/O and STT transport substituted."""

from __future__ import annotations

import copy
import sys
from types import ModuleType, SimpleNamespace

import httpx
import pytest

from openwebui_filters.stage2_audio_context_filter import (
    DEFAULT_INITIAL_RESPONSE_INSTRUCTION,
    Filter,
)


PROTOCOL = (
    "[00:00-00:04] Спикер 1:\nЕсли проверка пройдёт, перенесём встречу.\n\n"
    "[00:04-00:08] Спикер 2:\nПока это предложение, срок не обещаем.\n\n"
    "[00:08-00:12] Спикер 1:\nРешили сначала проверить остатки."
)
PLAIN = "Если проверка пройдёт, перенесём встречу. Пока это предложение, срок не обещаем. Решили сначала проверить остатки."
SUFFIX = "\n\n---\n\n## Полная транскрипция\n\n" + PROTOCOL


def audio(file_id="recording", name="meeting.mp3"):
    return {"id": file_id, "name": name, "content_type": "audio/mpeg", "size": 100,
            "file": {"id": file_id, "filename": name,
                     "meta": {"content_type": "audio/mpeg", "size": 100}}}


def user(mid, text, parent=None, files=None):
    return {"id": mid, "role": "user", "content": text, "parentId": parent,
            "files": files or []}


def assistant(mid, text, parent):
    return {"id": mid, "role": "assistant", "content": text, "parentId": parent}


@pytest.fixture
def native(monkeypatch, tmp_path):
    """Model the already-authorized native branch and owner-scoped File API."""
    state = SimpleNamespace(records={}, messages={}, reads=[], writes=[], statuses=[], calls=[])

    def add_file(fid="recording", owner="owner", marker=True, display=PROTOCOL):
        path = tmp_path / f"{fid}.mp3"
        path.write_bytes(b"synthetic transport input")
        data = {"unrelated": {"keep": True}}
        if marker:
            data["stage2_audio_context_filter"] = {
                "state": "transcribed-v1", "transcript": PLAIN,
                "display_transcript": display,
            }
        record = SimpleNamespace(id=fid, user_id=owner, path=str(path), data=data)
        state.records[fid] = record
        return record

    async def read_file(fid, uid):
        state.reads.append((fid, uid))
        record = state.records.get(fid)
        return record if record and record.user_id == uid else None

    async def write_file(fid, data):
        state.writes.append(fid)
        state.records[fid].data = copy.deepcopy(data)

    async def read_messages(chat_id):
        assert chat_id == "native-chat"
        return copy.deepcopy(state.messages)

    def selected_chain(messages, leaf):
        # Stand-in for the native pure parent-chain accessor; Filter is exercised intact.
        chain = []
        while leaf is not None and leaf in messages:
            message = messages[leaf]
            chain.append(message)
            leaf = message.get("parentId")
        return list(reversed(chain))

    modules = {
        "open_webui.models.files": {"Files": SimpleNamespace(
            get_file_by_id_and_user_id=read_file, update_file_data_by_id=write_file)},
        "open_webui.storage.provider": {"Storage": SimpleNamespace(get_file=lambda path: path)},
        "open_webui.models.chats": {"Chats": SimpleNamespace(get_messages_map_by_chat_id=read_messages)},
        "open_webui.utils.chat_id": {"is_saved_chat_id": lambda cid: cid == "native-chat"},
        "open_webui.utils.misc": {"get_message_list": selected_chain},
    }
    for name, attrs in modules.items():
        module = ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)

    async def forbid_provider(**kwargs):
        raise AssertionError("Cached/historical sources must not invoke paid STT")

    async def emit(event):
        state.statuses.append(event)

    filter_ = Filter()
    filter_.valves.internal_api_key = "synthetic-test-token"
    monkeypatch.setattr(filter_, "_call_sidecar", forbid_provider)
    state.filter = filter_
    state.add_file = add_file
    state.emit = emit
    return state


async def invoke(native, body, leaf, metadata=None):
    metadata = metadata if metadata is not None else {}
    metadata.update(chat_id="native-chat", user_message_id=leaf)
    await native.filter.inlet(body, __user__={"id": "owner"}, __metadata__=metadata,
                              __event_emitter__=native.emit)
    return metadata


@pytest.mark.asyncio
@pytest.mark.parametrize("prompt", ["", "Write an email to the customer in English."])
async def test_first_upload_keeps_prompt_but_always_requests_summary_and_exact_protocol(native, prompt):
    native.add_file()
    first = user("u1", prompt, files=[audio()])
    native.messages = {"u1": first}
    body = {"messages": [copy.deepcopy(first)], "model": "any-selected-model"}
    metadata = await invoke(native, body, "u1")
    content = body["messages"][-1]["content"]
    assert content.startswith(prompt)
    assert DEFAULT_INITIAL_RESPONSE_INSTRUCTION in content
    assert "Задания по записи выполняются следующими сообщениями" in content
    assert content.count(PROTOCOL) == 1
    body["messages"].append(assistant("a1", "Краткое содержание.", "u1"))
    await native.filter.outlet(body, __metadata__=metadata)
    result = body["messages"][-1]["content"]
    assert result.startswith("## Краткое содержание\n\nКраткое содержание.")
    assert result.endswith(SUFFIX)
    assert result.count(PROTOCOL) == 1
    assert native.writes == []


@pytest.mark.asyncio
async def test_all_current_recordings_are_transcribed_cached_and_shown_without_losing_documents(native, monkeypatch):
    for fid in ("one", "two"):
        native.add_file(fid, marker=False)
    recordings = [audio("one", "one.mp3"), audio("two", "two.mp3")]
    document = {"id": "pdf", "name": "notes.pdf", "content_type": "application/pdf"}
    first = user("u1", "", files=[*recordings, document])
    native.messages = {"u1": first}
    body = {"messages": [copy.deepcopy(first)], "files": [*recordings, document]}
    metadata = {"files": [*recordings, document]}

    async def transcribe(**kwargs):
        fid = kwargs["envelope"]["file"]["file_id"]
        native.calls.append(fid)
        return {"result": {"text": f"Distinct source {fid}.", "segments": [
            {"speaker": 0, "start": 0, "end": 2, "text": f"Distinct source {fid}."}
        ]}}

    monkeypatch.setattr(native.filter, "_call_sidecar", transcribe)
    await invoke(native, body, "u1", metadata)
    content = body["messages"][-1]["content"]
    for fid in ("one", "two"):
        assert content.count(f"Distinct source {fid}.") == 1
        marker = native.records[fid].data["stage2_audio_context_filter"]
        assert marker["state"] == "transcribed-v1"
        assert "[00:00-00:02] Спикер 1:" in marker["display_transcript"]
        assert native.records[fid].data["unrelated"] == {"keep": True}
    assert sorted(native.calls) == sorted(native.writes) == ["one", "two"]
    assert body["files"] == metadata["files"] == [document]
    assert body["messages"][0]["files"] == [*recordings, document]
    body["messages"].append(assistant("a1", "Summary.", "u1"))
    await native.filter.outlet(body, __metadata__=metadata)
    assert body["messages"][-1]["content"].count("Distinct source one.") == 1
    assert body["messages"][-1]["content"].count("Distinct source two.") == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["renamed-workspace-model", "different-provider-model"])
async def test_follow_up_and_regeneration_rehydrate_one_source_without_rebuilding_compaction(native, model):
    native.add_file()
    u1 = user("u1", "", files=[audio()])
    a1 = assistant("a1", "Summary." + SUFFIX, "u1")
    u2 = user("u2", "Now write a concise email.", "a1")
    native.messages = {m["id"]: m for m in (u1, a1, u2)}
    system = {"role": "system", "content": "Native compacted history; retain this exact message."}
    body = {"model": model, "messages": [copy.deepcopy(system), copy.deepcopy(a1), copy.deepcopy(u2)]}
    metadata = await invoke(native, body, "u2")
    assert len(body["messages"]) == 3
    assert body["messages"][0] == system
    assert body["messages"][1]["content"] == "Summary."
    assert body["messages"][-1]["content"].startswith(u2["content"])
    assert body["messages"][-1]["content"].count(PROTOCOL) == 1
    assert DEFAULT_INITIAL_RESPONSE_INSTRUCTION not in body["messages"][-1]["content"]
    assert sum(str(m.get("content", "")).count(PROTOCOL) for m in body["messages"]) == 1
    await invoke(native, body, "u2", metadata)
    assert body["messages"][-1]["content"].count(PROTOCOL) == 1
    body["messages"].append(assistant("a2", "Requested email only.", "u2"))
    await native.filter.outlet(body, __metadata__=metadata)
    assert body["messages"][-1]["content"] == "Requested email only."
    assert native.messages["a1"]["content"].endswith(SUFFIX)
    assert native.writes == []


@pytest.mark.asyncio
async def test_only_selected_native_branch_admits_sources_not_aggregate_or_sibling_files(native):
    native.add_file()
    native.add_file("sibling", display="SIBLING PRIVATE SOURCE")
    u1 = user("u1", "", files=[audio()])
    a1 = assistant("a1", "Summary." + SUFFIX, "u1")
    chosen = user("chosen", "Use this recording.", "a1")
    sibling = user("sibling-turn", "Other branch", "a1", [audio("sibling", "other.mp3")])
    native.messages = {m["id"]: m for m in (u1, a1, chosen, sibling)}
    body = {"messages": [copy.deepcopy(chosen)], "files": [audio("sibling", "other.mp3")]}
    await invoke(native, body, "chosen")
    assert PROTOCOL in body["messages"][-1]["content"]
    assert "SIBLING PRIVATE SOURCE" not in body["messages"][-1]["content"]
    assert {fid for fid, _ in native.reads} == {"recording"}
    assert body["files"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["foreign-owner", "missing-historical", "empty-current-marker"])
async def test_inaccessible_or_legacy_missing_cache_never_leaks_or_silently_succeeds(native, missing):
    record = native.add_file(owner="foreign" if missing == "foreign-owner" else "owner")
    if missing == "empty-current-marker":
        record.data["stage2_audio_context_filter"] = {"state": "transcribed-v1"}
    elif missing == "missing-historical":
        record.data.pop("stage2_audio_context_filter")
    u1 = user("u1", "", files=[audio()])
    u2 = user("u2", "Summarize the source.", "u1")
    native.messages = {"u1": u1, "u2": u2}
    current = u1 if missing == "empty-current-marker" else u2
    body = {"messages": [copy.deepcopy(current)]}
    metadata = await invoke(native, body, current["id"])
    content = body["messages"][-1]["content"]
    assert "Сохранённая транскрипция недоступна" in content
    assert "их содержание неизвестно" in content
    assert PROTOCOL not in content and PLAIN not in content
    assert metadata["_stage2_audio_transcript"] is None
    assert native.statuses[-1]["data"]["done"] is True
    assert native.writes == []
    assert all(uid == "owner" for _, uid in native.reads)


@pytest.mark.asyncio
async def test_similar_heading_or_altered_protocol_is_preserved_with_source_and_tool_artifacts(native):
    native.add_file()
    u1 = user("u1", "", files=[audio()])
    fake = "Authored example\n\n---\n\n## Полная транскрипция\n\nAn unrelated protocol."
    a1 = assistant("a1", fake, "u1")
    reasoning = {"type": "reasoning", "id": "r", "summary": [{"type": "summary_text", "text": "Trace"}]}
    tool = {"type": "function_call", "id": "t", "name": "example", "arguments": "{}"}
    a1.update(output=[reasoning, tool, {"type": "message", "role": "assistant", "content": [
        {"type": "output_text", "text": fake, "annotations": [{"type": "url_citation", "url": "https://example.test"}]}
    ]}], sources=[{"source": {"id": "doc"}, "document": ["Keep document source"]}])
    u2 = user("u2", "Revise the response", "a1")
    native.messages = {m["id"]: m for m in (u1, a1, u2)}
    body = {"messages": [copy.deepcopy(a1), copy.deepcopy(u2)]}
    before = copy.deepcopy(body["messages"][0])
    await invoke(native, body, "u2")
    assert body["messages"][0] == before
    assert body["messages"][-1]["content"].count(PROTOCOL) == 1


@pytest.mark.asyncio
async def test_exact_managed_suffix_is_removed_without_changing_tool_reasoning_or_source_annotations(native):
    native.add_file()
    u1 = user("u1", "", files=[audio()])
    a1 = assistant("a1", "Summary." + SUFFIX, "u1")
    a1.update(output=[
        {"type": "reasoning", "id": "r", "summary": [{"type": "summary_text", "text": "Trace"}]},
        {"type": "function_call", "id": "t", "name": "example", "arguments": "{}"},
        {"type": "message", "role": "assistant", "id": "text", "content": [
            {"type": "output_text", "text": "Summary.", "annotations": [{"type": "url_citation", "url": "https://example.test"}]},
            {"type": "output_text", "text": SUFFIX},
        ]},
    ], sources=[{"source": {"id": "doc"}}])
    u2 = user("u2", "Revise", "a1")
    native.messages = {m["id"]: m for m in (u1, a1, u2)}
    body = {"messages": [copy.deepcopy(a1), copy.deepcopy(u2)]}
    before = copy.deepcopy(body["messages"][0])
    await invoke(native, body, "u2")
    actual = body["messages"][0]
    assert actual["content"] == "Summary."
    assert actual["output"][:2] == before["output"][:2]
    assert actual["sources"] == before["sources"]
    assert actual["output"][2]["content"][0] == before["output"][2]["content"][0]
    assert "".join(p["text"] for p in actual["output"][2]["content"]) == "Summary."


@pytest.mark.asyncio
async def test_identical_source_looking_suffix_on_unlinked_assistant_is_not_managed(native):
    native.add_file()
    unrelated = assistant("unlinked", "Authored quotation." + SUFFIX, None)
    u1 = user("u1", "", "unlinked", [audio()])
    linked = assistant("linked", unrelated["content"], "u1")
    u2 = user("u2", "Revise only the later result", "linked")
    native.messages = {m["id"]: m for m in (unrelated, u1, linked, u2)}
    body = {"messages": [copy.deepcopy(unrelated), copy.deepcopy(linked), copy.deepcopy(u2)]}
    await invoke(native, body, "u2")
    assert body["messages"][0] == unrelated
    assert body["messages"][1]["content"] == "Authored quotation."
    assert body["messages"][-1]["content"].count(PROTOCOL) == 1


@pytest.mark.asyncio
async def test_managed_suffix_split_across_native_text_parts_is_removed_from_output_too(native):
    native.add_file()
    u1 = user("u1", "", files=[audio()])
    a1 = assistant("a1", "Summary." + SUFFIX, "u1")
    annotation = {"type": "url_citation", "url": "https://example.test"}
    a1["output"] = [{"type": "message", "role": "assistant", "id": "text", "content": [
        {"type": "output_text", "text": "Summary.", "annotations": [annotation]},
        {"type": "output_text", "text": SUFFIX[:-len(PROTOCOL)]},
        {"type": "output_text", "text": PROTOCOL},
    ]}]
    u2 = user("u2", "Revise", "a1")
    native.messages = {m["id"]: m for m in (u1, a1, u2)}
    body = {"messages": [copy.deepcopy(a1), copy.deepcopy(u2)]}
    await invoke(native, body, "u2")
    assert body["messages"][0]["content"] == "Summary."
    parts = body["messages"][0]["output"][0]["content"]
    assert "".join(part["text"] for part in parts) == "Summary."
    assert parts[0]["annotations"] == [annotation]
    assert body["messages"][-1]["content"].count(PROTOCOL) == 1


@pytest.mark.asyncio
async def test_partial_upload_failure_stays_visible_without_duplicating_successful_protocol(native, monkeypatch):
    native.add_file()
    native.add_file("oversized", marker=False)
    first = user("u1", "Write an email", files=[audio(), audio("oversized", "large.mp3")])
    native.messages = {"u1": first}

    async def rejected(**kwargs):
        assert kwargs["filename"] == "large.mp3"
        request = httpx.Request("POST", "http://fixture.invalid/transcription")
        response = httpx.Response(422, request=request, json={"detail": {"code": "prepared_audio_too_large"}})
        raise httpx.HTTPStatusError("rejected", request=request, response=response)

    monkeypatch.setattr(native.filter, "_call_sidecar", rejected)
    body = {"messages": [copy.deepcopy(first)]}
    metadata = await invoke(native, body, "u1")
    rendered = assistant("a1", "Summary of the available recording.", "u1")
    body["messages"].append(rendered)
    await native.filter.outlet(body, __metadata__=metadata)
    assert "large.mp3" in rendered["content"]
    assert "превышает допустимый размер" in rendered["content"]
    assert rendered["content"].endswith(PROTOCOL)

    followup = user("u2", "Explain the available recording", "a1")
    native.messages.update(a1=copy.deepcopy(rendered), u2=followup)
    continued = {"messages": [copy.deepcopy(rendered), copy.deepcopy(followup)]}
    await invoke(native, continued, "u2")
    assert PROTOCOL not in continued["messages"][0]["content"]
    assert "превышает допустимый размер" in continued["messages"][0]["content"]
    assert continued["messages"][-1]["content"].count(PROTOCOL) == 1
    assert "large.mp3" in continued["messages"][-1]["content"]
