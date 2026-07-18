from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .contracts import stable_digest


FACTORY_REQUIRED = (
    "NormalizedSliceProvenanceFactory.create is the only production source-unit provenance entrypoint"
)
FORBIDDEN = (
    "Profilers, Gate 2 package builders and smoke scripts must not mint row, cell or source-value refs directly"
)

SOURCE_UNIT_SCHEMA_VERSION = "source_unit_provenance_v0"
TABLE_SLICE_SCHEMA_VERSION = "private_normalized_table_slice_v0"
TEXT_SLICE_SCHEMA_VERSION = "private_normalized_text_slice_v0"
VISUAL_SLICE_SCHEMA_VERSION = "private_normalized_visual_slice_v1"
COVERAGE_SCHEMA_VERSION = "source_unit_coverage_v0"
SOURCE_VALUE_PROJECTION_POLICY = "private_payload_path_plus_checksum_v0"

_TABLE_PROVENANCE_FIELDS = {
    "schema_version",
    "source_unit_schema_version",
    "normalization_run_id",
    "table_ref",
    "row_refs",
    "row_range_ref",
    "cell_refs",
    "cell_value_refs",
    "source_value_refs",
    "normalized_header_descriptors",
    "row_provenance",
    "cell_provenance",
    "source_value_index",
    "source_value_projection_policy",
    "parser_ref",
    "source_checksum_ref",
    "slice_payload_checksum_ref",
    "safe_coverage_refs",
    "coverage",
}

_TEXT_PROVENANCE_FIELDS = {
    "schema_version",
    "source_unit_schema_version",
    "normalization_run_id",
    "text_segment_refs",
    "section_refs",
    "page_refs",
    "page_range_ref",
    "character_span_refs",
    "segment_provenance",
    "source_value_refs",
    "source_value_index",
    "source_value_projection_policy",
    "parser_ref",
    "source_checksum_ref",
    "slice_payload_checksum_ref",
    "safe_section_labels",
    "safe_coverage_refs",
    "coverage",
}

_VISUAL_PROVENANCE_FIELDS = {
    "schema_version",
    "source_unit_schema_version",
    "normalization_run_id",
    "page_refs",
    "media_ref",
    "media_checksum_ref",
    "source_value_refs",
    "source_value_index",
    "source_value_projection_policy",
    "parser_ref",
    "source_checksum_ref",
    "slice_payload_checksum_ref",
    "safe_coverage_refs",
    "coverage",
}

_VISUAL_MEDIA_PROVENANCE_FIELDS = {
    "schema_version",
    "source_unit_schema_version",
    "normalization_run_id",
    "media_item_refs",
    "media_ref",
    "media_checksum_ref",
    "source_value_refs",
    "source_value_index",
    "source_value_projection_policy",
    "parser_ref",
    "source_checksum_ref",
    "slice_payload_checksum_ref",
    "safe_coverage_refs",
    "coverage",
}


@dataclass(frozen=True)
class NormalizedSliceProvenanceConfig:
    source_value_projection_policy: str = SOURCE_VALUE_PROJECTION_POLICY


class NormalizedSliceProvenanceFactory:
    def __init__(self, config: NormalizedSliceProvenanceConfig | None = None) -> None:
        self.config = config or NormalizedSliceProvenanceConfig()

    def create(self) -> "NormalizedSliceProvenanceEnricher":
        if self.config.source_value_projection_policy != SOURCE_VALUE_PROJECTION_POLICY:
            raise ValueError("unsupported_source_value_projection_policy")
        return NormalizedSliceProvenanceEnricher(self.config)


