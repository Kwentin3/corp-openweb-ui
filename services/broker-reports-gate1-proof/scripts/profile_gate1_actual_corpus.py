#!/usr/bin/env python3
"""Profile the maintained actual-corpus Gate 1 proof without exposing values."""

from __future__ import annotations

import argparse
import contextlib
import functools
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterator

import psutil


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
sys.path.insert(0, str(SERVICE_ROOT))
sys.path.insert(0, str(SCRIPT_DIR))

import broker_reports_gate1.full_source as full_source_module  # noqa: E402
import broker_reports_gate1.normalizer as normalizer_module  # noqa: E402
import broker_reports_gate1.pdf_layout as pdf_layout_module  # noqa: E402
import broker_reports_gate1.pdf_text_layer as pdf_text_module  # noqa: E402
import broker_reports_gate1.pdf_visual_memory as pdf_visual_module  # noqa: E402
import broker_reports_gate1.source_provenance as provenance_module  # noqa: E402
import broker_reports_gate1.table_projection as table_projection_module  # noqa: E402
import prove_gate1_actual_customer_corpus as proof_module  # noqa: E402


SCHEMA_VERSION = "broker_reports_gate1_actual_phase_profile_safe_v1"
DEFAULT_RAW_SAFE = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_runtime_audit"
    / "gate1"
    / "acceptance.safe.json"
)


def _safe_family(value: Any) -> str:
    normalized = str(value or "").casefold().lstrip(".")
    return {
        "htm": "html",
        "html_text": "html",
        "jpeg": "image",
        "jpg": "image",
        "png": "image",
    }.get(normalized, normalized if normalized in {
        "csv",
        "docx",
        "html",
        "image",
        "pdf",
        "txt",
        "xlsx",
        "xml",
        "zip",
    } else "other")


class MetricBook:
    def __init__(self) -> None:
        self.calls: Counter[str] = Counter()
        self.seconds: Counter[str] = Counter()
        self.maximum: defaultdict[str, float] = defaultdict(float)

    def add(self, label: str, elapsed: float) -> None:
        self.calls[label] += 1
        self.seconds[label] += elapsed
        self.maximum[label] = max(self.maximum[label], elapsed)

    def safe_rows(self) -> dict[str, dict[str, Any]]:
        return {
            label: {
                "calls": self.calls[label],
                "inclusive_wall_seconds": round(self.seconds[label], 6),
                "maximum_call_wall_seconds": round(self.maximum[label], 6),
            }
            for label in sorted(self.calls)
        }


def _family_from_file_input(args: tuple[Any, ...], _kwargs: dict[str, Any]) -> str:
    item = args[0]
    extension = normalizer_module.extension_from_name(
        item.original_filename_private,
        item.mime_type,
    )
    return "source_bytes." + _safe_family(extension)


def _family_from_full_source(
    _args: tuple[Any, ...], kwargs: dict[str, Any]
) -> str:
    return "full_source_build." + _safe_family(kwargs.get("container_format"))


def _family_from_projection(
    _args: tuple[Any, ...], kwargs: dict[str, Any]
) -> str:
    return "table_projection." + _safe_family(kwargs.get("source_format"))


def _static(label: str) -> Callable[[tuple[Any, ...], dict[str, Any]], str]:
    return lambda _args, _kwargs: label


