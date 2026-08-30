from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[3]
DEPLOY_ROOT = ROOT / "deploy" / "openwebui-broker-reports-intake"
API_ROOT = "/api/v1/broker-reports"
AUTH_HEADERS = {"X-Test-User": "user-a"}
IDEMPOTENCY_HEADERS = {
    **AUTH_HEADERS,
    "Idempotency-Key": "metadata-http-0001",
}
PAYLOAD = b"synthetic declaration metadata\x00exact bytes"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _Repository:
    def __init__(self) -> None:
        self.rows = {}
        self._lock = asyncio.Lock()
        self.create_calls = 0

    async def get_owned(self, source_id, owner_user_id):
        row = self.rows.get(source_id)
        return row if row is not None and row.user_id == owner_user_id else None

    async def create(self, source):
        async with self._lock:
            self.create_calls += 1
            if source.id in self.rows:
                return False
            self.rows[source.id] = source
            return True


class _Storage:
    def __init__(self) -> None:
        self.objects = {}
        self.tags = {}
        self.store_calls = 0
        self.delete_calls = 0

    async def store(self, payload, object_name, tags):
        self.store_calls += 1
        path = f"private://{object_name}"
        self.objects[path] = payload
        self.tags[path] = dict(tags)
        return path

    async def delete(self, path):
        self.delete_calls += 1
        del self.objects[path]
        self.tags.pop(path, None)


def _stub_module(monkeypatch, name: str, **attributes):
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    monkeypatch.setitem(sys.modules, name, module)
    return module


@pytest.fixture
def http_harness(monkeypatch):
    """Actual FastAPI route/factory/service with only infrastructure boundaries faked."""

    open_webui = _stub_module(monkeypatch, "open_webui")
    open_webui.__path__ = []
    routers = _stub_module(monkeypatch, "open_webui.routers")
    routers.__path__ = []
    internal = _stub_module(monkeypatch, "open_webui.internal")
    internal.__path__ = []
    models = _stub_module(monkeypatch, "open_webui.models")
    models.__path__ = []
    storage_package = _stub_module(monkeypatch, "open_webui.storage")
    storage_package.__path__ = []
    utils = _stub_module(monkeypatch, "open_webui.utils")
    utils.__path__ = []

    async def get_verified_user(request: Request):
        user_id = str(request.headers.get("X-Test-User") or "").strip()
        if not user_id:
            raise HTTPException(status_code=401, detail="test_auth_required")
        return SimpleNamespace(id=user_id)

    async def get_async_session():
        yield object()

    class _UnusedModel:
        pass

    class _UnusedStorage:
        pass

    _stub_module(
        monkeypatch,
        "open_webui.env",
        WEBUI_SECRET_KEY="http-test-secret-with-at-least-32-bytes",
    )
    _stub_module(
        monkeypatch,
        "open_webui.internal.db",
        get_async_session=get_async_session,
    )
    _stub_module(
        monkeypatch,
        "open_webui.models.chat_messages",
        ChatMessage=_UnusedModel,
    )
    _stub_module(monkeypatch, "open_webui.models.chats", Chat=_UnusedModel, ChatFile=_UnusedModel)
    _stub_module(monkeypatch, "open_webui.models.files", File=_UnusedModel)
    _stub_module(monkeypatch, "open_webui.storage.provider", Storage=_UnusedStorage)
    _stub_module(
        monkeypatch,
        "open_webui.utils.auth",
        get_verified_user=get_verified_user,
    )

    contract_name = "open_webui.routers.broker_reports_intake_contract"
    monkeypatch.delitem(sys.modules, contract_name, raising=False)
    contract = _load_module(
        contract_name,
        DEPLOY_ROOT / "broker_reports_intake_contract.py",
    )
    router_name = "open_webui.routers.broker_reports_intake_http_test"
    monkeypatch.delitem(sys.modules, router_name, raising=False)
    router_module = _load_module(
        router_name,
        DEPLOY_ROOT / "broker_reports_intake.py",
    )

    repository = _Repository()
    storage = _Storage()
    monkeypatch.setattr(
        router_module,
        "build_broker_reports_intake_repository",
        lambda _db: repository,
    )
    monkeypatch.setattr(
        router_module,
        "build_broker_reports_intake_storage",
        lambda: storage,
    )

    app = FastAPI()
    app.include_router(router_module.router, prefix=API_ROOT)
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            contract=contract,
            repository=repository,
            storage=storage,
        )

    sys.modules.pop(router_name, None)
    sys.modules.pop(contract_name, None)


