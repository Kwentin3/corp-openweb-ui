from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any


EXPERIMENT_VERSION = "broker_reports_direct_pdf_multi_provider_experiment_v1"
TABLE_SCHEMA_VERSION = "broker_reports_direct_pdf_tables_v1"
BUSINESS_SCHEMA_VERSION = "broker_reports_direct_pdf_business_facts_v1"
DOMAIN_IDS = (
    "trade_operation",
    "cash_movement",
    "income",
    "fee_commission",
    "withholding_tax",
    "position_snapshot",
    "currency_fx",
    "document_evidence",
)
DOMAIN_STATUSES = ("typed_fact", "unknown", "no_fact", "unsupported", "ambiguous")
ROW_KINDS = ("header", "column_numbers", "data", "section", "subtotal", "total", "unknown")


def table_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "enum": [TABLE_SCHEMA_VERSION]},
            "document_status": {"type": "string", "enum": ["completed", "unsupported", "ambiguous"]},
            "tables": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "page": {"type": "integer", "minimum": 1},
                        "order_on_page": {"type": "integer", "minimum": 1},
                        "boundary": {"type": "array", "items": {"type": "number"}, "maxItems": 4},
                        "row_count": {"type": "integer", "minimum": 0},
                        "column_count": {"type": "integer", "minimum": 0},
                        "header_rows": {"type": "integer", "minimum": 0},
                        "rows": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "row_kind": {"type": "string", "enum": list(ROW_KINDS)},
                                    "cells": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": ["row_kind", "cells"],
                            },
                        },
                        "continuation_page": {"type": "integer", "minimum": 0},
                        "continuation_order_on_page": {"type": "integer", "minimum": 0},
                        "uncertainty": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "page", "order_on_page", "boundary", "row_count", "column_count",
                        "header_rows", "rows", "continuation_page", "continuation_order_on_page", "uncertainty",
                    ],
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["schema_version", "document_status", "tables", "warnings"],
    }


def business_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "schema_version": {"type": "string", "enum": [BUSINESS_SCHEMA_VERSION]},
            "domains": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "domain": {"type": "string", "enum": list(DOMAIN_IDS)},
                        "status": {"type": "string", "enum": list(DOMAIN_STATUSES)},
                        "facts": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "fact_type": {"type": "string"},
                                    "fields": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "additionalProperties": False,
                                            "properties": {
                                                "name": {"type": "string"},
                                                "value": {"type": "string"},
                                            },
                                            "required": ["name", "value"],
                                        },
                                    },
                                    "page": {"type": "integer", "minimum": 0},
                                    "table_order_on_page": {"type": "integer", "minimum": 0},
                                    "row_label": {"type": "string"},
                                    "column_label": {"type": "string"},
                                    "boundary": {"type": "array", "items": {"type": "number"}, "maxItems": 4},
                                    "provider_citation": {"type": "string"},
                                    "uncertainty": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": [
                                    "fact_type", "fields", "page", "table_order_on_page", "row_label",
                                    "column_label", "boundary", "provider_citation", "uncertainty",
                                ],
                            },
                        },
                        "uncertainty": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["domain", "status", "facts", "uncertainty"],
                },
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["schema_version", "domains", "warnings"],
    }


def table_prompt() -> str:
    return (
        "Find and reconstruct every table in this complete PDF. Discover tables independently: no expected count, "
        "coordinates or shapes are supplied. Preserve page and page-local order, exact rows and columns, hierarchical "
        "headers, empty-cell positions, digits, signs, decimal separators, totals and continuations across pages. "
        "Do not calculate, normalize, repair or invent values. Boundary is [x0,y0,x1,y1] only when the model can "
        "support it, otherwise []. A continuation points to the preceding table; use zeroes when absent. Return only "
        "the required structured result."
    )


def business_prompt() -> str:
    return (
        "Extract all source-visible broker-report facts from this complete PDF for these domains: trade_operation, "
        "cash_movement, income, fee_commission, withholding_tax, position_snapshot, currency_fx, and document_evidence "
        "only at the correct document or section boundary. Distinguish typed_fact, unknown, no_fact, unsupported and "
        "ambiguous. Preserve exact visible values; do not calculate tax, create a declaration, consolidate Gate 3 data, "
        "or invent a value. For each fact give the strongest source location you can support. Use page/table zero when "
        "not supported and boundary [] when unavailable. Return every domain exactly once and only the required "
        "structured result."
    )


