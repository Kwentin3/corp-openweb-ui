from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from .contracts import stable_digest


PDF_COMPACT_CANONICAL_SCHEMA_VERSION = (
    "broker_reports_pdf_compact_canonical_document_v1"
)
PDF_COMPACT_CANONICAL_POLICY_VERSION = "pdf_compact_canonical_policy_v1"

FACTORY_REQUIRED = (
    "PdfCompactCanonicalFactory.create is the only production compact-PDF builder entrypoint"
)
FORBIDDEN = (
    "Production callers must not bypass the factory, copy full PDF forensic inventories, "
    "or invent replacement table, cell, source-value, checksum, page, or bbox refs"
)

_GUARDS = {
    "semantic_table_truth_claimed": False,
    "source_facts_extracted": False,
    "tax_meaning_inferred": False,
    "knowledge_rag_used": False,
    "vectorization_performed": False,
    "ocr_vlm_used": False,
    "page_rendering_used_for_extraction": False,
    "provider_pdf_transport_used": False,
}

_TOP_LEVEL_KEYS = {
    "schema_version",
    "policy_version",
    "canonical_document_id",
    "canonical_document_checksum_ref",
    "normalization_run_id",
    "document_ref",
    "original_pdf_artifact_ref",
    "input_pdf_sha256",
    "input_pdf_bytes",
    "parser_manifest",
    "pages",
    "tables",
    "selected_source_evidence",
    "source_value_index",
    "coverage",
    "artifact_roles",
    "acceptance_mode",
    "authority_state",
    "production_ready",
    *_GUARDS,
}

_FORBIDDEN_KEYS = {
    "char_inventory",
    "word_inventory",
    "line_inventory",
    "block_inventory",
    "vector_inventory",
    "image_inventory",
    "parser_fragments",
    "private_values",
    "pdf_text_layer_projection",
    "normalized_projection",
    "raw_provider_output",
    "provider_request",
    "raster_bytes",
    "page_crop",
    "table_crop",
    "business_interpretation",
    "tax_calculation",
}


class PdfCompactCanonicalError(ValueError):
    def __init__(self, code: str, subject: str = "") -> None:
        self.code = code
        self.subject = subject
        super().__init__(code if not subject else f"{code}:{subject}")


@dataclass(frozen=True)
class PdfCompactCanonicalConfig:
    policy_version: str = PDF_COMPACT_CANONICAL_POLICY_VERSION
    coordinate_space: str = "pdfplumber_top_left_points"
    require_complete_candidate_accounting: bool = True
    require_ready_projection_validator: bool = True


class PdfCompactCanonicalFactory:
    def __init__(self, config: PdfCompactCanonicalConfig | None = None) -> None:
        self.config = config or PdfCompactCanonicalConfig()

    def create(self) -> "PdfCompactCanonicalBuilder":
        if self.config.policy_version != PDF_COMPACT_CANONICAL_POLICY_VERSION:
            raise PdfCompactCanonicalError("pdf_compact_policy_version_invalid")
        return PdfCompactCanonicalBuilder(self.config)


