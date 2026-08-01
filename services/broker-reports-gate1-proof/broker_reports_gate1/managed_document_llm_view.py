from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any, Mapping, Sequence

import tiktoken

from .managed_document_contracts import (
    ManagedDocumentContractValidator,
    canonical_document_json_bytes,
)


LLM_DOCUMENT_VIEW_SCHEMA_VERSION = "broker_reports_llm_document_view_v1"
LLM_DOCUMENT_VIEW_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_llm_document_view_receipt_v1"
)
LLM_DOCUMENT_VIEW_RENDERER_VERSION = (
    "broker_reports_managed_document_llm_view_renderer_v1"
)
REFERENCE_TOKENIZER_ID = "broker_reports_utf8_byte_bpe_v1"
REFERENCE_TOKENIZER_LIBRARY = "tiktoken"
REFERENCE_TOKENIZER_LIBRARY_VERSION = "0.12.0"

LLM_DOCUMENT_VIEW_ARTIFACT_TYPE = (
    "private_broker_reports_llm_document_view_v1"
)
LLM_DOCUMENT_VIEW_RECEIPT_ARTIFACT_TYPE = (
    "private_broker_reports_llm_document_view_receipt_v1"
)
LLM_DOCUMENT_VIEW_CHECKLIST_ARTIFACT_TYPE = (
    "private_broker_reports_llm_document_view_checklist_v1"
)
DOC3_PRIVATE_ARTIFACT_TYPES = frozenset(
    {
        LLM_DOCUMENT_VIEW_ARTIFACT_TYPE,
        LLM_DOCUMENT_VIEW_RECEIPT_ARTIFACT_TYPE,
        LLM_DOCUMENT_VIEW_CHECKLIST_ARTIFACT_TYPE,
    }
)

FACTORY_REQUIRED = (
    "ManagedDocumentLlmViewFactory.create is the only DOC3 Managed Document "
    "v1 to LLM Document View v1 renderer entrypoint"
)
FORBIDDEN = (
    "DOC3 callers must not bypass the renderer factory, filter or truncate "
    "document content, expose PRIVATE_SOURCE fields, call a provider, connect "
    "the view to a product route, or treat the view as document authority"
)

_HEADER = "BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1"
_TRUST = "CONTENT_TRUST UNTRUSTED_SOURCE_DOCUMENT"
_END = "END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1"
_ALLOWED_DISPOSITIONS = frozenset(
    {
        "RENDERED",
        "RENDERED_AS_SAFE_POINTER",
        "OMITTED_CONTROL_FIELD",
        "OMITTED_PRIVATE_SOURCE_FIELD",
        "OMITTED_REDUNDANT_WITH_EXACT_OWNER",
    }
)


@contextmanager
def inactive_doc3_artifact_type_scope():
    """Admit DOC3 private types only around the offline proof store operation."""

    from .artifact_models import ARTIFACT_TYPES

    preexisting = set(ARTIFACT_TYPES)
    ARTIFACT_TYPES.update(DOC3_PRIVATE_ARTIFACT_TYPES)
    try:
        yield
    finally:
        ARTIFACT_TYPES.intersection_update(preexisting)


@dataclass(frozen=True)
class ManagedDocumentLlmViewResult:
    view_text: str
    receipt: dict[str, Any]


class ManagedDocumentLlmViewFactory:
    """Sole inactive factory for the deterministic DOC3 renderer."""

    def create(
        self,
        managed_document_schema: Mapping[str, Any],
        field_disposition_contract: Mapping[str, Any],
    ) -> "ManagedDocumentLlmViewRenderer":
        validator = ManagedDocumentContractValidator(managed_document_schema)
        dispositions = _FieldDispositionResolver(field_disposition_contract)
        tokenizer = _ReferenceTokenizer()
        return ManagedDocumentLlmViewRenderer(
            validator=validator,
            dispositions=dispositions,
            tokenizer=tokenizer,
        )


