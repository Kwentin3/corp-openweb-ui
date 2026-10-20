"""Offline audio context integration in the exact installed OpenWebUI image.

Run without production environment, mounts or network:

docker run --rm --network none --read-only --memory 1g --pids-limit 128 \
  --tmpfs /tmp:rw,nosuid,size=128m -e PYTHONPATH=/app/backend --entrypoint python \
  -v /absolute/verify_native_audio_context_runtime.py:/verify.py:ro \
  -v /absolute/stage2_audio_context_filter.py:/candidate.py:ro \
  <verified-installed-webui-image-id> /verify.py --filter /candidate.py

Real native SQLite, File/Chat/ChatMessage, Storage, branch selection and output
conversion are used. Pure load/flatten functions are AST-extracted unchanged
from the installed middleware to avoid its application startup imports. The
Cached routes forbid _call_sidecar. A fresh upload additionally exercises its
real multipart HTTP client against an in-process httpx.MockTransport; native
File cache persistence is unchanged. Synthetic text and a constructed post-compaction body do not qualify
speech recognition, a running compactor, browser rendering or provider limits.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import copy
from email import policy
from email.parser import BytesParser
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import uuid
from unittest.mock import patch


def installed_functions(path: Path, namespace: dict) -> dict[str, str]:
    source = path.read_text()
    tree = ast.parse(source)
    names = {"load_messages_from_db", "process_messages_with_output", "add_file_context"}
    nodes = [node for node in tree.body if getattr(node, "name", None) in names]
    assert len(nodes) == len(names) and {node.name for node in nodes} == names
    assignment = [node for node in tree.body if isinstance(node, ast.Assign)
                  and any(isinstance(target, ast.Name) and target.id == "MESSAGE_REPLAY_KEYS"
                          for target in node.targets)]
    assert len(assignment) == 1
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.Module(body=[future, *assignment, *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(path), "exec"), namespace)
    return {node.name: hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest()
            for node in nodes}


async def verify(candidate: Path, root: Path) -> dict:
    assert not any(name.startswith("open_webui") for name in sys.modules)
    os.environ.update({
        "DATA_DIR": str(root / "data"), "DATABASE_URL": f"sqlite:///{root / 'context.sqlite3'}",
        "UPLOAD_DIR": str(root / "uploads"), "STATIC_DIR": str(root / "static"),
        "CACHE_DIR": str(root / "cache"), "ENABLE_DB_MIGRATIONS": "false",
        "ENABLE_PERSISTENT_CONFIG": "false", "OFFLINE_MODE": "true",
        "WEBUI_SECRET_KEY": "offline-context-fixture-only-" * 4,
        "STORAGE_PROVIDER": "local", "DATABASE_POOL_SIZE": "2",
        "STAGE2_STT_INTERNAL_API_KEY": "offline-never-call-provider",
    })
    for name in ("data", "uploads", "static", "cache"):
        (root / name).mkdir()

    from open_webui.internal.db import async_engine, engine, get_async_db_context
    from open_webui.models.files import File, FileForm, Files
    from open_webui.models.chats import Chat, Chats
    from open_webui.models.chat_messages import ChatMessage, ChatMessages
    from open_webui.storage.provider import LocalStorageProvider, Storage
    from open_webui.utils import misc

    assert isinstance(Storage, LocalStorageProvider)
    for model in (File, Chat, ChatMessage):
        model.__table__.create(bind=engine)
    native = {"Chats": Chats, "get_message_list": misc.get_message_list,
              "get_content_from_message": misc.get_content_from_message,
              "set_last_user_message_content": misc.set_last_user_message_content,
              "convert_output_to_messages": misc.convert_output_to_messages}
    native_hashes = installed_functions(Path("/app/backend/open_webui/utils/middleware.py"), native)
    spec = importlib.util.spec_from_file_location("candidate_audio_context", candidate)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    filter_ = module.Filter()
    sidecar_calls = 0

    async def forbidden_sidecar(**kwargs):
        nonlocal sidecar_calls
        sidecar_calls += 1
        raise AssertionError("Cached/foreign/auxiliary routes must not call STT")

    filter_._call_sidecar = forbidden_sidecar
    owner = str(uuid.uuid4())
    user = {"id": owner, "role": "user"}
    display = "[00:00-00:05] Speaker 1:\nCANONICAL_PROTOCOL_A\n\n[00:05-00:09] Speaker 2:\nSOURCE_END_A"
    sibling_display = "[00:00-00:04] Speaker 3:\nSIBLING_PROTOCOL_B"
    foreign_display = "[00:00-00:04] Speaker 9:\nFOREIGN_PROTOCOL_C"

    async def cached_file(file_owner, name, protocol, *, cached=True):
        file_id = str(uuid.uuid4())
        payload = ("synthetic-audio-" + file_id).encode()
        size, digest, path = Storage.upload_file_streaming(io.BytesIO(payload), f"{file_id}_{name}", {})
        row = await Files.insert_new_file(file_owner, FileForm(
            id=file_id, filename=name, path=path, hash=digest,
            meta={"name": name, "content_type": "audio/mpeg", "size": size},
            data={"status": "completed", **({"stage2_audio_context_filter": {
                "state": "transcribed-v1", "transcript": "RAW_TEXT_IS_NOT_THE_DIARIZED_SOURCE",
                "display_transcript": protocol,
            }} if cached else {})},
        ))
        assert row is not None
        return row

    def attachment(row):
        return {"type": "file", "id": row.id, "name": row.filename,
                "content_type": "audio/mpeg", "file": row.model_dump()}

    async def new_chat():
        chat_id = str(uuid.uuid4())
        async with get_async_db_context() as db:
            db.add(Chat(id=chat_id, user_id=owner, title="Offline context fixture",
                        chat={"title": "Offline context fixture", "history": {"messages": {}}},
                        created_at=int(time.time()), updated_at=int(time.time())))
            await db.commit()
        return chat_id

    async def persist(chat_id, message):
        result = await Chats.upsert_message_to_chat_by_id_and_message_id(chat_id, message["id"], message)
        assert result is not None
        assert await ChatMessages.get_message_by_id(f"{chat_id}-{message['id']}") is not None

    def message(role, text, parent=None, **extra):
        return {"id": str(uuid.uuid4()), "role": role, "content": text,
                "parentId": parent, "childrenIds": [], "done": True, **extra}

    async def outgoing(chat_id, current_id, model="model-a", files=None):
        raw = await native["load_messages_from_db"](chat_id, current_id)
        assert raw
        messages = native["process_messages_with_output"](copy.deepcopy(raw), include_file_context=False)
        return {"model": model, "messages": messages, "files": copy.deepcopy(files or [])}

    def metadata(chat_id, current_id, files=None):
        return {"chat_id": chat_id, "user_message_id": current_id, "files": copy.deepcopy(files or [])}

    async def fingerprints(rows):
        result = {}
        for row in rows:
            current = await Files.get_file_by_id(row.id)
            result[row.id] = {"row": current.model_dump(),
                              "blob_sha256": hashlib.sha256(Path(current.path).read_bytes()).hexdigest()}
        return result

    passed = []
    try:
        primary = await cached_file(owner, "primary.mp3", display)
        sibling = await cached_file(owner, "sibling.mp3", sibling_display)
        foreign = await cached_file(str(uuid.uuid4()), "foreign.mp3", foreign_display)
        rows = [primary, sibling, foreign]
        before_files = await fingerprints(rows)
        chat_id = await new_chat()
        first = message("user", "An initial task that must wait until the next turn.", files=[attachment(primary)])
        await persist(chat_id, first)
        initial = await outgoing(chat_id, first["id"], files=[attachment(primary)])
        initial_meta = metadata(chat_id, first["id"], [attachment(primary)])
        await filter_.inlet(initial, __user__=user, __metadata__=initial_meta)
        assert initial["messages"][-1]["content"].count(display) == 1
        assert module.DEFAULT_INITIAL_RESPONSE_INSTRUCTION in initial["messages"][-1]["content"]
        assert "RAW_TEXT_IS_NOT_THE_DIARIZED_SOURCE" not in initial["messages"][-1]["content"]
        answer = message("assistant", "Short synthetic summary.", first["id"], model="model-a", output=[{
            "type": "message", "id": "native-output", "role": "assistant", "status": "completed",
            "content": [{"type": "output_text", "text": "Short synthetic summary.", "annotations": []}],
        }])
        initial["messages"].append(answer)
        await filter_.outlet(initial, __metadata__=initial_meta)
        await persist(chat_id, answer)
        saved_answer = (await Chats.get_messages_map_by_chat_id(chat_id))[answer["id"]]
        assert saved_answer["content"].count(display) == 1
        converted = misc.convert_output_to_messages(saved_answer["output"], raw=True)
        assert converted[0]["content"] == saved_answer["content"]
        passed.append("cached first turn produces summary plus exact diarized protocol in both native persisted representations")

        followup = message("user", "List the agreed actions.", answer["id"])
        other_branch = message("user", "Sibling branch must stay excluded.", answer["id"], files=[attachment(sibling)])
        await persist(chat_id, other_branch)
        await persist(chat_id, followup)
        saved_before = copy.deepcopy(await Chats.get_messages_map_by_chat_id(chat_id))
        aggregate = [attachment(primary), attachment(sibling)]
        for selected_model in ("model-a", "renamed-model-b"):
            body = await outgoing(chat_id, followup["id"], model=selected_model, files=aggregate)
            meta = metadata(chat_id, followup["id"], aggregate)
            await filter_.inlet(body, __user__=user, __metadata__=meta)
            user_text = body["messages"][-1]["content"]
            assert user_text.startswith(followup["content"]) and user_text.count(display) == 1
            assert module.DEFAULT_INITIAL_RESPONSE_INSTRUCTION not in user_text
            assert all(display not in m.get("content", "") for m in body["messages"] if m["role"] == "assistant")
            assert any("Short synthetic summary." in m.get("content", "") for m in body["messages"])
            assert sibling_display not in json.dumps(body, ensure_ascii=False)
            assert body["files"] == meta["files"] == []
            assert "_stage2_audio_display" not in meta
        assert await Chats.get_messages_map_by_chat_id(chat_id) == saved_before
        passed.append("native reload/flatten and model rename keep one source, clean assistant history, exclude sibling aggregate and preserve stored display")

        compacted = {"model": "renamed-model-b", "messages": [
            {"role": "system", "content": "NATIVE_COMPACTED_SUMMARY"},
            {"role": "user", "content": followup["content"]},
        ]}
        await filter_.inlet(compacted, __user__=user, __metadata__=metadata(chat_id, followup["id"]))
        assert len(compacted["messages"]) == 2
        assert compacted["messages"][0] == {"role": "system", "content": "NATIVE_COMPACTED_SUMMARY"}
        assert compacted["messages"][1]["content"].count(display) == 1
        assert "Short synthetic summary." not in json.dumps(compacted)
        passed.append("already compacted outgoing history stays compacted while its selected native File source is restored once")

        denied_chat = await new_chat()
        foreign_user = message("user", "Untrusted foreign File reference.", files=[attachment(foreign)])
        await persist(denied_chat, foreign_user)
        for current in (foreign_user, message("user", "Follow-up to unavailable source.", foreign_user["id"])):
            if current["id"] != foreign_user["id"]:
                await persist(denied_chat, current)
            denied = await outgoing(denied_chat, current["id"], files=[attachment(foreign)])
            await filter_.inlet(denied, __user__=user, __metadata__=metadata(denied_chat, current["id"]))
            assert foreign_display not in json.dumps(denied, ensure_ascii=False)
        passed.append("native File ownership prevents foreign cached protocol disclosure on current and historical references without STT")

        for task in ("title_generation", "tags_generation", "follow_up_generation", "context_compaction"):
            auxiliary = await outgoing(chat_id, followup["id"], files=aggregate)
            aux_meta = {**metadata(chat_id, followup["id"], aggregate), "task": task}
            before_body, before_meta = copy.deepcopy(auxiliary), copy.deepcopy(aux_meta)
            assert await filter_.inlet(auxiliary, __user__=user, __metadata__=aux_meta) is auxiliary
            assert await filter_.outlet(auxiliary, __metadata__=aux_meta) is auxiliary
            assert auxiliary == before_body and aux_meta == before_meta
        assert await fingerprints(rows) == before_files
        assert sidecar_calls == 0
        passed.append("auxiliary tasks leave inputs untouched; all native File/cache rows and blobs remain unchanged; zero STT calls")

        # Exercise the real adapter and real _mark_transcribed, replacing only HTTP.
        import httpx

        fresh = await cached_file(owner, "fresh.mp3", "", cached=False)
        fresh_before = await fingerprints([fresh])
        fresh_payload = Path(fresh.path).read_bytes()
        segments = [
            {"speaker": "speaker-a", "start_seconds": 0, "end_seconds": 2, "text": "FRESH_KNOWN_A"},
            {"speaker": None, "start_seconds": 2, "end_seconds": 4, "text": "FRESH_UNKNOWN"},
            {"speaker": "speaker-b", "start": 4, "end": 6, "text": "FRESH_KNOWN_B"},
            {"speaker": "speaker-a", "start_seconds": 6, "end_seconds": 8, "text": "FRESH_RETURN_A"},
            {"speaker": "", "start_seconds": 8, "end_seconds": 10, "text": "FRESH_EMPTY_SPEAKER"},
        ]
        fresh_text = " ".join(segment["text"] for segment in segments)
        fresh_display = (
            "[00:00-00:02] Спикер 1:\nFRESH_KNOWN_A\n\n"
            "[00:02-00:04] Спикер не определён:\nFRESH_UNKNOWN\n\n"
            "[00:04-00:06] Спикер 2:\nFRESH_KNOWN_B\n\n"
            "[00:06-00:08] Спикер 1:\nFRESH_RETURN_A\n\n"
            "[00:08-00:10] Спикер не определён:\nFRESH_EMPTY_SPEAKER"
        )
        fresh_http_calls = 0

        async def fresh_transport(request):
            nonlocal fresh_http_calls
            fresh_http_calls += 1
            assert fresh_http_calls == 1, "A follow-up repeated HTTP transcription"
            assert request.method == "POST"
            assert str(request.url) == "http://offline-transcription.invalid/stage2-api/transcription/jobs"
            assert request.headers["authorization"] == "Bearer offline-never-call-provider"
            raw = await request.aread()
            multipart = BytesParser(policy=policy.default).parsebytes(
                b"Content-Type: " + request.headers["content-type"].encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + raw
            )
            parts = {part.get_param("name", header="content-disposition"): part for part in multipart.iter_parts()}
            assert set(parts) == {"envelope", "prepared_audio"}
            envelope = json.loads(parts["envelope"].get_payload(decode=True))
            assert envelope["user_id"] == owner and envelope["file"]["file_id"] == fresh.id
            assert envelope["file"]["size_bytes"] == len(fresh_payload)
            assert parts["prepared_audio"].get_filename() == "fresh.mp3"
            assert parts["prepared_audio"].get_content_type() == "audio/mpeg"
            assert parts["prepared_audio"].get_payload(decode=True) == fresh_payload
            return httpx.Response(200, json={"result": {"text": fresh_text, "segments": segments}})

        native_client = httpx.AsyncClient

        def offline_client(*args, **kwargs):
            return native_client(*args, **kwargs, transport=httpx.MockTransport(fresh_transport))

        fresh_filter = module.Filter()
        fresh_filter.valves.sidecar_base_url = "http://offline-transcription.invalid"
        fresh_chat = await new_chat()
        fresh_user = message("user", "Initial upload.", files=[attachment(fresh)])
        await persist(fresh_chat, fresh_user)
        with patch.object(module.httpx, "AsyncClient", offline_client):
            fresh_body = await outgoing(fresh_chat, fresh_user["id"], files=[attachment(fresh)])
            fresh_meta = metadata(fresh_chat, fresh_user["id"], [attachment(fresh)])
            await fresh_filter.inlet(fresh_body, __user__=user, __metadata__=fresh_meta)
            saved_file = await Files.get_file_by_id(fresh.id)
            marker = saved_file.data["stage2_audio_context_filter"]
            assert marker["state"] == "transcribed-v1"
            assert marker["transcript"] == fresh_text and marker["display_transcript"] == fresh_display
            assert fresh_body["messages"][-1]["content"].count(fresh_display) == 1
            fresh_answer = message("assistant", "Fresh synthetic summary.", fresh_user["id"], model="model-a", output=[{
                "type": "message", "id": "fresh-native-output", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": "Fresh synthetic summary."}],
            }])
            fresh_body["messages"].append(fresh_answer)
            await fresh_filter.outlet(fresh_body, __metadata__=fresh_meta)
            await persist(fresh_chat, fresh_answer)
            persisted = (await Chats.get_messages_map_by_chat_id(fresh_chat))[fresh_answer["id"]]
            assert persisted["content"].count(fresh_display) == 1
            assert misc.convert_output_to_messages(persisted["output"], raw=True)[0]["content"] == persisted["content"]
            after_transcription = await fingerprints([fresh])
            assert after_transcription[fresh.id]["blob_sha256"] == fresh_before[fresh.id]["blob_sha256"]
            assert saved_file.path == fresh.path and saved_file.hash == fresh.hash and saved_file.meta == fresh.meta
            fresh_followup = message("user", "Now list the actions.", fresh_answer["id"])
            await persist(fresh_chat, fresh_followup)
            follow_body = await outgoing(fresh_chat, fresh_followup["id"], model="renamed-model-b")
            await fresh_filter.inlet(follow_body, __user__=user, __metadata__=metadata(fresh_chat, fresh_followup["id"]))
            assert follow_body["messages"][-1]["content"].count(fresh_display) == 1
            assert all(fresh_display not in m.get("content", "") for m in follow_body["messages"] if m["role"] == "assistant")
            assert await fingerprints([fresh]) == after_transcription
            assert fresh_http_calls == 1
        passed.append("fresh File uses real multipart adapter once, persists all mixed/unknown speaker segments and timestamps in native cache/output, and reuses that cache after reload/model switch")
        return {"passed": passed, "filter_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                "installed_native_function_sha256": native_hashes, "cached_forbidden_sidecar_calls": sidecar_calls,
                "fresh_transcription_http_fixture_calls": fresh_http_calls,
                "scope": "real native SQLite/File/Chat/ChatMessage/Storage, real multipart STT client and cache persistence with HTTP-only MockTransport; exact AST-extracted installed load/flatten and actual misc conversion; synthetic text/post-compaction fixture; no providers/browser/compactor acceptance"}
    finally:
        await async_engine.dispose()
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filter", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="native-audio-context-offline-") as directory:
        receipt = asyncio.run(verify(args.filter.resolve(strict=True), Path(directory)))
    print(json.dumps(receipt, ensure_ascii=False))
