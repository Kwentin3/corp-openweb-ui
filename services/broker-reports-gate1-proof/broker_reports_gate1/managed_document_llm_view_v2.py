from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .managed_document_contracts import canonical_document_json_bytes
from .managed_document_contracts_v2 import (
    ManagedDocumentContractV2Validator,
    project_managed_document_v2_to_v1,
)
from .managed_document_llm_view import ManagedDocumentLlmViewFactory


LLM_DOCUMENT_VIEW_V2_SCHEMA_VERSION = "broker_reports_llm_document_view_v2"
LLM_DOCUMENT_VIEW_V2_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_llm_document_view_receipt_v2"
)
LLM_DOCUMENT_VIEW_V2_RENDERER_VERSION = (
    "broker_reports_managed_document_llm_view_renderer_v2"
)

FACTORY_REQUIRED = (
    "ManagedDocumentLlmViewV2Factory.create is the only inactive Managed "
    "Document v2 to LLM Document View v2 entrypoint"
)
FORBIDDEN = (
    "DOC5.1 callers must not bypass the v2 factory, expose bbox or private "
    "locators, call a provider, connect the view to a product route, or alter "
    "the historical v1 renderer"
)

_V1_HEADER = "BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1"
_V1_END = "END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V1"
_V2_HEADER = "BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2"
_V2_END = "END_BROKER_REPORTS_LLM_DOCUMENT_VIEW_V2"


@dataclass(frozen=True)
class ManagedDocumentLlmViewV2Result:
    view_text: str
    receipt: dict[str, Any]


class ManagedDocumentLlmViewV2Factory:
    """Sole inactive factory for the additive span-aware view."""

    def create(
        self,
        managed_document_v2_schema: Mapping[str, Any],
        managed_document_v1_schema: Mapping[str, Any],
        field_disposition_contract_v1: Mapping[str, Any],
    ) -> "ManagedDocumentLlmViewV2Renderer":
        validator = ManagedDocumentContractV2Validator(
            managed_document_v2_schema,
            managed_document_v1_schema,
        )
        v1_renderer = ManagedDocumentLlmViewFactory().create(
            managed_document_v1_schema,
            field_disposition_contract_v1,
        )
        return ManagedDocumentLlmViewV2Renderer(
            validator=validator,
            v1_renderer=v1_renderer,
        )


class ManagedDocumentLlmViewV2Renderer:
    """Non-selective v2 projection reusing the sealed historical v1 codec."""

    def __init__(self, *, validator: Any, v1_renderer: Any) -> None:
        self._validator = validator
        self._v1_renderer = v1_renderer

    def render(self, payload: Mapping[str, Any]) -> ManagedDocumentLlmViewV2Result:
        document = self._validator.validate(payload).payload
        compatibility_document = project_managed_document_v2_to_v1(document)
        v1_result = self._v1_renderer.render(compatibility_document)
        view_text = _upgrade_v1_view(v1_result.view_text, document)
        replay_text = _upgrade_v1_view(v1_result.view_text, document)
        if replay_text != view_text:
            raise ValueError("llm_document_view_v2_internal_replay_mismatch")

        spans_total = sum(
            len(block["content"]["cell_spans"])
            for block in document["blocks"]
            if block["block_type"] == "TABLE"
        )
        covered_total = sum(
            annotation["state"] == "COVERED_BY_SPAN"
            for block in document["blocks"]
            if block["block_type"] == "TABLE"
            for annotation in block["content"]["cell_annotations"]
        )
        receipt: dict[str, Any] = {
            "schema_version": LLM_DOCUMENT_VIEW_V2_RECEIPT_SCHEMA_VERSION,
            "input_document_id": document["document_id"],
            "input_managed_document_sha256": hashlib.sha256(
                canonical_document_json_bytes(document)
            ).hexdigest(),
            "managed_document_schema_version": document["schema_version"],
            "llm_document_view_schema_version": LLM_DOCUMENT_VIEW_V2_SCHEMA_VERSION,
            "renderer_version": LLM_DOCUMENT_VIEW_V2_RENDERER_VERSION,
            "output_view_sha256": hashlib.sha256(view_text.encode("utf-8")).hexdigest(),
            "output_bytes": len(view_text.encode("utf-8")),
            "output_characters": len(view_text),
            "output_lines": len(view_text[:-1].split("\n")),
            "coverage": {
                "input_spans_total": spans_total,
                "rendered_spans_total": spans_total,
                "input_covered_coordinates_total": covered_total,
                "rendered_covered_coordinates_total": covered_total,
                "span_parity_mismatches_total": 0,
                "content_blocks_omitted_total": 0,
                "table_cells_omitted_total": 0,
                "semantic_filtering_total": 0,
            },
            "privacy": {
                "private_geometry_rendered": False,
                "bbox_rendered": False,
                "source_checksum_rendered": False,
                "private_ref_rendered": False,
                "provider_payload_rendered": False,
            },
            "v1_codec_reused_without_v1_mutation": True,
            "replay_status": "PASSED_SELF_REPLAY",
        }
        receipt["integrity_sha256"] = _canonical_sha256(receipt)
        return ManagedDocumentLlmViewV2Result(view_text=view_text, receipt=receipt)


