from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from broker_reports_gate1.ordinary_trade_mapping_prompt import (
    ORDINARY_TRADE_MAPPING_V14_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V15_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V17_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V19_COMPACT_RESPONSE_SCHEMA_VERSION,
    PROMPT_PLACEHOLDER,
    ordinary_trade_mapping_prompt_hash,
)
from broker_reports_gate1.ordinary_trade_mapping_prompt_publication import (
    GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE,
    ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE,
    ORDINARY_TRADE_MAPPING_V14_PROFILE,
    ORDINARY_TRADE_MAPPING_V15_PROFILE,
    ORDINARY_TRADE_MAPPING_V16_PROFILE,
    ORDINARY_TRADE_MAPPING_V17_PROFILE,
    ORDINARY_TRADE_MAPPING_V18_PROFILE,
    ORDINARY_TRADE_MAPPING_V19_PROFILE,
    PDF_TABLE_CONTINUATION_ANNOTATION_V3_PROFILE,
    DOCUMENT_METADATA_PASSPORT_V1_PROFILE,
    OrdinaryTradeMappingPromptPublication,
    OrdinaryTradeMappingPromptPublicationError,
    OrdinaryTradeMappingPromptPublicationInput,
    OrdinaryTradeMappingPromptPublisher,
    publication_input_from_asset,
)
from broker_reports_gate1.pdf_table_continuation_annotation_prompt import (
    pdf_table_continuation_annotation_prompt_hash,
)


_CONTENT = "Map exactly one " + PROMPT_PLACEHOLDER + "."
_V14_PROMPT_ASSET = (
    Path(__file__).resolve().parents[1]
    / "managed_assets"
    / "prompts"
    / "goal391_grouped_mapping_lab_prompt.v14.md"
)


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


def test_closed_v14_lab_profile_publishes_a_distinct_non_product_prompt(
    monkeypatch, tmp_path: Path
):
    profile = GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE
    (tmp_path / profile.asset_filename).write_text(_CONTENT, encoding="utf-8")
    request = publication_input_from_asset(
        actor_user_id="admin", asset_root=tmp_path, profile=profile
    )
    publisher = OrdinaryTradeMappingPromptPublisher(profile=profile)
    owner = _native_owner(existing=None, profile=profile)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(publisher.publish(request))

    assert owner["prompts"].inserted.command == profile.command
    assert owner["prompts"].inserted.name == profile.name
    assert owner["prompts"].inserted.meta["output_schema_id"] == profile.output_schema_id
    assert owner["prompts"].inserted.is_production is False
    assert owner["prompts"].inserted.access_grants == [
        {"principal_type": "user", "principal_id": "*", "permission": "read"}
    ]
    assert result.safe_pin()["prompt_command"] == profile.command
    assert result.prompt_hash != ordinary_trade_mapping_prompt_hash(_CONTENT)


def test_closed_v14_production_profile_publishes_a_distinct_compact_prompt(
    monkeypatch, tmp_path: Path
):
    profile = ORDINARY_TRADE_MAPPING_V14_PROFILE
    (tmp_path / profile.asset_filename).write_text(_CONTENT, encoding="utf-8")
    request = publication_input_from_asset(
        actor_user_id="admin", asset_root=tmp_path, profile=profile
    )
    publisher = OrdinaryTradeMappingPromptPublisher(profile=profile)
    owner = _native_owner(existing=None, profile=profile)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(publisher.publish(request))

    assert profile.profile_id == "ordinary_trade_mapping_v14"
    assert profile.command == "broker_ordinary_trade_semantic_mapping_v14"
    assert profile.command != GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE.command
    assert profile.is_production is True
    assert profile.output_schema_id == ORDINARY_TRADE_MAPPING_V14_COMPACT_RESPONSE_SCHEMA_VERSION
    assert owner["prompts"].inserted.command == profile.command
    assert owner["prompts"].inserted.is_production is True
    assert result.safe_pin()["prompt_command"] == profile.command


def test_v14_production_asset_is_distinct_from_lab_and_carries_currency_guard():
    root = _V14_PROMPT_ASSET.parent
    content = (root / ORDINARY_TRADE_MAPPING_V14_PROFILE.asset_filename).read_text(
        encoding="utf-8"
    )

    assert "strict compact ordinary-trade" in content
    assert "amount_currency_bindings" in content
    assert "currency_column classified as currency" in content
    assert "SECURITY_TRADES_INCOMPLETE rather than COMPLETE" in content
    assert "grouped lab" not in content


