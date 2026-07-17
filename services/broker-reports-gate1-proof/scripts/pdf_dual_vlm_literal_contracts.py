from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Any, Iterable


MANIFEST_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_literal_manifest_v1"
DETECTION_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_literal_detection_v2"
LITERAL_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_literal_observations_v2"
REFERENCE_SCHEMA_VERSION = "broker_reports_pdf_table_literal_reference_v1"
REFERENCE_SEAL_SCHEMA_VERSION = "broker_reports_pdf_table_literal_reference_seal_v1"
PADDING_EXPERIMENT_SCHEMA_VERSION = (
    "broker_reports_pdf_table_crop_padding_experiment_v1"
)
TERMINAL_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_literal_terminal_v2"
DIFFS_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_literal_diffs_v1"
SCORING_SCHEMA_VERSION = "broker_reports_pdf_dual_vlm_literal_scores_v1"
DETECTION_PROMPT_VERSION = "dual_vlm_literal_table_detection_v2"
EXTRACTION_PROMPT_VERSION = "dual_vlm_literal_table_extraction_v2"
SCHEMA_ADAPTER_BENCHMARK_VERSION = "dual_vlm_literal_schema_equivalence_v2"

PADDING_VARIANTS = (0.0, 0.005, 0.01, 0.02, 0.03)
CELL_STATES = frozenset({"value", "empty", "unreadable", "ambiguous"})
REFERENCE_DECISIONS = frozenset({"confirmed", "corrected", "ambiguous", "excluded"})
UNCERTAINTY_CODES = frozenset(
    {
        "row_label_unclear",
        "header_unclear",
        "value_unclear",
        "binding_unclear",
        "source_region_unclear",
        "merged_visual_rows",
        "split_visual_row",
        "other",
    }
)
DISAGREEMENT_CLASSES = frozenset(
    {
        "entry_missing_in_gemini",
        "entry_missing_in_openai",
        "extra_entry_in_gemini",
        "extra_entry_in_openai",
        "row_label_text_mismatch",
        "column_header_text_mismatch",
        "column_header_path_mismatch",
        "visible_value_text_mismatch",
        "parsed_numeric_value_mismatch",
        "sign_mismatch",
        "decimal_or_thousands_separator_mismatch",
        "empty_vs_value_mismatch",
        "unreadable_vs_value_mismatch",
        "row_binding_mismatch",
        "column_binding_mismatch",
        "repeated_value_alignment_ambiguous",
        "merged_rows_vs_separate_rows",
        "split_row_vs_single_row",
        "source_bbox_material_mismatch",
        "raw_format_only_difference",
        "schema_or_contract_failure",
    }
)
FORBIDDEN_EXTRACTION_FIELDS = frozenset(
    {
        "fact_type",
        "normalized_row_identity",
        "financial_statement_category",
        "accounting_classification",
        "entity",
        "business_meaning",
        "financial_role",
        "semantic_aliases",
        "canonical_financial_name",
        "currency",
        "unit",
        "scale",
        "period",
    }
)

DETECTION_PROMPT = (
    "Inspect only the supplied PDF page image. Locate complete visual table regions. "
    "Do not read cells, transcribe content, classify financial meaning, or infer a table "
    "from prose or a table of contents. Return normalized page-relative bboxes exactly "
    "as observed. Every bbox array MUST use [x0, y0, x1, y1] = "
    "[left, top, right, bottom]: x0/x1 are horizontal positions and y0/y1 are "
    "vertical positions. Never use [top, left, bottom, right]. Require "
    "0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1. An invalid bbox is a terminal "
    "contract error and must not be repaired."
)

EXTRACTION_PROMPT = (
    "Read only literal visible table content from the supplied immutable crop. For every "
    "visible value-bearing entry, return the exact row-label text, exact printed column "
    "header path, exact visible value text, crop-relative source bboxes, cell state, and "
    "literal uncertainty codes. Preserve spelling, punctuation, spacing, currency marks, "
    "parentheses, dash forms, and separators. Do not classify financial meaning, normalize "
    "business concepts, infer missing qualifiers, translate, repair text, or use outside "
    "document knowledge. Every bbox array MUST use [x0, y0, x1, y1] = "
    "[left, top, right, bottom] relative to the crop: x0/x1 are horizontal positions "
    "and y0/y1 are vertical positions. Never use [top, left, bottom, right]. Require "
    "0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1. Empty header paths are allowed when "
    "no column header is printed."
)


class LiteralContractError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class NumericParse:
    parsed_numeric_value: str | None
    parsed_sign: str
    numeric_parse_status: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "parsed_numeric_value": self.parsed_numeric_value,
            "parsed_sign": self.parsed_sign,
            "numeric_parse_status": self.numeric_parse_status,
        }


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def detection_schema() -> dict[str, Any]:
    candidate = _closed_object(
        {
            "candidate_id": _identifier_schema(),
            "decision": {"type": "string", "enum": ["present", "uncertain"]},
            "bbox": _bbox_schema(),
            "uncertainty_codes": _string_array_schema(max_items=8, max_length=80),
        }
    )
    return {
        "$id": DETECTION_SCHEMA_VERSION,
        **_closed_object(
            {
                "schema_version": {
                    "type": "string",
                    "enum": [DETECTION_SCHEMA_VERSION],
                },
                "page_number": {"type": "integer", "minimum": 1},
                "candidates": {
                    "type": "array",
                    "items": candidate,
                    "minItems": 0,
                    "maxItems": 12,
                },
            }
        ),
    }


