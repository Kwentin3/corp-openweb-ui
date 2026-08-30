"""Inactive server-only declaration-metadata attachment capability.

The owner has two fixed operations: issue for a verified declaration metadata
source and consume for one trusted chat binding.  No transport imports this
module yet.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from sqlalchemy import MetaData, Table, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from open_webui.routers.broker_reports_intake_contract import (
    DECLARATION_METADATA_INPUT_SLOT,
    DECLARATION_METADATA_RECEIPT_SCHEMA_VERSION,
    IneligibleSource,
    IntakeActor,
    StoredSource,
    validate_receipt,
)


CAPABILITY_SCHEMA_VERSION = (
    "broker_reports_declaration_metadata_attachment_capability_v1"
)
CAPABILITY_TTL_SECONDS = 600
FACTORY_REQUIRED = "declaration_metadata_attachment_capability_factory_v1"
TABLE_NAME = "broker_reports_declaration_metadata_attachment_capability"

_TOKEN_CONTEXT = b"broker-reports-declaration-metadata-attachment-v1"
_metadata = MetaData()


class CapabilityState(str, Enum):
    PENDING = "PENDING"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


class AttachmentCapabilityError(RuntimeError):
    code = "declaration_metadata_attachment_capability_error"


class InvalidAttachmentSource(AttachmentCapabilityError):
    code = "declaration_metadata_attachment_source_invalid"


class InvalidAttachmentBinding(AttachmentCapabilityError):
    code = "declaration_metadata_attachment_binding_invalid"


class AttachmentCapabilityConflict(AttachmentCapabilityError):
    code = "declaration_metadata_attachment_capability_conflict"


class AttachmentCapabilityExpired(AttachmentCapabilityError):
    code = "declaration_metadata_attachment_capability_expired"


class AttachmentCapabilityPersistenceFailure(AttachmentCapabilityError):
    code = "declaration_metadata_attachment_capability_persistence_failed"


@dataclass(frozen=True)
class AttachmentBinding:
    """Server-verified identity of the actual native attachment."""

    actor_user_id: str
    source_id: str
    chat_id: str
    message_id: str
    workspace_model_id: str


@dataclass(frozen=True)
class IssuedAttachmentCapability:
    capability_id: str
    token: str
    state: CapabilityState
    expires_at: int


@dataclass(frozen=True)
class ConsumedAttachmentCapability:
    capability_id: str
    source_id: str
    chat_id: str
    message_id: str
    workspace_model_id: str
    consumed_at: int
    replayed: bool
    state: CapabilityState = CapabilityState.CONSUMED


def _table(engine: Engine) -> Table:
    return Table(TABLE_NAME, _metadata, autoload_with=engine, extend_existing=True)


def _required(value: str, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise InvalidAttachmentBinding(f"{field} is required.")
    return normalized


def _source_material(
    *, actor_user_id: str, source_id: str, receipt_id: str, source_sha256: str
) -> bytes:
    return json.dumps(
        {
            "actor_user_id": actor_user_id,
            "receipt_id": receipt_id,
            "schema_version": CAPABILITY_SCHEMA_VERSION,
            "source_id": source_id,
            "source_sha256": source_sha256,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _binding_hash(binding: AttachmentBinding) -> str:
    return hashlib.sha256(
        "\x00".join(
            (
                CAPABILITY_SCHEMA_VERSION,
                binding.actor_user_id,
                binding.source_id,
                binding.chat_id,
                binding.message_id,
                binding.workspace_model_id,
            )
        ).encode()
    ).hexdigest()


def _token_for_material(signing_key: bytes, material: bytes) -> str:
    return base64.urlsafe_b64encode(
        hmac.new(
            signing_key,
            _TOKEN_CONTEXT + b"\x00" + material,
            hashlib.sha256,
        ).digest()
    ).rstrip(b"=").decode()


class SqlAlchemyAttachmentCapabilityRepository:
    """One feature-owned table; each mutation is one real DB transaction."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._table = _table(engine)

    def persist_issued_declaration_metadata_attachment(
        self, values: dict[str, object]
    ) -> dict[str, object]:
        try:
            with self._engine.begin() as connection:
                existing = connection.execute(
                    select(self._table).where(
                        self._table.c.capability_id == values["capability_id"]
                    )
                ).mappings().one_or_none()
                if existing is None:
                    connection.execute(self._table.insert().values(**values))
                    return values
                return dict(existing)
        except IntegrityError as exc:
            try:
                with self._engine.connect() as connection:
                    existing = connection.execute(
                        select(self._table).where(
                            self._table.c.capability_id == values["capability_id"]
                        )
                    ).mappings().one_or_none()
            except SQLAlchemyError as lookup_exc:
                raise AttachmentCapabilityPersistenceFailure() from lookup_exc
            if existing is not None:
                return dict(existing)
            raise AttachmentCapabilityConflict() from exc
        except SQLAlchemyError as exc:
            raise AttachmentCapabilityPersistenceFailure() from exc

    def find_declaration_metadata_attachment_by_token_hash(
        self, token_sha256: str
    ) -> dict[str, object] | None:
        try:
            with self._engine.connect() as connection:
                row = connection.execute(
                    select(self._table).where(
                        self._table.c.token_sha256 == token_sha256
                    )
                ).mappings().one_or_none()
                return dict(row) if row is not None else None
        except SQLAlchemyError as exc:
            raise AttachmentCapabilityPersistenceFailure() from exc

    def expire_pending_declaration_metadata_attachment(
        self, capability_id: str
    ) -> None:
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    update(self._table)
                    .where(
                        self._table.c.capability_id == capability_id,
                        self._table.c.state == CapabilityState.PENDING.value,
                    )
                    .values(state=CapabilityState.EXPIRED.value)
                )
        except SQLAlchemyError as exc:
            raise AttachmentCapabilityPersistenceFailure() from exc

    def consume_pending_declaration_metadata_attachment(
        self,
        *,
        capability_id: str,
        binding: AttachmentBinding,
        binding_sha256: str,
        consumed_at: int,
    ) -> dict[str, object]:
        try:
            with self._engine.begin() as connection:
                result = connection.execute(
                    update(self._table)
                    .where(
                        self._table.c.capability_id == capability_id,
                        self._table.c.state == CapabilityState.PENDING.value,
                        self._table.c.expires_at > consumed_at,
                    )
                    .values(
                        state=CapabilityState.CONSUMED.value,
                        chat_id=binding.chat_id,
                        message_id=binding.message_id,
                        workspace_model_id=binding.workspace_model_id,
                        binding_sha256=binding_sha256,
                        consumed_at=consumed_at,
                    )
                )
                row = connection.execute(
                    select(self._table).where(
                        self._table.c.capability_id == capability_id
                    )
                ).mappings().one()
                if result.rowcount not in (0, 1):
                    raise AttachmentCapabilityPersistenceFailure()
                return dict(row)
        except IntegrityError as exc:
            try:
                with self._engine.connect() as connection:
                    duplicate = connection.execute(
                        select(self._table.c.capability_id).where(
                            self._table.c.binding_sha256 == binding_sha256
                        )
                    ).first()
            except SQLAlchemyError as lookup_exc:
                raise AttachmentCapabilityPersistenceFailure() from lookup_exc
            if duplicate is not None:
                raise AttachmentCapabilityConflict() from exc
            raise AttachmentCapabilityPersistenceFailure() from exc
        except AttachmentCapabilityPersistenceFailure:
            raise
        except SQLAlchemyError as exc:
            raise AttachmentCapabilityPersistenceFailure() from exc


