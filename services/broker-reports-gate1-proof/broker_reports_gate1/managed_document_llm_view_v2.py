from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .managed_document_contracts_v2 import ManagedDocumentContractV2Validator


LLM_DOCUMENT_VIEW_V2_SCHEMA_VERSION = "broker_reports_llm_document_view_v2"
LLM_DOCUMENT_VIEW_V2_RENDERER_VERSION = (
    "broker_reports_managed_document_llm_view_renderer_v2"
)

FACTORY_REQUIRED = (
    "ManagedDocumentLlmViewV2Factory.create is the sole DOC6 View v2 owner"
)
FORBIDDEN = (
    "grid projection, filtering, truncation, provider calls, product routing, "
    "and model-visible geometry or private source fields"
)

_HEADER = "BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2"
_DOCUMENT_BEGIN = "DOCUMENT_BEGIN"
_DOCUMENT_END = "DOCUMENT_END"
_END = "END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2"
_STANDARD_METADATA_FIELDS = (
    "document_type",
    "title",
    "issuer",
    "document_date",
    "reporting_period",
    "owner_or_account",
    "language",
    "primary_currency",
)
_MIN_PRIVATE_TAINT_LENGTH = 8


@dataclass(frozen=True)
class ManagedDocumentLlmViewV2Result:
    """Deterministic inactive model-visible projection."""

    text: str
    content_sha256: str


class ManagedDocumentLlmViewV2Factory:
    """Sole public factory for the inactive row-oriented View v2."""

    @staticmethod
    def create(
        managed_document: Mapping[str, Any],
        managed_document_schema: Mapping[str, Any],
    ) -> ManagedDocumentLlmViewV2Result:
        validator = ManagedDocumentContractV2Validator(managed_document_schema)
        validated = validator.validate(managed_document).payload
        return _ManagedDocumentLlmViewV2Renderer().render(validated)


