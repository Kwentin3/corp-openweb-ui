#!/usr/bin/env python3
"""Score a sealed PDF structural holdout against a post-terminal reference."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.pdf_hybrid_contracts import (  # noqa: E402
    sha256_json,
    validate_binding_output_shape,
)
from broker_reports_gate1.pdf_structural_repair_holdout_contracts import (  # noqa: E402
    PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2,
    PdfStructuralRepairHoldoutContractFactory,
)


REFERENCE_SCHEMA = "broker_reports_pdf_structural_holdout_reference_v1"
REFERENCE_SCHEMA_V2 = "broker_reports_pdf_structural_holdout_reference_v2"
SCORE_PRIVATE_SCHEMA = "broker_reports_pdf_structural_holdout_score_private_v1"
SCORE_PRIVATE_SCHEMA_V2 = "broker_reports_pdf_structural_holdout_score_private_v2"
SCORE_SAFE_SCHEMA = "broker_reports_pdf_structural_holdout_score_safe_v1"
SCORE_SAFE_SCHEMA_V2 = "broker_reports_pdf_structural_holdout_score_safe_v2"
REFERENCE_KEYS = {
    "schema_version",
    "holdout_id",
    "preregistration_file_sha256",
    "terminal_seal_hash",
    "targets",
    "reference_checksum",
}
REFERENCE_TARGET_KEYS = {
    "target_id",
    "rows",
    "columns",
    "header_rows",
    "spans",
    "header_hierarchy",
    "cells",
    "review_status",
}
REFERENCE_TARGET_KEYS_V2 = REFERENCE_TARGET_KEYS | {"unsupported_reason_codes"}
UNSUPPORTED_REFERENCE_REASON_CODES = frozenset(
    {
        "human_verified_no_semantic_table",
        "human_verified_multiple_disjoint_tables",
        "human_verified_page_region_not_single_table",
        "human_verified_parser_candidate_false_positive",
        "human_verified_table_topology_outside_supported_scope",
    }
)
CERTIFYING_HOLDOUT_CLASSES = frozenset(
    {
        "fresh_holdout",
        "fresh_holdout_v2",
        "fresh_holdout_v3",
        "fresh_holdout_v4",
        "fresh_holdout_v5",
    }
)


class HoldoutScoreError(RuntimeError):
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preregistration-private", required=True)
    parser.add_argument("--terminal-private", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    return score_holdout(
        preregistration_path=Path(args.preregistration_private),
        terminal_path=Path(args.terminal_private),
        reference_path=Path(args.reference),
        output_dir=Path(args.output_dir),
    )


def score_holdout(
    *,
    preregistration_path: Path,
    terminal_path: Path,
    reference_path: Path,
    output_dir: Path,
) -> int:
    preregistration_path = preregistration_path.resolve()
    terminal_path = terminal_path.resolve()
    reference_path = reference_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise HoldoutScoreError("pdf_structural_holdout_score_output_exists")
    preregistration, preregistration_raw_sha256 = _load_json(
        preregistration_path, dict, "preregistration"
    )
    terminal, terminal_raw_sha256_before = _load_json(
        terminal_path, dict, "terminal"
    )
    contracts = PdfStructuralRepairHoldoutContractFactory().create()
    errors = contracts.validate_terminal_against_preregistration(
        terminal=terminal,
        preregistration=preregistration,
        preregistration_file_sha256=preregistration_raw_sha256,
    )
    if errors:
        raise HoldoutScoreError(errors[0])
    _verify_source_freeze(_object(preregistration.get("frozen_source")))

    reference, reference_raw_sha256 = _load_json(
        reference_path, dict, "reference"
    )
    references = _validate_reference(
        reference,
        holdout_id=str(terminal.get("holdout_id") or ""),
        preregistration_file_sha256=preregistration_raw_sha256,
        terminal_seal_hash=str(terminal.get("terminal_seal_hash") or ""),
        policy_version=str(terminal.get("policy_version") or ""),
    )
    terminal_after, terminal_raw_sha256_after = _load_json(
        terminal_path, dict, "terminal_after_reference"
    )
    if (
        terminal_raw_sha256_after != terminal_raw_sha256_before
        or terminal_after != terminal
    ):
        raise HoldoutScoreError(
            "pdf_structural_holdout_terminal_changed_during_scoring"
        )
    errors = contracts.validate_terminal_against_preregistration(
        terminal=terminal_after,
        preregistration=preregistration,
        preregistration_file_sha256=preregistration_raw_sha256,
    )
    if errors:
        raise HoldoutScoreError(errors[0])
    _verify_source_freeze(_object(preregistration.get("frozen_source")))

    target_scores: dict[str, dict[str, Any]] = {}
    terminal_targets = _object(terminal.get("targets"))
    for target_id in sorted(terminal_targets):
        target = _object(terminal_targets.get(target_id))
        binding = _validate_independent_scoring_chain(target)
        target_scores[target_id] = _score_binding(
            reference=references[target_id],
            binding=binding,
            package=_object(target.get("visual_package")),
        )
    private = {
        "schema_version": (
            SCORE_PRIVATE_SCHEMA_V2
            if terminal.get("policy_version")
            == PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2
            else SCORE_PRIVATE_SCHEMA
        ),
        "holdout_id": terminal.get("holdout_id"),
        "execution_class": terminal.get("execution_class"),
        "certification_eligible": terminal.get("certification_eligible"),
        "corpus_policy": terminal.get("corpus_policy"),
        "preregistration_file_sha256": preregistration_raw_sha256,
        "terminal_file_sha256": terminal_raw_sha256_before,
        "terminal_seal_hash": terminal.get("terminal_seal_hash"),
        "reference_file_sha256": reference_raw_sha256,
        "reference_checksum": reference.get("reference_checksum"),
        "target_scores": target_scores,
        "terminal_unchanged_during_scoring": True,
    }
    private["artifact_checksum"] = sha256_json(private)
    safe_targets = [
        {"target_id": target_id, **target_scores[target_id]}
        for target_id in sorted(target_scores)
    ]
    safe = {
        "schema_version": (
            SCORE_SAFE_SCHEMA_V2
            if terminal.get("policy_version")
            == PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2
            else SCORE_SAFE_SCHEMA
        ),
        "holdout_id": terminal.get("holdout_id"),
        "execution_class": terminal.get("execution_class"),
        "certification_eligible": terminal.get("certification_eligible"),
        "corpus_policy": terminal.get("corpus_policy"),
        "terminal_file_sha256": terminal_raw_sha256_before,
        "terminal_seal_hash": terminal.get("terminal_seal_hash"),
        "reference_file_sha256": reference_raw_sha256,
        "reference_bound_to_terminal_seal": True,
        "terminal_unchanged_during_scoring": True,
        "targets": safe_targets,
        "metrics": {
            "targets": len(safe_targets),
            "supported_targets": sum(
                item.get("support_classification") == "supported"
                for item in safe_targets
            ),
            "unsupported_targets": sum(
                item.get("support_classification") == "unsupported"
                for item in safe_targets
            ),
            "unsupported_abstentions": sum(
                item.get("unsupported_abstention") is True
                for item in safe_targets
            ),
            "unsupported_false_positive_bindings": sum(
                item.get("unsupported_false_positive_binding") is True
                for item in safe_targets
            ),
            "accepted_bindings_available": sum(
                item.get("solver_binding_available") is True
                for item in safe_targets
            ),
            "grid_dimensions_exact_targets": sum(
                item.get("grid_dimensions_exact") is True for item in safe_targets
            ),
            "topology_exact_targets": sum(
                item.get("topology_exact") is True for item in safe_targets
            ),
            "all_cells_exact_targets": sum(
                item.get("all_cells_exact") is True for item in safe_targets
            ),
            "cells_exact": sum(
                int(item.get("cells_exact") or 0) for item in safe_targets
            ),
            "cells_total": sum(
                int(item.get("cells_total") or 0) for item in safe_targets
            ),
            "hallucinated_nonempty": sum(
                int(item.get("hallucinated_nonempty") or 0)
                for item in safe_targets
            ),
            "omitted_nonempty": sum(
                int(item.get("omitted_nonempty") or 0)
                for item in safe_targets
            ),
        },
        "scoring_role": (
            "post_terminal_diagnostic_only"
            if terminal.get("execution_class") in CERTIFYING_HOLDOUT_CLASSES
            else "development_regression_diagnostic_non_certifying"
        ),
        "reference_used_by_solver": False,
    }
    safe["artifact_checksum"] = sha256_json(safe)
    _assert_safe(safe)
    output_dir.mkdir(parents=True, exist_ok=False)
    _write_json(output_dir / "holdout.score.private.json", private)
    _write_json(output_dir / "holdout.score.safe.json", safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _validate_reference(
    value: dict[str, Any],
    *,
    holdout_id: str,
    preregistration_file_sha256: str,
    terminal_seal_hash: str,
    policy_version: str = "",
) -> dict[str, dict[str, Any]]:
    if set(value) != REFERENCE_KEYS:
        raise HoldoutScoreError("pdf_structural_holdout_reference_keys_invalid")
    unsigned = dict(value)
    stored_checksum = unsigned.pop("reference_checksum", None)
    if stored_checksum != sha256_json(unsigned):
        raise HoldoutScoreError(
            "pdf_structural_holdout_reference_checksum_invalid"
        )
    is_v2 = policy_version == PDF_STRUCTURAL_HOLDOUT_POLICY_VERSION_V2
    expected_schema = REFERENCE_SCHEMA_V2 if is_v2 else REFERENCE_SCHEMA
    if (
        value.get("schema_version") != expected_schema
        or value.get("holdout_id") != holdout_id
        or value.get("preregistration_file_sha256")
        != preregistration_file_sha256
        or value.get("terminal_seal_hash") != terminal_seal_hash
    ):
        raise HoldoutScoreError("pdf_structural_holdout_reference_identity_invalid")
    raw_targets = value.get("targets")
    targets = _dicts(raw_targets)
    if not isinstance(raw_targets, list) or len(targets) != len(raw_targets):
        raise HoldoutScoreError(
            "pdf_structural_holdout_reference_target_list_invalid"
        )
    expected_ids = {"holdout_001", "holdout_002", "holdout_003"}
    result: dict[str, dict[str, Any]] = {}
    for target in targets:
        target_id = str(target.get("target_id") or "")
        if (
            set(target)
            != (REFERENCE_TARGET_KEYS_V2 if is_v2 else REFERENCE_TARGET_KEYS)
            or target_id in result
            or target_id not in expected_ids
            or not (
                _valid_supported_reference(target, is_v2=is_v2)
                or (is_v2 and _valid_unsupported_reference(target))
            )
        ):
            raise HoldoutScoreError(
                "pdf_structural_holdout_reference_target_invalid"
            )
        result[target_id] = target
    if set(result) != expected_ids:
        raise HoldoutScoreError(
            "pdf_structural_holdout_reference_target_set_invalid"
        )
    return result


def _valid_supported_reference(
    target: dict[str, Any], *, is_v2: bool
) -> bool:
    rows = target.get("rows")
    columns = target.get("columns")
    header_rows = target.get("header_rows")
    spans = target.get("spans")
    header_hierarchy = target.get("header_hierarchy")
    cells = target.get("cells")
    unsupported_reasons = target.get("unsupported_reason_codes", [])
    return bool(
        _positive_int(rows)
        and _positive_int(columns)
        and isinstance(header_rows, list)
        and not any(not _positive_int(item) for item in header_rows)
        and header_rows == sorted(set(header_rows))
        and not any(int(item) > int(rows or 0) for item in header_rows)
        and isinstance(spans, list)
        and not any(
            not _valid_span(item, rows=int(rows or 0), columns=int(columns or 0))
            for item in spans
        )
        and spans == sorted(spans, key=_span_sort_key)
        and len(set(_canonical_span_geometry(spans))) == len(spans)
        and isinstance(header_hierarchy, list)
        and not any(
            not _valid_header_relation(
                item, rows=int(rows or 0), columns=int(columns or 0)
            )
            for item in header_hierarchy
        )
        and header_hierarchy
        == sorted(header_hierarchy, key=_header_relation_sort_key)
        and len({sha256_json(item) for item in header_hierarchy})
        == len(header_hierarchy)
        and target.get("review_status") == "human_verified"
        and isinstance(cells, list)
        and len(cells) == rows
        and not any(
            not isinstance(row, list)
            or len(row) != columns
            or any(not isinstance(cell, str) for cell in row)
            for row in cells
        )
        and (not is_v2 or unsupported_reasons == [])
    )


def _valid_unsupported_reference(target: dict[str, Any]) -> bool:
    reasons = target.get("unsupported_reason_codes")
    return bool(
        target.get("review_status") == "human_verified_unsupported"
        and target.get("rows") == 0
        and target.get("columns") == 0
        and target.get("header_rows") == []
        and target.get("spans") == []
        and target.get("header_hierarchy") == []
        and target.get("cells") == []
        and isinstance(reasons, list)
        and 1 <= len(reasons) <= 3
        and reasons == sorted(set(reasons))
        and all(item in UNSUPPORTED_REFERENCE_REASON_CODES for item in reasons)
    )


def _validate_independent_scoring_chain(
    target: dict[str, Any],
) -> dict[str, Any] | None:
    consensus = _object(target.get("consensus_result"))
    binding = target.get("accepted_binding")
    materialization = target.get("materialization")
    if consensus.get("terminal_status") != "accepted_supplied_consensus":
        if binding is not None or materialization is not None:
            raise HoldoutScoreError(
                "pdf_structural_holdout_score_nonaccepted_binding_invalid"
            )
        return None
    if not isinstance(binding, dict) or not isinstance(materialization, dict):
        raise HoldoutScoreError(
            "pdf_structural_holdout_score_accepted_chain_missing"
        )
    shape_errors = validate_binding_output_shape(binding)
    if shape_errors or binding.get("decision") != "bound":
        raise HoldoutScoreError(
            "pdf_structural_holdout_score_binding_shape_invalid"
        )
    package = _object(target.get("visual_package"))
    crop = _object(package.get("crop_identity"))
    dictionary = _object(package.get("private_candidate_dictionary"))
    if (
        not dictionary
        or any(
            not isinstance(candidate_id, str)
            or not candidate_id
            or not isinstance(candidate, dict)
            for candidate_id, candidate in dictionary.items()
        )
        or binding.get("package_id") != package.get("package_id")
        or binding.get("crop_sha256") != crop.get("crop_sha256")
        or binding.get("candidate_dictionary_hash")
        != package.get("candidate_dictionary_hash")
    ):
        raise HoldoutScoreError(
            "pdf_structural_holdout_score_binding_identity_invalid"
        )
    used = [
        candidate_id
        for row in _dicts(binding.get("rows"))
        for cell in row.get("cells") or []
        for candidate_id in cell
    ]
    dictionary_ids = sorted(dictionary)
    if sorted(used) != dictionary_ids or len(used) != len(set(used)):
        raise HoldoutScoreError(
            "pdf_structural_holdout_score_candidate_accounting_invalid"
        )
    if (
        materialization.get("package_id") != package.get("package_id")
        or materialization.get("binding_output_hash") != sha256_json(binding)
        or materialization.get("crop_sha256") != binding.get("crop_sha256")
        or materialization.get("candidate_dictionary_hash")
        != binding.get("candidate_dictionary_hash")
        or materialization.get("row_count") != binding.get("row_count")
        or materialization.get("column_count") != binding.get("column_count")
        or materialization.get("header_rows") != binding.get("header_rows")
        or materialization.get("header_hierarchy")
        != binding.get("header_hierarchy")
        or materialization.get("spans") != binding.get("spans")
        or materialization.get("selected_candidate_ids") != dictionary_ids
        or materialization.get("omitted_candidate_ids") != []
        or materialization.get("extra_candidate_ids") != []
        or materialization.get("duplicate_candidate_ids") != []
        or materialization.get("model_invented_values_total") != 0
    ):
        raise HoldoutScoreError(
            "pdf_structural_holdout_score_materialization_chain_invalid"
        )
    return binding


def _score_binding(
    *, reference: dict[str, Any], binding: Any, package: dict[str, Any]
) -> dict[str, Any]:
    if reference.get("review_status") == "human_verified_unsupported":
        binding_available = isinstance(binding, dict)
        return {
            "support_classification": "unsupported",
            "reference_reason_codes": list(
                reference.get("unsupported_reason_codes") or []
            ),
            "solver_binding_available": binding_available,
            "unsupported_abstention": not binding_available,
            "unsupported_false_positive_binding": binding_available,
            **_unavailable_score(),
        }
    if not isinstance(binding, dict):
        return {
            "support_classification": "supported",
            "reference_reason_codes": [],
            "solver_binding_available": False,
            "unsupported_abstention": False,
            "unsupported_false_positive_binding": False,
            **_unavailable_score(),
        }
    rows = int(binding.get("row_count") or 0)
    columns = int(binding.get("column_count") or 0)
    dictionary = _object(package.get("private_candidate_dictionary"))
    predicted = [["" for _ in range(columns)] for _ in range(rows)]
    for row in _dicts(binding.get("rows")):
        row_index = int(row.get("row_ordinal") or 0) - 1
        for column_index, cell in enumerate(row.get("cells") or []):
            if (
                0 <= row_index < rows
                and column_index < columns
                and isinstance(cell, list)
            ):
                predicted[row_index][column_index] = " ".join(
                    str(
                        _object(dictionary.get(str(candidate_id))).get(
                            "exact_source_span"
                        )
                        or ""
                    )
                    for candidate_id in cell
                )
    expected = reference.get("cells") or []
    binding_span_geometry = _canonical_span_geometry(binding.get("spans"))
    reference_span_geometry = _canonical_span_geometry(reference.get("spans"))
    height = max(len(expected), len(predicted))
    width = max(
        max((len(row) for row in expected if isinstance(row, list)), default=0),
        max((len(row) for row in predicted), default=0),
    )
    pairs: list[tuple[str, str]] = []
    for row_index in range(height):
        for column_index in range(width):
            left = (
                expected[row_index][column_index]
                if row_index < len(expected)
                and isinstance(expected[row_index], list)
                and column_index < len(expected[row_index])
                else ""
            )
            right = (
                predicted[row_index][column_index]
                if row_index < len(predicted)
                and column_index < len(predicted[row_index])
                else ""
            )
            pairs.append((_normalize(left), _normalize(right)))
    return {
        "support_classification": "supported",
        "reference_reason_codes": [],
        "solver_binding_available": True,
        "unsupported_abstention": False,
        "unsupported_false_positive_binding": False,
        "available": True,
        "grid_dimensions_exact": rows == int(reference.get("rows") or 0)
        and columns == int(reference.get("columns") or 0),
        "header_rows_exact": binding.get("header_rows")
        == reference.get("header_rows"),
        "spans_exact": binding_span_geometry == reference_span_geometry,
        "header_hierarchy_exact": binding.get("header_hierarchy")
        == reference.get("header_hierarchy"),
        "topology_exact": bool(
            rows == int(reference.get("rows") or 0)
            and columns == int(reference.get("columns") or 0)
            and binding.get("header_rows") == reference.get("header_rows")
            and binding_span_geometry == reference_span_geometry
            and binding.get("header_hierarchy")
            == reference.get("header_hierarchy")
        ),
        "cells_exact": sum(left == right for left, right in pairs),
        "cells_total": len(pairs),
        "all_cells_exact": bool(pairs and all(left == right for left, right in pairs)),
        "hallucinated_nonempty": sum(
            not left and bool(right) for left, right in pairs
        ),
        "omitted_nonempty": sum(bool(left) and not right for left, right in pairs),
    }


def _unavailable_score() -> dict[str, Any]:
    return {
        "available": False,
        "grid_dimensions_exact": False,
        "header_rows_exact": False,
        "spans_exact": False,
        "header_hierarchy_exact": False,
        "topology_exact": False,
        "cells_exact": 0,
        "cells_total": 0,
        "all_cells_exact": False,
        "hallucinated_nonempty": 0,
        "omitted_nonempty": 0,
    }


def _assert_safe(value: Any) -> None:
    forbidden_keys = {
        "accepted_binding",
        "cells",
        "exact_source_span",
        "private_candidate_dictionary",
        "reference_path",
        "terminal_path",
    }

    def walk(current: Any) -> None:
        if isinstance(current, dict):
            overlap = {str(key) for key in current} & forbidden_keys
            if overlap:
                raise HoldoutScoreError(
                    "pdf_structural_holdout_score_safe_forbidden_key"
                )
            for item in current.values():
                walk(item)
        elif isinstance(current, list):
            for item in current:
                walk(item)
        elif isinstance(current, str) and re.search(
            r"(?:[A-Za-z]:\\|/Users/|/home/|\\Users\\)", current
        ):
            raise HoldoutScoreError(
                "pdf_structural_holdout_score_safe_private_path"
            )

    walk(value)


def _verify_source_freeze(frozen: dict[str, Any]) -> None:
    paths = set((SERVICE_ROOT / "broker_reports_gate1").rglob("*.py"))
    paths.add(
        (
            SCRIPT_DIR / "local_pdf_structural_repair_holdout.py"
        ).resolve()
    )
    paths.add(Path(__file__).resolve())
    inventory: list[dict[str, Any]] = []
    for path in sorted(
        paths, key=lambda item: item.resolve().relative_to(REPO_ROOT).as_posix()
    ):
        resolved = path.resolve()
        try:
            relative = resolved.relative_to(REPO_ROOT).as_posix()
        except ValueError as exc:
            raise HoldoutScoreError(
                "pdf_structural_holdout_score_source_outside_repository"
            ) from exc
        raw = resolved.read_bytes()
        inventory.append(
            {
                "repo_relative_path": relative,
                "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    current = {
        "git_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
        ).strip(),
        "inventory": inventory,
        "inventory_checksum": sha256_json(inventory),
    }
    if current != frozen:
        raise HoldoutScoreError(
            "pdf_structural_holdout_score_source_freeze_mismatch"
        )


def _load_json(
    path: Path, expected_type: type, subject: str
) -> tuple[Any, str]:
    raw = path.read_bytes()
    try:
        value = json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=_strict_pairs(subject),
            parse_constant=lambda item: _raise_nonfinite(subject, item),
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HoldoutScoreError(
            f"pdf_structural_holdout_score_json_invalid:{subject}"
        ) from exc
    if not isinstance(value, expected_type):
        raise HoldoutScoreError(
            f"pdf_structural_holdout_score_json_root_invalid:{subject}"
        )
    return value, hashlib.sha256(raw).hexdigest()


def _strict_pairs(subject: str):
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise HoldoutScoreError(
                    f"pdf_structural_holdout_score_duplicate_key:{subject}:{key}"
                )
            result[key] = value
        return result

    return pairs


def _raise_nonfinite(subject: str, value: str) -> Any:
    raise HoldoutScoreError(
        f"pdf_structural_holdout_score_nonfinite:{subject}:{value}"
    )


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


def _normalize(value: Any) -> str:
    rendered = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(rendered.split()).strip()


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _valid_span(value: Any, *, rows: int, columns: int) -> bool:
    item = _object(value)
    if set(item) != {
        "start_row",
        "end_row",
        "start_column",
        "end_column",
        "relation",
    }:
        return False
    start_row = item.get("start_row")
    end_row = item.get("end_row")
    start_column = item.get("start_column")
    end_column = item.get("end_column")
    return bool(
        all(
            _positive_int(number)
            for number in (start_row, end_row, start_column, end_column)
        )
        and int(start_row) <= int(end_row) <= rows
        and int(start_column) <= int(end_column) <= columns
        and (
            int(start_row) != int(end_row)
            or int(start_column) != int(end_column)
        )
        and item.get("relation") in {"merged", "spanning_header"}
    )


def _valid_header_relation(value: Any, *, rows: int, columns: int) -> bool:
    item = _object(value)
    if set(item) != {
        "parent_row",
        "parent_column",
        "child_start_column",
        "child_end_column",
    }:
        return False
    parent_row = item.get("parent_row")
    parent_column = item.get("parent_column")
    child_start = item.get("child_start_column")
    child_end = item.get("child_end_column")
    return bool(
        all(
            _positive_int(number)
            for number in (parent_row, parent_column, child_start, child_end)
        )
        and int(parent_row) <= rows
        and int(parent_column) <= columns
        and int(child_start) <= int(child_end) <= columns
    )


def _span_sort_key(value: dict[str, Any]) -> tuple[int, int, int, int]:
    return (
        int(value["start_row"]),
        int(value["start_column"]),
        int(value["end_row"]),
        int(value["end_column"]),
    )


def _canonical_span_geometry(value: Any) -> list[tuple[int, int, int, int]]:
    return sorted(
        (
            int(item.get("start_row") or 0),
            int(item.get("start_column") or 0),
            int(item.get("end_row") or 0),
            int(item.get("end_column") or 0),
        )
        for item in _dicts(value)
    )


def _header_relation_sort_key(
    value: dict[str, Any],
) -> tuple[int, int, int, int]:
    return (
        int(value["parent_row"]),
        int(value["parent_column"]),
        int(value["child_start_column"]),
        int(value["child_end_column"]),
    )


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dicts(value: Any) -> list[dict[str, Any]]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, list)
        else []
    )


if __name__ == "__main__":
    raise SystemExit(main())
