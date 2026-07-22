from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .broker_pdf_neutral_tables import (
    PROFILE_ID as BROKER_PDF_NEUTRAL_PROFILE_ID,
    BrokerPdfNeutralTableFactory,
    validate_canonical_integrity,
    validate_canonical_neutral_projection,
)
from .contracts import stable_digest
from .source_provenance import resolve_source_values, validate_source_value_refs
from .semantic_visual_table_contracts import SEMANTIC_LOGICAL_TABLE_PROFILE_ID
from .semantic_visual_table_projection_contracts import (
    validate_semantic_visual_table_projection,
)


FACTORY_REQUIRED = (
    "NormalizedTableProjectionFactory.create is the only production normalized-table projection entrypoint"
)
FORBIDDEN = (
    "Normalizers, Gate 2 callers and smoke scripts must not mint replacement row, cell or source-value refs or treat PDF geometry as semantic table truth"
)

TABLE_PROJECTION_SCHEMA_VERSION = "broker_reports_normalized_table_projection_v0"
TABLE_COVERAGE_SCHEMA_VERSION = "broker_reports_table_projection_coverage_v0"
TABLE_QUALITY_SCHEMA_VERSION = "broker_reports_table_reconstruction_quality_v0"

SOURCE_FORMATS = {"csv", "html", "xlsx", "pdf", "xml", "txt", "unknown"}
ROW_ROLES = {
    "header_row",
    "data_row",
    "summary_row",
    "subtotal_row",
    "footer_row",
    "repeated_header_row",
    "blank_row",
    "layout_row",
    "unknown_row_role",
}
PDF_STATUSES = {
    "candidate",
    "canonical_table_accepted",
    "validated_geometry",
    "rejected_to_line_cluster",
    "partial",
    "blocked",
}


@dataclass(frozen=True)
class NormalizedTableProjectionConfig:
    max_rows: int = 10_000
    max_cells: int = 100_000
    max_payload_bytes: int = 20_000_000
    min_pdf_geometry_confidence: float = 0.90
    broker_pdf_neutral_table_profile_v1_enabled: bool = False


@dataclass(frozen=True)
class TableProjectionBuildResult:
    projections: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    safe_summary: dict[str, Any]


class NormalizedTableProjectionFactory:
    def __init__(
        self, config: NormalizedTableProjectionConfig | None = None
    ) -> None:
        self.config = config or NormalizedTableProjectionConfig()

    def create(self) -> "NormalizedTableProjectionService":
        if self.config.max_rows <= 0:
            raise ValueError("table_projection_row_budget_invalid")
        if self.config.max_cells <= 0:
            raise ValueError("table_projection_cell_budget_invalid")
        if self.config.max_payload_bytes <= 0:
            raise ValueError("table_projection_payload_budget_invalid")
        if not 0.0 <= self.config.min_pdf_geometry_confidence <= 1.0:
            raise ValueError("table_projection_pdf_confidence_invalid")
        return NormalizedTableProjectionService(self.config)


class NormalizedTableProjectionService:
    def __init__(self, config: NormalizedTableProjectionConfig) -> None:
        self.config = config
        self.native_builders = {
            "csv": CsvTableProjectionBuilder(config),
            "html": HtmlTableProjectionBuilder(config),
            "xlsx": XlsxTableProjectionBuilder(config),
            "xml": XmlTableProjectionBuilder(config),
        }
        self.pdf_builder = PdfTableCandidateProjectionBuilder(config)
        self.broker_pdf_neutral_builder = (
            BrokerPdfNeutralTableFactory().create()
            if config.broker_pdf_neutral_table_profile_v1_enabled
            else None
        )
        self.validator = TableProjectionValidator()

    def build_for_document(
        self,
        *,
        source_format: str,
        payloads: list[dict[str, Any]],
        source_units: list[dict[str, Any]],
    ) -> TableProjectionBuildResult:
        normalized_format = "html" if source_format == "html_text" else source_format
        projections: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        payload_by_ref = {
            str(item.get("source_payload_ref") or ""): item
            for item in payloads
            if isinstance(item, dict) and item.get("source_payload_ref")
        }
        broker_profile = (
            self.broker_pdf_neutral_builder.build_for_document(
                payloads=payloads,
                source_units=source_units,
            )
            if normalized_format == "pdf"
            and self.broker_pdf_neutral_builder is not None
            else None
        )
        for unit in source_units:
            if not isinstance(unit, dict):
                continue
            if unit.get("pdf_unit_type") == "pdf_table_candidate_unit":
                unit_ref = str(unit.get("unit_ref") or "")
                if broker_profile and unit_ref in broker_profile.projections_by_unit_ref:
                    projection = _finish_projection(
                        broker_profile.projections_by_unit_ref[unit_ref]
                    )
                else:
                    projection = self.pdf_builder.build(
                        source_unit=unit,
                        parent_payload=payload_by_ref.get(
                            str(unit.get("parent_payload_ref") or "")
                        ),
                    )
            elif unit.get("slice_type") == "table_rows":
                builder = self.native_builders.get(normalized_format)
                if builder is None:
                    decisions.append(
                        _decision(
                            unit,
                            status="blocked",
                            reason_codes=["table_projection_source_format_unsupported"],
                        )
                    )
                    continue
                projection = builder.build(source_unit=unit)
            else:
                continue
            validation = self.validator.validate(projection)
            projection["validator_status"] = validation["validator_status"]
            projection["validator_reason_codes"] = sorted(
                {str(item.get("code") or "") for item in validation["errors"]}
            )
            projections.append(projection)
            unit_ref = str(unit.get("unit_ref") or "")
            if broker_profile and unit_ref in broker_profile.decisions_by_unit_ref:
                decision = copy.deepcopy(broker_profile.decisions_by_unit_ref[unit_ref])
                if validation["validator_status"] != "passed":
                    decision["status"] = "blocked"
                    decision["reason_codes"] = sorted(
                        set(
                            list(decision.get("reason_codes") or [])
                            + list(projection.get("validator_reason_codes") or [])
                        )
                    )
                decisions.append(decision)
            else:
                decisions.append(
                    _decision(
                        unit,
                        status=(
                            str(projection.get("table_candidate_status") or "ready")
                        ),
                        reason_codes=[
                            *list(projection.get("reconstruction_reason_codes") or []),
                            *list(projection.get("validator_reason_codes") or []),
                        ],
                        projection_ref=projection.get("table_projection_id"),
                    )
                )
        summary = _safe_summary(projections, decisions)
        return TableProjectionBuildResult(
            projections=projections,
            decisions=decisions,
            safe_summary=summary,
        )


