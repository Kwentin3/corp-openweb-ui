from __future__ import annotations

import asyncio
import unittest

from broker_reports_gate1.workload_admission import (
    FACTORY_REQUIRED,
    FORBIDDEN,
    WORKLOAD_ADMISSION_COORDINATION_SCOPE,
    WORKLOAD_ADMISSION_IMPLEMENTATION_STATUS,
    CapacityBasis,
    CancellationDisposition,
    WorkloadAdmissionConfig,
    WorkloadAdmissionError,
    WorkloadAdmissionScheduler,
    WorkloadAdmissionSchedulerFactory,
    WorkloadClass,
    WorkloadCleanupPolicy,
    WorkloadState,
)


class BrokerReportsWorkloadAdmissionTest(unittest.IsolatedAsyncioTestCase):
    def test_factory_owns_construction_and_capacity_basis_is_explicit(self) -> None:
        self.assertIn("WorkloadAdmissionSchedulerFactory.create", FACTORY_REQUIRED)
        self.assertIn("must not create private semaphores", FORBIDDEN)

        with self.assertRaisesRegex(
            WorkloadAdmissionError,
            "workload_admission_factory_required",
        ):
            WorkloadAdmissionScheduler(
                config=WorkloadAdmissionConfig(),
                _factory_token=object(),
            )

        scheduler = WorkloadAdmissionSchedulerFactory().create()
        self.assertEqual(
            scheduler.implementation_status,
            WORKLOAD_ADMISSION_IMPLEMENTATION_STATUS,
        )
        self.assertEqual(
            scheduler.coordination_scope,
            WORKLOAD_ADMISSION_COORDINATION_SCOPE,
        )
        self.assertEqual(scheduler.implementation_status, "implementation_pending")
        self.assertEqual(
            scheduler.coordination_scope,
            "single_scheduler_instance_scaffold",
        )
        self.assertIn("process-wide or multi-worker", FORBIDDEN)
        profile = {
            capacity.workload_class: capacity
            for capacity in scheduler.capacity_profile()
        }
        self.assertEqual(profile[WorkloadClass.GATE1].max_concurrency, 1)
        self.assertEqual(profile[WorkloadClass.GATE2].max_concurrency, 2)
        self.assertEqual(profile[WorkloadClass.VISUAL_EXTERNAL].max_concurrency, 1)
        self.assertEqual(
            profile[WorkloadClass.LIGHTWEIGHT_DETERMINISTIC].max_concurrency,
            8,
        )
        self.assertIs(
            profile[WorkloadClass.GATE1].basis,
            CapacityBasis.MEASURED_ENVELOPE,
        )
        self.assertIs(
            profile[WorkloadClass.GATE2].basis,
            CapacityBasis.MEASURED_ENVELOPE,
        )
        self.assertIs(
            profile[WorkloadClass.VISUAL_EXTERNAL].basis,
            CapacityBasis.EXPLICIT_POLICY,
        )
        self.assertEqual(
            profile[WorkloadClass.VISUAL_EXTERNAL].policy_id,
            "visual_external_provider_serial_v1",
        )
        self.assertIs(
            profile[WorkloadClass.LIGHTWEIGHT_DETERMINISTIC].basis,
            CapacityBasis.EXPLICIT_POLICY,
        )

    def test_factory_rejects_invalid_or_implicit_capacity_policy(self) -> None:
        with self.assertRaisesRegex(
            WorkloadAdmissionError,
            "workload_concurrency_limit_invalid",
        ):
            WorkloadAdmissionSchedulerFactory(
                WorkloadAdmissionConfig(gate1_max_concurrency=0)
            ).create()
        with self.assertRaisesRegex(
            WorkloadAdmissionError,
            "gate1_measured_concurrency_override_forbidden",
        ):
            WorkloadAdmissionSchedulerFactory(
                WorkloadAdmissionConfig(gate1_max_concurrency=2)
            ).create()
        with self.assertRaisesRegex(
            WorkloadAdmissionError,
            "gate2_measured_concurrency_override_forbidden",
        ):
            WorkloadAdmissionSchedulerFactory(
                WorkloadAdmissionConfig(gate2_max_concurrency=3)
            ).create()
        with self.assertRaisesRegex(
            WorkloadAdmissionError,
            "visual_external_policy_id_required",
        ):
            WorkloadAdmissionSchedulerFactory(
                WorkloadAdmissionConfig(visual_external_policy_id="  ")
            ).create()

    async def test_cleanup_policy_is_explicit_and_contract_mismatch_releases_capacity(
        self,
    ) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        with self.assertRaisesRegex(
            WorkloadAdmissionError,
            "workload_cleanup_policy_required",
        ):
            await scheduler.submit(WorkloadClass.GATE1)

        missing_cleanup = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.CLEANUP_CALLBACK_REQUIRED,
        )
        following = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )

        async def operation(_context):
            return "not-run"

        with self.assertRaisesRegex(
            WorkloadAdmissionError,
            "workload_cancellation_cleanup_required",
        ):
            await scheduler.run(missing_cleanup, operation)

        rejected = await scheduler.snapshot(missing_cleanup)
        self.assertIs(rejected.state, WorkloadState.CANCELLED)
        self.assertTrue(rejected.cancellation_requested)
        self.assertIs(
            (await scheduler.snapshot(following)).state,
            WorkloadState.ADMITTED,
        )
        await scheduler.cancel(following)

        callback_forbidden = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )

        async def cleanup(_context):
            return None

        with self.assertRaisesRegex(
            WorkloadAdmissionError,
            "workload_cancellation_cleanup_forbidden",
        ):
            await scheduler.run(
                callback_forbidden,
                operation,
                cancellation_cleanup=cleanup,
            )
        self.assertIs(
            (await scheduler.snapshot(callback_forbidden)).state,
            WorkloadState.CANCELLED,
        )

    async def test_gate1_is_fifo_and_never_exceeds_one_running_job(self) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        tickets = [
            await scheduler.submit(
                WorkloadClass.GATE1,
                cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
            )
            for _ in range(3)
        ]
        entered = [asyncio.Event() for _ in tickets]
        release = [asyncio.Event() for _ in tickets]
        execution_order: list[int] = []
        active = 0
        maximum_active = 0

        def operation(index: int):
            async def run(_context):
                nonlocal active, maximum_active
                active += 1
                maximum_active = max(maximum_active, active)
                execution_order.append(index)
                entered[index].set()
                try:
                    await release[index].wait()
                finally:
                    active -= 1
                return f"result-{index}"

            return run

        tasks = [
            asyncio.create_task(scheduler.run(ticket, operation(index)))
            for index, ticket in enumerate(tickets)
        ]

        await entered[0].wait()
        self.assertEqual(
            (await scheduler.snapshot(tickets[1])).queue_position,
            1,
        )
        self.assertEqual(
            (await scheduler.snapshot(tickets[2])).queue_position,
            2,
        )

        release[0].set()
        first_result = await tasks[0]
        await entered[1].wait()
        self.assertIs(first_result.snapshot.state, WorkloadState.COMPLETED)
        self.assertEqual(first_result.value, "result-0")
        self.assertIs(
            (await scheduler.snapshot(tickets[2])).state,
            WorkloadState.QUEUED,
        )

        release[1].set()
        await tasks[1]
        await entered[2].wait()
        release[2].set()
        await tasks[2]

        self.assertEqual(execution_order, [0, 1, 2])
        self.assertEqual(maximum_active, 1)
        self.assertEqual(
            [
                transition.state
                for transition in (await scheduler.snapshot(tickets[2])).transitions
            ],
            [
                WorkloadState.QUEUED,
                WorkloadState.ADMITTED,
                WorkloadState.RUNNING,
                WorkloadState.COMPLETED,
            ],
        )

    async def test_gate2_admits_two_and_preserves_the_third(self) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        tickets = [
            await scheduler.submit(
                WorkloadClass.GATE2,
                cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
            )
            for _ in range(3)
        ]
        entered = [asyncio.Event() for _ in tickets]
        release = [asyncio.Event() for _ in tickets]
        active = 0
        maximum_active = 0

        def operation(index: int):
            async def run(_context):
                nonlocal active, maximum_active
                active += 1
                maximum_active = max(maximum_active, active)
                entered[index].set()
                try:
                    await release[index].wait()
                finally:
                    active -= 1
                return index

            return run

        tasks = [
            asyncio.create_task(scheduler.run(ticket, operation(index)))
            for index, ticket in enumerate(tickets)
        ]
        await asyncio.gather(entered[0].wait(), entered[1].wait())

        third_snapshot = await scheduler.snapshot(tickets[2])
        self.assertIs(third_snapshot.state, WorkloadState.QUEUED)
        self.assertEqual(third_snapshot.queue_position, 1)

        release[0].set()
        await tasks[0]
        await entered[2].wait()
        release[1].set()
        release[2].set()
        await asyncio.gather(tasks[1], tasks[2])

        self.assertEqual(maximum_active, 2)
        terminal_snapshots = [await scheduler.snapshot(ticket) for ticket in tickets]
        self.assertTrue(
            all(
                snapshot.state is WorkloadState.COMPLETED
                for snapshot in terminal_snapshots
            )
        )

    async def test_queued_cancellation_preserves_following_work(self) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        first = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        cancelled = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        third = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        first_entered = asyncio.Event()
        first_release = asyncio.Event()
        third_entered = asyncio.Event()

        async def first_operation(_context):
            first_entered.set()
            await first_release.wait()
            return "first"

        async def third_operation(_context):
            third_entered.set()
            return "third"

        first_task = asyncio.create_task(scheduler.run(first, first_operation))
        third_task = asyncio.create_task(scheduler.run(third, third_operation))
        await first_entered.wait()

        disposition = await scheduler.cancel(cancelled)
        self.assertIs(
            disposition,
            CancellationDisposition.CANCELLED_BEFORE_RUN,
        )
        cancelled_result = await scheduler.run(cancelled, third_operation)
        self.assertIs(cancelled_result.snapshot.state, WorkloadState.CANCELLED)
        self.assertEqual(
            [item.state for item in cancelled_result.snapshot.transitions],
            [WorkloadState.QUEUED, WorkloadState.CANCELLED],
        )
        self.assertEqual((await scheduler.snapshot(third)).queue_position, 1)

        first_release.set()
        await first_task
        await third_entered.wait()
        third_result = await third_task
        self.assertIs(third_result.snapshot.state, WorkloadState.COMPLETED)
        self.assertEqual(third_result.value, "third")

    async def test_cancelling_queued_run_task_does_not_orphan_admission(self) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        first = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        cancelled = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        following = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        first_entered = asyncio.Event()
        first_release = asyncio.Event()
        following_entered = asyncio.Event()

        async def first_operation(_context):
            first_entered.set()
            await first_release.wait()
            return "first"

        async def cancelled_operation(_context):
            return "must-not-run"

        async def following_operation(_context):
            following_entered.set()
            return "following"

        first_task = asyncio.create_task(scheduler.run(first, first_operation))
        cancelled_task = asyncio.create_task(
            scheduler.run(cancelled, cancelled_operation)
        )
        following_task = asyncio.create_task(
            scheduler.run(following, following_operation)
        )
        await first_entered.wait()
        self.assertIs(
            (await scheduler.snapshot(cancelled)).state,
            WorkloadState.QUEUED,
        )

        cancelled_task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await cancelled_task

        cancelled_snapshot = await scheduler.snapshot(cancelled)
        self.assertIs(cancelled_snapshot.state, WorkloadState.CANCELLED)
        self.assertEqual(
            [item.state for item in cancelled_snapshot.transitions],
            [WorkloadState.QUEUED, WorkloadState.CANCELLED],
        )
        self.assertEqual((await scheduler.snapshot(following)).queue_position, 1)

        first_release.set()
        first_result = await first_task
        await following_entered.wait()
        following_result = await following_task
        self.assertIs(first_result.snapshot.state, WorkloadState.COMPLETED)
        self.assertIs(following_result.snapshot.state, WorkloadState.COMPLETED)
        self.assertEqual(following_result.value, "following")

    async def test_running_cancellation_is_cooperative_and_terminal(self) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        running = await scheduler.submit(
            WorkloadClass.VISUAL_EXTERNAL,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        following = await scheduler.submit(
            WorkloadClass.VISUAL_EXTERNAL,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        running_entered = asyncio.Event()
        reach_checkpoint = asyncio.Event()
        following_entered = asyncio.Event()

        async def cancellable(context):
            running_entered.set()
            await reach_checkpoint.wait()
            context.checkpoint()
            return "must-not-complete"

        async def following_operation(_context):
            following_entered.set()
            return "following"

        running_task = asyncio.create_task(scheduler.run(running, cancellable))
        following_task = asyncio.create_task(
            scheduler.run(following, following_operation)
        )
        await running_entered.wait()

        disposition = await scheduler.cancel(running)
        self.assertIs(
            disposition,
            CancellationDisposition.CANCELLATION_REQUESTED,
        )
        requested = await scheduler.snapshot(running)
        self.assertIs(requested.state, WorkloadState.RUNNING)
        self.assertTrue(requested.cancellation_requested)
        self.assertFalse(following_entered.is_set())

        reach_checkpoint.set()
        cancelled_result = await running_task
        await following_entered.wait()
        following_result = await following_task

        self.assertIs(cancelled_result.snapshot.state, WorkloadState.CANCELLED)
        self.assertIs(following_result.snapshot.state, WorkloadState.COMPLETED)
        self.assertEqual(following_result.value, "following")

    async def test_cancelling_running_task_cleans_before_releasing_capacity(
        self,
    ) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        running = await scheduler.submit(
            WorkloadClass.VISUAL_EXTERNAL,
            cleanup_policy=WorkloadCleanupPolicy.CLEANUP_CALLBACK_REQUIRED,
        )
        following = await scheduler.submit(
            WorkloadClass.VISUAL_EXTERNAL,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        running_entered = asyncio.Event()
        never_complete = asyncio.Event()
        cleanup_entered = asyncio.Event()
        cleanup_release = asyncio.Event()
        following_entered = asyncio.Event()
        cleanup_trace: list[str] = []

        async def operation(_context):
            running_entered.set()
            await never_complete.wait()
            return "must-not-complete"

        async def cleanup(_context):
            cleanup_trace.append("cleanup_started")
            cleanup_entered.set()
            await cleanup_release.wait()
            cleanup_trace.append("cleanup_completed")

        async def following_operation(_context):
            following_entered.set()
            return "following"

        running_task = asyncio.create_task(
            scheduler.run(
                running,
                operation,
                cancellation_cleanup=cleanup,
            )
        )
        following_task = asyncio.create_task(
            scheduler.run(following, following_operation)
        )
        await running_entered.wait()

        running_task.cancel()
        await cleanup_entered.wait()
        self.assertFalse(running_task.done())
        self.assertFalse(following_entered.is_set())
        self.assertNotIn(
            (await scheduler.snapshot(running)).state,
            {
                WorkloadState.COMPLETED,
                WorkloadState.CANCELLED,
                WorkloadState.FAILED,
            },
        )

        cleanup_release.set()
        with self.assertRaises(asyncio.CancelledError):
            await running_task
        await following_entered.wait()
        following_result = await following_task

        self.assertIs(
            (await scheduler.snapshot(running)).state,
            WorkloadState.CANCELLED,
        )
        self.assertEqual(cleanup_trace, ["cleanup_started", "cleanup_completed"])
        self.assertIs(following_result.snapshot.state, WorkloadState.COMPLETED)

    async def test_typed_progress_is_visible_and_forward_only(self) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        ticket = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        normalizing_visible = asyncio.Event()
        continue_operation = asyncio.Event()

        async def operation(context):
            await context.advance(WorkloadState.SOURCE_INTAKE)
            await context.advance(WorkloadState.NORMALIZING)
            normalizing_visible.set()
            await continue_operation.wait()
            await context.advance(WorkloadState.BUILDING_DOCUMENT_MEMORY)
            await context.advance(WorkloadState.VALIDATING)
            return "sealed-manifest"

        task = asyncio.create_task(scheduler.run(ticket, operation))
        await normalizing_visible.wait()

        snapshot = await scheduler.snapshot(ticket)
        self.assertIs(snapshot.state, WorkloadState.NORMALIZING)
        self.assertEqual(
            [item.state for item in snapshot.transitions],
            [
                WorkloadState.QUEUED,
                WorkloadState.ADMITTED,
                WorkloadState.RUNNING,
                WorkloadState.SOURCE_INTAKE,
                WorkloadState.NORMALIZING,
            ],
        )

        continue_operation.set()
        result = await task
        self.assertIs(result.snapshot.state, WorkloadState.COMPLETED)
        self.assertEqual(result.value, "sealed-manifest")

    async def test_cancellation_cleanup_precedes_terminal_and_next_admission(
        self,
    ) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        running = await scheduler.submit(
            WorkloadClass.VISUAL_EXTERNAL,
            cleanup_policy=WorkloadCleanupPolicy.CLEANUP_CALLBACK_REQUIRED,
        )
        following = await scheduler.submit(
            WorkloadClass.VISUAL_EXTERNAL,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        running_entered = asyncio.Event()
        reach_checkpoint = asyncio.Event()
        cleanup_entered = asyncio.Event()
        cleanup_release = asyncio.Event()
        following_entered = asyncio.Event()
        cleanup_trace: list[str] = []

        async def operation(context):
            running_entered.set()
            await reach_checkpoint.wait()
            context.checkpoint()
            return "must-not-publish"

        async def cleanup(_context):
            cleanup_trace.append("temporary_private_artifacts_cleanup_started")
            cleanup_entered.set()
            await cleanup_release.wait()
            cleanup_trace.append("temporary_private_artifacts_cleanup_completed")

        async def following_operation(_context):
            following_entered.set()
            return "next-result"

        running_task = asyncio.create_task(
            scheduler.run(
                running,
                operation,
                cancellation_cleanup=cleanup,
            )
        )
        following_task = asyncio.create_task(
            scheduler.run(following, following_operation)
        )
        await running_entered.wait()
        await scheduler.cancel(running)
        reach_checkpoint.set()
        await cleanup_entered.wait()

        during_cleanup = await scheduler.snapshot(running)
        self.assertNotIn(
            during_cleanup.state,
            {
                WorkloadState.COMPLETED,
                WorkloadState.CANCELLED,
                WorkloadState.FAILED,
            },
        )
        self.assertFalse(following_entered.is_set())

        cleanup_release.set()
        cancelled_result = await running_task
        await following_entered.wait()
        following_result = await following_task

        self.assertIs(cancelled_result.snapshot.state, WorkloadState.CANCELLED)
        self.assertIsNone(cancelled_result.value)
        self.assertEqual(
            cleanup_trace,
            [
                "temporary_private_artifacts_cleanup_started",
                "temporary_private_artifacts_cleanup_completed",
            ],
        )
        self.assertIs(following_result.snapshot.state, WorkloadState.COMPLETED)

    async def test_failure_is_typed_terminal_and_releases_capacity(self) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        first = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        following = await scheduler.submit(
            WorkloadClass.GATE1,
            cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
        )
        following_entered = asyncio.Event()

        async def failing(_context):
            raise ValueError("private failure details")

        async def succeeding(_context):
            following_entered.set()
            return 42

        first_task = asyncio.create_task(scheduler.run(first, failing))
        following_task = asyncio.create_task(scheduler.run(following, succeeding))
        failed_result = await first_task
        await following_entered.wait()
        completed_result = await following_task

        self.assertIs(failed_result.snapshot.state, WorkloadState.FAILED)
        self.assertEqual(
            failed_result.snapshot.error_code,
            "workload_operation_failed",
        )
        self.assertEqual(failed_result.snapshot.error_type, "ValueError")
        self.assertNotIn(
            "private failure details",
            repr(failed_result.snapshot),
        )
        self.assertIs(completed_result.snapshot.state, WorkloadState.COMPLETED)
        self.assertEqual(completed_result.value, 42)

    async def test_queue_has_no_truncation_limit(self) -> None:
        scheduler = WorkloadAdmissionSchedulerFactory().create()
        tickets = [
            await scheduler.submit(
                WorkloadClass.GATE1,
                cleanup_policy=WorkloadCleanupPolicy.NO_PRIVATE_ARTIFACTS,
            )
            for _ in range(65)
        ]
        snapshots = [await scheduler.snapshot(ticket) for ticket in tickets]

        self.assertIs(snapshots[0].state, WorkloadState.ADMITTED)
        self.assertTrue(
            all(item.state is WorkloadState.QUEUED for item in snapshots[1:])
        )
        self.assertEqual(
            [item.queue_position for item in snapshots[1:]],
            list(range(1, 65)),
        )


if __name__ == "__main__":
    unittest.main()
