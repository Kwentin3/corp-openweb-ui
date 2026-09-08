"""Read the version-pinned OpenWebUI Prompt for ordinary-trade mapping.

This module is a representation adapter only.  OpenWebUI owns Prompt content,
history and access grants; ordinary-trade mapping consumes the typed snapshot.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .ordinary_trade_semantic_mapping import MAPPING_RESPONSE_SCHEMA_VERSION


FACTORY_REQUIRED = (
    "OrdinaryTradeMappingPromptResolverFactory.create is the only production "
    "ordinary-trade mapping prompt resolver entrypoint"
)
FORBIDDEN = (
    "Ordinary-trade mapping runtime, Pipe and qualification runner must not read "
    "OpenWebUI prompt or prompt_history tables directly"
)

PROMPT_CONTRACT_ID = "broker_reports_ordinary_trade_mapping_prompt_v1"
PROMPT_TEMPLATE_ID = "broker_reports.ordinary_trade_semantic_mapping.v1"
PROMPT_TEMPLATE_KIND = "broker_reports_ordinary_trade_semantic_mapping"
PROMPT_COMMAND = "broker_ordinary_trade_semantic_mapping_v1"
PROMPT_REQUIRED_TAG = "broker-reports-ordinary-trade-mapping"
INPUT_SCHEMA_VERSION = "broker_reports_ordinary_trade_mapping_case_v2"
# The mapping owner is the sole owner of this wire-schema identity.  The Prompt
# resolver consumes it so a native Workspace candidate cannot silently drift.
OUTPUT_SCHEMA_ID = MAPPING_RESPONSE_SCHEMA_VERSION
OUTPUT_SCHEMA_VERSION = OUTPUT_SCHEMA_ID
PROMPT_PLACEHOLDER = "{{ordinary_trade_mapping_case_json}}"
PROMPT_SNAPSHOT_SCHEMA_VERSION = "broker_reports_ordinary_trade_mapping_prompt_snapshot_v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OrdinaryTradeMappingPromptError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class OrdinaryTradeMappingPromptUserContext:
    user_id: str
    user_role: str = "user"
    user_groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class OrdinaryTradeMappingPromptConfig:
    source: str = "openwebui_sqlite"
    db_path: Path | None = None
    prompt_id: str | None = None
    command: str | None = PROMPT_COMMAND
    # Production keeps the sole released command. An isolated qualification
    # runner may opt into a separately named managed Prompt without changing
    # the production Prompt row or its active history version.
    required_command: str = PROMPT_COMMAND
    required_template_id: str = PROMPT_TEMPLATE_ID
    required_template_kind: str = PROMPT_TEMPLATE_KIND
    required_prompt_contract_id: str = PROMPT_CONTRACT_ID
    required_input_schema_version: str = INPUT_SCHEMA_VERSION
    required_output_schema_id: str = OUTPUT_SCHEMA_ID
    required_output_schema_version: str = OUTPUT_SCHEMA_VERSION
    required_tag: str = PROMPT_REQUIRED_TAG
    required_placeholder: str = PROMPT_PLACEHOLDER
    # These two values are release configuration, not Workspace metadata.
    # A syntactically valid Prompt revision is not implicitly approved for the
    # product route merely because it retains the same command and contract.
    release_prompt_version: str | None = None
    release_prompt_hash: str | None = None


@dataclass(frozen=True)
class OrdinaryTradeMappingManagedPrompt:
    prompt_ref: str
    command: str | None
    version: str
    content: str
    hash: str
    source: str
    template_id: str
    template_kind: str
    prompt_contract_id: str
    input_schema_version: str
    output_schema_id: str
    output_schema_version: str
    tags: tuple[str, ...]
    safe_metadata: dict[str, Any]

    def snapshot(self) -> dict[str, Any]:
        """Safe execution identity.  Prompt body is intentionally excluded."""
        return {
            "schema_version": PROMPT_SNAPSHOT_SCHEMA_VERSION,
            "prompt_ref": self.prompt_ref,
            "prompt_command": self.command,
            "prompt_version": self.version,
            "prompt_hash": self.hash,
            "prompt_source": self.source,
            "prompt_contract_id": self.prompt_contract_id,
            "template_id": self.template_id,
            "template_kind": self.template_kind,
            "input_schema_version": self.input_schema_version,
            "output_schema_id": self.output_schema_id,
            "output_schema_version": self.output_schema_version,
            "tags": list(self.tags),
            "safe_metadata": copy.deepcopy(self.safe_metadata),
        }


class OrdinaryTradeMappingPromptResolver(Protocol):
    def resolve(
        self, user_context: OrdinaryTradeMappingPromptUserContext
    ) -> OrdinaryTradeMappingManagedPrompt: ...


class AsyncOrdinaryTradeMappingPromptResolver(Protocol):
    async def resolve(
        self, user_context: OrdinaryTradeMappingPromptUserContext
    ) -> OrdinaryTradeMappingManagedPrompt: ...


class OrdinaryTradeMappingPromptResolverFactory:
    def __init__(self, config: OrdinaryTradeMappingPromptConfig) -> None:
        self.config = config

    def create(self) -> OrdinaryTradeMappingPromptResolver:
        if self.config.source == "openwebui_sqlite":
            if self.config.db_path is None:
                raise OrdinaryTradeMappingPromptError(
                    "ordinary_trade_mapping_prompt_unavailable",
                    "OpenWebUI prompt database path is not configured",
                )
            _validate_release_pin(
                version=self.config.release_prompt_version,
                prompt_hash=self.config.release_prompt_hash,
            )
            return OpenWebUISqliteOrdinaryTradeMappingPromptResolver(self.config)
        if self.config.source == "disabled":
            return DisabledOrdinaryTradeMappingPromptResolver()
        raise OrdinaryTradeMappingPromptError(
            "ordinary_trade_mapping_prompt_unavailable",
            "Unsupported ordinary-trade mapping prompt source",
        )

    def create_async(self) -> AsyncOrdinaryTradeMappingPromptResolver:
        """Return the native in-process resolver used by an OpenWebUI Function.

        This is deliberately a separate mode, rather than an async wrapper around
        the SQLite reader.  A running Function already has OpenWebUI's async
        database context and resource owners; opening the database again would
        create a parallel ownership path.
        """
        if self.config.source != "openwebui_server":
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_unavailable",
                "Async ordinary-trade mapping prompt source is unavailable",
            )
        _validate_release_pin(
            version=self.config.release_prompt_version,
            prompt_hash=self.config.release_prompt_hash,
        )
        return OpenWebUIServerOrdinaryTradeMappingPromptResolver(self.config)


class DisabledOrdinaryTradeMappingPromptResolver:
    def resolve(
        self, user_context: OrdinaryTradeMappingPromptUserContext
    ) -> OrdinaryTradeMappingManagedPrompt:
        raise OrdinaryTradeMappingPromptError(
            "ordinary_trade_mapping_prompt_disabled",
            "Ordinary-trade mapping prompt resolver is disabled",
        )


class StaticOrdinaryTradeMappingPromptResolver:
    """Hermetic-test boundary; it deliberately does not emulate Workspace state."""

    def __init__(self, prompt: OrdinaryTradeMappingManagedPrompt) -> None:
        self.prompt = prompt

    def resolve(
        self, user_context: OrdinaryTradeMappingPromptUserContext
    ) -> OrdinaryTradeMappingManagedPrompt:
        if not str(user_context.user_id or "").strip():
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_access_denied",
                "Authenticated user is required",
            )
        return self.prompt


class OpenWebUISqliteOrdinaryTradeMappingPromptResolver:
    def __init__(self, config: OrdinaryTradeMappingPromptConfig) -> None:
        self.config = config
        self.db_path = config.db_path

    def resolve(
        self, user_context: OrdinaryTradeMappingPromptUserContext
    ) -> OrdinaryTradeMappingManagedPrompt:
        if not str(user_context.user_id or "").strip():
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_access_denied",
                "Authenticated user is required",
            )
        conn = self._connect()
        try:
            row = self._find_prompt(conn)
            if row is None:
                raise OrdinaryTradeMappingPromptError(
                    "ordinary_trade_mapping_prompt_not_found",
                    "Ordinary-trade mapping Workspace Prompt was not found",
                )
            if not self._has_read_access(row, user_context, conn):
                raise OrdinaryTradeMappingPromptError(
                    "ordinary_trade_mapping_prompt_access_denied",
                    "Ordinary-trade mapping Workspace Prompt is not readable",
                )
            snapshot = self._version_snapshot(conn, row)
            self._require_current_row_matches_version(row, snapshot)
            prompt = self._row_to_prompt(row)
            self._require_release_pin(prompt)
            return prompt
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        if self.db_path is None or not self.db_path.exists():
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_unavailable",
                "OpenWebUI prompt database is unavailable",
            )
        try:
            conn = sqlite3.connect(
                f"file:{self.db_path.as_posix()}?mode=ro", uri=True
            )
        except sqlite3.Error as exc:
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_unavailable",
                "OpenWebUI prompt database is unavailable",
            ) from exc
        conn.row_factory = sqlite3.Row
        return conn

    def _find_prompt(self, conn: sqlite3.Connection) -> sqlite3.Row | None:
        try:
            if self.config.prompt_id:
                row = conn.execute(
                    """
                    SELECT id, command, user_id, name, content, data, meta, tags,
                           version_id, is_active
                    FROM prompt
                    WHERE is_active = 1 AND id = ?
                    """,
                    (self.config.prompt_id,),
                ).fetchone()
            elif self.config.command:
                row = conn.execute(
                    """
                    SELECT id, command, user_id, name, content, data, meta, tags,
                           version_id, is_active
                    FROM prompt
                    WHERE is_active = 1 AND command = ?
                    """,
                    (self.config.command,),
                ).fetchone()
            else:
                raise OrdinaryTradeMappingPromptError(
                    "ordinary_trade_mapping_prompt_not_found",
                    "Prompt id or command is required",
                )
        except sqlite3.Error as exc:
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_unavailable",
                "OpenWebUI prompt database schema is unavailable",
            ) from exc
        return row if row is not None and self._matches_contract(row) else None

    def _matches_contract(self, row: sqlite3.Row) -> bool:
        meta = _json_dict(row["meta"])
        tags = _json_list(row["tags"])
        content = str(row["content"] or "")
        return (
            str(row["command"] or "") == self.config.required_command
            and str(meta.get("template_id") or "") == self.config.required_template_id
            and str(meta.get("template_kind") or "")
            == self.config.required_template_kind
            and str(meta.get("prompt_contract_id") or "")
            == self.config.required_prompt_contract_id
            and str(meta.get("input_contract") or "")
            == self.config.required_input_schema_version
            and str(meta.get("output_schema_id") or "")
            == self.config.required_output_schema_id
            and str(meta.get("output_schema_version") or "")
            == self.config.required_output_schema_version
            and meta.get("structured_output_required") is True
            and self.config.required_tag in tags
            and bool(content.strip())
            and content.count(self.config.required_placeholder) == 1
        )

    def _version_snapshot(
        self, conn: sqlite3.Connection, row: sqlite3.Row
    ) -> dict[str, Any]:
        version_id = str(row["version_id"] or "").strip()
        if not version_id:
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_version_invalid",
                "Ordinary-trade mapping Workspace Prompt has no active version",
            )
        try:
            history = conn.execute(
                """
                SELECT snapshot FROM prompt_history
                WHERE id = ? AND prompt_id = ?
                """,
                (version_id, row["id"]),
            ).fetchone()
        except sqlite3.Error as exc:
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_version_invalid",
                "Ordinary-trade mapping Workspace Prompt history is unavailable",
            ) from exc
        snapshot = _json_dict(history["snapshot"]) if history is not None else {}
        if not snapshot:
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_version_invalid",
                "Ordinary-trade mapping Workspace Prompt active version is unavailable",
            )
        return snapshot

    def _require_current_row_matches_version(
        self, row: sqlite3.Row, snapshot: dict[str, Any]
    ) -> None:
        current = {
            "command": str(row["command"] or ""),
            "content": str(row["content"] or ""),
            "meta": _json_dict(row["meta"]),
            "tags": _json_list(row["tags"]),
        }
        versioned = {
            "command": str(snapshot.get("command") or ""),
            "content": str(snapshot.get("content") or ""),
            "meta": _json_dict(snapshot.get("meta")),
            "tags": _json_list(snapshot.get("tags")),
        }
        if current != versioned:
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_version_drift",
                "Ordinary-trade mapping Workspace Prompt differs from its active version",
            )

    def _row_to_prompt(self, row: sqlite3.Row) -> OrdinaryTradeMappingManagedPrompt:
        content = str(row["content"] or "")
        meta = _json_dict(row["meta"])
        tags = tuple(_json_list(row["tags"]))
        return OrdinaryTradeMappingManagedPrompt(
            prompt_ref=str(row["id"]),
            command=str(row["command"] or "") or None,
            version=str(row["version_id"]),
            content=content,
            hash=ordinary_trade_mapping_prompt_hash(content),
            source="openwebui_prompt_history",
            template_id=str(meta["template_id"]),
            template_kind=str(meta["template_kind"]),
            prompt_contract_id=str(meta["prompt_contract_id"]),
            input_schema_version=str(meta["input_contract"]),
            output_schema_id=str(meta["output_schema_id"]),
            output_schema_version=str(meta["output_schema_version"]),
            tags=tags,
            safe_metadata={
                "name": str(row["name"] or row["command"] or ""),
                "mapping_domain": str(meta.get("mapping_domain") or "ordinary_trade"),
            },
        )

    def _require_release_pin(self, prompt: OrdinaryTradeMappingManagedPrompt) -> None:
        if (
            prompt.version != self.config.release_prompt_version
            or prompt.hash != self.config.release_prompt_hash
        ):
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_release_pin_mismatch",
                "Ordinary-trade mapping Workspace Prompt differs from the release pin",
            )

    def _has_read_access(
        self,
        row: sqlite3.Row,
        user_context: OrdinaryTradeMappingPromptUserContext,
        conn: sqlite3.Connection,
    ) -> bool:
        role = str(user_context.user_role or "").lower()
        user_id = str(user_context.user_id or "")
        if role == "admin" or user_id == str(row["user_id"] or ""):
            return True
        try:
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
        except sqlite3.Error:
            return False
        granted_groups: set[str] = set()
        for grant in grants:
            principal_type = str(grant["principal_type"] or "")
            principal_id = str(grant["principal_id"] or "")
            if principal_type == "user" and principal_id in {"*", user_id}:
                return True
            if principal_type == "group" and principal_id:
                granted_groups.add(principal_id)
        if not granted_groups:
            return False
        try:
            membership_rows = conn.execute(
                "SELECT group_id FROM group_member WHERE user_id = ?",
                (user_id,),
            ).fetchall()
        except sqlite3.Error:
            return False
        return any(
            str(membership["group_id"] or "") in granted_groups
            for membership in membership_rows
        )


class OpenWebUIServerOrdinaryTradeMappingPromptResolver(
    OpenWebUISqliteOrdinaryTradeMappingPromptResolver
):
    """Resolve a release-pinned Prompt through native OpenWebUI owners only.

    The runtime Function calls this inside the OpenWebUI server process.  The
    dynamic import is intentional: source-only and hermetic tests do not ship
    OpenWebUI, while a Function without those in-process owners must fail closed
    instead of falling back to SQLite or HTTP.
    """

    async def resolve(
        self, user_context: OrdinaryTradeMappingPromptUserContext
    ) -> OrdinaryTradeMappingManagedPrompt:
        if not str(user_context.user_id or "").strip():
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_access_denied",
                "Authenticated user is required",
            )
        owners = self._native_owners()
        try:
            async with owners["get_async_db_context"]() as session:
                prompt_model = await self._native_prompt(
                    owners=owners, session=session
                )
                if prompt_model is None:
                    raise OrdinaryTradeMappingPromptError(
                        "ordinary_trade_mapping_prompt_not_found",
                        "Ordinary-trade mapping Workspace Prompt was not found",
                    )
                row = self._native_prompt_row(prompt_model)
                if not bool(row.get("is_active")) or not self._matches_contract(row):
                    raise OrdinaryTradeMappingPromptError(
                        "ordinary_trade_mapping_prompt_not_found",
                        "Ordinary-trade mapping Workspace Prompt was not found",
                    )
                if not await self._native_has_read_access(
                    owners=owners,
                    row=row,
                    user_context=user_context,
                    session=session,
                ):
                    raise OrdinaryTradeMappingPromptError(
                        "ordinary_trade_mapping_prompt_access_denied",
                        "Ordinary-trade mapping Workspace Prompt is not readable",
                    )
                snapshot = await self._native_version_snapshot(
                    owners=owners, row=row, session=session
                )
                self._require_current_row_matches_version(row, snapshot)
                prompt = self._row_to_prompt(row)
                self._require_release_pin(prompt)
                return prompt
        except OrdinaryTradeMappingPromptError:
            raise
        except Exception as exc:
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_unavailable",
                "OpenWebUI native Prompt owners are unavailable",
            ) from exc

    @staticmethod
    def _native_owners() -> dict[str, Any]:
        try:
            from open_webui.internal.db import get_async_db_context
            from open_webui.models.access_grants import AccessGrants
            from open_webui.models.prompt_history import PromptHistories
            from open_webui.models.prompts import Prompts
        except Exception as exc:
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_unavailable",
                "OpenWebUI native Prompt owners are unavailable",
            ) from exc
        return {
            "get_async_db_context": get_async_db_context,
            "prompts": Prompts,
            "prompt_histories": PromptHistories,
            "access_grants": AccessGrants,
        }

    async def _native_prompt(self, *, owners: dict[str, Any], session: Any) -> Any:
        if self.config.prompt_id:
            return await owners["prompts"].get_prompt_by_id(
                self.config.prompt_id, db=session
            )
        if self.config.command:
            return await owners["prompts"].get_prompt_by_command(
                self.config.command, db=session
            )
        raise OrdinaryTradeMappingPromptError(
            "ordinary_trade_mapping_prompt_not_found",
            "Prompt id or command is required",
        )

    @staticmethod
    def _native_prompt_row(prompt_model: Any) -> dict[str, Any]:
        if hasattr(prompt_model, "model_dump"):
            value = prompt_model.model_dump()
        elif isinstance(prompt_model, dict):
            value = prompt_model
        else:
            return {}
        return copy.deepcopy(value) if isinstance(value, dict) else {}

    async def _native_has_read_access(
        self,
        *,
        owners: dict[str, Any],
        row: dict[str, Any],
        user_context: OrdinaryTradeMappingPromptUserContext,
        session: Any,
    ) -> bool:
        role = str(user_context.user_role or "").lower()
        user_id = str(user_context.user_id or "")
        if role == "admin" or user_id == str(row.get("user_id") or ""):
            return True
        return bool(
            await owners["access_grants"].has_access(
                user_id,
                "prompt",
                str(row.get("id") or ""),
                permission="read",
                db=session,
            )
        )

    async def _native_version_snapshot(
        self, *, owners: dict[str, Any], row: dict[str, Any], session: Any
    ) -> dict[str, Any]:
        version_id = str(row.get("version_id") or "").strip()
        prompt_id = str(row.get("id") or "").strip()
        if not version_id or not prompt_id:
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_version_invalid",
                "Ordinary-trade mapping Workspace Prompt has no active version",
            )
        history = await owners["prompt_histories"].get_history_entry_by_id(
            version_id, db=session
        )
        history_prompt_id = str(getattr(history, "prompt_id", "") or "")
        snapshot = _json_dict(getattr(history, "snapshot", None))
        if history_prompt_id != prompt_id or not snapshot:
            raise OrdinaryTradeMappingPromptError(
                "ordinary_trade_mapping_prompt_version_invalid",
                "Ordinary-trade mapping Workspace Prompt active version is unavailable",
            )
        return snapshot


def ordinary_trade_mapping_prompt_hash(prompt_content: str) -> str:
    material = (
        prompt_content.replace("\r\n", "\n").strip()
        + "\nprompt_contract:"
        + PROMPT_CONTRACT_ID
        + "\ninput_schema:"
        + INPUT_SCHEMA_VERSION
        + "\noutput_schema_id:"
        + OUTPUT_SCHEMA_ID
        + "\noutput_schema_version:"
        + OUTPUT_SCHEMA_VERSION
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def validate_ordinary_trade_mapping_prompt_snapshot(value: Any) -> dict[str, Any]:
    """Validate a body-free resolver receipt before a mapping case retains it."""
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "prompt_ref",
        "prompt_command",
        "prompt_version",
        "prompt_hash",
        "prompt_source",
        "prompt_contract_id",
        "template_id",
        "template_kind",
        "input_schema_version",
        "output_schema_id",
        "output_schema_version",
        "tags",
        "safe_metadata",
    }:
        raise OrdinaryTradeMappingPromptError(
            "ordinary_trade_mapping_prompt_snapshot_invalid",
            "Ordinary-trade mapping prompt snapshot shape is invalid",
        )
    if (
        value.get("schema_version") != PROMPT_SNAPSHOT_SCHEMA_VERSION
        or not isinstance(value.get("prompt_ref"), str)
        or not value["prompt_ref"].strip()
        or value.get("prompt_command") not in {PROMPT_COMMAND, None}
        or not isinstance(value.get("prompt_version"), str)
        or not value["prompt_version"].strip()
        or not isinstance(value.get("prompt_hash"), str)
        or _SHA256.fullmatch(value["prompt_hash"]) is None
        or value.get("prompt_source") not in {"openwebui_prompt_history", "test"}
        or value.get("prompt_contract_id") != PROMPT_CONTRACT_ID
        or value.get("template_id") != PROMPT_TEMPLATE_ID
        or value.get("template_kind") != PROMPT_TEMPLATE_KIND
        or value.get("input_schema_version") != INPUT_SCHEMA_VERSION
        or value.get("output_schema_id") != OUTPUT_SCHEMA_ID
        or value.get("output_schema_version") != OUTPUT_SCHEMA_VERSION
        or not isinstance(value.get("tags"), list)
        or any(not isinstance(tag, str) for tag in value["tags"])
        or PROMPT_REQUIRED_TAG not in value["tags"]
        or not isinstance(value.get("safe_metadata"), dict)
        or set(value["safe_metadata"]) - {"name", "mapping_domain"}
    ):
        raise OrdinaryTradeMappingPromptError(
            "ordinary_trade_mapping_prompt_snapshot_invalid",
            "Ordinary-trade mapping prompt snapshot contract is invalid",
        )
    return copy.deepcopy(value)


def _validate_release_pin(*, version: str | None, prompt_hash: str | None) -> None:
    normalized_version = str(version or "").strip()
    normalized_hash = str(prompt_hash or "").strip()
    if (
        not normalized_version
        or len(normalized_version) > 200
        or _SHA256.fullmatch(normalized_hash) is None
    ):
        raise OrdinaryTradeMappingPromptError(
            "ordinary_trade_mapping_prompt_release_pin_invalid",
            "Ordinary-trade mapping release Prompt version and hash are required",
        )


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return copy.deepcopy(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return copy.deepcopy(parsed) if isinstance(parsed, dict) else {}
    return {}


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return [str(item) for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []
    return []


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "INPUT_SCHEMA_VERSION",
    "OUTPUT_SCHEMA_ID",
    "OUTPUT_SCHEMA_VERSION",
    "PROMPT_COMMAND",
    "PROMPT_CONTRACT_ID",
    "PROMPT_PLACEHOLDER",
    "PROMPT_REQUIRED_TAG",
    "PROMPT_SNAPSHOT_SCHEMA_VERSION",
    "PROMPT_TEMPLATE_ID",
    "PROMPT_TEMPLATE_KIND",
    "AsyncOrdinaryTradeMappingPromptResolver",
    "DisabledOrdinaryTradeMappingPromptResolver",
    "OpenWebUIServerOrdinaryTradeMappingPromptResolver",
    "OpenWebUISqliteOrdinaryTradeMappingPromptResolver",
    "OrdinaryTradeMappingManagedPrompt",
    "OrdinaryTradeMappingPromptConfig",
    "OrdinaryTradeMappingPromptError",
    "OrdinaryTradeMappingPromptResolver",
    "OrdinaryTradeMappingPromptResolverFactory",
    "OrdinaryTradeMappingPromptUserContext",
    "StaticOrdinaryTradeMappingPromptResolver",
    "ordinary_trade_mapping_prompt_hash",
    "validate_ordinary_trade_mapping_prompt_snapshot",
]
