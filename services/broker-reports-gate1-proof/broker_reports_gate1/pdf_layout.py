from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from .contracts import PDF_TABLE_LOCATOR_PAGE_SCHEMA_V3, stable_digest


PDFPLUMBER_PINNED_VERSION = "0.11.10"
PDFMINER_PINNED_VERSION = "20260107"
PDF_LAYOUT_POLICY_VERSION = "pdfplumber_layout_policy_v2"
PDF_LAYOUT_CAPABILITIES = frozenset(
    {"layout_words", "layout_lines", "table_candidates"}
)


@dataclass(frozen=True)
class PdfLayoutParserConfig:
    expected_pdfplumber_version: str = PDFPLUMBER_PINNED_VERSION
    expected_pdfminer_version: str = PDFMINER_PINNED_VERSION
    max_document_bytes: int = 50_000_000
    max_pages: int = 2_000
    max_chars_per_page: int = 50_000
    max_words_per_page: int = 10_000
    max_lines_per_page: int = 2_000
    max_vector_objects_per_page: int = 5_000
    max_inventory_objects_per_document: int = 400_000
    max_table_candidates_per_page: int = 20
    max_table_detection_words_per_page: int = 5_000
    max_table_detection_vector_objects_per_page: int = 5_000
    max_seconds_per_page: float = 30.0
    word_x_tolerance: float = 3.0
    word_y_tolerance: float = 3.0
    line_y_tolerance: float = 3.0
    table_snap_tolerance: float = 3.0
    table_join_tolerance: float = 3.0
    table_intersection_tolerance: float = 3.0
    locator_crop_margin_points: float = 1.0
    aligned_table_min_rows: int = 3
    aligned_table_min_columns: int = 2

    @property
    def config_ref(self) -> str:
        return "pdflayoutcfg_" + stable_digest(
            [
                PDF_LAYOUT_POLICY_VERSION,
                self.expected_pdfplumber_version,
                self.expected_pdfminer_version,
                self.max_document_bytes,
                self.max_pages,
                self.max_chars_per_page,
                self.max_words_per_page,
                self.max_lines_per_page,
                self.max_vector_objects_per_page,
                self.max_inventory_objects_per_document,
                self.max_table_candidates_per_page,
                self.max_table_detection_words_per_page,
                self.max_table_detection_vector_objects_per_page,
                self.max_seconds_per_page,
                self.word_x_tolerance,
                self.word_y_tolerance,
                self.line_y_tolerance,
                self.table_snap_tolerance,
                self.table_join_tolerance,
                self.table_intersection_tolerance,
                self.locator_crop_margin_points,
                self.aligned_table_min_rows,
                self.aligned_table_min_columns,
            ],
            length=24,
        )


@dataclass(frozen=True)
class PdfLayoutParseResult:
    parser_engine: str
    parser_engine_version: str
    underlying_engine: str
    underlying_engine_version: str
    parser_config_ref: str
    requested_capability: str
    provided_capabilities: list[str]
    layout_projection_status: str
    layout_reason_codes: list[str]
    table_candidate_status: str
    semantic_reconstruction_status: str
    pages: list[dict[str, Any]]
    diagnostics: dict[str, Any]


class PdfPlumberLayoutAdapter:
    def __init__(
        self,
        *,
        pdfplumber_module: Any,
        pdfminer_module: Any,
        config: PdfLayoutParserConfig,
        requested_capability: str,
    ) -> None:
        self._pdfplumber = pdfplumber_module
        self._pdfminer = pdfminer_module
        self.config = config
        self.requested_capability = requested_capability

    def parse(
        self,
        content_bytes: bytes,
        *,
        table_locator_pages: list[dict[str, Any]] | None = None,
    ) -> PdfLayoutParseResult:
        if not content_bytes.startswith(b"%PDF-"):
            return self._terminal_result("blocked", ["pdf_layout_header_missing"])
        if len(content_bytes) > self.config.max_document_bytes:
            return self._terminal_result(
                "partial", ["pdf_layout_document_budget_exceeded"]
            )
        try:
            pdf = self._pdfplumber.open(
                BytesIO(content_bytes),
                laparams={
                    "line_overlap": 0.5,
                    "char_margin": 2.0,
                    "line_margin": 0.5,
                    "word_margin": 0.1,
                    "boxes_flow": None,
                    "detect_vertical": True,
                    "all_texts": True,
                },
                unicode_norm="NFC",
                strict_metadata=False,
            )
        except Exception:
            return self._terminal_result(
                "blocked", ["pdf_layout_corrupt_encrypted_or_unreadable"]
            )

        pages: list[dict[str, Any]] = []
        source_pages_total = 0
        completed_pages_total = 0
        first_missing_page_number: int | None = None
        inventory_objects_total = 0
        inventory_objects_would_be_total = 0
        try:
            pages_total = len(pdf.pages)
            source_pages_total = pages_total
            if pages_total <= 0:
                return self._terminal_result(
                    "partial", ["pdf_layout_page_inventory_empty"]
                )
            if pages_total > self.config.max_pages:
                return self._terminal_result(
                    "partial", ["pdf_layout_page_budget_exceeded"]
                )
            locator_by_page = {
                int(item.get("page_number") or 0): item
                for item in table_locator_pages or []
                if isinstance(item, dict)
            }
            locator_mode = table_locator_pages is not None
            for page_number, page in enumerate(pdf.pages, start=1):
                page_result = self._parse_page(
                    page=page,
                    page_number=page_number,
                    locator_page=locator_by_page.get(page_number),
                    locator_mode=locator_mode,
                )
                page.close()
                page_inventory_objects_total = sum(
                    len(page_result.get(key) or [])
                    for key in (
                        "char_inventory",
                        "word_inventory",
                        "line_inventory",
                        "block_inventory",
                        "vector_line_inventory",
                        "rect_inventory",
                        "table_candidate_inventory",
                    )
                )
                inventory_objects_would_be_total = (
                    inventory_objects_total + page_inventory_objects_total
                )
                if inventory_objects_would_be_total > self.config.max_inventory_objects_per_document:
                    first_missing_page_number = page_number
                    pages.extend(
                        self._page_failure(
                            missing_page_number,
                            "pdf_layout_page_not_processed_document_inventory_budget",
                        )
                        for missing_page_number in range(page_number, pages_total + 1)
                    )
                    break
                pages.append(page_result)
                inventory_objects_total = inventory_objects_would_be_total
                completed_pages_total += 1
        finally:
            pdf.close()

        layout_reasons = sorted(
            {
                str(reason)
                for page in pages
                for reason in page.get("layout_reason_codes") or []
            }
        )
        if first_missing_page_number is not None:
            layout_reasons = sorted(
                {*layout_reasons, "pdf_layout_document_inventory_budget_exceeded"}
            )
        layout_status = "complete" if not layout_reasons else "partial"
        table_statuses = {
            str(page.get("table_candidate_status") or "not_claimed")
            for page in pages
        }
        if "blocked" in table_statuses:
            table_status = "blocked"
        elif "candidate" in table_statuses:
            table_status = "candidate"
        else:
            table_status = "not_claimed"
        return PdfLayoutParseResult(
            parser_engine="pdfplumber",
            parser_engine_version=self.config.expected_pdfplumber_version,
            underlying_engine="pdfminer.six",
            underlying_engine_version=self.config.expected_pdfminer_version,
            parser_config_ref=self.config.config_ref,
            requested_capability=self.requested_capability,
            provided_capabilities=self._provided_capabilities(),
            layout_projection_status=layout_status,
            layout_reason_codes=layout_reasons,
            table_candidate_status=table_status,
            semantic_reconstruction_status=(
                "candidate" if table_status == "candidate" else "not_claimed"
            ),
            pages=pages,
            diagnostics={
                "pages_total": len(pages),
                "source_pages_total": source_pages_total,
                "completed_pages_total": completed_pages_total,
                "missing_tail_pages_total": source_pages_total - completed_pages_total,
                "first_missing_page_number": first_missing_page_number,
                "inventory_objects_retained_total": inventory_objects_total,
                "inventory_objects_would_be_total": inventory_objects_would_be_total,
                "inventory_objects_limit": self.config.max_inventory_objects_per_document,
                "layout_complete_pages": sum(
                    1
                    for page in pages
                    if page.get("layout_projection_status") == "complete"
                ),
                "layout_partial_pages": sum(
                    1
                    for page in pages
                    if page.get("layout_projection_status") != "complete"
                ),
                "chars_total": sum(
                    len(page.get("char_inventory") or []) for page in pages
                ),
                "words_total": sum(
                    len(page.get("word_inventory") or []) for page in pages
                ),
                "lines_total": sum(
                    len(page.get("line_inventory") or []) for page in pages
                ),
                "blocks_total": sum(
                    len(page.get("block_inventory") or []) for page in pages
                ),
                "table_candidates_total": sum(
                    len(page.get("table_candidate_inventory") or [])
                    for page in pages
                ),
                "duplicate_chars_total": sum(
                    int(page.get("duplicate_chars_total") or 0) for page in pages
                ),
                "rotated_chars_total": sum(
                    int(page.get("rotated_chars_total") or 0) for page in pages
                ),
                "elapsed_milliseconds_total": round(
                    sum(float(page.get("elapsed_milliseconds") or 0.0) for page in pages),
                    3,
                ),
            },
        )

    def _parse_page(
        self,
        *,
        page: Any,
        page_number: int,
        locator_page: dict[str, Any] | None = None,
        locator_mode: bool = False,
    ) -> dict[str, Any]:
        started = time.monotonic()
        layout_reasons: list[str] = []
        table_reason_codes: list[str] = []
        try:
            raw_chars = list(page.chars or [])
            raw_vector_lines = list(page.lines or [])
            raw_rects = list(page.rects or [])
            raw_curves = list(page.curves or [])
        except Exception:
            return self._page_failure(page_number, "pdf_layout_object_inventory_failed")

        vector_objects_total = (
            len(raw_vector_lines) + len(raw_rects) + len(raw_curves)
        )
        if len(raw_chars) > self.config.max_chars_per_page:
            layout_reasons.append("pdf_layout_char_budget_exceeded")
        if vector_objects_total > self.config.max_vector_objects_per_page:
            layout_reasons.append("pdf_layout_vector_object_budget_exceeded")

        chars = [_sanitize_char(item, index) for index, item in enumerate(raw_chars, 1)]
        duplicate_chars_total = _mark_duplicate_chars(chars)
        rotated_chars_total = sum(1 for item in chars if item.get("upright") is False)

        try:
            raw_words = page.extract_words(
                x_tolerance=self.config.word_x_tolerance,
                y_tolerance=self.config.word_y_tolerance,
                keep_blank_chars=False,
                use_text_flow=False,
                line_dir="ttb",
                char_dir="ltr",
                split_at_punctuation=False,
                return_chars=True,
            )
            words = [
                _sanitize_word(item, index)
                for index, item in enumerate(raw_words or [], 1)
            ]
        except Exception:
            words = []
            layout_reasons.append("pdf_layout_word_extraction_failed")
        if len(words) > self.config.max_words_per_page:
            layout_reasons.append("pdf_layout_word_budget_exceeded")

        lines = _cluster_words_into_lines(
            words,
            y_tolerance=self.config.line_y_tolerance,
        )
        if len(lines) > self.config.max_lines_per_page:
            layout_reasons.append("pdf_layout_line_budget_exceeded")
        blocks = _cluster_lines_into_blocks(lines)
        vector_lines = [
            _sanitize_vector(item, index, "line")
            for index, item in enumerate(raw_vector_lines, 1)
        ]
        rects = [
            _sanitize_vector(item, index, "rect")
            for index, item in enumerate(raw_rects, 1)
        ]

        table_candidates: list[dict[str, Any]] = []
        if self.requested_capability == "table_candidates" and not layout_reasons:
            if (
                len(words) > self.config.max_table_detection_words_per_page
                or len(vector_lines) + len(rects)
                > self.config.max_table_detection_vector_objects_per_page
            ):
                table_reason_codes.append(
                    "pdf_table_detection_preflight_budget_exceeded"
                )
            else:
                if (
                    locator_mode
                    and locator_page is not None
                    and locator_page.get("schema_version")
                    == PDF_TABLE_LOCATOR_PAGE_SCHEMA_V3
                ):
                    table_reason_codes.append(
                        "pdf_table_locator_contract_version_unsupported"
                    )
                elif locator_mode and (
                    locator_page is None or locator_page.get("status") == "failed"
                ):
                    table_reason_codes.append("pdf_table_locator_page_failed")
                else:
                    try:
                        table_candidates, table_reason_codes = self._find_table_candidates(
                            page=page,
                            words=words,
                            vector_lines=vector_lines,
                            rects=rects,
                            locator_regions=(
                                list(locator_page.get("regions") or [])
                                if locator_mode and locator_page is not None
                                else None
                            ),
                        )
                    except Exception:
                        table_reason_codes.append("pdf_table_candidate_detection_failed")
        if len(table_candidates) > self.config.max_table_candidates_per_page:
            table_candidates = []
            table_reason_codes.append("pdf_table_candidate_budget_exceeded")

        elapsed_ms = round((time.monotonic() - started) * 1000.0, 3)
        if elapsed_ms > self.config.max_seconds_per_page * 1000.0:
            layout_reasons.append("pdf_layout_page_time_budget_exceeded")
        layout_status = "complete" if not layout_reasons else "partial"
        if self.requested_capability != "table_candidates":
            table_status = "not_claimed"
        elif any(
            reason.endswith("_failed")
            or reason.endswith("_budget_exceeded")
            or reason == "pdf_table_locator_contract_version_unsupported"
            for reason in table_reason_codes
        ):
            table_status = "blocked"
        elif table_candidates:
            table_status = "candidate"
        else:
            table_status = "not_claimed"

        locator_regions_total = (
            len(locator_page.get("regions") or [])
            if locator_mode and locator_page is not None
            else 0
        )
        locator_regions_accepted_total = (
            sum(bool(item.get("locator_region_ref")) for item in table_candidates)
            if locator_mode
            else 0
        )
        return {
            "page_number": page_number,
            "width": _number(getattr(page, "width", 0.0)),
            "height": _number(getattr(page, "height", 0.0)),
            "rotation": int(getattr(page, "rotation", 0) or 0),
            "layout_projection_status": layout_status,
            "layout_reason_codes": sorted(set(layout_reasons)),
            "layout_confidence": "parser_geometry" if layout_status == "complete" else "partial",
            "table_candidate_status": table_status,
            "table_reason_codes": sorted(set(table_reason_codes)),
            "char_inventory": chars,
            "word_inventory": words,
            "line_inventory": lines,
            "block_inventory": blocks,
            "vector_line_inventory": vector_lines,
            "rect_inventory": rects,
            "table_candidate_inventory": table_candidates,
            "parser_order_word_ordinals": [
                int(item["parser_ordinal"]) for item in words
            ],
            "geometry_reading_order_word_ordinals": [
                int(item["parser_ordinal"])
                for item in sorted(words, key=_geometry_key)
            ],
            "duplicate_chars_total": duplicate_chars_total,
            "rotated_chars_total": rotated_chars_total,
            "hidden_text_diagnostics_status": "not_available",
            "elapsed_milliseconds": elapsed_ms,
            "page_rendering_used_for_extraction": False,
            "ocr_vlm_used": False,
            "table_locator_mode": locator_mode,
            "table_locator_status": (
                str(locator_page.get("status") or "missing")
                if locator_mode and locator_page is not None
                else ("missing" if locator_mode else "not_requested")
            ),
            "table_locator_regions_total": locator_regions_total,
            "table_locator_regions_accepted_total": locator_regions_accepted_total,
            "table_locator_regions_rejected_total": (
                locator_regions_total - locator_regions_accepted_total
                if locator_mode
                else 0
            ),
        }

    def _find_table_candidates(
        self,
        *,
        page: Any,
        words: list[dict[str, Any]],
        vector_lines: list[dict[str, Any]],
        rects: list[dict[str, Any]],
        locator_regions: list[dict[str, Any]] | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if locator_regions is not None:
            return self._find_locator_scoped_table_candidates(
                page=page,
                words=words,
                vector_lines=vector_lines,
                rects=rects,
                locator_regions=locator_regions,
            )
        return self._find_unbounded_table_candidates(
            page=page,
            words=words,
            vector_lines=vector_lines,
            rects=rects,
        )

    def _find_unbounded_table_candidates(
        self,
        *,
        page: Any,
        words: list[dict[str, Any]],
        vector_lines: list[dict[str, Any]],
        rects: list[dict[str, Any]],
        source_bound: bool = False,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        raw_candidates: list[dict[str, Any]] = []
        reasons: list[str] = []
        strategies = []
        if len(vector_lines) + len(rects) >= 4:
            strategies.append((
                "ruled_lines_v0",
                {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": self.config.table_snap_tolerance,
                    "join_tolerance": self.config.table_join_tolerance,
                    "intersection_tolerance": self.config.table_intersection_tolerance,
                    "edge_min_length": 3,
                    "min_words_vertical": 3,
                    "min_words_horizontal": 1,
                    "text_x_tolerance": self.config.word_x_tolerance,
                    "text_y_tolerance": self.config.word_y_tolerance,
                },
                0.95,
            ))
        aligned_min_words_vertical = 3
        aligned_evidence = _has_aligned_column_evidence(words)
        if (
            source_bound
            and not aligned_evidence
            and _has_aligned_column_evidence(words, minimum_row_bands=2)
        ):
            aligned_min_words_vertical = 2
            aligned_evidence = True
        if aligned_evidence:
            strategies.append((
                "aligned_text_v0",
                {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "min_words_vertical": aligned_min_words_vertical,
                    "min_words_horizontal": 2,
                    "text_x_tolerance": self.config.word_x_tolerance,
                    "text_y_tolerance": self.config.word_y_tolerance,
                    "snap_tolerance": self.config.table_snap_tolerance,
                    "join_tolerance": self.config.table_join_tolerance,
                    "intersection_tolerance": self.config.table_intersection_tolerance,
                },
                0.8,
            ))
        for strategy_ref, settings, confidence in strategies:
            try:
                found = page.find_tables(table_settings=settings)
            except Exception:
                reasons.append(f"pdf_table_{strategy_ref}_failed")
                continue
            for table in found:
                candidate = _table_candidate_from_pdfplumber(
                    table=table,
                    strategy_ref=strategy_ref,
                    geometry_confidence=confidence,
                    words=words,
                    vector_lines=vector_lines,
                    rects=rects,
                )
                if candidate is None:
                    reasons.append(f"pdf_table_{strategy_ref}_low_confidence_rejected")
                    continue
                if (
                    strategy_ref == "aligned_text_v0"
                    and (
                        candidate["rows_total"]
                        < (1 if source_bound else self.config.aligned_table_min_rows)
                        or candidate["columns_total"]
                        < self.config.aligned_table_min_columns
                    )
                ):
                    reasons.append("pdf_table_aligned_text_low_confidence_rejected")
                    continue
                raw_candidates.append(candidate)

        if (
            source_bound
            and not raw_candidates
            and len(words) >= 2
            and len(vector_lines) + len(rects) >= 2
        ):
            settings = {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "min_words_vertical": 1,
                "min_words_horizontal": 1,
                "text_x_tolerance": self.config.word_x_tolerance,
                "text_y_tolerance": self.config.word_y_tolerance,
                "snap_tolerance": self.config.table_snap_tolerance,
                "join_tolerance": self.config.table_join_tolerance,
                "intersection_tolerance": self.config.table_intersection_tolerance,
            }
            try:
                found = page.find_tables(table_settings=settings)
            except Exception:
                reasons.append("pdf_table_aligned_text_failed")
                found = []
            for table in found:
                candidate = _table_candidate_from_pdfplumber(
                    table=table,
                    strategy_ref="aligned_text_v0",
                    geometry_confidence=0.8,
                    words=words,
                    vector_lines=vector_lines,
                    rects=rects,
                )
                if candidate is None or candidate["columns_total"] < 2:
                    reasons.append("pdf_table_aligned_text_low_confidence_rejected")
                    continue
                candidate["reconstruction_reason_codes"] = sorted(
                    {
                        *candidate.get("reconstruction_reason_codes", []),
                        "source_bound_single_band_alignment_fallback",
                    }
                )
                raw_candidates.append(candidate)

        accepted: list[dict[str, Any]] = []
        for candidate in sorted(
            raw_candidates,
            key=lambda item: (
                -float(item.get("geometry_confidence") or 0.0),
                tuple(item.get("bbox") or []),
                str(item.get("table_strategy_ref") or ""),
            ),
        ):
            if any(_bbox_iou(candidate["bbox"], item["bbox"]) >= 0.8 for item in accepted):
                reasons.append("pdf_table_candidate_duplicate_geometry_rejected")
                continue
            if any(_bbox_overlap(candidate["bbox"], item["bbox"]) for item in accepted):
                reasons.append("pdf_table_candidate_conflicting_geometry_rejected")
                continue
            accepted.append(candidate)
        return accepted, sorted(set(reasons))

    def _find_locator_scoped_table_candidates(
        self,
        *,
        page: Any,
        words: list[dict[str, Any]],
        vector_lines: list[dict[str, Any]],
        rects: list[dict[str, Any]],
        locator_regions: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        page_bbox = [_number(value) for value in list(page.bbox)]
        selected: list[dict[str, Any]] = []
        reasons: list[str] = []
        locator_bboxes: list[list[float]] = []
        for ordinal, region in enumerate(locator_regions, 1):
            locator_bbox = (
                list(region.get("bbox_pdf_points") or [])
                if isinstance(region, dict)
                else []
            )
            if (
                len(locator_bbox) != 4
                or any(
                    not isinstance(value, (int, float)) for value in locator_bbox
                )
                or locator_bbox[0] >= locator_bbox[2]
                or locator_bbox[1] >= locator_bbox[3]
                or locator_bbox[0] < page_bbox[0]
                or locator_bbox[1] < page_bbox[1]
                or locator_bbox[2] > page_bbox[2]
                or locator_bbox[3] > page_bbox[3]
            ):
                reasons.append("pdf_table_locator_region_invalid_rejected")
                continue
            bbox = [_number(value) for value in locator_bbox]
            minor_overlap_partitioned = False
            if locator_bboxes and _bbox_overlap(bbox, locator_bboxes[-1]):
                previous = locator_bboxes[-1]
                vertical_overlap = previous[3] - bbox[1]
                shared_width = max(
                    0.0, min(previous[2], bbox[2]) - max(previous[0], bbox[0])
                )
                narrowest_width = min(
                    previous[2] - previous[0], bbox[2] - bbox[0]
                )
                if (
                    0.0 < vertical_overlap
                    <= self.config.locator_crop_margin_points * 2.0
                    and narrowest_width > 0.0
                    and shared_width / narrowest_width >= 0.8
                    and bbox[1] < previous[3] < bbox[3]
                ):
                    bbox[1] = previous[3]
                    minor_overlap_partitioned = True
                else:
                    reasons.append("pdf_table_locator_region_invalid_rejected")
                    continue
            if any(_bbox_overlap(bbox, other) for other in locator_bboxes):
                reasons.append("pdf_table_locator_region_invalid_rejected")
                continue
            locator_bboxes.append(bbox)
            region_words = [
                word
                for word in words
                if _bbox_center_inside(word.get("bbox") or [], bbox)
            ]
            crop_bbox = _expanded_bbox(
                bbox,
                page_bbox=page_bbox,
                margin=self.config.locator_crop_margin_points,
            )
            region_lines = [
                line
                for line in vector_lines
                if _bbox_overlap(line.get("bbox") or [], crop_bbox)
            ]
            region_rects = [
                rect
                for rect in rects
                if _bbox_overlap(rect.get("bbox") or [], crop_bbox)
            ]
            try:
                crop = page.crop(tuple(crop_bbox), strict=False)
                candidates, region_reasons = self._find_unbounded_table_candidates(
                    page=crop,
                    words=region_words,
                    vector_lines=region_lines,
                    rects=region_rects,
                    source_bound=True,
                )
            except Exception:
                reasons.append("pdf_table_locator_region_native_extraction_rejected")
                continue
            reasons.extend(region_reasons)
            if len(candidates) != 1:
                reasons.append(
                    "pdf_table_locator_region_native_table_not_found_rejected"
                    if not candidates
                    else "pdf_table_locator_region_native_table_ambiguous_rejected"
                )
                continue
            candidate = candidates[0]
            candidate["locator_region_ref"] = str(
                region.get("region_ref") or f"locator_region_{ordinal}"
            )
            candidate["locator_bbox_pdf_points"] = [
                round(_number(value), 6) for value in locator_bbox
            ]
            candidate["locator_scope_status"] = "source_bound"
            candidate["model_values_used_as_source_literals"] = False
            candidate["pdfplumber_settings_selected_by_model"] = False
            candidate["reconstruction_reason_codes"] = sorted(
                {
                    *candidate.get("reconstruction_reason_codes", []),
                    "locator_boundary_margin_applied",
                    *(
                        ["locator_minor_overlap_partitioned"]
                        if minor_overlap_partitioned
                        else []
                    ),
                    "vlm_region_pdfplumber_structure_source_literals",
                }
            )
            selected.append(candidate)
        return selected, sorted(set(reasons))

    def _provided_capabilities(self) -> list[str]:
        ordered = ["layout_words", "layout_lines", "table_candidates"]
        limit = ordered.index(self.requested_capability)
        return ordered[: limit + 1]

    def _page_failure(self, page_number: int, reason: str) -> dict[str, Any]:
        return {
            "page_number": page_number,
            "width": 0.0,
            "height": 0.0,
            "rotation": 0,
            "layout_projection_status": "partial",
            "layout_reason_codes": [reason],
            "layout_confidence": "partial",
            "table_candidate_status": "blocked",
            "table_reason_codes": [reason],
            "char_inventory": [],
            "word_inventory": [],
            "line_inventory": [],
            "block_inventory": [],
            "vector_line_inventory": [],
            "rect_inventory": [],
            "table_candidate_inventory": [],
            "parser_order_word_ordinals": [],
            "geometry_reading_order_word_ordinals": [],
            "duplicate_chars_total": 0,
            "rotated_chars_total": 0,
            "hidden_text_diagnostics_status": "not_available",
            "elapsed_milliseconds": 0.0,
            "page_rendering_used_for_extraction": False,
            "ocr_vlm_used": False,
        }

    def _terminal_result(
        self, status: str, reasons: list[str]
    ) -> PdfLayoutParseResult:
        return PdfLayoutParseResult(
            parser_engine="pdfplumber",
            parser_engine_version=self.config.expected_pdfplumber_version,
            underlying_engine="pdfminer.six",
            underlying_engine_version=self.config.expected_pdfminer_version,
            parser_config_ref=self.config.config_ref,
            requested_capability=self.requested_capability,
            provided_capabilities=[],
            layout_projection_status=status,
            layout_reason_codes=sorted(set(reasons)),
            table_candidate_status="blocked",
            semantic_reconstruction_status="not_claimed",
            pages=[],
            diagnostics={
                "pages_total": 0,
                "layout_complete_pages": 0,
                "layout_partial_pages": 0,
                "chars_total": 0,
                "words_total": 0,
                "lines_total": 0,
                "blocks_total": 0,
                "table_candidates_total": 0,
                "duplicate_chars_total": 0,
                "rotated_chars_total": 0,
                "elapsed_milliseconds_total": 0.0,
            },
        )


def _sanitize_char(item: dict[str, Any], ordinal: int) -> dict[str, Any]:
    return {
        "parser_ordinal": ordinal,
        "text": str(item.get("text") or ""),
        "bbox": _bbox(item),
        "fontname": str(item.get("fontname") or ""),
        "size": _number(item.get("size")),
        "upright": bool(item.get("upright", True)),
        "direction": str(item.get("direction") or ""),
        "duplicate_of_parser_ordinal": None,
    }


def _sanitize_word(item: dict[str, Any], ordinal: int) -> dict[str, Any]:
    chars = item.get("chars") if isinstance(item.get("chars"), list) else []
    return {
        "parser_ordinal": ordinal,
        "text": str(item.get("text") or ""),
        "bbox": _bbox(item),
        "direction": str(item.get("direction") or ""),
        "upright": all(bool(char.get("upright", True)) for char in chars if isinstance(char, dict)),
        "char_parser_ordinals": [],
    }


def _sanitize_vector(
    item: dict[str, Any], ordinal: int, object_type: str
) -> dict[str, Any]:
    return {
        "parser_ordinal": ordinal,
        "object_type": object_type,
        "bbox": _bbox(item),
        "linewidth": _number(item.get("linewidth")),
    }


def _mark_duplicate_chars(chars: list[dict[str, Any]]) -> int:
    seen: dict[tuple[Any, ...], int] = {}
    duplicates = 0
    for item in chars:
        bbox = item.get("bbox") or []
        key = (
            item.get("text"),
            *bbox,
            item.get("fontname"),
            item.get("size"),
            item.get("upright"),
        )
        if key in seen:
            item["duplicate_of_parser_ordinal"] = seen[key]
            duplicates += 1
        else:
            seen[key] = int(item["parser_ordinal"])
    return duplicates


def _cluster_words_into_lines(
    words: list[dict[str, Any]], *, y_tolerance: float
) -> list[dict[str, Any]]:
    ordered = sorted(words, key=_geometry_key)
    groups: list[list[dict[str, Any]]] = []
    for word in ordered:
        top = float((word.get("bbox") or [0, 0, 0, 0])[1])
        target = next(
            (
                group
                for group in reversed(groups)
                if abs(
                    top
                    - statistics.median(
                        float((item.get("bbox") or [0, 0, 0, 0])[1])
                        for item in group
                    )
                )
                <= y_tolerance
            ),
            None,
        )
        if target is None:
            groups.append([word])
        else:
            target.append(word)
    result: list[dict[str, Any]] = []
    for ordinal, group in enumerate(groups, 1):
        row = sorted(group, key=lambda item: float((item.get("bbox") or [0])[0]))
        result.append(
            {
                "parser_ordinal": ordinal,
                "geometry_reading_order": ordinal,
                "text": " ".join(str(item.get("text") or "") for item in row).strip(),
                "bbox": _merge_bboxes([item.get("bbox") or [] for item in row]),
                "word_parser_ordinals": [int(item["parser_ordinal"]) for item in row],
            }
        )
    return result


def _cluster_lines_into_blocks(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not lines:
        return []
    heights = [
        max(0.0, float(line["bbox"][3]) - float(line["bbox"][1]))
        for line in lines
        if line.get("bbox")
    ]
    gap_limit = max(12.0, (statistics.median(heights) if heights else 10.0) * 1.8)
    groups: list[list[dict[str, Any]]] = []
    for line in lines:
        if not groups:
            groups.append([line])
            continue
        previous = groups[-1][-1]
        gap = float(line["bbox"][1]) - float(previous["bbox"][3])
        if gap > gap_limit:
            groups.append([line])
        else:
            groups[-1].append(line)
    return [
        {
            "parser_ordinal": ordinal,
            "bbox": _merge_bboxes([line["bbox"] for line in group]),
            "line_parser_ordinals": [int(line["parser_ordinal"]) for line in group],
        }
        for ordinal, group in enumerate(groups, 1)
    ]


def _table_candidate_from_pdfplumber(
    *,
    table: Any,
    strategy_ref: str,
    geometry_confidence: float,
    words: list[dict[str, Any]],
    vector_lines: list[dict[str, Any]],
    rects: list[dict[str, Any]],
) -> dict[str, Any] | None:
    bbox = [_number(value) for value in list(getattr(table, "bbox", ()) or ())]
    if len(bbox) != 4 or bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return None
    rows = list(getattr(table, "rows", []) or [])
    columns = list(getattr(table, "columns", []) or [])
    rows_total = len(rows)
    columns_total = len(columns)
    if rows_total < 1 or columns_total < 2:
        return None
    contributing = [
        int(word["parser_ordinal"])
        for word in words
        if _bbox_center_inside(word.get("bbox") or [], bbox)
    ]
    grid_cells = [
        [list(cell) if cell is not None else None for cell in row.cells] for row in rows
    ]
    cell_bboxes = [
        [_number(value) for value in cell]
        for row in grid_cells
        for cell in row
        if cell is not None and len(cell) == 4
    ]
    if not cell_bboxes:
        return None
    x_edges = sorted({value for cell in cell_bboxes for value in (cell[0], cell[2])})
    y_edges = sorted({value for cell in cell_bboxes for value in (cell[1], cell[3])})
    cell_inventory = []
    cell_ordinal = 0
    for row_ordinal, row_cells in enumerate(grid_cells, 1):
        for column_ordinal, cell_bbox in enumerate(row_cells, 1):
            if cell_bbox is None or len(cell_bbox) != 4:
                continue
            cell_ordinal += 1
            normalized_bbox = [_number(value) for value in cell_bbox]
            cell_inventory.append(
                {
                    "cell_ordinal": cell_ordinal,
                    "row_ordinal": row_ordinal,
                    "column_ordinal": column_ordinal,
                    "row_span": _axis_span(
                        y_edges, normalized_bbox[1], normalized_bbox[3]
                    ),
                    "column_span": _axis_span(
                        x_edges, normalized_bbox[0], normalized_bbox[2]
                    ),
                    "bbox": normalized_bbox,
                    "word_parser_ordinals": [
                        int(word["parser_ordinal"])
                        for word in words
                        if _bbox_center_inside(word.get("bbox") or [], normalized_bbox)
                    ],
                }
            )
    original_rows_total = rows_total
    original_columns_total = columns_total
    compacted = _compact_empty_table_axes(
        rows=rows,
        columns=columns,
        cells=cell_inventory,
        words=words,
    )
    rows_total = compacted["rows_total"]
    columns_total = compacted["columns_total"]
    cell_inventory = compacted["cells"]
    if rows_total < 1 or columns_total < 2 or len(contributing) < max(2, rows_total):
        return None
    ruling_evidence_total = sum(
        1
        for item in [*vector_lines, *rects]
        if _bbox_overlap(item.get("bbox") or [], bbox)
    )
    if strategy_ref == "ruled_lines_v0" and ruling_evidence_total < 2:
        return None
    return {
        "parser_ordinal": 0,
        "table_strategy_ref": strategy_ref,
        "table_reconstruction_status": "candidate",
        "geometry_confidence": round(float(geometry_confidence), 3),
        "bbox": bbox,
        "rows_total": rows_total,
        "columns_total": columns_total,
        "cells_total": len(cell_inventory),
        "cell_inventory": cell_inventory,
        "contributing_word_parser_ordinals": contributing,
        "ruling_evidence_total": ruling_evidence_total,
        "reconstruction_reason_codes": [
            "geometry_only_non_semantic_candidate",
            (
                "ruling_line_grid_detected"
                if strategy_ref == "ruled_lines_v0"
                else "repeated_text_alignment_detected"
            ),
            *(
                ["empty_grid_axes_compacted"]
                if rows_total != original_rows_total
                or columns_total != original_columns_total
                else []
            ),
        ],
    }


def _axis_span(edges: list[float], start: float, end: float) -> int:
    if len(edges) < 2:
        return 1
    start_index = min(range(len(edges)), key=lambda index: abs(edges[index] - start))
    end_index = min(range(len(edges)), key=lambda index: abs(edges[index] - end))
    return max(1, end_index - start_index)


def _compact_empty_table_axes(
    *,
    rows: list[Any],
    columns: list[Any],
    cells: list[dict[str, Any]],
    words: list[dict[str, Any]],
) -> dict[str, Any]:
    active_rows = [
        ordinal
        for ordinal, row in enumerate(rows, 1)
        if any(
            _bbox_center_inside(word.get("bbox") or [], list(row.bbox))
            for word in words
        )
    ]
    active_columns = [
        ordinal
        for ordinal, column in enumerate(columns, 1)
        if any(
            _bbox_center_inside(word.get("bbox") or [], list(column.bbox))
            for word in words
        )
    ]
    row_positions = {
        original: compacted for compacted, original in enumerate(active_rows, 1)
    }
    column_positions = {
        original: compacted for compacted, original in enumerate(active_columns, 1)
    }
    compacted_cells: list[dict[str, Any]] = []
    for cell in cells:
        row_ordinal = int(cell.get("row_ordinal") or 0)
        column_ordinal = int(cell.get("column_ordinal") or 0)
        retained_rows = [
            ordinal
            for ordinal in range(
                row_ordinal,
                row_ordinal + max(1, int(cell.get("row_span") or 1)),
            )
            if ordinal in row_positions
        ]
        retained_columns = [
            ordinal
            for ordinal in range(
                column_ordinal,
                column_ordinal + max(1, int(cell.get("column_span") or 1)),
            )
            if ordinal in column_positions
        ]
        if not retained_rows or not retained_columns:
            continue
        compacted_cells.append(
            {
                **cell,
                "cell_ordinal": len(compacted_cells) + 1,
                "row_ordinal": row_positions[retained_rows[0]],
                "column_ordinal": column_positions[retained_columns[0]],
                "row_span": len(retained_rows),
                "column_span": len(retained_columns),
            }
        )
    return {
        "rows_total": len(active_rows),
        "columns_total": len(active_columns),
        "cells": compacted_cells,
    }


def _expanded_bbox(
    bbox: list[float], *, page_bbox: list[float], margin: float
) -> list[float]:
    bounded_margin = max(0.0, float(margin))
    return [
        max(page_bbox[0], _number(bbox[0]) - bounded_margin),
        max(page_bbox[1], _number(bbox[1]) - bounded_margin),
        min(page_bbox[2], _number(bbox[2]) + bounded_margin),
        min(page_bbox[3], _number(bbox[3]) + bounded_margin),
    ]


def _geometry_key(item: dict[str, Any]) -> tuple[float, float, int]:
    bbox = item.get("bbox") or [0.0, 0.0, 0.0, 0.0]
    return (
        float(bbox[1]),
        float(bbox[0]),
        int(item.get("parser_ordinal") or 0),
    )


def _has_aligned_column_evidence(
    words: list[dict[str, Any]], *, minimum_row_bands: int = 3
) -> bool:
    clusters: list[list[dict[str, Any]]] = []
    for word in sorted(words, key=lambda item: float((item.get("bbox") or [0.0])[0])):
        x0 = float((word.get("bbox") or [0.0])[0])
        target = next(
            (
                cluster
                for cluster in reversed(clusters)
                if abs(
                    x0
                    - statistics.median(
                        float((item.get("bbox") or [0.0])[0]) for item in cluster
                    )
                )
                <= 5.0
            ),
            None,
        )
        if target is None:
            clusters.append([word])
        else:
            target.append(word)
    repeated_columns = 0
    for cluster in clusters:
        row_bands = {
            round(float((item.get("bbox") or [0.0, 0.0])[1]) / 3.0)
            for item in cluster
        }
        if len(row_bands) >= minimum_row_bands:
            repeated_columns += 1
    return repeated_columns >= 2


def _bbox(item: dict[str, Any]) -> list[float]:
    return [
        _number(item.get("x0")),
        _number(item.get("top")),
        _number(item.get("x1")),
        _number(item.get("bottom")),
    ]


def _merge_bboxes(bboxes: list[list[float]]) -> list[float]:
    valid = [bbox for bbox in bboxes if len(bbox) == 4]
    if not valid:
        return [0.0, 0.0, 0.0, 0.0]
    return [
        min(float(bbox[0]) for bbox in valid),
        min(float(bbox[1]) for bbox in valid),
        max(float(bbox[2]) for bbox in valid),
        max(float(bbox[3]) for bbox in valid),
    ]


def _bbox_center_inside(inner: list[float], outer: list[float]) -> bool:
    if len(inner) != 4 or len(outer) != 4:
        return False
    x = (float(inner[0]) + float(inner[2])) / 2.0
    y = (float(inner[1]) + float(inner[3])) / 2.0
    return float(outer[0]) <= x <= float(outer[2]) and float(outer[1]) <= y <= float(outer[3])


def _bbox_overlap(left: list[float], right: list[float]) -> bool:
    if len(left) != 4 or len(right) != 4:
        return False
    return not (
        float(left[2]) <= float(right[0])
        or float(right[2]) <= float(left[0])
        or float(left[3]) <= float(right[1])
        or float(right[3]) <= float(left[1])
    )


def _bbox_iou(left: list[float], right: list[float]) -> float:
    if not _bbox_overlap(left, right):
        return 0.0
    intersection = max(0.0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0.0, min(left[3], right[3]) - max(left[1], right[1])
    )
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def _number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number != number or abs(number) == float("inf"):
        return 0.0
    return round(number, 4)