def test_closed_v15_profile_is_distinct_and_marks_headerless_segments_terminal(
    monkeypatch, tmp_path: Path
):
    profile = ORDINARY_TRADE_MAPPING_V15_PROFILE
    (tmp_path / profile.asset_filename).write_text(_CONTENT, encoding="utf-8")
    publisher = OrdinaryTradeMappingPromptPublisher(profile=profile)
    owner = _native_owner(existing=None, profile=profile)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(
        publisher.publish(
            publication_input_from_asset(
                actor_user_id="admin", asset_root=tmp_path, profile=profile
            )
        )
    )

    asset = (_V14_PROMPT_ASSET.parent / profile.asset_filename).read_text(
        encoding="utf-8"
    )
    assert profile.profile_id == "ordinary_trade_mapping_v15"
    assert profile.output_schema_id == ORDINARY_TRADE_MAPPING_V15_COMPACT_RESPONSE_SCHEMA_VERSION
    assert profile.command != ORDINARY_TRADE_MAPPING_V14_PROFILE.command
    assert "physical_header_row is null" in asset
    assert "HEADER_ABSENT" in asset
    assert result.safe_pin()["prompt_command"] == profile.command


def test_closed_v16_profile_publishes_the_document_opening_input_contract(
    monkeypatch, tmp_path: Path
):
    profile = ORDINARY_TRADE_MAPPING_V16_PROFILE
    (tmp_path / profile.asset_filename).write_text(_CONTENT, encoding="utf-8")
    publisher = OrdinaryTradeMappingPromptPublisher(profile=profile)
    owner = _native_owner(existing=None, profile=profile)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(
        publisher.publish(
            publication_input_from_asset(
                actor_user_id="admin", asset_root=tmp_path, profile=profile
            )
        )
    )

    asset = (_V14_PROMPT_ASSET.parent / profile.asset_filename).read_text(
        encoding="utf-8"
    )
    assert profile.profile_id == "ordinary_trade_mapping_v16"
    assert profile.output_schema_id == ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION
    assert "DOCUMENT_OPENING" in asset
    assert owner["prompts"].inserted.meta["input_contract"] == profile.input_schema_version
    assert result.safe_pin()["prompt_command"] == profile.command


def test_closed_v17_profile_is_separate_and_forbids_direction_from_numeric_sign(
    monkeypatch, tmp_path: Path
):
    profile = ORDINARY_TRADE_MAPPING_V17_PROFILE
    (tmp_path / profile.asset_filename).write_text(_CONTENT, encoding="utf-8")
    publisher = OrdinaryTradeMappingPromptPublisher(profile=profile)
    owner = _native_owner(existing=None, profile=profile)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(
        publisher.publish(
            publication_input_from_asset(
                actor_user_id="admin", asset_root=tmp_path, profile=profile
            )
        )
    )

    asset = (_V14_PROMPT_ASSET.parent / profile.asset_filename).read_text(
        encoding="utf-8"
    )
    assert profile.profile_id == "ordinary_trade_mapping_v17"
    assert profile.output_schema_id == ORDINARY_TRADE_MAPPING_V17_COMPACT_RESPONSE_SCHEMA_VERSION
    assert "Never infer\ndirection from a numeric sign" in asset
    assert "SECURITY_TRADES_INCOMPLETE without a side column" in asset
    assert "explicit_header_source_claims" in asset
    assert "physical continuation link" in asset
    assert result.safe_pin()["prompt_command"] == profile.command


def test_closed_v19_profile_is_immutable_successor_with_same_cell_evidence_rule(
    monkeypatch, tmp_path: Path
):
    profile = ORDINARY_TRADE_MAPPING_V19_PROFILE
    (tmp_path / profile.asset_filename).write_text(_CONTENT, encoding="utf-8")
    publisher = OrdinaryTradeMappingPromptPublisher(profile=profile)
    owner = _native_owner(existing=None, profile=profile)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(
        publisher.publish(
            publication_input_from_asset(
                actor_user_id="admin", asset_root=tmp_path, profile=profile
            )
        )
    )

    asset = (_V14_PROMPT_ASSET.parent / profile.asset_filename).read_text(
        encoding="utf-8"
    )
    assert profile.profile_id == "ordinary_trade_mapping_v19"
    assert profile.command != ORDINARY_TRADE_MAPPING_V18_PROFILE.command
    assert profile.output_schema_id == ORDINARY_TRADE_MAPPING_V19_COMPACT_RESPONSE_SCHEMA_VERSION
    assert "position_effect_evidence" in asset
    assert "same source cell" in asset
    assert result.safe_pin()["prompt_command"] == profile.command