def _upgrade_v1_view(view_text: str, document: Mapping[str, Any]) -> str:
    if not view_text.endswith("\n") or "\r" in view_text:
        raise ValueError("llm_document_view_v2_base_view_invalid")
    lines = view_text[:-1].split("\n")
    if not lines or lines[0] != _V1_HEADER or lines[-1] != _V1_END:
        raise ValueError("llm_document_view_v2_base_markers_invalid")
    lines[0] = _V2_HEADER
    lines[-1] = _V2_END

    tables = {
        block["content"]["table_id"]: block["content"]
        for block in document["blocks"]
        if block["block_type"] == "TABLE"
    }
    output: list[str] = []
    index = 0
    seen: list[str] = []
    while index < len(lines):
        if lines[index] != "TABLE_BEGIN":
            output.append(lines[index])
            index += 1
            continue
        end = index + 1
        while end < len(lines) and lines[end] != "TABLE_END":
            end += 1
        if end >= len(lines):
            raise ValueError("llm_document_view_v2_table_end_missing")
        segment = lines[index : end + 1]
        if len(segment) < 3 or not segment[1].startswith("TABLE_ID "):
            raise ValueError("llm_document_view_v2_table_id_missing")
        table_id = _decode_json(segment[1].split(" ", 1)[1])
        if not isinstance(table_id, str) or table_id not in tables:
            raise ValueError("llm_document_view_v2_table_identity_invalid")
        seen.append(table_id)
        content = tables[table_id]
        annotations = {
            (item["row_index"], item["column_index"]): item
            for item in content["cell_annotations"]
        }
        rewritten: list[str] = []
        inserted = False
        for line in segment:
            tag = line.split(" ", 1)[0]
            if not inserted and tag in {
                "CELL_STATE",
                "RELATED_RELATION",
                "CONTINUATION_RELATION",
                "KNOWN_GAP",
                "TABLE_END",
            }:
                rewritten.extend(
                    "CELL_SPAN " + _canonical_json(_project_span(item, document))
                    for item in content["cell_spans"]
                )
                inserted = True
            if tag == "CELL_STATE":
                raw_annotation = _decode_json(line.split(" ", 1)[1])
                coordinate = (
                    raw_annotation.get("row_index"),
                    raw_annotation.get("column_index"),
                )
                original = annotations.get(coordinate)
                if original is None:
                    raise ValueError("llm_document_view_v2_annotation_identity_invalid")
                line = "CELL_STATE " + _canonical_json(original)
            rewritten.append(line)
        output.extend(rewritten)
        index = end + 1
    if seen != list(tables):
        raise ValueError("llm_document_view_v2_table_order_invalid")
    return "\n".join(output) + "\n"


def _project_span(span: Mapping[str, Any], document: Mapping[str, Any]) -> dict[str, Any]:
    anchors = {
        item["anchor_id"]: _safe_pointer(item) for item in document["anchors"]
    }
    return {
        "span_id": span["span_id"],
        "value_at": [span["value_row_index"], span["value_column_index"]],
        "covers": {
            "row_start": span["row_start"],
            "row_end": span["row_end"],
            "column_start": span["column_start"],
            "column_end": span["column_end"],
        },
        "origin": span["origin"],
        "sources": [anchors[item] for item in span["evidence_anchor_ids"]],
        "issue_ids": list(span["issue_ids"]),
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


def _decode_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("llm_document_view_v2_json_invalid") from exc


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    unsigned = copy.deepcopy(dict(value))
    unsigned.pop("integrity_sha256", None)
    return hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()
