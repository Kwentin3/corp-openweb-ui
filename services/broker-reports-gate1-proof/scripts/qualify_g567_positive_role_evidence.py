#!/usr/bin/env python3
"""Qualify frozen G5.67 replay outputs without changing model output."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development-replay", type=Path, required=True)
    parser.add_argument("--development-oracle", type=Path, required=True)
    parser.add_argument("--current-replay", type=Path, required=True)
    parser.add_argument("--current-oracle", type=Path, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, required=True)
    args = parser.parse_args()

    development = _read_json(args.development_replay)
    development_oracle = _read_json(args.development_oracle)
    current = _read_json(args.current_replay)
    current_oracle = _read_json(args.current_oracle)
    private, safe = qualify(
        development=development,
        development_oracle=development_oracle,
        current=current,
        current_oracle=current_oracle,
    )
    _write_json(args.private_output, private)
    _write_json(args.safe_output, safe)
    print(json.dumps(safe, ensure_ascii=False, indent=2))
    return 0 if safe["terminal"] == "POSITIVE_METADATA_ROLE_EVIDENCE_PROVEN" else 2


def qualify(
    *,
    development: dict[str, Any],
    development_oracle: dict[str, Any],
    current: dict[str, Any],
    current_oracle: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    _validate_inputs(development, development_oracle, current, current_oracle)
    oracle_by_alias = {
        case["alias"]: case["facts"] for case in development_oracle["cases"]
    }
    development_cases = [
        _qualify_case(case, oracle_by_alias[case["alias"]])
        for case in development["cases"]
    ]
    current_case = _qualify_case(
        {
            "alias": current["alias"],
            "validated_output": current["validated_output"],
            "binding_registry": current["binding_registry"],
            "provider_submissions": current["provider_submissions"],
            "metrics": current["metrics"],
        },
        current_oracle["facts"],
    )
    development_passed = sum(case["semantic_exact"] for case in development_cases)
    role_binding_failures = sum(
        case["role_binding_failures"] for case in development_cases
    ) + current_case["role_binding_failures"]
    provider_calls = sum(
        case.get("provider_submissions", 0) for case in development["cases"]
    ) + current["provider_submissions"]
    metrics = [case.get("metrics") or {} for case in development["cases"]]
    metrics.append(current.get("metrics") or {})
    positive_proof = (
        development_passed == len(development_cases)
        and current_case["semantic_exact"]
        and role_binding_failures == 0
    )
    terminal = (
        "POSITIVE_METADATA_ROLE_EVIDENCE_PROVEN"
        if positive_proof
        else "POSITIVE_ROLE_EVIDENCE_NOT_SUFFICIENT"
    )
    safe_cases = [_safe_case(case) for case in development_cases]
    safe_current = _safe_case(current_case)
    safe = {
        "schema_version": "broker_reports_g567_qualification_safe_v1",
        "goal": "G5.67",
        "terminal": terminal,
        "development_documents": len(development_cases),
        "development_semantic_exact": development_passed,
        "current_holdout_semantic_exact": current_case["semantic_exact"],
        "provider_calls": provider_calls,
        "retries": 0,
        "best_of_n": False,
        "manual_output_repair": False,
        "role_binding_failures": role_binding_failures,
        "input_tokens": sum(item.get("input_tokens") or 0 for item in metrics),
        "output_tokens": sum(item.get("output_tokens") or 0 for item in metrics),
        "total_tokens": sum(item.get("total_tokens") or 0 for item in metrics),
        "development_cases": safe_cases,
        "current_holdout": safe_current,
        "second_untouched_holdout_authorized": positive_proof,
        "semantic_tuning_after_replay": 0,
    }
    private = {
        **safe,
        "schema_version": "broker_reports_g567_qualification_private_v1",
        "development_cases": development_cases,
        "current_holdout": current_case,
    }
    return private, safe


def _qualify_case(
    replay_case: dict[str, Any], oracle_facts: list[dict[str, Any]]
) -> dict[str, Any]:
    candidates = replay_case["validated_output"]["metadata_facts"]
    expected = Counter(_semantic_key(fact) for fact in oracle_facts)
    actual = Counter(_semantic_key(fact) for fact in candidates)
    missing = list((expected - actual).elements())
    extras = list((actual - expected).elements())
    binding_failures = [
        failure
        for fact in candidates
        for failure in _role_binding_failures(
            fact=fact, registry=replay_case["binding_registry"]
        )
    ]
    return {
        "alias": replay_case["alias"],
        "provider_submissions": replay_case.get("provider_submissions"),
        "oracle_facts": len(oracle_facts),
        "published_facts": len(candidates),
        "semantic_exact": not missing and not extras,
        "missing_facts": missing,
        "extra_facts": extras,
        "role_binding_failures": len(binding_failures),
        "role_binding_failure_codes": binding_failures,
        "metrics": replay_case.get("metrics"),
    }


def _role_binding_failures(
    *, fact: dict[str, Any], registry: dict[str, Any]
) -> list[str]:
    source = fact.get("source_binding") or {}
    role = source.get("role_evidence_binding") or {}
    alias = role.get("source_target_alias")
    target = (registry.get("targets") or {}).get(alias)
    failures: list[str] = []
    if not role:
        failures.append("ROLE_EVIDENCE_BINDING_MISSING")
    if not isinstance(target, dict):
        failures.append("ROLE_EVIDENCE_TARGET_UNKNOWN")
        return failures
    if (
        role.get("document_id") != source.get("document_id")
        or role.get("canonical_version_id") != source.get("canonical_version_id")
        or target.get("document_id") != source.get("document_id")
        or target.get("canonical_version_id") != source.get("canonical_version_id")
    ):
        failures.append("ROLE_EVIDENCE_CANONICAL_BINDING_MISMATCH")
    if not role.get("source_refs"):
        failures.append("ROLE_EVIDENCE_SOURCE_REFS_EMPTY")
    return failures


def _semantic_key(fact: dict[str, Any]) -> tuple[str, str]:
    return (
        fact["fact_type"],
        json.dumps(
            fact["value"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
    )


def _safe_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "alias": case["alias"],
        "provider_submissions": case["provider_submissions"],
        "oracle_facts": case["oracle_facts"],
        "published_facts": case["published_facts"],
        "semantic_exact": case["semantic_exact"],
        "missing_facts": len(case["missing_facts"]),
        "extra_facts": len(case["extra_facts"]),
        "role_binding_failures": case["role_binding_failures"],
    }


def _validate_inputs(
    development: dict[str, Any],
    development_oracle: dict[str, Any],
    current: dict[str, Any],
    current_oracle: dict[str, Any],
) -> None:
    if (
        development.get("provider_submissions_total") != 4
        or development_oracle.get("source_truth_fact_count") != 24
        or current.get("goal") != "G5.67"
        or current.get("provider_submissions") != 1
        or current_oracle.get("goal") != "G5.67"
        or current_oracle.get("llm_output_used_as_truth_hint") is not False
    ):
        raise SystemExit("g567_qualification_input_invalid")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SystemExit("g567_json_object_required")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    raise SystemExit(main())
