from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from broker_reports_gate1.ordinary_trade_mapping_prompt import PROMPT_PLACEHOLDER
from broker_reports_gate1.ordinary_trade_mapping_prompt_publication import (
    OrdinaryTradeMappingPromptPublication,
    OrdinaryTradeMappingPromptPublicationError,
    OrdinaryTradeMappingPromptPublicationInput,
    OrdinaryTradeMappingPromptPublisher,
    publication_input_from_asset,
)


_CONTENT = "Map exactly one " + PROMPT_PLACEHOLDER + "."


class _PromptForm:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


def test_asset_input_uses_the_single_v13_prompt_and_requires_its_marker(tmp_path: Path):
    asset = tmp_path / "broker_reports_ordinary_trade_mapping_prompt.v13.md"
    asset.write_text(_CONTENT, encoding="utf-8")

    request = publication_input_from_asset(actor_user_id="admin", asset_root=tmp_path)

    assert request.actor_user_id == "admin"
    assert request.content == _CONTENT
    asset.write_text("no marker", encoding="utf-8")
    with pytest.raises(OrdinaryTradeMappingPromptPublicationError) as invalid:
        publication_input_from_asset(actor_user_id="admin", asset_root=tmp_path)
    assert invalid.value.code == "ordinary_trade_mapping_prompt_asset_contract_invalid"


def test_create_uses_native_prompt_lifecycle_and_returns_only_valve_safe_pin(monkeypatch):
    publisher = OrdinaryTradeMappingPromptPublisher()
    owner = _native_owner(existing=None)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(
        publisher.publish(
            OrdinaryTradeMappingPromptPublicationInput(
                actor_user_id="admin", content=_CONTENT
            )
        )
    )

    assert owner["prompts"].inserted is not None
    assert owner["prompts"].updated is None
    assert owner["prompts"].inserted.access_grants == [
        {"principal_type": "user", "principal_id": "*", "permission": "read"}
    ]
    assert result.action == "created"
    assert result.prompt_history_id == "history-created"
    assert result.pipe_valves() == {
        "ordinary_trade_mapping_prompt_id": "prompt-1",
        "ordinary_trade_mapping_prompt_command": "broker_ordinary_trade_semantic_mapping_v1",
        "ordinary_trade_mapping_prompt_version": "history-created",
        "ordinary_trade_mapping_prompt_hash": result.prompt_hash,
    }
    assert "content" not in result.pipe_valves()


def test_update_preserves_existing_public_grant_and_checks_native_history(monkeypatch):
    existing = _row(
        version_id="history-before",
        content="Old map " + PROMPT_PLACEHOLDER + ".",
    )
    existing["access_grants"] = [
        {"principal_type": "user", "principal_id": "*", "permission": "read"}
    ]
    publisher = OrdinaryTradeMappingPromptPublisher()
    owner = _native_owner(existing=existing)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(
        publisher.publish(
            OrdinaryTradeMappingPromptPublicationInput(
                actor_user_id="admin", content=_CONTENT
            )
        )
    )

    assert result.action == "updated"
    assert owner["prompts"].inserted is None
    assert owner["prompts"].updated.access_grants is None
    assert result.prompt_history_id == "history-updated"


def test_existing_non_public_prompt_is_not_silently_regranted(monkeypatch):
    existing = _row(version_id="history-before")
    existing["access_grants"] = []
    publisher = OrdinaryTradeMappingPromptPublisher()
    owner = _native_owner(existing=existing)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    with pytest.raises(OrdinaryTradeMappingPromptPublicationError) as rejected:
        asyncio.run(
            publisher.publish(
                OrdinaryTradeMappingPromptPublicationInput(
                    actor_user_id="admin", content=_CONTENT
                )
            )
        )

    assert rejected.value.code == "ordinary_trade_mapping_prompt_public_grant_required"
    assert owner["prompts"].updated is None


def test_matching_current_prompt_is_pinned_without_a_spurious_update(monkeypatch):
    publisher = OrdinaryTradeMappingPromptPublisher()
    owner = _native_owner(existing=_row(version_id="history-current"))
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(
        publisher.publish(
            OrdinaryTradeMappingPromptPublicationInput(
                actor_user_id="admin", content=_CONTENT
            )
        )
    )

    assert result.action == "pinned"
    assert owner["prompts"].inserted is None
    assert owner["prompts"].updated is None


def test_foreign_or_drifted_history_is_not_returned_as_a_pin(monkeypatch):
    publisher = OrdinaryTradeMappingPromptPublisher()
    owner = _native_owner(existing=None, history_prompt_id="foreign")
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    with pytest.raises(OrdinaryTradeMappingPromptPublicationError) as rejected:
        asyncio.run(
            publisher.publish(
                OrdinaryTradeMappingPromptPublicationInput(
                    actor_user_id="admin", content=_CONTENT
                )
            )
        )

    assert rejected.value.code == "ordinary_trade_mapping_prompt_publication_history_missing"


def test_reverification_rejects_a_pin_when_native_history_belongs_to_another_prompt(
    monkeypatch,
):
    publisher = OrdinaryTradeMappingPromptPublisher()
    owner = _native_owner(existing=_row(version_id="history-current"), history_prompt_id="foreign")
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    with pytest.raises(OrdinaryTradeMappingPromptPublicationError) as rejected:
        asyncio.run(
            publisher.verify(
                OrdinaryTradeMappingPromptPublication(
                    prompt_ref="prompt-1",
                    prompt_command="broker_ordinary_trade_semantic_mapping_v1",
                    prompt_history_id="history-current",
                    prompt_hash="a" * 64,
                    action="released",
                )
            )
        )

    assert rejected.value.code == "ordinary_trade_mapping_prompt_publication_history_missing"


def _native_owner(*, existing, history_prompt_id=None):
    @asynccontextmanager
    async def context():
        yield "session"

    class Prompts:
        inserted = None
        updated = None

        async def get_prompt_by_command(self, command, *, db):
            assert command == "broker_ordinary_trade_semantic_mapping_v1"
            assert db == "session"
            return _model(existing) if existing is not None else None

        async def insert_new_prompt(self, user_id, form, *, db):
            assert user_id == "admin" and db == "session"
            self.inserted = form
            return _model(_row(version_id="history-created", content=form.content))

        async def update_prompt_by_id(self, prompt_id, form, user_id, *, db):
            assert prompt_id == "prompt-1" and user_id == "admin" and db == "session"
            self.updated = form
            return _model(_row(version_id="history-updated", content=form.content))

    prompts = Prompts()

    class Histories:
        async def get_history_entry_by_id(self, history_id, *, db):
            assert db == "session"
            return SimpleNamespace(
                prompt_id=history_prompt_id or "prompt-1",
                snapshot=_snapshot(_CONTENT),
            )

    return {
        "get_async_db_context": context,
        "prompt_form": _PromptForm,
        "prompts": prompts,
        "prompt_histories": Histories(),
    }


def _model(row):
    return SimpleNamespace(model_dump=lambda: dict(row))


def _row(*, version_id, content=_CONTENT):
    from broker_reports_gate1.ordinary_trade_mapping_prompt_publication import _metadata

    return {
        "id": "prompt-1",
        "command": "broker_ordinary_trade_semantic_mapping_v1",
        "name": "Broker Reports ordinary-trade semantic mapping",
        "content": content,
        "data": {"managed_asset_version": "v13"},
        "meta": _metadata(),
        "tags": ["broker-reports-ordinary-trade-mapping"],
        "version_id": version_id,
        "access_grants": [
            {
                "principal_type": "user",
                "principal_id": "*",
                "permission": "read",
            }
        ],
    }


def _snapshot(content):
    from broker_reports_gate1.ordinary_trade_mapping_prompt_publication import _metadata

    return {
        "name": "Broker Reports ordinary-trade semantic mapping",
        "content": content,
        "command": "broker_ordinary_trade_semantic_mapping_v1",
        "data": {"managed_asset_version": "v13"},
        "meta": _metadata(),
        "tags": ["broker-reports-ordinary-trade-mapping"],
    }