class _ManagedDocumentLlmViewV2Renderer:
    def render(
        self, document: Mapping[str, Any]
    ) -> ManagedDocumentLlmViewV2Result:
        anchors = {
            item["anchor_id"]: _safe_pointer(item)
            for item in document["anchors"]
        }
        writer = _LineWriter()
        self._render_document(writer, document, anchors)
        text = writer.text()
        _assert_model_surface_safe(
            text,
            private_values=_private_source_values(document),
        )
        return ManagedDocumentLlmViewV2Result(
            text=text,
            content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        )

    def _render_document(
        self,
        writer: "_LineWriter",
        document: Mapping[str, Any],
        anchors: Mapping[str, dict[str, Any]],
    ) -> None:
        quality = document["quality"]
        writer.marker(_HEADER)
        writer.value("CONTENT_TRUST", "UNTRUSTED_SOURCE_DOCUMENT")
        writer.marker(_DOCUMENT_BEGIN)
        writer.value("SOURCE_FORMAT", document["source"]["format"])
        writer.value(
            "SOURCE_PARTS_TOTAL", document["source"]["source_part_count"]
        )
        writer.value("DOCUMENT_QUALITY_STATUS", quality["status"])
        writer.value("KNOWN_LOSSES_TOTAL", quality["known_losses_total"])
        writer.value(
            "BLOCKING_LOSSES_TOTAL", quality["blocking_losses_total"]
        )
        writer.value("UNKNOWN_BLOCKS_TOTAL", quality["unknown_blocks_total"])
        writer.value(
            "SOURCE_CONTEXT",
            {
                "mime_type": document["source"]["mime_type"],
                "source_details": document["source"]["source_details"],
            },
        )

        writer.marker("METADATA_BEGIN")
        metadata = document["metadata"]
        for name in _STANDARD_METADATA_FIELDS:
            self._render_metadata(writer, name, metadata[name], anchors)
        for named in metadata["additional"]:
            self._render_metadata(writer, named["name"], named, anchors)
        writer.marker("METADATA_END")

        writer.marker("ANCHORS_BEGIN")
        for anchor in document["anchors"]:
            writer.value("ANCHOR", anchors[anchor["anchor_id"]])
        writer.marker("ANCHORS_END")

        writer.marker("BLOCKS_BEGIN")
        for block in document["blocks"]:
            self._render_block(writer, block, anchors)
        writer.marker("BLOCKS_END")

        writer.marker("RELATIONS_BEGIN")
        for relation in document["relations"]:
            writer.value(
                "RELATION",
                {
                    "relation_id": relation["relation_id"],
                    "relation_type": relation["relation_type"],
                    "source": relation["source"],
                    "target": relation["target"],
                    "status": relation["status"],
                    "origin": relation["origin"],
                    "sources": _resolve_sources(
                        relation["evidence_anchor_ids"], anchors
                    ),
                    "issue_ids": relation["issue_ids"],
                },
            )
        writer.marker("RELATIONS_END")

        writer.value(
            "QUALITY",
            {
                key: value
                for key, value in quality.items()
                if key
                not in {"information_class", "issue_ledger", "loss_ledger"}
            },
        )
        writer.marker("ISSUES_BEGIN")
        for issue in quality["issue_ledger"]:
            writer.value(
                "ISSUE",
                {
                    key: copy.deepcopy(value)
                    for key, value in issue.items()
                    if key != "anchor_ids"
                }
                | {"sources": _resolve_sources(issue["anchor_ids"], anchors)},
            )
        writer.marker("ISSUES_END")
        writer.marker("LOSSES_BEGIN")
        for loss in quality["loss_ledger"]:
            writer.value(
                "LOSS",
                {
                    key: copy.deepcopy(value)
                    for key, value in loss.items()
                    if key != "anchor_ids"
                }
                | {"sources": _resolve_sources(loss["anchor_ids"], anchors)},
            )
        writer.marker("LOSSES_END")
        writer.marker(_DOCUMENT_END)
        writer.marker(_END)

    @staticmethod
    def _render_metadata(
        writer: "_LineWriter",
        name: str,
        field: Mapping[str, Any],
        anchors: Mapping[str, dict[str, Any]],
    ) -> None:
        writer.marker("METADATA_FIELD_BEGIN")
        writer.value("METADATA_NAME", name)
        writer.value("METADATA", _project_metadata(field, anchors))
        writer.marker("METADATA_FIELD_END")

    def _render_block(
        self,
        writer: "_LineWriter",
        block: Mapping[str, Any],
        anchors: Mapping[str, dict[str, Any]],
    ) -> None:
        writer.marker("BLOCK_BEGIN")
        writer.value("BLOCK_ORDINAL", block["ordinal"])
        writer.value("BLOCK_ID", block["block_id"])
        writer.value("BLOCK_TYPE", block["block_type"])
        writer.value(
            "BLOCK_SOURCE", _resolve_sources(block["source_anchor_ids"], anchors)
        )
        restoration = block["restoration"]
        writer.value(
            "RESTORATION",
            {
                key: copy.deepcopy(value)
                for key, value in restoration.items()
                if key != "information_class"
            },
        )
        writer.value("BLOCK_ISSUE_IDS", block["issue_ids"])
        if block["block_type"] == "TABLE":
            self._render_table(writer, block["content"], anchors)
        else:
            writer.value(
                "BLOCK_CONTENT",
                _project_non_table_content(
                    block["block_type"], block["content"], anchors
                ),
            )
        writer.marker("BLOCK_END")

    def _render_table(
        self,
        writer: "_LineWriter",
        table: Mapping[str, Any],
        anchors: Mapping[str, dict[str, Any]],
    ) -> None:
        writer.marker("TABLE_BEGIN")
        writer.value("TABLE_ID", table["table_id"])
        writer.value("TABLE_COMPLETENESS", table["completeness_status"])

        writer.marker("SOURCE_PARTS_BEGIN")
        for part in table["source_parts"]:
            writer.marker("SOURCE_PART_BEGIN")
            writer.value("SOURCE_PART_ORDINAL", part["ordinal"])
            writer.value("SOURCE_PART_ID", part["source_part_id"])
            writer.value("SOURCE_PART_PAGE", part["page"])
            writer.value(
                "SOURCE_PART_SOURCE", [anchors[part["region_anchor_id"]]]
            )
            writer.value("SOURCE_PART_FIRST_ROW_ID", part["first_row_id"])
            writer.value("SOURCE_PART_LAST_ROW_ID", part["last_row_id"])
            writer.value(
                "SOURCE_PART_CONTINUATION", part["continuation_status"]
            )
            writer.value("SOURCE_PART_ISSUE_IDS", part["issue_ids"])
            writer.marker("SOURCE_PART_END")
        writer.marker("SOURCE_PARTS_END")

        writer.marker("COLUMNS_BEGIN")
        for column in table["logical_columns"]:
            writer.marker("COLUMN_BEGIN")
            writer.value("COLUMN_ORDINAL", column["ordinal"])
            writer.value("COLUMN_ID", column["column_id"])
            writer.value("COLUMN_HEADER_PATH", column["header_path"])
            writer.value(
                "COLUMN_SOURCE",
                _resolve_sources(column["source_anchor_ids"], anchors),
            )
            writer.value("COLUMN_ISSUE_IDS", column["issue_ids"])
            writer.marker("COLUMN_END")
        writer.marker("COLUMNS_END")

        writer.marker("ROWS_BEGIN")
        for row in table["ordered_rows"]:
            writer.marker("ROW_BEGIN")
            writer.value("ROW_ORDINAL", row["ordinal"])
            writer.value("ROW_ID", row["row_id"])
            writer.value("ROW_ROLE", row["role"])
            writer.value("ROW_ROLE_ORIGIN", row["role_origin"])
            writer.value("ROW_NESTING_LEVEL", row["nesting_level"])
            writer.value("ROW_PARENT_ID", row["parent_row_id"])
            writer.value(
                "ROW_SOURCE", _resolve_sources(row["source_anchor_ids"], anchors)
            )
            writer.value("ROW_ISSUE_IDS", row["issue_ids"])
            writer.marker("ENTRIES_BEGIN")
            for entry in row["entries"]:
                writer.marker("ENTRY_BEGIN")
                writer.value("ENTRY_ORDINAL", entry["ordinal"])
                writer.value("ENTRY_ID", entry["entry_id"])
                writer.value("ENTRY_KIND", entry["kind"])
                writer.value("ENTRY_TEXT", entry["text"])
                writer.value("ENTRY_ORIGIN", entry["origin"])
                writer.value(
                    "ENTRY_COLUMN_BINDING_STATUS",
                    entry["column_binding_status"],
                )
                writer.value(
                    "ENTRY_LOGICAL_COLUMN_ID", entry["logical_column_id"]
                )
                writer.value(
                    "ENTRY_COVERS_LOGICAL_COLUMN_IDS",
                    entry["covers_logical_column_ids"],
                )
                writer.value(
                    "ENTRY_SOURCE",
                    _resolve_sources(entry["source_anchor_ids"], anchors),
                )
                writer.value("ENTRY_ISSUE_IDS", entry["issue_ids"])
                writer.marker("ENTRY_END")
            writer.marker("ENTRIES_END")
            writer.marker("ROW_END")
        writer.marker("ROWS_END")
        writer.value("TABLE_RELATION_IDS", table["relations"])
        writer.value("TABLE_ISSUE_IDS", table["issues"])
        writer.value("TABLE_KNOWN_GAP_IDS", table["known_gap_ids"])
        writer.marker("TABLE_END")


