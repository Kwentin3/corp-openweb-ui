#!/usr/bin/env python3
"""Profile actual-corpus visual recovery phases with safe aggregates only."""

from __future__ import annotations

import argparse
import contextlib
import functools
import json
import os
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

import psutil


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

import broker_reports_gate1.artifact_resolver as resolver_module  # noqa: E402
import broker_reports_gate1.gate2_input_readiness as readiness_module  # noqa: E402
import broker_reports_gate1.visual_neutral_tables as visual_module  # noqa: E402
import broker_reports_gate1.visual_recovery_handoff as handoff_module  # noqa: E402
import prove_visual_neutral_tables_actual_corpus as proof_module  # noqa: E402


SCHEMA_VERSION = "broker_reports_visual_actual_phase_profile_safe_v1"
DEFAULT_AUDIT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "restricted_scope_audit_private"
    / "restricted_scope_audit.private.json"
)
DEFAULT_JOB = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_visual_recovery_job.local.json"
)
DEFAULT_RAW_ROOT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_runtime_audit"
    / "visual"
)


class MetricBook:
    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.seconds: Counter[str] = Counter()
        self.maximum: defaultdict[str, float] = defaultdict(float)

    def add(self, label: str, seconds: float) -> None:
        self.calls[label] += 1
        self.seconds[label] += seconds
        self.maximum[label] = max(self.maximum[label], seconds)

    def safe_rows(self) -> dict[str, dict[str, Any]]:
        return {
            label: {
                "calls": self.calls[label],
                "inclusive_wall_seconds": round(self.seconds[label], 6),
                "maximum_call_wall_seconds": round(self.maximum[label], 6),
            }
            for label in sorted(self.calls)
        }


@contextlib.contextmanager
def _probe(metrics: MetricBook, owner: Any, name: str, label: str) -> Iterator[None]:
    original = getattr(owner, name)

    @functools.wraps(original)
    def measured(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            metrics.add(label, time.perf_counter() - started)

    setattr(owner, name, measured)
    try:
        yield
    finally:
        setattr(owner, name, original)


@contextlib.contextmanager
def installed_probes(metrics: MetricBook) -> Iterator[None]:
    targets = [
        (proof_module, "prepare_actual_latest", "source_graph.prepare_clone"),
        (resolver_module.ArtifactResolver, "resolve", "source_graph.resolver_reads"),
        (proof_module, "_decode_image", "image.base64_decode"),
        (proof_module, "_detect_grid_regions", "layout.grid_detection"),
        (proof_module, "_best_grid_orientation", "layout.orientation_search"),
        (
            proof_module,
            "_completed_observation",
            "layout.observation_and_reconstruction",
        ),
        (proof_module._IsolatedOcrRunner, "repeat", "ocr.isolated_two_pass"),
        (
            visual_module.Gate1VisualNeutralTableService,
            "recover",
            "canonical.recovery_validation",
        ),
        (proof_module, "build_visual_operator_review", "operator_review.build"),
        (
            proof_module,
            "validate_visual_continuation_chain",
            "canonical.continuation_validation",
        ),
        (proof_module, "_clone_actual_store", "handoff.clone_artifactstore"),
        (
            handoff_module.Gate1VisualRecoveryHandoffService,
            "persist",
            "handoff.persist_visual_results",
        ),
        (
            readiness_module.Gate2InputReadinessService,
            "audit_and_build",
            "handoff.gate2_integration",
        ),
        (
            proof_module,
            "render_visual_neutral_table_safe_report",
            "safe_report.visual_result_render",
        ),
    ]
    with contextlib.ExitStack() as stack:
        for owner, name, label in targets:
            stack.enter_context(_probe(metrics, owner, name, label))
        yield


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def build_safe_report(
    *,
    revision: str,
    visual: dict[str, Any],
    metrics: MetricBook,
    wall_seconds: float,
    peak_rss_bytes: int,
) -> dict[str, Any]:
    material = dict(visual.get("material_scope_accounting") or {})
    gate2 = dict(visual.get("gate2_canonical_integration") or {})
    return {
        "schema_version": SCHEMA_VERSION,
        "status": visual.get("status"),
        "repository_revision": revision,
        "resource_profile": {
            "profile_wall_seconds": round(wall_seconds, 6),
            "process_peak_rss_bytes": peak_rss_bytes,
        },
        "inclusive_phase_profile": metrics.safe_rows(),
        "terminal_outcome": {
            "material_scopes": material.get(
                "material_visual_scopes_requiring_recovery"
            ),
            "accepted_scopes": material.get("accepted_recovered_scopes"),
            "confirmed_empty_scopes": material.get(
                "confirmed_empty_source_scopes"
            ),
            "unresolved_scopes": material.get("unresolved_visual_scopes"),
            "unsupported_scopes": material.get("unsupported_visual_scopes"),
            "canonical_tables": dict(
                visual.get("canonical_region_accounting") or {}
            ).get("tables_accepted"),
            "canonical_cells": dict(
                visual.get("canonical_region_accounting") or {}
            ).get("cells_accepted"),
            "gate2_status": gate2.get("gate2_validator_status"),
            "gate2_errors": gate2.get("gate2_errors"),
            "artifactstore_unchanged": gate2.get(
                "gate2_artifactstore_unchanged_after_handoff"
            ),
            "provider_calls": dict(visual.get("provider_accounting") or {}).get(
                "calls"
            ),
        },
        "interpretation_guards": {
            "inclusive_nested_times_must_not_be_summed": True,
            "local_ocr_only": True,
            "model_canonical_authority": False,
            "golden_artifactstore_mutated": False,
        },
        "privacy": {
            "customer_values_in_output": False,
            "private_paths_in_output": False,
            "source_or_artifact_refs_in_output": False,
            "raw_outputs_private_or_ignored": True,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=proof_module.DEFAULT_ACTUAL_CONFIG
    )
    parser.add_argument("--audit-private", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--job", type=Path, default=DEFAULT_JOB)
    parser.add_argument("--model-root", type=Path, required=True)
    parser.add_argument("--confirmed-empty-group-ordinal", type=int, required=True)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    revision = _git_revision()
    raw_root = args.raw_root.resolve()
    raw_root.mkdir(parents=True, exist_ok=True)
    raw_safe = raw_root / "visual_profile.safe.json"
    raw_private = raw_root / "visual_profile.private.json"
    original_argv = sys.argv
    sys.argv = [
        str(proof_module.__file__),
        "--config",
        str(args.config.resolve()),
        "--audit-private",
        str(args.audit_private.resolve()),
        "--job",
        str(args.job.resolve()),
        "--model-root",
        str(args.model_root.resolve()),
        "--confirmed-empty-group-ordinal",
        str(args.confirmed_empty_group_ordinal),
        "--safe-output",
        str(raw_safe),
        "--private-output",
        str(raw_private),
    ]
    metrics = MetricBook()
    process = psutil.Process(os.getpid())
    started = time.perf_counter()
    try:
        with installed_probes(metrics):
            result = proof_module.main()
    finally:
        sys.argv = original_argv
    elapsed = time.perf_counter() - started
    if result != 0:
        raise RuntimeError("visual_phase_profile_proof_failed")
    if _git_revision() != revision:
        raise RuntimeError("visual_phase_profile_repository_revision_changed")
    visual = json.loads(raw_safe.read_text(encoding="utf-8"))
    report = build_safe_report(
        revision=revision,
        visual=visual,
        metrics=metrics,
        wall_seconds=elapsed,
        peak_rss_bytes=int(process.memory_info().peak_wset),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "customer_values_exposed": False,
                "private_paths_exposed": False,
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
