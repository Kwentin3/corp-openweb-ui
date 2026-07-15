from __future__ import annotations

import copy
from typing import Any

from .contracts import stable_digest
from .pdf_dual_oracle_consensus import (
    PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA,
    PdfDualOracleConsensusFactory,
)
from .pdf_dual_oracle_contracts import PdfDualOracleContractFactory
from .pdf_hybrid_contracts import (
    PDF_TABLE_MATERIALIZATION_SCHEMA,
    sha256_json,
    validate_binding_output_shape,
)


PDF_CONTINUATION_MATERIALIZATION_SCHEMA = (
    "broker_reports_pdf_continuation_materialization_v1"
)
FACTORY_REQUIRED = (
    "PdfHybridMaterializationFactory.create is the only candidate materialization entrypoint"
)
FORBIDDEN = "Materializers must not accept free values, invented ids, or incomplete grids"
_FACTORY_TOKEN = object()

_FRAGMENT_MATERIALIZATION_KEYS = {
    "schema_version",
    "materialization_id",
    "package_id",
    "binding_output_hash",
    "crop_sha256",
    "candidate_dictionary_hash",
    "row_count",
    "column_count",
    "grid_positions",
    "rows",
    "cells",
    "header_rows",
    "header_hierarchy",
    "spans",
    "selected_candidate_ids",
    "omitted_candidate_ids",
    "extra_candidate_ids",
    "duplicate_candidate_ids",
    "source_value_refs",
    "word_refs",
    "explicit_empty_positions",
    "structural_provenance_conflicts",
    "model_invented_values_total",
    "placement_checksum",
    "materialization_checksum",
}
_CONTINUATION_MATERIALIZATION_KEYS = {
    "schema_version",
    "materialization_id",
    "continuation_group_id",
    "continuation_result_checksum",
    "canonical_joined_grid_checksum",
    "join_plan_checksum",
    "row_count",
    "column_count",
    "grid_positions",
    "ordered_table_refs",
    "fragment_offsets",
    "rows",
    "cells",
    "header_rows",
    "header_hierarchy",
    "spans",
    "deduplicated_boundary_rows",
    "source_candidate_ids",
    "selected_candidate_ids",
    "deduplicated_candidate_ids",
    "omitted_candidate_ids",
    "extra_candidate_ids",
    "duplicate_candidate_ids",
    "source_value_refs",
    "word_refs",
    "explicit_empty_positions",
    "candidate_ownership_exact",
    "structural_provenance_conflicts",
    "model_invented_values_total",
    "materialization_checksum",
}
_CONTINUATION_ROW_KEYS = {
    "row_ref",
    "row_ordinal",
    "row_kind",
    "fragment_order",
    "page_number",
    "table_ref",
    "source_row_ordinal",
    "source_row_ref",
}
_CONTINUATION_CELL_KEYS = {
    "cell_ref",
    "row_ref",
    "row_ordinal",
    "column_ordinal",
    "candidate_ids",
    "explicit_empty",
    "resolved_source_values",
    "source_value_refs",
    "word_refs",
    "uncertainty_codes",
    "fragment_order",
    "page_number",
    "table_ref",
    "source_cell_ref",
}
_FRAGMENT_OFFSET_KEYS = {
    "fragment_order",
    "page_number",
    "table_ref",
    "fragment_evidence_id",
    "fragment_evidence_checksum",
    "fragment_materialization_id",
    "fragment_materialization_checksum",
    "source_row_count",
    "joined_row_start",
    "joined_row_end",
    "row_offset",
    "deduplicated_source_row_ordinals",
}
_CONTINUATION_SPAN_KEYS = {
    "start_row",
    "end_row",
    "start_column",
    "end_column",
    "relation",
    "fragment_order",
    "page_number",
    "table_ref",
    "source_start_row",
    "source_end_row",
}
_CONTINUATION_HEADER_RELATION_KEYS = {
    "parent_row",
    "parent_column",
    "child_start_column",
    "child_end_column",
    "fragment_order",
    "page_number",
    "table_ref",
    "source_parent_row",
}
_CONTINUATION_DEDUPE_KEYS = {
    "table_ref",
    "fragment_order",
    "page_number",
    "source_row_ordinal",
    "row_content_checksum",
    "removed_candidate_ids",
    "kept_table_ref",
    "kept_fragment_order",
    "kept_page_number",
    "kept_source_row_ordinal",
    "kept_joined_row_ordinal",
    "fragment_evidence_id",
    "fragment_evidence_checksum",
    "fragment_materialization_id",
    "fragment_materialization_checksum",
    "source_row_ref",
    "source_cell_refs",
}


