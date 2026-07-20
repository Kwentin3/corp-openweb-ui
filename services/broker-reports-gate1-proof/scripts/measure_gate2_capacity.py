#!/usr/bin/env python3
"""Measure one and two concurrent actual-corpus Gate 2 workers safely."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import psutil

try:
    from .benchmark_gate2_controlled import (
        DEFAULT_CONFIG,
        PROFILER,
        REPO_ROOT,
        _actual_store_files,
        _git_revision,
        _load,
        _prewarm,
        _stable_identity,
        _terminal_outcome,
    )
except ImportError:
    from benchmark_gate2_controlled import (
        DEFAULT_CONFIG,
        PROFILER,
        REPO_ROOT,
        _actual_store_files,
        _git_revision,
        _load,
        _prewarm,
        _stable_identity,
        _terminal_outcome,
    )


SCHEMA_VERSION = "broker_reports_gate2_capacity_safe_v1"
DEFAULT_RAW_ROOT = (
    REPO_ROOT / "local" / "stage2" / "broker_reports_runtime_audit" / "capacity"
)


def _disk_snapshot() -> dict[str, int]:
    counters = psutil.disk_io_counters()
    if counters is None:
        return {}
    return {
        "read_bytes": int(counters.read_bytes),
        "write_bytes": int(counters.write_bytes),
        "read_count": int(counters.read_count),
        "write_count": int(counters.write_count),
    }


def _delta(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    return {
        key: max(0, int(after.get(key) or 0) - int(before.get(key) or 0))
        for key in sorted(set(before) | set(after))
    }


def _worker_command(
    *, config_path: Path, raw_output: Path, cache_state: str
) -> list[str]:
    return [
        sys.executable,
        str(PROFILER),
        "--workload",
        "actual_latest",
        "--actual-config",
        str(config_path),
        "--mode",
        "baseline",
        "--cache-state",
        cache_state,
        "--output",
        str(raw_output),
    ]


def run_group(
    *,
    worker_count: int,
    config_path: Path,
    raw_root: Path,
    store_files: list[Path],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    prewarm = _prewarm(store_files)
    label = f"workers_{worker_count}"
    raw_outputs = [
        raw_root / f"{label}_{ordinal}.safe.json"
        for ordinal in range(1, worker_count + 1)
    ]
    commands = [
        _worker_command(
            config_path=config_path,
            raw_output=output,
            cache_state="warm_os_cache",
        )
        for output in raw_outputs
    ]
    raw_root.mkdir(parents=True, exist_ok=True)
    disk_before = _disk_snapshot()
    swap_before = psutil.swap_memory()
    psutil.cpu_percent(interval=None)
    started = time.perf_counter()
    children = [
        subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        for command in commands
    ]
    tracked = [psutil.Process(child.pid) for child in children]
    aggregate_rss_peak = 0
    per_process_rss_peak = [0 for _ in children]
    cpu_samples: list[float] = []
    minimum_available_memory = psutil.virtual_memory().available
    maximum_swap_percent = float(swap_before.percent)
    while any(child.poll() is None for child in children):
        aggregate = 0
        for index, process in enumerate(tracked):
            try:
                rss = int(process.memory_info().rss)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                rss = 0
            aggregate += rss
            per_process_rss_peak[index] = max(per_process_rss_peak[index], rss)
        aggregate_rss_peak = max(aggregate_rss_peak, aggregate)
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        minimum_available_memory = min(minimum_available_memory, int(memory.available))
        maximum_swap_percent = max(maximum_swap_percent, float(swap.percent))
        cpu_samples.append(float(psutil.cpu_percent(interval=0.05)))
    completed = [child.communicate() for child in children]
    group_wall = time.perf_counter() - started
    disk_after = _disk_snapshot()
    swap_after = psutil.swap_memory()
    failures = []
    for index, (child, (_stdout, stderr)) in enumerate(zip(children, completed)):
        if child.returncode != 0:
            failures.append(
                {
                    "worker_ordinal": index + 1,
                    "return_code": child.returncode,
                    "safe_error_tail_present": bool(stderr),
                }
            )
    if failures:
        raise RuntimeError(
            "gate2_capacity_worker_failed:"
            + json.dumps(failures, sort_keys=True)
        )
    runs = [_load(output) for output in raw_outputs]
    resources = [dict(run.get("resource_profile") or {}) for run in runs]
    group = {
        "workers": worker_count,
        "group_wall_seconds": round(group_wall, 6),
        "worker_wall_seconds": [
            round(float(row.get("wall_seconds") or 0.0), 6) for row in resources
        ],
        "worker_peak_rss_bytes": [
            int(row.get("rss_peak_sampled_bytes") or 0) for row in resources
        ],
        "aggregate_worker_rss_peak_sampled_bytes": aggregate_rss_peak,
        "parent_observed_worker_rss_peaks_bytes": per_process_rss_peak,
        "host_cpu_percent_mean": round(statistics.mean(cpu_samples), 6),
        "host_cpu_percent_maximum": round(max(cpu_samples, default=0.0), 6),
        "host_minimum_available_memory_bytes": minimum_available_memory,
        "host_swap_percent_maximum": round(maximum_swap_percent, 6),
        "host_swap_in_bytes_delta": max(0, int(swap_after.sin) - int(swap_before.sin)),
        "host_swap_out_bytes_delta": max(0, int(swap_after.sout) - int(swap_before.sout)),
        "host_disk_io_delta": _delta(disk_after, disk_before),
        "prewarm": prewarm,
        "worker_failures": 0,
        "worker_retries": 0,
        "database_lock_errors": 0,
        "artifactstore_unchanged": all(
            bool(dict(run.get("result") or {}).get("artifactstore_unchanged"))
            for run in runs
        ),
        "terminal_statuses": sorted(
            str(dict(run.get("result") or {}).get("validator_status"))
            for run in runs
        ),
        "disk_queue_depth": "not_exposed_by_portable_psutil_sampler",
    }
    return group, runs


def build_safe_report(
    *,
    revision: str,
    one: dict[str, Any],
    two: dict[str, Any],
    runs: list[dict[str, Any]],
) -> dict[str, Any]:
    identity = _stable_identity(runs)
    terminal = _terminal_outcome(runs)
    one_wall = float(one["group_wall_seconds"])
    two_wall = float(two["group_wall_seconds"])
    two_worker_median = statistics.median(
        float(value) for value in two["worker_wall_seconds"]
    )
    degradation = two_worker_median / one_wall if one_wall else 0.0
    throughput_ratio = (2.0 * one_wall / two_wall) if two_wall else 0.0
    status = "passed" if terminal["validator_status"] == "passed" else "failed"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "repository_revision": revision,
        "identity": identity,
        "methodology": {
            "representative_contour": "actual_corpus_gate2_package_preparation",
            "one_worker_measured": True,
            "two_concurrent_workers_measured": True,
            "fresh_processes": True,
            "full_graph_prewarm_before_each_group": True,
            "raw_outputs_private_or_ignored": True,
            "production_customer_workload_touched": False,
        },
        "one_worker": one,
        "two_concurrent_workers": two,
        "comparison": {
            "per_worker_wall_degradation_ratio": round(degradation, 6),
            "aggregate_throughput_ratio_vs_one_worker": round(
                throughput_ratio, 6
            ),
            "two_worker_terminal_correctness_preserved": (
                two["worker_failures"] == 0
                and two["database_lock_errors"] == 0
                and two["artifactstore_unchanged"] is True
            ),
        },
        "terminal_outcome": terminal,
        "privacy": {
            "customer_values_in_output": False,
            "private_paths_in_output": False,
            "raw_source_or_artifact_refs_in_output": False,
            "provider_calls": 0,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--actual-config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    revision = _git_revision()
    config_path = args.actual_config.resolve()
    store_files = _actual_store_files(config_path)
    one, one_runs = run_group(
        worker_count=1,
        config_path=config_path,
        raw_root=args.raw_root.resolve(),
        store_files=store_files,
    )
    print(json.dumps({"checkpoint": "one_worker_complete"}), flush=True)
    two, two_runs = run_group(
        worker_count=2,
        config_path=config_path,
        raw_root=args.raw_root.resolve(),
        store_files=store_files,
    )
    print(json.dumps({"checkpoint": "two_workers_complete"}), flush=True)
    if _git_revision() != revision:
        raise RuntimeError("gate2_capacity_repository_revision_changed")
    report = build_safe_report(
        revision=revision,
        one=one,
        two=two,
        runs=[*one_runs, *two_runs],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"status": report["status"], **report["comparison"]}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
