from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from typing import Any

from .semantic_visual_table_validator import (
    validate_semantic_visual_table_response,
)


SEMANTIC_THREE_TABLE_SCORE_SCHEMA = (
    "broker_reports_semantic_three_table_score_v1_private"
)
SEMANTIC_THREE_TABLE_GATE_SCHEMA = (
    "broker_reports_semantic_three_table_gate_v1_safe"
)
SEMANTIC_THREE_TABLE_REFERENCE_SCHEMA = (
    "broker_reports_semantic_three_table_source_reference_v1_private"
)
SEMANTIC_THREE_TABLE_GATE_SCOPE = "six_gemini_master_executions"

FACTORY_REQUIRED = (
    "Goal 4 live execution must use PdfDualVlmRuntimeFactory.create_for_openwebui; "
    "this module only scores preserved semantic responses"
)
FORBIDDEN = (
    "The scorer must not repair provider output, use provider consensus as truth, "
    "or score spans, physical grid coverage, bounding boxes or geometry"
)

_AMOUNT_RE = re.compile(
    r"^\(?[+-]?(?:\p{Sc}\s*)?\d[\d\s,.]*(?:%|\))?$"
    .replace(r"\p{Sc}", r"[$€£¥₽]")
)
_MARKER_RE = re.compile(r"^[$€£¥₽%]$")


