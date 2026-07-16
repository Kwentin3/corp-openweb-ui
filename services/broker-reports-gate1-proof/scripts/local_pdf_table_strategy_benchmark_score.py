#!/usr/bin/env python3
"""Score a sealed PDF table-strategy benchmark terminal.

The terminal and its seal are read and verified before the human reference is
opened.  Scoring is deliberately reference-only and never changes the sealed
strategy outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pdf_table_strategy_benchmark_contracts import (  # noqa: E402
    validate_detection_output,
    validate_evidence_overlay,
    validate_unified_extraction,
)


TERMINAL_SCHEMA = "broker_reports_pdf_table_strategy_benchmark_terminal_v1"
SEAL_SCHEMA = "broker_reports_pdf_table_strategy_benchmark_terminal_seal_v1"
REFERENCE_SCHEMA = "broker_reports_pdf_table_strategy_benchmark_reference_v1"
SCORE_SCHEMA = "broker_reports_pdf_table_strategy_benchmark_score_v1"
EVIDENCE_SCHEMA = "broker_reports_pdf_table_strategy_evidence_v1"

STRATEGIES = ("A", "B", "C")
SUCCESS_STATUSES = {
    "accepted",
    "completed",
    "passed",
    "replayed",
    "succeeded",
    "success",
    "validated",
}
ALLOWED_CONCLUSIONS = {
    "STRATEGY_A_DIRECT_VLM_PREFERRED",
    "STRATEGY_B_TWO_STEP_VLM_PREFERRED",
    "STRATEGY_C_HYBRID_EVIDENCE_PREFERRED",
    "HYBRID_ONLY_FOR_HIGH_RISK_DOCUMENTS",
    "CURRENT_APPROACH_NOT_JUSTIFIED",
}
FAILURE_CONCLUSION = "CURRENT_APPROACH_NOT_JUSTIFIED"

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_INTEGER_SUFFIX = re.compile(r"(?:^|[^0-9])(\d+)$")
_NUMERIC = re.compile(r"^[+\-−–—]?\(?\d[\d\s.,%]*\)?$")
_LEADING_CURRENCY_SYMBOL = re.compile(r"^([$\u20ac£¥₽₴₸₹₩₪])\s*(.+)$")


class ScoreError(RuntimeError):
    """Known fail-closed scoring error with reference-boundary context."""

    def __init__(
        self,
        code: str,
        *,
        terminal_sha256: str | None = None,
        terminal_verified: bool = False,
        reference_accessed: bool = False,
    ) -> None:
        self.code = code
        self.terminal_sha256 = terminal_sha256
        self.terminal_verified = terminal_verified
        self.reference_accessed = reference_accessed
        super().__init__(code)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal", required=True)
    parser.add_argument("--seal", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    try:
        result = score_paths(
            terminal_path=Path(args.terminal).resolve(),
            seal_path=Path(args.seal).resolve(),
            reference_path=Path(args.reference).resolve(),
        )
    except ScoreError as exc:
        result = _failed_score(
            exc.code,
            terminal_sha256=exc.terminal_sha256,
            terminal_verified=exc.terminal_verified,
            reference_accessed=exc.reference_accessed,
        )
    except OSError:
        result = _failed_score("benchmark_terminal_or_seal_file_unavailable")
    except Exception:
        # The CLI contract still requires a durable failure artifact.  Known
        # input failures are attributed above and must not be collapsed here.
        result = _failed_score("benchmark_scorer_internal_failure")

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_canonical_json_bytes(result))
    print(str(result["conclusion"]))
    return 0 if result.get("scoring_status") == "completed" else 1


def score_paths(
    *,
    terminal_path: Path,
    seal_path: Path,
    reference_path: Path,
) -> dict[str, Any]:
    """Verify a terminal, then open and score its independent reference."""

    try:
        terminal_bytes = terminal_path.read_bytes()
        seal_bytes = seal_path.read_bytes()
    except OSError as exc:
        raise ScoreError("benchmark_terminal_or_seal_file_unavailable") from exc

    terminal_digest = hashlib.sha256(terminal_bytes).hexdigest()
    terminal = _verified_terminal(
        terminal_bytes,
        seal_bytes,
        terminal_sha256=terminal_digest,
    )
    try:
        threshold = _detection_iou_threshold(terminal)
    except ScoreError as exc:
        raise ScoreError(
            exc.code,
            terminal_sha256=terminal_digest,
            terminal_verified=True,
            reference_accessed=False,
        ) from exc
    strategy_contract_errors = _prevalidate_strategy_outputs(terminal)

    # Reference access starts only after terminal bytes, seal, schemas, scope,
    # and the frozen scoring threshold have all passed verification.
    try:
        reference_bytes = reference_path.read_bytes()
    except OSError as exc:
        raise ScoreError(
            "benchmark_reference_file_unavailable",
            terminal_sha256=terminal_digest,
            terminal_verified=True,
            reference_accessed=True,
        ) from exc
    try:
        reference = _strict_json_loads(reference_bytes, "benchmark_reference_json_invalid")
    except ScoreError as exc:
        raise ScoreError(
            exc.code,
            terminal_sha256=terminal_digest,
            terminal_verified=True,
            reference_accessed=True,
        ) from exc

    try:
        _validate_reference(
            reference,
            terminal=terminal,
            terminal_sha256=terminal_digest,
        )
    except ScoreError as exc:
        raise ScoreError(
            exc.code,
            terminal_sha256=terminal_digest,
            terminal_verified=True,
            reference_accessed=True,
        ) from exc

    failed_contracts: list[dict[str, Any]] = []
    strategy_results = _score_strategies(
        terminal=terminal,
        reference=reference,
        iou_threshold=threshold,
        failed_contracts=failed_contracts,
        strategy_contract_errors=strategy_contract_errors,
    )
    conclusion, recommendation_trace = _recommend(strategy_results)
    if conclusion not in ALLOWED_CONCLUSIONS:
        raise ScoreError(
            "benchmark_recommendation_outside_allowed_enum",
            terminal_sha256=terminal_digest,
            terminal_verified=True,
            reference_accessed=True,
        )

    # The same immutable terminal and seal must still exist after scoring.
    try:
        terminal_bytes_after = terminal_path.read_bytes()
        seal_bytes_after = seal_path.read_bytes()
    except OSError as exc:
        raise ScoreError(
            "benchmark_terminal_changed_during_scoring",
            terminal_sha256=terminal_digest,
            terminal_verified=True,
            reference_accessed=True,
        ) from exc
    if terminal_bytes_after != terminal_bytes or seal_bytes_after != seal_bytes:
        raise ScoreError(
            "benchmark_terminal_changed_during_scoring",
            terminal_sha256=terminal_digest,
            terminal_verified=True,
            reference_accessed=True,
        )
    _verified_terminal(
        terminal_bytes_after,
        seal_bytes_after,
        terminal_sha256=terminal_digest,
    )

    reference_digest = hashlib.sha256(reference_bytes).hexdigest()
    result: dict[str, Any] = {
        "schema_version": SCORE_SCHEMA,
        "scoring_status": "completed",
        "conclusion": conclusion,
        "terminal_sha256": terminal_digest,
        "reference_sha256": reference_digest,
        "manifest_sha256": terminal.get("manifest_sha256"),
        "terminal_verified_before_reference_access": True,
        "reference_accessed_after_terminal_verification": True,
        "terminal_unchanged_during_scoring": True,
        "reference_human_reviewed": _reference_human_reviewed(reference),
        "provisional": not _reference_human_reviewed(reference),
        "scoring_policy": {
            "detection_matching": (
                "maximum_cardinality_then_maximum_iou_one_to_one_within_case"
            ),
            "detection_iou_threshold": threshold,
            "failed_or_malformed_strategy_output": "score_as_empty_prediction",
            "cell_text_normalization": "unicode_nfkc_plus_whitespace_collapse",
            "numeric_tolerance": "none",
            "physical_and_semantic_scores_separate": True,
            "currency_symbol_implies_iso_code": False,
            "evidence_authenticity_and_structural_accuracy_separate": True,
            "weighted_total": False,
            "recommendation_order": [
                "safety",
                "accuracy",
                "provenance",
                "frozen_complexity",
            ],
            "frozen_complexity": _complexity_policy(),
        },
        "strategies": strategy_results,
        "recommendation_trace": recommendation_trace,
        "failed_contracts": _deduplicate_dicts(failed_contracts),
    }
    result["score_checksum"] = _sha256_json(result)
    return result


def _verified_terminal(
    terminal_bytes: bytes,
    seal_bytes: bytes,
    *,
    terminal_sha256: str,
) -> dict[str, Any]:
    try:
        seal = _strict_json_loads(seal_bytes, "benchmark_terminal_seal_json_invalid")
    except ScoreError as exc:
        raise ScoreError(exc.code, terminal_sha256=terminal_sha256) from exc
    if not isinstance(seal, dict) or seal.get("schema_version") != SEAL_SCHEMA:
        raise ScoreError(
            "benchmark_terminal_seal_schema_invalid",
            terminal_sha256=terminal_sha256,
        )
    if (
        seal.get("terminal_sha256") != terminal_sha256
        or seal.get("terminal_size_bytes") != len(terminal_bytes)
    ):
        raise ScoreError(
            "benchmark_terminal_seal_checksum_mismatch",
            terminal_sha256=terminal_sha256,
        )
    try:
        terminal = _strict_json_loads(
            terminal_bytes,
            "benchmark_terminal_json_invalid",
        )
    except ScoreError as exc:
        raise ScoreError(exc.code, terminal_sha256=terminal_sha256) from exc
    if not isinstance(terminal, dict) or terminal.get("schema_version") != TERMINAL_SCHEMA:
        raise ScoreError(
            "benchmark_terminal_schema_invalid",
            terminal_sha256=terminal_sha256,
        )
    if not _is_sha256(terminal.get("manifest_sha256")):
        raise ScoreError(
            "benchmark_terminal_manifest_identity_invalid",
            terminal_sha256=terminal_sha256,
        )
    target_manifest = terminal.get("target_manifest")
    if not isinstance(target_manifest, dict):
        raise ScoreError(
            "benchmark_terminal_target_manifest_missing",
            terminal_sha256=terminal_sha256,
        )
    if _sha256_json(target_manifest) != terminal.get("manifest_sha256"):
        raise ScoreError(
            "benchmark_terminal_manifest_checksum_mismatch",
            terminal_sha256=terminal_sha256,
        )
    prompt_contracts = terminal.get("prompt_contracts")
    if not isinstance(prompt_contracts, dict) or set(prompt_contracts) != {
        "A",
        "B_detection",
        "B_extraction",
    }:
        raise ScoreError(
            "benchmark_terminal_prompt_contracts_invalid",
            terminal_sha256=terminal_sha256,
        )
    for contract in prompt_contracts.values():
        if (
            not isinstance(contract, dict)
            or not isinstance(contract.get("version"), str)
            or not contract.get("version")
            or not _is_sha256(contract.get("model_view_sha256"))
            or not _is_sha256(contract.get("output_schema_sha256"))
        ):
            raise ScoreError(
                "benchmark_terminal_prompt_contracts_invalid",
                terminal_sha256=terminal_sha256,
            )
    if not isinstance(terminal.get("provider_qualification"), (dict, list)):
        raise ScoreError(
            "benchmark_terminal_provider_qualification_invalid",
            terminal_sha256=terminal_sha256,
        )
    _validate_terminal_hard_constraints(
        terminal,
        terminal_sha256=terminal_sha256,
    )
    cases = terminal.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ScoreError(
            "benchmark_terminal_cases_invalid",
            terminal_sha256=terminal_sha256,
        )
    case_ids: list[str] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ScoreError(
                "benchmark_terminal_case_shape_invalid",
                terminal_sha256=terminal_sha256,
            )
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ScoreError(
                "benchmark_terminal_case_identity_invalid",
                terminal_sha256=terminal_sha256,
            )
        case_ids.append(case_id)
        if not _valid_bbox(case.get("page_bbox")):
            raise ScoreError(
                "benchmark_terminal_page_bbox_invalid",
                terminal_sha256=terminal_sha256,
            )
        strategies = case.get("strategies")
        if not isinstance(strategies, dict) or any(
            not isinstance(strategies.get(strategy), dict) for strategy in STRATEGIES
        ):
            raise ScoreError(
                "benchmark_terminal_strategy_set_invalid",
                terminal_sha256=terminal_sha256,
            )
    if len(case_ids) != len(set(case_ids)):
        raise ScoreError(
            "benchmark_terminal_case_identity_duplicate",
            terminal_sha256=terminal_sha256,
        )
    return terminal


def _detection_iou_threshold(terminal: dict[str, Any]) -> float:
    manifest = _object(terminal.get("target_manifest"))
    policy = _object(manifest.get("scoring_policy"))
    value = policy.get("detection_iou_threshold")
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(float(value))
        or not 0.0 < float(value) <= 1.0
    ):
        raise ScoreError(
            "benchmark_scoring_iou_threshold_missing_or_invalid",
            terminal_sha256=None,
            terminal_verified=True,
            reference_accessed=False,
        )
    return float(value)


def _validate_terminal_hard_constraints(
    terminal: dict[str, Any],
    *,
    terminal_sha256: str,
) -> None:
    for key in (
        "reference_accessed",
        "production_authority",
        "production_pipeline_changed",
        "production_gate2_selection_changed",
        "ocr_performed",
        "hidden_retry",
        "provider_failover",
    ):
        if terminal.get(key) is not False:
            raise ScoreError(
                f"benchmark_terminal_{key}_invalid",
                terminal_sha256=terminal_sha256,
            )
    if isinstance(terminal.get("runner"), dict):
        if terminal.get("knowledge_or_rag_used") is not False:
            raise ScoreError(
                "benchmark_terminal_knowledge_or_rag_used_invalid",
                terminal_sha256=terminal_sha256,
            )
        _validate_parser_accounting(
            terminal.get("parser_accounting"),
            terminal_sha256=terminal_sha256,
        )
        source_revision = _object(terminal.get("source_revision"))
        if (
            source_revision.get("worktree_clean") is not True
            or not isinstance(source_revision.get("repository_commit_sha"), str)
            or _HEX_40.fullmatch(source_revision["repository_commit_sha"]) is None
        ):
            raise ScoreError(
                "benchmark_terminal_source_revision_invalid",
                terminal_sha256=terminal_sha256,
            )
    qualification = terminal.get("provider_qualification")
    if not isinstance(qualification, dict) or qualification.get("status") != "qualified":
        raise ScoreError(
            "benchmark_provider_qualification_invalid",
            terminal_sha256=terminal_sha256,
        )
    if isinstance(terminal.get("runner"), dict):
        model_id = str(
            _object(_object(terminal.get("target_manifest")).get("provider_contract")).get(
                "model_id"
            )
            or ""
        )
        if (
            any(
                qualification.get(key) is not True
                for key in (
                    "exact_model_match",
                    "image_input_supported",
                    "structured_output_supported",
                    "native_provider_transport",
                    "credentials_from_openwebui_connection",
                )
            )
            or qualification.get("hidden_retry") is not False
            or qualification.get("provider_failover") is not False
            or qualification.get("requested_model_id") != model_id
            or qualification.get("resolved_model_id") != model_id
        ):
            raise ScoreError(
                "benchmark_provider_qualification_invalid",
                terminal_sha256=terminal_sha256,
            )
    for case in terminal.get("cases") or []:
        case_id = str(_object(case).get("case_id") or "")
        strategies = _object(_object(case).get("strategies"))
        b_result = _object(strategies.get("B"))
        c_result = _object(strategies.get("C"))
        if (
            c_result.get("replayed_from_strategy") != "B"
            or _sha256_json(c_result.get("extraction"))
            != _sha256_json(b_result.get("extraction"))
        ):
            raise ScoreError(
                f"benchmark_strategy_c_replay_invalid:{case_id}",
                terminal_sha256=terminal_sha256,
            )
        if _strategy_usable(c_result):
            replay_digest = _sha256_json(c_result.get("extraction"))
            if (
                c_result.get("extraction_sha256") != replay_digest
                or c_result.get("replayed_extraction_sha256") != replay_digest
                or c_result.get("reused_operations_from_strategy") != "B"
            ):
                raise ScoreError(
                    f"benchmark_strategy_c_replay_identity_invalid:{case_id}",
                    terminal_sha256=terminal_sha256,
                )
        c_operations = c_result.get("operations")
        if c_operations != [] or c_result.get("provider_calls") != 0:
            raise ScoreError(
                f"benchmark_strategy_c_provider_budget_invalid:{case_id}",
                terminal_sha256=terminal_sha256,
            )
        for strategy in STRATEGIES:
            result = _object(strategies.get(strategy))
            operations = result.get("operations")
            if not isinstance(operations, list):
                raise ScoreError(
                    f"benchmark_strategy_operations_invalid:{case_id}:{strategy}",
                    terminal_sha256=terminal_sha256,
                )
            for operation in operations:
                if not isinstance(operation, dict):
                    raise ScoreError(
                        f"benchmark_strategy_operation_shape_invalid:{case_id}:{strategy}",
                        terminal_sha256=terminal_sha256,
                    )
                attempt = operation.get("attempt")
                if attempt is None:
                    continue
                if not isinstance(attempt, dict) or (
                    attempt.get("hidden_retry") is not False
                    or attempt.get("provider_failover") is not False
                    or attempt.get("attempt_number") != 1
                    or attempt.get("attempt_lineage") != []
                ):
                    raise ScoreError(
                        f"benchmark_provider_attempt_policy_invalid:{case_id}:{strategy}",
                        terminal_sha256=terminal_sha256,
                    )


def _validate_parser_accounting(value: Any, *, terminal_sha256: str) -> None:
    if not isinstance(value, dict) or set(value) != {
        "unique_documents",
        "total_duration_ms",
    }:
        raise ScoreError(
            "benchmark_parser_accounting_invalid",
            terminal_sha256=terminal_sha256,
        )
    documents = value.get("unique_documents")
    if not isinstance(documents, list):
        raise ScoreError(
            "benchmark_parser_accounting_invalid",
            terminal_sha256=terminal_sha256,
        )
    seen: set[str] = set()
    duration_total = 0
    for item in documents:
        if not isinstance(item, dict):
            raise ScoreError(
                "benchmark_parser_accounting_invalid",
                terminal_sha256=terminal_sha256,
            )
        digest = item.get("pdf_sha256")
        duration = item.get("duration_ms")
        if (
            not _is_sha256(digest)
            or digest in seen
            or _nonnegative(item.get("pdf_bytes")) <= 0
            or _nonnegative(item.get("pages_parsed")) <= 0
            or not isinstance(duration, int)
            or isinstance(duration, bool)
            or duration < 0
            or item.get("capability") != "layout_words"
            or item.get("table_construction_performed") is not False
        ):
            raise ScoreError(
                "benchmark_parser_accounting_invalid",
                terminal_sha256=terminal_sha256,
            )
        seen.add(str(digest))
        duration_total += duration
    if value.get("total_duration_ms") != duration_total:
        raise ScoreError(
            "benchmark_parser_accounting_total_invalid",
            terminal_sha256=terminal_sha256,
        )


def _prevalidate_strategy_outputs(
    terminal: dict[str, Any],
) -> dict[tuple[str, str], list[str]]:
    """Validate sealed strategy payloads without opening the reference."""

    invalid: dict[tuple[str, str], list[str]] = {}
    for case in terminal.get("cases") or []:
        case_id = str(_object(case).get("case_id") or "")
        strategies = _object(_object(case).get("strategies"))
        b_result = _object(strategies.get("B"))
        for strategy in STRATEGIES:
            result = _object(strategies.get(strategy))
            if not _strategy_usable(result):
                continue
            errors = list(validate_unified_extraction(result.get("extraction")))
            if strategy in {"B", "C"}:
                detection = result.get("detection", b_result.get("detection"))
                errors.extend(validate_detection_output(detection))
            if strategy == "C":
                overlay = result.get("evidence_validation")
                errors.extend(validate_evidence_overlay(overlay))
                if _object(overlay).get("extraction_sha256") != _sha256_json(
                    result.get("extraction")
                ):
                    errors.append("benchmark_evidence_extraction_binding_invalid")
            if errors:
                invalid[(case_id, strategy)] = sorted(set(errors))
    return invalid


def _validate_reference(
    value: Any,
    *,
    terminal: dict[str, Any],
    terminal_sha256: str,
) -> None:
    if not isinstance(value, dict) or value.get("schema_version") != REFERENCE_SCHEMA:
        raise ScoreError("benchmark_reference_schema_invalid")
    if value.get("manifest_sha256") not in {None, terminal.get("manifest_sha256")}:
        raise ScoreError("benchmark_reference_manifest_binding_invalid")
    if value.get("terminal_sha256") not in {None, terminal_sha256}:
        raise ScoreError("benchmark_reference_terminal_binding_invalid")
    if "reference_checksum" in value:
        unsigned = dict(value)
        stored = unsigned.pop("reference_checksum", None)
        if not isinstance(stored, str) or stored != _sha256_json(unsigned):
            raise ScoreError("benchmark_reference_checksum_invalid")
    cases = value.get("cases")
    if not isinstance(cases, list):
        raise ScoreError("benchmark_reference_cases_invalid")
    reference_ids: list[str] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ScoreError("benchmark_reference_case_shape_invalid")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id:
            raise ScoreError("benchmark_reference_case_identity_invalid")
        reference_ids.append(case_id)
        raw_tables = case.get("tables", case.get("regions"))
        if not isinstance(raw_tables, list):
            raise ScoreError("benchmark_reference_tables_invalid")
        if isinstance(case.get("expected_regions"), int) and case.get(
            "expected_regions"
        ) != len(raw_tables):
            raise ScoreError("benchmark_reference_region_count_invalid")
        for table in _reference_tables(case):
            if not isinstance(table, dict) or not _valid_bbox(_table_bbox(table)):
                raise ScoreError("benchmark_reference_table_shape_invalid")
    if len(reference_ids) != len(set(reference_ids)):
        raise ScoreError("benchmark_reference_case_identity_duplicate")
    terminal_ids = [str(item.get("case_id")) for item in terminal.get("cases") or []]
    if set(reference_ids) != set(terminal_ids):
        raise ScoreError("benchmark_terminal_reference_scope_mismatch")


def _reference_tables(case: dict[str, Any]) -> list[dict[str, Any]]:
    raw = case.get("tables", case.get("regions", []))
    if not isinstance(raw, list):
        return []
    result: list[dict[str, Any]] = []
    for source in raw:
        if not isinstance(source, dict):
            continue
        table = dict(source)
        if "bbox" not in table and "bbox_normalized" in table:
            table["bbox"] = table.get("bbox_normalized")
        if not isinstance(table.get("physical"), dict):
            table["physical"] = {
                "row_count": table.get("rows", table.get("row_count")),
                "column_count": table.get("columns", table.get("column_count")),
                "cells": table.get("cells", []),
                "spans": table.get("spans", table.get("merged_regions", [])),
            }
        if "semantic" not in table and "semantic_gold" in table:
            table["semantic"] = _normalize_semantic_gold(table.get("semantic_gold"))
        result.append(table)
    return result


def _normalize_semantic_gold(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"fields": [], "qualifiers": []}
    fields: list[dict[str, Any]] = []
    columns_by_field: dict[str, list[str]] = {}
    for ordinal, column in enumerate(_dicts(value.get("logical_columns")), start=1):
        field_id = str(column.get("logical_column_id") or f"logical_{ordinal}")
        raw_roles = column.get("roles")
        roles = [str(item) for item in raw_roles] if isinstance(raw_roles, list) else []
        role = roles[0] if roles else "unknown"
        logical_type = _gold_logical_type(field_id, role)
        raw_indices = column.get("physical_column_indices")
        physical_ids = [
            f"c{int(item)}"
            for item in raw_indices or []
            if isinstance(item, int) and not isinstance(item, bool) and item > 0
        ]
        columns_by_field[field_id] = physical_ids
        fields.append(
            {
                "field_id": field_id,
                "role": role,
                "logical_type": logical_type,
                "physical_column_ids": physical_ids,
                "header_cell_ids": [],
                "qualifier_ids": [],
                "uncertainty_codes": [],
            }
        )
    qualifiers: list[dict[str, Any]] = []
    for ordinal, qualifier in enumerate(_dicts(value.get("qualifiers")), start=1):
        scope = _object(qualifier.get("scope"))
        logical_ids = scope.get("logical_column_ids")
        target_id = (
            str(logical_ids[0])
            if isinstance(logical_ids, list) and logical_ids
            else next(
                (
                    item["field_id"]
                    for item in fields
                    if item["logical_type"] == "monetary_amount"
                ),
                "unknown",
            )
        )
        qualifier_id = f"gold_qualifier_{ordinal}"
        kind = str(qualifier.get("kind") or "unknown")
        if kind == "currency_symbol":
            kind = "currency"
        qualifiers.append(
            {
                "qualifier_id": qualifier_id,
                "kind": kind,
                "target_field_id": target_id,
                "physical_column_ids": list(columns_by_field.get(target_id, [])),
                "evidence_cell_ids": [],
                "normalized_code": qualifier.get("normalized_code"),
                "uncertainty_codes": [],
            }
        )
        for field in fields:
            if field["field_id"] == target_id:
                field["qualifier_ids"].append(qualifier_id)
    return {"fields": fields, "qualifiers": qualifiers}


def _gold_logical_type(field_id: str, role: str) -> str:
    if field_id == "monetary_amount" or role == "amount":
        return "monetary_amount"
    if role in {"description", "header"}:
        return "text" if role == "description" else "header"
    if role in {"currency", "unit", "period", "entity", "unknown"}:
        return role
    return "unknown"


def _score_strategies(
    *,
    terminal: dict[str, Any],
    reference: dict[str, Any],
    iou_threshold: float,
    failed_contracts: list[dict[str, Any]],
    strategy_contract_errors: dict[tuple[str, str], list[str]],
) -> dict[str, dict[str, Any]]:
    reference_by_case = {
        str(case.get("case_id")): case
        for case in reference.get("cases") or []
        if isinstance(case, dict)
    }
    accumulators = {strategy: _new_accumulator() for strategy in STRATEGIES}

    for terminal_case in terminal.get("cases") or []:
        case_id = str(terminal_case.get("case_id"))
        reference_case = _object(reference_by_case.get(case_id))
        reference_tables = _reference_tables(reference_case)
        page_bbox = terminal_case.get("page_bbox")
        strategies = _object(terminal_case.get("strategies"))
        b_result = _object(strategies.get("B"))

        b_extraction = b_result.get("extraction")
        c_result = _object(strategies.get("C"))
        if c_result.get("replayed_from_strategy") != "B":
            _contract_failure(
                failed_contracts,
                case_id,
                "C",
                "benchmark_strategy_c_replay_lineage_invalid",
            )
            accumulators["C"]["safety"]["malformed_outputs"] += 1
        if _sha256_json(c_result.get("extraction")) != _sha256_json(b_extraction):
            _contract_failure(
                failed_contracts,
                case_id,
                "C",
                "benchmark_strategy_c_extraction_replay_mismatch",
            )
            accumulators["C"]["safety"]["malformed_outputs"] += 1

        for strategy in STRATEGIES:
            strategy_result = _object(strategies.get(strategy))
            usable = _strategy_usable(strategy_result)
            independent_errors = strategy_contract_errors.get((case_id, strategy), [])
            if independent_errors:
                usable = False
                accumulators[strategy]["safety"]["malformed_outputs"] += 1
                for reason_code in independent_errors:
                    _contract_failure(
                        failed_contracts,
                        case_id,
                        strategy,
                        reason_code,
                    )
            extraction = strategy_result.get("extraction") if usable else None
            extraction_tables = _extraction_tables(extraction)
            if usable and extraction_tables is None:
                usable = False
                extraction_tables = []
                _contract_failure(
                    failed_contracts,
                    case_id,
                    strategy,
                    "benchmark_strategy_extraction_contract_invalid",
                )
                accumulators[strategy]["safety"]["malformed_outputs"] += 1
            if not usable:
                extraction_tables = []
                accumulators[strategy]["safety"]["failed_or_unsupported_cases"] += 1
            accepted_evidence = (
                _accepted_evidence_cells(strategy_result.get("evidence_validation"))
                if strategy == "C" and usable
                else None
            )

            detection_value = (
                _detection_for_strategy(
                    strategy=strategy,
                    strategy_result=strategy_result,
                    b_result=b_result,
                    extraction_tables=extraction_tables,
                )
                if usable
                else {}
            )
            predicted_detection = _detection_regions(
                detection_value,
                page_bbox=page_bbox,
            )
            reference_regions = [
                _canonical_bbox(_table_bbox(table), page_bbox)
                for table in reference_tables
            ]
            reference_regions = [bbox for bbox in reference_regions if bbox is not None]
            detection_match = _match_bboxes(
                reference_regions,
                predicted_detection,
                threshold=iou_threshold,
            )
            _add_detection(accumulators[strategy]["detection"], detection_match)

            extracted = list(extraction_tables or [])
            _fill_missing_extraction_bboxes(
                extracted,
                predicted_detection,
            )
            predicted_table_regions = [
                _canonical_bbox(_table_bbox(table), page_bbox) for table in extracted
            ]
            valid_predicted_indices = [
                index for index, bbox in enumerate(predicted_table_regions) if bbox is not None
            ]
            valid_predicted_boxes = [
                predicted_table_regions[index] for index in valid_predicted_indices
            ]
            extraction_match = _match_bboxes(
                reference_regions,
                valid_predicted_boxes,
                threshold=iou_threshold,
            )
            matched_tables = {
                ref_index: extracted[valid_predicted_indices[pred_index]]
                for ref_index, pred_index, _ in extraction_match["pairs"]
            }
            matched_predicted = {
                valid_predicted_indices[pred_index]
                for _, pred_index, _ in extraction_match["pairs"]
            }

            for ref_index, reference_table in enumerate(reference_tables):
                predicted_table = matched_tables.get(ref_index)
                physical = _best_physical_score(reference_table, predicted_table)
                _add_physical(accumulators[strategy]["physical"], physical)
                accepted_ids = None
                if accepted_evidence is not None and predicted_table is not None:
                    accepted_ids = accepted_evidence.get(
                        (
                            str(predicted_table.get("table_id") or ""),
                            physical.get("_predicted_alternative_id"),
                        ),
                        set(),
                    )
                _add_safety_from_physical(
                    accumulators[strategy]["safety"],
                    physical,
                    accepted_cell_ids=accepted_ids,
                )

                semantic = _best_semantic_score(reference_table, predicted_table)
                _add_semantic(accumulators[strategy]["semantic"], semantic)
                accumulators[strategy]["safety"]["hidden_ambiguity"] += semantic[
                    "hidden_ambiguity"
                ]
                invented_codes = _invented_currency_codes(predicted_table)
                if invented_codes:
                    accumulators[strategy]["safety"]["invented_values"] += len(
                        invented_codes
                    )
                    _contract_failure(
                        failed_contracts,
                        case_id,
                        strategy,
                        "benchmark_currency_code_without_literal_evidence",
                        observed=sorted(invented_codes),
                    )

            for index, predicted_table in enumerate(extracted):
                if index not in matched_predicted:
                    accepted_ids = None
                    if accepted_evidence is not None:
                        accepted_ids = accepted_evidence.get(
                            (str(predicted_table.get("table_id") or ""), None),
                            set(),
                        )
                    invented = _visible_atom_count(
                        predicted_table,
                        accepted_cell_ids=accepted_ids,
                    )
                    accumulators[strategy]["safety"]["invented_values"] += invented
                    accumulators[strategy]["safety"][
                        "raw_extraction_invented_values"
                    ] += _visible_atom_count(predicted_table)

            evidence = _evidence_metrics(
                strategy_result.get("evidence_validation")
                if strategy == "C" and usable
                else None,
                extraction_tables=extracted,
            )
            _add_evidence(accumulators[strategy]["evidence"], evidence)
            accumulators[strategy]["safety"]["false_accepted_values"] += evidence[
                "false_accepted_values"
            ]
            accumulators[strategy]["safety"]["unsupported_evidence_cells"] += evidence[
                "unsupported"
            ]

            operations = (
                b_result.get("operations")
                if strategy == "C"
                else strategy_result.get("operations")
            )
            if not isinstance(operations, list):
                operations = []
                if usable:
                    _contract_failure(
                        failed_contracts,
                        case_id,
                        strategy,
                        "benchmark_strategy_operations_invalid",
                    )
                    accumulators[strategy]["safety"]["malformed_outputs"] += 1
            operation_metrics = _operation_metrics(
                operations,
                terminal=terminal,
            )
            pipeline_duration = _nonnegative(
                strategy_result.get("pipeline_duration_ms")
            )
            operation_metrics["latency_ms"] = (
                pipeline_duration
                if pipeline_duration
                else operation_metrics["provider_call_duration_ms"]
            )
            operation_metrics["evidence_validation_duration_ms"] = _nonnegative(
                strategy_result.get("evidence_validation_duration_ms")
            )
            _add_operations(accumulators[strategy]["operational"], operation_metrics)
            accumulators[strategy]["safety"]["hidden_retry"] += operation_metrics[
                "hidden_retry"
            ]
            accumulators[strategy]["safety"]["provider_failover"] += operation_metrics[
                "provider_failover"
            ]
            if operation_metrics["hidden_retry"]:
                _contract_failure(
                    failed_contracts,
                    case_id,
                    strategy,
                    "benchmark_hidden_retry_detected",
                )
            if operation_metrics["provider_failover"]:
                _contract_failure(
                    failed_contracts,
                    case_id,
                    strategy,
                    "benchmark_provider_failover_detected",
                )

    parser_accounting = _object(terminal.get("parser_accounting"))
    parser_duration = _nonnegative(parser_accounting.get("total_duration_ms"))
    parser_input_bytes = sum(
        _nonnegative(item.get("pdf_bytes"))
        for item in _dicts(parser_accounting.get("unique_documents"))
    )
    accumulators["C"]["operational"]["latency_ms"] += parser_duration
    accumulators["C"]["operational"]["parser_duration_ms"] += parser_duration
    accumulators["C"]["operational"]["input_bytes"] += parser_input_bytes
    accumulators["C"]["operational"]["parser_input_bytes"] += parser_input_bytes

    return {
        strategy: _finalize_accumulator(strategy, accumulators[strategy])
        for strategy in STRATEGIES
    }


def _new_accumulator() -> dict[str, Any]:
    return {
        "detection": {
            "reference_tables": 0,
            "predicted_tables": 0,
            "found_existing_tables": 0,
            "missed_tables": 0,
            "false_tables": 0,
            "matched_iou_sum": 0.0,
        },
        "physical": {
            "tables_total": 0,
            "exact_physical_tables": 0,
            "row_count_exact": 0,
            "column_count_exact": 0,
            "cell_placement_exact": 0,
            "cell_placement_total": 0,
            "cells_exact": 0,
            "cells_total": 0,
            "numeric_exact": 0,
            "numeric_total": 0,
            "empty_cells_exact": 0,
            "empty_cells_total": 0,
            "merged_spans_matched": 0,
            "merged_spans_expected": 0,
            "merged_spans_predicted": 0,
            "merged_span_exact_tables": 0,
            "invented_nonempty_cells": 0,
            "omitted_nonempty_cells": 0,
            "mutated_nonempty_cells": 0,
        },
        "semantic": {
            "tables_total": 0,
            "exact_semantic_tables": 0,
            "roles_matched": 0,
            "roles_expected": 0,
            "roles_predicted": 0,
            "logical_columns_matched": 0,
            "logical_columns_expected": 0,
            "logical_columns_predicted": 0,
            "header_roles_matched": 0,
            "header_roles_expected": 0,
            "header_roles_predicted": 0,
            "currency_relationships_matched": 0,
            "currency_relationships_expected": 0,
            "currency_relationships_predicted": 0,
            "unknown_roles_reported": 0,
        },
        "evidence": {
            "cases_not_run": 0,
            "cells_evaluated": 0,
            "source_value_exists": 0,
            "provenance_covered": 0,
            "uniquely_traced": 0,
            "accepted_cells": 0,
            "rejected_cells": 0,
            "human_review_cells": 0,
            "ambiguous": 0,
            "not_found": 0,
            "unsupported": 0,
            "false_accepted_values": 0,
        },
        "operational": {
            "operations": 0,
            "model_calls": 0,
            "count_tokens_calls": 0,
            "latency_ms": 0,
            "provider_call_duration_ms": 0,
            "evidence_validation_duration_ms": 0,
            "parser_duration_ms": 0,
            "parser_input_bytes": 0,
            "counted_input_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "response_bytes": 0,
            "visible_output_bytes": 0,
            "input_bytes": 0,
            "cost_microusd": 0.0,
            "priced_operations": 0,
            "unpriced_operations": 0,
        },
        "safety": {
            "invented_values": 0,
            "mutated_values": 0,
            "raw_extraction_invented_values": 0,
            "raw_extraction_mutated_values": 0,
            "hidden_ambiguity": 0,
            "unsupported_evidence_cells": 0,
            "false_accepted_values": 0,
            "malformed_outputs": 0,
            "failed_or_unsupported_cases": 0,
            "hidden_retry": 0,
            "provider_failover": 0,
        },
    }


def _strategy_usable(value: dict[str, Any]) -> bool:
    status = str(value.get("status") or "").strip().casefold()
    return status in SUCCESS_STATUSES and isinstance(value.get("extraction"), dict)


def _extraction_tables(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, dict):
        return None
    tables = value.get("tables")
    if not isinstance(tables, list) or any(not isinstance(item, dict) for item in tables):
        return None
    return [dict(item) for item in tables]


def _detection_for_strategy(
    *,
    strategy: str,
    strategy_result: dict[str, Any],
    b_result: dict[str, Any],
    extraction_tables: list[dict[str, Any]],
) -> Any:
    if strategy == "B":
        return strategy_result.get("detection")
    if strategy == "C":
        return strategy_result.get("detection", b_result.get("detection"))
    return {"regions": [_table_region(table) for table in extraction_tables]}


def _detection_regions(value: Any, *, page_bbox: Any) -> list[list[float]]:
    if not isinstance(value, dict):
        return []
    presence = str(
        value.get("table_presence", value.get("presence", "")) or ""
    ).casefold()
    if presence in {"absent", "no_tables", "none"}:
        return []
    raw = value.get("regions", value.get("tables", []))
    if not isinstance(raw, list):
        return []
    boxes: list[list[float]] = []
    for item in raw:
        bbox = _canonical_bbox(
            item if isinstance(item, list) else _table_bbox(item),
            page_bbox,
        )
        if bbox is not None:
            boxes.append(bbox)
    return boxes


def _fill_missing_extraction_bboxes(
    tables: list[dict[str, Any]],
    detected: list[list[float]],
) -> None:
    if len(tables) != len(detected):
        return
    for table, bbox in zip(tables, detected):
        if not _valid_bbox(_table_bbox(table)):
            table["bbox"] = list(bbox)


def _match_bboxes(
    reference: list[list[float]],
    predicted: list[list[float]],
    *,
    threshold: float,
) -> dict[str, Any]:
    scores = [
        [_bbox_iou(left, right) for right in predicted]
        for left in reference
    ]

    @lru_cache(maxsize=None)
    def solve(ref_index: int, used_mask: int) -> tuple[int, float, tuple[tuple[int, int, float], ...]]:
        if ref_index >= len(reference):
            return 0, 0.0, ()
        best = solve(ref_index + 1, used_mask)
        for pred_index, iou in enumerate(scores[ref_index]):
            if iou < threshold or used_mask & (1 << pred_index):
                continue
            count, total, pairs = solve(ref_index + 1, used_mask | (1 << pred_index))
            candidate = (count + 1, total + iou, ((ref_index, pred_index, iou), *pairs))
            if _matching_key(candidate) > _matching_key(best):
                best = candidate
        return best

    if len(predicted) <= 20:
        matched, iou_sum, pairs_tuple = solve(0, 0)
        pairs = list(pairs_tuple)
    else:
        # Corpus pages are bounded well below this.  The deterministic fallback
        # remains one-to-one without introducing a non-stdlib solver dependency.
        candidates = sorted(
            (
                (iou, ref_index, pred_index)
                for ref_index, row in enumerate(scores)
                for pred_index, iou in enumerate(row)
                if iou >= threshold
            ),
            key=lambda item: (-item[0], item[1], item[2]),
        )
        used_refs: set[int] = set()
        used_preds: set[int] = set()
        pairs = []
        for iou, ref_index, pred_index in candidates:
            if ref_index in used_refs or pred_index in used_preds:
                continue
            used_refs.add(ref_index)
            used_preds.add(pred_index)
            pairs.append((ref_index, pred_index, iou))
        matched = len(pairs)
        iou_sum = sum(item[2] for item in pairs)
    return {
        "pairs": sorted(pairs),
        "reference_tables": len(reference),
        "predicted_tables": len(predicted),
        "found_existing_tables": matched,
        "missed_tables": len(reference) - matched,
        "false_tables": len(predicted) - matched,
        "matched_iou_sum": iou_sum,
    }


def _matching_key(
    value: tuple[int, float, tuple[tuple[int, int, float], ...]],
) -> tuple[int, float, tuple[tuple[int, int], ...]]:
    return (
        value[0],
        round(value[1], 12),
        tuple((-left, -right) for left, right, _ in value[2]),
    )


def _add_detection(target: dict[str, Any], value: dict[str, Any]) -> None:
    for key in (
        "reference_tables",
        "predicted_tables",
        "found_existing_tables",
        "missed_tables",
        "false_tables",
    ):
        target[key] += int(value[key])
    target["matched_iou_sum"] += float(value["matched_iou_sum"])


def _best_physical_score(
    reference_table: dict[str, Any],
    predicted_table: dict[str, Any] | None,
) -> dict[str, Any]:
    reference_alternatives = _physical_alternatives(reference_table)
    predicted_alternatives = _physical_alternatives(predicted_table or {})
    if not reference_alternatives:
        reference_alternatives = [reference_table]
    if not predicted_alternatives:
        predicted_alternatives = [{}]
    candidates: list[dict[str, Any]] = []
    for reference in reference_alternatives:
        for predicted in predicted_alternatives:
            score = _physical_pair(reference, predicted)
            score["_reference_physical"] = reference
            score["_predicted_physical"] = predicted
            score["_predicted_alternative_id"] = _physical_alternative_id(
                predicted_table or {}, predicted
            )
            candidates.append(score)
    return max(candidates, key=_physical_pair_rank)


def _physical_alternatives(table: dict[str, Any]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    top_physical = table.get("physical")
    if isinstance(top_physical, dict):
        collected.append(top_physical)
    top_alternatives = table.get("alternatives")
    if isinstance(top_alternatives, list):
        collected.extend(
            item["physical"]
            for item in top_alternatives
            if isinstance(item, dict) and isinstance(item.get("physical"), dict)
        )
    if collected:
        return _deduplicate_objects(collected)
    for key in ("physical", "physical_structure", "topology"):
        block = table.get(key)
        if isinstance(block, dict):
            alternatives = block.get("alternatives")
            if isinstance(alternatives, list):
                return [item for item in alternatives if isinstance(item, dict)]
            return [block]
    alternatives = table.get("physical_alternatives")
    if isinstance(alternatives, list):
        return [item for item in alternatives if isinstance(item, dict)]
    return [table] if table else []


def _physical_pair(
    reference: dict[str, Any],
    predicted: dict[str, Any],
) -> dict[str, int]:
    left = _grid(reference)
    right = _grid(predicted)
    expected_positions = {
        (row, column)
        for row in range(1, left["rows"] + 1)
        for column in range(1, left["columns"] + 1)
    }
    predicted_positions = set(right["positions"])
    placement_match = len(expected_positions & predicted_positions)
    cells_exact = numeric_exact = numeric_total = 0
    empty_exact = empty_total = 0
    for position in sorted(expected_positions):
        expected = _normalize(left["values"].get(position, ""))
        actual = _normalize(right["values"].get(position, ""))
        cells_exact += expected == actual
        if _numeric_like(expected):
            numeric_total += 1
            numeric_exact += expected == actual
        if not expected:
            empty_total += 1
            empty_exact += not actual
    value_safety = _visible_atom_differences(reference, predicted)
    expected_spans = _span_set(reference)
    predicted_spans = _span_set(predicted)
    span_matches = len(expected_spans & predicted_spans)
    row_exact = left["rows"] == right["rows"]
    column_exact = left["columns"] == right["columns"]
    placement_exact = predicted_positions == expected_positions
    spans_exact = expected_spans == predicted_spans
    exact = (
        row_exact
        and column_exact
        and placement_exact
        and cells_exact == len(expected_positions)
        and spans_exact
    )
    return {
        "tables_total": 1,
        "exact_physical_tables": int(exact),
        "row_count_exact": int(row_exact),
        "column_count_exact": int(column_exact),
        "cell_placement_exact": placement_match,
        "cell_placement_total": len(expected_positions),
        "cells_exact": cells_exact,
        "cells_total": len(expected_positions),
        "numeric_exact": numeric_exact,
        "numeric_total": numeric_total,
        "empty_cells_exact": empty_exact,
        "empty_cells_total": empty_total,
        "merged_spans_matched": span_matches,
        "merged_spans_expected": len(expected_spans),
        "merged_spans_predicted": len(predicted_spans),
        "merged_span_exact_tables": int(spans_exact),
        "invented_nonempty_cells": value_safety["invented"],
        "omitted_nonempty_cells": value_safety["omitted"],
        "mutated_nonempty_cells": value_safety["mutated"],
    }


def _physical_pair_rank(value: dict[str, int]) -> tuple[int, ...]:
    return (
        value["exact_physical_tables"],
        value["row_count_exact"] + value["column_count_exact"],
        value["cell_placement_exact"],
        value["cells_exact"],
        value["merged_spans_matched"],
        -value["invented_nonempty_cells"],
        -value["mutated_nonempty_cells"],
        -value["omitted_nonempty_cells"],
    )


def _physical_alternative_id(
    table: dict[str, Any], physical: dict[str, Any]
) -> str | None:
    if table.get("physical") is physical:
        return None
    for alternative in _dicts(table.get("alternatives")):
        if alternative.get("physical") is physical:
            value = alternative.get("alternative_id")
            return str(value) if isinstance(value, str) else None
    return None


def _grid(value: dict[str, Any]) -> dict[str, Any]:
    raw_rows = value.get("rows")
    raw_columns = value.get("columns", value.get("column_count"))
    row_count = _dimension(value.get("row_count", raw_rows))
    column_count = _dimension(raw_columns)
    values: dict[tuple[int, int], str] = {}
    positions: set[tuple[int, int]] = set()

    matrix = value.get("cells", value.get("grid", value.get("matrix")))
    if isinstance(matrix, list) and matrix and all(isinstance(row, list) for row in matrix):
        row_count = row_count or len(matrix)
        column_count = column_count or max((len(row) for row in matrix), default=0)
        for row_index, row in enumerate(matrix, start=1):
            for column_index, cell in enumerate(row, start=1):
                positions.add((row_index, column_index))
                values[(row_index, column_index)] = _cell_text(cell)
    elif isinstance(matrix, list) and all(isinstance(cell, dict) for cell in matrix):
        for cell in matrix:
            row_index = _ordinal(cell, "row")
            column_index = _ordinal(cell, "column")
            if row_index and column_index:
                positions.add((row_index, column_index))
                values[(row_index, column_index)] = _cell_text(cell)
                row_count = max(row_count, row_index)
                column_count = max(column_count, column_index)

    if isinstance(raw_rows, list) and raw_rows and all(isinstance(row, dict) for row in raw_rows):
        row_count = row_count or len(raw_rows)
        for fallback_row, row in enumerate(raw_rows, start=1):
            row_index = _ordinal(row, "row") or fallback_row
            cells = row.get("cells")
            if not isinstance(cells, list):
                continue
            column_count = max(column_count, len(cells))
            for fallback_column, cell in enumerate(cells, start=1):
                column_index = (
                    _ordinal(cell, "column") if isinstance(cell, dict) else None
                ) or fallback_column
                positions.add((row_index, column_index))
                values[(row_index, column_index)] = _cell_text(cell)
    return {
        "rows": row_count,
        "columns": column_count,
        "positions": positions,
        "values": values,
    }


def _dimension(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, list):
        return len(value)
    return 0


def _ordinal(value: dict[str, Any], axis: str) -> int | None:
    for key in (f"{axis}_ordinal", axis, f"{axis}_index"):
        raw = value.get(key)
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw + 1 if key.endswith("_index") and raw >= 0 else raw
    raw_id = value.get(f"{axis}_id")
    if isinstance(raw_id, str):
        match = _INTEGER_SUFFIX.search(raw_id)
        if match:
            return int(match.group(1))
    return None


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        return " ".join(_cell_text(item) for item in value).strip()
    if not isinstance(value, dict):
        return ""
    if value.get("explicit_empty") is True or value.get("empty") is True:
        return ""
    for key in (
        "text",
        "value",
        "source_text",
        "display_text",
        "raw_text",
        "content",
    ):
        if key in value and isinstance(value.get(key), (str, int, float)):
            return str(value.get(key) or "")
    for key in ("resolved_source_values", "exact_values", "values"):
        raw = value.get(key)
        if isinstance(raw, list):
            return " ".join(str(item) for item in raw).strip()
    return ""


def _span_set(value: dict[str, Any]) -> set[tuple[int, int, int, int, str]]:
    raw = value.get("spans", value.get("merged_regions", []))
    if not isinstance(raw, list):
        return set()
    result: set[tuple[int, int, int, int, str]] = set()
    position_by_cell_id: dict[str, tuple[int, int]] = {}
    for cell in _dicts(value.get("cells")):
        row = _ordinal(cell, "row")
        column = _ordinal(cell, "column")
        cell_id = cell.get("cell_id")
        if row and column and isinstance(cell_id, str) and cell_id:
            position_by_cell_id[cell_id] = (row, column)
    for span in raw:
        if not isinstance(span, dict):
            continue
        coordinates: tuple[int | None, int | None, int | None, int | None] = (
            _integer(span.get("start_row", span.get("row_start"))),
            _integer(span.get("end_row", span.get("row_end"))),
            _integer(span.get("start_column", span.get("column_start"))),
            _integer(span.get("end_column", span.get("column_end"))),
        )
        cell_ids = span.get("cell_ids")
        if (
            not all(item is not None and item > 0 for item in coordinates)
            and isinstance(cell_ids, list)
        ):
            positions = [
                position_by_cell_id[item]
                for item in cell_ids
                if isinstance(item, str) and item in position_by_cell_id
            ]
            if positions and len(positions) == len(cell_ids):
                coordinates = (
                    min(item[0] for item in positions),
                    max(item[0] for item in positions),
                    min(item[1] for item in positions),
                    max(item[1] for item in positions),
                )
        if all(item is not None and item > 0 for item in coordinates):
            relation = str(span.get("relation") or "merged")
            if relation == "spanning_header":
                relation = "merged"
            result.add((*coordinates, relation))  # type: ignore[arg-type]
    return result


def _add_physical(target: dict[str, Any], value: dict[str, Any]) -> None:
    for key in target:
        target[key] += int(value[key])


def _add_safety_from_physical(
    target: dict[str, Any],
    value: dict[str, Any],
    *,
    accepted_cell_ids: set[str] | None,
) -> None:
    raw_invented = int(value["invented_nonempty_cells"])
    raw_mutated = int(value["mutated_nonempty_cells"])
    target["raw_extraction_invented_values"] += raw_invented
    target["raw_extraction_mutated_values"] += raw_mutated
    if accepted_cell_ids is None:
        target["invented_values"] += raw_invented
        target["mutated_values"] += raw_mutated
        return
    accepted = _visible_atom_differences(
        _object(value.get("_reference_physical")),
        _object(value.get("_predicted_physical")),
        accepted_cell_ids=accepted_cell_ids,
    )
    target["invented_values"] += accepted["invented"]
    target["mutated_values"] += accepted["mutated"]


def _best_semantic_score(
    reference_table: dict[str, Any],
    predicted_table: dict[str, Any] | None,
) -> dict[str, int]:
    references = _semantic_alternatives(reference_table)
    predictions = _semantic_alternatives(predicted_table or {})
    if not references:
        references = [{}]
    if not predictions:
        predictions = [{}]
    candidates = [
        _semantic_pair(reference, predicted)
        for reference in references
        for predicted in predictions
    ]
    best = max(candidates, key=_semantic_pair_rank)
    reference_ambiguous = _semantic_is_ambiguous(reference_table, len(references))
    predicted_ambiguous = _semantic_is_ambiguous(predicted_table or {}, len(predictions))
    best["hidden_ambiguity"] = int(reference_ambiguous and not predicted_ambiguous)
    return best


def _semantic_alternatives(table: dict[str, Any]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    top_semantic = table.get("semantic")
    if isinstance(top_semantic, dict):
        collected.append(top_semantic)
    top_alternatives = table.get("alternatives")
    if isinstance(top_alternatives, list):
        collected.extend(
            item["semantic"]
            for item in top_alternatives
            if isinstance(item, dict) and isinstance(item.get("semantic"), dict)
        )
    if collected:
        return _deduplicate_objects(collected)
    semantic = table.get("semantic", table.get("semantic_structure"))
    if isinstance(semantic, list):
        return [item for item in semantic if isinstance(item, dict)]
    if isinstance(semantic, dict):
        alternatives = semantic.get("alternatives")
        if isinstance(alternatives, list):
            return [item for item in alternatives if isinstance(item, dict)]
        return [semantic]
    alternatives = table.get("semantic_alternatives")
    if isinstance(alternatives, list):
        return [item for item in alternatives if isinstance(item, dict)]
    return []


def _semantic_pair(
    reference: dict[str, Any],
    predicted: dict[str, Any],
) -> dict[str, int]:
    left = _semantic_sets(reference)
    right = _semantic_sets(predicted)
    role_match = len(left["roles"] & right["roles"])
    logical_match = len(left["logical_columns"] & right["logical_columns"])
    header_match = len(left["header_roles"] & right["header_roles"])
    currency_match = len(left["currency_relationships"] & right["currency_relationships"])
    exact = all(
        left[key] == right[key]
        for key in (
            "roles",
            "header_roles",
            "currency_relationships",
            "logical_signature",
        )
    )
    return {
        "tables_total": 1,
        "exact_semantic_tables": int(exact),
        "roles_matched": role_match,
        "roles_expected": len(left["roles"]),
        "roles_predicted": len(right["roles"]),
        "logical_columns_matched": logical_match,
        "logical_columns_expected": len(left["logical_columns"]),
        "logical_columns_predicted": len(right["logical_columns"]),
        "header_roles_matched": header_match,
        "header_roles_expected": len(left["header_roles"]),
        "header_roles_predicted": len(right["header_roles"]),
        "currency_relationships_matched": currency_match,
        "currency_relationships_expected": len(left["currency_relationships"]),
        "currency_relationships_predicted": len(right["currency_relationships"]),
        "unknown_roles_reported": sum(item == "unknown" for item in right["roles"]),
        "hidden_ambiguity": 0,
    }


def _semantic_pair_rank(value: dict[str, int]) -> tuple[int, ...]:
    return (
        value["exact_semantic_tables"],
        value["currency_relationships_matched"],
        value["logical_columns_matched"],
        value["roles_matched"],
        value["header_roles_matched"],
        -value["unknown_roles_reported"],
    )


def _semantic_sets(value: dict[str, Any]) -> dict[str, set[Any]]:
    fields = _dicts(value.get("fields", value.get("semantic_fields")))
    roles: set[str] = set()
    logical_columns: set[tuple[str, tuple[str, ...]]] = set()
    header_roles: set[str] = set()
    field_role_by_id: dict[str, str] = {}
    for field in fields:
        role = str(field.get("role", field.get("logical_type", "unknown")) or "unknown")
        logical_type = str(field.get("logical_type") or role)
        field_id = str(field.get("field_id") or "")
        if field_id:
            field_role_by_id[field_id] = logical_type
        roles.add(role)
        columns = _canonical_column_ids(
            field.get("physical_column_ids", field.get("columns", []))
        )
        logical_columns.add((logical_type, columns))
        if role in {"header", "group_header", "leaf_header"}:
            header_roles.add(role)
    direct_roles = value.get("roles", value.get("semantic_roles"))
    if isinstance(direct_roles, list):
        roles.update(str(item) for item in direct_roles)
    direct_headers = value.get("header_roles")
    if isinstance(direct_headers, list):
        header_roles.update(str(item) for item in direct_headers)

    currency_relationships: set[tuple[Any, ...]] = set()
    for qualifier in _dicts(value.get("qualifiers")):
        if str(qualifier.get("kind") or "") != "currency":
            continue
        measure = qualifier.get(
            "target_field_id",
            qualifier.get("measure_field_id", qualifier.get("measure_role")),
        )
        measure_role = field_role_by_id.get(str(measure), str(measure or "unknown"))
        currency_relationships.add(
            (
                "currency",
                measure_role,
                qualifier.get("normalized_code"),
            )
        )
    direct_relationship = value.get(
        "currency_qualifier_relationship",
        value.get("currency_qualifier_relationships"),
    )
    if isinstance(direct_relationship, dict):
        currency_relationships.add(
            _canonical_relation(direct_relationship, field_role_by_id=field_role_by_id)
        )
    elif isinstance(direct_relationship, list):
        for item in direct_relationship:
            if isinstance(item, dict):
                currency_relationships.add(
                    _canonical_relation(item, field_role_by_id=field_role_by_id)
                )
            elif isinstance(item, str):
                currency_relationships.add((item,))
    elif isinstance(direct_relationship, str):
        currency_relationships.add((direct_relationship,))

    signature = value.get("logical_schema_signature")
    logical_signature: set[Any] = set()
    if isinstance(signature, list):
        for item in signature:
            if isinstance(item, dict):
                logical_signature.add(
                    str(
                        item.get("logical_type")
                        or item.get("logical_column_id")
                        or item.get("role")
                        or "unknown"
                    )
                )
            else:
                logical_signature.add(str(item))
    else:
        logical_signature.update(item[0] for item in logical_columns)
    return {
        "roles": roles,
        "logical_columns": logical_columns,
        "header_roles": header_roles,
        "currency_relationships": currency_relationships,
        "logical_signature": logical_signature,
    }


def _canonical_relation(
    value: dict[str, Any],
    *,
    field_role_by_id: dict[str, str],
) -> tuple[Any, ...]:
    kind = str(value.get("kind") or "currency")
    if kind == "currency_symbol":
        kind = "currency"
    target = value.get(
        "target_field_id",
        value.get("measure_field_id", value.get("measure_role", "unknown")),
    )
    return (
        kind,
        field_role_by_id.get(str(target), str(target)),
        value.get("normalized_code"),
    )


def _canonical_column_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    result: list[str] = []
    for item in value:
        if isinstance(item, int) and not isinstance(item, bool):
            result.append(str(item))
            continue
        rendered = str(item)
        match = _INTEGER_SUFFIX.search(rendered)
        result.append(match.group(1) if match else rendered)
    return tuple(sorted(set(result)))


def _semantic_is_ambiguous(table: dict[str, Any], alternatives: int) -> bool:
    semantic = table.get("semantic", table.get("semantic_structure"))
    status = str(_object(semantic).get("status", table.get("semantic_status", ""))).casefold()
    decision = str(table.get("decision") or "").casefold()
    return alternatives > 1 or status in {"ambiguous", "uncertain"} or decision == "ambiguous"


def _add_semantic(target: dict[str, Any], value: dict[str, int]) -> None:
    for key in target:
        target[key] += int(value[key])


def _invented_currency_codes(table: dict[str, Any] | None) -> set[str]:
    if not table:
        return set()
    visible = " ".join(
        _cell_text(cell)
        for alternative in _physical_alternatives(table)
        for cell in _all_cells(alternative)
    )
    literal_codes = set(re.findall(r"(?<![A-Z0-9])[A-Z]{3}(?![A-Z0-9])", visible))
    claimed: set[str] = set()
    for semantic in _semantic_alternatives(table):
        for qualifier in _dicts(semantic.get("qualifiers")):
            if qualifier.get("kind") == "currency" and isinstance(
                qualifier.get("normalized_code"), str
            ):
                claimed.add(str(qualifier["normalized_code"]))
    return claimed - literal_codes


def _all_cells(value: dict[str, Any]) -> list[Any]:
    cells = value.get("cells")
    if isinstance(cells, list) and cells and all(isinstance(row, list) for row in cells):
        return [cell for row in cells for cell in row]
    if isinstance(cells, list):
        return list(cells)
    rows = value.get("rows")
    if isinstance(rows, list):
        return [
            cell
            for row in rows
            if isinstance(row, dict)
            for cell in row.get("cells") or []
        ]
    return []


def _visible_atoms(value: dict[str, Any], *, accepted_cell_ids: set[str] | None = None) -> Counter[str]:
    atoms: Counter[str] = Counter()
    for cell in _all_cells(value):
        if accepted_cell_ids is not None:
            if not isinstance(cell, dict) or cell.get("cell_id") not in accepted_cell_ids:
                continue
        text = _normalize(_cell_text(cell))
        if not text:
            continue
        currency = _LEADING_CURRENCY_SYMBOL.fullmatch(text)
        if currency:
            atoms[currency.group(1)] += 1
            atoms[_normalize(currency.group(2))] += 1
        else:
            atoms[text] += 1
    return atoms


def _visible_atom_differences(
    reference: dict[str, Any],
    predicted: dict[str, Any],
    *,
    accepted_cell_ids: set[str] | None = None,
) -> dict[str, int]:
    expected = _visible_atoms(reference)
    actual = _visible_atoms(predicted, accepted_cell_ids=accepted_cell_ids)
    common = expected & actual
    expected_remaining = expected - common
    actual_remaining = actual - common
    expected_count = sum(expected_remaining.values())
    actual_count = sum(actual_remaining.values())
    mutated = min(expected_count, actual_count)
    return {
        "invented": max(0, actual_count - mutated),
        "mutated": mutated,
        "omitted": max(0, expected_count - mutated),
    }


def _visible_atom_count(table: dict[str, Any], *, accepted_cell_ids: set[str] | None = None) -> int:
    alternatives = _physical_alternatives(table)
    if not alternatives:
        return 0
    return sum(_visible_atoms(alternatives[0], accepted_cell_ids=accepted_cell_ids).values())


def _nonempty_cell_count(table: dict[str, Any]) -> int:
    alternatives = _physical_alternatives(table)
    if not alternatives:
        return 0
    grid = _grid(alternatives[0])
    return sum(bool(_normalize(value)) for value in grid["values"].values())


def _evidence_metrics(
    value: Any,
    *,
    extraction_tables: list[dict[str, Any]],
) -> dict[str, int]:
    nonempty = sum(_nonempty_cell_count(table) for table in extraction_tables)
    result = {
        "cases_not_run": 0,
        "cells_evaluated": 0,
        "source_value_exists": 0,
        "provenance_covered": 0,
        "uniquely_traced": 0,
        "accepted_cells": 0,
        "rejected_cells": 0,
        "human_review_cells": 0,
        "ambiguous": 0,
        "not_found": 0,
        "unsupported": 0,
        "false_accepted_values": 0,
    }
    if not isinstance(value, dict) or value.get("schema_version") != EVIDENCE_SCHEMA:
        result["cases_not_run"] = 1
        return result
    cells = _dicts(value.get("cells"))
    for cell in cells:
        cell_status = str(cell.get("status") or "").casefold()
        matches = _dicts(cell.get("matches"))
        traceable = bool(matches) and all(
            isinstance(match.get("parser_ordinals"), list)
            and bool(match.get("parser_ordinals"))
            and isinstance(match.get("bboxes"), list)
            and len(match["bboxes"]) == len(match["parser_ordinals"])
            for match in matches
        )
        exists = traceable
        unique = cell_status == "traced" and len(matches) == 1 and traceable
        ambiguous = cell_status == "ambiguous"
        not_found = cell_status == "not_found"
        unsupported = cell_status == "unsupported"
        disposition = str(cell.get("disposition") or "").casefold()
        accepted = disposition == "accept"
        result["cells_evaluated"] += 1
        result["source_value_exists"] += exists
        result["provenance_covered"] += unique
        result["uniquely_traced"] += unique
        result["accepted_cells"] += accepted
        result["rejected_cells"] += disposition == "reject"
        result["human_review_cells"] += disposition == "review"
        result["ambiguous"] += ambiguous
        result["not_found"] += not_found
        result["unsupported"] += unsupported
        result["false_accepted_values"] += accepted and not unique
    if not cells and result["cells_evaluated"] == 0:
        result["cells_evaluated"] = nonempty
    return result


def _accepted_evidence_cells(value: Any) -> dict[tuple[str, str | None], set[str]]:
    result: dict[tuple[str, str | None], set[str]] = {}
    for cell in _dicts(_object(value).get("cells")):
        if cell.get("disposition") != "accept":
            continue
        table_id = cell.get("table_id")
        alternative_id = cell.get("alternative_id")
        cell_id = cell.get("cell_id")
        if not isinstance(table_id, str) or not isinstance(cell_id, str):
            continue
        key = (
            table_id,
            alternative_id if isinstance(alternative_id, str) else None,
        )
        result.setdefault(key, set()).add(cell_id)
    return result


def _add_evidence(target: dict[str, Any], value: dict[str, int]) -> None:
    for key in target:
        target[key] += int(value[key])


def _operation_metrics(
    operations: list[Any],
    *,
    terminal: dict[str, Any],
) -> dict[str, Any]:
    result = {
        "operations": 0,
        "model_calls": 0,
        "count_tokens_calls": 0,
        "latency_ms": 0,
        "provider_call_duration_ms": 0,
        "evidence_validation_duration_ms": 0,
        "parser_duration_ms": 0,
        "parser_input_bytes": 0,
        "counted_input_tokens": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "response_bytes": 0,
        "visible_output_bytes": 0,
        "input_bytes": 0,
        "cost_microusd": 0.0,
        "priced_operations": 0,
        "unpriced_operations": 0,
        "hidden_retry": 0,
        "provider_failover": 0,
    }
    for raw in operations:
        if not isinstance(raw, dict):
            continue
        result["operations"] += 1
        attempt = _object(raw.get("attempt"))
        count_tokens = _object(raw.get("count_tokens"))
        if attempt:
            result["model_calls"] += 1
        if count_tokens:
            result["count_tokens_calls"] += 1
        result["provider_call_duration_ms"] += _nonnegative(
            attempt.get("duration_ms")
        )
        usage = _object(attempt.get("usage"))
        input_tokens = _nonnegative(
            usage.get("input_tokens", usage.get("prompt_tokens"))
        )
        output_tokens = _nonnegative(
            usage.get("output_tokens", usage.get("completion_tokens"))
        )
        explicit_reasoning_tokens = _nonnegative(
            usage.get("reasoning_tokens", usage.get("thinking_tokens"))
        )
        total_tokens = _nonnegative(usage.get("total_tokens"))
        reasoning_tokens = max(
            explicit_reasoning_tokens,
            total_tokens - input_tokens - output_tokens,
        )
        counted = _nonnegative(
            count_tokens.get("total_tokens", raw.get("counted_input_tokens"))
        )
        result["counted_input_tokens"] += counted
        result["input_tokens"] += input_tokens
        result["output_tokens"] += output_tokens
        result["reasoning_tokens"] += reasoning_tokens
        result["response_bytes"] += _nonnegative(raw.get("response_bytes"))
        result["visible_output_bytes"] += _nonnegative(raw.get("visible_output_bytes"))
        result["input_bytes"] += sum(
            _nonnegative(raw.get(key))
            for key in (
                "input_bytes",
                "image_bytes",
                "model_view_bytes",
                "prompt_bytes",
                "schema_bytes",
            )
        )
        result["hidden_retry"] += attempt.get("hidden_retry") is True or raw.get(
            "hidden_retry"
        ) is True
        result["provider_failover"] += attempt.get("provider_failover") is True or raw.get(
            "provider_failover"
        ) is True
        pricing = _pricing_for_operation(terminal, raw, attempt)
        if pricing is None:
            if attempt:
                result["unpriced_operations"] += 1
        else:
            result["priced_operations"] += 1
            result["cost_microusd"] += (
                input_tokens * pricing["input_usd_per_million_tokens"]
                + output_tokens * pricing["output_usd_per_million_tokens"]
                + reasoning_tokens * pricing["reasoning_usd_per_million_tokens"]
            )
    return result


def _pricing_for_operation(
    terminal: dict[str, Any],
    operation: dict[str, Any],
    attempt: dict[str, Any],
) -> dict[str, float] | None:
    manifest = _object(terminal.get("target_manifest"))
    pricing = _object(manifest.get("provider_contract")).get("pricing")
    model = str(
        attempt.get("model_resolved", attempt.get("model_requested", operation.get("model", "")))
        or ""
    )
    provider = str(attempt.get("provider", operation.get("provider", "")) or "")
    entry: Any = pricing
    if isinstance(pricing, list):
        entry = next(
            (
                item
                for item in pricing
                if isinstance(item, dict)
                and (not model or item.get("model") in {None, model})
                and (not provider or item.get("provider") in {None, provider})
            ),
            None,
        )
    elif isinstance(pricing, dict):
        for key in (model, model.removeprefix("models/"), provider, "default"):
            if key and isinstance(pricing.get(key), dict):
                entry = pricing[key]
                break
    if not isinstance(entry, dict):
        return None
    input_price = _finite_number(
        entry.get(
            "input_usd_per_1m_tokens",
            entry.get("input_usd_per_million_tokens", entry.get("input_per_million")),
        )
    )
    output_price = _finite_number(
        entry.get(
            "output_usd_per_1m_tokens",
            entry.get("output_usd_per_million_tokens", entry.get("output_per_million")),
        )
    )
    reasoning_price = _finite_number(
        entry.get(
            "reasoning_usd_per_million_tokens",
            entry.get("reasoning_per_million", output_price),
        )
    )
    if input_price is None or output_price is None or reasoning_price is None:
        return None
    return {
        "input_usd_per_million_tokens": input_price,
        "output_usd_per_million_tokens": output_price,
        "reasoning_usd_per_million_tokens": reasoning_price,
    }


def _add_operations(target: dict[str, Any], value: dict[str, Any]) -> None:
    for key in target:
        target[key] += value[key]


def _finalize_accumulator(strategy: str, value: dict[str, Any]) -> dict[str, Any]:
    detection = dict(value["detection"])
    physical = dict(value["physical"])
    semantic = dict(value["semantic"])
    evidence = dict(value["evidence"])
    operational = dict(value["operational"])
    safety = dict(value["safety"])

    detection["table_detection_precision"] = _ratio(
        detection["found_existing_tables"], detection["predicted_tables"]
    )
    detection["table_detection_recall"] = _ratio(
        detection["found_existing_tables"], detection["reference_tables"]
    )
    detection["table_detection_f1"] = _f1(
        detection["table_detection_precision"], detection["table_detection_recall"]
    )
    detection["mean_matched_iou"] = _ratio(
        detection.pop("matched_iou_sum"), detection["found_existing_tables"]
    )

    physical["exact_physical_table_rate"] = _ratio(
        physical["exact_physical_tables"], physical["tables_total"]
    )
    physical["row_count_accuracy"] = _ratio(
        physical["row_count_exact"], physical["tables_total"]
    )
    physical["column_count_accuracy"] = _ratio(
        physical["column_count_exact"], physical["tables_total"]
    )
    physical["cell_placement_accuracy"] = _ratio(
        physical["cell_placement_exact"], physical["cell_placement_total"]
    )
    physical["cell_accuracy"] = _ratio(
        physical["cells_exact"], physical["cells_total"]
    )
    physical["numeric_accuracy"] = _ratio(
        physical["numeric_exact"], physical["numeric_total"]
    )
    physical["empty_cell_accuracy"] = _ratio(
        physical["empty_cells_exact"], physical["empty_cells_total"]
    )
    physical["merged_span_precision"] = _ratio(
        physical["merged_spans_matched"], physical["merged_spans_predicted"]
    )
    physical["merged_span_recall"] = _ratio(
        physical["merged_spans_matched"], physical["merged_spans_expected"]
    )

    semantic["exact_semantic_table_rate"] = _ratio(
        semantic["exact_semantic_tables"], semantic["tables_total"]
    )
    for prefix in ("roles", "logical_columns", "header_roles", "currency_relationships"):
        semantic[f"{prefix}_precision"] = _ratio(
            semantic[f"{prefix}_matched"], semantic[f"{prefix}_predicted"]
        )
        semantic[f"{prefix}_recall"] = _ratio(
            semantic[f"{prefix}_matched"], semantic[f"{prefix}_expected"]
        )

    evidence["existence_rate"] = _ratio(
        evidence["source_value_exists"], evidence["cells_evaluated"]
    )
    evidence["provenance_coverage"] = _ratio(
        evidence["provenance_covered"], evidence["cells_evaluated"]
    )
    evidence["unique_traceability_rate"] = _ratio(
        evidence["uniquely_traced"], evidence["cells_evaluated"]
    )
    evidence["human_review_rate"] = _ratio(
        evidence["human_review_cells"], evidence["cells_evaluated"]
    )

    operational["cost_microusd"] = (
        round(float(operational["cost_microusd"]), 6)
        if operational["priced_operations"]
        else None
    )
    operational["cost_available"] = bool(operational["priced_operations"])
    operational["pricing_complete"] = bool(
        operational["model_calls"]
        and operational["unpriced_operations"] == 0
        and operational["priced_operations"] == operational["model_calls"]
    )
    operational["additional_model_calls"] = (
        0 if strategy == "C" else operational["model_calls"]
    )
    operational["reused_from_strategy"] = "B" if strategy == "C" else None

    safety["passed"] = all(
        safety[key] == 0
        for key in (
            "invented_values",
            "mutated_values",
            "hidden_ambiguity",
            "false_accepted_values",
            "malformed_outputs",
            "hidden_retry",
            "provider_failover",
        )
    )
    return {
        "detection": detection,
        "physical": physical,
        "semantic": semantic,
        "evidence": evidence,
        "operational": operational,
        "safety": safety,
        "complexity": _complexity_policy()[strategy],
    }


def _recommend(
    strategies: dict[str, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    eligible = [
        strategy
        for strategy in STRATEGIES
        if _object(strategies[strategy].get("safety")).get("passed") is True
    ]
    accuracy = {
        strategy: _accuracy_vector(strategies[strategy]) for strategy in STRATEGIES
    }
    trace: dict[str, Any] = {
        "eligible_after_safety": eligible,
        "accuracy_vectors": {key: list(value) for key, value in accuracy.items()},
        "provenance_considered_after_accuracy": True,
        "complexity_used_only_as_final_tiebreaker": True,
    }
    if not eligible or max(
        _object(strategies[item].get("physical")).get("exact_physical_tables", 0)
        for item in eligible
    ) == 0:
        trace["reason"] = "no_safe_strategy_with_exact_physical_table"
        return FAILURE_CONCLUSION, trace

    best_vector = max(accuracy[item] for item in eligible)
    best = [item for item in eligible if accuracy[item] == best_vector]
    c_evidence = _object(strategies["C"].get("evidence"))
    c_complete = bool(
        c_evidence.get("cells_evaluated", 0) > 0
        and c_evidence.get("provenance_coverage") == 1.0
        and c_evidence.get("unique_traceability_rate") == 1.0
        and c_evidence.get("ambiguous", 0) == 0
        and c_evidence.get("not_found", 0) == 0
        and c_evidence.get("unsupported", 0) == 0
        and c_evidence.get("false_accepted_values", 0) == 0
    )
    c_partial = bool(
        c_evidence.get("cells_evaluated", 0) > 0
        and c_evidence.get("provenance_covered", 0) > 0
        and c_evidence.get("false_accepted_values", 0) == 0
    )
    trace["strategy_c_complete_unique_provenance"] = c_complete
    trace["strategy_c_partial_provenance"] = c_partial
    if "C" in best and c_complete:
        trace["reason"] = "safety_and_accuracy_best_with_complete_unique_provenance"
        return "STRATEGY_C_HYBRID_EVIDENCE_PREFERRED", trace
    if "C" in eligible and c_partial and (
        "B" in best or accuracy["C"] == accuracy["B"]
    ):
        trace["reason"] = "vlm_accuracy_with_partial_high_risk_provenance_advantage"
        return "HYBRID_ONLY_FOR_HIGH_RISK_DOCUMENTS", trace

    non_c_best = [item for item in best if item in {"A", "B"}]
    if non_c_best:
        selected = min(
            non_c_best,
            key=lambda item: _object(strategies[item].get("complexity")).get(
                "objective_units", 999
            ),
        )
    elif "C" in best:
        selected = "C"
    else:
        selected = min(
            best,
            key=lambda item: _object(strategies[item].get("complexity")).get(
                "objective_units", 999
            ),
        )
    trace["reason"] = "lexicographic_accuracy_then_frozen_complexity"
    return {
        "A": "STRATEGY_A_DIRECT_VLM_PREFERRED",
        "B": "STRATEGY_B_TWO_STEP_VLM_PREFERRED",
        "C": "STRATEGY_C_HYBRID_EVIDENCE_PREFERRED",
    }[selected], trace


def _accuracy_vector(value: dict[str, Any]) -> tuple[float, ...]:
    detection = _object(value.get("detection"))
    physical = _object(value.get("physical"))
    semantic = _object(value.get("semantic"))
    return tuple(
        _rate_for_rank(item)
        for item in (
            physical.get("exact_physical_table_rate"),
            semantic.get("exact_semantic_table_rate"),
            physical.get("numeric_accuracy"),
            physical.get("cell_accuracy"),
            detection.get("table_detection_f1"),
        )
    )


def _complexity_policy() -> dict[str, dict[str, Any]]:
    return {
        "A": {
            "objective_units": 1,
            "model_phases": 1,
            "crop_stage": False,
            "evidence_validation_stage": False,
            "components": ["direct_page_extraction"],
        },
        "B": {
            "objective_units": 3,
            "model_phases": 2,
            "crop_stage": True,
            "evidence_validation_stage": False,
            "components": ["table_detection", "crop_generation", "crop_extraction"],
        },
        "C": {
            "objective_units": 4,
            "model_phases": 2,
            "crop_stage": True,
            "evidence_validation_stage": True,
            "components": [
                "table_detection",
                "crop_generation",
                "crop_extraction",
                "parser_evidence_validation",
            ],
        },
    }


def _failed_score(
    code: str,
    *,
    terminal_sha256: str | None = None,
    terminal_verified: bool = False,
    reference_accessed: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": SCORE_SCHEMA,
        "scoring_status": "failed",
        "conclusion": FAILURE_CONCLUSION,
        "terminal_sha256": terminal_sha256,
        "reference_sha256": None,
        "manifest_sha256": None,
        "terminal_verified_before_reference_access": terminal_verified,
        "reference_accessed_after_terminal_verification": reference_accessed,
        "terminal_unchanged_during_scoring": None,
        "reference_human_reviewed": False,
        "provisional": True,
        "scoring_policy": {
            "weighted_total": False,
            "recommendation_order": [
                "safety",
                "accuracy",
                "provenance",
                "frozen_complexity",
            ],
            "frozen_complexity": _complexity_policy(),
        },
        "strategies": {},
        "recommendation_trace": {"reason": code},
        "failed_contracts": [
            {
                "target": "benchmark",
                "reason_code": code,
            }
        ],
    }
    result["score_checksum"] = _sha256_json(result)
    return result


def _contract_failure(
    target: list[dict[str, Any]],
    case_id: str,
    strategy: str,
    reason_code: str,
    **details: Any,
) -> None:
    target.append(
        {
            "target": case_id,
            "strategy": strategy,
            "reason_code": reason_code,
            **details,
        }
    )


def _reference_human_reviewed(reference: dict[str, Any]) -> bool:
    if reference.get("human_reviewed") is True:
        return True
    status = str(reference.get("human_review_status") or "").casefold()
    return status in {"approved", "human_reviewed", "signed_off", "verified"}


def _table_region(table: dict[str, Any]) -> dict[str, Any]:
    return {"bbox": _table_bbox(table)}


def _table_bbox(value: Any) -> Any:
    if not isinstance(value, dict):
        return None
    for key in ("bbox", "boundary", "normalized_bbox"):
        if key in value:
            return value.get(key)
    for key in ("region", "table_region", "location"):
        nested = value.get(key)
        if isinstance(nested, dict):
            for bbox_key in ("bbox", "boundary", "normalized_bbox"):
                if bbox_key in nested:
                    return nested.get(bbox_key)
    return None


def _canonical_bbox(value: Any, page_bbox: Any) -> list[float] | None:
    if not _valid_bbox(value):
        return None
    bbox = [float(item) for item in value]
    if all(0.0 <= item <= 1.0 for item in bbox):
        return bbox
    if not _valid_bbox(page_bbox):
        return bbox
    page = [float(item) for item in page_bbox]
    width = page[2] - page[0]
    height = page[3] - page[1]
    if width <= 0.0 or height <= 0.0:
        return None
    normalized = [
        (bbox[0] - page[0]) / width,
        (bbox[1] - page[1]) / height,
        (bbox[2] - page[0]) / width,
        (bbox[3] - page[1]) / height,
    ]
    return normalized if _valid_bbox(normalized) else None


def _bbox_iou(left: list[float], right: list[float]) -> float:
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(left[2], right[2])
    y1 = min(left[3], right[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0.0 else 0.0


def _valid_bbox(value: Any) -> bool:
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


def _strict_json_loads(raw: bytes, code: str) -> Any:
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def invalid_constant(_: str) -> None:
        raise ValueError("nonfinite_json_number")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=invalid_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ScoreError(code) from exc


def _normalize(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).split())


def _numeric_like(value: str) -> bool:
    currency = _LEADING_CURRENCY_SYMBOL.fullmatch(value)
    candidate = _normalize(currency.group(2)) if currency else value
    return bool(candidate and _NUMERIC.fullmatch(candidate))


def _first_nonnegative_int(value: dict[str, Any], keys: Iterable[str]) -> int | None:
    for key in keys:
        raw = value.get(key)
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
            return raw
    return None


def _nonnegative(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _finite_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    return None


def _ratio(left: int | float, right: int | float) -> float | None:
    return round(float(left) / float(right), 6) if right else None


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    return round(2.0 * precision * recall / (precision + recall), 6) if precision + recall else 0.0


def _rate_for_rank(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else -1.0


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(_HEX_64.fullmatch(value))


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _deduplicate_objects(values: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[bytes] = set()
    for value in values:
        identity = _canonical_json_bytes(value)
        if identity in seen:
            continue
        seen.add(identity)
        result.append(value)
    return result


def _deduplicate_dicts(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[bytes, dict[str, Any]] = {}
    for value in values:
        unique[_canonical_json_bytes(value)] = value
    return sorted(
        unique.values(),
        key=lambda item: (
            str(item.get("target") or ""),
            str(item.get("strategy") or ""),
            str(item.get("reason_code") or ""),
        ),
    )


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