class _LineWriter:
    def __init__(self) -> None:
        self._lines: list[str] = []

    def marker(self, marker: str) -> None:
        self._lines.append(marker)

    def value(self, tag: str, value: Any) -> None:
        self._lines.append(f"{tag} {_canonical_json(value)}")

    def text(self) -> str:
        return "\n".join(self._lines) + "\n"


def _project_metadata(
    field: Mapping[str, Any],
    anchors: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": field["status"],
        "origin": field["origin"],
        "value": field["value"],
        "candidates": copy.deepcopy(field["candidates"]),
        "sources": _resolve_sources(field["evidence_anchor_ids"], anchors),
    }


def _project_non_table_content(
    block_type: str,
    raw_content: Mapping[str, Any],
    anchors: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    content = copy.deepcopy(dict(raw_content))
    content.pop("information_class", None)
    if block_type in {"VISUAL", "UNKNOWN"}:
        private = content.pop("private_artifact")
        content["private_source_available"] = private["status"] == "PRESENT"
    if block_type == "VISUAL":
        content["caption"] = _project_metadata(content["caption"], anchors)
        content["safe_description"] = _project_metadata(
            content["safe_description"], anchors
        )
    elif block_type == "BOUNDARY":
        content["label"] = _project_metadata(content["label"], anchors)
    return content


def _resolve_sources(
    anchor_ids: list[str],
    anchors: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [copy.deepcopy(anchors[anchor_id]) for anchor_id in anchor_ids]


def _safe_pointer(anchor: Mapping[str, Any]) -> dict[str, Any]:
    locator = anchor["locator"]
    pointer: dict[str, Any] = {
        "anchor_id": anchor["anchor_id"],
        "format": anchor["source_format"],
        "source_part_index": locator["source_part_index"],
    }
    for key in (
        "page",
        "row_start",
        "row_end",
        "column_start",
        "column_end",
        "ordinal",
    ):
        value = locator.get(key)
        if value is not None:
            pointer[key] = value
    return pointer


def _assert_model_surface_safe(
    text: str, *, private_values: set[str]
) -> None:
    for line in text.splitlines():
        _, separator, raw_json = line.partition(" ")
        if separator:
            value = json.loads(raw_json)
            _assert_value_has_no_private_keys(value)
            _assert_value_has_no_private_values(value, private_values)


def _assert_value_has_no_private_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = "".join(
                character
                for character in key.casefold()
                if character.isalnum()
            )
            if key != "private_source_available" and any(
                token in normalized
                for token in (
                    "bbox",
                    "checksum",
                    "artifactref",
                    "continuationevidence",
                    "privateartifact",
                    "privatelocator",
                    "geometry",
                    "confidence",
                    "sourceword",
                    "coordinate",
                )
            ):
                raise ValueError("llm_document_view_v2_private_field_rendered")
            _assert_value_has_no_private_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_value_has_no_private_keys(item)


def _assert_value_has_no_private_values(
    value: Any, private_values: set[str]
) -> None:
    if isinstance(value, str):
        if any(
            (
                private in value
                if len(private) >= _MIN_PRIVATE_TAINT_LENGTH
                else value == private
            )
            for private in private_values
        ):
            raise ValueError("llm_document_view_v2_private_source_leak")
    elif isinstance(value, dict):
        for key, item in value.items():
            _assert_value_has_no_private_values(key, private_values)
            _assert_value_has_no_private_values(item, private_values)
    elif isinstance(value, list):
        for item in value:
            _assert_value_has_no_private_values(item, private_values)


def _private_source_values(document: Mapping[str, Any]) -> set[str]:
    source = document["source"]
    values: set[Any] = {
        document.get("document_id"),
        source.get("checksum_sha256"),
        source.get("artifact", {}).get("ref"),
        source.get("artifact", {}).get("checksum_sha256"),
    }
    for anchor in document["anchors"]:
        locator = anchor["locator"]
        private = locator.get("private_locator") or {}
        values.update(
            {
                anchor.get("checksum_sha256"),
                private.get("ref"),
                private.get("checksum_sha256"),
                locator.get("source_block_ref"),
                locator.get("dom_path"),
                locator.get("sheet"),
                locator.get("cell_range"),
                locator.get("source_ref"),
            }
        )
    for block in document["blocks"]:
        private = block["content"].get("private_artifact") or {}
        values.update({private.get("ref"), private.get("checksum_sha256")})
        if block["block_type"] == "TABLE":
            for part in block["content"]["source_parts"]:
                values.update(part["continuation_evidence_ids"])
    for evidence in document["geometry_evidence"]:
        private = evidence["private_artifact"]
        values.update(
            {
                evidence.get("geometry_evidence_id"),
                evidence.get("evidence_checksum_sha256"),
                private.get("ref"),
                private.get("checksum_sha256"),
            }
        )
    for ownership in document["source_word_ownership"]:
        values.update(
            {
                ownership.get("source_word_id"),
                ownership.get("duplicate_of_source_word_id"),
            }
        )
    return {
        str(value)
        for value in values
        if value not in {None, ""}
    }


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