class _NativeTableProjectionBuilder:
    source_format = "unknown"

    def __init__(self, config: NormalizedTableProjectionConfig) -> None:
        self.config = config

    def build(self, *, source_unit: dict[str, Any]) -> dict[str, Any]:
        rows = _rows_from_unit(source_unit)
        row_provenance = _dicts(source_unit.get("row_provenance"))
        cell_provenance = _dicts(source_unit.get("cell_provenance"))
        row_count = len(row_provenance)
        cell_count = len(cell_provenance)
        budget_reasons = _budget_reasons(
            rows=row_count,
            cells=cell_count,
            payload_bytes=len(_canonical_bytes(rows)),
            config=self.config,
        )
        table_ref = str(source_unit.get("table_ref") or "")
        projection_id = "tableproj_" + stable_digest(
            [
                TABLE_PROJECTION_SCHEMA_VERSION,
                source_unit.get("unit_ref"),
                table_ref,
                source_unit.get("slice_payload_checksum_ref"),
            ],
            length=24,
        )
        max_columns = max((len(row) for row in rows), default=0)
        column_refs = [
            "tablecol_" + stable_digest([table_ref, ordinal], length=24)
            for ordinal in range(1, max_columns + 1)
        ]
        provenance_by_cell = {
            str(item.get("cell_ref") or ""): item for item in cell_provenance
        }
        cells: list[dict[str, Any]] = []
        private_values: list[dict[str, Any]] = []
        source_value_index: list[dict[str, Any]] = []
        source_value_refs = [
            str(item.get("source_value_ref") or "") for item in cell_provenance
        ]
        resolved_values = resolve_source_values(source_unit, source_value_refs)
        for item in cell_provenance:
            cell_ref = str(item.get("cell_ref") or "")
            source_value_ref = str(item.get("source_value_ref") or "")
            value = resolved_values[source_value_ref]
            value_text = "" if value is None else str(value)
            value_path_ref = "tablevaluepath_" + stable_digest(
                [projection_id, cell_ref, source_value_ref], length=24
            )
            cells.append(
                {
                    "cell_ref": cell_ref,
                    "row_ref": item.get("row_ref"),
                    "column_ref": column_refs[int(item.get("column_ordinal") or 1) - 1],
                    "row_ordinal": int(item.get("row_ordinal") or 0),
                    "column_ordinal": int(item.get("column_ordinal") or 0),
                    "source_value_refs": [source_value_ref],
                    "cell_value_ref": item.get("cell_value_ref"),
                    "normalized_private_value_path": value_path_ref,
                    "value_checksum_ref": item.get("value_checksum_ref"),
                    "value_kind_hints": _value_kind_hints(value_text),
                    "bbox_ref": None,
                    "row_span": 1,
                    "column_span": 1,
                    "merged_cell_group_ref": None,
                    "split_cell_candidate": False,
                    "multi_line_cell": "\n" in value_text,
                    "wrapped_text_cell": False,
                    "ambiguous_cell_boundary": False,
                    "empty_cell": not value_text.strip(),
                    "confidence": "high",
                    "reason_codes": [],
                }
            )
            private_values.append(
                {
                    "value_path_ref": value_path_ref,
                    "normalized_value": copy.deepcopy(value),
                    "value_checksum_ref": item.get("value_checksum_ref"),
                    "source_value_refs": [source_value_ref],
                }
            )
            source_value_index.append(
                {
                    "source_value_ref": source_value_ref,
                    "cell_ref": cell_ref,
                    "cell_value_ref": item.get("cell_value_ref"),
                    "value_path": {
                        "kind": "table_projection_private_value",
                        "value_path_ref": value_path_ref,
                    },
                    "value_checksum_ref": item.get("value_checksum_ref"),
                }
            )
        roles = _classify_rows(
            row_provenance=row_provenance,
            cells=cells,
            private_values=private_values,
        )
        normalized_rows = []
        for item in row_provenance:
            row_ref = str(item.get("row_ref") or "")
            normalized_rows.append(
                {
                    "row_ref": row_ref,
                    "row_ordinal": int(item.get("row_ordinal") or 0),
                    "cell_refs": [
                        ref
                        for ref in _strings(item.get("cell_refs"))
                        if ref in provenance_by_cell
                    ],
                    "row_role": roles.get(row_ref, "unknown_row_role"),
                    "row_checksum_ref": item.get("row_checksum_ref"),
                    "reason_codes": [],
                }
            )
        headers = _header_model(
            rows=normalized_rows,
            cells=cells,
            private_values=private_values,
            column_refs=column_refs,
            pdf_candidate=False,
        )
        source_selected = _strings(
            _object(source_unit.get("coverage")).get("selected_source_refs")
        )
        quality = _quality(
            rows=normalized_rows,
            cells=cells,
            coverage_complete=True,
            geometry_confidence=None,
            blocked=bool(budget_reasons),
        )
        projection = _base_projection(
            projection_id=projection_id,
            table_ref=table_ref,
            source_format=self.source_format,
            table_origin="native_table",
            source_unit=source_unit,
            row_refs=[str(item.get("row_ref") or "") for item in normalized_rows],
            column_refs=column_refs,
            cells=cells,
            rows=normalized_rows,
            private_values=private_values,
            source_value_index=source_value_index,
            headers=headers,
            coverage=_coverage(
                projection_id=projection_id,
                selected=source_selected,
                table_owned=source_selected,
            ),
            quality=quality,
            page_refs=[],
            sheet_refs=_sheet_refs(source_unit),
            section_refs=[],
            table_bbox_ref=None,
            table_candidate_status=None,
            reconstruction_strategy="parser_native",
            reconstruction_reason_codes=budget_reasons,
        )
        if budget_reasons:
            projection["projection_status"] = "blocked"
            projection["reconstruction_quality"] = "blocked"
        return _finish_projection(_apply_serialized_budget(projection, self.config))