def validate_table_output(value: Any) -> str | None:
    if not isinstance(value, dict):
        return "output_not_object"
    if value.get("schema_version") != TABLE_SCHEMA_VERSION:
        return "schema_version_mismatch"
    if value.get("document_status") not in {"completed", "unsupported", "ambiguous"}:
        return "document_status_invalid"
    if not _strings(value.get("warnings")) or not isinstance(value.get("tables"), list):
        return "top_level_shape_invalid"
    seen: set[tuple[int, int]] = set()
    for table in value["tables"]:
        required = {
            "page", "order_on_page", "boundary", "row_count", "column_count", "header_rows", "rows",
            "continuation_page", "continuation_order_on_page", "uncertainty",
        }
        if not isinstance(table, dict) or set(table) != required:
            return "table_shape_invalid"
        page, order = table.get("page"), table.get("order_on_page")
        if not _positive_int(page) or not _positive_int(order) or (page, order) in seen:
            return "table_identity_invalid"
        seen.add((page, order))
        if not _bbox(table.get("boundary")) or not _strings(table.get("uncertainty")):
            return "table_evidence_invalid"
        if not all(_nonnegative_int(table.get(key)) for key in ("row_count", "column_count", "header_rows", "continuation_page", "continuation_order_on_page")):
            return "table_counts_invalid"
        rows = table.get("rows")
        if not isinstance(rows, list) or len(rows) != table["row_count"]:
            return "row_count_mismatch"
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"row_kind", "cells"}:
                return "row_shape_invalid"
            if row.get("row_kind") not in ROW_KINDS or not _strings(row.get("cells")):
                return "row_content_invalid"
            if len(row["cells"]) != table["column_count"]:
                return "column_count_mismatch"
    return None


def validate_business_output(value: Any) -> str | None:
    if not isinstance(value, dict) or value.get("schema_version") != BUSINESS_SCHEMA_VERSION:
        return "schema_or_object_invalid"
    if not _strings(value.get("warnings")) or not isinstance(value.get("domains"), list):
        return "top_level_shape_invalid"
    if len(value["domains"]) != len(DOMAIN_IDS):
        return "domain_count_mismatch"
    seen: set[str] = set()
    for domain in value["domains"]:
        if not isinstance(domain, dict) or set(domain) != {"domain", "status", "facts", "uncertainty"}:
            return "domain_shape_invalid"
        domain_id = domain.get("domain")
        if domain_id not in DOMAIN_IDS or domain_id in seen or domain.get("status") not in DOMAIN_STATUSES:
            return "domain_identity_invalid"
        seen.add(domain_id)
        if not _strings(domain.get("uncertainty")) or not isinstance(domain.get("facts"), list):
            return "domain_content_invalid"
        if domain["status"] != "typed_fact" and domain["facts"]:
            return "non_fact_status_has_facts"
        for fact in domain["facts"]:
            required = {
                "fact_type", "fields", "page", "table_order_on_page", "row_label", "column_label",
                "boundary", "provider_citation", "uncertainty",
            }
            if not isinstance(fact, dict) or set(fact) != required:
                return "fact_shape_invalid"
            if not all(isinstance(fact.get(key), str) for key in ("fact_type", "row_label", "column_label", "provider_citation")):
                return "fact_text_invalid"
            if not _nonnegative_int(fact.get("page")) or not _nonnegative_int(fact.get("table_order_on_page")):
                return "fact_location_invalid"
            if not _bbox(fact.get("boundary")) or not _strings(fact.get("uncertainty")):
                return "fact_evidence_invalid"
            fields = fact.get("fields")
            if not isinstance(fields, list) or not fields:
                return "fact_fields_invalid"
            for field in fields:
                if not isinstance(field, dict) or set(field) != {"name", "value"}:
                    return "field_shape_invalid"
                if not isinstance(field.get("name"), str) or not isinstance(field.get("value"), str):
                    return "field_text_invalid"
    return None


