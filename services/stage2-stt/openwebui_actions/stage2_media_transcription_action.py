"""
title: Stage 2 Media Transcription
author: Alpha Soft
version: 0.1.0
required_open_webui_version: 0.9.6
requirements: httpx,pydantic
"""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field


DEFAULT_WARNING_ALIASES = {
    "prepared_audio_storage_transient": (
        "На данном этапе MVP аудиофайл, отправленный на транскрибацию, не сохраняется."
    ),
}
DEFAULT_WARNING_ALIASES_JSON = json.dumps(DEFAULT_WARNING_ALIASES, ensure_ascii=False)


class Action:
    def __init__(self) -> None:
        self.valves = self.Valves()

    class Valves(BaseModel):
        sidecar_base_url: str = Field(default="http://stage2-stt:8080")
        internal_api_key: str = Field(default="")
        upload_root: str = Field(default="/app/backend/data/uploads")
        allow_upload_path_access: bool = Field(default=True)
        request_timeout_seconds: int = Field(default=180, ge=1)
        priority: int = Field(default=0)
        warning_aliases_json: str = Field(default=DEFAULT_WARNING_ALIASES_JSON)

    async def action(
        self,
        body: dict,
        __user__=None,
        __metadata__=None,
        __event_emitter__=None,
        **kwargs,
    ):
        await self._emit(__event_emitter__, "Checking media attachment...", done=False)

        files = self._collect_files(body, __metadata__, kwargs.get("__files__"))
        media = self._first_supported_audio(files)
        if media is None:
            await self._emit(__event_emitter__, "No supported prepared audio attachment.", done=True)
            return {
                "content": (
                    "No supported prepared audio attachment was found. "
                    "For this Action-only probe, attach MP3, WebM/Opus, OGG/Opus or WAV. "
                    "Browser ffmpeg.wasm normalization for video/source media requires the "
                    "next OpenWebUI runtime/frontend probe."
                )
            }

        output_profile = self._profile_for_mime(media["mime_type"])
        token = self.valves.internal_api_key or os.environ.get("STAGE2_STT_INTERNAL_API_KEY", "")
        if not token:
            await self._emit(__event_emitter__, "STT sidecar internal token is not configured.", done=True)
            return {"content": "STT transcription is not configured for this OpenWebUI action."}

        try:
            audio_path = self._uploaded_file_path(media)
            audio_bytes = audio_path.read_bytes()
        except Exception as exc:
            await self._emit(__event_emitter__, "Unable to access uploaded media bytes.", done=True)
            return {"content": f"Unable to access uploaded media bytes safely: {exc}"}

        envelope = self._build_envelope(
            user=__user__ or {},
            metadata=__metadata__ or {},
            media=media,
            output_profile=output_profile,
        )

        await self._emit(__event_emitter__, "Sending prepared audio to STT sidecar...", done=False)
        try:
            result = await self._call_sidecar(
                token=token,
                envelope=envelope,
                audio_bytes=audio_bytes,
                filename=media["filename"],
                mime_type=media["mime_type"],
            )
        except httpx.HTTPError as exc:
            await self._emit(__event_emitter__, "STT sidecar request failed.", done=True)
            return {"content": f"STT sidecar request failed: {exc}"}

        transcript = ((result.get("result") or {}).get("text") or "").strip()
        warnings = result.get("warnings") or []
        await self._emit(__event_emitter__, "Transcription complete.", done=True)
        if not transcript:
            transcript = "[empty transcript]"
        warning_text = self._format_warnings(warnings)
        return {"content": f"Transcript:\n\n{transcript}{warning_text}"}

    async def _emit(self, emitter, description: str, *, done: bool) -> None:
        if emitter is None:
            return
        await emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done, "hidden": False},
            }
        )

    def _collect_files(self, body: dict, metadata: dict | None, files_arg: Any) -> list[dict]:
        candidates: list[Any] = []
        if isinstance(files_arg, list):
            candidates.extend(files_arg)
        if isinstance(metadata, dict) and isinstance(metadata.get("files"), list):
            candidates.extend(metadata["files"])
        if isinstance(body.get("files"), list):
            candidates.extend(body["files"])

        normalized = []
        for item in candidates:
            file_obj = item.get("file") if isinstance(item, dict) else None
            if not isinstance(file_obj, dict):
                continue
            filename = file_obj.get("filename") or file_obj.get("name")
            mime_type = (
                file_obj.get("mime_type")
                or file_obj.get("content_type")
                or file_obj.get("type")
                or ""
            )
            file_id = file_obj.get("id")
            if filename and file_id:
                normalized.append(
                    {
                        "file_id": str(file_id),
                        "filename": str(filename),
                        "mime_type": str(mime_type),
                        "size_bytes": file_obj.get("size") or file_obj.get("size_bytes"),
                    }
                )
        return normalized

    def _first_supported_audio(self, files: list[dict]) -> dict | None:
        for file in files:
            if self._profile_for_mime(file["mime_type"]) is not None:
                return file
        return None

    def _profile_for_mime(self, mime_type: str) -> str | None:
        if mime_type == "audio/mpeg":
            return "mp3_high_compat"
        if mime_type.startswith("audio/webm"):
            return "opus_webm_compact"
        if mime_type.startswith("audio/ogg"):
            return "opus_ogg_compact"
        if mime_type in {"audio/wav", "audio/x-wav"}:
            return "wav_pcm_safe"
        return None

    def _format_warnings(self, warnings: list[str]) -> str:
        normalized = list(dict.fromkeys(str(warning) for warning in warnings if warning))
        if not normalized:
            return ""

        aliases = self._warning_aliases()
        notes = [aliases[warning] for warning in normalized if warning in aliases]
        technical = [warning for warning in normalized if warning not in aliases]

        parts = []
        if notes:
            parts.append("Примечания:\n" + "\n".join(f"- {note}" for note in notes))
        if technical:
            parts.append("Технические предупреждения: " + ", ".join(technical))
        return "\n\n" + "\n\n".join(parts)

    def _warning_aliases(self) -> dict[str, str]:
        aliases = dict(DEFAULT_WARNING_ALIASES)
        try:
            configured = json.loads(self.valves.warning_aliases_json or "{}")
        except ValueError:
            return aliases
        if isinstance(configured, dict):
            aliases.update(
                {
                    str(code): str(message)
                    for code, message in configured.items()
                    if code and message
                }
            )
        return aliases

    def _uploaded_file_path(self, media: dict) -> Path:
        if not self.valves.allow_upload_path_access:
            raise RuntimeError("upload path access is disabled")

        upload_root = Path(self.valves.upload_root).resolve()
        candidate = (upload_root / f"{media['file_id']}_{media['filename']}").resolve()
        if upload_root not in candidate.parents and candidate != upload_root:
            raise RuntimeError("upload path escaped configured upload root")
        if not candidate.exists():
            raise RuntimeError("upload file path does not exist")
        return candidate

    def _build_envelope(
        self,
        *,
        user: dict,
        metadata: dict,
        media: dict,
        output_profile: str,
    ) -> dict:
        return {
            "source_context": "openwebui",
            "user_id": user.get("id") or user.get("user_id"),
            "user_email": user.get("email"),
            "user_role": user.get("role"),
            "user_groups": user.get("groups") or [],
            "chat_id": metadata.get("chat_id"),
            "message_id": metadata.get("message_id"),
            "workspace_id": metadata.get("workspace_id"),
            "file": {
                "file_id": media["file_id"],
                "filename": media["filename"],
                "mime_type": media["mime_type"],
                "size_bytes": media.get("size_bytes"),
            },
            "selected_output_profile": output_profile,
        }

    async def _call_sidecar(
        self,
        *,
        token: str,
        envelope: dict,
        audio_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> dict:
        async with httpx.AsyncClient(timeout=self.valves.request_timeout_seconds) as client:
            response = await client.post(
                f"{self.valves.sidecar_base_url.rstrip('/')}/stage2-api/transcription/jobs",
                headers={"Authorization": f"Bearer {token}"},
                data={"envelope": json.dumps(envelope)},
                files={"prepared_audio": (filename, audio_bytes, mime_type)},
            )
            response.raise_for_status()
            return response.json()
