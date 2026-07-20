#!/usr/bin/env python3
"""Run controlled actual-corpus Gate 2 baseline and diagnostic measurements."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
PROFILER = SCRIPT_DIR / "profile_gate2_package_preparation.py"
DEFAULT_CONFIG = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_customer_case_alpha.current.local.json"
)
DEFAULT_RAW_ROOT = (
    REPO_ROOT / "local" / "stage2" / "broker_reports_runtime_audit" / "gate2"
)
REFERENCE_SAFE = (
    REPO_ROOT
    / "docs"
    / "reports"
    / "2026-07-19"
    / "BROKER_REPORTS_GATE1_BROKER_PDF_NEUTRAL_TABLES.v1.safe.json"
)
SCHEMA_VERSION = "broker_reports_gate2_controlled_benchmark_safe_v1"


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"controlled_gate2_json_not_object:{path.name}")
    return value


def _git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _actual_store_files(config_path: Path) -> list[Path]:
    config = _load(config_path)
    proof_root = Path(str(config["proof_work_root"])).resolve()
    candidates: list[tuple[Path, Path]] = []
    for run_root in proof_root.iterdir():
        database = run_root / "artifact_store" / "artifacts.sqlite3"
        payload_root = run_root / "artifact_store" / "payloads"
        acceptance = run_root / "acceptance.safe.json"
        if run_root.is_dir() and database.is_file() and payload_root.is_dir() and acceptance.is_file():
            candidates.append((run_root, database))
    if not candidates:
        raise RuntimeError("controlled_gate2_actual_store_missing")
    run_root, database = sorted(candidates, key=lambda item: item[0].name)[-1]
    payloads = sorted(
        path
        for path in (run_root / "artifact_store" / "payloads").rglob("*")
        if path.is_file()
    )
    return [database, *payloads]


def _prewarm(files: list[Path]) -> dict[str, Any]:
    started = time.perf_counter()
    bytes_read = 0
    for path in files:
        with path.open("rb") as source:
            while chunk := source.read(8 * 1024 * 1024):
                bytes_read += len(chunk)
    return {
        "files": len(files),
        "bytes": bytes_read,
        "wall_seconds": round(time.perf_counter() - started, 6),
    }


def _run_probe(
    *,
    config_path: Path,
    mode: str,
    cache_state: str,
    raw_output: Path,
) -> dict[str, Any]:
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(PROFILER),
        "--workload",
        "actual_latest",
        "--actual-config",
        str(config_path),
        "--mode",
        mode,
        "--cache-state",
        cache_state,
        "--output",
        str(raw_output),
    ]
    completed = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "controlled_gate2_probe_failed:"
            + completed.stderr[-1000:].replace("\n", " ")
        )
    return _load(raw_output)


def _series(values: list[float | int]) -> dict[str, Any]:
    numeric = [float(value) for value in values]
    if not numeric:
        return {"count": 0}
    return {
        "count": len(numeric),
        "minimum": round(min(numeric), 6),
        "median": round(statistics.median(numeric), 6),
        "maximum": round(max(numeric), 6),
        "mean": round(statistics.mean(numeric), 6),
        "population_stdev": round(statistics.pstdev(numeric), 6),
    }


def _resource_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    resources = [_object(run.get("resource_profile")) for run in runs]
    return {
        key: _series([row.get(key) or 0 for row in resources])
        for key in (
            "wall_seconds",
            "cpu_user_seconds",
            "cpu_system_seconds",
            "rss_peak_sampled_bytes",
            "rss_incremental_peak_bytes",
            "disk_read_bytes",
            "disk_write_bytes",
        )
    }


def _phase_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    names = sorted(
        {
            name
            for run in runs
            for name in _object(_object(run.get("phase_profile")).get("phases"))
        }
    )
    return {
        name: _series(
            [
                float(
                    _object(_object(run.get("phase_profile")).get("phases")).get(name)
                    or 0.0
                )
                for run in runs
            ]
        )
        for name in names
    }


def _stable_identity(runs: list[dict[str, Any]]) -> dict[str, Any]:
    first = runs[0]
    workload = _object(first.get("workload"))
    inventory = _object(first.get("input_inventory"))
    runtime = _object(first.get("runtime"))
    identity = {
        "workload_fingerprint": workload.get("workload_fingerprint"),
        "run_label": workload.get("run_label"),
        "input_records": inventory.get("records_total"),
        "input_payload_bytes": inventory.get("payload_bytes"),
        "python": runtime.get("python"),
        "sqlite": runtime.get("sqlite"),
        "platform": runtime.get("platform"),
        "logical_cpus": runtime.get("logical_cpus"),
        "physical_memory_bytes": runtime.get("physical_memory_bytes"),
        "storage_location": runtime.get("storage_location"),
    }
    for run in runs[1:]:
        other = _stable_identity([run])
        if other != identity:
            raise RuntimeError("controlled_gate2_run_identity_drift")
    return identity


def _terminal_outcome(runs: list[dict[str, Any]]) -> dict[str, Any]:
    first = _object(runs[0].get("result"))
    expected = {
        "validator_status": first.get("validator_status"),
        "errors_count": first.get("errors_count"),
        "warnings_count": first.get("warnings_count"),
        "packages_total": first.get("packages_total"),
        "packages_passed": first.get("packages_passed"),
        "source_ready_refs_total": first.get("source_ready_refs_total"),
        "packageable_documents_total": first.get("packageable_documents_total"),
        "artifactstore_unchanged": first.get("artifactstore_unchanged"),
    }
    if any(
        {
            key: _object(run.get("result")).get(key)
            for key in expected
        }
        != expected
        for run in runs[1:]
    ):
        raise RuntimeError("controlled_gate2_terminal_outcome_drift")
    providers = [_object(run.get("provider_attribution")) for run in runs]
    if any(row.get("provider_client_or_transport_calls") != 0 for row in providers):
        raise RuntimeError("controlled_gate2_provider_call_detected")
    return {**expected, "provider_calls": 0}


def _operation_counts(instrumented: list[dict[str, Any]]) -> dict[str, Any]:
    first = instrumented[0]
    functions = _object(first.get("function_profile"))
    slice_audit = _object(_object(first.get("result")).get("slice_audit"))
    sqlite_profile = _object(first.get("sqlite_profile"))
    resolver = _object(first.get("resolver_store_profile"))
    result = {
        "sqlite_queries": sqlite_profile.get("queries_total"),
        "resolver_calls": _object(functions.get("resolver.resolve")).get("calls"),
        "payload_reads": resolver.get("payload_reads_total"),
        "payload_bytes_read": resolver.get("payload_bytes_read"),
        "duplicate_payload_reads": resolver.get("duplicate_payload_reads_total"),
        "pdf_parent_full_validations": slice_audit.get(
            "pdf_parent_full_validation_total"
        ),
        "pdf_parent_validation_cache_hits": slice_audit.get(
            "pdf_parent_validation_cache_hit_total"
        ),
        "package_candidates_enumerated": _object(
            _object(first.get("phase_profile")).get("candidate_outcomes")
        ).get("package_candidates_enumerated"),
    }
    for run in instrumented[1:]:
        if _operation_counts([run]) != result:
            raise RuntimeError("controlled_gate2_operation_count_drift")
    return result


def build_safe_report(
    *,
    revision: str,
    cold_runs: list[dict[str, Any]],
    warm_runs: list[dict[str, Any]],
    instrumented_runs: list[dict[str, Any]],
    prewarm_receipts: list[dict[str, Any]],
    reference: dict[str, Any],
) -> dict[str, Any]:
    all_runs = [*cold_runs, *warm_runs, *instrumented_runs]
    identity = _stable_identity(all_runs)
    terminal = _terminal_outcome(all_runs)
    if terminal != {
        **_terminal_outcome([all_runs[0]]),
    }:
        raise RuntimeError("controlled_gate2_terminal_summary_invalid")
    baseline_runs = [*cold_runs, *warm_runs]
    baseline_summary = _resource_summary(baseline_runs)
    instrumented_summary = _resource_summary(instrumented_runs)
    reference_after = _object(_object(reference.get("gate2_reproof")).get("after"))
    reference_wall = float(reference_after.get("wall_seconds") or 0.0)
    threshold = float(
        _object(reference.get("gate2_reproof")).get("performance_threshold_ratio")
        or 1.25
    )
    baseline_median = float(baseline_summary["wall_seconds"]["median"])
    ratio = baseline_median / reference_wall if reference_wall else math.inf
    performance_status = (
        "no_regression_measurement_noise"
        if ratio <= threshold
        else "inconclusive_with_exact_missing_evidence"
    )
    phase_summary = _phase_summary(instrumented_runs)
    phase_medians = {
        name: row.get("median") for name, row in phase_summary.items()
    }
    largest_phase = max(phase_medians, key=lambda key: phase_medians[key])
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "passed",
        "repository_revision": revision,
        "methodology": {
            "cold_process_runs": len(cold_runs),
            "warm_os_cache_runs": len(warm_runs),
            "instrumented_warm_runs": len(instrumented_runs),
            "fresh_python_process_for_every_measurement": True,
            "warm_runs_preceded_by_full_graph_chunked_read": True,
            "competing_diagnostic_workloads_started_by_harness": 0,
            "raw_runs_private_or_ignored": True,
        },
        "identity": identity,
        "terminal_outcome": terminal,
        "cold_process_resource_summary": _resource_summary(cold_runs),
        "warm_os_cache_resource_summary": _resource_summary(warm_runs),
        "baseline_combined_resource_summary": baseline_summary,
        "instrumented_resource_summary": instrumented_summary,
        "instrumented_phase_summary": phase_summary,
        "largest_instrumented_phase": largest_phase,
        "operation_counts": _operation_counts(instrumented_runs),
        "prewarm_summary": {
            "bytes": _series([item["bytes"] for item in prewarm_receipts]),
            "wall_seconds": _series(
                [item["wall_seconds"] for item in prewarm_receipts]
            ),
        },
        "reference_comparison": {
            "reference_wall_seconds": reference_wall,
            "reference_packages_total": reference_after.get("packages_total"),
            "historical_reference_runtime_identity_complete": False,
            "controlled_baseline_median_wall_seconds": round(baseline_median, 6),
            "ratio_to_reference": round(ratio, 6),
            "accepted_threshold_ratio": threshold,
            "performance_status": performance_status,
            "later_112_second_measurement_class": "instrumentation_heavy_not_product_latency",
        },
        "privacy": {
            "customer_values_in_output": False,
            "private_paths_in_output": False,
            "raw_source_or_artifact_refs_in_output": False,
            "provider_calls": 0,
            "artifactstore_unchanged": terminal["artifactstore_unchanged"],
        },
    }
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual-config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--reference", type=Path, default=REFERENCE_SAFE)
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--instrumented-runs", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.pairs < 3 or args.instrumented_runs < 3:
        raise RuntimeError("controlled_gate2_minimum_run_count_not_met")
    revision = _git_revision()
    store_files = _actual_store_files(args.actual_config.resolve())
    args.raw_root.mkdir(parents=True, exist_ok=True)
    cold_runs: list[dict[str, Any]] = []
    warm_runs: list[dict[str, Any]] = []
    instrumented_runs: list[dict[str, Any]] = []
    prewarm_receipts: list[dict[str, Any]] = []

    for index in range(1, args.pairs + 1):
        cold_runs.append(
            _run_probe(
                config_path=args.actual_config.resolve(),
                mode="baseline",
                cache_state="first_process",
                raw_output=args.raw_root / f"baseline_cold_{index}.safe.json",
            )
        )
        prewarm_receipts.append(_prewarm(store_files))
        warm_runs.append(
            _run_probe(
                config_path=args.actual_config.resolve(),
                mode="baseline",
                cache_state="warm_os_cache",
                raw_output=args.raw_root / f"baseline_warm_{index}.safe.json",
            )
        )
        print(json.dumps({"checkpoint": "baseline_pair_complete", "ordinal": index}))

    for index in range(1, args.instrumented_runs + 1):
        prewarm_receipts.append(_prewarm(store_files))
        instrumented_runs.append(
            _run_probe(
                config_path=args.actual_config.resolve(),
                mode="instrumented",
                cache_state="warm_os_cache",
                raw_output=args.raw_root / f"instrumented_warm_{index}.safe.json",
            )
        )
        print(
            json.dumps(
                {"checkpoint": "instrumented_run_complete", "ordinal": index}
            )
        )

    if _git_revision() != revision:
        raise RuntimeError("controlled_gate2_repository_revision_changed")
    report = build_safe_report(
        revision=revision,
        cold_runs=cold_runs,
        warm_runs=warm_runs,
        instrumented_runs=instrumented_runs,
        prewarm_receipts=prewarm_receipts,
        reference=_load(args.reference.resolve()),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "performance_status": report["reference_comparison"][
                    "performance_status"
                ],
                "customer_values_exposed": False,
                "private_paths_exposed": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
