from __future__ import annotations

import re
from typing import Any

from .contracts import stable_digest
from .pdf_hybrid_contracts import sha256_json


PDF_SEMANTIC_HEADER_PROJECTION_SCHEMA = (
    "broker_reports_pdf_semantic_header_projection_v1"
)
PDF_SEMANTIC_HEADER_POLICY_VERSION = "pdf_semantic_header_projection_policy_v1"
PDF_SEMANTIC_HEADER_CONFIGURATION_SCHEMA = (
    "broker_reports_pdf_semantic_header_projection_configuration_v1"
)
SEMANTIC_CURRENCY_CODE_POLICY_VERSION = "semantic_currency_code_allowlist_v1"
SEMANTIC_UNIT_CODE_POLICY_VERSION = "semantic_unit_code_allowlist_v1"
SEMANTIC_CURRENCY_CODE_ALLOWLIST = frozenset(
    {
        "AUD",
        "CAD",
        "CHF",
        "CNY",
        "EUR",
        "GBP",
        "HKD",
        "JPY",
        "NZD",
        "RUB",
        "SGD",
        "USD",
    }
)
SEMANTIC_UNIT_CODE_ALLOWLIST = frozenset({"kg", "pcs", "shares"})
MAX_SEMANTIC_CONTEXT_BYTES = 48 * 1024
MAX_SEMANTIC_PHYSICAL_ALTERNATIVES = 8
MAX_SEMANTIC_REPRESENTATIVE_ROWS = 3

SEMANTIC_HEADER_VOCABULARY = {
    "description",
    "entity",
    "date",
    "period",
    "amount",
    "currency",
    "unit",
    "quantity",
    "percentage",
    "total_or_subtotal",
    "group_header",
    "leaf_header",
    "unknown",
}
QUALIFIER_KINDS = {"currency", "unit"}
QUALIFIER_SCOPES = {"cell", "row", "column", "table", "unknown"}
PHYSICAL_TOPOLOGY_STATUSES = {
    "accepted_supplied_consensus",
    "ambiguous_multiple_consensus",
}
PROJECTION_STATUSES = {"projected", "incomplete"}
ALTERNATIVE_PROJECTION_STATUSES = {
    "projected",
    "context_budget_exceeded",
    "alternative_budget_exceeded",
    "representative_sample_incomplete",
    "qualifier_binding_incomplete",
}
SEMANTIC_EQUIVALENCE_STATUSES = {
    "not_applicable",
    "equivalent",
    "different",
    "incomplete",
}
LOGICAL_TYPES = SEMANTIC_HEADER_VOCABULARY | {"monetary_amount"}

_TOP_KEYS = {
    "schema_version",
    "policy_version",
    "projection_id",
    "physical_topology_status",
    "physical_ambiguity_preserved",
    "physical_alternatives",
    "projection_status",
    "semantic_equivalence_status",
    "semantic_equivalence_scope",
    "semantic_equivalence_does_not_select_topology",
    "reason_codes",
    "input_hash",
    "structural_result_checksum",
    "configuration",
    "configuration_checksum",
    "source_value_change_allowed",
    "geometry_change_allowed",
    "physical_cell_change_allowed",
    "reference_answer_used",
    "authority_state",
    "production_gate2_selection_changed",
    "projection_checksum",
}
_ALTERNATIVE_KEYS = {
    "grid_checksum",
    "projection_status",
    "reason_codes",
    "context_bytes",
    "physical_columns",
    "semantic_fields",
    "qualifiers",
    "mapped_physical_column_ids",
    "unmapped_physical_column_ids",
    "logical_schema_signature",
}
_FIELD_KEYS = {
    "field_id",
    "role",
    "logical_type",
    "physical_column_ids",
    "header_cell_refs",
    "header_span_refs",
    "header_atom_ids",
    "qualifier_refs",
}
_QUALIFIER_KEYS = {
    "qualifier_id",
    "kind",
    "scope",
    "measure_field_id",
    "physical_column_ids",
    "evidence_cell_refs",
    "evidence_atom_ids",
    "normalized_code",
}
_PHYSICAL_COLUMN_KEYS = {"physical_column_id", "column_ordinal"}
_PHYSICAL_ALTERNATIVE_KEYS = {
    "grid_checksum",
    "row_count",
    "column_count",
    "header_rows",
    "header_hierarchy",
    "spans",
    "rows",
    "cells",
}
_CONFIGURATION_KEYS = {
    "schema_version",
    "policy_version",
    "currency_code_policy_version",
    "unit_code_policy_version",
    "max_context_bytes",
    "max_physical_alternatives",
    "max_representative_rows",
}


