from __future__ import annotations

from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import (
    PDF_TABLE_MATERIALIZATION_SCHEMA,
    PDF_TABLE_VALIDATION_SCHEMA,
    sha256_json,
    validate_binding_output_shape,
)


FACTORY_REQUIRED = "PdfTableValidationFactory.create is the only hybrid table validation entrypoint"
FORBIDDEN = "Validation must fail closed and must not equate provenance authenticity with placement correctness"


class PdfTableValidationFactory:
    def create(self) -> "PdfTableValidator":
        return PdfTableValidator()


class PdfTableValidator:
    def validate(
        self,
        *,
        evidence_package: dict[str, Any],
        binding_output: dict[str, Any],
        materialization: dict[str, Any] | None,
        classification: dict[str, Any],
        repeated_materialization_checksum: str | None = None,
        require_repeatability: bool = False,
        independent_structural_validation: dict[str, Any] | None = None,
        repeatability_validation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        gates: dict[str, dict[str, Any]] = {}
        shape_errors = validate_binding_output_shape(binding_output)
        gates["exact_output_contract"] = _gate(not shape_errors, shape_errors)
        identity_errors = []
        if binding_output.get("package_id") != evidence_package.get("package_id"):
            identity_errors.append("pdf_hybrid_package_identity_mismatch")
        crop = _object(evidence_package.get("crop_identity"))
        if binding_output.get("crop_sha256") != crop.get("crop_sha256"):
            identity_errors.append("pdf_hybrid_crop_identity_mismatch")
        if binding_output.get("candidate_dictionary_hash") != evidence_package.get(
            "candidate_dictionary_hash"
        ):
            identity_errors.append("pdf_hybrid_candidate_dictionary_hash_mismatch")
        gates["package_crop_hash_identity"] = _gate(not identity_errors, identity_errors)
        dictionary = _object(evidence_package.get("private_candidate_dictionary"))
        used_ids = [
            str(candidate_id)
            for row in binding_output.get("rows") or []
            if isinstance(row, dict)
            for cell in row.get("cells") or []
            if isinstance(cell, list)
            for candidate_id in cell
        ]
        invalid_ids = sorted(set(used_ids) - set(dictionary))
        gates["candidate_id_membership"] = _gate(
            not invalid_ids,
            ["pdf_hybrid_candidate_id_not_in_dictionary"] if invalid_ids else [],
        )
        material = materialization if isinstance(materialization, dict) else {}
        provenance_errors = []
        if material.get("schema_version") != PDF_TABLE_MATERIALIZATION_SCHEMA:
            provenance_errors.append("pdf_hybrid_materialization_contract_invalid")
        if material.get("candidate_dictionary_hash") != evidence_package.get(
            "candidate_dictionary_hash"
        ):
            provenance_errors.append("pdf_hybrid_materialization_dictionary_mismatch")
        if material.get("package_id") != evidence_package.get("package_id"):
            provenance_errors.append("pdf_hybrid_materialization_package_mismatch")
        if material.get("crop_sha256") != crop.get("crop_sha256"):
            provenance_errors.append("pdf_hybrid_materialization_crop_mismatch")
        material_without_checksum = dict(material)
        stored_materialization_checksum = material_without_checksum.pop(
            "materialization_checksum", None
        )
        if (
            not stored_materialization_checksum
            or stored_materialization_checksum != sha256_json(material_without_checksum)
        ):
            provenance_errors.append("pdf_hybrid_materialization_checksum_mismatch")
        placement_projection = {
            "row_count": material.get("row_count"),
            "column_count": material.get("column_count"),
            "rows": [
                {
                    "row_ordinal": item.get("row_ordinal"),
                    "row_kind": item.get("row_kind"),
                }
                for item in material.get("rows") or []
                if isinstance(item, dict)
            ],
            "cells": [
                {
                    "row_ordinal": item.get("row_ordinal"),
                    "column_ordinal": item.get("column_ordinal"),
                    "candidate_ids": item.get("candidate_ids"),
                    "explicit_empty": item.get("explicit_empty"),
                }
                for item in material.get("cells") or []
                if isinstance(item, dict)
            ],
            "header_rows": material.get("header_rows") or [],
            "header_hierarchy": material.get("header_hierarchy") or [],
            "spans": material.get("spans") or [],
        }
        if material.get("placement_checksum") != sha256_json(placement_projection):
            provenance_errors.append("pdf_hybrid_placement_checksum_mismatch")
        if material.get("model_invented_values_total") != 0:
            provenance_errors.append("pdf_hybrid_model_invented_value")
        if material.get("extra_candidate_ids"):
            provenance_errors.append("pdf_hybrid_materialization_extra_candidate")
        gates["exact_source_provenance"] = _gate(
            not provenance_errors, provenance_errors
        )
        rows = int(binding_output.get("row_count") or 0)
        columns = int(binding_output.get("column_count") or 0)
        cells = material.get("cells") if isinstance(material.get("cells"), list) else []
        rectangular_errors = []
        if binding_output.get("decision") == "bound" and len(cells) != rows * columns:
            rectangular_errors.append("pdf_hybrid_complete_grid_missing")
        widths = [
            len(row.get("cells") or [])
            for row in binding_output.get("rows") or []
            if isinstance(row, dict)
        ]
        if binding_output.get("decision") == "bound" and any(width != columns for width in widths):
            rectangular_errors.append("pdf_hybrid_row_width_inconsistent")
        gates["complete_rectangular_grid"] = _gate(
            not rectangular_errors, rectangular_errors
        )
        empty_count = sum(item.get("explicit_empty") is True for item in cells)
        empty_errors = []
        for item in cells:
            if bool(item.get("candidate_ids")) == bool(item.get("explicit_empty")):
                empty_errors.append("pdf_hybrid_empty_cell_marker_inconsistent")
                break
        gates["explicit_empty_cell_coverage"] = _gate(not empty_errors, empty_errors)
        duplicate_ids = sorted(set(used_ids), key=used_ids.index)
        duplicate_ids = [item for item in duplicate_ids if used_ids.count(item) > 1]
        gates["duplicate_candidate_use"] = _gate(
            not duplicate_ids,
            ["pdf_hybrid_candidate_duplicate_use"] if duplicate_ids else [],
        )
        header_errors = []
        header_rows = list(binding_output.get("header_rows") or [])
        if len(header_rows) > 8 or any(
            not isinstance(item, int) or item < 1 or item > rows for item in header_rows
        ):
            header_errors.append("pdf_hybrid_header_hierarchy_invalid")
        gates["header_hierarchy"] = _gate(not header_errors, header_errors)
        accounting_errors = []
        source_refs = material.get("source_value_refs") or []
        word_refs = material.get("word_refs") or []
        if len(set(source_refs)) != len(source_refs) or len(set(word_refs)) != len(word_refs):
            accounting_errors.append("pdf_hybrid_source_ref_accounting_duplicate")
        if set(used_ids) != set(dictionary):
            accounting_errors.append("pdf_hybrid_candidate_accounting_incomplete")
        if material.get("omitted_candidate_ids"):
            accounting_errors.append("pdf_hybrid_candidate_omitted")
        gates["source_ref_candidate_accounting"] = _gate(
            not accounting_errors, accounting_errors
        )
        ambiguity_errors = []
        if binding_output.get("decision") != "bound":
            ambiguity_errors.append("pdf_hybrid_binding_not_bound")
        if binding_output.get("uncertainty_codes"):
            ambiguity_errors.append("pdf_hybrid_unresolved_uncertainty")
        gates["unresolved_ambiguity"] = _gate(not ambiguity_errors, ambiguity_errors)
        structural_errors = []
        signals = _object(classification.get("measured_signals"))
        if columns > 24 or rows > 64 or rows * columns > 1536:
            structural_errors.append("pdf_hybrid_shape_budget_exceeded")
        if signals.get("row_count_hint") and rows == 0:
            structural_errors.append("pdf_hybrid_deterministic_signal_conflict")
        gates["deterministic_signal_consistency"] = _gate(
            not structural_errors, structural_errors
        )
        placement_errors = []
        if independent_structural_validation is not None:
            if independent_structural_validation.get("passed") is not True:
                placement_errors.extend(
                    str(item)
                    for item in independent_structural_validation.get("reason_codes")
                    or ["pdf_hybrid_independent_structural_placement_failed"]
                )
        else:
            if signals.get("column_confidence") == "blocked" and signals.get(
                "wide_table"
            ):
                placement_errors.append(
                    "pdf_hybrid_wide_column_placement_not_independently_validated"
                )
            if signals.get("continuation_signal"):
                placement_errors.append(
                    "pdf_hybrid_continuation_placement_not_independently_validated"
                )
        gates["independent_structural_placement"] = _gate(
            not placement_errors, placement_errors
        )
        repeatability_errors = []
        if require_repeatability:
            if repeatability_validation is not None:
                if repeatability_validation.get("passed") is not True:
                    repeatability_errors.extend(
                        str(item)
                        for item in repeatability_validation.get("reason_codes")
                        or ["pdf_hybrid_non_repeatable_materialization"]
                    )
            elif repeated_materialization_checksum != material.get(
                "materialization_checksum"
            ):
                repeatability_errors.append("pdf_hybrid_non_repeatable_materialization")
        gates["repeatability"] = _gate(
            not repeatability_errors, repeatability_errors
        )
        all_errors = sorted(
            set(code for gate in gates.values() for code in gate["reason_codes"])
        )
        if binding_output.get("decision") == "unsupported":
            aggregate = "unsupported"
        elif binding_output.get("decision") == "ambiguous":
            aggregate = "human_review_required"
        elif placement_errors:
            aggregate = "human_review_required"
        elif all_errors:
            aggregate = "blocked"
        else:
            aggregate = "accepted_shadow"
        result = {
            "schema_version": PDF_TABLE_VALIDATION_SCHEMA,
            "validation_id": "pdfhybridval_"
            + stable_digest(
                [evidence_package.get("package_id"), sha256_json(binding_output)], length=24
            ),
            "package_id": evidence_package.get("package_id"),
            "binding_output_hash": sha256_json(binding_output),
            "materialization_checksum": material.get("materialization_checksum"),
            "aggregate_result": aggregate,
            "gates": gates,
            "reason_codes": all_errors,
            "metrics": {
                "rows": rows,
                "columns": columns,
                "grid_positions": rows * columns,
                "materialized_cells": len(cells),
                "explicit_empty_cells": empty_count,
                "selected_candidates": len(set(used_ids)),
                "source_value_refs": len(set(source_refs)),
                "word_refs": len(set(word_refs)),
            },
            "source_authenticity_validated": gates["exact_source_provenance"]["passed"],
            "structural_placement_validated": all(
                gates[name]["passed"]
                for name in (
                    "complete_rectangular_grid",
                    "explicit_empty_cell_coverage",
                    "header_hierarchy",
                    "deterministic_signal_consistency",
                    "independent_structural_placement",
                )
            ),
            "repeatability_required": require_repeatability,
            "repeatability_match": (
                repeatability_validation.get("passed")
                if repeatability_validation is not None and require_repeatability
                else repeated_materialization_checksum
                == material.get("materialization_checksum")
                if require_repeatability
                else None
            ),
            "authoritative": False,
            "production_gate2_selected": False,
        }
        result["validation_checksum"] = sha256_json(result)
        return result


def _gate(passed: bool, codes: list[str]) -> dict[str, Any]:
    return {"passed": passed, "reason_codes": sorted(set(codes))}


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