@contextlib.contextmanager
def _installed_probe(
    metrics: MetricBook,
    owner: Any,
    name: str,
    labeler: Callable[[tuple[Any, ...], dict[str, Any]], str],
) -> Iterator[None]:
    original = getattr(owner, name)

    @functools.wraps(original)
    def measured(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            metrics.add(labeler(args, kwargs), time.perf_counter() - started)

    setattr(owner, name, measured)
    try:
        yield
    finally:
        setattr(owner, name, original)


@contextlib.contextmanager
def installed_probes(metrics: MetricBook) -> Iterator[None]:
    targets = [
        (
            normalizer_module.FileInput,
            "read_bytes",
            _family_from_file_input,
        ),
        (
            normalizer_module.Gate1ArchiveIntakeFactory().create().__class__,
            "inspect_and_expand",
            _static("archive.inspect_and_expand"),
        ),
        (
            full_source_module.FullSourceArtifactBuilder,
            "build",
            _family_from_full_source,
        ),
        (
            full_source_module.FullSourceArtifactBuilder,
            "_build_pdf_visual_units",
            _static("pdf.visual_unit_materialization"),
        ),
        (
            pdf_text_module.PypdfParserAdapter,
            "parse",
            _static("pdf.text_layer_parse"),
        ),
        (
            pdf_layout_module.PdfPlumberLayoutAdapter,
            "parse",
            _static("pdf.layout_parse"),
        ),
        (
            pdf_visual_module.PdfVisualMemoryRenderer,
            "render_pages",
            _static("pdf.page_render"),
        ),
        (
            provenance_module.NormalizedSliceProvenanceEnricher,
            "enrich_slices",
            _static("source_provenance.enrich_profile_slices"),
        ),
        (
            table_projection_module.NormalizedTableProjectionService,
            "build_for_document",
            _family_from_projection,
        ),
        (
            normalizer_module,
            "apply_domain_ingestion_artifacts",
            _static("post_parse.domain_ingestion"),
        ),
        (
            normalizer_module,
            "validate_artifacts",
            _static("post_parse.artifact_validation"),
        ),
        (
            normalizer_module,
            "render_safe_report",
            _static("post_parse.safe_report_render"),
        ),
        (
            proof_module,
            "_inventory",
            _static("proof.source_inventory"),
        ),
        (
            proof_module,
            "_reconcile",
            _static("proof.source_reconciliation"),
        ),
        (
            proof_module,
            "_build_inputs",
            _static("proof.input_construction"),
        ),
        (
            proof_module,
            "persist_gate1_result",
            _static("proof.artifactstore_persistence"),
        ),
        (
            proof_module,
            "_audit_public_handoff",
            _static("proof.public_handoff_audit"),
        ),
        (
            proof_module,
            "_resolved_private_artifacts",
            _static("proof.private_artifact_reload"),
        ),
        (
            proof_module,
            "_review_documents",
            _static("proof.actual_corpus_operator_review"),
        ),
    ]
    with contextlib.ExitStack() as stack:
        for owner, name, labeler in targets:
            stack.enter_context(_installed_probe(metrics, owner, name, labeler))
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


def _latest_store(config_path: Path, started_epoch: float) -> Path:
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    proof_root = Path(str(config["proof_work_root"]))
    candidates = []
    for run_root in proof_root.iterdir():
        database = run_root / "artifact_store" / "artifacts.sqlite3"
        if database.is_file() and database.stat().st_mtime >= started_epoch:
            candidates.append(database)
    if not candidates:
        raise RuntimeError("gate1_phase_profile_store_missing")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _artifact_storage_summary(database: Path) -> dict[str, Any]:
    conn = sqlite3.connect(database)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT artifact_type, COUNT(*), COALESCE(SUM(payload_size_bytes), 0)
            FROM artifact_records
            GROUP BY artifact_type
            ORDER BY artifact_type
            """
        ).fetchall()
        totals = conn.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(payload_size_bytes), 0)
            FROM artifact_records
            """
        ).fetchone()
        projection_rows = conn.execute(
            """
            SELECT payload_ref, payload_inline_json, checksum_sha256
            FROM artifact_records
            WHERE artifact_type = 'broker_reports_normalized_table_projection_v0'
            ORDER BY artifact_id
            """
        ).fetchall()
    finally:
        conn.close()
    by_type = {
        str(artifact_type): {
            "records": int(records),
            "payload_bytes": int(payload_bytes),
        }
        for artifact_type, records, payload_bytes in rows
    }
    return {
        "records_total": int(totals[0]),
        "payload_bytes_total": int(totals[1]),
        "by_artifact_type": by_type,
        "table_projections": _table_projection_storage_summary(
            database=database,
            rows=projection_rows,
        ),
    }