def literal_observation_schema() -> dict[str, Any]:
    entry = _closed_object(
        {
            "entry_id": _identifier_schema(),
            "row_label_text": {"type": "string", "maxLength": 4000},
            "column_header_path": _string_array_schema(
                max_items=12, max_length=2000
            ),
            "visible_value_text": {"type": "string", "maxLength": 4000},
            "row_label_bbox": _bbox_schema(),
            "header_bboxes": {
                "type": "array",
                "items": _bbox_schema(),
                "minItems": 0,
                "maxItems": 12,
            },
            "value_bbox": _bbox_schema(),
            "cell_state": {"type": "string", "enum": sorted(CELL_STATES)},
            "uncertainty_codes": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(UNCERTAINTY_CODES)},
                "minItems": 0,
                "maxItems": 16,
            },
        }
    )
    return {
        "$id": LITERAL_SCHEMA_VERSION,
        **_closed_object(
            {
                "schema_version": {
                    "type": "string",
                    "enum": [LITERAL_SCHEMA_VERSION],
                },
                "crop_sha256": _sha256_schema(),
                "table_identifier": _identifier_schema(),
                "entries": {
                    "type": "array",
                    "items": entry,
                    "minItems": 0,
                    "maxItems": 400,
                },
            }
        ),
    }


def detection_model_view(*, page_number: int, page_sha256: str) -> dict[str, Any]:
    return {
        "task": DETECTION_PROMPT,
        "prompt_contract_version": DETECTION_PROMPT_VERSION,
        "input_identity": {
            "page_number": page_number,
            "page_sha256": page_sha256,
            "coordinate_space": "normalized_full_page_top_left_origin",
        },
        "output_contract": {
            "schema_version": DETECTION_SCHEMA_VERSION,
            "bbox_array_order": ["x0_left", "y0_top", "x1_right", "y1_bottom"],
            "forbidden_bbox_array_order": ["top", "left", "bottom", "right"],
            "bbox_invariants": "0 <= x0 < x1 <= 1; 0 <= y0 < y1 <= 1",
        },
    }


def literal_model_view(
    *, crop_sha256: str, table_identifier: str, image_width: int, image_height: int
) -> dict[str, Any]:
    return {
        "task": EXTRACTION_PROMPT,
        "prompt_contract_version": EXTRACTION_PROMPT_VERSION,
        "input_identity": {
            "crop_sha256": crop_sha256,
            "table_identifier": table_identifier,
            "image_width": image_width,
            "image_height": image_height,
            "coordinate_space": "normalized_immutable_crop_top_left_origin",
        },
        "output_contract": {
            "schema_version": LITERAL_SCHEMA_VERSION,
            "bbox_array_order": ["x0_left", "y0_top", "x1_right", "y1_bottom"],
            "forbidden_bbox_array_order": ["top", "left", "bottom", "right"],
            "bbox_invariants": "0 <= x0 < x1 <= 1; 0 <= y0 < y1 <= 1",
            "primary_unit": "observed_table_entry",
            "mapping": "(row_label_text + column_header_path) -> visible_value_text",
            "financial_semantic_classification": False,
        },
    }


