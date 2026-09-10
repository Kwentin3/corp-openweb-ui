"""Version-pinned native Prompt adapter for physical table continuation.

OpenWebUI owns the Prompt, its revision history and the caller's read grant.
This module only turns that native state into the small typed execution object
used by the PDF Document AI boundary.  It does not own Mistral transport,
Canonical data, or financial interpretation.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .pdf_table_continuation_annotation_contract import (
    INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_ID,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_COMMAND,
    PROMPT_CONTRACT_ID,
    PROMPT_REQUIRED_TAG,
    PROMPT_SNAPSHOT_SCHEMA_VERSION,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND,
    PdfTableContinuationAnnotationExecution,
    _execution_from_native_prompt,
    pdf_table_continuation_annotation_content_sha256,
    pdf_table_continuation_annotation_prompt_hash,
    validate_pdf_table_continuation_annotation_prompt_snapshot,
)
from .ordinary_trade_mapping_prompt import (
    OrdinaryTradeMappingPromptConfig,
    OrdinaryTradeMappingPromptError,
    OrdinaryTradeMappingPromptUserContext,
    OpenWebUIServerOrdinaryTradeMappingPromptResolver,
)


FACTORY_REQUIRED = (
    "PdfTableContinuationAnnotationPromptResolverFactory.create_async is the "
    "only production PDF table-continuation Prompt resolver entrypoint"
)
FORBIDDEN = (
    "PDF Document AI, normalizer and table-continuation sidecar must not read "
    "OpenWebUI Prompt, prompt_history or access_grant owners directly"
)

# The PDF bytes and the native response schema are supplied by the Mistral OCR
# request.  The managed Prompt is an instruction, not a template expanded with
# private document content, so it deliberately has no textual placeholder.


@dataclass(frozen=True)
class PdfTableContinuationAnnotationManagedPrompt:
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
        """Return an execution receipt.  The managed Prompt body stays private."""
        return {
            "schema_version": PROMPT_SNAPSHOT_SCHEMA_VERSION,
            "prompt_ref": self.prompt_ref,
            "prompt_command": self.command,
            "prompt_version": self.version,
            "prompt_hash": self.hash,
            "prompt_content_sha256": (
                pdf_table_continuation_annotation_content_sha256(self.content)
            ),
            "prompt_source": self.source,
            "prompt_contract_id": self.prompt_contract_id,
            "template_id": self.template_id,
            "template_kind": self.template_kind,
            "input_schema_version": self.input_schema_version,
            "output_schema_id": self.output_schema_id,
            "output_schema_version": self.output_schema_version,
            # This receipt is persisted with private source evidence.  It is
            # deliberately a sealed contract, not an echo of mutable native
            # Prompt presentation metadata or arbitrary tags.
            "tags": [PROMPT_REQUIRED_TAG],
            "safe_metadata": {
                "annotation_domain": "physical_table_continuation",
            },
        }


def execution_from_managed_prompt(
    prompt: PdfTableContinuationAnnotationManagedPrompt,
) -> PdfTableContinuationAnnotationExecution:
    """Issue the sealed execution value after native resolver access checks."""

    if type(prompt) is not PdfTableContinuationAnnotationManagedPrompt:
        raise OrdinaryTradeMappingPromptError(
            "pdf_table_continuation_annotation_execution_invalid",
            "PDF table-continuation managed Prompt is required",
        )
    try:
        return _execution_from_native_prompt(
            content=prompt.content,
            prompt_snapshot=prompt.snapshot(),
        )
    except ValueError as exc:
        raise OrdinaryTradeMappingPromptError(
            "pdf_table_continuation_annotation_execution_invalid",
            "PDF table-continuation managed Prompt receipt is invalid",
        ) from exc


@dataclass(frozen=True)
class PdfTableContinuationAnnotationPromptConfig:
    """Release pin and native selector; Prompt body is never configuration."""

    source: str = "disabled"
    db_path: Path | None = None
    prompt_id: str | None = None
    command: str | None = PROMPT_COMMAND
    release_prompt_version: str | None = None
    release_prompt_hash: str | None = None

    def native_config(self) -> OrdinaryTradeMappingPromptConfig:
        return OrdinaryTradeMappingPromptConfig(
            source=self.source,
            db_path=self.db_path,
            prompt_id=self.prompt_id,
            command=self.command,
            required_command=PROMPT_COMMAND,
            required_template_id=PROMPT_TEMPLATE_ID,
            required_template_kind=PROMPT_TEMPLATE_KIND,
            required_prompt_contract_id=PROMPT_CONTRACT_ID,
            required_input_schema_version=INPUT_SCHEMA_VERSION,
            required_output_schema_id=OUTPUT_SCHEMA_ID,
            required_output_schema_version=OUTPUT_SCHEMA_VERSION,
            required_tag=PROMPT_REQUIRED_TAG,
            # This adapter has no document-text placeholder.  Its resolver
            # overrides the generic template-placeholder check below.
            required_placeholder="",
            release_prompt_version=self.release_prompt_version,
            release_prompt_hash=self.release_prompt_hash,
        )


class PdfTableContinuationAnnotationPromptResolver(Protocol):
    async def resolve(
        self, user_context: OrdinaryTradeMappingPromptUserContext
    ) -> PdfTableContinuationAnnotationManagedPrompt: ...


class _PdfTableContinuationAnnotationPromptMixin:
    """Contract representation layered on the shared native owner reader."""

    def _matches_contract(self, row: Any) -> bool:
        meta = _json_dict(row["meta"] if not isinstance(row, dict) else row.get("meta"))
        tags = _json_list(row["tags"] if not isinstance(row, dict) else row.get("tags"))
        command = row["command"] if not isinstance(row, dict) else row.get("command")
        content = row["content"] if not isinstance(row, dict) else row.get("content")
        return (
            str(command or "") == self.config.required_command
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
            and bool(str(content or "").strip())
            and str(
                meta.get("annotation_domain") or "physical_table_continuation"
            )
            == "physical_table_continuation"
        )

    def _snapshot_to_prompt(
        self, row: Any, snapshot: dict[str, Any], *, version: str
    ) -> PdfTableContinuationAnnotationManagedPrompt:
        content = str(snapshot.get("content") or "")
        meta = _json_dict(snapshot.get("meta"))
        tags = tuple(_json_list(snapshot.get("tags")))
        row_value = row["id"] if not isinstance(row, dict) else row.get("id")
        row_name = row["name"] if not isinstance(row, dict) else row.get("name")
        return PdfTableContinuationAnnotationManagedPrompt(
            prompt_ref=str(row_value or ""),
            command=str(snapshot.get("command") or "") or None,
            version=version,
            content=content,
            hash=pdf_table_continuation_annotation_prompt_hash(content),
            source="openwebui_prompt_history",
            template_id=str(meta["template_id"]),
            template_kind=str(meta["template_kind"]),
            prompt_contract_id=str(meta["prompt_contract_id"]),
            input_schema_version=str(meta["input_contract"]),
            output_schema_id=str(meta["output_schema_id"]),
            output_schema_version=str(meta["output_schema_version"]),
            tags=tags,
            safe_metadata={
                "name": str(snapshot.get("name") or row_name or ""),
                "annotation_domain": str(
                    meta.get("annotation_domain") or "physical_table_continuation"
                ),
            },
        )


class OpenWebUIServerPdfTableContinuationAnnotationPromptResolver(
    _PdfTableContinuationAnnotationPromptMixin,
    OpenWebUIServerOrdinaryTradeMappingPromptResolver,
):
    """Native in-process resolver; no SQLite, HTTP, or fallback reader."""


class DisabledPdfTableContinuationAnnotationPromptResolver:
    async def resolve(
        self, user_context: OrdinaryTradeMappingPromptUserContext
    ) -> PdfTableContinuationAnnotationManagedPrompt:
        raise OrdinaryTradeMappingPromptError(
            "pdf_table_continuation_annotation_prompt_disabled",
            "PDF table-continuation annotation Prompt resolver is disabled",
        )


class StaticPdfTableContinuationAnnotationPromptResolver:
    """Hermetic test seam; it intentionally does not emulate Workspace state."""

    def __init__(self, prompt: PdfTableContinuationAnnotationManagedPrompt) -> None:
        self.prompt = prompt

    async def resolve(
        self, user_context: OrdinaryTradeMappingPromptUserContext
    ) -> PdfTableContinuationAnnotationManagedPrompt:
        if not str(user_context.user_id or "").strip():
            raise OrdinaryTradeMappingPromptError(
                "pdf_table_continuation_annotation_prompt_access_denied",
                "Authenticated user is required",
            )
        return self.prompt


class PdfTableContinuationAnnotationPromptResolverFactory:
    def __init__(self, config: PdfTableContinuationAnnotationPromptConfig) -> None:
        self.config = config

    def create_async(self) -> PdfTableContinuationAnnotationPromptResolver:
        if self.config.source == "disabled":
            return DisabledPdfTableContinuationAnnotationPromptResolver()
        if self.config.source != "openwebui_server":
            raise OrdinaryTradeMappingPromptError(
                "pdf_table_continuation_annotation_prompt_unavailable",
                "PDF table-continuation annotation Prompt source is unavailable",
            )
        _validate_release_pin(
            version=self.config.release_prompt_version,
            prompt_hash=self.config.release_prompt_hash,
        )
        return OpenWebUIServerPdfTableContinuationAnnotationPromptResolver(
            self.config.native_config()
        )


def _validate_release_pin(*, version: str | None, prompt_hash: str | None) -> None:
    normalized_version = str(version or "").strip()
    normalized_hash = str(prompt_hash or "").strip()
    if (
        not normalized_version
        or len(normalized_version) > 200
        or not re.fullmatch(r"[0-9a-f]{64}", normalized_hash)
    ):
        raise OrdinaryTradeMappingPromptError(
            "pdf_table_continuation_annotation_prompt_release_pin_invalid",
            "PDF table-continuation annotation release Prompt version and hash are required",
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
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []
    return []


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "INPUT_SCHEMA_VERSION",
    "OUTPUT_SCHEMA_ID",
    "OUTPUT_SCHEMA_VERSION",
    "PROMPT_COMMAND",
    "PROMPT_CONTRACT_ID",
    "PROMPT_REQUIRED_TAG",
    "PROMPT_SNAPSHOT_SCHEMA_VERSION",
    "PROMPT_TEMPLATE_ID",
    "PROMPT_TEMPLATE_KIND",
    "DisabledPdfTableContinuationAnnotationPromptResolver",
    "OpenWebUIServerPdfTableContinuationAnnotationPromptResolver",
    "PdfTableContinuationAnnotationExecution",
    "PdfTableContinuationAnnotationManagedPrompt",
    "PdfTableContinuationAnnotationPromptConfig",
    "PdfTableContinuationAnnotationPromptResolver",
    "PdfTableContinuationAnnotationPromptResolverFactory",
    "StaticPdfTableContinuationAnnotationPromptResolver",
    "execution_from_managed_prompt",
    "pdf_table_continuation_annotation_prompt_hash",
    "validate_pdf_table_continuation_annotation_prompt_snapshot",
]
