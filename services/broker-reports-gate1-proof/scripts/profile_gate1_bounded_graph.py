#!/usr/bin/env python3
"""Measure the bounded actual-corpus Gate 1 path and prove safe equivalence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import psutil


SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_ROOT = SCRIPT_DIR.parent
REPO_ROOT = SERVICE_ROOT.parents[1]
PROOF_SCRIPT = SCRIPT_DIR / "prove_gate1_actual_customer_corpus.py"
DEFAULT_CONFIG = (
    REPO_ROOT / "local" / "stage2" / "broker_reports_customer_case_alpha.local.json"
)
DEFAULT_BASELINE_SAFE = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_runtime_audit"
    / "gate1"
    / "architecture_recovery_profile.safe.json"
)
DEFAULT_SAFE_OUTPUT = (
    REPO_ROOT
    / "local"
    / "stage2"
    / "broker_reports_goal3_bounded_graph"
    / "bounded_graph_profile.safe.json"
)
SCHEMA_VERSION = "broker_reports_gate1_bounded_graph_profile_safe_v1"
PEAK_RSS_LIMIT_BYTES = 5 * 1024**3
WALL_REGRESSION_LIMIT = 0.15

_REPRESENTATION_TYPES = {
    "private_normalized_source_payload_v0",
    "private_normalized_source_unit_v0",
    "private_normalized_table_slice_v0",
    "private_normalized_text_slice_v0",
    "broker_reports_normalized_table_projection_v0",
}

_VOLATILE_PAYLOAD_KEYS = {
    "created_at",
    "elapsed_milliseconds_total",
    "layout_elapsed_milliseconds",
}


class _ProcessSampler:
    def __init__(self, process: psutil.Process) -> None:
        self.process = process
        self.peak_rss_bytes = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._sample()
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5)
        self._sample()

    def _run(self) -> None:
        while not self._stop.wait(0.01):
            self._sample()

    def _sample(self) -> None:
        try:
            rss = self.process.memory_info().rss
            for child in self.process.children(recursive=True):
                try:
                    rss += child.memory_info().rss
                except psutil.Error:
                    continue
            self.peak_rss_bytes = max(self.peak_rss_bytes, int(rss))
        except psutil.Error:
            return


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--baseline-safe", type=Path, default=DEFAULT_BASELINE_SAFE)
    parser.add_argument("--baseline-store", type=Path, required=True)
    parser.add_argument("--safe-output", type=Path, default=DEFAULT_SAFE_OUTPUT)
    args = parser.parse_args()

    config = _read_json(args.config)
    proof_root = Path(config["proof_work_root"])
    before_runs = {path.resolve() for path in proof_root.glob("actual_gate1_*")}
    acceptance_output = args.safe_output.with_name("acceptance.safe.json")
    acceptance_output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(PROOF_SCRIPT),
        "--config",
        str(args.config),
        "--safe-output",
        str(acceptance_output),
    ]

    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=SERVICE_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    ps_process = psutil.Process(process.pid)
    sampler = _ProcessSampler(ps_process)
    checkpoints: dict[str, float] = {}
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def drain_stdout() -> None:
        assert process.stdout is not None
        stdout_lines.extend(process.stdout.readlines())

    def drain_stderr() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            stderr_lines.append(line)
            if line.startswith("proof_checkpoint="):
                checkpoints[line.strip().split("=", 1)[1]] = (
                    time.perf_counter() - started
                )

    stdout_thread = threading.Thread(target=drain_stdout, daemon=True)
    stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
    sampler.start()
    stdout_thread.start()
    stderr_thread.start()
    return_code = process.wait()
    stdout_thread.join(timeout=30)
    stderr_thread.join(timeout=30)
    sampler.stop()
    wall_seconds = time.perf_counter() - started
    if return_code != 0:
        terminal = "".join(stderr_lines[-20:]).strip()
        raise RuntimeError(
            f"bounded_actual_corpus_proof_failed:{return_code}:{terminal}"
        )

    after_runs = {path.resolve() for path in proof_root.glob("actual_gate1_*")}
    new_runs = sorted(
        after_runs - before_runs,
        key=lambda path: path.stat().st_mtime,
    )
    if len(new_runs) != 1:
        raise RuntimeError("bounded_actual_corpus_run_root_not_unique")
    candidate_store = new_runs[0] / "artifact_store" / "artifacts.sqlite3"
    if not candidate_store.is_file():
        raise RuntimeError("bounded_actual_corpus_store_missing")

    baseline_safe = _read_json(args.baseline_safe)
    baseline_store = args.baseline_store
    if baseline_store.resolve() == candidate_store.resolve():
        raise RuntimeError("baseline_store_must_precede_candidate")
    if not baseline_store.is_file():
        raise RuntimeError("baseline_store_missing")
    baseline = _store_signature(baseline_store)
    candidate = _store_signature(candidate_store)
    acceptance = _read_json(acceptance_output)

    baseline_resources = baseline_safe["resource_profile"]
    baseline_wall = float(baseline_resources["proof_wall_seconds"])
    baseline_normalization = float(baseline_resources["normalization_wall_seconds"])
    normalization_seconds = _checkpoint_delta(
        checkpoints,
        "normalization_started",
        "normalization_completed",
    )
    raw_representation_payloads_identical = (
        candidate["representation_checksum_set_digests"]
        == baseline["representation_checksum_set_digests"]
    )
    representation_payloads_equivalent = (
        candidate["representation_semantic_checksum_set_digests"]
        == baseline["representation_semantic_checksum_set_digests"]
    )
    checks = {
        "actual_corpus_proof_passed": acceptance.get("proof_status") == "passed",
        "source_identity_count_equal": (
            candidate["source_records_total"] == baseline["source_records_total"] == 104
        ),
        "artifact_type_counts_equal": (
            candidate["records_by_type"] == baseline["records_by_type"]
        ),
        "representation_counts_equal": (
            candidate["representation_records_by_type"]
            == baseline["representation_records_by_type"]
        ),
        "representation_payloads_deterministically_equivalent": (
            representation_payloads_equivalent
        ),
        "representation_differences_limited_to_declared_volatile_fields": (
            raw_representation_payloads_identical or representation_payloads_equivalent
        ),
        "all_artifact_payloads_deterministically_equivalent": (
            candidate["semantic_checksum_set_digests"]
            == baseline["semantic_checksum_set_digests"]
        ),
        "artifact_record_contracts_equivalent": (
            candidate["record_contract_set_digests"]
            == baseline["record_contract_set_digests"]
        ),
        "terminal_status_counts_equal": (
            acceptance["actual_execution"]["terminal_status_counts"]
            == baseline_safe["terminal_outcome"]["terminal_status_counts"]
        ),
        "zero_silent_loss_passed": (
            acceptance["actual_execution"]["zero_silent_loss_status"]
            == "passed_for_all_profile_accepted_documents"
        ),
        "artifactstore_immutable_after_gate2": acceptance["automated_checks"][
            "gate1_immutable_after_gate2"
        ],
        "gate2_public_boundary_validated": acceptance["automated_checks"][
            "gate2_public_boundary_validated"
        ],
        "peak_rss_at_or_below_5_gib": (sampler.peak_rss_bytes <= PEAK_RSS_LIMIT_BYTES),
        "proof_wall_regression_at_or_below_15_percent": (
            wall_seconds <= baseline_wall * (1 + WALL_REGRESSION_LIMIT)
        ),
    }
    status = "passed" if all(checks.values()) else "not_closed"
    report = {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "checks": checks,
        "baseline": {
            "repository_revision": baseline_safe.get("repository_revision"),
            "proof_wall_seconds": baseline_wall,
            "normalization_wall_seconds": baseline_normalization,
            "process_peak_rss_bytes": int(baseline_resources["process_peak_rss_bytes"]),
            "records_total": baseline["records_total"],
            "payload_bytes_total": baseline["payload_bytes_total"],
            "source_records_total": baseline["source_records_total"],
        },
        "candidate": {
            "proof_wall_seconds": round(wall_seconds, 6),
            "normalization_wall_seconds": round(normalization_seconds, 6),
            "process_peak_rss_bytes": sampler.peak_rss_bytes,
            "records_total": candidate["records_total"],
            "payload_bytes_total": candidate["payload_bytes_total"],
            "source_records_total": candidate["source_records_total"],
            "checkpoint_seconds": {
                key: round(value, 6) for key, value in sorted(checkpoints.items())
            },
        },
        "limits": {
            "peak_rss_bytes": PEAK_RSS_LIMIT_BYTES,
            "wall_regression_fraction": WALL_REGRESSION_LIMIT,
            "proof_wall_limit_seconds": round(
                baseline_wall * (1 + WALL_REGRESSION_LIMIT), 6
            ),
            "normalization_wall_limit_seconds": round(
                baseline_normalization * (1 + WALL_REGRESSION_LIMIT), 6
            ),
        },
        "diagnostics": {
            "representation_payloads_byte_identical": (
                raw_representation_payloads_identical
            ),
            "payload_bytes_delta": (
                candidate["payload_bytes_total"] - baseline["payload_bytes_total"]
            ),
            "normalization_checkpoint_at_or_below_15_percent": (
                normalization_seconds
                <= baseline_normalization * (1 + WALL_REGRESSION_LIMIT)
            ),
            "normalization_checkpoint_comparable": False,
            "normalization_checkpoint_scope": (
                "candidate_includes_bounded_artifact_persistence"
            ),
            "volatile_payload_keys_excluded_from_deterministic_equivalence": (
                sorted(_VOLATILE_PAYLOAD_KEYS)
            ),
            "absolute_retention_expiry_excluded_from_cross_run_contract": True,
        },
        "equivalence": {
            "records_by_type": candidate["records_by_type"],
            "representation_records_by_type": candidate[
                "representation_records_by_type"
            ],
            "representation_checksum_set_digests": candidate[
                "representation_checksum_set_digests"
            ],
            "representation_semantic_checksum_set_digests": candidate[
                "representation_semantic_checksum_set_digests"
            ],
            "semantic_checksum_set_digests": candidate["semantic_checksum_set_digests"],
            "record_contract_set_digests": candidate["record_contract_set_digests"],
            "artifact_ids_in_output": False,
            "customer_values_in_output": False,
            "private_paths_in_output": False,
        },
        "terminal": {
            "document_sources_total": acceptance["actual_execution"][
                "document_sources_total"
            ],
            "logical_documents_total": acceptance["actual_execution"][
                "logical_documents_total"
            ],
            "terminal_status_counts": acceptance["actual_execution"][
                "terminal_status_counts"
            ],
            "zero_silent_loss_status": acceptance["actual_execution"][
                "zero_silent_loss_status"
            ],
        },
        "privacy": {
            "customer_values_in_output": False,
            "private_paths_in_output": False,
            "artifact_ids_in_output": False,
            "subprocess_stdout_in_output": False,
            "subprocess_stderr_in_output": False,
        },
    }
    _write_json(args.safe_output, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    if status != "passed":
        raise SystemExit(1)


def _store_totals(database: Path) -> tuple[int, int]:
    conn = sqlite3.connect(database)
    try:
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(payload_size_bytes), 0) "
            "FROM artifact_records"
        ).fetchone()
    finally:
        conn.close()
    return int(row[0]), int(row[1])


def _store_signature(database: Path) -> dict[str, Any]:
    conn = sqlite3.connect(database)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT rowid, artifact_id, artifact_type, document_id, "
            "payload_ref, payload_inline_json, checksum_sha256, "
            "payload_size_bytes, source_file_ref_json, visibility, "
            "storage_backend, retention_policy_json, expires_at, "
            "purge_status, lifecycle_status, access_policy_json, "
            "validation_status, payload_kind, safe_metadata_json, "
            "warning_codes_json FROM artifact_records ORDER BY rowid"
        ).fetchall()
    finally:
        conn.close()
    id_tokens = _artifact_id_tokens(rows)
    records_by_type: Counter[str] = Counter()
    bytes_by_type: Counter[str] = Counter()
    raw_checksums: defaultdict[str, list[str]] = defaultdict(list)
    semantic_checksums: defaultdict[str, list[str]] = defaultdict(list)
    record_contract_checksums: defaultdict[str, list[str]] = defaultdict(list)
    for row in rows:
        artifact_type = str(row["artifact_type"])
        records_by_type[artifact_type] += 1
        bytes_by_type[artifact_type] += int(row["payload_size_bytes"] or 0)
        raw_checksums[artifact_type].append(str(row["checksum_sha256"] or ""))
        payload = _read_payload(database, row)
        normalized = _normalize_payload(payload, id_tokens)
        semantic_checksums[artifact_type].append(_sha256_json(normalized))
        record_contract_checksums[artifact_type].append(
            _sha256_json(_record_contract(row, id_tokens))
        )
        del payload, normalized
    representation_records = {
        key: records_by_type.get(key, 0) for key in sorted(_REPRESENTATION_TYPES)
    }
    return {
        "records_total": len(rows),
        "payload_bytes_total": sum(bytes_by_type.values()),
        "source_records_total": records_by_type.get("source_file_ref_v0", 0),
        "records_by_type": dict(sorted(records_by_type.items())),
        "payload_bytes_by_type": dict(sorted(bytes_by_type.items())),
        "representation_records_by_type": representation_records,
        "representation_checksum_set_digests": {
            key: _string_set_digest(raw_checksums.get(key, []))
            for key in sorted(_REPRESENTATION_TYPES)
        },
        "representation_semantic_checksum_set_digests": {
            key: _string_set_digest(semantic_checksums.get(key, []))
            for key in sorted(_REPRESENTATION_TYPES)
        },
        "semantic_checksum_set_digests": {
            key: _string_set_digest(values)
            for key, values in sorted(semantic_checksums.items())
        },
        "record_contract_set_digests": {
            key: _string_set_digest(values)
            for key, values in sorted(record_contract_checksums.items())
        },
    }


def _artifact_id_tokens(rows: list[sqlite3.Row]) -> dict[str, str]:
    ordinals: Counter[tuple[str, str]] = Counter()
    result = {}
    for row in sorted(
        rows,
        key=lambda item: (
            str(item["artifact_type"]),
            str(item["document_id"] or ""),
            int(item["rowid"]),
        ),
    ):
        key = (str(row["artifact_type"]), str(row["document_id"] or "run"))
        ordinals[key] += 1
        result[str(row["artifact_id"])] = f"@artifact:{key[0]}:{key[1]}:{ordinals[key]}"
    return result


def _read_payload(database: Path, row: sqlite3.Row) -> Any:
    inline = row["payload_inline_json"]
    if inline is not None:
        return json.loads(str(inline))
    payload_ref = str(row["payload_ref"] or "")
    payload_root = (database.parent / "payloads").resolve()
    payload_path = (payload_root / payload_ref).resolve()
    if not payload_ref or (
        payload_path != payload_root and payload_root not in payload_path.parents
    ):
        raise RuntimeError("artifact_payload_ref_invalid")
    return json.loads(payload_path.read_text(encoding="utf-8"))


def _normalize_payload(value: Any, id_tokens: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_payload(child, id_tokens)
            for key, child in sorted(value.items())
            if key not in _VOLATILE_PAYLOAD_KEYS
        }
    if isinstance(value, list):
        return [_normalize_payload(child, id_tokens) for child in value]
    if isinstance(value, str):
        return id_tokens.get(value, value)
    return value


def _record_contract(
    row: sqlite3.Row,
    id_tokens: dict[str, str],
) -> dict[str, Any]:
    def decoded(name: str) -> Any:
        raw = row[name]
        return json.loads(str(raw)) if raw is not None else None

    retention_policy = decoded("retention_policy_json")
    retention_policy_expiry = None
    if isinstance(retention_policy, dict):
        retention_policy = dict(retention_policy)
        retention_policy_expiry = retention_policy.pop("expires_at", None)
    record_expiry = row["expires_at"]
    return {
        "artifact_type": str(row["artifact_type"]),
        "document_id": row["document_id"],
        "source_file_ref": _normalize_payload(
            decoded("source_file_ref_json"), id_tokens
        ),
        "visibility": row["visibility"],
        "storage_backend": row["storage_backend"],
        "retention_policy": retention_policy,
        "expiration_binding": {
            "scheduled": record_expiry is not None,
            "record_matches_policy": record_expiry == retention_policy_expiry,
        },
        "purge_status": row["purge_status"],
        "lifecycle_status": row["lifecycle_status"],
        "access_policy": decoded("access_policy_json"),
        "validation_status": row["validation_status"],
        "payload_kind": row["payload_kind"],
        "safe_metadata": _normalize_payload(decoded("safe_metadata_json"), id_tokens),
        "warning_codes": decoded("warning_codes_json"),
    }


def _checkpoint_delta(
    checkpoints: dict[str, float],
    start: str,
    end: str,
) -> float:
    if start not in checkpoints or end not in checkpoints:
        raise RuntimeError("bounded_profile_checkpoint_missing")
    return checkpoints[end] - checkpoints[start]


def _string_set_digest(values: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError("json_object_required")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