def semantic_header_configuration(
    *,
    policy_version: str,
    max_context_bytes: int,
    max_physical_alternatives: int,
    max_representative_rows: int,
) -> dict[str, Any]:
    return {
        "schema_version": PDF_SEMANTIC_HEADER_CONFIGURATION_SCHEMA,
        "policy_version": policy_version,
        "currency_code_policy_version": (
            SEMANTIC_CURRENCY_CODE_POLICY_VERSION
        ),
        "unit_code_policy_version": SEMANTIC_UNIT_CODE_POLICY_VERSION,
        "max_context_bytes": max_context_bytes,
        "max_physical_alternatives": max_physical_alternatives,
        "max_representative_rows": max_representative_rows,
    }


def physical_column_id(grid_checksum: str, column_ordinal: int) -> str:
    if not isinstance(grid_checksum, str) or not grid_checksum:
        raise ValueError("pdf_semantic_header_grid_checksum_invalid")
    if not isinstance(column_ordinal, int) or isinstance(column_ordinal, bool):
        raise ValueError("pdf_semantic_header_column_ordinal_invalid")
    if column_ordinal < 1:
        raise ValueError("pdf_semantic_header_column_ordinal_invalid")
    digest = stable_digest(
        [PDF_SEMANTIC_HEADER_PROJECTION_SCHEMA, grid_checksum, column_ordinal],
        length=24,
    )
    return f"pdfsemanticcol_{digest}"


def physical_span_id(grid_checksum: str, span: dict[str, Any]) -> str:
    coordinates = (
        span.get("start_row"),
        span.get("end_row"),
        span.get("start_column"),
        span.get("end_column"),
        span.get("relation"),
    )
    digest = stable_digest(
        [PDF_SEMANTIC_HEADER_PROJECTION_SCHEMA, grid_checksum, *coordinates],
        length=24,
    )
    return f"pdfsemanticspan_{digest}"


