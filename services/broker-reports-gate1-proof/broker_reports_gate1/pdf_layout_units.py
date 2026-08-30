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


PDF_LAYOUT_UNIT_POLICY_VERSION = "pdf_layout_unit_partition_policy_v2_exact_word_cell"
PDF_LAYOUT_UNIT_COVERAGE_SCHEMA_VERSION = "pdf_layout_unit_coverage_v0"
PDF_LAYOUT_DOCUMENT_COVERAGE_SCHEMA_VERSION = "pdf_layout_document_coverage_v0"
PDF_LAYOUT_SOURCE_CHAIN_SCHEMA_VERSION = "pdf_layout_source_chain_v0"
PDF_LAYOUT_SOURCE_CHAIN_POLICY_VERSION = "pdfplumber_exact_char_identity_v0"
_PDFPLUMBER_LIGATURE_EXPANSIONS = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
}


@dataclass(frozen=True)
class PdfLayoutUnitConfig:
    max_lines_per_cluster: int = 24
    max_words_per_cluster: int = 400
    max_characters_per_cluster: int = 6_000
    max_words_per_table_candidate_unit: int = 5_000
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
    source_chain: dict[str, Any]
    diagnostics: dict[str, Any]


class PdfLayoutUnitBuilder:
    """Build provenance-preserving PDF layout evidence, not canonical truth.

    Geometry and table candidates remain private evidence until the canonical
    assembler represents or terminally accounts them. This class must not be
    called as an alternate public PDF reader.
    """

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
        source_chain_page_receipts: list[dict[str, Any]] = []
        source_owner_binding_complete = True

        for page in page_inventory:
            page_number = int(page.get("page_number") or 0)
            raw_layout = page_by_number.get(page_number)
            if raw_layout is None:
                source_owner_binding_complete = False
                page["layout_projection_status"] = "partial"
                page["layout_reason_codes"] = ["pdf_layout_page_missing"]
                page["table_candidate_status"] = "blocked"
                page["layout_source_owner_binding_status"] = "partial"
                receipt = pdf_layout_source_chain_page_receipt(
                    page=page,
                    chars=[],
                    words=[],
                    lines=[],
                    bboxes=[],
                )
                page["layout_source_chain_receipt"] = copy.deepcopy(receipt)
                source_chain_page_receipts.append(receipt)
                reasons.append("pdf_layout_page_missing")
                continue
            materialized = self._materialize_page(
                page=page,
                raw_layout=raw_layout,
                source_checksum_ref=source_checksum_ref,
                layout_parser_ref=layout_parser_ref,
            )
            owner_binding_complete = _materialized_page_matches_raw_layout(
                raw_layout=raw_layout,
                materialized=materialized,
            )
            page["layout_source_owner_binding_status"] = (
                "complete" if owner_binding_complete else "partial"
            )
            if not owner_binding_complete:
                source_owner_binding_complete = False
                page["layout_projection_status"] = "partial"
                page["layout_reason_codes"] = sorted(
                    {
                        *page.get("layout_reason_codes", []),
                        "pdf_layout_source_owner_binding_failed",
                    }
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
            source_chain_page_receipts.append(materialized["source_chain_receipt"])
            reasons.extend(page.get("layout_reason_codes") or [])
            raw_layout.clear()

        page_layout_complete = all(
            page.get("layout_projection_status") == "complete"
            for page in page_inventory
        )
        source_chain_complete = all(
            _object(page.get("layout_source_chain_receipt")).get("status")
            == "complete"
            for page in page_inventory
        ) and source_owner_binding_complete
        units: list[dict[str, Any]] = []
        unit_reasons: list[str] = []
        if page_layout_complete and source_chain_complete:
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
            and source_chain_complete
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
            "blocked"
            if any(
                page.get("table_candidate_status") == "blocked"
                for page in page_inventory
            )
            or (bool(candidates) and not source_chain_complete)
            or (bool(candidates) and bool(unit_reasons) and not candidate_units)
            else (
                "candidate_with_rejections"
                if candidate_units
                and any(
                    page.get("table_candidate_status") == "rejected"
                    for page in page_inventory
                )
                else (
                    "rejected"
                    if any(
                        page.get("table_candidate_status") == "rejected"
                        for page in page_inventory
                    )
                    else ("candidate" if candidate_units else "none_detected")
                )
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
        source_chain = pdf_layout_source_chain_document_receipt(
            source_chain_page_receipts
        )
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
            source_chain=source_chain,
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
                "source_owner_binding_status": (
                    "complete" if source_owner_binding_complete else "partial"
                ),
                "table_terminal_counts": _table_terminal_counts(page_inventory),
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
        compatibility_reasons: list[str] = []
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
                compatibility_reasons.append("pdf_layout_word_page_text_mismatch")
            item = {
                **copy.deepcopy(raw),
                "word_ref": word_ref,
                "page_ref": page_ref,
                "bbox_ref": bbox_ref(raw.get("bbox")),
                "geometry_reading_order": geometry_ordinal,
                "text_checksum_ref": text_checksum,
                "source_value_ref": source_value_ref,
                "canonical_page_text_match_status": match_status,
                "char_refs": [
                    char_by_ordinal[item]
                    for item in [
                        int(value)
                        for value in raw.get("char_parser_ordinals") or []
                    ]
                    if item in char_by_ordinal
                ],
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

        char_owners: dict[str, list[str]] = {
            str(item.get("char_ref") or ""): [] for item in chars
        }
        for word in words:
            for char_ref in _strings(word.get("char_refs")):
                if char_ref in char_owners:
                    char_owners[char_ref].append(str(word.get("word_ref") or ""))
        for char in chars:
            char_ref = str(char.get("char_ref") or "")
            owners = char_owners.get(char_ref, [])
            char["source_chain_word_refs"] = owners
            if char.get("duplicate_of_char_ref"):
                disposition = "duplicate_overlay"
            elif not str(char.get("text") or "").strip() and not owners:
                disposition = "blank_unassigned"
            elif len(owners) == 1:
                disposition = "word_owned"
            else:
                disposition = "unresolved"
            char["source_chain_disposition"] = disposition

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
                compatibility_reasons.append("pdf_layout_line_page_text_mismatch")
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

        source_chain_receipt = pdf_layout_source_chain_page_receipt(
            page=page,
            chars=chars,
            words=words,
            lines=lines,
            bboxes=list(bbox_by_value.values()),
            unresolved_word_char_links_total=int(
                raw_layout.get("source_chain_unresolved_word_char_links_total") or 0
            ),
        )
        page["layout_source_chain_receipt"] = copy.deepcopy(source_chain_receipt)

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
            partition_reasons: list[str] = []
            contributing_ordinals = [
                int(value)
                for value in raw.get("contributing_word_parser_ordinals") or []
            ]
            if len(contributing_ordinals) != len(set(contributing_ordinals)):
                partition_reasons.append(
                    "pdf_table_word_cell_contributing_word_duplicate"
                )
            if any(ordinal not in word_by_ordinal for ordinal in contributing_ordinals):
                partition_reasons.append(
                    "pdf_table_word_cell_contributing_word_missing_or_foreign"
                )
            contributing_words = [
                word_by_ordinal[item]
                for item in contributing_ordinals
                if item in word_by_ordinal
            ]
            contributing_word_refs = [
                str(item.get("word_ref") or "") for item in contributing_words
            ]
            overlapping_lines = [
                line for line in lines if _bbox_overlap(line.get("bbox"), raw.get("bbox"))
            ]
            candidate_word_set = set(contributing_word_refs)
            fully_owned_lines = [
                line
                for line in overlapping_lines
                if set(_strings(line.get("word_refs"))) <= candidate_word_set
            ]
            if any(
                set(_strings(line.get("word_refs"))) - candidate_word_set
                and set(_strings(line.get("word_refs"))) & candidate_word_set
                for line in overlapping_lines
            ):
                table_reasons.append(
                    "pdf_table_candidate_cross_line_partial_partitioned"
                )
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
            row_inventory, cell_inventory, cell_partition_reasons = (
                _materialize_candidate_cells(
                table_ref=table_ref,
                page_ref=page_ref,
                raw_cells=_dicts(raw.get("cell_inventory")),
                rows_total=int(raw.get("rows_total") or 0),
                columns_total=int(raw.get("columns_total") or 0),
                word_by_ordinal=word_by_ordinal,
                contributing_word_ordinals=contributing_ordinals,
                char_by_ref={
                    str(item.get("char_ref") or ""): item for item in chars
                },
                bbox_ref=bbox_ref,
                )
            )
            partition_reasons.extend(cell_partition_reasons)
            partition_reasons = sorted(set(partition_reasons))
            partition_status = "complete" if not partition_reasons else "blocked"
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
                    str(line.get("line_ref") or "") for line in fully_owned_lines
                ],
                "fallback_source_value_refs": [
                    str(line.get("source_value_ref") or "") for line in fully_owned_lines
                ],
                "confidence_bucket": (
                    "high"
                    if float(raw.get("geometry_confidence") or 0.0) >= 0.9
                    else "medium"
                ),
                "semantic_table_truth_claimed": False,
                "word_cell_partition_status": partition_status,
                "word_cell_partition_reason_codes": partition_reasons,
                "table_reconstruction_status": (
                    "candidate" if partition_status == "complete" else "blocked"
                ),
            }
            candidates.append(candidate)

        if any(
            candidate.get("word_cell_partition_status") == "blocked"
            for candidate in candidates
        ):
            table_reasons.append("pdf_table_word_cell_partition_blocked")

        source_chain_status = str(source_chain_receipt.get("status") or "partial")
        if source_chain_status != "complete":
            reasons.extend(source_chain_receipt.get("reason_codes") or [])
        layout_status = (
            "complete"
            if raw_layout.get("layout_projection_status") == "complete"
            and source_chain_status == "complete"
            else "partial"
        )
        page.update(
            {
                "layout_projection_status": layout_status,
                "layout_reason_codes": sorted(set(reasons)),
                "page_text_compatibility_reason_codes": sorted(
                    set(compatibility_reasons)
                ),
                "layout_confidence": raw_layout.get("layout_confidence"),
                "table_candidate_status": (
                    "blocked"
                    if any(
                        candidate.get("word_cell_partition_status") == "blocked"
                        for candidate in candidates
                    )
                    else "candidate"
                    if candidates
                    else str(
                        raw_layout.get("table_candidate_status") or "none_detected"
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
                "table_locator_mode": bool(raw_layout.get("table_locator_mode")),
                "table_locator_status": raw_layout.get("table_locator_status"),
                "table_locator_regions_total": int(
                    raw_layout.get("table_locator_regions_total") or 0
                ),
                "table_locator_regions_accepted_total": int(
                    raw_layout.get("table_locator_regions_accepted_total") or 0
                ),
                "table_locator_regions_rejected_total": int(
                    raw_layout.get("table_locator_regions_rejected_total") or 0
                ),
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
            "source_chain_receipt": source_chain_receipt,
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
        if any(
            candidate.get("word_cell_partition_status") == "blocked"
            for candidate in candidates
        ):
            return [], ["pdf_table_word_cell_partition_blocked"]
        for candidate in candidates:
            word_refs = _strings(candidate.get("contributing_word_refs"))
            if len(word_refs) > self.config.max_words_per_table_candidate_unit:
                reasons.append("pdf_table_candidate_unit_word_budget_exceeded")
                continue
            candidate_word_set = set(word_refs)
            candidate_lines = [
                line
                for line in lines
                if set(_strings(line.get("word_refs"))) & candidate_word_set
            ]
            if not candidate_lines:
                reasons.append("pdf_table_candidate_fallback_lines_missing")
                continue
            owned_line_refs = [
                str(line.get("line_ref") or "")
                for line in candidate_lines
                if set(_strings(line.get("word_refs"))) <= candidate_word_set
            ]
            table_units.append(
                self._mint_unit(
                    **kwargs,
                    unit_type="pdf_table_candidate_unit",
                    selected_lines=candidate_lines,
                    owned_word_refs=word_refs,
                    owned_line_refs=owned_line_refs,
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
        candidate_cells = (
            copy.deepcopy(candidate.get("cell_inventory") or [])
            if candidate
            else []
        )
        has_exact_wordless_grid_cell = any(
            isinstance(cell, dict)
            and int(cell.get("row_ordinal") or 0) > 0
            and int(cell.get("column_ordinal") or 0) > 0
            and int(cell.get("row_span") or 1) == 1
            and int(cell.get("column_span") or 1) == 1
            and not list(cell.get("word_refs") or [])
            for cell in candidate_cells
        )
        table_cell_inventory_checksum_ref = (
            _checksum_ref(
                "pdftablecellinvchk",
                candidate_cells,
            )
            if has_exact_wordless_grid_cell
            else None
        )
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
                **(
                    {
                        "table_cell_inventory_checksum_ref": (
                            table_cell_inventory_checksum_ref
                        )
                    }
                    if table_cell_inventory_checksum_ref is not None
                    else {}
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
                **(
                    {
                        "table_cell_inventory_checksum_ref": (
                            table_cell_inventory_checksum_ref
                        )
                    }
                    if table_cell_inventory_checksum_ref is not None
                    else {}
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
                "table_locator_region_ref": (
                    candidate.get("locator_region_ref") if candidate else None
                ),
                "table_locator_bbox_pdf_points": copy.deepcopy(
                    candidate.get("locator_bbox_pdf_points") if candidate else None
                ),
                "table_locator_scope_status": (
                    candidate.get("locator_scope_status") if candidate else None
                ),
                "model_values_used_as_source_literals": False,
                "pdfplumber_settings_selected_by_model": False,
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
    rows_total: int,
    columns_total: int,
    word_by_ordinal: dict[int, dict[str, Any]],
    contributing_word_ordinals: list[int],
    char_by_ref: dict[str, dict[str, Any]],
    bbox_ref,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    reasons: list[str] = []
    if rows_total <= 0 or columns_total <= 0:
        reasons.append("pdf_table_word_cell_grid_dimensions_invalid")
    if not raw_cells:
        reasons.append("pdf_table_word_cell_source_cells_missing")

    addressed: list[tuple[dict[str, Any], int, int, int, int]] = []
    occupied_addresses: dict[tuple[int, int], int] = {}
    source_claim_owners: dict[int, int] = {}
    for cell_index, raw in enumerate(raw_cells, 1):
        row_ordinal = int(raw.get("row_ordinal") or 0)
        column_ordinal = int(raw.get("column_ordinal") or 0)
        row_span = int(raw.get("row_span") or 0)
        column_span = int(raw.get("column_span") or 0)
        if row_ordinal <= 0 or column_ordinal <= 0:
            reasons.append("pdf_table_word_cell_grid_address_missing")
        if row_span <= 0 or column_span <= 0:
            reasons.append("pdf_table_word_cell_grid_span_invalid")
        if (
            row_ordinal + max(row_span, 1) - 1 > rows_total
            or column_ordinal + max(column_span, 1) - 1 > columns_total
        ):
            reasons.append("pdf_table_word_cell_grid_address_out_of_bounds")
        for row_address in range(row_ordinal, row_ordinal + max(row_span, 1)):
            for column_address in range(
                column_ordinal, column_ordinal + max(column_span, 1)
            ):
                address = (row_address, column_address)
                if address in occupied_addresses:
                    reasons.append("pdf_table_word_cell_grid_address_overlap")
                occupied_addresses[address] = cell_index
        claimed_ordinals = [
            int(value) for value in raw.get("word_parser_ordinals") or []
        ]
        if len(claimed_ordinals) != len(set(claimed_ordinals)):
            reasons.append("pdf_table_word_cell_source_word_duplicate")
        for word_ordinal in claimed_ordinals:
            if word_ordinal not in word_by_ordinal:
                reasons.append("pdf_table_word_cell_source_word_missing_or_foreign")
            if word_ordinal in source_claim_owners:
                reasons.append("pdf_table_word_cell_source_word_multiple_cells")
            source_claim_owners[word_ordinal] = cell_index
        addressed.append(
            (raw, row_ordinal, column_ordinal, max(row_span, 1), max(column_span, 1))
        )

    expected_addresses = {
        (row, column)
        for row in range(1, rows_total + 1)
        for column in range(1, columns_total + 1)
    }
    if set(occupied_addresses) != expected_addresses:
        reasons.append("pdf_table_word_cell_grid_address_gap")

    for left_index, (left, *_rest) in enumerate(addressed):
        left_bbox = _bbox(left.get("bbox"))
        if left_bbox[2] <= left_bbox[0] or left_bbox[3] <= left_bbox[1]:
            reasons.append("pdf_table_word_cell_bbox_invalid")
        for right, *_ in addressed[left_index + 1 :]:
            right_bbox = _bbox(right.get("bbox"))
            overlap_width = min(left_bbox[2], right_bbox[2]) - max(
                left_bbox[0], right_bbox[0]
            )
            overlap_height = min(left_bbox[3], right_bbox[3]) - max(
                left_bbox[1], right_bbox[1]
            )
            if overlap_width > 0 and overlap_height > 0:
                reasons.append("pdf_table_word_cell_bbox_overlap")

    derived_words_by_cell: dict[int, list[str]] = {
        cell_index: [] for cell_index in range(1, len(addressed) + 1)
    }
    derived_cell_by_word_ordinal: dict[int, int] = {}
    contributing_set = set(contributing_word_ordinals)
    for word_ordinal in contributing_word_ordinals:
        word = word_by_ordinal.get(word_ordinal)
        if word is None:
            continue
        char_refs = _strings(word.get("char_refs"))
        if not char_refs:
            reasons.append("pdf_table_word_cell_word_chars_missing")
            continue
        resolved_cells: set[int] = set()
        word_failed = False
        for char_ref in char_refs:
            char = char_by_ref.get(char_ref)
            if char is None:
                reasons.append("pdf_table_word_cell_word_char_foreign")
                word_failed = True
                continue
            char_bbox = _bbox(char.get("bbox"))
            center = (
                (char_bbox[0] + char_bbox[2]) / 2.0,
                (char_bbox[1] + char_bbox[3]) / 2.0,
            )
            matching_cells = [
                cell_index
                for cell_index, (raw, *_rest) in enumerate(addressed, 1)
                if _point_in_bbox(center, _bbox(raw.get("bbox")))
            ]
            if not matching_cells:
                reasons.append("pdf_table_word_cell_char_center_gap")
                word_failed = True
            elif len(matching_cells) > 1:
                reasons.append("pdf_table_word_cell_char_center_ambiguous")
                word_failed = True
            else:
                resolved_cells.add(matching_cells[0])
        if word_failed:
            continue
        if len(resolved_cells) != 1:
            reasons.append("pdf_table_word_cell_word_crosses_cells")
            continue
        cell_index = next(iter(resolved_cells))
        derived_cell_by_word_ordinal[word_ordinal] = cell_index
        derived_words_by_cell[cell_index].append(
            str(word.get("word_ref") or "")
        )

    if set(source_claim_owners) != contributing_set:
        reasons.append("pdf_table_word_cell_source_claim_partition_mismatch")
    if any(
        source_claim_owners.get(word_ordinal)
        != derived_cell_by_word_ordinal.get(word_ordinal)
        for word_ordinal in contributing_set
    ):
        reasons.append("pdf_table_word_cell_source_claim_geometry_mismatch")
    if set(derived_cell_by_word_ordinal) != contributing_set:
        reasons.append("pdf_table_word_cell_contributing_partition_incomplete")

    rows: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    all_row_ordinals = sorted(
        set(range(1, rows_total + 1)) | {item[1] for item in addressed}
    )
    raw_cells_by_row = {
        row_ordinal: [
            item
            for item in addressed
            if item[1] == row_ordinal
        ]
        for row_ordinal in all_row_ordinals
    }
    cell_index_by_identity = {
        id(item[0]): index for index, item in enumerate(addressed, 1)
    }
    for row_ordinal in all_row_ordinals:
        row_ref = "pdftablerow_" + stable_digest([table_ref, row_ordinal], length=24)
        row_cell_refs = []
        ordered_group = sorted(raw_cells_by_row[row_ordinal], key=lambda item: item[2])
        for raw, _row, column_ordinal, row_span, column_span in ordered_group:
            cell_index = cell_index_by_identity[id(raw)]
            cell_ref = "pdftablecell_" + stable_digest(
                [table_ref, row_ordinal, column_ordinal, raw.get("bbox")], length=24
            )
            word_refs = derived_words_by_cell[cell_index]
            if not word_refs and (row_span != 1 or column_span != 1):
                reasons.append("pdf_table_word_cell_wordless_span_unsupported")
            cells.append(
                {
                    "cell_ref": cell_ref,
                    "row_ref": row_ref,
                    "page_ref": page_ref,
                    "row_ordinal": row_ordinal,
                    "column_ordinal": column_ordinal,
                    "row_span": row_span,
                    "column_span": column_span,
                    "merged_cell_group_ref": (
                        "pdfmergedcell_"
                        + stable_digest(
                            [
                                table_ref,
                                row_ordinal,
                                column_ordinal,
                                row_span,
                                column_span,
                            ],
                            length=24,
                        )
                        if row_span > 1 or column_span > 1
                        else None
                    ),
                    "bbox_ref": bbox_ref(raw.get("bbox")),
                    "word_refs": word_refs,
                    "source_word_parser_ordinals": [
                        int(value)
                        for value in raw.get("word_parser_ordinals") or []
                    ],
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
    cell_word_refs = [
        ref for cell in cells for ref in _strings(cell.get("word_refs"))
    ]
    contributing_word_refs = [
        str(word_by_ordinal[ordinal].get("word_ref") or "")
        for ordinal in contributing_word_ordinals
        if ordinal in word_by_ordinal
    ]
    if (
        len(cell_word_refs) != len(set(cell_word_refs))
        or sorted(cell_word_refs) != sorted(contributing_word_refs)
    ):
        reasons.append("pdf_table_word_cell_exact_partition_failed")
    return rows, cells, sorted(set(reasons))


def _materialized_page_matches_raw_layout(
    *,
    raw_layout: dict[str, Any],
    materialized: dict[str, Any],
) -> bool:
    """Owner-bound comparison while trusted parser objects are still live.

    This is deliberately not a serialized receipt. A payload-only validator
    cannot prove that geometry came from PDF bytes after all internal hashes
    have been recomputed.
    """

    for raw_key, materialized_key in (
        ("char_inventory", "chars"),
        ("word_inventory", "words"),
        ("line_inventory", "lines"),
    ):
        raw_by_ordinal = {
            int(item.get("parser_ordinal") or 0): item
            for item in _dicts(raw_layout.get(raw_key))
        }
        actual_by_ordinal = {
            int(item.get("parser_ordinal") or 0): item
            for item in _dicts(materialized.get(materialized_key))
        }
        if set(raw_by_ordinal) != set(actual_by_ordinal):
            return False
        for ordinal, raw in raw_by_ordinal.items():
            actual = actual_by_ordinal[ordinal]
            if any(actual.get(key) != value for key, value in raw.items()):
                return False

    expected_bboxes: set[tuple[float, ...]] = set()
    for key in (
        "char_inventory",
        "word_inventory",
        "line_inventory",
        "block_inventory",
        "vector_line_inventory",
        "rect_inventory",
        "table_candidate_inventory",
    ):
        for item in _dicts(raw_layout.get(key)):
            expected_bboxes.add(tuple(_bbox(item.get("bbox"))))
            if key == "table_candidate_inventory":
                expected_bboxes.update(
                    tuple(_bbox(cell.get("bbox")))
                    for cell in _dicts(item.get("cell_inventory"))
                )
    actual_bboxes = {
        tuple(_bbox(item.get("bbox")))
        for item in _dicts(materialized.get("bboxes"))
    }
    return actual_bboxes == expected_bboxes


def _table_terminal_counts(pages: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(
        str(page.get("table_candidate_status") or "none_detected")
        for page in pages
    )
    return {
        "candidate_pages_total": counts["candidate"],
        "rejected_pages_total": counts["rejected"],
        "blocked_pages_total": counts["blocked"],
        "none_detected_pages_total": counts["none_detected"],
    }


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


def pdf_layout_source_chain_page_receipt(
    *,
    page: dict[str, Any],
    chars: list[dict[str, Any]],
    words: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    bboxes: list[dict[str, Any]],
    unresolved_word_char_links_total: int = 0,
) -> dict[str, Any]:
    """Derive a structural receipt from exact pdfplumber object identities.

    This receipt participates in admission by proving page-scoped char -> word
    -> line ownership, but it is not a source-authenticity proof and is not
    sufficient without the owner-bound raw-parser comparison. Owner binding is
    likewise insufficient without this structural receipt and its validator.
    """

    page_ref = str(page.get("page_ref") or "")
    reasons: set[str] = set()
    if "pdf_layout_page_missing" in set(page.get("layout_reason_codes") or []):
        reasons.add("pdf_layout_source_chain_page_missing")
    chars_by_ref = {
        str(item.get("char_ref") or ""): item
        for item in chars
        if str(item.get("page_ref") or "") == page_ref
    }
    words_by_ref = {
        str(item.get("word_ref") or ""): item
        for item in words
        if str(item.get("page_ref") or "") == page_ref
    }
    for inventory, ordinal_reason in (
        (chars_by_ref.values(), "pdf_layout_source_chain_char_ordinal_invalid"),
        (words_by_ref.values(), "pdf_layout_source_chain_word_ordinal_invalid"),
        (
            [
                item
                for item in lines
                if str(item.get("page_ref") or "") == page_ref
            ],
            "pdf_layout_source_chain_line_ordinal_invalid",
        ),
    ):
        ordinals = sorted(int(item.get("parser_ordinal") or 0) for item in inventory)
        if ordinals != list(range(1, len(ordinals) + 1)):
            reasons.add(ordinal_reason)
    bboxes_by_ref = {
        str(item.get("bbox_ref") or ""): _bbox(item.get("bbox"))
        for item in bboxes
        if str(item.get("page_ref") or "") == page_ref
    }
    char_ref_by_ordinal = {
        int(item.get("parser_ordinal") or 0): char_ref
        for char_ref, item in chars_by_ref.items()
    }
    word_ref_by_ordinal = {
        int(item.get("parser_ordinal") or 0): word_ref
        for word_ref, item in words_by_ref.items()
    }
    char_owners: Counter[str] = Counter()
    char_owner_refs: dict[str, list[str]] = {
        char_ref: [] for char_ref in chars_by_ref
    }
    for word in words_by_ref.values():
        char_refs = _strings(word.get("char_refs"))
        parser_ordinals = [
            int(value) for value in word.get("char_parser_ordinals") or []
        ]
        expected_char_refs = [
            char_ref_by_ordinal[ordinal]
            for ordinal in parser_ordinals
            if ordinal in char_ref_by_ordinal
        ]
        if (
            len(expected_char_refs) != len(parser_ordinals)
            or char_refs != expected_char_refs
        ):
            reasons.add("pdf_layout_source_chain_word_char_parser_binding_mismatch")
        contributing_chars = [
            chars_by_ref[char_ref]
            for char_ref in char_refs
            if char_ref in chars_by_ref
        ]
        expected_text = "".join(
            _PDFPLUMBER_LIGATURE_EXPANSIONS.get(
                str(char.get("text") or ""), str(char.get("text") or "")
            )
            for char in contributing_chars
        )
        if str(word.get("text") or "") != expected_text:
            reasons.add("pdf_layout_source_chain_word_text_char_binding_mismatch")
        contributing_bboxes = [
            bboxes_by_ref.get(str(char.get("bbox_ref") or ""))
            for char in contributing_chars
        ]
        contributing_bboxes = [
            item for item in contributing_bboxes if item is not None
        ]
        word_bbox = bboxes_by_ref.get(str(word.get("bbox_ref") or ""))
        if contributing_chars and (
            len(contributing_bboxes) != len(contributing_chars)
            or word_bbox != _merged_bbox(contributing_bboxes)
        ):
            reasons.add("pdf_layout_source_chain_word_bbox_char_binding_mismatch")
        if len(char_refs) != len(set(char_refs)):
            reasons.add("pdf_layout_source_chain_word_char_ref_duplicate")
        for char_ref in char_refs:
            if char_ref not in chars_by_ref:
                reasons.add("pdf_layout_source_chain_word_char_ref_out_of_scope")
            else:
                char_owners[char_ref] += 1
                char_owner_refs[char_ref].append(str(word.get("word_ref") or ""))

    primary_refs: list[str] = []
    blank_refs: list[str] = []
    duplicate_refs: list[str] = []
    disposition_counts: Counter[str] = Counter()
    duplicate_identity_seen: dict[tuple[Any, ...], str] = {}
    for char_ref, char in sorted(
        chars_by_ref.items(), key=lambda item: int(item[1].get("parser_ordinal") or 0)
    ):
        owner_count = char_owners[char_ref]
        duplicate_ref = str(char.get("duplicate_of_char_ref") or "")
        duplicate_key = (
            str(char.get("text") or ""),
            tuple(bboxes_by_ref.get(str(char.get("bbox_ref") or ""), [])),
            str(char.get("fontname") or ""),
            char.get("size"),
            char.get("upright"),
        )
        expected_duplicate_ref = duplicate_identity_seen.get(duplicate_key, "")
        if duplicate_ref != expected_duplicate_ref:
            reasons.add("pdf_layout_source_chain_duplicate_disposition_invalid")
        if expected_duplicate_ref:
            duplicate_refs.append(char_ref)
            duplicate = chars_by_ref.get(expected_duplicate_ref)
            if (
                duplicate is None
                or int(duplicate.get("parser_ordinal") or 0)
                >= int(char.get("parser_ordinal") or 0)
            ):
                reasons.add("pdf_layout_source_chain_duplicate_ref_invalid")
            expected_disposition = "duplicate_overlay"
        elif not str(char.get("text") or "").strip():
            blank_refs.append(char_ref)
            if owner_count:
                reasons.add("pdf_layout_source_chain_blank_char_owned")
            expected_disposition = (
                "blank_unassigned" if owner_count == 0 else "unresolved"
            )
        else:
            primary_refs.append(char_ref)
            if owner_count == 0:
                reasons.add("pdf_layout_source_chain_primary_char_unowned")
            elif owner_count > 1:
                reasons.add("pdf_layout_source_chain_primary_char_multiply_owned")
            expected_disposition = "word_owned" if owner_count == 1 else "unresolved"
        disposition_counts[expected_disposition] += 1
        if char.get("source_chain_disposition") != expected_disposition:
            reasons.add("pdf_layout_source_chain_char_disposition_mismatch")
        if _strings(char.get("source_chain_word_refs")) != char_owner_refs[char_ref]:
            reasons.add("pdf_layout_source_chain_char_owner_inventory_mismatch")
        duplicate_identity_seen.setdefault(duplicate_key, char_ref)

    word_line_owners: Counter[str] = Counter()
    for line in lines:
        if str(line.get("page_ref") or "") != page_ref:
            continue
        line_word_refs = _strings(line.get("word_refs"))
        parser_ordinals = [
            int(value) for value in line.get("word_parser_ordinals") or []
        ]
        expected_word_refs = [
            word_ref_by_ordinal[ordinal]
            for ordinal in parser_ordinals
            if ordinal in word_ref_by_ordinal
        ]
        if (
            len(expected_word_refs) != len(parser_ordinals)
            or line_word_refs != expected_word_refs
        ):
            reasons.add("pdf_layout_source_chain_line_word_parser_binding_mismatch")
        if len(line_word_refs) != len(set(line_word_refs)):
            reasons.add("pdf_layout_source_chain_line_word_ref_duplicate")
        contributing_words = []
        for word_ref in line_word_refs:
            word = words_by_ref.get(word_ref)
            if word is None:
                reasons.add("pdf_layout_source_chain_line_word_ref_out_of_scope")
                continue
            word_line_owners[word_ref] += 1
            contributing_words.append(word)
        expected_text = " ".join(
            str(item.get("text") or "") for item in contributing_words
        ).strip()
        if str(line.get("text") or "") != expected_text:
            reasons.add("pdf_layout_source_chain_line_text_mismatch")
        contributing_bboxes = [
            bboxes_by_ref.get(str(item.get("bbox_ref") or ""))
            for item in contributing_words
        ]
        contributing_bboxes = [item for item in contributing_bboxes if item is not None]
        line_bbox = bboxes_by_ref.get(str(line.get("bbox_ref") or ""))
        if contributing_words and (
            len(contributing_bboxes) != len(contributing_words)
            or line_bbox != _merged_bbox(contributing_bboxes)
        ):
            reasons.add("pdf_layout_source_chain_line_bbox_mismatch")
    for word_ref in words_by_ref:
        if word_line_owners[word_ref] == 0:
            reasons.add("pdf_layout_source_chain_word_line_unowned")
        elif word_line_owners[word_ref] > 1:
            reasons.add("pdf_layout_source_chain_word_line_multiply_owned")

    if unresolved_word_char_links_total:
        reasons.add("pdf_layout_source_chain_word_char_identity_unresolved")
    rotated_total = sum(item.get("upright") is False for item in chars_by_ref.values())
    if rotated_total:
        reasons.add("pdf_layout_source_chain_rotated_text_unsupported")
    reason_codes = sorted(reasons)
    core = {
        "schema_version": PDF_LAYOUT_SOURCE_CHAIN_SCHEMA_VERSION,
        "policy_ref": PDF_LAYOUT_SOURCE_CHAIN_POLICY_VERSION,
        "page_ref": page_ref,
        "status": "complete" if not reason_codes else "partial",
        "reason_codes": reason_codes,
        "chars_total": len(chars_by_ref),
        "primary_chars_total": len(primary_refs),
        "blank_chars_total": len(blank_refs),
        "duplicate_chars_total": len(duplicate_refs),
        "words_total": len(words_by_ref),
        "lines_total": sum(
            str(item.get("page_ref") or "") == page_ref for item in lines
        ),
        "unresolved_word_char_links_total": unresolved_word_char_links_total,
        "disposition_counts": dict(sorted(disposition_counts.items())),
    }
    return {
        **core,
        "receipt_ref": _checksum_ref("pdflayoutchainpage", core),
    }


def pdf_layout_source_chain_document_receipt(
    page_receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons = sorted(
        {
            str(reason)
            for receipt in page_receipts
            for reason in receipt.get("reason_codes") or []
        }
    )
    core = {
        "schema_version": PDF_LAYOUT_SOURCE_CHAIN_SCHEMA_VERSION,
        "policy_ref": PDF_LAYOUT_SOURCE_CHAIN_POLICY_VERSION,
        "status": "complete" if not reasons else "partial",
        "reason_codes": reasons,
        "page_receipt_refs": [
            str(receipt.get("receipt_ref") or "") for receipt in page_receipts
        ],
        "pages_total": len(page_receipts),
        "complete_pages_total": sum(
            receipt.get("status") == "complete" for receipt in page_receipts
        ),
    }
    return {**core, "checksum_ref": _checksum_ref("pdflayoutchainchk", core)}


def _merged_bbox(values: list[list[float]]) -> list[float]:
    if not values:
        return [0.0, 0.0, 0.0, 0.0]
    return _bbox(
        [
            min(item[0] for item in values),
            min(item[1] for item in values),
            max(item[2] for item in values),
            max(item[3] for item in values),
        ]
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


def _point_in_bbox(
    point: tuple[float, float], bbox: list[float]
) -> bool:
    return (
        bbox[0] <= point[0] <= bbox[2]
        and bbox[1] <= point[1] <= bbox[3]
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