class SemanticThreeTableHypothesisError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def validate_source_reference(value: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(value, dict):
        raise SemanticThreeTableHypothesisError(
            "semantic_three_table_reference_not_object"
        )
    if (
        value.get("schema_version") != SEMANTIC_THREE_TABLE_REFERENCE_SCHEMA
        or value.get("source_only") is not True
        or value.get("provider_outputs_used") is not False
        or value.get("provider_agreement_used") is not False
        or value.get("customer_acceptance_claimed") is not False
    ):
        errors.append("semantic_three_table_reference_authority_invalid")
    tables = value.get("tables")
    if not isinstance(tables, list) or len(tables) != 3:
        errors.append("semantic_three_table_reference_table_count_invalid")
        tables = []
    table_ids: list[str] = []
    crop_hashes: list[str] = []
    for table_index, table in enumerate(tables):
        if not isinstance(table, dict):
            errors.append(f"semantic_three_table_reference_{table_index}_invalid")
            continue
        table_id = table.get("table_id")
        crop_sha256 = table.get("crop_sha256")
        if not _nonempty_string(table_id) or not _sha256(crop_sha256):
            errors.append(
                f"semantic_three_table_reference_{table_index}_identity_invalid"
            )
        else:
            table_ids.append(table_id)
            crop_hashes.append(crop_sha256)
        rows = table.get("rows")
        if not isinstance(rows, list) or not rows:
            errors.append(f"semantic_three_table_reference_{table_index}_rows_invalid")
            continue
        for row_index, row in enumerate(rows):
            errors.extend(_reference_row_errors(row, table_index, row_index))
    if len(set(table_ids)) != len(table_ids) or len(set(crop_hashes)) != len(
        crop_hashes
    ):
        errors.append("semantic_three_table_reference_identity_collision")
    if errors:
        raise SemanticThreeTableHypothesisError(sorted(set(errors))[0])
    return copy.deepcopy(value)


def score_semantic_response(
    reference_table: dict[str, Any],
    response: Any,
    *,
    raw_json_text: str | None,
) -> dict[str, Any]:
    """Score literal semantic content without normalizing or repairing it."""

    expected_rows = _reference_material_rows(reference_table)
    expected = _role_counters(reference_table)
    validation = validate_semantic_visual_table_response(
        response,
        raw_json_text=raw_json_text,
        require_raw_json=True,
    )
    contract_passed = validation["semantic_response_contract_passed"] is True
    observed_rows = _response_material_rows(response) if contract_passed else []
    scored_rows = _diagnostic_literal_tokens(observed_rows)
    observed = _classify_observed(scored_rows, expected)

    label_metric = _counter_metric(expected["labels"], observed["labels"])
    amount_metric = _counter_metric(expected["amounts"], observed["amounts"])
    marker_metric = _affix_metric(expected, observed)
    binding_metric = _binding_metric(reference_table, scored_rows, expected)
    expected_label_order = _reference_label_order(reference_table)
    observed_label_order = observed["label_order"]
    row_order_matches = _lcs_length(expected_label_order, observed_label_order)
    row_order_total = len(expected_label_order)
    row_order_rate = _rate(row_order_matches, row_order_total)

    score = {
        "schema_version": SEMANTIC_THREE_TABLE_SCORE_SCHEMA,
        "table_id": reference_table.get("table_id"),
        "crop_sha256": reference_table.get("crop_sha256"),
        "json_parse_success": contract_passed,
        "semantic_schema_valid": contract_passed,
        "validator_error_codes": copy.deepcopy(validation["error_codes"]),
        "label_completeness": label_metric,
        "amount_fidelity": amount_metric,
        "currency_sign_parenthesis_fidelity": marker_metric,
        "row_value_binding": binding_metric,
        "row_order": {
            "matches": row_order_matches,
            "opportunities": row_order_total,
            "rate": row_order_rate,
            "exact": expected_label_order == observed_label_order,
        },
        "hallucinated_labels": _expanded(observed["hallucinated_labels"]),
        "hallucinated_amounts": _expanded(observed["hallucinated_amounts"]),
        "hallucinated_markers": _expanded(observed["hallucinated_markers"]),
        "unexpected_empty_string_count": observed["unexpected_empty_string_count"],
        "missing_labels": label_metric["missing_values"],
        "missing_amounts": amount_metric["missing_values"],
        "missing_currency_sign_parenthesis_literals": marker_metric[
            "missing_values"
        ],
        "manual_correction_count": _sequence_edit_distance(
            expected_rows, scored_rows
        ),
        "material_rows_hash": _sha256_json(observed_rows),
        "raw_response_hash": (
            hashlib.sha256(raw_json_text.encode("utf-8")).hexdigest()
            if isinstance(raw_json_text, str)
            else None
        ),
        "geometric_metrics_used": False,
        "physical_grid_coverage_scored": False,
        "provider_output_repaired": False,
        "provider_consensus_used_as_truth": False,
        "customer_acceptance_claimed": False,
    }
    score["score_hash"] = _sha256_json(score)
    return score


def compare_material_repeatability(
    response_a: Any,
    response_b: Any,
) -> dict[str, Any]:
    rows_a = _response_material_rows(response_a)
    rows_b = _response_material_rows(response_b)
    return {
        "materially_identical": rows_a == rows_b,
        "gemini_run_a_material_hash": _sha256_json(rows_a),
        "gemini_run_b_material_hash": _sha256_json(rows_b),
        "description_compared": False,
        "null_padding_compared": False,
        "physical_geometry_compared": False,
    }


def evaluate_three_table_gate(
    executions: list[dict[str, Any]],
    repeatability: list[dict[str, Any]],
) -> dict[str, Any]:
    gemini = [item for item in executions if item.get("provider") == "gemini"]
    openai = [item for item in executions if item.get("provider") == "openai"]
    crop_hashes = {
        item.get("crop_sha256")
        for item in executions
        if _sha256(item.get("crop_sha256"))
    }
    master_scores = [item.get("score") for item in gemini]
    checks = {
        "frozen_tables_exactly_three": len(crop_hashes) == 3,
        "gemini_executions_exactly_six": len(gemini) == 6,
        "openai_control_executions_exactly_three": len(openai) == 3,
        "gemini_json_parse_success_100_percent": _all_scores(
            master_scores, "json_parse_success", True
        ),
        "gemini_label_completeness_100_percent": _all_metric_rates(
            master_scores, "label_completeness"
        ),
        "gemini_amount_fidelity_100_percent": _all_metric_rates(
            master_scores, "amount_fidelity"
        ),
        "gemini_currency_sign_parenthesis_fidelity_100_percent": (
            _all_metric_rates(
                master_scores, "currency_sign_parenthesis_fidelity"
            )
        ),
        "gemini_row_value_binding_100_percent": _all_metric_rates(
            master_scores, "row_value_binding"
        ),
        "gemini_hallucinated_labels_zero": _all_empty(
            master_scores, "hallucinated_labels"
        ),
        "gemini_hallucinated_amounts_zero": _all_empty(
            master_scores, "hallucinated_amounts"
        ),
        "gemini_hallucinated_markers_zero": _all_empty(
            master_scores, "hallucinated_markers"
        ),
        "gemini_unexpected_empty_strings_zero": all(
            isinstance(score, dict)
            and score.get("unexpected_empty_string_count") == 0
            for score in master_scores
        ),
        "gemini_material_repeatability_passed": (
            len(repeatability) == 3
            and all(item.get("materially_identical") is True for item in repeatability)
        ),
        "geometric_failures_as_metric_zero": all(
            isinstance(score, dict)
            and score.get("geometric_metrics_used") is False
            for score in master_scores
        ),
    }
    passed = bool(checks) and all(checks.values())
    gate = {
        "schema_version": SEMANTIC_THREE_TABLE_GATE_SCHEMA,
        "status": "COMPLETED" if passed else "NOT_CLOSED",
        "gate_scope": SEMANTIC_THREE_TABLE_GATE_SCOPE,
        "openai_control_is_non_authoritative": True,
        "checks": checks,
        "failed_invariants": [key for key, value in checks.items() if not value],
        "provider_merge_performed": False,
        "provider_repair_performed": False,
        "prompt_tuned_on_frozen_tables": False,
        "geometric_metrics_used": False,
    }
    gate["gate_hash"] = _sha256_json(gate)
    return gate


def public_score_summary(score: dict[str, Any]) -> dict[str, Any]:
    """Remove literal values while retaining measured counts and rates."""

    return {
        "table_id": score.get("table_id"),
        "crop_sha256": score.get("crop_sha256"),
        "json_parse_success": score.get("json_parse_success"),
        "semantic_schema_valid": score.get("semantic_schema_valid"),
        "validator_error_codes": copy.deepcopy(score.get("validator_error_codes")),
        "label_completeness": _public_metric(score.get("label_completeness")),
        "amount_fidelity": _public_metric(score.get("amount_fidelity")),
        "currency_sign_parenthesis_fidelity": _public_metric(
            score.get("currency_sign_parenthesis_fidelity")
        ),
        "row_value_binding": _public_metric(score.get("row_value_binding")),
        "row_order": copy.deepcopy(score.get("row_order")),
        "hallucinated_label_count": len(score.get("hallucinated_labels") or []),
        "hallucinated_amount_count": len(score.get("hallucinated_amounts") or []),
        "hallucinated_marker_count": len(score.get("hallucinated_markers") or []),
        "unexpected_empty_string_count": score.get(
            "unexpected_empty_string_count"
        ),
        "manual_correction_count": score.get("manual_correction_count"),
        "material_rows_hash": score.get("material_rows_hash"),
        "raw_response_hash": score.get("raw_response_hash"),
        "geometric_metrics_used": score.get("geometric_metrics_used"),
        "score_hash": score.get("score_hash"),
    }


def _reference_row_errors(row: Any, table_index: int, row_index: int) -> list[str]:
    prefix = f"semantic_three_table_reference_{table_index}_{row_index}"
    if not isinstance(row, dict) or set(row) != {
        "cells",
        "labels",
        "amounts",
        "markers",
    }:
        return [f"{prefix}_fields_invalid"]
    cells = row.get("cells")
    if (
        not isinstance(cells, list)
        or not cells
        or any(cell is not None and not _nonempty_string(cell) for cell in cells)
    ):
        return [f"{prefix}_cells_invalid"]
    roles: list[str] = []
    for key in ("labels", "amounts", "markers"):
        values = row.get(key)
        if not isinstance(values, list) or any(
            not _nonempty_string(value) for value in values
        ):
            return [f"{prefix}_{key}_invalid"]
        roles.extend(values)
    visible = [cell for cell in cells if cell is not None]
    if Counter(roles) != Counter(visible):
        return [f"{prefix}_role_accounting_invalid"]
    return []


def _reference_material_rows(table: dict[str, Any]) -> list[list[str]]:
    return [
        [cell for cell in row["cells"] if cell is not None]
        for row in table["rows"]
    ]


def _response_material_rows(response: Any) -> list[list[str]]:
    if not isinstance(response, dict) or not isinstance(response.get("rows"), list):
        return []
    result: list[list[str]] = []
    for row in response["rows"]:
        if not isinstance(row, list):
            return []
        material: list[str] = []
        for cell in row:
            if cell is None:
                continue
            if not isinstance(cell, str):
                return []
            material.append(cell)
        result.append(material)
    return result


def _role_counters(table: dict[str, Any]) -> dict[str, Counter[str]]:
    return {
        key: Counter(
            value
            for row in table["rows"]
            for value in row[key]
        )
        for key in ("labels", "amounts", "markers")
    }


def _classify_observed(
    rows: list[list[str]], expected: dict[str, Counter[str]]
) -> dict[str, Any]:
    labels: Counter[str] = Counter()
    amounts: Counter[str] = Counter()
    markers: Counter[str] = Counter()
    hallucinated_labels: Counter[str] = Counter()
    hallucinated_amounts: Counter[str] = Counter()
    hallucinated_markers: Counter[str] = Counter()
    unexpected_empty_string_count = 0
    label_order: list[str] = []
    for row in rows:
        for token in row:
            if token == "":
                unexpected_empty_string_count += 1
            elif token in expected["labels"]:
                labels[token] += 1
                label_order.append(token)
            elif token in expected["amounts"]:
                amounts[token] += 1
            elif token in expected["markers"]:
                markers[token] += 1
            elif _MARKER_RE.fullmatch(token):
                hallucinated_markers[token] += 1
            elif _AMOUNT_RE.fullmatch(token):
                hallucinated_amounts[token] += 1
            else:
                hallucinated_labels[token] += 1
                label_order.append(token)
    return {
        "labels": labels,
        "amounts": amounts,
        "markers": markers,
        "hallucinated_labels": hallucinated_labels,
        "hallucinated_amounts": hallucinated_amounts,
        "hallucinated_markers": hallucinated_markers,
        "unexpected_empty_string_count": unexpected_empty_string_count,
        "label_order": label_order,
    }


def _diagnostic_literal_tokens(rows: list[list[str]]) -> list[list[str]]:
    """Tokenize a combined currency marker and amount for scoring only.

    The semantic contract asks for the minimum logical column count, so both
    ``["$", "1,000"]`` and ``["$ 1,000"]`` preserve the same two source-visible
    literals.  This projection never mutates or replaces provider evidence.
    """

    result: list[list[str]] = []
    combined = re.compile(r"^([$€£¥₽]) ([^\s].*)$")
    for row in rows:
        projected: list[str] = []
        for token in row:
            match = combined.fullmatch(token)
            if match and _AMOUNT_RE.fullmatch(match.group(2)):
                projected.extend([match.group(1), match.group(2)])
            else:
                projected.append(token)
        result.append(projected)
    return result


def _counter_metric(expected: Counter[str], observed: Counter[str]) -> dict[str, Any]:
    matches = sum((expected & observed).values())
    total = sum(expected.values())
    missing = expected - observed
    return {
        "matches": matches,
        "opportunities": total,
        "rate": _rate(matches, total),
        "missing_values": _expanded(missing),
    }


def _affix_metric(
    expected: dict[str, Counter[str]], observed: dict[str, Any]
) -> dict[str, Any]:
    expected_decorated_amounts = Counter(
        {
            amount: count
            for amount, count in expected["amounts"].items()
            if re.search(r"[()%]", amount) or re.match(r"^[+-]", amount)
        }
    )
    marker_matches = sum(
        (expected["markers"] & observed["markers"]).values()
    )
    decorated_matches = sum(
        (expected_decorated_amounts & observed["amounts"]).values()
    )
    missing = (expected["markers"] - observed["markers"]) + (
        expected_decorated_amounts - observed["amounts"]
    )
    total = sum(expected["markers"].values()) + sum(
        expected_decorated_amounts.values()
    )
    matches = marker_matches + decorated_matches
    return {
        "matches": matches,
        "opportunities": total,
        "rate": _rate(matches, total),
        "missing_values": _expanded(missing),
    }


def _binding_metric(
    table: dict[str, Any],
    observed_rows: list[list[str]],
    expected: dict[str, Counter[str]],
) -> dict[str, Any]:
    expected_bindings = []
    for row in table["rows"]:
        if row["amounts"]:
            expected_bindings.append(
                (Counter(row["labels"]), Counter(row["amounts"]))
            )
    observed_bindings = []
    for row in observed_rows:
        observed_bindings.append(
            (
                Counter(token for token in row if token in expected["labels"]),
                Counter(token for token in row if token in expected["amounts"]),
            )
        )
    remaining = list(observed_bindings)
    matches = 0
    for binding in expected_bindings:
        try:
            index = remaining.index(binding)
        except ValueError:
            continue
        matches += 1
        remaining.pop(index)
    total = len(expected_bindings)
    return {
        "matches": matches,
        "opportunities": total,
        "rate": _rate(matches, total),
        "missing_binding_count": total - matches,
    }


def _reference_label_order(table: dict[str, Any]) -> list[str]:
    return [value for row in table["rows"] for value in row["labels"]]


def _sequence_edit_distance(left: list[list[str]], right: list[list[str]]) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_row in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_row in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_row != right_row),
                )
            )
        previous = current
    return previous[-1]


