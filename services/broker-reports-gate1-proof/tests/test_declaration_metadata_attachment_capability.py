from __future__ import annotations

import hashlib
import importlib.util
import sys
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, select, text
from sqlalchemy.pool import StaticPool


ROOT = Path(__file__).resolve().parents[3]
DEPLOY_ROOT = ROOT / "deploy" / "openwebui-broker-reports-intake"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


open_webui = sys.modules.setdefault("open_webui", ModuleType("open_webui"))
routers = sys.modules.setdefault("open_webui.routers", ModuleType("open_webui.routers"))
setattr(open_webui, "routers", routers)
contract = _load(
    "open_webui.routers.broker_reports_intake_contract",
    DEPLOY_ROOT / "broker_reports_intake_contract.py",
)
capability = _load(
    "declaration_metadata_attachment_capability_test",
    DEPLOY_ROOT / "declaration_metadata_attachment_capability.py",
)


def _migrate(engine) -> None:
    migration = _load(
        "declaration_metadata_attachment_capability_migration_test",
        DEPLOY_ROOT
        / "migrations"
        / "c7a9b21d4e63_add_declaration_metadata_attachment_capability.py",
    )
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()


def _source(*, user_id: str = "user-a", payload: bytes = b"details"):
    source_sha256 = hashlib.sha256(payload).hexdigest()
    source_id = contract.deterministic_declaration_metadata_source_id(
        user_id, "metadata-0001"
    )
    receipt_id = contract._receipt_id(
        contract.DECLARATION_METADATA_RECEIPT_SCHEMA_VERSION,
        source_id,
        source_sha256,
    )
    slot_checksum = contract._declaration_metadata_slot_checksum(
        source_id=source_id,
        owner_user_id=user_id,
        source_sha256=source_sha256,
        size_bytes=len(payload),
    )
    receipt = {
        "schema_version": contract.DECLARATION_METADATA_RECEIPT_SCHEMA_VERSION,
        "source_id": source_id,
        "receipt_id": receipt_id,
        "owner_user_id": user_id,
        "source_sha256": source_sha256,
        "size_bytes": len(payload),
        "state": "eligible",
        "process": False,
        "native_openwebui_document_processing": False,
        "knowledge_allowed": False,
        "rag_allowed": False,
        "embeddings_allowed": False,
        "vectorization_allowed": False,
        "intake_slot": contract.DECLARATION_METADATA_INPUT_SLOT,
        "slot_owner": contract.DECLARATION_METADATA_SLOT_OWNER,
        "slot_checksum": slot_checksum,
        "created_at": 1_730_000_000,
        "idempotency_fingerprint": hashlib.sha256(b"idempotency").hexdigest(),
    }
    return contract.StoredSource(
        id=source_id,
        user_id=user_id,
        source_hash=source_sha256,
        filename="details.pdf",
        path=f"private://{source_id}",
        data={},
        meta={
            "file_hash": source_sha256,
            "size": len(payload),
            contract.RECEIPT_META_KEY: receipt,
        },
        created_at=1_730_000_000,
        updated_at=1_730_000_000,
    )


@pytest.fixture
def harness():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _migrate(engine)
    now = [1_730_000_010]
    owner = capability.build_declaration_metadata_attachment_capability_owner(
        engine=engine,
        signing_key=b"server-secret-that-is-at-least-32-bytes",
        clock=lambda: now[0],
    )
    return engine, now, owner


def _binding(source, **changes):
    values = {
        "actor_user_id": source.user_id,
        "source_id": source.id,
        "chat_id": "chat-1",
        "message_id": "message-1",
        "workspace_model_id": "ndfl-workspace-model",
    }
    values.update(changes)
    return capability.AttachmentBinding(**values)


def test_migration_and_fixed_issue_persist_only_token_hash(harness):
    engine, _, owner = harness
    source = _source()
    actor = contract.IntakeActor(user_id=source.user_id)

    first = owner.issue_declaration_metadata_attachment(actor=actor, source=source)
    second = owner.issue_declaration_metadata_attachment(actor=actor, source=source)

    assert first == second
    table = capability._table(engine)
    with engine.connect() as connection:
        row = connection.execute(select(table)).mappings().one()
    assert row["state"] == "PENDING"
    assert row["source_id"] == source.id
    assert row["receipt_schema_version"].endswith("receipt_v2")
    assert row["source_sha256"] == source.source_hash
    assert row["token_sha256"] == hashlib.sha256(first.token.encode()).hexdigest()
    assert first.token not in tuple(str(value) for value in row.values())


