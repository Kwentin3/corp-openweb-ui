from __future__ import annotations

import copy
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .contracts import stable_digest


FACTORY_REQUIRED = (
    "PdfSourceBoundTableAssemblerFactory.create is the only product consumer "
    "of source-bound visual table-continuation decisions"
)
FORBIDDEN = (
    "The assembler must not infer continuation from broker identity, text, "
    "headers, regexes, filenames, or financial meaning"
)

SOURCE_BOUND_ORIGIN = "vlm_located_pdfplumber_source_bound"
CONTINUATION_SCHEMA = "broker_reports_pdf_source_bound_continuation_v2"


@dataclass(frozen=True)
class PdfSourceBoundTableAssemblyResult:
    projections: list[dict[str, Any]]
    physical_to_logical_ref: dict[str, str]
    blockers: list[dict[str, Any]]


class PdfSourceBoundTableAssemblerFactory:
    def create(self) -> "PdfSourceBoundTableAssembler":
        return PdfSourceBoundTableAssembler()


class PdfSourceBoundTableAssembler:
    """Validate and apply locator-owned table identity before Canonical."""

    def assemble(
        self,
        *,
        projections: list[dict[str, Any]],
        source_units: list[dict[str, Any]],
        payloads: list[dict[str, Any]],
    ) -> PdfSourceBoundTableAssemblyResult:
        physical = copy.deepcopy(projections)
        facts, malformed = _facts(physical, source_units, payloads)
        blockers = [
            _blocker("pdf_source_bound_table_projection_context_invalid", [ref])
            for ref in malformed
        ]
        by_page: dict[int, list[dict[str, Any]]] = {}
        for fact in facts:
            by_page.setdefault(fact["page_number"], []).append(fact)
        for page_facts in by_page.values():
            page_facts.sort(key=lambda item: (item["ymin"], item["projection_ref"]))

        edges: list[tuple[dict[str, Any], dict[str, Any], dict[str, str]]] = []
        for current in facts:
            boundary = current["boundary"]
            if boundary is None:
                continue
            decision = boundary.get("decision")
            if decision in {"NOT_APPLICABLE", "INDEPENDENT"}:
                continue
            if decision == "AMBIGUOUS":
                blockers.append(
                    _blocker("pdf_source_bound_table_continuation_ambiguous", [current["projection_ref"]])
                )
                continue
            previous_page = by_page.get(current["page_number"] - 1, [])
            current_page = by_page.get(current["page_number"], [])
            if (
                decision != "CONTINUATION"
                or not previous_page
                or not current_page
                or current is not current_page[0]
            ):
                blockers.append(
                    _blocker("pdf_source_bound_table_boundary_binding_invalid", [current["projection_ref"]])
                )
                continue
            previous = previous_page[-1]
            if not _same_grid(previous, current):
                blockers.append(
                    _blocker(
                        "pdf_source_bound_table_continuation_grid_incompatible",
                        [previous["projection_ref"], current["projection_ref"]],
                    )
                )
                continue
            edges.append((previous, current, copy.deepcopy(boundary)))

        if blockers:
            for projection in physical:
                if projection.get("table_origin") != SOURCE_BOUND_ORIGIN:
                    continue
                projection["projection_status"] = "blocked"
                projection["table_candidate_status"] = "blocked"
                projection["reconstruction_quality"] = "blocked"
                projection["quality"]["reconstruction_quality"] = "blocked"
                projection["reconstruction_reason_codes"] = sorted(
                    {
                        *list(projection.get("reconstruction_reason_codes") or []),
                        *[item["code"] for item in blockers],
                    }
                )
            return PdfSourceBoundTableAssemblyResult(physical, {}, blockers)

        next_by_ref = {left["projection_ref"]: (right, receipt) for left, right, receipt in edges}
        previous_refs = {right["projection_ref"] for _, right, _ in edges}
        consumed: set[str] = set()
        result: list[dict[str, Any]] = []
        replacements: dict[str, str] = {}
        for fact in facts:
            ref = fact["projection_ref"]
            if ref in consumed or ref in previous_refs:
                continue
            chain = [fact]
            receipts: list[dict[str, str]] = []
            while chain[-1]["projection_ref"] in next_by_ref:
                following, receipt = next_by_ref[chain[-1]["projection_ref"]]
                if following["projection_ref"] in {item["projection_ref"] for item in chain}:
                    raise ValueError("pdf_source_bound_table_continuation_cycle")
                chain.append(following)
                receipts.append(receipt)
            if len(chain) == 1:
                continue
            logical = _merge_chain(chain, receipts)
            result.append(logical)
            for member in chain:
                consumed.add(member["projection_ref"])
                replacements[member["projection_ref"]] = logical["table_projection_id"]

        for projection in physical:
            ref = str(projection.get("table_projection_id") or "")
            if ref not in consumed:
                result.append(projection)
        return PdfSourceBoundTableAssemblyResult(result, replacements, [])


