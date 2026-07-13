from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import PDF_TABLE_MATERIALIZATION_SCHEMA, sha256_json


PDF_HYBRID_STRUCTURAL_VALIDATION_SCHEMA = (
    "broker_reports_pdf_hybrid_structural_placement_validation_v2"
)
PDF_HYBRID_CONTINUATION_SCHEMA = "broker_reports_pdf_hybrid_continuation_contract_v2"
PDF_HYBRID_CONTINUATION_VALIDATION_SCHEMA = (
    "broker_reports_pdf_hybrid_continuation_validation_v2"
)
PDF_HYBRID_STRUCTURE_POLICY_VERSION = "pdf_hybrid_structure_policy_v2"
FACTORY_REQUIRED = (
    "PdfHybridStructureFactory.create is the only independent placement and continuation validation entrypoint"
)
FORBIDDEN = (
    "Exact provenance must not imply placement correctness; structural validation must fail closed"
)


class PdfHybridStructureError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfHybridStructureConfig:
    policy_version: str = PDF_HYBRID_STRUCTURE_POLICY_VERSION
    coordinate_tolerance_points: float = 0.75
    continuation_boundary_tolerance_ratio: float = 0.04


class PdfHybridStructureFactory:
    def __init__(self, config: PdfHybridStructureConfig | None = None) -> None:
        self.config = config or PdfHybridStructureConfig()

    def create(self) -> "PdfHybridStructureValidator":
        if self.config.policy_version != PDF_HYBRID_STRUCTURE_POLICY_VERSION:
            raise PdfHybridStructureError("pdf_hybrid_structure_policy_invalid")
        return PdfHybridStructureValidator(self.config)


