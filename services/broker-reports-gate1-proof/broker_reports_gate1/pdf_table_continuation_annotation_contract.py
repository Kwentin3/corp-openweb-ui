"""Pure sealed contract for a native PDF table-continuation instruction.

This module has no OpenWebUI, configuration, provider or persistence access.
The native Prompt resolver is the only issuer of its execution value; PDF
normalization and private sidecar persistence consume that value by contract.
"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


PROMPT_CONTRACT_ID = "broker_reports_pdf_table_continuation_annotation_prompt_v3"
PROMPT_TEMPLATE_ID = "broker_reports.pdf_table_continuation_annotation.v3"
PROMPT_TEMPLATE_KIND = "broker_reports_pdf_table_continuation_annotation"
PROMPT_COMMAND = "broker_pdf_table_continuation_annotation_v3"
PROMPT_REQUIRED_TAG = "broker-reports-pdf-table-continuation"
INPUT_SCHEMA_VERSION = "broker_reports_pdf_document_annotation_input_v1"
OUTPUT_SCHEMA_ID = "mistral_ocr_table_continuation_annotation_v4"
OUTPUT_SCHEMA_VERSION = OUTPUT_SCHEMA_ID
PROMPT_SNAPSHOT_SCHEMA_VERSION = (
    "broker_reports_pdf_table_continuation_annotation_prompt_snapshot_v3"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_EXECUTION_ISSUER = object()


class PdfTableContinuationAnnotationContractError(ValueError):
    """Closed-contract failure before a provider call or sidecar write."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, init=False)
class PdfTableContinuationAnnotationExecution:
    """Immutable instruction plus a sealed, body-free native Prompt receipt."""

    content: str
    _prompt_snapshot: dict[str, Any] = field(repr=False)

    def __init__(
        self,
        *,
        content: str,
        prompt_snapshot: dict[str, Any],
        _issuer: object | None = None,
    ) -> None:
        if _issuer is not _EXECUTION_ISSUER:
            raise PdfTableContinuationAnnotationContractError(
                "pdf_table_continuation_annotation_execution_issuer_invalid"
            )
        if not isinstance(content, str) or not content.strip():
            raise PdfTableContinuationAnnotationContractError(
                "pdf_table_continuation_annotation_execution_invalid"
            )
        snapshot = validate_pdf_table_continuation_annotation_prompt_snapshot(
            prompt_snapshot
        )
        if (
            pdf_table_continuation_annotation_prompt_hash(content)
            != snapshot["prompt_hash"]
            or pdf_table_continuation_annotation_content_sha256(content)
            != snapshot["prompt_content_sha256"]
        ):
            raise PdfTableContinuationAnnotationContractError(
                "pdf_table_continuation_annotation_execution_invalid"
            )
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "_prompt_snapshot", snapshot)

    @property
    def prompt_snapshot(self) -> dict[str, Any]:
        """Return a copy so callers cannot mutate the sealed receipt."""

        return copy.deepcopy(self._prompt_snapshot)

    @property
    def content_sha256(self) -> str:
        """Exact body digest returned by the native OCR receipt."""

        return pdf_table_continuation_annotation_content_sha256(self.content)

    def validated_prompt_snapshot(self) -> dict[str, Any]:
        """Validate again at the irreversible provider boundary."""

        snapshot = validate_pdf_table_continuation_annotation_prompt_snapshot(
            self._prompt_snapshot
        )
        if (
            pdf_table_continuation_annotation_prompt_hash(self.content)
            != snapshot["prompt_hash"]
            or pdf_table_continuation_annotation_content_sha256(self.content)
            != snapshot["prompt_content_sha256"]
        ):
            raise PdfTableContinuationAnnotationContractError(
                "pdf_table_continuation_annotation_execution_invalid"
            )
        return snapshot


def _execution_from_native_prompt(
    *, content: str, prompt_snapshot: dict[str, Any]
) -> PdfTableContinuationAnnotationExecution:
    """Private issuer used exclusively by the native resolver adapter."""

    return PdfTableContinuationAnnotationExecution(
        content=content,
        prompt_snapshot=prompt_snapshot,
        _issuer=_EXECUTION_ISSUER,
    )


def pdf_table_continuation_annotation_prompt_hash(prompt_content: str) -> str:
    """Bind the managed instruction body to this exact sealed contract."""

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


def validate_pdf_table_continuation_annotation_prompt_snapshot(
    value: Any,
) -> dict[str, Any]:
    """Accept exactly the body-free receipt schema and no presentation data."""

    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "prompt_ref",
        "prompt_command",
        "prompt_version",
        "prompt_hash",
        "prompt_content_sha256",
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
        raise _snapshot_error()
    if (
        value.get("schema_version") != PROMPT_SNAPSHOT_SCHEMA_VERSION
        or not isinstance(value.get("prompt_ref"), str)
        or not value["prompt_ref"].strip()
        or value.get("prompt_command") != PROMPT_COMMAND
        or not isinstance(value.get("prompt_version"), str)
        or not value["prompt_version"].strip()
        or not isinstance(value.get("prompt_hash"), str)
        or _SHA256.fullmatch(value["prompt_hash"]) is None
        or not isinstance(value.get("prompt_content_sha256"), str)
        or _SHA256.fullmatch(value["prompt_content_sha256"]) is None
        or value.get("prompt_source") not in {"openwebui_prompt_history", "test"}
        or value.get("prompt_contract_id") != PROMPT_CONTRACT_ID
        or value.get("template_id") != PROMPT_TEMPLATE_ID
        or value.get("template_kind") != PROMPT_TEMPLATE_KIND
        or value.get("input_schema_version") != INPUT_SCHEMA_VERSION
        or value.get("output_schema_id") != OUTPUT_SCHEMA_ID
        or value.get("output_schema_version") != OUTPUT_SCHEMA_VERSION
        or value.get("tags") != [PROMPT_REQUIRED_TAG]
        or value.get("safe_metadata")
        != {"annotation_domain": "physical_table_continuation"}
    ):
        raise _snapshot_error()
    return copy.deepcopy(value)


def pdf_table_continuation_annotation_content_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _snapshot_error() -> PdfTableContinuationAnnotationContractError:
    return PdfTableContinuationAnnotationContractError(
        "pdf_table_continuation_annotation_prompt_snapshot_invalid"
    )


__all__ = [
    "INPUT_SCHEMA_VERSION",
    "OUTPUT_SCHEMA_ID",
    "OUTPUT_SCHEMA_VERSION",
    "PROMPT_COMMAND",
    "PROMPT_CONTRACT_ID",
    "PROMPT_REQUIRED_TAG",
    "PROMPT_SNAPSHOT_SCHEMA_VERSION",
    "PROMPT_TEMPLATE_ID",
    "PROMPT_TEMPLATE_KIND",
    "PdfTableContinuationAnnotationContractError",
    "PdfTableContinuationAnnotationExecution",
    "pdf_table_continuation_annotation_content_sha256",
    "pdf_table_continuation_annotation_prompt_hash",
    "validate_pdf_table_continuation_annotation_prompt_snapshot",
]
