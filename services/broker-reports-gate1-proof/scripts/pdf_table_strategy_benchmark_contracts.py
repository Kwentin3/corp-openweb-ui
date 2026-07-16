from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from typing import Any


EXPERIMENT_VERSION = "broker_reports_pdf_table_strategy_benchmark_v1"
PROMPT_CONTRACT_VERSION = "broker_reports_pdf_table_strategy_prompts_v1"
MODEL_VIEW_SCHEMA_VERSION = "broker_reports_pdf_table_strategy_model_view_v1"
DIRECT_PAGE_MODEL_VIEW_VERSION = "direct_v1"
DETECTION_MODEL_VIEW_VERSION = "detection_v1"
CROP_EXTRACTION_MODEL_VIEW_VERSION = "crop_v1"
DETECTION_SCHEMA_VERSION = "broker_reports_pdf_table_strategy_detection_v1"
UNIFIED_EXTRACTION_SCHEMA_VERSION = (
    "broker_reports_pdf_table_strategy_unified_extraction_v1"
)
EVIDENCE_SCHEMA_VERSION = "broker_reports_pdf_table_strategy_evidence_v1"

# Compatibility aliases keep the research runner vocabulary explicit without
# creating a second contract.
DETECTION_OUTPUT_SCHEMA_VERSION = DETECTION_SCHEMA_VERSION
UNIFIED_OUTPUT_SCHEMA_VERSION = UNIFIED_EXTRACTION_SCHEMA_VERSION
TABLE_EXTRACTION_SCHEMA_VERSION = UNIFIED_EXTRACTION_SCHEMA_VERSION

INPUT_IMAGE_NORMALIZED = "input_image_normalized"
PAGE_NORMALIZED = "page_normalized"
COORDINATE_SPACES = frozenset({INPUT_IMAGE_NORMALIZED, PAGE_NORMALIZED})

DETECTION_PRESENCE = frozenset({"present", "absent", "uncertain"})
DOCUMENT_STATUSES = frozenset(
    {"completed", "no_tables", "partial", "unsupported", "ambiguous"}
)
TABLE_DECISIONS = frozenset({"resolved", "ambiguous", "unsupported"})
POSSIBLE_TABLE_TYPES = frozenset(
    {
        "simple_ruled",
        "borderless",
        "sparse_financial",
        "multi_row_header",
        "compound",
        "raster_or_image",
        "unknown",
    }
)
SEMANTIC_ROLES = frozenset(
    {
        "header",
        "amount",
        "currency",
        "unit",
        "period",
        "description",
        "entity",
        "unknown",
    }
)
LOGICAL_TYPES = frozenset(
    {
        "header",
        "text",
        "monetary_amount",
        "currency",
        "unit",
        "period",
        "entity",
        "unknown",
    }
)
QUALIFIER_KINDS = frozenset({"currency", "unit", "unknown"})
EVIDENCE_STATUSES = frozenset(
    {"traced", "ambiguous", "not_found", "unsupported"}
)
EVIDENCE_DISPOSITIONS = frozenset({"accept", "reject", "review"})
_EVIDENCE_DISPOSITION_BY_STATUS = {
    "traced": "accept",
    "not_found": "reject",
    "ambiguous": "review",
    "unsupported": "review",
}

MAX_EVIDENCE_WORDS_PER_CELL = 512
MAX_EVIDENCE_WORDS_PER_PAGE = 10_000
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


DIRECT_PAGE_PROMPT = (
    "Inspect only the supplied single PDF page image and return the versioned "
    "unified table extraction contract. Find every visible table on that page. "
    "Keep physical rows, columns, cells, empty cells, merged regions and geometry "
    "separate from semantic fields and qualifier relationships. Preserve visible "
    "cell text exactly. Do not calculate, normalize, repair, mutate or invent any "
    "financial value. Do not force a single answer when physical or semantic "
    "structure is ambiguous; return explicit alternatives and uncertainty instead. "
    "A visible currency symbol is evidence only: never infer an ISO currency code "
    "from a symbol. Set normalized_code to null unless an unambiguous literal code "
    "is visible. Return only the required JSON object."
)

DETECTION_PROMPT = (
    "Inspect only the supplied single PDF page image and perform table-region "
    "detection, not table extraction. Return only presence plus bounded normalized "
    "regions with confidence, a possible table type and uncertainty codes. Do not "
    "return or infer rows, columns, cells, headers, merged cells, semantic roles, "
    "currency meaning or financial values. Do not force presence, a type or a box "
    "when the image is uncertain. Return only the required JSON object."
)

