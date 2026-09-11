import asyncio
import json
import sqlite3
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from broker_reports_gate1.ordinary_trade_mapping_prompt import (
    DOCUMENT_OPENING_INPUT_SCHEMA_VERSION,
    INPUT_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V14_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V14_PROMPT_COMMAND,
    ORDINARY_TRADE_MAPPING_V14_PROMPT_REQUIRED_TAG,
    ORDINARY_TRADE_MAPPING_V14_PROMPT_TEMPLATE_ID,
    ORDINARY_TRADE_MAPPING_V14_PROMPT_TEMPLATE_KIND,
    ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_COMMAND,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_REQUIRED_TAG,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_ID,
    ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_KIND,
    ORDINARY_TRADE_MAPPING_V17_COMPACT_RESPONSE_SCHEMA_VERSION,
    ORDINARY_TRADE_MAPPING_V17_PROMPT_COMMAND,
    ORDINARY_TRADE_MAPPING_V17_PROMPT_REQUIRED_TAG,
    ORDINARY_TRADE_MAPPING_V17_PROMPT_TEMPLATE_ID,
    ORDINARY_TRADE_MAPPING_V17_PROMPT_TEMPLATE_KIND,
    OUTPUT_SCHEMA_ID,
    OUTPUT_SCHEMA_VERSION,
    PROMPT_COMMAND,
    PROMPT_CONTRACT_ID,
    PROMPT_REQUIRED_TAG,
    PROMPT_TEMPLATE_ID,
    PROMPT_TEMPLATE_KIND,
    DisabledOrdinaryTradeMappingPromptResolver,
    OrdinaryTradeMappingManagedPrompt,
    OrdinaryTradeMappingPromptConfig,
    OrdinaryTradeMappingPromptError,
    OrdinaryTradeMappingPromptResolverFactory,
    OrdinaryTradeMappingPromptUserContext,
    StaticOrdinaryTradeMappingPromptResolver,
    ordinary_trade_mapping_prompt_hash,
    validate_ordinary_trade_mapping_prompt_snapshot,
)