def validate_semantic_header_projection(
    value: object,
    *,
    physical_alternatives: list[dict[str, Any]] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["pdf_semantic_header_projection_not_object"]
    if set(value) != _TOP_KEYS:
        errors.append("pdf_semantic_header_projection_keys_invalid")
        return errors
    if value.get("schema_version") != PDF_SEMANTIC_HEADER_PROJECTION_SCHEMA:
        errors.append("pdf_semantic_header_projection_schema_invalid")
    if value.get("policy_version") != PDF_SEMANTIC_HEADER_POLICY_VERSION:
        errors.append("pdf_semantic_header_projection_policy_invalid")
    if value.get("physical_topology_status") not in PHYSICAL_TOPOLOGY_STATUSES:
        errors.append("pdf_semantic_header_physical_topology_status_invalid")
    if value.get("projection_status") not in PROJECTION_STATUSES:
        errors.append("pdf_semantic_header_projection_status_invalid")
    if value.get("semantic_equivalence_status") not in SEMANTIC_EQUIVALENCE_STATUSES:
        errors.append("pdf_semantic_header_equivalence_status_invalid")
    if value.get("semantic_equivalence_scope") != "logical_field_roles_only":
        errors.append("pdf_semantic_header_equivalence_scope_invalid")
    expected_ambiguous = value.get("physical_topology_status") == (
        "ambiguous_multiple_consensus"
    )
    if value.get("physical_ambiguity_preserved") is not expected_ambiguous:
        errors.append("pdf_semantic_header_physical_ambiguity_flag_invalid")
    if value.get("semantic_equivalence_does_not_select_topology") is not True:
        errors.append("pdf_semantic_header_selection_guard_invalid")
    for key in (
        "source_value_change_allowed",
        "geometry_change_allowed",
        "physical_cell_change_allowed",
        "reference_answer_used",
        "production_gate2_selection_changed",
    ):
        if value.get(key) is not False:
            errors.append(f"pdf_semantic_header_{key}_invalid")
    if value.get("authority_state") != "non_authoritative":
        errors.append("pdf_semantic_header_authority_state_invalid")
    if not _nonempty_string(value.get("projection_id")):
        errors.append("pdf_semantic_header_projection_id_invalid")
    if not _sha256(value.get("input_hash")):
        errors.append("pdf_semantic_header_input_hash_invalid")
    if not _sha256(value.get("structural_result_checksum")):
        errors.append("pdf_semantic_header_structural_result_checksum_invalid")
    configuration = value.get("configuration")
    errors.extend(_validate_configuration(configuration))
    configuration_checksum = value.get("configuration_checksum")
    if not _sha256(configuration_checksum):
        errors.append("pdf_semantic_header_configuration_checksum_invalid")
    elif isinstance(configuration, dict) and configuration_checksum != sha256_json(
        configuration
    ):
        errors.append("pdf_semantic_header_configuration_checksum_mismatch")
    if isinstance(configuration, dict) and configuration.get(
        "policy_version"
    ) != value.get("policy_version"):
        errors.append("pdf_semantic_header_configuration_policy_mismatch")
    if not _sorted_unique_strings(value.get("reason_codes")):
        errors.append("pdf_semantic_header_reason_codes_invalid")

    projected_alternatives = value.get("physical_alternatives")
    if not isinstance(projected_alternatives, list) or not projected_alternatives:
        errors.append("pdf_semantic_header_alternatives_invalid")
        projected_alternatives = []
    source_by_grid: dict[str, dict[str, Any]] = {}
    if physical_alternatives is None:
        errors.append("pdf_semantic_header_physical_alternatives_required")
    elif not isinstance(physical_alternatives, list):
        errors.append("pdf_semantic_header_physical_alternatives_invalid")
    else:
        source_by_grid = {
            str(item.get("grid_checksum")): item
            for item in physical_alternatives
            if isinstance(item, dict)
        }
        if len(projected_alternatives) != len(physical_alternatives):
            errors.append("pdf_semantic_header_alternative_count_mismatch")
        expected_input_hash = sha256_json(
            {
                "physical_topology_status": value.get(
                    "physical_topology_status"
                ),
                "physical_alternatives": physical_alternatives,
            }
        )
        if value.get("input_hash") != expected_input_hash:
            errors.append("pdf_semantic_header_input_hash_mismatch")

    for projected in projected_alternatives:
        source = None
        if isinstance(projected, dict):
            source = source_by_grid.get(str(projected.get("grid_checksum")))
        errors.extend(_validate_alternative(projected, source))

    expected_projected_status = bool(projected_alternatives) and all(
        isinstance(projected, dict)
        and projected.get("projection_status") == "projected"
        and not projected.get("unmapped_physical_column_ids")
        and not any(
            isinstance(field, dict) and field.get("role") == "unknown"
            for field in projected.get("semantic_fields") or []
        )
        for projected in projected_alternatives
    )
    expected_top_status = (
        "projected" if expected_projected_status else "incomplete"
    )
    if value.get("projection_status") != expected_top_status:
        errors.append("pdf_semantic_header_projection_status_inconsistent")

    if expected_ambiguous and len(projected_alternatives) < 2:
        errors.append("pdf_semantic_header_ambiguous_alternatives_missing")
    if not expected_ambiguous and len(projected_alternatives) != 1:
        errors.append("pdf_semantic_header_accepted_alternative_count_invalid")

    expected_projection_id = "pdfsemanticprojection_" + stable_digest(
        [
            PDF_SEMANTIC_HEADER_PROJECTION_SCHEMA,
            value.get("policy_version"),
            value.get("structural_result_checksum"),
            value.get("configuration_checksum"),
            value.get("input_hash"),
        ],
        length=24,
    )
    if value.get("projection_id") != expected_projection_id:
        errors.append("pdf_semantic_header_projection_id_mismatch")

    checksum_value = value.get("projection_checksum")
    unsigned = dict(value)
    unsigned.pop("projection_checksum", None)
    if checksum_value != sha256_json(unsigned):
        errors.append("pdf_semantic_header_projection_checksum_mismatch")
    return sorted(set(errors))


def validate_physical_alternative_shape(value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["pdf_semantic_header_physical_alternative_not_object"]
    if set(value) != _PHYSICAL_ALTERNATIVE_KEYS:
        return ["pdf_semantic_header_physical_alternative_keys_invalid"]
    errors: list[str] = []
    grid_checksum = value.get("grid_checksum")
    if not _sha256(grid_checksum):
        errors.append("pdf_semantic_header_grid_checksum_invalid")
    row_count = value.get("row_count")
    column_count = value.get("column_count")
    if not _bounded_int(row_count, maximum=256):
        errors.append("pdf_semantic_header_row_count_invalid")
    if not _bounded_int(column_count, maximum=64):
        errors.append("pdf_semantic_header_column_count_invalid")
    if errors:
        return sorted(set(errors))
    assert isinstance(row_count, int)
    assert isinstance(column_count, int)

    header_rows = value.get("header_rows")
    if (
        not isinstance(header_rows, list)
        or not all(_bounded_int(item, maximum=row_count) for item in header_rows)
        or header_rows != sorted(set(header_rows))
    ):
        errors.append("pdf_semantic_header_header_rows_invalid")
    rows = value.get("rows")
    if not isinstance(rows, list) or len(rows) != row_count:
        errors.append("pdf_semantic_header_rows_invalid")
    else:
        expected_ordinals = list(range(1, row_count + 1))
        ordinals: list[int] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"row_ordinal", "row_kind"}:
                errors.append("pdf_semantic_header_row_invalid")
                continue
            ordinal = row.get("row_ordinal")
            if not isinstance(ordinal, int) or isinstance(ordinal, bool):
                errors.append("pdf_semantic_header_row_ordinal_invalid")
                continue
            ordinals.append(ordinal)
            if row.get("row_kind") not in {
                "header",
                "column_numbers",
                "data",
                "section",
                "subtotal",
                "total",
                "unknown",
            }:
                errors.append("pdf_semantic_header_row_kind_invalid")
        if ordinals != expected_ordinals:
            errors.append("pdf_semantic_header_row_ordinals_invalid")

    cells = value.get("cells")
    expected_cell_count = row_count * column_count
    cell_positions: list[tuple[int, int]] = []
    candidate_ids: list[str] = []
    cell_refs: list[str] = []
    if not isinstance(cells, list) or len(cells) != expected_cell_count:
        errors.append("pdf_semantic_header_cells_invalid")
    else:
        for cell in cells:
            cell_errors = _validate_physical_cell(cell, row_count, column_count)
            errors.extend(cell_errors)
            if not cell_errors and isinstance(cell, dict):
                cell_positions.append(
                    (int(cell["row_ordinal"]), int(cell["column_ordinal"]))
                )
                cell_refs.append(str(cell["cell_ref"]))
                candidate_ids.extend(str(item) for item in cell["candidate_ids"])
        expected_positions = [
            (row, column)
            for row in range(1, row_count + 1)
            for column in range(1, column_count + 1)
        ]
        if cell_positions != expected_positions:
            errors.append("pdf_semantic_header_cell_positions_invalid")
        if len(cell_refs) != len(set(cell_refs)):
            errors.append("pdf_semantic_header_cell_refs_duplicate")
        if len(candidate_ids) != len(set(candidate_ids)):
            errors.append("pdf_semantic_header_candidate_ids_duplicate")

    spans = value.get("spans")
    if not isinstance(spans, list):
        errors.append("pdf_semantic_header_spans_invalid")
    else:
        for span in spans:
            errors.extend(_validate_span(span, row_count, column_count))
    hierarchy = value.get("header_hierarchy")
    if not isinstance(hierarchy, list):
        errors.append("pdf_semantic_header_hierarchy_invalid")
    else:
        for relation in hierarchy:
            errors.extend(
                _validate_header_relation(relation, row_count, column_count)
            )
    return sorted(set(errors))


def _validate_alternative(
    value: object,
    source: dict[str, Any] | None,
) -> list[str]:
    if not isinstance(value, dict):
        return ["pdf_semantic_header_alternative_not_object"]
    errors: list[str] = []
    if set(value) != _ALTERNATIVE_KEYS:
        return ["pdf_semantic_header_alternative_keys_invalid"]
    grid_checksum = value.get("grid_checksum")
    if not _sha256(grid_checksum):
        errors.append("pdf_semantic_header_grid_checksum_invalid")
    if value.get("projection_status") not in ALTERNATIVE_PROJECTION_STATUSES:
        errors.append("pdf_semantic_header_alternative_status_invalid")
    if not _sorted_unique_strings(value.get("reason_codes")):
        errors.append("pdf_semantic_header_alternative_reasons_invalid")
    context_bytes = value.get("context_bytes")
    if not isinstance(context_bytes, int) or isinstance(context_bytes, bool) or context_bytes < 1:
        errors.append("pdf_semantic_header_context_bytes_invalid")

    columns = value.get("physical_columns")
    column_ids: list[str] = []
    if not isinstance(columns, list) or not columns:
        errors.append("pdf_semantic_header_physical_columns_invalid")
    else:
        for expected_ordinal, column in enumerate(columns, start=1):
            if not isinstance(column, dict) or set(column) != _PHYSICAL_COLUMN_KEYS:
                errors.append("pdf_semantic_header_physical_column_invalid")
                continue
            if column.get("column_ordinal") != expected_ordinal:
                errors.append("pdf_semantic_header_physical_column_order_invalid")
            expected_id = physical_column_id(str(grid_checksum), expected_ordinal)
            if column.get("physical_column_id") != expected_id:
                errors.append("pdf_semantic_header_physical_column_id_mismatch")
            column_ids.append(str(column.get("physical_column_id")))
    column_id_set = set(column_ids)

    available_cells: set[str] = set()
    available_atoms: set[str] = set()
    available_spans: set[str] = set()
    header_cell_columns: dict[str, set[str]] = {}
    header_atom_columns: dict[str, set[str]] = {}
    span_columns: dict[str, set[str]] = {}
    all_cell_columns: dict[str, set[str]] = {}
    all_atom_columns: dict[str, set[str]] = {}
    if source is not None:
        errors.extend(validate_physical_alternative_shape(source))
        if source.get("grid_checksum") != grid_checksum:
            errors.append("pdf_semantic_header_source_grid_mismatch")
        (
            header_cell_columns,
            header_atom_columns,
            span_columns,
            all_cell_columns,
            all_atom_columns,
        ) = _source_evidence_bindings(source, str(grid_checksum))
        available_cells = set(header_cell_columns)
        available_atoms = set(header_atom_columns)
        available_spans = set(span_columns)

    fields = value.get("semantic_fields")
    field_ids: set[str] = set()
    field_qualifier_refs: set[str] = set()
    if not isinstance(fields, list):
        errors.append("pdf_semantic_header_fields_invalid")
        fields = []
    for field in fields:
        if not isinstance(field, dict) or set(field) != _FIELD_KEYS:
            errors.append("pdf_semantic_header_field_invalid")
            continue
        field_id = field.get("field_id")
        if not _nonempty_string(field_id) or field_id in field_ids:
            errors.append("pdf_semantic_header_field_id_invalid")
        else:
            field_ids.add(field_id)
        if field.get("role") not in SEMANTIC_HEADER_VOCABULARY:
            errors.append("pdf_semantic_header_field_role_invalid")
        if field.get("logical_type") not in LOGICAL_TYPES:
            errors.append("pdf_semantic_header_logical_type_invalid")
        physical_ids = field.get("physical_column_ids")
        if not _ordered_unique_strings(physical_ids) or not set(physical_ids) <= column_id_set:
            errors.append("pdf_semantic_header_field_columns_invalid")
        bound_field_columns = set(physical_ids) if isinstance(physical_ids, list) else set()
        for key, available, bindings in (
            ("header_cell_refs", available_cells, header_cell_columns),
            ("header_span_refs", available_spans, span_columns),
            ("header_atom_ids", available_atoms, header_atom_columns),
        ):
            refs = field.get(key)
            if not _ordered_unique_strings(refs, allow_empty=True):
                errors.append(f"pdf_semantic_header_field_{key}_invalid")
            elif source is not None and not set(refs) <= available:
                errors.append(f"pdf_semantic_header_field_{key}_unbound")
            elif source is not None and not _evidence_refs_match_columns(
                refs,
                bindings,
                bound_field_columns,
            ):
                errors.append(
                    f"pdf_semantic_header_field_{key}_column_unbound"
                )
        refs = field.get("qualifier_refs")
        if not _ordered_unique_strings(refs, allow_empty=True):
            errors.append("pdf_semantic_header_field_qualifier_refs_invalid")
        else:
            field_qualifier_refs.update(refs)

    qualifiers = value.get("qualifiers")
    qualifier_ids: set[str] = set()
    if not isinstance(qualifiers, list):
        errors.append("pdf_semantic_header_qualifiers_invalid")
        qualifiers = []
    source_all_cells = set(all_cell_columns)
    source_all_atoms = set(all_atom_columns)
    for qualifier in qualifiers:
        if not isinstance(qualifier, dict) or set(qualifier) != _QUALIFIER_KEYS:
            errors.append("pdf_semantic_header_qualifier_invalid")
            continue
        qualifier_id = qualifier.get("qualifier_id")
        if not _nonempty_string(qualifier_id) or qualifier_id in qualifier_ids:
            errors.append("pdf_semantic_header_qualifier_id_invalid")
        else:
            qualifier_ids.add(qualifier_id)
        if qualifier.get("kind") not in QUALIFIER_KINDS:
            errors.append("pdf_semantic_header_qualifier_kind_invalid")
        if qualifier.get("scope") not in QUALIFIER_SCOPES:
            errors.append("pdf_semantic_header_qualifier_scope_invalid")
        measure_field_id = qualifier.get("measure_field_id")
        if measure_field_id is not None and measure_field_id not in field_ids:
            errors.append("pdf_semantic_header_qualifier_measure_field_invalid")
        physical_ids = qualifier.get("physical_column_ids")
        if not _ordered_unique_strings(physical_ids) or not set(physical_ids) <= column_id_set:
            errors.append("pdf_semantic_header_qualifier_columns_invalid")
        bound_qualifier_columns = (
            set(physical_ids) if isinstance(physical_ids, list) else set()
        )
        for key, available, bindings in (
            ("evidence_cell_refs", source_all_cells, all_cell_columns),
            ("evidence_atom_ids", source_all_atoms, all_atom_columns),
        ):
            refs = qualifier.get(key)
            if not _ordered_unique_strings(refs, allow_empty=True):
                errors.append(f"pdf_semantic_header_qualifier_{key}_invalid")
            elif source is not None and not set(refs) <= available:
                errors.append(f"pdf_semantic_header_qualifier_{key}_unbound")
            elif source is not None and not _evidence_refs_match_columns(
                refs,
                bindings,
                bound_qualifier_columns,
            ):
                errors.append(
                    f"pdf_semantic_header_qualifier_{key}_column_unbound"
                )
        code = qualifier.get("normalized_code")
        kind = qualifier.get("kind")
        allowed_codes = (
            SEMANTIC_CURRENCY_CODE_ALLOWLIST
            if kind == "currency"
            else SEMANTIC_UNIT_CODE_ALLOWLIST
            if kind == "unit"
            else frozenset()
        )
        if code is not None and code not in allowed_codes:
            errors.append("pdf_semantic_header_qualifier_code_invalid")
        elif code is not None and source is not None:
            evidence_refs = set(qualifier.get("evidence_cell_refs") or [])
            literal_values = {
                exact_value
                for cell in source.get("cells") or []
                if isinstance(cell, dict) and cell.get("cell_ref") in evidence_refs
                for exact_value in cell.get("exact_values") or []
                if isinstance(exact_value, str)
            }
            literal_codes = {
                item
                for exact_value in literal_values
                for item in _literal_codes_for_kind(exact_value, str(kind))
            }
            if code not in literal_codes:
                errors.append("pdf_semantic_header_qualifier_code_not_literal_evidence")
    if qualifier_ids != field_qualifier_refs:
        errors.append("pdf_semantic_header_qualifier_backrefs_invalid")

    mapped = value.get("mapped_physical_column_ids")
    unmapped = value.get("unmapped_physical_column_ids")
    if not _ordered_unique_strings(mapped, allow_empty=True):
        errors.append("pdf_semantic_header_mapped_columns_invalid")
        mapped = []
    if not _ordered_unique_strings(unmapped, allow_empty=True):
        errors.append("pdf_semantic_header_unmapped_columns_invalid")
        unmapped = []
    if set(mapped) & set(unmapped) or set(mapped) | set(unmapped) != column_id_set:
        errors.append("pdf_semantic_header_column_partition_invalid")
    signature = value.get("logical_schema_signature")
    if not _string_list(signature, allow_empty=True):
        errors.append("pdf_semantic_header_signature_invalid")
    elif not set(signature) <= LOGICAL_TYPES:
        errors.append("pdf_semantic_header_signature_type_invalid")
    return errors


def _validate_physical_cell(
    value: object,
    row_count: int,
    column_count: int,
) -> list[str]:
    keys = {
        "cell_ref",
        "row_ordinal",
        "column_ordinal",
        "candidate_ids",
        "exact_values",
    }
    if not isinstance(value, dict) or set(value) != keys:
        return ["pdf_semantic_header_cell_invalid"]
    errors: list[str] = []
    if not _nonempty_string(value.get("cell_ref")):
        errors.append("pdf_semantic_header_cell_ref_invalid")
    if not _bounded_int(value.get("row_ordinal"), maximum=row_count):
        errors.append("pdf_semantic_header_cell_row_invalid")
    if not _bounded_int(value.get("column_ordinal"), maximum=column_count):
        errors.append("pdf_semantic_header_cell_column_invalid")
    candidates = value.get("candidate_ids")
    exact_values = value.get("exact_values")
    if not _ordered_unique_strings(candidates, allow_empty=True):
        errors.append("pdf_semantic_header_cell_candidate_ids_invalid")
    if not isinstance(exact_values, list) or not all(
        isinstance(item, str) for item in exact_values
    ):
        errors.append("pdf_semantic_header_cell_exact_values_invalid")
    elif isinstance(candidates, list) and len(candidates) != len(exact_values):
        errors.append("pdf_semantic_header_cell_value_binding_invalid")
    return errors


def _validate_span(value: object, row_count: int, column_count: int) -> list[str]:
    keys = {
        "start_row",
        "end_row",
        "start_column",
        "end_column",
        "relation",
    }
    if not isinstance(value, dict) or set(value) != keys:
        return ["pdf_semantic_header_span_invalid"]
    coordinates = (
        value.get("start_row"),
        value.get("end_row"),
        value.get("start_column"),
        value.get("end_column"),
    )
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in coordinates):
        return ["pdf_semantic_header_span_coordinates_invalid"]
    start_row, end_row, start_column, end_column = coordinates
    if (
        start_row < 1
        or end_row > row_count
        or start_column < 1
        or end_column > column_count
        or start_row > end_row
        or start_column > end_column
        or (start_row == end_row and start_column == end_column)
    ):
        return ["pdf_semantic_header_span_bounds_invalid"]
    if value.get("relation") != "merged":
        return ["pdf_semantic_header_span_relation_invalid"]
    return []


