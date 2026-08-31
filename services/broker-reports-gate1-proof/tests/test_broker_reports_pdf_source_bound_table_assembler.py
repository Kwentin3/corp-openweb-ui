from __future__ import annotations

import copy

from broker_reports_gate1.pdf_source_bound_table_assembler import (
    PdfSourceBoundTableAssemblerFactory,
)
from broker_reports_gate1.table_projection import (
    TableProjectionValidator,
    _base_projection,
    _checksum_ref,
    _coverage,
    _finish_projection,
    _quality,
)


def _physical(page: int, ordinal: int, *, columns: int = 2, header: bool = True):
    unit_ref = f"unit-{page}-{ordinal}"
    projection_ref = f"projection-{page}-{ordinal}"
    column_refs = [f"column-{page}-{ordinal}-{value}" for value in range(1, columns + 1)]
    rows = []
    cells = []
    private_values = []
    source_index = []
    bbox_inventory = []
    source_refs = []
    word_refs = []
    for row_ordinal in (1, 2):
        row_ref = f"row-{page}-{ordinal}-{row_ordinal}"
        row_cell_refs = []
        for column_ordinal in range(1, columns + 1):
            cell_ref = f"cell-{page}-{ordinal}-{row_ordinal}-{column_ordinal}"
            source_ref = f"source-{page}-{ordinal}-{row_ordinal}-{column_ordinal}"
            word_ref = f"word-{page}-{ordinal}-{row_ordinal}-{column_ordinal}"
            value_path = f"value-{page}-{ordinal}-{row_ordinal}-{column_ordinal}"
            bbox_ref = f"bbox-{page}-{ordinal}-{row_ordinal}-{column_ordinal}"
            value = f"p{page}r{row_ordinal}c{column_ordinal}"
            row_cell_refs.append(cell_ref)
            source_refs.append(source_ref)
            word_refs.append(word_ref)
            bbox_inventory.append(
                {
                    "bbox_ref": bbox_ref,
                    "bbox": [
                        (column_ordinal - 1) * 100.0,
                        float(row_ordinal * 20),
                        column_ordinal * 100.0,
                        float(row_ordinal * 20 + 20),
                    ],
                }
            )
            cells.append(
                {
                    "cell_ref": cell_ref,
                    "row_ref": row_ref,
                    "column_ref": column_refs[column_ordinal - 1],
                    "row_ordinal": row_ordinal,
                    "column_ordinal": column_ordinal,
                    "source_value_refs": [source_ref],
                    "source_unit_ref": unit_ref,
                    "page_ref": f"page-{page}",
                    "source_page": page,
                    "physical_table_projection_ref": projection_ref,
                    "cell_value_ref": f"cell-value-{cell_ref}",
                    "normalized_private_value_path": value_path,
                    "value_checksum_ref": _checksum_ref("valuechk", value),
                    "value_kind_hints": [],
                    "bbox_ref": bbox_ref,
                    "row_span": 1,
                    "column_span": 1,
                    "merged_cell_group_ref": None,
                    "split_cell_candidate": False,
                    "multi_line_cell": False,
                    "wrapped_text_cell": False,
                    "ambiguous_cell_boundary": False,
                    "empty_cell": False,
                    "confidence": "high",
                    "reason_codes": ["fixture_source_geometry"],
                }
            )
            private_values.append(
                {
                    "value_path_ref": value_path,
                    "normalized_value": value,
                    "value_checksum_ref": _checksum_ref("valuechk", value),
                    "source_value_refs": [source_ref],
                }
            )
            source_index.append(
                {
                    "source_value_ref": source_ref,
                    "source_object_ref": word_ref,
                    "cell_ref": cell_ref,
                    "row_ref": row_ref,
                    "source_unit_ref": unit_ref,
                    "page_ref": f"page-{page}",
                    "source_page": page,
                    "physical_table_projection_ref": projection_ref,
                    "value_path": {
                        "kind": "table_projection_private_value",
                        "value_path_ref": value_path,
                    },
                    "value_checksum_ref": _checksum_ref("valuechk", value),
                }
            )
        rows.append(
            {
                "row_ref": row_ref,
                "row_ordinal": row_ordinal,
                "cell_refs": row_cell_refs,
                "row_role": "header_row" if header and row_ordinal == 1 else "data_row",
                "row_checksum_ref": _checksum_ref("rowchk", row_cell_refs),
                "reason_codes": ["fixture_source_geometry"],
            }
        )
    header_refs = [rows[0]["row_ref"]] if header else []
    header_sources = [
        ref for cell in cells if cell["row_ref"] in header_refs for ref in cell["source_value_refs"]
    ]
    header_model = {
        "status": "present" if header else "absent",
        "header_row_refs": header_refs,
        "column_labels": [],
        "source_value_refs": header_sources,
        "source_checksum_ref": _checksum_ref(
            "pdfheaderchk", {"row_refs": header_refs, "source_value_refs": header_sources}
        ),
    }
    unit = {
        "unit_ref": unit_ref,
        "document_id": "document",
        "parent_payload_ref": "payload",
        "normalization_run_id": "run",
        "parser_ref": "parser",
        "source_checksum_ref": "source-checksum",
        "payload_checksum_ref": "payload-checksum",
        "source_unit_checksum_ref": f"unit-checksum-{unit_ref}",
        "page_refs": [f"page-{page}"],
        "source_location": {"page": page},
        "boundary_from_previous": None,
    }
    projection = _base_projection(
        projection_id=projection_ref,
        table_ref=f"table-{page}-{ordinal}",
        source_format="pdf",
        table_origin="vlm_located_pdfplumber_source_bound",
        source_unit=unit,
        row_refs=[item["row_ref"] for item in rows],
        column_refs=column_refs,
        cells=cells,
        rows=rows,
        private_values=private_values,
        source_value_index=source_index,
        headers=header_model,
        coverage=_coverage(
            projection_id=projection_ref,
            selected=word_refs,
            table_owned=word_refs,
        ),
        quality=_quality(
            rows=rows,
            cells=cells,
            coverage_complete=True,
            geometry_confidence=1.0,
            blocked=False,
        ),
        page_refs=[f"page-{page}"],
        sheet_refs=[],
        section_refs=[],
        table_bbox_ref=f"table-bbox-{page}-{ordinal}",
        table_candidate_status="validated_source_bound_geometry",
        reconstruction_strategy="source_bound_fixture",
        reconstruction_reason_codes=["fixture_source_geometry"],
    )
    projection.update(
        {
            "table_title_binding": None,
            "bound_header_row_count": 1 if header else 0,
            "geometry": {
                "table_locator_bbox_pdf_points": [0.0, ordinal * 60.0, 200.0, ordinal * 60.0 + 50.0]
            },
            "boundary_from_previous": None,
        }
    )
    return _finish_projection(projection), unit, bbox_inventory