class CsvTableProjectionBuilder(_NativeTableProjectionBuilder):
    source_format = "csv"


class HtmlTableProjectionBuilder(_NativeTableProjectionBuilder):
    source_format = "html"


class XlsxTableProjectionBuilder(_NativeTableProjectionBuilder):
    source_format = "xlsx"


class XmlTableProjectionBuilder(_NativeTableProjectionBuilder):
    source_format = "xml"


class PdfTableCandidateProjectionBuilder:
    def __init__(self, config: NormalizedTableProjectionConfig) -> None:
        self.config = config

    def build(
        self,
        *,
        source_unit: dict[str, Any],
        parent_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        candidate_ref = str(source_unit.get("table_candidate_ref") or "")
        projection_id = "tableproj_" + stable_digest(
            [
                TABLE_PROJECTION_SCHEMA_VERSION,
                source_unit.get("unit_ref"),
                candidate_ref,
                source_unit.get("pdf_layout_unit_checksum_ref"),
            ],
            length=24,
        )
        parent_projection = _object(
            _object(parent_payload).get("pdf_text_layer_projection")
        )
        candidates = _dicts(parent_projection.get("table_candidate_inventory"))
        candidate = next(
            (
                item
                for item in candidates
                if str(item.get("table_candidate_ref") or "") == candidate_ref
            ),
            None,
        )
        words = {
            str(item.get("word_ref") or ""): item
            for item in _dicts(parent_projection.get("word_inventory"))
        }
        bboxes = {
            str(item.get("bbox_ref") or ""): item
            for item in _dicts(parent_projection.get("bbox_inventory"))
        }
        reasons = _pdf_geometry_reasons(
            source_unit=source_unit,
            candidate=candidate,
            words=words,
            min_confidence=self.config.min_pdf_geometry_confidence,
        )
        candidate_rows = _dicts(_object(candidate).get("row_inventory"))
        candidate_cells = _dicts(_object(candidate).get("cell_inventory"))
        budget_reasons = _budget_reasons(
            rows=len(candidate_rows),
            cells=len(candidate_cells),
            payload_bytes=len(_canonical_bytes(candidate or {})),
            config=self.config,
        )
        reasons = sorted(set([*reasons, *budget_reasons]))
        selected = _strings(
            _object(source_unit.get("pdf_layout_coverage")).get(
                "selected_source_refs"
            )
        )
        fallback_text_refs = _strings(source_unit.get("table_fallback_text_refs"))
        if reasons:
            rejected_refs = sorted(set(selected) - set(fallback_text_refs))
            projection = _base_projection(
                projection_id=projection_id,
                table_ref=candidate_ref,
                source_format="pdf",
                table_origin="geometry_candidate",
                source_unit=source_unit,
                row_refs=[],
                column_refs=[],
                cells=[],
                rows=[],
                private_values=[],
                source_value_index=[],
                headers=_empty_header_model("candidate_rejected"),
                coverage=_coverage(
                    projection_id=projection_id,
                    selected=selected,
                    table_owned=[],
                    fallback=fallback_text_refs,
                    rejected=rejected_refs,
                ),
                quality=_quality(
                    rows=[],
                    cells=[],
                    coverage_complete=True,
                    geometry_confidence=float(
                        source_unit.get("geometry_confidence") or 0.0
                    ),
                    blocked=True,
                ),
                page_refs=_strings(source_unit.get("page_refs")),
                sheet_refs=[],
                section_refs=[],
                table_bbox_ref=source_unit.get("table_bbox_ref"),
                table_candidate_status="rejected_to_line_cluster",
                reconstruction_strategy=_pdf_strategy(source_unit),
                reconstruction_reason_codes=reasons,
            )
            projection["projection_status"] = "blocked"
            projection["reconstruction_quality"] = "blocked"
            return _finish_projection(_apply_serialized_budget(projection, self.config))

        max_columns = max(
            (int(item.get("column_ordinal") or 0) for item in candidate_cells),
            default=0,
        )
        column_refs = [
            "tablecol_" + stable_digest([candidate_ref, ordinal], length=24)
            for ordinal in range(1, max_columns + 1)
        ]
        cells: list[dict[str, Any]] = []
        private_values: list[dict[str, Any]] = []
        source_value_index: list[dict[str, Any]] = []
        for item in candidate_cells:
            cell_ref = str(item.get("cell_ref") or "")
            word_refs = _strings(item.get("word_refs"))
            cell_words = [words[ref] for ref in word_refs]
            source_value_refs = [
                str(word.get("source_value_ref") or "") for word in cell_words
            ]
            value = " ".join(str(word.get("text") or "") for word in cell_words)
            word_lines = {
                round(
                    float(
                        (
                            _object(bboxes.get(str(word.get("bbox_ref") or ""))).get(
                                "bbox"
                            )
                            or [0.0, 0.0, 0.0, 0.0]
                        )[1]
                    ),
                    2,
                )
                for word in cell_words
            }
            multi_line = len(word_lines) > 1
            checksum = _checksum_ref("valuechk", value)
            value_path_ref = "tablevaluepath_" + stable_digest(
                [projection_id, cell_ref, *source_value_refs], length=24
            )
            cells.append(
                {
                    "cell_ref": cell_ref,
                    "row_ref": item.get("row_ref"),
                    "column_ref": column_refs[int(item.get("column_ordinal") or 1) - 1],
                    "row_ordinal": int(item.get("row_ordinal") or 0),
                    "column_ordinal": int(item.get("column_ordinal") or 0),
                    "source_value_refs": source_value_refs,
                    "cell_value_ref": "cellval_"
                    + stable_digest([cell_ref, checksum], length=24),
                    "normalized_private_value_path": value_path_ref,
                    "value_checksum_ref": checksum,
                    "value_kind_hints": _value_kind_hints(value),
                    "bbox_ref": item.get("bbox_ref"),
                    "row_span": int(item.get("row_span") or 1),
                    "column_span": int(item.get("column_span") or 1),
                    "merged_cell_group_ref": item.get("merged_cell_group_ref"),
                    "split_cell_candidate": bool(item.get("split_cell_candidate")),
                    "multi_line_cell": multi_line,
                    "wrapped_text_cell": bool(item.get("wrapped_text_cell"))
                    or multi_line,
                    "ambiguous_cell_boundary": False,
                    "empty_cell": not value.strip(),
                    "confidence": "high",
                    "reason_codes": ["pdf_geometry_mechanically_validated"],
                }
            )
            private_values.append(
                {
                    "value_path_ref": value_path_ref,
                    "normalized_value": value,
                    "value_checksum_ref": checksum,
                    "source_value_refs": source_value_refs,
                }
            )
            for word in cell_words:
                word_value = str(word.get("text") or "")
                word_value_checksum_ref = _checksum_ref("valuechk", word_value)
                word_value_path_ref = "tablewordvaluepath_" + stable_digest(
                    [
                        projection_id,
                        cell_ref,
                        word.get("word_ref"),
                        word.get("source_value_ref"),
                    ],
                    length=24,
                )
                private_values.append(
                    {
                        "value_path_ref": word_value_path_ref,
                        "normalized_value": word_value,
                        "value_checksum_ref": word_value_checksum_ref,
                        "source_value_refs": [word.get("source_value_ref")],
                        "source_object_ref": word.get("word_ref"),
                    }
                )
                source_value_index.append(
                    {
                        "source_value_ref": word.get("source_value_ref"),
                        "source_object_ref": word.get("word_ref"),
                        "cell_ref": cell_ref,
                        "value_path": {
                            "kind": "table_projection_private_value",
                            "value_path_ref": word_value_path_ref,
                        },
                        "value_checksum_ref": word_value_checksum_ref,
                    }
                )
        roles = _classify_rows(
            row_provenance=candidate_rows,
            cells=cells,
            private_values=private_values,
        )
        normalized_rows = [
            {
                "row_ref": item.get("row_ref"),
                "row_ordinal": int(item.get("row_ordinal") or 0),
                "cell_refs": _strings(item.get("cell_refs")),
                "row_role": roles.get(
                    str(item.get("row_ref") or ""), "unknown_row_role"
                ),
                "row_checksum_ref": _checksum_ref(
                    "rowchk", _strings(item.get("cell_refs"))
                ),
                "reason_codes": ["pdf_geometry_mechanically_validated"],
            }
            for item in candidate_rows
        ]
        contributing_words = _strings(source_unit.get("table_contributing_word_refs"))
        quality = _quality(
            rows=normalized_rows,
            cells=cells,
            coverage_complete=True,
            geometry_confidence=float(source_unit.get("geometry_confidence") or 0.0),
            blocked=False,
        )
        projection = _base_projection(
            projection_id=projection_id,
            table_ref=candidate_ref,
            source_format="pdf",
            table_origin="reconstructed_candidate",
            source_unit=source_unit,
            row_refs=[str(item.get("row_ref") or "") for item in normalized_rows],
            column_refs=column_refs,
            cells=cells,
            rows=normalized_rows,
            private_values=private_values,
            source_value_index=source_value_index,
            headers=_header_model(
                rows=normalized_rows,
                cells=cells,
                private_values=private_values,
                column_refs=column_refs,
                pdf_candidate=True,
            ),
            coverage=_coverage(
                projection_id=projection_id,
                selected=selected,
                table_owned=contributing_words,
                fallback=fallback_text_refs,
            ),
            quality=quality,
            page_refs=_strings(source_unit.get("page_refs")),
            sheet_refs=[],
            section_refs=[],
            table_bbox_ref=source_unit.get("table_bbox_ref"),
            table_candidate_status="validated_geometry",
            reconstruction_strategy=_pdf_strategy(source_unit),
            reconstruction_reason_codes=["pdf_geometry_mechanically_validated"],
        )
        projection["geometry"] = {
            "table_strategy_ref": source_unit.get("table_strategy_ref"),
            "geometry_confidence": source_unit.get("geometry_confidence"),
            "contributing_word_refs": contributing_words,
            "contributing_line_refs": _strings(source_unit.get("layout_line_refs")),
            "fallback_text_refs": fallback_text_refs,
            "fallback_source_value_refs": _strings(
                source_unit.get("table_fallback_source_value_refs")
            ),
            "duplicate_ownership_refs": [],
            "unaccounted_ownership_refs": [],
        }
        return _finish_projection(_apply_serialized_budget(projection, self.config))


class TableProjectionValidator:
    def validate(self, projection: dict[str, Any]) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        projection_id = str(projection.get("table_projection_id") or "")
        if projection.get("schema_version") != TABLE_PROJECTION_SCHEMA_VERSION:
            errors.append(_error("table_projection_schema_mismatch", projection_id))
        if projection.get("source_format") not in SOURCE_FORMATS:
            errors.append(_error("table_projection_source_format_invalid", projection_id))
        if projection.get("visibility") != "private_case":
            errors.append(_error("table_projection_visibility_invalid", projection_id))
        if projection.get("semantic_table_truth_claimed") is not False:
            errors.append(_error("table_projection_semantic_truth_forbidden", projection_id))
        if projection.get("knowledge_rag_used") is not False:
            errors.append(_error("table_projection_knowledge_guard_failed", projection_id))
        if projection.get("vectorization_performed") is not False:
            errors.append(_error("table_projection_vector_guard_failed", projection_id))
        rows = _dicts(projection.get("rows"))
        cells = _dicts(projection.get("cells"))
        row_refs = _strings(projection.get("row_refs"))
        cell_refs = _strings(projection.get("cell_refs"))
        column_refs = _strings(projection.get("column_refs"))
        if row_refs != [str(item.get("row_ref") or "") for item in rows]:
            errors.append(_error("table_projection_row_refs_mismatch", projection_id))
        if cell_refs != [str(item.get("cell_ref") or "") for item in cells]:
            errors.append(_error("table_projection_cell_refs_mismatch", projection_id))
        for field, refs in (
            ("row_refs", row_refs),
            ("column_refs", column_refs),
            ("cell_refs", cell_refs),
            ("source_value_refs", _strings(projection.get("source_value_refs"))),
        ):
            if len(refs) != len(set(refs)):
                errors.append(_error("table_projection_duplicate_ref", field))
        row_set = set(row_refs)
        column_set = set(column_refs)
        cell_set = set(cell_refs)
        value_set = set(_strings(projection.get("source_value_refs")))
        private_paths = {
            str(item.get("value_path_ref") or "")
            for item in _dicts(projection.get("private_values"))
        }
        if len(private_paths) != len(_dicts(projection.get("private_values"))):
            errors.append(_error("table_projection_private_value_path_duplicate", projection_id))
        for row in rows:
            if row.get("row_role") not in ROW_ROLES:
                errors.append(_error("table_projection_row_role_invalid", row.get("row_ref")))
            if not set(_strings(row.get("cell_refs"))) <= cell_set:
                errors.append(_error("table_projection_row_cell_ref_invalid", row.get("row_ref")))
        for cell in cells:
            if cell.get("row_ref") not in row_set or cell.get("column_ref") not in column_set:
                errors.append(_error("table_projection_cell_scope_invalid", cell.get("cell_ref")))
            if not set(_strings(cell.get("source_value_refs"))) <= value_set:
                errors.append(_error("table_projection_cell_value_ref_invalid", cell.get("cell_ref")))
            if cell.get("normalized_private_value_path") not in private_paths:
                errors.append(_error("table_projection_private_value_path_invalid", cell.get("cell_ref")))
            if int(cell.get("row_span") or 0) <= 0 or int(cell.get("column_span") or 0) <= 0:
                errors.append(_error("table_projection_cell_span_invalid", cell.get("cell_ref")))
        source_index_refs = [
            str(item.get("source_value_ref") or "")
            for item in _dicts(projection.get("source_value_index"))
        ]
        if sorted(source_index_refs) != sorted(value_set):
            errors.append(_error("table_projection_source_value_index_mismatch", projection_id))
        else:
            errors.extend(validate_source_value_refs(projection, source_index_refs))
        coverage = _object(projection.get("coverage"))
        if coverage.get("schema_version") != TABLE_COVERAGE_SCHEMA_VERSION:
            errors.append(_error("table_projection_coverage_schema_mismatch", projection_id))
        selected = _strings(coverage.get("selected_source_refs"))
        owners = [
            *_strings(coverage.get("table_owned_refs")),
            *_strings(coverage.get("fallback_text_refs")),
            *_strings(coverage.get("non_table_refs")),
            *_strings(coverage.get("rejected_refs")),
        ]
        duplicate_refs = sorted(
            ref for ref, count in Counter(owners).items() if count > 1
        )
        unaccounted = sorted(set(selected) - set(owners))
        unexpected = sorted(set(owners) - set(selected))
        if duplicate_refs != _strings(coverage.get("duplicate_accounted_refs")):
            errors.append(_error("table_projection_duplicate_coverage_mismatch", projection_id))
        if unaccounted != _strings(coverage.get("unaccounted_refs")):
            errors.append(_error("table_projection_unaccounted_coverage_mismatch", projection_id))
        if unexpected:
            errors.append(_error("table_projection_coverage_ref_out_of_scope", projection_id))
        expected_complete = not duplicate_refs and not unaccounted and not unexpected
        if (coverage.get("coverage_status") == "complete") != expected_complete:
            errors.append(_error("table_projection_coverage_status_mismatch", projection_id))
        if projection.get("row_count") != len(rows):
            errors.append(_error("table_projection_row_count_mismatch", projection_id))
        if projection.get("column_count") != len(column_refs):
            errors.append(_error("table_projection_column_count_mismatch", projection_id))
        if projection.get("cell_count") != len(cells):
            errors.append(_error("table_projection_cell_count_mismatch", projection_id))
        if projection.get("source_format") == "pdf":
            if projection.get("table_candidate_status") not in PDF_STATUSES:
                errors.append(_error("table_projection_pdf_status_invalid", projection_id))
            if projection.get("semantic_table_truth_claimed") is not False:
                errors.append(_error("table_projection_pdf_semantic_truth_forbidden", projection_id))
            canonical_profile_id = projection.get("canonical_profile_id")
            if canonical_profile_id == BROKER_PDF_NEUTRAL_PROFILE_ID:
                canonical_validation = validate_canonical_neutral_projection(projection)
                errors.extend(
                    _error(code, projection_id)
                    for code in canonical_validation["reason_codes"]
                )
                if not validate_canonical_integrity(projection):
                    errors.append(
                        _error("canonical_neutral_table_integrity_mismatch", projection_id)
                    )
            elif canonical_profile_id == SEMANTIC_LOGICAL_TABLE_PROFILE_ID:
                semantic_validation = validate_semantic_visual_table_projection(
                    projection
                )
                errors.extend(
                    _error(code, projection_id)
                    for code in semantic_validation["reason_codes"]
                )
            elif canonical_profile_id:
                errors.append(
                    _error("table_projection_canonical_profile_unsupported", projection_id)
                )
        expected_checksum = _projection_checksum(projection)
        if projection.get("table_projection_checksum_ref") != expected_checksum:
            errors.append(_error("table_projection_checksum_mismatch", projection_id))
        return {
            "schema_version": "broker_reports_normalized_table_projection_validation_v0",
            "table_projection_id": projection_id,
            "validator_status": "passed" if not errors else "failed",
            "passed": not errors,
            "errors_count": len(errors),
            "errors": errors,
        }


_GATE2_TABLE_PACKAGE_COMPAT_EXPORTS = {
    "Gate2TablePackageBuilder",
    "Gate2TablePackageConfig",
    "Gate2TablePackageFactory",
    "TABLE_GATE2_PACKAGE_SCHEMA_VERSION",
    "validate_gate2_table_package",
}


def __getattr__(name: str):
    """Compatibility facade; Gate 2 implementation lives in its owning module."""

    if name not in _GATE2_TABLE_PACKAGE_COMPAT_EXPORTS:
        raise AttributeError(name)
    from . import gate2_table_packages

    if name == "TABLE_GATE2_PACKAGE_SCHEMA_VERSION":
        return gate2_table_packages.PACKAGE_SCHEMA_VERSION
    return getattr(gate2_table_packages, name)



def _base_projection(
    *,
    projection_id: str,
    table_ref: str,
    source_format: str,
    table_origin: str,
    source_unit: dict[str, Any],
    row_refs: list[str],
    column_refs: list[str],
    cells: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    private_values: list[dict[str, Any]],
    source_value_index: list[dict[str, Any]],
    headers: dict[str, Any],
    coverage: dict[str, Any],
    quality: dict[str, Any],
    page_refs: list[str],
    sheet_refs: list[str],
    section_refs: list[str],
    table_bbox_ref: Any,
    table_candidate_status: str | None,
    reconstruction_strategy: str,
    reconstruction_reason_codes: list[str],
) -> dict[str, Any]:
    cell_refs = [str(item.get("cell_ref") or "") for item in cells]
    cell_value_refs = [str(item.get("cell_value_ref") or "") for item in cells]
    source_value_refs = sorted(
        {
            ref
            for item in cells
            for ref in _strings(item.get("source_value_refs"))
        }
    )
    return {
        "schema_version": TABLE_PROJECTION_SCHEMA_VERSION,
        "table_projection_id": projection_id,
        "table_ref": table_ref,
        "source_format": source_format,
        "table_origin": table_origin,
        "source_document_ref": source_unit.get("document_id"),
        "source_unit_ref": source_unit.get("unit_ref"),
        "parent_payload_ref": source_unit.get("parent_payload_ref"),
        "normalization_run_id": source_unit.get("normalization_run_id"),
        "parser_ref": source_unit.get("parser_ref"),
        "parser_engine": source_unit.get("parser"),
        "parser_engine_version": source_unit.get("parser_version"),
        "parser_config_ref": source_unit.get("layout_parser_config_ref"),
        "source_checksum_ref": source_unit.get("source_checksum_ref"),
        "payload_checksum_ref": source_unit.get("payload_checksum_ref"),
        "source_unit_checksum_ref": source_unit.get("source_unit_checksum_ref"),
        "table_projection_checksum_ref": None,
        "visibility": "private_case",
        "storage_backend": "project_artifact_payload",
        "projection_status": "ready",
        "row_refs": row_refs,
        "column_refs": column_refs,
        "cell_refs": cell_refs,
        "cell_value_refs": cell_value_refs,
        "source_value_refs": source_value_refs,
        "row_count": len(rows),
        "column_count": len(column_refs),
        "cell_count": len(cells),
        "row_order_policy": "source_order_preserved",
        "column_order_policy": "source_order_preserved",
        "table_bbox_ref": table_bbox_ref,
        "page_refs": page_refs,
        "sheet_refs": sheet_refs,
        "section_refs": section_refs,
        "rows": rows,
        "cells": cells,
        "private_values": private_values,
        "source_value_index": source_value_index,
        "header_model": headers,
        "coverage": coverage,
        "quality": quality,
        "table_candidate_status": table_candidate_status,
        "reconstruction_strategy": reconstruction_strategy,
        "reconstruction_reason_codes": sorted(set(reconstruction_reason_codes)),
        "reconstruction_quality": quality["reconstruction_quality"],
        "semantic_table_truth_claimed": False,
        "source_facts_extracted": False,
        "tax_meaning_inferred": False,
        "knowledge_rag_used": False,
        "vectorization_performed": False,
        "ocr_vlm_used": False,
        "page_rendering_used_for_extraction": False,
    }


def _finish_projection(projection: dict[str, Any]) -> dict[str, Any]:
    projection["table_projection_checksum_ref"] = _projection_checksum(projection)
    return projection


def _apply_serialized_budget(
    projection: dict[str, Any], config: NormalizedTableProjectionConfig
) -> dict[str, Any]:
    if len(_canonical_bytes(projection)) <= config.max_payload_bytes:
        return projection
    reasons = set(projection.get("reconstruction_reason_codes") or [])
    reasons.add("table_projection_payload_budget_exceeded")
    projection["reconstruction_reason_codes"] = sorted(reasons)
    projection["projection_status"] = "blocked"
    projection["reconstruction_quality"] = "blocked"
    quality = _object(projection.get("quality"))
    quality["reconstruction_quality"] = "blocked"
    projection["quality"] = quality
    return projection


def _projection_checksum(projection: dict[str, Any]) -> str:
    material = copy.deepcopy(projection)
    material.pop("table_projection_checksum_ref", None)
    material.pop("validator_status", None)
    material.pop("validator_reason_codes", None)
    return _checksum_ref("tableprojchk", material)


def _coverage(
    *,
    projection_id: str,
    selected: list[str],
    table_owned: list[str],
    fallback: list[str] | None = None,
    non_table: list[str] | None = None,
    rejected: list[str] | None = None,
) -> dict[str, Any]:
    fallback = list(fallback or [])
    non_table = list(non_table or [])
    rejected = list(rejected or [])
    owners = [*table_owned, *fallback, *non_table, *rejected]
    duplicates = sorted(ref for ref, count in Counter(owners).items() if count > 1)
    unaccounted = sorted(set(selected) - set(owners))
    unexpected = sorted(set(owners) - set(selected))
    complete = not duplicates and not unaccounted and not unexpected
    return {
        "schema_version": TABLE_COVERAGE_SCHEMA_VERSION,
        "coverage_ref": "tablecoverage_"
        + stable_digest([projection_id, selected, owners], length=24),
        "selected_source_refs": list(selected),
        "accounted_source_refs": list(owners),
        "table_owned_refs": list(table_owned),
        "fallback_text_refs": fallback,
        "non_table_refs": non_table,
        "rejected_refs": rejected,
        "duplicate_accounted_refs": duplicates,
        "unaccounted_refs": unaccounted,
        "selected_total": len(selected),
        "accounted_total": len(owners),
        "coverage_status": "complete" if complete else "partial",
        "all_selected_refs_accounted": complete,
    }


def _quality(
    *,
    rows: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    coverage_complete: bool,
    geometry_confidence: float | None,
    blocked: bool,
) -> dict[str, Any]:
    counts = Counter(int(item.get("row_ordinal") or 0) for item in cells)
    expected = max(counts.values(), default=0)
    aligned = sum(1 for value in counts.values() if value == expected)
    row_alignment = aligned / len(counts) if counts else 0.0
    boundary_confidence = (
        min(float(geometry_confidence or 0.0), row_alignment)
        if geometry_confidence is not None
        else row_alignment
    )
    if blocked:
        reconstruction_quality = "blocked"
    elif coverage_complete and row_alignment >= 0.95 and boundary_confidence >= 0.90:
        reconstruction_quality = "high"
    elif coverage_complete and row_alignment >= 0.75:
        reconstruction_quality = "medium"
    else:
        reconstruction_quality = "low"
    return {
        "schema_version": TABLE_QUALITY_SCHEMA_VERSION,
        "row_alignment_score": round(row_alignment, 6),
        "column_alignment_score": round(row_alignment, 6),
        "header_confidence": (
            "high" if rows and reconstruction_quality == "high" else "medium"
        ),
        "cell_boundary_confidence": round(boundary_confidence, 6),
        "coverage_completeness": 1.0 if coverage_complete else 0.0,
        "duplicate_overlap_count": 0,
        "unaccounted_ref_count": 0 if coverage_complete else 1,
        "fallback_required": geometry_confidence is not None,
        "reconstruction_quality": reconstruction_quality,
    }


def _classify_rows(
    *,
    row_provenance: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    private_values: list[dict[str, Any]],
) -> dict[str, str]:
    values = {
        str(item.get("value_path_ref") or ""): str(item.get("normalized_value") or "")
        for item in private_values
    }
    cells_by_row: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        cells_by_row.setdefault(str(cell.get("row_ref") or ""), []).append(cell)
    row_values: dict[str, list[str]] = {}
    for row in row_provenance:
        row_ref = str(row.get("row_ref") or "")
        row_values[row_ref] = [
            values.get(str(cell.get("normalized_private_value_path") or ""), "")
            for cell in sorted(
                cells_by_row.get(row_ref, []),
                key=lambda item: int(item.get("column_ordinal") or 0),
            )
        ]
    first_nonblank = next(
        (ref for ref, row in row_values.items() if any(value.strip() for value in row)),
        None,
    )
    header_signature = _row_signature(row_values.get(first_nonblank, []))
    roles: dict[str, str] = {}
    for row in row_provenance:
        row_ref = str(row.get("row_ref") or "")
        current = row_values.get(row_ref, [])
        nonblank = [value.strip() for value in current if value.strip()]
        if not nonblank:
            role = "blank_row"
        elif row_ref == first_nonblank:
            role = "header_row"
        elif header_signature and _row_signature(current) == header_signature:
            role = "repeated_header_row"
        else:
            first = _safe_token(nonblank[0])
            if first in {"subtotal", "sub_total", "промежуточный_итог", "подытог"}:
                role = "subtotal_row"
            elif first in {"total", "grand_total", "summary", "итого", "всего"}:
                role = "summary_row"
            else:
                role = "data_row"
        roles[row_ref] = role
    return roles


def _header_model(
    *,
    rows: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    private_values: list[dict[str, Any]],
    column_refs: list[str],
    pdf_candidate: bool,
) -> dict[str, Any]:
    header_rows = [
        row
        for row in rows
        if row.get("row_role") in {"header_row", "repeated_header_row"}
    ]
    primary = next(
        (row for row in header_rows if row.get("row_role") == "header_row"), None
    )
    cells_by_ref = {
        str(item.get("cell_ref") or ""): item for item in cells
    }
    values = {
        str(item.get("value_path_ref") or ""): str(item.get("normalized_value") or "")
        for item in private_values
    }
    labels = []
    if primary:
        for cell_ref in _strings(primary.get("cell_refs")):
            cell = cells_by_ref.get(cell_ref, {})
            label = _safe_header_descriptor(
                values.get(str(cell.get("normalized_private_value_path") or ""), "")
            )
            labels.append(
                {
                    "header_ref": "tableheader_"
                    + stable_digest([primary.get("row_ref"), cell_ref], length=20),
                    "column_ref": cell.get("column_ref"),
                    "cell_ref": cell_ref,
                    "source_value_refs": _strings(cell.get("source_value_refs")),
                    "normalized_label": label,
                    "header_confidence": "high" if not pdf_candidate else "medium",
                    "mapping_status": "mapped",
                }
            )
    mapped_columns = {str(item.get("column_ref") or "") for item in labels}
    status = (
        "mapped"
        if set(column_refs) == mapped_columns and column_refs
        else "missing_or_ambiguous"
    )
    return {
        "header_row_refs": [
            str(item.get("row_ref") or "")
            for item in header_rows
            if item.get("row_role") == "header_row"
        ],
        "repeated_header_row_refs": [
            str(item.get("row_ref") or "")
            for item in header_rows
            if item.get("row_role") == "repeated_header_row"
        ],
        "multi_row_header": sum(
            1 for item in header_rows if item.get("row_role") == "header_row"
        )
        > 1,
        "column_labels": labels,
        "header_to_column_mapping_status": status,
        "pdf_header_candidate": pdf_candidate,
        "semantic_header_truth_claimed": False,
    }


def _empty_header_model(status: str) -> dict[str, Any]:
    return {
        "header_row_refs": [],
        "repeated_header_row_refs": [],
        "multi_row_header": False,
        "column_labels": [],
        "header_to_column_mapping_status": status,
        "pdf_header_candidate": True,
        "semantic_header_truth_claimed": False,
    }


def _pdf_geometry_reasons(
    *,
    source_unit: dict[str, Any],
    candidate: dict[str, Any] | None,
    words: dict[str, dict[str, Any]],
    min_confidence: float,
) -> list[str]:
    reasons = []
    if candidate is None:
        return ["pdf_table_candidate_inventory_missing"]
    confidence = float(source_unit.get("geometry_confidence") or 0.0)
    if confidence < min_confidence:
        reasons.append("pdf_table_geometry_confidence_below_threshold")
    rows = _dicts(candidate.get("row_inventory"))
    cells = _dicts(candidate.get("cell_inventory"))
    if len(rows) < 2 or len(cells) < 4:
        reasons.append("pdf_table_geometry_insufficient_structure")
    column_counts = Counter(int(item.get("row_ordinal") or 0) for item in cells)
    if not column_counts or min(column_counts.values(), default=0) < 2:
        reasons.append("pdf_table_geometry_column_structure_insufficient")
    owned = [
        ref for cell in cells for ref in _strings(cell.get("word_refs"))
    ]
    contributing = _strings(source_unit.get("table_contributing_word_refs"))
    if len(owned) != len(set(owned)):
        reasons.append("pdf_table_geometry_duplicate_word_owner")
    if set(owned) != set(contributing):
        reasons.append("pdf_table_geometry_word_coverage_mismatch")
    if not set(owned) <= set(words):
        reasons.append("pdf_table_geometry_word_ref_out_of_scope")
    if any(not cell.get("bbox_ref") for cell in cells):
        reasons.append("pdf_table_geometry_cell_bbox_missing")
    if source_unit.get("table_strategy_ref") not in {
        "ruled_lines_v0",
        "aligned_text_v0",
        "mixed_geometry_v0",
        "repeated_x_columns_v0",
    }:
        reasons.append("pdf_table_reconstruction_strategy_unsupported")
    return sorted(set(reasons))


def _pdf_strategy(source_unit: dict[str, Any]) -> str:
    return {
        "ruled_lines_v0": "ruled_lines",
        "aligned_text_v0": "aligned_words",
        "mixed_geometry_v0": "mixed_geometry",
        "repeated_x_columns_v0": "repeated_x_columns",
    }.get(str(source_unit.get("table_strategy_ref") or ""), "fallback_line_cluster")


def _rows_from_unit(unit: dict[str, Any]) -> list[list[str]]:
    projection = _object(unit.get("normalized_source_projection"))
    value = projection.get("cells")
    if not isinstance(value, list):
        value = unit.get("rows")
    return [
        [str(cell or "") for cell in row]
        for row in value or []
        if isinstance(row, list)
    ]


def _sheet_refs(unit: dict[str, Any]) -> list[str]:
    location = _object(unit.get("source_location"))
    sheet = location.get("sheet") or location.get("sheet_ref")
    return [str(sheet)] if sheet else []


def _budget_reasons(
    *,
    rows: int,
    cells: int,
    payload_bytes: int,
    config: NormalizedTableProjectionConfig,
) -> list[str]:
    reasons = []
    if rows > config.max_rows:
        reasons.append("table_projection_row_budget_exceeded")
    if cells > config.max_cells:
        reasons.append("table_projection_cell_budget_exceeded")
    if payload_bytes > config.max_payload_bytes:
        reasons.append("table_projection_payload_budget_exceeded")
    return reasons


def _value_kind_hints(value: str) -> list[str]:
    stripped = value.strip()
    if not stripped:
        return ["blank"]
    hints = []
    if re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", stripped.replace(" ", "")):
        hints.append("decimal_like")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped):
        hints.append("iso_date_like")
    if re.fullmatch(r"[A-Z]{3}", stripped):
        hints.append("currency_code_like")
    if "\n" in value:
        hints.append("multi_line_text")
    return hints or ["text"]


