from __future__ import annotations

import asyncio
import ast
import hashlib
import importlib.util
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
DEPLOY_ROOT = ROOT / "deploy" / "openwebui-broker-reports-intake"


def _load_contract():
    name = "broker_reports_declaration_metadata_intake_contract_test"
    spec = importlib.util.spec_from_file_location(
        name, DEPLOY_ROOT / "broker_reports_intake_contract.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = _load_contract()


class Repository:
    def __init__(self) -> None:
        self.rows = {}
        self.lock = asyncio.Lock()

    async def get_owned(self, source_id, owner_user_id):
        row = self.rows.get(source_id)
        return row if row is not None and row.user_id == owner_user_id else None

    async def create(self, source):
        async with self.lock:
            if source.id in self.rows:
                return False
            self.rows[source.id] = source
            return True


class Storage:
    def __init__(self) -> None:
        self.objects = {}
        self.tags = {}

    async def store(self, payload, object_name, tags):
        path = f"private://{object_name}"
        self.objects[path] = payload
        self.tags[path] = dict(tags)
        return path

    async def delete(self, path):
        del self.objects[path]
        self.tags.pop(path, None)


@pytest.fixture
def intake():
    repository = Repository()
    storage = Storage()
    service = contract.BrokerReportsIntakeService(
        repository,
        storage,
        clock=lambda: 1_730_000_000,
        nonce=lambda: "attempt-fixed",
    )
    return repository, storage, service, contract.IntakeActor(user_id="user-a")


async def _accept_metadata(intake, *, key="metadata-0001", payload=b"metadata bytes"):
    _, _, service, actor = intake
    return await service.accept_declaration_metadata_input(
        actor=actor,
        idempotency_key=key,
        filename="details.pdf",
        content_type="application/pdf",
        payload=payload,
    )


@pytest.mark.asyncio
async def test_fixed_intake_persists_exact_v2_receipt_and_bytes(intake):
    repository, storage, _, actor = intake
    payload = b"declaration metadata bytes\x00exact"

    result = await _accept_metadata(intake, payload=payload)

    assert result.source_id.startswith("br-dm-")
    assert result.receipt_schema_version == (
        contract.DECLARATION_METADATA_RECEIPT_SCHEMA_VERSION
    )
    assert result.intake_slot == contract.DECLARATION_METADATA_INPUT_SLOT
    row = repository.rows[result.source_id]
    receipt = row.meta[contract.RECEIPT_META_KEY]
    assert storage.objects[row.path] == payload
    assert row.user_id == actor.user_id
    assert row.source_hash == hashlib.sha256(payload).hexdigest()
    assert row.meta["file_hash"] == row.source_hash
    assert row.meta["size"] == len(payload)
    assert receipt["owner_user_id"] == actor.user_id
    assert receipt["source_sha256"] == row.source_hash
    assert receipt["size_bytes"] == len(payload)
    assert receipt["intake_slot"] == contract.DECLARATION_METADATA_INPUT_SLOT
    assert receipt["slot_owner"] == contract.DECLARATION_METADATA_SLOT_OWNER
    assert len(receipt["slot_checksum"]) == 64
    assert result.public_dict()["owner_user_id"] == actor.user_id
    assert result.public_dict()["source_sha256"] == row.source_hash
    assert result.public_dict()["slot_checksum"] == receipt["slot_checksum"]
    assert storage.tags[row.path]["Broker-Reports-Intake"] == (
        contract.DECLARATION_METADATA_RECEIPT_SCHEMA_VERSION
    )
    assert contract.validate_receipt(row, actor.user_id) == result


@pytest.mark.asyncio
async def test_v1_public_contract_and_persisted_receipt_remain_exact(intake):
    repository, _, service, actor = intake
    result = await service.accept(
        actor=actor,
        idempotency_key="ordinary-0001",
        filename="statement.pdf",
        content_type="application/pdf",
        payload=b"ordinary bytes",
    )

    assert result.source_id == "br-c66df37e-4cca-50ce-ac51-ffe4ccfd38ec"
    assert result.source_sha256 == (
        "b2bda50d7c93491973d4e45c8a2e3fb84acc2e2f41430d5de16c7a33fdf47621"
    )
    assert result.receipt_id == (
        "da19231664df8aba98798a72e764de3476b81786da934a001b91643fbac24d7e"
    )
    assert result.public_dict() == {
        "schema_version": "broker_reports_private_source_receipt_v1",
        "source_id": result.source_id,
        "receipt_id": result.receipt_id,
        "size_bytes": len(b"ordinary bytes"),
        "process": False,
        "native_openwebui_document_processing": False,
        "knowledge_allowed": False,
        "rag_allowed": False,
        "embeddings_allowed": False,
        "vectorization_allowed": False,
        "eligible": True,
        "replayed": False,
    }
    receipt = repository.rows[result.source_id].meta[contract.RECEIPT_META_KEY]
    assert "intake_slot" not in receipt
    assert "slot_owner" not in receipt
    assert "slot_checksum" not in receipt


@pytest.mark.asyncio
async def test_fixed_and_ordinary_routes_do_not_alias_same_idempotency_key(intake):
    repository, _, service, actor = intake
    ordinary = await service.accept(
        actor=actor,
        idempotency_key="shared-key-0001",
        filename="statement.pdf",
        content_type="application/pdf",
        payload=b"same bytes",
    )
    metadata = await _accept_metadata(
        intake, key="shared-key-0001", payload=b"same bytes"
    )

    assert ordinary.source_id != metadata.source_id
    assert ordinary.source_id.startswith("br-")
    assert not ordinary.source_id.startswith("br-dm-")
    assert metadata.source_id.startswith("br-dm-")
    assert len(repository.rows) == 2


@pytest.mark.asyncio
async def test_fixed_intake_replay_is_revalidated_and_conflicting_bytes_fail(intake):
    first = await _accept_metadata(intake, key="metadata-replay-1", payload=b"first")
    replay = await _accept_metadata(intake, key="metadata-replay-1", payload=b"first")

    assert replay.source_id == first.source_id
    assert replay.receipt_id == first.receipt_id
    assert replay.replayed is True
    with pytest.raises(contract.IntakeConflict):
        await _accept_metadata(
            intake, key="metadata-replay-1", payload=b"different"
        )


@pytest.mark.asyncio
async def test_metadata_receipt_is_explicitly_ineligible_for_ordinary_action(intake):
    repository, _, _, actor = intake
    result = await _accept_metadata(intake)

    with pytest.raises(contract.IneligibleSource, match="not an ordinary"):
        await contract.resolve_receipts(
            [result.source_id], actor=actor, repository=repository
        )


@pytest.mark.parametrize(
    ("query", "headers", "multipart", "expected"),
    [
        ([], [], ["file"], []),
        (["role"], [], ["file"], ["role"]),
        ([], ["Purpose"], ["file"], ["header:Purpose"]),
        ([], ["Source-Policy"], ["file"], ["header:Source-Policy"]),
        ([], [], ["file", "role"], ["multipart:role"]),
        ([], [], ["file", "file"], ["multipart:file_count"]),
        ([], [], [], ["multipart:file_count"]),
    ],
)
def test_fixed_transport_rejects_every_assignment_channel(
    query, headers, multipart, expected
):
    assert contract.declaration_metadata_override_fields(
        query_fields=query,
        header_fields=headers,
        multipart_fields=multipart,
    ) == expected


@pytest.mark.asyncio
async def test_fixed_receipt_rejects_foreign_stale_and_resealed_slot_refs(intake):
    repository, _, _, actor = intake
    result = await _accept_metadata(intake)
    row = repository.rows[result.source_id]

    with pytest.raises(contract.IneligibleSource):
        contract.validate_receipt(row, "foreign-user")

    stale_receipt = deepcopy(row.meta[contract.RECEIPT_META_KEY])
    stale_receipt["created_at"] -= 1
    stale = replace(row, meta={**row.meta, contract.RECEIPT_META_KEY: stale_receipt})
    with pytest.raises(contract.IneligibleSource):
        contract.validate_receipt(stale, actor.user_id)

    forged_receipt = deepcopy(row.meta[contract.RECEIPT_META_KEY])
    forged_receipt["intake_slot"] = "BROKER_REPORT_INPUT"
    forged_receipt["receipt_id"] = hashlib.sha256(
        (
            f"{forged_receipt['schema_version']}\x00{row.id}\x00"
            f"{forged_receipt['source_sha256']}"
        ).encode()
    ).hexdigest()
    forged_receipt["slot_checksum"] = hashlib.sha256(
        (
            f"{forged_receipt['schema_version']}\x00{row.id}\x00{actor.user_id}\x00"
            f"{forged_receipt['source_sha256']}\x00{forged_receipt['size_bytes']}\x00"
            f"{forged_receipt['intake_slot']}\x00{forged_receipt['slot_owner']}"
        ).encode()
    ).hexdigest()
    forged = replace(row, meta={**row.meta, contract.RECEIPT_META_KEY: forged_receipt})
    with pytest.raises(contract.IneligibleSource, match="intake_slot"):
        contract.validate_receipt(forged, actor.user_id)


def test_router_has_one_fixed_method_and_no_client_role_arguments():
    router_path = DEPLOY_ROOT / "broker_reports_intake.py"
    source = router_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "accept_declaration_metadata_input"
    )
    parameters = {argument.arg for argument in function.args.args}

    assert parameters == {"request", "file", "idempotency_key", "user", "db"}
    block = ast.get_source_segment(source, function) or ""
    assert ".accept_declaration_metadata_input(" in block
    assert "await _declaration_metadata_override_fields(request)" in block
    assert "DECLARATION_METADATA_INTAKE_SCHEMA_VERSION" in block
    assert "source_policy=" not in block
    assert "purpose=" not in block
    assert "role=" not in block
    assert '@router.post("/declaration-metadata-intake")' in source


def test_slice_is_inactive_outside_router_and_loader_composition_root():
    forbidden_roots = [
        ROOT / "services" / "broker-reports-gate1-proof" / "broker_reports_gate1",
        ROOT / "services" / "broker-reports-gate1-proof" / "openwebui_actions",
    ]
    needle = "DECLARATION_METADATA_RECEIPT_SCHEMA_VERSION"
    matches = []
    for root in forbidden_roots:
        for path in root.rglob("*.py"):
            if needle in path.read_text(encoding="utf-8"):
                matches.append(path.relative_to(ROOT).as_posix())
    assert matches == []
