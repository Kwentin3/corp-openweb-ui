"""Native OpenWebUI managed-Prompt adapter for instructional classification."""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .instructional_table_classification import (
    INPUT_SCHEMA_VERSION,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_CONTRACT_ID,
    PROMPT_PLACEHOLDER,
    prompt_hash,
)
from .ordinary_trade_mapping_prompt import (
    OrdinaryTradeMappingPromptConfig,
    OrdinaryTradeMappingPromptError,
    OpenWebUIServerOrdinaryTradeMappingPromptResolver,
    OpenWebUISqliteOrdinaryTradeMappingPromptResolver,
)


PROMPT_COMMAND = "broker_instructional_table_classification_v1"
PROMPT_TEMPLATE_ID = "broker_reports.instructional_table_classification.v1"
PROMPT_TEMPLATE_KIND = "broker_reports_instructional_table_classification"
PROMPT_REQUIRED_TAG = "broker-reports-instructional-classification"
PROMPT_SNAPSHOT_SCHEMA_VERSION = (
    "broker_reports_instructional_table_classification_prompt_snapshot_v1"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class InstructionalClassificationManagedPrompt:
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


@dataclass(frozen=True)
class InstructionalClassificationPromptConfig:
    source: str = "openwebui_sqlite"
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
            required_output_schema_id=OUTPUT_SCHEMA_VERSION,
            required_output_schema_version=OUTPUT_SCHEMA_VERSION,
            required_tag=PROMPT_REQUIRED_TAG,
            required_placeholder=PROMPT_PLACEHOLDER,
            release_prompt_version=self.release_prompt_version,
            release_prompt_hash=self.release_prompt_hash,
        )


class _InstructionalPromptMixin:
    @staticmethod
    def _row_to_prompt(row: Any) -> InstructionalClassificationManagedPrompt:
        content = str(row["content"] or "")
        meta = _json_dict(row["meta"])
        tags = tuple(_json_list(row["tags"]))
        return InstructionalClassificationManagedPrompt(
            prompt_ref=str(row["id"]),
            command=str(row["command"] or "") or None,
            version=str(row["version_id"]),
            content=content,
            hash=prompt_hash(content),
            source="openwebui_prompt_history",
            template_id=str(meta["template_id"]),
            template_kind=str(meta["template_kind"]),
            prompt_contract_id=str(meta["prompt_contract_id"]),
            input_schema_version=str(meta["input_contract"]),
            output_schema_id=str(meta["output_schema_id"]),
            output_schema_version=str(meta["output_schema_version"]),
            tags=tags,
            safe_metadata={
                "name": str(row["name"] or row["command"]),
                "mapping_domain": str(meta.get("mapping_domain") or "ordinary_trade"),
            },
        )


class OpenWebUIInstructionalClassificationPromptResolver(
    _InstructionalPromptMixin, OpenWebUISqliteOrdinaryTradeMappingPromptResolver
):
    pass


class OpenWebUIServerInstructionalClassificationPromptResolver(
    _InstructionalPromptMixin, OpenWebUIServerOrdinaryTradeMappingPromptResolver
):
    pass


class InstructionalClassificationPromptResolverFactory:
    def __init__(self, config: InstructionalClassificationPromptConfig) -> None:
        self.config = config

    def create(self) -> OpenWebUIInstructionalClassificationPromptResolver:
        native = self.config.native_config()
        if native.source != "openwebui_sqlite" or native.db_path is None:
            raise OrdinaryTradeMappingPromptError(
                "instructional_classification_prompt_unavailable",
                "Instructional classification Prompt source is unavailable",
            )
        return OpenWebUIInstructionalClassificationPromptResolver(native)

    def create_async(self) -> OpenWebUIServerInstructionalClassificationPromptResolver:
        native = self.config.native_config()
        if native.source != "openwebui_server":
            raise OrdinaryTradeMappingPromptError(
                "instructional_classification_prompt_unavailable",
                "Instructional classification Prompt source is unavailable",
            )
        return OpenWebUIServerInstructionalClassificationPromptResolver(native)


def validate_instructional_classification_prompt_snapshot(value: Any) -> dict[str, Any]:
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
            "instructional_classification_prompt_snapshot_invalid",
            "Instructional classification Prompt snapshot shape is invalid",
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
        or value.get("output_schema_id") != OUTPUT_SCHEMA_VERSION
        or value.get("output_schema_version") != OUTPUT_SCHEMA_VERSION
        or not isinstance(value.get("tags"), list)
        or any(not isinstance(tag, str) for tag in value["tags"])
        or PROMPT_REQUIRED_TAG not in value["tags"]
        or not isinstance(value.get("safe_metadata"), dict)
        or set(value["safe_metadata"]) - {"name", "mapping_domain"}
    ):
        raise OrdinaryTradeMappingPromptError(
            "instructional_classification_prompt_snapshot_invalid",
            "Instructional classification Prompt snapshot contract is invalid",
        )
    return copy.deepcopy(value)


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
