from __future__ import annotations

from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import (
    PDF_TABLE_MATERIALIZATION_SCHEMA,
    sha256_json,
    validate_binding_output_shape,
)


FACTORY_REQUIRED = (
    "PdfHybridMaterializationFactory.create is the only candidate materialization entrypoint"
)
FORBIDDEN = "Materializers must not accept free values, invented ids, or incomplete grids"


class PdfHybridMaterializationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PdfHybridMaterializationFactory:
    def create(self) -> "PdfHybridMaterializer":
        return PdfHybridMaterializer()


class PdfHybridMaterializer:
    def materialize(
        self,
        *,
        evidence_package: dict[str, Any],
        binding_output: dict[str, Any],
    ) -> dict[str, Any]:
        shape_errors = validate_binding_output_shape(binding_output)
        if shape_errors:
            raise PdfHybridMaterializationError(shape_errors[0])
        if binding_output.get("decision") != "bound":
            raise PdfHybridMaterializationError("pdf_hybrid_binding_not_bound")
        if (
            binding_output.get("package_id") != evidence_package.get("package_id")
            or binding_output.get("crop_sha256")
            != _object(evidence_package.get("crop_identity")).get("crop_sha256")
            or binding_output.get("candidate_dictionary_hash")
            != evidence_package.get("candidate_dictionary_hash")
        ):
            raise PdfHybridMaterializationError("pdf_hybrid_materialization_identity_mismatch")
        dictionary = _object(evidence_package.get("private_candidate_dictionary"))
        cells: list[dict[str, Any]] = []
        used: list[str] = []
        source_value_refs: list[str] = []
        word_refs: list[str] = []
        conflicts: list[str] = []
        rows: list[dict[str, Any]] = []
        for row in binding_output.get("rows") or []:
            row_ordinal = int(row["row_ordinal"])
            row_ref = "pdfhybridrow_" + stable_digest(
                [evidence_package["package_id"], row_ordinal], length=24
            )
            rows.append(
                {
                    "row_ref": row_ref,
                    "row_ordinal": row_ordinal,
                    "row_kind": row["row_kind"],
                }
            )
            for column_ordinal, cell in enumerate(row["cells"], start=1):
                candidate_ids = list(cell)
                resolved = []
                for candidate_id in candidate_ids:
                    candidate = dictionary.get(candidate_id)
                    if not isinstance(candidate, dict):
                        conflicts.append("pdf_hybrid_candidate_id_unresolved")
                        continue
                    resolved.append(candidate.get("exact_source_span"))
                    source_value_refs.extend(
                        str(item) for item in candidate.get("source_value_refs") or [] if item
                    )
                    word_refs.extend(
                        str(item) for item in candidate.get("word_refs") or [] if item
                    )
                    used.append(candidate_id)
                cell_ref = "pdfhybridcell_" + stable_digest(
                    [evidence_package["package_id"], row_ordinal, column_ordinal],
                    length=24,
                )
                cells.append(
                    {
                        "cell_ref": cell_ref,
                        "row_ref": row_ref,
                        "row_ordinal": row_ordinal,
                        "column_ordinal": column_ordinal,
                        "candidate_ids": candidate_ids,
                        "explicit_empty": not candidate_ids,
                        "resolved_source_values": resolved,
                        "source_value_refs": [
                            ref
                            for candidate_id in candidate_ids
                            for ref in _object(dictionary.get(candidate_id)).get(
                                "source_value_refs"
                            )
                            or []
                        ],
                        "word_refs": [
                            ref
                            for candidate_id in candidate_ids
                            for ref in _object(dictionary.get(candidate_id)).get("word_refs")
                            or []
                        ],
                        "uncertainty_codes": [],
                    }
                )
        duplicates = sorted(
            candidate_id for candidate_id in set(used) if used.count(candidate_id) > 1
        )
        if "pdf_hybrid_candidate_id_unresolved" in conflicts:
            raise PdfHybridMaterializationError("pdf_hybrid_candidate_id_unresolved")
        if duplicates:
            conflicts.append("pdf_hybrid_candidate_duplicate_use")
        all_ids = set(dictionary)
        selected = set(used)
        result = {
            "schema_version": PDF_TABLE_MATERIALIZATION_SCHEMA,
            "materialization_id": "pdfhybridmat_"
            + stable_digest(
                [evidence_package["package_id"], sha256_json(binding_output)], length=24
            ),
            "package_id": evidence_package["package_id"],
            "binding_output_hash": sha256_json(binding_output),
            "crop_sha256": binding_output["crop_sha256"],
            "candidate_dictionary_hash": binding_output["candidate_dictionary_hash"],
            "row_count": int(binding_output["row_count"]),
            "column_count": int(binding_output["column_count"]),
            "grid_positions": int(binding_output["row_count"])
            * int(binding_output["column_count"]),
            "rows": rows,
            "cells": cells,
            "header_rows": list(binding_output.get("header_rows") or []),
            "header_hierarchy": list(binding_output.get("header_hierarchy") or []),
            "spans": list(binding_output.get("spans") or []),
            "selected_candidate_ids": sorted(selected),
            "omitted_candidate_ids": sorted(all_ids - selected),
            "extra_candidate_ids": sorted(selected - all_ids),
            "duplicate_candidate_ids": duplicates,
            "source_value_refs": sorted(set(source_value_refs)),
            "word_refs": sorted(set(word_refs)),
            "explicit_empty_positions": [
                [item["row_ordinal"], item["column_ordinal"]]
                for item in cells
                if item["explicit_empty"]
            ],
            "structural_provenance_conflicts": sorted(set(conflicts)),
            "model_invented_values_total": 0,
        }
        result["placement_checksum"] = sha256_json(
            {
                "row_count": result["row_count"],
                "column_count": result["column_count"],
                "rows": [
                    {
                        "row_ordinal": item["row_ordinal"],
                        "row_kind": item["row_kind"],
                    }
                    for item in rows
                ],
                "cells": [
                    {
                        "row_ordinal": item["row_ordinal"],
                        "column_ordinal": item["column_ordinal"],
                        "candidate_ids": item["candidate_ids"],
                        "explicit_empty": item["explicit_empty"],
                    }
                    for item in cells
                ],
                "header_rows": result["header_rows"],
                "header_hierarchy": result["header_hierarchy"],
                "spans": result["spans"],
            }
        )
        result["materialization_checksum"] = sha256_json(result)
        return result


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
