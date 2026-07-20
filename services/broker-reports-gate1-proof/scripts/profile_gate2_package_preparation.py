#!/usr/bin/env python3
"""Safe performance probe for canonical Gate 2 package preparation.

The measured operation always enters through ``Gate2InputReadinessFactory``.
Gate 1 setup is outside the timed contour. The probe never prints document
values, filenames, private paths, artifact ids or source refs.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import copy
import functools
import gc
import hashlib
import inspect
import io
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

try:
    import psutil
except ImportError:  # pragma: no cover - exercised only in lean proof environments
    psutil = None


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1 import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
    build_retention_policy,
    persist_gate1_result,
)


SCHEMA_VERSION = "broker_reports_gate2_package_performance_probe_v1"
DEFAULT_ACTUAL_CONFIG = (
    REPO_ROOT / "local" / "stage2" / "broker_reports_customer_case_alpha.local.json"
)


@dataclass
class PreparedWorkload:
    store: Any
    context: ArtifactAccessContext
    dcp_ref: str
    identity: dict[str, Any]
    inventory: dict[str, Any]
    cleanup: Callable[[], None]


class MetricBook:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"calls": 0, "failures": 0, "wall_seconds": 0.0}
        )

    def record(self, label: str, elapsed: float, *, failed: bool = False) -> None:
        row = self.rows[label]
        row["calls"] += 1
        row["failures"] += int(failed)
        row["wall_seconds"] += elapsed

    def safe_rows(self) -> dict[str, dict[str, Any]]:
        return {
            label: {
                "calls": int(row["calls"]),
                "failures": int(row["failures"]),
                "inclusive_wall_seconds": round(float(row["wall_seconds"]), 6),
            }
            for label, row in sorted(self.rows.items())
        }


class InstrumentedStore:
    """Transparent counter around the real factory-created store adapter."""

    def __init__(self, store: Any, metrics: MetricBook) -> None:
        self._store = store
        self._metrics = metrics
        self.payload_reads_total = 0
        self.payload_bytes_read = 0
        self.payload_artifact_type_counts: Counter[str] = Counter()
        self.payload_artifact_id_counts: Counter[str] = Counter()
        self.records_returned_total = 0

    def get_record_unchecked(self, artifact_id: str):
        started = time.perf_counter()
        failed = False
        try:
            result = self._store.get_record_unchecked(artifact_id)
            self.records_returned_total += int(result is not None)
            return result
        except Exception:
            failed = True
            raise
        finally:
            self._metrics.record(
                "store.get_record_unchecked", time.perf_counter() - started, failed=failed
            )

    def list_by_run(self, normalization_run_id: str):
        started = time.perf_counter()
        failed = False
        try:
            result = self._store.list_by_run(normalization_run_id)
            self.records_returned_total += len(result)
            return result
        except Exception:
            failed = True
            raise
        finally:
            self._metrics.record(
                "store.list_by_run", time.perf_counter() - started, failed=failed
            )

    def read_payload(self, record):
        started = time.perf_counter()
        failed = False
        try:
            result = self._store.read_payload(record)
            self.payload_reads_total += 1
            self.payload_artifact_type_counts[str(record.artifact_type)] += 1
            self.payload_artifact_id_counts[str(record.artifact_id)] += 1
            self.payload_bytes_read += _record_payload_bytes(self._store, record, result)
            return result
        except Exception:
            failed = True
            raise
        finally:
            self._metrics.record(
                "store.read_payload", time.perf_counter() - started, failed=failed
            )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._store, name)

    def safe_summary(self) -> dict[str, Any]:
        duplicate_reads = sum(
            max(0, count - 1) for count in self.payload_artifact_id_counts.values()
        )
        return {
            "payload_reads_total": self.payload_reads_total,
            "unique_payloads_read": len(self.payload_artifact_id_counts),
            "duplicate_payload_reads_total": duplicate_reads,
            "payload_bytes_read": self.payload_bytes_read,
            "payload_read_counts_by_type": dict(
                sorted(self.payload_artifact_type_counts.items())
            ),
            "records_returned_total": self.records_returned_total,
        }


class SqliteProbe:
    def __init__(self) -> None:
        self.query_count = 0
        self.query_wall_seconds = 0.0
        self.statement_counts: Counter[str] = Counter()
        self._original_connect = sqlite3.connect

    @contextlib.contextmanager
    def installed(self) -> Iterator[None]:
        probe = self
        original_connect = self._original_connect

        class TracedConnection(sqlite3.Connection):
            def execute(self, sql, parameters=(), /):
                started = time.perf_counter()
                try:
                    return super().execute(sql, parameters)
                finally:
                    probe.query_count += 1
                    probe.query_wall_seconds += time.perf_counter() - started
                    statement = str(sql).strip().split(None, 1)
                    probe.statement_counts[(statement or ["unknown"])[0].lower()] += 1

        def traced_connect(*args, **kwargs):
            kwargs.setdefault("factory", TracedConnection)
            return original_connect(*args, **kwargs)

        sqlite3.connect = traced_connect
        try:
            yield
        finally:
            sqlite3.connect = original_connect

    def safe_summary(self) -> dict[str, Any]:
        return {
            "queries_total": self.query_count,
            "query_wall_seconds": round(self.query_wall_seconds, 6),
            "statement_counts": dict(sorted(self.statement_counts.items())),
        }


class PhaseTrace:
    """Low-volume line probe around the orchestration method only."""

    BOUNDARY_MARKERS = (
        (
            "records_before = self.resolver.catalog_run(context)",
            "catalog_and_dcp_resolution",
        ),
        ("errors: list[dict[str, str]] = []", "boundary_payloads_and_contracts"),
        ("handoff_audit = self._audit_handoff(", "handoff_audit"),
        (
            'next_stage_refs = _object(dcp.get("next_stage_refs"))',
            "input_strategy_and_scope_indexing",
        ),
        (
            "slices_by_document, slice_audit = self._resolve_private_slices(",
            "private_artifact_discovery_validation",
        ),
        ("duc_ready_refs = sorted(", "scope_readiness_reconciliation"),
        (
            "packages: list[dict[str, Any]] = []",
            "package_enumeration_construction_validation",
        ),
        (
            "representation_reconciliations: list[dict[str, Any]] = []",
            "coverage_aggregation",
        ),
        (
            "records_after = self.resolver.catalog_run(context)",
            "store_immutability_guard",
        ),
        (
            'error_codes = Counter(str(item.get("code") or "unknown") for item in errors)',
            "validation_summary",
        ),
        ("safe_report = _render_safe_report(", "safe_report_rendering"),
    )

    def __init__(self, target_function) -> None:
        self.target_code = target_function.__code__
        self.boundaries = self.resolve_boundaries(target_function)
        self.phase_seconds: Counter[str] = Counter()
        self.current_phase: str | None = None
        self.current_started = 0.0
        self.seen_boundaries: set[int] = set()
        self.trace_total_seconds = 0.0
        self.started = 0.0
        self.candidate_summary: dict[str, Any] = {}

    @classmethod
    def resolve_boundaries(cls, target_function) -> dict[int, str]:
        source_lines, start_line = inspect.getsourcelines(target_function)
        boundaries: dict[int, str] = {}
        for marker, phase in cls.BOUNDARY_MARKERS:
            matches = [
                start_line + offset
                for offset, line in enumerate(source_lines)
                if marker in line.strip()
            ]
            if len(matches) != 1:
                raise RuntimeError(
                    "gate2_phase_marker_resolution_failed:"
                    f"{phase}:matches={len(matches)}"
                )
            boundaries[matches[0]] = phase
        if list(boundaries) != sorted(boundaries):
            raise RuntimeError("gate2_phase_marker_order_invalid")
        return boundaries

    @contextlib.contextmanager
    def installed(self) -> Iterator[None]:
        previous = sys.gettrace()
        sys.settrace(self._global_trace)
        try:
            yield
        finally:
            sys.settrace(previous)

    def _global_trace(self, frame, event, arg):
        if event == "call" and frame.f_code is self.target_code:
            self.started = time.perf_counter()
            self._start_phase("preconditions")
            return self._local_trace
        return None

    def _local_trace(self, frame, event, arg):
        if event == "line":
            line = frame.f_lineno
            if line in self.boundaries and line not in self.seen_boundaries:
                self.seen_boundaries.add(line)
                self._finish_phase()
                self._start_phase(self.boundaries[line])
        elif event == "return":
            self._finish_phase()
            self.trace_total_seconds = time.perf_counter() - self.started
            self.candidate_summary = _candidate_summary_from_locals(frame.f_locals)
        return self._local_trace

    def _start_phase(self, name: str) -> None:
        self.current_phase = name
        self.current_started = time.perf_counter()

    def _finish_phase(self) -> None:
        if self.current_phase is not None:
            self.phase_seconds[self.current_phase] += (
                time.perf_counter() - self.current_started
            )
        self.current_phase = None

    def safe_summary(self) -> dict[str, Any]:
        return {
            "trace_total_seconds": round(self.trace_total_seconds, 6),
            "phases": {
                name: round(seconds, 6)
                for name, seconds in self.phase_seconds.items()
            },
            "candidate_outcomes": self.candidate_summary,
            "line_boundaries": {
                str(line): name for line, name in self.boundaries.items()
            },
        }


class PeakSampler:
    def __init__(self, process: psutil.Process, interval_seconds: float = 0.01) -> None:
        self.process = process
        self.interval_seconds = interval_seconds
        self.stop_event = threading.Event()
        self.peak_rss = 0
        self.thread = threading.Thread(target=self._sample, daemon=True)

    def start(self) -> None:
        self.peak_rss = self.process.memory_info().rss
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join()
        self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)

    def _sample(self) -> None:
        while not self.stop_event.wait(self.interval_seconds):
            try:
                self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)
            except psutil.Error:
                return


@contextlib.contextmanager
def _function_probes(metrics: MetricBook) -> Iterator[None]:
    import broker_reports_gate1.artifact_resolver as resolver_module
    import broker_reports_gate1.full_source as full_source_module
    import broker_reports_gate1.gate2_input_readiness as readiness_module
    import broker_reports_gate1.gate2_model_clients as model_clients_module
    import broker_reports_gate1.gate2_table_packages as table_packages_module
    import broker_reports_gate1.pdf_text_layer as pdf_text_module
    import broker_reports_gate1.source_provenance as provenance_module
    import broker_reports_gate1.table_projection as table_projection_module

    patches = [
        (resolver_module.ArtifactResolver, "catalog_run", "resolver.catalog_run"),
        (resolver_module.ArtifactResolver, "resolve", "resolver.resolve"),
        (readiness_module, "validate_document_memory_manifest", "validation.document_memory"),
        (readiness_module, "validate_full_source_unit", "validation.full_source_unit"),
        (
            readiness_module,
            "validate_pdf_source_unit_parent_linkage",
            "validation.pdf_source_unit_parent_linkage",
        ),
        (
            readiness_module,
            "validate_pdf_text_layer_payload",
            "validation.pdf_parent_payload_gate2",
        ),
        (readiness_module, "validate_normalized_slice_provenance", "validation.legacy_slice_provenance"),
        (readiness_module, "validate_dry_run_source_fact_package", "validation.source_fact_package"),
        (readiness_module, "_build_dry_run_package", "construction.source_fact_package"),
        (readiness_module, "_build_model_source_projection", "construction.model_projection"),
        (readiness_module, "_build_issue_context", "construction.issue_context"),
        (readiness_module, "_render_safe_report", "serialization.safe_report"),
        (readiness_module, "resolve_source_values", "validation.resolve_source_values"),
        (
            readiness_module,
            "resolve_pdf_layout_unit_source_values",
            "validation.resolve_pdf_values_input_batch",
        ),
        (readiness_module, "validate_gate2_table_package", "validation.table_package_outer"),
        (readiness_module, "stable_digest", "hash.stable_digest_readiness"),
        (provenance_module, "validate_normalized_slice_provenance", "validation.slice_provenance"),
        (provenance_module.NormalizedSliceProvenanceEnricher, "enrich_slice", "validation.rebuild_provenance"),
        (provenance_module, "_checksum_ref", "hash.provenance_checksum"),
        (
            full_source_module,
            "validate_pdf_source_unit_structure",
            "validation.pdf_source_unit_structure",
        ),
        (full_source_module, "_checksum_ref", "hash.full_source_checksum"),
        (pdf_text_module, "validate_pdf_text_layer_payload", "validation.pdf_parent_payload"),
        (
            pdf_text_module,
            "resolve_pdf_layout_unit_source_value_results",
            "validation.resolve_pdf_values_inner_batch",
        ),
        (pdf_text_module, "_checksum_ref", "hash.pdf_checksum"),
        (table_projection_module.TableProjectionValidator, "validate", "validation.table_projection"),
        (table_projection_module, "_projection_checksum", "hash.table_projection_checksum"),
        (table_packages_module.Gate2TablePackageBuilder, "build", "construction.table_package"),
        (table_packages_module, "validate_gate2_table_package", "validation.table_package_inner"),
        (table_packages_module, "stable_digest", "hash.stable_digest_table_package"),
        (model_clients_module.Gate2OpenWebUIStructuredModelClient, "extract", "provider.client_extract"),
        (model_clients_module.Gate2OpenWebUIStructuredModelClient, "_invoke_completion_once", "provider.openwebui_completion"),
    ]
    originals = []
    try:
        for owner, name, label in patches:
            if not hasattr(owner, name):
                continue
            original = getattr(owner, name)
            wrapped = _timed_wrapper(original, label, metrics)
            setattr(owner, name, wrapped)
            originals.append((owner, name, original))
        yield
    finally:
        for owner, name, original in reversed(originals):
            setattr(owner, name, original)


@contextlib.contextmanager
def _narrow_function_probes(metrics: MetricBook) -> Iterator[None]:
    """Low-overhead timings for full-corpus phase attribution."""

    import broker_reports_gate1.artifact_resolver as resolver_module
    import broker_reports_gate1.gate2_input_readiness as readiness_module
    import broker_reports_gate1.gate2_model_clients as model_clients_module
    import broker_reports_gate1.gate2_table_packages as table_packages_module
    import broker_reports_gate1.table_projection as table_projection_module

    patches = [
        (
            readiness_module.Gate2InputReadinessService,
            "_resolve_private_slices",
            "phase.private_artifact_discovery_validation",
        ),
        (
            readiness_module.Gate2InputReadinessService,
            "_audit_handoff",
            "phase.handoff_audit",
        ),
        (resolver_module.ArtifactResolver, "catalog_run", "resolver.catalog_run"),
        (resolver_module.ArtifactResolver, "resolve", "resolver.resolve"),
        (
            readiness_module,
            "validate_document_memory_manifest",
            "validation.document_memory",
        ),
        (
            readiness_module,
            "_build_dry_run_package",
            "construction.source_fact_package",
        ),
        (
            readiness_module,
            "validate_dry_run_source_fact_package",
            "validation.source_fact_package",
        ),
        (
            readiness_module,
            "validate_gate2_table_package",
            "validation.table_package_outer",
        ),
        (
            table_projection_module.TableProjectionValidator,
            "validate",
            "validation.table_projection",
        ),
        (
            table_packages_module.Gate2TablePackageBuilder,
            "build",
            "construction.table_package",
        ),
        (
            table_packages_module,
            "validate_gate2_table_package",
            "validation.table_package_inner",
        ),
        (readiness_module, "_render_safe_report", "serialization.safe_report"),
        (
            model_clients_module.Gate2OpenWebUIStructuredModelClient,
            "extract",
            "provider.client_extract",
        ),
        (
            model_clients_module.Gate2OpenWebUIStructuredModelClient,
            "_invoke_completion_once",
            "provider.openwebui_completion",
        ),
    ]
    originals = []
    try:
        for owner, name, label in patches:
            if not hasattr(owner, name):
                continue
            original = getattr(owner, name)
            setattr(owner, name, _timed_wrapper(original, label, metrics))
            originals.append((owner, name, original))
        yield
    finally:
        for owner, name, original in reversed(originals):
            setattr(owner, name, original)


def _timed_wrapper(function, label: str, metrics: MetricBook):
    if getattr(function, "__code__", None) is not None and (
        function.__code__.co_flags & 0x80
    ):
        @functools.wraps(function)
        async def async_wrapped(*args, **kwargs):
            started = time.perf_counter()
            failed = False
            try:
                return await function(*args, **kwargs)
            except Exception:
                failed = True
                raise
            finally:
                metrics.record(label, time.perf_counter() - started, failed=failed)

        return async_wrapped

    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        started = time.perf_counter()
        failed = False
        try:
            return function(*args, **kwargs)
        except Exception:
            failed = True
            raise
        finally:
            metrics.record(label, time.perf_counter() - started, failed=failed)

    return wrapped


def run_measurement(prepared: PreparedWorkload, *, mode: str, cache_state: str) -> dict[str, Any]:
    import broker_reports_gate1.gate2_input_readiness as readiness_module

    if psutil is None:
        raise RuntimeError("gate2_performance_probe_requires_psutil")
    gc.collect()
    process = psutil.Process(os.getpid())
    base_rss = process.memory_info().rss
    io_before = process.io_counters()
    cpu_before = process.cpu_times()
    metrics = MetricBook()
    sqlite_probe = SqliteProbe()
    counters_enabled = mode in {"instrumented", "narrow"}
    measured_store = InstrumentedStore(prepared.store, metrics) if counters_enabled else prepared.store
    service = readiness_module.Gate2InputReadinessFactory(
        store=measured_store
    ).create()
    phase_trace = PhaseTrace(
        readiness_module.Gate2InputReadinessService.audit_and_build
    )
    sampler = PeakSampler(process)
    sampler.start()
    started = time.perf_counter()
    try:
        with contextlib.ExitStack() as stack:
            if counters_enabled:
                stack.enter_context(sqlite_probe.installed())
            if mode == "instrumented":
                stack.enter_context(_function_probes(metrics))
                stack.enter_context(phase_trace.installed())
            elif mode == "narrow":
                stack.enter_context(_narrow_function_probes(metrics))
            result = service.audit_and_build(
                domain_context_packet_ref=prepared.dcp_ref,
                context=prepared.context,
            )
    finally:
        elapsed = time.perf_counter() - started
        sampler.stop()
    cpu_after = process.cpu_times()
    io_after = process.io_counters()
    rss_after = process.memory_info().rss
    fanout = _fanout_summary(result)
    function_rows = metrics.safe_rows()
    provider_calls = sum(
        row["calls"] for label, row in function_rows.items() if label.startswith("provider.")
    )
    package_model_flags = sum(
        _object(package.get("prompt_contract")).get("model_call_performed") is True
        for package in result.packages
    )
    store_summary = (
        measured_store.safe_summary()
        if isinstance(measured_store, InstrumentedStore)
        else {"measurement": "not_enabled_in_baseline_mode"}
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "safe_output": True,
        "measurement_mode": mode,
        "cache_state": cache_state,
        "workload": copy.deepcopy(prepared.identity),
        "input_inventory": copy.deepcopy(prepared.inventory),
        "runtime": _runtime_summary(),
        "resource_profile": {
            "wall_seconds": round(elapsed, 6),
            "cpu_user_seconds": round(cpu_after.user - cpu_before.user, 6),
            "cpu_system_seconds": round(cpu_after.system - cpu_before.system, 6),
            "rss_baseline_bytes": base_rss,
            "rss_peak_sampled_bytes": sampler.peak_rss,
            "rss_incremental_peak_bytes": max(0, sampler.peak_rss - base_rss),
            "rss_after_bytes": rss_after,
            "disk_read_count": io_after.read_count - io_before.read_count,
            "disk_read_bytes": io_after.read_bytes - io_before.read_bytes,
            "disk_write_count": io_after.write_count - io_before.write_count,
            "disk_write_bytes": io_after.write_bytes - io_before.write_bytes,
        },
        "phase_profile": (
            phase_trace.safe_summary()
            if mode == "instrumented"
            else {"measurement": f"line_trace_not_enabled_in_{mode}_mode"}
        ),
        "function_profile": function_rows,
        "resolver_store_profile": store_summary,
        "sqlite_profile": (
            sqlite_probe.safe_summary()
            if counters_enabled
            else {"measurement": "not_enabled_in_baseline_mode"}
        ),
        "fanout": fanout,
        "result": {
            "validator_status": result.validation.get("validator_status"),
            "errors_count": result.validation.get("errors_count"),
            "error_code_counts": copy.deepcopy(
                result.validation.get("error_code_counts") or {}
            ),
            "warnings_count": result.validation.get("warnings_count"),
            "warning_code_counts": copy.deepcopy(
                result.validation.get("warning_code_counts") or {}
            ),
            "packages_total": result.validation.get("packages_total"),
            "packages_passed": result.validation.get("packages_passed"),
            "source_ready_refs_total": result.validation.get("source_ready_refs_total"),
            "packageable_documents_total": len(
                result.validation.get("packageable_document_refs") or []
            ),
            "unpackageable_documents_total": len(
                result.validation.get("unpackageable_document_refs") or []
            ),
            "artifactstore_unchanged": result.validation.get("artifactstore_unchanged"),
            "safe_report_status": result.safe_report.get("status"),
            "slice_audit": copy.deepcopy(
                result.validation.get("slice_audit") or {}
            ),
        },
        "provider_attribution": {
            "provider_client_or_transport_calls": provider_calls,
            "provider_retries": 0,
            "provider_latency_seconds": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "packages_claiming_model_call": package_model_flags,
            "package_preparation_mode": "no_model_call",
        },
        "persistence_serialization": {
            "package_persistence_calls": 0,
            "package_serialization_calls": 0,
            "persisted_output_bytes": 0,
            "note": "maintained slow path returns in-memory packages and stops before provider/persistence",
        },
    }


def _fanout_summary(result) -> dict[str, Any]:
    by_document = Counter(str(package.get("document_ref") or "") for package in result.packages)
    unit_kinds = Counter(
        str(_object(package.get("source_unit")).get("unit_kind") or "unknown")
        for package in result.packages
    )
    input_modes = Counter(
        str(_object(package.get("source_unit")).get("source_input_mode") or "unknown")
        for package in result.packages
    )
    package_ids = [str(package.get("package_id") or "") for package in result.packages]
    counts = list(by_document.values())
    return {
        "documents_with_packages": len(by_document),
        "packages_total": len(result.packages),
        "packages_per_document_min": min(counts, default=0),
        "packages_per_document_max": max(counts, default=0),
        "packages_per_document_mean": round(sum(counts) / len(counts), 6) if counts else 0.0,
        "packages_per_document_histogram": dict(sorted(Counter(counts).items())),
        "unit_kind_counts": dict(sorted(unit_kinds.items())),
        "source_input_mode_counts": dict(sorted(input_modes.items())),
        "duplicate_package_ids": len(package_ids) - len(set(package_ids)),
    }


def _candidate_summary_from_locals(values: dict[str, Any]) -> dict[str, Any]:
    slices_by_document = values.get("slices_by_document") or {}
    slice_audit = values.get("slice_audit") or {}
    source_ready_refs = values.get("source_ready_refs") or []
    packages = values.get("packages") or []
    selected_candidates = sum(
        len(slices_by_document.get(ref, [])) for ref in source_ready_refs
    )
    candidates = int(
        slice_audit.get("full_source_units_total") or selected_candidates
    )
    built = len(packages)
    unselected_reasons = _object(
        slice_audit.get("unselected_scope_reason_counts")
    )
    visual_deferred = int(
        unselected_reasons.get("gate2_visual_consumer_unavailable") or 0
    )
    noncanonical_table_blocked = int(
        unselected_reasons.get(
            "gate2_noncanonical_table_candidate_scope_blocked"
        )
        or 0
    )
    return {
        "package_candidates_enumerated": candidates,
        "package_candidates_selected_after_scope": selected_candidates,
        "packages_built": built,
        "candidates_not_built": max(0, candidates - built),
        "visual_candidates_deferred": visual_deferred,
        "noncanonical_table_candidates_blocked": noncanonical_table_blocked,
        "other_rejected_or_deferred_candidates": max(
            0,
            candidates
            - built
            - visual_deferred
            - noncanonical_table_blocked,
        ),
    }


def prepare_actual_latest(config_path: Path) -> PreparedWorkload:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    proof_root = Path(config["proof_work_root"]).resolve()
    if _is_relative_to(proof_root, REPO_ROOT.resolve()):
        raise RuntimeError("actual_proof_root_must_remain_outside_git")
    selected = None
    for candidate in sorted(proof_root.glob("actual_gate1_*"), reverse=True):
        acceptance = candidate / "acceptance.safe.json"
        database = candidate / "artifact_store" / "artifacts.sqlite3"
        if acceptance.is_file() and database.is_file():
            selected = (candidate, acceptance, database)
            break
    if selected is None:
        raise RuntimeError("actual_gate1_persisted_root_not_found")
    run_root, acceptance_path, database = selected
    acceptance = json.loads(acceptance_path.read_text(encoding="utf-8"))
    run_id = str(_object(acceptance.get("actual_execution")).get("normalization_run_id") or "")
    if not run_id:
        with sqlite3.connect(database) as connection:
            run_ids = [
                str(row[0] or "")
                for row in connection.execute(
                    "SELECT DISTINCT normalization_run_id FROM artifact_records"
                ).fetchall()
                if row[0]
            ]
        if len(run_ids) != 1:
            raise RuntimeError("actual_gate1_run_id_missing_or_ambiguous")
        run_id = run_ids[0]
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=database,
            payload_root=run_root / "artifact_store" / "payloads",
        )
    ).create()
    records = store.list_by_run(run_id)
    dcp_records = [record for record in records if record.artifact_type == "domain_context_packet_v0"]
    if len(dcp_records) != 1:
        raise RuntimeError("actual_gate1_dcp_count_invalid")
    dcp_record = dcp_records[0]
    context = ArtifactAccessContext(
        user_id=dcp_record.user_id,
        normalization_run_id=dcp_record.normalization_run_id,
        case_id=dcp_record.case_id,
        chat_id=dcp_record.chat_id,
        workspace_model_id=dcp_record.workspace_model_id,
        allow_private=True,
        require_source_available=True,
    )
    inventory = _database_inventory(database)
    identity_material = {
        "run_label": run_root.name,
        "normalization_run_id": run_id,
        "records_total": inventory["records_total"],
        "payload_bytes": inventory["payload_bytes"],
    }
    return PreparedWorkload(
        store=store,
        context=context,
        dcp_ref=dcp_record.artifact_id,
        identity={
            "kind": "actual_customer_corpus_gate1_memory",
            "revision": "pilot_profile_v1",
            "run_label": run_root.name,
            "workload_fingerprint": _fingerprint(identity_material),
            "customer_values_exposed": False,
        },
        inventory=inventory,
        cleanup=lambda: None,
    )


def prepare_synthetic(workload: str, *, documents: int, csv_rows: int) -> PreparedWorkload:
    inputs = _synthetic_inputs(workload, documents=documents, csv_rows=csv_rows)
    result = Gate1Normalizer().normalize(
        inputs,
        input_context={
            "clarification_criticality_refinement_enabled": True,
            "proof_scope": "gate2_package_performance_synthetic_v1",
        },
        entrypoint="gate2_package_performance_probe",
        trigger_type="backend_core",
    )
    if result.package["validation_result"]["status"] != "passed":
        raise RuntimeError("synthetic_gate1_validation_failed")
    temp = tempfile.TemporaryDirectory(prefix="gate2-package-performance-")
    root = Path(temp.name)
    store = ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=root / "artifacts.sqlite3",
            payload_root=root / "payloads",
        )
    ).create()
    context = ArtifactAccessContext(
        user_id="synthetic-performance-user",
        normalization_run_id=result.package["normalization_run"]["run_id"],
        case_id="synthetic-performance-case",
        chat_id="synthetic-performance-chat",
        workspace_model_id="broker_reports_gate1_pipe",
        allow_private=True,
        require_source_available=True,
    )
    persisted = persist_gate1_result(
        store=store,
        result=result,
        context=context,
        retention_policy=build_retention_policy(mode="api_smoke"),
        source_file_refs=[
            {
                "provider": "synthetic_performance_probe",
                "openwebui_file_id": f"synthetic-performance-{index}",
                "content_type": item.mime_type,
                "size_bytes": item.declared_size_bytes,
                "source_deleted": False,
            }
            for index, item in enumerate(inputs, start=1)
        ],
    )
    database = root / "artifacts.sqlite3"
    inventory = _database_inventory(database)
    workload_material = {
        "workload": workload,
        "documents": documents,
        "csv_rows": csv_rows,
        "input_hashes": [
            hashlib.sha256(item.read_bytes().content_bytes or b"").hexdigest()
            for item in inputs
        ],
    }
    return PreparedWorkload(
        store=store,
        context=context,
        dcp_ref=persisted.artifact_refs_by_type["domain_context_packet_v0"][0],
        identity={
            "kind": f"synthetic_{workload}",
            "revision": "synthetic_workloads_v1",
            "source_records_requested": len(inputs),
            "csv_rows_per_document": csv_rows if workload in {"csv", "csv_scale", "mixed"} else 0,
            "workload_fingerprint": _fingerprint(workload_material),
            "customer_values_exposed": False,
        },
        inventory=inventory,
        cleanup=temp.cleanup,
    )


def _synthetic_inputs(workload: str, *, documents: int, csv_rows: int) -> list[FileInput]:
    if documents <= 0 or csv_rows <= 0:
        raise ValueError("synthetic_workload_dimensions_must_be_positive")
    builders = {
        "csv": _csv_input,
        "csv_scale": _csv_input,
        "html": _html_input,
        "pdf": _pdf_input,
        "xml": _xml_input,
        "zip": _zip_input,
        "review_visual": _review_visual_input,
    }
    if workload in builders:
        return [builders[workload](index, csv_rows) for index in range(documents)]
    if workload != "mixed":
        raise ValueError("synthetic_workload_unknown")
    sequence = [
        _csv_input,
        _html_input,
        _pdf_input,
        _xml_input,
        _zip_input,
        _review_visual_input,
    ]
    return [sequence[index % len(sequence)](index, csv_rows) for index in range(documents)]


def _csv_input(index: int, rows: int) -> FileInput:
    body = ["Date,Operation,Amount,Currency"]
    body.extend(
        f"2026-01-{(row % 28) + 1:02d},buy,{index * rows + row + 1}.00,USD"
        for row in range(rows)
    )
    return FileInput.from_bytes(
        private_ref=f"synthetic-csv-{index}",
        filename=f"synthetic-{index}.csv",
        content=("\n".join(body) + "\n").encode("utf-8"),
        mime_type="text/csv",
        source_kind="synthetic_performance_probe",
    )


def _html_input(index: int, rows: int) -> FileInput:
    table_rows = "".join(
        f"<tr><td>2026-01-{(row % 28) + 1:02d}</td><td>{index * rows + row + 1}.00</td></tr>"
        for row in range(rows)
    )
    content = (
        "<p>Statement context</p><table><tr><th>Date</th><th>Amount</th></tr>"
        + table_rows
        + "</table><p>Statement end</p>"
    )
    return FileInput.from_bytes(
        private_ref=f"synthetic-html-{index}",
        filename=f"synthetic-{index}.html",
        content=content.encode("utf-8"),
        mime_type="text/html",
        source_kind="synthetic_performance_probe",
    )


def _pdf_input(index: int, rows: int) -> FileInput:
    return FileInput.from_bytes(
        private_ref=f"synthetic-pdf-{index}",
        filename=f"synthetic-{index}.pdf",
        content=_ruled_table_pdf(index),
        mime_type="application/pdf",
        source_kind="synthetic_performance_probe",
    )


def _xml_input(index: int, rows: int) -> FileInput:
    events = "".join(
        f"<operation ordinal='{row + 1}' amount='{index * rows + row + 1}.00' currency='USD'/>"
        for row in range(rows)
    )
    return FileInput.from_bytes(
        private_ref=f"synthetic-xml-{index}",
        filename=f"synthetic-{index}.xml",
        content=(f"<statement>{events}</statement>").encode("utf-8"),
        mime_type="application/xml",
        source_kind="synthetic_performance_probe",
    )


def _zip_input(index: int, rows: int) -> FileInput:
    output = io.BytesIO()
    xml_bytes = _xml_input(index, rows).read_bytes().content_bytes or b""
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("payload.xml", xml_bytes)
        archive.writestr("statement.pdf", _ruled_table_pdf(index))
        archive.writestr("signature.p7s", b"synthetic-signature")
    return FileInput.from_bytes(
        private_ref=f"synthetic-zip-{index}",
        filename=f"synthetic-{index}.zip",
        content=output.getvalue(),
        mime_type="application/zip",
        source_kind="synthetic_performance_probe",
    )


def _review_visual_input(index: int, rows: int) -> FileInput:
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "AAMAASsJTYQAAAAASUVORK5CYII="
    )
    encoded = base64.b64encode(tiny_png).decode("ascii")
    content = (
        f"<p>Visual statement {index}</p><img src='data:image/png;base64,{encoded}'>"
        "<table><tr><th>Date</th></tr><tr><td>2026-01-01</td></tr></table>"
    )
    return FileInput.from_bytes(
        private_ref=f"synthetic-review-{index}",
        filename=f"synthetic-review-{index}.html",
        content=content.encode("utf-8"),
        mime_type="text/html",
        source_kind="synthetic_performance_probe",
    )


def _ruled_table_pdf(index: int) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=320, height=320)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    texts = [
        (30, 260, f"Synthetic Table {index}"),
        (30, 220, "Date"),
        (125, 220, "Amount"),
        (225, 220, "Currency"),
        (30, 195, "2026-01-01"),
        (125, 195, "10.00"),
        (225, 195, "USD"),
        (30, 170, "2026-01-02"),
        (125, 170, "20.00"),
        (225, 170, "EUR"),
    ]
    commands = [f"BT /F1 10 Tf {x} {y} Td ({text}) Tj ET" for x, y, text in texts]
    commands.extend(
        [
            "20 155 m 300 155 l S",
            "20 180 m 300 180 l S",
            "20 205 m 300 205 l S",
            "20 230 m 300 230 l S",
            "20 155 m 20 230 l S",
            "110 155 m 110 230 l S",
            "210 155 m 210 230 l S",
            "300 155 m 300 230 l S",
        ]
    )
    stream = DecodedStreamObject()
    stream.set_data("\n".join(commands).encode("latin-1"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _database_inventory(database: Path) -> dict[str, Any]:
    connection = sqlite3.connect(database)
    try:
        totals = connection.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT document_id),
                   COALESCE(SUM(payload_size_bytes), 0)
            FROM artifact_records
            """
        ).fetchone()
        by_type = connection.execute(
            """
            SELECT artifact_type, COUNT(*), COALESCE(SUM(payload_size_bytes), 0)
            FROM artifact_records
            GROUP BY artifact_type
            ORDER BY artifact_type
            """
        ).fetchall()
    finally:
        connection.close()
    return {
        "records_total": int(totals[0]),
        "document_ids_total": int(totals[1]),
        "payload_bytes": int(totals[2]),
        "artifact_types": {
            str(artifact_type): {"records_total": int(count), "payload_bytes": int(size)}
            for artifact_type, count, size in by_type
        },
    }


