import json
import sqlite3
import time
import uuid

import pytest

from stage2_stt.contracts import PromptCatalogUserContextV1
from stage2_stt.prompt_catalog import (
    PromptCatalogError,
    OpenWebUISqlitePromptCatalogAdapter,
)


def test_prompt_catalog_lists_ui_safe_templates_without_prompt_body(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_prompt_db(db_path)
    _insert_prompt(
        db_path,
        prompt_id="prompt-summary",
        command="stt-summary",
        name="Краткий пересказ",
        content="Summarize {{TRANSCRIPT_TEXT}}",
        owner_id="owner-1",
        template_id="stage2.stt.summary.v1",
        public=True,
    )
    adapter = OpenWebUISqlitePromptCatalogAdapter(db_path)

    templates = adapter.list_templates(_user("user-1"))

    assert len(templates) == 1
    template = templates[0]
    assert template.template_id == "stage2.stt.summary.v1"
    assert template.command == "stt-summary"
    assert template.label == "Краткий пересказ"
    assert template.openwebui_prompt_id == "prompt-summary"
    assert template.prompt_version == "version-prompt-summary"
    assert template.prompt_body_hash
    assert "Summarize" not in template.model_dump_json()
    assert "user:*:read" in template.access_grants


def test_prompt_catalog_resolves_body_only_inside_adapter(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_prompt_db(db_path)
    _insert_prompt(
        db_path,
        prompt_id="prompt-meeting",
        command="stt-meeting-protocol",
        name="Протокол встречи",
        content="Protocol {{TRANSCRIPT_WITH_SPEAKERS}}",
        owner_id="owner-1",
        template_id="stage2.stt.meeting_protocol.v1",
        public=True,
        requires_speakers=True,
    )
    adapter = OpenWebUISqlitePromptCatalogAdapter(db_path)

    resolved = adapter.resolve_command("stt-meeting-protocol", _user("user-1"))

    assert resolved.template.template_id == "stage2.stt.meeting_protocol.v1"
    assert resolved.template.requires_speakers is True
    assert resolved.prompt_body == "Protocol {{TRANSCRIPT_WITH_SPEAKERS}}"


def test_prompt_catalog_fails_closed_for_restricted_prompt(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_prompt_db(db_path)
    _insert_prompt(
        db_path,
        prompt_id="prompt-private",
        command="stt-summary",
        name="Краткий пересказ",
        content="Private {{TRANSCRIPT_TEXT}}",
        owner_id="owner-1",
        template_id="stage2.stt.summary.v1",
        public=False,
    )
    adapter = OpenWebUISqlitePromptCatalogAdapter(db_path)

    assert adapter.list_templates(_user("user-2")) == []
    with pytest.raises(PromptCatalogError) as denied:
        adapter.get_template("stage2.stt.summary.v1", _user("user-2"))
    assert denied.value.code == "prompt_access_denied"


def test_prompt_catalog_prompt_body_hash_changes_with_prompt_content(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_prompt_db(db_path)
    _insert_prompt(
        db_path,
        prompt_id="prompt-summary",
        command="stt-summary",
        name="Краткий пересказ",
        content="Version 1 {{TRANSCRIPT_TEXT}}",
        owner_id="owner-1",
        template_id="stage2.stt.summary.v1",
        public=True,
    )
    adapter = OpenWebUISqlitePromptCatalogAdapter(db_path)
    before = adapter.get_template("stage2.stt.summary.v1", _user("user-1")).template

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE prompt SET content = ?, version_id = ? WHERE id = ?",
            ("Version 2 {{TRANSCRIPT_TEXT}}", "version-2", "prompt-summary"),
        )
        conn.commit()

    after = adapter.get_template("stage2.stt.summary.v1", _user("user-1")).template
    assert after.prompt_version == "version-2"
    assert after.prompt_body_hash != before.prompt_body_hash


def test_prompt_catalog_deleted_prompt_is_typed_not_found(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_prompt_db(db_path)
    _insert_prompt(
        db_path,
        prompt_id="prompt-summary",
        command="stt-summary",
        name="РљСЂР°С‚РєРёР№ РїРµСЂРµСЃРєР°Р·",
        content="Summarize {{TRANSCRIPT_TEXT}}",
        owner_id="owner-1",
        template_id="stage2.stt.summary.v1",
        public=True,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE prompt SET is_active = 0 WHERE id = ?", ("prompt-summary",))
        conn.commit()
    adapter = OpenWebUISqlitePromptCatalogAdapter(db_path)

    with pytest.raises(PromptCatalogError) as missing:
        adapter.get_template("stage2.stt.summary.v1", _user("user-1"))
    assert missing.value.code == "prompt_not_found"
    assert adapter.list_templates(_user("user-1")) == []


def test_prompt_catalog_rename_does_not_break_stable_command_or_template_id(tmp_path):
    db_path = tmp_path / "webui.db"
    _create_prompt_db(db_path)
    _insert_prompt(
        db_path,
        prompt_id="prompt-summary",
        command="stt-summary",
        name="Old label",
        content="Summarize {{TRANSCRIPT_TEXT}}",
        owner_id="owner-1",
        template_id="stage2.stt.summary.v1",
        public=True,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE prompt SET name = ? WHERE id = ?", ("New label", "prompt-summary"))
        conn.commit()
    adapter = OpenWebUISqlitePromptCatalogAdapter(db_path)

    by_id = adapter.get_template("stage2.stt.summary.v1", _user("user-1")).template
    by_command = adapter.resolve_command("stt-summary", _user("user-1")).template

    assert by_id.openwebui_prompt_id == "prompt-summary"
    assert by_command.template_id == "stage2.stt.summary.v1"
    assert by_id.label == "New label"


def _create_prompt_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE prompt (
                id TEXT PRIMARY KEY,
                command TEXT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                content TEXT NOT NULL,
                data JSON,
                meta JSON,
                is_active BOOLEAN NOT NULL,
                version_id TEXT,
                tags JSON,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE access_grant (
                id TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                principal_type TEXT NOT NULL,
                principal_id TEXT NOT NULL,
                permission TEXT NOT NULL,
                created_at BIGINT NOT NULL
            )
            """
        )
        conn.commit()


def _insert_prompt(
    path,
    *,
    prompt_id,
    command,
    name,
    content,
    owner_id,
    template_id,
    public,
    requires_speakers=False,
):
    now = int(time.time())
    meta = {
        "template_kind": "post_processing",
        "template_id": template_id,
        "requires_speakers": requires_speakers,
        "chunkable": False,
    }
    tags = ["stage2-stt-v2", "stt-post-processing"]
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            INSERT INTO prompt(
                id, command, user_id, name, content, data, meta, is_active,
                version_id, tags, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                command,
                owner_id,
                name,
                content,
                "{}",
                json.dumps(meta),
                f"version-{prompt_id}",
                json.dumps(tags),
                now,
                now,
            ),
        )
        if public:
            conn.execute(
                """
                INSERT INTO access_grant(
                    id, resource_type, resource_id, principal_type,
                    principal_id, permission, created_at
                )
                VALUES (?, 'prompt', ?, 'user', '*', 'read', ?)
                """,
                (str(uuid.uuid4()), prompt_id, now),
            )
        conn.commit()


def _user(user_id, role="user"):
    return PromptCatalogUserContextV1(user_id=user_id, user_role=role, user_groups=[])
