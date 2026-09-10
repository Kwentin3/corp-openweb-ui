from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "prepare_goal391_mapping_lab_plan.py"


def _module():
    spec = importlib.util.spec_from_file_location("goal391_mapping_lab_plan", SOURCE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assessment(*table_node_ids: str) -> dict:
    return {
        "expected_status": "COMPLETE",
        "required_table_decisions": [
            {"table_node_id": table_node_id, "disposition": "SECURITY_TRADES"}
            for table_node_id in table_node_ids
        ],
        "unresolved_table_node_ids": [],
        "forbidden_qualified_mapping_table_node_ids": [],
    }


def test_prepare_uses_attested_source_binding_and_read_only_owners(monkeypatch):
    module = _module()
    calls: dict[str, object] = {}

    async def attest(**kwargs):
        calls["attest"] = kwargs
        return SimpleNamespace(id="ordinary-user", role="user")

    class StoreFactory:
        def __init__(self, config):
            calls["store_config"] = config

        def create_read_only(self):
            calls["read_only"] = True
            return object()

        def create(self):  # pragma: no cover - must never be reached
            raise AssertionError("write_capable_store_forbidden")

    canonical = {
        "source": {"source_sha256": "source-sha"},
        "nodes": [
            {"node_type": "TEXT", "node_id": "text-1"},
            {"node_type": "TABLE", "node_id": "table-1"},
            {"node_type": "TABLE", "node_id": "table-2"},
        ],
    }
    envelope = SimpleNamespace(
        artifact=canonical,
        document_id="document-1",
        canonical_root_sha256="canonical-root",
    )

    class Reader:
        def read_envelope(self, manifest_ref, context, *, expected_normalization_run_id):
            calls["reader"] = (manifest_ref, context, expected_normalization_run_id)
            return envelope

    class ReaderFactory:
        def __init__(self, *, store, read_enabled):
            assert store is not None and read_enabled is True

        def create(self):
            return Reader()

    class Issuer:
        def __init__(self, *, store, reader, resolver):
            assert store is not None and reader is not None and resolver is not None

        def issue_from_source_files(self, *, corpus_id, requests):
            calls["issuer"] = (corpus_id, tuple(requests))
            request = tuple(requests)[0]
            return SimpleNamespace(
                selections=(
                    SimpleNamespace(
                        manifest_ref="manifest-1",
                        normalization_run_id="resolved-run",
                        access_context=lambda *, require_source_available: request.context,
                    ),
                )
            )

    class Semantic:
        def build_mapping_package(self, **kwargs):
            calls["package"] = kwargs
            return {"transient": True}

    monkeypatch.setattr(module, "_attest_browser_file", attest)
    monkeypatch.setattr(module, "ArtifactStoreFactory", StoreFactory)
    monkeypatch.setattr(module, "CanonicalReaderFactory", ReaderFactory)
    monkeypatch.setattr(module, "ArtifactResolver", lambda store: object())
    monkeypatch.setattr(module, "Goal391PrivateSelectionBindingIssuer", Issuer)
    monkeypatch.setattr(
        module.OrdinaryTradeSemanticMappingFactory,
        "create",
        staticmethod(lambda: Semantic()),
    )

    result = asyncio.run(
        module._prepare(
            user_email="test@test.ru",
            slot_id="opaque-slot",
            chat_id="historical-chat",
            file_id="openwebui-file",
            plan_ref="opaque-plan",
            assessment=_assessment("table-1", "table-2"),
            sqlite_path=Path("/private/artifacts.sqlite3"),
            payload_root=Path("/private/payloads"),
        )
    )

    plan = result["plan"]
    assert calls["read_only"] is True
    assert calls["attest"] == {
        "user_email": "test@test.ru",
        "chat_id": "historical-chat",
        "file_id": "openwebui-file",
    }
    request = calls["issuer"][1][0]
    assert request.context.case_id == "historical-chat"
    assert request.context.chat_id is None
    assert plan["ordinary_test_user_id"] == "ordinary-user"
    assert plan["slots"][0]["canonical_identity"] == {
        "document_id": "document-1",
        "canonical_root_sha256": "canonical-root",
        "source_sha256": "source-sha",
    }
    assert plan["slots"][0]["target_table_node_ids"] == ["table-1", "table-2"]
    assert "transient" not in str(plan)
    assert "TEXT" not in str(plan)
    assert calls["package"]["target_table_node_ids"] == ["table-1", "table-2"]


def test_attached_file_ids_accept_only_explicit_chat_files():
    module = _module()
    assert module._attached_file_ids({"files": [{"id": "file-1"}, {"id": "file-2"}]}) == {
        "file-1",
        "file-2",
    }
    assert module._attached_file_ids({"history": {"files": [{"id": "wrong"}]}}) == set()
