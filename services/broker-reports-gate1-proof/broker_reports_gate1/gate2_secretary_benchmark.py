from __future__ import annotations

import copy
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


MANIFEST_SCHEMA_VERSION = "broker_reports_gate2_secretary_benchmark_manifest_v1"
RESULT_SCHEMA_VERSION = "broker_reports_gate2_secretary_benchmark_result_v1"
SAFE_REPORT_SCHEMA_VERSION = "broker_reports_gate2_secretary_benchmark_safe_report_v1"
DEFAULT_MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent
    / "benchmarks"
    / "gate2_secretary_v1"
    / "manifest.json"
)

FAILURE_PROVIDER_SCHEMA_REJECTED = "provider_schema_rejected"
FAILURE_PROVIDER_REFUSAL = "provider_refusal"
FAILURE_PROVIDER_TRUNCATION = "provider_truncation"
FAILURE_INVALID_JSON = "invalid_json"
FAILURE_SCHEMA_SHAPE = "schema_shape_invalid"
FAILURE_LITERAL_COPY = "literal_copy_mismatch"
FAILURE_CLASSIFICATION = "bounded_classification_mismatch"
FAILURE_SOURCE_BINDING = "source_binding_mismatch"
FAILURE_DUPLICATE_BINDING = "duplicate_binding"
FAILURE_INVENTED_VALUE = "invented_value"
FAILURE_EXPECTED_VALUE = "expected_value_mismatch"


@dataclass(frozen=True)
class SecretaryBenchmarkResult:
    case_id: str
    workload: str
    family: str
    passed: bool
    failure_codes: tuple[str, ...]
    exact_scalar_count: int
    expected_scalar_count: int
    invented_value_count: int
    binding_error_count: int
    duplicate_binding_count: int
    provider_schema_accepted: bool
    provider_refused: bool
    provider_truncated: bool
    correct_disposition: bool | None
    exact_value_accuracy: float
    source_binding_accuracy: float
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RESULT_SCHEMA_VERSION,
            "case_id": self.case_id,
            "workload": self.workload,
            "family": self.family,
            "passed": self.passed,
            "failure_codes": list(self.failure_codes),
            "metrics": {
                "exact_scalar_count": self.exact_scalar_count,
                "expected_scalar_count": self.expected_scalar_count,
                "invented_value_count": self.invented_value_count,
                "binding_error_count": self.binding_error_count,
                "duplicate_binding_count": self.duplicate_binding_count,
                "provider_schema_accepted": self.provider_schema_accepted,
                "canonical_accepted": self.passed,
                "provider_refused": self.provider_refused,
                "provider_truncated": self.provider_truncated,
                "correct_disposition": self.correct_disposition,
                "exact_value_accuracy": self.exact_value_accuracy,
                "source_binding_accuracy": self.source_binding_accuracy,
                "latency_ms": self.latency_ms,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "estimated_cost_usd": self.estimated_cost_usd,
            },
        }