def test_closed_physical_table_profile_publishes_native_instruction_without_mapping_placeholder(
    monkeypatch, tmp_path: Path
):
    profile = PDF_TABLE_CONTINUATION_ANNOTATION_V3_PROFILE
    content = "Assess physical table continuations only."
    (tmp_path / profile.asset_filename).write_text(content, encoding="utf-8")
    publisher = OrdinaryTradeMappingPromptPublisher(profile=profile)
    owner = _native_owner(existing=None, profile=profile)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(
        publisher.publish(
            publication_input_from_asset(
                actor_user_id="admin", asset_root=tmp_path, profile=profile
            )
        )
    )

    assert profile.placeholder is None
    assert owner["prompts"].inserted.meta["annotation_domain"] == (
        "physical_table_continuation"
    )
    assert "mapping_domain" not in owner["prompts"].inserted.meta
    assert owner["prompts"].inserted.access_grants == [
        {"principal_type": "user", "principal_id": "*", "permission": "read"}
    ]
    assert result.safe_pin()["prompt_command"] == profile.command
    assert result.prompt_hash == pdf_table_continuation_annotation_prompt_hash(content)


def test_repository_physical_table_asset_is_bound_to_its_closed_profile() -> None:
    profile = PDF_TABLE_CONTINUATION_ANNOTATION_V3_PROFILE
    asset_root = _V14_PROMPT_ASSET.parent

    request = publication_input_from_asset(
        actor_user_id="admin", asset_root=asset_root, profile=profile
    )

    assert profile.placeholder is None
    assert request.content == (asset_root / profile.asset_filename).read_text(
        encoding="utf-8"
    )
    assert "physical table" in request.content
    assert "{{" not in request.content


def test_document_passport_profile_is_native_public_and_has_one_private_input_marker(
    monkeypatch, tmp_path: Path
):
    profile = DOCUMENT_METADATA_PASSPORT_V1_PROFILE
    content = "Classify {{document_package_json}} once."
    (tmp_path / profile.asset_filename).write_text(content, encoding="utf-8")
    publisher = OrdinaryTradeMappingPromptPublisher(profile=profile)
    owner = _native_owner(existing=None, profile=profile)
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(
        publisher.publish(
            publication_input_from_asset(
                actor_user_id="admin", asset_root=tmp_path, profile=profile
            )
        )
    )

    assert profile.command == "broker_gate1_document_passport_v1"
    assert "mapping_domain" not in owner["prompts"].inserted.meta
    assert owner["prompts"].inserted.meta["gate"] == "gate1"
    assert owner["prompts"].inserted.access_grants == [
        {"principal_type": "user", "principal_id": "*", "permission": "read"}
    ]
    assert result.safe_pin()["prompt_command"] == profile.command


def test_v14_managed_prompt_requires_complete_document_currency_bindings():
    content = _V14_PROMPT_ASSET.read_text(encoding="utf-8")

    assert "every column classified as gross_amount" in content
    assert "amount_currency_bindings" in content
    assert "currency_column classified as currency" in content
    assert "ascending amount_column" in content


def test_closed_v14_lab_profile_never_updates_a_v13_prompt(monkeypatch):
    publisher = OrdinaryTradeMappingPromptPublisher(
        profile=GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE
    )
    owner = _native_owner(
        existing=_row(
            version_id="history-v13",
            profile=ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE,
        ),
        profile=GOAL391_GROUPED_MAPPING_LAB_V14_PROFILE,
    )
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    with pytest.raises(OrdinaryTradeMappingPromptPublicationError) as rejected:
        asyncio.run(
            publisher.publish(
                OrdinaryTradeMappingPromptPublicationInput(
                    actor_user_id="admin", content=_CONTENT
                )
            )
        )

    assert rejected.value.code == "ordinary_trade_mapping_prompt_existing_metadata_incompatible"
    assert owner["prompts"].updated is None


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
    assert not hasattr(owner["prompts"].updated, "access_grants")
    assert result.prompt_history_id == "history-updated"


def test_exact_v12_prompt_is_migrated_through_one_native_history_update(monkeypatch):
    existing = _row(
        version_id="history-v12",
        content="Old map " + PROMPT_PLACEHOLDER + ".",
    )
    existing.update(
        {
            "name": "Broker Reports Ordinary Trade Mapping",
            "data": {},
            "meta": _legacy_v12_metadata(),
        }
    )
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

    assert result.action == "migrated"
    assert owner["prompts"].updated is not None
    assert not hasattr(owner["prompts"].updated, "access_grants")
    assert owner["prompts"].updated.data == {"managed_asset_version": "v13"}


