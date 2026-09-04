from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    ArtifactResolver,
    ArtifactStoreConfig,
    ArtifactStoreError,
    ArtifactStoreFactory,
    build_retention_policy,
)
from broker_reports_gate1.artifact_models import ArtifactRecord
from broker_reports_gate1.artifact_models import (
    PRIVATE_BINARY_ARTIFACT_TYPE,
    build_private_binary_payload,
)


def _store(tmp_path: Path):
    return ArtifactStoreFactory(
        ArtifactStoreConfig(
            mode="sqlite",
            sqlite_path=tmp_path / "artifacts.sqlite3",
            payload_root=tmp_path / "payloads",
        )
    ).create()


def _record(
    artifact_id: str,
    *,
    private: bool = True,
    artifact_type: str = "validation_result_v0",
) -> ArtifactRecord:
    return ArtifactRecord(
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        case_id="case-integrity",
        chat_id="chat-integrity",
        user_id="user-integrity",
        workspace_model_id="workspace-integrity",
        normalization_run_id="run-integrity",
        document_id="document-integrity",
        source_file_ref={"openwebui_file_id": "file-integrity"},
        visibility="private_case" if private else "safe_internal",
        storage_backend=(
            "project_artifact_payload" if private else "project_artifact_store"
        ),
        retention_policy=build_retention_policy(mode="api_smoke"),
        access_policy={"requires_user_id": True},
        validation_status="validated",
        lifecycle_status="private_ready" if private else "visible_safe",
        payload={"schema_version": artifact_type, "value": "original"},
        safe_metadata={"status": "sealed"},
    )


def _context() -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="user-integrity",
        normalization_run_id="run-integrity",
        case_id="case-integrity",
        chat_id="chat-integrity",
        workspace_model_id="workspace-integrity",
        allow_private=True,
    )


def _payload_path(store, record: ArtifactRecord) -> Path:
    assert record.payload_ref
    return store.payload_root / record.payload_ref


def _update(store, sql: str, parameters: tuple[object, ...]) -> None:
    with closing(sqlite3.connect(store.sqlite_path)) as conn:
        conn.execute(sql, parameters)
        conn.commit()