class NormalizedSliceProvenanceEnricher:
    def __init__(self, config: NormalizedSliceProvenanceConfig) -> None:
        self.config = config

    def enrich_slices(
        self,
        *,
        normalization_run_id: str,
        document_id: str,
        source_checksum_sha256: str,
        slices: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            self.enrich_slice(
                normalization_run_id=normalization_run_id,
                document_id=document_id,
                source_checksum_sha256=source_checksum_sha256,
                private_slice=private_slice,
            )
            for private_slice in slices
        ]

    def enrich_slice(
        self,
        *,
        normalization_run_id: str,
        document_id: str,
        source_checksum_sha256: str,
        private_slice: dict[str, Any],
    ) -> dict[str, Any]:
        if not normalization_run_id:
            raise ValueError("normalization_run_id_required")
        if not document_id or private_slice.get("document_id") != document_id:
            raise ValueError("slice_document_scope_mismatch")
        if not source_checksum_sha256:
            raise ValueError("source_checksum_required")
        slice_id = str(private_slice.get("slice_id") or "")
        if not slice_id:
            raise ValueError("slice_id_required")

        enriched = copy.deepcopy(private_slice)
        source_checksum_ref = _ref(
            "srcsum",
            document_id,
            source_checksum_sha256,
            length=24,
        )
        parser = str(private_slice.get("parser") or "unknown")
        parser_ref = _ref(
            "parser",
            parser,
            private_slice.get("profile_id"),
            length=20,
        )
        common = {
            "source_unit_schema_version": SOURCE_UNIT_SCHEMA_VERSION,
            "normalization_run_id": normalization_run_id,
            "source_value_projection_policy": self.config.source_value_projection_policy,
            "source_checksum_ref": source_checksum_ref,
            "parser_ref": parser_ref,
        }
        if private_slice.get("slice_type") == "table_rows":
            enriched.update(
                self._table_provenance(
                    private_slice=private_slice,
                    source_checksum_ref=source_checksum_ref,
                    parser_ref=parser_ref,
                )
            )
            enriched["schema_version"] = TABLE_SLICE_SCHEMA_VERSION
        elif private_slice.get("slice_type") == "text_excerpt":
            enriched.update(
                self._text_provenance(
                    private_slice=private_slice,
                    source_checksum_ref=source_checksum_ref,
                    parser_ref=parser_ref,
                )
            )
            enriched["schema_version"] = TEXT_SLICE_SCHEMA_VERSION
        elif private_slice.get("slice_type") == "visual_page":
            enriched.update(
                self._visual_provenance(
                    private_slice=private_slice,
                    source_checksum_ref=source_checksum_ref,
                    parser_ref=parser_ref,
                )
            )
            enriched["schema_version"] = VISUAL_SLICE_SCHEMA_VERSION
        elif private_slice.get("slice_type") == "visual_media":
            enriched.update(
                self._visual_media_provenance(
                    private_slice=private_slice,
                    source_checksum_ref=source_checksum_ref,
                    parser_ref=parser_ref,
                )
            )
            enriched["schema_version"] = VISUAL_SLICE_SCHEMA_VERSION
        else:
            raise ValueError("unsupported_private_slice_type")
        enriched.update(common)
        return enriched

    def _table_provenance(
        self,
        *,
        private_slice: dict[str, Any],
        source_checksum_ref: str,
        parser_ref: str,
    ) -> dict[str, Any]:
        slice_id = str(private_slice["slice_id"])
        rows = _table_rows(private_slice)
        row_start = _row_start(private_slice)
        table_ref = _ref(
            "table",
            source_checksum_ref,
            slice_id,
            _canonical_json(private_slice.get("source_location") or {}),
            length=24,
        )
        row_range_ref = _ref(
            "rowrange",
            table_ref,
            row_start,
            row_start + max(len(rows) - 1, 0),
            length=24,
        )

        row_refs: list[str] = []
        cell_refs: list[str] = []
        cell_value_refs: list[str] = []
        source_value_refs: list[str] = []
        row_provenance: list[dict[str, Any]] = []
        cell_provenance: list[dict[str, Any]] = []
        source_value_index: list[dict[str, Any]] = []
        header_descriptors: list[dict[str, Any]] = []
        coverage_buckets: dict[str, list[str]] = {
            "header_candidate_refs": [],
            "blank_refs": [],
            "layout_candidate_refs": [],
            "fact_candidate_refs": [],
        }
        header_row_index = _first_nonblank_row_index(rows)

        for row_index, row in enumerate(rows):
            row_ordinal = row_start + row_index
            row_checksum_ref = _checksum_ref("rowchk", row)
            row_ref = _ref(
                "row",
                table_ref,
                row_ordinal,
                row_checksum_ref,
                length=24,
            )
            row_refs.append(row_ref)
            row_kind = _row_kind(row, is_header_candidate=row_index == header_row_index)
            coverage_buckets[f"{row_kind}_refs"].append(row_ref)
            current_cell_refs: list[str] = []
            current_value_refs: list[str] = []

            for column_index, value in enumerate(row):
                column_ordinal = column_index + 1
                value_checksum_ref = _checksum_ref("valuechk", value)
                cell_ref = _ref(
                    "cell",
                    row_ref,
                    column_ordinal,
                    length=24,
                )
                cell_value_ref = _ref(
                    "cellval",
                    cell_ref,
                    value_checksum_ref,
                    length=24,
                )
                source_value_ref = _ref(
                    "srcval",
                    source_checksum_ref,
                    slice_id,
                    row_ordinal,
                    column_ordinal,
                    value_checksum_ref,
                    length=24,
                )
                cell_refs.append(cell_ref)
                cell_value_refs.append(cell_value_ref)
                source_value_refs.append(source_value_ref)
                current_cell_refs.append(cell_ref)
                current_value_refs.append(source_value_ref)
                cell_provenance.append(
                    {
                        "cell_ref": cell_ref,
                        "cell_value_ref": cell_value_ref,
                        "source_value_ref": source_value_ref,
                        "row_ref": row_ref,
                        "row_ordinal": row_ordinal,
                        "column_ordinal": column_ordinal,
                        "value_checksum_ref": value_checksum_ref,
                    }
                )
                source_value_index.append(
                    {
                        "source_value_ref": source_value_ref,
                        "cell_ref": cell_ref,
                        "cell_value_ref": cell_value_ref,
                        "value_path": {
                            "kind": "table_cell",
                            "row_index": row_index,
                            "column_index": column_index,
                        },
                        "value_checksum_ref": value_checksum_ref,
                    }
                )
                if row_index == header_row_index:
                    header_descriptors.append(
                        {
                            "header_ref": _ref("header", table_ref, column_ordinal, length=20),
                            "column_ordinal": column_ordinal,
                            "cell_ref": cell_ref,
                            "source_value_ref": source_value_ref,
                            "normalized_label": _normalized_header_signal(value),
                            "label_policy": "safe_signal_or_unknown_v0",
                        }
                    )

            row_provenance.append(
                {
                    "row_ref": row_ref,
                    "row_range_ref": row_range_ref,
                    "row_ordinal": row_ordinal,
                    "row_kind": row_kind.removesuffix("_candidate"),
                    "row_checksum_ref": row_checksum_ref,
                    "cell_refs": current_cell_refs,
                    "source_value_refs": current_value_refs,
                }
            )

        coverage_ref = _ref("coverage", table_ref, *row_refs, length=24)
        coverage = {
            "schema_version": COVERAGE_SCHEMA_VERSION,
            "coverage_ref": coverage_ref,
            "unit_kind": "table_row_window",
            "selected_source_refs": list(row_refs),
            **coverage_buckets,
            "selected_total": len(row_refs),
            "accounted_total": sum(len(items) for items in coverage_buckets.values()),
            "all_selected_refs_accounted": len(row_refs)
            == sum(len(items) for items in coverage_buckets.values()),
        }
        slice_payload_checksum_ref = _checksum_ref(
            "slicepayload",
            {
                "slice_id": slice_id,
                "rows": rows,
                "source_location": private_slice.get("source_location") or {},
                "parser_ref": parser_ref,
            },
        )
        return {
            "table_ref": table_ref,
            "row_refs": row_refs,
            "row_range_ref": row_range_ref,
            "cell_refs": cell_refs,
            "cell_value_refs": cell_value_refs,
            "source_value_refs": source_value_refs,
            "normalized_header_descriptors": header_descriptors,
            "row_provenance": row_provenance,
            "cell_provenance": cell_provenance,
            "source_value_index": source_value_index,
            "slice_payload_checksum_ref": slice_payload_checksum_ref,
            "safe_coverage_refs": list(row_refs),
            "coverage": coverage,
        }

    def _visual_provenance(
        self,
        *,
        private_slice: dict[str, Any],
        source_checksum_ref: str,
        parser_ref: str,
    ) -> dict[str, Any]:
        slice_id = str(private_slice["slice_id"])
        source_location = (
            private_slice.get("source_location")
            if isinstance(private_slice.get("source_location"), dict)
            else {}
        )
        page_number = int(source_location.get("page") or 0)
        if page_number <= 0:
            raise ValueError("visual_page_number_required")
        encoded = str(private_slice.get("private_media_base64") or "")
        try:
            media_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("visual_media_base64_invalid") from exc
        if not media_bytes:
            raise ValueError("visual_media_bytes_required")
        media_sha256 = hashlib.sha256(media_bytes).hexdigest()
        if private_slice.get("private_media_sha256") != media_sha256:
            raise ValueError("visual_media_checksum_mismatch")
        page_ref = _ref(
            "page",
            source_checksum_ref,
            page_number,
            length=20,
        )
        media_ref = _ref(
            "visual",
            source_checksum_ref,
            page_number,
            media_sha256,
            length=24,
        )
        media_checksum_ref = _ref(
            "mediachk",
            media_sha256,
            len(media_bytes),
            length=24,
        )
        coverage_ref = _ref("coverage", slice_id, page_ref, media_ref, length=24)
        coverage = {
            "schema_version": COVERAGE_SCHEMA_VERSION,
            "coverage_ref": coverage_ref,
            "unit_kind": "visual_page",
            "selected_source_refs": [page_ref],
            "visual_page_refs": [page_ref],
            "selected_total": 1,
            "accounted_total": 1,
            "all_selected_refs_accounted": True,
        }
        slice_payload_checksum_ref = _checksum_ref(
            "slicepayload",
            {
                "slice_id": slice_id,
                "media_sha256": media_sha256,
                "media_type": private_slice.get("media_type"),
                "source_location": private_slice.get("source_location") or {},
                "parser_ref": parser_ref,
            },
        )
        return {
            "page_refs": [page_ref],
            "media_ref": media_ref,
            "media_checksum_ref": media_checksum_ref,
            "source_value_refs": [],
            "source_value_index": [],
            "slice_payload_checksum_ref": slice_payload_checksum_ref,
            "safe_coverage_refs": [page_ref],
            "coverage": coverage,
        }

    def _visual_media_provenance(
        self,
        *,
        private_slice: dict[str, Any],
        source_checksum_ref: str,
        parser_ref: str,
    ) -> dict[str, Any]:
        slice_id = str(private_slice["slice_id"])
        source_location = (
            private_slice.get("source_location")
            if isinstance(private_slice.get("source_location"), dict)
            else {}
        )
        media_ordinal = int(source_location.get("media_ordinal") or 0)
        if media_ordinal <= 0:
            raise ValueError("visual_media_ordinal_required")
        encoded = str(private_slice.get("private_media_base64") or "")
        try:
            media_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("visual_media_base64_invalid") from exc
        if not media_bytes:
            raise ValueError("visual_media_bytes_required")
        media_sha256 = hashlib.sha256(media_bytes).hexdigest()
        if private_slice.get("private_media_sha256") != media_sha256:
            raise ValueError("visual_media_checksum_mismatch")
        media_item_ref = _ref(
            "mediaitem", source_checksum_ref, media_ordinal, length=20
        )
        media_ref = _ref(
            "visual",
            source_checksum_ref,
            media_ordinal,
            media_sha256,
            length=24,
        )
        media_checksum_ref = _ref(
            "mediachk", media_sha256, len(media_bytes), length=24
        )
        coverage_ref = _ref(
            "coverage", slice_id, media_item_ref, media_ref, length=24
        )
        coverage = {
            "schema_version": COVERAGE_SCHEMA_VERSION,
            "coverage_ref": coverage_ref,
            "unit_kind": "visual_media",
            "selected_source_refs": [media_item_ref],
            "visual_media_refs": [media_item_ref],
            "selected_total": 1,
            "accounted_total": 1,
            "all_selected_refs_accounted": True,
        }
        slice_payload_checksum_ref = _checksum_ref(
            "slicepayload",
            {
                "slice_id": slice_id,
                "media_sha256": media_sha256,
                "media_type": private_slice.get("media_type"),
                "source_location": source_location,
                "parser_ref": parser_ref,
            },
        )
        return {
            "media_item_refs": [media_item_ref],
            "media_ref": media_ref,
            "media_checksum_ref": media_checksum_ref,
            "source_value_refs": [],
            "source_value_index": [],
            "slice_payload_checksum_ref": slice_payload_checksum_ref,
            "safe_coverage_refs": [media_item_ref],
            "coverage": coverage,
        }

    def _text_provenance(
        self,
        *,
        private_slice: dict[str, Any],
        source_checksum_ref: str,
        parser_ref: str,
    ) -> dict[str, Any]:
        slice_id = str(private_slice["slice_id"])
        text = str(private_slice.get("text") or "")
        lines = text.splitlines(keepends=True)
        if text and not lines:
            lines = [text]
        if lines and "".join(lines) != text:
            lines = [text]

        segment_provenance: list[dict[str, Any]] = []
        text_segment_refs: list[str] = []
        section_refs: list[str] = []
        character_span_refs: list[str] = []
        source_value_refs: list[str] = []
        source_value_index: list[dict[str, Any]] = []
        safe_section_labels: list[str] = []
        blank_refs: list[str] = []
        text_candidate_refs: list[str] = []
        current_offset = 0
        section_ordinal = 0
        in_section = False

        for segment_index, segment in enumerate(lines):
            start = current_offset
            end = start + len(segment)
            current_offset = end
            blank = not segment.strip()
            if not blank and not in_section:
                section_ordinal += 1
                in_section = True
            elif blank:
                in_section = False
            effective_section = max(section_ordinal, 1)
            section_ref = _ref("section", slice_id, effective_section, length=20)
            safe_section_label = f"section_{effective_section:03d}"
            value_checksum_ref = _checksum_ref("valuechk", segment)
            char_span_ref = _ref("charspan", slice_id, start, end, value_checksum_ref, length=24)
            text_segment_ref = _ref(
                "textseg",
                source_checksum_ref,
                slice_id,
                segment_index + 1,
                char_span_ref,
                length=24,
            )
            source_value_ref = _ref(
                "srcval",
                source_checksum_ref,
                slice_id,
                char_span_ref,
                value_checksum_ref,
                length=24,
            )
            text_segment_refs.append(text_segment_ref)
            character_span_refs.append(char_span_ref)
            source_value_refs.append(source_value_ref)
            if section_ref not in section_refs:
                section_refs.append(section_ref)
                safe_section_labels.append(safe_section_label)
            (blank_refs if blank else text_candidate_refs).append(text_segment_ref)
            segment_provenance.append(
                {
                    "text_segment_ref": text_segment_ref,
                    "section_ref": section_ref,
                    "safe_section_label": safe_section_label,
                    "page_ref": _single_page_ref(private_slice, source_checksum_ref),
                    "page_range_ref": _page_range_ref(private_slice, source_checksum_ref),
                    "character_span_ref": char_span_ref,
                    "character_start": start,
                    "character_end": end,
                    "segment_kind": "blank" if blank else "text_candidate",
                    "source_value_ref": source_value_ref,
                    "value_checksum_ref": value_checksum_ref,
                }
            )
            source_value_index.append(
                {
                    "source_value_ref": source_value_ref,
                    "text_segment_ref": text_segment_ref,
                    "value_path": {
                        "kind": "text_span",
                        "character_start": start,
                        "character_end": end,
                    },
                    "value_checksum_ref": value_checksum_ref,
                }
            )

        coverage_ref = _ref("coverage", slice_id, *text_segment_refs, length=24)
        coverage = {
            "schema_version": COVERAGE_SCHEMA_VERSION,
            "coverage_ref": coverage_ref,
            "unit_kind": "text_slice",
            "selected_source_refs": list(text_segment_refs),
            "blank_refs": blank_refs,
            "text_candidate_refs": text_candidate_refs,
            "selected_total": len(text_segment_refs),
            "accounted_total": len(blank_refs) + len(text_candidate_refs),
            "all_selected_refs_accounted": len(text_segment_refs)
            == len(blank_refs) + len(text_candidate_refs),
        }
        slice_payload_checksum_ref = _checksum_ref(
            "slicepayload",
            {
                "slice_id": slice_id,
                "text": text,
                "source_location": private_slice.get("source_location") or {},
                "parser_ref": parser_ref,
            },
        )
        page_refs = [page_ref] if (page_ref := _single_page_ref(private_slice, source_checksum_ref)) else []
        return {
            "text_segment_refs": text_segment_refs,
            "section_refs": section_refs,
            "page_refs": page_refs,
            "page_range_ref": _page_range_ref(private_slice, source_checksum_ref),
            "character_span_refs": character_span_refs,
            "segment_provenance": segment_provenance,
            "source_value_refs": source_value_refs,
            "source_value_index": source_value_index,
            "slice_payload_checksum_ref": slice_payload_checksum_ref,
            "safe_section_labels": safe_section_labels,
            "safe_coverage_refs": list(text_segment_refs),
            "coverage": coverage,
        }


