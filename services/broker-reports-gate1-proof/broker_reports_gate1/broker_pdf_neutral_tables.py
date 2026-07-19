from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest


FACTORY_REQUIRED = (
    "BrokerPdfNeutralTableFactory.create is the only production entrypoint for "
    "the supported broker PDF neutral-table profile"
)
FORBIDDEN = (
    "Callers must not select the profile by filename, path, document id, region "
    "id, artifact id, source hash, customer value, or page-specific exception"
)

PROFILE_ID = "supported_broker_pdf_neutral_table_profile_v1"
PROFILE_VERSION = "broker_pdf_neutral_table_profile_v1"
CANONICAL_SCHEMA_VERSION = "broker_reports_canonical_neutral_table_v1"
REGION_DECISION_SCHEMA_VERSION = "broker_reports_typed_region_decision_v1"
VALIDATOR_VERSION = "broker_pdf_neutral_table_validator_v1"
RECONSTRUCTION_VERSION = "broker_pdf_ruled_grid_reconstruction_v1"
CANONICAL_READY_SCOPE = "ready_validated_projection_only"

REGION_TYPES = {
    "canonical_table_candidate",
    "structured_form_panel",
    "section_heading",
    "material_non_table_region",
    "non_material_region",
    "unknown_or_ambiguous",
}


@dataclass(frozen=True)
class BrokerPdfNeutralTableConfig:
    minimum_geometry_confidence: float = 0.95
    boundary_tolerance_ratio: float = 0.0025
    maximum_columns: int = 24
    maximum_rows_per_region: int = 128
    continuation_top_ratio: float = 0.12
    continuation_previous_bottom_ratio: float = 0.84


@dataclass(frozen=True)
class BrokerPdfNeutralTableBuildResult:
    projections_by_unit_ref: dict[str, dict[str, Any]]
    decisions_by_unit_ref: dict[str, dict[str, Any]]
    profile_evidence: dict[str, Any]


class BrokerPdfNeutralTableFactory:
    def __init__(self, config: BrokerPdfNeutralTableConfig | None = None) -> None:
        self.config = config or BrokerPdfNeutralTableConfig()

    def create(self) -> "BrokerPdfNeutralTableRuntime":
        if not 0.0 < self.config.minimum_geometry_confidence <= 1.0:
            raise ValueError("broker_pdf_neutral_profile_confidence_invalid")
        if not 0.0 < self.config.boundary_tolerance_ratio <= 0.02:
            raise ValueError("broker_pdf_neutral_profile_tolerance_invalid")
        if self.config.maximum_columns < 2 or self.config.maximum_rows_per_region < 2:
            raise ValueError("broker_pdf_neutral_profile_budget_invalid")
        return BrokerPdfNeutralTableRuntime(self.config)