CROP_EXTRACTION_PROMPT = (
    "Analyze only the supplied table crop and return the versioned unified table "
    "extraction contract. The crop boundary is already selected: do not rediscover "
    "the page, search outside the crop, expand or shrink the crop, or propose another "
    "page region. Use [0,0,1,1] as the table bbox in crop-normalized coordinates. "
    "Keep physical structure separate from semantic fields and qualifier relations. "
    "Preserve visible text and explicit empty cells. Do not calculate, normalize, "
    "repair, mutate or invent financial values. Do not force a single answer when "
    "structure or meaning is ambiguous. A visible currency symbol must never be "
    "converted to an ISO code; normalized_code is null unless a literal unambiguous "
    "code is visible. Prefix every table_id with the table_id_prefix supplied in "
    "the model view. Return only the required JSON object."
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def detection_schema() -> dict[str, Any]:
    region = _closed_object(
        {
            "region_id": _identifier_schema(),
            "bbox": _bbox_schema(),
            "coordinate_space": {
                "type": "string",
                "enum": [INPUT_IMAGE_NORMALIZED],
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "possible_table_type": {
                "type": "string",
                "enum": sorted(POSSIBLE_TABLE_TYPES),
            },
            "uncertainty_codes": _string_array_schema(),
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": DETECTION_SCHEMA_VERSION,
        **_closed_object(
            {
                "schema_version": {
                    "type": "string",
                    "enum": [DETECTION_SCHEMA_VERSION],
                },
                "presence": {
                    "type": "string",
                    "enum": sorted(DETECTION_PRESENCE),
                },
                "regions": {
                    "type": "array",
                    "maxItems": 4,
                    "items": region,
                },
                "uncertainty_codes": _string_array_schema(),
            }
        ),
    }


def unified_extraction_schema() -> dict[str, Any]:
    physical = _physical_schema()
    semantic = _semantic_schema()
    alternative = _closed_object(
        {
            "alternative_id": _identifier_schema(),
            "physical": copy.deepcopy(physical),
            "semantic": copy.deepcopy(semantic),
            "uncertainty_codes": _string_array_schema(),
        }
    )
    table = _closed_object(
        {
            "table_id": _identifier_schema(),
            "bbox": _bbox_schema(),
            "coordinate_space": {
                "type": "string",
                "enum": sorted(COORDINATE_SPACES),
            },
            "decision": {"type": "string", "enum": sorted(TABLE_DECISIONS)},
            "physical": physical,
            "semantic": semantic,
            "alternatives": {"type": "array", "items": alternative},
            "uncertainty_codes": _string_array_schema(),
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": UNIFIED_EXTRACTION_SCHEMA_VERSION,
        **_closed_object(
            {
                "schema_version": {
                    "type": "string",
                    "enum": [UNIFIED_EXTRACTION_SCHEMA_VERSION],
                },
                "document_status": {
                    "type": "string",
                    "enum": sorted(DOCUMENT_STATUSES),
                },
                "tables": {"type": "array", "items": table},
                "uncertainty_codes": _string_array_schema(),
            }
        ),
    }


def table_extraction_schema() -> dict[str, Any]:
    return unified_extraction_schema()


def evidence_schema() -> dict[str, Any]:
    source_bbox = {
        "type": "array",
        "minItems": 4,
        "maxItems": 4,
        "items": {"type": "number"},
    }
    match = _closed_object(
        {
            "parser_ordinals": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "integer", "minimum": 1},
            },
            "bboxes": {"type": "array", "minItems": 1, "items": source_bbox},
            "matched_text": {"type": "string"},
        }
    )
    cell = _closed_object(
        {
            "table_id": _identifier_schema(),
            "alternative_id": {
                "anyOf": [_identifier_schema(), {"type": "null"}]
            },
            "cell_id": _identifier_schema(),
            "status": {"type": "string", "enum": sorted(EVIDENCE_STATUSES)},
            "disposition": {
                "type": "string",
                "enum": sorted(EVIDENCE_DISPOSITIONS),
            },
            "matches": {"type": "array", "items": match},
            "reason_codes": _string_array_schema(),
        }
    )
    status_counts = _closed_object(
        {
            status: {"type": "integer", "minimum": 0}
            for status in sorted(EVIDENCE_STATUSES)
        }
    )
    summary = _closed_object(
        {
            "nonempty_cells_total": {"type": "integer", "minimum": 0},
            "status_counts": status_counts,
            "traced_cells": {"type": "integer", "minimum": 0},
            "accepted_cells": {"type": "integer", "minimum": 0},
            "rejected_cells": {"type": "integer", "minimum": 0},
            "human_review_cells": {"type": "integer", "minimum": 0},
            "false_accepted_values": {"type": "integer", "enum": [0]},
            "provenance_coverage": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
            },
        }
    )
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": EVIDENCE_SCHEMA_VERSION,
        **_closed_object(
            {
                "schema_version": {
                    "type": "string",
                    "enum": [EVIDENCE_SCHEMA_VERSION],
                },
                "extraction_sha256": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
                "page_geometry": _closed_object(
                    {
                        "width": {"type": "number", "exclusiveMinimum": 0},
                        "height": {"type": "number", "exclusiveMinimum": 0},
                    }
                ),
                "usable_word_atoms": {"type": "integer", "minimum": 0},
                "cells": {"type": "array", "items": cell},
                "summary": summary,
                "parser_role": {
                    "type": "string",
                    "enum": ["evidence_and_coordinate_layer_only"],
                },
                "table_construction_performed": {
                    "type": "boolean",
                    "enum": [False],
                },
                "value_mutation_performed": {
                    "type": "boolean",
                    "enum": [False],
                },
                "extraction_unchanged": {"type": "boolean", "enum": [True]},
                "evidence_checksum": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                },
            }
        ),
    }


def direct_page_model_view(
    *,
    case_id: str,
    page_number: int,
    input_image_sha256: str | None = None,
) -> dict[str, Any]:
    return _model_view(
        case_id=case_id,
        page_number=page_number,
        strategy_id="strategy_a_direct_vlm",
        prompt_contract_version=DIRECT_PAGE_MODEL_VIEW_VERSION,
        task=DIRECT_PAGE_PROMPT,
        input_kind="single_pdf_page_image",
        output_schema=unified_extraction_schema(),
        extra_identity=(
            {"input_image_sha256": input_image_sha256}
            if input_image_sha256 is not None
            else {}
        ),
        rules={
            "whole_document_prompt": False,
            "page_region_rediscovery_allowed": True,
            "invented_values_allowed": False,
            "forced_guessing_allowed": False,
            "currency_symbol_to_iso_inference_allowed": False,
            "physical_semantic_separation_required": True,
        },
    )


def detection_model_view(
    *,
    case_id: str,
    page_number: int,
    input_image_sha256: str | None = None,
) -> dict[str, Any]:
    return _model_view(
        case_id=case_id,
        page_number=page_number,
        strategy_id="strategy_b_detection_only",
        prompt_contract_version=DETECTION_MODEL_VIEW_VERSION,
        task=DETECTION_PROMPT,
        input_kind="single_pdf_page_image",
        output_schema=detection_schema(),
        extra_identity=(
            {"input_image_sha256": input_image_sha256}
            if input_image_sha256 is not None
            else {}
        ),
        rules={
            "table_extraction_allowed": False,
            "rows_columns_cells_allowed": False,
            "financial_values_allowed": False,
            "forced_guessing_allowed": False,
            "region_coordinate_space": INPUT_IMAGE_NORMALIZED,
        },
    )


def crop_extraction_model_view(
    *,
    case_id: str,
    page_number: int,
    region_index: int,
    input_image_sha256: str | None = None,
) -> dict[str, Any]:
    if not _positive_int(region_index):
        raise ValueError("benchmark_region_index_invalid")
    identity = {"region_index": region_index}
    if input_image_sha256 is not None:
        identity["input_image_sha256"] = input_image_sha256
    return _model_view(
        case_id=case_id,
        page_number=page_number,
        strategy_id="shared_two_step_crop_extraction",
        prompt_contract_version=CROP_EXTRACTION_MODEL_VIEW_VERSION,
        task=CROP_EXTRACTION_PROMPT,
        input_kind="detected_table_crop_image",
        output_schema=unified_extraction_schema(),
        extra_identity=identity,
        rules={
            "page_region_rediscovery_allowed": False,
            "crop_boundary_change_allowed": False,
            "table_bbox_must_equal_full_crop": True,
            "table_id_prefix": f"region_{region_index}_",
            "invented_values_allowed": False,
            "forced_guessing_allowed": False,
            "currency_symbol_to_iso_inference_allowed": False,
            "physical_semantic_separation_required": True,
        },
    )


