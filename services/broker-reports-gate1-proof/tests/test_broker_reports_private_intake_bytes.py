from __future__ import annotations

import hashlib
import unittest

from broker_reports_gate1.private_intake_bytes import (
    PrivateIntakeBytesError,
    PrivateIntakeBytesResolverFactory,
    PrivateIntakeFileRecord,
    PrivateIntakeVerifiedReceipt,
    is_private_intake_source_id,
)


SOURCE_ID = "br-11111111-2222-3333-4444-555555555555"
ACTOR_ID = "verified-private-intake-user"
PAYLOAD = b"synthetic receipt-owned source bytes"


class FakeRepository:
    def __init__(self, record: PrivateIntakeFileRecord | None) -> None:
        self.record = record
        self.calls: list[tuple[str, str]] = []

    async def get_owned(self, source_id: str, actor_user_id: str):
        self.calls.append((source_id, actor_user_id))
        if self.record is None or self.record.user_id != actor_user_id:
            return None
        return self.record


class FakeStorage:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.paths: list[str] = []

    async def read_bytes(self, path: str) -> bytes:
        self.paths.append(path)
        return self.payload


class FakeReceiptValidator:
    def __init__(self, payload: bytes = PAYLOAD) -> None:
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    def validate(self, record, actor_user_id: str):
        self.calls.append((record.source_id, actor_user_id))
        return PrivateIntakeVerifiedReceipt(
            source_id=record.source_id,
            source_sha256=hashlib.sha256(self.payload).hexdigest(),
            size_bytes=len(self.payload),
        )


def record(*, user_id: str = ACTOR_ID) -> PrivateIntakeFileRecord:
    return PrivateIntakeFileRecord(
        source_id=SOURCE_ID,
        user_id=user_id,
        source_hash=hashlib.sha256(PAYLOAD).hexdigest(),
        filename="synthetic.pdf",
        path="/private/intake/nonce-qualified-object",
        data={},
        meta={"broker_reports_intake": {"state": "eligible"}},
        created_at=1_720_000_000,
        updated_at=1_720_000_000,
    )


class BrokerReportsPrivateIntakeBytesTest(unittest.IsolatedAsyncioTestCase):
    def _resolver(self, *, source_record=None, storage_payload=PAYLOAD):
        repository = FakeRepository(source_record or record())
        storage = FakeStorage(storage_payload)
        validator = FakeReceiptValidator()
        resolver = PrivateIntakeBytesResolverFactory(
            repository=repository,
            storage=storage,
            receipt_validator=validator,
        ).create()
        return resolver, repository, storage, validator

    async def test_factory_resolves_only_receipt_verified_exact_bytes(self):
        resolver, repository, storage, validator = self._resolver()

        resolved = await resolver.resolve(
            source_id=SOURCE_ID,
            actor_user_id=ACTOR_ID,
        )

        self.assertEqual(resolved, PAYLOAD)
        self.assertEqual(repository.calls, [(SOURCE_ID, ACTOR_ID)])
        self.assertEqual(storage.paths, [record().path])
        self.assertEqual(validator.calls, [(SOURCE_ID, ACTOR_ID)])

    async def test_cross_owner_resolution_fails_closed_before_storage(self):
        resolver, _, storage, _ = self._resolver()

        with self.assertRaises(PrivateIntakeBytesError) as denied:
            await resolver.resolve(
                source_id=SOURCE_ID,
                actor_user_id="different-user",
            )

        self.assertEqual(denied.exception.code, "private_intake_source_not_owned")
        self.assertEqual(storage.paths, [])

    async def test_storage_hash_mismatch_fails_closed(self):
        resolver, _, _, _ = self._resolver(
            storage_payload=b"x" * len(PAYLOAD)
        )

        with self.assertRaises(PrivateIntakeBytesError) as denied:
            await resolver.resolve(source_id=SOURCE_ID, actor_user_id=ACTOR_ID)

        self.assertEqual(denied.exception.code, "private_intake_storage_hash_mismatch")

    async def test_non_reserved_source_identity_is_rejected(self):
        resolver, repository, _, _ = self._resolver()

        with self.assertRaises(PrivateIntakeBytesError) as denied:
            await resolver.resolve(
                source_id="generic-file-id",
                actor_user_id=ACTOR_ID,
            )

        self.assertEqual(denied.exception.code, "private_intake_source_id_invalid")
        self.assertEqual(repository.calls, [])
        self.assertTrue(is_private_intake_source_id(SOURCE_ID))
        self.assertFalse(is_private_intake_source_id("br-forged"))