class BrokerPdfNeutralTableRuntime:
    def __init__(self, config: BrokerPdfNeutralTableConfig) -> None:
        self.config = config

    def build_for_document(
        self,
        *,
        payloads: list[dict[str, Any]],
        source_units: list[dict[str, Any]],
    ) -> BrokerPdfNeutralTableBuildResult | None:
        candidates = [
            item
            for item in source_units
            if isinstance(item, dict)
            and item.get("pdf_unit_type") == "pdf_table_candidate_unit"
        ]
        if not candidates:
            return None
        payload_by_ref = {
            str(item.get("source_payload_ref") or ""): item
            for item in payloads
            if isinstance(item, dict) and item.get("source_payload_ref")
        }
        fragments: list[dict[str, Any]] = []
        for unit in candidates:
            parent = payload_by_ref.get(str(unit.get("parent_payload_ref") or ""))
            analysis = self._analyse_region(unit=unit, parent_payload=parent)
            if analysis["reason_codes"]:
                return None
            fragments.append(analysis)
        fragments.sort(
            key=lambda item: (
                item["page_number"],
                item["table_bbox"][1],
                str(item["unit"].get("unit_ref") or ""),
            )
        )
        if not self._assign_logical_groups(fragments):
            return None

        projections_by_unit: dict[str, dict[str, Any]] = {}
        decisions_by_unit: dict[str, dict[str, Any]] = {}
        groups: dict[str, list[dict[str, Any]]] = {}
        for fragment in fragments:
            groups.setdefault(str(fragment["logical_group_key"]), []).append(fragment)
        for group_key, members in groups.items():
            members.sort(key=lambda item: item["fragment_order"])
            logical_table_id = "logicaltable_" + stable_digest(
                [
                    CANONICAL_SCHEMA_VERSION,
                    members[0]["unit"].get("document_id"),
                    group_key,
                    [item["grid_signature"] for item in members],
                    [item["unit"].get("source_unit_checksum_ref") for item in members],
                ],
                length=24,
            )
            root_projection_id = "tableproj_" + stable_digest(
                [
                    CANONICAL_SCHEMA_VERSION,
                    logical_table_id,
                    members[0]["unit"].get("unit_ref"),
                    members[0]["unit"].get("pdf_layout_unit_checksum_ref"),
                ],
                length=24,
            )
            logical_totals = [
                row["row_ref"]
                for item in members
                for row in item["canonical_rows"]
                if row["structural_role"] in {"subtotal_row", "total_row"}
            ]
            group_validation = {
                "regions_total": len(members),
                "page_order": [item["page_number"] for item in members],
                "continuation_required": len(members) > 1,
                "continuation_validated": True,
                "shared_column_count": members[0]["column_count"],
                "logical_rows_total": sum(
                    len(item["canonical_rows"]) for item in members
                ),
                "logical_total_row_refs": logical_totals,
                "every_region_consumed_once": True,
            }
            for index, fragment in enumerate(members, 1):
                projection_id = (
                    root_projection_id
                    if index == 1
                    else "tableproj_"
                    + stable_digest(
                        [
                            CANONICAL_SCHEMA_VERSION,
                            logical_table_id,
                            fragment["unit"].get("unit_ref"),
                            fragment["unit"].get("pdf_layout_unit_checksum_ref"),
                        ],
                        length=24,
                    )
                )
                projection = self._build_projection(
                    fragment=fragment,
                    group=members,
                    logical_table_id=logical_table_id,
                    projection_id=projection_id,
                    root_projection_id=root_projection_id,
                    group_validation=group_validation,
                )
                validation = validate_canonical_neutral_projection(projection)
                if validation["validator_status"] != "passed":
                    return None
                projection["canonical_validation"] = validation
                projection["canonical_integrity_hash"] = _canonical_integrity_hash(
                    projection
                )
                unit_ref = str(fragment["unit"].get("unit_ref") or "")
                projections_by_unit[unit_ref] = projection
                decisions_by_unit[unit_ref] = {
                    "schema_version": REGION_DECISION_SCHEMA_VERSION,
                    "source_unit_ref": unit_ref,
                    "document_ref": fragment["unit"].get("document_id"),
                    "table_projection_ref": projection_id,
                    "canonical_table_ref": projection["canonical_table_id"],
                    "logical_table_ref": logical_table_id,
                    "region_type": "canonical_table_candidate",
                    "status": "canonical_table_accepted",
                    "reason_codes": [
                        "broker_pdf_profile_v1_matched",
                        "deterministic_neutral_table_validation_passed",
                    ],
                    "detector_authority": "proposal_only",
                    "promotion_authority": VALIDATOR_VERSION,
                }
        return BrokerPdfNeutralTableBuildResult(
            projections_by_unit_ref=projections_by_unit,
            decisions_by_unit_ref=decisions_by_unit,
            profile_evidence={
                "profile_id": PROFILE_ID,
                "regions_total": len(fragments),
                "logical_tables_total": len(groups),
                "continued_logical_tables_total": sum(
                    1 for values in groups.values() if len(values) > 1
                ),
                "selection_uses_filename_path_id_hash_or_value_allowlist": False,
                "provider_calls": 0,
            },
        )

    def _analyse_region(
        self,
        *,
        unit: dict[str, Any],
        parent_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        projection = _object(_object(parent_payload).get("pdf_text_layer_projection"))
        candidate = next(
            (
                item
                for item in _dicts(projection.get("table_candidate_inventory"))
                if item.get("table_candidate_ref") == unit.get("table_candidate_ref")
            ),
            None,
        )
        if candidate is None:
            reasons.append("broker_pdf_profile_candidate_inventory_missing")
            candidate = {}
        if unit.get("table_strategy_ref") != "ruled_lines_v0":
            reasons.append("broker_pdf_profile_ruled_grid_required")
        if (
            float(unit.get("geometry_confidence") or 0.0)
            < self.config.minimum_geometry_confidence
        ):
            reasons.append("broker_pdf_profile_geometry_confidence_insufficient")
        if unit.get("ocr_vlm_used") is not False:
            reasons.append("broker_pdf_profile_provider_or_ocr_path_forbidden")
        rows = _dicts(candidate.get("row_inventory"))
        raw_cells = _dicts(candidate.get("cell_inventory"))
        if len(rows) < 2 or len(rows) > self.config.maximum_rows_per_region:
            reasons.append("broker_pdf_profile_row_shape_outside_profile")
        if len(raw_cells) < 4:
            reasons.append("broker_pdf_profile_cell_shape_outside_profile")
        bbox_by_ref = {
            str(item.get("bbox_ref") or ""): list(item.get("bbox") or [])
            for item in _dicts(projection.get("bbox_inventory"))
        }
        words_by_ref = {
            str(item.get("word_ref") or ""): item
            for item in _dicts(projection.get("word_inventory"))
        }
        lines_by_ref = {
            str(item.get("line_ref") or ""): item
            for item in _dicts(projection.get("line_inventory"))
        }
        table_bbox = bbox_by_ref.get(str(candidate.get("bbox_ref") or ""), [])
        if not _valid_bbox(table_bbox):
            reasons.append("broker_pdf_profile_table_bbox_invalid")
            table_bbox = [0.0, 0.0, 0.0, 0.0]
        row_cells: dict[int, list[dict[str, Any]]] = {}
        for cell in raw_cells:
            bbox = bbox_by_ref.get(str(cell.get("bbox_ref") or ""), [])
            if not _valid_bbox(bbox):
                reasons.append("broker_pdf_profile_cell_bbox_invalid")
                continue
            clone = copy.deepcopy(cell)
            clone["bbox"] = bbox
            clone["text"] = " ".join(
                str(words_by_ref.get(ref, {}).get("text") or "")
                for ref in _strings(cell.get("word_refs"))
            )
            row_cells.setdefault(int(cell.get("row_ordinal") or 0), []).append(clone)
        maximum = max((len(items) for items in row_cells.values()), default=0)
        if maximum < 2 or maximum > self.config.maximum_columns:
            reasons.append("broker_pdf_profile_column_shape_outside_profile")
        leaf_candidates = [
            sorted(items, key=lambda item: float(item["bbox"][0]))
            for items in row_cells.values()
            if len(items) == maximum
        ]
        leaf = leaf_candidates[0] if leaf_candidates else []
        boundaries = []
        if leaf:
            boundaries = [float(leaf[0]["bbox"][0])] + [
                float(item["bbox"][2]) for item in leaf
            ]
            if any(
                boundaries[index] >= boundaries[index + 1]
                for index in range(len(boundaries) - 1)
            ):
                reasons.append("broker_pdf_profile_column_boundaries_invalid")
        width = max(1.0, boundaries[-1] - boundaries[0]) if boundaries else 1.0
        tolerance = max(0.35, width * self.config.boundary_tolerance_ratio)
        canonical_cells: list[dict[str, Any]] = []
        for ordinal in sorted(row_cells):
            seen_ranges: list[tuple[int, int]] = []
            for cell in sorted(
                row_cells[ordinal], key=lambda item: float(item["bbox"][0])
            ):
                start = _nearest_boundary(boundaries, float(cell["bbox"][0]), tolerance)
                end = _nearest_boundary(boundaries, float(cell["bbox"][2]), tolerance)
                if start is None or end is None or end <= start:
                    reasons.append("broker_pdf_profile_cell_boundary_unresolved")
                    continue
                if any(
                    not (end <= left or start >= right) for left, right in seen_ranges
                ):
                    reasons.append("broker_pdf_profile_cell_overlap")
                seen_ranges.append((start, end))
                item = copy.deepcopy(cell)
                item["canonical_column_ordinal"] = start + 1
                item["canonical_column_span"] = end - start
                canonical_cells.append(item)
        cells_by_row: dict[int, list[dict[str, Any]]] = {}
        for cell in canonical_cells:
            cells_by_row.setdefault(int(cell.get("row_ordinal") or 0), []).append(cell)
        ordinal_row = _find_ordinal_header_row(cells_by_row, maximum)
        canonical_rows = []
        for row in sorted(rows, key=lambda item: int(item.get("row_ordinal") or 0)):
            row_ordinal = int(row.get("row_ordinal") or 0)
            cells = sorted(
                cells_by_row.get(row_ordinal, []),
                key=lambda item: int(item["canonical_column_ordinal"]),
            )
            canonical_rows.append(
                {
                    "row_ref": row.get("row_ref"),
                    "row_ordinal": row_ordinal,
                    "structural_role": _structural_row_role(
                        row_ordinal=row_ordinal,
                        ordinal_header_row=ordinal_row,
                        cells=cells,
                        column_count=maximum,
                    ),
                    "cell_refs": [str(item.get("cell_ref") or "") for item in cells],
                }
            )
        page_ref = next(iter(_strings(unit.get("page_refs"))), "")
        page_item = next(
            (
                item
                for item in _dicts(projection.get("page_inventory"))
                if item.get("page_ref") == page_ref
            ),
            {},
        )
        page_number = int(
            _object(unit.get("source_location")).get("page")
            or page_item.get("page_number")
            or 0
        )
        page_height = float(
            page_item.get("layout_page_height")
            or page_item.get("height")
            or max(table_bbox[3], 1.0)
        )
        normalized_boundaries = (
            [round((value - boundaries[0]) / width, 5) for value in boundaries]
            if boundaries
            else []
        )
        return {
            "unit": unit,
            "parent_payload": parent_payload or {},
            "candidate": candidate,
            "rows": rows,
            "canonical_rows": canonical_rows,
            "canonical_cells": canonical_cells,
            "words_by_ref": words_by_ref,
            "lines_by_ref": lines_by_ref,
            "bbox_by_ref": bbox_by_ref,
            "boundaries": boundaries,
            "normalized_boundaries": normalized_boundaries,
            "grid_signature": _sha256_json([maximum, normalized_boundaries]),
            "column_count": maximum,
            "ordinal_header_row": ordinal_row,
            "table_bbox": table_bbox,
            "page_number": page_number,
            "page_height": page_height,
            "reason_codes": sorted(set(reasons)),
        }

    def _assign_logical_groups(self, fragments: list[dict[str, Any]]) -> bool:
        groups: list[list[dict[str, Any]]] = []
        for fragment in fragments:
            if fragment["ordinal_header_row"] is not None:
                group = [fragment]
                groups.append(group)
                fragment["logical_group_key"] = stable_digest(
                    [
                        fragment["unit"].get("source_unit_checksum_ref"),
                        fragment["grid_signature"],
                    ],
                    length=20,
                )
                fragment["fragment_order"] = 1
                continue
            matches = []
            for group in groups:
                previous = group[-1]
                if previous["page_number"] + 1 != fragment["page_number"]:
                    continue
                if previous["column_count"] != fragment["column_count"]:
                    continue
                if not _boundary_vectors_match(
                    previous["normalized_boundaries"],
                    fragment["normalized_boundaries"],
                    tolerance=self.config.boundary_tolerance_ratio * 2,
                ):
                    continue
                if previous["table_bbox"][3] < (
                    previous["page_height"]
                    * self.config.continuation_previous_bottom_ratio
                ):
                    continue
                if fragment["table_bbox"][1] > (
                    fragment["page_height"] * self.config.continuation_top_ratio
                ):
                    continue
                matches.append(group)
            if len(matches) != 1:
                return False
            group = matches[0]
            fragment["logical_group_key"] = group[0]["logical_group_key"]
            fragment["fragment_order"] = len(group) + 1
            group.append(fragment)
        for group in groups:
            for item in group:
                item["fragment_count"] = len(group)
        return bool(groups) and sum(len(group) for group in groups) == len(fragments)

    def _build_projection(
        self,
        *,
        fragment: dict[str, Any],
        group: list[dict[str, Any]],
        logical_table_id: str,
        projection_id: str,
        root_projection_id: str,
        group_validation: dict[str, Any],
    ) -> dict[str, Any]:
        unit = fragment["unit"]
        candidate_ref = str(unit.get("table_candidate_ref") or "")
        column_refs = [
            "tablecol_" + stable_digest([logical_table_id, ordinal], length=24)
            for ordinal in range(1, fragment["column_count"] + 1)
        ]
        row_refs = [str(item["row_ref"] or "") for item in fragment["canonical_rows"]]
        role_by_ref = {
            str(item["row_ref"] or ""): item["structural_role"]
            for item in fragment["canonical_rows"]
        }
        private_values: list[dict[str, Any]] = []
        source_value_index: list[dict[str, Any]] = []
        cells: list[dict[str, Any]] = []
        source_value_refs: list[str] = []
        cell_owned_word_refs: list[str] = []
        source_checksums: dict[str, str] = {}
        for item in fragment["canonical_cells"]:
            cell_ref = str(item.get("cell_ref") or "")
            word_refs = _strings(item.get("word_refs"))
            words = [fragment["words_by_ref"][ref] for ref in word_refs]
            word_source_refs = [
                str(word.get("source_value_ref") or "") for word in words
            ]
            value = " ".join(str(word.get("text") or "") for word in words)
            value_checksum = _checksum_ref("valuechk", value)
            value_path_ref = "tablevaluepath_" + stable_digest(
                [projection_id, cell_ref, word_source_refs], length=24
            )
            private_values.append(
                {
                    "value_path_ref": value_path_ref,
                    "normalized_value": value,
                    "value_checksum_ref": value_checksum,
                    "source_value_refs": word_source_refs,
                }
            )
            for word in words:
                source_ref = str(word.get("source_value_ref") or "")
                word_ref = str(word.get("word_ref") or "")
                word_value = str(word.get("text") or "")
                word_checksum = _checksum_ref("valuechk", word_value)
                word_path_ref = "tablewordvaluepath_" + stable_digest(
                    [projection_id, cell_ref, word_ref, source_ref], length=24
                )
                private_values.append(
                    {
                        "value_path_ref": word_path_ref,
                        "normalized_value": word_value,
                        "value_checksum_ref": word_checksum,
                        "source_value_refs": [source_ref],
                        "source_object_ref": word_ref,
                    }
                )
                source_value_index.append(
                    {
                        "source_value_ref": source_ref,
                        "source_object_ref": word_ref,
                        "cell_ref": cell_ref,
                        "value_path": {
                            "kind": "table_projection_private_value",
                            "value_path_ref": word_path_ref,
                        },
                        "value_checksum_ref": word_checksum,
                    }
                )
                source_value_refs.append(source_ref)
                cell_owned_word_refs.append(word_ref)
                source_checksums[source_ref] = word_checksum
            column_ordinal = int(item["canonical_column_ordinal"])
            span = int(item["canonical_column_span"])
            cells.append(
                {
                    "cell_ref": cell_ref,
                    "row_ref": item.get("row_ref"),
                    "column_ref": column_refs[column_ordinal - 1],
                    "row_ordinal": int(item.get("row_ordinal") or 0),
                    "column_ordinal": column_ordinal,
                    "source_value_refs": word_source_refs,
                    "source_object_refs": word_refs,
                    "cell_value_ref": "cellval_"
                    + stable_digest([cell_ref, value_checksum], length=24),
                    "normalized_private_value_path": value_path_ref,
                    "value_checksum_ref": value_checksum,
                    "value_kind_hints": _value_kind_hints(value),
                    "bbox_ref": item.get("bbox_ref"),
                    "row_span": 1,
                    "column_span": span,
                    "covered_column_refs": column_refs[
                        column_ordinal - 1 : column_ordinal - 1 + span
                    ],
                    "merged_cell_group_ref": (
                        "mergedcell_"
                        + stable_digest([logical_table_id, cell_ref, span], length=20)
                        if span > 1
                        else None
                    ),
                    "split_cell_candidate": False,
                    "multi_line_cell": len(
                        {
                            round(
                                float(
                                    fragment["bbox_by_ref"].get(
                                        str(word.get("bbox_ref") or ""),
                                        [0, 0, 0, 0],
                                    )[1]
                                ),
                                2,
                            )
                            for word in words
                        }
                    )
                    > 1,
                    "wrapped_text_cell": False,
                    "ambiguous_cell_boundary": False,
                    "empty_cell": not word_source_refs,
                    "confidence": "deterministic",
                    "reason_codes": ["broker_pdf_profile_grid_boundary_validated"],
                }
            )
        alias_associations = []
        fallback_line_refs = _strings(unit.get("table_fallback_text_refs"))
        cell_owned_set = set(cell_owned_word_refs)
        for line_ref in fallback_line_refs:
            line = fragment["lines_by_ref"].get(line_ref)
            if not line:
                continue
            line_source_ref = str(line.get("source_value_ref") or "")
            line_value = str(line.get("text") or "")
            line_checksum = _checksum_ref("valuechk", line_value)
            line_path_ref = "tablelinealiaspath_" + stable_digest(
                [projection_id, line_ref, line_source_ref], length=24
            )
            private_values.append(
                {
                    "value_path_ref": line_path_ref,
                    "normalized_value": line_value,
                    "value_checksum_ref": line_checksum,
                    "source_value_refs": [line_source_ref],
                    "source_object_ref": line_ref,
                }
            )
            source_value_index.append(
                {
                    "source_value_ref": line_source_ref,
                    "source_object_ref": line_ref,
                    "cell_ref": None,
                    "value_path": {
                        "kind": "table_projection_private_value",
                        "value_path_ref": line_path_ref,
                    },
                    "value_checksum_ref": line_checksum,
                }
            )
            source_value_refs.append(line_source_ref)
            source_checksums[line_source_ref] = line_checksum
            linked_words = [
                ref for ref in _strings(line.get("word_refs")) if ref in cell_owned_set
            ]
            alias_associations.append(
                {
                    "alias_object_ref": line_ref,
                    "alias_source_value_ref": line_source_ref,
                    "relationship": "lossless_line_projection_of_owned_words",
                    "owned_word_refs": linked_words,
                    "controlled_duplication": True,
                }
            )
        normalized_rows = []
        cells_by_row: dict[str, list[dict[str, Any]]] = {}
        for cell in cells:
            cells_by_row.setdefault(str(cell.get("row_ref") or ""), []).append(cell)
        for item in fragment["canonical_rows"]:
            row_ref = str(item["row_ref"] or "")
            normalized_rows.append(
                {
                    "row_ref": row_ref,
                    "row_ordinal": int(item["row_ordinal"]),
                    "cell_refs": [
                        str(cell.get("cell_ref") or "")
                        for cell in sorted(
                            cells_by_row.get(row_ref, []),
                            key=lambda value: int(value.get("column_ordinal") or 0),
                        )
                    ],
                    "row_role": _legacy_row_role(item["structural_role"]),
                    "canonical_structural_role": item["structural_role"],
                    "row_checksum_ref": _checksum_ref("rowchk", item["cell_refs"]),
                    "reason_codes": ["source_geometry_order_preserved"],
                }
            )
        header_model, header_hierarchy = _header_contract(
            fragment=fragment,
            cells=cells,
            column_refs=column_refs,
            root_projection_id=root_projection_id,
        )
        selected_objects = _strings(
            _object(unit.get("pdf_layout_coverage")).get("selected_source_refs")
        )
        accounted_objects = [*cell_owned_word_refs, *fallback_line_refs]
        duplicate_objects = sorted(
            ref for ref in set(accounted_objects) if accounted_objects.count(ref) > 1
        )
        unaccounted_objects = sorted(set(selected_objects) - set(accounted_objects))
        unexpected_objects = sorted(set(accounted_objects) - set(selected_objects))
        coverage_complete = (
            not duplicate_objects and not unaccounted_objects and not unexpected_objects
        )
        canonical_table_id = "canonicaltable_" + stable_digest(
            [
                CANONICAL_SCHEMA_VERSION,
                logical_table_id,
                unit.get("source_unit_checksum_ref"),
                fragment["grid_signature"],
            ],
            length=24,
        )
        continuation = {
            "logical_table_ref": logical_table_id,
            "fragment_order": int(fragment["fragment_order"]),
            "fragment_count": int(fragment["fragment_count"]),
            "continued_from_projection_ref": (
                root_projection_id if int(fragment["fragment_order"]) > 1 else None
            ),
            "header_inheritance": (
                "local_header"
                if fragment["ordinal_header_row"] is not None
                else "inherited_by_validated_grid_equivalence"
            ),
            "page_order_validated": True,
            "shared_column_grid_validated": True,
        }
        canonical_contract = {
            "schema_version": CANONICAL_SCHEMA_VERSION,
            "canonical_table_id": canonical_table_id,
            "logical_table_id": logical_table_id,
            "profile_id": PROFILE_ID,
            "profile_version": PROFILE_VERSION,
            "source_document_ref": unit.get("document_id"),
            "logical_document_ref": unit.get("document_id"),
            "contributing_page_refs": _strings(unit.get("page_refs")),
            "contributing_region_refs": [unit.get("unit_ref")],
            "ordered_column_refs": column_refs,
            "ordered_row_refs": row_refs,
            "header_hierarchy": header_hierarchy,
            "merged_cell_refs": [
                cell["merged_cell_group_ref"]
                for cell in cells
                if cell.get("merged_cell_group_ref")
            ],
            "total_row_refs": [
                row_ref
                for row_ref, role in role_by_ref.items()
                if role in {"subtotal_row", "total_row"}
            ],
            "continuation": continuation,
            "annotation_associations": [],
            "source_projection_alias_associations": alias_associations,
            "source_accounting": {
                "selected_region_object_refs": selected_objects,
                "cell_owned_word_refs": cell_owned_word_refs,
                "projection_alias_line_refs": fallback_line_refs,
                "all_selected_region_objects_accounted": coverage_complete,
                "duplicate_region_object_refs": duplicate_objects,
                "unaccounted_region_object_refs": unaccounted_objects,
                "unexpected_region_object_refs": unexpected_objects,
                "source_value_refs": sorted(set(source_value_refs)),
                "source_value_checksum_refs": dict(sorted(source_checksums.items())),
            },
            "provenance": {
                "parent_payload_ref": unit.get("parent_payload_ref"),
                "source_checksum_ref": unit.get("source_checksum_ref"),
                "source_unit_checksum_ref": unit.get("source_unit_checksum_ref"),
                "pdf_layout_unit_checksum_ref": unit.get(
                    "pdf_layout_unit_checksum_ref"
                ),
                "table_bbox_ref": unit.get("table_bbox_ref"),
                "original_text_layout_refs": [
                    *_strings(unit.get("layout_word_refs")),
                    *_strings(unit.get("layout_line_refs")),
                    *_strings(unit.get("layout_bbox_refs")),
                ],
            },
            "reconstruction": {
                "method": "deterministic_ruled_grid_boundary_clustering",
                "version": RECONSTRUCTION_VERSION,
                "provider_or_model_used": False,
                "filename_path_id_hash_or_value_allowlist_used": False,
            },
            "validator_version": VALIDATOR_VERSION,
            "terminal_validation_result": "canonical_table_accepted",
            "uncertainty_ledger": [],
            "logical_table_validation": group_validation,
        }
        projection = {
            "schema_version": "broker_reports_normalized_table_projection_v0",
            "table_projection_id": projection_id,
            "table_ref": candidate_ref,
            "canonical_table_id": canonical_table_id,
            "logical_table_id": logical_table_id,
            "canonical_table_scope": CANONICAL_READY_SCOPE,
            "canonical_profile_id": PROFILE_ID,
            "canonical_contract": canonical_contract,
            "source_format": "pdf",
            "table_origin": "deterministic_neutral_canonical_table",
            "source_document_ref": unit.get("document_id"),
            "source_unit_ref": unit.get("unit_ref"),
            "source_unit_refs": [unit.get("unit_ref")],
            "parent_payload_ref": unit.get("parent_payload_ref"),
            "normalization_run_id": unit.get("normalization_run_id"),
            "parser_ref": unit.get("parser_ref"),
            "parser_engine": unit.get("parser"),
            "parser_engine_version": unit.get("parser_version"),
            "parser_config_ref": unit.get("layout_parser_config_ref"),
            "source_checksum_ref": unit.get("source_checksum_ref"),
            "payload_checksum_ref": unit.get("payload_checksum_ref"),
            "source_unit_checksum_ref": unit.get("source_unit_checksum_ref"),
            "table_projection_checksum_ref": None,
            "visibility": "private_case",
            "storage_backend": "project_artifact_payload",
            "projection_status": "ready",
            "row_refs": row_refs,
            "column_refs": column_refs,
            "cell_refs": [str(item.get("cell_ref") or "") for item in cells],
            "cell_value_refs": [
                str(item.get("cell_value_ref") or "") for item in cells
            ],
            "source_value_refs": sorted(set(source_value_refs)),
            "row_count": len(normalized_rows),
            "column_count": len(column_refs),
            "cell_count": len(cells),
            "row_order_policy": "source_order_preserved",
            "column_order_policy": "source_order_preserved",
            "table_bbox_ref": unit.get("table_bbox_ref"),
            "page_refs": _strings(unit.get("page_refs")),
            "sheet_refs": [],
            "section_refs": _strings(unit.get("section_refs")),
            "rows": normalized_rows,
            "cells": cells,
            "private_values": private_values,
            "source_value_index": source_value_index,
            "header_model": header_model,
            "coverage": {
                "schema_version": "broker_reports_table_projection_coverage_v0",
                "coverage_ref": "tablecoverage_"
                + stable_digest(
                    [projection_id, selected_objects, accounted_objects], length=24
                ),
                "selected_source_refs": selected_objects,
                "accounted_source_refs": accounted_objects,
                "table_owned_refs": cell_owned_word_refs,
                "fallback_text_refs": fallback_line_refs,
                "non_table_refs": [],
                "rejected_refs": [],
                "duplicate_accounted_refs": duplicate_objects,
                "unaccounted_refs": unaccounted_objects,
                "selected_total": len(selected_objects),
                "accounted_total": len(accounted_objects),
                "coverage_status": "complete" if coverage_complete else "partial",
                "all_selected_refs_accounted": coverage_complete,
            },
            "quality": {
                "schema_version": "broker_reports_table_reconstruction_quality_v0",
                "row_alignment_score": 1.0,
                "column_alignment_score": 1.0,
                "header_confidence": "deterministic",
                "cell_boundary_confidence": 1.0,
                "coverage_completeness": 1.0 if coverage_complete else 0.0,
                "duplicate_overlap_count": len(duplicate_objects),
                "unaccounted_ref_count": len(unaccounted_objects),
                "fallback_required": False,
                "reconstruction_quality": "high" if coverage_complete else "blocked",
            },
            "table_candidate_status": "canonical_table_accepted",
            "reconstruction_strategy": "deterministic_ruled_grid_profile_v1",
            "reconstruction_reason_codes": [
                "broker_pdf_profile_v1_matched",
                "merged_cells_explicitly_mapped",
                "source_value_accounting_complete",
            ],
            "reconstruction_quality": "high" if coverage_complete else "blocked",
            "geometry": {
                "table_strategy_ref": unit.get("table_strategy_ref"),
                "geometry_confidence": unit.get("geometry_confidence"),
                "contributing_word_refs": cell_owned_word_refs,
                "contributing_line_refs": fallback_line_refs,
                "fallback_text_refs": [],
                "fallback_source_value_refs": [],
                "duplicate_ownership_refs": duplicate_objects,
                "unaccounted_ownership_refs": unaccounted_objects,
            },
            "semantic_table_truth_claimed": False,
            "source_facts_extracted": False,
            "tax_meaning_inferred": False,
            "financial_semantics_introduced": False,
            "knowledge_rag_used": False,
            "vectorization_performed": False,
            "ocr_vlm_used": False,
            "page_rendering_used_for_extraction": False,
        }
        return projection


def validate_region_decision(value: Any) -> dict[str, Any]:
    decision = _object(value)
    errors = []
    if decision.get("schema_version") != REGION_DECISION_SCHEMA_VERSION:
        errors.append("typed_region_decision_schema_invalid")
    if decision.get("region_type") not in REGION_TYPES:
        errors.append("typed_region_decision_type_invalid")
    if not decision.get("source_unit_ref") or not decision.get("document_ref"):
        errors.append("typed_region_decision_scope_missing")
    if (
        decision.get("status") == "canonical_table_accepted"
        and decision.get("region_type") != "canonical_table_candidate"
    ):
        errors.append("typed_region_decision_promotion_type_mismatch")
    if decision.get("detector_authority") != "proposal_only":
        errors.append("typed_region_decision_detector_authority_invalid")
    if decision.get("status") == "canonical_table_accepted":
        if decision.get("promotion_authority") != VALIDATOR_VERSION:
            errors.append("typed_region_decision_promotion_authority_invalid")
        if not decision.get("table_projection_ref") or not decision.get(
            "canonical_table_ref"
        ):
            errors.append("typed_region_decision_canonical_refs_missing")
    return {
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "reason_codes": errors,
    }


def validate_canonical_neutral_projection(value: Any) -> dict[str, Any]:
    projection = _object(value)
    contract = _object(projection.get("canonical_contract"))
    errors: list[str] = []
    if contract.get("schema_version") != CANONICAL_SCHEMA_VERSION:
        errors.append("canonical_neutral_table_schema_invalid")
    if projection.get("canonical_profile_id") != PROFILE_ID:
        errors.append("canonical_neutral_table_profile_invalid")
    if projection.get("canonical_table_scope") != CANONICAL_READY_SCOPE:
        errors.append("canonical_neutral_table_scope_invalid")
    if contract.get("terminal_validation_result") != "canonical_table_accepted":
        errors.append("canonical_neutral_table_terminal_result_invalid")
    if contract.get("validator_version") != VALIDATOR_VERSION:
        errors.append("canonical_neutral_table_validator_version_invalid")
    if (
        contract.get("canonical_table_id") != projection.get("canonical_table_id")
        or contract.get("logical_table_id") != projection.get("logical_table_id")
        or contract.get("profile_id") != projection.get("canonical_profile_id")
    ):
        errors.append("canonical_neutral_table_identity_mismatch")
    if (
        contract.get("source_document_ref") != projection.get("source_document_ref")
        or contract.get("logical_document_ref") != projection.get("source_document_ref")
        or _strings(contract.get("contributing_region_refs"))
        != _strings(projection.get("source_unit_refs"))
        or _strings(contract.get("contributing_page_refs"))
        != _strings(projection.get("page_refs"))
        or _strings(projection.get("source_unit_refs"))
        != [str(projection.get("source_unit_ref") or "")]
    ):
        errors.append("canonical_neutral_table_source_membership_mismatch")
    provenance = _object(contract.get("provenance"))
    if (
        provenance.get("parent_payload_ref") != projection.get("parent_payload_ref")
        or provenance.get("source_checksum_ref")
        != projection.get("source_checksum_ref")
        or provenance.get("source_unit_checksum_ref")
        != projection.get("source_unit_checksum_ref")
        or provenance.get("table_bbox_ref") != projection.get("table_bbox_ref")
        or not provenance.get("pdf_layout_unit_checksum_ref")
    ):
        errors.append("canonical_neutral_table_provenance_mismatch")
    if projection.get("financial_semantics_introduced") is not False:
        errors.append("canonical_neutral_table_financial_semantics_forbidden")
    reconstruction = _object(contract.get("reconstruction"))
    if reconstruction.get("provider_or_model_used") is not False:
        errors.append("canonical_neutral_table_model_authority_forbidden")
    if reconstruction.get("filename_path_id_hash_or_value_allowlist_used") is not False:
        errors.append("canonical_neutral_table_allowlist_forbidden")
    if (
        reconstruction.get("method") != "deterministic_ruled_grid_boundary_clustering"
        or reconstruction.get("version") != RECONSTRUCTION_VERSION
    ):
        errors.append("canonical_neutral_table_reconstruction_method_invalid")
    rows = _dicts(projection.get("rows"))
    cells = _dicts(projection.get("cells"))
    columns = _strings(projection.get("column_refs"))
    if not rows or len(columns) < 2 or not cells:
        errors.append("canonical_neutral_table_structure_missing")
    row_refs = [str(item.get("row_ref") or "") for item in rows]
    if (
        row_refs != _strings(projection.get("row_refs"))
        or row_refs != _strings(contract.get("ordered_row_refs"))
        or len(row_refs) != len(set(row_refs))
    ):
        errors.append("canonical_neutral_table_row_order_invalid")
    if columns != _strings(contract.get("ordered_column_refs")) or columns != list(
        dict.fromkeys(columns)
    ):
        errors.append("canonical_neutral_table_column_order_invalid")
    cell_refs = [str(item.get("cell_ref") or "") for item in cells]
    if cell_refs != _strings(projection.get("cell_refs")) or len(cell_refs) != len(
        set(cell_refs)
    ):
        errors.append("canonical_neutral_table_cell_identity_invalid")
    rows_by_ref = {str(item.get("row_ref") or ""): item for item in rows}
    row_ordinals = [int(item.get("row_ordinal") or 0) for item in rows]
    if row_ordinals != sorted(row_ordinals) or len(row_ordinals) != len(
        set(row_ordinals)
    ):
        errors.append("canonical_neutral_table_row_ordinal_invalid")
    if (
        projection.get("row_count") != len(rows)
        or projection.get("column_count") != len(columns)
        or projection.get("cell_count") != len(cells)
    ):
        errors.append("canonical_neutral_table_count_mismatch")
    occupied: set[tuple[str, int]] = set()
    cells_by_row: dict[str, list[dict[str, Any]]] = {}
    for cell in cells:
        row_ref = str(cell.get("row_ref") or "")
        start = int(cell.get("column_ordinal") or 0)
        span = int(cell.get("column_span") or 0)
        if (
            row_ref not in rows_by_ref
            or start < 1
            or span < 1
            or start + span - 1 > len(columns)
        ):
            errors.append("canonical_neutral_table_cell_membership_invalid")
            continue
        cells_by_row.setdefault(row_ref, []).append(cell)
        if int(cell.get("row_ordinal") or 0) != int(
            rows_by_ref[row_ref].get("row_ordinal") or 0
        ):
            errors.append("canonical_neutral_table_cell_row_ordinal_invalid")
        expected = columns[start - 1 : start - 1 + span]
        if (
            cell.get("column_ref") != expected[0]
            or _strings(cell.get("covered_column_refs")) != expected
        ):
            errors.append("canonical_neutral_table_cell_span_invalid")
        for ordinal in range(start, start + span):
            position = (row_ref, ordinal)
            if position in occupied:
                errors.append("canonical_neutral_table_cell_overlap")
            occupied.add(position)
        if bool(cell.get("empty_cell")) == bool(
            _strings(cell.get("source_value_refs"))
        ):
            errors.append("canonical_neutral_table_empty_cell_invalid")
        merged_ref = str(cell.get("merged_cell_group_ref") or "")
        if (span > 1) != bool(merged_ref):
            errors.append("canonical_neutral_table_merged_cell_mapping_invalid")
        if (
            cell.get("row_span") != 1
            or cell.get("split_cell_candidate") is not False
            or cell.get("ambiguous_cell_boundary") is not False
            or cell.get("confidence") != "deterministic"
        ):
            errors.append("canonical_neutral_table_cell_ambiguity_unresolved")
    for row_ref, row in rows_by_ref.items():
        expected_cells = [
            str(item.get("cell_ref") or "")
            for item in sorted(
                cells_by_row.get(row_ref, []),
                key=lambda item: int(item.get("column_ordinal") or 0),
            )
        ]
        if _strings(row.get("cell_refs")) != expected_cells:
            errors.append("canonical_neutral_table_row_cell_membership_invalid")
        if row.get("row_checksum_ref") != _checksum_ref("rowchk", expected_cells):
            errors.append("canonical_neutral_table_row_checksum_invalid")
    expected_merged_refs = [
        str(cell.get("merged_cell_group_ref") or "")
        for cell in cells
        if cell.get("merged_cell_group_ref")
    ]
    if _strings(contract.get("merged_cell_refs")) != expected_merged_refs or len(
        expected_merged_refs
    ) != len(set(expected_merged_refs)):
        errors.append("canonical_neutral_table_merged_cell_inventory_invalid")
    expected_total_refs = [
        str(row.get("row_ref") or "")
        for row in rows
        if row.get("canonical_structural_role") in {"subtotal_row", "total_row"}
    ]
    if _strings(contract.get("total_row_refs")) != expected_total_refs:
        errors.append("canonical_neutral_table_total_row_inventory_invalid")
    header = _object(contract.get("header_hierarchy"))
    header_model = _object(projection.get("header_model"))
    continuation = _object(contract.get("continuation"))
    if continuation.get("header_inheritance") == "local_header":
        nodes = _dicts(header.get("nodes"))
        labels = _dicts(header_model.get("column_labels"))
        header_rows = {
            str(row.get("row_ref") or "")
            for row in rows
            if row.get("canonical_structural_role") == "header_row"
        }
        ordinal_rows = [
            str(row.get("row_ref") or "")
            for row in rows
            if row.get("canonical_structural_role") == "header_ordinal_row"
        ]
        cell_by_ref = {str(cell.get("cell_ref") or ""): cell for cell in cells}
        node_by_ref = {str(node.get("header_ref") or ""): node for node in nodes}
        if header.get("status") != "validated" or not nodes:
            errors.append("canonical_neutral_table_header_assignment_invalid")
        if (
            len(ordinal_rows) != 1
            or header.get("ordinal_marker_row_ref") != ordinal_rows[0]
            or _strings(header_model.get("header_row_refs"))
            != [
                str(row.get("row_ref") or "")
                for row in rows
                if row.get("canonical_structural_role")
                in {"header_row", "header_ordinal_row"}
            ]
        ):
            errors.append("canonical_neutral_table_ordinal_header_invalid")
        for node in nodes:
            cell = cell_by_ref.get(str(node.get("cell_ref") or ""))
            if (
                not cell
                or str(node.get("row_ref") or "") not in header_rows
                or _strings(node.get("covered_column_refs"))
                != _strings(cell.get("covered_column_refs"))
                or _strings(node.get("source_value_refs"))
                != _strings(cell.get("source_value_refs"))
                or node.get("column_span") != cell.get("column_span")
            ):
                errors.append("canonical_neutral_table_header_node_invalid")
        if (
            len(node_by_ref) != len(nodes)
            or [str(label.get("column_ref") or "") for label in labels] != columns
            or header_model.get("header_to_column_mapping_status") != "mapped"
            or any(
                label.get("header_ref") not in node_by_ref
                or label.get("mapping_status") != "mapped"
                or label.get("header_confidence") != "deterministic"
                for label in labels
            )
        ):
            errors.append("canonical_neutral_table_header_column_mapping_invalid")
    elif (
        continuation.get("header_inheritance")
        == "inherited_by_validated_grid_equivalence"
    ):
        if (
            header.get("status") != "inherited_validated"
            or _dicts(header.get("nodes"))
            or not header.get("inherited_from_projection_ref")
            or _dicts(header_model.get("column_labels"))
        ):
            errors.append("canonical_neutral_table_inherited_header_invalid")
    else:
        errors.append("canonical_neutral_table_header_inheritance_invalid")
    accounting = _object(contract.get("source_accounting"))
    selected = _strings(accounting.get("selected_region_object_refs"))
    owners = [
        *_strings(accounting.get("cell_owned_word_refs")),
        *_strings(accounting.get("projection_alias_line_refs")),
    ]
    duplicates = sorted(ref for ref in set(owners) if owners.count(ref) > 1)
    unaccounted = sorted(set(selected) - set(owners))
    unexpected = sorted(set(owners) - set(selected))
    if duplicates or unaccounted or unexpected:
        errors.append("canonical_neutral_table_region_membership_incomplete")
    if accounting.get("all_selected_region_objects_accounted") is not True:
        errors.append("canonical_neutral_table_source_coverage_incomplete")
    if (
        _strings(accounting.get("duplicate_region_object_refs")) != duplicates
        or _strings(accounting.get("unaccounted_region_object_refs")) != unaccounted
        or _strings(accounting.get("unexpected_region_object_refs")) != unexpected
    ):
        errors.append("canonical_neutral_table_source_accounting_ledger_invalid")
    source_refs = _strings(projection.get("source_value_refs"))
    if len(source_refs) != len(set(source_refs)):
        errors.append("canonical_neutral_table_source_value_duplicate")
    indexed = [
        str(item.get("source_value_ref") or "")
        for item in _dicts(projection.get("source_value_index"))
    ]
    if sorted(indexed) != sorted(source_refs) or len(indexed) != len(set(indexed)):
        errors.append("canonical_neutral_table_source_value_index_invalid")
    checksum_refs = _object(accounting.get("source_value_checksum_refs"))
    if set(checksum_refs) != set(source_refs):
        errors.append("canonical_neutral_table_source_checksum_coverage_invalid")
    aliases = _dicts(contract.get("source_projection_alias_associations"))
    alias_refs = [str(item.get("alias_object_ref") or "") for item in aliases]
    if sorted(alias_refs) != sorted(
        _strings(accounting.get("projection_alias_line_refs"))
    ):
        errors.append("canonical_neutral_table_alias_accounting_invalid")
    if any(
        item.get("relationship") != "lossless_line_projection_of_owned_words"
        or item.get("controlled_duplication") is not True
        or not set(_strings(item.get("owned_word_refs")))
        <= set(_strings(accounting.get("cell_owned_word_refs")))
        for item in aliases
    ):
        errors.append("canonical_neutral_table_alias_relationship_invalid")
    if contract.get("uncertainty_ledger") != []:
        errors.append("canonical_neutral_table_uncertainty_unresolved")
    logical_validation = _object(contract.get("logical_table_validation"))
    if (
        logical_validation.get("every_region_consumed_once") is not True
        or logical_validation.get("continuation_validated") is not True
        or logical_validation.get("shared_column_count") != len(columns)
    ):
        errors.append("canonical_neutral_table_continuation_invalid")
    fragment_order = int(continuation.get("fragment_order") or 0)
    fragment_count = int(continuation.get("fragment_count") or 0)
    page_order = logical_validation.get("page_order")
    if (
        fragment_count != int(logical_validation.get("regions_total") or 0)
        or not 1 <= fragment_order <= fragment_count
        or not isinstance(page_order, list)
        or len(page_order) != fragment_count
        or page_order != sorted(page_order)
        or len(page_order) != len(set(page_order))
        or bool(logical_validation.get("continuation_required")) != (fragment_count > 1)
        or (fragment_order == 1)
        != (continuation.get("continued_from_projection_ref") is None)
        or (fragment_order == 1)
        != (continuation.get("header_inheritance") == "local_header")
        or int(logical_validation.get("logical_rows_total") or 0) < len(rows)
        or not set(expected_total_refs)
        <= set(_strings(logical_validation.get("logical_total_row_refs")))
    ):
        errors.append("canonical_neutral_table_continuation_order_invalid")
    return {
        "schema_version": "broker_reports_canonical_neutral_table_validation_v1",
        "validator_version": VALIDATOR_VERSION,
        "canonical_table_id": projection.get("canonical_table_id"),
        "validator_status": "passed" if not errors else "failed",
        "passed": not errors,
        "errors_count": len(set(errors)),
        "reason_codes": sorted(set(errors)),
    }


def validate_canonical_integrity(projection: dict[str, Any]) -> bool:
    return projection.get("canonical_integrity_hash") == _canonical_integrity_hash(
        projection
    )


def _canonical_integrity_hash(projection: dict[str, Any]) -> str:
    material = copy.deepcopy(projection)
    material.pop("canonical_integrity_hash", None)
    material.pop("table_projection_checksum_ref", None)
    material.pop("validator_status", None)
    material.pop("validator_reason_codes", None)
    return (
        "canonicaltablehash_" + hashlib.sha256(_canonical_bytes(material)).hexdigest()
    )


def _find_ordinal_header_row(
    cells_by_row: dict[int, list[dict[str, Any]]], column_count: int
) -> int | None:
    matches = []
    for row_ordinal, cells in cells_by_row.items():
        ordered = sorted(cells, key=lambda item: int(item["canonical_column_ordinal"]))
        if len(ordered) != column_count:
            continue
        if any(int(item["canonical_column_span"]) != 1 for item in ordered):
            continue
        values = [_strict_integer(item.get("text")) for item in ordered]
        if values == list(range(1, column_count + 1)):
            matches.append(row_ordinal)
    return matches[0] if len(matches) == 1 else None


def _structural_row_role(
    *,
    row_ordinal: int,
    ordinal_header_row: int | None,
    cells: list[dict[str, Any]],
    column_count: int,
) -> str:
    if ordinal_header_row is not None and row_ordinal < ordinal_header_row:
        return "header_row"
    if ordinal_header_row is not None and row_ordinal == ordinal_header_row:
        return "header_ordinal_row"
    values = [_normalize_text(item.get("text")) for item in cells]
    nonblank = [value for value in values if value]
    if not nonblank:
        return "blank_row"
    first = nonblank[0]
    if first.startswith("общий итог") or first in {"всего", "grand total"}:
        return "total_row"
    if first.startswith("итого по") or first.startswith("subtotal"):
        return "subtotal_row"
    if first.startswith("итого") or first.startswith("total"):
        return "total_row"
    if (
        len(cells) == 1
        and int(cells[0].get("canonical_column_span") or 0) == column_count
    ):
        return "section_heading_row"
    return "data_row"


def _header_contract(
    *,
    fragment: dict[str, Any],
    cells: list[dict[str, Any]],
    column_refs: list[str],
    root_projection_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    ordinal_row = fragment["ordinal_header_row"]
    if ordinal_row is None:
        return (
            {
                "header_row_refs": [],
                "repeated_header_row_refs": [],
                "multi_row_header": False,
                "column_labels": [],
                "header_to_column_mapping_status": "inherited_validated",
                "pdf_header_candidate": False,
                "semantic_header_truth_claimed": False,
            },
            {
                "status": "inherited_validated",
                "nodes": [],
                "inherited_from_projection_ref": root_projection_id,
                "ordinal_marker_row_ref": None,
            },
        )
    rows = {int(item["row_ordinal"]): item for item in fragment["canonical_rows"]}
    header_row_refs = [
        str(item["row_ref"] or "")
        for item in fragment["canonical_rows"]
        if int(item["row_ordinal"]) < ordinal_row
    ]
    nodes = []
    labels_by_column: dict[str, list[dict[str, Any]]] = {ref: [] for ref in column_refs}
    for cell in cells:
        if int(cell.get("row_ordinal") or 0) >= ordinal_row:
            continue
        covered = _strings(cell.get("covered_column_refs"))
        node = {
            "header_ref": "tableheader_"
            + stable_digest([cell.get("cell_ref"), covered], length=20),
            "cell_ref": cell.get("cell_ref"),
            "row_ref": cell.get("row_ref"),
            "source_value_refs": _strings(cell.get("source_value_refs")),
            "covered_column_refs": covered,
            "column_span": int(cell.get("column_span") or 0),
            "structural_role": "header",
        }
        nodes.append(node)
        for ref in covered:
            labels_by_column.setdefault(ref, []).append(node)
    labels = []
    for ref in column_refs:
        path = labels_by_column.get(ref, [])
        if not path:
            continue
        leaf = path[-1]
        labels.append(
            {
                "header_ref": leaf["header_ref"],
                "column_ref": ref,
                "cell_ref": leaf["cell_ref"],
                "source_value_refs": leaf["source_value_refs"],
                "normalized_label": "source_header_preserved",
                "header_confidence": "deterministic",
                "mapping_status": "mapped",
            }
        )
    ordinal_ref = str(rows.get(ordinal_row, {}).get("row_ref") or "")
    model = {
        "header_row_refs": header_row_refs + ([ordinal_ref] if ordinal_ref else []),
        "repeated_header_row_refs": [],
        "multi_row_header": len(header_row_refs) > 1,
        "column_labels": labels,
        "header_to_column_mapping_status": (
            "mapped" if len(labels) == len(column_refs) else "missing_or_ambiguous"
        ),
        "pdf_header_candidate": False,
        "semantic_header_truth_claimed": False,
    }
    hierarchy = {
        "status": "validated" if len(labels) == len(column_refs) else "invalid",
        "nodes": nodes,
        "inherited_from_projection_ref": None,
        "ordinal_marker_row_ref": ordinal_ref,
    }
    return model, hierarchy


def _legacy_row_role(role: str) -> str:
    return {
        "header_row": "header_row",
        "header_ordinal_row": "header_row",
        "blank_row": "blank_row",
        "section_heading_row": "layout_row",
        "subtotal_row": "subtotal_row",
        "total_row": "summary_row",
        "data_row": "data_row",
    }.get(role, "unknown_row_role")


def _nearest_boundary(
    boundaries: list[float], value: float, tolerance: float
) -> int | None:
    if not boundaries:
        return None
    distances = [abs(item - value) for item in boundaries]
    minimum = min(distances)
    if minimum > tolerance:
        return None
    matches = [index for index, distance in enumerate(distances) if distance == minimum]
    return matches[0] if len(matches) == 1 else None


def _boundary_vectors_match(
    left: list[float], right: list[float], *, tolerance: float
) -> bool:
    return len(left) == len(right) and all(
        abs(a - b) <= tolerance for a, b in zip(left, right)
    )


def _strict_integer(value: Any) -> int | None:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    return int(text) if re.fullmatch(r"\d+", text) else None


def _normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return " ".join(re.findall(r"[\w]+", text, flags=re.UNICODE))


def _value_kind_hints(value: str) -> list[str]:
    stripped = value.strip()
    if not stripped:
        return ["blank"]
    if re.fullmatch(r"[+-]?\d+(?:[.,]\d+)?", stripped.replace(" ", "")):
        return ["decimal_like"]
    if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", stripped):
        return ["date_like"]
    if re.fullmatch(r"[A-Z]{3}", stripped):
        return ["currency_code_like"]
    return ["text"]


def _valid_bbox(value: list[Any]) -> bool:
    return (
        len(value) == 4
        and all(isinstance(item, (int, float)) for item in value)
        and float(value[2]) > float(value[0])
        and float(value[3]) > float(value[1])
    )


def _checksum_ref(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical_bytes(value)).hexdigest()[:24]}"


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value or [] if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _strings(value: Any) -> list[str]:
    return (
        [str(item) for item in value or [] if item is not None and str(item)]
        if isinstance(value, list)
        else []
    )