def validate_normalized_slice_provenance(
    *,
    private_slice: dict[str, Any],
    normalization_run_id: str,
    document_id: str,
    source_checksum_sha256: str,
) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    slice_id = str(private_slice.get("slice_id") or "")
    try:
        expected = NormalizedSliceProvenanceFactory().create().enrich_slice(
            normalization_run_id=normalization_run_id,
            document_id=document_id,
            source_checksum_sha256=source_checksum_sha256,
            private_slice=private_slice,
        )
        if private_slice.get("schema_version") == "private_normalized_source_unit_v0":
            expected["schema_version"] = "private_normalized_source_unit_v0"
    except ValueError as exc:
        return _validation_result(
            errors=[{"code": str(exc), "subject": slice_id}],
            private_slice=private_slice,
        )

    if private_slice.get("slice_type") == "table_rows":
        fields = _TABLE_PROVENANCE_FIELDS
    elif private_slice.get("slice_type") == "visual_page":
        fields = _VISUAL_PROVENANCE_FIELDS
    elif private_slice.get("slice_type") == "visual_media":
        fields = _VISUAL_MEDIA_PROVENANCE_FIELDS
    else:
        fields = _TEXT_PROVENANCE_FIELDS
    for field in sorted(fields):
        if field not in private_slice:
            errors.append({"code": "slice_provenance_field_missing", "subject": f"{slice_id}:{field}"})
        elif private_slice.get(field) != expected.get(field):
            errors.append({"code": "slice_provenance_field_mismatch", "subject": f"{slice_id}:{field}"})

    coverage = private_slice.get("coverage") if isinstance(private_slice.get("coverage"), dict) else {}
    if coverage.get("all_selected_refs_accounted") is not True:
        errors.append({"code": "slice_coverage_incomplete", "subject": slice_id})
    if coverage.get("selected_total") != coverage.get("accounted_total"):
        errors.append({"code": "slice_coverage_count_mismatch", "subject": slice_id})
    if len(set(private_slice.get("source_value_refs") or [])) != len(private_slice.get("source_value_refs") or []):
        errors.append({"code": "slice_source_value_ref_duplicate", "subject": slice_id})
    source_value_entries: dict[str, list[dict[str, Any]]] = {}
    for item in private_slice.get("source_value_index") or []:
        if not isinstance(item, dict):
            continue
        source_value_ref = str(item.get("source_value_ref") or "")
        if source_value_ref:
            source_value_entries.setdefault(source_value_ref, []).append(item)
    for source_value_ref in private_slice.get("source_value_refs") or []:
        matches = source_value_entries.get(str(source_value_ref), [])
        if len(matches) != 1:
            errors.append(
                {
                    "code": "source_value_ref_not_unique_or_missing",
                    "subject": str(source_value_ref),
                }
            )
            continue
        try:
            _resolve_source_value_entry(private_slice, matches[0])
        except ValueError as exc:
            errors.append({"code": str(exc), "subject": str(source_value_ref)})
    return _validation_result(errors=errors, private_slice=private_slice)