def load_secretary_benchmark_manifest(
    path: str | Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("secretary_benchmark_manifest_object_required")
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise ValueError("secretary_benchmark_manifest_schema_invalid")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != manifest.get("case_count"):
        raise ValueError("secretary_benchmark_case_count_invalid")
    case_ids = [case.get("case_id") for case in cases if isinstance(case, dict)]
    if len(case_ids) != len(cases) or len(set(case_ids)) != len(case_ids):
        raise ValueError("secretary_benchmark_case_ids_invalid")
    if manifest.get("contains_customer_data") is not False:
        raise ValueError("secretary_benchmark_customer_data_forbidden")
    return copy.deepcopy(manifest)


def compare_secretary_response(
    fixture: Mapping[str, Any],
    candidate: Any,
    *,
    provider_schema_accepted: bool = True,
    provider_refused: bool = False,
    provider_truncated: bool = False,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
) -> SecretaryBenchmarkResult:
    case_id = _required_string(fixture, "case_id")
    workload = _required_string(fixture, "workload")
    family = _required_string(fixture, "family")
    expected = fixture.get("expected_output")
    if not isinstance(expected, dict):
        raise ValueError("secretary_benchmark_expected_output_invalid")
    _validate_optional_nonnegative_int(latency_ms, "latency_ms")
    _validate_optional_nonnegative_int(input_tokens, "input_tokens")
    _validate_optional_nonnegative_int(output_tokens, "output_tokens")
    if estimated_cost_usd is not None and estimated_cost_usd < 0:
        raise ValueError("secretary_benchmark_estimated_cost_usd_invalid")

    failures: set[str] = set()
    if not provider_schema_accepted:
        failures.add(FAILURE_PROVIDER_SCHEMA_REJECTED)
    if provider_refused:
        failures.add(FAILURE_PROVIDER_REFUSAL)
    if provider_truncated:
        failures.add(FAILURE_PROVIDER_TRUNCATION)

    parsed = candidate
    if isinstance(candidate, str):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            failures.add(FAILURE_INVALID_JSON)
            parsed = None
    if not isinstance(parsed, dict):
        if FAILURE_INVALID_JSON not in failures:
            failures.add(FAILURE_SCHEMA_SHAPE)
        return SecretaryBenchmarkResult(
            case_id=case_id,
            workload=workload,
            family=family,
            passed=False,
            failure_codes=tuple(sorted(failures)),
            exact_scalar_count=0,
            expected_scalar_count=len(_scalar_items(expected)),
            invented_value_count=0,
            binding_error_count=0,
            duplicate_binding_count=0,
            provider_schema_accepted=provider_schema_accepted,
            provider_refused=provider_refused,
            provider_truncated=provider_truncated,
            correct_disposition=None,
            exact_value_accuracy=0.0,
            source_binding_accuracy=0.0,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )

    expected_items = _scalar_items(expected)
    actual_items = _scalar_items(parsed)
    exact_count = sum(
        1 for path, value in expected_items.items() if actual_items.get(path) == value
    )
    if _shape(expected) != _shape(parsed):
        failures.add(FAILURE_SCHEMA_SHAPE)
    if exact_count != len(expected_items):
        failures.add(FAILURE_EXPECTED_VALUE)

    literal_paths = tuple(str(path) for path in fixture.get("literal_paths", []))
    if any(
        actual_items.get(path) != expected_items.get(path)
        for path in literal_paths
    ):
        failures.add(FAILURE_LITERAL_COPY)

    bounded = fixture.get("bounded_classifications", {})
    if not isinstance(bounded, dict):
        raise ValueError("secretary_benchmark_bounded_classifications_invalid")
    for path, allowed_values in bounded.items():
        if not isinstance(allowed_values, list) or actual_items.get(str(path)) not in allowed_values:
            failures.add(FAILURE_CLASSIFICATION)

    binding_paths = tuple(str(path) for path in fixture.get("binding_paths", []))
    binding_errors = sum(
        1
        for path in binding_paths
        if actual_items.get(path) != expected_items.get(path)
    )
    if binding_errors:
        failures.add(FAILURE_SOURCE_BINDING)
    exact_literal_count = sum(
        1
        for path in literal_paths
        if actual_items.get(path) == expected_items.get(path)
    )
    exact_value_accuracy = (
        exact_literal_count / len(literal_paths) if literal_paths else 1.0
    )
    source_binding_accuracy = (
        (len(binding_paths) - binding_errors) / len(binding_paths)
        if binding_paths
        else 1.0
    )
    expected_disposition = expected_items.get("$.disposition")
    correct_disposition = (
        actual_items.get("$.disposition") == expected_disposition
        if "$.disposition" in expected_items
        else None
    )

    duplicate_count = _duplicate_binding_count(parsed)
    if duplicate_count:
        failures.add(FAILURE_DUPLICATE_BINDING)

    allowed_literals = {
        _stable_scalar(value) for value in fixture.get("allowed_literal_values", [])
    }
    invented = 0
    if allowed_literals:
        ignored_keys = {
            "schema_version",
            "disposition",
            "fact_type",
            "reason_code",
            "ambiguity_code",
            "registry_type_id",
            "status",
        }
        for path, value in actual_items.items():
            leaf = path.rsplit(".", 1)[-1].split("[", 1)[0]
            if leaf in ignored_keys:
                continue
            if _stable_scalar(value) not in allowed_literals:
                invented += 1
    if invented:
        failures.add(FAILURE_INVENTED_VALUE)

    return SecretaryBenchmarkResult(
        case_id=case_id,
        workload=workload,
        family=family,
        passed=not failures,
        failure_codes=tuple(sorted(failures)),
        exact_scalar_count=exact_count,
        expected_scalar_count=len(expected_items),
        invented_value_count=invented,
        binding_error_count=binding_errors,
        duplicate_binding_count=duplicate_count,
        provider_schema_accepted=provider_schema_accepted,
        provider_refused=provider_refused,
        provider_truncated=provider_truncated,
        correct_disposition=correct_disposition,
        exact_value_accuracy=exact_value_accuracy,
        source_binding_accuracy=source_binding_accuracy,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )


def render_safe_benchmark_report(
    *,
    benchmark_id: str,
    model_id: str,
    provider_route: str,
    contract_version: str,
    results: Iterable[SecretaryBenchmarkResult],
) -> dict[str, Any]:
    ordered = sorted(results, key=lambda item: item.case_id)
    failure_counts = Counter(
        code for result in ordered for code in result.failure_codes
    )
    family_counts = Counter(result.family for result in ordered)
    workload_counts = Counter(result.workload for result in ordered)
    passed = sum(1 for result in ordered if result.passed)
    measured_latency = [
        result.latency_ms for result in ordered if result.latency_ms is not None
    ]
    measured_cost = [
        result.estimated_cost_usd
        for result in ordered
        if result.estimated_cost_usd is not None
    ]
    dispositions = [
        result.correct_disposition
        for result in ordered
        if result.correct_disposition is not None
    ]
    return {
        "schema_version": SAFE_REPORT_SCHEMA_VERSION,
        "benchmark_id": benchmark_id,
        "qualification_subject": {
            "model_id": model_id,
            "provider_route": provider_route,
            "contract_version": contract_version,
        },
        "status": "passed" if passed == len(ordered) and ordered else "failed",
        "case_count": len(ordered),
        "passed_case_count": passed,
        "failed_case_count": len(ordered) - passed,
        "failure_counts": dict(sorted(failure_counts.items())),
        "family_counts": dict(sorted(family_counts.items())),
        "workload_counts": dict(sorted(workload_counts.items())),
        "aggregate_metrics": {
            "provider_schema_acceptance_rate": _mean(
                [result.provider_schema_accepted for result in ordered]
            ),
            "canonical_acceptance_rate": (
                passed / len(ordered) if ordered else 0.0
            ),
            "exact_value_accuracy": _mean(
                [result.exact_value_accuracy for result in ordered]
            ),
            "source_binding_accuracy": _mean(
                [result.source_binding_accuracy for result in ordered]
            ),
            "correct_disposition_rate": _mean(dispositions),
            "invented_value_count": sum(
                result.invented_value_count for result in ordered
            ),
            "duplicate_binding_count": sum(
                result.duplicate_binding_count for result in ordered
            ),
            "truncation_count": sum(
                result.provider_truncated for result in ordered
            ),
            "latency_ms_total": (
                sum(measured_latency) if measured_latency else None
            ),
            "input_tokens_total": _optional_sum(
                result.input_tokens for result in ordered
            ),
            "output_tokens_total": _optional_sum(
                result.output_tokens for result in ordered
            ),
            "estimated_cost_usd_total": (
                round(sum(measured_cost), 12) if measured_cost else None
            ),
        },
        "cases": [
            {
                "case_id": result.case_id,
                "passed": result.passed,
                "failure_codes": list(result.failure_codes),
                "metrics": result.to_dict()["metrics"],
            }
            for result in ordered
        ],
        "raw_provider_output_included": False,
        "customer_data_included": False,
    }


def _required_string(value: Mapping[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result:
        raise ValueError(f"secretary_benchmark_{key}_invalid")
    return result


def _scalar_items(value: Any, path: str = "$") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value):
            result.update(_scalar_items(value[key], f"{path}.{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(_scalar_items(item, f"{path}[{index}]"))
        return result
    return {path: value}


def _shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_shape(item) for item in value]
    return type(value).__name__


def _duplicate_binding_count(value: Mapping[str, Any]) -> int:
    duplicates = 0
    for key in ("bindings", "selected_bindings"):
        items = value.get(key)
        if not isinstance(items, list):
            continue
        encoded = [
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for item in items
        ]
        duplicates += len(encoded) - len(set(encoded))
    for nested in value.values():
        if isinstance(nested, dict):
            duplicates += _duplicate_binding_count(nested)
        elif isinstance(nested, list):
            duplicates += sum(
                _duplicate_binding_count(item)
                for item in nested
                if isinstance(item, dict)
            )
    return duplicates


def _stable_scalar(value: Any) -> tuple[str, str]:
    return (type(value).__name__, json.dumps(value, ensure_ascii=False, sort_keys=True))


def _validate_optional_nonnegative_int(value: int | None, name: str) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
        raise ValueError(f"secretary_benchmark_{name}_invalid")


def _mean(values: Iterable[bool | float]) -> float | None:
    materialized = [float(value) for value in values]
    return sum(materialized) / len(materialized) if materialized else None


def _optional_sum(values: Iterable[int | None]) -> int | None:
    materialized = list(values)
    if not materialized or any(value is None for value in materialized):
        return None
    return sum(value for value in materialized if value is not None)