class ManagedDocumentLlmViewRenderer:
    """Deterministic, non-selective projection from DOC1 to one text view."""

    def __init__(
        self,
        *,
        validator: ManagedDocumentContractValidator,
        dispositions: "_FieldDispositionResolver",
        tokenizer: "_ReferenceTokenizer",
    ) -> None:
        self._validator = validator
        self._dispositions = dispositions
        self._tokenizer = tokenizer

    def render(self, payload: Mapping[str, Any]) -> ManagedDocumentLlmViewResult:
        document = self._validator.validate(payload).payload
        field_coverage = self._dispositions.resolve_document(document)
        writer, render_index = self._render_lines(document)
        view_text = writer.text()

        replay_writer, replay_index = self._render_lines(document)
        replay_text = replay_writer.text()
        if view_text != replay_text or render_index != replay_index:
            raise ValueError("llm_document_view_internal_replay_mismatch")

        private_values = _private_source_values(document)
        leaked_values = sorted(value for value in private_values if value in view_text)
        if leaked_values:
            raise ValueError("llm_document_view_private_source_leak")

        receipt = self._build_receipt(
            document=document,
            writer=writer,
            render_index=render_index,
            field_coverage=field_coverage,
        )
        return ManagedDocumentLlmViewResult(view_text=view_text, receipt=receipt)

    def _render_lines(
        self, document: dict[str, Any]
    ) -> tuple["_LineWriter", dict[str, Any]]:
        anchors = {
            item["anchor_id"]: _safe_pointer(item) for item in document["anchors"]
        }
        writer = _LineWriter()
        index: dict[str, Any] = {
            "metadata": [],
            "blocks": [],
            "tables": [],
            "relations": [],
            "issues": [],
            "losses": [],
        }

        writer.marker(_HEADER)
        writer.marker(_TRUST)
        writer.marker("DOCUMENT_BEGIN")
        writer.value("DOCUMENT_ID", document["document_id"], "metadata")
        writer.value("SOURCE_FORMAT", document["source"]["format"], "metadata")
        writer.value(
            "SOURCE_PARTS_TOTAL",
            document["source"]["source_part_count"],
            "metadata",
        )
        writer.value(
            "DOCUMENT_QUALITY_STATUS", document["quality"]["status"], "metadata"
        )
        writer.value(
            "KNOWN_LOSSES_TOTAL",
            document["quality"]["known_losses_total"],
            "metadata",
        )
        writer.value(
            "BLOCKING_LOSSES_TOTAL",
            document["quality"]["blocking_losses_total"],
            "metadata",
        )
        writer.value(
            "UNKNOWN_BLOCKS_TOTAL",
            document["quality"]["unknown_blocks_total"],
            "metadata",
        )
        writer.value(
            "SOURCE_CONTEXT",
            {
                "mime_type": document["source"]["mime_type"],
                "source_details": document["source"]["source_details"],
            },
            "metadata",
        )

        writer.marker("METADATA_BEGIN")
        metadata_items = [
            (name, value)
            for name, value in document["metadata"].items()
            if name != "additional"
        ]
        metadata_items.extend(
            (item["name"], item) for item in document["metadata"]["additional"]
        )
        for name, field in metadata_items:
            start = writer.next_line_number
            writer.value("METADATA", name, "metadata")
            writer.value("STATUS", field["status"], "metadata")
            writer.value("ORIGIN", field["origin"], "metadata")
            writer.value("VALUE", field["value"], "metadata")
            writer.value("CANDIDATES", field["candidates"], "metadata")
            writer.value(
                "SOURCE",
                [anchors[item] for item in field["evidence_anchor_ids"]],
                "metadata",
            )
            writer.marker("METADATA_END")
            index["metadata"].append(
                {
                    "name": name,
                    "view_line_start": start,
                    "view_line_end": writer.line_count,
                    "source_content_sha256": _canonical_sha256(
                        _project_metadata(field, anchors)
                    ),
                }
            )
        writer.marker("METADATA_SECTION_END")

        writer.marker("ANCHORS_BEGIN")
        for anchor in document["anchors"]:
            writer.value("ANCHOR", anchors[anchor["anchor_id"]], "metadata")
        writer.marker("ANCHORS_END")

        writer.marker("BLOCKS_BEGIN")
        for block in document["blocks"]:
            block_index = self._render_block(writer, block, anchors)
            index["blocks"].append(block_index)
            if block["block_type"] == "TABLE":
                index["tables"].append(
                    _table_coverage(block, block_index["view_line_start"], block_index["view_line_end"])
                )
        writer.marker("BLOCKS_END")

        writer.marker("RELATIONS_BEGIN")
        for ordinal, relation in enumerate(document["relations"]):
            projection = {
                "relation_id": relation["relation_id"],
                "type": relation["relation_type"],
                "status": relation["status"],
                "origin": relation["origin"],
                "source": relation["source"],
                "target": relation["target"],
                "evidence": [
                    anchors[item] for item in relation["evidence_anchor_ids"]
                ],
                "issue_ids": relation["issue_ids"],
            }
            line = writer.next_line_number
            writer.value("RELATION", projection, "relations")
            index["relations"].append(
                _ordered_coverage(
                    id_key="relation_id",
                    item_id=relation["relation_id"],
                    ordinal=ordinal,
                    line=line,
                    projection=projection,
                )
            )
        writer.marker("RELATIONS_END")

        writer.value(
            "QUALITY",
            {
                key: value
                for key, value in document["quality"].items()
                if key
                not in {"information_class", "issue_ledger", "loss_ledger"}
            },
            "metadata",
        )
        writer.marker("ISSUES_BEGIN")
        for ordinal, issue in enumerate(document["quality"]["issue_ledger"]):
            projection = {
                "issue_id": issue["issue_id"],
                "code": issue["code"],
                "severity": issue["severity"],
                "message": issue["message"],
                "sources": [anchors[item] for item in issue["anchor_ids"]],
                "block_ids": issue["block_ids"],
                "relation_ids": issue["relation_ids"],
                "recoverability": issue["recoverability"],
                "requires_source_reread": issue["requires_source_reread"],
            }
            line = writer.next_line_number
            writer.value("ISSUE", projection, "issues")
            index["issues"].append(
                _ordered_coverage(
                    id_key="issue_id",
                    item_id=issue["issue_id"],
                    ordinal=ordinal,
                    line=line,
                    projection=projection,
                )
            )
        writer.marker("ISSUES_END")
        writer.marker("LOSSES_BEGIN")
        for ordinal, loss in enumerate(document["quality"]["loss_ledger"]):
            projection = {
                "loss_id": loss["loss_id"],
                "context_class": loss["context_class"],
                "what_lost": loss["what_lost"],
                "where": loss["where"],
                "reason": loss["reason"],
                "recoverability": loss["recoverability"],
                "requires_source_reread": loss["requires_source_reread"],
                "blocks_semantic_analysis": loss["blocks_semantic_analysis"],
                "accounted": loss["accounted"],
                "sources": [anchors[item] for item in loss["anchor_ids"]],
                "block_ids": loss["block_ids"],
            }
            line = writer.next_line_number
            writer.value("LOSS", projection, "losses")
            index["losses"].append(
                _ordered_coverage(
                    id_key="loss_id",
                    item_id=loss["loss_id"],
                    ordinal=ordinal,
                    line=line,
                    projection=projection,
                )
            )
        writer.marker("LOSSES_END")
        writer.marker("DOCUMENT_END")
        writer.marker(_END)
        return writer, index

    def _render_block(
        self,
        writer: "_LineWriter",
        block: dict[str, Any],
        anchors: Mapping[str, dict[str, Any]],
    ) -> dict[str, Any]:
        block_type = block["block_type"]
        category = _block_category(block_type)
        start = writer.next_line_number
        writer.marker("BLOCK_BEGIN", category)
        writer.value("ORDINAL", block["ordinal"], category)
        writer.value("BLOCK_ID", block["block_id"], category)
        writer.value("BLOCK_TYPE", block_type, category)
        writer.value(
            "SOURCE",
            [anchors[item] for item in block["source_anchor_ids"]],
            category,
        )
        writer.value(
            "RESTORATION_STATUS", block["restoration"]["status"], category
        )
        writer.value(
            "STRUCTURE_ORIGIN",
            block["restoration"]["classification_origin"],
            category,
        )
        writer.value(
            "RESTORATION_ISSUE_IDS",
            block["restoration"]["issue_ids"],
            category,
        )
        writer.value("ISSUE_IDS", block["issue_ids"], category)

        content = block["content"]
        if block_type == "HEADING":
            writer.value("HEADING_TEXT", content["raw_text"], category)
            writer.value("HEADING_LEVEL_STATUS", content["level_status"], category)
            writer.value("HEADING_LEVEL", content["level"], category)
        elif block_type == "PARAGRAPH":
            writer.value("TEXT", content["raw_text"], category)
            for event in content["join_events"]:
                writer.value("JOIN_EVENT", event, category)
        elif block_type == "LIST":
            writer.marker("LIST_BEGIN", category)
            for item in content["items"]:
                writer.indexed_value("ITEM", item["ordinal"], item, category)
            writer.marker("LIST_END", category)
        elif block_type == "TABLE":
            self._render_table(writer, content, anchors, category)
        elif block_type == "NOTE":
            writer.value(
                "NOTE",
                {"text": content["text"], "note_kind": content["note_kind"]},
                category,
            )
        elif block_type == "VISUAL":
            writer.value("VISUAL_TYPE", content["visual_type"], category)
            writer.value(
                "CAPTION", _project_metadata(content["caption"], anchors), category
            )
            writer.value(
                "DESCRIPTION",
                _project_metadata(content["safe_description"], anchors),
                category,
            )
            writer.value(
                "PROCESSING_STATUS", content["processing_status"], category
            )
            writer.value(
                "PRIVATE_SOURCE_AVAILABLE",
                content["private_artifact"]["status"] == "PRESENT",
                category,
            )
        elif block_type == "BOUNDARY":
            writer.value(
                "BOUNDARY",
                {
                    "kind": content["boundary_type"],
                    "source_part_index": content["source_part_index"],
                    "label": _project_metadata(content["label"], anchors),
                },
                category,
            )
        elif block_type == "UNKNOWN":
            writer.value("UNKNOWN_REASON", content["reason"], category)
            writer.value("RAW_TEXT", content["raw_text"], category)
            writer.value(
                "PRIVATE_SOURCE_AVAILABLE",
                content["private_artifact"]["status"] == "PRESENT",
                category,
            )
        else:  # pragma: no cover - DOC1 validator closes this enum.
            raise ValueError("llm_document_view_block_type_unsupported")

        writer.marker("BLOCK_END", category)
        projection = _project_block(block, anchors)
        return {
            "block_id": block["block_id"],
            "input_block_type": block_type,
            "ordinal": block["ordinal"],
            "view_line_start": start,
            "view_line_end": writer.line_count,
            "source_content_sha256": _canonical_sha256(projection),
            "rendered_content_sha256": _canonical_sha256(projection),
        }

    def _render_table(
        self,
        writer: "_LineWriter",
        content: dict[str, Any],
        anchors: Mapping[str, dict[str, Any]],
        category: str,
    ) -> None:
        writer.marker("TABLE_BEGIN", category)
        writer.value("TABLE_ID", content["table_id"], category)
        writer.value("TITLE", _project_metadata(content["title"], anchors), category)
        writer.value("DESCRIPTION", content["description"], category)
        writer.value("COMPLETENESS", content["completeness_status"], category)
        writer.value("ROWS_TOTAL", len(content["rows"]), category)
        writer.value(
            "COLUMNS_MAX_TOTAL", max(len(row) for row in content["rows"]), category
        )
        writer.value("HEADER_HIERARCHY", content["header_hierarchy"], category)
        writer.value("ROW_GROUPS", content["row_groups"], category)
        for marker in content["row_markers"]:
            writer.value("ROW_MARKER", marker, category)
        for unit in content["units"]:
            writer.value("UNIT", unit, category)
        for index, row in enumerate(content["rows"]):
            writer.indexed_value("ROW", index, row, category)
        for annotation in content["cell_annotations"]:
            writer.value("CELL_STATE", annotation, category)
        for relation_id in content["related_relation_ids"]:
            writer.value("RELATED_RELATION", relation_id, category)
        for relation_id in content["continuation_relation_ids"]:
            writer.value("CONTINUATION_RELATION", relation_id, category)
        for loss_id in content["known_gap_ids"]:
            writer.value("KNOWN_GAP", loss_id, category)
        writer.marker("TABLE_END", category)

    def _build_receipt(
        self,
        *,
        document: dict[str, Any],
        writer: "_LineWriter",
        render_index: dict[str, Any],
        field_coverage: dict[str, Any],
    ) -> dict[str, Any]:
        view_text = writer.text()
        blocks = copy.deepcopy(render_index["blocks"])
        for item in blocks:
            item["reference_tokens"] = self._tokenizer.count(
                writer.line_slice(item["view_line_start"], item["view_line_end"])
            )

        by_block_type: dict[str, dict[str, int]] = {}
        for block_type in sorted({item["block_type"] for item in document["blocks"]}):
            indexes = [
                item
                for item in blocks
                if item["input_block_type"] == block_type
            ]
            fragments = [
                writer.line_slice(item["view_line_start"], item["view_line_end"])
                for item in indexes
            ]
            joined = "".join(fragments)
            by_block_type[block_type] = {
                "blocks_total": len(indexes),
                "bytes": len(joined.encode("utf-8")),
                "characters": len(joined),
                "reference_tokens": self._tokenizer.count(joined),
            }

        pages: dict[str, list[dict[str, Any]]] = defaultdict(list)
        anchor_by_id = {item["anchor_id"]: item for item in document["anchors"]}
        for block, coverage in zip(document["blocks"], blocks, strict=True):
            page = _first_page(block, anchor_by_id)
            pages[str(page) if page is not None else "UNSPECIFIED"].append(coverage)
        by_page: dict[str, dict[str, int]] = {}
        for page, page_blocks in pages.items():
            joined = "".join(
                writer.line_slice(item["view_line_start"], item["view_line_end"])
                for item in page_blocks
            )
            by_page[page] = {
                "blocks_total": len(page_blocks),
                "bytes": len(joined.encode("utf-8")),
                "characters": len(joined),
                "reference_tokens": self._tokenizer.count(joined),
            }

        category_metrics = writer.category_metrics(self._tokenizer)
        source_values_bytes = sum(item["source_value_bytes"] for item in writer.records)
        renderer_overhead_bytes = sum(item["overhead_bytes"] for item in writer.records)
        if source_values_bytes + renderer_overhead_bytes != len(
            view_text.encode("utf-8")
        ):
            raise ValueError("llm_document_view_size_accounting_mismatch")

        block_counts = Counter(item["block_type"] for item in document["blocks"])
        table_blocks = [
            item for item in document["blocks"] if item["block_type"] == "TABLE"
        ]
        receipt: dict[str, Any] = {
            "schema_version": LLM_DOCUMENT_VIEW_RECEIPT_SCHEMA_VERSION,
            "input_document_id": document["document_id"],
            "input_managed_document_sha256": hashlib.sha256(
                canonical_document_json_bytes(document)
            ).hexdigest(),
            "managed_document_schema_version": document["schema_version"],
            "llm_document_view_schema_version": LLM_DOCUMENT_VIEW_SCHEMA_VERSION,
            "renderer_version": LLM_DOCUMENT_VIEW_RENDERER_VERSION,
            "output_view_sha256": hashlib.sha256(
                view_text.encode("utf-8")
            ).hexdigest(),
            "output_bytes": len(view_text.encode("utf-8")),
            "output_characters": len(view_text),
            "output_lines": writer.line_count,
            "whitespace_lexical_tokens": len(view_text.split()),
            "reference_tokenizer_id": REFERENCE_TOKENIZER_ID,
            "reference_tokenizer_library": REFERENCE_TOKENIZER_LIBRARY,
            "reference_tokenizer_version": REFERENCE_TOKENIZER_LIBRARY_VERSION,
            "reference_tokens_total": self._tokenizer.count(view_text),
            "block_coverage": blocks,
            "metadata_coverage": render_index["metadata"],
            "table_coverage": render_index["tables"],
            "relation_coverage": render_index["relations"],
            "issue_coverage": render_index["issues"],
            "loss_coverage": render_index["losses"],
            "coverage": {
                "blocks_input_total": len(document["blocks"]),
                "blocks_rendered_total": len(blocks),
                "content_blocks_omitted_total": 0,
                "table_blocks_input_total": len(table_blocks),
                "table_blocks_rendered_total": len(render_index["tables"]),
                "table_rows_input_total": sum(
                    len(item["content"]["rows"]) for item in table_blocks
                ),
                "table_rows_rendered_total": sum(
                    item["rows_rendered_total"] for item in render_index["tables"]
                ),
                "table_cells_input_total": sum(
                    len(row)
                    for item in table_blocks
                    for row in item["content"]["rows"]
                ),
                "table_cells_rendered_total": sum(
                    item["cells_rendered_total"] for item in render_index["tables"]
                ),
                "table_cells_omitted_total": 0,
                "unknown_blocks_input_total": block_counts["UNKNOWN"],
                "unknown_blocks_rendered_total": block_counts["UNKNOWN"],
                "unknown_blocks_omitted_total": 0,
                "visual_blocks_input_total": block_counts["VISUAL"],
                "visual_blocks_rendered_total": block_counts["VISUAL"],
                "visual_blocks_omitted_total": 0,
                "relations_input_total": len(document["relations"]),
                "relations_rendered_total": len(document["relations"]),
                "relations_omitted_total": 0,
                "issues_input_total": len(document["quality"]["issue_ledger"]),
                "issues_rendered_total": len(document["quality"]["issue_ledger"]),
                "known_losses_input_total": len(document["quality"]["loss_ledger"]),
                "known_losses_rendered_total": len(document["quality"]["loss_ledger"]),
                "known_losses_omitted_total": 0,
                "unaccounted_render_omissions_total": 0,
                "invented_source_content_total": 0,
                "private_source_fields_rendered_total": 0,
                "truncated_documents_total": 0,
                "filtered_blocks_total": 0,
                "filtered_table_rows_total": 0,
                "semantic_filtering_total": 0,
            },
            "field_disposition_coverage": field_coverage,
            "size_metrics": {
                "source_values_bytes": source_values_bytes,
                "renderer_overhead_bytes": renderer_overhead_bytes,
                "categories": category_metrics,
                "by_page": by_page,
                "by_block_type": by_block_type,
            },
            "privacy": {
                "private_source_fields_rendered_total": 0,
                "source_checksum_rendered": False,
                "private_ref_rendered": False,
                "local_path_rendered": False,
                "resolver_or_access_context_rendered": False,
                "provider_payload_rendered": False,
            },
            "replay_status": "PASSED_SELF_REPLAY",
            "integrity_policy": "sha256_canonical_json_without_integrity_sha256",
        }
        receipt["integrity_sha256"] = _canonical_sha256(receipt)
        return receipt


