from __future__ import annotations


def build_kt21_safe_package(
    *,
    index: int,
    document_ref: str | None = None,
    table_ref: str | None = None,
    row_ordinal: int = 1,
) -> dict:
    """Build a synthetic semantic redaction; never an exact customer package."""

    unit_id = f"kt21_unit_{index}"
    row_ref = f"row:kt21:{index}"
    document = document_ref or f"document:kt21:{index}"
    table = table_ref or f"table:kt21:{index}"
    values = (
        "Synthetic printed total",
        f"{200 + index}.00",
        "2026-06-30",
        "USD",
    )
    headers = ("Line item", "Amount", "As of date", "Currency")
    roles = ("source_label", "amount", "as_of_date", "currency")
    cells = []
    value_index = []
    value_refs = []
    for ordinal, (header, value) in enumerate(
        zip(headers, values, strict=True),
        start=1,
    ):
        cell_ref = f"{unit_id}:cell:{ordinal}"
        value_ref = f"{unit_id}:value:{ordinal}"
        value_refs.append(value_ref)
        cells.append(
            {
                "column_ordinal": ordinal,
                "header_label": header,
                "cell_ref": cell_ref,
                "source_value_ref": value_ref,
                "value": value,
            }
        )
        value_index.append(
            {
                "source_value_ref": value_ref,
                "row_ref": row_ref,
                "cell_ref": cell_ref,
                "value_path": {
                    "kind": "table_cell",
                    "row_index": 0,
                    "column_index": ordinal - 1,
                },
                "value_checksum_ref": f"checksum:{value_ref}",
            }
        )
    header_ref = f"{unit_id}:header"
    selected = [row_ref, header_ref]
    return {
        "schema_version": "broker_reports_source_fact_package_v0",
        "package_id": f"kt21_package_{index}",
        "extraction_run_id": "extraction:kt21:synthetic",
        "normalization_run_id": "normalization:kt21:synthetic",
        "case_id": "case:kt21:synthetic",
        "document_ref": document,
        "source_bucket_roles": ["primary_source_refs"],
        "document_context": {
            "usage_modes": ["source_fact"],
            "passport": {"document_kind_candidate": "broker_report"},
            "financial_interpretation_allowed": True,
            "document_role": "primary_statement",
            "document_title": "Synthetic quarterly statement",
            "issuer_role": "synthetic_issuer",
            "reporting_period": "2026-Q2",
            "statement_scope": "synthetic_statement_scope",
            "account_type": "synthetic_account",
            "language": "en",
        },
        "source_unit": {
            "unit_id": unit_id,
            "unit_kind": "table_row_window",
            "source_input_mode": "normalized_table_projection",
            "private_slice_artifact_ref": f"artifact:{unit_id}",
            "slice_ref": f"slice:{unit_id}",
            "document_ref": document,
            "source_checksum_ref": f"checksum:{unit_id}",
            "slice_payload_checksum_ref": f"payload-checksum:{unit_id}",
            "parser_ref": "parser:kt21:synthetic",
            "table_ref": table,
            "table_title": "Synthetic statement metrics",
            "safe_section_labels": ["Statement", "Totals"],
            "group_labels": ["Reported metrics"],
            "related_notes": ["Synthetic note"],
            "row_range_ref": f"row-range:{unit_id}",
            "coverage_ref": f"coverage:{unit_id}",
            "normalized_header_descriptors": [
                {"column_ordinal": ordinal, "normalized_label": role}
                for ordinal, role in enumerate(roles, start=1)
            ],
            "row_refs": [row_ref],
            "row_provenance": [
                {
                    "row_ref": row_ref,
                    "row_ordinal": row_ordinal,
                    "row_kind": "fact_candidate",
                }
            ],
            "cell_refs": [item["cell_ref"] for item in cells],
            "cell_provenance": [
                {
                    "row_ordinal": row_ordinal,
                    "column_ordinal": ordinal,
                    "row_ref": row_ref,
                    "cell_ref": item["cell_ref"],
                    "source_value_ref": item["source_value_ref"],
                }
                for ordinal, item in enumerate(cells, start=1)
            ],
            "cell_value_refs": value_refs,
            "source_value_refs": value_refs,
            "source_value_index": value_index,
            "private_values": [],
            "text_segment_refs": [],
            "section_refs": [],
            "page_refs": [],
            "character_span_refs": [],
            "segment_provenance": [],
            "normalized_source_projection": {"cells": [list(values)]},
            "model_source_projection": {
                "schema_version": "gate2_model_table_projection_v0",
                "rows": [
                    {
                        "row_ref": row_ref,
                        "row_kind": "fact_candidate",
                        "cells": cells,
                    }
                ],
            },
            "table_quality": {
                "header_confidence": "high",
                "reconstruction_quality": "high",
            },
            "continuation": {},
        },
        "allowed_evidence_refs": selected,
        "allowed_source_value_refs": value_refs,
        "issue_context": [],
        "allowed_issue_refs": [],
        "forbidden_assumptions": [],
        "coverage_expectation": {
            "coverage_ref": f"coverage:{unit_id}",
            "selected_source_refs": selected,
            "ignorable_header_refs": [header_ref],
            "ignorable_blank_refs": [],
            "layout_candidate_refs": [],
            "mandatory_no_fact_results": [
                {"source_ref": header_ref, "reason_code": "header_row"}
            ],
        },
        "privacy_policy": {
            "knowledge_rag_used": False,
            "vectorization_performed": False,
        },
        "created_at": "2026-07-31T00:00:00Z",
    }