def validate_detection_output(value: Any, *, page_number: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["literal_detection_not_object"]
    if set(value) != {"schema_version", "page_number", "candidates"}:
        errors.append("literal_detection_fields_invalid")
    if value.get("schema_version") != DETECTION_SCHEMA_VERSION:
        errors.append("literal_detection_schema_version_invalid")
    if value.get("page_number") != page_number:
        errors.append("literal_detection_page_number_invalid")
    candidates = value.get("candidates")
    if not isinstance(candidates, list) or len(candidates) > 12:
        errors.append("literal_detection_candidates_invalid")
        return errors
    identifiers: set[str] = set()
    for index, candidate in enumerate(candidates):
        prefix = f"literal_detection_candidate_{index}"
        if not isinstance(candidate, dict) or set(candidate) != {
            "candidate_id",
            "decision",
            "bbox",
            "uncertainty_codes",
        }:
            errors.append(prefix + "_fields_invalid")
            continue
        identifier = candidate.get("candidate_id")
        if not _identifier(identifier) or identifier in identifiers:
            errors.append(prefix + "_id_invalid")
        else:
            identifiers.add(identifier)
        if candidate.get("decision") not in {"present", "uncertain"}:
            errors.append(prefix + "_decision_invalid")
        if not valid_bbox(candidate.get("bbox")):
            errors.append(prefix + "_bbox_invalid")
        if not _string_list(candidate.get("uncertainty_codes"), max_items=8):
            errors.append(prefix + "_uncertainty_codes_invalid")
    return errors


def validate_literal_output(
    value: Any, *, crop_sha256: str, table_identifier: str
) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["literal_output_not_object"]
    if set(value) != {
        "schema_version",
        "crop_sha256",
        "table_identifier",
        "entries",
    }:
        errors.append("literal_output_fields_invalid")
    if value.get("schema_version") != LITERAL_SCHEMA_VERSION:
        errors.append("literal_output_schema_version_invalid")
    if value.get("crop_sha256") != crop_sha256:
        errors.append("literal_output_crop_sha256_invalid")
    if value.get("table_identifier") != table_identifier:
        errors.append("literal_output_table_identifier_invalid")
    entries = value.get("entries")
    if not isinstance(entries, list) or len(entries) > 400:
        errors.append("literal_output_entries_invalid")
        return errors
    identifiers: set[str] = set()
    for index, entry in enumerate(entries):
        errors.extend(_validate_entry(entry, index=index, identifiers=identifiers))
    return errors


def parse_visible_numeric(value: Any) -> NumericParse:
    if not isinstance(value, str):
        return NumericParse(None, "unknown", "not_text")
    normalized = unicodedata.normalize("NFKC", value).strip()
    if normalized in {"", "-", "–", "—", "−", "--", "N/A", "n/a"}:
        return NumericParse(None, "not_applicable", "empty_marker")

    negative = normalized.startswith("(") and normalized.endswith(")")
    if negative:
        normalized = normalized[1:-1].strip()
    normalized = normalized.replace("−", "-").replace("–", "-").replace("—", "-")
    normalized = re.sub(r"^[^0-9+\-.,]+", "", normalized)
    normalized = re.sub(r"[^0-9.,]+$", "", normalized)
    normalized = normalized.replace("\u00a0", "").replace("\u202f", "").replace(" ", "")
    if not normalized or not re.search(r"\d", normalized):
        return NumericParse(None, "unknown", "non_numeric")

    sign = -1 if negative else 1
    if normalized.startswith("-"):
        sign *= -1
        normalized = normalized[1:]
    elif normalized.startswith("+"):
        normalized = normalized[1:]
    if not normalized or not re.fullmatch(r"[0-9.,]+", normalized):
        return NumericParse(None, "unknown", "invalid_characters")

    decimal_separator: str | None = None
    if "." in normalized and "," in normalized:
        decimal_separator = "." if normalized.rfind(".") > normalized.rfind(",") else ","
    elif normalized.count(".") == 1:
        tail = normalized.rsplit(".", 1)[1]
        decimal_separator = "." if len(tail) != 3 else None
    elif normalized.count(",") == 1:
        tail = normalized.rsplit(",", 1)[1]
        decimal_separator = "," if len(tail) != 3 else None

    if decimal_separator is None:
        digits = normalized.replace(",", "").replace(".", "")
    else:
        thousands = "," if decimal_separator == "." else "."
        digits = normalized.replace(thousands, "").replace(decimal_separator, ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", digits):
        return NumericParse(None, "unknown", "separator_pattern_invalid")
    try:
        parsed = Decimal(digits) * sign
    except InvalidOperation:
        return NumericParse(None, "unknown", "decimal_invalid")
    canonical = format(parsed, "f")
    if "." in canonical:
        canonical = canonical.rstrip("0").rstrip(".")
    if canonical == "-0":
        canonical = "0"
    parsed_sign = "zero" if parsed == 0 else ("negative" if parsed < 0 else "positive")
    return NumericParse(canonical, parsed_sign, "parsed")


def canonicalize_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[‐‑‒–—―−]", "-", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def canonicalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    numeric = parse_visible_numeric(entry.get("visible_value_text"))
    return {
        "entry_id": entry.get("entry_id"),
        "row_label_text_raw": entry.get("row_label_text"),
        "row_label_text_canonical": canonicalize_text(entry.get("row_label_text")),
        "column_header_path_raw": copy.deepcopy(entry.get("column_header_path") or []),
        "column_header_path_canonical": [
            canonicalize_text(item) for item in entry.get("column_header_path") or []
        ],
        "visible_value_text_raw": entry.get("visible_value_text"),
        "visible_value_text_canonical": canonicalize_text(
            entry.get("visible_value_text")
        ),
        **numeric.as_dict(),
        "cell_state": entry.get("cell_state"),
        "row_label_bbox": copy.deepcopy(entry.get("row_label_bbox")),
        "header_bboxes": copy.deepcopy(entry.get("header_bboxes") or []),
        "value_bbox": copy.deepcopy(entry.get("value_bbox")),
        "uncertainty_codes": copy.deepcopy(entry.get("uncertainty_codes") or []),
    }


def apply_padding_bbox(bbox: list[float], padding: float) -> list[float]:
    if not valid_bbox(bbox):
        raise LiteralContractError("literal_padding_detected_bbox_invalid")
    if padding not in PADDING_VARIANTS:
        raise LiteralContractError("literal_padding_variant_not_predeclared")
    x0, y0, x1, y1 = (float(item) for item in bbox)
    return [
        round(max(0.0, x0 - padding), 9),
        round(max(0.0, y0 - padding), 9),
        round(min(1.0, x1 + padding), 9),
        round(min(1.0, y1 + padding), 9),
    ]


def padding_transformation(bbox: list[float], padding: float) -> dict[str, Any]:
    padded = apply_padding_bbox(bbox, padding)
    return {
        "detected_bbox": [round(float(item), 9) for item in bbox],
        "padding_fraction_per_page_side": padding,
        "requested_expansion": {
            "left_page_width_fraction": padding,
            "right_page_width_fraction": padding,
            "top_page_height_fraction": padding,
            "bottom_page_height_fraction": padding,
        },
        "clamped_to_page": [
            padded[0] == 0.0 and bbox[0] - padding < 0.0,
            padded[1] == 0.0 and bbox[1] - padding < 0.0,
            padded[2] == 1.0 and bbox[2] + padding > 1.0,
            padded[3] == 1.0 and bbox[3] + padding > 1.0,
        ],
        "padded_crop_bbox": padded,
    }


def valid_bbox(value: Any) -> bool:
    if not isinstance(value, list) or len(value) != 4:
        return False
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        return False
    if not all(math.isfinite(float(item)) for item in value):
        return False
    x0, y0, x1, y1 = (float(item) for item in value)
    return 0.0 <= x0 < x1 <= 1.0 and 0.0 <= y0 < y1 <= 1.0


def bbox_iou(left: list[float], right: list[float]) -> float:
    intersection = _bbox_intersection_area(left, right)
    if intersection <= 0:
        return 0.0
    union = bbox_area(left) + bbox_area(right) - intersection
    return intersection / union if union > 0 else 0.0


def bbox_area(value: list[float]) -> float:
    return max(0.0, float(value[2]) - float(value[0])) * max(
        0.0, float(value[3]) - float(value[1])
    )


def bbox_contains(outer: list[float], inner: list[float], *, tolerance: float = 1e-9) -> bool:
    return (
        outer[0] <= inner[0] + tolerance
        and outer[1] <= inner[1] + tolerance
        and outer[2] >= inner[2] - tolerance
        and outer[3] >= inner[3] - tolerance
    )


def normalized_bbox_to_points(
    bbox: list[float], page_bbox_points: list[float]
) -> list[float]:
    if not valid_bbox(bbox) or len(page_bbox_points) != 4:
        raise LiteralContractError("literal_bbox_projection_invalid")
    px0, py0, px1, py1 = (float(item) for item in page_bbox_points)
    width = px1 - px0
    height = py1 - py0
    return [
        px0 + bbox[0] * width,
        py0 + bbox[1] * height,
        px0 + bbox[2] * width,
        py0 + bbox[3] * height,
    ]


def project_crop_relative_bbox_to_page_normalized(
    bbox: list[float], crop_bbox: list[float]
) -> list[float]:
    if not valid_bbox(bbox) or not valid_bbox(crop_bbox):
        raise LiteralContractError("literal_crop_bbox_projection_invalid")
    x0, y0, x1, y1 = (float(item) for item in crop_bbox)
    width = x1 - x0
    height = y1 - y0
    return [
        round(x0 + float(bbox[0]) * width, 9),
        round(y0 + float(bbox[1]) * height, 9),
        round(x0 + float(bbox[2]) * width, 9),
        round(y0 + float(bbox[3]) * height, 9),
    ]


def project_entry_to_page_normalized(
    entry: dict[str, Any], crop_bbox: list[float]
) -> dict[str, Any]:
    projected = copy.deepcopy(entry)
    projected["row_label_bbox"] = project_crop_relative_bbox_to_page_normalized(
        entry["row_label_bbox"], crop_bbox
    )
    projected["header_bboxes"] = [
        project_crop_relative_bbox_to_page_normalized(item, crop_bbox)
        for item in entry.get("header_bboxes") or []
    ]
    projected["value_bbox"] = project_crop_relative_bbox_to_page_normalized(
        entry["value_bbox"], crop_bbox
    )
    return projected


def entry_regions_compatible(
    left: dict[str, Any], right: dict[str, Any]
) -> bool:
    return _entry_regions_compatible(
        canonicalize_entry(left), canonicalize_entry(right)
    )


def match_entries(
    gemini_entries: list[dict[str, Any]], openai_entries: list[dict[str, Any]]
) -> dict[str, Any]:
    left = [canonicalize_entry(item) for item in gemini_entries]
    right = [canonicalize_entry(item) for item in openai_entries]
    size = max(len(left), len(right))
    if size == 0:
        return {"matches": [], "unmatched_gemini": [], "unmatched_openai": []}
    edge_matrix: list[list[dict[str, Any] | None]] = []
    weight_matrix: list[list[int]] = []
    for left_index in range(size):
        edge_row: list[dict[str, Any] | None] = []
        weight_row: list[int] = []
        for right_index in range(size):
            if left_index >= len(left) or right_index >= len(right):
                edge_row.append(None)
                weight_row.append(0)
                continue
            edge = _entry_edge(
                left[left_index], right[right_index], left_index, right_index, size
            )
            edge_row.append(edge)
            weight_row.append(edge["matching_weight"] if edge["eligible"] else 0)
        edge_matrix.append(edge_row)
        weight_matrix.append(weight_row)

    assignments = _hungarian_max(weight_matrix)
    matches: list[dict[str, Any]] = []
    matched_left: set[int] = set()
    matched_right: set[int] = set()
    for left_index, right_index in assignments:
        if left_index >= len(left) or right_index >= len(right):
            continue
        edge = edge_matrix[left_index][right_index]
        if not edge or not edge["eligible"]:
            continue
        alternatives_left = sorted(
            (
                item["matching_weight"]
                for item in edge_matrix[left_index]
                if item and item["eligible"] and item is not edge
            ),
            reverse=True,
        )
        alternatives_right = sorted(
            (
                edge_matrix[row][right_index]["matching_weight"]
                for row in range(len(left))
                if edge_matrix[row][right_index]
                and edge_matrix[row][right_index]["eligible"]
                and edge_matrix[row][right_index] is not edge
            ),
            reverse=True,
        )
        unique = all(
            edge["matching_weight"] > alternative
            for alternative in alternatives_left[:1] + alternatives_right[:1]
        )
        matches.append(
            {
                "gemini_entry_id": gemini_entries[left_index]["entry_id"],
                "openai_entry_id": openai_entries[right_index]["entry_id"],
                "gemini_index": left_index,
                "openai_index": right_index,
                "matching_signals": copy.deepcopy(edge["matching_signals"]),
                "matching_score_components": copy.deepcopy(edge["score_components"]),
                "matching_weight": edge["matching_weight"],
                "tie_break_reason": edge["tie_break_reason"],
                "match_unique": unique,
                "status": "aligned" if unique else "entry_alignment_ambiguous",
            }
        )
        matched_left.add(left_index)
        matched_right.add(right_index)
    matches.sort(key=lambda item: (item["gemini_index"], item["openai_index"]))
    return {
        "matches": matches,
        "unmatched_gemini": [
            gemini_entries[index]["entry_id"]
            for index in range(len(left))
            if index not in matched_left
        ],
        "unmatched_openai": [
            openai_entries[index]["entry_id"]
            for index in range(len(right))
            if index not in matched_right
        ],
    }


def build_literal_diffs(
    *,
    gemini_entries: list[dict[str, Any]],
    openai_entries: list[dict[str, Any]],
    alignment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    alignment = alignment or match_entries(gemini_entries, openai_entries)
    gemini_by_id = {str(item["entry_id"]): item for item in gemini_entries}
    openai_by_id = {str(item["entry_id"]): item for item in openai_entries}
    compact_agreements: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []

    for entry_id in alignment.get("unmatched_gemini") or []:
        entry = gemini_by_id[str(entry_id)]
        disagreements.append(
            _missing_diff("entry_missing_in_openai", gemini=entry, openai=None)
        )
    for entry_id in alignment.get("unmatched_openai") or []:
        entry = openai_by_id[str(entry_id)]
        disagreements.append(
            _missing_diff("entry_missing_in_gemini", gemini=None, openai=entry)
        )

    for match in alignment.get("matches") or []:
        gemini = gemini_by_id[str(match["gemini_entry_id"])]
        openai = openai_by_id[str(match["openai_entry_id"])]
        if not match.get("match_unique"):
            disagreements.append(
                {
                    "class": "repeated_value_alignment_ambiguous",
                    "gemini_entry_id": gemini["entry_id"],
                    "openai_entry_id": openai["entry_id"],
                    "minimal_difference": "entry_alignment_ambiguous",
                    "gemini": copy.deepcopy(gemini),
                    "openai": copy.deepcopy(openai),
                    "alignment": copy.deepcopy(match),
                }
            )
            continue
        pair_diffs = _aligned_entry_diffs(gemini, openai, match)
        if pair_diffs:
            disagreements.extend(pair_diffs)
        else:
            gemini_canonical = canonicalize_entry(gemini)
            raw_equal = (
                gemini.get("row_label_text") == openai.get("row_label_text")
                and gemini.get("column_header_path")
                == openai.get("column_header_path")
                and gemini.get("visible_value_text")
                == openai.get("visible_value_text")
            )
            compact_agreements.append(
                {
                    "gemini_entry_id": gemini["entry_id"],
                    "openai_entry_id": openai["entry_id"],
                    "status": "exact_raw_agreement"
                    if raw_equal
                    else "canonical_match_with_raw_format_difference",
                    "canonical_mapping": {
                        "row_label_text": gemini_canonical[
                            "row_label_text_canonical"
                        ],
                        "column_header_path": gemini_canonical[
                            "column_header_path_canonical"
                        ],
                        "visible_value_text": gemini_canonical[
                            "visible_value_text_canonical"
                        ],
                        "parsed_numeric_value": gemini_canonical[
                            "parsed_numeric_value"
                        ],
                    },
                }
            )
    counts: dict[str, int] = {}
    for item in disagreements:
        counts[item["class"]] = counts.get(item["class"], 0) + 1
    return {
        "schema_version": DIFFS_SCHEMA_VERSION,
        "alignment": copy.deepcopy(alignment),
        "agreement_count": len(compact_agreements),
        "exact_raw_agreement_count": sum(
            item["status"] == "exact_raw_agreement" for item in compact_agreements
        ),
        "canonical_raw_format_difference_count": sum(
            item["status"] == "canonical_match_with_raw_format_difference"
            for item in compact_agreements
        ),
        "compact_agreements": compact_agreements,
        "disagreement_count": len(disagreements),
        "disagreement_class_counts": dict(sorted(counts.items())),
        "disagreements": disagreements,
    }


def automatically_acceptable(
    *,
    gemini_entry: dict[str, Any],
    openai_entry: dict[str, Any],
    alignment_unique: bool,
    parser_evidence_status: str,
    parser_binding_unique: bool,
) -> bool:
    if not alignment_unique or not parser_binding_unique:
        return False
    if parser_evidence_status != "parser_literal_verified":
        return False
    diffs = _aligned_entry_diffs(
        gemini_entry,
        openai_entry,
        {"gemini_entry_id": gemini_entry.get("entry_id"), "openai_entry_id": openai_entry.get("entry_id")},
    )
    material = [item for item in diffs if item["class"] != "raw_format_only_difference"]
    if material:
        return False
    left = canonicalize_entry(gemini_entry)
    right = canonicalize_entry(openai_entry)
    return (
        left["row_label_text_canonical"] == right["row_label_text_canonical"]
        and left["column_header_path_canonical"]
        == right["column_header_path_canonical"]
        and (
            left["visible_value_text_canonical"]
            == right["visible_value_text_canonical"]
            or (
                left["parsed_numeric_value"] is not None
                and left["parsed_numeric_value"] == right["parsed_numeric_value"]
            )
        )
        and left["parsed_sign"] == right["parsed_sign"]
        and _entry_regions_compatible(left, right)
    )


def schema_equivalence_record(
    canonical_schema: dict[str, Any], adapted_schema: dict[str, Any]
) -> dict[str, Any]:
    removed: list[str] = []
    transformed: list[str] = []
    weakened: list[str] = []
    _compare_schema_nodes(
        canonical_schema,
        adapted_schema,
        path="$",
        removed=removed,
        transformed=transformed,
        weakened=weakened,
    )
    logical_required_equivalent = _required_paths(canonical_schema) == _required_paths(
        adapted_schema
    )
    enum_equivalent = _enum_paths(canonical_schema) == _enum_paths(adapted_schema)
    nullability_equivalent = _nullable_paths(canonical_schema) == _nullable_paths(
        adapted_schema
    )
    return {
        "schema_adapter_benchmark_version": SCHEMA_ADAPTER_BENCHMARK_VERSION,
        "canonical_schema_sha256": sha256_json(canonical_schema),
        "adapted_schema_sha256": sha256_json(adapted_schema),
        "removed_keywords": sorted(removed),
        "transformed_keywords": sorted(transformed),
        "weakened_keywords": sorted(weakened),
        "required_field_cardinality_equivalent": logical_required_equivalent,
        "enum_meaning_equivalent": enum_equivalent,
        "nullability_equivalent": nullability_equivalent,
        "logical_contract_equivalent": (
            logical_required_equivalent and enum_equivalent and nullability_equivalent
        ),
        "comparison_unit": "model + provider API + schema adapter",
        "isolated_model_comparison_claimed": False,
    }


def validate_reference(value: Any, *, require_human_reviewed: bool) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["literal_reference_not_object"]
    if value.get("schema_version") != REFERENCE_SCHEMA_VERSION:
        errors.append("literal_reference_schema_version_invalid")
    if require_human_reviewed and value.get("human_reviewed") is not True:
        errors.append("literal_reference_not_human_reviewed")
    cases = value.get("cases")
    if not isinstance(cases, list):
        return errors + ["literal_reference_cases_invalid"]
    entry_ids: set[str] = set()
    for case_index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"literal_reference_case_{case_index}_invalid")
            continue
        if not _sha256(case.get("document_sha256")) or not isinstance(
            case.get("page_number"), int
        ):
            errors.append(f"literal_reference_case_{case_index}_identity_invalid")
        for table_index, table in enumerate(case.get("tables") or []):
            if not isinstance(table, dict) or not valid_bbox(table.get("complete_table_bbox")):
                errors.append(
                    f"literal_reference_case_{case_index}_table_{table_index}_invalid"
                )
                continue
            if table.get("evidence_medium") not in {"text_layer", "raster", "mixed"}:
                errors.append(
                    f"literal_reference_case_{case_index}_table_{table_index}_medium_invalid"
                )
            for entry_index, entry in enumerate(table.get("entries") or []):
                prefix = (
                    f"literal_reference_case_{case_index}_table_{table_index}_entry_{entry_index}"
                )
                entry_errors = _validate_reference_entry(entry, entry_ids=entry_ids)
                errors.extend(prefix + "_" + item for item in entry_errors)
    return errors


def _validate_entry(
    entry: Any, *, index: int, identifiers: set[str]
) -> list[str]:
    prefix = f"literal_entry_{index}"
    fields = {
        "entry_id",
        "row_label_text",
        "column_header_path",
        "visible_value_text",
        "row_label_bbox",
        "header_bboxes",
        "value_bbox",
        "cell_state",
        "uncertainty_codes",
    }
    if not isinstance(entry, dict) or set(entry) != fields:
        return [prefix + "_fields_invalid"]
    errors: list[str] = []
    entry_id = entry.get("entry_id")
    if not _identifier(entry_id) or entry_id in identifiers:
        errors.append(prefix + "_id_invalid")
    else:
        identifiers.add(entry_id)
    if not isinstance(entry.get("row_label_text"), str):
        errors.append(prefix + "_row_label_invalid")
    if not _string_list(entry.get("column_header_path"), max_items=12):
        errors.append(prefix + "_header_path_invalid")
    if not isinstance(entry.get("visible_value_text"), str):
        errors.append(prefix + "_value_invalid")
    if not valid_bbox(entry.get("row_label_bbox")):
        errors.append(prefix + "_row_label_bbox_invalid")
    header_bboxes = entry.get("header_bboxes")
    if not isinstance(header_bboxes, list) or len(header_bboxes) > 12 or any(
        not valid_bbox(item) for item in header_bboxes
    ):
        errors.append(prefix + "_header_bboxes_invalid")
    if not valid_bbox(entry.get("value_bbox")):
        errors.append(prefix + "_value_bbox_invalid")
    state = entry.get("cell_state")
    if state not in CELL_STATES:
        errors.append(prefix + "_cell_state_invalid")
    uncertainty = entry.get("uncertainty_codes")
    if (
        not isinstance(uncertainty, list)
        or len(uncertainty) > 16
        or any(item not in UNCERTAINTY_CODES for item in uncertainty)
    ):
        errors.append(prefix + "_uncertainty_codes_invalid")
    if state == "value" and not str(entry.get("visible_value_text") or "").strip():
        errors.append(prefix + "_value_state_text_missing")
    return errors


def _validate_reference_entry(entry: Any, *, entry_ids: set[str]) -> list[str]:
    if not isinstance(entry, dict):
        return ["not_object"]
    required = {
        "reference_entry_id",
        "row_label_text",
        "column_header_path",
        "visible_value_text",
        "row_label_bbox",
        "header_bboxes",
        "value_bbox",
        "cell_state",
        "visibly_empty",
        "spans_multiple_visual_rows",
        "spans_multiple_visual_columns",
        "literal_source_notes",
        "review_status",
        "review_provenance",
    }
    if set(entry) != required:
        return ["fields_invalid"]
    entry_id = entry.get("reference_entry_id")
    errors: list[str] = []
    if not _identifier(entry_id) or entry_id in entry_ids:
        errors.append("id_invalid")
    else:
        entry_ids.add(entry_id)
    provider_entry = {
        "entry_id": entry_id,
        "row_label_text": entry.get("row_label_text"),
        "column_header_path": entry.get("column_header_path"),
        "visible_value_text": entry.get("visible_value_text"),
        "row_label_bbox": entry.get("row_label_bbox"),
        "header_bboxes": entry.get("header_bboxes"),
        "value_bbox": entry.get("value_bbox"),
        "cell_state": entry.get("cell_state"),
        "uncertainty_codes": [],
    }
    review_status = entry.get("review_status")
    provider_errors = _validate_entry(provider_entry, index=0, identifiers=set())
    if review_status in {"ambiguous", "excluded"}:
        provider_errors = [
            item
            for item in provider_errors
            if item
            not in {
                "literal_entry_0_row_label_bbox_invalid",
                "literal_entry_0_value_bbox_invalid",
            }
        ]
    errors.extend(provider_errors)
    if review_status not in REFERENCE_DECISIONS:
        errors.append("review_status_invalid")
    for key in (
        "visibly_empty",
        "spans_multiple_visual_rows",
        "spans_multiple_visual_columns",
    ):
        if not isinstance(entry.get(key), bool):
            errors.append(key + "_invalid")
    if not isinstance(entry.get("literal_source_notes"), str):
        errors.append("literal_source_notes_invalid")
    if not isinstance(entry.get("review_provenance"), dict):
        errors.append("review_provenance_invalid")
    return errors


def _entry_edge(
    left: dict[str, Any],
    right: dict[str, Any],
    left_index: int,
    right_index: int,
    size: int,
) -> dict[str, Any]:
    value_iou = bbox_iou(left["value_bbox"], right["value_bbox"])
    value_centers = _centers_compatible(left["value_bbox"], right["value_bbox"])
    row_iou = bbox_iou(left["row_label_bbox"], right["row_label_bbox"])
    row_centers = _centers_compatible(left["row_label_bbox"], right["row_label_bbox"])
    header_score = _header_region_score(left["header_bboxes"], right["header_bboxes"])
    row_text = _text_similarity(
        left["row_label_text_canonical"], right["row_label_text_canonical"]
    )
    header_text = _text_similarity(
        " / ".join(left["column_header_path_canonical"]),
        " / ".join(right["column_header_path_canonical"]),
    )
    value_text = _text_similarity(
        left["visible_value_text_canonical"], right["visible_value_text_canonical"]
    )
    value_region = max(value_iou, 0.75 if value_centers else 0.0)
    row_region = max(row_iou, 0.75 if row_centers else 0.0)
    spatial_anchor = value_region > 0 or row_region > 0 or header_score > 0
    text_anchor = row_text >= 0.75 and (header_text >= 0.75 or value_text >= 0.75)
    eligible = spatial_anchor and (value_region >= 0.1 or row_region >= 0.1 or text_anchor)
    components = {
        "value_region_spatial_compatibility": round(value_region, 6),
        "row_label_region_compatibility": round(row_region, 6),
        "header_region_compatibility": round(header_score, 6),
        "row_label_text_similarity": round(row_text, 6),
        "header_text_similarity": round(header_text, 6),
        "visible_value_text_similarity": round(value_text, 6),
    }
    spatial_value = round(value_region * 100)
    spatial_row = round(row_region * 100)
    spatial_header = round(header_score * 100)
    text_value = round(((row_text + header_text + value_text) / 3) * 100)
    order_tie_break = max(0, size - abs(left_index - right_index))
    weight = (
        spatial_value * 1_000_000_000
        + spatial_row * 1_000_000
        + spatial_header * 1_000
        + text_value * 10
        + order_tie_break
    )
    return {
        "eligible": eligible,
        "matching_signals": {
            "value_region_spatial": value_region > 0,
            "row_label_region_spatial": row_region > 0,
            "header_region_spatial": header_score > 0,
            "canonical_text_support": text_anchor,
            "numeric_value_only_match_used": False,
        },
        "score_components": components,
        "matching_weight": weight,
        "tie_break_reason": (
            "table_order_final_deterministic_tie_break"
            if order_tie_break
            else "no_table_order_preference"
        ),
    }


def _hungarian_max(weights: list[list[int]]) -> list[tuple[int, int]]:
    size = len(weights)
    if size == 0:
        return []
    maximum = max(max(row) for row in weights)
    costs = [[maximum - item for item in row] for row in weights]
    u = [0] * (size + 1)
    v = [0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)
    for row in range(1, size + 1):
        p[0] = row
        column0 = 0
        minv = [10**30] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[column0] = True
            row0 = p[column0]
            delta = 10**30
            column1 = 0
            for column in range(1, size + 1):
                if used[column]:
                    continue
                current = costs[row0 - 1][column - 1] - u[row0] - v[column]
                if current < minv[column]:
                    minv[column] = current
                    way[column] = column0
                if minv[column] < delta:
                    delta = minv[column]
                    column1 = column
            for column in range(size + 1):
                if used[column]:
                    u[p[column]] += delta
                    v[column] -= delta
                else:
                    minv[column] -= delta
            column0 = column1
            if p[column0] == 0:
                break
        while True:
            column1 = way[column0]
            p[column0] = p[column1]
            column0 = column1
            if column0 == 0:
                break
    return sorted((p[column] - 1, column - 1) for column in range(1, size + 1))


def _aligned_entry_diffs(
    gemini: dict[str, Any], openai: dict[str, Any], alignment: dict[str, Any]
) -> list[dict[str, Any]]:
    left = canonicalize_entry(gemini)
    right = canonicalize_entry(openai)
    diffs: list[dict[str, Any]] = []

    def add(class_name: str, field: str, left_value: Any, right_value: Any) -> None:
        diffs.append(
            {
                "class": class_name,
                "gemini_entry_id": gemini.get("entry_id"),
                "openai_entry_id": openai.get("entry_id"),
                "field": field,
                "minimal_difference": {"gemini": left_value, "openai": right_value},
                "gemini": copy.deepcopy(gemini),
                "openai": copy.deepcopy(openai),
                "canonical": {"gemini": left, "openai": right},
                "alignment": copy.deepcopy(alignment),
            }
        )

    if left["row_label_text_canonical"] != right["row_label_text_canonical"]:
        add(
            "row_label_text_mismatch",
            "row_label_text",
            gemini.get("row_label_text"),
            openai.get("row_label_text"),
        )
    if left["column_header_path_canonical"] != right["column_header_path_canonical"]:
        class_name = (
            "column_header_path_mismatch"
            if len(left["column_header_path_canonical"])
            != len(right["column_header_path_canonical"])
            else "column_header_text_mismatch"
        )
        add(
            class_name,
            "column_header_path",
            gemini.get("column_header_path"),
            openai.get("column_header_path"),
        )
    if gemini.get("cell_state") != openai.get("cell_state"):
        states = {gemini.get("cell_state"), openai.get("cell_state")}
        class_name = (
            "empty_vs_value_mismatch"
            if "empty" in states and "value" in states
            else "unreadable_vs_value_mismatch"
            if "unreadable" in states and "value" in states
            else "visible_value_text_mismatch"
        )
        add(class_name, "cell_state", gemini.get("cell_state"), openai.get("cell_state"))
    raw_value_differs = gemini.get("visible_value_text") != openai.get(
        "visible_value_text"
    )
    canonical_value_differs = (
        left["visible_value_text_canonical"] != right["visible_value_text_canonical"]
    )
    if canonical_value_differs:
        if (
            left["parsed_numeric_value"] is not None
            and right["parsed_numeric_value"] is not None
            and left["parsed_numeric_value"] == right["parsed_numeric_value"]
        ):
            add(
                "decimal_or_thousands_separator_mismatch",
                "visible_value_text",
                gemini.get("visible_value_text"),
                openai.get("visible_value_text"),
            )
        else:
            add(
                "visible_value_text_mismatch",
                "visible_value_text",
                gemini.get("visible_value_text"),
                openai.get("visible_value_text"),
            )
    elif raw_value_differs:
        add(
            "raw_format_only_difference",
            "visible_value_text",
            gemini.get("visible_value_text"),
            openai.get("visible_value_text"),
        )
    if left["parsed_numeric_value"] != right["parsed_numeric_value"] and (
        left["parsed_numeric_value"] is not None
        or right["parsed_numeric_value"] is not None
    ):
        add(
            "parsed_numeric_value_mismatch",
            "parsed_numeric_value",
            left["parsed_numeric_value"],
            right["parsed_numeric_value"],
        )
    if left["parsed_sign"] != right["parsed_sign"] and {
        left["parsed_sign"],
        right["parsed_sign"],
    } <= {"positive", "negative", "zero"}:
        add(
            "sign_mismatch",
            "parsed_sign",
            left["parsed_sign"],
            right["parsed_sign"],
        )
    if not _entry_regions_compatible(left, right):
        add(
            "source_bbox_material_mismatch",
            "source_bboxes",
            {
                "row": gemini.get("row_label_bbox"),
                "header": gemini.get("header_bboxes"),
                "value": gemini.get("value_bbox"),
            },
            {
                "row": openai.get("row_label_bbox"),
                "header": openai.get("header_bboxes"),
                "value": openai.get("value_bbox"),
            },
        )
    return diffs


def _missing_diff(
    class_name: str,
    *,
    gemini: dict[str, Any] | None,
    openai: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "class": class_name,
        "gemini_entry_id": gemini.get("entry_id") if gemini else None,
        "openai_entry_id": openai.get("entry_id") if openai else None,
        "minimal_difference": "entry_present_vs_missing",
        "gemini": copy.deepcopy(gemini),
        "openai": copy.deepcopy(openai),
        "canonical": {
            "gemini": canonicalize_entry(gemini) if gemini else None,
            "openai": canonicalize_entry(openai) if openai else None,
        },
    }


def _entry_regions_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if bbox_iou(left["value_bbox"], right["value_bbox"]) < 0.1 and not _centers_compatible(
        left["value_bbox"], right["value_bbox"]
    ):
        return False
    if bbox_iou(left["row_label_bbox"], right["row_label_bbox"]) < 0.1 and not _centers_compatible(
        left["row_label_bbox"], right["row_label_bbox"]
    ):
        return False
    return _header_region_score(left["header_bboxes"], right["header_bboxes"]) >= 0.1


def _header_region_score(left: list[list[float]], right: list[list[float]]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    scores = [bbox_iou(a, b) for a in left for b in right]
    compatible_centers = any(_centers_compatible(a, b) for a in left for b in right)
    return max(max(scores, default=0.0), 0.75 if compatible_centers else 0.0)


def _centers_compatible(left: list[float], right: list[float]) -> bool:
    left_center = ((left[0] + left[2]) / 2, (left[1] + left[3]) / 2)
    right_center = ((right[0] + right[2]) / 2, (right[1] + right[3]) / 2)
    left_height = left[3] - left[1]
    right_height = right[3] - right[1]
    left_width = left[2] - left[0]
    right_width = right[2] - right[0]
    return (
        abs(left_center[0] - right_center[0]) <= max(left_width, right_width) * 0.75
        and abs(left_center[1] - right_center[1])
        <= max(left_height, right_height) * 0.75
    )


def _text_similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return SequenceMatcher(a=left.casefold(), b=right.casefold(), autojunk=False).ratio()


def _bbox_intersection_area(left: list[float], right: list[float]) -> float:
    return max(0.0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0.0, min(left[3], right[3]) - max(left[1], right[1])
    )


def _compare_schema_nodes(
    canonical: Any,
    adapted: Any,
    *,
    path: str,
    removed: list[str],
    transformed: list[str],
    weakened: list[str],
) -> None:
    if not isinstance(canonical, dict) or not isinstance(adapted, dict):
        if canonical != adapted:
            transformed.append(path)
        return
    for key, value in canonical.items():
        child_path = f"{path}.{key}"
        if key not in adapted:
            removed.append(child_path)
            if key in {"required", "enum", "type", "additionalProperties"}:
                weakened.append(child_path)
            continue
        _compare_schema_nodes(
            value,
            adapted[key],
            path=child_path,
            removed=removed,
            transformed=transformed,
            weakened=weakened,
        )
    for key in adapted:
        if key not in canonical:
            transformed.append(f"{path}.{key}:added")


def _required_paths(schema: Any, path: str = "$") -> dict[str, tuple[str, ...]]:
    found: dict[str, tuple[str, ...]] = {}
    if not isinstance(schema, dict):
        return found
    required = schema.get("required")
    if isinstance(required, list):
        found[path] = tuple(sorted(str(item) for item in required))
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for key, child in properties.items():
            found.update(_required_paths(child, f"{path}.properties.{key}"))
    items = schema.get("items")
    if isinstance(items, dict):
        found.update(_required_paths(items, f"{path}.items"))
    return found


def _enum_paths(schema: Any, path: str = "$") -> dict[str, tuple[Any, ...]]:
    found: dict[str, tuple[Any, ...]] = {}
    if not isinstance(schema, dict):
        return found
    if isinstance(schema.get("enum"), list):
        found[path] = tuple(schema["enum"])
    for key in ("properties",):
        children = schema.get(key)
        if isinstance(children, dict):
            for name, child in children.items():
                found.update(_enum_paths(child, f"{path}.{key}.{name}"))
    if isinstance(schema.get("items"), dict):
        found.update(_enum_paths(schema["items"], f"{path}.items"))
    return found


def _nullable_paths(schema: Any, path: str = "$") -> dict[str, bool]:
    found: dict[str, bool] = {}
    if not isinstance(schema, dict):
        return found
    schema_type = schema.get("type")
    found[path] = schema_type == "null" or (
        isinstance(schema_type, list) and "null" in schema_type
    )
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, child in properties.items():
            found.update(_nullable_paths(child, f"{path}.properties.{name}"))
    if isinstance(schema.get("items"), dict):
        found.update(_nullable_paths(schema["items"], f"{path}.items"))
    return found


def _closed_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _identifier_schema() -> dict[str, Any]:
    return {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"}


def _sha256_schema() -> dict[str, Any]:
    return {"type": "string", "pattern": r"^[0-9a-f]{64}$"}


def _bbox_schema() -> dict[str, Any]:
    return {
        "type": "array",
        "description": (
            "Normalized [x0, y0, x1, y1] = [left, top, right, bottom]; "
            "x coordinates are horizontal and y coordinates are vertical. "
            "Never [top, left, bottom, right]."
        ),
        "items": {"type": "number", "minimum": 0, "maximum": 1},
        "minItems": 4,
        "maxItems": 4,
    }


def _string_array_schema(*, max_items: int, max_length: int) -> dict[str, Any]:
    return {
        "type": "array",
        "items": {"type": "string", "maxLength": max_length},
        "minItems": 0,
        "maxItems": max_items,
    }


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value)
    )


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))


def _string_list(value: Any, *, max_items: int) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= max_items
        and all(isinstance(item, str) for item in value)
    )


def dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def unique_strings(values: Iterable[Any]) -> list[str]:
    return sorted({str(value) for value in values if value is not None})