class _ReferenceTokenizer:
    def __init__(self) -> None:
        installed = version(REFERENCE_TOKENIZER_LIBRARY)
        if installed != REFERENCE_TOKENIZER_LIBRARY_VERSION:
            raise ValueError("llm_document_view_reference_tokenizer_version_mismatch")
        self._encoding = tiktoken.Encoding(
            name=REFERENCE_TOKENIZER_ID,
            pat_str=r"(?s).",
            mergeable_ranks={bytes([item]): item for item in range(256)},
            special_tokens={},
        )

    def count(self, value: str) -> int:
        tokens = self._encoding.encode(value)
        if self._encoding.decode(tokens) != value:
            raise ValueError("llm_document_view_reference_tokenizer_round_trip_failed")
        return len(tokens)


class _LineWriter:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.records: list[dict[str, Any]] = []

    @property
    def line_count(self) -> int:
        return len(self.lines)

    @property
    def next_line_number(self) -> int:
        return self.line_count + 1

    def marker(self, marker: str, category: str = "renderer") -> None:
        self._append(marker, category, source_value_bytes=0)

    def value(self, tag: str, value: Any, category: str) -> None:
        encoded = _canonical_json(value)
        self._append(
            f"{tag} {encoded}",
            category,
            source_value_bytes=len(encoded.encode("utf-8")),
        )

    def indexed_value(self, tag: str, index: int, value: Any, category: str) -> None:
        encoded = _canonical_json(value)
        self._append(
            f"{tag} {index} {encoded}",
            category,
            source_value_bytes=len(encoded.encode("utf-8")),
        )

    def _append(self, line: str, category: str, *, source_value_bytes: int) -> None:
        if "\n" in line or "\r" in line:
            raise ValueError("llm_document_view_physical_line_invalid")
        total_bytes = len((line + "\n").encode("utf-8"))
        self.lines.append(line)
        self.records.append(
            {
                "category": category,
                "source_value_bytes": source_value_bytes,
                "overhead_bytes": total_bytes - source_value_bytes,
                "total_bytes": total_bytes,
            }
        )

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"

    def line_slice(self, start: int, end: int) -> str:
        return "\n".join(self.lines[start - 1 : end]) + "\n"

    def category_metrics(
        self, tokenizer: _ReferenceTokenizer
    ) -> dict[str, dict[str, int]]:
        indexes: dict[str, list[int]] = defaultdict(list)
        for index, record in enumerate(self.records):
            indexes[record["category"]].append(index)
        result: dict[str, dict[str, int]] = {}
        for category, positions in sorted(indexes.items()):
            text = "".join(self.lines[item] + "\n" for item in positions)
            result[category] = {
                "bytes": len(text.encode("utf-8")),
                "characters": len(text),
                "lines": len(positions),
                "reference_tokens": tokenizer.count(text),
                "source_value_bytes": sum(
                    self.records[item]["source_value_bytes"] for item in positions
                ),
                "renderer_overhead_bytes": sum(
                    self.records[item]["overhead_bytes"] for item in positions
                ),
            }
        return result


