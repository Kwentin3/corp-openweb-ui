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


ORDINARY_TRADE_MAPPING_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_schema_mapping_v2"
)
ORDINARY_TRADE_PROJECTION_SCHEMA_VERSION = (
    "broker_reports_ordinary_trade_runtime_projection_v3"
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
_DISPOSITIONS = {"RUNTIME_READY", "RELEVANT_UNMAPPED"}
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
_MAPPING_KEYS = {
    "schema_version",
    "mapping_id",
    "structural_fingerprint",
    "table_type",
    "title_literal",
    "columns",
    "amount_currency_bindings",
    "side_values",
    "semantic_decisions",
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
    ) -> dict[str, Any]:
        binding = _canonical_binding(canonical=canonical, value=canonical_binding)
        accepted = tuple(_validated_mapping(item) for item in mappings)
        fingerprints = [item["structural_fingerprint"] for item in accepted]
        if len(fingerprints) != len(set(fingerprints)):
            _fail("ordinary_trade_mapping_fingerprint_duplicate")

        observations: list[dict[str, Any]] = []
        runtime_records: list[dict[str, Any]] = []
        mapping_matches: dict[str, int] = {item["mapping_id"]: 0 for item in accepted}
        table_nodes = [
            item
            for item in canonical.get("nodes", [])
            if isinstance(item, dict) and item.get("node_type") == "TABLE"
        ]
        for table in table_nodes:
            rows = _table_rows(table)
            matches = _matching_mappings(rows=rows, mappings=accepted)
            if len(matches) > 1:
                _fail("ordinary_trade_table_mapping_ambiguous")
            if not matches:
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
            numeric_convention = _table_numeric_convention(rows=rows, mapping=mapping)
            for row_number in sorted(row for row in rows if row > header_row):
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

        if any(count > 1 for count in mapping_matches.values()):
            _fail("ordinary_trade_mapping_reuse_ambiguous")
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
            "compiler_contract": {
                "canonical_is_source_authority": True,
                "model_owns_rows": False,
                "model_owns_financial_values": False,
                "value_based_deduplication": False,
                "unknown_schema_terminal": "RELEVANT_UNMAPPED",
                "structural_lineage_inferred": False,
            },
            "semantic_decisions": [
                {
                    "mapping_id": item["mapping_id"],
                    "structural_fingerprint": item["structural_fingerprint"],
                    "decisions": copy.deepcopy(item["semantic_decisions"]),
                }
                for item in accepted
                if mapping_matches[item["mapping_id"]] > 0
            ],
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


def compile_schema_mapping(
    *,
    title_literal: str | None,
    headers: Iterable[Mapping[str, Any]],
    model_columns: Iterable[Mapping[str, Any]],
    amount_currency_bindings: Iterable[Mapping[str, int]],
    side_values: Iterable[Mapping[str, str]],
    semantic_decisions: Iterable[Mapping[str, str]],
) -> dict[str, Any]:
    """Freeze validated model decisions without accepting any row values."""

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
    frozen_decisions = sorted(
        [copy.deepcopy(dict(item)) for item in semantic_decisions],
        key=lambda item: (
            str(item.get("decision_kind") or ""),
            str(item.get("decision_id") or ""),
            str(item.get("model_id") or ""),
            str(item.get("response_sha256") or ""),
        ),
    )
    material = {
        "structural_fingerprint": fingerprint,
        "columns": columns,
        "amount_currency_bindings": [
            copy.deepcopy(dict(item)) for item in amount_currency_bindings
        ],
        "side_values": [copy.deepcopy(dict(item)) for item in side_values],
        "semantic_decisions": frozen_decisions,
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
        "semantic_decisions": material["semantic_decisions"],
    }
    return _validated_mapping(mapping)


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
            "compiler_contract",
            "semantic_decisions",
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
            or not item["header_literal"]
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
    decisions = value.get("semantic_decisions")
    if not isinstance(decisions, list) or not decisions:
        _fail("ordinary_trade_mapping_decision_invalid")
    for item in decisions:
        if (
            not isinstance(item, dict)
            or set(item)
            != {"decision_id", "decision_kind", "model_id", "response_sha256"}
            or item.get("decision_kind") not in {"SCHEMA_MAPPING", "SIDE_ENUM"}
            or not all(isinstance(item.get(key), str) and item.get(key) for key in item)
        ):
            _fail("ordinary_trade_mapping_decision_invalid")
    identity_material = {
        "structural_fingerprint": value["structural_fingerprint"],
        "columns": columns,
        "amount_currency_bindings": value["amount_currency_bindings"],
        "side_values": side_values,
        "semantic_decisions": sorted(
            [copy.deepcopy(dict(item)) for item in decisions],
            key=lambda item: (
                str(item.get("decision_kind") or ""),
                str(item.get("decision_id") or ""),
                str(item.get("model_id") or ""),
                str(item.get("response_sha256") or ""),
            ),
        ),
    }
    if value["mapping_id"] != "otmap_" + _sha256_json(identity_material)[:32]:
        _fail("ordinary_trade_mapping_identity_invalid")
    return copy.deepcopy(dict(value))


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


def _matching_mappings(
    *, rows: dict[int, dict[int, dict[str, Any]]], mappings: tuple[dict[str, Any], ...]
) -> list[tuple[dict[str, Any], int]]:
    result = []
    for mapping in mappings:
        expected = {
            item["column"]: item["header_literal"] for item in mapping["columns"]
        }
        row_matches = [
            row_number
            for row_number, cells in rows.items()
            if set(cells) == set(expected)
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
                    disposition="RELEVANT_UNMAPPED",
                    reason=reason,
                    mapping_id=None,
                    numeric_convention=None,
                )
            )
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
    "ORDINARY_TRADE_MAPPING_SCHEMA_VERSION",
    "ORDINARY_TRADE_PROJECTION_SCHEMA_VERSION",
    "OrdinaryTradeSemanticCompiler",
    "OrdinaryTradeSemanticCompilerError",
    "OrdinaryTradeSemanticCompilerFactory",
    "compile_schema_mapping",
    "normalize_runtime_value",
    "structural_fingerprint",
    "validate_ordinary_trade_projection",
]