def test_unknown_existing_metadata_is_not_migrated(monkeypatch):
    existing = _row(version_id="history-before")
    existing["meta"] = {"unknown": "metadata"}
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

    assert rejected.value.code == "ordinary_trade_mapping_prompt_existing_metadata_incompatible"
    assert owner["prompts"].updated is None


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


def test_pinned_prompt_uses_native_latest_history_when_row_version_is_stale(monkeypatch):
    publisher = OrdinaryTradeMappingPromptPublisher()
    owner = _native_owner(
        existing=_row(version_id="history-stale"), latest_history_id="history-latest"
    )
    monkeypatch.setattr(publisher, "_native_owners", lambda: owner)

    result = asyncio.run(
        publisher.publish(
            OrdinaryTradeMappingPromptPublicationInput(
                actor_user_id="admin", content=_CONTENT
            )
        )
    )

    assert result.action == "pinned"
    assert result.prompt_history_id == "history-latest"


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


def _native_owner(
    *,
    existing,
    history_prompt_id=None,
    latest_history_id=None,
    profile=ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE,
):
    initial_history_id = latest_history_id or (
        str(existing["version_id"]) if existing is not None else "history-created"
    )

    @asynccontextmanager
    async def context():
        yield "session"

    class Prompts:
        inserted = None
        updated = None
        latest_history_id = initial_history_id
        latest_content = str(existing["content"]) if existing is not None else _CONTENT

        async def get_prompt_by_command(self, command, *, db):
            assert command == profile.command
            assert db == "session"
            return _model(existing) if existing is not None else None

        async def insert_new_prompt(self, user_id, form, *, db):
            assert user_id == "admin" and db == "session"
            self.inserted = form
            self.latest_history_id = "history-created"
            self.latest_content = form.content
            return _model(
                _row(
                    version_id="history-created", content=form.content, profile=profile
                )
            )

        async def update_prompt_by_id(self, prompt_id, form, user_id, *, db):
            assert prompt_id == "prompt-1" and user_id == "admin" and db == "session"
            self.updated = form
            self.latest_history_id = "history-updated"
            self.latest_content = form.content
            return _model(
                _row(
                    version_id="history-updated", content=form.content, profile=profile
                )
            )

    prompts = Prompts()

    class Histories:
        async def get_latest_history_entry(self, prompt_id, *, db):
            assert db == "session"
            assert prompt_id == "prompt-1"
            return SimpleNamespace(
                id=prompts.latest_history_id,
                prompt_id=history_prompt_id or "prompt-1",
                snapshot=_snapshot(prompts.latest_content, profile=profile),
            )

    return {
        "get_async_db_context": context,
        "prompt_form": _PromptForm,
        "prompts": prompts,
        "prompt_histories": Histories(),
    }


def _model(row):
    return SimpleNamespace(model_dump=lambda: dict(row))


def _row(
    *,
    version_id,
    content=_CONTENT,
    profile=ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE,
):
    from broker_reports_gate1.ordinary_trade_mapping_prompt_publication import _metadata

    return {
        "id": "prompt-1",
        "command": profile.command,
        "name": profile.name,
        "content": content,
        "data": {"managed_asset_version": profile.asset_version},
        "meta": _metadata(profile=profile),
        "tags": [profile.required_tag],
        "version_id": version_id,
        "access_grants": [
            {
                "principal_type": "user",
                "principal_id": "*",
                "permission": "read",
            }
        ],
    }


def _snapshot(content, *, profile=ORDINARY_TRADE_MAPPING_PROMPT_V13_PROFILE):
    from broker_reports_gate1.ordinary_trade_mapping_prompt_publication import _metadata

    return {
        "name": profile.name,
        "content": content,
        "command": profile.command,
        "data": {"managed_asset_version": profile.asset_version},
        "meta": _metadata(profile=profile),
        "tags": [profile.required_tag],
    }


def _legacy_v12_metadata():
    from broker_reports_gate1.ordinary_trade_mapping_prompt import (
        INPUT_SCHEMA_VERSION,
        PROMPT_CONTRACT_ID,
        PROMPT_TEMPLATE_ID,
        PROMPT_TEMPLATE_KIND,
    )

    return {
        "template_id": PROMPT_TEMPLATE_ID,
        "template_kind": PROMPT_TEMPLATE_KIND,
        "prompt_contract_id": PROMPT_CONTRACT_ID,
        "input_contract": INPUT_SCHEMA_VERSION,
        "output_schema_id": "broker_reports_ordinary_trade_semantic_mapping_response_v12",
        "output_schema_version": "broker_reports_ordinary_trade_semantic_mapping_response_v12",
        "structured_output_required": True,
        "mapping_domain": "ordinary_trade",
    }
