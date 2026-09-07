import json
import sqlite3
import uuid

import pytest

from broker_reports_gate1.ordinary_trade_mapping_prompt import (
    INPUT_SCHEMA_VERSION,
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


def test_workspace_resolver_rejects_foreign_or_drifted_active_history(tmp_path):
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
    with pytest.raises(OrdinaryTradeMappingPromptError) as drift:
        resolver.resolve(_user("owner"))
    assert drift.value.code == "ordinary_trade_mapping_prompt_version_drift"


def test_workspace_resolver_fails_closed_for_inactive_or_wrong_contract(tmp_path):
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
    with pytest.raises(OrdinaryTradeMappingPromptError) as wrong_contract:
        resolver.resolve(_user("owner"))
    assert wrong_contract.value.code == "ordinary_trade_mapping_prompt_not_found"


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


def _resolver(db_path):
    return OrdinaryTradeMappingPromptResolverFactory(
        OrdinaryTradeMappingPromptConfig(db_path=db_path, prompt_id="mapping-prompt")
    ).create()


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


def _insert_prompt(path, *, content, grants, active=True):
    snapshot = _snapshot(content)
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
                "mapping-prompt", PROMPT_COMMAND, "owner", "Mapping prompt", content,
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


def _snapshot(content):
    return {
        "command": PROMPT_COMMAND,
        "content": content,
        "meta": _meta(),
        "tags": [PROMPT_REQUIRED_TAG],
    }