class PdfHybridStructureValidator:
    def __init__(self, config: PdfHybridStructureConfig) -> None:
        self.config = config

    def validate_placement(
        self,
        *,
        compact_ledger: dict[str, Any],
        materialization: dict[str, Any],
    ) -> dict[str, Any]:
        gates: dict[str, dict[str, Any]] = {}
        dictionary = _object(compact_ledger.get("private_candidate_dictionary"))
        cells = _dicts(materialization.get("cells"))
        rows = int(materialization.get("row_count") or 0)
        columns = int(materialization.get("column_count") or 0)
        identity_errors = []
        if materialization.get("schema_version") != PDF_TABLE_MATERIALIZATION_SCHEMA:
            identity_errors.append("pdf_hybrid_structure_materialization_schema_invalid")
        if materialization.get("candidate_dictionary_hash") != compact_ledger.get(
            "candidate_dictionary_hash"
        ):
            identity_errors.append("pdf_hybrid_structure_dictionary_identity_mismatch")
        if rows != int(compact_ledger.get("row_count") or 0) or columns != int(
            compact_ledger.get("column_count") or 0
        ):
            identity_errors.append("pdf_hybrid_structure_full_shape_mismatch")
        gates["identity_and_full_shape"] = _gate(identity_errors)

        used = [
            str(candidate_id)
            for cell in cells
            for candidate_id in cell.get("candidate_ids") or []
        ]
        ownership_errors = []
        if set(used) != set(dictionary):
            ownership_errors.append("pdf_hybrid_structure_candidate_coverage_incomplete")
        if len(used) != len(set(used)):
            ownership_errors.append("pdf_hybrid_structure_candidate_not_exactly_once")
        if materialization.get("omitted_candidate_ids"):
            ownership_errors.append("pdf_hybrid_structure_candidate_omitted")
        if materialization.get("extra_candidate_ids"):
            ownership_errors.append("pdf_hybrid_structure_candidate_extra")
        gates["exactly_once_candidate_ownership"] = _gate(ownership_errors)

        cell_by_position = {
            (int(item.get("row_ordinal") or 0), int(item.get("column_ordinal") or 0)): item
            for item in cells
        }
        grid_errors = []
        expected_positions = {
            (row, column)
            for row in range(1, rows + 1)
            for column in range(1, columns + 1)
        }
        if set(cell_by_position) != expected_positions or len(cells) != rows * columns:
            grid_errors.append("pdf_hybrid_structure_rectangular_grid_incomplete")
        gates["complete_rectangular_grid"] = _gate(grid_errors)

        column_model = _dicts(compact_ledger.get("column_model"))
        boundary_errors = _axis_errors(column_model, columns)
        row_model = _dicts(compact_ledger.get("row_model"))
        boundary_errors.extend(_axis_errors(row_model, rows))
        gates["independent_boundaries"] = _gate(boundary_errors)

        placement_errors = []
        spatial_errors = []
        for position, cell in cell_by_position.items():
            row, column = position
            for candidate_id in cell.get("candidate_ids") or []:
                candidate = _object(dictionary.get(str(candidate_id)))
                if not candidate:
                    placement_errors.append("pdf_hybrid_structure_candidate_unknown")
                    continue
                if int(candidate.get("expected_row_ordinal") or 0) != row:
                    placement_errors.append("pdf_hybrid_structure_candidate_row_mismatch")
                if int(candidate.get("expected_column_ordinal") or 0) != column:
                    placement_errors.append("pdf_hybrid_structure_candidate_column_mismatch")
                bbox = _bbox(candidate.get("source_bbox"))
                source_cell_bbox = _bbox(candidate.get("source_cell_bbox"))
                if bbox is None or source_cell_bbox is None:
                    spatial_errors.append("pdf_hybrid_structure_candidate_bbox_invalid")
                    continue
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                expected_column = _axis_entry(column_model, column)
                expected_row = _axis_entry(row_model, row)
                tolerance = self.config.coordinate_tolerance_points
                if expected_column is None or not (
                    float(expected_column["start"]) - tolerance
                    <= center_x
                    <= float(expected_column["end"]) + tolerance
                ):
                    spatial_errors.append("pdf_hybrid_structure_candidate_column_incompatible")
                if expected_row is None or not (
                    float(expected_row["start"]) - tolerance
                    <= center_y
                    <= float(expected_row["end"]) + tolerance
                ):
                    spatial_errors.append("pdf_hybrid_structure_candidate_row_incompatible")
                if not _center_inside(bbox, source_cell_bbox, tolerance):
                    spatial_errors.append("pdf_hybrid_structure_candidate_cell_incompatible")
        gates["candidate_to_cell_placement"] = _gate(placement_errors)
        gates["spatial_compatibility"] = _gate(spatial_errors)

        empty_errors = []
        expected_occupied = {
            (
                int(candidate.get("expected_row_ordinal") or 0),
                int(candidate.get("expected_column_ordinal") or 0),
            )
            for candidate in dictionary.values()
            if isinstance(candidate, dict)
        }
        for position in expected_positions:
            cell = cell_by_position.get(position, {})
            actual_empty = not bool(cell.get("candidate_ids"))
            expected_empty = position not in expected_occupied
            if actual_empty != expected_empty or bool(cell.get("explicit_empty")) != actual_empty:
                empty_errors.append("pdf_hybrid_structure_empty_cell_position_mismatch")
                break
        gates["explicit_empty_positions"] = _gate(empty_errors)

        row_order_errors = []
        previous = None
        for row in range(1, rows + 1):
            entry = _axis_entry(row_model, row)
            if entry is None:
                continue
            current = (float(entry["start"]), float(entry["end"]))
            if previous is not None and current[0] < previous[0]:
                row_order_errors.append("pdf_hybrid_structure_row_order_invalid")
            previous = current
        gates["row_order"] = _gate(row_order_errors)

        header_errors = []
        header_depth = int(compact_ledger.get("header_depth") or 0)
        expected_headers = list(range(1, header_depth + 1))
        if list(materialization.get("header_rows") or []) != expected_headers:
            header_errors.append("pdf_hybrid_structure_header_rows_mismatch")
        header_errors.extend(
            _merged_header_errors(
                dictionary=dictionary,
                materialization=materialization,
                column_model=column_model,
                header_depth=header_depth,
                tolerance=self.config.coordinate_tolerance_points,
            )
        )
        gates["repeated_and_merged_headers"] = _gate(header_errors)

        reason_codes = sorted(
            set(code for gate in gates.values() for code in gate["reason_codes"])
        )
        result = {
            "schema_version": PDF_HYBRID_STRUCTURAL_VALIDATION_SCHEMA,
            "policy_version": self.config.policy_version,
            "validation_id": "pdfhybridstruct_"
            + stable_digest(
                [
                    compact_ledger.get("ledger_id"),
                    materialization.get("placement_checksum"),
                ],
                length=24,
            ),
            "ledger_id": compact_ledger.get("ledger_id"),
            "table_ref": compact_ledger.get("table_ref"),
            "materialization_checksum": materialization.get(
                "materialization_checksum"
            ),
            "placement_checksum": materialization.get("placement_checksum"),
            "passed": not reason_codes,
            "gates": gates,
            "reason_codes": reason_codes,
            "metrics": {
                "rows": rows,
                "columns": columns,
                "grid_positions": rows * columns,
                "candidate_ids_expected": len(dictionary),
                "candidate_ids_used": len(used),
                "candidate_ids_unique": len(set(used)),
                "explicit_empty_positions": sum(
                    bool(item.get("explicit_empty")) for item in cells
                ),
                "column_boundaries": len(column_model),
                "row_boundaries": len(row_model),
            },
            "source_authenticity_implied": False,
            "independently_checkable": True,
            "authoritative": False,
        }
        result["validation_checksum"] = sha256_json(result)
        return result

    def validate_continuation(
        self,
        *,
        contract: dict[str, Any],
        fragment_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        errors = []
        if contract.get("schema_version") != PDF_HYBRID_CONTINUATION_SCHEMA:
            errors.append("pdf_hybrid_continuation_contract_schema_invalid")
        group_id = str(contract.get("continuation_group_id") or "")
        fragments = _dicts(contract.get("fragments"))
        if not group_id or len(fragments) < 2 or len(fragment_results) != len(fragments):
            errors.append("pdf_hybrid_continuation_fragment_contract_invalid")
        if contract.get("subtotal_policy") not in {
            "preserve_fragment_subtotals",
            "deduplicate_exact_boundary_subtotal",
        }:
            errors.append("pdf_hybrid_continuation_subtotal_policy_invalid")
        if contract.get("duplicate_row_policy") not in {
            "forbid",
            "allow_explicit_repeated_header_only",
        }:
            errors.append("pdf_hybrid_continuation_duplicate_policy_invalid")
        expected_order = list(range(1, len(fragments) + 1))
        if [int(item.get("fragment_order") or 0) for item in fragments] != expected_order:
            errors.append("pdf_hybrid_continuation_fragment_order_invalid")
        page_numbers = [int(item.get("page_number") or 0) for item in fragments]
        if page_numbers != sorted(page_numbers) or len(set(page_numbers)) != len(page_numbers):
            errors.append("pdf_hybrid_continuation_page_order_invalid")

        column_models = []
        total_rows = 0
        total_candidates = 0
        total_used = 0
        word_refs: list[str] = []
        repeated_header_rows = 0
        for definition, result in zip(fragments, fragment_results):
            ledger = _object(result.get("compact_ledger"))
            materialization = _object(result.get("materialization"))
            placement = _object(result.get("structural_validation"))
            if (
                definition.get("table_ref") != ledger.get("table_ref")
                or int(definition.get("page_number") or 0)
                != int(ledger.get("page_number") or 0)
            ):
                errors.append("pdf_hybrid_continuation_fragment_identity_mismatch")
            if int(ledger.get("column_count") or 0) != int(
                contract.get("shared_column_count") or 0
            ):
                errors.append("pdf_hybrid_continuation_shared_column_count_mismatch")
            if placement.get("passed") is not True:
                errors.append("pdf_hybrid_continuation_fragment_placement_blocked")
            policy = definition.get("repeated_header_policy")
            depth = int(ledger.get("header_depth") or 0)
            if policy == "source_header":
                if depth < 1:
                    errors.append("pdf_hybrid_continuation_source_header_missing")
                if int(definition.get("fragment_order") or 0) > 1:
                    repeated_header_rows += depth
            elif policy == "no_repeated_header":
                if depth != 0:
                    errors.append("pdf_hybrid_continuation_unexpected_repeated_header")
            else:
                errors.append("pdf_hybrid_continuation_header_policy_invalid")
            dictionary = _object(ledger.get("private_candidate_dictionary"))
            total_rows += int(materialization.get("row_count") or 0)
            total_candidates += len(dictionary)
            total_used += len(materialization.get("selected_candidate_ids") or [])
            word_refs.extend(
                str(ref)
                for candidate in dictionary.values()
                if isinstance(candidate, dict)
                for ref in candidate.get("word_refs") or []
            )
            column_models.append(_normalized_columns(ledger))
        if column_models:
            authority = column_models[0]
            for current in column_models[1:]:
                if len(current) != len(authority) or any(
                    abs(left - right)
                    > self.config.continuation_boundary_tolerance_ratio
                    for left_pair, right_pair in zip(authority, current)
                    for left, right in zip(left_pair, right_pair)
                ):
                    errors.append("pdf_hybrid_continuation_column_boundaries_incompatible")
                    break
        if total_candidates != total_used:
            errors.append("pdf_hybrid_continuation_fragment_coverage_incomplete")
        if len(word_refs) != len(set(word_refs)):
            errors.append("pdf_hybrid_continuation_cross_fragment_word_duplicate")
        errors = sorted(set(errors))
        result = {
            "schema_version": PDF_HYBRID_CONTINUATION_VALIDATION_SCHEMA,
            "policy_version": self.config.policy_version,
            "continuation_group_id": group_id,
            "passed": not errors,
            "reason_codes": errors,
            "shared_column_count": contract.get("shared_column_count"),
            "fragment_count": len(fragments),
            "ordered_table_refs": [item.get("table_ref") for item in fragments],
            "subtotal_policy": contract.get("subtotal_policy"),
            "duplicate_row_policy": contract.get("duplicate_row_policy"),
            "fragment_coverage": {
                "candidates_expected": total_candidates,
                "candidates_used": total_used,
                "word_refs": len(word_refs),
                "word_refs_unique": len(set(word_refs)),
            },
            "joined_coverage": {
                "source_rows": total_rows,
                "repeated_header_rows_removed": repeated_header_rows,
                "logical_rows": total_rows - repeated_header_rows,
                "columns": contract.get("shared_column_count"),
            },
            "authoritative": False,
        }
        result["validation_checksum"] = sha256_json(result)
        return result


def _merged_header_errors(
    *,
    dictionary: dict[str, Any],
    materialization: dict[str, Any],
    column_model: list[dict[str, Any]],
    header_depth: int,
    tolerance: float,
) -> list[str]:
    errors = []
    spans = _dicts(materialization.get("spans"))
    for span in spans:
        if (
            span.get("relation") not in {"merged", "spanning_header"}
            or int(span.get("start_row") or 0) < 1
            or int(span.get("end_row") or 0) < int(span.get("start_row") or 0)
            or int(span.get("start_column") or 0) < 1
            or int(span.get("end_column") or 0) < int(span.get("start_column") or 0)
        ):
            errors.append("pdf_hybrid_structure_merged_header_span_invalid")
    for candidate in dictionary.values():
        if not isinstance(candidate, dict) or int(candidate.get("expected_row_ordinal") or 0) > header_depth:
            continue
        bbox = _bbox(candidate.get("source_bbox"))
        if bbox is None:
            continue
        overlapped = [
            int(item.get("ordinal") or 0)
            for item in column_model
            if min(bbox[2], float(item.get("end") or 0))
            - max(bbox[0], float(item.get("start") or 0))
            > tolerance
        ]
        if len(overlapped) > 1:
            row = int(candidate.get("expected_row_ordinal") or 0)
            if not any(
                int(span.get("start_row") or 0) <= row <= int(span.get("end_row") or 0)
                and int(span.get("start_column") or 0) <= min(overlapped)
                and int(span.get("end_column") or 0) >= max(overlapped)
                for span in spans
            ):
                errors.append("pdf_hybrid_structure_merged_header_relation_missing")
                break
    return errors


def _normalized_columns(ledger: dict[str, Any]) -> list[tuple[float, float]]:
    table_bbox = _bbox(ledger.get("table_bbox"))
    if table_bbox is None:
        return []
    width = table_bbox[2] - table_bbox[0]
    return [
        (
            round((float(item.get("start") or 0) - table_bbox[0]) / width, 4),
            round((float(item.get("end") or 0) - table_bbox[0]) / width, 4),
        )
        for item in _dicts(ledger.get("column_model"))
    ]


def _axis_errors(values: list[dict[str, Any]], expected: int) -> list[str]:
    errors = []
    if len(values) != expected or [int(item.get("ordinal") or 0) for item in values] != list(
        range(1, expected + 1)
    ):
        return ["pdf_hybrid_structure_boundary_coverage_invalid"]
    previous_start = None
    for item in values:
        start = float(item.get("start") or 0)
        end = float(item.get("end") or 0)
        if end <= start or (previous_start is not None and start < previous_start):
            errors.append("pdf_hybrid_structure_boundary_order_invalid")
            break
        previous_start = start
    return errors


def _axis_entry(values: list[dict[str, Any]], ordinal: int) -> dict[str, Any] | None:
    return next((item for item in values if int(item.get("ordinal") or 0) == ordinal), None)


def _center_inside(value: list[float], scope: list[float], tolerance: float) -> bool:
    x = (value[0] + value[2]) / 2
    y = (value[1] + value[3]) / 2
    return (
        scope[0] - tolerance <= x <= scope[2] + tolerance
        and scope[1] - tolerance <= y <= scope[3] + tolerance
    )


def _gate(errors: list[str]) -> dict[str, Any]:
    codes = sorted(set(errors))
    return {"passed": not codes, "reason_codes": codes}


def _bbox(value: Any) -> list[float] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    result = [float(item) for item in value]
    if result[2] <= result[0] or result[3] <= result[1]:
        return None
    return result


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []
