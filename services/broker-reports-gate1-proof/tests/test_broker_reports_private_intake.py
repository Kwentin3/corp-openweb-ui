from __future__ import annotations

import asyncio
import ast
import importlib.util
import shutil
import sys
import tempfile
import time
import types
import unittest
from copy import deepcopy
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEPLOY_ROOT = REPO_ROOT / "deploy" / "openwebui-broker-reports-intake"
sys.path.insert(0, str(SERVICE_ROOT))

TEST_SERVER_SECRET = "unit-test-broker-intake-secret-32-bytes-minimum"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


open_webui_module = types.ModuleType("open_webui")
open_webui_module.__path__ = []
routers_module = types.ModuleType("open_webui.routers")
routers_module.__path__ = []
env_module = types.ModuleType("open_webui.env")
env_module.WEBUI_SECRET_KEY = TEST_SERVER_SECRET
sys.modules["open_webui"] = open_webui_module
sys.modules["open_webui.routers"] = routers_module
sys.modules["open_webui.env"] = env_module

contract = load_module(
    "open_webui.routers.broker_reports_intake_contract",
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
    async def asyncSetUp(self) -> None:
        self.repository = InMemoryReceiptRepository()
        self.storage = InMemoryPrivateStorage()
        self.actor = contract.IntakeActor(user_id="verified-user-action")
        self.result = await contract.BrokerReportsIntakeService(
            self.repository,
            self.storage,
            clock=lambda: 1_720_000_000,
            nonce=lambda: "attempt-action",
        ).accept(
            actor=self.actor,
            idempotency_key="request-action-1",
            filename="private.pdf",
            content_type="application/pdf",
            payload=b"private action source",
        )

    def _signed_attestation(self, *, issued_at: int | None = None) -> dict:
        return contract.action_attestation(
            [self.result],
            actor=self.actor,
            server_secret=TEST_SERVER_SECRET,
            issued_at=int(time.time()) if issued_at is None else issued_at,
            nonce="0123456789abcdef0123456789abcdef",
        )

    async def test_action_rejects_generic_file_refs_without_server_attestation(self):
        events: list[dict] = []

        async def emit(event: dict) -> None:
            events.append(event)

        with self.assertRaisesRegex(
            contract.IneligibleSource,
            "Signed server intake attestation is required",
        ):
            await Action().action(
                {"files": [{"id": "generic-file-id"}]},
                __id__=PROTECTED_ACTION_ID,
                __user__={"id": self.actor.user_id},
                __event_emitter__=emit,
            )
        self.assertEqual(events[-1]["data"]["done"], True)
        self.assertIn("rejected", events[-1]["data"]["description"].lower())

    async def test_direct_action_rejects_shape_only_client_forgery(self):
        issued_at = int(time.time())
        forged = {
            "schema_version": contract.ACTION_ATTESTATION_SCHEMA_VERSION,
            "guard": contract.FACTORY_REQUIRED,
            "action_id": PROTECTED_ACTION_ID,
            "actor_user_id": self.actor.user_id,
            "issued_at": issued_at,
            "expires_at": issued_at + contract.ACTION_ATTESTATION_TTL_SECONDS,
            "nonce": "0123456789abcdef0123456789abcdef",
            "sources": [
                {
                    "source_id": self.result.source_id,
                    "receipt_id": self.result.receipt_id,
                    "receipt_schema_version": contract.RECEIPT_SCHEMA_VERSION,
                }
            ],
            "signature": "0" * 64,
        }
        with self.assertRaisesRegex(contract.IneligibleSource, "signature is invalid"):
            await Action().action(
                {ACTION_ATTESTATION_KEY: forged},
                __id__=PROTECTED_ACTION_ID,
                __user__={"id": self.actor.user_id},
            )

    async def test_action_rejects_cross_user_and_expired_attestations(self):
        signed = self._signed_attestation()
        with self.assertRaisesRegex(contract.IneligibleSource, "actor does not match"):
            await Action().action(
                {ACTION_ATTESTATION_KEY: signed},
                __id__=PROTECTED_ACTION_ID,
                __user__={"id": "different-authenticated-user"},
            )

        expired = self._signed_attestation(
            issued_at=int(time.time()) - contract.ACTION_ATTESTATION_TTL_SECONDS - 1
        )
        with self.assertRaisesRegex(contract.IneligibleSource, "not currently valid"):
            await Action().action(
                {ACTION_ATTESTATION_KEY: expired},
                __id__=PROTECTED_ACTION_ID,
                __user__={"id": self.actor.user_id},
            )

    async def test_action_rejects_tampered_signed_source(self):
        signed = self._signed_attestation()
        tampered = deepcopy(signed)
        tampered["sources"][0]["receipt_id"] = "f" * 64
        with self.assertRaisesRegex(contract.IneligibleSource, "signature is invalid"):
            await Action().action(
                {ACTION_ATTESTATION_KEY: tampered},
                __id__=PROTECTED_ACTION_ID,
                __user__={"id": self.actor.user_id},
            )

    async def test_action_accepts_signed_server_attestation_and_hides_source_ids(self):
        events: list[dict] = []

        async def emit(event: dict) -> None:
            events.append(event)

        body = {
            "files": [{"id": self.result.source_id}],
            ACTION_ATTESTATION_KEY: self._signed_attestation(),
        }

        response = await Action().action(
            body,
            __id__=PROTECTED_ACTION_ID,
            __user__={"id": self.actor.user_id},
            __event_emitter__=emit,
        )

        report = response["broker_reports_private_intake"]
        self.assertEqual(report["run_status"], "receipt_verified")
        self.assertEqual(report["eligible_sources_total"], 1)
        self.assertNotIn(self.result.source_id, response["content"])
        self.assertNotIn(self.result.receipt_id, response["content"])
        self.assertFalse(report["documents"][0]["native_processing"])
        self.assertFalse(report["documents"][0]["knowledge_rag_vectorization"])
        self.assertEqual([event["data"]["done"] for event in events], [False, True])

    async def test_short_server_secret_fails_closed(self):
        with self.assertRaises(contract.IntakeConfigurationFailure):
            contract.action_attestation(
                [self.result],
                actor=self.actor,
                server_secret="short",
                issued_at=int(time.time()),
                nonce="0123456789abcdef0123456789abcdef",
            )


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
            files = (root / "routers" / "files.py").read_text(encoding="utf-8")
            knowledge = (root / "routers" / "knowledge.py").read_text(encoding="utf-8")

        self.assertIn("broker_reports_intake.router", main)
        self.assertIn("guard_protected_action_form", main)
        self.assertIn("db: AsyncSession = Depends(get_async_session)", main)
        self.assertEqual(retrieval.count("assert_native_processing_allowed"), 2)
        self.assertIn("assert_native_processing_allowed(db_file)", retrieval)
        self.assertEqual(files.count("assert_native_processing_allowed"), 1)
        self.assertEqual(knowledge.count("assert_native_processing_allowed"), 3)
        self.assertIn("reject the whole", knowledge)

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
        action_text = (
            SERVICE_ROOT
            / "openwebui_actions"
            / "broker_reports_private_intake_action.py"
        ).read_text(encoding="utf-8")
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
        self.assertIn("WEBUI_SECRET_KEY", router_text)
        self.assertIn("server_secret=WEBUI_SECRET_KEY", router_text)
        self.assertIn("Chat.user_id == owner_user_id", router_text)
        self.assertIn("ChatMessage.parent_id", router_text)
        self.assertIn("ChatFile.user_id == owner_user_id", router_text)
        self.assertIn(
            "from open_webui.routers.broker_reports_intake_contract import",
            action_text,
        )
        self.assertIn("verify_action_attestation", action_text)
        self.assertNotIn("broker_reports_private_intake_factory_v1", action_text)

    def test_delivery_assets_cover_image_action_and_terminal_live_proof(self):
        scripts = SERVICE_ROOT / "scripts"
        image_delivery = scripts / "live_deliver_broker_reports_private_intake_image.py"
        action_delivery = scripts / "live_update_broker_reports_private_intake_action.py"
        live_smoke = scripts / "live_broker_reports_private_intake_smoke.py"
        texts = {
            path.name: path.read_text(encoding="utf-8")
            for path in (image_delivery, action_delivery, live_smoke)
        }
        for name, text in texts.items():
            ast.parse(text, filename=name)

        self.assertIn("compose_up(rollback_image)", texts[image_delivery.name])
        self.assertIn("persist_image(original_env, IMAGE)", texts[image_delivery.name])
        self.assertIn("delivery_image_revision_mismatch", texts[image_delivery.name])
        self.assertIn("api/v1/auths/signin", texts[image_delivery.name])
        self.assertIn("content_hash_exact", texts[action_delivery.name])
        self.assertIn("function_type_action", texts[action_delivery.name])
        self.assertIn("private_action_receipt_verified", texts[live_smoke.name])
        self.assertIn("knowledge_delta_zero", texts[live_smoke.name])
        self.assertIn("vector_metadata_refs_zero", texts[live_smoke.name])
        self.assertIn("private_source_deleted", texts[live_smoke.name])
        self.assertIn("_create_temporary_knowledge", texts[live_smoke.name])
        self.assertIn("_cleanup_call", texts[live_smoke.name])
        self.assertNotIn('"/api/v1/knowledge/create"', texts[live_smoke.name])


if __name__ == "__main__":
    unittest.main()
