from __future__ import annotations

import copy
import hashlib
import json
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .source_provenance import NormalizedSliceProvenanceFactory


PDF_LAYOUT_UNIT_POLICY_VERSION = "pdf_layout_unit_partition_policy_v0"
PDF_LAYOUT_UNIT_COVERAGE_SCHEMA_VERSION = "pdf_layout_unit_coverage_v0"
PDF_LAYOUT_DOCUMENT_COVERAGE_SCHEMA_VERSION = "pdf_layout_document_coverage_v0"


@dataclass(frozen=True)
class PdfLayoutUnitConfig:
    max_lines_per_cluster: int = 24
    max_words_per_cluster: int = 400
    max_characters_per_cluster: int = 6_000
    max_words_per_table_candidate_unit: int = 1_000
    max_units_per_document: int = 5_000

    @property
    def config_ref(self) -> str:
        return "pdflayoutunitcfg_" + stable_digest(
            [
                PDF_LAYOUT_UNIT_POLICY_VERSION,
                self.max_lines_per_cluster,
                self.max_words_per_cluster,
                self.max_characters_per_cluster,
                self.max_words_per_table_candidate_unit,
                self.max_units_per_document,
            ],
            length=24,
        )


@dataclass(frozen=True)
class PdfLayoutBuildResult:
    pages: list[dict[str, Any]]
    char_inventory: list[dict[str, Any]]
    word_inventory: list[dict[str, Any]]
    line_inventory: list[dict[str, Any]]
    block_inventory: list[dict[str, Any]]
    bbox_inventory: list[dict[str, Any]]
    vector_line_inventory: list[dict[str, Any]]
    rect_inventory: list[dict[str, Any]]
    table_candidate_inventory: list[dict[str, Any]]
    units: list[dict[str, Any]]
    source_value_refs: list[str]
    source_value_index: list[dict[str, Any]]
    layout_projection_status: str
    layout_reason_codes: list[str]
    table_candidate_status: str
    semantic_reconstruction_status: str
    coverage: dict[str, Any]
    diagnostics: dict[str, Any]


