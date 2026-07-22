from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from broker_reports_gate1 import (
    ArtifactStoreConfig,
    ArtifactStoreFactory,
    FileInput,
    Gate1Normalizer,
)
from broker_reports_gate1.workload_authority import (
    GATE1_HEAVY_CONCURRENCY,
    GATE2_LOCAL_MAXIMUM_CONCURRENCY,
    LOCAL_OCR_WORKER_POOL_ALLOWED,
    REQUIRED_PERSISTED_STATES,
    WORKLOAD_ADMISSION_POLICY,
    WORKLOAD_AUTHORITY_COORDINATION_SCOPE,
    WORKLOAD_AUTHORITY_IMPLEMENTATION_STATUS,
    WORKLOAD_PRIMARY_WALL_TIMEOUT,
    WorkloadAccessContext,
    WorkloadAuthorityConfig,
    WorkloadAuthorityError,
    WorkloadAuthorityFactory,
    WorkloadCancelledError,
    WorkloadKind,
    WorkloadState,
)
from openwebui_actions.broker_reports_gate1_pipe import Pipe as Gate1Pipe
from openwebui_actions.broker_reports_gate2_source_fact_pipe import Pipe as Gate2Pipe


class BrokerReportsWorkloadAuthorityTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.access = WorkloadAccessContext(
            user_id="workload-user",
            case_id="workload-case",
            chat_id="workload-chat",
            workspace_model_id="workload-model",
        )

    def _config(self, **overrides) -> WorkloadAuthorityConfig:
        values = {
            "sqlite_path": self.root / "workloads.sqlite3",
            "temp_root": self.root / "private-job-temp",
            "lease_seconds": 2.0,
            "heartbeat_interval_seconds": 0.2,
            "poll_interval_seconds": 0.02,
            "provider_budgets": {"google_gemini": 1, "openai_gpt": 1},
        }
        values.update(overrides)
        return WorkloadAuthorityConfig(**values)

    def _authority(self, **overrides):
        return WorkloadAuthorityFactory(self._config(**overrides)).create()

    def _submit(self, authority, kind: WorkloadKind):
        return authority.submit(job_kind=kind, access=self.access)

    def test_contract_is_maintained_persisted_and_has_no_primary_wall_timeout(self):
        authority = self._authority()
        contract = authority.config.safe_contract()

        self.assertEqual(WORKLOAD_AUTHORITY_IMPLEMENTATION_STATUS, "maintained")
        self.assertEqual(
            WORKLOAD_AUTHORITY_COORDINATION_SCOPE,
            "sqlite_cross_process_single_authority",
        )
        self.assertEqual(WORKLOAD_ADMISSION_POLICY, "capacity_queue_plus_worker_lease")
        self.assertEqual(GATE1_HEAVY_CONCURRENCY, 1)
        self.assertEqual(GATE2_LOCAL_MAXIMUM_CONCURRENCY, 2)
        self.assertIsNone(WORKLOAD_PRIMARY_WALL_TIMEOUT)
        self.assertIsNone(contract["primary_wall_timeout"])
        self.assertFalse(LOCAL_OCR_WORKER_POOL_ALLOWED)
        self.assertEqual(
            set(REQUIRED_PERSISTED_STATES),
            {
                "queued",
                "source_intake",
                "normalizing",
                "building_document_memory",
                "validating",
                "preparing_gate2",
                "awaiting_provider",
                "awaiting_review",
                "completed",
                "failed",
                "cancelled",
            },
        )

    def test_shared_database_enforces_gate1_fifo_concurrency_one(self):
        first_authority = self._authority()
        second_authority = WorkloadAuthorityFactory(self._config()).create()
        first = self._submit(first_authority, WorkloadKind.GATE1)
        second = self._submit(second_authority, WorkloadKind.GATE1)

        first_session = first_authority.try_admit(
            job_id=first.job_id, access=self.access, worker_id="worker-one"
        )
        self.assertIsNotNone(first_session)
        self.assertIsNone(
            second_authority.try_admit(
                job_id=second.job_id,
                access=self.access,
                worker_id="worker-two",
            )
        )
        self.assertEqual(
            second_authority.snapshot(job_id=second.job_id, access=self.access)[
                "queue_position"
            ],
            1,
        )

        first_session.transition(WorkloadState.NORMALIZING)
        first_session.transition(WorkloadState.BUILDING_DOCUMENT_MEMORY)
        first_session.transition(WorkloadState.VALIDATING)
        first_session.complete()
        second_session = second_authority.try_admit(
            job_id=second.job_id, access=self.access, worker_id="worker-two"
        )
        self.assertIsNotNone(second_session)
        second_session.cancel("test_cleanup")

    def test_gate2_admits_two_and_keeps_third_queued(self):
        authority = self._authority(gate2_concurrency=2)
        tickets = [self._submit(authority, WorkloadKind.GATE2_SOURCE) for _ in range(3)]
        sessions = [
            authority.try_admit(
                job_id=ticket.job_id,
                access=self.access,
                worker_id=f"gate2-worker-{index}",
            )
            for index, ticket in enumerate(tickets)
        ]

        self.assertIsNotNone(sessions[0])
        self.assertIsNotNone(sessions[1])
        self.assertIsNone(sessions[2])
        self.assertEqual(
            authority.snapshot(job_id=tickets[2].job_id, access=self.access)["state"],
            "queued",
        )
        sessions[0].cancel("test_cleanup")
        sessions[1].cancel("test_cleanup")
        authority.request_cancel(job_id=tickets[2].job_id, access=self.access)

    def test_simultaneous_authority_instances_cannot_double_admit_gate1(self):
        first_authority = self._authority()
        second_authority = WorkloadAuthorityFactory(self._config()).create()
        first = self._submit(first_authority, WorkloadKind.GATE1)
        second = self._submit(second_authority, WorkloadKind.GATE1)
        barrier = threading.Barrier(2)
        admitted = []
        failures = []

        def claim(authority, ticket, worker):
            try:
                barrier.wait()
                session = authority.try_admit(
                    job_id=ticket.job_id,
                    access=self.access,
                    worker_id=worker,
                )
                if session is not None:
                    admitted.append(session)
            except BaseException as exc:
                failures.append(exc)

        threads = [
            threading.Thread(
                target=claim,
                args=(first_authority, first, "race-worker-1"),
            ),
            threading.Thread(
                target=claim,
                args=(second_authority, second, "race-worker-2"),
            ),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

        self.assertEqual(failures, [])
        self.assertEqual(len(admitted), 1)
        admitted[0].cancel("test_cleanup")
        for ticket in (first, second):
            snapshot = first_authority.snapshot(job_id=ticket.job_id, access=self.access)
            if snapshot["state"] == "queued":
                first_authority.request_cancel(job_id=ticket.job_id, access=self.access)

    def test_idempotent_submit_reuses_one_terminal_gate1_job(self):
        first_authority = self._authority()
        second_authority = WorkloadAuthorityFactory(self._config()).create()
        key = "bridem_" + "a" * 64

        first = first_authority.submit(
            job_kind=WorkloadKind.GATE1,
            access=self.access,
            idempotency_key=key,
            safe_metadata={"idempotency_key_present": True},
        )
        first_session = first_authority.try_admit(
            job_id=first.job_id,
            access=self.access,
            worker_id="idempotent-worker",
        )
        self.assertIsNotNone(first_session)
        first_session.transition(WorkloadState.NORMALIZING)
        first_session.transition(WorkloadState.BUILDING_DOCUMENT_MEMORY)
        first_session.transition(WorkloadState.VALIDATING)
        first_session.complete()

        replay = second_authority.submit(
            job_kind=WorkloadKind.GATE1,
            access=self.access,
            idempotency_key=key,
        )

        self.assertEqual(replay.job_id, first.job_id)
        self.assertTrue(replay.reused_existing)
        self.assertEqual(
            second_authority.snapshot(job_id=replay.job_id, access=self.access)[
                "state"
            ],
            "completed",
        )
        with closing(sqlite3.connect(self._config().sqlite_path)) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM workload_jobs WHERE idempotency_key = ?",
                    (key,),
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                conn.execute(
                    "SELECT COUNT(*) FROM workload_transitions WHERE job_id = ? "
                    "AND to_state = 'completed'",
                    (first.job_id,),
                ).fetchone()[0],
                1,
            )

    def test_idempotency_key_rejects_scope_substitution(self):
        authority = self._authority()
        key = "bridem_" + "b" * 64
        ticket = authority.submit(
            job_kind=WorkloadKind.GATE1,
            access=self.access,
            idempotency_key=key,
        )
        forged = WorkloadAccessContext(
            user_id="other-user",
            case_id=self.access.case_id,
            chat_id=self.access.chat_id,
            workspace_model_id=self.access.workspace_model_id,
        )

        with self.assertRaises(WorkloadAuthorityError) as denied:
            authority.submit(
                job_kind=WorkloadKind.GATE1,
                access=forged,
                idempotency_key=key,
            )
        self.assertEqual(denied.exception.code, "workload_access_denied")

        session = authority.try_admit(
            job_id=ticket.job_id,
            access=self.access,
            worker_id="idempotency-scope-worker",
        )
        self.assertIsNotNone(session)
        session.cancel("test_terminal_cleanup")
        self.assertEqual(session.snapshot()["state"], "cancelled")

    def test_existing_workload_database_migrates_idempotency_column_in_place(self):
        self._authority()
        database = self._config().sqlite_path
        with closing(sqlite3.connect(database)) as conn:
            conn.execute("DROP INDEX workload_jobs_idempotency_idx")
            conn.execute("ALTER TABLE workload_jobs DROP COLUMN idempotency_key")
            conn.commit()

        upgraded = WorkloadAuthorityFactory(self._config()).create()
        with closing(sqlite3.connect(database)) as conn:
            columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(workload_jobs)")
            }
            indexes = {
                str(row[1]) for row in conn.execute("PRAGMA index_list(workload_jobs)")
            }
        self.assertIn("idempotency_key", columns)
        self.assertIn("workload_jobs_idempotency_idx", indexes)

        ticket = upgraded.submit(
            job_kind=WorkloadKind.GATE1,
            access=self.access,
            idempotency_key="bridem_" + "c" * 64,
        )
        session = upgraded.try_admit(
            job_id=ticket.job_id,
            access=self.access,
            worker_id="migrated-schema-worker",
        )
        self.assertIsNotNone(session)
        session.cancel("test_terminal_cleanup")
        self.assertEqual(session.snapshot()["state"], "cancelled")

    def test_provider_budget_is_separate_persisted_fifo_capacity(self):
        async def scenario() -> None:
            authority = self._authority(gate2_concurrency=2)
            first = self._submit(authority, WorkloadKind.GATE2_SOURCE)
            second = self._submit(authority, WorkloadKind.GATE2_DOMAIN)
            first_session = authority.try_admit(
                job_id=first.job_id, access=self.access, worker_id="provider-worker-1"
            )
            second_session = authority.try_admit(
                job_id=second.job_id, access=self.access, worker_id="provider-worker-2"
            )
            first_entered = asyncio.Event()
            release_first = asyncio.Event()
            second_entered = asyncio.Event()

            async def first_call():
                async with first_session.provider_slot_async("openai_gpt"):
                    first_entered.set()
                    await release_first.wait()

            async def second_call():
                async with second_session.provider_slot_async("openai_gpt"):
                    second_entered.set()

            first_task = asyncio.create_task(first_call())
            await first_entered.wait()
            second_task = asyncio.create_task(second_call())
            await asyncio.sleep(0.08)
            self.assertFalse(second_entered.is_set())
            self.assertEqual(second_session.snapshot()["state"], "awaiting_provider")
            self.assertEqual(second_session.snapshot()["provider_queue_position"], 1)
            release_first.set()
            await first_task
            await second_task
            self.assertTrue(second_entered.is_set())
            first_session.complete()
            second_session.complete()

        asyncio.run(scenario())

    def test_authenticated_snapshot_and_cancel_reject_scope_substitution(self):
        authority = self._authority()
        ticket = self._submit(authority, WorkloadKind.GATE1)
        forged = WorkloadAccessContext(
            user_id="other-user",
            case_id=self.access.case_id,
            chat_id=self.access.chat_id,
            workspace_model_id=self.access.workspace_model_id,
        )

        with self.assertRaises(WorkloadAuthorityError) as denied:
            authority.snapshot(job_id=ticket.job_id, access=forged)
        self.assertEqual(denied.exception.code, "workload_access_denied")
        with self.assertRaises(WorkloadAuthorityError) as cancel_denied:
            authority.request_cancel(job_id=ticket.job_id, access=forged)
        self.assertEqual(cancel_denied.exception.code, "workload_access_denied")
        authority.request_cancel(job_id=ticket.job_id, access=self.access)

    def test_cancellation_while_waiting_for_provider_is_terminal(self):
        async def scenario() -> None:
            authority = self._authority(gate2_concurrency=2)
            first = self._submit(authority, WorkloadKind.GATE2_SOURCE)
            second = self._submit(authority, WorkloadKind.GATE2_DOMAIN)
            first_session = authority.try_admit(
                job_id=first.job_id, access=self.access, worker_id="holder"
            )
            second_session = authority.try_admit(
                job_id=second.job_id, access=self.access, worker_id="waiter"
            )
            holder_entered = asyncio.Event()
            release_holder = asyncio.Event()

            async def hold_provider():
                async with first_session.provider_slot_async("openai_gpt"):
                    holder_entered.set()
                    await release_holder.wait()

            async def wait_provider():
                async with second_session.provider_slot_async("openai_gpt"):
                    raise AssertionError("cancelled waiter must not enter provider slot")

            holder_task = asyncio.create_task(hold_provider())
            await holder_entered.wait()
            waiter_task = asyncio.create_task(wait_provider())
            while second_session.snapshot()["state"] != "awaiting_provider":
                await asyncio.sleep(0.01)
            authority.request_cancel(job_id=second.job_id, access=self.access)
            with self.assertRaises(WorkloadCancelledError):
                await waiter_task
            self.assertEqual(second_session.snapshot()["state"], "cancelled")
            release_holder.set()
            await holder_task
            first_session.complete()

        asyncio.run(scenario())

    def test_queued_cancellation_is_terminal_and_cleans_owned_private_temp(self):
        authority = self._authority()
        ticket = self._submit(authority, WorkloadKind.GATE1)
        temp_dir = self.root / "private-job-temp" / ticket.job_id
        (temp_dir / "partial.bin").write_bytes(b"private partial")

        snapshot = authority.request_cancel(
            job_id=ticket.job_id,
            access=self.access,
            reason_code="user_requested",
        )

        self.assertEqual(snapshot["state"], "cancelled")
        self.assertEqual(snapshot["cleanup_status"], "cleaned")
        self.assertFalse(temp_dir.exists())
        self.assertFalse(
            any(
                item["to_state"] == "completed"
                for item in authority.transitions(job_id=ticket.job_id, access=self.access)
            )
        )

    def test_running_cancellation_is_cooperative_terminal_and_retry_safe(self):
        authority = self._authority()
        ticket = self._submit(authority, WorkloadKind.GATE1)
        session = authority.try_admit(job_id=ticket.job_id, access=self.access)
        session.transition(WorkloadState.NORMALIZING)
        (session.temp_dir / "partial-private.json").write_text("{}", encoding="utf-8")
        authority.request_cancel(job_id=ticket.job_id, access=self.access)

        with self.assertRaises(WorkloadCancelledError):
            session.checkpoint()
        snapshot = authority.snapshot(job_id=ticket.job_id, access=self.access)
        self.assertEqual(snapshot["state"], "cancelled")
        self.assertEqual(snapshot["cleanup_status"], "cleaned")
        self.assertFalse(session.temp_dir.exists())
        with self.assertRaises(WorkloadAuthorityError):
            session.complete()

        retry = authority.retry(job_id=ticket.job_id, access=self.access)
        retry_snapshot = authority.snapshot(job_id=retry.job_id, access=self.access)
        self.assertEqual(retry_snapshot["state"], "queued")
        self.assertEqual(retry_snapshot["retry_of_job_id"], ticket.job_id)
        self.assertNotEqual(retry.job_id, ticket.job_id)
        authority.request_cancel(job_id=retry.job_id, access=self.access)

    def test_expired_worker_lease_fails_and_never_false_completes(self):
        config = self._config(
            lease_seconds=0.25,
            heartbeat_interval_seconds=0.05,
            poll_interval_seconds=0.01,
        )
        authority = WorkloadAuthorityFactory(config).create()
        ticket = self._submit(authority, WorkloadKind.GATE1)
        session = authority.try_admit(job_id=ticket.job_id, access=self.access)
        session.transition(WorkloadState.NORMALIZING)
        (session.temp_dir / "crash-partial").write_bytes(b"partial")
        time.sleep(0.32)

        recovered = WorkloadAuthorityFactory(config).create()
        snapshot = recovered.snapshot(job_id=ticket.job_id, access=self.access)
        self.assertEqual(snapshot["state"], "failed")
        self.assertEqual(snapshot["terminal_code"], "worker_lease_expired")
        self.assertEqual(snapshot["cleanup_status"], "cleaned")
        self.assertFalse(session.temp_dir.exists())
        self.assertNotIn(
            "completed",
            [
                item["to_state"]
                for item in recovered.transitions(job_id=ticket.job_id, access=self.access)
            ],
        )

    def test_review_waiting_releases_gate1_capacity_without_false_completion(self):
        authority = self._authority()
        first = self._submit(authority, WorkloadKind.GATE1)
        second = self._submit(authority, WorkloadKind.GATE1)
        session = authority.try_admit(job_id=first.job_id, access=self.access)
        session.transition(WorkloadState.NORMALIZING)
        session.transition(WorkloadState.BUILDING_DOCUMENT_MEMORY)
        session.transition(WorkloadState.VALIDATING)
        review = session.await_review(
            safe_detail={"canonical_publication": False, "review_items": 1}
        )

        self.assertEqual(review["state"], "awaiting_review")
        self.assertIsNone(review["terminal_at"])
        second_session = authority.try_admit(job_id=second.job_id, access=self.access)
        self.assertIsNotNone(second_session)
        second_session.cancel("test_cleanup")
        unresolved = authority.resolve_review(
            job_id=first.job_id,
            access=self.access,
            decision="unresolved",
            review_receipt_ref="reviewreceipt_unresolved_1",
        )
        self.assertEqual(unresolved["state"], "awaiting_review")
        resolved = authority.resolve_review(
            job_id=first.job_id,
            access=self.access,
            decision="accepted",
            review_receipt_ref="reviewreceipt_accepted_1",
        )
        self.assertEqual(resolved["state"], "completed")
        self.assertEqual(resolved["terminal_code"], "review_accepted")

    def test_progress_is_typed_ordered_persisted_and_invalid_jump_fails_closed(self):
        authority = self._authority()
        ticket = self._submit(authority, WorkloadKind.GATE1)
        session = authority.try_admit(job_id=ticket.job_id, access=self.access)
        with self.assertRaises(WorkloadAuthorityError) as invalid:
            session.transition(WorkloadState.PREPARING_GATE2)
        self.assertEqual(invalid.exception.code, "workload_progress_transition_invalid")

        session.transition(WorkloadState.NORMALIZING, event_code="normalization_started")
        session.transition(
            WorkloadState.BUILDING_DOCUMENT_MEMORY,
            event_code="document_memory_building",
        )
        session.transition(WorkloadState.VALIDATING, event_code="validation_started")
        session.complete()
        transitions = authority.transitions(job_id=ticket.job_id, access=self.access)
        self.assertEqual(
            [item["to_state"] for item in transitions],
            [
                "queued",
                "source_intake",
                "normalizing",
                "building_document_memory",
                "validating",
                "completed",
            ],
        )
        self.assertEqual(
            [item["sequence"] for item in transitions], list(range(len(transitions)))
        )
        with closing(sqlite3.connect(self.root / "workloads.sqlite3")) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT state FROM workload_jobs WHERE job_id = ?", (ticket.job_id,)
                ).fetchone()[0],
                "completed",
            )

    def test_shared_database_rejects_capacity_contract_drift(self):
        self._authority(gate2_concurrency=2)
        with self.assertRaises(WorkloadAuthorityError) as mismatch:
            self._authority(gate2_concurrency=1)
        self.assertEqual(
            mismatch.exception.code, "workload_authority_contract_mismatch"
        )

    def test_qualified_host_limits_reject_unsafe_configuration(self):
        with self.assertRaises(WorkloadAuthorityError) as gate1:
            self._config(gate1_concurrency=2)
        self.assertEqual(gate1.exception.code, "workload_gate1_concurrency_must_equal_one")
        with self.assertRaises(WorkloadAuthorityError) as gate2:
            self._config(gate2_concurrency=3)
        self.assertEqual(gate2.exception.code, "workload_gate2_concurrency_exceeds_two")

    def test_gate1_normalizer_exposes_document_phase_cancellation_checkpoints(self):
        phases = []
        checkpoints = []
        source = FileInput(
            private_ref="private-workload-source",
            original_filename_private="workload.txt",
            mime_type="text/plain",
            bytes_provider=lambda: b"bounded workload source",
        )
        result = Gate1Normalizer().normalize(
            [source],
            workload_checkpoint=lambda: checkpoints.append("checkpoint"),
            workload_progress=lambda state, detail: phases.append((state, detail)),
        )

        self.assertEqual(
            [state for state, _ in phases],
            ["normalizing", "building_document_memory", "validating"],
        )
        self.assertGreaterEqual(len(checkpoints), 5)
        self.assertEqual(result.package["normalization_run"]["files_total"], 1)

        def cancel_at_memory(state, _detail):
            if state == "building_document_memory":
                raise WorkloadCancelledError()

        with self.assertRaises(WorkloadCancelledError):
            Gate1Normalizer().normalize(
                [source],
                workload_progress=cancel_at_memory,
            )

    def test_production_gate1_pipe_persists_visible_terminal_workload(self):
        pipe = Gate1Pipe()
        pipe.valves.artifact_store_path = str(self.root / "pipe-artifacts.sqlite3")
        pipe.valves.artifact_payload_root = str(self.root / "pipe-payloads")
        events = []

        async def emitter(event):
            events.append(event)

        content = asyncio.run(
            pipe.pipe(
                {},
                __user__={"id": self.access.user_id},
                __metadata__={
                    "case_id": self.access.case_id,
                    "chat_id": self.access.chat_id,
                    "model_id": self.access.workspace_model_id,
                },
                __event_emitter__=emitter,
            )
        )

        self.assertIsInstance(content, str)
        self.assertEqual(pipe.last_workload_snapshot["state"], "completed")
        self.assertEqual(pipe.last_workload_snapshot["cleanup_status"], "cleaned")
        self.assertTrue(
            any(
                "state: queued" in event["data"]["description"]
                for event in events
            )
        )
        self.assertTrue(
            any(
                "state: completed" in event["data"]["description"]
                for event in events
            )
        )
        authority = pipe._workload_authority()
        access = pipe._canonical_workload_access(
            WorkloadAccessContext(
                user_id=self.access.user_id,
                case_id=self.access.case_id,
                chat_id=self.access.chat_id,
                workspace_model_id=self.access.workspace_model_id,
            )
        )
        states = [
            item["to_state"]
            for item in authority.transitions(
                job_id=pipe.last_workload_job_id,
                access=access,
            )
        ]
        self.assertEqual(
            states,
            [
                "queued",
                "source_intake",
                "normalizing",
                "building_document_memory",
                "validating",
                "completed",
            ],
        )
        store = ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=Path(pipe.valves.artifact_store_path),
                payload_root=Path(pipe.valves.artifact_payload_root),
            )
        ).create()
        dcp_ref = pipe.last_artifact_manifest["artifact_refs_by_type"][
            "domain_context_packet_v0"
        ][-1]
        dcp_record = store.get_record_unchecked(dcp_ref)
        self.assertEqual(
            dcp_record.safe_metadata["workload_job_id"],
            pipe.last_workload_job_id,
        )

    def test_provider_calls_and_bundle_builder_are_authority_routed(self):
        service_root = Path(__file__).resolve().parents[1]
        gate1_pipe = (
            service_root / "openwebui_actions" / "broker_reports_gate1_pipe.py"
        ).read_text(encoding="utf-8")
        gate2_source = (
            service_root
            / "openwebui_actions"
            / "broker_reports_gate2_source_fact_pipe.py"
        ).read_text(encoding="utf-8")
        gate2_domain = (
            service_root
            / "openwebui_actions"
            / "broker_reports_gate2_domain_source_fact_pipe.py"
        ).read_text(encoding="utf-8")
        dual_runtime = (
            service_root / "broker_reports_gate1" / "pdf_dual_vlm_runtime.py"
        ).read_text(encoding="utf-8")
        gate2_source_runtime = (
            service_root / "broker_reports_gate1" / "gate2_source_fact_runtime.py"
        ).read_text(encoding="utf-8")
        gate2_domain_runtime = (
            service_root / "broker_reports_gate1" / "gate2_domain_runtime.py"
        ).read_text(encoding="utf-8")
        bundle_builder = (
            service_root / "scripts" / "build_openwebui_pipe_bundle.py"
        ).read_text(encoding="utf-8")

        self.assertIn("provider_budget=self._dual_vlm_provider_budget", gate1_pipe)
        self.assertIn("provider_slot_async", gate2_source)
        self.assertIn("provider_slot_async", gate2_domain)
        self.assertGreaterEqual(
            dual_runtime.count("with self._provider_budget_context(provider_name)"),
            2,
        )
        self.assertIn('terminal_metadata["workload_job_id"]', gate2_source_runtime)
        self.assertIn('terminal_metadata["workload_job_id"]', gate2_domain_runtime)
        self.assertIn('"workload_authority"', bundle_builder)
        for source in (gate1_pipe, gate2_source, gate2_domain):
            self.assertNotIn("asyncio.Semaphore(", source)
            self.assertNotIn("ProcessPoolExecutor(", source)
            self.assertNotIn("PaddleOCR", source)

    def test_gate2_rejects_dcp_until_owning_gate1_workload_is_completed(self):
        authority = self._authority()
        pending = self._submit(authority, WorkloadKind.GATE1)
        pending_record = SimpleNamespace(
            safe_metadata={"workload_job_id": pending.job_id}
        )

        with self.assertRaises(WorkloadAuthorityError) as not_completed:
            Gate2Pipe._assert_gate1_workload_completed(
                authority=authority,
                access=self.access,
                dcp_record=pending_record,
            )
        self.assertEqual(
            not_completed.exception.code,
            "gate1_workload_not_completed",
        )

        session = authority.try_admit(job_id=pending.job_id, access=self.access)
        session.transition(WorkloadState.NORMALIZING)
        session.transition(WorkloadState.BUILDING_DOCUMENT_MEMORY)
        session.transition(WorkloadState.VALIDATING)
        session.complete()
        Gate2Pipe._assert_gate1_workload_completed(
            authority=authority,
            access=self.access,
            dcp_record=pending_record,
        )

        with self.assertRaises(WorkloadAuthorityError) as missing:
            Gate2Pipe._assert_gate1_workload_completed(
                authority=authority,
                access=self.access,
                dcp_record=SimpleNamespace(safe_metadata={}),
            )
        self.assertEqual(missing.exception.code, "gate1_workload_receipt_missing")


if __name__ == "__main__":
    unittest.main()
