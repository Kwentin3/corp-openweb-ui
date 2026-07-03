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
        operation = self._stage2_operation(body)
        if operation == "list_postprocessing_templates":
            return await self._list_postprocessing_templates(
                body=body,
                user=__user__ or {},
                metadata=__metadata__ or {},
                emitter=__event_emitter__,
            )
        if operation == "execute_postprocessing":
            return await self._execute_postprocessing(
                body=body,
                user=__user__ or {},
                metadata=__metadata__ or {},
                emitter=__event_emitter__,
            )
        if operation == "draft_postprocessing_prompt":
            return await self._draft_postprocessing_prompt(
                body=body,
                user=__user__ or {},
                metadata=__metadata__ or {},
                emitter=__event_emitter__,
            )
        if operation == "export_message_docx":
            return await self._export_message_docx(
                body=body,
                user=__user__ or {},
                metadata=__metadata__ or {},
                emitter=__event_emitter__,
            )

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

        transcript = self._format_transcript_result(result.get("result"))
        warnings = result.get("warnings") or []
        await self._emit(__event_emitter__, "Transcription complete.", done=True)
        if not transcript:
            transcript = "[empty transcript]"
        warning_text = self._format_warnings(warnings)
        ref_text = self._format_transcript_ref(result.get("transcript_ref"))
        return {"content": f"Transcript:\n\n{transcript}{ref_text}{warning_text}"}

    def _stage2_operation(self, body: dict) -> str | None:
        if not isinstance(body, dict):
            return None
        stage2 = body.get("stage2_stt")
        if isinstance(stage2, dict) and stage2.get("operation"):
            return str(stage2["operation"])
        message_docx = body.get("stage2_message_docx")
        if not isinstance(message_docx, dict):
            return None
        operation = message_docx.get("operation")
        return str(operation) if operation else None

    async def _list_postprocessing_templates(
        self,
        *,
        body: dict,
        user: dict,
        metadata: dict,
        emitter,
    ) -> dict:
        await self._emit(emitter, "Loading transcript actions...", done=False)
        token = self.valves.internal_api_key or os.environ.get("STAGE2_STT_INTERNAL_API_KEY", "")
        if not token:
            await self._emit(emitter, "STT sidecar internal token is not configured.", done=True)
            return {
                "content": "STT post-processing is not configured for this OpenWebUI action.",
                "stage2_stt_templates": [],
            }
        try:
            templates = await self._call_sidecar_templates(
                token=token,
                user=user,
            )
        except httpx.HTTPError as exc:
            await self._emit(emitter, "Transcript actions unavailable.", done=True)
            return {
                "content": f"STT post-processing templates unavailable: {exc}",
                "stage2_stt_templates": [],
            }
        await self._emit(emitter, "Transcript actions loaded.", done=True)
        return {"content": "", "stage2_stt_templates": templates}

    async def _execute_postprocessing(
        self,
        *,
        body: dict,
        user: dict,
        metadata: dict,
        emitter,
    ) -> dict:
        stage2 = body.get("stage2_stt") if isinstance(body, dict) else {}
        if not isinstance(stage2, dict):
            stage2 = {}
        transcript_ref = str(stage2.get("transcript_ref") or "")
        template_id = str(stage2.get("template_id") or "")
        if not transcript_ref.startswith("art_") or not template_id:
            return {"content": "STT post-processing request is invalid."}

        token = self.valves.internal_api_key or os.environ.get("STAGE2_STT_INTERNAL_API_KEY", "")
        if not token:
            await self._emit(emitter, "STT sidecar internal token is not configured.", done=True)
            return {"content": "STT post-processing is not configured for this OpenWebUI action."}

        await self._emit(emitter, "Running transcript action...", done=False)
        try:
            result = await self._call_sidecar_postprocessing(
                token=token,
                user=user,
                metadata=metadata,
                body=body,
                transcript_ref=transcript_ref,
                template_id=template_id,
            )
        except httpx.HTTPStatusError as exc:
            await self._emit(emitter, "Transcript action failed.", done=True)
            return {"content": self._format_postprocessing_error(exc)}
        except httpx.HTTPError as exc:
            await self._emit(emitter, "Transcript action failed.", done=True)
            return {"content": f"STT post-processing request failed: {exc}"}
        await self._emit(emitter, "Transcript action complete.", done=True)
        return {"content": self._format_postprocessing_result(result)}

    async def _draft_postprocessing_prompt(
        self,
        *,
        body: dict,
        user: dict,
        metadata: dict,
        emitter,
    ) -> dict:
        stage2 = body.get("stage2_stt") if isinstance(body, dict) else {}
        if not isinstance(stage2, dict):
            stage2 = {}
        transcript_ref = str(stage2.get("transcript_ref") or "")
        template_id = str(stage2.get("template_id") or "")
        if not transcript_ref.startswith("art_") or not template_id:
            return {
                "content": "STT post-processing prompt draft request is invalid.",
                "stage2_stt_prompt_draft": None,
            }

        token = self.valves.internal_api_key or os.environ.get("STAGE2_STT_INTERNAL_API_KEY", "")
        if not token:
            await self._emit(emitter, "STT sidecar internal token is not configured.", done=True)
            return {
                "content": "STT post-processing is not configured for this OpenWebUI action.",
                "stage2_stt_prompt_draft": None,
            }

        await self._emit(emitter, "Preparing transcript prompt...", done=False)
        try:
            result = await self._call_sidecar_postprocessing_prompt_draft(
                token=token,
                user=user,
                metadata=metadata,
                body=body,
                transcript_ref=transcript_ref,
                template_id=template_id,
            )
        except httpx.HTTPStatusError as exc:
            await self._emit(emitter, "Transcript prompt preparation failed.", done=True)
            return {
                "content": self._format_postprocessing_error(exc),
                "stage2_stt_prompt_draft": None,
            }
        except httpx.HTTPError as exc:
            await self._emit(emitter, "Transcript prompt preparation failed.", done=True)
            return {
                "content": f"STT post-processing prompt draft request failed: {exc}",
                "stage2_stt_prompt_draft": None,
            }
        await self._emit(emitter, "Transcript prompt ready.", done=True)
        return {"content": "", "stage2_stt_prompt_draft": result}

    async def _export_message_docx(
        self,
        *,
        body: dict,
        user: dict,
        metadata: dict,
        emitter,
    ) -> dict:
        stage2 = body.get("stage2_message_docx") if isinstance(body, dict) else {}
        if not isinstance(stage2, dict):
            stage2 = {}
        request = stage2.get("request")
        if not isinstance(request, dict):
            return {
                "content": "",
                "stage2_message_docx_error": {
                    "code": "message_docx_no_safe_source",
                    "message": "DOCX export request is invalid.",
                },
            }

        token = self.valves.internal_api_key or os.environ.get("STAGE2_STT_INTERNAL_API_KEY", "")
        if not token:
            await self._emit(emitter, "DOCX export is not configured.", done=True)
            return {
                "content": "",
                "stage2_message_docx_error": {
                    "code": "message_docx_access_denied",
                    "message": "DOCX export is not configured.",
                },
            }

        user_id = user.get("id") or user.get("user_id")
        if user_id:
            request = dict(request)
            metadata_payload = request.get("safe_metadata")
            if not isinstance(metadata_payload, dict):
                metadata_payload = {}
            if not metadata_payload.get("source_url_path") and metadata.get("chat_id"):
                metadata_payload["source_url_path"] = f"/c/{metadata.get('chat_id')}"
            request["safe_metadata"] = metadata_payload

        await self._emit(emitter, "Preparing DOCX export...", done=False)
        try:
            result = await self._call_sidecar_message_docx(token=token, request=request)
        except httpx.HTTPStatusError as exc:
            await self._emit(emitter, "DOCX export failed.", done=True)
            return {"content": "", "stage2_message_docx_error": self._format_docx_http_error(exc)}
        except httpx.HTTPError:
            await self._emit(emitter, "DOCX export failed.", done=True)
            return {
                "content": "",
                "stage2_message_docx_error": {
                    "code": "message_docx_generation_failed",
                    "message": "DOCX export request failed.",
                },
            }
        await self._emit(emitter, "DOCX export ready.", done=True)
        return {"content": "", "stage2_message_docx_export": result}

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

    def _format_transcript_ref(self, transcript_ref: Any) -> str:
        if not isinstance(transcript_ref, str) or not transcript_ref.startswith("art_"):
            return ""
        return f"\n\nTranscript reference: `{transcript_ref}`"

    def _format_transcript_result(self, result: Any) -> str:
        if not isinstance(result, dict):
            return ""

        plain_text = str(result.get("text") or "").strip()
        segments = result.get("segments")
        if not isinstance(segments, list):
            return plain_text

        has_speakers = any(
            isinstance(segment, dict) and bool(segment.get("speaker"))
            for segment in segments
        )
        if not has_speakers:
            return plain_text

        turns = self._speaker_turns(segments)
        if not turns:
            return plain_text

        return "\n\n".join(self._format_speaker_turn(turn) for turn in turns)

    def _speaker_turns(self, segments: list[Any]) -> list[dict[str, Any]]:
        speaker_labels: dict[str, str] = {}
        turns: list[dict[str, Any]] = []

        for segment in segments:
            if not isinstance(segment, dict):
                continue

            text = str(segment.get("text") or "").strip()
            if not text:
                continue

            speaker = self._display_speaker_label(segment.get("speaker"), speaker_labels)
            start_seconds = self._optional_seconds(
                segment.get("start_seconds", segment.get("start"))
            )
            end_seconds = self._optional_seconds(
                segment.get("end_seconds", segment.get("end"))
            )

            if turns and turns[-1]["speaker"] == speaker:
                turns[-1]["texts"].append(text)
                if turns[-1]["start_seconds"] is None:
                    turns[-1]["start_seconds"] = start_seconds
                if end_seconds is not None:
                    turns[-1]["end_seconds"] = end_seconds
                continue

            turns.append(
                {
                    "speaker": speaker,
                    "texts": [text],
                    "start_seconds": start_seconds,
                    "end_seconds": end_seconds,
                }
            )

        return turns

    def _display_speaker_label(self, raw_speaker: Any, labels: dict[str, str]) -> str:
        speaker = str(raw_speaker or "").strip()
        if not speaker:
            return "Спикер неизвестен"
        if speaker not in labels:
            labels[speaker] = f"Спикер {len(labels) + 1}"
        return labels[speaker]

    def _format_speaker_turn(self, turn: dict[str, Any]) -> str:
        time_prefix = self._format_time_prefix(
            turn.get("start_seconds"),
            turn.get("end_seconds"),
        )
        text = " ".join(str(part).strip() for part in turn.get("texts") or [] if part)
        return f"{time_prefix}{turn['speaker']}:\n{text}"

    def _optional_seconds(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return None
        if seconds < 0:
            return None
        return seconds

    def _format_time_prefix(self, start_seconds: Any, end_seconds: Any) -> str:
        start = self._format_seconds(start_seconds)
        end = self._format_seconds(end_seconds)
        if start and end:
            return f"[{start}-{end}] "
        if start:
            return f"[{start}] "
        return ""

    def _format_seconds(self, value: Any) -> str:
        if value is None:
            return ""
        total_seconds = int(round(float(value)))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _format_postprocessing_result(self, result: dict) -> str:
        text = str(result.get("text") or "").strip() or "[empty post-processing result]"
        label = str(result.get("label") or result.get("template_id") or "Transcript action")
        ref = result.get("result_ref")
        ref_text = f"\n\nPost-processing result reference: `{ref}`" if isinstance(ref, str) and ref.startswith("art_") else ""
        return f"{label}\n\n{text}{ref_text}"

    def _format_postprocessing_error(self, exc: httpx.HTTPStatusError) -> str:
        try:
            payload = exc.response.json()
        except ValueError:
            return f"STT post-processing failed with HTTP {exc.response.status_code}."
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(detail, dict):
            code = detail.get("code") or "postprocessing_failed"
            message = detail.get("message") or "Post-processing failed"
            return f"STT post-processing failed: {message} [{code}]"
        return f"STT post-processing failed with HTTP {exc.response.status_code}."

    def _format_docx_http_error(self, exc: httpx.HTTPStatusError) -> dict:
        try:
            payload = exc.response.json()
        except ValueError:
            return {
                "code": "message_docx_generation_failed",
                "message": f"DOCX export failed with HTTP {exc.response.status_code}.",
            }
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if isinstance(detail, dict):
            return {
                "code": str(detail.get("code") or "message_docx_generation_failed"),
                "message": str(detail.get("message") or "DOCX export failed."),
            }
        return {
            "code": "message_docx_generation_failed",
            "message": f"DOCX export failed with HTTP {exc.response.status_code}.",
        }

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

    def _build_artifact_context(self, *, user: dict, metadata: dict, body: dict) -> dict:
        stage2 = body.get("stage2_stt") if isinstance(body, dict) else {}
        if not isinstance(stage2, dict):
            stage2 = {}
        return {
            "workspace_id": stage2.get("workspace_id") or metadata.get("workspace_id"),
            "user_id": user.get("id") or user.get("user_id"),
            "chat_id": stage2.get("chat_id") or metadata.get("chat_id") or body.get("chat_id"),
            "message_id": stage2.get("message_id") or metadata.get("message_id"),
            "openwebui_file_id": stage2.get("openwebui_file_id"),
            "tenant_id": stage2.get("tenant_id"),
        }

    def _build_user_context(self, *, user: dict) -> dict:
        return {
            "user_id": user.get("id") or user.get("user_id"),
            "user_role": user.get("role"),
            "user_groups": user.get("groups") or [],
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

    async def _call_sidecar_templates(self, *, token: str, user: dict) -> list[dict]:
        params = self._build_user_context(user=user)
        groups = params.pop("user_groups", [])
        if groups:
            params["user_groups"] = ",".join(str(group) for group in groups if group)
        async with httpx.AsyncClient(timeout=self.valves.request_timeout_seconds) as client:
            response = await client.get(
                f"{self.valves.sidecar_base_url.rstrip('/')}/stage2-api/transcription/post-processing/templates",
                headers={"Authorization": f"Bearer {token}"},
                params={key: value for key, value in params.items() if value},
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []

    async def _call_sidecar_postprocessing(
        self,
        *,
        token: str,
        user: dict,
        metadata: dict,
        body: dict,
        transcript_ref: str,
        template_id: str,
    ) -> dict:
        request = self._build_postprocessing_request(
            user=user,
            metadata=metadata,
            body=body,
            transcript_ref=transcript_ref,
            template_id=template_id,
        )
        async with httpx.AsyncClient(timeout=self.valves.request_timeout_seconds) as client:
            response = await client.post(
                f"{self.valves.sidecar_base_url.rstrip('/')}/stage2-api/transcription/post-processing/execute",
                headers={"Authorization": f"Bearer {token}"},
                json=request,
            )
            response.raise_for_status()
            return response.json()

    async def _call_sidecar_postprocessing_prompt_draft(
        self,
        *,
        token: str,
        user: dict,
        metadata: dict,
        body: dict,
        transcript_ref: str,
        template_id: str,
    ) -> dict:
        request = self._build_postprocessing_request(
            user=user,
            metadata=metadata,
            body=body,
            transcript_ref=transcript_ref,
            template_id=template_id,
        )
        async with httpx.AsyncClient(timeout=self.valves.request_timeout_seconds) as client:
            response = await client.post(
                f"{self.valves.sidecar_base_url.rstrip('/')}/stage2-api/transcription/post-processing/prompt-draft",
                headers={"Authorization": f"Bearer {token}"},
                json=request,
            )
            response.raise_for_status()
            return response.json()

    def _build_postprocessing_request(
        self,
        *,
        user: dict,
        metadata: dict,
        body: dict,
        transcript_ref: str,
        template_id: str,
    ) -> dict:
        return {
            "transcript_ref": transcript_ref,
            "template_id": template_id,
            "user_context": self._build_user_context(user=user),
            "artifact_context": self._build_artifact_context(
                user=user,
                metadata=metadata,
                body=body,
            ),
        }

    async def _call_sidecar_message_docx(self, *, token: str, request: dict) -> dict:
        async with httpx.AsyncClient(timeout=self.valves.request_timeout_seconds) as client:
            response = await client.post(
                f"{self.valves.sidecar_base_url.rstrip('/')}/stage2-api/message-docx/exports",
                headers={"Authorization": f"Bearer {token}"},
                json=request,
            )
            response.raise_for_status()
            return response.json()