class PdfLayoutUnitBuilder:
    def __init__(self, config: PdfLayoutUnitConfig | None = None) -> None:
        self.config = config or PdfLayoutUnitConfig()
        self.provenance = NormalizedSliceProvenanceFactory().create()

    def build(
        self,
        *,
        normalization_run_id: str,
        document_id: str,
        profile_id: str,
        source_checksum_sha256: str,
        source_checksum_ref: str,
        payload_ref: str,
        layout_parser_ref: str,
        layout_parser_label: str,
        layout_parser_config_ref: str,
        layout_pages: list[dict[str, Any]],
        page_inventory: list[dict[str, Any]],
    ) -> PdfLayoutBuildResult:
        reasons: list[str] = []
        page_by_number = {
            int(page.get("page_number") or 0): page for page in layout_pages
        }
        if len(layout_pages) != len(page_inventory):
            reasons.append("pdf_layout_page_count_reconciliation_failed")

        chars: list[dict[str, Any]] = []
        words: list[dict[str, Any]] = []
        lines: list[dict[str, Any]] = []
        blocks: list[dict[str, Any]] = []
        bboxes: list[dict[str, Any]] = []
        vector_lines: list[dict[str, Any]] = []
        rects: list[dict[str, Any]] = []
        candidates: list[dict[str, Any]] = []
        source_value_refs: list[str] = []
        source_value_index: list[dict[str, Any]] = []

        for page in page_inventory:
            page_number = int(page.get("page_number") or 0)
            raw_layout = page_by_number.get(page_number)
            if raw_layout is None:
                page["layout_projection_status"] = "partial"
                page["layout_reason_codes"] = ["pdf_layout_page_missing"]
                page["table_candidate_status"] = "blocked"
                reasons.append("pdf_layout_page_missing")
                continue
            materialized = self._materialize_page(
                page=page,
                raw_layout=raw_layout,
                source_checksum_ref=source_checksum_ref,
                layout_parser_ref=layout_parser_ref,
            )
            chars.extend(materialized["chars"])
            words.extend(materialized["words"])
            lines.extend(materialized["lines"])
            blocks.extend(materialized["blocks"])
            bboxes.extend(materialized["bboxes"])
            vector_lines.extend(materialized["vector_lines"])
            rects.extend(materialized["rects"])
            candidates.extend(materialized["candidates"])
            source_value_refs.extend(materialized["source_value_refs"])
            source_value_index.extend(materialized["source_value_index"])
            reasons.extend(page.get("layout_reason_codes") or [])
            raw_layout.clear()

        page_layout_complete = all(
            page.get("layout_projection_status") == "complete"
            for page in page_inventory
        )
        page_text_complete = all(
            page.get("page_projection_status") == "complete"
            for page in page_inventory
        )
        units: list[dict[str, Any]] = []
        unit_reasons: list[str] = []
        if page_layout_complete and page_text_complete:
            units, unit_reasons = self._build_units(
                normalization_run_id=normalization_run_id,
                document_id=document_id,
                profile_id=profile_id,
                source_checksum_sha256=source_checksum_sha256,
                payload_ref=payload_ref,
                layout_parser_ref=layout_parser_ref,
                layout_parser_label=layout_parser_label,
                layout_parser_config_ref=layout_parser_config_ref,
                pages=page_inventory,
            )
            reasons.extend(unit_reasons)

        selected_refs = [
            str(item.get("word_ref") or "") for item in words
        ] + [str(item.get("line_ref") or "") for item in lines]
        selected_refs = [ref for ref in selected_refs if ref]
        ownership = [
            ref
            for unit in units
            for ref in _strings(
                _object(unit.get("pdf_layout_coverage")).get(
                    "accounted_source_refs"
                )
            )
        ]
        duplicate_owned = sorted(
            ref for ref, count in Counter(ownership).items() if count > 1
        )
        unaccounted = sorted(set(selected_refs) - set(ownership))
        unexpected = sorted(set(ownership) - set(selected_refs))
        layout_complete = (
            page_layout_complete
            and page_text_complete
            and bool(units or not selected_refs)
            and not unit_reasons
            and not duplicate_owned
            and not unaccounted
            and not unexpected
        )
        if page_layout_complete and selected_refs and not units:
            reasons.append("pdf_layout_complete_without_units")
        if duplicate_owned:
            reasons.append("pdf_layout_duplicate_coverage_ownership")
        if unaccounted:
            reasons.append("pdf_layout_unaccounted_refs")
        if unexpected:
            reasons.append("pdf_layout_unexpected_accounted_refs")
        reasons = sorted(set(reasons))
        layout_status = "complete" if layout_complete else "partial"
        candidate_units = [
            unit
            for unit in units
            if unit.get("pdf_unit_type") == "pdf_table_candidate_unit"
        ]
        table_status = (
            "candidate"
            if candidate_units
            else (
                "blocked"
                if any(page.get("table_candidate_status") == "blocked" for page in page_inventory)
                else "not_claimed"
            )
        )
        coverage = {
            "schema_version": PDF_LAYOUT_DOCUMENT_COVERAGE_SCHEMA_VERSION,
            "coverage_ref": "pdflayoutcoverage_"
            + stable_digest(
                [
                    source_checksum_ref,
                    layout_parser_ref,
                    self.config.config_ref,
                    *selected_refs,
                    *ownership,
                ],
                length=24,
            ),
            "selected_source_refs": selected_refs,
            "accounted_source_refs": ownership,
            "selected_total": len(selected_refs),
            "accounted_total": len(ownership),
            "duplicate_accounted_refs": duplicate_owned,
            "unaccounted_refs": unaccounted,
            "unexpected_accounted_refs": unexpected,
            "all_selected_refs_accounted": (
                len(selected_refs) == len(ownership)
                and not duplicate_owned
                and not unaccounted
                and not unexpected
            ),
            "unit_refs": [str(unit.get("unit_ref") or "") for unit in units],
            "line_cluster_unit_refs": [
                str(unit.get("unit_ref") or "")
                for unit in units
                if unit.get("pdf_unit_type") == "pdf_line_cluster_unit"
            ],
            "table_candidate_unit_refs": [
                str(unit.get("unit_ref") or "") for unit in candidate_units
            ],
            "blank_page_refs": [
                str(page.get("page_ref") or "")
                for page in page_inventory
                if page.get("page_content_kind") == "blank"
            ],
        }
        for page in page_inventory:
            page.pop("_layout_words", None)
            page.pop("_layout_lines", None)
            page.pop("_layout_candidates", None)
        for item in [
            *chars,
            *words,
            *lines,
            *blocks,
            *vector_lines,
            *rects,
            *candidates,
        ]:
            item.pop("bbox", None)
        for candidate in candidates:
            for cell in _dicts(candidate.get("cell_inventory")):
                cell.pop("bbox", None)
        return PdfLayoutBuildResult(
            pages=page_inventory,
            char_inventory=chars,
            word_inventory=words,
            line_inventory=lines,
            block_inventory=blocks,
            bbox_inventory=bboxes,
            vector_line_inventory=vector_lines,
            rect_inventory=rects,
            table_candidate_inventory=candidates,
            units=units if layout_complete else [],
            source_value_refs=source_value_refs,
            source_value_index=source_value_index,
            layout_projection_status=layout_status,
            layout_reason_codes=reasons,
            table_candidate_status=table_status,
            semantic_reconstruction_status=(
                "candidate" if table_status == "candidate" else "not_claimed"
            ),
            coverage=coverage,
            diagnostics={
                "chars_total": len(chars),
                "words_total": len(words),
                "lines_total": len(lines),
                "blocks_total": len(blocks),
                "table_candidates_total": len(candidates),
                "line_cluster_units_total": sum(
                    1
                    for unit in units
                    if unit.get("pdf_unit_type") == "pdf_line_cluster_unit"
                ),
                "table_candidate_units_total": len(candidate_units),
                "unit_config_ref": self.config.config_ref,
            },
        )

    def _materialize_page(
        self,
        *,
        page: dict[str, Any],
        raw_layout: dict[str, Any],
        source_checksum_ref: str,
        layout_parser_ref: str,
    ) -> dict[str, Any]:
        page_ref = str(page.get("page_ref") or "")
        page_text = str(page.get("text") or "")
        text_match_status = _page_text_matcher(page_text)
        reasons = list(raw_layout.get("layout_reason_codes") or [])
        table_reasons = list(raw_layout.get("table_reason_codes") or [])
        bbox_by_value: dict[tuple[float, ...], dict[str, Any]] = {}

        def bbox_ref(value: Any) -> str:
            bbox = _bbox(value)
            key = tuple(bbox)
            if key not in bbox_by_value:
                ref = "pdfbbox_" + stable_digest(
                    [page_ref, layout_parser_ref, *bbox], length=24
                )
                bbox_by_value[key] = {
                    "bbox_ref": ref,
                    "page_ref": page_ref,
                    "coordinate_space": "pdfplumber_top_origin_points",
                    "bbox": bbox,
                }
            return str(bbox_by_value[key]["bbox_ref"])

        chars: list[dict[str, Any]] = []
        char_by_ordinal: dict[int, str] = {}
        for raw in _dicts(raw_layout.get("char_inventory")):
            ordinal = int(raw.get("parser_ordinal") or 0)
            text_checksum = _checksum_ref("pdfchartxtchk", str(raw.get("text") or ""))
            char_ref = "pdfchar_" + stable_digest(
                [source_checksum_ref, page_ref, layout_parser_ref, ordinal, text_checksum],
                length=24,
            )
            item = {
                **copy.deepcopy(raw),
                "char_ref": char_ref,
                "page_ref": page_ref,
                "bbox_ref": bbox_ref(raw.get("bbox")),
                "text_checksum_ref": text_checksum,
            }
            duplicate_ordinal = raw.get("duplicate_of_parser_ordinal")
            item["duplicate_of_char_ref"] = (
                char_by_ordinal.get(int(duplicate_ordinal))
                if duplicate_ordinal is not None
                else None
            )
            char_by_ordinal[ordinal] = char_ref
            chars.append(item)

        words: list[dict[str, Any]] = []
        word_by_ordinal: dict[int, dict[str, Any]] = {}
        source_value_refs: list[str] = []
        source_value_index: list[dict[str, Any]] = []
        for geometry_ordinal, raw in enumerate(
            sorted(_dicts(raw_layout.get("word_inventory")), key=_geometry_key), 1
        ):
            ordinal = int(raw.get("parser_ordinal") or 0)
            text = str(raw.get("text") or "")
            text_checksum = _checksum_ref("pdfwordtxtchk", text)
            word_ref = "pdfword_" + stable_digest(
                [source_checksum_ref, page_ref, layout_parser_ref, ordinal, text_checksum],
                length=24,
            )
            source_value_ref = "srcval_" + stable_digest(
                [word_ref, text_checksum], length=24
            )
            match_status = text_match_status(text)
            if text and match_status == "mismatch":
                reasons.append("pdf_layout_word_page_text_mismatch")
            item = {
                **copy.deepcopy(raw),
                "word_ref": word_ref,
                "page_ref": page_ref,
                "bbox_ref": bbox_ref(raw.get("bbox")),
                "geometry_reading_order": geometry_ordinal,
                "text_checksum_ref": text_checksum,
                "source_value_ref": source_value_ref,
                "canonical_page_text_match_status": match_status,
            }
            words.append(item)
            word_by_ordinal[ordinal] = item
            source_value_refs.append(source_value_ref)
            source_value_index.append(
                {
                    "source_value_ref": source_value_ref,
                    "source_object_ref": word_ref,
                    "value_path": {
                        "kind": "pdf_layout_word_text",
                        "word_ref": word_ref,
                    },
                    "value_checksum_ref": _checksum_ref("valuechk", text),
                }
            )

        lines: list[dict[str, Any]] = []
        line_by_ordinal: dict[int, dict[str, Any]] = {}
        for raw in _dicts(raw_layout.get("line_inventory")):
            ordinal = int(raw.get("parser_ordinal") or 0)
            word_refs = [
                str(word_by_ordinal[item]["word_ref"])
                for item in [int(value) for value in raw.get("word_parser_ordinals") or []]
                if item in word_by_ordinal
            ]
            text = str(raw.get("text") or "")
            text_checksum = _checksum_ref("pdflinetxtchk", text)
            line_ref = "pdfline_" + stable_digest(
                [source_checksum_ref, page_ref, layout_parser_ref, ordinal, text_checksum],
                length=24,
            )
            source_value_ref = "srcval_" + stable_digest(
                [line_ref, text_checksum], length=24
            )
            match_status = text_match_status(text)
            contributing_words = [
                word_by_ordinal[item]
                for item in [int(value) for value in raw.get("word_parser_ordinals") or []]
                if item in word_by_ordinal
            ]
            if match_status == "mismatch" and contributing_words and all(
                item.get("canonical_page_text_match_status") != "mismatch"
                for item in contributing_words
            ):
                match_status = "resolved_via_word_refs"
            if text and match_status == "mismatch":
                reasons.append("pdf_layout_line_page_text_mismatch")
            item = {
                **copy.deepcopy(raw),
                "line_ref": line_ref,
                "page_ref": page_ref,
                "bbox_ref": bbox_ref(raw.get("bbox")),
                "word_refs": word_refs,
                "text_checksum_ref": text_checksum,
                "source_value_ref": source_value_ref,
                "canonical_page_text_match_status": match_status,
            }
            lines.append(item)
            line_by_ordinal[ordinal] = item
            source_value_refs.append(source_value_ref)
            source_value_index.append(
                {
                    "source_value_ref": source_value_ref,
                    "source_object_ref": line_ref,
                    "value_path": {
                        "kind": "pdf_layout_line_text",
                        "line_ref": line_ref,
                    },
                    "value_checksum_ref": _checksum_ref("valuechk", text),
                }
            )

        blocks: list[dict[str, Any]] = []
        for raw in _dicts(raw_layout.get("block_inventory")):
            ordinal = int(raw.get("parser_ordinal") or 0)
            line_refs = [
                str(line_by_ordinal[item]["line_ref"])
                for item in [int(value) for value in raw.get("line_parser_ordinals") or []]
                if item in line_by_ordinal
            ]
            block_ref = "pdfblock_" + stable_digest(
                [source_checksum_ref, page_ref, layout_parser_ref, ordinal, *line_refs],
                length=24,
            )
            blocks.append(
                {
                    **copy.deepcopy(raw),
                    "block_ref": block_ref,
                    "page_ref": page_ref,
                    "bbox_ref": bbox_ref(raw.get("bbox")),
                    "line_refs": line_refs,
                }
            )

        vector_lines = self._materialize_vectors(
            raw_layout.get("vector_line_inventory"),
            prefix="pdfvectorline",
            page_ref=page_ref,
            source_checksum_ref=source_checksum_ref,
            layout_parser_ref=layout_parser_ref,
            bbox_ref=bbox_ref,
        )
        rects = self._materialize_vectors(
            raw_layout.get("rect_inventory"),
            prefix="pdfrect",
            page_ref=page_ref,
            source_checksum_ref=source_checksum_ref,
            layout_parser_ref=layout_parser_ref,
            bbox_ref=bbox_ref,
        )

        candidates: list[dict[str, Any]] = []
        for candidate_ordinal, raw in enumerate(
            _dicts(raw_layout.get("table_candidate_inventory")), 1
        ):
            contributing_words = [
                word_by_ordinal[item]
                for item in [
                    int(value)
                    for value in raw.get("contributing_word_parser_ordinals") or []
                ]
                if item in word_by_ordinal
            ]
            contributing_word_refs = [
                str(item.get("word_ref") or "") for item in contributing_words
            ]
            overlapping_lines = [
                line for line in lines if _bbox_overlap(line.get("bbox"), raw.get("bbox"))
            ]
            candidate_word_set = set(contributing_word_refs)
            if any(
                set(_strings(line.get("word_refs"))) - candidate_word_set
                and set(_strings(line.get("word_refs"))) & candidate_word_set
                for line in overlapping_lines
            ):
                table_reasons.append(
                    "pdf_table_candidate_cross_line_partial_rejected"
                )
                continue
            table_ref = "pdftablecand_" + stable_digest(
                [
                    source_checksum_ref,
                    page_ref,
                    layout_parser_ref,
                    raw.get("table_strategy_ref"),
                    candidate_ordinal,
                    *contributing_word_refs,
                ],
                length=24,
            )
            row_inventory, cell_inventory = _materialize_candidate_cells(
                table_ref=table_ref,
                page_ref=page_ref,
                raw_cells=_dicts(raw.get("cell_inventory")),
                word_by_ordinal=word_by_ordinal,
                bbox_ref=bbox_ref,
            )
            candidate = {
                **copy.deepcopy(raw),
                "parser_ordinal": candidate_ordinal,
                "table_candidate_ref": table_ref,
                "page_ref": page_ref,
                "bbox_ref": bbox_ref(raw.get("bbox")),
                "row_refs": [str(item["row_ref"]) for item in row_inventory],
                "cell_refs": [str(item["cell_ref"]) for item in cell_inventory],
                "row_inventory": row_inventory,
                "cell_inventory": cell_inventory,
                "contributing_word_refs": contributing_word_refs,
                "contributing_source_value_refs": [
                    str(item.get("source_value_ref") or "") for item in contributing_words
                ],
                "fallback_text_refs": [
                    str(line.get("line_ref") or "") for line in overlapping_lines
                ],
                "fallback_source_value_refs": [
                    str(line.get("source_value_ref") or "") for line in overlapping_lines
                ],
                "confidence_bucket": (
                    "high"
                    if float(raw.get("geometry_confidence") or 0.0) >= 0.9
                    else "medium"
                ),
                "semantic_table_truth_claimed": False,
            }
            candidates.append(candidate)

        layout_status = str(raw_layout.get("layout_projection_status") or "partial")
        if any(reason.endswith("_mismatch") for reason in reasons):
            layout_status = "partial"
        page.update(
            {
                "layout_projection_status": layout_status,
                "layout_reason_codes": sorted(set(reasons)),
                "layout_confidence": raw_layout.get("layout_confidence"),
                "table_candidate_status": (
                    "candidate"
                    if candidates
                    else (
                        "blocked"
                        if raw_layout.get("table_candidate_status") == "blocked"
                        else "not_claimed"
                    )
                ),
                "table_reason_codes": sorted(set(table_reasons)),
                "layout_char_refs": [str(item["char_ref"]) for item in chars],
                "layout_word_refs": [str(item["word_ref"]) for item in words],
                "layout_line_refs": [str(item["line_ref"]) for item in lines],
                "layout_block_refs": [str(item["block_ref"]) for item in blocks],
                "table_candidate_refs": [
                    str(item["table_candidate_ref"]) for item in candidates
                ],
                "parser_order_word_refs": [
                    str(item["word_ref"])
                    for item in sorted(words, key=lambda value: int(value.get("parser_ordinal") or 0))
                ],
                "geometry_reading_order_refs": [
                    str(item["word_ref"])
                    for item in sorted(words, key=lambda value: int(value.get("geometry_reading_order") or 0))
                ],
                "duplicate_chars_total": int(
                    raw_layout.get("duplicate_chars_total") or 0
                ),
                "rotated_chars_total": int(raw_layout.get("rotated_chars_total") or 0),
                "hidden_text_diagnostics_status": raw_layout.get(
                    "hidden_text_diagnostics_status", "not_available"
                ),
                "layout_elapsed_milliseconds": raw_layout.get("elapsed_milliseconds"),
                "layout_page_width": raw_layout.get("width"),
                "layout_page_height": raw_layout.get("height"),
                "layout_page_rotation": raw_layout.get("rotation"),
                "_layout_words": words,
                "_layout_lines": lines,
                "_layout_candidates": candidates,
            }
        )
        return {
            "chars": chars,
            "words": words,
            "lines": lines,
            "blocks": blocks,
            "bboxes": list(bbox_by_value.values()),
            "vector_lines": vector_lines,
            "rects": rects,
            "candidates": candidates,
            "source_value_refs": source_value_refs,
            "source_value_index": source_value_index,
        }

    def _materialize_vectors(
        self,
        raw_items: Any,
        *,
        prefix: str,
        page_ref: str,
        source_checksum_ref: str,
        layout_parser_ref: str,
        bbox_ref,
    ) -> list[dict[str, Any]]:
        result = []
        for raw in _dicts(raw_items):
            ordinal = int(raw.get("parser_ordinal") or 0)
            ref = prefix + "_" + stable_digest(
                [source_checksum_ref, page_ref, layout_parser_ref, ordinal, raw.get("bbox")],
                length=24,
            )
            result.append(
                {
                    **copy.deepcopy(raw),
                    f"{prefix}_ref": ref,
                    "object_ref": ref,
                    "page_ref": page_ref,
                    "bbox_ref": bbox_ref(raw.get("bbox")),
                }
            )
        return result

    def _build_units(
        self,
        *,
        normalization_run_id: str,
        document_id: str,
        profile_id: str,
        source_checksum_sha256: str,
        payload_ref: str,
        layout_parser_ref: str,
        layout_parser_label: str,
        layout_parser_config_ref: str,
        pages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        units: list[dict[str, Any]] = []
        reasons: list[str] = []
        for page in pages:
            page_units, page_reasons = self._build_page_units(
                normalization_run_id=normalization_run_id,
                document_id=document_id,
                profile_id=profile_id,
                source_checksum_sha256=source_checksum_sha256,
                payload_ref=payload_ref,
                layout_parser_ref=layout_parser_ref,
                layout_parser_label=layout_parser_label,
                layout_parser_config_ref=layout_parser_config_ref,
                page=page,
            )
            units.extend(page_units)
            reasons.extend(page_reasons)
        if len(units) > self.config.max_units_per_document:
            return [], ["pdf_layout_unit_document_budget_exceeded"]
        unit_refs = [str(unit.get("unit_ref") or "") for unit in units]
        for index, unit in enumerate(units):
            unit["remaining_unit_refs"] = unit_refs[index + 1 :]
            unit["next_unit_refs"] = unit_refs[index + 1 : index + 2]
            unit["sibling_unit_refs"] = [
                ref for ref in unit_refs if ref != unit.get("unit_ref")
            ]
            unit["deferred_unit_refs"] = []
        return units, sorted(set(reasons))

    def _build_page_units(self, **kwargs: Any) -> tuple[list[dict[str, Any]], list[str]]:
        page = kwargs["page"]
        words = _dicts(page.get("_layout_words"))
        lines = _dicts(page.get("_layout_lines"))
        candidates = _dicts(page.get("_layout_candidates"))
        if not words and not lines:
            return [], []
        table_units: list[dict[str, Any]] = []
        accepted_candidate_word_refs: set[str] = set()
        reasons: list[str] = []
        for candidate in candidates:
            word_refs = _strings(candidate.get("contributing_word_refs"))
            if len(word_refs) > self.config.max_words_per_table_candidate_unit:
                reasons.append("pdf_table_candidate_unit_word_budget_exceeded")
                continue
            candidate_lines = [
                line
                for line in lines
                if set(_strings(line.get("word_refs")))
                and set(_strings(line.get("word_refs"))) <= set(word_refs)
            ]
            if not candidate_lines:
                reasons.append("pdf_table_candidate_fallback_lines_missing")
                continue
            table_units.append(
                self._mint_unit(
                    **kwargs,
                    unit_type="pdf_table_candidate_unit",
                    selected_lines=candidate_lines,
                    owned_word_refs=word_refs,
                    owned_line_refs=[str(line.get("line_ref") or "") for line in candidate_lines],
                    candidate=candidate,
                )
            )
            accepted_candidate_word_refs.update(word_refs)

        remaining_lines = [
            line
            for line in lines
            if not set(_strings(line.get("word_refs"))) <= accepted_candidate_word_refs
        ]
        clusters: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        current_words = 0
        current_chars = 0
        for line in remaining_lines:
            line_words = [
                ref
                for ref in _strings(line.get("word_refs"))
                if ref not in accepted_candidate_word_refs
            ]
            if not line_words:
                continue
            line_chars = len(str(line.get("text") or ""))
            if (
                len(line_words) > self.config.max_words_per_cluster
                or line_chars > self.config.max_characters_per_cluster
            ):
                return [], ["pdf_line_cluster_single_line_budget_exceeded"]
            would_overflow = current and (
                len(current) + 1 > self.config.max_lines_per_cluster
                or current_words + len(line_words) > self.config.max_words_per_cluster
                or current_chars + line_chars + 1
                > self.config.max_characters_per_cluster
            )
            if would_overflow:
                clusters.append(current)
                current = []
                current_words = 0
                current_chars = 0
            current.append(line)
            current_words += len(line_words)
            current_chars += line_chars + (1 if current_chars else 0)
        if current:
            clusters.append(current)

        line_units = []
        for cluster in clusters:
            owned_words = [
                ref
                for line in cluster
                for ref in _strings(line.get("word_refs"))
                if ref not in accepted_candidate_word_refs
            ]
            line_units.append(
                self._mint_unit(
                    **kwargs,
                    unit_type="pdf_line_cluster_unit",
                    selected_lines=cluster,
                    owned_word_refs=owned_words,
                    owned_line_refs=[str(line.get("line_ref") or "") for line in cluster],
                    candidate=None,
                )
            )
        return [*table_units, *line_units], reasons

    def _mint_unit(
        self,
        *,
        normalization_run_id: str,
        document_id: str,
        profile_id: str,
        source_checksum_sha256: str,
        payload_ref: str,
        layout_parser_ref: str,
        layout_parser_label: str,
        layout_parser_config_ref: str,
        page: dict[str, Any],
        unit_type: str,
        selected_lines: list[dict[str, Any]],
        owned_word_refs: list[str],
        owned_line_refs: list[str],
        candidate: dict[str, Any] | None,
    ) -> dict[str, Any]:
        text, supplemental_index = _unit_text_and_source_values(
            selected_lines=selected_lines,
            owned_word_refs=set(owned_word_refs),
            owned_line_refs=set(owned_line_refs),
            page_words=_dicts(page.get("_layout_words")),
        )
        owned_refs = [*owned_word_refs, *owned_line_refs]
        page_ref = str(page.get("page_ref") or "")
        slice_id = "fullsrc_" + stable_digest(
            [payload_ref, unit_type, page_ref, *owned_refs], length=24
        )
        source_location = {
            "kind": (
                "pdf_layout_table_candidate"
                if unit_type == "pdf_table_candidate_unit"
                else "pdf_layout_line_cluster"
            ),
            "page": int(page.get("page_number") or 0),
            "page_start": int(page.get("page_number") or 0),
            "page_end": int(page.get("page_number") or 0),
            "line_start": min(
                int(line.get("geometry_reading_order") or 0)
                for line in selected_lines
            ),
            "line_end": max(
                int(line.get("geometry_reading_order") or 0)
                for line in selected_lines
            ),
            "bbox_ref": candidate.get("bbox_ref") if candidate else None,
        }
        private_slice = {
            "slice_id": slice_id,
            "document_id": document_id,
            "profile_id": profile_id,
            "slice_type": "text_excerpt",
            "source_location": source_location,
            "location": copy.deepcopy(source_location),
            "bounded": True,
            "truncated": False,
            "parser": layout_parser_label,
            "created_for_gate": "gate1_pdf_layout_slice2",
            "characters_in_slice": len(text),
            "chars_count": len(text),
            "text": text,
        }
        unit = self.provenance.enrich_slice(
            normalization_run_id=normalization_run_id,
            document_id=document_id,
            source_checksum_sha256=source_checksum_sha256,
            private_slice=private_slice,
        )
        unit_ref = "srcunit_" + stable_digest(
            [
                payload_ref,
                unit_type,
                unit.get("slice_payload_checksum_ref"),
                self.config.config_ref,
                *owned_refs,
            ],
            length=24,
        )
        layout_coverage = {
            "schema_version": PDF_LAYOUT_UNIT_COVERAGE_SCHEMA_VERSION,
            "coverage_ref": "pdflayoutunitcoverage_"
            + stable_digest([unit_ref, *owned_refs], length=24),
            "selected_source_refs": owned_refs,
            "accounted_source_refs": list(owned_refs),
            "owned_word_refs": list(owned_word_refs),
            "owned_line_refs": list(owned_line_refs),
            "fallback_text_refs": copy.deepcopy(
                candidate.get("fallback_text_refs") if candidate else []
            ),
            "selected_total": len(owned_refs),
            "accounted_total": len(owned_refs),
            "duplicate_accounted_refs": [],
            "unaccounted_refs": [],
            "all_selected_refs_accounted": len(owned_refs) == len(set(owned_refs)),
        }
        supplemental_refs = [
            str(item.get("source_value_ref") or "") for item in supplemental_index
        ]
        layout_checksum = _checksum_ref(
            "pdflayoutunitchk",
            {
                "unit_ref": unit_ref,
                "unit_type": unit_type,
                "layout_parser_ref": layout_parser_ref,
                "layout_parser_config_ref": layout_parser_config_ref,
                "owned_refs": owned_refs,
                "fallback_text_refs": layout_coverage["fallback_text_refs"],
                "table_candidate_ref": (
                    candidate.get("table_candidate_ref") if candidate else None
                ),
                "text_checksum_ref": _checksum_ref("pdfunittextchk", text),
            },
        )
        unit.update(
            {
                "schema_version": "private_normalized_source_unit_v0",
                "unit_ref": unit_ref,
                "unit_id": unit_ref,
                "parent_payload_ref": payload_ref,
                "payload_checksum_ref": None,
                "source_unit_checksum_ref": None,
                "pdf_layout_unit_checksum_ref": layout_checksum,
                "parser_completeness_status": "complete",
                "declared_range_complete": True,
                "coverage_scope": "complete_pdf_layout_partition",
                "source_slice_truncated": False,
                "parent_source_slice_truncated": False,
                "parent_remainder_status": "not_applicable_parent_complete",
                "remaining_unit_refs": [],
                "next_unit_refs": [],
                "sibling_unit_refs": [],
                "deferred_unit_refs": [],
                "visibility": "private_case",
                "knowledge_rag_used": False,
                "vectorization_performed": False,
                "pdf_unit_type": unit_type,
                "pdf_projection_schema_version": "pdf_text_layer_projection_v0",
                "declared_page_refs": [page_ref],
                "page_refs": [page_ref],
                "layout_word_refs": list(owned_word_refs),
                "layout_line_refs": list(owned_line_refs),
                "layout_bbox_refs": sorted(
                    {
                        str(line.get("bbox_ref") or "")
                        for line in selected_lines
                        if line.get("bbox_ref")
                    }
                ),
                "pdf_layout_coverage": layout_coverage,
                "pdf_layout_source_value_refs": supplemental_refs,
                "pdf_layout_source_value_index": supplemental_index,
                "layout_parser_ref": layout_parser_ref,
                "layout_parser_config_ref": layout_parser_config_ref,
                "layout_projection_status": "complete",
                "text_layer_projection_status": "complete",
                "visible_content_coverage_status": page.get(
                    "visible_content_coverage_status", "complete_text_only"
                ),
                "semantic_reconstruction_status": (
                    "candidate" if candidate else "not_claimed"
                ),
                "table_reconstruction_status": (
                    "candidate" if candidate else "not_claimed"
                ),
                "table_candidate_ref": (
                    candidate.get("table_candidate_ref") if candidate else None
                ),
                "table_strategy_ref": (
                    candidate.get("table_strategy_ref") if candidate else None
                ),
                "geometry_confidence": (
                    candidate.get("geometry_confidence") if candidate else None
                ),
                "confidence_bucket": (
                    candidate.get("confidence_bucket") if candidate else None
                ),
                "table_bbox_ref": candidate.get("bbox_ref") if candidate else None,
                "table_row_refs": copy.deepcopy(
                    candidate.get("row_refs") if candidate else []
                ),
                "table_cell_refs": copy.deepcopy(
                    candidate.get("cell_refs") if candidate else []
                ),
                "table_contributing_word_refs": copy.deepcopy(
                    candidate.get("contributing_word_refs") if candidate else []
                ),
                "table_fallback_text_refs": copy.deepcopy(
                    candidate.get("fallback_text_refs") if candidate else []
                ),
                "table_fallback_source_value_refs": copy.deepcopy(
                    candidate.get("fallback_source_value_refs") if candidate else []
                ),
                "table_reconstruction_reason_codes": copy.deepcopy(
                    candidate.get("reconstruction_reason_codes") if candidate else []
                ),
                "semantic_table_truth_claimed": False,
                "ocr_vlm_used": False,
                "page_rendering_used_for_extraction": False,
            }
        )
        return unit


def resolve_pdf_layout_unit_source_value(
    unit: dict[str, Any], source_value_ref: str
) -> str:
    return _PdfLayoutUnitSourceValueResolver(unit).resolve(source_value_ref)


def resolve_pdf_layout_unit_source_values(
    unit: dict[str, Any], source_value_refs: list[str]
) -> dict[str, str]:
    resolver = _PdfLayoutUnitSourceValueResolver(unit)
    return {
        str(source_value_ref): resolver.resolve(str(source_value_ref))
        for source_value_ref in source_value_refs
    }


def resolve_pdf_layout_unit_source_value_results(
    unit: dict[str, Any], source_value_refs: list[str]
) -> tuple[dict[str, str], list[dict[str, str]]]:
    resolver = _PdfLayoutUnitSourceValueResolver(unit)
    resolved: dict[str, str] = {}
    errors: list[dict[str, str]] = []
    for source_value_ref in source_value_refs:
        try:
            resolved[str(source_value_ref)] = resolver.resolve(
                str(source_value_ref)
            )
        except ValueError as exc:
            errors.append(
                {"code": str(exc), "subject": str(source_value_ref)}
            )
    return resolved, errors


class _PdfLayoutUnitSourceValueResolver:
    def __init__(self, unit: dict[str, Any]) -> None:
        self.text = str(unit.get("text") or "")
        self.entries: dict[str, list[dict[str, Any]]] = {}
        for item in _dicts(unit.get("pdf_layout_source_value_index")):
            source_value_ref = str(item.get("source_value_ref") or "")
            if source_value_ref:
                self.entries.setdefault(source_value_ref, []).append(item)

    def resolve(self, source_value_ref: str) -> str:
        matches = self.entries.get(str(source_value_ref), [])
        if len(matches) != 1:
            raise ValueError("pdf_layout_unit_source_value_ref_not_unique_or_missing")
        path = _object(matches[0].get("value_path"))
        if path.get("kind") != "pdf_unit_text_span":
            raise ValueError("pdf_layout_unit_source_value_path_kind_invalid")
        start = int(path.get("character_start") or 0)
        end = int(path.get("character_end") or 0)
        if start < 0 or end < start or end > len(self.text):
            raise ValueError("pdf_layout_unit_source_value_path_invalid")
        value = self.text[start:end]
        if matches[0].get("value_checksum_ref") != _checksum_ref("valuechk", value):
            raise ValueError("pdf_layout_unit_source_value_checksum_mismatch")
        return value


def _unit_text_and_source_values(
    *,
    selected_lines: list[dict[str, Any]],
    owned_word_refs: set[str],
    owned_line_refs: set[str],
    page_words: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    words_by_ref = {
        str(item.get("word_ref") or ""): item for item in page_words
    }
    chunks: list[str] = []
    index: list[dict[str, Any]] = []
    cursor = 0
    for line_index, line in enumerate(selected_lines):
        if line_index:
            chunks.append("\n")
            cursor += 1
        line_start = cursor
        selected_words = [
            words_by_ref[ref]
            for ref in _strings(line.get("word_refs"))
            if ref in owned_word_refs and ref in words_by_ref
        ]
        for word_index, word in enumerate(selected_words):
            if word_index:
                chunks.append(" ")
                cursor += 1
            value = str(word.get("text") or "")
            start = cursor
            chunks.append(value)
            cursor += len(value)
            index.append(
                {
                    "source_value_ref": word.get("source_value_ref"),
                    "source_object_ref": word.get("word_ref"),
                    "value_path": {
                        "kind": "pdf_unit_text_span",
                        "character_start": start,
                        "character_end": cursor,
                    },
                    "value_checksum_ref": _checksum_ref("valuechk", value),
                }
            )
        line_ref = str(line.get("line_ref") or "")
        if line_ref in owned_line_refs:
            value = "".join(chunks)[line_start:cursor]
            index.append(
                {
                    "source_value_ref": line.get("source_value_ref"),
                    "source_object_ref": line_ref,
                    "value_path": {
                        "kind": "pdf_unit_text_span",
                        "character_start": line_start,
                        "character_end": cursor,
                    },
                    "value_checksum_ref": _checksum_ref("valuechk", value),
                }
            )
    return "".join(chunks), index


def _materialize_candidate_cells(
    *,
    table_ref: str,
    page_ref: str,
    raw_cells: list[dict[str, Any]],
    word_by_ordinal: dict[int, dict[str, Any]],
    bbox_ref,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(raw_cells, key=_geometry_key)
    row_groups: list[list[dict[str, Any]]] = []
    for cell in ordered:
        top = float((_bbox(cell.get("bbox")))[1])
        target = next(
            (
                group
                for group in reversed(row_groups)
                if abs(top - float(_bbox(group[0].get("bbox"))[1])) <= 2.0
            ),
            None,
        )
        if target is None:
            row_groups.append([cell])
        else:
            target.append(cell)
    rows: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    for row_ordinal, group in enumerate(row_groups, 1):
        row_ref = "pdftablerow_" + stable_digest(
            [table_ref, row_ordinal], length=24
        )
        row_cell_refs = []
        for column_ordinal, raw in enumerate(
            sorted(group, key=lambda value: float(_bbox(value.get("bbox"))[0])), 1
        ):
            cell_ref = "pdftablecell_" + stable_digest(
                [table_ref, row_ordinal, column_ordinal, raw.get("bbox")], length=24
            )
            word_refs = [
                str(word_by_ordinal[item].get("word_ref") or "")
                for item in [
                    int(value) for value in raw.get("word_parser_ordinals") or []
                ]
                if item in word_by_ordinal
            ]
            cells.append(
                {
                    "cell_ref": cell_ref,
                    "row_ref": row_ref,
                    "page_ref": page_ref,
                    "row_ordinal": row_ordinal,
                    "column_ordinal": column_ordinal,
                    "bbox_ref": bbox_ref(raw.get("bbox")),
                    "word_refs": word_refs,
                    "semantic_role": "not_claimed",
                }
            )
            row_cell_refs.append(cell_ref)
        rows.append(
            {
                "row_ref": row_ref,
                "page_ref": page_ref,
                "row_ordinal": row_ordinal,
                "cell_refs": row_cell_refs,
                "semantic_role": "not_claimed",
            }
        )
    return rows, cells


def _page_text_matcher(page_text: str):
    normalized_page = _canonical_match_text(page_text)

    def match(candidate: str) -> str:
        if not candidate:
            return "empty"
        if candidate in page_text:
            return "exact"
        normalized_candidate = _canonical_match_text(candidate)
        if normalized_candidate and normalized_candidate in normalized_page:
            return "normalized_whitespace"
        return "mismatch"

    return match


def _canonical_match_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        character
        for character in normalized
        if not character.isspace()
        and unicodedata.category(character) not in {"Cf", "Cc"}
    )


def _geometry_key(item: dict[str, Any]) -> tuple[float, float, int]:
    bbox = _bbox(item.get("bbox"))
    return (
        float(bbox[1]),
        float(bbox[0]),
        int(item.get("parser_ordinal") or item.get("cell_ordinal") or 0),
    )


def _bbox(value: Any) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return [0.0, 0.0, 0.0, 0.0]
    result = []
    for item in value:
        try:
            result.append(round(float(item), 4))
        except (TypeError, ValueError):
            result.append(0.0)
    return result


def _bbox_overlap(left: Any, right: Any) -> bool:
    left_bbox = _bbox(left)
    right_bbox = _bbox(right)
    return not (
        left_bbox[2] <= right_bbox[0]
        or right_bbox[2] <= left_bbox[0]
        or left_bbox[3] <= right_bbox[1]
        or right_bbox[3] <= left_bbox[1]
    )


def _checksum_ref(prefix: str, value: Any) -> str:
    material = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:24]}"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []
