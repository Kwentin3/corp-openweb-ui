from __future__ import annotations

import asyncio
import inspect
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Generic, TypeVar


WORKLOAD_ADMISSION_POLICY_VERSION = "broker_reports_workload_admission_v1"
WORKLOAD_ADMISSION_IMPLEMENTATION_STATUS = "implementation_pending"
WORKLOAD_ADMISSION_COORDINATION_SCOPE = "single_scheduler_instance_scaffold"
VISUAL_EXTERNAL_POLICY_ID = "visual_external_provider_serial_v1"
LIGHTWEIGHT_DETERMINISTIC_POLICY_ID = "lightweight_deterministic_bounded_v1"

FACTORY_REQUIRED = (
    "WorkloadAdmissionSchedulerFactory.create is the only construction entrypoint "
    "for the Broker Reports single-scheduler-instance scaffold"
)
FORBIDDEN = (
    "Callers must not create private semaphores, bypass FIFO admission, drop queued "
    "work, allocate temporary private artifacts before RUNNING, treat a cancellation "
    "request as terminal before work cooperates, or represent this scaffold as "
    "process-wide or multi-worker admission"
)

_FACTORY_TOKEN = object()
_T = TypeVar("_T")


class WorkloadClass(str, Enum):
    GATE1 = "gate1"
    GATE2 = "gate2"
    VISUAL_EXTERNAL = "visual_external"
    LIGHTWEIGHT_DETERMINISTIC = "lightweight_deterministic"


class WorkloadState(str, Enum):
    QUEUED = "queued"
    ADMITTED = "admitted"
    RUNNING = "running"
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


class CapacityBasis(str, Enum):
    MEASURED_ENVELOPE = "measured_envelope"
    EXPLICIT_POLICY = "explicit_policy"


class CancellationDisposition(str, Enum):
    CANCELLED_BEFORE_RUN = "cancelled_before_run"
    CANCELLATION_REQUESTED = "cancellation_requested"
    ALREADY_TERMINAL = "already_terminal"


class WorkloadCleanupPolicy(str, Enum):
    NO_PRIVATE_ARTIFACTS = "no_private_artifacts"
    CLEANUP_CALLBACK_REQUIRED = "cleanup_callback_required"


TERMINAL_WORKLOAD_STATES = frozenset(
    {
        WorkloadState.COMPLETED,
        WorkloadState.FAILED,
        WorkloadState.CANCELLED,
    }
)
_ACTIVE_WORKLOAD_STATES = frozenset(
    {
        WorkloadState.RUNNING,
        WorkloadState.SOURCE_INTAKE,
        WorkloadState.NORMALIZING,
        WorkloadState.BUILDING_DOCUMENT_MEMORY,
        WorkloadState.VALIDATING,
        WorkloadState.PREPARING_GATE2,
        WorkloadState.AWAITING_PROVIDER,
        WorkloadState.AWAITING_REVIEW,
    }
)
_PROGRESS_ORDER = {
    WorkloadClass.GATE1: (
        WorkloadState.SOURCE_INTAKE,
        WorkloadState.NORMALIZING,
        WorkloadState.BUILDING_DOCUMENT_MEMORY,
        WorkloadState.VALIDATING,
    ),
    WorkloadClass.GATE2: (
        WorkloadState.PREPARING_GATE2,
        WorkloadState.AWAITING_PROVIDER,
        WorkloadState.VALIDATING,
        WorkloadState.AWAITING_REVIEW,
    ),
    WorkloadClass.VISUAL_EXTERNAL: (
        WorkloadState.AWAITING_PROVIDER,
        WorkloadState.VALIDATING,
        WorkloadState.AWAITING_REVIEW,
    ),
    WorkloadClass.LIGHTWEIGHT_DETERMINISTIC: (WorkloadState.VALIDATING,),
}


class WorkloadAdmissionError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class WorkloadCancellationCheckpoint(RuntimeError):
    """Private control-flow signal raised only at a cooperative checkpoint."""


@dataclass(frozen=True)
class WorkloadAdmissionConfig:
    gate1_max_concurrency: int = 1
    gate2_max_concurrency: int = 2
    visual_external_max_concurrency: int = 1
    visual_external_policy_id: str = VISUAL_EXTERNAL_POLICY_ID
    lightweight_deterministic_max_concurrency: int = 8
    lightweight_deterministic_policy_id: str = LIGHTWEIGHT_DETERMINISTIC_POLICY_ID

    def limit_for(self, workload_class: WorkloadClass) -> int:
        if workload_class is WorkloadClass.GATE1:
            return self.gate1_max_concurrency
        if workload_class is WorkloadClass.GATE2:
            return self.gate2_max_concurrency
        if workload_class is WorkloadClass.VISUAL_EXTERNAL:
            return self.visual_external_max_concurrency
        if workload_class is WorkloadClass.LIGHTWEIGHT_DETERMINISTIC:
            return self.lightweight_deterministic_max_concurrency
        raise WorkloadAdmissionError("workload_class_unsupported")


@dataclass(frozen=True)
class WorkloadCapacity:
    workload_class: WorkloadClass
    max_concurrency: int
    basis: CapacityBasis
    policy_id: str


@dataclass(frozen=True)
class WorkloadTransition:
    sequence: int
    state: WorkloadState


@dataclass(frozen=True)
class WorkloadTicket:
    job_id: str
    workload_class: WorkloadClass
    cleanup_policy: WorkloadCleanupPolicy
    _scheduler_id: str = field(repr=False, compare=False)


@dataclass(frozen=True)
class WorkloadSnapshot:
    job_id: str
    workload_class: WorkloadClass
    state: WorkloadState
    queue_position: int | None
    cancellation_requested: bool
    cleanup_policy: WorkloadCleanupPolicy
    transitions: tuple[WorkloadTransition, ...]
    error_code: str | None
    error_type: str | None


@dataclass(frozen=True)
class WorkloadExecutionResult(Generic[_T]):
    snapshot: WorkloadSnapshot
    value: _T | None


@dataclass
class _JobRecord:
    ticket: WorkloadTicket
    state: WorkloadState = WorkloadState.QUEUED
    transitions: list[WorkloadTransition] = field(
        default_factory=lambda: [
            WorkloadTransition(sequence=1, state=WorkloadState.QUEUED)
        ]
    )
    ready: asyncio.Event = field(default_factory=asyncio.Event)
    terminal: asyncio.Event = field(default_factory=asyncio.Event)
    cancellation_requested: asyncio.Event = field(default_factory=asyncio.Event)
    error_code: str | None = None
    error_type: str | None = None
    progress_rank: int = -1


class WorkloadExecutionContext:
    __slots__ = ("_record", "_scheduler")

    def __init__(
        self,
        record: _JobRecord,
        scheduler: "WorkloadAdmissionScheduler",
    ) -> None:
        self._record = record
        self._scheduler = scheduler

    @property
    def job_id(self) -> str:
        return self._record.ticket.job_id

    @property
    def workload_class(self) -> WorkloadClass:
        return self._record.ticket.workload_class

    @property
    def cancellation_requested(self) -> bool:
        return self._record.cancellation_requested.is_set()

    def checkpoint(self) -> None:
        if self.cancellation_requested:
            raise WorkloadCancellationCheckpoint(
                "workload_cancellation_checkpoint_reached"
            )

    async def advance(self, state: WorkloadState) -> WorkloadSnapshot:
        self.checkpoint()
        snapshot = await self._scheduler._advance_progress(self._record, state)
        self.checkpoint()
        return snapshot


WorkloadOperation = Callable[[WorkloadExecutionContext], Awaitable[_T]]
WorkloadCancellationCleanup = Callable[
    [WorkloadExecutionContext],
    Awaitable[None],
]


class WorkloadAdmissionSchedulerFactory:
    def __init__(self, config: WorkloadAdmissionConfig | None = None) -> None:
        self._config = config or WorkloadAdmissionConfig()

    def create(self) -> "WorkloadAdmissionScheduler":
        _validate_config(self._config)
        return WorkloadAdmissionScheduler(
            config=self._config,
            _factory_token=_FACTORY_TOKEN,
        )


class WorkloadAdmissionScheduler:
    def __init__(
        self,
        *,
        config: WorkloadAdmissionConfig,
        _factory_token: object,
    ) -> None:
        if _factory_token is not _FACTORY_TOKEN:
            raise WorkloadAdmissionError("workload_admission_factory_required")
        self._config = config
        self._scheduler_id = uuid.uuid4().hex
        self._lock = asyncio.Lock()
        self._records: dict[str, _JobRecord] = {}
        self._queues = {workload_class: deque() for workload_class in WorkloadClass}
        self._active = {workload_class: 0 for workload_class in WorkloadClass}

    @property
    def policy_version(self) -> str:
        return WORKLOAD_ADMISSION_POLICY_VERSION

    @property
    def implementation_status(self) -> str:
        return WORKLOAD_ADMISSION_IMPLEMENTATION_STATUS

    @property
    def coordination_scope(self) -> str:
        return WORKLOAD_ADMISSION_COORDINATION_SCOPE

    def capacity_profile(self) -> tuple[WorkloadCapacity, ...]:
        return (
            WorkloadCapacity(
                workload_class=WorkloadClass.GATE1,
                max_concurrency=self._config.gate1_max_concurrency,
                basis=CapacityBasis.MEASURED_ENVELOPE,
                policy_id="broker_reports_gate1_measured_envelope_v1",
            ),
            WorkloadCapacity(
                workload_class=WorkloadClass.GATE2,
                max_concurrency=self._config.gate2_max_concurrency,
                basis=CapacityBasis.MEASURED_ENVELOPE,
                policy_id="broker_reports_gate2_measured_envelope_v1",
            ),
            WorkloadCapacity(
                workload_class=WorkloadClass.VISUAL_EXTERNAL,
                max_concurrency=self._config.visual_external_max_concurrency,
                basis=CapacityBasis.EXPLICIT_POLICY,
                policy_id=self._config.visual_external_policy_id,
            ),
            WorkloadCapacity(
                workload_class=WorkloadClass.LIGHTWEIGHT_DETERMINISTIC,
                max_concurrency=(
                    self._config.lightweight_deterministic_max_concurrency
                ),
                basis=CapacityBasis.EXPLICIT_POLICY,
                policy_id=self._config.lightweight_deterministic_policy_id,
            ),
        )

    async def submit(
        self,
        workload_class: WorkloadClass,
        *,
        cleanup_policy: WorkloadCleanupPolicy | None = None,
    ) -> WorkloadTicket:
        if not isinstance(workload_class, WorkloadClass):
            raise WorkloadAdmissionError("workload_class_unsupported")
        if not isinstance(cleanup_policy, WorkloadCleanupPolicy):
            raise WorkloadAdmissionError("workload_cleanup_policy_required")
        ticket = WorkloadTicket(
            job_id=f"brjob_{uuid.uuid4().hex}",
            workload_class=workload_class,
            cleanup_policy=cleanup_policy,
            _scheduler_id=self._scheduler_id,
        )
        record = _JobRecord(ticket=ticket)
        async with self._lock:
            self._records[ticket.job_id] = record
            self._queues[workload_class].append(record)
            self._admit_locked(workload_class)
        return ticket

    async def execute(
        self,
        workload_class: WorkloadClass,
        operation: WorkloadOperation[_T],
        *,
        cleanup_policy: WorkloadCleanupPolicy | None = None,
        cancellation_cleanup: WorkloadCancellationCleanup | None = None,
    ) -> WorkloadExecutionResult[_T]:
        ticket = await self.submit(
            workload_class,
            cleanup_policy=cleanup_policy,
        )
        return await self.run(
            ticket,
            operation,
            cancellation_cleanup=cancellation_cleanup,
        )

    async def run(
        self,
        ticket: WorkloadTicket,
        operation: WorkloadOperation[_T],
        *,
        cancellation_cleanup: WorkloadCancellationCleanup | None = None,
    ) -> WorkloadExecutionResult[_T]:
        record = self._record_for(ticket)
        cleanup_contract_error = _cleanup_contract_error(
            ticket.cleanup_policy,
            cancellation_cleanup,
        )
        if cleanup_contract_error is not None:
            await self._reject_before_run(record)
            raise WorkloadAdmissionError(cleanup_contract_error)

        try:
            await record.ready.wait()
            async with self._lock:
                if record.state is WorkloadState.CANCELLED:
                    return WorkloadExecutionResult(
                        snapshot=self._snapshot_locked(record),
                        value=None,
                    )
                if record.state is not WorkloadState.ADMITTED:
                    raise WorkloadAdmissionError("workload_ticket_not_runnable")
                self._transition_locked(record, WorkloadState.RUNNING)
        except asyncio.CancelledError:
            await asyncio.shield(
                self._cancel_from_task(
                    record,
                    cancellation_cleanup,
                )
            )
            raise

        context = WorkloadExecutionContext(record, self)
        try:
            context.checkpoint()
            pending_result = operation(context)
            if not inspect.isawaitable(pending_result):
                raise WorkloadAdmissionError("workload_operation_must_be_async")
            value = await pending_result
            context.checkpoint()
            snapshot = await self._finish(record, WorkloadState.COMPLETED)
            return WorkloadExecutionResult(snapshot=snapshot, value=value)
        except WorkloadCancellationCheckpoint:
            snapshot = await self._cancel_after_cleanup(
                record,
                context,
                cancellation_cleanup,
            )
            return WorkloadExecutionResult(snapshot=snapshot, value=None)
        except asyncio.CancelledError:
            await asyncio.shield(
                self._cancel_from_task(
                    record,
                    cancellation_cleanup,
                )
            )
            raise
        except Exception as exc:
            snapshot = await self._finish(
                record,
                WorkloadState.FAILED,
                error_code="workload_operation_failed",
                error_type=type(exc).__name__,
            )
            return WorkloadExecutionResult(snapshot=snapshot, value=None)

    async def cancel(
        self,
        ticket: WorkloadTicket,
    ) -> CancellationDisposition:
        record = self._record_for(ticket)
        async with self._lock:
            if record.state in TERMINAL_WORKLOAD_STATES:
                return CancellationDisposition.ALREADY_TERMINAL
            record.cancellation_requested.set()
            if record.state is WorkloadState.QUEUED:
                self._queues[ticket.workload_class].remove(record)
                self._transition_locked(record, WorkloadState.CANCELLED)
                record.ready.set()
                record.terminal.set()
                self._admit_locked(ticket.workload_class)
                return CancellationDisposition.CANCELLED_BEFORE_RUN
            if record.state is WorkloadState.ADMITTED:
                self._active[ticket.workload_class] -= 1
                self._transition_locked(record, WorkloadState.CANCELLED)
                record.ready.set()
                record.terminal.set()
                self._admit_locked(ticket.workload_class)
                return CancellationDisposition.CANCELLED_BEFORE_RUN
            return CancellationDisposition.CANCELLATION_REQUESTED

    async def snapshot(self, ticket: WorkloadTicket) -> WorkloadSnapshot:
        record = self._record_for(ticket)
        async with self._lock:
            return self._snapshot_locked(record)

    async def wait_terminal(self, ticket: WorkloadTicket) -> WorkloadSnapshot:
        record = self._record_for(ticket)
        await record.terminal.wait()
        async with self._lock:
            return self._snapshot_locked(record)

    def _record_for(self, ticket: WorkloadTicket) -> _JobRecord:
        if (
            not isinstance(ticket, WorkloadTicket)
            or ticket._scheduler_id != self._scheduler_id
        ):
            raise WorkloadAdmissionError("workload_ticket_foreign")
        record = self._records.get(ticket.job_id)
        if record is None or record.ticket != ticket:
            raise WorkloadAdmissionError("workload_ticket_unknown")
        return record

    async def _finish(
        self,
        record: _JobRecord,
        state: WorkloadState,
        *,
        error_code: str | None = None,
        error_type: str | None = None,
    ) -> WorkloadSnapshot:
        async with self._lock:
            if record.state not in _ACTIVE_WORKLOAD_STATES:
                raise WorkloadAdmissionError("workload_terminal_transition_invalid")
            record.error_code = error_code
            record.error_type = error_type
            self._active[record.ticket.workload_class] -= 1
            self._transition_locked(record, state)
            record.terminal.set()
            self._admit_locked(record.ticket.workload_class)
            return self._snapshot_locked(record)

    async def _cancel_after_cleanup(
        self,
        record: _JobRecord,
        context: WorkloadExecutionContext,
        cleanup: WorkloadCancellationCleanup | None,
    ) -> WorkloadSnapshot:
        if cleanup is not None:
            try:
                cleanup_result = cleanup(context)
                if not inspect.isawaitable(cleanup_result):
                    raise WorkloadAdmissionError(
                        "workload_cancellation_cleanup_must_be_async"
                    )
                await cleanup_result
            except asyncio.CancelledError:
                return await self._finish(
                    record,
                    WorkloadState.FAILED,
                    error_code="workload_cancellation_cleanup_cancelled",
                    error_type="CancelledError",
                )
            except Exception as exc:
                return await self._finish(
                    record,
                    WorkloadState.FAILED,
                    error_code="workload_cancellation_cleanup_failed",
                    error_type=type(exc).__name__,
                )
        return await self._finish(record, WorkloadState.CANCELLED)

    async def _cancel_from_task(
        self,
        record: _JobRecord,
        cleanup: WorkloadCancellationCleanup | None,
    ) -> WorkloadSnapshot:
        async with self._lock:
            if record.state in TERMINAL_WORKLOAD_STATES:
                return self._snapshot_locked(record)
            record.cancellation_requested.set()
            workload_class = record.ticket.workload_class
            if record.state is WorkloadState.QUEUED:
                self._queues[workload_class].remove(record)
                self._transition_locked(record, WorkloadState.CANCELLED)
                record.ready.set()
                record.terminal.set()
                self._admit_locked(workload_class)
                return self._snapshot_locked(record)
            if record.state is WorkloadState.ADMITTED:
                self._active[workload_class] -= 1
                self._transition_locked(record, WorkloadState.CANCELLED)
                record.ready.set()
                record.terminal.set()
                self._admit_locked(workload_class)
                return self._snapshot_locked(record)
            if record.state not in _ACTIVE_WORKLOAD_STATES:
                raise WorkloadAdmissionError("workload_cancellation_transition_invalid")

        return await self._cancel_after_cleanup(
            record,
            WorkloadExecutionContext(record, self),
            cleanup,
        )

    async def _reject_before_run(self, record: _JobRecord) -> None:
        async with self._lock:
            if record.state in TERMINAL_WORKLOAD_STATES:
                return
            workload_class = record.ticket.workload_class
            record.cancellation_requested.set()
            if record.state is WorkloadState.QUEUED:
                self._queues[workload_class].remove(record)
            elif record.state is WorkloadState.ADMITTED:
                self._active[workload_class] -= 1
            else:
                raise WorkloadAdmissionError("workload_ticket_not_runnable")
            self._transition_locked(record, WorkloadState.CANCELLED)
            record.ready.set()
            record.terminal.set()
            self._admit_locked(workload_class)

    async def _advance_progress(
        self,
        record: _JobRecord,
        state: WorkloadState,
    ) -> WorkloadSnapshot:
        allowed = _PROGRESS_ORDER[record.ticket.workload_class]
        if state not in allowed:
            raise WorkloadAdmissionError("workload_progress_state_not_allowed")
        progress_rank = allowed.index(state)
        async with self._lock:
            if record.state not in _ACTIVE_WORKLOAD_STATES:
                raise WorkloadAdmissionError("workload_progress_transition_invalid")
            if record.cancellation_requested.is_set():
                raise WorkloadCancellationCheckpoint(
                    "workload_cancellation_checkpoint_reached"
                )
            if progress_rank <= record.progress_rank:
                raise WorkloadAdmissionError("workload_progress_not_forward")
            record.progress_rank = progress_rank
            self._transition_locked(record, state)
            return self._snapshot_locked(record)

    def _admit_locked(self, workload_class: WorkloadClass) -> None:
        queue = self._queues[workload_class]
        limit = self._config.limit_for(workload_class)
        while queue and self._active[workload_class] < limit:
            record = queue.popleft()
            if record.state is not WorkloadState.QUEUED:
                continue
            self._active[workload_class] += 1
            self._transition_locked(record, WorkloadState.ADMITTED)
            record.ready.set()

    def _snapshot_locked(self, record: _JobRecord) -> WorkloadSnapshot:
        queue_position: int | None = None
        if record.state is WorkloadState.QUEUED:
            queue = self._queues[record.ticket.workload_class]
            queue_position = next(
                index
                for index, queued_record in enumerate(queue, start=1)
                if queued_record is record
            )
        return WorkloadSnapshot(
            job_id=record.ticket.job_id,
            workload_class=record.ticket.workload_class,
            state=record.state,
            queue_position=queue_position,
            cancellation_requested=record.cancellation_requested.is_set(),
            cleanup_policy=record.ticket.cleanup_policy,
            transitions=tuple(record.transitions),
            error_code=record.error_code,
            error_type=record.error_type,
        )

    @staticmethod
    def _transition_locked(record: _JobRecord, state: WorkloadState) -> None:
        record.state = state
        record.transitions.append(
            WorkloadTransition(sequence=len(record.transitions) + 1, state=state)
        )


def _validate_config(config: WorkloadAdmissionConfig) -> None:
    limits = (
        config.gate1_max_concurrency,
        config.gate2_max_concurrency,
        config.visual_external_max_concurrency,
        config.lightweight_deterministic_max_concurrency,
    )
    if any(
        isinstance(limit, bool) or not isinstance(limit, int) or limit < 1
        for limit in limits
    ):
        raise WorkloadAdmissionError("workload_concurrency_limit_invalid")
    if config.gate1_max_concurrency != 1:
        raise WorkloadAdmissionError("gate1_measured_concurrency_override_forbidden")
    if config.gate2_max_concurrency != 2:
        raise WorkloadAdmissionError("gate2_measured_concurrency_override_forbidden")
    if not config.visual_external_policy_id.strip():
        raise WorkloadAdmissionError("visual_external_policy_id_required")
    if not config.lightweight_deterministic_policy_id.strip():
        raise WorkloadAdmissionError("lightweight_deterministic_policy_id_required")


def _cleanup_contract_error(
    cleanup_policy: WorkloadCleanupPolicy,
    cleanup: WorkloadCancellationCleanup | None,
) -> str | None:
    if cleanup_policy is WorkloadCleanupPolicy.CLEANUP_CALLBACK_REQUIRED:
        if cleanup is None:
            return "workload_cancellation_cleanup_required"
        return None
    if cleanup_policy is WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS:
        if cleanup is not None:
            return "workload_cancellation_cleanup_forbidden"
        return None
    return "workload_cleanup_policy_required"
