"""
title: Audio context for ordinary chats
author: Alpha Soft
version: 0.2.2
required_open_webui_version: 0.9.6
requirements: httpx,pydantic

Transcribes an audio attachment before the selected ordinary model is called.
The Filter deliberately does not declare ``file_handler``: in OpenWebUI 0.9.6
that flag disables native file processing for every attachment, not audio only.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field


DEFAULT_INITIAL_RESPONSE_INSTRUCTION = (
    "Сформируй только краткое содержание транскрипции одним предложением. "
    "Не добавляй анализ, рекомендации, следующие шаги, вопросы или варианты действий. "
    "Не повторяй полную транскрипцию и не добавляй заголовки."
)


class Filter:
    class Valves(BaseModel):
        sidecar_base_url: str = Field(default="http://stage2-stt:8080")
        internal_api_key: str = Field(default="")
        request_timeout_seconds: int = Field(default=360, ge=1)
        initial_response_instruction: str = Field(
            default=DEFAULT_INITIAL_RESPONSE_INSTRUCTION,
            description=(
                "Instruction for the ordinary model's first response after an audio upload. "
                "Keep it limited to the short summary; OpenWebUI generates follow-ups separately."
            ),
        )

    def __init__(self) -> None:
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict,
        __user__=None,
        __metadata__=None,
        __event_emitter__=None,
        **_: Any,
    ) -> dict:
        metadata = __metadata__ if isinstance(__metadata__, dict) else body.get("metadata") or {}
        media = self._latest_supported_audio(self._collect_files(body, metadata))
        if media is None:
            return body

        cached_transcript = await self._cached_transcript(
            media["file_id"], (__user__ or {}).get("id")
        )
        if cached_transcript:
            self._remove_processed_audio(body, metadata, media["file_id"])
            metadata["_stage2_audio_transcript"] = cached_transcript
            metadata["_stage2_audio_display"] = (
                await self._cached_display(media["file_id"], (__user__ or {}).get("id"))
                or self._paragraphize_plain_text(cached_transcript)
            )
            self._append_context(body, cached_transcript)
            return body
        if await self._was_transcribed(media["file_id"], (__user__ or {}).get("id")):
            self._remove_processed_audio(body, metadata, media["file_id"])
            return body

        # Audio has one product owner: the STT sidecar. Remove it from the
        # outbound native-file collections before any error path as well; the
        # original attachment still remains in the persisted user message.
        self._remove_processed_audio(body, metadata, media["file_id"])

        await self._emit(__event_emitter__, "Транскрибирую аудио…", done=False)
        token = self.valves.internal_api_key or os.environ.get("STAGE2_STT_INTERNAL_API_KEY", "")
        if not token:
            return await self._inject_failure(
                body, metadata, __event_emitter__, "Транскрибация сейчас не настроена."
            )

        try:
            source_path = await self._native_upload_path(media["file_id"], (__user__ or {}).get("id"))
            stt_media = media
            audio_path = source_path
            with tempfile.TemporaryDirectory(prefix="stage2-audio-") as work_dir:
                if media["is_video"]:
                    source_sha256 = await asyncio.to_thread(self._sha256_file, source_path)
                    prepared = await self._prepare_video(
                        token=token,
                        envelope=self._build_envelope(__user__ or {}, metadata, media),
                        source_path=source_path,
                        filename=media["filename"],
                        mime_type=media["mime_type"],
                        output_path=Path(work_dir) / "prepared-audio",
                    )
                    derived = await self._persist_prepared_audio(
                        user_id=(__user__ or {}).get("id"), source_file_id=media["file_id"],
                        prepared=prepared, source_sha256=source_sha256,
                    )
                    stt_media = {"file_id": derived["file_id"], "filename": derived["filename"], "mime_type": derived["mime_type"], "size_bytes": derived["size_bytes"], "is_video": False}
                    audio_path = prepared["audio_path"]
                result = await self._call_sidecar(
                    token=token,
                    envelope=self._build_envelope(__user__ or {}, metadata, stt_media),
                    audio_path=audio_path,
                    filename=stt_media["filename"],
                    mime_type=stt_media["mime_type"],
                )
        except httpx.HTTPStatusError as exc:
            message = self._format_sidecar_error(exc)
            return await self._inject_failure(body, metadata, __event_emitter__, message)
        except (httpx.HTTPError, OSError, RuntimeError, ValueError):
            return await self._inject_failure(
                body,
                metadata,
                __event_emitter__,
                "Не удалось обработать аудио. Повторите попытку позже.",
            )

        transcript = self._transcript(result)
        if not transcript:
            return await self._inject_failure(
                body,
                metadata,
                __event_emitter__,
                "Сервис не вернул текст транскрипции. Повторите попытку позже.",
            )

        metadata["_stage2_audio_transcript"] = transcript
        metadata["_stage2_audio_display"] = self._format_transcript(result)
        await self._mark_transcribed(
            stt_media["file_id"],
            (__user__ or {}).get("id"),
            transcript,
            metadata["_stage2_audio_display"],
        )
        self._append_context(body, transcript)
        if media["is_video"]:
            metadata["_stage2_video_lifecycle"] = {
                "source_file_id": media["file_id"],
                "audio_file_id": stt_media["file_id"],
                "user_id": (__user__ or {}).get("id"),
                "chat_id": metadata.get("chat_id"),
                # At outlet OpenWebUI identifies the assistant response, while
                # the uploaded video belongs to the preceding user message.
                # The lifecycle overlay resolves that owner from ChatFile.
                "message_id": None,
                "transcript_hash": hashlib.sha256(transcript.encode("utf-8")).hexdigest(),
            }
        await self._emit(__event_emitter__, "Транскрипция готова. Готовлю ответ…", done=True)
        return body

    async def outlet(self, body: dict, __metadata__=None, **_: Any) -> dict:
        metadata = __metadata__ if isinstance(__metadata__, dict) else body.get("metadata") or {}
        transcript = metadata.pop("_stage2_audio_transcript", None)
        display_transcript = metadata.pop("_stage2_audio_display", None)
        if not isinstance(transcript, str) or not transcript:
            return body
        if not isinstance(display_transcript, str) or not display_transcript:
            display_transcript = self._paragraphize_plain_text(transcript)

        for message in reversed(body.get("messages") or []):
            if message.get("role") != "assistant" or not isinstance(message.get("content"), str):
                continue
            if display_transcript:
                summary = message["content"].strip()
                message["content"] = (
                    f"## Краткое содержание\n\n{summary}\n\n"
                    f"---\n\n## Полная транскрипция\n\n"
                    f"{display_transcript}"
                )
            break
        lifecycle = metadata.pop("_stage2_video_lifecycle", None)
        if isinstance(lifecycle, dict):
            try:
                await self._commit_video_lifecycle(lifecycle)
            except RuntimeError:
                # The source video stays available. A failed cleanup must never
                # hide a successful transcript or turn its source into a dead link.
                pass
        return body

    async def _inject_failure(self, body: dict, metadata: dict, emitter, message: str) -> dict:
        metadata["_stage2_audio_transcript"] = None
        self._append_context(body, f"[Транскрибация не выполнена: {message}]")
        await self._emit(emitter, message, done=True)
        return body

    async def _emit(self, emitter, description: str, *, done: bool) -> None:
        if emitter is not None:
            await emitter({"type": "status", "data": {"description": description, "done": done, "hidden": False}})

    def _collect_files(self, body: dict, metadata: dict) -> list[dict]:
        candidates: list[Any] = []
        for source in (body.get("files"), metadata.get("files")):
            if isinstance(source, list):
                candidates.extend(source)

        files: list[dict] = []
        seen_ids: set[str] = set()
        for item in candidates:
            if not isinstance(item, dict):
                continue
            file_obj = item.get("file") if isinstance(item.get("file"), dict) else item
            file_meta = file_obj.get("meta") if isinstance(file_obj.get("meta"), dict) else {}
            file_id = file_obj.get("id") or item.get("id")
            filename = item.get("name") or file_obj.get("filename") or file_meta.get("name")
            mime_type = item.get("content_type") or file_obj.get("mime_type") or file_meta.get("content_type") or ""
            if not file_id or not filename or str(file_id) in seen_ids:
                continue
            seen_ids.add(str(file_id))
            files.append({"file_id": str(file_id), "filename": str(filename), "mime_type": str(mime_type), "size_bytes": item.get("size") or file_meta.get("size"), "is_video": str(mime_type).startswith("video/")})
        return files

    def _latest_supported_audio(self, files: list[dict]) -> dict | None:
        # OpenWebUI may include earlier attachments in metadata on a follow-up
        # turn. The current attachment is the most recent one, never the first
        # audio from the chat history.
        return next(
            (item for item in reversed(files) if self._profile_for_mime(item["mime_type"])),
            None,
        )

    def _profile_for_mime(self, mime_type: str) -> str | None:
        if mime_type == "audio/mpeg":
            return "mp3_high_compat"
        if mime_type.startswith("audio/webm"):
            return "opus_webm_compact"
        if mime_type.startswith("audio/ogg"):
            return "opus_ogg_compact"
        if mime_type in {"audio/wav", "audio/x-wav"}:
            return "wav_pcm_safe"
        if mime_type.startswith("video/"):
            return "mp3_high_compat"
        return None

    async def _prepare_video(self, *, token: str, envelope: dict, source_path: Path, filename: str, mime_type: str, output_path: Path) -> dict:
        async with httpx.AsyncClient(timeout=self.valves.request_timeout_seconds) as client:
            with source_path.open("rb") as source:
                async with client.stream(
                    "POST",
                    f"{self.valves.sidecar_base_url.rstrip('/')}/stage2-api/media/prepare",
                    headers={"Authorization": f"Bearer {token}"},
                    data={"envelope": json.dumps(envelope)},
                    files={"source_media": (filename, source, mime_type)},
                ) as response:
                    if response.is_error:
                        await response.aread()
                        response.raise_for_status()
                    prepared_name = response.headers.get("X-Stage2-Prepared-Filename") or "audio.mp3"
                    prepared_mime = response.headers.get("content-type", "").split(";", 1)[0]
                    if not prepared_mime.startswith("audio/"):
                        raise RuntimeError("Video preparation returned no audio")
                    with output_path.open("wb") as output:
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            output.write(chunk)
        if not output_path.stat().st_size:
            raise RuntimeError("Video preparation returned no audio")
        return {"audio_path": output_path, "filename": prepared_name, "mime_type": prepared_mime, "size_bytes": output_path.stat().st_size}

    async def _persist_prepared_audio(self, *, user_id: str | None, source_file_id: str, prepared: dict, source_sha256: str) -> dict:
        if not user_id:
            raise RuntimeError("Missing authenticated user")
        from open_webui.services.stage2_media_lifecycle import persist_prepared_audio

        derived = await persist_prepared_audio(user_id=user_id, source_file_id=source_file_id, filename=prepared["filename"], mime_type=prepared["mime_type"], audio_path=prepared["audio_path"], source_sha256=source_sha256)
        return {"file_id": derived.file_id, "filename": derived.filename, "mime_type": derived.mime_type, "size_bytes": derived.size_bytes}

    async def _commit_video_lifecycle(self, lifecycle: dict) -> None:
        from open_webui.services.stage2_media_lifecycle import replace_source_video_with_audio

        await replace_source_video_with_audio(**lifecycle)

    async def _native_upload_path(self, file_id: str, user_id: str | None) -> Path:
        if not user_id:
            raise RuntimeError("Missing authenticated user")
        from open_webui.models.files import Files
        from open_webui.storage.provider import Storage

        record = await Files.get_file_by_id_and_user_id(file_id, user_id)
        if record is None:
            raise RuntimeError("Uploaded file is unavailable")
        local_path = await asyncio.to_thread(Storage.get_file, record.path)
        if not local_path:
            raise RuntimeError("Uploaded file is unavailable")
        path = Path(local_path)
        if not path.is_file():
            raise RuntimeError("Uploaded file is unavailable")
        return path

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    async def _was_transcribed(self, file_id: str, user_id: str | None) -> bool:
        if not user_id:
            return False
        from open_webui.models.files import Files

        record = await Files.get_file_by_id_and_user_id(file_id, user_id)
        data = record.data if record is not None and isinstance(record.data, dict) else {}
        return bool(data.get("stage2_audio_context_filter"))

    async def _cached_transcript(self, file_id: str, user_id: str | None) -> str | None:
        if not user_id:
            return None
        from open_webui.models.files import Files

        record = await Files.get_file_by_id_and_user_id(file_id, user_id)
        data = record.data if record is not None and isinstance(record.data, dict) else {}
        marker = data.get("stage2_audio_context_filter")
        transcript = marker.get("transcript") if isinstance(marker, dict) else None
        return transcript.strip() if isinstance(transcript, str) and transcript.strip() else None

    async def _cached_display(self, file_id: str, user_id: str | None) -> str | None:
        if not user_id:
            return None
        from open_webui.models.files import Files

        record = await Files.get_file_by_id_and_user_id(file_id, user_id)
        data = record.data if record is not None and isinstance(record.data, dict) else {}
        marker = data.get("stage2_audio_context_filter")
        display = marker.get("display_transcript") if isinstance(marker, dict) else None
        return display.strip() if isinstance(display, str) and display.strip() else None

    async def _mark_transcribed(
        self,
        file_id: str,
        user_id: str | None,
        transcript: str,
        display_transcript: str,
    ) -> None:
        if not user_id:
            return
        from open_webui.models.files import Files

        record = await Files.get_file_by_id_and_user_id(file_id, user_id)
        if record is None:
            return
        data = dict(record.data) if isinstance(record.data, dict) else {}
        data["stage2_audio_context_filter"] = {
            "state": "transcribed-v1",
            "transcript": transcript,
            "display_transcript": display_transcript,
        }
        await Files.update_file_data_by_id(file_id, data)

    def _build_envelope(self, user: dict, metadata: dict, media: dict) -> dict:
        # ``is_video`` is Filter-internal routing state. The sidecar contract
        # deliberately rejects undeclared fields, so project only the native
        # file reference here.
        file_reference = {
            key: media.get(key)
            for key in ("file_id", "filename", "mime_type", "size_bytes")
        }
        return {"source_context": "openwebui", "user_id": user.get("id"), "user_email": user.get("email"), "user_role": user.get("role"), "user_groups": user.get("groups") or [], "chat_id": metadata.get("chat_id"), "message_id": metadata.get("message_id"), "workspace_id": metadata.get("workspace_id"), "file": file_reference, "selected_output_profile": self._profile_for_mime(media["mime_type"])}

    def _remove_processed_audio(self, body: dict, metadata: dict, file_id: str) -> None:
        for container in (body, metadata):
            files = container.get("files")
            if not isinstance(files, list):
                continue
            container["files"] = [item for item in files if self._attachment_id(item) != file_id]

    def _attachment_id(self, item: Any) -> str | None:
        if not isinstance(item, dict):
            return None
        nested = item.get("file")
        if isinstance(nested, dict) and nested.get("id"):
            return str(nested["id"])
        return str(item["id"]) if item.get("id") else None

    async def _call_sidecar(self, *, token: str, envelope: dict, audio_path: Path, filename: str, mime_type: str) -> dict:
        async with httpx.AsyncClient(timeout=self.valves.request_timeout_seconds) as client:
            with audio_path.open("rb") as audio:
                response = await client.post(f"{self.valves.sidecar_base_url.rstrip('/')}/stage2-api/transcription/jobs", headers={"Authorization": f"Bearer {token}"}, data={"envelope": json.dumps(envelope)}, files={"prepared_audio": (filename, audio, mime_type)})
            response.raise_for_status()
            return response.json()

    def _append_context(self, body: dict, transcript: str) -> None:
        for message in reversed(body.get("messages") or []):
            if message.get("role") != "user" or not isinstance(message.get("content"), str):
                continue
            instruction = self.valves.initial_response_instruction.strip()
            if not instruction:
                instruction = DEFAULT_INITIAL_RESPONSE_INSTRUCTION
            message["content"] += (
                "\n\n[Системная транскрипция прикреплённого аудио]\n"
                + transcript
                + "\n[/Системная транскрипция]\n\n"
                + instruction
            )
            return

    def _transcript(self, result: dict) -> str:
        payload = result.get("result") if isinstance(result, dict) else None
        return str(payload.get("text") or "").strip() if isinstance(payload, dict) else ""

    def _format_transcript(self, response: dict) -> str:
        payload = response.get("result") if isinstance(response, dict) else None
        if not isinstance(payload, dict):
            return ""

        plain_text = str(payload.get("text") or "").strip()
        segments = payload.get("segments")
        if not isinstance(segments, list):
            return self._paragraphize_plain_text(plain_text)

        turns = self._speaker_turns(segments)
        if turns:
            return "\n\n".join(self._format_speaker_turn(turn) for turn in turns)

        segment_texts = [
            str(segment.get("text") or "").strip()
            for segment in segments
            if isinstance(segment, dict) and str(segment.get("text") or "").strip()
        ]
        if segment_texts:
            return "\n\n".join(segment_texts)
        return self._paragraphize_plain_text(plain_text)

    def _speaker_turns(self, segments: list[Any]) -> list[dict[str, Any]]:
        labels: dict[str, str] = {}
        turns: list[dict[str, Any]] = []
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            raw_speaker = str(segment.get("speaker") or "").strip()
            text = str(segment.get("text") or "").strip()
            if not raw_speaker or not text:
                continue
            speaker = labels.setdefault(raw_speaker, f"Спикер {len(labels) + 1}")
            start = self._optional_seconds(segment.get("start_seconds", segment.get("start")))
            end = self._optional_seconds(segment.get("end_seconds", segment.get("end")))
            if turns and turns[-1]["speaker"] == speaker:
                turns[-1]["texts"].append(text)
                turns[-1]["end"] = end if end is not None else turns[-1]["end"]
                continue
            turns.append({"speaker": speaker, "texts": [text], "start": start, "end": end})
        return turns

    def _format_speaker_turn(self, turn: dict[str, Any]) -> str:
        start = self._format_seconds(turn.get("start"))
        end = self._format_seconds(turn.get("end"))
        timestamp = f"[{start}-{end}] " if start and end else f"[{start}] " if start else ""
        text = " ".join(part for part in turn["texts"] if part)
        return f"{timestamp}{turn['speaker']}:\n{text}"

    def _optional_seconds(self, value: Any) -> float | None:
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return None
        return seconds if seconds >= 0 else None

    def _format_seconds(self, value: float | None) -> str:
        if value is None:
            return ""
        total = int(round(value))
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"

    def _paragraphize_plain_text(self, text: str) -> str:
        text = text.strip()
        if len(text) <= 700 or "\n\n" in text:
            return text
        paragraphs: list[str] = []
        remainder = text
        while len(remainder) > 700:
            boundary = remainder.rfind(" ", 0, 700)
            if boundary < 200:
                boundary = 700
            paragraphs.append(remainder[:boundary].strip())
            remainder = remainder[boundary:].strip()
        paragraphs.append(remainder)
        return "\n\n".join(part for part in paragraphs if part)

    def _format_sidecar_error(self, exc: httpx.HTTPStatusError) -> str:
        if exc.response.status_code >= 500:
            return "Сервис транскрибации временно недоступен. Повторите попытку позже."
        try:
            detail = exc.response.json().get("detail")
            code = detail.get("code") if isinstance(detail, dict) else None
        except (TypeError, ValueError, json.JSONDecodeError):
            code = None
        if code == "source_has_no_audio_stream":
            return "Видеофайл не содержит аудиодорожки. Выберите видео со звуком."
        return "Сервис транскрибации отклонил аудиофайл. Проверьте формат и повторите попытку."