def _merge_chain(
    chain: list[dict[str, Any]], receipts: list[dict[str, str]]
) -> dict[str, Any]:
    members = [item["projection"] for item in chain]
    root = copy.deepcopy(members[0])
    if int(root.get("bound_header_row_count") or 0) <= 0:
        raise ValueError("pdf_source_bound_table_anchor_header_missing")
    member_refs = [str(item.get("table_projection_id") or "") for item in members]
    logical_ref = "tableproj_" + stable_digest(
        [CONTINUATION_SCHEMA, *member_refs], length=24
    )
    root["table_projection_id"] = logical_ref
    root["logical_table_id"] = "logicaltable_" + stable_digest(
        [CONTINUATION_SCHEMA, *member_refs], length=24
    )
    root_columns = list(root.get("column_refs") or [])
    merged_rows: list[dict[str, Any]] = []
    merged_cells: list[dict[str, Any]] = []
    repeated_header_evidence: list[dict[str, Any]] = []
    row_ordinal = 0
    for member_index, member in enumerate(members):
        header_count = int(member.get("bound_header_row_count") or 0)
        omitted_header_refs = {
            str(row.get("row_ref") or "")
            for row in list(member.get("rows") or [])[:header_count]
        } if member_index else set()
        if omitted_header_refs:
            omitted_cells = [
                cell
                for cell in member.get("cells") or []
                if str(cell.get("row_ref") or "") in omitted_header_refs
            ]
            repeated_header_evidence.append(
                {
                    "physical_table_projection_ref": str(
                        member.get("table_projection_id") or ""
                    ),
                    "source_unit_ref": str(member.get("source_unit_ref") or ""),
                    "page_ref": str((member.get("page_refs") or [""])[0]),
                    "source_page": int(
                        (omitted_cells[0] if omitted_cells else {}).get("source_page")
                        or 0
                    ),
                    "row_refs": sorted(omitted_header_refs),
                    "cell_refs": [
                        str(cell.get("cell_ref") or "") for cell in omitted_cells
                    ],
                    "source_value_refs": [
                        str(ref)
                        for cell in omitted_cells
                        for ref in cell.get("source_value_refs") or []
                    ],
                }
            )
        row_ordinals: dict[str, int] = {}
        for row in member.get("rows") or []:
            row_ref = str(row.get("row_ref") or "")
            if row_ref in omitted_header_refs:
                continue
            row_ordinal += 1
            row_ordinals[row_ref] = row_ordinal
            mapped = copy.deepcopy(row)
            mapped["row_ordinal"] = row_ordinal
            mapped["row_role"] = (
                mapped.get("row_role") if member_index == 0 else "data_row"
            )
            merged_rows.append(mapped)
        member_columns = list(member.get("column_refs") or [])
        column_map = dict(zip(member_columns, root_columns, strict=True))
        for cell in member.get("cells") or []:
            row_ref = str(cell.get("row_ref") or "")
            if row_ref in omitted_header_refs:
                continue
            mapped = copy.deepcopy(cell)
            mapped["row_ordinal"] = row_ordinals[row_ref]
            mapped["column_ref"] = column_map[str(cell.get("column_ref") or "")]
            merged_cells.append(mapped)

    root["rows"] = merged_rows
    root["row_refs"] = [str(item.get("row_ref") or "") for item in merged_rows]
    root["cells"] = merged_cells
    root["cell_refs"] = [str(item.get("cell_ref") or "") for item in merged_cells]
    root["cell_value_refs"] = [str(item.get("cell_value_ref") or "") for item in merged_cells]
    root["row_count"] = len(merged_rows)
    root["cell_count"] = len(merged_cells)
    root["page_refs"] = _unique(item for member in members for item in member.get("page_refs") or [])
    root["source_unit_refs"] = _unique(
        str(member.get("source_unit_ref") or "") for member in members
    )
    root["private_values"] = [
        copy.deepcopy(item) for member in members for item in member.get("private_values") or []
    ]
    root["source_value_index"] = [
        copy.deepcopy(item) for member in members for item in member.get("source_value_index") or []
    ]
    root["source_value_refs"] = sorted(
        {str(ref) for member in members for ref in member.get("source_value_refs") or [] if ref}
    )
    root["coverage"] = _merge_coverage(logical_ref, members)
    root["continuation"] = {
        "schema_version": CONTINUATION_SCHEMA,
        "owner": "source_bound_visual_table_locator",
        "physical_table_projection_refs": member_refs,
        "boundary_receipts": receipts,
        "repeated_header_source_value_refs": sorted(
            ref
            for item in repeated_header_evidence
            for ref in item["source_value_refs"]
        ),
        "repeated_header_evidence": repeated_header_evidence,
        "semantic_table_truth_claimed": False,
    }
    root["boundary_from_previous"] = None
    root["reconstruction_reason_codes"] = sorted(
        {
            *[code for member in members for code in member.get("reconstruction_reason_codes") or []],
            "pdf_source_bound_visual_continuation_applied",
        }
    )
    root["table_projection_checksum_ref"] = None
    root.pop("validator_status", None)
    root.pop("validator_reason_codes", None)
    return root


