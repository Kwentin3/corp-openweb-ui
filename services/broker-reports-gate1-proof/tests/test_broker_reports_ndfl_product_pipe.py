from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
import sys
import threading
from types import ModuleType
from types import SimpleNamespace

import pytest

from broker_reports_gate1 import (
    ArtifactAccessContext,
    GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
)
from broker_reports_gate1.gate3_ndfl_workflow import NdflWorkflowError
from openwebui_actions.broker_reports_gate1_pipe import Pipe
from broker_reports_gate1.artifact_retention import build_retention_policy
import test_broker_reports_ordinary_trade_declaration_mvp as declaration_fixtures


def test_native_chat_scope_is_recovered_only_through_owner_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeChats:
        @staticmethod
        async def get_chat_by_id_and_user_id(chat_id: str, user_id: str):
            assert (chat_id, user_id) == ("owned-chat", "user-a")
            return SimpleNamespace(chat={"models": ["broker-reports-ndfl"]})

    class FakeRequest:
        async def json(self):
            return {"metadata": {"chat_id": "owned-chat"}}

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    chats = ModuleType("open_webui.models.chats")
    chats.Chats = FakeChats
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.chats", chats)

    metadata = asyncio.run(
        Pipe()._server_attested_runtime_metadata(
            request=FakeRequest(),
            metadata={},
            user={"id": "user-a"},
        )
    )

    assert metadata == {
        "chat_id": "owned-chat",
        "model_id": "broker-reports-ndfl",
    }


def test_product_stage_is_disabled_by_default() -> None:
    pipe = Pipe()
    result = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            store=object(),
            context=_context("broker-reports-ndfl"),
            artifact_manifest=SimpleNamespace(artifact_refs_by_type={}),
            user={"id": "user"},
            request=object(),
            event_emitter=None,
        )
    )

    assert result == {
        "schema_version": "broker_reports_ndfl_gate3_product_run_v1",
        "enabled": False,
        "status": "disabled",
        "provider_calls_total": 0,
    }


def test_product_stage_rejects_base_pipe_identity_before_provider() -> None:
    pipe = Pipe()
    pipe.valves.ndfl_gate3_enabled = True

    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(
            pipe._maybe_run_ndfl_gate3(
                store=object(),
                context=_context("broker_reports_gate1_pipe"),
                artifact_manifest=SimpleNamespace(artifact_refs_by_type={}),
                user={"id": "user"},
                request=object(),
                event_emitter=None,
            )
        )

    assert failure.value.code == "ndfl_workspace_model_identity_required"


def test_public_pipe_rejects_caller_selected_hidden_declaration_action() -> None:
    pipe = Pipe()
    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(
            pipe.pipe(
                {
                    "broker_reports_declaration_action": {
                        "request_publication_ref": "artifact_" + "a" * 64,
                        "answer": {"kind": "confirmation", "value": True},
                    }
                },
                __user__={"id": "user-a"},
                __metadata__={
                    "chat_id": "case-a",
                    "model_id": "broker-reports-ndfl",
                },
            )
        )
    assert failure.value.code == "ordinary_trade_declaration_hidden_action_forbidden"


def test_maintained_stage_binds_event_response_to_current_owner_actions(
    tmp_path: Path,
) -> None:
    _runtime, context, _providers, store = declaration_fixtures._case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        include_store=True,
    )
    pipe = Pipe()
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    kwargs = {
        "store": store,
        "context": context,
        "artifact_manifest": SimpleNamespace(artifact_refs_by_type={}),
        "user": {"id": context.user_id},
        "request": object(),
        "event_emitter": None,
        "retention_policy": build_retention_policy(mode="synthetic_dev"),
    }

    first = asyncio.run(pipe._maybe_run_ndfl_gate3(**kwargs))
    assert first["product"]["status"] == "INPUT_REQUIRED"
    assert first["provider_calls_total"] == 0
    while first["product"]["preparation"]["user_actions"]:
        request = first["product"]["preparation"]["user_actions"][0]

        async def event_call(payload, *, answer=_product_chat_answer(request["fact_key"])):
            assert payload["type"] in {"confirmation", "input"}
            return answer

        result = asyncio.run(
            pipe._maybe_run_ndfl_gate3(
                **kwargs,
                trusted_interaction_message="Продолжить",
                event_call=event_call,
            )
        )
        assert result["declaration_chat_receipt"]["status"] == "ANSWER_ACCEPTED"
        first = result
    assert result["product"]["status"] == "DECLARATION_XML_READY"
    assert result["product"]["xml_created"] is True
    assert result["declaration_action_receipt"]["fact_created"] is True
    assert result["provider_calls_total"] == 0


