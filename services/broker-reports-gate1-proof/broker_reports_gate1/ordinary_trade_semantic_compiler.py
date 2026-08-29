"""Deterministic Canonical-to-runtime projection for qualified ordinary trades.

The semantic model owns only an immutable schema mapping and literal enum
decisions.  Every row, value and source reference is copied from the active
Canonical by this module.
"""

from __future__ import annotations

import copy
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re
from typing import Any, Iterable, Mapping

from .canonical_artifact import validate_canonical_artifact


ORDINARY_TRADE_MAPPING_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_schema_mapping_v3"
)
ORDINARY_TRADE_PROJECTION_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_runtime_projection_v5"
)
ORDINARY_TRADE_MANAGED_HEADER_VIEW_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_managed_header_view_v1"
)
ORDINARY_TRADE_MANAGED_DATA_REPLAY_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_managed_data_replay_v1"
)
ORDINARY_TRADE_MANAGED_CASE_MAPPING_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_managed_case_mapping_v4"
)
SOURCE_OBSERVATION_SCHEMA_VERSION = "broker_reports_source_observation_v1"
FACTORY_REQUIRED = (
    "OrdinaryTradeSemanticCompilerFactory.create is the only production-candidate "
    "Canonical to ordinary-trade projection entrypoint"
)
FORBIDDEN = (
    "broker, year or filename profiles; model-authored rows or financial values; "
    "value-based deduplication; inferred table continuation; regex broker rules"
)

_TABLE_TYPE = "SECURITY_TRADES"
_DISPOSITIONS = {
    "RUNTIME_READY",
    "RELEVANT_UNMAPPED",
    "SOURCE_RETAINED_NO_CONSUMER",
}
_ROLES = {
    "asset_name",
    "trade_date",
    "side",
    "quantity",
    "unit_price",
    "currency",
    "gross_amount",
    "broker_commission",
    "exchange_commission",
    "settlement_date",
    "trade_time",
    "security_code",
    "accrued_interest",
    "trade_id",
    "venue",
    "comment",
    "status",
    "description",
    "unmapped",
}
_REQUIRED = {
    "asset_name",
    "trade_date",
    "side",
    "quantity",
    "unit_price",
    "currency",
    "gross_amount",
}
_DISPLAY_ONLY_NON_RECORD_ROLES = {
    "asset_name",
    "security_code",
    "trade_id",
    "venue",
    "comment",
    "status",
    "description",
    "unmapped",
}
_MANAGED_SOURCE_REPRESENTATION_OWNER = "managed_document_v2"
_MANAGED_WHOLE_TABLE_PROJECTION_SCHEMA_VERSION = (
    "broker_reports_managed_whole_table_projection_v2"
)
_MANAGED_ENTRY_BINDING_SCHEMA_VERSION = (
    "broker_reports_canonical_managed_entry_binding_v1"
)
_MANAGED_ROW_ROLE_ORIGINS = {
    "REVIEWED_SOURCE_BOUND",
    "DETERMINISTIC_DERIVED",
}
_MANAGED_ROW_ROLES = {
    "TABLE_TITLE",
    "COLUMN_HEADER",
    "GROUP_HEADER",
    "DATA",
    "SUBTOTAL",
    "TOTAL",
    "NOTE",
    "CONTINUATION_HEADER",
    "UNKNOWN",
}
_MANAGED_STRUCTURAL_ROW_ROLES = {
    "TABLE_TITLE",
    "COLUMN_HEADER",
    "GROUP_HEADER",
    "NOTE",
    "CONTINUATION_HEADER",
}
_MAPPING_KEYS = {
    "schema_version",
    "mapping_id",
    "structural_fingerprint",
    "table_type",
    "title_literal",
    "columns",
    "amount_currency_bindings",
    "side_values",
    "qualification_ref",
}
_MANAGED_CASE_MAPPING_KEYS = {
    "schema_version",
    "candidate_id",
    "mapping_status",
    "runtime_activation",
    "global_reuse",
    "table_type",
    "header_view_binding",
    "structural_fingerprint",
    "columns",
    "amount_currency_bindings",
}
_FORBIDDEN_PROFILE_KEYS = {"broker", "broker_id", "year", "filename", "profile"}
_DMY_PREFIX = re.compile(r"^([0-9]{2})\.([0-9]{2})\.([0-9]{4})(?:\s|$)")
_ISO_PREFIX = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})(?:[T\s]|$)")
_PLAIN_DECIMAL = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:[.,][0-9]+)?$")
_SPACE_DECIMAL = re.compile(
    r"^-?(?:[1-9][0-9]{0,2})(?:[ \u00a0\u202f][0-9]{3})+(?:[.,][0-9]+)?$"
)
_COMMA_GROUPED_DOT = re.compile(r"^-?(?:[1-9][0-9]{0,2})(?:,[0-9]{3})+\.[0-9]+$")
_DOT_GROUPED_COMMA = re.compile(r"^-?(?:[1-9][0-9]{0,2})(?:\.[0-9]{3})+,[0-9]+$")
_COMMA_GROUPED_INTEGER = re.compile(r"^-?(?:[1-9][0-9]{0,2})(?:,[0-9]{3})+$")


class OrdinaryTradeSemanticCompilerError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class OrdinaryTradeSemanticCompilerFactory:
    @staticmethod
    def create() -> "OrdinaryTradeSemanticCompiler":
        return OrdinaryTradeSemanticCompiler()


