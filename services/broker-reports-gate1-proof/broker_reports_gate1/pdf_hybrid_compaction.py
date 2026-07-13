from __future__ import annotations

import math
import re
from dataclasses import dataclass
from statistics import median
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import sha256_json


PDF_HYBRID_COMPACT_LEDGER_SCHEMA = "broker_reports_pdf_hybrid_compact_ledger_v2"
PDF_HYBRID_COMPACTION_POLICY_VERSION = "pdf_hybrid_compaction_policy_v2"
FACTORY_REQUIRED = (
    "PdfHybridCompactionFactory.create is the only compact hybrid ledger entrypoint"
)
FORBIDDEN = (
    "Compaction must not summarize, normalize, drop, duplicate, or fuzzily reconstruct source words"
)


class PdfHybridCompactionError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfHybridCompactionConfig:
    policy_version: str = PDF_HYBRID_COMPACTION_POLICY_VERSION


class PdfHybridCompactionFactory:
    def __init__(self, config: PdfHybridCompactionConfig | None = None) -> None:
        self.config = config or PdfHybridCompactionConfig()

    def create(self) -> "PdfHybridCompactor":
        if self.config.policy_version != PDF_HYBRID_COMPACTION_POLICY_VERSION:
            raise PdfHybridCompactionError("pdf_hybrid_compaction_policy_invalid")
        return PdfHybridCompactor(self.config)