def score_tables(reference: dict[str, dict[str, Any]], output: Any) -> dict[str, Any]:
    validation_error = validate_table_output(output)
    predicted = {} if validation_error else {
        f"{table['page']}:{table['order_on_page']}": table for table in output["tables"]
    }
    ref_keys = set(reference)
    found_keys = set(predicted)
    cell_exact = cell_total = numeric_exact = numeric_total = 0
    structures = headers = header_total = hallucinated = omitted = 0
    for key, ref in reference.items():
        actual = predicted.get(key)
        expected_rows = ref["cells"]
        actual_rows = [row["cells"] for row in actual["rows"]] if actual else []
        expected_cols = max((len(row) for row in expected_rows), default=0)
        actual_cols = max((len(row) for row in actual_rows), default=0)
        if actual and len(actual_rows) == len(expected_rows) and actual_cols == expected_cols:
            structures += 1
        if ref.get("header_rows") is not None:
            header_total += 1
            headers += bool(actual and actual.get("header_rows") == ref["header_rows"])
        for row in range(max(len(expected_rows), len(actual_rows))):
            for column in range(max(expected_cols, actual_cols)):
                left = _cell(expected_rows, row, column)
                right = _cell(actual_rows, row, column)
                cell_total += 1
                cell_exact += left == right
                if _numeric(left):
                    numeric_total += 1
                    numeric_exact += left == right
                hallucinated += not left and bool(right)
                omitted += bool(left) and not right
    return {
        "validation_error": validation_error,
        "reference_tables": len(ref_keys),
        "discovered_tables": len(found_keys),
        "matched_tables": len(ref_keys & found_keys),
        "missed_tables": len(ref_keys - found_keys),
        "false_tables": len(found_keys - ref_keys),
        "table_detection_recall": _ratio(len(ref_keys & found_keys), len(ref_keys)),
        "exact_structures": structures,
        "exact_headers": headers,
        "header_tables_scored": header_total,
        "cells_exact": cell_exact,
        "cells_total": cell_total,
        "cell_accuracy": _ratio(cell_exact, cell_total),
        "numeric_exact": numeric_exact,
        "numeric_total": numeric_total,
        "numeric_accuracy": _ratio(numeric_exact, numeric_total),
        "hallucinated_nonempty_cells": hallucinated,
        "omitted_nonempty_cells": omitted,
        "continuation_4_1_to_3_2": bool(
            predicted.get("4:1")
            and predicted["4:1"].get("continuation_page") == 3
            and predicted["4:1"].get("continuation_order_on_page") == 2
        ),
    }


def assess_business(output: Any, page_texts: list[str]) -> dict[str, Any]:
    validation_error = validate_business_output(output)
    domains = [] if validation_error else output["domains"]
    facts = [fact for domain in domains for fact in domain["facts"]]
    field_total = field_relocated = numeric_total = numeric_relocated = 0
    page_supported = table_supported = bbox_supported = citation_supported = 0
    for fact in facts:
        page = fact["page"]
        text = page_texts[page - 1] if 1 <= page <= len(page_texts) else ""
        page_supported += 1 <= page <= len(page_texts)
        table_supported += fact["table_order_on_page"] > 0
        bbox_supported += len(fact["boundary"]) == 4
        citation_supported += bool(fact["provider_citation"].strip())
        for field in fact["fields"]:
            value = normalize_cell(field["value"])
            relocated = bool(value and value in normalize_cell(text))
            field_total += 1
            field_relocated += relocated
            if _numeric(value):
                numeric_total += 1
                numeric_relocated += relocated
    strongest_claimed = 0
    if facts and page_supported == len(facts):
        strongest_claimed = 1
    if facts and table_supported == len(facts):
        strongest_claimed = 2
    if facts and (bbox_supported == len(facts) or citation_supported == len(facts)):
        strongest_claimed = 3
    uniformly_verified = 1 if field_total and field_relocated == field_total and page_supported == len(facts) else 0
    return {
        "validation_error": validation_error,
        "domains": {item["domain"]: item["status"] for item in domains},
        "typed_facts": len(facts),
        "fields_total": field_total,
        "fields_exactly_relocated_on_claimed_page": field_relocated,
        "field_relocation_rate": _ratio(field_relocated, field_total),
        "numeric_fields_total": numeric_total,
        "numeric_fields_exactly_relocated_on_claimed_page": numeric_relocated,
        "numeric_relocation_rate": _ratio(numeric_relocated, numeric_total),
        "facts_with_page": page_supported,
        "facts_with_table_identity": table_supported,
        "facts_with_bbox": bbox_supported,
        "facts_with_provider_citation": citation_supported,
        "strongest_claimed_provenance_level": strongest_claimed,
        "strongest_uniformly_verified_provenance_level": uniformly_verified,
        "level_4_exact_source_ref": False,
        "posthoc_exact_page_text_relocation_used": True,
        "posthoc_fuzzy_matching_used": False,
        "authoritative_fact_acceptance": "rejected",
        "human_reference_precision_recall_available": False,
    }


def schema_hash(schema: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_bytes(schema)).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def normalize_cell(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split())


def _cell(rows: list[list[str]], row: int, column: int) -> str:
    if row >= len(rows) or column >= len(rows[row]):
        return ""
    return normalize_cell(rows[row][column])


def _numeric(value: str) -> bool:
    return bool(value and re.fullmatch(r"[+\-−–—]?\(?\d[\d\s.,%]*\)?", value))


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _bbox(value: Any) -> bool:
    return isinstance(value, list) and len(value) in {0, 4} and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _ratio(left: int, right: int) -> float:
    return round(left / right, 6) if right else 0.0