def _validate_header_relation(
    value: object,
    row_count: int,
    column_count: int,
) -> list[str]:
    keys = {
        "parent_row",
        "parent_column",
        "child_start_column",
        "child_end_column",
    }
    if not isinstance(value, dict) or set(value) != keys:
        return ["pdf_semantic_header_relation_invalid"]
    parent_row = value.get("parent_row")
    parent_column = value.get("parent_column")
    child_start = value.get("child_start_column")
    child_end = value.get("child_end_column")
    if not all(
        isinstance(item, int) and not isinstance(item, bool)
        for item in (parent_row, parent_column, child_start, child_end)
    ):
        return ["pdf_semantic_header_relation_coordinates_invalid"]
    if (
        parent_row < 1
        or parent_row > row_count
        or parent_column < 1
        or parent_column > column_count
        or child_start < 1
        or child_end > column_count
        or child_start > child_end
    ):
        return ["pdf_semantic_header_relation_bounds_invalid"]
    return []


def _validate_configuration(value: object) -> list[str]:
    if not isinstance(value, dict) or set(value) != _CONFIGURATION_KEYS:
        return ["pdf_semantic_header_configuration_invalid"]
    errors: list[str] = []
    if value.get("schema_version") != PDF_SEMANTIC_HEADER_CONFIGURATION_SCHEMA:
        errors.append("pdf_semantic_header_configuration_schema_invalid")
    if value.get("policy_version") != PDF_SEMANTIC_HEADER_POLICY_VERSION:
        errors.append("pdf_semantic_header_configuration_policy_invalid")
    if (
        value.get("currency_code_policy_version")
        != SEMANTIC_CURRENCY_CODE_POLICY_VERSION
    ):
        errors.append("pdf_semantic_header_currency_policy_invalid")
    if value.get("unit_code_policy_version") != SEMANTIC_UNIT_CODE_POLICY_VERSION:
        errors.append("pdf_semantic_header_unit_policy_invalid")
    for key, maximum in (
        ("max_context_bytes", MAX_SEMANTIC_CONTEXT_BYTES),
        (
            "max_physical_alternatives",
            MAX_SEMANTIC_PHYSICAL_ALTERNATIVES,
        ),
        ("max_representative_rows", MAX_SEMANTIC_REPRESENTATIVE_ROWS),
    ):
        if not _bounded_int(value.get(key), maximum=maximum):
            errors.append(f"pdf_semantic_header_configuration_{key}_invalid")
    return errors