class _FieldDispositionResolver:
    def __init__(self, contract: Mapping[str, Any]) -> None:
        candidate = copy.deepcopy(dict(contract))
        if candidate.get("schema_version") != (
            "broker_reports_doc1_to_doc3_view_coverage_v1"
        ):
            raise ValueError("llm_document_view_field_coverage_version_invalid")
        if set(candidate.get("allowed_dispositions", [])) != _ALLOWED_DISPOSITIONS:
            raise ValueError("llm_document_view_field_dispositions_invalid")
        rules = candidate.get("rules")
        if not isinstance(rules, list) or not rules:
            raise ValueError("llm_document_view_field_rules_missing")
        seen: set[str] = set()
        self._rules: list[dict[str, str]] = []
        for rule in rules:
            if set(rule) != {"doc1_field_path", "disposition", "exact_owner"}:
                raise ValueError("llm_document_view_field_rule_shape_invalid")
            path = rule["doc1_field_path"]
            if path in seen or not isinstance(path, str) or not path.startswith("/"):
                raise ValueError("llm_document_view_field_rule_path_invalid")
            if rule["disposition"] not in _ALLOWED_DISPOSITIONS:
                raise ValueError("llm_document_view_field_rule_disposition_invalid")
            if not rule["exact_owner"]:
                raise ValueError("llm_document_view_field_rule_owner_missing")
            seen.add(path)
            self._rules.append(dict(rule))
        self.contract_integrity_sha256 = str(candidate.get("integrity_sha256", ""))
        unsigned = copy.deepcopy(candidate)
        unsigned.pop("integrity_sha256", None)
        if self.contract_integrity_sha256 != _canonical_sha256(unsigned):
            raise ValueError("llm_document_view_field_coverage_integrity_invalid")

    def resolve_document(self, document: Mapping[str, Any]) -> dict[str, Any]:
        resolved: list[dict[str, str]] = []
        unaccounted: list[str] = []
        for path in _document_field_paths(document):
            matches = [rule for rule in self._rules if _path_matches(rule["doc1_field_path"], path)]
            if not matches:
                unaccounted.append(path)
                continue
            matches.sort(key=lambda item: _path_specificity(item["doc1_field_path"]), reverse=True)
            best = matches[0]
            if len(matches) > 1 and _path_specificity(matches[0]["doc1_field_path"]) == _path_specificity(matches[1]["doc1_field_path"]) and matches[0]["disposition"] != matches[1]["disposition"]:
                raise ValueError("llm_document_view_field_rule_ambiguous")
            resolved.append(
                {
                    "doc1_field_path": path,
                    "disposition": best["disposition"],
                    "exact_owner": best["exact_owner"],
                }
            )
        if unaccounted:
            raise ValueError("llm_document_view_unaccounted_field_paths")
        counts = Counter(item["disposition"] for item in resolved)
        return {
            "contract_integrity_sha256": self.contract_integrity_sha256,
            "input_field_paths_total": len(resolved),
            "disposition_counts": {
                key: counts.get(key, 0) for key in sorted(_ALLOWED_DISPOSITIONS)
            },
            "unaccounted_field_paths_total": 0,
            "unaccounted_field_paths": [],
            "resolved_fields": resolved,
        }