def _record_payload_bytes(store: Any, record: Any, payload: Any) -> int:
    if record.payload_ref:
        try:
            return int((Path(store.payload_root) / record.payload_ref).stat().st_size)
        except OSError:
            return 0
    if payload is None:
        return 0
    return len(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def _runtime_summary() -> dict[str, Any]:
    if psutil is None:
        raise RuntimeError("gate2_performance_probe_requires_psutil")
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        revision = "unavailable"
    return {
        "repository_revision": revision,
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "platform": platform.platform(),
        "logical_cpus": psutil.cpu_count(logical=True),
        "physical_memory_bytes": psutil.virtual_memory().total,
        "storage_location": "local_ntfs_private_proof_root_or_temporary_directory",
    }


def _fingerprint(value: Any) -> str:
    rendered = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workload",
        choices=("actual_latest", "csv", "csv_scale", "html", "pdf", "xml", "zip", "review_visual", "mixed"),
        default="actual_latest",
    )
    parser.add_argument("--documents", type=int, default=1)
    parser.add_argument("--csv-rows", type=int, default=10)
    parser.add_argument("--actual-config", type=Path, default=DEFAULT_ACTUAL_CONFIG)
    parser.add_argument(
        "--mode",
        choices=("baseline", "instrumented", "narrow"),
        default="instrumented",
    )
    parser.add_argument("--cache-state", choices=("first_process", "warm_os_cache", "unknown"), default="unknown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    prepared = (
        prepare_actual_latest(args.actual_config)
        if args.workload == "actual_latest"
        else prepare_synthetic(
            args.workload, documents=args.documents, csv_rows=args.csv_rows
        )
    )
    try:
        measurement = run_measurement(
            prepared, mode=args.mode, cache_state=args.cache_state
        )
    finally:
        prepared.cleanup()
    rendered = json.dumps(measurement, ensure_ascii=False, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if measurement["result"]["validator_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
