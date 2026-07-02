from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from stage2_stt.config import PromptCatalogMode, SttConfig
from stage2_stt.contracts import PostProcessingTemplateV1, PromptCatalogUserContextV1


FACTORY_REQUIRED = "PromptCatalogFactory.create is the only production prompt catalog entrypoint"
FORBIDDEN = "Route handlers must not read OpenWebUI prompt tables directly"

STT_TEMPLATE_TAG = "stage2-stt-v2"
POST_PROCESSING_TAG = "stt-post-processing"


class PromptCatalogError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ResolvedPromptTemplate:
    template: PostProcessingTemplateV1
    prompt_body: str


class PromptCatalogAdapter(Protocol):
    def list_templates(
        self,
        user_context: PromptCatalogUserContextV1,
    ) -> list[PostProcessingTemplateV1]:
        ...

    def get_template(
        self,
        template_id: str,
        user_context: PromptCatalogUserContextV1,
    ) -> ResolvedPromptTemplate:
        ...

    def resolve_command(
        self,
        command: str,
        user_context: PromptCatalogUserContextV1,
    ) -> ResolvedPromptTemplate:
        ...


class PromptCatalogFactory:
    def __init__(self, config: SttConfig) -> None:
        self.config = config

    def create(self) -> PromptCatalogAdapter:
        if self.config.prompt_catalog_mode is PromptCatalogMode.OPENWEBUI_SQLITE:
            if not self.config.openwebui_prompt_db_path:
                raise PromptCatalogError(
                    "prompt_catalog_unavailable",
                    "OpenWebUI prompt DB path is not configured",
                )
            return OpenWebUISqlitePromptCatalogAdapter(
                Path(self.config.openwebui_prompt_db_path)
            )
        return DisabledPromptCatalogAdapter()


class DisabledPromptCatalogAdapter:
    def list_templates(
        self,
        user_context: PromptCatalogUserContextV1,
    ) -> list[PostProcessingTemplateV1]:
        raise PromptCatalogError("prompt_catalog_unavailable", "Prompt catalog is disabled")

    def get_template(
        self,
        template_id: str,
        user_context: PromptCatalogUserContextV1,
    ) -> ResolvedPromptTemplate:
        raise PromptCatalogError("prompt_catalog_unavailable", "Prompt catalog is disabled")

    def resolve_command(
        self,
        command: str,
        user_context: PromptCatalogUserContextV1,
    ) -> ResolvedPromptTemplate:
        raise PromptCatalogError("prompt_catalog_unavailable", "Prompt catalog is disabled")