class OrdinaryTradeSemanticCompiler:
    """Compile a full Canonical document using exact qualified mappings only."""

    def compile(
        self,
        *,
        canonical: Mapping[str, Any],
        canonical_binding: Mapping[str, str],
        mappings: Iterable[Mapping[str, Any]],
        scoped_mappings: Iterable[Mapping[str, Any]] = (),
        table_resolutions: Iterable[Mapping[str, Any]] = (),
        semantic_mapping_case_ref: str | None = None,
    ) -> dict[str, Any]:
        if semantic_mapping_case_ref is not None and (
            not isinstance(semantic_mapping_case_ref, str)
            or not semantic_mapping_case_ref.startswith("art_otmapcase_")
        ):
            _fail("ordinary_trade_mapping_case_ref_invalid")
        binding = _canonical_binding(canonical=canonical, value=canonical_binding)
        accepted = tuple(_validated_mapping(item) for item in mappings)
        accepted_scoped = tuple(
            _validated_scoped_mapping(item) for item in scoped_mappings
        )
        accepted_resolutions = tuple(
            _validated_table_resolution(item) for item in table_resolutions
        )
        fingerprints = [item["structural_fingerprint"] for item in accepted]
        if len(fingerprints) != len(set(fingerprints)):
            _fail("ordinary_trade_mapping_fingerprint_duplicate")
        scoped_nodes = [item["table_node_id"] for item in accepted_scoped]
        if len(scoped_nodes) != len(set(scoped_nodes)):
            _fail("ordinary_trade_case_mapping_scope_duplicate")
        resolution_nodes = [item["table_node_id"] for item in accepted_resolutions]
        if len(resolution_nodes) != len(set(resolution_nodes)):
            _fail("ordinary_trade_table_resolution_duplicate")

        observations: list[dict[str, Any]] = []
        runtime_records: list[dict[str, Any]] = []
        all_mappings = (*accepted, *(item["mapping"] for item in accepted_scoped))
        mapping_matches: dict[str, int] = {
            item["mapping_id"]: 0 for item in all_mappings
        }
        table_nodes = [
            item
            for item in canonical.get("nodes", [])
            if isinstance(item, dict) and item.get("node_type") == "TABLE"
        ]
        for table in table_nodes:
            rows, managed_row_roles = ordinary_trade_canonical_table_rows(
                table,
                provenance=canonical.get("provenance"),
                source=canonical.get("source"),
            )
            managed_header_rows = _managed_header_row_numbers(managed_row_roles)
            global_matches = _matching_mappings(
                rows=rows,
                mappings=accepted,
                candidate_header_rows=managed_header_rows,
            )
            if len(global_matches) > 1:
                _fail("ordinary_trade_table_mapping_ambiguous")
            scoped_matches = _matching_scoped_mappings(
                table=table,
                rows=rows,
                mappings=accepted_scoped,
                candidate_header_rows=managed_header_rows,
            )
            if len(scoped_matches) > 1:
                _fail("ordinary_trade_case_mapping_scope_ambiguous")
            if global_matches and scoped_matches:
                _fail("ordinary_trade_table_mapping_authority_conflict")
            matches = global_matches or scoped_matches
            if not matches:
                resolutions = _matching_table_resolutions(
                    table=table,
                    rows=rows,
                    resolutions=accepted_resolutions,
                )
                if len(resolutions) > 1:
                    _fail("ordinary_trade_table_resolution_ambiguous")
                if resolutions:
                    resolution = resolutions[0]
                    resolution_rows = _managed_unmapped_rows(
                        rows=rows,
                        managed_row_roles=managed_row_roles,
                        after_row=resolution["header_row"],
                    )
                    no_consumer = (
                        resolution["disposition"] == "NO_NAMED_CONSUMER"
                    )
                    observations.extend(
                        _unmapped_table_rows(
                            binding=binding,
                            table=table,
                            rows={
                                row: cells
                                for row, cells in resolution_rows.items()
                                if not (
                                    no_consumer
                                    and managed_row_roles.get(row) == "UNKNOWN"
                                )
                            },
                            reason=(
                                "NO_NAMED_ORDINARY_TRADE_CONSUMER"
                                if no_consumer
                                else "UNSUPPORTED_FINANCIAL_MEANING"
                            ),
                            disposition=(
                                "SOURCE_RETAINED_NO_CONSUMER"
                                if no_consumer
                                else "RELEVANT_UNMAPPED"
                            ),
                        )
                    )
                    if no_consumer:
                        observations.extend(
                            _unmapped_table_rows(
                                binding=binding,
                                table=table,
                                rows={
                                    row: cells
                                    for row, cells in resolution_rows.items()
                                    if managed_row_roles.get(row) == "UNKNOWN"
                                },
                                reason="MANAGED_ROW_ROLE_UNRESOLVED",
                            )
                        )
                    continue
                observations.extend(
                    _unmapped_table_rows(
                        binding=binding,
                        table=table,
                        rows=rows,
                        reason="UNKNOWN_STRUCTURAL_FINGERPRINT",
                    )
                )
                continue
            mapping, header_row = matches[0]
            mapping_matches[mapping["mapping_id"]] += 1
            mapped_rows = _managed_mapped_data_rows(
                rows=rows,
                managed_row_roles=managed_row_roles,
                after_row=header_row,
            )
            numeric_convention = _table_numeric_convention(
                rows=mapped_rows,
                mapping=mapping,
            )
            unresolved_rows = {
                row: cells
                for row, cells in rows.items()
                if managed_row_roles.get(row) == "UNKNOWN"
            }
            retained_rows = {
                row: cells
                for row, cells in rows.items()
                if managed_row_roles.get(row)
                in {
                    "GROUP_HEADER",
                    "SUBTOTAL",
                    "TOTAL",
                    "NOTE",
                    "CONTINUATION_HEADER",
                }
            }
            for row_number in sorted(
                {*mapped_rows, *unresolved_rows, *retained_rows}
            ):
                if row_number in unresolved_rows:
                    observations.extend(
                        _unmapped_table_rows(
                            binding=binding,
                            table=table,
                            rows={row_number: unresolved_rows[row_number]},
                            reason="MANAGED_ROW_ROLE_UNRESOLVED",
                        )
                    )
                    continue
                if row_number in retained_rows:
                    reason = "MANAGED_STRUCTURAL_ROW_NO_FINANCIAL_CONSUMER"
                    disposition = "SOURCE_RETAINED_NO_CONSUMER"
                    if (
                        managed_row_roles[row_number] == "CONTINUATION_HEADER"
                        and not _same_row_literals(
                            retained_rows[row_number],
                            rows[header_row],
                        )
                    ):
                        reason = "MANAGED_CONTINUATION_HEADER_MISMATCH"
                        disposition = "RELEVANT_UNMAPPED"
                    observations.extend(
                        _unmapped_table_rows(
                            binding=binding,
                            table=table,
                            rows={row_number: retained_rows[row_number]},
                            reason=reason,
                            disposition=disposition,
                        )
                    )
                    continue
                cells = rows[row_number]
                if not any(_literal(cell) for cell in cells.values()):
                    continue
                observation = _mapped_observation(
                    binding=binding,
                    table=table,
                    row=row_number,
                    cells=cells,
                    mapping=mapping,
                    numeric_convention=numeric_convention,
                )
                observations.append(observation)
                if observation["disposition"] == "RUNTIME_READY":
                    runtime_records.extend(
                        _runtime_records(observation=observation, mapping=mapping)
                    )

        for scoped in accepted_scoped:
            if mapping_matches[scoped["mapping"]["mapping_id"]] != 1:
                _fail("ordinary_trade_case_mapping_scope_stale")
        _validate_projection_lineage(
            observations=observations,
            runtime_records=runtime_records,
        )
        _validate_projection_against_canonical(
            canonical=canonical,
            observations=observations,
        )
        projection = {
            "schema_version": ORDINARY_TRADE_PROJECTION_SCHEMA_VERSION,
            "canonical_binding": binding,
            "semantic_mapping_case_ref": semantic_mapping_case_ref,
            "compiler_contract": {
                "canonical_is_source_authority": True,
                "model_owns_rows": False,
                "model_owns_financial_values": False,
                "value_based_deduplication": False,
                "unknown_schema_terminal": "RELEVANT_UNMAPPED",
                "structural_lineage_inferred": False,
            },
            "qualified_semantic_authorities": [
                {
                    "mapping_id": item["mapping_id"],
                    "structural_fingerprint": item["structural_fingerprint"],
                    "qualification_ref": copy.deepcopy(item["qualification_ref"]),
                }
                for item in all_mappings
                if mapping_matches[item["mapping_id"]] > 0
            ],
            "qualified_table_resolutions": copy.deepcopy(
                list(accepted_resolutions)
            ),
            "mapping_matches": [
                {"mapping_id": key, "matched_tables": value}
                for key, value in sorted(mapping_matches.items())
                if value > 0
            ],
            "source_observations": observations,
            "runtime_records": runtime_records,
        }
        projection["projection_sha256"] = _sha256_json(projection)
        validate_ordinary_trade_projection(projection)
        return projection

    def unmapped_table_node_ids(
        self,
        *,
        canonical: Mapping[str, Any],
        mappings: Iterable[Mapping[str, Any]],
    ) -> list[str]:
        """Return exact table nodes not covered by the frozen schema registry."""

        accepted = tuple(_validated_mapping(item) for item in mappings)
        fingerprints = [item["structural_fingerprint"] for item in accepted]
        if len(fingerprints) != len(set(fingerprints)):
            _fail("ordinary_trade_mapping_fingerprint_duplicate")
        result: list[str] = []
        for table in canonical.get("nodes", []):
            if not isinstance(table, dict) or table.get("node_type") != "TABLE":
                continue
            node_id = table.get("node_id")
            if not isinstance(node_id, str) or not node_id:
                _fail("ordinary_trade_table_node_id_invalid")
            rows, managed_row_roles = ordinary_trade_canonical_table_rows(
                table,
                provenance=canonical.get("provenance"),
                source=canonical.get("source"),
            )
            matches = _matching_mappings(
                rows=rows,
                mappings=accepted,
                candidate_header_rows=_managed_header_row_numbers(
                    managed_row_roles
                ),
            )
            if len(matches) > 1:
                _fail("ordinary_trade_table_mapping_ambiguous")
            if not matches:
                result.append(node_id)
        return result


def compile_schema_mapping(
    *,
    title_literal: str | None,
    headers: Iterable[Mapping[str, Any]],
    model_columns: Iterable[Mapping[str, Any]],
    amount_currency_bindings: Iterable[Mapping[str, int]],
    side_values: Iterable[Mapping[str, str]],
    qualification_ref: Mapping[str, str],
) -> dict[str, Any]:
    """Freeze a validated mapping candidate without accepting row values."""

    header_items = [
        {"column": int(item["column"]), "literal": str(item["literal"])}
        for item in headers
    ]
    decisions = [copy.deepcopy(dict(item)) for item in model_columns]
    if len(header_items) != len(decisions):
        _fail("ordinary_trade_mapping_header_accounting")
    columns = []
    for header, decision in zip(header_items, decisions, strict=True):
        if int(decision.get("column", -1)) != header["column"]:
            _fail("ordinary_trade_mapping_header_order")
        columns.append(
            {
                "column": header["column"],
                "header_literal": header["literal"],
                "semantic_role": decision.get("semantic_role"),
            }
        )
    fingerprint = structural_fingerprint(
        title_literal=title_literal,
        columns=columns,
    )
    frozen_qualification_ref = copy.deepcopy(dict(qualification_ref))
    frozen_amount_currency_bindings = [
        copy.deepcopy(dict(item)) for item in amount_currency_bindings
    ]
    frozen_amount_currency_bindings.sort(
        key=lambda item: (
            item.get("amount_column")
            if isinstance(item.get("amount_column"), int)
            and not isinstance(item.get("amount_column"), bool)
            else -1
        )
    )
    material = {
        "structural_fingerprint": fingerprint,
        "columns": columns,
        "amount_currency_bindings": frozen_amount_currency_bindings,
        "side_values": [copy.deepcopy(dict(item)) for item in side_values],
        "qualification_ref": frozen_qualification_ref,
    }
    mapping = {
        "schema_version": ORDINARY_TRADE_MAPPING_SCHEMA_VERSION,
        "mapping_id": "otmap_" + _sha256_json(material)[:32],
        "structural_fingerprint": fingerprint,
        "table_type": _TABLE_TYPE,
        "title_literal": title_literal,
        "columns": columns,
        "amount_currency_bindings": material["amount_currency_bindings"],
        "side_values": material["side_values"],
        "qualification_ref": material["qualification_ref"],
    }
    return _validated_mapping(mapping)


def compile_managed_header_case_mapping_candidate(
    *,
    canonical: Mapping[str, Any],
    canonical_binding: Mapping[str, str],
    table_node_id: str,
    model_decision: Mapping[str, Any],
) -> dict[str, Any]:
    """Freeze one inactive case-only mapping over host-owned header paths."""

    view = ordinary_trade_canonical_managed_header_view(
        canonical=canonical,
        canonical_binding=canonical_binding,
        table_node_id=table_node_id,
    )
    if not isinstance(model_decision, Mapping) or set(model_decision) != {
        "columns",
        "amount_currency_bindings",
    }:
        _fail("ordinary_trade_managed_case_model_decision_invalid")
    decisions = model_decision.get("columns")
    if not isinstance(decisions, list) or len(decisions) != len(view["columns"]):
        _fail("ordinary_trade_managed_case_model_columns_invalid")
    columns = []
    for host, decision in zip(view["columns"], decisions, strict=True):
        if (
            not isinstance(decision, Mapping)
            or set(decision) != {"column", "semantic_role"}
            or not isinstance(decision.get("column"), int)
            or isinstance(decision.get("column"), bool)
            or decision.get("column") != host["column"]
            or decision.get("semantic_role") not in _ROLES
        ):
            _fail("ordinary_trade_managed_case_model_columns_invalid")
        columns.append(
            {
                "column": host["column"],
                "logical_column_id": host["logical_column_id"],
                "header_path": copy.deepcopy(host["primary_header_path"]),
                "semantic_role": decision["semantic_role"],
            }
        )
    material = {
        "schema_version": ORDINARY_TRADE_MANAGED_CASE_MAPPING_SCHEMA_VERSION,
        "mapping_status": "CANDIDATE_ONLY",
        "runtime_activation": False,
        "global_reuse": False,
        "table_type": _TABLE_TYPE,
        "header_view_binding": _managed_header_view_binding(view),
        "structural_fingerprint": _managed_header_structural_fingerprint(view),
        "columns": columns,
        "amount_currency_bindings": copy.deepcopy(
            model_decision["amount_currency_bindings"]
        ),
    }
    candidate = {
        **material,
        "candidate_id": "otmapcase_" + _sha256_json(material)[:32],
    }
    return _validated_managed_header_case_mapping_candidate(
        candidate,
        managed_header_view=view,
    )


def validate_managed_header_case_mapping_candidate(
    *,
    value: Mapping[str, Any],
    canonical: Mapping[str, Any],
    canonical_binding: Mapping[str, str],
    table_node_id: str,
) -> dict[str, Any]:
    """Validate one v4 candidate against the exact host-owned header view."""

    view = ordinary_trade_canonical_managed_header_view(
        canonical=canonical,
        canonical_binding=canonical_binding,
        table_node_id=table_node_id,
    )
    return _validated_managed_header_case_mapping_candidate(
        value,
        managed_header_view=view,
    )


def _validated_managed_header_case_mapping_candidate(
    value: Mapping[str, Any],
    *,
    managed_header_view: Mapping[str, Any],
) -> dict[str, Any]:
    view = managed_header_view
    if (
        not isinstance(value, Mapping)
        or set(value) != _MANAGED_CASE_MAPPING_KEYS
        or value.get("schema_version")
        != ORDINARY_TRADE_MANAGED_CASE_MAPPING_SCHEMA_VERSION
        or value.get("mapping_status") != "CANDIDATE_ONLY"
        or value.get("runtime_activation") is not False
        or value.get("global_reuse") is not False
        or value.get("table_type") != _TABLE_TYPE
        or value.get("header_view_binding") != _managed_header_view_binding(view)
    ):
        _fail("ordinary_trade_managed_case_mapping_contract_invalid")
    columns = value.get("columns")
    if not isinstance(columns, list) or len(columns) != len(view["columns"]):
        _fail("ordinary_trade_managed_case_mapping_columns_invalid")
    for column, host in zip(columns, view["columns"], strict=True):
        if (
            not isinstance(column, Mapping)
            or set(column)
            != {
                "column",
                "logical_column_id",
                "header_path",
                "semantic_role",
            }
            or not isinstance(column.get("column"), int)
            or isinstance(column.get("column"), bool)
            or column.get("column") != host["column"]
            or column.get("logical_column_id") != host["logical_column_id"]
            or column.get("header_path") != host["primary_header_path"]
            or column.get("semantic_role") not in _ROLES
        ):
            _fail("ordinary_trade_managed_case_mapping_columns_invalid")
    if value.get("structural_fingerprint") != _managed_header_structural_fingerprint(
        view
    ):
        _fail("ordinary_trade_managed_case_mapping_fingerprint_invalid")
    _validate_managed_case_bounded_decisions(
        columns=columns,
        amount_currency_bindings=value.get("amount_currency_bindings"),
    )
    material = copy.deepcopy(dict(value))
    candidate_id = material.pop("candidate_id", None)
    if candidate_id != "otmapcase_" + _sha256_json(material)[:32]:
        _fail("ordinary_trade_managed_case_mapping_identity_invalid")
    return copy.deepcopy(dict(value))


def _managed_header_structural_fingerprint(
    view: Mapping[str, Any],
) -> str:
    primary_rows = view["primary_header_rows"]
    row_ordinals = {
        int(item["row"]): ordinal for ordinal, item in enumerate(primary_rows)
    }
    entry_shapes: dict[str, dict[str, Any]] = {}
    ordered_entry_ids = []
    for column in view["columns"]:
        for item in column["primary_header_path"]:
            entry_id = str(item["entry_id"])
            if entry_id not in entry_shapes:
                ordered_entry_ids.append(entry_id)
                entry_shapes[entry_id] = {
                    "primary_row_ordinal": row_ordinals[int(item["row"])],
                    "literal": item["literal"],
                    "columns": [],
                }
            entry_shapes[entry_id]["columns"].append(int(column["column"]))
    rows = []
    for row_ordinal in range(len(primary_rows)):
        rows.append(
            {
                "primary_row_ordinal": row_ordinal,
                "entries": [
                    copy.deepcopy(entry_shapes[entry_id])
                    for entry_id in ordered_entry_ids
                    if entry_shapes[entry_id]["primary_row_ordinal"] == row_ordinal
                ],
            }
        )
    return _sha256_json({"table_type": _TABLE_TYPE, "primary_rows": rows})


def _managed_header_view_binding(view: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": view["schema_version"],
        "header_view_sha256": view["header_view_sha256"],
        "table_node_id": view["table_node_id"],
        "canonical_binding": copy.deepcopy(view["canonical_binding"]),
        "managed_binding": copy.deepcopy(view["managed_binding"]),
    }


def _validate_managed_case_bounded_decisions(
    *,
    columns: list[Mapping[str, Any]],
    amount_currency_bindings: Any,
) -> None:
    roles_by_column = {
        int(item["column"]): str(item["semantic_role"]) for item in columns
    }
    if not _REQUIRED <= set(roles_by_column.values()):
        _fail("ordinary_trade_managed_case_required_roles_missing")
    amount_columns = {
        column
        for column, role in roles_by_column.items()
        if role in {"gross_amount", "broker_commission", "exchange_commission"}
    }
    if not isinstance(amount_currency_bindings, list):
        _fail("ordinary_trade_managed_case_amount_binding_invalid")
    bound_amounts = []
    for item in amount_currency_bindings:
        if (
            not isinstance(item, Mapping)
            or set(item) != {"amount_column", "currency_column"}
            or not isinstance(item.get("amount_column"), int)
            or isinstance(item.get("amount_column"), bool)
            or not isinstance(item.get("currency_column"), int)
            or isinstance(item.get("currency_column"), bool)
            or item["amount_column"] not in amount_columns
            or roles_by_column.get(item["currency_column"]) != "currency"
        ):
            _fail("ordinary_trade_managed_case_amount_binding_invalid")
        bound_amounts.append(item["amount_column"])
    if set(bound_amounts) != amount_columns or len(bound_amounts) != len(
        set(bound_amounts)
    ):
        _fail("ordinary_trade_managed_case_amount_binding_invalid")


def structural_fingerprint(
    *, title_literal: str | None, columns: Iterable[Mapping[str, Any]]
) -> str:
    items = list(columns)
    return _sha256_json(
        {
            "title": title_literal,
            "headers": [item.get("header_literal") for item in items],
            "columns": [item.get("column") for item in items],
        }
    )


def validate_ordinary_trade_projection(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != ORDINARY_TRADE_PROJECTION_SCHEMA_VERSION
        or set(value)
        != {
            "schema_version",
            "canonical_binding",
            "semantic_mapping_case_ref",
            "compiler_contract",
            "qualified_semantic_authorities",
            "qualified_table_resolutions",
            "mapping_matches",
            "source_observations",
            "runtime_records",
            "projection_sha256",
        }
    ):
        _fail("ordinary_trade_projection_contract_invalid")
    material = copy.deepcopy(value)
    expected = material.pop("projection_sha256")
    if expected != _sha256_json(material):
        _fail("ordinary_trade_projection_hash_invalid")
    observations = value.get("source_observations")
    records = value.get("runtime_records")
    if not isinstance(observations, list) or not isinstance(records, list):
        _fail("ordinary_trade_projection_contract_invalid")
    _validate_projection_lineage(observations=observations, runtime_records=records)


def normalize_runtime_value(
    role: str,
    literal: str,
    *,
    numeric_convention: str | None = None,
) -> tuple[str, str]:
    """Return (normalized value, deterministic transform id)."""

    if not isinstance(literal, str) or not literal.strip():
        _fail("ordinary_trade_runtime_literal_invalid")
    value = literal.strip()
    if role == "date":
        match = _DMY_PREFIX.match(value)
        if match is not None:
            day, month, year = match.groups()
            try:
                result = date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                _fail("ordinary_trade_runtime_date_invalid")
            return result, "DMY_OR_DMY_TIME_TO_ISO_DATE"
        match = _ISO_PREFIX.match(value)
        if match is not None:
            year, month, day = match.groups()
            try:
                result = date(int(year), int(month), int(day)).isoformat()
            except ValueError:
                _fail("ordinary_trade_runtime_date_invalid")
            return result, "ISO_OR_ISO_TIME_TO_ISO_DATE"
        _fail("ordinary_trade_runtime_date_invalid")
    if role in {"quantity", "unit_price", "amount"}:
        normalized = _decimal_literal(value, numeric_convention=numeric_convention)
        try:
            Decimal(normalized)
        except InvalidOperation:
            _fail("ordinary_trade_runtime_decimal_invalid")
        return normalized, "SOURCE_DECIMAL_TO_CANONICAL_DECIMAL"
    if role in {"asset", "currency"}:
        return value, "TRIM_ONLY"
    _fail("ordinary_trade_runtime_role_invalid")