def test_consume_is_exactly_once_for_same_tuple_and_conflicts_for_other(harness):
    _, _, owner = harness
    source = _source()
    actor = contract.IntakeActor(user_id=source.user_id)
    issued = owner.issue_declaration_metadata_attachment(actor=actor, source=source)

    first = owner.consume_declaration_metadata_attachment(
        token=issued.token, actor=actor, source=source, binding=_binding(source)
    )
    replay = owner.consume_declaration_metadata_attachment(
        token=issued.token, actor=actor, source=source, binding=_binding(source)
    )

    assert first.replayed is False
    assert replay.replayed is True
    with pytest.raises(capability.AttachmentCapabilityConflict):
        owner.consume_declaration_metadata_attachment(
            token=issued.token,
            actor=actor,
            source=source,
            binding=_binding(source, message_id="message-2"),
        )


def test_forged_token_foreign_actor_and_missing_binding_fail_closed(harness):
    _, _, owner = harness
    source = _source()
    actor = contract.IntakeActor(user_id=source.user_id)
    issued = owner.issue_declaration_metadata_attachment(actor=actor, source=source)

    with pytest.raises(capability.AttachmentCapabilityConflict):
        owner.consume_declaration_metadata_attachment(
            token=issued.token + "x",
            actor=actor,
            source=source,
            binding=_binding(source),
        )
    with pytest.raises(capability.InvalidAttachmentSource):
        owner.consume_declaration_metadata_attachment(
            token=issued.token,
            actor=contract.IntakeActor(user_id="user-b"),
            source=source,
            binding=_binding(source, actor_user_id="user-b"),
        )
    with pytest.raises(capability.InvalidAttachmentBinding):
        owner.consume_declaration_metadata_attachment(
            token=issued.token,
            actor=actor,
            source=source,
            binding=_binding(source, chat_id=""),
        )


def test_recomputed_receipt_and_stale_source_cannot_consume(harness):
    _, _, owner = harness
    source = _source(payload=b"original")
    actor = contract.IntakeActor(user_id=source.user_id)
    issued = owner.issue_declaration_metadata_attachment(actor=actor, source=source)
    forged = deepcopy(source)
    forged_payload = b"replacement"
    forged_hash = hashlib.sha256(forged_payload).hexdigest()
    forged_meta = deepcopy(dict(forged.meta))
    forged_receipt = forged_meta[contract.RECEIPT_META_KEY]
    forged_meta["file_hash"] = forged_hash
    forged_meta["size"] = len(forged_payload)
    forged_receipt["source_sha256"] = forged_hash
    forged_receipt["size_bytes"] = len(forged_payload)
    forged_receipt["receipt_id"] = contract._receipt_id(
        contract.DECLARATION_METADATA_RECEIPT_SCHEMA_VERSION,
        forged.id,
        forged_hash,
    )
    forged_receipt["slot_checksum"] = contract._declaration_metadata_slot_checksum(
        source_id=forged.id,
        owner_user_id=forged.user_id,
        source_sha256=forged_hash,
        size_bytes=len(forged_payload),
    )
    forged = contract.StoredSource(
        **{**forged.__dict__, "source_hash": forged_hash, "meta": forged_meta}
    )

    with pytest.raises(capability.AttachmentCapabilityConflict):
        owner.consume_declaration_metadata_attachment(
            token=issued.token,
            actor=actor,
            source=forged,
            binding=_binding(forged),
        )


def test_rehashed_forged_token_cannot_consume(harness):
    engine, _, owner = harness
    source = _source()
    actor = contract.IntakeActor(user_id=source.user_id)
    owner.issue_declaration_metadata_attachment(actor=actor, source=source)
    forged_token = "attacker-chosen-token"
    table = capability._table(engine)
    with engine.begin() as connection:
        connection.execute(
            table.update().values(
                token_sha256=hashlib.sha256(forged_token.encode()).hexdigest()
            )
        )

    with pytest.raises(capability.AttachmentCapabilityConflict):
        owner.consume_declaration_metadata_attachment(
            token=forged_token,
            actor=actor,
            source=source,
            binding=_binding(source),
        )
    with engine.connect() as connection:
        assert connection.execute(select(table.c.state)).scalar_one() == "PENDING"


def test_expiry_is_persisted_and_blocks_consumption(harness):
    engine, now, owner = harness
    source = _source()
    actor = contract.IntakeActor(user_id=source.user_id)
    issued = owner.issue_declaration_metadata_attachment(actor=actor, source=source)
    now[0] = issued.expires_at

    with pytest.raises(capability.AttachmentCapabilityExpired):
        owner.consume_declaration_metadata_attachment(
            token=issued.token, actor=actor, source=source, binding=_binding(source)
        )
    table = capability._table(engine)
    with engine.connect() as connection:
        state = connection.execute(select(table.c.state)).scalar_one()
    assert state == "EXPIRED"


