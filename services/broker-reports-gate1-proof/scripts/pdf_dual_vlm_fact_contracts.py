#!/usr/bin/env python3
"""Closed contracts for the research-only dual-VLM financial-fact benchmark."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from typing import Any, Iterable


MANIFEST_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_fact_manifest_v1"
DETECTION_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_detection_v1"
FACT_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_financial_facts_v1"
CONSENSUS_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_consensus_v1"
CROP_CONTRACT_VERSION = "broker_reports_pdf_dual_vlm_crop_v1"
DETECTION_PROMPT_VERSION = "dual_vlm_detection_v1"
FACT_PROMPT_VERSION = "dual_vlm_fact_extraction_v1"

CONSENSUS_STATUSES = {
    "models_exactly_agree",
    "models_semantically_agree_physical_layout_differs",
    "models_partially_agree",
    "model_conflict",
    "one_model_missing_fact",
    "both_models_unknown",
    "human_review_required",
}
AGREEMENT_STATUSES = {
    "models_exactly_agree",
    "models_semantically_agree_physical_layout_differs",
}
FACT_TYPES = {
    "financial_statement_line_item",
    "subtotal",
    "total",
    "ratio",
    "per_share_amount",
    "count",
    "other_financial_fact",
    "unknown",
}
SIGN_VALUES = {"positive", "negative", "zero", "unknown", "not_applicable"}
UNCERTAINTY_VALUES = {"certain", "uncertain", "unknown"}
CELL_ROLES = {
    "row_label",
    "header",
    "value",
    "period",
    "currency",
    "unit_scale",
    "entity",
    "qualifier",
    "other",
}
DETECTION_REASON_CODES = {
    "borderless",
    "compound_page",
    "possible_table",
    "raster_region",
    "low_visual_separation",
    "partial_visibility",
    "multiple_adjacent_tables",
    "non_table_grid_like_content",
}
FACT_UNCERTAINTY_CODES = {
    "ambiguous_row_binding",
    "ambiguous_header_binding",
    "ambiguous_period",
    "ambiguous_currency",
    "ambiguous_unit_scale",
    "ambiguous_entity",
    "illegible_value",
    "physical_layout_uncertain",
    "missing_visible_context",
    "not_a_financial_fact",
}

DETECTION_PROMPT = (
    "Inspect only the supplied PDF page image. Return the strict versioned table "
    "detection object and nothing else. Your sole task is table-region detection: "
    "do not extract cells, values, financial facts, row labels, or business meaning. "
    "Use normalized top-left image coordinates [x0,y0,x1,y1]. A table bbox must "
    "contain one complete table and every visually governing title, date/period, "
    "currency, unit, scale, entity label, header, total, row, and column. Do not "
    "include neighbouring prose unless it governs the table. Never merge adjacent "
    "tables or split one table. Keep false positives visible; use uncertain when "
    "the boundary cannot be established. No free-form narrative."
)

FACT_PROMPT = (
    "Analyze only the supplied immutable table crop. Return the strict versioned "
    "financial-fact object and nothing else. The primary object is a financial fact, "
    "not a perfect reconstructed grid. Preserve exact visible row labels, header "
    "paths, values, punctuation, signs, parentheses, separators, currency symbols, "
    "and qualifiers. Do not infer a period, ISO currency, unit, scale, entity, or "
    "normalized row identity unless visibly justified inside this crop; use null or "
    "unknown instead. Provide only the minimally sufficient physical cells used by "
    "facts, with crop-normalized [x0,y0,x1,y1] bboxes. Separate observed content, "
    "interpreted meaning, and exact evidence requests; explicitly declare whether "
    "each qualifier applies to the value, row label, header, or whole table. Do not use page context, "
    "parser topology, human reference, another model result, retries, or repairs."
)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def detection_schema() -> dict[str, Any]:
    candidate = _closed_object(
        {
            "candidate_id": _identifier_schema(),
            "bbox": _bbox_schema(),
            "state": {"type": "string", "enum": ["present", "uncertain"]},
            "reason_codes": _enum_array_schema(sorted(DETECTION_REASON_CODES)),
        }
    )
    return _closed_object(
        {
            "schema_version": {"type": "string", "enum": [DETECTION_SCHEMA_VERSION]},
            "document_id": _identifier_schema(),
            "page_number": {"type": "integer", "minimum": 1},
            "page_status": {
                "type": "string",
                "enum": ["present", "absent", "uncertain"],
            },
            "candidates": {"type": "array", "items": candidate, "maxItems": 12},
            "uncertainty_codes": _string_array_schema(max_items=16),
        }
    )


def financial_fact_schema() -> dict[str, Any]:
    physical_cell = _closed_object(
        {
            "cell_id": _identifier_schema(),
            "text_exact": {"type": "string", "maxLength": 1000},
            "bbox": _bbox_schema(),
            "role": {"type": "string", "enum": sorted(CELL_ROLES)},
            "row_hint": _nullable_string_schema(),
            "column_hint": _nullable_string_schema(),
        }
    )
    source_regions = _closed_object(
        {
            "row_label_bbox": _nullable_bbox_schema(),
            "value_bbox": _bbox_schema(),
            "header_bboxes": {
                "type": "array",
                "items": _bbox_schema(),
                "maxItems": 12,
            },
            "qualifier_bboxes": _closed_object(
                {
                    "period": _nullable_bbox_schema(),
                    "currency": _nullable_bbox_schema(),
                    "unit": _nullable_bbox_schema(),
                    "scale": _nullable_bbox_schema(),
                    "entity": _nullable_bbox_schema(),
                }
            ),
        }
    )
    observed = _closed_object(
        {
            "row_label_exact": _nullable_string_schema(max_length=1000),
            "header_path_exact": _string_array_schema(max_items=12, max_length=500),
            "value_exact": {"type": "string", "minLength": 1, "maxLength": 500},
            "source_cell_ids": {
                "type": "array",
                "items": _identifier_schema(),
                "minItems": 1,
                "maxItems": 32,
            },
            "source_regions": source_regions,
        }
    )
    interpreted_fields = {
        "normalized_row_identity": _nullable_string_schema(max_length=1000),
        "numeric_value": _nullable_string_schema(max_length=500),
        "sign": {"type": "string", "enum": sorted(SIGN_VALUES)},
        "period": _nullable_string_schema(max_length=500),
        "currency_literal": _nullable_string_schema(max_length=100),
        "currency_code": _nullable_string_schema(max_length=20),
        "unit": _nullable_string_schema(max_length=200),
        "scale": _nullable_string_schema(max_length=200),
        "entity": _nullable_string_schema(max_length=500),
        "qualifiers": _string_array_schema(max_items=32, max_length=500),
    }
    interpreted = _closed_object(interpreted_fields)
    requested_text = _closed_object(
        {
            "row_label_exact": _nullable_string_schema(max_length=1000),
            "header_path_exact": _string_array_schema(max_items=12, max_length=500),
            "value_exact": {"type": "string", "minLength": 1, "maxLength": 500},
            "period_exact": _nullable_string_schema(max_length=500),
            "currency_exact": _nullable_string_schema(max_length=100),
            "unit_exact": _nullable_string_schema(max_length=200),
            "scale_exact": _nullable_string_schema(max_length=200),
            "entity_exact": _nullable_string_schema(max_length=500),
        }
    )
    evidence_request = _closed_object(
        {
            "requested_text": requested_text,
            "qualifier_scopes": _closed_object(
                {
                    "period": {
                        "type": "string",
                        "enum": ["value", "row_label", "header", "table"],
                    },
                    "currency": {
                        "type": "string",
                        "enum": ["value", "row_label", "header", "table"],
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["value", "row_label", "header", "table"],
                    },
                    "scale": {
                        "type": "string",
                        "enum": ["value", "row_label", "header", "table"],
                    },
                    "entity": {
                        "type": "string",
                        "enum": ["value", "row_label", "header", "table"],
                    },
                }
            ),
            "required_relations": _enum_array_schema(
                [
                    "row_value_spatial",
                    "header_value_spatial",
                    "period_scope",
                    "currency_scope",
                    "unit_scale_scope",
                    "entity_scope",
                ],
                max_items=6,
            ),
        }
    )
    alternative = _closed_object(
        {
            "description": {"type": "string", "minLength": 1, "maxLength": 1000},
            **interpreted_fields,
        }
    )
    uncertainty = _closed_object(
        {
            "status": {"type": "string", "enum": sorted(UNCERTAINTY_VALUES)},
            "reason_codes": _enum_array_schema(sorted(FACT_UNCERTAINTY_CODES)),
            "alternative_interpretations": {
                "type": "array",
                "items": alternative,
                "maxItems": 4,
            },
        }
    )
    fact = _closed_object(
        {
            "fact_id": _identifier_schema(),
            "fact_type": {"type": "string", "enum": sorted(FACT_TYPES)},
            "observed": observed,
            "interpreted": interpreted,
            "evidence_request": evidence_request,
            "uncertainty": uncertainty,
        }
    )
    context = _closed_object(
        {
            "table_title_exact": _nullable_string_schema(max_length=1000),
            "period_context_exact": _nullable_string_schema(max_length=500),
            "currency_context_exact": _nullable_string_schema(max_length=200),
            "unit_scale_context_exact": _nullable_string_schema(max_length=300),
            "entity_context_exact": _nullable_string_schema(max_length=500),
            "uncertainty_codes": _string_array_schema(max_items=16),
        }
    )
    return _closed_object(
        {
            "schema_version": {"type": "string", "enum": [FACT_SCHEMA_VERSION]},
            "document_id": _identifier_schema(),
            "page_number": {"type": "integer", "minimum": 1},
            "crop_id": _identifier_schema(),
            "crop_sha256": _sha256_schema(),
            "status": {
                "type": "string",
                "enum": ["completed", "no_financial_facts", "uncertain", "unsupported"],
            },
            "table_context": context,
            "physical_cells": {
                "type": "array",
                "items": physical_cell,
                "maxItems": 512,
            },
            "facts": {"type": "array", "items": fact, "maxItems": 512},
            "uncertainty_codes": _string_array_schema(max_items=32),
        }
    )


def detection_model_view(
    *, document_id: str, page_number: int, page_image_sha256: str
) -> dict[str, Any]:
    return {
        "prompt_contract_version": DETECTION_PROMPT_VERSION,
        "prompt": DETECTION_PROMPT,
        "identity": {
            "schema_version": DETECTION_SCHEMA_VERSION,
            "document_id": document_id,
            "page_number": page_number,
            "page_image_sha256": page_image_sha256,
        },
        "rules": {
            "bbox_order": ["x0", "y0", "x1", "y1"],
            "coordinate_space": "page_image_normalized_top_left",
            "extract_cells_or_facts": False,
            "free_form_narrative": False,
            "complete_governing_context_required": True,
        },
    }


def fact_model_view(
    *,
    document_id: str,
    page_number: int,
    crop_id: str,
    crop_sha256: str,
) -> dict[str, Any]:
    return {
        "prompt_contract_version": FACT_PROMPT_VERSION,
        "prompt": FACT_PROMPT,
        "identity": {
            "schema_version": FACT_SCHEMA_VERSION,
            "document_id": document_id,
            "page_number": page_number,
            "crop_id": crop_id,
            "crop_sha256": crop_sha256,
        },
        "rules": {
            "bbox_order": ["x0", "y0", "x1", "y1"],
            "coordinate_space": "crop_image_normalized_top_left",
            "full_grid_required": False,
            "observed_interpreted_evidence_separated": True,
            "unknown_preferred_to_inference": True,
            "reference_or_other_provider_available": False,
        },
    }


def validate_detection_output(
    value: Any,
    *,
    expected_document_id: str | None = None,
    expected_page_number: int | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["dual_vlm_detection_not_object"]
    if set(value) != {
        "schema_version",
        "document_id",
        "page_number",
        "page_status",
        "candidates",
        "uncertainty_codes",
    }:
        errors.append("dual_vlm_detection_keys_invalid")
    if value.get("schema_version") != DETECTION_SCHEMA_VERSION:
        errors.append("dual_vlm_detection_schema_invalid")
    if (
        expected_document_id is not None
        and value.get("document_id") != expected_document_id
    ):
        errors.append("dual_vlm_detection_document_identity_mismatch")
    if (
        expected_page_number is not None
        and value.get("page_number") != expected_page_number
    ):
        errors.append("dual_vlm_detection_page_identity_mismatch")
    status = value.get("page_status")
    if status not in {"present", "absent", "uncertain"}:
        errors.append("dual_vlm_detection_status_invalid")
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 12:
        return errors + ["dual_vlm_detection_candidates_invalid"]
    ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        prefix = f"dual_vlm_detection_candidate_{index}"
        if not isinstance(candidate, dict) or set(candidate) != {
            "candidate_id",
            "bbox",
            "state",
            "reason_codes",
        }:
            errors.append(prefix + "_keys_invalid")
            continue
        candidate_id = candidate.get("candidate_id")
        if not _identifier(candidate_id) or candidate_id in ids:
            errors.append(prefix + "_id_invalid")
        else:
            ids.add(candidate_id)
        if not valid_bbox(candidate.get("bbox")):
            errors.append(prefix + "_bbox_invalid")
        if candidate.get("state") not in {"present", "uncertain"}:
            errors.append(prefix + "_state_invalid")
        if not _bounded_codes(
            candidate.get("reason_codes"), DETECTION_REASON_CODES, 16
        ):
            errors.append(prefix + "_reason_codes_invalid")
    if status == "absent" and candidates:
        errors.append("dual_vlm_detection_absent_has_candidates")
    if status == "present" and not any(
        isinstance(item, dict) and item.get("state") == "present" for item in candidates
    ):
        errors.append("dual_vlm_detection_present_without_present_candidate")
    if not _string_list(value.get("uncertainty_codes"), max_items=16):
        errors.append("dual_vlm_detection_uncertainty_invalid")
    return sorted(set(errors))


def validate_fact_extraction_output(
    value: Any,
    *,
    expected_identity: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["dual_vlm_fact_output_not_object"]
    expected_keys = {
        "schema_version",
        "document_id",
        "page_number",
        "crop_id",
        "crop_sha256",
        "status",
        "table_context",
        "physical_cells",
        "facts",
        "uncertainty_codes",
    }
    if set(value) != expected_keys:
        errors.append("dual_vlm_fact_output_keys_invalid")
    if value.get("schema_version") != FACT_SCHEMA_VERSION:
        errors.append("dual_vlm_fact_schema_invalid")
    if expected_identity:
        for key in ("document_id", "page_number", "crop_id", "crop_sha256"):
            if value.get(key) != expected_identity.get(key):
                errors.append(f"dual_vlm_fact_{key}_mismatch")
    if value.get("status") not in {
        "completed",
        "no_financial_facts",
        "uncertain",
        "unsupported",
    }:
        errors.append("dual_vlm_fact_status_invalid")
    if not _valid_context(value.get("table_context")):
        errors.append("dual_vlm_fact_context_invalid")
    cells = value.get("physical_cells")
    if not isinstance(cells, list) or len(cells) > 512:
        return sorted(set(errors + ["dual_vlm_fact_cells_invalid"]))
    cell_ids: set[str] = set()
    for index, cell in enumerate(cells):
        if not _valid_physical_cell(cell):
            errors.append(f"dual_vlm_fact_cell_{index}_invalid")
            continue
        cell_id = str(cell["cell_id"])
        if cell_id in cell_ids:
            errors.append("dual_vlm_fact_cell_id_duplicate")
        cell_ids.add(cell_id)
    facts = value.get("facts")
    if not isinstance(facts, list) or len(facts) > 512:
        return sorted(set(errors + ["dual_vlm_facts_invalid"]))
    fact_ids: set[str] = set()
    for index, fact in enumerate(facts):
        fact_errors = _validate_fact(fact, cell_ids)
        errors.extend(f"dual_vlm_fact_{index}:{item}" for item in fact_errors)
        if isinstance(fact, dict) and _identifier(fact.get("fact_id")):
            fact_id = str(fact["fact_id"])
            if fact_id in fact_ids:
                errors.append("dual_vlm_fact_id_duplicate")
            fact_ids.add(fact_id)
    if value.get("status") == "no_financial_facts" and facts:
        errors.append("dual_vlm_no_facts_status_has_facts")
    if value.get("status") == "completed" and not facts:
        errors.append("dual_vlm_completed_status_without_facts")
    if not _string_list(value.get("uncertainty_codes"), max_items=32):
        errors.append("dual_vlm_fact_uncertainty_codes_invalid")
    return sorted(set(errors))


def build_crop_contract(
    *,
    document_id: str,
    page_image_sha256: str,
    normalized_bbox: list[float],
    raster_manifest: dict[str, Any],
) -> dict[str, Any]:
    required = {
        "crop_id",
        "pdf_sha256",
        "page_number",
        "declared_table_bbox",
        "rendered_bbox",
        "dpi",
        "width",
        "height",
        "png_bytes",
        "png_sha256",
        "renderer",
        "renderer_version",
        "padding_points",
        "lossless",
        "silent_resize_performed",
        "manifest_hash",
    }
    if not required.issubset(raster_manifest):
        raise ValueError("dual_vlm_crop_raster_manifest_incomplete")
    if not valid_bbox(normalized_bbox):
        raise ValueError("dual_vlm_crop_normalized_bbox_invalid")
    contract = {
        "schema_version": CROP_CONTRACT_VERSION,
        "document_id": document_id,
        "pdf_sha256": raster_manifest["pdf_sha256"],
        "page_number": raster_manifest["page_number"],
        "page_image_sha256": page_image_sha256,
        "crop_id": raster_manifest["crop_id"],
        "source_bbox_points": copy.deepcopy(raster_manifest["declared_table_bbox"]),
        "rendered_bbox_points": copy.deepcopy(raster_manifest["rendered_bbox"]),
        "normalized_bbox": [round(float(item), 9) for item in normalized_bbox],
        "source_to_pixel_transform": copy.deepcopy(
            raster_manifest["source_to_pixel_transform"]
        ),
        "render_dpi": raster_manifest["dpi"],
        "dimensions": {
            "width": raster_manifest["width"],
            "height": raster_manifest["height"],
        },
        "rendered_image_bytes": raster_manifest["png_bytes"],
        "rendered_image_sha256": raster_manifest["png_sha256"],
        "renderer": raster_manifest["renderer"],
        "renderer_version": raster_manifest["renderer_version"],
        "padding_points": raster_manifest["padding_points"],
        "lossless": raster_manifest["lossless"],
        "silent_resize_performed": raster_manifest["silent_resize_performed"],
        "raster_manifest_hash": raster_manifest["manifest_hash"],
    }
    contract["contract_checksum"] = sha256_json(contract)
    return contract


def validate_crop_contract(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["dual_vlm_crop_contract_not_object"]
    expected = {
        "schema_version",
        "document_id",
        "pdf_sha256",
        "page_number",
        "page_image_sha256",
        "crop_id",
        "source_bbox_points",
        "rendered_bbox_points",
        "normalized_bbox",
        "source_to_pixel_transform",
        "render_dpi",
        "dimensions",
        "rendered_image_bytes",
        "rendered_image_sha256",
        "renderer",
        "renderer_version",
        "padding_points",
        "lossless",
        "silent_resize_performed",
        "raster_manifest_hash",
        "contract_checksum",
    }
    errors: list[str] = []
    if set(value) != expected:
        errors.append("dual_vlm_crop_contract_keys_invalid")
    if value.get("schema_version") != CROP_CONTRACT_VERSION:
        errors.append("dual_vlm_crop_contract_schema_invalid")
    for key in (
        "pdf_sha256",
        "page_image_sha256",
        "rendered_image_sha256",
        "raster_manifest_hash",
    ):
        if not _sha256(value.get(key)):
            errors.append(f"dual_vlm_crop_{key}_invalid")
    if not _identifier(value.get("document_id")) or not _identifier(
        value.get("crop_id")
    ):
        errors.append("dual_vlm_crop_identity_invalid")
    if not valid_bbox(value.get("normalized_bbox")):
        errors.append("dual_vlm_crop_normalized_bbox_invalid")
    if not _source_bbox(value.get("source_bbox_points")) or not _source_bbox(
        value.get("rendered_bbox_points")
    ):
        errors.append("dual_vlm_crop_source_bbox_invalid")
    if value.get("padding_points") != 0:
        errors.append("dual_vlm_crop_padding_invalid")
    if (
        value.get("lossless") is not True
        or value.get("silent_resize_performed") is not False
    ):
        errors.append("dual_vlm_crop_immutability_invalid")
    unsigned = copy.deepcopy(value)
    checksum = unsigned.pop("contract_checksum", None)
    if checksum != sha256_json(unsigned):
        errors.append("dual_vlm_crop_contract_checksum_invalid")
    return sorted(set(errors))


def compare_provider_facts(
    gemini_output: dict[str, Any], openai_output: dict[str, Any]
) -> dict[str, Any]:
    gemini_errors = validate_fact_extraction_output(gemini_output)
    openai_errors = validate_fact_extraction_output(openai_output)
    if gemini_errors or openai_errors:
        raise ValueError("dual_vlm_consensus_provider_contract_invalid")
    identity = {
        key: gemini_output[key]
        for key in ("document_id", "page_number", "crop_id", "crop_sha256")
    }
    if any(openai_output.get(key) != item for key, item in identity.items()):
        raise ValueError("dual_vlm_consensus_crop_identity_mismatch")
    gemini_facts = [copy.deepcopy(item) for item in gemini_output["facts"]]
    openai_facts = [copy.deepcopy(item) for item in openai_output["facts"]]
    outputs_completed = (
        gemini_output.get("status") == "completed"
        and openai_output.get("status") == "completed"
    )
    pairs = _pair_facts(gemini_facts, openai_facts)
    entries: list[dict[str, Any]] = []
    for ordinal, pair in enumerate(pairs, start=1):
        left = pair.get("gemini")
        right = pair.get("openai")
        if left is None or right is None:
            fact = left or right
            entries.append(
                _consensus_entry(
                    ordinal,
                    left,
                    right,
                    "one_model_missing_fact",
                    fact=None,
                    differences=["provider_fact_missing"],
                    source_compatible=False,
                    physical_same=False,
                )
            )
            continue
        left_canonical = canonicalize_fact(left)
        right_canonical = canonicalize_fact(right)
        material_differences = [
            key
            for key in _MATERIAL_KEYS
            if left_canonical.get(key) != right_canonical.get(key)
        ]
        source_compatible = _source_regions_compatible(left, right)
        facts_certain = _fact_is_certain(left) and _fact_is_certain(right)
        evidence_prerequisites = _fact_evidence_prerequisites(left) and (
            _fact_evidence_prerequisites(right)
        )
        physical_same = _physical_signature(left, gemini_output) == _physical_signature(
            right, openai_output
        )
        if not outputs_completed or not facts_certain or not evidence_prerequisites:
            status = "human_review_required"
            fact = None
            differences = []
            if not outputs_completed:
                differences.append("provider_output_not_completed")
            if not facts_certain:
                differences.append("provider_fact_uncertain")
            if not evidence_prerequisites:
                differences.append("evidence_prerequisite_missing")
        elif not material_differences and source_compatible:
            status = (
                "models_exactly_agree"
                if physical_same
                else "models_semantically_agree_physical_layout_differs"
            )
            fact = _consensus_fact(left, right, left_canonical)
            differences: list[str] = [] if physical_same else ["physical_layout"]
        elif not material_differences:
            status = "human_review_required"
            fact = None
            differences = ["source_region_incompatible"]
        elif _partial_agreement(left_canonical, right_canonical):
            status = "models_partially_agree"
            fact = None
            differences = material_differences or ["source_region"]
        else:
            status = "model_conflict"
            fact = None
            differences = material_differences or ["source_region"]
        entries.append(
            _consensus_entry(
                ordinal,
                left,
                right,
                status,
                fact=fact,
                differences=differences,
                source_compatible=source_compatible,
                physical_same=physical_same,
            )
        )
    if not entries:
        both_definitively_empty = (
            gemini_output.get("status") == "no_financial_facts"
            and openai_output.get("status") == "no_financial_facts"
        )
        entries.append(
            _consensus_entry(
                1,
                None,
                None,
                (
                    "both_models_unknown"
                    if both_definitively_empty
                    else "human_review_required"
                ),
                fact=None,
                differences=(
                    []
                    if both_definitively_empty
                    else ["provider_output_not_definitive"]
                ),
                source_compatible=False,
                physical_same=False,
            )
        )
    result = {
        "schema_version": CONSENSUS_SCHEMA_VERSION,
        **identity,
        "gemini_output_sha256": sha256_json(gemini_output),
        "openai_output_sha256": sha256_json(openai_output),
        "entries": entries,
        "summary": {
            status: sum(1 for entry in entries if entry["status"] == status)
            for status in sorted(CONSENSUS_STATUSES)
        },
        "human_reference_used": False,
        "voting_used": False,
        "confidence_averaging_used": False,
        "third_llm_arbiter_used": False,
    }
    result["consensus_checksum"] = sha256_json(result)
    return result


def validate_consensus(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["dual_vlm_consensus_not_object"]
    errors: list[str] = []
    expected = {
        "schema_version",
        "document_id",
        "page_number",
        "crop_id",
        "crop_sha256",
        "gemini_output_sha256",
        "openai_output_sha256",
        "entries",
        "summary",
        "human_reference_used",
        "voting_used",
        "confidence_averaging_used",
        "third_llm_arbiter_used",
        "consensus_checksum",
    }
    if set(value) != expected:
        errors.append("dual_vlm_consensus_keys_invalid")
    if value.get("schema_version") != CONSENSUS_SCHEMA_VERSION:
        errors.append("dual_vlm_consensus_schema_invalid")
    if value.get("human_reference_used") is not False or any(
        value.get(key) is not False
        for key in (
            "voting_used",
            "confidence_averaging_used",
            "third_llm_arbiter_used",
        )
    ):
        errors.append("dual_vlm_consensus_authority_boundary_invalid")
    entries = value.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("dual_vlm_consensus_entries_invalid")
    else:
        for index, entry in enumerate(entries):
            if (
                not isinstance(entry, dict)
                or entry.get("status") not in CONSENSUS_STATUSES
            ):
                errors.append(f"dual_vlm_consensus_entry_{index}_invalid")
    unsigned = copy.deepcopy(value)
    checksum = unsigned.pop("consensus_checksum", None)
    if checksum != sha256_json(unsigned):
        errors.append("dual_vlm_consensus_checksum_invalid")
    return sorted(set(errors))


def canonicalize_fact(fact: dict[str, Any]) -> dict[str, Any]:
    observed = _object(fact.get("observed"))
    interpreted = _object(fact.get("interpreted"))
    normalized_row = interpreted.get("normalized_row_identity")
    row = (
        normalized_row
        if isinstance(normalized_row, str) and normalized_row
        else observed.get("row_label_exact")
    )
    return {
        "fact_type": str(fact.get("fact_type") or "unknown"),
        "row": normalize_text(row),
        "header_path": tuple(
            normalize_text(item) for item in observed.get("header_path_exact") or []
        ),
        "value_exact": normalize_whitespace(observed.get("value_exact")),
        "numeric_value": _canonical_decimal(interpreted.get("numeric_value")),
        "sign": str(interpreted.get("sign") or "unknown"),
        "period": normalize_text(interpreted.get("period")),
        "currency_literal": normalize_whitespace(interpreted.get("currency_literal")),
        "currency_code": _upper_or_none(interpreted.get("currency_code")),
        "unit": normalize_text(interpreted.get("unit")),
        "scale": normalize_text(interpreted.get("scale")),
        "entity": normalize_text(interpreted.get("entity")),
        "qualifiers": tuple(
            sorted(normalize_text(item) for item in interpreted.get("qualifiers") or [])
        ),
    }


def normalize_whitespace(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return " ".join(value.split())


def normalize_text(value: Any) -> str | None:
    collapsed = normalize_whitespace(value)
    if collapsed is None:
        return None
    return unicodedata.normalize("NFKC", collapsed).casefold()


def valid_bbox(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    if not all(
        isinstance(item, (int, float))
        and not isinstance(item, bool)
        and math.isfinite(float(item))
        and 0 <= float(item) <= 1
        for item in value
    ):
        return False
    return float(value[0]) < float(value[2]) and float(value[1]) < float(value[3])


def bbox_iou(left: list[float], right: list[float]) -> float:
    x0 = max(float(left[0]), float(right[0]))
    y0 = max(float(left[1]), float(right[1]))
    x1 = min(float(left[2]), float(right[2]))
    y1 = min(float(left[3]), float(right[3]))
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    left_area = (float(left[2]) - float(left[0])) * (float(left[3]) - float(left[1]))
    right_area = (float(right[2]) - float(right[0])) * (
        float(right[3]) - float(right[1])
    )
    union = left_area + right_area - intersection
    return intersection / union if union else 0.0


def normalized_to_source_bbox(
    normalized_bbox: list[float], page_bbox: list[float]
) -> list[float]:
    if not valid_bbox(normalized_bbox) or not _source_bbox(page_bbox):
        raise ValueError("dual_vlm_bbox_projection_invalid")
    width = float(page_bbox[2]) - float(page_bbox[0])
    height = float(page_bbox[3]) - float(page_bbox[1])
    return [
        round(float(page_bbox[0]) + normalized_bbox[0] * width, 6),
        round(float(page_bbox[1]) + normalized_bbox[1] * height, 6),
        round(float(page_bbox[0]) + normalized_bbox[2] * width, 6),
        round(float(page_bbox[1]) + normalized_bbox[3] * height, 6),
    ]


_MATERIAL_KEYS = (
    "fact_type",
    "row",
    "header_path",
    "value_exact",
    "numeric_value",
    "sign",
    "period",
    "currency_literal",
    "currency_code",
    "unit",
    "scale",
    "entity",
    "qualifiers",
)


def _pair_facts(
    gemini_facts: list[dict[str, Any]], openai_facts: list[dict[str, Any]]
) -> list[dict[str, dict[str, Any] | None]]:
    candidates: list[tuple[int, int, int]] = []
    for left_index, left in enumerate(gemini_facts):
        left_canonical = canonicalize_fact(left)
        for right_index, right in enumerate(openai_facts):
            right_canonical = canonicalize_fact(right)
            score = _pair_score(left_canonical, right_canonical)
            if score > 0:
                candidates.append((-score, left_index, right_index))
    used_left: set[int] = set()
    used_right: set[int] = set()
    pairs: list[dict[str, dict[str, Any] | None]] = []
    for _negative_score, left_index, right_index in sorted(candidates):
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        pairs.append(
            {"gemini": gemini_facts[left_index], "openai": openai_facts[right_index]}
        )
    for index, fact in enumerate(gemini_facts):
        if index not in used_left:
            pairs.append({"gemini": fact, "openai": None})
    for index, fact in enumerate(openai_facts):
        if index not in used_right:
            pairs.append({"gemini": None, "openai": fact})
    return pairs


def _pair_score(left: dict[str, Any], right: dict[str, Any]) -> int:
    score = 0
    if left["fact_type"] == right["fact_type"]:
        score += 10
    if left["row"] and left["row"] == right["row"]:
        score += 40
    if left["header_path"] and left["header_path"] == right["header_path"]:
        score += 20
    if left["value_exact"] and left["value_exact"] == right["value_exact"]:
        score += 50
    if left["numeric_value"] and left["numeric_value"] == right["numeric_value"]:
        score += 20
    if left["period"] and left["period"] == right["period"]:
        score += 10
    return score if score >= 50 else 0


def _partial_agreement(left: dict[str, Any], right: dict[str, Any]) -> bool:
    same_row = bool(left["row"] and left["row"] == right["row"])
    same_value = bool(
        left["value_exact"]
        and left["value_exact"] == right["value_exact"]
        and left["sign"] == right["sign"]
    )
    same_numeric = bool(
        left["numeric_value"]
        and left["numeric_value"] == right["numeric_value"]
        and left["sign"] == right["sign"]
    )
    return same_row and (same_value or same_numeric)


def _source_regions_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_observed = _object(left.get("observed"))
    right_observed = _object(right.get("observed"))
    left_regions = _object(left_observed.get("source_regions"))
    right_regions = _object(right_observed.get("source_regions"))
    if not _bbox_pair_intersects(
        left_regions.get("row_label_bbox"), right_regions.get("row_label_bbox")
    ) or not _bbox_pair_intersects(
        left_regions.get("value_bbox"), right_regions.get("value_bbox")
    ):
        return False
    left_headers = left_regions.get("header_bboxes")
    right_headers = right_regions.get("header_bboxes")
    header_path = left_observed.get("header_path_exact")
    if (
        not isinstance(header_path, list)
        or not header_path
        or not isinstance(left_headers, list)
        or not isinstance(right_headers, list)
        or len(left_headers) != len(header_path)
        or len(right_headers) != len(header_path)
        or any(
            not _bbox_pair_intersects(left_box, right_box)
            for left_box, right_box in zip(left_headers, right_headers)
        )
    ):
        return False

    left_interpreted = _object(left.get("interpreted"))
    left_request = _object(_object(left.get("evidence_request")).get("requested_text"))
    right_request = _object(
        _object(right.get("evidence_request")).get("requested_text")
    )
    left_qualifiers = _object(left_regions.get("qualifier_bboxes"))
    right_qualifiers = _object(right_regions.get("qualifier_bboxes"))
    qualifier_requirements = {
        "period": (
            left_interpreted.get("period"),
            left_request.get("period_exact"),
            right_request.get("period_exact"),
        ),
        "currency": (
            left_interpreted.get("currency_literal")
            or left_interpreted.get("currency_code"),
            left_request.get("currency_exact"),
            right_request.get("currency_exact"),
        ),
        "unit": (
            left_interpreted.get("unit"),
            left_request.get("unit_exact"),
            right_request.get("unit_exact"),
        ),
        "scale": (
            left_interpreted.get("scale"),
            left_request.get("scale_exact"),
            right_request.get("scale_exact"),
        ),
        "entity": (
            left_interpreted.get("entity"),
            left_request.get("entity_exact"),
            right_request.get("entity_exact"),
        ),
    }
    for kind, (material, left_exact, right_exact) in qualifier_requirements.items():
        if not _material_text(material):
            continue
        if (
            not _material_text(left_exact)
            or normalize_whitespace(left_exact) != normalize_whitespace(right_exact)
            or not _bbox_pair_intersects(
                left_qualifiers.get(kind), right_qualifiers.get(kind)
            )
        ):
            return False
    return True


def _fact_is_certain(value: dict[str, Any]) -> bool:
    uncertainty = _object(value.get("uncertainty"))
    return bool(
        uncertainty.get("status") == "certain"
        and not uncertainty.get("reason_codes")
        and not uncertainty.get("alternative_interpretations")
    )


def _fact_evidence_prerequisites(value: dict[str, Any]) -> bool:
    observed = _object(value.get("observed"))
    interpreted = _object(value.get("interpreted"))
    requested = _object(_object(value.get("evidence_request")).get("requested_text"))
    return bool(
        _material_text(observed.get("row_label_exact"))
        and isinstance(observed.get("header_path_exact"), list)
        and observed["header_path_exact"]
        and _material_text(interpreted.get("period"))
        and _material_text(requested.get("period_exact"))
    )


def _bbox_pair_intersects(left: Any, right: Any) -> bool:
    return bool(valid_bbox(left) and valid_bbox(right) and bbox_iou(left, right) > 0)


def _material_text(value: Any) -> bool:
    rendered = normalize_whitespace(value)
    return bool(rendered and rendered.casefold() != "unknown")


def _physical_signature(
    fact: dict[str, Any], output: dict[str, Any]
) -> tuple[Any, ...]:
    ids = set(_object(fact.get("observed")).get("source_cell_ids") or [])
    cells = []
    for cell in output.get("physical_cells") or []:
        if isinstance(cell, dict) and cell.get("cell_id") in ids:
            bbox = cell.get("bbox") or []
            cells.append(
                (
                    cell.get("role"),
                    normalize_whitespace(cell.get("text_exact")),
                    tuple(round(float(item), 4) for item in bbox)
                    if valid_bbox(bbox)
                    else (),
                )
            )
    return tuple(sorted(cells))


def _consensus_fact(
    left: dict[str, Any], right: dict[str, Any], canonical: dict[str, Any]
) -> dict[str, Any]:
    result = {
        "fact_type": canonical["fact_type"],
        "row_label_exact": _object(left.get("observed")).get("row_label_exact"),
        "header_path_exact": copy.deepcopy(
            _object(left.get("observed")).get("header_path_exact") or []
        ),
        "value_exact": _object(left.get("observed")).get("value_exact"),
        "interpreted": copy.deepcopy(left.get("interpreted") or {}),
        "evidence_request": copy.deepcopy(left.get("evidence_request") or {}),
        "gemini_source_regions": copy.deepcopy(
            _object(_object(left.get("observed")).get("source_regions"))
        ),
        "openai_source_regions": copy.deepcopy(
            _object(_object(right.get("observed")).get("source_regions"))
        ),
        "canonical_identity": canonical,
    }
    result["fact_checksum"] = sha256_json(result)
    return result


def _consensus_entry(
    ordinal: int,
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
    status: str,
    *,
    fact: dict[str, Any] | None,
    differences: list[str],
    source_compatible: bool,
    physical_same: bool,
) -> dict[str, Any]:
    return {
        "consensus_id": f"consensus_{ordinal:04d}",
        "gemini_fact_id": left.get("fact_id") if left else None,
        "openai_fact_id": right.get("fact_id") if right else None,
        "status": status,
        "runtime_disposition": (
            "evidence_eligible"
            if status in AGREEMENT_STATUSES
            else "human_review_required"
        ),
        "canonical_fact": fact,
        "material_differences": sorted(set(differences)),
        "source_region_compatible": source_compatible,
        "physical_layout_same": physical_same,
    }


def _validate_fact(value: Any, cell_ids: set[str]) -> list[str]:
    if not isinstance(value, dict) or set(value) != {
        "fact_id",
        "fact_type",
        "observed",
        "interpreted",
        "evidence_request",
        "uncertainty",
    }:
        return ["keys_invalid"]
    errors: list[str] = []
    if (
        not _identifier(value.get("fact_id"))
        or value.get("fact_type") not in FACT_TYPES
    ):
        errors.append("identity_invalid")
    observed = value.get("observed")
    if not _valid_observed(observed, cell_ids):
        errors.append("observed_invalid")
    interpreted = value.get("interpreted")
    if not _valid_interpreted(interpreted):
        errors.append("interpreted_invalid")
    request = value.get("evidence_request")
    if not _valid_evidence_request(request, observed):
        errors.append("evidence_request_invalid")
    if not _valid_uncertainty(value.get("uncertainty")):
        errors.append("uncertainty_invalid")
    return errors


def _valid_context(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "table_title_exact",
        "period_context_exact",
        "currency_context_exact",
        "unit_scale_context_exact",
        "entity_context_exact",
        "uncertainty_codes",
    }:
        return False
    return all(
        item is None or isinstance(item, str)
        for key, item in value.items()
        if key != "uncertainty_codes"
    ) and _string_list(value.get("uncertainty_codes"), max_items=16)


def _valid_physical_cell(value: Any) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value)
        == {"cell_id", "text_exact", "bbox", "role", "row_hint", "column_hint"}
        and _identifier(value.get("cell_id"))
        and isinstance(value.get("text_exact"), str)
        and len(value["text_exact"]) <= 1000
        and valid_bbox(value.get("bbox"))
        and value.get("role") in CELL_ROLES
        and _nullable_string(value.get("row_hint"))
        and _nullable_string(value.get("column_hint"))
    )


def _valid_observed(value: Any, cell_ids: set[str]) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "row_label_exact",
        "header_path_exact",
        "value_exact",
        "source_cell_ids",
        "source_regions",
    }:
        return False
    refs = value.get("source_cell_ids")
    regions = value.get("source_regions")
    return bool(
        _nullable_string(value.get("row_label_exact"))
        and _string_list(value.get("header_path_exact"), max_items=12)
        and isinstance(value.get("value_exact"), str)
        and value["value_exact"]
        and isinstance(refs, list)
        and refs
        and len(refs) == len(set(refs))
        and all(ref in cell_ids for ref in refs)
        and isinstance(regions, dict)
        and set(regions)
        == {"row_label_bbox", "value_bbox", "header_bboxes", "qualifier_bboxes"}
        and (regions["row_label_bbox"] is None or valid_bbox(regions["row_label_bbox"]))
        and valid_bbox(regions["value_bbox"])
        and isinstance(regions["header_bboxes"], list)
        and all(valid_bbox(item) for item in regions["header_bboxes"])
        and isinstance(regions["qualifier_bboxes"], dict)
        and set(regions["qualifier_bboxes"])
        == {"period", "currency", "unit", "scale", "entity"}
        and all(
            item is None or valid_bbox(item)
            for item in regions["qualifier_bboxes"].values()
        )
    )


def _valid_interpreted(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "normalized_row_identity",
        "numeric_value",
        "sign",
        "period",
        "currency_literal",
        "currency_code",
        "unit",
        "scale",
        "entity",
        "qualifiers",
    }:
        return False
    if value.get("sign") not in SIGN_VALUES:
        return False
    if not all(
        _nullable_string(value.get(key))
        for key in (
            "normalized_row_identity",
            "numeric_value",
            "period",
            "currency_literal",
            "currency_code",
            "unit",
            "scale",
            "entity",
        )
    ):
        return False
    return _string_list(value.get("qualifiers"), max_items=32)


def _valid_evidence_request(value: Any, observed: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "requested_text",
        "qualifier_scopes",
        "required_relations",
    }:
        return False
    requested = value.get("requested_text")
    if not isinstance(requested, dict) or set(requested) != {
        "row_label_exact",
        "header_path_exact",
        "value_exact",
        "period_exact",
        "currency_exact",
        "unit_exact",
        "scale_exact",
        "entity_exact",
    }:
        return False
    if not isinstance(observed, dict):
        return False
    if requested.get("value_exact") != observed.get("value_exact"):
        return False
    if requested.get("row_label_exact") != observed.get("row_label_exact"):
        return False
    if requested.get("header_path_exact") != observed.get("header_path_exact"):
        return False
    if not all(
        _nullable_string(requested.get(key))
        for key in (
            "row_label_exact",
            "period_exact",
            "currency_exact",
            "unit_exact",
            "scale_exact",
            "entity_exact",
        )
    ):
        return False
    scopes = value.get("qualifier_scopes")
    if (
        not isinstance(scopes, dict)
        or set(scopes)
        != {
            "period",
            "currency",
            "unit",
            "scale",
            "entity",
        }
        or any(
            item not in {"value", "row_label", "header", "table"}
            for item in scopes.values()
        )
    ):
        return False
    allowed_relations = {
        "row_value_spatial",
        "header_value_spatial",
        "period_scope",
        "currency_scope",
        "unit_scale_scope",
        "entity_scope",
    }
    return _bounded_codes(value.get("required_relations"), allowed_relations, 6)


def _valid_uncertainty(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "status",
        "reason_codes",
        "alternative_interpretations",
    }:
        return False
    if value.get("status") not in UNCERTAINTY_VALUES:
        return False
    if not _bounded_codes(value.get("reason_codes"), FACT_UNCERTAINTY_CODES, 16):
        return False
    alternatives = value.get("alternative_interpretations")
    return (
        isinstance(alternatives, list)
        and len(alternatives) <= 4
        and all(
            isinstance(item, dict) and isinstance(item.get("description"), str)
            for item in alternatives
        )
    )


def _closed_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _identifier_schema() -> dict[str, Any]:
    return {"type": "string", "minLength": 1, "maxLength": 200}


def _sha256_schema() -> dict[str, Any]:
    return {"type": "string", "minLength": 64, "maxLength": 64}


def _bbox_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "number", "minimum": 0, "maximum": 1},
        "minItems": 4,
        "maxItems": 4,
    }


def _nullable_bbox_schema() -> dict[str, Any]:
    return {"anyOf": [_bbox_schema(), {"type": "null"}]}


def _nullable_string_schema(max_length: int = 1000) -> dict[str, Any]:
    return {
        "anyOf": [
            {"type": "string", "maxLength": max_length},
            {"type": "null"},
        ]
    }


def _string_array_schema(*, max_items: int, max_length: int = 500) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "maxLength": max_length},
        "maxItems": max_items,
    }


def _enum_array_schema(values: list[str], max_items: int = 16) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "enum": values},
        "maxItems": max_items,
    }


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 200 and not value.isspace()


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _source_bbox(value: Any) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) == 4
        and all(
            isinstance(item, (int, float))
            and not isinstance(item, bool)
            and math.isfinite(float(item))
            for item in value
        )
        and float(value[0]) < float(value[2])
        and float(value[1]) < float(value[3])
    )


def _string_list(value: Any, *, max_items: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= max_items
        and all(isinstance(item, str) for item in value)
    )


def _bounded_codes(value: Any, allowed: set[str], maximum: int) -> bool:
    return bool(
        isinstance(value, list)
        and len(value) <= maximum
        and len(value) == len(set(value))
        and all(isinstance(item, str) and item in allowed for item in value)
    )


def _nullable_string(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _canonical_decimal(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    rendered = value.strip()
    if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", rendered):
        return rendered
    sign = "-" if rendered.startswith("-") else ""
    unsigned = rendered.removeprefix("-")
    if "." in unsigned:
        whole, fraction = unsigned.split(".", 1)
        fraction = fraction.rstrip("0")
        unsigned = whole + ("." + fraction if fraction else "")
    unsigned = unsigned.lstrip("0") or "0"
    return "0" if unsigned == "0" else sign + unsigned


def _upper_or_none(value: Any) -> str | None:
    return value.upper() if isinstance(value, str) and value else None


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


def unique_strings(values: Iterable[Any]) -> list[str]:
    return sorted({str(item) for item in values if isinstance(item, str) and item})
