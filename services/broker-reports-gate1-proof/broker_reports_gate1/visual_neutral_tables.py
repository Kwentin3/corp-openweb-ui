from __future__ import annotations

import base64
import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest


VISUAL_OBSERVATION_SCHEMA_VERSION = (
    "broker_reports_gate1_visual_ocr_geometry_observation_v1"
)
VISUAL_NEUTRAL_TABLE_SCHEMA_VERSION = (
    "broker_reports_gate1_visual_neutral_table_v1"
)
VISUAL_VALIDATION_SCHEMA_VERSION = (
    "broker_reports_gate1_visual_neutral_table_validation_v1"
)
VISUAL_SAFE_REPORT_SCHEMA_VERSION = (
    "broker_reports_gate1_visual_neutral_table_safe_report_v1"
)
VISUAL_OPERATOR_REVIEW_SCHEMA_VERSION = (
    "broker_reports_gate1_visual_operator_review_v1"
)
VISUAL_RECOVERY_POLICY_VERSION = "broker_reports_visual_recovery_policy_v1"
VISUAL_VALIDATOR_VERSION = "broker_reports_visual_neutral_table_validator_v1"

PROMOTION_STATES = {
    "canonical_table_accepted_deterministic",
    "canonical_table_accepted_reviewed_visual",
    "unresolved_visual_requires_review",
    "unsupported_visual_layout",
}
PROPOSAL_SOURCES = {"local_ocr_geometry", "bounded_vl_proposal"}
ROW_ROLES = {"header", "body", "subtotal", "total"}
OBSERVATION_TERMINAL_STATUSES = {"completed", "unresolved", "unsupported"}

FACTORY_REQUIRED = (
    "Gate1VisualNeutralTableFactory.create is the only canonical visual-neutral "
    "table promotion entrypoint"
)
FORBIDDEN = (
    "Callers must not promote OCR or model output by authority, omit OCR-line "
    "accounting, recover an undeclared page/region, or assign financial meaning"
)