class OpenWebUISqlitePromptCatalogAdapter:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def list_templates(
        self,
        user_context: PromptCatalogUserContextV1,
    ) -> list[PostProcessingTemplateV1]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, command, user_id, name, content, data, meta, tags, version_id
                FROM prompt
                WHERE is_active = 1
                ORDER BY updated_at DESC
                """
            ).fetchall()
            return [
                self._row_to_resolved(row, user_context, conn).template
                for row in rows
                if self._is_post_processing_prompt(row)
                and self._has_read_access(row, user_context, conn)
            ]

    def get_template(
        self,
        template_id: str,
        user_context: PromptCatalogUserContextV1,
    ) -> ResolvedPromptTemplate:
        normalized_id = str(template_id or "").strip()
        if not normalized_id:
            raise PromptCatalogError("prompt_not_found", "Prompt template id is empty")
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, command, user_id, name, content, data, meta, tags, version_id
                FROM prompt
                WHERE is_active = 1
                """
            ).fetchall()
            for row in rows:
                if not self._is_post_processing_prompt(row):
                    continue
                if self._template_id(row) != normalized_id:
                    continue
                if not self._has_read_access(row, user_context, conn):
                    raise PromptCatalogError(
                        "prompt_access_denied",
                        "Prompt template is not readable for the user context",
                    )
                return self._row_to_resolved(row, user_context, conn)
        raise PromptCatalogError("prompt_not_found", "Prompt template was not found")

    def resolve_command(
        self,
        command: str,
        user_context: PromptCatalogUserContextV1,
    ) -> ResolvedPromptTemplate:
        normalized_command = str(command or "").strip()
        if not normalized_command:
            raise PromptCatalogError("prompt_not_found", "Prompt command is empty")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, command, user_id, name, content, data, meta, tags, version_id
                FROM prompt
                WHERE is_active = 1 AND command = ?
                """,
                (normalized_command,),
            ).fetchone()
            if row is None or not self._is_post_processing_prompt(row):
                raise PromptCatalogError("prompt_not_found", "Prompt command was not found")
            if not self._has_read_access(row, user_context, conn):
                raise PromptCatalogError(
                    "prompt_access_denied",
                    "Prompt command is not readable for the user context",
                )
            return self._row_to_resolved(row, user_context, conn)

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise PromptCatalogError(
                "prompt_catalog_unavailable",
                "OpenWebUI prompt DB file is not available",
            )
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _is_post_processing_prompt(self, row: sqlite3.Row) -> bool:
        tags = _json_list(row["tags"])
        meta = _json_dict(row["meta"])
        return (
            STT_TEMPLATE_TAG in tags
            and POST_PROCESSING_TAG in tags
            and meta.get("template_kind") == "post_processing"
            and bool(self._template_id(row))
        )

    def _template_id(self, row: sqlite3.Row) -> str:
        meta = _json_dict(row["meta"])
        value = meta.get("template_id") or meta.get("stage2_template_id")
        return str(value or "").strip()

    def _row_to_resolved(
        self,
        row: sqlite3.Row,
        user_context: PromptCatalogUserContextV1,
        conn: sqlite3.Connection,
    ) -> ResolvedPromptTemplate:
        meta = _json_dict(row["meta"])
        tags = _json_list(row["tags"])
        body = str(row["content"] or "")
        template = PostProcessingTemplateV1(
            template_id=self._template_id(row),
            command=str(row["command"] or ""),
            label=str(row["name"] or row["command"] or self._template_id(row)),
            openwebui_prompt_id=str(row["id"]),
            prompt_version=row["version_id"],
            prompt_body_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
            tags=tags,
            requires_speakers=bool(meta.get("requires_speakers", False)),
            chunkable=bool(meta.get("chunkable", False)),
            access_grants=self._safe_access_projection(row, conn),
        )
        return ResolvedPromptTemplate(template=template, prompt_body=body)

    def _has_read_access(
        self,
        row: sqlite3.Row,
        user_context: PromptCatalogUserContextV1,
        conn: sqlite3.Connection,
    ) -> bool:
        user_role = str(user_context.user_role or "").lower()
        user_id = str(user_context.user_id or "")
        user_groups = {str(group) for group in user_context.user_groups if group}
        if user_role == "admin":
            return True
        if user_id and user_id == row["user_id"]:
            return True
        grants = conn.execute(
            """
            SELECT principal_type, principal_id, permission
            FROM access_grant
            WHERE resource_type = 'prompt'
              AND resource_id = ?
              AND permission = 'read'
            """,
            (row["id"],),
        ).fetchall()
        for grant in grants:
            principal_type = grant["principal_type"]
            principal_id = grant["principal_id"]
            if principal_type == "user" and principal_id == "*":
                return True
            if user_id and principal_type == "user" and principal_id == user_id:
                return True
            if principal_type == "group" and principal_id in user_groups:
                return True
        return False

    def _safe_access_projection(
        self,
        row: sqlite3.Row,
        conn: sqlite3.Connection,
    ) -> list[str]:
        grants = conn.execute(
            """
            SELECT principal_type, principal_id, permission
            FROM access_grant
            WHERE resource_type = 'prompt'
              AND resource_id = ?
              AND permission = 'read'
            ORDER BY principal_type, principal_id, permission
            """,
            (row["id"],),
        ).fetchall()
        projected = ["owner"]
        for grant in grants:
            principal_type = grant["principal_type"]
            principal_id = grant["principal_id"]
            if principal_type == "user" and principal_id == "*":
                projected.append("user:*:read")
            elif principal_type == "group":
                projected.append(f"group:{principal_id}:read")
            elif principal_type == "user":
                projected.append("user:<specific>:read")
        return list(dict.fromkeys(projected))


def _json_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value) -> list[str]:
    if isinstance(value, list):
        parsed = value
    elif not value:
        parsed = []
    else:
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            parsed = []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item]