def resolve_source_value(private_slice: dict[str, Any], source_value_ref: str) -> Any:
    matches = [
        item
        for item in private_slice.get("source_value_index") or []
        if isinstance(item, dict) and item.get("source_value_ref") == source_value_ref
    ]
    if len(matches) != 1:
        raise ValueError("source_value_ref_not_unique_or_missing")
    return _resolve_source_value_entry(private_slice, matches[0])


def resolve_source_values(
    private_slice: dict[str, Any], source_value_refs: list[str]
) -> dict[str, Any]:
    entries: dict[str, list[dict[str, Any]]] = {}
    for item in private_slice.get("source_value_index") or []:
        if not isinstance(item, dict):
            continue
        source_value_ref = str(item.get("source_value_ref") or "")
        if source_value_ref:
            entries.setdefault(source_value_ref, []).append(item)
    resolved: dict[str, Any] = {}
    for source_value_ref in source_value_refs:
        matches = entries.get(str(source_value_ref), [])
        if len(matches) != 1:
            raise ValueError("source_value_ref_not_unique_or_missing")
        resolved[str(source_value_ref)] = _resolve_source_value_entry(
            private_slice, matches[0]
        )
    return resolved


def _resolve_source_value_entry(
    private_slice: dict[str, Any], entry: dict[str, Any]
) -> Any:
    path = entry.get("value_path") if isinstance(entry.get("value_path"), dict) else {}
    if path.get("kind") == "table_cell":
        rows = _table_rows(private_slice)
        row_index = int(path.get("row_index"))
        column_index = int(path.get("column_index"))
        try:
            value = rows[row_index][column_index]
        except (IndexError, TypeError):
            raise ValueError("source_value_path_invalid") from None
    elif path.get("kind") == "text_span":
        text = str(private_slice.get("text") or "")
        start = int(path.get("character_start"))
        end = int(path.get("character_end"))
        if start < 0 or end < start or end > len(text):
            raise ValueError("source_value_path_invalid")
        value = text[start:end]
    elif path.get("kind") == "table_projection_private_value":
        value_path_ref = str(path.get("value_path_ref") or "")
        matches = [
            item
            for item in private_slice.get("private_values") or []
            if isinstance(item, dict)
            and str(item.get("value_path_ref") or "") == value_path_ref
        ]
        if not value_path_ref or len(matches) != 1:
            raise ValueError("source_value_path_invalid")
        value = matches[0].get("normalized_value")
    else:
        raise ValueError("source_value_path_kind_invalid")
    if entry.get("value_checksum_ref") != _checksum_ref("valuechk", value):
        raise ValueError("source_value_checksum_mismatch")
    return value