class VisualNeutralTableError(RuntimeError):
    def __init__(self, code: str, subject: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.subject = subject


@dataclass(frozen=True)
class VisualNeutralTableConfig:
    maximum_tables_per_scope: int = 32
    maximum_rows_per_table: int = 200
    maximum_columns_per_table: int = 200
    maximum_cells_per_scope: int = 40_000
    maximum_ocr_lines_per_scope: int = 20_000
    geometry_tolerance_pixels: int = 12
    low_confidence_threshold: float = 0.85
    blank_nonwhite_pixel_ceiling: int = 0


@dataclass(frozen=True)
class VisualProviderPolicy:
    provider_enabled: bool = False
    customer_data_transfer_approved: bool = False
    bounded_transfer_only: bool = True


class Gate1VisualNeutralTableFactory:
    def __init__(
        self,
        config: VisualNeutralTableConfig | None = None,
        provider_policy: VisualProviderPolicy | None = None,
    ) -> None:
        self.config = config or VisualNeutralTableConfig()
        self.provider_policy = provider_policy or VisualProviderPolicy()

    def create(self) -> "Gate1VisualNeutralTableService":
        numeric = (
            self.config.maximum_tables_per_scope,
            self.config.maximum_rows_per_table,
            self.config.maximum_columns_per_table,
            self.config.maximum_cells_per_scope,
            self.config.maximum_ocr_lines_per_scope,
            self.config.geometry_tolerance_pixels,
        )
        if any(value <= 0 for value in numeric):
            raise ValueError("visual_neutral_table_budget_invalid")
        if not 0.0 <= self.config.low_confidence_threshold <= 1.0:
            raise ValueError("visual_neutral_table_confidence_policy_invalid")
        return Gate1VisualNeutralTableService(
            config=self.config,
            provider_policy=self.provider_policy,
        )


class Gate1VisualNeutralTableService:
    def __init__(
        self,
        *,
        config: VisualNeutralTableConfig,
        provider_policy: VisualProviderPolicy,
    ) -> None:
        self.config = config
        self.provider_policy = provider_policy

    def recover(
        self,
        *,
        source_unit: dict[str, Any],
        observation: dict[str, Any],
        operator_review: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        errors = validate_visual_ocr_observation(
            observation,
            source_unit=source_unit,
            config=self.config,
        )
        if errors:
            raise VisualNeutralTableError(
                errors[0]["code"], errors[0].get("subject") or ""
            )

        terminal_status = str(observation.get("terminal_status") or "")
        proposal_source = str(observation.get("proposal_source") or "")
        provider_blocked = proposal_source == "bounded_vl_proposal" and not (
            self.provider_policy.provider_enabled
            and self.provider_policy.customer_data_transfer_approved
            and self.provider_policy.bounded_transfer_only
        )
        if provider_blocked:
            return _terminal_result(
                source_unit=source_unit,
                observation=observation,
                promotion_state="unresolved_visual_requires_review",
                canonical_tables=[],
                reason_codes=["visual_provider_disabled_or_transfer_not_approved"],
                operator_review_status="not_performed",
            )
        if terminal_status in {"unresolved", "unsupported"}:
            state = (
                "unsupported_visual_layout"
                if terminal_status == "unsupported"
                else "unresolved_visual_requires_review"
            )
            return _terminal_result(
                source_unit=source_unit,
                observation=observation,
                promotion_state=state,
                canonical_tables=[],
                reason_codes=_string_list(observation.get("reason_codes")),
                operator_review_status="not_performed",
            )

        canonical_tables = [
            _canonical_table(item, observation=observation)
            for item in _dict_list(observation.get("tables"))
        ]
        uncertainty = _dict_list(observation.get("uncertainty_ledger"))
        unresolved_uncertainty = [
            item
            for item in uncertainty
            if item.get("resolution") not in {"not_applicable", "operator_resolved"}
        ]
        all_confirmed = observation.get("ocr_consensus_status") == "exact"
        low_confidence = [
            item
            for item in _dict_list(observation.get("ocr_lines"))
            if float(item.get("confidence") or 0.0)
            < self.config.low_confidence_threshold
        ]
        if all_confirmed and not low_confidence and not unresolved_uncertainty:
            state = "canonical_table_accepted_deterministic"
            review_status = "not_required"
        else:
            review_errors = validate_visual_operator_review(
                operator_review,
                observation=observation,
                canonical_tables=canonical_tables,
            )
            if review_errors:
                return _terminal_result(
                    source_unit=source_unit,
                    observation=observation,
                    promotion_state="unresolved_visual_requires_review",
                    canonical_tables=[],
                    reason_codes=[item["code"] for item in review_errors],
                    operator_review_status="missing_or_invalid",
                )
            state = "canonical_table_accepted_reviewed_visual"
            review_status = "accepted"

        result = _terminal_result(
            source_unit=source_unit,
            observation=observation,
            promotion_state=state,
            canonical_tables=canonical_tables,
            reason_codes=[],
            operator_review_status=review_status,
        )
        result_errors = validate_visual_neutral_table_result(result)
        if result_errors:
            raise VisualNeutralTableError(
                result_errors[0]["code"], result_errors[0].get("subject") or ""
            )
        return result


def seal_visual_ocr_observation(observation: dict[str, Any]) -> dict[str, Any]:
    sealed = copy.deepcopy(observation)
    sealed.pop("integrity_ref", None)
    sealed["integrity_ref"] = _checksum_ref("visualobschk", sealed)
    return sealed


def build_visual_operator_review(
    *,
    observation: dict[str, Any],
    canonical_tables: list[dict[str, Any]] | None = None,
    resolved_uncertainty_refs: list[str],
    reviewer_role: str = "technical_operator",
) -> dict[str, Any]:
    proposal_tables = canonical_tables or [
        _canonical_table(item, observation=observation)
        for item in _dict_list(observation.get("tables"))
    ]
    review = {
        "schema_version": VISUAL_OPERATOR_REVIEW_SCHEMA_VERSION,
        "status": "accepted",
        "reviewer_role": reviewer_role,
        "observation_integrity_ref": observation.get("integrity_ref"),
        "table_checksum_refs": sorted(
            str(item.get("table_checksum_ref") or "")
            for item in proposal_tables
        ),
        "resolved_uncertainty_refs": sorted(set(resolved_uncertainty_refs)),
        "source_to_table_mapping_checked": True,
        "financial_meaning_assigned": False,
        "model_canonical_authority_used": False,
    }
    review["integrity_ref"] = _checksum_ref("visualreviewchk", review)
    return review


def validate_visual_ocr_observation(
    observation: dict[str, Any],
    *,
    source_unit: dict[str, Any],
    config: VisualNeutralTableConfig | None = None,
) -> list[dict[str, str]]:
    config = config or VisualNeutralTableConfig()
    errors: list[dict[str, str]] = []
    unit_ref = str(source_unit.get("unit_ref") or source_unit.get("unit_id") or "")
    document_ref = str(source_unit.get("document_id") or "")
    page_number = int(source_unit.get("page_number") or 0)
    if source_unit.get("pdf_unit_type") != "pdf_visual_page_unit":
        errors.append(_error("visual_source_unit_type_invalid", unit_ref))
    expected_scope = {
        "source_unit_ref": unit_ref,
        "document_ref": document_ref,
        "page_number": page_number,
        "image_sha256": source_unit.get("private_media_sha256"),
        "access_scope_ref": source_unit.get("access_scope_ref"),
    }
    if not str(source_unit.get("access_scope_ref") or ""):
        errors.append(_error("visual_source_access_scope_missing", unit_ref))
    if observation.get("schema_version") != VISUAL_OBSERVATION_SCHEMA_VERSION:
        errors.append(_error("visual_observation_schema_invalid", unit_ref))
    for field, expected in expected_scope.items():
        if observation.get(field) != expected:
            errors.append(_error("visual_observation_scope_mismatch", field))
    if observation.get("proposal_source") not in PROPOSAL_SOURCES:
        errors.append(_error("visual_observation_proposal_source_invalid", unit_ref))
    proposal_evidence = _object(observation.get("proposal_evidence"))
    if proposal_evidence != {
        "declared_region_only": True,
        "whole_document_provided_to_model": False,
        "model_canonical_authority": False,
        "financial_interpretation_performed": False,
    }:
        errors.append(_error("visual_proposal_authority_contract_invalid", unit_ref))
    terminal = observation.get("terminal_status")
    if terminal not in OBSERVATION_TERMINAL_STATUSES:
        errors.append(_error("visual_observation_terminal_status_invalid", unit_ref))
    raw_media = _decode_media(source_unit.get("private_media_base64"))
    if (
        raw_media is None
        or hashlib.sha256(raw_media).hexdigest()
        != source_unit.get("private_media_sha256")
    ):
        errors.append(_error("visual_source_image_checksum_drift", unit_ref))
    width = int(observation.get("oriented_width_pixels") or 0)
    height = int(observation.get("oriented_height_pixels") or 0)
    region = _int_list(observation.get("declared_region_bbox"))
    if width <= 0 or height <= 0 or not _bbox_valid(region, width=width, height=height):
        errors.append(_error("visual_observation_region_invalid", unit_ref))
    orientation = observation.get("orientation_degrees")
    if orientation not in {0, 90, 180, 270}:
        errors.append(_error("visual_observation_orientation_invalid", unit_ref))
    image_statistics = _object(observation.get("image_statistics"))
    nonwhite_pixels = image_statistics.get("nonwhite_pixel_count")
    pixel_stddev = image_statistics.get("pixel_stddev")
    if (
        not isinstance(nonwhite_pixels, int)
        or isinstance(nonwhite_pixels, bool)
        or nonwhite_pixels < 0
        or not isinstance(pixel_stddev, (int, float))
        or isinstance(pixel_stddev, bool)
        or float(pixel_stddev) < 0
    ):
        errors.append(_error("visual_image_statistics_invalid", unit_ref))
    if not all(
        str(observation.get(field) or "")
        for field in (
            "renderer_version",
            "preprocessing_version",
            "ocr_engine_id",
            "ocr_engine_version",
            "ocr_model_set_ref",
            "validator_version",
            "recovery_policy_version",
        )
    ):
        errors.append(_error("visual_observation_job_identity_incomplete", unit_ref))
    if observation.get("validator_version") != VISUAL_VALIDATOR_VERSION:
        errors.append(_error("visual_observation_validator_version_invalid", unit_ref))
    if observation.get("recovery_policy_version") != VISUAL_RECOVERY_POLICY_VERSION:
        errors.append(_error("visual_observation_policy_version_invalid", unit_ref))
    provider = _object(observation.get("provider_accounting"))
    if observation.get("proposal_source") == "local_ocr_geometry" and provider != {
        "calls": 0,
        "retries": 0,
        "tokens": 0,
        "cost": 0,
        "whole_document_uploads": 0,
    }:
        errors.append(_error("visual_local_ocr_provider_accounting_invalid", unit_ref))
    if provider.get("whole_document_uploads") not in {0, None}:
        errors.append(_error("visual_whole_document_provider_upload_forbidden", unit_ref))

    lines = _dict_list(observation.get("ocr_lines"))
    if len(lines) > config.maximum_ocr_lines_per_scope:
        errors.append(_error("visual_ocr_line_budget_exceeded", unit_ref))
    line_by_ref: dict[str, dict[str, Any]] = {}
    for line in lines:
        line_ref = str(line.get("line_ref") or "")
        if not line_ref or line_ref in line_by_ref:
            errors.append(_error("visual_ocr_line_identity_invalid", unit_ref))
            continue
        line_by_ref[line_ref] = line
        text = str(line.get("text") or "")
        bbox = _int_list(line.get("bbox"))
        confidence = line.get("confidence")
        if not text or not _bbox_valid(bbox, width=width, height=height):
            errors.append(_error("visual_ocr_line_payload_invalid", line_ref))
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= float(confidence) <= 1:
            errors.append(_error("visual_ocr_line_confidence_invalid", line_ref))
        if line.get("text_checksum_ref") != _checksum_ref("visualtextchk", text):
            errors.append(_error("visual_ocr_line_checksum_invalid", line_ref))
    uncertainties = _dict_list(observation.get("uncertainty_ledger"))
    uncertainty_refs = [str(item.get("uncertainty_ref") or "") for item in uncertainties]
    if "" in uncertainty_refs or len(uncertainty_refs) != len(set(uncertainty_refs)):
        errors.append(_error("visual_uncertainty_identity_invalid", unit_ref))
    uncertainty_by_scope = {
        str(item.get("scope_ref") or ""): item for item in uncertainties
    }
    consensus = observation.get("ocr_consensus_status")
    if consensus not in {"exact", "differences_resolved_by_review", "not_available"}:
        errors.append(_error("visual_ocr_consensus_status_invalid", unit_ref))
    for line_ref, line in line_by_ref.items():
        confirmation = line.get("confirmation_text_checksum_ref")
        if consensus == "exact" and confirmation != line.get("text_checksum_ref"):
            errors.append(_error("visual_ocr_repeatability_mismatch", line_ref))
        if (
            float(line.get("confidence") or 0.0) < config.low_confidence_threshold
            or confirmation != line.get("text_checksum_ref")
        ):
            uncertainty = _object(uncertainty_by_scope.get(line_ref))
            if uncertainty.get("resolution") != "operator_resolved":
                errors.append(_error("visual_ocr_uncertainty_unresolved", line_ref))

    tables = _dict_list(observation.get("tables"))
    if terminal == "completed" and not tables:
        errors.append(_error("visual_completed_observation_has_no_tables", unit_ref))
    if terminal != "completed" and tables:
        errors.append(_error("visual_nonterminal_tables_forbidden", unit_ref))
    if "visual_source_image_blank_or_uniform" in _string_list(
        observation.get("reason_codes")
    ) and (
        not isinstance(nonwhite_pixels, int)
        or nonwhite_pixels > config.blank_nonwhite_pixel_ceiling
        or not isinstance(pixel_stddev, (int, float))
        or isinstance(pixel_stddev, bool)
        or float(pixel_stddev) != 0.0
    ):
        errors.append(_error("visual_blank_reason_evidence_invalid", unit_ref))
    if len(tables) > config.maximum_tables_per_scope:
        errors.append(_error("visual_table_budget_exceeded", unit_ref))
    used_line_refs: list[str] = []
    cells_total = 0
    table_refs: set[str] = set()
    for table in tables:
        table_ref = str(table.get("table_ref") or "")
        if not table_ref or table_ref in table_refs:
            errors.append(_error("visual_table_identity_invalid", unit_ref))
            continue
        table_refs.add(table_ref)
        table_errors, table_used = _validate_observed_table(
            table,
            line_by_ref=line_by_ref,
            region=region,
            config=config,
        )
        errors.extend(table_errors)
        used_line_refs.extend(table_used)
        cells_total += len(_dict_list(table.get("cells")))
    if cells_total > config.maximum_cells_per_scope:
        errors.append(_error("visual_cell_budget_exceeded", unit_ref))
    if len(used_line_refs) != len(set(used_line_refs)):
        errors.append(_error("visual_ocr_line_assigned_multiple_times", unit_ref))
    outside_refs = _string_list(observation.get("outside_table_line_refs"))
    if len(outside_refs) != len(set(outside_refs)):
        errors.append(_error("visual_outside_line_accounting_duplicate", unit_ref))
    if set(used_line_refs) & set(outside_refs):
        errors.append(_error("visual_ocr_line_accounting_overlap", unit_ref))
    if set(used_line_refs) | set(outside_refs) != set(line_by_ref):
        errors.append(_error("visual_ocr_line_accounting_incomplete", unit_ref))
    _validate_continuation(observation, errors=errors)
    expected_integrity = _checksum_ref(
        "visualobschk",
        {key: value for key, value in observation.items() if key != "integrity_ref"},
    )
    if observation.get("integrity_ref") != expected_integrity:
        errors.append(_error("visual_observation_integrity_mismatch", unit_ref))
    return errors


def _validate_observed_table(
    table: dict[str, Any],
    *,
    line_by_ref: dict[str, dict[str, Any]],
    region: list[int],
    config: VisualNeutralTableConfig,
) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[dict[str, str]] = []
    used_lines: list[str] = []
    table_ref = str(table.get("table_ref") or "")
    bbox = _int_list(table.get("bbox"))
    if not _bbox_within(bbox, region):
        errors.append(_error("visual_table_region_out_of_scope", table_ref))
        return errors, used_lines
    rows = table.get("row_count")
    columns = table.get("column_count")
    if not _bounded_int(rows, 1, config.maximum_rows_per_table):
        errors.append(_error("visual_table_row_count_invalid", table_ref))
        return errors, used_lines
    if not _bounded_int(columns, 1, config.maximum_columns_per_table):
        errors.append(_error("visual_table_column_count_invalid", table_ref))
        return errors, used_lines
    row_boundaries = _int_list(table.get("row_boundaries"))
    column_boundaries = _int_list(table.get("column_boundaries"))
    row_boundaries_valid = _boundaries_valid(
        row_boundaries, rows + 1, bbox[1], bbox[3]
    )
    column_boundaries_valid = _boundaries_valid(
        column_boundaries, columns + 1, bbox[0], bbox[2]
    )
    if not row_boundaries_valid:
        errors.append(_error("visual_table_row_boundaries_invalid", table_ref))
    if not column_boundaries_valid:
        errors.append(_error("visual_table_column_boundaries_invalid", table_ref))
    if not row_boundaries_valid or not column_boundaries_valid:
        return errors, used_lines
    cells = _dict_list(table.get("cells"))
    coverage: dict[tuple[int, int], int] = {}
    anchors: set[tuple[int, int]] = set()
    row_text: dict[int, list[str]] = {index: [] for index in range(rows)}
    for cell in cells:
        row = cell.get("row_index")
        column = cell.get("column_index")
        row_span = cell.get("row_span")
        column_span = cell.get("column_span")
        anchor = (row, column)
        if (
            not _bounded_int(row, 0, rows - 1)
            or not _bounded_int(column, 0, columns - 1)
            or not _bounded_int(row_span, 1, rows)
            or not _bounded_int(column_span, 1, columns)
            or row + row_span > rows
            or column + column_span > columns
        ):
            errors.append(_error("visual_cell_span_invalid", table_ref))
            continue
        if anchor in anchors:
            errors.append(_error("visual_cell_anchor_duplicate", table_ref))
            continue
        anchors.add(anchor)
        for row_index in range(row, row + row_span):
            for column_index in range(column, column + column_span):
                slot = (row_index, column_index)
                coverage[slot] = coverage.get(slot, 0) + 1
        expected_bbox = [
            column_boundaries[column],
            row_boundaries[row],
            column_boundaries[column + column_span],
            row_boundaries[row + row_span],
        ]
        if not _bbox_close(
            _int_list(cell.get("bbox")),
            expected_bbox,
            tolerance=config.geometry_tolerance_pixels,
        ):
            errors.append(_error("visual_cell_geometry_mismatch", table_ref))
        refs = _string_list(cell.get("ocr_line_refs"))
        if len(refs) != len(set(refs)) or not set(refs) <= set(line_by_ref):
            errors.append(_error("visual_cell_ocr_refs_invalid", table_ref))
            continue
        if any(
            not _bbox_center_within(
                _int_list(line_by_ref[ref].get("bbox")), expected_bbox
            )
            for ref in refs
        ):
            errors.append(_error("visual_cell_ocr_geometry_mismatch", table_ref))
        used_lines.extend(refs)
        expected_text = _canonical_text(
            " ".join(str(line_by_ref[ref].get("text") or "") for ref in refs)
        )
        source_text = _canonical_text(str(cell.get("source_text") or ""))
        state = cell.get("content_state")
        if state == "present" and (not refs or source_text != expected_text):
            errors.append(_error("visual_cell_source_text_unreproducible", table_ref))
        elif state == "empty" and (refs or source_text):
            errors.append(_error("visual_cell_empty_state_invalid", table_ref))
        elif state == "unreadable":
            if refs or source_text:
                errors.append(_error("visual_cell_unreadable_state_invalid", table_ref))
        elif state not in {"present", "empty", "unreadable"}:
            errors.append(_error("visual_cell_content_state_invalid", table_ref))
        if source_text:
            row_text[row].append(source_text)
    if len(coverage) != rows * columns or any(value != 1 for value in coverage.values()):
        errors.append(_error("visual_table_grid_coverage_invalid", table_ref))
    header_rows = _int_list(table.get("header_rows"))
    if header_rows != list(range(len(header_rows))) or any(item >= rows for item in header_rows):
        errors.append(_error("visual_table_header_rows_invalid", table_ref))
    roles = _string_list(table.get("row_roles"))
    if len(roles) != rows or any(role not in ROW_ROLES for role in roles):
        errors.append(_error("visual_table_row_roles_invalid", table_ref))
    else:
        for row in range(rows):
            if (row in header_rows) != (roles[row] == "header"):
                errors.append(_error("visual_table_header_role_mismatch", table_ref))
            has_total_label = _has_total_label(" ".join(row_text[row]))
            if has_total_label and roles[row] not in {"total", "subtotal"}:
                errors.append(_error("visual_table_total_role_missing", table_ref))
            if roles[row] in {"total", "subtotal"} and not has_total_label:
                errors.append(_error("visual_table_total_role_unsupported", table_ref))
    hierarchy = _dict_list(table.get("header_hierarchy"))
    cell_by_anchor = {
        (cell.get("row_index"), cell.get("column_index")): cell
        for cell in cells
        if isinstance(cell.get("row_index"), int)
        and isinstance(cell.get("column_index"), int)
    }
    header_anchors = {
        (cell["row_index"], cell["column_index"])
        for cell in cells
        if isinstance(cell.get("row_index"), int)
        and not isinstance(cell.get("row_index"), bool)
        and isinstance(cell.get("column_index"), int)
        and not isinstance(cell.get("column_index"), bool)
        and cell.get("row_index") in header_rows
    }
    hierarchy_anchors = {
        tuple(_int_list(item.get("anchor"))) for item in hierarchy
    }
    if hierarchy_anchors != header_anchors:
        errors.append(_error("visual_table_header_hierarchy_incomplete", table_ref))
    for item in hierarchy:
        anchor = tuple(_int_list(item.get("anchor")))
        parent = tuple(_int_list(item.get("parent_anchor")))
        level = item.get("level")
        if len(anchor) != 2 or not isinstance(level, int) or level < 0:
            errors.append(_error("visual_table_header_hierarchy_invalid", table_ref))
        if parent and (len(parent) != 2 or parent not in header_anchors):
            errors.append(_error("visual_table_header_parent_invalid", table_ref))
        source_text = str(_object(cell_by_anchor.get(anchor)).get("source_text") or "")
        if item.get("source_text_checksum_ref") != _checksum_ref(
            "visualtextchk", source_text
        ):
            errors.append(_error("visual_table_header_text_mismatch", table_ref))
        if parent:
            parent_item = next(
                (
                    candidate
                    for candidate in hierarchy
                    if tuple(_int_list(candidate.get("anchor"))) == parent
                ),
                {},
            )
            if (
                not isinstance(level, int)
                or not isinstance(parent_item.get("level"), int)
                or parent_item.get("level") >= level
            ):
                errors.append(_error("visual_table_header_level_invalid", table_ref))
    expected_spans = sorted(
        [cell.get("row_index"), cell.get("column_index")]
        for cell in cells
        if (
            isinstance(cell.get("row_span"), int)
            and cell.get("row_span") > 1
        )
        or (
            isinstance(cell.get("column_span"), int)
            and cell.get("column_span") > 1
        )
    )
    merge_evidence = _object(table.get("merge_evidence"))
    if (
        merge_evidence.get("spanning_cell_anchors") != expected_spans
        or merge_evidence.get("ambiguity_status")
        != ("confirmed" if expected_spans else "not_present")
    ):
        errors.append(_error("visual_table_merge_evidence_invalid", table_ref))
    geometry = _object(table.get("geometry_evidence"))
    cell_boxes = [_int_list(cell.get("bbox")) for cell in cells]
    if (
        geometry.get("expected_row_count") != rows
        or geometry.get("expected_column_count") != columns
        or geometry.get("raw_cell_boxes_total") != len(cells)
        or geometry.get("independent_grid_consistency") != "passed"
        or geometry.get("raw_cell_boxes_checksum_ref")
        != _checksum_ref("visualcellboxchk", cell_boxes)
        or geometry.get("row_boundaries_checksum_ref")
        != _checksum_ref("visualrowgridchk", row_boundaries)
        or geometry.get("column_boundaries_checksum_ref")
        != _checksum_ref("visualcolgridchk", column_boundaries)
    ):
        errors.append(_error("visual_table_geometry_evidence_invalid", table_ref))
    return errors, used_lines


def validate_visual_operator_review(
    review: dict[str, Any] | None,
    *,
    observation: dict[str, Any],
    canonical_tables: list[dict[str, Any]],
) -> list[dict[str, str]]:
    review = _object(review)
    errors: list[dict[str, str]] = []
    if review.get("schema_version") != VISUAL_OPERATOR_REVIEW_SCHEMA_VERSION:
        errors.append(_error("visual_operator_review_schema_invalid", "review"))
        return errors
    expected = {
        "status": "accepted",
        "reviewer_role": "technical_operator",
        "observation_integrity_ref": observation.get("integrity_ref"),
        "table_checksum_refs": sorted(
            str(item.get("table_checksum_ref") or "")
            for item in canonical_tables
        ),
        "resolved_uncertainty_refs": sorted(
            str(item.get("uncertainty_ref") or "")
            for item in _dict_list(observation.get("uncertainty_ledger"))
            if item.get("resolution") == "operator_resolved"
        ),
        "source_to_table_mapping_checked": True,
        "financial_meaning_assigned": False,
        "model_canonical_authority_used": False,
    }
    for field, value in expected.items():
        if review.get(field) != value:
            errors.append(_error("visual_operator_review_scope_mismatch", field))
    expected_integrity = _checksum_ref(
        "visualreviewchk",
        {key: value for key, value in review.items() if key != "integrity_ref"},
    )
    if review.get("integrity_ref") != expected_integrity:
        errors.append(_error("visual_operator_review_integrity_mismatch", "review"))
    return errors


def _canonical_table(
    table: dict[str, Any], *, observation: dict[str, Any]
) -> dict[str, Any]:
    canonical = {
        "table_id": f"visualtable_{stable_digest([observation.get('integrity_ref'), table.get('table_ref')], length=24)}",
        "source_table_ref": table.get("table_ref"),
        "bbox": copy.deepcopy(table.get("bbox")),
        "row_count": table.get("row_count"),
        "column_count": table.get("column_count"),
        "row_boundaries": copy.deepcopy(table.get("row_boundaries")),
        "column_boundaries": copy.deepcopy(table.get("column_boundaries")),
        "cells": copy.deepcopy(table.get("cells")),
        "header_rows": copy.deepcopy(table.get("header_rows")),
        "header_hierarchy": copy.deepcopy(table.get("header_hierarchy")),
        "row_roles": copy.deepcopy(table.get("row_roles")),
        "merge_evidence": copy.deepcopy(table.get("merge_evidence")),
        "geometry_evidence": copy.deepcopy(table.get("geometry_evidence")),
    }
    canonical["table_checksum_ref"] = _checksum_ref("visualtablechk", canonical)
    return canonical


def _terminal_result(
    *,
    source_unit: dict[str, Any],
    observation: dict[str, Any],
    promotion_state: str,
    canonical_tables: list[dict[str, Any]],
    reason_codes: list[str],
    operator_review_status: str,
) -> dict[str, Any]:
    line_refs = {
        str(ref)
        for table in _dict_list(observation.get("tables"))
        for cell in _dict_list(table.get("cells"))
        for ref in _string_list(cell.get("ocr_line_refs"))
    }
    result = {
        "schema_version": VISUAL_NEUTRAL_TABLE_SCHEMA_VERSION,
        "recovery_id": f"visualrecovery_{stable_digest([observation.get('integrity_ref')], length=24)}",
        "source_document_ref": source_unit.get("document_id"),
        "source_unit_ref": source_unit.get("unit_ref") or source_unit.get("unit_id"),
        "page_number": source_unit.get("page_number"),
        "image_sha256": source_unit.get("private_media_sha256"),
        "declared_region_bbox": copy.deepcopy(
            observation.get("declared_region_bbox")
        ),
        "job_identity": {
            "renderer_version": observation.get("renderer_version"),
            "preprocessing_version": observation.get("preprocessing_version"),
            "ocr_engine_id": observation.get("ocr_engine_id"),
            "ocr_engine_version": observation.get("ocr_engine_version"),
            "ocr_model_set_ref": observation.get("ocr_model_set_ref"),
            "validator_version": observation.get("validator_version"),
            "recovery_policy_version": observation.get("recovery_policy_version"),
        },
        "promotion_state": promotion_state,
        "canonical_tables": copy.deepcopy(canonical_tables),
        "uncertainty_ledger": copy.deepcopy(
            observation.get("uncertainty_ledger") or []
        ),
        "reason_codes": sorted(set(reason_codes)),
        "operator_review_status": operator_review_status,
        "continuation": copy.deepcopy(observation.get("continuation") or {}),
        "source_to_table_accounting": {
            "ocr_lines_total": len(_dict_list(observation.get("ocr_lines"))),
            "ocr_lines_assigned_to_tables": len(line_refs),
            "ocr_lines_outside_tables": len(
                _string_list(observation.get("outside_table_line_refs"))
            ),
            "tables_total": len(canonical_tables),
            "cells_total": sum(
                len(_dict_list(table.get("cells"))) for table in canonical_tables
            ),
            "source_to_table_accounting_passed": promotion_state.startswith(
                "canonical_table_accepted_"
            ),
        },
        "provider_accounting": copy.deepcopy(
            observation.get("provider_accounting") or {}
        ),
        "model_canonical_authority": False,
        "financial_interpretation_allowed": False,
        "visibility": "private_case",
        "knowledge_rag_used": False,
        "vectorization_performed": False,
    }
    result["integrity_ref"] = _checksum_ref("visualrecoverychk", result)
    return result


def validate_visual_neutral_table_result(
    result: dict[str, Any],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    recovery_id = str(result.get("recovery_id") or "")
    if result.get("schema_version") != VISUAL_NEUTRAL_TABLE_SCHEMA_VERSION:
        errors.append(_error("visual_result_schema_invalid", recovery_id))
    if result.get("promotion_state") not in PROMOTION_STATES:
        errors.append(_error("visual_result_promotion_state_invalid", recovery_id))
    accepted = str(result.get("promotion_state") or "").startswith(
        "canonical_table_accepted_"
    )
    tables = _dict_list(result.get("canonical_tables"))
    if accepted != bool(tables):
        errors.append(_error("visual_result_canonical_table_state_mismatch", recovery_id))
    if result.get("model_canonical_authority") is not False:
        errors.append(_error("visual_result_model_authority_forbidden", recovery_id))
    if result.get("financial_interpretation_allowed") is not False:
        errors.append(_error("visual_result_gate_boundary_violated", recovery_id))
    if result.get("knowledge_rag_used") is not False or result.get(
        "vectorization_performed"
    ) is not False:
        errors.append(_error("visual_result_knowledge_write_forbidden", recovery_id))
    for table in tables:
        expected = _checksum_ref(
            "visualtablechk",
            {key: value for key, value in table.items() if key != "table_checksum_ref"},
        )
        if table.get("table_checksum_ref") != expected:
            errors.append(_error("visual_result_table_integrity_mismatch", recovery_id))
    expected_integrity = _checksum_ref(
        "visualrecoverychk",
        {key: value for key, value in result.items() if key != "integrity_ref"},
    )
    if result.get("integrity_ref") != expected_integrity:
        errors.append(_error("visual_result_integrity_mismatch", recovery_id))
    return errors


def validate_visual_continuation_chain(
    results: list[dict[str, Any]],
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    groups: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        continuation = _object(result.get("continuation"))
        if continuation.get("relationship") != "declared_page_sequence":
            continue
        group_ref = str(continuation.get("group_ref") or "")
        groups.setdefault(group_ref, []).append(result)
    for group_ref, members in groups.items():
        documents = {str(item.get("source_document_ref") or "") for item in members}
        pages = sorted(int(item.get("page_number") or 0) for item in members)
        if not group_ref or len(documents) != 1 or pages != list(
            range(pages[0], pages[-1] + 1)
        ):
            errors.append(_error("visual_continuation_chain_invalid", group_ref))
            continue
        by_page = {int(item.get("page_number") or 0): item for item in members}
        for page, result in by_page.items():
            continuation = _object(result.get("continuation"))
            expected_previous = page - 1 if page != pages[0] else None
            expected_next = page + 1 if page != pages[-1] else None
            if (
                continuation.get("previous_page_number") != expected_previous
                or continuation.get("next_page_number") != expected_next
            ):
                errors.append(
                    _error("visual_continuation_link_invalid", result.get("recovery_id"))
                )
    return errors


def render_visual_neutral_table_safe_report(
    result: dict[str, Any],
) -> dict[str, Any]:
    validation = validate_visual_neutral_table_result(result)
    tables = _dict_list(result.get("canonical_tables"))
    report = {
        "schema_version": VISUAL_SAFE_REPORT_SCHEMA_VERSION,
        "opaque_recovery_id": _checksum_ref(
            "visualsafeid", result.get("recovery_id")
        ),
        "promotion_state": result.get("promotion_state"),
        "validator_status": "passed" if not validation else "failed",
        "tables_total": len(tables),
        "rows_total": sum(int(item.get("row_count") or 0) for item in tables),
        "columns_total": sum(
            int(item.get("column_count") or 0) for item in tables
        ),
        "cells_total": sum(
            len(_dict_list(item.get("cells"))) for item in tables
        ),
        "uncertainties_total": len(
            _dict_list(result.get("uncertainty_ledger"))
        ),
        "operator_review_status": result.get("operator_review_status"),
        "provider_calls": _object(result.get("provider_accounting")).get("calls"),
        "provider_retries": _object(result.get("provider_accounting")).get(
            "retries"
        ),
        "provider_tokens": _object(result.get("provider_accounting")).get("tokens"),
        "provider_cost": _object(result.get("provider_accounting")).get("cost"),
        "whole_document_provider_uploads": _object(
            result.get("provider_accounting")
        ).get("whole_document_uploads"),
        "model_canonical_authority": False,
        "customer_values_in_report": False,
        "source_identities_in_report": False,
        "source_to_table_accounting_passed": _object(
            result.get("source_to_table_accounting")
        ).get("source_to_table_accounting_passed"),
    }
    report["integrity_ref"] = _checksum_ref("visualsafechk", report)
    return report


def _validate_continuation(
    observation: dict[str, Any], *, errors: list[dict[str, str]]
) -> None:
    continuation = _object(observation.get("continuation"))
    relationship = continuation.get("relationship")
    if relationship == "not_applicable":
        if any(
            continuation.get(field) is not None
            for field in ("group_ref", "previous_page_number", "next_page_number")
        ):
            errors.append(_error("visual_continuation_not_applicable_invalid", "scope"))
        return
    if relationship != "declared_page_sequence" or not continuation.get("group_ref"):
        errors.append(_error("visual_continuation_contract_invalid", "scope"))
        return
    page = int(observation.get("page_number") or 0)
    previous = continuation.get("previous_page_number")
    following = continuation.get("next_page_number")
    if previous is not None and previous != page - 1:
        errors.append(_error("visual_continuation_previous_page_invalid", "scope"))
    if following is not None and following != page + 1:
        errors.append(_error("visual_continuation_next_page_invalid", "scope"))


def _has_total_label(value: str) -> bool:
    normalized = _canonical_text(value).casefold()
    return bool(
        re.search(r"(?:^|\s)(?:итого|всего|subtotal|total)(?:\s|$|:)", normalized)
    )


def _canonical_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(
        normalized.replace("\u00a0", " ").replace("\u202f", " ").split()
    )


def _decode_media(value: Any) -> bytes | None:
    try:
        return base64.b64decode(str(value or ""), validate=True)
    except (ValueError, TypeError):
        return None


def _bbox_valid(value: list[int], *, width: int, height: int) -> bool:
    return (
        len(value) == 4
        and 0 <= value[0] < value[2] <= width
        and 0 <= value[1] < value[3] <= height
    )


def _bbox_within(inner: list[int], outer: list[int]) -> bool:
    return (
        len(inner) == len(outer) == 4
        and outer[0] <= inner[0] < inner[2] <= outer[2]
        and outer[1] <= inner[1] < inner[3] <= outer[3]
    )


def _bbox_close(left: list[int], right: list[int], *, tolerance: int) -> bool:
    return len(left) == len(right) == 4 and all(
        abs(a - b) <= tolerance for a, b in zip(left, right)
    )


def _bbox_center_within(inner: list[int], outer: list[int]) -> bool:
    if len(inner) != 4 or len(outer) != 4:
        return False
    center_x = (inner[0] + inner[2]) / 2
    center_y = (inner[1] + inner[3]) / 2
    return outer[0] <= center_x <= outer[2] and outer[1] <= center_y <= outer[3]


def _boundaries_valid(
    values: list[int], expected_length: int, lower: int, upper: int
) -> bool:
    return (
        len(values) == expected_length
        and values[0] == lower
        and values[-1] == upper
        and all(left < right for left, right in zip(values, values[1:]))
    )


def _bounded_int(value: Any, minimum: int, maximum: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and minimum <= value <= maximum
    )


def _checksum_ref(prefix: str, value: Any) -> str:
    material = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(material).hexdigest()[:24]}"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in value or [] if item is not None and str(item)]


def _int_list(value: Any) -> list[int]:
    return [int(item) for item in value or [] if isinstance(item, int) and not isinstance(item, bool)]


def _error(code: str, subject: object) -> dict[str, str]:
    safe_subject = re.sub(r"[^A-Za-z0-9_.:\-]", "_", str(subject or ""))[:160]
    return {"code": code, "subject": safe_subject}
