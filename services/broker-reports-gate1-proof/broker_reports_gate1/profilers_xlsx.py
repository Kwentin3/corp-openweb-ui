from __future__ import annotations

from collections import Counter
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from .blockers import corrupt_file, encrypted_file, parser_failed
from .contracts import profile_id, slice_id, stable_digest


MAX_XLSX_MEMBER_SIZE = 5_000_000


def profile_xlsx(run_id: str, document_id: str, content_bytes: bytes) -> tuple[dict, list[dict], list[dict]]:
    current_profile_id = profile_id(document_id)
    blockers = []
    try:
        with ZipFile(BytesIO(content_bytes)) as archive:
            infos = archive.infolist()
            encrypted_count = sum(1 for info in infos if info.flag_bits & 0x1)
            oversized_count = sum(1 for info in infos if info.file_size > MAX_XLSX_MEMBER_SIZE)
            if encrypted_count:
                blocker = encrypted_file(run_id, document_id)
                return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]
            if oversized_count:
                blockers.append(parser_failed(run_id, document_id, "xlsx_member_too_large"))
            profile, private_slices = _profile_workbook(archive, document_id, current_profile_id)
    except BadZipFile:
        blocker = corrupt_file(run_id, document_id, "bad_xlsx_zip")
        return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]
    except (KeyError, ET.ParseError) as exc:
        blocker = corrupt_file(run_id, document_id, f"xlsx_structure_invalid:{exc.__class__.__name__}")
        return _blocked_profile(document_id, [blocker["blocker_id"]]), [], [blocker]

    profile["oversized_member_count"] = oversized_count
    profile["blocker_refs"] = [item["blocker_id"] for item in blockers]
    if blockers:
        profile["profile_status"] = "profiled_with_review"
        profile["warnings"].append("xlsx_member_too_large")
    return profile, private_slices, blockers


def _profile_workbook(
    archive: ZipFile,
    document_id: str,
    current_profile_id: str,
) -> tuple[dict, list[dict]]:
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = _relationships(archive)
    shared_strings = _shared_strings(archive)
    sheet_summaries = []
    table_like_ranges = []
    private_slices = []
    hidden_sheets_count = 0
    formulas_count = 0
    normalized_slice_refs = []

    for sheet_index, sheet_node in enumerate(_iter_local(workbook_root, "sheet"), start=1):
        raw_name = sheet_node.attrib.get("name") or f"sheet_{sheet_index}"
        state = sheet_node.attrib.get("state", "visible")
        if state != "visible":
            hidden_sheets_count += 1
        safe_sheet_id = f"xlsheet_{stable_digest([document_id, sheet_index, raw_name], length=12)}"
        rel_id = sheet_node.attrib.get(_rel_attr("id"))
        target = relationships.get(rel_id or "")
        sheet_xml_path = _sheet_target_path(target)
        used_range = None
        rows_count = 0
        columns_count = 0
        sheet_formulas = 0
        table_like = False
        rows: list[list[str | None]] = []

        if sheet_xml_path and sheet_xml_path in archive.namelist():
            sheet_root = ET.fromstring(archive.read(sheet_xml_path))
            dimension = next(_iter_local(sheet_root, "dimension"), None)
            used_range = dimension.attrib.get("ref") if dimension is not None else None
            rows, sheet_formulas = _sheet_rows(sheet_root, shared_strings)
            formulas_count += sheet_formulas
            rows_count = len(rows)
            columns_count = max((len(row) for row in rows), default=0)
            table_like = sum(1 for row in rows if _non_empty_count(row) >= 2) >= 2
            if table_like:
                table_like_ranges.append(
                    {
                        "safe_sheet_id": safe_sheet_id,
                        "sheet_index": sheet_index,
                        "used_range": used_range,
                        "rows_count": rows_count,
                        "columns_count": columns_count,
                    }
                )
            if rows and state == "visible":
                slice_rows = [row[:5] for row in rows[:5]]
                private_slice = {
                    "slice_id": slice_id(document_id, f"xlsx_table_{sheet_index:03d}"),
                    "document_id": document_id,
                    "profile_id": current_profile_id,
                    "slice_type": "table_rows",
                    "source_location": {
                        "kind": "xlsx_sheet_rows",
                        "safe_sheet_id": safe_sheet_id,
                        "sheet_index": sheet_index,
                        "row_start": 1,
                        "row_end": len(slice_rows),
                        "column_start": 1,
                        "column_end": max((len(row) for row in slice_rows), default=0),
                    },
                    "location": {
                        "kind": "xlsx_sheet_rows",
                        "safe_sheet_id": safe_sheet_id,
                        "sheet_index": sheet_index,
                        "row_start": 1,
                        "row_end": len(slice_rows),
                    },
                    "bounded": True,
                    "rows_count": len(slice_rows),
                    "columns_count": max((len(row) for row in slice_rows), default=0),
                    "row_range": [1, len(slice_rows)] if slice_rows else [0, 0],
                    "column_policy": "first_5_columns",
                    "cells": slice_rows,
                    "rows": slice_rows,
                    "truncated": rows_count > len(slice_rows) or columns_count > 5,
                    "parser": "python_stdlib_xlsx_zip_xml",
                    "created_for_gate": "gate1",
                }
                private_slices.append(private_slice)
                normalized_slice_refs.append(private_slice["slice_id"])

        sheet_summaries.append(
            {
                "sheet_index": sheet_index,
                "safe_sheet_id": safe_sheet_id,
                "visibility": state,
                "used_range": used_range,
                "rows_count": rows_count,
                "columns_count": columns_count,
                "table_like": table_like,
                "formulas_count": sheet_formulas,
            }
        )

    extension_counts = Counter(PurePosixPath(name).suffix.lower().lstrip(".") or "none" for name in archive.namelist())
    profile = {
        "profile_id": current_profile_id,
        "document_id": document_id,
        "container_format": "xlsx",
        "parser": "python_stdlib_xlsx_zip_xml",
        "parser_version": "1",
        "profile_status": "profiled",
        "machine_readable": "yes",
        "machine_readable_table": bool(table_like_ranges),
        "workbook_readable": True,
        "sheet_name_policy": "safe_sheet_id_only",
        "sheets_count": len(sheet_summaries),
        "hidden_sheets_count": hidden_sheets_count,
        "formulas_present": formulas_count > 0,
        "formulas_count": formulas_count,
        "used_ranges": sheet_summaries,
        "table_like_ranges": table_like_ranges,
        "workbook_member_extension_counts": dict(sorted(extension_counts.items())),
        "normalized_slice_refs": normalized_slice_refs,
        "warnings": [],
        "blocker_refs": [],
    }
    return profile, private_slices


