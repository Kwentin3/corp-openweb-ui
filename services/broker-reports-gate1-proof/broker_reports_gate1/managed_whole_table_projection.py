from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from .managed_document_contracts import compute_document_integrity_sha256
from .managed_document_contracts_v2 import (
    ManagedDocumentV2,
    _source_unit_ledger_inventory,
)


PROJECTION_SCHEMA_VERSION = "broker_reports_managed_whole_table_projection_v2"
PROJECTION_RECEIPT_SCHEMA_VERSION = (
    "broker_reports_managed_whole_table_projection_receipt_v1"
)

FACTORY_REQUIRED = (
    "The private adjudicated Managed PDF route is the sole caller of "
    "_project_sealed_adjudicated_managed_document"
)
FORBIDDEN = (
    "Callers must not submit a Managed payload, ledger, raw scope, provider "
    "connection or projection receipt to this inactive representation seam"
)


@dataclass(frozen=True, slots=True)
class _ManagedWholeTableProjectionResult:
    status: str
    projections: tuple[dict[str, Any], ...]
    issues: tuple[dict[str, str], ...]


def _project_sealed_adjudicated_managed_document(
    managed_document: ManagedDocumentV2,
    *,
    expected_source_unit_ledger: tuple[Mapping[str, Any], ...],
) -> _ManagedWholeTableProjectionResult:
    """Project the same-call, privately sealed Managed result without mutation."""

    if not isinstance(managed_document, ManagedDocumentV2):
        return _not_ready("managed_whole_table_projection_input_invalid")
    before_bytes = managed_document.canonical_json_bytes()
    before_integrity = managed_document.integrity_sha256
    payload = copy.deepcopy(managed_document.payload)
    result = _project_payload(
        payload,
        expected_source_unit_ledger=expected_source_unit_ledger,
    )
    if (
        managed_document.canonical_json_bytes() != before_bytes
        or managed_document.integrity_sha256 != before_integrity
    ):
        return _not_ready("managed_whole_table_projection_input_mutated")
    return result


def _project_payload(
    payload: dict[str, Any],
    *,
    expected_source_unit_ledger: tuple[Mapping[str, Any], ...],
) -> _ManagedWholeTableProjectionResult:
    if not expected_source_unit_ledger:
        return _not_ready("managed_whole_table_projection_ledger_plan_missing")

    integrity = str(payload.get("integrity_sha256") or "")
    if (
        len(integrity) != 64
        or compute_document_integrity_sha256(payload) != integrity
    ):
        return _not_ready("managed_whole_table_projection_integrity_invalid")
    if (
        payload.get("schema_version") != "broker_reports_managed_document_v2"
        or _object(payload.get("quality")).get("status") != "COMPLETE"
    ):
        return _not_ready("managed_whole_table_projection_document_not_complete")

    source = _object(payload.get("source"))
    document_coverage = _object(source.get("table_source_unit_coverage"))
    if not document_coverage:
        return _not_ready("managed_whole_table_projection_ledger_missing")
    if any(
        _strings(document_coverage.get(field))
        for field in (
            "duplicate_source_unit_refs",
            "duplicate_source_atom_refs",
            "duplicate_source_word_refs",
        )
    ):
        return _not_ready("managed_whole_table_projection_ledger_overlap")
    if list(expected_source_unit_ledger) != _source_unit_ledger_inventory(payload):
        return _not_ready("managed_whole_table_projection_ledger_plan_mismatch")

    anchors = _dicts(payload.get("anchors"))
    anchor_by_id = {
        str(anchor.get("anchor_id") or ""): anchor for anchor in anchors
    }
    if "" in anchor_by_id or len(anchor_by_id) != len(anchors):
        return _not_ready("managed_whole_table_projection_anchor_inventory_invalid")

    tables = [
        _object(block.get("content"))
        for block in _dicts(payload.get("blocks"))
        if block.get("block_type") == "TABLE"
    ]
    if not tables:
        return _not_ready("managed_whole_table_projection_table_missing")

    projections: list[dict[str, Any]] = []
    document_units: list[str] = []
    document_atoms: list[str] = []
    document_words: list[str] = []
    source_part_ids: set[str] = set()
    table_ids: set[str] = set()
    for table in tables:
        issue = _table_issue(
            table=table,
            anchor_by_id=anchor_by_id,
            source_part_ids=source_part_ids,
            table_ids=table_ids,
        )
        if issue is not None:
            return _not_ready(issue)
        projection = _table_projection(
            payload=payload,
            table=table,
            managed_integrity=integrity,
        )
        projections.append(projection)
        document_units.extend(projection["covered_source_unit_refs"])
        document_atoms.extend(projection["covered_source_atom_refs"])
        document_words.extend(projection["covered_source_word_refs"])

    if _has_duplicates(document_units + document_atoms + document_words):
        return _not_ready("managed_whole_table_projection_document_overlap")
    if (
        sorted(document_units)
        != _strings(document_coverage.get("covered_source_unit_refs"))
        or sorted(document_atoms)
        != _strings(document_coverage.get("covered_source_atom_refs"))
        or sorted(document_words)
        != _strings(document_coverage.get("covered_source_word_refs"))
    ):
        return _not_ready("managed_whole_table_projection_document_union_mismatch")

    return _ManagedWholeTableProjectionResult(
        status="READY",
        projections=tuple(projections),
        issues=(),
    )