class PdfHybridMaterializationError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PdfHybridMaterializationFactory:
    def create(self) -> "PdfHybridMaterializationRuntime":
        return PdfHybridMaterializationRuntime(_factory_token=_FACTORY_TOKEN)


class PdfHybridMaterializationRuntime:
    def __init__(self, *, _factory_token: object | None = None) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise PdfHybridMaterializationError(
                "pdf_hybrid_materialization_factory_required"
            )

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

    def validate_materialization(self, value: Any) -> list[str]:
        """Validate a single-fragment materialization as a terminal contract.

        Materialization construction and terminal validation intentionally stay
        separate: shadow intake callers must prove the returned source-only grid
        before treating it as an accepted physical structure.
        """

        return _fragment_materialization_errors(value)

    def materialize_continuation(
        self,
        *,
        continuation_result: dict[str, Any],
        fragment_evidence: list[dict[str, Any]],
        fragment_materializations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        consensus_errors = (
            PdfDualOracleConsensusFactory()
            .create()
            .validate_continuation_result(continuation_result)
        )
        if consensus_errors:
            raise PdfHybridMaterializationError(consensus_errors[0])
        if (
            continuation_result.get("schema_version")
            != PDF_DUAL_ORACLE_CONTINUATION_RESULT_SCHEMA
            or continuation_result.get("terminal_status")
            != "accepted_supplied_consensus"
            or continuation_result.get("joined_coverage_complete") is not True
            or not continuation_result.get("join_plan_checksum")
        ):
            raise PdfHybridMaterializationError(
                "pdf_continuation_materialization_consensus_not_sealed"
            )
        if (
            not isinstance(fragment_evidence, list)
            or len(fragment_evidence) != 2
            or not all(isinstance(item, dict) for item in fragment_evidence)
            or not isinstance(fragment_materializations, list)
            or len(fragment_materializations) != 2
            or not all(isinstance(item, dict) for item in fragment_materializations)
        ):
            raise PdfHybridMaterializationError(
                "pdf_continuation_materialization_fragment_set_invalid"
            )

        ordered_fragments = _dicts(continuation_result.get("ordered_fragments"))
        contracts = PdfDualOracleContractFactory().create()
        contexts: list[dict[str, Any]] = []
        for index, (plan, evidence, materialization) in enumerate(
            zip(
                ordered_fragments,
                fragment_evidence,
                fragment_materializations,
            ),
            start=1,
        ):
            evidence_errors = contracts.validate_continuation_fragment_evidence(
                evidence
            )
            materialization_errors = _fragment_materialization_errors(
                materialization
            )
            if evidence_errors:
                raise PdfHybridMaterializationError(evidence_errors[0])
            if materialization_errors:
                raise PdfHybridMaterializationError(materialization_errors[0])
            if (
                plan.get("fragment_order") != index
                or evidence.get("fragment_order") != index
                or plan.get("page_number") != evidence.get("page_number")
                or plan.get("table_ref") != evidence.get("table_ref")
                or plan.get("repeated_header_policy")
                != evidence.get("repeated_header_policy")
                or plan.get("fragment_result_checksum")
                != evidence.get("consensus_result_checksum")
                or plan.get("fragment_evidence_checksum")
                != evidence.get("fragment_evidence_checksum")
                or plan.get("canonical_grid_checksum")
                != evidence.get("canonical_grid_checksum")
                or plan.get("binding_checksum") != evidence.get("binding_checksum")
                or materialization.get("binding_output_hash")
                != evidence.get("binding_checksum")
                or materialization.get("row_count") != evidence.get("row_count")
                or materialization.get("column_count")
                != evidence.get("column_count")
                or materialization.get("header_rows")
                != evidence.get("header_rows")
                or materialization.get("header_hierarchy")
                != evidence.get("header_hierarchy")
                or materialization.get("spans") != evidence.get("spans")
                or materialization.get("selected_candidate_ids")
                != sorted(str(item) for item in evidence.get("candidate_ids") or [])
            ):
                raise PdfHybridMaterializationError(
                    "pdf_continuation_materialization_fragment_crosslink_invalid"
                )
            rows_by_ordinal = {
                int(item.get("row_ordinal") or 0): item
                for item in _dicts(materialization.get("rows"))
            }
            cells_by_position = {
                (
                    int(item.get("row_ordinal") or 0),
                    int(item.get("column_ordinal") or 0),
                ): item
                for item in _dicts(materialization.get("cells"))
            }
            evidence_rows = {
                int(item.get("row_ordinal") or 0): item
                for item in _dicts(evidence.get("rows"))
            }
            for row_ordinal, evidence_row in evidence_rows.items():
                materialized_row = rows_by_ordinal.get(row_ordinal)
                materialized_source_cells = [
                    _object(cells_by_position.get((row_ordinal, column)))
                    for column in range(
                        1, int(evidence.get("column_count") or 0) + 1
                    )
                ]
                materialized_cells = [
                    source_cell.get("candidate_ids")
                    for source_cell in materialized_source_cells
                ]
                materialized_value_checksum_grid = [
                    [
                        sha256_json(value)
                        for value in source_cell.get("resolved_source_values") or []
                    ]
                    for source_cell in materialized_source_cells
                ]
                if (
                    not materialized_row
                    or materialized_row.get("row_kind")
                    != evidence_row.get("row_kind")
                    or materialized_cells != evidence_row.get("cells")
                    or sha256_json(materialized_value_checksum_grid)
                    != evidence_row.get("row_content_checksum")
                ):
                    raise PdfHybridMaterializationError(
                        "pdf_continuation_materialization_fragment_grid_mismatch"
                    )
            contexts.append(
                {
                    "plan": plan,
                    "evidence": evidence,
                    "materialization": materialization,
                    "rows_by_ordinal": rows_by_ordinal,
                    "cells_by_position": cells_by_position,
                    "evidence_rows": evidence_rows,
                }
            )

        context_by_order = {
            int(_object(context.get("plan")).get("fragment_order") or 0): context
            for context in contexts
        }
        group_id = str(continuation_result.get("continuation_group_id") or "")
        join_checksum = str(continuation_result.get("join_plan_checksum") or "")
        column_count = int(continuation_result.get("shared_column_count") or 0)
        rows: list[dict[str, Any]] = []
        cells: list[dict[str, Any]] = []
        joined_source_map: dict[tuple[int, int], int] = {}
        for joined in _dicts(continuation_result.get("joined_rows")):
            row_ordinal = int(joined.get("row_ordinal") or 0)
            fragment_order = int(joined.get("fragment_order") or 0)
            source_row_ordinal = int(joined.get("source_row_ordinal") or 0)
            context = _object(context_by_order.get(fragment_order))
            plan = _object(context.get("plan"))
            source_row = _object(
                _object(context.get("rows_by_ordinal")).get(source_row_ordinal)
            )
            evidence_row = _object(
                _object(context.get("evidence_rows")).get(source_row_ordinal)
            )
            if (
                not source_row
                or not evidence_row
                or joined.get("row_kind") != source_row.get("row_kind")
                or joined.get("cells") != evidence_row.get("cells")
                or joined.get("row_content_checksum")
                != evidence_row.get("row_content_checksum")
                or joined.get("page_number") != plan.get("page_number")
                or joined.get("table_ref") != plan.get("table_ref")
            ):
                raise PdfHybridMaterializationError(
                    "pdf_continuation_materialization_joined_row_mismatch"
                )
            joined_source_map[(fragment_order, source_row_ordinal)] = row_ordinal
            row_ref = "pdfcontinuationrow_" + stable_digest(
                [group_id, join_checksum, row_ordinal], length=24
            )
            rows.append(
                {
                    "row_ref": row_ref,
                    "row_ordinal": row_ordinal,
                    "row_kind": joined.get("row_kind"),
                    "fragment_order": fragment_order,
                    "page_number": plan.get("page_number"),
                    "table_ref": plan.get("table_ref"),
                    "source_row_ordinal": source_row_ordinal,
                    "source_row_ref": source_row.get("row_ref"),
                }
            )
            for column_ordinal in range(1, column_count + 1):
                source_cell = _object(
                    _object(context.get("cells_by_position")).get(
                        (source_row_ordinal, column_ordinal)
                    )
                )
                expected_candidate_ids = _object(evidence_row).get("cells")[
                    column_ordinal - 1
                ]
                if (
                    not source_cell
                    or source_cell.get("candidate_ids") != expected_candidate_ids
                ):
                    raise PdfHybridMaterializationError(
                        "pdf_continuation_materialization_source_cell_mismatch"
                    )
                cell_ref = "pdfcontinuationcell_" + stable_digest(
                    [group_id, join_checksum, row_ordinal, column_ordinal],
                    length=24,
                )
                cells.append(
                    {
                        "cell_ref": cell_ref,
                        "row_ref": row_ref,
                        "row_ordinal": row_ordinal,
                        "column_ordinal": column_ordinal,
                        "candidate_ids": copy.deepcopy(
                            source_cell.get("candidate_ids") or []
                        ),
                        "explicit_empty": source_cell.get("explicit_empty"),
                        "resolved_source_values": copy.deepcopy(
                            source_cell.get("resolved_source_values") or []
                        ),
                        "source_value_refs": copy.deepcopy(
                            source_cell.get("source_value_refs") or []
                        ),
                        "word_refs": copy.deepcopy(
                            source_cell.get("word_refs") or []
                        ),
                        "uncertainty_codes": copy.deepcopy(
                            source_cell.get("uncertainty_codes") or []
                        ),
                        "fragment_order": fragment_order,
                        "page_number": plan.get("page_number"),
                        "table_ref": plan.get("table_ref"),
                        "source_cell_ref": source_cell.get("cell_ref"),
                    }
                )

        deduplicated_boundary_rows: list[dict[str, Any]] = []
        deduplicated_candidate_ids: list[str] = []
        deduplicated_source_refs: list[str] = []
        deduplicated_word_refs: list[str] = []
        for deduplicated in _dicts(
            continuation_result.get("deduplicated_boundary_rows")
        ):
            fragment_order = int(deduplicated.get("fragment_order") or 0)
            source_row_ordinal = int(deduplicated.get("source_row_ordinal") or 0)
            context = _object(context_by_order.get(fragment_order))
            plan = _object(context.get("plan"))
            evidence = _object(context.get("evidence"))
            materialization = _object(context.get("materialization"))
            source_row = _object(
                _object(context.get("rows_by_ordinal")).get(source_row_ordinal)
            )
            source_cells = [
                _object(
                    _object(context.get("cells_by_position")).get(
                        (source_row_ordinal, column)
                    )
                )
                for column in range(1, column_count + 1)
            ]
            source_candidate_ids = [
                str(candidate_id)
                for source_cell in source_cells
                for candidate_id in source_cell.get("candidate_ids") or []
            ]
            if (
                not source_row
                or any(not source_cell for source_cell in source_cells)
                or source_candidate_ids
                != [str(item) for item in deduplicated.get("removed_candidate_ids") or []]
                or deduplicated.get("page_number") != plan.get("page_number")
                or deduplicated.get("table_ref") != plan.get("table_ref")
            ):
                raise PdfHybridMaterializationError(
                    "pdf_continuation_materialization_boundary_dedupe_mismatch"
                )
            deduplicated_candidate_ids.extend(source_candidate_ids)
            deduplicated_source_refs.extend(
                str(item)
                for source_cell in source_cells
                for item in source_cell.get("source_value_refs") or []
            )
            deduplicated_word_refs.extend(
                str(item)
                for source_cell in source_cells
                for item in source_cell.get("word_refs") or []
            )
            deduplicated_boundary_rows.append(
                {
                    **copy.deepcopy(deduplicated),
                    "fragment_evidence_id": evidence.get("fragment_evidence_id"),
                    "fragment_evidence_checksum": evidence.get(
                        "fragment_evidence_checksum"
                    ),
                    "fragment_materialization_id": materialization.get(
                        "materialization_id"
                    ),
                    "fragment_materialization_checksum": materialization.get(
                        "materialization_checksum"
                    ),
                    "source_row_ref": source_row.get("row_ref"),
                    "source_cell_refs": [
                        source_cell.get("cell_ref") for source_cell in source_cells
                    ],
                }
            )

        header_rows: list[int] = []
        header_hierarchy: list[dict[str, Any]] = []
        spans: list[dict[str, Any]] = []
        fragment_offsets: list[dict[str, Any]] = []
        for context in contexts:
            plan = _object(context.get("plan"))
            evidence = _object(context.get("evidence"))
            materialization = _object(context.get("materialization"))
            fragment_order = int(plan.get("fragment_order") or 0)
            source_row_count = int(evidence.get("row_count") or 0)
            joined_ordinals = [
                joined_source_map[(fragment_order, source_row)]
                for source_row in range(1, source_row_count + 1)
                if (fragment_order, source_row) in joined_source_map
            ]
            deduplicated_ordinals = [
                int(item.get("source_row_ordinal") or 0)
                for item in deduplicated_boundary_rows
                if item.get("fragment_order") == fragment_order
            ]
            if len(joined_ordinals) + len(deduplicated_ordinals) != source_row_count:
                raise PdfHybridMaterializationError(
                    "pdf_continuation_materialization_row_coverage_incomplete"
                )
            fragment_offsets.append(
                {
                    "fragment_order": fragment_order,
                    "page_number": plan.get("page_number"),
                    "table_ref": plan.get("table_ref"),
                    "fragment_evidence_id": evidence.get("fragment_evidence_id"),
                    "fragment_evidence_checksum": evidence.get(
                        "fragment_evidence_checksum"
                    ),
                    "fragment_materialization_id": materialization.get(
                        "materialization_id"
                    ),
                    "fragment_materialization_checksum": materialization.get(
                        "materialization_checksum"
                    ),
                    "source_row_count": source_row_count,
                    "joined_row_start": min(joined_ordinals)
                    if joined_ordinals
                    else None,
                    "joined_row_end": max(joined_ordinals)
                    if joined_ordinals
                    else None,
                    "row_offset": (
                        joined_ordinals[0]
                        - next(
                            source_row
                            for source_row in range(1, source_row_count + 1)
                            if (fragment_order, source_row) in joined_source_map
                        )
                        if joined_ordinals
                        else None
                    ),
                    "deduplicated_source_row_ordinals": deduplicated_ordinals,
                }
            )
            for source_header in evidence.get("header_rows") or []:
                mapped = joined_source_map.get((fragment_order, int(source_header)))
                if mapped is None:
                    raise PdfHybridMaterializationError(
                        "pdf_continuation_materialization_header_deduplicated"
                    )
                header_rows.append(mapped)
            for relation in _dicts(evidence.get("header_hierarchy")):
                source_parent_row = int(relation.get("parent_row") or 0)
                mapped = joined_source_map.get((fragment_order, source_parent_row))
                if mapped is None:
                    raise PdfHybridMaterializationError(
                        "pdf_continuation_materialization_header_offset_invalid"
                    )
                header_hierarchy.append(
                    {
                        **copy.deepcopy(relation),
                        "parent_row": mapped,
                        "fragment_order": fragment_order,
                        "page_number": plan.get("page_number"),
                        "table_ref": plan.get("table_ref"),
                        "source_parent_row": source_parent_row,
                    }
                )
            for span in _dicts(evidence.get("spans")):
                source_start = int(span.get("start_row") or 0)
                source_end = int(span.get("end_row") or 0)
                mapped_rows = [
                    joined_source_map.get((fragment_order, source_row))
                    for source_row in range(source_start, source_end + 1)
                ]
                if (
                    any(mapped is None for mapped in mapped_rows)
                    or mapped_rows
                    != list(range(int(mapped_rows[0]), int(mapped_rows[-1]) + 1))
                ):
                    raise PdfHybridMaterializationError(
                        "pdf_continuation_materialization_span_offset_invalid"
                    )
                spans.append(
                    {
                        **copy.deepcopy(span),
                        "start_row": mapped_rows[0],
                        "end_row": mapped_rows[-1],
                        "fragment_order": fragment_order,
                        "page_number": plan.get("page_number"),
                        "table_ref": plan.get("table_ref"),
                        "source_start_row": source_start,
                        "source_end_row": source_end,
                    }
                )

        selected_candidate_ids = [
            str(candidate_id)
            for cell in cells
            for candidate_id in cell.get("candidate_ids") or []
        ]
        source_candidate_ids = [
            str(candidate_id)
            for context in contexts
            for candidate_id in _object(context.get("evidence")).get("candidate_ids")
            or []
        ]
        if (
            len(source_candidate_ids) != len(set(source_candidate_ids))
            or len(selected_candidate_ids) != len(set(selected_candidate_ids))
            or len(deduplicated_candidate_ids)
            != len(set(deduplicated_candidate_ids))
            or set(selected_candidate_ids) & set(deduplicated_candidate_ids)
            or set(selected_candidate_ids) | set(deduplicated_candidate_ids)
            != set(source_candidate_ids)
        ):
            raise PdfHybridMaterializationError(
                "pdf_continuation_materialization_candidate_ownership_invalid"
            )
        source_value_refs = [
            str(item)
            for cell in cells
            for item in cell.get("source_value_refs") or []
        ] + deduplicated_source_refs
        word_refs = [
            str(item)
            for cell in cells
            for item in cell.get("word_refs") or []
        ] + deduplicated_word_refs
        result = {
            "schema_version": PDF_CONTINUATION_MATERIALIZATION_SCHEMA,
            "materialization_id": "pdfcontinuationmat_"
            + stable_digest(
                [group_id, continuation_result.get("result_checksum")], length=24
            ),
            "continuation_group_id": group_id,
            "continuation_result_checksum": continuation_result.get(
                "result_checksum"
            ),
            "canonical_joined_grid_checksum": continuation_result.get(
                "canonical_joined_grid_checksum"
            ),
            "join_plan_checksum": join_checksum,
            "row_count": len(rows),
            "column_count": column_count,
            "grid_positions": len(rows) * column_count,
            "ordered_table_refs": copy.deepcopy(
                continuation_result.get("ordered_table_refs") or []
            ),
            "fragment_offsets": fragment_offsets,
            "rows": rows,
            "cells": cells,
            "header_rows": sorted(header_rows),
            "header_hierarchy": header_hierarchy,
            "spans": spans,
            "deduplicated_boundary_rows": deduplicated_boundary_rows,
            "source_candidate_ids": sorted(source_candidate_ids),
            "selected_candidate_ids": sorted(selected_candidate_ids),
            "deduplicated_candidate_ids": sorted(deduplicated_candidate_ids),
            "omitted_candidate_ids": [],
            "extra_candidate_ids": [],
            "duplicate_candidate_ids": [],
            "source_value_refs": sorted(set(source_value_refs)),
            "word_refs": sorted(set(word_refs)),
            "explicit_empty_positions": [
                [cell["row_ordinal"], cell["column_ordinal"]]
                for cell in cells
                if cell["explicit_empty"]
            ],
            "candidate_ownership_exact": True,
            "structural_provenance_conflicts": [],
            "model_invented_values_total": 0,
        }
        result["materialization_checksum"] = sha256_json(result)
        result_errors = self.validate_continuation_materialization(result)
        if result_errors:
            raise PdfHybridMaterializationError(result_errors[0])
        return result

    def validate_continuation_materialization(self, value: Any) -> list[str]:
        return _continuation_materialization_errors(value)


PdfHybridMaterializer = PdfHybridMaterializationRuntime


def _fragment_materialization_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["pdf_continuation_fragment_materialization_not_object"]
    data = value
    errors: list[str] = []
    if (
        set(data) != _FRAGMENT_MATERIALIZATION_KEYS
        or data.get("schema_version") != PDF_TABLE_MATERIALIZATION_SCHEMA
    ):
        errors.append("pdf_continuation_fragment_materialization_contract_invalid")
    checksum_copy = dict(data)
    stored_checksum = checksum_copy.pop("materialization_checksum", None)
    if stored_checksum != sha256_json(checksum_copy):
        errors.append("pdf_continuation_fragment_materialization_checksum_invalid")
    rows = _dicts(data.get("rows"))
    cells = _dicts(data.get("cells"))
    row_count = data.get("row_count")
    column_count = data.get("column_count")
    if (
        not isinstance(row_count, int)
        or isinstance(row_count, bool)
        or row_count < 1
        or not isinstance(column_count, int)
        or isinstance(column_count, bool)
        or column_count < 1
        or len(rows) != row_count
        or len(cells) != row_count * column_count
        or data.get("grid_positions") != row_count * column_count
    ):
        errors.append("pdf_continuation_fragment_materialization_shape_invalid")
    if any(
        set(row) != {"row_ref", "row_ordinal", "row_kind"}
        or row.get("row_ordinal") != ordinal
        or not row.get("row_ref")
        for ordinal, row in enumerate(rows, start=1)
    ):
        errors.append("pdf_continuation_fragment_materialization_row_invalid")
    expected_positions = {
        (row, column)
        for row in range(1, int(row_count or 0) + 1)
        for column in range(1, int(column_count or 0) + 1)
    }
    actual_positions: set[tuple[int, int]] = set()
    used: list[str] = []
    for cell in cells:
        if set(cell) != {
            "cell_ref",
            "row_ref",
            "row_ordinal",
            "column_ordinal",
            "candidate_ids",
            "explicit_empty",
            "resolved_source_values",
            "source_value_refs",
            "word_refs",
            "uncertainty_codes",
        }:
            errors.append("pdf_continuation_fragment_materialization_cell_invalid")
            continue
        position = (
            int(cell.get("row_ordinal") or 0),
            int(cell.get("column_ordinal") or 0),
        )
        actual_positions.add(position)
        candidate_ids = cell.get("candidate_ids")
        if (
            not isinstance(candidate_ids, list)
            or not all(isinstance(item, str) and item for item in candidate_ids)
            or cell.get("explicit_empty") is not (not candidate_ids)
            or not isinstance(cell.get("resolved_source_values"), list)
            or len(cell.get("resolved_source_values") or []) != len(candidate_ids)
            or not isinstance(cell.get("source_value_refs"), list)
            or not isinstance(cell.get("word_refs"), list)
            or cell.get("uncertainty_codes") != []
        ):
            errors.append("pdf_continuation_fragment_materialization_cell_invalid")
        used.extend(str(item) for item in candidate_ids or [])
    selected = [str(item) for item in data.get("selected_candidate_ids") or []]
    if (
        actual_positions != expected_positions
        or len(actual_positions) != len(cells)
        or sorted(used) != selected
        or len(used) != len(set(used))
        or data.get("omitted_candidate_ids") != []
        or data.get("extra_candidate_ids") != []
        or data.get("duplicate_candidate_ids") != []
        or data.get("structural_provenance_conflicts") != []
        or data.get("model_invented_values_total") != 0
    ):
        errors.append("pdf_continuation_fragment_materialization_coverage_invalid")
    placement_projection = {
        "row_count": row_count,
        "column_count": column_count,
        "rows": [
            {
                "row_ordinal": item.get("row_ordinal"),
                "row_kind": item.get("row_kind"),
            }
            for item in rows
        ],
        "cells": [
            {
                "row_ordinal": item.get("row_ordinal"),
                "column_ordinal": item.get("column_ordinal"),
                "candidate_ids": item.get("candidate_ids"),
                "explicit_empty": item.get("explicit_empty"),
            }
            for item in cells
        ],
        "header_rows": data.get("header_rows"),
        "header_hierarchy": data.get("header_hierarchy"),
        "spans": data.get("spans"),
    }
    if data.get("placement_checksum") != sha256_json(placement_projection):
        errors.append(
            "pdf_continuation_fragment_materialization_placement_checksum_invalid"
        )
    return sorted(set(errors))


def _continuation_materialization_errors(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["pdf_continuation_materialization_not_object"]
    data = value
    errors: list[str] = []
    if (
        set(data) != _CONTINUATION_MATERIALIZATION_KEYS
        or data.get("schema_version") != PDF_CONTINUATION_MATERIALIZATION_SCHEMA
    ):
        errors.append("pdf_continuation_materialization_contract_invalid")
    checksum_copy = dict(data)
    stored_checksum = checksum_copy.pop("materialization_checksum", None)
    if stored_checksum != sha256_json(checksum_copy):
        errors.append("pdf_continuation_materialization_checksum_invalid")
    row_count = data.get("row_count")
    column_count = data.get("column_count")
    rows = _dicts(data.get("rows"))
    cells = _dicts(data.get("cells"))
    if (
        not isinstance(row_count, int)
        or isinstance(row_count, bool)
        or row_count < 1
        or not isinstance(column_count, int)
        or isinstance(column_count, bool)
        or column_count < 1
        or len(rows) != row_count
        or len(cells) != row_count * column_count
        or data.get("grid_positions") != row_count * column_count
        or not isinstance(data.get("ordered_table_refs"), list)
        or len(data.get("ordered_table_refs") or []) != 2
        or len(set(data.get("ordered_table_refs") or [])) != 2
    ):
        errors.append("pdf_continuation_materialization_shape_invalid")
    if any(
        set(row) != _CONTINUATION_ROW_KEYS
        or row.get("row_ordinal") != ordinal
        or not row.get("row_ref")
        or row.get("fragment_order") not in {1, 2}
        or not isinstance(row.get("source_row_ordinal"), int)
        or row.get("source_row_ordinal") < 1
        for ordinal, row in enumerate(rows, start=1)
    ):
        errors.append("pdf_continuation_materialization_row_invalid")
    row_refs = {int(row.get("row_ordinal") or 0): row.get("row_ref") for row in rows}
    expected_positions = {
        (row, column)
        for row in range(1, int(row_count or 0) + 1)
        for column in range(1, int(column_count or 0) + 1)
    }
    actual_positions: set[tuple[int, int]] = set()
    used: list[str] = []
    for cell in cells:
        if set(cell) != _CONTINUATION_CELL_KEYS:
            errors.append("pdf_continuation_materialization_cell_invalid")
            continue
        position = (
            int(cell.get("row_ordinal") or 0),
            int(cell.get("column_ordinal") or 0),
        )
        actual_positions.add(position)
        candidate_ids = cell.get("candidate_ids")
        if (
            not isinstance(candidate_ids, list)
            or not all(isinstance(item, str) and item for item in candidate_ids)
            or cell.get("explicit_empty") is not (not candidate_ids)
            or cell.get("row_ref") != row_refs.get(position[0])
            or not isinstance(cell.get("resolved_source_values"), list)
            or len(cell.get("resolved_source_values") or []) != len(candidate_ids)
            or not isinstance(cell.get("source_value_refs"), list)
            or not isinstance(cell.get("word_refs"), list)
            or cell.get("uncertainty_codes") != []
            or cell.get("fragment_order") not in {1, 2}
            or not cell.get("source_cell_ref")
        ):
            errors.append("pdf_continuation_materialization_cell_invalid")
        used.extend(str(item) for item in candidate_ids or [])
    selected = [str(item) for item in data.get("selected_candidate_ids") or []]
    source = [str(item) for item in data.get("source_candidate_ids") or []]
    deduplicated = [
        str(item) for item in data.get("deduplicated_candidate_ids") or []
    ]
    if (
        actual_positions != expected_positions
        or len(actual_positions) != len(cells)
        or sorted(used) != selected
        or len(used) != len(set(used))
        or len(deduplicated) != len(set(deduplicated))
        or set(selected) & set(deduplicated)
        or set(selected) | set(deduplicated) != set(source)
        or len(source) != len(set(source))
        or data.get("omitted_candidate_ids") != []
        or data.get("extra_candidate_ids") != []
        or data.get("duplicate_candidate_ids") != []
        or data.get("candidate_ownership_exact") is not True
        or data.get("structural_provenance_conflicts") != []
        or data.get("model_invented_values_total") != 0
    ):
        errors.append("pdf_continuation_materialization_coverage_invalid")
    offsets = _dicts(data.get("fragment_offsets"))
    if (
        len(offsets) != 2
        or any(set(item) != _FRAGMENT_OFFSET_KEYS for item in offsets)
        or [item.get("fragment_order") for item in offsets] != [1, 2]
        or [item.get("table_ref") for item in offsets]
        != data.get("ordered_table_refs")
    ):
        errors.append("pdf_continuation_materialization_offset_invalid")
    if any(
        set(item) != _CONTINUATION_SPAN_KEYS for item in _dicts(data.get("spans"))
    ):
        errors.append("pdf_continuation_materialization_span_invalid")
    if any(
        set(item) != _CONTINUATION_HEADER_RELATION_KEYS
        for item in _dicts(data.get("header_hierarchy"))
    ):
        errors.append("pdf_continuation_materialization_header_invalid")
    dedupe_rows = _dicts(data.get("deduplicated_boundary_rows"))
    if (
        any(set(item) != _CONTINUATION_DEDUPE_KEYS for item in dedupe_rows)
        or sorted(
            str(candidate_id)
            for item in dedupe_rows
            for candidate_id in item.get("removed_candidate_ids") or []
        )
        != sorted(deduplicated)
    ):
        errors.append("pdf_continuation_materialization_dedupe_invalid")
    explicit_empty_positions = sorted(
        [cell["row_ordinal"], cell["column_ordinal"]]
        for cell in cells
        if cell.get("explicit_empty") is True
    )
    if sorted(data.get("explicit_empty_positions") or []) != explicit_empty_positions:
        errors.append("pdf_continuation_materialization_empty_position_invalid")
    return sorted(set(errors))


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )
