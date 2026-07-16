#!/usr/bin/env python3
"""Score a sealed VLM-guided intake development terminal.

The scorer deliberately lives in a separate process.  It verifies and parses
the immutable terminal before opening the human reference, then verifies the
same terminal bytes again after scoring.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import unicodedata
from pathlib import Path
from typing import Any


TERMINAL_SCHEMA = "broker_reports_pdf_vlm_guided_intake_development_terminal_v1"
SEAL_SCHEMA = "broker_reports_pdf_vlm_guided_intake_terminal_seal_v1"
REFERENCE_SCHEMA = "broker_reports_pdf_vlm_guided_intake_development_reference_v1"
SCORE_SCHEMA = "broker_reports_pdf_vlm_guided_intake_development_score_v1"
PASS_LINE = "WORKS_ON_DEVELOPMENT_CORPUS"
FAIL_LINE = "DOES_NOT_WORK_ON_DEVELOPMENT_CORPUS"
PROVIDER_ROUTES = {"candidate_crop", "page_level"}
PRE_PROVIDER_ZERO_CALL_REASONS = {
    "pdf_visual_topology_atom_bbox_invalid",
    "pdf_visual_topology_atom_contract_invalid",
    "pdf_visual_topology_atom_normalization_defect",
    "pdf_visual_topology_atom_outside_selected_source_region",
    "pdf_visual_topology_coordinate_transform_defect",
    "pdf_visual_topology_provider_package_construction_invalid",
}
PROVIDER_ACCOUNTING_FIELDS = (
    "count_token_calls",
    "generate_calls",
    "journal_count_token_calls",
    "journal_generate_calls",
    "counted_input_tokens",
    "actual_input_tokens",
    "output_tokens",
    "package_id",
    "package_hash",
    "request_hash",
    "task_id",
    "attempt_id",
    "provider_profile",
    "provider_profile_revision",
    "model_requested",
    "model_resolved",
    "image_sha256",
    "image_bytes",
    "hidden_retry",
    "provider_failover",
    "journal_checksum",
)
GENERIC_INTERNAL_CODES = {
    "internal_processing_failed",
    "pdf_vlm_guided_intake_internal_processing_failed",
}


class ScoreError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
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
        result = _failed_score(exc.code)
    except OSError:
        result = _failed_score("development_terminal_or_reference_file_unavailable")

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_canonical_json_bytes(result))
    _print_result(result)
    return 0 if result.get("binary_result") == PASS_LINE else 1


def score_paths(
    *,
    terminal_path: Path,
    seal_path: Path,
    reference_path: Path,
) -> dict[str, Any]:
    # Reference access must remain below the initial immutable-terminal read.
    terminal_bytes = terminal_path.read_bytes()
    seal_bytes = seal_path.read_bytes()
    terminal_digest = hashlib.sha256(terminal_bytes).hexdigest()
    terminal_stat = _stat_identity(terminal_path)
    terminal = _verified_terminal(terminal_bytes, seal_bytes)

    reference_bytes = reference_path.read_bytes()
    try:
        reference = json.loads(reference_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScoreError("development_reference_json_invalid") from exc
    _validate_reference(
        reference,
        terminal_digest=terminal_digest,
        manifest_digest=str(terminal.get("manifest_sha256") or ""),
    )

    failures = _evaluate_conditions(terminal, reference)

    terminal_bytes_after = terminal_path.read_bytes()
    seal_bytes_after = seal_path.read_bytes()
    if (
        terminal_bytes_after != terminal_bytes
        or seal_bytes_after != seal_bytes
        or _stat_identity(terminal_path) != terminal_stat
        or hashlib.sha256(terminal_bytes_after).hexdigest() != terminal_digest
    ):
        raise ScoreError("development_terminal_changed_during_scoring")
    _verified_terminal(terminal_bytes_after, seal_bytes_after)

    binary_result = PASS_LINE if not failures else FAIL_LINE
    condition_results = []
    for condition in range(1, 13):
        current = [item for item in failures if item["condition"] == condition]
        condition_results.append(
            {
                "condition": condition,
                "passed": not current,
                "failures": current,
            }
        )
    result = {
        "schema_version": SCORE_SCHEMA,
        "binary_result": binary_result,
        "terminal_sha256": terminal_digest,
        "reference_sha256": hashlib.sha256(reference_bytes).hexdigest(),
        "scorer_pid": os.getpid(),
        "reference_accessed_after_terminal_verification": True,
        "terminal_unchanged_during_scoring": True,
        "conditions": condition_results,
        "failed_contracts": failures,
    }
    result["score_checksum"] = _sha256_json(result)
    return result


def _verified_terminal(terminal_bytes: bytes, seal_bytes: bytes) -> dict[str, Any]:
    try:
        seal = json.loads(seal_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScoreError("development_terminal_seal_json_invalid") from exc
    digest = hashlib.sha256(terminal_bytes).hexdigest()
    if (
        not isinstance(seal, dict)
        or seal.get("schema_version") != SEAL_SCHEMA
        or seal.get("terminal_sha256") != digest
        or seal.get("terminal_size_bytes") != len(terminal_bytes)
    ):
        raise ScoreError("development_terminal_seal_checksum_mismatch")
    try:
        terminal = json.loads(terminal_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScoreError("development_terminal_json_invalid") from exc
    if (
        not isinstance(terminal, dict)
        or terminal.get("schema_version") != TERMINAL_SCHEMA
    ):
        raise ScoreError("development_terminal_schema_invalid")
    return terminal


def _validate_reference(
    value: Any, *, terminal_digest: str, manifest_digest: str
) -> None:
    if not isinstance(value, dict) or value.get("schema_version") != REFERENCE_SCHEMA:
        raise ScoreError("development_reference_schema_invalid")
    if value.get("terminal_sha256") not in {None, terminal_digest}:
        raise ScoreError("development_reference_terminal_binding_invalid")
    if not manifest_digest or value.get("manifest_sha256") != manifest_digest:
        raise ScoreError("development_reference_manifest_binding_invalid")
    unsigned_reference = dict(value)
    reference_checksum = unsigned_reference.pop("reference_checksum", None)
    if not isinstance(reference_checksum, str) or reference_checksum != _sha256_json(
        unsigned_reference
    ):
        raise ScoreError("development_reference_checksum_invalid")
    cases = value.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ScoreError("development_reference_cases_invalid")
    ids = [str(item.get("case_id") or "") for item in cases if isinstance(item, dict)]
    if (
        len(ids) != len(cases)
        or any(not item for item in ids)
        or len(ids) != len(set(ids))
    ):
        raise ScoreError("development_reference_case_identity_invalid")
    for item in cases:
        if item.get("expected_kind") not in {"table", "negative"}:
            raise ScoreError("development_reference_expected_kind_invalid")
        expected_route = item.get("expected_route")
        if (
            item.get("expected_kind") == "table"
            and expected_route not in PROVIDER_ROUTES
        ):
            raise ScoreError("development_reference_expected_route_invalid")
        if (
            item.get("expected_kind") == "negative"
            and expected_route != "skip_obvious_non_table"
        ):
            raise ScoreError("development_reference_expected_route_invalid")
        if not _nonnegative_int(item.get("expected_regions")):
            raise ScoreError("development_reference_expected_regions_invalid")
        technical_assertions = item.get("technical_assertions", [])
        if (
            not isinstance(technical_assertions, list)
            or technical_assertions
            != sorted(set(str(value) for value in technical_assertions))
            or any(
                value != "retained_prefix_accounted" for value in technical_assertions
            )
        ):
            raise ScoreError("development_reference_technical_assertion_invalid")
        regions = item.get("regions")
        if not isinstance(regions, list) or len(regions) != item.get(
            "expected_regions"
        ):
            raise ScoreError("development_reference_region_contract_invalid")
        if item.get("expected_kind") == "negative" and regions:
            raise ScoreError("development_reference_region_contract_invalid")
        for region in regions:
            if not _reference_region_valid(region):
                raise ScoreError("development_reference_region_contract_invalid")


def _evaluate_conditions(
    terminal: dict[str, Any], reference: dict[str, Any]
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    observed_list = terminal.get("cases")
    observed = {
        str(item.get("case_id") or ""): item
        for item in observed_list or []
        if isinstance(item, dict) and item.get("case_id")
    }
    expected = {
        str(item["case_id"]): item
        for item in reference.get("cases") or []
        if isinstance(item, dict)
    }
    provider_contract = _object(
        _object(terminal.get("target_manifest")).get("provider_contract")
    )

    for case_id in sorted(expected):
        ref = expected[case_id]
        case = observed.get(case_id)
        if case is None:
            for condition in (1, 3, 9, 10):
                _fail(
                    failures,
                    condition,
                    case_id,
                    "development_target_terminal_missing",
                )
            continue
        for assertion in ref.get("technical_assertions") or []:
            if assertion == "retained_prefix_accounted" and not (
                _retained_prefix_evidence_verified(case)
            ):
                _fail(
                    failures,
                    10,
                    case_id,
                    "development_retained_prefix_evidence_invalid",
                )
        target = _object(case.get("target_terminal"))
        kind = ref.get("expected_kind")
        route = target.get("route_selected")
        count_calls = target.get("count_tokens_calls")
        generate_calls = target.get("generate_calls")
        accepted = _accepted_region_count(target)
        processability = _decision(
            _object(target.get("intake_decisions")), "processability"
        )

        if kind == "table":
            if (
                route != ref.get("expected_route")
                or not _routing_evidence_verified(target)
                or count_calls != 1
                or generate_calls != 1
                or processability != "processable"
                or _object(target.get("proposal")).get("table_presence") != "present"
            ):
                _fail(
                    failures,
                    1,
                    case_id,
                    "development_positive_route_mismatch",
                )
            if ref.get("broker") == "moomoo" or ref.get("region_contract") in {
                "compound",
                "outside_bbox",
            }:
                if _produced_region_count(target) != ref.get("expected_regions"):
                    _fail(
                        failures,
                        2,
                        case_id,
                        "development_expected_region_count_mismatch",
                    )
        else:
            if (
                route != ref.get("expected_route")
                or not _routing_evidence_verified(target)
                or target.get("terminal_status") != "skipped_obvious_non_table"
                or processability != "processable"
                or count_calls != 0
                or generate_calls != 0
                or accepted != 0
            ):
                _fail(
                    failures,
                    3,
                    case_id,
                    "development_negative_provider_budget_or_acceptance_invalid",
                )

        for region in _adjusted_regions(target):
            included = _strings(region.get("included_word_refs"))
            excluded = _strings(region.get("excluded_word_refs"))
            crossing = _strings(region.get("crossing_word_refs"))
            parent_total = _object(target.get("binding_result")).get(
                "source_accounting", {}
            )
            expected_total = _object(parent_total).get("parent_word_refs_total")
            if (
                not isinstance(expected_total, int)
                or isinstance(expected_total, bool)
                or len(included) + len(excluded) + len(crossing) != expected_total
                or set(included) & set(excluded)
                or set(included) & set(crossing)
                or set(excluded) & set(crossing)
            ):
                _fail(
                    failures,
                    4,
                    case_id,
                    "development_adjusted_atom_accounting_invalid",
                    region_key=region.get("region_key"),
                )
            if region.get("runtime_terminal_status") == "accepted_physical_structure":
                binding = _object(target.get("binding_result"))
                if (
                    not _accepted_region_source_exact(
                        region, page_level=route == "page_level"
                    )
                    or binding.get("value_mutation_performed") is not False
                    or binding.get("model_invented_values_total") != 0
                ):
                    _fail(
                        failures,
                        5,
                        case_id,
                        "development_accepted_adjusted_source_integrity_invalid",
                        region_key=region.get("region_key"),
                    )

        provider_failures = _provider_accounting_failures(
            target,
            provider_routed=route in PROVIDER_ROUTES,
            provider_contract=provider_contract,
        )
        if route in PROVIDER_ROUTES:
            for code in provider_failures:
                _fail(failures, 9, case_id, code)
        elif kind == "negative":
            for code in provider_failures:
                _fail(failures, 3, case_id, code)

        decisions = _object(target.get("intake_decisions"))
        cardinality_failures = _terminal_cardinality_failures(target, decisions)
        for code in cardinality_failures:
            _fail(failures, 10, case_id, code)

        reason_codes = set(_strings(target.get("reason_codes")))
        if (
            reason_codes & GENERIC_INTERNAL_CODES
            or target.get("terminal_status") in GENERIC_INTERNAL_CODES
        ):
            _fail(
                failures,
                11,
                case_id,
                "development_known_failure_collapsed_to_internal",
            )

    correct_regions_by_case = {
        case_id: _correctly_accepted_regions(
            observed.get(case_id), ref, provider_contract=provider_contract
        )
        for case_id, ref in expected.items()
        if ref.get("expected_kind") == "table"
    }
    minimum = reference.get("minimum_correct_acceptances", 4)
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 4:
        minimum = 4
    correct_table_total = sum(
        len(regions) for regions in correct_regions_by_case.values()
    )
    if correct_table_total < minimum:
        _fail(
            failures,
            6,
            "corpus",
            "development_minimum_correct_acceptances_not_met",
            observed=correct_table_total,
            expected=minimum,
        )

    required_brokers = set(
        reference.get("required_brokers") or ["betterment", "drivewealth", "moomoo"]
    )
    accepted_brokers = {
        str(expected[case_id].get("broker") or "")
        for case_id, regions in correct_regions_by_case.items()
        if regions
    }
    accepted_routes = {
        _object(_object(observed.get(case_id)).get("target_terminal")).get(
            "route_selected"
        )
        for case_id, regions in correct_regions_by_case.items()
        if regions
    }
    for broker in sorted(required_brokers - accepted_brokers):
        _fail(
            failures,
            7,
            "corpus",
            "development_required_broker_acceptance_missing",
            broker=broker,
        )
    for route in sorted(PROVIDER_ROUTES - accepted_routes):
        _fail(
            failures,
            7,
            "corpus",
            "development_required_route_acceptance_missing",
            route=route,
        )

    for case_id, ref in expected.items():
        target = _object(_object(observed.get(case_id)).get("target_terminal"))
        accepted_total = _accepted_region_count(target)
        if ref.get("expected_kind") == "negative":
            if accepted_total > 0:
                _fail(
                    failures,
                    8,
                    case_id,
                    "development_false_accepted_table",
                )
        elif accepted_total > int(ref.get("expected_regions") or 0):
            _fail(
                failures,
                8,
                case_id,
                "development_excess_accepted_table_region",
            )
        elif accepted_total and not _accepted_regions_match_expected_positions(
            target, ref
        ):
            _fail(
                failures,
                8,
                case_id,
                "development_incorrect_structure_accepted",
            )

    runner = _object(terminal.get("runner"))
    if (
        terminal.get("reference_accessed") is not False
        or runner.get("reference_argument_supported") is not False
        or not isinstance(runner.get("pid"), int)
        or runner.get("pid") == os.getpid()
    ):
        _fail(
            failures,
            12,
            "corpus",
            "development_reference_process_boundary_invalid",
        )

    manifest_ids = set(terminal.get("manifest_case_ids") or [])
    if manifest_ids != set(expected) or set(observed) != set(expected):
        _fail(
            failures,
            10,
            "corpus",
            "development_manifest_terminal_reference_scope_mismatch",
        )
    for item in terminal.get("failures") or []:
        code = str(_object(item).get("code") or "development_runner_failed")
        _fail(
            failures,
            10,
            str(_object(item).get("case_id") or "corpus"),
            code,
        )
    return sorted(
        _deduplicate(failures),
        key=lambda item: (
            int(item.get("condition") or 0),
            str(item.get("target") or ""),
            str(item.get("reason_code") or ""),
            json.dumps(item, sort_keys=True),
        ),
    )


def _correctly_accepted_regions(
    case: Any,
    reference: dict[str, Any],
    *,
    provider_contract: dict[str, Any],
) -> list[dict[str, Any]]:
    terminal = _object(_object(case).get("target_terminal"))
    if (
        terminal.get("route_selected") != reference.get("expected_route")
        or not _routing_evidence_verified(terminal)
        or _decision(_object(terminal.get("intake_decisions")), "processability")
        != "processable"
        or terminal.get("count_tokens_calls") != 1
        or terminal.get("generate_calls") != 1
        or _object(terminal.get("proposal")).get("table_presence") != "present"
        or terminal.get("hidden_retry") is not False
        or terminal.get("provider_failover") is not False
        or _provider_accounting_failures(
            terminal,
            provider_routed=True,
            provider_contract=provider_contract,
        )
    ):
        return []
    expected = reference.get("regions")
    if not isinstance(expected, list):
        return []
    produced = sorted(_regions(terminal), key=_region_order_key)
    return [
        region
        for index, region in enumerate(produced)
        if region.get("runtime_terminal_status") == "accepted_physical_structure"
        and index < len(expected)
        and _accepted_region_source_exact(
            region, page_level=terminal.get("route_selected") == "page_level"
        )
        and _region_structure_exact(region, expected[index])
    ]


def _accepted_regions_match_expected_positions(
    terminal: dict[str, Any], reference: dict[str, Any]
) -> bool:
    expected = reference.get("regions")
    if not isinstance(expected, list):
        return False
    produced = sorted(_regions(terminal), key=_region_order_key)
    return all(
        index < len(expected) and _region_structure_exact(region, expected[index])
        for index, region in enumerate(produced)
        if region.get("runtime_terminal_status") == "accepted_physical_structure"
    )


def _region_structure_exact(region: dict[str, Any], expected: dict[str, Any]) -> bool:
    material = _object(region.get("materialization"))
    rows = material.get("row_count")
    columns = material.get("column_count")
    if rows != expected.get("rows") or columns != expected.get("columns"):
        return False
    predicted = [["" for _ in range(columns)] for _ in range(rows)]
    for cell in material.get("cells") or []:
        if not isinstance(cell, dict):
            return False
        row = cell.get("row_ordinal")
        column = cell.get("column_ordinal")
        values = cell.get("resolved_source_values")
        if (
            not isinstance(row, int)
            or isinstance(row, bool)
            or not isinstance(column, int)
            or isinstance(column, bool)
            or not isinstance(values, list)
            or not (1 <= row <= rows)
            or not (1 <= column <= columns)
        ):
            return False
        predicted[row - 1][column - 1] = " ".join(str(item) for item in values)
    expected_cells = expected.get("cells")
    normalized_predicted = [[_normalize(cell) for cell in row] for row in predicted]
    normalized_expected = [[_normalize(cell) for cell in row] for row in expected_cells]
    return bool(
        normalized_predicted == normalized_expected
        and material.get("header_rows") == expected.get("header_rows")
        and material.get("spans") == expected.get("spans")
        and material.get("header_hierarchy") == expected.get("header_hierarchy")
    )


def _reference_region_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    rows = value.get("rows")
    columns = value.get("columns")
    cells = value.get("cells")
    return bool(
        isinstance(rows, int)
        and not isinstance(rows, bool)
        and rows > 0
        and isinstance(columns, int)
        and not isinstance(columns, bool)
        and columns > 0
        and isinstance(cells, list)
        and len(cells) == rows
        and all(isinstance(row, list) and len(row) == columns for row in cells)
        and isinstance(value.get("header_rows"), list)
        and isinstance(value.get("spans"), list)
        and isinstance(value.get("header_hierarchy"), list)
    )


def _region_order_key(region: dict[str, Any]) -> tuple[Any, ...]:
    bbox = region.get("normalized_bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        bbox = [0.0, 0.0, 1.0, 1.0]
    return (
        float(bbox[1]),
        float(bbox[0]),
        float(bbox[3]),
        float(bbox[2]),
        str(region.get("region_key") or ""),
    )


def _accepted_region_source_exact(
    region: dict[str, Any], *, page_level: bool = False
) -> bool:
    material = _object(region.get("materialization"))
    assembly = _object(region.get("assembly"))
    source = _object(assembly.get("source_accounting"))
    candidate = _object(region.get("candidate_accounting"))
    scope_candidates_total = candidate.get("scope_candidates_total")
    page_scope_without_parser_candidates = bool(
        page_level
        and isinstance(scope_candidates_total, int)
        and not isinstance(scope_candidates_total, bool)
        and scope_candidates_total == 0
        and candidate.get("included_candidate_ids") == []
        and candidate.get("excluded_candidate_ids") == []
        and candidate.get("crossing_candidate_ids") == []
    )
    selected_candidates_match_scope = bool(
        page_scope_without_parser_candidates
        or set(material.get("selected_candidate_ids") or [])
        == set(candidate.get("included_candidate_ids") or [])
    )
    return bool(
        region.get("crossing_word_refs") == []
        and candidate.get("every_scope_candidate_accounted") is True
        and source.get("all_bound_alternatives_exactly_once") is True
        and assembly.get("value_mutation_performed") is False
        and assembly.get("nearest_cell_fallback_used") is False
        and assembly.get("legacy_grid_consumed") is False
        and material.get("model_invented_values_total") == 0
        and material.get("omitted_candidate_ids") == []
        and material.get("extra_candidate_ids") == []
        and material.get("duplicate_candidate_ids") == []
        and not material.get("structural_provenance_conflicts")
        and selected_candidates_match_scope
        and set(material.get("word_refs") or [])
        == set(region.get("included_word_refs") or [])
    )


def _routing_evidence_verified(target: dict[str, Any]) -> bool:
    evidence = _object(target.get("routing_evidence"))
    if (
        evidence.get("route") != target.get("route_selected")
        or evidence.get("route")
        not in {
            "candidate_crop",
            "page_level",
            "skip_obvious_non_table",
            "upstream_failure",
        }
        or not isinstance(evidence.get("schema_version"), str)
        or not isinstance(
            evidence.get("detection_decision") or evidence.get("detection"), str
        )
        or not isinstance(evidence.get("reason_codes"), list)
        or not isinstance(evidence.get("observations"), dict)
    ):
        return False
    unsigned = dict(evidence)
    stored = unsigned.pop("routing_checksum", None)
    return (
        target.get("routing_evidence_verified") is True
        and isinstance(stored, str)
        and stored == _sha256_json(unsigned)
    )


def _provider_accounting_failures(
    target: dict[str, Any],
    *,
    provider_routed: bool,
    provider_contract: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    accounting = _object(target.get("provider_accounting"))
    expected_fields = {*PROVIDER_ACCOUNTING_FIELDS, "accounting_checksum"}
    if set(accounting) != expected_fields:
        failures.append("development_provider_accounting_projection_invalid")
    unsigned = dict(accounting)
    stored = unsigned.pop("accounting_checksum", None)
    if not isinstance(stored, str) or stored != _sha256_json(unsigned):
        failures.append("development_provider_accounting_checksum_invalid")
    verification = _object(target.get("provider_accounting_verification"))
    verification_unsigned = dict(verification)
    verification_stored = verification_unsigned.pop("verification_checksum", None)
    if not isinstance(verification_stored, str) or verification_stored != _sha256_json(
        verification_unsigned
    ):
        failures.append("development_provider_accounting_verification_checksum_invalid")
    for code in _strings(verification.get("failure_codes")):
        failures.append(code)
    if verification.get("verified") is not True:
        failures.append("development_provider_accounting_cross_view_unverified")
    observed_views = verification.get("views_observed")
    view_checksums = _object(verification.get("view_checksums"))
    required_views = {"terminal", "state"}
    count_calls = target.get("count_tokens_calls")
    generate_calls = target.get("generate_calls")
    if count_calls or generate_calls:
        required_views.add("journal")
    if not isinstance(observed_views, list) or set(observed_views) != required_views:
        failures.append("development_provider_accounting_required_view_missing")
    if verification.get("unique_views_total") != 1:
        failures.append("development_provider_accounting_view_conflict")
    if accounting and (
        set(view_checksums) != required_views
        or any(value != stored for value in view_checksums.values())
    ):
        failures.append("development_provider_accounting_view_checksum_conflict")
    if (
        accounting.get("count_token_calls") != count_calls
        or accounting.get("generate_calls") != target.get("generate_calls")
        or accounting.get("journal_count_token_calls") != count_calls
        or accounting.get("journal_generate_calls") != target.get("generate_calls")
        or accounting.get("hidden_retry") is not False
        or accounting.get("provider_failover") is not False
        or target.get("hidden_retry") is not False
        or target.get("provider_failover") is not False
    ):
        failures.append("development_provider_accounting_counter_mismatch")
    if not provider_routed:
        if not (
            accounting.get("count_token_calls") == 0
            and accounting.get("generate_calls") == 0
            and accounting.get("counted_input_tokens") is None
            and accounting.get("actual_input_tokens") is None
            and accounting.get("output_tokens") is None
        ):
            failures.append("development_provider_zero_call_contract_invalid")
        return sorted(set(failures))

    pre_provider = _pre_provider_zero_call_allowed(target)
    if count_calls == 0 or generate_calls == 0 and count_calls != 1:
        if not pre_provider:
            failures.append("development_provider_pre_provider_reason_invalid")
        elif verification.get("pre_provider_zero_call_allowed") is not True:
            failures.append("development_provider_pre_provider_projection_invalid")
        if not (
            accounting.get("count_token_calls") == 0
            and accounting.get("generate_calls") == 0
            and accounting.get("journal_count_token_calls") == 0
            and accounting.get("journal_generate_calls") == 0
            and accounting.get("counted_input_tokens") is None
            and accounting.get("actual_input_tokens") is None
            and accounting.get("output_tokens") is None
        ):
            failures.append("development_provider_zero_call_contract_invalid")
        return sorted(set(failures))

    if count_calls != 1:
        failures.append("development_provider_count_token_call_cardinality_invalid")
    if generate_calls not in {0, 1}:
        failures.append("development_provider_generate_call_cardinality_invalid")
    counted = accounting.get("counted_input_tokens")
    image_bytes = accounting.get("image_bytes")
    image_sha256 = accounting.get("image_sha256")
    if not isinstance(counted, int) or isinstance(counted, bool) or counted <= 0:
        failures.append("development_provider_counted_input_tokens_missing")
    if generate_calls == 1:
        actual = accounting.get("actual_input_tokens")
        output = accounting.get("output_tokens")
        if not isinstance(actual, int) or isinstance(actual, bool) or actual <= 0:
            failures.append("development_provider_actual_input_tokens_missing")
        elif actual != counted:
            failures.append("development_provider_input_token_count_mismatch")
        if not isinstance(output, int) or isinstance(output, bool) or output < 0:
            failures.append("development_provider_output_tokens_missing")
        if not _nonempty(accounting.get("attempt_id")):
            failures.append("development_provider_attempt_identity_missing")
        if any(
            not _nonempty(accounting.get(field))
            for field in ("provider_profile", "provider_profile_revision")
        ):
            failures.append("development_provider_identity_missing")
        if not _nonempty(accounting.get("model_resolved")):
            failures.append("development_provider_model_identity_missing")
    elif (
        accounting.get("actual_input_tokens") is not None
        or accounting.get("output_tokens") is not None
    ):
        failures.append("development_provider_unexpected_generate_usage")
    for fields, code in (
        (
            ("package_id", "package_hash"),
            "development_provider_package_identity_missing",
        ),
        (("request_hash", "task_id"), "development_provider_request_identity_missing"),
        (("model_requested",), "development_provider_model_identity_missing"),
    ):
        if any(not _nonempty(accounting.get(field)) for field in fields):
            failures.append(code)
    if (
        not isinstance(image_bytes, int)
        or isinstance(image_bytes, bool)
        or image_bytes <= 0
        or not isinstance(image_sha256, str)
        or len(image_sha256) != 64
    ):
        failures.append("development_provider_image_identity_missing")
    expected_profile = provider_contract.get("provider_profile")
    expected_model = provider_contract.get("model_id")
    if generate_calls == 1 and (
        not expected_profile or accounting.get("provider_profile") != expected_profile
    ):
        failures.append("development_provider_manifest_profile_mismatch")
    if not expected_model or (
        accounting.get("model_requested") != expected_model
        or (generate_calls == 1 and accounting.get("model_resolved") != expected_model)
    ):
        failures.append("development_provider_manifest_model_mismatch")
    return sorted(set(failures))


def _pre_provider_zero_call_allowed(target: dict[str, Any]) -> bool:
    reason_codes = set(_strings(target.get("reason_codes")))
    return bool(
        target.get("route_selected") in PROVIDER_ROUTES
        and target.get("terminal_status") == "guided_upstream_blocked"
        and target.get("count_tokens_calls") == 0
        and target.get("generate_calls") == 0
        and reason_codes
        and reason_codes <= PRE_PROVIDER_ZERO_CALL_REASONS
    )


def _terminal_cardinality_failures(
    target: dict[str, Any], decisions: dict[str, Any]
) -> list[str]:
    failures = _strings(target.get("cardinality_failure_codes"))
    if not target.get("terminal_status"):
        failures.append("development_terminal_status_missing")
    expected_counts = {
        "target_outcomes_total": (1, "development_target_outcome_cardinality_invalid"),
        "terminal_payloads_total": (1, "development_terminal_cardinality_invalid"),
        "target_state_payloads_total": (
            1,
            "development_target_state_cardinality_invalid",
        ),
        "proposal_outcomes_total": (
            1,
            "development_proposal_outcome_cardinality_invalid",
        ),
        "proposal_outcome_views_total": (
            2,
            "development_proposal_outcome_view_cardinality_invalid",
        ),
        "binding_outcomes_total": (
            1,
            "development_binding_outcome_cardinality_invalid",
        ),
        "binding_outcome_views_total": (
            2,
            "development_binding_outcome_view_cardinality_invalid",
        ),
        "detection_decisions_total": (
            1,
            "development_detection_decision_cardinality_invalid",
        ),
        "processability_decisions_total": (
            1,
            "development_processability_decision_cardinality_invalid",
        ),
        "holdout_decisions_total": (
            1,
            "development_holdout_decision_cardinality_invalid",
        ),
    }
    for field, (expected, code) in expected_counts.items():
        if target.get(field) != expected:
            failures.append(code)
    if not _outcome_verified(
        target.get("proposal_outcome"),
        expected_keys={
            "status",
            "proposal_scope",
            "proposal_checksum",
            "raw_proposal_checksum",
            "reason_codes",
            "outcome_checksum",
        },
        statuses={"not_attempted", "persisted", "invalid", "missing"},
    ):
        failures.append("development_proposal_outcome_checksum_invalid")
    if not _outcome_verified(
        target.get("binding_outcome"),
        expected_keys={
            "status",
            "binding_checksum",
            "reason_codes",
            "outcome_checksum",
        },
        statuses={"not_applicable", "attempted_failed", "completed"},
    ):
        failures.append("development_binding_outcome_checksum_invalid")
    for name in ("detection", "processability", "holdout"):
        if not _decision(decisions, name):
            failures.append(f"development_{name}_decision_missing")
    if target.get("terminal_cardinality_verified") is not True and not failures:
        failures.append("development_terminal_cardinality_unverified")
    return sorted(set(failures))


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _outcome_verified(
    value: Any, *, expected_keys: set[str], statuses: set[str]
) -> bool:
    if not isinstance(value, dict) or set(value) != expected_keys:
        return False
    unsigned = dict(value)
    stored = unsigned.pop("outcome_checksum", None)
    reasons = value.get("reason_codes")
    return bool(
        value.get("status") in statuses
        and isinstance(reasons, list)
        and reasons == sorted(set(str(item) for item in reasons))
        and isinstance(stored, str)
        and stored == _sha256_json(unsigned)
    )


def _retained_prefix_evidence_verified(case: dict[str, Any]) -> bool:
    evidence = _object(_object(case.get("source")).get("retained_prefix_evidence"))
    unsigned = dict(evidence)
    stored = unsigned.pop("evidence_checksum", None)
    numeric_keys = (
        "source_pages_total",
        "completed_pages_total",
        "missing_tail_pages_total",
        "first_missing_page_number",
        "selected_page_number",
        "inventory_objects_retained_total",
        "inventory_objects_limit",
        "inventory_objects_would_be_total",
    )
    if any(
        not isinstance(evidence.get(key), int) or isinstance(evidence.get(key), bool)
        for key in numeric_keys
    ):
        return False
    return bool(
        evidence.get("retained_prefix_accounted") is True
        and isinstance(stored, str)
        and stored == _sha256_json(unsigned)
        and evidence.get("document_projection_status") == "partial"
        and "pdf_layout_document_inventory_budget_exceeded"
        in (evidence.get("document_reason_codes") or [])
        and evidence.get("selected_page_projection_status") == "complete"
        and evidence.get("source_pages_total")
        == evidence.get("completed_pages_total")
        + evidence.get("missing_tail_pages_total")
        and evidence.get("first_missing_page_number")
        == evidence.get("completed_pages_total") + 1
        and evidence.get("selected_page_number")
        <= evidence.get("completed_pages_total")
        and evidence.get("inventory_objects_retained_total")
        <= evidence.get("inventory_objects_limit")
        < evidence.get("inventory_objects_would_be_total")
    )


def _regions(target: dict[str, Any]) -> list[dict[str, Any]]:
    binding = _object(target.get("binding_result"))
    return [
        item for item in binding.get("region_results") or [] if isinstance(item, dict)
    ]


def _adjusted_regions(target: dict[str, Any]) -> list[dict[str, Any]]:
    parent = _object(target.get("binding_result")).get("parent_source_bbox")
    return [item for item in _regions(target) if item.get("source_bbox") != parent]


def _accepted_region_count(target: dict[str, Any]) -> int:
    return sum(
        item.get("runtime_terminal_status") == "accepted_physical_structure"
        for item in _regions(target)
    )


def _produced_region_count(target: dict[str, Any]) -> int:
    return len(_regions(target))


def _decision(decisions: dict[str, Any], name: str) -> str:
    value = _object(decisions.get(name)).get("decision")
    return str(value or "")


def _fail(
    failures: list[dict[str, Any]],
    condition: int,
    target: str,
    reason_code: str,
    **details: Any,
) -> None:
    failures.append(
        {
            "condition": condition,
            "target": target,
            "reason_code": reason_code,
            **{key: value for key, value in details.items() if value is not None},
        }
    )


def _failed_score(code: str) -> dict[str, Any]:
    failure = {"condition": 12, "target": "corpus", "reason_code": code}
    result = {
        "schema_version": SCORE_SCHEMA,
        "binary_result": FAIL_LINE,
        "terminal_sha256": None,
        "reference_sha256": None,
        "scorer_pid": os.getpid(),
        "reference_accessed_after_terminal_verification": False,
        "terminal_unchanged_during_scoring": False,
        "conditions": [
            {
                "condition": number,
                "passed": number != 12,
                "failures": [failure] if number == 12 else [],
            }
            for number in range(1, 13)
        ],
        "failed_contracts": [failure],
    }
    result["score_checksum"] = _sha256_json(result)
    return result


def _print_result(result: dict[str, Any]) -> None:
    line = str(result.get("binary_result") or FAIL_LINE)
    print(line)
    if line == FAIL_LINE:
        for failure in result.get("failed_contracts") or []:
            details = " ".join(
                f"{key}={value}"
                for key, value in failure.items()
                if key not in {"condition", "target", "reason_code"}
            )
            suffix = f" {details}" if details else ""
            print(
                f"condition_{failure.get('condition')} "
                f"target={failure.get('target')} "
                f"reason={failure.get('reason_code')}{suffix}"
            )


def _stat_identity(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, getattr(stat, "st_ino", 0)


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _normalize(value: Any) -> str:
    rendered = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(rendered.split()).strip()


def _deduplicate(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[bytes, dict[str, Any]] = {}
    for value in values:
        unique[_canonical_json_bytes(value)] = value
    return list(unique.values())


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