class PdfHybridCompactor:
    def __init__(self, config: PdfHybridCompactionConfig) -> None:
        self.config = config

    def compact(
        self,
        *,
        document_ref: str,
        pdf_sha256: str,
        page_ref: str,
        page_number: int,
        table_candidate: dict[str, Any],
        pdf_text_layer_projection: dict[str, Any],
        header_depth: int,
    ) -> dict[str, Any]:
        table_ref = str(table_candidate.get("table_candidate_ref") or "")
        if not table_ref:
            raise PdfHybridCompactionError("pdf_hybrid_compaction_table_identity_missing")
        bbox_by_ref = {
            str(item.get("bbox_ref") or ""): _bbox(item.get("bbox"))
            for item in _dicts(pdf_text_layer_projection.get("bbox_inventory"))
            if item.get("bbox_ref")
        }
        table_bbox = bbox_by_ref.get(str(table_candidate.get("bbox_ref") or ""))
        if table_bbox is None:
            raise PdfHybridCompactionError("pdf_hybrid_compaction_table_bbox_missing")
        owned_refs = [
            str(item) for item in table_candidate.get("contributing_word_refs") or []
        ]
        if len(owned_refs) != len(set(owned_refs)):
            raise PdfHybridCompactionError("pdf_hybrid_compaction_source_word_duplicate")
        owned_set = set(owned_refs)
        words = [
            item
            for item in _dicts(pdf_text_layer_projection.get("word_inventory"))
            if item.get("page_ref") == page_ref
            and str(item.get("word_ref") or "") in owned_set
        ]
        words.sort(key=_word_order)
        word_by_ref = {str(item.get("word_ref") or ""): item for item in words}
        if set(word_by_ref) != owned_set:
            raise PdfHybridCompactionError("pdf_hybrid_compaction_source_scope_incomplete")
        cells = sorted(
            _dicts(table_candidate.get("cell_inventory")),
            key=lambda item: (
                int(item.get("row_ordinal") or 0),
                int(item.get("column_ordinal") or 0),
                str(item.get("cell_ref") or ""),
            ),
        )
        if not cells:
            raise PdfHybridCompactionError("pdf_hybrid_compaction_cell_inventory_missing")
        cell_records = []
        for cell in cells:
            cell_bbox = bbox_by_ref.get(str(cell.get("bbox_ref") or ""))
            row = int(cell.get("row_ordinal") or 0)
            column = int(cell.get("column_ordinal") or 0)
            if cell_bbox is None or row < 1 or column < 1:
                raise PdfHybridCompactionError("pdf_hybrid_compaction_cell_geometry_invalid")
            cell_records.append(
                {
                    "row": row,
                    "column": column,
                    "bbox": cell_bbox,
                    "cell_ref": str(cell.get("cell_ref") or ""),
                    "word_refs": [
                        str(ref)
                        for ref in cell.get("word_refs") or []
                        if str(ref) in word_by_ref
                    ],
                }
            )
        row_count = max(item["row"] for item in cell_records)
        column_count = max(item["column"] for item in cell_records)
        if header_depth < 0 or header_depth > row_count:
            raise PdfHybridCompactionError("pdf_hybrid_compaction_header_depth_invalid")
        by_cell = {(item["row"], item["column"]): item for item in cell_records}
        if len(by_cell) != len(cell_records):
            raise PdfHybridCompactionError("pdf_hybrid_compaction_cell_identity_duplicate")
        claimed: set[str] = set()
        for cell in cell_records:
            unique = []
            for ref in cell["word_refs"]:
                if ref not in claimed:
                    unique.append(ref)
                    claimed.add(ref)
            cell["word_refs"] = unique
        for ref in sorted(owned_set - claimed, key=lambda item: _word_order(word_by_ref[item])):
            word_bbox = bbox_by_ref.get(str(word_by_ref[ref].get("bbox_ref") or ""))
            if word_bbox is None:
                raise PdfHybridCompactionError("pdf_hybrid_compaction_word_bbox_missing")
            selected = _select_cell(word_bbox, cell_records)
            selected["word_refs"].append(ref)
            claimed.add(ref)
        if claimed != owned_set:
            raise PdfHybridCompactionError("pdf_hybrid_compaction_source_ownership_incomplete")

        dictionary: dict[str, Any] = {}
        model_records: list[list[Any]] = []
        candidate_order: list[str] = []
        source_refs_seen: list[str] = []
        word_refs_seen: list[str] = []
        for cell in cell_records:
            refs = sorted(cell["word_refs"], key=lambda item: _word_order(word_by_ref[item]))
            if not refs:
                continue
            candidate_id = _dense_id(len(candidate_order))
            selected_words = [word_by_ref[ref] for ref in refs]
            word_bboxes = [
                bbox_by_ref.get(str(word.get("bbox_ref") or ""))
                for word in selected_words
            ]
            if any(item is None for item in word_bboxes):
                raise PdfHybridCompactionError("pdf_hybrid_compaction_word_bbox_missing")
            source_bbox = _bbox_union([item for item in word_bboxes if item is not None])
            text = " ".join(str(word.get("text") or "") for word in selected_words)
            source_value_refs = [
                str(word.get("source_value_ref") or "") for word in selected_words
            ]
            text_checksum_refs = [
                str(word.get("text_checksum_ref") or "") for word in selected_words
            ]
            entry = {
                "candidate_id": candidate_id,
                "exact_source_span": text,
                "source_value_refs": source_value_refs,
                "word_refs": refs,
                "source_bbox": source_bbox,
                "source_bbox_refs": [
                    str(word.get("bbox_ref") or "") for word in selected_words
                ],
                "source_text_checksum_refs": text_checksum_refs,
                "private_exact_value_paths": [
                    {"kind": "pdf_layout_word_text", "word_ref": ref} for ref in refs
                ],
                "source_cell_ref": cell["cell_ref"],
                "source_cell_bbox": cell["bbox"],
                "expected_row_ordinal": cell["row"],
                "expected_column_ordinal": cell["column"],
                "source_order": len(candidate_order),
            }
            entry["candidate_checksum"] = sha256_json(entry)
            dictionary[candidate_id] = entry
            candidate_order.append(candidate_id)
            source_refs_seen.extend(source_value_refs)
            word_refs_seen.extend(refs)
            normalized = _normalized_bbox(source_bbox, table_bbox)
            model_records.append(
                [
                    candidate_id,
                    text,
                    _mechanical_class(text),
                    *normalized,
                ]
            )

        if sorted(word_refs_seen) != sorted(owned_refs):
            raise PdfHybridCompactionError("pdf_hybrid_compaction_word_coverage_failed")
        if len(word_refs_seen) != len(set(word_refs_seen)):
            raise PdfHybridCompactionError("pdf_hybrid_compaction_word_ownership_not_exactly_once")
        column_model = _grid_axis_model(cell_records, "column", column_count)
        row_model = _grid_axis_model(cell_records, "row", row_count)
        header_ids = [
            item
            for item in candidate_order
            if int(dictionary[item]["expected_row_ordinal"]) <= header_depth
        ]
        shared_header = {
            "header_depth": header_depth,
            "candidate_ids": header_ids,
            "column_model": column_model,
        }
        shared_header["shared_header_hash"] = sha256_json(shared_header)
        ledger_id = "pdfhybridledger_" + stable_digest(
            [
                pdf_sha256,
                page_ref,
                table_ref,
                sha256_json(dictionary),
                self.config.policy_version,
            ],
            length=24,
        )
        ledger = {
            "schema_version": PDF_HYBRID_COMPACT_LEDGER_SCHEMA,
            "policy_version": self.config.policy_version,
            "ledger_id": ledger_id,
            "document_ref": document_ref,
            "pdf_sha256": pdf_sha256,
            "page_ref": page_ref,
            "page_number": page_number,
            "table_ref": table_ref,
            "table_bbox": table_bbox,
            "row_count": row_count,
            "column_count": column_count,
            "header_depth": header_depth,
            "candidate_order": candidate_order,
            "model_candidate_records": model_records,
            "private_candidate_dictionary": dictionary,
            "candidate_dictionary_hash": sha256_json(dictionary),
            "column_model": column_model,
            "row_model": row_model,
            "shared_header": shared_header,
            "source_accounting": {
                "owned_word_refs": len(owned_refs),
                "classified_word_refs": len(word_refs_seen),
                "unique_word_refs": len(set(word_refs_seen)),
                "source_value_refs": len(source_refs_seen),
                "compact_candidates": len(candidate_order),
                "non_empty_source_cells": sum(bool(item["word_refs"]) for item in cell_records),
                "source_cells": len(cell_records),
                "word_coverage_ratio": 1.0,
                "exactly_once_candidate_ownership": True,
                "lossy_summary_performed": False,
                "fuzzy_reconstruction_performed": False,
            },
        }
        ledger["ledger_checksum"] = sha256_json(ledger)
        return ledger