def reproduce_normalized_value(
    private_slice: dict[str, Any],
    source_value_ref: str,
    normalization_kind: str,
) -> str:
    value = resolve_source_value(private_slice, source_value_ref)
    text = str(value or "")
    if normalization_kind == "trimmed_text":
        return text.strip()
    if normalization_kind == "decimal_dot":
        candidate = text.strip().replace(" ", "")
        if "," in candidate or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", candidate):
            raise ValueError("normalized_decimal_not_mechanically_reproducible")
        try:
            normalized = Decimal(candidate)
        except InvalidOperation:
            raise ValueError("normalized_decimal_not_mechanically_reproducible") from None
        return format(normalized, "f")
    if normalization_kind == "iso_date_exact":
        candidate = text.strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            raise ValueError("normalized_date_not_mechanically_reproducible")
        return candidate
    if normalization_kind == "currency_code_visible":
        candidate = text.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", candidate):
            raise ValueError("normalized_currency_not_mechanically_reproducible")
        return candidate
    raise ValueError("unsupported_mechanical_normalization_kind")


def _validation_result(*, errors: list[dict[str, str]], private_slice: dict[str, Any]) -> dict[str, Any]:
    coverage = private_slice.get("coverage") if isinstance(private_slice.get("coverage"), dict) else {}
    return {
        "schema_version": "source_unit_provenance_validation_v0",
        "slice_id": private_slice.get("slice_id"),
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "errors_count": len(errors),
        "errors": errors,
        "source_value_refs_total": len(private_slice.get("source_value_refs") or []),
        "coverage_selected_total": int(coverage.get("selected_total") or 0),
        "coverage_accounted_total": int(coverage.get("accounted_total") or 0),
    }


def _table_rows(private_slice: dict[str, Any]) -> list[list[Any]]:
    rows = private_slice.get("cells")
    if not isinstance(rows, list):
        rows = private_slice.get("rows")
    if not isinstance(rows, list):
        return []
    return [list(row) if isinstance(row, list) else [row] for row in rows]


def _row_start(private_slice: dict[str, Any]) -> int:
    row_range = private_slice.get("row_range")
    if isinstance(row_range, list) and row_range:
        try:
            return int(row_range[0])
        except (TypeError, ValueError):
            pass
    location = private_slice.get("source_location") if isinstance(private_slice.get("source_location"), dict) else {}
    for key in ("start_row", "row_start"):
        try:
            return int(location.get(key))
        except (TypeError, ValueError):
            continue
    return 1


def _first_nonblank_row_index(rows: list[list[Any]]) -> int:
    for index, row in enumerate(rows):
        if any(str(value or "").strip() for value in row):
            return index
    return -1


def _row_kind(row: list[Any], *, is_header_candidate: bool) -> str:
    nonblank = sum(1 for value in row if str(value or "").strip())
    if nonblank == 0:
        return "blank"
    if is_header_candidate:
        return "header_candidate"
    if nonblank == 1:
        return "layout_candidate"
    return "fact_candidate"


def _normalized_header_signal(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    signals = {
        "date": ("date", "trade_date", "payment_date"),
        "amount": ("amount", "value", "sum", "total"),
        "currency": ("currency", "ccy"),
        "quantity": ("quantity", "qty", "units"),
        "instrument": (
            "instrument",
            "identifier",
            "isin",
            "ticker",
            "security",
        ),
        "operation": ("operation", "type", "side", "action"),
    }
    for label, candidates in signals.items():
        if any(candidate in text for candidate in candidates):
            return label
    return "unknown"


def _single_page_ref(private_slice: dict[str, Any], source_checksum_ref: str) -> str | None:
    location = private_slice.get("source_location") if isinstance(private_slice.get("source_location"), dict) else {}
    page_start = location.get("page_start") or location.get("page")
    page_end = location.get("page_end") or page_start
    if page_start and page_end and str(page_start) == str(page_end):
        return _ref("page", source_checksum_ref, page_start, length=20)
    return None


def _page_range_ref(private_slice: dict[str, Any], source_checksum_ref: str) -> str | None:
    location = private_slice.get("source_location") if isinstance(private_slice.get("source_location"), dict) else {}
    page_start = location.get("page_start") or location.get("page")
    page_end = location.get("page_end") or page_start
    if page_start and page_end:
        return _ref("pagerange", source_checksum_ref, page_start, page_end, length=20)
    return None


def _checksum_ref(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _ref(prefix: str, *parts: Any, length: int) -> str:
    return f"{prefix}_{stable_digest(parts, length=length)}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
