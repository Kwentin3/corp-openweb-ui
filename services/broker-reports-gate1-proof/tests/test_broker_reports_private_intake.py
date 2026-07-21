from __future__ import annotations

import asyncio
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEPLOY_ROOT = REPO_ROOT / "deploy" / "openwebui-broker-reports-intake"
sys.path.insert(0, str(SERVICE_ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load_module(
    "broker_reports_intake_contract_test",
    DEPLOY_ROOT / "broker_reports_intake_contract.py",
)
patcher = load_module(
    "apply_broker_reports_intake_patch_test",
    DEPLOY_ROOT / "apply_broker_reports_intake_patch.py",
)

from openwebui_actions.broker_reports_private_intake_action import (  # noqa: E402
    ACTION_ATTESTATION_KEY,
    PROTECTED_ACTION_ID,
    Action,
)


class InMemoryReceiptRepository:
    """Explicit database boundary fake; the intake service itself remains real."""

    def __init__(self) -> None:
        self.rows: dict[str, object] = {}
        self._create_lock = asyncio.Lock()

    async def get_owned(self, source_id: str, owner_user_id: str):
        row = self.rows.get(source_id)
        return row if row is not None and row.user_id == owner_user_id else None

    async def create(self, source) -> bool:
        async with self._create_lock:
            if source.id in self.rows:
                return False
            self.rows[source.id] = source
            return True


class ConcurrentFirstReadRepository(InMemoryReceiptRepository):
    def __init__(self) -> None:
        super().__init__()
        self._initial_reads = 0
        self._both_read = asyncio.Event()

    async def get_owned(self, source_id: str, owner_user_id: str):
        if not self.rows and self._initial_reads < 2:
            self._initial_reads += 1
            if self._initial_reads == 2:
                self._both_read.set()
            await self._both_read.wait()
            return None
        return await super().get_owned(source_id, owner_user_id)


class InMemoryPrivateStorage:
    """Explicit storage boundary fake with observable writes and compensation."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.store_calls = 0
        self.delete_calls = 0

    async def store(self, payload: bytes, object_name: str, tags) -> str:
        self.store_calls += 1
        path = f"private://{object_name}"
        self.objects[path] = payload
        return path

    async def delete(self, path: str) -> None:
        self.delete_calls += 1
        if path not in self.objects:
            raise RuntimeError("storage object is absent")
        del self.objects[path]


class FailingCreateRepository(InMemoryReceiptRepository):
    async def create(self, source) -> bool:
        raise RuntimeError("synthetic database failure")


class FailingDeleteStorage(InMemoryPrivateStorage):
    async def delete(self, path: str) -> None:
        self.delete_calls += 1
        raise RuntimeError("synthetic storage deletion failure")


class BrokerReportsPrivateIntakeContractTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.repository = InMemoryReceiptRepository()
        self.storage = InMemoryPrivateStorage()
        self.service = contract.BrokerReportsIntakeService(
            self.repository,
            self.storage,
            clock=lambda: 1_720_000_000,
            nonce=lambda: "attempt-a",
        )
        self.actor = contract.IntakeActor(user_id="verified-user-1")

    async def test_intake_persists_server_receipt_without_native_artifacts(self):
        result = await self.service.accept(
            actor=self.actor,
            idempotency_key="request-0001",
            filename="statement.pdf",
            content_type="application/pdf",
            payload=b"synthetic private broker source",
        )

        self.assertFalse(result.replayed)
        self.assertTrue(result.source_id.startswith("br-"))
        self.assertEqual(self.storage.store_calls, 1)
        row = self.repository.rows[result.source_id]
        receipt = row.meta[contract.RECEIPT_META_KEY]
        self.assertEqual(row.data, {})
        self.assertFalse(receipt["process"])
        self.assertFalse(receipt["native_openwebui_document_processing"])
        self.assertFalse(receipt["knowledge_allowed"])
        self.assertFalse(receipt["rag_allowed"])
        self.assertFalse(receipt["embeddings_allowed"])
        self.assertFalse(receipt["vectorization_allowed"])
        self.assertNotIn("collection_name", row.meta)
        self.assertNotIn("content", row.data)
        self.assertEqual(
            contract.validate_receipt(row, self.actor.user_id).receipt_id,
            result.receipt_id,
        )

    async def test_retry_is_reload_safe_and_does_not_write_storage_twice(self):
        first = await self.service.accept(
            actor=self.actor,
            idempotency_key="request-0002",
            filename="statement.csv",
            content_type="text/csv",
            payload=b"a,b\n1,2\n",
        )
        second = await self.service.accept(
            actor=self.actor,
            idempotency_key="request-0002",
            filename="renamed-by-client.csv",
            content_type="text/csv",
            payload=b"a,b\n1,2\n",
        )

        self.assertEqual(second.source_id, first.source_id)
        self.assertEqual(second.receipt_id, first.receipt_id)
        self.assertTrue(second.replayed)
        self.assertEqual(self.storage.store_calls, 1)
        self.assertEqual(len(self.repository.rows), 1)

    async def test_idempotency_key_cannot_be_reused_for_different_bytes(self):
        await self.service.accept(
            actor=self.actor,
            idempotency_key="request-0003",
            filename="statement.csv",
            content_type="text/csv",
            payload=b"first",
        )

        with self.assertRaises(contract.IntakeConflict):
            await self.service.accept(
                actor=self.actor,
                idempotency_key="request-0003",
                filename="statement.csv",
                content_type="text/csv",
                payload=b"different",
            )
        self.assertEqual(self.storage.store_calls, 1)
        self.assertEqual(len(self.repository.rows), 1)

    async def test_database_failure_compensates_storage_and_never_returns_success(self):
        repository = FailingCreateRepository()
        storage = InMemoryPrivateStorage()
        service = contract.BrokerReportsIntakeService(
            repository,
            storage,
            clock=lambda: 1_720_000_000,
            nonce=lambda: "attempt-db-failure",
        )

        with self.assertRaisesRegex(RuntimeError, "synthetic database failure"):
            await service.accept(
                actor=self.actor,
                idempotency_key="request-0005",
                filename="statement.pdf",
                content_type="application/pdf",
                payload=b"synthetic failure source",
            )
        self.assertEqual(storage.store_calls, 1)
        self.assertEqual(storage.delete_calls, 1)
        self.assertEqual(storage.objects, {})
        self.assertEqual(repository.rows, {})

    async def test_failed_compensation_is_terminal_error_not_false_success(self):
        repository = FailingCreateRepository()
        storage = FailingDeleteStorage()
        service = contract.BrokerReportsIntakeService(
            repository,
            storage,
            clock=lambda: 1_720_000_000,
            nonce=lambda: "attempt-cleanup-failure",
        )

        with self.assertRaises(contract.IntakeCleanupFailure):
            await service.accept(
                actor=self.actor,
                idempotency_key="request-0006",
                filename="statement.pdf",
                content_type="application/pdf",
                payload=b"synthetic cleanup failure source",
            )
        self.assertEqual(storage.store_calls, 1)
        self.assertEqual(storage.delete_calls, 1)
        self.assertEqual(repository.rows, {})

    async def test_concurrent_same_request_has_one_row_and_compensates_loser(self):
        repository = ConcurrentFirstReadRepository()
        storage = InMemoryPrivateStorage()
        service_a = contract.BrokerReportsIntakeService(
            repository,
            storage,
            clock=lambda: 1_720_000_000,
            nonce=lambda: "attempt-a",
        )
        service_b = contract.BrokerReportsIntakeService(
            repository,
            storage,
            clock=lambda: 1_720_000_000,
            nonce=lambda: "attempt-b",
        )
        command = {
            "actor": self.actor,
            "idempotency_key": "request-0004",
            "filename": "statement.xlsx",
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "payload": b"synthetic workbook bytes",
        }

        first, second = await asyncio.gather(
            service_a.accept(**command),
            service_b.accept(**command),
        )

        self.assertEqual(first.source_id, second.source_id)
        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertEqual(sorted([first.replayed, second.replayed]), [False, True])
        self.assertEqual(len(repository.rows), 1)
        self.assertEqual(storage.store_calls, 2)
        self.assertEqual(storage.delete_calls, 1)
        self.assertEqual(len(storage.objects), 1)

    async def test_generic_or_client_nested_receipt_is_ineligible_and_rag_guard_is_closed(self):
        generic = contract.StoredSource(
            id="generic-file-id",
            user_id=self.actor.user_id,
            source_hash="a" * 64,
            filename="generic.pdf",
            path="private://generic.pdf",
            data={},
            meta={
                "file_hash": "a" * 64,
                "data": {contract.RECEIPT_META_KEY: {"schema_version": "client-forged"}},
            },
            created_at=1,
            updated_at=1,
        )
        self.repository.rows[generic.id] = generic

        with self.assertRaises(contract.IneligibleSource):
            await contract.resolve_receipts(
                [generic.id],
                actor=self.actor,
                repository=self.repository,
            )

        malformed_reserved = contract.StoredSource(
            **{**generic.__dict__, "id": "br-malformed", "meta": {}}
        )
        with self.assertRaises(contract.NativeProcessingForbidden):
            contract.assert_native_processing_allowed(malformed_reserved)


class BrokerReportsPrivateIntakeActionTest(unittest.IsolatedAsyncioTestCase):
    async def test_action_rejects_generic_file_refs_without_server_attestation(self):
        with self.assertRaisesRegex(ValueError, "Generic OpenWebUI file refs are ineligible"):
            await Action().action(
                {"files": [{"id": "generic-file-id"}]},
                __id__=PROTECTED_ACTION_ID,
            )

    async def test_action_accepts_only_server_attestation_and_hides_source_ids(self):
        repository = InMemoryReceiptRepository()
        storage = InMemoryPrivateStorage()
        result = await contract.BrokerReportsIntakeService(
            repository,
            storage,
            clock=lambda: 1_720_000_000,
            nonce=lambda: "attempt-action",
        ).accept(
            actor=contract.IntakeActor(user_id="verified-user-action"),
            idempotency_key="request-action-1",
            filename="private.pdf",
            content_type="application/pdf",
            payload=b"private action source",
        )
        body = {
            "files": [{"id": result.source_id}],
            ACTION_ATTESTATION_KEY: contract.action_attestation([result]),
        }

        response = await Action().action(body, __id__=PROTECTED_ACTION_ID)

        report = response["broker_reports_private_intake"]
        self.assertEqual(report["run_status"], "receipt_verified")
        self.assertEqual(report["eligible_sources_total"], 1)
        self.assertNotIn(result.source_id, response["content"])
        self.assertNotIn(result.receipt_id, response["content"])
        self.assertFalse(report["documents"][0]["native_processing"])
        self.assertFalse(report["documents"][0]["knowledge_rag_vectorization"])


class BrokerReportsOpenWebUIPatchTest(unittest.TestCase):
    def _make_backend_fixture(self, root: Path) -> None:
        (root / "routers").mkdir(parents=True)
        grouped: dict[str, list[str]] = {}
        for replacement in patcher.REPLACEMENTS:
            grouped.setdefault(replacement.path, []).append(replacement.old)
        for relative_path, anchors in grouped.items():
            path = root / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n\n".join(anchors), encoding="utf-8")
        shutil.copyfile(
            DEPLOY_ROOT / "broker_reports_intake.py",
            root / "routers" / "broker_reports_intake.py",
        )
        shutil.copyfile(
            DEPLOY_ROOT / "broker_reports_intake_contract.py",
            root / "routers" / "broker_reports_intake_contract.py",
        )

    def test_patch_is_atomic_idempotent_and_wires_all_authority_hooks(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._make_backend_fixture(root)

            self.assertEqual(patcher.patch_backend(root, dry_run=False), "patched")
            self.assertEqual(
                patcher.patch_backend(root, dry_run=False),
                "already_patched",
            )
            main = (root / "main.py").read_text(encoding="utf-8")
            retrieval = (root / "routers" / "retrieval.py").read_text(encoding="utf-8")

        self.assertIn("broker_reports_intake.router", main)
        self.assertIn("guard_protected_action_form", main)
        self.assertIn("db: AsyncSession = Depends(get_async_session)", main)
        self.assertEqual(retrieval.count("assert_native_processing_allowed"), 2)
        self.assertIn("assert_native_processing_allowed(db_file)", retrieval)

    def test_patch_fails_closed_on_upstream_signature_drift(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._make_backend_fixture(root)
            main_path = root / "main.py"
            main_path.write_text(
                main_path.read_text(encoding="utf-8").replace(
                    "async def chat_action(request: Request",
                    "async def changed_chat_action(request: Request",
                    1,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "unexpected signature counts"):
                patcher.patch_backend(root, dry_run=False)

    def test_deployed_intake_has_no_native_pipeline_dependency(self):
        router_text = (DEPLOY_ROOT / "broker_reports_intake.py").read_text(encoding="utf-8")
        dockerfile = (
            REPO_ROOT / "deploy" / "openwebui-native-web-stt-patch" / "Dockerfile"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "ASYNC_VECTOR_DB_CLIENT",
            "process_uploaded_file",
            "open_webui.models.knowledge",
            "open_webui.routers.retrieval",
        ):
            self.assertNotIn(forbidden, router_text)
        self.assertIn(
            "broker_reports_intake_contract.py /app/backend/open_webui/routers/",
            dockerfile,
        )
        self.assertIn("apply_broker_reports_intake_patch.py --backend-root", dockerfile)
        self.assertIn("get_action_chat_source_ids", router_text)
        self.assertIn("Chat.user_id == owner_user_id", router_text)
        self.assertIn("ChatMessage.parent_id", router_text)
        self.assertIn("ChatFile.user_id == owner_user_id", router_text)


if __name__ == "__main__":
    unittest.main()