def test_file_payload_mutation_fails_before_json_is_returned(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-file-mutation"))
    _payload_path(store, stored).write_text(
        json.dumps({"value": "tampered"}), encoding="utf-8"
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_payload_checksum_mismatch"


def test_inline_sqlite_payload_mutation_fails_before_return(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-inline-mutation", private=False))
    _update(
        store,
        "UPDATE artifact_records SET payload_inline_json = ? WHERE artifact_id = ?",
        (json.dumps({"value": "tampered"}), stored.artifact_id),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_payload_checksum_mismatch"


def test_checksum_is_verified_before_mutated_inline_json_is_parsed(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-inline-invalid", private=False))
    _update(
        store,
        "UPDATE artifact_records SET payload_inline_json = '{' WHERE artifact_id = ?",
        (stored.artifact_id,),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_payload_checksum_mismatch"


def test_payload_ref_swap_to_another_in_root_file_fails_closed(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-ref-swap"))
    swapped = store.payload_root / "swapped.json"
    swapped.write_text(json.dumps({"value": "swapped"}), encoding="utf-8")
    _update(
        store,
        "UPDATE artifact_records SET payload_ref = ? WHERE artifact_id = ?",
        (swapped.name, stored.artifact_id),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_payload_checksum_mismatch"


def test_payload_ref_swap_with_identical_bytes_is_identity_blocked(tmp_path: Path):
    store = _store(tmp_path)
    first = store.put_record(_record("artifact-ref-identical-first"))
    second = store.put_record(_record("artifact-ref-identical-second"))
    assert _payload_path(store, first).read_bytes() == _payload_path(store, second).read_bytes()
    _update(
        store,
        "UPDATE artifact_records SET payload_ref = ? WHERE artifact_id = ?",
        (second.payload_ref, first.artifact_id),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(first)

    assert blocked.value.code == "artifact_payload_checksum_mismatch"


def test_cross_artifact_ref_swap_cannot_delete_the_other_payload(tmp_path: Path):
    store = _store(tmp_path)
    first = store.put_record(_record("artifact-purge-first"))
    second_input = _record("artifact-purge-second")
    second_input.normalization_run_id = "run-integrity-other"
    second = store.put_record(second_input)
    second_path = _payload_path(store, second)
    _update(
        store,
        "UPDATE artifact_records SET payload_ref = ? WHERE artifact_id = ?",
        (second.payload_ref, first.artifact_id),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.purge_run(_context())

    assert blocked.value.code == "artifact_payload_checksum_mismatch"
    assert second_path.exists()
    assert store.read_payload(second)["value"] == "original"


def test_inline_backend_rejects_any_file_locator(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-inline-ref", private=False))
    _update(
        store,
        "UPDATE artifact_records SET payload_ref = 'foreign.json' WHERE artifact_id = ?",
        (stored.artifact_id,),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_payload_checksum_mismatch"


def test_file_backend_rejects_inline_payload_shadow(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-file-inline-shadow"))
    _update(
        store,
        "UPDATE artifact_records SET payload_inline_json = '{}' WHERE artifact_id = ?",
        (stored.artifact_id,),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_payload_checksum_mismatch"


def test_file_backend_inline_shadow_cannot_bypass_purge_locator_guard(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-file-inline-shadow-purge"))
    stored_path = _payload_path(store, stored)
    _update(
        store,
        "UPDATE artifact_records SET payload_inline_json = '{}' WHERE artifact_id = ?",
        (stored.artifact_id,),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.purge_run(_context())

    assert blocked.value.code == "artifact_payload_checksum_mismatch"
    assert stored_path.exists()


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("payload_size_bytes", 1),
        ("payload_size_bytes", "invalid"),
        ("checksum_sha256", "0" * 64),
    ],
)
def test_stored_size_or_checksum_mutation_fails_closed(
    tmp_path: Path, column: str, value: object
):
    store = _store(tmp_path)
    stored = store.put_record(_record(f"artifact-{column}"))
    _update(
        store,
        f"UPDATE artifact_records SET {column} = ? WHERE artifact_id = ?",
        (value, stored.artifact_id),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_payload_checksum_mismatch"


def test_legacy_row_without_integrity_fields_remains_readable(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-legacy", private=False))
    _update(
        store,
        """
        UPDATE artifact_records
        SET checksum_sha256 = NULL, payload_size_bytes = NULL
        WHERE artifact_id = ?
        """,
        (stored.artifact_id,),
    )

    assert store.read_payload(stored)["value"] == "original"


@pytest.mark.parametrize(
    "mutation",
    [
        "checksum_sha256 = NULL",
        "checksum_sha256 = ''",
        "checksum_sha256 = 'not-a-sha256'",
        "payload_size_bytes = NULL",
        "payload_size_bytes = -1",
    ],
)
def test_current_row_with_partial_or_malformed_integrity_seal_is_blocked(
    tmp_path: Path, mutation: str
):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-partial-seal", private=False))
    _update(
        store,
        f"UPDATE artifact_records SET {mutation} WHERE artifact_id = ?",
        (stored.artifact_id,),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_payload_checksum_mismatch"


def test_lifecycle_precedes_missing_payload_file(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-expired-missing"))
    _payload_path(store, stored).unlink()
    _update(
        store,
        """
        UPDATE artifact_records
        SET lifecycle_status = 'expired', purge_status = 'expired'
        WHERE artifact_id = ?
        """,
        (stored.artifact_id,),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_expired"


def test_missing_payload_file_keeps_existing_terminal(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-missing"))
    _payload_path(store, stored).unlink()

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_payload_unavailable"


def test_full_source_resolver_rejects_mutated_private_payload(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(
        _record(
            "artifact-full-source",
            artifact_type="private_normalized_source_payload_v0",
        )
    )
    _payload_path(store, stored).write_text(
        json.dumps({"schema_version": "private_normalized_source_payload_v0"}),
        encoding="utf-8",
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        ArtifactResolver(store).resolve(stored.artifact_id, _context())

    assert blocked.value.code == "artifact_payload_checksum_mismatch"


def test_idempotent_put_and_atomic_replay_reject_corrupted_stored_payload(
    tmp_path: Path,
):
    store = _store(tmp_path)
    record = _record("artifact-replay")
    stored = store.put_record(record)
    _payload_path(store, stored).write_text(
        json.dumps({"value": "tampered"}), encoding="utf-8"
    )

    with pytest.raises(ArtifactStoreError) as ordinary:
        store.put_record(copy.deepcopy(record))
    with pytest.raises(ArtifactStoreError) as atomic:
        store.put_records_atomic([copy.deepcopy(record)])

    assert ordinary.value.code == "artifact_payload_checksum_mismatch"
    assert atomic.value.code == "artifact_payload_checksum_mismatch"


def test_same_database_writer_can_reseal_generic_payload_scope_limit(tmp_path: Path):
    """The adjacent DB checksum detects corruption; it is not authentication."""

    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-resealed", private=False))
    tampered = json.dumps({"value": "resealed"}, sort_keys=True).encode("utf-8")
    _update(
        store,
        """
        UPDATE artifact_records
        SET payload_inline_json = ?, checksum_sha256 = ?, payload_size_bytes = ?
        WHERE artifact_id = ?
        """,
        (
            tampered.decode("utf-8"),
            hashlib.sha256(tampered).hexdigest(),
            len(tampered),
            stored.artifact_id,
        ),
    )

    assert store.read_payload(stored)["value"] == "resealed"


def test_atomic_preparation_failure_removes_earlier_payload_files(tmp_path: Path):
    store = _store(tmp_path)
    first = _record("artifact-atomic-preparation-first")
    second = _record("artifact-atomic-preparation-second")
    original_write = store._write_payload
    calls = 0

    def fail_second(artifact_id: str, payload_bytes: bytes) -> str:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise PermissionError("synthetic preparation failure")
        return original_write(artifact_id, payload_bytes)

    with patch.object(store, "_write_payload", side_effect=fail_second):
        with pytest.raises(PermissionError, match="synthetic preparation"):
            store.put_records_atomic([first, second])

    assert list(store.payload_root.glob("*.json")) == []
    assert store.get_record_unchecked(first.artifact_id) is None
    assert store.get_record_unchecked(second.artifact_id) is None


def test_private_binary_roundtrip_is_acl_checked_and_inner_hash_bound(tmp_path: Path):
    store = _store(tmp_path)
    content = b"\x89PNG\r\n\x1a\nprivate-image"
    record = _record(
        "artifact-private-binary", artifact_type=PRIVATE_BINARY_ARTIFACT_TYPE
    )
    record.payload = build_private_binary_payload(
        content=content, media_type="image/png"
    )
    stored = store.put_record(record)
    resolver = ArtifactResolver(store)

    resolved = resolver.resolve_private_binary(
        stored.artifact_id,
        _context(),
        expected_sha256=hashlib.sha256(content).hexdigest(),
    )

    assert resolved["content"] == content
    assert resolved["media_type"] == "image/png"
    assert resolved["content_sha256"] == hashlib.sha256(content).hexdigest()
    with pytest.raises(ArtifactStoreError) as denied:
        resolver.resolve_private_binary(
            stored.artifact_id, replace(_context(), user_id="foreign-user")
        )
    assert denied.value.code == "artifact_access_denied"


def test_private_binary_inner_mutation_fails_after_outer_store_reseal(tmp_path: Path):
    store = _store(tmp_path)
    record = _record(
        "artifact-private-binary-mutated",
        artifact_type=PRIVATE_BINARY_ARTIFACT_TYPE,
    )
    record.payload = build_private_binary_payload(
        content=b"original-private-bytes", media_type="image/jpeg"
    )
    stored = store.put_record(record)
    payload_path = _payload_path(store, stored)
    envelope = json.loads(payload_path.read_text(encoding="utf-8"))
    envelope["content_base64"] = "dGFtcGVyZWQ="
    resealed = json.dumps(envelope, sort_keys=True).encode("utf-8")
    payload_path.write_bytes(resealed)
    _update(
        store,
        """
        UPDATE artifact_records
        SET checksum_sha256 = ?, payload_size_bytes = ?
        WHERE artifact_id = ?
        """,
        (hashlib.sha256(resealed).hexdigest(), len(resealed), stored.artifact_id),
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        ArtifactResolver(store).resolve_private_binary(stored.artifact_id, _context())

    assert blocked.value.code == "artifact_binary_checksum_mismatch"


def test_private_binary_expected_association_hash_mismatch_fails(tmp_path: Path):
    store = _store(tmp_path)
    record = _record(
        "artifact-private-binary-association",
        artifact_type=PRIVATE_BINARY_ARTIFACT_TYPE,
    )
    record.payload = build_private_binary_payload(
        content=b"association-bound", media_type="image/webp"
    )
    stored = store.put_record(record)

    with pytest.raises(ArtifactStoreError) as blocked:
        ArtifactResolver(store).resolve_private_binary(
            stored.artifact_id, _context(), expected_sha256="0" * 64
        )

    assert blocked.value.code == "artifact_binary_checksum_mismatch"


def test_payload_root_preflight_leaves_no_probe_and_uses_private_mode(tmp_path: Path):
    store = _store(tmp_path)

    assert list(store.payload_root.glob(".artifact-store-probe-*")) == []
    if os.name != "nt":
        assert store.payload_root.stat().st_mode & 0o077 == 0


def test_payload_root_symlink_is_rejected_when_platform_supports_it(tmp_path: Path):
    target = tmp_path / "payload-target"
    target.mkdir(mode=0o700)
    linked = tmp_path / "payload-link"
    try:
        linked.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable for this runtime")

    with pytest.raises(ArtifactStoreError) as blocked:
        ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=tmp_path / "linked.sqlite3",
                payload_root=linked,
            )
        ).create()

    assert blocked.value.code == "artifact_store_unavailable"


def test_payload_root_permission_preflight_fails_closed(tmp_path: Path):
    original_open = os.open

    def deny_probe(path, flags, mode=0o777):
        if ".artifact-store-probe-" in str(path):
            raise PermissionError("synthetic permission denial")
        return original_open(path, flags, mode)

    with patch("broker_reports_gate1.artifact_store.os.open", side_effect=deny_probe):
        with pytest.raises(ArtifactStoreError) as blocked:
            _store(tmp_path)

    assert blocked.value.code == "artifact_store_unavailable"
    assert "synthetic permission denial" not in str(blocked.value)


def test_payload_root_rename_and_replacement_is_identity_blocked(tmp_path: Path):
    store = _store(tmp_path)
    stored = store.put_record(_record("artifact-root-replaced"))
    original_root = store.payload_root
    moved_root = tmp_path / "payloads-moved"
    original_root.rename(moved_root)
    original_root.mkdir(mode=0o700)
    assert stored.payload_ref is not None
    (original_root / stored.payload_ref).write_bytes(
        (moved_root / stored.payload_ref).read_bytes()
    )

    with pytest.raises(ArtifactStoreError) as blocked:
        store.read_payload(stored)

    assert blocked.value.code == "artifact_payload_unavailable"


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not Windows ACLs")
def test_existing_non_private_payload_root_is_rejected(tmp_path: Path):
    payload_root = tmp_path / "non-private"
    payload_root.mkdir(mode=0o755)
    payload_root.chmod(0o755)

    with pytest.raises(ArtifactStoreError) as blocked:
        ArtifactStoreFactory(
            ArtifactStoreConfig(
                mode="sqlite",
                sqlite_path=tmp_path / "non-private.sqlite3",
                payload_root=payload_root,
            )
        ).create()

    assert blocked.value.code == "artifact_store_unavailable"
