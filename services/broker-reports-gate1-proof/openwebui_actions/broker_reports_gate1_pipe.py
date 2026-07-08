"""
title: Broker Reports Gate 1 Pipe Backend Normalizer
author: Alpha Soft
version: 0.4.0-backend-normalizer
required_open_webui_version: 0.9.6
requirements: pydantic
"""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    BytesUnavailable,
    FileInput,
    Gate1Normalizer,
    NORMALIZER_VERSION,
    SAFE_REPORT_SCHEMA,
    SAFETY_STATEMENT,
    RetentionPolicyError,
    build_retention_policy,
    persist_gate1_result,
    render_chat_content,
)
from broker_reports_gate1.detectors import extension_from_name


class Pipe:
    """OpenWebUI adapter: file refs -> backend Gate 1 normalizer -> safe report."""

    class Valves(BaseModel):
        require_trigger_phrase: bool = Field(default=False)
        trigger_phrases: str = Field(
            default=(
                "gate1,gate 1,normalization,normalize,"
                "\u043d\u043e\u0440\u043c\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f,"
                "\u043d\u043e\u0440\u043c\u0430\u043b\u0438\u0437\u0443\u0439"
            )
        )
        upload_root: str = Field(default="/app/backend/data/uploads")
        allow_upload_path_access: bool = Field(default=True)
        artifact_store_path: str = Field(default="/app/backend/data/broker_reports_gate1/artifacts.sqlite3")
        artifact_payload_root: str = Field(default="/app/backend/data/broker_reports_gate1/payloads")
        artifact_retention_mode: str = Field(default="api_smoke")
        artifact_retention_ttl_seconds: int = Field(default=24 * 60 * 60)
        artifact_retention_explicit: bool = Field(default=True)
        live_smoke_trigger_phrases: str = Field(
            default="artifactstore retention smoke,gate1 artifactstore smoke"
        )

    def __init__(self) -> None:
        self.valves = self.Valves()
        self._normalizer = Gate1Normalizer()
        self.last_safe_report: dict | None = None
        self.last_artifact_manifest: dict | None = None

    async def pipe(
        self,
        body: dict,
        __user__=None,
        __metadata__=None,
        __files__=None,
        __messages__=None,
        __event_emitter__=None,
        **kwargs,
    ) -> str:
        await self._emit(__event_emitter__, "Checking uploaded file refs...", done=False)
        safe_body = body if isinstance(body, dict) else {}
        safe_metadata = __metadata__ if isinstance(__metadata__, dict) else {}
        messages_arg = __messages__ or kwargs.get("__messages__")
        files_arg = __files__ or kwargs.get("__files__")

        if self.valves.require_trigger_phrase and not self._has_trigger_phrase(safe_body, messages_arg):
            await self._emit(__event_emitter__, "Gate 1 trigger phrase was not found.", done=True)
            return (
                "Gate 1 normalization is available. Attach documents and send "
                "`Gate 1 normalization` in the same message."
            )

        file_refs = self._collect_file_refs(safe_body, safe_metadata, files_arg, messages_arg)
        input_context = self._safe_input_context(safe_body, safe_metadata, files_arg, messages_arg)
        file_inputs = [self._to_file_input(file_ref) for file_ref in file_refs]
        result = self._normalizer.normalize(
            file_inputs,
            entrypoint="broker_reports_gate1_pipe",
            trigger_type="pipe_backend_normalizer",
            input_context={
                **input_context,
                "normalizer_version": NORMALIZER_VERSION,
            },
            extra_private_markers=self._private_markers(file_refs),
        )
        artifact_context = self._artifact_context(
            user=__user__,
            metadata=safe_metadata,
            body=safe_body,
            kwargs=kwargs,
            normalization_run_id=result.package["normalization_run"]["run_id"],
        )
        retention_policy = build_retention_policy(
            mode=self.valves.artifact_retention_mode,
            explicit=self.valves.artifact_retention_explicit,
            ttl_seconds=self.valves.artifact_retention_ttl_seconds,
        )
        artifact_store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=Path(self.valves.artifact_store_path),
                payload_root=Path(self.valves.artifact_payload_root),
            )
        ).create()
        artifact_manifest = persist_gate1_result(
            store=artifact_store,
            result=result,
            context=artifact_context,
            retention_policy=retention_policy,
            source_file_refs=self._source_file_refs(file_refs),
        )
        self.last_safe_report = result.safe_report
        self.last_artifact_manifest = artifact_manifest.to_dict()

        if not file_refs:
            await self._emit(__event_emitter__, "No uploaded file refs were visible.", done=True)
        else:
            await self._emit(__event_emitter__, "Gate 1 artifacts persisted and compact report ready.", done=True)
        chat_content = render_chat_content(result.safe_report)
        if self._live_smoke_requested(safe_body, messages_arg):
            smoke_lines = self._run_live_artifactstore_smoke(
                store=artifact_store,
                result=result,
                context=artifact_context,
                retention_policy=retention_policy,
                manifest=artifact_manifest,
                file_inputs=file_inputs,
                file_refs=file_refs,
                chat_content=chat_content,
            )
            chat_content = "\n".join(
                [
                    chat_content,
                    "",
                    "Проверка ArtifactStore:",
                    *[f"- {line}" for line in smoke_lines],
                ]
            )
        return chat_content

    async def _emit(self, emitter, description: str, *, done: bool) -> None:
        if emitter is None:
            return
        await emitter(
            {
                "type": "status",
                "data": {"description": description, "done": done, "hidden": False},
            }
        )

    def _live_smoke_requested(self, body: dict, messages_arg: Any) -> bool:
        text_parts = []
        for message in self._message_iter(body.get("messages")):
            if isinstance(message, dict):
                text_parts.append(str(message.get("content") or ""))
        for message in self._message_iter(messages_arg):
            if isinstance(message, dict):
                text_parts.append(str(message.get("content") or ""))
        text = "\n".join(text_parts).lower()
        return any(
            phrase.strip().lower() in text
            for phrase in str(self.valves.live_smoke_trigger_phrases or "").split(",")
            if phrase.strip()
        )

    def _run_live_artifactstore_smoke(
        self,
        *,
        store,
        result,
        context: ArtifactAccessContext,
        retention_policy,
        manifest,
        file_inputs: list[FileInput],
        file_refs: list[dict[str, Any]],
        chat_content: str,
    ) -> list[str]:
        if not context.case_id:
            raise RuntimeError("case_context_missing_for_wrong_case_resolver_proof")
        records = store.list_by_run(context.normalization_run_id)
        type_counts = self._artifact_type_counts(records)
        required_types = {
            "normalization_run_v0",
            "document_inventory_v0",
            "technical_readability_profile_v0",
            "taxonomy_candidates_v0",
            "normalization_blockers_v0",
            "validation_result_v0",
            "chat_visible_normalization_report_v0",
            "private_normalized_text_slice_v0",
            "private_normalized_table_slice_v0",
            "gate2_handoff_v0",
            "source_file_ref_v0",
        }
        missing = sorted(required_types - set(type_counts))
        if missing:
            raise RuntimeError(f"artifact_type_missing:{missing[0]}")
        private_records = [record for record in records if record.visibility == "private_case"]
        if not private_records or not manifest.private_slice_refs:
            raise RuntimeError("private_slice_artifacts_missing")
        if not all(record.payload_ref and record.payload is None for record in private_records):
            raise RuntimeError("private_payload_storage_invalid")
        private_payload_paths = [
            self._payload_path(record.payload_ref)
            for record in private_records
            if record.payload_ref
        ]
        if not all(path.exists() for path in private_payload_paths):
            raise RuntimeError("private_payload_file_missing")

        private_markers = self._private_markers(file_refs)
        if any(marker and marker in chat_content for marker in private_markers):
            raise RuntimeError("chat_private_marker_leak")
        if "private_normalized_slices" in chat_content or "```json" in chat_content:
            raise RuntimeError("chat_full_json_or_private_slice_leak")
        if any(record.storage_backend == "openwebui_knowledge" for record in records):
            raise RuntimeError("knowledge_storage_forbidden_bypassed")
        if result.safe_report["safety_flags"]["customer_docs_loaded_to_knowledge"]:
            raise RuntimeError("customer_docs_loaded_to_knowledge_true")

        resolver = ArtifactResolver(store)
        resolver.resolve(manifest.safe_refs[0], context)
        resolver.resolve(manifest.private_slice_refs[0], context)
        self._assert_resolver_denies(
            resolver,
            manifest.safe_refs[0],
            ArtifactAccessContext(**{**context.__dict__, "user_id": "wrong-user"}),
            "artifact_access_denied",
        )
        self._assert_resolver_denies(
            resolver,
            manifest.safe_refs[0],
            ArtifactAccessContext(**{**context.__dict__, "case_id": "wrong-case"}),
            "artifact_access_denied",
        )

        handoff = resolver.resolve(manifest.gate2_handoff_ref, context)["payload"]
        if handoff.get("private_slice_refs") != manifest.private_slice_refs:
            raise RuntimeError("gate2_handoff_private_refs_missing")
        if "```json" in str(handoff) or any(marker and marker in str(handoff) for marker in private_markers):
            raise RuntimeError("gate2_handoff_private_marker_leak")

        probe_result = self._normalizer.normalize(
            file_inputs,
            entrypoint="broker_reports_gate1_live_retention_probe",
            trigger_type="live_retention_smoke_probe",
            input_context={"smoke_probe": "retention"},
            extra_private_markers=private_markers,
        )
        probe_context = ArtifactAccessContext(
            user_id=context.user_id,
            normalization_run_id=probe_result.package["normalization_run"]["run_id"],
            case_id=f"{context.case_id}-retention-probe",
            chat_id=context.chat_id,
            workspace_model_id=context.workspace_model_id,
            allow_private=True,
        )
        probe_manifest = persist_gate1_result(
            store=store,
            result=probe_result,
            context=probe_context,
            retention_policy=build_retention_policy(
                mode="expires_after_ttl",
                explicit=True,
                ttl_seconds=1,
            ),
            source_file_refs=self._source_file_refs(file_refs),
        )
        store.expire_artifacts(now=datetime.now(timezone.utc) + timedelta(seconds=2))
        self._assert_resolver_denies(
            resolver,
            probe_manifest.safe_refs[0],
            probe_context,
            "artifact_expired",
        )
        purge_private_ref = probe_manifest.private_slice_refs[0]
        purge_private_record = store.get_record_unchecked(purge_private_ref)
        if purge_private_record is None or not purge_private_record.payload_ref:
            raise RuntimeError("purge_probe_private_payload_missing")
        purge_payload_path = self._payload_path(purge_private_record.payload_ref)
        if not purge_payload_path.exists():
            raise RuntimeError("purge_probe_payload_file_missing")
        purged_ids = store.purge_run(probe_context.normalization_run_id)
        purged_private_record = store.get_record_unchecked(purge_private_ref)
        if not purged_ids or purge_payload_path.exists() or purged_private_record is None:
            raise RuntimeError("purge_probe_failed")
        if purged_private_record.storage_backend != "none_tombstone" or purged_private_record.payload_ref:
            raise RuntimeError("purge_tombstone_invalid")
        self._assert_resolver_denies(
            resolver,
            purge_private_ref,
            probe_context,
            "artifact_purged",
        )

        try:
            build_retention_policy(mode="customer_approved_test", explicit=False)
        except RetentionPolicyError as exc:
            if exc.code != "retention_policy_missing":
                raise
        else:
            raise RuntimeError("customer_approved_test_missing_policy_accepted")

        flags = result.safe_report["safety_flags"]
        if any(
            flags[key]
            for key in (
                "source_fact_extraction_performed",
                "tax_correctness_claimed",
                "declaration_generated",
                "xlsx_generated",
                "ocr_performed",
            )
        ):
            raise RuntimeError("forbidden_gate1_flag_true")

        return [
            "хранилище доступно для записи: да",
            (
                "retention policy: "
                f"mode={retention_policy.mode}, explicit={retention_policy.explicit}, "
                f"ttl_seconds={retention_policy.ttl_seconds}"
            ),
            "обязательные артефакты сохранены: " + ", ".join(sorted(required_types)),
            "private slices в chat: нет",
            "private slices в Knowledge: нет",
            "customer_docs_loaded_to_knowledge=false",
            "Gate 2 handoff использует opaque refs, не chat JSON",
            "resolver same-context: allow",
            "resolver denies wrong-user/wrong-case/expired/purged: ok",
            "purge удалил private payloads и оставил tombstones",
            "source facts/tax/declaration/xlsx/ocr flags=false",
        ]

    def _artifact_type_counts(self, records) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in records:
            counts[record.artifact_type] = counts.get(record.artifact_type, 0) + 1
        return counts

    def _assert_resolver_denies(
        self,
        resolver: ArtifactResolver,
        artifact_id: str,
        context: ArtifactAccessContext,
        expected_code: str,
    ) -> None:
        try:
            resolver.resolve(artifact_id, context)
        except ArtifactStoreError as exc:
            if exc.code == expected_code:
                return
            raise
        raise RuntimeError(f"resolver_expected_denial_missing:{expected_code}")

    def _payload_path(self, payload_ref: str) -> Path:
        return Path(self.valves.artifact_payload_root) / payload_ref

    def _has_trigger_phrase(self, body: dict, messages_arg: Any) -> bool:
        text_parts = []
        for message in self._message_iter(body.get("messages")):
            if isinstance(message, dict):
                text_parts.append(str(message.get("content") or ""))
        for message in self._message_iter(messages_arg):
            if isinstance(message, dict):
                text_parts.append(str(message.get("content") or ""))
        text = "\n".join(text_parts).lower()
        return any(
            phrase.strip().lower() in text
            for phrase in str(self.valves.trigger_phrases or "").split(",")
            if phrase.strip()
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
                    "filename": filename,
                    "extension": extension_from_name(filename, mime_type),
                    "mime_type": mime_type,
                    "size_bytes": self._optional_int(
                        file_obj.get("size") or file_obj.get("size_bytes")
                    ),
                    "_private_file_obj": file_obj,
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
        return suffix.split("/", 1)[0].split("?", 1)[0].strip()

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

    def _artifact_context(
        self,
        *,
        user: Any,
        metadata: dict,
        body: dict,
        kwargs: dict[str, Any],
        normalization_run_id: str,
    ) -> ArtifactAccessContext:
        user_id = self._user_id(user, metadata)
        chat_id = (
            metadata.get("chat_id")
            or kwargs.get("__chat_id__")
            or kwargs.get("chat_id")
            or body.get("chat_id")
            or metadata.get("session_id")
        )
        body_metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        case_id = metadata.get("case_id") or body_metadata.get("case_id") or body.get("case_id")
        workspace_model_id = metadata.get("model_id") or body.get("model") or body.get("model_id")
        return ArtifactAccessContext(
            user_id=user_id,
            normalization_run_id=normalization_run_id,
            case_id=str(case_id) if case_id else None,
            chat_id=str(chat_id) if chat_id else None,
            workspace_model_id=str(workspace_model_id) if workspace_model_id else None,
            allow_private=True,
        )

    def _user_id(self, user: Any, metadata: dict) -> str:
        if isinstance(user, dict):
            value = user.get("id") or user.get("user_id")
            if value:
                return str(value)
        nested = metadata.get("user") if isinstance(metadata.get("user"), dict) else {}
        value = metadata.get("user_id") or nested.get("id") or nested.get("user_id")
        if value:
            return str(value)
        return "openwebui_user_unavailable"

    def _source_file_refs(self, file_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for file_ref in file_refs:
            refs.append(
                {
                    "provider": "openwebui",
                    "openwebui_file_id": str(file_ref.get("file_id") or ""),
                    "content_type": str(file_ref.get("mime_type") or ""),
                    "size_bytes": self._optional_int(file_ref.get("size_bytes")),
                    "source_deleted": False,
                    "source_delete_observed_at": None,
                }
            )
        return refs

    def _to_file_input(self, file_ref: dict[str, Any]) -> FileInput:
        file_id = str(file_ref.get("file_id") or "")
        filename = str(file_ref.get("filename") or "")
        return FileInput(
            private_ref=file_id,
            original_filename_private=filename,
            mime_type=str(file_ref.get("mime_type") or ""),
            source_kind="openwebui_pipe",
            declared_size_bytes=self._optional_int(file_ref.get("size_bytes")),
            bytes_provider=lambda ref=file_ref: self._read_original_bytes(ref),
            provider_label="openwebui_pipe",
            privacy_markers=[],
        )

    def _read_original_bytes(self, file_ref: dict[str, Any]) -> bytes:
        file_obj = file_ref.get("_private_file_obj")
        if isinstance(file_obj, dict):
            inline = self._inline_bytes(file_obj)
            if inline is not None:
                return inline

        if not self.valves.allow_upload_path_access:
            raise BytesUnavailable("upload_path_access_disabled")

        candidate_result = self._upload_root_candidate(file_ref)
        if candidate_result.get("status") == "blocked":
            raise BytesUnavailable(str(candidate_result.get("reason") or "upload_candidate_blocked"))
        candidate = candidate_result.get("path")
        if isinstance(candidate, Path) and candidate.exists() and candidate.is_file():
            return candidate.read_bytes()
        raise BytesUnavailable("upload_file_not_found")

    def _inline_bytes(self, file_obj: dict[str, Any]) -> bytes | None:
        for key in ("content_bytes", "bytes", "data_bytes"):
            value = file_obj.get(key)
            if isinstance(value, bytes):
                return value
        for key in ("content_base64", "data_base64"):
            value = file_obj.get(key)
            if isinstance(value, str):
                try:
                    return base64.b64decode(value.encode("ascii"), validate=True)
                except (binascii.Error, UnicodeEncodeError):
                    return None
        for key in ("content", "data"):
            value = file_obj.get(key)
            if isinstance(value, str):
                return value.encode("utf-8")
        return None

    def _upload_root_candidate(self, file_ref: dict[str, Any]) -> dict[str, Any]:
        upload_root = Path(self.valves.upload_root).resolve()
        file_id = str(file_ref.get("file_id") or "")
        filename = str(file_ref.get("filename") or "")
        if self._has_path_separator(file_id) or self._has_path_separator(filename):
            return {"status": "blocked", "reason": "upload_path_escape_detected"}
        candidate = (upload_root / f"{file_id}_{filename}").resolve()
        if upload_root not in candidate.parents and candidate != upload_root:
            return {"status": "blocked", "reason": "upload_path_escape_detected"}
        return {"status": "candidate", "path": candidate}

    def _has_path_separator(self, value: str) -> bool:
        return "/" in value or "\\" in value or Path(value).name != value

    def _private_markers(self, file_refs: list[dict[str, Any]]) -> list[str]:
        markers: list[str] = []
        for file_ref in file_refs:
            markers.extend(
                [
                    str(file_ref.get("file_id") or ""),
                    str(file_ref.get("filename") or ""),
                ]
            )
            file_obj = file_ref.get("_private_file_obj")
            if isinstance(file_obj, dict):
                for key in ("content", "data"):
                    value = file_obj.get(key)
                    if isinstance(value, str):
                        markers.append(value)
                for key in ("content_bytes", "bytes", "data_bytes"):
                    value = file_obj.get(key)
                    if isinstance(value, bytes):
                        try:
                            markers.append(value.decode("utf-8"))
                        except UnicodeDecodeError:
                            pass
        return [marker for marker in markers if marker]

    def _optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            result = int(value)
        except (TypeError, ValueError):
            return None
        return result if result >= 0 else None
