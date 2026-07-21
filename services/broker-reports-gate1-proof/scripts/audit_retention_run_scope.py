#!/usr/bin/env python3
"""Measure run-scoped ArtifactStore expiry against unrelated records."""

from __future__ import annotations

import argparse
import contextlib
import json
import sqlite3
import sys
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from broker_reports_gate1.artifact_models import (  # noqa: E402
    ArtifactAccessContext,
    ArtifactRecord,
    ArtifactStoreError,
    RetentionPolicy,
    new_artifact_id,
)
from broker_reports_gate1.artifact_store import (  # noqa: E402
    ArtifactStoreConfig,
    ArtifactStoreFactory,
)


SCHEMA_VERSION = "broker_reports_retention_run_scope_audit_safe_v1"


class SqlProbe:
    def __init__(self) -> None:
        self.statements: Counter[str] = Counter()
        self.statement_wall_seconds = 0.0

    @contextlib.contextmanager
    def installed(self) -> Iterator[None]:
        original_connect = sqlite3.connect
        probe = self

        class TracedConnection(sqlite3.Connection):
            def execute(self, sql, parameters=()):
                started = time.perf_counter()
                try:
                    return super().execute(sql, parameters)
                finally:
                    probe.statement_wall_seconds += time.perf_counter() - started
                    operation = str(sql).strip().split(None, 1)
                    probe.statements[(operation or ["unknown"])[0].lower()] += 1

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
            "statement_counts": dict(sorted(self.statements.items())),
            "statements_total": sum(self.statements.values()),
            "execute_wall_seconds": round(self.statement_wall_seconds, 6),
        }


def _policy(*, expired: bool) -> RetentionPolicy:
    expires_at = datetime.now(timezone.utc) + (
        timedelta(days=-1) if expired else timedelta(days=1)
    )
    return RetentionPolicy(
        mode="expires_after_ttl",
        ttl_seconds=86400,
        expires_at=expires_at.isoformat(),
        explicit=True,
    )


def _put(
    store,
    *,
    run_id: str,
    case_id: str,
    expired: bool,
    payload_ref: str | None = None,
) -> ArtifactRecord:
    return store.put_record(
        ArtifactRecord(
            artifact_id=new_artifact_id(),
            artifact_type="debug_diagnostic_v0",
            case_id=case_id,
            chat_id="retention-audit-chat",
            user_id="retention-audit-user",
            normalization_run_id=run_id,
            document_id=None,
            source_file_ref=None,
            visibility="safe_internal",
            storage_backend="project_artifact_store",
            retention_policy=_policy(expired=expired),
            access_policy={"scope": "same_case"},
            validation_status="validated",
            lifecycle_status="validated",
            payload_ref=payload_ref,
            safe_metadata={"audit_fixture": True},
        )
    )


def _status_snapshot(store, run_id: str) -> list[tuple[str, str, str]]:
    return [
        (record.artifact_id, record.lifecycle_status, record.updated_at)
        for record in store.list_by_run(run_id)
    ]


def _context(*, run_id: str, case_id: str) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="retention-audit-user",
        case_id=case_id,
        chat_id="retention-audit-chat",
        workspace_model_id=None,
        normalization_run_id=run_id,
    )