def validate_detection_output(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["benchmark_detection_output_not_object"]
    expected_keys = {"schema_version", "presence", "regions", "uncertainty_codes"}
    if set(value) != expected_keys:
        errors.append("benchmark_detection_keys_invalid")
    if value.get("schema_version") != DETECTION_SCHEMA_VERSION:
        errors.append("benchmark_detection_schema_invalid")
    presence = value.get("presence")
    if presence not in DETECTION_PRESENCE:
        errors.append("benchmark_detection_presence_invalid")
    if not _valid_code_list(value.get("uncertainty_codes")):
        errors.append("benchmark_detection_uncertainty_invalid")

    raw_regions = value.get("regions")
    regions = raw_regions if isinstance(raw_regions, list) else []
    if not isinstance(raw_regions, list):
        errors.append("benchmark_detection_regions_not_array")
    if len(regions) > 4:
        errors.append("benchmark_detection_region_budget_exceeded")
    region_ids: set[str] = set()
    for region in regions:
        if not isinstance(region, dict):
            errors.append("benchmark_detection_region_not_object")
            continue
        if set(region) != {
            "region_id",
            "bbox",
            "coordinate_space",
            "confidence",
            "possible_table_type",
            "uncertainty_codes",
        }:
            errors.append("benchmark_detection_region_keys_invalid")
        region_id = region.get("region_id")
        if not _valid_identifier(region_id) or region_id in region_ids:
            errors.append("benchmark_detection_region_id_invalid")
        elif isinstance(region_id, str):
            region_ids.add(region_id)
        if _normalized_bbox(region.get("bbox")) is None:
            errors.append("benchmark_detection_region_bbox_invalid")
        if region.get("coordinate_space") != INPUT_IMAGE_NORMALIZED:
            errors.append("benchmark_detection_coordinate_space_invalid")
        confidence = region.get("confidence")
        if not _number(confidence) or not 0.0 <= float(confidence) <= 1.0:
            errors.append("benchmark_detection_confidence_invalid")
        if region.get("possible_table_type") not in POSSIBLE_TABLE_TYPES:
            errors.append("benchmark_detection_table_type_invalid")
        if not _valid_code_list(region.get("uncertainty_codes")):
            errors.append("benchmark_detection_region_uncertainty_invalid")

    if presence == "present" and not regions:
        errors.append("benchmark_detection_present_without_region")
    if presence == "absent" and regions:
        errors.append("benchmark_detection_absent_with_region")
    if presence == "uncertain" and not value.get("uncertainty_codes"):
        errors.append("benchmark_detection_uncertain_without_reason")
    return sorted(set(errors))


def validate_detection(value: Any) -> list[str]:
    return validate_detection_output(value)


def validate_unified_extraction(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["benchmark_extraction_output_not_object"]
    if set(value) != {
        "schema_version",
        "document_status",
        "tables",
        "uncertainty_codes",
    }:
        errors.append("benchmark_extraction_keys_invalid")
    if value.get("schema_version") != UNIFIED_EXTRACTION_SCHEMA_VERSION:
        errors.append("benchmark_extraction_schema_invalid")
    status = value.get("document_status")
    if status not in DOCUMENT_STATUSES:
        errors.append("benchmark_extraction_document_status_invalid")
    if not _valid_code_list(value.get("uncertainty_codes")):
        errors.append("benchmark_extraction_uncertainty_invalid")

    raw_tables = value.get("tables")
    tables = raw_tables if isinstance(raw_tables, list) else []
    if not isinstance(raw_tables, list):
        errors.append("benchmark_extraction_tables_not_array")
    table_ids: set[str] = set()
    decisions: list[str] = []
    for table in tables:
        if not isinstance(table, dict):
            errors.append("benchmark_extraction_table_not_object")
            continue
        if set(table) != {
            "table_id",
            "bbox",
            "coordinate_space",
            "decision",
            "physical",
            "semantic",
            "alternatives",
            "uncertainty_codes",
        }:
            errors.append("benchmark_extraction_table_keys_invalid")
        table_id = table.get("table_id")
        if not _valid_identifier(table_id) or table_id in table_ids:
            errors.append("benchmark_extraction_table_id_invalid")
        elif isinstance(table_id, str):
            table_ids.add(table_id)
        table_bbox = _normalized_bbox(table.get("bbox"))
        if table_bbox is None:
            errors.append("benchmark_extraction_table_bbox_invalid")
        if table.get("coordinate_space") not in COORDINATE_SPACES:
            errors.append("benchmark_extraction_coordinate_space_invalid")
        decision = table.get("decision")
        if decision not in TABLE_DECISIONS:
            errors.append("benchmark_extraction_table_decision_invalid")
        elif isinstance(decision, str):
            decisions.append(decision)
        if not _valid_code_list(table.get("uncertainty_codes")):
            errors.append("benchmark_extraction_table_uncertainty_invalid")

        physical_errors, physical_ids = _validate_physical(
            table.get("physical"),
            scope_bbox=table_bbox,
            prefix="benchmark_extraction",
        )
        errors.extend(physical_errors)
        errors.extend(
            _validate_semantic(
                table.get("semantic"),
                column_ids=physical_ids["column_ids"],
                cell_ids=physical_ids["cell_ids"],
                prefix="benchmark_extraction",
            )
        )

        raw_alternatives = table.get("alternatives")
        alternatives = raw_alternatives if isinstance(raw_alternatives, list) else []
        if not isinstance(raw_alternatives, list):
            errors.append("benchmark_extraction_alternatives_not_array")
        alternative_ids: set[str] = set()
        for alternative in alternatives:
            if not isinstance(alternative, dict) or set(alternative) != {
                "alternative_id",
                "physical",
                "semantic",
                "uncertainty_codes",
            }:
                errors.append("benchmark_extraction_alternative_keys_invalid")
                continue
            alternative_id = alternative.get("alternative_id")
            if (
                not _valid_identifier(alternative_id)
                or alternative_id in alternative_ids
            ):
                errors.append("benchmark_extraction_alternative_id_invalid")
            elif isinstance(alternative_id, str):
                alternative_ids.add(alternative_id)
            if not _valid_code_list(alternative.get("uncertainty_codes")):
                errors.append("benchmark_extraction_alternative_uncertainty_invalid")
            alt_errors, alt_ids = _validate_physical(
                alternative.get("physical"),
                scope_bbox=table_bbox,
                prefix="benchmark_extraction_alternative",
            )
            errors.extend(alt_errors)
            errors.extend(
                _validate_semantic(
                    alternative.get("semantic"),
                    column_ids=alt_ids["column_ids"],
                    cell_ids=alt_ids["cell_ids"],
                    prefix="benchmark_extraction_alternative",
                )
            )
        if decision == "ambiguous" and (
            not alternatives or not table.get("uncertainty_codes")
        ):
            errors.append("benchmark_extraction_ambiguous_alternatives_missing")
        if decision == "resolved" and alternatives:
            errors.append("benchmark_extraction_resolved_has_alternatives")
        if decision == "unsupported" and not table.get("uncertainty_codes"):
            errors.append("benchmark_extraction_unsupported_without_reason")

    if status == "completed" and any(item != "resolved" for item in decisions):
        errors.append("benchmark_extraction_completed_with_unresolved_table")
    if status == "completed" and not tables:
        errors.append("benchmark_extraction_completed_without_table")
    if status == "no_tables" and tables:
        errors.append("benchmark_extraction_no_tables_status_mismatch")
    if status in {"partial", "unsupported", "ambiguous"} and not value.get(
        "uncertainty_codes"
    ):
        errors.append("benchmark_extraction_nonterminal_without_reason")
    if "ambiguous" in decisions and status not in {"ambiguous", "partial"}:
        errors.append("benchmark_extraction_ambiguous_status_mismatch")
    return sorted(set(errors))


def validate_unified_extraction_output(value: Any) -> list[str]:
    return validate_unified_extraction(value)


def project_crop_bbox_to_page(
    extraction: dict[str, Any],
    detected_page_bbox: list[float],
) -> dict[str, Any]:
    """Project all extraction bboxes from crop-normalized to page-normalized.

    A deep copy is returned. The caller's extraction is never modified.
    """

    errors = validate_unified_extraction(extraction)
    if errors:
        raise ValueError(errors[0])
    page_bbox = _normalized_bbox(detected_page_bbox)
    if page_bbox is None:
        raise ValueError("benchmark_detected_page_bbox_invalid")
    result = copy.deepcopy(extraction)
    for table in result.get("tables") or []:
        if table.get("coordinate_space") != INPUT_IMAGE_NORMALIZED:
            raise ValueError("benchmark_extraction_not_crop_normalized")
        table["bbox"] = _project_bbox(table["bbox"], page_bbox)
        table["coordinate_space"] = PAGE_NORMALIZED
        _project_physical_bboxes(table["physical"], page_bbox)
        for alternative in table.get("alternatives") or []:
            _project_physical_bboxes(alternative["physical"], page_bbox)
    projected_errors = validate_unified_extraction(result)
    if projected_errors:
        raise ValueError(projected_errors[0])
    return result


def validate_extraction_evidence(
    extraction: dict[str, Any],
    word_inventory: list[dict[str, Any]],
    page_width: float,
    page_height: float,
) -> dict[str, Any]:
    """Build a parser-evidence overlay without altering VLM extraction.

    Only raw word text, parser ordinal and page-coordinate bbox are consumed.
    No table shape is constructed and no extracted value is repaired.
    """

    extraction_errors = validate_unified_extraction(extraction)
    if extraction_errors:
        raise ValueError(extraction_errors[0])
    if not _number(page_width) or not _number(page_height):
        raise ValueError("benchmark_evidence_page_geometry_invalid")
    width = float(page_width)
    height = float(page_height)
    if width <= 0 or height <= 0:
        raise ValueError("benchmark_evidence_page_geometry_invalid")
    if not isinstance(word_inventory, list):
        raise ValueError("benchmark_evidence_word_inventory_invalid")

    extraction_before = canonical_json_bytes(extraction)
    usable_words = _usable_words(word_inventory)
    cells: list[dict[str, Any]] = []
    counts = {status: 0 for status in sorted(EVIDENCE_STATUSES)}
    for table in extraction.get("tables") or []:
        physical_variants = [(None, table["physical"])] + [
            (alternative["alternative_id"], alternative["physical"])
            for alternative in table.get("alternatives") or []
        ]
        for alternative_id, physical in physical_variants:
            for cell in physical["cells"]:
                if cell["explicit_empty"]:
                    continue
                evidence = _cell_evidence(
                    table_id=table["table_id"],
                    alternative_id=alternative_id,
                    cell=cell,
                    words=usable_words,
                    page_width=width,
                    page_height=height,
                )
                cells.append(evidence)
                counts[evidence["status"]] += 1

    extraction_after = canonical_json_bytes(extraction)
    if extraction_after != extraction_before:
        raise RuntimeError("benchmark_evidence_extraction_mutated")
    nonempty_total = len(cells)
    overlay = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "extraction_sha256": hashlib.sha256(extraction_before).hexdigest(),
        "page_geometry": {"width": width, "height": height},
        "usable_word_atoms": len(usable_words),
        "cells": cells,
        "summary": {
            "nonempty_cells_total": nonempty_total,
            "status_counts": counts,
            "traced_cells": counts["traced"],
            "accepted_cells": counts["traced"],
            "rejected_cells": counts["not_found"],
            "provenance_coverage": round(
                counts["traced"] / nonempty_total, 6
            )
            if nonempty_total
            else 1.0,
            "human_review_cells": counts["ambiguous"] + counts["unsupported"],
            "false_accepted_values": 0,
        },
        "parser_role": "evidence_and_coordinate_layer_only",
        "table_construction_performed": False,
        "value_mutation_performed": False,
        "extraction_unchanged": True,
    }
    overlay["evidence_checksum"] = sha256_json(overlay)
    return overlay


def validate_evidence_overlay(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["benchmark_evidence_overlay_not_object"]
    expected_keys = {
        "schema_version",
        "extraction_sha256",
        "page_geometry",
        "usable_word_atoms",
        "cells",
        "summary",
        "parser_role",
        "table_construction_performed",
        "value_mutation_performed",
        "extraction_unchanged",
        "evidence_checksum",
    }
    if set(value) != expected_keys:
        errors.append("benchmark_evidence_overlay_keys_invalid")
    if value.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append("benchmark_evidence_overlay_schema_invalid")
    if not _sha256(value.get("extraction_sha256")):
        errors.append("benchmark_evidence_extraction_hash_invalid")
    page_geometry = value.get("page_geometry")
    if (
        not isinstance(page_geometry, dict)
        or set(page_geometry) != {"width", "height"}
        or not _number(page_geometry.get("width"))
        or not _number(page_geometry.get("height"))
        or float(page_geometry.get("width", 0)) <= 0
        or float(page_geometry.get("height", 0)) <= 0
    ):
        errors.append("benchmark_evidence_page_geometry_invalid")
    if not _nonnegative_int(value.get("usable_word_atoms")):
        errors.append("benchmark_evidence_word_count_invalid")
    if (
        value.get("parser_role") != "evidence_and_coordinate_layer_only"
        or value.get("table_construction_performed") is not False
        or value.get("value_mutation_performed") is not False
        or value.get("extraction_unchanged") is not True
    ):
        errors.append("benchmark_evidence_authority_boundary_invalid")

    raw_cells = value.get("cells")
    cells = raw_cells if isinstance(raw_cells, list) else []
    if not isinstance(raw_cells, list):
        errors.append("benchmark_evidence_cells_not_array")
    observed_counts = {status: 0 for status in sorted(EVIDENCE_STATUSES)}
    identities: set[tuple[str, str | None, str]] = set()
    for cell in cells:
        if not isinstance(cell, dict) or set(cell) != {
            "table_id",
            "alternative_id",
            "cell_id",
            "status",
            "disposition",
            "matches",
            "reason_codes",
        }:
            errors.append("benchmark_evidence_cell_keys_invalid")
            continue
        table_id = cell.get("table_id")
        alternative_id = cell.get("alternative_id")
        cell_id = cell.get("cell_id")
        identity_valid = (
            _valid_identifier(table_id)
            and _valid_identifier(cell_id)
            and (alternative_id is None or _valid_identifier(alternative_id))
        )
        identity = (
            (str(table_id), alternative_id, str(cell_id))
            if identity_valid
            else None
        )
        if not identity_valid or identity in identities:
            errors.append("benchmark_evidence_cell_identity_invalid")
        elif identity is not None:
            identities.add(identity)
        status = cell.get("status")
        disposition = cell.get("disposition")
        if not isinstance(status, str) or status not in EVIDENCE_STATUSES:
            errors.append("benchmark_evidence_cell_status_invalid")
        else:
            observed_counts[status] += 1
            if disposition != _EVIDENCE_DISPOSITION_BY_STATUS[status]:
                errors.append("benchmark_evidence_cell_disposition_invalid")
        raw_matches = cell.get("matches")
        matches = raw_matches if isinstance(raw_matches, list) else []
        if not isinstance(raw_matches, list):
            errors.append("benchmark_evidence_matches_not_array")
        for match in matches:
            if not isinstance(match, dict) or set(match) != {
                "parser_ordinals",
                "bboxes",
                "matched_text",
            }:
                errors.append("benchmark_evidence_match_keys_invalid")
                continue
            ordinals = match.get("parser_ordinals")
            bboxes = match.get("bboxes")
            if (
                not isinstance(ordinals, list)
                or not ordinals
                or not all(_positive_int(item) for item in ordinals)
                or not isinstance(bboxes, list)
                or len(bboxes) != len(ordinals)
                or any(_positive_bbox(item) is None for item in bboxes)
                or not isinstance(match.get("matched_text"), str)
            ):
                errors.append("benchmark_evidence_match_invalid")
        if status == "traced" and len(matches) != 1:
            errors.append("benchmark_evidence_traced_match_count_invalid")
        if status == "ambiguous" and len(matches) < 2:
            errors.append("benchmark_evidence_ambiguous_match_count_invalid")
        if status == "unsupported" and matches:
            errors.append("benchmark_evidence_unsupported_has_matches")
        if not _valid_code_list(cell.get("reason_codes")):
            errors.append("benchmark_evidence_reason_codes_invalid")

    summary = value.get("summary")
    expected_summary_keys = {
        "nonempty_cells_total",
        "status_counts",
        "traced_cells",
        "accepted_cells",
        "rejected_cells",
        "human_review_cells",
        "false_accepted_values",
        "provenance_coverage",
    }
    if not isinstance(summary, dict) or set(summary) != expected_summary_keys:
        errors.append("benchmark_evidence_summary_keys_invalid")
    else:
        expected_coverage = (
            round(observed_counts["traced"] / len(cells), 6) if cells else 1.0
        )
        if (
            summary.get("nonempty_cells_total") != len(cells)
            or summary.get("status_counts") != observed_counts
            or summary.get("traced_cells") != observed_counts["traced"]
            or summary.get("accepted_cells") != observed_counts["traced"]
            or summary.get("rejected_cells") != observed_counts["not_found"]
            or summary.get("human_review_cells")
            != observed_counts["ambiguous"] + observed_counts["unsupported"]
            or summary.get("false_accepted_values") != 0
            or summary.get("provenance_coverage") != expected_coverage
        ):
            errors.append("benchmark_evidence_summary_accounting_invalid")
    unsigned = dict(value)
    checksum = unsigned.pop("evidence_checksum", None)
    if not _sha256(checksum) or checksum != sha256_json(unsigned):
        errors.append("benchmark_evidence_checksum_invalid")
    return sorted(set(errors))


def _model_view(
    *,
    case_id: str,
    page_number: int,
    strategy_id: str,
    prompt_contract_version: str,
    task: str,
    input_kind: str,
    output_schema: dict[str, Any],
    extra_identity: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    if not _valid_identifier(case_id):
        raise ValueError("benchmark_case_id_invalid")
    if not _positive_int(page_number):
        raise ValueError("benchmark_page_number_invalid")
    if "input_image_sha256" in extra_identity and not _sha256(
        extra_identity["input_image_sha256"]
    ):
        raise ValueError("benchmark_input_image_sha256_invalid")
    return {
        "schema_version": MODEL_VIEW_SCHEMA_VERSION,
        "experiment_version": EXPERIMENT_VERSION,
        "prompt_contract_version": prompt_contract_version,
        "prompt_family_version": PROMPT_CONTRACT_VERSION,
        "strategy_id": strategy_id,
        "task": task,
        "identity": {
            "case_id": case_id,
            "page_number": page_number,
            **copy.deepcopy(extra_identity),
        },
        "input": {
            "kind": input_kind,
            "coordinate_space": INPUT_IMAGE_NORMALIZED,
        },
        "output_contract": {
            "schema_version": output_schema["$id"],
            "schema_sha256": sha256_json(output_schema),
        },
        "rules": copy.deepcopy(rules),
    }


def _physical_schema() -> dict[str, Any]:
    row = _closed_object(
        {
            "row_id": _identifier_schema(),
            "ordinal": {"type": "integer", "minimum": 1},
            "bbox": _bbox_schema(),
        }
    )
    column = _closed_object(
        {
            "column_id": _identifier_schema(),
            "ordinal": {"type": "integer", "minimum": 1},
            "bbox": _bbox_schema(),
        }
    )
    cell = _closed_object(
        {
            "cell_id": _identifier_schema(),
            "row_id": _identifier_schema(),
            "column_id": _identifier_schema(),
            "bbox": _bbox_schema(),
            "text": {"type": "string"},
            "explicit_empty": {"type": "boolean"},
            "uncertainty_codes": _string_array_schema(),
        }
    )
    merged = _closed_object(
        {
            "merged_region_id": _identifier_schema(),
            "cell_ids": {
                "type": "array",
                "minItems": 2,
                "items": _identifier_schema(),
            },
            "bbox": _bbox_schema(),
            "uncertainty_codes": _string_array_schema(),
        }
    )
    return _closed_object(
        {
            "row_count": {"type": "integer", "minimum": 1},
            "column_count": {"type": "integer", "minimum": 1},
            "rows": {"type": "array", "items": row},
            "columns": {"type": "array", "items": column},
            "cells": {"type": "array", "items": cell},
            "merged_regions": {"type": "array", "items": merged},
        }
    )


def _semantic_schema() -> dict[str, Any]:
    field = _closed_object(
        {
            "field_id": _identifier_schema(),
            "role": {"type": "string", "enum": sorted(SEMANTIC_ROLES)},
            "logical_type": {"type": "string", "enum": sorted(LOGICAL_TYPES)},
            "physical_column_ids": {
                "type": "array",
                "minItems": 1,
                "items": _identifier_schema(),
            },
            "header_cell_ids": {"type": "array", "items": _identifier_schema()},
            "qualifier_ids": {"type": "array", "items": _identifier_schema()},
            "uncertainty_codes": _string_array_schema(),
        }
    )
    qualifier = _closed_object(
        {
            "qualifier_id": _identifier_schema(),
            "kind": {"type": "string", "enum": sorted(QUALIFIER_KINDS)},
            "target_field_id": _identifier_schema(),
            "physical_column_ids": {
                "type": "array",
                "minItems": 1,
                "items": _identifier_schema(),
            },
            "evidence_cell_ids": {
                "type": "array",
                "items": _identifier_schema(),
            },
            "normalized_code": {
                "anyOf": [{"type": "string", "minLength": 1}, {"type": "null"}]
            },
            "uncertainty_codes": _string_array_schema(),
        }
    )
    return _closed_object(
        {
            "fields": {"type": "array", "items": field},
            "qualifiers": {"type": "array", "items": qualifier},
        }
    )


def _closed_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": sorted(properties),
    }


def _bbox_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": 4,
        "maxItems": 4,
        "items": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    }


def _identifier_schema() -> dict[str, Any]:
    return {"type": "string", "pattern": _IDENTIFIER.pattern}


def _string_array_schema() -> dict[str, Any]:
    return {"type": "array", "items": {"type": "string"}}


def _validate_physical(
    value: Any,
    *,
    scope_bbox: list[float] | None,
    prefix: str,
) -> tuple[list[str], dict[str, set[str]]]:
    errors: list[str] = []
    empty_ids = {"row_ids": set(), "column_ids": set(), "cell_ids": set()}
    if not isinstance(value, dict):
        return [f"{prefix}_physical_not_object"], empty_ids
    if set(value) != {
        "row_count",
        "column_count",
        "rows",
        "columns",
        "cells",
        "merged_regions",
    }:
        errors.append(f"{prefix}_physical_keys_invalid")
    rows_count = value.get("row_count")
    columns_count = value.get("column_count")
    if not _positive_int(rows_count) or not _positive_int(columns_count):
        errors.append(f"{prefix}_physical_counts_invalid")
        rows_count = 0
        columns_count = 0
    raw_rows = value.get("rows")
    raw_columns = value.get("columns")
    raw_cells = value.get("cells")
    rows = raw_rows if isinstance(raw_rows, list) else []
    columns = raw_columns if isinstance(raw_columns, list) else []
    cells = raw_cells if isinstance(raw_cells, list) else []
    if not isinstance(raw_rows, list) or len(rows) != rows_count:
        errors.append(f"{prefix}_row_count_mismatch")
    if not isinstance(raw_columns, list) or len(columns) != columns_count:
        errors.append(f"{prefix}_column_count_mismatch")
    if not isinstance(raw_cells, list) or len(cells) != rows_count * columns_count:
        errors.append(f"{prefix}_cell_count_mismatch")

    row_ids, row_ordinals = _axis_ids(
        rows, id_key="row_id", count=rows_count, scope_bbox=scope_bbox
    )
    column_ids, column_ordinals = _axis_ids(
        columns, id_key="column_id", count=columns_count, scope_bbox=scope_bbox
    )
    if row_ids is None or row_ordinals != set(range(1, rows_count + 1)):
        errors.append(f"{prefix}_rows_invalid")
        row_ids = set()
    if column_ids is None or column_ordinals != set(range(1, columns_count + 1)):
        errors.append(f"{prefix}_columns_invalid")
        column_ids = set()

    cell_ids: set[str] = set()
    positions: set[tuple[str, str]] = set()
    cell_by_id: dict[str, dict[str, Any]] = {}
    for cell in cells:
        if not isinstance(cell, dict) or set(cell) != {
            "cell_id",
            "row_id",
            "column_id",
            "bbox",
            "text",
            "explicit_empty",
            "uncertainty_codes",
        }:
            errors.append(f"{prefix}_cell_keys_invalid")
            continue
        cell_id = cell.get("cell_id")
        row_id = cell.get("row_id")
        column_id = cell.get("column_id")
        if not _valid_identifier(cell_id) or cell_id in cell_ids:
            errors.append(f"{prefix}_cell_id_invalid")
        elif isinstance(cell_id, str):
            cell_ids.add(cell_id)
            cell_by_id[cell_id] = cell
        if row_id not in row_ids or column_id not in column_ids:
            errors.append(f"{prefix}_cell_axis_ref_invalid")
        position = (str(row_id), str(column_id))
        if position in positions:
            errors.append(f"{prefix}_cell_position_duplicate")
        positions.add(position)
        bbox = _normalized_bbox(cell.get("bbox"))
        if bbox is None or (scope_bbox is not None and not _contains(scope_bbox, bbox)):
            errors.append(f"{prefix}_cell_bbox_invalid")
        text = cell.get("text")
        explicit = cell.get("explicit_empty")
        if not isinstance(text, str) or not isinstance(explicit, bool):
            errors.append(f"{prefix}_cell_value_invalid")
        elif explicit is not (text == ""):
            errors.append(f"{prefix}_explicit_empty_mismatch")
        if not _valid_code_list(cell.get("uncertainty_codes")):
            errors.append(f"{prefix}_cell_uncertainty_invalid")
    expected_positions = {(row, column) for row in row_ids for column in column_ids}
    if positions != expected_positions:
        errors.append(f"{prefix}_rectangular_cell_coverage_invalid")

    raw_merges = value.get("merged_regions")
    merges = raw_merges if isinstance(raw_merges, list) else []
    if not isinstance(raw_merges, list):
        errors.append(f"{prefix}_merged_regions_not_array")
    merge_ids: set[str] = set()
    merged_cells: set[str] = set()
    row_ordinal_by_id = {
        str(item.get("row_id")): int(item.get("ordinal"))
        for item in rows
        if isinstance(item, dict) and _positive_int(item.get("ordinal"))
    }
    column_ordinal_by_id = {
        str(item.get("column_id")): int(item.get("ordinal"))
        for item in columns
        if isinstance(item, dict) and _positive_int(item.get("ordinal"))
    }
    for merge in merges:
        if not isinstance(merge, dict) or set(merge) != {
            "merged_region_id",
            "cell_ids",
            "bbox",
            "uncertainty_codes",
        }:
            errors.append(f"{prefix}_merged_region_keys_invalid")
            continue
        merge_id = merge.get("merged_region_id")
        refs = merge.get("cell_ids")
        if not _valid_identifier(merge_id) or merge_id in merge_ids:
            errors.append(f"{prefix}_merged_region_id_invalid")
        elif isinstance(merge_id, str):
            merge_ids.add(merge_id)
        if (
            not isinstance(refs, list)
            or len(refs) < 2
            or not _unique_strings(refs)
            or not set(refs).issubset(cell_ids)
            or set(refs) & merged_cells
        ):
            errors.append(f"{prefix}_merged_region_refs_invalid")
            continue
        merged_cells.update(refs)
        merge_bbox = _normalized_bbox(merge.get("bbox"))
        if merge_bbox is None or (scope_bbox is not None and not _contains(scope_bbox, merge_bbox)):
            errors.append(f"{prefix}_merged_region_bbox_invalid")
        elif any(
            not _contains(merge_bbox, _normalized_bbox(cell_by_id[ref].get("bbox")))
            for ref in refs
        ):
            errors.append(f"{prefix}_merged_region_bbox_scope_invalid")
        coordinates = {
            (
                row_ordinal_by_id.get(str(cell_by_id[ref].get("row_id"))),
                column_ordinal_by_id.get(str(cell_by_id[ref].get("column_id"))),
            )
            for ref in refs
        }
        row_values = {item[0] for item in coordinates if item[0] is not None}
        column_values = {item[1] for item in coordinates if item[1] is not None}
        if coordinates != {(row, column) for row in row_values for column in column_values}:
            errors.append(f"{prefix}_merged_region_not_rectangular")
        if not _valid_code_list(merge.get("uncertainty_codes")):
            errors.append(f"{prefix}_merged_region_uncertainty_invalid")
    return sorted(set(errors)), {
        "row_ids": row_ids,
        "column_ids": column_ids,
        "cell_ids": cell_ids,
    }


def _validate_semantic(
    value: Any,
    *,
    column_ids: set[str],
    cell_ids: set[str],
    prefix: str,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{prefix}_semantic_not_object"]
    if set(value) != {"fields", "qualifiers"}:
        errors.append(f"{prefix}_semantic_keys_invalid")
    raw_fields = value.get("fields")
    raw_qualifiers = value.get("qualifiers")
    fields = raw_fields if isinstance(raw_fields, list) else []
    qualifiers = raw_qualifiers if isinstance(raw_qualifiers, list) else []
    if not isinstance(raw_fields, list):
        errors.append(f"{prefix}_semantic_fields_not_array")
    if not isinstance(raw_qualifiers, list):
        errors.append(f"{prefix}_semantic_qualifiers_not_array")

    field_ids: set[str] = set()
    field_by_id: dict[str, dict[str, Any]] = {}
    for field in fields:
        if not isinstance(field, dict) or set(field) != {
            "field_id",
            "role",
            "logical_type",
            "physical_column_ids",
            "header_cell_ids",
            "qualifier_ids",
            "uncertainty_codes",
        }:
            errors.append(f"{prefix}_semantic_field_keys_invalid")
            continue
        field_id = field.get("field_id")
        if not _valid_identifier(field_id) or field_id in field_ids:
            errors.append(f"{prefix}_semantic_field_id_invalid")
        elif isinstance(field_id, str):
            field_ids.add(field_id)
            field_by_id[field_id] = field
        if field.get("role") not in SEMANTIC_ROLES:
            errors.append(f"{prefix}_semantic_role_invalid")
        if field.get("logical_type") not in LOGICAL_TYPES:
            errors.append(f"{prefix}_semantic_logical_type_invalid")
        if not _valid_refs(field.get("physical_column_ids"), column_ids, nonempty=True):
            errors.append(f"{prefix}_semantic_column_refs_invalid")
        if not _valid_refs(field.get("header_cell_ids"), cell_ids):
            errors.append(f"{prefix}_semantic_header_refs_invalid")
        if not _unique_strings(field.get("qualifier_ids")):
            errors.append(f"{prefix}_semantic_qualifier_backrefs_invalid")
        if not _valid_code_list(field.get("uncertainty_codes")):
            errors.append(f"{prefix}_semantic_field_uncertainty_invalid")

    qualifier_ids: set[str] = set()
    qualifier_targets: dict[str, str] = {}
    for qualifier in qualifiers:
        if not isinstance(qualifier, dict) or set(qualifier) != {
            "qualifier_id",
            "kind",
            "target_field_id",
            "physical_column_ids",
            "evidence_cell_ids",
            "normalized_code",
            "uncertainty_codes",
        }:
            errors.append(f"{prefix}_semantic_qualifier_keys_invalid")
            continue
        qualifier_id = qualifier.get("qualifier_id")
        target = qualifier.get("target_field_id")
        if not _valid_identifier(qualifier_id) or qualifier_id in qualifier_ids:
            errors.append(f"{prefix}_semantic_qualifier_id_invalid")
        elif isinstance(qualifier_id, str):
            qualifier_ids.add(qualifier_id)
            qualifier_targets[qualifier_id] = str(target)
        if qualifier.get("kind") not in QUALIFIER_KINDS:
            errors.append(f"{prefix}_semantic_qualifier_kind_invalid")
        if target not in field_ids:
            errors.append(f"{prefix}_semantic_qualifier_target_invalid")
        if not _valid_refs(qualifier.get("physical_column_ids"), column_ids, nonempty=True):
            errors.append(f"{prefix}_semantic_qualifier_columns_invalid")
        if not _valid_refs(qualifier.get("evidence_cell_ids"), cell_ids):
            errors.append(f"{prefix}_semantic_qualifier_evidence_invalid")
        normalized_code = qualifier.get("normalized_code")
        if normalized_code is not None and (
            not isinstance(normalized_code, str) or not normalized_code.strip()
        ):
            errors.append(f"{prefix}_semantic_normalized_code_invalid")
        if not _valid_code_list(qualifier.get("uncertainty_codes")):
            errors.append(f"{prefix}_semantic_qualifier_uncertainty_invalid")

    declared_backref_pairs = [
        (str(ref), str(field_id))
        for field_id, field in field_by_id.items()
        for ref in field.get("qualifier_ids") or []
    ]
    declared_backrefs = dict(declared_backref_pairs)
    if (
        len(declared_backref_pairs) != len(declared_backrefs)
        or
        set(declared_backrefs) != qualifier_ids
        or any(
            declared_backrefs.get(qualifier_id) != target
            for qualifier_id, target in qualifier_targets.items()
        )
    ):
        errors.append(f"{prefix}_semantic_qualifier_backrefs_invalid")
    return sorted(set(errors))


def _axis_ids(
    values: list[Any],
    *,
    id_key: str,
    count: int,
    scope_bbox: list[float] | None,
) -> tuple[set[str] | None, set[int]]:
    ids: set[str] = set()
    ordinals: set[int] = set()
    expected_keys = {id_key, "ordinal", "bbox"}
    for value in values:
        if not isinstance(value, dict) or set(value) != expected_keys:
            return None, ordinals
        identifier = value.get(id_key)
        ordinal = value.get("ordinal")
        bbox = _normalized_bbox(value.get("bbox"))
        if (
            not _valid_identifier(identifier)
            or identifier in ids
            or not _positive_int(ordinal)
            or int(ordinal) > count
            or ordinal in ordinals
            or bbox is None
            or (scope_bbox is not None and not _contains(scope_bbox, bbox))
        ):
            return None, ordinals
        ids.add(str(identifier))
        ordinals.add(int(ordinal))
    return ids, ordinals


def _project_physical_bboxes(
    physical: dict[str, Any], page_bbox: list[float]
) -> None:
    for key in ("rows", "columns", "cells", "merged_regions"):
        for item in physical.get(key) or []:
            item["bbox"] = _project_bbox(item["bbox"], page_bbox)


def _project_bbox(value: Any, page_bbox: list[float]) -> list[float]:
    bbox = _normalized_bbox(value)
    if bbox is None:
        raise ValueError("benchmark_crop_bbox_invalid")
    x0, y0, x1, y1 = bbox
    px0, py0, px1, py1 = page_bbox
    width = px1 - px0
    height = py1 - py0
    return [
        round(px0 + x0 * width, 9),
        round(py0 + y0 * height, 9),
        round(px0 + x1 * width, 9),
        round(py0 + y1 * height, 9),
    ]


def _usable_words(word_inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for word in word_inventory:
        if not isinstance(word, dict):
            continue
        ordinal = word.get("parser_ordinal")
        text = word.get("text")
        bbox = _positive_bbox(word.get("bbox"))
        if not _positive_int(ordinal) or not isinstance(text, str) or not text or bbox is None:
            continue
        result.append(
            {
                "parser_ordinal": int(ordinal),
                "geometry_reading_order": word.get("geometry_reading_order"),
                "text": text,
                "bbox": bbox,
            }
        )
    return result


def _cell_evidence(
    *,
    table_id: str,
    alternative_id: str | None,
    cell: dict[str, Any],
    words: list[dict[str, Any]],
    page_width: float,
    page_height: float,
) -> dict[str, Any]:
    normalized = _normalized_bbox(cell.get("bbox"))
    if normalized is None:
        raise ValueError("benchmark_evidence_cell_bbox_invalid")
    cell_bbox = [
        normalized[0] * page_width,
        normalized[1] * page_height,
        normalized[2] * page_width,
        normalized[3] * page_height,
    ]
    scoped = [word for word in words if _center_inside(word["bbox"], cell_bbox)]
    scoped.sort(key=_word_order_key)
    reasons: list[str] = []
    matches: list[dict[str, Any]] = []
    if not words:
        status = "unsupported"
        reasons.append("parser_text_layer_unavailable")
    elif (
        len(words) > MAX_EVIDENCE_WORDS_PER_PAGE
        or len(scoped) > MAX_EVIDENCE_WORDS_PER_CELL
    ):
        status = "unsupported"
        reasons.append(
            "parser_page_word_budget_exceeded"
            if len(words) > MAX_EVIDENCE_WORDS_PER_PAGE
            else "parser_cell_word_budget_exceeded"
        )
    else:
        target = _evidence_text_key(cell["text"])
        matches = _exact_word_matches(scoped, target)
        if len(matches) == 1:
            status = "traced"
        elif len(matches) > 1:
            status = "ambiguous"
            reasons.append("multiple_exact_source_spans")
        else:
            ordered_page_words = sorted(words, key=_word_order_key)
            page_matches = _exact_word_matches(ordered_page_words, target)
            if len(page_matches) == 1:
                status = "not_found"
                matches = page_matches
                reasons.append("source_span_outside_cell_bbox")
            elif len(page_matches) > 1:
                status = "ambiguous"
                matches = page_matches
                reasons.extend(
                    [
                        "multiple_exact_source_spans",
                        "source_span_outside_cell_bbox",
                    ]
                )
            else:
                status = "not_found"
                reasons.append("exact_source_span_not_found")
    return {
        "table_id": table_id,
        "alternative_id": alternative_id,
        "cell_id": cell["cell_id"],
        "status": status,
        "disposition": _EVIDENCE_DISPOSITION_BY_STATUS[status],
        "matches": matches,
        "reason_codes": reasons,
    }


def _exact_word_matches(
    words: list[dict[str, Any]], target: str
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[tuple[int, ...]] = set()
    for start in range(len(words)):
        for end in range(start + 1, len(words) + 1):
            selected = words[start:end]
            spaced = " ".join(item["text"] for item in selected)
            compact = "".join(item["text"] for item in selected)
            compact_key = _evidence_text_key(compact)
            if target in {_evidence_text_key(spaced), compact_key}:
                ordinals = tuple(item["parser_ordinal"] for item in selected)
                if ordinals not in seen:
                    seen.add(ordinals)
                    matches.append(
                        {
                            "parser_ordinals": list(ordinals),
                            "bboxes": [
                                copy.deepcopy(item["bbox"]) for item in selected
                            ],
                            "matched_text": spaced,
                        }
                    )
            # Every usable word has non-empty normalized text, so a candidate
            # longer than the target cannot become equal after appending words.
            if len(compact_key) > len(target):
                break
    return matches


def _word_order_key(value: dict[str, Any]) -> tuple[Any, ...]:
    order = value.get("geometry_reading_order")
    bbox = value["bbox"]
    return (
        0 if _positive_int(order) else 1,
        int(order) if _positive_int(order) else round(float(bbox[1]), 6),
        round(float(bbox[0]), 6),
        int(value["parser_ordinal"]),
    )


def _evidence_text_key(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    return "".join(normalized.split())


def _valid_refs(value: Any, allowed: set[str], *, nonempty: bool = False) -> bool:
    return (
        _unique_strings(value)
        and (not nonempty or bool(value))
        and set(value).issubset(allowed)
    )


def _valid_code_list(value: Any) -> bool:
    return _unique_strings(value) and all(
        bool(item.strip()) and len(item) <= 128 for item in value
    )


def _unique_strings(value: Any) -> bool:
    return (
        isinstance(value, list)
        and all(isinstance(item, str) for item in value)
        and len(value) == len(set(value))
    )


def _valid_identifier(value: Any) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _normalized_bbox(value: Any) -> list[float] | None:
    bbox = _positive_bbox(value)
    if bbox is None or any(item < 0.0 or item > 1.0 for item in bbox):
        return None
    return bbox


def _positive_bbox(value: Any) -> list[float] | None:
    if (
        not isinstance(value, list)
        or len(value) != 4
        or not all(_number(item) for item in value)
    ):
        return None
    bbox = [float(item) for item in value]
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return None
    return bbox


def _contains(outer: list[float] | None, inner: list[float] | None) -> bool:
    return bool(
        outer is not None
        and inner is not None
        and outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[2] >= inner[2]
        and outer[3] >= inner[3]
    )


def _center_inside(value: list[float], scope: list[float]) -> bool:
    x = (value[0] + value[2]) / 2.0
    y = (value[1] + value[3]) / 2.0
    return scope[0] <= x <= scope[2] and scope[1] <= y <= scope[3]


def _number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