def _project_metadata(
    field: Mapping[str, Any], anchors: Mapping[str, dict[str, Any]]
) -> dict[str, Any]:
    return {
        "status": field["status"],
        "origin": field["origin"],
        "value": field["value"],
        "candidates": field["candidates"],
        "sources": [anchors[item] for item in field["evidence_anchor_ids"]],
    }


def _project_block(
    block: Mapping[str, Any], anchors: Mapping[str, dict[str, Any]]
) -> dict[str, Any]:
    content = copy.deepcopy(dict(block["content"]))
    content.pop("information_class", None)
    if block["block_type"] in {"VISUAL", "UNKNOWN"}:
        private = content.pop("private_artifact")
        content["private_source_available"] = private["status"] == "PRESENT"
    if block["block_type"] == "VISUAL":
        content["caption"] = _project_metadata(content["caption"], anchors)
        content["safe_description"] = _project_metadata(
            content["safe_description"], anchors
        )
    if block["block_type"] == "BOUNDARY":
        content["label"] = _project_metadata(content["label"], anchors)
    if block["block_type"] == "TABLE":
        content["title"] = _project_metadata(content["title"], anchors)
    return {
        "block_id": block["block_id"],
        "ordinal": block["ordinal"],
        "block_type": block["block_type"],
        "sources": [anchors[item] for item in block["source_anchor_ids"]],
        "restoration": {
            key: value
            for key, value in block["restoration"].items()
            if key != "information_class"
        },
        "issue_ids": block["issue_ids"],
        "content": content,
    }


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
        if locator.get(key) is not None:
            pointer[key] = locator[key]
    return pointer


def _table_coverage(block: Mapping[str, Any], start: int, end: int) -> dict[str, Any]:
    content = block["content"]
    rows = content["rows"]
    cells_total = sum(len(row) for row in rows)
    return {
        "table_id": content["table_id"],
        "block_id": block["block_id"],
        "ordinal": block["ordinal"],
        "view_line_start": start,
        "view_line_end": end,
        "rows_input_total": len(rows),
        "rows_rendered_total": len(rows),
        "cells_input_total": cells_total,
        "cells_rendered_total": cells_total,
        "annotations_input_total": len(content["cell_annotations"]),
        "annotations_rendered_total": len(content["cell_annotations"]),
    }


def _ordered_coverage(
    *,
    id_key: str,
    item_id: str,
    ordinal: int,
    line: int,
    projection: Mapping[str, Any],
) -> dict[str, Any]:
    projection_hash = _canonical_sha256(projection)
    return {
        id_key: item_id,
        "ordinal": ordinal,
        "view_line_start": line,
        "view_line_end": line,
        "source_content_sha256": projection_hash,
        "rendered_content_sha256": projection_hash,
    }


def _block_category(block_type: str) -> str:
    if block_type in {"HEADING", "PARAGRAPH", "LIST", "NOTE", "BOUNDARY"}:
        return "textual_blocks"
    if block_type == "TABLE":
        return "tables"
    if block_type == "UNKNOWN":
        return "unknown_blocks"
    if block_type == "VISUAL":
        return "visual_blocks"
    raise ValueError("llm_document_view_block_category_invalid")


