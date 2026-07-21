"""Closed-world contract for Broker Reports private source intake.

This module deliberately has no OpenWebUI imports.  The deployed router owns the
OpenWebUI adapters; this module owns eligibility, idempotency and receipt rules.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol


INTAKE_SCHEMA_VERSION = "broker_reports_private_source_intake_v1"
RECEIPT_SCHEMA_VERSION = "broker_reports_private_source_receipt_v1"
ACTION_ATTESTATION_SCHEMA_VERSION = "broker_reports_action_intake_attestation_v1"
RECEIPT_META_KEY = "broker_reports_intake"
ACTION_ATTESTATION_KEY = "broker_reports_server_intake_attestation"
PROTECTED_ACTION_ID = "broker_reports_private_intake_action"

# FACTORY_REQUIRED: production construction goes through
# build_broker_reports_intake_service() in the deployed router.
FACTORY_REQUIRED = "broker_reports_private_intake_factory_v1"

# FORBIDDEN: native processing, Knowledge, RAG, embeddings and vectorization are
# never optional capabilities of an eligible Broker Reports source.
FORBIDDEN = (
    "native_openwebui_document_processing",
    "knowledge",
    "rag",
    "embeddings",
    "vectorization",
)

PROCESS_NATIVE = False
KNOWLEDGE_ALLOWED = False
RAG_ALLOWED = False
EMBEDDINGS_ALLOWED = False
VECTORIZATION_ALLOWED = False

_SOURCE_ID_NAMESPACE = uuid.UUID("75355f89-3ed8-4eb8-815c-909f3276aeb1")
_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")
_BROKER_REPORTS_ID_PREFIX = "br-"
_FORBIDDEN_NATIVE_DATA_KEYS = frozenset(
    {
        "collection_name",
        "content",
        "embedding",
        "embeddings",
        "knowledge_id",
        "status",
        "vector",
        "vectors",
    }
)
_FORBIDDEN_NATIVE_META_KEYS = frozenset(
    {
        "collection_name",
        "embedding_model",
        "knowledge_id",
        "vector_collection",
    }
)


class IntakeContractError(RuntimeError):
    """Base class with a stable machine-readable error code."""

    code = "broker_reports_intake_error"


class InvalidIntakeRequest(IntakeContractError):
    code = "broker_reports_intake_invalid_request"


class IntakeConflict(IntakeContractError):
    code = "broker_reports_intake_idempotency_conflict"


class IntakePersistenceFailure(IntakeContractError):
    code = "broker_reports_intake_persistence_failed"


class IntakeCleanupFailure(IntakeContractError):
    code = "broker_reports_intake_cleanup_failed"


class IneligibleSource(IntakeContractError):
    code = "broker_reports_source_not_receipt_backed"


class NativeProcessingForbidden(IntakeContractError):
    code = "broker_reports_native_processing_forbidden"


@dataclass(frozen=True)
class IntakeActor:
    """Trusted identity supplied by the authenticated server context."""

    user_id: str


@dataclass(frozen=True)
class StoredSource:
    """Storage-neutral view of the persisted OpenWebUI file row."""

    id: str
    user_id: str
    source_hash: str | None
    filename: str
    path: str | None
    data: Mapping[str, Any] | None
    meta: Mapping[str, Any] | None
    created_at: int
    updated_at: int


@dataclass(frozen=True)
class VerifiedReceipt:
    source_id: str
    receipt_id: str
    source_sha256: str
    size_bytes: int
    replayed: bool = False

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "source_id": self.source_id,
            "receipt_id": self.receipt_id,
            "size_bytes": self.size_bytes,
            "process": PROCESS_NATIVE,
            "native_openwebui_document_processing": PROCESS_NATIVE,
            "knowledge_allowed": KNOWLEDGE_ALLOWED,
            "rag_allowed": RAG_ALLOWED,
            "embeddings_allowed": EMBEDDINGS_ALLOWED,
            "vectorization_allowed": VECTORIZATION_ALLOWED,
            "eligible": True,
            "replayed": self.replayed,
        }


class IntakeRepository(Protocol):
    async def get_owned(self, source_id: str, owner_user_id: str) -> StoredSource | None:
        """Resolve by primary key and authenticated owner in one predicate."""

    async def create(self, source: StoredSource) -> bool:
        """Create once; return False only for a unique-key race."""


class IntakeStorage(Protocol):
    async def store(
        self,
        payload: bytes,
        object_name: str,
        tags: Mapping[str, str],
    ) -> str:
        """Persist the exact bytes and return the provider path."""

    async def delete(self, path: str) -> None:
        """Delete one exact storage object or raise."""


def _default_clock() -> int:
    return int(time.time())


def _default_nonce() -> str:
    return uuid.uuid4().hex


def validate_idempotency_key(value: str) -> str:
    key = str(value or "")
    if not _IDEMPOTENCY_KEY_RE.fullmatch(key):
        raise InvalidIntakeRequest(
            "Idempotency-Key must be 8-128 ASCII letters, digits, '.', '_', ':' or '-'."
        )
    return key


def sanitize_filename(value: str) -> str:
    name = str(value or "").replace("\\", "/").split("/")[-1].strip()
    if (
        not name
        or name in {".", ".."}
        or "\x00" in name
        or any(ord(character) < 32 for character in name)
    ):
        raise InvalidIntakeRequest("A safe non-empty filename is required.")
    if len(name.encode("utf-8")) > 255:
        raise InvalidIntakeRequest("Filename is longer than 255 UTF-8 bytes.")
    return name


def deterministic_source_id(owner_user_id: str, idempotency_key: str) -> str:
    owner = str(owner_user_id or "").strip()
    if not owner:
        raise InvalidIntakeRequest("Authenticated user identity is required.")
    key = validate_idempotency_key(idempotency_key)
    scoped = f"{INTAKE_SCHEMA_VERSION}\x00{owner}\x00{key}"
    return f"{_BROKER_REPORTS_ID_PREFIX}{uuid.uuid5(_SOURCE_ID_NAMESPACE, scoped)}"


def idempotency_fingerprint(owner_user_id: str, idempotency_key: str) -> str:
    material = f"{owner_user_id}\x00{validate_idempotency_key(idempotency_key)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def is_broker_reports_reserved_source(source: StoredSource | Any) -> bool:
    """Fail closed for both a receipt marker and the reserved source-id family."""

    source_id = str(getattr(source, "id", "") or "")
    meta = getattr(source, "meta", None)
    has_marker = isinstance(meta, Mapping) and RECEIPT_META_KEY in meta
    return source_id.startswith(_BROKER_REPORTS_ID_PREFIX) or has_marker


def assert_native_processing_allowed(source: StoredSource | Any) -> None:
    if is_broker_reports_reserved_source(source):
        raise NativeProcessingForbidden(
            "Receipt-backed Broker Reports sources cannot enter native processing, "
            "Knowledge, RAG, embeddings or vectorization."
        )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def validate_receipt(source: StoredSource, owner_user_id: str) -> VerifiedReceipt:
    if source.user_id != owner_user_id:
        raise IneligibleSource("Source is not owned by the authenticated user.")
    if not source.id.startswith(_BROKER_REPORTS_ID_PREFIX):
        raise IneligibleSource("Source id is outside the Broker Reports reserved family.")

    meta = _mapping(source.meta)
    receipt = _mapping(meta.get(RECEIPT_META_KEY))
    if receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        raise IneligibleSource("Server-persisted Broker Reports receipt is absent or invalid.")

    expected_pairs = {
        "source_id": source.id,
        "owner_user_id": owner_user_id,
        "state": "eligible",
        "process": PROCESS_NATIVE,
        "native_openwebui_document_processing": PROCESS_NATIVE,
        "knowledge_allowed": KNOWLEDGE_ALLOWED,
        "rag_allowed": RAG_ALLOWED,
        "embeddings_allowed": EMBEDDINGS_ALLOWED,
        "vectorization_allowed": VECTORIZATION_ALLOWED,
    }
    for key, expected in expected_pairs.items():
        if receipt.get(key) != expected:
            raise IneligibleSource(f"Receipt invariant failed: {key}.")

    source_sha256 = str(receipt.get("source_sha256") or "")
    meta_hash = str(meta.get("file_hash") or "")
    row_hash = str(source.source_hash or "")
    if not (
        len(source_sha256) == 64
        and all(character in "0123456789abcdef" for character in source_sha256)
        and hmac.compare_digest(source_sha256, meta_hash)
        and hmac.compare_digest(source_sha256, row_hash)
    ):
        raise IneligibleSource("Persisted source provenance hashes disagree.")

    data = _mapping(source.data)
    if _FORBIDDEN_NATIVE_DATA_KEYS.intersection(data):
        raise IneligibleSource("Native document-processing data is present.")
    if _FORBIDDEN_NATIVE_META_KEYS.intersection(meta):
        raise IneligibleSource("Native Knowledge/RAG/vector metadata is present.")
    client_meta = _mapping(meta.get("data"))
    if _FORBIDDEN_NATIVE_META_KEYS.intersection(client_meta):
        raise IneligibleSource("Client metadata attempts to select native processing.")

    receipt_id = str(receipt.get("receipt_id") or "")
    expected_receipt_id = hashlib.sha256(
        f"{RECEIPT_SCHEMA_VERSION}\x00{source.id}\x00{source_sha256}".encode("utf-8")
    ).hexdigest()
    if not hmac.compare_digest(receipt_id, expected_receipt_id):
        raise IneligibleSource("Receipt identity does not match persisted provenance.")

    try:
        size_bytes = int(receipt.get("size_bytes"))
    except (TypeError, ValueError) as exc:
        raise IneligibleSource("Receipt size is invalid.") from exc
    if size_bytes <= 0 or meta.get("size") != size_bytes:
        raise IneligibleSource("Receipt size does not match the persisted file metadata.")
    if not source.path:
        raise IneligibleSource("Private source storage path is absent.")
    if receipt.get("created_at") != source.created_at:
        raise IneligibleSource("Receipt creation time does not match the persisted row.")
    fingerprint = str(receipt.get("idempotency_fingerprint") or "")
    if len(fingerprint) != 64 or any(
        character not in "0123456789abcdef" for character in fingerprint
    ):
        raise IneligibleSource("Receipt idempotency provenance is invalid.")

    return VerifiedReceipt(
        source_id=source.id,
        receipt_id=receipt_id,
        source_sha256=source_sha256,
        size_bytes=size_bytes,
    )


class BrokerReportsIntakeService:
    """Canonical intake service.  There is no native-processing code path."""

    def __init__(
        self,
        repository: IntakeRepository,
        storage: IntakeStorage,
        *,
        clock: Callable[[], int] = _default_clock,
        nonce: Callable[[], str] = _default_nonce,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._clock = clock
        self._nonce = nonce

    async def accept(
        self,
        *,
        actor: IntakeActor,
        idempotency_key: str,
        filename: str,
        content_type: str | None,
        payload: bytes,
    ) -> VerifiedReceipt:
        if not isinstance(payload, bytes) or not payload:
            raise InvalidIntakeRequest("Broker Reports source must contain bytes.")

        safe_name = sanitize_filename(filename)
        safe_content_type = str(content_type or "").strip() or None
        if safe_content_type and len(safe_content_type) > 255:
            raise InvalidIntakeRequest("Content-Type is longer than 255 characters.")

        source_id = deterministic_source_id(actor.user_id, idempotency_key)
        source_sha256 = hashlib.sha256(payload).hexdigest()
        existing = await self._repository.get_owned(source_id, actor.user_id)
        if existing is not None:
            return self._replay(existing, actor.user_id, source_sha256)

        attempt_name = f"{source_id}_{self._nonce()}_{safe_name}"
        path = await self._storage.store(
            payload,
            attempt_name,
            {
                "OpenWebUI-User-Id": actor.user_id,
                "OpenWebUI-File-Id": source_id,
                "Broker-Reports-Intake": RECEIPT_SCHEMA_VERSION,
            },
        )

        created_at = self._clock()
        receipt_id = hashlib.sha256(
            f"{RECEIPT_SCHEMA_VERSION}\x00{source_id}\x00{source_sha256}".encode("utf-8")
        ).hexdigest()
        receipt = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "receipt_id": receipt_id,
            "source_id": source_id,
            "owner_user_id": actor.user_id,
            "source_sha256": source_sha256,
            "size_bytes": len(payload),
            "idempotency_fingerprint": idempotency_fingerprint(
                actor.user_id, idempotency_key
            ),
            "state": "eligible",
            "process": PROCESS_NATIVE,
            "native_openwebui_document_processing": PROCESS_NATIVE,
            "knowledge_allowed": KNOWLEDGE_ALLOWED,
            "rag_allowed": RAG_ALLOWED,
            "embeddings_allowed": EMBEDDINGS_ALLOWED,
            "vectorization_allowed": VECTORIZATION_ALLOWED,
            "created_at": created_at,
        }
        source = StoredSource(
            id=source_id,
            user_id=actor.user_id,
            source_hash=source_sha256,
            filename=safe_name,
            path=path,
            data={},
            meta={
                "name": safe_name,
                "content_type": safe_content_type,
                "size": len(payload),
                "file_hash": source_sha256,
                RECEIPT_META_KEY: receipt,
            },
            created_at=created_at,
            updated_at=created_at,
        )

        try:
            created = await self._repository.create(source)
        except Exception:
            await self._delete_or_raise(path)
            raise

        if created:
            return validate_receipt(source, actor.user_id)

        # A concurrent request won the deterministic primary key.  Delete only
        # this attempt's unique object, then read and validate the winner.
        await self._delete_or_raise(path)
        winner = await self._repository.get_owned(source_id, actor.user_id)
        if winner is None:
            raise IntakePersistenceFailure(
                "Deterministic source id conflicted without an owned persisted receipt."
            )
        return self._replay(winner, actor.user_id, source_sha256)

    async def _delete_or_raise(self, path: str) -> None:
        try:
            await self._storage.delete(path)
        except Exception as exc:
            raise IntakeCleanupFailure(
                "Failed to compensate a non-authoritative storage write."
            ) from exc

    def _replay(
        self,
        existing: StoredSource,
        owner_user_id: str,
        incoming_sha256: str,
    ) -> VerifiedReceipt:
        receipt = validate_receipt(existing, owner_user_id)
        if not hmac.compare_digest(receipt.source_sha256, incoming_sha256):
            raise IntakeConflict(
                "Idempotency-Key was already used for different source bytes."
            )
        return VerifiedReceipt(
            source_id=receipt.source_id,
            receipt_id=receipt.receipt_id,
            source_sha256=receipt.source_sha256,
            size_bytes=receipt.size_bytes,
            replayed=True,
        )


async def resolve_receipts(
    source_ids: list[str],
    *,
    actor: IntakeActor,
    repository: IntakeRepository,
) -> list[VerifiedReceipt]:
    """Resolve only authenticated-owner, server-persisted receipts."""

    if not source_ids:
        raise IneligibleSource("At least one Broker Reports source is required.")
    if len(source_ids) > 128:
        raise IneligibleSource("More than 128 sources require an explicit batch session.")

    receipts: list[VerifiedReceipt] = []
    seen: set[str] = set()
    for source_id in source_ids:
        if source_id in seen:
            continue
        seen.add(source_id)
        source = await repository.get_owned(source_id, actor.user_id)
        if source is None:
            raise IneligibleSource(
                "Generic, missing or cross-owner file reference is not eligible."
            )
        receipts.append(validate_receipt(source, actor.user_id))
    return receipts


def action_attestation(receipts: list[VerifiedReceipt]) -> dict[str, Any]:
    """Build the only file-reference payload accepted by the protected Action."""

    if not receipts:
        raise IneligibleSource("Action attestation cannot be empty.")
    return {
        "schema_version": ACTION_ATTESTATION_SCHEMA_VERSION,
        "guard": FACTORY_REQUIRED,
        "sources": [
            {
                "source_id": receipt.source_id,
                "receipt_id": receipt.receipt_id,
                "receipt_schema_version": RECEIPT_SCHEMA_VERSION,
            }
            for receipt in receipts
        ],
    }