class DeclarationMetadataAttachmentCapabilityOwner:
    def __init__(
        self,
        *,
        repository: SqlAlchemyAttachmentCapabilityRepository,
        signing_key: bytes,
        clock: Callable[[], int],
    ) -> None:
        if len(signing_key) < 32:
            raise ValueError("signing_key must contain at least 32 bytes")
        self._repository = repository
        self._signing_key = bytes(signing_key)
        self._clock = clock

    def issue_declaration_metadata_attachment(
        self, *, actor: IntakeActor, source: StoredSource
    ) -> IssuedAttachmentCapability:
        try:
            receipt = validate_receipt(source, actor.user_id)
        except IneligibleSource as exc:
            raise InvalidAttachmentSource() from exc
        if (
            receipt.receipt_schema_version
            != DECLARATION_METADATA_RECEIPT_SCHEMA_VERSION
            or receipt.intake_slot != DECLARATION_METADATA_INPUT_SLOT
            or receipt.owner_user_id != actor.user_id
        ):
            raise InvalidAttachmentSource()
        material = _source_material(
            actor_user_id=actor.user_id,
            source_id=receipt.source_id,
            receipt_id=receipt.receipt_id,
            source_sha256=receipt.source_sha256,
        )
        capability_id = "br-dmac-" + hashlib.sha256(material).hexdigest()
        token = _token_for_material(self._signing_key, material)
        token_sha256 = hashlib.sha256(token.encode()).hexdigest()
        issued_at = int(self._clock())
        candidate = {
            "capability_id": capability_id,
            "schema_version": CAPABILITY_SCHEMA_VERSION,
            "token_sha256": token_sha256,
            "actor_user_id": actor.user_id,
            "source_id": receipt.source_id,
            "receipt_schema_version": receipt.receipt_schema_version,
            "receipt_id": receipt.receipt_id,
            "source_sha256": receipt.source_sha256,
            "intake_slot": receipt.intake_slot,
            "state": CapabilityState.PENDING.value,
            "issued_at": issued_at,
            "expires_at": issued_at + CAPABILITY_TTL_SECONDS,
            "chat_id": None,
            "message_id": None,
            "workspace_model_id": None,
            "binding_sha256": None,
            "consumed_at": None,
        }
        row = self._repository.persist_issued_declaration_metadata_attachment(candidate)
        immutable = (
            "schema_version",
            "token_sha256",
            "actor_user_id",
            "source_id",
            "receipt_schema_version",
            "receipt_id",
            "source_sha256",
            "intake_slot",
        )
        if any(row.get(field) != candidate[field] for field in immutable):
            raise AttachmentCapabilityConflict()
        return IssuedAttachmentCapability(
            capability_id=capability_id,
            token=token,
            state=CapabilityState(str(row["state"])),
            expires_at=int(row["expires_at"]),
        )

    def consume_declaration_metadata_attachment(
        self,
        *,
        token: str,
        actor: IntakeActor,
        source: StoredSource,
        binding: AttachmentBinding,
    ) -> ConsumedAttachmentCapability:
        try:
            receipt = validate_receipt(source, actor.user_id)
        except IneligibleSource as exc:
            raise InvalidAttachmentSource() from exc
        row = self._repository.find_declaration_metadata_attachment_by_token_hash(
            hashlib.sha256(str(token or "").encode()).hexdigest()
        )
        if row is None:
            raise AttachmentCapabilityConflict()
        persisted_material = _source_material(
            actor_user_id=str(row["actor_user_id"]),
            source_id=str(row["source_id"]),
            receipt_id=str(row["receipt_id"]),
            source_sha256=str(row["source_sha256"]),
        )
        expected_token = _token_for_material(self._signing_key, persisted_material)
        expected_capability_id = (
            "br-dmac-" + hashlib.sha256(persisted_material).hexdigest()
        )
        if (
            row["schema_version"] != CAPABILITY_SCHEMA_VERSION
            or row["capability_id"] != expected_capability_id
            or not hmac.compare_digest(str(token or ""), expected_token)
            or not hmac.compare_digest(
                str(row["token_sha256"]),
                hashlib.sha256(expected_token.encode()).hexdigest(),
            )
        ):
            raise AttachmentCapabilityConflict()
        normalized = AttachmentBinding(
            actor_user_id=_required(binding.actor_user_id, "actor_user_id"),
            source_id=_required(binding.source_id, "source_id"),
            chat_id=_required(binding.chat_id, "chat_id"),
            message_id=_required(binding.message_id, "message_id"),
            workspace_model_id=_required(
                binding.workspace_model_id, "workspace_model_id"
            ),
        )
        exact = {
            "actor_user_id": actor.user_id,
            "source_id": receipt.source_id,
            "receipt_schema_version": receipt.receipt_schema_version,
            "receipt_id": receipt.receipt_id,
            "source_sha256": receipt.source_sha256,
            "intake_slot": receipt.intake_slot,
        }
        if any(row.get(field) != value for field, value in exact.items()) or (
            normalized.actor_user_id != actor.user_id
            or normalized.source_id != receipt.source_id
        ):
            raise AttachmentCapabilityConflict()
        now = int(self._clock())
        if row["state"] == CapabilityState.EXPIRED.value:
            raise AttachmentCapabilityExpired()
        if row["state"] == CapabilityState.PENDING.value and now >= int(
            row["expires_at"]
        ):
            self._repository.expire_pending_declaration_metadata_attachment(
                str(row["capability_id"])
            )
            raise AttachmentCapabilityExpired()
        binding_sha256 = _binding_hash(normalized)
        replayed = row["state"] == CapabilityState.CONSUMED.value
        if replayed:
            if not hmac.compare_digest(
                str(row["binding_sha256"] or ""), binding_sha256
            ):
                raise AttachmentCapabilityConflict()
        else:
            row = self._repository.consume_pending_declaration_metadata_attachment(
                capability_id=str(row["capability_id"]),
                binding=normalized,
                binding_sha256=binding_sha256,
                consumed_at=now,
            )
            if not hmac.compare_digest(
                str(row["binding_sha256"] or ""), binding_sha256
            ):
                raise AttachmentCapabilityConflict()
        return ConsumedAttachmentCapability(
            capability_id=str(row["capability_id"]),
            source_id=str(row["source_id"]),
            chat_id=str(row["chat_id"]),
            message_id=str(row["message_id"]),
            workspace_model_id=str(row["workspace_model_id"]),
            consumed_at=int(row["consumed_at"]),
            replayed=replayed,
        )


def build_declaration_metadata_attachment_capability_owner(
    *, engine: Engine, signing_key: bytes, clock: Callable[[], int]
) -> DeclarationMetadataAttachmentCapabilityOwner:
    return DeclarationMetadataAttachmentCapabilityOwner(
        repository=SqlAlchemyAttachmentCapabilityRepository(engine),
        signing_key=signing_key,
        clock=clock,
    )