def _merge_coverage(projection_ref: str, members: list[dict[str, Any]]) -> dict[str, Any]:
    fields = ("selected_source_refs", "table_owned_refs", "fallback_text_refs", "non_table_refs", "rejected_refs")
    combined = {
        field: [str(ref) for member in members for ref in (member.get("coverage") or {}).get(field) or []]
        for field in fields
    }
    owners = [
        *combined["table_owned_refs"], *combined["fallback_text_refs"],
        *combined["non_table_refs"], *combined["rejected_refs"],
    ]
    duplicates = sorted(ref for ref, count in Counter(owners).items() if count > 1)
    unaccounted = sorted(set(combined["selected_source_refs"]) - set(owners))
    return {
        "schema_version": "broker_reports_table_projection_coverage_v0",
        "coverage_ref": "tablecoverage_" + stable_digest([projection_ref, combined, owners], length=24),
        **combined,
        "accounted_source_refs": owners,
        "duplicate_accounted_refs": duplicates,
        "unaccounted_refs": unaccounted,
        "selected_total": len(combined["selected_source_refs"]),
        "accounted_total": len(owners),
        "coverage_status": "complete" if not duplicates and not unaccounted else "partial",
        "all_selected_refs_accounted": not duplicates and not unaccounted,
    }


def _facts(
    projections: list[dict[str, Any]],
    source_units: list[dict[str, Any]],
    payloads: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    unit_by_ref = {str(item.get("unit_ref") or ""): item for item in source_units if isinstance(item, dict)}
    page_by_ref: dict[str, dict[str, Any]] = {}
    bbox_by_ref: dict[str, list[float]] = {}
    for payload in payloads:
        projection = payload.get("pdf_text_layer_projection") if isinstance(payload, dict) else None
        if not isinstance(projection, dict):
            continue
        for page in projection.get("page_inventory") or []:
            if isinstance(page, dict):
                page_by_ref[str(page.get("page_ref") or "")] = page
        for bbox in projection.get("bbox_inventory") or []:
            if isinstance(bbox, dict) and isinstance(bbox.get("bbox"), list):
                bbox_by_ref[str(bbox.get("bbox_ref") or "")] = bbox["bbox"]
    source_bound_units = [
        unit_by_ref.get(str(item.get("source_unit_ref") or ""), {})
        for item in projections
        if item.get("table_origin") == SOURCE_BOUND_ORIGIN
    ]
    if not any(
        isinstance(unit.get("boundary_from_previous"), dict)
        for unit in source_bound_units
    ):
        return [], []
    facts: list[dict[str, Any]] = []
    malformed: list[str] = []
    for projection in projections:
        if projection.get("table_origin") != SOURCE_BOUND_ORIGIN:
            continue
        ref = str(projection.get("table_projection_id") or "")
        unit = unit_by_ref.get(str(projection.get("source_unit_ref") or ""), {})
        page_refs = list(projection.get("page_refs") or [])
        page = page_by_ref.get(str(page_refs[0])) if len(page_refs) == 1 else None
        width = float((page or {}).get("layout_page_width") or 0.0)
        bbox = (projection.get("geometry") or {}).get("table_locator_bbox_pdf_points")
        edges = sorted({
            round(float(value) / width, 6)
            for cell in projection.get("cells") or []
            for cell_bbox in [bbox_by_ref.get(str(cell.get("bbox_ref") or ""))]
            if isinstance(cell_bbox, list) and len(cell_bbox) == 4 and width > 0
            for value in (cell_bbox[0], cell_bbox[2])
        })
        if not page or not isinstance(bbox, list) or len(bbox) != 4 or len(edges) != int(projection.get("column_count") or 0) + 1:
            malformed.append(ref)
            continue
        facts.append({
            "projection": projection,
            "projection_ref": ref,
            "page_number": int(page.get("page_number") or 0),
            "ymin": float(bbox[1]),
            "column_count": int(projection.get("column_count") or 0),
            "x_edges": edges,
            "boundary": copy.deepcopy(unit.get("boundary_from_previous")) if isinstance(unit.get("boundary_from_previous"), dict) else None,
        })
    return facts, sorted(set(malformed))


def _same_grid(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left["column_count"] == right["column_count"]
        and len(left["x_edges"]) == len(right["x_edges"])
        and max((abs(a - b) for a, b in zip(left["x_edges"], right["x_edges"], strict=True)), default=1.0) <= 0.001
    )


def _unique(values: Any) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if value))


def _blocker(code: str, refs: list[str]) -> dict[str, Any]:
    return {"code": code, "projection_refs": sorted(set(refs))}