def _safe_header_descriptor(value: str) -> str:
    token = _safe_token(value)
    mappings = {
        "date": "date",
        "дата": "date",
        "amount": "amount",
        "сумма": "amount",
        "currency": "currency",
        "валюта": "currency",
        "operation": "operation",
        "операция": "operation",
        "описание_операции": "operation",
        "operation_description": "operation",
        "торговая_площадка": "market",
        "trading_venue": "market",
        "quantity": "quantity",
        "количество": "quantity",
        "identifier": "instrument",
        "инструмент": "instrument",
        "сумма_зачисления": "amount",
        "сумма_списания": "amount",
        "credit_amount": "amount",
        "debit_amount": "amount",
    }
    return mappings.get(token, "unknown")


def _row_signature(values: list[str]) -> str:
    if not any(value.strip() for value in values):
        return ""
    return hashlib.sha256(
        json.dumps(
            [_safe_token(value) for value in values],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _safe_token(value: Any) -> str:
    return re.sub(
        r"_+",
        "_",
        re.sub(r"[^\w]+", "_", str(value or "").strip().lower(), flags=re.UNICODE),
    ).strip("_")


def _decision(
    unit: dict[str, Any],
    *,
    status: str,
    reason_codes: list[str],
    projection_ref: Any = None,
) -> dict[str, Any]:
    return {
        "schema_version": "broker_reports_typed_region_decision_v1",
        "source_unit_ref": unit.get("unit_ref"),
        "document_ref": unit.get("document_id"),
        "table_projection_ref": projection_ref,
        "canonical_table_ref": None,
        "logical_table_ref": None,
        "region_type": "unknown_or_ambiguous",
        "status": status,
        "reason_codes": sorted(set(reason_codes)),
        "detector_authority": "proposal_only",
        "promotion_authority": None,
    }


def _safe_summary(
    projections: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> dict[str, Any]:
    quality = Counter(
        str(item.get("reconstruction_quality") or "blocked")
        for item in projections
    )
    return {
        "schema_version": "broker_reports_table_projection_safe_summary_v0",
        "table_projections_total": len(projections),
        "native_table_projections_total": sum(
            1 for item in projections if item.get("source_format") != "pdf"
        ),
        "pdf_table_projections_total": sum(
            1 for item in projections if item.get("source_format") == "pdf"
        ),
        "quality_counts": dict(sorted(quality.items())),
        "rows_total": sum(int(item.get("row_count") or 0) for item in projections),
        "cells_total": sum(int(item.get("cell_count") or 0) for item in projections),
        "source_value_refs_total": sum(
            len(_strings(item.get("source_value_refs"))) for item in projections
        ),
        "fallback_refs_total": sum(
            len(_strings(_object(item.get("coverage")).get("fallback_text_refs")))
            for item in projections
        ),
        "unaccounted_refs_total": sum(
            len(_strings(_object(item.get("coverage")).get("unaccounted_refs")))
            for item in projections
        ),
        "duplicate_refs_total": sum(
            len(
                _strings(
                    _object(item.get("coverage")).get("duplicate_accounted_refs")
                )
            )
            for item in projections
        ),
        "blocked_decisions_total": sum(
            1 for item in decisions if item.get("status") in {"blocked", "rejected_to_line_cluster"}
        ),
        "raw_values_in_summary": False,
        "knowledge_rag_used": False,
        "vectorization_performed": False,
    }


def _checksum_ref(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical_bytes(value)).hexdigest()[:24]}"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)] if isinstance(value, list) else []


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}