def test_database_failure_is_not_reported_as_success(harness, monkeypatch):
    _, _, owner = harness
    source = _source()
    actor = contract.IntakeActor(user_id=source.user_id)

    def fail(_values):
        raise capability.AttachmentCapabilityPersistenceFailure()

    monkeypatch.setattr(
        owner._repository,
        "persist_issued_declaration_metadata_attachment",
        fail,
    )
    with pytest.raises(capability.AttachmentCapabilityPersistenceFailure):
        owner.issue_declaration_metadata_attachment(actor=actor, source=source)


def test_consume_database_failure_rolls_back_to_pending(harness):
    engine, _, owner = harness
    source = _source()
    actor = contract.IntakeActor(user_id=source.user_id)
    issued = owner.issue_declaration_metadata_attachment(actor=actor, source=source)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TRIGGER reject_capability_consume BEFORE UPDATE ON "
                "broker_reports_declaration_metadata_attachment_capability "
                "BEGIN SELECT RAISE(ABORT, 'forced DB failure'); END"
            )
        )

    with pytest.raises(capability.AttachmentCapabilityPersistenceFailure):
        owner.consume_declaration_metadata_attachment(
            token=issued.token,
            actor=actor,
            source=source,
            binding=_binding(source),
        )
    table = capability._table(engine)
    with engine.connect() as connection:
        assert connection.execute(select(table.c.state)).scalar_one() == "PENDING"


def test_concurrent_different_bindings_have_one_winner(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'capability.db'}",
        connect_args={"check_same_thread": False},
    )
    _migrate(engine)
    owner = capability.build_declaration_metadata_attachment_capability_owner(
        engine=engine,
        signing_key=b"server-secret-that-is-at-least-32-bytes",
        clock=lambda: 1_730_000_010,
    )
    source = _source()
    actor = contract.IntakeActor(user_id=source.user_id)
    issued = owner.issue_declaration_metadata_attachment(actor=actor, source=source)

    def consume(message_id):
        try:
            return owner.consume_declaration_metadata_attachment(
                token=issued.token,
                actor=actor,
                source=source,
                binding=_binding(source, message_id=message_id),
            )
        except capability.AttachmentCapabilityConflict as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(consume, ("message-a", "message-b")))

    assert (
        sum(
            isinstance(item, capability.ConsumedAttachmentCapability)
            for item in results
        )
        == 1
    )
    assert (
        sum(isinstance(item, capability.AttachmentCapabilityConflict) for item in results)
        == 1
    )


def test_concurrent_same_issue_tuple_is_idempotent(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'issue-capability.db'}",
        connect_args={"check_same_thread": False},
    )
    _migrate(engine)
    owner = capability.build_declaration_metadata_attachment_capability_owner(
        engine=engine,
        signing_key=b"server-secret-that-is-at-least-32-bytes",
        clock=lambda: 1_730_000_010,
    )
    source = _source()
    actor = contract.IntakeActor(user_id=source.user_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _index: owner.issue_declaration_metadata_attachment(
                    actor=actor, source=source
                ),
                range(2),
            )
        )

    assert results[0] == results[1]


def test_contract_is_inactive_and_has_no_generic_or_transport_surface():
    source_path = DEPLOY_ROOT / "declaration_metadata_attachment_capability.py"
    source_text = source_path.read_text(encoding="utf-8")
    allowed_mentions = {
        source_path,
        DEPLOY_ROOT
        / "migrations"
        / "c7a9b21d4e63_add_declaration_metadata_attachment_capability.py",
        Path(__file__),
        ROOT / "deploy" / "openwebui-native-web-stt-patch" / "Dockerfile",
    }
    consumers = []
    for path in ROOT.rglob("*.py"):
        if path in allowed_mentions or any(part == ".git" for part in path.parts):
            continue
        if "declaration_metadata_attachment_capability" in path.read_text(
            encoding="utf-8", errors="ignore"
        ):
            consumers.append(path)
    assert consumers == []
    assert "def issue(" not in source_text
    assert "def consume(" not in source_text
    assert "FastAPI" not in source_text
    assert "APIRouter" not in source_text
    assert "source_policy" not in source_text
    assert "ChatFile" not in source_text
    assert "Canonical" not in source_text