def _table_projection_storage_summary(
    *, database: Path, rows: list[sqlite3.Row]
) -> dict[str, Any]:
    payload_root = (database.parent / "payloads").resolve()
    by_format: dict[str, dict[str, Any]] = {}
    for row in rows:
        if row["payload_inline_json"]:
            projection = json.loads(str(row["payload_inline_json"]))
        else:
            payload_ref = str(row["payload_ref"] or "")
            payload_path = (payload_root / payload_ref).resolve()
            if not payload_ref or (
                payload_path != payload_root and payload_root not in payload_path.parents
            ):
                raise RuntimeError("gate1_phase_profile_payload_ref_invalid")
            projection = json.loads(payload_path.read_text(encoding="utf-8"))
        source_format = str(projection.get("source_format") or "unknown")
        summary = by_format.setdefault(
            source_format,
            {
                "projections_total": 0,
                "rows_total": 0,
                "cells_total": 0,
                "source_value_refs_total": 0,
                "payload_checksums": [],
                "projection_checksums": [],
            },
        )
        summary["projections_total"] += 1
        summary["rows_total"] += int(projection.get("row_count") or 0)
        summary["cells_total"] += int(projection.get("cell_count") or 0)
        summary["source_value_refs_total"] += len(
            projection.get("source_value_refs") or []
        )
        summary["payload_checksums"].append(str(row["checksum_sha256"] or ""))
        summary["projection_checksums"].append(
            str(projection.get("table_projection_checksum_ref") or "")
        )
    for summary in by_format.values():
        summary["payload_checksum_set_digest"] = _string_set_digest(
            summary.pop("payload_checksums")
        )
        summary["projection_checksum_set_digest"] = _string_set_digest(
            summary.pop("projection_checksums")
        )
    return {
        "by_source_format": {
            key: value for key, value in sorted(by_format.items())
        },
        "customer_values_in_output": False,
        "source_or_artifact_refs_in_output": False,
    }


def _string_set_digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def build_safe_report(
    *,
    revision: str,
    proof: dict[str, Any],
    metrics: MetricBook,
    total_wall_seconds: float,
    peak_rss_bytes: int,
    storage: dict[str, Any],
) -> dict[str, Any]:
    performance = dict(proof.get("performance") or {})
    actual = dict(proof.get("actual_execution") or {})
    return {
        "schema_version": SCHEMA_VERSION,
        "status": proof.get("proof_status"),
        "repository_revision": revision,
        "workload": {
            "top_level_inputs": actual.get("top_level_inputs_total"),
            "document_sources": actual.get("document_sources_total"),
            "logical_documents": actual.get("logical_documents_total"),
            "archive_containers": actual.get("archive_containers_total"),
            "archive_promoted_members": actual.get(
                "archive_promoted_members_total"
            ),
        },
        "resource_profile": {
            "profile_total_wall_seconds": round(total_wall_seconds, 6),
            "normalization_wall_seconds": performance.get(
                "gate1_normalization_wall_seconds"
            ),
            "proof_wall_seconds": performance.get("actual_proof_wall_seconds"),
            "process_peak_rss_bytes": peak_rss_bytes,
        },
        "inclusive_phase_profile": metrics.safe_rows(),
        "artifact_storage": storage,
        "terminal_outcome": {
            "proof_status": proof.get("proof_status"),
            "zero_silent_loss": actual.get("zero_silent_loss_status"),
            "terminal_status_counts": actual.get("terminal_status_counts"),
            "knowledge_rag_absent": dict(proof.get("automated_checks") or {}).get(
                "knowledge_rag_absent"
            ),
        },
        "interpretation_guards": {
            "inclusive_nested_times_must_not_be_summed": True,
            "instrumentation_changes_source_semantics": False,
            "provider_calls_added_by_profiler": 0,
            "visual_or_review_memory_dropped": False,
        },
        "privacy": {
            "customer_values_in_output": False,
            "private_paths_in_output": False,
            "source_or_artifact_refs_in_output": False,
            "raw_profile_private_or_ignored": True,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=proof_module.DEFAULT_CONFIG)
    parser.add_argument("--raw-safe-output", type=Path, default=DEFAULT_RAW_SAFE)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    revision = _git_revision()
    started_epoch = time.time()
    metrics = MetricBook()
    process = psutil.Process(os.getpid())
    original_argv = sys.argv
    sys.argv = [
        str(proof_module.__file__),
        "--config",
        str(args.config.resolve()),
        "--safe-output",
        str(args.raw_safe_output.resolve()),
    ]
    started = time.perf_counter()
    try:
        with installed_probes(metrics):
            proof_module.main()
    finally:
        sys.argv = original_argv
    total_wall = time.perf_counter() - started
    if _git_revision() != revision:
        raise RuntimeError("gate1_phase_profile_repository_revision_changed")
    proof = json.loads(args.raw_safe_output.read_text(encoding="utf-8"))
    storage = _artifact_storage_summary(
        _latest_store(args.config.resolve(), started_epoch)
    )
    report = build_safe_report(
        revision=revision,
        proof=proof,
        metrics=metrics,
        total_wall_seconds=total_wall,
        peak_rss_bytes=int(process.memory_info().peak_wset),
        storage=storage,
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
