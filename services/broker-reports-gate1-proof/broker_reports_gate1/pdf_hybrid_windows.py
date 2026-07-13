from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_budget import PdfHybridBudgetGuard
from .pdf_hybrid_contracts import (
    PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
    hybrid_binding_output_schema,
    sha256_json,
    validate_binding_output_shape,
)


PDF_HYBRID_WINDOW_PLAN_SCHEMA = "broker_reports_pdf_hybrid_row_window_plan_v2"
PDF_HYBRID_WINDOW_EVIDENCE_SCHEMA = "broker_reports_pdf_hybrid_window_evidence_v2"
PDF_HYBRID_LOGICAL_EVIDENCE_SCHEMA = "broker_reports_pdf_hybrid_logical_evidence_v2"
PDF_HYBRID_ROW_WINDOW_POLICY_VERSION = "pdf_hybrid_row_window_policy_v2"
FACTORY_REQUIRED = (
    "PdfHybridWindowFactory.create is the only row-window planning, package, and join entrypoint"
)
FORBIDDEN = (
    "Windows must not split columns, truncate candidates, overlap row ownership, or join conflicting identities"
)


class PdfHybridWindowError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PdfHybridWindowConfig:
    policy_version: str = PDF_HYBRID_ROW_WINDOW_POLICY_VERSION
    maximum_rows_per_window: int = 12
    maximum_candidates_per_window: int = 192


class PdfHybridWindowFactory:
    def __init__(self, config: PdfHybridWindowConfig | None = None) -> None:
        self.config = config or PdfHybridWindowConfig()

    def create(self, *, budget: PdfHybridBudgetGuard) -> "PdfHybridWindowRuntime":
        if self.config.policy_version != PDF_HYBRID_ROW_WINDOW_POLICY_VERSION:
            raise PdfHybridWindowError("pdf_hybrid_window_policy_invalid")
        return PdfHybridWindowRuntime(self.config, budget)


class PdfHybridWindowRuntime:
    TASK_TEXT = (
        "Return only candidate-id placement. Copy package_id, crop_sha256 and candidate_dictionary_hash "
        "from the matching named fields in i. "
        "Produce exactly r[2] local rows and r[3] columns; local row ordinals start at 1. "
        "When r[0] is 1, header_rows must be local rows 1 through h[1]; otherwise header_rows must be []. "
        "Use every supplied id exactly once and never emit an id absent from c. "
        "Use [] only where the visible grid cell is empty. "
        "Do not return values, calculations or inferred facts. Return ambiguous if placement is not provable."
    )

    def __init__(
        self,
        config: PdfHybridWindowConfig,
        budget: PdfHybridBudgetGuard,
    ) -> None:
        self.config = config
        self.budget = budget

    def plan(self, *, compact_ledger: dict[str, Any]) -> dict[str, Any]:
        dictionary = _object(compact_ledger.get("private_candidate_dictionary"))
        row_count = int(compact_ledger.get("row_count") or 0)
        column_count = int(compact_ledger.get("column_count") or 0)
        table_bbox = _bbox(compact_ledger.get("table_bbox"))
        rows = {
            int(item.get("ordinal") or 0): item
            for item in _dicts(compact_ledger.get("row_model"))
        }
        if row_count < 1 or column_count < 1 or table_bbox is None or len(rows) != row_count:
            raise PdfHybridWindowError("pdf_hybrid_window_ledger_shape_invalid")
        candidates_by_row: dict[int, list[str]] = {row: [] for row in range(1, row_count + 1)}
        for candidate_id in compact_ledger.get("candidate_order") or []:
            candidate = _object(dictionary.get(str(candidate_id)))
            row = int(candidate.get("expected_row_ordinal") or 0)
            if row not in candidates_by_row:
                raise PdfHybridWindowError("pdf_hybrid_window_candidate_row_invalid")
            candidates_by_row[row].append(str(candidate_id))
        minimum_windows = max(
            1,
            (row_count + self.config.maximum_rows_per_window - 1)
            // self.config.maximum_rows_per_window,
            (len(dictionary) + self.config.maximum_candidates_per_window - 1)
            // self.config.maximum_candidates_per_window,
        )
        ranges: list[tuple[int, int]] = []
        for window_count in range(minimum_windows, row_count + 1):
            candidate_ranges = _balanced_ranges(row_count, window_count)
            if all(
                sum(len(candidates_by_row[row]) for row in range(start, end + 1))
                <= self.config.maximum_candidates_per_window
                and end - start + 1 <= self.config.maximum_rows_per_window
                for start, end in candidate_ranges
            ):
                ranges = candidate_ranges
                break
        if not ranges:
            raise PdfHybridWindowError("pdf_hybrid_window_balanced_plan_unavailable")
        windows = []
        assigned: list[str] = []
        for row_start, row_end in ranges:
            candidate_ids = [
                candidate_id
                for row in range(row_start, row_end + 1)
                for candidate_id in candidates_by_row[row]
            ]
            crop_bbox = [
                table_bbox[0],
                float(rows[row_start]["start"]),
                table_bbox[2],
                float(rows[row_end]["end"]),
            ]
            window_index = len(windows) + 1
            window_id = "pdfhybridwin_" + stable_digest(
                [
                    compact_ledger.get("ledger_id"),
                    window_index,
                    row_start,
                    row_end,
                    candidate_ids,
                ],
                length=24,
            )
            windows.append(
                {
                    "window_id": window_id,
                    "window_index": window_index,
                    "row_start": row_start,
                    "row_end": row_end,
                    "row_count": row_end - row_start + 1,
                    "column_start": 1,
                    "column_end": column_count,
                    "column_count": column_count,
                    "candidate_ids": candidate_ids,
                    "candidate_count": len(candidate_ids),
                    "crop_bbox": [round(item, 6) for item in crop_bbox],
                    "shared_header_hash": _object(
                        compact_ledger.get("shared_header")
                    ).get("shared_header_hash"),
                    "shared_header_reused": window_index > 1,
                    "candidate_ownership": "exactly_once",
                    "column_split_performed": False,
                    "silent_truncation_performed": False,
                }
            )
            assigned.extend(candidate_ids)
        expected = [str(item) for item in compact_ledger.get("candidate_order") or []]
        if assigned != expected:
            raise PdfHybridWindowError("pdf_hybrid_window_candidate_ownership_incomplete")
        plan = {
            "schema_version": PDF_HYBRID_WINDOW_PLAN_SCHEMA,
            "policy_version": self.config.policy_version,
            "ledger_id": compact_ledger.get("ledger_id"),
            "logical_table_id": "pdfhybridlogical_"
            + stable_digest(
                [compact_ledger.get("ledger_id"), sha256_json(windows)], length=24
            ),
            "table_ref": compact_ledger.get("table_ref"),
            "row_count": row_count,
            "column_count": column_count,
            "windows": windows,
            "candidate_count": len(expected),
            "candidate_ids_assigned": len(assigned),
            "candidate_ids_unique": len(set(assigned)),
            "row_coverage": list(range(1, row_count + 1)),
            "exactly_once_candidate_ownership": True,
            "shared_header_hash": _object(compact_ledger.get("shared_header")).get(
                "shared_header_hash"
            ),
            "deterministic_join": True,
            "column_split_performed": False,
            "silent_truncation_performed": False,
        }
        plan["plan_checksum"] = sha256_json(plan)
        return plan

    def build_package(
        self,
        *,
        compact_ledger: dict[str, Any],
        plan: dict[str, Any],
        window: dict[str, Any],
        crop_manifest: dict[str, Any],
        private_crop_artifact_ref: str,
    ) -> dict[str, Any]:
        if plan.get("ledger_id") != compact_ledger.get("ledger_id"):
            raise PdfHybridWindowError("pdf_hybrid_window_plan_ledger_mismatch")
        if crop_manifest.get("table_ref") != compact_ledger.get("table_ref"):
            raise PdfHybridWindowError("pdf_hybrid_window_crop_table_mismatch")
        if _rounded_bbox(crop_manifest.get("declared_table_bbox")) != _rounded_bbox(
            window.get("crop_bbox")
        ):
            raise PdfHybridWindowError("pdf_hybrid_window_crop_bbox_mismatch")
        dictionary = _object(compact_ledger.get("private_candidate_dictionary"))
        candidate_ids = [str(item) for item in window.get("candidate_ids") or []]
        window_dictionary = {
            candidate_id: copy.deepcopy(dictionary[candidate_id])
            for candidate_id in candidate_ids
            if candidate_id in dictionary
        }
        if list(window_dictionary) != candidate_ids:
            raise PdfHybridWindowError("pdf_hybrid_window_dictionary_incomplete")
        dictionary_hash = sha256_json(window_dictionary)
        package_id = "pdfhybridpkg2_" + stable_digest(
            [
                plan.get("logical_table_id"),
                window.get("window_id"),
                crop_manifest.get("png_sha256"),
                dictionary_hash,
                self.config.policy_version,
            ],
            length=24,
        )
        crop_bbox = _bbox(crop_manifest.get("declared_table_bbox"))
        if crop_bbox is None:
            raise PdfHybridWindowError("pdf_hybrid_window_crop_bbox_invalid")
        records = []
        for candidate_id in candidate_ids:
            candidate = window_dictionary[candidate_id]
            normalized = _normalized_bbox(candidate["source_bbox"], crop_bbox)
            records.append(
                [
                    candidate_id,
                    candidate.get("exact_source_span"),
                    _short_class(candidate.get("exact_source_span")),
                    *normalized,
                ]
            )
        column_model = _normalized_axis(
            _dicts(compact_ledger.get("column_model")),
            crop_bbox[0],
            crop_bbox[2],
        )
        identity = {
            "package_id": package_id,
            "crop_sha256": crop_manifest.get("png_sha256"),
            "candidate_dictionary_hash": dictionary_hash,
        }
        model_facing = {
            "t": self.TASK_TEXT,
            "i": identity,
            "r": [
                int(window.get("row_start") or 0),
                int(window.get("row_end") or 0),
                int(window.get("row_count") or 0),
                int(window.get("column_count") or 0),
            ],
            "h": [
                window.get("shared_header_hash"),
                int(compact_ledger.get("header_depth") or 0),
                column_model,
            ],
            "c": records,
        }
        schema = _window_output_schema(
            row_count=int(window.get("row_count") or 0),
            column_count=int(window.get("column_count") or 0),
        )
        accounting = self.budget.estimate(
            model_facing=model_facing,
            output_schema=schema,
            crop_manifest=crop_manifest,
            candidate_count=len(records),
            row_count=int(window.get("row_count") or 0),
            column_count=int(window.get("column_count") or 0),
        )
        self.budget.require_static(accounting)
        package = {
            "schema_version": PDF_HYBRID_WINDOW_EVIDENCE_SCHEMA,
            "policy_version": self.config.policy_version,
            "package_id": package_id,
            "logical_table_id": plan.get("logical_table_id"),
            "ledger_id": compact_ledger.get("ledger_id"),
            "document_ref": compact_ledger.get("document_ref"),
            "pdf_sha256": compact_ledger.get("pdf_sha256"),
            "page_ref": compact_ledger.get("page_ref"),
            "page_number": compact_ledger.get("page_number"),
            "table_ref": compact_ledger.get("table_ref"),
            "window": copy.deepcopy(window),
            "crop_identity": {
                "private_crop_artifact_ref": private_crop_artifact_ref,
                "crop_id": crop_manifest.get("crop_id"),
                "crop_sha256": crop_manifest.get("png_sha256"),
                "dpi": crop_manifest.get("dpi"),
                "width": crop_manifest.get("width"),
                "height": crop_manifest.get("height"),
                "renderer": crop_manifest.get("renderer"),
                "renderer_version": crop_manifest.get("renderer_version"),
                "declared_table_bbox": crop_manifest.get("declared_table_bbox"),
                "source_to_pixel_transform": crop_manifest.get(
                    "source_to_pixel_transform"
                ),
            },
            "candidate_dictionary_hash": dictionary_hash,
            "model_facing": model_facing,
            "private_candidate_dictionary": window_dictionary,
            "output_schema": schema,
            "component_accounting": accounting,
            "source_authority": "existing_production_pdf_words_only",
            "ocr_used": False,
            "business_domain_context_included": False,
            "silent_truncation_performed": False,
            "column_split_performed": False,
        }
        package["package_hash"] = sha256_json(package)
        return package

    def join(
        self,
        *,
        compact_ledger: dict[str, Any],
        plan: dict[str, Any],
        packages: list[dict[str, Any]],
        bindings: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        windows = _dicts(plan.get("windows"))
        if len(packages) != len(windows) or len(bindings) != len(windows):
            raise PdfHybridWindowError("pdf_hybrid_window_join_window_count_mismatch")
        joined_rows: list[dict[str, Any]] = []
        joined_spans: list[dict[str, Any]] = []
        header_rows: list[int] = []
        header_hierarchy: list[dict[str, Any]] = []
        crop_hashes = []
        all_package_ids = []
        for window, package, binding in zip(windows, packages, bindings):
            errors = validate_binding_output_shape(binding)
            if errors:
                raise PdfHybridWindowError(errors[0])
            if binding.get("decision") != "bound":
                raise PdfHybridWindowError("pdf_hybrid_window_join_binding_not_bound")
            crop = _object(package.get("crop_identity"))
            if (
                package.get("logical_table_id") != plan.get("logical_table_id")
                or binding.get("package_id") != package.get("package_id")
                or binding.get("crop_sha256") != crop.get("crop_sha256")
                or binding.get("candidate_dictionary_hash")
                != package.get("candidate_dictionary_hash")
            ):
                raise PdfHybridWindowError("pdf_hybrid_window_join_identity_mismatch")
            expected_rows = int(window.get("row_count") or 0)
            if (
                int(binding.get("row_count") or 0) != expected_rows
                or int(binding.get("column_count") or 0)
                != int(plan.get("column_count") or 0)
            ):
                raise PdfHybridWindowError("pdf_hybrid_window_join_shape_mismatch")
            offset = int(window.get("row_start") or 0) - 1
            for row in binding.get("rows") or []:
                joined_rows.append(
                    {
                        "row_ordinal": int(row["row_ordinal"]) + offset,
                        "row_kind": row["row_kind"],
                        "cells": copy.deepcopy(row["cells"]),
                    }
                )
            translated_headers = [int(item) + offset for item in binding.get("header_rows") or []]
            if int(window.get("window_index") or 0) == 1:
                header_rows = translated_headers
                header_hierarchy = copy.deepcopy(binding.get("header_hierarchy") or [])
            elif translated_headers:
                raise PdfHybridWindowError("pdf_hybrid_window_join_repeated_header_output")
            for span in binding.get("spans") or []:
                translated = copy.deepcopy(span)
                translated["start_row"] = int(translated["start_row"]) + offset
                translated["end_row"] = int(translated["end_row"]) + offset
                joined_spans.append(translated)
            crop_hashes.append(crop.get("crop_sha256"))
            all_package_ids.append(package.get("package_id"))
        expected_ordinals = list(range(1, int(plan.get("row_count") or 0) + 1))
        if [int(item.get("row_ordinal") or 0) for item in joined_rows] != expected_ordinals:
            raise PdfHybridWindowError("pdf_hybrid_window_join_row_coverage_invalid")
        crop_set_hash = sha256_json(crop_hashes)
        logical_package_id = str(plan.get("logical_table_id") or "")
        binding = {
            "schema_version": PDF_HYBRID_BINDING_OUTPUT_SCHEMA,
            "package_id": logical_package_id,
            "crop_sha256": crop_set_hash,
            "candidate_dictionary_hash": compact_ledger.get(
                "candidate_dictionary_hash"
            ),
            "decision": "bound",
            "row_count": int(plan.get("row_count") or 0),
            "column_count": int(plan.get("column_count") or 0),
            "header_rows": header_rows,
            "header_hierarchy": header_hierarchy,
            "rows": joined_rows,
            "spans": joined_spans,
            "uncertainty_codes": [],
        }
        shape_errors = validate_binding_output_shape(binding)
        if shape_errors:
            raise PdfHybridWindowError(shape_errors[0])
        evidence = {
            "schema_version": PDF_HYBRID_LOGICAL_EVIDENCE_SCHEMA,
            "package_id": logical_package_id,
            "logical_table_id": logical_package_id,
            "ledger_id": compact_ledger.get("ledger_id"),
            "document_ref": compact_ledger.get("document_ref"),
            "pdf_sha256": compact_ledger.get("pdf_sha256"),
            "page_ref": compact_ledger.get("page_ref"),
            "page_number": compact_ledger.get("page_number"),
            "table_ref": compact_ledger.get("table_ref"),
            "crop_identity": {
                "crop_kind": "ordered_row_window_set",
                "crop_sha256": crop_set_hash,
                "window_crop_sha256s": crop_hashes,
            },
            "candidate_dictionary_hash": compact_ledger.get(
                "candidate_dictionary_hash"
            ),
            "private_candidate_dictionary": copy.deepcopy(
                compact_ledger.get("private_candidate_dictionary") or {}
            ),
            "window_package_ids": all_package_ids,
            "window_plan_checksum": plan.get("plan_checksum"),
            "source_authority": "existing_production_pdf_words_only",
            "silent_truncation_performed": False,
            "column_split_performed": False,
        }
        evidence["package_hash"] = sha256_json(evidence)
        return evidence, binding


def _window_output_schema(*, row_count: int, column_count: int) -> dict[str, Any]:
    schema = hybrid_binding_output_schema()
    properties = schema["properties"]
    properties["row_count"]["minimum"] = row_count
    properties["row_count"]["maximum"] = row_count
    properties["column_count"]["minimum"] = column_count
    properties["column_count"]["maximum"] = column_count
    properties["rows"]["minItems"] = row_count
    properties["rows"]["maxItems"] = row_count
    row = properties["rows"]["items"]
    row["properties"]["row_ordinal"]["maximum"] = row_count
    row["properties"]["cells"]["minItems"] = column_count
    row["properties"]["cells"]["maxItems"] = column_count
    return schema


def _balanced_ranges(row_count: int, window_count: int) -> list[tuple[int, int]]:
    base, remainder = divmod(row_count, window_count)
    sizes = [base + (1 if index < remainder else 0) for index in range(window_count)]
    result = []
    start = 1
    for size in sizes:
        end = start + size - 1
        result.append((start, end))
        start = end + 1
    return result


def _normalized_axis(values: list[dict[str, Any]], start: float, end: float) -> list[list[Any]]:
    width = end - start
    return [
        [
            int(item.get("ordinal") or 0),
            round((float(item.get("start") or 0) - start) / width, 4),
            round((float(item.get("end") or 0) - start) / width, 4),
        ]
        for item in values
    ]


def _normalized_bbox(value: Any, scope: list[float]) -> list[float]:
    bbox = _bbox(value)
    if bbox is None:
        raise PdfHybridWindowError("pdf_hybrid_window_candidate_bbox_invalid")
    width = scope[2] - scope[0]
    height = scope[3] - scope[1]
    return [
        round((bbox[0] - scope[0]) / width, 4),
        round((bbox[1] - scope[1]) / height, 4),
        round((bbox[2] - scope[0]) / width, 4),
        round((bbox[3] - scope[1]) / height, 4),
    ]


def _short_class(value: Any) -> str:
    text = str(value or "").strip()
    return "n" if text and all(char.isdigit() or char in " +-.," for char in text) else "t"


def _rounded_bbox(value: Any) -> list[float] | None:
    bbox = _bbox(value)
    return [round(item, 6) for item in bbox] if bbox else None


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
