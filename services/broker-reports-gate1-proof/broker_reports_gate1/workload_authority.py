"""Persisted Broker Reports workload admission, progress and cancellation.

The authority deliberately uses SQLite transactions instead of process-local
locks.  OpenWebUI can host more than one Function instance or worker process;
all of them must observe the same queue, capacity counters and worker leases.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Iterator, Mapping


WORKLOAD_AUTHORITY_CONTRACT_VERSION = "broker_reports_workload_authority_v1"
WORKLOAD_AUTHORITY_IMPLEMENTATION_STATUS = "maintained"
WORKLOAD_AUTHORITY_COORDINATION_SCOPE = "sqlite_cross_process_single_authority"
WORKLOAD_ADMISSION_POLICY = "capacity_queue_plus_worker_lease"
WORKLOAD_PRIMARY_WALL_TIMEOUT = None
LOCAL_OCR_WORKER_POOL_ALLOWED = False

GATE1_HEAVY_CONCURRENCY = 1
GATE2_LOCAL_MAXIMUM_CONCURRENCY = 2

FACTORY_REQUIRED = (
    "WorkloadAuthorityFactory.create is the only maintained Broker Reports "
    "workload authority entrypoint"
)
FORBIDDEN = (
    "Production Broker Reports entrypoints must not create process-local "
    "scheduler queues, bypass persisted admission, publish success after "
    "cancellation, or create a local OCR worker pool"
)

_SAFE_CODE_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
_SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})
_ACTIVE_LOCAL_STATES = frozenset(
    {
        "source_intake",
        "normalizing",
        "building_document_memory",
        "validating",
        "preparing_gate2",
        "awaiting_provider",
    }
)


class WorkloadKind(str, Enum):
    PRIVATE_SOURCE_INTAKE = "private_source_intake"
    GATE1 = "gate1"
    GATE2_SOURCE = "gate2_source"
    GATE2_DOMAIN = "gate2_domain"
    REVIEW = "review"
    LIGHTWEIGHT_ADAPTER = "lightweight_adapter"


class WorkloadResourceClass(str, Enum):
    SOURCE_INTAKE = "source_intake"
    GATE1_HEAVY = "gate1_heavy"
    GATE2_LOCAL = "gate2_local"
    REVIEW_WAITING = "review_waiting"
    LIGHTWEIGHT_DETERMINISTIC = "lightweight_deterministic"


class WorkloadState(str, Enum):
    QUEUED = "queued"
    SOURCE_INTAKE = "source_intake"
    NORMALIZING = "normalizing"
    BUILDING_DOCUMENT_MEMORY = "building_document_memory"
    VALIDATING = "validating"
    PREPARING_GATE2 = "preparing_gate2"
    AWAITING_PROVIDER = "awaiting_provider"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


REQUIRED_PERSISTED_STATES = tuple(state.value for state in WorkloadState)


_KIND_RESOURCE = {
    WorkloadKind.PRIVATE_SOURCE_INTAKE: WorkloadResourceClass.SOURCE_INTAKE,
    WorkloadKind.GATE1: WorkloadResourceClass.GATE1_HEAVY,
    WorkloadKind.GATE2_SOURCE: WorkloadResourceClass.GATE2_LOCAL,
    WorkloadKind.GATE2_DOMAIN: WorkloadResourceClass.GATE2_LOCAL,
    WorkloadKind.REVIEW: WorkloadResourceClass.REVIEW_WAITING,
    WorkloadKind.LIGHTWEIGHT_ADAPTER: WorkloadResourceClass.LIGHTWEIGHT_DETERMINISTIC,
}

_INITIAL_STATE = {
    WorkloadKind.PRIVATE_SOURCE_INTAKE: WorkloadState.SOURCE_INTAKE,
    WorkloadKind.GATE1: WorkloadState.SOURCE_INTAKE,
    WorkloadKind.GATE2_SOURCE: WorkloadState.PREPARING_GATE2,
    WorkloadKind.GATE2_DOMAIN: WorkloadState.PREPARING_GATE2,
    WorkloadKind.REVIEW: WorkloadState.AWAITING_REVIEW,
    WorkloadKind.LIGHTWEIGHT_ADAPTER: WorkloadState.VALIDATING,
}

_ALLOWED_TRANSITIONS = {
    WorkloadState.SOURCE_INTAKE: frozenset(
        {
            WorkloadState.NORMALIZING,
            WorkloadState.VALIDATING,
            WorkloadState.AWAITING_PROVIDER,
        }
    ),
    WorkloadState.NORMALIZING: frozenset(
        {
            WorkloadState.BUILDING_DOCUMENT_MEMORY,
            WorkloadState.VALIDATING,
            WorkloadState.AWAITING_PROVIDER,
        }
    ),
    WorkloadState.BUILDING_DOCUMENT_MEMORY: frozenset(
        {WorkloadState.VALIDATING, WorkloadState.AWAITING_PROVIDER}
    ),
    WorkloadState.VALIDATING: frozenset(
        {
            WorkloadState.AWAITING_PROVIDER,
            WorkloadState.AWAITING_REVIEW,
        }
    ),
    WorkloadState.PREPARING_GATE2: frozenset(
        {WorkloadState.AWAITING_PROVIDER, WorkloadState.VALIDATING}
    ),
    WorkloadState.AWAITING_PROVIDER: frozenset(
        {
            WorkloadState.NORMALIZING,
            WorkloadState.BUILDING_DOCUMENT_MEMORY,
            WorkloadState.VALIDATING,
            WorkloadState.PREPARING_GATE2,
            WorkloadState.AWAITING_REVIEW,
        }
    ),
    WorkloadState.AWAITING_REVIEW: frozenset(),
}


class WorkloadAuthorityError(RuntimeError):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


class WorkloadCancelledError(WorkloadAuthorityError):
    def __init__(self) -> None:
        super().__init__(
            "workload_cancelled",
            "Broker Reports workload cancellation was requested",
        )


@dataclass(frozen=True)
class WorkloadAccessContext:
    user_id: str
    case_id: str | None = None
    chat_id: str | None = None
    workspace_model_id: str | None = None

    def __post_init__(self) -> None:
        if not str(self.user_id or "").strip():
            raise WorkloadAuthorityError(
                "workload_authentication_required",
                "Authenticated server user context is required",
            )
        if not self.case_id and not self.chat_id:
            raise WorkloadAuthorityError(
                "workload_scope_required",
                "Server-attested case or chat context is required",
            )

    @classmethod
    def from_artifact_context(cls, context: Any) -> "WorkloadAccessContext":
        return cls(
            user_id=str(getattr(context, "user_id", "") or ""),
            case_id=_optional_text(getattr(context, "case_id", None)),
            chat_id=_optional_text(getattr(context, "chat_id", None)),
            workspace_model_id=_optional_text(
                getattr(context, "workspace_model_id", None)
            ),
        )


DEFAULT_PROVIDER_BUDGETS = {
    "google_gemini": 1,
    "openai_gpt": 2,
    "anthropic_claude": 1,
    "deepseek": 1,
    "zai_glm": 1,
    "alibaba_qwen": 1,
    "openwebui_completion": 2,
}


@dataclass(frozen=True)
class WorkloadAuthorityConfig:
    sqlite_path: Path
    temp_root: Path
    gate1_concurrency: int = GATE1_HEAVY_CONCURRENCY
    gate2_concurrency: int = GATE2_LOCAL_MAXIMUM_CONCURRENCY
    source_intake_concurrency: int = 4
    lightweight_concurrency: int = 8
    provider_budgets: Mapping[str, int] = field(
        default_factory=lambda: dict(DEFAULT_PROVIDER_BUDGETS)
    )
    lease_seconds: float = 90.0
    poll_interval_seconds: float = 0.2
    heartbeat_interval_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sqlite_path", Path(self.sqlite_path))
        object.__setattr__(self, "temp_root", Path(self.temp_root))
        budgets = {str(key): int(value) for key, value in self.provider_budgets.items()}
        object.__setattr__(self, "provider_budgets", budgets)
        if self.gate1_concurrency != GATE1_HEAVY_CONCURRENCY:
            raise WorkloadAuthorityError("workload_gate1_concurrency_must_equal_one")
        if not 1 <= self.gate2_concurrency <= GATE2_LOCAL_MAXIMUM_CONCURRENCY:
            raise WorkloadAuthorityError("workload_gate2_concurrency_exceeds_two")
        if self.source_intake_concurrency < 1 or self.lightweight_concurrency < 1:
            raise WorkloadAuthorityError("workload_local_capacity_invalid")
        if not budgets or any(
            not _SAFE_CODE_RE.fullmatch(key) or value < 1
            for key, value in budgets.items()
        ):
            raise WorkloadAuthorityError("workload_provider_budget_invalid")
        if self.lease_seconds < 0.2:
            raise WorkloadAuthorityError("workload_lease_too_short")
        if self.poll_interval_seconds <= 0:
            raise WorkloadAuthorityError("workload_poll_interval_invalid")
        heartbeat = self.heartbeat_interval_seconds
        if heartbeat is None:
            heartbeat = max(0.05, min(10.0, self.lease_seconds / 3.0))
            object.__setattr__(self, "heartbeat_interval_seconds", heartbeat)
        if heartbeat <= 0 or heartbeat >= self.lease_seconds:
            raise WorkloadAuthorityError("workload_heartbeat_interval_invalid")

    def safe_contract(self) -> dict[str, Any]:
        return {
            "contract_version": WORKLOAD_AUTHORITY_CONTRACT_VERSION,
            "coordination_scope": WORKLOAD_AUTHORITY_COORDINATION_SCOPE,
            "admission_policy": WORKLOAD_ADMISSION_POLICY,
            "gate1_concurrency": self.gate1_concurrency,
            "gate2_concurrency": self.gate2_concurrency,
            "source_intake_concurrency": self.source_intake_concurrency,
            "lightweight_concurrency": self.lightweight_concurrency,
            "provider_budgets": dict(sorted(self.provider_budgets.items())),
            "lease_seconds": self.lease_seconds,
            "primary_wall_timeout": WORKLOAD_PRIMARY_WALL_TIMEOUT,
            "local_ocr_worker_pool": LOCAL_OCR_WORKER_POOL_ALLOWED,
        }


@dataclass(frozen=True)
class WorkloadTicket:
    job_id: str
    job_kind: WorkloadKind
    resource_class: WorkloadResourceClass


class WorkloadAuthorityFactory:
    def __init__(self, config: WorkloadAuthorityConfig) -> None:
        self.config = config

    def create(self) -> "WorkloadAuthority":
        return WorkloadAuthority(self.config, _factory_token=_FACTORY_TOKEN)


class _FactoryToken:
    pass


_FACTORY_TOKEN = _FactoryToken()


class WorkloadAuthority:
    def __init__(
        self,
        config: WorkloadAuthorityConfig,
        *,
        _factory_token: _FactoryToken,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise WorkloadAuthorityError("workload_authority_factory_required")
        self.config = config
        self._ensure_schema_and_contract()
        self.recover_expired_workers()
        self._retry_pending_cleanup()

    def submit(
        self,
        *,
        job_kind: WorkloadKind | str,
        access: WorkloadAccessContext,
        retry_of_job_id: str | None = None,
        safe_metadata: Mapping[str, Any] | None = None,
    ) -> WorkloadTicket:
        kind = _workload_kind(job_kind)
        resource_class = _KIND_RESOURCE[kind]
        retry_of = str(retry_of_job_id or "").strip() or None
        if retry_of:
            self._validate_retry_source(retry_of, access, kind)
        metadata = _safe_metadata(safe_metadata)
        job_id = "brjob_" + secrets.token_hex(16)
        temp_dir = self.config.temp_root / job_id
        self._create_private_temp_dir(temp_dir)
        now_iso = _utc_now_iso()
        try:
            with self._connect(immediate=True) as conn:
                conn.execute(
                    """
                    INSERT INTO workload_jobs(
                        job_id, job_kind, resource_class,
                        user_id, case_id, chat_id, workspace_model_id,
                        state, progress_sequence, cancel_requested,
                        retry_of_job_id, safe_metadata_json, temp_dir,
                        cleanup_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'queued', 0, 0, ?, ?, ?,
                              'pending', ?, ?)
                    """,
                    (
                        job_id,
                        kind.value,
                        resource_class.value,
                        access.user_id,
                        access.case_id,
                        access.chat_id,
                        access.workspace_model_id,
                        retry_of,
                        _canonical_json(metadata),
                        str(temp_dir),
                        now_iso,
                        now_iso,
                    ),
                )
                self._insert_transition(
                    conn,
                    job_id=job_id,
                    sequence=0,
                    from_state=None,
                    to_state=WorkloadState.QUEUED,
                    event_code="submitted",
                    safe_detail={"retry_of_job_id": retry_of},
                )
        except BaseException:
            self._remove_owned_temp_dir(temp_dir)
            raise
        return WorkloadTicket(job_id, kind, resource_class)

    def retry(
        self,
        *,
        job_id: str,
        access: WorkloadAccessContext,
        safe_metadata: Mapping[str, Any] | None = None,
    ) -> WorkloadTicket:
        snapshot = self.snapshot(job_id=job_id, access=access)
        if snapshot["state"] not in {
            WorkloadState.FAILED.value,
            WorkloadState.CANCELLED.value,
        }:
            raise WorkloadAuthorityError("workload_retry_source_not_retryable")
        return self.submit(
            job_kind=snapshot["job_kind"],
            access=access,
            retry_of_job_id=job_id,
            safe_metadata=safe_metadata,
        )

    def try_admit(
        self,
        *,
        job_id: str,
        access: WorkloadAccessContext,
        worker_id: str | None = None,
    ) -> "WorkloadSession | None":
        self.recover_expired_workers()
        worker = _safe_identifier(worker_id or f"worker_{os.getpid()}_{threading.get_ident()}")
        lease_token = "brlease_" + secrets.token_hex(24)
        now_epoch = time.time()
        now_iso = _utc_now_iso()
        expires = now_epoch + self.config.lease_seconds
        with self._connect(immediate=True) as conn:
            row = self._authorized_row(conn, job_id, access)
            if row["state"] in _TERMINAL_STATES:
                raise WorkloadAuthorityError("workload_job_already_terminal")
            if bool(row["cancel_requested"]):
                self._cancel_without_worker(conn, row, "cancelled_before_admission")
                cleanup_path = Path(str(row["temp_dir"]))
            else:
                cleanup_path = None
            if cleanup_path is not None:
                admitted = None
            elif row["state"] != WorkloadState.QUEUED.value:
                raise WorkloadAuthorityError("workload_job_already_admitted")
            elif not self._is_queue_head(conn, row):
                admitted = None
            elif self._active_count(conn, str(row["resource_class"]), now_epoch) >= (
                self._capacity(str(row["resource_class"]))
            ):
                admitted = None
            else:
                initial_state = _INITIAL_STATE[WorkloadKind(str(row["job_kind"]))]
                sequence = int(row["progress_sequence"]) + 1
                updated = conn.execute(
                    """
                    UPDATE workload_jobs
                    SET state = ?, progress_sequence = ?, worker_id = ?,
                        lease_token = ?, lease_expires_epoch = ?,
                        admitted_at = COALESCE(admitted_at, ?), updated_at = ?
                    WHERE job_id = ? AND state = 'queued' AND cancel_requested = 0
                    """,
                    (
                        initial_state.value,
                        sequence,
                        worker,
                        lease_token,
                        expires,
                        now_iso,
                        now_iso,
                        job_id,
                    ),
                ).rowcount
                if updated != 1:
                    admitted = None
                else:
                    self._insert_transition(
                        conn,
                        job_id=job_id,
                        sequence=sequence,
                        from_state=WorkloadState.QUEUED,
                        to_state=initial_state,
                        event_code="admitted",
                        safe_detail={"resource_class": row["resource_class"]},
                    )
                    admitted = WorkloadSession(
                        authority=self,
                        job_id=job_id,
                        access=access,
                        worker_id=worker,
                        lease_token=lease_token,
                        temp_dir=Path(str(row["temp_dir"])),
                    )
        if cleanup_path is not None:
            self._finalize_cleanup(job_id, cleanup_path)
            raise WorkloadCancelledError()
        return admitted

    async def wait_for_admission(
        self,
        *,
        job_id: str,
        access: WorkloadAccessContext,
        worker_id: str | None = None,
        on_wait: Callable[[dict[str, Any]], Any] | None = None,
    ) -> "WorkloadSession":
        """Wait on persisted capacity without imposing a fixed job wall timeout."""

        last_position: int | None = None
        while True:
            session = self.try_admit(
                job_id=job_id,
                access=access,
                worker_id=worker_id,
            )
            if session is not None:
                return session
            snapshot = self.snapshot(job_id=job_id, access=access)
            if snapshot["state"] == WorkloadState.CANCELLED.value:
                raise WorkloadCancelledError()
            position = snapshot["queue_position"]
            if on_wait is not None and position != last_position:
                result = on_wait(snapshot)
                if hasattr(result, "__await__"):
                    await result
            last_position = position
            await asyncio.sleep(self.config.poll_interval_seconds)

    def snapshot(
        self,
        *,
        job_id: str,
        access: WorkloadAccessContext,
    ) -> dict[str, Any]:
        self.recover_expired_workers()
        self._retry_pending_cleanup()
        with self._connect() as conn:
            row = self._authorized_row(conn, job_id, access)
            queue_position = None
            if row["state"] == WorkloadState.QUEUED.value:
                queue_position = int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM workload_jobs
                        WHERE resource_class = ? AND state = 'queued'
                          AND sequence <= ?
                        """,
                        (row["resource_class"], row["sequence"]),
                    ).fetchone()[0]
                )
            provider_queue_position = None
            waiter = conn.execute(
                "SELECT sequence, provider_id FROM workload_provider_waiters WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if waiter is not None:
                provider_queue_position = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM workload_provider_waiters
                        WHERE provider_id = ? AND sequence <= ?
                        """,
                        (waiter["provider_id"], waiter["sequence"]),
                    ).fetchone()[0]
                )
            return {
                "schema_version": WORKLOAD_AUTHORITY_CONTRACT_VERSION,
                "job_id": str(row["job_id"]),
                "job_kind": str(row["job_kind"]),
                "resource_class": str(row["resource_class"]),
                "state": str(row["state"]),
                "progress_sequence": int(row["progress_sequence"]),
                "queue_position": queue_position,
                "provider_id": _optional_text(row["provider_id"]),
                "provider_queue_position": provider_queue_position,
                "cancel_requested": bool(row["cancel_requested"]),
                "retry_of_job_id": _optional_text(row["retry_of_job_id"]),
                "terminal_code": _optional_text(row["terminal_code"]),
                "cleanup_status": str(row["cleanup_status"]),
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "terminal_at": _optional_text(row["terminal_at"]),
                "primary_wall_timeout": WORKLOAD_PRIMARY_WALL_TIMEOUT,
            }

    def transitions(
        self,
        *,
        job_id: str,
        access: WorkloadAccessContext,
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            self._authorized_row(conn, job_id, access)
            rows = conn.execute(
                """
                SELECT sequence, from_state, to_state, event_code,
                       safe_detail_json, created_at
                FROM workload_transitions
                WHERE job_id = ? ORDER BY event_id
                """,
                (job_id,),
            ).fetchall()
        return [
            {
                "sequence": int(row["sequence"]),
                "from_state": _optional_text(row["from_state"]),
                "to_state": str(row["to_state"]),
                "event_code": str(row["event_code"]),
                "safe_detail": json.loads(str(row["safe_detail_json"])),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def request_cancel(
        self,
        *,
        job_id: str,
        access: WorkloadAccessContext,
        reason_code: str = "user_requested",
    ) -> dict[str, Any]:
        reason = _safe_code(reason_code, "workload_cancel_reason_invalid")
        cleanup_path: Path | None = None
        already_terminal = False
        with self._connect(immediate=True) as conn:
            row = self._authorized_row(conn, job_id, access)
            if row["state"] in _TERMINAL_STATES:
                already_terminal = True
            else:
                now_iso = _utc_now_iso()
                conn.execute(
                    """
                    UPDATE workload_jobs
                    SET cancel_requested = 1, cancel_reason_code = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    (reason, now_iso, job_id),
                )
                conn.execute(
                    "DELETE FROM workload_provider_waiters WHERE job_id = ?",
                    (job_id,),
                )
                if row["state"] in {
                    WorkloadState.QUEUED.value,
                    WorkloadState.AWAITING_REVIEW.value,
                } or not row["lease_token"]:
                    self._cancel_without_worker(conn, row, reason)
                    cleanup_path = Path(str(row["temp_dir"]))
        if cleanup_path is not None:
            self._finalize_cleanup(job_id, cleanup_path)
        if already_terminal:
            return self.snapshot(job_id=job_id, access=access)
        return self.snapshot(job_id=job_id, access=access)

    def resolve_review(
        self,
        *,
        job_id: str,
        access: WorkloadAccessContext,
        decision: str,
        review_receipt_ref: str,
    ) -> dict[str, Any]:
        """Resolve a waiting job from an already validated review receipt."""

        normalized_decision = _safe_code(
            decision,
            "workload_review_decision_invalid",
        )
        if normalized_decision not in {
            "accepted",
            "rejected",
            "unsupported",
            "unresolved",
        }:
            raise WorkloadAuthorityError("workload_review_decision_invalid")
        receipt_ref = str(review_receipt_ref or "").strip()
        if not _SAFE_REF_RE.fullmatch(receipt_ref):
            raise WorkloadAuthorityError("workload_review_receipt_ref_invalid")
        with self._connect(immediate=True) as conn:
            row = self._authorized_row(conn, job_id, access)
            if row["state"] != WorkloadState.AWAITING_REVIEW.value:
                raise WorkloadAuthorityError("workload_review_not_waiting")
            sequence = int(row["progress_sequence"]) + 1
            now_iso = _utc_now_iso()
            if normalized_decision == "accepted":
                target = WorkloadState.COMPLETED
                terminal_code = "review_accepted"
            elif normalized_decision in {"rejected", "unsupported"}:
                target = WorkloadState.FAILED
                terminal_code = f"review_{normalized_decision}"
            else:
                target = WorkloadState.AWAITING_REVIEW
                terminal_code = None
            conn.execute(
                """
                UPDATE workload_jobs
                SET state = ?, progress_sequence = ?, terminal_code = ?,
                    terminal_at = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    target.value,
                    sequence,
                    terminal_code,
                    now_iso if target.value in _TERMINAL_STATES else None,
                    now_iso,
                    job_id,
                ),
            )
            self._insert_transition(
                conn,
                job_id=job_id,
                sequence=sequence,
                from_state=WorkloadState.AWAITING_REVIEW,
                to_state=target,
                event_code=terminal_code or "review_unresolved",
                safe_detail={
                    "review_decision": normalized_decision,
                    "review_receipt_ref": receipt_ref,
                    "partial_success_published": False,
                },
            )
        return self.snapshot(job_id=job_id, access=access)

    def recover_expired_workers(self) -> list[str]:
        now_epoch = time.time()
        now_iso = _utc_now_iso()
        cleanup: list[tuple[str, Path]] = []
        with self._connect(immediate=True) as conn:
            conn.execute(
                """
                UPDATE workload_provider_leases
                SET released_at = ?, release_code = 'provider_lease_expired'
                WHERE released_at IS NULL AND lease_expires_epoch <= ?
                """,
                (now_iso, now_epoch),
            )
            rows = conn.execute(
                """
                SELECT * FROM workload_jobs
                WHERE state IN (
                    'source_intake', 'normalizing', 'building_document_memory',
                    'validating', 'preparing_gate2', 'awaiting_provider'
                )
                  AND lease_token IS NOT NULL
                  AND lease_expires_epoch <= ?
                ORDER BY sequence
                """,
                (now_epoch,),
            ).fetchall()
            for row in rows:
                sequence = int(row["progress_sequence"]) + 1
                conn.execute(
                    """
                    UPDATE workload_jobs
                    SET state = 'failed', progress_sequence = ?,
                        terminal_code = 'worker_lease_expired', terminal_at = ?,
                        worker_id = NULL, lease_token = NULL,
                        lease_expires_epoch = NULL, provider_id = NULL,
                        provider_lease_token = NULL, cleanup_status = 'pending',
                        updated_at = ?
                    WHERE job_id = ?
                    """,
                    (sequence, now_iso, now_iso, row["job_id"]),
                )
                conn.execute(
                    "DELETE FROM workload_provider_waiters WHERE job_id = ?",
                    (row["job_id"],),
                )
                self._insert_transition(
                    conn,
                    job_id=str(row["job_id"]),
                    sequence=sequence,
                    from_state=WorkloadState(str(row["state"])),
                    to_state=WorkloadState.FAILED,
                    event_code="worker_lease_expired",
                    safe_detail={"false_completion_prevented": True},
                )
                cleanup.append((str(row["job_id"]), Path(str(row["temp_dir"]))))
        for job_id, temp_dir in cleanup:
            self._finalize_cleanup(job_id, temp_dir)
        return [job_id for job_id, _ in cleanup]

    def _transition(
        self,
        *,
        session: "WorkloadSession",
        state: WorkloadState | str,
        event_code: str,
        safe_detail: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        target = _workload_state(state)
        if target in {WorkloadState.QUEUED, *map(WorkloadState, _TERMINAL_STATES)}:
            raise WorkloadAuthorityError("workload_transition_target_invalid")
        event = _safe_code(event_code, "workload_event_code_invalid")
        detail = _safe_metadata(safe_detail)
        with self._connect(immediate=True) as conn:
            row = self._session_row(conn, session)
            self._raise_if_cancel_requested(conn, row)
            current = WorkloadState(str(row["state"]))
            if target == current:
                self._renew_lease(conn, row, session)
            elif target not in _ALLOWED_TRANSITIONS.get(current, frozenset()):
                raise WorkloadAuthorityError(
                    "workload_progress_transition_invalid",
                    f"Invalid workload state transition: {current.value}->{target.value}",
                )
            else:
                sequence = int(row["progress_sequence"]) + 1
                now_iso = _utc_now_iso()
                conn.execute(
                    """
                    UPDATE workload_jobs
                    SET state = ?, progress_sequence = ?, updated_at = ?,
                        lease_expires_epoch = ?
                    WHERE job_id = ?
                    """,
                    (
                        target.value,
                        sequence,
                        now_iso,
                        time.time() + self.config.lease_seconds,
                        session.job_id,
                    ),
                )
                self._insert_transition(
                    conn,
                    job_id=session.job_id,
                    sequence=sequence,
                    from_state=current,
                    to_state=target,
                    event_code=event,
                    safe_detail=detail,
                )
        return self.snapshot(job_id=session.job_id, access=session.access)

    def _checkpoint(self, session: "WorkloadSession") -> dict[str, Any]:
        with self._connect(immediate=True) as conn:
            row = self._session_row(conn, session)
            self._raise_if_cancel_requested(conn, row)
            self._renew_lease(conn, row, session)
        return self.snapshot(job_id=session.job_id, access=session.access)

    def _heartbeat(self, session: "WorkloadSession") -> None:
        with self._connect(immediate=True) as conn:
            row = self._session_row(conn, session)
            self._renew_lease(conn, row, session)

    def _terminal(
        self,
        *,
        session: "WorkloadSession",
        state: WorkloadState,
        terminal_code: str,
        safe_detail: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if state not in {
            WorkloadState.COMPLETED,
            WorkloadState.FAILED,
            WorkloadState.CANCELLED,
        }:
            raise WorkloadAuthorityError("workload_terminal_state_invalid")
        code = _safe_code(terminal_code, "workload_terminal_code_invalid")
        detail = _safe_metadata(safe_detail)
        with self._connect(immediate=True) as conn:
            row = self._session_row(conn, session, allow_expired=False)
            current = WorkloadState(str(row["state"]))
            if state is WorkloadState.COMPLETED and bool(row["cancel_requested"]):
                raise WorkloadCancelledError()
            sequence = int(row["progress_sequence"]) + 1
            now_iso = _utc_now_iso()
            conn.execute(
                """
                UPDATE workload_jobs
                SET state = ?, progress_sequence = ?, terminal_code = ?,
                    terminal_at = ?, updated_at = ?, worker_id = NULL,
                    lease_token = NULL, lease_expires_epoch = NULL,
                    provider_id = NULL, provider_lease_token = NULL,
                    cleanup_status = 'pending'
                WHERE job_id = ?
                """,
                (state.value, sequence, code, now_iso, now_iso, session.job_id),
            )
            conn.execute(
                "DELETE FROM workload_provider_waiters WHERE job_id = ?",
                (session.job_id,),
            )
            conn.execute(
                """
                UPDATE workload_provider_leases
                SET released_at = COALESCE(released_at, ?),
                    release_code = COALESCE(release_code, 'job_terminal')
                WHERE job_id = ? AND released_at IS NULL
                """,
                (now_iso, session.job_id),
            )
            self._insert_transition(
                conn,
                job_id=session.job_id,
                sequence=sequence,
                from_state=current,
                to_state=state,
                event_code=code,
                safe_detail=detail,
            )
        session._terminal = True
        self._finalize_cleanup(session.job_id, session.temp_dir)
        return self.snapshot(job_id=session.job_id, access=session.access)

    def _await_review(
        self,
        *,
        session: "WorkloadSession",
        reason_code: str,
        safe_detail: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        code = _safe_code(reason_code, "workload_review_reason_invalid")
        detail = _safe_metadata(safe_detail)
        with self._connect(immediate=True) as conn:
            row = self._session_row(conn, session)
            self._raise_if_cancel_requested(conn, row)
            current = WorkloadState(str(row["state"]))
            if WorkloadState.AWAITING_REVIEW not in _ALLOWED_TRANSITIONS.get(
                current, frozenset()
            ):
                raise WorkloadAuthorityError("workload_review_transition_invalid")
            sequence = int(row["progress_sequence"]) + 1
            now_iso = _utc_now_iso()
            conn.execute(
                """
                UPDATE workload_jobs
                SET state = 'awaiting_review', progress_sequence = ?,
                    worker_id = NULL, lease_token = NULL,
                    lease_expires_epoch = NULL, provider_id = NULL,
                    provider_lease_token = NULL, updated_at = ?
                WHERE job_id = ?
                """,
                (sequence, now_iso, session.job_id),
            )
            self._insert_transition(
                conn,
                job_id=session.job_id,
                sequence=sequence,
                from_state=current,
                to_state=WorkloadState.AWAITING_REVIEW,
                event_code=code,
                safe_detail=detail,
            )
        session._terminal = True
        self._finalize_cleanup(session.job_id, session.temp_dir)
        return self.snapshot(job_id=session.job_id, access=session.access)

    def _begin_provider_wait(
        self,
        *,
        session: "WorkloadSession",
        provider_id: str,
    ) -> None:
        provider = _safe_code(provider_id, "workload_provider_id_invalid")
        if provider not in self.config.provider_budgets:
            raise WorkloadAuthorityError("workload_provider_budget_missing")
        with self._connect(immediate=True) as conn:
            row = self._session_row(conn, session)
            self._raise_if_cancel_requested(conn, row)
            current = WorkloadState(str(row["state"]))
            if current is not WorkloadState.AWAITING_PROVIDER:
                if WorkloadState.AWAITING_PROVIDER not in _ALLOWED_TRANSITIONS.get(
                    current, frozenset()
                ):
                    raise WorkloadAuthorityError(
                        "workload_provider_transition_invalid"
                    )
                sequence = int(row["progress_sequence"]) + 1
                now_iso = _utc_now_iso()
                conn.execute(
                    """
                    UPDATE workload_jobs
                    SET state = 'awaiting_provider', progress_sequence = ?,
                        provider_id = ?, updated_at = ?, lease_expires_epoch = ?
                    WHERE job_id = ?
                    """,
                    (
                        sequence,
                        provider,
                        now_iso,
                        time.time() + self.config.lease_seconds,
                        session.job_id,
                    ),
                )
                self._insert_transition(
                    conn,
                    job_id=session.job_id,
                    sequence=sequence,
                    from_state=current,
                    to_state=WorkloadState.AWAITING_PROVIDER,
                    event_code="provider_wait_started",
                    safe_detail={"provider_id": provider},
                )
            elif row["provider_id"] != provider:
                raise WorkloadAuthorityError("workload_provider_wait_already_active")
            conn.execute(
                """
                INSERT OR IGNORE INTO workload_provider_waiters(
                    job_id, provider_id, requested_at
                ) VALUES (?, ?, ?)
                """,
                (session.job_id, provider, _utc_now_iso()),
            )

    def _try_acquire_provider(
        self,
        *,
        session: "WorkloadSession",
        provider_id: str,
    ) -> str | None:
        provider = _safe_code(provider_id, "workload_provider_id_invalid")
        now_epoch = time.time()
        now_iso = _utc_now_iso()
        token = "brproviderlease_" + secrets.token_hex(24)
        with self._connect(immediate=True) as conn:
            row = self._session_row(conn, session)
            self._raise_if_cancel_requested(conn, row)
            if row["state"] != WorkloadState.AWAITING_PROVIDER.value:
                raise WorkloadAuthorityError("workload_provider_wait_not_active")
            conn.execute(
                """
                UPDATE workload_provider_leases
                SET released_at = ?, release_code = 'provider_lease_expired'
                WHERE released_at IS NULL AND lease_expires_epoch <= ?
                """,
                (now_iso, now_epoch),
            )
            existing = conn.execute(
                """
                SELECT lease_token FROM workload_provider_leases
                WHERE job_id = ? AND released_at IS NULL
                """,
                (session.job_id,),
            ).fetchone()
            if existing is not None:
                return str(existing["lease_token"])
            waiter = conn.execute(
                """
                SELECT job_id FROM workload_provider_waiters
                WHERE provider_id = ? ORDER BY sequence LIMIT 1
                """,
                (provider,),
            ).fetchone()
            if waiter is None or waiter["job_id"] != session.job_id:
                self._renew_lease(conn, row, session)
                return None
            active = int(
                conn.execute(
                    """
                    SELECT COUNT(*) FROM workload_provider_leases
                    WHERE provider_id = ? AND released_at IS NULL
                      AND lease_expires_epoch > ?
                    """,
                    (provider, now_epoch),
                ).fetchone()[0]
            )
            if active >= int(self.config.provider_budgets[provider]):
                self._renew_lease(conn, row, session)
                return None
            conn.execute(
                """
                INSERT INTO workload_provider_leases(
                    lease_token, provider_id, job_id, worker_id,
                    acquired_at, lease_expires_epoch
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    token,
                    provider,
                    session.job_id,
                    session.worker_id,
                    now_iso,
                    now_epoch + self.config.lease_seconds,
                ),
            )
            conn.execute(
                "DELETE FROM workload_provider_waiters WHERE job_id = ?",
                (session.job_id,),
            )
            conn.execute(
                """
                UPDATE workload_jobs
                SET provider_lease_token = ?, lease_expires_epoch = ?, updated_at = ?
                WHERE job_id = ?
                """,
                (
                    token,
                    now_epoch + self.config.lease_seconds,
                    now_iso,
                    session.job_id,
                ),
            )
            return token

    def _release_provider(
        self,
        *,
        session: "WorkloadSession",
        provider_token: str,
        resume_state: WorkloadState | str,
        release_code: str,
    ) -> None:
        resume = _workload_state(resume_state)
        code = _safe_code(release_code, "workload_provider_release_code_invalid")
        with self._connect(immediate=True) as conn:
            row = self._session_row(conn, session)
            if row["provider_lease_token"] != provider_token:
                raise WorkloadAuthorityError("workload_provider_lease_lost")
            current = WorkloadState(str(row["state"]))
            if current is not WorkloadState.AWAITING_PROVIDER:
                raise WorkloadAuthorityError("workload_provider_state_invalid")
            if resume not in _ALLOWED_TRANSITIONS[current]:
                raise WorkloadAuthorityError("workload_provider_resume_state_invalid")
            now_iso = _utc_now_iso()
            conn.execute(
                """
                UPDATE workload_provider_leases
                SET released_at = ?, release_code = ?
                WHERE lease_token = ? AND released_at IS NULL
                """,
                (now_iso, code, provider_token),
            )
            sequence = int(row["progress_sequence"]) + 1
            conn.execute(
                """
                UPDATE workload_jobs
                SET state = ?, progress_sequence = ?, provider_id = NULL,
                    provider_lease_token = NULL, lease_expires_epoch = ?,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (
                    resume.value,
                    sequence,
                    time.time() + self.config.lease_seconds,
                    now_iso,
                    session.job_id,
                ),
            )
            self._insert_transition(
                conn,
                job_id=session.job_id,
                sequence=sequence,
                from_state=current,
                to_state=resume,
                event_code=code,
                safe_detail={},
            )

    def _cancel_session(self, session: "WorkloadSession", reason_code: str) -> None:
        if session._terminal:
            return
        try:
            self._terminal(
                session=session,
                state=WorkloadState.CANCELLED,
                terminal_code=reason_code,
                safe_detail={"partial_success_published": False},
            )
        except WorkloadAuthorityError as exc:
            if exc.code not in {
                "workload_job_terminal",
                "workload_worker_lease_lost",
                "workload_worker_lease_expired",
            }:
                raise

    def _raise_if_cancel_requested(
        self, conn: sqlite3.Connection, row: sqlite3.Row
    ) -> None:
        if not bool(row["cancel_requested"]):
            return
        raise WorkloadCancelledError()

    def _session_row(
        self,
        conn: sqlite3.Connection,
        session: "WorkloadSession",
        *,
        allow_expired: bool = False,
    ) -> sqlite3.Row:
        row = self._authorized_row(conn, session.job_id, session.access)
        if row["state"] in _TERMINAL_STATES:
            raise WorkloadAuthorityError("workload_job_terminal")
        if (
            row["worker_id"] != session.worker_id
            or row["lease_token"] != session.lease_token
        ):
            raise WorkloadAuthorityError("workload_worker_lease_lost")
        if not allow_expired and float(row["lease_expires_epoch"] or 0) <= time.time():
            raise WorkloadAuthorityError("workload_worker_lease_expired")
        return row

    def _renew_lease(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        session: "WorkloadSession",
    ) -> None:
        expires = time.time() + self.config.lease_seconds
        now_iso = _utc_now_iso()
        conn.execute(
            """
            UPDATE workload_jobs
            SET lease_expires_epoch = ?, updated_at = ?
            WHERE job_id = ? AND lease_token = ?
            """,
            (expires, now_iso, session.job_id, session.lease_token),
        )
        if row["provider_lease_token"]:
            conn.execute(
                """
                UPDATE workload_provider_leases
                SET lease_expires_epoch = ?
                WHERE lease_token = ? AND released_at IS NULL
                """,
                (expires, row["provider_lease_token"]),
            )

    def _validate_retry_source(
        self,
        job_id: str,
        access: WorkloadAccessContext,
        kind: WorkloadKind,
    ) -> None:
        with self._connect() as conn:
            row = self._authorized_row(conn, job_id, access)
            if row["state"] not in {
                WorkloadState.FAILED.value,
                WorkloadState.CANCELLED.value,
            }:
                raise WorkloadAuthorityError("workload_retry_source_not_retryable")
            if row["job_kind"] != kind.value:
                raise WorkloadAuthorityError("workload_retry_kind_mismatch")

    def _cancel_without_worker(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        reason_code: str,
    ) -> None:
        if row["state"] in _TERMINAL_STATES:
            return
        sequence = int(row["progress_sequence"]) + 1
        now_iso = _utc_now_iso()
        conn.execute(
            """
            UPDATE workload_jobs
            SET state = 'cancelled', progress_sequence = ?,
                cancel_requested = 1, cancel_reason_code = ?,
                terminal_code = ?, terminal_at = ?, updated_at = ?,
                worker_id = NULL, lease_token = NULL,
                lease_expires_epoch = NULL, provider_id = NULL,
                provider_lease_token = NULL, cleanup_status = 'pending'
            WHERE job_id = ?
            """,
            (
                sequence,
                reason_code,
                reason_code,
                now_iso,
                now_iso,
                row["job_id"],
            ),
        )
        conn.execute(
            "DELETE FROM workload_provider_waiters WHERE job_id = ?",
            (row["job_id"],),
        )
        conn.execute(
            """
            UPDATE workload_provider_leases
            SET released_at = COALESCE(released_at, ?),
                release_code = COALESCE(release_code, 'job_cancelled')
            WHERE job_id = ? AND released_at IS NULL
            """,
            (now_iso, row["job_id"]),
        )
        self._insert_transition(
            conn,
            job_id=str(row["job_id"]),
            sequence=sequence,
            from_state=WorkloadState(str(row["state"])),
            to_state=WorkloadState.CANCELLED,
            event_code=reason_code,
            safe_detail={"partial_success_published": False},
        )

    def _authorized_row(
        self,
        conn: sqlite3.Connection,
        job_id: str,
        access: WorkloadAccessContext,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM workload_jobs WHERE job_id = ?",
            (str(job_id),),
        ).fetchone()
        if row is None:
            raise WorkloadAuthorityError("workload_job_not_found")
        expected = (
            str(row["user_id"]),
            _optional_text(row["case_id"]),
            _optional_text(row["chat_id"]),
            _optional_text(row["workspace_model_id"]),
        )
        observed = (
            access.user_id,
            access.case_id,
            access.chat_id,
            access.workspace_model_id,
        )
        if expected != observed:
            raise WorkloadAuthorityError("workload_access_denied")
        return row

    def _is_queue_head(self, conn: sqlite3.Connection, row: sqlite3.Row) -> bool:
        head = conn.execute(
            """
            SELECT job_id FROM workload_jobs
            WHERE resource_class = ? AND state = 'queued'
              AND cancel_requested = 0
            ORDER BY sequence LIMIT 1
            """,
            (row["resource_class"],),
        ).fetchone()
        return head is not None and head["job_id"] == row["job_id"]

    def _active_count(
        self, conn: sqlite3.Connection, resource_class: str, now_epoch: float
    ) -> int:
        placeholders = ",".join("?" for _ in _ACTIVE_LOCAL_STATES)
        return int(
            conn.execute(
                f"""
                SELECT COUNT(*) FROM workload_jobs
                WHERE resource_class = ? AND state IN ({placeholders})
                  AND lease_token IS NOT NULL AND lease_expires_epoch > ?
                """,
                (resource_class, *sorted(_ACTIVE_LOCAL_STATES), now_epoch),
            ).fetchone()[0]
        )

    def _capacity(self, resource_class: str) -> int:
        capacities = {
            WorkloadResourceClass.SOURCE_INTAKE.value: (
                self.config.source_intake_concurrency
            ),
            WorkloadResourceClass.GATE1_HEAVY.value: self.config.gate1_concurrency,
            WorkloadResourceClass.GATE2_LOCAL.value: self.config.gate2_concurrency,
            WorkloadResourceClass.REVIEW_WAITING.value: 2_147_483_647,
            WorkloadResourceClass.LIGHTWEIGHT_DETERMINISTIC.value: (
                self.config.lightweight_concurrency
            ),
        }
        return capacities[resource_class]

    def _insert_transition(
        self,
        conn: sqlite3.Connection,
        *,
        job_id: str,
        sequence: int,
        from_state: WorkloadState | None,
        to_state: WorkloadState,
        event_code: str,
        safe_detail: Mapping[str, Any] | None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO workload_transitions(
                job_id, sequence, from_state, to_state, event_code,
                safe_detail_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                sequence,
                from_state.value if from_state is not None else None,
                to_state.value,
                event_code,
                _canonical_json(_safe_metadata(safe_detail)),
                _utc_now_iso(),
            ),
        )

    def _create_private_temp_dir(self, temp_dir: Path) -> None:
        self.config.temp_root.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
        try:
            temp_dir.chmod(0o700)
        except OSError:
            pass

    def _remove_owned_temp_dir(self, temp_dir: Path) -> None:
        root = self.config.temp_root.resolve()
        candidate = temp_dir.resolve()
        if candidate.parent != root or not candidate.name.startswith("brjob_"):
            raise WorkloadAuthorityError("workload_temp_scope_invalid")
        if candidate.exists():
            shutil.rmtree(candidate)

    def _finalize_cleanup(self, job_id: str, temp_dir: Path) -> None:
        status = "cleaned"
        code = None
        try:
            self._remove_owned_temp_dir(temp_dir)
        except Exception as exc:
            status = "cleanup_failed"
            code = _safe_exception_code(exc)
        with self._connect(immediate=True) as conn:
            conn.execute(
                """
                UPDATE workload_jobs
                SET cleanup_status = ?, cleanup_at = ?, cleanup_error_code = ?,
                    updated_at = ?
                WHERE job_id = ?
                """,
                (status, _utc_now_iso(), code, _utc_now_iso(), job_id),
            )

    def _retry_pending_cleanup(self) -> None:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id, temp_dir FROM workload_jobs
                WHERE state IN ('completed', 'failed', 'cancelled')
                  AND cleanup_status IN ('pending', 'cleanup_failed')
                ORDER BY sequence
                """
            ).fetchall()
        for row in rows:
            self._finalize_cleanup(str(row["job_id"]), Path(str(row["temp_dir"])))

    @contextmanager
    def _connect(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.config.sqlite_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 30000")
        try:
            if immediate:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema_and_contract(self) -> None:
        self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.temp_root.mkdir(parents=True, exist_ok=True)
        contract = self.config.safe_contract()
        contract_json = _canonical_json(contract)
        contract_hash = hashlib.sha256(contract_json.encode("utf-8")).hexdigest()
        journal_conn = sqlite3.connect(self.config.sqlite_path, timeout=30.0)
        try:
            journal_conn.execute("PRAGMA journal_mode = WAL")
        finally:
            journal_conn.close()
        with self._connect(immediate=True) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS workload_authority_contract(
                    authority_id TEXT PRIMARY KEY,
                    contract_version TEXT NOT NULL,
                    contract_hash TEXT NOT NULL,
                    contract_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workload_jobs(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL UNIQUE,
                    job_kind TEXT NOT NULL,
                    resource_class TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    case_id TEXT NULL,
                    chat_id TEXT NULL,
                    workspace_model_id TEXT NULL,
                    state TEXT NOT NULL,
                    progress_sequence INTEGER NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    cancel_reason_code TEXT NULL,
                    worker_id TEXT NULL,
                    lease_token TEXT NULL,
                    lease_expires_epoch REAL NULL,
                    provider_id TEXT NULL,
                    provider_lease_token TEXT NULL,
                    retry_of_job_id TEXT NULL,
                    safe_metadata_json TEXT NOT NULL,
                    temp_dir TEXT NOT NULL,
                    cleanup_status TEXT NOT NULL,
                    cleanup_at TEXT NULL,
                    cleanup_error_code TEXT NULL,
                    terminal_code TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    admitted_at TEXT NULL,
                    terminal_at TEXT NULL,
                    FOREIGN KEY(retry_of_job_id) REFERENCES workload_jobs(job_id)
                );

                CREATE INDEX IF NOT EXISTS workload_jobs_queue_idx
                    ON workload_jobs(resource_class, state, sequence);
                CREATE INDEX IF NOT EXISTS workload_jobs_lease_idx
                    ON workload_jobs(state, lease_expires_epoch);

                CREATE TABLE IF NOT EXISTS workload_transitions(
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    from_state TEXT NULL,
                    to_state TEXT NOT NULL,
                    event_code TEXT NOT NULL,
                    safe_detail_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES workload_jobs(job_id)
                );

                CREATE INDEX IF NOT EXISTS workload_transitions_job_idx
                    ON workload_transitions(job_id, event_id);

                CREATE TABLE IF NOT EXISTS workload_provider_waiters(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL UNIQUE,
                    provider_id TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES workload_jobs(job_id)
                );

                CREATE INDEX IF NOT EXISTS workload_provider_waiters_queue_idx
                    ON workload_provider_waiters(provider_id, sequence);

                CREATE TABLE IF NOT EXISTS workload_provider_leases(
                    lease_token TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    acquired_at TEXT NOT NULL,
                    lease_expires_epoch REAL NOT NULL,
                    released_at TEXT NULL,
                    release_code TEXT NULL,
                    FOREIGN KEY(job_id) REFERENCES workload_jobs(job_id)
                );

                CREATE INDEX IF NOT EXISTS workload_provider_leases_active_idx
                    ON workload_provider_leases(
                        provider_id, released_at, lease_expires_epoch
                    );
                """
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO workload_authority_contract(
                    authority_id, contract_version, contract_hash,
                    contract_json, created_at
                ) VALUES ('broker_reports', ?, ?, ?, ?)
                """,
                (
                    WORKLOAD_AUTHORITY_CONTRACT_VERSION,
                    contract_hash,
                    contract_json,
                    _utc_now_iso(),
                ),
            )
            row = conn.execute(
                """
                SELECT contract_hash FROM workload_authority_contract
                WHERE authority_id = 'broker_reports'
                """
            ).fetchone()
            if row is None or row["contract_hash"] != contract_hash:
                raise WorkloadAuthorityError(
                    "workload_authority_contract_mismatch",
                    "The shared workload database is already bound to another capacity contract",
                )


class WorkloadSession:
    def __init__(
        self,
        *,
        authority: WorkloadAuthority,
        job_id: str,
        access: WorkloadAccessContext,
        worker_id: str,
        lease_token: str,
        temp_dir: Path,
    ) -> None:
        self.authority = authority
        self.job_id = job_id
        self.access = access
        self.worker_id = worker_id
        self.lease_token = lease_token
        self.temp_dir = temp_dir
        self._terminal = False
        self._heartbeat_error: BaseException | None = None

    @property
    def terminal(self) -> bool:
        return self._terminal

    def snapshot(self) -> dict[str, Any]:
        return self.authority.snapshot(job_id=self.job_id, access=self.access)

    def transition(
        self,
        state: WorkloadState | str,
        *,
        event_code: str = "progress",
        safe_detail: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._raise_heartbeat_error()
        try:
            return self.authority._transition(
                session=self,
                state=state,
                event_code=event_code,
                safe_detail=safe_detail,
            )
        except WorkloadCancelledError:
            self.cancel("cooperative_checkpoint_cancelled")
            raise

    def checkpoint(self) -> dict[str, Any]:
        self._raise_heartbeat_error()
        try:
            return self.authority._checkpoint(self)
        except WorkloadCancelledError:
            self.cancel("cooperative_checkpoint_cancelled")
            raise

    def complete(
        self,
        *,
        terminal_code: str = "completed",
        safe_detail: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._raise_heartbeat_error()
        try:
            self.checkpoint()
            return self.authority._terminal(
                session=self,
                state=WorkloadState.COMPLETED,
                terminal_code=terminal_code,
                safe_detail=safe_detail,
            )
        except WorkloadCancelledError:
            self.cancel("cancelled_before_completion")
            raise

    def fail(
        self,
        terminal_code: str = "operation_failed",
        *,
        safe_detail: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if self._terminal:
            return None
        return self.authority._terminal(
            session=self,
            state=WorkloadState.FAILED,
            terminal_code=_safe_code(terminal_code, "workload_failure_code_invalid"),
            safe_detail=safe_detail,
        )

    def cancel(
        self,
        reason_code: str = "cooperative_cancelled",
    ) -> dict[str, Any] | None:
        if self._terminal:
            return None
        result = self.authority._terminal(
            session=self,
            state=WorkloadState.CANCELLED,
            terminal_code=_safe_code(reason_code, "workload_cancel_reason_invalid"),
            safe_detail={"partial_success_published": False},
        )
        return result

    def await_review(
        self,
        *,
        reason_code: str = "explicit_review_required",
        safe_detail: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._raise_heartbeat_error()
        return self.authority._await_review(
            session=self,
            reason_code=reason_code,
            safe_detail=safe_detail,
        )

    @contextmanager
    def provider_slot(
        self,
        provider_id: str,
        *,
        resume_state: WorkloadState | str = WorkloadState.VALIDATING,
    ) -> Iterator[None]:
        token = self._wait_for_provider_sync(provider_id)
        release_code = "provider_call_completed"
        try:
            yield
        except BaseException:
            release_code = "provider_call_terminated"
            raise
        finally:
            self.authority._release_provider(
                session=self,
                provider_token=token,
                resume_state=resume_state,
                release_code=release_code,
            )
            self.checkpoint()

    @asynccontextmanager
    async def provider_slot_async(
        self,
        provider_id: str,
        *,
        resume_state: WorkloadState | str = WorkloadState.VALIDATING,
    ) -> AsyncIterator[None]:
        token = await self._wait_for_provider_async(provider_id)
        release_code = "provider_call_completed"
        try:
            yield
        except BaseException:
            release_code = "provider_call_terminated"
            raise
        finally:
            self.authority._release_provider(
                session=self,
                provider_token=token,
                resume_state=resume_state,
                release_code=release_code,
            )
            self.checkpoint()

    @contextmanager
    def keepalive(self) -> Iterator["WorkloadSession"]:
        stop = threading.Event()

        def heartbeat_loop() -> None:
            interval = float(self.authority.config.heartbeat_interval_seconds or 1.0)
            while not stop.wait(interval):
                try:
                    self.authority._heartbeat(self)
                except BaseException as exc:
                    self._heartbeat_error = exc
                    return

        thread = threading.Thread(
            target=heartbeat_loop,
            name=f"broker-reports-workload-heartbeat-{self.job_id[-8:]}",
            daemon=True,
        )
        thread.start()
        try:
            yield self
            self._raise_heartbeat_error()
        finally:
            stop.set()
            thread.join(timeout=max(0.1, float(self.authority.config.heartbeat_interval_seconds or 1.0) * 2))

    @asynccontextmanager
    async def cancellation_scope(self) -> AsyncIterator["WorkloadSession"]:
        owner = asyncio.current_task()
        if owner is None:
            raise WorkloadAuthorityError("workload_async_task_required")
        monitor_cancelled_owner = False

        async def monitor() -> None:
            nonlocal monitor_cancelled_owner
            while True:
                await asyncio.sleep(self.authority.config.poll_interval_seconds)
                snapshot = self.snapshot()
                if snapshot["cancel_requested"]:
                    monitor_cancelled_owner = True
                    owner.cancel()
                    return

        task = asyncio.create_task(monitor())
        try:
            yield self
        except asyncio.CancelledError:
            if monitor_cancelled_owner or self.snapshot()["cancel_requested"]:
                self.cancel("cooperative_async_cancelled")
                raise WorkloadCancelledError() from None
            self.cancel("caller_task_cancelled")
            raise
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _wait_for_provider_async(self, provider_id: str) -> str:
        try:
            self.authority._begin_provider_wait(session=self, provider_id=provider_id)
            while True:
                token = self.authority._try_acquire_provider(
                    session=self,
                    provider_id=provider_id,
                )
                if token is not None:
                    return token
                self.checkpoint()
                await asyncio.sleep(self.authority.config.poll_interval_seconds)
        except WorkloadCancelledError:
            self.cancel("provider_wait_cancelled")
            raise

    def _wait_for_provider_sync(self, provider_id: str) -> str:
        try:
            self.authority._begin_provider_wait(session=self, provider_id=provider_id)
            while True:
                token = self.authority._try_acquire_provider(
                    session=self,
                    provider_id=provider_id,
                )
                if token is not None:
                    return token
                self.checkpoint()
                time.sleep(self.authority.config.poll_interval_seconds)
        except WorkloadCancelledError:
            self.cancel("provider_wait_cancelled")
            raise

    def _raise_heartbeat_error(self) -> None:
        if self._terminal:
            return
        if self._heartbeat_error is not None:
            raise WorkloadAuthorityError(
                "workload_heartbeat_failed",
                self._heartbeat_error.__class__.__name__,
            ) from self._heartbeat_error


def provider_budgets_from_json(value: str | None) -> dict[str, int]:
    if not str(value or "").strip():
        return dict(DEFAULT_PROVIDER_BUDGETS)
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError) as exc:
        raise WorkloadAuthorityError("workload_provider_budget_json_invalid") from exc
    if not isinstance(parsed, dict):
        raise WorkloadAuthorityError("workload_provider_budget_json_invalid")
    try:
        return {str(key): int(number) for key, number in parsed.items()}
    except (TypeError, ValueError) as exc:
        raise WorkloadAuthorityError("workload_provider_budget_json_invalid") from exc


def _workload_kind(value: WorkloadKind | str) -> WorkloadKind:
    try:
        return value if isinstance(value, WorkloadKind) else WorkloadKind(str(value))
    except ValueError as exc:
        raise WorkloadAuthorityError("workload_kind_invalid") from exc


def _workload_state(value: WorkloadState | str) -> WorkloadState:
    try:
        return value if isinstance(value, WorkloadState) else WorkloadState(str(value))
    except ValueError as exc:
        raise WorkloadAuthorityError("workload_state_invalid") from exc


def _safe_code(value: str, error_code: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SAFE_CODE_RE.fullmatch(normalized):
        raise WorkloadAuthorityError(error_code)
    return normalized


def _safe_identifier(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > 160:
        raise WorkloadAuthorityError("workload_worker_id_invalid")
    return normalized


def _safe_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    result = dict(value or {})
    encoded = _canonical_json(result)
    if len(encoded.encode("utf-8")) > 8192:
        raise WorkloadAuthorityError("workload_safe_metadata_too_large")
    return json.loads(encoded)


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise WorkloadAuthorityError("workload_safe_metadata_invalid") from exc


def _safe_exception_code(exc: BaseException) -> str:
    name = re.sub(r"[^a-z0-9]+", "_", exc.__class__.__name__.lower()).strip("_")
    return f"cleanup_{name or 'error'}"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