def _table_issue(
    *,
    table: dict[str, Any],
    anchor_by_id: dict[str, dict[str, Any]],
    source_part_ids: set[str],
    table_ids: set[str],
) -> str | None:
    table_id = str(table.get("table_id") or "")
    if not table_id or table_id in table_ids:
        return "managed_whole_table_projection_table_identity_invalid"
    table_ids.add(table_id)
    if table.get("completeness_status") != "COMPLETE":
        return "managed_whole_table_projection_table_not_complete"

    rows = _dicts(table.get("ordered_rows"))
    parts = _dicts(table.get("source_parts"))
    if not rows or not parts:
        return "managed_whole_table_projection_table_structure_missing"
    row_ids = [str(row.get("row_id") or "") for row in rows]
    if (
        "" in row_ids
        or len(row_ids) != len(set(row_ids))
        or [row.get("ordinal") for row in rows] != list(range(len(rows)))
    ):
        return "managed_whole_table_projection_row_inventory_invalid"
    row_ordinal = {row_id: index for index, row_id in enumerate(row_ids)}

    table_units: list[str] = []
    table_atoms: list[str] = []
    table_words: list[str] = []
    table_empty_cells: list[str] = []
    assigned_rows: list[str] = []
    for expected_ordinal, part in enumerate(parts):
        part_id = str(part.get("source_part_id") or "")
        if (
            not part_id
            or part_id in source_part_ids
            or part.get("ordinal") != expected_ordinal
        ):
            return "managed_whole_table_projection_source_part_invalid"
        source_part_ids.add(part_id)
        first = row_ordinal.get(str(part.get("first_row_id") or ""))
        last = row_ordinal.get(str(part.get("last_row_id") or ""))
        if first is None or last is None or first > last:
            return "managed_whole_table_projection_source_part_row_range_invalid"
        part_rows = rows[first : last + 1]
        assigned_rows.extend(str(row["row_id"]) for row in part_rows)

        units = _dicts(part.get("covered_source_units"))
        if not units:
            return "managed_whole_table_projection_source_part_ledger_missing"
        part_units = [str(unit.get("unit_ref") or "") for unit in units]
        part_atoms = [
            ref
            for unit in units
            for ref in _strings(unit.get("selected_source_atom_refs"))
        ]
        part_words = [
            ref
            for unit in units
            for ref in _strings(unit.get("table_contributing_word_refs"))
        ]
        part_empty_cells = [
            str(cell.get("cell_ref") or "")
            for unit in units
            for cell in _dicts(unit.get("empty_grid_slots"))
        ]
        if (
            "" in part_units
            or any(
                not str(unit.get("source_unit_checksum_ref") or "")
                or not str(unit.get("parent_payload_ref") or "")
                or not _strings(unit.get("page_refs"))
                for unit in units
            )
            or "" in part_empty_cells
            or _has_duplicates(
                part_units + part_atoms + part_words + part_empty_cells
            )
        ):
            return "managed_whole_table_projection_source_unit_ledger_invalid"
        anchor_issue = _part_anchor_issue(
            rows=part_rows,
            part=part,
            part_words=set(part_words),
            anchor_by_id=anchor_by_id,
        )
        if anchor_issue is not None:
            return anchor_issue
        table_units.extend(part_units)
        table_atoms.extend(part_atoms)
        table_words.extend(part_words)
        table_empty_cells.extend(part_empty_cells)

    if assigned_rows != row_ids:
        return "managed_whole_table_projection_source_part_partition_invalid"
    if _has_duplicates(
        table_units + table_atoms + table_words + table_empty_cells
    ):
        return "managed_whole_table_projection_table_overlap"
    if (
        sorted(table_atoms) != _strings(table.get("covered_source_atom_refs"))
        or sorted(table_words) != _strings(table.get("covered_source_word_refs"))
    ):
        return "managed_whole_table_projection_table_union_mismatch"
    slots = _dicts(table.get("empty_grid_slots"))
    if sorted(table_empty_cells) != sorted(
        str(slot.get("source_cell_ref") or "") for slot in slots
    ):
        return "managed_whole_table_projection_empty_grid_slot_union_mismatch"
    return None


def _part_anchor_issue(
    *,
    rows: list[dict[str, Any]],
    part: dict[str, Any],
    part_words: set[str],
    anchor_by_id: dict[str, dict[str, Any]],
) -> str | None:
    page = part.get("page")
    for row in rows:
        objects = [row, *_dicts(row.get("entries"))]
        for value in objects:
            anchor_ids = _strings(value.get("source_anchor_ids"))
            if not anchor_ids:
                return "managed_whole_table_projection_source_anchor_missing"
            for anchor_id in anchor_ids:
                anchor = anchor_by_id.get(anchor_id)
                if anchor is None:
                    return "managed_whole_table_projection_source_anchor_unknown"
                locator = _object(anchor.get("locator"))
                if (
                    locator.get("kind") != "PDF"
                    or locator.get("page") != page
                    or str(locator.get("source_block_ref") or "") not in part_words
                ):
                    return "managed_whole_table_projection_source_anchor_mismatch"
    return None


def _table_projection(
    *,
    payload: dict[str, Any],
    table: dict[str, Any],
    managed_integrity: str,
) -> dict[str, Any]:
    source_parts = copy.deepcopy(_dicts(table.get("source_parts")))
    source_anchor_ids = _table_source_anchor_ids(table)
    anchor_by_id = {
        str(anchor.get("anchor_id") or ""): anchor
        for anchor in _dicts(payload.get("anchors"))
    }
    unit_refs = sorted(
        str(unit["unit_ref"])
        for part in source_parts
        for unit in _dicts(part.get("covered_source_units"))
    )
    table_id = str(table["table_id"])
    projection = {
        "schema_version": PROJECTION_SCHEMA_VERSION,
        "projection_id": "managedtableprojection_"
        + _digest([managed_integrity, table_id]),
        "managed_document_id": str(payload["document_id"]),
        "managed_document_integrity_sha256": managed_integrity,
        "table_id": table_id,
        "completeness_status": "COMPLETE",
        "ordered_rows": copy.deepcopy(table["ordered_rows"]),
        "logical_columns": copy.deepcopy(table["logical_columns"]),
        **(
            {
                "empty_grid_slots": copy.deepcopy(
                    table.get("empty_grid_slots") or []
                )
            }
            if table.get("empty_grid_slots")
            else {}
        ),
        "source_parts": source_parts,
        "source_part_refs": [str(part["source_part_id"]) for part in source_parts],
        "source_anchors": [
            copy.deepcopy(anchor_by_id[anchor_id])
            for anchor_id in sorted(source_anchor_ids)
            if anchor_id in anchor_by_id
        ],
        "covered_source_unit_refs": unit_refs,
        "covered_source_atom_refs": copy.deepcopy(
            table["covered_source_atom_refs"]
        ),
        "covered_source_word_refs": copy.deepcopy(
            table["covered_source_word_refs"]
        ),
        "continuation_header_row_refs": [
            str(row["row_id"])
            for row in table["ordered_rows"]
            if row["role"] == "CONTINUATION_HEADER"
        ],
        "receipt": {
            "schema_version": PROJECTION_RECEIPT_SCHEMA_VERSION,
            "representation_only": True,
            "managed_rows_preserved": True,
            "continuation_headers_collapsed": False,
            "source_unit_refs_synthesized": False,
            "source_atom_refs_synthesized": False,
            "canonical_connected": False,
            "product_connected": False,
        },
    }
    projection["projection_integrity_sha256"] = hashlib.sha256(
        _canonical_bytes(projection)
    ).hexdigest()
    return projection


def _table_source_anchor_ids(table: dict[str, Any]) -> set[str]:
    anchor_ids: set[str] = set()
    for part in _dicts(table.get("source_parts")):
        region_anchor_id = str(part.get("region_anchor_id") or "")
        if region_anchor_id:
            anchor_ids.add(region_anchor_id)
    for row in _dicts(table.get("ordered_rows")):
        anchor_ids.update(_strings(row.get("source_anchor_ids")))
        for entry in _dicts(row.get("entries")):
            anchor_ids.update(_strings(entry.get("source_anchor_ids")))
    return anchor_ids


def _not_ready(code: str) -> _ManagedWholeTableProjectionResult:
    return _ManagedWholeTableProjectionResult(
        status="NOT_READY",
        projections=(),
        issues=({"code": code},),
    )


def _has_duplicates(values: list[str]) -> bool:
    return len(values) != len(set(values))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()[:24]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def _strings(value: Any) -> list[str]:
    return (
        [str(item) for item in value if item is not None and str(item)]
        if isinstance(value, list)
        else []
    )