def test_workspace_resolver_returns_version_pinned_safe_snapshot_for_owner(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_db(db_path)
    content = "Classify only {{ordinary_trade_mapping_case_json}} as strict JSON."
    _insert_prompt(db_path, content=content, grants=[])

    resolved = _resolver(db_path).resolve(_user("owner"))

    assert resolved.content == content
    assert resolved.hash == ordinary_trade_mapping_prompt_hash(content)
    assert resolved.version == "history-1"
    snapshot = resolved.snapshot()
    assert snapshot["prompt_ref"] == "mapping-prompt"
    assert snapshot["prompt_version"] == "history-1"
    assert snapshot["prompt_hash"] == resolved.hash
    assert snapshot["prompt_source"] == "openwebui_prompt_history"
    assert content not in json.dumps(snapshot)
    assert validate_ordinary_trade_mapping_prompt_snapshot(snapshot) == snapshot


def test_workspace_resolver_enforces_public_group_and_denied_access(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_db(db_path)
    _insert_prompt(
        db_path,
        content="Map {{ordinary_trade_mapping_case_json}}.",
        grants=[("group", "finance", "read")],
    )
    _insert_group_member(db_path, user_id="group-user", group_id="finance")
    resolver = _resolver(db_path)

    # Membership comes from the OpenWebUI group_member owner; an untrusted
    # caller-supplied group list cannot grant access by itself.
    assert resolver.resolve(_user("group-user", groups=("untrusted",))).prompt_ref == "mapping-prompt"
    with pytest.raises(OrdinaryTradeMappingPromptError) as not_public:
        resolver.resolve(_user("public-user"))
    assert not_public.value.code == "ordinary_trade_mapping_prompt_access_denied"

    _replace_grants(db_path, [("user", "*", "read")])
    assert resolver.resolve(_user("public-user")).prompt_ref == "mapping-prompt"

    _replace_grants(db_path, [])
    with pytest.raises(OrdinaryTradeMappingPromptError) as denied:
        resolver.resolve(_user("foreign"))
    assert denied.value.code == "ordinary_trade_mapping_prompt_access_denied"


def test_workspace_resolver_rejects_foreign_pinned_history_but_uses_its_snapshot(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_db(db_path)
    content = "Map {{ordinary_trade_mapping_case_json}}."
    _insert_prompt(db_path, content=content, grants=[])
    resolver = _resolver(db_path)

    _replace_history(db_path, prompt_id="foreign-prompt", snapshot=_snapshot(content))
    with pytest.raises(OrdinaryTradeMappingPromptError) as foreign:
        resolver.resolve(_user("owner"))
    assert foreign.value.code == "ordinary_trade_mapping_prompt_version_invalid"

    _replace_history(db_path, prompt_id="mapping-prompt", snapshot=_snapshot(content))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE prompt SET content = ? WHERE id = ?",
            ("Draft {{ordinary_trade_mapping_case_json}}.", "mapping-prompt"),
        )
        conn.commit()
    resolved = resolver.resolve(_user("owner"))
    assert resolved.content == content
    assert resolved.version == "history-1"


def test_workspace_resolver_keeps_the_approved_history_when_active_row_advances(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_db(db_path)
    approved_content = "Map {{ordinary_trade_mapping_case_json}}."
    replacement_content = "Classify {{ordinary_trade_mapping_case_json}} strictly."
    _insert_prompt(db_path, content=approved_content, grants=[])
    resolver = _resolver(db_path)

    # Simulate a legitimate Workspace edit: current row and active history are
    # internally consistent, and all command/metadata contract fields remain
    # valid. It still requires a new release approval.
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE prompt SET content = ?, version_id = ? WHERE id = ?",
            (replacement_content, "history-2", "mapping-prompt"),
        )
        conn.execute(
            "INSERT INTO prompt_history(id, prompt_id, snapshot) VALUES (?, ?, ?)",
            ("history-2", "mapping-prompt", json.dumps(_snapshot(replacement_content))),
        )
        conn.commit()

    resolved = resolver.resolve(_user("owner"))
    assert resolved.content == approved_content
    assert resolved.version == "history-1"


def test_workspace_resolver_uses_active_row_for_access_and_pinned_history_for_contract(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_db(db_path)
    _insert_prompt(db_path, content="Map {{ordinary_trade_mapping_case_json}}.", grants=[])
    resolver = _resolver(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE prompt SET is_active = 0 WHERE id = ?", ("mapping-prompt",))
        conn.commit()
    with pytest.raises(OrdinaryTradeMappingPromptError) as inactive:
        resolver.resolve(_user("owner"))
    assert inactive.value.code == "ordinary_trade_mapping_prompt_not_found"

    _insert_prompt(db_path, content="Map {{ordinary_trade_mapping_case_json}}.", grants=[], active=True)
    with sqlite3.connect(db_path) as conn:
        meta = _meta()
        meta["output_schema_version"] = "foreign"
        conn.execute("UPDATE prompt SET meta = ? WHERE id = ?", (json.dumps(meta), "mapping-prompt"))
        conn.commit()
    assert resolver.resolve(_user("owner")).prompt_ref == "mapping-prompt"

    with sqlite3.connect(db_path) as conn:
        legacy = _meta()
        legacy["output_schema_id"] = (
            "broker_reports_ordinary_trade_semantic_mapping_response_v6"
        )
        legacy["output_schema_version"] = legacy["output_schema_id"]
        conn.execute(
            "UPDATE prompt SET meta = ? WHERE id = ?",
            (json.dumps(legacy), "mapping-prompt"),
        )
        conn.commit()
    assert resolver.resolve(_user("owner")).prompt_ref == "mapping-prompt"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE prompt SET command = ? WHERE id = ?",
            ("foreign-command", "mapping-prompt"),
        )
        conn.commit()
    with pytest.raises(OrdinaryTradeMappingPromptError) as wrong_identity:
        resolver.resolve(_user("owner"))
    assert wrong_identity.value.code == "ordinary_trade_mapping_prompt_not_found"


def test_static_and_disabled_helpers_are_typed_and_require_authenticated_user():
    prompt = OrdinaryTradeMappingManagedPrompt(
        prompt_ref="test-prompt",
        command=PROMPT_COMMAND,
        version="test-version",
        content="Map {{ordinary_trade_mapping_case_json}}.",
        hash="a" * 64,
        source="test",
        template_id=PROMPT_TEMPLATE_ID,
        template_kind=PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PROMPT_CONTRACT_ID,
        input_schema_version=INPUT_SCHEMA_VERSION,
        output_schema_id=OUTPUT_SCHEMA_ID,
        output_schema_version=OUTPUT_SCHEMA_VERSION,
        tags=(PROMPT_REQUIRED_TAG,),
        safe_metadata={},
    )
    static = StaticOrdinaryTradeMappingPromptResolver(prompt)
    assert static.resolve(_user("ordinary")).prompt_ref == "test-prompt"
    with pytest.raises(OrdinaryTradeMappingPromptError) as unauthenticated:
        static.resolve(_user(""))
    assert unauthenticated.value.code == "ordinary_trade_mapping_prompt_access_denied"
    with pytest.raises(OrdinaryTradeMappingPromptError) as disabled:
        DisabledOrdinaryTradeMappingPromptResolver().resolve(_user("ordinary"))
    assert disabled.value.code == "ordinary_trade_mapping_prompt_disabled"


def test_native_server_resolver_uses_openwebui_owners_for_direct_test_user_grant(
    monkeypatch,
):
    content = "Map {{ordinary_trade_mapping_case_json}}."
    calls = []
    resolver = _server_resolver(content)
    _install_native_owners(
        monkeypatch,
        resolver,
        content=content,
        access=lambda *args, **kwargs: calls.append((args, kwargs)) or True,
    )

    resolved = asyncio.run(resolver.resolve(_user("ordinary-user")))

    assert resolved.prompt_ref == "mapping-prompt"
    assert calls == [
        (
            ("ordinary-user", "prompt", "mapping-prompt"),
            {"permission": "read", "db": "native-session"},
        )
    ]


def test_native_server_resolver_rejects_wrong_user_before_history_read(monkeypatch):
    content = "Map {{ordinary_trade_mapping_case_json}}."
    resolver = _server_resolver(content)
    calls = {"history": 0}
    _install_native_owners(
        monkeypatch,
        resolver,
        content=content,
        access=lambda *_args, **_kwargs: False,
        calls=calls,
    )

    with pytest.raises(OrdinaryTradeMappingPromptError) as denied:
        asyncio.run(resolver.resolve(_user("wrong-user")))

    assert denied.value.code == "ordinary_trade_mapping_prompt_access_denied"
    assert calls["history"] == 0


@pytest.mark.parametrize(
    ("row_overrides", "history_prompt_id", "snapshot_content", "expected"),
    [
        ({"is_active": False}, "mapping-prompt", None, "ordinary_trade_mapping_prompt_not_found"),
        ({}, "foreign-prompt", None, "ordinary_trade_mapping_prompt_version_invalid"),
        ({}, "mapping-prompt", "Drift {{ordinary_trade_mapping_case_json}}.", "ordinary_trade_mapping_prompt_release_pin_mismatch"),
    ],
    ids=["inactive", "history-misbinding", "stale-current-row"],
)
def test_native_server_resolver_fails_closed_for_inactive_or_stale_prompt(
    monkeypatch, row_overrides, history_prompt_id, snapshot_content, expected
):
    content = "Map {{ordinary_trade_mapping_case_json}}."
    resolver = _server_resolver(content)
    _install_native_owners(
        monkeypatch,
        resolver,
        content=content,
        row_overrides=row_overrides,
        history_prompt_id=history_prompt_id,
        snapshot_content=snapshot_content,
        access=lambda *_args, **_kwargs: True,
    )

    with pytest.raises(OrdinaryTradeMappingPromptError) as invalid:
        asyncio.run(resolver.resolve(_user("ordinary-user")))

    assert invalid.value.code == expected


def test_native_server_resolver_keeps_pinned_history_when_active_prompt_advances(
    monkeypatch,
):
    approved = "Map {{ordinary_trade_mapping_case_json}}."
    replacement = "Classify {{ordinary_trade_mapping_case_json}} strictly."
    resolver = _server_resolver(approved)
    _install_native_owners(
        monkeypatch,
        resolver,
        content=replacement,
        row_overrides={"version_id": "history-2"},
        history_entries={
            "history-1": ("mapping-prompt", _snapshot(approved)),
            "history-2": ("mapping-prompt", _snapshot(replacement)),
        },
        access=lambda *_args, **_kwargs: True,
    )

    resolved = asyncio.run(resolver.resolve(_user("ordinary-user")))

    assert resolved.content == approved
    assert resolved.version == "history-1"


def test_snapshot_validator_rejects_foreign_contract_and_body_leak():
    prompt = OrdinaryTradeMappingManagedPrompt(
        prompt_ref="test-prompt", command=PROMPT_COMMAND, version="test-version",
        content="Map {{ordinary_trade_mapping_case_json}}.", hash="a" * 64,
        source="test", template_id=PROMPT_TEMPLATE_ID, template_kind=PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PROMPT_CONTRACT_ID, input_schema_version=INPUT_SCHEMA_VERSION,
        output_schema_id=OUTPUT_SCHEMA_ID, output_schema_version=OUTPUT_SCHEMA_VERSION,
        tags=(PROMPT_REQUIRED_TAG,), safe_metadata={},
    )
    malformed = prompt.snapshot()
    malformed["content"] = "forbidden"
    with pytest.raises(OrdinaryTradeMappingPromptError) as body_leak:
        validate_ordinary_trade_mapping_prompt_snapshot(malformed)
    assert body_leak.value.code == "ordinary_trade_mapping_prompt_snapshot_invalid"


def test_snapshot_validator_accepts_only_the_closed_v14_identity():
    snapshot = OrdinaryTradeMappingManagedPrompt(
        prompt_ref="test-v14-prompt",
        command=ORDINARY_TRADE_MAPPING_V14_PROMPT_COMMAND,
        version="test-v14-version",
        content="Map {{ordinary_trade_mapping_case_json}}.",
        hash="b" * 64,
        source="test",
        template_id=ORDINARY_TRADE_MAPPING_V14_PROMPT_TEMPLATE_ID,
        template_kind=ORDINARY_TRADE_MAPPING_V14_PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PROMPT_CONTRACT_ID,
        input_schema_version=INPUT_SCHEMA_VERSION,
        output_schema_id=ORDINARY_TRADE_MAPPING_V14_COMPACT_RESPONSE_SCHEMA_VERSION,
        output_schema_version=ORDINARY_TRADE_MAPPING_V14_COMPACT_RESPONSE_SCHEMA_VERSION,
        tags=(ORDINARY_TRADE_MAPPING_V14_PROMPT_REQUIRED_TAG,),
        safe_metadata={},
    ).snapshot()

    assert validate_ordinary_trade_mapping_prompt_snapshot(snapshot) == snapshot

    mixed = dict(snapshot)
    mixed["output_schema_id"] = OUTPUT_SCHEMA_ID
    mixed["output_schema_version"] = OUTPUT_SCHEMA_VERSION
    with pytest.raises(OrdinaryTradeMappingPromptError) as invalid:
        validate_ordinary_trade_mapping_prompt_snapshot(mixed)
    assert invalid.value.code == "ordinary_trade_mapping_prompt_snapshot_invalid"


def test_snapshot_validator_accepts_only_the_closed_v16_document_opening_identity():
    snapshot = OrdinaryTradeMappingManagedPrompt(
        prompt_ref="test-v16-prompt",
        command=ORDINARY_TRADE_MAPPING_V16_PROMPT_COMMAND,
        version="test-v16-version",
        content="Map {{ordinary_trade_mapping_case_json}}.",
        hash="c" * 64,
        source="test",
        template_id=ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_ID,
        template_kind=ORDINARY_TRADE_MAPPING_V16_PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PROMPT_CONTRACT_ID,
        input_schema_version=DOCUMENT_OPENING_INPUT_SCHEMA_VERSION,
        output_schema_id=ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION,
        output_schema_version=ORDINARY_TRADE_MAPPING_V16_COMPACT_RESPONSE_SCHEMA_VERSION,
        tags=(ORDINARY_TRADE_MAPPING_V16_PROMPT_REQUIRED_TAG,),
        safe_metadata={},
    ).snapshot()

    assert validate_ordinary_trade_mapping_prompt_snapshot(snapshot) == snapshot
    mixed = dict(snapshot)
    mixed["input_schema_version"] = INPUT_SCHEMA_VERSION
    with pytest.raises(OrdinaryTradeMappingPromptError) as invalid:
        validate_ordinary_trade_mapping_prompt_snapshot(mixed)
    assert invalid.value.code == "ordinary_trade_mapping_prompt_snapshot_invalid"


def test_snapshot_validator_accepts_only_the_closed_v17_direction_guard_identity():
    snapshot = OrdinaryTradeMappingManagedPrompt(
        prompt_ref="test-v17-prompt",
        command=ORDINARY_TRADE_MAPPING_V17_PROMPT_COMMAND,
        version="test-v17-version",
        content="Map {{ordinary_trade_mapping_case_json}}.",
        hash="d" * 64,
        source="test",
        template_id=ORDINARY_TRADE_MAPPING_V17_PROMPT_TEMPLATE_ID,
        template_kind=ORDINARY_TRADE_MAPPING_V17_PROMPT_TEMPLATE_KIND,
        prompt_contract_id=PROMPT_CONTRACT_ID,
        input_schema_version=DOCUMENT_OPENING_INPUT_SCHEMA_VERSION,
        output_schema_id=ORDINARY_TRADE_MAPPING_V17_COMPACT_RESPONSE_SCHEMA_VERSION,
        output_schema_version=ORDINARY_TRADE_MAPPING_V17_COMPACT_RESPONSE_SCHEMA_VERSION,
        tags=(ORDINARY_TRADE_MAPPING_V17_PROMPT_REQUIRED_TAG,),
        safe_metadata={},
    ).snapshot()

    assert validate_ordinary_trade_mapping_prompt_snapshot(snapshot) == snapshot
    mixed = dict(snapshot)
    mixed["prompt_command"] = ORDINARY_TRADE_MAPPING_V16_PROMPT_COMMAND
    with pytest.raises(OrdinaryTradeMappingPromptError) as invalid:
        validate_ordinary_trade_mapping_prompt_snapshot(mixed)
    assert invalid.value.code == "ordinary_trade_mapping_prompt_snapshot_invalid"


def _resolver(db_path):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT content, version_id FROM prompt WHERE id = ?", ("mapping-prompt",)
        ).fetchone()
    assert row is not None
    return OrdinaryTradeMappingPromptResolverFactory(
        OrdinaryTradeMappingPromptConfig(
            db_path=db_path,
            prompt_id="mapping-prompt",
            release_prompt_version=row[1],
            release_prompt_hash=ordinary_trade_mapping_prompt_hash(row[0]),
        )
    ).create()


def test_sqlite_qualification_resolver_accepts_an_explicit_candidate_command(
    tmp_path,
):
    db_path = tmp_path / "prompts.sqlite3"
    candidate_command = "broker_ordinary_trade_semantic_mapping_rnd_v23"
    _create_db(db_path)
    _insert_prompt(
        db_path,
        content="Map {{ordinary_trade_mapping_case_json}}.",
        grants=[("user", "ordinary-user", "read")],
        command=candidate_command,
    )
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT content, version_id FROM prompt WHERE id = ?", ("mapping-prompt",)
        ).fetchone()
    assert row is not None

    prompt = OrdinaryTradeMappingPromptResolverFactory(
        OrdinaryTradeMappingPromptConfig(
            db_path=db_path,
            prompt_id="mapping-prompt",
            command=None,
            required_command=candidate_command,
            release_prompt_version=row[1],
            release_prompt_hash=ordinary_trade_mapping_prompt_hash(row[0]),
        )
    ).create().resolve(_user("ordinary-user"))

    assert prompt.command == candidate_command


def _server_resolver(content):
    return OrdinaryTradeMappingPromptResolverFactory(
        OrdinaryTradeMappingPromptConfig(
            source="openwebui_server",
            prompt_id="mapping-prompt",
            release_prompt_version="history-1",
            release_prompt_hash=ordinary_trade_mapping_prompt_hash(content),
        )
    ).create_async()


def _install_native_owners(
    monkeypatch,
    resolver,
    *,
    content,
    access,
    row_overrides=None,
    history_prompt_id="mapping-prompt",
    snapshot_content=None,
    history_entries=None,
    calls=None,
):
    row = {
        "id": "mapping-prompt",
        "command": PROMPT_COMMAND,
        "user_id": "owner",
        "name": "Mapping prompt",
        "content": content,
        "data": {},
        "meta": _meta(),
        "tags": [PROMPT_REQUIRED_TAG],
        "version_id": "history-1",
        "is_active": True,
    }
    row.update(row_overrides or {})
    entries = history_entries or {
        "history-1": (
            history_prompt_id,
            _snapshot(snapshot_content or content),
        )
    }

    @asynccontextmanager
    async def context():
        yield "native-session"

    class Prompts:
        async def get_prompt_by_id(self, prompt_id, *, db):
            assert prompt_id == "mapping-prompt" and db == "native-session"
            return SimpleNamespace(model_dump=lambda: dict(row))

        async def get_prompt_by_command(self, _command, *, db):
            raise AssertionError("prompt id is required in this test")

    class PromptHistories:
        async def get_history_entry_by_id(self, history_id, *, db):
            assert history_id in entries and db == "native-session"
            if calls is not None:
                calls["history"] += 1
            prompt_id, snapshot = entries[history_id]
            return SimpleNamespace(prompt_id=prompt_id, snapshot=snapshot)

    class AccessGrants:
        async def has_access(self, *args, **kwargs):
            return access(*args, **kwargs)

    monkeypatch.setattr(
        resolver,
        "_native_owners",
        lambda: {
            "get_async_db_context": context,
            "prompts": Prompts(),
            "prompt_histories": PromptHistories(),
            "access_grants": AccessGrants(),
        },
    )


def _user(user_id, *, role="user", groups=()):
    return OrdinaryTradeMappingPromptUserContext(
        user_id=user_id, user_role=role, user_groups=groups
    )


def _create_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE prompt (
                id TEXT PRIMARY KEY, command TEXT, user_id TEXT, name TEXT,
                content TEXT, data JSON, meta JSON, tags JSON,
                version_id TEXT, is_active INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE prompt_history (
                id TEXT PRIMARY KEY, prompt_id TEXT, snapshot JSON
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE access_grant (
                id TEXT PRIMARY KEY, resource_type TEXT, resource_id TEXT,
                principal_type TEXT, principal_id TEXT, permission TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE group_member (
                id TEXT PRIMARY KEY, group_id TEXT, user_id TEXT
            )
            """
        )


def _insert_prompt(path, *, content, grants, active=True, command=PROMPT_COMMAND):
    snapshot = _snapshot(content, command=command)
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM prompt")
        conn.execute("DELETE FROM prompt_history")
        conn.execute("DELETE FROM access_grant")
        conn.execute(
            """
            INSERT INTO prompt(id, command, user_id, name, content, data, meta,
                               tags, version_id, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "mapping-prompt", command, "owner", "Mapping prompt", content,
                "{}", json.dumps(_meta()), json.dumps([PROMPT_REQUIRED_TAG]), "history-1", int(active),
            ),
        )
        conn.execute(
            "INSERT INTO prompt_history(id, prompt_id, snapshot) VALUES (?, ?, ?)",
            ("history-1", "mapping-prompt", json.dumps(snapshot)),
        )
        for principal_type, principal_id, permission in grants:
            conn.execute(
                """
                INSERT INTO access_grant(id, resource_type, resource_id,
                                         principal_type, principal_id, permission)
                VALUES (?, 'prompt', 'mapping-prompt', ?, ?, ?)
                """,
                (str(uuid.uuid4()), principal_type, principal_id, permission),
            )
        conn.commit()


def _replace_grants(path, grants):
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM access_grant")
        for principal_type, principal_id, permission in grants:
            conn.execute(
                """
                INSERT INTO access_grant(id, resource_type, resource_id,
                                         principal_type, principal_id, permission)
                VALUES (?, 'prompt', 'mapping-prompt', ?, ?, ?)
                """,
                (str(uuid.uuid4()), principal_type, principal_id, permission),
            )
        conn.commit()


def _replace_history(path, *, prompt_id, snapshot):
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM prompt_history")
        conn.execute(
            "INSERT INTO prompt_history(id, prompt_id, snapshot) VALUES (?, ?, ?)",
            ("history-1", prompt_id, json.dumps(snapshot)),
        )
        conn.commit()


def _insert_group_member(path, *, user_id, group_id):
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO group_member(id, group_id, user_id) VALUES (?, ?, ?)",
            (str(uuid.uuid4()), group_id, user_id),
        )
        conn.commit()


def _meta():
    return {
        "template_id": PROMPT_TEMPLATE_ID,
        "template_kind": PROMPT_TEMPLATE_KIND,
        "prompt_contract_id": PROMPT_CONTRACT_ID,
        "input_contract": INPUT_SCHEMA_VERSION,
        "output_schema_id": OUTPUT_SCHEMA_ID,
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "structured_output_required": True,
        "mapping_domain": "ordinary_trade",
    }


def _snapshot(content, *, command=PROMPT_COMMAND):
    return {
        "command": command,
        "content": content,
        "meta": _meta(),
        "tags": [PROMPT_REQUIRED_TAG],
    }