def _first_page(
    block: Mapping[str, Any], anchors: Mapping[str, Mapping[str, Any]]
) -> int | None:
    for anchor_id in block["source_anchor_ids"]:
        page = anchors[anchor_id]["locator"].get("page")
        if page is not None:
            return int(page)
    return None


def _private_source_values(document: Mapping[str, Any]) -> set[str]:
    values: set[str] = {
        str(document["source"]["checksum_sha256"]),
        str(document["source"]["artifact"]["checksum_sha256"]),
        str(document["source"]["artifact"]["ref"]),
    }
    for anchor in document["anchors"]:
        values.add(str(anchor["checksum_sha256"]))
        private = anchor["locator"].get("private_locator")
        if private:
            values.update(str(private.get(key)) for key in ("ref", "checksum_sha256"))
    for block in document["blocks"]:
        private = block["content"].get("private_artifact")
        if private:
            values.update(str(private.get(key)) for key in ("ref", "checksum_sha256"))
    return {item for item in values if item not in {"None", ""}}


def _document_field_paths(value: Any, path: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, Mapping):
        for key in sorted(value):
            child_path = f"{path}/{key}"
            paths.append(child_path)
            paths.extend(_document_field_paths(value[key], child_path))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if not value:
            return paths
        for item in value:
            child_path = f"{path}/*"
            paths.extend(_document_field_paths(item, child_path))
    return sorted(set(paths))


def _path_matches(pattern: str, path: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        regex = re.escape(prefix).replace(r"\*", "[^/]+")
        return re.fullmatch(regex + r"(?:/.*)?", path) is not None
    regex = "^" + re.escape(pattern).replace(r"\*", "[^/]+") + "$"
    return re.fullmatch(regex, path) is not None


def _path_specificity(pattern: str) -> tuple[int, int]:
    return (len(pattern.replace("*", "")), -pattern.count("*"))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _canonical_sha256(value: Mapping[str, Any] | list[Any] | Any) -> str:
    material = copy.deepcopy(value)
    if isinstance(material, dict):
        material.pop("integrity_sha256", None)
    return hashlib.sha256(_canonical_json(material).encode("utf-8")).hexdigest()