def test_plain_chat_answer_cannot_select_a_new_current_request(
    tmp_path: Path,
) -> None:
    _runtime, context, _providers, store = declaration_fixtures._case(
        tmp_path,
        proceeds="60.00",
        publish_human_facts=False,
        include_store=True,
    )
    pipe = Pipe()
    pipe.valves.ordinary_trade_candidate_enabled = True
    pipe.valves.canonical_gate2_write_enabled = True
    pipe.valves.canonical_gate2_read_enabled = True
    kwargs = {
        "store": store,
        "context": context,
        "artifact_manifest": SimpleNamespace(artifact_refs_by_type={}),
        "user": {"id": context.user_id},
        "request": object(),
        "event_emitter": None,
        "retention_policy": build_retention_policy(mode="synthetic_dev"),
    }

    first = asyncio.run(pipe._maybe_run_ndfl_gate3(**kwargs))
    current = first["product"]["preparation"]["user_actions"][0]
    replay = asyncio.run(
        pipe._maybe_run_ndfl_gate3(
            **kwargs,
            trusted_interaction_message=_product_chat_answer(current["fact_key"]),
        )
    )

    assert replay["product"]["status"] == "INPUT_REQUIRED"
    assert replay["product"]["preparation"]["user_actions"][0][
        "request_publication_ref"
    ] == current["request_publication_ref"]
    assert "declaration_action_receipt" not in replay