def _relationships(archive: ZipFile) -> dict[str, str]:
    try:
        root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        return {}
    result = {}
    for node in _iter_local(root, "Relationship"):
        rel_id = node.attrib.get("Id")
        target = node.attrib.get("Target")
        if rel_id and target:
            result[rel_id] = target
    return result


def _shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    strings = []
    for item in _iter_local(root, "si"):
        strings.append("".join(node.text or "" for node in _iter_local(item, "t")))
    return strings


def _sheet_target_path(target: str | None) -> str | None:
    if not target:
        return None
    normalized = target.lstrip("/")
    if normalized.startswith("xl/"):
        return normalized
    return f"xl/{normalized}"


def _sheet_rows(root: ET.Element, shared_strings: list[str]) -> tuple[list[list[str | None]], int]:
    formulas_count = 0
    rows = []
    for row_node in _iter_local(root, "row"):
        cells = []
        for cell_node in _iter_local(row_node, "c"):
            formula = next(_iter_local(cell_node, "f"), None)
            if formula is not None:
                formulas_count += 1
                cells.append(None)
                continue
            cells.append(_cell_value(cell_node, shared_strings))
        if cells:
            rows.append(cells)
    return rows, formulas_count


def _cell_value(cell_node: ET.Element, shared_strings: list[str]) -> str | None:
    cell_type = cell_node.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in _iter_local(cell_node, "t")) or None
    value_node = next(_iter_local(cell_node, "v"), None)
    if value_node is None or value_node.text is None:
        return None
    if cell_type == "s":
        try:
            return shared_strings[int(value_node.text)]
        except (ValueError, IndexError):
            return None
    return value_node.text


def _iter_local(root: ET.Element, local_name: str):
    return (node for node in root.iter() if _local_name(node.tag) == local_name)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _rel_attr(local_name: str) -> str:
    return f"{{http://schemas.openxmlformats.org/officeDocument/2006/relationships}}{local_name}"


def _non_empty_count(row: list[str | None]) -> int:
    return sum(1 for cell in row if cell not in {None, ""})


def _blocked_profile(document_id: str, blocker_refs: list[str]) -> dict:
    return {
        "profile_id": profile_id(document_id),
        "document_id": document_id,
        "container_format": "xlsx",
        "parser": "python_stdlib_xlsx_zip_xml",
        "parser_version": "1",
        "profile_status": "blocked",
        "machine_readable": "unknown",
        "machine_readable_table": False,
        "workbook_readable": False,
        "sheet_name_policy": "safe_sheet_id_only",
        "sheets_count": 0,
        "hidden_sheets_count": 0,
        "formulas_present": False,
        "formulas_count": 0,
        "used_ranges": [],
        "table_like_ranges": [],
        "normalized_slice_refs": [],
        "warnings": ["parser_failed"],
        "blocker_refs": blocker_refs,
    }