def _grid_axis_model(
    cells: list[dict[str, Any]], axis: str, expected_segments: int
) -> list[dict[str, Any]]:
    first_index, second_index = (0, 2) if axis == "column" else (1, 3)
    coordinates = sorted(
        float(item["bbox"][index])
        for item in cells
        for index in (first_index, second_index)
    )
    clusters: list[list[float]] = []
    for coordinate in coordinates:
        if not clusters or abs(coordinate - median(clusters[-1])) > 0.2:
            clusters.append([coordinate])
        else:
            clusters[-1].append(coordinate)
    needed = expected_segments + 1
    if len(clusters) < needed:
        raise PdfHybridCompactionError("pdf_hybrid_compaction_grid_boundaries_incomplete")
    if len(clusters) > needed:
        clusters = sorted(
            sorted(clusters, key=lambda values: (-len(values), median(values)))[:needed],
            key=median,
        )
    boundaries = [round(float(median(values)), 6) for values in clusters]
    if any(right <= left for left, right in zip(boundaries, boundaries[1:])):
        raise PdfHybridCompactionError("pdf_hybrid_compaction_grid_boundaries_invalid")
    return [
        {"ordinal": index, "start": boundaries[index - 1], "end": boundaries[index]}
        for index in range(1, needed)
    ]


def _select_cell(word_bbox: list[float], cells: list[dict[str, Any]]) -> dict[str, Any]:
    center = _center(word_bbox)
    containing = [item for item in cells if _point_inside(center, item["bbox"])]
    if containing:
        return min(containing, key=lambda item: _area(item["bbox"]))
    return min(
        cells,
        key=lambda item: (
            math.dist(center, _center(item["bbox"])),
            item["row"],
            item["column"],
        ),
    )


def _dense_id(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    result = ""
    current = value
    while current:
        current, remainder = divmod(current, len(alphabet))
        result = alphabet[remainder] + result
    return result


def _mechanical_class(value: str) -> str:
    text = value.strip()
    if re.fullmatch(r"[+\-]?[\d\s]+(?:[.,]\d+)?", text):
        return "n"
    if re.fullmatch(r"\d{1,4}[./-]\d{1,2}(?:[./-]\d{1,4})?", text):
        return "d"
    if re.fullmatch(r"[A-ZА-Я]{3}", text):
        return "c"
    if re.fullmatch(r"[^\w\s]+", text):
        return "s"
    return "t"


def _word_order(item: dict[str, Any]) -> tuple[int, int, str]:
    return (
        int(item.get("geometry_reading_order") or 0),
        int(item.get("parser_ordinal") or 0),
        str(item.get("word_ref") or ""),
    )


def _bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    result = [float(item) for item in value]
    if result[2] <= result[0] or result[3] <= result[1]:
        return None
    return result


def _bbox_union(values: list[list[float]]) -> list[float]:
    return [
        min(item[0] for item in values),
        min(item[1] for item in values),
        max(item[2] for item in values),
        max(item[3] for item in values),
    ]


def _normalized_bbox(value: list[float], scope: list[float]) -> list[float]:
    width = scope[2] - scope[0]
    height = scope[3] - scope[1]
    return [
        round((value[0] - scope[0]) / width, 4),
        round((value[1] - scope[1]) / height, 4),
        round((value[2] - scope[0]) / width, 4),
        round((value[3] - scope[1]) / height, 4),
    ]


def _center(value: list[float]) -> tuple[float, float]:
    return ((value[0] + value[2]) / 2, (value[1] + value[3]) / 2)


def _point_inside(point: tuple[float, float], value: list[float]) -> bool:
    return value[0] - 0.5 <= point[0] <= value[2] + 0.5 and value[1] - 0.5 <= point[1] <= value[3] + 0.5


def _area(value: list[float]) -> float:
    return max(0.0, value[2] - value[0]) * max(0.0, value[3] - value[1])


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []
