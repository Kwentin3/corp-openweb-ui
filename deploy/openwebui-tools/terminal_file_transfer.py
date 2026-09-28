"""
title: Native Terminal File Transfer
author: Alpha Soft
version: 0.1.0-candidate
required_open_webui_version: 0.9.6
description: Copy authorized Files into the selected Terminal and publish results as native chat attachments.
"""

from contextlib import asynccontextmanager
import asyncio
import hashlib
import json
import mimetypes
from pathlib import PurePosixPath
import re
from tempfile import TemporaryFile
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import aiohttp
from pydantic import BaseModel, Field


TRANSIENT_READ_STATUS = {429, 502, 503, 504}
TRANSIENT_READ_ERRORS = (aiohttp.ClientConnectionError, aiohttp.ClientPayloadError, asyncio.TimeoutError)


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("A confirmed native identifier is required")
    return value


def _filename(value: str) -> str:
    name = value.replace("\\", "/").rsplit("/", 1)[-1]
    if name in ("", ".", "..") or any(ord(c) < 32 for c in name):
        raise ValueError("Invalid file name")
    return name


class Tools:
    class Valves(BaseModel):
        openwebui_base_url: str = Field(
            default="http://127.0.0.1:8080",
            description="This OpenWebUI instance's internal API origin; never a Terminal origin.",
        )
        max_file_mib: int = Field(default=32, ge=1, le=128,
            description="Per-transfer bound, also subject to native upload limits.")

    def __init__(self):
        self.valves = self.Valves()

    async def _context(self, request, metadata):
        if not isinstance(metadata, dict) or metadata.get("task") is not None:
            raise ValueError("File transfer requires a primary saved chat turn")
        chat_id = _identifier(metadata.get("chat_id"))
        _identifier(metadata.get("message_id"))
        terminal_id = metadata.get("terminal_id")
        if terminal_id is None:
            # 0.9.6 captures Tool extra_params before adding terminal_id to a
            # replacement metadata dict. Read the same native selection from
            # the original HTTP body; never infer it from UI or a default server.
            body = json.loads(await request.body())
            if body.get("chat_id") != chat_id:
                raise ValueError("Native request and Tool chat identities differ")
            terminal_id = body.get("terminal_id")
        if not terminal_id:
            raise ValueError("No Terminal was selected in this native chat request")
        terminal_id = _identifier(terminal_id)
        token = getattr(getattr(getattr(request, "state", None), "token", None), "credentials", None)
        if not isinstance(token, str) or not token:
            raise ValueError("Authenticated native request is required")
        headers = {"Authorization": f"Bearer {token}", "X-Session-Id": chat_id}
        return terminal_id, headers

    def _session(self, headers):
        # The native APIs own access checks, server selection, credentials and storage.
        # Do not forward the user's bearer token to the Terminal service itself.
        return aiohttp.ClientSession(
            base_url=self.valves.openwebui_base_url.rstrip("/"), headers=headers,
            timeout=aiohttp.ClientTimeout(total=180, connect=10), trust_env=False,
        )

    async def _json(self, session, method, path, **kwargs):
        for attempt in range(2):
            try:
                async with session.request(method, path, allow_redirects=False, **kwargs) as response:
                    if method == "GET" and response.status in TRANSIENT_READ_STATUS and attempt == 0:
                        await asyncio.sleep(0.25)
                        continue
                    if not 200 <= response.status < 300:
                        raise ValueError(f"Native API {method} failed with HTTP {response.status}; no further automatic retry")
                    return await response.json()
            except TRANSIENT_READ_ERRORS:
                if method != "GET" or attempt:
                    raise
                await asyncio.sleep(0.25)

    async def _terminal(self, session, terminal_id):
        allowed = await self._json(session, "GET", "/api/v1/terminals/")
        if not any(item.get("id") == terminal_id for item in allowed):
            raise ValueError("The selected Terminal is disabled, missing or not accessible")
        return f"/api/v1/terminals/{quote(terminal_id, safe='')}/"

    @asynccontextmanager
    async def _download(self, session, path, **kwargs):
        for attempt in range(2):
            with TemporaryFile() as data:
                size = 0
                digest = hashlib.sha256()
                try:
                    async with session.get(path, allow_redirects=False, **kwargs) as response:
                        if response.status in TRANSIENT_READ_STATUS and attempt == 0:
                            await asyncio.sleep(0.25)
                            continue
                        if response.status != 200:
                            raise ValueError(f"Native download failed with HTTP {response.status}")
                        async for chunk in response.content.iter_chunked(128 * 1024):
                            size += len(chunk)
                            if size > self.valves.max_file_mib * 1024 * 1024:
                                raise ValueError("File exceeds the configured transfer bound; nothing was uploaded")
                            data.write(chunk)
                            digest.update(chunk)
                except TRANSIENT_READ_ERRORS:
                    if attempt:
                        raise
                    await asyncio.sleep(0.25)
                    continue
                # Keep the caller's subsequent upload outside the read-retry
                # handler: a failed write must never restart this generator.
                data.seek(0)
                yield data, size, digest.hexdigest()
                return

    async def stage_chat_file(
        self, file_id: str, __request__: Any = None, __metadata__: dict | None = None,
    ) -> dict:
        """Copy an authorized native file into the CURRENTLY SELECTED Terminal.

        Use an explicit file_id from native chat files. Returns the actual path for
        run_command/read_file. Creates a unique input directory; never overwrites
        or deletes the original or an existing Terminal file. No Office conversion.
        Transient reads get one retry; writes are never retried automatically.
        """
        file_id = _identifier(file_id)
        terminal_id, headers = await self._context(__request__, __metadata__)
        async with self._session(headers) as session:
            terminal = await self._terminal(session, terminal_id)
            source = await self._json(session, "GET", f"/api/v1/files/{file_id}")
            if source.get("id") != file_id:
                raise ValueError("Native file identity mismatch")
            name = _filename(source["filename"])
            async with self._download(session, f"/api/v1/files/{file_id}/content") as (data, size, digest):
                cwd = (await self._json(session, "GET", terminal + "files/cwd"))["cwd"]
                if not isinstance(cwd, str) or not cwd.startswith("/"):
                    raise ValueError("Terminal did not return an absolute working directory")
                directory = str(PurePosixPath(cwd) / ".chat-inputs" / uuid4().hex)
                await self._json(session, "POST", terminal + "files/mkdir", json={"path": directory})
                form = aiohttp.FormData(quote_fields=False)
                form.add_field("file", data, filename=name,
                    content_type=source.get("meta", {}).get("content_type") or "application/octet-stream")
                uploaded = await self._json(session, "POST", terminal + "files/upload",
                    params={"directory": directory}, data=form)
            path = uploaded.get("path")
            if path != str(PurePosixPath(directory) / name):
                raise ValueError("Unexpected Terminal upload path; inspect the file manager before retrying")
            async with self._download(session, terminal + "files/view", params={"path": path}) as (_, actual_size, actual_hash):
                if (actual_size, actual_hash) != (size, digest):
                    raise ValueError("Transferred file differs from the native source; do not use it")
            return {"source_file_id": file_id, "terminal_id": terminal_id,
                    "path": path, "size": size, "sha256": digest, "source_modified": False}

    async def publish_terminal_file(
        self, path: str, __request__: Any = None, __metadata__: dict | None = None,
        __event_emitter__: Any = None,
    ) -> dict:
        """Publish a completed file from the SELECTED Terminal as a NEW native chat attachment.

        First finish execution and verify the document. Pass its confirmed absolute
        path. Source files are never deleted or changed. Use returned download_url
        verbatim, without sandbox:. If attachment delivery fails, retain the returned
        result_file_id/download_url; do not repeat publication blindly.
        Transient reads get one retry; writes are never retried automatically.
        """
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError("A confirmed absolute Terminal file path is required")
        if __event_emitter__ is None:
            raise ValueError("Native chat attachment delivery is unavailable")
        terminal_id, headers = await self._context(__request__, __metadata__)
        name = _filename(path)
        content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        async with self._session(headers) as session:
            terminal = await self._terminal(session, terminal_id)
            async with self._download(session, terminal + "files/view", params={"path": path}) as (data, size, digest):
                form = aiohttp.FormData(quote_fields=False)
                form.add_field("file", data, filename=name, content_type=content_type)
                native_file = await self._json(session, "POST", "/api/v1/files/?process=false", data=form)
            result_id = _identifier(native_file.get("id"))
            url = f"/api/v1/files/{result_id}/content"
            receipt = {"result_file_id": result_id, "result_file": native_file,
                       "download_url": url, "size": size, "sha256": digest,
                       "status": "uploaded_unverified"}
            try:
                async with self._download(session, url) as (_, actual_size, actual_hash):
                    if (actual_size, actual_hash) != (size, digest):
                        raise ValueError("Published bytes differ from the Terminal snapshot")
                receipt["status"] = "verified_attachment_pending"
                chat_file = {"type": "file", "file": native_file, "id": result_id,
                             "url": result_id, "name": native_file["filename"],
                             "status": "uploaded", "size": size, "content_type": content_type}
                for event in ("files", "chat:message:files"):
                    await __event_emitter__({"type": event, "data": {"files": [chat_file]}})
                receipt["status"] = "published"
            except Exception:
                # A new File already exists. Return its real identity even when a
                # later verification/event fails; never hide it or retry the write.
                receipt["error"] = "Publication is incomplete; inspect the existing result_file_id before any retry"
            return receipt