def test_public_bundled_pipe_reaches_one_idempotent_private_xml_from_chat(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _runtime, context, _providers, store = declaration_fixtures._case(
        tmp_path / "case",
        proceeds="60.00",
        publish_human_facts=False,
        include_store=True,
    )
    maintained_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1.")
    }
    for name in list(maintained_modules):
        sys.modules.pop(name, None)
    bundle_path = (
        Path(__file__).resolve().parents[1]
        / "openwebui_actions"
        / "broker_reports_gate1_pipe_bundled.py"
    )
    spec = importlib.util.spec_from_file_location("issue304_public_bundle", bundle_path)
    assert spec is not None and spec.loader is not None
    bundled = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundled)

    rows = {}
    calls = {"upload": 0, "insert": 0, "delete": 0}

    class FileForm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Files:
        @staticmethod
        async def get_file_by_id(file_id):
            return rows.get(file_id)

        @staticmethod
        async def insert_new_file(user_id, form):
            calls["insert"] += 1
            row = SimpleNamespace(**form.__dict__, user_id=user_id)
            rows[form.id] = row
            return row

    class Storage:
        @staticmethod
        def upload_file(stream, name, headers):
            assert headers["OpenWebUI-User-Id"] == context.user_id
            calls["upload"] += 1
            contents = stream.read()
            path = tmp_path / "private" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)
            return contents, str(path)

        @staticmethod
        def get_file(path):
            return path

        @staticmethod
        def delete_file(path):
            calls["delete"] += 1
            Path(path).unlink(missing_ok=True)

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    files = ModuleType("open_webui.models.files")
    storage = ModuleType("open_webui.storage")
    provider = ModuleType("open_webui.storage.provider")
    files.FileForm = FileForm
    files.Files = Files
    provider.Storage = Storage
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.files", files)
    monkeypatch.setitem(sys.modules, "open_webui.storage", storage)
    monkeypatch.setitem(sys.modules, "open_webui.storage.provider", provider)

    try:
        pipe = bundled.Pipe()
        pipe.valves.ordinary_trade_candidate_enabled = True
        pipe.valves.canonical_gate2_write_enabled = True
        pipe.valves.canonical_gate2_read_enabled = True
        pipe.valves.artifact_store_path = str(store.sqlite_path)
        pipe.valves.artifact_payload_root = str(store.payload_root)
        pipe.valves.artifact_retention_mode = "synthetic_dev"
        metadata = {
            "chat_id": context.case_id,
            "case_id": context.case_id,
            "model_id": "broker-reports-ndfl",
        }

        event_payloads = []

        def public_turn(
            message: str,
            *,
            event_response=None,
            user_id: str = context.user_id,
        ) -> str:
            async def event_call(payload):
                event_payloads.append(payload)
                if payload.get("type") == "confirmation" and event_response in {
                    "Да",
                    "Нет",
                }:
                    return event_response == "Да"
                return event_response

            return asyncio.run(
                pipe.pipe(
                    {"messages": [{"role": "user", "content": message}]},
                    __user__={"id": user_id, "email": "", "name": ""},
                    __metadata__=metadata,
                    __event_call__=event_call,
                )
            )

        first_content = public_turn("Подготовить 3-НДФЛ")
        first = pipe.last_artifact_manifest["ndfl_gate3"]
        assert first["product"]["status"] == "INPUT_REQUIRED"
        assert first["product"]["xml_created"] is False
        assert "request_publication_ref" not in first_content
        assert "Допустимые значения" in first_content or "Ответьте" in first_content

        states = {"INPUT_REQUIRED"}
        last_answer = ""
        while first["product"]["preparation"]["user_actions"]:
            action = first["product"]["preparation"]["user_actions"][0]
            fact_key = action["fact_key"]
            if fact_key == "taxpayer_identity":
                rejected = public_turn(
                    "Продолжить",
                    event_response="Изменить: 123456789012; Иванов; Иван; Иванович",
                )
                first = pipe.last_artifact_manifest["ndfl_gate3"]
                assert first["declaration_chat_receipt"]["status"] == "ANSWER_REJECTED"
                assert "не принят" in rejected
                last_answer = (
                    "Изменить: 500100732259; Иванов; Иван; Иванович"
                )
            elif fact_key == "declaration_date":
                rejected = public_turn("Продолжить", event_response="2025-99-99")
                first = pipe.last_artifact_manifest["ndfl_gate3"]
                assert first["declaration_chat_receipt"] == {
                    "status": "ANSWER_REJECTED",
                    "answer_accepted": False,
                    "reason_code": "gate5_gap_declaration_date_invalid",
                }
                assert "не принят" in rejected
                last_answer = "2026-08-24"
            else:
                last_answer = _product_chat_answer(fact_key)
            public_turn("Продолжить", event_response=last_answer)
            first = pipe.last_artifact_manifest["ndfl_gate3"]
            states.add(first["product"]["status"])

        assert "DRAFT_READY" in states
        assert first["product"]["status"] == "DECLARATION_XML_READY"
        file_id = first["product"]["private_download"]["file_id"]
        assert calls == {"upload": 1, "insert": 1, "delete": 0}
        assert len(rows) == 1

        repeated_content = public_turn("Продолжить")
        repeated = pipe.last_artifact_manifest["ndfl_gate3"]
        assert repeated["product"]["private_download"]["file_id"] == file_id
        assert calls == {"upload": 1, "insert": 1, "delete": 0}
        assert "/api/v1/files/" + file_id in repeated_content
        assert first["provider_calls_total"] == 0
        assert pipe.last_artifact_manifest["resumed_case"] is True
        serialized_events = json.dumps(event_payloads, ensure_ascii=False)
        assert "request_publication_ref" not in serialized_events
        assert "fact_key" not in serialized_events
        assert "500100732259" not in serialized_events
        assert "••••" in serialized_events

        change_content = public_turn("Изменить дату")
        changing = pipe.last_artifact_manifest["ndfl_gate3"]
        assert changing["product"]["status"] == "DRAFT_READY"
        assert changing["product"]["xml_created"] is False
        assert changing["product"]["preparation"]["checklist_fact_keys"] == [
            "declaration_date"
        ]
        assert "календарную дату" in change_content
        rejected_change = public_turn("Продолжить", event_response="2025-99-99")
        changing = pipe.last_artifact_manifest["ndfl_gate3"]
        assert changing["product"]["status"] == "DRAFT_READY"
        assert changing["declaration_chat_receipt"]["status"] == "ANSWER_REJECTED"
        assert "не принят" in rejected_change
        public_turn("Продолжить", event_response="2026-08-25")
        corrected = pipe.last_artifact_manifest["ndfl_gate3"]
        corrected_file_id = corrected["product"]["private_download"]["file_id"]
        assert corrected["product"]["status"] == "DECLARATION_XML_READY"
        assert corrected_file_id != file_id
        assert calls == {"upload": 2, "insert": 2, "delete": 0}
        public_turn("Продолжить")
        assert pipe.last_artifact_manifest["ndfl_gate3"]["product"][
            "private_download"
        ]["file_id"] == corrected_file_id
        assert calls == {"upload": 2, "insert": 2, "delete": 0}
    finally:
        for name in list(sys.modules):
            if name == "broker_reports_gate1" or name.startswith("broker_reports_gate1."):
                sys.modules.pop(name, None)
        sys.modules.update(maintained_modules)