def _source_evidence_bindings(
    source: dict[str, Any],
    grid_checksum: str,
) -> tuple[
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    header_rows = set(source.get("header_rows") or [])
    spans_by_anchor: dict[tuple[int, int], list[dict[str, Any]]] = {}
    span_columns: dict[str, set[str]] = {}
    for span in source.get("spans") or []:
        if not isinstance(span, dict):
            continue
        anchor = (int(span["start_row"]), int(span["start_column"]))
        spans_by_anchor.setdefault(anchor, []).append(span)
        if int(span["start_row"]) in header_rows:
            span_columns[physical_span_id(grid_checksum, span)] = {
                physical_column_id(grid_checksum, ordinal)
                for ordinal in range(
                    int(span["start_column"]),
                    int(span["end_column"]) + 1,
                )
            }

    header_cell_columns: dict[str, set[str]] = {}
    header_atom_columns: dict[str, set[str]] = {}
    all_cell_columns: dict[str, set[str]] = {}
    all_atom_columns: dict[str, set[str]] = {}
    for cell in source.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        position = (int(cell["row_ordinal"]), int(cell["column_ordinal"]))
        columns = {physical_column_id(grid_checksum, position[1])}
        for span in spans_by_anchor.get(position, []):
            columns.update(
                physical_column_id(grid_checksum, ordinal)
                for ordinal in range(
                    int(span["start_column"]),
                    int(span["end_column"]) + 1,
                )
            )
        cell_ref = str(cell["cell_ref"])
        all_cell_columns[cell_ref] = columns
        for atom_id in cell.get("candidate_ids") or []:
            all_atom_columns[str(atom_id)] = columns
        if position[0] in header_rows:
            header_cell_columns[cell_ref] = columns
            for atom_id in cell.get("candidate_ids") or []:
                header_atom_columns[str(atom_id)] = columns
    return (
        header_cell_columns,
        header_atom_columns,
        span_columns,
        all_cell_columns,
        all_atom_columns,
    )


def _evidence_refs_match_columns(
    refs: object,
    bindings: dict[str, set[str]],
    bound_columns: set[str],
) -> bool:
    if not isinstance(refs, list):
        return False
    return all(
        isinstance(ref, str)
        and bool(bindings.get(ref, set()) & bound_columns)
        for ref in refs
    )


def _literal_codes_for_kind(value: str, kind: str) -> list[str]:
    if kind == "currency":
        choices = sorted(SEMANTIC_CURRENCY_CODE_ALLOWLIST)
        pattern = r"(?<![A-Z0-9])(?:" + "|".join(choices) + r")(?![A-Z0-9])"
        return re.findall(pattern, value)
    if kind == "unit":
        choices = sorted(SEMANTIC_UNIT_CODE_ALLOWLIST)
        pattern = r"(?<![\w])(?:" + "|".join(choices) + r")(?![\w])"
        return re.findall(pattern, value.casefold(), flags=re.UNICODE)
    return []


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sha256(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _bounded_int(value: object, *, maximum: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= maximum
    )


def _ordered_unique_strings(value: object, *, allow_empty: bool = False) -> bool:
    if not isinstance(value, list) or (not value and not allow_empty):
        return False
    if not all(_nonempty_string(item) for item in value):
        return False
    return len(value) == len(set(value))


def _string_list(value: object, *, allow_empty: bool = False) -> bool:
    return (
        isinstance(value, list)
        and (allow_empty or bool(value))
        and all(_nonempty_string(item) for item in value)
    )


def _sorted_unique_strings(value: object) -> bool:
    return (
        isinstance(value, list)
        and all(_nonempty_string(item) for item in value)
        and value == sorted(set(value))
    )
