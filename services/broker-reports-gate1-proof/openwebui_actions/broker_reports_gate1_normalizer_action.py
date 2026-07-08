"""
title: Broker Reports Gate 1 Normalizer Stub
author: Alpha Soft
version: 0.1.1-proof
required_open_webui_version: 0.9.6
requirements: pydantic
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


SAFE_REPORT_SCHEMA = "broker_reports_chat_visible_normalization_report_v0"
SAFETY_STATEMENT = (
    "Gate 1 did not calculate tax, extract source facts through LLM, generate "
    "declaration, generate XLS/XLSX or file with FNS."
)


class Action:
    """Proof-only Action stub for OpenWebUI -> file refs -> safe report."""

    def __init__(self) -> None:
        self.valves = self.Valves()

    class Valves(BaseModel):
        upload_root: str = Field(default="/app/backend/data/uploads")
        allow_upload_path_access: bool = Field(default=True)
        prove_original_bytes_access: bool = Field(default=False)

    async def action(
        self,
        body: dict,
        __user__=None,
        __metadata__=None,
        __event_emitter__=None,
        **kwargs,
    ) -> dict:
        await self._emit(__event_emitter__, "Checking uploaded file refs...", done=False)

        file_refs = self._collect_file_refs(
            body if isinstance(body, dict) else {},
            __metadata__ if isinstance(__metadata__, dict) else {},
            kwargs.get("__files__"),
            kwargs.get("__messages__"),
        )
        input_context = self._safe_input_context(
            body if isinstance(body, dict) else {},
            __metadata__ if isinstance(__metadata__, dict) else {},
            kwargs.get("__files__"),
            kwargs.get("__messages__"),
        )
        if not file_refs:
            report = self._safe_report(
                file_refs=[],
                bytes_probe={"status": "not_started", "files_with_bytes": 0},
                run_status="failed_safe",
                blockers_total=1,
                input_context=input_context,
            )
            await self._emit(__event_emitter__, "No uploaded file refs were visible.", done=True)
            return self._response(report)

        await self._emit(__event_emitter__, "Building safe Gate 1 stub report...", done=False)
        bytes_probe = (
            self._probe_original_bytes(file_refs)
            if self.valves.prove_original_bytes_access
            else {"status": "not_requested", "files_with_bytes": 0}
        )
        report = self._safe_report(
            file_refs=file_refs,
            bytes_probe=bytes_probe,
            run_status="completed_with_blockers",
            blockers_total=0,
            input_context=input_context,
        )
        await self._emit(__event_emitter__, "Gate 1 stub report ready.", done=True)
        return self._response(report)

    async def _emit(self, emitter, description: str, *, done: bool) -> None:
        if emitter is None:
            return
        await emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done, "hidden": False},
            }
        )

    def _collect_file_refs(
        self,
        body: dict,
        metadata: dict,
        files_arg: Any,
        messages_arg: Any = None,
    ) -> list[dict[str, Any]]:
        candidates: list[Any] = []
        for source in (files_arg, metadata.get("files"), body.get("files")):
            self._append_file_candidates(candidates, source)
        for source in (
            body.get("message"),
            body.get("messages"),
            metadata.get("message"),
            metadata.get("messages"),
            messages_arg,
        ):
            self._append_message_file_candidates(candidates, source)

        refs: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in candidates:
            file_obj = self._file_obj(item)
            if not isinstance(file_obj, dict):
                continue

            file_id = self._file_id(file_obj)
            filename = self._filename(file_obj)
            mime_type = self._mime_type(file_obj)
            if not file_id:
                continue
            stable_key = str(file_id)
            if stable_key in seen:
                continue
            seen.add(stable_key)
            refs.append(
                {
                    "file_id": stable_key,
                    "filename": str(filename),
                    "extension": self._extension(filename, mime_type),
                    "mime_type": str(mime_type),
                    "size_bytes": self._optional_int(
                        file_obj.get("size") or file_obj.get("size_bytes")
                    ),
                }
            )
        return refs

    def _append_file_candidates(self, candidates: list[Any], source: Any) -> None:
        if isinstance(source, list):
            candidates.extend(source)
        elif isinstance(source, dict):
            candidates.append(source)

    def _append_message_file_candidates(self, candidates: list[Any], source: Any) -> None:
        for message in self._message_iter(source):
            if isinstance(message, dict):
                self._append_file_candidates(candidates, message.get("files"))
                self._append_nested_file_candidates(candidates, message, depth=0)

    def _append_nested_file_candidates(
        self,
        candidates: list[Any],
        value: Any,
        *,
        depth: int,
    ) -> None:
        if depth > 4:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "files":
                    self._append_file_candidates(candidates, child)
                    continue
                if key in {"content", "text"}:
                    continue
                self._append_nested_file_candidates(candidates, child, depth=depth + 1)
            return
        if isinstance(value, list):
            for item in value:
                self._append_nested_file_candidates(candidates, item, depth=depth + 1)

    def _message_iter(self, source: Any) -> list[Any]:
        if isinstance(source, list):
            return source
        if isinstance(source, dict):
            return [source]
        return []

    def _file_obj(self, item: Any) -> dict[str, Any] | None:
        if not isinstance(item, dict):
            return None
        nested = item.get("file")
        if isinstance(nested, dict):
            merged = dict(item)
            merged.update(nested)
            return merged
        return item

    def _file_id(self, file_obj: dict[str, Any]) -> str:
        value = file_obj.get("id") or file_obj.get("file_id")
        if value:
            return str(value)
        for key in ("url", "path", "href"):
            parsed = self._file_id_from_path(file_obj.get(key))
            if parsed:
                return parsed
        return ""

    def _file_id_from_path(self, value: Any) -> str:
        text = str(value or "")
        marker = "/api/v1/files/"
        if marker not in text:
            return ""
        suffix = text.split(marker, 1)[1]
        file_id = suffix.split("/", 1)[0].split("?", 1)[0].strip()
        return file_id

    def _filename(self, file_obj: dict[str, Any]) -> str:
        meta = file_obj.get("meta") if isinstance(file_obj.get("meta"), dict) else {}
        return str(
            file_obj.get("filename")
            or file_obj.get("name")
            or file_obj.get("original_filename")
            or meta.get("filename")
            or meta.get("name")
            or ""
        )

    def _mime_type(self, file_obj: dict[str, Any]) -> str:
        meta = file_obj.get("meta") if isinstance(file_obj.get("meta"), dict) else {}
        return str(
            file_obj.get("mime_type")
            or file_obj.get("content_type")
            or meta.get("mime_type")
            or meta.get("content_type")
            or ""
        )

    def _safe_input_context(
        self,
        body: dict,
        metadata: dict,
        files_arg: Any,
        messages_arg: Any,
    ) -> dict[str, Any]:
        message_sources = [
            body.get("message"),
            body.get("messages"),
            metadata.get("message"),
            metadata.get("messages"),
            messages_arg,
        ]
        messages = []
        for source in message_sources:
            messages.extend(self._message_iter(source))
        return {
            "body_files_count": self._safe_len(body.get("files")),
            "metadata_files_count": self._safe_len(metadata.get("files")),
            "files_arg_count": self._safe_len(files_arg),
            "messages_count": len(messages),
            "messages_with_files_count": sum(
                1
                for message in messages
                if isinstance(message, dict) and self._safe_len(message.get("files")) > 0
            ),
        }

    def _safe_len(self, value: Any) -> int:
        return len(value) if isinstance(value, list) else 0

    def _probe_original_bytes(self, file_refs: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.valves.allow_upload_path_access:
            return {"status": "blocked", "reason": "upload_path_access_disabled", "files_with_bytes": 0}

        upload_root = Path(self.valves.upload_root).resolve()
        files_with_bytes = 0
        bytes_total = 0
        for file_ref in file_refs:
            filename = file_ref.get("filename") or ""
            file_id = file_ref.get("file_id") or ""
            candidate = (upload_root / f"{file_id}_{filename}").resolve()
            if upload_root not in candidate.parents and candidate != upload_root:
                return {"status": "blocked", "reason": "upload_path_escape_detected", "files_with_bytes": files_with_bytes}
            if not candidate.exists() or not candidate.is_file():
                continue
            data = candidate.read_bytes()
            files_with_bytes += 1
            bytes_total += len(data)
        if files_with_bytes:
            return {
                "status": "proven",
                "files_with_bytes": files_with_bytes,
                "bytes_total": bytes_total,
            }
        return {"status": "blocked", "reason": "upload_files_not_found", "files_with_bytes": 0}

    def _safe_report(
        self,
        *,
        file_refs: list[dict[str, Any]],
        bytes_probe: dict[str, Any],
        run_status: str,
        blockers_total: int,
        input_context: dict[str, Any],
    ) -> dict[str, Any]:
        container_counts: dict[str, int] = {}
        documents = []
        for file_ref in file_refs:
            container = self._container_format(file_ref["extension"], file_ref["mime_type"])
            container_counts[container] = container_counts.get(container, 0) + 1
            documents.append(
                {
                    "document_id": self._document_id(file_ref),
                    "container_format": container,
                    "size_bytes": file_ref.get("size_bytes"),
                    "classification": "unknown_or_needs_review",
                    "can_be_source_evidence": "conditional",
                    "declaration_relevance": "source_fact",
                }
            )

        return {
            "schema_version": SAFE_REPORT_SCHEMA,
            "run_status": run_status,
            "trigger_type": "action_stub",
            "summary_counts": {
                "files_total": len(file_refs),
                "container_counts": container_counts,
                "blockers_total": blockers_total,
            },
            "file_ref_visibility": "visible" if file_refs else "not_visible",
            "input_context": input_context,
            "original_bytes_access": bytes_probe,
            "documents": documents,
            "case_groups": [
                {
                    "case_group_id": "case_group_synthetic_001",
                    "readiness": "needs_review",
                    "recommended_for_next_proof": True,
                }
            ],
            "next_step": "Select case_group_synthetic_001",
            "safety_statement": SAFETY_STATEMENT,
        }

    def _response(self, report: dict[str, Any]) -> dict[str, Any]:
        return {
            "content": self._format_chat_content(report),
            "broker_reports_gate1_report": report,
        }

    def _format_chat_content(self, report: dict[str, Any]) -> str:
        return (
            "Gate 1 normalization stub report\n\n"
            "```json\n"
            f"{json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)}\n"
            "```\n\n"
            "Next step: Select case_group_synthetic_001"
        )

    def _document_id(self, file_ref: dict[str, Any]) -> str:
        material = "|".join(
            [
                str(file_ref.get("file_id") or ""),
                str(file_ref.get("extension") or ""),
                str(file_ref.get("mime_type") or ""),
            ]
        )
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
        return f"doc_synthetic_{digest}"

    def _container_format(self, extension: str, mime_type: str) -> str:
        ext = extension.lower().lstrip(".")
        mime = mime_type.lower()
        if ext == "pdf" or mime == "application/pdf":
            return "pdf"
        if ext == "xlsx" or "spreadsheetml.sheet" in mime:
            return "xlsx"
        if ext == "xls":
            return "xls"
        if ext == "csv" or mime == "text/csv":
            return "csv"
        if ext == "txt" or mime.startswith("text/plain"):
            return "txt"
        if ext == "docx" or "wordprocessingml.document" in mime:
            return "docx"
        if ext in {"png", "jpg", "jpeg", "webp", "tif", "tiff"} or mime.startswith("image/"):
            return "image"
        if ext == "zip" or mime in {"application/zip", "application/x-zip-compressed"}:
            return "zip"
        return "unknown"

    def _extension(self, filename: Any, mime_type: str) -> str:
        suffix = Path(str(filename or "")).suffix.lower()
        if suffix:
            return suffix.lstrip(".")
        mime = str(mime_type or "").lower()
        if mime == "text/csv":
            return "csv"
        if mime.startswith("text/plain"):
            return "txt"
        if mime == "application/pdf":
            return "pdf"
        if "spreadsheetml.sheet" in mime:
            return "xlsx"
        return ""

    def _optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            result = int(value)
        except (TypeError, ValueError):
            return None
        return result if result >= 0 else None