def test_xml_delivery_uses_authenticated_openwebui_private_file_owner(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured = {"uploads": 0, "inserts": 0}
    rows = {}
    xml_bytes = b"<root/>"

    class FileForm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Files:
        @staticmethod
        async def get_file_by_id(file_id):
            return rows.get(file_id)

        @staticmethod
        async def insert_new_file(user_id, form):
            captured["inserts"] += 1
            captured["user_id"] = user_id
            captured["form"] = form
            row = SimpleNamespace(**form.__dict__, user_id=user_id)
            rows[form.id] = row
            return row

    class Storage:
        @staticmethod
        def upload_file(stream, name, headers):
            captured["uploads"] += 1
            captured["headers"] = headers
            contents = stream.read()
            path = tmp_path / name
            path.write_bytes(contents)
            return contents, str(path)

        @staticmethod
        def get_file(path):
            return path

        @staticmethod
        def delete_file(path):
            Path(path).unlink(missing_ok=True)

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    files = ModuleType("open_webui.models.files")
    storage = ModuleType("open_webui.storage")
    provider = ModuleType("open_webui.storage.provider")
    files.FileForm = FileForm
    files.Files = Files
    provider.Storage = Storage
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.files", files)
    monkeypatch.setitem(sys.modules, "open_webui.storage", storage)
    monkeypatch.setitem(sys.modules, "open_webui.storage.provider", provider)

    context = ArtifactAccessContext(
        user_id="user-a",
        normalization_run_id="run-a",
        case_id="case-a",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    kwargs = {
        "user": {"id": "user-a", "email": "", "name": ""},
        "context": context,
        "filename": "3-ndfl-2025.xml",
        "xml_bytes": xml_bytes,
        "xml_sha256": __import__("hashlib").sha256(xml_bytes).hexdigest(),
        "receipt_sha256": "a" * 64,
    }
    file_id = asyncio.run(Pipe._publish_ndfl_xml_file(**kwargs))
    repeated = asyncio.run(Pipe._publish_ndfl_xml_file(**kwargs))

    assert repeated == file_id
    assert captured["uploads"] == 1
    assert captured["inserts"] == 1
    assert captured["user_id"] == "user-a"
    assert captured["headers"]["OpenWebUI-User-Id"] == "user-a"
    assert captured["form"].id == file_id
    assert captured["form"].meta["data"]["private_user_artifact"] is True
    assert captured["form"].meta["data"]["receipt_sha256"] == "a" * 64


def test_concurrent_identical_xml_delivery_keeps_one_valid_owner_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    rows = {}
    calls = {"upload": 0, "insert": 0, "delete": 0}
    counter_lock = threading.Lock()
    upload_barrier = threading.Barrier(2)
    xml_bytes = b"<root/>"

    class FileForm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Files:
        @staticmethod
        async def get_file_by_id(file_id):
            return rows.get(file_id)

        @staticmethod
        async def insert_new_file(user_id, form):
            calls["insert"] += 1
            if form.id in rows:
                return None
            row = SimpleNamespace(**form.__dict__, user_id=user_id)
            rows[form.id] = row
            return row

    class Storage:
        @staticmethod
        def upload_file(stream, name, _headers):
            contents = stream.read()
            path = tmp_path / name
            path.write_bytes(contents)
            with counter_lock:
                calls["upload"] += 1
            upload_barrier.wait()
            return contents, str(path)

        @staticmethod
        def get_file(path):
            return path

        @staticmethod
        def delete_file(path):
            with counter_lock:
                calls["delete"] += 1
            Path(path).unlink(missing_ok=True)

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    files = ModuleType("open_webui.models.files")
    storage = ModuleType("open_webui.storage")
    provider = ModuleType("open_webui.storage.provider")
    files.FileForm = FileForm
    files.Files = Files
    provider.Storage = Storage
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.files", files)
    monkeypatch.setitem(sys.modules, "open_webui.storage", storage)
    monkeypatch.setitem(sys.modules, "open_webui.storage.provider", provider)
    context = ArtifactAccessContext(
        user_id="user-a",
        normalization_run_id="run-a",
        case_id="case-a",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )
    kwargs = {
        "user": {"id": "user-a", "email": "", "name": ""},
        "context": context,
        "filename": "3-ndfl-2025.xml",
        "xml_bytes": xml_bytes,
        "xml_sha256": __import__("hashlib").sha256(xml_bytes).hexdigest(),
        "receipt_sha256": "c" * 64,
    }

    async def publish_twice():
        return await asyncio.gather(
            Pipe._publish_ndfl_xml_file(**kwargs),
            Pipe._publish_ndfl_xml_file(**kwargs),
            return_exceptions=True,
        )

    results = asyncio.run(publish_twice())

    assert all(isinstance(item, str) for item in results), results
    assert results[0] == results[1]
    assert len(rows) == 1
    assert Path(next(iter(rows.values())).path).read_bytes() == xml_bytes
    assert len(list(tmp_path.glob("*"))) == 1
    assert calls == {"upload": 2, "insert": 2, "delete": 1}
    assert asyncio.run(Pipe._publish_ndfl_xml_file(**kwargs)) == results[0]
    assert calls == {"upload": 2, "insert": 2, "delete": 1}


def test_private_xml_record_failure_removes_partial_storage_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    deleted = []

    class FileForm:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Files:
        @staticmethod
        async def get_file_by_id(_file_id):
            return None

        @staticmethod
        async def insert_new_file(_user_id, _form):
            return None

    class Storage:
        @staticmethod
        def upload_file(stream, name, _headers):
            contents = stream.read()
            path = tmp_path / name
            path.write_bytes(contents)
            return contents, str(path)

        @staticmethod
        def delete_file(path):
            deleted.append(path)
            Path(path).unlink()

    openwebui = ModuleType("open_webui")
    models = ModuleType("open_webui.models")
    files = ModuleType("open_webui.models.files")
    storage = ModuleType("open_webui.storage")
    provider = ModuleType("open_webui.storage.provider")
    files.FileForm = FileForm
    files.Files = Files
    provider.Storage = Storage
    monkeypatch.setitem(sys.modules, "open_webui", openwebui)
    monkeypatch.setitem(sys.modules, "open_webui.models", models)
    monkeypatch.setitem(sys.modules, "open_webui.models.files", files)
    monkeypatch.setitem(sys.modules, "open_webui.storage", storage)
    monkeypatch.setitem(sys.modules, "open_webui.storage.provider", provider)
    xml_bytes = b"<root/>"
    context = ArtifactAccessContext(
        user_id="user-a",
        normalization_run_id="run-a",
        case_id="case-a",
        workspace_model_id="broker-reports-ndfl",
        allow_private=True,
    )

    with pytest.raises(NdflWorkflowError) as failure:
        asyncio.run(
            Pipe._publish_ndfl_xml_file(
                user={"id": "user-a"},
                context=context,
                filename="3-ndfl-2025.xml",
                xml_bytes=xml_bytes,
                xml_sha256=__import__("hashlib").sha256(xml_bytes).hexdigest(),
                receipt_sha256="b" * 64,
            )
        )

    assert failure.value.code == "ordinary_trade_declaration_private_file_record_failed"
    assert len(deleted) == 1
    assert not Path(deleted[0]).exists()


def _product_chat_answer(fact_key: str) -> str:
    return {
        "taxpayer_identity": "Подтверждаю",
        "taxpayer_capacity": "individual_not_ip_not_private_practice",
        "residency_evidence": (
            "Присутствие: 2025-01-01..2025-07-02; "
            "отсутствие: 2025-07-03..2025-12-31; причины: нет"
        ),
        "ordinary_trade_declaration_zero_scope_confirmed": "Да",
        "filing_instance_identity": "INITIAL",
        "declaration_date": "2026-08-24",
        "filing_destination_code": "7705",
        "signer_and_representation": "SELF",
        "budget_disposition": "PAYMENT",
        "budget_oktmo": "45382000",
    }[fact_key]


def test_workload_failure_detail_exposes_only_explicit_safe_details() -> None:
    failure = NdflWorkflowError(
        "ndfl_gate3_document_incomplete",
        safe_details={"chunks_rejected": 1},
    )

    assert Pipe._workload_failure_detail(failure) == {"chunks_rejected": 1}
    assert Pipe._workload_failure_detail(RuntimeError("private payload")) is None


def test_human_residual_turn_reuses_one_validated_gate3_artifact() -> None:
    context = _context("broker-reports-ndfl")
    record = SimpleNamespace(
        artifact_id="annotations",
        artifact_type=GATE3_FINANCIAL_ANNOTATIONS_ARTIFACT_TYPE,
        user_id=context.user_id,
        normalization_run_id=context.normalization_run_id,
        case_id=context.case_id,
        chat_id=None,
        workspace_model_id=context.workspace_model_id,
        visibility="private_case",
        validation_status="validated",
        lifecycle_status="active",
        purge_status=None,
        expires_at=None,
        source_file_ref={"source_deleted": False},
        payload=None,
        payload_ref=None,
    )
    store = SimpleNamespace(
        list_by_run=lambda run_id: [record] if run_id == "run" else [],
        get_record_unchecked=lambda artifact_id: (
            record if artifact_id == "annotations" else None
        ),
    )

    assert Pipe._persisted_gate3_annotations_artifact_id(
        store=store,
        context=context,
    ) == "annotations"


def test_private_audit_is_exact_external_and_non_overwriting(tmp_path: Path) -> None:
    pipe = Pipe()
    pipe.valves.ndfl_gate3_private_audit_enabled = True
    pipe.valves.ndfl_gate3_private_audit_root = str(tmp_path)
    pipe.valves.ndfl_gate3_private_audit_id = "g3c5_product_test_001"
    envelope = SimpleNamespace(
        artifact={"private": "exact canonical"},
        document_id="document",
        canonical_version_id="version",
        canonical_version_number=1,
        version_status="ACTIVE",
        schema_version="canonical_artifact_v1",
        canonical_root_sha256="a" * 64,
        physical_layout="single_payload",
        component_count=1,
        payload_bytes=100,
    )
    attempt = SimpleNamespace(
        projection={"model_view": {"content": "exact fragment"}},
        dictionary={"labels": [{"meaning": "exact meaning"}]},
        dictionary_managed_binding={"dictionary_identity": {"version": "1"}},
        dictionary_markdown="exact dictionary",
        instruction="exact instruction",
        model_visible_request={"messages": []},
        final_provider_request={"messages": []},
        raw_provider_response={"raw": True},
        raw_model_output={"annotations": []},
        validated_output={"annotations": []},
        validation_status="validated",
        validation_error_code=None,
        execution_metadata={"provider": "test"},
        metrics={"calls": 1},
    )
    role_attempt = SimpleNamespace(
        facts=(),
        role_context={
            "schema_version": "broker_reports_gate3_role_context_v1",
            "accepted_target_aliases": [],
        },
        role_provenance={
            "schema_version": "broker_reports_gate3_role_provenance_v1",
            "facts": [],
        },
        role_pack={"roles": []},
        role_pack_markdown="exact role pack",
        instruction="exact role instruction",
        model_visible_request=None,
        final_provider_request=None,
        raw_provider_response=None,
        raw_model_output=None,
        validated_output={"annotations": []},
        execution_status="skipped_empty",
        validation_error_code=None,
        execution_metadata=None,
        metrics={"provider_called": False},
    )
    outcome = SimpleNamespace(
        chunk={"content": "exact fragment"},
        attempt=attempt,
        role_attempt=role_attempt,
    )
    execution = SimpleNamespace(
        canonical_artifact_ref="manifest",
        activation_receipt=None,
        canonical_before_gate3=envelope,
        canonical_after_gate3=envelope,
        gate3=SimpleNamespace(
            batch_result=SimpleNamespace(
                outcomes=(outcome,),
                merged_output={"annotations": []},
                metrics={
                    "financial_labeling_provider_calls": 1,
                    "role_labeling_provider_calls": 1,
                },
            ),
            annotations_payload={
                "schema_version": "broker_reports_financial_annotations_v2",
                "annotations": [],
            },
            annotations_artifact_id="annotations",
        ),
    )

    receipt = pipe._write_ndfl_private_audit([execution])
    exact_path = tmp_path / "g3c5_product_test_001" / "document_001.exact.json"
    exact = json.loads(exact_path.read_text(encoding="utf-8"))

    assert receipt["status"] == "saved"
    assert pipe._ndfl_provider_calls_total([execution]) == 2
    assert exact["attempts"][0]["projection"]["model_view"]["content"] == (
        "exact fragment"
    )
    assert exact["attempts"][0]["dictionary_markdown"] == "exact dictionary"
    assert exact["attempts"][0]["instruction"] == "exact instruction"
    assert exact["attempts"][0]["raw_model_output"] == {"annotations": []}
    assert exact["attempts"][0]["role_attempt"]["role_pack_markdown"] == (
        "exact role pack"
    )
    assert exact["attempts"][0]["role_attempt"]["role_context"] == {
        "schema_version": "broker_reports_gate3_role_context_v1",
        "accepted_target_aliases": [],
    }
    assert exact["attempts"][0]["role_attempt"]["role_provenance"] == {
        "schema_version": "broker_reports_gate3_role_provenance_v1",
        "facts": [],
    }
    assert exact["financial_annotations_v2"]["annotations"] == []
    with pytest.raises(NdflWorkflowError) as failure:
        pipe._write_ndfl_private_audit([execution])
    assert failure.value.code == "ndfl_private_audit_target_not_new"


def _context(workspace_model_id: str) -> ArtifactAccessContext:
    return ArtifactAccessContext(
        user_id="user",
        normalization_run_id="run",
        case_id="case",
        workspace_model_id=workspace_model_id,
        allow_private=True,
    )