class PdfCompactCanonicalBuilder:
    def __init__(self, config: PdfCompactCanonicalConfig) -> None:
        self.config = config

    def build(
        self,
        *,
        normalization_run_id: str,
        document: dict[str, Any],
        original_pdf_artifact_ref: str,
        source_payload: dict[str, Any],
        source_units: list[dict[str, Any]],
        table_projections: list[dict[str, Any]],
        table_decisions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        document_id = str(document.get("document_id") or "")
        if document.get("container_format") != "pdf":
            raise PdfCompactCanonicalError("pdf_compact_document_not_pdf", document_id)
        if not normalization_run_id or not document_id or not original_pdf_artifact_ref:
            raise PdfCompactCanonicalError("pdf_compact_identity_missing", document_id)
        if source_payload.get("document_ref") != document_id:
            raise PdfCompactCanonicalError("pdf_compact_payload_document_mismatch", document_id)

        projection = _object(source_payload.get("pdf_text_layer_projection"))
        candidates = _dicts(projection.get("table_candidate_inventory"))
        pages = _dicts(projection.get("page_inventory"))
        bbox_by_ref = {
            str(item.get("bbox_ref") or ""): item
            for item in _dicts(projection.get("bbox_inventory"))
            if item.get("bbox_ref")
        }
        word_by_ref = {
            str(item.get("word_ref") or ""): item
            for item in _dicts(projection.get("word_inventory"))
            if item.get("word_ref")
        }
        projection_by_table = _unique_index(
            table_projections,
            "table_ref",
            "pdf_compact_duplicate_projection_table_ref",
        )
        unit_by_table = _unique_index(
            [item for item in source_units if item.get("table_candidate_ref")],
            "table_candidate_ref",
            "pdf_compact_duplicate_source_unit_table_ref",
        )
        decision_by_unit = _unique_index(
            table_decisions,
            "source_unit_ref",
            "pdf_compact_duplicate_table_decision",
        )

        compact_tables: list[dict[str, Any]] = []
        evidence_by_ref: dict[str, dict[str, Any]] = {}
        index_by_ref: dict[str, dict[str, Any]] = {}
        for candidate in sorted(
            candidates,
            key=lambda item: (
                _page_number(pages, item.get("page_ref")),
                int(item.get("parser_ordinal") or 0),
                str(item.get("table_candidate_ref") or ""),
            ),
        ):
            table_ref = str(candidate.get("table_candidate_ref") or "")
            if not table_ref:
                raise PdfCompactCanonicalError("pdf_compact_table_ref_missing")
            current = projection_by_table.get(table_ref)
            unit = unit_by_table.get(table_ref)
            if current is None or unit is None:
                raise PdfCompactCanonicalError("pdf_compact_table_projection_missing", table_ref)
            decision = decision_by_unit.get(str(unit.get("unit_ref") or ""))
            if decision is None:
                raise PdfCompactCanonicalError("pdf_compact_table_decision_missing", table_ref)
            compact_table = self._table(
                candidate=candidate,
                projection=current,
                unit=unit,
                decision=decision,
                bbox_by_ref=bbox_by_ref,
                word_by_ref=word_by_ref,
                evidence_by_ref=evidence_by_ref,
                index_by_ref=index_by_ref,
            )
            compact_tables.append(compact_table)

        candidate_refs = [str(item.get("table_candidate_ref") or "") for item in candidates]
        compact_refs = [str(item.get("table_ref") or "") for item in compact_tables]
        duplicates = _duplicates(compact_refs)
        unaccounted = sorted(set(candidate_refs) - set(compact_refs))
        unexpected = sorted(set(compact_refs) - set(candidate_refs))
        if self.config.require_complete_candidate_accounting and (
            duplicates or unaccounted or unexpected
        ):
            raise PdfCompactCanonicalError("pdf_compact_candidate_accounting_failed")

        page_manifest = [self._page(item) for item in sorted(pages, key=lambda x: int(x.get("page_number") or 0))]
        config_hash = _sha256_ref("pdfcompactcfg", asdict(self.config))
        evidence_refs = sorted(evidence_by_ref)
        document_coverage = {
            "candidate_refs": candidate_refs,
            "accounted_table_refs": compact_refs,
            "duplicate_table_refs": duplicates,
            "unaccounted_table_refs": unaccounted,
            "unexpected_table_refs": unexpected,
            "table_candidates_total": len(candidate_refs),
            "tables_accepted_total": sum(
                1 for item in compact_tables if item.get("status") == "accepted"
            ),
            "tables_blocked_total": sum(
                1 for item in compact_tables if item.get("status") == "blocked"
            ),
            "accepted_source_refs_total": len(evidence_refs),
            "duplicate_source_refs": [],
            "unaccounted_source_refs": [],
            "accepted_source_ref_set_checksum": _ref_set_checksum(evidence_refs),
            "coverage_status": (
                "complete" if not duplicates and not unaccounted and not unexpected else "partial"
            ),
        }
        document_coverage["coverage_checksum_ref"] = _sha256_ref(
            "pdfcompactcoveragechk", document_coverage
        )
        result: dict[str, Any] = {
            "schema_version": PDF_COMPACT_CANONICAL_SCHEMA_VERSION,
            "policy_version": self.config.policy_version,
            "canonical_document_id": "pdfcompact_"
            + stable_digest(
                [
                    normalization_run_id,
                    document_id,
                    document.get("sha256"),
                    source_payload.get("payload_checksum_ref"),
                    config_hash,
                ],
                length=24,
            ),
            "canonical_document_checksum_ref": None,
            "normalization_run_id": normalization_run_id,
            "document_ref": document_id,
            "original_pdf_artifact_ref": original_pdf_artifact_ref,
            "input_pdf_sha256": str(document.get("sha256") or ""),
            "input_pdf_bytes": int(document.get("size_bytes") or 0),
            "parser_manifest": {
                "parser": source_payload.get("parser"),
                "parser_ref": source_payload.get("parser_ref"),
                "parser_version": source_payload.get("parser_version"),
                "layout_parser": projection.get("layout_parser_engine"),
                "layout_parser_version": projection.get("layout_parser_engine_version"),
                "layout_underlying_engine_version": projection.get(
                    "layout_underlying_engine_version"
                ),
                "parser_config_ref": projection.get("layout_parser_config_ref"),
                "table_detection_policy_version": "pdf_layout_table_detection_v0",
                "canonicalization_policy_version": self.config.policy_version,
                "compact_config_hash": config_hash,
                "source_payload_ref": source_payload.get("source_payload_ref"),
                "source_payload_checksum_ref": source_payload.get("payload_checksum_ref"),
                "source_checksum_ref": source_payload.get("source_checksum_ref"),
            },
            "pages": page_manifest,
            "tables": compact_tables,
            "selected_source_evidence": {
                "fields": [
                    "source_value_ref",
                    "source_object_ref",
                    "page_ref",
                    "bbox",
                    "text",
                    "text_checksum_ref",
                    "value_checksum_ref",
                ],
                "items": [
                    [
                        evidence_by_ref[key].get("source_value_ref"),
                        evidence_by_ref[key].get("source_object_ref"),
                        evidence_by_ref[key].get("page_ref"),
                        evidence_by_ref[key].get("bbox"),
                        evidence_by_ref[key].get("text"),
                        evidence_by_ref[key].get("text_checksum_ref"),
                        evidence_by_ref[key].get("value_checksum_ref"),
                    ]
                    for key in evidence_refs
                ],
            },
            "source_value_index": {
                "index_kind": "source_value_ref_to_selected_evidence_ordinal",
                "items": {key: ordinal for ordinal, key in enumerate(evidence_refs)},
            },
            "coverage": document_coverage,
            "artifact_roles": {
                "original_pdf": "permanent_source_evidence",
                "compact_canonical": "permanent_canonical_normalization",
                "acceptance_record": "permanent_decision_record",
                "full_forensic_payload": "temporary_parser_working_state_ttl_debug",
                "full_source_units": "temporary_parser_working_state_ttl_debug",
                "table_projections": "permanent_during_dual_write_migration",
                "cleanup_enabled": False,
                "current_artifacts_deleted": False,
            },
            "acceptance_mode": "shadow_dual_write",
            "authority_state": "non_authoritative",
            "production_ready": False,
            **_GUARDS,
        }
        result["canonical_document_checksum_ref"] = _compact_checksum(result)
        validation = PdfCompactCanonicalValidator().validate(result)
        if not validation["passed"]:
            raise PdfCompactCanonicalError(
                "pdf_compact_validation_failed",
                ",".join(item["code"] for item in validation["errors"][:5]),
            )
        return result

    def _page(self, page: dict[str, Any]) -> dict[str, Any]:
        return {
            "page_ref": page.get("page_ref"),
            "page_number": int(page.get("page_number") or 0),
            "page_text_checksum_ref": page.get("page_text_checksum_ref"),
            "page_layout_checksum_ref": page.get("page_layout_checksum_ref"),
            "page_projection_status": page.get("page_projection_status"),
            "layout_projection_status": page.get("layout_projection_status"),
            "visible_content_coverage_status": page.get("visible_content_coverage_status"),
            "width": page.get("layout_page_width"),
            "height": page.get("layout_page_height"),
            "rotation": page.get("layout_page_rotation"),
            "coordinate_space": self.config.coordinate_space,
            "table_candidate_refs": list(page.get("table_candidate_refs") or []),
        }

    def _table(
        self,
        *,
        candidate: dict[str, Any],
        projection: dict[str, Any],
        unit: dict[str, Any],
        decision: dict[str, Any],
        bbox_by_ref: dict[str, dict[str, Any]],
        word_by_ref: dict[str, dict[str, Any]],
        evidence_by_ref: dict[str, dict[str, Any]],
        index_by_ref: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        table_ref = str(candidate.get("table_candidate_ref") or "")
        accepted = (
            projection.get("projection_status") == "ready"
            and projection.get("validator_status") == "passed"
            and projection.get("table_candidate_status") == "validated_geometry"
            and decision.get("status") == "validated_geometry"
        )
        status = "accepted" if accepted else "blocked"
        rows = (
            [
                {
                    "row_ref": item.get("row_ref"),
                    "row_ordinal": int(item.get("row_ordinal") or 0),
                    "row_role": item.get("row_role"),
                    "row_checksum_ref": item.get("row_checksum_ref"),
                }
                for item in _dicts(projection.get("rows"))
            ]
            if accepted
            else []
        )
        compact_cells: list[dict[str, Any]] = []
        if accepted:
            values = {
                str(item.get("value_path_ref") or ""): item
                for item in _dicts(projection.get("private_values"))
            }
            source_index = {
                str(item.get("source_value_ref") or ""): item
                for item in _dicts(projection.get("source_value_index"))
            }
            for cell in _dicts(projection.get("cells")):
                value = values.get(str(cell.get("normalized_private_value_path") or ""))
                if value is None:
                    raise PdfCompactCanonicalError(
                        "pdf_compact_cell_value_missing", str(cell.get("cell_ref") or "")
                    )
                source_value_refs = [str(item) for item in cell.get("source_value_refs") or []]
                for source_value_ref in source_value_refs:
                    existing_owner = index_by_ref.get(source_value_ref)
                    owner = {
                        "cell_ref": str(cell.get("cell_ref") or ""),
                        "table_ref": table_ref,
                    }
                    if existing_owner is not None and existing_owner != owner:
                        raise PdfCompactCanonicalError(
                            "pdf_compact_duplicate_source_ownership", source_value_ref
                        )
                    source_entry = source_index.get(source_value_ref)
                    if source_entry is None:
                        raise PdfCompactCanonicalError(
                            "pdf_compact_source_index_missing", source_value_ref
                        )
                    word_ref = str(source_entry.get("source_object_ref") or "")
                    word = word_by_ref.get(word_ref)
                    if word is None:
                        raise PdfCompactCanonicalError(
                            "pdf_compact_source_word_missing", source_value_ref
                        )
                    evidence = {
                        "source_value_ref": source_value_ref,
                        "source_object_ref": word_ref,
                        "page_ref": word.get("page_ref"),
                        "bbox": _bbox(bbox_by_ref, word.get("bbox_ref")),
                        "text": word.get("text"),
                        "text_checksum_ref": word.get("text_checksum_ref"),
                        "value_checksum_ref": source_entry.get("value_checksum_ref"),
                    }
                    existing = evidence_by_ref.get(source_value_ref)
                    if existing is not None and existing != evidence:
                        raise PdfCompactCanonicalError(
                            "pdf_compact_inconsistent_source_evidence", source_value_ref
                        )
                    evidence_by_ref[source_value_ref] = evidence
                    index_by_ref[source_value_ref] = owner
                compact_cells.append(
                    {
                        "cell_ref": cell.get("cell_ref"),
                        "row_ref": cell.get("row_ref"),
                        "row_ordinal": int(cell.get("row_ordinal") or 0),
                        "column_ref": cell.get("column_ref"),
                        "column_ordinal": int(cell.get("column_ordinal") or 0),
                        "row_span": int(cell.get("row_span") or 0),
                        "column_span": int(cell.get("column_span") or 0),
                        "bbox_ref": cell.get("bbox_ref"),
                        "bbox": _bbox(bbox_by_ref, cell.get("bbox_ref")),
                        "text": value.get("normalized_value"),
                        "value_checksum_ref": value.get("value_checksum_ref"),
                        "source_value_refs": source_value_refs,
                        "empty_cell": cell.get("empty_cell") is True,
                        "flags": sorted(
                            key
                            for key in (
                                "multi_line_cell",
                                "wrapped_text_cell",
                                "ambiguous_cell_boundary",
                                "split_cell_candidate",
                            )
                            if cell.get(key) is True
                        ),
                    }
                )
            actual_position_list = [
                (int(item["row_ordinal"]), int(item["column_ordinal"]))
                for item in compact_cells
            ]
            row_count = int(projection.get("row_count") or 0)
            column_count = int(projection.get("column_count") or 0)
            if (
                len(actual_position_list) != len(set(actual_position_list))
                or any(
                    row < 1
                    or row > row_count
                    or column < 1
                    or column > column_count
                    for row, column in actual_position_list
                )
            ):
                raise PdfCompactCanonicalError("pdf_compact_cell_grid_invalid", table_ref)

        return {
            "table_ref": table_ref,
            "table_projection_id": projection.get("table_projection_id"),
            "source_unit_ref": unit.get("unit_ref"),
            "source_unit_checksum_ref": unit.get("source_unit_checksum_ref"),
            "parent_payload_ref": projection.get("parent_payload_ref"),
            "page_ref": candidate.get("page_ref"),
            "bbox_ref": candidate.get("bbox_ref"),
            "bbox": _bbox(bbox_by_ref, candidate.get("bbox_ref")),
            "status": status,
            "current_projection_status": projection.get("projection_status"),
            "current_table_candidate_status": projection.get("table_candidate_status"),
            "current_validator_status": projection.get("validator_status"),
            "validation_ref": projection.get("table_projection_checksum_ref"),
            "decision_status": decision.get("status"),
            "decision_path": [
                "current_pdf_parser",
                str(projection.get("reconstruction_strategy") or "unknown"),
                str(projection.get("table_candidate_status") or "unknown"),
            ],
            "reason_codes": sorted(
                set(
                    list(decision.get("reason_codes") or [])
                    + list(projection.get("reconstruction_reason_codes") or [])
                )
            ),
            "reconstruction_strategy": projection.get("reconstruction_strategy"),
            "reconstruction_quality": projection.get("reconstruction_quality"),
            "column_refs": list(projection.get("column_refs") or []) if accepted else [],
            "row_count": int(projection.get("row_count") or 0) if accepted else 0,
            "column_count": int(projection.get("column_count") or 0) if accepted else 0,
            "cell_count": int(projection.get("cell_count") or 0) if accepted else 0,
            "rows": _pack_rows(rows),
            "cells": _pack_cells(compact_cells),
            "header_model": copy.deepcopy(projection.get("header_model") or {}),
            "coverage": _compact_coverage(projection.get("coverage")),
            "quality": copy.deepcopy(projection.get("quality") or {}),
            "geometry_summary": {
                "geometry_confidence": candidate.get("geometry_confidence"),
                "table_strategy_ref": candidate.get("table_strategy_ref"),
                "fallback_text_refs_total": len(
                    _object(projection.get("geometry")).get("fallback_text_refs") or []
                ),
                "fallback_text_refs_checksum": _ref_set_checksum(
                    _object(projection.get("geometry")).get("fallback_text_refs") or []
                ),
            },
            "projection_compatibility": {
                "schema_version": projection.get("schema_version"),
                "normalization_run_id": projection.get("normalization_run_id"),
                "source_document_ref": projection.get("source_document_ref"),
                "source_format": projection.get("source_format"),
                "table_origin": projection.get("table_origin"),
                "source_checksum_ref": projection.get("source_checksum_ref"),
                "payload_checksum_ref": projection.get("payload_checksum_ref"),
                "parser_ref": projection.get("parser_ref"),
                "parser_engine": projection.get("parser_engine"),
                "parser_engine_version": projection.get("parser_engine_version"),
                "parser_config_ref": projection.get("parser_config_ref"),
                "table_bbox_ref": projection.get("table_bbox_ref"),
                "page_refs": list(projection.get("page_refs") or []),
                "section_refs": list(projection.get("section_refs") or []),
                "table_projection_checksum_ref": projection.get(
                    "table_projection_checksum_ref"
                ),
            },
        }


class PdfCompactCanonicalValidator:
    def validate(self, document: dict[str, Any]) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        if set(document) != _TOP_LEVEL_KEYS:
            errors.append(_error("pdf_compact_top_level_keys_invalid", "document"))
        if document.get("schema_version") != PDF_COMPACT_CANONICAL_SCHEMA_VERSION:
            errors.append(_error("pdf_compact_schema_mismatch", "document"))
        if document.get("policy_version") != PDF_COMPACT_CANONICAL_POLICY_VERSION:
            errors.append(_error("pdf_compact_policy_mismatch", "document"))
        if not document.get("original_pdf_artifact_ref"):
            errors.append(_error("pdf_compact_original_artifact_ref_missing", "document"))
        if len(str(document.get("input_pdf_sha256") or "")) != 64:
            errors.append(_error("pdf_compact_input_sha256_invalid", "document"))
        for key, expected in _GUARDS.items():
            if document.get(key) is not expected:
                errors.append(_error("pdf_compact_guard_failed", key))
        for path, key in _walk_keys(document):
            if key in _FORBIDDEN_KEYS:
                errors.append(_error("pdf_compact_forbidden_field", f"{path}.{key}"))

        pages = _dicts(document.get("pages"))
        page_refs = [str(item.get("page_ref") or "") for item in pages]
        if not pages or not all(page_refs) or len(page_refs) != len(set(page_refs)):
            errors.append(_error("pdf_compact_page_manifest_invalid", "pages"))
        tables = _dicts(document.get("tables"))
        table_refs = [str(item.get("table_ref") or "") for item in tables]
        coverage = _object(document.get("coverage"))
        if table_refs != [str(item) for item in coverage.get("accounted_table_refs") or []]:
            errors.append(_error("pdf_compact_table_coverage_order_mismatch", "coverage"))
        if sorted(table_refs) != sorted(str(item) for item in coverage.get("candidate_refs") or []):
            errors.append(_error("pdf_compact_table_candidate_accounting_mismatch", "coverage"))
        if coverage.get("coverage_status") != "complete":
            errors.append(_error("pdf_compact_table_coverage_incomplete", "coverage"))
        if coverage.get("duplicate_table_refs") or coverage.get("unaccounted_table_refs") or coverage.get("unexpected_table_refs"):
            errors.append(_error("pdf_compact_table_coverage_errors", "coverage"))
        coverage_material = copy.deepcopy(coverage)
        coverage_checksum = coverage_material.pop("coverage_checksum_ref", None)
        if coverage_checksum != _sha256_ref("pdfcompactcoveragechk", coverage_material):
            errors.append(_error("pdf_compact_coverage_checksum_mismatch", "coverage"))

        evidence = compact_source_evidence(document)
        evidence_refs = {str(item.get("source_value_ref") or "") for item in evidence}
        source_index = _object(document.get("source_value_index"))
        index_items = _object(source_index.get("items"))
        index_refs = set(index_items)
        if evidence_refs != index_refs or "" in evidence_refs:
            errors.append(_error("pdf_compact_source_index_mismatch", "source_value_index"))
        if sorted(index_items.values()) != list(range(len(evidence))):
            errors.append(_error("pdf_compact_source_index_ordinal_invalid", "source_value_index"))
        if int(coverage.get("accepted_source_refs_total") or 0) != len(evidence_refs):
            errors.append(_error("pdf_compact_source_coverage_count_mismatch", "coverage"))
        if coverage.get("accepted_source_ref_set_checksum") != _ref_set_checksum(
            sorted(evidence_refs)
        ):
            errors.append(_error("pdf_compact_source_coverage_checksum_mismatch", "coverage"))
        if coverage.get("duplicate_source_refs") or coverage.get("unaccounted_source_refs"):
            errors.append(_error("pdf_compact_source_coverage_errors", "coverage"))
        referenced: set[str] = set()
        for table in tables:
            status = table.get("status")
            if status not in {"accepted", "blocked"}:
                errors.append(_error("pdf_compact_table_status_invalid", table.get("table_ref")))
                continue
            rows = compact_table_rows(table)
            cells = compact_table_cells(table)
            if status == "blocked":
                if rows or cells or table.get("row_count") or table.get("cell_count"):
                    errors.append(_error("pdf_compact_blocked_table_contains_grid", table.get("table_ref")))
                continue
            row_count = int(table.get("row_count") or 0)
            column_count = int(table.get("column_count") or 0)
            if row_count != len(rows) or int(table.get("cell_count") or 0) != len(cells):
                errors.append(_error("pdf_compact_table_counts_mismatch", table.get("table_ref")))
            positions = [
                (int(item.get("row_ordinal") or 0), int(item.get("column_ordinal") or 0))
                for item in cells
            ]
            if (
                len(positions) != len(set(positions))
                or any(
                    row < 1
                    or row > row_count
                    or column < 1
                    or column > column_count
                    for row, column in positions
                )
            ):
                errors.append(_error("pdf_compact_cell_grid_mismatch", table.get("table_ref")))
            for cell in cells:
                refs = {str(item) for item in cell.get("source_value_refs") or []}
                referenced.update(refs)
                if not refs <= evidence_refs:
                    errors.append(_error("pdf_compact_cell_source_ref_unresolved", cell.get("cell_ref")))
                text = str(cell.get("text") or "")
                if bool(cell.get("empty_cell")) != (text == ""):
                    errors.append(_error("pdf_compact_empty_cell_mismatch", cell.get("cell_ref")))
        if referenced != evidence_refs:
            errors.append(_error("pdf_compact_unreferenced_source_evidence", "selected_source_evidence"))
        if document.get("canonical_document_checksum_ref") != _compact_checksum(document):
            errors.append(_error("pdf_compact_checksum_mismatch", "document"))
        return {
            "schema_version": "broker_reports_pdf_compact_canonical_validation_v1",
            "passed": not errors,
            "validator_status": "passed" if not errors else "failed",
            "errors_count": len(errors),
            "errors": errors,
        }


def resolve_compact_source_value(document: dict[str, Any], source_value_ref: str) -> str:
    validation = PdfCompactCanonicalValidator().validate(document)
    if not validation["passed"]:
        raise PdfCompactCanonicalError("pdf_compact_source_resolution_document_invalid")
    matches = [
        item for item in compact_source_evidence(document)
        if item.get("source_value_ref") == source_value_ref
    ]
    if len(matches) != 1:
        raise PdfCompactCanonicalError("pdf_compact_source_value_ref_not_unique", source_value_ref)
    return str(matches[0].get("text") or "")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def compact_source_evidence(document: dict[str, Any]) -> list[dict[str, Any]]:
    packed = _object(document.get("selected_source_evidence"))
    fields = [str(item) for item in packed.get("fields") or []]
    expected = [
        "source_value_ref",
        "source_object_ref",
        "page_ref",
        "bbox",
        "text",
        "text_checksum_ref",
        "value_checksum_ref",
    ]
    if fields != expected:
        return []
    result: list[dict[str, Any]] = []
    for item in packed.get("items") or []:
        if not isinstance(item, list) or len(item) != len(fields):
            return []
        result.append(dict(zip(fields, item)))
    return result


def compact_table_rows(table: dict[str, Any]) -> list[dict[str, Any]]:
    return _unpack_records(
        table.get("rows"),
        ["row_ref", "row_ordinal", "row_role", "row_checksum_ref"],
    )


def compact_table_cells(table: dict[str, Any]) -> list[dict[str, Any]]:
    return _unpack_records(
        table.get("cells"),
        [
            "cell_ref",
            "row_ref",
            "row_ordinal",
            "column_ref",
            "column_ordinal",
            "row_span",
            "column_span",
            "bbox_ref",
            "bbox",
            "text",
            "value_checksum_ref",
            "source_value_refs",
            "empty_cell",
            "flags",
        ],
    )


def _compact_checksum(document: dict[str, Any]) -> str:
    material = copy.deepcopy(document)
    material.pop("canonical_document_checksum_ref", None)
    return _sha256_ref("pdfcompactchk", material)


def _sha256_ref(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def _bbox(index: dict[str, dict[str, Any]], bbox_ref: Any) -> list[float]:
    value = index.get(str(bbox_ref or ""))
    if value is None:
        raise PdfCompactCanonicalError("pdf_compact_bbox_missing", str(bbox_ref or ""))
    bbox = value.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise PdfCompactCanonicalError("pdf_compact_bbox_invalid", str(bbox_ref or ""))
    return [float(item) for item in bbox]


def _page_number(pages: list[dict[str, Any]], page_ref: Any) -> int:
    for page in pages:
        if page.get("page_ref") == page_ref:
            return int(page.get("page_number") or 0)
    return 0


def _unique_index(
    values: list[dict[str, Any]], key: str, duplicate_code: str
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for value in values:
        ref = str(value.get(key) or "")
        if not ref:
            continue
        if ref in result:
            raise PdfCompactCanonicalError(duplicate_code, ref)
        result[ref] = value
    return result


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicate: set[str] = set()
    for value in values:
        if value in seen:
            duplicate.add(value)
        seen.add(value)
    return sorted(duplicate)


def _compact_coverage(value: Any) -> dict[str, Any]:
    coverage = _object(value)
    selected = [str(item) for item in coverage.get("selected_source_refs") or []]
    return {
        "schema_version": coverage.get("schema_version"),
        "coverage_ref": coverage.get("coverage_ref"),
        "coverage_status": coverage.get("coverage_status"),
        "selected_total": int(coverage.get("selected_total") or 0),
        "accounted_total": int(coverage.get("accounted_total") or 0),
        "fallback_refs_total": len(coverage.get("fallback_text_refs") or []),
        "non_table_refs_total": len(coverage.get("non_table_refs") or []),
        "rejected_refs_total": len(coverage.get("rejected_refs") or []),
        "duplicate_refs_total": len(coverage.get("duplicate_accounted_refs") or []),
        "unaccounted_refs_total": len(coverage.get("unaccounted_refs") or []),
        "selected_ref_set_checksum": _ref_set_checksum(selected),
        "all_selected_refs_accounted": coverage.get("all_selected_refs_accounted") is True,
    }


def _pack_rows(values: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ["row_ref", "row_ordinal", "row_role", "row_checksum_ref"]
    return {"fields": fields, "items": [[item.get(key) for key in fields] for item in values]}


def _pack_cells(values: list[dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "cell_ref",
        "row_ref",
        "row_ordinal",
        "column_ref",
        "column_ordinal",
        "row_span",
        "column_span",
        "bbox_ref",
        "bbox",
        "text",
        "value_checksum_ref",
        "source_value_refs",
        "empty_cell",
        "flags",
    ]
    return {"fields": fields, "items": [[item.get(key) for key in fields] for item in values]}


def _unpack_records(value: Any, expected_fields: list[str]) -> list[dict[str, Any]]:
    packed = _object(value)
    fields = [str(item) for item in packed.get("fields") or []]
    if fields != expected_fields:
        return []
    result: list[dict[str, Any]] = []
    for item in packed.get("items") or []:
        if not isinstance(item, list) or len(item) != len(fields):
            return []
        result.append(dict(zip(fields, item)))
    return result


def _ref_set_checksum(values: Any) -> str:
    return _sha256_ref("refsetchk", sorted(str(item) for item in values or []))


def _walk_keys(value: Any, path: str = "$"):
    if isinstance(value, dict):
        for key, child in value.items():
            yield path, str(key)
            yield from _walk_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_keys(child, f"{path}[{index}]")


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)] if isinstance(value, list) else []


def _error(code: str, subject: Any) -> dict[str, str]:
    return {"code": code, "subject": str(subject or "")}