def _file(payload=PAYLOAD, filename="details.pdf"):
    return {"file": (filename, payload, "application/pdf")}


def _state_snapshot(http_harness):
    return (
        dict(http_harness.repository.rows),
        dict(http_harness.storage.objects),
        {path: dict(tags) for path, tags in http_harness.storage.tags.items()},
        http_harness.repository.create_calls,
        http_harness.storage.store_calls,
        http_harness.storage.delete_calls,
    )


def _assert_pristine(http_harness):
    assert _state_snapshot(http_harness) == ({}, {}, {}, 0, 0, 0)


def test_http_success_persists_exact_bytes_and_returns_v2_receipt(http_harness):
    response = http_harness.client.post(
        f"{API_ROOT}/declaration-metadata-intake",
        headers=IDEMPOTENCY_HEADERS,
        files=_file(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == (
        "broker_reports_declaration_metadata_receipt_v2"
    )
    assert body["intake_schema_version"] == (
        "broker_reports_declaration_metadata_intake_v2"
    )
    assert body["source_id"].startswith("br-dm-")
    assert body["owner_user_id"] == "user-a"
    assert body["source_sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert body["size_bytes"] == len(PAYLOAD)
    assert body["intake_slot"] == "DECLARATION_METADATA_INPUT"
    assert body["slot_owner"] == "SERVER_FIXED_DECLARATION_METADATA_INTAKE_V2"
    assert len(body["slot_checksum"]) == 64
    assert body["replayed"] is False

    assert http_harness.storage.store_calls == 1
    assert http_harness.repository.create_calls == 1
    row = http_harness.repository.rows[body["source_id"]]
    assert row.user_id == "user-a"
    assert row.source_hash == body["source_sha256"]
    assert row.meta["size"] == len(PAYLOAD)
    assert http_harness.storage.objects[row.path] == PAYLOAD
    assert http_harness.storage.tags == {
        row.path: {
            "OpenWebUI-User-Id": "user-a",
            "OpenWebUI-File-Id": body["source_id"],
            "Broker-Reports-Intake": (
                "broker_reports_declaration_metadata_receipt_v2"
            ),
        }
    }
    assert len(http_harness.storage.objects) == 1
    assert http_harness.storage.delete_calls == 0

    receipt_response = http_harness.client.get(
        f"{API_ROOT}/intake/{body['source_id']}/receipt",
        headers=AUTH_HEADERS,
    )
    assert receipt_response.status_code == 200
    assert receipt_response.json()["receipt_id"] == body["receipt_id"]
    assert receipt_response.json()["slot_checksum"] == body["slot_checksum"]


def test_http_requires_authentication_before_storage(http_harness):
    response = http_harness.client.post(
        f"{API_ROOT}/declaration-metadata-intake",
        headers={"Idempotency-Key": "metadata-http-auth"},
        files=_file(),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "test_auth_required"}
    _assert_pristine(http_harness)


@pytest.mark.parametrize(
    ("headers", "files", "expected_status"),
    [
        (AUTH_HEADERS, _file(), 422),
        (IDEMPOTENCY_HEADERS, None, 422),
    ],
)
def test_http_requires_idempotency_key_and_one_file(
    http_harness, headers, files, expected_status
):
    response = http_harness.client.post(
        f"{API_ROOT}/declaration-metadata-intake",
        headers=headers,
        files=files,
    )

    assert response.status_code == expected_status
    assert response.json()["detail"]
    _assert_pristine(http_harness)


@pytest.mark.parametrize(
    ("query", "extra_headers", "data", "expected_field"),
    [
        ("?role=BROKER_REPORT_INPUT", {}, None, "role"),
        ("?process=true", {}, None, "process"),
        ("", {"Purpose": "other"}, None, "header:purpose"),
        ("", {"Source-Policy": "client"}, None, "header:source-policy"),
        ("", {}, {"role": "BROKER_REPORT_INPUT"}, "multipart:role"),
        ("", {}, {"purpose": "other"}, "multipart:purpose"),
        ("", {}, {"source_policy": "client"}, "multipart:source_policy"),
    ],
)
def test_http_rejects_every_client_assignment_channel_before_storage(
    http_harness, query, extra_headers, data, expected_field
):
    response = http_harness.client.post(
        f"{API_ROOT}/declaration-metadata-intake{query}",
        headers={**IDEMPOTENCY_HEADERS, **extra_headers},
        files=_file(),
        data=data,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "broker_reports_declaration_metadata_override_denied",
        "fields": [expected_field],
    }
    _assert_pristine(http_harness)


def test_http_rejects_duplicate_file_fields_before_storage(http_harness):
    response = http_harness.client.post(
        f"{API_ROOT}/declaration-metadata-intake",
        headers=IDEMPOTENCY_HEADERS,
        files=[
            ("file", ("first.pdf", b"first", "application/pdf")),
            ("file", ("second.pdf", b"second", "application/pdf")),
        ],
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "broker_reports_declaration_metadata_override_denied",
        "fields": ["multipart:file_count"],
    }
    _assert_pristine(http_harness)


def test_http_replay_is_terminal_and_conflicting_bytes_return_409(http_harness):
    first = http_harness.client.post(
        f"{API_ROOT}/declaration-metadata-intake",
        headers=IDEMPOTENCY_HEADERS,
        files=_file(),
    )
    assert first.status_code == 200
    accepted_state = _state_snapshot(http_harness)

    replay = http_harness.client.post(
        f"{API_ROOT}/declaration-metadata-intake",
        headers=IDEMPOTENCY_HEADERS,
        files=_file(),
    )
    conflict = http_harness.client.post(
        f"{API_ROOT}/declaration-metadata-intake",
        headers=IDEMPOTENCY_HEADERS,
        files=_file(payload=b"different bytes"),
    )

    assert replay.status_code == 200
    assert replay.json()["source_id"] == first.json()["source_id"]
    assert replay.json()["receipt_id"] == first.json()["receipt_id"]
    assert replay.json()["replayed"] is True
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == (
        "broker_reports_intake_idempotency_conflict"
    )
    assert http_harness.storage.store_calls == 1
    assert http_harness.repository.create_calls == 1
    assert http_harness.storage.delete_calls == 0
    assert len(http_harness.repository.rows) == 1
    assert _state_snapshot(http_harness) == accepted_state


def test_http_receipt_is_private_to_authenticated_owner(http_harness):
    accepted = http_harness.client.post(
        f"{API_ROOT}/declaration-metadata-intake",
        headers=IDEMPOTENCY_HEADERS,
        files=_file(),
    )
    assert accepted.status_code == 200
    accepted_state = _state_snapshot(http_harness)

    foreign = http_harness.client.get(
        f"{API_ROOT}/intake/{accepted.json()['source_id']}/receipt",
        headers={"X-Test-User": "user-b"},
    )

    assert foreign.status_code == 422
    assert foreign.json()["detail"]["code"] == (
        "broker_reports_source_not_receipt_backed"
    )
    assert _state_snapshot(http_harness) == accepted_state