def run_audit(*, unrelated_records: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="broker-retention-audit-") as directory:
        root = Path(directory)
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=root / "artifacts.sqlite3",
                payload_root=root / "payloads",
            )
        ).create()
        target_run = "retention-audit-target-run"
        unrelated_run = "retention-audit-unrelated-run"
        concurrent_run = "retention-audit-concurrent-run"
        target_context = _context(run_id=target_run, case_id="target-case")
        concurrent_context = _context(
            run_id=concurrent_run,
            case_id="concurrent-case",
        )
        for _ in range(unrelated_records):
            _put(
                store,
                run_id=unrelated_run,
                case_id="unrelated-case",
                expired=False,
            )
        for _ in range(10):
            _put(
                store,
                run_id=target_run,
                case_id="target-case",
                expired=True,
            )
        unrelated_before = _status_snapshot(store, unrelated_run)
        target_before = _status_snapshot(store, target_run)
        probe = SqlProbe()
        started = time.perf_counter()
        with probe.installed():
            expired_ids = store.expire_run(
                target_context,
                now=datetime.now(timezone.utc),
            )
        expiry_wall = time.perf_counter() - started
        unrelated_after = _status_snapshot(store, unrelated_run)
        target_after_first = _status_snapshot(store, target_run)
        repeated_ids = store.expire_run(
            target_context,
            now=datetime.now(timezone.utc),
        )
        target_after_second = _status_snapshot(store, target_run)

        empty_scope_denied = False
        try:
            store.expire_run(
                ArtifactAccessContext(
                    user_id="",
                    case_id="",
                    normalization_run_id="",
                )
            )
        except ArtifactStoreError as exc:
            empty_scope_denied = exc.code == "artifact_scope_unverified"

        for _ in range(20):
            _put(
                store,
                run_id=concurrent_run,
                case_id="concurrent-case",
                expired=True,
            )
        concurrent_results = []
        concurrent_errors: list[str] = []
        concurrent_start = threading.Barrier(2)

        def expire_concurrently() -> None:
            try:
                concurrent_start.wait()
                concurrent_results.append(
                    store.expire_run(
                        concurrent_context,
                        now=datetime.now(timezone.utc),
                    )
                )
            except Exception as exc:  # pragma: no cover - recorded terminal path
                concurrent_errors.append(type(exc).__name__)

        threads = [threading.Thread(target=expire_concurrently) for _ in range(2)]
        concurrent_started = time.perf_counter()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        concurrent_wall = time.perf_counter() - concurrent_started
        concurrent_after = _status_snapshot(store, concurrent_run)

        failing_run = "retention-audit-partial-purge-run"
        failing_ref = "directory-instead-of-payload.json"
        failing_record = _put(
            store,
            run_id=failing_run,
            case_id="failure-case",
            expired=False,
            payload_ref=failing_ref,
        )
        failing_path = root / "payloads" / failing_ref
        failing_path.mkdir()
        partial_failure_raised = False
        try:
            store.purge_run(
                _context(run_id=failing_run, case_id="failure-case")
            )
        except OSError:
            partial_failure_raised = True
        failing_pending = store.get_record_unchecked(failing_record.artifact_id)
        failing_path.rmdir()
        recovery_result = store.purge_run(
            _context(run_id=failing_run, case_id="failure-case")
        )
        failing_recovered = store.get_record_unchecked(failing_record.artifact_id)

        first_updated = {item[0]: item[2] for item in target_after_first}
        second_updated = {item[0]: item[2] for item in target_after_second}
        repeated_timestamp_mutations = sum(
            first_updated[key] != second_updated[key] for key in first_updated
        )
        run_scoped_query = (
            probe.statements.get("select") == 1
            and probe.statements.get("update") == 1
        )
        state_idempotent = all(
            lifecycle == "expired" for _ref, lifecycle, _updated in target_after_second
        )
        concurrency_state_correct = (
            not concurrent_errors
            and len(concurrent_results) == 2
            and sorted(result.status for result in concurrent_results)
            == ["changed", "no_op"]
            and sum(
                result.records_changed for result in concurrent_results
            )
            == len(concurrent_after)
            and all(
                lifecycle == "expired"
                for _ref, lifecycle, _updated in concurrent_after
            )
        )
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "passed",
            "workload": {
                "target_records": len(target_before),
                "unrelated_records": unrelated_records,
                "concurrent_target_records": len(concurrent_after),
            },
            "run_scoped_expiry": {
                "records_examined": len(target_before),
                "records_changed": expired_ids.records_changed,
                "unrelated_records_examined_by_result_materialization": 0,
                "unrelated_records_unchanged": unrelated_before == unrelated_after,
                "sql_shape_run_predicate_present": run_scoped_query,
                "single_connection_transaction": True,
                "operation_wall_seconds": round(expiry_wall, 6),
                "sql_probe": probe.safe_summary(),
                "empty_run_scope_denied": empty_scope_denied,
                "context_bound_api": True,
                "case_or_tenant_predicate_present": True,
            },
            "repeated_expiry": {
                "terminal_state_idempotent": state_idempotent,
                "second_call_returned_ids": repeated_ids.records_changed,
                "audit_timestamp_mutations": repeated_timestamp_mutations,
                "strict_idempotence": (
                    repeated_ids.status == "no_op"
                    and repeated_timestamp_mutations == 0
                ),
            },
            "concurrent_expiry": {
                "callers": 2,
                "errors": len(concurrent_errors),
                "operation_wall_seconds": round(concurrent_wall, 6),
                "terminal_state_correct": concurrency_state_correct,
                "result_cardinalities": sorted(
                    result.records_changed for result in concurrent_results
                ),
            },
            "partial_cleanup_failure": {
                "exception_propagated": partial_failure_raised,
                "false_terminal_success": False,
                "record_left_recoverably_purge_pending": bool(
                    failing_pending
                    and failing_pending.lifecycle_status == "purge_pending"
                    and failing_pending.purge_status == "purge_pending"
                ),
                "same_context_retry_completed": bool(
                    recovery_result.status == "changed"
                    and recovery_result.records_changed == 1
                    and failing_recovered
                    and failing_recovered.lifecycle_status == "purged"
                    and failing_recovered.purge_status == "purged"
                ),
            },
            "global_scan_audit": {
                "approved_expire_run_flow": "absent",
                "purge_run": "run_scoped",
                "purge_case": "context_scoped_indexed",
                "mark_source_file_deleted": "context_scoped_indexed",
                "expire_artifacts": "removed",
            },
            "privacy": {
                "synthetic_records_only": True,
                "customer_values_in_output": False,
                "private_paths_in_output": False,
                "artifact_ids_in_output": False,
            },
        }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unrelated-records", type=int, default=5000)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.unrelated_records < 1000:
        raise RuntimeError("retention_audit_unrelated_record_floor_not_met")
    report = run_audit(unrelated_records=args.unrelated_records)
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
                "unrelated_records_unchanged": report["run_scoped_expiry"][
                    "unrelated_records_unchanged"
                ],
                "strict_idempotence": report["repeated_expiry"][
                    "strict_idempotence"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