def _assemble(specs, boundaries):
    projections = []
    units = []
    bboxes = []
    pages = {}
    for spec in specs:
        projection, unit, inventory = _physical(
            spec[0], spec[1], columns=(spec[2] if len(spec) > 2 else 2)
        )
        unit["boundary_from_previous"] = copy.deepcopy(
            boundaries.get((spec[0], spec[1]))
        )
        projections.append(projection)
        units.append(unit)
        bboxes.extend(inventory)
        pages[spec[0]] = {
            "page_ref": f"page-{spec[0]}",
            "page_number": spec[0],
            "layout_page_width": 200.0,
            "layout_page_height": 400.0,
        }
    payloads = [
        {
            "source_payload_ref": "payload",
            "pdf_text_layer_projection": {
                "page_inventory": list(pages.values()),
                "bbox_inventory": bboxes,
            },
        }
    ]
    return PdfSourceBoundTableAssemblerFactory().create().assemble(
        projections=projections, source_units=units, payloads=payloads
    )


def test_three_page_chain_is_one_projection_and_repeated_headers_keep_custody():
    boundaries = {
        (1, 1): {"decision": "NOT_APPLICABLE", "evidence": "FIRST_PAGE"},
        (2, 1): {"decision": "CONTINUATION", "evidence": "VISUAL_FLOW"},
        (3, 1): {"decision": "CONTINUATION", "evidence": "EXPLICIT_CONTINUATION"},
    }
    result = _assemble([(1, 1), (2, 1), (3, 1)], boundaries)
    assert not result.blockers
    assert len(result.projections) == 1
    logical = result.projections[0]
    assert logical["row_count"] == 4
    assert logical["cell_count"] == 8
    assert len(logical["source_value_refs"]) == 12
    assert len(logical["source_value_index"]) == 12
    assert len(logical["continuation"]["repeated_header_source_value_refs"]) == 4
    assert [
        item["physical_table_projection_ref"]
        for item in logical["continuation"]["repeated_header_evidence"]
    ] == ["projection-2-1", "projection-3-1"]
    assert [
        item["source_page"]
        for item in logical["continuation"]["repeated_header_evidence"]
    ] == [2, 3]
    _finish_projection(logical)
    assert TableProjectionValidator().validate(logical)["passed"] is True