def _canonical_binding(
    *, canonical: Mapping[str, Any], value: Mapping[str, str]
) -> dict[str, str]:
    keys = {
        "document_id",
        "canonical_version_id",
        "canonical_root_sha256",
        "source_artifact_ref",
        "source_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != keys:
        _fail("ordinary_trade_canonical_binding_invalid")
    source = canonical.get("source") or {}
    if (
        value.get("canonical_root_sha256") != canonical.get("canonical_root_hash")
        or value.get("source_artifact_ref") != source.get("source_artifact_ref")
        or value.get("source_sha256") != source.get("source_sha256")
        or not all(isinstance(value.get(key), str) and value.get(key) for key in keys)
    ):
        _fail("ordinary_trade_canonical_binding_invalid")
    return copy.deepcopy(dict(value))


def _validated_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value) != _MAPPING_KEYS
        or any(key in value for key in _FORBIDDEN_PROFILE_KEYS)
        or value.get("schema_version") != ORDINARY_TRADE_MAPPING_SCHEMA_VERSION
        or value.get("table_type") != _TABLE_TYPE
        or not isinstance(value.get("mapping_id"), str)
        or not value["mapping_id"].startswith("otmap_")
        or not isinstance(value.get("title_literal"), (str, type(None)))
    ):
        _fail("ordinary_trade_mapping_contract_invalid")
    columns = value.get("columns")
    if not isinstance(columns, list) or not columns:
        _fail("ordinary_trade_mapping_contract_invalid")
    column_numbers = []
    roles = []
    for item in columns:
        if (
            not isinstance(item, dict)
            or set(item) != {"column", "header_literal", "semantic_role"}
            or not isinstance(item.get("column"), int)
            or item["column"] < 1
            or not isinstance(item.get("header_literal"), str)
            or item.get("semantic_role") not in _ROLES
        ):
            _fail("ordinary_trade_mapping_column_invalid")
        column_numbers.append(item["column"])
        roles.append(item["semantic_role"])
    if column_numbers != sorted(set(column_numbers)) or not _REQUIRED <= set(roles):
        _fail("ordinary_trade_mapping_column_invalid")
    expected_fingerprint = structural_fingerprint(
        title_literal=value["title_literal"], columns=columns
    )
    if value.get("structural_fingerprint") != expected_fingerprint:
        _fail("ordinary_trade_mapping_fingerprint_invalid")
    _validated_amount_currency_bindings(value=value, columns=columns)
    side_values = value.get("side_values")
    if not isinstance(side_values, list) or not side_values:
        _fail("ordinary_trade_mapping_side_invalid")
    sides: dict[str, str] = {}
    for item in side_values:
        if (
            not isinstance(item, dict)
            or set(item) != {"source_literal", "normalized_value"}
            or not isinstance(item.get("source_literal"), str)
            or not item["source_literal"]
            or item.get("normalized_value") not in {"PURCHASE", "DISPOSAL"}
            or item["source_literal"] in sides
        ):
            _fail("ordinary_trade_mapping_side_invalid")
        sides[item["source_literal"]] = item["normalized_value"]
    qualification_ref = value.get("qualification_ref")
    if (
        not isinstance(qualification_ref, dict)
        or set(qualification_ref) != {"qualification_id", "receipt_sha256"}
        or not isinstance(qualification_ref.get("qualification_id"), str)
        or not qualification_ref["qualification_id"].startswith("otqual_")
        or not isinstance(qualification_ref.get("receipt_sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", qualification_ref["receipt_sha256"])
        is None
    ):
        _fail("ordinary_trade_mapping_qualification_ref_invalid")
    identity_material = {
        "structural_fingerprint": value["structural_fingerprint"],
        "columns": columns,
        "amount_currency_bindings": value["amount_currency_bindings"],
        "side_values": side_values,
        "qualification_ref": copy.deepcopy(qualification_ref),
    }
    if value["mapping_id"] != "otmap_" + _sha256_json(identity_material)[:32]:
        _fail("ordinary_trade_mapping_identity_invalid")
    return copy.deepcopy(dict(value))


def validate_schema_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a mapping candidate without granting production qualification."""

    return _validated_mapping(value)


def _validated_scoped_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"table_node_id", "mapping"}
        or not isinstance(value.get("table_node_id"), str)
        or not value["table_node_id"]
    ):
        _fail("ordinary_trade_case_mapping_scope_invalid")
    return {
        "table_node_id": value["table_node_id"],
        "mapping": _validated_mapping(value.get("mapping")),
    }


def _validated_amount_currency_bindings(
    *, value: Mapping[str, Any], columns: list[Mapping[str, Any]]
) -> None:
    bindings = value.get("amount_currency_bindings")
    if not isinstance(bindings, list) or not bindings:
        _fail("ordinary_trade_mapping_currency_binding_invalid")
    roles_by_column = {
        int(item["column"]): str(item["semantic_role"]) for item in columns
    }
    amount_columns = {
        column
        for column, role in roles_by_column.items()
        if role in {"gross_amount", "broker_commission", "exchange_commission"}
    }
    bound_amount_columns: list[int] = []
    for item in bindings:
        if (
            not isinstance(item, dict)
            or set(item) != {"amount_column", "currency_column"}
            or not isinstance(item.get("amount_column"), int)
            or not isinstance(item.get("currency_column"), int)
            or item["amount_column"] not in amount_columns
            or roles_by_column.get(item["currency_column"]) != "currency"
        ):
            _fail("ordinary_trade_mapping_currency_binding_invalid")
        bound_amount_columns.append(item["amount_column"])
    if (
        bound_amount_columns != sorted(set(bound_amount_columns))
        or set(bound_amount_columns) != amount_columns
    ):
        _fail("ordinary_trade_mapping_currency_binding_invalid")


def _table_rows(table: Mapping[str, Any]) -> dict[int, dict[int, dict[str, Any]]]:
    rows: dict[int, dict[int, dict[str, Any]]] = {}
    for cell in (table.get("content") or {}).get("cells", []):
        if not isinstance(cell, dict):
            _fail("ordinary_trade_canonical_table_invalid")
        row = cell.get("row")
        column = cell.get("column")
        if (
            not isinstance(row, int)
            or not isinstance(column, int)
            or row < 1
            or column < 1
        ):
            _fail("ordinary_trade_canonical_table_invalid")
        if column in rows.setdefault(row, {}):
            _fail("ordinary_trade_canonical_cell_duplicate")
        rows[row][column] = copy.deepcopy(cell)
    return rows


def ordinary_trade_canonical_table_rows(
    table: Mapping[str, Any],
    *,
    provenance: Any = None,
    source: Any = None,
) -> tuple[dict[int, dict[int, dict[str, Any]]], dict[int, str]]:
    """Return one validated Canonical cell grid and its Managed row roles."""

    rows = _table_rows(table)
    return rows, _managed_row_roles_by_number(
        table=table,
        rows=rows,
        provenance=provenance,
        source=source,
    )


def ordinary_trade_canonical_managed_header_view(
    *,
    canonical: Mapping[str, Any],
    canonical_binding: Mapping[str, str],
    table_node_id: str,
) -> dict[str, Any]:
    """Build one inactive source-bound primary-header representation."""

    if not isinstance(canonical, dict) or not validate_canonical_artifact(canonical)[
        "passed"
    ]:
        _fail("ordinary_trade_canonical_managed_header_view_canonical_invalid")
    binding = _canonical_binding(canonical=canonical, value=canonical_binding)
    if not isinstance(table_node_id, str) or not table_node_id:
        _fail("ordinary_trade_canonical_managed_header_view_invalid")
    matches = [
        node
        for node in canonical.get("nodes", [])
        if isinstance(node, Mapping)
        and node.get("node_type") == "TABLE"
        and node.get("node_id") == table_node_id
    ]
    if len(matches) != 1:
        _fail("ordinary_trade_canonical_managed_header_view_invalid")
    table = matches[0]
    rows = _table_rows(table)
    roles = _managed_contiguous_primary_header_row_roles(
        table=table,
        rows=rows,
        provenance=canonical.get("provenance"),
        source=canonical.get("source"),
    )
    if not roles:
        _fail("ordinary_trade_canonical_managed_header_view_invalid")
    content = table.get("content")
    metadata = content.get("metadata") if isinstance(content, Mapping) else None
    if not isinstance(metadata, Mapping):
        _fail("ordinary_trade_canonical_managed_header_view_invalid")
    sequence = metadata.get("managed_row_sequence")
    if not isinstance(sequence, list):
        _fail("ordinary_trade_canonical_managed_header_view_invalid")
    row_ids = {
        row_number: str(item["row_id"])
        for row_number, item in enumerate(sequence, start=1)
    }
    columns = _managed_header_view_columns(metadata.get("logical_columns"))
    column_ordinals = {
        str(column["column_id"]): int(column["ordinal"]) for column in columns
    }
    evidence = _managed_header_entry_evidence(
        rows=rows,
        roles=roles,
        provenance=canonical.get("provenance"),
        column_ordinals=column_ordinals,
        row_ids=row_ids,
    )
    _validate_managed_continuation_header_runs(roles=roles, evidence=evidence)
    expected_paths = {column_id: [] for column_id in column_ordinals}
    primary_paths = {column_id: [] for column_id in column_ordinals}
    continuation_paths = {column_id: [] for column_id in column_ordinals}
    for item in evidence:
        if item["role"] not in {"COLUMN_HEADER", "CONTINUATION_HEADER"}:
            continue
        binding_columns = list(
            dict.fromkeys(
                [
                    item["logical_column_id"],
                    *item["covers_logical_column_ids"],
                ]
            )
        )
        if item["column_binding_status"] != "BOUND" or not binding_columns:
            if item["role"] == "COLUMN_HEADER":
                _fail("ordinary_trade_canonical_managed_header_path_invalid")
            continue
        target = (
            primary_paths
            if item["role"] == "COLUMN_HEADER"
            else continuation_paths
        )
        for column_id in binding_columns:
            if column_id is None:
                continue
            expected_paths[column_id].append(item["entry_id"])
            target[column_id].append(item)

    output_columns = []
    continuation_columns = []
    for column in columns:
        column_id = str(column["column_id"])
        header_path = column.get("header_path")
        if (
            not isinstance(header_path, list)
            or not header_path
            or len(header_path) != len(set(header_path))
            or header_path != expected_paths[column_id]
            or not primary_paths[column_id]
        ):
            _fail("ordinary_trade_canonical_managed_header_path_invalid")
        output_columns.append(
            {
                "column": int(column["ordinal"]) + 1,
                "logical_column_id": column_id,
                "primary_header_path": [
                    _managed_header_path_item(item)
                    for item in primary_paths[column_id]
                ],
            }
        )
        continuation_columns.append(
            {
                "logical_column_id": column_id,
                "filtered_entry_refs": [
                    str(item["entry_id"]) for item in continuation_paths[column_id]
                ],
            }
        )
    material = {
        "schema_version": ORDINARY_TRADE_MANAGED_HEADER_VIEW_SCHEMA_VERSION,
        "representation_only": True,
        "consumer_eligible": False,
        "table_node_id": table_node_id,
        "canonical_binding": binding,
        "managed_binding": {
            "source_representation_owner": metadata[
                "source_representation_owner"
            ],
            "managed_whole_table_projection_id": metadata[
                "managed_whole_table_projection_id"
            ],
            "managed_document_id": metadata["managed_document_id"],
            "managed_document_integrity_sha256": metadata[
                "managed_document_integrity_sha256"
            ],
            "managed_table_id": metadata["managed_table_id"],
        },
        "primary_header_rows": [
            {"row": row, "row_id": row_ids[row]}
            for row, role in roles.items()
            if role == "COLUMN_HEADER"
        ],
        "columns": output_columns,
        "continuation_accounting": {
            "filtered_from_primary_paths": True,
            "rows": [
                {"row": row, "row_id": row_ids[row]}
                for row, role in roles.items()
                if role == "CONTINUATION_HEADER"
            ],
            "filtered_entry_refs": [
                str(item["entry_id"])
                for item in evidence
                if item["role"] == "CONTINUATION_HEADER"
            ],
            "columns": continuation_columns,
        },
    }
    return {
        **material,
        "header_view_sha256": _sha256_json(material),
    }


def ordinary_trade_canonical_managed_data_replay(
    *,
    canonical: Mapping[str, Any],
    canonical_binding: Mapping[str, str],
    table_node_id: str,
) -> dict[str, Any]:
    """Replay exact Managed DATA cells for inactive qualification evidence."""

    if not isinstance(canonical, dict) or not validate_canonical_artifact(canonical)[
        "passed"
    ]:
        _fail("ordinary_trade_canonical_managed_data_replay_canonical_invalid")
    binding = _canonical_binding(canonical=canonical, value=canonical_binding)
    if not isinstance(table_node_id, str) or not table_node_id:
        _fail("ordinary_trade_canonical_managed_data_replay_invalid")
    matches = [
        node
        for node in canonical.get("nodes", [])
        if isinstance(node, Mapping)
        and node.get("node_type") == "TABLE"
        and node.get("node_id") == table_node_id
    ]
    if len(matches) != 1:
        _fail("ordinary_trade_canonical_managed_data_replay_invalid")
    table = matches[0]
    rows = _table_rows(table)
    roles = _managed_contiguous_primary_header_row_roles(
        table=table,
        rows=rows,
        provenance=canonical.get("provenance"),
        source=canonical.get("source"),
    )
    if not roles or "UNKNOWN" in roles.values():
        _fail("ordinary_trade_canonical_managed_data_replay_roles_invalid")
    content = table.get("content")
    metadata = content.get("metadata") if isinstance(content, Mapping) else None
    sequence = metadata.get("managed_row_sequence") if isinstance(metadata, Mapping) else None
    if not isinstance(metadata, Mapping) or not isinstance(sequence, list):
        _fail("ordinary_trade_canonical_managed_data_replay_invalid")
    data_rows = []
    for row_number, role in roles.items():
        if role != "DATA":
            continue
        row_id = sequence[row_number - 1]["row_id"]
        data_rows.append(
            {
                "row": row_number,
                "row_id": row_id,
                "cells": [
                    {
                        "column": column,
                        "literal": _literal(cell),
                        "source_coordinate": cell.get("source_coordinate"),
                        "canonical_provenance_ref": cell["source_refs"][0],
                    }
                    for column, cell in sorted(rows[row_number].items())
                ],
            }
        )
    material = {
        "schema_version": ORDINARY_TRADE_MANAGED_DATA_REPLAY_SCHEMA_VERSION,
        "representation_only": True,
        "consumer_eligible": False,
        "table_node_id": table_node_id,
        "canonical_binding": binding,
        "managed_binding": {
            "source_representation_owner": metadata[
                "source_representation_owner"
            ],
            "managed_whole_table_projection_id": metadata[
                "managed_whole_table_projection_id"
            ],
            "managed_document_id": metadata["managed_document_id"],
            "managed_document_integrity_sha256": metadata[
                "managed_document_integrity_sha256"
            ],
            "managed_table_id": metadata["managed_table_id"],
        },
        "data_rows": data_rows,
    }
    return {**material, "data_replay_sha256": _sha256_json(material)}


def _managed_row_roles_by_number(
    *,
    table: Mapping[str, Any],
    rows: dict[int, dict[int, dict[str, Any]]],
    provenance: Any,
    source: Any,
) -> dict[int, str]:
    roles = _validated_managed_row_roles_by_number(
        table=table,
        rows=rows,
        provenance=provenance,
        source=source,
    )
    if not roles:
        return {}
    header_rows = [row for row, role in roles.items() if role == "COLUMN_HEADER"]
    if len(header_rows) != 1:
        _fail("ordinary_trade_canonical_managed_header_invalid")
    _validate_managed_primary_header_order(roles, first_header_row=header_rows[0])
    return roles


def _managed_contiguous_primary_header_row_roles(
    *,
    table: Mapping[str, Any],
    rows: dict[int, dict[int, dict[str, Any]]],
    provenance: Any,
    source: Any,
) -> dict[int, str]:
    roles = _validated_managed_row_roles_by_number(
        table=table,
        rows=rows,
        provenance=provenance,
        source=source,
    )
    if not roles:
        return {}
    header_rows = [row for row, role in roles.items() if role == "COLUMN_HEADER"]
    if not header_rows or header_rows != list(
        range(header_rows[0], header_rows[-1] + 1)
    ):
        _fail("ordinary_trade_canonical_managed_header_invalid")
    _validate_managed_primary_header_order(roles, first_header_row=header_rows[0])
    return roles


def _validated_managed_row_roles_by_number(
    *,
    table: Mapping[str, Any],
    rows: dict[int, dict[int, dict[str, Any]]],
    provenance: Any,
    source: Any,
) -> dict[int, str]:
    content = table.get("content")
    if not isinstance(content, Mapping):
        return {}
    managed_provenance_present = _table_has_managed_cell_provenance(
        rows=rows,
        provenance=provenance,
    )
    metadata = content.get("metadata")
    if not isinstance(metadata, Mapping):
        if managed_provenance_present:
            _fail("ordinary_trade_canonical_managed_authority_invalid")
        return {}
    owner_is_managed = (
        metadata.get("source_representation_owner")
        == _MANAGED_SOURCE_REPRESENTATION_OWNER
    )
    managed_markers_present = any(
        str(key).startswith("managed_")
        or key == "canonical_managed_whole_table_projection_connected"
        for key in metadata
    )
    if not owner_is_managed:
        if managed_markers_present or managed_provenance_present:
            _fail("ordinary_trade_canonical_managed_authority_invalid")
        return {}
    if not _managed_metadata_connected(metadata):
        _fail("ordinary_trade_canonical_managed_authority_invalid")
    if not isinstance(provenance, list):
        _fail("ordinary_trade_canonical_managed_authority_invalid")
    if (
        not isinstance(source, Mapping)
        or not _sha256_text(source.get("source_sha256"))
        or not isinstance(source.get("source_artifact_ref"), str)
        or not source.get("source_artifact_ref")
    ):
        _fail("ordinary_trade_canonical_managed_authority_invalid")
    provenance_by_id = {
        item.get("provenance_id"): item
        for item in provenance
        if isinstance(item, Mapping)
        and isinstance(item.get("provenance_id"), str)
        and item.get("provenance_id")
    }
    if len(provenance_by_id) != len(provenance):
        _fail("ordinary_trade_canonical_managed_authority_invalid")
    sequence = metadata.get("managed_row_sequence")
    if not isinstance(sequence, list) or not sequence:
        _fail("ordinary_trade_canonical_managed_row_sequence_invalid")
    roles: dict[int, str] = {}
    row_ids: set[str] = set()
    managed_provenance_refs: set[str] = set()
    for row_number, item in enumerate(sequence, start=1):
        if not isinstance(item, Mapping):
            _fail("ordinary_trade_canonical_managed_row_sequence_invalid")
        role = item.get("role")
        role_origin = item.get("role_origin")
        ordinal = item.get("ordinal")
        row_id = item.get("row_id")
        entry_texts = item.get("entry_texts")
        if (
            role not in _MANAGED_ROW_ROLES
            or role_origin not in _MANAGED_ROW_ROLE_ORIGINS
            or not isinstance(ordinal, int)
            or isinstance(ordinal, bool)
            or ordinal != row_number - 1
            or not isinstance(row_id, str)
            or not row_id
            or row_id in row_ids
            or not isinstance(entry_texts, list)
            or any(not isinstance(value, str) for value in entry_texts)
        ):
            _fail("ordinary_trade_canonical_managed_row_sequence_invalid")
        row_ids.add(row_id)
        cells = rows.get(row_number, {})
        if entry_texts != [
            _literal(cell) for _, cell in sorted(cells.items())
        ]:
            _fail("ordinary_trade_canonical_managed_row_sequence_invalid")
        _validate_managed_cell_provenance(
            cells=cells,
            row_id=row_id,
            role=str(role),
            metadata=metadata,
            provenance_by_id=provenance_by_id,
            seen_refs=managed_provenance_refs,
            source=source,
        )
        roles[row_number] = str(role)
    if set(rows) != set(roles):
        _fail("ordinary_trade_canonical_managed_row_sequence_invalid")
    return roles


def _validate_managed_primary_header_order(
    roles: Mapping[int, str],
    *,
    first_header_row: int,
) -> None:
    if any(
        row < first_header_row and role == "DATA"
        for row, role in roles.items()
    ):
        _fail("ordinary_trade_canonical_managed_header_order_invalid")


def _table_has_managed_cell_provenance(
    *,
    rows: Mapping[int, Mapping[int, Mapping[str, Any]]],
    provenance: Any,
) -> bool:
    if not isinstance(provenance, list):
        return False
    table_provenance_refs = {
        ref
        for cells in rows.values()
        for cell in cells.values()
        for ref in (cell.get("source_refs") or [])
        if isinstance(ref, str)
    }
    return any(
        isinstance(item, Mapping)
        and item.get("provenance_id") in table_provenance_refs
        and isinstance(item.get("source_locator"), Mapping)
        and item["source_locator"].get("kind") == "managed_whole_table_entry"
        for item in provenance
    )


def _managed_metadata_connected(metadata: Mapping[str, Any]) -> bool:
    return (
        metadata.get("source_format") == "pdf"
        and metadata.get("canonical_managed_whole_table_projection_connected")
        is True
        and metadata.get("managed_whole_table_projection_schema_version")
        == _MANAGED_WHOLE_TABLE_PROJECTION_SCHEMA_VERSION
        and metadata.get("managed_table_completeness_status") == "COMPLETE"
        and _prefixed_text(
            metadata.get("managed_whole_table_projection_id"),
            "managedtableprojection_",
        )
        and _prefixed_text(metadata.get("managed_document_id"), "document_pdf_")
        and _prefixed_text(metadata.get("managed_table_id"), "table_")
        and _sha256_text(metadata.get("managed_document_integrity_sha256"))
    )


def _validate_managed_cell_provenance(
    *,
    cells: Mapping[int, Mapping[str, Any]],
    row_id: str,
    role: str,
    metadata: Mapping[str, Any],
    provenance_by_id: Mapping[str, Mapping[str, Any]],
    seen_refs: set[str],
    source: Mapping[str, Any],
) -> None:
    for cell in cells.values():
        refs = cell.get("source_refs")
        if (
            not isinstance(refs, list)
            or len(refs) != 1
            or not isinstance(refs[0], str)
            or refs[0] in seen_refs
        ):
            _fail("ordinary_trade_canonical_managed_cell_provenance_invalid")
        seen_refs.add(refs[0])
        record = provenance_by_id.get(refs[0])
        locator = record.get("source_locator") if isinstance(record, Mapping) else None
        if (
            not isinstance(locator, Mapping)
            or locator.get("kind") != "managed_whole_table_entry"
            or locator.get("managed_row_id") != row_id
            or locator.get("managed_row_role") != role
            or locator.get("managed_whole_table_projection_id")
            != metadata.get("managed_whole_table_projection_id")
            or locator.get("managed_document_id")
            != metadata.get("managed_document_id")
            or locator.get("managed_table_id") != metadata.get("managed_table_id")
            or not _prefixed_text(locator.get("managed_entry_id"), "entry_")
            or cell.get("source_coordinate")
            != f"{row_id}:{locator.get('managed_entry_id')}"
            or record.get("source_ref") != source.get("source_artifact_ref")
            or refs[0]
            != "prov_"
            + _sha256_json([source.get("source_sha256"), dict(locator)])[:24]
        ):
            _fail("ordinary_trade_canonical_managed_cell_provenance_invalid")


def _managed_header_view_columns(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        _fail("ordinary_trade_canonical_managed_header_path_invalid")
    result = []
    column_ids: set[str] = set()
    for expected_ordinal, column in enumerate(value):
        if not isinstance(column, Mapping):
            _fail("ordinary_trade_canonical_managed_header_path_invalid")
        column_id = column.get("column_id")
        if (
            not isinstance(column_id, str)
            or not column_id
            or column_id in column_ids
            or column.get("ordinal") != expected_ordinal
        ):
            _fail("ordinary_trade_canonical_managed_header_path_invalid")
        column_ids.add(column_id)
        result.append(copy.deepcopy(dict(column)))
    return result


def _managed_header_entry_evidence(
    *,
    rows: Mapping[int, Mapping[int, Mapping[str, Any]]],
    roles: Mapping[int, str],
    provenance: Any,
    column_ordinals: Mapping[str, int],
    row_ids: Mapping[int, str],
) -> list[dict[str, Any]]:
    if not isinstance(provenance, list):
        _fail("ordinary_trade_canonical_managed_entry_binding_invalid")
    provenance_by_id = {
        item.get("provenance_id"): item
        for item in provenance
        if isinstance(item, Mapping)
        and isinstance(item.get("provenance_id"), str)
        and item.get("provenance_id")
    }
    if len(provenance_by_id) != len(provenance):
        _fail("ordinary_trade_canonical_managed_entry_binding_invalid")
    seen_entry_ids: set[str] = set()
    result = []
    for row_number, cells in sorted(rows.items()):
        for column, cell in sorted(cells.items()):
            refs = cell.get("source_refs")
            record = (
                provenance_by_id.get(refs[0])
                if isinstance(refs, list) and len(refs) == 1
                else None
            )
            locator = record.get("source_locator") if isinstance(record, Mapping) else None
            if not isinstance(locator, Mapping):
                _fail("ordinary_trade_canonical_managed_entry_binding_invalid")
            entry_id = locator.get("managed_entry_id")
            if (
                not isinstance(entry_id, str)
                or not entry_id
                or entry_id in seen_entry_ids
            ):
                _fail("ordinary_trade_canonical_managed_entry_binding_invalid")
            seen_entry_ids.add(entry_id)
            binding = _managed_header_entry_binding(
                locator,
                column_ordinals=column_ordinals,
            )
            result.append(
                {
                    "row": row_number,
                    "row_id": row_ids[row_number],
                    "column": column,
                    "role": roles[row_number],
                    "entry_id": entry_id,
                    "literal": _literal(cell),
                    "source_refs": copy.deepcopy(refs),
                    **binding,
                }
            )
    return result


def _validate_managed_continuation_header_runs(
    *,
    roles: Mapping[int, str],
    evidence: Iterable[Mapping[str, Any]],
) -> None:
    primary_rows = [row for row, role in roles.items() if role == "COLUMN_HEADER"]
    continuation_rows = [
        row for row, role in roles.items() if role == "CONTINUATION_HEADER"
    ]
    if not continuation_rows:
        return
    if not primary_rows or any(row <= primary_rows[-1] for row in continuation_rows):
        _fail("ordinary_trade_canonical_managed_continuation_header_invalid")

    runs: list[list[int]] = []
    for row in continuation_rows:
        if not runs or row != runs[-1][-1] + 1:
            runs.append([row])
        else:
            runs[-1].append(row)
    by_row: dict[int, list[Mapping[str, Any]]] = {}
    for item in evidence:
        by_row.setdefault(int(item["row"]), []).append(item)
    expected = [_managed_header_row_shape(by_row[row]) for row in primary_rows]
    for run in runs:
        if len(run) != len(primary_rows) or [
            _managed_header_row_shape(by_row[row]) for row in run
        ] != expected:
            _fail("ordinary_trade_canonical_managed_continuation_header_invalid")


def _managed_header_row_shape(
    evidence: Iterable[Mapping[str, Any]],
) -> list[tuple[Any, ...]]:
    return [
        (
            int(item["column"]),
            str(item["literal"]),
            item["column_binding_status"],
            item["logical_column_id"],
            tuple(item["covers_logical_column_ids"]),
        )
        for item in evidence
    ]


def _managed_header_entry_binding(
    locator: Mapping[str, Any],
    *,
    column_ordinals: Mapping[str, int],
) -> dict[str, Any]:
    if (
        locator.get("managed_entry_binding_schema_version")
        != _MANAGED_ENTRY_BINDING_SCHEMA_VERSION
        or "managed_column_binding_status" not in locator
        or "managed_logical_column_id" not in locator
        or "managed_covers_logical_column_ids" not in locator
    ):
        _fail("ordinary_trade_canonical_managed_entry_binding_invalid")
    status = locator.get("managed_column_binding_status")
    logical_column_id = locator.get("managed_logical_column_id")
    covers = locator.get("managed_covers_logical_column_ids")
    expected_status = (
        "BOUND" if logical_column_id is not None or covers else "NOT_APPLICABLE"
    )
    if (
        logical_column_id is not None
        and (
            not isinstance(logical_column_id, str)
            or logical_column_id not in column_ordinals
        )
    ) or (
        not isinstance(covers, list)
        or any(
            not isinstance(column_id, str) or column_id not in column_ordinals
            for column_id in covers
        )
        or len(covers) != len(set(covers))
        or bool(covers) and len(covers) < 2
        or covers
        != sorted(covers, key=lambda column_id: column_ordinals[column_id])
        or logical_column_id is not None
        and covers
        and covers[0] != logical_column_id
        or status != expected_status
    ):
        _fail("ordinary_trade_canonical_managed_entry_binding_invalid")
    return {
        "column_binding_status": status,
        "logical_column_id": logical_column_id,
        "covers_logical_column_ids": copy.deepcopy(covers),
    }


def _managed_header_path_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "row": int(item["row"]),
        "row_id": str(item["row_id"]),
        "entry_id": str(item["entry_id"]),
        "literal": str(item["literal"]),
        "source_refs": copy.deepcopy(item["source_refs"]),
        "canonical_provenance_ref": str(item["source_refs"][0]),
    }


def _prefixed_text(value: Any, prefix: str) -> bool:
    return isinstance(value, str) and value.startswith(prefix) and len(value) > len(prefix)


def _sha256_text(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _managed_header_row_numbers(
    managed_row_roles: Mapping[int, str],
) -> frozenset[int] | None:
    if not managed_row_roles:
        return None
    return frozenset(
        row for row, role in managed_row_roles.items() if role == "COLUMN_HEADER"
    )


def _managed_mapped_data_rows(
    *,
    rows: dict[int, dict[int, dict[str, Any]]],
    managed_row_roles: Mapping[int, str],
    after_row: int,
) -> dict[int, dict[int, dict[str, Any]]]:
    if not managed_row_roles:
        return {row: cells for row, cells in rows.items() if row > after_row}
    return {
        row: cells
        for row, cells in rows.items()
        if row > after_row and managed_row_roles.get(row) == "DATA"
    }


def _managed_unmapped_rows(
    *,
    rows: dict[int, dict[int, dict[str, Any]]],
    managed_row_roles: Mapping[int, str],
    after_row: int = 0,
) -> dict[int, dict[int, dict[str, Any]]]:
    if not managed_row_roles:
        return {row: cells for row, cells in rows.items() if row > after_row}
    return {
        row: cells
        for row, cells in rows.items()
        if row > after_row
        and managed_row_roles.get(row) not in _MANAGED_STRUCTURAL_ROW_ROLES
    }


def _same_row_literals(
    left: Mapping[int, Mapping[str, Any]],
    right: Mapping[int, Mapping[str, Any]],
) -> bool:
    return set(left) == set(right) and all(
        _literal(left[column]) == _literal(right[column]) for column in left
    )


def _matching_mappings(
    *,
    rows: dict[int, dict[int, dict[str, Any]]],
    mappings: tuple[dict[str, Any], ...],
    candidate_header_rows: frozenset[int] | None = None,
) -> list[tuple[dict[str, Any], int]]:
    result = []
    for mapping in mappings:
        expected = {
            item["column"]: item["header_literal"] for item in mapping["columns"]
        }
        row_matches = [
            row_number
            for row_number, cells in rows.items()
            if (candidate_header_rows is None or row_number in candidate_header_rows)
            and set(cells) == set(expected)
            and all(
                _literal(cells[column]) == literal
                for column, literal in expected.items()
            )
        ]
        title = mapping["title_literal"]
        if title is not None:
            row_matches = [
                row_number
                for row_number in row_matches
                if any(
                    _literal(cell) == title
                    for prior, cells in rows.items()
                    if prior < row_number
                    for cell in cells.values()
                )
            ]
        if len(row_matches) > 1:
            _fail("ordinary_trade_mapping_header_ambiguous")
        if row_matches:
            result.append((mapping, row_matches[0]))
    return result


def _matching_scoped_mappings(
    *,
    table: Mapping[str, Any],
    rows: dict[int, dict[int, dict[str, Any]]],
    mappings: tuple[dict[str, Any], ...],
    candidate_header_rows: frozenset[int] | None = None,
) -> list[tuple[dict[str, Any], int]]:
    scoped = tuple(
        item["mapping"]
        for item in mappings
        if item["table_node_id"] == table.get("node_id")
    )
    return _matching_mappings(
        rows=rows,
        mappings=scoped,
        candidate_header_rows=candidate_header_rows,
    )


def _table_numeric_convention(
    *,
    rows: dict[int, dict[int, dict[str, Any]]],
    mapping: dict[str, Any],
) -> str | None:
    numeric_columns = {
        item["column"]
        for item in mapping["columns"]
        if item["semantic_role"]
        in {
            "quantity",
            "unit_price",
            "gross_amount",
            "broker_commission",
            "exchange_commission",
            "accrued_interest",
        }
    }
    literals = [
        _literal(cell).strip()
        for cells in rows.values()
        for column, cell in cells.items()
        if column in numeric_columns and _literal(cell).strip()
    ]
    comma_dot = any(
        _COMMA_GROUPED_DOT.fullmatch(value) is not None for value in literals
    )
    dot_comma = any(
        _DOT_GROUPED_COMMA.fullmatch(value) is not None for value in literals
    )
    if comma_dot and dot_comma:
        _fail("ordinary_trade_numeric_convention_ambiguous")
    if comma_dot:
        return "COMMA_GROUPED_DOT_DECIMAL"
    if dot_comma:
        return "DOT_GROUPED_COMMA_DECIMAL"
    return None


def _mapped_observation(
    *,
    binding: dict[str, str],
    table: Mapping[str, Any],
    row: int,
    cells: dict[int, dict[str, Any]],
    mapping: dict[str, Any],
    numeric_convention: str | None,
) -> dict[str, Any]:
    fields = [
        _field(
            binding=binding,
            table=table,
            cell=cells[item["column"]],
            role=item["semantic_role"],
        )
        for item in mapping["columns"]
        if item["column"] in cells
    ]
    by_role = _by_role(fields)
    record_anchor_roles = {"trade_date", "side", "quantity", "gross_amount"}
    has_record_anchor = any(
        _single_nonempty(by_role, role) is not None for role in record_anchor_roles
    )
    has_named_financial_value = any(
        field["literal"].strip()
        and field["semantic_role"] not in _DISPLAY_ONLY_NON_RECORD_ROLES
        for field in fields
    )
    if not has_record_anchor and not has_named_financial_value:
        return _observation(
            binding=binding,
            table=table,
            row=row,
            fields=fields,
            disposition="SOURCE_RETAINED_NO_CONSUMER",
            reason="MAPPED_TABLE_NON_RECORD_ROW",
            mapping_id=mapping["mapping_id"],
            numeric_convention=numeric_convention,
        )
    side_literals = {
        item["source_literal"]: item["normalized_value"]
        for item in mapping["side_values"]
    }
    ready = all(
        _single_nonempty(by_role, role) is not None for role in _REQUIRED - {"currency"}
    )
    gross = _single_nonempty(by_role, "gross_amount")
    ready = ready and gross is not None
    ready = ready and _currency_field_for_amount(
        amount=gross, by_role=by_role, mapping=mapping
    ) is not None
    side = _single_nonempty(by_role, "side")
    ready = ready and side is not None and side["literal"] in side_literals
    if ready:
        ready = _row_values_runtime_valid(
            by_role=by_role,
            mapping=mapping,
            numeric_convention=numeric_convention,
        )
    return _observation(
        binding=binding,
        table=table,
        row=row,
        fields=fields,
        disposition="RUNTIME_READY" if ready else "RELEVANT_UNMAPPED",
        reason=None if ready else "ORDINARY_TRADE_ROW_CONTRACT_INCOMPLETE",
        mapping_id=mapping["mapping_id"],
        numeric_convention=numeric_convention,
    )


def _unmapped_table_rows(
    *,
    binding: dict[str, str],
    table: Mapping[str, Any],
    rows: dict[int, dict[int, dict[str, Any]]],
    reason: str,
    disposition: str = "RELEVANT_UNMAPPED",
) -> list[dict[str, Any]]:
    result = []
    for row, cells in sorted(rows.items()):
        fields = [
            _field(binding=binding, table=table, cell=cell, role="unmapped")
            for _, cell in sorted(cells.items())
            if _literal(cell)
        ]
        if fields:
            result.append(
                _observation(
                    binding=binding,
                    table=table,
                    row=row,
                    fields=fields,
                    disposition=disposition,
                    reason=reason,
                    mapping_id=None,
                    numeric_convention=None,
                )
            )
    return result


def _validated_table_resolution(value: Mapping[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(value, Mapping)
        or set(value)
        != {
            "table_node_id",
            "header_row",
            "structural_fingerprint",
            "evidence_surface",
            "disposition",
        }
        or not isinstance(value.get("table_node_id"), str)
        or not value["table_node_id"]
        or not isinstance(value.get("header_row"), int)
        or value["header_row"] < 1
        or value.get("disposition")
        not in {
            "SECURITY_TRADES",
            "NO_NAMED_CONSUMER",
            "UNSUPPORTED_FINANCIAL_MEANING",
        }
    ):
        _fail("ordinary_trade_table_resolution_invalid")
    surface = value.get("evidence_surface")
    if (
        not isinstance(surface, dict)
        or set(surface) != {"title_literal", "headers"}
        or surface.get("title_literal") is not None
        or not isinstance(surface.get("headers"), list)
        or not surface["headers"]
    ):
        _fail("ordinary_trade_table_resolution_invalid")
    headers = surface["headers"]
    if any(
        not isinstance(item, dict)
        or set(item) != {"column", "literal"}
        or not isinstance(item.get("column"), int)
        or item["column"] < 1
        or not isinstance(item.get("literal"), str)
        for item in headers
    ):
        _fail("ordinary_trade_table_resolution_invalid")
    expected = structural_fingerprint(
        title_literal=None,
        columns=[
            {"column": item["column"], "header_literal": item["literal"]}
            for item in headers
        ],
    )
    if value.get("structural_fingerprint") != expected:
        _fail("ordinary_trade_table_resolution_fingerprint_invalid")
    return copy.deepcopy(dict(value))


def _matching_table_resolutions(
    *,
    table: Mapping[str, Any],
    rows: dict[int, dict[int, dict[str, Any]]],
    resolutions: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    result = []
    for resolution in resolutions:
        if resolution["table_node_id"] != table.get("node_id"):
            continue
        cells = rows.get(resolution["header_row"])
        expected = {
            item["column"]: item["literal"]
            for item in resolution["evidence_surface"]["headers"]
        }
        if (
            cells is None
            or set(cells) != set(expected)
            or any(
                _literal(cells[column]) != literal
                for column, literal in expected.items()
            )
        ):
            _fail("ordinary_trade_table_resolution_surface_stale")
        result.append(resolution)
    return result


def _field(
    *,
    binding: dict[str, str],
    table: Mapping[str, Any],
    cell: Mapping[str, Any],
    role: str,
) -> dict[str, Any]:
    node_id = str(table.get("node_id") or "")
    coordinate = str(cell.get("source_coordinate") or "")
    refs = cell.get("source_refs")
    if not node_id or not coordinate or not isinstance(refs, list) or not refs:
        _fail("ordinary_trade_canonical_cell_provenance_missing")
    row = int(cell["row"])
    column = int(cell["column"])
    source_ref = (
        f"canonical:{binding['canonical_version_id']}:{node_id}:r{row}:c{column}"
    )
    return {
        "semantic_role": role,
        "source_ref": source_ref,
        "literal": _literal(cell),
        "canonical_cell": {
            "node_id": node_id,
            "row": row,
            "column": column,
            "source_coordinate": coordinate,
            "provenance_refs": copy.deepcopy(refs),
        },
    }


def _observation(
    *,
    binding: dict[str, str],
    table: Mapping[str, Any],
    row: int,
    fields: list[dict[str, Any]],
    disposition: str,
    reason: str | None,
    mapping_id: str | None,
    numeric_convention: str | None,
) -> dict[str, Any]:
    node_id = str(table["node_id"])
    observation_id = (
        "bso_"
        + _sha256_json(
            {
                "canonical_root_sha256": binding["canonical_root_sha256"],
                "node_id": node_id,
                "row": row,
                "source_refs": [item["source_ref"] for item in fields],
            }
        )[:32]
    )
    return {
        "schema_version": SOURCE_OBSERVATION_SCHEMA_VERSION,
        "observation_id": observation_id,
        "table_node_id": node_id,
        "row": row,
        "mapping_id": mapping_id,
        "numeric_convention": numeric_convention,
        "disposition": disposition,
        "reason_code": reason,
        "fields": fields,
    }


def _runtime_records(
    *, observation: dict[str, Any], mapping: dict[str, Any]
) -> list[dict[str, Any]]:
    by_role = _by_role(observation["fields"])
    numeric_convention = observation.get("numeric_convention")
    side_field = _required_field(by_role, "side")
    sides = {
        item["source_literal"]: item["normalized_value"]
        for item in mapping["side_values"]
    }
    normalized_side = sides.get(side_field["literal"])
    if normalized_side not in {"PURCHASE", "DISPOSAL"}:
        _fail("ordinary_trade_side_unmapped")
    gross_amount = _required_field(by_role, "gross_amount")
    currency = _currency_field_for_amount(
        amount=gross_amount, by_role=by_role, mapping=mapping
    )
    if currency is None:
        _fail("ordinary_trade_runtime_currency_ambiguous")
    common = [
        _runtime_role(
            "date", _required_field(by_role, "trade_date"), numeric_convention
        ),
        _runtime_role(
            "asset", _required_field(by_role, "asset_name"), numeric_convention
        ),
        _runtime_role(
            "quantity", _required_field(by_role, "quantity"), numeric_convention
        ),
        _runtime_role(
            "unit_price", _required_field(by_role, "unit_price"), numeric_convention
        ),
        _runtime_role(
            "amount", gross_amount, numeric_convention
        ),
        _runtime_role("currency", currency, numeric_convention),
    ]
    records = [
        _runtime_record(
            observation=observation,
            record_type=(
                "SECURITY_PURCHASE"
                if normalized_side == "PURCHASE"
                else "SECURITY_DISPOSAL"
            ),
            roles=common,
            claim_refs=[side_field["source_ref"]],
        )
    ]
    for commission in [
        *by_role.get("broker_commission", []),
        *by_role.get("exchange_commission", []),
    ]:
        if not commission["literal"] or _is_zero(commission["literal"]):
            continue
        commission_currency = _currency_field_for_amount(
            amount=commission, by_role=by_role, mapping=mapping
        )
        if commission_currency is None:
            _fail("ordinary_trade_runtime_currency_binding_missing")
        records.append(
            _runtime_record(
                observation=observation,
                record_type="TRANSACTION_CHARGE",
                roles=[
                    _runtime_role(
                        "date",
                        _required_field(by_role, "trade_date"),
                        numeric_convention,
                    ),
                    _runtime_role(
                        "asset",
                        _required_field(by_role, "asset_name"),
                        numeric_convention,
                    ),
                    _runtime_role("amount", commission, numeric_convention),
                    _runtime_role(
                        "currency", commission_currency, numeric_convention
                    ),
                ],
                claim_refs=[commission["source_ref"]],
            )
        )
    return records


def _runtime_role(
    role: str,
    field: dict[str, Any],
    numeric_convention: str | None,
) -> dict[str, Any]:
    value, transform = normalize_runtime_value(
        role,
        field["literal"],
        numeric_convention=numeric_convention,
    )
    return {
        "role": role,
        "value": value,
        "source_binding": {
            "source_ref": field["source_ref"],
            "source_literal": field["literal"],
            "deterministic_transform": transform,
            "canonical_cell": copy.deepcopy(field["canonical_cell"]),
        },
    }


def _runtime_record(
    *,
    observation: dict[str, Any],
    record_type: str,
    roles: list[dict[str, Any]],
    claim_refs: list[str],
) -> dict[str, Any]:
    record_id = (
        "bstr_"
        + _sha256_json(
            {
                "observation_id": observation["observation_id"],
                "record_type": record_type,
                "source_refs": [item["source_binding"]["source_ref"] for item in roles],
            }
        )[:32]
    )
    return {
        "runtime_record_id": record_id,
        "source_observation_id": observation["observation_id"],
        "record_type": record_type,
        "annotation_target": {
            "kind": "table_row",
            "node_id": observation["table_node_id"],
            "row": observation["row"],
        },
        "claim_refs": copy.deepcopy(claim_refs),
        "roles": roles,
    }


def _validate_projection_lineage(
    *, observations: list[dict[str, Any]], runtime_records: list[dict[str, Any]]
) -> None:
    observation_ids = [item.get("observation_id") for item in observations]
    if len(observation_ids) != len(set(observation_ids)):
        _fail("ordinary_trade_observation_duplicate")
    observations_by_id = {item["observation_id"]: item for item in observations}
    record_ids = [item.get("runtime_record_id") for item in runtime_records]
    if len(record_ids) != len(set(record_ids)):
        _fail("ordinary_trade_runtime_record_duplicate")
    for observation in observations:
        if observation.get("disposition") not in _DISPOSITIONS:
            _fail("ordinary_trade_observation_invalid")
    records_by_observation: dict[str, list[dict[str, Any]]] = {}
    charge_amount_refs: list[str] = []
    for record in runtime_records:
        observation = observations_by_id.get(record.get("source_observation_id"))
        if observation is None or observation.get("disposition") != "RUNTIME_READY":
            _fail("ordinary_trade_runtime_observation_invalid")
        observation_id = observation["observation_id"]
        records_by_observation.setdefault(observation_id, []).append(record)
        if record.get("annotation_target") != {
            "kind": "table_row",
            "node_id": observation.get("table_node_id"),
            "row": observation.get("row"),
        }:
            _fail("ordinary_trade_runtime_target_invalid")
        literals = {item["source_ref"]: item for item in observation.get("fields", [])}
        claim_refs = record.get("claim_refs")
        if (
            not isinstance(claim_refs, list)
            or not claim_refs
            or len(claim_refs) != len(set(claim_refs))
            or any(item not in literals for item in claim_refs)
        ):
            _fail("ordinary_trade_runtime_claim_lineage_invalid")
        for role in record.get("roles", []):
            source = role.get("source_binding") or {}
            field = literals.get(source.get("source_ref"))
            if (
                field is None
                or source.get("source_literal") != field.get("literal")
                or source.get("canonical_cell") != field.get("canonical_cell")
            ):
                _fail("ordinary_trade_runtime_lineage_invalid")
            expected, transform = normalize_runtime_value(
                str(role.get("role")),
                str(field.get("literal")),
                numeric_convention=observation.get("numeric_convention"),
            )
            if (
                role.get("value") != expected
                or source.get("deterministic_transform") != transform
            ):
                _fail("ordinary_trade_runtime_value_not_deterministic")
        if record.get("record_type") == "TRANSACTION_CHARGE":
            amount_roles = [
                item for item in record.get("roles", []) if item.get("role") == "amount"
            ]
            if len(amount_roles) != 1 or claim_refs != [
                amount_roles[0]["source_binding"]["source_ref"]
            ]:
                _fail("ordinary_trade_charge_binding_invalid")
            charge_amount_refs.append(claim_refs[0])
        elif record.get("record_type") not in {
            "SECURITY_PURCHASE",
            "SECURITY_DISPOSAL",
        }:
            _fail("ordinary_trade_runtime_record_type_invalid")
    if len(charge_amount_refs) != len(set(charge_amount_refs)):
        _fail("ordinary_trade_charge_source_duplicate")
    for observation in observations:
        if observation.get("disposition") != "RUNTIME_READY":
            continue
        records = records_by_observation.get(observation["observation_id"], [])
        security_records = [
            item
            for item in records
            if item.get("record_type") in {"SECURITY_PURCHASE", "SECURITY_DISPOSAL"}
        ]
        if len(security_records) != 1:
            _fail("ordinary_trade_security_record_cardinality_invalid")


def _validate_projection_against_canonical(
    *, canonical: Mapping[str, Any], observations: list[dict[str, Any]]
) -> None:
    provenance_ids = {
        item.get("provenance_id")
        for item in canonical.get("provenance", [])
        if isinstance(item, dict)
    }
    if not provenance_ids:
        _fail("ordinary_trade_canonical_provenance_missing")
    for observation in observations:
        for field in observation.get("fields", []):
            refs = (field.get("canonical_cell") or {}).get("provenance_refs")
            if (
                not isinstance(refs, list)
                or not refs
                or any(ref not in provenance_ids for ref in refs)
            ):
                _fail("ordinary_trade_canonical_provenance_unresolved")


def _literal(cell: Mapping[str, Any]) -> str:
    value = cell.get("displayed_value")
    if not isinstance(value, str):
        value = cell.get("value")
    return value if isinstance(value, str) else ""


def _by_role(fields: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for item in fields:
        result.setdefault(item["semantic_role"], []).append(item)
    return result


def _single_nonempty(
    by_role: dict[str, list[dict[str, Any]]], role: str
) -> dict[str, Any] | None:
    values = [item for item in by_role.get(role, []) if item["literal"]]
    return values[0] if len(values) == 1 else None


def _required_field(
    by_role: dict[str, list[dict[str, Any]]], role: str
) -> dict[str, Any]:
    value = _single_nonempty(by_role, role)
    if value is None:
        _fail("ordinary_trade_runtime_role_ambiguous")
    return value


def _currency_field_for_amount(
    *,
    amount: dict[str, Any],
    by_role: dict[str, list[dict[str, Any]]],
    mapping: dict[str, Any],
) -> dict[str, Any] | None:
    amount_column = amount["canonical_cell"]["column"]
    bindings = [
        item
        for item in mapping["amount_currency_bindings"]
        if item["amount_column"] == amount_column
    ]
    if len(bindings) != 1:
        return None
    currency_column = bindings[0]["currency_column"]
    candidates = [
        item
        for item in by_role.get("currency", [])
        if item["literal"]
        and item["canonical_cell"]["column"] == currency_column
    ]
    return candidates[0] if len(candidates) == 1 else None


def _row_values_runtime_valid(
    *,
    by_role: dict[str, list[dict[str, Any]]],
    mapping: dict[str, Any],
    numeric_convention: str | None,
) -> bool:
    gross = _single_nonempty(by_role, "gross_amount")
    if gross is None:
        return False
    currency = _currency_field_for_amount(
        amount=gross, by_role=by_role, mapping=mapping
    )
    if currency is None:
        return False
    bindings = (
        ("date", _single_nonempty(by_role, "trade_date")),
        ("asset", _single_nonempty(by_role, "asset_name")),
        ("quantity", _single_nonempty(by_role, "quantity")),
        ("unit_price", _single_nonempty(by_role, "unit_price")),
        ("amount", _single_nonempty(by_role, "gross_amount")),
        ("currency", currency),
    )
    try:
        for role, field in bindings:
            if field is None:
                return False
            normalize_runtime_value(
                role,
                field["literal"],
                numeric_convention=numeric_convention,
            )
    except OrdinaryTradeSemanticCompilerError:
        return False
    return True


def _decimal_literal(value: str, *, numeric_convention: str | None = None) -> str:
    if (
        numeric_convention == "COMMA_GROUPED_DOT_DECIMAL"
        and _COMMA_GROUPED_INTEGER.fullmatch(value) is not None
    ):
        return value.replace(",", "")
    if _PLAIN_DECIMAL.fullmatch(value) is not None:
        return value.replace(",", ".")
    if _SPACE_DECIMAL.fullmatch(value) is not None:
        compact = re.sub(r"[ \u00a0\u202f]", "", value)
        return compact.replace(",", ".")
    if _COMMA_GROUPED_DOT.fullmatch(value) is not None:
        return value.replace(",", "")
    if _DOT_GROUPED_COMMA.fullmatch(value) is not None:
        return value.replace(".", "").replace(",", ".")
    _fail("ordinary_trade_runtime_decimal_invalid")


def _is_zero(value: str) -> bool:
    try:
        return Decimal(_decimal_literal(value.strip())) == 0
    except (InvalidOperation, OrdinaryTradeSemanticCompilerError):
        return False


def _sha256_json(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OrdinaryTradeSemanticCompilerError("ordinary_trade_json_invalid") from exc
    return hashlib.sha256(encoded).hexdigest()


def _fail(code: str) -> None:
    raise OrdinaryTradeSemanticCompilerError(code)


__all__ = [
    "FACTORY_REQUIRED",
    "FORBIDDEN",
    "ORDINARY_TRADE_MANAGED_CASE_MAPPING_SCHEMA_VERSION",
    "ORDINARY_TRADE_MANAGED_DATA_REPLAY_SCHEMA_VERSION",
    "ORDINARY_TRADE_MANAGED_HEADER_VIEW_SCHEMA_VERSION",
    "ORDINARY_TRADE_MAPPING_SCHEMA_VERSION",
    "ORDINARY_TRADE_PROJECTION_SCHEMA_VERSION",
    "OrdinaryTradeSemanticCompiler",
    "OrdinaryTradeSemanticCompilerError",
    "OrdinaryTradeSemanticCompilerFactory",
    "compile_managed_header_case_mapping_candidate",
    "compile_schema_mapping",
    "normalize_runtime_value",
    "ordinary_trade_canonical_managed_data_replay",
    "structural_fingerprint",
    "validate_managed_header_case_mapping_candidate",
    "validate_schema_mapping",
    "validate_ordinary_trade_projection",
]