def _lcs_length(left: list[str], right: list[str]) -> int:
    previous = [0] * (len(right) + 1)
    for left_value in left:
        current = [0]
        for index, right_value in enumerate(right, start=1):
            current.append(
                previous[index - 1] + 1
                if left_value == right_value
                else max(previous[index], current[-1])
            )
        previous = current
    return previous[-1]


def _expanded(values: Counter[str]) -> list[str]:
    return sorted(values.elements())


def _rate(matches: int, total: int) -> float:
    return round(matches / total, 9) if total else 1.0


def _all_scores(scores: list[Any], key: str, expected: Any) -> bool:
    return len(scores) == 6 and all(
        isinstance(score, dict) and score.get(key) is expected for score in scores
    )


def _all_metric_rates(scores: list[Any], key: str) -> bool:
    return len(scores) == 6 and all(
        isinstance(score, dict)
        and isinstance(score.get(key), dict)
        and score[key].get("rate") == 1.0
        for score in scores
    )


def _all_empty(scores: list[Any], key: str) -> bool:
    return len(scores) == 6 and all(
        isinstance(score, dict) and score.get(key) == [] for score in scores
    )


def _public_metric(value: Any) -> dict[str, Any]:
    metric = value if isinstance(value, dict) else {}
    return {
        "matches": metric.get("matches"),
        "opportunities": metric.get("opportunities"),
        "rate": metric.get("rate"),
        **(
            {"missing_binding_count": metric.get("missing_binding_count")}
            if "missing_binding_count" in metric
            else {}
        ),
    }


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