def test_page_with_table_a_then_b_links_only_previous_last_to_current_first():
    boundaries = {
        (1, 1): {"decision": "NOT_APPLICABLE", "evidence": "FIRST_PAGE"},
        (2, 1): {"decision": "CONTINUATION", "evidence": "VISUAL_FLOW"},
    }
    result = _assemble([(1, 1), (1, 2), (2, 1)], boundaries)
    assert not result.blockers
    assert len(result.projections) == 2
    logical = next(item for item in result.projections if item.get("logical_table_id"))
    assert logical["continuation"]["physical_table_projection_refs"] == [
        "projection-1-2",
        "projection-2-1",
    ]


def test_same_grid_independent_tables_stay_separate():
    result = _assemble(
        [(1, 1), (2, 1)],
        {
            (1, 1): {"decision": "NOT_APPLICABLE", "evidence": "FIRST_PAGE"},
            (2, 1): {"decision": "INDEPENDENT", "evidence": "NEW_TABLE"},
        },
    )
    assert not result.blockers
    assert len(result.projections) == 2
    assert all(not item.get("logical_table_id") for item in result.projections)


def test_ambiguous_and_incompatible_continuations_fail_closed():
    ambiguous = _assemble(
        [(1, 1), (2, 1)],
        {
            (1, 1): {"decision": "NOT_APPLICABLE", "evidence": "FIRST_PAGE"},
            (2, 1): {"decision": "AMBIGUOUS", "evidence": "INSUFFICIENT_EVIDENCE"},
        },
    )
    assert {item["projection_status"] for item in ambiguous.projections} == {"blocked"}
    incompatible = _assemble(
        [(1, 1), (2, 1, 3)],
        {
            (1, 1): {"decision": "NOT_APPLICABLE", "evidence": "FIRST_PAGE"},
            (2, 1): {"decision": "CONTINUATION", "evidence": "VISUAL_FLOW"},
        },
    )
    assert {item["projection_status"] for item in incompatible.projections} == {"blocked"}
    assert incompatible.blockers[0]["code"] == (
        "pdf_source_bound_table_continuation_grid_incompatible"
    )


def test_foreign_missing_or_duplicate_continuation_provenance_fails_closed():
    result = _assemble(
        [(1, 1), (2, 1), (3, 1)],
        {
            (1, 1): {"decision": "NOT_APPLICABLE", "evidence": "FIRST_PAGE"},
            (2, 1): {"decision": "CONTINUATION", "evidence": "VISUAL_FLOW"},
            (3, 1): {"decision": "CONTINUATION", "evidence": "VISUAL_FLOW"},
        },
    )
    logical = result.projections[0]
    validator = TableProjectionValidator()

    foreign = copy.deepcopy(logical)
    foreign["cells"][0]["source_unit_ref"] = "foreign-unit"
    _finish_projection(foreign)
    assert "pdf_table_cell_physical_provenance_invalid" in {
        item["code"] for item in validator.validate(foreign)["errors"]
    }

    swapped = copy.deepcopy(logical)
    target = swapped["cells"][0]
    donor = next(
        item
        for item in swapped["cells"]
        if item["physical_table_projection_ref"]
        != target["physical_table_projection_ref"]
    )
    for field in (
        "source_unit_ref",
        "page_ref",
        "source_page",
        "physical_table_projection_ref",
    ):
        target[field] = donor[field]
    _finish_projection(swapped)
    assert "pdf_table_cell_physical_provenance_invalid" in {
        item["code"] for item in validator.validate(swapped)["errors"]
    }

    missing = copy.deepcopy(logical)
    missing["continuation"]["repeated_header_evidence"].pop()
    _finish_projection(missing)
    assert "pdf_source_bound_continuation_invalid" in {
        item["code"] for item in validator.validate(missing)["errors"]
    }

    duplicate = copy.deepcopy(logical)
    first_ref = duplicate["continuation"]["repeated_header_evidence"][0][
        "source_value_refs"
    ][0]
    duplicate["continuation"]["repeated_header_evidence"][1][
        "source_value_refs"
    ].append(first_ref)
    _finish_projection(duplicate)
    assert "pdf_source_bound_continuation_invalid" in {
        item["code"] for item in validator.validate(duplicate)["errors"]
    }

    bogus_row = copy.deepcopy(logical)
    bogus_row["continuation"]["repeated_header_evidence"][0]["row_refs"].append(
        "bogus-row"
    )
    _finish_projection(bogus_row)
    assert "pdf_table_cell_physical_provenance_invalid" in {
        item["code"] for item in validator.validate(bogus_row)["errors"]
    }

    bogus_cell = copy.deepcopy(logical)
    bogus_cell["continuation"]["repeated_header_evidence"][0]["cell_refs"].append(
        "bogus-cell"
    )
    _finish_projection(bogus_cell)
    assert "pdf_table_cell_physical_provenance_invalid" in {
        item["code"] for item in validator.validate(bogus_cell)["errors"]
    }
